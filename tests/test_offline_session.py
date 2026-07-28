from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from arcworld.env.arc_adapter import ArcAdapter, ArcAdapterError
from arcworld.env.offline_session import DeferredOfflineEnvironment
from arcworld.env.provenance import collect_environment_provenance
from arcworld.types import GameStatus, Observation, freeze_grid


def test_official_sdk_creation_is_deferred_and_source_cache_changes_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game_id = "ab12-1234abcd"
    location = tmp_path / "environment_files" / "ab12" / "1234abcd"
    location.mkdir(parents=True)
    (location / "metadata.json").write_text(
        json.dumps(
            {
                "game_id": game_id,
                "title": "Fixture",
                "class_name": "FixtureGame",
            }
        ),
        encoding="utf-8",
    )
    source = location / "fixturegame.py"
    source.write_text("class FixtureGame:\n    pass\n", encoding="utf-8")
    provenance = collect_environment_provenance(tmp_path / "environment_files", game_id)
    calls: list[dict[str, Any]] = []
    observation = Observation(
        frames=(freeze_grid([[0]]),),
        status=GameStatus.NOT_FINISHED,
        game_id=game_id,
    )

    class FakeAdapter:
        raw_wrapper = SimpleNamespace(info=SimpleNamespace(local_dir=str(location.resolve())))

        def start(self) -> Observation:
            return observation

    def fake_open(
        _cls: type[ArcAdapter],
        _game_id: str,
        **kwargs: Any,
    ) -> FakeAdapter:
        calls.append(kwargs)
        return FakeAdapter()

    monkeypatch.setattr(ArcAdapter, "open_offline", classmethod(fake_open))
    deferred = DeferredOfflineEnvironment(
        game_id=game_id,
        environments_dir=tmp_path / "environment_files",
        recordings_dir=tmp_path / "recordings",
        seed=0,
        expected_provenance=provenance,
    )

    assert calls == []
    assert deferred.start() is observation
    assert deferred.start() is observation
    assert len(calls) == 1
    assert Path(calls[0]["environments_dir"]).is_absolute()

    source.write_text("class FixtureGame:\n    pass\n# changed\n", encoding="utf-8")
    changed = collect_environment_provenance(tmp_path / "environment_files", game_id)
    second = DeferredOfflineEnvironment(
        game_id=game_id,
        environments_dir=tmp_path / "environment_files",
        recordings_dir=tmp_path / "recordings",
        seed=1,
        expected_provenance=changed,
    )
    with pytest.raises(ArcAdapterError, match="restart the GUI"):
        second.start()
    assert len(calls) == 1
