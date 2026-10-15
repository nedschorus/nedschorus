#!/usr/bin/env python3
"""Tests for scripts/git-client-side-hooks/pre-push, the hook that refuses to
push a branch that conflicts with main, or whose selective test run has a
failing suite, and for the Python files it runs,
scripts/git-client-side-hooks-pre-push-conflict-check.py and
scripts/git-client-side-hooks-pre-push-selective-test-run.py.

Run: python3 scripts/git-client-side-hooks-pre-push-test.py
Prints one line per case and exits non-zero if any case fails.

Every push case pushes with real git, from throwaway clones of throwaway bare
repositories under a temporary directory. Each clone's own core.hooksPath
points at a copy of the hooks laid out as this checkout lays them out, under
the temporary directory:
    <layout>/scripts/git-client-side-hooks/pre-push
    <layout>/scripts/git-client-side-hooks-pre-push-conflict-check.py
    <layout>/scripts/branch-conflict-check.py
    <layout>/scripts/git-client-side-hooks-pre-push-selective-test-run.py
    <layout>/scripts/run-all-test-suites.py, always a fake that passes
    unless a case gives another fake; the real one is never run by a push here
    <layout>/nc-systems/general-tools/git-machine-readable-output-runner-and-parser-common.py
So each case runs exactly what git runs on a seat's push. A case that needs
the conflict check to misbehave puts a fake check at the check's path, and
leaves the real one alone. No real repository's config is read or written:
global and system git config are shut out, and every GIT_ variable is
removed from each case's environment.

The hook must never stop a push it should let through (user, 2026-09-23:
"Messing up how git works or how we push is a big problem"), so most cases
here are pushes that must go through, one for each way the check can fail.
Every push runs under an outer timeout in its own process group, so a hook
that hangs fails its case instead of wedging the suite.
"""

import contextlib
import importlib.util
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import types
from pathlib import Path

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
HOOK_DIRECTORY_NAME = "git-client-side-hooks"
PRE_PUSH_HOOK = SCRIPTS_DIRECTORY / HOOK_DIRECTORY_NAME / "pre-push"
PREPARE_COMMIT_MSG_HOOK = SCRIPTS_DIRECTORY / HOOK_DIRECTORY_NAME / "prepare-commit-msg"
CONFLICT_CHECK_RUNNER = SCRIPTS_DIRECTORY / "git-client-side-hooks-pre-push-conflict-check.py"
MUTATION_TESTING_WORKTREE_CHECK = (SCRIPTS_DIRECTORY / "git-client-side-hooks-pre-push-mutation-"
                                   "testing-worktree-push-refusal.py")
REAL_CONFLICT_CHECK = SCRIPTS_DIRECTORY / "branch-conflict-check.py"
SELECTIVE_TEST_RUN_CHECK = SCRIPTS_DIRECTORY / "git-client-side-hooks-pre-push-selective-test-run.py"
REAL_TEST_SUITES_RUNNER = SCRIPTS_DIRECTORY / "run-all-test-suites.py"
GIT_OUTPUT_MODULE_RELATIVE_PATH = Path(
    "nc-systems/general-tools/git-machine-readable-output-runner-and-parser-common.py")

TIME_BUDGET_VARIABLE = "NEDSCHORUS_PRE_PUSH_CONFLICT_CHECK_SECONDS"
FAKE_CHECK_LOG_VARIABLE = "PRE_PUSH_TEST_FAKE_CHECK_LOG"
FAKE_TEST_SUITES_RUNNER_LOG_VARIABLE = "PRE_PUSH_TEST_FAKE_TEST_SUITES_RUNNER_LOG"
SELECTIVE_TEST_RUN_BUDGET_VARIABLE = "NEDSCHORUS_PRE_PUSH_SELECTIVE_TEST_RUN_SECONDS"
SESSION_VARIABLE = "CLAUDE_CODE_BRIDGE_SESSION_ID"
LOCAL_SESSION_VARIABLE = "CLAUDE_CODE_SESSION_ID"
FAKE_SESSION = "session_0FakePrePushTestSessionAAAA"
# The hook is POSIX sh; ned-box's /bin/sh is dash, so the hook is run under
# both where both exist.
SHELLS_FOR_THE_HOOK = [shell for shell in ("/bin/sh", "/bin/dash")
                       if os.path.exists(shell)]

OUTER_PUSH_TIMEOUT_SECONDS = 30
# A hanging fake check sleeps this long. Longer than the outer timeout, so a
# hook that fails to stop it still fails its case; short enough that one
# missed by every cleanup exits on its own soon after the suite does.
FAKE_HANG_SECONDS = 90
HANGING_CHECK_BUDGET_SECONDS = "1"
HANGING_CASE_WALL_CLOCK_LIMIT_SECONDS = 15

REFUSAL_HEADER = "pre-push: branch %s conflicts with origin/main; this push is refused."
CLOSING_INSTRUCTION = "Once the merge is committed, push again."
# The hooks' own texts, copied here rather than imported, so a change to a
# text fails a case.
TELL_USER_LINE = ("Tell the user this whole message, including any error printed "
                  "just above it: the next push on this machine may go unchecked "
                  "the same way.")
RERUN_VERDICT_LINE = ("If that run also prints no VERDICT line, tell the user this "
                      "whole message and what that run printed.")
NO_BRANCH_CHECKED = ("so this push goes ahead with none of its branches checked for "
                     "conflicts with origin/main: %s.")
SHORT_COMMIT_LENGTH = 12


def hand_check_line(branch, commit):
    return ("Check %s by hand from your worktree: python3 "
            "scripts/branch-conflict-check.py --head %s"
            % (branch, commit[:SHORT_COMMIT_LENGTH]))


def branch_entry(branch, commit):
    return "%s (%s)" % (branch, commit[:SHORT_COMMIT_LENGTH])

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


# --- Fake conflict checks -------------------------------------------------
# Each is written to <layout>/scripts/branch-conflict-check.py. Each first
# appends its arguments to the file FAKE_CHECK_LOG_VARIABLE names, so a case
# can tell whether the hook ran the check at all, and on which commit.

FAKE_CHECK_PREAMBLE = """\
import os, sys
FAKE_HANG_SECONDS = %d
_log = os.environ.get("%s")
if _log:
    with open(_log, "a") as _handle:
        _handle.write(" ".join(sys.argv[1:]) + "\\n")
""" % (FAKE_HANG_SECONDS, FAKE_CHECK_LOG_VARIABLE)

FAKE_CHECK_ALWAYS_CONFLICT = FAKE_CHECK_PREAMBLE + """\
print("VERDICT: CONFLICT -- fake conflict for the test.")
print("Merge origin/main into the branch by hand, with the frozen head as first parent.")
sys.exit(1)
"""

FAKE_CHECK_CRASHES = FAKE_CHECK_PREAMBLE + """\
raise RuntimeError("fake crash inside the conflict check")
"""

FAKE_CHECK_NO_ANSWER = FAKE_CHECK_PREAMBLE + """\
print("UNFETCHED: fake no-answer line from the check.")
sys.exit(2)
"""

FAKE_CHECK_UNEXPECTED_STATUS = FAKE_CHECK_PREAMBLE + """\
print("VERDICT: CONFLICT -- printed, but with a status the hook must not trust.")
sys.exit(7)
"""

FAKE_CHECK_CONFLICT_TEXT_EXIT_ZERO = FAKE_CHECK_PREAMBLE + """\
print("VERDICT: CONFLICT -- printed, but the check exited 0.")
sys.exit(0)
"""

FAKE_CHECK_HANGS = FAKE_CHECK_PREAMBLE + """\
import time
time.sleep(FAKE_HANG_SECONDS)
"""

# The shape a real hang takes: the check's child (its git fetch) holds the
# output pipe open, so stopping the check alone would leave the pipe open,
# and the child running. The child's pid is written beside the log, so the
# case can see that the whole process group was stopped.
FAKE_CHECK_HANGS_WITH_CHILD = FAKE_CHECK_PREAMBLE + """\
import subprocess, time
_child = subprocess.Popen([sys.executable, "-c",
                           "import time; time.sleep(%d)" % FAKE_HANG_SECONDS])
with open(_log + ".child-pid", "w") as _handle:
    _handle.write(str(_child.pid))
time.sleep(FAKE_HANG_SECONDS)
"""

# git removes its lock files on SIGTERM and cannot on SIGKILL, so a stopped
# check must be sent SIGTERM first. This fake records that it was.
FAKE_CHECK_RECORDS_SIGTERM = FAKE_CHECK_PREAMBLE + """\
import signal, time
def _on_sigterm(_signal_number, _frame):
    with open(_log, "a") as _handle:
        _handle.write("received SIGTERM\\n")
    sys.exit(143)
signal.signal(signal.SIGTERM, _on_sigterm)
time.sleep(FAKE_HANG_SECONDS)
"""

FAKE_CHECK_IGNORES_SIGTERM = FAKE_CHECK_PREAMBLE + """\
import signal, time
signal.signal(signal.SIGTERM, signal.SIG_IGN)
time.sleep(FAKE_HANG_SECONDS)
"""


