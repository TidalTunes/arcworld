# ARC-AGI-3 scoring: exact RHAE reference

**Research snapshot:** 2026-07-26
**Pinned implementation:** `arc-agi` v0.9.9 at
[`f12822c4d550121c35a275008d964afbbed47d2f`](https://github.com/arcprize/ARC-AGI/tree/f12822c4d550121c35a275008d964afbbed47d2f)
**Exact upstream file:**
[`arc_agi/scorecard.py`](https://github.com/arcprize/ARC-AGI/blob/f12822c4d550121c35a275008d964afbbed47d2f/arc_agi/scorecard.py)

ARC-AGI-3 uses **Relative Human Action Efficiency** (RHAE, pronounced
“ray”). The current metric rewards level completion and penalizes real actions
quadratically. This document treats the pinned source as the executable
reference because older Kaggle prose contains a stale formula.

The local, dependency-free reproduction is
[`src/arcworld/scoring.py`](../src/arcworld/scoring.py). It returns normalized
scores in `0..1`; the upstream file performs equivalent calculations in
percentage units.

## Notation

For level \(i\) of a game:

- \(H_i\): upper-median first-time human action baseline;
- \(A_i\): AI actions charged to that level;
- \(C_i\): 1 if completed, otherwise 0;
- \(w_i = i\): the 1-indexed level weight.

Human baselines are gathered from multiple people seeing the game for the first
time. The official methodology sorts the participants by action efficiency and
uses the upper median rather than an average or theoretical shortest path.

## 1. Per-level score

For a completed level with at least one recorded action:

\[
s_i = \min\left(1.15,\left(\frac{H_i}{A_i}\right)^2\right)
\]

For an incomplete level, or a completed level recorded with zero actions:

\[
s_i = 0
\]

The square is the dominant incentive:

| Relative action use | Uncapped RHAE |
|---:|---:|
| \(A = H\) | 1.00 |
| \(A = 2H\) | 0.25 |
| \(A = 5H\) | 0.04 |
| \(A = 10H\) | 0.01 |
| \(A < 0.9325H\) | capped at 1.15 |

The threshold in the last row is \(H/\sqrt{1.15}\). A faster-than-baseline
level can therefore earn up to 15% excess credit, but that does not let the
final game score exceed 100%.

## 2. Later levels receive more weight

For a game with \(L\) levels, compute the weighted efficiency:

\[
E =
\frac{\sum_{i=1}^{L} w_i s_i}
     {\sum_{i=1}^{L} w_i},
\qquad w_i=i
\]

Level 5 is worth five times as much as level 1. This intentionally discounts
tutorial behavior and emphasizes transfer of the inferred rule to later levels.

## 3. Completion cap

Efficiency is capped by the weighted fraction of levels completed:

\[
M =
\frac{\sum_{i=1}^{L} w_i \mathbf{1}[s_i>0]}
     {\sum_{i=1}^{L} w_i}
\]

The game score is:

\[
G = \min(E, M)
\]

The exact v0.9.9 source uses `level_score > 0` rather than a separate completion
flag when computing \(M\). With valid positive human baselines and action
counts, these are equivalent. The local implementation preserves the source
behavior.

For five levels, solving only the first four gives:

\[
M = \frac{1+2+3+4}{1+2+3+4+5}
  = \frac{10}{15}
  = 0.666\overline{6}
\]

Even scores of 1.15 on all four completed levels cannot push the game above
66.67%. Conversely, when all levels are complete, the cap is 1.0. The 1.15
per-level bonus can offset inefficiency elsewhere in the game, but can never
make \(G > 1\).

## 4. Benchmark score

For \(N\) games:

\[
B = \frac{1}{N}\sum_{g=1}^{N}G_g
\]

The result is displayed as a percentage. In Kaggle competition mode:

- the public score averages the 55 hidden public-LB games;
- the final score averages the 55 hidden private-LB games; and
- an unplayed game contributes zero.

The 25 Public Demo score is a separate 25-game average. It must never be mixed
into either Kaggle average.

## Worked examples

### Action penalty

For \(H=10\):

- \(A=10\): \(s=1.0\)
- \(A=20\): \(s=(10/20)^2=0.25\)
- \(A=100\): \(s=(10/100)^2=0.01\)
- \(A=8\): the raw value is 1.5625, so \(s=1.15\)

### Speed bonus versus completion cap

A three-level game with scores `[1.15, 1.15, 0]` has weighted efficiency:

\[
E = \frac{1(1.15)+2(1.15)+3(0)}{1+2+3}=0.575
\]

but the completion cap is:

\[
M=\frac{1+2}{1+2+3}=0.5
\]

so the final game score is 0.5.

### Speed bonus offsets a slower level

A two-level game with scores `[1.15, 0.80]` is fully complete:

\[
E=\frac{1(1.15)+2(0.80)}{3}=0.916\overline{6},
\quad M=1
\]

so \(G=0.916\overline{6}\).

### Missing games are zeros

If a system has game scores `1.0` and `0.5` but the evaluated split contains
three games, the benchmark score is:

\[
B=\frac{1.0+0.5+0}{3}=0.5
\]

The local helper makes this explicit with
`benchmark_score([1.0, 0.5], total_games=3)`.

## What consumes an action

The documentation defines an action as a discrete interaction with the
environment. Reasoning, local Python execution, simulator search, perception,
LLM tool calls, and a retry that never reaches the environment do not count.

The pinned toolkit's scorecard bookkeeping gives the more operational rule:

- every accepted `ACTION1` through `ACTION7` command increments the play's
  cumulative action count;
- a `RESET` while a play is active increments both reset count and action count;
- the initial reset that creates a new play initializes its action count at
  zero;
- per-level actions are differences in the cumulative counter at level
  transitions, so actions and charged resets since the prior transition belong
  to the current level; and
- actions spent on an unfinished final level remain recorded, but that level
  scores zero.

A command need not visibly alter pixels to be costly. Local “retry” language in
the methodology should not be read as permission to resend environment actions
for free. The safe accounting boundary is the authoritative environment client.

There is no published universal Kaggle action budget. Three distinct concepts
are often conflated:

| Number/policy | Actual scope |
|---|---|
| Starter `MAX_ACTIONS = 80` | Editable client anti-loop guard |
| `ceil(5 × H)` per level | ARC Prize Foundation frontier-model benchmarking protocol |
| `GAME_OVER` from max actions | A game-specific terminal condition |

None of these establishes a global 80-action or \(5H\) Kaggle limit.

## Exact v0.9.9 aggregation behavior

The relevant upstream behavior is:

1. `add_level` computes `(baseline/actions)^2 * 100`, caps it at `115.0`,
   and assigns zero to incomplete levels.
2. `to_score` weights by the stored 1-indexed level number.
3. `to_score` computes the maximum score from weights whose level score is
   positive.
4. It returns the smaller of weighted efficiency and that completion maximum.
5. An environment with no levels scores zero.
6. A scorecard averages environment scores arithmetically.
7. Outside competition mode, if an environment contains multiple plays,
   `EnvironmentScoreList.score` exposes the maximum run score. Kaggle competition
   mode prohibits multiple `make` calls per environment, so this best-run
   behavior is unavailable there.

The official code stores percentages internally; multiplying every level score,
weighted efficiency, and completion cap by 100 leaves the normalized formulas
above unchanged.

## Local reference API

`src/arcworld/scoring.py` intentionally has no NumPy, SDK, or Pydantic
dependency.

| Function | Purpose |
|---|---|
| `level_score(H, A, completed=...)` | Compute one capped level score |
| `completion_cap(flags, level_indices=...)` | Compute the weighted completion fraction |
| `game_score(level_scores, level_indices=...)` | Reproduce v0.9.9 aggregation from level scores |
| `score_game(baselines, actions, flags, level_indices=...)` | Compute a game directly from raw aligned values |
| `benchmark_score(game_scores, total_games=...)` | Average games, optionally zero-padding omissions |

Equivalent `rhae_*` aliases are available for explicit call sites. Inputs are
validated as finite and non-negative; level indices must be positive integers.
The helper accepts a zero action count and returns zero, matching the reference
source's edge behavior.

Reference vectors:

```python
from arcworld.scoring import benchmark_score, game_score, level_score

assert level_score(10, 10) == 1.0
assert level_score(10, 20) == 0.25
assert level_score(10, 8) == 1.15
assert level_score(10, 1, completed=False) == 0.0

assert game_score([1.0, 1.0, 1.0, 1.0, 0.0]) == 10 / 15
assert game_score([1.15, 1.15, 0.0]) == 0.5
assert benchmark_score([1.0, 0.5, 0.0]) == 0.5
assert benchmark_score([1.0, 0.5], total_games=3) == 0.5
```

## Stale formula warning

The current Kaggle Data prose has presented:

\[
\min(H/A,1)^2
\]

That caps each level at 1.0 and is **not** the current v0.9.9 execution path.
Current ARC Prize methodology and pinned source instead calculate
\((H/A)^2\) and cap the result at **1.15**. The game-level completion cap still
limits the final score to 1.0. Until the evaluation package changes, experiments
and local dashboards should use v0.9.9 behavior and record the exact toolkit
version with every score.

## Optimization consequences

- A twofold action overrun is not a mild penalty; it removes 75% of that level's
  efficiency credit.
- Later levels dominate. Learning a transferable rule is more valuable than
  over-optimizing a tutorial after the rule is understood.
- Completion is still essential. Fast early levels cannot compensate for an
  unsolved late level beyond the weighted completion cap.
- Simulator search, replay verification, object extraction, and LLM reasoning
  are free in RHAE terms as long as they remain local. Spend compute to avoid
  uncertain real actions.
- A queued plan should stop at the first model mismatch. Continuing a disproven
  plan both damages evidence quality and pays the quadratic action penalty.
- Reset is not free after play begins. The controller should model death risk,
  reversibility, and expected information gain before probing.
- Human baseline values can be useful to the scoring harness but must not be
  exposed to the tested reasoning model; doing so leaks benchmark metadata.

## Reporting checklist

Every benchmark claim should include:

- exact split: 25 Public Demo, 55 hidden public-LB, 55 Semi-Private verified, or
  55 private-LB;
- toolkit/scoring commit;
- model and weights;
- harness and available tools;
- reasoning effort and compute budget;
- run count and whether the result is pass@1, mean, or best-of-\(k\);
- selection rule and any per-game reruns;
- number of games and unplayed-game handling;
- timestamp; and
- primary source or immutable local scorecard.

The visible Kaggle leaderboard truncates scores to two decimals at this
snapshot. Store full-precision local values; do not reconstruct detailed
per-game performance from a truncated leaderboard number.
