from datetime import UTC, datetime

from faultline.graph.runner import StrategicSwarmRunner
from faultline.models import RawSignal, ResearchBrief


class _FakeWebSearchProvider:
    provider_name = "openai-websearch"
    source_family = "synthesis"

    def query(self, question: str, *, story_key: str, fetched_at: datetime) -> list[RawSignal]:
        signals = [
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
        return signals


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


def _workspace(tmp_path):
    runner = StrategicSwarmRunner(
        output_dir=tmp_path / "outputs",
        database_url=f"sqlite:///{tmp_path / 'runs.sqlite'}",
        live_providers=[_FakeMacroProvider()],
        web_search_provider=_FakeWebSearchProvider(),
    )
    topic_session = runner.prepare_topic_chat(
        "Deep dive on Iran war impact on global inflation and listed defense/energy names over 3 months"
    )
    workspace = runner.initialize_workspace(
        topic_session,
        start_at=datetime(2026, 3, 8, tzinfo=UTC),
        end_at=datetime(2026, 3, 9, tzinfo=UTC),
    )
    workspace.brief_checkpoint.approved_brief = topic_session.brief
    workspace.brief_checkpoint.status = "approved"
    return runner, workspace


def test_workspace_brief_edits_mark_downstream_stale(tmp_path) -> None:
    runner, workspace = _workspace(tmp_path)
    workspace = runner.build_evidence_checkpoint(workspace)
    workspace.evidence_checkpoint.status = "approved"
    workspace.evidence_checkpoint.approved_cluster_id = workspace.evidence_checkpoint.selected_cluster_id
    workspace = runner.build_situation_checkpoint(workspace)
    workspace.situation_checkpoint.status = "approved"

    edited = ResearchBrief.model_validate(
        {
            **workspace.brief_checkpoint.approved_brief.model_dump(mode="json"),
            "time_horizon": "6 months",
        }
    )
    workspace = runner.apply_brief_edits(workspace, edited)

    assert workspace.brief_checkpoint.status == "generated"
    assert workspace.evidence_checkpoint.status == "stale"
    assert workspace.situation_checkpoint.status == "stale"


def test_workspace_excluding_signal_changes_selected_cluster(tmp_path) -> None:
    runner, workspace = _workspace(tmp_path)
    workspace = runner.build_evidence_checkpoint(workspace)
    initial_cluster = workspace.evidence_checkpoint.selected_cluster_id

    workspace = runner.build_evidence_checkpoint(
        workspace,
        excluded_signal_ids=["energy-1", "macro-1"],
    )

    assert workspace.evidence_checkpoint.selected_cluster_id != initial_cluster
    assert workspace.evidence_checkpoint.excluded_signal_ids == ["energy-1", "macro-1"]


def test_workspace_implication_rerun_rebuilds_report_only(tmp_path) -> None:
    runner, workspace = _workspace(tmp_path)
    workspace = runner.rerun_from_checkpoint(workspace, "brief")
    workspace = runner.apply_implication_edits(
        workspace,
        implications=[
            {
                **workspace.implications_checkpoint.market_implications[0].model_dump(mode="json"),
                "target": "Edited energy beneficiaries",
            }
        ],
        actions=[item.model_dump(mode="json") for item in workspace.implications_checkpoint.action_recommendations],
    )

    assert workspace.report_checkpoint.status == "stale"

    workspace = runner.rerun_from_checkpoint(workspace, "implications")

    assert workspace.report_checkpoint.final_report is not None
    assert workspace.implications_checkpoint.market_implications[0].target == "Edited energy beneficiaries"


def test_workspace_report_edits_do_not_invalidate_upstream(tmp_path) -> None:
    runner, workspace = _workspace(tmp_path)
    workspace = runner.rerun_from_checkpoint(workspace, "brief")
    workspace = runner.apply_report_edits(
        workspace,
        headline="Custom headline",
        executive_summary="Custom summary",
    )

    assert workspace.report_checkpoint.final_report.headline == "Custom headline"
    assert workspace.implications_checkpoint.status in {"generated", "approved"}
