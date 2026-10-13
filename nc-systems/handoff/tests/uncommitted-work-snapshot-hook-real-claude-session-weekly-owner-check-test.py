#!/usr/bin/env python3
"""Tests for nc-systems/handoff/uncommitted-work-snapshot-hook-real-claude-session-weekly-owner-check.py.

Each case runs the check with --claude-program naming a fake claude, a Python
script that does what one outcome of a real session would do, and with
--record-directory in a scratch directory, so no case starts a real claude or
writes to the log-store. In the passing case the fake writes the file and runs
the hook command the scratch clone's settings register, as claude does after a
Bash call; to be the claude process the hook looks for, the fake first replaces
itself with a copy of this Python interpreter named claude. In the failing
cases the fake writes the work-snapshot itself, through the scratch clone's
copy of the module, with whatever owner, file or transcript the case needs.

Run: python3 nc-systems/handoff/tests/uncommitted-work-snapshot-hook-real-claude-session-weekly-owner-check-test.py
"""

import importlib.util
import json
import os
import signal
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

SYSTEM_DIRECTORY = Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = SYSTEM_DIRECTORY.parent.parent
CHECK = SYSTEM_DIRECTORY / "uncommitted-work-snapshot-hook-real-claude-session-weekly-owner-check.py"

_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    REPOSITORY_ROOT / "scripts" / "git-redirecting-environment-removal-test-fixture.py")
_fixture = importlib.util.module_from_spec(_fixture_spec)
_fixture_spec.loader.exec_module(_fixture)
_fixture.remove_git_redirecting_environment_variables_from_this_process()

SCRATCH = Path(tempfile.mkdtemp(prefix="real-claude-session-weekly-owner-check-test-"))
GLOBAL_CONFIG = SCRATCH / "gitconfig"
GLOBAL_CONFIG.write_text("[init]\n\tdefaultBranch = main\n")
os.environ.update(GIT_CONFIG_GLOBAL=str(GLOBAL_CONFIG), GIT_CONFIG_NOSYSTEM="1")

