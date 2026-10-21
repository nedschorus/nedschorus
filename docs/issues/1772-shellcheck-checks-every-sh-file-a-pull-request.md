---
issue: "[ShellCheck checks every .sh file a pull request changes, and its findings block the merge](https://github.com/nedschorus/nedschorus/issues/1772)"
---

# ShellCheck checks every .sh file a pull request changes, and its findings block the merge

ShellCheck is the standard linter for shell scripts. It finds defects that a reviewer reading the script often misses, such as an unquoted variable that splits on spaces, a `cd` whose failure is ignored, or a test written with the wrong operator. Neither ned-box nor the Mac has ShellCheck today, and no lint reads the project's shell scripts for these defects.

## Why

- A shell defect such as an unquoted variable passes review and fails only when a path or an argument holds a space or is empty. ShellCheck finds such defects mechanically, and a review prompt does not find them reliably.
- GHI [Replace the hand-written parsers in the project's hooks and scripts with real parsers](https://github.com/nedschorus/nedschorus/issues/1196) holds the open question on linters, Deferred-decision 3, and GHI [Agents reuse what the project has already solved: shared helpers, one page of reusable components, and a reuse check before, during and after the build](https://github.com/nedschorus/nedschorus/issues/1123) listed "whether ShellCheck gets a GHI of its own" as open. The user decided on 2026-10-20 that it does, by approving item 37 of agent-instructions-editor's approval-walk, whose minutes are `nedlern@ned-box:/home/nedlern/agents/agent-instructions-editor/docs/walk/agent-instructions-editor-every-open-decision-2026-10-15-minutes.md`.
- The trawl of linters, `nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/reboot-test/detection-and-correction-techniques-research-2026-10-10/linters-trawl.md`, recommends ShellCheck.

## What is decided

The three steps run in this order.

1. An agent-seat installs ShellCheck on ned-box with `sudo apt install shellcheck`, and an agent-seat on the Mac installs it with `brew install shellcheck`. This GHI is a design the user decided on, so the daily check of GHI [Regular maintenance: the list of maintenance jobs, how often each runs, and how each reaches the user](https://github.com/nedschorus/nedschorus/issues/1058), which checks that every command-line tool such a design requires runs on both machines, covers ShellCheck from then on.
2. One pull request runs ShellCheck over every `.sh` file on main and either fixes each finding or marks it, with a ShellCheck `disable` directive on the line above the finding and a comment giving the reason. On 2026-10-20, `git ls-files '*.sh'` listed two: `scripts/launch-claude-update-step-test.sh` and `scripts/merge-gate.sh`.
3. ShellCheck then runs on every file ending in `.sh` that a pull request adds or changes and that still exists after the pull request. Its findings block the merge, like any other code finding. When ShellCheck cannot run, the lint says so and fails, so the merge is blocked rather than passed unchecked.

## Deferred-decisions

1. Where the lint of step 3 runs: as a test suite that `scripts/run-all-test-suites.py` runs, as a step of `scripts/merge-gate.sh`, or both. The trawl of linters recommends a test suite, and also a PostToolUse hook, a Claude Code hook that runs after each Edit or Write, that reports findings without fixing them. The agent-seat that builds step 3 brings this to the user before building it.
2. Whether ShellCheck also reads shell code that is not in a `.sh` file, such as a script with a `#!/bin/bash` first line and no extension.

## Next action

Install ShellCheck on both machines, then open the pull request of step 2.
