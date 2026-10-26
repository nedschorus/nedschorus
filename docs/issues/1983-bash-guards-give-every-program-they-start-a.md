---
issue: "[Bash guards give every program they start a time limit of their own, so a program that never exits cannot hold up the Bash guards replay for hours](https://github.com/nedschorus/nedschorus/issues/1983)"
---

# Bash guards give every program they start a time limit of their own, so a program that never exits cannot hold up the Bash guards replay for hours

The Bash guards replay, `nc-systems/general-tools/bash-guards-verdict-changes-between-two-git-refs-on-transcript-recorded-commands-check.py`, runs every Bash command recorded in the agent-sessions' transcripts through every Bash guard, once at main and once at a pull request's head commit, to show which verdicts the pull request changes. A Bash guard is a PreToolUse hook with the matcher `Bash` in `.claude/settings.json`; there are seven. A pair is one recorded command with the working directory it ran in; a reading is one pair run through one guard. Each reading gets a time limit, the per-pair timeout, 20 seconds by default.

Since PR [Replay check: the per-pair timeout waits until no subprocess call is running, so it cannot leave subprocess's wait lock held](https://github.com/nedschorus/nedschorus/pull/1838), merged 2026-10-22, the replay does not let the per-pair timeout fire while a guard is inside a call to Python's `subprocess` module, for example while it waits for a program it started to exit. A timeout fired inside that module's own code can leave a lock in the module held, after which the next wait on the program blocks forever; so the replay keeps putting the timeout off until the call returns. The gap: a guard that starts a program which never exits, and passes no `timeout` of its own to that call, would make the reading run on until the replay's limit for the whole step stops the step, and that limit can be many hours (worked out below).

The fix this GHI asks for is in the guards, not in the replay: each call that starts a program, made by a Bash guard or by a module the guard loads, passes a `timeout`.

No reproduction exists. This is a gap judged from reading the code: no guard is known to have hung this way, and, as the check below shows, every program the Bash guards start on main today already has a time limit.

## Why

A replay whose step runs to that limit holds up the merge of the pull request it was run for, because merge-lane-2 holds the merge until the replay runs without failing, and it takes a share of ned-box's processors for the whole time. A live guard has no such gap: Claude Code stops a hook that runs past the `timeout` its `.claude/settings.json` entry gives it, 30 seconds for every Bash guard. Only the replay lets an unbounded program run on. Agent-seats reboot-test and merge-lane-2 agree that the fix belongs in the guards, not in the replay, because the replay's putting-off of the timeout is what keeps that lock from being left held; removing it would bring back the hang PR 1838 fixed.

The user approved filing this GHI on 2026-10-26, at 13:58 by the minutes' clock, answering "A" (file the issue, owned by reboot-test) to item 12 of 23 of merge-lane-2's approval-walk merge-lane-2-everything-waiting-on-the-user-2026-10-22; its minutes are `nedlern@ned-box:/home/nedlern/agents/merge-lane-2/docs/walk/merge-lane-2-everything-waiting-on-the-user-2026-10-22-minutes.md`.

## The code, on main at commit 29fb37b38

- `raise_pair_timed_out()`, the handler of the per-pair timeout's signal, walks the interrupted stack frames, and when any belongs to the `subprocess` module it sets the timer again for 0.05 seconds and returns instead of raising ([lines 172-188](https://github.com/nedschorus/nedschorus/blob/29fb37b38707b03bdefed9027e4907212f3df6c8/nc-systems/general-tools/bash-guards-verdict-changes-between-two-git-refs-on-transcript-recorded-commands-check.py#L172-L188)). So a subprocess call that never returns has its timeout put off every 0.05 seconds until the step's limit, below, kills the step.
- `read_within_pair_timeout()` sets the per-pair timeout with `signal.alarm()`, and when the reading returns after its timeout was put off, counts the reading as timed out ([lines 190-204](https://github.com/nedschorus/nedschorus/blob/29fb37b38707b03bdefed9027e4907212f3df6c8/nc-systems/general-tools/bash-guards-verdict-changes-between-two-git-refs-on-transcript-recorded-commands-check.py#L190-L204)). The default, `DEFAULT_PER_PAIR_TIMEOUT_SECONDS`, is at [line 83](https://github.com/nedschorus/nedschorus/blob/29fb37b38707b03bdefed9027e4907212f3df6c8/nc-systems/general-tools/bash-guards-verdict-changes-between-two-git-refs-on-transcript-recorded-commands-check.py#L83).
- The step's limit, from `step_deadline_seconds()`, is sized for every reading of every pair to time out, and then for every pair to be read again alone and time out again ([lines 775-779](https://github.com/nedschorus/nedschorus/blob/29fb37b38707b03bdefed9027e4907212f3df6c8/nc-systems/general-tools/bash-guards-verdict-changes-between-two-git-refs-on-transcript-recorded-commands-check.py#L775-L779)): (pairs ÷ workers, rounded up, + pairs) × (guards + 1) × per-pair timeout + a 600-second margin ([line 87](https://github.com/nedschorus/nedschorus/blob/29fb37b38707b03bdefed9027e4907212f3df6c8/nc-systems/general-tools/bash-guards-verdict-changes-between-two-git-refs-on-transcript-recorded-commands-check.py#L87)). For example, 1,000 pairs on 4 workers, with the seven guards and the default timeout, give (250 + 1,000) × 8 × 20 s + 600 s = 200,600 s, about 56 hours. `run_step_in_child()` waits for the step until that limit, then kills it and raises `ReplayFailed` ([lines 782-804](https://github.com/nedschorus/nedschorus/blob/29fb37b38707b03bdefed9027e4907212f3df6c8/nc-systems/general-tools/bash-guards-verdict-changes-between-two-git-refs-on-transcript-recorded-commands-check.py#L782-L804)).

## Which Bash guards start a program without a time limit today: none

The check, run on 2026-10-26 on main at commit 29fb37b38. Its scope was the seven Bash guards listed in `.claude/settings.json` and the modules they load. Each file was parsed with Python's `ast` module. Every call of `subprocess.run`, `subprocess.Popen`, `subprocess.check_output`, `subprocess.check_call` or `subprocess.call` was found, and also every call of a function the guard names `runner`, which is how these guards take `subprocess.run` as an argument so that a test or the replay can pass a stand-in. Each call was checked for a `timeout=` argument. A `grep` of the same files for `os.system`, `os.popen`, `os.exec`, `os.spawn`, `create_subprocess`, `pty.`, `.communicate(` and `.wait(` found nothing.

- `scripts/synthetic-keystroke-guard-hook.py` line 296: has `timeout`.
- `scripts/force-push-with-open-pull-request-guard-hook.py` lines 283 and 318: have `timeout`.
- `.claude/hooks/ghi-issue-write-hand-typed-gh-command-refusal.py` line 418: has `timeout`; the function of `scripts/ghi-issue-write.py` it calls, `run()`, passes its `timeout` on to `subprocess.run`.
- `nc-systems/general-tools/claude-code-bash-git-push-of-markdown-change-citation-checks-reminder-hook.py` line 143: has `timeout`.
- `nc-systems/general-tools/shell-command-tree-sitter-bash-reader-common.py`, the shell reader, which every guard loads, lines 426, 743 and 1648: have `timeout`.
- `scripts/search-file-argument-read-as-option-guard-hook.py`, `nc-systems/general-tools/claude-code-tmux-kill-server-and-kill-session-missing-server-selection-refusal-hook.py`, `scripts/hand-typed-codex-exec-command-refusal-hook.py` and `nc-systems/general-tools/tmux-target-or-server-does-not-exist-error-pattern-common.py`: no call that starts a program.

The check looked for a `timeout=` argument, not at its value.

## What to do

reboot-test, which owns the replay and the shell reader, does each step:

1. Keep every Bash guard, and every module one loads, to the rule: each call that starts a program passes a `timeout`. On main today every such call does, as the check above shows; a pull request that adds or changes a Bash guard, or a module one loads, keeps it so. A `timeout` added to such a call needs no test of its own: CLAUDE.md's rule on guards, validation and retries names "a timeout sized to an operation the code already performs" among the three things that need no test, so the reviewer of such a pull request does not block the `timeout` as an unneeded guard.
2. Record the outcome in this GHI-MD and close the issue.
