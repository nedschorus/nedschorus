#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/failed-command-agent-facing-message-rerun-once-then-stop-and-report-lines-common.py.

The programs that print these lines reach this module through their own
suites. These cases pin the wording itself, word for word, so a change to it
is a change a reviewer sees here, and pin the rerun command and the printer
that the file-edit hooks take from the module.

Run: python3 nc-systems/general-tools/tests/failed-command-agent-facing-message-rerun-once-then-stop-and-report-lines-common-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "failed_command_agent_facing_message_rerun_once_then_stop_and_report_lines_common",
    REPOSITORY_ROOT / "nc-systems" / "general-tools"
    / "failed-command-agent-facing-message-rerun-once-then-stop-and-report-lines-common.py")
next_step_lines = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(next_step_lines)

failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


WHO = "the user, or, if you are a subagent, the agent that dispatched you,"

lines = next_step_lines.git_failure_next_step_lines(
    "`p --x`", "p", text_the_failure_line_contains="p: could not",
    include_the_misspelt_branch_commit_or_path_line=True).splitlines()
check("a git failure in a program that takes names on its command line gets four lines: "
      "two cases, the unchanged rerun when no case applies, and the stop naming "
      "the text to look for, who is told, and which lines",
      lines == [
          "If git's error names a lock file, such as .git/index.lock, do not delete the lock file "
          "yourself, because a git command still running may hold it; wait up to one minute for git "
          "to remove it by running `i=0; while [ -e \"<lock file path>\" ] && [ $i -lt 30 ]; do "
          "sleep 2; i=$((i+1)); done` with <lock file path> replaced by the path git's error names, "
          "without the quotes git puts around it (Claude Code refuses a plain `sleep 60`), then run exactly `p --x`, whether or not the "
          "lock file is gone.",
          "If a branch, commit or path you gave p on its command line is misspelt or does "
          "not exist, correct it in your command, then run the corrected command.",
          "If none of the cases above applies, run exactly `p --x` once more.",
          'If the rerun, or the corrected command, prints a line containing "p: could not" '
          f'again, stop, and tell {WHO} word for word, the line containing "p: could not" '
          "from each run."], lines)

lines = next_step_lines.git_failure_next_step_lines(
    "`git -C d status`", "the sync", include_the_misspelt_branch_commit_or_path_line=False,
    rerun_fails_when="prints an error again", which_lines_to_quote_in_the_report="the sync line and the error",
    read_by_a_subagent=False,
    next_step_to_skip_when_the_rerun_fails_too="act on the rest of this prompt").splitlines()
check("a program that takes no names gets one case; a line no subagent reads names only "
      "the user; the stop holds back the work that follows; free text replaces the marker",
      lines[1:] == [
          "If git's error names no lock file, run exactly `git -C d status` once more.",
          "If the rerun prints an error again, stop, do not act on the rest of this prompt, "
          "and tell the user word for word, the sync line and the error."], lines)

for case_name, arguments in [
        ("neither the failure text nor the free-text pair", {}),
        ("the failure text and which lines to quote",
         {"text_the_failure_line_contains": "x", "which_lines_to_quote_in_the_report": "y"}),
        ("the failure text and when the rerun fails",
         {"text_the_failure_line_contains": "x", "rerun_fails_when": "fails"}),
        ("when the rerun fails without which lines to quote", {"rerun_fails_when": "fails"})]:
    try:
        line = next_step_lines.agent_instruction_if_rerun_fails_too_stop_and_report_both_runs_line(
            **arguments)
    except TypeError as error:
        line = None
        said = str(error)
    check(f"a call giving {case_name} is refused, naming the arguments",
          line is None and "text_the_failure_line_contains" in said
          and "which_lines_to_quote_in_the_report" in said, line)

line = next_step_lines.hook_agent_instruction_if_git_failure_recurs_tell_user_both_outputs_line(
    "at your next Edit", "h:")
check("a hook's line names the prefix to look for, says any git failure counts, when to "
      "tell, and that a clean check needs no report",
      line == 'If a line starting "h:" reports a git failure again at your next Edit, whether '
              f"this error or another, tell {WHO} word for word, every line of this message and "
              "of the new one, before you go on. If the check finds no git failure then, this "
              "failure needs no report.", line)

line = next_step_lines.hook_agent_instruction_if_rerun_command_reports_git_failure_tell_user_both_outputs_line("h:")
check("a hook that hands over a rerun command says to look inside the JSON's additionalContext "
      "field for the prefix, who is told, and that a clean rerun needs no report",
      line == "If the command on the line above prints JSON whose hookSpecificOutput.additionalContext "
              f'field starts with "h:" and reports a git failure, whether this error or another, tell {WHO} '
              "word for word, every line of this message and of that field, before you go on. If the "
              "command prints nothing, or JSON whose field reports no git failure, the git failure "
              "above needs no report.", line)


