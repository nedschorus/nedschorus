---
issue: "[ned-box runs out of reclaimable memory, so systemd-oomd kills agent-seats and Bash-guard replay readings time out](https://github.com/nedschorus/nedschorus/issues/1834)"
---

# ned-box runs out of reclaimable memory, so systemd-oomd kills agent-seats and Bash-guard replay readings time out

## What is wrong

Three times since 2026-10-17, systemd-oomd, Ubuntu's memory-pressure killer, has killed an agent-seat's whole tmux pane on ned-box, `claude` included. The seat loses whatever it had not yet saved, and the agent-crash-watcher relaunches it. On 2026-10-21 the agent-seat it killed was reboot-test, which was idle at the time.

Each kill came 30 to 63 seconds after merge-lane-2 started the Bash-guards replay check, `nc-systems/general-tools/bash-guards-verdict-changes-between-two-git-refs-on-transcript-recorded-commands-check.py`. The same load made five of the check's readings run past their 20 s timeout on [Search-file guard's time-limit and error note reuses its plain next-step line](https://github.com/nedschorus/nedschorus/pull/1825). Rerun with a 60 s timeout, each of those readings took 1 s. [Bash-guards replay check reads a timed-out reading once more](https://github.com/nedschorus/nedschorus/pull/1833) adds a retry for such timeouts. This issue is for the cause.

The trace, with every measurement and its source, is at nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/reboot-test/ned-box-oomd-kills-trace-2026-10-22/trace.md. In short:

- ned-box has 59.6G of RAM and no swap. `/tmp` is a tmpfs, which keeps its files in RAM. It holds 21G: 12G of agent-session scratchpads, 4.8G in 34 replay-check scratch directories the check left behind, and 3.1G in 562 `run-all-test-suites-*` log directories. Without swap, none of those 21G can be reclaimed, and killing a pane frees none of them.
- Each replay-check run reads 17.5G of transcripts and starts 8 worker processes. It does not go through the free-memory admission that `scripts/run-all-test-suites.py` (class `MachineWideTestSuiteAdmission`) and mutation testing use.
- That admission counts page cache as free memory, and does not count the tmpfs's pages as used.
- systemd-oomd kills the scope with the most reclaimable memory. That is a long-lived agent-seat, not the process that applied the pressure.

## Why it matters

An agent-seat killed this way loses its unsaved work: a subagent's uncommitted changes, a running test or mutation run, messages owed to other agent-seats. Every seat on ned-box is at risk whenever the replay check runs. The pressure also slows every guard and test running at the same moment, and tests sized to an idle machine then fail; that cause is [Tests that time work against a wall-clock limit sized to an idle machine fail when ned-box is busy](https://github.com/nedschorus/nedschorus/issues/1830).

## What to do

1. The replay check waits for the free-memory admission before it reads any transcript, because the kills came while it was reading them, before its workers started. The build decides how the check takes part in `MachineWideTestSuiteAdmission`, which today admits test suites, and measures which lowers the pressure more: reading the transcripts without leaving them in page cache, or fewer than its 8 workers. Its scratch directory goes on disk, not in `/tmp`, and is removed whenever the check exits; when a verdict changed or a reading failed, the files a reader needs to see why are first copied to the log-store. reboot-test owns the replay-check topic and builds this step first.
2. Large scratch files and logs move from `/tmp` to disk, with pruning: the `run-all-test-suites-*` log directories and mutation-testing worktrees. Agent-session scratchpads are placed by Claude Code under `/tmp/claude-1000/`, so moving them needs either a Claude Code setting for the scratchpad's location, or `/tmp` itself on disk instead of a tmpfs, which is a change to ned-box's operating system that the user makes; find whether the setting exists.
3. The free-memory admission counts the tmpfs's pages (`Shmem` in `/proc/meminfo`) as used.
4. Keep a record of memory over time on ned-box, such as sysstat collecting every minute, so the next kill can be traced. No record exists for the days of the kills. Enabling sysstat needs root, so the agent gives the user the command to run.

Next action: reboot-test builds step 1 as one pull request. Steps 2 to 4 each go to the agent-seat that last changed the program involved, as `git log` shows, or to the user for what needs root, and each is tracked in this GHI-MD until it is done.
