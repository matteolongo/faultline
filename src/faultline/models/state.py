from __future__ import annotations

from typing import Any

from typing_extensions import TypedDict

from faultline.models.contracts import (
    ActionRecommendation,
    EventCluster,
    FinalReport,
    MarketImplication,
    OutcomeRecord,
    Prediction,
    ProviderHealthStatus,
    RawSignal,
    RelatedSituation,
    SignalEvent,
    SituationSnapshot,
)


class FaultlineInputSchema(TypedDict, total=False):
    scenario_id: str
    run_mode: str
    window_start: str
    window_end: str


class FaultlineState(TypedDict, total=False):
    scenario_id: str
    run_mode: str
    window_start: str
    window_end: str
    raw_signals: list[RawSignal]
    normalized_events: list[SignalEvent]
    event_clusters: list[EventCluster]
    selected_cluster: EventCluster | None
    related_situations: list[RelatedSituation]
    situation_snapshot: SituationSnapshot | None
    predictions: list[Prediction]
    market_implications: list[MarketImplication]
    action_recommendations: list[ActionRecommendation]
    exit_signals: list[ActionRecommendation]
    outcome_records: list[OutcomeRecord]
    final_report: FinalReport | None
    diagnostics: dict[str, Any]
    provenance: list[str]
    provider_health: list[ProviderHealthStatus]
