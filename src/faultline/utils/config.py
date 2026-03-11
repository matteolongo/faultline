from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT_DIR = Path(__file__).resolve().parents[3]
CONFIG_DIR = ROOT_DIR / "configs"


@lru_cache(maxsize=1)
def load_yaml_config(name: str) -> dict[str, Any]:
    path = CONFIG_DIR / name
    return yaml.safe_load(path.read_text())


@lru_cache(maxsize=1)
def load_prompts() -> dict[str, str]:
    return load_yaml_config("prompts.yaml")


@lru_cache(maxsize=1)
def load_mechanisms() -> dict[str, Any]:
    return load_yaml_config("mechanisms.yaml")


@lru_cache(maxsize=1)
def load_stages() -> dict[str, Any]:
    return load_yaml_config("stages.yaml")


@lru_cache(maxsize=1)
def load_scoring() -> dict[str, Any]:
    return load_yaml_config("scoring.yaml")


@lru_cache(maxsize=1)
def load_provider_config() -> dict[str, Any]:
    return load_yaml_config("providers.yaml")
