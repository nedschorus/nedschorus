#!/usr/bin/env python3
"""What the handoff-supervisor suites beside this file share.

Each suite loads this file by path in a process of its own, so each gets its
own copy of the supervisor module: the cases patch the module's globals, and
two suites sharing one copy would see each other's patches.

Loading it puts in place, for the rest of the process, the sandboxes every
case relies on: a scratch HOME, so no launch writes the real ~/.claude.json;
an ssh first on PATH that never reaches ned-box, an empty
directory standing in for the overview reminders' marks, and a directory of
the process's own for the agent-binary update lock.

Not a test file: its name ends `-test-fixture.py` rather than `-test.py`, so
scripts/run-all-test-suites.py does not run it as a suite of its own.
"""

import atexit
import builtins
import contextlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

# This fixture sits at nn-systems/handoff/tests/, beside the suites, so the
# system they test is one directory up and the repository root is three.
# SYSTEM_DIRECTORY and REPOSITORY_ROOT name those depths once each; a
# with_name() lookup here would resolve inside tests/ and find nothing.
SYSTEM_DIRECTORY = Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = SYSTEM_DIRECTORY.parent.parent

SCRIPT_PATH = SYSTEM_DIRECTORY / "handoff-supervisor.py"

# No case may write the real ~/.claude.json: every agent-session launch writes
# Claude Code's onboarding presets into it, in this process and in every
# supervisor the cases start. HOME is a scratch directory for this process and
# every process it starts, set before the supervisor is loaded so its paths
# under HOME land there too. Git still reads the real ~/.gitconfig, for the
# identity the cases' commits need.
REAL_GIT_GLOBAL_CONFIG = Path.home() / ".gitconfig"
os.environ.setdefault("GIT_CONFIG_GLOBAL", str(REAL_GIT_GLOBAL_CONFIG))
SCRATCH_HOME_DIRECTORY = Path(tempfile.mkdtemp(prefix="handoff-supervisor-test-home-"))
atexit.register(shutil.rmtree, SCRATCH_HOME_DIRECTORY, True)
os.environ["HOME"] = str(SCRATCH_HOME_DIRECTORY)
SCRATCH_CLAUDE_JSON_PATH = SCRATCH_HOME_DIRECTORY / ".claude.json"

_spec = importlib.util.spec_from_file_location("handoff_supervisor", SCRIPT_PATH)
supervisor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(supervisor)

# The supervisor refuses to start without the agent-seat's GitHub token, read from
# ~/.config/nedsnodes/<account>.token, so the scratch HOME holds a made-up token for
# each account an agent-seat can act as, taken from the supervisor's own table. Never a
# real credential.
FIXTURE_GITHUB_TOKEN_BY_ACCOUNT = {
    account: f"github_pat_{account.upper().replace('-', '_')}_TEST_ONLY_not-a-real-credential"
    for account in {*supervisor.AGENT_SEAT_GITHUB_ACCOUNTS_OTHER_THAN_THE_MACHINE_DEFAULT.values(),
                    "ubuntu-claude", "mac-claude"}}
(SCRATCH_HOME_DIRECTORY / ".config" / "nedsnodes").mkdir(parents=True)
for _account, _token in FIXTURE_GITHUB_TOKEN_BY_ACCOUNT.items():
    (SCRATCH_HOME_DIRECTORY / ".config" / "nedsnodes" / f"{_account}.token").write_text(
        _token + "\n", encoding="utf-8")

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
    "#!/bin/sh\necho 'ssh: this nc-test-suite never reaches ned-box' >&2\nexit 255\n",
    encoding="utf-8")
(SSH_THAT_NEVER_REACHES_NED_BOX_DIRECTORY / "ssh").chmod(0o755)
os.environ["PATH"] = (f"{SSH_THAT_NEVER_REACHES_NED_BOX_DIRECTORY}{os.pathsep}"
                      f"{os.environ.get('PATH', '')}")

# The agent-binary update cases take the machine-wide update lock, so the lock
# is pointed into a directory of this process's own: a suite run must neither
# skip because a real update holds the lock nor make a real update skip.
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


STAND_IN_SUPERVISOR_READY_LINE = "stand-in supervisor running"


@contextlib.contextmanager
def a_process_that_looks_like_a_supervisor(workspace: Path, agent: str,
                                          agent_argument=None, equals_form=False,
                                          launched_through=None):
    """A live process whose command line is a supervisor's for `agent`.

    The identity check reads the command line, so the process has to have a
    real one: a file actually NAMED handoff-supervisor.py, run with --agent.
    It sleeps; nothing about the supervisor's behaviour is being tested here,
    only that it can be recognised.

    Yields only once the stand-in prints its ready line: Popen can return while
    the child is still inside exec, when `ps -o args=` shows `[python3]`, and a
    real supervisor writes its pid to the lock only once it is running.
    `launched_through`, when given, is the command run in its place, with the
    stand-in's command as a JSON list in STAND_IN_SUPERVISOR_COMMAND rather than
    on its own command line, which would look like a supervisor's: a case uses
    it to delay the stand-in's exec, or to stop it from ever running. Raises
    RuntimeError when the process ends without printing the ready line.
    """
    stub_directory = workspace / f"looks-like-a-supervisor-for-{agent}"
    stub_directory.mkdir(parents=True, exist_ok=True)
    stub = stub_directory / "handoff-supervisor.py"
    stub.write_text(f"import time\nprint({STAND_IN_SUPERVISOR_READY_LINE!r}, flush=True)\n"
                    "time.sleep(120)\n", encoding="utf-8")
    named = agent if agent_argument is None else agent_argument
    arguments = ([f"--agent={named}"] if equals_form else ["--agent", named])
    command = [sys.executable, str(stub), *arguments, "--cd", str(stub_directory)]
    environment = None
    if launched_through:
        environment = {**os.environ, "STAND_IN_SUPERVISOR_COMMAND": json.dumps(command)}
        command = list(launched_through)
    process = subprocess.Popen(  # pylint: disable=consider-using-with
        command, env=environment, stdout=subprocess.PIPE, text=True)
    try:
        first_line = process.stdout.readline().rstrip("\n")
        if first_line != STAND_IN_SUPERVISOR_READY_LINE:
            exit_status = process.wait() if first_line == "" else "none yet, it is still running"
            raise RuntimeError(
                f"the stand-in supervisor for {agent} (process {process.pid}) never printed "
                f"{STAND_IN_SUPERVISOR_READY_LINE!r}: its first line was {first_line!r} and its "
                f"exit status is {exit_status}, so no case can use it as a running supervisor")
        yield process
    finally:
        process.kill()
        process.wait()
        process.stdout.close()


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
    terminal on stdin when `stdin_isatty` is given; everything is put back.

    Raises NameError, replacing nothing, for a name that is neither the
    supervisor's own nor a builtin: a stub under a name the supervisor no
    longer defines would replace nothing, and the real code would run."""
    stdin_isatty = replacements.pop("stdin_isatty", None)
    unknown = sorted(name for name in replacements
                     if name not in supervisor.__dict__ and not hasattr(builtins, name))
    if unknown:
        raise NameError(f"supervisor_names_replaced: {', '.join(unknown)} not defined in "
                        f"{SCRIPT_PATH} nor a builtin, so a stub under that name replaces nothing")
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
