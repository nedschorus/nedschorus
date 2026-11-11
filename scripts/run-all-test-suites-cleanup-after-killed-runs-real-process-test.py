#!/usr/bin/env python3
"""Tests, with real processes and real bwrap, of how scripts/run-all-test-suites.py
cleans up after a run that was killed.

A run killed by SIGKILL can leave a suite still running and still writing its
strace traces. The next run must not remove those traces until every suite
process the killed run recorded has ended. These cases kill a real runner and
look at what the next run removes.

This suite runs outside the signal sandbox (it is listed in
SUITES_RUN_WITHOUT_ANY_SANDBOX): it starts the runner, which starts
bwrap, and bwrap cannot start inside bwrap. Outside the sandbox a signal sent
to the wrong process can reach every process of this account, every agent
included. So every signal this suite sends goes through
signal_own_descendant, which signals only a live descendant of this process
whose start time it has just checked, and the cases that test its refusals
give it a recorder instead of the real os.kill. This process makes itself a
child subreaper, so a suite orphaned by its killed runner stays its descendant.

Linux only, and only where bwrap starts: elsewhere every case prints SKIP.

Run: python3 scripts/run-all-test-suites-cleanup-after-killed-runs-real-process-test.py   (exit 0 = all passed)
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
WATCHED_PID_VARIABLE = "RUN_ALL_TEST_SUITES_KILLED_RUN_TEST_SUITE_ENDS_WITH_PROCESS_PID"
WATCHED_START_TICKS_VARIABLE = "RUN_ALL_TEST_SUITES_KILLED_RUN_TEST_SUITE_ENDS_WITH_PROCESS_START_TICKS"
# A runner this test starts is killed when the thread that started it ends, so a test killed
# with SIGKILL, whose finally does not run, leaves no runner, and so no suite in bwrap, behind.
DIES_WITH_ITS_STARTER = ("setpriv", "--pdeathsig", "KILL")
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
    if start_ticks is None:
        raise SignalRefused(f"pid {pid} has no start time to check it against")
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


# A suite that says it started, then runs until the test creates its stop file, or, when
# given a watched process, until that process no longer runs: a test killed with SIGKILL
# never creates the stop file. It says it started in its output too, which the runner copies
# to the suite's log as it runs: a sandboxed suite's write in the checkout does not reach the
# checkout outside. A sandboxed suite is given no watched process, since its PID namespace
# shows none outside it; it ends with its namespace when its runner ends.
WAITS_FOR_THE_STOP_FILE = f'''import os, pathlib, time
pathlib.Path(os.environ["{STARTED_FILE_VARIABLE}"]).write_text(str(os.getpid()))
print("started", flush=True)
watched = os.environ.get("{WATCHED_PID_VARIABLE}")


def watched_process_runs():
    if watched is None:
        return True
    try:
        stat = pathlib.Path(f"/proc/{{watched}}/stat").read_text()
    except (FileNotFoundError, ProcessLookupError):
        return False
    fields = stat.rsplit(")", 1)[1].split()
    return fields[0] != "Z" and fields[19] == os.environ["{WATCHED_START_TICKS_VARIABLE}"]


while watched_process_runs() and not pathlib.Path(os.environ["{STOP_FILE_VARIABLE}"]).exists():
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


# Runs the runner with admission's CPU and memory thresholds opened wide, so a case does
# not wait on how busy the machine is; the admission directory is this test's own.
ADMISSION_OPENED_DRIVER = r'''
import importlib.util, sys
program_path, *arguments = sys.argv[1:]
spec = importlib.util.spec_from_file_location("run_all_test_suites", program_path)
program = importlib.util.module_from_spec(spec)
sys.argv = [program_path, *arguments]
spec.loader.exec_module(program)
program.TEST_SUITE_ADMISSION_CPU_PERCENT_BELOW = 101
program.TEST_SUITE_ADMISSION_AVAILABLE_MEMORY_BYTES_ABOVE = -1
sys.exit(program.main(arguments))
'''


def run_command_and_environment(root, repo, name, suite_watches_this_test):
    """The runner's command on repo with its own log directory, and its environment."""
    environment = dict(os.environ)
    environment.pop(module.SIGNAL_SANDBOX_INSIDE_VARIABLE, None)
    # In the checkout, which a suite run without any sandbox and this test share; inside
    # an nc-test-sandbox the checkout is a copy-on-write overlay, so a sandboxed suite reports
    # its start in its output instead.
    environment[STARTED_FILE_VARIABLE] = str(repo / f"{name}.started")
    environment[STOP_FILE_VARIABLE] = str(repo / "stop")
    if suite_watches_this_test:
        environment[WATCHED_PID_VARIABLE] = str(os.getpid())
        environment[WATCHED_START_TICKS_VARIABLE] = str(module.process_start_ticks(os.getpid()))
    command = [*DIES_WITH_ITS_STARTER, sys.executable, "-c", ADMISSION_OPENED_DRIVER, str(PROGRAM),
               "--checkout", str(repo), "--log-dir", str(root / f"logs-{name}"),
               "--lock-file", str(root / "run.lock"),
               "--recorded-inputs-directory", str(root / "recordings")]
    return command, environment


