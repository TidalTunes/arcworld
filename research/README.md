# Research index

This directory is the dated evidence base for ARCWorld. It separates facts obtained
from primary sources, volatile observations, third-party claims, design hypotheses,
and implementation status.

**Snapshot:** 2026-07-26, with live Kaggle values captured at
2026-07-27 06:22 UTC.
**Benchmark claim:** none.
**Competition submission:** none.

## Read in this order

1. [`benchmark.md`](benchmark.md) — benchmark mechanics, splits, actions, Kaggle
   execution, deadlines, rules, prizes, and the dated live leaderboard.
2. [`scoring.md`](scoring.md) — the current Relative Human Action Efficiency formula,
   worked examples, action accounting, and stale-source discrepancies.
3. [`sdk_and_games.md`](sdk_and_games.md) — exact SDK/runtime contract and the verified
   25-game, 183-level Public Demo catalog.
4. [`landscape.md`](landscape.md) — comparable score regimes, current approaches,
   public-game saturation, and the closest prior systems.
5. [`architecture.md`](architecture.md) — the falsifiable research hypothesis and
   target system.
6. [`evaluation_protocol.md`](evaluation_protocol.md) — blindness, pass@1,
   provenance, ablations, and invalidation rules.
7. [`open_questions.md`](open_questions.md) — unresolved questions and proposed
   falsification experiments.
8. [`progress.md`](progress.md) — living implemented/partial/planned ledger.

## Source registries

The source records are split by audit area so their claims and retrieval methods remain
reviewable:

- [`sources-rules.yaml`](sources-rules.yaml) — Kaggle, benchmark, scoring, policy,
  timeline, and leaderboard sources.
- [`sources-sdk.yaml`](sources-sdk.yaml) — official SDK, engine, toolkit, catalog,
  recording, and submission-harness sources.
- [`sources-strategies.yaml`](sources-strategies.yaml) — official results, papers,
  repositories, harnesses, and self-reported scores.

Repository revisions are pinned when a Git source was inspected. Volatile web/API
observations include capture times. Self-reported scores are labeled as such and retain
their pass@1/best-of-k protocol caveats.

## Most consequential finding

The project’s starting idea—an LLM-authored `step(state, action)` model, exact replay
admission, simulator planning, queued action execution, and cancellation on
divergence—is a strong baseline, but it is not a new architecture in July 2026.
Executable World Models, OPINE-World, and especially Schema already cover most of that
loop and report near-saturation of the exposed Public Demo games.

ARCWorld therefore tests a narrower extension:

> Preserve a weighted version space of replay-consistent executable models and competing
> object ontologies, and spend real actions according to expected discrimination
> adjusted for cost and irreversible risk.

That is a research hypothesis, not a novelty or performance claim. It earns support
only through the blind protocol in [`evaluation_protocol.md`](evaluation_protocol.md).

## Important separations

- The 25 downloadable Public Demo games are not Kaggle’s visible Public Leaderboard
  set.
- Kaggle reruns on 110 unseen games: 55 hidden public-LB games and 55 hidden private-LB
  games.
- Official verified Semi-Private results, Kaggle scores, and public-harness results use
  different environments and protocols.
- Near-99% Public Demo best-of-rerun results and a 1.86% Kaggle public-LB result can
  coexist without contradiction.
- OpenAI models can support development, but Kaggle’s inference notebook has internet
  disabled. A final submission needs bundled local inference or precomputed
  non-game-specific artifacts.

## Update policy

When a source changes:

1. Add a new dated observation; do not silently rewrite an old snapshot.
2. Mark the superseded claim and explain which source is binding.
3. Update any derived architecture or evaluation assumption.
4. Record the repository commit and protocol for any new score.
5. Never promote Public Demo tuning into a hidden-generalization claim.
