from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


class ScoreDetail(BaseModel):
    value: float = Field(ge=0.0, le=1.0)
    explanation: str


class RawSignal(BaseModel):
    id: str
    provider_name: str | None = None
    provider_item_id: str | None = None
    source: str
    timestamp: datetime
    fetched_at: datetime | None = None
    published_at: datetime | None = None
    signal_type: str
    title: str
    summary: str
    source_url: str | None = None
    request_url: str | None = None
    query_key: str | None = None
    language: str | None = None
    entities: list[str] = Field(default_factory=list)
    region: str
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    provider_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    content_hash: str | None = None
    dedupe_hash: str | None = None
    raw_payload_reference: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def populate_defaults(self) -> "RawSignal":
        if self.provider_name is None:
            self.provider_name = self.source
        if self.provider_item_id is None:
            self.provider_item_id = self.id
        if self.fetched_at is None:
            self.fetched_at = self.timestamp
        if self.published_at is None:
            self.published_at = self.timestamp
        if self.provider_confidence is None:
            self.provider_confidence = self.confidence
        if self.content_hash is None:
            self.content_hash = hashlib.sha256(f"{self.title} {self.summary}".encode("utf-8")).hexdigest()
        if self.dedupe_hash is None:
            self.dedupe_hash = hashlib.sha256(
                f"{(self.source_url or '').lower()}::{self.title.lower().strip()}".encode("utf-8")
            ).hexdigest()
        if self.raw_payload_reference is None:
            self.raw_payload_reference = f"{self.provider_name}:{self.provider_item_id}"
        return self


class SignalEvent(BaseModel):
    id: str
    provider_name: str | None = None
    source: str
    timestamp: datetime
    fetched_at: datetime | None = None
    published_at: datetime | None = None
    signal_type: str
    title: str
    summary: str
    source_url: str | None = None
    language: str | None = None
    entities: list[str] = Field(default_factory=list)
    region: str
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    provider_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    novelty: float = Field(ge=0.0, le=1.0)
    possible_systemic_relevance: float = Field(ge=0.0, le=1.0)
    cluster_id: str | None = None
    story_key: str | None = None
    dedupe_hash: str | None = None
    source_families: list[str] = Field(default_factory=list)
    query_key: str | None = None
    raw_payload_reference: str

    @model_validator(mode="after")
    def populate_event_defaults(self) -> "SignalEvent":
        if self.provider_name is None:
            self.provider_name = self.source
        if self.fetched_at is None:
            self.fetched_at = self.timestamp
        if self.provider_confidence is None:
            self.provider_confidence = self.confidence
        if self.story_key is None:
            self.story_key = self.id
        if self.cluster_id is None:
            self.cluster_id = self.id
        if self.dedupe_hash is None:
            self.dedupe_hash = self.id
        return self


class HistoricalAnalog(BaseModel):
    name: str
    reference: str
    why_relevant: str


class Archetype(BaseModel):
    id: str
    name: str
    empire_type: str
    disruptor_type: str
    asymmetry_type: str
    trigger_tags: list[str] = Field(default_factory=list)
    cheap_weapon_examples: list[str] = Field(default_factory=list)
    analog_refs: list[str] = Field(default_factory=list)


class FragilityPattern(BaseModel):
    name: str
    description: str
    trigger_tags: list[str] = Field(default_factory=list)


class EventCluster(BaseModel):
    cluster_id: str
    story_key: str
    canonical_title: str
    summary: str
    region: str
    language: str | None = None
    entities: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    source_families: list[str] = Field(default_factory=list)
    signal_ids: list[str] = Field(default_factory=list)
    first_seen_at: datetime
    last_seen_at: datetime
    novelty_score: float = Field(ge=0.0, le=1.0)
    agreement_score: float = Field(ge=0.0, le=1.0)
    cluster_strength: float = Field(ge=0.0, le=1.0)


class Actor(BaseModel):
    name: str
    actor_type: str = "organization"
    role: str = "participant"
    objectives: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    resources: list[str] = Field(default_factory=list)
    alliances: list[str] = Field(default_factory=list)
    narrative_position: str | None = None
    adaptability: float = Field(default=0.5, ge=0.0, le=1.0)
    influence: float = Field(default=0.5, ge=0.0, le=1.0)


