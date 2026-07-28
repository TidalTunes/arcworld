from __future__ import annotations

import json
from pathlib import Path

from arcworld.cli import build_parser, main


def test_toy_cli_is_end_to_end_certified(tmp_path: Path, capsys: object) -> None:
    main(["toy-run", "--root", str(tmp_path / ".arcworld")])
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    value = json.loads(captured.out)
    assert value["status"] == "WIN"
    assert value["actions"] == 7
    assert value["replay_certified"]
    assert not value["diverged"]


def test_gui_uses_the_non_conflicting_http_location_by_default() -> None:
    args = build_parser().parse_args(["gui"])
    assert args.host == "127.0.0.1"
    assert args.port == 8878
