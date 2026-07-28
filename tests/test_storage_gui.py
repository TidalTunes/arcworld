from __future__ import annotations

import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from fastapi.testclient import TestClient

from arcworld.env.toy import TOY_MODEL_SOURCE, ToyKeyDoorEnvironment
from arcworld.gui.app import create_app
from arcworld.models.contract import RuleProgram
from arcworld.storage import RunStore, _event_hash
from arcworld.types import Action, ActionKind


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
    with closing(sqlite3.connect(path)) as connection:
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
        connection.commit()

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

    with closing(sqlite3.connect(path)) as connection:
        connection.execute(
            "UPDATE events SET payload_json = ? WHERE run_id = ? AND sequence = 0",
            ('{"value":999}', run_id),
        )
        connection.commit()

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

    with closing(sqlite3.connect(path)) as connection:
        connection.execute(
            """
            UPDATE events SET sequence = ?, event_hash = ?
            WHERE run_id = ? AND sequence = 1
            """,
            (gapped_sequence, gapped_hash, run_id),
        )
        connection.commit()

    assert not RunStore(path).verify_chain(run_id)


def test_gui_projects_observable_events_without_rewriting_lossless_evidence(
    tmp_path: Path,
) -> None:
    path = tmp_path / "runs.db"
    store = RunStore(path)
    run_id = store.create_run("projection")
    store.append(
        run_id,
        "reasoner_response",
        {
            "response": "observable final output",
            "reasoning_content": "hidden provider trace",
            "provider_metadata": {"analysis": "hidden nested trace"},
        },
    )

    with TestClient(create_app(path)) as client:
        projected = client.get(f"/api/runs/{run_id}").json()["timeline"]
        incremental = client.get(f"/api/runs/{run_id}/events").json()["events"]

    assert "observable final output" in json.dumps(projected)
    assert "hidden provider trace" not in json.dumps(projected)
    assert "hidden nested trace" not in json.dumps(incremental)
    stored = RunStore(path).timeline(run_id)
    assert stored[0]["payload"]["reasoning_content"] == "hidden provider trace"
    assert stored[0]["payload"]["provider_metadata"]["analysis"] == "hidden nested trace"


def test_gui_observation_inspection_api(tmp_path: Path) -> None:
    environment = ToyKeyDoorEnvironment()
    before = environment.start()
    program = RuleProgram.from_source(TOY_MODEL_SOURCE)
    prediction = program.predict(
        program.initial_state(before),
        Action(ActionKind.ACTION4),
        before,
    )
    actual = environment.step(Action(ActionKind.ACTION4))
    with TestClient(create_app(tmp_path / "runs.db")) as client:
        assert client.get("/api/health").json()["status"] == "ok"
        inspection = client.post(
            "/api/inspect",
            json={
                "actual": actual.to_jsonable(),
                "predicted": prediction.observation.to_jsonable(),
            },
        )
        assert inspection.status_code == 200
        assert inspection.json()["diff"]["exact"]


def test_gui_creates_and_steps_a_paused_test_without_double_spending(
    tmp_path: Path,
) -> None:
    path = tmp_path / "runs.db"
    with TestClient(
        create_app(
            path,
            environments_dir=tmp_path / "no-environments",
            workspace=tmp_path / "workspace",
        )
    ) as client:
        capabilities = client.get("/api/test-capabilities").json()
        assert capabilities["local_only"]
        assert capabilities["puzzles"][0]["id"] == "synthetic-key-door"
        assert capabilities["providers"][0]["id"] == "deterministic"

        response = client.post(
            "/api/tests",
            json={
                "puzzle_id": "synthetic-key-door",
                "provider": "deterministic",
                "model": "deterministic-fixture",
                "effort": "fixed",
                "action_budget": 20,
                "candidate_count": 1,
                "seed": 0,
            },
        )
        assert response.status_code == 201
        session = response.json()
        run_id = session["run_id"]
        assert session["phase"] == "start"
        assert not session["busy"]
        assert session["state_version"] == 0

        accepted = client.post(
            f"/api/tests/{run_id}/step",
            json={
                "expected_state_version": 0,
                "authorize_real_action": False,
            },
        )
        assert accepted.status_code == 202
        session = _wait_until_idle(client, run_id)
        assert session["phase"] == "induction"
        assert session["state_version"] == 1
        stale = client.post(
            f"/api/tests/{run_id}/step",
            json={
                "expected_state_version": 0,
                "authorize_real_action": False,
            },
        )
        assert stale.status_code == 409

        while session["phase"] != "finished":
            raw_before = _event_count(client, run_id, "transition_raw")
            authorized_phase = session["phase"]
            if authorized_phase == "execution":
                refused = client.post(
                    f"/api/tests/{run_id}/step",
                    json={
                        "expected_state_version": session["state_version"],
                        "authorize_real_action": False,
                    },
                )
                assert refused.status_code == 409
                assert _event_count(client, run_id, "transition_raw") == raw_before
            accepted = client.post(
                f"/api/tests/{run_id}/step",
                json={
                    "expected_state_version": session["state_version"],
                    "authorize_real_action": authorized_phase == "execution",
                },
            )
            assert accepted.status_code == 202
            session = _wait_until_idle(client, run_id)
            raw_after = _event_count(client, run_id, "transition_raw")
            assert raw_after - raw_before == (1 if authorized_phase == "execution" else 0)

        assert session["result"]["status"] == "WIN"
        assert session["result"]["real_actions"] == 7
        run = client.get(f"/api/runs/{run_id}").json()
        assert run["event_chain_valid"]
        assert run["audit_state"] == "not_applicable"
        page = client.get(
            f"/api/runs/{run_id}/events",
            params={"after_sequence": -1, "limit": 3},
        ).json()
        assert [event["sequence"] for event in page["events"]] == [0, 1, 2]
        assert page["has_more"]


def _wait_until_idle(client: TestClient, run_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        response = client.get(f"/api/tests/{run_id}")
        assert response.status_code == 200
        value = response.json()
        if not value["busy"]:
            return value
        time.sleep(0.005)
    raise AssertionError("interactive phase did not finish")


def _event_count(client: TestClient, run_id: str, kind: str) -> int:
    events = client.get(f"/api/runs/{run_id}").json()["timeline"]
    return sum(event["kind"] == kind for event in events)
