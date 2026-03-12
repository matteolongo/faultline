from faultline.graph.runner import StrategicSwarmRunner
from faultline.presentation.operator_surface import (
    available_demo_scenarios,
    current_review_step,
    list_recent_runs,
    load_outcome_json,
    load_outcome_markdown,
    load_report_markdown,
    parse_operator_datetime,
    review_toc_rows,
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


def test_operator_surface_summarizes_topic_chat_run(tmp_path) -> None:
    class _FakeWebSearchProvider:
        provider_name = "openai-websearch"
        source_family = "synthesis"

        def query(self, question: str, *, story_key: str, fetched_at):
            return [
                {
                    "id": "topic-1",
                    "provider_name": self.provider_name,
                    "provider_item_id": "topic-1",
                    "source": self.source_family,
                    "timestamp": fetched_at.isoformat(),
                    "fetched_at": fetched_at.isoformat(),
                    "published_at": fetched_at.isoformat(),
                    "signal_type": "news-synthesis",
                    "title": "Iran conflict disrupts energy shipping lanes",
                    "summary": question,
                    "source_url": "https://example.com/topic/1",
                    "query_key": story_key,
                    "region": "Global",
                    "entities": ["Iran", "Israel"],
                    "tags": ["energy", "shipping", "market-stress", "chokepoint"],
                    "confidence": 0.82,
                    "payload": {},
                }
            ]

    class _FakeMacroProvider:
        provider_name = "macro-fake"
        source_family = "macro"

        def fetch_window(self, start_at, end_at):
            return [
                {
                    "id": "macro-1",
                    "provider_name": self.provider_name,
                    "provider_item_id": "macro-1",
                    "source": self.source_family,
                    "timestamp": end_at.isoformat(),
                    "fetched_at": end_at.isoformat(),
                    "published_at": end_at.isoformat(),
                    "signal_type": "macro-observation",
                    "title": "Oil spike pushes inflation expectations higher",
                    "summary": "Energy and shipping costs are repricing globally.",
                    "source_url": "https://example.com/macro/1",
                    "query_key": "macro-1",
                    "region": "Global",
                    "entities": ["Oil", "Inflation"],
                    "tags": ["energy", "market-stress", "chokepoint"],
                    "confidence": 0.8,
                    "payload": {},
                }
            ]

    runner = StrategicSwarmRunner(
        output_dir=tmp_path / "outputs",
        database_url=f"sqlite:///{tmp_path / 'runs.sqlite'}",
        live_providers=[_FakeMacroProvider()],
        web_search_provider=_FakeWebSearchProvider(),
    )
    session = runner.prepare_topic_chat(
        "Deep dive on Iran war impact on global inflation and listed defense/energy names over 3 months"
    )

    payload = run_and_summarize(runner, mode="topic_chat", topic_session=session.model_dump(mode="json"))

    assert payload["summary"]["topic_prompt"].startswith("Deep dive on Iran war")
    assert payload["summary"]["retrieval_question_count"] >= 3
    assert payload["report_json"]["deep_dive_objective"]


def test_operator_surface_formats_review_rows() -> None:
    rows = review_toc_rows(
        {
            "session_id": "session-1",
            "thread_id": "thread-1",
            "run_mode": "demo",
            "current_node_id": "normalize_events",
            "approved_nodes": ["ingest_signals"],
            "state_snapshots": [{}],
            "steps": [
                {
                    "node_id": "ingest_signals",
                    "title": "Ingest Signals",
                    "status": "approved",
                    "changed_keys": ["raw_signals"],
                    "artifact_summary": "3 signals",
                },
                {
                    "node_id": "normalize_events",
                    "title": "Normalize Events",
                    "status": "paused",
                    "changed_keys": ["normalized_events", "event_clusters"],
                    "artifact_summary": "2 events / 1 clusters",
                },
            ],
        }
    )
    step = current_review_step(
        {
            "session_id": "session-1",
            "thread_id": "thread-1",
            "run_mode": "demo",
            "current_node_id": "normalize_events",
            "approved_nodes": ["ingest_signals"],
            "state_snapshots": [{}],
            "steps": [
                {
                    "node_id": "ingest_signals",
                    "title": "Ingest Signals",
                    "status": "approved",
                    "changed_keys": ["raw_signals"],
                    "artifact_summary": "3 signals",
                },
                {
                    "node_id": "normalize_events",
                    "title": "Normalize Events",
                    "status": "paused",
                    "changed_keys": ["normalized_events", "event_clusters"],
                    "artifact_summary": "2 events / 1 clusters",
                },
            ],
        }
    )

    assert rows[0]["node_id"] == "ingest_signals"
    assert rows[1]["status"] == "paused"
    assert rows[1]["changed_key_count"] == 2
    assert step["node_id"] == "normalize_events"
