#!/usr/bin/env python3
"""Tests for scripts/git-client-side-hooks/pre-push, the hook that refuses to
push a branch that conflicts with main, or a push that rewrites or deletes the
head branch of an open pull request, and runs no test suites, and for the
Python files it runs,
scripts/git-client-side-hooks-pre-push-conflict-check.py and
scripts/git-client-side-hooks-pre-push-open-pull-request-branch-non-fast-forward-or-deletion-refusal.py.

Run: python3 scripts/git-client-side-hooks-pre-push-test.py
Prints one line per case and exits non-zero if any case fails.

Every push case pushes with real git, from throwaway clones of throwaway bare
repositories under a temporary directory. Each clone's own core.hooksPath
points at a copy of the hooks laid out as this checkout lays them out, under
the temporary directory:
    <layout>/scripts/git-client-side-hooks/pre-push
    <layout>/scripts/git-client-side-hooks-pre-push-conflict-check.py
    <layout>/scripts/branch-conflict-check.py
    <layout>/scripts/branch-reverts-a-file-to-an-older-main-version-check.py
    <layout>/scripts/git-client-side-hooks-pre-push-open-pull-request-branch-non-fast-forward-or-deletion-refusal.py
    <layout>/scripts/run-all-test-suites.py, a fake that fails and logs each
    start, so a case can show the hook never starts it
    <layout>/nc-systems/general-tools/git-machine-readable-output-runner-and-parser-common.py
So each case runs exactly what git runs on a seat's push. A case that needs
the conflict check to misbehave puts a fake check at the check's path, and
leaves the real one alone. No real repository's config is read or written:
global and system git config are shut out, and every GIT_ variable is
removed from each case's environment. A fake gh, first on every case's PATH,
answers the open pull request lookup: no open pull request, unless a case
names some or makes the fake fail.

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
import re
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
REAL_REVERT_CHECK = SCRIPTS_DIRECTORY / "branch-reverts-a-file-to-an-older-main-version-check.py"
OPEN_PULL_REQUEST_BRANCH_CHECK = (SCRIPTS_DIRECTORY / "git-client-side-hooks-pre-push-open-pull-"
                                  "request-branch-non-fast-forward-or-deletion-refusal.py")
REAL_TEST_SUITES_RUNNER = SCRIPTS_DIRECTORY / "run-all-test-suites.py"
GIT_OUTPUT_MODULE_RELATIVE_PATH = Path(
    "nc-systems/general-tools/git-machine-readable-output-runner-and-parser-common.py")

TIME_BUDGET_VARIABLE = "NEDSCHORUS_PRE_PUSH_CONFLICT_CHECK_SECONDS"
FAKE_CHECK_LOG_VARIABLE = "PRE_PUSH_TEST_FAKE_CHECK_LOG"
FAKE_TEST_SUITES_RUNNER_LOG_VARIABLE = "PRE_PUSH_TEST_FAKE_TEST_SUITES_RUNNER_LOG"
FAKE_GH_OPEN_PULL_REQUESTS_VARIABLE = "PRE_PUSH_TEST_FAKE_GH_OPEN_PULL_REQUESTS"
FAKE_GH_FAILURE_VARIABLE = "PRE_PUSH_TEST_FAKE_GH_FAILURE"
FAKE_GH_LOG_VARIABLE = "PRE_PUSH_TEST_FAKE_GH_LOG"
ESCAPE_HATCH_VARIABLE = "CLAUDE_MERGE_LANE_ASKED_FOR_THIS_REWRITE"
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
RERUN_VERDICT_LINE = ("If the hand conflict check also prints no VERDICT line, tell the user "
                      "this whole message and what that check printed.")
NO_BRANCH_CHECKED = ("so none of this push's branches was checked for conflicts with "
                     "origin/main: %s.")
PUSH_GOES_ON_LINE = ("pre-push: neither the conflict check nor the revert check refuses this "
                     "push, so it goes through.")
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

# Answers per branch: no answer for the branch whose commit is "Clean work", a conflict
# for any other, so one push can mix a skipped branch with a refused one.
FAKE_CHECK_NO_ANSWER_FOR_CLEAN_CONFLICT_OTHERWISE = FAKE_CHECK_PREAMBLE + """\
import subprocess
subject = subprocess.run(["git", "show", "-s", "--format=%s", sys.argv[2]],
                         capture_output=True, text=True).stdout.strip()
if subject == "Clean work":
    print("UNFETCHED: fake no-answer line from the check.")
    sys.exit(2)
print("VERDICT: CONFLICT -- fake conflict for the test.")
sys.exit(1)
"""

FAKE_CHECK_NO_VERDICT_FOR_CLEAN_CONFLICT_OTHERWISE = (
    FAKE_CHECK_NO_ANSWER_FOR_CLEAN_CONFLICT_OTHERWISE.replace("sys.exit(2)", "sys.exit(7)"))

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


BRANCH_NOT_CHECKED_END = "."
# What git itself writes on stderr for a push: the remote's name, one line per ref, and a
# line when a hook refused the push.
GIT_PUSH_REMOTE_LINE_START = "To "
GIT_PUSH_FAILED_LINE_START = "error: failed to push some refs to "
GIT_PUSH_REF_LINE = re.compile(r"^ [ +\-*!=] ")

# --- Fake run-all-test-suites.py -------------------------------------------
# Written to <layout>/scripts/run-all-test-suites.py. It appends its arguments,
# as one JSON list, to the file FAKE_TEST_SUITES_RUNNER_LOG_VARIABLE names, and
# fails, so a push that started it would be logged, and refused were the hook
# to read its status.
FAKE_TEST_SUITES_RUNNER_FAILS = """\
import json, os, sys
_log = os.environ.get("%s")
if _log:
    with open(_log, "a") as _handle:
        _handle.write(json.dumps(sys.argv[1:]) + "\\n")
