# ARCWorld progress ledger

**Current snapshot:** 2026-07-27
**Project phase:** integrated research baseline; blind benchmark work not started
**Benchmark claim:** none
**Hidden-evaluation claim:** none

This is the living status record. It distinguishes files that exist from
features that are integrated, tested, and research-ready.

## Status legend

- ✅ **Implemented and smoke-checked:** code exists and a relevant local check
  passed.
- 🟨 **Partial/scaffold:** useful code exists, but the target architecture,
  integration, or verification is incomplete.
- ⬜ **Planned:** no adequate implementation exists.
- ⛔ **Blocked:** external data, credentials, authority, or a decision is
  required.

An item is not marked implemented because it appears in a design document or
README.

## Snapshot summary

| Area | Status | Evidence |
|---|---|---|
| Source-linked benchmark/strategy research | ✅ | `research/` landscape and source registries |
| Domain types and environment protocol | ✅ | `types.py`, `env/base.py`, replay and toy environments |
| Official SDK offline adapter | 🟨 | Six SDK-free tests pass; pinned-SDK/local-game audit passed separately; scored integration is pending |
| Persistent evidence ledger | 🟨 | SQLite events are transactional and hash-chained; final seals and crash tests do not exist |
| Object-centric perception | 🟨 | Components, relations, tracking, and alternatives exist; ontology lattice is limited |
| Executable model contract and replay verifier | ✅ | Source validation, content-addressing, exact replay, and toy certification work |
| Single active plus weighted shadows | 🟨 | Joint model/ontology IDs, complete revalidation, promotion, and control integration work; no blind ablation |
| Risk-aware active probes | 🟨 | Disagreement, cost, failure-as-risk, death risk, and one-step probe integration work; utility remains incomplete |
| Latent-state induction | ⬜ | Design only |
| Tiered exact/semantic verification | 🟨 | Exact and semantic diffs exist; tier policy and shadow likelihoods are incomplete |
| Planning | 🟨 | Bounded BFS, plan DSL, and verified executor exist; CEGAR and portfolio do not |
| Short high-level agent loop | ✅ | Protocol-oriented controller plus concrete revision/probe/plan services pass a local-reasoner end-to-end test |
| Optional OpenAI development adapter | 🟨 | Sanitized, recorded requests and responses exist; no live API test, usage/cost capture, or retry policy |
| Synthetic environment | ✅ | Deterministic key-door toy world and exact model |
| Synthetic blind holdout suite | ⬜ | One visible toy is not a blind suite |
| Local inspection GUI | 🟨 | Actual/Predicted/Diff, objects, relations, timeline, and toy controls exist |
| Scoring utilities | ✅ | Formula helpers, CLI, eight edge/reference tests, and a 5,000-game research differential check pass |
| Automated tests | ✅ | 48 tests across 13 files pass in the project virtual environment |
| Lint/type/test gate | ✅ | Ruff, strict mypy, and pytest pass |
| Public Demo evaluation | ⬜ | No 25-game run has been performed |
| Kaggle submission/evaluation | ⬜ | No submission has been performed |
| Git history and GitHub remote | ✅ | Public `TidalTunes/arcworld` remote and audited baseline commit |

## Implemented and inspected

### Research record

- [x] Dated strategy landscape separating official Semi-Private, Kaggle hidden,
  and Public Demo/self-reported regimes.
- [x] Machine-readable strategy source registry with score protocol and
  best-of-\(k\) caveats.
- [x] Official SDK/game, benchmark, scoring, and rules research created by the
  parallel research work.
- [x] Architecture document states the proposed differentiation as a
  hypothesis, not a proven novelty claim.
- [x] Evaluation protocol defines strict pass@1, blindness, lane separation,
  synthetic holdouts, metrics, and ablations.
- [x] Open-question register records falsification experiments and unresolved
  design choices.

### Core domain and environments

- [x] Immutable grid, action, observation, transition, status, and serialization
  types.
