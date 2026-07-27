"""OpenAI Responses API adapter with role-specific, configurable models."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from arcworld.llm.base import ReasonerConfig


def default_role_configs() -> dict[str, ReasonerConfig]:
    """Defaults reflect current verified reasoning results, not a hard dependency."""
    return {
        "revision": ReasonerConfig(
            model=os.getenv("ARCWORLD_REASONER_MODEL", "gpt-5.6-sol"),
            effort=os.getenv("ARCWORLD_REASONER_EFFORT", "high"),
            role="revision",
        ),
        "planning": ReasonerConfig(
            model=os.getenv("ARCWORLD_REASONER_MODEL", "gpt-5.6-sol"),
            effort=os.getenv("ARCWORLD_REASONER_EFFORT", "high"),
            role="planning",
        ),
        "utility": ReasonerConfig(
            model=os.getenv("ARCWORLD_UTILITY_MODEL", "gpt-5.6-luna"),
            effort=os.getenv("ARCWORLD_UTILITY_EFFORT", "low"),
            role="utility",
        ),
    }


@dataclass(slots=True)
class OpenAIResponsesReasoner:
    config: ReasonerConfig
    client: Any = None

    def complete(self, *, instructions: str, input_text: str) -> str:
        client = self.client
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as error:
                raise RuntimeError("install ARCWorld with the 'openai' extra") from error
            client = OpenAI()
            self.client = client
        response = client.responses.create(
            model=self.config.model,
            reasoning={"effort": self.config.effort},
            instructions=instructions,
            input=input_text,
        )
        return str(response.output_text)
