from faultline.graph.runner import StrategicSwarmRunner
from faultline.providers.sample import SampleScenarioRepository


def test_all_demo_scenarios_run_end_to_end(tmp_path) -> None:
    runner = StrategicSwarmRunner(output_dir=tmp_path / "outputs", db_path=tmp_path / "runs.sqlite")
    repository = SampleScenarioRepository()

    for scenario_id in repository.scenario_ids():
        result = runner.evaluate(scenario_id)
        state = result["final_state"]
        report = state["final_report"]

        assert state["situation_snapshot"] is not None
        assert state["predictions"]
        assert state["market_implications"]
        assert state["action_recommendations"]
        assert state["exit_signals"]
        assert report.publication_status in {"publish", "monitor_only"}
        assert report.mechanism_map
        assert report.scenario_map
        assert report.confidence_boundaries
        assert report.action_traceability
        assert report.actions_now
        assert result["evaluation"]["overall"] >= 0.65
