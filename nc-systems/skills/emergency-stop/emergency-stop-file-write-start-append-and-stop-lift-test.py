#!/usr/bin/env python3
"""Tests for emergency-stop-file-write-start-append-and-stop-lift.py: starting a stop,
adding to the one in force, naming a coordinating agent-seat, recording the
push notification, handing the lift over, lifting, and each FAILED path.

Every case drives run() in-process with NEDSCHORUS_EMERGENCY_STOP_FOLDER set to
a temporary folder; one runs the file as a subprocess. None touches the
log-store. Run: python3 nc-systems/skills/emergency-stop/emergency-stop-file-write-start-append-and-stop-lift-test.py
Prints one line per case and exits non-zero if any case fails."""

import contextlib
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PROGRAM = Path(__file__).with_name("emergency-stop-file-write-start-append-and-stop-lift.py")
_spec = importlib.util.spec_from_file_location("emergency_stop_file_start_append_and_lift", PROGRAM)
program = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(program)
common = program.common

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def run(folder, *arguments, agent_seat="prime-intellect"):
    environment = {"NEDSCHORUS_EMERGENCY_STOP_FOLDER": str(folder)}
    if agent_seat:
        environment["GIT_AUTHOR_NAME"] = agent_seat
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        status = program.run(list(arguments), environment)
    return status, out.getvalue()


