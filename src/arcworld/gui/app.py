"""Local dashboard API; model calls occur only after an explicit test-phase command."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from arcworld.audit import audit_real_llm_run
from arcworld.env.arc_adapter import ArcAdapterError
from arcworld.env.provenance import (
    EnvironmentProvenanceError,
    discover_offline_puzzles,
)
from arcworld.gui.sessions import (
    SYNTHETIC_PUZZLE_ID,
    SessionBusyError,
    SessionNotFoundError,
    SessionRegistry,
    SessionStateError,
    TestFactory,
    TestSpec,
    provider_capabilities,
)
from arcworld.perception.components import parse_scene
from arcworld.perception.diff import compare_observations
from arcworld.storage import RunStore
from arcworld.types import Observation


def create_app(
    store_path: Path,
    *,
    environments_dir: Path = Path("environment_files"),
    workspace: Path | None = None,
    recordings_dir: Path = Path("recordings"),
    codex_bin: Path | None = None,
) -> Any:
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import FileResponse
        from fastapi.staticfiles import StaticFiles
    except ImportError as error:
        raise RuntimeError("install ARCWorld with the 'gui' extra") from error

    store_path = store_path.expanduser().resolve()
    environments_dir = environments_dir.expanduser().resolve()
    workspace = (workspace or store_path.parent).expanduser().resolve()
    recordings_dir = recordings_dir.expanduser().resolve()
    codex_bin = codex_bin.expanduser().resolve() if codex_bin is not None else None
    store = RunStore(store_path)
    static = Path(__file__).with_name("static")
    test_sessions = SessionRegistry()
    factory = TestFactory(
        store_path=store_path,
        workspace=workspace,
        environments_dir=environments_dir,
        recordings_dir=recordings_dir,
        codex_bin=codex_bin,
    )

    @asynccontextmanager
    async def lifespan(_application: Any) -> AsyncIterator[None]:
        yield
        test_sessions.close()

    app = FastAPI(
        title="ARCWorld Test Console",
        docs_url="/api/docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "store": str(store_path)}

    @app.get("/api/test-capabilities")
    def test_capabilities() -> dict[str, Any]:
        catalog = discover_offline_puzzles(environments_dir)
        official = [
            {
                "id": item.game_id,
                "label": item.title or item.game_id,
                "kind": "official",
                **item.to_jsonable(),
            }
            for item in catalog.puzzles
        ]
        return {
            "puzzles": [
                {
                    "id": SYNTHETIC_PUZZLE_ID,
                    "label": "Synthetic key-door (deterministic fixture)",
                    "kind": "synthetic",
                    "runtime_ready": True,
                },
                *official,
            ],
            "providers": provider_capabilities(codex_bin),
            "efforts": ["minimal", "low", "medium", "high", "xhigh"],
            "limits": {
                "action_budget": {"minimum": 1, "maximum": 5000, "default": 100},
                "candidate_count": {"minimum": 1, "maximum": 8, "default": 1},
            },
            "issues": [issue.to_jsonable() for issue in catalog.issues],
            "local_only": True,
        }

    @app.get("/api/tests")
    def tests() -> list[dict[str, Any]]:
        return test_sessions.list()

    @app.post("/api/tests", status_code=201)
    def create_test(payload: Mapping[str, Any]) -> dict[str, Any]:
        try:
            spec = TestSpec.from_jsonable(dict(payload))
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        catalog = discover_offline_puzzles(environments_dir)
        known_official = {item.game_id for item in catalog.puzzles}
        if spec.puzzle_id != SYNTHETIC_PUZZLE_ID and spec.puzzle_id not in known_official:
            raise HTTPException(
                status_code=404,
                detail=f"no valid local environment found for {spec.puzzle_id!r}",
            )
        capability = {
            str(item["id"]): bool(item["available"]) for item in provider_capabilities(codex_bin)
        }
        if not capability.get(spec.provider, False):
            raise HTTPException(
                status_code=503,
                detail=f"provider {spec.provider!r} is not available in this server process",
            )
        try:
            controller = factory.create(spec)
            snapshot = test_sessions.add(controller, spec)
        except (EnvironmentProvenanceError, ArcAdapterError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        run_id = str(snapshot["run_id"])
        store.append(
            run_id,
            "interactive_session_created",
            {
                "state_version": snapshot["state_version"],
                "phase": snapshot["phase"],
                "test": spec.to_jsonable(),
            },
        )
        return test_sessions.get(run_id)

    @app.get("/api/tests/{run_id}")
    def test(run_id: str) -> dict[str, Any]:
        try:
            return test_sessions.get(run_id)
        except SessionNotFoundError as error:
            raise HTTPException(status_code=404, detail="interactive test not found") from error

    @app.post("/api/tests/{run_id}/step", status_code=202)
    def step_test(run_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        try:
            raw_version = payload["expected_state_version"]
            if isinstance(raw_version, bool) or not isinstance(raw_version, int):
                raise ValueError("expected_state_version must be an integer")
            authorize_real_action = payload.get("authorize_real_action", False)
            if not isinstance(authorize_real_action, bool):
                raise ValueError("authorize_real_action must be a boolean")
            return test_sessions.advance(
                run_id,
                expected_state_version=raw_version,
                authorize_real_action=authorize_real_action,
            )
        except KeyError as error:
            if isinstance(error, SessionNotFoundError):
                raise HTTPException(
                    status_code=404,
                    detail="interactive test not found",
                ) from error
            raise HTTPException(
                status_code=422,
                detail="expected_state_version is required",
            ) from error
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except (SessionBusyError, SessionStateError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/api/runs")
    def runs() -> list[dict[str, Any]]:
        return store.list_runs()

    @app.get("/api/runs/{run_id}")
    def run(run_id: str) -> dict[str, Any]:
        try:
            run_record = store.run(run_id)
            raw_timeline = store.timeline(run_id)
            timeline = [_observable_event(event) for event in raw_timeline]
            experiment = _as_mapping(_as_mapping(run_record["config"]).get("experiment", {}))
            audit = None
            real = experiment.get("run_kind") == "official-public-game-live-llm"
            finished = any(event["kind"] == "run_finished" for event in raw_timeline)
            errored = any(event["kind"] == "run_error" for event in raw_timeline)
            if real and finished:
                audit = audit_real_llm_run(store, run_id).to_jsonable()
            return {
                "run": run_record,
                "timeline": timeline,
                "audit": audit,
                "audit_state": (
                    "not_applicable"
                    if not real
                    else "passed"
                    if audit and audit["passed"]
                    else "failed"
                    if audit
                    else "failed"
                    if errored
                    else "pending"
                ),
                "event_chain_valid": store.verify_chain(run_id),
            }
        except KeyError as error:
            raise HTTPException(status_code=404, detail="run not found") from error

    @app.get("/api/runs/{run_id}/events")
    def run_events(
        run_id: str,
        after_sequence: int = -1,
        limit: int = 200,
    ) -> dict[str, Any]:
        try:
            store.run(run_id)
            events = store.events_after(
                run_id,
                after_sequence=after_sequence,
                limit=limit,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="run not found") from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {
            "events": [_observable_event(event) for event in events],
            "after_sequence": after_sequence,
            "next_after_sequence": events[-1]["sequence"] if events else after_sequence,
            "has_more": len(events) == limit,
        }

    @app.post("/api/inspect")
    def inspect(payload: Mapping[str, Any]) -> dict[str, Any]:
        try:
            actual = Observation.from_jsonable(_as_mapping(payload["actual"]))
            predicted = Observation.from_jsonable(_as_mapping(payload["predicted"]))
            diff = compare_observations(predicted, actual)
        except (KeyError, TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {
            "actual_scene": parse_scene(actual.latest).to_jsonable(),
            "predicted_scene": parse_scene(predicted.latest).to_jsonable(),
            "diff": diff.to_jsonable(),
        }

    @app.get("/")
    def index() -> Any:
        return FileResponse(static / "index.html")

    app.mount("/assets", StaticFiles(directory=static), name="assets")
    return app


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("observation must be an object")
    return value


_HIDDEN_PROVIDER_FIELDS = frozenset(
    {
        "analysis",
        "chain_of_thought",
        "encrypted_content",
        "internal_reasoning",
        "reasoning_content",
    }
)


def _observable_event(event: dict[str, Any]) -> dict[str, Any]:
    return {key: _observable_value(value) for key, value in event.items()}


def _observable_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _observable_value(item)
            for key, item in value.items()
            if key.casefold() not in _HIDDEN_PROVIDER_FIELDS
        }
    if isinstance(value, list):
        return [_observable_value(item) for item in value]
    return value
