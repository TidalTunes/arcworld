# ARCWorld open questions

**Snapshot:** 2026-07-26
**Purpose:** living uncertainty register for research and implementation
**Protocol:** experiments should follow
[evaluation_protocol.md](evaluation_protocol.md)

## Status language

- **Open:** no adequate experiment has been run.
- **In progress:** implementation or a preregistered experiment exists, but the
  result is not complete.
- **Provisionally answered:** evidence supports a decision within a named
  distribution; broader transfer remains open.
- **Closed by constraint:** a project or competition requirement fixes the
  answer rather than an experiment.

None of the empirical questions below is resolved as of this snapshot.

## Decisions already grounded

These are architectural starting points, not experimental discoveries:

1. The single editable `step(state, action)` loop is prior art and is the
   baseline, not the novelty claim. See [landscape.md](landscape.md).
2. Exactly one promoted active model controls exploitation plans; alternative
   replay-consistent models remain as shadows.
3. Active promotion requires complete exact replay, even when semantic partial
   models are retained for diagnosis.
4. The lossless interaction record is authoritative; summaries are indexes.
5. OpenAI is the only permitted external model service and is optional in
   development. Offline evaluation cannot require it.
6. Public Demo, Semi-Private, Kaggle Public, Kaggle Private, and synthetic blind
   results remain separate.

## P0 — questions that can invalidate the research direction

### OQ-001: Does a shadow version space improve blind transfer?

**Status:** Open

**Why it matters:** This is the central research hypothesis. Maintaining several
programs adds model calls, storage, simulation, and decision complexity. It may
merely delay commitment without improving behavior.

**Current hypothesis:** Weighted replay-consistent shadows improve pass@1,
reduce irreversible errors, and shorten recovery after counterexamples relative
to a single active model.

**Minimum experiment:** Paired single-model and active-plus-shadow treatments on
sealed synthetic games, holding reasoner, prompts, action budget, and planner
constant. Include games with deliberately underdetermined early histories and
observable games where ambiguity disappears immediately.

**Primary outcomes:** completion at fixed real-action budget, avoidable deaths,
and real-action recovery latency after the first active-model contradiction.

**Decision rule:** Retain the version-space treatment only if it improves a
predeclared blind outcome or yields a meaningful action saving at matched
completion. Public-only improvement is insufficient.

### OQ-002: Are hypothesis weights calibrated enough to guide actions?

**Status:** Open

**Why it matters:** A numerically normalized set of heuristic scores is not
automatically a posterior. Miscalibrated weights can make information-gain
probes worse than unweighted disagreement.

**Current hypothesis:** Description-length priors plus evidence likelihoods
calibrated separately for exact and semantic agreement outperform uniform
weights.

**Minimum experiment:** On generated worlds with known true programs, compare
uniform voting, rank-only weights, MDL weights, and calibrated likelihood
weights. Measure probability assigned to the true equivalence class and
calibration of predicted outcome/death probabilities.

**Open design choices:**

- whether complexity is source length, AST nodes, state variables, or a learned
  structural cost;
- how much probability semantic shadows retain after exact mismatch;
- whether correlated LLM-generated hypotheses require diversity correction;
- how to prevent duplicate programs from multiplying one theory's mass.

### OQ-003: Does active information gathering beat coverage exploration?

**Status:** Open

**Why it matters:** Weighted disagreement can be expensive to compute and may
prefer scientifically informative actions that are bad for the task or human
efficiency score.

**Current hypothesis:** Information gain adjusted for progress, action cost,
death risk, reset cost, and irreversibility dominates raw entropy and
state-action coverage.

**Minimum experiment:** Compare random legal, coverage graph, raw outcome
entropy, and the full risk-adjusted utility on the same sealed games and shadow
predictions.

**Primary outcomes:** information gain per real action and completion at fixed
action budget. Report deaths and resets separately.

**Key unknown:** How should the utility trade learning against immediate
progress as confidence and remaining budget change?

### OQ-004: Does Public Demo development predict any hidden improvement?

**Status:** Open

**Why it matters:** Public harnesses report approximately 99% while the first
Kaggle milestone winner reported 1.21%. Optimizing a public mean can reward
contamination, manual game knowledge, or representation choices that do not
transfer.

