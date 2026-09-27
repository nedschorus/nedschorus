---
issue: "[Run fleet maintenance on a schedule: weekly worktree cleanup that reports before it deletes, and a citation check before a seat is retired](https://github.com/nedschorus/nedschorus/issues/226)"
---

# Run fleet maintenance on a schedule: weekly worktree cleanup that reports before it deletes, and a citation check before a seat is retired

Nothing on this fleet runs periodic maintenance. Session worktrees accumulate until someone notices, and by then the pile is too large to triage — so it gets cleared with force instead of with judgment, which is how uncommitted work is lost.

**Measured 2026-08-31.** 81 registered worktrees, accumulated over roughly three weeks. Clearing them took a manual pass and `--force`, and the force was necessary *because* of the size: triaging 81 individually was not on. Ten files of uncommitted work went with them — recovered afterwards from a local APFS snapshot, then discarded as unwanted, but the recovery was luck rather than design (`/private/tmp/claude-501` is excluded from Time Machine, so the snapshot was the only surface that had them).

## What already exists

`scripts/clean-worktrees.py` reports or removes finished session worktrees, and its caution is already correct. A worktree is removable only when three mechanical checks pass:

- **clean** — no uncommitted, untracked *or ignored* files. Ignored files count as dirt deliberately, so machine-local state like a walk ledger or an identity file is never reaped with its worktree.
- **landed** — no commits beyond `origin/main`.
- **vacant** — no live process working inside it, proven by `lsof`; if `lsof` cannot be trusted the worktree is kept rather than assumed empty.

Anything failing a check is kept, with the failing reason. Worktrees outside `<repo>/.claude/worktrees/` — agent seat homes, manual checkouts — are always kept, because their lifecycles belong to their owners.

**The finding that motivates this issue:** those checks would have *kept* most of what was reaped on 2026-08-31. The mechanism was right and the human path went around it, because the backlog had grown past the point where per-item judgment was affordable. Running weekly is not tidiness; it is what keeps the pile below the size at which force starts to look reasonable.

## What is missing

**1. A schedule.** Nothing invokes the script. Precedent and a home both exist: seven `com.nedlern.*` LaunchAgents already run periodic work on the Mac.

**2. Report-then-delete, not delete.** Auto-remove only the provably-safe class — the worktrees passing all three checks, which by construction lose nothing. Everything else is reported and waits for a person. A maintenance job that deletes on judgment is a job that eventually deletes something wanted.

**3. Seat retirement needs a different check, and it does not exist.** `clean-worktrees.py` deliberately never touches `~/agents/*`, which is correct — but retiring a seat is exactly where loose ends were found on 2026-08-31, and the check that found them was not "is it clean" but **"does anything still cite this?"** Sweeping main, all open issues and both live task lists for references into the paths being removed found two live citations into `doctrine-queue-drain` out of five candidate paths: `docs/agents/sanity-checker-instructions.md` on main, and issue [Sanity-check write detector never inspects the worktree after claude agents, and one wrote a file during a live run](https://github.com/nedschorus/nedschorus/issues/161). The content-judgment checks run alongside it produced no signal at all — the task stores were test fixtures, the unconsumed handoffs were superseded, and the one untracked design report turned out to be a specimen whose durable facts GHI [Sanity-check write detector never inspects the worktree after claude agents, and one wrote a file during a live run](https://github.com/nedschorus/nedschorus/issues/161) had already extracted on purpose.

That citation check is mechanical and is the only part of the loose-ends sweep worth automating. It belongs with GHI [Reference-integrity checker: links resolve and cited revision-paths exist — pure-code review check (and the home for what-else-can-code-check)](https://github.com/nedschorus/nedschorus/issues/42)'s reference-integrity checker rather than here — same instrument, one more caller — scoped as "inbound references into a path about to be deleted." This issue depends on it for the seat half and does not duplicate it.

## Watch out

GHI [Run named agents on the Ubuntu box, reachable from iTerm2 by name: launch-claude with tmux attach-or-create, and the migration it requires](https://github.com/nedschorus/nedschorus/issues/45) records that `launch-claude-ubuntu` invokes `scripts/clean-worktrees.py` by absolute path in the box's main checkout, and nothing keeps that copy current — it sat two merges stale until pulled by hand. A schedule that runs a stale copy inherits that defect and hides it behind automation, so the scheduled invocation must run a checkout that is verifiably current, or the job must fail loudly rather than run old code.

## Next action

1. Schedule `clean-worktrees.py` weekly on the Mac as a LaunchAgent beside the existing `com.nedlern.*` jobs: remove the provably-safe class, report the rest, and make the report reach the user rather than a log nobody reads.
2. Do the same on the box once the Mac shape is proven, addressing GHI [Run named agents on the Ubuntu box, reachable from iTerm2 by name: launch-claude with tmux attach-or-create, and the migration it requires](https://github.com/nedschorus/nedschorus/issues/45)'s staleness.
3. Extend the citation check under GHI [Reference-integrity checker: links resolve and cited revision-paths exist — pure-code review check (and the home for what-else-can-code-check)](https://github.com/nedschorus/nedschorus/issues/42), then add a seat-retirement report that uses it.

Frequency is proposed as weekly from the measured rate — roughly 27 worktrees a week — not from preference.

## Search receipt

`scripts/ghi-info-ask.py` over both mirrors, 2026-08-31: no issue covers periodic fleet maintenance, scheduling `clean-worktrees.py`, or a pre-deletion citation check. GHI [Queue drain procedure — the review process that empties wiki/queue, the pair queue, and the draft-label issue queue](https://github.com/nedschorus/nedschorus/issues/24) (queue drain) is deliberately on-demand and ruled that way; GHI [Build ghi-info — the GHI knowledge agent](https://github.com/nedschorus/nedschorus/issues/46)'s "maintenance sweep" is scoped to the GHI corpus only.
