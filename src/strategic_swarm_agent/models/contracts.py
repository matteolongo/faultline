from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ScoreDetail(BaseModel):
    value: float = Field(ge=0.0, le=1.0)
    explanation: str


class RawSignal(BaseModel):
    id: str
    source: str
    timestamp: datetime
    signal_type: str
    title: str
    summary: str
    entities: list[str] = Field(default_factory=list)
    region: str
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    payload: dict[str, Any] = Field(default_factory=dict)


class SignalEvent(BaseModel):
    id: str
    source: str
    timestamp: datetime
    signal_type: str
    title: str
    summary: str
    entities: list[str] = Field(default_factory=list)
    region: str
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    novelty: float = Field(ge=0.0, le=1.0)
    possible_systemic_relevance: float = Field(ge=0.0, le=1.0)
    raw_payload_reference: str


class HistoricalAnalog(BaseModel):
    name: str
    reference: str
    why_relevant: str


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


class FinalReport(BaseModel):
    executive_summary: str
    system_topology: str
    fragility_map: list[str] = Field(default_factory=list)
    ripple_map: list[str] = Field(default_factory=list)
    opportunity_map: list[str] = Field(default_factory=list)
    execution_recommendations: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    invalidation_signals: list[str] = Field(default_factory=list)
    provenance: list[str] = Field(default_factory=list)


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
