#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/claude-code-temp-folders-of-exited-agent-sessions-delete.py.

Each case builds scratch temp parents, a scratch sessions directory and a scratch process table
in a temporary directory, never the real /tmp, ~/.claude/sessions or /proc, and runs the program
on them.

Run: python3 nc-systems/general-tools/tests/claude-code-temp-folders-of-exited-agent-sessions-delete-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PROGRAM = (Path(__file__).resolve().parents[1]
           / "claude-code-temp-folders-of-exited-agent-sessions-delete.py")
_specification = importlib.util.spec_from_file_location(
    "claude_code_temp_folders_of_exited_agent_sessions_delete", PROGRAM)
program = importlib.util.module_from_spec(_specification)
_specification.loader.exec_module(program)

ROOT_NAME = f"claude-{os.getuid()}"
LIVE = "11111111-1111-1111-1111-111111111111"
DEAD = "22222222-2222-2222-2222-222222222222"
REUSED = "33333333-3333-3333-3333-333333333333"
OTHER = "44444444-4444-4444-4444-444444444444"
LIVE_PID, DEAD_PID, REUSED_PID = 4101, 4102, 4103
START_TIME = "777"
DAY_AGO = time.time() - 86400

failures = []


def check(name, condition, detail=""):
    print(("ok   " if condition else "FAIL ") + name + ("" if condition else f": {detail}"))
    if not condition:
        failures.append(name)


class Scene:
    """A scratch machine: two temp parents, a sessions directory and a process table."""

    def __init__(self, base: Path):
        self.base = base
        self.parents = [base / "tmp", base / "claude-code-tmp"]
        self.sessions = base / "sessions"
        self.proc = base / "proc"
        self.sessions.mkdir()
        self.proc.mkdir()

    def session(self, pid, session_id, start_time=START_TIME, running=True,
                running_start_time=START_TIME):
        (self.sessions / f"{pid}.json").write_text(json.dumps(
            {"pid": pid, "sessionId": session_id, "procStart": start_time}), encoding="utf-8")
        if running:
            (self.proc / str(pid)).mkdir()
            # The command may hold spaces and parentheses; the program reads after the last ")".
            fields = ["S"] + ["0"] * 18 + [running_start_time] + ["0"] * 5
            (self.proc / str(pid) / "stat").write_text(
                f"{pid} (claude (x) y) " + " ".join(fields) + "\n")

    def folder(self, parent_index, session_id, project="-home-nedlern-agents-seat", old=True):
        folder = self.parents[parent_index] / ROOT_NAME / project / session_id
        (folder / "tasks").mkdir(parents=True)
        (folder / "tasks" / "b1.output").write_text("output\n")
        (folder / "scratchpad").mkdir()
        if old:
            for path in (folder / "tasks", folder / "scratchpad", folder):
                os.utime(path, (DAY_AGO, DAY_AGO))
        return folder

    def run(self, *extra, minimum_age="3600", parents=None):
        arguments = [sys.executable, str(PROGRAM), "--sessions-directory", str(self.sessions),
                     "--proc-directory", str(self.proc), "--minimum-age-seconds", minimum_age]
        for parent in (self.parents if parents is None else parents):
            arguments += ["--temp-parent", str(parent)]
        return subprocess.run(arguments + list(extra), capture_output=True, text=True, timeout=60)


def scene():
    return Scene(Path(tempfile.mkdtemp(prefix="claude-code-temp-folders-delete-test-", dir=WORKSPACE)))


