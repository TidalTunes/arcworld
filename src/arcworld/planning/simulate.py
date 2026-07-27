"""Complete a plan rollout before its first real action is authorized."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from arcworld.models.contract import RuleProgram
from arcworld.planning.dsl import Plan
from arcworld.types import ActionKind, GameStatus, Observation


@dataclass(frozen=True, slots=True)
class SimulatedStep:
    action_index: int
    state: Mapping[str, Any]
    observation: Observation


@dataclass(frozen=True, slots=True)
class SimulationRollout:
    steps: tuple[SimulatedStep, ...]
    terminal: bool
    final_state: Mapping[str, Any]
    final_observation: Observation


def simulate_plan(
    program: RuleProgram,
    state: Mapping[str, Any],
    observation: Observation,
    plan: Plan,
) -> SimulationRollout:
    """Roll out every planned step without touching the real environment."""
    current_state = dict(state)
    current_observation = observation
    steps: list[SimulatedStep] = []
    for index, action in enumerate(plan.actions):
        if (
            action.kind is not ActionKind.RESET
            and current_observation.available_actions
            and action.kind not in current_observation.available_actions
        ):
            raise ValueError(f"plan uses unavailable action {action} at step {index}")
        prediction = program.predict(current_state, action, current_observation)
        current_state = prediction.state
        current_observation = prediction.observation
        steps.append(SimulatedStep(index, current_state, current_observation))
        if current_observation.status is GameStatus.WIN:
            if index != len(plan.actions) - 1:
                raise ValueError("plan contains actions after a predicted terminal state")
            break
        if (
            current_observation.status is GameStatus.GAME_OVER
            and index != len(plan.actions) - 1
            and plan.actions[index + 1].kind is not ActionKind.RESET
        ):
            raise ValueError("only RESET may follow a predicted GAME_OVER state")
    return SimulationRollout(
        steps=tuple(steps),
        terminal=current_observation.status is GameStatus.WIN,
        final_state=current_state,
        final_observation=current_observation,
    )