class Force(BaseModel):
    force_type: str
    description: str
    strength: float = Field(ge=0.0, le=1.0)
    directional_bias: str = "mixed"


class Relation(BaseModel):
    relation_type: str
    source_actor: str
    target_actor: str
    description: str
    strength: float = Field(default=0.5, ge=0.0, le=1.0)


class Mechanism(BaseModel):
    mechanism_id: str
    name: str
    status: str = "active"
    explanation: str
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class EvidenceItem(BaseModel):
    signal_id: str
    title: str
    summary: str
    source: str
    source_url: str | None = None
    rationale: str


class StageAssessment(BaseModel):
    stage: str
    explanation: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class CalibrationSignal(BaseModel):
    prediction_type: str
    sample_size: int = Field(ge=0)
    confirmed_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    partial_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    unconfirmed_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    average_confidence_delta: float = Field(default=0.0, ge=-1.0, le=1.0)
    guidance: str


class Prediction(BaseModel):
    prediction_id: str | None = None
    prediction_type: str
    description: str
    rationale: str
    time_horizon: str
    related_actors: list[str] = Field(default_factory=list)
    affected_assets: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    status: str = "pending"

    @model_validator(mode="after")
    def populate_prediction_id(self) -> "Prediction":
        if self.prediction_id is None:
            seed = "::".join(
                [
                    self.prediction_type,
                    self.description,
                    self.time_horizon,
                    ",".join(self.related_actors),
                    ",".join(self.affected_assets),
                ]
            )
            self.prediction_id = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
        return self


class ScenarioPath(BaseModel):
    name: str
    probability: float = Field(default=0.5, ge=0.0, le=1.0)
    trigger_signals: list[str] = Field(default_factory=list)
    expected_moves: list[str] = Field(default_factory=list)
    market_effects: list[str] = Field(default_factory=list)
    timeframe: str = "near-term"


class MarketImplication(BaseModel):
    target: str
    implication_type: str = "asset"
    direction: str
    thesis_type: str
    rationale: str
    time_horizon: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    references: list[str] = Field(default_factory=list)


class ActionRecommendation(BaseModel):
    action: str
    target: str
    rationale: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    urgency: str = "medium"
    thesis_type: str | None = None


class PortfolioPosition(BaseModel):
    symbol: str
    direction: str = "long"
    quantity: float = 1.0
    cost_basis: float | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None


class WatchlistEntry(BaseModel):
    symbol: str
    bias: str | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None


class ExitSignal(BaseModel):
    target: str
    description: str
    trigger_type: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class RelatedSituation(BaseModel):
    situation_id: str
    title: str
    summary: str
    matched_on: list[str] = Field(default_factory=list)
    mechanisms: list[str] = Field(default_factory=list)
    similarity_score: float = Field(default=0.0, ge=0.0, le=1.0)


class SituationSnapshot(BaseModel):
    situation_id: str
    title: str
    summary: str
    domain: str = "complex_system"
    system_under_pressure: str
    key_actors: list[Actor] = Field(default_factory=list)
    forces: list[Force] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
    mechanisms: list[Mechanism] = Field(default_factory=list)
    stage: StageAssessment
    risks: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class OutcomeRecord(BaseModel):
    prediction_id: str
    prediction_type: str
    target: str
    outcome_status: str
    explanation: str
    confidence_delta: float = Field(default=0.0, ge=-1.0, le=1.0)
    supporting_signal_ids: list[str] = Field(default_factory=list)


class AbstractPattern(BaseModel):
    pattern_name: str
    empire_type: str
    disruptor_type: str
    asymmetry_type: str
    empire_actor: str
    disruptor_actor: str
    cheap_weapon: str
    armor_breach: str
    historical_analogs: list[HistoricalAnalog] = Field(default_factory=list)
    explanation: str
    confidence: float = Field(ge=0.0, le=1.0)


class SignalBundle(BaseModel):
    bundle_id: str
    cluster_id: str
    source_families: list[str] = Field(default_factory=list)
    agreement_score: float = Field(ge=0.0, le=1.0)
    anomaly_tags: list[str] = Field(default_factory=list)
    pressure_indicators: list[str] = Field(default_factory=list)
    sentiment_entropy: ScoreDetail
    response_capacity: ScoreDetail
    supporting_signal_ids: list[str] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)


