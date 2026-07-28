from __future__ import annotations

import socket
from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from arcworld.env.arc_adapter import (
    ActionUnavailableError,
    ArcAdapter,
    EmptyObservationError,
)
from arcworld.types import Action, ActionKind, GameStatus, freeze_grid


@dataclass(slots=True)
class RawObservation:
    """Dependency-free stand-in for an SDK FrameDataRaw object."""

    frame: list[list[list[int]]]
    state: str = "NOT_FINISHED"
    available_actions: list[int] = field(default_factory=list)
    levels_completed: int = 0
    win_levels: int = 0
    full_reset: bool = False
    game_id: str = "fake-00000000"
    guid: str = "fake-guid"


@dataclass(frozen=True, slots=True)
class StepCall:
    action: object
    data: dict[str, int] | None
    reasoning: dict[str, Any] | None


class FakeWrapper:
    """Deterministic wrapper with the exact surface consumed by ArcAdapter."""

    def __init__(
        self,
        initial: RawObservation | None,
        *,
        steps: tuple[RawObservation | None, ...] = (),
        reset_result: RawObservation | None = None,
    ) -> None:
        self.observation_space = initial
        self._steps = list(steps)
        self._reset_result = reset_result
        self.step_calls: list[StepCall] = []
        self.reset_calls = 0

    def reset(self) -> RawObservation | None:
        self.reset_calls += 1
        self.observation_space = self._reset_result
        return self._reset_result

    def step(
        self,
        action: object,
        data: dict[str, int] | None = None,
        reasoning: dict[str, Any] | None = None,
    ) -> RawObservation | None:
        self.step_calls.append(StepCall(action, data, reasoning))
        if not self._steps:
            raise AssertionError("unexpected fake environment step")
        result = self._steps.pop(0)
        if result is not None:
            self.observation_space = result
        return result


def _grid(value: int) -> list[list[int]]:
    return [[value, 0], [0, value]]


def _raw(
    *frame_values: int,
    actions: tuple[int, ...] = (),
    state: str = "NOT_FINISHED",
    levels_completed: int = 0,
    win_levels: int = 0,
    full_reset: bool = False,
) -> RawObservation:
    return RawObservation(
        frame=[_grid(value) for value in frame_values],
        state=state,
        available_actions=list(actions),
        levels_completed=levels_completed,
        win_levels=win_levels,
        full_reset=full_reset,
    )


def _name_encoder(action: Action) -> str:
    return f"encoded:{action}"


def test_initial_observation_and_all_animation_frames_are_retained() -> None:
    initial = _raw(
        1,
        actions=(1, 6),
        levels_completed=2,
        win_levels=7,
    )
    animated = _raw(2, 3, 4, actions=(2,), levels_completed=3, win_levels=7)
    wrapper = FakeWrapper(initial, steps=(animated,))
    environment = ArcAdapter(wrapper, action_encoder=_name_encoder)

    observation = environment.observation
    assert observation.frames == (freeze_grid(_grid(1)),)
    assert observation.status is GameStatus.NOT_FINISHED
    assert observation.available_actions == (
        ActionKind.ACTION1,
        ActionKind.ACTION6,
    )
    assert observation.levels_completed == 2
    assert observation.win_levels == 7
    assert observation.game_id == "fake-00000000"
    assert observation.guid == "fake-guid"

    after = environment.step(Action(ActionKind.ACTION1))
    assert after.frames == tuple(freeze_grid(_grid(value)) for value in (2, 3, 4))
    assert after.latest == freeze_grid(_grid(4))
    assert after.levels_completed == 3


def test_available_actions_are_enforced_from_each_current_observation() -> None:
    wrapper = FakeWrapper(
        _raw(1, actions=(1,)),
        steps=(
            _raw(2, actions=(2,)),
            _raw(3, actions=(3,)),
        ),
    )
    encoded: list[Action] = []

    def encode(action: Action) -> str:
        encoded.append(action)
        return action.kind.name

    environment = ArcAdapter(wrapper, action_encoder=encode)
    environment.step(Action(ActionKind.ACTION1))
    assert environment.available_actions == (ActionKind.ACTION2,)

    with pytest.raises(ActionUnavailableError, match="ACTION1 is not advertised"):
        environment.step(Action(ActionKind.ACTION1))

    assert len(wrapper.step_calls) == 1
    assert encoded == [Action(ActionKind.ACTION1)]

    environment.step(Action(ActionKind.ACTION2))
    assert len(wrapper.step_calls) == 2
    assert environment.available_actions == (ActionKind.ACTION3,)


