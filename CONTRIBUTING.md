# Contributing

ARCWorld is organized so that perception, model induction, verification, exploration,
planning, environment access, and visualization can be changed independently.

Set up a development environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e '.[dev,gui,openai]'
ruff check .
mypy
pytest
```

The official environment package is optional:

```bash
python -m pip install -e '.[arc]'
```

Place legally obtained public environment files under `environment_files/`. That
directory is deliberately ignored. Do not add task-specific rules or public-game
walkthroughs to prompts, fixtures, or default models.

For a new experiment, record:

1. A falsifiable question and frozen configuration.
2. Model identifiers, reasoning efforts, and prompt hashes.
3. Split and evaluation protocol.
4. Every transition and model revision.
5. Pass@1 results before any best-of-k diagnostic.
