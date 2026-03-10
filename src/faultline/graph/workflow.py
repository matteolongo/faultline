from __future__ import annotations

from datetime import UTC, datetime, timedelta

try:
    from langgraph.graph import END, START, StateGraph
except Exception:  # pragma: no cover
    END = "__end__"
    START = "__start__"

    class _CompiledGraph:
        def __init__(self, nodes: dict, edges: dict) -> None:
            self.nodes = nodes
            self.edges = edges

        def stream(self, initial_state: dict, stream_mode: str = "values"):
            state = dict(initial_state)
            current = self.edges[START]
            while current != END:
                update = self.nodes[current](state) or {}
                state = {**state, **update}
                yield state.copy()
                current = self.edges[current]

    class StateGraph:  # type: ignore[override]
        def __init__(self, _state_schema, **kwargs) -> None:
            self.nodes: dict[str, object] = {}
            self.edges: dict[str, str] = {}

        def add_node(self, name: str, fn) -> None:
            self.nodes[name] = fn

        def add_edge(self, source: str, target: str) -> None:
            self.edges[source] = target

        def compile(self) -> _CompiledGraph:
            return _CompiledGraph(self.nodes, self.edges)


from faultline.analysis import ActionEngine, MarketMapper, PredictionEngine, SituationMapper
from faultline.memory import SituationMemory
from faultline.models import FaultlineState
from faultline.persistence.store import SignalStore, make_dead_letter
from faultline.providers.base import ProviderError, SignalProvider
from faultline.providers.normalizer import SignalNormalizer
from faultline.providers.registry import build_live_providers
from faultline.providers.sample import DarkSignalProvider, MarketContextProvider, NewsSignalProvider
from faultline.synthesis.report_builder import ReportBuilder


