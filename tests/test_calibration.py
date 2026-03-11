from datetime import UTC, datetime, timedelta

from faultline.analysis.system_first import ActionEngine
from faultline.graph.runner import StrategicSwarmRunner
from faultline.models import (
    CalibrationSignal,
    MarketImplication,
    Mechanism,
    OutcomeRecord,
    Prediction,
    RawSignal,
    SituationSnapshot,
    StageAssessment,
)
from faultline.persistence.store import SignalStore


def _snapshot() -> SituationSnapshot:
    return SituationSnapshot(
        situation_id="s1",
        title="Test situation",
        summary="Summary",
        system_under_pressure="software platform competition",
        mechanisms=[
            Mechanism(
                mechanism_id="platform_bypass",
                name="Platform Bypass",
                explanation="Open layers reduce dependence on the incumbent.",
                confidence=0.7,
            )
        ],
        stage=StageAssessment(stage="repricing", explanation="Repricing underway", confidence=0.7),
        confidence=0.7,
    )


def test_store_loads_calibration_signals(tmp_path) -> None:
    store = SignalStore(f"sqlite:///{tmp_path / 'runs.sqlite'}")
    predictions = [
        Prediction(
            prediction_type="actor_move",
            description="Actor responds.",
            rationale="Base rationale.",
            time_horizon="1-4 weeks",
            related_actors=["Incumbent"],
            confidence=0.7,
        )
    ]
    store.save_predictions(run_id="run-a", predictions=predictions)
    store.save_outcome_records(
        run_id="run-a",
        outcomes=[
            OutcomeRecord(
                prediction_id=predictions[0].prediction_id or "missing",
                prediction_type="actor_move",
                target="Incumbent",
                outcome_status="confirmed",
                explanation="Confirmed by follow-up.",
                confidence_delta=0.2,
                supporting_signal_ids=["sig-1"],
            )
        ],
    )

    signals = store.load_calibration_signals()

    assert len(signals) == 1
    assert signals[0].prediction_type == "actor_move"
    assert signals[0].confirmed_rate == 1.0
    assert "held up well" in signals[0].guidance


def test_workflow_uses_prior_calibration_to_adjust_predictions(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path / 'runs.sqlite'}"
    runner = StrategicSwarmRunner(output_dir=tmp_path / "outputs", database_url=db_url)
    first = runner.run_demo("open_model_breakout")
    runner.score_followup(
        run_id=first["run_id"],
        followup_signals=[
            RawSignal(
                id="followup-1",
                provider_name="sample",
                provider_item_id="followup-1",
                source="news",
                timestamp=datetime.now(UTC) + timedelta(days=1),
                fetched_at=datetime.now(UTC) + timedelta(days=1),
                published_at=datetime.now(UTC) + timedelta(days=1),
                signal_type="news",
                title="Enterprise Cloud Suite responds with deeper discounts",
                summary="The company tightens control while portability remains central.",
                region="Global",
                entities=["Enterprise Cloud Suite"],
                tags=["response", "discount", "portability", "platform"],
                confidence=0.8,
                payload={},
            ),
            RawSignal(
                id="followup-2",
                provider_name="sample",
                provider_item_id="followup-2",
                source="market",
                timestamp=datetime.now(UTC) + timedelta(days=2),
                fetched_at=datetime.now(UTC) + timedelta(days=2),
                published_at=datetime.now(UTC) + timedelta(days=2),
                signal_type="market",
                title="Open ecosystem enablers gain while bundled incumbents weaken",
                summary="The repricing thesis continues to play out.",
                region="Global",
                entities=["Open ecosystem enablers", "Bundled incumbents"],
                tags=["gain", "outperform", "pressure"],
                confidence=0.79,
                payload={},
            ),
        ],
    )

    second = runner.run_demo("open_model_breakout")
    predictions = second["final_state"]["predictions"]
    report = second["final_state"]["final_report"]

    assert second["final_state"]["calibration_signals"]
    assert any("Calibration:" in item.rationale for item in predictions)
    assert report.calibration_notes


def test_bad_calibration_makes_actions_more_conservative() -> None:
    action_engine = ActionEngine()
    snapshot = _snapshot()
    implication = MarketImplication(
        target="Bundled AI incumbents",
        direction="negative",
        thesis_type="high_confidence_opportunity",
        rationale="Defensive repricing is visible.",
        time_horizon="2-8 weeks",
        confidence=0.7,
    )
    good_calibration = [
        CalibrationSignal(
            prediction_type="asset_repricing",
            sample_size=8,
            confirmed_rate=0.75,
            partial_rate=0.125,
            unconfirmed_rate=0.125,
            average_confidence_delta=0.12,
            guidance="Asset repricing predictions have held up well.",
        )
    ]
    bad_calibration = [
        CalibrationSignal(
            prediction_type="asset_repricing",
            sample_size=8,
            confirmed_rate=0.125,
            partial_rate=0.125,
            unconfirmed_rate=0.75,
            average_confidence_delta=-0.15,
            guidance="Asset repricing predictions have weak confirmation.",
        )
    ]

    good_actions, good_exits, good_endangered = action_engine.generate(snapshot, [implication], [], good_calibration)
    bad_actions, bad_exits, bad_endangered = action_engine.generate(snapshot, [implication], [], bad_calibration)

    assert good_actions[0].confidence > bad_actions[0].confidence
    assert good_actions[0].action in {"avoid", "enter"}
    assert bad_actions[0].action == "watch"
