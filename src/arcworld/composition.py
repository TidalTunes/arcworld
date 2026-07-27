"""Ready-to-run compositions; construction itself performs no network call."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from arcworld.agent import WorldModelAgent
from arcworld.env.base import Environment
from arcworld.hypotheses import HypothesisLedger
from arcworld.llm.base import Reasoner, ReasonerConfig, RecordingReasoner
from arcworld.llm.codex_cli import CodexCLIReasoner
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
    model: str | None = None,
    effort: str | None = None,
    workspace: Path = Path(".arcworld"),
    label: str = "unknown-world",
    candidate_count: int = 2,
    run_metadata: Mapping[str, Any] | None = None,
) -> AgentBundle:
    """Compose OpenAI development roles around a local/injected environment.

    This is unsuitable for Kaggle's internet-disabled rerun; inject a local
    ``CallableReasoner`` into the same services for competition packaging.
    """
    configs = default_role_configs()
    if model or effort:
        for role in ("revision", "planning"):
            current = configs[role]
            configs[role] = ReasonerConfig(
                model=model or current.model,
                effort=effort or current.effort,
                role=role,
            )
    revision_reasoner = OpenAIResponsesReasoner(configs["revision"])
    planning_reasoner = OpenAIResponsesReasoner(configs["planning"])
    return build_agent(
        environment,
        revision_reasoner=revision_reasoner,
        planning_reasoner=planning_reasoner,
        workspace=workspace,
        label=label,
        candidate_count=candidate_count,
        run_metadata=run_metadata,
    )


def build_codex_agent(
    environment: Environment,
    *,
    model: str = "gpt-5.6-luna",
    effort: str = "low",
    executable: Path | None = None,
    workspace: Path = Path(".arcworld"),
    label: str = "unknown-world",
    candidate_count: int = 1,
    run_metadata: Mapping[str, Any] | None = None,
) -> AgentBundle:
    """Compose isolated, authenticated OpenAI Codex CLI development roles."""

    revision_reasoner = CodexCLIReasoner(
        ReasonerConfig(model=model, effort=effort, role="revision"),
        executable=executable,
    )
    planning_reasoner = CodexCLIReasoner(
        ReasonerConfig(model=model, effort=effort, role="planning"),
        executable=executable,
    )
    return build_agent(
        environment,
        revision_reasoner=revision_reasoner,
        planning_reasoner=planning_reasoner,
        workspace=workspace,
        label=label,
        candidate_count=candidate_count,
        run_metadata=run_metadata,
    )


def build_agent(
    environment: Environment,
    *,
    revision_reasoner: Reasoner,
    planning_reasoner: Reasoner,
    workspace: Path = Path(".arcworld"),
    label: str = "unknown-world",
    candidate_count: int = 2,
    run_metadata: Mapping[str, Any] | None = None,
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
            "experiment": dict(run_metadata or {}),
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
    fallback = LLMPlanningService(LLMPythonPlanner(recorded_planning_reasoner), recorder)
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
