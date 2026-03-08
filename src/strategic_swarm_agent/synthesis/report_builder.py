from __future__ import annotations

from strategic_swarm_agent.models import (
    AbstractPattern,
    FinalReport,
    FragilityAssessment,
    ReviewedOpportunity,
    RippleScenario,
    SignalBundle,
    SignalEvent,
)


class ReportBuilder:
    def build(
        self,
        scenario_id: str,
        events: list[SignalEvent],
        patterns: list[AbstractPattern],
        bundles: list[SignalBundle],
        fragility: list[FragilityAssessment],
        ripple_scenarios: list[RippleScenario],
        reviewed: list[ReviewedOpportunity],
        provenance: list[str],
    ) -> FinalReport:
        pattern = patterns[0]
        assessment = fragility[0]
        ripple = ripple_scenarios[0]
        approved = [item for item in reviewed if item.approved]
        top_signal = max(events, key=lambda item: item.possible_systemic_relevance)

        executive_summary = (
            f"{scenario_id} is not a simple event cluster. It is a {pattern.pattern_name.lower()} topology in which "
            f"{pattern.empire_actor} represents a costly defensive surface and {pattern.disruptor_actor} uses "
            f"{pattern.cheap_weapon.lower()} to exploit this breach: {pattern.armor_breach}"
        )
        system_topology = (
            f"Empire: {pattern.empire_actor} ({pattern.empire_type}). "
            f"Disruptor: {pattern.disruptor_actor} ({pattern.disruptor_type}). "
            f"Asymmetry: {pattern.asymmetry_type}."
        )
        fragility_map = [
            f"Hubris index {assessment.hubris_index.value:.2f}: {assessment.hubris_index.explanation}",
            f"Energy-to-defense ratio {assessment.energy_defense_ratio.value:.2f}: {assessment.energy_defense_ratio.explanation}",
            f"Fragility score {assessment.fragility_score.value:.2f}: fragile nodes include {', '.join(assessment.fragile_nodes[:3])}.",
            f"Antifragility attraction {assessment.antifragility_attraction.value:.2f}: beneficiaries include {', '.join(assessment.antifragile_nodes[:3])}.",
        ]
        ripple_map = ripple.first_order + ripple.second_order + ripple.third_order
        opportunity_map = [
            f"{item.idea.direction.upper()} {', '.join(item.idea.related_assets_or_theme[:3])}: {item.idea.thesis}"
            for item in approved
        ]
        execution_recommendations = [
            f"{item.idea.thesis} Invalidation: {item.idea.invalidation}"
            for item in approved
        ] or ["No sufficiently convex idea survived critique. Stay thematic rather than force a trade."]
        open_questions = [
            "Which weak signal would most clearly confirm that the bypass is gaining durable adoption?",
            "Is funding stress accelerating faster than the dominant system can add redundancy?",
            *[note for bundle in bundles for note in bundle.uncertainty_notes],
        ]
        invalidation_signals = [
            "Repair, policy, or repricing restores confidence without forcing structural migration.",
            "Second-order beneficiaries fail to see demand transfer despite ongoing stress.",
            "The event remains local and does not propagate into financing, routing, or adoption behavior.",
        ]
        provenance_lines = provenance + [
            f"Primary trigger: {top_signal.raw_payload_reference}",
            *[f"Analog: {analog.name}" for analog in pattern.historical_analogs],
        ]

        return FinalReport(
            executive_summary=executive_summary,
            system_topology=system_topology,
            fragility_map=fragility_map,
            ripple_map=ripple_map,
            opportunity_map=opportunity_map,
            execution_recommendations=execution_recommendations,
            open_questions=open_questions,
            invalidation_signals=invalidation_signals,
            provenance=provenance_lines,
        )


def render_markdown(report: FinalReport) -> str:
    lines = [
        "# Strategic Swarm Agent Report",
        "",
        "## Executive Summary",
        report.executive_summary,
        "",
        "## System Topology",
        report.system_topology,
        "",
        "## Fragility Map",
        *[f"- {item}" for item in report.fragility_map],
        "",
        "## Ripple Map",
        *[f"- {item}" for item in report.ripple_map],
        "",
        "## Opportunity Map",
        *[f"- {item}" for item in report.opportunity_map],
        "",
        "## Execution Recommendations",
        *[f"- {item}" for item in report.execution_recommendations],
        "",
        "## Open Questions",
        *[f"- {item}" for item in report.open_questions],
        "",
        "## Invalidation Signals",
        *[f"- {item}" for item in report.invalidation_signals],
        "",
        "## Provenance",
        *[f"- {item}" for item in report.provenance],
    ]
    return "\n".join(lines)
