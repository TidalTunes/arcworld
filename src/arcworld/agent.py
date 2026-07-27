"""High-level composition of learning, planning, and verified execution."""

from __future__ import annotations

from dataclasses import dataclass

from arcworld.agent_contracts import AgentResult, PlanningService, RevisionService, replay_state
from arcworld.agent_journal import AgentJournal
from arcworld.env.base import Environment
from arcworld.history import EpisodeHistory
from arcworld.planning.dsl import Plan
from arcworld.planning.executor import VerifiedExecutor
from arcworld.storage import RunStore


@dataclass(slots=True)
class WorldModelAgent:
    environment: Environment
    revisions: RevisionService
    planner: PlanningService
    executor: VerifiedExecutor
    store: RunStore | None = None
    run_id: str | None = None

    def run(self, *, action_budget: int = 500) -> AgentResult:
        observation = self.environment.start()
        history = EpisodeHistory(observation)
        journal = AgentJournal(history, self.store, self.run_id)
        journal.initial(observation)
        program = self.revisions.revise(history, None)
        state = program.initial_state(observation)
        revision_count = 1

        while len(history.transitions) < action_budget:
            plan = self.planner.plan(program, state, observation, history)
            remaining_budget = action_budget - len(history.transitions)
            if len(plan.actions) > remaining_budget:
                plan = Plan(
                    plan.actions[:remaining_budget],
                    source_digest=plan.source_digest,
                    rationale=f"{plan.rationale}; clipped to real-action budget",
                )
            execution_journal = journal.execution(program.digest, plan.source_digest)

            outcome = self.executor.execute(
                plan,
                environment=self.environment,
                program=program,
                model_state=state,
                observation=observation,
                on_intent=execution_journal.intent,
                on_raw_step=execution_journal.raw,
                on_step=execution_journal.analysis,
                max_actions=remaining_budget,
            )
            observation = outcome.final_observation
            if outcome.terminal:
                return AgentResult(
                    history,
                    observation.status,
                    len(history.transitions),
                    revision_count,
                    "terminal",
                )
            if outcome.diverged:
                latest_diff = outcome.steps[-1].diff.to_jsonable()
                program = self.revisions.revise(history, latest_diff)
                state = replay_state(program, history)
                revision_count += 1
            else:
                state = dict(outcome.final_state)

        return AgentResult(
            history,
            observation.status,
            len(history.transitions),
            revision_count,
            "action_budget",
        )
