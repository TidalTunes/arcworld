# Run attestations

This directory anchors compact, reviewable facts about selected experiments in Git.
Raw ARC environment source, frames, SDK recordings, provider responses, generated model
workspaces, session identifiers, and the SQLite evidence database remain local and
gitignored.

An attestation is not a benchmark score. It records hashes and requirement-level checks
that can be reproduced against the corresponding local event chain.

- [`vc33-live-llm-2026-07-27.json`](vc33-live-llm-2026-07-27.json) — one-action
  infrastructure-legitimacy test on the `vc33-5430563c` Public Demo game.
