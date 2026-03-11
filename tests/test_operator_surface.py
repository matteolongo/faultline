from faultline.graph.runner import StrategicSwarmRunner
from faultline.presentation.operator_surface import (
    available_demo_scenarios,
    list_recent_runs,
    load_outcome_json,
    load_outcome_markdown,
    load_report_markdown,
    parse_operator_datetime,
    run_and_summarize,
    summarize_final_state,
)
from faultline.utils.io import write_json


def test_operator_surface_summarizes_demo_run(tmp_path) -> None:
    runner = StrategicSwarmRunner(
        output_dir=tmp_path / "outputs",
        database_url=f"sqlite:///{tmp_path / 'runs.sqlite'}",
    )
    payload = run_and_summarize(runner, mode="demo", scenario="open_model_breakout")
    summary = payload["summary"]

    assert summary["run_id"]
    assert summary["run_dir"]
    assert summary["publication_status"] in {"publish", "monitor_only"}
    assert summary["cluster_id"]
    assert "calibrated_conviction" in summary
    assert summary["scenario_branch_count"] >= 1
    assert summary["stage_warning_count"] >= 1
    assert summary["action_traceability_count"] >= 1
    assert payload["report_json"]
    assert payload["report_markdown"]


def test_operator_surface_handles_monitor_only_and_missing_report(tmp_path) -> None:
    final_state = {
        "final_report": {
            "publication_status": "monitor_only",
            "executive_summary": "Summary",
            "monitor_only_reason": "Weak agreement",
            "system_topology": "Topology",
            "market_implications": [],
        },
        "selected_cluster": {
            "cluster_id": "cluster-1",
            "canonical_title": "Cluster",
            "cluster_strength": 0.4,
            "agreement_score": 0.3,
        },
        "diagnostics": {
            "fragility_score": 0.49,
            "publish_decision": "monitor_only",
            "source_counts": {"newsapi": 0},
        },
    }
    summary = summarize_final_state(final_state)
    assert summary["monitor_only_reason"] == "Weak agreement"
    assert load_report_markdown(tmp_path / "missing") is None


def test_operator_surface_lists_recent_runs_and_parses_time(tmp_path) -> None:
    run_dir = tmp_path / "outputs" / "demo" / "run-1"
    write_json(
        run_dir / "report.json",
        {
            "publication_status": "publish",
            "executive_summary": "A structural shift.",
            "monitor_only_reason": None,
        },
    )
    recent = list_recent_runs(tmp_path / "outputs", limit=5)
    assert recent[0]["run_id"] == "run-1"
    parsed = parse_operator_datetime("2026-03-08T10:00:00Z")
    assert parsed.isoformat().startswith("2026-03-08T10:00:00+00:00")
    assert "open_model_breakout" in available_demo_scenarios()


def test_operator_surface_loads_followup_outcomes(tmp_path) -> None:
    runner = StrategicSwarmRunner(
        output_dir=tmp_path / "outputs",
        database_url=f"sqlite:///{tmp_path / 'runs.sqlite'}",
    )
    initial = runner.run_demo("open_model_breakout")
    runner.score_followup(
        run_id=initial["run_id"],
        followup_signals=[
            {
                "id": "followup-1",
                "provider_name": "sample",
                "provider_item_id": "followup-1",
                "source": "news",
                "timestamp": "2026-03-12T10:00:00+00:00",
                "fetched_at": "2026-03-12T10:00:00+00:00",
                "published_at": "2026-03-12T10:00:00+00:00",
                "signal_type": "news",
                "title": "Enterprise Cloud Suite cuts prices to defend its bundle",
                "summary": "Portability and platform bypass remain central to customer discussions.",
                "region": "Global",
                "entities": ["Enterprise Cloud Suite"],
                "tags": ["discount", "platform", "portability", "response"],
                "confidence": 0.8,
                "payload": {},
            }
        ],
    )

    outcome_json = load_outcome_json(initial["run_dir"])
    outcome_markdown = load_outcome_markdown(initial["run_dir"])

    assert outcome_json is not None
    assert "summary" in outcome_json
    assert outcome_markdown is not None
    assert "## Outcomes" in outcome_markdown
