#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/claude-code-background-command-output-file-wait-until-no-process-writes-it.py.

The Linux cases run real writer processes and read the real /proc; the cases
for each way the writers cannot be listed use a fake /proc tree or a fake lsof.

Run: python3 nc-systems/general-tools/tests/claude-code-background-command-output-file-wait-until-no-process-writes-it-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PROGRAM = (Path(__file__).resolve().parents[1]
           / "claude-code-background-command-output-file-wait-until-no-process-writes-it.py")
_spec = importlib.util.spec_from_file_location("background_command_wait", PROGRAM)
wait = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wait)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


scratch = tempfile.TemporaryDirectory()
root = Path(scratch.name)
output_file = root / "task.output"
output_file.write_text("")
CHILD_THAT_SLEEPS = "import time; time.sleep(120)"


def writer(source):
    with open(output_file, "a") as handle:
        return subprocess.Popen([sys.executable, "-c", source], stdout=handle, stdin=subprocess.DEVNULL)


def stop(process):
    process.kill()
    process.wait()


def no_sleep(_seconds):
    pass


code, message = wait.wait_until_no_process_writes(str(root / "missing.output"), 60, set)
check("a file that does not exist exits 2, saying so",
      code == wait.EXIT_CANNOT_WAIT and "does not exist" in message, (code, message))

if not os.path.isdir("/proc/self/fd"):
    print("SKIP  the cases on real processes need /proc [this machine cannot run it]")
else:
    linux = wait.linux_processes_writing_file
    with open(output_file) as read_only:
        reader_process = subprocess.Popen([sys.executable, "-c", CHILD_THAT_SLEEPS],
                                          stdin=read_only, stdout=subprocess.DEVNULL)
    try:
        code, message = wait.wait_until_no_process_writes(str(output_file), 60, linux, sleep=no_sleep)
    finally:
        stop(reader_process)
    check("a file that a process holds open only for reading has no writer, and exits 2 rather than "
          "reading as finished", code == wait.EXIT_CANNOT_WAIT and "no process has" in message
          and "hidden from this program" in message, (code, message))

    # The parent writer prints its child's process id and both hold the file open, as a background
    # command's shell and the program it starts do.
    output_file.write_text("")
    parent = writer("import subprocess, sys, time\n"
                    f"child = subprocess.Popen([sys.executable, '-c', {CHILD_THAT_SLEEPS!r}])\n"
                    "print(child.pid, flush=True)\n"
                    "time.sleep(120)\n")
    child_process_id = None
    for _ in range(200):
        text = output_file.read_text().strip()
        if text:
            child_process_id = int(text)
            break
        time.sleep(0.05)
    seen_after_each_sleep = []

    def end_parent_then_child(_seconds):
        if not seen_after_each_sleep:
            stop(parent)
        else:
            # The child was its parent's, so this test cannot reap it; it holds no file once killed.
            os.kill(child_process_id, 9)
            for _ in range(200):
                if child_process_id not in linux(os.path.realpath(output_file)):
                    break
                time.sleep(0.05)
        seen_after_each_sleep.append(linux(os.path.realpath(output_file)))

    try:
        writers_at_start = linux(os.path.realpath(output_file))
        code, message = wait.wait_until_no_process_writes(str(output_file), 60, linux,
                                                          sleep=end_parent_then_child)
    finally:
        if parent.poll() is None:
            stop(parent)
        try:
            os.kill(child_process_id, 9)
        except (OSError, TypeError):
            pass
    check("real processes: both writers are seen at the start, the wait goes on while the child still "
          "writes after its parent exits, and exits 0 once the child exits too",
          writers_at_start == {parent.pid, child_process_id} and code == wait.EXIT_NO_WRITER_LEFT
          and "Finished" in message and seen_after_each_sleep == [{child_process_id}, set()],
          (writers_at_start, parent.pid, child_process_id, seen_after_each_sleep, code, message))

    long_writer = writer(CHILD_THAT_SLEEPS)
    try:
        code, message = wait.wait_until_no_process_writes(str(output_file), 0, linux)
        process = subprocess.run([sys.executable, str(PROGRAM), str(output_file),
                                  "--time-limit-seconds", "0.2"], capture_output=True, text=True)
    finally:
        stop(long_writer)
    check("the time limit running out while a process still writes exits 1, naming the process and "
          "saying to run the same command again",
          code == wait.EXIT_TIME_LIMIT_REACHED and str(long_writer.pid) in message
          and "run the same command again" in message, (code, message))
    check("as a process, the time limit exits 1 and prints its message on standard error",
          process.returncode == wait.EXIT_TIME_LIMIT_REACHED and "Still running" in process.stderr,
          (process.returncode, process.stdout, process.stderr))

