#!/usr/bin/env python3
"""Tests for open-iterm-window-running-command.

Every generation case runs with OPEN_ITERM_WINDOW_DRY_RUN=1, which prints the
AppleScript instead of executing it, and the remaining cases are argument
or shell validation failures — so no test ever opens a real window on the user's Mac.
The validation rules under test are the PR #82 review's F11: joining multiple
arguments must never silently change the command's word boundaries.

The login-shell cases are the other half. iTerm2 hands a custom command a bare
PATH with neither Homebrew nor ~/.local/bin on it, so the command is wrapped in
`/bin/zsh -l -c 'exec "$@"' <name>` — and the point of that wrapper is that
it changes NOTHING about the command it wraps. The cases below hold both halves:
the wrapper is present, and the caller's text still arrives verbatim behind it,
never re-quoted (iTerm2's parser does not implement the POSIX '\\'' escape, so
re-quoting a command containing a single quote is not available to fall back on).

Run: python3 scripts/open-iterm-window-running-command-test.py
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

OPENER_SCRIPT = Path(__file__).with_name("open-iterm-window-running-command")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def wrapper_prefix():
    """The wrapper as it appears INSIDE the AppleScript string, where the
    shell script's own double quotes are already backslash-escaped."""
    return """/bin/zsh -l -c 'exec \\"$@\\"' open-iterm-window-running-command """


def run_opener(arguments, dry_run=True, login_shell="/bin/zsh"):
    environment = dict(os.environ)
    if dry_run:
        environment["OPEN_ITERM_WINDOW_DRY_RUN"] = "1"
    else:
        environment.pop("OPEN_ITERM_WINDOW_DRY_RUN", None)
    environment["SHELL"] = login_shell
    return subprocess.run(["sh", str(OPENER_SCRIPT), *arguments],
                          capture_output=True, text=True, env=environment)


result = run_opener([])
check("no arguments is a usage error",
      result.returncode == 2 and "usage:" in result.stderr, result.stderr)

result = run_opener(["ssh -t ned tmux attach -t gatekeeper"])
check("a single command string lands verbatim behind the login-shell wrapper",
      result.returncode == 0
      and f'create window with default profile command "{wrapper_prefix()}'
          'ssh -t ned tmux attach -t gatekeeper"'
      in result.stdout,
      result.stdout or result.stderr)

# The window is useless if the app stays in the background: AppleScript's
# `tell application` launches iTerm without bringing it forward, which is how
# a whole reboot's worth of restarted seats stayed invisible on 2026-09-18.
check("the script activates iTerm before creating the window",
      result.returncode == 0
      and "\tactivate\n" in result.stdout
      and result.stdout.index("activate") < result.stdout.index("create window"),
      result.stdout or result.stderr)

result = run_opener(["ssh", "-t", "ned", "tmux", "attach"])
check("several simple arguments join with single spaces",
      result.returncode == 0
      and f'command "{wrapper_prefix()}ssh -t ned tmux attach"' in result.stdout,
      result.stdout or result.stderr)

result = run_opener(['echo "a\\b"'])
check("double quotes and backslashes are escaped for the AppleScript string",
      result.returncode == 0
      and f'command "{wrapper_prefix()}echo \\"a\\\\b\\""' in result.stdout,
      result.stdout or result.stderr)

result = run_opener(["tmux", "attach", "-t", "seat a"])
check("F11: multiple arguments where one contains a space are refused",
      result.returncode == 2 and "one quoted argument" in result.stderr,
      result.stderr)

result = run_opener(["echo", "don't"])
check("F11: multiple arguments where one contains a quote are refused",
      result.returncode == 2 and "one quoted argument" in result.stderr,
      result.stderr)

result = run_opener(["echo hi\necho bye"])
check("a raw newline in the command is refused (AppleScript cannot hold it)",
      result.returncode == 2 and "raw newline" in result.stderr, result.stderr)

check("the newline refusal points at a shell of the caller's own, not a bare ';'",
      "argument vector" in result.stderr and "sh -c" in result.stderr,
      result.stderr)

result = run_opener(["tmux attach -t 'seat a'"])
check("a single argument may of course contain spaces and quotes",
      result.returncode == 0 and "seat a" in result.stdout,
      result.stdout or result.stderr)

# The login-shell wrapper (2026-09-02): iTerm2 gives a custom command a bare
# PATH, so `tmux` and `claude` are not found and the window dies before it can
# say why. The wrapper must be present, and must leave the command untouched.

check("a command containing a single quote is NOT re-quoted for the wrapper",
      result.returncode == 0
      and f"{wrapper_prefix()}tmux attach -t 'seat a'\"" in result.stdout,
      result.stdout or result.stderr)

for login_shell in ("/bin/bash", "/usr/local/bin/fish", "", "relative shell"):
    result = run_opener(["echo hi"], login_shell=login_shell)
    check(f"the wrapper uses /bin/zsh regardless of SHELL={login_shell!r}",
          result.returncode == 0
          and f'command "{wrapper_prefix()}echo hi"' in result.stdout
          and result.stderr == "",
          result.stdout or result.stderr)

# Override the executable check without changing the machine's /bin/zsh. A dry run
# never runs zsh, so this case runs for real, with a stand-in osascript on PATH that
# the opener must not reach.
stand_in_directory = Path(tempfile.mkdtemp())
stand_in_osascript = stand_in_directory / "osascript"
stand_in_osascript.write_text("#!/bin/sh\necho osascript-was-run\n")
stand_in_osascript.chmod(0o755)
environment_without_dry_run = {key: value for key, value in os.environ.items()
                               if key != "OPEN_ITERM_WINDOW_DRY_RUN"}
environment_without_dry_run["PATH"] = f"{stand_in_directory}:{os.environ.get('PATH', '')}"
result = subprocess.run(
    ["sh", "-s", "--", "echo hi"],
    input='''test() {
    if [ "$1" = "-x" ] && [ "$2" = "/bin/zsh" ]; then
        return 1
    fi
    command test "$@"
}
''' + OPENER_SCRIPT.read_text(),
    capture_output=True, text=True,
    env=environment_without_dry_run)
shutil.rmtree(stand_in_directory, ignore_errors=True)
check("an unavailable /bin/zsh stops window creation with an error",
      result.returncode == 1 and result.stdout == ""
      and "window creation stopped" in result.stderr
      and "/bin/zsh is missing or not executable" in result.stderr,
      result.stdout or result.stderr)

result = run_opener(["echo lit$HOME and ; a semicolon"])
check("no expansion layer is added: $ and ; reach iTerm as written",
      result.returncode == 0
      and f"{wrapper_prefix()}echo lit$HOME and ; a semicolon\"" in result.stdout,
      result.stdout or result.stderr)


print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print(f"all cases passed")
