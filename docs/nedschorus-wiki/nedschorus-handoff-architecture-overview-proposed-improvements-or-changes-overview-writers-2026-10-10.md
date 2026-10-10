# Proposed improvements or changes: the handoff-system architecture overview (overview writers, 2026-10-10)

Merged from the proposed-improvements-or-changes-files of the two agents that wrote drafts of the overview, which read the code at commit 8e7ddb10a6e1efbbd9bbc08f8fae3d0159aa457a, and re-checked against commit a6b1471e0263e72475cf11e362d0ce311af3cbe2. Line numbers are at a6b1471e. Each entry is an improvement or a possible problem in the code the overview describes; none is in the overview. Two entries the merge found, on the refresh check's file name and on links to the old overview, are settled by the pull request that adds this file and are left out.

## E2 — possible problem: the handoff-supervisor's refresh-due rule misses most of this system's code

Goes wrong when: a commit changes only a component outside `nc-systems/handoff/`, such as either launcher, the three hooks, the extractor or the recovery programs. The handoff-supervisor counts only non-Markdown commits under `nc-systems/<system>/`; the how-to page also makes a refresh due for a change to any path the overview lists as a component, the hooks in `.claude/settings.json`, `nc-systems/general-tools/scheduled-jobs-on-each-machine.json`, or the page itself. More than half of this system's programs are in `scripts/`, so the overview can fall behind with no reminder. Gain from aligning the two rules: an overview refreshed whenever its system changes. GHI [Rationalize the repository layout: group components by owning system under nc-systems/, and a hook dispatcher](https://github.com/nedschorus/nedschorus/issues/224) plans to move these programs under `nc-systems/`, which would shrink the gap to the shared scripts; that move must plan for running handoff-supervisors, which resolve the extractor's path when they start.
Rests on: `nc-systems/handoff/handoff-supervisor.py:890` (`pathspecs = [f"nc-systems/{system}/", f":(exclude)nc-systems/{system}/*.md"]`), `:166-167` (`# Live supervisors resolve this path at import; moving the extractor would break those processes.`, `EXTRACTOR_PATH = SCRIPTS_DIRECTORY / "handoff-extract-conversation.py"`); `nc-systems/handoff/handoff-census-user-record-shapes.py:8`; `.claude/settings.json:21,42,157` (the hook paths); the how-to page, "A refresh is due when a commit ... changes a file under `nc-systems/<system>/`, a path the overview lists as a component, ...".
State: open

## E3 — possible problem: on the Mac, `resupervise-seat.py` and a by-hand `launch-claude-mac` start the handoff-supervisor from whatever checkout they run in

Goes wrong when: a person or agent runs `scripts/resupervise-seat.py <seat> --machine mac`, or `scripts/launch-claude-mac <seat>`, from a worktree. `launch-claude-mac` takes the handoff-supervisor from its own checkout, so the agent-seat's handoff-supervisor runs that worktree's code and stops at its first session-handoff after the worktree is removed, because it runs the extractor from its own checkout. `scripts/recover-crashed-seats.py` avoids this with its `--checkout` default of `~/Projects/nedschorus`; `resupervise-seat.py` could take the same default, and `launch-claude-mac` could warn when it is not run from `~/Projects/nedschorus`.
Rests on: `scripts/resupervise-seat.py:218` (`return SCRIPT_DIRECTORY / f"launch-claude-{machine}"`); `scripts/launch-claude-mac:76-77` (`REPOSITORY_ROOT=$(cd "$SCRIPT_DIRECTORY/.." && pwd)`, `SUPERVISOR="$REPOSITORY_ROOT/nc-systems/handoff/handoff-supervisor.py"`); `nc-systems/handoff/handoff-supervisor.py:167`; `scripts/recover-crashed-seats.py:117-118` (docstring, "Checkout:").
State: open

## E4 — improvement: remove the adoption path that nothing reaches

