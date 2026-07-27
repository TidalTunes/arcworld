"""Provider-neutral text reasoner interface."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections.abc import Callable
from collections.abc import Mapping as MappingABC
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class ReasonerConfig:
    model: str
    effort: str
    role: str


class Reasoner(Protocol):
    @property
    def config(self) -> ReasonerConfig: ...

    def complete(self, *, instructions: str, input_text: str) -> str: ...


@dataclass(slots=True)
class CallableReasoner:
    """Attach an in-process local model without adding a service dependency."""

    config: ReasonerConfig
    function: Callable[[str, str], str]

    def complete(self, *, instructions: str, input_text: str) -> str:
        return self.function(instructions, input_text)


@dataclass(slots=True)
class RecordingReasoner:
    """Fail-closed request/response provenance around any reasoner."""

    inner: Reasoner
    record: Callable[[str, dict[str, Any]], None]
    last_request_id: str = ""
    last_response_digest: str = ""

    @property
    def config(self) -> ReasonerConfig:
        return self.inner.config

    def complete(self, *, instructions: str, input_text: str) -> str:
        request_id = uuid.uuid4().hex
        self.last_request_id = request_id
        self.last_response_digest = ""
        request = {
            "request_id": request_id,
            "model": self.config.model,
            "effort": self.config.effort,
            "role": self.config.role,
            "instructions": instructions,
            "input": input_text,
            "instructions_digest": _digest(instructions),
            "input_digest": _digest(input_text),
            "config_digest": _digest(
                json.dumps(
                    {
                        "model": self.config.model,
                        "effort": self.config.effort,
                        "role": self.config.role,
                    },
                    sort_keys=True,
                )
            ),
        }
        self.record("reasoner_request", request)
        started = time.perf_counter()
        try:
            response = self.inner.complete(instructions=instructions, input_text=input_text)
        except Exception as error:
            self.record(
                "reasoner_error",
                {
                    "request_id": request_id,
                    "input_digest": request["input_digest"],
                    "model": self.config.model,
                    "role": self.config.role,
                    "error_type": type(error).__name__,
                    "error": str(error),
                    "duration_seconds": time.perf_counter() - started,
                },
            )
            raise
        self.record(
            "reasoner_response",
            {
                "request_id": request_id,
                "input_digest": request["input_digest"],
                "model": self.config.model,
                "role": self.config.role,
                "response": response,
                "response_digest": _digest(response),
                "provider_metadata": _provider_metadata(self.inner),
                "duration_seconds": time.perf_counter() - started,
            },
        )
        self.last_response_digest = _digest(response)
        return response


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _provider_metadata(reasoner: Reasoner) -> dict[str, Any]:
    value = getattr(reasoner, "last_completion_metadata", {})
    if not isinstance(value, MappingABC):
        return {}
    return dict(value)
