from __future__ import annotations

from abc import ABC, abstractmethod

from strategic_swarm_agent.models import RawSignal


class SignalProvider(ABC):
    source_name: str

    @abstractmethod
    def fetch(self, scenario_id: str) -> list[RawSignal]:
        raise NotImplementedError
