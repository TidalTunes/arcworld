from __future__ import annotations

from enum import Enum

import numpy as np
import pytest

from arcworld.types import Action, ActionKind, GameStatus, Observation, freeze_grid


def test_grid_and_action_validation() -> None:
    assert freeze_grid([[0, 1], [2, 3]]) == ((0, 1), (2, 3))
    with pytest.raises(ValueError):
        freeze_grid([[16]])
    with pytest.raises(ValueError):
        Action(ActionKind.ACTION6)
    with pytest.raises(ValueError):
        Action(ActionKind.ACTION1, x=1, y=2)
    assert Action.from_jsonable({"id": 6, "x": 9, "y": 4}).to_jsonable() == {
        "id": 6,
        "x": 9,
        "y": 4,
    }


def test_observation_round_trip_and_sdk_duck_type() -> None:
    observation = Observation(
        frames=(freeze_grid([[1, 2], [3, 4]]),),
        status=GameStatus.NOT_FINISHED,
        available_actions=(ActionKind.ACTION1, ActionKind.ACTION6),
        game_id="hidden-from-player",
    )
    assert Observation.from_jsonable(observation.to_jsonable()) == observation

    class SdkState(Enum):
        NOT_FINISHED = "NOT_FINISHED"

    class Raw:
        frame = [np.array([[0, 1], [2, 3]], dtype=np.int8)]
        state = SdkState.NOT_FINISHED
        available_actions = [1, 6]
        levels_completed = 0
        win_levels = 2
        full_reset = False
        game_id = "demo"
        guid = "session"

    converted = Observation.from_sdk(Raw())
    assert converted.latest == ((0, 1), (2, 3))
    assert converted.available_actions == (ActionKind.ACTION1, ActionKind.ACTION6)
    assert converted.guid == "session"
