from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
import os
import json

from strategic_swarm_agent.evaluation.rubric import evaluate_report
from strategic_swarm_agent.graph.workflow import StrategicSwarmWorkflow
from strategic_swarm_agent.synthesis.report_builder import render_markdown
from strategic_swarm_agent.utils.io import ensure_directory, serialize_model, write_json, write_text


class StrategicSwarmRunner:
    def __init__(self, output_dir: str | Path | None = None, db_path: str | Path | None = None) -> None:
        self.output_dir = ensure_directory(Path(output_dir or os.getenv("SWARM_OUTPUT_DIR", "outputs")))
        self.db_path = Path(db_path or os.getenv("SWARM_RUN_DB", self.output_dir / "swarm_runs.sqlite"))
        self.workflow = StrategicSwarmWorkflow().build()
        self._initialize_db()

    def run(self, scenario_id: str) -> dict:
        initial_state = {"scenario_id": scenario_id}
        snapshots = list(self.workflow.stream(initial_state, stream_mode="values"))
        final_state = snapshots[-1]
        run_id = uuid.uuid4().hex[:12]
        run_dir = ensure_directory(self.output_dir / scenario_id / run_id)
        write_json(run_dir / "state.json", final_state)
        write_json(run_dir / "trace.json", snapshots)
        write_json(run_dir / "report.json", final_state["final_report"])
        write_text(run_dir / "report.md", render_markdown(final_state["final_report"]))
        self._persist_run(run_id, scenario_id, final_state, snapshots)
        return {
            "run_id": run_id,
            "scenario_id": scenario_id,
            "run_dir": str(run_dir),
            "final_state": final_state,
        }

    def evaluate(self, scenario_id: str) -> dict:
        result = self.run(scenario_id)
        report = result["final_state"]["final_report"]
        scores = evaluate_report(report)
        run_dir = Path(result["run_dir"])
        write_json(run_dir / "evaluation.json", scores)
        return {
            **result,
            "evaluation": scores,
        }

    def run_all(self, scenario_ids: list[str]) -> list[dict]:
        return [self.evaluate(scenario_id) for scenario_id in scenario_ids]

    def _initialize_db(self) -> None:
        ensure_directory(self.db_path.parent)
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    scenario_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    final_state_json TEXT NOT NULL,
                    trace_json TEXT NOT NULL
                )
                """
            )

    def _persist_run(self, run_id: str, scenario_id: str, final_state: dict, snapshots: list[dict]) -> None:
        created_at = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                "INSERT INTO runs (run_id, scenario_id, created_at, final_state_json, trace_json) VALUES (?, ?, ?, ?, ?)",
                (
                    run_id,
                    scenario_id,
                    created_at,
                    json.dumps(serialize_model(final_state)),
                    json.dumps(serialize_model(snapshots)),
                ),
            )
