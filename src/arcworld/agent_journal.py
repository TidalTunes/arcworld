"""Journal callbacks kept out of the high-level control loop."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from arcworld.agent_contracts import AgentResult
from arcworld.history import EpisodeHistory
from arcworld.planning.executor import ExecutionStep
from arcworld.storage import RunStore
from arcworld.types import Action, GameStatus, Observation, Transition


@dataclass(slots=True)
class AgentJournal:
    history: EpisodeHistory
    store: RunStore | None
    run_id: str | None

    def started(self, *, action_budget: int) -> None:
        self._record(
            "run_started",
            {
                "action_budget": action_budget,
                "initial_game_id": self.history.initial.game_id,
                "initial_status": self.history.initial.status.value,
            },
        )

    def initial(self, observation: Observation) -> None:
        self._record("initial_observation", observation.to_jsonable())

    def model_initialized(
        self,
        model_digest: str,
        state: Mapping[str, Any],
        *,
        phase: str,
    ) -> None:
        self._record(
            "model_executed",
            {
                "model_digest": model_digest,
                "function": "initial_state" if phase == "initial" else "history_replay",
                "phase": phase,
                "state_sha256": _mapping_digest(state),
                "transition_count": len(self.history.transitions),
                "sandbox_process_returned_json": True,
            },
        )

    def finished(
        self,
        *,
        status: GameStatus,
        revisions: int,
        reason: str,
    ) -> AgentResult:
        result = AgentResult(
            self.history,
            status,
            len(self.history.transitions),
            revisions,
            reason,
        )
        self._record(
            "run_finished",
            {
                "status": status.value,
                "real_actions": result.real_actions,
                "revisions": revisions,
                "reason": reason,
            },
        )
        return result

    def execution(
        self,
        model_digest: str,
        plan_digest: str,
        *,
        plan_id: str = "",
        controller_version: int | None = None,
    ) -> ExecutionJournal:
        return ExecutionJournal(
            self,
            model_digest,
            plan_digest,
            plan_id=plan_id,
            controller_version=controller_version,
        )

    def _record(self, kind: str, payload: dict[str, object]) -> None:
        if self.store and self.run_id:
            self.store.append(self.run_id, kind, payload)


@dataclass(slots=True)
class ExecutionJournal:
    parent: AgentJournal
    model_digest: str
    plan_digest: str
    plan_id: str = ""
    controller_version: int | None = None

    def intent(self, action: Action) -> None:
        control = self._control_fields()
        self.parent._record(
            "action_intent",
            {
                "action": action.to_jsonable(),
                "model_digest": self.model_digest,
                "plan_digest": self.plan_digest,
                **control,
            },
        )

    def raw(self, action: Action, predicted: Observation, actual: Observation) -> None:
        transition = Transition(
            index=len(self.parent.history.transitions),
            before=self.parent.history.latest,
            action=action,
            after=actual,
        )
        self.parent._record(
            "transition_raw",
            {
                "transition": transition.to_jsonable(),
                "predicted": predicted.to_jsonable(),
                **self._control_fields(),
            },
        )
        self.parent.history.transitions.append(transition)

    def analysis(self, step: ExecutionStep) -> None:
        self.parent._record(
            "transition_analysis",
            {
                "transition_index": len(self.parent.history.transitions) - 1,
                "diff": step.diff.to_jsonable(),
                "model_digest": self.model_digest,
                "plan_digest": self.plan_digest,
                **self._control_fields(),
            },
        )

    def _control_fields(self) -> dict[str, object]:
        value: dict[str, object] = {}
        if self.plan_id:
            value["plan_id"] = self.plan_id
        if self.controller_version is not None:
            value["controller_version"] = self.controller_version
        return value


def _mapping_digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(dict(value), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()