# --- Fake run-all-test-suites.py files -------------------------------------
# Each is written to <layout>/scripts/run-all-test-suites.py. Each first
# appends its arguments, as one JSON list, to the file
# FAKE_TEST_SUITES_RUNNER_LOG_VARIABLE names, so a case can tell whether the
# selective test run started, and with which arguments.

SELECTIVE_TEST_RUN_STARTING = "pre-push: starting the selective test run on "
SELECTIVE_TEST_RUN_PASSED = "pre-push: the selective test run passed. "
SELECTIVE_TEST_RUN_REFUSED = ("pre-push: a test suite failed in the selective test run, so this "
                              "push is refused. ")
SELECTIVE_TEST_RUN_NOT_RUN_END = ", so this push goes ahead without the selective test run"
SELECTIVE_TEST_RUN_HAND_RUN_LINE = (
    "Run it by hand from your worktree: python3 scripts/run-all-test-suites.py "
    "--only-suites-whose-recorded-inputs-changed-since origin/main --wait-for-lock-seconds 600")
FAKE_LOG_DIRECTORY = "/fake/run-all-test-suites-logs"
FAKE_FAILING_SUITE_LINE = "FAIL scripts/fake-failing-test.py exit 1 — log /fake/fake-failing-test.log"
FAKE_FAILED_SUMMARY = "SUMMARY: 2 passed, 1 failed, 3 total; 0 cases skipped in 0 suites"
FAKE_PASSED_SUMMARY = "SUMMARY: 3 passed, 0 failed, 3 total; 0 cases skipped in 0 suites"
# The real runner's refusal when told to wait 0 seconds for a held lock: the
# holder on the first line, then advice to the runner's own caller.
FAKE_LOCK_HOLDER_LINE = ("run-all-test-suites: not run — another run holds /fake/lock: "
                         "process 4242, checkout /fake/other.")
FAKE_LOCK_ADVICE_LINE = ("To wait for the lock, run this again with --wait-for-lock-seconds 600, "
                         "instead of retrying in a loop.")

FAKE_TEST_SUITES_RUNNER_PREAMBLE = """\
import json, os, sys
FAKE_HANG_SECONDS = %d
_log = os.environ.get("%s")
if _log:
    with open(_log, "a") as _handle:
        _handle.write(json.dumps(sys.argv[1:]) + "\\n")
print("run-all-test-suites: /fake at abc (clean); 9 suites listed by git; -j 4; logs in %s",
      flush=True)
""" % (FAKE_HANG_SECONDS, FAKE_TEST_SUITES_RUNNER_LOG_VARIABLE, FAKE_LOG_DIRECTORY)

FAKE_TEST_SUITES_RUNNER_PASSES = FAKE_TEST_SUITES_RUNNER_PREAMBLE + """\
print("PASS scripts/a-test.py (0.1s)")
print(%r)
""" % FAKE_PASSED_SUMMARY

FAKE_TEST_SUITES_RUNNER_FAILS = FAKE_TEST_SUITES_RUNNER_PREAMBLE + """\
print("FAIL scripts/fake-failing-test.py exit 1 (0.1s)")
print("")
print("1 failed:")
print(%r)
print(%r)
sys.exit(1)
""" % (FAKE_FAILING_SUITE_LINE, FAKE_FAILED_SUMMARY)

FAKE_TEST_SUITES_RUNNER_LOCKED = FAKE_TEST_SUITES_RUNNER_PREAMBLE + """\
print(%r, file=sys.stderr)
print(%r, file=sys.stderr)
sys.exit(3)
""" % (FAKE_LOCK_HOLDER_LINE, FAKE_LOCK_ADVICE_LINE)

FAKE_TEST_SUITES_RUNNER_CANNOT_START = FAKE_TEST_SUITES_RUNNER_PREAMBLE + """\
print("run-all-test-suites: not run — /fake is not a checkout's top directory", file=sys.stderr)
sys.exit(2)
"""

FAKE_TEST_SUITES_RUNNER_KILLED = FAKE_TEST_SUITES_RUNNER_PREAMBLE + """\
import signal
os.kill(os.getpid(), signal.SIGKILL)
"""

FAKE_OVERRUN_STDERR_LINE = "run-all-test-suites: scripts/slow-test.py is still running"

# The shape a real overrun takes: the suites the run started keep running, so
# stopping the run alone would leave them. One child stays in the run's process
# group; the other starts its own session, as scripts/run-codex-task-from-brief-test.py's
# children do, so stopping the group alone would miss it. Each child's pid is
# written beside the log, so the case can see that both were stopped.
FAKE_TEST_SUITES_RUNNER_HANGS_WITH_CHILD = FAKE_TEST_SUITES_RUNNER_PREAMBLE + (
    "print(%r, file=sys.stderr, flush=True)\n" % FAKE_OVERRUN_STDERR_LINE) + """\
import subprocess, time
_sleeper = [sys.executable, "-c", "import time; time.sleep(%d)" % FAKE_HANG_SECONDS]
_child = subprocess.Popen(_sleeper)
_detached = subprocess.Popen(_sleeper, start_new_session=True, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
with open(_log + ".child-pid", "w") as _handle:
    _handle.write(str(_child.pid))
with open(_log + ".detached-child-pid", "w") as _handle:
    _handle.write(str(_detached.pid))
time.sleep(FAKE_HANG_SECONDS)
"""

# An uncaught exception after the run has started: Python exits 1, as a failed
# suite does, but the run prints no SUMMARY line.
FAKE_RUNNER_CRASH_ERROR = "OSError: [Errno 28] No space left on device: '/fake/logs'"
FAKE_TEST_SUITES_RUNNER_CRASHES = FAKE_TEST_SUITES_RUNNER_PREAMBLE + """\
raise OSError(28, "No space left on device", "/fake/logs")
"""

# The real runner writes its report and run record after printing SUMMARY, so
# a write that fails there exits 1 after a SUMMARY that counts no failure.
FAKE_TEST_SUITES_RUNNER_CRASHES_AFTER_SUMMARY = FAKE_TEST_SUITES_RUNNER_PREAMBLE + """\
print(%r, flush=True)
raise OSError(28, "No space left on device", "/fake/logs")
""" % FAKE_PASSED_SUMMARY

# The real runner's refusal when the signal sandbox cannot start: the cause is
# on the first line, and the lines after it advise the runner's own caller.
FAKE_SANDBOX_REFUSAL_FIRST_LINE = ("run-all-test-suites: not run — the signal sandbox could not "
                                   "start: bwrap missing from PATH")
FAKE_SANDBOX_REFUSAL_LAST_LINE = ("On macOS, report the reason above to the user: the suites need "
                                  "sandbox-exec to refuse their signals to processes outside the "
                                  "sandbox.")
FAKE_TEST_SUITES_RUNNER_SANDBOX_CANNOT_START = FAKE_TEST_SUITES_RUNNER_PREAMBLE + """\
print(%r, file=sys.stderr)
print("Each suite runs inside the signal sandbox (bwrap on Linux, sandbox-exec on macOS).",
      file=sys.stderr)
print(%r, file=sys.stderr)
sys.exit(2)
""" % (FAKE_SANDBOX_REFUSAL_FIRST_LINE, FAKE_SANDBOX_REFUSAL_LAST_LINE)


# --- Layouts and repositories ---------------------------------------------

def make_layout(parent, name, conflict_check=REAL_CONFLICT_CHECK,
                runner_text=None, include_runner=True, mutation_testing_worktree_check_text=None,
                include_mutation_testing_worktree_check=True,
                test_suites_runner_text=None, include_test_suites_runner=True,
                selective_test_run_check_text=None, include_selective_test_run_check=True):
    """A copy of this checkout's hooks, laid out as the hook expects.

    conflict_check is a Path to copy, a string of fake check source, or None
    for no check at all. runner_text replaces the Python file the hook runs
    for the conflict check. test_suites_runner_text replaces the fake
    run-all-test-suites.py that passes, and selective_test_run_check_text the
    selective test run check. Returns the hooks directory, for core.hooksPath.
    """
    scripts = parent / name / "scripts"
    hooks = scripts / HOOK_DIRECTORY_NAME
    hooks.mkdir(parents=True)
    for hook in (PRE_PUSH_HOOK, PREPARE_COMMIT_MSG_HOOK):
        shutil.copy2(hook, hooks / hook.name)
    runner = scripts / CONFLICT_CHECK_RUNNER.name
    if runner_text is not None:
        runner.write_text(runner_text)
    elif include_runner:
        shutil.copy2(CONFLICT_CHECK_RUNNER, runner)
    mutation_testing_worktree_check = scripts / MUTATION_TESTING_WORKTREE_CHECK.name
    if mutation_testing_worktree_check_text is not None:
        mutation_testing_worktree_check.write_text(mutation_testing_worktree_check_text)
    elif include_mutation_testing_worktree_check:
        shutil.copy2(MUTATION_TESTING_WORKTREE_CHECK, mutation_testing_worktree_check)
    selective_test_run_check = scripts / SELECTIVE_TEST_RUN_CHECK.name
    if selective_test_run_check_text is not None:
        selective_test_run_check.write_text(selective_test_run_check_text)
    elif include_selective_test_run_check:
        shutil.copy2(SELECTIVE_TEST_RUN_CHECK, selective_test_run_check)
    if include_test_suites_runner:
        (scripts / REAL_TEST_SUITES_RUNNER.name).write_text(
            test_suites_runner_text if test_suites_runner_text is not None
            else FAKE_TEST_SUITES_RUNNER_PASSES)
    if isinstance(conflict_check, Path):
        shutil.copy2(conflict_check, scripts / REAL_CONFLICT_CHECK.name)
        module = parent / name / GIT_OUTPUT_MODULE_RELATIVE_PATH
        module.parent.mkdir(parents=True)
        shutil.copy2(SCRIPTS_DIRECTORY.parent / GIT_OUTPUT_MODULE_RELATIVE_PATH, module)
    elif isinstance(conflict_check, str):
        (scripts / REAL_CONFLICT_CHECK.name).write_text(conflict_check)
    return hooks


