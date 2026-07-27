"""Requirement-level audit of a recorded real-game LLM episode."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from arcworld.llm.prompts import extract_python
from arcworld.storage import RunStore
from arcworld.types import Observation


@dataclass(frozen=True, slots=True)
class AuditCheck:
    name: str
    passed: bool
    evidence: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RunAudit:
    run_id: str
    passed: bool
    checks: tuple[AuditCheck, ...]

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "passed": self.passed,
            "checks": [asdict(check) for check in self.checks],
        }


def audit_real_llm_run(store: RunStore, run_id: str) -> RunAudit:
    """Prove the stored chain connects official assets, live output, code, and actions."""

    run = store.run(run_id)
    events = store.timeline(run_id)
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        by_kind.setdefault(str(event["kind"]), []).append(event)
    config = _mapping(run.get("config"))
    experiment = _mapping(config.get("experiment"))
    environment = _mapping(experiment.get("environment"))
    responses = {
        str(_payload(event).get("request_id", "")): _payload(event)
        for event in by_kind.get("reasoner_response", [])
    }

    checks = (
        _integrity_check(store, run_id, events),
        _lifecycle_check(by_kind),
        _environment_check(experiment, environment),
        _provider_check(by_kind),
        _world_model_check(by_kind, responses),
        _plan_check(by_kind, responses),
        _execution_check(by_kind, environment),
    )
    return RunAudit(run_id, all(check.passed for check in checks), checks)


def _integrity_check(
    store: RunStore,
    run_id: str,
    events: list[dict[str, Any]],
) -> AuditCheck:
    return AuditCheck(
        "tamper-evident event chain",
        bool(events) and store.verify_chain(run_id),
        {
            "event_count": len(events),
            "head_event_hash": events[-1].get("event_hash") if events else None,
        },
    )


def _lifecycle_check(by_kind: dict[str, list[dict[str, Any]]]) -> AuditCheck:
    started = by_kind.get("run_started", [])
    finished = by_kind.get("run_finished", [])
    payload = _payload(finished[-1]) if finished else {}
    passed = (
        len(started) == 1
        and len(finished) == 1
        and int(payload.get("real_actions", 0)) > 0
        and str(payload.get("reason", "")) in {"terminal", "action_budget"}
    )
    return AuditCheck(
        "complete run lifecycle",
        passed,
        {
            "run_started_events": len(started),
            "run_finished_events": len(finished),
            "status": payload.get("status"),
            "real_actions": payload.get("real_actions"),
            "revisions": payload.get("revisions"),
            "reason": payload.get("reason"),
        },
    )


def _environment_check(
    experiment: dict[str, Any],
    environment: dict[str, Any],
) -> AuditCheck:
    metadata = _mapping(environment.get("metadata"))
    source = _mapping(environment.get("source"))
    metadata_path = Path(str(metadata.get("path", "")))
    source_path = Path(str(source.get("path", "")))
    expected_metadata = str(metadata.get("sha256", ""))
    expected_source = str(source.get("sha256", ""))
    actual_metadata = _path_digest(metadata_path)
    actual_source = _path_digest(source_path)
    game_id = str(environment.get("game_id", ""))
    passed = (
        experiment.get("run_kind") == "official-public-game-live-llm"
        and experiment.get("evaluation_lane") == "public-demo"
        and environment.get("operation_mode") == "offline"
        and bool(game_id)
        and len(expected_metadata) == 64
        and len(expected_source) == 64
        and actual_metadata == expected_metadata
        and actual_source == expected_source
    )
    return AuditCheck(
        "official public game assets",
        passed,
        {
            "game_id": game_id,
            "evaluation_lane": experiment.get("evaluation_lane"),
            "operation_mode": environment.get("operation_mode"),
            "metadata_path": str(metadata_path),
            "metadata_sha256": expected_metadata,
            "metadata_hash_matches": actual_metadata == expected_metadata,
            "source_path": str(source_path),
            "source_sha256": expected_source,
            "source_hash_matches": actual_source == expected_source,
            "arc_agi_version": environment.get("arc_agi_version"),
            "arcengine_version": environment.get("arcengine_version"),
        },
    )


def _provider_check(by_kind: dict[str, list[dict[str, Any]]]) -> AuditCheck:
    response_events = by_kind.get("reasoner_response", [])
    summaries: list[dict[str, Any]] = []
    valid = len(response_events) >= 2
    for event in response_events:
        payload = _payload(event)
        metadata = _mapping(payload.get("provider_metadata"))
        usage = _mapping(metadata.get("usage"))
        transport = str(metadata.get("transport", ""))
        provider_anchor = (
            str(metadata.get("thread_id", ""))
            if transport == "codex-cli"
            else str(metadata.get("response_id", ""))
        )
        token_total = sum(
            int(value) for key, value in usage.items() if "token" in key and isinstance(value, int)
        )
        final_digest = str(metadata.get("final_message_sha256", ""))
        item_valid = (
            metadata.get("provider") == "openai"
            and transport in {"codex-cli", "responses-api"}
            and bool(provider_anchor)
            and token_total > 0
            and int(metadata.get("tool_event_count", 0)) == 0
            and (
                transport != "codex-cli"
                or (
                    int(metadata.get("exit_code", -1)) == 0
                    and final_digest == payload.get("response_digest")
                    and metadata.get("sandbox") == "read-only"
                    and metadata.get("isolated_empty_workdir") is True
                )
            )
        )
        valid = valid and item_valid
        summaries.append(
            {
                "request_id": payload.get("request_id"),
                "role": payload.get("role"),
                "model": payload.get("model"),
                "provider": metadata.get("provider"),
                "transport": transport,
                "provider_anchor": provider_anchor,
                "token_total": token_total,
                "tool_event_count": metadata.get("tool_event_count", 0),
                "transcript_sha256": metadata.get("transcript_sha256"),
                "valid": item_valid,
            }
        )
    roles = {str(item.get("role", "")) for item in summaries}
    valid = valid and {"revision", "planning"}.issubset(roles)
    return AuditCheck(
        "live OpenAI completion provenance",
        valid,
        {"completion_count": len(summaries), "roles": sorted(roles), "completions": summaries},
    )


def _world_model_check(
    by_kind: dict[str, list[dict[str, Any]]],
    responses: dict[str, dict[str, Any]],
) -> AuditCheck:
    revisions = [_payload(event) for event in by_kind.get("model_revision", [])]
    promoted = [item for item in revisions if item.get("promoted") is True]
    executed = {
        str(_payload(event).get("model_digest", "")) for event in by_kind.get("model_executed", [])
    }
    linked: list[dict[str, Any]] = []
    valid = bool(promoted)
    for item in promoted:
        source = str(item.get("source", ""))
        digest = str(item.get("model_digest", ""))
        request_id = str(item.get("origin_request_id", ""))
        response = responses.get(request_id, {})
        extracted = _extract_or_empty(str(response.get("response", "")))
        item_valid = (
            bool(source)
            and _text_digest(source.strip() + "\n") == digest
            and item.get("source_sha256") == digest
            and item.get("origin_response_digest") == response.get("response_digest")
            and extracted == source.strip() + "\n"
            and digest in executed
            and _mapping(item.get("verification")).get("passed") is True
        )
        valid = valid and item_valid
        linked.append(
            {
                "model_digest": digest,
                "origin_request_id": request_id,
                "response_digest": response.get("response_digest"),
                "source_bytes": len(source.encode()),
                "replay_verified": _mapping(item.get("verification")).get("passed"),
                "sandbox_executed": digest in executed,
                "valid": item_valid,
            }
        )
    return AuditCheck(
        "LLM world-model source executed",
        valid,
        {"promoted_revisions": linked},
    )


def _plan_check(
    by_kind: dict[str, list[dict[str, Any]]],
    responses: dict[str, dict[str, Any]],
) -> AuditCheck:
    generated = [_payload(event) for event in by_kind.get("plan_generated", [])]
    simulated = {
        str(_payload(event).get("plan_digest", "")): _payload(event)
        for event in by_kind.get("plan_simulated", [])
    }
    intended = {
        str(_payload(event).get("plan_digest", "")) for event in by_kind.get("action_intent", [])
    }
    linked: list[dict[str, Any]] = []
    valid = bool(generated)
    for item in generated:
        source = str(item.get("source", ""))
        digest = str(item.get("plan_digest", ""))
        request_id = str(item.get("origin_request_id", ""))
        response = responses.get(request_id, {})
        extracted = _extract_or_empty(str(response.get("response", "")))
        simulation = simulated.get(digest, {})
        item_valid = (
            bool(source)
            and _text_digest(source.strip() + "\n") == digest
            and item.get("source_sha256") == digest
            and item.get("origin_response_digest") == response.get("response_digest")
            and extracted == source.strip() + "\n"
            and item.get("build_plan_executed") is True
            and simulation.get("complete_before_real_action") is True
            and digest in intended
        )
        valid = valid and item_valid
        linked.append(
            {
                "plan_digest": digest,
                "origin_request_id": request_id,
                "response_digest": response.get("response_digest"),
                "source_bytes": len(source.encode()),
                "returned_actions": len(item.get("actions", [])),
                "build_plan_executed": item.get("build_plan_executed"),
                "fully_simulated": simulation.get("complete_before_real_action"),
                "authorized_real_action": digest in intended,
                "valid": item_valid,
            }
        )
    return AuditCheck("LLM plan source executed", valid, {"plans": linked})


def _execution_check(
    by_kind: dict[str, list[dict[str, Any]]],
    environment: dict[str, Any],
) -> AuditCheck:
    raws = [_payload(event) for event in by_kind.get("transition_raw", [])]
    analyses = [_payload(event) for event in by_kind.get("transition_analysis", [])]
    intents = [_payload(event) for event in by_kind.get("action_intent", [])]
    game_id = str(environment.get("game_id", ""))
    transitions: list[dict[str, Any]] = []
    valid = bool(raws and analyses and intents)
    for index, raw in enumerate(raws):
        transition = _mapping(raw.get("transition"))
        before = Observation.from_jsonable(_mapping(transition.get("before")))
        after = Observation.from_jsonable(_mapping(transition.get("after")))
        changed = _changed_pixels(before, after)
        intent = intents[index] if index < len(intents) else {}
        analysis = analyses[index] if index < len(analyses) else {}
        action = _mapping(transition.get("action"))
        item_valid = (
            before.game_id == game_id
            and after.game_id == game_id
            and bool(before.guid)
            and bool(after.guid)
            and action == _mapping(intent.get("action"))
            and str(intent.get("model_digest", "")) == str(analysis.get("model_digest", ""))
            and str(intent.get("plan_digest", "")) == str(analysis.get("plan_digest", ""))
        )
        valid = valid and item_valid
        transitions.append(
            {
                "index": transition.get("index"),
                "action": action,
                "game_id": after.game_id,
                "session_guid_present": bool(after.guid),
                "changed_pixels": changed,
                "model_digest": intent.get("model_digest"),
                "plan_digest": intent.get("plan_digest"),
                "valid": item_valid,
            }
        )
    return AuditCheck(
        "real official environment transition",
        valid,
        {
            "transition_count": len(transitions),
            "effectful_transition_count": sum(
                int(item["changed_pixels"]) > 0 for item in transitions
            ),
            "transitions": transitions,
        },
    )


def _payload(event: dict[str, Any]) -> dict[str, Any]:
    return _mapping(event.get("payload"))


def _mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return value


def _extract_or_empty(response: str) -> str:
    try:
        return extract_python(response)
    except ValueError:
        return ""


def _changed_pixels(before: Observation, after: Observation) -> int:
    if before.shape != after.shape:
        return max(
            len(before.latest) * len(before.latest[0]),
            len(after.latest) * len(after.latest[0]),
        )
    return sum(
        left != right
        for before_row, after_row in zip(before.latest, after.latest, strict=True)
        for left, right in zip(before_row, after_row, strict=True)
    )


def _path_digest(path: Path) -> str:
    if not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _text_digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
