"""A weighted shadow version-space around one committed model."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable
from dataclasses import dataclass, field, replace


@dataclass(frozen=True, slots=True)
class EvidenceLink:
    transition_index: int
    verdict: str
    note: str = ""


@dataclass(frozen=True, slots=True)
class Hypothesis:
    model_digest: str
    ontology: str
    log_weight: float = 0.0
    complexity: float = 0.0
    replay_consistent: bool = False
    evidence: tuple[EvidenceLink, ...] = ()
    known_guards: tuple[str, ...] = ()

    @property
    def id(self) -> str:
        payload = f"{self.model_digest}\0{self.ontology}".encode()
        return hashlib.sha256(payload).hexdigest()

    def with_evidence(self, link: EvidenceLink, *, consistent: bool) -> Hypothesis:
        likelihood = 0.0 if consistent else -20.0
        return replace(
            self,
            log_weight=self.log_weight + likelihood,
            replay_consistent=consistent,
            evidence=self.evidence + (link,),
        )


@dataclass(slots=True)
class HypothesisLedger:
    _items: dict[str, Hypothesis] = field(default_factory=dict)
    active_id: str | None = None

    def add(self, hypothesis: Hypothesis) -> None:
        if hypothesis.id in self._items:
            raise ValueError(f"duplicate hypothesis {hypothesis.id}")
        self._items[hypothesis.id] = hypothesis

    def update(self, hypothesis: Hypothesis) -> None:
        if hypothesis.id not in self._items:
            raise KeyError(hypothesis.id)
        self._items[hypothesis.id] = hypothesis

    def get(self, hypothesis_id: str) -> Hypothesis:
        return self._items[hypothesis_id]

    def candidates(self, *, replay_consistent_only: bool = True) -> tuple[Hypothesis, ...]:
        values: Iterable[Hypothesis] = self._items.values()
        if replay_consistent_only:
            values = (item for item in values if item.replay_consistent)
        return tuple(sorted(values, key=lambda item: (-item.log_weight, item.id)))

    def weights(self) -> dict[str, float]:
        candidates = self.candidates()
        if not candidates:
            return {}
        maximum = max(item.log_weight - item.complexity for item in candidates)
        unnormalized = {
            item.id: math.exp(item.log_weight - item.complexity - maximum) for item in candidates
        }
        total = sum(unnormalized.values())
        return {hypothesis_id: value / total for hypothesis_id, value in unnormalized.items()}

    def commit(self, hypothesis_id: str) -> None:
        hypothesis = self.get(hypothesis_id)
        if not hypothesis.replay_consistent:
            raise ValueError("only a replay-consistent hypothesis can be committed")
        self.active_id = hypothesis_id
