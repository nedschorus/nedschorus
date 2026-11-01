---
issue: "[scripts/launch-claude-ubuntu with --no-attach exits 0 and loses the refusal when the handoff-supervisor refuses to start for a missing GitHub token file](https://github.com/nedschorus/nedschorus/issues/2312)"
---

# scripts/launch-claude-ubuntu with --no-attach exits 0 and loses the refusal when the handoff-supervisor refuses to start for a missing GitHub token file

Filed by merge-lane-2 on 2026-10-31. Codex's review cell raised the defect while reviewing another pull request; a subagent of merge-lane-2 reproduced it on ned-box the same day. Line numbers are on main at `a6bdac066`.

## Reproduction

The launcher's last step, `scripts/launch-claude-ubuntu:477-479`, starts the agent-seat with a `tmux -L "$SEAT_TMUX_SOCKET" new-session -d` command whose pane command is `"$SUPERVISOR_COMMAND; exit \$?"`. `tmux new-session -d` exits 0 as soon as the tmux session exists; it does not wait for the command inside the tmux session. That command runs `nc-systems/handoff/handoff-supervisor.py`, which reads the agent-seat's GitHub token from `~/.config/nedschorus/<account>.token` (`nc-systems/handoff/handoff-supervisor.py:854-876`): `ubuntu-claude.token` for most agent-seats on ned-box, `ned-review-merge.token` for merge-lane-2. When that file is missing, unreadable or empty, the handoff-supervisor prints a refusal to stderr and exits 5 (`nc-systems/handoff/handoff-supervisor.py:2457-2467`, from [PR 2238](https://github.com/nedschorus/nedschorus/pull/2238)). The pane's shell then exits, tmux closes the pane and the tmux session, and the refusal is gone. The launcher has already exited 0.

Reproduced on ned-box with these test doubles: a fake `HOME` that has no `.config` directory; a stub `ssh` that drops its options and host and runs the remote command locally; a stub `claude`; and stubs of the four scripts the launcher's prepare step calls, `agent-binary-update-under-lock.py`, `clean-worktrees.py`, `checkout-freshness-catch-up.py` and `claude-json-agent-seat-folder-trust-and-onboarding-presets-write.py`. The files are in `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/ghi-reproductions/launch-claude-no-attach-token-refusal-2026-10-31/`, written here as `$F`. In a checkout of main on ned-box, first link that checkout's `nc-systems/` into the fake `HOME`, then start the agent-seat `repro978seat`:

```
ln -s "$PWD/nc-systems" $F/home/Projects/nedschorus/nc-systems
HOME=$F/home PATH=$F/bin:$PATH NEDSCHORUS_AGENT_BOX=stubbox scripts/launch-claude-ubuntu repro978seat --no-attach
```

The launcher printed only its prepare-step lines, said nothing about a token, and exited 0. Three seconds later, `tmux -L repro978seat ls` printed `no server running on /tmp/tmux-1000/repro978seat` and exited 1: no agent-seat was running. The handoff-supervisor command run directly, from `$F/home/agents/repro978seat`:

```
HOME=$F/home CLAUDE_CODE_TASK_LIST_ID=nedschorus-repro978seat-tasks python3 $F/home/Projects/nedschorus/nc-systems/handoff/handoff-supervisor.py --agent repro978seat --cd $F/home/agents/repro978seat
```

printed `handoff-supervisor: the agent-seat repro978seat was not started, because the token file .../.config/nedschorus/ubuntu-claude.token of the GitHub account ubuntu-claude, which the agent-seat repro978seat acts as, does not exist.`, with the steps to fix it, and exited 5.

Not affected: `scripts/recover-crashed-seats.py`'s `launch_seat` reads the token file itself before it starts the tmux session (`scripts/recover-crashed-seats.py:714-719`), so its report shows the refusal.

Judged from reading the code, not reproduced:
- `scripts/launch-claude-mac --no-attach` starts the tmux session the same way (`scripts/launch-claude-mac:498`) and has the same defect.
- The handoff-supervisor exits early for other reasons too, before any agent-session starts: exit 3 at `nc-systems/handoff/handoff-supervisor.py:2499` and exit 4 at `:2536`. A `--no-attach` launch loses those refusals the same way.
- Only the `--no-attach` path was examined; whether an attached launch also loses the refusal was not checked.

## Why it matters

The launcher reports success for an agent-seat that never started. The `start-agent-seat` skill starts every new agent-seat on ned-box with `launch-claude-ubuntu <name> --no-attach` (`.claude/skills/start-agent-seat/SKILL.md:18` and `:24`). The caller believes the agent-seat is running; the agent-seat's work stalls until someone notices that no tmux session exists, and the handoff-supervisor's refusal, which names the missing file and the fix, has been thrown away. No data is lost.

## Next action

For reboot-test, the agent-seat that wrote PR 2238: make `scripts/launch-claude-ubuntu --no-attach` and `scripts/launch-claude-mac --no-attach` exit nonzero and print the handoff-supervisor's refusal when the handoff-supervisor exits before starting an agent-session. Choose between two designs:
- Catch every early exit: keep the handoff-supervisor's stderr, for example with tmux's `remain-on-exit` option or by copying stderr to a file, then check a few seconds after `tmux new-session` whether the tmux session still exists, and when it does not, print what the handoff-supervisor printed and exit with its status. This covers the token refusal and exits 3 and 4 alike.
- Catch only the token refusal: before `tmux new-session`, call the handoff-supervisor's own `agent_seat_github_account_lookup_and_token_file_read` and `agent_seat_github_token_unreadable_so_agent_seat_not_started_message_build` through `python3`, as `scripts/recover-crashed-seats.py:714-719` does, so the refusal text has one copy. On ned-box that call runs inside the command the launcher sends over ssh.

Either way, add a test to `scripts/launch-claude-ubuntu-test.py` and to `scripts/launch-claude-mac-test.py` that launches with no token file and expects a nonzero exit and the handoff-supervisor's refusal text in the launcher's output.

## Outcome

Fixed for the missing, unreadable or empty token file by [PR 2321, "launch-claude --no-attach refuses a missing GitHub token file itself (GHI 2312)"](https://github.com/nedschorus/nedschorus/pull/2321), merged to main as `3d2c2bee9`. It took the second design: the handoff-supervisor gained the flag `--agent-seat-github-token-file-readable-check-only` (`nc-systems/handoff/handoff-supervisor.py:2410`), and on `--no-attach` both launchers run the handoff-supervisor with that flag before they create the tmux session (`scripts/launch-claude-ubuntu:477`, inside the command sent to ned-box over ssh; `scripts/launch-claude-mac:501`). When the token file cannot be read, the launch prints the handoff-supervisor's refusal and exits 5, and no tmux session is created. `scripts/launch-claude-ubuntu-test.py` and `scripts/launch-claude-mac-test.py` each run the real handoff-supervisor with no token file and with one present.

Not fixed: a `--no-attach` launch still loses the handoff-supervisor's exits 3 and 4 (`nc-systems/handoff/handoff-supervisor.py:2510` and `:2547` on `3d2c2bee9`). They are left out under CLAUDE.md's rule for guards: neither exit has happened after a `--no-attach` launch, and none is foreseeable, so the first design, which catches every early exit, is built only if one does.