def run_lock_file_wait_command(lock_file, seconds_until_removed=None):
    """Run the wait command the lock-file line gives, on lock_file; return (exit code, seconds taken)."""
    command = next_step_lines.WAIT_UP_TO_ONE_MINUTE_FOR_LOCK_FILE_TO_GO_COMMAND.replace(
        next_step_lines.LOCK_FILE_PATH_PLACEHOLDER, str(lock_file))
    if seconds_until_removed is not None:
        command = f'(sleep {seconds_until_removed}; rm -f "{lock_file}") & {command}; wait'
    started = time.monotonic()
    completed = subprocess.run(["sh", "-c", command], check=False, timeout=90)
    return completed.returncode, time.monotonic() - started


with tempfile.TemporaryDirectory() as directory:
    lock_file = Path(directory) / "index.lock"
    exit_code, seconds = run_lock_file_wait_command(lock_file)
    check("the lock-file wait command, run by sh, returns at once when the lock file is absent",
          exit_code == 0 and seconds < 2, (exit_code, seconds))
    lock_file.write_text("")
    exit_code, seconds = run_lock_file_wait_command(lock_file, seconds_until_removed=1)
    check("the lock-file wait command returns within one poll of git removing the lock file",
          exit_code == 0 and 1 <= seconds < 5 and not lock_file.exists(), (exit_code, seconds))

with tempfile.TemporaryDirectory() as directory:
    # A sleep stub first on PATH returns at once and counts its calls, so the cap is reached in no time.
    stub_directory = Path(directory) / "bin"
    stub_directory.mkdir()
    calls = Path(directory) / "sleep-calls"
    (stub_directory / "sleep").write_text(f'#!/bin/sh\necho "$1" >> "{calls}"\n')
    (stub_directory / "sleep").chmod(0o755)
    lock_file = Path(directory) / "index.lock"
    lock_file.write_text("")
    command = next_step_lines.WAIT_UP_TO_ONE_MINUTE_FOR_LOCK_FILE_TO_GO_COMMAND.replace(
        next_step_lines.LOCK_FILE_PATH_PLACEHOLDER, str(lock_file))
    completed = subprocess.run(["sh", "-c", command], check=False, timeout=30,
                               env={"PATH": f"{stub_directory}:/usr/bin:/bin"})
    polls = calls.read_text().splitlines() if calls.exists() else []
    check("the lock-file wait command, against a lock file that stays, stops after exactly 30 polls of "
          "2 seconds, one minute in all",
          completed.returncode == 0 and polls == ["2"] * 30, (completed.returncode, polls))

with tempfile.TemporaryDirectory() as directory:
    hook_script_path = Path(directory) / "a hook's copy.py"
    hook_script_path.write_text(
        "import sys\nsys.stdout.write(sys.stdin.read())\n", encoding="utf-8")
    working_directory = Path(directory) / "o'clock dir"
    file_path = "docs/it's a file \u00e9.md"
    command = next_step_lines.file_edit_hook_shell_command_that_runs_the_hook_on_one_file_as_claude_code_would(
        hook_script_path, working_directory, file_path)
    payload = json.dumps({"cwd": str(working_directory), "tool_input": {"file_path": file_path}})
    check("the rerun command pipes the hook's payload into python3 running the hook script given",
          command == "printf '%s\\n' " + payload.replace("'", "'\"'\"'").join("''")
          + " | python3 '" + str(hook_script_path).replace("'", "'\"'\"'") + "'", command)
    completed = subprocess.run(["bash", "-c", command], capture_output=True, text=True, timeout=30)
    check("run by a shell, the rerun command hands the hook script the cwd and file path "
          "Claude Code would, quotes and spaces intact",
          completed.returncode == 0 and json.loads(completed.stdout)
          == {"cwd": str(working_directory), "tool_input": {"file_path": file_path}},
          (completed.returncode, completed.stdout, completed.stderr))

printed = io.StringIO()
with contextlib.redirect_stdout(printed):
    next_step_lines.post_tool_use_hook_additional_context_print_for_agent("line one \u00e9\nline two")
check("the printer writes one JSON object carrying the text as PostToolUse additionalContext, "
      "non-ASCII unescaped",
      printed.getvalue() == json.dumps({"hookSpecificOutput": {
          "hookEventName": "PostToolUse", "additionalContext": "line one \u00e9\nline two"}},
          ensure_ascii=False) + "\n" and "\u00e9" in printed.getvalue(), printed.getvalue())

print(f"{failures} failure(s)" if failures else "all cases pass")
sys.exit(1 if failures else 0)
