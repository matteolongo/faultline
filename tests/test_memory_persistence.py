from faultline.graph.runner import StrategicSwarmRunner
from faultline.graph.workflow import StrategicSwarmWorkflow
from faultline.models import EventCluster
from faultline.persistence.store import SignalStore


def test_situation_memory_bootstraps_from_persisted_snapshots(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path / 'runs.sqlite'}"
    first_runner = StrategicSwarmRunner(output_dir=tmp_path / "outputs", database_url=db_url)
    first = first_runner.run_demo("open_model_breakout")
    stored_snapshot = first_runner.store.load_situation_snapshots()[0]
    first_runner.store.save_situation_snapshot(
        stored_snapshot.model_copy(update={"situation_id": "prior-1", "title": "Earlier open-model stress"})
    )

    bootstrapped_workflow = StrategicSwarmWorkflow(
        store=SignalStore(db_url),
        live_providers=[],
    )
    cluster = EventCluster.model_validate(first["final_state"]["selected_cluster"])
    related = bootstrapped_workflow.retrieve_related_situations({"selected_cluster": cluster, "provenance": []})

    assert related["related_situations"]
    assert related["related_situations"][0].situation_id == "prior-1"