Gain: a smaller handoff-supervisor. `--adopt-session-id`, `--adopt-process-id` and `AdoptedSession` are passed by no launcher or recovery program; `resupervise-seat.py` retires an unsupervised agent-session instead, and its docstring says no entry point reaches adoption. GHI [Run named agents on the Ubuntu box, reachable from iTerm2 by name: launch-claude with tmux attach-or-create, and the migration it requires](https://github.com/nedschorus/nedschorus/issues/45) records adoption of a running agent-session as deliberately deferred, so removal may need the user; git keeps the code if it is wanted later.
Rests on: `nc-systems/handoff/handoff-supervisor.py:1254-1293` (`class AdoptedSession`), `:1524-1537` and `:1619-1626` (the adopted branches of `supervise_sessions`), `:1803-1809` and `:1830-1845` (the flags and their checks), `:64-65` and `:420-424` (the unknown-exit-code case only an adopted session has); `scripts/resupervise-seat.py:45-47` ("which no entry point reaches"); a search of `scripts/` and `nc-systems/` for `adopt-session-id` outside the handoff-supervisor and tests found only that docstring.
State: open

## E5 — improvement: delete the changeover check for handoff-supervisors that predate the flock lock

Gain: less code on the lock path. `refuse_old_code_supervisor` carries its own removal condition: "Delete this check once no supervisor started before this change is running." A `ps` for `handoff-supervisor.py` on both machines, compared with each process's start time, settles whether the condition holds. The legacy state-key migration is a similar candidate, once no `-supervisor-state.json` still holds `session_id`.
Rests on: `nc-systems/handoff/handoff-supervisor.py:1331-1356` (`refuse_old_code_supervisor`; the condition at `:1332`), `:352` and `:367-369` (`LEGACY_SESSION_ID_STATE_KEY` and its migration).
State: open

## E6 — improvement: give `handoff-census-user-record-shapes.py` a home that runs, or archive it

Gain: the census is the only check that no new kind of injected text slips into a conversation-tail, but it has no test, no caller and no schedule, and its work runs at module level, so nothing tells anyone when a new kind appears. Run it from the extractor's test against a fixture, or from a scheduled job, or archive it.
Rests on: `nc-systems/handoff/handoff-census-user-record-shapes.py:32` (`for jsonl in sorted(root.glob("*/*.jsonl")):`, a module-level loop with no `__main__` guard); the only other mentions in `scripts/` and `nc-systems/` are comments in `scripts/handoff-extract-conversation-test.py:162` and `:261`.
State: open

## E7 — improvement: one definition of the session-handoff's field names

Gain: the writer and the reader cannot drift apart. The writer script loads the handoff-supervisor and takes several names from it, yet defines `NEXT_STEP_VERBATIM_FIELD`, `NEXT_STEP_BLOCK_OPENING_MARKER`, `NEXT_STEP_BLOCK_TERMINATOR` and `SPAWNED_SUBAGENT_FIELD_PREFIX` again with the same values. Goes wrong when: one copy is changed and the other is not, and the writer writes a block the handoff-supervisor misreads.
Rests on: `nc-systems/handoff/handoff-write-and-check-supervisor.py:70-74` (loads the supervisor), `:77-79` and `:100` (the second definitions), `:81-92` (names taken from the supervisor); `nc-systems/handoff/handoff-supervisor.py:194-196` and `:198`.
State: open

## E8 — possible problem: every session-handoff waits on the main-gatekeeper's branch-protection audit

Goes wrong when: the audit or GitHub is slow; the writer script runs `main-gatekeeper.py audit` with a 45-second timeout before it reports whether a handoff-supervisor is watching, so a retiring agent-session near the end of its context waits up to that long on a check unrelated to the handoff, and prints the result to an agent about to stop. Nothing in the handoff-system acts on the result. If the audit is meant to reach someone, a scheduled job or the place where it is read may be a better home; if not, the call can go, making the writer script smaller and every session-handoff faster.
Rests on: `nc-systems/handoff/handoff-write-and-check-supervisor.py:358-374` (`run_branch_protection_audit`, `timeout=45` at `:369`), `:494`.
State: open

## E9 — improvement: bring up to date, or cut, the stale parts of the design of record

Gain: a reader of `nc-systems/handoff/handoff-design.md`, which the overview links, is not misled. The design still says the block form of the next step is queued, not built, though the writer and the handoff-supervisor both build it; and it still describes a writer that starts an adopting handoff-supervisor when none is watching ("self-healing"), a path the code no longer has: the writer script starts nothing, and the launchers run the handoff-supervisor as the pane's command. Under the refresh-design of GHI [refresh-design: when a system's code lands, bring its design, build-slice plan and overview into line — removing, never revising](https://github.com/nedschorus/nedschorus/issues/670), the stale parts would be removed.
Rests on: `nc-systems/handoff/handoff-design.md:47` ("the block form below is QUEUED, not built"), `:243` ("the writer starts an adopting supervisor"), `:278` ("the hook-fired skill run starts an adopting supervisor"), `:282` (a self-started supervisor's output); `nc-systems/handoff/handoff-write-and-check-supervisor.py:344-347` and `nc-systems/handoff/handoff-supervisor.py:194-196` (the block form, built); the writer script's only subprocess call is the audit at `:367`.
State: open

## E10 — improvement: drop the queue that no longer exists from the queue status line

Gain: one dead entry gone. The handoff-supervisor's queue status line lists `legacy-feature-queue`, which does not exist at this commit; the function skips missing directories, so this is dead code, not a failure. GHI [Queue drain procedure — the review process that empties the wiki queue, the pair queue, nc-queue, docs/drafts and the draft-label issue queue](https://github.com/nedschorus/nedschorus/issues/24) plans to take `nc-queue` out of the same line; the two changes fit one commit.
Rests on: `nc-systems/handoff/handoff-supervisor.py:640`.
State: open
