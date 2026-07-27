# Working agreement

This repository is an experiment harness, not a collection of game-specific solutions.

- Keep `src/arcworld/agent.py` declarative and short. Put mechanisms in focused modules.
- Do not commit ARC environment binaries, private replays, API keys, generated model
  workspaces, or competition output.
- Any claim about benchmark performance must name the split, harness, model, reasoning
  effort, run count, selection rule, date, and source.
- Do not expose game IDs, benchmark descriptions, human baselines, prior solutions, or
  internet access to a tested game-playing model. Its context may contain observations,
  available actions, its own history, tool contracts, and generated artifacts only.
- Candidate world models are never promoted until they replay all known transitions.
- Preserve the lossless event log. Summaries are indexes, never replacements for evidence.
- A public-demo result is development evidence, not evidence of private generalization.
- Prefer deterministic unit tests and synthetic blind games over public-game tuning.
- Run `ruff check .`, `mypy`, and `pytest` before merging.
