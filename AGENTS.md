# nedschorus — repository rules for Codex agents

This file is the durable home for repository rules addressed to agents on
the Codex runtime — the GitHub review bot and `codex exec review` both
read AGENTS.md by Codex's documented mechanism (the pinned invocation is
`scripts/code-review-codex-cell.py`). Claude Code does NOT read this file
(verified 2026-08-20, tools-disallowed probe): the Claude-side home is
CLAUDE.md, so a rule meant for every runtime is deliberately duplicated
into both files — neither copy is derived from the other, and an edit to
one is not seen by the other runtime.

## Reviewing code and pull requests

Defensive tightening: before proposing a guard, validation, or robustness
fix, name the behavior it defends against — something this project's
cooperative, supervised agents actually did (cite it), or concretely will
do. If you cannot name the behavior, raise it as a question for the user,
not as a finding. Do not propose hardening against deliberate attackers:
this fleet's failures are accidents between cooperative agents
(user-ruled 2026-08-20).

## Writing instructions

- When writing instructions, absolute imperatives like 'always' or 'never' can backfire in unforeseen conditions. Use them cautiously.
- Instruction text is read by agents and humans who may have no context beyond the text itself. When any reader has difficulty with it — what it means, or what it explains, recommends, or dictates — expect future readers to share that difficulty: fix the text rather than assuming the standing version is clear. Choose wordings on merit — the best text wins, and nobody's draft, the user's included, wins by authorship; bring real disagreements to the user in the objector's own words. If you find yourself restating words to explain them, rewrite the words that way instead, so they need no explanation.
