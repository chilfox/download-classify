"""One serial local classification and optional automatic movement worker."""
from __future__ import annotations

import json
import math
import os
import stat
from datetime import datetime, timezone
import threading
from pathlib import Path
from typing import Callable

from backend.classification import decide_topic
from backend.model_input import read_opening
from backend.movement import SourceChanged, move_document, open_directory, signature


class Monitor:
    def __init__(self, root: Path, categories: Callable, model, poll_interval: float, mode: str, log_path: Path):
        self.root = root
        self.mode = mode
        self.log_path = log_path
        self.root_identity = None
        self.categories = categories
        self.model = model
        self.interval = poll_interval
        self.lock = threading.Lock()
        self.shutdown = threading.Event()
        self.thread = threading.Thread(target=self.run, name="document-monitor", daemon=False)
        self.monitoring = False
        self.generation = 0
        self.busy = None
        self.model_status = "not-loaded"
        self.model_error = None
        self.monitor_error = None
        self.results = []
        self.baseline = set()
        self.previous = {}
        self.processed = {}

    def status(self):
        with self.lock:
            return {"folder": str(self.root), "monitoring": self.monitoring,
                    "processing": self.busy, "model_status": self.model_status,
                    "model_error": self.model_error, "monitor_error": self.monitor_error,
                    "movement_enabled": self.mode == "automatic", "mode": self.mode}

    def start(self):
        with self.lock:
            if self.busy:
                raise ValueError("An attempt is still finishing. Wait before restarting.")
            if not self.monitoring:
                if not self.root.is_dir() or self.root.is_symlink():
                    raise ValueError("Configured monitored folder must be an existing non-symlink directory")
                info = self.root.stat(follow_symlinks=False)
                self.root_identity = (info.st_dev, info.st_ino)
                self.baseline = {path.name for path in self.root.iterdir()}
                self.previous = {}
                self.processed = {}
                self.monitor_error = None
                self.generation += 1
                self.monitoring = True
        return self.status()

    def stop(self):
        with self.lock:
            self.monitoring = False
            self.generation += 1
        return self.status()

    def close(self):
        self.stop()
        self.shutdown.set()
        self.thread.join()

    @staticmethod
    def signature(path):
        return signature(path.stat(follow_symlinks=False))

    def scan(self):
        info = self.root.stat(follow_symlinks=False)
        if not stat.S_ISDIR(info.st_mode) or (info.st_dev, info.st_ino) != self.root_identity:
            raise OSError("Monitored folder identity changed or became a symbolic link")
        current = {}
        for path in self.root.iterdir():
            if path == self.log_path.absolute():
                continue
            name = path.name.lower()
            if name.startswith("~$") or name.endswith((".crdownload", ".part", ".partial", ".download", ".tmp", ".temp")):
                continue
            try:
                info = path.stat(follow_symlinks=False)
            except FileNotFoundError:
                continue
            if stat.S_ISREG(info.st_mode):
                current[path.name] = signature(info)
        return current

    def run(self):
        while not self.shutdown.wait(self.interval):
            with self.lock:
                if not self.monitoring:
                    continue
                generation = self.generation
            self.load_model()
            try:
                current = self.scan()
                with self.lock:
                    if not self.monitoring or self.generation != generation:
                        continue
                    pending = [(name, sig) for name, sig in sorted(current.items())
                               if name not in self.baseline and self.previous.get(name) == sig
                               and self.processed.get(name) != sig]
                    self.previous = current
                for name, sig in pending:
                    with self.lock:
                        if not self.monitoring or self.generation != generation or self.shutdown.is_set():
                            break
                        self.busy = name
                    self.attempt(name, sig)
            except OSError as error:
                with self.lock:
                    if self.generation == generation:
                        self.monitor_error = f"Could not scan monitored folder: {error}"
                        self.monitoring = False

    def load_model(self):
        if self.model_status != "not-loaded":
            return
        with self.lock:
            self.model_status = "loading"
        try:
            self.model.load()
        except Exception as error:
            with self.lock:
                self.model_status = "unavailable"
                self.model_error = f"Model loading failed: {error}"
        else:
            with self.lock:
                self.model_status = "ready"

    def attempt(self, name, signature):
        path = self.root / name
        moved = False
        result = {"filename": name, "outcome": "failed", "suggestion": None,
                  "mode": self.mode, "destination": None, "recorded": None, "recording_error": None,
                  "scores": None, "reason": None, "truncated": None,
                  "encoded_tokens": None, "categories": None}
        try:
            if path.is_symlink() or self.signature(path) != signature:
                return
            if path.suffix.lower() not in {".txt", ".md", ".markdown"}:
                result.update(outcome="skipped", reason="Unsupported format. Only TXT and Markdown are supported; all PDFs stay untouched.")
            else:
                categories = self.categories()
                if not categories:
                    raise ValueError("No topic categories configured")
                result["categories"] = categories
                opening = read_opening(path)
                if not opening.text.strip():
                    raise ValueError("No usable UTF-8 text in bounded opening")
                if path.is_symlink() or self.signature(path) != signature:
                    return
                if self.model_status == "unavailable":
                    raise RuntimeError(self.model_error)
                scores, truncated, tokens = self.model.classify(opening, categories)
                if set(scores) != set(categories) or any(not math.isfinite(score) or not 0 <= score <= 1 for score in scores.values()):
                    raise ValueError("Model must return a finite score in [0, 1] for every configured category")
                prediction, gap, clear = decide_topic(scores)
                result.update(outcome="suggestion-only", suggestion=prediction if clear else "NeedsReview",
                              scores=scores, truncated=truncated, encoded_tokens=tokens, top_two_gap=gap,
                              reason="Opening excerpt only; long-document quality unvalidated. Source untouched." if truncated else "Suggestion only. Source untouched.")
                if self.mode == "automatic":
                    destination = move_document(self.root, self.root_identity, name, signature, result["suggestion"])
                    moved = True
                    result.update(outcome="moved" if clear else "needs-review", destination=str(destination),
                                  reason="Opening excerpt only; long-document quality unvalidated. Original contents preserved." if truncated else "Original contents preserved.")
                    try:
                        if self.log_path.suffix.lower() != ".jsonl":
                            raise OSError("Movement trace must use a .jsonl path, not a document path")
                        self.log_path.parent.mkdir(parents=True, exist_ok=True)
                        parent_fd = open_directory(self.log_path.parent)
                        try:
                            fd = os.open(self.log_path.name, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=parent_fd)
                        finally:
                            os.close(parent_fd)
                        with os.fdopen(fd, "a", encoding="utf-8") as stream:
                            trace = os.fstat(stream.fileno())
                            if not stat.S_ISREG(trace.st_mode) or trace.st_nlink != 1:
                                raise OSError("Movement trace must be a regular file without hard links")
                            if (trace.st_dev, trace.st_ino) == signature[:2]:
                                raise OSError("Movement trace must not modify the moved document")
                            stream.write(json.dumps({"original": str(path), "destination": str(destination),
                                                     "time": datetime.now(timezone.utc).isoformat(), "result": result["outcome"]}, ensure_ascii=False) + "\n")
                            stream.flush()
                            os.fsync(stream.fileno())
                        result["recorded"] = True
                    except Exception as error:
                        result.update(recorded=False, recording_error=f"File moved, but movement recording failed: {error}")
        except SourceChanged:
            return
        except Exception as error:
            result.update(outcome="failed", reason=f"Processing failed: {error}")
        finally:
            try:
                unchanged = not path.is_symlink() and self.signature(path) == signature
            except OSError:
                unchanged = False
            with self.lock:
                if unchanged or moved:
                    self.results.append(result)
                    self.processed[name] = signature
                else:
                    # Discard stale scores; require two fresh scans before retry.
                    self.previous.pop(name, None)
                self.busy = None
