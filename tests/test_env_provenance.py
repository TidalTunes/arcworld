from __future__ import annotations

import builtins
import hashlib
import json
import socket
import sys
from pathlib import Path
from typing import Any

import pytest

from arcworld.env.provenance import (
    AmbiguousEnvironmentError,
    AmbiguousSourceError,
    InvalidGameIdError,
    InvalidMetadataError,
    MetadataMismatchError,
    MissingEnvironmentError,
    MissingSourceError,
    SourceMismatchError,
    collect_environment_provenance,
    discover_offline_puzzles,
)


def _write_environment(
    root: Path,
    game_id: str = "ab12-1234abcd",
    *,
    class_name: str | None = None,
    directory: Path | None = None,
    source_name: str | None = None,
    source: str | None = None,
) -> tuple[Path, Path]:
    base_id, version_id = game_id.split("-", 1)
    location = directory or root / base_id / version_id
    location.mkdir(parents=True, exist_ok=True)
    metadata: dict[str, object] = {"game_id": game_id, "title": "fixture"}
    if class_name is not None:
        metadata["class_name"] = class_name
    metadata_path = location / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    resolved_class = class_name or (base_id[0].upper() + base_id[1:])
    source_path = location / (source_name or f"{resolved_class.lower()}.py")
    source_path.write_text(
        source or f"class {resolved_class}:\n    pass\n",
        encoding="utf-8",
    )
    return metadata_path, source_path


def test_collects_exact_offline_file_and_distribution_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metadata_path, source_path = _write_environment(tmp_path)
    versions = {"arc-agi": "0.9.9", "arcengine": "0.9.3"}
    monkeypatch.setattr(
        "arcworld.env.provenance._installed_version",
        versions.__getitem__,
    )

    record = collect_environment_provenance(tmp_path, "ab12-1234abcd")

    assert record.game_id == "ab12-1234abcd"
    assert record.class_name == "Ab12"
    assert record.operation_mode == "offline"
    assert record.arc_agi_version == "0.9.9"
    assert record.arcengine_version == "0.9.3"
    assert record.metadata.path == metadata_path.resolve()
    assert record.source.path == source_path.resolve()
    assert record.metadata.size_bytes == len(metadata_path.read_bytes())
    assert record.source.size_bytes == len(source_path.read_bytes())
    assert record.metadata.sha256 == hashlib.sha256(metadata_path.read_bytes()).hexdigest()
    assert record.source.sha256 == hashlib.sha256(source_path.read_bytes()).hexdigest()
    assert record.to_jsonable()["operation_mode"] == "offline"
    assert record.to_jsonable()["metadata"] == record.metadata.to_jsonable()


def test_explicit_metadata_class_name_selects_exact_class_source(tmp_path: Path) -> None:
    _, source_path = _write_environment(
        tmp_path,
        class_name="FixtureGame",
        source_name="FixtureGame.py",
    )

    record = collect_environment_provenance(tmp_path, "ab12-1234abcd")

    assert record.class_name == "FixtureGame"
    assert record.source.path.samefile(source_path)


@pytest.mark.parametrize(
    "game_id",
    [
        "ab12",
        "ab12-",
        "../ab12-1234abcd",
        "ab12-../../escape",
        "abc-1234abcd",
    ],
)
def test_requires_an_exact_safe_versioned_game_id(tmp_path: Path, game_id: str) -> None:
    with pytest.raises(InvalidGameIdError, match="exact versioned game ID"):
        collect_environment_provenance(tmp_path, game_id)


def test_missing_and_mismatched_metadata_fail_distinctly(tmp_path: Path) -> None:
    with pytest.raises(MissingEnvironmentError, match="no metadata.json"):
        collect_environment_provenance(tmp_path, "ab12-1234abcd")

    canonical = tmp_path / "ab12" / "1234abcd"
    canonical.mkdir(parents=True)
    (canonical / "metadata.json").write_text(
        json.dumps({"game_id": "ab12-deadbeef"}),
        encoding="utf-8",
    )

    with pytest.raises(MetadataMismatchError, match="declares game_id 'ab12-deadbeef'"):
        collect_environment_provenance(tmp_path, "ab12-1234abcd")


