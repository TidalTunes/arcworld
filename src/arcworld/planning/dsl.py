"""A small Python-facing plan language: code produces actions, never spends them."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from arcworld.models.contract import validate_generated_source
from arcworld.sandbox import GeneratedProcess
from arcworld.types import Action, ActionKind


@dataclass(frozen=True, slots=True)
class Plan:
    actions: tuple[Action, ...]
    source_digest: str = ""
    rationale: str = ""

    def __post_init__(self) -> None:
        if not self.actions:
            raise ValueError("a plan must contain at least one action")


class PlanAPI:
    """The only capability exposed to generated plan code."""

    def action(self, name: str) -> Action:
        return Action.named(name)

    def click(self, x: int, y: int) -> Action:
        return Action(ActionKind.ACTION6, x=x, y=y)

    def reset(self) -> Action:
        return Action(ActionKind.RESET)

    def repeat(self, action: Action, count: int) -> list[Action]:
        if not 0 <= count <= 256:
            raise ValueError("repeat count must be in 0..256")
        return [action] * count

    def sequence(self, *parts: Action | Iterable[Action]) -> list[Action]:
        result: list[Action] = []
        for part in parts:
            if isinstance(part, Action):
                result.append(part)
            else:
                result.extend(part)
        return result


def compile_plan(
    source: str,
    context: Mapping[str, Any],
    *,
    timeout_seconds: float = 2.0,
) -> Plan:
    """Execute a validated ``build_plan(api, context)`` function."""
    normalized = source.strip() + "\n"
    validate_generated_source(normalized, {"build_plan"})
    runtime = GeneratedProcess(normalized, timeout_seconds=timeout_seconds)
    try:
        raw = runtime.build_plan(context)
    finally:
        runtime.close()
    actions = tuple(Action.from_jsonable(item) for item in raw)
    if not actions:
        raise TypeError("build_plan returned no actions")
    if len(actions) > 512:
        raise ValueError("plan exceeds the 512-action safety limit")
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return Plan(actions=actions, source_digest=digest)
