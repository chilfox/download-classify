import time
import threading

import pytest

from fastapi.testclient import TestClient

from backend.app import create_app


class Model:
    def load(self):
        pass

    def validate_categories(self, categories):
        pass

    def classify(self, opening, categories):
        return {name: 0.9 if i == 0 else 0.1 for i, name in enumerate(categories)}, opening.read_truncated, 100


def wait_for(client, predicate, endpoint="/results"):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        value = client.get(endpoint).json()
        if predicate(value):
            return value
        time.sleep(0.01)
    raise AssertionError(f"Timed out: {value}")


def test_suggestions_only_fallback_never_touches_sources(tmp_path):
    root = tmp_path / "inbox"
    root.mkdir()
    (root / "existing.txt").write_text("existing")
    with TestClient(create_app(tmp_path / "settings.json", root, Model(), poll_interval=0.02, mode="suggestions-only")) as client:
        assert client.post("/monitor/start").status_code == 200
        (root / "invoice.txt").write_text("Invoice payment due")
        results = wait_for(client, lambda rows: len(rows) == 1)
        assert results[0]["filename"] == "invoice.txt"
        assert results[0]["outcome"] == "suggestion-only"
        assert results[0]["suggestion"] == "Work"
        assert results[0]["scores"] == {"Work": 0.9, "Personal": 0.1, "Research": 0.1}
        assert (root / "invoice.txt").read_text() == "Invoice payment due"
        assert client.get("/status").json()["movement_enabled"] is False
        client.post("/monitor/stop")
        assert client.get("/results").json() == results


@pytest.mark.parametrize("name", [".notes.txt", ".notes.md", ".notes.markdown"])
def test_new_hidden_documents_move_with_bytes_preserved_but_temporary_downloads_do_not(tmp_path, name):
    root = tmp_path / "inbox"
    root.mkdir()
    content = "Hidden document 隱藏筆記\n".encode("utf-8")
    existing = root / ".existing.txt"
    existing.write_bytes(b"baseline document")
    temporary_names = ["~$draft.txt", ".notes.txt.crdownload", ".notes.txt.part",
                       ".notes.txt.partial", ".notes.txt.download", ".notes.txt.tmp", ".notes.txt.temp"]
    with TestClient(create_app(tmp_path / "settings.json", root, Model(), poll_interval=0.01)) as client:
        assert client.post("/monitor/start").status_code == 200
        for temporary_name in temporary_names:
            (root / temporary_name).write_bytes(b"incomplete download")
        (root / "nested").mkdir()
        (root / "nested" / name).write_bytes(b"nested document")
        (root / ".link.txt").symlink_to(root / "nested" / name)
        (root / name).write_bytes(content)
        row = wait_for(client, bool)[0]
        assert row["filename"] == name
        assert row["outcome"] == "moved"
        assert row["destination"] == str(root / "Work" / name)
        assert (root / "Work" / name).read_bytes() == content
        assert not (root / name).exists()
        time.sleep(0.1)
        assert client.get("/results").json() == [row]
        assert existing.read_bytes() == b"baseline document"
        for temporary_name in temporary_names:
            assert (root / temporary_name).read_bytes() == b"incomplete download"
        assert (root / "nested" / name).read_bytes() == b"nested document"
        assert (root / ".link.txt").is_symlink()


def test_exclusions_dedup_and_restart_baseline(tmp_path):
    root = tmp_path / "inbox"
    root.mkdir()
    with TestClient(create_app(tmp_path / "settings.json", root, Model(), poll_interval=0.02)) as client:
        client.post("/monitor/start")
        (root / "nested").mkdir()
        (root / "nested" / "hidden.txt").write_text("nested")
        (root / "link.txt").symlink_to(root / "nested" / "hidden.txt")
        for name in ["file.txt.crdownload", "file.part", "file.download", "~$draft.txt", ".draft.txt.part", "draft.txt.tmp"]:
            (root / name).write_text("temporary")
        (root / "new.md").write_text("Research")
        rows = wait_for(client, lambda rows: any(row["filename"] == "new.md" for row in rows))
        assert [row["filename"] for row in rows] == ["new.md"]
        time.sleep(0.1)
        assert client.get("/results").json() == rows
        client.post("/monitor/stop")
        (root / "stopped.txt").write_text("during stop")
        client.post("/monitor/start")
        (root / "later.txt").write_text("later")
        rows = wait_for(client, lambda rows: len(rows) >= 2)
        assert [row["filename"] for row in rows] == ["new.md", "later.txt"]


