# ARCWorld evaluation protocol

**Protocol snapshot:** 2026-07-26
**Status:** normative for reported experiments
**Related:** [architecture](architecture.md),
[strategy landscape](landscape.md), and
[ARC Prize testing policy](https://arcprize.org/policy)

## Purpose

This protocol is designed to answer one question without public-game
self-deception:

> Does explicit uncertainty over executable rules and perception ontologies
> improve first-contact learning on unseen interactive worlds?

The protocol separates development, blind synthetic evaluation, official
Semi-Private evaluation, and Kaggle evaluation. It makes pass@1 the headline
statistic, forbids identity/lore leakage, and records enough provenance to
reproduce both successes and failures.

## Non-comparable evaluation lanes

Results remain in their lane. They are never merged into one score table.

| Lane | Data | Permitted purpose | Claim it can support |
|---|---|---|---|
| Unit and regression | Authored toy transitions and tiny worlds | Correctness and debugging | Implementation works on specified cases |
| Public development | 25 ARC-AGI-3 Public Demo games | Instrumentation, qualitative analysis, ablation development | Performance on exposed public games only |
| Synthetic blind | Sealed generator families and seeds | Controlled first-contact generalization | Transfer within the declared synthetic distribution |
| Official verified | ARC Prize Semi-Private set | Foundation-run verification | Official verified capability under its protocol |
| Kaggle Public LB | Hidden competition subset | Iterative competition feedback | Public-leaderboard performance only |
| Kaggle Private LB | Fully hidden final subset | Final competition evaluation | Competition result on the final hidden set |

The benchmark partitions and policy are tracked in the source registries. The
[Kaggle data page](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3/data)
states that 110 unseen competition games are split between Public and Private
leaderboards. Public Demo scores, including near-99% harness claims, are not
evidence of performance on those games.

## Claim checklist

Every reported aggregate must name:

- evaluation lane and exact dataset/package version;
- date and repository commit;
- harness configuration hash;
- model ID, provider, checkpoint, quantization, and reasoning effort;
- prompt/context-template hashes;
- action budget and timeout policy;
- run count and predeclared seed schedule;
- selection rule: pass@1, mean of all runs, or explicitly labeled best@\(k\);
- scorer and human-baseline version;
- hardware, wall time, tokens, and monetary cost;
- number and treatment of failures, timeouts, and invalid runs;
- whether any component or weight had seen the evaluated games.

If any field is unknown, label it unknown rather than silently assuming a
default.

## Strict pass@1

`pass@1` means:

1. the code, prompts, model, reasoning effort, budgets, and configuration are
   frozen before the evaluated world identity or seed is revealed;
2. the agent starts with a fresh process, empty model workspace, and no prior
   conversation for that game;
3. exactly one authoritative environment session is created;
4. no human intervenes after the initial run command;
5. every legal action, reset, death, timeout, and failed hypothesis remains in
   the result;
6. the first complete playthrough is the reported outcome;
7. a crash or exhausted budget scores as that run's actual incomplete result,
   not as a reason to silently retry.

Infrastructure failures may be declared invalid only under a prewritten rule
that is independent of game progress—for example, the environment process
never returned its initial observation. The failed artifact is retained, the
reason is reported, and any rerun is labeled a rerun.

### Repeated runs

Repeated experiments are useful for variance, but they do not replace pass@1:

- run every predeclared seed or model-sampling condition;
- report all-run mean, median, dispersion, and each trajectory;
- use paired seeds/configurations across ablations;
- do not stop when a desired score appears;
- report `best@k` only as a secondary oracle/robustness statistic;
- state whether selection occurred per benchmark, game, or level;
- identify conditional reruns, such as “rerun games below 80% and retain the
  better score.”

Conditional selection protocols such as Schema's fallback result are recorded
for comparison but never labeled pass@1.

## Blindness and anti-leakage contract

### Trusted runner may know

The evaluator may retain identity and scoring data outside model context to:

- open the environment;
- enforce action and time budgets;
- compute scores after the run;
- group paired experimental results;
- diagnose infrastructure.

### Tested agent may know

The game-playing reasoner and generated programs receive only:

- sanitized frames and their exact pixel arrays;
- current advertised actions and action tool contracts;
- status/progress fields returned as part of normal interaction;
- their own complete sanitized action history;
- their own generated artifacts and verification results;
- generic algorithms and helpers declared before evaluation.

### Tested agent may not know

- game ID, GUID, filename, path, or stable benchmark-specific identifier;
- “ARC-AGI-3,” game descriptions, public game nicknames, or benchmark lore;
- human baselines, expected number of levels, solutions, walkthroughs, or score;
- environment implementation, source maps, metadata files, or package assets;
- replays from another agent or an earlier attempt at the evaluated game;
- internet, web search, repository search outside its sandbox, or a second
  environment client;
- messages or memory from a previously evaluated game unless the experiment is
  explicitly a separately labeled cross-game continual-learning treatment.

Even Public Demo runs use opaque episode IDs. Redaction is tested by capturing
the exact reasoner request and asserting that forbidden identifiers and paths
are absent.

## Pre-run manifest

Before a scored run, the runner writes a read-only manifest:

```yaml
protocol_version:
repository_commit:
working_tree_clean:
evaluation_lane:
dataset_or_generator_digest:
opaque_episode_schedule_digest:
harness_config_digest:
model:
  provider:
  id_or_checkpoint:
  reasoning_effort:
  quantization:
  sampling:
prompt_digests:
budgets:
  environment_actions:
  resets:
  wall_seconds:
  model_tokens_or_calls:
  simulated_nodes:
scorer_version:
external_network_allowed:
manual_intervention_allowed: false
selection_rule: pass_at_1
```

For development on a dirty tree, archive a content digest of every source and
configuration file. Competition or publication runs should use a committed
tree.

## Run lifecycle

1. **Freeze.** Write the manifest and derive an opaque episode token.
2. **Isolate.** Start a fresh process/container and empty per-game workspace.
3. **Redact.** Open the environment in the trusted runner and serialize the
   initial observation with identity fields removed.
4. **Record first.** Persist the initial observation before invoking a model.
5. **Play.** For every action, atomically record request, response, action,
   predicted successor, actual successor, diffs, and model state.
6. **Enforce budgets.** The runner, not the reasoner, stops the run at declared
   limits.
7. **Finalize.** Seal event and artifact hashes before computing the score.
8. **Score.** Use the pinned official scorer or a versioned local replica and
   record its exact version.
9. **Export.** Produce a machine-readable result and a human-readable replay.
10. **Audit.** Run leakage, integrity, and provenance checks.

No dashboard button may modify a scored run. Evaluation mode is read-only.

## Scoring

Use the official package/scorer version appropriate to the evaluation date.
Do not embed a remembered score formula as the sole authority: human baselines,
caps, and methodology can change. Record both the official aggregate and raw
ingredients so results can be rescored:

- levels reached and completed;
- real actions per level;
- resets and game-over events;
- status transitions;
- human-baseline/scorer digest;
- per-level and per-game score returned by the scorer.

The tested reasoner does not receive the human action baseline or live score.
Internal planning may optimize generic real-action efficiency and survival, not
private scoring metadata.

## Synthetic blind holdouts

Synthetic worlds provide repeatable hidden tests before Kaggle submissions.
They are not a substitute for ARC-AGI-3; claims must name their distribution.

### Dataset construction

Maintain three layers:

1. **Visible fixtures:** tiny deterministic worlds used by unit tests.
2. **Development generators:** documented families whose seeds are visible.
3. **Sealed holdouts:** held-out families, parameters, compositions, and seeds
   unavailable to the agent and to day-to-day harness tuning.

A holdout manifest contains only hashes until evaluation completes. Ideally, a
different contributor authors or seals it. At minimum:

- commit generator code before drawing evaluation seeds;
- derive seeds from a committed future-independent value or store them
  encrypted/sealed;
- keep generator source outside the tested agent sandbox;
- prohibit inspecting failed holdout source during the experiment series;
- rotate holdout families after a major design cycle, not after each poor run;
- publish the reveal and every result after the series closes.

### Required mechanic families

The blind suite should cover combinations, not only isolated primitives:

- object motion, collision, pushing, carrying, and blocking;
- switches, resources, counters, orientation, and color/shape transformations;
- containment, occlusion, part/whole ambiguity, and repeated motifs;
- coordinate clicks and non-coordinate actions;
- irreversible traps, reset decisions, and delayed consequences;
- level-to-level rule accumulation;
- visually identical states with history-dependent latent state;
- irrelevant animation or decorative pixels around a correct causal mechanism;
- changing action availability and sparse/no-effect actions;
- goals that must be inferred from progress rather than supplied.

Each family includes positive and adversarial cases that break superficial
analogies.

### Generator leakage controls

A model must not see generator class names, mechanic tags, parameter names, or
source. Harness algorithms may use generic grid and action abstractions but may
not dispatch on hidden family IDs. The report lists family-level results only
after evaluation.

## Baselines

At minimum, every blind study includes:

1. **Random legal:** uniformly sampled advertised primitive actions and
   predeclared click distribution.
2. **Coverage graph:** transition graph seeking untested state-action pairs.
3. **Lossless-memory reasoner:** full event log and code search, without an
   executable world-model requirement.
4. **Single-model exact replay:** a Schema-like active simulator, full replay
   gate, one planner, and mismatch cancellation.
5. **Full ARCWorld treatment:** active model, weighted shadows, competing
   ontologies, risk-aware probes, latent-state option, and planner portfolio.

Use the same base reasoner, model effort, budgets, action candidate generator,
and environment seeds wherever the treatment permits. If a baseline cannot use
an element by definition, record that difference.

## Ablation matrix

### Core factorial

The primary causal study is a paired \(2 \times 2 \times 2\) design:

| Factor | Off | On |
|---|---|---|
| Version space | one promoted replay-consistent model; prior overwritten | active model plus weighted replay-consistent shadows |
| Active probing | coverage/salience action selection | weighted disagreement/information gain adjusted for risk and cost |
| Ontology alternatives | one fixed component parser | competing background/connectivity/part-whole ontologies |

Run all eight cells on the same sealed seed schedule. This isolates main effects
and interactions better than adding components only in a staircase.

### Conditional component studies

| Study | Control | Treatment | Primary diagnostic |
|---|---|---|---|
| Latent state | observable-Markov models only | bounded latent automaton after contradiction test | repeated-state prediction accuracy |
| Verification | exact-only accept/reject | semantic shadows plus exact promotion | recovery and unsafe-plan rate |
| Formalization timing | executable model required immediately | textual/partial theory until trigger, exact before long plans | actions, tokens, completion |
| Planning | bounded BFS | planner portfolio | solved planning instances per simulated-node budget |
| CEGAR | fixed abstraction | counterexample-guided refinement | spurious-plan rate and refinements |
| Memory | derived summary only | immutable log plus provenance-linked semantic memory | recovery after old evidence becomes relevant |
| Macro induction | primitive plans only | verified parameterized macros | real actions unchanged; tokens and planning time |
| Reasoner | deterministic/no-LLM baseline | declared local or OpenAI development model | marginal value and cost |

Latent-state experiments should include worlds that are provably observable as
negative controls; otherwise the treatment can win by adding unnecessary
complexity.

### Predeclared comparisons

Before opening a holdout, state:

- primary outcome and any acceptable tradeoff;
- paired statistical test or interval;
- minimum sample size or fixed seed count;
- maximum budgets;
- whether a tie favors the simpler system;
- stopping rule;
- correction for multiple primary comparisons, if any.

Do not choose the winning metric after seeing the results.

## Metrics

### Benchmark outcomes

- official-style total score, when applicable;
- games and levels completed;
- fraction of environments with any level progress;
- real actions and resets per completed level;
- terminal failures and action-budget exhaustion.

### World-model quality

- exact next-observation accuracy;
- status and progress accuracy;
- object and relation precision/recall or deterministic delta agreement;
- calibration of hypothesis weights and predicted death risk;
- number of replay-consistent shadows over time;
- posterior entropy before and after probes;
- proportion of surprises attributed to ontology, rule, renderer, or latent
  state;
- active-model lifetime and promotion count;
- counterexample recovery latency in real actions and model calls.

### Exploration and planning

- information gain per real action;
- no-effect and repeated-equivalent actions;
- irreversible mistakes and avoidable deaths;
- simulated nodes, depth, and wall time;
- abstract plans rejected by exact simulation;
- planner selection and success by instance;
- queued actions cancelled after divergence;
- real-to-simulated action ratio.

### Compute and cost

- input, cached, output, and reasoning tokens when available;
- model calls, retries, timeouts, and invalid responses;
- retail API cost for development runs;
- local model checkpoint, quantization, GPU model, peak memory, and energy proxy
  if available;
- CPU time, GPU time, and wall time;
- generated-code executions and sandbox terminations.

### Researcher usability

- time to reproduce a run from its manifest;
- percentage of artifacts with complete provenance;
- GUI load/render latency for long traces;
- number of manual steps required in development and zero permitted in scored
  execution.

## Statistical reporting

Games are the primary paired unit for benchmark-level comparisons. Report:

- per-game results, not only the mean;
- paired differences between treatments;
- bootstrap confidence intervals over games or generator instances;
- run-to-run variance separately from game-to-game variance;
- completion and action efficiency together, since one can improve by
  sacrificing the other;
- median and tail metrics for recovery latency and cost;
- treatment failures and crashes in the denominator.

Twenty-five public games are too few and too exposed for strong generalization
claims. Synthetic studies should use enough sealed instances across enough
families to expose variance, with the count fixed before evaluation.

## OpenAI and offline profiles

### Development profile

- OpenAI API is permitted as the only external service.
- Model ID and reasoning effort are pinned.
- Request and response hashes, usage, latency, and cost are recorded.
- Sanitization occurs before any request leaves the process.
- The run is labeled networked development.

### Offline/Kaggle profile

- network access is disabled;
- API keys are absent;
- only bundled local checkpoints or deterministic agents are used;
- installation and model assets are prepared before evaluation;
- the same evidence, model, verifier, and planner contracts remain in force.

Scores from these profiles are separate model/system conditions.

## Integrity and invalidation checks

A scored run fails audit if:

- a forbidden identifier or lore string appears in reasoner context;
- generated code obtains file, process, socket, clock, or environment-client
  capabilities;
- more than one real environment session is used;
- the event chain has a missing or modified transition;
- a promoted model lacks a successful complete replay report;
- an action is omitted from accounting;
- a human changes state, prompt, theory, or plan after launch;
- a retry or selected run is labeled pass@1;
- scorer, model, prompts, or harness configuration cannot be identified.

Keep failed-audit artifacts, label them invalid, and explain the failure. Do not
delete inconvenient runs.

## Result record

Each run exports at least:

```text
manifest.yaml
result.json
events.sqlite (or immutable event stream)
artifact_manifest.json
model revisions and verification reports
plans and simulated rollouts
reasoner request/response metadata
metrics.jsonl
replay/index.html or GUI-loadable bundle
audit.json
```

Private environment data and competition outputs remain local and are never
committed. A publishable result can include hashes and aggregated metrics
without leaking hidden frames.

## Decision standard

The version-space hypothesis is supported only when the treatment improves a
predeclared primary outcome on synthetic blind or hidden evaluation while
respecting the same real-action and model-compute budgets. It is weakened if:

- gains appear only on the 25 public games;
- pass@1 does not improve but best@\(k\) does;
- model strength explains the gain under controlled ablation;
- shadow maintenance consumes more actions or compute without reducing
  surprise or improving completion;
- ontology or latent-state machinery overfits observable control worlds.

Negative results are part of the suite's purpose and should remain in the
progress record.
