# ARC-AGI-3 agent strategy landscape

**Research snapshot:** 2026-07-26
**Scope:** ARC-AGI-3 interactive-agent results and architectures. ARC-AGI-1/2
results are excluded unless needed for context.
**Evidence rule:** Scores from the official verified leaderboard, the Kaggle
competition, and the 25-game Public Demo are reported in separate regimes.
They are not directly interchangeable.

## Executive conclusion

The initially proposed architecture—object-centric frame grounding, an
LLM-written Python `step(state, action)` simulator, complete-history replay
verification, planning inside the simulator, queued real actions, and
abort/revise on the first mismatch—has already been implemented very closely by
[Schema](https://schema-harness.github.io/). It also overlaps substantially with
[Executable World Models](https://arxiv.org/abs/2605.05138) and
[OPINE-World](https://arxiv.org/abs/2607.01531).

Accordingly, the project should implement this loop as a strong baseline but
should not present the loop itself as novel. The most defensible **novelty
hypothesis**, pending a systematic literature review and blind evaluation, is:

> A risk-aware, actively probed version space of executable world models whose
> object ontologies and latent state can also be revised will generalize better
> than a single replay-consistent simulator.

This is a research hypothesis, not a proven novelty or performance claim.

The second major conclusion is that Public Demo scores are a weak proxy for the
Kaggle challenge. Public harnesses now report scores near 99%, while the first
Kaggle milestone winner reported 1.21% on hidden games. The project must optimize
for first-contact transfer and should treat public-game saturation as a
development diagnostic rather than the headline result.

## Evidence regimes

### 1. Official verified model evaluation

The official verified leaderboard evaluates frontier models on 55 Semi-Private
environments. ARC Prize normally uses one run, a $10,000 runtime cap, and a
minimal model configuration without Python, web search, or other client-side
tools. These scores measure the model under the Foundation's protocol, not a
research harness. See the
[official testing policy](https://arcprize.org/policy).

As of this snapshot:

| Model and effort | Semi-Private score | Public Demo score | Notes |
|---|---:|---:|---|
| Claude Opus 5 High | **30.16%** | approximately **40.68%**, derived from the 25 published per-game rows | Highest official verified ARC-AGI-3 score as of 2026-07-24 |
| GPT-5.6 Sol Max | **7.78%** | **13.33%** | First verified model reported to win a public game |
| GPT-5.6 Terra Max | **0.80%** | not used here | Much weaker than Sol |
| GPT-5.6 Luna Max | **0.18%** | not used here | Unsuitable as the only high-level reasoner |

Sources: [Claude Opus 5 scorecard](https://arcprize.org/results/anthropic-claude-opus-5)
and [GPT-5.6 scorecard](https://arcprize.org/results/openai-gpt-5-6).

The official policy currently states that the 25-game Public Demo is harder on
average than the Semi-Private set and treats the two as being in reasonable
agreement when scores differ by at most 15 percentage points. Individual models
can deviate in either direction. Public exposure nevertheless makes public
results much more vulnerable to harness adaptation and model contamination.

ARC Prize's analysis of GPT-5.5 and Claude Opus 4.7 identified three recurring
failure modes:

1. The model observes a true local action effect but embeds it in a false global
   world model.
2. A superficial analogy to a familiar game selects the wrong abstraction.
3. The model completes a forgiving level without learning the causal mechanism,
   then transfers the incorrect rule to later levels.

These are direct targets for competing hypotheses, ontology revision, and
evidence provenance. Source:
[official failure analysis](https://arcprize.org/blog/arc-agi-3-gpt-5-5-opus-4-7-analysis).

### 2. Kaggle hidden-game competition

The competition evaluates 110 unseen games: half contribute to the live Public
Leaderboard and half to the final Private Leaderboard. This is distinct from the
25 openly playable games. Source:
[Kaggle data description](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3/data).

The live Kaggle leaderboard was captured through Kaggle's own competition and
leaderboard services at **2026-07-26 23:22 PDT / 2026-07-27 06:22 UTC**. The top
five displayed results were YUTO KOJIMA 1.86%, Tecnod8.AI 1.61%,
DhanaLakshmiMalla 1.60%, ippeiogawa 1.58%, and Yuchen20 1.58%. Kaggle displays
two decimal places, and the ordering is volatile; this is a dated observation,
not a durable benchmark result. The request/response provenance is recorded in
[`benchmark.md`](benchmark.md#live-public-leaderboard-snapshot) and
[`sources-rules.yaml`](sources-rules.yaml). The public
[leaderboard page](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3/leaderboard)
is the current authority.

The latest primary milestone source is the
[June 30 Milestone 1 announcement](https://arcprize.org/blog/arc-prize-2026-milestone-1):

1. Tufa Labs, **The Duck**
2. **Reki**
3. Md Boktiar Mahbub Murad, **forge**

ARC Prize did not publish the three scores in that announcement. Tufa Labs
[self-reported 1.21%](https://www.linkedin.com/posts/tufalabs_our-winning-solution-to-the-arc-agi-3-milestone-activity-7478103606093676546-dlQu)
for The Duck.

The Duck runs Qwen 3.6 27B FP8 locally, exposes a Python REPL, and gives the
model a rendered frame, raw ASCII, and a region-segmentation/zoom tool. It evicts
old conversational context and keeps the harness deliberately generic. Reki
and forge use Gemma-4-31B vision policies that return short JSON action queues,
with recent labeled frames, reflection memory, legal-action guards, JSON repair,
and simple interaction heuristics. Forge included candidate generation,
arbitration, and confidence-safe behavior, but its best run disabled most of
that additional machinery.

The hidden-game result is an important counterweight to public harness scores:
simple, local, code-capable models can transfer better than heavily
public-optimized systems, and extra orchestration does not necessarily help.

### 3. Public Demo and community research

The Public Demo contains 25 games and is appropriate for development,
instrumentation, and ablation. ARC Prize states that ARC-AGI-3 community scores
are normally self-reported. The following results differ in model, cost, number
of runs, exposure, and selection procedure and must not be ranked as if they
were one controlled experiment.

| System | Reported Public Demo result | Protocol caveat |
|---|---:|---|
| Schema, Claude Opus 4.8 + Fable 5 | **98.98%** | Conditional per-game fallback; retain the better result after rerunning games below 80%; not pass@1 |
| Executable World Models verification, GPT-5.6 Sol xhigh | **98.97%** | One reported public run; model postdates public games; no holdout result |
| PRO-LONG, Fable 5 | **97.4% best@2** | Best of two runs; its reported pass@1 ceiling is 76.1% |
| Schema, GPT-5.6 Sol xhigh + max fallback | **95.35%** | Same conditional rerun-and-retain protocol |
| OPINE-World, Claude Opus 4.8 | **78.4%** | One run per game; no same-model baseline ablation |
| baseline1 community entry | **63.7%** | Public, self-reported |
| Vision Continual Learning v1 | **63.1%** | Weights adapted using the same 25 public games before scoring |
| TELL | **43.9%** | Public, self-reported |
| Human Intelligence Harness | **95.3%** | Human replay/upper-bound harness, not an AI result |

Sources:
[Schema](https://schema-harness.github.io/),
[Executable World Models ablation](https://arxiv.org/abs/2607.15439),
[PRO-LONG](https://arxiv.org/abs/2607.20064),
[OPINE-World](https://arxiv.org/abs/2607.01531), and the
[ARC Prize community leaderboard](https://arcprize.org/leaderboard/community).

#### Why best-of-\(k\) requires separate reporting

Selecting the better of multiple complete runs measures a different system from
a single first-contact playthrough. Conditional reruns are especially difficult
to compare because the decision to rerun uses the first score. The suite should
record:

- `pass_at_1`: a predeclared single run;
- all-run mean and variance when repeated experiments are allowed;
- `best_at_k` only as a separately labeled robustness/oracle statistic;
- whether selection occurs per benchmark, per game, or per level;
- whether the model or harness had prior exposure to the public games.

## Architecture review

### Schema: the closest implementation

[Schema](https://schema-harness.github.io/) implements the original proposed
loop with unusually close correspondence:

1. It grounds the 64×64 pixel screen into objects, variables, and relations.
2. It keeps one editable `world_model.py` with the state representation,
   transition function, and inferred goal predicate.
3. It records every real transition in an append-only Timeline.
4. The LLM writes and revises the model as Python source.
5. `run_backtest` replays the complete known history and requires exact
   agreement before a revision is accepted.
6. BFS explores thousands of simulated states without spending real actions.
7. `commit_actions` queues structured action sequences.
8. Every committed action is simulated and checked against the real frame.
9. The remaining queue is cancelled on the first mismatch.
10. The agent can choose an experiment intended to distinguish alternative
    candidate rules.

Its published traces show that the important revisions can be ontological. In
WA30, for example, replacing a “steer a block” representation with a carry-state
representation changed the solvable search space. This demonstrates that search
is complete only relative to the chosen state representation.

Schema reports exact learned models in 14 of 25 games and, once a game is
modeled, can use substantially fewer real actions than the human aggregate
because simulator search is free. Its 50 public trajectories are available in
the [Schema traces dataset](https://huggingface.co/datasets/schema-harness/arc-agi-3-schema-traces).

Limitations relevant to this project:

- one admitted active world model encourages premature commitment;
- exact pixel equality can discard useful partially correct mechanics;
- it does not establish hidden-game transfer;
- fallback scores select across runs;
- “candidate hypotheses” are not a persistent, calibrated executable version
  space.

### Executable World Models and its ablation

[Executable World Models](https://arxiv.org/abs/2605.05138), with
[open code](https://github.com/astroseger/arc-3-agents-baseline1), divides the
work into a world-model engine, state I/O, planner, replay verifier, and plan
executor. It repeatedly refactors the model as an informal minimum-description-
length pressure. Plans are simulated before execution, and execution halts on a
frame mismatch.

The follow-up
[component ablation](https://arxiv.org/abs/2607.15439) compared four nested
agents: textual theory, flexible executable theory, scheduled simplification,
and fixed-interface replay verification. The strongest general findings are:

- stronger models and higher reasoning effort dominate the component effects;
- requiring an executable deliverable is not universally beneficial—the
  textual agent beat the flexible executable agent in both GPT-5.5 settings;
- simplification helped in three of four original settings;
- fixed-interface exact verification ranked first in all four settings but used
  the most resources;
- GPT-5.6 Sol plus verification saturated the public set, but held-out
  performance was not tested.

The paper's main Public Demo table, in that variant order, is:

| Model and effort | Textual | Executable | + simplification | + fixed replay verification |
|---|---:|---:|---:|---:|
| GPT-5.4 High | 34.16 | 33.54 | 30.60 | **39.16** |
| GPT-5.4 xhigh | 40.67 | 44.72 | 53.10 | **53.72** |
| GPT-5.5 High | 58.85 | 51.16 | 58.35 | **65.64** |
| GPT-5.5 xhigh | 72.51 | 69.70 | 73.09 | **74.78** |

In the exploratory GPT-5.6 Sol follow-up, textual versus verification scored
92.34 versus 98.97 at xhigh and 95.97 versus 98.77 at max. These figures are
public-set author reports, not official Semi-Private scores.

Therefore, this suite should make executable formalization adaptive: use a
textual or partial theory while evidence is sparse, and require executable
certification before long plans or expensive commitments.

The baseline authors also found that insufficiently hardened coding-agent
setups could expose game identifiers, web search, or a second environment
client. Evaluation must hide identifiers and source, block network access, and
permit only one authoritative environment connection.

### OPINE-World

[OPINE-World](https://arxiv.org/abs/2607.01531) uses an acting agent, a
program-synthesizing agent, and a critic. It writes an object-centric
`game_engine.py`, transition function, goal predicate, and planner. Models are
admitted by exact replay, run twice to detect impurity or hidden mutable state,
and subjected to static goal checks.

Its distinguishing mechanism is “ontology error”: Dirichlet counts and entropy
over effect signatures indexed by object type, action, and local context direct
probes toward uncertain affordances. Synthesis is counterexample-triggered
rather than scheduled. Planning begins after a level has been cleared, is
validated on completed levels, and is checked after every real action.

This means object-centric synthesis, replay admission, and Bayesian
object-affordance uncertainty are already prior art. OPINE's stated limitations
suggest productive extensions: it assumes deterministic observable-Markov
dynamics, uses heuristic object extraction/matching, relies on bounded forward
search, and reports no run variance.

### PRO-LONG and lossless programmatic memory

[PRO-LONG](https://arxiv.org/abs/2607.20064), with
[open code](https://github.com/alexisfox7/PRO-LONG), appends observations,
actions, and outcomes verbatim to one structured `log.txt`. A coding agent uses
grep and Python as retrieval rather than relying on an elaborate memory service.
The action analyzer can emit a queue that drains without further model calls and
is interrupted by salient state or score changes.

The main lesson is architectural: retain an immutable, lossless event ledger
alongside compiled semantic memory. Summaries and context eviction can compound
incorrect theories; no summary should be allowed to erase the evidence from
which a rule was inferred.

### Other relevant baselines

- [TELL](https://github.com/studio-dots-ai/TELL): a single conversation with
  screenshot, bash, and `MEMORY.md`; a useful minimal memory baseline.
- [Graph-based exploration](https://arxiv.org/abs/2512.24156): segments frames,
  records an observed transition graph, and seeks paths to untested state-action
  pairs. Useful when no model is trustworthy.
- [StochasticGoose](https://github.com/DriesSmit/ARC3-solution): learned
  frame-change prediction and exploration; successful in the small preview but
  transferred poorly to the broader launch distribution.
- [Vision Continual Learning v1](https://github.com/vansh-one/arc-agi-3_Vision-CLv1):
  multimodal perception plus learned weights carried across the public games;
  useful as an exposed-data upper bound, not first-contact evidence.
- [Agentica](https://www.symbolica.ai/blog/arc-agi-3), with
  [code](https://github.com/symbolica-ai/ARC-AGI-3-Agents): orchestrator and
  specialized subagents with compressed textual state.
- [DreamTeam](https://arxiv.org/abs/2605.09650): role-specialized agents that
  construct models, plan, hypothesize, probe, and route failures. It reports
  38.4% under the official public scoring protocol, averaged over two runs, with
  31% fewer environment actions than its protocol-matched comparator.
- [WorldCoder](https://arxiv.org/abs/2402.12275): earlier LLM-written Python
  world models constrained by interaction evidence and optimistic planning.
- [Theory-based reinforcement learning](https://doi.org/10.1098/rsta.2024.0529):
  object-oriented causal theories, targeted exploration, and planning as an
  account of rapid human game learning.

## Recommended research architecture

### 1. Executable version space

Maintain \(K\) replay-consistent hypotheses rather than one authoritative file.
Each hypothesis contains:

- a perception and object-ontology program;
- transition and goal programs;
- optional latent-state variables;
- supporting and refuting transition IDs;
- a domain of known applicability and untested guards;
- a description-length prior and calibrated posterior weight.

Exact history consistency is necessary but insufficient: many incorrect rules
fit a short trace. Do not collapse the version space until an observed outcome
discriminates among hypotheses.

### 2. Risk-aware active experiments

Score candidate real actions by a combination such as:

\[
\frac{\text{expected model information} + \text{expected task progress}}
     {\text{RHAE action cost} + \text{death risk} + \text{irreversibility}}
\]

Predicted outcomes are obtained by running all surviving simulators. Prefer
actions with high disagreement when the game is safe to probe. Cache
state-action “no effect” signatures to avoid repeated ineffective interactions.

### 3. Revisable causal ontology

Object extraction should return hypotheses, not facts. Preserve alternative
4-connected and 8-connected components, part/whole decompositions,
merge/split candidates, symmetry groups, repeated motifs, and temporal identity
matches. Infer causal roles from interventions rather than color or shape alone.
Relations should include touching, containment, alignment, occlusion, blocking,
pairing, and relative offsets.

### 4. Layered dynamics and hidden state

Keep four synchronized layers:

1. lossless pixels and metadata;
2. multi-scale object/relation graph;
3. symbolic causal transition program;
4. unexplained pixel residuals and optional latent-state automaton.

Use graded diagnostics—pixel mismatch, object mismatch, relation mismatch, and
status mismatch—while retaining exact replay as the certification requirement.
If apparently identical visible state-action pairs yield different outcomes,
introduce a latent automaton or history feature rather than repeatedly patching
visible rules.

### 5. Abstraction-refining planning

Plan first over coarse relational state and validate the plan against finer
simulation. A failed refinement check should identify the omitted predicate or
state factor. Select among BFS, A*, width-based search, constraint solving, and
backtracking based on the modeled game. Anti-unify verified repeated plans into
parameterized macros with explicit preconditions.

### 6. Dual memory and two-speed control

The fast path performs deterministic parsing, diffs, transition logging, graph
coverage, and verified macro execution. The slow LLM path revises theories or
ontologies only after surprise, stalling, or a high-value ambiguity.

Store both:

- an append-only lossless event log; and
- compiled objects, rules, hypotheses, plans, and macros whose claims link back
  to supporting transition IDs.

## Evaluation requirements

The main ablations should compare:

- single simulator versus executable version space;
- fixed ontology versus ontology revision;
- passive exploration versus information-gain probing;
- exact-only versus layered diagnostics plus exact certification;
- observable state versus latent-state induction;
- summary memory versus immutable log plus semantic memory;
- fixed BFS versus the planner portfolio;
- mandatory versus adaptively triggered executable modeling.

For every run, record score, completed games and levels, real actions, simulated
states, LLM calls and tokens, runtime, model-mismatch rate, hypothesis entropy,
recovery latency after a mismatch, planner type, deaths/resets, and cost.

Evaluation hygiene:

- fresh workspace and model context for every game;
- no game identifier, source code, web access, or second environment client;
- one predeclared pass@1 as the headline;
- no retained solution or weight update from one public game unless evaluating a
  separately labeled continual-learning condition;
- separate Public Demo, blind synthetic holdout, Kaggle Public Leaderboard, and
  Kaggle Private Leaderboard reporting;
- publish every trajectory and failure, not only successful runs.

The architecture should be considered supported only if the version-space and
ontology-revision components improve blind holdout transfer or materially reduce
real actions at equal completion—not merely if they reproduce near-saturated
Public Demo results.
