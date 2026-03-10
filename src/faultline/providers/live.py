from __future__ import annotations

import hashlib
import os
from collections.abc import Iterable
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx

from faultline.models import RawSignal
from faultline.providers.base import HTTPProvider
from faultline.utils.config import load_provider_config


def _iso_to_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    if len(value) == 15 and "T" in value and "+" not in value and "Z" not in value:
        return datetime.strptime(value, "%Y%m%dT%H%M%S").replace(tzinfo=UTC)
    candidate = value.replace("Z", "+00:00")
    return datetime.fromisoformat(candidate)


def _compact_text(*parts: str | None) -> str:
    return " ".join(part.strip() for part in parts if part and part.strip())


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _domain(url: str | None) -> str | None:
    if not url:
        return None
    return urlparse(url).netloc or None


def _coerce_tags(values: Iterable[str]) -> list[str]:
    tags = []
    for value in values:
        token = value.strip().lower().replace(" ", "-")
        if token and token not in tags:
            tags.append(token)
    return tags


class NewsAPIProvider(HTTPProvider):
    provider_name = "newsapi"
    source_family = "news"

    def __init__(self, *, transport: httpx.BaseTransport | None = None) -> None:
        config = load_provider_config()
        defaults = config["defaults"]
        provider_cfg = config["providers"]["newsapi"]
        super().__init__(
            timeout_seconds=defaults["timeout_seconds"],
            retries=defaults["retries"],
            backoff_seconds=defaults["backoff_seconds"],
            transport=transport,
        )
        self.base_url = provider_cfg["base_url"]
        self.everything_query = provider_cfg["everything_query"]
        self.top_headlines_query = provider_cfg["top_headlines_query"]
        self.page_size = provider_cfg["page_size"]
        self.max_pages = provider_cfg["max_pages"]
        self.language = provider_cfg["language"]
        self.sources_whitelist = provider_cfg["sources_whitelist"]

    def fetch_window(self, start_at: datetime, end_at: datetime) -> list[RawSignal]:
        api_key = os.getenv("NEWSAPI_API_KEY")
        if not api_key:
            return []
        headers = {"X-Api-Key": api_key}
        signals: list[RawSignal] = []
        for page in range(1, self.max_pages + 1):
            payload = self._request(
                "GET",
                f"{self.base_url}/everything",
                params={
                    "q": self.everything_query,
                    "from": start_at.isoformat(),
                    "to": end_at.isoformat(),
                    "language": self.language,
                    "pageSize": self.page_size,
                    "page": page,
                    "sortBy": "publishedAt",
                },
                headers=headers,
            )
            signals.extend(self.parse_everything_payload(payload, fetched_at=end_at))
            if len(payload.get("articles", [])) < self.page_size:
                break

        headlines = self._request(
            "GET",
            f"{self.base_url}/top-headlines",
            params={
                "q": self.top_headlines_query,
                "language": self.language,
                "pageSize": min(self.page_size, 25),
            },
            headers=headers,
        )
        signals.extend(self.parse_everything_payload(headlines, fetched_at=end_at, query_key="top-headlines"))
        return signals

    def parse_everything_payload(
        self, payload: dict, *, fetched_at: datetime, query_key: str = "everything"
    ) -> list[RawSignal]:
        records = []
        for article in payload.get("articles", []):
            source_url = article.get("url")
            title = article.get("title") or "Untitled article"
            summary = article.get("description") or article.get("content") or ""
            published_at = _iso_to_datetime(article.get("publishedAt")) or fetched_at
            body = _compact_text(title, summary)
            content_hash = _hash_text(body)
            dedupe_hash = _hash_text(f"{_domain(source_url)}::{title.lower().strip()}")
            records.append(
                RawSignal(
                    id=content_hash[:16],
                    provider_name=self.provider_name,
                    provider_item_id=source_url or content_hash[:16],
                    source=self.source_family,
                    timestamp=published_at,
                    fetched_at=fetched_at,
                    published_at=published_at,
                    signal_type="news",
                    title=title,
                    summary=summary,
                    source_url=source_url,
                    request_url=f"{self.base_url}/{query_key}",
                    query_key=query_key,
                    language=article.get("language") or self.language,
                    entities=[article.get("source", {}).get("name")] if article.get("source", {}).get("name") else [],
                    region="Global",
                    tags=_coerce_tags(
                        [
                            query_key,
                            article.get("source", {}).get("name", ""),
                            _domain(source_url) or "",
                        ]
                    ),
                    confidence=0.74,
                    provider_confidence=0.74,
                    content_hash=content_hash,
                    dedupe_hash=dedupe_hash,
                    raw_payload_reference=f"{self.provider_name}:{source_url or content_hash[:16]}",
                    payload=article,
                )
            )
        return records


