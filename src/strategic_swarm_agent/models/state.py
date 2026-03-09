from __future__ import annotations

from typing import Any, TypedDict

from strategic_swarm_agent.models.contracts import (
    AbstractPattern,
    EventCluster,
    EquityOpportunity,
    FinalReport,
    FragilityAssessment,
    OpportunityIdea,
    ProviderHealthStatus,
    RawSignal,
    ReviewedOpportunity,
    RippleScenario,
    ScenarioDetection,
    SignalBundle,
    SignalEvent,
)


class SwarmGraphState(TypedDict, total=False):
    scenario_id: str
    run_mode: str
    window_start: str
    window_end: str
    raw_signals: list[RawSignal]
    normalized_events: list[SignalEvent]
    event_clusters: list[EventCluster]
    selected_cluster: EventCluster | None
    abstract_patterns: list[AbstractPattern]
    signal_bundles: list[SignalBundle]
    fragility_assessments: list[FragilityAssessment]
    ripple_scenarios: list[RippleScenario]
    candidate_opportunities: list[OpportunityIdea]
    reviewed_opportunities: list[ReviewedOpportunity]
    final_report: FinalReport | None
    diagnostics: dict[str, Any]
    provenance: list[str]
    provider_health: list[ProviderHealthStatus]
    opportunity_retry_count: int
    max_opportunity_retries: int
    detected_scenario: ScenarioDetection | None
    equity_opportunities: list[EquityOpportunity]
