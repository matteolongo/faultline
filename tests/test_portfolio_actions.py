from faultline.analysis.system_first import ActionEngine
from faultline.graph.runner import StrategicSwarmRunner
from faultline.models import (
    MarketImplication,
    Mechanism,
    PortfolioPosition,
    SituationSnapshot,
    StageAssessment,
    WatchlistEntry,
)


def _snapshot() -> SituationSnapshot:
    return SituationSnapshot(
        situation_id="s-portfolio",
        title="Portfolio test",
        summary="Test summary",
        system_under_pressure="software platform competition",
        mechanisms=[
            Mechanism(
                mechanism_id="platform_bypass",
                name="Platform Bypass",
                explanation="Open ecosystems pressure incumbents.",
                confidence=0.7,
            )
        ],
        stage=StageAssessment(stage="repricing", explanation="Repricing underway", confidence=0.7),
        confidence=0.7,
    )


def test_action_engine_flags_endangered_held_symbols() -> None:
    engine = ActionEngine()
    actions, exits, endangered = engine.generate(
        _snapshot(),
        implications=[
            MarketImplication(
                target="Exposed incumbents",
                direction="negative",
                thesis_type="high_confidence_opportunity",
                rationale="Pressure on incumbent margin structure.",
                time_horizon="2-8 weeks",
                confidence=0.8,
            )
        ],
        predictions=[],
        portfolio_positions=[PortfolioPosition(symbol="AAPL", direction="long", quantity=10)],
        watchlist=[],
    )

    assert any(item.target == "AAPL" and item.action in {"exit", "trim"} for item in actions)
    assert "AAPL" in endangered
    assert any(item.target == "AAPL" and item.action == "exit" for item in exits)


def test_action_engine_generates_watchlist_recommendations() -> None:
    engine = ActionEngine()
    actions, _, _ = engine.generate(
        _snapshot(),
        implications=[
            MarketImplication(
                target="Open ecosystem enablers",
                direction="positive",
                thesis_type="asymmetric_opportunity",
                rationale="Open ecosystem theme strengthening.",
                time_horizon="1-3 months",
                confidence=0.78,
            )
        ],
        predictions=[],
        portfolio_positions=[],
        watchlist=[WatchlistEntry(symbol="NVDA", tags=["enablers"])],
    )

    assert any(item.target == "NVDA" and item.action in {"enter", "watch"} for item in actions)


def test_runner_accepts_positions_and_watchlist_in_demo(tmp_path) -> None:
    runner = StrategicSwarmRunner(
        output_dir=tmp_path / "outputs",
        database_url=f"sqlite:///{tmp_path / 'runs.sqlite'}",
    )
    result = runner.run_demo(
        "open_model_breakout",
        portfolio_positions=[{"symbol": "AAPL", "direction": "long", "quantity": 5}],
        watchlist=[{"symbol": "NVDA", "tags": ["enablers"]}],
    )
    report = result["final_state"]["final_report"]

    assert report.endangered_symbols
    assert "AAPL" in report.endangered_symbols
    assert any("NVDA" in line for line in report.actions_now)