print("FAIL scripts/fake-failing-test.py exit 1 (0.1s)")
sys.exit(1)
""" % FAKE_TEST_SUITES_RUNNER_LOG_VARIABLE


# --- Fake gh ---------------------------------------------------------------
# Answers `gh pr list --state open --head <branch> --json ...` from a JSON object of
# branch to pull request in FAKE_GH_OPEN_PULL_REQUESTS_VARIABLE, or fails with the
# text in FAKE_GH_FAILURE_VARIABLE, as a logged-out gh does. Logs each call.
FAKE_GH = """\
#!/usr/bin/env python3
import json, os, sys
_log = os.environ.get("%s")
if _log:
    with open(_log, "a") as _handle:
        _handle.write(" ".join(sys.argv[1:]) + "\\n")
_failure = os.environ.get("%s")
if _failure:
    print(_failure, file=sys.stderr)
    sys.exit(4)
_branch = sys.argv[sys.argv.index("--head") + 1]
_open = json.loads(os.environ.get("%s") or "{}")
print(json.dumps([_open[_branch]] if _branch in _open else []))
""" % (FAKE_GH_LOG_VARIABLE, FAKE_GH_FAILURE_VARIABLE, FAKE_GH_OPEN_PULL_REQUESTS_VARIABLE)
FAKE_GH_LOGGED_OUT = "To get started with GitHub CLI, please run:  gh auth login"


# --- Layouts and repositories ---------------------------------------------

def make_layout(parent, name, conflict_check=REAL_CONFLICT_CHECK,
                runner_text=None, include_runner=True, mutation_testing_worktree_check_text=None,
                include_mutation_testing_worktree_check=True,
                include_test_suites_runner=True,
                open_pull_request_branch_check_text=None,
                include_open_pull_request_branch_check=True, revert_check=REAL_REVERT_CHECK):
    """A copy of this checkout's hooks, laid out as the hook expects.

    conflict_check is a Path to copy, a string of fake check source, or None
    for no check at all. runner_text replaces the Python file the hook runs
    for the conflict check, and open_pull_request_branch_check_text the check
    for rewrites and deletions of open pull requests' head branches. revert_check,
    like conflict_check, is a Path to copy, fake source, or None for no file.
    Returns the hooks directory, for core.hooksPath.
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
    open_pull_request_branch_check = scripts / OPEN_PULL_REQUEST_BRANCH_CHECK.name
    if open_pull_request_branch_check_text is not None:
        open_pull_request_branch_check.write_text(open_pull_request_branch_check_text)
    elif include_open_pull_request_branch_check:
        shutil.copy2(OPEN_PULL_REQUEST_BRANCH_CHECK, open_pull_request_branch_check)
    if include_test_suites_runner:
        (scripts / REAL_TEST_SUITES_RUNNER.name).write_text(FAKE_TEST_SUITES_RUNNER_FAILS)
    if isinstance(conflict_check, Path):
        shutil.copy2(conflict_check, scripts / REAL_CONFLICT_CHECK.name)
        module = parent / name / GIT_OUTPUT_MODULE_RELATIVE_PATH
        module.parent.mkdir(parents=True)
        shutil.copy2(SCRIPTS_DIRECTORY.parent / GIT_OUTPUT_MODULE_RELATIVE_PATH, module)
    elif isinstance(conflict_check, str):
        (scripts / REAL_CONFLICT_CHECK.name).write_text(conflict_check)
    if isinstance(revert_check, Path):
        shutil.copy2(revert_check, scripts / REAL_REVERT_CHECK.name)
    elif isinstance(revert_check, str):
        (scripts / REAL_REVERT_CHECK.name).write_text(revert_check)
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
        self.fake_gh_directory = parent / (name + "-fake-gh-bin")
        self.fake_gh_directory.mkdir()
        (self.fake_gh_directory / "gh").write_text(FAKE_GH)
        (self.fake_gh_directory / "gh").chmod(0o755)
        self.fake_gh_log = parent / (name + "-fake-gh-log.txt")
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
        env[FAKE_GH_LOG_VARIABLE] = str(self.fake_gh_log)
        env.pop(ESCAPE_HATCH_VARIABLE, None)
        path = self.path_override if self.path_override is not None else env.get("PATH", "")
        env["PATH"] = str(self.fake_gh_directory) + os.pathsep + path
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
        # --verify --quiet exits 1 for a ref that does not exist.
        if completed.returncode == 1:
            return None
        if completed.returncode != 0:
            raise RuntimeError(f"git rev-parse --verify refs/heads/{branch} in origin exited "
                               f"{completed.returncode}: {completed.stderr.strip()}")
        return completed.stdout.strip()

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

    def fake_gh_calls(self):
        if not self.fake_gh_log.exists():
            return []
        return [line for line in self.fake_gh_log.read_text().splitlines() if line]

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


def git_push_output_line(line):
    return (line.startswith((GIT_PUSH_REMOTE_LINE_START, GIT_PUSH_FAILED_LINE_START))
            or bool(GIT_PUSH_REF_LINE.match(line)))


