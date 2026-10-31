---
issue: "[Hooks that tell the agent something on stderr with exit 1 are read only by the user, because Claude Code never gives that stderr to the model](https://github.com/nedschorus/nedschorus/issues/1796)"
---

# Hooks that tell the agent something on stderr with exit 1 are read only by the user, because Claude Code never gives that stderr to the model

## Reproduction

Claude Code 2.1.306, on ned-box, in a scratch directory outside the repository: `claude -p` with `--settings` holding one PostToolUse hook on `Write`, which prints three lines to stderr, `MARK-LINE-ONE`, `MARK-LINE-TWO` and `MARK-LINE-THREE`, and exits 1. The prompt asked the model to write a file, then to quote every text in its context that mentions MARK-LINE, or to say NONE.

- **Exit 1.** The transcript records the hook's output as a `hook_non_blocking_error` record whose `stderr` holds all three lines. The `api-request` record sent after the hook ran (line 31 of the transcript) contains no `MARK` text at all. The model answered: "MARK-LINE: NONE. No hook output, error or other text in my context mentions it." Transcript: `nedlern@ned-box:/home/nedlern/.claude/projects/-home-nedlern--cache-merge-lane-pull-request-reviewer-scratch-directories-rv1795-r1-probe/00f861d4-7301-4c76-9c52-a9753f4f3827.jsonl`.
- **Exit 2, as a control.** The same hook exiting 2 put all three lines in the model's context, as `PostToolUse:Write hook blocking error from command: ...`, and the model quoted all three. Transcript: the one `.jsonl` file under `nedlern@ned-box:/home/nedlern/.claude/projects/-home-nedlern--cache-merge-lane-pull-request-reviewer-scratch-directories-rv1795-r1-probe2/`.

