from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from faultline.evaluation.rubric import evaluate_report
from faultline.graph.workflow import StrategicSwarmWorkflow
from faultline.models import (
    OperatorPolicyConfig,
    OutcomeRecord,
    PortfolioPosition,
    Prediction,
    PublishedReport,
    RawSignal,
    WatchlistEntry,
)
from faultline.persistence.store import SignalStore
from faultline.prediction import OutcomeEvaluator
from faultline.providers.registry import build_live_providers
from faultline.providers.sample import SampleScenarioRepository
from faultline.synthesis.report_builder import render_markdown, render_outcome_markdown
from faultline.utils.env import bootstrap_env
from faultline.utils.io import (
    ensure_directory,
    serialize_model,
    write_json,
    write_text,
)


class StrategicSwarmRunner:
    def __init__(
        self,
        output_dir: str | Path | None = None,
        db_path: str | Path | None = None,
        database_url: str | None = None,
    ) -> None:
        bootstrap_env()
        self.output_dir = ensure_directory(Path(output_dir or os.getenv("FAULTLINE_OUTPUT_DIR", "outputs")))
        self.database_url = database_url or os.getenv(
            "FAULTLINE_DATABASE_URL",
            str(Path(db_path or self.output_dir / "swarm_runs.sqlite")),
        )
        self.store = SignalStore(self.database_url)
        self.workflow = StrategicSwarmWorkflow(store=self.store, live_providers=build_live_providers()).build()
        self.outcome_evaluator = OutcomeEvaluator()

    def run_demo(
        self,
        scenario_id: str,
        *,
        portfolio_positions: list[PortfolioPosition | dict] | None = None,
        watchlist: list[WatchlistEntry | dict] | None = None,
        operator_policy_config: OperatorPolicyConfig | dict | None = None,
    ) -> dict:
        return self._run(
            initial_state={
                "scenario_id": scenario_id,
                "run_mode": "demo",
                "portfolio_positions": portfolio_positions or [],
                "watchlist": watchlist or [],
                "operator_policy_config": operator_policy_config,
            }
        )

    def run_live(
        self,
        *,
        start_at: datetime,
        end_at: datetime,
        portfolio_positions: list[PortfolioPosition | dict] | None = None,
        watchlist: list[WatchlistEntry | dict] | None = None,
        operator_policy_config: OperatorPolicyConfig | dict | None = None,
        auto_followup: bool = False,
        followup_min_run_age_minutes: int = 60,
        followup_limit_runs: int = 20,
        followup_include_demo: bool = False,
        followup_rescore_existing: bool = False,
    ) -> dict:
        result = self._run(
            initial_state={
                "run_mode": "live",
                "window_start": start_at.isoformat(),
                "window_end": end_at.isoformat(),
                "portfolio_positions": portfolio_positions or [],
                "watchlist": watchlist or [],
                "operator_policy_config": operator_policy_config,
            }
        )
        if auto_followup:
            result["followup"] = self.auto_score_followups(
                start_at=start_at,
                end_at=end_at,
                min_run_age_minutes=followup_min_run_age_minutes,
                limit_runs=followup_limit_runs,
                include_demo=followup_include_demo,
                rescore_existing=followup_rescore_existing,
            )
        return result

    def run_latest(
        self,
        *,
        lookback_minutes: int | None = None,
        portfolio_positions: list[PortfolioPosition | dict] | None = None,
        watchlist: list[WatchlistEntry | dict] | None = None,
        operator_policy_config: OperatorPolicyConfig | dict | None = None,
        auto_followup: bool = False,
        followup_min_run_age_minutes: int = 60,
        followup_limit_runs: int = 20,
        followup_include_demo: bool = False,
        followup_rescore_existing: bool = False,
    ) -> dict:
        lookback = lookback_minutes or int(os.getenv("FAULTLINE_DEFAULT_LOOKBACK_MINUTES", "60"))
        end_at = datetime.now(UTC)
        start_at = end_at - timedelta(minutes=lookback)
        return self.run_live(
            start_at=start_at,
            end_at=end_at,
            portfolio_positions=portfolio_positions,
            watchlist=watchlist,
            operator_policy_config=operator_policy_config,
            auto_followup=auto_followup,
            followup_min_run_age_minutes=followup_min_run_age_minutes,
            followup_limit_runs=followup_limit_runs,
            followup_include_demo=followup_include_demo,
            followup_rescore_existing=followup_rescore_existing,
        )

    def ingest_window(self, *, start_at: datetime, end_at: datetime) -> dict:
        result = self.run_live(start_at=start_at, end_at=end_at)
        diagnostics = result["final_state"].get("diagnostics", {})
        return {
            "run_id": result["run_id"],
            "window_start": start_at.isoformat(),
            "window_end": end_at.isoformat(),
            "source_counts": diagnostics.get("source_counts", {}),
            "duplicates_removed": diagnostics.get("duplicates_removed", 0),
            "cluster_count": diagnostics.get("cluster_count", 0),
        }

    def backfill(self, *, start_at: datetime, end_at: datetime, step_minutes: int = 60) -> list[dict]:
        cursor = start_at
        results = []
        while cursor < end_at:
            next_cursor = min(cursor + timedelta(minutes=step_minutes), end_at)
            results.append(self.run_live(start_at=cursor, end_at=next_cursor))
            cursor = next_cursor
        return results

    def replay(
        self,
        *,
        run_id: str | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> dict:
        if run_id:
            previous = self.store.get_run_state(run_id)
            if not previous:
                raise ValueError(f"Unknown run_id: {run_id}")
            raw_signals = previous.get("raw_signals", [])
            return self._run(initial_state={"run_mode": "replay", "raw_signals": raw_signals})
        if not start_at or not end_at:
            raise ValueError("Replay requires either run_id or start_at/end_at.")
        raw_signals = self.store.load_raw_signals_for_window(start_at, end_at)
        return self._run(
            initial_state={
                "run_mode": "replay",
                "window_start": start_at.isoformat(),
                "window_end": end_at.isoformat(),
                "raw_signals": raw_signals,
            }
        )

    def evaluate(self, scenario_id: str) -> dict:
        result = self.run_demo(scenario_id)
        report = result["final_state"]["final_report"]
        scores = evaluate_report(report)
        run_dir = Path(result["run_dir"])
        write_json(run_dir / "evaluation.json", scores)
        return {
            **result,
            "evaluation": scores,
        }

    def evaluate_goldset(self, scenario_ids: list[str]) -> list[dict]:
        return [self.evaluate(scenario_id) for scenario_id in scenario_ids]

    def score_followup(
        self,
        *,
        run_id: str,
        followup_signals: list[RawSignal | dict] | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> dict:
        predictions = self.store.load_predictions_for_run(run_id)
        if not predictions:
            previous = self.store.get_run_state(run_id)
            if not previous:
                raise ValueError(f"Unknown run_id: {run_id}")
            predictions = [Prediction.model_validate(item) for item in previous.get("predictions", [])]
        if followup_signals is not None:
            signals = [
                signal if isinstance(signal, RawSignal) else RawSignal.model_validate(signal)
                for signal in followup_signals
            ]
            self.store.save_raw_signals(signals)
        else:
            if not start_at or not end_at:
                raise ValueError("Follow-up scoring requires explicit signals or start_at/end_at.")
            signals = self.store.load_raw_signals_for_window(start_at, end_at)
        outcomes = self.outcome_evaluator.score(predictions, signals)
        self.store.save_outcome_records(run_id=run_id, outcomes=outcomes)
        summary = self._summarize_outcomes(outcomes)
        self._persist_outcomes(run_id=run_id, outcomes=outcomes, summary=summary)
        return {
            "run_id": run_id,
            "followup_signal_count": len(signals),
            "outcomes": [item.model_dump(mode="json") for item in outcomes],
            "summary": summary,
        }

    def auto_score_followups(
        self,
        *,
        start_at: datetime,
        end_at: datetime,
        min_run_age_minutes: int = 60,
        limit_runs: int = 20,
        include_demo: bool = False,
        rescore_existing: bool = False,
    ) -> dict:
        signals = self.store.load_raw_signals_for_window(start_at, end_at)
        if not signals:
            return {
                "window_start": start_at.isoformat(),
                "window_end": end_at.isoformat(),
                "followup_signal_count": 0,
                "candidate_run_count": 0,
                "processed_run_count": 0,
                "processed_runs": [],
                "calibration_signal_count": len(self.store.load_calibration_signals()),
            }
        cutoff = end_at - timedelta(minutes=min_run_age_minutes)
        candidates = self.store.list_runs_for_followup(
            cutoff_time=cutoff,
            limit=limit_runs,
            include_demo=include_demo,
            include_scored=rescore_existing,
        )
        processed_runs: list[dict] = []
        for item in candidates:
            run_id = item["run_id"]
            predictions = self.store.load_predictions_for_run(run_id)
            if not predictions:
                continue
            outcomes = self.outcome_evaluator.score(predictions, signals)
            self.store.save_outcome_records(run_id=run_id, outcomes=outcomes)
            summary = self._summarize_outcomes(outcomes)
            self._persist_outcomes(run_id=run_id, outcomes=outcomes, summary=summary)
            processed_runs.append(
                {
                    "run_id": run_id,
                    "run_mode": item["run_mode"],
                    "scenario_id": item["scenario_id"],
                    "summary": summary,
                    "prediction_count": len(predictions),
                }
            )
        return {
            "window_start": start_at.isoformat(),
            "window_end": end_at.isoformat(),
            "followup_signal_count": len(signals),
            "candidate_run_count": len(candidates),
            "processed_run_count": len(processed_runs),
            "processed_runs": processed_runs,
            "calibration_signal_count": len(self.store.load_calibration_signals()),
        }

    def list_signals(self, *, limit: int = 25, provider_name: str | None = None) -> list[dict]:
        return self.store.list_raw_signals(limit=limit, provider_name=provider_name)

    def provider_health(self) -> list[dict]:
        providers = []
        for provider in build_live_providers():
            configured = bool(
                os.getenv(
                    {
                        "newsapi": "NEWSAPI_API_KEY",
                        "alphavantage": "ALPHAVANTAGE_API_KEY",
                        "fred": "FRED_API_KEY",
                    }.get(provider.provider_name, ""),
                    "1" if provider.provider_name == "gdelt" else "",
                )
            )
            providers.append((provider.provider_name, provider.source_family, configured))
        return [item.model_dump(mode="json") for item in self.store.provider_health(providers)]

    def _run(self, *, initial_state: dict) -> dict:
        run_id = uuid4().hex[:12]
        if initial_state.get("raw_signals"):
            initial_state["raw_signals"] = [
                signal if isinstance(signal, RawSignal) else RawSignal.model_validate(signal)
                for signal in initial_state["raw_signals"]
            ]
        initial_state["portfolio_positions"] = [
            item if isinstance(item, PortfolioPosition) else PortfolioPosition.model_validate(item)
            for item in initial_state.get("portfolio_positions", [])
        ]
        initial_state["watchlist"] = [
            item if isinstance(item, WatchlistEntry) else WatchlistEntry.model_validate(item)
            for item in initial_state.get("watchlist", [])
        ]
        if initial_state.get("operator_policy_config") is not None:
            policy = initial_state["operator_policy_config"]
            initial_state["operator_policy_config"] = (
                policy if isinstance(policy, OperatorPolicyConfig) else OperatorPolicyConfig.model_validate(policy)
            )
        initial_state = {
            **initial_state,
            "diagnostics": {"run_id": run_id},
        }
        snapshots = list(self.workflow.stream(initial_state, stream_mode="values"))
        final_state = snapshots[-1]
        scenario_label = initial_state.get("scenario_id") or initial_state.get("run_mode", "live")
        run_dir = ensure_directory(self.output_dir / scenario_label / run_id)
        write_json(run_dir / "state.json", final_state)
        write_json(run_dir / "trace.json", snapshots)
        if final_state.get("final_report") is not None:
            write_json(run_dir / "report.json", final_state["final_report"])
            write_text(run_dir / "report.md", render_markdown(final_state["final_report"]))
        self.store.save_run(
            run_id=run_id,
            scenario_id=initial_state.get("scenario_id"),
            run_mode=initial_state.get("run_mode", "demo"),
            window_start=self._parse_time(initial_state.get("window_start")),
            window_end=self._parse_time(initial_state.get("window_end")),
            publish_decision=final_state.get("diagnostics", {}).get("publish_decision", "monitor_only"),
            diagnostics=final_state.get("diagnostics", {}),
            final_state=serialize_model(final_state),
            trace=serialize_model(snapshots),
        )
        self.store.save_predictions(run_id=run_id, predictions=final_state.get("predictions", []))
        if final_state.get("final_report") is not None and final_state.get("selected_cluster") is not None:
            self.store.save_report(
                PublishedReport(
                    report_id=uuid4().hex[:12],
                    run_id=run_id,
                    cluster_id=final_state["selected_cluster"]["cluster_id"]
                    if isinstance(final_state["selected_cluster"], dict)
                    else final_state["selected_cluster"].cluster_id,
                    publication_status=final_state["final_report"]["publication_status"]
                    if isinstance(final_state["final_report"], dict)
                    else final_state["final_report"].publication_status,
                    published_at=datetime.now(UTC),
                    report=final_state["final_report"],
                    diagnostics=final_state.get("diagnostics", {}),
                )
            )
        return {
            "run_id": run_id,
            "scenario_id": initial_state.get("scenario_id"),
            "run_dir": str(run_dir),
            "final_state": final_state,
        }

    def _parse_time(self, value: str | None) -> datetime | None:
        return datetime.fromisoformat(value) if value else None

    def _summarize_outcomes(self, outcomes: list[OutcomeRecord]) -> dict[str, int]:
        counts = {"confirmed": 0, "partial": 0, "unconfirmed": 0}
        for item in outcomes:
            if item.outcome_status in counts:
                counts[item.outcome_status] += 1
        return counts

    def _resolve_run_dir(self, run_id: str) -> Path | None:
        candidates = list(self.output_dir.glob(f"*/{run_id}"))
        if candidates:
            return candidates[0]
        return None

    def _persist_outcomes(self, *, run_id: str, outcomes: list[OutcomeRecord], summary: dict[str, int]) -> None:
        run_dir = self._resolve_run_dir(run_id)
        if run_dir is None:
            return
        write_json(run_dir / "outcomes.json", {"run_id": run_id, "summary": summary, "outcomes": outcomes})
        write_text(run_dir / "outcomes.md", render_outcome_markdown(run_id=run_id, outcomes=outcomes, summary=summary))


def default_goldset() -> list[str]:
    return SampleScenarioRepository().scenario_ids()