**Current hypothesis:** Improvements in mechanism-level diagnostics on sealed
synthetic games—calibration, counterexample recovery, and action efficiency—
will be more predictive than aggregate Public Demo score.

**Minimum experiment:** Freeze several materially different harness versions,
record public and sealed-synthetic metrics, then submit them without further
adaptation to the same Kaggle Public evaluation window when submission budget
permits.

**Decision implication:** If public score and hidden score are negatively or
weakly associated, public runs become qualitative regression tests only.

### OQ-005: Can an offline model perform the required synthesis?

**Status:** Open

**Why it matters:** OpenAI models can accelerate development, but Kaggle
execution must not depend on a network API. The winning Milestone 1 system used
a local Qwen model, while official results show large capability differences
between reasoning models.

**Current hypothesis:** A two-speed design can reserve a local code-capable
model for counterexample-triggered ontology/model revision and use
deterministic code for all other steps.

**Minimum experiment:** Run the same sanitized synthesis and plan-authoring
corpus through the selected OpenAI development model and candidate local
checkpoints. Evaluate source validity, replay success, revision count, latency,
and end-to-end blind-game outcomes.

**Decision implication:** The architecture must expose model-neutral adapters;
features that only work with an unavailable API cannot be part of the Kaggle
profile.

## P1 — core mechanism questions

### OQ-006: Which ontology candidate language is broad enough but searchable?

**Status:** Open; basic background and 4/8-connectivity alternatives are
implemented.

**Why it matters:** Schema traces show that changing the state representation
can make an otherwise exhaustive search useful. Enumerating every possible
pixel grouping is intractable.

**Candidate language:**

- background hypotheses;
- monochrome 4/8-connected components;
- multicolor connected components;
- repeated motifs and symmetry groups;
- nested part/whole objects;
- merge/split operations;
- temporal motion-coherent groups;
- roles and relations induced from interventions.

**Minimum experiment:** Build adversarial synthetic pairs where each ontology
family is necessary, then measure whether the true or behaviorally equivalent
ontology survives within a fixed candidate/model-call budget.

**Open design choices:** beam size, ontology complexity prior, canonicalization,
and when temporal evidence is allowed to overturn the initial segmentation.

### OQ-007: How should object identity survive transformation and occlusion?

**Status:** Open; deterministic greedy tracking is implemented as a baseline.

**Why it matters:** A recolored, rotated, carried, split, hidden, or reappearing
object can be misclassified as deletion plus creation, causing the rule program
to learn the wrong effect.

**Current hypothesis:** Multiple temporal matchings with explicit costs and
causal consistency will outperform one greedy assignment.

**Minimum experiment:** Synthetic sequences covering translation, recoloring,
rotation, temporary occlusion, merge/split, and identical distractors. Compare
greedy matching, global bipartite matching, and top-\(k\) correspondence
hypotheses.

### OQ-008: When is latent state justified?

**Status:** Open; no latent-state learner is implemented.

**Why it matters:** OPINE assumes observable-Markov deterministic dynamics.
ARC-like worlds can contain counters, toggles, inventory, delayed effects, or
occluded state. Conversely, arbitrary hidden variables can memorize history.

**Current hypothesis:** Introduce a bounded latent automaton only after two
apparently equivalent visible state-action transitions disagree and visible
refinements fail.

**Minimum experiment:** Positive controls with known hidden bits/counters and
negative controls whose apparent nondeterminism is caused by missed pixels,
object correspondence, or animation frames.

**Acceptance checks:** exact replay improves, held-out transition prediction
improves, complexity is bounded, and the induced state is not an episode-step
lookup table.

### OQ-009: How much semantic mismatch is safe?

**Status:** Open; exact pixel and object/relation diffs are implemented, but a
calibrated tier policy is not.

**Why it matters:** Exact-only admission may discard a correct causal model with
a decorative renderer error. Relaxed admission may authorize a catastrophic
plan under a partially wrong model.

**Current hypothesis:** Semantic shadows can guide probes and diagnoses, while
only exact models authorize exploitation.

**Minimum experiment:** Worlds with irrelevant animation/decorative residuals
and worlds where a small pixel mismatch signals a critical hidden obstacle.
Measure useful-shadow retention and unsafe-plan rate.

