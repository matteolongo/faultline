from datetime import datetime, timezone

from strategic_swarm_agent.models import (
    FinalReport,
    OpportunityIdea,
    ScoreDetail,
    SignalEvent,
)


def test_signal_event_model_validates_required_fields() -> None:
    event = SignalEvent(
        id="sig-1",
        source="news",
        timestamp=datetime.now(timezone.utc),
        signal_type="technology",
        title="Open stack pressures incumbent",
        summary="Summary",
        entities=["Open Builder Network"],
        region="Global",
        tags=["open-source"],
        confidence=0.8,
        novelty=0.7,
        possible_systemic_relevance=0.8,
        raw_payload_reference="news:sig-1",
    )
    assert event.source == "news"
    assert event.novelty == 0.7


def test_opportunity_idea_uses_explained_convexity() -> None:
    idea = OpportunityIdea(
        thesis="Long picks-and-shovels",
        direction="long",
        exposure_type="theme",
        related_assets_or_theme=["tooling"],
        why_convex="Indirect beneficiary",
        catalyst="Demand rotation",
        invalidation="No rotation",
        time_horizon="6 months",
        convexity_score=ScoreDetail(value=0.72, explanation="Indirect exposure"),
        confidence=0.75,
        crowdedness_risk=0.3,
        directness="indirect",
    )
    assert idea.convexity_score.value > 0.7


def test_final_report_fields_are_serializable() -> None:
    report = FinalReport(
        executive_summary="Summary",
        system_topology="Empire: A. Disruptor: B.",
        fragility_map=["Item"],
        ripple_map=["Ripple"],
        opportunity_map=["Opportunity"],
        execution_recommendations=["Recommendation"],
        open_questions=["Question"],
        invalidation_signals=["Signal"],
        provenance=["Trace"],
    )
    assert report.model_dump()["system_topology"].startswith("Empire:")