class PushResult:
    def __init__(self, returncode, stdout, stderr, seconds, timed_out):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.seconds = seconds
        self.timed_out = timed_out

    def describe(self):
        return ("exit %s after %.1fs%s; stderr %r"
                % (self.returncode, self.seconds,
                   " (TIMED OUT)" if self.timed_out else "", self.stderr[-1500:]))


class Scenario:
    """A bare origin, one clone wired to a layout's hooks, and branches.

    main holds shared.txt. Three branches are cut from the first commit:
      conflicting:        changes shared.txt one way
      clean:              adds a different file
      clean-second:       adds another different file
    Then main changes shared.txt the other way and is pushed, so
    `conflicting` conflicts with origin/main and the other two do not.
    Every setup push uses --no-verify, so the setup never depends on the hook
    under test.
    """

    def __init__(self, parent, name, hooks, path_override=None):
        self.parent = parent
        self.name = name
        self.origin = parent / (name + "-origin.git")
        self.clone = parent / (name + "-clone")
        self.empty_global_config = parent / (name + "-empty-gitconfig")
        self.empty_global_config.write_text("")
        self.fake_check_log = parent / (name + "-fake-check-log.txt")
        self.fake_test_suites_runner_log = parent / (name + "-fake-test-suites-runner-log.txt")
        self.path_override = path_override
        self.extra_environment = {}
        self.git(parent, "init", "--quiet", "--bare", str(self.origin))
        self.git(parent, "init", "--quiet", "--initial-branch=main", str(self.clone))
        self.git(self.clone, "config", "user.name", "Pre-push Test")
        self.git(self.clone, "config", "user.email", "pre-push-test@example.invalid")
        self.git(self.clone, "remote", "add", "origin", str(self.origin))
        self.git(self.clone, "config", "core.hooksPath", str(hooks))
        self.commit("shared.txt", "first line\n", "Base")
        self.base = self.head()
        self.git(self.clone, "push", "--quiet", "--no-verify", "origin", "main")
        self.git(self.clone, "branch", "conflicting", self.base)
        self.git(self.clone, "branch", "clean", self.base)
        self.git(self.clone, "branch", "clean-second", self.base)
        self.on_branch("conflicting", "shared.txt", "the branch's line\n", "Branch side")
        self.on_branch("clean", "clean.txt", "clean\n", "Clean work")
        self.on_branch("clean-second", "clean-second.txt", "clean too\n", "More clean work")
        self.git(self.clone, "switch", "--quiet", "main")
        self.commit("shared.txt", "main's line\n", "Main side")
        self.git(self.clone, "push", "--quiet", "--no-verify", "origin", "main")
        self.git(self.clone, "fetch", "--quiet", "origin")

    def environment(self):
        env = {key: value for key, value in os.environ.items()
               if not key.startswith("GIT_")}
        env.pop(SESSION_VARIABLE, None)
        env.pop(LOCAL_SESSION_VARIABLE, None)
        env["GIT_CONFIG_GLOBAL"] = str(self.empty_global_config)
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env[FAKE_CHECK_LOG_VARIABLE] = str(self.fake_check_log)
        env[FAKE_TEST_SUITES_RUNNER_LOG_VARIABLE] = str(self.fake_test_suites_runner_log)
        if self.path_override is not None:
            env["PATH"] = self.path_override
        env.update(self.extra_environment)
        return env

    def git(self, cwd, *arguments):
        environment = self.environment()
        # Setup and inspection run with the real PATH, even in a case that
        # takes python3 off PATH for the hook under test.
        environment["PATH"] = os.environ.get("PATH", "")
        completed = subprocess.run(
            ["git", *arguments], cwd=str(cwd), env=environment,
            capture_output=True, text=True, timeout=60)
        if completed.returncode != 0:
            raise RuntimeError("git %s failed: %s" % (" ".join(arguments),
                                                      completed.stderr.strip()))
        return completed.stdout.strip()

    def commit(self, filename, content, message, cwd=None):
        work_tree = cwd or self.clone
        (Path(work_tree) / filename).write_text(content)
        self.git(work_tree, "add", filename)
        self.git(work_tree, "commit", "--quiet", "-m", message)

    def on_branch(self, branch, filename, content, message):
        self.git(self.clone, "switch", "--quiet", branch)
        self.commit(filename, content, message)

    def head(self, revision="HEAD", cwd=None):
        return self.git(cwd or self.clone, "rev-parse", revision)

    def origin_ref(self, branch):
        """The commit origin holds for a branch, or None."""
        completed = subprocess.run(
            ["git", "--git-dir", str(self.origin), "rev-parse", "--verify",
             "--quiet", "refs/heads/" + branch],
            env={key: value for key, value in os.environ.items()
                 if not key.startswith("GIT_")},
            capture_output=True, text=True, timeout=30)
        return completed.stdout.strip() or None

    def push(self, *arguments, cwd=None):
        """git push with the hook live, bounded by an outer timeout."""
        started = time.monotonic()
        process = subprocess.Popen(
            ["git", "push", *arguments], cwd=str(cwd or self.clone),
            env=self.environment(), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            start_new_session=True)
        try:
            stdout, stderr = process.communicate(timeout=OUTER_PUSH_TIMEOUT_SECONDS)
            timed_out = False
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            try:
                stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                stdout, stderr = "", ""
            timed_out = True
            # The hook starts the check in its own session, out of reach of
            # the killpg above, so a check the hook failed to stop is found
            # by its path under this suite's temporary directory.
            try:
                subprocess.run(["pkill", "-KILL", "-f", str(self.parent)],
                               capture_output=True, timeout=30)
            except (OSError, subprocess.TimeoutExpired):
                pass
        return PushResult(process.returncode, stdout, stderr,
                          time.monotonic() - started, timed_out)

    def fake_test_suites_runner_calls(self):
        """The argument lists the fake run-all-test-suites.py was started with."""
        if not self.fake_test_suites_runner_log.exists():
            return []
        return [json.loads(line) for line in
                self.fake_test_suites_runner_log.read_text().splitlines() if line]

    def fake_check_calls(self):
        if not self.fake_check_log.exists():
            return []
        return [line for line in self.fake_check_log.read_text().splitlines() if line]


def process_gone_within(pid, seconds):
    """True when no process has this pid, waiting up to the given seconds."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False
        time.sleep(0.1)
    return False


def stop_leftover_process(pid):
    """Kill a process a failed case left running, so the suite leaks nothing."""
    try:
        os.kill(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def conflict_check_said_nothing(stderr):
    """True when every pre-push line is the selective test run's own start or pass line."""
    return all(line.startswith((SELECTIVE_TEST_RUN_STARTING, SELECTIVE_TEST_RUN_PASSED))
               for line in stderr.splitlines() if line.startswith("pre-push:"))


def went_through(result):
    return result.returncode == 0 and not result.timed_out


def was_refused(result):
    return result.returncode not in (0, None) and not result.timed_out


# --- The Python file's own functions ---------------------------------------

def load_runner_module():
    """The runner, compiled from source, never from a bytecode cache.

    A mutation test edits the file and reruns this suite, sometimes within
    the same second; a cached .pyc could then run the unmutated code.
    """
    source = CONFLICT_CHECK_RUNNER.read_text()
    module = types.ModuleType("pre_push_conflict_check_runner_under_test")
    module.__file__ = str(CONFLICT_CHECK_RUNNER)
    exec(compile(source, str(CONFLICT_CHECK_RUNNER), "exec"), module.__dict__)
    return module