class AlphaVantageProvider(HTTPProvider):
    provider_name = "alphavantage"
    source_family = "market"

    def __init__(self, *, transport: httpx.BaseTransport | None = None) -> None:
        config = load_provider_config()
        defaults = config["defaults"]
        provider_cfg = config["providers"]["alphavantage"]
        super().__init__(
            timeout_seconds=defaults["timeout_seconds"],
            retries=defaults["retries"],
            backoff_seconds=defaults["backoff_seconds"],
            transport=transport,
        )
        self.base_url = provider_cfg["base_url"]
        self.news_topics = provider_cfg["news_topics"]
        self.tickers = provider_cfg["tickers"]
        self.quote_symbols = provider_cfg["quote_symbols"]
        self.news_limit = provider_cfg["news_limit"]

    def fetch_window(self, start_at: datetime, end_at: datetime) -> list[RawSignal]:
        api_key = os.getenv("ALPHAVANTAGE_API_KEY")
        if not api_key:
            return []
        signals = []
        payload = self._request(
            "GET",
            self.base_url,
            params={
                "function": "NEWS_SENTIMENT",
                "apikey": api_key,
                "topics": self.news_topics,
                "tickers": self.tickers,
                "time_from": start_at.strftime("%Y%m%dT%H%M"),
                "time_to": end_at.strftime("%Y%m%dT%H%M"),
                "limit": self.news_limit,
                "sort": "LATEST",
            },
        )
        signals.extend(self.parse_news_payload(payload, fetched_at=end_at))
        for symbol in [item.strip() for item in self.quote_symbols.split(",") if item.strip()]:
            quote_payload = self._request(
                "GET",
                self.base_url,
                params={
                    "function": "GLOBAL_QUOTE",
                    "symbol": symbol,
                    "apikey": api_key,
                },
            )
            signals.extend(self.parse_quote_payload(quote_payload, symbol=symbol, fetched_at=end_at))
        return signals

    def parse_news_payload(self, payload: dict, *, fetched_at: datetime) -> list[RawSignal]:
        records = []
        for item in payload.get("feed", []):
            title = item.get("title") or "Untitled market item"
            summary = item.get("summary") or ""
            source_url = item.get("url")
            published_at = _iso_to_datetime(item.get("time_published")) or fetched_at
            body = _compact_text(title, summary)
            content_hash = _hash_text(body)
            dedupe_hash = _hash_text(f"alphavantage::{title.lower().strip()}")
            tags = _coerce_tags(
                [sentiment.get("topic", "") for sentiment in item.get("topics", [])]
                + [ticker.get("ticker", "") for ticker in item.get("ticker_sentiment", [])[:4]]
            )
            records.append(
                RawSignal(
                    id=content_hash[:16],
                    provider_name=self.provider_name,
                    provider_item_id=source_url or content_hash[:16],
                    source=self.source_family,
                    timestamp=published_at,
                    fetched_at=fetched_at,
                    published_at=published_at,
                    signal_type="market-news",
                    title=title,
                    summary=summary,
                    source_url=source_url,
                    request_url=self.base_url,
                    query_key="NEWS_SENTIMENT",
                    language="en",
                    entities=[item.get("source", "")] if item.get("source") else [],
                    region="Global",
                    tags=tags or ["market-news"],
                    confidence=0.76,
                    provider_confidence=0.76,
                    content_hash=content_hash,
                    dedupe_hash=dedupe_hash,
                    raw_payload_reference=f"{self.provider_name}:{source_url or content_hash[:16]}",
                    payload=item,
                )
            )
        return records

    def parse_quote_payload(self, payload: dict, *, symbol: str, fetched_at: datetime) -> list[RawSignal]:
        quote = payload.get("Global Quote", {})
        if not quote:
            return []
        title = f"{symbol} quote moved to {quote.get('05. price', 'unknown')}"
        summary = (
            f"Open {quote.get('02. open', 'n/a')}, high {quote.get('03. high', 'n/a')}, "
            f"low {quote.get('04. low', 'n/a')}, volume {quote.get('06. volume', 'n/a')}."
        )
        content_hash = _hash_text(_compact_text(title, summary))
        return [
            RawSignal(
                id=content_hash[:16],
                provider_name=self.provider_name,
                provider_item_id=symbol,
                source=self.source_family,
                timestamp=fetched_at,
                fetched_at=fetched_at,
                published_at=fetched_at,
                signal_type="market-quote",
                title=title,
                summary=summary,
                source_url=None,
                request_url=self.base_url,
                query_key=f"GLOBAL_QUOTE:{symbol}",
                language="en",
                entities=[symbol],
                region="Global",
                tags=_coerce_tags([symbol, "market-quote"]),
                confidence=0.8,
                provider_confidence=0.8,
                content_hash=content_hash,
                dedupe_hash=_hash_text(f"quote::{symbol}::{fetched_at.isoformat()}"),
                raw_payload_reference=f"{self.provider_name}:{symbol}:{fetched_at.isoformat()}",
                payload=quote,
            )
        ]


