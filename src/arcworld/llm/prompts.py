"""Minimal prompts that reveal game evidence but no benchmark lore."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from arcworld.history import EpisodeHistory
from arcworld.perception.components import parse_scene_candidates
from arcworld.types import Observation

WORLD_MODEL_INSTRUCTIONS = """
You are identifying the rules of an unknown interactive grid world.
You receive only observations, available actions, your own action history, and a Python
contract. Do not assume action meanings. Maintain the simplest causal theory consistent
with every transition. Raw pixels are authoritative; object descriptions are fallible.

Return exactly one fenced Python block. It must define:
  initial_state(observation) -> JSON-serializable dict
  step(state, action) -> new JSON-serializable dict
  render(state) -> rectangular grid of integers 0..15
It should also define status(state), metrics(state), and is_goal(state) when evidence
supports them. Define available_actions(state) and full_reset(state) when those fields
can change. RESET has id 0 and is part of the dynamics; after GAME_OVER it is the only
legal recovery. Do not import modules, access files, use a network, or inspect runtime
internals. Never encode an unexplained transition by action index or history index.
""".strip()

PLAN_INSTRUCTIONS = """
Plan in the supplied world model before proposing any real action. Return exactly one
fenced Python block defining build_plan(api, context). It must return a list of Actions.
Use api.action("ACTION1") ... api.action("ACTION5"), api.click(x, y),
api.action("ACTION7"), api.reset(), api.repeat, and api.sequence. Prefer a short robust
plan. The executor will simulate it and will cancel the remaining actions at the first
real/simulated mismatch.

ACTION6 is coordinate-bearing and cannot be created with api.action("ACTION6"). Always
use api.click(x, y) for action 6. The planning context includes a structured scene with
object bounding boxes and centroids; use it to choose evidence-grounded click coordinates.
The returned action list must be non-empty. If ACTION6 is the only available action,
select a salient non-background object from planning_context["scene"]["objects"] and
click an integer coordinate inside its bounding box.
""".strip()


def world_model_input(
    history: EpisodeHistory,
    *,
    current_source: str | None = None,
    mismatch: Mapping[str, Any] | None = None,
    preferred_ontology: str | None = None,
) -> str:
    evidence = {
        "initial": _safe_observation(history.initial),
        "transitions": [
            _strip_identity(transition.to_jsonable(expose_identity=False))
            for transition in history.transitions
        ],
        "scene_candidates": [
            graph.to_jsonable() for graph in parse_scene_candidates(history.latest.latest)
        ],
        "current_model": current_source,
        "latest_mismatch": _strip_identity(dict(mismatch or {})),
        "preferred_scene_ontology": preferred_ontology,
    }
    return (
        "Revise the executable theory. A candidate is accepted only if it exactly replays "
        "all final frames and required metadata.\n\n"
        + json.dumps(evidence, separators=(",", ":"), sort_keys=True)
    )


def plan_input(
    *,
    model_source: str,
    state: Mapping[str, Any],
    observation: Mapping[str, Any],
    planning_context: Mapping[str, Any],
    max_actions: int,
) -> str:
    context = {
        "world_model": model_source,
        "simulator_state": _strip_identity(dict(state)),
        "observation": _strip_identity(dict(observation)),
        "planning_context": _strip_identity(dict(planning_context)),
        "maximum_plan_actions": max_actions,
    }
    return json.dumps(context, separators=(",", ":"), sort_keys=True)


def extract_python(text: str) -> str:
    blocks: list[str] = re.findall(
        r"```(?:python)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE
    )
    if len(blocks) != 1:
        raise ValueError(f"expected exactly one fenced Python block, received {len(blocks)}")
    return blocks[0].strip() + "\n"


def _safe_observation(observation: Observation) -> dict[str, Any]:
    return _strip_identity(observation.to_jsonable(expose_identity=False))


def _strip_identity(value: dict[str, Any]) -> dict[str, Any]:
    """Recursively remove evaluator-owned identity and opaque metadata."""
    result: dict[str, Any] = {}
    for key, item in value.items():
        if key.casefold() in {"game_id", "guid", "environment_id", "metadata"}:
            continue
        if isinstance(item, dict):
            result[key] = _strip_identity(item)
        elif isinstance(item, list):
            result[key] = [_strip_nested(element) for element in item]
        else:
            result[key] = item
    return result


def _strip_nested(value: Any) -> Any:
    if isinstance(value, dict):
        return _strip_identity(value)
    if isinstance(value, list):
        return [_strip_nested(item) for item in value]
    return value