def run_unit_cases():
    runner = load_runner_module()
    zeros = "0" * 40
    sha = "a" * 40
    other = "b" * 40
    pushed = "\n".join([
        "refs/heads/topic %s refs/heads/topic %s" % (sha, zeros),
        "(delete) %s refs/heads/gone %s" % (zeros, sha),
        "refs/tags/v1 %s refs/tags/v1 %s" % (sha, zeros),
        "refs/heads/main %s refs/heads/main %s" % (sha, other),
        "refs/heads/local %s refs/heads/renamed-on-push %s" % (other, zeros),
        "refs/notes/commits %s refs/notes/commits %s" % (sha, zeros),
        "a line git would never write",
        "(delete) %s refs/heads/sha256-gone %s" % ("0" * 64, sha),
        "",
    ])
    check("only branch pushes other than main and deletes are checked",
          runner.branches_to_check(pushed)
          == [("topic", sha), ("renamed-on-push", other)],
          repr(runner.branches_to_check(pushed)))
    check("an empty push checks nothing", runner.branches_to_check("") == [])

    default = runner.DEFAULT_TIME_BUDGET_SECONDS
    variable = runner.TIME_BUDGET_ENVIRONMENT_VARIABLE
    check("the time budget variable is the one this suite sets",
          variable == TIME_BUDGET_VARIABLE, variable)
    check("with no variable the budget is the default",
          runner.time_budget_seconds({}) == default)
    check("a positive number sets the budget",
          runner.time_budget_seconds({variable: "2.5"}) == 2.5)
    for bad in ("", "soon", "0", "-5", "nan-ish"):
        check("a budget of %r falls back to the default" % bad,
              runner.time_budget_seconds({variable: bad}) == default,
              repr(runner.time_budget_seconds({variable: bad})))
    check("the refusal status is not 1, which any crash also exits with",
          runner.EXIT_REFUSE_PUSH not in (0, 1, 2), repr(runner.EXIT_REFUSE_PUSH))

    # Message 7, an error the Python file catches, in both of its forms.
    import io
    error = RuntimeError("boom")
    stream = io.StringIO()
    runner.report_unexpected_error(stream, error, ["origin", "url"], pushed)
    check("an error after the pushed refs were read names each unchecked branch",
          stream.getvalue().splitlines() == [
              "pre-push: the pre-push conflict check failed with RuntimeError: boom, "
              + NO_BRANCH_CHECKED % ", ".join(
                  [branch_entry("topic", sha), branch_entry("renamed-on-push", other)]),
              hand_check_line("topic", sha),
              hand_check_line("renamed-on-push", other),
              TELL_USER_LINE],
          stream.getvalue())
    stream = io.StringIO()
    runner.report_unexpected_error(stream, error, ["origin", "url"], None)
    check("an error before the pushed refs were read says no branch was checked",
          stream.getvalue().splitlines() == [
              "pre-push: the pre-push conflict check failed with RuntimeError: boom "
              "before reading which branches this push sends, so this push goes ahead "
              "with none of its branches checked for conflicts with origin/main.",
              "For each branch this push sends to origin, other than main, run from "
              "your worktree: python3 scripts/branch-conflict-check.py --head "
              "<branch name>",
              TELL_USER_LINE],
          stream.getvalue())
    stream = io.StringIO()
    runner.report_unexpected_error(stream, error, ["backup", "url"], pushed)
    check("an error on a push to another remote names no branch, since none is checked",
          stream.getvalue() == "", stream.getvalue())

    # The shell part filters the pushed refs the same way: the same push, given
    # straight to the hook with the Python file missing, names exactly the
    # branches branches_to_check returns above, under sh and under dash.
    layout_parent = Path(tempfile.mkdtemp(prefix="pre-push-shell-filter-")).resolve()
    try:
        hooks = make_layout(layout_parent, "filter", conflict_check=None,
                            include_runner=False,
                            mutation_testing_worktree_check_text="import sys\nsys.exit(0)\n",
                            selective_test_run_check_text="import sys\nsys.exit(0)\n")
        expected_first_line_end = NO_BRANCH_CHECKED % ", ".join(
            [branch_entry("topic", sha), branch_entry("renamed-on-push", other)])
        for shell in SHELLS_FOR_THE_HOOK:
            def run_hook(remote, refs_text):
                return subprocess.run(
                    [shell, str(hooks / "pre-push"), remote, "url"],
                    input=refs_text, capture_output=True, text=True, timeout=30)
            completed = run_hook("origin", pushed)
            lines = completed.stderr.splitlines()
            check("%s: the shell part names the branches branches_to_check keeps"
                  % shell,
                  completed.returncode == 0 and bool(lines)
                  and lines[0].endswith(expected_first_line_end)
                  and lines[1:] == [hand_check_line("topic", sha),
                                    hand_check_line("renamed-on-push", other),
                                    TELL_USER_LINE],
                  completed.stderr)
            for label, refs_text in (
                    ("main", "refs/heads/main %s refs/heads/main %s\n" % (sha, other)),
                    ("a tag", "refs/tags/v1 %s refs/tags/v1 %s\n" % (sha, zeros)),
                    ("a deletion", "(delete) %s refs/heads/gone %s\n" % (zeros, sha))):
                completed = run_hook("origin", refs_text)
                check("%s: the shell part says nothing for a push of %s"
                      % (shell, label),
                      completed.returncode == 0 and completed.stderr == "",
                      completed.stderr)
            completed = run_hook("backup", pushed)
            check("%s: the shell part says nothing for a push to another remote"
                  % shell,
                  completed.returncode == 0 and completed.stderr == "",
                  completed.stderr)
    finally:
        shutil.rmtree(layout_parent, ignore_errors=True)


# --- Push cases ------------------------------------------------------------

