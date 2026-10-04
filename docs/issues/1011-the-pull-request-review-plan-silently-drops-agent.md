---
issue: "[The pull request review plan silently drops agent-facing text and split test suites when run from a subdirectory of the checkout](https://github.com/nedschorus/nedschorus/issues/1011)"
---

# The pull request review plan silently drops agent-facing text and split test suites when run from a subdirectory of the checkout

Filed without the user's sign-off by the agent-seat ned-box-helper on 2026-10-03, at the request of merge-lane-2. The user ruled on 2026-08-23 that a reproduced finding whose consequence is at least wrong behavior in operation is filed that way; the ruling is recorded in merge-lane-2's `CLAUDE.local.md` on ned-box. The reproduction comes first; the cause and the next action follow it.

## Reproduction

The program is `scripts/pull-request-review-plan.py` as it is on main at `8d9751d`. Every command below ran on ned-box in a checkout of that commit; `<checkout>` stands for the checkout's top level.

1. The plan for PR [install-scheduled-jobs: back up the crontab before each write, and name the backup in every FAILED write](https://github.com/nedschorus/nedschorus/pull/999), at head commit `d660caf4`, computed twice. The first run used `--repository <checkout>` and the second `--repository <checkout>/scripts`, each with `--json`. Both runs exited 0, and both gave the same head commit, merge base, tier (`full-reviewer`) and test files. Only one field differs:
   - `agent_facing_text_whole_pull_request`: 2 entries from the top level, the first being the changed `--help` docstring of `nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py`, and 0 entries from `scripts/`.
2. The underlying git call, with that pull request's merge base `dc6ff64a` and head commit `d660caf4`:
   - From `<checkout>`, `git diff -U0 dc6ff64a d660caf4 -- nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py | wc -l` prints `101`.
   - From `<checkout>/scripts`, the same command prints `0`.
3. The program's test-file selection function, `test_files_to_run_for_changed_files(repository, head, changed_files)`, called directly with `head` set to `"HEAD"` and `changed_files` set to one changed program, `[{"path": "nc-systems/handoff/handoff-supervisor.py", "status": "M"}]`:
   - with `repository` set to `<checkout>`, the function returns the three suites `nc-systems/handoff/tests/handoff-supervisor-session-end-and-resume-test.py`, `nc-systems/handoff/tests/handoff-supervisor-session-launch-and-seat-lock-test.py` and `nc-systems/handoff/tests/handoff-supervisor-successor-prompt-test.py`;
   - with `repository` set to `<checkout>/scripts`, the function returns `[]`.

Neither run printed a warning or an error. The plan is what the merge-lane reads to write the reviewer brief when it commissions a review of a pull request. A reviewer brief written from the second plan would list no changed agent-facing text and, for a change to the supervisor, no test file to run.

The finding was first reproduced by the `mac-claude` reviewer on PR [handoff-supervisor-test: split into three suites that run at once, and stop the processes it left running](https://github.com/nedschorus/nedschorus/pull/977), in review [5401931552](https://github.com/nedschorus/nedschorus/pull/977#pullrequestreview-5401931552) and its inline comment [r4174185591](https://github.com/nedschorus/nedschorus/pull/977#discussion_r4174185591). The reviewer marked it as a defect that predates that pull request and did not block on it.

## Cause

`--repository` defaults to `Path.cwd()` (line 784), and the only check on the directory is `git rev-parse --git-dir` (line 555), which succeeds in any subdirectory. Every git call runs as `git -C <repository>`. Git reads a pathspec relative to the `-C` directory, and `git ls-tree` prints paths relative to the `-C` directory, but the program passes paths relative to the checkout's top level. Three calls go wrong this way:

- line 314, `git diff ... -- <path>` for a changed Markdown file. With no diff, a change inside a fenced code block reads as prose, so the file gets the review tier `seat-alone` instead of `seat-and-codex`; the program's module docstring defines its review tiers. This consequence follows from the code; no run demonstrated it.
- line 476, `git diff ... -- <path>` for a changed program, which yields the empty agent-facing text in step 1.
- line 506, `git ls-tree ... -- <directory>/`, which finds no part of a split suite, giving the empty list in step 3.

The `<revision>:<path>` reads, such as `read_revision_blob_or_none`, are relative to the top level, and the changed-file list comes from a `git diff` with no pathspec, so both stay correct. The plan is therefore partly right and gives no sign of the parts that are wrong.

## Next action

Change `compute_pull_request_review_plan` in `scripts/pull-request-review-plan.py`, the function that computes the plan and passes `repository` to every helper. The change goes after the existing `--git-dir` check at line 555, which keeps refusing a directory outside any checkout, and does one of two things:

- resolve `--repository` to `git rev-parse --show-toplevel` before any other git call, so that a run from a subdirectory, the default of the current directory included, gives the same plan as a run from the top level; or
- refuse with a message naming the top level when `--repository` is not the top level, so that a run from a subdirectory, the default of the current directory included, exits 1 instead of giving a partial plan.

The fixer chooses one and gives the reason in the pull request. Helper functions such as `test_files_to_run_for_changed_files` keep taking the top level as given. `scripts/run-all-test-suites.py` already refuses a directory other than the top level, because `git ls-files` falls into the same trap.

Add a case to `scripts/pull-request-review-plan-test.py` that runs the program with `--repository` naming a subdirectory. With the first choice, the case asserts that the plan equals the top-level run's plan, agent-facing text included. With the second, the case asserts exit 1 and the refusal message. Either way the case fails on the current program, which exits 0 with a partial plan, and passes after the change. Patching only line 506, for example with `--full-tree`, would leave lines 314 and 476 wrong.
