"""Append-only episode evidence."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from arcworld.types import Action, Observation, Transition


@dataclass(slots=True)
class EpisodeHistory:
    initial: Observation
    transitions: list[Transition] = field(default_factory=list)

    @property
    def latest(self) -> Observation:
        return self.transitions[-1].after if self.transitions else self.initial

    def append(
        self,
        action: Action,
        after: Observation,
        *,
        reasoning: dict[str, object] | None = None,
    ) -> Transition:
        item = Transition(
            index=len(self.transitions),
            before=self.latest,
            action=action,
            after=after,
            reasoning=reasoning or {},
        )
        self.transitions.append(item)
        return item

    @classmethod
    def from_transitions(
        cls, initial: Observation, transitions: Iterable[Transition]
    ) -> EpisodeHistory:
        history = cls(initial)
        for transition in transitions:
            if transition.index != len(history.transitions):
                raise ValueError("transition indexes must be contiguous and zero-based")
            if transition.before != history.latest:
                raise ValueError(f"transition {transition.index} does not follow prior evidence")
            history.transitions.append(transition)
        return history
