from strategic_swarm_agent.graph.runner import StrategicSwarmRunner


def test_replay_rebuilds_report_from_stored_run(tmp_path) -> None:
    runner = StrategicSwarmRunner(
        output_dir=tmp_path / "outputs",
        db_path=tmp_path / "runs.sqlite",
        database_url=f"sqlite:///{tmp_path / 'runs.sqlite'}",
    )
    first = runner.run_demo("open_model_breakout")
    replayed = runner.replay(run_id=first["run_id"])

    first_report = first["final_state"]["final_report"]
    replay_report = replayed["final_state"]["final_report"]

    assert replay_report.system_topology == first_report.system_topology
    assert replay_report.publication_status == first_report.publication_status
