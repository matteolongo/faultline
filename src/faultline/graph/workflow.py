from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from langgraph.graph import END, START, StateGraph

from faultline.analysis import ActionEngine, MarketMapper, PredictionEngine, SituationMapper
from faultline.memory import SituationMemory
from faultline.models import (
    ActionRecommendation,
    CalibrationSignal,
    EventCluster,
    FaultlineState,
    MarketImplication,
    PortfolioPosition,
    Prediction,
    RawSignal,
    RelatedSituation,
    ResearchBrief,
    ScenarioPath,
    SignalEvent,
    SituationSnapshot,
    StageTransitionWarning,
    TopicPrompt,
    WatchlistEntry,
)
from faultline.persistence.store import SignalStore, make_dead_letter
from faultline.providers.base import ProviderError, SignalProvider
from faultline.providers.live import WebSearchEnricher
from faultline.providers.normalizer import SignalNormalizer
from faultline.providers.registry import build_live_providers
from faultline.providers.sample import DarkSignalProvider, MarketContextProvider, NewsSignalProvider
from faultline.synthesis.report_builder import ReportBuilder

WORKFLOW_NODE_ORDER = (
    "ingest_signals",
    "normalize_events",
    "retrieve_related_situations",
    "retrieve_calibration",
    "map_situation",
    "generate_predictions",
    "map_market_implications",
    "generate_actions",
    "synthesize_report",
    "remember_situation",
)


