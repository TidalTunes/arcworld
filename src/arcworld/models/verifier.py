"""Replay-gate candidate programs against every observed transition."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from arcworld.history import EpisodeHistory
from arcworld.models.contract import RuleProgram
from arcworld.perception.diff import ObservationDiff, compare_observations


@dataclass(frozen=True, slots=True)
class VerificationPolicy:
    require_final_pixels: bool = True
    require_status: bool = True
    require_levels: bool = True
    require_available_actions: bool = True
    require_full_reset: bool = True
    require_animation_frames: bool = False
    stop_at_first_failure: bool = False


@dataclass(frozen=True, slots=True)
class VerificationStep:
    transition_index: int
    passed: bool
    diff: ObservationDiff | None
    error: str | None = None

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "transition_index": self.transition_index,
            "passed": self.passed,
            "diff": self.diff.to_jsonable() if self.diff else None,
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class VerificationReport:
    model_digest: str
    evidence_digest: str
    passed: bool
    checked: int
    total: int
    steps: tuple[VerificationStep, ...]

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "model_digest": self.model_digest,
            "evidence_digest": self.evidence_digest,
            "passed": self.passed,
            "checked": self.checked,
            "total": self.total,
            "steps": [step.to_jsonable() for step in self.steps],
        }


class ReplayVerifier:
    def __init__(self, policy: VerificationPolicy | None = None) -> None:
        self.policy = policy or VerificationPolicy()

    def verify(self, program: RuleProgram, history: EpisodeHistory) -> VerificationReport:
        evidence_digest = _evidence_digest(history)
        steps: list[VerificationStep] = []
        try:
            state = program.initial_state(history.initial)
        except Exception as error:  # generated model failures must become evidence
            step = VerificationStep(-1, False, None, f"{type(error).__name__}: {error}")
            return VerificationReport(
                model_digest=program.digest,
                evidence_digest=evidence_digest,
                passed=False,
                checked=0,
                total=len(history.transitions),
                steps=(step,),
            )

        previous = history.initial
        for transition in history.transitions:
            try:
                prediction = program.predict(state, transition.action, previous)
                diff = compare_observations(prediction.observation, transition.after)
                passed = self._passes(diff)
                steps.append(VerificationStep(transition.index, passed, diff))
                state = prediction.state
                previous = transition.after
            except Exception as error:
                steps.append(
                    VerificationStep(
                        transition.index,
                        False,
                        None,
                        f"{type(error).__name__}: {error}",
                    )
                )
            if not steps[-1].passed and self.policy.stop_at_first_failure:
                break

        return VerificationReport(
            model_digest=program.digest,
            evidence_digest=evidence_digest,
            passed=len(steps) == len(history.transitions) and all(step.passed for step in steps),
            checked=len(steps),
            total=len(history.transitions),
            steps=tuple(steps),
        )

    def _passes(self, diff: ObservationDiff) -> bool:
        checks = []
        if self.policy.require_final_pixels:
            checks.append(diff.pixels.equal)
        if self.policy.require_status:
            checks.append(diff.status_match)
        if self.policy.require_levels:
            checks.append(diff.level_match)
        if self.policy.require_available_actions:
            checks.append(diff.available_actions_match)
        if self.policy.require_full_reset:
            checks.append(diff.full_reset_match)
        if self.policy.require_animation_frames:
            checks.append(diff.animation_frames_match)
        return all(checks)


def _evidence_digest(history: EpisodeHistory) -> str:
    value = {
        "initial": history.initial.to_jsonable(),
        "transitions": [item.to_jsonable() for item in history.transitions],
    }
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()