def lister_answering(*answers):
    """Return a writer lister giving each answer in turn, raising one that is an exception, and the
    seconds each look was given."""
    given = []
    remaining_answers = iter(answers)

    def list_writers(_path, seconds_left):
        given.append(seconds_left)
        answer = next(remaining_answers)
        if isinstance(answer, Exception):
            raise answer
        return answer
    return list_writers, given


sleeps = []
list_writers, given = lister_answering({7}, {7}, set())
clock_values = iter([100.0, 101.0, 106.0, 107.0, 112.0])
code, message = wait.wait_until_no_process_writes(
    str(output_file), 20, list_writers, clock=lambda: next(clock_values), sleep=sleeps.append)
check("the wait sleeps the poll interval between looks while time remains, and gives each look the time "
      "that remains", code == wait.EXIT_NO_WRITER_LEFT and sleeps == [wait.POLL_SECONDS, wait.POLL_SECONDS]
      and given == [20, 14.0, 8.0], (code, sleeps, given))
sleeps = []
list_writers, given = lister_answering({7}, set())
clock_values = iter([100.0, 105.0])
code, message = wait.wait_until_no_process_writes(
    str(output_file), 10, list_writers, clock=lambda: next(clock_values), sleep=sleeps.append)
check("with no more than one poll interval left, the wait neither sleeps nor looks again, and exits 1 "
      "naming the writers of the last look",
      sleeps == [] and given == [10] and code == wait.EXIT_TIME_LIMIT_REACHED and "process 7 still has" in message,
      (sleeps, given, code, message))
list_writers, given = lister_answering({7}, wait.WritersLookTimeLimitReached("lsof had not listed them"))
clock_values = iter([100.0, 101.0, 107.0])
code, message = wait.wait_until_no_process_writes(
    str(output_file), 10, list_writers, clock=lambda: next(clock_values), sleep=no_sleep)
check("the time limit running out during a later look exits 1, naming the writers of the last look",
      code == wait.EXIT_TIME_LIMIT_REACHED and "process 7 still has" in message and given == [10, 3.0],
      (code, message, given))
list_writers, _ = lister_answering(wait.WritersLookTimeLimitReached("lsof had not listed them"))
code, message = wait.wait_until_no_process_writes(str(output_file), 1, list_writers, sleep=no_sleep)
check("the time limit running out during the first look exits 2, saying to give a longer time limit",
      code == wait.EXIT_CANNOT_WAIT and "lsof had not listed them" in message
      and "longer --time-limit-seconds" in message, (code, message))
list_writers, _ = lister_answering({7}, wait.WritersCannotBeListed("lsof exited 2"))
clock_values = iter([100.0, 101.0, 102.0])
code, message = wait.wait_until_no_process_writes(
    str(output_file), 10, list_writers, clock=lambda: next(clock_values), sleep=no_sleep)
check("writers that cannot be listed at a later look exit 2, saying so",
      code == wait.EXIT_CANNOT_WAIT and "cannot be listed: lsof exited 2" in message, (code, message))

code, message = wait.wait_until_no_process_writes(
    str(output_file), 60, lambda path, _seconds: wait.linux_processes_writing_file(path, proc_root=root / "no-proc"))
check("a /proc that cannot be read exits 2, saying the writers cannot be listed",
      code == wait.EXIT_CANNOT_WAIT and "cannot be listed" in message and "no-proc" in message,
      (code, message))

target = str(root / "fake-target.output")
fake_proc = root / "fake-proc"


def fake_process(process_id, descriptors):
    """Make /proc/<process_id> with fd links and fdinfo files: descriptor -> (link target, flags line)."""
    (fake_proc / process_id / "fd").mkdir(parents=True)
    (fake_proc / process_id / "fdinfo").mkdir()
    for descriptor, (link_target, fdinfo) in descriptors.items():
        os.symlink(link_target, fake_proc / process_id / "fd" / descriptor)
        if fdinfo is not None:
            (fake_proc / process_id / "fdinfo" / descriptor).write_text(fdinfo)


