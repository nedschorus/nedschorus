---
issue: "[refresh-design: when a system's code lands, bring its design, build-slice plan and overview into line — removing, never revising](https://github.com/nedschorus/nedschorus/issues/670)"
kind: design
---

# refresh-design: when a system's code lands, bring its design, build-slice plan and overview into line — removing, never revising

## What is wanted

Build **`refresh-design`**: the step that brings a system's three documents — its design, its build-slice plan and its overview — into line with what has landed on main since the last refresh, removing and never revising. The name is the user's coinage (walk of 2026-09-22, item 6). Nothing performs this step today. The user's rulings of 2026-10-30 and 2026-10-31 make the refresh a nightly maintenance job that also fixes a stale line the code cannot show, as the section "What is decided: the refresh as a nightly maintenance job" says; where an older section below differs, the section "What is decided: the refresh as a nightly maintenance job" decides.

## What is decided: the refresh as a nightly maintenance job

The user ruled these on 2026-10-30 and 2026-10-31, as items 9.2, 9.3, 9.3.1 and 9.4 of prime-intellect's approval-walk prime-intellect-handed-over-items-2026-10-29. Its walk-document and walk-minutes, which record each answer with his words, are `docs/walk/prime-intellect-handed-over-items-2026-10-29.md` and `docs/walk/prime-intellect-handed-over-items-2026-10-29-minutes.md` in prime-intellect's checkout on ned-box, shipped to `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/` when the walk closes. He approved each item's recommendation, except item 9.4, whose answer the bullet "It is a maintenance job" gives.