class FredProvider(HTTPProvider):
    provider_name = "fred"
    source_family = "macro"

    def __init__(self, *, transport: httpx.BaseTransport | None = None) -> None:
        config = load_provider_config()
        defaults = config["defaults"]
        provider_cfg = config["providers"]["fred"]
        super().__init__(
            timeout_seconds=defaults["timeout_seconds"],
            retries=defaults["retries"],
            backoff_seconds=defaults["backoff_seconds"],
            transport=transport,
        )
        self.base_url = provider_cfg["base_url"]
        self.series_ids = provider_cfg["series_ids"]
        self.updates_limit = provider_cfg["updates_limit"]

    def fetch_window(self, start_at: datetime, end_at: datetime) -> list[RawSignal]:
        api_key = os.getenv("FRED_API_KEY")
        if not api_key:
            return []
        signals = []
        updates = self._request(
            "GET",
            f"{self.base_url}/series/updates",
            params={
                "api_key": api_key,
                "file_type": "json",
                "realtime_start": start_at.date().isoformat(),
                "realtime_end": end_at.date().isoformat(),
                "limit": self.updates_limit,
            },
        )
        signals.extend(self.parse_updates_payload(updates, fetched_at=end_at))
        for series_id in self.series_ids:
            obs = self._request(
                "GET",
                f"{self.base_url}/series/observations",
                params={
                    "api_key": api_key,
                    "file_type": "json",
                    "series_id": series_id,
                    "observation_start": start_at.date().isoformat(),
                    "observation_end": end_at.date().isoformat(),
                    "sort_order": "desc",
                    "limit": 2,
                },
            )
            signals.extend(self.parse_observations_payload(obs, series_id=series_id, fetched_at=end_at))
        return signals

    def parse_updates_payload(self, payload: dict, *, fetched_at: datetime) -> list[RawSignal]:
        records = []
        for item in payload.get("seriess", []):
            title = f"FRED updated {item.get('id', 'unknown series')}"
            summary = item.get("title") or item.get("notes") or "Series update."
            content_hash = _hash_text(_compact_text(title, summary))
            records.append(
                RawSignal(
                    id=content_hash[:16],
                    provider_name=self.provider_name,
                    provider_item_id=item.get("id", content_hash[:16]),
                    source=self.source_family,
                    timestamp=fetched_at,
                    fetched_at=fetched_at,
                    published_at=fetched_at,
                    signal_type="macro-update",
                    title=title,
                    summary=summary,
                    source_url=None,
                    request_url=f"{self.base_url}/series/updates",
                    query_key="series_updates",
                    language="en",
                    entities=[item.get("id", "")],
                    region="US",
                    tags=_coerce_tags(
                        [
                            item.get("frequency", ""),
                            item.get("units", ""),
                            "fred-update",
                        ]
                    ),
                    confidence=0.82,
                    provider_confidence=0.82,
                    content_hash=content_hash,
                    dedupe_hash=_hash_text(f"fred-update::{item.get('id', '')}::{fetched_at.date().isoformat()}"),
                    raw_payload_reference=f"{self.provider_name}:{item.get('id', content_hash[:16])}",
                    payload=item,
                )
            )
        return records

    def parse_observations_payload(self, payload: dict, *, series_id: str, fetched_at: datetime) -> list[RawSignal]:
        observations = payload.get("observations", [])
        if not observations:
            return []
        latest = observations[0]
        previous = observations[1] if len(observations) > 1 else None
        title = f"FRED {series_id} latest observation is {latest.get('value', 'n/a')}"
        comparison = ""
        if previous:
            comparison = f" Previous value was {previous.get('value', 'n/a')}."
        summary = f"Date {latest.get('date', 'n/a')}.{comparison}"
        content_hash = _hash_text(_compact_text(title, summary))
        return [
            RawSignal(
                id=content_hash[:16],
                provider_name=self.provider_name,
                provider_item_id=series_id,
                source=self.source_family,
                timestamp=fetched_at,
                fetched_at=fetched_at,
                published_at=fetched_at,
                signal_type="macro-observation",
                title=title,
                summary=summary,
                source_url=None,
                request_url=f"{self.base_url}/series/observations",
                query_key=series_id,
                language="en",
                entities=[series_id],
                region="US",
                tags=_coerce_tags([series_id, "macro-observation"]),
                confidence=0.84,
                provider_confidence=0.84,
                content_hash=content_hash,
                dedupe_hash=_hash_text(f"fred-obs::{series_id}::{latest.get('date', '')}"),
                raw_payload_reference=f"{self.provider_name}:{series_id}:{latest.get('date', '')}",
                payload={"latest": latest, "previous": previous},
            )
        ]


