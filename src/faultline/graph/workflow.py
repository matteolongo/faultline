from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel

try:
    from langgraph.graph import END, START, StateGraph
except Exception:  # pragma: no cover - fallback for incompatible local langgraph installs
    END = "__end__"
    START = "__start__"

    class _CompiledGraph:
        def __init__(self, nodes: dict, edges: dict, conditional_edges: dict) -> None:
            self.nodes = nodes
            self.edges = edges
            self.conditional_edges = conditional_edges

        def stream(self, initial_state: dict, stream_mode: str = "values"):
            state = dict(initial_state)
            current = self.edges[START]
            while current != END:
                update = self.nodes[current](state) or {}
                state = {**state, **update}
                yield state.copy()
                if current in self.conditional_edges:
                    route_fn, route_map = self.conditional_edges[current]
                    current = route_map[route_fn(state)]
                else:
                    current = self.edges[current]

    class StateGraph:  # type: ignore[override]
        def __init__(self, _state_schema, **kwargs) -> None:
            self.nodes: dict[str, object] = {}
            self.edges: dict[str, str] = {}
            self.conditional_edges: dict[str, tuple[object, dict[str, str]]] = {}

        def add_node(self, name: str, fn) -> None:
            self.nodes[name] = fn

        def add_edge(self, source: str, target: str) -> None:
            self.edges[source] = target

        def add_conditional_edges(self, source: str, fn, mapping: dict[str, str]) -> None:
            self.conditional_edges[source] = (fn, mapping)

        def compile(self) -> _CompiledGraph:
            return _CompiledGraph(self.nodes, self.edges, self.conditional_edges)


from faultline.agents.execution_critic import ExecutionCritic
from faultline.agents.opportunity_generator import OpportunityGenerator
from faultline.agents.pattern_matcher import PatternMatcher
from faultline.agents.ripple_architect import RippleArchitect
from faultline.agents.signal_alchemist import SignalAlchemist
from faultline.llm.backend import StructuredReasoner
from faultline.models import FaultlineState
from faultline.models.contracts import EquityOpportunity, ScenarioDetection
from faultline.persistence.store import SignalStore, make_dead_letter
from faultline.providers.base import ProviderError, SignalProvider
from faultline.providers.live import WebSearchEnricher
from faultline.providers.normalizer import SignalNormalizer
from faultline.providers.registry import build_live_providers
from faultline.providers.sample import (
    DarkSignalProvider,
    MarketContextProvider,
    NewsSignalProvider,
)
from faultline.scoring.fragility import FragilityScorer
from faultline.synthesis.report_builder import ReportBuilder


class EquityList(BaseModel):
    """Module-level wrapper used for structured LLM output in map_equity_opportunities."""

    opportunities: list[EquityOpportunity]


