from __future__ import annotations

from datetime import UTC, datetime

from strategic_swarm_agent.llm.backend import StructuredReasoner
from strategic_swarm_agent.models import (
    AbstractPattern,
    EventCluster,
    FinalReport,
    FragilityAssessment,
    PublishedReport,
    ReviewedOpportunity,
    RippleScenario,
    SignalBundle,
    SignalEvent,
)
from strategic_swarm_agent.utils.config import load_prompts


class ReportBuilder:
    def __init__(self, reasoner: StructuredReasoner | None = None) -> None:
        self.reasoner = reasoner or StructuredReasoner()
        self.prompts = load_prompts()

    def build(
        self,
        report_id: str,
        run_id: str,
        events: list[SignalEvent],
        cluster: EventCluster,
        patterns: list[AbstractPattern],
        bundles: list[SignalBundle],
        fragility: list[FragilityAssessment],
        ripple_scenarios: list[RippleScenario],
        reviewed: list[ReviewedOpportunity],
        provenance: list[str],
        detected_scenario=None,
        equity_opportunities=None,
    ) -> PublishedReport:
        pattern = patterns[0]
        assessment = fragility[0]
        ripple = ripple_scenarios[0]
        approved = [item for item in reviewed if item.approved]
        top_signal = max(events, key=lambda item: item.possible_systemic_relevance)
        contradictions = []
        if cluster.agreement_score < 0.45:
            contradictions.append("Cluster agreement is too weak.")
        if len(cluster.source_families) < 2:
            contradictions.append("Only one source family confirmed the story.")
        if assessment.fragility_score.value < 0.55:
            contradictions.append("Fragility score is below the publication threshold.")
        if not approved:
            contradictions.append("No opportunity idea survived execution critique.")
        publication_status = "publish" if not contradictions else "monitor_only"

        executive_summary = (
            f"{cluster.canonical_title} is not a simple event cluster. It is a {pattern.pattern_name.lower()} topology in which "
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
        opportunity_map = [] if publication_status != "publish" else [
            f"{item.idea.direction.upper()} {', '.join(item.idea.related_assets_or_theme[:3])}: {item.idea.thesis}"
            for item in approved
        ]
        execution_recommendations = (
            [f"{item.idea.thesis} Invalidation: {item.idea.invalidation}" for item in approved]
            if publication_status == "publish"
            else ["Monitor only. The structural topology is interesting, but evidence is not strong enough to publish an execution thesis."]
        )
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
        fallback = FinalReport(
            publication_status=publication_status,
            executive_summary=executive_summary,
            system_topology=system_topology,
            fragility_map=fragility_map,
            ripple_map=ripple_map,
            opportunity_map=opportunity_map,
            execution_recommendations=execution_recommendations,
            open_questions=open_questions,
            invalidation_signals=invalidation_signals,
            provenance=provenance_lines,
            monitor_only_reason="; ".join(contradictions) if contradictions else None,
            detected_scenario=detected_scenario,
            equity_opportunities=equity_opportunities or [],
        )
        final_report, llm_diag = self.reasoner.refine_model(
            system_prompt=self.prompts["execution_critic"],
            user_payload={
                "cluster": cluster.model_dump(mode="json"),
                "pattern": pattern.model_dump(mode="json"),
                "fragility": assessment.model_dump(mode="json"),
                "ripple": ripple.model_dump(mode="json"),
                "reviewed_opportunities": [item.model_dump(mode="json") for item in reviewed],
                "fallback": fallback.model_dump(mode="json"),
            },
            model_class=FinalReport,
            fallback=fallback,
        )
        final_report.publication_status = publication_status
        if publication_status != "publish":
            final_report.monitor_only_reason = "; ".join(contradictions)
            final_report.opportunity_map = []
            final_report.execution_recommendations = execution_recommendations
        # Preserve scenario + equity fields (LLM refine_model doesn't know about them)
        final_report.detected_scenario = detected_scenario
        final_report.equity_opportunities = equity_opportunities or []
        return PublishedReport(
            report_id=report_id,
            run_id=run_id,
            cluster_id=cluster.cluster_id,
            publication_status=publication_status,
            published_at=datetime.now(UTC),
            report=final_report,
            diagnostics={"contradictions": contradictions, **llm_diag},
        )


def render_markdown(report: FinalReport) -> str:
    lines = [
        "# Strategic Swarm Agent Report",
        "",
        "## Executive Summary",
        report.executive_summary,
        "",
        "## Publication Status",
        report.publication_status,
        "",
    ]

    # Scenario Detection section
    if report.detected_scenario:
        sc = report.detected_scenario
        lines += [
            "## Detected Scenario",
            f"**{sc.scenario_name}** · type: `{sc.scenario_type}` · confidence: {sc.confidence:.0%}",
            "",
        ]
        if sc.key_actors:
            lines += [f"**Key actors:** {', '.join(sc.key_actors)}", ""]
        if sc.geographic_scope:
            lines += [f"**Geographic scope:** {', '.join(sc.geographic_scope)}", ""]
        if sc.consequence_chain:
            lines += ["### Causal Chain"]
            lines += [f"{i+1}. {step}" for i, step in enumerate(sc.consequence_chain)]
            lines += [""]

    # Equity Opportunities section
    if report.equity_opportunities:
        lines += ["## Equity Signals", ""]
        lines += ["| Symbol | Company | Direction | Confidence | Rationale |"]
        lines += ["|--------|---------|-----------|------------|-----------|"]
        for opp in report.equity_opportunities:
            arrow = {"long": "⬆ LONG", "short": "⬇ SHORT", "watch": "👁 WATCH"}.get(opp.direction, opp.direction.upper())
            lines += [f"| {opp.symbol} | {opp.company_name} | {arrow} | {opp.confidence:.0%} | {opp.rationale} |"]
        lines += [""]

    lines += [
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
    ]
    if report.monitor_only_reason:
        lines.extend(
            [
                "",
                "## Monitor Only Reason",
                report.monitor_only_reason,
            ]
        )
    lines.extend(
        [
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
    )
    return "\n".join(lines)
