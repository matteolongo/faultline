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
    CalibrationSignal,
    DeadLetterRecord,
    EventCluster,
    OutcomeRecord,
    Prediction,
    ProviderHealthStatus,
    PublishedReport,
    RawSignal,
    SignalEvent,
    SituationSnapshot,
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
            CREATE TABLE IF NOT EXISTS situation_snapshots (
                situation_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                domain TEXT NOT NULL,
                stage TEXT NOT NULL,
                confidence REAL NOT NULL,
                payload_json TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS predictions (
                prediction_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                prediction_type TEXT NOT NULL,
                time_horizon TEXT NOT NULL,
                confidence REAL NOT NULL,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS outcome_records (
                prediction_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                prediction_type TEXT NOT NULL,
                target TEXT NOT NULL,
                outcome_status TEXT NOT NULL,
                confidence_delta REAL NOT NULL,
                payload_json TEXT NOT NULL,
                PRIMARY KEY (run_id, prediction_id)
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

    def list_runs_for_followup(
        self,
        *,
        cutoff_time: datetime,
        limit: int = 20,
        include_demo: bool = False,
        include_scored: bool = False,
    ) -> list[dict[str, Any]]:
        placeholder = self._placeholder()
        sql = (
            "SELECT r.run_id, r.run_mode, r.scenario_id, COALESCE(r.window_end, r.started_at) AS anchor_time, "
            "COUNT(DISTINCT p.prediction_id) AS prediction_count, COUNT(DISTINCT o.prediction_id) AS scored_count "
            "FROM runs r "
            "JOIN predictions p ON p.run_id = r.run_id "
            "LEFT JOIN outcome_records o ON o.run_id = r.run_id "
            "WHERE COALESCE(r.window_end, r.started_at) < " + placeholder
        )
        params: list[Any] = [cutoff_time.isoformat()]
        if not include_demo:
            sql += " AND r.run_mode != " + placeholder
            params.append("demo")
        sql += " GROUP BY r.run_id, r.run_mode, r.scenario_id, anchor_time HAVING COUNT(DISTINCT p.prediction_id) > 0"
        if not include_scored:
            sql += " AND COUNT(DISTINCT o.prediction_id) = 0"
        sql += " ORDER BY anchor_time DESC LIMIT " + placeholder
        params.append(limit)
        with self.connection() as connection:
            cursor = connection.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
        return [
            {
                "run_id": row[0],
                "run_mode": row[1],
                "scenario_id": row[2],
                "anchor_time": datetime.fromisoformat(row[3]),
                "prediction_count": int(row[4] or 0),
                "scored_count": int(row[5] or 0),
            }
            for row in rows
        ]

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

    def save_situation_snapshot(self, snapshot: SituationSnapshot) -> None:
        sql = """
            INSERT OR REPLACE INTO situation_snapshots (
                situation_id, title, domain, stage, confidence, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?)
        """
        if self.scheme.startswith("postgres"):
            sql = """
                INSERT INTO situation_snapshots (
                    situation_id, title, domain, stage, confidence, payload_json
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (situation_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    domain = EXCLUDED.domain,
                    stage = EXCLUDED.stage,
                    confidence = EXCLUDED.confidence,
                    payload_json = EXCLUDED.payload_json
            """
        with self.connection() as connection:
            connection.cursor().execute(
                sql,
                (
                    snapshot.situation_id,
                    snapshot.title,
                    snapshot.domain,
                    snapshot.stage.stage,
                    snapshot.confidence,
                    json.dumps(serialize_model(snapshot)),
                ),
            )

    def load_situation_snapshots(self, *, limit: int | None = None) -> list[SituationSnapshot]:
        sql = "SELECT payload_json FROM situation_snapshots ORDER BY confidence DESC, title ASC"
        params: list[Any] = []
        if limit is not None:
            sql += f" LIMIT {self._placeholder()}"
            params.append(limit)
        with self.connection() as connection:
            cursor = connection.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
        return [SituationSnapshot.model_validate(json.loads(row[0])) for row in rows]

    def save_predictions(self, *, run_id: str, predictions: list[Prediction]) -> None:
        if not predictions:
            return
        sql = """
            INSERT OR REPLACE INTO predictions (
                prediction_id, run_id, prediction_type, time_horizon, confidence, status, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        if self.scheme.startswith("postgres"):
            sql = """
                INSERT INTO predictions (
                    prediction_id, run_id, prediction_type, time_horizon, confidence, status, payload_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (prediction_id) DO UPDATE SET
                    run_id = EXCLUDED.run_id,
                    prediction_type = EXCLUDED.prediction_type,
                    time_horizon = EXCLUDED.time_horizon,
                    confidence = EXCLUDED.confidence,
                    status = EXCLUDED.status,
                    payload_json = EXCLUDED.payload_json
            """
        rows = [
            (
                prediction.prediction_id,
                run_id,
                prediction.prediction_type,
                prediction.time_horizon,
                prediction.confidence,
                prediction.status,
                json.dumps(serialize_model(prediction)),
            )
            for prediction in predictions
        ]
        with self.connection() as connection:
            connection.cursor().executemany(sql, rows)

    def load_predictions_for_run(self, run_id: str) -> list[Prediction]:
        placeholder = self._placeholder()
        sql = f"SELECT payload_json FROM predictions WHERE run_id = {placeholder} ORDER BY prediction_type ASC"
        with self.connection() as connection:
            cursor = connection.cursor()
            cursor.execute(sql, [run_id])
            rows = cursor.fetchall()
        return [Prediction.model_validate(json.loads(row[0])) for row in rows]

    def save_outcome_records(self, *, run_id: str, outcomes: list[OutcomeRecord]) -> None:
        if not outcomes:
            return
        sql = """
            INSERT OR REPLACE INTO outcome_records (
                prediction_id, run_id, prediction_type, target, outcome_status, confidence_delta, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        if self.scheme.startswith("postgres"):
            sql = """
                INSERT INTO outcome_records (
                    prediction_id, run_id, prediction_type, target, outcome_status, confidence_delta, payload_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (run_id, prediction_id) DO UPDATE SET
                    prediction_type = EXCLUDED.prediction_type,
                    target = EXCLUDED.target,
                    outcome_status = EXCLUDED.outcome_status,
                    confidence_delta = EXCLUDED.confidence_delta,
                    payload_json = EXCLUDED.payload_json
            """
        rows = [
            (
                outcome.prediction_id,
                run_id,
                outcome.prediction_type,
                outcome.target,
                outcome.outcome_status,
                outcome.confidence_delta,
                json.dumps(serialize_model(outcome)),
            )
            for outcome in outcomes
        ]
        with self.connection() as connection:
            connection.cursor().executemany(sql, rows)

    def load_outcomes_for_run(self, run_id: str) -> list[OutcomeRecord]:
        placeholder = self._placeholder()
        sql = f"SELECT payload_json FROM outcome_records WHERE run_id = {placeholder} ORDER BY prediction_type ASC"
        with self.connection() as connection:
            cursor = connection.cursor()
            cursor.execute(sql, [run_id])
            rows = cursor.fetchall()
        return [OutcomeRecord.model_validate(json.loads(row[0])) for row in rows]

    def load_calibration_signals(self, *, exclude_run_id: str | None = None) -> list[CalibrationSignal]:
        base_sql = """
            SELECT
                prediction_type,
                COUNT(*) AS sample_size,
                SUM(CASE WHEN outcome_status = 'confirmed' THEN 1 ELSE 0 END) AS confirmed_count,
                SUM(CASE WHEN outcome_status = 'partial' THEN 1 ELSE 0 END) AS partial_count,
                SUM(CASE WHEN outcome_status = 'unconfirmed' THEN 1 ELSE 0 END) AS unconfirmed_count,
                AVG(confidence_delta) AS avg_confidence_delta
            FROM outcome_records
        """
        params: list[Any] = []
        if exclude_run_id is not None:
            base_sql += f" WHERE run_id != {self._placeholder()}"
            params.append(exclude_run_id)
        base_sql += " GROUP BY prediction_type ORDER BY prediction_type ASC"
        with self.connection() as connection:
            cursor = connection.cursor()
            cursor.execute(base_sql, params)
            rows = cursor.fetchall()
        signals: list[CalibrationSignal] = []
        for row in rows:
            prediction_type = row[0]
            sample_size = int(row[1] or 0)
            if sample_size == 0:
                continue
            confirmed_count = int(row[2] or 0)
            partial_count = int(row[3] or 0)
            unconfirmed_count = int(row[4] or 0)
            avg_delta = float(row[5] or 0.0)
            signals.append(
                CalibrationSignal(
                    prediction_type=prediction_type,
                    sample_size=sample_size,
                    confirmed_rate=confirmed_count / sample_size,
                    partial_rate=partial_count / sample_size,
                    unconfirmed_rate=unconfirmed_count / sample_size,
                    average_confidence_delta=avg_delta,
                    guidance=self._calibration_guidance(
                        prediction_type=prediction_type,
                        confirmed_rate=confirmed_count / sample_size,
                        partial_rate=partial_count / sample_size,
                        avg_delta=avg_delta,
                    ),
                )
            )
        return signals

    def _calibration_guidance(
        self,
        *,
        prediction_type: str,
        confirmed_rate: float,
        partial_rate: float,
        avg_delta: float,
    ) -> str:
        if confirmed_rate >= 0.65 and avg_delta >= 0.08:
            return f"{prediction_type} predictions have held up well; confidence can be nudged upward when structure matches."
        if confirmed_rate + partial_rate >= 0.65:
            return f"{prediction_type} predictions often need nuance; keep them but frame them probabilistically."
        return f"{prediction_type} predictions have weak historical confirmation; confidence should be discounted."

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
