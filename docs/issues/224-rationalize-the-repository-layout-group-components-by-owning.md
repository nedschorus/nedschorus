---
issue: "[Rationalize the repository layout: group components by owning system under nc-systems/, and a hook dispatcher](https://github.com/nedschorus/nedschorus/issues/224)"
---

# Rationalize the repository layout: group components by owning system under nc-systems/, and a hook dispatcher

The repository is laid out by file type, so no system is findable in one place. Everything about one system is scattered across `scripts/`, `docs/`, `.claude/`, and sometimes an unmerged branch. An agent asked "what is the recovery system, and what works today" cannot answer it by listing a directory.

**Measured 2026-08-31.** `scripts/` holds 57 files — 31 distinct programs once each program is paired with its test. Clustering them by the system they serve gives five groups and **no leftovers**:

| system | programs |
|---|---|
| running and recycling seats | 14 — handoff supervisors and hooks, both launchers, `recover-crashed-seats`, `resupervise-seat`, statusline, dialog watcher |
| reviewing documents | 9 — cold-read cells and grid, `sanity-check-attacks`, `code-review-codex-cell`, two lints |
| getting work onto main | 4 — `git-gatekeeper`, `checkout-freshness-catch-up`, `clean-worktrees`, `watch-open-pull-requests` |
| GitHub issues | 2 — `ghi-info-ask`, `ghi-mirror-refresh` |
| backup and recovery | 2 — `backup-health-check`, `find-deleted-path-across-backups` |

Alphabetical order actively scatters these groups: the recovery system's two halves sort to opposite ends of the directory, eleven unrelated programs apart. Add its design (on an unmerged branch), its unbuilt hook half, and its sudoers file, and one system occupies five locations across two trees and a branch.

**Why waiting costs more than acting.** Every additional citation into a path raises the price of moving it later, and this project has now measured that price three times: the `md-review` -> `cold-read` rename left an entire branch reading as obsolete; the incident behind `scripts/find-deleted-path-across-backups.py` was an agent following a citation to a moved file and building the wrong thing from its absence; and `docs/issues/queue/3-gatekeeper-checks-never-run-at-check-in.md` cites `scripts/git-gatekeeper.py:823-825`, where the attach point has since moved to 861-863.

## What is proposed

1. **`nc-systems/<system>/` holds everything one system owns** — its code, its tests, its design, its configuration. The prefix matches the existing `nc-queue/` at the repository root. Not `systems/`, which is ambiguous, and not a name encoding maturity: a directory renamed on promotion breaks every citation into it at exactly the moment most readers point at it.

   **A system earns its directory; it is not given one on speculation** (user-ruled 2026-08-31). Material not yet sure of stays in a queue with no directory and no name, and graduates when production code is written for it (test code does not count): a directory forces a name before the thing is understood, and that premature name is what later gets renamed, breaking every citation into it.