- [x] Identity-redacting observation serialization.
- [x] Narrow `Environment` protocol.
- [x] Deterministic replay environment.
- [x] Deterministic synthetic key-door environment with undo/reset behavior.
- [x] Offline-only official SDK adapter with lazy optional imports, action
  availability checks, and explicit refusal of a competition-mode environment
  override.
- [ ] SDK adapter exercised against the installed official package and a real
  locally downloaded Public Demo environment.

### Evidence and artifacts

- [x] In-memory contiguous episode history.
- [x] SQLite runs/events schema with ordered event append API and WAL mode.
- [x] Transactional sequence allocation and SHA-256 event hash chain.
- [x] Content-addressed model revisions, manifests, verification reports, and
  atomic active pointer.
- [x] Actual, predicted, diff, model digest, and plan digest can be stored for
  an executed step.
- [ ] Final run seals, content-addressed frame blobs, and insert-only database
  enforcement.
- [ ] Crash-consistency and concurrent-append tests.
- [x] Sanitized reasoner request, response, config hashes, latency, revision
  reports, action intent, raw result, and derived analysis are recorded.
- [ ] Provider token usage and monetary cost provenance.

### Perception

- [x] Background-color candidate ranking.
- [x] Same-color 4- and 8-connected component parsers.
- [x] Object attributes: pixels, shape, area, perimeter, holes, bounding box,
  centroid.
- [x] Geometric relations: left/right, above/below, aligned axes, touching,
  contains/inside, same color, and same shape.
- [x] Candidate scene graphs preserve two backgrounds and both connectivity
  choices; ontology IDs include the background and connectivity choice.
- [x] Deterministic greedy temporal identity tracker with uncertainty cost
  exposed in events.
- [x] Exact pixel regions and semantic object/relation diffs.
- [ ] Multicolor objects, repeated motifs, symmetry groups, part/whole
  alternatives, and explicit merge/split hypotheses.
- [ ] Top-\(k\) temporal correspondences and occlusion memory.
- [ ] Causal roles learned from interventions.

### Executable models and revisions

- [x] Small generated-code contract:
  `initial_state`, `step`, and `render`, with optional frames, status, metrics,
  and goal.
- [x] JSON-state normalization and content digest.
- [x] AST/call restrictions, reduced builtins, isolated `python -I` workers,
  fresh globals per call, JSON-only IPC, timeouts, and best-effort resource
  limits.
- [x] Complete-history replay report with per-transition exact and semantic
  diagnostics.
- [x] Revision manager stages multiple candidates, records reports, retains
  hypotheses, and promotes only a passing candidate.
- [x] Weighted hypothesis ledger using evidence log weight minus a complexity
  proxy.
- [x] A former or nonwinning passing candidate can remain in the ledger.
- [x] Promotion is bound to the model digest and the exact successful evidence
  digest; every verification report is retained.
- [ ] Hardened container/seccomp boundary for adversarial generated source.
- [ ] Explicit semantic-shadow versus exact-shadow lifecycle.
- [ ] Duplicate/equivalent-program canonicalization.
- [ ] Calibrated likelihoods and diversity-aware weights.
- [x] Joint hypothesis identity for a scene-ontology choice and dynamics
  program, with ontology-targeted proposals.
- [ ] Learned executable ontology programs and representation operations beyond
  the built-in candidates.
- [ ] Bounded latent-state automaton induction and belief-state tracking.

### Probing and planning

- [x] Weighted outcome fingerprints and entropy.
- [x] Death-risk penalty and primitive/reset/click action costs.
- [x] Deterministic probe ranking.
- [x] Bounded BFS over JSON states with node and depth limits.
- [x] Capability-poor Python plan DSL.
- [x] Plan source digest and action-count limits.
- [x] Per-action simulate/execute/compare loop.
- [x] Complete plan rollout is required before the first real action.
- [x] Hard real-action budget enforcement and GAME_OVER-to-RESET recovery.
- [x] Dynamic available-action/full-reset checks and exact animation checks.
- [x] Remaining queued actions are returned and execution stops at the first
  mismatch.
