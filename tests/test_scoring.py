from __future__ import annotations

import math

import pytest

from arcworld.scoring import (
    benchmark_score,
    completion_cap,
    game_score,
    level_score,
    score_game,
)


def test_level_score_uses_squared_relative_human_action_efficiency() -> None:
    assert level_score(10, 10) == 1.0
    assert level_score(10, 20) == 0.25
    assert level_score(10, 100) == pytest.approx(0.01)
    assert level_score(10, 5) == 1.15


def test_speed_bonus_is_capped_at_115_percent() -> None:
    assert level_score(100, 1) == 1.15
    assert level_score(10, 9) == 1.15


def test_game_score_applies_weighted_completion_cap() -> None:
    assert completion_cap([True, True, False]) == 0.5
    # Weighted efficiency is 0.575, but only levels with weights 1 and 2
    # are complete, so the game cannot exceed (1 + 2) / (1 + 2 + 3).
    assert game_score([1.15, 1.15, 0.0]) == 0.5


def test_later_levels_receive_more_weight() -> None:
    early_level_only = game_score([1.0, 0.0])
    later_level_only = game_score([0.0, 1.0])
    assert early_level_only == pytest.approx(1 / 3)
    assert later_level_only == pytest.approx(2 / 3)
    assert later_level_only > early_level_only


def test_incomplete_levels_and_unplayed_games_score_zero() -> None:
    assert level_score(10, 1, completed=False) == 0.0
    assert game_score([]) == 0.0
    assert score_game([], [], []) == 0.0
    assert benchmark_score([], total_games=55) == 0.0


def test_total_games_includes_omitted_games_as_zero() -> None:
    assert benchmark_score([1.0, 0.5]) == 0.75
    assert benchmark_score([1.0, 0.5], total_games=4) == 0.375
    assert benchmark_score([1.0], total_games=55) == pytest.approx(1 / 55)


def test_exact_hand_computed_game_reference() -> None:
    # Scores are [1/4, 1, 0]. Their weighted efficiency is
    # (1 * 1/4 + 2 * 1 + 3 * 0) / 6 = 3/8. The completion cap is
    # (1 + 2) / 6 = 1/2, so the uncapped 3/8 is the final game score.
    assert (
        score_game(
            human_baseline_actions=[10, 8, 6],
            ai_actions=[20, 8, 3],
            completed=[True, True, False],
        )
        == 3 / 8
    )


def test_scoring_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        level_score(-1, 1)
    with pytest.raises(ValueError):
        level_score(1, math.inf)
    with pytest.raises(ValueError):
        level_score(1, math.nan)
    with pytest.raises(ValueError):
        game_score([-0.1])
    with pytest.raises(ValueError):
        game_score([1.16])
    with pytest.raises(ValueError):
        game_score([1.0], level_indices=[0])
    with pytest.raises(ValueError):
        score_game([1], [1, 2], [True])
    with pytest.raises(ValueError):
        benchmark_score([1.0, 0.5], total_games=1)
    with pytest.raises(ValueError):
        benchmark_score([1.01])
