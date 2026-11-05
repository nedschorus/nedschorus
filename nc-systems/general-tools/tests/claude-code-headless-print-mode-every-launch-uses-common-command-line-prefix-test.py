#!/usr/bin/env python3
"""Every headless `claude -p` launch in the repository begins its command line
with nc-systems/general-tools/claude-code-headless-print-mode-command-line-prefix-with-no-connectors-and-explicit-permission-mode-common.py,
and this test keeps it that way.

A `claude -p` command line written out by hand can leave out
--strict-mcp-config, and then the session loads the account's claude.ai
connectors, such as Gmail and Google Drive; or leave out --permission-mode, and
then it runs in the user's default mode, bypassPermissions on ned-box. So every
Python file git lists, tracked or untracked and not ignored, is read, and a
list or tuple literal fails here when its second element is "-p" or "--print"
and it also holds a flag only claude takes (CLAUDE_ONLY_FLAGS), unless its file
is the module itself, or a test, whose literals are fake claude command lines to
check a program against. The second condition keeps out `ps -p`, `mkdir -p` and
`tmux display-message -p`.

Not caught: a command line built up piece by piece, such as ["claude"] + ["-p"];
or one in a shell script or an f-string.

Run: python3 nc-systems/general-tools/tests/claude-code-headless-print-mode-every-launch-uses-common-command-line-prefix-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import ast
import importlib.util
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_variables_removal_common",
    REPOSITORY_ROOT / "nc-systems" / "general-tools"
    / "git-redirecting-environment-variables-removal-common.py")
git_redirecting_removal = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(git_redirecting_removal)

COMMAND_LINE_PREFIX_MODULE_PATH = ("nc-systems/general-tools/"
                             "claude-code-headless-print-mode-command-line-prefix-with-no-connectors-and-explicit-permission-mode-common.py")
PRINT_MODE_FLAGS = {"-p", "--print"}
CLAUDE_ONLY_FLAGS = {
    "--allowedTools", "--allowed-tools", "--disallowedTools", "--disallowed-tools",
    "--permission-mode", "--output-format", "--json-schema", "--model", "--effort",
    "--settings", "--setting-sources", "--tools", "--system-prompt", "--resume",
    "--no-session-persistence", "--strict-mcp-config", "--mcp-config",
}

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def is_a_test_file(filename):
    return filename.endswith("-test.py") or "/tests/" in filename


def hand_written_claude_print_mode_command_lines(source, filename):
    """Line numbers of the list and tuple literals in `source` that write out a `claude -p` command line."""
    lines = []
    for node in ast.walk(ast.parse(source, filename=filename)):
        if not isinstance(node, (ast.List, ast.Tuple)) or len(node.elts) < 2:
            continue
        second = node.elts[1]
        if not (isinstance(second, ast.Constant) and second.value in PRINT_MODE_FLAGS):
            continue
        strings = {element.value for element in node.elts
                   if isinstance(element, ast.Constant) and isinstance(element.value, str)}
        if strings & CLAUDE_ONLY_FLAGS:
            lines.append(node.lineno)
    return sorted(lines)


def python_files_git_lists():
    listed = subprocess.run(
        ["git", "-C", str(REPOSITORY_ROOT), "ls-files", "-z", "--cached", "--others",
         "--exclude-standard", "--", "*.py"],
        capture_output=True, text=True, check=False,
        env=git_redirecting_removal.environment_without_git_redirecting_variables())
    if listed.returncode != 0:
        print(f"git ls-files in {REPOSITORY_ROOT} exited {listed.returncode}: "
              f"{listed.stderr.strip()}", file=sys.stderr)
        sys.exit(2)
    return sorted({path for path in listed.stdout.split("\0") if path})


# --- The detector finds what it is meant to find ----------------------------
check("a planted claude -p command list is found",
      hand_written_claude_print_mode_command_lines(
          'command = ["claude", "-p", "--model", "m", "--output-format", "json"]\n',
          "scripts/planted.py") == [1])
check("a planted command tuple with the program in a variable and --print is found",
      hand_written_claude_print_mode_command_lines(
          'command = (program, "--print", prompt, "--allowedTools", "Bash")\n',
          "scripts/planted.py") == [1])
check("ps -p, mkdir -p and tmux display-message -p are not counted",
      hand_written_claude_print_mode_command_lines(
          'a = ["ps", "-p", "1", "-o", "args="]\n'
          'b = ["mkdir", "-p", "/x"]\n'
          'c = ["tmux", "display-message", "-p", "#{session_name}"]\n',
          "scripts/planted.py") == [])
check("a command list starting with the common command line prefix is not counted",
      hand_written_claude_print_mode_command_lines(
          'command = [*start("dontAsk"), "--model", "m"]\n', "scripts/planted.py") == [])

# --- No program outside the tests writes out its own claude -p command line ---
found = {}
for relative_path in python_files_git_lists():
    if is_a_test_file(relative_path):
        continue
    path = REPOSITORY_ROOT / relative_path
    if not path.is_file():
        continue    # deleted in the working tree, not yet in the index
    try:
        lines = hand_written_claude_print_mode_command_lines(
            path.read_text(encoding="utf-8"), relative_path)
    except (SyntaxError, UnicodeDecodeError) as error:
        check(f"{relative_path} can be read", False, f"{type(error).__name__}: {error}")
        continue
    if lines:
        found[relative_path] = lines

check("the module's own command line is still found, so the detector still matches it",
      COMMAND_LINE_PREFIX_MODULE_PATH in found, sorted(found))
found.pop(COMMAND_LINE_PREFIX_MODULE_PATH, None)
check("no program writes out its own claude -p command line",
      not found,
      "; ".join(f"{path} line(s) {lines}" for path, lines in sorted(found.items()))
      + " -- begin the command line with claude_code_headless_print_mode_command_line_prefix_build(<permission mode>) from "
      + COMMAND_LINE_PREFIX_MODULE_PATH + ", so it passes --strict-mcp-config and a permission mode of its own")

print()
if failures:
    print(f"{len(failures)} case(s) failed:")
    for failure in failures:
        print(f"  {failure}")
    sys.exit(1)
print("all cases passed")
