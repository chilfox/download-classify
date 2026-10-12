"""One serial, local-only suggestions worker. No source writes or movement."""
from __future__ import annotations

import math
import stat
import threading
from pathlib import Path
from typing import Callable

from backend.model_input import read_opening

MIN_SCORE = 0.80
MIN_GAP = 0.20


class Monitor:
    def __init__(self, root: Path, categories: Callable, model, poll_interval: float):
        self.root = root
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
                    "movement_enabled": False, "mode": "suggestions-only"}

    def start(self):
        with self.lock:
            if self.busy:
                raise ValueError("An attempt is still finishing. Wait before restarting.")
            if not self.monitoring:
                if not self.root.is_dir() or self.root.is_symlink():
                    raise ValueError("Configured monitored folder must be an existing non-symlink directory")
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
        stat = path.stat(follow_symlinks=False)
        return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns

    def scan(self):
        if self.root.is_symlink():
            raise OSError("Monitored folder became a symbolic link")
        current = {}
        for path in self.root.iterdir():
            name = path.name.lower()
            if name.startswith((".", "~$")) or name.endswith((".crdownload", ".part", ".partial", ".download", ".tmp", ".temp")):
                continue
            try:
                info = path.stat(follow_symlinks=False)
            except FileNotFoundError:
                continue
            if stat.S_ISREG(info.st_mode):
                current[path.name] = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
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
        result = {"filename": name, "outcome": "failed", "suggestion": None,
                  "scores": None, "reason": None, "truncated": None,
                  "encoded_tokens": None, "categories": None}
        try:
            if path.is_symlink() or self.signature(path) != signature:
                return
            if path.suffix.lower() not in {".txt", ".md", ".markdown"}:
                result.update(outcome="unsupported", reason="Unsupported format. Only TXT and Markdown are supported; all PDFs stay untouched.")
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
                ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
                gap = ranked[0][1] - ranked[1][1] if len(ranked) > 1 else None
                clear = ranked[0][1] >= MIN_SCORE and (gap is None or gap >= MIN_GAP)
                result.update(outcome="suggestion-only", suggestion=ranked[0][0] if clear else "NeedsReview",
                              scores=scores, truncated=truncated, encoded_tokens=tokens, top_two_gap=gap,
                              reason="Opening excerpt only; long-document quality unvalidated. Source untouched." if truncated else "Suggestion only. Source untouched.")
        except Exception as error:
            result["reason"] = f"Processing failed: {error}"
        finally:
            try:
                unchanged = not path.is_symlink() and self.signature(path) == signature
            except OSError:
                unchanged = False
            with self.lock:
                if unchanged:
                    self.results.append(result)
                    self.processed[name] = signature
                else:
                    # Discard stale scores; require two fresh scans before retry.
                    self.previous.pop(name, None)
                self.busy = None
