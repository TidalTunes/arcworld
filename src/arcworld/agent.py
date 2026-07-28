"""The deliberately small batch facade over the phase-addressable controller."""

from __future__ import annotations

from dataclasses import dataclass

from arcworld.agent_contracts import AgentResult, PlanningService, RevisionService
from arcworld.env.base import Environment
from arcworld.interactive import InteractiveEpisode
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
        episode = InteractiveEpisode(self, action_budget=action_budget)
        while episode.can_advance:
            episode.advance()
        if episode.result is None:
            raise RuntimeError(episode.error or "episode ended without a result")
        return episode.result
