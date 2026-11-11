#!/usr/bin/env python3
"""Claude Code's WorktreeCreate hook: make the worktree with
scripts/agent-seat-worktree-create-with-owner-file.py, so it has an owner file from its
first second, and print its path for Claude Code.

Claude Code runs this hook in place of its own `git worktree add` whenever it makes a
worktree: for a subagent started with isolation "worktree", for `claude --worktree`,
and for the EnterWorktree tool. It reads the hook's JSON from stdin, of which it uses
`name`, the worktree's name, such as "agent-a48479f668ee15726" for a subagent, and
`cwd`, the checkout of the agent-session that asked. It runs the creator in `cwd` with
the branch `worktree-<name>`, which, as when Claude Code makes the worktree itself, is
cut from origin/main after a `git fetch origin`; the creator puts the worktree at
<reference-checkout>/.claude/worktrees/worktree-<name> and, with --owned-by-agent-session,
writes its owner file naming the agent-session of the `claude` process that runs this hook,
with the agent-seat GIT_AUTHOR_NAME names. The creator's stderr passes through; its one
stdout line, the worktree's path, is printed on stdout, the line Claude Code reads.

What it does not handle: it makes no worktree outside a git checkout, and it does not
remove one. A worktree it made carries no Claude Code lock, and Claude Code keeps a
subagent's when the subagent ends, so scripts/clean-worktrees.py removes it by its
owner file: once its branch's pull request has merged, or once that agent-session has
ended and the worktree holds no work. nc-systems/general-tools/tests/agent-seat-worktree-create-with-owner-file-claude-code-worktree-create-hook-test.py
checks both against the installed Claude Code.

How it can fail. Input that is not JSON, or without a `name` and a `cwd` as strings,
and a creator that exits nonzero or prints no path, each exit 1 with a message on
stderr; Claude Code then makes no worktree and the subagent, or the agent-session,
does not start. The creator's own failures leave what its docstring says, at most a
branch with no worktree, or a worktree with no owner file, which it names.

Exit codes: 0 made, with the path on stdout; 1 failed.
"""

import json
import subprocess
import sys
from pathlib import Path

CREATOR = Path(__file__).resolve().parents[2] / "scripts" / "agent-seat-worktree-create-with-owner-file.py"
# Claude Code names the branch of a worktree it makes itself worktree-<name>.
BRANCH_PREFIX = "worktree-"


def fail(problem):
    print(f"agent-seat-worktree-create-with-owner-file-claude-code-worktree-create-hook: FAILED: {problem}, "
          "so no worktree was made and the agent that needed it did not start.\n"
          "Pass this message to the user word for word; the hook is in .claude/settings.json under "
          "WorktreeCreate.", file=sys.stderr)
    return 1


def main():
    try:
        hook_input = json.loads(sys.stdin.read())
    except ValueError as error:
        return fail(f"its stdin is not JSON ({error})")
    name = hook_input.get("name") if isinstance(hook_input, dict) else None
    cwd = hook_input.get("cwd") if isinstance(hook_input, dict) else None
    if not isinstance(name, str) or not name or not isinstance(cwd, str) or not cwd:
        return fail(f"its stdin JSON has no `name` and `cwd` strings: {hook_input!r}")
    completed = subprocess.run([sys.executable, str(CREATOR), BRANCH_PREFIX + name, "--owned-by-agent-session"], cwd=cwd,
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, text=True, check=False)
    path = completed.stdout.strip()
    if completed.returncode != 0 or not path:
        return fail(f"{CREATOR.name} exited {completed.returncode}"
                    + ("" if path else " and printed no worktree path")
                    + "; its own message is above")
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