class GDELTProvider(HTTPProvider):
    provider_name = "gdelt"
    source_family = "alt"

    def __init__(self, *, transport: httpx.BaseTransport | None = None) -> None:
        config = load_provider_config()
        defaults = config["defaults"]
        provider_cfg = config["providers"]["gdelt"]
        super().__init__(
            timeout_seconds=defaults["timeout_seconds"],
            retries=defaults["retries"],
            backoff_seconds=defaults["backoff_seconds"],
            transport=transport,
        )
        self.base_url = provider_cfg["base_url"]
        self.query = provider_cfg["query"]
        self.mode = provider_cfg["mode"]
        self.format = provider_cfg["format"]
        self.maxrecords = provider_cfg["maxrecords"]

    def fetch_window(self, start_at: datetime, end_at: datetime) -> list[RawSignal]:
        payload = self._request(
            "GET",
            self.base_url,
            params={
                "query": self.query,
                "mode": self.mode,
                "format": self.format,
                "maxrecords": self.maxrecords,
                "startdatetime": start_at.strftime("%Y%m%d%H%M%S"),
                "enddatetime": end_at.strftime("%Y%m%d%H%M%S"),
            },
        )
        return self.parse_doc_payload(payload, fetched_at=end_at)

    def parse_doc_payload(self, payload: dict, *, fetched_at: datetime) -> list[RawSignal]:
        records = []
        articles = payload.get("articles") or payload.get("data") or []
        for item in articles:
            title = item.get("title") or "Untitled GDELT event"
            summary = item.get("seendate") or item.get("domain") or ""
            source_url = item.get("url")
            published_at = _iso_to_datetime(item.get("seendate")) or fetched_at
            content_hash = _hash_text(_compact_text(title, summary))
            tags = _coerce_tags(
                [
                    item.get("domain", ""),
                    item.get("sourcecountry", ""),
                    item.get("language", ""),
                    "gdelt",
                ]
            )
            records.append(
                RawSignal(
                    id=content_hash[:16],
                    provider_name=self.provider_name,
                    provider_item_id=source_url or content_hash[:16],
                    source=self.source_family,
                    timestamp=published_at,
                    fetched_at=fetched_at,
                    published_at=published_at,
                    signal_type="alt-event",
                    title=title,
                    summary=summary,
                    source_url=source_url,
                    request_url=self.base_url,
                    query_key="gdelt-doc",
                    language=item.get("language"),
                    entities=[item.get("domain")] if item.get("domain") else [],
                    region=item.get("sourcecountry") or "Global",
                    tags=tags,
                    confidence=0.68,
                    provider_confidence=0.68,
                    content_hash=content_hash,
                    dedupe_hash=_hash_text(f"gdelt::{title.lower().strip()}::{_domain(source_url) or ''}"),
                    raw_payload_reference=f"{self.provider_name}:{source_url or content_hash[:16]}",
                    payload=item,
                )
            )
        return records