def test_invalid_canonical_metadata_and_duplicate_exact_metadata_fail(
    tmp_path: Path,
) -> None:
    canonical = tmp_path / "ab12" / "1234abcd"
    canonical.mkdir(parents=True)
    (canonical / "metadata.json").write_text("{not-json", encoding="utf-8")
    with pytest.raises(InvalidMetadataError, match="invalid JSON"):
        collect_environment_provenance(tmp_path, "ab12-1234abcd")

    (canonical / "metadata.json").unlink()
    _write_environment(tmp_path, directory=tmp_path / "copy-one")
    _write_environment(tmp_path, directory=tmp_path / "copy-two")
    with pytest.raises(AmbiguousEnvironmentError, match="multiple metadata files"):
        collect_environment_provenance(tmp_path, "ab12-1234abcd")


def test_missing_ambiguous_and_mismatched_sources_fail_clearly(tmp_path: Path) -> None:
    _, source_path = _write_environment(tmp_path, class_name="FixtureGame")
    source_path.unlink()
    with pytest.raises(MissingSourceError, match="no source file"):
        collect_environment_provenance(tmp_path, "ab12-1234abcd")

    source_path.write_text("class WrongGame:\n    pass\n", encoding="utf-8")
    with pytest.raises(SourceMismatchError, match="does not define expected"):
        collect_environment_provenance(tmp_path, "ab12-1234abcd")

    source_path.write_text("class FixtureGame:\n    pass\n", encoding="utf-8")
    case_variant = source_path.with_name("FixtureGame.py")
    case_variant.write_text("class FixtureGame:\n    pass\n", encoding="utf-8")
    if case_variant.samefile(source_path):
        record = collect_environment_provenance(tmp_path, "ab12-1234abcd")
        assert record.source.path.samefile(source_path)
    else:
        with pytest.raises(AmbiguousSourceError, match="multiple source files"):
            collect_environment_provenance(tmp_path, "ab12-1234abcd")


def test_collection_imports_no_sdk_and_opens_no_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_environment(tmp_path)
    real_import = builtins.__import__
    module_presence = {name: name in sys.modules for name in ("arc_agi", "arcengine")}

    def guarded_import(
        name: str,
        globals: dict[str, Any] | None = None,
        locals: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        if name.split(".", 1)[0] in {"arc_agi", "arcengine"}:
            raise AssertionError(f"SDK import attempted: {name}")
        return real_import(name, globals, locals, fromlist, level)

    def forbidden_network(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"network attempted with {args!r} {kwargs!r}")

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(socket, "create_connection", forbidden_network)

    record = collect_environment_provenance(tmp_path, "ab12-1234abcd")

    assert record.game_id == "ab12-1234abcd"
    assert {name: name in sys.modules for name in ("arc_agi", "arcengine")} == module_presence


def test_offline_catalog_is_sorted_validated_and_surfaces_bad_entries(
    tmp_path: Path,
) -> None:
    _write_environment(tmp_path, "zz99-deadbeef")
    first_metadata, _ = _write_environment(tmp_path, "ab12-1234abcd")
    value = json.loads(first_metadata.read_text(encoding="utf-8"))
    value["tags"] = ["do-not-expose"]
    value["baseline_actions"] = [1, 2, 3]
    first_metadata.write_text(json.dumps(value), encoding="utf-8")
    broken = tmp_path / "broken" / "metadata.json"
    broken.parent.mkdir()
    broken.write_text("{not-json", encoding="utf-8")

    catalog = discover_offline_puzzles(tmp_path)

    assert [item.game_id for item in catalog.puzzles] == [
        "ab12-1234abcd",
        "zz99-deadbeef",
    ]
    assert len(catalog.issues) == 1
    assert catalog.issues[0].code == "InvalidMetadataError"
    serialized = json.dumps(catalog.to_jsonable())
    assert "do-not-expose" not in serialized
    assert "baseline_actions" not in serialized
    assert "class Ab12" not in serialized


def test_offline_catalog_missing_directory_is_an_explicit_issue(tmp_path: Path) -> None:
    catalog = discover_offline_puzzles(tmp_path / "absent")
    assert catalog.puzzles == ()
    assert len(catalog.issues) == 1
    assert catalog.issues[0].code == "missing_directory"
