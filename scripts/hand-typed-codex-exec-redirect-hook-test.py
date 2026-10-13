#!/usr/bin/env python3
"""Tests for scripts/hand-typed-codex-exec-redirect-hook.py.

Each case drives main() with the JSON payload the harness sends, and one case
pipes a payload into the hook as a real process.

Run: python3 scripts/hand-typed-codex-exec-redirect-hook-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

HOOK_SCRIPT = Path(__file__).with_name("hand-typed-codex-exec-redirect-hook.py")
_spec = importlib.util.spec_from_file_location("codex_exec_redirect", HOOK_SCRIPT)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def refusal(command, tool_name="Bash"):
    payload = {"tool_name": tool_name, "tool_input": {"command": command}}
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code = hook.main(stdin=io.StringIO(json.dumps(payload)))
    if code != 0:
        return f"<exit {code}>"
    text = stdout.getvalue().strip()
    if not text:
        return None
    output = json.loads(text)["hookSpecificOutput"]
    return output.get("permissionDecisionReason") if output.get("permissionDecision") == "deny" else None


REFUSED = {
    "a bare codex exec with an argument prompt": 'codex exec -C /tmp/x "do the task"',
    "codex exec in the background": 'codex exec -s workspace-write -o r.md "task" &',
    "codex exec in a backgrounded subshell": '( codex exec -C x -o y "task"; echo done ) &',
    "codex exec with stdin closed": 'codex exec -C x "task" < /dev/null',
    "codex exec reading its prompt from a pipe": 'cat brief.md | codex exec -',
    "the exec alias e": 'codex e "task"',
    "codex exec by full path": '/opt/homebrew/bin/codex exec "task"',
    "codex exec after a global option with a value": 'codex -c model="x" exec "task"',
    "codex exec behind env, nohup and timeout": 'env A=1 nohup timeout 600 codex exec "task"',
    "codex exec after an environment assignment": 'CODEX_HOME=/tmp/h codex exec "task"',
    "codex exec after &&": 'cd /tmp && codex exec "task"',
    "codex exec inside a command substitution": 'out=$(codex exec "task")',
    "codex exec inside bash -c": "bash -c 'codex exec -C x \"task\"'",
    "codex exec inside an ssh command": "ssh nedlern@ned-box 'cd ~/x && codex exec \"task\"'",
    "codex exec reading a heredoc": 'codex exec - <<EOF\ndo the task\nEOF',
    "codex exec after a global --search": 'timeout 1500 codex --search exec --skip-git-repo-check "task"',
    "codex exec inside bash -lc": "bash -lc 'cd x; codex exec \"task\"'",
    "codex exec inside bash -o pipefail -c": "bash -o pipefail -c 'codex exec \"task\" | tee log'",
    "codex exec inside nohup bash -c": "nohup bash -c 'codex exec \"task\" > log 2>&1' &",
    "codex exec inside ssh with options that take values":
        "ssh -o ConnectTimeout=10 -p 22 nedlern@ned-box 'codex exec \"task\" < /dev/null'",
    "codex exec in ssh's remote command given as several words": "ssh ned-box cd x '&&' codex exec task",
    "codex exec inside bash -c inside ssh":
        "ssh ned-box \"bash -c 'codex exec task'\"",
    "codex exec inside a substitution inside double quotes": 'echo "$(codex exec task)"',
    "codex review behind exec": 'codex exec review --uncommitted',
    "codex exec behind env -u, whose option takes a value":
        'env -u GIT_DIR -u GIT_WORK_TREE timeout 400 codex exec "task"',
    "codex exec behind sandbox-exec -f": "sandbox-exec -f p.sb codex exec --sandbox danger-full-access task",
    "codex exec in a heredoc that ssh runs": "ssh -o BatchMode=yes ned-box <<'EOF'\ncd x\ncodex exec task\nEOF",
    "codex exec in a heredoc that a remote bash -s runs":
        "ssh ned-box bash -s <<'EOF'\ncodex exec task < /dev/null\nEOF",
    "codex exec behind setsid nohup over ssh":
        "ssh -o ConnectTimeout=8 ned-box 'cd x && setsid nohup codex exec task > log 2>&1 &'",
    "codex exec run by eval": "eval codex exec $ARGS -C . 'task'",
    "codex exec in a heredoc that a local bash runs": "bash <<'EOF'\ncodex exec task\nEOF",
    "codex exec writing its report to a file named help": "codex exec -o help 'task' &",
    "codex exec whose prompt, after --, is --help": "codex exec -- '--help'",
    "codex exec inside bash -c --": "bash -c -- 'codex exec task'",
    "codex exec in a heredoc that bash -s runs with arguments":
        "bash -s one two <<'EOF'\ncodex exec task\nEOF",
    "codex exec resume whose later operand is help": "codex exec resume --last help",
    "codex exec whose second operand is help": "codex exec task help",
    "codex exec whose help may be a second image": "codex exec -i shot.png help",
}

ALLOWED = {
    "the new program": "python3 scripts/run-codex-task-from-brief.py -C . --brief b.md -o r.md",
    "codex --version": "codex --version",
    "codex exec --help": "codex exec --help",
    "codex exec -h after its options": "codex exec -C x -h",
    "codex exec help": "codex exec help",
    "codex login status": "codex login status",
    "a grep for the words codex exec": 'grep -rn "codex exec" docs/',
    "an echo that mentions codex exec": "echo 'never type codex exec by hand'",
    "a heredoc body that mentions codex exec": "cat > notes.md <<'EOF'\ncodex exec \"x\"\nEOF",
    "a commit message that mentions codex exec": 'git commit -m "Refuse a hand-typed codex exec"',
    "ps listing codex processes": "ps -axo pid,command | grep codex",
    "pgrep for codex exec": "pgrep -fl 'git push|codex exec'",
    "an ssh command that runs no codex": "ssh -o BatchMode=yes ned-box 'ls ~/codex-exec-notes'",
    "an ssh session with no remote command": "ssh -p 22 ned-box",
    "bash running a script file": "bash scripts/run.sh codex exec",
    "a bash -c that mentions codex exec in quoted text": "bash -c 'echo \"codex exec\"'",
    "a heredoc of notes appended over ssh": "ssh ned-box 'cat >> notes.md' <<'EOF'\nNever type `codex exec` by hand.\nEOF",
    "an eval that runs no codex": "eval \"$(ssh-agent -s)\"",
    "a heredoc fed to a bash script file": "bash run.sh <<'EOF'\ncodex exec task\nEOF",
    "a python heredoc that mentions codex exec": "python3 - <<'EOF'\nprint('codex exec')\nEOF",
    "a cold-read cell, which runs Codex itself":
        "python3 nc-systems/cold-read/cold-read-codex-cell.py --prompt-file p.md -o r.md",
    "a cold-read cell run over ssh":
        "ssh nedlern@ned-box 'cd ~/x && python3 nc-systems/cold-read/cold-read-codex-cell.py --prompt-file p.md'",
}

for name, command in REFUSED.items():
    got = refusal(command)
    check(f"refused: {name}", got == hook.REFUSAL, f"got {got!r}")

for name, command in ALLOWED.items():
    got = refusal(command)
    check(f"allowed: {name}", got is None, f"got {got!r}")

check("a tool other than Bash is ignored",
      refusal('codex exec "task"', tool_name="Read") is None)

check("the refusal gives the program's usage line",
      hook.USAGE_LINE in hook.REFUSAL)

check("the refusal names the program by an absolute path that exists, so it runs from any folder",
      hook.RUNNER_PATH.is_absolute() and hook.RUNNER_PATH.is_file()
      and f"python3 {hook.RUNNER_PATH} " in hook.USAGE_LINE, hook.USAGE_LINE)

check("the refusal writes Codex's configuration keys with their -c",
      all(f"-c {key}" in hook.REFUSAL for key in (
          "sandbox_workspace_write.network_access", "sandbox_workspace_write.writable_roots",
          "web_search", "model_reasoning_effort")), hook.REFUSAL)

check("the refusal maps Codex's own widening options to the program's",
      all(option in hook.REFUSAL for option in ("--network", "--writable-root",
                                                "--outside-git-checkout", "--web-search")))

saved_simple_commands = hook.shell_reader.simple_commands


def parser_missing(_command):
    raise hook.shell_reader.ShellParserUnavailable("pip: no network")


hook.shell_reader.simple_commands = parser_missing
try:
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code = hook.main(stdin=io.StringIO(json.dumps(
            {"tool_name": "Bash", "tool_input": {"command": 'codex exec "task"'}})))
finally:
    hook.shell_reader.simple_commands = saved_simple_commands
output = json.loads(stdout.getvalue() or "{}").get("hookSpecificOutput", {})
check("without the shell parser the hook exits 0, lets the command through and says so",
      code == 0 and "permissionDecision" not in output
      and "hand-typed codex exec guard" in output.get("additionalContext", "")
      and "pip: no network" in output.get("additionalContext", ""), repr(output))

program_help = subprocess.run(
    [sys.executable, str(HOOK_SCRIPT.with_name("run-codex-task-from-brief.py")), "--help"],
    capture_output=True, text=True, check=False)
for flag in ("-C", "--brief", "-o", "--sandbox", "-m", "--effort", "--network",
             "--writable-root", "--outside-git-checkout", "--web-search",
             "--deadline-minutes", "--run-log"):
    check(f"the usage line's flag {flag} is one the program accepts",
          flag in hook.USAGE_LINE and flag in program_help.stdout,
          program_help.stdout[:200])

usage_in_program_docstring = " ".join(
    program_help.stdout.split("Usage:\n", 1)[-1].split("\n\n", 1)[0].split())
hook_usage_options = hook.USAGE_LINE.split(f"python3 {hook.RUNNER_PATH} ", 1)[-1]
program_usage_options = usage_in_program_docstring.split("scripts/run-codex-task-from-brief.py ", 1)[-1]
check("the hook's usage line carries the program's own usage line, word for word",
      hook_usage_options == program_usage_options, f"{hook_usage_options!r} vs {program_usage_options!r}")

process = subprocess.run(
    [sys.executable, str(HOOK_SCRIPT)],
    input=json.dumps({"tool_name": "Bash",
                      "tool_input": {"command": 'codex exec "task" &'}}),
    capture_output=True, text=True, check=False)
decision = json.loads(process.stdout)["hookSpecificOutput"] if process.stdout.strip() else {}
check("as a process, the hook denies a hand-typed codex exec and exits 0",
      process.returncode == 0 and decision.get("permissionDecision") == "deny",
      f"exit {process.returncode}, stdout {process.stdout!r}")

process = subprocess.run(
    [sys.executable, str(HOOK_SCRIPT)],
    input=json.dumps({"tool_name": "Bash", "tool_input": {"command": "git status"}}),
    capture_output=True, text=True, check=False)
check("as a process, the hook allows an ordinary command silently",
      process.returncode == 0 and not process.stdout.strip(),
      f"exit {process.returncode}, stdout {process.stdout!r}")

if failures:
    print(f"{len(failures)} case(s) failed: " + ", ".join(failures))
    sys.exit(1)
print("all cases passed")
