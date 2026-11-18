Reviewer brief names earlier #root_cause pull requests that changed the same line ranges

Part 3 of GHI [Ask for the root cause at the moments a defect is fixed: fix pull requests, review fix-rounds, and code fixed a third time](https://github.com/nedschorus/nedschorus/issues/1154), as the user approved on 2026-11-17 at 23:18 UTC ("a"), item 59.2 of cold-read-improvement's approval-walk walk-me-through-skill-refactor-approval-walk-2026-11-02 (walk-minutes `nedlern@ned-box:/home/nedlern/agents/cold-read-improvement/docs/walk/walk-me-through-skill-refactor-approval-walk-2026-11-02-minutes.md`).

- `scripts/merge-lane-pull-request-reviewer-brief-compose-with-facts.py`: for each range of lines at the merge base that the pull request changes or deletes (from `git diff -U0`), `git log --first-parent -L` from the merge base finds the `Merge pull request #N` merges that changed the range. When two or more of those pull requests have a `#root_cause` line (or the older `Root cause:` form) in the merged pull requests' descriptions the program already reads once per invocation, the brief carries one fact line naming each such range with its pull request numbers, then each of those pull requests once with its title and link. No model and no new gh call. Fewer than two per range: no line.
- `scripts/merge-gate.sh`: no change. The note the item asked to remove was designed in the GHI-MD but never built, so `scripts/merge-gate.sh` has no note, test or helper to remove.
- `docs/issues/1154-ask-for-the-root-cause-at-the-moments.md`: item 3 now describes the fact line, not a note from `scripts/merge-gate.sh`. The paragraph about the start conditions is dropped, and so is the weekly review of them, and the provisional additions about the check and the research. The intro and the next action are updated to match.
- `docs/issues/1518-...-proposed-hashtag.md`: rows 60 and 73 cite the composer's moved line numbers, and the new reader of `Merge pull request #<n> `.
- Tests: a scratch repository with real `--no-ff` merges covers these cases: a range two #root_cause pull requests changed, in either form, is named, and a pull request in two ranges is listed once; a range only one changed is not; a direct commit, a pull request with only a not-fixed line, and a merge gh does not list are not counted; a deleted line beginning `-- ` is not read as a patch header; no extra gh call is made; and `git log -L` failing (injected by a git wrapper on PATH) exits 1 and writes no brief.
- Measured on 11 recent merges with the real merged descriptions, the line would appear on 10. It would name 0 to 8 pull requests on small changes and 25, 42, 216, 559 and 621 on large ones. Composing it takes 0.1 to 10 s for most pull requests and 63 to 267 s for the three largest, which had 1,323 to 5,631 changed ranges. Approval item 59.2 expected the line on about a third of reviews, at a few dozen words. Whether to cap the line, or to narrow the rule, is not settled.

#no_defect_fixed

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01QHxb4kaDsGeMeN2Z3KsDLT
