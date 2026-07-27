# ARC-AGI-3 SDK, protocol, and public games

**Research snapshot:** 2026-07-26
**Validated packages:** `arc-agi==0.9.9`, `arcengine==0.9.3`
**Scope:** Official SDK, engine behavior, local/hosted protocol, recordings,
official baseline tooling, and the 25 public games. Competition rules and
leaderboard claims are tracked in separate research notes.

The machine-readable source ledger is
[`sources-sdk.yaml`](sources-sdk.yaml). Protocol claims below come from official
documentation and source code at pinned revisions, with local runtime checks
where stated. Public game metadata is a dated live-API snapshot and can change.

## Executive findings

1. An ARC-AGI-3 observation is not one image. One action returns **one or more
   64×64 palette-index frames**, followed by state and progress metadata. The
   last animation frame is the stable post-action observation, but earlier
   frames can reveal otherwise hidden motion and must be retained.
2. The current engine has eight action IDs: `RESET=0`, `ACTION1..ACTION7=1..7`.
   `ACTION6` alone carries an `(x, y)` coordinate, each in `0..63`.
3. `available_actions` on the current observation is the authoritative action
   set. Metadata tags such as `click` and `keyboard_click` are only hints and
   are inconsistent with the actual action spaces of some public games.
4. Reset has stateful semantics. In ordinary local execution, a reset after a
   played action restarts the current level; a reset when the per-level action
   count is already zero performs a full-game reset. Consequently, two
   consecutive resets yield a fresh game outside competition mode.
5. The live public catalog contained **25 games and 183 levels**. All 25
   downloaded constructors were zero-argument constructors, so the SDK's
   `seed=` parameter had no effect on this snapshot.
6. The official prose, OpenAPI file, SDK examples, agent templates, and current
   implementation are not perfectly synchronized. Code that is tolerant of
   documented inconsistencies is necessary; silently choosing one stale schema
   is not.
7. ARCWorld's environment integration should remain local-first. The adapter in
   `src/arcworld/env/arc_adapter.py` accepts an injected wrapper or opens an
   already-downloaded game in hard-coded SDK `OFFLINE` mode. It exposes no API
   key, URL, normal-mode, or online-mode configuration.

## Provenance and versions