class StrategicSwarmWorkflow:
    def __init__(
        self,
        *,
        store: SignalStore,
        live_providers: list[SignalProvider] | None = None,
        web_search_provider: WebSearchEnricher | None = None,
    ) -> None:
        self.store = store
        self.news = NewsSignalProvider()
        self.market = MarketContextProvider()
        self.dark = DarkSignalProvider()
        self.live_providers = live_providers or build_live_providers()
        self.web_search_provider = web_search_provider or WebSearchEnricher()
        self.normalizer = SignalNormalizer()
        self.memory = SituationMemory()
        self.memory.bootstrap(self.store.load_situation_snapshots())
        self.mapper = SituationMapper()
        self.prediction_engine = PredictionEngine()
        self.market_mapper = MarketMapper()
        self.action_engine = ActionEngine()
        self.report_builder = ReportBuilder()

    def build(self, *, _input_schema=None, checkpointer=None, interrupt_after=None):
        graph = StateGraph(FaultlineState, input_schema=_input_schema) if _input_schema else StateGraph(FaultlineState)
        for node_id in WORKFLOW_NODE_ORDER:
            graph.add_node(node_id, getattr(self, node_id))

        graph.add_edge(START, WORKFLOW_NODE_ORDER[0])
        for source, target in zip(WORKFLOW_NODE_ORDER[:-1], WORKFLOW_NODE_ORDER[1:], strict=True):
            graph.add_edge(source, target)
        graph.add_edge(WORKFLOW_NODE_ORDER[-1], END)
        return graph.compile(checkpointer=checkpointer, interrupt_after=interrupt_after)

    def ingest_signals(self, state: FaultlineState) -> FaultlineState:
        if "raw_signals" in state:
            return {
                "provenance": [
                    *state.get("provenance", []),
                    f"Loaded {len(state['raw_signals'])} raw signals into the workflow.",
                ]
            }

        if state.get("run_mode") == "demo":
            scenario_id = state.get("scenario_id") or "open_model_breakout"
            raw = self.news.fetch(scenario_id) + self.market.fetch(scenario_id) + self.dark.fetch(scenario_id)
            return {
                "raw_signals": raw,
                "provenance": [f"Ingested {len(raw)} raw signals from sample providers for {scenario_id}."],
                "diagnostics": {**state.get("diagnostics", {}), "source_counts": {"sample": len(raw)}},
            }

        if state.get("run_mode") == "topic_chat":
            start_at, end_at = self._resolve_window(state, lookback_minutes=60 * 24 * 7)
            brief = self._coerce_brief(state.get("research_brief"))
            story_key = self._topic_story_key(brief)
            questions = state.get("retrieval_questions", [])
            raw = []
            provider_counts: dict[str, int] = {}
            synthesis_count = 0
            for question in questions:
                try:
                    fetched = [
                        item if isinstance(item, RawSignal) else RawSignal.model_validate(item)
                        for item in self.web_search_provider.query(question, story_key=story_key, fetched_at=end_at)
                    ]
                    synthesis_count += len(fetched)
                    raw.extend(fetched)
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
                    fetched = [
                        item if isinstance(item, RawSignal) else RawSignal.model_validate(item)
                        for item in provider.fetch_window(start_at, end_at)
                    ]
                    provider_counts[provider.provider_name] = len(fetched)
                    raw.extend(fetched)
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
            return {
                "raw_signals": raw,
                "provenance": [
                    f"Ingested {len(raw)} raw signals for topic chat across {len(questions)} retrieval questions."
                ],
                "diagnostics": {**state.get("diagnostics", {}), "source_counts": provider_counts},
            }

        start_at, end_at = self._resolve_window(state)
        raw = []
        provider_counts: dict[str, int] = {}
        for provider in self.live_providers:
            try:
                fetched = [
                    item if isinstance(item, RawSignal) else RawSignal.model_validate(item)
                    for item in provider.fetch_window(start_at, end_at)
                ]
                provider_counts[provider.provider_name] = len(fetched)
                raw.extend(fetched)
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
        return {
            "raw_signals": raw,
            "provenance": [f"Ingested {len(raw)} raw signals from live providers."],
            "diagnostics": {**state.get("diagnostics", {}), "source_counts": provider_counts},
        }

    def normalize_events(self, state: FaultlineState) -> FaultlineState:
        manual_excluded_ids = set(state.get("excluded_signal_ids", []))
        raw_signals = self._coerce_list(state["raw_signals"], RawSignal)
        source_signals = [signal for signal in raw_signals if signal.id not in manual_excluded_ids]
        story_keys = [self.normalizer._story_key(signal) for signal in source_signals]
        dedupe_hashes = [signal.dedupe_hash or signal.id for signal in source_signals]
        known_hashes = (
            self.store.get_seen_dedupe_hashes(dedupe_hashes)
            if state.get("run_mode") not in {"demo", "replay", "topic_chat"}
            else set()
        )
        prior_story_counts = self.store.get_story_counts(story_keys) if state.get("run_mode") != "demo" else {}
        events, clusters, diagnostics = self.normalizer.normalize(
            source_signals,
            known_dedupe_hashes=known_hashes,
            prior_story_counts=prior_story_counts,
        )
        if state.get("run_mode") != "demo":
            self.store.save_raw_signals(source_signals)
            self.store.save_normalized_events(events)
            self.store.save_event_clusters(clusters)

        included_signal_ids = [item.id for item in events]
        excluded_signal_ids = sorted(
            {
                *manual_excluded_ids,
                *(signal.id for signal in raw_signals if signal.id not in included_signal_ids),
            }
        )
        selected_cluster = clusters[0] if clusters else None
        return {
            "normalized_events": events,
            "event_clusters": clusters,
            "selected_cluster": selected_cluster,
            "included_signal_ids": included_signal_ids,
            "excluded_signal_ids": excluded_signal_ids,
            "diagnostics": {**state.get("diagnostics", {}), **diagnostics},
            "provenance": [
                *state.get("provenance", []),
                f"Normalized {len(events)} events into {len(clusters)} event clusters.",
            ],
        }

    def retrieve_related_situations(self, state: FaultlineState) -> FaultlineState:
        cluster = self._coerce_optional(state.get("selected_cluster"), EventCluster)
        if cluster is None:
            return {
                "related_situations": [],
                "provenance": [*state.get("provenance", []), "Related situation retrieval skipped."],
            }
        related = self.memory.search(cluster, exclude_id=cluster.cluster_id)
        return {
            "related_situations": related,
            "provenance": [*state.get("provenance", []), f"Retrieved {len(related)} related prior situations."],
        }

    def retrieve_calibration(self, state: FaultlineState) -> FaultlineState:
        run_id = state.get("diagnostics", {}).get("run_id")
        calibration_signals = self.store.load_calibration_signals(exclude_run_id=run_id)
        return {
            "calibration_signals": calibration_signals,
            "provenance": [
                *state.get("provenance", []),
                f"Loaded {len(calibration_signals)} calibration signals from prior outcomes.",
            ],
        }

    def map_situation(self, state: FaultlineState) -> FaultlineState:
        cluster = self._coerce_optional(state.get("selected_cluster"), EventCluster)
        if cluster is None:
            return {
                "situation_snapshot": None,
                "provenance": [*state.get("provenance", []), "Situation mapping skipped."],
            }
        cluster_events = [
            item
            for item in self._coerce_list(state["normalized_events"], SignalEvent)
            if item.cluster_id == cluster.cluster_id
        ]
        snapshot = self.mapper.map(
            cluster,
            cluster_events,
            self._coerce_list(state.get("related_situations", []), RelatedSituation),
        )
        return {
            "situation_snapshot": snapshot,
            "provenance": [
                *state.get("provenance", []),
                f"Mapped situation {snapshot.title} at stage {snapshot.stage.stage}.",
            ],
        }

    def generate_predictions(self, state: FaultlineState) -> FaultlineState:
        snapshot = self._coerce_optional(state.get("situation_snapshot"), SituationSnapshot)
        cluster = self._coerce_optional(state.get("selected_cluster"), EventCluster)
        if snapshot is None or cluster is None:
            return {
                "predictions": [],
                "scenario_tree": [],
                "stage_transition_warnings": [],
                "provenance": [*state.get("provenance", []), "Prediction skipped."],
            }
        predictions, scenario_tree, stage_transition_warnings = self.prediction_engine.predict(
            snapshot,
            cluster,
            self._coerce_list(state.get("calibration_signals", []), CalibrationSignal),
        )
        return {
            "predictions": predictions,
            "scenario_tree": scenario_tree,
            "stage_transition_warnings": stage_transition_warnings,
            "provenance": [
                *state.get("provenance", []),
                f"Generated {len(predictions)} predictions, {len(scenario_tree)} scenario branches, "
                f"and {len(stage_transition_warnings)} stage warnings.",
            ],
        }

    def map_market_implications(self, state: FaultlineState) -> FaultlineState:
        snapshot = self._coerce_optional(state.get("situation_snapshot"), SituationSnapshot)
        cluster = self._coerce_optional(state.get("selected_cluster"), EventCluster)
        if snapshot is None or cluster is None:
            return {
                "market_implications": [],
                "provenance": [*state.get("provenance", []), "Market mapping skipped."],
            }
        implications = self.market_mapper.map(
            snapshot,
            self._coerce_list(state.get("predictions", []), Prediction),
            cluster,
            self._coerce_list(state.get("calibration_signals", []), CalibrationSignal),
        )
        return {
            "market_implications": implications,
            "provenance": [*state.get("provenance", []), f"Mapped {len(implications)} market implications."],
        }

    def generate_actions(self, state: FaultlineState) -> FaultlineState:
        snapshot = self._coerce_optional(state.get("situation_snapshot"), SituationSnapshot)
        if snapshot is None:
            return {
                "action_recommendations": [],
                "exit_signals": [],
                "endangered_symbols": [],
                "provenance": [*state.get("provenance", []), "Action generation skipped."],
            }
        actions, exits, endangered_symbols = self.action_engine.generate(
            snapshot,
            self._coerce_list(state.get("market_implications", []), MarketImplication),
            self._coerce_list(state.get("predictions", []), Prediction),
            self._coerce_list(state.get("calibration_signals", []), CalibrationSignal),
            self._coerce_list(state.get("portfolio_positions", []), PortfolioPosition),
            self._coerce_list(state.get("watchlist", []), WatchlistEntry),
            self._coerce_list(state.get("stage_transition_warnings", []), StageTransitionWarning),
            state.get("operator_policy_config"),
        )
        return {
            "action_recommendations": actions,
            "exit_signals": exits,
            "endangered_symbols": endangered_symbols,
            "provenance": [*state.get("provenance", []), f"Generated {len(actions)} actions and {len(exits)} exits."],
        }

    def synthesize_report(self, state: FaultlineState) -> FaultlineState:
        snapshot = self._coerce_optional(state.get("situation_snapshot"), SituationSnapshot)
        cluster = self._coerce_optional(state.get("selected_cluster"), EventCluster)
        diagnostics = self._report_diagnostics(state)
        if snapshot is None or cluster is None:
            report = self.report_builder.empty_report(state.get("provenance", []))
            topic_prompt = state.get("topic_prompt")
            research_brief = state.get("research_brief")
            if topic_prompt is not None:
                report.topic_prompt = (
                    topic_prompt.topic if isinstance(topic_prompt, TopicPrompt) else topic_prompt.get("topic", "")
                )
            if research_brief is not None:
                if not isinstance(research_brief, ResearchBrief):
                    research_brief = ResearchBrief.model_validate(research_brief)
                report.intake_assumptions = research_brief.assumptions
                report.deep_dive_objective = self.report_builder._deep_dive_objective(research_brief)
            report.retrieval_questions = state.get("retrieval_questions", [])
            return {
                "final_report": report,
                "diagnostics": {**diagnostics, "publish_decision": report.publication_status},
            }
        report = self.report_builder.build(
            snapshot=snapshot,
            cluster=cluster,
            related_situations=self._coerce_list(state.get("related_situations", []), RelatedSituation),
            calibration_signals=self._coerce_list(state.get("calibration_signals", []), CalibrationSignal),
            predictions=self._coerce_list(state.get("predictions", []), Prediction),
            scenario_tree=self._coerce_list(state.get("scenario_tree", []), ScenarioPath),
            stage_transition_warnings=self._coerce_list(
                state.get("stage_transition_warnings", []), StageTransitionWarning
            ),
            implications=self._coerce_list(state.get("market_implications", []), MarketImplication),
            actions=self._coerce_list(state.get("action_recommendations", []), ActionRecommendation),
            exits=self._coerce_list(state.get("exit_signals", []), ActionRecommendation),
            endangered_symbols=state.get("endangered_symbols", []),
            provenance=state.get("provenance", []),
            topic_prompt=state.get("topic_prompt"),
            research_brief=state.get("research_brief"),
            retrieval_questions=state.get("retrieval_questions", []),
        )
        return {
            "final_report": report,
            "diagnostics": {
                **diagnostics,
                "publish_decision": report.publication_status,
                "stage": snapshot.stage.stage,
            },
        }

    def remember_situation(self, state: FaultlineState) -> FaultlineState:
        snapshot = self._coerce_optional(state.get("situation_snapshot"), SituationSnapshot)
        if snapshot is not None:
            self.memory.remember(snapshot)
            self.store.save_situation_snapshot(snapshot)
        return {}

    def _resolve_window(self, state: FaultlineState, *, lookback_minutes: int = 60) -> tuple[datetime, datetime]:
        now = datetime.now(UTC)
        start_at = (
            datetime.fromisoformat(state["window_start"])
            if state.get("window_start")
            else now - timedelta(minutes=lookback_minutes)
        )
        end_at = datetime.fromisoformat(state["window_end"]) if state.get("window_end") else now
        return start_at, end_at

    def _coerce_brief(self, brief: ResearchBrief | dict[str, Any] | None) -> ResearchBrief | None:
        if brief is None or isinstance(brief, ResearchBrief):
            return brief
        return ResearchBrief.model_validate(brief)

    def _topic_story_key(self, brief: ResearchBrief | None) -> str:
        if brief is None:
            return "topic_chat"
        seed = brief.normalized_topic or brief.original_topic
        return "_".join(token for token in seed.lower().replace("/", " ").split() if token)[:80] or "topic_chat"

    def _report_diagnostics(self, state: FaultlineState) -> dict[str, Any]:
        topic_prompt = state.get("topic_prompt")
        topic = (
            topic_prompt.topic
            if isinstance(topic_prompt, TopicPrompt)
            else topic_prompt.get("topic", "")
            if isinstance(topic_prompt, dict)
            else ""
        )
        chat_session = state.get("chat_intake_session")
        return {
            **state.get("diagnostics", {}),
            "topic_prompt": topic,
            "topic_chat_turn_count": len(chat_session.turns) if chat_session is not None else 0,
            "included_signal_count": len(state.get("included_signal_ids", [])),
            "excluded_signal_count": len(state.get("excluded_signal_ids", [])),
        }

    def _coerce_optional(self, value: Any, model_class):
        if value is None or isinstance(value, model_class):
            return value
        return model_class.model_validate(value)

    def _coerce_list(self, values: list[Any], model_class) -> list[Any]:
        return [item if isinstance(item, model_class) else model_class.model_validate(item) for item in values]
