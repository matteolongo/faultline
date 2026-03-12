from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from faultline.evaluation.rubric import evaluate_report
from faultline.graph.workflow import StrategicSwarmWorkflow
from faultline.intake import TopicChatIntake
from faultline.models import (
    ActionRecommendation,
    BriefCheckpoint,
    ChatIntakeSession,
    EventCluster,
    EvidenceCheckpoint,
    FinalReport,
    ImplicationsCheckpoint,
    MarketImplication,
    OperatorPolicyConfig,
    OperatorWorkspaceSession,
    OutcomeRecord,
    PortfolioPosition,
    Prediction,
    PublishedReport,
    RawSignal,
    ReportCheckpoint,
    ResearchBrief,
    SituationCheckpoint,
    TopicPrompt,
    WatchlistEntry,
)
from faultline.persistence.store import SignalStore, make_dead_letter
from faultline.prediction import OutcomeEvaluator
from faultline.providers.base import ProviderError
from faultline.providers.live import WebSearchEnricher
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
        live_providers: list | None = None,
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
        self.workflow_engine = StrategicSwarmWorkflow(store=self.store, live_providers=self.live_providers)
        self.workflow = self.workflow_engine.build()
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

    def initialize_workspace(
        self,
        session: ChatIntakeSession | dict,
        *,
        operator_policy_config: OperatorPolicyConfig | dict | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> OperatorWorkspaceSession:
        intake_session = (
            session if isinstance(session, ChatIntakeSession) else ChatIntakeSession.model_validate(session)
        )
        policy = (
            operator_policy_config
            if isinstance(operator_policy_config, OperatorPolicyConfig) or operator_policy_config is None
            else OperatorPolicyConfig.model_validate(operator_policy_config)
        )
        return OperatorWorkspaceSession(
            workspace_id=uuid4().hex[:12],
            current_stage="brief",
            window_start=start_at.isoformat() if start_at else None,
            window_end=end_at.isoformat() if end_at else None,
            operator_policy_config=policy,
            brief_checkpoint=BriefCheckpoint(
                status="generated",
                topic_prompt=intake_session.topic_prompt,
                chat_intake_session=intake_session,
                computed_brief=intake_session.brief,
                diagnostics={"brief_status": intake_session.status},
                provenance=[f"Initialized workspace from topic '{intake_session.topic_prompt.topic}'."],
            ),
        )

    def apply_brief_edits(
        self,
        workspace: OperatorWorkspaceSession | dict,
        brief: ResearchBrief | dict,
    ) -> OperatorWorkspaceSession:
        session = self._coerce_workspace(workspace)
        updated = brief if isinstance(brief, ResearchBrief) else ResearchBrief.model_validate(brief)
        session.brief_checkpoint.computed_brief = updated
        session.brief_checkpoint.approved_brief = None
        session.brief_checkpoint.status = "generated"
        session.current_stage = "brief"
        return self._mark_downstream_stale(session, "brief")

    def apply_evidence_edits(
        self,
        workspace: OperatorWorkspaceSession | dict,
        *,
        retrieval_questions: list[str],
        excluded_signal_ids: list[str],
        selected_cluster_id: str | None,
    ) -> OperatorWorkspaceSession:
        session = self._coerce_workspace(workspace)
        session.evidence_checkpoint.retrieval_questions = retrieval_questions
        session.evidence_checkpoint.excluded_signal_ids = excluded_signal_ids
        session.evidence_checkpoint.selected_cluster_id = selected_cluster_id
        session.evidence_checkpoint.approved_cluster_id = None
        session.evidence_checkpoint.status = "generated"
        session.current_stage = "evidence"
        return self._mark_downstream_stale(session, "evidence")

    def apply_situation_edits(
        self,
        workspace: OperatorWorkspaceSession | dict,
        *,
        title: str,
        summary: str,
        system_under_pressure: str,
    ) -> OperatorWorkspaceSession:
        session = self._coerce_workspace(workspace)
        snapshot = session.situation_checkpoint.situation_snapshot
        if snapshot is None:
            raise ValueError("Situation checkpoint is not available.")
        snapshot.title = title
        snapshot.summary = summary
        snapshot.system_under_pressure = system_under_pressure
        session.situation_checkpoint.status = "generated"
        session.current_stage = "situation"
        return self._mark_downstream_stale(session, "situation")

    def apply_implication_edits(
        self,
        workspace: OperatorWorkspaceSession | dict,
        *,
        implications: list[dict] | list,
        actions: list[dict] | list,
    ) -> OperatorWorkspaceSession:
        session = self._coerce_workspace(workspace)
        session.implications_checkpoint.market_implications = [
            item if isinstance(item, MarketImplication) else MarketImplication.model_validate(item)
            for item in implications
        ]
        session.implications_checkpoint.action_recommendations = [
            item if isinstance(item, ActionRecommendation) else ActionRecommendation.model_validate(item)
            for item in actions
        ]
        session.implications_checkpoint.status = "generated"
        session.current_stage = "implications"
        return self._mark_downstream_stale(session, "implications")

    def apply_report_edits(
        self,
        workspace: OperatorWorkspaceSession | dict,
        *,
        headline: str,
        executive_summary: str,
    ) -> OperatorWorkspaceSession:
        session = self._coerce_workspace(workspace)
        report = session.report_checkpoint.final_report
        if report is None:
            raise ValueError("Report checkpoint is not available.")
        report.headline = headline
        report.executive_summary = executive_summary
        session.report_checkpoint.report_markdown = render_markdown(report)
        session.report_checkpoint.status = "generated"
        session.current_stage = "report"
        return session

    def build_evidence_checkpoint(
        self,
        workspace: OperatorWorkspaceSession | dict,
        *,
        retrieval_questions: list[str] | None = None,
        excluded_signal_ids: list[str] | None = None,
        selected_cluster_id: str | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> OperatorWorkspaceSession:
        session = self._coerce_workspace(workspace)
        brief = self._effective_brief(session)
        if brief is None:
            raise ValueError("Brief checkpoint must exist before evidence generation.")
        start_at, end_at = self._resolve_workspace_window(session, start_at=start_at, end_at=end_at)
        questions = (
            retrieval_questions
            or session.evidence_checkpoint.retrieval_questions
            or self.topic_chat_intake.build_retrieval_questions(brief)
        )
        excluded_ids = excluded_signal_ids or session.evidence_checkpoint.excluded_signal_ids
        raw_signals, provider_counts = self._retrieve_signals_for_brief(
            brief,
            questions,
            start_at=start_at,
            end_at=end_at,
        )
        filtered_signals = [item for item in raw_signals if item.id not in set(excluded_ids)]
        events, clusters, normalize_diag = self.workflow_engine.normalizer.normalize(
            filtered_signals,
            known_dedupe_hashes=set(),
            prior_story_counts={},
        )
        selected_id = selected_cluster_id or session.evidence_checkpoint.selected_cluster_id
        valid_cluster_ids = {item.cluster_id for item in clusters}
        if selected_id and selected_id not in valid_cluster_ids:
            selected_id = None
        if not selected_id and clusters:
            selected_id = clusters[0].cluster_id
        session.evidence_checkpoint = EvidenceCheckpoint(
            status="generated",
            retrieval_questions=questions,
            raw_signals=raw_signals,
            normalized_events=events,
            candidate_clusters=clusters,
            selected_cluster_id=selected_id,
            approved_cluster_id=session.evidence_checkpoint.approved_cluster_id,
            excluded_signal_ids=excluded_ids,
            included_signal_ids=[item.id for item in filtered_signals],
            diagnostics={
                "source_counts": provider_counts,
                "cluster_count": len(clusters),
                "edited_retrieval_question_count": len(questions),
                "included_signal_count": len(filtered_signals),
                "excluded_signal_count": len(excluded_ids),
                **normalize_diag,
            },
            provenance=[
                f"Generated {len(questions)} retrieval questions.",
                f"Retained {len(filtered_signals)} of {len(raw_signals)} raw signals after exclusions.",
                f"Built {len(clusters)} candidate clusters.",
            ],
        )
        session.current_stage = "evidence"
        return self._mark_downstream_stale(session, "evidence")

    def build_situation_checkpoint(
        self,
        workspace: OperatorWorkspaceSession | dict,
    ) -> OperatorWorkspaceSession:
        session = self._coerce_workspace(workspace)
        cluster = self._selected_cluster(session.evidence_checkpoint)
        if cluster is None:
            raise ValueError("Evidence checkpoint must select a cluster before situation generation.")
        calibration_signals = self.store.load_calibration_signals()
        related_situations = self.workflow_engine.memory.search(cluster, exclude_id=cluster.cluster_id)
        cluster_events = [item for item in session.evidence_checkpoint.normalized_events if item.cluster_id == cluster.cluster_id]
        snapshot = self.workflow_engine.mapper.map(cluster, cluster_events, related_situations)
        predictions, scenario_tree, warnings = self.workflow_engine.prediction_engine.predict(
            snapshot,
            cluster,
            calibration_signals,
        )
        session.situation_checkpoint = SituationCheckpoint(
            status="generated",
            related_situations=related_situations,
            calibration_signals=calibration_signals,
            situation_snapshot=snapshot,
            predictions=predictions,
            scenario_tree=scenario_tree,
            stage_transition_warnings=warnings,
            diagnostics={
                "related_situation_count": len(related_situations),
                "calibration_signal_count": len(calibration_signals),
                "prediction_count": len(predictions),
            },
            provenance=[
                f"Selected cluster {cluster.cluster_id}.",
                f"Mapped situation {snapshot.title}.",
                f"Generated {len(predictions)} predictions and {len(warnings)} warnings.",
            ],
        )
        session.current_stage = "situation"
        return self._mark_downstream_stale(session, "situation")

    def build_implications_checkpoint(
        self,
        workspace: OperatorWorkspaceSession | dict,
    ) -> OperatorWorkspaceSession:
        session = self._coerce_workspace(workspace)
        cluster = self._selected_cluster(session.evidence_checkpoint)
        brief = self._effective_brief(session)
        if cluster is None or brief is None or session.situation_checkpoint.situation_snapshot is None:
            raise ValueError("Situation checkpoint must exist before implications generation.")
        implications = self.workflow_engine.market_mapper.map(
            session.situation_checkpoint.situation_snapshot,
            session.situation_checkpoint.predictions,
            cluster,
            session.situation_checkpoint.calibration_signals,
        )
        actions, exits, endangered = self.workflow_engine.action_engine.generate(
            session.situation_checkpoint.situation_snapshot,
            implications,
            session.situation_checkpoint.predictions,
            session.situation_checkpoint.calibration_signals,
            brief.positions,
            brief.watchlist,
            session.situation_checkpoint.stage_transition_warnings,
            session.operator_policy_config,
        )
        session.implications_checkpoint = ImplicationsCheckpoint(
            status="generated",
            market_implications=implications,
            action_recommendations=actions,
            exit_signals=exits,
            endangered_symbols=endangered,
            diagnostics={
                "market_implication_count": len(implications),
                "action_count": len(actions),
                "exit_count": len(exits),
            },
            provenance=[
                f"Mapped {len(implications)} market implications.",
                f"Generated {len(actions)} actions and {len(exits)} exits.",
            ],
        )
        session.current_stage = "implications"
        return self._mark_downstream_stale(session, "implications")

    def build_report_checkpoint(
        self,
        workspace: OperatorWorkspaceSession | dict,
    ) -> OperatorWorkspaceSession:
        session = self._coerce_workspace(workspace)
        cluster = self._selected_cluster(session.evidence_checkpoint)
        brief = self._effective_brief(session)
        if cluster is None or brief is None or session.situation_checkpoint.situation_snapshot is None:
            raise ValueError("Implications checkpoint must exist before report generation.")
        report = self.workflow_engine.report_builder.build(
            snapshot=session.situation_checkpoint.situation_snapshot,
            cluster=cluster,
            related_situations=session.situation_checkpoint.related_situations,
            calibration_signals=session.situation_checkpoint.calibration_signals,
            predictions=session.situation_checkpoint.predictions,
            scenario_tree=session.situation_checkpoint.scenario_tree,
            stage_transition_warnings=session.situation_checkpoint.stage_transition_warnings,
            implications=session.implications_checkpoint.market_implications,
            actions=session.implications_checkpoint.action_recommendations,
            exits=session.implications_checkpoint.exit_signals,
            endangered_symbols=session.implications_checkpoint.endangered_symbols,
            provenance=self._workspace_provenance(session),
            topic_prompt=session.brief_checkpoint.topic_prompt,
            research_brief=brief,
            retrieval_questions=session.evidence_checkpoint.retrieval_questions,
        )
        run_payload = self._persist_workspace_run(session, report)
        session.report_checkpoint = ReportCheckpoint(
            status="generated",
            final_report=report,
            report_markdown=render_markdown(report),
            run_id=run_payload["run_id"],
            run_dir=run_payload["run_dir"],
            diagnostics=run_payload["final_state"].get("diagnostics", {}),
            provenance=report.provenance,
        )
        session.selected_run_id = run_payload["run_id"]
        session.selected_run_dir = run_payload["run_dir"]
        session.current_stage = "report"
        return session

    def rerun_from_checkpoint(
        self,
        workspace: OperatorWorkspaceSession | dict,
        checkpoint: str,
    ) -> OperatorWorkspaceSession:
        session = self._coerce_workspace(workspace)
        session.rerun_lineage.append(f"rerun_from:{checkpoint}")
        if checkpoint == "brief":
            session = self.build_evidence_checkpoint(session)
            session = self.build_situation_checkpoint(session)
            session = self.build_implications_checkpoint(session)
            return self.build_report_checkpoint(session)
        if checkpoint == "evidence":
            session = self.build_situation_checkpoint(session)
            session = self.build_implications_checkpoint(session)
            return self.build_report_checkpoint(session)
        if checkpoint == "situation":
            session = self.build_implications_checkpoint(session)
            return self.build_report_checkpoint(session)
        if checkpoint in {"implications", "report"}:
            return self.build_report_checkpoint(session)
        raise ValueError(f"Unsupported checkpoint: {checkpoint}")

    def run_topic_chat(
        self,
        session: ChatIntakeSession | dict,
        *,
        operator_policy_config: OperatorPolicyConfig | dict | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> dict:
        intake_session = (
            session if isinstance(session, ChatIntakeSession) else ChatIntakeSession.model_validate(session)
        )
        if not self.topic_chat_intake.is_ready(intake_session):
            raise ValueError(intake_session.current_question or "Topic chat is not ready to run.")
        workspace = self.initialize_workspace(
            intake_session,
            operator_policy_config=operator_policy_config,
            start_at=start_at,
            end_at=end_at,
        )
        workspace.brief_checkpoint.status = "approved"
        workspace.brief_checkpoint.approved_brief = intake_session.brief
        workspace = self.build_evidence_checkpoint(workspace, start_at=start_at, end_at=end_at)
        workspace.evidence_checkpoint.status = "approved"
        workspace.evidence_checkpoint.approved_cluster_id = workspace.evidence_checkpoint.selected_cluster_id
        workspace = self.build_situation_checkpoint(workspace)
        workspace.situation_checkpoint.status = "approved"
        workspace = self.build_implications_checkpoint(workspace)
        workspace.implications_checkpoint.status = "approved"
        workspace = self.build_report_checkpoint(workspace)
        workspace.report_checkpoint.status = "approved"
        return {
            "run_id": workspace.report_checkpoint.run_id,
            "scenario_id": None,
            "run_dir": workspace.report_checkpoint.run_dir,
            "final_state": self._workspace_final_state(workspace),
        }

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

    def _coerce_workspace(self, workspace: OperatorWorkspaceSession | dict) -> OperatorWorkspaceSession:
        return workspace if isinstance(workspace, OperatorWorkspaceSession) else OperatorWorkspaceSession.model_validate(workspace)

    def _effective_brief(self, workspace: OperatorWorkspaceSession) -> ResearchBrief | None:
        return workspace.brief_checkpoint.approved_brief or workspace.brief_checkpoint.computed_brief

    def _resolve_workspace_window(
        self,
        workspace: OperatorWorkspaceSession,
        *,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> tuple[datetime, datetime]:
        default_start, default_end = self.topic_chat_intake.default_window()
        resolved_start = (
            start_at
            or (datetime.fromisoformat(workspace.window_start) if workspace.window_start else None)
            or default_start
        )
        resolved_end = (
            end_at
            or (datetime.fromisoformat(workspace.window_end) if workspace.window_end else None)
            or default_end
        )
        workspace.window_start = resolved_start.isoformat()
        workspace.window_end = resolved_end.isoformat()
        return resolved_start, resolved_end

    def _retrieve_signals_for_brief(
        self,
        brief: ResearchBrief,
        retrieval_questions: list[str],
        *,
        start_at: datetime,
        end_at: datetime,
    ) -> tuple[list[RawSignal], dict[str, int]]:
        raw_signals: list[RawSignal] = []
        provider_counts: dict[str, int] = {}
        story_key = self._topic_story_key(brief)
        synthesis_count = 0
        for question in retrieval_questions:
            try:
                fetched = self.web_search_provider.query(question, story_key=story_key, fetched_at=end_at)
                normalized = [item if isinstance(item, RawSignal) else RawSignal.model_validate(item) for item in fetched]
                raw_signals.extend(normalized)
                synthesis_count += len(normalized)
            except ProviderError as exc:
                self.store.save_dead_letter(
                    make_dead_letter(
                        provider_name=self.web_search_provider.provider_name,
                        window_start=start_at,
                        window_end=end_at,
                        error_type="provider_error",
                        error_message=str(exc),
                    )
                )
        provider_counts[self.web_search_provider.provider_name] = synthesis_count
        for provider in self.live_providers:
            if getattr(provider, "source_family", "") not in {"market", "macro"}:
                continue
            try:
                fetched = provider.fetch_window(start_at, end_at)
                normalized = [item if isinstance(item, RawSignal) else RawSignal.model_validate(item) for item in fetched]
                raw_signals.extend(normalized)
                provider_counts[provider.provider_name] = len(normalized)
            except ProviderError as exc:
                self.store.save_dead_letter(
                    make_dead_letter(
                        provider_name=provider.provider_name,
                        window_start=start_at,
                        window_end=end_at,
                        error_type="provider_error",
                        error_message=str(exc),
                    )
                )
                provider_counts[provider.provider_name] = 0
        return raw_signals, provider_counts

    def _selected_cluster(self, checkpoint: EvidenceCheckpoint) -> EventCluster | None:
        target_id = checkpoint.approved_cluster_id or checkpoint.selected_cluster_id
        if not target_id:
            return None
        return next((item for item in checkpoint.candidate_clusters if item.cluster_id == target_id), None)

    def _mark_downstream_stale(self, workspace: OperatorWorkspaceSession, checkpoint: str) -> OperatorWorkspaceSession:
        order = workspace.stages
        index = order.index(checkpoint)
        for downstream in order[index + 1 :]:
            current = getattr(workspace, f"{downstream}_checkpoint")
            if current.status != "not_started":
                current.status = "stale"
        return workspace

    def _workspace_provenance(self, workspace: OperatorWorkspaceSession) -> list[str]:
        brief = self._effective_brief(workspace)
        topic = workspace.brief_checkpoint.topic_prompt.topic if workspace.brief_checkpoint.topic_prompt else "unknown topic"
        lines = [
            f"Topic chat started from '{topic}'.",
            f"Workspace stage: {workspace.current_stage}.",
        ]
        if brief is not None:
            lines.append(f"Interpreted objective: {self.topic_chat_intake.describe_brief(brief)}")
            lines.extend(f"Assumption: {item}" for item in brief.assumptions)
        lines.extend(workspace.evidence_checkpoint.provenance)
        lines.extend(workspace.situation_checkpoint.provenance)
        lines.extend(workspace.implications_checkpoint.provenance)
        if workspace.rerun_lineage:
            lines.extend(f"Rerun lineage: {item}" for item in workspace.rerun_lineage)
        return lines

    def _workspace_final_state(self, workspace: OperatorWorkspaceSession) -> dict:
        report = workspace.report_checkpoint.final_report
        situation = workspace.situation_checkpoint
        evidence = workspace.evidence_checkpoint
        diagnostics = {
            "publish_decision": report.publication_status if report is not None else "monitor_only",
            "stage": situation.situation_snapshot.stage.stage if situation.situation_snapshot is not None else None,
            "topic_prompt": workspace.brief_checkpoint.topic_prompt.topic if workspace.brief_checkpoint.topic_prompt else "",
            "deep_dive_objective": self.topic_chat_intake.describe_brief(self._effective_brief(workspace))
            if self._effective_brief(workspace)
            else "",
            "retrieval_questions": evidence.retrieval_questions,
            "intake_assumptions": self._effective_brief(workspace).assumptions if self._effective_brief(workspace) else [],
            "topic_chat_turn_count": len(workspace.brief_checkpoint.chat_intake_session.turns)
            if workspace.brief_checkpoint.chat_intake_session
            else 0,
            "checkpoint_statuses": {
                "brief": workspace.brief_checkpoint.status,
                "evidence": workspace.evidence_checkpoint.status,
                "situation": workspace.situation_checkpoint.status,
                "implications": workspace.implications_checkpoint.status,
                "report": workspace.report_checkpoint.status,
            },
            "approved_cluster_id": evidence.approved_cluster_id or evidence.selected_cluster_id,
            "edited_retrieval_question_count": len(evidence.retrieval_questions),
            "included_signal_count": len(evidence.included_signal_ids),
            "excluded_signal_count": len(evidence.excluded_signal_ids),
            "stale_downstream_flags": {
                "evidence": workspace.evidence_checkpoint.status == "stale",
                "situation": workspace.situation_checkpoint.status == "stale",
                "implications": workspace.implications_checkpoint.status == "stale",
                "report": workspace.report_checkpoint.status == "stale",
            },
            "workspace_payload": workspace.model_dump(mode="json"),
            **evidence.diagnostics,
            **situation.diagnostics,
            **workspace.implications_checkpoint.diagnostics,
        }
        return {
            "topic_prompt": workspace.brief_checkpoint.topic_prompt,
            "research_brief": self._effective_brief(workspace),
            "chat_intake_session": workspace.brief_checkpoint.chat_intake_session,
            "retrieval_questions": evidence.retrieval_questions,
            "raw_signals": evidence.raw_signals,
            "normalized_events": evidence.normalized_events,
            "event_clusters": evidence.candidate_clusters,
            "selected_cluster": self._selected_cluster(evidence),
            "related_situations": situation.related_situations,
            "calibration_signals": situation.calibration_signals,
            "situation_snapshot": situation.situation_snapshot,
            "predictions": situation.predictions,
            "scenario_tree": situation.scenario_tree,
            "stage_transition_warnings": situation.stage_transition_warnings,
            "market_implications": workspace.implications_checkpoint.market_implications,
            "action_recommendations": workspace.implications_checkpoint.action_recommendations,
            "exit_signals": workspace.implications_checkpoint.exit_signals,
            "endangered_symbols": workspace.implications_checkpoint.endangered_symbols,
            "final_report": report,
            "operator_workspace_session": workspace,
            "diagnostics": diagnostics,
            "provenance": self._workspace_provenance(workspace),
        }

    def _persist_workspace_run(self, workspace: OperatorWorkspaceSession, report: FinalReport) -> dict:
        initial_state = {
            "run_mode": "topic_chat",
            "window_start": workspace.window_start,
            "window_end": workspace.window_end,
            "portfolio_positions": self._effective_brief(workspace).positions if self._effective_brief(workspace) else [],
            "watchlist": self._effective_brief(workspace).watchlist if self._effective_brief(workspace) else [],
            "operator_policy_config": workspace.operator_policy_config,
            "topic_prompt": workspace.brief_checkpoint.topic_prompt,
            "research_brief": self._effective_brief(workspace),
            "chat_intake_session": workspace.brief_checkpoint.chat_intake_session,
            "retrieval_questions": workspace.evidence_checkpoint.retrieval_questions,
            "raw_signals": workspace.evidence_checkpoint.raw_signals,
        }
        final_state = self._workspace_final_state(workspace)
        final_state["final_report"] = report
        diagnostics = final_state["diagnostics"]
        run_id = uuid4().hex[:12]
        scenario_label = "topic_chat"
        run_dir = ensure_directory(self.output_dir / scenario_label / run_id)
        write_json(run_dir / "state.json", final_state)
        write_json(run_dir / "trace.json", [final_state])
        write_json(run_dir / "report.json", report)
        write_text(run_dir / "report.md", render_markdown(report))
        write_json(run_dir / "workspace.json", workspace)
        self.store.save_run(
            run_id=run_id,
            scenario_id=None,
            run_mode="topic_chat",
            window_start=self._parse_time(initial_state.get("window_start")),
            window_end=self._parse_time(initial_state.get("window_end")),
            publish_decision=diagnostics.get("publish_decision", "monitor_only"),
            diagnostics=diagnostics,
            final_state=serialize_model(final_state),
            trace=serialize_model([final_state]),
        )
        self.store.save_predictions(run_id=run_id, predictions=final_state.get("predictions", []))
        selected_cluster = final_state.get("selected_cluster")
        if selected_cluster is not None:
            self.store.save_report(
                PublishedReport(
                    report_id=uuid4().hex[:12],
                    run_id=run_id,
                    cluster_id=selected_cluster.cluster_id if hasattr(selected_cluster, "cluster_id") else selected_cluster["cluster_id"],
                    publication_status=report.publication_status,
                    published_at=datetime.now(UTC),
                    report=report,
                    diagnostics=diagnostics,
                )
            )
        return {
            "run_id": run_id,
            "run_dir": str(run_dir),
            "final_state": final_state,
        }

    def _run(self, *, initial_state: dict) -> dict:
        run_id = uuid4().hex[:12]
        if "raw_signals" in initial_state:
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
        if initial_state.get("topic_prompt") is not None:
            prompt = initial_state["topic_prompt"]
            initial_state["topic_prompt"] = (
                prompt if isinstance(prompt, TopicPrompt) else TopicPrompt.model_validate(prompt)
            )
        if initial_state.get("research_brief") is not None:
            brief = initial_state["research_brief"]
            initial_state["research_brief"] = (
                brief if isinstance(brief, ResearchBrief) else ResearchBrief.model_validate(brief)
            )
        if initial_state.get("chat_intake_session") is not None:
            session = initial_state["chat_intake_session"]
            initial_state["chat_intake_session"] = (
                session if isinstance(session, ChatIntakeSession) else ChatIntakeSession.model_validate(session)
            )
        initial_state = {
            **initial_state,
            "diagnostics": {"run_id": run_id, **initial_state.get("diagnostics", {})},
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

    def _topic_story_key(self, brief: ResearchBrief) -> str:
        seed = brief.normalized_topic or brief.original_topic
        return "_".join(token for token in seed.lower().replace("/", " ").split() if token)[:80] or "topic_chat"


def default_goldset() -> list[str]:
    return SampleScenarioRepository().scenario_ids()
