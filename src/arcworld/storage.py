"""A compact SQLite evidence store used by experiments and the dashboard."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections.abc import Mapping
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    label TEXT NOT NULL,
    config_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(id),
    sequence INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    previous_hash TEXT,
    event_hash TEXT NOT NULL,
    UNIQUE(run_id, sequence)
);
CREATE INDEX IF NOT EXISTS events_run_sequence ON events(run_id, sequence);
"""


class RunStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.executescript(_SCHEMA)
            self._migrate_and_backfill(connection)

    def create_run(self, label: str, config: Mapping[str, Any] | None = None) -> str:
        run_id = uuid.uuid4().hex
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT INTO runs(id, started_at, label, config_json) VALUES (?, ?, ?, ?)",
                (run_id, _now(), label, _json(config or {})),
            )
            connection.commit()
        return run_id

    def append(self, run_id: str, kind: str, payload: Mapping[str, Any]) -> int:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT sequence, event_hash FROM events
                WHERE run_id = ? ORDER BY sequence DESC LIMIT 1
                """,
                (run_id,),
            ).fetchone()
            sequence = 0 if row is None else int(row[0]) + 1
            previous_hash = None if row is None else str(row[1])
            created_at = _now()
            payload_json = _json(payload)
            event_hash = _event_hash(
                run_id,
                sequence,
                created_at,
                kind,
                payload_json,
                previous_hash,
            )
            connection.execute(
                """
                INSERT INTO events(
                    run_id, sequence, created_at, kind, payload_json, previous_hash, event_hash
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    sequence,
                    created_at,
                    kind,
                    payload_json,
                    previous_hash,
                    event_hash,
                ),
            )
            connection.commit()
        return sequence

    def list_runs(self, limit: int = 100) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT r.id, r.started_at, r.label, r.config_json, COUNT(e.id) AS event_count
                FROM runs r LEFT JOIN events e ON e.run_id = r.id
                GROUP BY r.id ORDER BY r.started_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "started_at": row["started_at"],
                "label": row["label"],
                "config": json.loads(row["config_json"]),
                "event_count": row["event_count"],
            }
            for row in rows
        ]

    def timeline(self, run_id: str) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT sequence, created_at, kind, payload_json, previous_hash, event_hash
                FROM events WHERE run_id = ? ORDER BY sequence
                """,
                (run_id,),
            ).fetchall()
        return [
            {
                "sequence": row["sequence"],
                "created_at": row["created_at"],
                "kind": row["kind"],
                "payload": json.loads(row["payload_json"]),
                "previous_hash": row["previous_hash"],
                "event_hash": row["event_hash"],
            }
            for row in rows
        ]

    def run(self, run_id: str) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT id, started_at, label, config_json FROM runs WHERE id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            raise KeyError(run_id)
        return {
            "id": row["id"],
            "started_at": row["started_at"],
            "label": row["label"],
            "config": json.loads(row["config_json"]),
        }

    def verify_chain(self, run_id: str) -> bool:
        previous_hash: str | None = None
        for event in self.timeline(run_id):
            payload_json = _json(event["payload"])
            expected = _event_hash(
                run_id,
                int(event["sequence"]),
                str(event["created_at"]),
                str(event["kind"]),
                payload_json,
                previous_hash,
            )
            if event["previous_hash"] != previous_hash or event["event_hash"] != expected:
                return False
            previous_hash = expected
        return True

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _migrate_and_backfill(self, connection: sqlite3.Connection) -> None:
        columns = {
            str(row[1]) for row in connection.execute("PRAGMA table_info(events)").fetchall()
        }
        if "previous_hash" not in columns:
            connection.execute("ALTER TABLE events ADD COLUMN previous_hash TEXT")
        if "event_hash" not in columns:
            connection.execute("ALTER TABLE events ADD COLUMN event_hash TEXT")
        run_rows = connection.execute("SELECT id FROM runs ORDER BY id").fetchall()
        for (run_id,) in run_rows:
            previous_hash: str | None = None
            events = connection.execute(
                """
                SELECT id, sequence, created_at, kind, payload_json
                FROM events WHERE run_id = ? ORDER BY sequence
                """,
                (run_id,),
            ).fetchall()
            for event_id, sequence, created_at, kind, payload_json in events:
                event_hash = _event_hash(
                    str(run_id),
                    int(sequence),
                    str(created_at),
                    str(kind),
                    str(payload_json),
                    previous_hash,
                )
                connection.execute(
                    """
                    UPDATE events SET previous_hash = ?, event_hash = ? WHERE id = ?
                    """,
                    (previous_hash, event_hash, event_id),
                )
                previous_hash = event_hash
        connection.commit()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _event_hash(
    run_id: str,
    sequence: int,
    created_at: str,
    kind: str,
    payload_json: str,
    previous_hash: str | None,
) -> str:
    value = {
        "run_id": run_id,
        "sequence": sequence,
        "created_at": created_at,
        "kind": kind,
        "payload_json": payload_json,
        "previous_hash": previous_hash,
    }
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()
