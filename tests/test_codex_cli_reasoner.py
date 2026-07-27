from __future__ import annotations

from pathlib import Path

import pytest

from arcworld.llm import CodexCLIReasoner, ReasonerConfig
from arcworld.llm.codex_cli import CodexCLIError


def _fake_codex(path: Path, *, tool_event: bool = False) -> Path:
    extra = (
        'print(json.dumps({"type":"item.completed","item":{"type":"command_execution"}}))'
        if tool_event
        else ""
    )
    path.write_text(
        f"""#!/usr/bin/env python3
import json
import pathlib
import sys
if "--version" in sys.argv:
    print("codex-cli test")
    raise SystemExit
prompt = sys.stdin.read()
assert "<instructions>" in prompt and "<input>" in prompt
output = "```python\\ndef answer():\\n    return 1\\n```"
target = pathlib.Path(sys.argv[sys.argv.index("--output-last-message") + 1])
target.write_text(output)
print(json.dumps({{"type":"thread.started","thread_id":"thread-real-shape"}}))
print(json.dumps({{"type":"turn.started"}}))
{extra}
print(json.dumps({{"type":"item.completed","item":{{"type":"agent_message","text":output}}}}))
print(json.dumps({{"type":"turn.completed","usage":{{"input_tokens":12,"output_tokens":8}}}}))
""",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def test_codex_cli_reasoner_records_provider_receipt(tmp_path: Path) -> None:
    executable = _fake_codex(tmp_path / "codex")
    reasoner = CodexCLIReasoner(
        ReasonerConfig("gpt-5.6-luna", "low", "revision"),
        executable=executable,
    )

    response = reasoner.complete(instructions="write code", input_text="evidence")

    assert response.startswith("```python")
    metadata = reasoner.last_completion_metadata
    assert metadata["provider"] == "openai"
    assert metadata["transport"] == "codex-cli"
    assert metadata["thread_id"] == "thread-real-shape"
    assert metadata["usage"] == {"input_tokens": 12, "output_tokens": 8}
    assert metadata["tool_event_count"] == 0
    assert metadata["sandbox"] == "read-only"
    assert len(str(metadata["executable_sha256"])) == 64


def test_codex_cli_reasoner_rejects_tool_use(tmp_path: Path) -> None:
    executable = _fake_codex(tmp_path / "codex", tool_event=True)
    reasoner = CodexCLIReasoner(
        ReasonerConfig("gpt-5.6-luna", "low", "planning"),
        executable=executable,
    )

    with pytest.raises(CodexCLIError, match="tool use"):
        reasoner.complete(instructions="write code", input_text="evidence")