def conflict_check_said_nothing(stderr):
    """True when every stderr line is git's own push output, so a line the conflict or revert
    check adds fails it, whatever it starts with."""
    return all(git_push_output_line(line) for line in stderr.splitlines())


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
    check("an error after the pushed refs were read names each unchecked branch, and says, "
          "before the line to tell the user, when to run the revert check on it",
          stream.getvalue().splitlines() == [
              "pre-push: the pre-push conflict check failed with RuntimeError: boom, "
              + NO_BRANCH_CHECKED % ", ".join(
                  [branch_entry("topic", sha), branch_entry("renamed-on-push", other)]),
              hand_check_line("topic", sha),
              hand_check_line("renamed-on-push", other),
              *no_branch_revert_lines([("topic", sha), ("renamed-on-push", other)]),
              PUSH_GOES_ON_LINE,
              TELL_USER_LINE],
          stream.getvalue())
    stream = io.StringIO()
    runner.report_unexpected_error(stream, error, ["origin", "url"], None)
    check("an error before the pushed refs were read says no branch was checked, for "
          "conflicts or for files set back",
          stream.getvalue().splitlines() == [
              "pre-push: the pre-push conflict check failed with RuntimeError: boom "
              "before reading which branches this push sends, so none of them was checked "
              "for conflicts with origin/main.",
              "For each branch this push sends to origin, other than main, run from "
              "your worktree: python3 scripts/branch-conflict-check.py --head "
              "<branch name>",
              "Nor was any branch checked for files set back to a version that origin/main "
              "has replaced. For each branch this push sends to origin, other than main, "
              "once that conflict check prints VERDICT: CLEAN, also run: python3 "
              "scripts/branch-reverts-a-file-to-an-older-main-version-check.py "
              "--head <branch name>",
              PUSH_GOES_ON_LINE,
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
                            open_pull_request_branch_check_text="import sys\nsys.exit(0)\n")
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
                                    *no_branch_revert_lines(
                                        [("topic", sha), ("renamed-on-push", other)]),
                                    PUSH_GOES_ON_LINE,
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

    sha = "a" * 40
    stream = io.StringIO()
    reverts, skipped = runner.check_reverts([("late", sha)], time.monotonic() - 1, 7, stream)
    check("a branch left with no time budget is not sent to the revert check, is reported "
          "as skipped, and gets a message",
          reverts == [] and skipped and REVERT_NOT_CHECKED % (
              "late", "the 7-second time budget was used up") in stream.getvalue()
          and revert_hand_check_line(sha) in stream.getvalue(), stream.getvalue())


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
    check("and carries the line on an edit beyond the conflicting lines",
          "If the resolution forces an edit beyond the conflicting lines, put "
          "that edit in one ordinary commit after the merge." in result.stderr,
          result.describe())
    check("and carries the line on pushing the merge and that commit once",
          "Push the merge and that commit once, and name the files you "
          "resolved in the merge's commit message and in the pull request's "
          "description." in result.stderr, result.describe())
    check("and ends with the instruction to push again",
          CLOSING_INSTRUCTION in result.stderr, result.describe())
    check("and does not offer --no-verify", "--no-verify" not in result.stderr,
          result.describe())
    lines = result.stderr.splitlines()
    header = REFUSAL_HEADER % "conflicting"
    outside = (lines[:lines.index(header)] + lines[lines.index(CLOSING_INSTRUCTION) + 1:]
               if header in lines and CLOSING_INSTRUCTION in lines else lines)
    check("and the hook says nothing outside the refusal",
          all(git_push_output_line(line) for line in outside), result.describe())

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
            check("%s: and says once that the revert check did not run either, with when "
                  "to run it" % label,
                  outcome.stderr.count(revert_check_not_run_lines(
                      "conflicting", failing.head("conflicting"))) == 1,
                  outcome.describe())
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
    lines = outcome.stderr.splitlines()
    hand = hand_check_line("conflicting", conflicting_commit)
    check("check missing: and gives the hand check, says once when to run the revert check, "
          "and then tells the user",
          lines.count(hand) == 1
          and lines[lines.index(hand):lines.index(hand) + 5]
          == [hand, *no_branch_revert_lines([("conflicting", conflicting_commit)]),
              PUSH_GOES_ON_LINE, TELL_USER_LINE]
          and outcome.stderr.count("files set back") == 2, outcome.describe())

    # A push whose first branch is skipped and whose second conflicts is refused, and no
    # line says it goes ahead.
    mixed = make_layout(scratch, "layout-mixed",
                        conflict_check=FAKE_CHECK_NO_ANSWER_FOR_CLEAN_CONFLICT_OTHERWISE)
    failing = Scenario(scratch, "mixed", mixed)
    outcome = failing.push("origin", "clean", "conflicting")
    check("mixed push, one branch undecided and one conflicting: the push is refused",
          was_refused(outcome) and failing.origin_ref("clean") is None
          and failing.origin_ref("conflicting") is None, outcome.describe())
    check("mixed push: and it names the undecided branch, then refuses for the conflicting one",
          "pre-push: branch clean was not checked for conflicts with origin/main, because "
          "scripts/branch-conflict-check.py could not decide, as its report below says"
          + BRANCH_NOT_CHECKED_END in outcome.stderr.splitlines()
          and REFUSAL_HEADER % "conflicting" in outcome.stderr, outcome.describe())
    check("mixed push: and no line says the push goes ahead or goes on",
          PUSH_GOES_ON_LINE not in outcome.stderr and "goes ahead" not in outcome.stderr,
          outcome.describe())

    mixed = make_layout(scratch, "layout-mixed-no-verdict",
                        conflict_check=FAKE_CHECK_NO_VERDICT_FOR_CLEAN_CONFLICT_OTHERWISE)
    failing = Scenario(scratch, "mixed-no-verdict", mixed)
    outcome = failing.push("origin", "clean", "conflicting")
    hook_lines = [line for line in outcome.stderr.splitlines()
                  if not git_push_output_line(line)]
    check("mixed push, one branch with no verdict and one conflicting: refused, and the line "
          "telling the user ends the message, after the refusal",
          was_refused(outcome) and hook_lines[-1:] == [TELL_USER_LINE]
          and outcome.stderr.count(TELL_USER_LINE) == 1
          and PUSH_GOES_ON_LINE not in outcome.stderr, outcome.describe())

    def gave_no_verdict(label, outcome, reason):
        lines = outcome.stderr.splitlines()
        first = ("pre-push: branch conflicting was not checked for conflicts with "
                 "origin/main, because scripts/branch-conflict-check.py gave no "
                 "verdict: %s" % reason + BRANCH_NOT_CHECKED_END)
        index = next((i for i, line in enumerate(lines) if line == first), None)
        check("%s: says which branch went unchecked and why" % label,
              index is not None, outcome.describe())
        if index is not None:
            commit = lines[index + 1].rsplit(" ", 1)[-1] if len(lines) > index + 1 else ""
            check("%s: then the hand check, when to run the revert check, that the push goes "
                  "on, and the line telling the user" % label,
                  lines[index + 1:index + 6]
                  == [hand_check_line("conflicting", commit),
                      *revert_check_not_run_lines("conflicting", commit).splitlines(),
                      PUSH_GOES_ON_LINE, TELL_USER_LINE],
                  outcome.describe())

    outcome = failing_check_case("check-crashes", FAKE_CHECK_CRASHES,
                                 "exited 1 without a VERDICT: CONFLICT line")
    gave_no_verdict("check-crashes", outcome,
                    "it exited 1 without a VERDICT: CONFLICT line: RuntimeError: fake crash "
                    "inside the conflict check")
    outcome = failing_check_case(
        "check-no-answer", FAKE_CHECK_NO_ANSWER,
        "pre-push: branch conflicting was not checked for conflicts with "
        "origin/main, because scripts/branch-conflict-check.py could not decide, as its "
        "report below says" + BRANCH_NOT_CHECKED_END)
    check("check-no-answer: and passes on the check's own lines",
          "UNFETCHED: fake no-answer line from the check." in outcome.stderr,
          outcome.describe())
    no_answer_lines = outcome.stderr.splitlines()
    follow = next((i for i, line in enumerate(no_answer_lines) if line.startswith(
        "Follow the report, then check conflicting again by hand from your "
        "worktree: python3 scripts/branch-conflict-check.py --head ")), None)
    check("check-no-answer: and ends with the rerun, when to run the revert check, and when "
          "to tell the user",
          follow is not None
          and no_answer_lines[follow + 1:follow + 4]
          == [*revert_check_not_run_lines(
              "conflicting", no_answer_lines[follow].rsplit(" ", 1)[-1]).splitlines(),
              RERUN_VERDICT_LINE],
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
            "when the 1-second time budget ran out, and was stopped"
            + BRANCH_NOT_CHECKED_END,
            budget=HANGING_CHECK_BUDGET_SECONDS)
        check("%s: and says to check by hand, when to run the revert check, and to tell "
              "the user only if the hand check fails too" % label,
              ("\n" + revert_check_not_run_lines("conflicting", hand_checked_commit(outcome.stderr))
               + "\n" + RERUN_VERDICT_LINE + "\n") in ("\n" + outcome.stderr)
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
                   "time budget" % branch + BRANCH_NOT_CHECKED_END in lines]
    check("budget spent: one branch is named as never getting its turn",
          len(turnless) == 1, outcome.describe())
    if len(turnless) == 1:
        branch = turnless[0]
        line = ("pre-push: branch %s was not checked for conflicts with origin/main, "
                "because the earlier branches in this push used up the 1-second "
                "time budget" % branch + BRANCH_NOT_CHECKED_END)
        index = lines.index(line)
        check("budget spent: followed by that branch's hand check, by its commit",
              lines[index + 1:index + 2] == [hand_check_line(branch, spent.head(branch))],
              outcome.describe())
        check("budget spent: then that the revert check did not run either, with its "
              "hand check",
              "\n".join(lines[index + 2:index + 4])
              == revert_check_not_run_lines(branch, spent.head(branch)),
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
    check("the Python file fails to run: then the hand check, when to run the revert check, "
          "and the line telling the user",
          "\n".join([hand_check_line("conflicting", failing.head("conflicting")),
                     *no_branch_revert_lines([("conflicting", failing.head("conflicting"))]),
                     PUSH_GOES_ON_LINE, TELL_USER_LINE]) in outcome.stderr, outcome.describe())

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


# --- No test suites ---------------------------------------------------------

def run_no_test_suites_cases(scratch):
    hooks = make_layout(scratch, "layout-no-test-suites")
    scenario = Scenario(scratch, "no-test-suites", hooks)
    result = scenario.push("origin", "clean")
    check("a clean branch goes through although run-all-test-suites.py beside the hook fails",
          went_through(result) and scenario.origin_ref("clean") == scenario.head("clean"),
          result.describe())
    check("and the hook never starts run-all-test-suites.py",
          scenario.fake_test_suites_runner_calls() == [], repr(scenario.fake_test_suites_runner_calls()))
    check("the hook names no test run, and no file of the test step it no longer runs",
          "test run" not in PRE_PUSH_HOOK.read_text()
          and "selective" not in PRE_PUSH_HOOK.read_text(), str(PRE_PUSH_HOOK))


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


# --- Rewrites and deletions of open pull requests' head branches ----------
def run_open_pull_request_branch_cases(scratch):
    pull_request = {"number": 4242, "title": "Clean work",
                    "url": "https://github.com/example/example/pull/4242"}
    open_on_clean = json.dumps({"clean": pull_request, "clean-second": pull_request})
    refused_header = ("pre-push: this push is refused, because its update to branch clean does not "
                      "build on the commits origin holds, and clean is the head of open pull "
                      "request #4242 (https://github.com/example/example/pull/4242)")
    lookup_failed = "whether clean has an open pull request could not be checked: "

    def fresh(label):
        scenario = Scenario(scratch, "open-pull-request-" + label, real)
        scenario.git(scenario.clone, "push", "--quiet", "--no-verify", "origin", "clean",
                     "conflicting")
        scenario.extra_environment[FAKE_GH_OPEN_PULL_REQUESTS_VARIABLE] = open_on_clean
        return scenario

    def rewrite(scenario, branch):
        """Replace the branch's last commit, so its pushed head is no longer an ancestor."""
        scenario.git(scenario.clone, "switch", "--quiet", branch)
        scenario.git(scenario.clone, "commit", "--quiet", "--amend", "-m", "Rewritten")

    real = make_layout(scratch, "layout-open-pull-request")

    # (a) A new branch needs no lookup, open pull request or not.
    scenario = fresh("new-branch")
    result = scenario.push("origin", "clean-second")
    check("open pull request check: a new branch goes through without asking gh",
          went_through(result) and scenario.fake_gh_calls() == [], result.describe())

    # (c) A fast-forward to an open pull request's head goes through without asking gh.
    scenario = fresh("fast-forward")
    scenario.on_branch("clean", "on-top.txt", "on top\n", "On top")
    result = scenario.push("origin", "clean")
    check("open pull request check: a fast-forward to an open pull request's head goes through "
          "without asking gh",
          went_through(result) and scenario.fake_gh_calls() == []
          and scenario.origin_ref("clean") == scenario.head("clean"), result.describe())

    # (d) A forced update that does not build on the head is refused, in each spelling.
    for label, arguments in (("--force", ("--force", "origin", "clean")),
                             ("--force-with-lease", ("--force-with-lease", "origin", "clean")),
                             ("a + refspec", ("origin", "+clean:clean"))):
        scenario = fresh("rewrite-" + label.replace(" ", "-").replace("+", "plus").strip("-"))
        pushed = scenario.origin_ref("clean")
        rewrite(scenario, "clean")
        result = scenario.push(*arguments)
        check(f"open pull request check: a push with {label} that rewrites an open pull "
              f"request's head is refused, naming the branch and the pull request",
              was_refused(result) and refused_header in result.stderr
              and scenario.origin_ref("clean") == pushed, result.describe())
    check("open pull request check: the refusal says to push a new commit on top, to clear a "
          "conflict by the hand-merge, and how merge-lane-2 lets the push through",
          "new commit on top of origin/clean" in result.stderr
          and "the hand-merge that scripts/branch-conflict-check.py describes" in result.stderr
          and f"{ESCAPE_HATCH_VARIABLE}=1 directly in front of the git push command"
          in result.stderr, result.describe())

    # An unforced rewrite never reaches the hook: git rejects it first.
    scenario = fresh("unforced-rewrite")
    rewrite(scenario, "clean")
    result = scenario.push("origin", "clean")
    check("open pull request check: git rejects an unforced rewrite before the hook runs",
          was_refused(result) and "this push is refused" not in result.stderr
          and scenario.fake_gh_calls() == [], result.describe())

    # (c) A remote commit this clone has never fetched cannot be shown to be an ancestor.
    scenario = fresh("remote-commit-absent")
    other_clone = scratch / "open-pull-request-remote-commit-absent-other-clone"
    scenario.git(scratch, "clone", "--quiet", "--branch", "clean", str(scenario.origin),
                 str(other_clone))
    scenario.git(other_clone, "config", "user.name", "Other")
    scenario.git(other_clone, "config", "user.email", "other@example.invalid")
    scenario.commit("other.txt", "other\n", "Pushed from another clone", cwd=other_clone)
    scenario.git(other_clone, "push", "--quiet", "--no-verify", "origin", "clean")
    pushed = scenario.origin_ref("clean")
    scenario.on_branch("clean", "on-top.txt", "on top\n", "On top of an old head")
    result = scenario.push("--force", "origin", "clean")
    check("open pull request check: a forced push over a remote commit this clone never fetched "
          "is refused, and the refusal says to fetch",
          was_refused(result) and refused_header in result.stderr
          and "git fetch origin clean" in result.stderr
          and scenario.origin_ref("clean") == pushed, result.describe())

    # (b) A rewrite of a branch with no open pull request goes through, after asking gh.
    scenario = fresh("no-pull-request")
    scenario.extra_environment[FAKE_GH_OPEN_PULL_REQUESTS_VARIABLE] = "{}"
    rewrite(scenario, "clean")
    result = scenario.push("--force", "origin", "clean")
    check("open pull request check: a forced rewrite of a branch with no open pull request goes "
          "through",
          went_through(result) and scenario.origin_ref("clean") == scenario.head("clean")
          and any("--head clean" in call for call in scenario.fake_gh_calls()),
          result.describe())

    # (e) Deleting an open pull request's head branch closes the pull request: refused.
    scenario = fresh("deletion")
    result = scenario.push("origin", "--delete", "clean")
    check("open pull request check: deleting an open pull request's head branch is refused, "
          "saying it closes the pull request and how to close it first",
          was_refused(result) and "it deletes branch clean, the head of open pull request #4242"
          in result.stderr and "gh pr close 4242 --comment" in result.stderr
          and scenario.origin_ref("clean") is not None, result.describe())
    result = scenario.push("origin", "--delete", "conflicting")
    check("open pull request check: deleting a branch with no open pull request goes through",
          went_through(result) and scenario.origin_ref("conflicting") is None, result.describe())

    # The escape merge-lane-2 gives, the same assignment the Bash force-push guard reads.
    scenario = fresh("escape")
    rewrite(scenario, "clean")
    scenario.extra_environment[ESCAPE_HATCH_VARIABLE] = "1"
    result = scenario.push("--force", "origin", "clean")
    check(f"open pull request check: {ESCAPE_HATCH_VARIABLE}=1 lets a forced rewrite through",
          scenario.origin_ref("clean") == scenario.head("clean")
          and "this push is refused, because its update" not in result.stderr, result.describe())

    # Only origin is checked.
    scenario = fresh("other-remote")
    scenario.git(scenario.clone, "remote", "add", "other", str(scenario.origin))
    rewrite(scenario, "clean")
    result = scenario.push("--force", "other", "clean")
    check("open pull request check: a forced rewrite pushed to a remote other than origin is not "
          "checked", scenario.fake_gh_calls() == []
          and scenario.origin_ref("clean") == scenario.head("clean"), result.describe())

    # (f) When gh cannot answer, a rewrite or a deletion is refused; a fast-forward needs no answer.
    scenario = fresh("gh-logged-out")
    scenario.extra_environment[FAKE_GH_FAILURE_VARIABLE] = FAKE_GH_LOGGED_OUT
    pushed = scenario.origin_ref("clean")
    rewrite(scenario, "clean")
    result = scenario.push("--force", "origin", "clean")
    check("open pull request check: when gh is logged out, a forced rewrite is refused, saying "
          "what failed and to tell the user",
          was_refused(result) and "it forces an update to branch clean on origin, and "
          + lookup_failed + "gh pr list exited with status 4: " + FAKE_GH_LOGGED_OUT in result.stderr
          and "Tell the user this whole message, and do not push clean again until he answers."
          in result.stderr
          and "Run gh auth status" not in result.stderr
          and "CLAUDE_MERGE_LANE_ASKED_FOR_THIS_REWRITE=1" in result.stderr
          and scenario.origin_ref("clean") == pushed, result.describe())
    result = scenario.push("origin", "--delete", "conflicting")
    check("open pull request check: when gh is logged out, a deletion is refused",
          was_refused(result) and "it deletes branch conflicting on origin" in result.stderr
          and "do not push conflicting again until he answers" in result.stderr
          and scenario.origin_ref("conflicting") is not None, result.describe())
    scenario.git(scenario.clone, "reset", "--quiet", "--hard", pushed)
    scenario.on_branch("clean", "on-top.txt", "on top\n", "On top")
    result = scenario.push("origin", "clean")
    check("open pull request check: when gh is logged out, a fast-forward still goes through",
          went_through(result) and scenario.origin_ref("clean") == scenario.head("clean"),
          result.describe())

    # The check itself crashing, or missing, lets the push through and says so, as the other checks do.
    for label, text, expected in [
            ("crashes", "raise RuntimeError('broken')\n",
             "-deletion-refusal.py, exited with status 1, so this check lets the push through "
             "without checking whether it rewrites or deletes the head branch of an open pull "
             "request."),
            ("is missing", None, "head branches did not run, because ")]:
        hooks = make_layout(scratch, "layout-open-pull-request-check-" + label.replace(" ", "-"),
                            open_pull_request_branch_check_text=text,
                            include_open_pull_request_branch_check=text is not None)
        scenario = Scenario(scratch, "open-pull-request-check-" + label.replace(" ", "-"), hooks)
        result = scenario.push("origin", "clean")
        check(f"when the open pull request check {label}, the push goes through and the hook "
              f"says what was not checked and to tell the user",
              went_through(result) and expected in result.stderr
              and TELL_USER_LINE in result.stderr, result.describe())

    # gh that cannot be run, that hangs, or that prints what is not JSON: each refuses.
    specification = importlib.util.spec_from_file_location("open_pull_request_branch_check",
                                                           OPEN_PULL_REQUEST_BRANCH_CHECK)
    loaded = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(loaded)
    pushed_refs = f"refs/heads/clean {'1' * 40} refs/heads/clean {'2' * 40}\n"

    def runner_whose_git(cat_file, is_ancestor, gh_behaviour):
        def run(command, **options):
            if command[:2] == ["git", "cat-file"]:
                return cat_file(command, options)
            if command[:3] == ["git", "merge-base", "--is-ancestor"]:
                return is_ancestor(command)
            return gh_behaviour(command)
        return run

    def present(command, options):
        return subprocess.CompletedProcess(command, 0, options["input"].strip() + " commit 200\n",
                                           "")

    def exits(status, stderr_text=""):
        return lambda command, *_: subprocess.CompletedProcess(command, status, "", stderr_text)

    def runner_whose_gh(gh_behaviour):
        return runner_whose_git(present, exits(1), gh_behaviour)

    gh_options = []

    def recording_runner(command, **options):
        gh_options.append(options)
        return subprocess.CompletedProcess(command, 0, "[]", "")

    loaded.open_pull_request("clean", recording_runner)
    check("open pull request check: the gh call is given the gh timeout",
          [o.get("timeout") for o in gh_options] == [loaded.GH_TIMEOUT_SECONDS]
          and loaded.GH_TIMEOUT_SECONDS > 0, repr(gh_options))

    def raises(error):
        def behaviour(command):
            raise error
        return behaviour

    for label, behaviour, detail in [
            ("cannot be run", raises(FileNotFoundError(2, "No such file or directory", "gh")),
             "gh could not be run ("),
            ("does not answer in time", raises(subprocess.TimeoutExpired(["gh"], 10)),
             "gh pr list did not answer within 10 seconds"),
            ("prints what is not JSON",
             lambda command: subprocess.CompletedProcess(command, 0, "not json", ""),
             "gh pr list printed output that is not JSON")]:
        printed = io.StringIO()
        try:
            status = loaded.main(["origin", "url"], pushed_refs, printed, {},
                                 runner_whose_gh(behaviour))
        except Exception as error:  # A crash is this case's failure, not the suite's.
            status = repr(error)
        check(f"open pull request check: when gh {label}, a forced rewrite is refused, saying so",
              status == loaded.EXIT_REFUSE_PUSH and lookup_failed + detail in printed.getvalue(),
              (status, printed.getvalue()))


    # git failing to say whether an update is a fast-forward is a check that could not run,
    # not a rewrite: the check exits 2 without asking gh. A commit cat-file reports missing
    # still counts as not a fast-forward.
    def gh_must_not_be_asked(command):
        raise AssertionError("gh was asked")

    def gh_with_open_pull_request(command):
        return subprocess.CompletedProcess(command, 0, json.dumps([pull_request]), "")

    for label, cat_file, is_ancestor, gh_behaviour, expected_status, expected_text in [
            ("merge-base --is-ancestor exits 128", present,
             exits(128, "fatal: injected merge-base failure"), gh_must_not_be_asked,
             loaded.EXIT_CHECK_COULD_NOT_RUN,
             "pre-push: whether this push's update to branch clean is a fast-forward could not "
             "be checked: git merge-base --is-ancestor exited with status 128: fatal: injected "
             "merge-base failure."),
            ("cat-file --batch-check exits 128", exits(128, "fatal: injected cat-file failure"),
             exits(1), gh_must_not_be_asked, loaded.EXIT_CHECK_COULD_NOT_RUN,
             "git cat-file --batch-check exited with status 128: fatal: injected cat-file "
             "failure."),
            ("cat-file reports the remote commit missing",
             lambda command, options: subprocess.CompletedProcess(
                 command, 0, options["input"].strip() + " missing\n", ""),
             exits(128, "fatal: Not a valid commit name"), gh_with_open_pull_request,
             loaded.EXIT_REFUSE_PUSH, refused_header)]:
        printed = io.StringIO()
        try:
            status = loaded.main(["origin", "url"], pushed_refs, printed, {},
                                 runner_whose_git(cat_file, is_ancestor, gh_behaviour))
        except Exception as error:  # A crash is this case's failure, not the suite's.
            status = repr(error)
        check(f"open pull request check: when {label}, the check exits {expected_status} "
              f"and says why",
              status == expected_status and expected_text in printed.getvalue(),
              (status, printed.getvalue()))

    # One update git cannot check does not stop the check of the others: a later deletion of
    # an open pull request's head branch in the same push is still refused.
    def gh_with_open_pull_request_on(branch):
        def answer(command):
            listed = [pull_request] if command[command.index("--head") + 1] == branch else []
            return subprocess.CompletedProcess(command, 0, json.dumps(listed), "")
        return answer

    several_refs = (f"refs/heads/clean {'1' * 40} refs/heads/clean {'2' * 40}\n"
                    f"(delete) {'0' * 40} refs/heads/conflicting {'3' * 40}\n")
    printed = io.StringIO()
    try:
        status = loaded.main(["origin", "url"], several_refs, printed, {},
                             runner_whose_git(present, exits(128, "fatal: injected"),
                                              gh_with_open_pull_request_on("conflicting")))
    except Exception as error:  # A crash is this case's failure, not the suite's.
        status = repr(error)
    check("open pull request check: when git cannot check one update, a deletion of an open "
          "pull request's head branch later in the same push is still refused, exit 10, and "
          "the unchecked update is named",
          status == loaded.EXIT_REFUSE_PUSH
          and "it deletes branch conflicting, the head of open pull request #4242"
          in printed.getvalue()
          and "whether this push's update to branch clean is a fast-forward could not be "
          "checked" in printed.getvalue(), (status, printed.getvalue()))

    # The test helper origin_ref tells a missing ref from a git failure.
    broken = Scenario(scratch, "origin-ref-broken-origin", real)
    shutil.rmtree(broken.origin / "objects")
    try:
        broken.origin_ref("clean")
        raised = None
    except RuntimeError as error:
        raised = str(error)
    check("origin_ref raises when git rev-parse fails, rather than answering no such ref",
          raised is not None and "exited 128" in raised, raised)


# --- Files set back to a version main has replaced --------------------------

REVERT_REFUSAL_HEADER = ("pre-push: branch %s sets a file back to a version that "
                         "origin/main has replaced; this push is refused.")
REVERT_NOT_CHECKED = ("pre-push: branch %s was not checked for files set back to a version "
                      "that origin/main has replaced, because %s.")


def hand_checked_commit(stderr):
    """The commit named by the first hand conflict check line in a push's stderr."""
    return next((line.rsplit(" ", 1)[-1] for line in stderr.splitlines()
                 if " by hand from your worktree: python3 scripts/branch-conflict-check.py "
                 in line), "")


def revert_check_not_run_lines(branch, commit):
    """The two lines that say a branch never reached the revert check, and when to run it."""
    return ("Nor was %s checked for files set back to a version that origin/main has "
            "replaced, because that check runs only on a branch the conflict check finds "
            "clean.\n"
            "Once the hand conflict check of %s prints VERDICT: CLEAN, check it for files set "
            "back too: python3 scripts/branch-reverts-a-file-to-an-older-main-version-check.py "
            "--head %s" % (branch, branch, commit[:SHORT_COMMIT_LENGTH]))


def no_branch_revert_lines(branches):
    """The lines that say no branch reached the revert check, and when to run it, after the
    hand conflict check lines and before TELL_USER_LINE."""
    return ["Nor was any of them checked for files set back to a version that origin/main has "
            "replaced, because that check runs only on a branch the conflict check finds clean.",
            *("Once the hand conflict check of %s prints VERDICT: CLEAN, check it for files set back "
              "too: python3 scripts/branch-reverts-a-file-to-an-older-main-version-check.py "
              "--head %s" % (branch, commit[:SHORT_COMMIT_LENGTH])
              for branch, commit in branches)]


def revert_hand_check_line(commit):
    return ("Check it by hand from your worktree: python3 scripts/branch-reverts-a-file-to-an-"
            "older-main-version-check.py --head %s" % commit[:SHORT_COMMIT_LENGTH])


FAKE_REVERT_CHECK_NO_ANSWER = FAKE_CHECK_PREAMBLE + """\
print("fake revert check: git failed", file=sys.stderr)
sys.exit(2)
"""

FAKE_REVERT_CHECK_FOUND_WITHOUT_VERDICT = FAKE_CHECK_PREAMBLE + """\
print("no verdict line here")
sys.exit(1)
"""

FAKE_REVERT_CHECK_HANGS = FAKE_CHECK_HANGS


def squash_by_soft_reset(scenario, branch):
    """Cut a branch before main's last change to shared.txt, then squash it onto main.

    The squash keeps the old index, so the branch sets shared.txt back."""
    scenario.git(scenario.clone, "switch", "--quiet", "-c", branch, scenario.base)
    scenario.commit("squashed-work.txt", "work\n", "Work before the squash")
    scenario.git(scenario.clone, "reset", "--soft", "origin/main")
    scenario.git(scenario.clone, "commit", "--quiet", "-m", "Squashed work")
    return scenario.head(branch)


def run_revert_check_cases(scratch):
    real = make_layout(scratch, "layout-revert-real")
    scenario = Scenario(scratch, "revert-real", real)
    commit = squash_by_soft_reset(scenario, "squashed")
    result = scenario.push("origin", "squashed")
    check("a branch squashed by soft reset onto a newer main is refused",
          was_refused(result), result.describe())
    check("and never reaches origin", scenario.origin_ref("squashed") is None,
          repr(scenario.origin_ref("squashed")))
    check("the refusal names the branch and passes on the check's verdict, file and commit",
          REVERT_REFUSAL_HEADER % "squashed" in result.stderr
          and "VERDICT: BRANCH-REVERTS-A-FILE-TO-AN-OLDER-MAIN-VERSION" in result.stderr
          and "shared.txt: back to its version before %s (Main side)"
          % scenario.head("origin/main")[:SHORT_COMMIT_LENGTH] in result.stderr,
          result.describe())
    check("and does not give the conflict refusal's merge instruction",
          "Once the merge is committed" not in result.stderr, result.describe())

    result = scenario.push("origin", "clean")
    check("(control) a clean branch still goes through, with the revert check silent",
          went_through(result) and conflict_check_said_nothing(result.stderr),
          result.describe())

    for label, revert_check, reason in (
            ("is missing", None, None),
            ("cannot decide", FAKE_REVERT_CHECK_NO_ANSWER,
             "it could not decide: fake revert check: git failed"),
            ("exits 1 without a verdict line", FAKE_REVERT_CHECK_FOUND_WITHOUT_VERDICT,
             "it exited 1 without a VERDICT: BRANCH-REVERTS-A-FILE-TO-AN-OLDER-MAIN-VERSION "
             "line")):
        hooks = make_layout(scratch, "layout-revert-" + label.replace(" ", "-"),
                            revert_check=revert_check)
        scenario = Scenario(scratch, "revert-" + label.replace(" ", "-"), hooks)
        commit = squash_by_soft_reset(scenario, "squashed")
        result = scenario.push("origin", "squashed")
        if reason is None:
            reason = "%s is missing" % (hooks.parent / REAL_REVERT_CHECK.name)
        check("when the revert check %s, the push goes ahead" % label,
              went_through(result), result.describe())
        check("and says the branch was not checked, why, and the command to check it by hand",
              REVERT_NOT_CHECKED % ("squashed", reason) in result.stderr
              and revert_hand_check_line(commit) in result.stderr, result.describe())
        check("and then, once, that the push goes through",
              result.stderr.count(PUSH_GOES_ON_LINE) == 1
              and result.stderr.index(PUSH_GOES_ON_LINE)
              > result.stderr.index(REVERT_NOT_CHECKED % ("squashed", reason)),
              result.describe())

    hooks = make_layout(scratch, "layout-revert-hangs", revert_check=FAKE_REVERT_CHECK_HANGS)
    scenario = Scenario(scratch, "revert-hangs", hooks)
    scenario.extra_environment[TIME_BUDGET_VARIABLE] = "3"
    commit = squash_by_soft_reset(scenario, "squashed")
    result = scenario.push("origin", "squashed")
    check("when the revert check hangs past the time budget, the push goes ahead",
          went_through(result), result.describe())
    check("and says it was stopped at the budget",
          REVERT_NOT_CHECKED % ("squashed", "it had not finished when the 3-second time "
                                "budget ran out, and was stopped") in result.stderr,
          result.describe())

    hooks = make_layout(scratch, "layout-revert-conflict-no-answer",
                        conflict_check=FAKE_CHECK_NO_ANSWER)
    scenario = Scenario(scratch, "revert-conflict-no-answer", hooks)
    commit = squash_by_soft_reset(scenario, "squashed")
    result = scenario.push("origin", "squashed")
    check("a squashed branch the conflict check cannot decide on goes ahead",
          went_through(result), result.describe())
    check("and the push says the revert check did not run on it, with the command to run it",
          revert_check_not_run_lines("squashed", commit) in result.stderr,
          result.describe())

    hooks = make_layout(scratch, "layout-revert-after-conflict",
                        conflict_check=FAKE_CHECK_ALWAYS_CONFLICT,
                        revert_check=FAKE_CHECK_ALWAYS_CONFLICT)
    scenario = Scenario(scratch, "revert-after-conflict", hooks)
    result = scenario.push("origin", "clean")
    check("a branch that conflicts is not sent to the revert check",
          scenario.fake_check_calls() == ["--head %s" % scenario.head("clean")],
          repr(scenario.fake_check_calls()))


def main():
    run_unit_cases()
    # Resolved, because git and the hooks print resolved paths: on macOS the temporary
    # directory is under /var, a symlink to /private/var.
    scratch = Path(tempfile.mkdtemp(prefix="pre-push-test-")).resolve()
    try:
        run_push_cases(scratch)
        run_no_test_suites_cases(scratch)
        run_mutation_testing_worktree_cases(scratch)
        run_open_pull_request_branch_cases(scratch)
        run_revert_check_cases(scratch)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    if failures:
        print(f"\n{len(failures)} case(s) failed")
        return 1
    print("\nall cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
