# Proposed improvements or changes: nedschorus-handoff-architecture-overview.md

Each entry proposes a change to the nc-architecture-overview docs/nedschorus-wiki/nedschorus-handoff-architecture-overview.md or to the system it describes. An entry with a Claim: line is an assertion of the overview that the overview claim check found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on it.

## E1 — possible problem: the handoff-supervisor's refresh-due rule misses most of this system's code

Found by: the two agents that wrote drafts of the overview, reading the code at commit 8e7ddb10a6e1efbbd9bbc08f8fae3d0159aa457a, re-checked against commit a6b1471e0263e72475cf11e362d0ce311af3cbe2; the line numbers below are at a6b1471e.
Goes wrong when: a commit changes only a component outside `nc-systems/handoff/`, such as either launcher, the three hooks, the extractor or the recovery programs. The handoff-supervisor counts only non-Markdown commits under `nc-systems/<system>/`; the how-to page also makes a refresh due for a change to any path the overview lists as a component, the hooks in `.claude/settings.json`, `nc-systems/general-tools/scheduled-jobs-on-each-machine.json`, or the page itself. More than half of this system's programs are in `scripts/`, so the overview can fall behind with no reminder. Gain from aligning the two rules: an overview refreshed whenever its system changes. GHI [Rationalize the repository layout: group components by owning system under nc-systems/](https://github.com/nedschorus/nedschorus/issues/224) plans to move these programs under `nc-systems/`, which would shrink the gap to the shared scripts; that move must plan for running handoff-supervisors, which resolve the extractor's path when they start.
Rests on: `nc-systems/handoff/handoff-supervisor.py:890` (`pathspecs = [f"nc-systems/{system}/", f":(exclude)nc-systems/{system}/*.md"]`), `:166-167` (`# Live supervisors resolve this path at import; moving the extractor would break those processes.`, `EXTRACTOR_PATH = SCRIPTS_DIRECTORY / "handoff-extract-conversation.py"`); `.claude/settings.json:21,42,157` (the hook paths); the how-to page, "A refresh is due when a commit ... changes a file under `nc-systems/<system>/`, a path the overview lists as a component, ...".
State: open

## E2 — possible problem: on the Mac, `resupervise-seat.py` and a by-hand `launch-claude-mac` start the handoff-supervisor from whatever checkout they run in

Found by: the two agents that wrote drafts of the overview, reading the code at commit 8e7ddb10a6e1efbbd9bbc08f8fae3d0159aa457a, re-checked against commit a6b1471e0263e72475cf11e362d0ce311af3cbe2; the line numbers below are at a6b1471e.
Goes wrong when: a person or agent runs `scripts/resupervise-seat.py <seat> --machine mac`, or `scripts/launch-claude-mac <seat>`, from a worktree. `launch-claude-mac` takes the handoff-supervisor from its own checkout, so the agent-seat's handoff-supervisor runs that worktree's code and stops at its first session-handoff after the worktree is removed, because it runs the extractor from its own checkout. `scripts/recover-crashed-seats.py` avoids this with its `--checkout` default of `~/Projects/nedschorus`; `resupervise-seat.py` could take the same default, and `launch-claude-mac` could warn when it is not run from `~/Projects/nedschorus`.
Rests on: `scripts/resupervise-seat.py:218` (`return SCRIPT_DIRECTORY / f"launch-claude-{machine}"`); `scripts/launch-claude-mac:76-77` (`REPOSITORY_ROOT=$(cd "$SCRIPT_DIRECTORY/.." && pwd)`, `SUPERVISOR="$REPOSITORY_ROOT/nc-systems/handoff/handoff-supervisor.py"`); `nc-systems/handoff/handoff-supervisor.py:167`; `scripts/recover-crashed-seats.py:117-118` (docstring, "Checkout:").
State: open

## E3 — improvement: delete the changeover check for handoff-supervisors that predate the flock lock

Found by: the two agents that wrote drafts of the overview, reading the code at commit 8e7ddb10a6e1efbbd9bbc08f8fae3d0159aa457a, re-checked against commit a6b1471e0263e72475cf11e362d0ce311af3cbe2; the line numbers below are at a6b1471e.
Gain: less code on the lock path. `refuse_old_code_supervisor` carries its own removal condition: "Delete this check once no supervisor started before this change is running." A `ps` for `handoff-supervisor.py` on both machines, compared with each process's start time, settles whether the condition holds. The legacy state-key migration is a similar candidate, once no `-supervisor-state.json` still holds `session_id`.
Rests on: `nc-systems/handoff/handoff-supervisor.py:1331-1356` (`refuse_old_code_supervisor`; the condition at `:1332`), `:352` and `:367-369` (`LEGACY_SESSION_ID_STATE_KEY` and its migration).
State: open

## E4 — improvement: one definition of the session-handoff's field names

Found by: the two agents that wrote drafts of the overview, reading the code at commit 8e7ddb10a6e1efbbd9bbc08f8fae3d0159aa457a, re-checked against commit a6b1471e0263e72475cf11e362d0ce311af3cbe2; the line numbers below are at a6b1471e.
Gain: the writer and the reader cannot drift apart. The writer script loads the handoff-supervisor and takes several names from it, yet defines `NEXT_STEP_VERBATIM_FIELD`, `NEXT_STEP_BLOCK_OPENING_MARKER`, `NEXT_STEP_BLOCK_TERMINATOR` and `SPAWNED_SUBAGENT_FIELD_PREFIX` again with the same values. Goes wrong when: one copy is changed and the other is not, and the writer writes a block the handoff-supervisor misreads.
Rests on: `nc-systems/handoff/handoff-write-and-check-supervisor.py:70-74` (loads the supervisor), `:77-79` and `:100` (the second definitions), `:81-92` (names taken from the supervisor); `nc-systems/handoff/handoff-supervisor.py:194-196` and `:198`.
State: open

## E5 — possible problem: every session-handoff waits on the main-gatekeeper's branch-protection audit

Found by: the two agents that wrote drafts of the overview, reading the code at commit 8e7ddb10a6e1efbbd9bbc08f8fae3d0159aa457a, re-checked against commit a6b1471e0263e72475cf11e362d0ce311af3cbe2; the line numbers below are at a6b1471e.
Goes wrong when: the audit or GitHub is slow; the writer script runs `main-gatekeeper.py audit` with a 45-second timeout before it reports whether a handoff-supervisor is watching, so a retiring agent-session near the end of its context waits up to that long on a check unrelated to the handoff, and prints the result to an agent about to stop. Nothing in the handoff-system acts on the result. If the audit is meant to reach someone, a scheduled job or the place where it is read may be a better home; if not, the call can go, making the writer script smaller and every session-handoff faster.
Rests on: `nc-systems/handoff/handoff-write-and-check-supervisor.py:358-374` (`run_branch_protection_audit`, `timeout=45` at `:369`), `:494`.
State: open

## E6 — improvement: bring up to date, or cut, the stale parts of the design of record

