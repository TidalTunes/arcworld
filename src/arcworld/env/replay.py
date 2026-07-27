"""Deterministic environment backed by an authored evidence trace."""

from __future__ import annotations

from arcworld.types import Action, Observation, Transition


class ReplayEnvironment:
    def __init__(self, initial: Observation, transitions: tuple[Transition, ...]) -> None:
        self.initial = initial
        self.transitions = transitions
        self.position = 0

    def reset(self) -> Observation:
        self.position = 0
        return self.initial

    def start(self) -> Observation:
        self.position = 0
        return self.initial

    def step(self, action: Action) -> Observation:
        if self.position >= len(self.transitions):
            raise RuntimeError("replay is exhausted")
        transition = self.transitions[self.position]
        if action != transition.action:
            raise ValueError(
                f"replay expected {transition.action}, received {action} at {self.position}"
            )
        self.position += 1
        return transition.after
