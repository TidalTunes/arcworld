"""The intentionally small contract for an LLM-authored world model."""

from __future__ import annotations

import ast
import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from arcworld.sandbox import GeneratedProcess
from arcworld.types import Action, ActionKind, GameStatus, Grid, Observation, freeze_grid

_BANNED_CALLS = {
    "__import__",
    "breakpoint",
    "compile",
    "delattr",
    "eval",
    "exec",
    "getattr",
    "globals",
    "input",
    "locals",
    "open",
    "setattr",
    "vars",
}
_BANNED_NODES = (
    ast.AsyncFunctionDef,
    ast.Await,
    ast.ClassDef,
    ast.Delete,
    ast.Global,
    ast.Import,
    ast.ImportFrom,
    ast.Lambda,
    ast.Nonlocal,
    ast.With,
)


class SourceValidationError(ValueError):
    """Generated code violates the narrow model/plan policy."""


@dataclass(frozen=True, slots=True)
class RulePrediction:
    state: dict[str, Any]
    observation: Observation


@dataclass(slots=True)
class RuleProgram:
    """A loaded rule program.

    Required generated functions:

    - ``initial_state(observation) -> dict``
    - ``step(state, action) -> dict``
    - ``render(state) -> grid``

    Optional: ``render_frames``, ``status``, ``metrics``, ``available_actions``,
    ``full_reset``, and ``is_goal``.
    """

    source: str
    function_names: frozenset[str]
    digest: str
    runtime: GeneratedProcess

    @classmethod
    def from_source(
        cls,
        source: str,
        *,
        call_timeout_seconds: float = 2.0,
    ) -> RuleProgram:
        normalized = source.strip() + "\n"
        tree = validate_generated_source(normalized, {"initial_state", "step", "render"})
        function_names = frozenset(
            node.name for node in tree.body if isinstance(node, ast.FunctionDef)
        )
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return cls(
            normalized,
            function_names,
            digest,
            GeneratedProcess(normalized, timeout_seconds=call_timeout_seconds),
        )

    def initial_state(self, observation: Observation) -> dict[str, Any]:
        raw = self.runtime.call(
            "initial_state",
            deepcopy(observation.to_jsonable(expose_identity=False)),
        )
        return _json_dict(raw, "initial_state")

    def step_state(self, state: Mapping[str, Any], action: Action) -> dict[str, Any]:
        raw = self.runtime.call("step", deepcopy(dict(state)), action.to_jsonable())
        return _json_dict(raw, "step")

    def render(self, state: Mapping[str, Any]) -> Grid:
        raw = self.runtime.call("render", deepcopy(dict(state)))
        return freeze_grid(raw)

    def render_frames(self, state: Mapping[str, Any]) -> tuple[Grid, ...]:
        if "render_frames" not in self.function_names:
            return (self.render(state),)
        raw = self.runtime.call("render_frames", deepcopy(dict(state)))
        return tuple(freeze_grid(frame) for frame in raw)

    def predict(
        self,
        state: Mapping[str, Any],
        action: Action,
        previous: Observation,
    ) -> RulePrediction:
        next_state = self.step_state(state, action)
        status = previous.status
        if "status" in self.function_names:
            status = GameStatus(str(self.runtime.call("status", deepcopy(next_state))))
        levels_completed = previous.levels_completed
        win_levels = previous.win_levels
        if "metrics" in self.function_names:
            metrics = _json_dict(
                self.runtime.call("metrics", deepcopy(next_state)),
                "metrics",
            )
            levels_completed = int(metrics.get("levels_completed", levels_completed))
            win_levels = int(metrics.get("win_levels", win_levels))
        available_actions = previous.available_actions
        if "available_actions" in self.function_names:
            raw_actions = self.runtime.call("available_actions", deepcopy(next_state))
            available_actions = tuple(ActionKind(int(action)) for action in raw_actions)
        full_reset = False
        if "full_reset" in self.function_names:
            full_reset = bool(self.runtime.call("full_reset", deepcopy(next_state)))
        observation = Observation(
            frames=self.render_frames(next_state),
            status=status,
            available_actions=available_actions,
            levels_completed=levels_completed,
            win_levels=win_levels,
            full_reset=full_reset,
            game_id=None,
            guid=None,
            metadata={"predicted_by": self.digest},
        )
        return RulePrediction(next_state, observation)

    def is_goal(self, state: Mapping[str, Any]) -> bool:
        if "is_goal" not in self.function_names:
            return False
        return bool(self.runtime.call("is_goal", deepcopy(dict(state))))

    def close(self) -> None:
        self.runtime.close()


def validate_generated_source(source: str, required_functions: set[str]) -> ast.Module:
    """Reject obvious side effects before executing generated code.

    Calls subsequently run in a restricted child process. The AST policy and worker are
    defense in depth, not a replacement for a hardened container against adversarial code.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        raise SourceValidationError(f"invalid Python: {error}") from error

    functions = {
        node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing = required_functions - functions
    if missing:
        raise SourceValidationError(f"missing required functions: {sorted(missing)}")

    for module_node in tree.body:
        if isinstance(module_node, ast.FunctionDef):
            continue
        if (
            isinstance(module_node, ast.Expr)
            and isinstance(module_node.value, ast.Constant)
            and isinstance(module_node.value.value, str)
        ):
            continue
        if isinstance(module_node, (ast.Assign, ast.AnnAssign)) and module_node.value is not None:
            try:
                ast.literal_eval(module_node.value)
            except (ValueError, TypeError):
                pass
            else:
                continue
        raise SourceValidationError(
            "module scope may contain only functions, docstrings, and literal constants"
        )

    for walked_node in ast.walk(tree):
        if isinstance(walked_node, _BANNED_NODES):
            raise SourceValidationError(f"{type(walked_node).__name__} is not allowed")
        if isinstance(walked_node, ast.Attribute) and walked_node.attr.startswith("__"):
            raise SourceValidationError("dunder attribute access is not allowed")
        if isinstance(walked_node, ast.Name) and walked_node.id.startswith("__"):
            raise SourceValidationError("dunder names are not allowed")
        if (
            isinstance(walked_node, ast.Call)
            and isinstance(walked_node.func, ast.Name)
            and walked_node.func.id in _BANNED_CALLS
        ):
            raise SourceValidationError(f"call to {walked_node.func.id} is not allowed")
    return tree


def _json_dict(value: Any, function_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{function_name} must return a dict")
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as error:
        raise TypeError(f"{function_name} returned non-JSON state: {error}") from error
    decoded = json.loads(encoded)
    if not isinstance(decoded, dict):
        raise TypeError(f"{function_name} must return a JSON object")
    return decoded
