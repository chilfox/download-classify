from contextlib import asynccontextmanager
import json
import os
import tempfile
import unicodedata
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from backend.model import LocalModel
from backend.monitor import Monitor

DEFAULT_CATEGORIES = [
    {"name": "Work", "description": "Work documents and projects"},
    {"name": "Personal", "description": "Personal documents and records"},
    {"name": "Research", "description": "Research papers and reference material"},
]
SETTINGS_PATH = Path(os.environ.get("DOWNLOAD_CLASSIFY_SETTINGS_PATH", Path.home() / ".download-classify" / "categories.json"))


class Category(BaseModel):
    name: Annotated[str, Field(max_length=120)]
    description: Annotated[str, Field(max_length=2000)]


class CategorySettings(BaseModel):
    categories: Annotated[list[Category], Field(min_length=1, max_length=50)]


def validated(settings: CategorySettings) -> CategorySettings:
    names: set[str] = set()
    for category in settings.categories:
        name = unicodedata.normalize("NFC", category.name).strip()
        category.name = name
        if not name:
            raise ValueError("Category names cannot be empty")
        if name in {".", ".."} or "/" in name or "\\" in name or ":" in name or len(name.encode("utf-8")) > 255 or any(unicodedata.category(char) == "Cc" for char in name):
            raise ValueError(f"Invalid folder name: {category.name}")
        key = unicodedata.normalize("NFD", name).casefold()
        if key == "needsreview":
            raise ValueError("NeedsReview is reserved")
        if key in names:
            raise ValueError(f"Duplicate category name: {category.name}")
        names.add(key)
    return settings


def create_app(settings_path: Path | str | None = None, monitored_folder: Path | str | None = None,
               model=None, poll_interval: float = 1.0) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application):
        monitor.thread.start()
        try:
            yield
        finally:
            monitor.close()

    application = FastAPI(title="Download Classify API", lifespan=lifespan)
    application.state.settings_path = Path(settings_path) if settings_path else SETTINGS_PATH

    def load_categories() -> CategorySettings:
        path = application.state.settings_path
        if not path.exists():
            return CategorySettings(categories=DEFAULT_CATEGORIES)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("categories") == []:
                raise ValueError("No topic categories configured")
            return validated(CategorySettings.model_validate(data))
        except (ValueError, OSError) as error:
            raise HTTPException(status_code=500, detail=f"Saved category settings are invalid: {error}") from error

    def load_settings(request: Request) -> CategorySettings:
        return load_categories()

    root = Path(monitored_folder or os.environ.get("DOWNLOAD_CLASSIFY_FOLDER", str(Path.home() / "DownloadClassifyDemo"))).absolute()
    monitor = Monitor(root, lambda: {category.name: category.description for category in load_categories().categories},
                      model if model is not None else LocalModel(), poll_interval)

    @application.get("/status")
    def status():
        return monitor.status()

    @application.get("/results")
    def results():
        with monitor.lock:
            return list(monitor.results)

    @application.post("/monitor/start")
    def start():
        try:
            return monitor.start()
        except (ValueError, OSError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @application.post("/monitor/stop")
    def stop():
        return monitor.stop()

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/settings", response_model=CategorySettings)
    def get_settings(request: Request) -> CategorySettings:
        return load_settings(request)

    @application.put("/settings", response_model=CategorySettings)
    def save_settings(settings: CategorySettings, request: Request) -> CategorySettings:
        try:
            settings = validated(settings)
            if monitor.status()["model_status"] == "ready":
                monitor.model.validate_categories({category.name: category.description for category in settings.categories})
            path = request.app.state.settings_path
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    stream.write(settings.model_dump_json(indent=2) + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            return settings
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except OSError as error:
            raise HTTPException(status_code=500, detail=f"Could not save category settings: {error}") from error
        except Exception as error:
            raise HTTPException(status_code=500, detail=f"Could not validate category schema: {error}") from error

    return application


app = create_app()
