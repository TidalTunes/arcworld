"""Construction and serialized background control for GUI-started tests."""

from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import subprocess
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any, Literal, cast

from arcworld.composition import AgentBundle, build_agent, build_codex_agent, build_openai_agent
from arcworld.env.base import Environment
from arcworld.env.offline_session import DeferredOfflineEnvironment
from arcworld.env.provenance import (
    EnvironmentProvenance,
    collect_environment_provenance,
)
from arcworld.env.toy import TOY_MODEL_SOURCE, ToyKeyDoorEnvironment
from arcworld.interactive import InteractiveEpisode
from arcworld.llm import CallableReasoner, ReasonerConfig

SYNTHETIC_PUZZLE_ID = "synthetic-key-door"
Provider = Literal["deterministic", "codex-cli", "openai-api"]
_PROVIDERS = frozenset({"deterministic", "codex-cli", "openai-api"})
_CODEX_APP = Path("/Applications/ChatGPT.app/Contents/Resources/codex")


class SessionNotFoundError(KeyError):
    pass


class SessionBusyError(RuntimeError):
    pass


class SessionStateError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TestSpec:
    puzzle_id: str
    provider: Provider
    model: str
    effort: str
    action_budget: int
    candidate_count: int
    seed: int

    @classmethod
    def from_jsonable(cls, payload: dict[str, Any]) -> TestSpec:
        puzzle_id = _text(payload.get("puzzle_id", SYNTHETIC_PUZZLE_ID), "puzzle_id")
        default_provider = "deterministic" if puzzle_id == SYNTHETIC_PUZZLE_ID else "codex-cli"
        raw_provider = _text(payload.get("provider", default_provider), "provider")
        if raw_provider not in _PROVIDERS:
            raise ValueError(f"provider must be one of {sorted(_PROVIDERS)}")
        provider = cast(Provider, raw_provider)
        default_model = (
            "deterministic-fixture"
            if provider == "deterministic"
            else "gpt-5.6-luna"
            if provider == "codex-cli"
            else "gpt-5.6-sol"
        )
        default_effort = (
            "fixed" if provider == "deterministic" else "low" if provider == "codex-cli" else "high"
        )
        model = _text(payload.get("model", default_model), "model")
        effort = _text(payload.get("effort", default_effort), "effort")
        action_budget = _integer(payload.get("action_budget", 100), "action_budget")
        candidate_count = _integer(payload.get("candidate_count", 1), "candidate_count")
        seed = _integer(payload.get("seed", 0), "seed")
        if not 1 <= action_budget <= 5000:
            raise ValueError("action_budget must be in 1..5000")
        if not 1 <= candidate_count <= 8:
            raise ValueError("candidate_count must be in 1..8")
        if not 0 <= seed <= 2_147_483_647:
            raise ValueError("seed must be in 0..2147483647")
        if provider == "deterministic" and puzzle_id != SYNTHETIC_PUZZLE_ID:
            raise ValueError("the deterministic fixture provider is synthetic-only")
        if provider == "deterministic" and candidate_count != 1:
            raise ValueError("the deterministic fixture has exactly one candidate")
        return cls(
            puzzle_id=puzzle_id,
            provider=provider,
            model=model,
            effort=effort,
            action_budget=action_budget,
            candidate_count=candidate_count,
            seed=seed,
        )

    def to_jsonable(self) -> dict[str, str | int]:
        return {
            "puzzle_id": self.puzzle_id,
            "provider": self.provider,
            "model": self.model,
            "effort": self.effort,
            "action_budget": self.action_budget,
            "candidate_count": self.candidate_count,
            "seed": self.seed,
        }