def run_push_cases(scratch):
    # --- With the real conflict check ------------------------------------

    real = make_layout(scratch, "layout-real")
    scenario = Scenario(scratch, "real", real)

    result = scenario.push("origin", "clean")
    check("a clean branch is pushed", went_through(result), result.describe())
    check("and arrives at origin",
          scenario.origin_ref("clean") == scenario.head("clean"),
          repr(scenario.origin_ref("clean")))
    check("and the conflict check says nothing",
          conflict_check_said_nothing(result.stderr), result.describe())

    result = scenario.push("origin", "conflicting")
    check("a branch that conflicts with origin/main is refused",
          was_refused(result), result.describe())
    check("and never reaches origin", scenario.origin_ref("conflicting") is None,
          repr(scenario.origin_ref("conflicting")))
    check("the refusal names the branch",
          REFUSAL_HEADER % "conflicting" in result.stderr, result.describe())
    check("and passes on the check's own verdict and instructions",
          "VERDICT: CONFLICT" in result.stderr
          and "Merge origin/main into the branch by hand" in result.stderr,
          result.describe())
    check("and ends with the instruction to push again",
          CLOSING_INSTRUCTION in result.stderr, result.describe())
    check("and does not offer --no-verify", "--no-verify" not in result.stderr,
          result.describe())

    # A branch already on origin: the refused push must leave it where it was.
    scenario.git(scenario.clone, "switch", "--quiet", "-c", "pushed-then-conflicting",
                 scenario.base)
    scenario.commit("early.txt", "early\n", "Early work, pushed")
    scenario.git(scenario.clone, "push", "--quiet", "--no-verify", "origin",
                 "pushed-then-conflicting")
    early = scenario.head()
    scenario.commit("shared.txt", "another branch line\n", "Later work that conflicts")
    result = scenario.push("origin", "pushed-then-conflicting")
    check("a conflicting update to a branch origin already has is refused",
          was_refused(result), result.describe())
    check("and origin keeps the branch's earlier commit",
          scenario.origin_ref("pushed-then-conflicting") == early,
          repr(scenario.origin_ref("pushed-then-conflicting")))

    # The remedy the refusal gives: merge origin/main by hand, then push again.
    merge = subprocess.run(
        ["git", "merge", "--quiet", "origin/main"], cwd=str(scenario.clone),
        env=scenario.environment(), capture_output=True, text=True, timeout=60)
    check("(setup) the hand merge stops on the conflict", merge.returncode != 0,
          merge.stderr)
    (scenario.clone / "shared.txt").write_text("main's line\nanother branch line\n")
    scenario.git(scenario.clone, "add", "shared.txt")
    scenario.git(scenario.clone, "commit", "--quiet", "--no-edit")
    result = scenario.push("origin", "pushed-then-conflicting")
    check("after the hand merge the same branch is pushed",
          went_through(result), result.describe())

    result = scenario.push("origin", "clean-second", "conflicting")
    check("one push of a clean branch and a conflicting one is refused",
          was_refused(result), result.describe())
    check("and the refusal names the conflicting branch",
          REFUSAL_HEADER % "conflicting" in result.stderr, result.describe())
    check("and not the clean one",
          REFUSAL_HEADER % "clean-second" not in result.stderr, result.describe())
    check("and neither branch reaches origin",
          scenario.origin_ref("clean-second") is None
          and scenario.origin_ref("conflicting") is None,
          repr((scenario.origin_ref("clean-second"), scenario.origin_ref("conflicting"))))

    # Seats push from linked worktrees of their clone.
    conflicting_worktree = scratch / "real-worktree-conflicting"
    scenario.git(scenario.clone, "worktree", "add", "--quiet", "-b",
                 "worktree-conflicting", str(conflicting_worktree), scenario.base)
    scenario.commit("shared.txt", "a worktree's line\n", "Worktree side",
                    cwd=conflicting_worktree)
    result = scenario.push("origin", "worktree-conflicting", cwd=conflicting_worktree)
    check("from a linked worktree, a conflicting branch is refused",
          was_refused(result), result.describe())
    check("and the refusal names that worktree's branch",
          REFUSAL_HEADER % "worktree-conflicting" in result.stderr, result.describe())
    clean_worktree = scratch / "real-worktree-clean"
    scenario.git(scenario.clone, "worktree", "add", "--quiet", "-b",
                 "worktree-clean", str(clean_worktree), scenario.base)
    scenario.commit("worktree.txt", "w\n", "Worktree clean work", cwd=clean_worktree)
    result = scenario.push("origin", "worktree-clean", cwd=clean_worktree)
    check("from a linked worktree, a clean branch is pushed",
          went_through(result), result.describe())
    check("and arrives at origin as that worktree's commit",
          scenario.origin_ref("worktree-clean") == scenario.head(cwd=clean_worktree),
          repr(scenario.origin_ref("worktree-clean")))

    # --- What is not checked: a check that always says CONFLICT ------------

    always = make_layout(scratch, "layout-always-conflict",
                         conflict_check=FAKE_CHECK_ALWAYS_CONFLICT)
    scenario = Scenario(scratch, "skips", always)

    result = scenario.push("origin", "clean")
    check("(control) a check that says CONFLICT with exit 1 refuses the push",
          was_refused(result), result.describe())
    calls = scenario.fake_check_calls()
    check("and the check was asked about the pushed commit, by full hash, "
          "without --pull-request",
          calls == ["--head %s" % scenario.head("clean")], repr(calls))

    scenario.git(scenario.clone, "push", "--quiet", "--no-verify", "origin", "clean")
    scenario.fake_check_log.unlink()
    result = scenario.push("origin", "--delete", "clean")
    check("deleting a branch goes through", went_through(result), result.describe())
    check("without running the check", scenario.fake_check_calls() == [],
          repr(scenario.fake_check_calls()))
    check("and the branch is gone from origin", scenario.origin_ref("clean") is None)

    scenario.git(scenario.clone, "tag", "a-tag", scenario.head("conflicting"))
    result = scenario.push("origin", "a-tag")
    check("pushing a tag goes through", went_through(result), result.describe())
    check("without running the check", scenario.fake_check_calls() == [],
          repr(scenario.fake_check_calls()))

    scenario.git(scenario.clone, "switch", "--quiet", "main")
    scenario.commit("main-only.txt", "m\n", "More main")
    result = scenario.push("origin", "main")
    check("pushing main goes through", went_through(result), result.describe())
    check("without running the check", scenario.fake_check_calls() == [],
          repr(scenario.fake_check_calls()))

    backup = scratch / "skips-backup.git"
    scenario.git(scratch, "init", "--quiet", "--bare", str(backup))
    scenario.git(scenario.clone, "remote", "add", "backup", str(backup))
    result = scenario.push("backup", "conflicting")
    check("pushing to a remote not named origin goes through",
          went_through(result), result.describe())
    check("without running the check", scenario.fake_check_calls() == [],
          repr(scenario.fake_check_calls()))

    # --- Every way the check can fail lets the push go ---------------------

    def failing_check_case(label, fake_source, expected_text, silent=False,
                           budget=None):
        hooks = make_layout(scratch, "layout-" + label, conflict_check=fake_source)
        failing = Scenario(scratch, label, hooks)
        if budget is not None:
            failing.extra_environment[TIME_BUDGET_VARIABLE] = budget
        outcome = failing.push("origin", "conflicting")
        check("%s: the push goes through" % label, went_through(outcome),
              outcome.describe())
        check("%s: and the branch reaches origin" % label,
              failing.origin_ref("conflicting") == failing.head("conflicting"),
              repr(failing.origin_ref("conflicting")))
        if silent:
            check("%s: and the conflict check says nothing" % label,
                  conflict_check_said_nothing(outcome.stderr), outcome.describe())
        else:
            check("%s: and says why it did not check" % label,
                  expected_text in outcome.stderr, outcome.describe())
        return outcome

    missing = make_layout(scratch, "layout-check-missing", conflict_check=None)
    failing = Scenario(scratch, "check-missing", missing)
    outcome = failing.push("origin", "conflicting")
    conflicting_commit = failing.head("conflicting")
    check("check missing: the push goes through", went_through(outcome),
          outcome.describe())
    check("check missing: and says the check is missing, naming the branch",
          "branch-conflict-check.py is missing, "
          + NO_BRANCH_CHECKED % branch_entry("conflicting", conflicting_commit)
          in outcome.stderr, outcome.describe())
    check("check missing: and gives the hand check and tells the user",
          hand_check_line("conflicting", conflicting_commit) + "\n" + TELL_USER_LINE
          in outcome.stderr, outcome.describe())

    def gave_no_verdict(label, outcome, reason):
        lines = outcome.stderr.splitlines()
        start = ("pre-push: branch conflicting was not checked for conflicts with "
                 "origin/main, because scripts/branch-conflict-check.py gave no "
                 "verdict: %s" % reason)
        index = next((i for i, line in enumerate(lines) if line.startswith(start)), None)
        check("%s: says which branch went unchecked and why" % label,
              index is not None, outcome.describe())
        if index is not None:
            check("%s: then the hand check and the line telling the user" % label,
                  len(lines) > index + 2
                  and lines[index + 1].startswith(
                      "Check conflicting by hand from your worktree: python3 "
                      "scripts/branch-conflict-check.py --head ")
                  and lines[index + 2] == TELL_USER_LINE,
                  outcome.describe())

    outcome = failing_check_case("check-crashes", FAKE_CHECK_CRASHES,
                                 "exited 1 without a VERDICT: CONFLICT line")
    gave_no_verdict("check-crashes", outcome,
                    "it exited 1 without a VERDICT: CONFLICT line")
    outcome = failing_check_case(
        "check-no-answer", FAKE_CHECK_NO_ANSWER,
        "pre-push: branch conflicting was not checked for conflicts with "
        "origin/main, because scripts/branch-conflict-check.py could not decide; "
        "its report follows.")
    check("check-no-answer: and passes on the check's own lines",
          "UNFETCHED: fake no-answer line from the check." in outcome.stderr,
          outcome.describe())
    no_answer_lines = outcome.stderr.splitlines()
    follow = next((i for i, line in enumerate(no_answer_lines) if line.startswith(
        "Follow the report, then check conflicting again by hand from your "
        "worktree: python3 scripts/branch-conflict-check.py --head ")), None)
    check("check-no-answer: and ends with the rerun and when to tell the user",
          follow is not None
          and no_answer_lines[follow + 1:follow + 2] == [RERUN_VERDICT_LINE],
          outcome.describe())
    outcome = failing_check_case("check-unexpected-status", FAKE_CHECK_UNEXPECTED_STATUS,
                                 "it exited 7")
    gave_no_verdict("check-unexpected-status", outcome, "it exited 7")
    failing_check_case("check-conflict-text-exit-zero",
                       FAKE_CHECK_CONFLICT_TEXT_EXIT_ZERO, "", silent=True)

    for label, source in (("check-hangs", FAKE_CHECK_HANGS),
                          ("check-hangs-with-child", FAKE_CHECK_HANGS_WITH_CHILD),
                          ("check-ignores-sigterm", FAKE_CHECK_IGNORES_SIGTERM),
                          ("check-records-sigterm", FAKE_CHECK_RECORDS_SIGTERM)):
        outcome = failing_check_case(
            label, source,
            "pre-push: branch conflicting was not checked for conflicts with "
            "origin/main, because scripts/branch-conflict-check.py had not finished "
            "when the 1-second time budget ran out, and was stopped.",
            budget=HANGING_CHECK_BUDGET_SECONDS)
        check("%s: and says to check by hand, telling the user only if that fails too"
              % label,
              ("\n" + RERUN_VERDICT_LINE + "\n") in ("\n" + outcome.stderr)
              and TELL_USER_LINE not in outcome.stderr,
              outcome.describe())
        check("%s: and the push is not held for long" % label,
              outcome.seconds < HANGING_CASE_WALL_CLOCK_LIMIT_SECONDS,
              "%.1f seconds" % outcome.seconds)

    # Message 5: the first branch's hang spends the budget, so the second
    # branch never gets its turn.
    hooks = make_layout(scratch, "layout-budget-spent", conflict_check=FAKE_CHECK_HANGS)
    spent = Scenario(scratch, "budget-spent", hooks)
    spent.extra_environment[TIME_BUDGET_VARIABLE] = HANGING_CHECK_BUDGET_SECONDS
    outcome = spent.push("origin", "clean", "clean-second")
    check("budget spent: the push goes through", went_through(outcome),
          outcome.describe())
    lines = outcome.stderr.splitlines()
    turnless = [branch for branch in ("clean", "clean-second")
                if "pre-push: branch %s was not checked for conflicts with origin/main, "
                   "because the earlier branches in this push used up the 1-second "
                   "time budget." % branch in lines]
    check("budget spent: one branch is named as never getting its turn",
          len(turnless) == 1, outcome.describe())
    if len(turnless) == 1:
        branch = turnless[0]
        line = ("pre-push: branch %s was not checked for conflicts with origin/main, "
                "because the earlier branches in this push used up the 1-second "
                "time budget." % branch)
        index = lines.index(line)
        check("budget spent: followed by that branch's hand check, by its commit",
              lines[index + 1:index + 2] == [hand_check_line(branch, spent.head(branch))],
              outcome.describe())

    log = scratch / "check-hangs-with-child-fake-check-log.txt"
    child_pid_file = Path(str(log) + ".child-pid")
    child_pid = int(child_pid_file.read_text()) if child_pid_file.exists() else None
    check("(setup) the hanging check's child recorded its pid", child_pid is not None)
    if child_pid is not None:
        check("check-hangs-with-child: and the check's child was stopped too",
              process_gone_within(child_pid, seconds=5), "pid %d still running" % child_pid)
        stop_leftover_process(child_pid)

    log = scratch / "check-records-sigterm-fake-check-log.txt"
    check("check-records-sigterm: and the check was sent SIGTERM before anything harsher",
          log.exists() and "received SIGTERM" in log.read_text(),
          repr(log.read_text() if log.exists() else None))

    # A pusher that names the repository with GIT_DIR, from a directory
    # outside it: git hands the hook that GIT_DIR, and the check must use it.
    outside = make_layout(scratch, "layout-git-dir")
    scenario = Scenario(scratch, "git-dir-from-outside", outside)
    scenario.extra_environment["GIT_DIR"] = str(scenario.clone / ".git")
    result = scenario.push("origin", "conflicting", cwd=scratch)
    del scenario.extra_environment["GIT_DIR"]
    check("a push made with GIT_DIR from outside the clone is still checked, "
          "and a conflicting branch refused",
          was_refused(result) and REFUSAL_HEADER % "conflicting" in result.stderr,
          result.describe())

    # --- The shell hook in front of the Python file ------------------------

    no_python_bin = scratch / "bin-without-python3"
    no_python_bin.mkdir()
    for tool in ("git", "dirname", "cat"):
        found = shutil.which(tool)
        if found:
            os.symlink(found, no_python_bin / tool)
    hooks = make_layout(scratch, "layout-no-python", conflict_check=FAKE_CHECK_ALWAYS_CONFLICT)
    failing = Scenario(scratch, "no-python", hooks, path_override=str(no_python_bin))
    check("(setup) python3 is not reachable on the case's PATH",
          shutil.which("python3", path=str(no_python_bin)) is None)
    outcome = failing.push("origin", "conflicting")
    check("no python3 on PATH: the push goes through", went_through(outcome),
          outcome.describe())
    check("no python3 on PATH: reported as the check exiting 127, naming the branch",
          "pre-push: the pre-push conflict check exited with status 127, "
          + NO_BRANCH_CHECKED % branch_entry("conflicting", failing.head("conflicting"))
          in outcome.stderr, outcome.describe())

    hooks = make_layout(scratch, "layout-runner-broken",
                        conflict_check=FAKE_CHECK_ALWAYS_CONFLICT,
                        runner_text="this is not python (\n")
    failing = Scenario(scratch, "runner-broken", hooks)
    outcome = failing.push("origin", "conflicting")
    check("the Python file fails to run: the push goes through",
          went_through(outcome), outcome.describe())
    check("the Python file fails to run: and says the check exited 1, naming the branch",
          "pre-push: the pre-push conflict check exited with status 1, "
          + NO_BRANCH_CHECKED % branch_entry("conflicting", failing.head("conflicting"))
          in outcome.stderr, outcome.describe())
    check("the Python file fails to run: then the hand check and the line telling the user",
          hand_check_line("conflicting", failing.head("conflicting")) + "\n"
          + TELL_USER_LINE in outcome.stderr, outcome.describe())

    hooks = make_layout(scratch, "layout-runner-missing",
                        conflict_check=FAKE_CHECK_ALWAYS_CONFLICT, include_runner=False)
    failing = Scenario(scratch, "runner-missing", hooks)
    outcome = failing.push("origin", "conflicting")
    check("the Python file is missing: the push goes through",
          went_through(outcome), outcome.describe())
    check("the Python file is missing: and says so, naming the branch",
          "git-client-side-hooks-pre-push-conflict-check.py is missing, "
          + NO_BRANCH_CHECKED % branch_entry("conflicting", failing.head("conflicting"))
          in outcome.stderr, outcome.describe())

    # --- The hook directory's other hook still works -----------------------

    stamping = Scenario(scratch, "prepare-commit-msg", real)
    stamping.extra_environment[SESSION_VARIABLE] = FAKE_SESSION
    stamping.git(stamping.clone, "switch", "--quiet", "clean")
    stamping.commit("stamped.txt", "s\n", "Stamped work")
    message = stamping.git(stamping.clone, "log", "-1", "--format=%B")
    check("prepare-commit-msg still stamps the session trailer beside pre-push",
          "Claude-Session: https://claude.ai/code/%s" % FAKE_SESSION in message,
          repr(message))

    check("the hook is executable, or git would skip it",
          os.access(PRE_PUSH_HOOK, os.X_OK), str(PRE_PUSH_HOOK))


