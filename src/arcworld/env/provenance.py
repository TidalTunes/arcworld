"""Deterministic provenance for an official environment cached for offline use.

This module only reads local files and installed distribution metadata.  It
does not import ``arc_agi`` or ``arcengine`` and contains no network client.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Literal, cast

_EXACT_GAME_ID = re.compile(r"^[A-Za-z0-9]{4}-[A-Za-z0-9][A-Za-z0-9._-]*$")


class EnvironmentProvenanceError(RuntimeError):
    """Base class for local provenance failures."""


class InvalidGameIdError(EnvironmentProvenanceError):
    """The requested ID is not an exact versioned game ID."""


class MissingEnvironmentError(EnvironmentProvenanceError):
    """No metadata for the exact game ID exists below the cache root."""


class AmbiguousEnvironmentError(EnvironmentProvenanceError):
    """More than one metadata file claims the exact game ID."""


class InvalidMetadataError(EnvironmentProvenanceError):
    """A relevant metadata file is unreadable or invalid."""


class MetadataMismatchError(EnvironmentProvenanceError):
    """A canonical cache path contains metadata for another game."""


class MissingSourceError(EnvironmentProvenanceError):
    """Metadata resolves to no class source file."""


class AmbiguousSourceError(EnvironmentProvenanceError):
    """Metadata resolves to more than one distinct class source file."""


class SourceMismatchError(EnvironmentProvenanceError):
    """The resolved source does not define the metadata-selected class."""


@dataclass(frozen=True, slots=True)
class FileProvenance:
    """Byte-level identity of one local evidence file."""

    path: Path
    sha256: str
    size_bytes: int

    def to_jsonable(self) -> dict[str, str | int]:
        return {
            "path": str(self.path),
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True, slots=True)
class EnvironmentProvenance:
    """Reproducibility record for one exact official environment."""

    game_id: str
    class_name: str
    operation_mode: Literal["offline"]
    metadata: FileProvenance
    source: FileProvenance
    arc_agi_version: str | None
    arcengine_version: str | None

    def to_jsonable(self) -> dict[str, object]:
        return {
            "game_id": self.game_id,
            "class_name": self.class_name,
            "operation_mode": self.operation_mode,
            "metadata": self.metadata.to_jsonable(),
            "source": self.source.to_jsonable(),
            "arc_agi_version": self.arc_agi_version,
            "arcengine_version": self.arcengine_version,
        }


@dataclass(frozen=True, slots=True)
class _MetadataCandidate:
    path: Path
    content: bytes
    value: dict[str, object]


def collect_environment_provenance(
    environments_dir: str | Path,
    game_id: str,
) -> EnvironmentProvenance:
    """Collect offline provenance for one exact versioned game.

    The cache is searched recursively because that is how SDK offline discovery
    works.  Exactly one ``metadata.json`` must claim ``game_id``.  The source
    filename comes from ``class_name``; when that optional field is absent, the
    official SDK convention derives the class from the first four ID
    characters (for example, ``vc33-...`` becomes ``Vc33`` / ``vc33.py``).
    """

    base_id, version_id = _validate_exact_game_id(game_id)
    root = Path(environments_dir).expanduser()
    if not root.is_dir():
        raise MissingEnvironmentError(
            f"environment cache directory does not exist or is not a directory: {root}"
        )
    root = root.resolve()

    canonical_paths = {
        (root / game_id / "metadata.json").resolve(),
        (root / base_id / version_id / "metadata.json").resolve(),
    }
    matches: list[_MetadataCandidate] = []
    canonical_failures: list[EnvironmentProvenanceError] = []

    for metadata_path in sorted(root.rglob("metadata.json")):
        resolved = metadata_path.resolve()
        try:
            candidate = _read_metadata(resolved)
        except InvalidMetadataError as exc:
            if resolved in canonical_paths:
                canonical_failures.append(exc)
            continue
        if candidate.value.get("game_id") == game_id:
            matches.append(candidate)
        elif resolved in canonical_paths:
            actual = candidate.value.get("game_id")
            canonical_failures.append(
                MetadataMismatchError(
                    f"{resolved} declares game_id {actual!r}, expected {game_id!r}"
                )
            )

    if canonical_failures:
        raise canonical_failures[0]
    if len(matches) > 1:
        paths = ", ".join(str(item.path) for item in matches)
        raise AmbiguousEnvironmentError(
            f"multiple metadata files declare game_id {game_id!r}: {paths}"
        )
    if not matches:
        if canonical_failures:
            raise canonical_failures[0]
        raise MissingEnvironmentError(
            f"no metadata.json below {root} declares exact game_id {game_id!r}"
        )

    selected = matches[0]
    class_name = _metadata_class_name(selected.value, game_id, selected.path)
    source_path = _resolve_source(selected.path.parent, class_name)
    source_content = _read_source(source_path, class_name)

    return EnvironmentProvenance(
        game_id=game_id,
        class_name=class_name,
        operation_mode="offline",
        metadata=_fingerprint(selected.path, selected.content),
        source=_fingerprint(source_path, source_content),
        arc_agi_version=_installed_version("arc-agi"),
        arcengine_version=_installed_version("arcengine"),
    )


def _validate_exact_game_id(game_id: str) -> tuple[str, str]:
    if not _EXACT_GAME_ID.fullmatch(game_id) or ".." in game_id:
        raise InvalidGameIdError(
            f"expected an exact versioned game ID such as 'vc33-5430563c', got {game_id!r}"
        )
    base_id, version_id = game_id.split("-", 1)
    return base_id, version_id


def _read_metadata(path: Path) -> _MetadataCandidate:
    if not path.is_file():
        raise InvalidMetadataError(f"metadata path is not a regular file: {path}")
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise InvalidMetadataError(f"cannot read metadata file {path}: {exc}") from exc
    try:
        parsed: object = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidMetadataError(f"invalid JSON in metadata file {path}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise InvalidMetadataError(f"metadata file must contain a JSON object: {path}")
    value = cast(dict[str, object], parsed)
    declared_id = value.get("game_id")
    if not isinstance(declared_id, str) or not declared_id:
        raise InvalidMetadataError(f"metadata file has no non-empty string game_id: {path}")
    return _MetadataCandidate(path=path, content=content, value=value)


def _metadata_class_name(
    metadata: dict[str, object],
    game_id: str,
    metadata_path: Path,
) -> str:
    raw = metadata.get("class_name")
    if raw is None:
        base_id = game_id[:4]
        class_name = base_id[0].upper() + base_id[1:]
    elif isinstance(raw, str):
        class_name = raw
    else:
        raise InvalidMetadataError(f"class_name in {metadata_path} must be a string when present")
    if not class_name or not class_name.isidentifier():
        raise InvalidMetadataError(
            f"class_name in {metadata_path} is not a non-empty Python identifier: {class_name!r}"
        )
    return class_name


def _resolve_source(directory: Path, class_name: str) -> Path:
    candidates = _distinct_paths(
        directory / f"{class_name.lower()}.py",
        directory / f"{class_name}.py",
    )
    existing = [path for path in candidates if path.is_file()]
    if not existing:
        expected = ", ".join(str(path) for path in candidates)
        found = ", ".join(str(path) for path in sorted(directory.glob("*.py"))) or "none"
        raise MissingSourceError(
            f"no source file for class {class_name!r}; expected {expected}; "
            f"other Python files: {found}"
        )
    if len(existing) > 1:
        paths = ", ".join(str(path) for path in existing)
        raise AmbiguousSourceError(
            f"multiple source files resolve from class_name {class_name!r}: {paths}"
        )
    return existing[0].resolve()


def _distinct_paths(*paths: Path) -> list[Path]:
    result: list[Path] = []
    for path in paths:
        if any(_same_file_or_path(path, prior) for prior in result):
            continue
        result.append(path)
    return result


def _same_file_or_path(left: Path, right: Path) -> bool:
    try:
        if left.exists() and right.exists():
            return left.samefile(right)
    except OSError:
        pass
    return left.resolve() == right.resolve()


def _read_source(path: Path, class_name: str) -> bytes:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise MissingSourceError(f"cannot read source file {path}: {exc}") from exc
    try:
        source = content.decode("utf-8")
        tree = ast.parse(source, filename=str(path))
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise SourceMismatchError(f"invalid Python source file {path}: {exc}") from exc
    declared_classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    if class_name not in declared_classes:
        raise SourceMismatchError(
            f"{path} does not define expected top-level class {class_name!r}; "
            f"found {sorted(declared_classes)}"
        )
    return content


def _fingerprint(path: Path, content: bytes) -> FileProvenance:
    return FileProvenance(
        path=path.resolve(),
        sha256=hashlib.sha256(content).hexdigest(),
        size_bytes=len(content),
    )


def _installed_version(distribution_name: str) -> str | None:
    try:
        return version(distribution_name)
    except PackageNotFoundError:
        return None
