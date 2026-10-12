from fastapi.testclient import TestClient

from backend.app import app


def client_at(tmp_path):
    app.state.settings_path = tmp_path / "categories.json"
    return TestClient(app)


def test_default_settings_save_and_survive_app_restart(tmp_path):
    client = client_at(tmp_path)
    defaults = client.get("/settings").json()["categories"]
    assert [item["name"] for item in defaults] == ["Work", "Personal", "Research"]
    changed = {"categories": [{"name": "Research", "description": "Papers and notes"}]}
    assert client.put("/settings", json=changed).json() == changed
    app.state.settings_path = tmp_path / "categories.json"
    assert TestClient(app).get("/settings").json() == changed


def test_rejects_unsafe_and_colliding_folder_names_without_replacing_saved_config(tmp_path):
    client = client_at(tmp_path)
    valid = {"categories": [{"name": "Work", "description": "Projects"}]}
    client.put("/settings", json=valid)
    for name in ["", "..", "../escape", "a/b", "a\\b", "NeedsReview", "nEeDsReViEw"]:
        bad = {"categories": [{"name": name, "description": "x"}]}
        assert client.put("/settings", json=bad).status_code == 422
        assert client.get("/settings").json() == valid
    duplicate = {"categories": [{"name": "Résumé", "description": "a"}, {"name": "Re\u0301sume\u0301", "description": "b"}]}
    assert client.put("/settings", json=duplicate).status_code == 422
    assert client.get("/settings").json() == valid


def test_failed_save_preserves_previous_settings(tmp_path):
    client = client_at(tmp_path)
    valid = {"categories": [{"name": "Work", "description": "Projects"}]}
    client.put("/settings", json=valid)
    app.state.settings_path = tmp_path / "missing" / "not-a-directory" / "settings.json"
    blocked = tmp_path / "missing"
    blocked.write_text("file")
    response = client.put("/settings", json={"categories": [{"name": "New", "description": "New"}]})
    assert response.status_code == 500
    assert (tmp_path / "categories.json").read_text()
