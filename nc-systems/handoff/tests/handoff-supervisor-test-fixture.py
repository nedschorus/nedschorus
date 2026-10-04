#!/usr/bin/env python3
"""What the three handoff-supervisor suites beside this file share.

Each suite loads this file by path in a process of its own, so each gets its
own copy of the supervisor module: the cases patch the module's globals, and
two suites sharing one copy would see each other's patches.

Loading it puts in place, for the rest of the process, the sandboxes every
case relies on: an ssh first on PATH that never reaches ned-box, an empty
directory standing in for the overview reminders' marks, and a directory of
the process's own for the agent-binary update lock.

Not a test file: its name ends `-test-fixture.py` rather than `-test.py`, so
scripts/run-all-test-suites.py does not run it as a suite of its own.
"""

import atexit
import contextlib
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

# This fixture sits at nc-systems/handoff/tests/, beside the suites, so the
# system they test is one directory up and the repository root is three.
# SYSTEM_DIRECTORY and REPOSITORY_ROOT name those depths once each; a
# with_name() lookup here would resolve inside tests/ and find nothing.
SYSTEM_DIRECTORY = Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = SYSTEM_DIRECTORY.parent.parent

SCRIPT_PATH = SYSTEM_DIRECTORY / "handoff-supervisor.py"

_spec = importlib.util.spec_from_file_location("handoff_supervisor", SCRIPT_PATH)
supervisor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(supervisor)

failures = []

os.environ["CLAUDE_CODE_TASK_LIST_ID"] = "handoff-supervisor-test-pin-tasks"

# No case may reach ned-box. On the Mac from noon Pacific, every launch that
# composes a successor's first prompt runs memory_review_due_lines, which reads
# ned-box over ssh, and many of the suites' cases launch the real supervisor.
# This ssh, first on PATH for this process and every process it starts, refuses
# at once, so those launches give no memory line. The memory-review cases put
# an ssh of their own ahead of it.
SSH_THAT_NEVER_REACHES_NED_BOX_DIRECTORY = Path(
    tempfile.mkdtemp(prefix="ssh-that-never-reaches-ned-box-"))
atexit.register(shutil.rmtree, SSH_THAT_NEVER_REACHES_NED_BOX_DIRECTORY, True)
(SSH_THAT_NEVER_REACHES_NED_BOX_DIRECTORY / "ssh").write_text(
    "#!/bin/sh\necho 'ssh: this test suite never reaches ned-box' >&2\nexit 255\n",
    encoding="utf-8")
(SSH_THAT_NEVER_REACHES_NED_BOX_DIRECTORY / "ssh").chmod(0o755)
os.environ["PATH"] = (f"{SSH_THAT_NEVER_REACHES_NED_BOX_DIRECTORY}{os.pathsep}"
                      f"{os.environ.get('PATH', '')}")

# No case run in this process may read the real marks of the day's overview
# reminders either. overview_refresh_due_lines reads them whenever a system's
# line is still to give, and a read that fails adds a line of its own; so on
# both machines the read is local, of this directory, which holds nothing and
# stands in for the log-store's. The once-a-day cases put a marks directory,
# an ssh and the real choice of machine back in place. A case that launches
# the real supervisor as a process of its own is outside this: on ned-box that
# process reads the log-store's real directory, for a fixture system no real
# mark is ever written for, and it writes nothing; on the Mac the ssh above
# refuses its read.
SSH_TARGET_FOR_THIS_MACHINE_UNPATCHED = None
if hasattr(supervisor, "daily_overview_refresh_reminder_mark"):
    supervisor.daily_overview_refresh_reminder_mark \
        .DAILY_OVERVIEW_REFRESH_REMINDER_MARKS_DIRECTORY = str(
            SSH_THAT_NEVER_REACHES_NED_BOX_DIRECTORY / "no-overview-refresh-reminder-marks")
    SSH_TARGET_FOR_THIS_MACHINE_UNPATCHED = (
        supervisor.daily_overview_refresh_reminder_mark.ssh_target_for_this_machine)
    supervisor.daily_overview_refresh_reminder_mark.ssh_target_for_this_machine = (
        lambda: None)