def test_action6_uses_injected_encoder_and_coordinate_payload() -> None:
    wrapper = FakeWrapper(
        _raw(1, actions=(6,)),
        steps=(_raw(2, actions=(6,)),),
    )
    encoded_actions: list[Action] = []
    sentinel = object()

    def encode(action: Action) -> object:
        encoded_actions.append(action)
        return sentinel

    environment = ArcAdapter(wrapper, action_encoder=encode)
    click = Action(ActionKind.ACTION6, x=17, y=41)
    environment.step(click, reasoning={"purpose": "disambiguating probe"})

    assert encoded_actions == [click]
    assert wrapper.step_calls == [
        StepCall(
            sentinel,
            {"x": 17, "y": 41},
            {"purpose": "disambiguating probe"},
        )
    ]


def test_reset_method_and_reset_action_are_supported() -> None:
    reset_frame = _raw(
        5,
        actions=(4,),
        state="NOT_FINISHED",
        levels_completed=0,
        full_reset=True,
    )
    wrapper = FakeWrapper(
        _raw(1, actions=()),
        steps=(_raw(6, actions=(4,), full_reset=False),),
        reset_result=reset_frame,
    )
    environment = ArcAdapter(wrapper, action_encoder=_name_encoder)

    assert environment.accepts(Action(ActionKind.RESET))
    reset_observation = environment.reset()
    assert wrapper.reset_calls == 1
    assert reset_observation.full_reset
    assert reset_observation.latest == freeze_grid(_grid(5))

    # RESET is an engine control action and need not appear in available_actions.
    after_step_reset = environment.step(Action(ActionKind.RESET))
    assert after_step_reset.latest == freeze_grid(_grid(6))
    assert wrapper.step_calls == [StepCall("encoded:RESET", {}, {})]


def test_empty_initial_reset_and_step_responses_raise_clear_errors() -> None:
    missing_initial = ArcAdapter(FakeWrapper(None), action_encoder=_name_encoder)
    with pytest.raises(EmptyObservationError, match="no current observation"):
        _ = missing_initial.observation

    missing_reset = ArcAdapter(
        FakeWrapper(_raw(1), reset_result=None),
        action_encoder=_name_encoder,
    )
    with pytest.raises(EmptyObservationError, match="after reset"):
        missing_reset.reset()

    missing_step = ArcAdapter(
        FakeWrapper(_raw(1, actions=(1,)), steps=(None,)),
        action_encoder=_name_encoder,
    )
    with pytest.raises(EmptyObservationError, match="after ACTION1"):
        missing_step.step(Action(ActionKind.ACTION1))


def test_injected_wrapper_path_imports_no_sdk_and_opens_no_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def guarded_import(name: str) -> Any:
        if name in {"arc_agi", "arcengine"}:
            raise AssertionError(f"optional SDK import attempted: {name}")
        return import_module(name)

    def forbidden_network(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"network attempted with {args!r} {kwargs!r}")

    monkeypatch.setattr("arcworld.env.arc_adapter.import_module", guarded_import)
    monkeypatch.setattr(socket, "create_connection", forbidden_network)

    wrapper = FakeWrapper(
        _raw(1, actions=(1,)),
        steps=(_raw(2, actions=(2,)),),
        reset_result=_raw(3, actions=(1,), full_reset=True),
    )
    environment = ArcAdapter(wrapper, action_encoder=_name_encoder)

    assert environment.observation.latest == freeze_grid(_grid(1))
    assert environment.step(Action(ActionKind.ACTION1)).latest == freeze_grid(_grid(2))
    assert environment.reset().latest == freeze_grid(_grid(3))


def test_offline_factory_passes_absolute_roots_that_cannot_be_env_overridden(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    environments = tmp_path / "environment_files"
    recordings = tmp_path / "recordings"
    environments.mkdir()

    class FakeArcade:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)
            self.operation_mode = SimpleNamespace(value="offline")

        def make(self, game_id: str, **kwargs: object) -> FakeWrapper:
            captured["game_id"] = game_id
            captured["make"] = kwargs
            return FakeWrapper(_raw(1, actions=(1,)))

    fake_sdk = SimpleNamespace(
        Arcade=FakeArcade,
        OperationMode=SimpleNamespace(OFFLINE="offline"),
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENVIRONMENTS_DIR", str(tmp_path / "wrong-cache"))
    monkeypatch.setattr(
        "arcworld.env.arc_adapter.import_module",
        lambda name: fake_sdk if name == "arc_agi" else import_module(name),
    )

    ArcAdapter.open_offline(
        "ab12-1234abcd",
        environments_dir=Path("environment_files"),
        recordings_dir=Path("recordings"),
    )

    assert captured["environments_dir"] == str(environments.resolve())
    assert captured["recordings_dir"] == str(recordings.resolve())
