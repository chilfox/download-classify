import json
import os
import threading
import time
from pathlib import Path

import pytest

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.tests.test_monitoring import BlockingModel, Model, wait_for


def test_clear_document_moves_and_records_original_destination_and_result(tmp_path):
    root = tmp_path / "inbox"
    root.mkdir()
    with TestClient(create_app(tmp_path / "settings.json", root, Model(), poll_interval=0.01)) as client:
        client.post("/monitor/start")
        (root / "new.txt").write_bytes(b"Original bytes\n")
        row = wait_for(client, bool)[0]
        assert row["outcome"] == "moved"
        assert row["mode"] == "automatic"
        assert row["destination"] == str(root / "Work" / "new.txt")
        assert not (root / "new.txt").exists()
        assert Path(row["destination"]).read_bytes() == b"Original bytes\n"
        assert row["recorded"] is True
        record = json.loads((tmp_path / "movements.jsonl").read_text())
        assert record["original"] == str(root / "new.txt")
        assert record["destination"] == row["destination"]
        assert record["result"] == "moved"
        assert record["time"]
        assert client.get("/status").json()["movement_enabled"] is True


@pytest.mark.parametrize("unsafe", ["symlink", "file"])
def test_unsafe_destination_remains_untouched_even_if_created_during_inference(tmp_path, unsafe):
    root = tmp_path / "inbox"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    model = BlockingModel()
    with TestClient(create_app(tmp_path / "settings.json", root, model, poll_interval=0.01)) as client:
        client.post("/monitor/start")
        source = root / "new.txt"
        source.write_bytes(b"original")
        try:
            assert model.entered.wait(2)
            if unsafe == "symlink":
                (root / "Work").symlink_to(outside, target_is_directory=True)
            else:
                (root / "Work").write_bytes(b"folder-name occupied")
        finally:
            model.release.set()
        row = wait_for(client, bool)[0]
        assert row["outcome"] == "failed"
        assert row["destination"] is None
        assert source.read_bytes() == b"original"
        assert list(outside.iterdir()) == []
        assert not (tmp_path / "movements.jsonl").exists()


def test_collision_created_during_inference_preserves_every_original_byte(tmp_path):
    root = tmp_path / "inbox"
    root.mkdir()
    model = BlockingModel()
    with TestClient(create_app(tmp_path / "settings.json", root, model, poll_interval=0.01)) as client:
        client.post("/monitor/start")
        (root / "new.txt").write_bytes(b"arriving document")
        try:
            assert model.entered.wait(2)
            folder = root / "Work"
            folder.mkdir()
            (folder / "new.txt").write_bytes(b"existing document")
            (folder / "new (1).txt").symlink_to(tmp_path / "outside.txt")
        finally:
            model.release.set()
        row = wait_for(client, bool)[0]
        assert row["destination"] == str(folder / "new (2).txt")
        assert (folder / "new.txt").read_bytes() == b"existing document"
        assert (folder / "new (2).txt").read_bytes() == b"arriving document"
        assert (folder / "new (1).txt").is_symlink()
        assert not (tmp_path / "outside.txt").exists()
        time.sleep(0.05)
        assert client.get("/results").json() == [row]


def test_concurrent_destination_creation_never_overwrites_either_document(tmp_path):
    root = tmp_path / "inbox"
    root.mkdir()
    folder = root / "Work"
    folder.mkdir()
    model = BlockingModel()
    with TestClient(create_app(tmp_path / "settings.json", root, model, poll_interval=0.01)) as client:
        client.post("/monitor/start")
        for index in range(20):
            name = f"race-{index}.txt"
            (root / name).write_bytes(b"source bytes")
            try:
                assert model.entered.wait(2)
                def compete():
                    try:
                        with (folder / name).open("xb") as stream:
                            stream.write(b"competitor bytes")
                    except FileExistsError:
                        pass
                racer = threading.Thread(target=compete)
                racer.start()
            finally:
                model.release.set()
            rows = wait_for(client, lambda rows: len(rows) == index + 1)
            racer.join()
            assert Path(rows[-1]["destination"]).read_bytes() == b"source bytes"
            if rows[-1]["destination"] != str(folder / name):
                assert (folder / name).read_bytes() == b"competitor bytes"
            model.entered.clear()
            model.release.clear()


