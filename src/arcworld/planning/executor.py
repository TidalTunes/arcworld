"""Spend a simulated plan one action at a time and stop at first surprise."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from arcworld.env.base import Environment
from arcworld.models.contract import RuleProgram
from arcworld.perception.diff import ObservationDiff, compare_observations
from arcworld.planning.dsl import Plan
from arcworld.types import Action, GameStatus, Observation


@dataclass(frozen=True, slots=True)
class ExecutionStep:
    action: Action
    predicted: Observation
    actual: Observation
    diff: ObservationDiff


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    steps: tuple[ExecutionStep, ...]
    remaining: tuple[Action, ...]
    diverged: bool
    terminal: bool
    game_over: bool
    final_state: Mapping[str, Any]
    final_observation: Observation


class VerifiedExecutor:
    def __init__(
        self,
        *,
        require_status: bool = True,
        require_levels: bool = True,
        require_available_actions: bool = True,
        require_full_reset: bool = True,
    ) -> None:
        self.require_status = require_status
        self.require_levels = require_levels
        self.require_available_actions = require_available_actions
        self.require_full_reset = require_full_reset

    def execute(
        self,
        plan: Plan,
        *,
        environment: Environment,
        program: RuleProgram,
        model_state: Mapping[str, Any],
        observation: Observation,
        on_intent: Callable[[Action], None] | None = None,
        on_raw_step: Callable[[Action, Observation, Observation], None] | None = None,
        on_step: Callable[[ExecutionStep], None] | None = None,
        max_actions: int | None = None,
    ) -> ExecutionResult:
        if max_actions is not None and max_actions < 0:
            raise ValueError("max_actions must be non-negative")
        state = dict(model_state)
        current = observation
        steps: list[ExecutionStep] = []
        remaining = plan.actions
        diverged = False
        authorized_actions = plan.actions if max_actions is None else plan.actions[:max_actions]
        for index, action in enumerate(authorized_actions):
            prediction = program.predict(state, action, current)
            if on_intent:
                on_intent(action)
            actual = environment.step(action)
            if on_raw_step:
                on_raw_step(action, prediction.observation, actual)
            diff = compare_observations(prediction.observation, actual)
            step = ExecutionStep(action, prediction.observation, actual, diff)
            steps.append(step)
            if on_step:
                on_step(step)
            current = actual
            remaining = plan.actions[index + 1 :]
            if not self._matches(diff):
                diverged = True
                break
            state = prediction.state
            if actual.status in (GameStatus.WIN, GameStatus.GAME_OVER):
                break
        return ExecutionResult(
            steps=tuple(steps),
            remaining=remaining,
            diverged=diverged,
            terminal=current.status is GameStatus.WIN,
            game_over=current.status is GameStatus.GAME_OVER,
            final_state=state,
            final_observation=current,
        )

    def _matches(self, diff: ObservationDiff) -> bool:
        return (
            diff.pixels.equal
            and (diff.status_match or not self.require_status)
            and (diff.level_match or not self.require_levels)
            and (diff.available_actions_match or not self.require_available_actions)
            and (diff.full_reset_match or not self.require_full_reset)
        )
