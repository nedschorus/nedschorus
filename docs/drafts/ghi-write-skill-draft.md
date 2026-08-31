# ghi-write skill — draft for the user's walk

*Landed 2026-08-12: the ruled text lives at [.claude/skills/ghi-write/SKILL.md](../../.claude/skills/ghi-write/SKILL.md); this draft is the decision trail.*

Proposed text for `.claude/skills/ghi-write/SKILL.md`, built against [nedschorus#13](https://github.com/nedschorus/nedschorus/issues/13) (the commission) and the skill-authoring checklist (the authoring rules; retired 2026-08-30 as obsolete — in git history at `git show 19e2e9b:docs/wiki/queue/skill-authoring-checklist.md`). Instructions only; the justifying evidence lives in the commission issue.

One tension for the walk: the commission asks for a description "written pushy" (undertriggering is the known failure direction); the checklist calls pushy descriptions a hypothesis to adopt only with false-trigger tests. The draft's description is firm about the trigger class without exhortation — rule which register wins. *(Ruled 2026-08-12: the plain register wins; see walk-order item 2.)*

## Walk order (opened 2026-08-06, new-vp session 3a11d08f)

1. Purpose and the bar the text is judged by
   *processed 2026-08-07 → accepted (purpose item; no capture)*
2. The description — the trigger
   *processed 2026-08-12 → accepted: the drafted description stands unchanged, plain register; the commission's "pushy" ask is not adopted and the checklist's false-trigger test debt is not incurred, because the landed backstop (docs/issues/46-ghi-info-agent-design.md § The three-layer stack) makes a missed trigger cost efficiency, not correctness. Commission reconciliation deferred to close-out (item 10).*
   *Parked first against a pre-tool-hook gate on issue writes, on the reasoning that a gate blocking unmediated writes would remove the undertriggering risk the "pushy" register was meant to cover. That direction was then rejected: neither reads nor writes are gated (`ghi-gatekeeper-plan-draft.md`). So no mechanical backstop exists and the description carries the whole trigger alone — the original register question stands unchanged, and the "a hook covers the write path" argument against pushiness is withdrawn. What still bears on this item: the search-first step is being redirected from the agent running its own search to asking a dedicated issue-knowledge agent (`ghi-info-agent-plan-draft.md`), which changes what the skill's step 1 instructs but not what the description must trigger on.*
   *Backstop restored 2026-08-07, changing the calculus again (see `ghi-info-agent-plan-draft.md`, write-time integration): the rewrite-hook-plus-tool design — not a gate; `gh` writes are silently routed through the project tool, which runs the checks and consults ghi-info — means a missed skill trigger no longer causes damage, only a less efficient path (a late duplicate catch, a comment retry). The skill is the layer that front-loads the right behavior so agents are not blocked and made to retry (user framing, 2026-08-07); the hook and tool are the correctness backstop when it does not fire. Consequence for this item when the walk resumes: the description can stay firm — pushy is not needed and its false-trigger test debt is not incurred.*
3. When Used
   *processed 2026-08-12 → accepted: the section stands as drafted — it names the three homes (issue, queue, MD) so "home not yet decided" is checkable, and does not repeat the description's load-time exclusion.*
4. What to do, step 1 — search before filing
   *processed 2026-08-12 → revised: step 1 rewritten from search-first to ask-first per the landed design (docs/issues/46-ghi-info-agent-design.md § The ask path) — ask ghi-info via scripts/ghi-info-ask.py, read what it returns, edit-over-file unchanged; the author's own search demotes to the fallback ladder (mirror grep, then gh search), and a failed ask never blocks the write. The ladder also covers the pre-build window while nedschorus#46 is open: a missing script is just a failed ask. Applied to the skill text below; the How-to command lines follow at item 9; the landing-sequence question is carried at item 10.*
5. What to do, step 2 — route by state
   *processed 2026-08-12 → revised: the pending-state bullet now says plainly "under 500 words" (user-ruled over "lean" and over naming the tool's limit — the author gets a number to aim at while composing) and carries the split rule (body summary, pair MD substance) plus the pair sequence write-land-cite, per docs/issues/46-ghi-info-agent-design.md. Accepted drift caveat: 500 is the tool's tunable starting value, so tuning the constant means editing this line too; a stale number costs one corrected retry. The other three bullets stand as drafted.*
6. What to do, step 3 — revise by editing the body
   *processed 2026-08-12 → revised: "completion" collapsed into close-with-reason — the comment catalog keeps two events (instance outcome, ruling challenge); a finished commitment records its outcome in the body by edit, then closes with its reason, since the close is itself a recorded event and a completion comment would restate both. This settles the question docs/issues/46-ghi-info-agent-design.md deferred to this walk; the design's catalog line and its comment-deny teaching prompt updated in the same commit.*
7. What to do, step 4 — write for a zero-context reader
   *processed 2026-08-12 → accepted: the three pre-submit tests stand as drafted; confirmed against the item-5 split rule — "identifiable from the issue alone" reads as the body plus what it cites, so a pair's summary body passes without the reader opening the MD; the split rule lives in step 2 and is not restated here.*
8. What to do, step 5 — openable references and checked claims
   *processed 2026-08-12 → accepted: the three bullets stand as drafted; noted without text change — the write tool now mechanically enforces the in-repo-paths-resolve-on-main check (the skill line front-loads it), and a step-1 ask that returns nothing is itself a valid absence receipt (query and scope named).*
9. How to do it
   *processed 2026-08-12 → revised: the Search line became the Ask line with the fallback ladder inline (mirror grep, then gh search, then pair-document grep), and Close / Comment lines were added carrying the item-6 catalog mechanics; File, Edit, compose-in-a-file, and queue-routing lines unchanged. The named scripts and ghi-mirror/ remain unbuilt until nedschorus#46 — gh alone works today; the landing-sequence question rides at item 10.*
10. Close-out: where the skill file lands and what closes the commission
    *carries (added 2026-08-12, from item 4's discussion): the skill names scripts/ghi-info-ask.py, which does not exist until nedschorus#46 builds it — rule whether the skill file lands on main before the script exists (the fallback ladder covers the gap) or waits for the build.*
    *processed 2026-08-12 → accepted: land now, not after the #46 build — the fallback ladder makes the skill correct in the gap. The ruled text copied to .claude/skills/ghi-write/SKILL.md on the walk branch; this draft stays as the decision trail with a pointer at its top; the design doc's stack line updated to point at the landed skill; a cold read before the user-deputized push. nedschorus#13 closes after the push by the skill's own rules — body edit recording the outcome (path, and the plain-over-pushy register ruling), then close with reason completed; nedschorus#46 stays open as the build commission.*

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
```
