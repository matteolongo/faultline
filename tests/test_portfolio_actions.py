from faultline.analysis.portfolio_engine import PortfolioActionEngine
from faultline.graph.runner import StrategicSwarmRunner
from faultline.models import (
    MarketImplication,
    PortfolioPosition,
    WatchlistEntry,
)


def test_action_engine_flags_endangered_held_symbols() -> None:
    engine = PortfolioActionEngine()
    implications = [
        MarketImplication(
            target="Exposed incumbents",
            direction="negative",
            thesis_type="high_confidence_opportunity",
            rationale="Pressure on incumbent margin structure.",
            time_horizon="2-8 weeks",
            confidence=0.8,
        )
    ]
    actions, endangered = engine.generate(
        implications=implications,
        portfolio_positions=[PortfolioPosition(symbol="AAPL", direction="long", quantity=10)],
        watchlist=[],
    )

    assert any(item.target == "AAPL" and item.action in {"exit", "trim"} for item in actions)
    assert "AAPL" in endangered


def test_action_engine_generates_watchlist_recommendations() -> None:
    engine = PortfolioActionEngine()
    actions, _ = engine.generate(
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