- [ ] Generic click candidate generator.
- [ ] Task-progress, reversibility, delayed-risk, reset, and remaining-budget
  terms in probe utility.
- [x] Probe selection is integrated through `BeliefAwarePlanningService`.
- [ ] A*, width/novelty, constraint/backtracking, and belief-state planners.
- [ ] Planner router and comparable planner metrics.
- [ ] Counterexample-guided abstraction refinement.
- [ ] Verified macro induction and invalidation.

### Agent and reasoner

- [x] High-level `WorldModelAgent` depends on revision and planning protocols
  rather than implementing their mechanisms.
- [x] It records the initial observation and every actual/predicted step when a
  store is configured.
- [x] It requests revision after divergence and rebuilds model state by replay.
- [x] Provider-neutral reasoner interface.
- [x] Optional OpenAI Responses API adapter with revision/planning/utility role
  defaults.
- [x] World-model and plan prompts serialize observations without game ID or
  GUID.
- [x] Exact one-code-block extraction and contract validation.
- [x] Concrete adapter connects `LLMWorldModelProposer`,
  `RevisionManager`, the shadow predictor/probe selector, and
  `WorldModelAgent`.
- [x] Recursive reasoner request redaction removes identity and opaque metadata;
  dedicated leakage tests pass.
- [ ] Model-call retry, timeout, rate-limit, and invalid-output policy.
- [x] Request/response/config hashes and latency records.
- [ ] Provider token usage and cost records.
- [x] In-process `CallableReasoner` and generic local composition.
- [ ] Packaged Kaggle local-checkpoint profile/notebook.
- [ ] Deterministic fallback when the reasoner is unavailable.

### GUI and CLI

- [x] CLI parser with `doctor`, `toy-run`, `gui`, local `list-games`,
  `run-offline`, `score`, and `verify-run`.
- [x] Doctor command performs no network operation.
- [x] Toy command records events, promotes a model, executes a plan, and
  certifies complete replay.
- [x] FastAPI read APIs for run list/timeline and observation comparison.
- [x] Local dashboard shows Actual, Predicted, and Difference grids.
- [x] Dashboard shows objects, relations, changed-pixel/object metrics, raw
  evidence, and a timeline.
- [x] Development-only live controls for the synthetic toy.
- [ ] Active/shadow model timeline with weights and evidence links.
- [ ] Ontology comparison and latent-state inspector.
- [ ] Plan rollout tree, planner statistics, and cancelled-action display.
- [ ] Explicit read-only evaluation mode and scored-run lock.
- [ ] Replay export/import and experiment comparison.
- [ ] Browser-level GUI tests and accessibility/responsive review.

### Scoring

- [x] Dependency-free level, game, completion-cap, and benchmark helpers that
  declare compatibility with `arc-agi` v0.9.9.
- [x] Level cap, level weighting, incomplete-level handling, and omitted-game
  denominator are explicit.
- [x] Eight scoring edge/reference tests and a research-time 5,000-game
  differential check against the pinned official formula.
- [ ] Differential check against the installed official scorer on real public
  recordings.
- [ ] Scorer and human-baseline digests in run manifests.
- [ ] Raw per-level action/progress extraction from the event ledger.
- [x] Basic one-game scoring command.
- [ ] Versioned run-ledger rescoring command.

### Automated quality checks

- [x] Domain, model, perception, hypothesis/probe, planning, storage/GUI API,
  and end-to-end toy CLI tests.
- [x] 48 tests pass in `.venv`.
- [x] Ruff reports no issues.
- [x] Strict mypy reports no issues across 43 checked source modules.
- [x] Dedicated scoring edge-case tests.
- [x] Six dependency-free official-adapter contract tests.
- [x] Generated-code module-scope, global-purity, and timeout tests.
- [ ] Browser-level GUI tests.

