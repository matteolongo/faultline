from strategic_swarm_agent.graph.runner import StrategicSwarmRunner
from strategic_swarm_agent.providers.sample import SampleScenarioRepository


def test_all_demo_scenarios_run_end_to_end(tmp_path) -> None:
    runner = StrategicSwarmRunner(output_dir=tmp_path / "outputs", db_path=tmp_path / "runs.sqlite")
    repository = SampleScenarioRepository()

    for scenario_id in repository.scenario_ids():
        result = runner.evaluate(scenario_id)
        state = result["final_state"]
        report = state["final_report"]

        assert state["abstract_patterns"]
        assert state["fragility_assessments"]
        assert state["ripple_scenarios"]
        assert report.opportunity_map
        assert result["evaluation"]["overall"] >= 0.7
