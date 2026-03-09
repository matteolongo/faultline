"""Tests for detect_scenario and map_equity_opportunities workflow nodes."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from strategic_swarm_agent.models.contracts import (
    AbstractPattern,
    EquityOpportunity,
    EventCluster,
    ScenarioDetection,
)
from strategic_swarm_agent.synthesis.report_builder import render_markdown
from strategic_swarm_agent.models.contracts import FinalReport


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_cluster(n_signals: int = 5) -> EventCluster:
    return EventCluster(
        cluster_id="c1",
        story_key="us_iran_escalation",
        canonical_title="US-Iran Military Escalation",
        summary="US strikes on Iranian nuclear facilities trigger regional response.",
        region="Middle East",
        entities=["United States", "Iran", "IRGC"],
        tags=["military", "nuclear", "sanctions"],
        source_families=["news", "market"],
        signal_ids=[f"sig_{i}" for i in range(n_signals)],
        first_seen_at=datetime(2026, 3, 9, tzinfo=timezone.utc),
        last_seen_at=datetime(2026, 3, 9, tzinfo=timezone.utc),
        novelty_score=0.9,
        agreement_score=0.8,
        cluster_strength=0.85,
    )


def _base_state(cluster: EventCluster | None = None) -> dict:
    c = cluster or _make_cluster()
    return {
        "event_clusters": [c],
        "selected_cluster": c,
        "abstract_patterns": [],
        "raw_signals": [],
        "normalized_events": [],
        "signal_bundles": [],
        "diagnostics": {},
        "provenance": [],
        "run_mode": "demo",
    }


# ── ScenarioDetection model ────────────────────────────────────────────────────

def test_scenario_detection_model_valid():
    sd = ScenarioDetection(
        scenario_name="US-Iran Military Escalation",
        scenario_type="geopolitical_conflict",
        key_actors=["United States", "Iran"],
        geographic_scope=["Middle East", "Persian Gulf"],
        consequence_chain=[
            "US strikes Iranian nuclear facilities",
            "Iran retaliates via Strait of Hormuz disruption",
            "Global oil supply contracts by 20%",
            "Middle East oil producers face export blockade",
            "Alternative suppliers (Venezuela, Nigeria) gain premium",
        ],
        confidence=0.82,
    )
    assert sd.scenario_name == "US-Iran Military Escalation"
    assert len(sd.consequence_chain) == 5
    assert sd.confidence == pytest.approx(0.82)


def test_scenario_detection_confidence_bounds():
    with pytest.raises(Exception):
        ScenarioDetection(
            scenario_name="X",
            scenario_type="other",
            confidence=1.5,  # out of range
        )


def test_scenario_detection_defaults():
    sd = ScenarioDetection(scenario_name="Test", scenario_type="other")
    assert sd.key_actors == []
    assert sd.geographic_scope == []
    assert sd.consequence_chain == []
    assert sd.confidence == pytest.approx(0.5)


# ── EquityOpportunity model ────────────────────────────────────────────────────

def test_equity_opportunity_model_valid():
    opp = EquityOpportunity(
        symbol="REP.MC",
        company_name="Repsol",
        direction="long",
        rationale="Repsol's Venezuelan operations become critical as Middle East supply collapses.",
        scenario_link="Alternative suppliers (Venezuela) gain premium",
        confidence=0.75,
    )
    assert opp.symbol == "REP.MC"
    assert opp.direction == "long"
    assert opp.search_summary is None


def test_equity_opportunity_directions():
    for direction in ("long", "short", "watch"):
        opp = EquityOpportunity(
            symbol="XOM",
            company_name="ExxonMobil",
            direction=direction,
            rationale="Test",
            scenario_link="Test link",
            confidence=0.5,
        )
        assert opp.direction == direction


# ── detect_scenario node ───────────────────────────────────────────────────────

def test_detect_scenario_skips_when_no_clusters():
    """detect_scenario returns None with no clusters."""
    from strategic_swarm_agent.graph.workflow import StrategicSwarmWorkflow
    from unittest.mock import MagicMock

    wf = StrategicSwarmWorkflow.__new__(StrategicSwarmWorkflow)
    wf.reasoner = MagicMock()

    state = _base_state()
    state["event_clusters"] = []

    result = wf.detect_scenario(state)

    assert result["detected_scenario"] is None
    assert "skipped" in result["provenance"][-1].lower()
    wf.reasoner.refine_model.assert_not_called()


def test_detect_scenario_produces_scenario_detection():
    """detect_scenario calls LLM and returns a ScenarioDetection."""
    from strategic_swarm_agent.graph.workflow import StrategicSwarmWorkflow

    expected = ScenarioDetection(
        scenario_name="US-Iran Military Escalation",
        scenario_type="geopolitical_conflict",
        key_actors=["United States", "Iran"],
        geographic_scope=["Middle East"],
        consequence_chain=["US strikes Iran", "Hormuz disrupted", "Oil price spikes"],
        confidence=0.88,
    )

    wf = StrategicSwarmWorkflow.__new__(StrategicSwarmWorkflow)
    wf.reasoner = MagicMock()
    wf.reasoner.refine_model.return_value = (expected, {"llm_used": True, "llm_status": "ok"})

    state = _base_state()
    result = wf.detect_scenario(state)

    assert result["detected_scenario"] is expected
    assert result["detected_scenario"].scenario_name == "US-Iran Military Escalation"
    assert len(result["detected_scenario"].consequence_chain) == 3
    assert "US-Iran Military Escalation" in result["provenance"][-1]


def test_detect_scenario_uses_fallback_when_llm_disabled():
    """detect_scenario returns fallback ScenarioDetection when LLM disabled."""
    from strategic_swarm_agent.graph.workflow import StrategicSwarmWorkflow

    fallback = ScenarioDetection(
        scenario_name="Unclassified macro event",
        scenario_type="other",
        confidence=0.0,
    )

    wf = StrategicSwarmWorkflow.__new__(StrategicSwarmWorkflow)
    wf.reasoner = MagicMock()
    wf.reasoner.refine_model.return_value = (fallback, {"llm_used": False, "llm_status": "disabled"})

    state = _base_state()
    result = wf.detect_scenario(state)

    assert result["detected_scenario"].scenario_name == "Unclassified macro event"
    assert result["detected_scenario"].confidence == pytest.approx(0.0)


# ── map_equity_opportunities node ─────────────────────────────────────────────

def test_map_equity_skips_when_no_scenario():
    """map_equity_opportunities skips gracefully when no scenario is detected."""
    from strategic_swarm_agent.graph.workflow import StrategicSwarmWorkflow

    wf = StrategicSwarmWorkflow.__new__(StrategicSwarmWorkflow)
    wf.reasoner = MagicMock()
    wf.web_search = MagicMock()
    wf.web_search.enabled = False

    state = _base_state()
    state["detected_scenario"] = None

    result = wf.map_equity_opportunities(state)

    assert result["equity_opportunities"] == []
    assert "skipped" in result["provenance"][-1].lower()
    wf.reasoner.refine_model.assert_not_called()


def test_map_equity_produces_opportunities():
    """map_equity_opportunities returns a list of EquityOpportunity."""
    from pydantic import BaseModel

    from strategic_swarm_agent.graph.workflow import StrategicSwarmWorkflow

    class _EquityList(BaseModel):
        opportunities: list[EquityOpportunity]

    expected_opps = [
        EquityOpportunity(symbol="REP.MC", company_name="Repsol", direction="long",
                          rationale="Venezuela operations become critical.", scenario_link="Alternative suppliers gain", confidence=0.75),
        EquityOpportunity(symbol="ARAMCO.SR", company_name="Saudi Aramco", direction="short",
                          rationale="Export routes blocked.", scenario_link="Hormuz disrupted", confidence=0.8),
    ]
    equity_list = _EquityList(opportunities=expected_opps)

    scenario = ScenarioDetection(
        scenario_name="US-Iran Military Escalation",
        scenario_type="geopolitical_conflict",
        key_actors=["US", "Iran"],
        geographic_scope=["Middle East"],
        consequence_chain=["US strikes Iran", "Hormuz disrupted", "Alternative suppliers gain"],
        confidence=0.85,
    )

    wf = StrategicSwarmWorkflow.__new__(StrategicSwarmWorkflow)
    wf.reasoner = MagicMock()
    wf.reasoner.refine_model.return_value = (equity_list, {"llm_used": True, "llm_status": "ok"})
    wf.web_search = MagicMock()
    wf.web_search.enabled = False

    state = _base_state()
    state["detected_scenario"] = scenario

    result = wf.map_equity_opportunities(state)

    assert len(result["equity_opportunities"]) == 2
    symbols = [o.symbol for o in result["equity_opportunities"]]
    assert "REP.MC" in symbols
    assert "ARAMCO.SR" in symbols
    assert result["diagnostics"]["equity_opportunity_count"] == 2
    assert "US-Iran Military Escalation" in result["provenance"][-1]


# ── render_markdown with scenario + equity ────────────────────────────────────

def test_render_markdown_includes_scenario_and_equity():
    """render_markdown emits Detected Scenario and Equity Signals sections."""
    scenario = ScenarioDetection(
        scenario_name="Energy Crisis",
        scenario_type="energy_crisis",
        key_actors=["OPEC", "US"],
        geographic_scope=["Global"],
        consequence_chain=["Supply cut", "Price spike", "Refiners squeezed"],
        confidence=0.9,
    )
    equity = [
        EquityOpportunity(
            symbol="XOM",
            company_name="ExxonMobil",
            direction="long",
            rationale="Benefits from price spike.",
            scenario_link="Price spike",
            confidence=0.8,
        )
    ]
    report = FinalReport(
        publication_status="publish",
        executive_summary="Test summary.",
        system_topology="Empire: OPEC. Disruptor: US shale.",
        detected_scenario=scenario,
        equity_opportunities=equity,
    )
    md = render_markdown(report)

    assert "## Detected Scenario" in md
    assert "Energy Crisis" in md
    assert "Supply cut" in md  # consequence chain step
    assert "## Equity Signals" in md
    assert "XOM" in md
    assert "LONG" in md
    assert "ExxonMobil" in md


def test_render_markdown_without_scenario_has_no_scenario_section():
    """render_markdown omits scenario section when detected_scenario is None."""
    report = FinalReport(
        publication_status="monitor_only",
        executive_summary="No scenario.",
        system_topology="Unknown.",
        detected_scenario=None,
        equity_opportunities=[],
        monitor_only_reason="Low confidence.",
    )
    md = render_markdown(report)
    assert "## Detected Scenario" not in md
    assert "## Equity Signals" not in md
