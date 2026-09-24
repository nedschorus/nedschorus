---
issue: "[MD-placement guidance as symmetric pre-tool remind hooks on both runtimes (boss-directed design, build deferred)](https://github.com/nedschorus/nedschorus/issues/11)"
---

# MD-placement guidance as symmetric pre-tool remind hooks on both runtimes (boss-directed design, build deferred)

## Context

Boss-requested notes were landing in arbitrary peer-local paths or not being written at all. The intake spot is now ruled and live: `nc-queue/` (verbatim unreviewed drops, 90-day TTL, dispersal at the initial walk — rule of record: founding plan § Project organization, commit 22a2be1). The remaining question was how agents get *taught* the placement rule mechanically.

## Boss-directed design (2026-07-22, build deferred to a later boss pick)

- **Mechanism: a pre-tool hook on MD writes, symmetric across both runtimes.** Claude side: a PreToolUse hook on Write/Edit of `*.md` outside the approved homes. Codex side: the same shape — the Codex runtime supports PreToolUse hooks and the old fleet already runs them (`features.hooks=true`, worktree-guard precedent, observed live 2026-07-22). The instruction-file route (an AGENTS.md/template line) was considered and rejected by the boss in favor of the hook.
- **Strength: remind, not block** — MD creation is overwhelmingly legitimate (handoffs, drafts, staging files), so a block would be a false-positive machine; the hook surfaces the approved-homes list, asks the agent to place deliberately, and proceeds.
- **Single-source path list:** the approved homes live in one conf file every hook reads. For nedschorus the approved homes are the charter README's "Where things live" table; check-in-time enforcement already exists separately at the git-gatekeeper (subsystem hygiene check).
- **Known limit, accepted:** a write-hook cannot catch a note that was never written; the queue's request-is-not-done-until-the-file-exists check covers that failure mode.

## Trigger to build

Boss pick. During the founding window the deployment surface is the OLD system's hook points (its code is under the old repo's 2026-07-14 halt, so the pick is doubly the boss's); post-boot, the NC-side equivalent would be specified fresh if evidence demands it. Evidence that should prompt the pick: a boss-requested note going astray despite the queue rule being in place.

## Retargeted 2026-09-11, user-approved: the PreToolUse design is withdrawn, and split in two

**The layer was wrong.** All three existing write guards (`.claude/hooks/instruction-file-guard.py`, `session-location-write-guard.py`, `backup-and-snapshot-write-guard.py`) match `Edit|Write|NotebookEdit`. A shell write passes through every one of them, and two of the three say so in their own docstrings. Seats are instructed to prefer the shell, so a remind hook built the same way would watch the tools agents are told not to use.

Demonstrated live, 2026-09-11: the user asked the cold-read-research seat to repair an Obsidian vault, which meant writing inside the reference checkout — exactly what `session-location-write-guard.py` refuses — and nothing stopped it, because the writes went through the shell. The user's instruction is what authorised that, not the guard.

**And the rule this would check does not exist.** The 2026-09-10 placement-rule enforcement survey found the homes tables stated twice and drifted, naming three homes absent from the worktree, omitting six directories that exist, and asserting three mechanisms nobody built. Consolidating the two tables makes the rule single, not complete or correct. The user's sharper objection, which settled it: a watcher is only reasonable "if we know exactly which files are supposed to go to exactly which places and when, which I don't know if we do." The "and when" is lifecycle — draft to queue to home to archive — which no table can express.

### Half one, buildable now and needing no rule

A Stop-hook delta report that **reports and never judges**, reusing the proven code in `scripts/cold-read-cell-common.py`: `working_tree_state()` (git status --porcelain --untracked-files=all, around line 414), `stray_writes_since()` (the delta, subtracting the run's expected output), and `report_stray_writes()` (never raises, and says loudly when the check could not run, because a failure to look is not a clean result). That module has run on every cold-read cell since August. It exists because on 2026-08-21 a reviewer agent wrote a 25,170-byte file into the worktree root and the only notice anyone got was the agent confessing in its own report.

Known limit to state in the code rather than discover later: git cannot see gitignored paths, which that module's docstring records at lines 38-39. A file misplaced into `docs/walk/` stays invisible.

Use plain stdout, not a block decision — see GHI [checkout-freshness catch-up's block decision overwrites the answer of a claude -p subprocess whose output a program reads](https://github.com/nedschorus/nedschorus/issues/334), where this repository's other Stop hook's block consumed a subagent's answer.

### Half two, the missing precondition, user-directed

The user directed the rule built anyway, minimally: "It can be minimal to start, just the obvious cases." The framing that makes it tractable is **shape, not meaning** — whether a path matches the pattern its directory requires is decidable by code; whether a document is standing knowledge is not. Lifecycle is explicitly out of scope for version one.

Four obvious cases proposed to him and **not yet corrected by him**: the repository root accepts only a known list of files (the 2026-08-21 incident); `docs/issues/` accepts only `<number>-<slug>.md` plus its queue and archived subdirectories; `scripts/` accepts code, so a Markdown file there is reported; and every directory under `docs/` must have a row in the single homes table.

The fourth is the valuable one, because it gives the homes table its **first consumer**. Both copies are prose nothing reads, which is why they drifted unnoticed. It depends on the table consolidation landing first.

Supersedes nedlern/nedlern#2159 (filed there first, moved here 2026-07-22 by boss direction: NC-related GHIs live on the NC repo).

Session: c3a1c7c5-9dd9-4d3f-9a92-602b37fff592 (new-vp)
