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
    ScenarioPath,
    SituationSnapshot,
    StageTransitionWarning,
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
        scenario_tree: list[ScenarioPath],
        stage_transition_warnings: list[StageTransitionWarning],
        implications: list[MarketImplication],
        actions: list[ActionRecommendation],
        exits: list[ActionRecommendation],
        endangered_symbols: list[str],
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
            f"{prediction.prediction_type}: {prediction.description} ({prediction.time_horizon}) "
            f"[{prediction.confidence_band} {prediction.confidence:.0%}]"
            for prediction in predictions
        ]
        scenario_tree_lines = [self._render_scenario_branch(item) for item in scenario_tree]
        transition_warning_lines = [
            f"{item.from_stage}->{item.to_stage} in {item.lead_time} | p={item.probability:.0%} | trigger: {item.trigger}"
            for item in stage_transition_warnings
        ]
        priors = sorted({prior for prediction in predictions for prior in prediction.prior_evidence})
        confidence_boundaries = self._confidence_boundaries()
        market_lines = [
            f"{item.target}: {item.direction} | {item.thesis_type} | {item.rationale}" for item in implications
        ]
        action_lines = [f"{item.action.upper()} {item.target}: {item.rationale}" for item in actions]
        exit_lines = [f"{item.action.upper()} {item.target}: {item.rationale}" for item in exits]
        action_traceability = self._action_traceability(
            actions=actions,
            predictions=predictions,
            warnings=stage_transition_warnings,
            evidence=snapshot.evidence,
        )
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
            scenario_tree=scenario_tree_lines,
            stage_transition_warnings=transition_warning_lines,
            prediction_priors=priors,
            confidence_boundaries=confidence_boundaries,
            action_traceability=action_traceability,
            market_implications=market_lines,
            actions_now=action_lines,
            exit_signals=exit_lines,
            endangered_symbols=endangered_symbols,
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

    def _render_scenario_branch(self, path: ScenarioPath) -> str:
        trigger = path.trigger_signals[0] if path.trigger_signals else "follow-up confirmation broadens"
        effect = path.market_effects[0] if path.market_effects else "relative repricing continues"
        return (
            f"{path.name} ({path.branch_type}) -> p={path.probability:.0%} [{path.confidence_band}] in {path.timeframe}. "
            f"If {trigger.lower()}, then {effect.lower()}."
        )

    def _confidence_boundaries(self) -> list[str]:
        return [
            "high_confidence: >=74% conviction. Bias toward direct execution unless invalidation signals appear.",
            "asymmetric: 58%-73% conviction. Scale in with staged sizing and explicit downside controls.",
            "speculative: <58% conviction. Monitor only; avoid full-size directional exposure.",
        ]

    def _action_traceability(
        self,
        *,
        actions: list[ActionRecommendation],
        predictions: list[Prediction],
        warnings: list[StageTransitionWarning],
        evidence: list,
    ) -> list[str]:
        evidence_titles = [item.title for item in evidence]
        timing_prediction = max((item for item in predictions if item.prediction_type == "timing_window"), default=None)
        strongest_warning = max(warnings, key=lambda item: item.probability, default=None)
        lines: list[str] = []
        for action in actions:
            band = self._band_for(action.confidence)
            linked_prediction = self._prediction_for_action(action, predictions)
            support = []
            if linked_prediction is not None:
                support.append(f"prediction={linked_prediction.prediction_type}:{linked_prediction.confidence:.0%}")
            if action.thesis_type == "timing_window_policy" and timing_prediction is not None:
                support.append(f"timing_window={timing_prediction.confidence:.0%}")
            if (
                action.thesis_type in {"stage_transition_warning", "timing_window_policy"}
                and strongest_warning is not None
            ):
                support.append(
                    f"stage_warning={strongest_warning.from_stage}->{strongest_warning.to_stage}:{strongest_warning.probability:.0%}"
                )
            if evidence_titles:
                support.append(f"evidence={evidence_titles[0]}")
                if len(evidence_titles) > 1:
                    support.append(f"evidence_2={evidence_titles[1]}")
            lines.append(
                f"{action.action.upper()} {action.target} | confidence={action.confidence:.0%} ({band}) | "
                f"{'; '.join(support) if support else 'support=limited'}"
            )
        return lines

    def _prediction_for_action(
        self,
        action: ActionRecommendation,
        predictions: list[Prediction],
    ) -> Prediction | None:
        if action.thesis_type == "stage_transition_warning":
            return next((item for item in predictions if item.prediction_type == "timing_window"), None)
        if action.thesis_type in {"portfolio_position", "watchlist_symbol", "timing_window_policy"}:
            return next((item for item in predictions if item.prediction_type == "asset_repricing"), None)
        if action.thesis_type == "asymmetric_opportunity":
            return next((item for item in predictions if item.prediction_type == "narrative"), None)
        return next((item for item in predictions if item.prediction_type == "actor_move"), None)

    def _band_for(self, confidence: float) -> str:
        if confidence >= 0.74:
            return "high_confidence"
        if confidence >= 0.58:
            return "asymmetric"
        return "speculative"

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
        "## Scenario Tree",
        *[f"- {item}" for item in report.scenario_tree],
        "",
        "## Stage Transition Warnings",
        *[f"- {item}" for item in report.stage_transition_warnings],
        "",
        "## Prediction Priors",
        *[f"- {item}" for item in report.prediction_priors],
        "",
        "## Confidence Boundaries",
        *[f"- {item}" for item in report.confidence_boundaries],
        "",
        "## Market Implications",
        *[f"- {item}" for item in report.market_implications],
        "",
        "## Actions Now",
        *[f"- {item}" for item in report.actions_now],
        "",
        "## Action Traceability",
        *[f"- {item}" for item in report.action_traceability],
        "",
        "## Exit Signals",
        *[f"- {item}" for item in report.exit_signals],
        "",
        "## Endangered Symbols",
        *[f"- {item}" for item in report.endangered_symbols],
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
