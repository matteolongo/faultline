from __future__ import annotations

import json
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
    source_name = "sample"
    source_key: str

    def __init__(self, repository: SampleScenarioRepository | None = None) -> None:
        self.repository = repository or SampleScenarioRepository()

    def fetch(self, scenario_id: str) -> list[RawSignal]:
        payload = self.repository.load(scenario_id)
        records = payload.get(self.source_key, [])
        return [RawSignal.model_validate(record) for record in records]


class NewsSignalProvider(SampleProvider):
    source_name = "news"
    source_key = "news"


class MarketContextProvider(SampleProvider):
    source_name = "market"
    source_key = "market"


class DarkSignalProvider(SampleProvider):
    source_name = "dark"
    source_key = "dark"
