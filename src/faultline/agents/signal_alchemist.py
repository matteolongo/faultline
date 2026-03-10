from __future__ import annotations

from faultline.llm.backend import StructuredReasoner
from faultline.models import (
    EventCluster,
    ScoreDetail,
    SignalBundle,
    SignalEvent,
)
from faultline.utils.config import load_prompts


class SignalAlchemist:
    """Converts structural patterns and event clusters into quantified signal bundles.

    Takes the Empire–Disruptor topology output from PatternMatcher and translates
    abstract structural observations into measurable signal vectors: direction, magnitude,
    confidence, and relevant financial instruments. Optionally refines signal extraction
    via LLM when an OpenAI key is available.
    """

    def __init__(self, reasoner: StructuredReasoner | None = None) -> None:
        self.reasoner = reasoner or StructuredReasoner()
        self.prompts = load_prompts()

    def enrich(self, events: list[SignalEvent], cluster: EventCluster) -> tuple[list[SignalBundle], dict]:
        if not events:
            return [], {"llm_used": False, "llm_status": "empty"}

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
            if {
                "spread-widening",
                "funding-stress",
                "repair-delay",
                "capital-flight",
            }.intersection(event.tags)
        )
        response_capacity_value = max(0.0, 0.85 - response_penalty)

        uncertainty_notes = []
        if len(dark_events) < 2:
            uncertainty_notes.append("Dark-signal coverage is shallow, so sentiment entropy is probably understated.")
        if not market_events:
            uncertainty_notes.append(
                "No explicit market stress signal was provided; response capacity is inferred indirectly."
            )

        fallback = SignalBundle(
            bundle_id=f"{cluster.cluster_id}-bundle-1",
            cluster_id=cluster.cluster_id,
            source_families=cluster.source_families,
            agreement_score=cluster.agreement_score,
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
        refined, llm_diag = self.reasoner.refine_model(
            system_prompt=self.prompts["signal_alchemist"],
            user_payload={
                "cluster": cluster.model_dump(mode="json"),
                "events": [event.model_dump(mode="json") for event in events],
                "fallback": fallback.model_dump(mode="json"),
            },
            model_class=SignalBundle,
            fallback=fallback,
        )
        return [refined], llm_diag
