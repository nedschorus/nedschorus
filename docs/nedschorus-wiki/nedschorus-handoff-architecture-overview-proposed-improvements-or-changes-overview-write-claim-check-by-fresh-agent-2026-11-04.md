# Proposed improvements or changes: nedschorus-handoff-architecture-overview.md (overview claim check, 2026-11-04)

Assertions of the overview that the claim check against commit 6a8ed6b3b82415fa9bc6f5d384ef5d7d8741184e found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/26a7ee88e8ad1032ec8c5e6371d2d03e0a687ebb-2026-11-04T02-13-06-891647Z.md. A follow-up pull request fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: The successor's initial-agent-instructions name the conversation-tail, or, when the extraction failed, where the outgoing agent-session's transcript is, and also the next step, the launch-time-git-sync's result and the spawned-subagent-roster (plus the Mac memory review and the agent-instructions-editor overview refresh reminder).
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - When the extraction fails, the prompt is built by `IgnitionPlanWithoutConversationTail.compose`, `nc-systems/handoff/handoff-supervisor.py:1089-1128`. It adds the next step, the recovery note, the approval-walk instruction, the git-sync report, the overview-refresh lines and the memory-review lines, and no roster. Only `build_ignition_prompt` adds `ORPHANED_SUBAGENT_ROSTER_SENTENCE_TEMPLATE` (line 1045).
> - The sentence also leaves out the agent-seat's worktrees and branches with no pull request, which every launch adds: `nc-systems/handoff/handoff-supervisor.py:2329-2332` `worktrees_and_branches = agent_seat_worktrees_and_branches_text(...)`. The program that builds that list, `nc-systems/handoff/agent-seat-worktrees-and-branches-with-no-pull-request-first-prompt-list.py`, is not listed under Components.
> - The rest is borne out: lines 2291-2300 (overview refresh only `if settings.agent == AGENT_SEAT_GIVEN_OVERVIEW_REFRESH_LINES`), and 1461-1462 (memory review `if mark_module.this_machine_is_ned_box(): return ()`).
> - Rank: incomplete. No agent would act wrongly on it.
State: open

## E2 — possible problem: an assertion of the overview is contradicted

Claim: The agent-crash-watcher never restarts an agent-seat whose session-handoff waits or whose exit was recorded. When it leaves such an agent-seat down, other than after an exit the handoff-supervisor recorded as on purpose, or when a restart fails, it shows the user a failed-restart-notice.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - A waiting dont-restart session-handoff is also left down with no notice. `nc-systems/handoff/handoff-agent-crash-watcher.py:30-32` "leaves every other agent-seat alone: a stop on purpose (a clean exit, an exit its supervisor recorded as a stop at a dont-restart handoff, or a dont-restart handoff waiting, verdict seat-asked-to-be-consulted)".
> - `down_kind` at lines 615-621 returns `"for-the-user"` only for `WAITING_HANDOFF_VERDICT = "defer-to-boot-ignition"` (line 120), and None for `seat-asked-to-be-consulted`.
> - The rest is borne out: once a minute on ned-box, seen running since boot, `recover-crashed-seats.py`'s assessment (lines 14-17, 983-984), and `RESTART_LIMIT_SECONDS = 3600` (line 129).
> - Rank: one silent case is left out. No agent would act wrongly on it.
State: open

## E3 — possible problem: an assertion of the overview is contradicted

Claim: `scripts/launch-claude-mac` "fast-forwards the launcher's own checkout to main" and runs the handoff-supervisor from that checkout.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - `scripts/launch-claude-mac:280` `python3 "$SCRIPT_DIRECTORY/checkout-freshness-catch-up.py" --reference-pull --repo "$REPOSITORY"`
> - `scripts/checkout-freshness-catch-up.py:1704` `help="only fast-forward the reference checkout of --repo"`
> - `scripts/checkout-freshness-catch-up.py:1727-1729` `reference = reference_checkout_of(root) ... fast_forward_reference_checkout(reference, ...)`
> - `scripts/checkout-freshness-catch-up.py:1550` "The main worktree of the same repository — the machine's reference copy."
> - So when the launcher runs from a linked worktree, the clone's main checkout is fast-forwarded, not the launcher's own checkout.
> - The rest is borne out: agent-home and branch created at 251-256, update at 228-230, own tmux server at 292/490, task list and git identity at 393-395, token check before a detached start at 500-502 under `set -eu`.
> - Rank: wrong only for a launch from a linked worktree. Nothing an agent does depends on it.
State: open

## E4 — possible problem: an assertion of the overview is contradicted

