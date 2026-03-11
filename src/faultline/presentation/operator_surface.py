from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from faultline.graph.runner import StrategicSwarmRunner, default_goldset
from faultline.utils.io import serialize_model


def parse_operator_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def summarize_final_state(final_state: dict[str, Any]) -> dict[str, Any]:
    report = final_state.get("final_report") or {}
    cluster = final_state.get("selected_cluster") or {}
    diagnostics = final_state.get("diagnostics") or {}
    return {
        "publication_status": report.get("publication_status"),
        "headline": report.get("headline"),
        "executive_summary": report.get("executive_summary"),
        "monitor_only_reason": report.get("monitor_only_reason"),
        "system_topology": report.get("system_topology"),
        "stage": report.get("stage"),
        "calibrated_conviction": report.get("calibrated_conviction"),
        "opportunity_count": len(report.get("market_implications") or report.get("opportunity_map") or []),
        "cluster_id": cluster.get("cluster_id"),
        "cluster_title": cluster.get("canonical_title"),
        "cluster_strength": cluster.get("cluster_strength"),
        "agreement_score": cluster.get("agreement_score"),
        "stage_diagnostic": diagnostics.get("stage"),
        "publish_decision": diagnostics.get("publish_decision"),
        "source_counts": diagnostics.get("source_counts", {}),
        "calibration_note_count": len(report.get("calibration_notes") or []),
        "endangered_symbol_count": len(report.get("endangered_symbols") or []),
    }


def load_outcome_markdown(run_dir: str | Path) -> str | None:
    path = Path(run_dir) / "outcomes.md"
    if not path.exists():
        return None
    return path.read_text()


def load_outcome_json(run_dir: str | Path) -> dict[str, Any] | None:
    path = Path(run_dir) / "outcomes.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def load_report_markdown(run_dir: str | Path) -> str | None:
    path = Path(run_dir) / "report.md"
    if not path.exists():
        return None
    return path.read_text()


def load_report_json(run_dir: str | Path) -> dict[str, Any] | None:
    path = Path(run_dir) / "report.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def list_recent_runs(output_dir: str | Path, limit: int = 10) -> list[dict[str, Any]]:
    root = Path(output_dir)
    if not root.exists():
        return []
    candidates = []
    for report_path in root.glob("*/*/report.json"):
        run_dir = report_path.parent
        run_id = run_dir.name
        scenario = run_dir.parent.name
        payload = json.loads(report_path.read_text())
        candidates.append(
            {
                "scenario": scenario,
                "run_id": run_id,
                "run_dir": str(run_dir),
                "publication_status": payload.get("publication_status"),
                "executive_summary": payload.get("executive_summary"),
                "monitor_only_reason": payload.get("monitor_only_reason"),
                "updated_at": report_path.stat().st_mtime,
            }
        )
    return sorted(candidates, key=lambda item: item["updated_at"], reverse=True)[:limit]


def available_demo_scenarios() -> list[str]:
    return default_goldset()


def run_and_summarize(
    runner: StrategicSwarmRunner,
    *,
    mode: str,
    scenario: str | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    lookback_minutes: int | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    if mode == "demo":
        if not scenario:
            raise ValueError("Scenario is required for demo mode.")
        result = runner.run_demo(scenario)
    elif mode == "live":
        if not start_at or not end_at:
            raise ValueError("Live mode requires start_at and end_at.")
        result = runner.run_live(start_at=start_at, end_at=end_at)
    elif mode == "latest":
        result = runner.run_latest(lookback_minutes=lookback_minutes)
    elif mode == "replay":
        if run_id:
            result = runner.replay(run_id=run_id)
        elif start_at and end_at:
            result = runner.replay(start_at=start_at, end_at=end_at)
        else:
            raise ValueError("Replay mode requires run_id or start_at/end_at.")
    else:
        raise ValueError(f"Unsupported mode: {mode}")

    summary = summarize_final_state(serialize_model(result["final_state"]))
    summary["run_id"] = result["run_id"]
    summary["run_dir"] = result["run_dir"]
    outcome_json = load_outcome_json(result["run_dir"])
    if outcome_json:
        outcome_summary = outcome_json.get("summary", {})
        summary["confirmed_outcomes"] = outcome_summary.get("confirmed", 0)
        summary["partial_outcomes"] = outcome_summary.get("partial", 0)
        summary["unconfirmed_outcomes"] = outcome_summary.get("unconfirmed", 0)
    return {
        "result": result,
        "summary": summary,
        "report_markdown": load_report_markdown(result["run_dir"]),
        "report_json": load_report_json(result["run_dir"]),
        "outcome_markdown": load_outcome_markdown(result["run_dir"]),
        "outcome_json": outcome_json,
    }
