from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from faultline.evaluation.rubric import evaluate_report
from faultline.graph.review import build_review_steps, coerce_review_session
from faultline.graph.workflow import WORKFLOW_NODE_ORDER, StrategicSwarmWorkflow
from faultline.intake import TopicChatIntake
from faultline.models import (
    ActionRecommendation,
    ChatIntakeSession,
    EventCluster,
    FinalReport,
    MarketImplication,
    NodeReviewSession,
    OperatorPolicyConfig,
    OutcomeRecord,
    PortfolioPosition,
    Prediction,
    PublishedReport,
    RawSignal,
    ResearchBrief,
    SituationSnapshot,
    TopicPrompt,
    WatchlistEntry,
)
from faultline.persistence.store import SignalStore
from faultline.prediction import OutcomeEvaluator
from faultline.providers.base import SignalProvider
from faultline.providers.live import WebSearchEnricher
from faultline.providers.registry import build_live_providers
from faultline.providers.sample import SampleScenarioRepository
from faultline.synthesis.report_builder import render_markdown, render_outcome_markdown
from faultline.utils.env import bootstrap_env
from faultline.utils.io import ensure_directory, serialize_model, write_json, write_text

REVIEW_CHECKPOINTER = MemorySaver(
    serde=JsonPlusSerializer(
        pickle_fallback=True,
        allowed_msgpack_modules=True,
    )
)


