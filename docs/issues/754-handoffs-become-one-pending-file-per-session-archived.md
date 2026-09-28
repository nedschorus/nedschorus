---
issue: "[Handoffs become one pending file per session, archived only after a successor is up](https://github.com/nedschorus/nedschorus/issues/754)"
status: specified, not built
design-as-of: 2026-09-28
---

# Handoffs become one pending file per session, archived only after a successor is up

Today every agent-seat has one session-handoff file, `~/.claude/handoffs/<seat>-handoff.md`, and the handoff-supervisor tells a new handoff from one it has already acted on by comparing two counters: the `restart-counter:` field in the file, and `consumed_counter` in its own state file. This issue carries a specification, directed by the user on 2026-08-31 and never built, that replaces both with one rule. Each agent-session writes its handoff to a pending file named after that session, overwriting it if it hands off twice. The file's presence means a handoff is waiting. The handoff-supervisor moves it into the archive only once a successor is running. The counter, and the pruning of old handoffs, go.

The specification's only copy is a section of a design document on the branch `fast-handoff-design-drift-correction-and-per-session-handoff-file`, which is to be deleted once this file is on main. It is carried here in substance, with every code claim rechecked against main as it stood on 2026-09-28, and with what has changed since it was written stated where it bears on the build.

Every line number below is on main at commit `a34b3ded36cad5f9051e09b3715da9a9cf0fd524`, 2026-09-28.

## Why

A session-handoff is mostly a summary of the transcript of the agent-session that wrote it, and every handoff file already names that session in its `written-by-session:` field. A session can write more than one handoff, but only its latest matters. So one file per session, overwritten in place, loses nothing. With it, the counter machinery has no job left, and the user called it useless.

There is a defect it repairs too. When a handoff carries `dont-restart` and the answer to the handoff-supervisor's restart question is no, or there is no terminal to ask on, the handoff-supervisor records the handoff consumed and stops (`nc-systems/handoff/handoff-supervisor.py:2180` to `:2195`). From then on nothing treats that handoff as waiting. `scripts/resupervise-seat.py` refuses the seat, because the counter is not above the consumed one (`scripts/resupervise-seat.py:144` to `:150`). A launch by hand starts an empty session rather than asking the restart question again. `scripts/recover-crashed-seats.py` offers only to restart the seat from its old transcript, or fresh when there is none, because the handoff-supervisor recorded an exit. The handoff's next step is then lost unless someone reads the file by hand. Under this specification nothing is consumed unless a successor exists, so that handoff stays pending and the next launch asks again.

## The user's direction

The user gave it on 2026-08-31, between 04:47Z and 05:22Z, in the merge-lane seat's session `ff210027-a00c-4d38-b94f-7e16594e0d10`. That was the evening of 2026-08-30 in his time zone. The transcript is at `nedlern@ned-box:/home/nedlern/nedschorus-logs/transcripts/mac/projects/-Users-el-agents-merge-lane/ff210027-a00c-4d38-b94f-7e16594e0d10.jsonl`. His words, verbatim, with the times they were sent:

- 04:51:38Z: "should the handoffs be tied to the jsonl - seems like if you search for one you might want the other - instead of being enumerated - that only works if there is either 0 or 1 correct handoff per jsonl. what do you think"
- 04:52:50Z, typed while the agent worked: "I think it can, but I'd also think all the the latest are invalid." He restated it at 04:53:50Z, below, as "all but the latest".
- 04:53:06Z: "or rather obsolete. AFter all it's mostly a summary of the jsonl"
- 04:53:50Z: "that is all but the latest are invalid"
- 05:02:55Z: "COnfused - if the only count is 1 - because there is only the latest handoff per GUID, then why bother with a count."
- 05:04:15Z: "It used to guard name conflicts, but if the name includes the guid, then we only want the latest handoff I think"
- 05:05:30Z: "so we'd have to remove some uselss mechinery if we make this change."
- 05:09:02Z: "as soon as the handoff if written (fully I'd hope) the supervisor kicks in, unless its supressed or broken or never started. If it doesn't kick in then further handoffs are named correctly and old handoffs like this are junk. BUt agree that we must be careful we might need some intermediate steps."
- 05:12:49Z: "I think we're going to finish that design MD now and build it now. As I'm eager to fix handoffs."
- 05:21:49Z: "ANd yes, update the fast-handoff design. very carefully."

