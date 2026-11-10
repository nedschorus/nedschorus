---
issue: "[The head test run wrapper crashes without its report when its stderr copy cannot be written](https://github.com/nedschorus/nedschorus/issues/1696)"
---

# The head test run wrapper crashes without its report when its stderr copy cannot be written

## Reproduction

`scripts/merge-lane-pull-request-head-test-run-on-merged-worktree.py` copies each line of a head test run's stderr to the file `<outputs>/stderr`, where `<outputs>` is `hr/pr<number>` under the merge-lane worktrees and outputs directory. When a write to that file fails, the wrapper catches the error, stops copying to that file, and goes on. The file object still holds the line it could not write. When the `with open(...)` block ends, Python closes the file, the close tries to write that line again, and it raises the same error. The wrapper then exits with a traceback. It never prints the copy-failure message, the run's exit code or its SUMMARY line.

prime-intellect found this on 2026-10-20 (UTC) while fixing PR [Head test run messages: the admission wait says it ends by itself, and the wrapper's exit 2 says nothing about the tests](https://github.com/nedschorus/nedschorus/pull/1687), and reproduced it with `/dev/full`, which fails every write with ENOSPC. merge-lane-2 reproduced the Python behaviour that makes the wrapper crash, with Python 3.14.4 on ned-box:

```
python3 - <<'EOF'
try:
    with open('/dev/full', 'w') as f:
        try:
            f.write('line\n'); f.flush()
        except OSError as e:
            print('write/flush failed, caught:', type(e).__name__, e)
    print('with block exited normally')
except OSError as e:
    print('close() at with-exit raised:', type(e).__name__, e)
EOF
```

It prints:

```
write/flush failed, caught: OSError [Errno 28] No space left on device
close() at with-exit raised: OSError [Errno 28] No space left on device
```

The wrapper's loop on main does what the inner `try` does: it catches `OSError` and `ValueError` from `target.write(line)` and `target.flush()`, records the failure, and leaves the file object open with the line still in its buffer. No test covers this case. The existing tests make `sys.stderr` fail, and the wrapper already replaces `sys.stderr` with `/dev/null` after a failure, so they never reach it.

## Why it matters

The disk under the log-store filling up is the case the wrapper's copy-failure message was written for. In that case the wrapper crashes instead of reporting. merge-lane-2 then sees a traceback rather than the run's verdict. The run itself finished, and its stdout copy holds the SUMMARY line, but the wrapper never reads it out.

## What to do

The owner is reboot-test, whose commit c31c1fcc6, "Head test run: a failed write of the runner's output is reported, and the pipes are still read to the end", added the copy loop.

1. When a write or flush to `<outputs>/stderr` fails, close that file object (the `stderr` the `with open(...)` opened, not `sys.stderr`) at once, inside its own `try`. Record any error from the close as part of the same copy failure. After that, nothing is left for the end of the `with` block to write.
2. Add a test that runs the wrapper with `<outputs>/stderr` failing on write, for example by pointing it at `/dev/full`; where `/dev/full` does not exist, as on the Mac, the test case reports itself skipped. The test checks that the wrapper prints the copy-failure message and the `PR <number> head test run: exit ...` line, and exits 2. Check the test with mutation testing on the new close.
3. Look for the same pattern elsewhere: a `with open(...)` block that catches a write error inside it and goes on. Fix each case in code the pull request already changes; list the rest in the pull request's description.