@pytest.mark.parametrize("failure", ["directory", "symlink", "hardlink"])
def test_recording_failure_does_not_hide_successful_movement(tmp_path, failure):
    root = tmp_path / "inbox"
    root.mkdir()
    log = tmp_path / "movements.jsonl"
    outside = tmp_path / "outside-log"
    outside.write_bytes(b"untouched")
    if failure == "directory":
        log.mkdir()
    elif failure == "symlink":
        log.symlink_to(outside)
    else:
        log.hardlink_to(outside)
    with TestClient(create_app(tmp_path / "settings.json", root, Model(), poll_interval=0.01)) as client:
        client.post("/monitor/start")
        (root / "new.txt").write_bytes(b"original")
        row = wait_for(client, bool)[0]
        assert row["outcome"] == "moved"
        assert row["recorded"] is False
        assert "File moved, but movement recording failed" in row["recording_error"]
        assert Path(row["destination"]).read_bytes() == b"original"
        assert not (root / "new.txt").exists()
        assert outside.read_bytes() == b"untouched"


def test_process_restart_has_no_history_and_does_not_reprocess_moved_files(tmp_path):
    root = tmp_path / "inbox"
    root.mkdir()
    for run in range(2):
        with TestClient(create_app(tmp_path / "settings.json", root, Model(), poll_interval=0.01)) as client:
            assert client.get("/results").json() == []
            client.post("/monitor/start")
            (root / f"new-{run}.txt").write_text("original")
            rows = wait_for(client, bool)
            assert len(rows) == 1
            assert rows[0]["filename"] == f"new-{run}.txt"
    records = [json.loads(line) for line in (tmp_path / "movements.jsonl").read_text().splitlines()]
    assert len(records) == 2


def test_source_symlink_swap_is_never_moved_and_replacement_waits_for_stability(tmp_path):
    root = tmp_path / "inbox"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"outside bytes")
    model = BlockingModel()
    with TestClient(create_app(tmp_path / "settings.json", root, model, poll_interval=0.01)) as client:
        client.post("/monitor/start")
        source = root / "new.txt"
        source.write_bytes(b"old bytes")
        try:
            assert model.entered.wait(2)
            source.rename(root / "retained.part")
            source.symlink_to(outside)
        finally:
            model.release.set()
        time.sleep(0.1)
        assert client.get("/results").json() == []
        assert source.is_symlink()
        assert not (root / "Work").exists()
        assert outside.read_bytes() == b"outside bytes"
        source.unlink()
        source.write_bytes(b"replacement bytes")
        row = wait_for(client, bool)[0]
        assert row["outcome"] == "moved"
        assert Path(row["destination"]).read_bytes() == b"replacement bytes"
        assert (root / "retained.part").read_bytes() == b"old bytes"


def test_same_size_edit_with_restored_mtime_discards_stale_classification(tmp_path):
    class Changed(BlockingModel):
        def classify(self, opening, categories):
            super().classify(opening, categories)
            return {"Work": 0.9 if opening.text == "old" else 0.1,
                    "Personal": 0.1 if opening.text == "old" else 0.9, "Research": 0.1}, False, 100

    model = Changed()
    with TestClient(create_app(tmp_path / "settings.json", tmp_path, model, poll_interval=0.01)) as client:
        client.post("/monitor/start")
        source = tmp_path / "new.txt"
        source.write_text("old")
        try:
            assert model.entered.wait(2)
            info = source.stat()
            source.write_text("new")
            os.utime(source, ns=(info.st_atime_ns, info.st_mtime_ns))
        finally:
            model.release.set()
        row = wait_for(client, bool)[0]
        assert row["suggestion"] == "Personal"
        assert Path(row["destination"]).read_bytes() == b"new"
        assert not (tmp_path / "Work").exists()


