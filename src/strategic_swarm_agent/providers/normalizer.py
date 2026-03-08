from __future__ import annotations

from strategic_swarm_agent.models import RawSignal, SignalEvent

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


class SignalNormalizer:
    def normalize(self, raw_signals: list[RawSignal]) -> list[SignalEvent]:
        normalized = []
        for signal in sorted(raw_signals, key=lambda item: item.timestamp):
            tag_count = len(set(signal.tags))
            novelty = min(1.0, 0.25 + tag_count / 10)
            systemic_overlap = len(SYSTEMIC_TAGS.intersection(set(signal.tags)))
            systemic_relevance = min(1.0, 0.2 + systemic_overlap / 4)
            normalized.append(
                SignalEvent(
                    id=signal.id,
                    source=signal.source,
                    timestamp=signal.timestamp,
                    signal_type=signal.signal_type,
                    title=signal.title,
                    summary=signal.summary,
                    entities=signal.entities,
                    region=signal.region,
                    tags=signal.tags,
                    confidence=signal.confidence,
                    novelty=novelty,
                    possible_systemic_relevance=systemic_relevance,
                    raw_payload_reference=f"{signal.source}:{signal.id}",
                )
            )
        return normalized
