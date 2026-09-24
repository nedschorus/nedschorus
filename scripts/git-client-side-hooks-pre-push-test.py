#!/usr/bin/env python3
"""Tests for scripts/git-client-side-hooks/pre-push, the hook that refuses to
push a branch that conflicts with main, and for the Python file it runs,
scripts/git-client-side-hooks-pre-push-conflict-check.py.

Run: python3 scripts/git-client-side-hooks-pre-push-test.py
Prints one line per case and exits non-zero if any case fails.

Every push case pushes with real git, from throwaway clones of throwaway bare
repositories under a temporary directory. Each clone's own core.hooksPath
points at a copy of the hooks laid out as this checkout lays them out, under
the temporary directory:
    <layout>/scripts/git-client-side-hooks/pre-push
    <layout>/scripts/git-client-side-hooks-pre-push-conflict-check.py
    <layout>/scripts/branch-conflict-check.py
So each case runs exactly what git runs on a seat's push. A case that needs
the conflict check to misbehave puts a fake check at that last path, and
leaves the real one alone. No real repository's config is read or written:
global and system git config are shut out, and every GIT_ variable is
removed from each case's environment.

The hook must never stop a push it should let through (user, 2026-09-23:
"Messing up how git works or how we push is a big problem"), so most cases
here are pushes that must go through, one for each way the check can fail.
Every push runs under an outer timeout in its own process group, so a hook
that hangs fails its case instead of wedging the suite.
"""

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
REAL_CONFLICT_CHECK = SCRIPTS_DIRECTORY / "branch-conflict-check.py"

TIME_BUDGET_VARIABLE = "NEDSCHORUS_PRE_PUSH_CONFLICT_CHECK_SECONDS"
FAKE_CHECK_LOG_VARIABLE = "PRE_PUSH_TEST_FAKE_CHECK_LOG"
SESSION_VARIABLE = "CLAUDE_CODE_BRIDGE_SESSION_ID"
LOCAL_SESSION_VARIABLE = "CLAUDE_CODE_SESSION_ID"
FAKE_SESSION = "session_0FakePrePushTestSessionAAAA"

OUTER_PUSH_TIMEOUT_SECONDS = 30
# A hanging fake check sleeps this long. Longer than the outer timeout, so a
# hook that fails to stop it still fails its case; short enough that one
# missed by every cleanup exits on its own soon after the suite does.
FAKE_HANG_SECONDS = 90
HANGING_CHECK_BUDGET_SECONDS = "1"
HANGING_CASE_WALL_CLOCK_LIMIT_SECONDS = 15

REFUSAL_HEADER = "pre-push: branch %s conflicts with origin/main; this push is refused."
CLOSING_INSTRUCTION = "Once the merge is committed, push again."

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


# --- Layouts and repositories ---------------------------------------------

def make_layout(parent, name, conflict_check=REAL_CONFLICT_CHECK,
                runner_text=None, include_runner=True):
    """A copy of this checkout's hooks, laid out as the hook expects.

    conflict_check is a Path to copy, a string of fake check source, or None
    for no check at all. runner_text replaces the Python file the hook runs.
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
    if isinstance(conflict_check, Path):
        shutil.copy2(conflict_check, scripts / REAL_CONFLICT_CHECK.name)
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
    check("and the hook says nothing",
          "pre-push:" not in result.stderr, result.describe())

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
            check("%s: and the hook says nothing" % label,
                  "pre-push:" not in outcome.stderr, outcome.describe())
        else:
            check("%s: and says why it did not check" % label,
                  expected_text in outcome.stderr, outcome.describe())
        return outcome

    missing = make_layout(scratch, "layout-check-missing", conflict_check=None)
    failing = Scenario(scratch, "check-missing", missing)
    outcome = failing.push("origin", "conflicting")
    check("check missing: the push goes through", went_through(outcome),
          outcome.describe())
    check("check missing: and says the check is missing",
          "branch-conflict-check.py is missing" in outcome.stderr, outcome.describe())

    failing_check_case("check-crashes", FAKE_CHECK_CRASHES,
                       "exited 1 without a VERDICT: CONFLICT line")
    outcome = failing_check_case("check-no-answer", FAKE_CHECK_NO_ANSWER,
                                 "gave no answer for branch conflicting")
    check("check-no-answer: and passes on the check's own lines",
          "UNFETCHED: fake no-answer line from the check." in outcome.stderr,
          outcome.describe())
    failing_check_case("check-unexpected-status", FAKE_CHECK_UNEXPECTED_STATUS,
                       "it exited 7")
    failing_check_case("check-conflict-text-exit-zero",
                       FAKE_CHECK_CONFLICT_TEXT_EXIT_ZERO, "", silent=True)

    for label, source in (("check-hangs", FAKE_CHECK_HANGS),
                          ("check-hangs-with-child", FAKE_CHECK_HANGS_WITH_CHILD),
                          ("check-ignores-sigterm", FAKE_CHECK_IGNORES_SIGTERM),
                          ("check-records-sigterm", FAKE_CHECK_RECORDS_SIGTERM)):
        outcome = failing_check_case(label, source, "had not finished when the 1-second budget ran out",
                                     budget=HANGING_CHECK_BUDGET_SECONDS)
        check("%s: and the push is not held for long" % label,
              outcome.seconds < HANGING_CASE_WALL_CLOCK_LIMIT_SECONDS,
              "%.1f seconds" % outcome.seconds)

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
    check("no python3 on PATH: and says so", "no python3 on PATH" in outcome.stderr,
          outcome.describe())

    hooks = make_layout(scratch, "layout-runner-broken",
                        conflict_check=FAKE_CHECK_ALWAYS_CONFLICT,
                        runner_text="this is not python (\n")
    failing = Scenario(scratch, "runner-broken", hooks)
    outcome = failing.push("origin", "conflicting")
    check("the Python file fails to run: the push goes through",
          went_through(outcome), outcome.describe())
    check("the Python file fails to run: and says the check failed",
          "the conflict check failed (exit 1)" in outcome.stderr, outcome.describe())

    hooks = make_layout(scratch, "layout-runner-missing",
                        conflict_check=FAKE_CHECK_ALWAYS_CONFLICT, include_runner=False)
    failing = Scenario(scratch, "runner-missing", hooks)
    outcome = failing.push("origin", "conflicting")
    check("the Python file is missing: the push goes through",
          went_through(outcome), outcome.describe())
    check("the Python file is missing: and says so",
          "git-client-side-hooks-pre-push-conflict-check.py is missing" in outcome.stderr,
          outcome.describe())

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


def main():
    run_unit_cases()
    scratch = Path(tempfile.mkdtemp(prefix="pre-push-test-"))
    try:
        run_push_cases(scratch)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    if failures:
        print(f"\n{len(failures)} case(s) failed")
        return 1
    print("\nall cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