def start_run(root, repo, name, suite_watches_this_test):
    """Start the runner on repo with its own log directory; return (process, log dir)."""
    command, environment = run_command_and_environment(root, repo, name, suite_watches_this_test)
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, env=environment)
    return process, root / f"logs-{name}"


# Starts the command it is given, first adding its own pid and start ticks to the command's
# environment under the two variable names when it is given them, writes the started
# process's pid down, then waits for the case to kill it.
STARTS_A_COMMAND_THEN_WAITS = r'''
import json, os, pathlib, subprocess, sys, time
command, environment, pid_file, own_pid_and_start_ticks_variables = json.loads(sys.argv[1])
if own_pid_and_start_ticks_variables:
    pid_variable, start_ticks_variable = own_pid_and_start_ticks_variables
    environment[pid_variable] = str(os.getpid())
    environment[start_ticks_variable] = (
        pathlib.Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()[19])
started = subprocess.Popen(command, env=environment, stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
pathlib.Path(pid_file).write_text(str(started.pid))
time.sleep(60)
'''


def start_helper(command, environment, pid_file, own_pid_and_start_ticks_variables=None):
    return subprocess.Popen(
        [sys.executable, "-c", STARTS_A_COMMAND_THEN_WAITS,
         json.dumps([command, environment, str(pid_file), own_pid_and_start_ticks_variables])],
        stdin=subprocess.DEVNULL)


def pid_written_in(path):
    """The pid in path once it is there, or None when it is not written within WAIT_SECONDS."""
    if not wait_until(lambda: path.exists() and path.read_text().strip()):
        return None
    return int(path.read_text())


def reap_ended_children():
    """Reap the zombies of processes this test inherited as their child subreaper."""
    while True:
        try:
            reaped_pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return
        if reaped_pid == 0:
            return


def run_records(root):
    runs = module.run_records_directory_for_lock_file(root / "run.lock")
    return [json.loads(path.read_text()) for path in sorted(runs.glob("*.json"))]


