from datetime import UTC, datetime

from faultline.graph.runner import StrategicSwarmRunner
from faultline.intake import TopicChatIntake
from faultline.models import RawSignal


class _FakeWebSearchProvider:
    provider_name = "openai-websearch"
    source_family = "synthesis"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def query(self, question: str, *, story_key: str, fetched_at: datetime) -> list[RawSignal]:
        index = len(self.calls)
        self.calls.append(question)
        return [
            RawSignal(
                id=f"web-{index}",
                provider_name=self.provider_name,
                provider_item_id=f"web-{index}",
                source=self.source_family,
                timestamp=fetched_at,
                fetched_at=fetched_at,
                published_at=fetched_at,
                signal_type="news-synthesis",
                title="Iran conflict disrupts energy shipping lanes",
                summary=f"{question} Evidence points to pressure on energy flows and shipping insurance.",
                source_url=f"https://example.com/web/{index}",
                query_key=story_key,
                region="Global",
                entities=["Iran", "Israel", "Strait of Hormuz"],
                tags=["energy", "shipping", "market-stress", "chokepoint"],
                confidence=0.82,
                payload={},
            )
        ]


class _FakeMacroProvider:
    provider_name = "macro-fake"
    source_family = "macro"

    def fetch_window(self, start_at: datetime, end_at: datetime) -> list[RawSignal]:
        return [
            RawSignal(
                id="macro-1",
                provider_name=self.provider_name,
                provider_item_id="macro-1",
                source=self.source_family,
                timestamp=end_at,
                fetched_at=end_at,
                published_at=end_at,
                signal_type="macro-observation",
                title="Oil spike pushes inflation expectations higher",
                summary="Rates, freight costs, and energy imports are repricing after the conflict shock.",
                source_url="https://example.com/macro/1",
                query_key="macro-1",
                region="Global",
                entities=["Oil", "Inflation"],
                tags=["energy", "market-stress", "chokepoint"],
                confidence=0.8,
                payload={},
            )
        ]


def test_topic_chat_topic_only_produces_first_question() -> None:
    intake = TopicChatIntake()
    session = intake.start_session("Iran war")

    assert session.status == "exploring"
    assert session.current_field == "analysis_goal"
    assert session.current_question is not None
    assert "optimize for" in session.current_question


def test_topic_chat_multi_turn_reaches_ready_state() -> None:
    intake = TopicChatIntake()
    session = intake.start_session("Iran war")
    session = intake.answer_question(session, "listed companies and symbols")
    session = intake.answer_question(session, "Global")
    session = intake.answer_question(session, "3 months")
    session = intake.answer_question(session, "listed companies and ETFs")

    assert session.status == "ready"
    assert session.brief.analysis_goal == "listed_companies"
    assert session.brief.geographic_scope == "Global"
    assert session.brief.time_horizon == "3 months"
    assert session.brief.target_universe == "listed_companies_and_etfs"
    assert len(session.turns) == 4


def test_topic_chat_clear_prompt_reaches_ready_quickly() -> None:
    intake = TopicChatIntake()
    session = intake.start_session(
        "Deep dive on Iran war impact on global inflation and listed defense/energy names over 3 months"
    )

    assert session.status == "ready"
    assert session.brief.analysis_goal == "macro_transmission"
    assert session.brief.geographic_scope == "Global"
    assert session.brief.time_horizon == "3 months"
    assert session.brief.target_universe == "listed_companies_and_etfs"


def test_runner_topic_chat_produces_report_with_provenance(tmp_path) -> None:
    runner = StrategicSwarmRunner(
        output_dir=tmp_path / "outputs",
        database_url=f"sqlite:///{tmp_path / 'runs.sqlite'}",
        live_providers=[_FakeMacroProvider()],
        web_search_provider=_FakeWebSearchProvider(),
    )
    session = runner.prepare_topic_chat(
        "Deep dive on Iran war impact on global inflation and listed defense/energy names over 3 months"
    )

    result = runner.run_topic_chat(
        session,
        start_at=datetime(2026, 3, 8, tzinfo=UTC),
        end_at=datetime(2026, 3, 9, tzinfo=UTC),
    )

    report = result["final_state"]["final_report"]
    diagnostics = result["final_state"]["diagnostics"]

    assert report.topic_prompt == "Deep dive on Iran war impact on global inflation and listed defense/energy names over 3 months"
    assert report.deep_dive_objective
    assert len(report.retrieval_questions) >= 3
    assert diagnostics["topic_chat_turn_count"] == 0
    assert diagnostics["topic_prompt"].startswith("Deep dive on Iran war")
