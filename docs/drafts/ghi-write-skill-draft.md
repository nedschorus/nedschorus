# ghi-write skill — draft for the user's walk

Proposed text for `.claude/skills/ghi-write/SKILL.md`, built against [nedschorus#13](https://github.com/nedschorus/nedschorus/issues/13) (the commission) and `docs/wiki/queue/skill-authoring-checklist.md` (the authoring rules). Instructions only; the justifying evidence lives in the commission issue.

One tension for the walk: the commission asks for a description "written pushy" (undertriggering is the known failure direction); the checklist calls pushy descriptions a hypothesis to adopt only with false-trigger tests. The draft's description is firm about the trigger class without exhortation — rule which register wins.

## Walk order (opened 2026-08-06, new-vp session 3a11d08f)

1. Purpose and the bar the text is judged by
   *processed 2026-08-07 → accepted (purpose item; no capture)*
2. The description — the trigger
   *open 2026-08-07 — the gate premise this item was parked on is gone; see below.*
   *Parked first against a pre-tool-hook gate on issue writes, on the reasoning that a gate blocking unmediated writes would remove the undertriggering risk the "pushy" register was meant to cover. That direction was then rejected: neither reads nor writes are gated (`ghi-gatekeeper-plan-draft.md`). So no mechanical backstop exists and the description carries the whole trigger alone — the original register question stands unchanged, and the "a hook covers the write path" argument against pushiness is withdrawn. What still bears on this item: the search-first step is being redirected from the agent running its own search to asking a dedicated issue-knowledge agent (`ghi-info-agent-plan-draft.md`), which changes what the skill's step 1 instructs but not what the description must trigger on.*
   *Backstop restored 2026-08-07, changing the calculus again (see `ghi-info-agent-plan-draft.md`, write-time integration): the rewrite-hook-plus-tool design — not a gate; `gh` writes are silently routed through the project tool, which runs the checks and consults ghi-info — means a missed skill trigger no longer causes damage, only a less efficient path (a late duplicate catch, a comment retry). The skill is the layer that front-loads the right behavior so agents are not blocked and made to retry (user framing, 2026-08-07); the hook and tool are the correctness backstop when it does not fire. Consequence for this item when the walk resumes: the description can stay firm — pushy is not needed and its false-trigger test debt is not incurred.*
3. When Used
4. What to do, step 1 — search before filing
5. What to do, step 2 — route by state
6. What to do, step 3 — revise by editing the body
7. What to do, step 4 — write for a zero-context reader
8. What to do, step 5 — openable references and checked claims
9. How to do it
10. Close-out: where the skill file lands and what closes the commission

Everything below the line is the proposed skill file, verbatim.

---

```
---
name: ghi-write
description: Use BEFORE any write that touches a GitHub issue in this project — filing a new issue, editing an issue body, commenting on an issue, or promoting queue material into an issue. Creating or revising any project artifact that might belong in an issue also triggers it, because routing is part of the skill. Not for merely reading or citing an issue.
---

# ghi-write

## When Used

Before filing a new issue, editing an issue body, commenting on an issue, or writing project material whose home (issue, queue, or MD) is not yet decided.

## What to do

1. Search before filing. Search existing issues (open and closed) and the pair documents for the subject. When an existing artifact covers it, edit that artifact — a revision of the existing issue is the default disposition, the same way md-write defaults to REVISE.
2. Route by state. Every artifact is either final at its home or in a named queue with a drain:
   - Material whose disposition is not yet decided goes to its destination queue — `docs/wiki/queue/` for wiki-bound doctrine, `docs/issues/queue/` for pair-bound MDs, the `draft` label for queued issues — with no GHI.
   - Anything carrying pending state — a wanted feature or component, an open question, a commitment to act — gets a GHI: issue-only when lean, an MD-GHI pair when substantial working material rides with it.
   - Final reference content awaiting nothing is a bare MD at its home.
   - The discriminator: the GHI carries state, the MD carries substance, the queue holds the not-yet-decided. When the routing is genuinely ambiguous, file a `draft`-labeled issue and move on; ambiguity never blocks the write.
3. Revise by editing the body. A clarification, correction, or scope change edits the issue body, including fixes to references already in it. A comment is only for a genuinely new event — an instance outcome, a completion, a challenge to a ruling. A second issue is never filed where an edit to the first serves. (This overrides the default habit of stacking comments and new records; the edit history preserves the before/after.)
4. Write for a zero-context reader. Before submitting, check the three tests: the subject is identifiable from the issue alone; the why is stated; the next action is executable by a reader who was not in this conversation.
5. Make every reference openable and every claim checked:
   - A file reference must open from the reader's seat: full URLs for anything outside this repository; in-repo paths verified present on main before citing.
   - Run the cheap verifications before filing — a check one grep or one `gh` call answers is run now, so the body states what is, not what might be.
   - An absence claim carries its search receipt: the query and the scope that came up empty.

## How to do it

- Search: `gh issue list --repo nedschorus/nedschorus --state all --search "<terms>"`, and grep the repository for pair documents on the subject.
- File: `gh issue create --repo nedschorus/nedschorus --title "<title>" --body-file <file>`.
- Edit: `gh issue edit <number> --repo nedschorus/nedschorus --body-file <file>`.
- Compose bodies in a file and pass `--body-file`; an inline `--body` with backticks is silently mangled by the shell.
- Queue routing: write the queue file under its destination directory, or add the `draft` label to the issue; the drain process is [nedschorus#24](https://github.com/nedschorus/nedschorus/issues/24).
```