@dataclass(frozen=True, slots=True)
class TestFactory:
    """Create a fresh paused test without making a model call."""

    store_path: Path
    workspace: Path
    environments_dir: Path
    recordings_dir: Path
    codex_bin: Path | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "store_path", self.store_path.expanduser().resolve())
        object.__setattr__(self, "workspace", self.workspace.expanduser().resolve())
        object.__setattr__(
            self,
            "environments_dir",
            self.environments_dir.expanduser().resolve(),
        )
        object.__setattr__(
            self,
            "recordings_dir",
            self.recordings_dir.expanduser().resolve(),
        )
        if self.codex_bin is not None:
            object.__setattr__(self, "codex_bin", self.codex_bin.expanduser().resolve())

    def create(self, spec: TestSpec) -> InteractiveEpisode:
        environment: Environment
        if spec.provider == "openai-api" and not os.environ.get("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY is required for the OpenAI API provider")
        if spec.puzzle_id == SYNTHETIC_PUZZLE_ID:
            environment = ToyKeyDoorEnvironment()
            provenance = None
            run_kind = "synthetic-interactive-test"
            evaluation_lane = "synthetic-regression"
        else:
            provenance = collect_environment_provenance(
                environments_dir=self.environments_dir,
                game_id=spec.puzzle_id,
            )
            environment = DeferredOfflineEnvironment(
                game_id=spec.puzzle_id,
                environments_dir=self.environments_dir,
                recordings_dir=self.recordings_dir,
                seed=spec.seed,
                expected_provenance=provenance,
                save_recording=True,
            )
            run_kind = "official-public-game-live-llm"
            evaluation_lane = "public-demo"
        metadata = _run_metadata(spec, provenance, run_kind, evaluation_lane)
        bundle = self._bundle(environment, spec, metadata)
        return InteractiveEpisode(bundle.agent, action_budget=spec.action_budget)

    def _bundle(
        self,
        environment: Environment,
        spec: TestSpec,
        metadata: dict[str, Any],
    ) -> AgentBundle:
        label = f"interactive:{spec.puzzle_id}:{spec.provider}"
        if spec.provider == "deterministic":
            return build_agent(
                environment,
                revision_reasoner=CallableReasoner(
                    ReasonerConfig(spec.model, spec.effort, "revision"),
                    _toy_revision,
                ),
                planning_reasoner=CallableReasoner(
                    ReasonerConfig(spec.model, spec.effort, "planning"),
                    _toy_plan,
                ),
                workspace=self.workspace,
                store_path=self.store_path,
                label=label,
                candidate_count=spec.candidate_count,
                run_metadata=metadata,
            )
        if spec.provider == "codex-cli":
            return build_codex_agent(
                environment,
                model=spec.model,
                effort=spec.effort,
                executable=self.codex_bin,
                workspace=self.workspace,
                store_path=self.store_path,
                label=label,
                candidate_count=spec.candidate_count,
                run_metadata=metadata,
            )
        return build_openai_agent(
            environment,
            model=spec.model,
            effort=spec.effort,
            workspace=self.workspace,
            store_path=self.store_path,
            label=label,
            candidate_count=spec.candidate_count,
            run_metadata=metadata,
        )


@dataclass(slots=True)
class ManagedSession:
    controller: InteractiveEpisode
    spec: TestSpec
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    busy: bool = False
    last_error: str | None = None
    _future: Future[dict[str, Any]] | None = field(default=None, init=False, repr=False)
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)

    def snapshot(self) -> dict[str, Any]:
        controller = self.controller.snapshot()
        with self._lock:
            busy = self.busy
            last_error = self.last_error
        controller.update(
            {
                "busy": busy,
                "can_advance": bool(controller["can_advance"]) and not busy,
                "created_at": self.created_at,
                "test": self.spec.to_jsonable(),
                "worker_error": last_error,
            }
        )
        return controller


class SessionRegistry:
    """Serialize every test while allowing status and event polling."""

    def __init__(self, *, max_workers: int = 1) -> None:
        if max_workers <= 0:
            raise ValueError("max_workers must be positive")
        self._sessions: dict[str, ManagedSession] = {}
        self._lock = RLock()
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="arcworld-test",
        )

    def add(self, controller: InteractiveEpisode, spec: TestSpec) -> dict[str, Any]:
        if controller.run_id is None:
            raise ValueError("interactive tests require an evidence run")
        session = ManagedSession(controller, spec)
        with self._lock:
            if controller.run_id in self._sessions:
                raise RuntimeError(f"duplicate session run_id {controller.run_id}")
            self._sessions[controller.run_id] = session
        return session.snapshot()

    def get(self, run_id: str) -> dict[str, Any]:
        return self._session(run_id).snapshot()

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            sessions = tuple(self._sessions.values())
        return sorted(
            (session.snapshot() for session in sessions),
            key=lambda item: str(item["created_at"]),
            reverse=True,
        )

    def advance(
        self,
        run_id: str,
        *,
        expected_state_version: int,
        authorize_real_action: bool = False,
    ) -> dict[str, Any]:
        session = self._session(run_id)
        with session._lock:
            snapshot = session.controller.snapshot()
            actual_version = int(snapshot["state_version"])
            if expected_state_version != actual_version:
                raise SessionStateError(
                    f"stale state version {expected_state_version}; current is {actual_version}"
                )
            if session.busy:
                raise SessionBusyError("a phase is already running")
            if not bool(snapshot["can_advance"]):
                raise SessionStateError(f"episode cannot advance from {snapshot['phase']}")
            if snapshot["phase"] == "execution" and not authorize_real_action:
                raise SessionStateError(
                    "execution requires explicit authorization for one real action"
                )
            session.busy = True
            session.last_error = None
            try:
                session._future = self._executor.submit(self._run_one, session)
            except Exception:
                session.busy = False
                raise
        return session.snapshot()

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _session(self, run_id: str) -> ManagedSession:
        with self._lock:
            session = self._sessions.get(run_id)
        if session is None:
            raise SessionNotFoundError(run_id)
        return session

    @staticmethod
    def _run_one(session: ManagedSession) -> dict[str, Any]:
        try:
            return session.controller.advance()
        except Exception as exc:
            with session._lock:
                session.last_error = f"{type(exc).__name__}: {exc}"
            return session.controller.snapshot()
        finally:
            with session._lock:
                session.busy = False


