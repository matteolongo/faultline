from __future__ import annotations

from typing import Any, TypedDict

from strategic_swarm_agent.models.contracts import (
    AbstractPattern,
    FinalReport,
    FragilityAssessment,
    OpportunityIdea,
    RawSignal,
    ReviewedOpportunity,
    RippleScenario,
    SignalBundle,
    SignalEvent,
)


class SwarmGraphState(TypedDict, total=False):
    scenario_id: str
    raw_signals: list[RawSignal]
    normalized_events: list[SignalEvent]
    abstract_patterns: list[AbstractPattern]
    signal_bundles: list[SignalBundle]
    fragility_assessments: list[FragilityAssessment]
    ripple_scenarios: list[RippleScenario]
    candidate_opportunities: list[OpportunityIdea]
    reviewed_opportunities: list[ReviewedOpportunity]
    final_report: FinalReport | None
    diagnostics: dict[str, Any]
    provenance: list[str]
    opportunity_retry_count: int
    max_opportunity_retries: int
