from __future__ import annotations

from faultline.models import (
    ActionRecommendation,
    CalibrationSignal,
    EventCluster,
    FinalReport,
    MarketImplication,
    OutcomeRecord,
    Prediction,
    RelatedSituation,
    SituationSnapshot,
)


class ReportBuilder:
    def build(
        self,
        *,
        snapshot: SituationSnapshot,
        cluster: EventCluster,
        related_situations: list[RelatedSituation],
        calibration_signals: list[CalibrationSignal],
        predictions: list[Prediction],
        implications: list[MarketImplication],
        actions: list[ActionRecommendation],
        exits: list[ActionRecommendation],
        provenance: list[str],
    ) -> FinalReport:
        publishable = cluster.agreement_score >= 0.55 and snapshot.confidence >= 0.55 and bool(implications)
        publication_status = "publish" if publishable else "monitor_only"
        monitor_reason = None
        if not publishable:
            reasons = []
            if cluster.agreement_score < 0.55:
                reasons.append("cross-source agreement is still weak")
            if snapshot.confidence < 0.55:
                reasons.append("situation confidence remains below threshold")
            if not implications:
                reasons.append("market translation is not strong enough yet")
            monitor_reason = "; ".join(reasons)

        system_map = [
            f"System under pressure: {snapshot.system_under_pressure}",
            *[
                f"{actor.role.title()}: {actor.name} | objectives: {', '.join(actor.objectives[:2])}"
                for actor in snapshot.key_actors
            ],
            *[
                f"{relation.relation_type.title()}: {relation.source_actor} -> {relation.target_actor}"
                for relation in snapshot.relations
            ],
        ]
        mechanism_map = [f"{item.name}: {item.explanation}" for item in snapshot.mechanisms]
        scenario_map = [
            f"{prediction.prediction_type}: {prediction.description} ({prediction.time_horizon})"
            for prediction in predictions
        ]
        market_lines = [
            f"{item.target}: {item.direction} | {item.thesis_type} | {item.rationale}" for item in implications
        ]
        action_lines = [f"{item.action.upper()} {item.target}: {item.rationale}" for item in actions]
        exit_lines = [f"{item.action.upper()} {item.target}: {item.rationale}" for item in exits]
        evidence = [f"{item.title}: {item.rationale}" for item in snapshot.evidence]
        references = [item.source_url for item in snapshot.evidence if item.source_url]
        references.extend(f"memory:{item.title}" for item in related_situations[:2])
        calibration_notes = [
            f"{item.prediction_type}: {item.guidance} sample={item.sample_size} confirmed={item.confirmed_rate:.0%}"
            for item in calibration_signals
        ]
        calibrated_conviction = (
            sum(item.confidence for item in actions) / len(actions)
            if actions
            else (sum(item.confidence for item in predictions) / len(predictions) if predictions else 0.0)
        )

        return FinalReport(
            publication_status=publication_status,
            headline=snapshot.title,
            executive_summary=(
                f"{snapshot.title} reflects pressure on {snapshot.system_under_pressure} via "
                f"{', '.join(item.name for item in snapshot.mechanisms[:2])}."
            ),
            why_now=(
                f"The situation is in {snapshot.stage.stage} and already shows "
                f"{cluster.agreement_score:.0%} cross-source agreement."
            ),
            calibrated_conviction=calibrated_conviction,
            system_topology=snapshot.system_under_pressure,
            situation=snapshot.summary,
            stage=snapshot.stage.stage,
            system_map=system_map,
            mechanism_map=mechanism_map,
            scenario_map=scenario_map,
            market_implications=market_lines,
            actions_now=action_lines,
            exit_signals=exit_lines,
            risks=snapshot.risks,
            open_questions=[
                "What follow-up signal would most clearly confirm the current mechanism?",
                "Which actor can change the timing or invalidate the base case fastest?",
            ],
            invalidation_signals=[
                "The incumbent restores control without ceding pricing, legitimacy, or platform position.",
                "Follow-up signals fail to broaden beyond the original cluster.",
                "Expected beneficiaries do not see adoption, demand, or capital rotation.",
            ],
            evidence=evidence,
            references=references,
            calibration_notes=calibration_notes,
            provenance=provenance,
            monitor_only_reason=monitor_reason,
            fragility_map=mechanism_map,
            ripple_map=scenario_map,
            opportunity_map=market_lines,
            execution_recommendations=action_lines,
        )

    def empty_report(self, provenance: list[str]) -> FinalReport:
        return FinalReport(
            publication_status="monitor_only",
            executive_summary="No coherent clustered situation was available to analyze.",
            why_now="There was insufficient clustered evidence to build a system-first report.",
            monitor_only_reason="missing clustered situation",
            provenance=provenance,
        )


def render_markdown(report: FinalReport) -> str:
    lines = [
        "# Faultline Analyst Memo",
        "",
        "## Headline",
        report.headline or "Untitled situation",
        "",
        "## Executive Summary",
        report.executive_summary,
        "",
        "## Why Now",
        report.why_now,
        "",
        "## Publication Status",
        report.publication_status,
        "",
        "## Calibrated Conviction",
        f"{report.calibrated_conviction:.0%}",
        "",
        "## Stage",
        report.stage or "unknown",
        "",
        "## Situation",
        report.situation or report.system_topology or "No situation summary available.",
        "",
        "## System Map",
        *[f"- {item}" for item in report.system_map],
        "",
        "## Active Mechanisms",
        *[f"- {item}" for item in report.mechanism_map],
        "",
        "## Likely Next Moves",
        *[f"- {item}" for item in report.scenario_map],
        "",
        "## Market Implications",
        *[f"- {item}" for item in report.market_implications],
        "",
        "## Actions Now",
        *[f"- {item}" for item in report.actions_now],
        "",
        "## Exit Signals",
        *[f"- {item}" for item in report.exit_signals],
    ]
    if report.monitor_only_reason:
        lines.extend(["", "## Monitor Only Reason", report.monitor_only_reason])
    lines.extend(
        [
            "",
            "## Risks",
            *[f"- {item}" for item in report.risks],
            "",
            "## Open Questions",
            *[f"- {item}" for item in report.open_questions],
            "",
            "## Invalidation Signals",
            *[f"- {item}" for item in report.invalidation_signals],
            "",
            "## Evidence",
            *[f"- {item}" for item in report.evidence],
            "",
            "## Calibration",
            *[f"- {item}" for item in report.calibration_notes],
            "",
            "## References",
            *[f"- {item}" for item in report.references],
            "",
            "## Provenance",
            *[f"- {item}" for item in report.provenance],
        ]
    )
    return "\n".join(lines)


def render_outcome_markdown(*, run_id: str, outcomes: list[OutcomeRecord], summary: dict[str, int]) -> str:
    lines = [
        "# Faultline Follow-Up Review",
        "",
        "## Run",
        run_id,
        "",
        "## Summary",
        f"- Confirmed: {summary.get('confirmed', 0)}",
        f"- Partial: {summary.get('partial', 0)}",
        f"- Unconfirmed: {summary.get('unconfirmed', 0)}",
        "",
        "## Outcomes",
    ]
    for item in outcomes:
        lines.extend(
            [
                f"- `{item.prediction_type}` on `{item.target}` -> **{item.outcome_status}**",
                f"  {item.explanation}",
                f"  Evidence: {', '.join(item.supporting_signal_ids) if item.supporting_signal_ids else 'none'}",
            ]
        )
    return "\n".join(lines)
