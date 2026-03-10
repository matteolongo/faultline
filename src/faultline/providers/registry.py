from __future__ import annotations

from faultline.providers.base import SignalProvider
from faultline.providers.live import (
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
