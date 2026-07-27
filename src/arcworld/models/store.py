"""Content-addressed, append-only model revisions with atomic promotion."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from arcworld.models.contract import RuleProgram


@dataclass(frozen=True, slots=True)
class ModelRevision:
    digest: str
    source_path: Path
    created_at: str
    parent: str | None
    author: str
    note: str

    def to_jsonable(self) -> dict[str, Any]:
        value = asdict(self)
        value["source_path"] = str(self.source_path)
        return value


class ModelRepository:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.revisions_dir = root / "revisions"
        self.active_path = root / "active.json"
        self.revisions_dir.mkdir(parents=True, exist_ok=True)

    def stage(
        self,
        source: str,
        *,
        parent: str | None = None,
        author: str = "unknown",
        note: str = "",
    ) -> ModelRevision:
        program = RuleProgram.from_source(source)
        directory = self.revisions_dir / program.digest
        directory.mkdir(parents=True, exist_ok=True)
        source_path = directory / "world_model.py"
        manifest_path = directory / "manifest.json"
        created_at = datetime.now(UTC).isoformat()
        revision = ModelRevision(
            digest=program.digest,
            source_path=source_path,
            created_at=created_at,
            parent=parent,
            author=author,
            note=note,
        )
        if not source_path.exists():
            source_path.write_text(program.source, encoding="utf-8")
            _atomic_json(manifest_path, revision.to_jsonable())
        return revision

    def record_verification(self, digest: str, report: dict[str, Any]) -> None:
        directory = self._revision_dir(digest)
        evidence_digest = str(report.get("evidence_digest", ""))
        if len(evidence_digest) != 64:
            raise ValueError("verification report requires an evidence digest")
        _atomic_json(
            directory / "verifications" / f"{evidence_digest}.json",
            report,
        )
        _atomic_json(directory / "verification.json", report)

    def promote(self, digest: str, *, evidence_digest: str) -> None:
        directory = self._revision_dir(digest)
        verification_path = directory / "verification.json"
        if not verification_path.exists():
            raise ValueError("a model cannot be promoted without a recorded verification")
        verification = json.loads(verification_path.read_text(encoding="utf-8"))
        if (
            verification.get("model_digest") != digest
            or verification.get("evidence_digest") != evidence_digest
            or verification.get("passed") is not True
        ):
            raise ValueError(
                "promotion requires the matching successful complete-history verification"
            )
        _atomic_json(
            self.active_path,
            {
                "digest": digest,
                "evidence_digest": evidence_digest,
                "promoted_at": datetime.now(UTC).isoformat(),
            },
        )

    def deactivate(self, *, reason: str) -> None:
        previous = self.active_digest()
        _atomic_json(
            self.active_path,
            {
                "digest": None,
                "previous_digest": previous,
                "deactivated_at": datetime.now(UTC).isoformat(),
                "reason": reason,
            },
        )

    def active_digest(self) -> str | None:
        if not self.active_path.exists():
            return None
        value = json.loads(self.active_path.read_text(encoding="utf-8"))
        digest = value.get("digest")
        return str(digest) if digest is not None else None

    def load(self, digest: str) -> RuleProgram:
        path = self._revision_dir(digest) / "world_model.py"
        return RuleProgram.from_source(path.read_text(encoding="utf-8"))

    def active(self) -> RuleProgram | None:
        digest = self.active_digest()
        return self.load(digest) if digest else None

    def revisions(self) -> tuple[ModelRevision, ...]:
        results: list[ModelRevision] = []
        for manifest in self.revisions_dir.glob("*/manifest.json"):
            value = json.loads(manifest.read_text(encoding="utf-8"))
            results.append(
                ModelRevision(
                    digest=str(value["digest"]),
                    source_path=Path(value["source_path"]),
                    created_at=str(value["created_at"]),
                    parent=value.get("parent"),
                    author=str(value.get("author", "unknown")),
                    note=str(value.get("note", "")),
                )
            )
        return tuple(sorted(results, key=lambda item: item.created_at))

    def _revision_dir(self, digest: str) -> Path:
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError("invalid revision digest")
        directory = self.revisions_dir / digest
        if not directory.is_dir():
            raise KeyError(digest)
        return directory


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)