def provider_capabilities(codex_bin: Path | None = None) -> list[dict[str, Any]]:
    codex_candidate: Path | None
    if codex_bin is not None:
        codex_candidate = codex_bin.expanduser()
    elif os.environ.get("ARCWORLD_CODEX_BIN"):
        codex_candidate = Path(os.environ["ARCWORLD_CODEX_BIN"]).expanduser()
    elif _CODEX_APP.is_file():
        codex_candidate = _CODEX_APP
    else:
        discovered = shutil.which("codex")
        codex_candidate = Path(discovered) if discovered else None
    codex_available = (
        codex_candidate is not None
        and codex_candidate.is_file()
        and os.access(codex_candidate, os.X_OK)
    )
    return [
        {
            "id": "deterministic",
            "label": "Deterministic fixture",
            "available": True,
            "synthetic_only": True,
            "default_model": "deterministic-fixture",
            "default_effort": "fixed",
            "isolation": "in-process-fixture",
            "notice": "No external model call; intended for harness checks.",
        },
        {
            "id": "codex-cli",
            "label": "OpenAI via Codex CLI · development-only",
            "available": codex_available,
            "synthetic_only": False,
            "default_model": "gpt-5.6-luna",
            "default_effort": "low",
            "isolation": "post-hoc-tool-rejection",
            "notice": (
                "Development transport: tool attempts fail the run after the CLI returns; "
                "this is not a strict confidentiality boundary."
            ),
        },
        {
            "id": "openai-api",
            "label": "OpenAI Responses API",
            "available": bool(os.environ.get("OPENAI_API_KEY"))
            and importlib.util.find_spec("openai") is not None,
            "synthetic_only": False,
            "default_model": "gpt-5.6-sol",
            "default_effort": "high",
            "isolation": "text-only-api-request",
            "notice": (
                "Text-only Responses API request with no tools supplied; model calls may "
                "incur cost."
            ),
        },
    ]


def _run_metadata(
    spec: TestSpec,
    provenance: EnvironmentProvenance | None,
    run_kind: str,
    evaluation_lane: str,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "run_kind": run_kind,
        "evaluation_lane": evaluation_lane,
        "controller": "interactive-phase-v1",
        "provider_transport": spec.provider,
        "action_budget": spec.action_budget,
        "candidate_count": spec.candidate_count,
        "seed": spec.seed,
        "git": _git_state(),
        "python": platform.python_version(),
    }
    if provenance is not None:
        value["environment"] = provenance.to_jsonable()
    return value


def _git_state() -> dict[str, str | bool | None]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    status = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "commit": commit.stdout.strip() if commit.returncode == 0 else None,
        "dirty": bool(status.stdout.strip()) if status.returncode == 0 else None,
    }


def _toy_revision(_instructions: str, _input_text: str) -> str:
    return f"```python\n{TOY_MODEL_SOURCE}\n```"


def _toy_plan(_instructions: str, _input_text: str) -> str:
    return (
        "```python\n"
        "def build_plan(api, context):\n"
        '    return api.repeat(api.action("ACTION4"), 7)\n'
        "```"
    )


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    if len(value) > 256:
        raise ValueError(f"{name} must be at most 256 characters")
    return value.strip()


def _integer(value: Any, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    try:
        converted = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if isinstance(value, float) and not value.is_integer():
        raise ValueError(f"{name} must be an integer")
    return converted
