from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict

from faultline.models import EventCluster, RawSignal, SignalEvent
from faultline.utils.config import load_provider_config

SYSTEMIC_TAGS = {
    "chokepoint",
    "bypass",
    "grid",
    "debt",
    "stablecoin",
    "undersea",
    "open-source",
    "protocol",
    "refinancing",
    "microgrid",
}
STOP_WORDS = {
    "the",
    "and",
    "or",
    "for",
    "with",
    "from",
    "into",
    "after",
    "amid",
    "near",
    "over",
    "under",
    "latest",
    "new",
    "report",
    "reports",
}
REGION_KEYWORDS = {
    "US": {"fed", "treasury", "washington", "america", "us"},
    "Europe": {"baltic", "europe", "eu", "arctic"},
    "Asia": {"china", "taiwan", "japan", "india"},
    "Global": {"global", "world"},
}
ONTOLOGY_TAGS = {
    "undersea": {"undersea", "subsea", "cable"},
    "chokepoint": {"chokepoint", "corridor", "route"},
    "bypass": {"bypass", "rerouting", "alternate-route", "mesh"},
    "microgrid": {"microgrid", "distributed-energy", "storage"},
    "open-source": {"open-source", "open-weight", "fork", "open"},
    "protocol": {"protocol", "interoperability", "portable"},
    "stablecoin": {"stablecoin", "settlement", "payment-rail"},
    "debt": {"debt", "refinancing", "spread-widening", "yield"},
}