def finish_run(root, repo, name):
    environment = dict(os.environ)
    environment.pop(module.SIGNAL_SANDBOX_INSIDE_VARIABLE, None)
    environment[STARTED_FILE_VARIABLE] = str(root / f"{name}.started")
    environment[STOP_FILE_VARIABLE] = str(root / "stop")
    return subprocess.run(
        [sys.executable, "-c", ADMISSION_OPENED_DRIVER, str(PROGRAM), "--checkout", str(repo),
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

# The cases below read start times and ancestry from /proc, which only Linux has.
not_linux = None if sys.platform.startswith("linux") else f"{sys.platform} is not Linux"
if not_linux:
    print(f"SKIP  the signal helper's descendant and start-time cases: {not_linux}, "
          f"so there is no /proc to read start times and ancestry from")
else:
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
    try:
        signal_own_descendant(child.pid, None, signal.SIGTERM, kill=recorder)
    except SignalRefused:
        refused = True
    else:
        refused = False
    check("the signal helper refuses a process given without a start time",
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

    # A test killed with SIGKILL runs no finally, so it never creates the stop file.
    with tempfile.TemporaryDirectory() as scratch:
        root = pathlib.Path(scratch)
        environment = dict(os.environ, **{STARTED_FILE_VARIABLE: str(root / "started"),
                                          STOP_FILE_VARIABLE: str(root / "stop")})
        helper = start_helper([sys.executable, "-c", WAITS_FOR_THE_STOP_FILE], environment,
                              root / "suite.pid",
                              [WATCHED_PID_VARIABLE, WATCHED_START_TICKS_VARIABLE])
        try:
            suite_pid = pid_written_in(root / "started")
            suite_ticks = None if suite_pid is None else module.process_start_ticks(suite_pid)
            signal_own_descendant(helper.pid, module.process_start_ticks(helper.pid),
                                  signal.SIGKILL)
            helper.wait(timeout=30)
            check("the fixture suite given a process to end with ends when that process is "
                  "killed with SIGKILL",
                  suite_ticks is not None and wait_until(
                      lambda: not module.process_alive(suite_pid, suite_ticks)),
                  (suite_pid, suite_ticks))
        finally:
            (root / "stop").write_text("stop\n")

# --- The launcher a suite outside an nc-test-sandbox starts under ----------------
_launcher_spec = importlib.util.spec_from_file_location(
    "suite_launcher", module.ONE_SUITE_CHILD_SUBREAPER_LAUNCHER_PATH)
launcher = importlib.util.module_from_spec(_launcher_spec)
_launcher_spec.loader.exec_module(launcher)
LAUNCHER_COMMAND = [sys.executable, "-I", str(module.ONE_SUITE_CHILD_SUBREAPER_LAUNCHER_PATH)]


class PrctlRefuses:
    def prctl(self, *arguments):
        return -1


real_cdll = launcher.ctypes.CDLL
launcher.ctypes.CDLL = lambda *arguments, **keywords: PrctlRefuses()
real_stderr = sys.stderr
sys.stderr = captured_stderr = __import__("io").StringIO()
try:
    # main ends with sys.exit when it starts the suite, which would end this whole test file
    # with that status midway; count it as this case's result instead.
    refused_status = launcher.main(["true"])
except SystemExit as exit_from_main:
    refused_status = f"main started the suite and called sys.exit({exit_from_main.code!r})"
finally:
    sys.stderr = real_stderr
    launcher.ctypes.CDLL = real_cdll
check("the launcher starts no suite, exits 125 and says why, when prctl refuses",
      refused_status == launcher.CHILD_SUBREAPER_LAUNCHER_SUITE_NOT_STARTED_EXIT_STATUS
      and "prctl(PR_SET_CHILD_SUBREAPER) failed" in captured_stderr.getvalue()
      and "was not started" in captured_stderr.getvalue(), captured_stderr.getvalue())

if not_linux:
    print(f"SKIP  the launcher's and the orphaned-descendant cases: {not_linux}, so there is "
          f"no child subreaper")
else:
    missing = subprocess.run([*LAUNCHER_COMMAND, "/nonexistent/suite-command"],
                             capture_output=True, text=True, timeout=60)
    check("the launcher exits 125 and says why when the suite's command cannot start",
          missing.returncode == launcher.CHILD_SUBREAPER_LAUNCHER_SUITE_NOT_STARTED_EXIT_STATUS
          and "the command could not start" in missing.stderr, missing)
    no_command = subprocess.run(LAUNCHER_COMMAND, capture_output=True, text=True, timeout=60)
    check("the launcher given no command runs nothing and exits 2",
          no_command.returncode == 2 and "no command given" in no_command.stderr, no_command)
    exited = subprocess.run([*LAUNCHER_COMMAND, "sh", "-c", "exit 7"], timeout=60)
    check("the launcher exits with the suite's exit status", exited.returncode == 7,
          exited.returncode)
    passed = subprocess.run([*LAUNCHER_COMMAND, "sh", "-c", "exit 0"], timeout=60)
    check("the launcher exits 0 when the suite exits 0", passed.returncode == 0,
          passed.returncode)
    # Signal 1, the lowest, so a launcher that took -1 for an exit status is caught.
    hung_up = subprocess.run([*LAUNCHER_COMMAND, "sh", "-c", "kill -HUP $$"], timeout=60)
    check("the launcher ends by SIGHUP when SIGHUP ended the suite",
          hung_up.returncode == -signal.SIGHUP, hung_up.returncode)
    signalled = subprocess.run([*LAUNCHER_COMMAND, "sh", "-c", "kill -TERM $$"], timeout=60)
    check("the launcher ends by the signal that ended the suite",
          signalled.returncode == -signal.SIGTERM, signalled.returncode)
    # SIGKILL is what the kernel sends a suite at its memory ceiling.
    killed = subprocess.run([*LAUNCHER_COMMAND, "sh", "-c", "kill -KILL $$"], timeout=60)
    check("the launcher ends by SIGKILL when SIGKILL ended the suite",
          killed.returncode == -signal.SIGKILL, killed.returncode)

    # Made a child subreaper here too, so a grandchild the runner misses is reparented to this
    # test, which can then end it, rather than to a process of the account's.
    libc_for_orphans = ctypes.CDLL(None, use_errno=True)
    if libc_for_orphans.prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) != 0:
        print(f"SKIP  the orphaned-descendant case: prctl(PR_SET_CHILD_SUBREAPER) failed, "
              f"errno {ctypes.get_errno()}")
    else:
        with tempfile.TemporaryDirectory() as scratch:
            root = pathlib.Path(scratch)
            top = root / "top"
            top.mkdir()
            grandchild_pid_file = root / "grandchild.pid"
            # A helper starts a grandchild in a session of its own and exits, so the grandchild
            # has no parent below the suite when the suite is killed at its limit.
            (top / "orphan-suite-test.py").write_text(
                "import subprocess, sys, time\n"
                "helper = ('import subprocess, sys; '\n"
                "          'p = subprocess.Popen([\"sleep\", \"60\"], start_new_session=True); '\n"
                "          'open(sys.argv[1], \"w\").write(str(p.pid))')\n"
                f"subprocess.run([sys.executable, '-c', helper, {str(grandchild_pid_file)!r}],\n"
                "               check=True)\n"
                "print('helper exited', flush=True)\n"
                "time.sleep(60)\n")
            logs = root / "logs"
            logs.mkdir()
            grandchild = grandchild_ticks = None
            try:
                result = module.run_one_suite(top, sys.executable, "orphan-suite-test.py", logs,
                                              time_limit=(20, None))
                grandchild = (int(grandchild_pid_file.read_text())
                              if grandchild_pid_file.exists() else None)
                grandchild_ticks = (None if grandchild is None
                                    else module.process_start_ticks(grandchild))
                check("a killed suite's grandchild whose parent ended first is killed too",
                      "timeout" in result and grandchild is not None
                      and grandchild_ticks is None,
                      (result, grandchild, grandchild_ticks))
            finally:
                if grandchild_ticks is not None:
                    signal_own_descendant(grandchild, grandchild_ticks, signal.SIGKILL)
                    wait_until(lambda: module.process_start_ticks(grandchild) is None, 10)
                reap_ended_children()

    # Elsewhere the kill cannot see below the process group, so the directory is kept.
    with tempfile.TemporaryDirectory() as scratch:
        root = pathlib.Path(scratch)
        top = root / "top"
        top.mkdir()
        (top / "sleeps-test.py").write_text("import time\ntime.sleep(60)\n")
        logs = root / "logs"
        logs.mkdir()
        result = module.run_one_suite(top, sys.executable, "sleeps-test.py", logs,
                                      platform="darwin", time_limit=(2, None))
        note = result.get("output_note") or ""
        kept = [part for part in note.split("`rm -rf ")[1:]]
        kept_directory = kept[0].split("`")[0].strip("'") if kept else None
        check("on a platform without /proc a killed suite's temporary directory is kept, "
              "and the note says how to remove it",
              "timeout" in result and "is kept for any still running" in note
              and kept_directory is not None and pathlib.Path(kept_directory).is_dir(), note)
        if kept_directory and pathlib.Path(kept_directory).name.startswith(
                module.SUITE_OUTSIDE_NC_TEST_SANDBOX_TEMPORARY_DIRECTORY_PREFIX):
            shutil.rmtree(kept_directory, ignore_errors=True)

# --- A killed run's suite that still runs keeps its traces ---------------------
not_runnable = not_linux or sandbox_starts()
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
        unconfined_suite = next(iter(module.SUITES_RUN_WITHOUT_ANY_SANDBOX))
        with tempfile.TemporaryDirectory() as scratch:
            root = pathlib.Path(scratch)
            repo = make_repo(root, unconfined_suite)
            # The later runs run a suite that ends at once, so they need no stop file.
            quick_repo = make_repo(root, "quick-test.py", "print('ok')\n", "quick-repo")
            run_b, logs_b = start_run(root, repo, "b", suite_watches_this_test=True)
            try:
                started = wait_until(lambda: (repo / "b.started").exists())
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
                suite_pid = int((repo / "b.started").read_text())
                check("the suite outlives its killed runner",
                      module.process_start_ticks(suite_pid) is not None)
                result_c = finish_run(root, quick_repo, "c-with-the-suite-still-running")
            finally:
                (repo / "stop").write_text("stop\n")
            check("the next run keeps the traces of a killed run whose suite still runs",
                  trace.exists(), result_c.stdout)
            check("and says why",
                  "has no runner, but 1 of its suite processes still run; its files are kept"
                  in result_c.stdout, result_c.stdout)
            check("the orphaned suite ends once told to",
                  wait_until(lambda: module.process_start_ticks(suite_pid) is None))
            reap_ended_children()
            result_d = finish_run(root, quick_repo, "d-after-the-suite-ended")
            check("a run after the suite ended removes the killed run's traces",
                  not trace.exists(), result_d.stdout)

        # A suite in the sandbox is recorded by the init of its PID namespace.
        sandboxed_suite = "sandboxed-test.py"
        with tempfile.TemporaryDirectory() as scratch:
            root = pathlib.Path(scratch)
            repo = make_repo(root, sandboxed_suite)
            quick_repo = make_repo(root, "quick-test.py", "print('ok')\n", "quick-repo")
            run_e, logs_e = start_run(root, repo, "e", suite_watches_this_test=False)
            try:
                suite_log = module.log_path_for(logs_e, sandboxed_suite)
                started = wait_until(lambda: suite_log.exists()
                                     and "started" in suite_log.read_text(errors="replace"))
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
                (repo / "stop").write_text("stop\n")
            trace = logs_e / "recorded-inputs" / "left.strace"
            trace.mkdir(parents=True, exist_ok=True)
            result_f = finish_run(root, quick_repo, "f")
            check("the next run removes what the killed sandboxed run left",
                  not trace.exists(), result_f.stdout)

        # The process that started a runner of this test killed with SIGKILL, as this test
        # can be, takes the runner and its sandboxed suite with it.
        with tempfile.TemporaryDirectory() as scratch:
            root = pathlib.Path(scratch)
            repo = make_repo(root, sandboxed_suite)
            command, environment = run_command_and_environment(
                root, repo, "g", suite_watches_this_test=False)
            helper = start_helper(command, environment, root / "runner.pid")
            runner_pid = runner_ticks = None
            try:
                suite_log = module.log_path_for(root / "logs-g", sandboxed_suite)
                started = wait_until(lambda: suite_log.exists()
                                     and "started" in suite_log.read_text(errors="replace"))
                runner_pid = pid_written_in(root / "runner.pid")
                runner_ticks = None if runner_pid is None else module.process_start_ticks(runner_pid)
                records = run_records(root)
                init = records[0]["suite_processes"][0] if records and records[0][
                    "suite_processes"] else {}
                signal_own_descendant(helper.pid, module.process_start_ticks(helper.pid),
                                      signal.SIGKILL)
                helper.wait(timeout=30)
                check("a runner this test starts ends when the process that started it is "
                      "killed with SIGKILL, and its sandboxed suite ends with it",
                      started and runner_ticks is not None and init.get("pid") is not None
                      and wait_until(lambda: not module.process_alive(runner_pid, runner_ticks))
                      and wait_until(lambda: not module.process_alive(
                          init["pid"], init["start_ticks"]), seconds=10),
                      (started, runner_pid, runner_ticks, records))
            finally:
                (repo / "stop").write_text("stop\n")
                # The stop file may not reach the sandboxed suite through its overlay, and a
                # runner that outlived its starter would wait on that suite for ever.
                if runner_ticks is not None and module.process_alive(runner_pid, runner_ticks):
                    signal_own_descendant(runner_pid, runner_ticks, signal.SIGKILL)
                reap_ended_children()

print()
print(f"{cases_run} cases run")
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
