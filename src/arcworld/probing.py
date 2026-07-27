"""Rank real actions by version-space information gain and irreversible risk."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from arcworld.types import Action, GameStatus


@dataclass(frozen=True, slots=True)
class ShadowPrediction:
    model_digest: str
    action: Action
    outcome_fingerprint: str
    weight: float
    status: GameStatus = GameStatus.NOT_FINISHED


@dataclass(frozen=True, slots=True)
class ProbeScore:
    action: Action
    entropy_bits: float
    death_risk: float
    action_cost: float
    score: float
    outcome_count: int


def rank_probes(
    actions: Iterable[Action],
    predictions: Iterable[ShadowPrediction],
    *,
    death_penalty: float = 2.0,
    reset_cost: float = 3.0,
    click_cost: float = 1.2,
) -> tuple[ProbeScore, ...]:
    by_action: dict[Action, list[ShadowPrediction]] = defaultdict(list)
    for prediction in predictions:
        by_action[prediction.action].append(prediction)
    results: list[ProbeScore] = []
    for action in actions:
        entries = by_action[action]
        if not entries:
            continue
        total = sum(max(0.0, item.weight) for item in entries)
        if total <= 0:
            continue
        outcomes: dict[str, float] = defaultdict(float)
        death_weight = 0.0
        for item in entries:
            weight = max(0.0, item.weight) / total
            outcomes[item.outcome_fingerprint] += weight
            if item.status is GameStatus.GAME_OVER:
                death_weight += weight
        entropy = -sum(probability * math.log2(probability) for probability in outcomes.values())
        cost = reset_cost if int(action.kind) == 0 else click_cost if int(action.kind) == 6 else 1.0
        score = entropy / cost - death_penalty * death_weight
        results.append(
            ProbeScore(
                action=action,
                entropy_bits=entropy,
                death_risk=death_weight,
                action_cost=cost,
                score=score,
                outcome_count=len(outcomes),
            )
        )
    return tuple(sorted(results, key=lambda item: (-item.score, str(item.action))))
