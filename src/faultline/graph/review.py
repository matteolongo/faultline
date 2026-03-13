from __future__ import annotations

from pathlib import Path
from typing import Any

from faultline.graph.workflow import WORKFLOW_NODE_ORDER
from faultline.models import NodeReviewSession, NodeReviewStep, ReviewStepArtifactRefs
from faultline.utils.io import serialize_model

NODE_TITLES = {
    "ingest_signals": "Ingest Signals",
    "normalize_events": "Normalize Events",
    "retrieve_related_situations": "Retrieve Related Situations",
    "retrieve_calibration": "Retrieve Calibration",
    "map_situation": "Map Situation",
    "generate_predictions": "Generate Predictions",
    "map_market_implications": "Map Market Implications",
    "generate_actions": "Generate Actions",
    "synthesize_report": "Synthesize Report",
    "remember_situation": "Remember Situation",
}

NODE_OUTPUT_KEYS = {
    "ingest_signals": ["raw_signals", "diagnostics", "provenance"],
    "normalize_events": [
        "normalized_events",
        "event_clusters",
        "selected_cluster",
        "included_signal_ids",
        "excluded_signal_ids",
        "diagnostics",
        "provenance",
    ],
    "retrieve_related_situations": ["related_situations", "provenance"],
    "retrieve_calibration": ["calibration_signals", "provenance"],
    "map_situation": ["situation_snapshot", "provenance"],
    "generate_predictions": ["predictions", "scenario_tree", "stage_transition_warnings", "provenance"],
    "map_market_implications": ["market_implications", "provenance"],
    "generate_actions": ["action_recommendations", "exit_signals", "endangered_symbols", "provenance"],
    "synthesize_report": ["final_report", "diagnostics"],
    "remember_situation": [],
}

EDITABLE_NODE_IDS = {
    "normalize_events",
    "map_situation",
    "map_market_implications",
    "generate_actions",
    "synthesize_report",
}


def coerce_review_session(session: NodeReviewSession | dict[str, Any]) -> NodeReviewSession:
    return session if isinstance(session, NodeReviewSession) else NodeReviewSession.model_validate(session)


def build_review_steps(session: NodeReviewSession | dict[str, Any]) -> list[NodeReviewStep]:
    current = coerce_review_session(session)
    snapshots = [serialize_model(item) for item in current.state_snapshots]
    reached_nodes = max(0, len(snapshots) - 1)
    artifact_refs = _artifact_refs(current.selected_run_dir)
    steps: list[NodeReviewStep] = []

    for index, node_id in enumerate(WORKFLOW_NODE_ORDER):
        if index < reached_nodes:
            pre_state = snapshots[index]
            post_state = snapshots[index + 1]
            changed_keys = _changed_keys(node_id, pre_state, post_state)
            preview_payload = _preview_payload(node_id, pre_state, post_state)
            editable_payload = _editable_payload(node_id, post_state)
            status = _step_status(current, node_id, index, reached_nodes)
            steps.append(
                NodeReviewStep(
                    node_id=node_id,
                    title=NODE_TITLES[node_id],
                    status=status,
                    changed_keys=changed_keys,
                    artifact_summary=_artifact_summary(node_id, preview_payload),
                    delta_summary={key: _value_summary(post_state.get(key)) for key in changed_keys},
                    preview_payload=preview_payload,
                    editable_payload=editable_payload,
                    artifact_refs=artifact_refs,
                    pre_state_index=index,
                    post_state_index=index + 1,
                )
            )
            continue

        steps.append(
            NodeReviewStep(
                node_id=node_id,
                title=NODE_TITLES[node_id],
                status="pending",
                artifact_refs=artifact_refs,
            )
        )
    return steps


def review_toc_rows(session: NodeReviewSession | dict[str, Any]) -> list[dict[str, Any]]:
    current = coerce_review_session(session)
    rows = []
    for step in current.steps:
        rows.append(
            {
                "node_id": step.node_id,
                "title": step.title,
                "status": step.status,
                "changed_key_count": len(step.changed_keys),
                "artifact_summary": step.artifact_summary,
            }
        )
    return rows


def current_review_step(session: NodeReviewSession | dict[str, Any]) -> NodeReviewStep | None:
    current = coerce_review_session(session)
    return next((step for step in current.steps if step.status == "paused"), None)


def _step_status(session: NodeReviewSession, node_id: str, index: int, reached_nodes: int) -> str:
    if index >= reached_nodes:
        return "pending"
    if session.status == "completed":
        return "completed"
    if node_id == session.current_node_id:
        return "paused"
    if node_id in session.approved_nodes:
        return "approved"
    return "completed"


def _artifact_refs(run_dir: str | None) -> ReviewStepArtifactRefs:
    if not run_dir:
        return ReviewStepArtifactRefs()
    path = Path(run_dir)
    return ReviewStepArtifactRefs(
        run_dir=str(path),
        report_path=str(path / "report.md"),
        trace_path=str(path / "trace.json"),
    )


def _changed_keys(node_id: str, pre_state: dict[str, Any], post_state: dict[str, Any]) -> list[str]:
    return [key for key in NODE_OUTPUT_KEYS[node_id] if pre_state.get(key) != post_state.get(key)]


def _value_summary(value: Any) -> str:
    if value is None:
        return "empty"
    if isinstance(value, list):
        return f"{len(value)} items"
    if isinstance(value, dict):
        return f"{len(value)} fields"
    if isinstance(value, str):
        return value[:120]
    return str(value)


