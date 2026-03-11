from faultline.graph.runner import StrategicSwarmRunner
from faultline.synthesis.report_builder import render_markdown


def test_report_storytelling_has_traceability_and_boundaries(tmp_path) -> None:
    runner = StrategicSwarmRunner(
        output_dir=tmp_path / "outputs",
        database_url=f"sqlite:///{tmp_path / 'runs.sqlite'}",
    )
    result = runner.run_demo("open_model_breakout")
    report = result["final_state"]["final_report"]
    markdown = render_markdown(report)

    assert report.scenario_tree
    assert any("If " in line for line in report.scenario_tree)
    assert report.confidence_boundaries
    assert report.action_traceability
    assert "## Confidence Boundaries" in markdown
    assert "## Action Traceability" in markdown
