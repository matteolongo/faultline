from datetime import datetime, timezone

from faultline.models import (
    ActionRecommendation,
    FinalReport,
    MarketImplication,
    Prediction,
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


def test_prediction_model_is_explicit_about_horizon() -> None:
    prediction = Prediction(
        prediction_type="narrative",
        description="Coverage shifts toward platform bypass.",
        rationale="The system is leaving one-off event framing.",
        time_horizon="days to weeks",
        confidence=0.74,
    )
    assert prediction.time_horizon == "days to weeks"


def test_market_implication_tracks_thesis_type() -> None:
    implication = MarketImplication(
        target="Open ecosystem enablers",
        direction="positive",
        thesis_type="asymmetric_opportunity",
        rationale="Modular layers win when portability rises.",
        time_horizon="1-3 months",
        confidence=0.72,
    )
    assert implication.thesis_type == "asymmetric_opportunity"


def test_final_report_fields_are_serializable() -> None:
    report = FinalReport(
        headline="Open model breakout",
        executive_summary="Summary",
        why_now="Why now",
        situation="Situation",
        stage="repricing",
        system_map=["Actor map"],
        mechanism_map=["Platform bypass"],
        scenario_map=["Actor move"],
        market_implications=["Implication"],
        actions_now=["WATCH target"],
        exit_signals=["EXIT target"],
        risks=["Risk"],
        open_questions=["Question"],
        invalidation_signals=["Signal"],
        evidence=["Evidence"],
        references=["https://example.com"],
        provenance=["Trace"],
    )
    payload = report.model_dump()
    assert payload["stage"] == "repricing"
    assert payload["actions_now"] == ["WATCH target"]


def test_action_recommendation_accepts_watch_and_exit() -> None:
    watch = ActionRecommendation(action="watch", target="AAA", rationale="Wait for confirmation", confidence=0.6)
    exit_action = ActionRecommendation(action="exit", target="BBB", rationale="Thesis broke", confidence=0.8)
    assert watch.action == "watch"
    assert exit_action.action == "exit"
