from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path

from fastapi.testclient import TestClient

from arcworld.audit import audit_real_llm_run
from arcworld.composition import build_agent
from arcworld.env.toy import TOY_MODEL_SOURCE, ToyKeyDoorEnvironment
from arcworld.gui.app import create_app
from arcworld.llm import ReasonerConfig
from arcworld.storage import RunStore
from arcworld.types import Action, Observation


@dataclass(slots=True)
class _ProviderShapedReasoner:
    config: ReasonerConfig
    function: Callable[[str, str], str]
    calls: int = 0
    last_completion_metadata: dict[str, object] = field(default_factory=dict)

    def complete(self, *, instructions: str, input_text: str) -> str:
        response = self.function(instructions, input_text)
        self.calls += 1
        self.last_completion_metadata = {
            "provider": "openai",
            "transport": "codex-cli",
            "thread_id": f"provider-thread-{self.config.role}-{self.calls}",
            "usage": {"input_tokens": 100, "output_tokens": 50},
            "exit_code": 0,
            "tool_event_count": 0,
            "sandbox": "read-only",
            "isolated_empty_workdir": True,
            "final_message_sha256": hashlib.sha256(response.encode()).hexdigest(),
            "transcript_sha256": "a" * 64,
        }
        return response


class _IdentifiedToy(ToyKeyDoorEnvironment):
    def start(self) -> Observation:
        return _identified(super().start())

    def reset(self) -> Observation:
        return _identified(super().reset())

    def step(self, action: Action) -> Observation:
        return _identified(super().step(action))


def _identified(observation: Observation) -> Observation:
    return replace(observation, game_id="real-fixture-0001", guid="official-session-guid")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_audit_links_provider_code_sandboxes_and_real_transition(tmp_path: Path) -> None:
    metadata = tmp_path / "metadata.json"
    source = tmp_path / "game.py"
    metadata.write_text('{"game_id":"real-fixture-0001"}', encoding="utf-8")
    source.write_text("class FixtureGame: pass\n", encoding="utf-8")
    revision = _ProviderShapedReasoner(
        ReasonerConfig("gpt-live", "low", "revision"),
        lambda _instructions, _input: f"```python\n{TOY_MODEL_SOURCE}\n```",
    )
    planning = _ProviderShapedReasoner(
        ReasonerConfig("gpt-live", "low", "planning"),
        lambda _instructions, _input: (
            "```python\n"
            "def build_plan(api, context):\n"
            '    return api.repeat(api.action("ACTION4"), 7)\n'
            "```"
        ),
    )
    workspace = tmp_path / ".arcworld"
    bundle = build_agent(
        _IdentifiedToy(),
        revision_reasoner=revision,
        planning_reasoner=planning,
        workspace=workspace,
        label="public-demo-live-llm:real-fixture-0001:test",
        candidate_count=1,
        run_metadata={
            "run_kind": "official-public-game-live-llm",
            "evaluation_lane": "public-demo",
            "environment": {
                "game_id": "real-fixture-0001",
                "operation_mode": "offline",
                "metadata": {
                    "path": str(metadata),
                    "sha256": _digest(metadata),
                    "size_bytes": metadata.stat().st_size,
                },
                "source": {
                    "path": str(source),
                    "sha256": _digest(source),
                    "size_bytes": source.stat().st_size,
                },
                "arc_agi_version": "test",
                "arcengine_version": "test",
            },
        },
    )

    result = bundle.agent.run(action_budget=7)
    report = audit_real_llm_run(RunStore(workspace / "runs.db"), bundle.run_id)

    assert result.real_actions == 7
    assert report.passed
    assert all(check.passed for check in report.checks)
    with TestClient(create_app(workspace / "runs.db")) as client:
        gui_payload = client.get(f"/api/runs/{bundle.run_id}").json()
    assert gui_payload["audit"]["passed"]
    assert gui_payload["event_chain_valid"]
    assert gui_payload["run"]["config"]["experiment"]["run_kind"].endswith("live-llm")