## Verification performed through 2026-07-27

### Passed

- [x] `python3 -m compileall -q src/arcworld`
- [x] `PYTHONPATH=src python3 -m arcworld.cli doctor`
- [x] `PYTHONPATH=src python3 -m arcworld.cli toy-run --root <temporary-dir>`
- [x] Toy result: `WIN`, 7 real actions, no divergence, complete replay
  certified.
- [x] `.venv/bin/python -m pytest -q`: 48 passed.
- [x] `.venv/bin/ruff check .`: all checks passed.
- [x] `.venv/bin/mypy`: no issues in 43 checked source modules.
- [x] FastAPI storage/live-toy/inspection API smoke test is included in pytest.
- [x] `research/sources-strategies.yaml` parsed successfully.
- [x] All source IDs referenced by that strategy registry resolve internally.
- [x] `git diff --check` passed for the strategy research artifacts when they
  were created.

### Not run

- [x] Six SDK-free adapter contract tests.
- [x] During the SDK research audit, the adapter opened and stepped local
  `ls20` with `arc-agi` 0.9.9/`arcengine` 0.9.3. The project venv deliberately
  does not require those optional packages.
- [ ] Browser-level GUI test: the API is covered, but the rendered browser UI
  has not been exercised automatically.
- [ ] Live OpenAI adapter test: the package is installed but no API key was
  configured.

These are explicit gaps, not passing checks.

## Immediate plan

### P0 — make the scaffold trustworthy

- [x] Install the declared development dependencies in a project virtual
  environment.
- [x] Add initial deterministic tests for types, parsing, tracking, diffs, model source
  validation, replay verification, revision promotion, probe ranking, BFS,
  executor cancellation, storage, GUI API, CLI, and redaction.
- [x] Add scoring and official-adapter tests.
- [x] Run and fix `ruff check .`, strict `mypy`, and `pytest`.
- [x] Add generated-code isolation and adversarial timeout/global-purity tests.
- [x] Add transactional event hash chaining.
- [ ] Add final seals and crash-injection tests.
- [ ] Pin run manifests with commit, config, prompt, model, scorer, budget, and
  selection-rule hashes.
- [x] Create the first repository commit and configure the intended GitHub
  remote without committing environment files, secrets, private replays, or
  generated workspaces.

### P1 — integrate the research treatment

- [x] Wire a single-model exact-replay baseline end to end.
- [x] Wire `RevisionManager` and `HypothesisLedger` into the agent.
- [x] Simulate every viable exact shadow over candidate actions and rank
  discriminating probes.
- [x] Add a controller: observe, diagnose, probe, formalize, plan, execute,
  and stop.
- [x] Keep only the promoted active model in the exploitation planner.
- [ ] Implement semantic shadows without weakening exact promotion.
- [x] Add joint IDs for built-in ontology candidates and dynamics hypotheses.
- [ ] Add learned representation-revision operations.
- [ ] Add contradiction-triggered bounded latent-state synthesis.
- [ ] Build click candidates and no-effect signatures generically.
- [ ] Add CEGAR plus at least one complementary planner before calling the
  planner a portfolio.

### P2 — establish blind evidence

- [ ] Implement visible synthetic generator families.
- [ ] Seal independent families/parameters/seeds before tuning.
- [ ] Implement the strict pass@1 runner and audit checks.
- [ ] Run the core \(2 \times 2 \times 2\) version-space/probing/ontology
  ablation.
- [ ] Report per-instance completion, actions, deaths, mismatch calibration,
  recovery latency, simulated nodes, tokens, time, and cost.
- [ ] Freeze a candidate before any Public Demo aggregate run.
- [ ] Run the 25 public games only through the offline official adapter.
- [ ] Treat public results as development evidence and publish every trajectory.
- [ ] Prepare an offline local-model Kaggle profile only after the synthetic
  blind treatment beats its single-model baseline.

