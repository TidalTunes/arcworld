"""FastAPI dashboard API. It never opens a browser or contacts an external service."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from arcworld.audit import audit_real_llm_run
from arcworld.env.toy import TOY_MODEL_SOURCE, ToyKeyDoorEnvironment
from arcworld.models.contract import RuleProgram
from arcworld.perception.components import parse_scene
from arcworld.perception.diff import compare_observations
from arcworld.storage import RunStore
from arcworld.types import Action, Observation


@dataclass(slots=True)
class _LiveToy:
    environment: ToyKeyDoorEnvironment
    program: RuleProgram
    state: dict[str, Any]
    observation: Observation
    run_id: str


def create_app(store_path: Path) -> Any:
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import FileResponse
        from fastapi.staticfiles import StaticFiles
    except ImportError as error:
        raise RuntimeError("install ARCWorld with the 'gui' extra") from error

    store = RunStore(store_path)
    static = Path(__file__).with_name("static")
    app = FastAPI(title="ARCWorld Inspector", docs_url="/api/docs", redoc_url=None)
    sessions: dict[str, _LiveToy] = {}

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "store": str(store_path)}

    @app.get("/api/runs")
    def runs() -> list[dict[str, Any]]:
        return store.list_runs()

    @app.get("/api/runs/{run_id}")
    def run(run_id: str) -> dict[str, Any]:
        try:
            run_record = store.run(run_id)
            experiment = _as_mapping(_as_mapping(run_record["config"]).get("experiment", {}))
            audit = None
            if experiment.get("run_kind") == "official-public-game-live-llm":
                audit = audit_real_llm_run(store, run_id).to_jsonable()
            return {
                "run": run_record,
                "timeline": store.timeline(run_id),
                "audit": audit,
                "event_chain_valid": store.verify_chain(run_id),
            }
        except KeyError as error:
            raise HTTPException(status_code=404, detail="run not found") from error

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

    @app.post("/api/live/toy")
    def start_toy() -> dict[str, Any]:
        environment = ToyKeyDoorEnvironment()
        observation = environment.reset()
        program = RuleProgram.from_source(TOY_MODEL_SOURCE)
        state = program.initial_state(observation)
        run_id = store.create_run(
            "synthetic-key-door-live",
            {"model_digest": program.digest, "source": "built-in synthetic fixture"},
        )
        store.append(run_id, "initial_observation", observation.to_jsonable())
        sessions[run_id] = _LiveToy(environment, program, state, observation, run_id)
        return {"run_id": run_id, "observation": observation.to_jsonable()}

    @app.post("/api/live/{run_id}/action")
    def live_action(run_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        session = sessions.get(run_id)
        if session is None:
            raise HTTPException(status_code=404, detail="live session not found")
        try:
            action = Action.from_jsonable(payload)
            prediction = session.program.predict(session.state, action, session.observation)
            actual = session.environment.step(action)
            diff = compare_observations(prediction.observation, actual)
        except (KeyError, TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        store.append(
            run_id,
            "transition",
            {
                "action": action.to_jsonable(),
                "before": session.observation.to_jsonable(),
                "actual": actual.to_jsonable(),
                "predicted": prediction.observation.to_jsonable(),
                "diff": diff.to_jsonable(),
                "model_digest": session.program.digest,
            },
        )
        if diff.pixels.equal and diff.status_match and diff.level_match:
            session.state = prediction.state
        session.observation = actual
        return {
            "actual": actual.to_jsonable(),
            "predicted": prediction.observation.to_jsonable(),
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
