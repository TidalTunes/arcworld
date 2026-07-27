from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from arcworld.env.toy import TOY_MODEL_SOURCE, ToyKeyDoorEnvironment
from arcworld.history import EpisodeHistory
from arcworld.hypotheses import HypothesisLedger
from arcworld.models.contract import RuleProgram
from arcworld.models.store import ModelRepository
from arcworld.models.verifier import ReplayVerifier
from arcworld.planning.dsl import Plan
from arcworld.planning.simulate import simulate_plan
from arcworld.revision import RevisionManager
from arcworld.services import BeliefAwarePlanningService
from arcworld.types import Action, ActionKind, Observation


def _no_motion_source() -> str:
    return TOY_MODEL_SOURCE.replace(
        'if action["id"] not in directions or state["status"] != "NOT_FINISHED":',
        'if action["id"] == 4 or action["id"] not in directions '
        'or state["status"] != "NOT_FINISHED":',
    )


def test_revision_revalidates_every_shadow_on_new_evidence(tmp_path: Path) -> None:
    repository = ModelRepository(tmp_path / "models")
    ledger = HypothesisLedger()
    manager = RevisionManager(repository, ReplayVerifier(), ledger)
    environment = ToyKeyDoorEnvironment()
    history = EpisodeHistory(environment.reset())

    _, initial_attempts = manager.reconcile(history, [TOY_MODEL_SOURCE, _no_motion_source()])
    assert len(initial_attempts) == 2
    assert len(ledger.candidates()) == 2

    action = Action(ActionKind.ACTION4)
    history.append(action, environment.step(action))
    active, updated_attempts = manager.reconcile(history, [])
    assert active.digest == RuleProgram.from_source(TOY_MODEL_SOURCE).digest
    assert sum(attempt.report.passed for attempt in updated_attempts) == 1
    assert len(ledger.candidates()) == 1


@dataclass
class _Fallback:
    called: bool = False

    def plan(
        self,
        program: RuleProgram,
        state: Mapping[str, object],
        observation: Observation,
        history: EpisodeHistory,
    ) -> Plan:
        self.called = True
        return Plan((Action(ActionKind.ACTION1),))


def test_belief_planner_uses_disagreement_as_safe_probe(tmp_path: Path) -> None:
    repository = ModelRepository(tmp_path / "models")
    ledger = HypothesisLedger()
    manager = RevisionManager(repository, ReplayVerifier(), ledger)
    environment = ToyKeyDoorEnvironment()
    observation = environment.reset()
    history = EpisodeHistory(observation)
    active, _ = manager.reconcile(history, [TOY_MODEL_SOURCE, _no_motion_source()])
    fallback = _Fallback()
    service = BeliefAwarePlanningService(fallback, ledger, repository)  # type: ignore[arg-type]

    plan = service.plan(active, active.initial_state(observation), observation, history)

    assert plan.actions == (Action(ActionKind.ACTION4),)
    assert plan.source_digest == "active-probe"
    assert not fallback.called


def test_full_plan_is_simulated_before_execution() -> None:
    environment = ToyKeyDoorEnvironment()
    observation = environment.reset()
    program = RuleProgram.from_source(TOY_MODEL_SOURCE)
    plan = Plan(tuple(Action(ActionKind.ACTION4) for _ in range(7)))
    rollout = simulate_plan(program, program.initial_state(observation), observation, plan)
    assert len(rollout.steps) == 7
    assert rollout.terminal
