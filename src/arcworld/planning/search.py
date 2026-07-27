"""Bounded breadth-first search over a certified executable program."""

from __future__ import annotations

import json
from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from arcworld.models.contract import RuleProgram
from arcworld.types import Action


@dataclass(frozen=True, slots=True)
class SearchResult:
    found: bool
    actions: tuple[Action, ...]
    expanded: int
    depth: int
    reason: str


def breadth_first_search(
    program: RuleProgram,
    initial_state: Mapping[str, Any],
    actions: Iterable[Action],
    *,
    max_depth: int = 30,
    max_nodes: int = 20_000,
) -> SearchResult:
    action_space = tuple(actions)
    queue: deque[tuple[dict[str, Any], tuple[Action, ...]]] = deque(
        [(dict(initial_state), tuple())]
    )
    seen = {_state_key(initial_state)}
    expanded = 0
    while queue and expanded < max_nodes:
        state, path = queue.popleft()
        if program.is_goal(state):
            return SearchResult(True, path, expanded, len(path), "goal")
        if len(path) >= max_depth:
            continue
        expanded += 1
        for action in action_space:
            try:
                next_state = program.step_state(state, action)
            except Exception:
                continue
            key = _state_key(next_state)
            if key in seen:
                continue
            seen.add(key)
            queue.append((next_state, path + (action,)))
    reason = "node_limit" if expanded >= max_nodes else "depth_exhausted"
    return SearchResult(False, tuple(), expanded, max_depth, reason)


def _state_key(state: Mapping[str, Any]) -> str:
    return json.dumps(state, sort_keys=True, separators=(",", ":"))