class SignalNormalizer:
    def __init__(self) -> None:
        provider_config = load_provider_config()
        self.source_weights = provider_config["source_weights"]

    def normalize(
        self,
        raw_signals: list[RawSignal],
        *,
        known_dedupe_hashes: set[str] | None = None,
        prior_story_counts: dict[str, int] | None = None,
    ) -> tuple[list[SignalEvent], list[EventCluster], dict[str, int]]:
        normalized: list[SignalEvent] = []
        known_dedupe_hashes = known_dedupe_hashes or set()
        prior_story_counts = prior_story_counts or {}
        batch_seen: set[str] = set()
        clusters: dict[str, list[RawSignal]] = defaultdict(list)
        duplicates_removed = 0

        for signal in sorted(raw_signals, key=lambda item: item.timestamp):
            if signal.dedupe_hash in known_dedupe_hashes or signal.dedupe_hash in batch_seen:
                duplicates_removed += 1
                continue
            batch_seen.add(signal.dedupe_hash or signal.id)
            story_key = self._story_key(signal)
            clusters[story_key].append(signal)

        cluster_models: list[EventCluster] = []
        for story_key, signals in clusters.items():
            cluster_id = hashlib.sha256(story_key.encode("utf-8")).hexdigest()[:16]
            source_families = sorted({signal.source for signal in signals})
            canonical = max(signals, key=lambda item: len(item.summary) + len(item.title))
            entities = self._merge_entities(signals)
            tags = self._merge_tags(signals)
            agreement_score = min(
                1.0,
                0.18 + len(source_families) * 0.22 + len({signal.provider_name for signal in signals}) * 0.1,
            )
            novelty_score = max(0.0, min(1.0, 0.9 - prior_story_counts.get(story_key, 0) * 0.12))
            cluster_strength = min(
                1.0,
                0.2 + agreement_score * 0.45 + novelty_score * 0.2 + min(len(signals), 5) * 0.06,
            )
            cluster_models.append(
                EventCluster(
                    cluster_id=cluster_id,
                    story_key=story_key,
                    canonical_title=canonical.title,
                    summary=canonical.summary,
                    region=self._region_for(signals),
                    language=canonical.language,
                    entities=entities,
                    tags=tags,
                    source_families=source_families,
                    signal_ids=[signal.id for signal in signals],
                    first_seen_at=min(signal.timestamp for signal in signals),
                    last_seen_at=max(signal.timestamp for signal in signals),
                    novelty_score=novelty_score,
                    agreement_score=agreement_score,
                    cluster_strength=cluster_strength,
                )
            )
            for signal in signals:
                systemic_overlap = len(SYSTEMIC_TAGS.intersection(set(tags)))
                source_weight = self.source_weights.get(signal.source, 0.8)
                normalized.append(
                    SignalEvent(
                        id=signal.id,
                        provider_name=signal.provider_name or signal.source,
                        source=signal.source,
                        timestamp=signal.timestamp,
                        fetched_at=signal.fetched_at or signal.timestamp,
                        published_at=signal.published_at,
                        signal_type=signal.signal_type,
                        title=signal.title,
                        summary=signal.summary,
                        source_url=signal.source_url,
                        language=signal.language or "en",
                        entities=self._entities_for(signal),
                        region=self._region_for([signal]),
                        tags=self._merge_tags([signal]),
                        confidence=min(1.0, signal.confidence * source_weight),
                        provider_confidence=signal.provider_confidence or signal.confidence,
                        novelty=novelty_score,
                        possible_systemic_relevance=min(1.0, 0.18 + systemic_overlap / 4 + agreement_score * 0.25),
                        cluster_id=cluster_id,
                        story_key=story_key,
                        dedupe_hash=signal.dedupe_hash or signal.id,
                        source_families=source_families,
                        query_key=signal.query_key,
                        raw_payload_reference=signal.raw_payload_reference
                        or f"{signal.provider_name}:{signal.provider_item_id}",
                    )
                )

        diagnostics = {
            "duplicates_removed": duplicates_removed,
            "cluster_count": len(cluster_models),
            "retained_signal_count": len(normalized),
        }
        return (
            normalized,
            sorted(cluster_models, key=lambda item: item.cluster_strength, reverse=True),
            diagnostics,
        )

    def _story_key(self, signal: RawSignal) -> str:
        tokens = re.findall(r"[a-z0-9]+", f"{signal.title} {signal.summary}".lower())
        filtered = [token for token in tokens if token not in STOP_WORDS and len(token) > 2]
        ontology = []
        raw_candidates = set(signal.tags).union(set(filtered))
        for canonical, aliases in ONTOLOGY_TAGS.items():
            if aliases.intersection(raw_candidates) or canonical in raw_candidates:
                ontology.append(canonical)
        head = "-".join(sorted(ontology[:4]) or sorted(filtered[:4]) or [signal.source])
        return f"{self._region_for([signal]).lower()}::{head}"

    def _entities_for(self, signal: RawSignal) -> list[str]:
        return signal.entities or self._extract_entities(signal.title, signal.summary)

    def _merge_entities(self, signals: list[RawSignal]) -> list[str]:
        counter = Counter(entity for signal in signals for entity in self._entities_for(signal))
        return [entity for entity, _ in counter.most_common(6)]

    def _merge_tags(self, signals: list[RawSignal]) -> list[str]:
        tags = []
        for signal in signals:
            candidates = set(signal.tags)
            text_tokens = set(re.findall(r"[a-z0-9-]+", f"{signal.title} {signal.summary}".lower()))
            for canonical, aliases in ONTOLOGY_TAGS.items():
                if aliases.intersection(text_tokens.union(candidates)):
                    candidates.add(canonical)
            for tag in sorted(candidates):
                if tag and tag not in tags:
                    tags.append(tag)
        return tags

    def _region_for(self, signals: list[RawSignal]) -> str:
        explicit = [signal.region for signal in signals if signal.region and signal.region != "Global"]
        if explicit:
            return Counter(explicit).most_common(1)[0][0]
        text = " ".join(f"{signal.title} {signal.summary}".lower() for signal in signals)
        for region, keywords in REGION_KEYWORDS.items():
            if keywords.intersection(set(re.findall(r"[a-z0-9]+", text))):
                return region
        return "Global"

    def _extract_entities(self, title: str, summary: str) -> list[str]:
        candidates = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b", f"{title} {summary}")
        entities = []
        for candidate in candidates:
            if candidate not in entities:
                entities.append(candidate)
        return entities[:6]
