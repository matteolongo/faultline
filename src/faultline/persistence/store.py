from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

from faultline.models import (
    DeadLetterRecord,
    EventCluster,
    ProviderHealthStatus,
    PublishedReport,
    RawSignal,
    SignalEvent,
)
from faultline.utils.io import ensure_directory, serialize_model

try:  # pragma: no cover - optional dependency path
    import psycopg
except Exception:  # pragma: no cover - sqlite remains the default test path
    psycopg = None


class SignalStore:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.getenv(
            "FAULTLINE_DATABASE_URL", "sqlite:///outputs/faultline_runs.sqlite"
        )
        self.scheme = urlparse(self.database_url).scheme or "sqlite"
        if self.scheme in {"", "sqlite"}:
            parsed = urlparse(self.database_url)
            if parsed.scheme:
                db_path = parsed.path if parsed.path else self.database_url.replace("sqlite:///", "")
            else:
                db_path = self.database_url.replace("sqlite:///", "")
            if (
                parsed.scheme
                and db_path.startswith("/")
                and not db_path.startswith(("/Users/", "/private/", "/tmp/", "/var/", "/home/"))
            ):
                db_path = db_path.lstrip("/")
            elif not db_path.startswith("/") and parsed.scheme:
                db_path = f"/{db_path}"
            self.sqlite_path = Path(db_path or "outputs/swarm_runs.sqlite")
            ensure_directory(self.sqlite_path.parent)
        elif self.scheme.startswith("postgres"):
            if psycopg is None:
                raise RuntimeError("psycopg is required for PostgreSQL database URLs.")
            self.sqlite_path = None
        else:
            raise ValueError(f"Unsupported database URL: {self.database_url}")
        self._initialize_schema()

    @contextmanager
    def connection(self) -> Iterator[Any]:
        if self.scheme in {"", "sqlite"}:
            connection = sqlite3.connect(self.sqlite_path)
            try:
                yield connection
                connection.commit()
            finally:
                connection.close()
            return
        connection = psycopg.connect(self.database_url)
        try:  # pragma: no cover - postgres is optional in tests
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _placeholder(self) -> str:
        return "?" if self.scheme in {"", "sqlite"} else "%s"

    def _initialize_schema(self) -> None:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS raw_signals (
                id TEXT PRIMARY KEY,
                provider_name TEXT NOT NULL,
                provider_item_id TEXT NOT NULL,
                source_family TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                source_url TEXT,
                request_url TEXT,
                query_key TEXT,
                region TEXT NOT NULL,
                language TEXT,
                timestamp TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                published_at TEXT,
                confidence REAL NOT NULL,
                provider_confidence REAL NOT NULL,
                content_hash TEXT NOT NULL,
                dedupe_hash TEXT NOT NULL,
                raw_payload_reference TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS normalized_signals (
                id TEXT PRIMARY KEY,
                raw_signal_id TEXT NOT NULL,
                cluster_id TEXT NOT NULL,
                story_key TEXT NOT NULL,
                source_family TEXT NOT NULL,
                provider_name TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                novelty REAL NOT NULL,
                possible_systemic_relevance REAL NOT NULL,
                payload_json TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS event_clusters (
                cluster_id TEXT PRIMARY KEY,
                story_key TEXT NOT NULL,
                canonical_title TEXT NOT NULL,
                region TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                agreement_score REAL NOT NULL,
                novelty_score REAL NOT NULL,
                cluster_strength REAL NOT NULL,
                payload_json TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                scenario_id TEXT,
                run_mode TEXT NOT NULL,
                started_at TEXT NOT NULL,
                created_at TEXT,
                window_start TEXT,
                window_end TEXT,
                publish_decision TEXT NOT NULL,
                diagnostics_json TEXT NOT NULL,
                final_state_json TEXT NOT NULL,
                trace_json TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS reports (
                report_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                cluster_id TEXT NOT NULL,
                publication_status TEXT NOT NULL,
                published_at TEXT NOT NULL,
                report_json TEXT NOT NULL,
                diagnostics_json TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS dead_letters (
                id TEXT PRIMARY KEY,
                provider_name TEXT NOT NULL,
                window_start TEXT NOT NULL,
                window_end TEXT NOT NULL,
                failed_at TEXT NOT NULL,
                request_url TEXT,
                error_type TEXT NOT NULL,
                error_message TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """,
        ]
        with self.connection() as connection:
            cursor = connection.cursor()
            for statement in statements:
                cursor.execute(statement)
            if self.scheme in {"", "sqlite"}:
                self._migrate_sqlite_schema(cursor)

    def _migrate_sqlite_schema(self, cursor) -> None:
        migrations = {
            "runs": {
                "scenario_id": "TEXT",
                "run_mode": "TEXT",
                "started_at": "TEXT",
                "created_at": "TEXT",
                "window_start": "TEXT",
                "window_end": "TEXT",
                "publish_decision": "TEXT",
                "diagnostics_json": "TEXT",
            },
            "raw_signals": {
                "provider_name": "TEXT",
                "provider_item_id": "TEXT",
                "source_family": "TEXT",
                "source_url": "TEXT",
                "request_url": "TEXT",
                "query_key": "TEXT",
                "language": "TEXT",
                "fetched_at": "TEXT",
                "published_at": "TEXT",
                "provider_confidence": "REAL",
                "content_hash": "TEXT",
                "dedupe_hash": "TEXT",
                "raw_payload_reference": "TEXT",
            },
        }
        for table_name, columns in migrations.items():
            cursor.execute(f"PRAGMA table_info({table_name})")
            existing = {row[1] for row in cursor.fetchall()}
            for column_name, column_type in columns.items():
                if column_name not in existing:
                    try:
                        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
                    except sqlite3.OperationalError as exc:
                        if "duplicate column name" not in str(exc):
                            raise

    def get_seen_dedupe_hashes(self, dedupe_hashes: list[str]) -> set[str]:
        if not dedupe_hashes:
            return set()
        placeholders = ",".join([self._placeholder()] * len(dedupe_hashes))
        query = f"SELECT dedupe_hash FROM raw_signals WHERE dedupe_hash IN ({placeholders})"
        with self.connection() as connection:
            cursor = connection.cursor()
            cursor.execute(query, dedupe_hashes)
            return {row[0] for row in cursor.fetchall()}

    def get_story_counts(self, story_keys: list[str]) -> dict[str, int]:
        if not story_keys:
            return {}
        placeholders = ",".join([self._placeholder()] * len(story_keys))
        query = f"SELECT story_key, COUNT(*) FROM event_clusters WHERE story_key IN ({placeholders}) GROUP BY story_key"
        with self.connection() as connection:
            cursor = connection.cursor()
            cursor.execute(query, story_keys)
            return {row[0]: row[1] for row in cursor.fetchall()}

    def save_raw_signals(self, signals: list[RawSignal]) -> None:
        if not signals:
            return
        sql = """
            INSERT OR REPLACE INTO raw_signals (
                id, provider_name, provider_item_id, source_family, signal_type, title, summary,
                source_url, request_url, query_key, region, language, timestamp, fetched_at,
                published_at, confidence, provider_confidence, content_hash, dedupe_hash,
                raw_payload_reference, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        if self.scheme.startswith("postgres"):
            sql = """
                INSERT INTO raw_signals (
                    id, provider_name, provider_item_id, source_family, signal_type, title, summary,
                    source_url, request_url, query_key, region, language, timestamp, fetched_at,
                    published_at, confidence, provider_confidence, content_hash, dedupe_hash,
                    raw_payload_reference, payload_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET payload_json = EXCLUDED.payload_json
            """
        rows = [
            (
                signal.id,
                signal.provider_name,
                signal.provider_item_id,
                signal.source,
                signal.signal_type,
                signal.title,
                signal.summary,
                signal.source_url,
                signal.request_url,
                signal.query_key,
                signal.region,
                signal.language,
                signal.timestamp.isoformat(),
                signal.fetched_at.isoformat() if signal.fetched_at else signal.timestamp.isoformat(),
                signal.published_at.isoformat() if signal.published_at else None,
                signal.confidence,
                signal.provider_confidence,
                signal.content_hash,
                signal.dedupe_hash,
                signal.raw_payload_reference,
                json.dumps(serialize_model(signal.payload)),
            )
            for signal in signals
        ]
        with self.connection() as connection:
            connection.cursor().executemany(sql, rows)

    def save_normalized_events(self, events: list[SignalEvent]) -> None:
        if not events:
            return
        sql = """
            INSERT OR REPLACE INTO normalized_signals (
                id, raw_signal_id, cluster_id, story_key, source_family, provider_name, timestamp, novelty,
                possible_systemic_relevance, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        if self.scheme.startswith("postgres"):
            sql = """
                INSERT INTO normalized_signals (
                    id, raw_signal_id, cluster_id, story_key, source_family, provider_name, timestamp, novelty,
                    possible_systemic_relevance, payload_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET payload_json = EXCLUDED.payload_json
            """
        rows = [
            (
                event.id,
                event.id,
                event.cluster_id,
                event.story_key,
                event.source,
                event.provider_name,
                event.timestamp.isoformat(),
                event.novelty,
                event.possible_systemic_relevance,
                json.dumps(serialize_model(event)),
            )
            for event in events
        ]
        with self.connection() as connection:
            connection.cursor().executemany(sql, rows)

    def save_event_clusters(self, clusters: list[EventCluster]) -> None:
        if not clusters:
            return
        sql = """
            INSERT OR REPLACE INTO event_clusters (
                cluster_id, story_key, canonical_title, region, first_seen_at, last_seen_at,
                agreement_score, novelty_score, cluster_strength, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        if self.scheme.startswith("postgres"):
            sql = """
                INSERT INTO event_clusters (
                    cluster_id, story_key, canonical_title, region, first_seen_at, last_seen_at,
                    agreement_score, novelty_score, cluster_strength, payload_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (cluster_id) DO UPDATE SET payload_json = EXCLUDED.payload_json
            """
        rows = [
            (
                cluster.cluster_id,
                cluster.story_key,
                cluster.canonical_title,
                cluster.region,
                cluster.first_seen_at.isoformat(),
                cluster.last_seen_at.isoformat(),
                cluster.agreement_score,
                cluster.novelty_score,
                cluster.cluster_strength,
                json.dumps(serialize_model(cluster)),
            )
            for cluster in clusters
        ]
        with self.connection() as connection:
            connection.cursor().executemany(sql, rows)

    def list_raw_signals(self, *, limit: int = 25, provider_name: str | None = None) -> list[dict[str, Any]]:
        if self.scheme.startswith("postgres"):
            sql = "SELECT provider_name, source_family, title, timestamp, raw_payload_reference FROM raw_signals"
            params: list[Any] = []
            if provider_name:
                sql += " WHERE provider_name = %s"
                params.append(provider_name)
            sql += " ORDER BY timestamp DESC LIMIT %s"
            params.append(limit)
        else:
            sql = "SELECT provider_name, source_family, title, timestamp, raw_payload_reference FROM raw_signals"
            params = []
            if provider_name:
                sql += " WHERE provider_name = ?"
                params.append(provider_name)
            sql += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
        with self.connection() as connection:
            cursor = connection.cursor()
            cursor.execute(sql, params)
            return [
                {
                    "provider_name": row[0],
                    "source_family": row[1],
                    "title": row[2],
                    "timestamp": row[3],
                    "raw_payload_reference": row[4],
                }
                for row in cursor.fetchall()
            ]

    def load_raw_signals_for_window(self, start_at: datetime, end_at: datetime) -> list[RawSignal]:
        operator_start = self._placeholder()
        operator_end = self._placeholder()
        sql = (
            "SELECT id, provider_name, provider_item_id, source_family, signal_type, title, summary, "
            "source_url, request_url, query_key, region, language, timestamp, fetched_at, published_at, "
            "confidence, provider_confidence, content_hash, dedupe_hash, raw_payload_reference, payload_json "
            "FROM raw_signals WHERE timestamp >= "
            + operator_start
            + " AND timestamp <= "
            + operator_end
            + " ORDER BY timestamp ASC"
        )
        with self.connection() as connection:
            cursor = connection.cursor()
            cursor.execute(sql, [start_at.isoformat(), end_at.isoformat()])
            rows = cursor.fetchall()
        signals = []
        for row in rows:
            signals.append(
                RawSignal(
                    id=row[0],
                    provider_name=row[1],
                    provider_item_id=row[2],
                    source=row[3],
                    signal_type=row[4],
                    title=row[5],
                    summary=row[6],
                    source_url=row[7],
                    request_url=row[8],
                    query_key=row[9],
                    region=row[10],
                    language=row[11],
                    timestamp=datetime.fromisoformat(row[12]),
                    fetched_at=datetime.fromisoformat(row[13]),
                    published_at=datetime.fromisoformat(row[14]) if row[14] else None,
                    confidence=row[15],
                    provider_confidence=row[16],
                    content_hash=row[17],
                    dedupe_hash=row[18],
                    raw_payload_reference=row[19],
                    payload=json.loads(row[20]),
                )
            )
        return signals

    def save_run(
        self,
        *,
        run_id: str,
        scenario_id: str | None,
        run_mode: str,
        window_start: datetime | None,
        window_end: datetime | None,
        publish_decision: str,
        diagnostics: dict[str, Any],
        final_state: dict[str, Any],
        trace: list[dict[str, Any]],
    ) -> None:
        sql = """
            INSERT OR REPLACE INTO runs (
                run_id, scenario_id, run_mode, started_at, created_at, window_start, window_end, publish_decision,
                diagnostics_json, final_state_json, trace_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        if self.scheme.startswith("postgres"):
            sql = """
                INSERT INTO runs (
                    run_id, scenario_id, run_mode, started_at, created_at, window_start, window_end, publish_decision,
                    diagnostics_json, final_state_json, trace_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (run_id) DO UPDATE SET final_state_json = EXCLUDED.final_state_json
            """
        now_iso = datetime.now(UTC).isoformat()
        with self.connection() as connection:
            connection.cursor().execute(
                sql,
                (
                    run_id,
                    scenario_id or run_mode,
                    run_mode,
                    now_iso,
                    now_iso,
                    window_start.isoformat() if window_start else None,
                    window_end.isoformat() if window_end else None,
                    publish_decision,
                    json.dumps(serialize_model(diagnostics)),
                    json.dumps(serialize_model(final_state)),
                    json.dumps(serialize_model(trace)),
                ),
            )

    def get_run_state(self, run_id: str) -> dict[str, Any] | None:
        placeholder = self._placeholder()
        sql = f"SELECT final_state_json FROM runs WHERE run_id = {placeholder}"
        with self.connection() as connection:
            cursor = connection.cursor()
            cursor.execute(sql, [run_id])
            row = cursor.fetchone()
        return json.loads(row[0]) if row else None

    def save_report(self, report: PublishedReport) -> None:
        sql = """
            INSERT OR REPLACE INTO reports (
                report_id, run_id, cluster_id, publication_status, published_at, report_json, diagnostics_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        if self.scheme.startswith("postgres"):
            sql = """
                INSERT INTO reports (
                    report_id, run_id, cluster_id, publication_status, published_at, report_json, diagnostics_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (report_id) DO UPDATE SET report_json = EXCLUDED.report_json
            """
        with self.connection() as connection:
            connection.cursor().execute(
                sql,
                (
                    report.report_id,
                    report.run_id,
                    report.cluster_id,
                    report.publication_status,
                    report.published_at.isoformat(),
                    json.dumps(serialize_model(report.report)),
                    json.dumps(serialize_model(report.diagnostics)),
                ),
            )

    def save_dead_letter(self, record: DeadLetterRecord) -> None:
        sql = """
            INSERT OR REPLACE INTO dead_letters (
                id, provider_name, window_start, window_end, failed_at, request_url, error_type, error_message, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        if self.scheme.startswith("postgres"):
            sql = """
                INSERT INTO dead_letters (
                    id, provider_name, window_start, window_end, failed_at, request_url, error_type, error_message, payload_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET payload_json = EXCLUDED.payload_json
            """
        with self.connection() as connection:
            connection.cursor().execute(
                sql,
                (
                    record.id,
                    record.provider_name,
                    record.window_start.isoformat(),
                    record.window_end.isoformat(),
                    record.failed_at.isoformat(),
                    record.request_url,
                    record.error_type,
                    record.error_message,
                    json.dumps(serialize_model(record.payload)),
                ),
            )

    def provider_health(self, provider_names: list[tuple[str, str, bool]]) -> list[ProviderHealthStatus]:
        with self.connection() as connection:
            cursor = connection.cursor()
            cutoff = (datetime.now(UTC) - timedelta(days=7)).isoformat()
            status_by_provider: dict[str, ProviderHealthStatus] = {}
            for provider_name, source_family, configured in provider_names:
                status_by_provider[provider_name] = ProviderHealthStatus(
                    provider_name=provider_name,
                    source_family=source_family,
                    enabled=True,
                    configured=configured,
                )
            for provider_name in status_by_provider:
                cursor.execute(
                    f"SELECT MAX(fetched_at), COUNT(*) FROM raw_signals WHERE provider_name = {self._placeholder()} AND fetched_at >= {self._placeholder()}",
                    [provider_name, cutoff],
                )
                success = cursor.fetchone()
                cursor.execute(
                    f"SELECT MAX(failed_at), COUNT(*) FROM dead_letters WHERE provider_name = {self._placeholder()}",
                    [provider_name],
                )
                failure = cursor.fetchone()
                status = status_by_provider[provider_name]
                if success and success[0]:
                    status.last_success_at = datetime.fromisoformat(success[0])
                    status.recent_signal_count = success[1]
                if failure and failure[0]:
                    status.last_error_at = datetime.fromisoformat(failure[0])
                    status.dead_letter_count = failure[1]
            return list(status_by_provider.values())


def make_dead_letter(
    *,
    provider_name: str,
    window_start: datetime,
    window_end: datetime,
    error_type: str,
    error_message: str,
    request_url: str | None = None,
    payload: dict[str, Any] | None = None,
) -> DeadLetterRecord:
    return DeadLetterRecord(
        id=uuid.uuid4().hex[:16],
        provider_name=provider_name,
        window_start=window_start,
        window_end=window_end,
        failed_at=datetime.now(UTC),
        request_url=request_url,
        error_type=error_type,
        error_message=error_message,
        payload=payload or {},
    )
