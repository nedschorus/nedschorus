---
issue: "[`scripts/run-all-test-suites.py` does not kill a killed suite's descendant whose parent exited before the kill, and removes the suite's TMPDIR while that descendant runs](https://github.com/nedschorus/nedschorus/issues/3144)"
---

# `scripts/run-all-test-suites.py` does not kill a killed suite's descendant whose parent exited before the kill, and removes the suite's TMPDIR while that descendant runs

## Reproduction

On ned-box, on main at `8f38e5740`, this was run from the directory `/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/ghi-reproductions-2026-11-11/`, which holds both files named below:

```
python3 run-all-test-suites-orphaned-descendant-reproduction.py <a checkout of main> orphaned-descendant-suite-top <an empty log directory>
```

The script loads `scripts/run-all-test-suites.py` from the checkout and calls `run_one_suite(Path(top), sys.executable, "orphan-suite-test.py", Path(logs), time_limit=(3, None))`, where `top` is the directory `orphaned-descendant-suite-top`, which holds the suite, and `logs` is the log directory. It gives no sandbox prefix, which is how a suite runs outside an nc-test-sandbox. The suite, `orphaned-descendant-suite-top/orphan-suite-test.py`, is:

```python
import os, subprocess, sys, time
# Helper starts a detached grandchild in a session of its own, records it, and exits.
helper = ("import os,subprocess,sys;"
          "p=subprocess.Popen(['sleep','60'],start_new_session=True);"
          "open(os.path.join(os.environ['TMPDIR'],'grandchild.pid'),'w').write(str(p.pid))")
subprocess.run([sys.executable, "-c", helper], check=True)
print("helper exited; suite now sleeps past its limit", flush=True)
time.sleep(60)
```

The result carried `"timeout"`, and its `output_note` said only that a process still held the suite's output open 10 s after the suite ended; it named no process still running. After the call returned:

- `ps -eo pid,ppid,sid,etimes,cmd` showed the grandchild `sleep 60` still running, with parent process 1;
- the grandchild's environment held `TMPDIR=/tmp/rts-bvezs5v1`, and `ls -d /tmp/rts-bvezs5v1` answered `No such file or directory`: the runner had removed the suite's temporary directory while the grandchild was running.

The Codex review cell reproduced the same with real processes while reviewing pull request [3093](https://github.com/nedschorus/nedschorus/pull/3093); its report, first finding, is `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/cx/pr3093-17dc0f17/codex-code-review-report.md`.

## What is wrong

When a suite passes its time limit, or the run is stopped, `run_one_suite()` calls `kill_test_suite_process_group_and_descendants()`. That function sends SIGKILL to the suite's process group, and to each process that `descendant_processes_with_start_ticks()` finds below the suite in `/proc/<pid>/task/*/children`. A process that started a session or process group of its own is outside the group, and once its parent has exited it is reparented away from the suite, so the walk does not find it either. It is not killed and not listed as still running, so `run_one_suite()` removes the suite's TMPDIR under it and reports nothing about it.

The function's docstring and the runner's module docstring state this limit. Pull request 3093 did not cause it; main had it before. merge-lane-2 graded it fix-next, to be fixed in a follow-up pull request, as finding 1 of its approving review there.

The defect does not happen to a suite that runs in an nc-test-sandbox of its own: the suite's process group holds the init of the suite's PID namespace, and the init's end ends every process in the namespace. It happens to every suite that runs without one:

- the suites in `SUITES_RUN_WITHOUT_ANY_SANDBOX`, which `scripts/no-sandbox-test-suites-run-on-main-in-a-quiet-gap.py` runs;
- the suites of a run of the runner that is itself inside an nc-test-sandbox, such as one started by a suite that tests the runner: that run starts its suites without a sandbox of their own, because bwrap cannot start inside bwrap;
- every suite on macOS, where the signal sandbox is `sandbox-exec` alone and there is no nc-test-sandbox; there is no `/proc` either, so the walk finds no descendant at all and only the process-group kill happens.

The root cause is that the runner knows a suite's processes only through the parent links at the moment of the kill, and a parent's exit breaks those links.

## What to do

The owner is the agent-seat reboot-test, whose pull request 3093 wrote the current kill.

1. Give each suite that runs without an nc-test-sandbox an ownership of its processes that survives reparenting. Codex's report points to a subreaper on Linux, `prctl(PR_SET_CHILD_SUBREAPER)`: one process per suite, standing between the runner and the suite, so that the suite's orphans reparent to it and the walk below it finds them, and orphans of suites that run at the same time are not mixed. That process must also reap what it adopts.
2. On macOS, which has neither a subreaper nor `/proc`, the owner decides what the runner does, such as keeping the TMPDIR of every killed suite and saying in `output_note` that its processes could not be checked.
3. Add the reproduction as a case of `scripts/run-all-test-suites-cleanup-after-killed-runs-real-process-test.py` that asserts the grandchild is no longer running after `run_one_suite()` returns. It fails on main.
4. Change what the runner's module docstring, and the docstrings of `kill_test_suite_process_group_and_descendants()` and `run_one_suite()`, say about processes the kill does not reach, to say what the runner now does.