@pytest.mark.parametrize("mode", ["automatic", "suggestions-only"])
def test_start_loads_model_in_background_once_and_reports_unavailability(tmp_path, mode):
    class UnavailableModel(Model):
        def load(self):
            raise RuntimeError("Cached weights missing")

    with TestClient(create_app(tmp_path / "settings.json", tmp_path, UnavailableModel(), poll_interval=0.02, mode=mode)) as client:
        assert client.post("/monitor/start").status_code == 200
        status = wait_for(client, lambda status: status["model_status"] == "unavailable", "/status")
        assert "Cached weights missing" in status["model_error"]
        (tmp_path / "new.txt").write_text("local text")
        rows = wait_for(client, lambda rows: len(rows) == 1)
        assert rows[0]["outcome"] == "failed" and rows[0]["scores"] is None
        assert "Model loading failed" in rows[0]["reason"]
        assert (tmp_path / "new.txt").read_text() == "local text"


@pytest.mark.parametrize("scores, expected", [
    ({"One": 0.649999}, "NeedsReview"), ({"One": 0.65}, "One"),
    ({"One": 0.79}, "One"),
    ({"One": 0.649999, "Two": 0.1}, "NeedsReview"),
    ({"One": 0.65, "Two": 0.4}, "One"),
    ({"One": 0.65, "Two": 0.54}, "One"),
    ({"One": 0.65, "Two": 0.56}, "NeedsReview"),
    ({"One": 0.75, "Two": 0.65}, "One"),
    ({"One": 0.75, "Two": 0.650001}, "NeedsReview"),
    ({"One": 0.75, "Two": 0.649999}, "One"),
    ({"One": 0.9, "Two": 0.8}, "One"),
    ({"One": 0.9, "Two": 0.1}, "One"),
    ({"One": 0.8, "Two": 0.6}, "One"),
    ({"One": 0.9, "Two": 0.899}, "NeedsReview"),
])
def test_fixed_thresholds_use_all_real_candidate_scores(tmp_path, scores, expected):
    class ScoredModel(Model):
        def classify(self, opening, categories):
            return scores, False, 100

    with TestClient(create_app(tmp_path / "settings.json", tmp_path, ScoredModel(), poll_interval=0.01)) as client:
        client.put("/settings", json={"categories": [{"name": name, "description": "Topic"} for name in scores]})
        client.post("/monitor/start")
        (tmp_path / "new.txt").write_text("text")
        row = wait_for(client, lambda rows: bool(rows))[0]
        assert row["suggestion"] == expected and row["scores"] == scores
        assert row["outcome"] == ("needs-review" if expected == "NeedsReview" else "moved")
        assert (tmp_path / expected / "new.txt").read_text() == "text"
        assert not (tmp_path / "new.txt").exists()


@pytest.mark.parametrize("scores", [{"Work": 0.9}, {"Work": float("nan"), "Personal": 0.1, "Research": 0.1},
                                    {"Work": 1.1, "Personal": 0.1, "Research": 0.1}])
def test_invalid_or_winning_only_scores_are_failures_not_suggestions(tmp_path, scores):
    class InvalidModel(Model):
        def classify(self, opening, categories):
            return scores, False, 100

    with TestClient(create_app(tmp_path / "settings.json", tmp_path, InvalidModel(), poll_interval=0.01)) as client:
        client.post("/monitor/start")
        (tmp_path / "new.txt").write_text("text")
        row = wait_for(client, lambda rows: bool(rows))[0]
        assert row["outcome"] == "failed" and row["scores"] is None
        assert "every configured category" in row["reason"]


