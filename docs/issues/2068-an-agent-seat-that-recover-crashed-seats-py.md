---
issue: "[An agent-seat that recover-crashed-seats.py launches starts its tmux server in the caller's directory, so the calling agent-seat can no longer be recovered](https://github.com/nedschorus/nedschorus/issues/2068)"
---

# An agent-seat that recover-crashed-seats.py launches starts its tmux server in the caller's directory, so the calling agent-seat can no longer be recovered

When `scripts/recover-crashed-seats.py` launches an agent-seat, the agent-seat's own tmux server keeps the working directory of whoever ran the program. When an agent-seat runs the program from its own agent-home, every agent-seat it launches leaves a tmux server rooted in that directory. The program's occupancy check then counts those servers as a running process of the calling agent-seat, so a later `recover-crashed-seats.py <calling seat>` refuses, and the calling agent-seat's directory cannot be cleared without killing the other agent-seats. Crash recovery of the calling agent-seat is lost until each of those agent-seats' tmux servers is restarted.

## Reproduction

On 2026-10-28 (UTC) on ned-box, during the handoff-supervisor restart run whose steps file is `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/ned-box-helper/handoff-supervisor-restart-steps-2026-10-28.md`, ned-box-helper restarted seven agent-seats by running `scripts/recover-crashed-seats.py <seat>` from its own agent-home. The steps file says the operator, the agent-seat that runs the restart steps for another agent-seat, runs the scripts "from its own directory"; for those seven restarts the operator was ned-box-helper, so its working directory was `/home/nedlern/agents/ned-box-helper`.

Each launched agent-seat's tmux server, started as `tmux -L <seat> new-session -d -s <seat> -c /home/nedlern/agents/<seat> ...`, kept the launcher's working directory, `/home/nedlern/agents/ned-box-helper`. The `-c` option sets only the new pane's directory, not the server's.

merge-lane-2 then acted as the operator for the restart of ned-box-helper itself, and ran step 6, the recovery. `recover-crashed-seats.py ned-box-helper` printed `ned-box-helper: REFUSED — a live process is rooted in /home/nedlern/agents/ned-box-helper` and exited 1. `lsof -a -d cwd +D /home/nedlern/agents/ned-box-helper` listed the tmux servers of seven other agent-seats: prime-intellect (process 18953), reboot-test (57832), merge-lane-2 (90028), agent-instructions-editor (4068808), cold-read-improvement (4083974), fleet-restart-at-login (4139791) and MD-skills (4181561). Ending those processes would have taken those agent-seats down.

The full log is `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/ned-box-helper-restart-steps-4-to-7-2026-10-28.log`. merge-lane-2 recovered ned-box-helper with a one-off wrapper that excuses only those seven process ids, `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/recover-ned-box-helper-excusing-other-seats-tmux-servers.py`, run from `/home/nedlern`; ned-box-helper's new tmux server has `/home/nedlern` as its working directory.

The seven servers are still rooted in `/home/nedlern/agents/ned-box-helper`, so ned-box-helper's next crash recovery will refuse the same way until each of those agent-seats' tmux servers is restarted.

## Cause

`launch_seat` in `scripts/recover-crashed-seats.py` has two branches.

- Off macOS, it calls `run_tmux("new-session", "-d", "-s", name, "-c", str(seat_directory), ...)`, and `run_tmux` runs `subprocess.run(["tmux", ...])` with no `cwd=`. The tmux server it starts therefore inherits the program's own working directory.
- On macOS, it runs `scripts/launch-claude-mac <name> --no-attach`. Read on main: that script runs `tmux -L "$SEAT_TMUX_SOCKET" new-session -d -s "$AGENT_NAME" -c "$AGENT_DIRECTORY" ...` with no `cd` before it, so it has the same behaviour on the Mac.

`scripts/launch-claude-ubuntu` is not one of these branches: it is the Mac-side wrapper, and it starts the agent-seat's tmux server through an `ssh` command to ned-box, whose box-side shell has no `cd` before `tmux ... new-session`, so that server starts in the ssh login's directory, `$HOME` by default, not in an agent-home; it needs no change.

The occupancy check, `seat_directory_occupied` with `processes_rooted_in_seat_directory`, counts every process whose working directory is in the agent-home, so it cannot tell another agent-seat's tmux server from a running agent-session of the agent-seat being recovered.

The launch lines were written by identity-probe in commit bce3b9d0c (2026-08-22, GHI [#120](https://github.com/nedschorus/nedschorus/issues/120)); that agent-seat may be retired. They were last changed by fleet-restart-at-login in commit 7b3eda1d6 (2026-10-11).

Related, closed: GHI [#659](https://github.com/nedschorus/nedschorus/issues/659), where the recovered agent-seat's supervisor ran from the checkout the recovery was run from; it is the same family, a launch that keeps something of its caller.

## Next action

The agent-seat that last changed the launch lines, fleet-restart-at-login, decides the fix; when it is retired, the user names who does. Two directions, which can be combined:

- Start the agent-seat's tmux server in `$HOME`, a directory that is no agent-seat's agent-home: in `scripts/recover-crashed-seats.py` by passing `cwd=` to the `subprocess.run` call in `run_tmux`, and in `scripts/launch-claude-mac` by running the `tmux ... new-session` command from `$HOME`, for example in a `cd "$HOME"` subshell. The launched agent-seat's own agent-home is not a safe choice: its tmux server would then count as occupying its own agent-home whenever it outlives the agent-session, for example after a crash that leaves an after-exit shell.
- Make the occupancy check ignore a process that is another agent-seat's tmux server. The fix must then say how the check recognizes one, for example by the server's socket name under `tmux -L <agent-seat name>`, since an unrelated tmux server would look the same in the `lsof` listing.

The fix gets a test that launches an agent-seat from a second agent-seat's directory and shows that the second agent-seat's recovery is not refused. Until each of the seven agent-seats named above has its tmux server restarted, which happens at its next restart once the fix is merged, a recovery of ned-box-helper refuses again; the operator of that recovery then excuses those servers' process ids, as merge-lane-2's one-off wrapper above did, rather than ending them, because ending them takes those agent-seats down. `scripts/recover-crashed-seats.py` itself has no option to excuse a process.
