#!/usr/bin/env python3
"""Tests for .claude/guard-hooks/hand-typed-git-worktree-add-refusal-hook.py.

Each case drives main() with the JSON payload the harness sends, and one case
pipes a payload into the hook as a real process. One case runs the commands the
refusal gives in a throwaway clone, to show they work as the refusal says.

Run: python3 .claude/guard-hooks/hand-typed-git-worktree-add-refusal-hook-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK_SCRIPT = Path(__file__).with_name("hand-typed-git-worktree-add-refusal-hook.py")
_spec = importlib.util.spec_from_file_location("hand_typed_git_worktree_add_refusal_hook", HOOK_SCRIPT)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def hook_output(payload_text):
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code = hook.main(stdin=io.StringIO(payload_text))
    return code, stdout.getvalue().strip()


def refusal(command, tool_name="Bash"):
    code, text = hook_output(json.dumps({"tool_name": tool_name, "tool_input": {"command": command}}))
    if code != 0:
        return f"<exit {code}>"
    if not text:
        return None
    output = json.loads(text)["hookSpecificOutput"]
    return output.get("permissionDecisionReason") if output.get("permissionDecision") == "deny" else None


REFUSED = [
    ("a bare git worktree add", "git worktree add -b topic ../topic origin/main"),
    ("git -C <clone> worktree add", "git -C ~/Projects/nedschorus worktree add --detach /tmp/x HEAD"),
    ("git -c <setting> worktree add", "git -c core.hooksPath=/dev/null worktree add /tmp/x"),
    ("a flag with no value before worktree", "git --no-pager worktree add /tmp/x"),
    ("git worktree add after &&", "cd /tmp && git worktree add x"),
    ("git worktree add after ;", "echo hi; git worktree add x"),
    ("git worktree add after ||", "false || git worktree add x"),
    ("git worktree add in a pipeline", "git worktree add x 2>&1 | tail -1"),
    ("git worktree add in a subshell", "( git worktree add x )"),
    ("git worktree add in a command substitution", 'echo "$(git worktree add x)"'),
    ("git worktree add behind env and timeout", "env A=1 timeout 60 git worktree add x"),
    ("git worktree add after an environment assignment", "GIT_AUTHOR_NAME=me git worktree add x"),
    ("git by full path", "/usr/bin/git worktree add x"),
    ("inside bash -c", "bash -c 'git worktree add x'"),
    ("inside sh -c after another command", "sh -c 'cd /tmp && git -C r worktree add x'"),
]

ALLOWED = [
    ("git worktree list", "git worktree list --porcelain"),
    ("git worktree remove", "git worktree remove --force /tmp/x"),
    ("git worktree prune", "git -C ~/Projects/nedschorus worktree prune"),
    ("the creator itself", "python3 scripts/agent-seat-worktree-create-with-owner-file.py topic"),
    ("worktree add as a grep pattern", "git grep -n 'worktree add' origin/main"),
    ("worktree add inside an echoed string", 'echo "git worktree add x"'),
    ("git add, not worktree add", "git add worktree"),
    ("the remote command of ssh", "ssh nedlern@ned-box 'git -C ~/Projects/nedschorus worktree add --detach x origin/main'"),
    ("a heredoc body not run by a shell", "cat > notes.txt <<'EOF'\ngit worktree add x\nEOF"),
]


def main():
    for name, command in REFUSED:
        reason = refusal(command)
        check(f"refused: {name}", reason == hook.REFUSAL_MESSAGE, f"{command!r} -> {reason!r}")
    for name, command in ALLOWED:
        reason = refusal(command)
        check(f"allowed: {name}", reason is None, f"{command!r} -> {reason!r}")

    check("a tool other than Bash is not read", refusal("git worktree add x", tool_name="Read") is None)
    for name, text in (("not JSON", "{"), ("a JSON list", "[]"),
                       ("no command", json.dumps({"tool_name": "Bash", "tool_input": {}})),
                       ("a command that is not text",
                        json.dumps({"tool_name": "Bash", "tool_input": {"command": 7}}))):
        code, output = hook_output(text)
        check(f"malformed payload ({name}): exits 0 and says nothing", code == 0 and output == "",
              f"{code} {output!r}")

    original = hook.shell_reader.simple_commands

    def unavailable(*arguments, **keywords):
        raise hook.shell_reader.ShellParserUnavailable("pip: network is unreachable (injected)")

    hook.shell_reader.simple_commands = unavailable
    try:
        code, output = hook_output(json.dumps({"tool_name": "Bash",
                                               "tool_input": {"command": "git worktree add x"}}))
    finally:
        hook.shell_reader.simple_commands = original
    context = json.loads(output)["hookSpecificOutput"] if output else {}
    check("shell reader unavailable: the command is let through, with this hook's next steps",
          code == 0 and "permissionDecision" not in context
          and hook.PARSER_UNAVAILABLE_NEXT_STEP_LINES in context.get("additionalContext", ""),
          output[:400])

    for line in ("<branch name> --base <commit>", "--detach <directory name> <commit>",
                 "prints the new worktree's path"):
        check(f"the refusal carries {line!r}", line in hook.REFUSAL_MESSAGE)
    check("the refusal names the creator by a path that exists", hook.CREATOR_PATH.is_file()
          and str(hook.CREATOR_PATH) in hook.REFUSAL_MESSAGE)

    process = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": "git worktree add x"}}),
        capture_output=True, text=True, check=False)
    decision = json.loads(process.stdout)["hookSpecificOutput"] if process.stdout.strip() else {}
    check("run as a process, the hook denies with the refusal",
          process.returncode == 0 and decision.get("permissionDecision") == "deny"
          and decision.get("permissionDecisionReason") == hook.REFUSAL_MESSAGE,
          f"{process.returncode} {process.stdout[:200]!r} {process.stderr[:200]!r}")

    root = Path(tempfile.mkdtemp(prefix="hand-typed-git-worktree-add-refusal-hook-test-"))
    try:
        refusal_commands_run_in_a_throwaway_clone(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    if failures:
        print(f"\n{len(failures)} case(s) failed")
        return 1
    print("\nall cases passed")
    return 0


def refusal_commands_run_in_a_throwaway_clone(root):
    """Run each command the refusal gives, with its placeholders filled, in a clone with an origin."""
    home = root / "home"
    clone = home / "Projects" / "nedschorus"
    (home / ".claude" / "handoffs").mkdir(parents=True)
    (home / ".claude" / "handoffs" / "seat-a-handoff.md").write_text("handoff\n")
    (home / "agents" / "seat-a").mkdir(parents=True)
    (root / "empty-gitconfig").write_text("")
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(("GIT_", "CLAUDE_", "NEDSCHORUS_"))}
    environment.update(HOME=str(home), GIT_CONFIG_NOSYSTEM="1", GIT_AUTHOR_NAME="seat-a",
                       GIT_CONFIG_GLOBAL=str(root / "empty-gitconfig"))

    def shell(command, cwd=clone):
        return subprocess.run(["bash", "-c", command], cwd=cwd, env=environment,
                              capture_output=True, text=True, check=False)

    clone.mkdir(parents=True)
    for command in ("git init -q --bare --initial-branch=main ../../origin.git",
                    "git init -q --initial-branch=main",
                    "git -c user.name=f -c user.email=f@example.invalid commit -q --allow-empty -m base",
                    "git remote add origin ../../origin.git && git push -q origin main",
                    "git push -q origin main:refs/heads/pushed && git branch -q existing"):
        shell(command)
    commands = [line.split("run: ", 1)[1] for line in hook.REFUSAL_MESSAGE.splitlines()
                if "run: " in line]
    filled = [commands[0].replace("<branch name>", "new-topic"),
              commands[0].replace("<branch name>", "existing"),
              commands[0].replace("<branch name>", "pushed"),
              commands[1].replace("<branch name>", "based-topic").replace("<commit>", "HEAD"),
              commands[2].replace("<directory name>", "detached").replace("<commit>", "HEAD")]
    for command in filled:
        ran = shell(command)
        made = Path(ran.stdout.strip())
        check(f"the refusal's command works: {command.split('.py', 1)[1].strip()}",
              ran.returncode == 0 and made.is_dir()
              and made.parent == (clone / ".claude" / "worktrees").resolve(),
              f"{ran.returncode} {ran.stdout!r} {ran.stderr[-400:]!r}")


if __name__ == "__main__":
    sys.exit(main())
