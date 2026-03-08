from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from strategic_swarm_agent.models import RawSignal
from strategic_swarm_agent.providers.base import SignalProvider

SAMPLE_DIR = Path(__file__).resolve().parents[3] / "data" / "samples"


class SampleScenarioRepository:
    def load(self, scenario_id: str) -> dict:
        path = SAMPLE_DIR / f"{scenario_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Unknown scenario: {scenario_id}")
        return json.loads(path.read_text())

    def scenario_ids(self) -> list[str]:
        return sorted(path.stem for path in SAMPLE_DIR.glob("*.json"))


class SampleProvider(SignalProvider):
    provider_name = "sample"
    source_family = "sample"
    source_key: str

    def __init__(self, repository: SampleScenarioRepository | None = None) -> None:
        self.repository = repository or SampleScenarioRepository()

    def fetch(self, scenario_id: str) -> list[RawSignal]:
        payload = self.repository.load(scenario_id)
        records = payload.get(self.source_key, [])
        return [RawSignal.model_validate(record) for record in records]

    def fetch_window(self, start_at: datetime, end_at: datetime) -> list[RawSignal]:
        raise NotImplementedError("Sample providers are scenario-based only. Use fetch(scenario_id).")


class NewsSignalProvider(SampleProvider):
    provider_name = "sample-news"
    source_family = "news"
    source_key = "news"


class MarketContextProvider(SampleProvider):
    provider_name = "sample-market"
    source_family = "market"
    source_key = "market"


class DarkSignalProvider(SampleProvider):
    provider_name = "sample-dark"
    source_family = "alt"
    source_key = "dark"
