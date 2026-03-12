import json
from datetime import UTC, datetime

from faultline.graph.runner import StrategicSwarmRunner
from faultline.models import RawSignal


class _FakeWebSearchProvider:
    provider_name = "openai-websearch"
    source_family = "synthesis"

    def query(self, question: str, *, story_key: str, fetched_at: datetime) -> list[RawSignal]:
        return [
            RawSignal(
                id="energy-1",
                provider_name=self.provider_name,
                provider_item_id="energy-1",
                source=self.source_family,
                timestamp=fetched_at,
                fetched_at=fetched_at,
                published_at=fetched_at,
                signal_type="news-synthesis",
                title="Hormuz disruption raises tanker insurance costs",
                summary=f"{question} Energy and shipping channels tighten.",
                source_url="https://example.com/energy-1",
                query_key=story_key,
                region="Global",
                entities=["Iran", "Hormuz"],
                tags=["energy", "shipping", "market-stress", "chokepoint"],
                confidence=0.82,
                payload={},
            ),
            RawSignal(
                id="noise-1",
                provider_name=self.provider_name,
                provider_item_id="noise-1",
                source=self.source_family,
                timestamp=fetched_at,
                fetched_at=fetched_at,
                published_at=fetched_at,
                signal_type="news-synthesis",
                title="Tech exporters face inventory pressure in Europe",
                summary=f"{question} EV oversupply adds margin pressure.",
                source_url="https://example.com/noise-1",
                query_key=story_key,
                region="Europe",
                entities=["Europe", "Exporters"],
                tags=["competition", "margin-pressure"],
                confidence=0.71,
                payload={},
            ),
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
                source_url="https://example.com/macro-1",
                query_key="macro-1",
                region="Global",
                entities=["Oil", "Inflation"],
                tags=["energy", "market-stress", "chokepoint"],
                confidence=0.8,
                payload={},
            )
        ]


def _start_review(tmp_path):
    runner = StrategicSwarmRunner(
        output_dir=tmp_path / "outputs",
        database_url=f"sqlite:///{tmp_path / 'runs.sqlite'}",
        live_providers=[_FakeMacroProvider()],
        web_search_provider=_FakeWebSearchProvider(),
    )
    topic_session = runner.prepare_topic_chat(
        "Deep dive on Iran war impact on global inflation and listed defense/energy names over 3 months"
    )
    review = runner.start_review_session(
        mode="topic_chat",
        topic_session=topic_session,
        start_at=datetime(2026, 3, 8, tzinfo=UTC),
        end_at=datetime(2026, 3, 9, tzinfo=UTC),
    )
    return runner, review


def _advance_to(runner: StrategicSwarmRunner, review, node_id: str):
    current = review
    while current.status != "completed" and current.current_node_id != node_id:
        current = runner.approve_review_step(current)
    return current


def _complete(runner: StrategicSwarmRunner, review):
    current = review
    while current.status != "completed":
        current = runner.approve_review_step(current)
    return current


def test_review_session_starts_on_ingest_with_signal_preview(tmp_path) -> None:
    _runner, review = _start_review(tmp_path)

    assert review.current_node_id == "ingest_signals"
    assert review.steps[0].status == "paused"
    assert len(review.steps[0].preview_payload["signals"]) >= 3
    assert review.steps[1].status == "pending"


def test_review_session_normalize_edits_update_cluster_selection(tmp_path) -> None:
    runner, review = _start_review(tmp_path)
    review = _advance_to(runner, review, "normalize_events")
    initial_cluster_id = review.steps[1].editable_payload["selected_cluster_id"]

    review = runner.apply_review_edits(
        review,
        edits={"excluded_signal_ids": ["energy-1", "macro-1"], "selected_cluster_id": None},
    )

    current = next(step for step in review.steps if step.node_id == "normalize_events")
    assert sorted(current.editable_payload["excluded_signal_ids"]) == ["energy-1", "macro-1"]
    assert current.preview_payload["selected_cluster_id"] != initial_cluster_id


def test_review_session_situation_edits_flow_into_report_headline(tmp_path) -> None:
    runner, review = _start_review(tmp_path)
    review = _advance_to(runner, review, "map_situation")

    review = runner.apply_review_edits(
        review,
        edits={
            "title": "Custom situation title",
            "summary": "Custom summary for review flow.",
            "system_under_pressure": "Energy logistics",
        },
    )
    review = _complete(runner, review)

    assert review.final_state["final_report"]["headline"] == "Custom situation title"
    assert review.final_state["situation_snapshot"]["system_under_pressure"] == "Energy logistics"


def test_review_session_implication_and_report_edits_persist(tmp_path) -> None:
    runner, review = _start_review(tmp_path)
    review = _advance_to(runner, review, "map_market_implications")
    first_implication = review.steps[6].editable_payload["market_implications"][0]

    review = runner.apply_review_edits(
        review,
        edits={
            "market_implications": [
                {
                    **first_implication,
                    "target": "Edited energy beneficiaries",
                }
            ]
        },
    )
    review = _advance_to(runner, review, "synthesize_report")
    review = runner.apply_review_edits(
        review,
        edits={
            "headline": "Custom report headline",
            "executive_summary": "Custom report summary",
        },
    )
    review = _complete(runner, review)

    assert review.final_state["market_implications"][0]["target"] == "Edited energy beneficiaries"
    assert review.final_state["final_report"]["headline"] == "Custom report headline"
    assert review.final_state["final_report"]["executive_summary"] == "Custom report summary"


def test_review_session_persists_node_aware_trace(tmp_path) -> None:
    runner, review = _start_review(tmp_path)
    review = _complete(runner, review)

    trace_path = tmp_path / "outputs" / "topic_chat" / review.selected_run_id / "trace.json"
    payload = json.loads(trace_path.read_text())

    assert len(payload["steps"]) == 10
    assert payload["steps"][0]["node_id"] == "ingest_signals"
    assert payload["steps"][-1]["node_id"] == "remember_situation"
    assert len(payload["snapshots"]) == 11