FAKE_CLAUDE = SCRATCH / "fake-claude.py"
FAKE_CLAUDE.write_text(r'''#!/usr/bin/env python3
import importlib.util, json, os, subprocess, sys, time
from pathlib import Path
mode = os.environ["FAKE_CLAUDE_MODE"]
session = "11111111-2222-3333-4444-555555555555"
named_claude = os.environ["FAKE_CLAUDE_PYTHON_NAMED_CLAUDE"]
if mode == "hook" and sys.executable != named_claude:
    os.execv(named_claude, [named_claude, __file__, *sys.argv[1:]])
if mode == "login-lapsed":
    print("Invalid API key · Please run /login", file=sys.stderr)
    sys.exit(1)
if mode == "hang":
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"])
    Path(os.environ["FAKE_CLAUDE_CHILD_PROCESS_ID_FILE"]).write_text(str(child.pid))
    Path(os.environ["FAKE_CLAUDE_PROCESS_ID_FILE"]).write_text(str(os.getpid()))
    time.sleep(600)
if mode == "error-result":
    print(json.dumps({"is_error": True, "result": "API Error: Connection error.",
                      "session_id": session}))
    sys.exit(0)
if mode == "no-json":
    print("not json")
    sys.exit(0)
clone = Path.cwd()
settings = json.loads(Path(sys.argv[sys.argv.index("--settings") + 1]).read_text())
Path(os.environ["FAKE_CLAUDE_ARGUMENTS_FILE"]).write_text(json.dumps({
    "arguments": sys.argv[1:], "settings": settings, "clone": str(clone)}))
if mode == "breaks-clone":
    import shutil
    shutil.rmtree(clone / ".git")
    print(json.dumps({"is_error": False, "result": "done", "session_id": session}))
    sys.exit(0)
if mode == "hook":
    (clone / "live-check.txt").write_text("live\n")
    hook = subprocess.run(
        settings["hooks"]["PostToolUse"][0]["hooks"][0]["command"], shell=True, text=True,
        capture_output=True, input=json.dumps({
            "session_id": session, "transcript_path": f"/transcripts/{session}.jsonl",
            "cwd": str(clone), "hook_event_name": "PostToolUse", "tool_name": "Bash",
            "tool_input": {"command": "echo live > live-check.txt"}}))
    print(f"hook exited {hook.returncode}: {hook.stdout}{hook.stderr}", file=sys.stderr)
    print(json.dumps({"is_error": False, "result": "done", "session_id": session}))
    sys.exit(0)
spec = importlib.util.spec_from_file_location(
    "m", clone / "nc-systems" / "handoff" / "uncommitted-work-snapshots.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
(clone / ("other.txt" if mode == "no-file" else "live-check.txt")).write_text("live\n")
owner = os.getppid() if mode == "other-owner" else os.getpid()
transcript_session = "99999999-0000-0000-0000-000000000000" if mode == "wrong-session" else session
if mode != "no-snapshot":
    module.refresh_work_snapshot(clone, module.owner_key_of_process(owner), "seat",
                                 f"/transcripts/{transcript_session}.jsonl")
print(json.dumps({"is_error": False, "result": "done", "session_id": session}))
''')
FAKE_CLAUDE.chmod(0o755)
FAKE_CLAUDE_PROCESS_ID_FILE = SCRATCH / "fake-claude-process-id"
FAKE_CLAUDE_CHILD_PROCESS_ID_FILE = SCRATCH / "fake-claude-child-process-id"
FAKE_CLAUDE_ARGUMENTS_FILE = SCRATCH / "fake-claude-arguments.json"
# A copy, not a symbolic link: the process name the hook reads is the name of the file executed.
PYTHON_NAMED_CLAUDE = SCRATCH / "python-named-claude" / "claude"
PYTHON_NAMED_CLAUDE.parent.mkdir()
shutil.copy2(Path(sys.executable).resolve(), PYTHON_NAMED_CLAUDE)
os.environ.update(FAKE_CLAUDE_PROCESS_ID_FILE=str(FAKE_CLAUDE_PROCESS_ID_FILE),
                  FAKE_CLAUDE_CHILD_PROCESS_ID_FILE=str(FAKE_CLAUDE_CHILD_PROCESS_ID_FILE),
                  FAKE_CLAUDE_ARGUMENTS_FILE=str(FAKE_CLAUDE_ARGUMENTS_FILE),
                  FAKE_CLAUDE_PYTHON_NAMED_CLAUDE=str(PYTHON_NAMED_CLAUDE))

_check_spec = importlib.util.spec_from_file_location("weekly_owner_check", CHECK)
weekly_owner_check = importlib.util.module_from_spec(_check_spec)
_check_spec.loader.exec_module(weekly_owner_check)

failures = []


def check(condition, name, detail=""):
    if condition:
        print(f"ok   {name}")
    else:
        print(f"FAIL {name}" + (f": {detail}" if detail else ""))
        failures.append(name)


run_count = [0]


def run_check(mode, *extra, claude_program=None, timeout=120, environment=None):
    run_count[0] += 1
    records = SCRATCH / f"records-{run_count[0]}"
    completed = subprocess.run(
        [sys.executable, str(CHECK), "--claude-program", str(claude_program or FAKE_CLAUDE),
         "--record-directory", str(records), *extra],
        capture_output=True, text=True,
        env=dict(os.environ, FAKE_CLAUDE_MODE=mode, **(environment or {})), timeout=timeout)
    written = list(records.glob("*.txt")) if records.is_dir() else []
    record = written[0].read_text() if written else ""
    return completed, record


