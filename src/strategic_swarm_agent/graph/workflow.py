from __future__ import annotations

from typing import Literal

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
        def __init__(self, _state_schema) -> None:
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

from strategic_swarm_agent.agents.execution_critic import ExecutionCritic
from strategic_swarm_agent.agents.opportunity_generator import OpportunityGenerator
from strategic_swarm_agent.agents.pattern_matcher import PatternMatcher
from strategic_swarm_agent.agents.ripple_architect import RippleArchitect
from strategic_swarm_agent.agents.signal_alchemist import SignalAlchemist
from strategic_swarm_agent.models import SwarmGraphState
from strategic_swarm_agent.providers.normalizer import SignalNormalizer
from strategic_swarm_agent.providers.sample import DarkSignalProvider, MarketContextProvider, NewsSignalProvider
from strategic_swarm_agent.scoring.fragility import FragilityScorer
from strategic_swarm_agent.synthesis.report_builder import ReportBuilder


class StrategicSwarmWorkflow:
    def __init__(self) -> None:
        self.news = NewsSignalProvider()
        self.market = MarketContextProvider()
        self.dark = DarkSignalProvider()
        self.normalizer = SignalNormalizer()
        self.pattern_matcher = PatternMatcher()
        self.signal_alchemist = SignalAlchemist()
        self.fragility = FragilityScorer()
        self.ripple_architect = RippleArchitect()
        self.opportunity_generator = OpportunityGenerator()
        self.execution_critic = ExecutionCritic()
        self.report_builder = ReportBuilder()

    def build(self):
        graph = StateGraph(SwarmGraphState)
        graph.add_node("ingest_signals", self.ingest_signals)
        graph.add_node("normalize_events", self.normalize_events)
        graph.add_node("pattern_match", self.pattern_match)
        graph.add_node("enrich_dark_signals", self.enrich_dark_signals)
        graph.add_node("compute_fragility", self.compute_fragility)
        graph.add_node("build_ripple_graph", self.build_ripple_graph)
        graph.add_node("generate_opportunities", self.generate_opportunities)
        graph.add_node("critique_execution", self.critique_execution)
        graph.add_node("synthesize_report", self.synthesize_report)
        graph.add_node("final_review", self.final_review)

        graph.add_edge(START, "ingest_signals")
        graph.add_edge("ingest_signals", "normalize_events")
        graph.add_edge("normalize_events", "pattern_match")
        graph.add_edge("pattern_match", "enrich_dark_signals")
        graph.add_edge("enrich_dark_signals", "compute_fragility")
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

    def ingest_signals(self, state: SwarmGraphState) -> SwarmGraphState:
        scenario_id = state["scenario_id"]
        raw = self.news.fetch(scenario_id) + self.market.fetch(scenario_id) + self.dark.fetch(scenario_id)
        provenance = [f"Ingested {len(raw)} raw signals from sample providers for {scenario_id}."]
        return {"raw_signals": raw, "provenance": provenance, "opportunity_retry_count": 0, "max_opportunity_retries": 1}

    def normalize_events(self, state: SwarmGraphState) -> SwarmGraphState:
        events = self.normalizer.normalize(state["raw_signals"])
        provenance = [*state["provenance"], f"Normalized {len(events)} events into SignalEvent records."]
        return {"normalized_events": events, "provenance": provenance}

    def pattern_match(self, state: SwarmGraphState) -> SwarmGraphState:
        patterns = self.pattern_matcher.match(state["normalized_events"])
        diagnostics = {
            **state.get("diagnostics", {}),
            "pattern_confidence": patterns[0].confidence if patterns else 0.0,
        }
        provenance = [*state["provenance"], f"Matched topology {patterns[0].pattern_name}."]
        return {"abstract_patterns": patterns, "diagnostics": diagnostics, "provenance": provenance}

    def enrich_dark_signals(self, state: SwarmGraphState) -> SwarmGraphState:
        bundles = self.signal_alchemist.enrich(state["normalized_events"], state["scenario_id"])
        provenance = [*state["provenance"], f"Built {len(bundles)} signal bundle(s) from weak and market signals."]
        return {"signal_bundles": bundles, "provenance": provenance}

    def compute_fragility(self, state: SwarmGraphState) -> SwarmGraphState:
        assessment = self.fragility.score(
            state["normalized_events"],
            state["abstract_patterns"],
            state.get("signal_bundles", []),
        )
        diagnostics = {
            **state.get("diagnostics", {}),
            "fragility_score": assessment[0].fragility_score.value if assessment else 0.0,
        }
        provenance = [*state["provenance"], f"Computed fragility score {assessment[0].fragility_score.value:.2f}."]
        return {"fragility_assessments": assessment, "diagnostics": diagnostics, "provenance": provenance}

    def build_ripple_graph(self, state: SwarmGraphState) -> SwarmGraphState:
        scenarios = self.ripple_architect.build(
            state["normalized_events"],
            state["abstract_patterns"],
            state["fragility_assessments"],
            state.get("signal_bundles", []),
        )
        provenance = [*state["provenance"], f"Generated {len(scenarios)} ripple scenario(s)."]
        return {"ripple_scenarios": scenarios, "provenance": provenance}

    def generate_opportunities(self, state: SwarmGraphState) -> SwarmGraphState:
        retry_count = state.get("opportunity_retry_count", 0)
        ideas = self.opportunity_generator.generate(state["ripple_scenarios"], retry_count=retry_count)
        provenance = [*state["provenance"], f"Generated {len(ideas)} opportunity ideas on pass {retry_count + 1}."]
        return {"candidate_opportunities": ideas, "provenance": provenance}

    def critique_execution(self, state: SwarmGraphState) -> SwarmGraphState:
        reviewed = self.execution_critic.review(state["candidate_opportunities"])
        approved_count = sum(1 for item in reviewed if item.approved)
        retry_count = state.get("opportunity_retry_count", 0)
        if approved_count == 0:
            retry_count += 1
        diagnostics = {
            **state.get("diagnostics", {}),
            "approved_opportunities": approved_count,
        }
        provenance = [*state["provenance"], f"Execution critic approved {approved_count} ideas."]
        return {
            "reviewed_opportunities": reviewed,
            "opportunity_retry_count": retry_count,
            "diagnostics": diagnostics,
            "provenance": provenance,
        }

    def synthesize_report(self, state: SwarmGraphState) -> SwarmGraphState:
        report = self.report_builder.build(
            scenario_id=state["scenario_id"],
            events=state["normalized_events"],
            patterns=state["abstract_patterns"],
            bundles=state.get("signal_bundles", []),
            fragility=state["fragility_assessments"],
            ripple_scenarios=state["ripple_scenarios"],
            reviewed=state["reviewed_opportunities"],
            provenance=state["provenance"],
        )
        return {"final_report": report}

    def final_review(self, state: SwarmGraphState) -> SwarmGraphState:
        report = state["final_report"]
        diagnostics = {
            **state.get("diagnostics", {}),
            "report_has_opportunities": bool(report and report.opportunity_map),
            "open_question_count": len(report.open_questions) if report else 0,
        }
        return {"diagnostics": diagnostics}

    def _route_after_critique(self, state: SwarmGraphState) -> Literal["retry", "synthesize"]:
        approved = sum(1 for item in state["reviewed_opportunities"] if item.approved)
        if approved == 0 and state.get("opportunity_retry_count", 0) <= state.get("max_opportunity_retries", 1):
            return "retry"
        return "synthesize"