What is his and what is not. Naming the handoff after its session, keeping only the latest one per session, and removing the counter are his direction. Consume by removal, the `pending/` directory and the two migration phases are the merge-lane seat's answers to it, written into the specification that night. He asked for "intermediate steps" and directed that the specification be written and built. He did not rule on its details one by one. The specification was never taken through an approval-walk with him or reviewed on a pull request. Its one review was an independent check by an agent given no context, which the branch's second commit answered. The user said "Y" on 2026-09-28 to filing it as this GHI.

## The specification

This section carries the specification as written on 2026-08-31. Line numbers are moved to main's. Where main now differs, the next section says so.

### Two counters, and they are different fields

It is easy to run these together. The specification's own first draft did, and so did the argument the merge-lane seat first put to the user.

- **`restart-counter:`** is a field of the handoff file, mirrored as `consumed_counter` in the handoff-supervisor's state file. It has exactly one job, novelty: has the handoff-supervisor already acted on this file? The writer, `nc-systems/handoff/handoff-write-and-check-supervisor.py`, sets it in `next_restart_counter` (line 167) to one more than the higher of the file's value and the state's, so the new value reads as new even when the file is missing, malformed, or older than what was consumed.
- **`generation`** lives only in the state file (`fresh_supervisor_state`, `nc-systems/handoff/handoff-supervisor.py:395`). It names the archives: the handoff copy `<seat>-handoff-<NNNN>.md` at `nc-systems/handoff/handoff-supervisor.py:1871` and the conversation-tail `<seat>-dialog-<NNNN>.md` at `:1859`. It is also what orders pruning, in `prune_old_generations` (`:1181`). `restart-counter` appears in no file name anywhere.

That split is what makes the change clean. Naming the archives and ordering the pruning were never `restart-counter`'s jobs, so retiring it costs neither. Its only job is novelty, and consume by removal retires that.

### Consume by removal

A pending handoff is a file whose presence means "waiting". The handoff-supervisor moves it into the archive only after a successor has actually come up. Where the archive is, and what an archived handoff is called, the specification does not say (question 5 below). Novelty becomes "does a pending file exist", with no counter to compare against. A session that hands off twice simply overwrites its own pending file.

Pruning goes with the counter, by the other half of the change. Files named for their session never collide, so nothing needs pruning. Keeping every handoff costs a few kilobytes, against the transcript of several megabytes that each one summarises. `generation` stops being an identifier. It survives only as the reincarnation count the handoff-supervisor prints, at `nc-systems/handoff/handoff-supervisor.py:2070` and `:2101`: a number for a person reading a console.

### The shape

One pending file per writing session:

    ~/.claude/handoffs/pending/<seat>-<session-id>.md

**The `pending/` directory is required, not decoration.** As written on 2026-08-31, the reason was this. `prune_old_generations` globs `<seat>-handoff-*.md`. A new file of that shape placed beside the old ones would match the glob, and an old handoff-supervisor would delete a live pending handoff as a stale generation. A subdirectory puts the new files outside every existing glob, and it makes "presence means waiting" literal. The next section says how far that reason still holds.

