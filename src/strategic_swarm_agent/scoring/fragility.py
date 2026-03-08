from __future__ import annotations

from strategic_swarm_agent.models import AbstractPattern, FragilityAssessment, ScoreDetail, SignalBundle, SignalEvent
from strategic_swarm_agent.utils.config import load_archetypes, load_scoring_config

HIGH_DEFENSE_TAGS = {"chokepoint", "grid", "debt", "undersea", "compliance", "carrier", "cloud"}
LOW_COST_DISRUPTOR_TAGS = {"bypass", "open-source", "protocol", "microgrid", "stablecoin", "sabotage"}
ANTIFRAGILE_TAGS = {"microgrid", "open-source", "protocol", "resilience", "bypass", "monitoring", "settlement"}


class FragilityScorer:
    def __init__(self) -> None:
        self.scoring = load_scoring_config()
        self.archetypes = load_archetypes()

    def score(
        self,
        events: list[SignalEvent],
        patterns: list[AbstractPattern],
        bundles: list[SignalBundle],
    ) -> list[FragilityAssessment]:
        if not events or not patterns:
            return []

        tags = {tag for event in events for tag in event.tags}
        bundle = bundles[0] if bundles else None

        hubris_value = self._bounded(
            0.25
            + 0.12 * len(tags.intersection({"incumbent", "deterrence", "compliance", "repair-delay", "defensive-doctrine"}))
            + 0.08 * len(tags.intersection({"debt", "refinancing", "pricing-power"}))
        )
        energy_defense_value = self._bounded(
            0.28
            + 0.11 * len(tags.intersection(HIGH_DEFENSE_TAGS))
            + 0.08 * len(tags.intersection(LOW_COST_DISRUPTOR_TAGS))
        )
        kinetic_ripple_value = self._bounded(
            0.24
            + 0.13 * len(tags.intersection({"market-stress", "funding-stress", "shipping", "insurance", "cloud-spend"}))
            + 0.08 * len(tags.intersection({"undersea", "grid", "payment-rail", "developer-flight"}))
        )
        centralization_value = self._bounded(
            0.3 + 0.1 * len(tags.intersection({"chokepoint", "central-hub", "grid", "incumbent", "treasury", "carrier"}))
        )
        redundancy_value = self._bounded(
            0.18
            + 0.12 * len(tags.intersection({"bypass", "microgrid", "open-source", "redundancy", "protocol"}))
        )
        antifragility_value = self._bounded(
            0.25 + 0.1 * len(tags.intersection(ANTIFRAGILE_TAGS)) + (bundle.sentiment_entropy.value * 0.12 if bundle else 0.0)
        )
        weights = self.scoring["weights"]
        fragility_value = self._bounded(
            hubris_value * weights["hubris_index"]
            + energy_defense_value * weights["energy_defense_ratio"]
            + kinetic_ripple_value * weights["kinetic_ripple"]
            + centralization_value * weights["centralization_score"]
            + (1 - redundancy_value) * weights["redundancy_penalty"]
            + antifragility_value * weights["antifragility_attraction"]
        )

        fragility_patterns = [
            pattern.name
            for pattern in self.archetypes["fragility_patterns"]
            if tags.intersection(set(pattern.trigger_tags))
        ]
        fragile_nodes = self._fragile_nodes(tags)
        antifragile_nodes = self._antifragile_nodes(tags)

        return [
            FragilityAssessment(
                hubris_index=ScoreDetail(
                    value=hubris_value,
                    explanation="Higher when incumbents lean on legacy assumptions, slow doctrine, or financing confidence.",
                ),
                energy_defense_ratio=ScoreDetail(
                    value=energy_defense_value,
                    explanation="Higher when defending the system is materially more expensive than disrupting it.",
                ),
                kinetic_ripple=ScoreDetail(
                    value=kinetic_ripple_value,
                    explanation="Higher when a local shock can spill into funding, logistics, or confidence channels.",
                ),
                centralization_score=ScoreDetail(
                    value=centralization_value,
                    explanation="Higher when control, routing, or balance-sheet risk is concentrated in a few nodes.",
                ),
                redundancy_score=ScoreDetail(
                    value=redundancy_value,
                    explanation="Higher when the system still has substitutes and alternate paths. Lower values imply brittleness.",
                ),
                fragility_score=ScoreDetail(
                    value=fragility_value,
                    explanation="Composite score combining hubris, defense burden, ripple risk, centralization, and available substitutes.",
                ),
                antifragility_attraction=ScoreDetail(
                    value=antifragility_value,
                    explanation="Higher when disorder increases demand for decentralized, modular, or resilience-linked systems.",
                ),
                notes=[
                    f"Detected fragility patterns: {', '.join(fragility_patterns[:4]) or 'none explicit'}.",
                    f"Pattern driver: {patterns[0].pattern_name}.",
                ],
                fragile_nodes=fragile_nodes,
                antifragile_nodes=antifragile_nodes,
            )
        ]

    def _fragile_nodes(self, tags: set[str]) -> list[str]:
        nodes = []
        if {"undersea", "cable", "chokepoint"}.intersection(tags):
            nodes.extend(["incumbent corridor operators", "marine repair chains"])
        if {"debt", "refinancing", "treasury"}.intersection(tags):
            nodes.extend(["levered sovereign proxies", "balance-sheet-heavy lenders"])
        if {"open-source", "margin-pressure", "cloud-spend"}.intersection(tags):
            nodes.extend(["bundled SaaS incumbents", "premium closed model wrappers"])
        if {"grid", "substation", "outage"}.intersection(tags):
            nodes.extend(["central utility infrastructure", "single-node substations"])
        return nodes or ["fragile centralized assets"]

    def _antifragile_nodes(self, tags: set[str]) -> list[str]:
        nodes = []
        if {"undersea", "bypass", "monitoring"}.intersection(tags):
            nodes.extend(["alternate route infrastructure", "network resilience software"])
        if {"open-source", "protocol", "developer-flight"}.intersection(tags):
            nodes.extend(["developer infrastructure", "interoperability tooling"])
        if {"stablecoin", "payment-rail", "settlement"}.intersection(tags):
            nodes.extend(["settlement infrastructure", "collateral software"])
        if {"microgrid", "storage", "grid"}.intersection(tags):
            nodes.extend(["distributed energy systems", "grid orchestration software"])
        return nodes or ["resilience tooling", "modular networks"]

    def _bounded(self, value: float) -> float:
        return max(0.0, min(1.0, value))
