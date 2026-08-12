---
name: ghi-write
description: Use BEFORE any write that touches a GitHub issue in this project — filing a new issue, editing an issue body, commenting on an issue, or promoting queue material into an issue. Creating or revising any project artifact that might belong in an issue also triggers it, because routing is part of the skill. Not for merely reading or citing an issue.
---

# ghi-write

## When Used

Before filing a new issue, editing an issue body, commenting on an issue, or writing project material whose home (issue, queue, or MD) is not yet decided.

## What to do

1. Ask before filing. Put the subject to ghi-info by running scripts/ghi-info-ask.py with the question (add `--include-closed` when asking about precedent or absence); read the issues it returns and the pair documents they cite. When an existing artifact covers the subject, edit that artifact — a revision of the existing issue is the default disposition, the same way md-write defaults to REVISE. A failed ask never blocks the write: fall back to grepping the local mirror, then `gh` search, and proceed under these rules.
2. Route by state. Every artifact is either final at its home or in a named queue with a drain:
   - Material whose disposition is not yet decided goes to its destination queue — `docs/wiki/queue/` for wiki-bound doctrine, `docs/issues/queue/` for pair-bound MDs, the `draft` label for queued issues — with no GHI.
   - Anything carrying pending state — a wanted feature or component, an open question, a commitment to act — gets a GHI: issue-only when the body stays under 500 words, an MD-GHI pair when substantial working material rides with it. The body carries the summary, the pair MD the substance; the pair sequence is write the MD, land it, then cite it from the issue.
   - Final reference content awaiting nothing is a bare MD at its home.
   - The discriminator: the GHI carries state, the MD carries substance, the queue holds the not-yet-decided. When the routing is genuinely ambiguous, file a `draft`-labeled issue and move on; ambiguity never blocks the write.
3. Revise by editing the body. A clarification, correction, or scope change edits the issue body, including fixes to references already in it. A comment is only for a genuinely new event — an instance outcome, or a challenge to a ruling. Completion is not a comment: record the outcome in the body, then close the issue with its reason. A second issue is never filed where an edit to the first serves. (This overrides the default habit of stacking comments and new records; the edit history preserves the before/after.)
4. Write for a zero-context reader. Before submitting, check the three tests: the subject is identifiable from the issue alone; the why is stated; the next action is executable by a reader who was not in this conversation.
5. Make every reference openable and every claim checked:
   - A file reference must open from the reader's seat: full URLs for anything outside this repository; in-repo paths verified present on main before citing.
   - Run the cheap verifications before filing — a check one grep or one `gh` call answers is run now, so the body states what is, not what might be.
   - An absence claim carries its search receipt: the query and the scope that came up empty.

## How to do it

- Ask: `scripts/ghi-info-ask.py "<question>"`; add `--include-closed` when asking about precedent or absence. When the ask fails, fall back in order: grep `ghi-mirror/` in the checkout (stale unless freshly regenerated), then `gh issue list --repo nedschorus/nedschorus --state all --search "<terms>"`, and grep the repository for pair documents on the subject.
- File: `gh issue create --repo nedschorus/nedschorus --title "<title>" --body-file <file>`.
- Edit: `gh issue edit <number> --repo nedschorus/nedschorus --body-file <file>`.
- Close: after the body edit recording the outcome, `gh issue close <number> --repo nedschorus/nedschorus --reason "completed"` (or `"not planned"`).
- Comment (the two catalog events only): resubmit through the write tool `scripts/ghi-issue-write.py`'s comment verb naming the event kind; plain `gh issue comment` is denied by the write path.
- Compose bodies in a file and pass `--body-file`; an inline `--body` with backticks is silently mangled by the shell.
- Queue routing: write the queue file under its destination directory, or add the `draft` label to the issue; the drain process is [nedschorus#24](https://github.com/nedschorus/nedschorus/issues/24).
