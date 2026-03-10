from datetime import UTC, datetime

from faultline.models import RawSignal
from faultline.providers.normalizer import SignalNormalizer


def test_normalizer_dedupes_and_clusters_cross_source_story() -> None:
    now = datetime.now(UTC)
    raw = [
        RawSignal(
            id="1",
            provider_name="newsapi",
            provider_item_id="a",
            source="news",
            timestamp=now,
            fetched_at=now,
            published_at=now,
            signal_type="news",
            title="Undersea cable bypass gains support",
            summary="Operators shift toward alternate routes and monitoring.",
            source_url="https://a.example/story",
            region="Arctic",
            tags=["undersea", "bypass", "monitoring"],
            confidence=0.8,
            payload={},
        ),
        RawSignal(
            id="2",
            provider_name="gdelt",
            provider_item_id="b",
            source="alt",
            timestamp=now,
            fetched_at=now,
            published_at=now,
            signal_type="alt-event",
            title="Arctic operators discuss cable rerouting",
            summary="Repeated sabotage risk pushes the network toward bypass routes.",
            source_url="https://b.example/story",
            region="Arctic",
            tags=["cable", "rerouting", "sabotage"],
            confidence=0.7,
            payload={},
        ),
        RawSignal(
            id="3",
            provider_name="newsapi",
            provider_item_id="a-dup",
            source="news",
            timestamp=now,
            fetched_at=now,
            published_at=now,
            signal_type="news",
            title="Undersea cable bypass gains support",
            summary="Operators shift toward alternate routes and monitoring.",
            source_url="https://a.example/story-duplicate",
            region="Arctic",
            tags=["undersea", "bypass", "monitoring"],
            confidence=0.8,
            dedupe_hash="shared-hash",
            payload={},
        ),
    ]
    raw[0].dedupe_hash = "shared-hash"
    events, clusters, diagnostics = SignalNormalizer().normalize(raw)
    assert diagnostics["duplicates_removed"] == 1
    assert len(clusters) == 1
    assert set(clusters[0].source_families) == {"alt", "news"}
    assert all(event.cluster_id == clusters[0].cluster_id for event in events)
