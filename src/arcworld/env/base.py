"""A narrow environment interface shared by SDK, replay, and synthetic worlds."""

from __future__ import annotations

from typing import Protocol

from arcworld.types import Action, Observation


class Environment(Protocol):
    def start(self) -> Observation:
        """Return the already-initialized first observation without spending a reset."""
        ...

    def reset(self) -> Observation: ...

    def step(self, action: Action) -> Observation: ...
