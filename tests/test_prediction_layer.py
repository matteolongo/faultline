from datetime import UTC, datetime

from faultline.analysis.system_first import ActionEngine, PredictionEngine
from faultline.models import (
    Actor,
    EventCluster,
    MarketImplication,
    Mechanism,
    SituationSnapshot,
    StageAssessment,
    StageTransitionWarning,
)


def _snapshot() -> SituationSnapshot:
    return SituationSnapshot(
        situation_id="s-prediction",
        title="Prediction layer test",
        summary="System pressure is broadening.",
        system_under_pressure="software platform competition",
        key_actors=[
            Actor(name="Incumbent Cloud", role="incumbent"),
            Actor(name="Open Toolchain Alliance", role="challenger"),
        ],
        mechanisms=[
            Mechanism(
                mechanism_id="platform_bypass",
                name="Platform Bypass",
                explanation="Open layers reduce dependence on bundled control planes.",
                confidence=0.76,
            )
        ],
        stage=StageAssessment(stage="repricing", explanation="Repricing underway", confidence=0.72),
        confidence=0.73,
    )


def _cluster() -> EventCluster:
    now = datetime.now(UTC)
    return EventCluster(
        cluster_id="cluster-prediction",
        story_key="story-prediction",
        canonical_title="Open architecture pressure broadens",
        summary="Follow-up signals show continued portability demand and pricing pressure.",
        region="Global",
        entities=["Incumbent Cloud", "Open Toolchain Alliance"],
        tags=["open-source", "portability", "pricing-power", "market-stress"],
        source_families=["news", "market"],
        signal_ids=["sig-1", "sig-2"],
        first_seen_at=now,
        last_seen_at=now,
        novelty_score=0.71,
        agreement_score=0.77,
        cluster_strength=0.75,
    )


def test_prediction_engine_outputs_scenario_tree_and_stage_warnings() -> None:
    predictions, scenario_tree, warnings = PredictionEngine().predict(_snapshot(), _cluster(), [])

    assert len(predictions) >= 3
    assert all(item.confidence_band in {"speculative", "asymmetric", "high_confidence"} for item in predictions)
    assert all(item.prior_evidence for item in predictions)

    assert len(scenario_tree) == 3
    assert scenario_tree[0].probability >= scenario_tree[1].probability >= scenario_tree[2].probability
    assert abs(sum(item.probability for item in scenario_tree) - 1.0) < 1e-6
    assert all(item.confidence_band in {"speculative", "asymmetric", "high_confidence"} for item in scenario_tree)

    assert warnings
    assert warnings[0].from_stage == "repricing"
    assert all(item.probability > 0.0 for item in warnings)


def test_action_engine_uses_stage_transition_warnings_for_actions() -> None:
    warning = StageTransitionWarning(
        from_stage="repricing",
        to_stage="exhaustion_or_reversal",
        trigger="Incumbent execution recovery is broadening.",
        lead_time="2-8 weeks",
        probability=0.8,
        rationale="Late-stage reversal risk is rising.",
    )
    implication = MarketImplication(
        target="Bundled AI incumbents",
        direction="negative",
        thesis_type="high_confidence_opportunity",
        rationale="Defensive repricing remains visible.",
        time_horizon="2-8 weeks",
        confidence=0.74,
    )

    actions, exits, _ = ActionEngine().generate(
        snapshot=_snapshot(),
        implications=[implication],
        predictions=[],
        stage_transition_warnings=[warning],
        portfolio_positions=[],
        watchlist=[],
    )

    assert any(item.thesis_type == "stage_transition_warning" for item in actions)
    assert any(item.action == "trim" and item.thesis_type == "stage_transition_warning" for item in exits)
