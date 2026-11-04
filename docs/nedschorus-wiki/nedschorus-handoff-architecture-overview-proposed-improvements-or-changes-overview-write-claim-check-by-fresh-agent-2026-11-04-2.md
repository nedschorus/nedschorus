# Proposed improvements or changes: nedschorus-handoff-architecture-overview.md (overview claim check, 2026-11-04)

Assertions of the overview that the claim check against commit 6a8ed6b3b82415fa9bc6f5d384ef5d7d8741184e found contradicted or unsupported and ranked fix later: loose, incomplete or badly worded, but no agent would act wrongly on them. Its report is /home/nedlern/nedschorus-logs/overview-write-architecture-overview-claim-check-reports/nedschorus-handoff-architecture-overview/1c7c70e3d77567153a5ab74cb4b7045f17e27e5f-2026-11-04T02-27-57-080850Z.md. A follow-up pull request fixes them in the overview.

## E1 — possible problem: an assertion of the overview is contradicted

Claim: At each session-handoff that launches a successor without consulting the user, the handoff-supervisor first restarts itself on main's code.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The boot path carries out a waiting session-handoff and launches its successor without any restart: handoff-supervisor.py:2199 `if adopted is None and not next_launch_resumes_the_session and settings.handoff_path.is_file():`, through :2237 `session_id = successor_session_id`. The restart call appears only in the wait loop, at :2418–2421.
> - The overview's own Invariants (line 61) say the first launch does this "without restarting itself", so this sentence is too broad. No agent would open a wrong file because of it.
State: open

## E2 — possible problem: an assertion of the overview is contradicted

Claim: The successor's initial-agent-instructions name the conversation-tail, or, when extraction failed, where the outgoing transcript is; they also give the next step, the launch-time-git-sync's result and the spawned-subagent-roster.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - When extraction fails, the prompt has no spawned-subagent-roster. `IgnitionPlanWithoutConversationTail.compose`, handoff-supervisor.py:1118–1128, adds only the next step, the recovery note, the approval-walk instruction, the git-sync report and the reminder lines. The roster is added only in `build_ignition_prompt`, :1040 `roster = spawned_subagent_roster_from(handoff_fields)`.
> - The sentence also leaves out a paragraph every launch carries. handoff-supervisor.py:2329–2332: `worktrees_and_branches = agent_seat_worktrees_and_branches_text(` … `launch_prompt = "\n\n".join(part for part in (prompt, leftover_work_snapshots, worktrees_and_branches) if part)`. That text comes from nc-systems/handoff/agent-seat-worktrees-and-branches-with-no-pull-request-first-prompt-list.py, which the overview never names.
State: open

## E3 — possible problem: an assertion of the overview is contradicted

Claim: When the agent-crash-watcher leaves such an agent-seat down, it shows the user a failed-restart-notice on the Mac, except after an exit the handoff-supervisor recorded as on purpose. It also shows one when a restart fails.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - A waiting dont-restart session-handoff gets no notice. handoff-agent-crash-watcher.py:615 handles only `if verdict == WAITING_HANDOFF_VERDICT:` (defer-to-boot-ignition). The verdict `seat-asked-to-be-consulted` (:124) falls through to :621 `return None`, which is logged as "left alone" at :717.
> - Its docstring, :30–32, lists among stops on purpose "or a dont-restart handoff waiting, verdict seat-asked-to-be-consulted".
> - A recorded exit with code 0 is also silent: :946 `if detail[0] == 0:` / `return True`.
> - No agent would open a wrong file because of this.
State: open

## E4 — possible problem: an assertion of the overview is contradicted

