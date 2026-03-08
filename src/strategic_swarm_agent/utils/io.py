from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def serialize_model(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [serialize_model(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize_model(item) for key, item in value.items()}
    return value


def write_json(path: Path, payload: Any) -> None:
    ensure_directory(path.parent)
    path.write_text(json.dumps(serialize_model(payload), indent=2, sort_keys=True))


def write_text(path: Path, content: str) -> None:
    ensure_directory(path.parent)
    path.write_text(content)
