"""Authenticated OpenAI Codex CLI transport for local development experiments."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from arcworld.llm.base import ReasonerConfig

_APP_CODEX = Path("/Applications/ChatGPT.app/Contents/Resources/codex")
_TOOL_ITEM_TYPES = frozenset(
    {
        "command_execution",
        "file_change",
        "mcp_tool_call",
        "web_search",
    }
)


class CodexCLIError(RuntimeError):
    """The isolated CLI reasoner did not produce an auditable completion."""


@dataclass(slots=True)
class CodexCLIReasoner:
    """Use an authenticated OpenAI Codex installation as a text-only reasoner.

    Each request runs in a fresh empty directory, read-only, with repository rules and
    user configuration ignored. Authentication is retained, but the game-playing model
    receives only the supplied instructions and observation evidence.
    """

    config: ReasonerConfig
    executable: Path | None = None
    timeout_seconds: float = 300.0
    last_completion_metadata: dict[str, Any] = field(default_factory=dict, init=False)

    def complete(self, *, instructions: str, input_text: str) -> str:
        executable = _resolve_executable(self.executable)
        version = _codex_version(executable)
        prompt = _prompt(instructions, input_text)
        with tempfile.TemporaryDirectory(prefix="arcworld-codex-") as directory:
            root = Path(directory)
            final_path = root / "final.txt"
            command = [
                str(executable),
                "exec",
                "--ephemeral",
                "--ignore-user-config",
                "--ignore-rules",
                "--skip-git-repo-check",
                "--sandbox",
                "read-only",
                "--model",
                self.config.model,
                "-c",
                f'model_reasoning_effort="{self.config.effort}"',
                "--cd",
                str(root),
                "--json",
                "--output-last-message",
                str(final_path),
                "-",
            ]
            try:
                completed = subprocess.run(
                    command,
                    input=prompt,
                    text=True,
                    capture_output=True,
                    timeout=self.timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as error:
                raise CodexCLIError(
                    f"Codex CLI exceeded the {self.timeout_seconds:g}s completion timeout"
                ) from error
            if completed.returncode != 0:
                detail = completed.stderr.strip().splitlines()[-1:] or ["no stderr"]
                raise CodexCLIError(f"Codex CLI exited {completed.returncode}: {detail[0][:500]}")
            if not final_path.is_file():
                raise CodexCLIError("Codex CLI did not write a final response")
            response = final_path.read_text(encoding="utf-8").strip()
            if not response:
                raise CodexCLIError("Codex CLI returned an empty final response")

        events = _events(completed.stdout)
        tool_items = _tool_items(events)
        if tool_items:
            raise CodexCLIError(
                "text-only reasoner attempted tool use: " + ", ".join(sorted(tool_items))
            )
        thread_id = _thread_id(events)
        usage = _usage(events)
        if not thread_id or not usage:
            raise CodexCLIError("Codex CLI transcript lacks thread or token-usage evidence")
        self.last_completion_metadata = {
            "provider": "openai",
            "transport": "codex-cli",
            "requested_model": self.config.model,
            "reasoning_effort": self.config.effort,
            "thread_id": thread_id,
            "usage": usage,
            "exit_code": completed.returncode,
            "event_count": len(events),
            "tool_event_count": 0,
            "ephemeral": True,
            "sandbox": "read-only",
            "isolated_empty_workdir": True,
            "cli_version": version,
            "executable_path": str(executable),
            "executable_sha256": _file_digest(executable),
            "transcript_sha256": _text_digest(completed.stdout),
            "stderr_sha256": _text_digest(completed.stderr),
            "final_message_sha256": _text_digest(response),
        }
        return response


def _resolve_executable(configured: Path | None) -> Path:
    if configured is not None:
        candidate = configured.expanduser().resolve()
    elif os.getenv("ARCWORLD_CODEX_BIN"):
        candidate = Path(os.environ["ARCWORLD_CODEX_BIN"]).expanduser().resolve()
    elif _APP_CODEX.is_file():
        candidate = _APP_CODEX.resolve()
    else:
        discovered = shutil.which("codex")
        if discovered is None:
            raise CodexCLIError(
                "no Codex CLI was found; set ARCWORLD_CODEX_BIN or pass an executable"
            )
        candidate = Path(discovered).resolve()
    if not candidate.is_file():
        raise CodexCLIError(f"Codex CLI does not exist: {candidate}")
    return candidate


def _codex_version(executable: Path) -> str:
    completed = subprocess.run(
        [str(executable), "--version"],
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    if completed.returncode != 0:
        raise CodexCLIError("could not identify the Codex CLI version")
    return completed.stdout.strip()


def _prompt(instructions: str, input_text: str) -> str:
    return (
        "Act only as a text reasoner. Do not call tools, inspect files, or use a network.\n"
        "<instructions>\n"
        f"{instructions}\n"
        "</instructions>\n"
        "<input>\n"
        f"{input_text}\n"
        "</input>\n"
        "Return the requested answer directly."
    )


def _events(transcript: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(transcript.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise CodexCLIError(
                f"invalid Codex JSON event at line {line_number}: {error}"
            ) from error
        if not isinstance(value, dict):
            raise CodexCLIError(f"Codex JSON event {line_number} is not an object")
        events.append(value)
    return events


def _tool_items(events: list[dict[str, Any]]) -> set[str]:
    result: set[str] = set()
    for event in events:
        item = event.get("item")
        if isinstance(item, dict) and str(item.get("type")) in _TOOL_ITEM_TYPES:
            result.add(str(item["type"]))
    return result


def _thread_id(events: list[dict[str, Any]]) -> str:
    for event in events:
        if event.get("type") == "thread.started":
            return str(event.get("thread_id", ""))
    return ""


def _usage(events: list[dict[str, Any]]) -> dict[str, int]:
    for event in reversed(events):
        if event.get("type") != "turn.completed":
            continue
        value = event.get("usage")
        if isinstance(value, dict):
            return {str(key): int(item) for key, item in value.items()}
    return {}


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _text_digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
