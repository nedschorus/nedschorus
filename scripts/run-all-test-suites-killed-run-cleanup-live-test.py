#!/usr/bin/env python3
"""Tests, with real processes and real bwrap, of how scripts/run-all-test-suites.py
cleans up after a run that was killed.

A run killed by SIGKILL can leave a suite still running and still writing its
strace traces. The next run must not remove those traces until every suite
process the killed run recorded has ended. These cases kill a real runner and
look at what the next run removes.

This suite runs outside the signal sandbox (it is listed in
SUITES_RUN_OUTSIDE_THE_SIGNAL_SANDBOX): it starts the runner, which starts
bwrap, and bwrap cannot start inside bwrap. Outside the sandbox a signal sent
to the wrong process can reach every process of this account, as one did on
ned-box on 2026-10-04. So every signal this suite sends goes through
signal_own_descendant, which signals only a live descendant of this process
whose start time it has just checked, and the cases that test its refusals
give it a recorder instead of the real os.kill. This process makes itself a
child subreaper, so a suite orphaned by its killed runner stays its descendant.

Linux only, and only where bwrap starts: elsewhere every case prints SKIP.

Run: python3 scripts/run-all-test-suites-killed-run-cleanup-live-test.py   (exit 0 = all passed)
"""

import ctypes
import importlib.util
import json
import os
import pathlib
import shutil
import signal
import subprocess
import sys
import tempfile
import time

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    pathlib.Path(__file__).resolve().with_name(
        "git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
PROGRAM = SCRIPTS_DIR / "run-all-test-suites.py"
STARTED_FILE_VARIABLE = "RUN_ALL_TEST_SUITES_KILLED_RUN_TEST_STARTED_FILE"
STOP_FILE_VARIABLE = "RUN_ALL_TEST_SUITES_KILLED_RUN_TEST_STOP_FILE"
PR_SET_CHILD_SUBREAPER = 36
WAIT_SECONDS = 60

failures = []
cases_run = 0


def check(case_name, condition, detail=""):
    global cases_run
    cases_run += 1
    print(f"{'ok' if condition else 'FAIL'}: {case_name}")
    if not condition:
        failures.append(case_name)
        if detail:
            print(f"      {detail!r}"[:1200])


def load_program_module():
    spec = importlib.util.spec_from_file_location("run_all_test_suites", PROGRAM)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


module = load_program_module()


class SignalRefused(Exception):
    """signal_own_descendant would not send this signal; the message says why."""


def parent_pid(pid):
    stat = pathlib.Path(f"/proc/{pid}/stat").read_text()
    return int(stat.rsplit(")", 1)[1].split()[1])


def signal_own_descendant(pid, start_ticks, signal_number, kill=os.kill):
    """Send the signal only to a live descendant of this process with this start time."""
    if not isinstance(pid, int) or pid <= 1:
        raise SignalRefused(f"pid {pid!r} is not a single process this test started")
    if module.process_start_ticks(pid) != start_ticks:
        raise SignalRefused(f"pid {pid} is not the process with start ticks {start_ticks}")
    ancestor = pid
    while ancestor != os.getpid():
        try:
            ancestor = parent_pid(ancestor)
        except (FileNotFoundError, ProcessLookupError):
            raise SignalRefused(f"pid {pid} ended while its ancestry was read") from None
        if ancestor <= 1:
            raise SignalRefused(f"pid {pid} is not a descendant of this test")
    # Read again just before the signal, so a pid reused meanwhile is not hit.
    if module.process_start_ticks(pid) != start_ticks:
        raise SignalRefused(f"pid {pid} changed before the signal could be sent")
    kill(pid, signal_number)


def wait_until(condition, seconds=WAIT_SECONDS):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.05)
    return condition()


def git(repo, *arguments):
    subprocess.run(["git", "-C", str(repo), "-c", "core.hooksPath=/dev/null",
                    "-c", "commit.gpgsign=false", "-c", "user.name=test",
                    "-c", "user.email=test@nedschorus.invalid", *arguments],
                   check=True, capture_output=True)


# A suite that says it started, then runs until the test creates its stop file.
WAITS_FOR_THE_STOP_FILE = f'''import os, pathlib, time
pathlib.Path(os.environ["{STARTED_FILE_VARIABLE}"]).write_text(str(os.getpid()))
while not pathlib.Path(os.environ["{STOP_FILE_VARIABLE}"]).exists():
    time.sleep(0.05)
'''


