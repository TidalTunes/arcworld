# Architecture tour

ARCWorld keeps the control file small and puts every mechanism behind an explicit
interface. Start with [`agent.py`](../src/arcworld/agent.py): it resets, asks for a
certified model, asks for a pre-simulated plan, executes until terminal or surprise,
and requests revision after surprise.

## Evidence path

`Observation` retains every animation frame plus state, progress, and available-action
metadata. `EpisodeHistory` is the in-memory contiguous trace; `RunStore` is the
persistent SQLite event ledger. The trusted ledger may retain environment identity for
human auditing. Reasoner prompts use a separate recursive redactor.

Files:

- [`types.py`](../src/arcworld/types.py)
- [`history.py`](../src/arcworld/history.py)
- [`storage.py`](../src/arcworld/storage.py)

## Perception path

`parse_scene_candidates` deliberately returns more than one interpretation. Current
alternatives vary background hypotheses and 4/8 connectivity. Each graph includes
monochrome components, shape masks, holes, boxes, centroids, and geometric relations.
The raw grid remains authoritative.

Files:

- [`perception/components.py`](../src/arcworld/perception/components.py)
- [`perception/relations.py`](../src/arcworld/perception/relations.py)
- [`perception/tracking.py`](../src/arcworld/perception/tracking.py)
- [`perception/diff.py`](../src/arcworld/perception/diff.py)

Multicolor grouping, explicit part/whole programs, learned causal roles, and latent
state are research work, not current capabilities.

## Executable rule path

A generated rule module has three required pure functions:

```python
def initial_state(observation): ...
def step(state, action): ...
def render(state): ...
```

It can additionally define `render_frames`, `status`, `metrics`, and `is_goal`.
`RuleProgram` validates syntax, then runs calls in an isolated `python -I` worker with a
reduced builtin namespace, a fresh module namespace per call, a wall timeout, and
best-effort CPU/memory/file limits. Inputs and outputs cross a JSON pipe. This prevents
ordinary file/network access, persistent generated globals, and unbounded hangs in the
trusted runner. It is not a seccomp/container security boundary; use a hardened
container for adversarial output.

`ModelRepository` stores content-addressed revisions. `ReplayVerifier` reconstructs
state from the initial observation and checks every known transition. `RevisionManager`
revalidates every stored candidate after every new counterexample; only a complete
replay pass can update the atomic active pointer.

Files:

- [`models/contract.py`](../src/arcworld/models/contract.py)
- [`models/store.py`](../src/arcworld/models/store.py)
- [`models/verifier.py`](../src/arcworld/models/verifier.py)
- [`revision.py`](../src/arcworld/revision.py)

## Belief and action path

Exactly one promoted model controls exploitation. Other replay-consistent revisions
remain weighted shadows. Before falling back to a strategic plan,
`BeliefAwarePlanningService` predicts candidate actions under each shadow. If a safe
action separates their outcomes, it emits a one-action probe.

For exploitation, the reasoner writes Python `build_plan(api, context)` code. That code
only constructs an action list. `simulate_plan` must roll out the complete list before
the real executor receives it. `VerifiedExecutor` then spends actions one by one and
returns the unspent suffix at the first pixel/status/progress mismatch.

Files:

- [`hypotheses.py`](../src/arcworld/hypotheses.py)
- [`probing.py`](../src/arcworld/probing.py)
- [`services.py`](../src/arcworld/services.py)
- [`planning/dsl.py`](../src/arcworld/planning/dsl.py)
- [`planning/simulate.py`](../src/arcworld/planning/simulate.py)
- [`planning/executor.py`](../src/arcworld/planning/executor.py)

## Reasoner boundary

`Reasoner` is provider-neutral. `OpenAIResponsesReasoner` is the optional development
adapter; `CallableReasoner` accepts a bundled in-process local model. The default
OpenAI composition uses separate hard-reasoning revision/planning roles and creates a
fresh per-episode model workspace, preventing silent cross-game rule reuse.

The final Kaggle runtime cannot call OpenAI because notebook internet is disabled. Use
`build_agent` with local `CallableReasoner` instances in that setting.

Files:

- [`llm/base.py`](../src/arcworld/llm/base.py)
- [`llm/prompts.py`](../src/arcworld/llm/prompts.py)
- [`llm/workflows.py`](../src/arcworld/llm/workflows.py)
- [`composition.py`](../src/arcworld/composition.py)

## Inspection boundary

`arcworld gui` serves a local FastAPI application and never opens a browser. The UI
shows Actual, Predicted, and Difference grids, timeline evidence, objects, relations,
and mismatch metrics. The live buttons operate only the bundled synthetic world.

Files:

- [`gui/app.py`](../src/arcworld/gui/app.py)
- [`gui/static/`](../src/arcworld/gui/static/)
