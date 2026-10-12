import json
import os
import tempfile
import unicodedata
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

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


def create_app(settings_path: Path | str | None = None) -> FastAPI:
    application = FastAPI(title="Download Classify API")
    application.state.settings_path = Path(settings_path) if settings_path else SETTINGS_PATH

    def load_settings(request: Request) -> CategorySettings:
        path = request.app.state.settings_path
        if not path.exists():
            return CategorySettings(categories=DEFAULT_CATEGORIES)
        try:
            return validated(CategorySettings.model_validate_json(path.read_text(encoding="utf-8")))
        except (ValueError, OSError) as error:
            raise HTTPException(status_code=500, detail=f"Saved category settings are invalid: {error}") from error

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/settings", response_model=CategorySettings)
    @application.get("/categories", response_model=CategorySettings)
    def get_settings(request: Request) -> CategorySettings:
        return load_settings(request)

    @application.put("/settings", response_model=CategorySettings)
    @application.put("/categories", response_model=CategorySettings)
    def save_settings(settings: CategorySettings, request: Request) -> CategorySettings:
        try:
            settings = validated(settings)
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

    return application


app = create_app()