def main():
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        folder = root / "emergency-stop"

        status, out = run(folder, "lift", "--words", "lift it")
        check("lift with no stop: FAILED, exit 1", status == 1 and out.startswith("FAILED"), out)

        status, out = run(folder, "start", "--words", "stop everyone")
        state = common.read_state(folder)
        check("start creates a stop file in force", status == 0 and isinstance(state, common.InForce), (status, out))
        text = state.text
        check("new file names the starter as coordinating agent-seat",
              common.coordinating_agent_seat(text) == "prime-intellect", text)
        check("new file names the repair brief beside it", "-repair-brief.md" in text, text)
        check("new file has a pending push notification", "push notification: pending" in text, text)
        check("new file lists the scheduled jobs", "transcript-mirror-to-log-store" in text, text)
        check("new file name is the UTC start time",
              common.STOP_FILE_NAME_PATTERN.fullmatch(state.path.name) is not None, state.path)
        check("start time is written to the second", "." not in text.splitlines()[0], text.splitlines()[0])
        check("new file is readable by every agent-session on the machine",
              (state.path.stat().st_mode & 0o777) == (0o644 & ~_umask()), oct(state.path.stat().st_mode))

        status, out = run(folder, "start", "--evidence", "main is broken", agent_seat="reboot-test")
        files = sorted(p.name for p in folder.iterdir())
        check("second start appends, no new file", status == 0 and len(files) == 1
              and "evidence added by reboot-test: main is broken" in state.path.read_text(), (files, out))

        later = datetime(2029, 6, 1, 12, 0, 1, tzinfo=timezone.utc)
        program.now_utc = lambda: later
        try:
            status, out = run(folder, "start", "--words", "a later second", agent_seat="md-skills")
        finally:
            program.now_utc = _real_now_utc
        files = sorted(p.name for p in folder.iterdir())
        check("start in a later second while a stop is in force: appends to it, no new file",
              status == 0 and out.startswith("added to the emergency stop in force") and len(files) == 1
              and "words added by md-skills: a later second" in state.path.read_text(), (files, out))

        moment = datetime(2030, 1, 1, tzinfo=timezone.utc)
        clash = folder / program.stop_file_name(moment)
        clash.write_text("someone else's file\n")
        reads = []

        def no_stop_then_real(f):
            reads.append(f)
            return common.NoStop(f) if len(reads) == 1 else _real_read_state(f)

        program.common.read_state = no_stop_then_real
        try:
            message = program.start(folder, "md-skills", "words", "same second", program.SCHEDULED_JOBS_FILE, moment)
        finally:
            program.common.read_state = _real_read_state
        check("exclusive create lost at the same second: appends",
              "same second" in message and "words added by md-skills: same second" in clash.read_text(), message)
        clash.unlink()

        status, _ = run(folder, "coordinate", "--agent-seat", "merge-lane-2", "--words", "let merge-lane-2 lead")
        check("coordinate names another agent-seat",
              status == 0 and common.coordinating_agent_seat(state.path.read_text()) == "merge-lane-2")

        status, _ = run(folder, "push-notification", "failed", "--error", "no device")
        check("push notification failure recorded",
              status == 0 and "push notification: failed at" in state.path.read_text())

        status, out = run(folder, "hand-over-lift", "--agent-seat", "merge-lane-2", "--words", "you may lift it")
        check("hand-over-lift does not lift", status == 0 and isinstance(common.read_state(folder), common.InForce)
              and out.startswith("hand-over-lift: written to")
              and "#emergency_stop_lift_handed_over merge-lane-2 you may lift it" in state.path.read_text(), out)

        status, _ = run(folder, "lift", "--words", "all clear")
        lifted = common.read_state(folder)
        check("lift writes the lift line last", status == 0 and isinstance(lifted, common.Lifted)
              and lifted.lift_line == "#emergency_stop_lifted all clear", lifted)

        skewed = root / "clock-skew" / "emergency-stop"
        skewed.parent.mkdir()
        lifted_at = datetime(2026, 11, 14, 12, 0, 10, tzinfo=timezone.utc)
        program.start(skewed, "ned-box-helper", "words", "first", program.SCHEDULED_JOBS_FILE, lifted_at)
        program.append(skewed / program.stop_file_name(lifted_at), "#emergency_stop_lifted all clear")
        behind = datetime(2026, 11, 14, 12, 0, 7, tzinfo=timezone.utc)
        message = program.start(skewed, "mac-claude", "words", "clock behind", program.SCHEDULED_JOBS_FILE, behind)
        skew_state = common.read_state(skewed)
        check("start on a clock behind the lifted newest stop file's: the new stop is named after it and is in force",
              isinstance(skew_state, common.InForce) and skew_state.path.name == "2026-11-14T12-00-11Z.md"
              and message == f"started the emergency stop {skew_state.path}"
              and "words: clock behind" in skew_state.text, (message, skew_state))

        written_but_lifted = root / "read-back" / "emergency-stop"
        written_but_lifted.parent.mkdir()
        program.common.read_state = lambda f: (common.NoStop(f) if not f.exists() or not any(f.iterdir())
                                               else common.Lifted(f / "2099-01-01T00-00-00Z.md", "#emergency_stop_lifted x"))
        program.now_utc = lambda: datetime(2026, 11, 14, 12, 0, 0, tzinfo=timezone.utc)
        try:
            status, out = run(written_but_lifted, "start", "--words", "stop")
        finally:
            program.common.read_state = _real_read_state
            program.now_utc = _real_now_utc
        check("start whose stop is twice not the one in force when read back: FAILED, and says pushes are not refused",
              status == 1 and out.startswith("FAILED") and "neither time found its stop in force" in out
              and "is lifted" in out and "pushes and merges are not refused" in out
              and "Tell the user this whole message" in out, out)

        def reads_in_order(*answers):
            calls = []

            def read(f):
                calls.append(f)
                answer = answers[len(calls) - 1] if len(calls) <= len(answers) else None
                return answer(f) if answer else _real_read_state(f)
            return read

        first_read_back_fails = root / "read-back-once" / "emergency-stop"
        first_read_back_fails.parent.mkdir()
        program.common.read_state = reads_in_order(common.NoStop, common.NoStop)
        program.now_utc = lambda: datetime(2026, 11, 14, 12, 0, 0, tzinfo=timezone.utc)
        try:
            status, out = run(first_read_back_fails, "start", "--words", "stop")
        finally:
            program.common.read_state = _real_read_state
            program.now_utc = _real_now_utc
        check("start whose first read-back fails writes again, and the stop is in force",
              status == 0 and out.startswith("added to the emergency stop in force")
              and isinstance(common.read_state(first_read_back_fails), common.InForce), out)

        read_back_unreadable = root / "read-back-unreadable" / "emergency-stop"
        read_back_unreadable.parent.mkdir()
        old_lifted = read_back_unreadable / "2099-01-01T00-00-00Z.md"
        program.common.read_state = reads_in_order(
            common.NoStop, lambda f: common.Lifted(old_lifted, "#emergency_stop_lifted x"), common.NoStop,
            lambda f: common.Unreadable(old_lifted, "bad bytes"))
        program.now_utc = lambda: datetime(2026, 11, 14, 12, 0, 0, tzinfo=timezone.utc)
        try:
            status, out = run(read_back_unreadable, "start", "--words", "stop")
        finally:
            program.common.read_state = _real_read_state
            program.now_utc = _real_now_utc
        check("start whose second read-back finds an unreadable file: FAILED, and says pushes are refused",
              status == 1 and "cannot be read: bad bytes" in out
              and "so pushes and merges are refused" in out, out)

        status, out = run(folder, "start", "--words", "again", agent_seat=None)
        check("no agent-seat known: FAILED, printing the command to run with a name placeholder", status == 1
              and "GIT_AUTHOR_NAME" in out
              and (f"python3 {program.PROGRAM_PATH} --as-agent-seat <your agent-seat name> start --words again"
                   in out), out)

        unreachable_for_lift = root / "gone-for-lift" / "emergency-stop"
        status, out = run(unreachable_for_lift, "lift", "--words", "all clear")
        check("lift with unreachable folder: FAILED, the stop stays in force, add a task to run it again",
              status == 1 and "nothing was written, so an emergency stop that was in force before is still in force"
              in out and "Add a task to run the same command again" in out, out)

        failing_lift = root / "lift-write-fails" / "emergency-stop"
        failing_lift.parent.mkdir()
        program.start(failing_lift, "md-skills", "words", "stop", program.SCHEDULED_JOBS_FILE,
                      datetime(2026, 11, 14, 12, 0, 0, tzinfo=timezone.utc))
        real_append = program.append

        def append_that_fails(_path, _line):
            raise OSError(28, "No space left on device")

        program.append = append_that_fails
        try:
            status, out = run(failing_lift, "lift", "--words", "all clear")
        finally:
            program.append = real_append
        check("lift whose write fails: FAILED, says the stop is still in force and pushes are refused",
              status == 1 and "No space left" in out and "the emergency-stop file in force is" in out
              and "so pushes and merges are refused" in out and "Add a task" in out, out)

        unreachable = root / "gone" / "emergency-stop"
        status, out = run(unreachable, "start", "--words", "stop")
        check("start with unreachable folder: FAILED, no retry, and says no stop was started", status == 1
              and out.startswith("FAILED: start wrote nothing") and "No emergency stop was started" in out, out)

        if os.geteuid() != 0:
            blocked = root / "blocked"
            blocked.mkdir()
            (blocked / "emergency-stop").mkdir()
            (blocked / "emergency-stop").chmod(0o500)
            try:
                status, out = run(blocked / "emergency-stop", "start", "--words", "stop")
                check("stop file cannot be written: FAILED, saying no stop is in force and to add a task", status == 1
                      and out.startswith("FAILED") and "pushes and merges are not refused" in out
                      and "Tell the user this error" in out and "Add a task" in out, out)
            finally:
                (blocked / "emergency-stop").chmod(0o755)

        broken_folder = root / "write-fails" / "emergency-stop"
        broken_folder.parent.mkdir()
        real_fdopen = program.os.fdopen

        def fdopen_whose_write_fails(descriptor, *arguments, **keywords):
            handle = real_fdopen(descriptor, *arguments, **keywords)
            def write(_text):
                raise OSError(28, "No space left on device")
            handle.write = write
            return handle

        program.os.fdopen = fdopen_whose_write_fails
        try:
            status, out = run(broken_folder, "start", "--words", "stop")
        finally:
            program.os.fdopen = real_fdopen
        check("a write that fails part-way: FAILED, and no stop file or temporary file is left",
              status == 1 and out.startswith("FAILED") and "No space left" in out
              and list(broken_folder.iterdir()) == [], (out, list(broken_folder.iterdir())))

        unreadable_folder = root / "unreadable" / "emergency-stop"
        unreadable_folder.mkdir(parents=True)
        (unreadable_folder / "2029-01-01T00-00-00Z.md").write_bytes(b"\xff\xfe not utf-8")
        status, out = run(unreadable_folder, "start", "--words", "stop")
        check("start while the newest stop file is unreadable: FAILED, and no new stop file hides it",
              status == 1 and out.startswith("FAILED: start wrote nothing") and "only the user" in out
              and sorted(p.name for p in unreadable_folder.iterdir()) == ["2029-01-01T00-00-00Z.md"], out)

        jobs_without_a_program = root / "jobs-without-a-program.json"
        jobs_without_a_program.write_text('{"jobs": [{"name": "nightly"}]}')
        lines = program.scheduled_job_lines(jobs_without_a_program)
        check("a scheduled job with no program field is named as unreadable, not fatal",
              len(lines) == 1 and "could not be read" in lines[0] and "'program'" in lines[0], lines)

        lines = program.scheduled_job_lines(root / "no-such-jobs.json")
        check("unreadable scheduled-jobs list is named, not fatal",
              len(lines) == 1 and "could not be read" in lines[0], lines)

        status, out = run(folder, "status")
        check("status prints the state", status == 0 and out.strip() == "Lifted", out)

        result = subprocess.run([sys.executable, str(PROGRAM), "status"], capture_output=True, text=True,
                                env={**os.environ, "NEDSCHORUS_EMERGENCY_STOP_FOLDER": str(folder)})
        check("runs as a program", result.returncode == 0 and result.stdout.strip() == "Lifted", result)

    print(f"{len(failures)} failure(s)")
    return 1 if failures else 0


_real_read_state = common.read_state
_real_now_utc = program.now_utc


def _umask():
    current = os.umask(0)
    os.umask(current)
    return current

if __name__ == "__main__":
    sys.exit(main())