# --- The selective test run -------------------------------------------------

def run_selective_test_run_cases(scratch):
    def lines_from(stderr, first):
        """The stderr lines from the first one starting with `first`, or []."""
        lines = stderr.splitlines()
        index = next((i for i, line in enumerate(lines) if line.startswith(first)), None)
        return [] if index is None else lines[index:]

    real = make_layout(scratch, "layout-selective-passes")
    scenario = Scenario(scratch, "selective-passes", real)
    result = scenario.push("origin", "clean")
    check("selective test run passes: the push goes through and arrives at origin",
          went_through(result) and scenario.origin_ref("clean") == scenario.head("clean"),
          result.describe())
    check("selective test run passes: the hook says it started, then that it passed, with "
          "the run's summary",
          SELECTIVE_TEST_RUN_STARTING + str(scenario.clone) in result.stderr
          and SELECTIVE_TEST_RUN_PASSED + FAKE_PASSED_SUMMARY in result.stderr.splitlines(),
          result.describe())
    calls = scenario.fake_test_suites_runner_calls()
    check("the run is the selective test run on the clone's top directory, waiting 0 seconds "
          "for the lock",
          calls == [["--checkout", str(scenario.clone),
                     "--only-suites-whose-recorded-inputs-changed-since", "origin/main",
                     "--wait-for-lock-seconds", "0"]], repr(calls))

    help_text = subprocess.run([sys.executable, str(REAL_TEST_SUITES_RUNNER), "--help"],
                               capture_output=True, text=True, timeout=60).stdout
    check("every option the check passes is one the real run-all-test-suites.py offers",
          all(option in help_text for option in calls[0] if option.startswith("--"))
          if calls else False, help_text)

    worktree = scratch / "selective-passes-worktree"
    scenario.git(scenario.clone, "worktree", "add", "--quiet", "-b", "selective-worktree",
                 str(worktree), scenario.base)
    scenario.commit("selective-worktree.txt", "w\n", "Worktree work", cwd=worktree)
    scenario.fake_test_suites_runner_log.unlink()
    result = scenario.push("origin", "selective-worktree", cwd=worktree)
    calls = scenario.fake_test_suites_runner_calls()
    check("from a linked worktree, the run tests that worktree, not the clone",
          went_through(result) and len(calls) == 1 and calls[0][:2] == ["--checkout", str(worktree)],
          repr(calls) + result.describe())

    # The pushes the hook checks nothing on start no run.
    scenario.fake_test_suites_runner_log.unlink()
    scenario.git(scenario.clone, "push", "--quiet", "--no-verify", "origin", "clean-second")
    for label, arguments in (("a deletion", ("origin", "--delete", "clean-second")),
                             ("a tag", ("origin", "refs/heads/clean:refs/tags/selective-tag")),
                             ("main", ("origin", "main"))):
        result = scenario.push(*arguments)
        check("a push of %s goes through without the selective test run" % label,
              went_through(result) and scenario.fake_test_suites_runner_calls() == []
              and "selective test run" not in result.stderr, result.describe())
    backup = scratch / "selective-backup.git"
    scenario.git(scratch, "init", "--quiet", "--bare", str(backup))
    scenario.git(scenario.clone, "remote", "add", "backup", str(backup))
    result = scenario.push("backup", "clean")
    check("a push to a remote not named origin goes through without the selective test run",
          went_through(result) and scenario.fake_test_suites_runner_calls() == [],
          result.describe())
    result = scenario.push("origin", "conflicting")
    check("a push the conflict check refuses never starts the selective test run",
          was_refused(result) and scenario.fake_test_suites_runner_calls() == [],
          result.describe())

    # A failing suite refuses the push.
    hooks = make_layout(scratch, "layout-selective-fails",
                        test_suites_runner_text=FAKE_TEST_SUITES_RUNNER_FAILS)
    failing = Scenario(scratch, "selective-fails", hooks)
    result = failing.push("origin", "clean")
    check("a failing suite: the push is refused and the branch never reaches origin",
          was_refused(result) and failing.origin_ref("clean") is None, result.describe())
    refusal = lines_from(result.stderr, SELECTIVE_TEST_RUN_REFUSED)
    check("a failing suite: the refusal carries the summary, each failing suite with its log, "
          "and the whole report's path",
          refusal[:3] == [SELECTIVE_TEST_RUN_REFUSED + FAKE_FAILED_SUMMARY,
                          FAKE_FAILING_SUITE_LINE,
                          "The whole report: %s/report.txt" % FAKE_LOG_DIRECTORY],
          result.describe())
    check("a failing suite: then says to fix and push again, and when to tell the user",
          len(refusal) >= 6 and refusal[3].startswith("Fix what each failing suite's log shows")
          and refusal[5].startswith("If it fails a second time, tell the user"),
          result.describe())
    check("a failing suite: the refusal does not offer --no-verify",
          "--no-verify" not in result.stderr, result.describe())

    def not_run_case(label, runner_text, expected_cause, tell_user, budget=None,
                     include_test_suites_runner=True, extra_environment=None):
        hooks = make_layout(scratch, "layout-selective-" + label,
                            test_suites_runner_text=runner_text,
                            include_test_suites_runner=include_test_suites_runner)
        outcome_scenario = Scenario(scratch, "selective-" + label, hooks)
        if budget is not None:
            outcome_scenario.extra_environment[SELECTIVE_TEST_RUN_BUDGET_VARIABLE] = budget
        outcome_scenario.extra_environment.update(extra_environment or {})
        outcome = outcome_scenario.push("origin", "clean")
        check("%s: the push goes through" % label,
              went_through(outcome)
              and outcome_scenario.origin_ref("clean") == outcome_scenario.head("clean"),
              outcome.describe())
        message = lines_from(outcome.stderr, "pre-push: " + expected_cause)
        check("%s: says why the selective test run gave no verdict, and how to run it by hand"
              % label,
              bool(message) and message[0].endswith(SELECTIVE_TEST_RUN_NOT_RUN_END + ".")
              and message[1:3] == [SELECTIVE_TEST_RUN_HAND_RUN_LINE,
                                   "If a suite fails, fix it, commit the fix and push again."],
              outcome.describe())
        check("%s: %s the user" % (label, "tells" if tell_user else "does not tell"),
              (message[3:4] == [TELL_USER_LINE]) == tell_user
              and (TELL_USER_LINE in outcome.stderr) == tell_user, outcome.describe())
        return outcome_scenario, outcome

    _, outcome = not_run_case(
        "lock held", FAKE_TEST_SUITES_RUNNER_LOCKED,
        "another run of the test suites held this machine's test lock: " + FAKE_LOCK_HOLDER_LINE,
        tell_user=False)
    check("lock held: the runner's advice to its own caller is not passed on",
          FAKE_LOCK_ADVICE_LINE not in outcome.stderr, outcome.describe())
    not_run_case("cannot start", FAKE_TEST_SUITES_RUNNER_CANNOT_START,
                 "the selective test run gave no verdict, because it exited 2: run-all-test-"
                 "suites: not run — /fake is not a checkout's top directory", tell_user=True)
    _, outcome = not_run_case(
        "runner crashes", FAKE_TEST_SUITES_RUNNER_CRASHES,
        "the selective test run gave no verdict, because it exited 1: " + FAKE_RUNNER_CRASH_ERROR,
        tell_user=True)
    check("runner crashes: the runner's traceback is shown above the message",
          "pre-push: the test runner printed on stderr:" in outcome.stderr
          and "Traceback (most recent call last):" in outcome.stderr
          and outcome.stderr.index("Traceback") < outcome.stderr.index(
              "the selective test run gave no verdict"), outcome.describe())
    check("runner crashes: the push is not reported as a failed suite",
          SELECTIVE_TEST_RUN_REFUSED not in outcome.stderr, outcome.describe())
    _, outcome = not_run_case(
        "runner crashes after a passing SUMMARY", FAKE_TEST_SUITES_RUNNER_CRASHES_AFTER_SUMMARY,
        "the selective test run gave no verdict, because it exited 1: " + FAKE_RUNNER_CRASH_ERROR,
        tell_user=True)
    check("runner crashes after a passing SUMMARY: the push is not reported as a failed suite",
          SELECTIVE_TEST_RUN_REFUSED not in outcome.stderr, outcome.describe())
    check("runner crashes after a passing SUMMARY: the runner's traceback is shown",
          "Traceback (most recent call last):" in outcome.stderr, outcome.describe())
    _, outcome = not_run_case(
        "sandbox cannot start", FAKE_TEST_SUITES_RUNNER_SANDBOX_CANNOT_START,
        "the selective test run gave no verdict, because it exited 2: "
        + FAKE_SANDBOX_REFUSAL_FIRST_LINE, tell_user=True)
    check("sandbox cannot start: everything the runner printed on stderr is shown",
          FAKE_SANDBOX_REFUSAL_LAST_LINE in outcome.stderr.splitlines(), outcome.describe())
    not_run_case("killed", FAKE_TEST_SUITES_RUNNER_KILLED,
                 "the selective test run gave no verdict, because it was killed by signal 9",
                 tell_user=True)
    not_run_case("runner missing", None,
                 "the selective test run did not start, because %s is missing"
                 % (scratch / "layout-selective-runner missing" / "scripts"
                    / REAL_TEST_SUITES_RUNNER.name),
                 tell_user=True, include_test_suites_runner=False)

    hanging, outcome = not_run_case(
        "overrun", FAKE_TEST_SUITES_RUNNER_HANGS_WITH_CHILD,
        "the selective test run had not finished when the 1-second time budget ran out, and "
        "was stopped; the logs of the suites it ran are in " + FAKE_LOG_DIRECTORY,
        tell_user=False, budget=HANGING_CHECK_BUDGET_SECONDS)
    check("overrun: what the run printed on stderr is shown above the message",
          "pre-push: the test runner printed on stderr:" in outcome.stderr
          and FAKE_OVERRUN_STDERR_LINE in outcome.stderr.splitlines()
          and outcome.stderr.index(FAKE_OVERRUN_STDERR_LINE) < outcome.stderr.index(
              "the selective test run had not finished"), outcome.describe())
    check("overrun: the push is not held for long",
          outcome.seconds < HANGING_CASE_WALL_CLOCK_LIMIT_SECONDS, "%.1f seconds" % outcome.seconds)
    child_pid_file = Path(str(hanging.fake_test_suites_runner_log) + ".child-pid")
    child_pid = int(child_pid_file.read_text()) if child_pid_file.exists() else None
    check("(setup) the overrunning run's child recorded its pid", child_pid is not None)
    if child_pid is not None:
        check("overrun: the run's child, a suite, was stopped too",
              process_gone_within(child_pid, seconds=5), "pid %d still running" % child_pid)
        stop_leftover_process(child_pid)
    detached_pid_file = Path(str(hanging.fake_test_suites_runner_log) + ".detached-child-pid")
    detached_pid = (int(detached_pid_file.read_text()) if detached_pid_file.exists() else None)
    check("(setup) the overrunning run's child in its own session recorded its pid",
          detached_pid is not None)
    if detached_pid is not None:
        check("overrun: a child the run started in its own session was stopped too",
              process_gone_within(detached_pid, seconds=5),
              "pid %d still running" % detached_pid)
        stop_leftover_process(detached_pid)

    # An overrun where ps fails: the run's descendants cannot be listed, so the message says
    # some may still be running, and tells the user.
    failing_ps_bin = scratch / "overrun-failing-ps-bin"
    failing_ps_bin.mkdir()
    (failing_ps_bin / "ps").write_text(
        "#!/bin/sh\necho 'ps: cannot read the process table' >&2\nexit 1\n")
    (failing_ps_bin / "ps").chmod(0o755)
    unlisted, outcome = not_run_case(
        "overrun with ps failing", FAKE_TEST_SUITES_RUNNER_HANGS_WITH_CHILD,
        "the selective test run had not finished when the 1-second time budget ran out, and "
        "was stopped; the logs of the suites it ran are in " + FAKE_LOG_DIRECTORY
        + "; the processes its suites started in their own sessions could not be listed, so "
        "some may still be running: ps -A -o pid=,ppid= exited 1: ps: cannot read the process "
        "table", tell_user=True, budget=HANGING_CHECK_BUDGET_SECONDS,
        extra_environment={"PATH": "%s%s%s" % (failing_ps_bin, os.pathsep,
                                               os.environ.get("PATH", ""))})
    for suffix in (".child-pid", ".detached-child-pid"):
        leftover_file = Path(str(unlisted.fake_test_suites_runner_log) + suffix)
        if leftover_file.exists():
            stop_leftover_process(int(leftover_file.read_text()))

    # The shell hook in front of the check.
    for label, options, expected in (
            ("check missing", {"include_selective_test_run_check": False},
             "the selective test run did not start, because %s is missing"
             % (scratch / "layout-selective-check-missing" / "scripts"
                / SELECTIVE_TEST_RUN_CHECK.name)),
            ("check fails", {"selective_test_run_check_text": "raise RuntimeError('broken')\n"},
             "the selective test run check, %s, exited with status 1"
             % (scratch / "layout-selective-check-fails" / "scripts"
                / SELECTIVE_TEST_RUN_CHECK.name))):
        hooks = make_layout(scratch, "layout-selective-" + label.replace(" ", "-"), **options)
        broken = Scenario(scratch, "selective-" + label.replace(" ", "-"), hooks)
        outcome = broken.push("origin", "clean")
        message = lines_from(outcome.stderr, "pre-push: " + expected)
        check("selective test run %s: the push goes through" % label,
              went_through(outcome) and broken.origin_ref("clean") == broken.head("clean"),
              outcome.describe())
        check("selective test run %s: the hook names the branch, the hand run, and tells the "
              "user" % label,
              message[:1] == ["pre-push: %s%s: %s." % (expected, SELECTIVE_TEST_RUN_NOT_RUN_END,
                                                      branch_entry("clean", broken.head("clean")))]
              and message[1:4] == [SELECTIVE_TEST_RUN_HAND_RUN_LINE,
                                   "If a suite fails, fix it, commit the fix and push again.",
                                   TELL_USER_LINE],
              outcome.describe())

    # A missing conflict check does not end the hook before the selective test run.
    # include_runner=False removes the file the hook itself tests for, so the hook's own
    # "is missing" branch runs, not the Python check's.
    hooks = make_layout(scratch, "layout-selective-conflict-check-missing", conflict_check=None, include_runner=False,
                        test_suites_runner_text=FAKE_TEST_SUITES_RUNNER_FAILS)
    missing = Scenario(scratch, "selective-conflict-check-missing", hooks)
    outcome = missing.push("origin", "clean")
    said = [line for line in outcome.stderr.splitlines()
            if line.startswith("pre-push: the pre-push conflict check did not run, because ")]
    check("with the conflict check missing, the hook's own branch says so",
          len(said) == 1 and ("/%s is missing" % CONFLICT_CHECK_RUNNER.name) in said[0],
          outcome.describe())
    check("with the conflict check missing, the selective test run still runs and refuses",
          was_refused(outcome) and SELECTIVE_TEST_RUN_REFUSED in outcome.stderr,
          outcome.describe())

    selective = types.ModuleType("selective_test_run_check_under_test")
    selective.__file__ = str(SELECTIVE_TEST_RUN_CHECK)
    exec(compile(SELECTIVE_TEST_RUN_CHECK.read_text(), str(SELECTIVE_TEST_RUN_CHECK), "exec"),
         selective.__dict__)
    for summary, expected in ((FAKE_FAILED_SUMMARY, 1), (FAKE_PASSED_SUMMARY, 0), ("", 0),
                              ("SUMMARY: 0 passed, 12 failed, 12 total", 12)):
        check("the SUMMARY line %r counts %d failed suites" % (summary, expected),
              selective.summary_failed_count(summary) == expected)
    for configured, expected in (("", 480.0), ("abc", 480.0), ("-5", 480.0), ("0", 480.0),
                                 ("90", 90.0)):
        got = selective.time_budget_seconds({SELECTIVE_TEST_RUN_BUDGET_VARIABLE: configured})
        check("a time budget configured as %r is %g seconds" % (configured, expected),
              got == expected, repr(got))
    check("a time budget left unconfigured is 480 seconds",
          selective.time_budget_seconds({}) == 480.0)

    # A ps that fails: the descendants cannot be listed, and the stop says so.
    failing_ps_directory = scratch / "failing-ps-bin"
    failing_ps_directory.mkdir()
    failing_ps = failing_ps_directory / "ps"
    failing_ps.write_text("#!/bin/sh\necho 'ps: cannot read the process table' >&2\nexit 1\n")
    failing_ps.chmod(0o755)
    saved_path = os.environ.get("PATH", "")
    os.environ["PATH"] = "%s%s%s" % (failing_ps_directory, os.pathsep, saved_path)
    try:
        try:
            selective.descendant_process_ids(os.getpid())
            listing_raised = None
        except RuntimeError as error:
            listing_raised = str(error)
        sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                                   start_new_session=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True)
        try:
            _stdout, _stderr, stop_error = selective.stop_process_group(sleeper)
        finally:
            stop_leftover_process(sleeper.pid)
    finally:
        os.environ["PATH"] = saved_path
    check("a ps that fails: listing the run's descendants raises, naming ps and its error",
          listing_raised is not None and "ps -A -o pid=,ppid= exited 1" in listing_raised
          and "cannot read the process table" in listing_raised, repr(listing_raised))
    check("a ps that fails: the run is still stopped, and the stop returns the listing error",
          sleeper.returncode is not None and stop_error is not None
          and "cannot read the process table" in stop_error, repr((sleeper.returncode, stop_error)))


