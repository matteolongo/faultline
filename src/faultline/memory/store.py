from __future__ import annotations

import hashlib
import math
import re
from collections import Counter

from langgraph.store.memory import InMemoryStore

from faultline.models import EventCluster, RelatedSituation, SituationSnapshot


class HashingEmbedder:
    """Deterministic local embedder for tests and in-memory semantic retrieval."""

    def __init__(self, dims: int = 64) -> None:
        self.dims = dims

    def __call__(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dims
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        counts = Counter(tokens)
        for token, weight in counts.items():
            bucket = int(hashlib.md5(token.encode()).hexdigest(), 16) % self.dims
            vector[bucket] += float(weight)
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class SituationMemory:
    def __init__(self, *, dims: int = 64) -> None:
        self.namespace = ("situations",)
        self.store = InMemoryStore(index={"dims": dims, "embed": HashingEmbedder(dims), "fields": ["text"]})

    def bootstrap(self, snapshots: list[SituationSnapshot]) -> None:
        for snapshot in snapshots:
            self.remember(snapshot)

    def remember(self, snapshot: SituationSnapshot) -> None:
        mechanisms = ", ".join(item.name for item in snapshot.mechanisms)
        actors = ", ".join(item.name for item in snapshot.key_actors)
        text = " | ".join(
            [
                snapshot.title,
                snapshot.summary,
                snapshot.system_under_pressure,
                actors,
                mechanisms,
                snapshot.stage.stage,
            ]
        )
        self.store.put(
            self.namespace,
            snapshot.situation_id,
            {
                "situation_id": snapshot.situation_id,
                "title": snapshot.title,
                "summary": snapshot.summary,
                "mechanisms": [item.name for item in snapshot.mechanisms],
                "text": text,
            },
        )

    def search(self, cluster: EventCluster, *, exclude_id: str | None = None, limit: int = 3) -> list[RelatedSituation]:
        query = " ".join([cluster.canonical_title, cluster.summary, *cluster.entities, *cluster.tags]).strip()
        if not query:
            return []
        results = self.store.search(self.namespace, query=query, limit=limit + (1 if exclude_id else 0))
        related: list[RelatedSituation] = []
        for item in results:
            if exclude_id and item.key == exclude_id:
                continue
            related.append(
                RelatedSituation(
                    situation_id=item.value["situation_id"],
                    title=item.value["title"],
                    summary=item.value["summary"],
                    matched_on=cluster.entities[:2] + cluster.tags[:2],
                    mechanisms=item.value.get("mechanisms", []),
                    similarity_score=max(0.0, min(1.0, float(item.score or 0.0))),
                )
            )
            if len(related) >= limit:
                break
        return related
