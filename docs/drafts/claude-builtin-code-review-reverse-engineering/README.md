# Claude's built-in code-review, reverse-engineered (rescued working material)

Four documents extracted 2026-08-21 (session e8a84999, the
miami-nba-playoff-history worktree) by running `strings` over the claude CLI
binary (2.1.235): the built-in /code-review's prompt reconstructed, the
engineering:code-review plugin skill for comparison, the legacy /simplify
prompt, and a human-readable explanation of the xhigh path. Rescued from the
session scratchpad on the user's word 2026-08-22 — he is analyzing whether
only the xhigh/max review path serves his review-quality work (context: the
merge-lane review-quality thread). Version-bound: re-extract against newer
CLI versions before trusting details.