Claim: `scripts/checkout-freshness-catch-up.py` — "both launchers run it to fast-forward the checkout they run the handoff-supervisor from".
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - `scripts/checkout-freshness-catch-up.py:1704` "only fast-forward the reference checkout of --repo"
> - `scripts/checkout-freshness-catch-up.py:1727` `reference = reference_checkout_of(root)`
> - `scripts/launch-claude-mac:396` runs the supervisor from `$REPOSITORY`, the launcher's own checkout, which may be a linked worktree that is not the one fast-forwarded.
> - The rest is borne out: it is a hook outside this system (`.claude/settings.json:66-67`), and the launch-time-git-sync uses `uncommitted_tracked_change_count` and `in_progress_marker` (`nc-systems/handoff/handoff-supervisor.py:1224, 1239`).
> - Rank: same edge case as 22.
State: open

## E5 — possible problem: an assertion of the overview is contradicted

Claim: At a session-handoff the handoff-supervisor "removes the worktrees under the agent-home's `.claude/worktrees/` that `scripts/clean-worktrees.py` judges finished". Also: "At its first launch with a session-handoff waiting it does the same from the question to the user on, without restarting itself."
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The supervisor runs `clean-worktrees.py --remove --repo <agent-home>` (`nc-systems/handoff/handoff-supervisor.py:1535-1536`). clean-worktrees then judges "Every worktree of the clone except its main checkout ... wherever the worktree is" (`scripts/clean-worktrees.py:4-5`, `357` `git worktree list`), not only those under the agent-home.
> - The first-launch path at `nc-systems/handoff/handoff-supervisor.py:2199-2237` asks the question and runs `carry_over_to_successor`, but never calls `remove_finished_worktrees_at_handoff`. The only call is at line 2414, in the loop.
> - The rest is borne out: lines 2395-2411 (end session, ask, no terminal counts as no, record exit) and 2418-2419 (no restart for dont-restart).
> - Rank: wrong scope and a step that does not happen, but nothing an agent does hinges on either.
State: open

## E6 — possible problem: an assertion of the overview is contradicted

Claim: "A handoff-supervisor that outlives its agent-session records the exit before it exits"; the only exceptions named are a restarted supervisor that cannot start for want of its token or lock, and an unhandled error.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - After a death, the supervisor chooses to resume (`nc-systems/handoff/handoff-supervisor.py:2377-2379` `continue`). The loop then clears the exit record and writes the state (2276-2277). If the transcript cannot be read at 2313-2320, it returns 5 with no exit record: `except OSError as error: print(transcript_unreadable_stop_message(...)); return 5`. That is a handled exit without a record, after the agent-session died, which the invariant's exception list leaves out.
> - The main paths are borne out: 2380 and 2408-2410 record the exit; 2354-2355 records it before return 5 in the post-death branch.
> - Rank: a rare edge case. The printed message tells the user to run recovery.
State: open

## E7 — possible problem: an assertion of the overview is contradicted

Claim: The reference-checkout `~/Projects/nedschorus` is fast-forwarded by `launch-claude-ubuntu`, by `launch-claude-mac` "when run from it", and by every supervisor that runs from it at each non-consulting handoff.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - `scripts/launch-claude-mac:280` runs `--reference-pull --repo "$REPOSITORY"`, and `scripts/checkout-freshness-catch-up.py:1727-1729` fast-forwards `reference_checkout_of(root)`, the clone's main worktree. So `launch-claude-mac` fast-forwards the reference-checkout whichever checkout of the clone it runs from, not only when it runs from that checkout.
> - The other two writers are borne out: `scripts/launch-claude-ubuntu:327` and `nc-systems/handoff/handoff-supervisor.py:2102`.
> - Rank: the qualifier understates who writes the checkout. No agent would act wrongly on it.
State: open

## E8 — possible problem: an assertion of the overview is contradicted

Claim: `GH_TOKEN` — "a caller's value is kept out of the agent-seat's tmux server, unset by `launch-claude-mac` and dropped by `recover-crashed-seats.py` and `resupervise-seat.py` from the environment they start a launcher or tmux server with".
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - `scripts/resupervise-seat.py:370` `environment = {**os.environ, "NEDSCHORUS_AGENT_BOX": arguments.agent_box}`, then line 374 `os.execve(str(launcher), [str(launcher), arguments.name], environment)` runs `launch-claude-ubuntu` with the caller's `GH_TOKEN` still set. Only the Mac path (line 527) uses `agent_seat_launch_environment_without_calling_agent_session_tmux_and_supervisor_variables`, which drops it (`nc-systems/handoff/handoff-supervisor.py:306`).
> - The rest is borne out: `scripts/launch-claude-mac:427` `unset GH_TOKEN`, `scripts/recover-crashed-seats.py:781`, and `nc-systems/handoff/handoff-supervisor.py:2546`.
> - Rank: over ssh the variable does not reach the ned-box tmux server, so the effect holds even though the sentence is wrong for that path.
State: open