def test_unsupported_unusable_and_inference_errors_are_explicit_and_preserve_bytes(tmp_path):
    class FailingModel(Model):
        def classify(self, opening, categories):
            raise RuntimeError("Inference unavailable")

    originals = {"paper.pdf": b"%PDF text", "archive.zip": b"PK unsupported", "binary.txt": b"\xff", "empty.md": b" \n", "valid.txt": b"Valid text"}
    with TestClient(create_app(tmp_path / "settings.json", tmp_path, FailingModel(), poll_interval=0.01)) as client:
        client.post("/monitor/start")
        for name, content in originals.items():
            (tmp_path / name).write_bytes(content)
        rows = wait_for(client, lambda rows: len(rows) == 5)
        by_name = {row["filename"]: row for row in rows}
        assert by_name["paper.pdf"]["outcome"] == "failed"
        assert "PDF text extraction failed" in by_name["paper.pdf"]["reason"]
        assert by_name["archive.zip"]["outcome"] == "skipped"
        assert "UTF-8" in by_name["empty.md"]["reason"]
        assert "decode" in by_name["binary.txt"]["reason"]
        assert "Inference unavailable" in by_name["valid.txt"]["reason"]
        for name, content in originals.items():
            assert (tmp_path / name).read_bytes() == content


def test_oversized_opening_is_disclosed_without_modifying_unicode_source(tmp_path):
    content = ("發票付款期限。" * 10000).encode("utf-8")
    with TestClient(create_app(tmp_path / "settings.json", tmp_path, Model(), poll_interval=0.01)) as client:
        client.post("/monitor/start")
        (tmp_path / "long.txt").write_bytes(content)
        row = wait_for(client, lambda rows: bool(rows))[0]
        assert row["truncated"] is True
        assert "Opening excerpt only" in row["reason"]
        assert (tmp_path / "Work" / "long.txt").read_bytes() == content


def test_settings_schema_budget_errors_are_explicit_and_preserve_saved_settings(tmp_path):
    class BudgetModel(Model):
        def validate_categories(self, categories):
            if "Oversized" in categories:
                raise ValueError("Category schema alone exceeds the 512 encoded-token input budget")

    with TestClient(create_app(tmp_path / "settings.json", tmp_path, BudgetModel(), poll_interval=0.01)) as client:
        client.post("/monitor/start")
        wait_for(client, lambda status: status["model_status"] == "ready", "/status")
        response = client.put("/settings", json={"categories": [{"name": "Oversized", "description": "Too much"}]})
        assert response.status_code == 422
        assert "512 encoded-token" in response.json()["detail"]
        assert client.get("/settings").json()["categories"][0]["name"] == "Work"


