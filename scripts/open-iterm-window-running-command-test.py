#!/usr/bin/env python3
"""Tests for open-iterm-window-running-command.

Every generation case runs with OPEN_ITERM_WINDOW_DRY_RUN=1, which prints the
AppleScript instead of executing it, and the remaining cases are argument-
validation failures — so no test ever opens a real window on the user's Mac.
The validation rules under test are the PR #82 review's F11: joining multiple
arguments must never silently change the command's word boundaries.

The login-shell cases are the other half. iTerm2 hands a custom command a bare
PATH with neither Homebrew nor ~/.local/bin on it, so the command is wrapped in
`<login shell> -l -c 'exec "$@"' <name>` — and the point of that wrapper is that
it changes NOTHING about the command it wraps. The cases below hold both halves:
the wrapper is present, and the caller's text still arrives verbatim behind it,
never re-quoted (iTerm2's parser does not implement the POSIX '\\'' escape, so
re-quoting a command containing a single quote is not available to fall back on).

Run: python3 scripts/open-iterm-window-running-command-test.py
"""

import os
import subprocess
import sys
from pathlib import Path

OPENER_SCRIPT = Path(__file__).with_name("open-iterm-window-running-command")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def wrapper_prefix(login_shell="/bin/zsh"):
    """The wrapper as it appears INSIDE the AppleScript string, where the
    shell script's own double quotes are already backslash-escaped."""
    return f"""{login_shell} -l -c 'exec \\"$@\\"' open-iterm-window-running-command """


def run_opener(arguments, dry_run=True, login_shell="/bin/zsh"):
    environment = dict(os.environ)
    if dry_run:
        environment["OPEN_ITERM_WINDOW_DRY_RUN"] = "1"
    else:
        environment.pop("OPEN_ITERM_WINDOW_DRY_RUN", None)
    # Pinned rather than inherited: the generated command names this shell, so
    # a test run under a different login shell must not change the assertions.
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

result = run_opener(["launch-claude-mac MD-skills"], login_shell="/bin/bash")
check("the wrapper runs the user's own $SHELL as a login shell",
      result.returncode == 0
      and f'command "{wrapper_prefix("/bin/bash")}launch-claude-mac MD-skills"'
      in result.stdout,
      result.stdout or result.stderr)

for good_shell in ("/bin/sh", "/bin/bash", "/bin/zsh", "/opt/homebrew/bin/bash",
                   "/bin/dash", "/bin/ksh"):
    result = run_opener(["echo hi"], login_shell=good_shell)
    check(f"a POSIX-family $SHELL is used as given ({good_shell})",
          result.returncode == 0
          and f'command "{wrapper_prefix(good_shell)}echo hi"' in result.stdout,
          result.stdout or result.stderr)

# An empty $SHELL is not a substitution — no shell was named, so /bin/sh is the
# default rather than a fallback, and a notice there would fire on every call in
# an environment that simply does not set the variable.
result = run_opener(["echo hi"], login_shell="")
check("an empty $SHELL defaults to /bin/sh silently, as no shell was named",
      result.returncode == 0
      and f'command "{wrapper_prefix("/bin/sh")}echo hi"' in result.stdout
      and result.stderr == "",
      result.stdout or repr(result.stderr))

for bad_shell, why in (("zsh", "relative"),
                       ("/opt/my shell/zsh", "containing whitespace"),
                       ("/opt/it's/zsh", "containing a quote"),
                       # Both are in this Mac's /etc/shells, and both reject
                       # `-l` and have no `exec "$@"` — a window opened under
                       # one would die instantly and say nothing.
                       ("/bin/csh", "that is csh"),
                       ("/bin/tcsh", "that is tcsh"),
                       ("/usr/local/bin/fish", "that is fish")):
    result = run_opener(["echo hi"], login_shell=bad_shell)
    check(f"a $SHELL {why} falls back to /bin/sh",
          result.returncode == 0
          and f'command "{wrapper_prefix("/bin/sh")}echo hi"' in result.stdout,
          result.stdout or result.stderr)
    check(f"the fallback from a $SHELL {why} is announced, never silent",
          "not using $SHELL" in result.stderr
          and "does NOT read that shell's login files" in result.stderr,
          repr(result.stderr))

result = run_opener(["echo hi"])
check("a usable $SHELL produces no fallback notice",
      result.returncode == 0 and result.stderr == "", repr(result.stderr))

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
