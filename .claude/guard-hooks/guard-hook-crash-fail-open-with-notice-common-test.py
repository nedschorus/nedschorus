#!/usr/bin/env python3
"""Tests for .claude/guard-hooks/guard-hook-crash-fail-open-with-notice-common.py, and for each
guard that wraps its loads and its main() in it.

Each guard is crashed for real: once in main(), by a payload whose tool_input is not an object, and
once while loading the modules it needs, by running a copy of it from a directory that holds
none of them.

Run: python3 .claude/guard-hooks/guard-hook-crash-fail-open-with-notice-common-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

GUARD_HOOKS_DIRECTORY = Path(__file__).resolve().parent
MODULE_PATH = GUARD_HOOKS_DIRECTORY / "guard-hook-crash-fail-open-with-notice-common.py"
_spec = importlib.util.spec_from_file_location(
    "guard_hook_crash_fail_open_with_notice_common", MODULE_PATH)
crash_notice = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(crash_notice)

# Each guard, and whether it loads a module of its own that a copy run elsewhere cannot find.
GUARDS = (
    ("instruction-file-guard.py", True),
    ("session-location-write-guard.py", True),
    ("backup-and-snapshot-write-guard.py", False),
    ("synthetic-keystroke-guard-hook.py", True),
    ("force-push-with-open-pull-request-guard-hook.py", True),
    ("ghi-issue-write-hand-typed-gh-command-refusal.py", True),
    ("search-file-argument-read-as-option-guard-hook.py", True),
    ("claude-code-tmux-kill-server-and-kill-session-missing-server-selection-refusal-hook.py", True),
    ("hand-typed-codex-exec-command-refusal-hook.py", True),
)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def notices_of(stdout):
    """Return (agent notice, user notice) from the hook's stdout, or None when it is not one
    JSON object carrying both."""
    try:
        output = json.loads(stdout)
        hook_output = output["hookSpecificOutput"]
        if hook_output.get("hookEventName") != "PreToolUse" or "permissionDecision" in hook_output:
            return None
        return hook_output["additionalContext"], output["systemMessage"]
    except (ValueError, KeyError, TypeError):
        return None


def check_crash_notice(case_name, result, guard_name, exception_name):
    notices = notices_of(result.stdout)
    check(f"{case_name}: exits 0, so the call goes ahead", result.returncode == 0,
          (result.returncode, result.stderr))
    check(f"{case_name}: prints nothing on stderr", result.stderr == "", result.stderr)
    check(f"{case_name}: stdout is one JSON object with both notices", notices is not None,
          result.stdout)
    if notices is None:
        return
    agent_notice, user_notice = notices
    check(f"{case_name}: the agent is told which guard crashed, with what, and that the call ran",
          f"The guard hook {guard_name} crashed" in agent_notice and exception_name in agent_notice
          and "the call has run" in agent_notice, agent_notice)
    check(f"{case_name}: the user is told which guard crashed, with what, and that the call went "
          f"ahead unchecked",
          f"The guard hook {guard_name} crashed" in user_notice and exception_name in user_notice
          and "let a tool call through unchecked" in user_notice, user_notice)


# --- the helper on its own ---

def raise_inside(running_as_hook, error):
    with crash_notice.guard_hook_crash_fail_open_with_notice_context_manager(
            "/x/.claude/guard-hooks/some-guard.py", running_as_hook):
        raise error


# BaseException: an exit 0 escaping here would end this suite as a pass.
stdout = io.StringIO()
with contextlib.redirect_stdout(stdout):
    try:
        raise_inside(False, KeyError("injected"))
        raised = None
    except BaseException as error:
        raised = error
check("when not running as the hook, a crash is raised unchanged, so a test sees it",
      isinstance(raised, KeyError), raised)

stdout = io.StringIO()
with contextlib.redirect_stdout(stdout):
    try:
        raise_inside(True, ValueError("injected value"))
        exit_code = None
    except SystemExit as error:
        exit_code = error.code
notices = notices_of(stdout.getvalue())
check("when running as the hook, a crash exits 0 with both notices",
      exit_code == 0 and notices is not None, (exit_code, stdout.getvalue()))
if notices is not None:
    check("the notices name the guard, the exception and the line it was raised at",
          all("some-guard.py" in notice and "ValueError: injected value" in notice
              and "guard-hook-crash-fail-open-with-notice-common-test.py:" in notice
              for notice in notices), notices)
    check("the agent notice says what to check, with the guard's path, and gives a subagent line",
          "/x/.claude/guard-hooks/some-guard.py says what that is" in notices[0]
          and "subagent" in notices[0] and "dispatched" in notices[0], notices[0])

try:
    raise_inside(True, SystemExit(2))
    exit_code = None
except SystemExit as error:
    exit_code = error.code
check("a guard's own exit, such as a refusal's 2, passes through unchanged", exit_code == 2,
      exit_code)

# --- each guard, crashed for real ---

with tempfile.TemporaryDirectory() as temporary_directory:
    scratch = Path(temporary_directory)
    for guard_name, loads_own_modules in GUARDS:
        guard_path = GUARD_HOOKS_DIRECTORY / guard_name
        result = subprocess.run([sys.executable, str(guard_path)],
                                input=json.dumps({"tool_name": "Bash", "tool_input": "not an object"}),
                                capture_output=True, text=True, timeout=60, cwd=scratch)
        check_crash_notice(f"{guard_name} crashing in main()", result, guard_name,
                           "AttributeError")
        if not loads_own_modules:
            continue
        copy_directory = scratch / guard_path.stem / ".claude" / "guard-hooks"
        copy_directory.mkdir(parents=True)
        shutil.copy(guard_path, copy_directory)
        shutil.copy(MODULE_PATH, copy_directory)
        result = subprocess.run([sys.executable, str(copy_directory / guard_name)],
                                input=json.dumps({"tool_name": "Bash", "tool_input": {}}),
                                capture_output=True, text=True, timeout=60, cwd=scratch)
        check_crash_notice(f"{guard_name} crashing while loading its modules", result, guard_name,
                           "FileNotFoundError")

    keystroke_copy = (scratch / "synthetic-keystroke-guard-hook" / ".claude" / "guard-hooks"
                      / "synthetic-keystroke-guard-hook.py")
    result = subprocess.run([sys.executable, str(keystroke_copy), "--is-target-detached", "x"],
                            capture_output=True, text=True, timeout=60, cwd=scratch)
    check("the synthetic keystroke guard's check mode, which is no hook, still fails on a crash",
          result.returncode != 0 and "FileNotFoundError" in result.stderr
          and notices_of(result.stdout) is None, (result.returncode, result.stdout))

if failures:
    print(f"\n{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("\nall cases passed")