def run_selection_cases():
    s = scene()
    s.session(LIVE_PID, LIVE)
    s.session(DEAD_PID, DEAD, running=False)
    s.session(REUSED_PID, REUSED, running_start_time="999")
    live = s.folder(0, LIVE)
    dead = s.folder(0, DEAD)
    reused = s.folder(1, REUSED)
    unclaimed = s.folder(1, OTHER, project="-home-nedlern-agents-other")
    recent = s.folder(0, "55555555-5555-5555-5555-555555555555", project="-home-nedlern-agents-other", old=False)
    hand_made = s.parents[0] / ROOT_NAME / "-home-nedlern-agents-seat" / "store-walk"
    hand_made.mkdir()
    loose_file = s.parents[0] / ROOT_NAME / f"cache-break-state-{DEAD}.json"
    loose_file.write_text("{}")
    (s.sessions / "notes.txt").write_text("not a sessions file")

    dry = s.run("--dry-run")
    check("a dry run exits 0", dry.returncode == 0, dry.stderr)
    check("a dry run names each folder it would delete, and deletes none",
          f"would delete {dead}" in dry.stdout and dead.is_dir() and reused.is_dir(), dry.stdout)

    real = s.run()
    check("a real run exits 0 with no failure", real.returncode == 0 and real.stderr == "",
          real.stdout + real.stderr)
    check("the folder of a live agent-session is kept", live.is_dir())
    check("the folder of an agent-session whose pid is gone is deleted, and named first",
          not dead.exists() and f"deleting {dead}" in real.stdout, real.stdout)
    check("the folder of an agent-session whose pid now runs another process is deleted",
          not reused.exists())
    check("a folder no sessions file names is deleted, under the second temp parent too",
          not unclaimed.exists())
    check("a folder changed within the minimum age is kept", recent.is_dir())
    check("a folder whose name is not a session id is kept", hand_made.is_dir())
    check("a file directly under claude-<uid> is kept", loose_file.is_file())
    check("a project folder the run emptied is removed",
          not (s.parents[1] / ROOT_NAME / "-home-nedlern-agents-other").exists())
    check("a project folder still holding something is kept",
          (s.parents[0] / ROOT_NAME / "-home-nedlern-agents-other").is_dir())
    check("the summary counts what was deleted and kept",
          "deleted 3 folders of exited agent-sessions; kept 1 of live agent-sessions and 1 changed "
          "within 3600 seconds; 0 failures" in real.stdout, real.stdout)


def run_absent_inputs_cases():
    s = scene()
    shutil.rmtree(s.sessions)
    dead = s.folder(0, DEAD)
    absent_parent = s.base / "no-such-parent"
    result = s.run(parents=[s.parents[0], absent_parent])
    check("a temp parent with no claude-<uid> folder is not a failure",
          result.returncode == 0 and result.stderr == "", result.stderr)
    check("with no sessions directory no agent-session is live, so folders are deleted",
          not dead.exists())

    s = scene()
    (s.sessions / f"{DEAD_PID}.json").symlink_to(s.base / "gone.json")
    dead = s.folder(0, DEAD)
    result = s.run()
    check("a sessions file gone between the listing and its read is skipped, not a failure",
          result.returncode == 0 and not dead.exists(), result.stderr)


def expect_nothing_deleted(name, s, folder, expected_text):
    result = s.run()
    check(name + ": exits 1", result.returncode == 1, result.stdout + result.stderr)
    check(name + ": nothing is deleted", folder.is_dir())
    check(name + ": stderr says what failed and that nothing was deleted",
          "nothing was deleted: " in result.stderr and expected_text in result.stderr, result.stderr)
    check(name + ": stderr says what to do", program.FAILURES_INSTRUCTION in result.stderr,
          result.stderr)


def run_live_set_failure_cases():
    s = scene()
    shutil.rmtree(s.sessions)
    s.sessions.write_text("a file where the directory should be")
    expect_nothing_deleted("the sessions directory cannot be listed", s, s.folder(0, DEAD),
                           f"the sessions directory {s.sessions} could not be listed")

    s = scene()
    (s.sessions / "4200.json").write_text("{not json")
    expect_nothing_deleted("a sessions file is not JSON", s, s.folder(0, DEAD),
                           f"the sessions file {s.sessions / '4200.json'} could not be read")

    s = scene()
    (s.sessions / "4201.json").write_text(json.dumps({"pid": 4201, "sessionId": LIVE}))
    expect_nothing_deleted("a sessions file lacks procStart", s, s.folder(0, DEAD),
                           "KeyError")

    s = scene()
    s.session(LIVE_PID, LIVE, running=False)
    (s.proc / str(LIVE_PID) / "stat").mkdir(parents=True)
    expect_nothing_deleted("a running pid's start time cannot be read", s, s.folder(0, DEAD),
                           f"the start time of pid {LIVE_PID}")


