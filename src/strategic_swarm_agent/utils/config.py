from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from strategic_swarm_agent.models import Archetype, FragilityPattern, HistoricalAnalog

ROOT_DIR = Path(__file__).resolve().parents[3]
CONFIG_DIR = ROOT_DIR / "configs"


@lru_cache(maxsize=1)
def load_yaml_config(name: str) -> dict[str, Any]:
    path = CONFIG_DIR / name
    return yaml.safe_load(path.read_text())


@lru_cache(maxsize=1)
def load_archetypes() -> dict[str, Any]:
    payload = load_yaml_config("archetypes.yaml")
    analogs = {
        item["id"]: HistoricalAnalog(
            name=item["name"],
            reference=item["reference"],
            why_relevant=item["why_relevant"],
        )
        for item in payload["historical_analogs"]
    }
    topologies = [Archetype.model_validate(item) for item in payload["topologies"]]
    fragility_patterns = [
        FragilityPattern.model_validate(item) for item in payload["fragility_patterns"]
    ]
    return {
        "version": payload["version"],
        "topologies": topologies,
        "historical_analogs": analogs,
        "fragility_patterns": fragility_patterns,
    }


@lru_cache(maxsize=1)
def load_scoring_config() -> dict[str, Any]:
    return load_yaml_config("scoring.yaml")


@lru_cache(maxsize=1)
def load_prompts() -> dict[str, str]:
    return load_yaml_config("prompts.yaml")


@lru_cache(maxsize=1)
def load_provider_config() -> dict[str, Any]:
    return load_yaml_config("providers.yaml")
