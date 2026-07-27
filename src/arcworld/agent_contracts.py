"""Interfaces and results used by the high-level controller."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from arcworld.history import EpisodeHistory
from arcworld.models.contract import RuleProgram
from arcworld.planning.dsl import Plan
from arcworld.types import GameStatus, Observation


class RevisionService(Protocol):
    def revise(
        self,
        history: EpisodeHistory,
        mismatch: Mapping[str, object] | None,
    ) -> RuleProgram: ...


class PlanningService(Protocol):
    def plan(
        self,
        program: RuleProgram,
        state: Mapping[str, object],
        observation: Observation,
        history: EpisodeHistory,
    ) -> Plan: ...


@dataclass(frozen=True, slots=True)
class AgentResult:
    history: EpisodeHistory
    status: GameStatus
    real_actions: int
    revisions: int
    reason: str


def replay_state(program: RuleProgram, history: EpisodeHistory) -> dict[str, object]:
    state: dict[str, object] = program.initial_state(history.initial)
    previous = history.initial
    for transition in history.transitions:
        prediction = program.predict(state, transition.action, previous)
        state = prediction.state
        previous = transition.after
    return state
