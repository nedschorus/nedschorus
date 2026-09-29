---
name: ghi-write
description: Use BEFORE any write that touches a GitHub issue in this project — filing a new issue, changing what an issue says, commenting on an issue, closing one, or promoting queue material into an issue. Deciding whether material should become an issue or a task also triggers it, because routing that decision is part of the skill. Not for merely reading or citing an issue.
---

# ghi-write

## When Used

Before filing a new issue, changing what an issue says, commenting on an issue, closing one, or deciding whether material belongs in an issue.

## What to do

1. Ask before filing. Put the subject to ghi-info, the project's issue-knowledge agent, as a question — the ask command and its fallback ladder are under How to do it; read the issues it returns and the documents they cite. When an existing issue or GHI-MD covers the subject — the same matter, not merely the same area — edit that artifact; revision is the default disposition. A failed ask does not block the write: fall down the ladder and proceed under these rules.
2. Route by state. Every artifact this skill routes is either at its home or in a named queue with a drain:
   - Material whose fate is not yet decided goes to a queue, not to an issue: `docs/nedschorus-wiki/queue/` for wiki-bound doctrine, `docs/issues/queue/` for MDs on their way to becoming GHI-MDs, `docs/agents/queue/` for agent-instructions; a candidate issue queues as a `draft`-labeled issue — the label is the issue world's queue membership.
   - Work that will become a pull request, or that otherwise suits an issue, gets a GHI. Every GHI is a link-only-GHI: its text is its GHI-MD under `docs/issues/`, and its body is the links to that file and nothing else (user-ruled 2026-09-15). Design substance, working material, a ruling, a measurement: all of it goes in the GHI-MD.
   - Anything else still pending — a commitment, a question waiting on the user, a follow-up — goes on the seat's task list, not into a GHI (user-ruled 2026-09-24: "We use tasks to track items that aren't pr related or otherwise not suitable for a ghi").
   - Final reference content awaiting nothing is a bare MD at its home.
   - The discriminator: the GHI carries work headed for a pull request, its GHI-MD carries the substance, the task list carries everything else pending, and the queue holds the not-yet-decided. When the routing is genuinely ambiguous, file a `draft`-labeled issue and move on.
3. Revise by editing the GHI-MD. Every change to a filed GHI — a clarification, a correction, a scope change, a new event, a challenge to a ruling it records, its outcome — is an edit to its GHI-MD, landed with edit-GHI. There are no issue comments (user-ruled 2026-09-24: "But I don't want comments as agents forget to read them. Better to update the ghi-Md"). Completion is an edit too: record the outcome in the GHI-MD, then close the issue with its reason. Where an edit to the existing GHI-MD is sufficient, no second issue is filed; work that needs its own lifecycle — its own next action and its own closure — is a new GHI, not an edit.
4. Write for a fresh-reader. Before submitting, check the three tests: the subject is identifiable from the GHI-MD alone (plus what it cites); the why is stated; the next action is one a reader who was not in this conversation can take. Give the GHI-MD its /cold-read before filing (user-ruled 2026-09-20).
5. Make every reference openable and every claim checked:
   - A file reference must open from the reader's seat: full URLs for anything outside this repository; in-repo paths verified present on main before citing.
   - Run the cheap verifications before submitting — a check one grep or one `gh` call answers is run now, so the GHI-MD states what is, not what might be.
   - An absence claim carries its search receipt: the query and the scope that came up empty.

## How to do it

- Ask: `scripts/ghi-info-ask.py "<question>"`; add `--include-closed` when asking about precedent or absence. When the ask fails, fall back in order: grep `ghi-mirror/` in the checkout when present (stale unless freshly regenerated), then `gh issue list --repo nedschorus/nedschorus --state all --limit 100 --search "<terms>"`, and grep the repository for GHI-MDs on the subject.
- File: write the GHI-MD, then run `python3 scripts/ghi-issue-write.py create <path-to-ghi-md>` (the create-GHI operation). It asks ghi-info whether an open GHI already covers the file, and refuses if one does. Every refusal says what to do next. Add `--dry-run` to see what it would file.
- Edit: change the GHI-MD, then run `python3 scripts/ghi-issue-write.py edit <path-to-ghi-md>` (the edit-GHI operation). A changed first heading retitles the issue.
- Both operations land the file through a pull request and stop there; merge-lane-2 reviews and merges it. After it merges, run the same command again on the path the run's last line names; that run finishes the issue.
- Close: after the edit recording the outcome has landed, `gh issue close <number> --repo nedschorus/nedschorus --reason "completed"` (or `"not planned"`, `"duplicate"`), with no `--comment`.
- Labels: `gh issue edit <number> --repo nedschorus/nedschorus --add-label <label>` or `--remove-label <label>`. To queue a candidate issue, file it with create-GHI, then add the `draft` label. An issue's title and body belong to the tool.
- A hand-typed `gh issue create`, `gh issue comment`, or `gh issue edit` that changes the body is refused by `.claude/hooks/ghi-issue-write-redirect.py`.
- Queue routing: write the queue file under its destination directory, or add the `draft` label to the issue; the drain process is GHI [Queue drain procedure](https://github.com/nedschorus/nedschorus/issues/24).
- The machinery: ghi-info and `ghi-mirror/` are specified in `docs/issues/46-ghi-info-agent-design.md`, built under GHI [Build ghi-info — the GHI knowledge agent](https://github.com/nedschorus/nedschorus/issues/46); the write tool is `scripts/ghi-issue-write.py`; the routing doctrine (queues, homes, the drain) is `docs/nedschorus-wiki/nedschorus-ai-native-software-development-objective.md` § Project organization.
