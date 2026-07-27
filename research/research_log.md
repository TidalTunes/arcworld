# Research log

This log records consequential research decisions. Detailed evidence remains in the
topic documents and source registries.

## 2026-07-26 — benchmark and runtime audit

- Confirmed three distinct collections: 25 downloadable Public Demo games, 55 unseen
  Kaggle public-LB games, and 55 unseen Kaggle private-LB games.
- Pinned `arc-agi` 0.9.9, `arcengine` 0.9.3, the official Agents repository,
  benchmarking harness, and Kaggle starter revisions.
- Enumerated the current 25 versioned games and 183 levels by instantiating official
  local sources. Runtime `available_actions` is authoritative; metadata tags are not.
- Recorded the 64×64, 16-color, multi-frame observation contract and ACTION1–7/RESET
  shapes.
- Chose a local-only adapter. ARCWorld does not use the anonymous or authenticated
  online ARC API during ordinary research runs.

## 2026-07-26 — scoring and competition audit

- Verified current toolkit scoring as
  `min(1.15, (human_actions / agent_actions)^2)` for a completed level, followed by
  1-indexed level weighting and a weighted-completion cap.
- Recorded stale alternatives in Kaggle data prose and the technical-report equation;
  the pinned toolkit implementation and current methodology are the executable
  authority for this snapshot.
- Confirmed one submission per day, two final submissions, team size eight, notebook
  runtime of nine hours, and internet-disabled reruns.
- Recorded binding Kaggle prize terms separately from the conflicting ARC track page.

## 2026-07-26 — prior-art correction

- Found that the requested world-model/replay/abort loop is substantially implemented
  by Executable World Models, OPINE-World, and Schema.
- Reclassified the requested loop as the baseline, not the contribution.
- Selected “risk-aware active induction over an executable version space with
  representation alternatives” as the hypothesis to test.
- Kept latent-state synthesis, joint ontology programs, and CEGAR planning as planned
  extensions rather than implemented claims.

## 2026-07-26 — model selection and deployment boundary

- Official verified results show a large current gap between GPT-5.6 Sol and Luna on
  ARC-AGI-3. Defaulted hard revision/planning roles to configurable Sol/high and cheap
  utility work to configurable Luna/low.
- Kept the reasoner interface provider-neutral and added an in-process callable adapter
  for bundled local inference.
- Restricted OpenAI usage to an optional development composition. The core simulator,
  verifier, scoring, storage, SDK adapter, and GUI are offline.

## 2026-07-26 — first implementation slice

- Implemented immutable evidence types, object graphs and alternatives, temporal
  tracking, exact/semantic diffs, generated rule/plan contracts, content-addressed
  revisions, complete-history replay, a weighted shadow ledger, active probe ranking,
  search, pre-execution rollout, verified real execution, SQLite storage, and the local
  inspection dashboard.
- Added a deterministic key/door/goal world to exercise the complete path without
  contaminating Public Demo evaluation.
- No Public Demo, Semi-Private, or Kaggle score was produced.

## 2026-07-27 — safety and scored-run correctness audit

- Removed the implicit second reset: the agent now consumes the observation already
  created by the official SDK.
- Added a hard executor action cap, GAME_OVER → RESET recovery, dynamic action/full-reset
  prediction checks, and exact intermediate-animation comparison.
- Bound atomic model promotion to a successful verification report and exact evidence
  digest; prior verification reports remain content-addressed.
- Moved generated rule and plan execution to isolated workers with JSON-only IPC, fresh
  globals, timeouts, and best-effort resource limits.
- Added intent/raw-result/derived-analysis event phases and a hash chain over SQLite
  events.
- Connected scene-ontology identifiers to joint ontology/model hypotheses. This is an
  initial version-space mechanism, not full learned ontology-program induction.