def test_a_session_that_finds_itself_passes():
    completed, record = run_check("hook")
    check(completed.returncode == 0 and "VERDICT: PASSED" in record
          and "FAIL" not in record
          and sum(line.startswith("PASS ") for line in record.splitlines()) == 5,
          "a session that runs the scratch clone's hook, and whose hook wrote its own "
          "work-snapshot, passes, and the record says so",
          completed.stdout + completed.stderr)
    check("record: " in completed.stdout, "the run prints the record's citation", completed.stdout)
    seen = json.loads(FAKE_CLAUDE_ARGUMENTS_FILE.read_text())
    arguments = seen["arguments"]
    check(arguments[:2] == ["-p", weekly_owner_check.LIVE_CHECK_PROMPT]
          and arguments[arguments.index("--model") + 1] == "haiku"
          and arguments[arguments.index("--allowedTools") + 1] == "Bash"
          and "--no-session-persistence" in arguments,
          "claude runs print mode on Haiku with Bash allowed and no saved session", arguments)
    entries = seen["settings"]["hooks"]["PostToolUse"]
    hook_relative = str(weekly_owner_check.HOOK_RELATIVE)
    check(len(entries) == 1 and entries[0]["matcher"] == "Bash"
          and entries[0]["hooks"][0]["command"].endswith(f"{seen['clone']}/{hook_relative}"),
          "the settings register the scratch clone's hook after each Bash call", entries)


def test_failures_are_recorded():
    cases = [
        ("login-lapsed", "claude exited 1: Invalid API key · Please run /login",
         "a lapsed login fails the check with claude's own words"),
        ("error-result", "claude's result is an error: API Error: Connection error.",
         "an error result, as when the network is down, fails the check"),
        ("no-json", "claude printed no JSON result: not json",
         "output that is not JSON fails the check"),
        ("no-snapshot", "the hook wrote 0 work-snapshots, not 1",
         "a session whose hook wrote no work-snapshot fails the check"),
        ("no-file", "FAIL the work-snapshot holds live-check.txt",
         "a work-snapshot without the file the session wrote fails the check"),
        ("other-owner", "FAIL its owner key names process",
         "a work-snapshot owned by another process than the session fails the check"),
        ("wrong-session", "FAIL its transcript trailer",
         "a work-snapshot naming another session's transcript fails the check"),
    ]
    for mode, expected, name in cases:
        completed, record = run_check(mode)
        check(completed.returncode == 1 and expected in record and "VERDICT: FAILED" in record,
              name, f"exit {completed.returncode}: {record or completed.stderr}")


def process_is_running(process_id, wait_seconds=5):
    """False once the process is gone or a zombie; an orphan's reaping can take a moment."""
    deadline = time.monotonic() + wait_seconds
    while True:
        state = subprocess.run(["ps", "-o", "stat=", "-p", str(process_id)],
                               capture_output=True, text=True)
        if state.returncode != 0 or state.stdout.strip().startswith("Z"):
            return False
        if time.monotonic() > deadline:
            return True
        time.sleep(0.1)


def test_claude_that_cannot_start_or_finish_fails():
    completed, record = run_check("pass", claude_program=SCRATCH / "no-such-claude")
    check(completed.returncode == 1 and "could not be started" in record,
          "a claude program that cannot be started fails the check", record or completed.stderr)
    try:
        completed, record = run_check("hang", "--timeout-seconds", "1", timeout=30)
    except subprocess.TimeoutExpired:
        completed, record = None, "the check itself did not finish within 30 s"
    still_running = [process_id for process_id in (
        int(FAKE_CLAUDE_PROCESS_ID_FILE.read_text()),
        int(FAKE_CLAUDE_CHILD_PROCESS_ID_FILE.read_text())) if process_is_running(process_id)]
    for process_id in still_running:
        os.kill(process_id, signal.SIGKILL)
    check(completed is not None and completed.returncode == 1
          and "did not finish within 1.0 s" in record and not still_running,
          "a claude that does not finish in time is killed with its child process "
          "and fails the check",
          f"still running: {still_running}; {record or (completed and completed.stderr)}")


