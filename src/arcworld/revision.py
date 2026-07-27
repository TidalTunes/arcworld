"""Stage, replay-test, retain, and atomically promote rule revisions."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from arcworld.history import EpisodeHistory
from arcworld.hypotheses import EvidenceLink, Hypothesis, HypothesisLedger
from arcworld.models.contract import RuleProgram
from arcworld.models.store import ModelRepository
from arcworld.models.verifier import ReplayVerifier, VerificationReport


@dataclass(frozen=True, slots=True)
class RevisionAttempt:
    hypothesis_id: str
    model_digest: str
    ontology: str
    report: VerificationReport
    promoted: bool
    origin_request_id: str = ""
    origin_response_digest: str = ""

    @property
    def digest(self) -> str:
        return self.model_digest


@dataclass(frozen=True, slots=True)
class CandidateSpec:
    source: str
    ontology: str
    origin_request_id: str = ""
    origin_response_digest: str = ""


@dataclass(slots=True)
class RevisionManager:
    repository: ModelRepository
    verifier: ReplayVerifier
    ledger: HypothesisLedger

    def reconcile(
        self,
        history: EpisodeHistory,
        sources: Iterable[str | CandidateSpec],
        *,
        author: str = "reasoner",
        note: str = "",
        ontology: str = "monochrome-components-4",
    ) -> tuple[RuleProgram, tuple[RevisionAttempt, ...]]:
        parent = self.repository.active_digest()
        prior_items = {
            item.id: item for item in self.ledger.candidates(replay_consistent_only=False)
        }
        hypotheses: dict[str, Hypothesis] = dict(prior_items)
        origins: dict[str, tuple[str, str]] = {}
        passing: list[tuple[Hypothesis, VerificationReport]] = []
        for item in sources:
            spec = item if isinstance(item, CandidateSpec) else CandidateSpec(item, ontology)
            revision = self.repository.stage(
                spec.source,
                parent=parent,
                author=author,
                note=note,
            )
            candidate = Hypothesis(
                revision.digest,
                spec.ontology,
                complexity=len(spec.source) / 10_000,
            )
            origins[candidate.id] = (
                spec.origin_request_id,
                spec.origin_response_digest,
            )
            hypotheses.setdefault(candidate.id, candidate)
        attempts: list[RevisionAttempt] = []
        for hypothesis_id, base_hypothesis in sorted(hypotheses.items()):
            program = self.repository.load(base_hypothesis.model_digest)
            report = self.verifier.verify(program, history)
            self.repository.record_verification(
                base_hypothesis.model_digest,
                report.to_jsonable(),
            )
            complexity = len(program.source) / 10_000
            prior = prior_items.get(hypothesis_id)
            hypothesis = prior or Hypothesis(
                base_hypothesis.model_digest,
                base_hypothesis.ontology,
                complexity=complexity,
            )
            hypothesis = hypothesis.with_evidence(
                EvidenceLink(
                    transition_index=len(history.transitions) - 1,
                    verdict="supports" if report.passed else "refutes",
                    note=f"replayed {report.checked}/{report.total}",
                ),
                consistent=report.passed,
            )
            if hypothesis_id in prior_items:
                self.ledger.update(hypothesis)
            else:
                self.ledger.add(hypothesis)
            if report.passed:
                passing.append((hypothesis, report))
            attempts.append(
                RevisionAttempt(
                    hypothesis.id,
                    hypothesis.model_digest,
                    hypothesis.ontology,
                    report,
                    False,
                    *origins.get(hypothesis.id, ("", "")),
                )
            )

        if not passing:
            self.repository.deactivate(reason="no revision passes the current evidence")
            raise RuntimeError("no candidate replayed the complete evidence history")
        winner, winning_report = min(
            passing,
            key=lambda item: (item[0].complexity, -item[0].log_weight, item[0].id),
        )
        self.repository.promote(
            winner.model_digest,
            evidence_digest=winning_report.evidence_digest,
        )
        self.ledger.commit(winner.id)
        attempts = [
            RevisionAttempt(
                item.hypothesis_id,
                item.model_digest,
                item.ontology,
                item.report,
                item.hypothesis_id == winner.id,
                item.origin_request_id,
                item.origin_response_digest,
            )
            for item in attempts
        ]
        return self.repository.load(winner.model_digest), tuple(attempts)