Claim: launch-claude-mac fast-forwards the launcher's own checkout to main.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - launch-claude-mac:280 `python3 "$SCRIPT_DIRECTORY/checkout-freshness-catch-up.py" --reference-pull --repo "$REPOSITORY"`
> - That mode updates the clone's main worktree, not the checkout it is given. scripts/checkout-freshness-catch-up.py:1727 `reference = reference_checkout_of(root)`; :1550 `"""The main worktree of the same repository — the machine's reference copy.`; :1554 `return Path(records[0].path) if records else None`.
> - When the launcher runs from a linked worktree, that worktree is not fast-forwarded. The launcher's own comment, :275–276, says "fast-forward the machine's reference checkout".
State: open

## E5 — possible problem: an assertion of the overview is contradicted

Claim: Both launchers run checkout-freshness-catch-up.py to fast-forward the checkout they run the handoff-supervisor from.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - launch-claude-mac runs the handoff-supervisor from `$REPOSITORY_ROOT` (launch-claude-mac:91). But `--reference-pull` fast-forwards the clone's main worktree: checkout-freshness-catch-up.py:1727 `reference = reference_checkout_of(root)` and :1554 `return Path(records[0].path)`.
> - When launch-claude-mac is run from a linked worktree, those two checkouts differ. For launch-claude-ubuntu they are the same (`~/Projects/nedschorus`).
State: open

## E6 — possible problem: an assertion of the overview is contradicted

Claim: At a session-handoff the handoff-supervisor removes the worktrees under the agent-home's `.claude/worktrees/` that clean-worktrees.py judges finished.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The cleaner is run on the whole clone, with no path restriction: handoff-supervisor.py:1535–1536 `[sys.executable, "-u", str(CLEAN_WORKTREES_PATH), "--remove", "--repo", str(working_directory)],`
> - clean-worktrees.py:4–5 `Every worktree of the clone except its main checkout, the reference-checkout, wherever the worktree is.`
> - The overview's own clean-worktrees bullet (line 49) says "wherever it is". The cleaner's owner-file and pull-request guards keep the narrower reading from losing work.
State: open

## E7 — possible problem: an assertion of the overview is contradicted

Claim: At its first launch with a session-handoff waiting, the handoff-supervisor does the same from the question to the user on, without restarting itself.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The boot path never removes finished worktrees. It runs from handoff-supervisor.py:2199 `if adopted is None and not next_launch_resumes_the_session and settings.handoff_path.is_file():` to :2237 and calls only the question, `carry_over_to_successor` and the no-tail fallback.
> - A search for `remove_finished_worktrees_at_handoff\(` in handoff-supervisor.py found one call, :2414, inside the wait loop.
> - So a successor started by boot-ignition, after resupervise-seat.py or recover-crashed-seats.py, gets no worktree cleanup.
State: open

## E8 — possible problem: an assertion of the overview is contradicted

Claim: A handoff-supervisor that outlives its agent-session records the exit before it exits.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - One path exits without a record after the session died. After a death the supervisor decides to resume (handoff-supervisor.py:2378 `next_launch_resumes_the_session = True`, :2379 `continue`).
> - At the top of the loop it clears the record and writes the state: :2276 `clear_agent_exit_record_from_supervisor_state(state)`, :2277 `write_supervisor_state(settings.state_path, state)`.
> - If the transcript then cannot be read, it returns with no record: :2317–2320 `except OSError as error:` … `return 5`. Compare :2354, which records the exit on the same failure in the death branch.
> - This is a rare edge case, and its message names recover-crashed-seats.py.
State: open

## E9 — possible problem: an assertion of the overview is contradicted

Claim: `refs/work-snapshots/` is written by uncommitted-work-snapshot-hook.py, listed by handoff-supervisor.py, and deleted by the hook, clean-worktrees.py or the restoring agent.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - clean-worktrees.py also writes work-snapshots. clean-worktrees.py:39–41 `its uncommitted and untracked files go to a work-snapshot (nc-systems/handoff/uncommitted-work-snapshots.py) owned by this invocation's own process`.
> - The row names clean-worktrees.py only as a deleter, although the overview's own clean-worktrees bullet (line 49) says it copies files to a work-snapshot. The rest of the row holds: uncommitted-work-snapshots.py:703 `run_git(repo, "update-ref", "-d", ref, snapshot["commit"])`; :579 `4. Delete the ref: git update-ref -d <ref>`.
State: open

## E10 — possible problem: an assertion of the overview is contradicted

Claim: The reference-checkout, `~/Projects/nedschorus`, is fast-forwarded to main by launch-claude-ubuntu, by launch-claude-mac when run from it, and by every handoff-supervisor that runs from it, at each handoff that launches a successor without consulting the user.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - launch-claude-mac fast-forwards the clone's main worktree, the reference-checkout, whichever checkout of the clone it runs from, not only "when run from it".
>   - launch-claude-mac:280 `--reference-pull --repo "$REPOSITORY"`
>   - checkout-freshness-catch-up.py:1727 `reference = reference_checkout_of(root)`
>   - checkout-freshness-catch-up.py:1550 `"""The main worktree of the same repository — the machine's reference copy.`
> - The other two writers hold: launch-claude-ubuntu:327 and handoff-supervisor.py:2102.
State: open

## E11 — possible problem: an assertion of the overview is contradicted

Claim: `GH_TOKEN` is set by handoff-supervisor.py for every agent-session. A caller's value is unset by launch-claude-mac, and dropped by recover-crashed-seats.py and resupervise-seat.py from the environment they start a launcher or tmux server with.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - resupervise-seat.py drops it only on the Mac path, :527 `environment = supervisor.agent_seat_launch_environment_without_calling_agent_session_tmux_and_supervisor_variables(os.environ)`.
> - For `--machine ubuntu` it starts launch-claude-ubuntu with the caller's whole environment, GH_TOKEN included: :370 `environment = {**os.environ, "NEDSCHORUS_AGENT_BOX": arguments.agent_box}` and :374 `os.execve(str(launcher), [str(launcher), arguments.name], environment)`.
> - The rest holds: handoff-supervisor.py:2546; launch-claude-mac:427 `unset GH_TOKEN`; handoff-supervisor.py:306 `caller_only = {"TMUX", "TMUX_PANE", "IS_DEMO", "GH_TOKEN",`; recover-crashed-seats.py:781.
State: open

## E12 — possible problem: an assertion of the overview is contradicted

Claim: Entry points: recover-crashed-seats.py is started by a person, restart-live-seats-at-login.py, or, on ned-box, the agent-crash-watcher.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The restart program also runs it. nc-systems/handoff/handoff-supervisor-restart-onto-main-code-by-relaunch-from-reference-checkout.py:40 `- step 6: runs scripts/recover-crashed-seats.py <seat> from the reference-checkout,`
> - The overview never names that program as a component.
State: open

## E13 — possible problem: an assertion of the overview is contradicted

Claim: Entry points: clean-worktrees.py runs from the `clean-worktrees` job, and from the handoff-supervisor at each session-handoff that launches a successor. The launchers run it only to report.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - A successor launched by boot-ignition from a waiting session-handoff gets no clean-worktrees run. The only call is handoff-supervisor.py:2414, in the wait loop; the boot path, :2199–2237, has none.
> - The rest holds: scheduled-jobs-on-each-machine.json:61; launch-claude-mac:271 `python3 "$SCRIPT_DIRECTORY/clean-worktrees.py" --only-done \`; launch-claude-ubuntu:316.
State: open

## E14 — possible problem: an assertion of the overview is contradicted

Claim: Entry points: resupervise-seat.py and the install scripts are started by a person. The `list` command of uncommitted-work-snapshots.py is run by a person, or an agent its initial-agent-instructions send there.
Goes wrong when: a reader takes the assertion as exact.
The claim check's evidence:
> - The restart program also runs resupervise-seat.py: handoff-supervisor-restart-onto-main-code-by-relaunch-from-reference-checkout.py:37 `- step 5: runs scripts/resupervise-seat.py <seat> --prepare-only from the reference-checkout,`
> - The `list` half holds: uncommitted-work-snapshots.py:568 `return f"python3 {MODULE_PATH} list --agent-seat {agent_seat}"`, used in first_prompt_text at :632 and :639.
State: open
