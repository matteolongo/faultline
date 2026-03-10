from datetime import UTC, datetime, timedelta

from faultline.graph.runner import StrategicSwarmRunner
from faultline.models import Prediction, RawSignal
from faultline.prediction import OutcomeEvaluator


def test_outcome_evaluator_scores_prediction_types() -> None:
    predictions = [
        Prediction(
            prediction_type="actor_move",
            description="Enterprise Cloud Suite will defend pricing and tighten bundle control.",
            rationale="Incumbent is under pressure.",
            time_horizon="1-4 weeks",
            related_actors=["Enterprise Cloud Suite"],
            confidence=0.7,
        ),
        Prediction(
            prediction_type="narrative",
            description="Coverage shifts toward platform bypass and portability.",
            rationale="Mechanism is becoming clearer.",
            time_horizon="days to weeks",
            related_actors=["Enterprise Cloud Suite"],
            confidence=0.68,
        ),
        Prediction(
            prediction_type="asset_repricing",
            description="Assets tied to flexibility and neutral infrastructure should outperform exposed incumbents.",
            rationale="Repricing should follow the structural shift.",
            time_horizon="1-8 weeks",
            affected_assets=["open ecosystem enablers", "bundled incumbents"],
            confidence=0.72,
        ),
    ]
    signals = [
        RawSignal(
            id="f1",
            provider_name="sample",
            provider_item_id="f1",
            source="news",
            timestamp=datetime.now(UTC),
            fetched_at=datetime.now(UTC),
            published_at=datetime.now(UTC),
            signal_type="news",
            title="Enterprise Cloud Suite responds with deeper discounting to defend bundle retention",
            summary="The company tightens its platform posture as customers demand portability.",
            region="Global",
            entities=["Enterprise Cloud Suite"],
            tags=["response", "discount", "portability", "platform"],
            confidence=0.8,
            payload={},
        ),
        RawSignal(
            id="f2",
            provider_name="sample",
            provider_item_id="f2",
            source="market",
            timestamp=datetime.now(UTC),
            fetched_at=datetime.now(UTC),
            published_at=datetime.now(UTC),
            signal_type="market",
            title="Open ecosystem enablers gain as bundled incumbents weaken",
            summary="Demand rises for neutral orchestration and portability layers.",
            region="Global",
            entities=["Open ecosystem enablers", "Bundled incumbents"],
            tags=["outperform", "gain", "pressure", "portability"],
            confidence=0.77,
            payload={},
        ),
    ]

    outcomes = OutcomeEvaluator().score(predictions, signals)

    assert len(outcomes) == 3
    assert outcomes[0].outcome_status == "confirmed"
    assert outcomes[1].outcome_status == "confirmed"
    assert outcomes[2].outcome_status == "confirmed"


def test_runner_score_followup_persists_outcomes(tmp_path) -> None:
    runner = StrategicSwarmRunner(
        output_dir=tmp_path / "outputs",
        database_url=f"sqlite:///{tmp_path / 'runs.sqlite'}",
    )
    initial = runner.run_demo("open_model_breakout")
    followup_signals = [
        RawSignal(
            id="fu-1",
            provider_name="sample",
            provider_item_id="fu-1",
            source="news",
            timestamp=datetime.now(UTC) + timedelta(days=1),
            fetched_at=datetime.now(UTC) + timedelta(days=1),
            published_at=datetime.now(UTC) + timedelta(days=1),
            signal_type="news",
            title="Enterprise Cloud Suite cuts prices and defends its AI bundle",
            summary="Customers continue asking for portability as the platform bypass narrative spreads.",
            region="Global",
            entities=["Enterprise Cloud Suite"],
            tags=["discount", "platform", "portability", "response"],
            confidence=0.8,
            payload={},
        ),
        RawSignal(
            id="fu-2",
            provider_name="sample",
            provider_item_id="fu-2",
            source="market",
            timestamp=datetime.now(UTC) + timedelta(days=2),
            fetched_at=datetime.now(UTC) + timedelta(days=2),
            published_at=datetime.now(UTC) + timedelta(days=2),
            signal_type="market",
            title="Open ecosystem enablers gain while bundled incumbents weaken",
            summary="Investors reprice beneficiaries of interoperability and neutral tooling.",
            region="Global",
            entities=["Open ecosystem enablers", "Bundled incumbents"],
            tags=["gain", "pressure", "outperform", "interoperability"],
            confidence=0.79,
            payload={},
        ),
    ]

    result = runner.score_followup(run_id=initial["run_id"], followup_signals=followup_signals)
    stored = runner.store.load_outcomes_for_run(initial["run_id"])

    assert result["run_id"] == initial["run_id"]
    assert result["followup_signal_count"] == 2
    assert result["summary"]["confirmed"] >= 2
    assert stored
    assert any(item.outcome_status == "confirmed" for item in stored)
