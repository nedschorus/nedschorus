---
issue: "[ned-box runs out of reclaimable memory, so systemd-oomd kills agent-seats and Bash-guard replay readings time out](https://github.com/nedschorus/nedschorus/issues/1834)"
---

# ned-box runs out of reclaimable memory, so systemd-oomd kills agent-seats and Bash-guard replay readings time out

## What is wrong

Five times from 2026-10-17 to 2026-10-22, systemd-oomd, Ubuntu's memory-pressure killer, has killed an agent-seat's whole tmux pane on ned-box, `claude` included. The seat loses whatever it had not yet saved, and the agent-crash-watcher relaunches it. On 2026-10-21 the agent-seat it killed was reboot-test, which was idle at the time.

The first three kills came 30 to 63 seconds after merge-lane-2 started the Bash-guards replay check, `nc-systems/general-tools/bash-guards-verdict-changes-between-two-git-refs-on-transcript-recorded-commands-check.py`. The same load made five of the check's readings run past their 20 s timeout on [Search-file guard's time-limit and error note reuses its plain next-step line](https://github.com/nedschorus/nedschorus/pull/1825). Rerun with a 60 s timeout, each of those readings took 1 s. [Bash-guards replay check reads a timed-out reading once more](https://github.com/nedschorus/nedschorus/pull/1833) adds a retry for such timeouts. This issue is for the cause.

The other two kills, on 2026-10-22 at 02:00:52Z and 10:01:02Z, followed no replay check. Each came within 61 seconds of the hourly snapshot that timeshift, ned-box's system backup, starts at the top of every hour: an rsync of `/`, `/home/nedlern` included, that walks 1.6 million files. In the hour before the first, no agent-seat started heavy work, and systemd-oomd also killed the login screen in another user's slice, so the pressure was machine-wide. Before the second, merge-lane-2 had started a full run of every test suite three minutes earlier. The first kill, on 2026-10-17, also came 44 seconds after a timeshift snapshot started.

The trace, with every measurement and its source, is at nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/reboot-test/ned-box-oomd-kills-trace-2026-10-22/trace.md. In short:

- ned-box has 59.6G of RAM and no swap. `/tmp` is a tmpfs, which keeps its files in RAM. It holds 21G: 12G of agent-session scratchpads, 4.8G in 34 replay-check scratch directories the check left behind, and 3.1G in 562 `run-all-test-suites-*` log directories. Without swap, none of those 21G can be reclaimed, and killing a pane frees none of them.
- Each replay-check run reads 17.5G of transcripts and starts 8 worker processes. It does not go through the free-memory admission that `scripts/run-all-test-suites.py` (class `MachineWideTestSuiteAdmission`) and mutation testing use.
- That admission counts page cache as free memory, and does not count the tmpfs's pages as used.
- systemd-oomd kills the scope with the most reclaimable memory. That is a long-lived agent-seat, not the process that applied the pressure.
- timeshift runs as root from `/etc/cron.d/timeshift-hourly`, in rsync mode, and keeps 24 hourly snapshots; changing it needs root. No step under What to do covers timeshift yet.

## Why it matters

An agent-seat killed this way loses its unsaved work: a subagent's uncommitted changes, a running test or mutation run, messages owed to other agent-seats. Every seat on ned-box is at risk whenever the replay check or timeshift's hourly snapshot runs. The pressure also slows every guard and test running at the same moment, and tests sized to an idle machine then fail; that cause is [Tests that time work against a wall-clock limit sized to an idle machine fail when ned-box is busy](https://github.com/nedschorus/nedschorus/issues/1830).

## What to do

1. The replay check waits for the free-memory admission before it reads any transcript, because the kills came while it was reading them, before its workers started. The build decides how the check takes part in `MachineWideTestSuiteAdmission`, which today admits test suites, and measures which lowers the pressure more: reading the transcripts without leaving them in page cache, or fewer than its 8 workers. Its scratch directory goes on disk, not in `/tmp`, and is removed whenever the check exits; when a verdict changed or a reading failed, the files a reader needs to see why are first copied to the log-store. reboot-test owns the replay-check topic and builds this step first.
2. Large scratch files and logs move from `/tmp` to disk, with pruning: the `run-all-test-suites-*` log directories and mutation-testing worktrees. Agent-session temp folders are done: [ned-box agent-sessions keep Claude Code's temp folders under ~/.cache on the main disk; a daily job deletes those of exited sessions](https://github.com/nedschorus/nedschorus/pull/2010) has `nc-systems/handoff/handoff-supervisor.py` give each agent-session it launches on ned-box `CLAUDE_CODE_TMPDIR=/home/nedlern/.cache/claude-code-tmp`, so Claude Code makes each agent-session's folder, its scratchpad and background-task output, under `/home/nedlern/.cache/claude-code-tmp/claude-1000/` instead of `/tmp/claude-1000/`. Timeshift's hourly snapshot leaves out `/home/nedlern/.cache/**`, so these folders stay out of it. An agent-session started before that change keeps using `/tmp` until it restarts. `nc-systems/general-tools/claude-code-temp-folders-of-exited-agent-sessions-delete.py`, run by cron on ned-box at 07:30 daily, deletes the folders of exited agent-sessions in both places. What remains of this step is the test-suite log directories and the mutation-testing worktrees.
3. The free-memory admission counts the tmpfs's pages (`Shmem` in `/proc/meminfo`) as used.
4. Keep a record of memory over time on ned-box, at an interval short enough to trace the next kill. sysstat already records memory every 10 minutes and keeps 7 days (`OnCalendar=*:00/10` in `sysstat-collect.timer`, `HISTORY=7` in `/etc/sysstat/sysstat`; `/var/log/sysstat` held `sa15` to `sa23` on 2026-10-23, so every kill day has a record). sysstat as it stands does not finish this step: each kill came 45 to 84 seconds after a sample, so the samples show the machine before the pressure and then averaged over the next ten minutes, not the pressure itself, as the trace's sar tables show. What remains is a 1-minute interval. That needs root, so the agent gives the user the command to run.

Next action: reboot-test builds step 1 as one pull request. Steps 2 to 4 each go to the agent-seat that last changed the program involved, as `git log` shows, or to the user for what needs root, and each is tracked in this GHI-MD until it is done.
