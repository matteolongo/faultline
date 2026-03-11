from __future__ import annotations

from typing import Any

from typing_extensions import TypedDict

from faultline.models.contracts import (
    ActionRecommendation,
    CalibrationSignal,
    ChatIntakeSession,
    EventCluster,
    FinalReport,
    MarketImplication,
    OperatorPolicyConfig,
    OutcomeRecord,
    PortfolioPosition,
    Prediction,
    ProviderHealthStatus,
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


class FaultlineInputSchema(TypedDict, total=False):
    scenario_id: str
    run_mode: str
    window_start: str
    window_end: str
    portfolio_positions: list[PortfolioPosition]
    watchlist: list[WatchlistEntry]
    operator_policy_config: OperatorPolicyConfig
    topic_prompt: TopicPrompt
    research_brief: ResearchBrief
    chat_intake_session: ChatIntakeSession
    retrieval_questions: list[str]


class FaultlineState(TypedDict, total=False):
    scenario_id: str
    run_mode: str
    window_start: str
    window_end: str
    portfolio_positions: list[PortfolioPosition]
    watchlist: list[WatchlistEntry]
    operator_policy_config: OperatorPolicyConfig
    topic_prompt: TopicPrompt
    research_brief: ResearchBrief
    chat_intake_session: ChatIntakeSession
    retrieval_questions: list[str]
    raw_signals: list[RawSignal]
    normalized_events: list[SignalEvent]
    event_clusters: list[EventCluster]
    selected_cluster: EventCluster | None
    related_situations: list[RelatedSituation]
    calibration_signals: list[CalibrationSignal]
    situation_snapshot: SituationSnapshot | None
    predictions: list[Prediction]
    scenario_tree: list[ScenarioPath]
    stage_transition_warnings: list[StageTransitionWarning]
    market_implications: list[MarketImplication]
    action_recommendations: list[ActionRecommendation]
    exit_signals: list[ActionRecommendation]
    endangered_symbols: list[str]
    outcome_records: list[OutcomeRecord]
    final_report: FinalReport | None
    diagnostics: dict[str, Any]
    provenance: list[str]
    provider_health: list[ProviderHealthStatus]