# The agent-binary update cases take the machine-wide update lock, so the lock
# is pointed into a directory of this process's own: a suite run must neither
# wait on this machine's real updates nor delay them.
update_lock_sandbox = tempfile.TemporaryDirectory()
supervisor.agent_binary_update_under_lock.AGENT_BINARY_UPDATE_LOCK_PATH = str(
    Path(update_lock_sandbox.name) / "agent-binary-update.lock")
sandboxed_update_lock_path = (
    supervisor.agent_binary_update_under_lock.agent_binary_update_lock_path())


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


@contextlib.contextmanager
def handoff_supervisor_suite_workspace():
    """A scratch directory for one suite's cases, removed when they end. Each
    suite makes its own, so suites running at the same time share none of it."""
    with tempfile.TemporaryDirectory() as directory:
        yield Path(directory)


@contextlib.contextmanager
def a_process_that_looks_like_a_supervisor(workspace: Path, agent: str,
                                          agent_argument=None, equals_form=False):
    """A live process whose command line is a supervisor's for `agent`.

    The identity check reads the command line, so the process has to have a
    real one: a file actually NAMED handoff-supervisor.py, run with --agent.
    It sleeps; nothing about the supervisor's behaviour is being tested here,
    only that it can be recognised.
    """
    stub_directory = workspace / f"looks-like-a-supervisor-for-{agent}"
    stub_directory.mkdir(parents=True, exist_ok=True)
    stub = stub_directory / "handoff-supervisor.py"
    stub.write_text("import time\ntime.sleep(120)\n", encoding="utf-8")
    named = agent if agent_argument is None else agent_argument
    arguments = ([f"--agent={named}"] if equals_form else ["--agent", named])
    process = subprocess.Popen(  # pylint: disable=consider-using-with
        [sys.executable, str(stub), *arguments, "--cd", str(stub_directory)])
    try:
        yield process
    finally:
        process.kill()
        process.wait()


def git_in(arguments, cwd):
    completed = subprocess.run(["git", *arguments], cwd=str(cwd),
                               capture_output=True, text=True, check=False)
    if completed.returncode != 0 and arguments[0] not in ("merge",):
        raise AssertionError(f"git {' '.join(arguments)} failed: {completed.stderr}")
    return completed


class StubLaunchedSession:
    """A launched session's stand-in for the in-process cases: poll() reports
    exit_code once the session has ended, and terminate() ends it, as a real
    session's returncode is set only when its end is observed."""

    def __init__(self, exit_code, ended=True):
        self.returncode = None
        self.exit_code = exit_code
        self.ended = ended

    def poll(self):
        if self.ended:
            self.returncode = self.exit_code
        return self.returncode

    def terminate(self):
        self.ended = True

    def kill(self):
        self.ended = True

    def wait(self, timeout=None):
        return self.poll()


@contextlib.contextmanager
def supervisor_names_replaced(**replacements):
    """Replace module-level names the supervisor looks up when it runs — its
    functions, and `input`, which it otherwise finds in builtins — and a
    terminal on stdin when `stdin_isatty` is given; everything is put back."""
    stdin_isatty = replacements.pop("stdin_isatty", None)
    missing = object()
    saved = {name: supervisor.__dict__.get(name, missing) for name in replacements}
    saved_stdin = sys.stdin
    for name, value in replacements.items():
        setattr(supervisor, name, value)
    if stdin_isatty is not None:
        sys.stdin = SimpleNamespace(isatty=lambda: stdin_isatty)
    try:
        yield
    finally:
        sys.stdin = saved_stdin
        for name, value in saved.items():
            if value is missing:
                delattr(supervisor, name)
            else:
                setattr(supervisor, name, value)


def print_summary_and_exit_nonzero_if_any_case_failed():
    print()
    if failures:
        print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
        sys.exit(1)
    print("all cases passed")
