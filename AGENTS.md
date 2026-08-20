# nedschorus — repository rules for Codex agents

This file is the durable home for repository rules addressed to agents on
the Codex runtime — the GitHub review bot and `codex exec review` both
read AGENTS.md by Codex's documented mechanism (the pinned invocation is
`scripts/code-review-codex-cell.py`). The Claude-side conventions live in
CLAUDE.md; a rule meant for every runtime appears in both files.

## Reviewing code and pull requests

Defensive tightening: before proposing a guard, validation, or robustness
fix, name the behavior it defends against — something this project's
cooperative, supervised agents actually did (cite it), or concretely will
do. If you cannot name the behavior, raise it as a question for the user,
not as a finding. Do not propose hardening against deliberate attackers:
this fleet's failures are accidents between cooperative agents
(user-ruled 2026-08-20).
