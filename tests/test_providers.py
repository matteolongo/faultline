import json
from datetime import UTC, datetime
from pathlib import Path

from strategic_swarm_agent.providers.live import AlphaVantageProvider, FredProvider, GDELTProvider, NewsAPIProvider


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text())


def test_newsapi_payload_parses_to_raw_signal() -> None:
    provider = NewsAPIProvider()
    signals = provider.parse_everything_payload(_load("newsapi_everything.json"), fetched_at=datetime.now(UTC))
    assert len(signals) == 1
    assert signals[0].provider_name == "newsapi"
    assert signals[0].source == "news"
    assert signals[0].source_url == "https://example.com/news/cable-rerouting"


def test_alphavantage_payloads_parse_news_and_quotes() -> None:
    provider = AlphaVantageProvider()
    news = provider.parse_news_payload(_load("alphavantage_news_sentiment.json"), fetched_at=datetime.now(UTC))
    quotes = provider.parse_quote_payload(_load("alphavantage_global_quote.json"), symbol="QQQ", fetched_at=datetime.now(UTC))
    assert news[0].query_key == "NEWS_SENTIMENT"
    assert "technology" in news[0].tags
    assert quotes[0].signal_type == "market-quote"


def test_fred_payloads_parse_updates_and_observations() -> None:
    provider = FredProvider()
    updates = provider.parse_updates_payload(_load("fred_series_updates.json"), fetched_at=datetime.now(UTC))
    observations = provider.parse_observations_payload(_load("fred_series_observations.json"), series_id="DGS10", fetched_at=datetime.now(UTC))
    assert updates[0].source == "macro"
    assert observations[0].provider_item_id == "DGS10"


def test_gdelt_payload_parses_structural_event() -> None:
    provider = GDELTProvider()
    signals = provider.parse_doc_payload(_load("gdelt_doc_artlist.json"), fetched_at=datetime.now(UTC))
    assert signals[0].provider_name == "gdelt"
    assert signals[0].source == "alt"
