from __future__ import annotations

from arcworld.env.toy import TOY_MODEL_SOURCE, ToyKeyDoorEnvironment
from arcworld.models.contract import RuleProgram
from arcworld.planning.dsl import Plan, compile_plan
from arcworld.planning.executor import VerifiedExecutor
from arcworld.planning.search import breadth_first_search
from arcworld.types import Action, ActionKind


def test_python_plan_dsl_supports_structured_series() -> None:
    plan = compile_plan(
        """
def build_plan(api, context):
    moves = api.repeat(api.action("ACTION4"), context["count"])
    return api.sequence(moves, api.action("ACTION5"))
""",
        {"count": 3},
    )
    assert [action.kind for action in plan.actions] == [
        ActionKind.ACTION4,
        ActionKind.ACTION4,
        ActionKind.ACTION4,
        ActionKind.ACTION5,
    ]


def test_bfs_plans_many_moves_in_simulator() -> None:
    environment = ToyKeyDoorEnvironment()
    observation = environment.reset()
    program = RuleProgram.from_source(TOY_MODEL_SOURCE)
    result = breadth_first_search(
        program,
        program.initial_state(observation),
        (Action(ActionKind.ACTION4),),
        max_depth=10,
    )
    assert result.found
    assert len(result.actions) == 7


def test_executor_completes_matching_plan() -> None:
    environment = ToyKeyDoorEnvironment()
    observation = environment.reset()
    program = RuleProgram.from_source(TOY_MODEL_SOURCE)
    plan = Plan(tuple(Action(ActionKind.ACTION4) for _ in range(7)))
    result = VerifiedExecutor().execute(
        plan,
        environment=environment,
        program=program,
        model_state=program.initial_state(observation),
        observation=observation,
    )
    assert not result.diverged
    assert result.terminal
    assert len(result.steps) == 7


def test_executor_cancels_remaining_plan_on_first_surprise() -> None:
    environment = ToyKeyDoorEnvironment()
    observation = environment.reset()
    wrong_source = TOY_MODEL_SOURCE.replace('"grid"][y][x] = 0', '"grid"][y][x] = 1')
    program = RuleProgram.from_source(wrong_source)
    plan = Plan(tuple(Action(ActionKind.ACTION4) for _ in range(4)))
    result = VerifiedExecutor().execute(
        plan,
        environment=environment,
        program=program,
        model_state=program.initial_state(observation),
        observation=observation,
    )
    assert result.diverged
    assert len(result.steps) == 1
    assert len(result.remaining) == 3
