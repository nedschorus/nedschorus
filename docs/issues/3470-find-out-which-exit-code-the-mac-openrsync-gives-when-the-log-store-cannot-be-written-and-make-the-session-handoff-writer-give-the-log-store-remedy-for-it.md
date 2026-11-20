---
issue: "[Find out which exit code the Mac's openrsync gives when the log-store cannot be written, and make the session-handoff writer give the log-store remedy for it](https://github.com/nedschorus/nedschorus/issues/3470)"
---

# Find out which exit code the Mac's openrsync gives when the log-store cannot be written, and make the session-handoff writer give the log-store remedy for it

## What happens

`nc-systems/handoff/handoff-write-and-check-supervisor.py` copies completed task files to the log-store on ned-box with rsync, in the function `copy_task_files_to_log_store`. When rsync fails over ssh, that function picks what the agent is told from rsync's exit code. An exit code in `RSYNC_EXITS_AFTER_CONNECTING`, which is `(3, 11, 23)`, means ssh connected but the log-store side could not be written, so it raises `LogStoreCopyFailedOnLogStoreSide`, whose message tells the agent to check the log-store on ned-box; this issue calls that message the log-store remedy. Any other exit code raises `LogStoreUnreachable`, whose message says "Check that ned-box is up and that `ssh <host> true` works"; this issue calls that the ssh remedy. When rsync copies to a local folder instead, any failure raises `RuntimeError`, with the exit code in its message.

On the Mac, `rsync` is openrsync (`rsync --version` prints "openrsync: protocol version 29"), not rsync 3. Where rsync 3 exits 23 for a store it cannot write, openrsync exits 1. Three cases of `nc-systems/handoff/tests/handoff-write-and-check-supervisor-test.py` fail on the Mac because of that, and pass on ned-box. Run on the Mac on 2026-11-13, at origin/main 70992bcc, they printed:

- "a copy to the log-store that fails keeps every completed task, names rsync's exit, and still writes the handoff", the fixture `store-folder-unwritable`: rsync copies to a local folder, and the case expects "exited 23" in the `RuntimeError` message, which says "exited 1".
- "over ssh, an rsync that cannot write the store keeps every completed task" and "over ssh, an rsync that cannot write the store gets the log-store remedy, not the ssh remedy", both the fixture `remote-store-unwritable`: rsync goes through the test's ssh stand-in, `RUN_REMOTE_COMMAND_HERE_SSH_STUB`, exits 1, and the supervisor gives the ssh remedy instead of the log-store remedy.

PR [Mac-only nc-test-suite failures fixed: moved HOME hides user site-packages, Linux-only launcher, /home resolution, agents root, git wording, BSD pgrep](https://github.com/nedschorus/nedschorus/pull/3461) fixed the Mac's other failing suites and left this one failing, with a `#root_cause_not_fixed` line that names this issue.

## Why the cause is not yet known

The test's ssh stand-in runs the receiving rsync on the Mac too, so the test pairs openrsync with openrsync. In production, openrsync on the Mac sends to rsync 3.4.1 on ned-box (unverified: the version is as PR 3461's description states it). Which exit code that pair gives for a store it cannot write has not been measured, because measuring it means making, on ned-box, a directory that rsync cannot write. So it is not known whether the Mac has a real defect, where an agent on the Mac whose log-store copy fails is told to fix ssh while ssh works, or whether only the test is wrong.

## What to do next

1. Measure the pair. On ned-box, make a scratch directory with `mktemp -d` under `/tmp` and `chmod 0555` it. From the Mac, run the command `transcript_mirror.rsync_command(host, source, target, files_on_stdin=True)` builds, where `transcript_mirror` is `scripts/transcript-mirror-to-log-store.py` as the supervisor loads it, with ned-box as the host and that directory as the target, giving it on standard input the names of one or more files in the source folder, one per line, as `copy_task_files_to_log_store` does. Record the exit code, stderr, and `rsync --version` on both machines. Then `chmod 0755` the directory and remove it. Also record the exit code the same command gives when the host cannot be reached, for example a host name that does not resolve.
2. If the pair exits 23, the supervisor is right in production and only the test is wrong: make the two ssh cases' stand-in give the code the real pair gives, so they pass on the Mac.
3. If the pair exits a code outside `RSYNC_EXITS_AFTER_CONNECTING` that an unreachable host does not also give, such as 1, the defect is real: make the supervisor give the log-store remedy for that code, and make the test reproduce the measured pair.
4. If the pair exits a code an unreachable host also gives, the exit code cannot tell the two failures apart. Then the supervisor needs another way to choose the remedy, for example running `ssh <host> true` after rsync fails and giving the ssh remedy only when that fails too.
5. In every case, fix the local case: its expected "exited 23" is what rsync 3 prints, so it must accept the code the local rsync gives on each machine. The suite `nc-systems/handoff/tests/handoff-write-and-check-supervisor-test.py` must pass on the Mac and on ned-box when this issue closes.