fake_proc.mkdir()
(fake_proc / "sys").mkdir()
(fake_proc / "50").mkdir()
fake_process("51", {"0": ("/elsewhere", "flags:\t0102001\n"), "1": (target, "pos:\t0\nflags:\t0100000\n")})
fake_process("52", {"1": (target, None)})
fake_process("53", {"3": (target, "pos:\t0\nflags:\t0102001\n")})
fake_process("54", {"4": (target, "flags:\t0100002\n")})
# Process 56's descriptor 1, whose fdinfo has vanished, is scanned before its writing descriptor 2.
fake_process("56", {"1": (target, None), "2": (target, "flags:\t0102001\n")})
check("in /proc, writers are the processes holding the file write-only or read-write; a read-only "
      "holder, a link elsewhere, a process with no fd directory, a vanished fdinfo and a name that is "
      "no process id are skipped, and the scan goes on after each",
      wait.linux_processes_writing_file(target, proc_root=fake_proc) == {53, 54, 56},
      wait.linux_processes_writing_file(target, proc_root=fake_proc))
fake_process("55", {"1": (target, "pos:\t0\n")})
try:
    wait.linux_processes_writing_file(target, proc_root=fake_proc)
    raised = None
except wait.WritersCannotBeListed as error:
    raised = str(error)
check("an fdinfo file with no flags line is reported as writers that cannot be listed",
      raised is not None and "no flags line" in raised, raised)


class Completed:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


timeouts = []


def lsof_answering(completed):
    called = []

    def runner(arguments, **options):
        called.append(arguments)
        timeouts.append(options["timeout"])
        if isinstance(completed, Exception):
            raise completed
        return completed
    return runner, called


runner, called = lsof_answering(Completed(0, "p12\nf1\naw\np13\nf3\nar\np14\nf4\nau\n"))
check("lsof: the processes whose access letter is w or u are writers",
      wait.macos_processes_writing_file(target, runner=runner) == {12, 14}
      and called == [["lsof", "-w", "-F", "pa", "--", target]], called)
runner, _ = lsof_answering(Completed(1))
check("lsof exiting 1 with no output means no process has the file open",
      wait.macos_processes_writing_file(target, runner=runner) == set())
for name, completed in [("lsof is not installed", FileNotFoundError("lsof")),
                        ("lsof times out", subprocess.TimeoutExpired("lsof", 30)),
                        ("lsof exits 1 with an error", Completed(1, "", "lsof: status error on x")),
                        ("lsof exits 2", Completed(2))]:
    runner, _ = lsof_answering(completed)
    try:
        wait.macos_processes_writing_file(target, runner=runner)
        raised = None
    except wait.WritersCannotBeListed as error:
        raised = str(error)
    check(f"{name}: reported as writers that cannot be listed", raised is not None and "lsof" in raised,
          raised)

timeouts.clear()
runner, _ = lsof_answering(Completed(1))
wait.macos_processes_writing_file(target, seconds_left=12.5, runner=runner)
wait.macos_processes_writing_file(target, seconds_left=100, runner=runner)
check("lsof is given the time that remains, up to its own limit", timeouts == [12.5, wait.LSOF_TIMEOUT_SECONDS],
      timeouts)
for seconds_left, expected in [(12.5, wait.WritersLookTimeLimitReached), (100, wait.WritersCannotBeListed)]:
    runner, _ = lsof_answering(subprocess.TimeoutExpired("lsof", seconds_left))
    try:
        wait.macos_processes_writing_file(target, seconds_left=seconds_left, runner=runner)
        raised = None
    except Exception as error:
        raised = error
    check(f"lsof timing out when given {seconds_left:g} seconds raises {expected.__name__}",
          type(raised) is expected, repr(raised))

check("macOS lists writers with lsof, Linux with /proc",
      wait.processes_writing_file_lister("darwin") is wait.macos_processes_writing_file
      and wait.processes_writing_file_lister("linux") is wait.linux_processes_writing_file)

process = subprocess.run([sys.executable, str(PROGRAM), str(root / "missing.output")],
                         capture_output=True, text=True)
check("as a process, a missing file exits 2 and prints why on standard error",
      process.returncode == wait.EXIT_CANNOT_WAIT and "does not exist" in process.stderr,
      (process.returncode, process.stderr))
check("the default time limit ends the wait before the Bash tool's default timeout of 120 seconds",
      wait.DEFAULT_TIME_LIMIT_SECONDS < 120)

scratch.cleanup()
if failures:
    print(f"{len(failures)} case(s) failed: " + ", ".join(failures))
    sys.exit(1)
print("all cases passed")