def _preview_payload(node_id: str, pre_state: dict[str, Any], post_state: dict[str, Any]) -> dict[str, Any]:
    if node_id == "ingest_signals":
        return {
            "signals": [_signal_row(item) for item in post_state.get("raw_signals", [])],
            "source_counts": post_state.get("diagnostics", {}).get("source_counts", {}),
        }
    if node_id == "normalize_events":
        return {
            "included_signal_ids": post_state.get("included_signal_ids", []),
            "excluded_signal_ids": post_state.get("excluded_signal_ids", []),
            "normalized_events": [_event_row(item) for item in post_state.get("normalized_events", [])],
            "candidate_clusters": [_cluster_row(item) for item in post_state.get("event_clusters", [])],
            "selected_cluster_id": (post_state.get("selected_cluster") or {}).get("cluster_id"),
        }
    if node_id == "retrieve_related_situations":
        return {"related_situations": post_state.get("related_situations", [])}
    if node_id == "retrieve_calibration":
        rows = post_state.get("calibration_signals", [])
        return {"calibration_signals": rows, "count": len(rows)}
    if node_id == "map_situation":
        snapshot = post_state.get("situation_snapshot") or {}
        return {
            "situation_snapshot": snapshot,
            "actors": [item.get("name") for item in snapshot.get("key_actors", [])],
            "mechanisms": [item.get("name") for item in snapshot.get("mechanisms", [])],
        }
    if node_id == "generate_predictions":
        return {
            "predictions": post_state.get("predictions", []),
            "scenario_tree": post_state.get("scenario_tree", []),
            "stage_transition_warnings": post_state.get("stage_transition_warnings", []),
        }
    if node_id == "map_market_implications":
        return {"market_implications": post_state.get("market_implications", [])}
    if node_id == "generate_actions":
        return {
            "action_recommendations": post_state.get("action_recommendations", []),
            "exit_signals": post_state.get("exit_signals", []),
            "endangered_symbols": post_state.get("endangered_symbols", []),
        }
    if node_id == "synthesize_report":
        report = post_state.get("final_report") or {}
        return {
            "headline": report.get("headline", ""),
            "executive_summary": report.get("executive_summary", ""),
            "publication_status": report.get("publication_status", ""),
            "market_implications": report.get("market_implications", []),
            "retrieval_questions": report.get("retrieval_questions", []),
            "full_report": report,
        }
    snapshot = post_state.get("situation_snapshot") or {}
    return {
        "message": "Situation snapshot saved to memory."
        if snapshot
        else "No situation snapshot was available to save.",
        "situation_id": snapshot.get("situation_id"),
    }


def _editable_payload(node_id: str, post_state: dict[str, Any]) -> dict[str, Any]:
    if node_id not in EDITABLE_NODE_IDS:
        return {}
    if node_id == "normalize_events":
        return {
            "excluded_signal_ids": post_state.get("excluded_signal_ids", []),
            "selected_cluster_id": (post_state.get("selected_cluster") or {}).get("cluster_id"),
        }
    if node_id == "map_situation":
        snapshot = post_state.get("situation_snapshot") or {}
        return {
            "title": snapshot.get("title", ""),
            "summary": snapshot.get("summary", ""),
            "system_under_pressure": snapshot.get("system_under_pressure", ""),
        }
    if node_id == "map_market_implications":
        return {"market_implications": post_state.get("market_implications", [])}
    if node_id == "generate_actions":
        return {
            "action_recommendations": post_state.get("action_recommendations", []),
            "exit_signals": post_state.get("exit_signals", []),
        }
    report = post_state.get("final_report") or {}
    return {
        "headline": report.get("headline", ""),
        "executive_summary": report.get("executive_summary", ""),
    }


def _artifact_summary(node_id: str, preview_payload: dict[str, Any]) -> str:
    if node_id == "ingest_signals":
        return f"{len(preview_payload.get('signals', []))} signals"
    if node_id == "normalize_events":
        return (
            f"{len(preview_payload.get('normalized_events', []))} events / "
            f"{len(preview_payload.get('candidate_clusters', []))} clusters"
        )
    if node_id == "retrieve_related_situations":
        return f"{len(preview_payload.get('related_situations', []))} related situations"
    if node_id == "retrieve_calibration":
        return f"{preview_payload.get('count', 0)} calibration signals"
    if node_id == "map_situation":
        snapshot = preview_payload.get("situation_snapshot", {})
        return snapshot.get("title", "No situation snapshot")
    if node_id == "generate_predictions":
        return f"{len(preview_payload.get('predictions', []))} predictions"
    if node_id == "map_market_implications":
        return f"{len(preview_payload.get('market_implications', []))} implications"
    if node_id == "generate_actions":
        return f"{len(preview_payload.get('action_recommendations', []))} actions"
    if node_id == "synthesize_report":
        return preview_payload.get("publication_status", "report ready")
    return preview_payload.get("message", "")


def _signal_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "source": item.get("source"),
        "timestamp": item.get("timestamp"),
        "region": item.get("region"),
        "confidence": item.get("confidence"),
        "url": item.get("source_url"),
        "summary": item.get("summary"),
    }


def _event_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "source": item.get("source"),
        "cluster_id": item.get("cluster_id"),
        "novelty": item.get("novelty"),
        "systemic_relevance": item.get("possible_systemic_relevance"),
    }


def _cluster_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "cluster_id": item.get("cluster_id"),
        "title": item.get("canonical_title"),
        "agreement": item.get("agreement_score"),
        "strength": item.get("cluster_strength"),
        "region": item.get("region"),
    }