# --- Pushes from a mutation-testing worktree ------------------------------
def run_mutation_testing_worktree_cases(scratch):
    real = make_layout(scratch, "layout-mutation-testing-worktree")

    for label, text, expected in [
            ("crashes", "raise RuntimeError('broken')\n",
             "-push-refusal.py, exited with status 1, so this check lets the push through without checking whether it comes from a mutation-testing worktree."),
            ("is missing", None, "the check for mutation-testing worktrees did not run, because ")]:
        hooks = make_layout(scratch, "layout-worktree-check-" + label.replace(" ", "-"),
                            mutation_testing_worktree_check_text=text,
                            include_mutation_testing_worktree_check=text is not None)
        scenario = Scenario(scratch, "worktree-check-" + label.replace(" ", "-"), hooks)
        result = scenario.push("origin", "clean")
        check(f"when the mutation-testing worktree check {label}, the push goes through and the "
              f"hook says what was not checked and to tell the user",
              went_through(result) and expected in result.stderr
              and TELL_USER_LINE in result.stderr, result.describe())
        check(f"when the mutation-testing worktree check {label}, the hook names it by a resolved "
              f"path, with no ../ in it", "/../" not in result.stderr, result.describe())

    # A push from a copy whose directory name ends in -mutation-testing-worktree is refused, whatever it pushes.
    scenario = Scenario(scratch, "copy", real)
    copy = scratch / "copy-checkout-mutation-testing-worktree"
    scenario.git(scenario.clone, "worktree", "add", "--quiet", "--detach", str(copy), "clean")
    result = scenario.push("origin", "HEAD:refs/heads/from-a-copy", cwd=copy)
    check("a push from a checkout whose directory name ends in -mutation-testing-worktree is refused, "
          "naming the copy and how to remove it",
          was_refused(result) and str(copy) in result.stderr
          and "Push from the checkout you work in, not from this copy." in result.stderr
          and f"git worktree remove --force {copy}" in result.stderr
          and scenario.origin_ref("from-a-copy") is None, result.describe())
    result = scenario.push("origin", "clean:refs/heads/clean-mutation-testing-worktree")
    check("a push of a branch whose name ends in -mutation-testing-worktree is refused",
          was_refused(result) and "pushes clean-mutation-testing-worktree, whose name ends in -mutation-testing-worktree"
          in result.stderr and scenario.origin_ref("clean-mutation-testing-worktree") is None,
          result.describe())
    result = scenario.push("origin", "clean")
    check("a push of any other branch from the checkout itself goes through",
          went_through(result) and "this push is refused" not in result.stderr, result.describe())
    specification = importlib.util.spec_from_file_location("mutation_testing_worktree_check",
                                                           MUTATION_TESTING_WORKTREE_CHECK)
    loaded = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(loaded)
    helper_source = (SCRIPTS_DIRECTORY / "run-suite-in-signal-sandbox.py").read_text()
    check("the pre-push check and the mutation helper use the same label",
          f'MUTATION_TESTING_WORKTREE_LABEL = "{loaded.MUTATION_TESTING_WORKTREE_LABEL}"' in helper_source,
          loaded.MUTATION_TESTING_WORKTREE_LABEL)

    # git rev-parse fails: the check says in one line what went unchecked and exits with a status
    # the hook reports as unchecked, never taking the failure for "not a mutation-testing worktree".
    real_run, here = loaded.subprocess.run, os.getcwd()
    os.chdir(scenario.clone)

    def failing_run(command, **options):
        if command[:2] == ["git", "rev-parse"]:
            return subprocess.CompletedProcess(command, 128, "", "fatal: injected")
        return real_run(command, **options)
    loaded.subprocess.run = failing_run
    printed = io.StringIO()
    real_stdin = sys.stdin
    sys.stdin = io.StringIO(f"refs/heads/clean {'1' * 40} refs/heads/clean {'0' * 40}\n")
    try:
        with contextlib.redirect_stderr(printed):
            status = loaded.main()
    finally:
        sys.stdin, loaded.subprocess.run = real_stdin, real_run
        os.chdir(here)
    check("when git rev-parse fails, the check says so in one line and exits with a status the "
          "hook reports as unchecked, not as a refusal or a pass",
          status == loaded.EXIT_CHECK_FAILED
          and status not in (loaded.EXIT_REFUSE_PUSH, loaded.EXIT_ALLOW_PUSH)
          and printed.getvalue() == "pre-push: git rev-parse --show-toplevel failed: fatal: "
          "injected, so this check lets the push through without checking whether it comes from a mutation-testing worktree.\n",
          (status, printed.getvalue()))


def main():
    run_unit_cases()
    # Resolved, because git and the hooks print resolved paths: on macOS the temporary
    # directory is under /var, a symlink to /private/var.
    scratch = Path(tempfile.mkdtemp(prefix="pre-push-test-")).resolve()
    try:
        run_push_cases(scratch)
        run_selective_test_run_cases(scratch)
        run_mutation_testing_worktree_cases(scratch)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    if failures:
        print(f"\n{len(failures)} case(s) failed")
        return 1
    print("\nall cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