| Artifact | Revision or version | Date | License |
|---|---|---:|---|
| [ARC-AGI SDK](https://github.com/arcprize/ARC-AGI) | `0.9.9`, commit `f12822c4d550121c35a275008d964afbbed47d2f` | 2026-06-10 | MIT |
| [ARCEngine](https://github.com/arcprize/ARCEngine) | `0.9.3`, `b495c6acaf253c9681cd7b75c4299d352e9ce6f8` | 2026-01-28 | MIT |
| [ARC-AGI-3-Agents](https://github.com/arcprize/ARC-AGI-3-Agents) | `10213de83f01df0ef4f0149ee9f8408dcc3772fb` | 2026-05-28 | MIT |
| [ARC-AGI-3 Kaggle Starter](https://github.com/arcprize/ARC-AGI-3-Kaggle-Starter) | `eeb1535404f321d280a8f9194bbc1d7aca5f05fc` | 2026-05-27 | **No LICENSE file found** |
| [Official benchmarking harness](https://github.com/arcprize/arc-agi-3-benchmarking) | `0.1.0`, `dc814bedbc0d694b25cc5dd9e546a6a249aef24e` | 2026-06-29 | MIT |
| 25 downloaded public game sources | live versions listed below | 2026-07-26 | MIT header in every source |
| Kaggle competition dataset | live competition | 2026-07-26 | Apache-2.0 on competition page |
| Stochastic Goose origin repository | `a6e77bbf90b5438d37f2d4d35b1c4825d769844d` | 2026-01-27 | **No LICENSE file found** |

Absence of a repository license is not permission to copy its code. The
unlicensed starter/sample-origin repositories are evidence about workflows and
architectures only unless permission is clarified.

## Installation and local execution

The published SDK requires Python 3.12 or newer:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install "arc-agi==0.9.9"
```

The project's optional dependency is equivalent to:

```bash
pip install -e ".[arc]"
```

The official SDK's `NORMAL` mode downloads public source before running it
locally. That is useful for a one-time research acquisition step, but it is not
the execution mode used by the ARCWorld core adapter. Once the official files
exist at:

```text
environment_files/<base-game-id>/<version>/metadata.json
environment_files/<base-game-id>/<version>/<class-name-lower>.py
```

use SDK `OFFLINE` mode:

```python
from arc_agi import Arcade, OperationMode

arcade = Arcade(
    operation_mode=OperationMode.OFFLINE,
    environments_dir="environment_files",
)
env = arcade.make("ls20-9607627b", render_mode="terminal-fast")
assert env is not None
first = env.observation_space
```

`Arcade.make()` creates and resets the wrapper before returning it.
`observation_space` therefore contains the initial active frame; callers should
not spend an extra reset simply to obtain an initial observation.

ARCWorld's narrower entry point is:

```python
from arcworld.env.arc_adapter import ArcAdapter

env = ArcAdapter.open_offline(
    "ls20-9607627b",
    environments_dir="environment_files",
)
observation = env.observation
```

An already-created local wrapper or deterministic test double can instead be
injected:

```python
env = ArcAdapter(wrapper, action_encoder=encoder_for_test_double)
```

The adapter lazily imports the optional SDK/engine, validates actions against
each current observation, preserves all returned frames, and returns only
ARCWorld `Action` and `Observation` values to the suite.

## Exact Python API surface

The signatures below were introspected from SDK 0.9.9.

```python
Arcade(
    arc_api_key: str = "",
    arc_base_url: str = "https://three.arcprize.org",
    operation_mode: OperationMode = OperationMode.NORMAL,
    environments_dir: str = "environment_files",
    recordings_dir: str = "recordings",
    logger: logging.Logger | None = None,
)
```

```python
Arcade.make(
    game_id: str,
    seed: int = 0,
    scorecard_id: str | None = None,
    save_recording: bool = False,
    include_frame_data: bool = True,
    render_mode: str | None = None,
    renderer: Callable[[int, FrameDataRaw], None] | None = None,
) -> EnvironmentWrapper | None
```

```python
Arcade.open_scorecard(
    source_url=None,
    tags=None,
    opaque=None,
) -> str

Arcade.create_scorecard(...) -> str
Arcade.get_scorecard(scorecard_id=None) -> EnvironmentScorecard | None
Arcade.close_scorecard(scorecard_id=None) -> EnvironmentScorecard | None
```

```python
Arcade.listen_and_serve(
    host="0.0.0.0",
    port=8001,
    competition_mode=False,
    save_all_recordings=False,
    include_frame_data=True,
    add_cookie=None,
    scorecard_timeout=None,
    on_scorecard_close=None,
    extra_api_routes=None,
    renderer=None,
    **kwargs,
) -> None
```

The returned wrapper surface is:

```python
EnvironmentWrapper.reset() -> FrameDataRaw | None

EnvironmentWrapper.step(
    action: GameAction,
    data: dict | None = None,
    reasoning: dict | None = None,
) -> FrameDataRaw | None

EnvironmentWrapper.observation_space
EnvironmentWrapper.action_space          # list[GameAction]
EnvironmentWrapper.info                  # EnvironmentInfo
```

`EnvironmentInfo` has a required `game_id` and optional `title`, `default_fps`,
`tags`, `private_tags`, `level_tags`, `baseline_actions`, `date_downloaded`,
`class_name`, and runtime-only `local_dir`. `default_fps` defaults to 5.

SDK render modes are `terminal`, `terminal-fast`, and `human`. A callback can
replace the built-in renderer.

### Environment variables and precedence

SDK 0.9.9 reads:

- `ARC_API_KEY`
- `ARC_BASE_URL`
- `OPERATION_MODE`
- `ENVIRONMENTS_DIR`
- `RECORDINGS_DIR`

Non-default explicit constructor values generally beat environment values.
There are two important qualifications:

- explicit parameters equal to the constructor's default sentinel defer to the
  corresponding environment variable;
- `OPERATION_MODE=competition` takes precedence over an explicitly passed
  `OperationMode.OFFLINE`.

If no key exists and the resolved mode is not offline, the constructor calls
the undocumented anonymous-key endpoint and then fetches game metadata.
ARCWorld therefore refuses `open_offline()` when
`OPERATION_MODE=competition`; otherwise an apparently local call could create a
remote session.

## Execution modes

| Mode | Discovery and execution | Network | Scorecard behavior |
|---|---|---:|---|
| `NORMAL` | Scans local files, downloads a missing/exact public source, executes locally | Yes | Local in-memory scorecard |
| `OFFLINE` | Recursively scans existing `metadata.json`, executes downloaded source locally | No | Local in-memory scorecard |
| `ONLINE` | Uses hosted command and scorecard REST APIs | Yes | Hosted scorecard and replay |
| `COMPETITION` | Managed remote gateway only | Yes | One constrained competition scorecard |

Competition mode additionally enforces one scorecard, one `make()` per
environment, participation in all exposed games, no in-flight scorecard read,
and level-only reset behavior. Kaggle supplies the managed gateway and forces
this mode; a user implementation should not try to create a second environment
client.

For local REST-compatible testing after the files are present:

```python
from arc_agi import Arcade, OperationMode

Arcade(
    operation_mode=OperationMode.OFFLINE,
    environments_dir="environment_files",
).listen_and_serve(port=8001)
```

This exposes the command routes described below plus
`GET /api/healthcheck`.

## Actions

The exact engine enumeration is:

| ID | Name | Payload | Common UI binding, not a universal meaning |
|---:|---|---|---|
| 0 | `RESET` | none | start/retry/reset |
| 1 | `ACTION1` | none | up / W |
| 2 | `ACTION2` | none | down / S |
| 3 | `ACTION3` | none | left / A |
| 4 | `ACTION4` | none | right / D |
| 5 | `ACTION5` | none | interact / space |
| 6 | `ACTION6` | `x`, `y` integers in `0..63` | click |
| 7 | `ACTION7` | none | undo where supported |

Coordinates use a top-left origin: `x` increases horizontally and `y`
vertically. The common bindings are interface conventions, not semantic facts;
games can interpret legal actions differently.

`ActionInput` contains:

```text
id: GameAction = RESET
data: dict = {}
reasoning: any JSON-serializable value or null
```

The documented reasoning limit is 16 KiB. Reasoning is metadata for audit and
must not be treated as part of game state.

### Dynamic legality

The engine returns `available_actions` with every observation. This can change
during a game, so consumers must not cache `wrapper.action_space`, a metadata
tag, or the first frame's list as permanent legality.

Current public games normally do not put `RESET` in `available_actions`.
RESET is an engine control operation and must be handled separately. ARCWorld
accepts RESET independently but rejects any non-reset action absent from the
current observation before spending it.

## Observation and animation format

The serializable `FrameData` fields are:

```text
game_id: str
frame: list[list[list[int]]]       # one or more 64×64 frames
state: GameState
levels_completed: int in 0..254
win_levels: int in 0..254
action_input: ActionInput
guid: str | null
full_reset: bool
available_actions: list[int]
```

`FrameDataRaw` has the same metadata but holds `frame` as a runtime-only
`list[numpy.ndarray]`; local and remote conversion use signed 8-bit arrays.
Serialization of `FrameDataRaw` does not include the runtime frame field.

`GameState` is:

```text
NOT_PLAYED
NOT_FINISHED
WIN
GAME_OVER
```

Every externally rendered frame is exactly 64×64 with integer cells in
`0..15`. A game's internal camera can be smaller. ARCEngine scales it uniformly
with nearest-neighbor interpolation and letterboxes it to 64×64. Object
measurements in rendered coordinates can therefore include scale and padding
that are not native mechanics.

An action can produce consecutive animation frames until the game calls
`complete_action`. The engine has a nominal 1,000-frame guard; its current loop
can render the boundary frame before raising on the next iteration. Code should
impose a tighter research-side resource limit rather than depend on this guard.

The final animation frame is the stable post-action state. Earlier frames remain
evidence: they can distinguish translation, replacement, collision, projectile
motion, and delayed effects. The event ledger must keep all of them even if
perception and planning primarily use `observation.latest`.

### Palette

| Index | Meaning | RGBA/hex |
|---:|---|---|
| 0 | white | `#FFFFFFFF` |
| 1 | light gray | `#CCCCCC` |
| 2 | gray | `#999999` |
| 3 | dark gray | `#666666` |
| 4 | darker gray | `#333333` |
| 5 | black | `#000000` |
| 6 | magenta | `#E53AA3` |
| 7 | light magenta | `#FF7BCC` |
| 8 | red | `#F93C31` |
| 9 | blue | `#1E93FF` |
| 10 | light blue | `#88D8F1` |
| 11 | yellow | `#FFDC00` |
| 12 | orange | `#FF851B` |
| 13 | maroon | `#921231` |
| 14 | green | `#4FCC30` |
| 15 | purple | `#A356D6` |

These names are display names, not game semantics. Perception should represent
the integer index losslessly and attach semantic hypotheses separately.

## Reset and level-transition semantics

The following behavior comes from ARCEngine 0.9.3, not an inference from UI
labels:

1. `RESET` is dispatched through `handle_reset` before ordinary action logic.
2. If `ONLY_RESET_LEVELS` is true and the game is not already won, the engine
   performs a level reset.
3. Otherwise, if the current level's internal action count is zero or the game
   state is `WIN`, it performs a full reset.
4. Otherwise, it performs a level reset.

A **full reset** clones every clean level, sets score/progress to the beginning,
selects level zero, and reports `full_reset=True`.

A **level reset** clones only the current clean level, retains the number of
completed levels, and reports `full_reset=False`.

The internal per-level action count excludes RESET and returns to zero on every
level transition or reset. Therefore:

```text
played action -> RESET       = reset current level
played action -> RESET -> RESET = second reset sees zero actions and resets full game
WIN -> RESET                 = full reset outside competition constraints
```

Competition mode coerces/blocks full reset behavior so a contestant cannot
start a new scoreable run. Do not use the two-reset pattern there.

The constructor's initial reset starts a play but is not counted as a submitted
action. A later level reset increments both action and reset counts in the
scorecard. `ACTION1..ACTION7` count as actions.

`next_level()` increments `levels_completed`. If no level remains, the state
becomes `WIN`; otherwise the next level can be rendered within the same returned
animation sequence. Actions after a terminal state are rejected; the hosted
documentation describes HTTP 400 and RESET as the only terminal recovery.

These semantics make reset evidence special. A transition verifier must record
whether a reset was full or level-only and must never collapse both into one
generic “initial state.”

## Public game catalog

This table combines the hosted descriptor metadata with local instantiation of
the exact downloaded source versions on 2026-07-26.

- `A1` through `A7` denote action IDs 1 through 7.
- `baseline_actions` is the metadata's ordered per-level list.
- The runtime action column was read from each instantiated environment, not
  inferred from its tag.
- The 25 games contain 183 levels total.

| Full game ID | Levels | Runtime actions | Metadata tag | FPS | `baseline_actions` |
|---|---:|---|---|---:|---|
| `ar25-0c556536` | 8 | A1,A2,A3,A4,A5,A6,A7 | keyboard_click | 6 | 32, 50, 75, 37, 89, 159, 233, 73 |
| `bp35-0a0ad940` | 9 | A3,A4,A6,A7 | keyboard_click | 20 | 21, 48, 44, 38, 33, 87, 86, 131, 163 |
| `cd82-fb555c5d` | 6 | A1,A2,A3,A4,A5,A6 | keyboard_click | 30 | 55, 8, 41, 21, 23, 23 |
| `cn04-2fe56bfb` | 6 | A1,A2,A3,A4,A5,A6 | keyboard_click | 5 | 29, 54, 85, 300, 208, 113 |
| `dc22-fdcac232` | 6 | A1,A2,A3,A4,A6 | keyboard_click | 15 | 59, 102, 67, 98, 324, 578 |
| `ft09-0d8bbf25` | 6 | A6 | — | 8 | 43, 12, 23, 28, 65, 37 |
| `g50t-5849a774` | 7 | A1,A2,A3,A4,A5 | keyboard | 30 | 78, 175, 179, 230, 96, 54, 67 |
| `ka59-38d34dbb` | 7 | A1,A2,A3,A4,A6 | keyboard_click | 10 | 28, 109, 51, 51, 33, 132, 326 |
| `lf52-271a04aa` | 10 | A1,A2,A3,A4,A6,A7 | click | 30 | 32, 81, 60, 71, 205, 148, 244, 109, 164, 225 |
| `lp85-305b61c3` | 8 | A6 | click | 20 | 17, 38, 31, 16, 41, 60, 26, 159 |
| `ls20-9607627b` | 7 | A1,A2,A3,A4 | keyboard | 30 | 22, 123, 73, 84, 96, 192, 186 |
| `m0r0-492f87ba` | 6 | A1,A2,A3,A4,A5,A6 | keyboard_click | 7 | 30, 111, 203, 26, 500, 237 |
| `r11l-495a7899` | 6 | A6 | click | 30 | 22, 33, 51, 26, 52, 49 |
| `re86-8af5384d` | 8 | A1,A2,A3,A4,A5 | keyboard_click | 25 | 26, 42, 86, 108, 189, 139, 424, 241 |
| `s5i5-18d95033` | 8 | A6 | click | 15 | 20, 89, 106, 54, 162, 38, 86, 83 |
| `sb26-7fbdac44` | 8 | A5,A6,A7 | keyboard_click | 30 | 18, 28, 18, 19, 31, 23, 58, 18 |
| `sc25-635fd71a` | 6 | A1,A2,A3,A4,A6 | keyboard_click | 20 | 36, 6, 32, 83, 143, 50 |
| `sk48-d8078629` | 8 | A1,A2,A3,A4,A6,A7 | keyboard_click | 30 | 61, 177, 101, 103, 230, 181, 125, 92 |
| `sp80-589a99af` | 6 | A1,A2,A3,A4,A5,A6 | keyboard_click | 10 | 39, 58, 25, 148, 96, 152 |
| `su15-1944f8ab` | 9 | A6,A7 | click | 20 | 22, 42, 26, 115, 36, 31, 8, 40, 41 |
| `tn36-ef4dde99` | 7 | A6 | click | 3 | 32, 72, 26, 40, 30, 55, 62 |
| `tr87-cd924810` | 6 | A1,A2,A3,A4 | keyboard | 10 | 54, 58, 40, 45, 71, 146 |
| `tu93-0768757b` | 9 | A1,A2,A3,A4 | keyboard_click | 30 | 19, 16, 34, 42, 123, 80, 14, 23, 111 |
| `vc33-5430563c` | 7 | A6 | click | 20 | 7, 18, 44, 61, 131, 34, 152 |
| `wa30-ee6fef47` | 9 | A1,A2,A3,A4,A5 | keyboard | 5 | 71, 119, 183, 98, 368, 68, 79, 442, 415 |

Metadata tag counts were 13 `keyboard_click`, 7 `click`, 4 `keyboard`, and one
untagged game. Two concrete reasons not to derive legality from the tag:

- `lf52` is tagged `click` but its runtime space contains four directions and
  undo as well as click;
- `tu93` is tagged `keyboard_click` but its runtime space has no click action.

Initial reset returned one frame in 23 games and two frames in `bp35` and
`lf52`. Every inspected frame was 64×64.

Every current public constructor had signature `()`. The SDK only forwards
`seed` if the downloaded environment subclass declares it, so `seed=` is inert
for these exact versions. Keep it in interfaces for future games, but do not
claim reproducibility was seed-controlled when the constructor ignored it.

The full versioned ID should be pinned in experiments. A four-character base ID
asks the local SDK to select a matching/latest cached version and therefore does
not fully specify an experiment.

## Hosted REST protocol

SDK 0.9.9 preserves a shared `requests.Session` cookie jar because the hosted
service uses session affinity cookies such as `AWSALB*`. A client that recreates
requests independently can lose its game session even with the correct GUID.

### Discovery

```http
GET /api/games
X-API-Key: ...
```

The live response contained objects with `game_id`, `title`, optional `tags`,
and `baseline_actions`. The public OpenAPI only promises `game_id` and `title`.

SDK-used routes absent from the OpenAPI file:

```http
GET /api/games/{base-or-full-game-id}
GET /api/games/{full-game-id}/source
GET /api/games/anonkey
```

The detail route returns metadata; the source route returns Python source text;
the anonymous-key route returns `{"api_key": ...}`.

### Scorecards

```http
POST /api/scorecard/open
{"source_url": "<optional URI>", "tags": ["optional"], "opaque": {"optional": "data"}}
-> {"card_id": "..."}

POST /api/scorecard/close
{"card_id": "..."}

GET /api/scorecard/{card_id}
GET /api/scorecard/{card_id}/{game_id}
```

`opaque` is limited to 16 KiB. Competition mode adds managed constraints not
represented by merely calling these endpoints.

### Commands

Start a play:

```http
POST /api/cmd/RESET
{"game_id": "ls20-9607627b", "card_id": "..."}
```

Reset an existing play:

```http
POST /api/cmd/RESET
{"game_id": "ls20-9607627b", "card_id": "...", "guid": "..."}
```

Simple actions:

```http
POST /api/cmd/ACTION1
...
POST /api/cmd/ACTION5
POST /api/cmd/ACTION7

{"game_id": "...", "guid": "...", "reasoning": {"optional": "metadata"}}
```

Coordinate action:

```http
POST /api/cmd/ACTION6
{
  "game_id": "...",
  "guid": "...",
  "x": 0,
  "y": 63,
  "reasoning": {"optional": "metadata"}
}
```

A successful command returns frame data as JSON; `action_input.id` is numeric.
The documented limit is 600 requests/minute. A rate-limit response is HTTP 429
with:

```json
{"error": "RATE_LIMIT_EXCEEDED", "message": "rate limit has been exceeded"}
```

The hosted API is best-effort and has no stated availability SLA. ARCWorld's
real-action executor should therefore distinguish transport failure from game
transition mismatch; neither is evidence that a world rule is wrong.

## Recordings and replay

### SDK wrapper JSONL

With `save_recording=True`, the wrapper writes:

```text
<recordings_dir>/<scorecard_id>/<full-game-id>-<guid>.jsonl
```

Each line has:

```json
{
  "timestamp": "ISO-8601",
  "data": {
    "game_id": "ls20-9607627b",
    "state": "NOT_FINISHED",
    "levels_completed": 0,
    "win_levels": 0,
    "action_input": {
      "id": "ACTION1",
      "data": {},
      "reasoning": {}
    },
    "guid": "...",
    "full_reset": false,
    "available_actions": [1, 2, 3, 4],
    "frame": [[[0, 0]]]
  }
}
```

The shown frame is abbreviated. `frame` is omitted from the record when
`include_frame_data=False`; other fields remain. The constructor's initial
RESET is the first record.

### Agents/benchmark JSONL

The Agents-style recorder uses:

```text
<RECORDINGS_DIR>/<game>.<agent-class>.anim7.<uuid>.recording.jsonl
```

Its event envelope is also `{timestamp, data}`. Gameplay records contain
serializable FrameData; cleanup can append the scorecard.

### Current benchmarking detail records

The official benchmarking repository additionally creates:

```text
recordings/<agent-name>.<run-uuid>/
  run_meta.json
  step_001.json
  step_002.json
  ...
```

A step contains:

```text
step, timestamp, duration_seconds, model, messages_sent,
assistant_response, reasoning, parsed_action, usage, retries
```

Run metadata contains:

```text
run_id, game_id, agent_name, model, started_at, ended_at,
duration_seconds, total_steps, total_usage, outcome, run_dir
```

Malformed provider responses can also create diagnostic JSON files. This richer
format is a useful reference for ARCWorld's audit ledger, although ARCWorld
must additionally record predicted simulator states, candidate rule version,
verification result, and action-queue cancellation.

Hosted scorecards and plays can be viewed at:

```text
https://arcprize.org/scorecards/<card_id>
https://arcprize.org/replay/<guid>
```

## Official baseline and packaging tools

### ARC-AGI-3-Agents

```bash
git clone https://github.com/arcprize/ARC-AGI-3-Agents.git
cd ARC-AGI-3-Agents
cp .env.example .env
uv sync
uv run main.py --agent=random --game=ls20
uv run main.py --agent=random
pytest
```

The repository contains random, fast/reasoning/guided LLM, multimodal,
LangGraph, SmolAgents, and OpenClaw examples. They are educational templates,
not one stable reference implementation. Several use external providers, and
parts lag the current engine schema. Reuse the small agent contract, not stale
conversion or prompt code.

### Current official benchmarking harness

```bash
git clone https://github.com/arcprize/arc-agi-3-benchmarking.git
cd arc-agi-3-benchmarking
uv venv
uv sync
cp .env.example .env
uv run main.py --list-games
uv run main.py --list-configs
uv run main.py --game=ls20 --config=openai-gpt-5-4-2026-03-05
uv run main.py --config=openai-gpt-5-4-2026-03-05
```

When no game is specified, it runs one thread per game under one online
scorecard. The baseline gives the model:

- a minimal “play and win” system prompt;
- state and completed-level count;
- exact text rows for the raw palette grid;
- at most seven uniformly sampled animation frames;
- dynamically available actions.

It executes the **last valid action name mentioned** in the model response.
For `ACTION6`, it parses two 0–63 integers separated by whitespace/comma, with
optional colon or parentheses. It retries three times after the first request,
for at most four attempts.

Current model configs set a per-level action budget to:

```text
ceil(metadata baseline_actions[level] × 5)
```

The agent stops as soon as a level reaches its budget. Total budget is the sum
of level budgets; wall time defaults to 12 hours; representative configs use a
175,000-token context limit. The repository supports OpenAI Chat Completions
and Responses, native Anthropic, Gemini-compatible/OpenAI endpoints,
OpenRouter, and other providers. This is a measurement baseline, not a
world-model architecture.

Official Dockerfile:

```bash
docker build -t arc-agi-3-benchmarking .
docker run --env-file .env arc-agi-3-benchmarking
docker run --env-file .env arc-agi-3-benchmarking \
  python main.py --game=ls20 --config=openai-gpt-5-4-2026-03-05
```

It uses Python 3.12 and runs as non-root UID 10001. The core SDK and Agents
repository do not publish a Dockerized local game service. The Agents tree has
a separate third-party OpenClaw gateway compose file, which is not required for
ARCWorld.

One implementation defect to preserve in comparative reports: the shared base
loop checks `action_counter <= MAX_ACTIONS`, which can permit one action beyond
the nominal total budget even though the benchmarking subclass also checks its
per-level budget.

### Kaggle starter

```bash
git clone https://github.com/arcprize/ARC-AGI-3-Kaggle-Starter.git
cd ARC-AGI-3-Kaggle-Starter
mkdir -p .kaggle
# Put the Kaggle token in .kaggle/access_token, then:
chmod 600 .kaggle/access_token
make setup
make play-local
make play-local GAME=ls20
make verify-local
make list-games
make pull-sample
make notebook
make submit
make status
```

In a Kaggle rerun, the notebook installs offline wheels from:

```text
/kaggle/input/competitions/arc-prize-2026-arc-agi-3/arc_agi_3_wheels
```

It copies the bundled Agents framework, waits for managed
`http://gateway:8001`, and uses the gateway through the online wrapper.
Competition input also contains `ARC-AGI-3-Agents` and `environment_files`.
`KAGGLE_IS_COMPETITION_RERUN` separates the managed scoring run from local
notebook execution. A non-rerun writes a placeholder parquet with columns
`row_id`, `game_id`, `end_of_game`, and `score`; the managed gateway produces
the real `submission.parquet`.

### Stochastic Goose sample

The official
[sample notebook](https://www.kaggle.com/code/inversion/arc3-sample-submission-stochastic-goose)
adapts [Dries Smit's ARC3-solution](https://github.com/DriesSmit/ARC3-solution).
It is an online novelty learner:

- 16-channel one-hot 64×64 input;
- convolution widths 32, 64, 128, and 256;
- a five-logit action head and a 4,096-logit coordinate head;
- binary supervision for whether the next frame differs;
- a 200,000-example deduplicated replay buffer;
- batch size 64 and training every five actions;
- action masking and stochastic sampling;
- model and buffer reset on each new level.

It learns where an action is likely to change the frame, not which changes
advance the goal. It supplies a useful reactive exploration baseline but no
explicit goal inference, causal simulator, replay-certified rules, or
multi-step planning.

## Known documentation and implementation inconsistencies

These are concrete observed discrepancies, not speculative risks.

| Surface | Discrepancy | Engineering response |
|---|---|---|
| OpenAPI state enum | Says `NOT_STARTED`; engine/SDK use `NOT_PLAYED` | Normalize explicitly at an API boundary; use engine value internally |
| OpenAPI available-actions enum | Omits action ID 7 | Accept the engine's full `0..7` enumeration |
| OpenAPI `action_input.id` description | Describes a client/sequential index | Treat it as the action ID |
| OpenAPI score fields | Declares integers | SDK scorecard values can be floats |
| OpenAPI routes | Omits game detail, game source, and anonymous key | Do not infer the complete live protocol from OpenAPI alone |
| Games documentation | Says list is alphabetical | Live response order was not alphabetical | Sort only for display; do not derive meaning from order |
| Public FrameResponse | Omits `full_reset` | Preserve local `full_reset`; tolerate absence remotely |
| Remote wrapper | Rebuilds FrameData without propagating response `full_reset` | Never infer reset kind solely from the online field |
| Reasoning request | Docs say object; remote wrapper applies `json.dumps` first | Treat hosted reasoning encoding as version-specific; test it |
| Recording docs | Example uses old `score` field | Use `levels_completed` and actual 0.9.9 records |
| Local-vs-online docs | Say local toolkit has no recording | Local `save_recording=True` works in 0.9.9 |
| Agent creation docs | Refer to nonexistent `agents.structs` and omit A7 | Import current engine types and test A7 |
| SDK `main.py` example | Reverses the complex-action data conditional | Follow SDK README/quickstart and engine API instead |
| Older Agents conversion | Drops `action_input`, so it defaults to RESET in serialized playback | Copy `raw.action_input`; official benchmarking repo now does |
| Benchmark docs | Show `python -m arcagi3.runner --check` | Current repository package is `benchmarking`; entry is `main.py` |
| Metadata tags | Do not match runtime actions in all games | Trust per-observation `available_actions` |
| Seed parameter | Present in `make`, absent from every current public constructor | Record both requested seed and whether the environment consumed it |

The discrepancy between remote `full_reset` and the local engine deserves
particular care. Reset mode affects replay admission. If the hosted field is
missing or always false, infer a candidate reset class from known action
history but mark it uncertain rather than rewriting evidence as a definite
level reset.

## Implications for ARCWorld

### Environment boundary

The core should consume only:

```text
Action(kind, optional x/y)
Observation(all frames, status, dynamic actions, progress, reset flag, IDs)
```

Official SDK objects stay behind the adapter. `arcengine` is imported only when
an official action is encoded. Model prompts must use identity-redacted
serialization and must not receive game ID, catalog metadata, human baselines,
source code, or these research notes.

### Evidence ledger

For every real operation, preserve:

- exact pre-action observation;
- exact `Action`;
- every returned animation frame;
- state, progress, GUID, and reset flag;
- current advertised action set;
- executor reasoning metadata;
- transport/runtime error separately from state mismatch.

Summary frames, objects, relations, and learned rules are indexes over this
ledger, never replacements for it.

### Simulator verification

Simulator comparison should have at least two layers:

1. strict palette-grid equality for claims that purport to reproduce rendering;
2. structured-state/effect comparison for partially correct hypotheses.

All accepted rule revisions must replay the entire known transition history,
including level boundaries and both reset classes. Animation-frame prediction
should be scored separately from stable-final-state prediction so a correct
mechanic is not discarded solely because it lacks cosmetic tweening.

### Experiment records

Every reported result should pin:

- full versioned game IDs;
- `arc-agi` and `arcengine` versions;
- acquisition date of public sources;
- operation mode;
- model and reasoning effort;
- action-budget multiplier and wall-time limit;
- run count and selection rule;
- whether the public games were used for development or adaptation;
- whether `seed` was actually accepted by the game constructor.

The public catalog is development evidence. A system tuned to these 25 source-
available games must not be described as demonstrating private-game
generalization.

## Remaining gaps

- Hosted response behavior around `full_reset` should be probed again whenever
  the SDK or API version changes.
- The live catalog and exact source hashes should be snapshotted before each
  reproducible experiment; versioned IDs alone are better than base IDs but do
  not replace a content hash.
- Future games may accept `seed`, change actions during play, use more animation
  frames, or expose different internal camera sizes. The adapter intentionally
  avoids specializing to the current constructors.
- Competition gateway behavior can differ from the public hosted endpoint.
  Local tests validate mechanics and integration, not the managed Kaggle
  session contract.
- Official documentation does not provide a complete formal guarantee of
  determinism or observability. The world-model layer must represent stochastic
  and latent-state hypotheses rather than assuming a deterministic Markov grid.