- **It covers designs as well as overviews, and fixes what the code cannot show (item 9.3.1, approved 2026-10-30).** A stale line that restates what the code shows, such as a list of files to read, is removed; a stale line about what the code cannot show, such as a reason or a decision, is fixed. This revises the rule of 2026-09-22 that a refresh removes and never revises. The user's words of 2026-10-30: "stale items should be either fixed or removed. It makes sense to remove design items which can simply be, here are the files you should read. [...] things that are not easily or not visibly not in the code or otherwise clear from reading the code have to be fixed."
- **What is due (item 9.3.1).** Each document gets a `**Checked against:**` line when it is checked. A program lists a document as due when its system's code changed after that line's commit, or when it has no such line.
- **How often, and when (items 9.3.1 and 9.2).** One document every 2 hours, the oldest check first. While the 5-hour usage limit lasts, the refresh runs only overnight: from the end of the full test run of main, which moves from 03:30 to 00:00 Pacific in GHI 1058's build, until 08:00 Pacific; after that, around the clock.
- **It is a maintenance job (item 9.4, answered D on 2026-10-31).** The refresh becomes one of the maintenance jobs of GHI [Regular maintenance: the list of maintenance jobs, how often each runs, and how each reaches the user](https://github.com/nedschorus/nedschorus/issues/1058), and its questions go to the approval-walk of that GHI's nightly overseer agent-session. The overseer runs in tmux on ned-box with Remote Control on, and an iTerm2 window on the Mac, attached to its tmux session, opens each night. The recommendation built no Mac window; the user disapproved that recommendation, so the window opens: "It'd be safer to make it show up in Tmux Mac, just in case there's some message I need to see that doesn't get echoed in remote control."
- **A question waits until the user answers it (item 9.3, approved 2026-10-30).** A question has no deadline and carries into the next night's continuation of the same approval-walk. This replaces the ruling of 2026-10-04, decision 2 of the supporting design `docs/issues/670-system-overview-refresh-agent-design.md`, that the waiting agent-session ends at 04:30 and the next night asks afresh.

The supporting design `docs/issues/670-system-overview-refresh-agent-design.md` predates these rulings: its 05:00 start, its overview-only scope, its agent-session of its own in the tmux session `system-overview-refresh`, and its 04:30 end are replaced by them.

**The glossary gets its entry only when the step exists.** The user's words, 2026-09-23: "I would not add this to the glossary yet. I'd try to keep the glossary true now, not true eventually. Instead I'd make a GHI for it, assuming there isn't one." Until it is built, this issue is where the definition lives. A search on 2026-09-23 found no issue for it: `scripts/ghi-guide-agent-ask.py --include-closed` over open and closed issues, and `gh issue list --state all --search 'refresh-design OR "refresh design" OR overview OR BIPP OR "design lifecycle"'`.

## The draft definition, as put to the user on 2026-09-23

> **refresh-design** — brings a system's three documents into line with what landed on main since the last refresh; run at a landing, and when a reincarnated agent's opening prompt reports the system due. The **design** is streamlined: what the build superseded is removed. The **build-slice plan** marks the slices that landed. The **overview** — what neither the code nor the design says: how the parts fit, why the system is built this way, what was rejected — is re-checked against the code, and created if the system has none. A refresh removes and never revises; a change to a decision is a redesign, a full design-to-main run. Each refresh appends a pinned line carrying the landing commit to the design and the overview. Over an empty commit range it does nothing.

He redirected it here rather than approving it for the glossary; its wording is a draft, not a ruling.

## The rulings it rests on — walk "what a design becomes when its code lands", 2026-09-22/23

The walk's minutes are shipped at its close to the log-store as `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/what-a-design-becomes-when-its-code-lands-2026-09-22-minutes.md`.

1. **A design is pinned to what landed (item 5, accepted).** It is not refined between design-to-main runs. It carries decisions, never build status: decisions do not go out of phase, descriptions of the build do. The evidence: `nc-systems/main-gatekeeper/main-gatekeeper-design.md` carries a `status:` line and an Implementation status block and has been patched out of phase; `nc-systems/handoff/handoff-design.md` carries neither and has taken no substantive edit since moving.
2. **What a refresh is (item 6; the user: "Y but be careful").**
   - **It removes; it never revises.** Revised on 2026-10-30 by item 9.3.1, as the section "What is decided: the refresh as a nightly maintenance job" says: a stale line the code cannot show is fixed. A change that revises a decision is a **redesign** — a full design-to-main run with its own five-verdict review (`scripts/design-to-main/design-to-main-state-tables-common.py`: reject design, contract, implementation, tests, test-design). Checkable, before that revision: a refresh commit's diff is deletions plus the pinned line. His caution, in his words: "We ran into endless problems with designs chasing code, code and test code chasing design changes … once the code lands on main (ie pasts all test) then we can refresh the design."
   - **It runs at landing** (his word: "y").
   - **It refreshes all three documents.** His words: "Designs do go stale, that's why we need refresh-design (which probably should refresh all 3 documents)."
   - **The design does not move**, and each landing appends one pinned line carrying the **commit**, not only a date — so the next refresh's range is exact.
   - Prior art: `docs/nedschorus-wiki/nedschorus-fleet-git-worktree-working-model.md`'s closing note, streamlined 2026-08-20 after its mechanism prose was three times found stale against the code.
3. **Built / in-process / planned live in the build-slice plan (item 7, accepted).** The BIPP document kind is retired — his words: "Just one type of overview." `docs/issues/3-main-gatekeeper-build-slice-plan.md` is the one build-slice plan on main. **A cut slice is a decision, not a phase** — his words: "will not built is not a phase, its a removal of a part of the design" — so it leaves the plan and is recorded in the design with its date and reason. Slices are named and numbered when scheduled.
4. **An overview is created by the first refresh, at first landing, and updated by every one after (item 8, accepted).**
5. **Who keeps an overview true (items 9 and 14, accepted).**
   - **Trigger: reincarnation**, his proposal — "Maybe check if any designs need to be refreshed during reincarnation - would that work? That's our usual maintence period."
   - **The staleness check runs in the handoff supervisor**, `nc-systems/handoff/handoff-supervisor.py` (item 14, 2026-09-23; his words: "this goes into the handoff supervisor and ultimately into the (next) reincarnated agent"). It compares each system's last commit under `nc-systems/<system>/` with the commit pinned in that system's overview, and a stale system gets a "refresh due" line in the successor's opening prompt, beside the launch-time-git-sync line the supervisor already writes. Item 9 first placed it in `scripts/checkout-freshness-catch-up.py`, which is wrong: that is a Stop hook and runs at every turn boundary, so it would report every turn.
   - **A fresh subagent performs the refresh**, given one system and one commit range, `git log <pinned commit>..HEAD -- nc-systems/<system>/` — his words: "this could be done by a subagent as this is a type of one off." The refresh scopes itself by commit subjects, never by diff size: `git diff --stat` sized the handoff overview's due refresh at 7,745 insertions when nearly all of it was a directory move.
   - **No owner.** His words: "why not just refresh - the refresh skill should be smart enough to do nothing if nothing needs to be done, and smart enough to do a little if a little needs to be done." Idempotence makes ownership moot: a second run finds an empty range and stops.
6. **What an overview is (his correction at item 14).** His words: "the overview should not be limited to - a page that says what the system is now. Thats not an overview. It needs to complement the 'what it is now' that is complement the prose and code." An overview complements the code and the design and does not restate them. The one overview on main is `docs/nedschorus-wiki/nedschorus-handoff-architecture-overview.md`; on 2026-09-22 it was due a refresh, verified 2026-09-16 against a system last changed 2026-09-22.

## Constraints on the build

- **Design-to-main is not built** (its design, `docs/design-to-main/design-to-main-state-machine-design.md`, reads `status: design, not built`). So no landing fires a refresh today, and until it is built the supervisor's staleness check is the only trigger.
- **The supervisor half belongs to the fleet seat**, which owns `nc-systems/handoff/` and the reincarnation cycle.
- Item 9.3.1 of 2026-10-30 names the line a check adds `**Checked against:**`; its exact format, and whether it replaces the pinned line of the rulings above, are not yet fixed, and the program that lists due documents reads it, so the two are built together.

## What the first refresh by hand taught, 2026-09-23

The handoff overview was refreshed by hand before this step exists, in PR [Handoff overview: refreshed by hand against the code at 40afb38](https://github.com/nedschorus/nedschorus/pull/677). Five lessons for whoever builds the step:

1. **An overview's last commit is not its verification commit.** The handoff overview's last commit was the 2026-09-20 directory move, and finding the commit it was actually checked against took `git log --follow` and a read of commit subjects. The pinned line must carry the commit.
2. **While a system is half-migrated, the range must cover its files outside `nc-systems/<system>/`.** Seven of the handoff system's parts still live in `scripts/`.
3. **A GitHub issue's status is itself stale.** GHI [recover-crashed-seats.py: the six changes ruled 2026-09-02 — exit record, process-identity liveness, parking marker, verified restart, by-hand resume, window](https://github.com/nedschorus/nedschorus/issues/242) says in its header that change 5 is not built and in its body that it is. A refresh reads the code and the merged pull requests, never an issue's claim.
4. **A text match is not behaviour.** A grep reported that `resupervise-seat.py` passes `--adopt-session-id`; the hit was in its docstring. A claim is checked against the code path.
5. **Most of what was new was "why" material** — how the parts fit and why — which a mechanical diff would miss. The refresh is judgement, done by an agent.

## Related, not parents

- GHI [overview-write skill: how an overview of a system is written and checked before it lands](https://github.com/nedschorus/nedschorus/issues/168) — writes an overview's first version and says "something else keeps it true"; this issue is that something. A refresh's overview half should lean on it.
- GHI [built-in-process-planned documents: design docs convert to a pointer map of built / in process / planned, with a skill that verifies and updates them](https://github.com/nedschorus/nedschorus/issues/219) — its 2026-08-29 update-at-landing ruling is this step's predecessor; item 7 retires the BIPP document it proposed.
- GHI [Queue drain procedure — the review process that empties the wiki queue, the pair queue, nc-queue, docs/drafts and the draft-label issue queue](https://github.com/nedschorus/nedschorus/issues/24) — the precedent for a report at reincarnation (the handoff scrub step reports each queue's depth).

## The daily reminder turned down; a refresh agent deferred, 2026-10-03

The staleness check of item 5 is built: `nc-systems/handoff/handoff-supervisor.py` tells the first agent-seat that restarts each day that an overview is due, and that agent-seat, busy with its own job, lets the refresh wait. On 2026-10-03 at about 23:00Z the user turned that reminder down: "no - this is a stupid design - we should build the refresh agent" (item 5 of the approval-walk whose minutes are `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/handoff-system-overview-refresh-2026-10-03-minutes.md`). So the Next action's "builds the supervisor's staleness check" is done and turned down. He deferred the refresh agent to later maintenance work; nothing is built before he takes it up. Its design, this issue's supporting document `docs/issues/670-system-overview-refresh-agent-design.md`, runs one fresh agent per due system on ned-box after main passes its nightly full test run, refreshes the overview only, not the design or the build-slice plan, and deletes the reminder.

## Next action

Build the refresh as a maintenance job of GHI 1058, after that GHI's nightly overseer, which is built first: the program that lists the documents due by their `**Checked against:**` line, and the refresh itself, one document every 2 hours overnight, as the section "What is decided: the refresh as a nightly maintenance job" says. Settle the draft definition and the line's format with the user first. Add the glossary entry in the pull request that makes the step exist.

## Provisional additions (not yet vetted by the user)

- The agent-seat cold-read-improvement (2026-10-14): rewrite this GHI-MD's definition of how an overview is refreshed to point at `docs/nedschorus-wiki/nedschorus-how-to-write-an-architecture-overview.md`, through /ghi-write and a short approval-walk.
