"""Dependency-free ARC-AGI-3 Relative Human Action Efficiency scoring.

The formulas mirror ``arc-agi`` v0.9.9. Public functions use normalized scores
in ``[0, 1]``; the official implementation performs the same arithmetic in
percent units.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from math import fsum, isfinite

LEVEL_SCORE_CAP = 1.15


def level_score(
    human_baseline_actions: int | float,
    ai_actions: int | float,
    *,
    completed: bool = True,
) -> float:
    """Return one level's normalized RHAE score.

    Incomplete levels and completed levels recorded with zero actions score
    zero, matching ``EnvironmentScoreCalculator.add_level`` in v0.9.9.
    """
    baseline = _nonnegative_finite(human_baseline_actions, "human_baseline_actions")
    actions = _nonnegative_finite(ai_actions, "ai_actions")
    if not completed or actions == 0:
        return 0.0
    return min((baseline / actions) ** 2, LEVEL_SCORE_CAP)


def completion_cap(
    completed: Sequence[bool],
    *,
    level_indices: Sequence[int] | None = None,
) -> float:
    """Return the weighted fraction of levels marked complete."""
    flags = tuple(completed)
    if not flags:
        return 0.0
    weights = _level_weights(len(flags), level_indices)
    return fsum(weight for weight, flag in zip(weights, flags, strict=True) if flag) / fsum(weights)


def game_score(
    level_scores: Sequence[int | float],
    *,
    level_indices: Sequence[int] | None = None,
) -> float:
    """Aggregate already-computed level scores exactly as v0.9.9 does.

    The completion cap follows the reference implementation and treats a level
    as complete when its score is positive. With valid positive human baselines
    this is equivalent to using the environment's completion flags.
    """
    scores = tuple(_level_score_value(value) for value in level_scores)
    if not scores:
        return 0.0

    weights = _level_weights(len(scores), level_indices)
    total_weight = fsum(weights)
    weighted_score = (
        fsum(weight * score for weight, score in zip(weights, scores, strict=True)) / total_weight
    )
    maximum_score = (
        fsum(weight for weight, score in zip(weights, scores, strict=True) if score > 0)
        / total_weight
    )
    return min(weighted_score, maximum_score)


def score_game(
    human_baseline_actions: Sequence[int | float],
    ai_actions: Sequence[int | float],
    completed: Sequence[bool],
    *,
    level_indices: Sequence[int] | None = None,
) -> float:
    """Compute a complete game score from aligned per-level observations."""
    baselines = tuple(human_baseline_actions)
    actions = tuple(ai_actions)
    flags = tuple(completed)
    if not (len(baselines) == len(actions) == len(flags)):
        raise ValueError("baseline, action, and completion sequences must have equal length")
    scores = tuple(
        level_score(baseline, action_count, completed=flag)
        for baseline, action_count, flag in zip(baselines, actions, flags, strict=True)
    )
    return game_score(scores, level_indices=level_indices)


def benchmark_score(
    game_scores: Iterable[int | float],
    *,
    total_games: int | None = None,
) -> float:
    """Return the arithmetic mean of game scores.

    Set ``total_games`` in competition mode to include omitted or unplayed games
    as zero. For example, passing 20 observed scores with ``total_games=55``
    divides their sum by 55.
    """
    scores = tuple(_game_score_value(value) for value in game_scores)
    denominator = len(scores) if total_games is None else total_games
    if denominator < 0:
        raise ValueError("total_games must be non-negative")
    if denominator < len(scores):
        raise ValueError("total_games cannot be smaller than the supplied game count")
    if denominator == 0:
        return 0.0
    return fsum(scores) / denominator


# Explicit RHAE names make call sites self-documenting while the shorter names
# track the terminology used in the official methodology.
rhae_level_score = level_score
rhae_game_score = game_score
rhae_score_game = score_game
rhae_benchmark_score = benchmark_score


def _level_weights(count: int, level_indices: Sequence[int] | None) -> tuple[float, ...]:
    if level_indices is None:
        return tuple(float(index) for index in range(1, count + 1))
    indices = tuple(level_indices)
    if len(indices) != count:
        raise ValueError("level_indices and level values must have equal length")
    invalid_index = any(
        isinstance(index, bool) or not isinstance(index, int) or index <= 0 for index in indices
    )
    if invalid_index:
        raise ValueError("level indices must be positive integers")
    return tuple(float(index) for index in indices)


def _nonnegative_finite(value: int | float, name: str) -> float:
    number = float(value)
    if not isfinite(number) or number < 0:
        raise ValueError(f"{name} must be a finite non-negative number")
    return number


def _level_score_value(value: int | float) -> float:
    score = _nonnegative_finite(value, "level score")
    if score > LEVEL_SCORE_CAP:
        raise ValueError(f"level score cannot exceed {LEVEL_SCORE_CAP}")
    return score


def _game_score_value(value: int | float) -> float:
    score = _nonnegative_finite(value, "game score")
    if score > 1:
        raise ValueError("game score cannot exceed 1")
    return score


__all__ = [
    "LEVEL_SCORE_CAP",
    "benchmark_score",
    "completion_cap",
    "game_score",
    "level_score",
    "rhae_benchmark_score",
    "rhae_game_score",
    "rhae_level_score",
    "rhae_score_game",
    "score_game",
]