def test_the_record_goes_to_the_log_store_by_default():
    mark = weekly_owner_check.mark
    real = mark.this_machine_is_ned_box, mark.run_on_ned_box_or_here
    now = datetime(2026, 10, 12, 18, 0, tzinfo=timezone.utc)
    store = f"/home/nedlern/nedschorus-logs/{weekly_owner_check.RECORDS_KIND_DIRECTORY_NAME}"
    try:
        for on_ned_box, machine, ssh_target in ((True, "ned-box", None),
                                                (False, "mac", "nedlern@ned-box")):
            calls = []
            mark.this_machine_is_ned_box = lambda on_ned_box=on_ned_box: on_ned_box
            mark.run_on_ned_box_or_here = (
                lambda command, target, timeout, stdin_text=None:
                calls.append((command, target, stdin_text)))
            citation = weekly_owner_check.write_record("the record\n", None, now)
            path = f"{store}/{machine}/2026-10-12.txt"
            check(citation == f"nedlern@ned-box:{path}" and len(calls) == 1
                  and calls[0][1] == ssh_target and calls[0][2] == "the record\n"
                  and calls[0][0].endswith(f"cat > {path}"),
                  f"on {machine} the record goes to the log-store's {machine} directory"
                  + (" over ssh" if ssh_target else " on this machine"), f"{citation} {calls}")
    finally:
        mark.this_machine_is_ned_box, mark.run_on_ned_box_or_here = real


def test_a_scratch_clone_that_cannot_be_made_fails():
    broken = SCRATCH / "broken-gitconfig"
    broken.write_text("[unclosed\n")
    no_git = SCRATCH / "a-path-without-git"
    no_git.mkdir()
    for program in ("mkdir", "cat"):  # the record is still written through these
        (no_git / program).symlink_to(shutil.which(program))
    cases = [
        ({"GIT_CONFIG_GLOBAL": str(broken)}, "RuntimeError: git",
         "a scratch clone git cannot make fails the check, naming git's error"),
        ({"PATH": str(no_git)}, "FileNotFoundError",
         "a scratch clone that cannot be made because git cannot be started fails the "
         "check as a scratch clone failure, not as claude failing to start"),
    ]
    for environment, error, name in cases:
        completed, record = run_check("pass", environment=environment)
        check(completed.returncode == 1
              and f"FAIL the scratch clone could not be made: {error}" in record,
              name, record or completed.stderr)


def test_a_check_that_cannot_run_fails():
    completed, record = run_check("breaks-clone")
    check(completed.returncode == 1 and "FAIL the check could not run: " in record,
          "a scratch clone broken while claude runs fails the check, naming the error",
          record or completed.stderr)


def test_a_record_that_cannot_be_written_is_reported():
    blocker = SCRATCH / "a-file-not-a-directory"
    blocker.write_text("")
    completed = subprocess.run(
        [sys.executable, str(CHECK), "--claude-program", str(FAKE_CLAUDE),
         "--record-directory", str(blocker / "records")],
        capture_output=True, text=True, env=dict(os.environ, FAKE_CLAUDE_MODE="pass"),
        timeout=120)
    check(completed.returncode == 2 and "the record was not written" in completed.stderr
          and "VERDICT: PASSED" in completed.stdout,
          "a record that cannot be written exits 2, says so, and still prints the record",
          completed.stdout + completed.stderr)


def main():
    try:
        for case in (test_a_session_that_finds_itself_passes, test_failures_are_recorded,
                     test_claude_that_cannot_start_or_finish_fails,
                     test_the_record_goes_to_the_log_store_by_default,
                     test_a_scratch_clone_that_cannot_be_made_fails,
                     test_a_check_that_cannot_run_fails,
                     test_a_record_that_cannot_be_written_is_reported):
            try:
                case()
            except Exception as error:
                check(False, f"{case.__name__} raised", f"{type(error).__name__}: {error}")
    finally:
        shutil.rmtree(SCRATCH, ignore_errors=True)
    if failures:
        print(f"{len(failures)} case(s) failed")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
