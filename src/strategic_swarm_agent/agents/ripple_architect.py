from __future__ import annotations

from strategic_swarm_agent.llm.backend import StructuredReasoner
from strategic_swarm_agent.models import AbstractPattern, EventCluster, FragilityAssessment, RippleScenario, SignalBundle, SignalEvent
from strategic_swarm_agent.utils.config import load_prompts


class RippleArchitect:
    def __init__(self, reasoner: StructuredReasoner | None = None) -> None:
        self.reasoner = reasoner or StructuredReasoner()
        self.prompts = load_prompts()

    def build(
        self,
        events: list[SignalEvent],
        cluster: EventCluster,
        patterns: list[AbstractPattern],
        fragility: list[FragilityAssessment],
        bundles: list[SignalBundle],
    ) -> tuple[list[RippleScenario], dict]:
        if not events or not patterns or not fragility:
            return [], {"llm_used": False, "llm_status": "empty"}

        pattern = patterns[0]
        assessment = fragility[0]
        bundle = bundles[0] if bundles else None
        trigger = max(events, key=lambda event: event.possible_systemic_relevance).title

        if pattern.pattern_name == "Chokepoint vs Bypass":
            first_order = [
                "Insurance, routing, and repair costs rise on the incumbent corridor.",
                "Governments and carriers accelerate alternate route funding.",
            ]
            second_order = [
                "Network traffic and strategic attention migrate toward bypass infrastructure.",
                "Pricing power of the dominant corridor weakens before the physical asset base fully depreciates.",
            ]
            third_order = [
                "Capital rotates toward resilience, monitoring, and redundant network operators.",
                "Defense spending becomes less important than route optionality and survivability software.",
            ]
            helped = ["network resilience", "monitoring software", "alternate route infrastructure"]
            hurt = ["incumbent corridor operators", "repair-dependent cable assets", "route-concentrated logistics"]
        elif pattern.pattern_name == "Monolith vs Protocol":
            first_order = [
                "Developer experimentation shifts toward open components and lower switching-cost stacks.",
                "Incumbent pricing power weakens faster than enterprise contracts reprice.",
            ]
            second_order = [
                "Budgets migrate from full-stack vendors to orchestration, optimization, and integration layers.",
                "Compute and tooling demand fragments across more providers and open ecosystems.",
            ]
            third_order = [
                "The market rewards picks-and-shovels exposure rather than the obvious direct product challenger.",
                "Open commodity pressure compresses margins but expands the surrounding ecosystem.",
            ]
            helped = ["developer infrastructure", "model optimization", "interoperability tooling"]
            hurt = ["bundled SaaS incumbents", "closed premium model layers", "high-margin AI wrappers"]
        elif pattern.pattern_name == "Heavy Capital vs Light Network":
            first_order = [
                "Funding spreads increase the cost of defending the incumbent balance sheet.",
                "Users search for payment and collateral rails with less policy and refinancing drag.",
            ]
            second_order = [
                "Liquidity preference shifts toward shorter-duration, collateral-rich, and modular rails.",
                "Policy defense crowds out productive capital deployment and deepens confidence erosion.",
            ]
            third_order = [
                "Capital rotates toward neutral rails, settlement infrastructure, and balance-sheet-light enablers.",
                "The visible debt problem becomes a distribution and trust problem across the financial stack.",
            ]
            helped = ["settlement infrastructure", "collateral software", "risk transfer platforms"]
            hurt = ["levered sovereign proxies", "balance-sheet-heavy lenders", "policy-dependent intermediaries"]
        else:
            first_order = [
                "The dominant system absorbs immediate repair, defense, or compliance costs.",
                "The disruptor validates a cheaper method of pressuring a larger surface area.",
            ]
            second_order = [
                "Users and capital explore alternatives that reduce dependence on the fragile core.",
                "The incumbent spends more just to preserve a shrinking perception of control.",
            ]
            third_order = [
                "Peripheral suppliers and resilience enablers benefit from persistent uncertainty.",
                "Narrative control weakens as practical bypass options gain adoption.",
            ]
            helped = assessment.antifragile_nodes
            hurt = assessment.fragile_nodes

        rotation = [
            f"Rotate away from {', '.join(hurt[:2]) or 'fragile incumbents'} toward {', '.join(helped[:2]) or 'resilience themes'}.",
            f"Favor indirect beneficiaries because {pattern.disruptor_actor} changes the cost curve more than the headline alone implies.",
        ]
        if bundle and bundle.sentiment_entropy.value > 0.55:
            third_order.append("Social and narrative fragmentation keep the shock alive longer than a single event window.")

        fallback = RippleScenario(
            trigger=trigger,
            first_order=first_order,
            second_order=second_order,
            third_order=third_order,
            sectors_helped=helped,
            sectors_hurt=hurt,
            capital_rotation=rotation,
            fragile_nodes=assessment.fragile_nodes,
            antifragile_nodes=assessment.antifragile_nodes,
            time_horizon="3 to 18 months",
            confidence=min(0.92, 0.45 + assessment.fragility_score.value * 0.4),
        )
        refined, llm_diag = self.reasoner.refine_model(
            system_prompt=self.prompts["ripple_architect"],
            user_payload={
                "cluster": cluster.model_dump(mode="json"),
                "pattern": patterns[0].model_dump(mode="json"),
                "fragility": fragility[0].model_dump(mode="json"),
                "bundle": bundles[0].model_dump(mode="json") if bundles else None,
                "fallback": fallback.model_dump(mode="json"),
            },
            model_class=RippleScenario,
            fallback=fallback,
        )
        return [refined], llm_diag
