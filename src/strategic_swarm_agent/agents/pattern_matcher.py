from __future__ import annotations

from collections import Counter

from strategic_swarm_agent.llm.backend import StructuredReasoner
from strategic_swarm_agent.models import AbstractPattern, EventCluster, HistoricalAnalog, SignalEvent
from strategic_swarm_agent.utils.config import load_archetypes, load_prompts

EMPIRE_KEYWORDS = {
    "consortium",
    "alliance",
    "grid",
    "utility",
    "treasury",
    "ministry",
    "bank",
    "incumbent",
    "cloud",
    "carrier",
}
DISRUPTOR_KEYWORDS = {
    "mesh",
    "builders",
    "protocol",
    "collective",
    "open",
    "startup",
    "network",
    "coop",
    "stablecoin",
    "microgrid",
}


class PatternMatcher:
    def __init__(self, reasoner: StructuredReasoner | None = None) -> None:
        self.archetypes = load_archetypes()
        self.prompts = load_prompts()
        self.reasoner = reasoner or StructuredReasoner()

    def match(self, events: list[SignalEvent], cluster: EventCluster | None = None) -> tuple[list[AbstractPattern], dict]:
        if not events:
            return [], {"llm_used": False, "llm_status": "empty"}
        if cluster is None:
            cluster = EventCluster(
                cluster_id=events[0].cluster_id,
                story_key=events[0].story_key,
                canonical_title=events[0].title,
                summary=events[0].summary,
                region=events[0].region,
                language=events[0].language,
                entities=events[0].entities,
                tags=events[0].tags,
                source_families=events[0].source_families or [events[0].source],
                signal_ids=[event.id for event in events],
                first_seen_at=min(event.timestamp for event in events),
                last_seen_at=max(event.timestamp for event in events),
                novelty_score=max(event.novelty for event in events),
                agreement_score=min(1.0, 0.2 + len({event.source for event in events}) * 0.25),
                cluster_strength=min(1.0, 0.3 + len(events) * 0.1),
            )

        tag_pool = {tag for event in events for tag in event.tags}
        text_pool = " ".join(
            " ".join([event.title, event.summary, *event.entities]).lower() for event in events
        )
        scored = []
        for archetype in self.archetypes["topologies"]:
            overlap = len(tag_pool.intersection(set(archetype.trigger_tags)))
            keyword_bonus = sum(1 for token in archetype.name.lower().split() if token in text_pool)
            score = overlap + keyword_bonus * 0.35
            scored.append((score, archetype))

        _, best = max(scored, key=lambda item: item[0])
        analogs = [self.archetypes["historical_analogs"][ref] for ref in best.analog_refs]

        empire_actor = self._select_actor(events, EMPIRE_KEYWORDS)
        disruptor_actor = self._select_actor(events, DISRUPTOR_KEYWORDS, fallback_avoid=empire_actor)
        cheap_weapon = self._infer_cheap_weapon(best.name, tag_pool)
        armor_breach = self._infer_armor_breach(best.name, tag_pool)

        explanation = (
            f"The event cluster matches {best.name} because the tag set shows "
            f"{', '.join(sorted(tag_pool.intersection(set(best.trigger_tags)))[:4]) or 'structural pressure'} "
            f"and the incumbent must defend a wider surface area than the disruptor."
        )
        confidence = min(0.95, 0.42 + len(tag_pool.intersection(set(best.trigger_tags))) * 0.08)

        fallback = AbstractPattern(
            pattern_name=best.name,
            empire_type=best.empire_type,
            disruptor_type=best.disruptor_type,
            asymmetry_type=best.asymmetry_type,
            empire_actor=empire_actor,
            disruptor_actor=disruptor_actor,
            cheap_weapon=cheap_weapon,
            armor_breach=armor_breach,
            historical_analogs=[
                HistoricalAnalog(
                    name=analog.name,
                    reference=analog.reference,
                    why_relevant=analog.why_relevant,
                )
                for analog in analogs
            ],
            explanation=explanation,
            confidence=confidence,
        )
        refined, llm_diag = self.reasoner.refine_model(
            system_prompt=self.prompts["pattern_matcher"],
            user_payload={
                "cluster": cluster.model_dump(mode="json"),
                "events": [event.model_dump(mode="json") for event in events],
                "fallback": fallback.model_dump(mode="json"),
            },
            model_class=AbstractPattern,
            fallback=fallback,
        )
        return [refined], llm_diag

    def _select_actor(
        self,
        events: list[SignalEvent],
        keywords: set[str],
        fallback_avoid: str | None = None,
    ) -> str:
        counts = Counter(entity for event in events for entity in event.entities)
        ranked = counts.most_common()
        for entity, _ in ranked:
            tokens = set(entity.lower().replace("-", " ").split())
            if keywords.intersection(tokens) and entity != fallback_avoid:
                return entity
        for entity, _ in ranked:
            if entity != fallback_avoid:
                return entity
        return "Unknown actor"

    def _infer_cheap_weapon(self, pattern_name: str, tags: set[str]) -> str:
        if "Chokepoint vs Bypass" in pattern_name:
            return "Rerouting connectivity away from the defended corridor."
        if "Monolith vs Protocol" in pattern_name:
            return "Open modular releases that collapse the incumbent pricing umbrella."
        if "Heavy Capital vs Light Network" in pattern_name:
            return "Low-cost software rails that bypass capital-intensive balance-sheet defense."
        if "Central Grid vs Micro-Network" in pattern_name:
            return "Distributed resilience assets that neutralize dependence on a central node."
        if "sabotage" in tags or "drone" in tags:
            return "Cheap repeated probes against a costly defensive perimeter."
        return "Adaptive low-cost pressure against a rigid defensive system."

    def _infer_armor_breach(self, pattern_name: str, tags: set[str]) -> str:
        if "Chokepoint vs Bypass" in pattern_name:
            return "The incumbent route loses pricing and strategic leverage once rerouting becomes credible."
        if "Monolith vs Protocol" in pattern_name:
            return "Developer adoption can move faster than enterprise repricing and roadmap defense."
        if "Heavy Capital vs Light Network" in pattern_name:
            return "Funding costs compound while users migrate to cheaper modular rails."
        if "Central Grid vs Micro-Network" in pattern_name:
            return "Local resilience demand rises after each central outage and weakens the utility monopoly."
        if "debt" in tags:
            return "Debt service turns defense into a reflexive stress amplifier."
        return "The dominant system cannot cheaply defend every exposed node."
