from __future__ import annotations

from datetime import datetime, timezone

from faultline.graph.workflow import StrategicSwarmWorkflow
from faultline.models import EventCluster, RawSignal
from faultline.persistence.store import SignalStore
from faultline.providers.normalizer import SignalNormalizer
from faultline.synthesis.report_builder import render_markdown


def _make_cluster() -> EventCluster:
    return EventCluster(
        cluster_id="c1",
        story_key="global::open-source-protocol",
        canonical_title="Open stack pressures bundled incumbent",
        summary="Customers seek portability while the incumbent defends pricing.",
        region="Global",
        entities=["Open Builder Network", "Enterprise Cloud Suite"],
        tags=["open-source", "protocol", "market-stress", "portability"],
        source_families=["news", "market"],
        signal_ids=["sig-1", "sig-2"],
        first_seen_at=datetime(2026, 3, 9, tzinfo=timezone.utc),
        last_seen_at=datetime(2026, 3, 9, tzinfo=timezone.utc),
        novelty_score=0.9,
        agreement_score=0.8,
        cluster_strength=0.85,
    )


def _make_state(cluster: EventCluster | None = None) -> dict:
    raw = [
        RawSignal(
            id="sig-1",
            provider_name="sample",
            provider_item_id="sig-1",
            source="news",
            timestamp=datetime(2026, 3, 9, tzinfo=timezone.utc),
            fetched_at=datetime(2026, 3, 9, tzinfo=timezone.utc),
            published_at=datetime(2026, 3, 9, tzinfo=timezone.utc),
            signal_type="technology",
            title="Open stack pressures bundled incumbent",
            summary="Customers seek portability while the incumbent defends pricing.",
            source_url="https://example.com/open",
            region="Global",
            tags=["open-source", "protocol", "portability"],
            confidence=0.8,
            entities=["Open Builder Network", "Enterprise Cloud Suite"],
            payload={},
        ),
        RawSignal(
            id="sig-2",
            provider_name="sample",
            provider_item_id="sig-2",
            source="market",
            timestamp=datetime(2026, 3, 10, tzinfo=timezone.utc),
            fetched_at=datetime(2026, 3, 10, tzinfo=timezone.utc),
            published_at=datetime(2026, 3, 10, tzinfo=timezone.utc),
            signal_type="market",
            title="Incumbent bundle sees margin pressure",
            summary="Market pricing starts to reflect platform bypass risk.",
            source_url="https://example.com/mkt",
            region="Global",
            tags=["market-stress", "pricing-power"],
            confidence=0.75,
            entities=["Enterprise Cloud Suite"],
            payload={},
        ),
    ]
    normalized_events, normalized_clusters, _ = SignalNormalizer().normalize(raw)
    inferred_cluster = normalized_clusters[0]
    c = (cluster or _make_cluster()).model_copy(
        update={
            "cluster_id": inferred_cluster.cluster_id,
            "story_key": inferred_cluster.story_key,
        }
    )
    return {
        "event_clusters": [c],
        "selected_cluster": c,
        "normalized_events": normalized_events,
        "provenance": [],
        "diagnostics": {},
        "run_mode": "demo",
    }


def test_retrieve_related_situations_returns_memory_hits(tmp_path) -> None:
    wf = StrategicSwarmWorkflow(store=SignalStore(f"sqlite:///{tmp_path / 'runs.sqlite'}"), live_providers=[])
    cluster = _make_cluster()
    state = _make_state(cluster)

    previous_cluster = cluster.model_copy(
        update={"cluster_id": "prior-1", "canonical_title": "Earlier open stack stress"}
    )
    previous_snapshot = wf.mapper.map(previous_cluster, state["normalized_events"], [])
    wf.memory.remember(previous_snapshot)

    result = wf.retrieve_related_situations(state)

    assert result["related_situations"]
    assert result["related_situations"][0].situation_id == "prior-1"


def test_map_situation_generates_snapshot_and_predictions(tmp_path) -> None:
    wf = StrategicSwarmWorkflow(store=SignalStore(f"sqlite:///{tmp_path / 'runs.sqlite'}"), live_providers=[])
    state = _make_state()
    mapped = wf.map_situation({**state, "related_situations": []})
    assert mapped["situation_snapshot"] is not None
    assert mapped["situation_snapshot"].mechanisms

    predictions = wf.generate_predictions({**state, **mapped})
    assert predictions["predictions"]
    assert any(item.prediction_type == "actor_move" for item in predictions["predictions"])


def test_render_markdown_includes_actions_and_evidence(tmp_path) -> None:
    wf = StrategicSwarmWorkflow(store=SignalStore(f"sqlite:///{tmp_path / 'runs.sqlite'}"), live_providers=[])
    state = _make_state()
    mapped = wf.map_situation({**state, "related_situations": []})
    predictions = wf.generate_predictions({**state, **mapped})
    implications = wf.map_market_implications({**state, **mapped, **predictions})
    actions = wf.generate_actions({**state, **mapped, **predictions, **implications})
    report_state = wf.synthesize_report({**state, **mapped, **predictions, **implications, **actions})

    md = render_markdown(report_state["final_report"])

    assert "## Active Mechanisms" in md
    assert "## Actions Now" in md
    assert "## Exit Signals" in md
    assert "## Evidence" in md
