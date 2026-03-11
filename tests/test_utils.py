from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from pydantic import BaseModel

from faultline.utils.io import ensure_directory, serialize_model, write_json, write_text
from faultline.utils.logging import JsonLogFormatter, configure_logging

# ── io tests ────────────────────────────────────────────────────────────────


class _SimpleModel(BaseModel):
    name: str
    value: int


def test_ensure_directory_creates_nested_dirs(tmp_path):
    target = tmp_path / "a" / "b" / "c"
    result = ensure_directory(target)
    assert result == target
    assert target.is_dir()


def test_ensure_directory_is_idempotent(tmp_path):
    ensure_directory(tmp_path)
    ensure_directory(tmp_path)  # should not raise
    assert tmp_path.is_dir()


def test_serialize_model_pydantic(tmp_path):
    model = _SimpleModel(name="test", value=42)
    result = serialize_model(model)
    assert result == {"name": "test", "value": 42}


def test_serialize_model_list_of_models():
    models = [_SimpleModel(name="a", value=1), _SimpleModel(name="b", value=2)]
    result = serialize_model(models)
    assert result == [{"name": "a", "value": 1}, {"name": "b", "value": 2}]


def test_serialize_model_dict_of_models():
    data = {"x": _SimpleModel(name="x", value=10)}
    result = serialize_model(data)
    assert result == {"x": {"name": "x", "value": 10}}


def test_serialize_model_passthrough_for_primitives():
    assert serialize_model("hello") == "hello"
    assert serialize_model(42) == 42
    assert serialize_model(None) is None


def test_write_json_creates_file_and_is_valid_json(tmp_path):
    target = tmp_path / "sub" / "out.json"
    write_json(target, {"key": "value", "num": 1})
    assert target.exists()
    loaded = json.loads(target.read_text())
    assert loaded == {"key": "value", "num": 1}


def test_write_json_serializes_pydantic(tmp_path):
    target = tmp_path / "model.json"
    write_json(target, _SimpleModel(name="hi", value=7))
    loaded = json.loads(target.read_text())
    assert loaded == {"name": "hi", "value": 7}


def test_write_text_creates_file(tmp_path):
    target = tmp_path / "nested" / "file.txt"
    write_text(target, "hello world")
    assert target.read_text() == "hello world"


# ── logging tests ────────────────────────────────────────────────────────────


def test_json_log_formatter_produces_valid_json():
    formatter = JsonLogFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    output = formatter.format(record)
    parsed = json.loads(output)
    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test.logger"
    assert parsed["message"] == "hello world"
    assert "timestamp" in parsed


def test_configure_logging_sets_json_handler(monkeypatch):
    monkeypatch.setenv("FAULTLINE_LOG_LEVEL", "WARNING")
    root = logging.getLogger()
    # Clear handlers to force reconfigure
    root.handlers.clear()
    configure_logging()
    assert root.level == logging.WARNING
    assert any(isinstance(h.formatter, JsonLogFormatter) for h in root.handlers)


def test_configure_logging_is_idempotent():
    root = logging.getLogger()
    handler_count_before = len(root.handlers)
    configure_logging()
    configure_logging()
    assert len(root.handlers) == handler_count_before
