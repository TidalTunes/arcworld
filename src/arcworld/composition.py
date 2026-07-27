"""Ready-to-run compositions; construction itself performs no network call."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from arcworld.agent import WorldModelAgent
from arcworld.env.base import Environment
from arcworld.hypotheses import HypothesisLedger
from arcworld.llm.base import Reasoner, RecordingReasoner
from arcworld.llm.openai_client import OpenAIResponsesReasoner, default_role_configs
from arcworld.llm.workflows import LLMPythonPlanner, LLMWorldModelProposer
from arcworld.models.store import ModelRepository
from arcworld.models.verifier import ReplayVerifier
from arcworld.planning.executor import VerifiedExecutor
from arcworld.revision import RevisionManager
from arcworld.services import (
    BeliefAwarePlanningService,
    InductiveRevisionService,
    LLMPlanningService,
)
from arcworld.storage import RunStore


@dataclass(frozen=True, slots=True)
class AgentBundle:
    agent: WorldModelAgent
    repository: ModelRepository
    ledger: HypothesisLedger
    run_id: str
    episode_workspace: Path


def build_openai_agent(
    environment: Environment,
    *,
    workspace: Path = Path(".arcworld"),
    label: str = "unknown-world",
    candidate_count: int = 2,
) -> AgentBundle:
    """Compose OpenAI development roles around a local/injected environment.

    This is unsuitable for Kaggle's internet-disabled rerun; inject a local
    ``CallableReasoner`` into the same services for competition packaging.
    """
    configs = default_role_configs()
    revision_reasoner = OpenAIResponsesReasoner(configs["revision"])
    planning_reasoner = OpenAIResponsesReasoner(configs["planning"])
    return build_agent(
        environment,
        revision_reasoner=revision_reasoner,
        planning_reasoner=planning_reasoner,
        workspace=workspace,
        label=label,
        candidate_count=candidate_count,
    )


def build_agent(
    environment: Environment,
    *,
    revision_reasoner: Reasoner,
    planning_reasoner: Reasoner,
    workspace: Path = Path(".arcworld"),
    label: str = "unknown-world",
    candidate_count: int = 2,
) -> AgentBundle:
    """Compose either hosted development roles or bundled local reasoners."""
    store = RunStore(workspace / "runs.db")
    run_id = store.create_run(
        label,
        {
            "revision_model": revision_reasoner.config.model,
            "revision_effort": revision_reasoner.config.effort,
            "planning_model": planning_reasoner.config.model,
            "planning_effort": planning_reasoner.config.effort,
            "candidate_count": candidate_count,
        },
    )
    episode_workspace = workspace / "episodes" / run_id
    repository = ModelRepository(episode_workspace / "models")

    def recorder(kind: str, payload: dict[str, Any]) -> None:
        store.append(run_id, kind, payload)

    recorded_revision_reasoner = RecordingReasoner(revision_reasoner, recorder)
    recorded_planning_reasoner = RecordingReasoner(planning_reasoner, recorder)
    ledger = HypothesisLedger()
    manager = RevisionManager(repository, ReplayVerifier(), ledger)
    revisions = InductiveRevisionService(
        manager,
        LLMWorldModelProposer(recorded_revision_reasoner),
        candidate_count=candidate_count,
        record=recorder,
    )
    fallback = LLMPlanningService(LLMPythonPlanner(recorded_planning_reasoner))
    planning = BeliefAwarePlanningService(fallback, ledger, repository)
    agent = WorldModelAgent(
        environment=environment,
        revisions=revisions,
        planner=planning,
        executor=VerifiedExecutor(),
        store=store,
        run_id=run_id,
    )
    return AgentBundle(agent, repository, ledger, run_id, episode_workspace)
