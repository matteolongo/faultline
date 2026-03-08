from __future__ import annotations

from strategic_swarm_agent.models import ScoreDetail, SignalBundle, SignalEvent


class SignalAlchemist:
    def enrich(self, events: list[SignalEvent], scenario_id: str) -> list[SignalBundle]:
        if not events:
            return []

        dark_events = [event for event in events if event.source == "dark"]
        market_events = [event for event in events if event.source == "market"]

        anomaly_tags = sorted({tag for event in dark_events for tag in event.tags})[:8]
        pressure_indicators = []
        for event in market_events + dark_events:
            pressure_indicators.append(f"{event.title}: {event.summary}")

        distinct_dark_tags = len({tag for event in dark_events for tag in event.tags})
        dark_ratio = len(dark_events) / max(len(events), 1)
        sentiment_entropy_value = min(1.0, 0.2 + distinct_dark_tags / 8 + dark_ratio / 3)

        response_penalty = sum(
            0.12
            for event in market_events
            if {"spread-widening", "funding-stress", "repair-delay", "capital-flight"}.intersection(event.tags)
        )
        response_capacity_value = max(0.0, 0.85 - response_penalty)

        uncertainty_notes = []
        if len(dark_events) < 2:
            uncertainty_notes.append("Dark-signal coverage is shallow, so sentiment entropy is probably understated.")
        if not market_events:
            uncertainty_notes.append("No explicit market stress signal was provided; response capacity is inferred indirectly.")

        return [
            SignalBundle(
                bundle_id=f"{scenario_id}-bundle-1",
                anomaly_tags=anomaly_tags,
                pressure_indicators=pressure_indicators[:6],
                sentiment_entropy=ScoreDetail(
                    value=sentiment_entropy_value,
                    explanation="Higher when weak signals are fragmented, unusual, and cluster around distrust or rerouting.",
                ),
                response_capacity=ScoreDetail(
                    value=response_capacity_value,
                    explanation="Lower when financing, repair, or policy response appears constrained.",
                ),
                supporting_signal_ids=[event.id for event in dark_events + market_events],
                uncertainty_notes=uncertainty_notes,
            )
        ]
