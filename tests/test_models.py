from __future__ import annotations

from pathlib import Path

import pytest

from arcworld.env.toy import TOY_MODEL_SOURCE, ToyKeyDoorEnvironment
from arcworld.history import EpisodeHistory
from arcworld.models.contract import RuleProgram, SourceValidationError
from arcworld.models.store import ModelRepository
from arcworld.models.verifier import ReplayVerifier
from arcworld.types import Action, ActionKind


def _toy_history(steps: int = 7) -> EpisodeHistory:
    environment = ToyKeyDoorEnvironment()
    history = EpisodeHistory(environment.reset())
    for _ in range(steps):
        action = Action(ActionKind.ACTION4)
        history.append(action, environment.step(action))
    return history


def test_generated_source_guard_and_contract() -> None:
    with pytest.raises(SourceValidationError):
        RuleProgram.from_source(
            """
def initial_state(observation): return {}
def step(state, action): return state
def render(state): return [[open("/tmp/bad")]]
"""
        )
    program = RuleProgram.from_source(TOY_MODEL_SOURCE)
    assert len(program.digest) == 64


def test_full_history_replay_accepts_correct_model() -> None:
    history = _toy_history()
    report = ReplayVerifier().verify(RuleProgram.from_source(TOY_MODEL_SOURCE), history)
    assert report.passed
    assert report.checked == 7


def test_replay_rejects_pixel_divergence() -> None:
    wrong = TOY_MODEL_SOURCE.replace('"grid"][y][x] = 0', '"grid"][y][x] = 1')
    report = ReplayVerifier().verify(RuleProgram.from_source(wrong), _toy_history(1))
    assert not report.passed
    assert report.steps[0].diff is not None
    assert not report.steps[0].diff.pixels.equal


def test_repository_requires_verification_for_promotion(tmp_path: Path) -> None:
    repository = ModelRepository(tmp_path / "models")
    revision = repository.stage(TOY_MODEL_SOURCE, author="test")
    duplicate = repository.stage(TOY_MODEL_SOURCE, author="test")
    assert revision.digest == duplicate.digest
    with pytest.raises(ValueError):
        repository.promote(revision.digest, evidence_digest="0" * 64)
    history = EpisodeHistory(ToyKeyDoorEnvironment().reset())
    report = ReplayVerifier().verify(repository.load(revision.digest), history)
    repository.record_verification(revision.digest, report.to_jsonable())
    repository.promote(revision.digest, evidence_digest=report.evidence_digest)
    assert repository.active_digest() == revision.digest
    assert repository.active() is not None

    environment = ToyKeyDoorEnvironment()
    changed_history = EpisodeHistory(environment.reset())
    action = Action(ActionKind.ACTION4)
    changed_history.append(action, environment.step(action))
    newer_report = ReplayVerifier().verify(repository.load(revision.digest), changed_history)
    with pytest.raises(ValueError):
        repository.promote(
            revision.digest,
            evidence_digest=newer_report.evidence_digest,
        )