class FragilityAssessment(BaseModel):
    hubris_index: ScoreDetail
    energy_defense_ratio: ScoreDetail
    kinetic_ripple: ScoreDetail
    centralization_score: ScoreDetail
    redundancy_score: ScoreDetail
    fragility_score: ScoreDetail
    antifragility_attraction: ScoreDetail
    notes: list[str] = Field(default_factory=list)
    fragile_nodes: list[str] = Field(default_factory=list)
    antifragile_nodes: list[str] = Field(default_factory=list)


class RippleScenario(BaseModel):
    trigger: str
    first_order: list[str] = Field(default_factory=list)
    second_order: list[str] = Field(default_factory=list)
    third_order: list[str] = Field(default_factory=list)
    sectors_helped: list[str] = Field(default_factory=list)
    sectors_hurt: list[str] = Field(default_factory=list)
    capital_rotation: list[str] = Field(default_factory=list)
    fragile_nodes: list[str] = Field(default_factory=list)
    antifragile_nodes: list[str] = Field(default_factory=list)
    time_horizon: str
    confidence: float = Field(ge=0.0, le=1.0)


class OpportunityIdea(BaseModel):
    thesis: str
    direction: str
    exposure_type: str
    related_assets_or_theme: list[str] = Field(default_factory=list)
    why_convex: str
    catalyst: str
    invalidation: str
    time_horizon: str
    convexity_score: ScoreDetail
    confidence: float = Field(ge=0.0, le=1.0)
    crowdedness_risk: float = Field(ge=0.0, le=1.0)
    directness: str


class ReviewedOpportunity(BaseModel):
    idea: OpportunityIdea
    approved: bool
    review_summary: str
    rejection_reasons: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)


class ScenarioDetection(BaseModel):
    scenario_name: str
    scenario_type: str
    key_actors: list[str] = Field(default_factory=list)
    geographic_scope: list[str] = Field(default_factory=list)
    consequence_chain: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class EquityOpportunity(BaseModel):
    symbol: str
    company_name: str
    direction: str
    rationale: str
    scenario_link: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    search_summary: str | None = None


class FinalReport(BaseModel):
    publication_status: str = "publish"
    headline: str = ""
    executive_summary: str
    why_now: str = ""
    calibrated_conviction: float = Field(default=0.0, ge=0.0, le=1.0)
    system_topology: str = ""
    situation: str = ""
    stage: str = ""
    system_map: list[str] = Field(default_factory=list)
    mechanism_map: list[str] = Field(default_factory=list)
    scenario_map: list[str] = Field(default_factory=list)
    market_implications: list[str] = Field(default_factory=list)
    actions_now: list[str] = Field(default_factory=list)
    exit_signals: list[str] = Field(default_factory=list)
    endangered_symbols: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    invalidation_signals: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    calibration_notes: list[str] = Field(default_factory=list)
    provenance: list[str] = Field(default_factory=list)
    monitor_only_reason: str | None = None
    detected_scenario: ScenarioDetection | None = None
    equity_opportunities: list[EquityOpportunity] = Field(default_factory=list)

    # Legacy fields retained temporarily while old modules are phased out.
    fragility_map: list[str] = Field(default_factory=list)
    ripple_map: list[str] = Field(default_factory=list)
    opportunity_map: list[str] = Field(default_factory=list)
    execution_recommendations: list[str] = Field(default_factory=list)


class PublishedReport(BaseModel):
    report_id: str
    run_id: str
    cluster_id: str
    publication_status: str
    published_at: datetime
    report: FinalReport
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class ProviderHealthStatus(BaseModel):
    provider_name: str
    source_family: str
    enabled: bool
    configured: bool
    last_success_at: datetime | None = None
    last_error_at: datetime | None = None
    dead_letter_count: int = 0
    recent_signal_count: int = 0


class DeadLetterRecord(BaseModel):
    id: str
    provider_name: str
    window_start: datetime
    window_end: datetime
    failed_at: datetime
    request_url: str | None = None
    error_type: str
    error_message: str
    payload: dict[str, Any] = Field(default_factory=dict)