**Open design choices:** equivalence classes, object-diff thresholds,
animation-frame requirements, and whether short reversible plans can be
authorized under semantic agreement.

### OQ-010: When should the reasoner formalize an executable model?

**Status:** Open.

**Why it matters:** The Executable World Models ablation found that a textual
theory beat a flexible executable model in both GPT-5.5 conditions, although
fixed replay verification performed best overall and cost more.

**Current hypothesis:** Use textual/partial theories while evidence is sparse,
then require executable exact replay before long planning.

**Minimum experiment:** Immediate formalization, scheduled formalization, and
counterexample/plan-triggered formalization under identical model and token
budgets.

**Potential triggers:** first progress event, two informative transitions,
shadow disagreement below a threshold, planned depth above a threshold, or a
model mismatch.

### OQ-011: Which planner should handle which learned model?

**Status:** Open; bounded BFS is implemented.

**Why it matters:** BFS is reliable for small exact states but fails under large
click spaces, long horizons, constraints, or latent belief states.

**Current hypothesis:** A measurable router over BFS, A*, width-based search,
constraint/backtracking, belief search, and plan code will reduce simulated
compute without reducing plan validity.

**Minimum experiment:** A planner corpus whose true dynamics are known,
stratified by branching factor, horizon, constraint density, and partial
observability. Hold the world model fixed so the planner is the only treatment.

**Router inputs must exclude:** game ID, public-game-specific labels, and prior
solution memory.

### OQ-012: Does CEGAR improve planning or just add machinery?

**Status:** Open; not implemented.

**Why it matters:** Search in a coarse object abstraction may be efficient but
produce spurious plans. Full-state search may be exact but infeasible.

**Current hypothesis:** Validating an abstract plan in the exact active model
and refining only the first missing predicate will reduce search while
preserving correctness.

**Minimum experiment:** Paired fixed-abstraction and CEGAR planners on worlds
with deliberately omitted blocking, inventory, orientation, or identity
predicates.

**Metrics:** simulated nodes, refinement count, exact-plan success, and wall
time.

### OQ-013: Can verified macros transfer without becoming game-specific lore?

**Status:** Open; not implemented.

**Why it matters:** Parameterized skills can cut tokens and planning time, but a
macro named after or keyed to a public game is leakage.

**Current hypothesis:** Anti-unification over verified traces can produce
generic macros expressed only through object relations and preconditions.

**Minimum experiment:** Learn macros on visible synthetic families, then test on
sealed recombinations with new colors, layouts, and object counts.

**Rejection rule:** A macro is invalid if it dispatches on identity, filename,
fixed public coordinates, or an unverified visual signature.

### OQ-014: What should be retrieved into limited model context?

**Status:** Open; an in-memory history exists, but persistent retrieval and
reasoner context assembly do not.

**Why it matters:** PRO-LONG shows that a complete searchable log can outperform
specialized memory, while The Duck succeeds with old-context eviction. These
are compatible only if eviction affects prompts, not evidence.

**Current hypothesis:** Recent exact transitions plus programmatic retrieval by
action/object/diff signature and provenance-linked semantic claims will
outperform either full prompt stuffing or summary-only memory.

**Minimum experiment:** Full transcript, recent window, summary-only, and
lossless searchable log under the same context/token budget.

## P2 — engineering and measurement questions

### OQ-015: Is generated-code isolation strong enough?

**Status:** Partial. Generated code now runs in an isolated `python -I` worker
with JSON-only IPC, a fresh namespace per call, wall timeouts, and best-effort
CPU/memory/file limits. It is not a hardened syscall/container boundary.

**Why it matters:** Coding-agent baselines have found unintended information
channels. Python AST filtering cannot contain resource exhaustion or all object
graph attacks.

**Minimum experiment:** Red-team corpus covering imports, dunder traversal,
introspection, closures, exceptions, serialization abuse, infinite loops,
memory exhaustion, filesystem/process/network access, environment variables,
and attempts to obtain a second client.

**Target:** Retain the current AST and worker defenses, then add a hardened
container/seccomp boundary with explicit filesystem, syscall, and network
denial. Red-team both layers.

### OQ-016: What event-store design is truly append-only?