def make_repo(root, suite_path, body=WAITS_FOR_THE_STOP_FILE, name="repo"):
    repo = root / name
    (repo / suite_path).parent.mkdir(parents=True, exist_ok=True)
    (repo / suite_path).write_text(body)
    git(repo, "init", "-q")
    git(repo, "add", "--", suite_path)
    git(repo, "commit", "-q", "-m", "fixture")
    return repo


def start_run(root, repo, name):
    """Start the runner on repo with its own log directory; return (process, log dir)."""
    environment = dict(os.environ)
    environment.pop(module.SIGNAL_SANDBOX_INSIDE_VARIABLE, None)
    environment[STARTED_FILE_VARIABLE] = str(root / f"{name}.started")
    environment[STOP_FILE_VARIABLE] = str(root / "stop")
    log_dir = root / f"logs-{name}"
    process = subprocess.Popen(
        [sys.executable, str(PROGRAM), "--checkout", str(repo), "--log-dir", str(log_dir),
         "--lock-file", str(root / "run.lock"),
         "--recorded-inputs-directory", str(root / "recordings")],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, env=environment)
    return process, log_dir


def run_records(root):
    runs = module.runs_directory_for(root / "run.lock")
    return [json.loads(path.read_text()) for path in sorted(runs.glob("*.json"))]


def finish_run(root, repo, name):
    environment = dict(os.environ)
    environment.pop(module.SIGNAL_SANDBOX_INSIDE_VARIABLE, None)
    environment[STARTED_FILE_VARIABLE] = str(root / f"{name}.started")
    environment[STOP_FILE_VARIABLE] = str(root / "stop")
    return subprocess.run(
        [sys.executable, str(PROGRAM), "--checkout", str(repo),
         "--log-dir", str(root / f"logs-{name}"), "--lock-file", str(root / "run.lock"),
         "--recorded-inputs-directory", str(root / "recordings")],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, env=environment,
        timeout=600)


def sandbox_starts():
    try:
        prefix, unconfined_because = module.signal_sandbox(
            environment={key: value for key, value in os.environ.items()
                         if key != module.SIGNAL_SANDBOX_INSIDE_VARIABLE})
    except module.SignalSandboxCouldNotStart as error:
        return str(error)
    return None if prefix else unconfined_because


# --- The signal helper refuses anything it did not start ---------------------
sent = []


def recorder(pid, signal_number):
    sent.append((pid, signal_number))


for refused_pid, why in ((1, "pid 1"), (0, "pid 0, the whole process group"),
                         (-1, "pid -1, every process of this account"),
                         (-os.getpgrp(), "a negative pid, a process group")):
    try:
        signal_own_descendant(refused_pid, module.process_start_ticks(1) or 0,
                              signal.SIGTERM, kill=recorder)
    except SignalRefused:
        refused = True
    else:
        refused = False
    check(f"the signal helper refuses {why}", refused and not sent, sent)

try:
    signal_own_descendant(os.getppid(), module.process_start_ticks(os.getppid()),
                          signal.SIGTERM, kill=recorder)
except SignalRefused:
    refused = True
else:
    refused = False
check("the signal helper refuses a process that is not its descendant", refused and not sent,
      sent)

child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
child_ticks = module.process_start_ticks(child.pid)
try:
    signal_own_descendant(child.pid, child_ticks + 1, signal.SIGTERM, kill=recorder)
except SignalRefused:
    refused = True
else:
    refused = False
check("the signal helper refuses a descendant whose start time is not the one it was given",
      refused and not sent, sent)
signal_own_descendant(child.pid, child_ticks, signal.SIGTERM)
check("the signal helper signals its own live child", child.wait(timeout=30) == -signal.SIGTERM)
try:
    signal_own_descendant(child.pid, child_ticks, signal.SIGTERM, kill=recorder)
except SignalRefused:
    refused = True
else:
    refused = False
check("the signal helper refuses a child that has ended", refused and not sent, sent)

# --- A killed run's suite that still runs keeps its traces ---------------------
not_runnable = (None if sys.platform.startswith("linux") else f"{sys.platform} is not Linux")
not_runnable = not_runnable or sandbox_starts()
if not_runnable:
    print(f"SKIP  every killed-run case: {not_runnable}")
