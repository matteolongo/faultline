from __future__ import annotations

from strategic_swarm_agent.models import OpportunityIdea, RippleScenario, ScoreDetail

DIRECT_THEME_KEYWORDS = {
    "oil majors",
    "utilities incumbent",
    "hyperscaler",
    "sovereign bonds",
    "regional utility",
}


class OpportunityGenerator:
    def generate(self, scenarios: list[RippleScenario], retry_count: int = 0) -> list[OpportunityIdea]:
        ideas: list[OpportunityIdea] = []
        for scenario in scenarios:
            helped_theme = scenario.sectors_helped[0] if scenario.sectors_helped else "resilience infrastructure"
            hurt_theme = scenario.sectors_hurt[0] if scenario.sectors_hurt else "fragile centralized assets"

            primary = self._build_idea(
                thesis=f"Long the indirect beneficiaries of {helped_theme} demand as the system rerates toward resilience.",
                direction="long",
                exposure_type="theme",
                related_assets_or_theme=scenario.sectors_helped[:3],
                catalyst=scenario.trigger,
                invalidation="The incumbent absorbs the shock cheaply and restores confidence without rerouting demand.",
                time_horizon=scenario.time_horizon,
                directness="indirect",
                base_convexity=0.72 - retry_count * 0.02,
            )
            hedge = self._build_idea(
                thesis=f"Short the most route-concentrated or financing-dependent expression of {hurt_theme}.",
                direction="short",
                exposure_type="basket",
                related_assets_or_theme=scenario.sectors_hurt[:3],
                catalyst="Further cost inflation, share loss, or funding pressure confirms structural fragility.",
                invalidation="Redundancy improves quickly enough that the affected incumbents keep pricing power.",
                time_horizon=scenario.time_horizon,
                directness="semi-direct",
                base_convexity=0.58 - retry_count * 0.01,
            )
            optionality = self._build_idea(
                thesis="Own picks-and-shovels software that benefits regardless of which bypass winner captures the narrative.",
                direction="long",
                exposure_type="theme",
                related_assets_or_theme=["monitoring software", "orchestration tooling", "risk intelligence"],
                catalyst="Budgets shift from defending the old perimeter to coordinating new distributed systems.",
                invalidation="Buyers treat the shock as temporary and stop funding resilience tooling.",
                time_horizon="6 to 24 months",
                directness="indirect",
                base_convexity=0.78 - retry_count * 0.02,
            )
            ideas.extend([primary, hedge, optionality])
        return ideas

    def _build_idea(
        self,
        thesis: str,
        direction: str,
        exposure_type: str,
        related_assets_or_theme: list[str],
        catalyst: str,
        invalidation: str,
        time_horizon: str,
        directness: str,
        base_convexity: float,
    ) -> OpportunityIdea:
        crowdedness = 0.25 if directness == "indirect" else 0.55
        if any(theme in DIRECT_THEME_KEYWORDS for theme in related_assets_or_theme):
            crowdedness += 0.15
        convexity = min(0.95, max(0.05, base_convexity - crowdedness * 0.12))
        return OpportunityIdea(
            thesis=thesis,
            direction=direction,
            exposure_type=exposure_type,
            related_assets_or_theme=related_assets_or_theme,
            why_convex="It captures second-order demand shifts rather than the first obvious headline reaction.",
            catalyst=catalyst,
            invalidation=invalidation,
            time_horizon=time_horizon,
            convexity_score=ScoreDetail(
                value=convexity,
                explanation="Higher for indirect, non-consensus beneficiaries with multiple ways to win and fewer ways to be obviously crowded.",
            ),
            confidence=min(0.9, 0.48 + convexity * 0.4),
            crowdedness_risk=min(1.0, crowdedness),
            directness=directness,
        )
