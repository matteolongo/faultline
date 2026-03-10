from faultline.evaluation.rubric import evaluate_report
from faultline.graph.runner import StrategicSwarmRunner


def test_evaluation_rubric_rewards_reports_with_mechanisms_actions_and_evidence(tmp_path) -> None:
    runner = StrategicSwarmRunner(
        output_dir=tmp_path / "outputs",
        database_url=f"sqlite:///{tmp_path / 'runs.sqlite'}",
    )
    result = runner.run_demo("debt_defense_spiral")
    report = result["final_state"]["final_report"]
    scores = evaluate_report(report)

    assert scores["mechanism_quality"] > 0.5
    assert scores["prediction_quality"] > 0.5
    assert scores["action_quality"] > 0.5
