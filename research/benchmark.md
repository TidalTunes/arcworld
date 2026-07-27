# ARC-AGI-3 benchmark and Kaggle challenge

**Research snapshot:** 2026-07-26
**Live Kaggle capture:** 2026-07-27 06:22:44 UTC
(2026-07-26 23:22:44 PDT)
**Competition:** `arc-prize-2026-arc-agi-3`, Kaggle competition ID `133468`
**Toolkit/scoring reference:** `arc-agi` v0.9.9, commit
[`f12822c`](https://github.com/arcprize/ARC-AGI/commit/f12822c4d550121c35a275008d964afbbed47d2f)

Competition rules, metadata, and leaderboards are mutable. Every volatile value
below carries a timestamp. Source provenance and machine-readable conflict notes
are in [`sources-rules.yaml`](sources-rules.yaml); the scoring derivation is in
[`scoring.md`](scoring.md).

## The split distinction that must never be collapsed

ARC-AGI-3 has 135 games in the current official taxonomy, but the Kaggle
competition evaluates only the 110 hidden games.

| Regime | Games | Visibility | Purpose | Score comparability |
|---|---:|---|---|---|
| **Public Demo** | **25** | Downloadable and playable during development | Instrumentation, ablations, debugging, and public demonstrations | Development evidence only |
| **Kaggle Public Leaderboard** | **55 hidden games** | Executed only inside the Kaggle evaluation gateway | Live competition ranking and milestone ranking | Comparable only under the Kaggle harness |
| **Kaggle Private Leaderboard** | **55 hidden games** | Withheld until final evaluation and verification | Final winner ranking | The binding final result |

The technical report calls the three groups **Public Demo**,
**Semi-Private**, and **Fully Private**. Kaggle describes its 110 evaluation
games as equal Public- and Private-Leaderboard halves. These labels appear to
align as 25 + 55 + 55, but “Public Leaderboard” does **not** mean the game files
are public. It means scores on those 55 hidden games are shown during the
competition.

Likewise, the ARC Prize Foundation's verified frontier-model score on 55
Semi-Private games and a Kaggle submission's score are not interchangeable:
the model, tool harness, budget, and selection protocol differ even if the
environment set aligns.

## What the benchmark measures

ARC-AGI-3 replaces ARC-AGI-1/2's static input-output transformations with small
interactive games. The player receives no natural-language rules and must infer
the game's objects, dynamics, controls, level goal, and relevant hidden state by
acting. Games contain multiple increasingly difficult levels. Performance
combines:

1. **completion** — which levels and games were solved; and
2. **action efficiency** — actions used relative to first-time human baselines.

The official metric is Relative Human Action Efficiency (RHAE). Later levels
have larger weights. An unplayed game scores zero in competition mode. See
[`scoring.md`](scoring.md) for the exact formula and executable reference
functions.

## Environment contract

### Observation

- A frame is at most 64 × 64 cells.
- Each cell is an integer color in `0..15`.
- Coordinates use `(x, y)`, with `(0, 0)` at the upper-left.
- A response may contain multiple frames representing an animation; the last
  frame is the current visible state, but preceding frames can contain causal
  evidence.
- Metadata includes the available action subset, state, completed-level count,
  and identifiers. Benchmark identifiers and human baselines are evaluation
  metadata and should not be shown to the game-playing model.

### Actions

Every game exposes only the relevant subset.

| API action | Stable interface meaning |
|---|---|
| `RESET` | Start or reset play; restricted to a level reset in competition mode |
| `ACTION1` | Up |
| `ACTION2` | Down |
| `ACTION3` | Left |
| `ACTION4` | Right |
| `ACTION5` | Game-specific interaction |
| `ACTION6(x, y)` | Coordinate interaction, with each coordinate in `0..63` |
| `ACTION7` | Undo where supported |

The semantics of `ACTION5`, the target or consequence of `ACTION6`, and whether
an action changes the visible frame are game-specific. A no-op action is still
valuable evidence and, when accepted by the environment, still consumes an
action.

### States

| State | Meaning |
|---|---|
| `NOT_FINISHED` | The current play is active |
| `WIN` | The game objective and required levels were completed |
| `GAME_OVER` | The play terminated because of a game condition or game-specific action limit |

After `GAME_OVER`, only a reset is legal. There is no published universal
Kaggle action limit. The starter's `MAX_ACTIONS = 80` is an editable anti-loop
guard, and the Foundation's `ceil(5 × human_baseline)` evaluation budget is a
separate verified-model protocol, not a Kaggle rule.

## The 25 Public Demo games

These base IDs are the only games in the initial development scope. Experiments
should pin the full versioned IDs reported by the
[live catalog](https://arcprize.org/api/games); the catalog and exact local
versions are audited separately in [`sdk_and_games.md`](sdk_and_games.md).

| | | | | |
|---|---|---|---|---|
| `AR25` | `FT09` | `LP85` | `R11L` | `S5I5` |
| `VC33` | `SB26` | `RE86` | `SP80` | `CN04` |
| `TR87` | `DC22` | `M0R0` | `WA30` | `KA59` |
| `SU15` | `SK48` | `TN36` | `LS20` | `TU93` |
| `LF52` | `CD82` | `BP35` | `G50T` | `SC25` |

Official documentation says three games can be accessed anonymously; a free ARC
API key unlocks the rest of the public catalog. The public environment files can
also be used locally through the toolkit. This repository must not commit those
binaries or leak a game ID, source file, baseline, prior solution, or internet
access into a tested agent's context.

## Direct API and toolkit flow

The public service base is `https://three.arcprize.org`. A direct play session
uses:

1. `GET /api/games`
2. `POST /api/scorecard/open`
3. `POST /api/cmd/RESET`
4. `POST /api/cmd/ACTION1` through `POST /api/cmd/ACTION7`
5. `POST /api/scorecard/close`

The toolkit is the preferred client. Kaggle redirects the same interaction
contract through the local gateway at `http://gateway:8001`.

Competition mode is mandatory on Kaggle and imposes all of the following:

- environments are accessed only through the API;
- all available environments are scored, including unplayed ones;
- only level resets are permitted; attempted game resets become level resets;
- `make` may be called only once for each environment;
- only one scorecard may be opened; and
- an in-flight scorecard cannot be queried for its score.

These constraints rule out selecting the best of repeated hidden-game attempts.
They also make a lossless local event log essential: the agent cannot ask the
server for the developing score as a substitute for its own state tracking.

## Kaggle execution and submission contract

This is a notebook-only Code Competition. The starter follows a listen-and-serve
protocol: the notebook starts the agent, the gateway performs the hidden
evaluation, and the gateway produces the required `submission.parquet`.
Kaggle first performs a validation phase and then reruns accepted code against
the hidden evaluation.

Binding/live settings captured on 2026-07-27 06:22:44 UTC:

| Setting | Captured value |
|---|---:|
| Required output | `submission.parquet` |
| Notebook CPU runtime | 540 minutes |
| Notebook GPU runtime | 540 minutes |
| Internet | Disabled during scored execution |
| Submission artifact limit | 20,480 MB |
| Daily submissions | 1 |
| Final submissions selected | 2 |
| Maximum team size | 8 |
| Score display truncation | 2 decimal places |
| Submission type | Kaggle notebook only |
| Identity verification | Required |
| Final leaderboard | Withheld until verification |

Publicly available external data and pretrained models are allowed subject to
the competition rules and reasonable accessibility requirements. They must be
available offline to the notebook. In particular, **the OpenAI API cannot be
called during the final scored Kaggle run** because internet access is disabled.
An OpenAI model can be used for development or to generate an offline artifact,
but a competitive submission needs a local inference path or a non-LLM fallback.

The binding rules also prohibit private code/data sharing outside a registered
team. Public sharing should use Kaggle's public competition channels. Entrants
must use one Kaggle account, satisfy age and jurisdiction eligibility, comply
with team rules, and complete identity verification. Consult the live
[official rules](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3/rules)
before any submission; this summary is an engineering record, not a substitute
for the legal terms.

## Timeline

All competition deadlines below are UTC and were captured on 2026-07-27. UTC is
canonical because the entry cutoff has a live-source conflict.

| Event | Date/time | Status or caveat |
|---|---|---|
| Competition enabled | 2026-03-25 17:38:23.913 UTC | Live metadata |
| Milestone 1 cutoff | 2026-06-30 23:59 UTC | Passed |
| Milestone 2 cutoff | 2026-09-30 23:59 UTC | Upcoming at snapshot |
| New entrant cutoff | **2026-10-26 11:59 UTC** in backend metadata | Visible Timeline says 23:59 UTC; use the earlier time |
| Team merger cutoff | 2026-10-26 23:59 UTC | Live metadata and visible Timeline agree |
| Kernel publishing disabled | 2026-10-26 23:59 UTC | Live metadata |
| Final submission deadline | 2026-11-02 23:59 UTC | Live metadata |
| Winner announcement | 2026-12-04 | ARC Prize schedule; no time published |

The separate ARC Prize paper/research track has a 2026-11-08 date. That is not
an extension of Kaggle's 2026-11-02 submission deadline.

## Prizes and winner obligations

The live Kaggle reward is **$850,000**:

| Pool | Distribution |
|---|---|
| Final Private Leaderboard, $75,000 | $40,000 / $15,000 / $10,000 / $5,000 / $5,000 |
| Milestone 1, $37,500 | $25,000 / $7,500 / $5,000 |
| Milestone 2, $37,500 | $25,000 / $7,500 / $5,000 |
| 100% bonus, $700,000 | Conditional; among the first five qualifying 100% solutions: $350,000 / $175,000 / $70,000 / $70,000 / $35,000 |

The Private Leaderboard determines final placement. The competition rules use
submission time as the tie-breaker. Prize-winning teams must provide the full
training and inference system, documentation sufficient to reproduce it, and
reasonable technical cooperation/interviews for verification.

Prize eligibility includes an open-source obligation. The Kaggle rules refer to
CC BY 4.0 for the winning submission and require the system/model/weights to
satisfy the Open Source Initiative's Open Source AI definition/checklist. The
broader ARC Prize 2026 page separately asks for submitter-authored code and
methods under CC0 or MIT-0. To satisfy the stricter practical intersection,
release original code under MIT-0 or CC0, publish all required weights and
training/inference artifacts, and mirror the exact competition code publicly on
Kaggle before relying on prize eligibility.

## Live Public Leaderboard snapshot

The following is the hidden **55-game Kaggle Public Leaderboard**, not a result
on the 25 Public Demo games.

**Captured:** 2026-07-27 06:22:44 UTC

| Rank | Team/user | Public score (%) |
|---:|---|---:|
| 1 | YUTO KOJIMA | 1.86 |
| 2 | Tecnod8.AI | 1.61 |
| 3 | DhanaLakshmiMalla | 1.60 |
| 4 | ippeiogawa | 1.58 |
| 5 | Yuchen20 | 1.58 |

At the same capture time, Kaggle's live metadata reported:

| Volatile field | Value |
|---|---:|
| Teams | 1,931 |
| Competitors | 2,068 |
| Submissions | 17,838 |
| Joined users | 10,386 |
| Leaderboard percentage | 50 |

These are Kaggle's own overlapping metadata categories and must not be added
together. Scores are displayed/truncated to two decimal places. The top-five
snapshot says nothing about the unreleased Private Leaderboard.

For comparison only, ARC Prize reported Claude Opus 5 High at 30.16% under its
[verified](https://arcprize.org/policy) 55-game Semi-Private model-evaluation
protocol on 2026-07-24. That is a different submitted system and harness. Its
published per-game Public Demo result is also a separate regime. Do not infer
that a 30.16% model automatically produces a 30.16% Kaggle notebook.

## Official inconsistencies and scope traps

Where official sources disagree, this project records both claims and applies
the operational precedence shown in the final column.

| Topic | Conflicting official claims | Project interpretation |
|---|---|---|
| Per-level speed cap | Current scoring docs and v0.9.9 source cap `(H/A)^2` at **1.15**; Kaggle Data prose still presents `min(H/A, 1)^2` | Use v0.9.9/server behavior: 1.15 per level, then completion-cap the game |
| Daily submissions | Binding rules/live metadata say **1/day**; official starter README says **5/day** | Plan for 1/day |
| Entry cutoff | Backend metadata says **2026-10-26 11:59 UTC**; visible Timeline says **23:59 UTC** | Enter by the earlier 11:59 UTC cutoff |
| Milestone split | Kaggle says $25k/$7.5k/$5k per milestone; ARC track page says $25k/$10k/$2.5k | Kaggle distribution is binding for this competition |
| $700k bonus | Kaggle splits a conditional pool among the first five qualifying 100% teams; ARC track page says the first eligible 100% system receives the pool, with rollover language | Follow the live Kaggle rules |
| “Guaranteed” milestones | ARC track prose calls milestones guaranteed; Kaggle metadata/rules attach eligibility and verification conditions | Treat payment as conditional on the binding rules |
| Winner license | Kaggle names CC BY 4.0 plus Open Source AI requirements; the general 2026 page recommends CC0/MIT-0 for entrant-authored work | Use MIT-0/CC0 for original code and meet all model/weight disclosure requirements |
| Compute limit | An ARC track page still says Kaggle hardware will be announced; live Kaggle metadata sets **540 minutes** for CPU and GPU notebooks | Engineer for the live 9-hour limit |
| Action budget | Starter defaults to 80; Foundation benchmarking uses `ceil(5H)` per level; Kaggle publishes no universal limit | Treat both as harness policies, not Kaggle rules; obey each game's terminal behavior |
| Public-score reporting | The technical report says the official model leaderboard will not report Public Demo scores; later official result pages publish Public Demo rows/results | Treat this as policy drift and label the evaluated split every time |
| “Public” terminology | Public Demo games are downloadable; Public-Leaderboard games are hidden | Always write **25 Public Demo**, **55 hidden public-LB**, or **55 private-LB** |
| November dates | Kaggle ends 2026-11-02; the research/paper track lists 2026-11-08 | Separate tracks, not a deadline extension |

Operational precedence for this repository is:

1. live Kaggle legal rules and competition metadata for eligibility, submissions,
   deadlines, compute, and prizes;
2. the scoring server/current pinned toolkit source for executed metric behavior;
3. current ARC-AGI-3 documentation;
4. Kaggle overview prose;
5. starter README and general ARC Prize track pages.

Any competition release can change this ordering in practice. Re-audit before a
milestone or final submission.

## Implications for this research suite

- Use the 25 Public Demo games to validate infrastructure, not to claim hidden
  generalization.
- Report every score with split, model, harness, reasoning effort, run count,
  selection rule, date, and source.
- Preserve raw animation frames and no-op transitions; both can reveal mechanics
  that a last-frame-only object model misses.
- Keep real environment actions distinct from simulated planning steps and LLM
  calls. Only the former affect RHAE.
- Bias long committed plans toward replay-certified simulators because every
  mistaken real action is quadratically expensive.
- Keep inference offline-compatible from the beginning. A development agent
  that requires an external API cannot be submitted unchanged.
- Hide game identity and benchmark lore from the reasoning model. It should see
  only observations, available actions, its own evidence history, and tool
  contracts.
- Re-run the live-source audit before each Kaggle submission window; leaderboard
  positions, participation counts, and potentially the operational rules can
  change.

## Primary references

- [Kaggle competition](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3)
- [Kaggle rules](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3/rules)
- [Kaggle data description](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3/data)
- [Kaggle code requirements](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3/overview/code-requirements)
- [ARC Prize 2026 ARC-AGI-3 track](https://arcprize.org/competitions/2026/arc-agi-3)
- [ARC-AGI-3 technical report](https://arcprize.org/media/ARC_AGI_3_Technical_Report.pdf)
- [ARC Prize verified testing policy](https://arcprize.org/policy)
- [ARC-AGI-3 documentation](https://docs.arcprize.org/)
- [Hosted Public Demo catalog](https://arcprize.org/api/games)
- [Toolkit repository](https://github.com/arcprize/ARC-AGI)
- [Official Kaggle starter](https://github.com/arcprize/ARC-AGI-3-Kaggle-Starter)
