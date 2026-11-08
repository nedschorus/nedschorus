#!/usr/bin/env python3
"""Every headless `claude -p` launch in the repository begins its command line
with nc-systems/general-tools/claude-code-headless-run-command-line-prefix-with-no-connectors-and-explicit-permission-mode-common.py,
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

Each call to claude_code_headless_run_command_line_prefix_build() in those
files must also name its permission mode as a string literal other than
bypassPermissions, so a launch moved off bypassPermissions cannot drift back to
it, or to the default, unseen.

And no file but the module holds the string literal "--settings", or one
starting "--settings=": the prefix carries the one --settings, with the advisor
turned off, and a second --settings added after it would drop that. A program
passes its own settings to the prefix function as caller_claude_code_session_settings.

Not caught: a command line built up piece by piece, such as ["claude"] + ["-p"];
or one in a shell script or an f-string; or a --permission-mode or
--dangerously-skip-permissions flag appended after the prefix.

Run: python3 nc-systems/general-tools/tests/claude-code-headless-run-every-launch-uses-common-command-line-prefix-test.py
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
                             "claude-code-headless-run-command-line-prefix-with-no-connectors-and-explicit-permission-mode-common.py")
PRINT_MODE_FLAGS = {"-p", "--print"}
CLAUDE_ONLY_FLAGS = {
    "--allowedTools", "--allowed-tools", "--disallowedTools", "--disallowed-tools",
    "--permission-mode", "--output-format", "--json-schema", "--model", "--effort",
    "--settings", "--setting-sources", "--tools", "--system-prompt", "--resume",
    "--no-session-persistence", "--strict-mcp-config", "--mcp-config",
}

COMMAND_LINE_PREFIX_BUILD_FUNCTION = "claude_code_headless_run_command_line_prefix_build"
BYPASS_PERMISSION_MODE = "bypassPermissions"

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


def permission_modes_passed_to_command_line_prefix_build(source, filename):
    """(line, permission mode) for each call in `source` to the build function; the mode is None
    when the call does not name it as a string literal."""
    calls = []
    for node in ast.walk(ast.parse(source, filename=filename)):
        if not isinstance(node, ast.Call):
            continue
        called = node.func
        called_name = called.attr if isinstance(called, ast.Attribute) else getattr(called, "id", None)
        if called_name != COMMAND_LINE_PREFIX_BUILD_FUNCTION:
            continue
        mode_node = node.args[0] if node.args else next(
            (keyword.value for keyword in node.keywords if keyword.arg == "permission_mode"), None)
        mode = (mode_node.value if isinstance(mode_node, ast.Constant)
                and isinstance(mode_node.value, str) else None)
        calls.append((node.lineno, mode))
    return sorted(calls)


def settings_flag_literal_lines(source, filename):
    """Line numbers of the string literals in `source` that are "--settings" or start "--settings="."""
    return sorted(node.lineno for node in ast.walk(ast.parse(source, filename=filename))
                  if isinstance(node, ast.Constant) and isinstance(node.value, str)
                  and (node.value == "--settings" or node.value.startswith("--settings=")))


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

check("the build function's permission mode is read from the call, positional or keyword",
      permission_modes_passed_to_command_line_prefix_build(
          'a = [*prefix.claude_code_headless_run_command_line_prefix_build("dontAsk")]\n'
          'b = claude_code_headless_run_command_line_prefix_build(permission_mode="plan")\n'
          'c = prefix.claude_code_headless_run_command_line_prefix_build("bypassPermissions", program)\n'
          'd = prefix.claude_code_headless_run_command_line_prefix_build(mode)\n'
          'e = prefix.claude_code_headless_run_command_line_prefix_build()\n',
          "scripts/planted.py")
      == [(1, "dontAsk"), (2, "plan"), (3, "bypassPermissions"), (4, None), (5, None)])
check("a --settings or --settings= literal is found, and a sentence that only mentions --settings is not",
      settings_flag_literal_lines(
          'a = [*prefix(), "--settings", "{}"]\n'
          'b = ["--settings={}"]\n'
          '"""Hooks are registered through --settings."""\n',
          "scripts/planted.py") == [1, 2])

# --- No program outside the tests writes out its own claude -p command line ---
found = {}
permission_modes_by_file = {}
settings_flags_by_file = {}
for relative_path in python_files_git_lists():
    if is_a_test_file(relative_path):
        continue
    path = REPOSITORY_ROOT / relative_path
    if not path.is_file():
        continue    # deleted in the working tree, not yet in the index
    try:
        source = path.read_text(encoding="utf-8")
        lines = hand_written_claude_print_mode_command_lines(source, relative_path)
        calls = permission_modes_passed_to_command_line_prefix_build(source, relative_path)
        settings_flags = settings_flag_literal_lines(source, relative_path)
    except (SyntaxError, UnicodeDecodeError) as error:
        check(f"{relative_path} can be read", False, f"{type(error).__name__}: {error}")
        continue
    if lines:
        found[relative_path] = lines
    if calls:
        permission_modes_by_file[relative_path] = calls
    if settings_flags:
        settings_flags_by_file[relative_path] = settings_flags

check("the module's own command line is still found, so the detector still matches it",
      COMMAND_LINE_PREFIX_MODULE_PATH in found, sorted(found))
found.pop(COMMAND_LINE_PREFIX_MODULE_PATH, None)
check("no program writes out its own claude -p command line",
      not found,
      "; ".join(f"{path} line(s) {lines}" for path, lines in sorted(found.items()))
      + " -- begin the command line with claude_code_headless_run_command_line_prefix_build(<permission mode>) from "
      + COMMAND_LINE_PREFIX_MODULE_PATH + ", so it passes --strict-mcp-config and a permission mode of its own")


check("the programs that launch claude through the build function are found",
      bool(permission_modes_by_file), sorted(permission_modes_by_file))
not_named_or_bypass = [f"{path} line {line}: {mode!r}"
                       for path, calls in sorted(permission_modes_by_file.items())
                       for line, mode in calls if mode is None or mode == BYPASS_PERMISSION_MODE]
check("every launch names its permission mode as a string literal, and none is bypassPermissions",
      not not_named_or_bypass,
      "; ".join(not_named_or_bypass)
      + f" -- pass {COMMAND_LINE_PREFIX_BUILD_FUNCTION}() a permission mode such as \"dontAsk\", "
      + "with the tools the session needs in --allowedTools, so a tool call outside them is refused")

settings_flags_by_file.pop(COMMAND_LINE_PREFIX_MODULE_PATH, None)
check("no program adds a --settings of its own, so the prefix's advisor-off --settings stays the only one",
      not settings_flags_by_file,
      "; ".join(f"{path} line(s) {lines}" for path, lines in sorted(settings_flags_by_file.items()))
      + f" -- pass the settings to {COMMAND_LINE_PREFIX_BUILD_FUNCTION}() as caller_claude_code_session_settings=<dict>, "
      + "and drop the --settings flag")

print()
if failures:
    print(f"{len(failures)} case(s) failed:")
    for failure in failures:
        print(f"  {failure}")
    sys.exit(1)
print("all cases passed")
