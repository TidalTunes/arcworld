from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from arcworld.composition import build_agent
from arcworld.env.toy import TOY_MODEL_SOURCE, ToyKeyDoorEnvironment
from arcworld.llm import CallableReasoner, ReasonerConfig
from arcworld.types import Action, ActionKind, GameStatus, Observation, freeze_grid


def _revision_response(_instructions: str, _input_text: str) -> str:
    return f"```python\n{TOY_MODEL_SOURCE}\n```"


def _plan_response(_instructions: str, _input_text: str) -> str:
    return """
```python
def build_plan(api, context):
    return api.repeat(api.action("ACTION4"), 7)
```
"""


def _reasoner(role: str, function: Callable[[str, str], str]) -> CallableReasoner:
    return CallableReasoner(
        ReasonerConfig(model=f"deterministic-{role}", effort="fixed", role=role),
        function,
    )


def test_complete_agent_loop_with_local_callable_reasoners(tmp_path: Path) -> None:
    class CountedToy(ToyKeyDoorEnvironment):
        reset_calls = 0

        def reset(self) -> Observation:
            self.reset_calls += 1
            return super().reset()

    environment = CountedToy()
    bundle = build_agent(
        environment,
        revision_reasoner=_reasoner("revision", _revision_response),
        planning_reasoner=_reasoner("planning", _plan_response),
        workspace=tmp_path / ".arcworld",
        label="sealed-synthetic",
        candidate_count=1,
    )

    result = bundle.agent.run(action_budget=20)

    assert result.status is GameStatus.WIN
    assert result.real_actions == 7
    assert result.revisions == 1
    assert environment.reset_calls == 0
    assert bundle.repository.active_digest() is not None
    assert bundle.episode_workspace.parent.name == "episodes"


def test_each_composition_gets_a_fresh_model_workspace(tmp_path: Path) -> None:
    revision = _reasoner("revision", _revision_response)
    planning = _reasoner("planning", _plan_response)
    first = build_agent(
        ToyKeyDoorEnvironment(),
        revision_reasoner=revision,
        planning_reasoner=planning,
        workspace=tmp_path / ".arcworld",
        label="first",
        candidate_count=1,
    )
    second = build_agent(
        ToyKeyDoorEnvironment(),
        revision_reasoner=revision,
        planning_reasoner=planning,
        workspace=tmp_path / ".arcworld",
        label="second",
        candidate_count=1,
    )
    assert first.run_id != second.run_id
    assert first.episode_workspace != second.episode_workspace
    assert first.repository.revisions() == ()
    assert second.repository.revisions() == ()


def test_agent_never_exceeds_real_action_budget(tmp_path: Path) -> None:
    bundle = build_agent(
        ToyKeyDoorEnvironment(),
        revision_reasoner=_reasoner("revision", _revision_response),
        planning_reasoner=_reasoner("planning", _plan_response),
        workspace=tmp_path / ".arcworld",
        candidate_count=1,
    )
    result = bundle.agent.run(action_budget=3)
    assert result.real_actions == 3
    assert result.reason == "action_budget"


_RECOVERY_MODEL = """
def initial_state(observation):
    return {
        "status": observation["status"],
        "cell": observation["frames"][-1][0][0],
        "full_reset": False,
    }
def step(state, action):
    state = deepcopy(state)
    state["full_reset"] = False
    if action["id"] == 0:
        state["status"] = "NOT_FINISHED"
        state["cell"] = 0
        state["full_reset"] = True
    elif action["id"] == 1 and state["status"] == "NOT_FINISHED":
        state["status"] = "WIN"
        state["cell"] = 1
    return state
def render(state): return [[state["cell"]]]
def status(state): return state["status"]
def metrics(state): return {"levels_completed": 0, "win_levels": 0}
def available_actions(state):
    if state["status"] == "GAME_OVER": return []
    return [1]
def full_reset(state): return state["full_reset"]
def is_goal(state): return state["status"] == "WIN"
"""


class _RecoveryEnvironment:
    def __init__(self) -> None:
        self.status = GameStatus.GAME_OVER

    def start(self) -> Observation:
        return self._observation()

    def reset(self) -> Observation:
        self.status = GameStatus.NOT_FINISHED
        return self._observation(full_reset=True)

    def step(self, action: Action) -> Observation:
        if action.kind is ActionKind.RESET:
            return self.reset()
        if action.kind is ActionKind.ACTION1 and self.status is GameStatus.NOT_FINISHED:
            self.status = GameStatus.WIN
        return self._observation()

    def _observation(self, *, full_reset: bool = False) -> Observation:
        if self.status is GameStatus.GAME_OVER:
            cell = 8
        elif self.status is GameStatus.WIN:
            cell = 1
        else:
            cell = 0
        actions = () if self.status is GameStatus.GAME_OVER else (ActionKind.ACTION1,)
        return Observation(
            frames=(freeze_grid([[cell]]),),
            status=self.status,
            available_actions=actions,
            full_reset=full_reset,
        )


def test_game_over_routes_through_reset_and_continues(tmp_path: Path) -> None:
    revision = _reasoner(
        "revision",
        lambda _instructions, _input: f"```python\n{_RECOVERY_MODEL}\n```",
    )
    planning = _reasoner(
        "planning",
        lambda _instructions, _input: (
            '```python\ndef build_plan(api, context):\n    return [api.action("ACTION1")]\n```'
        ),
    )
    bundle = build_agent(
        _RecoveryEnvironment(),
        revision_reasoner=revision,
        planning_reasoner=planning,
        workspace=tmp_path / ".arcworld",
        candidate_count=1,
    )
    result = bundle.agent.run(action_budget=5)
    assert result.status is GameStatus.WIN
    assert result.real_actions == 2