2. **Each system's built / in-process / planned state lives in its build-slice plan, not in a `<system>-BIPP.md`.** The BIPP document this point first proposed, from GHI [built-in-process-planned documents: design docs convert to a pointer map of built / in process / planned, with a skill that verifies and updates them](https://github.com/nedschorus/nedschorus/issues/219), was retired on 2026-09-23 by item 7 of the walk *what a design becomes when its code lands* (minutes: `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/what-a-design-becomes-when-its-code-lands-2026-09-22-minutes.md`). A system carries its design, pinned to what landed; a build-slice plan when it is built in more than one run, on the model of `docs/issues/3-main-gatekeeper-build-slice-plan.md`; and an overview. All three are kept in line by refresh-design, GHI [refresh-design: when a system's code lands, bring its design, build-slice plan and overview into line — removing, never revising](https://github.com/nedschorus/nedschorus/issues/670). Whether a system is real is settled before the directory exists. Maturity is a checkable fact inside the directory, not part of any name, so promotion edits a sentence and moves nothing.

3. **`nc-systems/` carries a repository map**: one line per system, written so an agent grepping can tell whether to open a system at all. Its shape was first ruled in GHI [built-in-process-planned documents: design docs convert to a pointer map of built / in process / planned, with a skill that verifies and updates them](https://github.com/nedschorus/nedschorus/issues/219), whose BIPP document kind is now retired; the map's requirement stands — a map, not a summary.

4. **Hooks reach their systems through a dispatcher.** `.claude/settings.json` registers 6 handlers directly, four `PreToolUse` ones belonging to four systems. One entry per event running each system's own handler by convention lets a system own its hook without `settings.json` changing. A generated `settings.json` is rejected: a second copy of the truth that drifts from its sources.

## Relationship to the layer design

GHI [Layer-design draft held on branch repo-boundary-and-runtime-layers: land or discard](https://github.com/nedschorus/nedschorus/issues/79) holds a parked draft on branch [repo-boundary-and-runtime-layers](https://github.com/nedschorus/nedschorus/tree/repo-boundary-and-runtime-layers) sorting components by where each must be when used. A different axis, not a competing answer: a component has an owning system and a delivery layer independently. They collide only at hooks and skills, which sit where the harness reads them; the dispatcher above reconciles that. The draft's claim that disk layout is cheap to change is contradicted by the three citation breaks above, and GHI [Layer-design draft held on branch repo-boundary-and-runtime-layers: land or discard](https://github.com/nedschorus/nedschorus/issues/79) is itself an instance, parked where no reader looks.

## Rulings since filing (user-ruled 2026-09-07/08, reboot-test seat)

From the walks that landed the design-to-main design; minutes in the log-store, `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/state-machine-design-third-cold-read-decisions-minutes.md`, item 7.

- **Systems are hierarchical, with matching directories**: "Think of subdirectories like tags - they are helpful."
- **A component's tests live in a subdirectory of its own directory**: "tests would be in a subdirectory of the code it tests." Applied in `scripts/design-to-main/tests/` (PR [design-to-main machine, slice 1: the state and transition tables, the counters, the run record, and a stub launcher, with 55 tests](https://github.com/nedschorus/nedschorus/pull/287)), against `scripts/`'s flat convention on purpose, pending this issue.
- **Cold-read gets its own directory**: "Seems like cold-read should have its own directory." It is in four places today: its skill and prompts, seven programs in `scripts/`, a draft design in `docs/drafts/`, and the log-store's records. By this issue's test it has earned one.
- **`design-to-main` is a system**, its subdirectories proposed and not overruled: `docs/`, `machine/` with `tests/`, `agent-instructions/` (yielding to `docs/agents/queue/` until this lands), `skills/`.
- **Each system's directory carries a `docs/` subdirectory, beside its `tests/`** (user-ruled 2026-09-20, reboot-test seat; minutes at `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/where-test-designs-and-per-system-docs-live-minutes.md`). Three kinds of thing, three places: the code at the top of the directory, `tests/`, `docs/`. This extends the 2026-09-07 tests ruling to documents, and settles the `docs/` subdivision that this issue's 2026-09-07/08 rulings proposed for design-to-main without ruling on. The repository's top-level `docs/` is unaffected and keeps what belongs to no single system: the wiki, the agent briefs, and a GHI-MD during the period before its code starts. The reason is volume: once design-to-main runs, a system carries a design, a component-contract, a test-design, a status document and a check-in record, and the alternative rule — flat until it gets crowded — makes "crowded" a judgment every agent makes differently.
  - **`nc-systems/main-gatekeeper/` does not match this rule yet.** It landed 2026-09-19 with `main-gatekeeper-design.md` and `main-gatekeeper-first-live-check-in-record.md` level with the code and only `tests/` as a subdirectory. Deliberately not corrected on its own: it had already moved once that week, and the user ruled it is brought into line by the pilot this issue's Next action schedules rather than by a third move.
  - Companion ruling of the same walk, recorded on the queue note `docs/nedschorus-wiki/queue/where-designs-live-and-how-sibling-drift-is-caught.md` rather than here: a test-design is written beside its design and its component-contract, and the three move together. That is what this `docs/` directory receives when code starts.
- **A design lives in its issue's GHI-MD**, refined in place, and moves with its component-contract into its system's directory when code starts. User-ruled 2026-09-18, replacing the `docs/designs/queue/` rule that stood here ("what is the advantage of the split - seems like a meaningless complexity"); that directory is not created.

## Next action

Pilot on **one system before migrating anything else**: the backup-and-recovery system. It is two programs, it is the worst-scattered, it has a hook to prove the dispatcher against, and it has both built and planned parts so its document has something real to say on day one. Land the pilot, then decide whether the convention earned the remaining four systems.

Open question for the user, not settled here: the dispatcher's ordering and blocking rules when several systems handle one event.

## Search receipt

`scripts/ghi-info-ask.py` over both mirrors, 2026-08-31: nothing proposes organizing by owning system or a hook dispatcher; closest are GHI [Layer-design draft held on branch repo-boundary-and-runtime-layers: land or discard](https://github.com/nedschorus/nedschorus/issues/79) (layers) and GHI [built-in-process-planned documents: design docs convert to a pointer map of built / in process / planned, with a skill that verifies and updates them](https://github.com/nedschorus/nedschorus/issues/219) (the status document).
