#!/usr/bin/env python3
"""Cases for the stub left under the walk-me-through current-item Stop hook's old
name: on the same stdin, arguments and environment, the stub's stdout, stderr
and exit code equal those of the renamed hook, for a reply the hook passes, a
reply it sends back, and input that makes it fail.

Delete this suite with the stub.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Before anything runs git: a GIT_DIR or similar variable inherited from the
# caller would otherwise send this suite's `git init` into another repository.
_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().parents[4] / "scripts"
    / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()
_attendance_check_spec = importlib.util.spec_from_file_location(
    "agent_session_unattended_by_user_check_common",
    Path(__file__).resolve().parents[4] / "nc-systems" / "general-tools"
    / "agent-session-unattended-by-user-check-common.py")
attendance_check = importlib.util.module_from_spec(_attendance_check_spec)
_attendance_check_spec.loader.exec_module(attendance_check)

HOOK_DIRECTORY = Path(__file__).resolve().parents[1]
STUB = HOOK_DIRECTORY / "walk-me-through-current-item-shown-to-user-after-each-agent-message-stop-hook.py"
RENAMED_HOOK = (HOOK_DIRECTORY
                / "walk-me-through-agent-reply-to-user-not-ending-with-waiting-item-closing-line-refusal-stop-hook.py")

WALK_DOCUMENT = """# A walk: approval-walk

This approval-walk settles one question. It has 2 items.

## Item 2 of 2: where the page lives

The page goes in the wiki. Recommendation: Y.
"""
PAGE = "https://claude.ai/artifact/PageOfItem2"
CLOSING_LINE = (f"[Item 2 of 2, where the page lives]({PAGE}) · A approve · AO approve as obvious · "
                "Aa approve after an advisor check · D disapprove · Z defer · E explain · O other options")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def run(script, stdin_text, checkout):
    # The hook passes every reply in an unattended session or one whose caller owns reincarnation,
    # so a caller's own values of these would hide the block a case expects.
    environment = attendance_check.environment_without_agent_session_attendance_variables(os.environ)
    # The hook passes every reply during an emergency stop, so a real stop in force would hide the block too.
    environment["NEDSCHORUS_EMERGENCY_STOP_FOLDER"] = str(Path(checkout) / "no-emergency-stop")
    return subprocess.run([sys.executable, str(script), "an-argument"], input=stdin_text,
                          capture_output=True, text=True, cwd=checkout, env=environment)


def main():
    root = Path(tempfile.mkdtemp(prefix="walk-me-through-old-name-stub-test-")).resolve()
    try:
        checkout = root / "checkout"
        walk = checkout / "docs" / "walk"
        walk.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(checkout)], check=True)
        (walk / "a-walk-2026-11-08.md").write_text(WALK_DOCUMENT)
        (walk / "a-walk-2026-11-08-minutes.md").write_text(
            f"# Minutes\n\n#item_page item 2 of 99 {PAGE}\n\n#next_to_present item 2 of 2.\n")
        transcript = root / "transcript.jsonl"
        payload = json.dumps({"hook_event_name": "Stop", "session_id": "test-session",
                              "transcript_path": str(transcript), "cwd": str(checkout),
                              "stop_hook_active": False})
        for case_name, reply, stdin_text, expected_exit_code, expects_stdout in (
                ("a reply ending with the closing line", "Recorded.\n\n" + CLOSING_LINE, payload, 0, False),
                ("a reply without the closing line", "Recorded.", payload, 0, True),
                ("input that is not JSON", "Recorded.", "not json", 1, False)):
            transcript.write_text(
                json.dumps({"type": "user", "message": {"role": "user", "content": "y"}}) + "\n"
                + json.dumps({"type": "assistant",
                              "message": {"id": "message-0", "content": [{"type": "text", "text": reply}]}})
                + "\n")
            renamed = run(RENAMED_HOOK, stdin_text, checkout)
            stub = run(STUB, stdin_text, checkout)
            check(f"{case_name}: the renamed hook exits {expected_exit_code}"
                  + (" and prints a block" if expects_stdout else ""),
                  renamed.returncode == expected_exit_code and bool(renamed.stdout.strip()) == expects_stdout,
                  f"exit {renamed.returncode}, stdout {renamed.stdout!r}, stderr {renamed.stderr!r}")
            check(f"{case_name}: the stub gives the renamed hook's stdout, stderr and exit code",
                  (stub.returncode, stub.stdout, stub.stderr)
                  == (renamed.returncode, renamed.stdout, renamed.stderr),
                  f"stub {(stub.returncode, stub.stdout, stub.stderr)!r}, "
                  f"renamed hook {(renamed.returncode, renamed.stdout, renamed.stderr)!r}")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    if failures:
        print(f"{len(failures)} case(s) failed")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