def test_root_replaced_by_symlink_stops_monitoring_without_escaping(tmp_path):
    root = tmp_path / "inbox"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    model = BlockingModel()
    with TestClient(create_app(tmp_path / "settings.json", root, model, poll_interval=0.01)) as client:
        client.post("/monitor/start")
        (root / "new.txt").write_bytes(b"original")
        try:
            assert model.entered.wait(2)
            root.rename(tmp_path / "retained")
            root.symlink_to(outside, target_is_directory=True)
        finally:
            model.release.set()
        status = wait_for(client, lambda value: not value["monitoring"], "/status")
        assert "identity changed" in status["monitor_error"]
        assert list(outside.iterdir()) == []
        assert (tmp_path / "retained" / "new.txt").read_bytes() == b"original"
        assert client.get("/results").json() == []


def test_trace_path_must_not_append_to_the_document_that_just_moved(tmp_path):
    root = tmp_path / "inbox"
    root.mkdir()
    destination = root / "Work" / "new.txt"
    with TestClient(create_app(tmp_path / "settings.json", root, Model(), poll_interval=0.01,
                               movement_log=destination)) as client:
        client.post("/monitor/start")
        (root / "new.txt").write_bytes(b"original document")
        row = wait_for(client, bool)[0]
        assert row["outcome"] == "moved" and row["recorded"] is False
        assert "document" in row["recording_error"]
        assert destination.read_bytes() == b"original document"


def test_fifo_trace_failure_is_reported_without_blocking_processing(tmp_path):
    root = tmp_path / "inbox"
    root.mkdir()
    log = tmp_path / "movements.jsonl"
    os.mkfifo(log)
    with TestClient(create_app(tmp_path / "settings.json", root, Model(), poll_interval=0.01)) as client:
        client.post("/monitor/start")
        (root / "new.txt").write_bytes(b"original")
        row = wait_for(client, bool)[0]
        assert row["outcome"] == "moved" and row["recorded"] is False
        assert row["recording_error"]
        assert Path(row["destination"]).read_bytes() == b"original"


@pytest.mark.parametrize("name", ["文" * 83 + ".txt", "a" * 251 + ".txt"])
def test_maximum_length_filename_collision_preserves_bytes(tmp_path, name):
    root = tmp_path / "inbox"
    root.mkdir()
    folder = root / "Work"
    folder.mkdir()
    (folder / name).write_bytes(b"existing")
    with TestClient(create_app(tmp_path / "settings.json", root, Model(), poll_interval=0.01)) as client:
        client.post("/monitor/start")
        (root / name).write_bytes(b"arriving")
        row = wait_for(client, bool)[0]
        assert row["outcome"] == "moved"
        assert Path(row["destination"]).read_bytes() == b"arriving"
        assert (folder / name).read_bytes() == b"existing"


def test_uncertain_suggestions_only_fallback_and_unavailable_model_never_move(tmp_path):
    class Uncertain(Model):
        def classify(self, opening, categories):
            return {name: 0.1 for name in categories}, False, 100

    with TestClient(create_app(tmp_path / "settings.json", tmp_path, Uncertain(), poll_interval=0.01, mode="suggestions-only")) as client:
        client.post("/monitor/start")
        (tmp_path / "new.txt").write_bytes(b"original")
        row = wait_for(client, bool)[0]
        assert row["outcome"] == "suggestion-only"
        assert row["suggestion"] == "NeedsReview"
        assert row["destination"] is None and row["recorded"] is None
        assert (tmp_path / "new.txt").read_bytes() == b"original"
        assert not (tmp_path / "NeedsReview").exists()
        assert not (tmp_path / "movements.jsonl").exists()
