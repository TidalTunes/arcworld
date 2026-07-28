from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from arcworld.composition import build_agent
from arcworld.env.toy import TOY_MODEL_SOURCE, ToyKeyDoorEnvironment
from arcworld.interactive import EpisodePhase, InteractiveEpisode
from arcworld.llm import CallableReasoner, ReasonerConfig
from arcworld.types import Action, Observation


def _reasoner(role: str, function: Callable[[str, str], str]) -> CallableReasoner:
    return CallableReasoner(
        ReasonerConfig(model=f"deterministic-{role}", effort="fixed", role=role),
        function,
    )


def _plan(_instructions: str, _input_text: str) -> str:
    return (
        "```python\n"
        "def build_plan(api, context):\n"
        '    return api.repeat(api.action("ACTION4"), 7)\n'
        "```"
    )


def _episode(
    tmp_path: Path,
    revision: Callable[[str, str], str],
    *,
    action_budget: int = 20,
    environment: ToyKeyDoorEnvironment | None = None,
) -> InteractiveEpisode:
    bundle = build_agent(
        environment or ToyKeyDoorEnvironment(),
        revision_reasoner=_reasoner("revision", revision),
        planning_reasoner=_reasoner("planning", _plan),
        workspace=tmp_path / ".arcworld",
        candidate_count=1,
    )
    return InteractiveEpisode(bundle.agent, action_budget=action_budget)


def test_episode_advances_one_phase_and_at_most_one_real_action(
    tmp_path: Path,
) -> None:
    episode = _episode(
        tmp_path,
        lambda _instructions, _input: f"```python\n{TOY_MODEL_SOURCE}\n```",
    )
    expected = [
        EpisodePhase.START,
        EpisodePhase.INDUCTION,
        EpisodePhase.PLANNING,
        *([EpisodePhase.EXECUTION] * 7),
    ]

    for version, phase in enumerate(expected):
        assert episode.phase is phase
        before = len(episode.history.transitions) if episode.history else 0
        snapshot = episode.advance()
        after = len(episode.history.transitions) if episode.history else 0
        assert after - before == (1 if phase is EpisodePhase.EXECUTION else 0)
        assert snapshot["state_version"] == version + 1

    assert episode.phase is EpisodePhase.FINISHED
    assert episode.result is not None
    assert episode.result.real_actions == 7
    timeline = episode.agent.store.timeline(episode.run_id or "")
    raw = [event for event in timeline if event["kind"] == "transition_raw"]
    analyses = [event for event in timeline if event["kind"] == "transition_analysis"]
    intents = [event for event in timeline if event["kind"] == "action_intent"]
    assert len(raw) == len(analyses) == len(intents) == 7
    plan_ids = {event["payload"]["plan_id"] for event in raw}
    assert len(plan_ids) == 1
    assert all(event["payload"]["controller_version"] >= 3 for event in raw)
    assert episode.program is not None
    assert episode.program.runtime._process is None


def test_divergence_invalidates_plan_before_revision_and_replays_history(
    tmp_path: Path,
) -> None:
    no_motion = TOY_MODEL_SOURCE.replace(
        'if action["id"] not in directions or state["status"] != "NOT_FINISHED":',
        'if action["id"] == 4 or action["id"] not in directions '
        'or state["status"] != "NOT_FINISHED":',
    )
    calls = 0

    def revision(_instructions: str, _input_text: str) -> str:
        nonlocal calls
        calls += 1
        source = no_motion if calls == 1 else TOY_MODEL_SOURCE
        return f"```python\n{source}\n```"

    episode = _episode(tmp_path, revision)
    episode.advance()  # start
    episode.advance()  # initial induction
    episode.advance()  # planning
    snapshot = episode.advance()  # one surprising action

    assert snapshot["phase"] == EpisodePhase.REVISION.value
    assert snapshot["real_actions"] == 1
    assert snapshot["pending_plan"] is None
    assert snapshot["latest_mismatch"] is not None
    invalidations = [
        event
        for event in episode.agent.store.timeline(episode.run_id or "")
        if event["kind"] == "plan_invalidated"
    ]
    assert len(invalidations) == 1
    assert len(invalidations[0]["payload"]["discarded_actions"]) == 6

    revised = episode.advance()

    assert revised["phase"] == EpisodePhase.PLANNING.value
    assert revised["revision_count"] == 2
    assert revised["latest_mismatch"] is None
    assert episode.history is not None
    assert len(episode.history.transitions) == 1
    assert episode.model_state is not None
    assert episode.model_state["player"] == [2, 1]


def test_last_budgeted_surprise_is_revised_before_finishing(tmp_path: Path) -> None:
    no_motion = TOY_MODEL_SOURCE.replace(
        'if action["id"] not in directions or state["status"] != "NOT_FINISHED":',
        'if action["id"] == 4 or action["id"] not in directions '
        'or state["status"] != "NOT_FINISHED":',
    )
    calls = 0

    def revision(_instructions: str, _input_text: str) -> str:
        nonlocal calls
        calls += 1
        return f"```python\n{no_motion if calls == 1 else TOY_MODEL_SOURCE}\n```"

    episode = _episode(tmp_path, revision, action_budget=1)
    episode.advance()
    episode.advance()
    episode.advance()
    after_action = episode.advance()

    assert after_action["phase"] == "revision"
    assert after_action["remaining_actions"] == 0
    assert after_action["latest_mismatch"] is not None
    assert episode.result is None

    after_revision = episode.advance()

    assert after_revision["phase"] == "finished"
    assert after_revision["result"]["reason"] == "action_budget"
    assert after_revision["revision_count"] == 2
    kinds = [event["kind"] for event in episode.agent.store.timeline(episode.run_id or "")]
    assert kinds.index("plan_invalidated") < kinds.index("run_finished")


def test_post_intent_failure_becomes_outcome_unknown_and_cannot_retry(
    tmp_path: Path,
) -> None:
    class AmbiguousToy(ToyKeyDoorEnvironment):
        def step(self, action: Action) -> Observation:
            result = super().step(action)
            raise RuntimeError(f"transport lost after {result.status.value}")

    episode = _episode(
        tmp_path,
        lambda _instructions, _input: f"```python\n{TOY_MODEL_SOURCE}\n```",
        environment=AmbiguousToy(),
    )
    episode.advance()
    episode.advance()
    episode.advance()
    snapshot = episode.advance()

    assert snapshot["phase"] == "outcome_unknown"
    assert not snapshot["can_advance"]
    assert snapshot["pending_plan"] is None
    assert snapshot["real_actions"] == 0
    kinds = [event["kind"] for event in episode.agent.store.timeline(episode.run_id or "")]
    assert "action_intent" in kinds
    assert "action_outcome_unknown" in kinds
    assert "transition_raw" not in kinds
    assert episode.program is not None
    assert episode.program.runtime._process is None


def test_phase_start_evidence_failure_cannot_leave_controller_busy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    episode = _episode(
        tmp_path,
        lambda _instructions, _input: f"```python\n{TOY_MODEL_SOURCE}\n```",
    )
    assert episode.agent.store is not None

    def fail_append(*_args: object, **_kwargs: object) -> int:
        raise OSError("evidence device unavailable")

    monkeypatch.setattr(episode.agent.store, "append", fail_append)
    with pytest.raises(OSError, match="evidence device unavailable"):
        episode.advance()

    assert episode.phase is EpisodePhase.ERROR
    assert episode.active_phase is None
    assert not episode.can_advance
    assert episode.state_version == 1
