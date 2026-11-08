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
