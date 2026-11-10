# Proposed improvements or changes: nedschorus-handoff-architecture-overview.md (overview claim check, 2026-11-08)

Assertions of the overview that the claim check against commit 31905b3dea48908baf818723090b23b5388cfa49 found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/827a7befcb763718932936563f8664e9bd99ebad-2026-11-08T23-20-02-417909Z.md. Regular maintenance fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: At its first launch: it carries out a waiting session-handoff unless started with `--resume-session-id`; otherwise it starts fresh when an exit is recorded, else resumes the last transcript worth resuming, and stops when it cannot read the transcript folder.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - nc-systems/handoff/handoff-supervisor.py:2440-2443 `if (not settings.resume_session_id and not settings.first_prompt_wins_over_crashed_transcript and ignition_plan is None and agent_exit_record_from_supervisor_state(state) is None):`
> - :2690-2694 `"--first-prompt-file-wins-over-crashed-transcript"` … `"start fresh on --first-prompt-file even when this seat has a crashed transcript worth resuming"`
> - With that flag the handoff-supervisor starts fresh even when there is no exit record. `recover-crashed-seats.py` passes the flag for its conversation-tail start (recover-crashed-seats.py:86), so "else resumes" is incomplete. The rest is supported: :2385-2395 marks a waiting session-handoff consumed under `--resume-session-id`; :2446-2455 stops with exit 5 on an unreadable transcript folder.
State: open

## E2 — possible problem: an assertion of the overview is contradicted

Claim: `clean-worktrees.py`: "a worktree with no owner file, or locked, as Claude Code locks a subagent's worktree while the subagent runs, is kept".
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - scripts/clean-worktrees.py:13-14 `it has no owner file, as agent-homes and worktrees made by hand have, and is not a merge-lane review checkout`
> - :61-68: a worktree with no owner file inside `~/.cache/merge-lane-review-worktrees` is removed once its pull request was merged or closed 24 hours ago.
> - The rest of the row is supported: :33-47 (owner running or stopped, branch for detached commits, work-snapshot of uncommitted files).
State: open

## E3 — possible problem: an assertion of the overview is contradicted

Claim: `<session>-handoff-deferred` "is also read … by scripts/agent-seat-idle-sweep-verdicts-print.py, which spells the suffix itself".
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - scripts/agent-seat-idle-sweep-verdicts-print.py:68-70 `deferred_marker_files = _load("handoff_deferred_marker_and_refused_commands_files_common", …)`; :533 `marker = deferred_marker_files.handoff_deferred_marker_path(`
> - It takes the path from the common module. A grep of that file for the literal `-handoff-deferred` finds only the module's file name.
> - The rest of the row is supported: threshold hook :696-730 and :742-745; due-task hook :711-712; guard hook :192; writer :463; deferred-marker module :35 `"-handoff-deferred-fired"`; post-compaction :109-110.
State: open

## E4 — possible problem: an assertion of the overview is contradicted

Claim: The reference-checkout `~/Projects/nedschorus` is "fast-forwarded to main by launch-claude-ubuntu on ned-box, by launch-claude-mac on the Mac, and, at each session-handoff …, by every handoff-supervisor that runs from it, and by the restart program".
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - scripts/checkout-freshness-catch-up.py:11 `Wired as a Stop hook, so it runs at every turn boundary.`; :61-62 `6. The machine's reference checkout — the main worktree of the same repository, parked on main — gets a fast-forward-only pull on the same rhythm`; .claude/settings.json:73
> - Every agent-session's Stop hook also fast-forwards it at every turn, and that writer is left out.
> - The listed writers are right: launch-claude-mac:288, launch-claude-ubuntu:335, handoff-supervisor.py:2304, restart program :19, back-on-main :16-20.
State: open
