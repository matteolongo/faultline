from datetime import UTC, datetime, timedelta

from faultline.graph.runner import StrategicSwarmRunner
from faultline.models import RawSignal


def _followup_signals(base: datetime) -> list[RawSignal]:
    return [
        RawSignal(
            id="auto-fu-1",
            provider_name="sample",
            provider_item_id="auto-fu-1",
            source="news",
            timestamp=base + timedelta(hours=1),
            fetched_at=base + timedelta(hours=1),
            published_at=base + timedelta(hours=1),
            signal_type="news",
            title="Enterprise Cloud Suite cuts prices to defend its bundle",
            summary="Portability pressure persists and the incumbent is responding defensively.",
            region="Global",
            entities=["Enterprise Cloud Suite"],
            tags=["discount", "response", "platform", "portability"],
            confidence=0.8,
            payload={},
        ),
        RawSignal(
            id="auto-fu-2",
            provider_name="sample",
            provider_item_id="auto-fu-2",
            source="market",
            timestamp=base + timedelta(hours=2),
            fetched_at=base + timedelta(hours=2),
            published_at=base + timedelta(hours=2),
            signal_type="market",
            title="Open ecosystem enablers gain while bundled incumbents weaken",
            summary="The repricing theme continues to broaden across related assets.",
            region="Global",
            entities=["Open ecosystem enablers", "Bundled incumbents"],
            tags=["gain", "outperform", "pressure"],
            confidence=0.79,
            payload={},
        ),
    ]


def test_store_lists_only_unscored_runs_for_followup(tmp_path) -> None:
    runner = StrategicSwarmRunner(
        output_dir=tmp_path / "outputs",
        database_url=f"sqlite:///{tmp_path / 'runs.sqlite'}",
    )
    initial = runner.run_demo("open_model_breakout")
    cutoff = datetime.now(UTC) + timedelta(minutes=1)

    before = runner.store.list_runs_for_followup(cutoff_time=cutoff, include_demo=True)
    assert any(item["run_id"] == initial["run_id"] for item in before)

    runner.score_followup(run_id=initial["run_id"], followup_signals=_followup_signals(datetime.now(UTC)))

    after = runner.store.list_runs_for_followup(cutoff_time=cutoff, include_demo=True)
    assert all(item["run_id"] != initial["run_id"] for item in after)


def test_runner_auto_scores_followups_from_window(tmp_path) -> None:
    runner = StrategicSwarmRunner(
        output_dir=tmp_path / "outputs",
        database_url=f"sqlite:///{tmp_path / 'runs.sqlite'}",
    )
    initial = runner.run_demo("open_model_breakout")
    base = datetime.now(UTC)
    signals = _followup_signals(base)
    runner.store.save_raw_signals(signals)

    result = runner.auto_score_followups(
        start_at=base,
        end_at=base + timedelta(hours=3),
        min_run_age_minutes=0,
        limit_runs=10,
        include_demo=True,
        rescore_existing=False,
    )
    outcomes = runner.store.load_outcomes_for_run(initial["run_id"])

    assert result["processed_run_count"] >= 1
    assert any(item["run_id"] == initial["run_id"] for item in result["processed_runs"])
    assert outcomes
    assert result["calibration_signal_count"] >= 1
