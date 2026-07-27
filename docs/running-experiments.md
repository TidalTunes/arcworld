# Running experiments

## Deterministic local gate

```bash
source .venv/bin/activate
arcworld doctor
arcworld toy-run
arcworld score --baselines 10,20 --actions 20,20 --completed true,true
ruff check .
ruff format --check .
mypy
pytest
```

`toy-run` should end in `WIN` after seven actions, report no divergence, and certify
complete replay. It creates only gitignored data under `.arcworld/`.

Every event is hash-chained. Verify a recorded run with:

```bash
arcworld verify-run --run-id <run-id>
```

## Dashboard

```bash
arcworld gui --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765` yourself if desired. The command does not control or open a
browser.

## Public Demo development

Install the official optional package and place legally obtained environments in the
ignored `environment_files/` directory:

```bash
python -m pip install -e '.[arc]'
arcworld list-games --environments-dir environment_files
```

For an explicitly OpenAI-backed development run:

```bash
export OPENAI_API_KEY=...
arcworld run-offline \
  --game ls20 \
  --environments-dir environment_files \
  --workspace .arcworld \
  --action-budget 500 \
  --candidate-count 2
```

This can incur API cost. It uses the official SDK in hard-coded OFFLINE mode and creates
a fresh model workspace for the episode. The trusted run label contains the game ID for
human audit, but reasoner requests redact it.

An authenticated Codex installation can provide the same OpenAI-only development
transport without placing an API key in the project:

```bash
arcworld run-offline \
  --game vc33-5430563c \
  --environments-dir environment_files \
  --workspace .arcworld \
  --provider codex-cli \
  --model gpt-5.6-luna \
  --effort low \
  --action-budget 1 \
  --candidate-count 1
```

Each completion runs in a fresh empty, read-only directory with repository rules and
user configuration excluded. The run fails closed if the model attempts a tool call.
The event record retains the OpenAI provider thread ID, token usage, CLI version and
binary hash, transcript hash, full response, and generated source links.

Audit the complete chain after a run:

```bash
arcworld audit-run --store .arcworld/runs.db --run-id <run-id>
```

The audit checks the event hash chain, exact official environment-file hashes, live
provider receipts, response-to-source hashes, world-model and plan sandbox receipts,
pre-action simulation, and real SDK transitions. `verify-run` remains the smaller
event-chain-only check.

Do not report this as hidden-benchmark evidence. The 25 Public Demo games are exposed
development data.

## Local reasoner composition

Kaggle has no inference-time internet. Attach bundled inference with
`CallableReasoner`:

```python
from arcworld.composition import build_agent
from arcworld.llm import CallableReasoner, ReasonerConfig


def infer(instructions: str, input_text: str) -> str:
    # Call a bundled local model here and return plain text.
    raise NotImplementedError


revision = CallableReasoner(
    ReasonerConfig(model="local-checkpoint", effort="fixed", role="revision"),
    infer,
)
planning = CallableReasoner(
    ReasonerConfig(model="local-checkpoint", effort="fixed", role="planning"),
    infer,
)
bundle = build_agent(
    environment,
    revision_reasoner=revision,
    planning_reasoner=planning,
)
result = bundle.agent.run(action_budget=500)
```

The local callback must return exactly one fenced Python block for each request. Package
model weights and inference dependencies under Kaggle’s licensing, size, and runtime
rules.

## Evaluation record

Before a scored experiment:

1. Freeze a commit and configuration.
2. Choose one lane from
   [`research/evaluation_protocol.md`](../research/evaluation_protocol.md).
3. Use a fresh per-game workspace and pass@1.
4. Keep all failures and resets.
5. Record model/checkpoint, effort, costs, hardware, time, action budget, and scorer
   revision.
6. Report Public Demo, blind synthetic, Kaggle public-LB, and private-LB results
   separately.