class StrategicSwarmWorkflow:
    def __init__(
        self,
        *,
        store: SignalStore,
        live_providers: list[SignalProvider] | None = None,
    ) -> None:
        self.store = store
        self.news = NewsSignalProvider()
        self.market = MarketContextProvider()
        self.dark = DarkSignalProvider()
        self.live_providers = live_providers or build_live_providers()
        self.normalizer = SignalNormalizer()
        self.memory = SituationMemory()
        self.memory.bootstrap(self.store.load_situation_snapshots())
        self.mapper = SituationMapper()
        self.prediction_engine = PredictionEngine()
        self.market_mapper = MarketMapper()
        self.action_engine = ActionEngine()
        self.report_builder = ReportBuilder()

    def build(self, *, _input_schema=None):
        graph = StateGraph(FaultlineState, input_schema=_input_schema) if _input_schema else StateGraph(FaultlineState)
        graph.add_node("ingest_signals", self.ingest_signals)
        graph.add_node("normalize_events", self.normalize_events)
        graph.add_node("retrieve_related_situations", self.retrieve_related_situations)
        graph.add_node("retrieve_calibration", self.retrieve_calibration)
        graph.add_node("map_situation", self.map_situation)
        graph.add_node("generate_predictions", self.generate_predictions)
        graph.add_node("map_market_implications", self.map_market_implications)
        graph.add_node("generate_actions", self.generate_actions)
        graph.add_node("synthesize_report", self.synthesize_report)
        graph.add_node("remember_situation", self.remember_situation)

        graph.add_edge(START, "ingest_signals")
        graph.add_edge("ingest_signals", "normalize_events")
        graph.add_edge("normalize_events", "retrieve_related_situations")
        graph.add_edge("retrieve_related_situations", "retrieve_calibration")
        graph.add_edge("retrieve_calibration", "map_situation")
        graph.add_edge("map_situation", "generate_predictions")
        graph.add_edge("generate_predictions", "map_market_implications")
        graph.add_edge("map_market_implications", "generate_actions")
        graph.add_edge("generate_actions", "synthesize_report")
        graph.add_edge("synthesize_report", "remember_situation")
        graph.add_edge("remember_situation", END)
        return graph.compile()

    def ingest_signals(self, state: FaultlineState) -> FaultlineState:
        if state.get("raw_signals"):
            return {"provenance": [f"Loaded {len(state['raw_signals'])} raw signals into the workflow."]}

        if state.get("run_mode") == "demo":
            scenario_id = state.get("scenario_id") or "open_model_breakout"
            raw = self.news.fetch(scenario_id) + self.market.fetch(scenario_id) + self.dark.fetch(scenario_id)
            return {
                "raw_signals": raw,
                "provenance": [f"Ingested {len(raw)} raw signals from sample providers for {scenario_id}."],
                "diagnostics": {**state.get("diagnostics", {}), "source_counts": {"sample": len(raw)}},
            }

        now = datetime.now(UTC)
        start_at = (
            datetime.fromisoformat(state["window_start"]) if state.get("window_start") else now - timedelta(minutes=60)
        )
        end_at = datetime.fromisoformat(state["window_end"]) if state.get("window_end") else now
        raw = []
        provider_counts: dict[str, int] = {}
        for provider in self.live_providers:
            try:
                fetched = provider.fetch_window(start_at, end_at)
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
        story_keys = [self.normalizer._story_key(signal) for signal in state["raw_signals"]]
        dedupe_hashes = [signal.dedupe_hash or signal.id for signal in state["raw_signals"]]
        known_hashes = (
            self.store.get_seen_dedupe_hashes(dedupe_hashes)
            if state.get("run_mode") not in {"demo", "replay"}
            else set()
        )
        prior_story_counts = self.store.get_story_counts(story_keys) if state.get("run_mode") != "demo" else {}
        events, clusters, diagnostics = self.normalizer.normalize(
            state["raw_signals"],
            known_dedupe_hashes=known_hashes,
            prior_story_counts=prior_story_counts,
        )
        if state.get("run_mode") != "demo":
            self.store.save_raw_signals(state["raw_signals"])
            self.store.save_normalized_events(events)
            self.store.save_event_clusters(clusters)
        selected_cluster = clusters[0] if clusters else None
        return {
            "normalized_events": events,
            "event_clusters": clusters,
            "selected_cluster": selected_cluster,
            "diagnostics": {**state.get("diagnostics", {}), **diagnostics},
            "provenance": [
                *state.get("provenance", []),
                f"Normalized {len(events)} events into {len(clusters)} event clusters.",
            ],
        }

    def retrieve_related_situations(self, state: FaultlineState) -> FaultlineState:
        cluster = state.get("selected_cluster")
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
        cluster = state.get("selected_cluster")
        if cluster is None:
            return {
                "situation_snapshot": None,
                "provenance": [*state.get("provenance", []), "Situation mapping skipped."],
            }
        cluster_events = [item for item in state["normalized_events"] if item.cluster_id == cluster.cluster_id]
        snapshot = self.mapper.map(cluster, cluster_events, state.get("related_situations", []))
        return {
            "situation_snapshot": snapshot,
            "provenance": [
                *state.get("provenance", []),
                f"Mapped situation {snapshot.title} at stage {snapshot.stage.stage}.",
            ],
        }

    def generate_predictions(self, state: FaultlineState) -> FaultlineState:
        snapshot = state.get("situation_snapshot")
        cluster = state.get("selected_cluster")
        if snapshot is None or cluster is None:
            return {"predictions": [], "provenance": [*state.get("provenance", []), "Prediction skipped."]}
        predictions = self.prediction_engine.predict(snapshot, cluster, state.get("calibration_signals", []))
        return {
            "predictions": predictions,
            "provenance": [*state.get("provenance", []), f"Generated {len(predictions)} explicit predictions."],
        }

    def map_market_implications(self, state: FaultlineState) -> FaultlineState:
        snapshot = state.get("situation_snapshot")
        cluster = state.get("selected_cluster")
        if snapshot is None or cluster is None:
            return {
                "market_implications": [],
                "provenance": [*state.get("provenance", []), "Market mapping skipped."],
            }
        implications = self.market_mapper.map(
            snapshot,
            state.get("predictions", []),
            cluster,
            state.get("calibration_signals", []),
        )
        return {
            "market_implications": implications,
            "provenance": [*state.get("provenance", []), f"Mapped {len(implications)} market implications."],
        }

    def generate_actions(self, state: FaultlineState) -> FaultlineState:
        snapshot = state.get("situation_snapshot")
        if snapshot is None:
            return {
                "action_recommendations": [],
                "exit_signals": [],
                "provenance": [*state.get("provenance", []), "Action generation skipped."],
            }
        actions, exits = self.action_engine.generate(
            snapshot,
            state.get("market_implications", []),
            state.get("predictions", []),
            state.get("calibration_signals", []),
        )
        return {
            "action_recommendations": actions,
            "exit_signals": exits,
            "provenance": [*state.get("provenance", []), f"Generated {len(actions)} actions and {len(exits)} exits."],
        }

    def synthesize_report(self, state: FaultlineState) -> FaultlineState:
        snapshot = state.get("situation_snapshot")
        cluster = state.get("selected_cluster")
        if snapshot is None or cluster is None:
            report = self.report_builder.empty_report(state.get("provenance", []))
            return {
                "final_report": report,
                "diagnostics": {**state.get("diagnostics", {}), "publish_decision": report.publication_status},
            }
        report = self.report_builder.build(
            snapshot=snapshot,
            cluster=cluster,
            related_situations=state.get("related_situations", []),
            calibration_signals=state.get("calibration_signals", []),
            predictions=state.get("predictions", []),
            implications=state.get("market_implications", []),
            actions=state.get("action_recommendations", []),
            exits=state.get("exit_signals", []),
            provenance=state.get("provenance", []),
        )
        return {
            "final_report": report,
            "diagnostics": {
                **state.get("diagnostics", {}),
                "publish_decision": report.publication_status,
                "stage": snapshot.stage.stage,
            },
        }

    def remember_situation(self, state: FaultlineState) -> FaultlineState:
        snapshot = state.get("situation_snapshot")
        if snapshot is not None:
            self.memory.remember(snapshot)
            self.store.save_situation_snapshot(snapshot)
        return {}