class StrategicSwarmRunner:
    def __init__(
        self,
        output_dir: str | Path | None = None,
        db_path: str | Path | None = None,
        database_url: str | None = None,
        live_providers: list[SignalProvider] | None = None,
        web_search_provider: WebSearchEnricher | None = None,
        topic_chat_intake: TopicChatIntake | None = None,
    ) -> None:
        bootstrap_env()
        self.output_dir = ensure_directory(Path(output_dir or os.getenv("FAULTLINE_OUTPUT_DIR", "outputs")))
        self.database_url = database_url or os.getenv(
            "FAULTLINE_DATABASE_URL",
            str(Path(db_path or self.output_dir / "swarm_runs.sqlite")),
        )
        self.store = SignalStore(self.database_url)
        self.live_providers = live_providers or build_live_providers()
        self.web_search_provider = web_search_provider or WebSearchEnricher()
        self.topic_chat_intake = topic_chat_intake or TopicChatIntake()
        self.workflow_engine = StrategicSwarmWorkflow(
            store=self.store,
            live_providers=self.live_providers,
            web_search_provider=self.web_search_provider,
        )
        self.workflow = self.workflow_engine.build()
        self.review_workflow = self.workflow_engine.build(
            checkpointer=REVIEW_CHECKPOINTER,
            interrupt_after=list(WORKFLOW_NODE_ORDER),
        )
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

    def prepare_topic_chat(
        self,
        topic: str,
        *,
        thesis: str | None = None,
        portfolio_positions: list[PortfolioPosition | dict] | None = None,
        watchlist: list[WatchlistEntry | dict] | None = None,
    ) -> ChatIntakeSession:
        return self.topic_chat_intake.start_session(
            topic,
            thesis=thesis,
            portfolio_positions=portfolio_positions,
            watchlist=watchlist,
        )

    def continue_topic_chat(
        self,
        session: ChatIntakeSession | dict,
        answer: str,
    ) -> ChatIntakeSession:
        return self.topic_chat_intake.answer_question(session, answer)

    def run_topic_chat(
        self,
        session: ChatIntakeSession | dict,
        *,
        operator_policy_config: OperatorPolicyConfig | dict | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> dict:
        intake_session = self._coerce_topic_session(session)
        if not self.topic_chat_intake.is_ready(intake_session):
            raise ValueError(intake_session.current_question or "Topic chat is not ready to run.")
        return self._run(
            initial_state=self._topic_chat_initial_state(
                intake_session,
                operator_policy_config=operator_policy_config,
                start_at=start_at,
                end_at=end_at,
            )
        )

    def start_review_session(
        self,
        *,
        mode: str,
        scenario: str | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        lookback_minutes: int | None = None,
        run_id: str | None = None,
        topic_session: ChatIntakeSession | dict | None = None,
        operator_policy_config: OperatorPolicyConfig | dict | None = None,
    ) -> NodeReviewSession:
        initial_state = self._initial_state_for_mode(
            mode=mode,
            scenario=scenario,
            start_at=start_at,
            end_at=end_at,
            lookback_minutes=lookback_minutes,
            run_id=run_id,
            topic_session=topic_session,
            operator_policy_config=operator_policy_config,
        )
        return self._start_review_session(initial_state)

    def load_review_session(self, session: NodeReviewSession | dict[str, Any]) -> NodeReviewSession:
        current = coerce_review_session(session)
        current.steps = build_review_steps(current)
        return current

    def apply_review_edits(
        self,
        session: NodeReviewSession | dict[str, Any],
        *,
        edits: dict[str, Any],
    ) -> NodeReviewSession:
        current = coerce_review_session(session)
        node_id = current.current_node_id
        if node_id is None:
            raise ValueError("Review session is already complete.")
        config = self._review_config(current)
        graph_state = self.review_workflow.get_state(config).values
        updates = self._review_node_updates(node_id, graph_state, edits)
        self.review_workflow.update_state(config, updates, as_node=node_id)
        current.state_snapshots[-1] = serialize_model(self.review_workflow.get_state(config).values)
        return self.load_review_session(current)

    def approve_review_step(self, session: NodeReviewSession | dict[str, Any]) -> NodeReviewSession:
        current = coerce_review_session(session)
        node_id = current.current_node_id
        if node_id is None:
            return current
        if node_id not in current.approved_nodes:
            current.approved_nodes.append(node_id)
        config = self._review_config(current)

        if node_id == WORKFLOW_NODE_ORDER[-1]:
            final_state = self.review_workflow.get_state(config).values
            return self._finalize_review_session(current, final_state)

        list(self.review_workflow.stream(None, config=config))
        current.state_snapshots.append(serialize_model(self.review_workflow.get_state(config).values))
        current.current_node_id = self._current_node_id_from_snapshots(current)
        return self.load_review_session(current)

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
            current_run_id = item["run_id"]
            predictions = self.store.load_predictions_for_run(current_run_id)
            if not predictions:
                continue
            outcomes = self.outcome_evaluator.score(predictions, signals)
            self.store.save_outcome_records(run_id=current_run_id, outcomes=outcomes)
            summary = self._summarize_outcomes(outcomes)
            self._persist_outcomes(run_id=current_run_id, outcomes=outcomes, summary=summary)
            processed_runs.append(
                {
                    "run_id": current_run_id,
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
        for provider in self.live_providers:
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

    def _run(self, *, initial_state: dict[str, Any]) -> dict:
        session = self._start_review_session(initial_state)
        while session.status != "completed":
            session = self.approve_review_step(session)
        return {
            "run_id": session.selected_run_id,
            "scenario_id": session.scenario_id,
            "run_dir": session.selected_run_dir,
            "final_state": self._restore_runtime_state(session.final_state),
        }

    def _start_review_session(self, initial_state: dict[str, Any]) -> NodeReviewSession:
        session_id = uuid4().hex[:12]
        thread_id = f"review-{session_id}"
        normalized_state = self._normalize_initial_state(initial_state, run_id=session_id)
        config = {"configurable": {"thread_id": thread_id}}
        list(self.review_workflow.stream(normalized_state, config=config))
        session = NodeReviewSession(
            session_id=session_id,
            thread_id=thread_id,
            run_mode=normalized_state.get("run_mode", "live"),
            scenario_id=normalized_state.get("scenario_id"),
            window_start=normalized_state.get("window_start"),
            window_end=normalized_state.get("window_end"),
            topic_prompt=normalized_state.get("topic_prompt"),
            research_brief=normalized_state.get("research_brief"),
            chat_intake_session=normalized_state.get("chat_intake_session"),
            current_node_id=WORKFLOW_NODE_ORDER[0],
            state_snapshots=[
                serialize_model(normalized_state),
                serialize_model(self.review_workflow.get_state(config).values),
            ],
            diagnostics={"run_id": session_id},
        )
        session.steps = build_review_steps(session)
        return session

    def _initial_state_for_mode(
        self,
        *,
        mode: str,
        scenario: str | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        lookback_minutes: int | None = None,
        run_id: str | None = None,
        topic_session: ChatIntakeSession | dict | None = None,
        operator_policy_config: OperatorPolicyConfig | dict | None = None,
    ) -> dict[str, Any]:
        if mode == "demo":
            if not scenario:
                raise ValueError("Scenario is required for demo mode.")
            return {
                "scenario_id": scenario,
                "run_mode": "demo",
                "operator_policy_config": operator_policy_config,
            }
        if mode == "topic_chat":
            if not topic_session:
                raise ValueError("Topic chat mode requires a prepared topic session.")
            return self._topic_chat_initial_state(
                self._coerce_topic_session(topic_session),
                operator_policy_config=operator_policy_config,
                start_at=start_at,
                end_at=end_at,
            )
        if mode == "live":
            if not start_at or not end_at:
                raise ValueError("Live mode requires start_at and end_at.")
            return {
                "run_mode": "live",
                "window_start": start_at.isoformat(),
                "window_end": end_at.isoformat(),
                "operator_policy_config": operator_policy_config,
            }
        if mode == "latest":
            lookback = lookback_minutes or int(os.getenv("FAULTLINE_DEFAULT_LOOKBACK_MINUTES", "60"))
            resolved_end = datetime.now(UTC)
            resolved_start = resolved_end - timedelta(minutes=lookback)
            return {
                "run_mode": "live",
                "window_start": resolved_start.isoformat(),
                "window_end": resolved_end.isoformat(),
                "operator_policy_config": operator_policy_config,
            }
        if mode == "replay":
            if run_id:
                previous = self.store.get_run_state(run_id)
                if not previous:
                    raise ValueError(f"Unknown run_id: {run_id}")
                return {"run_mode": "replay", "raw_signals": previous.get("raw_signals", [])}
            if not start_at or not end_at:
                raise ValueError("Replay mode requires run_id or start_at/end_at.")
            return {
                "run_mode": "replay",
                "window_start": start_at.isoformat(),
                "window_end": end_at.isoformat(),
                "raw_signals": self.store.load_raw_signals_for_window(start_at, end_at),
            }
        raise ValueError(f"Unsupported review mode: {mode}")

    def _normalize_initial_state(self, initial_state: dict[str, Any], *, run_id: str) -> dict[str, Any]:
        normalized = dict(initial_state)
        if "raw_signals" in normalized:
            normalized["raw_signals"] = [
                signal if isinstance(signal, RawSignal) else RawSignal.model_validate(signal)
                for signal in normalized["raw_signals"]
            ]
        normalized["portfolio_positions"] = [
            item if isinstance(item, PortfolioPosition) else PortfolioPosition.model_validate(item)
            for item in normalized.get("portfolio_positions", [])
        ]
        normalized["watchlist"] = [
            item if isinstance(item, WatchlistEntry) else WatchlistEntry.model_validate(item)
            for item in normalized.get("watchlist", [])
        ]
        if normalized.get("operator_policy_config") is not None and not isinstance(
            normalized["operator_policy_config"], OperatorPolicyConfig
        ):
            normalized["operator_policy_config"] = OperatorPolicyConfig.model_validate(
                normalized["operator_policy_config"]
            )
        if normalized.get("topic_prompt") is not None and not isinstance(normalized["topic_prompt"], TopicPrompt):
            normalized["topic_prompt"] = TopicPrompt.model_validate(normalized["topic_prompt"])
        if normalized.get("research_brief") is not None and not isinstance(normalized["research_brief"], ResearchBrief):
            normalized["research_brief"] = ResearchBrief.model_validate(normalized["research_brief"])
        if normalized.get("chat_intake_session") is not None and not isinstance(
            normalized["chat_intake_session"], ChatIntakeSession
        ):
            normalized["chat_intake_session"] = ChatIntakeSession.model_validate(normalized["chat_intake_session"])
        normalized["diagnostics"] = {**normalized.get("diagnostics", {}), "run_id": run_id}
        return normalized

    def _coerce_topic_session(self, session: ChatIntakeSession | dict[str, Any]) -> ChatIntakeSession:
        return session if isinstance(session, ChatIntakeSession) else ChatIntakeSession.model_validate(session)

    def _topic_chat_initial_state(
        self,
        session: ChatIntakeSession,
        *,
        operator_policy_config: OperatorPolicyConfig | dict | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> dict[str, Any]:
        resolved_start, resolved_end = self._resolve_topic_chat_window(start_at=start_at, end_at=end_at)
        brief = session.brief
        return {
            "run_mode": "topic_chat",
            "window_start": resolved_start.isoformat(),
            "window_end": resolved_end.isoformat(),
            "portfolio_positions": brief.positions,
            "watchlist": brief.watchlist,
            "operator_policy_config": operator_policy_config,
            "topic_prompt": session.topic_prompt,
            "research_brief": brief,
            "chat_intake_session": session,
            "retrieval_questions": self.topic_chat_intake.build_retrieval_questions(brief),
        }

    def _resolve_topic_chat_window(
        self,
        *,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> tuple[datetime, datetime]:
        default_start, default_end = self.topic_chat_intake.default_window()
        return start_at or default_start, end_at or default_end

    def _review_config(self, session: NodeReviewSession) -> dict[str, Any]:
        return {"configurable": {"thread_id": session.thread_id}}

    def _current_node_id_from_snapshots(self, session: NodeReviewSession) -> str | None:
        index = len(session.state_snapshots) - 2
        if session.status == "completed" or index < 0 or index >= len(WORKFLOW_NODE_ORDER):
            return None
        return WORKFLOW_NODE_ORDER[index]

    def _review_node_updates(self, node_id: str, graph_state: dict[str, Any], edits: dict[str, Any]) -> dict[str, Any]:
        if node_id == "normalize_events":
            working_state = {
                **graph_state,
                "excluded_signal_ids": edits.get("excluded_signal_ids", graph_state.get("excluded_signal_ids", [])),
            }
            updates = self.workflow_engine.normalize_events(working_state)
            selected_cluster_id = edits.get("selected_cluster_id")
            if selected_cluster_id:
                selected_cluster = next(
                    (
                        cluster
                        for cluster in updates.get("event_clusters", [])
                        if cluster.cluster_id == selected_cluster_id
                    ),
                    None,
                )
                if selected_cluster is not None:
                    updates["selected_cluster"] = selected_cluster
            return updates
        if node_id == "map_situation":
            snapshot = graph_state.get("situation_snapshot")
            if snapshot is None:
                return {}
            validated = (
                snapshot if isinstance(snapshot, SituationSnapshot) else SituationSnapshot.model_validate(snapshot)
            )
            return {
                "situation_snapshot": validated.model_copy(
                    update={
                        "title": edits.get("title", validated.title),
                        "summary": edits.get("summary", validated.summary),
                        "system_under_pressure": edits.get(
                            "system_under_pressure",
                            validated.system_under_pressure,
                        ),
                    }
                )
            }
        if node_id == "map_market_implications":
            return {
                "market_implications": [
                    item if isinstance(item, MarketImplication) else MarketImplication.model_validate(item)
                    for item in edits.get("market_implications", graph_state.get("market_implications", []))
                ]
            }
        if node_id == "generate_actions":
            return {
                "action_recommendations": [
                    item if isinstance(item, ActionRecommendation) else ActionRecommendation.model_validate(item)
                    for item in edits.get("action_recommendations", graph_state.get("action_recommendations", []))
                ],
                "exit_signals": [
                    item if isinstance(item, ActionRecommendation) else ActionRecommendation.model_validate(item)
                    for item in edits.get("exit_signals", graph_state.get("exit_signals", []))
                ],
            }
        if node_id == "synthesize_report":
            report = graph_state.get("final_report")
            if report is None:
                return {}
            validated = report if isinstance(report, FinalReport) else FinalReport.model_validate(report)
            return {
                "final_report": validated.model_copy(
                    update={
                        "headline": edits.get("headline", validated.headline),
                        "executive_summary": edits.get("executive_summary", validated.executive_summary),
                    }
                )
            }
        return {}

    def _finalize_review_session(
        self,
        session: NodeReviewSession,
        final_state: dict[str, Any],
    ) -> NodeReviewSession:
        session.status = "completed"
        session.current_node_id = None
        session.final_state = serialize_model(final_state)
        session.steps = build_review_steps(session)
        run_payload = self._persist_review_run(session, final_state)
        session.selected_run_id = run_payload["run_id"]
        session.selected_run_dir = run_payload["run_dir"]
        return session

    def _persist_review_run(self, session: NodeReviewSession, final_state: dict[str, Any]) -> dict[str, Any]:
        run_id = session.session_id
        scenario_label = session.scenario_id or session.run_mode
        run_dir = ensure_directory(self.output_dir / scenario_label / run_id)
        serialized_final_state = serialize_model(final_state)
        trace_payload = {
            "steps": [step.model_dump(mode="json") for step in session.steps],
            "snapshots": session.state_snapshots,
        }
        write_json(run_dir / "state.json", serialized_final_state)
        write_json(run_dir / "trace.json", trace_payload)
        if serialized_final_state.get("final_report") is not None:
            write_json(run_dir / "report.json", serialized_final_state["final_report"])
            write_text(run_dir / "report.md", render_markdown(final_state["final_report"]))
        self.store.save_run(
            run_id=run_id,
            scenario_id=session.scenario_id,
            run_mode=session.run_mode,
            window_start=self._parse_time(session.window_start),
            window_end=self._parse_time(session.window_end),
            publish_decision=serialized_final_state.get("diagnostics", {}).get("publish_decision", "monitor_only"),
            diagnostics=serialized_final_state.get("diagnostics", {}),
            final_state=serialized_final_state,
            trace=trace_payload["steps"],
        )
        self.store.save_predictions(run_id=run_id, predictions=final_state.get("predictions", []))
        selected_cluster = final_state.get("selected_cluster")
        report = final_state.get("final_report")
        if report is not None and selected_cluster is not None:
            self.store.save_report(
                PublishedReport(
                    report_id=uuid4().hex[:12],
                    run_id=run_id,
                    cluster_id=selected_cluster.cluster_id
                    if hasattr(selected_cluster, "cluster_id")
                    else selected_cluster["cluster_id"],
                    publication_status=report.publication_status
                    if hasattr(report, "publication_status")
                    else report["publication_status"],
                    published_at=datetime.now(UTC),
                    report=report,
                    diagnostics=serialized_final_state.get("diagnostics", {}),
                )
            )
        return {
            "run_id": run_id,
            "run_dir": str(run_dir),
            "final_state": serialized_final_state,
        }

    def _restore_runtime_state(self, payload: dict[str, Any]) -> dict[str, Any]:
        restored = dict(payload)
        if restored.get("topic_prompt") is not None:
            restored["topic_prompt"] = TopicPrompt.model_validate(restored["topic_prompt"])
        if restored.get("research_brief") is not None:
            restored["research_brief"] = ResearchBrief.model_validate(restored["research_brief"])
        if restored.get("chat_intake_session") is not None:
            restored["chat_intake_session"] = ChatIntakeSession.model_validate(restored["chat_intake_session"])
        if restored.get("final_report") is not None:
            restored["final_report"] = FinalReport.model_validate(restored["final_report"])
        if restored.get("selected_cluster") is not None:
            restored["selected_cluster"] = EventCluster.model_validate(restored["selected_cluster"])
        if restored.get("predictions"):
            restored["predictions"] = [Prediction.model_validate(item) for item in restored["predictions"]]
        if restored.get("market_implications"):
            restored["market_implications"] = [
                MarketImplication.model_validate(item) for item in restored["market_implications"]
            ]
        if restored.get("action_recommendations"):
            restored["action_recommendations"] = [
                ActionRecommendation.model_validate(item) for item in restored["action_recommendations"]
            ]
        if restored.get("exit_signals"):
            restored["exit_signals"] = [ActionRecommendation.model_validate(item) for item in restored["exit_signals"]]
        return restored

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