Found by: the two agents that wrote drafts of the overview, reading the code at commit 8e7ddb10a6e1efbbd9bbc08f8fae3d0159aa457a, re-checked against commit a6b1471e0263e72475cf11e362d0ce311af3cbe2; the line numbers below are at a6b1471e.
Gain: a reader of `nc-systems/handoff/handoff-design.md`, which the overview links, is not misled. The design still says the block form of the next step is queued, not built, though the writer and the handoff-supervisor both build it; and it still describes a writer that starts an adopting handoff-supervisor when none is watching ("self-healing"), a path the code no longer has: the writer script starts nothing, and the launchers run the handoff-supervisor as the pane's command. Under the refresh-design of GHI [refresh-design: when a system's code lands, bring its design, build-slice plan and overview into line — removing, never revising](https://github.com/nedschorus/nedschorus/issues/670), the stale parts would be removed.
Rests on: `nc-systems/handoff/handoff-design.md:47` ("the block form below is QUEUED, not built"), `:243` ("the writer starts an adopting supervisor"), `:278` ("the hook-fired skill run starts an adopting supervisor"), `:282` (a self-started supervisor's output); `nc-systems/handoff/handoff-write-and-check-supervisor.py:344-347` and `nc-systems/handoff/handoff-supervisor.py:194-196` (the block form, built); the writer script's only subprocess call is the audit at `:367`.
State: open

## E7 — improvement: drop the queue that no longer exists from the queue status line

Found by: the two agents that wrote drafts of the overview, reading the code at commit 8e7ddb10a6e1efbbd9bbc08f8fae3d0159aa457a, re-checked against commit a6b1471e0263e72475cf11e362d0ce311af3cbe2; the line numbers below are at a6b1471e.
Gain: one dead entry gone. The handoff-supervisor's queue status line lists `legacy-feature-queue`, which does not exist at this commit; the function skips missing directories, so this is dead code, not a failure. GHI [Queue drain procedure — the review process that empties the wiki queue, the pair queue, nc-queue, docs/drafts and the draft-label issue queue](https://github.com/nedschorus/nedschorus/issues/24) plans to take `nc-queue` out of the same line; the two changes fit one commit.
Rests on: `nc-systems/handoff/handoff-supervisor.py:640`.
State: open

## E8 — possible problem: an assertion of the overview is contradicted

Claim: `<session>-handoff-asked` and `<session>-handoff-deferred` are written by handoff-context-threshold-hook.py and read by it and by `scripts/agent-seat-due-task-raise-hook.py`. The first is deleted by the post-compaction hook; the second outlasts a compaction and is deleted by the threshold hook when it tells the agent to run /handoff.
Found by: the overview claim check of 2026-11-04 against commit 9ecda8345f6d2062befc44c042236d7e6c6ae6fa; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/0e70ae713f204f4060a2c90726caef86c5b80c19-2026-11-04T23-15-57-960804Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> The writer, deleters and the two named readers are borne out: handoff-context-threshold-hook.py:565, 585, 597; agent-seat-due-task-raise-hook.py:697-698; post-compaction-session-continues-hook.py:109-110. But the reader list leaves out a third reader of the deferred marker, scripts/agent-seat-idle-sweep-verdicts-print.py:79 `HANDOFF_DEFERRED_SUFFIX = "-handoff-deferred"`; an agent renaming the marker would miss it.
State: open

## E9 — possible problem: an assertion of the overview is contradicted

Claim: Diagram: agent-crash-watcher (ned-box, every minute) ──> recover-crashed-seats.py ──> launcher or tmux pane
Found by: the overview claim check of 2026-11-05 against commit ffda8acb53b803e99d2da40fd114686ee8fc0291; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/a9e58dc888a1fa644d2d69e0f307e6817a3a4746-2026-11-05T04-44-09-006473Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - On ned-box, recover-crashed-seats.py never runs a launcher. recover-crashed-seats.py:645-648 `if sys.platform == "darwin":` … `return durable_checkout / LAUNCH_CLAUDE_MAC_WITHIN_A_CHECKOUT` / `return None`
> - With no launcher, launch_seat takes the tmux branch at :855 `completed = run_tmux(`.
> - The watcher refuses to run anywhere but ned-box: handoff-agent-crash-watcher.py:76 `Off ned-box the program refuses: the agent-seats root it reads is ned-box's.`
> - So on this row the only target is the tmux pane. The rest of the overview says recover-crashed-seats.py starts a ned-box tmux server itself, so no agent would act wrongly on it.
State: open

## E10 — possible problem: an assertion of the overview is contradicted

Claim: `<session>-handoff-asked` and `<session>-handoff-deferred`, keyed by session ID, are written by the threshold hook and read by it and by `scripts/agent-seat-due-task-raise-hook.py`. The first is deleted by the post-compaction hook; the second outlasts a compaction and is deleted by the threshold hook when it asks for the handoff.
Found by: the overview claim check of 2026-11-05 against commit ffda8acb53b803e99d2da40fd114686ee8fc0291; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/a9e58dc888a1fa644d2d69e0f307e6817a3a4746-2026-11-05T04-44-09-006473Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The writers, the deletions and the due-task hook read are right: handoff-context-threshold-hook.py:565, 585, 597; post-compaction-session-continues-hook.py:110; agent-seat-due-task-raise-hook.py:708-709.
> - But the reader list names one outside reader and leaves out another: scripts/agent-seat-idle-sweep-verdicts-print.py:82 `HANDOFF_DEFERRED_SUFFIX = "-handoff-deferred"` and :531 `marker = paths.handoff_directory / f"{session_id}{HANDOFF_DEFERRED_SUFFIX}"`
> - The idle sweep keeps its own copy of the suffix, so renaming the marker from this list alone would silently break it.
State: open

## E11 — possible problem: an assertion of the overview is contradicted

Claim: `<seat>-leftovers-prompt-listing-counts.json`, how many first prompts have listed each leftover branch, worktree and work-snapshot: written and read by `handoff-supervisor.py` at each launch, keeping only the entries listed that time.
Found by: the overview claim check of 2026-11-05 against commit 10e18749c1f0845cb6ca1552068728dbf8d5d56e; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/d4fe8af9c49be5553a1747f5aceef6b79a14d35f-2026-11-05T05-53-15-888969Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> handoff-supervisor.py:1618-1620 `leftovers = "\n\n".join(part for part in leftover_parts if part)` / `if not leftovers: return prompt`. That return comes before `leftovers_with_prompt_listing_counts` (:1593-1605), so a launch with no leftovers neither reads nor rewrites the file. Its entries from an earlier launch stay, and :1602 `earlier.get(key, 0) + 1` counts on from them at the next launch that lists that entry. So the file is not touched at every launch, and it does not always hold only the last launch's entries.
State: open

## E12 — possible problem: an assertion of the overview is contradicted

Claim: The reference-checkout, `~/Projects/nedschorus` on each machine: fast-forwarded to main by `launch-claude-ubuntu` on ned-box, by `launch-claude-mac` on the Mac, and, at each session-handoff that launches a successor without consulting the user, by every handoff-supervisor that runs from it, and by the restart program.
Found by: the overview claim check of 2026-11-05 against commit 10e18749c1f0845cb6ca1552068728dbf8d5d56e; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/d4fe8af9c49be5553a1747f5aceef6b79a14d35f-2026-11-05T05-53-15-888969Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> A writer is missing: the Stop hook checkout-freshness-catch-up.py also fast-forwards the reference-checkout at each turn end. See checkout-freshness-catch-up.py:1779-1781 `reference = reference_checkout_of(root)` / `fast_forward_reference_checkout(reference, ...`, and :1567-1573 `operator_facing=False is the Stop hook ... This function runs at every turn end`. It is registered at .claude/settings.json:72. So the checkout can move under a running handoff-supervisor between session-handoffs. The listed writers hold: launch-claude-ubuntu:327, launch-claude-mac:280, handoff-supervisor.py:2215, restart program:19.
State: open

## E13 — possible problem: an assertion of the overview is contradicted

Claim: `<session>-handoff-asked` and `<session>-handoff-deferred` are read by the threshold hook and by `scripts/agent-seat-due-task-raise-hook.py`.
Found by: the overview claim check of 2026-11-08 against commit 10e18749c1f0845cb6ca1552068728dbf8d5d56e; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/83cab4082b64cb25a57a0892626dc5f2d9d48ffa-2026-11-08T00-33-58-763065Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - A third program reads the deferral marker: scripts/agent-seat-idle-sweep-verdicts-print.py:82 `HANDOFF_DEFERRED_SUFFIX = "-handoff-deferred"` and :531-533 `marker = paths.handoff_directory / f"{session_id}{HANDOFF_DEFERRED_SUFFIX}" ... marker.stat().st_mtime`.
> - The list of readers is incomplete. No agent opens a wrong file because of it.
State: open

## E14 — possible problem: an assertion of the overview is contradicted

Claim: `<seat>-leftovers-prompt-listing-counts.json` is written and read by `handoff-supervisor.py` at each launch, keeping only the entries listed that time.
Found by: the overview claim check of 2026-11-08 against commit 10e18749c1f0845cb6ca1552068728dbf8d5d56e; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/83cab4082b64cb25a57a0892626dc5f2d9d48ffa-2026-11-08T00-33-58-763065Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The counts file is not touched at a launch that lists no leftovers: handoff-supervisor.py:1618-1620 `leftovers = "\n\n".join(part for part in leftover_parts if part)` / `if not leftovers:` / `return prompt`.
> - So the entries from an earlier launch stay in the file. "At each launch" is loose; no agent acts wrongly on it.
State: open

## E15 — possible problem: an assertion of the overview is contradicted

Claim: `<seat>-handoff-NNNN.md` holds copies of consumed session-handoffs, kept by handoff-supervisor.py, which keeps the two newest generations of these and of the dialog files.
Found by: the overview claim check of 2026-11-05 against commit d08dc058fd63a331f346678ce36f067e533aa856; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/13f5a0f276a83d4a68bf40cd0a301b0278599b54-2026-11-05T22-06-08-886798Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - handoff-supervisor.py copies a consumed session-handoff to `<seat>-handoff-NNNN.md` only when the dialog extraction succeeded.
> - nc-systems/handoff/handoff-supervisor.py:2156-2165 `extracted = extract_dialog(...) if not extracted: ... return None, None` comes before `shutil.copy2(settings.handoff_path, settings.handoff_directory / f"{settings.agent}-handoff-{generation:04d}.md",)`
> - When extraction fails, the handoff is consumed (:2611 `state["consumed_counter"] = counter_from(handoff_fields)`) with no numbered copy.
> - The two-generation part is supported: :287 `GENERATIONS_KEPT = 2`, :2166-2167 prune_old_generations for -dialog and -handoff.
State: open

## E16 — possible problem: an assertion of the overview is contradicted

Claim: `<seat>-leftovers-prompt-listing-counts.json` counts how many first prompts have listed each leftover. handoff-supervisor.py writes and reads it at each launch, keeping only the entries listed that time.
Found by: the overview claim check of 2026-11-05 against commit d08dc058fd63a331f346678ce36f067e533aa856; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/13f5a0f276a83d4a68bf40cd0a301b0278599b54-2026-11-05T22-06-08-886798Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The counts file is read and rewritten only at a launch that lists at least one leftover.
> - nc-systems/handoff/handoff-supervisor.py:1625-1627 `leftovers = "\n\n".join(part for part in leftover_parts if part); if not leftovers: return prompt`: this return comes before leftovers_with_prompt_listing_counts (:1600-1612), which reads and rewrites the file.
> - So at a launch with nothing to list, the file is neither read nor written, and entries from an earlier launch survive.
State: open

## E17 — possible problem: an assertion of the overview is contradicted

Claim: `scripts/clean-worktrees.py`: before a removal it copies the worktree's review records to the log-store.
Found by: the overview claim check of 2026-11-05 against commit d08dc058fd63a331f346678ce36f067e533aa856; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/4f1e208f47643e513f48ee18957408dc1df2de05-2026-11-05T22-27-21-827479Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - What it ships is more than review records: clean-worktrees.py:45-50 `Before --remove removes one, it ships each walk in the worktree's docs/walk/, one for each <name>-minutes.md there, with d08dc058:scripts/walk-files-ship.py ... and each non-empty record directory under its cold-read-records/ and sanity-check-records/`.
> - It also keeps the worktree when a shipment fails (:51-52). "Review records" leaves out the approval-walk files. Loose wording; no agent would act wrongly.
State: open

## E18 — possible problem: an assertion of the overview is contradicted

Claim: Invariant: a supervisor restarted on main's code that cannot start, for want of the token or its lock, or one that fails with an error it does not handle, exits without a record, leaving any session-handoff waiting; so does one that cannot read the transcript of the agent-session it is about to resume.
Found by: the overview claim check of 2026-11-05 against commit d08dc058fd63a331f346678ce36f067e533aa856; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/4f1e208f47643e513f48ee18957408dc1df2de05-2026-11-05T22-27-21-827479Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The two reasons named are not the only startup exits without a record. The restarted process can also return early at handoff-supervisor.py:2752-2754 `if shutil.which(arguments.agent_command) is None: print(f"handoff-supervisor: no such command: ..."); return 3`, and at :2750-2751 `parser.error(f"--cd is not a directory: ...")`.
> - Both are handled errors that leave no exit record and the session-handoff waiting. The sentence reads as a full list of causes.
State: open

## E19 — possible problem: an assertion of the overview is contradicted

Claim: `<session>-handoff-asked` and `<session>-handoff-deferred`: written by the threshold hook and read by it and by `scripts/agent-seat-due-task-raise-hook.py`. The first is deleted by the post-compaction hook; the second outlasts a compaction and is deleted by the threshold hook when it asks for the handoff.
Found by: the overview claim check of 2026-11-05 against commit d08dc058fd63a331f346678ce36f067e533aa856; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/4f1e208f47643e513f48ee18957408dc1df2de05-2026-11-05T22-27-21-827479Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The writers, the deletions and the due-task hook read hold: handoff-context-threshold-hook.py:565, 585, 597; agent-seat-due-task-raise-hook.py:708-709 `if (handoff.fired_marker_path(session_id).exists() or handoff.deferred_marker_path(session_id).exists()):`; post-compaction-session-continues-hook.py:110 `marker.unlink()`.
> - The reader list leaves one out: scripts/agent-seat-idle-sweep-verdicts-print.py:82 `HANDOFF_DEFERRED_SUFFIX = "-handoff-deferred"` and :531 `marker = paths.handoff_directory / f"{session_id}{HANDOFF_DEFERRED_SUFFIX}"`.
> - The idle sweep keeps its own copy of the suffix, so renaming the marker from this list alone would break it.
State: open

## E20 — possible problem: an assertion of the overview is contradicted

Claim: The reference-checkout, `~/Projects/nedschorus` on each machine: fast-forwarded to main by `launch-claude-ubuntu` on ned-box, by `launch-claude-mac` on the Mac, at each non-consulting handoff by every supervisor running from it, and by the restart program; put back on main by the leftovers program.
Found by: the overview claim check of 2026-11-05 against commit d08dc058fd63a331f346678ce36f067e533aa856; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/4f1e208f47643e513f48ee18957408dc1df2de05-2026-11-05T22-27-21-827479Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - A writer is missing: the Stop hook checkout-freshness-catch-up.py also fast-forwards the reference-checkout at each turn end.
> - checkout-freshness-catch-up.py:1779-1782 `reference = reference_checkout_of(root)` / `fast_forward_reference_checkout(reference, arguments.interval_seconds, operator_facing=False)`, and :1573 `This function runs at every turn end`. It is registered at .claude/settings.json:72.
> - So the checkout can move under a running supervisor between handoffs.
> - The listed writers hold: launch-claude-ubuntu:327, launch-claude-mac:280, handoff-supervisor.py:2273, the restart program :19, the leftovers program :20.
State: open

## E21 — possible problem: an assertion of the overview is contradicted

Claim: `NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER`: set by `scripts/ghi-guide-agent-ask.py` for the `claude` it starts; silences `handoff-context-threshold-hook.py`; removed by the supervisor from every agent-session it starts.
Found by: the overview claim check of 2026-11-05 against commit d08dc058fd63a331f346678ce36f067e533aa856; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/4f1e208f47643e513f48ee18957408dc1df2de05-2026-11-05T22-27-21-827479Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The setter, the threshold-hook read and the removal hold: ghi-guide-agent-ask.py:575; handoff-context-threshold-hook.py:513-514 `if os.environ.get(REINCARNATION_OWNED_BY_CALLER_VARIABLE): return 0`; handoff-supervisor.py:325.
> - It silences more hooks than the threshold hook: agent-seat-due-task-raise-hook.py:754 `if environment.get(REINCARNATION_OWNED_BY_CALLER_VARIABLE):`, absence-claim-locator-reminder-hook.py:460, cold-read-fast-read-due-for-linked-document-reminder-hook.py:509, ned-box-path-in-agent-reply-unclickable-on-mac-warning-hook.py:268, and nc-systems/general-tools/shell-command-tree-sitter-bash-reader-common.py:474.
> - An agent renaming or changing the variable from this entry alone would miss them.
State: open

## E22 — possible problem: an assertion of the overview is unsupported

Claim: Entry: the install scripts are run by a person. The `list` command of `uncommitted-work-snapshots.py` is run by a person, or an agent its initial-agent-instructions send there. The `write` and `show` commands of `worktree-owner-file-read-and-write.py` are run by a person or a program that makes a worktree.
Found by: the overview claim check of 2026-11-05 against commit d08dc058fd63a331f346678ce36f067e533aa856; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/4f1e208f47643e513f48ee18957408dc1df2de05-2026-11-05T22-27-21-827479Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The install scripts and the `list` command are borne out: uncommitted-work-snapshots.py:639 and :631 hand the agent `list_command_text(agent_seat)`.
> - No program in the repository runs the owner-file module's `write` or `show` command.
> - Search `worktree-owner-file-read-and-write` in non-test files finds only the module itself, uncommitted-work-snapshot-hook.py (which calls the function worktree_owner_file_write at :132, not the command), clean-worktrees.py, the weekly owner check, the first-prompt list and the overview.
> - Search `owner-file-read-and-write\.py (write|show)|worktree_owner_file_write` in *.md finds nothing.
> - The launchers' `git worktree add` (launch-claude-mac:253, launch-claude-ubuntu:308) writes no owner file. The module's docstring :25-26 describes the intended writer, but none exists.
> - Files read: worktree-owner-file-read-and-write.py, uncommitted-work-snapshot-hook.py, clean-worktrees.py, both launchers.
State: open

## E23 — possible problem: an assertion of the overview is contradicted

Claim: `<session>-handoff-asked` and `<session>-handoff-deferred` are written by handoff-context-threshold-hook.py and read by it and by scripts/agent-seat-due-task-raise-hook.py.
Found by: the overview claim check of 2026-11-08 against commit d08dc058fd63a331f346678ce36f067e533aa856; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/e4e0413d9567614cd111da020834e83fb6c826f1-2026-11-08T09-00-03-176432Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The list of readers is incomplete. scripts/agent-seat-idle-sweep-verdicts-print.py:531-533 also reads the deferred marker: "marker = paths.handoff_directory / f\"{session_id}{HANDOFF_DEFERRED_SUFFIX}\" ... put_off_at = datetime.fromtimestamp(marker.stat().st_mtime, timezone.utc)" (with HANDOFF_DEFERRED_SUFFIX = "-handoff-deferred" at line 82).
> - The rest of the row is supported: the writers are at handoff-context-threshold-hook.py:565 and 585; the post-compaction hook deletes the first marker; the threshold hook deletes the second at lines 595-597.
State: open

## E24 — possible problem: an assertion of the overview is contradicted

Claim: `<seat>-leftovers-prompt-listing-counts.json` is written and read by the handoff-supervisor at each launch, keeping only the entries listed that time.
Found by: the overview claim check of 2026-11-08 against commit d08dc058fd63a331f346678ce36f067e533aa856; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/e4e0413d9567614cd111da020834e83fb6c826f1-2026-11-08T09-00-03-176432Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - nc-systems/handoff/handoff-supervisor.py:1626-1627 "if not leftovers: return prompt". The counts file is read and written only inside leftovers_with_prompt_listing_counts (lines 1606-1612), which is called only when something is listed (lines 1628-1629).
> - So a launch that lists nothing neither reads nor writes the file, and earlier entries stay. "At each launch" and "keeping only the entries listed that time" are true only for launches that list leftovers.
State: open

## E25 — possible problem: an assertion of the overview is contradicted

Claim: Shared state: the reference-checkout `~/Projects/nedschorus`. The overview lists its writers as the launchers, every handoff-supervisor that runs from it at a session-handoff, and the restart program.
Found by: the overview claim check of 2026-11-06 against commit e0f608a0a433a189da0c362861753d098c48a959; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/260741fa9320708ce9cb7822f6e8e78798963c5e-2026-11-06T15-22-52-331480Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The list leaves out the Stop hook checkout-freshness-catch-up.py, which fast-forwards it at every turn boundary.
> - scripts/checkout-freshness-catch-up.py:11 `Wired as a Stop hook, so it runs at every turn boundary. Each run:`
> - same file:61-63 `6. The machine's reference checkout — the main worktree of the same repository, parked on main — gets a fast-forward-only pull on the same rhythm, under its own stamp.`
> - The list is incomplete, but no agent would open the wrong file on it.
State: open

## E26 — possible problem: an assertion of the overview is contradicted

Claim: These leftovers go between the opening of the initial-agent-instructions and their next step, under one sentence that says to keep, delete or hand on each before the next step. Each entry opens with how many first prompts have listed it, and the branches the first-prompt list deleted go above that sentence.
Found by: the overview claim check of 2026-11-06 against commit e0f608a0a433a189da0c362861753d098c48a959; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/eb5b14ff122f03688551f6bfc827f605d3fd032d-2026-11-06T15-33-42-134028Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - `nc-systems/handoff/handoff-supervisor.py:1690-1691` "The prompt with the leftovers between its opening and its next step, or after it when it has no next step."
> - `nc-systems/handoff/handoff-supervisor.py:1712-1713` "if not next_step_heading: return f\"{prompt}\n\n{inserted}\""
> - A resume launch uses RESUME_PROMPT_WHEN_A_SESSION_ENDED_WITHOUT_A_HANDOFF (`nc-systems/handoff/handoff-supervisor.py:249-253`), which has no next-step heading. For a resume, which the same paragraph says every launch includes, the leftovers therefore come after the prompt.
> - The sentence, the counts and the deleted-branches placement are borne out at `nc-systems/handoff/handoff-supervisor.py:1638-1642`, `:1672` and `:1701-1705`.
> - Suggested fix: add "or after the prompt when it has no next step".
State: open

## E27 — possible problem: an assertion of the overview is contradicted

Claim: At its first launch: it carries out a waiting session-handoff unless started with `--resume-session-id`; otherwise it starts fresh when an exit is recorded, else resumes the last transcript worth resuming, and stops when it cannot read the transcript folder.
Found by: the overview claim check of 2026-11-08 against commit 31905b3dea48908baf818723090b23b5388cfa49; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/827a7befcb763718932936563f8664e9bd99ebad-2026-11-08T23-20-02-417909Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - nc-systems/handoff/handoff-supervisor.py:2440-2443 `if (not settings.resume_session_id and not settings.first_prompt_wins_over_crashed_transcript and ignition_plan is None and agent_exit_record_from_supervisor_state(state) is None):`
> - :2690-2694 `"--first-prompt-file-wins-over-crashed-transcript"` … `"start fresh on --first-prompt-file even when this seat has a crashed transcript worth resuming"`
> - With that flag the handoff-supervisor starts fresh even when there is no exit record. `recover-crashed-seats.py` passes the flag for its conversation-tail start (recover-crashed-seats.py:86), so "else resumes" is incomplete. The rest is supported: :2385-2395 marks a waiting session-handoff consumed under `--resume-session-id`; :2446-2455 stops with exit 5 on an unreadable transcript folder.
State: open

## E28 — possible problem: an assertion of the overview is contradicted

Claim: `clean-worktrees.py`: "a worktree with no owner file, or locked, as Claude Code locks a subagent's worktree while the subagent runs, is kept".
Found by: the overview claim check of 2026-11-08 against commit 31905b3dea48908baf818723090b23b5388cfa49; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/827a7befcb763718932936563f8664e9bd99ebad-2026-11-08T23-20-02-417909Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - scripts/clean-worktrees.py:13-14 `it has no owner file, as agent-homes and worktrees made by hand have, and is not a merge-lane review checkout`
> - :61-68: a worktree with no owner file inside `~/.cache/merge-lane-review-worktrees` is removed once its pull request was merged or closed 24 hours ago.
> - The rest of the row is supported: :33-47 (owner running or stopped, branch for detached commits, work-snapshot of uncommitted files).
State: open

## E29 — possible problem: an assertion of the overview is contradicted

Claim: `<session>-handoff-deferred` "is also read … by scripts/agent-seat-idle-sweep-verdicts-print.py, which spells the suffix itself".
Found by: the overview claim check of 2026-11-08 against commit 31905b3dea48908baf818723090b23b5388cfa49; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/827a7befcb763718932936563f8664e9bd99ebad-2026-11-08T23-20-02-417909Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - scripts/agent-seat-idle-sweep-verdicts-print.py:68-70 `deferred_marker_files = _load("handoff_deferred_marker_and_refused_commands_files_common", …)`; :533 `marker = deferred_marker_files.handoff_deferred_marker_path(`
> - It takes the path from the common module. A grep of that file for the literal `-handoff-deferred` finds only the module's file name.
> - The rest of the row is supported: threshold hook :696-730 and :742-745; due-task hook :711-712; guard hook :192; writer :463; deferred-marker module :35 `"-handoff-deferred-fired"`; post-compaction :109-110.
State: open

## E30 — possible problem: an assertion of the overview is contradicted

Claim: The reference-checkout `~/Projects/nedschorus` is "fast-forwarded to main by launch-claude-ubuntu on ned-box, by launch-claude-mac on the Mac, and, at each session-handoff …, by every handoff-supervisor that runs from it, and by the restart program".
Found by: the overview claim check of 2026-11-08 against commit 31905b3dea48908baf818723090b23b5388cfa49; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/827a7befcb763718932936563f8664e9bd99ebad-2026-11-08T23-20-02-417909Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - scripts/checkout-freshness-catch-up.py:11 `Wired as a Stop hook, so it runs at every turn boundary.`; :61-62 `6. The machine's reference checkout — the main worktree of the same repository, parked on main — gets a fast-forward-only pull on the same rhythm`; .claude/settings.json:73
> - Every agent-session's Stop hook also fast-forwards it at every turn, and that writer is left out.
> - The listed writers are right: launch-claude-mac:288, launch-claude-ubuntu:335, handoff-supervisor.py:2304, restart program :19, back-on-main :16-20.
State: open

## E31 — possible problem: an assertion of the overview is contradicted

Claim: clean-worktrees.py keeps "a worktree with no owner file, or locked ..."
Found by: the overview claim check of 2026-11-08 against commit 31905b3dea48908baf818723090b23b5388cfa49; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/b734eef5ed84f6f5ef61190b13c31f2755202c73-2026-11-08T23-29-10-938461Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - scripts/clean-worktrees.py:13-14 "it has no owner file, as agent-homes and worktrees made by hand have, and is not a merge-lane review checkout"
> - scripts/clean-worktrees.py:61-68 "A worktree with no owner file directly inside ~/.cache/merge-lane-review-worktrees ... It is removed when that pull request was merged or closed at least 24 hours ago"
> - scripts/worktree-owner-file-read-and-write.py:38-41 "The cleaner never removes a worktree with no owner file, except a merge-lane review checkout"
> - scripts/clean-worktrees.py:49-52: a Claude Code lock whose process has ended is unlocked by --remove.
> - The overview leaves out both exceptions. The rest of the sentence is supported: :33-47 (rules while the owner runs and after it stops), :85 (records shipped before removal), :108-110 (branches), :192-208 (the log, using `run_on_ned_box_or_here`), :169 (work-snapshots deleted after ten days).
State: open

## E32 — possible problem: an assertion of the overview is contradicted

Claim: The asked and deferred markers. The overview says the second marker is read "by `scripts/agent-seat-idle-sweep-verdicts-print.py`, which spells the suffix itself".
Found by: the overview claim check of 2026-11-08 against commit 31905b3dea48908baf818723090b23b5388cfa49; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/b734eef5ed84f6f5ef61190b13c31f2755202c73-2026-11-08T23-29-10-938461Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - scripts/agent-seat-idle-sweep-verdicts-print.py:68-70 `deferred_marker_files = _load("handoff_deferred_marker_and_refused_commands_files_common", ...)`
> - scripts/agent-seat-idle-sweep-verdicts-print.py:533 `marker = deferred_marker_files.handoff_deferred_marker_path(`
> - A grep for `handoff-deferred` or `DEFERRED` in that file finds no suffix spelled there. It takes the suffix from the shared module, like the other readers.
> - The rest of the bullet is supported: agent-seat-due-task-raise-hook.py:711-712 reads both markers; the guard hook :47; the writer :463; post-compaction :109-110; handoff-deferred-marker-and-refused-commands-files-common.py:35 `"-handoff-deferred-fired"`; threshold hook :744.
State: open

## E33 — possible problem: an assertion of the overview is contradicted

Claim: The successor's initial-agent-instructions give the next step and the sync's result, and either name the conversation-tail and roster or say where the transcript is. On the Mac they carry the memory review when due. For agent-instructions-editor alone they carry "an overview refresh reminder for each system whose code has moved past the commit its nc-architecture-overview names".
Found by: the overview claim check of 2026-11-09 against commit a17081fe3b0d0c6092273fa1e910bd22528cdd78; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/b7ae570d5bf93bceaf69d8d7d04bf3f3ee37db26-2026-11-09T01-08-43-906731Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> Supported parts:
> - handoff-supervisor.py:1130, :1135, :1144 (roster) and :1165 (next step).
> - handoff-supervisor.py:1204-1210: when extraction failed, the note gives `that session's transcript is {self.unextracted_transcript_path}`.
> - handoff-supervisor.py:1576-1580: no memory review line on ned-box or before noon Pacific.
> - handoff-supervisor.py:2483-2484: `if settings.agent == AGENT_SEAT_GIVEN_OVERVIEW_REFRESH_LINES`.
> Contradicting lines: the reminder is not given for every system whose code moved. It is withheld when an open pull request already changes that overview, or when the user was shown that refresh earlier the same day.
> - handoff-supervisor.py:1530-1532 `print(f"handoff-supervisor: overview check for {system} withheld its line: " f"the open pull request \"{title}\" ({url}) already changes " f"{overview_path}")`
> - handoff-supervisor.py:1564-1565 `print(f"handoff-supervisor: overview check for {system} withheld its line: the " f"user was shown this overview's refresh today`
> The daily withholding is stated under handoff-architecture-overview-refresh-user-shown-mark.py. The open-pull-request withholding is stated nowhere in the overview. No agent would act wrongly on the omission.
State: open

## E34 — possible problem: an assertion of the overview is contradicted

Claim: `clean-worktrees.py` removes the worktrees of the clone, other than the reference-checkout, whose work is done. "a worktree with no owner file, or locked ..., is kept". While its owner runs a worktree goes only after its pull request merged or closed and nothing is uncommitted; once its owner has stopped it goes unless an open pull request keeps it, after branching and snapshotting.
Found by: the overview claim check of 2026-11-09 against commit a17081fe3b0d0c6092273fa1e910bd22528cdd78; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/b7ae570d5bf93bceaf69d8d7d04bf3f3ee37db26-2026-11-09T01-08-43-906731Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> Supported parts:
> - clean-worktrees.py:5-6 `Every worktree of the clone except its main checkout, the reference-checkout`
> - clean-worktrees.py:33-47: the while-running and once-stopped rules.
> Contradicting lines: a merge-lane review checkout has no owner file and can still be removed.
> - clean-worktrees.py:13-14 `it has no owner file, as agent-homes and worktrees made by hand have, and is not a merge-lane review checkout;`
> - clean-worktrees.py:63-70 `A worktree with no owner file directly inside ~/.cache/merge-lane-review-worktrees ... is removed when that pull request was merged or closed at least 24 hours ago`
> The overview's rule is incomplete, but no agent works in those checkouts, so no agent would act wrongly.
State: open

## E35 — possible problem: an assertion of the overview is contradicted

Claim: handoff-supervisor: "These leftovers go between the opening of the initial-agent-instructions and their next step", under the background-subagent instructions, with listing counts, and the deleted branches above that sentence.
Found by: the overview claim check of 2026-11-09 against commit 731c1517b92f4ddaa928f0cfbc7afe98dbc275ad; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/c39cbdf2d362ca565b27ae65b14c052b8a29eeac-2026-11-09T04-56-31-029366Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The instructions, counts and deleted-branch placement are supported by `nc-systems/handoff/handoff-supervisor.py:1633-1639` and :1703-1707.
> - Contradicted for prompts that have no next step, such as a resume prompt or the first prompt of an agent-seat without a session-handoff. There the leftovers go after the prompt: `nc-systems/handoff/handoff-supervisor.py:1689` "or after it when it has no next step"; :1714-1715 `if not next_step_heading: return f"{prompt}\n\n{inserted}"`.
> - Incomplete wording; no agent would act wrongly on it.
State: open

## E36 — possible problem: an assertion of the overview is contradicted

Claim: handoff-supervisor: at its first launch it carries out a waiting session-handoff, unless started with `--resume-session-id`; "otherwise it starts fresh when an exit is recorded, and else resumes the agent-seat's last transcript worth resuming", and stops when it cannot read the transcript folder.
Found by: the overview claim check of 2026-11-09 against commit 731c1517b92f4ddaa928f0cfbc7afe98dbc275ad; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/c39cbdf2d362ca565b27ae65b14c052b8a29eeac-2026-11-09T04-56-31-029366Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The handoff, `--resume-session-id`, exit-record and stop parts are supported by `nc-systems/handoff/handoff-supervisor.py:2393-2403`, :2406-2444 and :2455-2463.
> - The sentence leaves out a third case that also starts fresh with no exit recorded: `nc-systems/handoff/handoff-supervisor.py:2449` `and not settings.first_prompt_wins_over_crashed_transcript`, set by `--first-prompt-file-wins-over-crashed-transcript` (:2697-2703).
> - Incomplete; no agent would act wrongly on it.
State: open

## E37 — possible problem: an assertion of the overview is contradicted

Claim: `clean-worktrees.py`: "a worktree with no owner file, or locked ... is kept".
Found by: the overview claim check of 2026-11-09 against commit 731c1517b92f4ddaa928f0cfbc7afe98dbc275ad; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/c39cbdf2d362ca565b27ae65b14c052b8a29eeac-2026-11-09T04-56-31-029366Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - Contradicted for merge-lane review checkouts, which have no owner file and are removed: `scripts/clean-worktrees.py:6-8` "Only a worktree holding an owner file, or a merge-lane review checkout ... can be removed", and :64-71 "It is removed when that pull request was merged or closed at least 24 hours ago".
> - Also `scripts/worktree-owner-file-read-and-write.py:38-41`.
> - The owner-running and owner-stopped rules are supported by `scripts/clean-worktrees.py:34-48`.
> - Incomplete; no agent-seat other than merge-lane-2 works in that directory, so no agent would act wrongly.
State: open

## E38 — possible problem: an assertion of the overview is contradicted

Claim: Invariant: "When the checkout cannot be brought to main's commit, or the replacement fails, it carries on with its old code, and the successor's initial-agent-instructions ... name the program to run: the reference-checkout leftovers-saving back-on-main program when the handoff-supervisor runs from the reference-checkout and the replacement itself did not fail ... and the restart program otherwise."
Found by: the overview claim check of 2026-11-11 against commit 84a92dd16d5d3d180f2214e2f3a7c2541fb62562; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/38d35b2b5174f76b24a910ba1bd21d16812534dd-2026-11-11T22-22-26-436876Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - handoff-supervisor.py:2382-2388 `if report and REPOSITORY_ROOT == REFERENCE_CHECKOUT:` ... `reference_checkout_back_on_main.put_reference_checkout_back_on_main(` (the supervisor runs the leftovers-saving step itself first)
> - :2320-2324 the back-on-main program is named only `if back_on_main_program_failure_output:`, that is, only when the supervisor's own run of it failed.
> - :2398-2400 `report = launch_time_git_sync_of_own_checkout_first_line_if_not_on_main()` / `if report: return handoff_supervisor_not_restarted_notice_and_console_line(report, settings.agent)`: when the program succeeded but the checkout is still not on main, the restart program is named (:2325-2328).
> - handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch.py:8-11 "the handoff-supervisor runs this program's put_reference_checkout_back_on_main itself and, when it succeeds, restarts"
> - The overview never says the supervisor runs this step itself. An agent changing the back-on-main program would not know the supervisor loads it at startup (handoff-supervisor.py:225-233). An agent reading a not-restarted notice that names the back-on-main program would not know it has already been run once.
State: open

## E39 — possible problem: an assertion of the overview is contradicted

Claim: Shared state, the task list under `~/.claude/tasks/`: "written by Claude Code; completed tasks removed by the writer script, which compares each with its copy in the log-store, ... written by `transcript-mirror-to-log-store.py`."
Found by: the overview claim check of 2026-11-11 against commit 84a92dd16d5d3d180f2214e2f3a7c2541fb62562; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/38d35b2b5174f76b24a910ba1bd21d16812534dd-2026-11-11T22-22-26-436876Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - uncommitted-work-snapshots.py:34-35 restore "opens a task naming the branch on the task list ~/.claude/tasks/<CLAUDE_CODE_TASK_LIST_ID>"
> - clean-worktrees.py:227-230 "--remove ... marks the task completed, adding a line at the end of its description"
> - handoff-agent-crash-watcher.py:49-51 "A failure an agent can fix becomes a task on an agent-seat's task list, ~/.claude/tasks/nedschorus-<seat>-tasks/"
> - handoff-write-and-check-supervisor.py:611-617 `copy_task_files_to_log_store`: the writer itself rsyncs the log-store copies before comparing.
> - The path agent-session-files-by-machine/<machine>/tasks/ is supported: transcript-mirror-to-log-store.py:33.
State: open

## E40 — possible problem: an assertion of the overview is contradicted

Claim: Shared state, the reference-checkout `~/Projects/nedschorus`: "fast-forwarded to main by launch-claude-ubuntu ..., by launch-claude-mac ..., by every handoff-supervisor that runs from it, and by the restart program; put back on main by the reference-checkout leftovers-saving back-on-main program"
Found by: the overview claim check of 2026-11-11 against commit 84a92dd16d5d3d180f2214e2f3a7c2541fb62562; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/38d35b2b5174f76b24a910ba1bd21d16812534dd-2026-11-11T22-22-26-436876Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - scripts/checkout-freshness-catch-up.py:1896-1898 `reference = reference_checkout_of(root)` / `fast_forward_reference_checkout(reference, ...)` in the Stop hook path. :1661-1662 "operator_facing=False is the Stop hook", so every agent-session's turn end also fast-forwards it.
> - handoff-supervisor.py:2386-2388 `reference_checkout_back_on_main.put_reference_checkout_back_on_main(REFERENCE_CHECKOUT, ...)`: the supervisor itself puts it back on main.
> - The listed writers are borne out: launch-claude-ubuntu:335, launch-claude-mac:288, handoff-supervisor.py:2357, restart program :19.
State: open

## E41 — possible problem: an assertion of the overview is contradicted

Claim: Entry point: "The reference-checkout leftovers-saving back-on-main program: an agent-seat whose initial-agent-instructions name it, because its handoff-supervisor did not restart itself on main's code."
Found by: the overview claim check of 2026-11-11 against commit 84a92dd16d5d3d180f2214e2f3a7c2541fb62562; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/38d35b2b5174f76b24a910ba1bd21d16812534dd-2026-11-11T22-22-26-436876Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch.py:8-9 "the handoff-supervisor runs this program's put_reference_checkout_back_on_main itself"
> - handoff-supervisor.py:2387 `reference_checkout_back_on_main.put_reference_checkout_back_on_main(`
> - The handoff-supervisor is also a caller, at each session-handoff where it would restart itself and the reference-checkout will not fast-forward.
State: open

## E42 — possible problem: an assertion of the overview is contradicted

Claim: The leftovers-saving back-on-main program saves the leftovers to a branch it pushes, "and only then puts the checkout back on main".
Found by: the overview claim check of 2026-11-11 against commit 84a92dd16d5d3d180f2214e2f3a7c2541fb62562; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/2849acdfa8c72239374f9f407c895e6404784896-2026-11-11T23-05-48-837391Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - nc-systems/handoff/handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch.py:27-29 `runs git switch --no-overwrite-ignore -C main origin/main ... whether or not every push succeeded, because every agent-seat's git hooks and the cron jobs run from this checkout`
> - The checkout goes back on main even when the push failed; unpushed leftovers stay only on a local branch (:17-18, :23).
> - The overview also never says that the handoff-supervisor runs this program's `put_reference_checkout_back_on_main` itself (handoff-supervisor.py:2382-2388; this program's docstring :7-11).
State: open

## E43 — possible problem: an assertion of the overview is contradicted

Claim: When the restart cannot happen, the successor's notice names the back-on-main program whenever the supervisor runs from the reference-checkout and the replacement itself did not fail, and the restart program otherwise.
Found by: the overview claim check of 2026-11-11 against commit 84a92dd16d5d3d180f2214e2f3a7c2541fb62562; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/2849acdfa8c72239374f9f407c895e6404784896-2026-11-11T23-05-48-837391Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - handoff-supervisor.py:2382-2394: the back-on-main program is named only when the supervisor's own run of `put_reference_checkout_back_on_main` failed.
> - :2398-2400 `report = launch_time_git_sync_of_own_checkout_first_line_if_not_on_main()` / `if report: return handoff_supervisor_not_restarted_notice_and_console_line(report, settings.agent)`: when that run succeeded but the checkout is still not at main, the notice names the restart program (:2325-2328).
> - The overview also omits that the supervisor runs the back-on-main step itself before giving up.
State: open

## E44 — possible problem: an assertion of the overview is unsupported

Claim: The owner file's writers are the post-checkout hook, the snapshot hook, clean-worktrees, the backfill script and the module's `write` command.
Found by: the overview claim check of 2026-11-11 against commit 84a92dd16d5d3d180f2214e2f3a7c2541fb62562; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/2849acdfa8c72239374f9f407c895e6404784896-2026-11-11T23-05-48-837391Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - Files read: uncommitted-work-snapshots.py, worktree-owner-file-read-and-write.py.
> - The list is incomplete: the `restore` command of uncommitted-work-snapshots.py also writes owner files through the module's function (uncommitted-work-snapshots.py:910-914 `owners.worktree_owner_file_write(worktree, owners.OWNER_AGENT_SEAT, agent_seat)`).
State: open

## E45 — possible problem: an assertion of the overview is unsupported

Claim: The agent-seat's task list is written by Claude Code, and completed tasks are removed by the writer script.
Found by: the overview claim check of 2026-11-11 against commit 84a92dd16d5d3d180f2214e2f3a7c2541fb62562; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/2849acdfa8c72239374f9f407c895e6404784896-2026-11-11T23-05-48-837391Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - Files read: handoff-agent-crash-watcher.py, uncommitted-work-snapshots.py, clean-worktrees.py.
> - Programs in this system also write the task list, and the overview leaves them out:
>   - handoff-agent-crash-watcher.py:1101-1104 `task_list = task_lists_directory / f"nedschorus-{agent_seat}-tasks"` writes new tasks.
>   - uncommitted-work-snapshots.py:949-952: `restore` opens a task.
>   - clean-worktrees.py:221 `Last, it closes the tasks that uncommitted-work-snapshots.py restore opens`.
State: open

## E46 — possible problem: an assertion of the overview is unsupported

Claim: Entry points: the install scripts (a person); the `list` command of uncommitted-work-snapshots.py (a person or an agent); the `write` and `show` commands of the owner-file module.
Found by: the overview claim check of 2026-11-11 against commit 84a92dd16d5d3d180f2214e2f3a7c2541fb62562; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/2849acdfa8c72239374f9f407c895e6404784896-2026-11-11T23-05-48-837391Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - Files read: uncommitted-work-snapshots.py.
> - The module also has `restore` and `discard` commands (uncommitted-work-snapshots.py:29-39, :1138-1148).
> - The first prompt sends agents to these commands: :605-612 `return f"{program} restore {snapshot['ref']} --keep {files}"`, :633 `parts.append(f"handle it with: `{entry_command_text(repo, snapshot)}`")`.
> - These entry points are missing from Entry points and from Components.
State: open

## E47 — possible problem: an assertion of the overview is contradicted

Claim: The back-on-main program saves the reference-checkout's leftovers to a branch it pushes, "and only then puts the checkout back on main".
Found by: the overview claim check of 2026-11-12 against commit 1b6fb19aeab73778f234b7552b2f7dfec1ef2cef; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/fd86d56b9bc675e893af7a8f405bbde8898a40f5-2026-11-12T05-18-38-382372Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - nc-systems/handoff/handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch.py:27-29 "then runs `git switch --no-overwrite-ignore -C main origin/main`, which puts the local main at origin/main and checks it out, whether or not every push succeeded"
> - nc-systems/handoff/handoff-supervisor.py:2288-2290 "once the checkout is on main, which it can be even after a failed push, so a leftovers branch the program could not push stays only in that checkout"
> - The leftovers are saved on a local branch before the switch, and the switch does not wait for the push to succeed. "Only then" overstates the order.
State: open

## E48 — possible problem: an assertion of the overview is contradicted

Claim: The agent-seat's task list under `~/.claude/tasks/` is "written by Claude Code"; the writer script removes completed tasks; the log-store copy is "written by `transcript-mirror-to-log-store.py`".
Found by: the overview claim check of 2026-11-12 against commit 1b6fb19aeab73778f234b7552b2f7dfec1ef2cef; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/fd86d56b9bc675e893af7a8f405bbde8898a40f5-2026-11-12T05-18-38-382372Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - nc-systems/handoff/handoff-agent-crash-watcher.py:1101-1104 `task_list = task_lists_directory / f"nedschorus-{agent_seat}-tasks"` ... `agent_seat_task_list_new_pending_task_write(` (the crash watcher writes tasks to agent-seat task lists).
> - nc-systems/handoff/uncommitted-work-snapshots.py:34 "opens a task naming the branch on the task list ~/.claude/tasks/<CLAUDE_CODE_TASK_LIST_ID>"
> - scripts/clean-worktrees.py:221-230 (marks restore tasks completed in every task list)
> - nc-systems/handoff/handoff-write-and-check-supervisor.py:616-618 "Copy the named task files into the log-store's copy of the list ... The mirror runs on a timer" (the writer also writes the log-store copy)
> - The lists of writers are incomplete. No one would act wrongly on them.
State: open

## E49 — possible problem: an assertion of the overview is contradicted

Claim: The reference-checkout is fast-forwarded by both launchers, by every supervisor running from it at a qualifying session-handoff, and by the restart program. It is "put back on main by the reference-checkout leftovers-saving back-on-main program, which pushes any leftovers in it to a `reference-checkout-leftovers-<date>` branch first".
Found by: the overview claim check of 2026-11-12 against commit 1b6fb19aeab73778f234b7552b2f7dfec1ef2cef; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/fd86d56b9bc675e893af7a8f405bbde8898a40f5-2026-11-12T05-18-38-382372Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - Fast-forwarders are supported: launch-claude-ubuntu:335, launch-claude-mac:288, handoff-supervisor.py:2357, restart program:19.
> - nc-systems/handoff/handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch.py:27-29 "...checks it out, whether or not every push succeeded". The leftovers are committed to a local branch first; the push is attempted, not guaranteed, before the switch.
State: open

## E50 — possible problem: an assertion of the overview is contradicted

Claim: Entry points: "The install scripts: a person. The `list` command of `uncommitted-work-snapshots.py`: a person, or an agent its initial-agent-instructions send there. The `write` and `show` commands of `worktree-owner-file-read-and-write.py`: a person or a program that makes a worktree."
Found by: the overview claim check of 2026-11-12 against commit 1b6fb19aeab73778f234b7552b2f7dfec1ef2cef; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/fd86d56b9bc675e893af7a8f405bbde8898a40f5-2026-11-12T05-18-38-382372Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - nc-systems/handoff/uncommitted-work-snapshots.py:15-17 "lists an agent-seat's lost work in the first prompt of every agent-session it starts, each entry ending with the restore or discard command that handles it"
> - nc-systems/handoff/uncommitted-work-snapshots.py:29, 38 (`restore` and `discard`)
> - The `restore` and `discard` commands are entry points that an agent the initial-agent-instructions send there runs. The section omits them, so it is incomplete. What it does say is true.
State: open

## E51 — possible problem: an assertion of the overview is contradicted

Claim: Diagram row: agent-crash-watcher (ned-box, every minute) ──> recover-crashed-seats.py ──> launcher or tmux pane.
Found by: the overview claim check of 2026-11-12 against commit 1b6fb19aeab73778f234b7552b2f7dfec1ef2cef; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/c6db3c481b478830a1784c634a6acd8cd1b1e318-2026-11-12T06-25-19-226589Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The agent-crash-watcher runs only on ned-box. There recover-crashed-seats.py never runs a launcher: it always starts the tmux pane itself. So the "launcher or" in this row cannot happen.
> - recover-crashed-seats.py:645-651 `"""Return the durable checkout’s Mac launcher, or None off macOS."""` ... `if sys.platform == "darwin": ... return None`
> - recover-crashed-seats.py:796 `# This branch bypasses the launcher: preserve its task-store migration and binding,`
> - handoff-agent-crash-watcher.py:1215-1218 `if sys.platform != "linux": print(f"{PROGRAM}: refused: this program watches ned-box's agent-seats and runs only on ned-box`
State: open

## E52 — possible problem: an assertion of the overview is contradicted

Claim: `nc-systems/handoff/session-handoff-field-names-common.py` holds the session-handoff's field names, so renaming a field is one edit there.
Found by: the overview claim check of 2026-11-12 against commit 1b6fb19aeab73778f234b7552b2f7dfec1ef2cef; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/c6db3c481b478830a1784c634a6acd8cd1b1e318-2026-11-12T06-25-19-226589Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - Two fields of the session-handoff are named elsewhere: handoff-supervisor.py:380-383 `BACKGROUND_TASK_STARTED_DURING_HANDOFF_DEFERRAL_FIELD_PREFIX = ("background-task-started-during-handoff-deferral-")` and `COLD_READ_FULL_RUN_COMMAND_REFUSED_DURING_HANDOFF_DEFERRAL_FIELD_PREFIX = (...)`.
> - The writer takes them from the supervisor, not from the common module: handoff-write-and-check-supervisor.py:156-159.
> - Renaming them is still one edit, but not in the file this row names.
State: open

## E53 — possible problem: an assertion of the overview is contradicted

Claim: The reference-checkout leftovers-saving back-on-main program saves the leftovers to a branch it pushes, and only then puts the checkout back on main.
Found by: the overview claim check of 2026-11-12 against commit 1b6fb19aeab73778f234b7552b2f7dfec1ef2cef; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/c6db3c481b478830a1784c634a6acd8cd1b1e318-2026-11-12T06-25-19-226589Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - It puts the checkout back on main even when a push failed: handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch.py:27-29 `then runs git switch --no-overwrite-ignore -C main origin/main, ... whether or not every push succeeded`
> - :52-55 `a failed push of a leftovers branch ... still lets the checkout go back on main: the unpushed branch stays in the checkout`
State: open

## E54 — possible problem: an assertion of the overview is contradicted

Claim: The task list is written by Claude Code and on ned-box by the agent-crash-watcher. The writer removes completed tasks after comparing with the log-store copy, which transcript-mirror-to-log-store.py writes.
Found by: the overview claim check of 2026-11-12 against commit 1b6fb19aeab73778f234b7552b2f7dfec1ef2cef; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/c6db3c481b478830a1784c634a6acd8cd1b1e318-2026-11-12T06-25-19-226589Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - Other programs also write task files:
>   - clean-worktrees.py:221-230 `it closes the tasks that uncommitted-work-snapshots.py restore opens, in every task list on the machine ... marks the task completed, adding a line at the end of its description`
>   - uncommitted-work-snapshots.py:34-37 `opens a task naming the branch on the task list ~/.claude/tasks/<CLAUDE_CODE_TASK_LIST_ID>`
> - The writer also writes the log-store copy and the high-water mark itself:
>   - handoff-write-and-check-supervisor.py:52-54 `The writer first copies each completed task it would remove into the log-store`, and :616-632
>   - handoff-write-and-check-supervisor.py:672-690 (writes `.highwatermark`)
State: open

## E55 — possible problem: an assertion of the overview is contradicted

Claim: The reference-checkout is put back on main by the back-on-main program, which pushes any leftovers to a `reference-checkout-leftovers-<date>` branch first.
Found by: the overview claim check of 2026-11-12 against commit 1b6fb19aeab73778f234b7552b2f7dfec1ef2cef; its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/c6db3c481b478830a1784c634a6acd8cd1b1e318-2026-11-12T06-25-19-226589Z.md.
Fixed by: regular maintenance, in the overview.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The switch to main runs even when a push failed: handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch.py:27-29 `whether or not every push succeeded`; :52-55
> - The branch may also be an existing leftovers branch rather than a new dated one: :19-20 `the leftovers branch HEAD is already on, else a new branch reference-checkout-leftovers-<YYYY-MM-DD>`
> - The rest of the row is supported: launch-claude-ubuntu:335, launch-claude-mac:288, handoff-supervisor.py:2381, restart program :19
State: open