class WebSearchEnricher(HTTPProvider):
    """Cluster-driven enricher that uses OpenAI web_search_preview for live synthesis.

    Unlike the other providers this class is NOT registered in build_live_providers()
    and does NOT implement fetch_window(). It is called from enrich_dark_signals()
    after clustering, with one targeted question derived per EventCluster.

    Reuses OPENAI_API_KEY — no additional account or credits needed beyond the LLM
    refinement nodes that already use the same key.
    """

    provider_name = "openai-websearch"
    source_family = "synthesis"
    base_url = "https://api.openai.com/v1/responses"

    def __init__(self, *, transport: httpx.BaseTransport | None = None) -> None:
        config = load_provider_config()
        defaults = config["defaults"]
        provider_cfg = config["providers"]["web_search"]
        super().__init__(
            timeout_seconds=defaults["timeout_seconds"],
            retries=defaults["retries"],
            backoff_seconds=defaults["backoff_seconds"],
            transport=transport,
        )
        self.model = provider_cfg["model"]
        self.max_tokens = provider_cfg["max_tokens"]
        self.min_cluster_signals = provider_cfg["min_cluster_signals"]
        self.max_queries_per_run = provider_cfg["max_queries_per_run"]

    @property
    def enabled(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY"))

    def fetch_window(self, start_at: datetime, end_at: datetime) -> list[RawSignal]:  # pragma: no cover
        # Required by ABC but unused — this enricher is called via query(), not fetch_window()
        return []

    def build_query(
        self,
        story_key: str,
        entities: list[str],
        region: str,
        scenario_name: str | None = None,
        consequence_hint: list[str] | None = None,
    ) -> str:
        """Derive a targeted fragility question from cluster metadata, optionally framed by a detected scenario."""
        topic = story_key.replace("_", " ")
        named = [e for e in entities if e and len(e) > 2][:4]
        actor_clause = f" Key actors or entities involved: {', '.join(named)}." if named else ""
        if scenario_name and consequence_hint:
            context = (
                f"In the context of the scenario '{scenario_name}', particularly regarding "
                f"{consequence_hint[0]}" + (f" and {consequence_hint[1]}" if len(consequence_hint) > 1 else "") + ", "
            )
        else:
            context = ""
        return (
            f"{context}What are the latest confirmed developments regarding {topic} in {region}?"
            f"{actor_clause}"
            " Focus on: which systems or infrastructure are most affected,"
            " which actors bear the greatest structural cost,"
            " and what second-order fragilities or indirect effects are emerging."
            " Cite specific recent events where possible."
        )

    def query(self, question: str, *, story_key: str, fetched_at: datetime) -> list[RawSignal]:
        """Send one question via OpenAI web_search_preview and return signals per citation."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return []
        payload = self._request(
            "POST",
            self.base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json_body={
                "model": self.model,
                "max_output_tokens": self.max_tokens,
                "tools": [{"type": "web_search_preview"}],
                "input": [
                    {
                        "role": "system",
                        "content": (
                            "You are a geopolitical and structural fragility analyst. "
                            "Provide factual, citation-backed answers focused on systemic risks, "
                            "asymmetric pressure points, and second-order effects."
                        ),
                    },
                    {"role": "user", "content": question},
                ],
            },
        )
        return self.parse_search_response(payload, story_key=story_key, fetched_at=fetched_at)

    def parse_search_response(
        self,
        payload: dict,
        *,
        story_key: str,
        fetched_at: datetime,
    ) -> list[RawSignal]:
        """Parse an OpenAI Responses API web_search_preview response.

        The response output list contains items of type "web_search_call" (the search
        step) and "message" (the answer). The message content block of type "output_text"
        carries the synthesized answer in .text and citation URLs in .annotations
        (each annotation has type "url_citation" with .url and .title fields).
        """
        answer = ""
        citations: list[dict] = []  # [{url, title}]

        for item in payload.get("output") or []:
            if item.get("type") != "message":
                continue
            for block in item.get("content") or []:
                if block.get("type") != "output_text":
                    continue
                answer = block.get("text") or ""
                for ann in block.get("annotations") or []:
                    if ann.get("type") == "url_citation" and ann.get("url"):
                        citations.append({"url": ann["url"], "title": ann.get("title") or ""})

        if not answer:
            return []

        if not citations:
            # No citations: emit a single signal for the synthesis text itself
            content_hash = _hash_text(_compact_text(story_key, answer))
            return [
                RawSignal(
                    id=content_hash[:16],
                    provider_name=self.provider_name,
                    provider_item_id=content_hash[:16],
                    source=self.source_family,
                    timestamp=fetched_at,
                    fetched_at=fetched_at,
                    published_at=fetched_at,
                    signal_type="news-synthesis",
                    title=f"Web synthesis: {story_key.replace('_', ' ')}",
                    summary=answer,
                    source_url=None,
                    request_url=self.base_url,
                    query_key=story_key,
                    language="en",
                    entities=[],
                    region="Global",
                    tags=_coerce_tags([story_key, "openai-websearch", "synthesis"]),
                    confidence=0.82,
                    provider_confidence=0.82,
                    content_hash=content_hash,
                    dedupe_hash=_hash_text(f"openai-websearch::{story_key}::{fetched_at.date().isoformat()}"),
                    raw_payload_reference=f"{self.provider_name}:{content_hash[:16]}",
                    payload=payload,
                )
            ]

        records: list[RawSignal] = []
        for citation in citations:
            url = citation["url"]
            title = citation["title"] or f"Web synthesis: {story_key.replace('_', ' ')}"
            content_hash = _hash_text(_compact_text(story_key, url, answer[:200]))
            dedupe_hash = _hash_text(f"openai-websearch::{_domain(url) or url}::{story_key}")
            records.append(
                RawSignal(
                    id=content_hash[:16],
                    provider_name=self.provider_name,
                    provider_item_id=url,
                    source=self.source_family,
                    timestamp=fetched_at,
                    fetched_at=fetched_at,
                    published_at=fetched_at,
                    signal_type="news-synthesis",
                    title=title,
                    summary=answer,
                    source_url=url,
                    request_url=self.base_url,
                    query_key=story_key,
                    language="en",
                    entities=[_domain(url)] if _domain(url) else [],
                    region="Global",
                    tags=_coerce_tags([story_key, "openai-websearch", "synthesis", _domain(url) or ""]),
                    confidence=0.82,
                    provider_confidence=0.82,
                    content_hash=content_hash,
                    dedupe_hash=dedupe_hash,
                    raw_payload_reference=f"{self.provider_name}:{url}",
                    payload={
                        "answer": answer,
                        "citation_url": url,
                        "citation_title": title,
                        "all_citations": citations,
                    },
                )
            )
        return records
