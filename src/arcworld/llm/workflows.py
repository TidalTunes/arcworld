"""Turn reasoner text into validated candidate programs and plans."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from arcworld.history import EpisodeHistory
from arcworld.llm.base import Reasoner
from arcworld.llm.prompts import (
    PLAN_INSTRUCTIONS,
    WORLD_MODEL_INSTRUCTIONS,
    extract_python,
    plan_input,
    world_model_input,
)
from arcworld.models.contract import RuleProgram
from arcworld.planning.dsl import Plan, compile_plan


@dataclass(slots=True)
class LLMWorldModelProposer:
    reasoner: Reasoner

    def propose(
        self,
        history: EpisodeHistory,
        *,
        current_source: str | None = None,
        mismatch: Mapping[str, Any] | None = None,
        preferred_ontology: str | None = None,
    ) -> str:
        response = self.reasoner.complete(
            instructions=WORLD_MODEL_INSTRUCTIONS,
            input_text=world_model_input(
                history,
                current_source=current_source,
                mismatch=mismatch,
                preferred_ontology=preferred_ontology,
            ),
        )
        source = extract_python(response)
        RuleProgram.from_source(source)
        return source


@dataclass(slots=True)
class LLMPythonPlanner:
    reasoner: Reasoner
    max_actions: int = 128

    def plan(
        self,
        *,
        program: RuleProgram,
        state: Mapping[str, Any],
        observation: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> Plan:
        response = self.reasoner.complete(
            instructions=PLAN_INSTRUCTIONS,
            input_text=plan_input(
                model_source=program.source,
                state=state,
                observation=observation,
                max_actions=self.max_actions,
            ),
        )
        plan = compile_plan(
            extract_python(response),
            context,
            origin_request_id=getattr(self.reasoner, "last_request_id", ""),
            origin_response_digest=getattr(self.reasoner, "last_response_digest", ""),
        )
        if len(plan.actions) > self.max_actions:
            raise ValueError(
                f"generated plan has {len(plan.actions)} actions; limit is {self.max_actions}"
            )
        return plan
