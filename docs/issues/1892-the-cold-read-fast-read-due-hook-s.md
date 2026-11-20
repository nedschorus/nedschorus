---
issue: "[The cold-read-fast-read due hook's test fails when the shell running it sets CLAUDE_CODE_SESSION_ATTENDED to 0](https://github.com/nedschorus/nedschorus/issues/1892)"
---

# The cold-read-fast-read due hook's test fails when the shell running it sets CLAUDE_CODE_SESSION_ATTENDED to 0

## Reproduction

On ned-box, in a detached checkout of main at `611d9501b3ce` (and again at `27cbf1faa`):

```
CLAUDE_CODE_SESSION_ATTENDED=0 python3 scripts/cold-read-fast-read-due-for-linked-document-reminder-hook-test.py
```

prints

```
FAIL  a module run() loads that is missing is a fault naming its path: exit 1, one stderr line: exit 0, stdout '', stderr ''
1 case(s) failed
```

The same suite prints `all cases passed` when the variable is unset or set to `1`.

## Why it matters

The suite's result depends on the shell that runs it, not on the code under test. Headless Claude reviewers run with `CLAUDE_CODE_SESSION_ATTENDED=0`, so every reviewer that runs this suite sees a failure that is not in the pull request it reviews. A reviewer of [PR 1879 Shared Python modules that other programs load end in -common](https://github.com/nedschorus/nedschorus/pull/1879) hit it, which is how it was found. A false failure costs a review round, and teaches reviewers to discount real failures from this suite.

## Cause

- The hook, `scripts/cold-read-fast-read-due-for-linked-document-reminder-hook.py`, returns at once, with exit 0 and no output, when `CLAUDE_CODE_SESSION_ATTENDED` is `"0"` (line 451).
- The test file is `scripts/cold-read-fast-read-due-for-linked-document-reminder-hook-test.py`. Its shared helper `run_on_written_transcript` (test file, lines 185-198) removes `CLAUDE_CODE_SESSION_ATTENDED` and `NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER` from the child's environment before starting the hook.
- Three cases that copy the hook into a scratch tree start it with their own `subprocess.run` instead (test file, lines 675, 689 and 708), with no `env=`, so the hook inherits the caller's full `os.environ`. The case at line 708 reaches the attended check before the fault it tests, so with the variable at `0` the hook exits 0 and the case fails. The cases at 675 and 689 fail at import, before that check, so they pass today only by that ordering.

Introduced by [PR 1659 cold-read-fast-read due hook: fault line names the failing path; git failures finding a checkout are reported, not read as no checkout](https://github.com/nedschorus/nedschorus/pull/1659) (commit `817f0c2a0`, 2026-10-19), which added the failing case at line 708 and the case at line 689. Its author's agent-session: https://claude.ai/code/session_01A2SGHt7Xhbjm4zQm4AAjFk.

## Root cause

A test case that starts the hook outside the shared helper inherits the caller's environment, so the suite has no single place that decides which outside variables reach the hook.

## Next action

In `scripts/cold-read-fast-read-due-for-linked-document-reminder-hook-test.py`, build the child environment in one function that removes `CLAUDE_CODE_SESSION_ATTENDED` and `NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER`, and make every case that starts the hook, the three scratch-tree cases included, pass `env=` from it. The function returns that base environment; `run_on_written_transcript` adds its store variable and `environment_extra` to it as it does now, and the scratch-tree cases use it as returned. Check the fix by running the suite with `CLAUDE_CODE_SESSION_ATTENDED=0`, unset, and `1`, and once with `NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER` set, which also silences the hook (line 450); every run must print `all cases passed`.