def test_no_topics_saved_on_disk_is_an_explicit_failure_not_fake_success(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text('{"categories": []}')
    with TestClient(create_app(settings, tmp_path, Model(), poll_interval=0.01)) as client:
        client.post("/monitor/start")
        (tmp_path / "new.txt").write_text("text")
        row = wait_for(client, lambda rows: bool(rows))[0]
        assert row["outcome"] == "failed" and row["suggestion"] is None
        assert "No topic categories configured" in row["reason"]
        assert client.put("/settings", json={"categories": []}).status_code == 422


def test_reading_failure_is_reported_and_not_repeated(tmp_path):
    path = tmp_path / "unreadable.txt"
    with TestClient(create_app(tmp_path / "settings.json", tmp_path, Model(), poll_interval=0.01)) as client:
        client.post("/monitor/start")
        path.write_text("Private bytes")
        path.chmod(0)
        try:
            row = wait_for(client, lambda rows: bool(rows))[0]
            assert row["outcome"] == "failed" and row["scores"] is None
            assert "Permission denied" in row["reason"]
            time.sleep(0.05)
            assert client.get("/results").json() == [row]
        finally:
            path.chmod(0o600)
        assert path.read_text() == "Private bytes"


def test_model_is_reused_across_stops_and_starts(tmp_path):
    class LoadOnce(Model):
        loaded = False

        def load(self):
            if self.loaded:
                raise RuntimeError("Model was loaded again")
            self.loaded = True

    with TestClient(create_app(tmp_path / "settings.json", tmp_path, LoadOnce(), poll_interval=0.01)) as client:
        client.post("/monitor/start")
        (tmp_path / "first.txt").write_text("first")
        wait_for(client, lambda rows: len(rows) == 1)
        client.post("/monitor/stop")
        client.post("/monitor/start")
        (tmp_path / "second.txt").write_text("second")
        rows = wait_for(client, lambda rows: len(rows) == 2)
        assert all(row["outcome"] == "moved" for row in rows)
        assert client.get("/status").json()["model_status"] == "ready"


def test_continuously_changing_download_waits_for_consecutive_stable_scans(tmp_path):
    with TestClient(create_app(tmp_path / "settings.json", tmp_path, Model(), poll_interval=0.1)) as client:
        client.post("/monitor/start")
        path = tmp_path / "downloading.txt"
        for i in range(30):
            path.write_text(f"download chunk {i}")
            time.sleep(0.01)
        assert client.get("/results").json() == []
        row = wait_for(client, lambda rows: bool(rows))[0]
        assert row["filename"] == "downloading.txt"
        assert (tmp_path / "Work" / path.name).read_text() == "download chunk 29"


class BlockingModel(Model):
    def __init__(self):
        self.entered = threading.Event()
        self.release = threading.Event()

    def classify(self, opening, categories):
        self.entered.set()
        if not self.release.wait(3):
            raise TimeoutError("Test did not release inference")
        return super().classify(opening, categories)


def test_status_and_stop_remain_responsive_during_inference_and_categories_are_snapshotted(tmp_path):
    model = BlockingModel()
    with TestClient(create_app(tmp_path / "settings.json", tmp_path, model, poll_interval=0.02)) as client:
        client.put("/settings", json={"categories": [{"name": "Before", "description": "Original"}]})
        client.post("/monitor/start")
        (tmp_path / "active.txt").write_text("original")
        try:
            assert model.entered.wait(2)
            started = time.monotonic()
            status = client.get("/status").json()
            assert status["processing"] == "active.txt"
            assert status["monitoring"] is True
            stopped = client.post("/monitor/stop").json()
            assert stopped["monitoring"] is False and stopped["processing"] == "active.txt"
            assert time.monotonic() - started < 0.5
            assert client.post("/monitor/start").status_code == 422
            client.put("/settings", json={"categories": [{"name": "After", "description": "Updated"}]})
            (tmp_path / "not-started.txt").write_text("untouched")
        finally:
            model.release.set()
        rows = wait_for(client, lambda rows: len(rows) == 1)
        assert rows[0]["suggestion"] == "Before"
        assert rows[0]["categories"] == {"Before": "Original"}
        assert (tmp_path / "Before" / "active.txt").read_text() == "original"
        assert (tmp_path / "not-started.txt").read_text() == "untouched"
        client.post("/monitor/start")
        (tmp_path / "later.txt").write_text("later")
        rows = wait_for(client, lambda rows: len(rows) == 2)
        assert rows[1]["suggestion"] == "After"
        assert (tmp_path / "After" / "later.txt").read_text() == "later"


def test_lifespan_shutdown_waits_for_active_attempt_and_does_not_start_another(tmp_path):
    model = BlockingModel()
    application = create_app(tmp_path / "settings.json", tmp_path, model, poll_interval=0.01)
    with TestClient(application) as client:
        client.post("/monitor/start")
        (tmp_path / "first.txt").write_text("first")
        try:
            assert model.entered.wait(2)
            (tmp_path / "second.txt").write_text("second")
            # Shutdown must drain the active attempt without picking up second.
            release = threading.Timer(0.1, model.release.set)
            release.start()
        except BaseException:
            model.release.set()
            raise
    release.join()
    observer = TestClient(application)
    assert observer.get("/status").json()["monitoring"] is False
    assert observer.get("/status").json()["processing"] is None
    assert [row["filename"] for row in observer.get("/results").json()] == ["first.txt"]
    assert (tmp_path / "second.txt").read_text() == "second"


def test_changed_during_inference_discards_stale_scores_and_retries_after_stability(tmp_path):
    class ChangingModel(BlockingModel):
        def classify(self, opening, categories):
            super().classify(opening, categories)
            if opening.text == "new content":
                return {"Work": 0.1, "Personal": 0.95, "Research": 0.1}, False, 100
            return {"Work": 0.95, "Personal": 0.1, "Research": 0.1}, False, 100

    model = ChangingModel()
    with TestClient(create_app(tmp_path / "settings.json", tmp_path, model, poll_interval=0.02)) as client:
        client.post("/monitor/start")
        path = tmp_path / "changing.txt"
        path.write_text("old")
        try:
            assert model.entered.wait(2)
            path.write_text("new content")
            assert client.get("/results").json() == []
        finally:
            model.release.set()
        rows = wait_for(client, lambda rows: len(rows) == 1)
        assert rows[0]["outcome"] == "moved"
        assert rows[0]["suggestion"] == "Personal"
        assert (tmp_path / "Personal" / path.name).read_text() == "new content"
        assert not (tmp_path / "Work").exists()
        time.sleep(0.1)
        assert client.get("/results").json() == rows
