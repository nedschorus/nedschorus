# Proposed improvements or changes: nedschorus-handoff-architecture-overview.md (overview claim check, 2026-11-05)

Assertions of the overview that the claim check against commit d08dc058fd63a331f346678ce36f067e533aa856 found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/4f1e208f47643e513f48ee18957408dc1df2de05-2026-11-05T22-27-21-827479Z.md. Regular maintenance fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: `scripts/clean-worktrees.py`: before a removal it copies the worktree's review records to the log-store.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - What it ships is more than review records: clean-worktrees.py:45-50 `Before --remove removes one, it ships each walk in the worktree's docs/walk/, one for each <name>-minutes.md there, with scripts/walk-files-ship.py ... and each non-empty record directory under its cold-read-records/ and sanity-check-records/`.
> - It also keeps the worktree when a shipment fails (:51-52). "Review records" leaves out the approval-walk files. Loose wording; no agent would act wrongly.
State: open

## E2 — possible problem: an assertion of the overview is contradicted

Claim: Invariant: a supervisor restarted on main's code that cannot start, for want of the token or its lock, or one that fails with an error it does not handle, exits without a record, leaving any session-handoff waiting; so does one that cannot read the transcript of the agent-session it is about to resume.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The two reasons named are not the only startup exits without a record. The restarted process can also return early at handoff-supervisor.py:2752-2754 `if shutil.which(arguments.agent_command) is None: print(f"handoff-supervisor: no such command: ..."); return 3`, and at :2750-2751 `parser.error(f"--cd is not a directory: ...")`.
> - Both are handled errors that leave no exit record and the session-handoff waiting. The sentence reads as a full list of causes.
State: open

## E3 — possible problem: an assertion of the overview is contradicted

Claim: `<session>-handoff-asked` and `<session>-handoff-deferred`: written by the threshold hook and read by it and by `scripts/agent-seat-due-task-raise-hook.py`. The first is deleted by the post-compaction hook; the second outlasts a compaction and is deleted by the threshold hook when it asks for the handoff.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The writers, the deletions and the due-task hook read hold: handoff-context-threshold-hook.py:565, 585, 597; agent-seat-due-task-raise-hook.py:708-709 `if (handoff.fired_marker_path(session_id).exists() or handoff.deferred_marker_path(session_id).exists()):`; post-compaction-session-continues-hook.py:110 `marker.unlink()`.
> - The reader list leaves one out: scripts/agent-seat-idle-sweep-verdicts-print.py:82 `HANDOFF_DEFERRED_SUFFIX = "-handoff-deferred"` and :531 `marker = paths.handoff_directory / f"{session_id}{HANDOFF_DEFERRED_SUFFIX}"`.
> - The idle sweep keeps its own copy of the suffix, so renaming the marker from this list alone would break it.
State: open

## E4 — possible problem: an assertion of the overview is contradicted

Claim: `<seat>-leftovers-prompt-listing-counts.json`: written and read by the supervisor at each launch, keeping only the entries listed that time.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - handoff-supervisor.py:1625-1627 `leftovers = "\n\n".join(part for part in leftover_parts if part)` / `if not leftovers: return prompt`.
> - That return comes before `leftovers_with_prompt_listing_counts` (:1629), so a launch with no leftovers neither reads nor rewrites the file.
> - Earlier entries stay, and :1609 `counts = {key: earlier.get(key, 0) + 1 ...}` counts on from them at the next launch that lists that entry. The file is not touched at every launch and does not always hold only the last launch's entries.
State: open

## E5 — possible problem: an assertion of the overview is contradicted

Claim: The reference-checkout, `~/Projects/nedschorus` on each machine: fast-forwarded to main by `launch-claude-ubuntu` on ned-box, by `launch-claude-mac` on the Mac, at each non-consulting handoff by every supervisor running from it, and by the restart program; put back on main by the leftovers program.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - A writer is missing: the Stop hook checkout-freshness-catch-up.py also fast-forwards the reference-checkout at each turn end.
> - checkout-freshness-catch-up.py:1779-1782 `reference = reference_checkout_of(root)` / `fast_forward_reference_checkout(reference, arguments.interval_seconds, operator_facing=False)`, and :1573 `This function runs at every turn end`. It is registered at .claude/settings.json:72.
> - So the checkout can move under a running supervisor between handoffs.
> - The listed writers hold: launch-claude-ubuntu:327, launch-claude-mac:280, handoff-supervisor.py:2273, the restart program :19, the leftovers program :20.
State: open

## E6 — possible problem: an assertion of the overview is contradicted

Claim: `NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER`: set by `scripts/ghi-guide-agent-ask.py` for the `claude` it starts; silences `handoff-context-threshold-hook.py`; removed by the supervisor from every agent-session it starts.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The setter, the threshold-hook read and the removal hold: ghi-guide-agent-ask.py:575; handoff-context-threshold-hook.py:513-514 `if os.environ.get(REINCARNATION_OWNED_BY_CALLER_VARIABLE): return 0`; handoff-supervisor.py:325.
> - It silences more hooks than the threshold hook: agent-seat-due-task-raise-hook.py:754 `if environment.get(REINCARNATION_OWNED_BY_CALLER_VARIABLE):`, absence-claim-locator-reminder-hook.py:460, cold-read-fast-read-due-for-linked-document-reminder-hook.py:509, ned-box-path-in-agent-reply-unclickable-on-mac-warning-hook.py:268, and nc-systems/general-tools/shell-command-tree-sitter-bash-reader-common.py:474.
> - An agent renaming or changing the variable from this entry alone would miss them.
State: open

## E7 — possible problem: an assertion of the overview is unsupported

Claim: Entry: the install scripts are run by a person. The `list` command of `uncommitted-work-snapshots.py` is run by a person, or an agent its initial-agent-instructions send there. The `write` and `show` commands of `worktree-owner-file-read-and-write.py` are run by a person or a program that makes a worktree.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The install scripts and the `list` command are borne out: uncommitted-work-snapshots.py:639 and :631 hand the agent `list_command_text(agent_seat)`.
> - No program in the repository runs the owner-file module's `write` or `show` command.
> - Search `worktree-owner-file-read-and-write` in non-test files finds only the module itself, uncommitted-work-snapshot-hook.py (which calls the function worktree_owner_file_write at :132, not the command), clean-worktrees.py, the weekly owner check, the first-prompt list and the overview.
> - Search `owner-file-read-and-write\.py (write|show)|worktree_owner_file_write` in *.md finds nothing.
> - The launchers' `git worktree add` (launch-claude-mac:253, launch-claude-ubuntu:308) writes no owner file. The module's docstring :25-26 describes the intended writer, but none exists.
> - Files read: worktree-owner-file-read-and-write.py, uncommitted-work-snapshot-hook.py, clean-worktrees.py, both launchers.
State: open
