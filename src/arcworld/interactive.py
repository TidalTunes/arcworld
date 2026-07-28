"""A phase-addressable controller for observable, one-action-at-a-time episodes."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from threading import RLock
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from arcworld.agent_contracts import AgentResult, replay_state
from arcworld.agent_journal import AgentJournal
from arcworld.history import EpisodeHistory
from arcworld.models.contract import RuleProgram
from arcworld.planning.dsl import Plan
from arcworld.planning.simulate import simulate_plan
from arcworld.types import Action, GameStatus, Observation

if TYPE_CHECKING:
    from arcworld.agent import WorldModelAgent


class EpisodePhase(StrEnum):
    """The next independently authorized unit of agent work."""

    START = "start"
    INDUCTION = "induction"
    PLANNING = "planning"
    EXECUTION = "execution"
    REVISION = "revision"
    OUTCOME_UNKNOWN = "outcome_unknown"
    FINISHED = "finished"
    ERROR = "error"


_TERMINAL_PHASES = frozenset(
    {EpisodePhase.FINISHED, EpisodePhase.ERROR, EpisodePhase.OUTCOME_UNKNOWN}
)


class _OutcomeUnknownError(RuntimeError):
    pass


@dataclass(slots=True)
class InteractiveEpisode:
    """Expose the normal agent loop as explicit, auditable phase transitions.

    Planning still simulates a complete proposed plan. Execution authorizes only
    its next action, so a GUI click cannot accidentally spend an entire plan.
    """

    agent: WorldModelAgent
    action_budget: int = 500
    phase: EpisodePhase = field(default=EpisodePhase.START, init=False)
    active_phase: EpisodePhase | None = field(default=None, init=False)
    observation: Observation | None = field(default=None, init=False)
    history: EpisodeHistory | None = field(default=None, init=False)
    program: RuleProgram | None = field(default=None, init=False)
    model_state: dict[str, object] | None = field(default=None, init=False)
    pending_plan: Plan | None = field(default=None, init=False)
    pending_plan_id: str | None = field(default=None, init=False)
    revision_count: int = field(default=0, init=False)
    latest_mismatch: dict[str, object] | None = field(default=None, init=False)
    result: AgentResult | None = field(default=None, init=False)
    error: str | None = field(default=None, init=False)
    state_version: int = field(default=0, init=False)
    finish_after_revision_reason: str | None = field(default=None, init=False)
    _journal: AgentJournal | None = field(default=None, init=False, repr=False)
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.action_budget <= 0:
            raise ValueError("action_budget must be positive")

    @property
    def run_id(self) -> str | None:
        return self.agent.run_id

    @property
    def can_advance(self) -> bool:
        with self._lock:
            return self.active_phase is None and self.phase not in _TERMINAL_PHASES

    def advance(self) -> dict[str, Any]:
        """Complete exactly one phase and return the resulting public snapshot."""

        with self._lock:
            if self.active_phase is not None:
                raise RuntimeError(f"phase {self.active_phase.value!r} is already running")
            if self.phase in _TERMINAL_PHASES:
                raise RuntimeError(f"episode is already {self.phase.value}")
            authorized = self.phase
            self.active_phase = authorized
        try:
            self._record(
                "interactive_phase_started",
                {
                    "phase": authorized.value,
                    "real_actions": self._action_count(),
                    "revision_count": self.revision_count,
                    "state_version": self.state_version,
                },
            )
            self._dispatch(authorized)
        except _OutcomeUnknownError as exc:
            with self._lock:
                self.error = str(exc)
                self.phase = EpisodePhase.OUTCOME_UNKNOWN
                self.state_version += 1
            self._close_model_runtime()
            self._record(
                "interactive_phase_failed",
                {
                    "phase": authorized.value,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "outcome_unknown": True,
                    "real_actions": self._action_count(),
                    "revision_count": self.revision_count,
                    "state_version": self.state_version,
                },
            )
            self._record(
                "run_error",
                {
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "outcome_unknown": True,
                },
            )
        except Exception as exc:
            with self._lock:
                self.error = f"{type(exc).__name__}: {exc}"
                self.phase = EpisodePhase.ERROR
                self.state_version += 1
            self._close_model_runtime()
            self._record(
                "interactive_phase_failed",
                {
                    "phase": authorized.value,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "real_actions": self._action_count(),
                    "revision_count": self.revision_count,
                    "state_version": self.state_version,
                },
            )
            self._record(
                "run_error",
                {"error_type": type(exc).__name__, "error": str(exc)},
            )
            raise
        else:
            with self._lock:
                self.state_version += 1
            self._record(
                "interactive_phase_completed",
                {
                    "phase": authorized.value,
                    "next_phase": self.phase.value,
                    "real_actions": self._action_count(),
                    "revision_count": self.revision_count,
                    "status": self.observation.status.value if self.observation else None,
                    "state_version": self.state_version,
                },
            )
        finally:
            with self._lock:
                self.active_phase = None
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        """Return enough state for a local UI without replacing event evidence."""

        with self._lock:
            observation = self.observation
            plan = self.pending_plan
            plan_id = self.pending_plan_id
            result = self.result
            active = self.active_phase
            phase = self.phase
            error = self.error
            revision_count = self.revision_count
            action_count = self._action_count()
            model_digest = self.program.digest if self.program else None
            state_version = self.state_version
            latest_mismatch = self.latest_mismatch
        pending = None
        if plan is not None:
            pending = {
                "plan_digest": plan.source_digest,
                "plan_id": plan_id,
                "rationale": plan.rationale,
                "remaining_count": len(plan.actions),
                "actions": [action.to_jsonable() for action in plan.actions],
            }
        return {
            "run_id": self.run_id,
            "state_version": state_version,
            "phase": phase.value,
            "active_phase": active.value if active else None,
            "can_advance": active is None and phase not in _TERMINAL_PHASES,
            "action_budget": self.action_budget,
            "real_actions": action_count,
            "remaining_actions": max(0, self.action_budget - action_count),
            "revision_count": revision_count,
            "model_digest": model_digest,
            "pending_plan": pending,
            "latest_mismatch": latest_mismatch,
            "observation": observation.to_jsonable() if observation else None,
            "error": error,
            "result": (
                {
                    "status": result.status.value,
                    "real_actions": result.real_actions,
                    "revisions": result.revisions,
                    "reason": result.reason,
                }
                if result
                else None
            ),
        }

    def _dispatch(self, phase: EpisodePhase) -> None:
        if phase is EpisodePhase.START:
            self._start()
        elif phase is EpisodePhase.INDUCTION:
            self._induct()
        elif phase is EpisodePhase.PLANNING:
            self._plan()
        elif phase is EpisodePhase.EXECUTION:
            self._execute_one()
        elif phase is EpisodePhase.REVISION:
            self._revise()
        else:
            raise RuntimeError(f"cannot execute phase {phase.value!r}")

    def _start(self) -> None:
        observation = self.agent.environment.start()
        history = EpisodeHistory(observation)
        journal = AgentJournal(history, self.agent.store, self.agent.run_id)
        journal.started(action_budget=self.action_budget)
        journal.initial(observation)
        with self._lock:
            self.observation = observation
            self.history = history
            self._journal = journal
        if observation.status is GameStatus.WIN:
            self._finish(reason="terminal")
        else:
            with self._lock:
                self.phase = EpisodePhase.INDUCTION

    def _induct(self) -> None:
        history, journal = self._started_state()
        program = self.agent.revisions.revise(history, None)
        state = program.initial_state(history.latest)
        journal.model_initialized(program.digest, state, phase="initial")
        with self._lock:
            self.program = program
            self.model_state = dict(state)
            self.revision_count = 1
            self.phase = EpisodePhase.PLANNING

    def _plan(self) -> None:
        history, _journal = self._started_state()
        program, state, observation = self._model_state()
        remaining_budget = self.action_budget - len(history.transitions)
        if remaining_budget <= 0:
            self._finish(reason="action_budget")
            return
        plan = self.agent.planner.plan(program, state, observation, history)
        if len(plan.actions) > remaining_budget:
            plan = Plan(
                plan.actions[:remaining_budget],
                source_digest=plan.source_digest,
                source=plan.source,
                rationale=f"{plan.rationale}; clipped to real-action budget",
                origin_request_id=plan.origin_request_id,
                origin_response_digest=plan.origin_response_digest,
            )
        rollout = simulate_plan(program, state, observation, plan)
        self._record(
            "controller_plan_certified",
            {
                "model_digest": program.digest,
                "plan_digest": plan.source_digest,
                "steps": len(rollout.steps),
                "terminal": rollout.terminal,
                "final_status": rollout.final_observation.status.value,
                "complete_before_real_action": True,
                "starting_transition_count": len(history.transitions),
                "controller_version": self.state_version,
            },
        )
        self._record(
            "interactive_decision",
            {
                "decision": "plan_committed",
                "plan_id": (plan_id := uuid4().hex),
                "model_digest": program.digest,
                "plan_digest": plan.source_digest,
                "rationale": plan.rationale,
                "actions": [action.to_jsonable() for action in plan.actions],
                "complete_simulation_required": True,
                "starting_transition_count": len(history.transitions),
                "controller_version": self.state_version,
            },
        )
        with self._lock:
            self.pending_plan = plan
            self.pending_plan_id = plan_id
            self.phase = EpisodePhase.EXECUTION

    def _execute_one(self) -> None:
        history, journal = self._started_state()
        program, state, observation = self._model_state()
        plan = self.pending_plan
        if plan is None:
            raise RuntimeError("execution phase has no committed plan")
        plan_id = self.pending_plan_id
        if plan_id is None:
            raise RuntimeError("execution phase has no plan instance identity")
        remaining_budget = self.action_budget - len(history.transitions)
        if remaining_budget <= 0:
            self._finish(reason="action_budget")
            return
        execution_journal = journal.execution(
            program.digest,
            plan.source_digest,
            plan_id=plan_id,
            controller_version=self.state_version,
        )
        intent_recorded = False

        def record_intent(action: Action) -> None:
            nonlocal intent_recorded
            execution_journal.intent(action)
            intent_recorded = True

        transition_count = len(history.transitions)
        try:
            outcome = self.agent.executor.execute(
                plan,
                environment=self.agent.environment,
                program=program,
                model_state=state,
                observation=observation,
                on_intent=record_intent,
                on_raw_step=execution_journal.raw,
                on_step=execution_journal.analysis,
                max_actions=1,
            )
        except Exception as exc:
            if intent_recorded and len(history.transitions) == transition_count:
                with self._lock:
                    self.pending_plan = None
                    self.pending_plan_id = None
                    self.phase = EpisodePhase.OUTCOME_UNKNOWN
                self._record(
                    "action_outcome_unknown",
                    {
                        "action": plan.actions[0].to_jsonable(),
                        "plan_id": plan_id,
                        "plan_digest": plan.source_digest,
                        "model_digest": program.digest,
                        "controller_version": self.state_version,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    },
                )
                raise _OutcomeUnknownError(
                    "a real action was intended, but no durable outcome was recorded; "
                    "the episode is inspection-only to prevent duplicate spending"
                ) from exc
            raise
        if len(outcome.steps) != 1:
            raise RuntimeError("an execution phase must spend exactly one real action")
        step = outcome.steps[0]
        with self._lock:
            self.observation = outcome.final_observation
        if outcome.diverged:
            finish_reason = (
                "terminal"
                if outcome.terminal
                else "action_budget"
                if len(history.transitions) >= self.action_budget
                else None
            )
            with self._lock:
                self.latest_mismatch = step.diff.to_jsonable()
                self.pending_plan = None
                self.pending_plan_id = None
                self.finish_after_revision_reason = finish_reason
                self.phase = EpisodePhase.REVISION
            self._record(
                "interactive_decision",
                {
                    "decision": "action_observed",
                    "plan_id": plan_id,
                    "action": step.action.to_jsonable(),
                    "model_digest": program.digest,
                    "plan_digest": plan.source_digest,
                    "matched": False,
                    "discarded_actions": len(outcome.remaining),
                    "controller_version": self.state_version,
                },
            )
            self._record_plan_invalidation(
                plan,
                plan_id,
                program.digest,
                "prediction_mismatch",
                outcome.remaining,
            )
            return
        self._record(
            "interactive_decision",
            {
                "decision": "action_observed",
                "plan_id": plan_id,
                "action": step.action.to_jsonable(),
                "model_digest": program.digest,
                "plan_digest": plan.source_digest,
                "matched": True,
                "discarded_actions": 0,
                "controller_version": self.state_version,
            },
        )
        if outcome.terminal:
            if outcome.remaining:
                self._record_plan_invalidation(
                    plan,
                    plan_id,
                    program.digest,
                    "terminal_observation",
                    outcome.remaining,
                )
            with self._lock:
                self.pending_plan = None
                self.pending_plan_id = None
            self._finish(reason="terminal")
            return
        if len(history.transitions) >= self.action_budget:
            if outcome.remaining:
                self._record_plan_invalidation(
                    plan,
                    plan_id,
                    program.digest,
                    "action_budget_exhausted",
                    outcome.remaining,
                )
            with self._lock:
                self.pending_plan = None
                self.pending_plan_id = None
            self._finish(reason="action_budget")
            return
        if outcome.game_over:
            if outcome.remaining:
                self._record_plan_invalidation(
                    plan,
                    plan_id,
                    program.digest,
                    "game_over_requires_fresh_reset_plan",
                    outcome.remaining,
                )
            with self._lock:
                self.model_state = dict(outcome.final_state)
                self.pending_plan = None
                self.pending_plan_id = None
                self.phase = EpisodePhase.PLANNING
            return
        with self._lock:
            self.model_state = dict(outcome.final_state)
            if not outcome.remaining:
                self.pending_plan = None
                self.pending_plan_id = None
                self.phase = EpisodePhase.PLANNING
            else:
                self.pending_plan = _remaining_plan(plan, outcome.remaining)
                self.phase = EpisodePhase.EXECUTION

    def _revise(self) -> None:
        history, journal = self._started_state()
        if self.latest_mismatch is None:
            raise RuntimeError("revision phase has no counterexample")
        program = self.agent.revisions.revise(history, self.latest_mismatch)
        state = replay_state(program, history)
        journal.model_initialized(program.digest, state, phase="revision-replay")
        finish_reason = self.finish_after_revision_reason
        with self._lock:
            self.program = program
            self.model_state = dict(state)
            self.revision_count += 1
            self.latest_mismatch = None
            self.finish_after_revision_reason = None
            if finish_reason is None:
                self.phase = EpisodePhase.PLANNING
        if finish_reason is not None:
            self._finish(reason=finish_reason)

    def _finish(self, *, reason: str) -> None:
        _history, journal = self._started_state()
        if self.observation is None:
            raise RuntimeError("cannot finish before the first observation")
        result = journal.finished(
            status=self.observation.status,
            revisions=self.revision_count,
            reason=reason,
        )
        self._close_model_runtime()
        with self._lock:
            self.result = result
            self.pending_plan = None
            self.pending_plan_id = None
            self.phase = EpisodePhase.FINISHED

    def _started_state(self) -> tuple[EpisodeHistory, AgentJournal]:
        if self.history is None or self._journal is None:
            raise RuntimeError("episode has not started")
        return self.history, self._journal

    def _model_state(self) -> tuple[RuleProgram, Mapping[str, object], Observation]:
        if self.program is None or self.model_state is None or self.observation is None:
            raise RuntimeError("episode has no committed world model")
        return self.program, self.model_state, self.observation

    def _action_count(self) -> int:
        return len(self.history.transitions) if self.history else 0

    def _record(self, kind: str, payload: Mapping[str, Any]) -> None:
        if self.agent.store is not None and self.agent.run_id is not None:
            self.agent.store.append(self.agent.run_id, kind, payload)

    def _close_model_runtime(self) -> None:
        if self.program is not None:
            self.program.close()

    def _record_plan_invalidation(
        self,
        plan: Plan,
        plan_id: str,
        model_digest: str,
        reason: str,
        discarded: tuple[Action, ...],
    ) -> None:
        self._record(
            "plan_invalidated",
            {
                "plan_id": plan_id,
                "plan_digest": plan.source_digest,
                "model_digest": model_digest,
                "reason": reason,
                "discarded_actions": [action.to_jsonable() for action in discarded],
                "controller_version": self.state_version,
            },
        )


def _remaining_plan(plan: Plan, actions: tuple[Action, ...]) -> Plan:
    return Plan(
        actions,
        source_digest=plan.source_digest,
        source=plan.source,
        rationale=plan.rationale,
        origin_request_id=plan.origin_request_id,
        origin_response_digest=plan.origin_response_digest,
    )
