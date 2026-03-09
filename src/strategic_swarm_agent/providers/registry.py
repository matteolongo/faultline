from __future__ import annotations

from strategic_swarm_agent.providers.base import SignalProvider
from strategic_swarm_agent.providers.live import (
    AlphaVantageProvider,
    FredProvider,
    GDELTProvider,
    NewsAPIProvider,
)


def build_live_providers() -> list[SignalProvider]:
    return [
        NewsAPIProvider(),
        AlphaVantageProvider(),
        FredProvider(),
        GDELTProvider(),
    ]
