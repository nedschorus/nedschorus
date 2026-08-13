---
name: ghi-write
description: Use BEFORE any write that touches a GitHub issue in this project — filing a new issue, editing an issue body, commenting on an issue, or promoting queue material into an issue. Deciding whether material should become an issue also triggers it, because routing that decision is part of the skill. Not for merely reading or citing an issue.
---

# ghi-write

## When Used

Before filing a new issue, editing an issue body, commenting on an issue, or deciding whether material belongs in an issue.

## What to do

1. Ask before filing. Put the subject to ghi-info, the project's issue-knowledge agent, as a question — the ask command and its fallback ladder are under How to do it; read the issues it returns and the documents they cite. When an existing issue or pair document covers the subject — the same matter, not merely the same area — edit that artifact; revision is the default disposition. A failed ask does not block the write: fall down the ladder and proceed under these rules.
2. Route by state. Every artifact this skill routes is either at its home or in a named queue with a drain:
   - Material whose fate is not yet decided goes to a queue, not to an issue: `docs/wiki/queue/` for wiki-bound doctrine, `docs/issues/queue/` for pair-bound MDs; a candidate issue queues as a `draft`-labeled issue — the label is the issue world's queue membership.
   - Anything carrying pending state — a wanted feature or component, an open question, a commitment to act — gets a GHI (GitHub issue): an MD-GHI pair when substantial working material rides with it, issue-only otherwise, and the issue body stays under 500 words either way — a body that cannot is carrying pair material. The body carries the summary, the pair MD the substance; the pair sequence is write the MD, land it on main, then cite it from the issue.
   - Final reference content awaiting nothing is a bare MD at its home.
   - The discriminator: the GHI carries state, the MD carries substance, the queue holds the not-yet-decided. When the routing is genuinely ambiguous, file a `draft`-labeled issue and move on.
3. Revise by editing the body. A clarification, correction, or scope change edits the issue body, including fixes to references already in it. A comment is only for a genuinely new event — an instance outcome (one run of a recurring process the issue tracks, while the issue stays open), or a challenge to a ruling the issue records. Completion is not a comment: record the outcome in the body, then close the issue with its reason. Where an edit to the existing issue is sufficient, no second issue is filed; work that needs its own lifecycle — its own next action and its own closure — is a new issue, not an edit. (This overrides the default habit of stacking comments and new records; the edit history preserves the before/after.)
4. Write for a zero-context reader. Before submitting, check the three tests: the subject is identifiable from the issue alone (the body plus what it cites); the why is stated; the next action is executable by a reader who was not in this conversation.
5. Make every reference openable and every claim checked:
   - A file reference must open from the reader's seat: full URLs for anything outside this repository; in-repo paths verified present on main before citing.
   - Run the cheap verifications before submitting — a check one grep or one `gh` call answers is run now, so the body states what is, not what might be.
   - An absence claim carries its search receipt: the query and the scope that came up empty.

## How to do it

- Ask: `scripts/ghi-info-ask.py "<question>"`; add `--include-closed` when asking about precedent or absence. When the ask fails, fall back in order: grep `ghi-mirror/` in the checkout when present (stale unless freshly regenerated), then `gh issue list --repo nedschorus/nedschorus --state all --limit 100 --search "<terms>"`, and grep the repository for pair documents on the subject.
- File: `gh issue create --repo nedschorus/nedschorus --title "<title>" --body-file <file>`.
- Edit: `gh issue edit <number> --repo nedschorus/nedschorus --body-file <file>`.
- Close: after the body edit recording the outcome, `gh issue close <number> --repo nedschorus/nedschorus --reason "completed"` (or `"not planned"`, `"duplicate"`).
- Comment (the two catalog events only): submit through the write tool `scripts/ghi-issue-write.py`'s comment verb naming the event kind; the write path denies plain `gh issue comment`. Until [nedschorus#46](https://github.com/nedschorus/nedschorus/issues/46) builds the tool, plain `gh issue comment` naming the event kind is the interim path.
- Compose bodies in a scratch file outside the repository and pass `--body-file`; an inline `--body` is easily mangled by shell quoting (backticks especially).
- Queue routing: write the queue file under its destination directory, or add the `draft` label to the issue; the drain process is [nedschorus#24](https://github.com/nedschorus/nedschorus/issues/24).
- The machinery named here — ghi-info, `ghi-mirror/`, the write tool, the write path — is specified in `docs/issues/46-ghi-info-agent-design.md` and built under [nedschorus#46](https://github.com/nedschorus/nedschorus/issues/46); the routing doctrine (queues, homes, the drain) is `docs/cross-project/nedschorus-founding-plan.md` § Project organization.