**Status:** Open; current `EpisodeHistory` is an in-memory list.

**Why it matters:** A mutable list cannot establish durable provenance or
survive a crash. SQLite can still be mutated unless application and audit
constraints are explicit.

**Candidate design:** chained event hashes, insert-only API, WAL durability,
content-addressed frame blobs, schema migrations that add derived tables, and a
seal/finalization record.

**Minimum experiment:** crash injection around every environment action and
write boundary, followed by integrity verification and replay.

### OQ-017: How should click candidates be generated generically?

**Status:** Open.

**Why it matters:** ACTION6 exposes thousands of coordinates. Pure enumeration
is intractable; handcrafted “button” heuristics may encode public-game bias.

**Candidate sources:** object centers, corners, holes, repeated-motif cells,
changed regions, relation intersections, grid-cell representatives, reasoner
proposals, and adaptive subdivision.

**Minimum experiment:** Sealed click worlds where salient-small-object,
large-region, empty-cell, repeated-pattern, and off-center clicks are each
required. Report target coverage per candidate count.

### OQ-018: What constitutes irreversibility before the rules are known?

**Status:** Open.

**Why it matters:** Death risk is observable only after examples; many harmful
actions do not immediately set `GAME_OVER`.

**Candidate proxies:** disagreement over terminal outcome, inability of shadow
models to return to the prior state, disappearing unique objects, resource
decrease, level-reset signatures, and absence of known inverse actions.

**Minimum experiment:** Calibrate predicted irreversibility on synthetic traces
with labeled reversible, costly, delayed-trap, and terminal actions.

### OQ-019: How should level transitions affect learning?

**Status:** Open.

**Why it matters:** Later levels compose earlier mechanics, but a level can be
solved accidentally. Treating every win as proof hardens false theories;
discarding prior evidence wastes continual-learning signal.

**Current hypothesis:** Preserve the full model version space across levels,
increase the weight of mechanisms causally required by the successful trace,
and keep coincidental alternatives until later evidence distinguishes them.

**Minimum experiment:** Progressive synthetic levels where Level 1 admits
multiple explanations and Level 2 separates them.

### OQ-020: How much GUI control is compatible with reproducibility?

**Status:** Open; GUI not implemented.

**Why it matters:** Researchers need to inspect actual/predicted/diff views and
model evolution, but manual edits during a scored run invalidate pass@1.

**Decision constraint:** Evaluation mode is read-only. Interactive stepping,
model editing, replay branching, and prompt experiments are development-mode
features and create new explicitly unscored branches.

**Minimum usability test:** An independent researcher can locate the first
model mismatch, its supporting evidence, the cancelled plan, and the next model
revision without reading raw database tables.

### OQ-021: How will scorer and benchmark drift be handled?

**Status:** Open.

**Why it matters:** Human baselines, caps, official packages, and competition
rules can change. A historical raw trajectory should remain rescorable.

**Current hypothesis:** Store raw action counts/progress plus scorer and
human-baseline digests; never store only an aggregate score.

**Minimum experiment:** Recompute a fixed replay using two versioned scorer
fixtures and show that the original and updated results coexist without
altering evidence.

### OQ-022: What is the correct compute allocation between thinking and acting?

**Status:** Open.

**Why it matters:** Stronger models and reasoning effort dominate several
public ablations, but real actions and runtime are also scarce. Excess model
calls can make an otherwise strong harness unusable offline.

**Minimum experiment:** Predeclare equal-cost and equal-action frontiers across
reasoning effort, shadow count, probe simulation budget, and planner node
budget. Plot completion against real actions, wall time, tokens, and retail
cost.

## Required evidence before a novelty claim

Before describing the system as a novel architecture in a paper or README:

1. complete a broader literature search beyond the ARC-specific systems already
   cataloged;
2. implement a faithful single-model exact-replay baseline;
3. preregister the shadow-version-space ablation;
4. run it on sealed synthetic holdouts;
5. publish pass@1, all failures, variance, cost, and action counts;
6. obtain at least one genuinely hidden evaluation when feasible;
7. show that gains are not explained solely by a stronger base model or larger
   compute budget.

Until then, use “novelty hypothesis,” “research bet,” or “proposed
differentiation,” not “novel system.”