### P3 — researcher usability

- [ ] Add model/ontology/latent-state timelines to the GUI.
- [ ] Show shadow predictions and the decomposition of probe utility.
- [ ] Add replay branching in explicitly unscored development mode.
- [ ] Add experiment comparison, filters, and machine-readable export.
- [ ] Ask an independent researcher to reproduce the toy run and locate a
  planted mismatch using only the docs and GUI.

## Research milestone checklist

- [x] Identify official score regimes and current frontier results.
- [x] Identify the direct collision with Schema and executable-world-model
  prior art.
- [x] State a falsifiable differentiation hypothesis.
- [x] Define blindness, pass@1, cost, action, and ablation reporting.
- [x] Faithfully implement and test a single-active exact-replay baseline.
- [x] Demonstrate active-plus-shadow revalidation and a discriminating toy
  probe.
- [ ] Demonstrate ontology revision on a synthetic part/whole ambiguity.
- [ ] Demonstrate latent-state recovery on a positive control and rejection on
  an observable negative control.
- [ ] Complete a preregistered synthetic blind ablation.
- [ ] Complete a fresh Public Demo pass@1 run with frozen configuration.
- [ ] Complete a Kaggle hidden evaluation.
- [ ] Support, weaken, or reject the central research hypothesis.

## Dated activity log

### 2026-07-26 — benchmark and strategy research

- Recorded official, Kaggle, and public/self-reported evidence separately.
- Documented Schema, Executable World Models, OPINE-World, PRO-LONG, Milestone
  1 agents, and adjacent baselines.
- Determined that the originally proposed single-simulator loop is not itself a
  defensible novelty claim.
- Proposed an active-model plus weighted-shadow version space as a hypothesis.

### 2026-07-26 — first scaffold inspection

- Inspected domain, perception, model, hypothesis, probing, planning,
  environment, storage, agent, LLM, scoring, CLI, and GUI sources.
- Confirmed that the high-level agent is short and protocol-oriented.
- Compiled all Python sources successfully under Python 3.13.6.
- Ran the local doctor successfully without network access.
- Ran the toy key-door path successfully: 7 actions, `WIN`, no divergence, and
  exact complete-history replay certification.
- Ran 19 tests successfully, including the GUI API and end-to-end toy CLI.
- Ran Ruff and strict mypy successfully.
- Recorded that the official SDK/game files and a live OpenAI key were not
  available; no benchmark score was produced.

### 2026-07-27 — scored-run correctness and integration audit

- Replaced the hidden second reset with `Environment.start()`, which consumes
  the observation already created by `Arcade.make`.
- Hard-capped real actions, made GAME_OVER recover through RESET, and added
  tests for both.
- Moved generated world-model and plan code to isolated workers with JSON IPC,
  fresh globals, timeouts, and resource limits; timeout/adversarial tests pass.
- Bound promotion to exact evidence digests, retained all verification reports,
  and hash-chained intent/raw-result/analysis events.
- Wired local callable reasoners, model revision, joint ontology/model shadows,
  active probes, pre-execution rollout, verified execution, and recovery
  through the complete agent path.
- Ran 48 tests, Ruff, strict mypy, wheel-content inspection, and the seven-action
  toy certification successfully.
- No OpenAI request, Public Demo run, Kaggle submission, or benchmark score was
  produced.
- Created the public `TidalTunes/arcworld` GitHub repository and added a
  Python 3.12/3.13 CI gate.

## How to update this file

For each material change:

1. update the relevant checklist item without upgrading partial work to
   implemented prematurely;
2. add a dated activity-log entry naming the command, artifact, or experiment;
3. link a run ID, manifest, commit, or report where one exists;
4. preserve failed checks and negative results;
5. state the next falsifiable step;
6. never place Public Demo and hidden results in the same unlabeled aggregate.
