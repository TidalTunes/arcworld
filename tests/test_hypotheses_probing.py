from __future__ import annotations

import math

import pytest

from arcworld.hypotheses import Hypothesis, HypothesisLedger
from arcworld.probing import ShadowPrediction, rank_probes
from arcworld.types import Action, ActionKind, GameStatus


def test_ledger_normalizes_only_consistent_hypotheses() -> None:
    ledger = HypothesisLedger()
    first = Hypothesis("a" * 64, "objects", log_weight=0.0, replay_consistent=True)
    second = Hypothesis("b" * 64, "pixels", log_weight=-1.0, replay_consistent=True)
    bad = Hypothesis("c" * 64, "bad", log_weight=5.0, replay_consistent=False)
    ledger.add(first)
    ledger.add(second)
    ledger.add(bad)
    weights = ledger.weights()
    assert set(weights) == {first.id, second.id}
    assert math.isclose(sum(weights.values()), 1.0)
    with pytest.raises(ValueError):
        ledger.commit(bad.id)


def test_probe_prefers_safe_disagreement() -> None:
    safe = Action(ActionKind.ACTION1)
    risky = Action(ActionKind.ACTION2)
    predictions = [
        ShadowPrediction("a", safe, "left", 0.5),
        ShadowPrediction("b", safe, "right", 0.5),
        ShadowPrediction("a", risky, "win", 0.5),
        ShadowPrediction("b", risky, "death", 0.5, GameStatus.GAME_OVER),
    ]
    scores = rank_probes((safe, risky), predictions)
    assert scores[0].action == safe
    assert scores[0].entropy_bits == 1.0
    assert scores[1].death_risk == 0.5


def test_same_dynamics_can_coexist_under_competing_ontologies() -> None:
    ledger = HypothesisLedger()
    components = Hypothesis("a" * 64, "components-4", replay_consistent=True)
    grouped = Hypothesis("a" * 64, "multicolor-groups", replay_consistent=True)
    ledger.add(components)
    ledger.add(grouped)
    assert components.id != grouped.id
    assert len(ledger.weights()) == 2