else:
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) != 0:
        print(f"SKIP  every killed-run case: prctl(PR_SET_CHILD_SUBREAPER) failed, "
              f"errno {ctypes.get_errno()}")
    else:
        # A suite the runner starts outside the sandbox outlives a killed runner: that
        # is the case where a later run could delete traces still being written.
        unconfined_suite = next(iter(module.SUITES_RUN_OUTSIDE_THE_SIGNAL_SANDBOX))
        with tempfile.TemporaryDirectory() as scratch:
            root = pathlib.Path(scratch)
            repo = make_repo(root, unconfined_suite)
            # The later runs run a suite that ends at once, so they need no stop file.
            quick_repo = make_repo(root, "quick-test.py", "print('ok')\n", "quick-repo")
            run_b, logs_b = start_run(root, repo, "b")
            try:
                started = wait_until(lambda: (root / "b.started").exists())
                check("the killed run's suite starts", started, run_b.poll())
                records = run_records(root)
                suite_processes = records[0]["suite_processes"] if records else []
                check("the run's record names its suite process while the suite runs",
                      len(suite_processes) == 1, records)
                # The trace a suite under strace would be writing.
                trace = logs_b / "recorded-inputs" / "a-suite-still-running.strace"
                trace.mkdir(parents=True, exist_ok=True)
                (trace / "trace.1").write_text("still being written\n")
                runner_ticks = module.process_start_ticks(run_b.pid)
                signal_own_descendant(run_b.pid, runner_ticks, signal.SIGKILL)
                run_b.wait(timeout=30)
                run_b.stdout.close()
                suite_pid = int((root / "b.started").read_text())
                check("the suite outlives its killed runner",
                      module.process_start_ticks(suite_pid) is not None)
                result_c = finish_run(root, quick_repo, "c-with-the-suite-still-running")
            finally:
                (root / "stop").write_text("stop\n")
            check("the next run keeps the traces of a killed run whose suite still runs",
                  trace.exists(), result_c.stdout)
            check("and says why",
                  "has no runner, but 1 of its suite processes still run; its files are kept"
                  in result_c.stdout, result_c.stdout)
            check("the orphaned suite ends once told to",
                  wait_until(lambda: module.process_start_ticks(suite_pid) is None))
            reaped = []
            while True:
                try:
                    reaped_pid, _ = os.waitpid(-1, os.WNOHANG)
                except ChildProcessError:
                    break
                if reaped_pid == 0:
                    break
                reaped.append(reaped_pid)
            result_d = finish_run(root, quick_repo, "d-after-the-suite-ended")
            check("a run after the suite ended removes the killed run's traces",
                  not trace.exists(), result_d.stdout)

        # A suite in the sandbox is recorded by the init of its PID namespace.
        sandboxed_suite = "sandboxed-test.py"
        with tempfile.TemporaryDirectory() as scratch:
            root = pathlib.Path(scratch)
            repo = make_repo(root, sandboxed_suite)
            quick_repo = make_repo(root, "quick-test.py", "print('ok')\n", "quick-repo")
            run_e, logs_e = start_run(root, repo, "e")
            try:
                started = wait_until(lambda: (root / "e.started").exists())
                records = run_records(root)
                suite_processes = records[0]["suite_processes"] if records else []
                init = suite_processes[0] if suite_processes else {}
                check("a sandboxed suite is recorded by its namespace init",
                      started and init.get("namespace_init") is True, records)
                comm = pathlib.Path(f"/proc/{init.get('pid')}/comm")
                check("which is bwrap's own process inside the namespace",
                      comm.exists() and comm.read_text().strip() == "bwrap",
                      comm.read_text() if comm.exists() else None)
                runner_ticks = module.process_start_ticks(run_e.pid)
                signal_own_descendant(run_e.pid, runner_ticks, signal.SIGKILL)
                run_e.wait(timeout=30)
                run_e.stdout.close()
                # The suite's own pid is the namespace's; the init's pid is this host's.
                init_pid = init.get("pid")
                check("killing the runner ends its sandboxed suite with the namespace",
                      init_pid is not None and wait_until(
                          lambda: module.process_start_ticks(init_pid) is None, seconds=10))
            finally:
                (root / "stop").write_text("stop\n")
            trace = logs_e / "recorded-inputs" / "left.strace"
            trace.mkdir(parents=True, exist_ok=True)
            result_f = finish_run(root, quick_repo, "f")
            check("the next run removes what the killed sandboxed run left",
                  not trace.exists(), result_f.stdout)

print()
print(f"{cases_run} cases run")
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
