from datetime import UTC, datetime, timedelta

from faultline.graph.runner import StrategicSwarmRunner
from faultline.models import OutcomeRecord, Prediction, RawSignal
from faultline.persistence.store import SignalStore


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