class StrategicSwarmWorkflow:
    def __init__(
        self,
        *,
        store: SignalStore,
        live_providers: list[SignalProvider] | None = None,
        reasoner: StructuredReasoner | None = None,
    ) -> None:
        self.store = store
        self.reasoner = reasoner or StructuredReasoner()
        self.news = NewsSignalProvider()
        self.market = MarketContextProvider()
        self.dark = DarkSignalProvider()
        self.live_providers = live_providers or build_live_providers()
        self.web_search = WebSearchEnricher()
        self.normalizer = SignalNormalizer()
        self.pattern_matcher = PatternMatcher(self.reasoner)
        self.signal_alchemist = SignalAlchemist(self.reasoner)
        self.fragility = FragilityScorer()
        self.ripple_architect = RippleArchitect(self.reasoner)
        self.opportunity_generator = OpportunityGenerator()
        self.execution_critic = ExecutionCritic()
        self.report_builder = ReportBuilder(self.reasoner)

    def build(self, *, _input_schema=None):
        graph = StateGraph(FaultlineState, input_schema=_input_schema) if _input_schema else StateGraph(FaultlineState)
        graph.add_node("ingest_signals", self.ingest_signals)
        graph.add_node("normalize_events", self.normalize_events)
        graph.add_node("pattern_match", self.pattern_match)
        graph.add_node("detect_scenario", self.detect_scenario)
        graph.add_node("enrich_dark_signals", self.enrich_dark_signals)
        graph.add_node("map_equity_opportunities", self.map_equity_opportunities)
        graph.add_node("compute_fragility", self.compute_fragility)
        graph.add_node("build_ripple_graph", self.build_ripple_graph)
        graph.add_node("generate_opportunities", self.generate_opportunities)
        graph.add_node("critique_execution", self.critique_execution)
        graph.add_node("synthesize_report", self.synthesize_report)
        graph.add_node("final_review", self.final_review)

        graph.add_edge(START, "ingest_signals")
        graph.add_edge("ingest_signals", "normalize_events")
        graph.add_edge("normalize_events", "pattern_match")
        graph.add_edge("pattern_match", "detect_scenario")
        graph.add_edge("detect_scenario", "enrich_dark_signals")
        graph.add_edge("enrich_dark_signals", "map_equity_opportunities")
        graph.add_edge("map_equity_opportunities", "compute_fragility")
        graph.add_edge("compute_fragility", "build_ripple_graph")
        graph.add_edge("build_ripple_graph", "generate_opportunities")
        graph.add_edge("generate_opportunities", "critique_execution")
        graph.add_conditional_edges(
            "critique_execution",
            self._route_after_critique,
            {
                "retry": "generate_opportunities",
                "synthesize": "synthesize_report",
            },
        )
        graph.add_edge("synthesize_report", "final_review")
        graph.add_edge("final_review", END)
        return graph.compile()

    def ingest_signals(self, state: FaultlineState) -> FaultlineState:
        if state.get("raw_signals"):
            provenance = [f"Loaded {len(state['raw_signals'])} raw signals into the workflow."]
            return {
                "provenance": provenance,
                "opportunity_retry_count": 0,
                "max_opportunity_retries": 1,
            }

        if state.get("run_mode") == "demo":
            scenario_id = state.get("scenario_id") or "arctic_cable_bypass"
            raw = self.news.fetch(scenario_id) + self.market.fetch(scenario_id) + self.dark.fetch(scenario_id)
            provenance = [f"Ingested {len(raw)} raw signals from sample providers for {scenario_id}."]
            return {
                "raw_signals": raw,
                "provenance": provenance,
                "opportunity_retry_count": 0,
                "max_opportunity_retries": 1,
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
        provenance = [f"Ingested {len(raw)} raw signals from live providers."]
        diagnostics = {"source_counts": provider_counts}
        return {
            "raw_signals": raw,
            "provenance": provenance,
            "diagnostics": diagnostics,
            "opportunity_retry_count": 0,
            "max_opportunity_retries": 1,
        }

    def normalize_events(self, state: FaultlineState) -> FaultlineState:
        story_keys = []
        dedupe_hashes = []
        for signal in state["raw_signals"]:
            dedupe_hashes.append(signal.dedupe_hash or signal.id)
            story_keys.append(self.normalizer._story_key(signal))
        known_hashes = (
            self.store.get_seen_dedupe_hashes(dedupe_hashes)
            if state.get("run_mode") not in {"demo", "replay"}
            else set()
        )
        prior_story_counts = self.store.get_story_counts(story_keys) if state.get("run_mode") != "demo" else {}
        events, clusters, norm_diag = self.normalizer.normalize(
            state["raw_signals"],
            known_dedupe_hashes=known_hashes,
            prior_story_counts=prior_story_counts,
        )
        if state.get("run_mode") != "demo":
            self.store.save_raw_signals(state["raw_signals"])
            self.store.save_normalized_events(events)
            self.store.save_event_clusters(clusters)
        selected_cluster = clusters[0] if clusters else None
        diagnostics = {**state.get("diagnostics", {}), **norm_diag}
        provenance = [
            *state["provenance"],
            f"Normalized {len(events)} events into SignalEvent records across {len(clusters)} clusters.",
        ]
        return {
            "normalized_events": events,
            "event_clusters": clusters,
            "selected_cluster": selected_cluster,
            "diagnostics": diagnostics,
            "provenance": provenance,
        }

    def pattern_match(self, state: FaultlineState) -> FaultlineState:
        cluster = state.get("selected_cluster")
        cluster_events = (
            [item for item in state["normalized_events"] if item.cluster_id == cluster.cluster_id] if cluster else []
        )
        patterns, llm_diag = (
            self.pattern_matcher.match(cluster_events, cluster)
            if cluster
            else ([], {"llm_used": False, "llm_status": "empty"})
        )
        diagnostics = {
            **state.get("diagnostics", {}),
            "pattern_confidence": patterns[0].confidence if patterns else 0.0,
            "pattern_llm": llm_diag,
        }
        provenance = (
            [*state["provenance"], f"Matched topology {patterns[0].pattern_name}."]
            if patterns
            else [*state["provenance"], "Pattern match skipped."]
        )
        return {
            "abstract_patterns": patterns,
            "diagnostics": diagnostics,
            "provenance": provenance,
        }

    def detect_scenario(self, state: FaultlineState) -> FaultlineState:
        clusters = state.get("event_clusters") or []
        patterns = state.get("abstract_patterns") or []
        if not clusters:
            return {
                "detected_scenario": None,
                "provenance": [
                    *state["provenance"],
                    "Scenario detection skipped (no clusters).",
                ],
                "diagnostics": state.get("diagnostics", {}),
            }
        fallback = ScenarioDetection(
            scenario_name="Unclassified macro event",
            scenario_type="other",
            key_actors=[],
            geographic_scope=[],
            consequence_chain=[],
            confidence=0.0,
        )
        cluster_summaries = [
            {
                "story": c.story_key,
                "title": c.canonical_title,
                "summary": c.summary,
                "region": c.region,
                "entities": c.entities[:6],
                "tags": c.tags[:8],
                "signals": len(c.signal_ids),
            }
            for c in sorted(clusters, key=lambda x: len(x.signal_ids), reverse=True)[:5]
        ]
        pattern_names = [p.pattern_name for p in patterns[:3]]
        system_prompt = (
            "You are a geopolitical and macro analyst. Given a set of news/market signal clusters "
            "and matched fragility patterns, identify the single dominant macro scenario currently unfolding.\n"
            "Return a JSON object with:\n"
            "- scenario_name: concise name (e.g. 'US-Iran Military Escalation')\n"
            "- scenario_type: one of geopolitical_conflict, trade_war, energy_crisis, monetary_policy, "
            "social_unrest, financial_contagion, supply_chain_disruption, other\n"
            "- key_actors: list of countries, companies, or institutions driving the scenario\n"
            "- geographic_scope: list of affected regions or countries\n"
            "- consequence_chain: ordered list of causal consequences "
            "(e.g. ['US strikes Iranian facilities', 'Strait of Hormuz disrupted', 'Global oil supply falls', "
            "'Middle East producers drop', 'Alternative suppliers gain'])\n"
            "- confidence: float 0.0–1.0 reflecting how clearly the scenario emerges from the data"
        )
        scenario, llm_diag = self.reasoner.refine_model(
            system_prompt=system_prompt,
            user_payload={"clusters": cluster_summaries, "patterns": pattern_names},
            model_class=ScenarioDetection,
            fallback=fallback,
        )
        diagnostics = {
            **state.get("diagnostics", {}),
            "scenario_detection_llm": llm_diag,
            "detected_scenario_name": scenario.scenario_name,
        }
        provenance = [
            *state["provenance"],
            f"Detected scenario: '{scenario.scenario_name}' (confidence {scenario.confidence:.2f}).",
        ]
        return {
            "detected_scenario": scenario,
            "diagnostics": diagnostics,
            "provenance": provenance,
        }

    def enrich_dark_signals(self, state: FaultlineState) -> FaultlineState:
        cluster = state.get("selected_cluster")
        cluster_events = (
            [item for item in state["normalized_events"] if item.cluster_id == cluster.cluster_id] if cluster else []
        )
        bundles, llm_diag = (
            self.signal_alchemist.enrich(cluster_events, cluster)
            if cluster
            else ([], {"llm_used": False, "llm_status": "empty"})
        )
        diagnostics = {**state.get("diagnostics", {}), "signal_alchemist_llm": llm_diag}
        provenance = [
            *state["provenance"],
            f"Built {len(bundles)} signal bundle(s) from weak and market signals.",
        ]

        scenario = state.get("detected_scenario")
        web_search_signals: list = []
        if self.web_search.enabled:
            all_clusters = state.get("event_clusters") or ([] if not cluster else [cluster])
            eligible = sorted(
                [c for c in all_clusters if len(c.signal_ids) >= self.web_search.min_cluster_signals],
                key=lambda c: len(c.signal_ids),
                reverse=True,
            )[: self.web_search.max_queries_per_run]
            fetched_at = datetime.now(UTC)
            for c in eligible:
                question = self.web_search.build_query(
                    c.story_key,
                    c.entities,
                    c.region,
                    scenario_name=scenario.scenario_name if scenario else None,
                    consequence_hint=scenario.consequence_chain[:2] if scenario else None,
                )
                try:
                    web_search_signals.extend(
                        self.web_search.query(question, story_key=c.story_key, fetched_at=fetched_at)
                    )
                except Exception:  # noqa: BLE001
                    pass  # non-fatal; enrichment is best-effort
            if web_search_signals:
                provenance = [
                    *provenance,
                    f"Web search enriched {len(eligible)} cluster(s) → {len(web_search_signals)} synthesis signal(s).",
                ]
                diagnostics = {
                    **diagnostics,
                    "web_search_signal_count": len(web_search_signals),
                }

        raw_signals = list(state.get("raw_signals") or []) + web_search_signals
        return {
            "signal_bundles": bundles,
            "raw_signals": raw_signals,
            "provenance": provenance,
            "diagnostics": diagnostics,
        }

    def map_equity_opportunities(self, state: FaultlineState) -> FaultlineState:
        scenario = state.get("detected_scenario")
        if not scenario or not scenario.consequence_chain:
            return {
                "equity_opportunities": [],
                "provenance": [
                    *state["provenance"],
                    "Equity mapping skipped (no scenario detected).",
                ],
                "diagnostics": state.get("diagnostics", {}),
            }

        fallback = EquityList(opportunities=[])
        system_prompt = (
            "You are an equity strategist. Given a detected macro scenario and its causal consequence chain, "
            "identify specific publicly-traded companies that will be significantly affected.\n"
            "For each company provide:\n"
            "- symbol: ticker symbol including exchange suffix if relevant (e.g. REP.MC, XOM, BNO, TTE)\n"
            "- company_name: full company name\n"
            "- direction: 'long' (benefits), 'short' (hurt), or 'watch' (uncertain/monitoring)\n"
            "- rationale: 1–2 sentence causal explanation linking the consequence chain to this company\n"
            "- scenario_link: the specific consequence chain item that drives this opportunity\n"
            "- confidence: float 0.0–1.0\n"
            "Return 3–8 opportunities. Focus on direct, near-term impact. Avoid vague sector calls."
        )
        equity_list, llm_diag = self.reasoner.refine_model(
            system_prompt=system_prompt,
            user_payload={
                "scenario_name": scenario.scenario_name,
                "scenario_type": scenario.scenario_type,
                "key_actors": scenario.key_actors,
                "geographic_scope": scenario.geographic_scope,
                "consequence_chain": scenario.consequence_chain,
            },
            model_class=EquityList,
            fallback=fallback,
        )

        opportunities = equity_list.opportunities
        # Best-effort web search confirmation per symbol
        if self.web_search.enabled and opportunities:
            fetched_at = datetime.now(UTC)
            for opp in opportunities[:3]:  # cap at 3 to avoid excess API calls
                query = f"{opp.company_name} ({opp.symbol}) stock {scenario.scenario_name} impact latest news"
                try:
                    signals = self.web_search.query(
                        query,
                        story_key=f"equity_{opp.symbol.lower()}",
                        fetched_at=fetched_at,
                    )
                    if signals:
                        opp.search_summary = signals[0].summary[:400] if signals[0].summary else None
                except Exception:  # noqa: BLE001
                    pass

        diagnostics = {
            **state.get("diagnostics", {}),
            "equity_opportunity_count": len(opportunities),
            "equity_map_llm": llm_diag,
        }
        provenance = [
            *state["provenance"],
            f"Mapped {len(opportunities)} equity opportunity/ies from scenario '{scenario.scenario_name}'.",
        ]
        return {
            "equity_opportunities": opportunities,
            "diagnostics": diagnostics,
            "provenance": provenance,
        }

    def compute_fragility(self, state: FaultlineState) -> FaultlineState:
        cluster = state.get("selected_cluster")
        cluster_events = (
            [item for item in state["normalized_events"] if item.cluster_id == cluster.cluster_id] if cluster else []
        )
        if not cluster or not state.get("abstract_patterns"):
            return {
                "fragility_assessments": [],
                "diagnostics": state.get("diagnostics", {}),
                "provenance": [*state["provenance"], "Fragility scoring skipped."],
            }
        assessment = self.fragility.score(
            cluster_events,
            cluster,
            state["abstract_patterns"],
            state.get("signal_bundles", []),
        )
        diagnostics = {
            **state.get("diagnostics", {}),
            "fragility_score": assessment[0].fragility_score.value if assessment else 0.0,
        }
        provenance = (
            [
                *state["provenance"],
                f"Computed fragility score {assessment[0].fragility_score.value:.2f}.",
            ]
            if assessment
            else [*state["provenance"], "Fragility scoring skipped."]
        )
        return {
            "fragility_assessments": assessment,
            "diagnostics": diagnostics,
            "provenance": provenance,
        }

    def build_ripple_graph(self, state: FaultlineState) -> FaultlineState:
        cluster = state.get("selected_cluster")
        cluster_events = (
            [item for item in state["normalized_events"] if item.cluster_id == cluster.cluster_id] if cluster else []
        )
        if not cluster or not state.get("fragility_assessments"):
            return {
                "ripple_scenarios": [],
                "provenance": [*state["provenance"], "Ripple graph skipped."],
                "diagnostics": state.get("diagnostics", {}),
            }
        scenarios, llm_diag = self.ripple_architect.build(
            cluster_events,
            cluster,
            state["abstract_patterns"],
            state["fragility_assessments"],
            state.get("signal_bundles", []),
        )
        diagnostics = {**state.get("diagnostics", {}), "ripple_llm": llm_diag}
        provenance = [
            *state["provenance"],
            f"Generated {len(scenarios)} ripple scenario(s).",
        ]
        return {
            "ripple_scenarios": scenarios,
            "provenance": provenance,
            "diagnostics": diagnostics,
        }

    def generate_opportunities(self, state: FaultlineState) -> FaultlineState:
        retry_count = state.get("opportunity_retry_count", 0)
        ideas = self.opportunity_generator.generate(state["ripple_scenarios"], retry_count=retry_count)
        provenance = [
            *state["provenance"],
            f"Generated {len(ideas)} opportunity ideas on pass {retry_count + 1}.",
        ]
        return {"candidate_opportunities": ideas, "provenance": provenance}

    def critique_execution(self, state: FaultlineState) -> FaultlineState:
        reviewed = self.execution_critic.review(state["candidate_opportunities"], state["selected_cluster"])
        approved_count = sum(1 for item in reviewed if item.approved)
        retry_count = state.get("opportunity_retry_count", 0)
        if approved_count == 0:
            retry_count += 1
        diagnostics = {
            **state.get("diagnostics", {}),
            "approved_opportunities": approved_count,
            "publish_decision": "publish"
            if approved_count and state["selected_cluster"].agreement_score >= 0.45
            else "monitor_only",
        }
        provenance = [
            *state["provenance"],
            f"Execution critic approved {approved_count} ideas.",
        ]
        return {
            "reviewed_opportunities": reviewed,
            "opportunity_retry_count": retry_count,
            "diagnostics": diagnostics,
            "provenance": provenance,
        }

    def synthesize_report(self, state: FaultlineState) -> FaultlineState:
        cluster = state["selected_cluster"]
        cluster_events = [item for item in state["normalized_events"] if item.cluster_id == cluster.cluster_id]
        run_id = state.get("diagnostics", {}).get("run_id", uuid4().hex[:12])
        if not cluster:
            return {
                "final_report": None,
                "diagnostics": {
                    **state.get("diagnostics", {}),
                    "publish_decision": "monitor_only",
                },
            }
        published = self.report_builder.build(
            report_id=uuid4().hex[:12],
            run_id=run_id,
            events=cluster_events,
            cluster=cluster,
            patterns=state["abstract_patterns"],
            bundles=state.get("signal_bundles", []),
            fragility=state["fragility_assessments"],
            ripple_scenarios=state["ripple_scenarios"],
            reviewed=state["reviewed_opportunities"],
            provenance=state["provenance"],
            detected_scenario=state.get("detected_scenario"),
            equity_opportunities=state.get("equity_opportunities", []),
        )
        diagnostics = {
            **state.get("diagnostics", {}),
            **published.diagnostics,
            "publish_decision": published.publication_status,
        }
        return {"final_report": published.report, "diagnostics": diagnostics}

    def final_review(self, state: FaultlineState) -> FaultlineState:
        report = state["final_report"]
        diagnostics = {
            **state.get("diagnostics", {}),
            "report_has_opportunities": bool(report and report.opportunity_map),
            "open_question_count": len(report.open_questions) if report else 0,
        }
        return {"diagnostics": diagnostics}

    def _route_after_critique(self, state: FaultlineState) -> Literal["retry", "synthesize"]:
        approved = sum(1 for item in state["reviewed_opportunities"] if item.approved)
        if approved == 0 and state.get("opportunity_retry_count", 0) <= state.get("max_opportunity_retries", 1):
            return "retry"
        return "synthesize"
