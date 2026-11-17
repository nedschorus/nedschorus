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

        PP = program.PROGRAM_PATH
        start_rerun = f"python3 {PP} start --words stop"

        def reads_in_order(*answers):
            calls = []

            def read(f):
                calls.append(f)
                answer = answers[len(calls) - 1] if len(calls) <= len(answers) else None
                return answer(f) if answer else _real_read_state(f)
            return read

        def run_start_with_reads(target, read_state):
            program.common.read_state = read_state
            program.now_utc = lambda: datetime(2026, 11, 14, 12, 0, 0, tzinfo=timezone.utc)
            try:
                return run(target, "start", "--words", "stop")
            finally:
                program.common.read_state = _real_read_state
                program.now_utc = _real_now_utc

        def both_tries_failed(holds, clause):
            return ("FAILED: start wrote its emergency stop and read the emergency-stop folder back, twice, and "
                    "neither time found its stop in force, so it deleted the stop files it wrote. A read of the "
                    f"folder now finds that {holds}. {clause}\nTell the user this whole message.\n"
                    f"Run start again only if the user says to: {start_rerun}\n")

        def failed_write(command, target, holds, clause, last_line, error="[Errno 28] No space left on device"):
            return (f"FAILED: {command} could not finish writing to the emergency-stop folder {target}: {error}. "
                    f"A read of the folder now finds that {holds}. {clause}\nTell the user this whole message.\n"
                    f"{last_line}\n")

        not_refused = "So no emergency stop is in force, and pushes and merges are not refused."
        refused = "So an emergency stop counts as in force, and pushes and merges are refused."

        written_but_lifted = root / "read-back" / "emergency-stop"
        written_but_lifted.parent.mkdir()
        status, out = run_start_with_reads(written_but_lifted, lambda f: (
            common.NoStop(f) if not f.exists() or not any(f.iterdir())
            else common.Lifted(f / "2099-01-01T00-00-00Z.md", "#emergency_stop_lifted x")))
        check("start whose stop is twice not the one in force when read back: deletes both stop files it wrote, "
              "and FAILED saying what the folder now holds",
              status == 1 and out == both_tries_failed(f"no emergency-stop file in {written_but_lifted} is in force",
                                                        not_refused)
              and list(written_but_lifted.iterdir()) == [], (out, list(written_but_lifted.iterdir())))

        first_read_back_fails = root / "read-back-once" / "emergency-stop"
        first_read_back_fails.parent.mkdir()
        status, out = run_start_with_reads(first_read_back_fails, reads_in_order(common.NoStop, common.NoStop))
        own_file = first_read_back_fails / "2026-11-14T12-00-00Z.md"
        own_state = common.read_state(first_read_back_fails)
        check("start whose first read-back fails and whose second try appends to the first try's file: "
              "keeps that file, which is in force",
              status == 0 and out == f"added to the emergency stop in force, {own_file}\n"
              and isinstance(own_state, common.InForce) and own_state.path == own_file
              and "words added by prime-intellect: stop" in own_state.text, (out, own_state))

        read_back_unreadable = root / "read-back-unreadable" / "emergency-stop"
        read_back_unreadable.parent.mkdir()
        old_lifted = read_back_unreadable / "2099-01-01T00-00-00Z.md"
        unreadable_answer = lambda f: common.Unreadable(old_lifted, "bad bytes")
        status, out = run_start_with_reads(read_back_unreadable, reads_in_order(
            common.NoStop, lambda f: common.Lifted(old_lifted, "#emergency_stop_lifted x"), common.NoStop,
            unreadable_answer, unreadable_answer))
        check("start whose second read-back finds an unreadable file: deletes its stop file, FAILED, "
              "and says pushes are refused",
              status == 1 and out == both_tries_failed(
                  f"the newest emergency-stop file, {old_lifted}, cannot be read: bad bytes", refused)
              and list(read_back_unreadable.iterdir()) == [], (out, list(read_back_unreadable.iterdir())))

        second_try_unreadable = root / "second-try-unreadable" / "emergency-stop"
        second_try_unreadable.parent.mkdir()
        newer_unreadable = second_try_unreadable / "2099-01-01T00-00-00Z.md"
        status, out = run_start_with_reads(second_try_unreadable, reads_in_order(
            common.NoStop, lambda f: common.Lifted(newer_unreadable, "#emergency_stop_lifted x"),
            lambda f: common.Unreadable(newer_unreadable, "bad bytes")))
        check("start whose second try finds the newest file unreadable: deletes the first try's stop file, "
              "and FAILED saying it wrote no emergency-stop file",
              status == 1 and out == (
                  f"FAILED: start wrote no emergency-stop file: the newest emergency-stop file, {newer_unreadable}, "
                  "cannot be read: bad bytes. That unreadable file already counts as an emergency stop in force, so "
                  "pushes and merges stay refused; writing a newer emergency-stop file would hide the unreadable "
                  "one.\nTell the user the file's path and this error, and leave the file as it is: only the user "
                  "repairs or moves it.\n")
              and list(second_try_unreadable.iterdir()) == [], (out, list(second_try_unreadable.iterdir())))

        mount = root / "mount-lost"
        lost_folder = mount / "emergency-stop"
        mount.mkdir()
        moved_mount = root / "mount-lost-moved"

        def mount_lost(f):
            mount.rename(moved_mount)
            return _real_read_state(f)

        status, out = run_start_with_reads(lost_folder, reads_in_order(common.NoStop, mount_lost))
        lost_file = lost_folder / "2026-11-14T12-00-00Z.md"
        check("start whose folder becomes unreachable after its first write: the delete fails, so FAILED says "
              "the write could not finish, not that the stop files were deleted",
              status == 1 and out == failed_write(
                  "start", lost_folder, f"the folder {lost_folder} cannot be reached: {mount} does not exist or "
                  "cannot be reached", "So no one on this machine can tell whether an emergency stop is in force, "
                  "and pushes and merges are not refused here.",
                  f"Run this command again only if the user says to: {start_rerun}",
                  error=f"[Errno 2] No such file or directory: '{lost_file}'")
              and (moved_mount / "emergency-stop" / lost_file.name).exists(), out)

        same_second_other = root / "read-back-same-second" / "emergency-stop"
        same_second_other.mkdir(parents=True)
        others_file = same_second_other / "2026-11-14T12-00-00Z.md"
        others_file.write_text("# another agent-seat's stop\n")
        lifted_answer = lambda f: common.Lifted(others_file, "#emergency_stop_lifted x")
        status, out = run_start_with_reads(same_second_other, reads_in_order(
            common.NoStop, lifted_answer, common.NoStop, lifted_answer))
        check("start that only appended to another agent-seat's stop file, both tries failing: that file is kept",
              status == 1 and out == both_tries_failed(f"the emergency-stop file in force is {others_file}", refused)
              and sorted(p.name for p in same_second_other.iterdir()) == [others_file.name], out)

        another_in_force = root / "read-back-another" / "emergency-stop"
        another_in_force.mkdir(parents=True)
        other_file = another_in_force / "2099-01-01T00-00-00Z.md"
        other_file.write_text("# someone else's stop\n")
        status, out = run_start_with_reads(another_in_force, reads_in_order(common.NoStop))
        check("start whose first read-back finds another stop in force and whose second try adds to it: "
              "deletes the first try's stop file",
              status == 0 and out == f"added to the emergency stop in force, {other_file}\n"
              and sorted(p.name for p in another_in_force.iterdir()) == [other_file.name]
              and "words added by prime-intellect: stop" in other_file.read_text(), out)

        no_seat_message = ("FAILED: start wrote nothing: no agent-seat is known, because GIT_AUTHOR_NAME is unset or "
                           "empty.\nRun this command, with your agent-seat's name in place of <your agent-seat "
                           f"name>:\npython3 {PP} --as-agent-seat <your agent-seat name> start --words 'again now'\n")
        status, out = run(folder, "start", "--words", "again now", agent_seat=None)
        check("no agent-seat known: FAILED, printing the command to run with a name placeholder",
              status == 1 and out == no_seat_message, out)
        status, out = run(folder, "--as-agent-seat", "", "start", "--words", "again now", agent_seat=None)
        check("empty --as-agent-seat: FAILED, and the command printed carries the option once",
              status == 1 and out == no_seat_message, out)

        unreachable_for_lift = root / "gone-for-lift" / "emergency-stop"
        unreachable_error = common.read_state(unreachable_for_lift).error
        status, out = run(unreachable_for_lift, "lift", "--words", "all clear")
        check("lift with unreachable folder: FAILED, the folder holds what it held, add a task to run it again",
              status == 1 and out == (
                  f"FAILED: the emergency-stop folder {unreachable_for_lift} cannot be reached: {unreachable_error}; "
                  "nothing was written, so the folder holds what it held before. While this machine cannot reach "
                  "the folder, its emergency-stop hook refuses no pushes or merges here.\nAdd a task to run this "
                  f"command again once this machine can reach that folder: python3 {PP} lift --words 'all clear'\n"
                  "Tell the user now that this machine cannot reach that folder.\n"), out)

        failing_lift = root / "lift-write-fails" / "emergency-stop"
        failing_lift.parent.mkdir()
        program.start(failing_lift, "md-skills", "words", "stop", program.SCHEDULED_JOBS_FILE,
                      datetime(2026, 11, 14, 12, 0, 0, tzinfo=timezone.utc))
        real_append = program.append

        def append_that_fails(_path, _line):
            raise OSError(28, "No space left on device")

        program.append = append_that_fails
        try:
            status, out = run(failing_lift, "--as-agent-seat", "md-skills", "lift", "--words", "all clear")
        finally:
            program.append = real_append
        check("lift whose write fails: FAILED, says the stop is still in force and pushes are refused",
              status == 1 and out == failed_write(
                  "lift", failing_lift,
                  f"the emergency-stop file in force is {failing_lift / '2026-11-14T12-00-00Z.md'}",
                  refused, "Add a task to run this command again once a write to that folder can succeed: "
                  f"python3 {PP} --as-agent-seat md-skills lift --words 'all clear'"), out)

        program.append = append_that_fails
        program.common.read_state = reads_in_order(None, lambda f: common.FolderUnreachable(f, "mount gone"))
        try:
            status, out = run(failing_lift, "push-notification", "sent")
        finally:
            program.append = real_append
            program.common.read_state = _real_read_state
        check("push-notification whose write fails and whose folder is then unreachable: FAILED, "
              "says no one here can tell whether a stop is in force",
              status == 1 and out == failed_write(
                  "push-notification", failing_lift, f"the folder {failing_lift} cannot be reached: mount gone",
                  "So no one on this machine can tell whether an emergency stop is in force, and pushes and merges "
                  "are not refused here.", "Add a task to run this command again once a write to that folder can "
                  f"succeed: python3 {PP} push-notification sent"), out)

        unreachable = root / "gone" / "emergency-stop"
        unreachable_error = common.read_state(unreachable).error
        status, out = run(unreachable, "start", "--words", "stop")
        check("start with unreachable folder: FAILED, no retry, and says no stop was started", status == 1
              and out == (f"FAILED: start wrote nothing: the emergency-stop folder {unreachable} cannot be reached: "
                          f"{unreachable_error}. No emergency stop was started. This machine cannot tell whether "
                          "another emergency stop is in force, so its emergency-stop hook refuses no pushes or merges "
                          "here.\nTell the user at once that the emergency stop was not started, and why.\nRun this "
                          f"command again only if the user says to: {start_rerun}\n"), out)

        if os.geteuid() != 0:
            blocked = root / "blocked"
            blocked.mkdir()
            (blocked / "emergency-stop").mkdir()
            (blocked / "emergency-stop").chmod(0o500)
            try:
                status, out = run(blocked / "emergency-stop", "start", "--words", "stop")
                # The temporary file's name is random, so the text is checked on each side of it.
                check("stop file cannot be written: FAILED, saying no stop is in force, to run start only on the "
                      "user's word", status == 1 and out.startswith(
                          "FAILED: start could not finish writing to the emergency-stop folder "
                          f"{blocked / 'emergency-stop'}: "
                          f"[Errno 13] Permission denied: '{blocked / 'emergency-stop'}/.") and out.endswith(
                          ".partial'. A read of the folder now finds that no emergency-stop file in "
                          f"{blocked / 'emergency-stop'} is in force. {not_refused}\nTell the user this whole "
                          f"message.\nRun this command again only if the user says to: {start_rerun}\n"), out)
            finally:
                (blocked / "emergency-stop").chmod(0o755)

        broken_folder = root / "write-fails" / "emergency-stop"
        broken_folder.mkdir(parents=True)
        lifted_before = broken_folder / "2026-01-01T00-00-00Z.md"
        lifted_before.write_text("started\n#emergency_stop_lifted all clear\n")
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
        check("a write that fails part-way: FAILED saying the newest file is lifted, and no stop file or temporary "
              "file is left", status == 1 and out == failed_write(
                  "start", broken_folder, f"the newest emergency-stop file, {lifted_before}, is lifted", not_refused,
                  f"Run this command again only if the user says to: {start_rerun}")
              and sorted(p.name for p in broken_folder.iterdir()) == [lifted_before.name],
              (out, list(broken_folder.iterdir())))

        unreadable_folder = root / "unreadable" / "emergency-stop"
        unreadable_folder.mkdir(parents=True)
        unreadable_file = unreadable_folder / "2029-01-01T00-00-00Z.md"
        unreadable_file.write_bytes(b"\xff\xfe not utf-8")
        unreadable_error = common.read_state(unreadable_folder).error
        status, out = run(unreadable_folder, "start", "--words", "stop")
        check("start while the newest stop file is unreadable: FAILED, and no new stop file hides it",
              status == 1 and out == (
                  f"FAILED: start wrote no emergency-stop file: the newest emergency-stop file, {unreadable_file}, "
                  f"cannot be read: {unreadable_error}. That unreadable file already counts as an emergency stop in "
                  "force, so pushes and merges stay refused; writing a newer emergency-stop file would hide the "
                  "unreadable one.\nTell the user the file's path and this error, and leave the file as it is: only "
                  "the user repairs or moves it.\n")
              and sorted(p.name for p in unreadable_folder.iterdir()) == [unreadable_file.name], out)

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
