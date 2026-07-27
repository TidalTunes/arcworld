"""Journal callbacks kept out of the high-level control loop."""

from __future__ import annotations

from dataclasses import dataclass

from arcworld.history import EpisodeHistory
from arcworld.planning.executor import ExecutionStep
from arcworld.storage import RunStore
from arcworld.types import Action, Observation


@dataclass(slots=True)
class AgentJournal:
    history: EpisodeHistory
    store: RunStore | None
    run_id: str | None

    def initial(self, observation: Observation) -> None:
        self._record("initial_observation", observation.to_jsonable())

    def execution(self, model_digest: str, plan_digest: str) -> ExecutionJournal:
        return ExecutionJournal(self, model_digest, plan_digest)

    def _record(self, kind: str, payload: dict[str, object]) -> None:
        if self.store and self.run_id:
            self.store.append(self.run_id, kind, payload)


@dataclass(slots=True)
class ExecutionJournal:
    parent: AgentJournal
    model_digest: str
    plan_digest: str

    def intent(self, action: Action) -> None:
        self.parent._record(
            "action_intent",
            {
                "action": action.to_jsonable(),
                "model_digest": self.model_digest,
                "plan_digest": self.plan_digest,
            },
        )

    def raw(self, action: Action, predicted: Observation, actual: Observation) -> None:
        transition = self.parent.history.append(action, actual)
        self.parent._record(
            "transition_raw",
            {
                "transition": transition.to_jsonable(),
                "predicted": predicted.to_jsonable(),
            },
        )

    def analysis(self, step: ExecutionStep) -> None:
        self.parent._record(
            "transition_analysis",
            {
                "transition_index": len(self.parent.history.transitions) - 1,
                "diff": step.diff.to_jsonable(),
                "model_digest": self.model_digest,
                "plan_digest": self.plan_digest,
            },
        )