def run_per_folder_failure_cases():
    s = scene()
    root = s.parents[0] / ROOT_NAME
    root.parent.mkdir(parents=True)
    root.write_text("a file where claude-<uid> should be")
    dead = s.folder(1, DEAD)
    result = s.run()
    check("a claude-<uid> that cannot be listed is a failure, exit 1",
          result.returncode == 1 and f"{root} could not be listed" in result.stderr, result.stderr)
    check("a claude-<uid> that cannot be listed does not stop the other temp parent",
          not dead.exists())

    s = scene()
    blocked = s.folder(0, DEAD, project="-blocked")
    other = s.folder(0, OTHER)
    project = blocked.parent
    project.chmod(0o000)
    try:
        result = s.run()
    finally:
        project.chmod(0o755)
    check("a project folder that cannot be listed is a failure, exit 1",
          result.returncode == 1 and f"{project} could not be listed" in result.stderr, result.stderr)
    check("a project folder that cannot be listed keeps its folders and does not stop the others",
          blocked.is_dir() and not other.exists())

    s = scene()
    stuck = s.folder(0, DEAD)
    (stuck / "tasks").chmod(0o555)
    other = s.folder(0, OTHER, project="-home-nedlern-agents-other")
    try:
        result = s.run()
    finally:
        (stuck / "tasks").chmod(0o755)
    check("a folder that cannot be deleted in full is a failure naming the system's error, exit 1",
          result.returncode == 1 and f"{stuck} could not be read or deleted in full: " in result.stderr
          and "Permission denied" in result.stderr, result.stderr)
    check("a folder that cannot be deleted does not stop the others", not other.exists())
    check("a failure to delete says what to do", program.FAILURES_INSTRUCTION in result.stderr)
    check("a project folder still holding a folder that could not be deleted is kept",
          stuck.parent.is_dir())

    s = scene()
    dead = s.folder(0, DEAD)
    root = dead.parent.parent
    root.chmod(0o555)
    try:
        result = s.run()
    finally:
        root.chmod(0o755)
    check("an emptied project folder that cannot be removed is a failure, exit 1",
          result.returncode == 1 and not dead.exists()
          and f"the emptied folder {dead.parent} could not be removed" in result.stderr,
          result.stderr)


def run_recheck_cases():
    s = scene()
    s.session(LIVE_PID, LIVE)
    first = s.folder(0, DEAD)
    second = s.folder(0, OTHER)
    calls = []

    def session_starts_during_the_run():
        # The first folder's age is read after the live set; a session for it starts then.
        if not calls:
            s.session(DEAD_PID, DEAD)
        calls.append(1)
        return time.time()

    result = program.delete_folders_of_exited_sessions(
        [str(s.parents[0])], s.sessions, s.proc, 3600, False, now=session_starts_during_the_run)
    check("a session that starts during the run keeps its folder",
          first.is_dir() and not second.exists() and result["kept_live"] == 1, str(result))

    s = scene()
    first = s.folder(0, DEAD)
    calls = []

    def sessions_file_breaks_during_the_run():
        (s.sessions / "4300.json").write_text("{not json")
        return time.time()

    result = program.delete_folders_of_exited_sessions(
        [str(s.parents[0])], s.sessions, s.proc, 3600, False, now=sessions_file_breaks_during_the_run)
    check("a live set unreadable at the recheck keeps the folder and is a failure",
          first.is_dir() and len(result["failures"]) == 1
          and result["failures"][0].startswith(f"{first} was kept: the sessions file"),
          str(result))


WORKSPACE = tempfile.mkdtemp(prefix="claude-code-temp-folders-delete-test-workspace-")
try:
    run_selection_cases()
    run_absent_inputs_cases()
    run_live_set_failure_cases()
    run_per_folder_failure_cases()
    run_recheck_cases()
finally:
    for directory, subdirectories, _ in os.walk(WORKSPACE):
        for name in subdirectories:
            os.chmod(os.path.join(directory, name), 0o755)
    shutil.rmtree(WORKSPACE, ignore_errors=True)

print(f"{len(failures)} failures" if failures else "all cases passed")
sys.exit(1 if failures else 0)