The pull request reviewer `mac-claude` ran these probes for review 5599415547 on [pull request 1795](https://github.com/nedschorus/nedschorus/pull/1795); read the review with `gh api repos/nedschorus/nedschorus/pulls/1795/reviews --jq '.[] | select(.id==5599415547) | .body'` and its inline comment with `gh api repos/nedschorus/nedschorus/pulls/1795/comments --jq '.[] | select(.pull_request_review_id==5599415547) | .body'`.

Earlier probes on Claude Code 2.1.294 and 2.1.295 agree. Their transcripts are under `nedlern@ned-box:/home/nedlern/.claude/projects/`, in the directories whose names start with `-tmp-claude-1000--home-nedlern-agents-merge-lane-2-e1187575-` and end with `rv1107r2-probe2`, `rv1107r3-exp`, `rv1107r3-exp2`, `rv1107-stopprobe` and `rv1109-stopprobe`.

### Which hook events this was tested on

| Hook event | Tested | Result |
|---|---|---|
| PostToolUse | 2.1.306, with the exit-2 control above; also 2.1.295 (`rv1107r3-exp2`) | the model never received the exit-1 stderr |
| UserPromptSubmit | 2.1.295 only (`rv1107r2-probe2`), no exit-2 control | a hook printing `PROBE-STDERR-MARK-1` on stderr with exit 1 was recorded as `hook_non_blocking_error`; asked to quote any text containing `PROBE-STDERR-MARK`, the model answered NONE |
| Stop | not tested for delivery | exit 1 is recorded as `hook_non_blocking_error` (2.1.294, 2.1.295), but no model turn followed it in those probes, so they do not show whether the next turn receives the stderr |
| PreToolUse, SessionStart, SubagentStop | not tested | |

The [Claude Code hooks reference](https://code.claude.com/docs/en/hooks) describes the same behavior: exit 2 gives stderr to Claude on most events, PostToolUse among them, and any other nonzero code is a non-blocking error shown to the user while work continues. So the defect is not in Claude Code. The defect is in this project's hooks and their docstrings, which assume the agent reads that stderr.

## Why this matters

Each hook listed below writes on stderr, with exit 1, either an instruction the agent is meant to follow, or the news that a hook's work was not done, so that the agent knows not to rely on it. Neither reaches the agent. The user sees, at most, a notice in the transcript view, and the agent goes on as if the hook had run cleanly. Some docstrings say outright that the agent is told: `scripts/markdown-edit-hard-wrapped-paragraph-reminder-hook-nbd.py:19` says an exit-1 line means "the agent is told the check was not made".

## The hooks

Line numbers are at origin/main commit `1846c5282`, and each cites the line that starts the stderr text. Every hook below is registered in `.claude/settings.json`.

[Pull request 1795](https://github.com/nedschorus/nedschorus/pull/1795), open when this GHI was filed, fixes the git-failure reports of `scripts/file-name-collision-warning-hook.py` and `scripts/obsolete-file-edit-warning-hook.py`: those reports move to exit 0 with JSON `hookSpecificOutput.additionalContext`. At `1846c5282` both reports still print to stderr and exit 1, at `scripts/file-name-collision-warning-hook.py:162` and `scripts/obsolete-file-edit-warning-hook.py:528`; they are left out of the list below only because pull request 1795 fixes them. If pull request 1795 closes without merging, add them back. The crash handler of `scripts/obsolete-file-edit-warning-hook.py` still prints to stderr and exits 1 after pull request 1795, so the crash handler is listed.

### Instructions the agent is meant to follow

- `scripts/markdown-edit-hard-wrapped-paragraph-reminder-hook-nbd.py:325` (PostToolUse): markdown-it-py is missing; tells the agent to go on, write each paragraph as one line, and tell the user.
- `scripts/new-shared-names-reminder-hook.py:425` (PostToolUse): a git failure; tells the agent nothing needs rerunning, and what to do if the failure recurs.
- `scripts/ned-box-path-in-agent-reply-unclickable-on-mac-warning-hook.py:83` (UserPromptSubmit): the hook broke; tells the agent how to link a ned-box file for the Mac, and to tell the user if the failure recurs.
- `scripts/absence-claim-locator-reminder-hook.py:525` (Stop and SubagentStop): the hook broke; tells the agent to run the hook's test and tell the user what it reports if the failure recurs.
- `scripts/agent-seat-due-task-raise-hook.py:513` (Stop): a `HookFault`, such as a state file that cannot be written; tells the agent which directory to make writable.
- `.claude/hooks/session-location-write-guard.py:243` (PreToolUse): the guard could not check a write; tells the agent to carry on when the write is into its own checkout on a branch, and otherwise to tell the user.

### News that the hook's work was not done

- `scripts/markdown-edit-hard-wrapped-paragraph-reminder-hook-nbd.py:313`, `:331` and `:349` (PostToolUse): a git failure, an Edit whose added lines cannot be found, and the hook's own crash handler.
- `scripts/style-guide-word-checker-markdown-edit-hook-nbd.py:169` (PostToolUse): the crash handler. The docstring at `:10-12` names exit 1 as the hook's way of reporting a fault.
- `scripts/bare-number-citation-in-markdown-and-agent-reply-warning-hook.py:771` (UserPromptSubmit and PostToolUse): the crash handler.
- `scripts/obsolete-file-edit-warning-hook.py:581` (PostToolUse): the crash handler.
- `scripts/agent-seat-due-task-raise-hook.py:516` (Stop): the crash handler; its stderr text tells the agent that no task was checked at this stop, and that the first stop without the fault raises any due task.
- `scripts/post-compaction-session-continues-hook.py:215` (SessionStart, matcher `compact`): the crash handler; the agent is not told to continue after compaction.

### Says the agent need not act

- `scripts/cold-read-fast-read-due-for-linked-document-reminder-hook.py:120` (Stop).
- `nc-systems/skills/walk-me-through/walk-me-through-current-item-shown-to-user-after-each-agent-message-stop-hook.py:539` (Stop).

These two say the agent need not act, so an agent that never reads them loses nothing. They are listed so that step 2 of the next action decides their channel too: leave them at exit 1, or move them with the rest.

How the list was made: for every program registered in `.claude/settings.json` at `1846c5282`, `grep -n 'return 1$\|exit(1)\|EXIT_.*= *1'` and `grep -n 'file=sys.stderr'`, then reading each match. `.claude/hooks/guarded-file-unapproved-change-afterward-backup-and-ask-hook.py` has `EXIT_REFUSED = 1`, but only on its `--approve` and `--restore` command-line paths; run as a hook, it reports in `additionalContext` and exits 0. A hook that exits 1 through a value computed elsewhere would not show in this search.

## Related, and not the same work

- GHI [Design the project's Claude Code hooks: requirements drawn from the existing hooks, then keep, fix, merge, rewrite or remove each one](https://github.com/nedschorus/nedschorus/issues/1790) does not mention which channel a hook's output reaches.
- GHI [Every refusal and warning a program hands an agent says why and what to do instead](https://github.com/nedschorus/nedschorus/issues/956) is about the wording of such messages, not about whether they reach the agent.
- reboot-test's approval-walk on exit codes, whose walk-document is `nedlern@ned-box:/home/nedlern/agents/reboot-test/docs/walk/exit-code-convention-wiki-page-2026-10-20.md` (the 17-item version in reboot-test's agent-home; the copy in the log-store is older and has 11 items), proposes in item 6 that "When the agent's next act depends on the check having run, as with a guard that could not check a command, the hook exits 0 and tells the agent in `additionalContext`", and in item 15 that a hook tells the agent things through `additionalContext` at exit 0 and, when it breaks, prints the cause on stderr and exits 1. The user has not decided items 6 and 15: the walk-minutes, `nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/exit-code-convention-wiki-page-2026-10-20-minutes.md`, record items 1 and 2 approved and item 3 as the next to present. This GHI does not decide those items.

## Next action

1. For each hook event not yet tested (Stop, SubagentStop, PreToolUse, SessionStart, and UserPromptSubmit on a current Claude Code), find whether an exit-1 hook's stderr reaches the model, by a probe like the one in the reproduction: a hook that prints a known string on stderr and exits 1, then a prompt asking the model to quote that string, with the same hook at exit 2 as a control. For Stop and SubagentStop, ask on the user prompt that follows the stop. On each event, also probe exit 0 with JSON `hookSpecificOutput.additionalContext`, and note whether exit 2 stops the act, as it would for a PreToolUse guard such as `session-location-write-guard.py` that means to let the write go ahead.
2. For each listed hook whose report the agent must act on, move that report to a channel the model reads on that hook's event without stopping an act the hook means to allow, and correct the hook's docstring and tests to match. Which channel each event uses, such as exit 0 with `additionalContext` or exit 2 with stderr, is a design question, and it may wait for the user's decision on items 6 and 15 of the approval-walk above.
3. Name the Claude Code version that showed the behavior wherever the fix records it: 2.1.306.
4. Any workaround gets a regression test that fails if Claude Code starts giving the model an exit-1 hook's stderr, so that the project learns when the workaround is no longer needed. The probe of step 1, kept as a script that runs `claude -p` and is run after each Claude Code upgrade, is one way to build that test; it calls the model, so it does not belong in the offline test suites.