The directory needs no permission work. `.claude/hooks/instruction-file-guard.py` has carved `.claude/handoffs/` out of its protection since PR [instruction-file-guard: carve out .claude/handoffs/](https://github.com/nedschorus/nedschorus/pull/215), merged 2026-08-31, and the carve-out covers subdirectories. One limit: the guard checks its protected file names before any carve-out, so a `CLAUDE.md` or `CLAUDE.local.md` anywhere beneath `.claude/handoffs/` is still refused. `.claude/hooks/instruction-file-guard-test.py` pins that case.

### A recorded correction: the double write

The merge-lane seat first defended the counter with this case. A session writes a handoff. The handoff-supervisor consumes it without launching a successor. The session writes a second handoff, and a handoff-supervisor comparing session ids sees "already consumed" and ignores a live handoff.

The user rejected it, and he was right. `stop_session(process)` runs before anything else on the handoff path (`nc-systems/handoff/handoff-supervisor.py:2177`, still ahead of the carry-over and of the consume). So consuming a handoff implies the writing session was stopped. A session that lives to write twice is one whose first handoff was never consumed, and then comparing session ids gives the right answer. The case cannot arise on the paths that consume inside the loop.

### Boot is where consuming and stopping come apart

At startup the handoff-supervisor has no session of its own to stop, and two startup paths consume a handoff anyway. A build must answer this case explicitly. It is not a reason to keep the counter.

- **Resume at startup** (`nc-systems/handoff/handoff-supervisor.py:1971`), reached with `--resume-session-id`. It marks any waiting handoff consumed before resuming the transcript, because "the operator chose the transcript over the handoff by passing the flag", as its comment says. The writing session is dead by construction.
- **Boot ignition** (`:1987`), which runs only when no session was adopted. It launches a fresh successor from the waiting handoff through `carry_over_to_successor`, so it replaces rather than adopts. On the adoption path (`--adopt-session-id`) this branch is skipped and nothing is consumed at boot.

### Migration, in two phases; only the second is gated

- **Phase 1 adds and removes nothing, and can land at any time.** The writer writes both files: the old `<seat>-handoff.md` exactly as today, counter included, and the new pending file. A new handoff-supervisor prefers the pending file and falls back to the old one. An old handoff-supervisor never looks in `pending/` and reads the old file as it always has. Every combination of old and new writer with old and new handoff-supervisor works. That is the property that matters, because a handoff-supervisor is a process that runs for days and keeps the code it started with.
- **Phase 2 waits until every agent-seat's handoff-supervisor runs current code.** The writer stops writing the old file and the counter, and the machinery listed below is removed. Landing phase 2 while any handoff-supervisor is old would strand that seat. `scripts/resupervise-seat.py:136` to `:142` refuses a handoff that carries no readable `restart-counter`, saying the handoff-supervisor would not ignite from it. `scripts/recover-crashed-seats.py:1102` to `:1112` refuses one the same way. That is why the phases are separate changes.

### What phase 2 removes, and what it only narrows

Removed: the `restart-counter:` field and `counter_from`, `next_restart_counter`, `consumed_counter` with the writer's `consumed_counter_from_state`, `prune_old_generations` with `GENERATIONS_KEPT`, and the counter comparisons in the two recovery tools. The next section but one lists every place on main that uses them.

Two things are narrowed rather than removed, and a builder should not delete them outright:

- **`generation`** stops being an identifier but survives as the printed reincarnation count.
- **`--claim`** and `claiming_directory()` in the writer lose their stated reason. The writer's docstring gives it as a handoff lost unread because two agent-seats sharing a name overwrote one file, observed 2026-08-16 (`nc-systems/handoff/handoff-write-and-check-supervisor.py:17` to `:22`). Files named for their session no longer collide. But the agent-seat's name still selects the handoff-supervisor's state file and lock, so the refusal narrows rather than vanishes: what it still guards against is two agent-seats sharing one name, and with it one state file and one lock.

## What has changed on main since 2026-08-31

Each of these bears on the build. None of them reverses the direction.

1. **"Consumed" today means carried over, not that a successor is up.** In the loop the handoff-supervisor records the consume at `nc-systems/handoff/handoff-supervisor.py:2213`, after `carry_over_to_successor` (`:2198`), and launches the successor at the top of the next pass (`:2102`). Boot ignition records it at `:2024`, also before the launch. Nothing checks that the successor came up. The specification's "only after a successor has actually come up" therefore moves the consume to after the launch. Two things already leave a handoff unconsumed, and those stay as they are: a failed extraction (`:2201` to `:2205`), and the no-terminal refusal when a handoff arrives (`:2168`).
2. **The pruning hazard now applies only to old handoff-supervisors.** PR [The dialog pruner keeps two generations, not two files](https://github.com/nedschorus/nedschorus/pull/406), merged 2026-09-16, changed `prune_old_generations` to delete only names that fully match `<stem>-<digits>.md` or `<stem>-<digits>-complete.md`, grouped by the number. A current handoff-supervisor would not delete a file named for a session id. One started before that merge still would, so `pending/` is still the safe place, and it still makes "presence means waiting" literal.
3. **The session that writes a handoff can differ from the one the handoff-supervisor launched.** PR [The dialog is extracted from the session that wrote the handoff](https://github.com/nedschorus/nedschorus/pull/573), merged 2026-09-20, has `carry_over_to_successor` prefer the handoff's `written-by-session:` over the session id in the state file. It was built after the MD-skills seat's generation 27, whose handoff was written by a session the handoff-supervisor had not launched (the docstring at `:1809` has the account). So the handoff-supervisor cannot work out a pending file's name from its own state. It has to look for any pending file under its agent-seat's name, and how it tells its own files from those of a seat whose name starts with the same letters is question 3 below.
4. **More paths now read "is a handoff waiting".** Each has to read "a pending file exists" instead:
   - The launch by hand of a crashed seat resumes its last transcript only when no handoff waits and no exit is recorded (`:2043`). This came from PR [A by-hand launch resumes a crashed seat instead of minting an empty session](https://github.com/nedschorus/nedschorus/pull/566), merged 2026-09-20.
   - A session that dies without a handoff is resumed inside the loop, keeping its session id and its generation. This came from PR [The handoff-supervisor resumes a session that died without a handoff](https://github.com/nedschorus/nedschorus/pull/651), merged 2026-09-22. Its test for "no handoff" is `wait_for_handoff` returning `None`, which is today a counter comparison (`:1742` to `:1746`).
   - `scripts/recover-crashed-seats.py` `assess_seat` (`:1096` to `:1130`) chooses between the verdicts `seat-asked-to-be-consulted` and `defer-to-boot-ignition` by the same comparison. The first came from PR [recover-crashed-seats: a seat whose waiting handoff asks to be consulted is not launched](https://github.com/nedschorus/nedschorus/pull/445), merged 2026-09-17.
5. **The specification's consumer list was already one short.** `scripts/recover-crashed-seats.py` has read the counter since PR [Crash recovery: resume a dead seat's last real transcript under a supervisor (#120)](https://github.com/nedschorus/nedschorus/pull/131), merged 2026-08-22, before the specification was written. The specification's table counted only the handoff-supervisor, the writer and `scripts/resupervise-seat.py`. `scripts/restart-live-seats-at-login.py`, built since, runs the recovery tool for each seat it restarts, so it depends on that tool's reading.
6. **The conversation-tail and the handoff archive are named by generation**, `<seat>-dialog-<NNNN>.md` with its `-complete.md` companion, and `<seat>-handoff-<NNNN>.md`. The specification names the pending file but neither of these. The project glossary spells both the session-handoff's path and the conversation-tail's in their entries, and so do `docs/nedschorus-wiki/nedschorus-handoff-system-overview.md` and `docs/nedschorus-wiki/nedschorus-file-naming-and-location-standards.md`. Each of those needs the new names.

## Every consumer of the counter on main

The search: `git grep -n -E "restart-counter|restart_counter|consumed_counter|counter_from|next_restart_counter" origin/main -- scripts/ nc-systems/ .claude/`, on 2026-09-28. The counts use the specification's own method, so they compare with its 2026-08-31 table: matching lines, `grep -Ec` per pattern, per file. A line may mention a pattern twice, and some mentions are docstring prose. The counts size the change. They do not scope it.

| file | what it does with the counter | `restart-counter` or `counter_from` | `next_restart_counter` | `consumed_counter` | `prune_old_generations` or `GENERATIONS_KEPT` |
|---|---|---|---|---|---|
| `nc-systems/handoff/handoff-supervisor.py` | defines `counter_from` (`:836`); holds `consumed_counter` in its state; `wait_for_handoff`'s novelty test (`:1742` to `:1746`); marks consumed on resume at startup (`:1981`), on boot ignition and its `dont-restart` branch (`:2001`, `:2006`, `:2024`), on the in-loop `dont-restart` answer (`:2193`) and on every reincarnation (`:2213`) | 9 | 0 | 13 | 7 |
| `nc-systems/handoff/handoff-write-and-check-supervisor.py` | `consumed_counter_from_state` (`:156`), `next_restart_counter` (`:167`), writes the field (`:570`) | 5 | 2 | 3 | 0 |
| `scripts/resupervise-seat.py` | `handoff_is_waiting` (`:119`): refuses a handoff with no readable counter, and one not above the consumed counter | 6 | 0 | 1 | 0 |
| `scripts/recover-crashed-seats.py` | `assess_seat`: refuses a handoff with no readable counter; above the consumed counter it is `seat-asked-to-be-consulted` or `defer-to-boot-ignition` | 3 | 0 | 1 | 0 |
| `scripts/restart-live-seats-at-login.py` | no direct use; runs `scripts/recover-crashed-seats.py` for each seat (`recovery_command_for_seat`) | 0 | 0 | 0 | 0 |
| `nc-systems/handoff/tests/handoff-supervisor-test.py` | tests | 26 | 0 | 17 | 4 |
| `nc-systems/handoff/tests/handoff-write-and-check-supervisor-test.py` | tests | 9 | 6 | 3 | 0 |
| `scripts/recover-crashed-seats-test.py` | tests | 19 | 0 | 6 | 0 |
| `scripts/resupervise-seat-test.py` | tests | 5 | 0 | 4 | 0 |
| `scripts/restart-live-seats-at-login-test.py` | fixture state files and one fixture handoff | 1 | 0 | 2 | 0 |

One more hit is not a consumer: `scripts/md-drift-lint-test.py` uses the words "the `restart-counter` field" as fixture text for the linter. `nc-systems/handoff/handoff-design.md` shows the field once, in its example handoff, and would change with the format.

## Questions the build must answer

These came up while the specification was rechecked on 2026-09-28. They are not the user's direction. The builder brings the answers to him before building, and records them here with the edit operation of `scripts/ghi-issue-write.py`.

1. **Startup paths.** What each does to a pending file: the resume at startup (`nc-systems/handoff/handoff-supervisor.py:1971`), which consumes today; boot ignition and its `dont-restart` branch (`:1987`); adoption, which consumes nothing; and the resume by hand (`:2043`), which runs only when nothing waits. The specification asks for this and does not answer it.
2. **What "a successor is up" means, and what happens when it never is.** `launch_agent_session` returning a process, the successor's transcript appearing, or something else. Consuming moves to that point. When the successor fails to come up, the pending file stays, so something has to stop the handoff-supervisor relaunching from it without limit, as the resume budget `CONSECUTIVE_RESUMES_WITHOUT_NEW_WORK_BUDGET` does for resumes.
3. **Finding a seat's own pending file when seat names share a prefix.** `pending/<seat>-*.md` for the seat `merge-lane` also matches `pending/merge-lane-backlog-<session-id>.md`. Both seats exist on the Mac today, as do `reboot-test` and `reboot-test-2` (their state files are in `~/.claude/handoffs/` there, listed 2026-09-28). The handoff-supervisor cannot name the file exactly (change 3 above). So it needs a name it can match exactly, such as a session id matched in full after the seat's name, or a directory per seat under `pending/`.
4. **A session with no id.** The writer writes `written-by-session: unknown` when `CLAUDE_CODE_SESSION_ID` is unset (`nc-systems/handoff/handoff-write-and-check-supervisor.py:576`). Every such session would write the same pending file name.
5. **The archive's name and the conversation-tail's.** The specification names neither (change 6 above). Handoffs are small enough to keep forever. The `-complete.md` companion holds a whole dialog, so whether conversation-tails are still pruned is a separate choice.
6. **`dont-restart` after a no.** Under this specification the pending file stays, and the next launch by hand reaches the restart question again. `scripts/recover-crashed-seats.py` already leaves such a seat down for the same reason, user-ruled 2026-09-17 in PR [recover-crashed-seats: a seat whose waiting handoff asks to be consulted is not launched](https://github.com/nedschorus/nedschorus/pull/445). A build should confirm that this is the behaviour wanted, and say how an operator discards a pending handoff he does not want acted on.
7. **The old file during phase 1.** When a new handoff-supervisor consumes a pending file, the old `<seat>-handoff.md` with its counter still stands beside it. Unless the new handoff-supervisor also keeps recording `consumed_counter` as today, anything still reading the old file, an old handoff-supervisor or a recovery tool run from a checkout that is behind, would read that handoff as still waiting. The specification's claim that every combination of old and new works depends on this.
8. **Several pending files for one agent-seat.** A session can die, or its handoff-supervisor can be down, before its pending file is consumed, and a later session of the same seat can then hand off too. That leaves two pending files for one seat. The user's words at 05:09:02Z point at the answer, "further handoffs are named correctly and old handoffs like this are junk", but the build must still say how the newest is chosen, by the `written-at:` field or otherwise, and what happens to the older ones.

## Next action

A builder answers the eight questions above and brings the answers to the user. Then phase 1 is built on a topic-branch cut from current main, as one pull request: the writer writes both files, and the handoff-supervisor prefers the pending file, consumes it by moving it after the successor is up, and falls back to the old file. Phase 2 is a separate pull request, opened only once every agent-seat's handoff-supervisor has been restarted on phase 1 code.

## Where this came from

The specification was the section "QUEUED: the per-session handoff file and consume-by-removal" of the design document then at docs/cross-project/fast-handoff-design.md, on the branch `fast-handoff-design-drift-correction-and-per-session-handoff-file`, tip commit `220330beb23d1ab4e60c649719697960ad6df7c9`. Main has no file at that path now: the design moved to `nc-systems/handoff/handoff-design.md`. Once the branch is deleted its commits may stop being reachable, which is why the substance is carried here rather than cited. The merge-lane seat wrote it on 2026-08-31, in commit `0a0396bf`, and corrected it the same day in `220330be` after the check by an agent given no context. The branch was pushed and never opened as a pull request. Later on 2026-08-31 the user ruled that a design document changes role once its code exists (GHI [built-in-process-planned documents: design docs convert to a pointer map of built / in process / planned, with a skill that verifies and updates them](https://github.com/nedschorus/nedschorus/issues/219)). That left open where a specification for unbuilt work should live, and the branch waited. A design is now written in its issue's GHI-MD (`docs/nedschorus-wiki/nedschorus-file-naming-and-location-standards.md`, the design document row), which is this file.

The branch's other change, seven corrections to that design document's description of the system as it then stood, is left out. The design has since moved to `nc-systems/handoff/handoff-design.md` and been revised, so those corrections no longer apply. The search for another copy of the specification on main: `git grep -n -i -E "per-session handoff|consume-by-removal|consume by removal|pending/" origin/main -- docs/ nc-systems/ scripts/ .claude/`, 2026-09-28, found none.

## Related

- GHI [Build fast-handoff (renames to handoff at entry) — script, skill, dogfood, per docs/cross-project/fast-handoff-design.md](https://github.com/nedschorus/nedschorus/issues/2), closed: the original build of the handoff system and its counter.
- GHI [Crash recovery for seats that died without a handoff: find the last live transcript, resume it supervised](https://github.com/nedschorus/nedschorus/issues/120), closed: built `scripts/recover-crashed-seats.py`, one of the counter's consumers.
- GHI [recover-crashed-seats.py: the six changes ruled 2026-09-02 — exit record, process-identity liveness, parking marker, verified restart, by-hand resume, window](https://github.com/nedschorus/nedschorus/issues/242): the exit record, and the resume by hand at `nc-systems/handoff/handoff-supervisor.py:2043`.
- GHI [The handoff-supervisor resumes a session that died without a handoff, instead of stopping the seat](https://github.com/nedschorus/nedschorus/issues/613): the resume inside the loop, which keeps the generation.
- GHI [Fleet survives a machine restart without losing seat context: detect, hand off on notice, relaunch at boot, resume from transcript](https://github.com/nedschorus/nedschorus/issues/116): `scripts/restart-live-seats-at-login.py`, which reaches the counter through the recovery tool.
- GHI [Run named agents on the Ubuntu box, reachable from iTerm2 by name: launch-claude with tmux attach-or-create, and the migration it requires](https://github.com/nedschorus/nedschorus/issues/45): the recovery procedure that became `scripts/resupervise-seat.py`, another of the counter's consumers.
