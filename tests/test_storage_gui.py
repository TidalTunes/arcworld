from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from arcworld.gui.app import create_app
from arcworld.storage import RunStore, _event_hash


def test_store_is_append_only_and_ordered(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs.db")
    run_id = store.create_run("example", {"seed": 0})
    assert store.append(run_id, "first", {"value": 1}) == 0
    assert store.append(run_id, "second", {"value": 2}) == 1
    assert [item["kind"] for item in store.timeline(run_id)] == ["first", "second"]
    assert store.timeline(run_id)[1]["previous_hash"] == store.timeline(run_id)[0]["event_hash"]
    assert store.verify_chain(run_id)
    assert store.list_runs()[0]["event_count"] == 2


def test_legacy_events_are_backfilled_without_rewriting_existing_hashes(
    tmp_path: Path,
) -> None:
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE runs (
                id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                label TEXT NOT NULL,
                config_json TEXT NOT NULL
            );
            CREATE TABLE events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL REFERENCES runs(id),
                sequence INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                kind TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                UNIQUE(run_id, sequence)
            );
            """
        )
        connection.execute(
            "INSERT INTO runs VALUES (?, ?, ?, ?)",
            ("legacy-run", "2026-07-27T00:00:00+00:00", "legacy", "{}"),
        )
        connection.executemany(
            """
            INSERT INTO events(run_id, sequence, created_at, kind, payload_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                (
                    "legacy-run",
                    0,
                    "2026-07-27T00:00:01+00:00",
                    "first",
                    '{"value":1}',
                ),
                (
                    "legacy-run",
                    1,
                    "2026-07-27T00:00:02+00:00",
                    "second",
                    '{"value":2}',
                ),
            ),
        )

    store = RunStore(path)
    timeline = store.timeline("legacy-run")
    assert timeline[0]["event_hash"]
    assert timeline[1]["previous_hash"] == timeline[0]["event_hash"]
    assert store.verify_chain("legacy-run")


def test_reopening_through_gui_does_not_repair_tampered_evidence(tmp_path: Path) -> None:
    path = tmp_path / "runs.db"
    store = RunStore(path)
    run_id = store.create_run("tamper-check")
    store.append(run_id, "first", {"value": 1})
    store.append(run_id, "second", {"value": 2})
    original_hash = store.timeline(run_id)[0]["event_hash"]

    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE events SET payload_json = ? WHERE run_id = ? AND sequence = 0",
            ('{"value":999}', run_id),
        )

    assert not store.verify_chain(run_id)
    with TestClient(create_app(path)) as client:
        assert client.get(f"/api/runs/{run_id}").status_code == 200

    reopened = RunStore(path)
    assert reopened.timeline(run_id)[0]["event_hash"] == original_hash
    assert not reopened.verify_chain(run_id)


def test_verify_chain_rejects_a_valid_hash_chain_with_a_sequence_gap(tmp_path: Path) -> None:
    path = tmp_path / "runs.db"
    store = RunStore(path)
    run_id = store.create_run("gap-check")
    store.append(run_id, "first", {"value": 1})
    store.append(run_id, "second", {"value": 2})
    second = store.timeline(run_id)[1]
    gapped_sequence = 2
    gapped_hash = _event_hash(
        run_id,
        gapped_sequence,
        str(second["created_at"]),
        str(second["kind"]),
        json.dumps(second["payload"], sort_keys=True, separators=(",", ":")),
        str(second["previous_hash"]),
    )

    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            UPDATE events SET sequence = ?, event_hash = ?
            WHERE run_id = ? AND sequence = 1
            """,
            (gapped_sequence, gapped_hash, run_id),
        )

    assert not RunStore(path).verify_chain(run_id)


def test_gui_live_toy_and_inspection_api(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "runs.db"))
    assert client.get("/api/health").json()["status"] == "ok"
    started = client.post("/api/live/toy", json={}).json()
    run_id = started["run_id"]
    result = client.post(f"/api/live/{run_id}/action", json={"id": 4})
    assert result.status_code == 200
    payload = result.json()
    assert payload["diff"]["pixels"]["equal"]
    inspection = client.post(
        "/api/inspect",
        json={"actual": payload["actual"], "predicted": payload["predicted"]},
    )
    assert inspection.status_code == 200
    assert inspection.json()["diff"]["exact"]
    assert len(client.get(f"/api/runs/{run_id}").json()["timeline"]) == 2
