from __future__ import annotations

import pytest

from arcworld.models.contract import RuleProgram, SourceValidationError
from arcworld.planning.dsl import compile_plan
from arcworld.sandbox import SandboxTimeout
from arcworld.types import Action, ActionKind, Observation, freeze_grid


def test_module_scope_execution_is_rejected() -> None:
    with pytest.raises(SourceValidationError):
        RuleProgram.from_source(
            """
while True:
    pass
def initial_state(observation): return {}
def step(state, action): return state
def render(state): return [[0]]
"""
        )


def test_world_model_call_is_killed_on_timeout() -> None:
    program = RuleProgram.from_source(
        """
def initial_state(observation):
    while True:
        pass
def step(state, action): return state
def render(state): return [[0]]
""",
        call_timeout_seconds=0.05,
    )
    observation = Observation(frames=(freeze_grid([[0]]),))
    with pytest.raises(SandboxTimeout):
        program.initial_state(observation)


def test_generated_globals_are_recreated_for_each_call() -> None:
    program = RuleProgram.from_source(
        """
COUNTER = {"value": 0}
def initial_state(observation): return {"value": 0}
def step(state, action):
    COUNTER["value"] += 1
    state["value"] = COUNTER["value"]
    return state
def render(state): return [[0]]
"""
    )
    action = Action(ActionKind.ACTION1)
    assert program.step_state({"value": 0}, action)["value"] == 1
    assert program.step_state({"value": 0}, action)["value"] == 1


def test_generated_code_can_use_safe_type_predicates() -> None:
    program = RuleProgram.from_source(
        """
def initial_state(observation):
    return {"is_mapping": isinstance(observation, dict)}
def step(state, action): return state
def render(state): return [[1 if state["is_mapping"] else 0]]
"""
    )
    observation = Observation(frames=(freeze_grid([[0]]),))
    assert program.initial_state(observation) == {"is_mapping": True}


def test_generated_plan_is_killed_on_timeout() -> None:
    with pytest.raises(SandboxTimeout):
        compile_plan(
            """
def build_plan(api, context):
    while True:
        pass
""",
            {},
            timeout_seconds=0.05,
        )
