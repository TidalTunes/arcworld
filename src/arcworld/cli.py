"""Command-line entry points for local experiments and inspection."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

from arcworld.env.toy import TOY_MODEL_SOURCE, ToyKeyDoorEnvironment
from arcworld.history import EpisodeHistory
from arcworld.models.store import ModelRepository
from arcworld.models.verifier import ReplayVerifier
from arcworld.planning.dsl import Plan
from arcworld.planning.executor import ExecutionStep, VerifiedExecutor
from arcworld.storage import RunStore
from arcworld.types import Action, ActionKind, Observation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="arcworld", description="ARCWorld research suite")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor", help="report local capabilities without network access")

    toy = subparsers.add_parser("toy-run", help="run and certify the synthetic key-door world")
    toy.add_argument("--root", type=Path, default=Path(".arcworld"))

    gui = subparsers.add_parser("gui", help="serve the local dashboard; does not open a browser")
    gui.add_argument("--store", type=Path, default=Path(".arcworld/runs.db"))
    gui.add_argument("--host", default="127.0.0.1")
    gui.add_argument("--port", type=int, default=8765)

    games = subparsers.add_parser("list-games", help="list locally installed official games")
    games.add_argument("--environments-dir", type=Path, default=Path("environment_files"))

    run = subparsers.add_parser(
        "run-offline",
        help="run the OpenAI development composition on one locally installed game",
    )
    run.add_argument("--game", required=True)
    run.add_argument("--environments-dir", type=Path, default=Path("environment_files"))
    run.add_argument("--workspace", type=Path, default=Path(".arcworld"))
    run.add_argument("--action-budget", type=int, default=500)
    run.add_argument("--candidate-count", type=int, default=2)
    run.add_argument(
        "--provider",
        choices=("openai-api", "codex-cli"),
        default="openai-api",
        help="explicit live OpenAI transport",
    )
    run.add_argument("--model", help="override the provider model")
    run.add_argument("--effort", help="override the provider reasoning effort")
    run.add_argument("--codex-bin", type=Path, help="Codex CLI executable")
    run.add_argument("--seed", type=int, default=0)

    score = subparsers.add_parser("score", help="compute one normalized RHAE game score")
    score.add_argument("--baselines", required=True, help="comma-separated human actions")
    score.add_argument("--actions", required=True, help="comma-separated agent actions")
    score.add_argument(
        "--completed",
        required=True,
        help="comma-separated true/false completion flags",
    )

    verify = subparsers.add_parser("verify-run", help="verify a run's event hash chain")
    verify.add_argument("--store", type=Path, default=Path(".arcworld/runs.db"))
    verify.add_argument("--run-id", required=True)

    audit = subparsers.add_parser(
        "audit-run",
        help="audit official-game, live-LLM, generated-code, and real-action evidence",
    )
    audit.add_argument("--store", type=Path, default=Path(".arcworld/runs.db"))
    audit.add_argument("--run-id", required=True)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "doctor":
        _doctor()
    elif args.command == "toy-run":
        _toy_run(args.root)
    elif args.command == "gui":
        _gui(args.store, args.host, args.port)
    elif args.command == "list-games":
        _list_games(args.environments_dir)
    elif args.command == "run-offline":
        _run_offline(
            args.game,
            args.environments_dir,
            args.workspace,
            args.action_budget,
            args.candidate_count,
            args.provider,
            args.model,
            args.effort,
            args.codex_bin,
            args.seed,
        )
    elif args.command == "score":
        _score(args.baselines, args.actions, args.completed)
    elif args.command == "verify-run":
        _verify_run(args.store, args.run_id)
    elif args.command == "audit-run":
        _audit_run(args.store, args.run_id)


def _doctor() -> None:
    optional = {
        "arc_agi": bool(importlib.util.find_spec("arc_agi")),
        "fastapi": bool(importlib.util.find_spec("fastapi")),
        "openai": bool(importlib.util.find_spec("openai")),
        "uvicorn": bool(importlib.util.find_spec("uvicorn")),
    }
    print(
        json.dumps(
            {
                "python": platform.python_version(),
                "executable": sys.executable,
                "optional_packages": optional,
                "openai_key_present": bool(__import__("os").environ.get("OPENAI_API_KEY")),
                "network_used": False,
            },
            indent=2,
            sort_keys=True,
        )
    )


def _toy_run(root: Path) -> None:
    store = RunStore(root / "runs.db")
    repository = ModelRepository(root / "models" / "toy")
    revision = repository.stage(
        TOY_MODEL_SOURCE,
        author="built-in",
        note="deterministic synthetic smoke-test model",
    )
    program = repository.load(revision.digest)
    environment = ToyKeyDoorEnvironment()
    observation = environment.reset()
    history = EpisodeHistory(observation)
    run_id = store.create_run("synthetic-key-door", {"model_digest": program.digest})
    store.append(run_id, "initial_observation", observation.to_jsonable())
    initial_report = ReplayVerifier().verify(program, history)
    repository.record_verification(program.digest, initial_report.to_jsonable())
    repository.promote(program.digest, evidence_digest=initial_report.evidence_digest)

    state = program.initial_state(observation)
    plan = Plan(tuple(Action(ActionKind.ACTION4) for _ in range(7)), rationale="collect/open/reach")

    def capture_raw(
        action: Action,
        predicted: Observation,
        actual: Observation,
    ) -> None:
        transition = history.append(action, actual)
        store.append(
            run_id,
            "transition_raw",
            {
                "transition": transition.to_jsonable(),
                "predicted": predicted.to_jsonable(),
                "model_digest": program.digest,
            },
        )

    def capture_analysis(step: ExecutionStep) -> None:
        store.append(
            run_id,
            "transition_analysis",
            {
                "transition_index": len(history.transitions) - 1,
                "diff": step.diff.to_jsonable(),
                "model_digest": program.digest,
            },
        )

    result = VerifiedExecutor().execute(
        plan,
        environment=environment,
        program=program,
        model_state=state,
        observation=observation,
        on_raw_step=capture_raw,
        on_step=capture_analysis,
    )
    report = ReplayVerifier().verify(program, history)
    repository.record_verification(program.digest, report.to_jsonable())
    store.append(run_id, "verification", report.to_jsonable())
    print(
        json.dumps(
            {
                "run_id": run_id,
                "status": result.final_observation.status.value,
                "actions": len(result.steps),
                "diverged": result.diverged,
                "replay_certified": report.passed,
                "model_digest": program.digest,
                "store": str(store.path),
            },
            indent=2,
        )
    )


def _gui(store: Path, host: str, port: int) -> None:
    try:
        import uvicorn
    except ImportError as error:
        raise SystemExit("install ARCWorld with: pip install -e '.[gui]'") from error
    from arcworld.gui.app import create_app

    uvicorn.run(create_app(store), host=host, port=port, log_level="info")


def _list_games(environments_dir: Path) -> None:
    try:
        arc_agi = __import__("arc_agi", fromlist=["Arcade", "OperationMode"])
    except ModuleNotFoundError as error:
        raise SystemExit("install ARCWorld with: pip install -e '.[arc]'") from error
    arcade = arc_agi.Arcade(
        operation_mode=arc_agi.OperationMode.OFFLINE,
        environments_dir=str(environments_dir),
    )
    environments: list[Any] = arcade.get_environments()
    for item in sorted(environments, key=lambda value: value.game_id):
        print(item.game_id)


def _run_offline(
    game_id: str,
    environments_dir: Path,
    workspace: Path,
    action_budget: int,
    candidate_count: int,
    provider: str,
    model: str | None,
    effort: str | None,
    codex_bin: Path | None,
    seed: int,
) -> None:
    if provider == "openai-api" and not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is required for the OpenAI development composition")
    if action_budget <= 0:
        raise SystemExit("--action-budget must be positive")
    if not 1 <= candidate_count <= 8:
        raise SystemExit("--candidate-count must be in 1..8")

    from arcworld.audit import audit_real_llm_run
    from arcworld.composition import build_codex_agent, build_openai_agent
    from arcworld.env.arc_adapter import ArcAdapter
    from arcworld.env.provenance import collect_environment_provenance

    provenance = collect_environment_provenance(environments_dir, game_id)
    environment = ArcAdapter.open_offline(
        game_id,
        environments_dir=environments_dir,
        save_recording=True,
        seed=seed,
    )
    run_metadata = {
        "run_kind": "official-public-game-live-llm",
        "evaluation_lane": "public-demo",
        "environment": provenance.to_jsonable(),
        "provider_transport": provider,
        "action_budget": action_budget,
        "candidate_count": candidate_count,
        "seed": seed,
        "git": _git_state(),
        "python": platform.python_version(),
    }
    if provider == "codex-cli":
        bundle = build_codex_agent(
            environment,
            model=model or "gpt-5.6-luna",
            effort=effort or "low",
            executable=codex_bin,
            workspace=workspace,
            label=f"public-demo-live-llm:{game_id}:codex-cli",
            candidate_count=candidate_count,
            run_metadata=run_metadata,
        )
    else:
        bundle = build_openai_agent(
            environment,
            model=model,
            effort=effort,
            workspace=workspace,
            label=f"public-demo-live-llm:{game_id}:responses-api",
            candidate_count=candidate_count,
            run_metadata=run_metadata,
        )
    try:
        result = bundle.agent.run(action_budget=action_budget)
    except Exception as error:
        store = RunStore(workspace / "runs.db")
        store.append(
            bundle.run_id,
            "run_error",
            {"error_type": type(error).__name__, "error": str(error)},
        )
        print(
            json.dumps(
                {
                    "run_id": bundle.run_id,
                    "episode_workspace": str(bundle.episode_workspace),
                    "error_type": type(error).__name__,
                    "error": str(error),
                },
                indent=2,
            )
        )
        raise
    store = RunStore(workspace / "runs.db")
    audit = audit_real_llm_run(store, bundle.run_id)
    print(
        json.dumps(
            {
                "run_id": bundle.run_id,
                "episode_workspace": str(bundle.episode_workspace),
                "status": result.status.value,
                "actions": result.real_actions,
                "revisions": result.revisions,
                "reason": result.reason,
                "audit_passed": audit.passed,
                "audit_checks": {check.name: check.passed for check in audit.checks},
            },
            indent=2,
        )
    )
    if not audit.passed:
        raise SystemExit(2)


def _score(baselines_text: str, actions_text: str, completed_text: str) -> None:
    from arcworld.scoring import score_game

    try:
        baselines = [float(item) for item in baselines_text.split(",")]
        actions = [float(item) for item in actions_text.split(",")]
        completed = [
            {"true": True, "false": False}[item.strip().casefold()]
            for item in completed_text.split(",")
        ]
        score = score_game(baselines, actions, completed)
    except (KeyError, ValueError) as error:
        raise SystemExit(f"invalid scoring input: {error}") from error
    print(json.dumps({"normalized_score": score, "percent": score * 100}, indent=2))


def _verify_run(store_path: Path, run_id: str) -> None:
    store = RunStore(store_path)
    try:
        store.run(run_id)
    except KeyError as error:
        raise SystemExit(f"run not found: {run_id}") from error
    valid = store.verify_chain(run_id)
    print(json.dumps({"run_id": run_id, "event_chain_valid": valid}, indent=2))
    if not valid:
        raise SystemExit(1)


def _audit_run(store_path: Path, run_id: str) -> None:
    from arcworld.audit import audit_real_llm_run

    store = RunStore(store_path)
    try:
        report = audit_real_llm_run(store, run_id)
    except KeyError as error:
        raise SystemExit(f"run not found: {run_id}") from error
    print(json.dumps(report.to_jsonable(), indent=2))
    if not report.passed:
        raise SystemExit(2)


def _git_state() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    status = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "commit": commit.stdout.strip() if commit.returncode == 0 else None,
        "dirty": bool(status.stdout.strip()) if status.returncode == 0 else None,
    }


if __name__ == "__main__":
    main()
