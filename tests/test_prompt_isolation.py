from __future__ import annotations

from arcworld.history import EpisodeHistory
from arcworld.llm.prompts import plan_input, world_model_input
from arcworld.types import ActionKind, Observation, freeze_grid


def test_model_context_redacts_environment_identity_and_metadata() -> None:
    observation = Observation(
        frames=(freeze_grid([[0, 1], [1, 0]]),),
        available_actions=(ActionKind.ACTION1,),
        game_id="secret-game-id",
        guid="secret-session-id",
        metadata={"environment_id": "secret-nested-id", "benchmark": "secret-suite"},
    )
    history = EpisodeHistory(observation)
    prompt = world_model_input(history)
    assert "secret-game-id" not in prompt
    assert "secret-session-id" not in prompt
    assert "secret-nested-id" not in prompt
    assert "secret-suite" not in prompt


def test_plan_context_redacts_nested_identity() -> None:
    text = plan_input(
        model_source="def placeholder(): pass",
        state={},
        observation={
            "frames": [[[0]]],
            "game_id": "secret",
            "metadata": {"guid": "also-secret"},
        },
        max_actions=3,
    )
    assert "secret" not in text
