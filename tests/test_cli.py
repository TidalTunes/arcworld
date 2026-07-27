from __future__ import annotations

import json
from pathlib import Path

from arcworld.cli import main


def test_toy_cli_is_end_to_end_certified(tmp_path: Path, capsys: object) -> None:
    main(["toy-run", "--root", str(tmp_path / ".arcworld")])
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    value = json.loads(captured.out)
    assert value["status"] == "WIN"
    assert value["actions"] == 7
    assert value["replay_certified"]
    assert not value["diverged"]
