from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from arcworld.gui.app import create_app
from arcworld.storage import RunStore


def test_store_is_append_only_and_ordered(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs.db")
    run_id = store.create_run("example", {"seed": 0})
    assert store.append(run_id, "first", {"value": 1}) == 0
    assert store.append(run_id, "second", {"value": 2}) == 1
    assert [item["kind"] for item in store.timeline(run_id)] == ["first", "second"]
    assert store.timeline(run_id)[1]["previous_hash"] == store.timeline(run_id)[0]["event_hash"]
    assert store.verify_chain(run_id)
    assert store.list_runs()[0]["event_count"] == 2


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
