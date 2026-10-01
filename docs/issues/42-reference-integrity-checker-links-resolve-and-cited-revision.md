---
issue: "[Reference-integrity checker: links resolve and cited revision-paths exist — pure-code review check (and the home for what-else-can-code-check)](https://github.com/nedschorus/nedschorus/issues/42)"
---

# Reference-integrity checker: links resolve and cited revision-paths exist — pure-code review check (and the home for what-else-can-code-check)

## The check

A pure-code checker for reference integrity in committed markdown: every relative link resolves to a real file, and every cited `<revision>:<path>` form exists at that revision (`git ls-tree` per citation). No agent judgment involved — a yes/no a script computes.

## Why this one is real

The defect class recurs: dangling citations and non-resolving paths have bitten repeatedly in the legacy project (three dangling citations caught in a single session there; the wiki checklist manually asks "each path resolves" today). It is the one review check identified so far that code can do completely.

## Scope note — this issue is also the home for "what else can code check"

Migration of doctrine from MD to code is a completely different problem set (boss, verbatim, 2026-08-04) — a hard, per-candidate question that resists one-sentence rules, which is why the d-review skill deliberately carries no migration doctrine. Candidates accumulate here as they surface, each judged on its own: does code decide it fully, does code only screen candidates for an agent, or does it stay judgment. Current screen-class candidates (code narrows, agent judges): absolute-word grep for over-claim candidates; one-word-name and bare-issue-number lints.

Judged — stays judgment, no lint (user-ruled 2026-08-23): bare subprocess `check=False`. The codebase uses `check=False` pervasively and correctly, inspecting the returncode afterward; separating careful uses from careless ones needs judgment, not a grep. Reasoning recorded on https://github.com/nedschorus/nedschorus/pull/111, whose `scripts/silenced-error-lint.py` flags silenced stderr and deliberately excludes `check=False` on these grounds.

## Third caller, added 2026-09-08: a citation the reader's machine cannot resolve

Issue 226 already routes its seat-retirement check here, as "inbound references into a path about to be deleted — same instrument, one more caller". This is a second such caller, and the survey behind it is measured rather than argued.

**The defect class.** This project runs on two machines, the user's Mac and ned-box, each with its own clone. A citation written on one is often unreachable from the other, and nothing in the text says so, so a reader follows the path, finds nothing, and cannot tell whether the file is missing, renamed, or simply elsewhere. The existing scope catches a link that does not resolve *in the repository*; this catches one that does not resolve *from the reader's machine*, which committed markdown does not currently distinguish.

**Measured 2026-09-08** by an exhaustive survey of every script, hook and skill (record: `nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/2026-09-08-cross-machine-write-and-read-survey/`):

| Citation form | Count | Resolves from the other machine |
|---|---|---|
| `nedlern@ned-box:/home/nedlern/nedschorus-logs/...`, the scp form | 14 | yes |
| `file:///Users/el/...` | 64 | no |
| specific paths inside gitignored directories | 63 | no |
| bare directory names in instructions | 21 | yes, not a problem — counted separately |

127 unresolvable against 14 resolvable. Of the 64 `file:///Users/el/` citations only 21 point inside the citing checkout: 26 name `agents/reboot-test`, 9 `Projects/nedschorus`, 8 `agents/MD-skills` — other Mac seats, which no second machine has and no other Mac seat has either. The sanity-checker seat brief, deleted on 2026-10-01 (`git show b30aa47c:docs/agents/sanity-checker-instructions.md`), flagged its own case in prose, "(on that machine only, not committed)", and nothing ships `sanity-check-records/`, so the brief's citation into `sanity-check-records/` was permanently unreachable by design rather than by accident.

**What the check would decide, and it is mechanical.** A path in a committed file is one of: repository-relative and present at the cited revision, which the existing scope covers; machine-qualified in the `user@host:/path` form the log-store already uses, which any reader can act on; or an absolute local path outside the repository, which no other machine can resolve. The third class is the finding. Judgment enters only in the remedy, which is the writer's.

**Why a check rather than a rule.** A drafted rule for CLAUDE.md exists (in the survey record beside the counts) saying: repository-relative when the file is on main, plus the branch when it is not, machine-qualified when it is not in git at all, and say so when a path is temporary. The user's ruling on it, 2026-09-08: "Claude sounds like a temp fix. Is there a GHI that would be a place for a real fix?" A rule agents must remember is the class of fix that fails; this is the instrument that does not need remembering, so the rule is not being landed.

**Related, and not this check's job.** The same survey found that no program performs the copy the 2026-09-08 walk-file ruling requires, and that the `walk-me-through` skill still places its four files in `docs/walk/` and names no shipping step. That is a gap in the ruling's own machinery, for its owner, not a reference-integrity check.

## Requirement, added 2026-09-11: the checker excludes `cold-read-reviewer-test-cases/`

That directory holds the reviewer test set: measured data, committed by the user's ruling of 2026-09-10, whose files cite paths, name scripts and quote sentences as they stood when each was written. Several of those targets have since been retired, renamed or revised on main, and the citations are correct as data: bringing one up to date changes the text every published score was measured against, which is the edit the directory's README already forbids.

Measured 2026-09-11: `scripts/md-drift-lint.py` run over the three trio files produces nine findings, every one a frozen citation and none a defect. This checker would report the same list, and whoever triages it would fix them.

So the checker skips that directory by mechanism and says which rule fired rather than silently doing nothing, the shape GHI [Genre-suffix naming for non-reviewable documents (-log, -report, -capture), and mechanical exclusion from the review instruments](https://github.com/nedschorus/nedschorus/issues/152) gives the review instruments for non-reviewable documents; it may be the same mechanism. The drift lint owes the same exclusion when it is wired into something that runs. The README's side of this is https://github.com/nedschorus/nedschorus/pull/315.

Build timing: gatekeeper era — a natural early check-battery addition, not founding work.

new-vp session bba1b075
