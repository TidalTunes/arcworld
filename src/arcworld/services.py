"""Concrete services composed by the short high-level agent."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from arcworld.history import EpisodeHistory
from arcworld.hypotheses import HypothesisLedger
from arcworld.llm.workflows import LLMPythonPlanner, LLMWorldModelProposer
from arcworld.models.contract import RuleProgram
from arcworld.models.store import ModelRepository
from arcworld.perception.components import parse_scene, parse_scene_candidates
from arcworld.planning.dsl import Plan
from arcworld.planning.simulate import simulate_plan
from arcworld.probing import ShadowPrediction, rank_probes
from arcworld.revision import CandidateSpec, RevisionManager
from arcworld.types import Action, ActionKind, GameStatus, Observation


@dataclass(slots=True)
class InductiveRevisionService:
    manager: RevisionManager
    proposer: LLMWorldModelProposer
    candidate_count: int = 2
    record: Callable[[str, dict[str, Any]], None] | None = None

    def revise(
        self,
        history: EpisodeHistory,
        mismatch: Mapping[str, object] | None,
    ) -> RuleProgram:
        current = self.manager.repository.active()
        ontologies = tuple(
            graph.ontology for graph in parse_scene_candidates(history.latest.latest)
        ) or ("raw-pixels",)
        sources = []
        for index in range(self.candidate_count):
            ontology = ontologies[index % len(ontologies)]
            source = self.proposer.propose(
                history,
                current_source=current.source if current else None,
                mismatch=mismatch,
                preferred_ontology=ontology,
            )
            sources.append(
                CandidateSpec(
                    source,
                    ontology,
                    getattr(self.proposer.reasoner, "last_request_id", ""),
                    getattr(self.proposer.reasoner, "last_response_digest", ""),
                )
            )
        program, attempts = self.manager.reconcile(
            history,
            sources,
            author=self.proposer.reasoner.config.model,
            note="counterexample revision" if mismatch else "initial theory",
        )
        if self.record:
            for attempt in attempts:
                self.record(
                    "model_revision",
                    {
                        "model_digest": attempt.digest,
                        "hypothesis_id": attempt.hypothesis_id,
                        "ontology": attempt.ontology,
                        "source": self.manager.repository.load(attempt.model_digest).source,
                        "source_sha256": attempt.model_digest,
                        "origin_request_id": attempt.origin_request_id,
                        "origin_response_digest": attempt.origin_response_digest,
                        "promoted": attempt.promoted,
                        "verification": attempt.report.to_jsonable(),
                    },
                )
        return program


@dataclass(slots=True)
class LLMPlanningService:
    planner: LLMPythonPlanner
    record: Callable[[str, dict[str, Any]], None] | None = None

    def plan(
        self,
        program: RuleProgram,
        state: Mapping[str, object],
        observation: Observation,
        history: EpisodeHistory,
    ) -> Plan:
        scene = parse_scene(observation.latest)
        context = {
            "available_actions": [item.name for item in observation.available_actions],
            "scene": scene.to_jsonable(),
            "transition_count": len(history.transitions),
        }
        plan = self.planner.plan(
            program=program,
            state=state,
            observation=observation.to_jsonable(expose_identity=False),
            context=context,
        )
        if self.record:
            self.record(
                "plan_generated",
                {
                    "model_digest": program.digest,
                    "plan_digest": plan.source_digest,
                    "source": plan.source,
                    "source_sha256": plan.source_digest,
                    "origin_request_id": plan.origin_request_id,
                    "origin_response_digest": plan.origin_response_digest,
                    "actions": [action.to_jsonable() for action in plan.actions],
                    "build_plan_executed": True,
                },
            )
        rollout = simulate_plan(program, state, observation, plan)
        if self.record:
            self.record(
                "plan_simulated",
                {
                    "model_digest": program.digest,
                    "plan_digest": plan.source_digest,
                    "steps": len(rollout.steps),
                    "terminal": rollout.terminal,
                    "final_status": rollout.final_observation.status.value,
                    "complete_before_real_action": True,
                },
            )
        return plan


@dataclass(slots=True)
class BeliefAwarePlanningService:
    """Use a real action as a probe only when certified models disagree materially."""

    fallback: LLMPlanningService
    ledger: HypothesisLedger
    repository: ModelRepository
    minimum_entropy_bits: float = 0.2

    def plan(
        self,
        program: RuleProgram,
        state: Mapping[str, object],
        observation: Observation,
        history: EpisodeHistory,
    ) -> Plan:
        if observation.status is GameStatus.GAME_OVER:
            plan = Plan(
                (Action(ActionKind.RESET),),
                source_digest="game-over-recovery",
                rationale="RESET is the only legal recovery action",
            )
            simulate_plan(program, state, observation, plan)
            return plan
        weights = self.ledger.weights()
        if len(weights) < 2:
            return self.fallback.plan(program, state, observation, history)
        actions = _candidate_actions(observation)
        predictions: list[ShadowPrediction] = []
        for hypothesis_id, weight in weights.items():
            hypothesis = self.ledger.get(hypothesis_id)
            candidate = self.repository.load(hypothesis.model_digest)
            candidate_state = _replay_state(candidate, history)
            for action in actions:
                try:
                    predicted = candidate.predict(candidate_state, action, observation)
                except Exception:
                    predictions.append(
                        ShadowPrediction(
                            model_digest=hypothesis.model_digest,
                            action=action,
                            outcome_fingerprint="__prediction_error__",
                            weight=weight,
                            status=GameStatus.GAME_OVER,
                        )
                    )
                    continue
                predictions.append(
                    ShadowPrediction(
                        model_digest=hypothesis.model_digest,
                        action=action,
                        outcome_fingerprint=_fingerprint(predicted.observation),
                        weight=weight,
                        status=predicted.observation.status,
                    )
                )
        ranked = rank_probes(actions, predictions)
        if ranked and ranked[0].entropy_bits >= self.minimum_entropy_bits and ranked[0].score > 0:
            plan = Plan(
                (ranked[0].action,),
                source_digest="active-probe",
                rationale=(
                    f"discriminating experiment: {ranked[0].entropy_bits:.3f} bits, "
                    f"death risk {ranked[0].death_risk:.3f}"
                ),
            )
            simulate_plan(program, state, observation, plan)
            return plan
        return self.fallback.plan(program, state, observation, history)


def _candidate_actions(observation: Observation) -> tuple[Action, ...]:
    if observation.status is GameStatus.GAME_OVER:
        return (Action(ActionKind.RESET),)
    actions: list[Action] = []
    scene = parse_scene(observation.latest)
    for kind in observation.available_actions:
        if kind is ActionKind.RESET:
            continue
        if kind is ActionKind.ACTION6:
            centers = {(round(item.centroid[0]), round(item.centroid[1])) for item in scene.objects}
            if not centers:
                centers.add((len(observation.latest[0]) // 2, len(observation.latest) // 2))
            actions.extend(
                Action(ActionKind.ACTION6, x=max(0, min(63, x)), y=max(0, min(63, y)))
                for x, y in sorted(centers)[:32]
            )
        else:
            actions.append(Action(kind))
    return tuple(actions)


def _replay_state(program: RuleProgram, history: EpisodeHistory) -> dict[str, Any]:
    state = program.initial_state(history.initial)
    previous = history.initial
    for transition in history.transitions:
        prediction = program.predict(state, transition.action, previous)
        state = prediction.state
        previous = transition.after
    return state


def _fingerprint(observation: Observation) -> str:
    value = {
        "frame": observation.latest,
        "status": observation.status.value,
        "levels_completed": observation.levels_completed,
        "win_levels": observation.win_levels,
        "available_actions": [int(item) for item in observation.available_actions],
        "full_reset": observation.full_reset,
    }
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()
