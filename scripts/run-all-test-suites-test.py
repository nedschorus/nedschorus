#!/usr/bin/env python3
"""Tests for scripts/run-all-test-suites.py.

Every case runs the program as a subprocess against a fixture git
repository built in a scratch directory, whose "suites" are a few lines
each: they record that they ran, print what the case needs, and exit with
the code the case needs. No case runs the project's real suites — this
file is itself one of them, and a full run inside a full run would never
end.

Every run passes its own --lock-file and --log-dir inside the scratch
directory. That is what lets this suite run inside a real full run, which
holds the machine's default lock for the whole of it.

Which suites ran is read from a file each fixture suite appends its own
path to (named by RAN_FILE_VARIABLE, which the program passes on through
the environment), not from the program's report, so a case about what was
run does not trust the thing it is testing.

Run: python3 scripts/run-all-test-suites-test.py   (exit 0 = all passed)
"""

import fcntl
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

# Before anything runs git: a run started with GIT_DIR set, or with another
# variable that redirects git, must still build this suite's scratch
# repositories where the suite says, not in the repository the variable names.
_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    pathlib.Path(__file__).resolve().with_name(
        "git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
PROGRAM = SCRIPTS_DIR / "run-all-test-suites.py"
RAN_FILE_VARIABLE = "RUN_ALL_TEST_SUITES_TEST_RAN_FILE"
RENDEZVOUS_WAIT_VARIABLE = "RUN_ALL_TEST_SUITES_TEST_RENDEZVOUS_SECONDS"

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


# Each fixture suite records its own path, relative to the checkout, then
# does what its BODY says.
SUITE_PREAMBLE = f'''import os, sys, time, signal, pathlib
with open(os.environ["{RAN_FILE_VARIABLE}"], "a") as ran:
    ran.write(sys.argv[0] + "\\n")
'''

PASSES = "print('ok')\n"
SAYS_PASSED_BUT_EXITS_ONE = "print('all cases passed')\nsys.exit(1)\n"
SAYS_FAIL_BUT_EXITS_ZERO = "print('FAIL: this text is not the verdict')\nsys.exit(0)\n"
SKIPS_TWO = ("print('SKIP  end-to-end: tmux is not installed')\n"
             "print('PASS  tool_result blocks are skipped entirely')\n"
             "print(' SKIP  indented, not a skip line')\n"
             "print('SKIPPED is not SKIP followed by a space')\n"
             "print('SKIP  per-seat end-to-end: could not create a session')\n"
             "print('all cases passed')\n")
KILLED_BY_SIGTERM = "os.kill(os.getpid(), signal.SIGTERM)\ntime.sleep(5)\n"

# A suite that needs a git repository, written the way the 21 suites on main
# that need one are written: build it with `git init` in a scratch directory,
# configure an identity, commit — and never check that `init` worked. It
# writes down what it saw and what it built, so the case can tell a suite
# that built its own repository from one that wrote into somebody else's.
# nedschorus#639.
BUILDS_A_SCRATCH_REPOSITORY = f'''import json, subprocess, tempfile
here = pathlib.Path(os.environ["{RAN_FILE_VARIABLE}"]).parent
scratch = tempfile.mkdtemp(dir=str(here), prefix="the-suite-s-own-repository-")


def git(*arguments):
    return subprocess.run(["git", "-C", scratch, "-c", "core.hooksPath=/dev/null",
                           "-c", "commit.gpgsign=false", *arguments],
                          capture_output=True, text=True, check=False)


git("init", "-q")
git("config", "user.name", "the suite's test identity")
git("config", "user.email", "suite-test@nedschorus.invalid")
pathlib.Path(scratch, "the-suite-s-own-file.txt").write_text("the suite's work\\n")
git("add", "-A")
git("commit", "-q", "-m", "the suite's own commit")

# A child this suite gives GIT_DIR of its own must still get it: that is the
# fixture pattern nc-systems/cold-read/tests/cold-read-grid-test.py and
# nc-systems/cold-read/tests/cold-read-cell-common-test.py are built on.
child = dict(os.environ)
child["GIT_DIR"] = str(here / "the-child-s-own-git-directory")
child_saw = subprocess.run(
    [sys.executable, "-c", "import os; print(os.environ.get('GIT_DIR', 'unset'))"],
    env=child, capture_output=True, text=True, check=False)

pathlib.Path(here, "what-the-suite-saw.json").write_text(json.dumps(dict(
    git_variables_seen=sorted(name for name in os.environ if name.startswith("GIT_")),
    repository_built_at_its_own_scratch=pathlib.Path(scratch, ".git").is_dir(),
    a_variable_that_is_not_git_s=os.environ.get("{RENDEZVOUS_WAIT_VARIABLE}", "unset"),
    git_dir_the_child_was_given=child_saw.stdout.strip(),
)))
'''

VICTIM_IDENTITY = "the victim's own identity"


def make_victim_repository(root, suite_path):
    """A throwaway repository standing in for the live checkout an ambient
    GIT_DIR names, so a case can see whether a suite's git commands landed in
    it. Given a committing identity of its own in its local config, because
    overwriting that is the part of nedschorus#639 that outlives the run.

    It tracks `suite_path`. The case about the environment a suite is
    launched WITH passes the checkout's own suite path, the 2026-09-22
    incident's own shape — a second clone of the same project, with the same
    paths in it. The case about the program's own git calls passes a path the
    checkout does not track, so a suite list read from the victim instead of
    the checkout shows in what runs."""
    victim = root / "victim"
    victim.mkdir()
    git(victim, "init", "-q", "-b", "main")
    git(victim, "config", "user.name", VICTIM_IDENTITY)
    git(victim, "config", "user.email", "victim@nedschorus.invalid")
    (victim / suite_path).write_text("the victim's copy, which is never run\n")
    git(victim, "add", "-A")
    git(victim, "commit", "-q", "-m", "the victim's own commit")
    return victim


def victim_state(victim):
    return dict(
        tracked=sorted(git(victim, "ls-files").stdout.split()),
        commits=git(victim, "rev-list", "--count", "--all").stdout.strip(),
        identity=git(victim, "config", "--local", "user.name").stdout.strip(),
    )


def rendezvous(mine, theirs):
    """Passes only when the other suite is running at the same time."""
    return (f"wait = float(os.environ['{RENDEZVOUS_WAIT_VARIABLE}'])\n"
            f"here = pathlib.Path(os.environ['{RAN_FILE_VARIABLE}']).parent\n"
            f"(here / '{mine}').touch()\n"
            f"deadline = time.monotonic() + wait\n"
            f"while time.monotonic() < deadline:\n"
            f"    if (here / '{theirs}').exists():\n"
            f"        sys.exit(0)\n"
            f"    time.sleep(0.02)\n"
            f"sys.exit(1)\n")


def git(repo, *arguments):
    return subprocess.run(["git", "-C", str(repo), "-c", "core.hooksPath=/dev/null",
                           "-c", "user.name=fixture", "-c", "user.email=fixture@invalid",
                           "-c", "commit.gpgsign=false", *arguments],
                          capture_output=True, text=True, check=True)


def make_repo(root, tracked, untracked=None, commit=True):
    """A git repository at root/repo holding `tracked` (added, and committed
    when `commit`) and `untracked` (on disk only); both map path -> body."""
    repo = root / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    for files in (tracked, untracked or {}):
        for relative, body in files.items():
            path = repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(SUITE_PREAMBLE + body)
    if tracked:
        git(repo, "add", "--", *tracked)
        if commit:
            git(repo, "commit", "-q", "-m", "fixture")
    return repo


def run(root, *arguments, checkout=None, lock_file=None, rendezvous_seconds="20",
        environment_extra=None):
    """The program run against root/repo with its own lock and log directory.

    environment_extra goes into the environment the PROGRAM is launched with,
    which is how a case gives the program's own process an ambient variable
    and then asks what its suites saw."""
    environment = dict(os.environ)
    environment[RAN_FILE_VARIABLE] = str(root / "ran.txt")
    environment[RENDEZVOUS_WAIT_VARIABLE] = rendezvous_seconds
    environment.update(environment_extra or {})
    command = [sys.executable, str(PROGRAM),
               "--checkout", str(checkout if checkout is not None else root / "repo"),
               "--log-dir", str(root / "logs"),
               "--lock-file", str(lock_file if lock_file is not None else root / "run.lock"),
               "--recorded-inputs-directory", str(root / "recordings"),
               *arguments]
    return subprocess.run(command, capture_output=True, text=True, env=environment,
                          stdin=subprocess.DEVNULL, check=False)


def ran(root):
    path = root / "ran.txt"
    return sorted(path.read_text().split()) if path.exists() else []


def lines(text):
    return text.splitlines()


def load_program_module():
    spec = importlib.util.spec_from_file_location("run_all_test_suites", PROGRAM)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MIXED_TRACKED = {
    "a-test.py": PASSES,
    "nested/deeper/b-test.py": PASSES,
    "says-passed-but-exits-one-test.py": SAYS_PASSED_BUT_EXITS_ONE,
    "says-fail-but-exits-zero-test.py": SAYS_FAIL_BUT_EXITS_ZERO,
    "skips-two-test.py": SKIPS_TWO,
    "killed-test.py": KILLED_BY_SIGTERM,
    "design-to-main-test-fixture.py": PASSES,
}
MIXED_UNTRACKED = {"untracked-test.py": PASSES}
MIXED_SUITES = sorted(path for path in MIXED_TRACKED if path.endswith("-test.py"))

# --- What runs: the suites git lists, and nothing else ------------------------
with tempfile.TemporaryDirectory() as scratch:
    root = pathlib.Path(scratch)
    repo = make_repo(root, MIXED_TRACKED, MIXED_UNTRACKED)
    result = run(root)
    out = lines(result.stdout)
    check("every tracked *-test.py ran, including one in a directory nothing names",
          ran(root) == MIXED_SUITES, ran(root))
    check("an untracked *-test.py is not run", "untracked-test.py" not in ran(root))
    check("a tracked file not named *-test.py is not run",
          "design-to-main-test-fixture.py" not in ran(root))

    # --- The verdict is the exit code, in both directions ---------------------
    check("the program exits 1 when any suite failed", result.returncode == 1,
          (result.returncode, result.stderr))
    check("a suite printing 'all cases passed' that exits 1 is FAIL, exit 1",
          any(line.startswith("FAIL says-passed-but-exits-one-test.py exit 1 (")
              for line in out), out)
    check("a suite printing 'FAIL' that exits 0 is PASS",
          any(line.startswith("PASS says-fail-but-exits-zero-test.py (") for line in out),
          out)
    check("a suite killed by a signal is FAIL naming the signal",
          any(line.startswith("FAIL killed-test.py killed by SIGTERM") for line in out),
          out)

    # --- Skipped cases: counted from SKIP lines, never a verdict --------------
    check("a suite that printed two SKIP lines is PASS, with 2 skipped",
          any(line.startswith("PASS skips-two-test.py (") and line.endswith(", 2 skipped)")
              for line in out), out)
    check("each SKIP line is listed under its suite",
          "skips-two-test.py: SKIP  end-to-end: tmux is not installed" in out
          and "skips-two-test.py: SKIP  per-seat end-to-end: could not create a session"
          in out, out)
    check("an indented SKIP, SKIPPED, and a case name containing 'skipped' are not counted",
          not any("indented" in line or "SKIPPED is" in line or "tool_result" in line
                  for line in out), out)

    # --- The end of the output holds everything needed ------------------------
    check("the last line is the SUMMARY, with the counts",
          out[-1].startswith("SUMMARY: 4 passed, 2 failed, 6 total; 2 cases skipped in 1 suites;"),
          out[-1:])
    check("the failed suites are repeated before the SUMMARY, each with its log",
          "2 failed:" in out
          and any(line.startswith("FAIL killed-test.py killed by SIGTERM — log ")
                  for line in out), out)
    check("the first line names the checkout, its commit and the suite count",
          out[0].startswith(f"run-all-test-suites: {repo.resolve()} at ")
          and "(tracked files match that commit); 6 suites listed by git;" in out[0],
          out[:1])
    check("the whole report is also written to report.txt in the log directory",
          (root / "logs" / "report.txt").read_text() == result.stdout)
    nested_log = root / "logs" / "nested__deeper__b-test.py.log"
    check("each suite's log is named by its whole path, so no two can collide",
          nested_log.exists() and nested_log.read_text() == "ok\n",
          sorted(path.name for path in (root / "logs").iterdir()))

    # --- The lock names its holder after the run ------------------------------
    holder = (root / "run.lock").read_text()
    check("the lock file names the run that held it: pid, checkout, start",
          holder.startswith("pid ") and f"checkout {repo.resolve()}, started 20" in holder,
          holder)

# --- A *-test.sh suite runs under sh, and keeps no recording ------------------
SHELL_SUITE_PREAMBLE = f'echo "$0" >> "${RAN_FILE_VARIABLE}"\n'
with tempfile.TemporaryDirectory() as scratch:
    root = pathlib.Path(scratch)
    repo = make_repo(root, {"a-test.py": PASSES})
    (repo / "passes-test.sh").write_text(SHELL_SUITE_PREAMBLE + "exit 0\n")
    (repo / "nested/fails-test.sh").parent.mkdir()
    (repo / "nested/fails-test.sh").write_text(SHELL_SUITE_PREAMBLE + "exit 1\n")
    git(repo, "add", "--", "passes-test.sh", "nested/fails-test.sh")
    git(repo, "commit", "-q", "-m", "shell suites")
    result = run(root)
    check("a tracked *-test.sh runs under sh, beside the *-test.py suites",
          ran(root) == ["a-test.py", "nested/fails-test.sh", "passes-test.sh"], ran(root))
    check("a *-test.sh suite is judged by its exit code, and its failure fails the run",
          result.returncode == 1
          and "FAIL nested/fails-test.sh exit 1" in result.stdout
          and lines(result.stdout)[-1].startswith("SUMMARY: 2 passed, 1 failed, 3 total;"),
          (result.returncode, result.stdout, result.stderr))
    check("a *-test.sh suite keeps no recording of its inputs",
          not list((root / "recordings").glob("*/*test.sh.json")),
          sorted(str(path) for path in (root / "recordings").glob("*/*")))
    (root / "ran.txt").unlink()
    result = run(root, "--only-suites-whose-recorded-inputs-changed-since", "HEAD")
    check("so every selective run selects a *-test.sh suite, even unchanged",
          "SELECTED passes-test.sh: no recording of its inputs on this machine yet"
          in result.stdout and "passes-test.sh" in ran(root),
          (result.stdout, ran(root)))

# --- An all-passing checkout exits 0 -----------------------------------------
with tempfile.TemporaryDirectory() as scratch:
    root = pathlib.Path(scratch)
    make_repo(root, {"a-test.py": PASSES, "b/c-test.py": PASSES})
    result = run(root)
    check("the program exits 0 when every suite exited 0", result.returncode == 0,
          (result.returncode, result.stdout, result.stderr))
    check("an all-passing SUMMARY counts no failures and no skips",
          lines(result.stdout)[-1].startswith(
              "SUMMARY: 2 passed, 0 failed, 2 total; 0 cases skipped in 0 suites;"),
          lines(result.stdout)[-1:])

# --- A suite added but not committed runs; modified tracked files are said ---
with tempfile.TemporaryDirectory() as scratch:
    root = pathlib.Path(scratch)
    repo = make_repo(root, {"a-test.py": PASSES})
    (repo / "added-test.py").write_text(SUITE_PREAMBLE + PASSES)
    git(repo, "add", "--", "added-test.py")
    result = run(root)
    check("a suite added to the index but not committed is run",
          ran(root) == ["a-test.py", "added-test.py"], ran(root))
    check("the first line says when tracked files differ from the commit",
          "(tracked files differ from that commit)" in lines(result.stdout)[0],
          lines(result.stdout)[:1])

# --- -j: N suites at once, and -j 1 is one at a time -------------------------
with tempfile.TemporaryDirectory() as scratch:
    root = pathlib.Path(scratch)
    make_repo(root, {"first-test.py": rendezvous("first.flag", "second.flag"),
                     "second-test.py": rendezvous("second.flag", "first.flag")})
    result = run(root, "-j", "2")
    check("-j 2 runs two suites at the same time", result.returncode == 0,
          (result.returncode, result.stdout))
with tempfile.TemporaryDirectory() as scratch:
    root = pathlib.Path(scratch)
    make_repo(root, {"first-test.py": rendezvous("first.flag", "second.flag"),
                     "second-test.py": rendezvous("second.flag", "first.flag")})
    result = run(root, "-j", "1", rendezvous_seconds="0.5")
    check("-j 1 runs one suite at a time", result.returncode == 1
          and lines(result.stdout)[-1].startswith("SUMMARY: 1 passed, 1 failed"),
          (result.returncode, result.stdout))
    check("-j 1 overrides the default, and the first line names it",
          "; -j 1; logs in " in lines(result.stdout)[0], lines(result.stdout)[:1])
with tempfile.TemporaryDirectory() as scratch:
    root = pathlib.Path(scratch)
    make_repo(root, {"first-test.py": rendezvous("first.flag", "second.flag"),
                     "second-test.py": rendezvous("second.flag", "first.flag")})
    result = run(root)
    expected_jobs = min(os.cpu_count() or 4, 2)
    check("with no -j, the run uses one job per core, capped at the 2 suites it runs, and "
          "the first line names the number used",
          f"; -j {expected_jobs}; logs in " in lines(result.stdout)[0]
          and result.returncode == (0 if expected_jobs == 2 else 1),
          (result.returncode, result.stdout))

# --- --python: the given interpreter runs each suite and names itself ---------
with tempfile.TemporaryDirectory() as scratch:
    root = pathlib.Path(scratch)
    make_repo(root, {"a-test.py": PASSES})
    fake = root / "fake-python"
    invocations = root / "fake-python-invocations.txt"
    fake.write_text("#!/bin/sh\n"
                    'if [ "$1" = --version ]; then echo "Python 9.99.9-fake"; exit 0; fi\n'
                    f'echo "$@" >> "{invocations}"\n'
                    f'exec "{sys.executable}" "$@"\n')
    fake.chmod(0o755)
    result = run(root, "--python", str(fake))
    check("--python runs each suite as <interpreter> -u <path>",
          invocations.exists() and invocations.read_text() == "-u a-test.py\n",
          invocations.read_text() if invocations.exists() else "never invoked")
    check("the SUMMARY names the interpreter by its own --version answer",
          lines(result.stdout)[-1].endswith("; Python 9.99.9-fake"),
          lines(result.stdout)[-1:])
    result = run(root, "--python", str(root / "no-such-python"))
    check("an interpreter that is not there is exit 2, and nothing runs",
          result.returncode == 2 and "--python" in result.stderr and ran(root) == ["a-test.py"],
          (result.returncode, result.stderr))

# --- One run per lock: a held lock is exit 3, and nothing runs ----------------
with tempfile.TemporaryDirectory() as scratch:
    root = pathlib.Path(scratch)
    make_repo(root, {"a-test.py": PASSES})
    lock_file = root / "held.lock"
    with open(lock_file, "a+") as held:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        held.write("pid 424242, checkout /elsewhere, started 2026-09-21T00:00:00Z\n")
        held.flush()
        result = run(root, lock_file=lock_file)
        check("a run while another holds the lock exits 3", result.returncode == 3,
              (result.returncode, result.stdout, result.stderr))
        check("the refusal names the holder, and says to run again after it finishes",
              "pid 424242, checkout /elsewhere" in result.stderr
              and "Run this again after that run has finished." in result.stderr,
              result.stderr)
        check("a refused run runs no suite and prints nothing on stdout",
              ran(root) == [] and result.stdout == "", (ran(root), result.stdout))
    result = run(root, lock_file=lock_file)
    check("once the lock is released the next run proceeds",
          result.returncode == 0 and ran(root) == ["a-test.py"],
          (result.returncode, result.stderr))

# --- Refusals before anything runs: exit 2 -----------------------------------
with tempfile.TemporaryDirectory() as scratch:
    root = pathlib.Path(scratch)
    repo = make_repo(root, {"a-test.py": PASSES, "sub/b-test.py": PASSES})
    result = run(root, checkout=repo / "sub")
    check("a subdirectory of a checkout is refused, exit 2, naming the top directory",
          result.returncode == 2
          and f"Pass --checkout {repo.resolve()}" in result.stderr and ran(root) == [],
          (result.returncode, result.stderr))
with tempfile.TemporaryDirectory() as scratch:
    root = pathlib.Path(scratch)
    (root / "not-a-checkout").mkdir()
    result = run(root, checkout=root / "not-a-checkout")
    check("a directory outside any git checkout is refused, exit 2",
          result.returncode == 2 and "not inside a git checkout" in result.stderr,
          (result.returncode, result.stderr))
with tempfile.TemporaryDirectory() as scratch:
    root = pathlib.Path(scratch)
    make_repo(root, {})
    result = run(root)
    check("a checkout where git lists no *-test.py is refused, exit 2, not a green run",
          result.returncode == 2 and "lists no *-test.py" in result.stderr
          and "SUMMARY" not in result.stdout, (result.returncode, result.stdout, result.stderr))
with tempfile.TemporaryDirectory() as scratch:
    root = pathlib.Path(scratch)
    make_repo(root, {"a-test.py": PASSES})
    result = run(root, "-j", "0")
    check("-j 0 is refused, exit 2", result.returncode == 2 and ran(root) == [],
          (result.returncode, result.stderr))

# --- The environment each suite is launched with: no git redirection ---------
# nedschorus#639. The program's OWN process is given an ambient GIT_DIR
# pointing at a throwaway victim repository — the one variable measured to
# reach every one of the 21 suites that build a scratch repository, and the
# one that did the 2026-09-22 damage. A suite the program launches must not
# see it, must get a real repository of its own, and must leave the victim
# alone.
#
# Against the program without this change, this case fails with the suite
# reporting GIT_DIR among the variables it saw, no repository at its own
# scratch path, and the victim carrying the suite's commit and identity.
SUITE_THAT_BUILDS_A_REPOSITORY = "builds-a-repository-test.py"
with tempfile.TemporaryDirectory() as scratch:
    root = pathlib.Path(scratch)
    make_repo(root, {SUITE_THAT_BUILDS_A_REPOSITORY: BUILDS_A_SCRATCH_REPOSITORY})
    victim = make_victim_repository(root, SUITE_THAT_BUILDS_A_REPOSITORY)
    before = victim_state(victim)
    result = run(root, environment_extra={"GIT_DIR": str(victim / ".git")})
    saw_file = root / "what-the-suite-saw.json"
    saw = json.loads(saw_file.read_text()) if saw_file.exists() else {}
    check("a suite launched by the program sees no ambient GIT_DIR the program has",
          "GIT_DIR" not in saw.get("git_variables_seen", ["GIT_DIR"]),
          (saw.get("git_variables_seen"), result.stdout, result.stderr))
    check("so a suite that builds a scratch repository really gets one",
          saw.get("repository_built_at_its_own_scratch") is True, saw)
    check("and the repository the ambient GIT_DIR named is untouched",
          victim_state(victim) == before, (before, victim_state(victim)))
    check("the victim keeps the committing identity its own config pins",
          victim_state(victim)["identity"] == VICTIM_IDENTITY, victim_state(victim))
    check("a variable that is not git's is passed through to the suite unchanged",
          saw.get("a_variable_that_is_not_git_s") == "20", saw)
    check("a suite that gives its own child GIT_DIR still does — the cold-read fixture",
          saw.get("git_dir_the_child_was_given")
          == str(root / "the-child-s-own-git-directory"), saw)
    check("the suite still exits 0, so none of the above is read off a failure",
          result.returncode == 0, (result.returncode, result.stdout, result.stderr))

# --- The program's own git calls: no git redirection either ------------------
# nedschorus#639, the program's half. The program's OWN process is given an
# ambient GIT_DIR naming a victim repository that tracks a suite the checkout
# does not. The program's own `rev-parse`, `ls-files` and `status` must still
# read the checkout it was given: the suites listed and run are the
# checkout's, and so is the commit its first line names.
#
# Against the program without this change, this case fails with the victim's
# suite listed and FAIL (it is not on disk in the checkout), the checkout's
# own suite never run, and the first line naming the victim's commit.
SUITE_ONLY_THE_CHECKOUT_TRACKS = "the-checkout-s-own-test.py"
SUITE_ONLY_THE_VICTIM_TRACKS = "the-victim-s-own-test.py"
with tempfile.TemporaryDirectory() as scratch:
    root = pathlib.Path(scratch)
    repo = make_repo(root, {SUITE_ONLY_THE_CHECKOUT_TRACKS: PASSES})
    victim = make_victim_repository(root, SUITE_ONLY_THE_VICTIM_TRACKS)
    checkout_commit = git(repo, "rev-parse", "HEAD").stdout.strip()
    result = run(root, environment_extra={"GIT_DIR": str(victim / ".git")})
    out = lines(result.stdout)
    check("with an ambient GIT_DIR, the suites the program lists and runs are the checkout's",
          ran(root) == [SUITE_ONLY_THE_CHECKOUT_TRACKS]
          and not any(SUITE_ONLY_THE_VICTIM_TRACKS in line for line in out),
          (ran(root), result.stdout, result.stderr))
    check("with an ambient GIT_DIR, the first line names the checkout's own commit",
          bool(out) and out[0].startswith(
              f"run-all-test-suites: {repo.resolve()} at {checkout_commit} "
              f"(tracked files match that commit); 1 suites listed by git;"),
          (checkout_commit, out[:1]))
    check("with an ambient GIT_DIR, a checkout whose suites all pass exits 0",
          result.returncode == 0, (result.returncode, result.stdout, result.stderr))

# --- Which variables are stripped, and which are deliberately kept -----------
# The five beyond GIT_DIR are pinned here at the seam they act on rather than
# each driven through a whole run: the program's own git calls and every
# suite it launches take their environment from this one function.
# GIT_NAMESPACE and GIT_CEILING_DIRECTORIES are checked as KEPT, because
# deciding against them was a measured decision and widening the list later
# should trip a case.
module = load_program_module()
every_variable = {
    "GIT_DIR": "/elsewhere/.git", "GIT_WORK_TREE": "/elsewhere",
    "GIT_INDEX_FILE": "/elsewhere/.git/index",
    "GIT_OBJECT_DIRECTORY": "/elsewhere/.git/objects",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES": "/elsewhere/.git/objects",
    "GIT_COMMON_DIR": "/elsewhere/.git",
    "GIT_NAMESPACE": "a-namespace", "GIT_CEILING_DIRECTORIES": "/elsewhere",
    "A_VARIABLE_THAT_IS_NOT_GIT_S": "kept",
}
was = dict(os.environ)
try:
    os.environ.update(every_variable)
    stripped_environment = module.environment_without_git_redirecting_variables()
finally:
    os.environ.clear()
    os.environ.update(was)
check("every variable measured to redirect where git reads and writes is stripped",
      [name for name in every_variable if name in stripped_environment]
      == ["GIT_NAMESPACE", "GIT_CEILING_DIRECTORIES", "A_VARIABLE_THAT_IS_NOT_GIT_S"],
      [name for name in every_variable if name in stripped_environment])
check("GIT_NAMESPACE is kept: measured contained inside one repository",
      stripped_environment.get("GIT_NAMESPACE") == "a-namespace")
check("GIT_CEILING_DIRECTORIES is kept: stripping it would widen where git looks",
      stripped_environment.get("GIT_CEILING_DIRECTORIES") == "/elsewhere")
check("the rest of the environment is passed through, not rebuilt",
      stripped_environment.get("A_VARIABLE_THAT_IS_NOT_GIT_S") == "kept"
      and stripped_environment.get("PATH") == os.environ.get("PATH"))

# --- Recorded inputs: a suite reruns only when a file it read differs --------
# Walk open-questions-concerns-and-recommendations-2026-09-30, item 5. Each
# suite reads something different, by a different route: a file it opens, a
# file a Python child it starts opens, a program it loads by path the way 57
# suites on main load theirs, a directory it lists, and the checkout's file
# list through git. Two full runs record them (the second finds the loaded
# program's bytecode already cached, so it never opens the source); then one
# file changes at a time, and only the suite that read it may run.
#
# Against the program without this change, every case below fails: it has no
# --only-suites-whose-recorded-inputs-changed-since, so each selective run is
# refused with exit 2 and nothing runs.
CHANGED_SINCE = "--only-suites-whose-recorded-inputs-changed-since"
RECORDING_SUITES = {
    "reads-a-file-test.py": "pathlib.Path('inputs/read-directly.txt').read_text()\n",
    "child-reads-a-file-test.py": (
        "import subprocess\n"
        "subprocess.run([sys.executable, '-c', "
        "\"open('inputs/read-by-a-child.txt').read()\"], check=True)\n"),
    "loads-a-program-by-path-test.py": (
        "import importlib.util\n"
        "spec = importlib.util.spec_from_file_location("
        "'loaded_by_path', 'programs/loaded-by-path.py')\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(module)\n"
        "sys.exit(0 if module.VALUE else 1)\n"),
    "lists-a-directory-test.py": "print(sorted(os.listdir('skills')))\n",
    "lists-files-through-git-test.py": (
        "import subprocess\n"
        "subprocess.run(['git', 'ls-files'], check=True, capture_output=True)\n"),
    # git run from the checkout on a repository of the suite's own reads
    # nothing of the checkout's, so a change to the checkout never selects it.
    # An option's value before the directory (`-b main`, `--origin upstream`)
    # is not the directory: read as one, it resolves inside the checkout.
    "runs-git-on-its-own-repository-test.py": (
        "import subprocess, tempfile\n"
        "with tempfile.TemporaryDirectory() as own:\n"
        "    subprocess.run(['git', 'init', '-q', own + '/origin'], check=True)\n"
        "    subprocess.run(['git', 'clone', '-q', own + '/origin', own + '/copy'],\n"
        "                   check=True, capture_output=True)\n"
        "    subprocess.run(['git', 'init', '-q', '--bare', '-b', 'main', own + '/bare'],\n"
        "                   check=True)\n"
        "    subprocess.run(['git', 'clone', '-q', '--origin', 'upstream', own + '/origin',\n"
        "                    own + '/named-copy'], check=True, capture_output=True)\n"),
    "reads-nothing-else-test.py": PASSES,
    "reads-a-file-only-when-asked-test.py": (
        f"if (pathlib.Path(os.environ['{RAN_FILE_VARIABLE}']).parent / 'ask.txt').exists():\n"
        "    pathlib.Path('inputs/read-when-asked.txt').read_text()\n"),
}
RECORDING_INPUTS = {
    ".gitignore": "__pycache__/\n",
    "inputs/read-directly.txt": "first\n",
    "inputs/read-by-a-child.txt": "first\n",
    "programs/loaded-by-path.py": "VALUE = 1\n",
    "skills/one.md": "one\n",
    "inputs/read-when-asked.txt": "first\n",
    "unread.txt": "nobody reads this\n",
}


def commit_files(repo, files, message):
    for relative, body in files.items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def selective_run(root, since):
    (root / "ran.txt").unlink(missing_ok=True)
    return run(root, CHANGED_SINCE, since)


def recording(root, suite):
    found = list((root / "recordings").glob(f"*/{suite.replace('/', '__')}.json"))
    return json.loads(found[0].read_text()) if found else {}


with tempfile.TemporaryDirectory() as scratch:
    root = pathlib.Path(scratch)
    repo = make_repo(root, RECORDING_SUITES)
    base = commit_files(repo, RECORDING_INPUTS, "inputs")
    (root / "ask.txt").write_text("read it\n")
    first = run(root)
    asked = recording(root, "reads-a-file-only-when-asked-test.py")
    (root / "ask.txt").unlink()
    second = run(root)
    check("two full runs of the recording fixture pass",
          first.returncode == 0 and second.returncode == 0,
          (first.stdout, second.stdout, first.stderr))
    check("a full run says how inputs are recorded and where they are kept",
          len(lines(second.stdout)) > 1
          and lines(second.stdout)[1].startswith("inputs recorded by python-audit-hook")
          and str(root / "recordings") in lines(second.stdout)[1], lines(second.stdout)[:2])
    check("a file a suite opens is recorded, with its blob hash",
          "inputs/read-directly.txt" in recording(root, "reads-a-file-test.py").get("reads", {}),
          recording(root, "reads-a-file-test.py"))
    check("a file a Python child process of the suite opens is recorded",
          "inputs/read-by-a-child.txt"
          in recording(root, "child-reads-a-file-test.py").get("reads", {}),
          recording(root, "child-reads-a-file-test.py"))
    check("a program loaded by path is recorded as its source, though its bytecode was cached",
          "programs/loaded-by-path.py"
          in recording(root, "loads-a-program-by-path-test.py").get("reads", {}),
          recording(root, "loads-a-program-by-path-test.py"))
    check("a directory the suite lists is recorded, and the import system's listings are not",
          recording(root, "lists-a-directory-test.py").get("lists") == {"skills": ["one.md"]},
          recording(root, "lists-a-directory-test.py"))
    check("a git command run on the checkout is recorded",
          recording(root, "lists-files-through-git-test.py").get(
              "git_commands_on_the_checkout") == ["ls-files"],
          recording(root, "lists-files-through-git-test.py"))
    check("git init and git clone of a repository outside the checkout, run from the "
          "checkout, are not recorded as git on the checkout, with option values or without",
          recording(root, "runs-git-on-its-own-repository-test.py").get(
              "git_commands_on_the_checkout") == []
          and recording(root, "runs-git-on-its-own-repository-test.py").get(
              "git_calls_run_from_the_checkout") == [],
          recording(root, "runs-git-on-its-own-repository-test.py"))
    check("a run records what its suite read in that run, not what an earlier run into "
          "the same log directory read",
          "inputs/read-when-asked.txt" in asked.get("reads", {})
          and "inputs/read-when-asked.txt" not in recording(
              root, "reads-a-file-only-when-asked-test.py").get("reads", {}),
          (asked, recording(root, "reads-a-file-only-when-asked-test.py")))
    check("a file no suite reads is in no recording",
          not any("unread.txt" in recording(root, suite).get("reads", {})
                  for suite in RECORDING_SUITES))

    result = selective_run(root, base)
    out = lines(result.stdout)
    check("with nothing changed since the commit, no suite runs, and the run exits 0",
          result.returncode == 0 and ran(root) == [], (ran(root), result.stdout))
    check("an unchanged suite is NOT SELECTED, saying none of the files it read differs",
          any(line.startswith("NOT SELECTED reads-nothing-else-test.py: none of the 1 files "
                              f"it read differs since {base[:12]}") for line in out), out)
    check("the SUMMARY counts the suites not selected",
          bool(out) and out[-1].endswith(f"; 8 suites not selected, their recorded inputs "
                                         f"unchanged since {base[:12]}"), out[-1:])

    commit_files(repo, {"inputs/read-directly.txt": "second\n"}, "change a file one suite reads")
    result = selective_run(root, base)
    out = lines(result.stdout)
    check("a changed file a suite read selects that suite, and only that suite",
          ran(root) == ["reads-a-file-test.py"], (ran(root), result.stdout, result.stderr))
    check("the SELECTED line names the file that differs",
          "SELECTED reads-a-file-test.py: it reads inputs/read-directly.txt, which differs"
          in out, out)
    base = git(repo, "rev-parse", "HEAD").stdout.strip()

    commit_files(repo, {"inputs/read-by-a-child.txt": "second\n"}, "change a child's input")
    result = selective_run(root, base)
    check("a changed file a child process read selects the suite that started the child",
          ran(root) == ["child-reads-a-file-test.py"], (ran(root), result.stdout))
    base = git(repo, "rev-parse", "HEAD").stdout.strip()

    commit_files(repo, {"programs/loaded-by-path.py": "VALUE = 2\n"}, "change the program")
    result = selective_run(root, base)
    check("a changed program loaded by path selects the suite that loads it",
          ran(root) == ["loads-a-program-by-path-test.py"], (ran(root), result.stdout))
    base = git(repo, "rev-parse", "HEAD").stdout.strip()

    commit_files(repo, {"skills/two.md": "two\n"}, "add a file to a listed directory")
    result = selective_run(root, base)
    out = lines(result.stdout)
    check("a file added to a directory a suite lists selects that suite, and so does "
          "one running git ls-files on the checkout",
          ran(root) == ["lists-a-directory-test.py", "lists-files-through-git-test.py"],
          (ran(root), result.stdout))
    check("the SELECTED line names the directory and the added file",
          "SELECTED lists-a-directory-test.py: it lists skills/, where skills/two.md was added"
          in out, out)
    base = git(repo, "rev-parse", "HEAD").stdout.strip()

    for recording_file in (root / "recordings").glob("*/reads-nothing-else-test.py.json"):
        recording_file.unlink()
    result = selective_run(root, base)
    check("a suite with no recording on this machine runs, saying so",
          ran(root) == ["reads-nothing-else-test.py"]
          and "SELECTED reads-nothing-else-test.py: no recording of its inputs on this "
              "machine yet" in lines(result.stdout), (ran(root), result.stdout))

    for changed in ("scripts/run-all-test-suites.py", ".claude/hooks/a-hook.py",
                    ".claude/settings.json"):
        base = git(repo, "rev-parse", "HEAD").stdout.strip()
        commit_files(repo, {changed: f"# {changed}\n"}, f"change {changed}")
        result = selective_run(root, base)
        check(f"a change to {changed} runs every suite, saying why",
              ran(root) == sorted(RECORDING_SUITES)
              and f"SELECTED reads-nothing-else-test.py: {changed} differs, and every suite "
                  f"runs under it" in lines(result.stdout), (ran(root), result.stdout))

    result = run(root, CHANGED_SINCE, "no-such-commit")
    check("a commit git cannot resolve is refused, exit 2, before anything runs",
          result.returncode == 2 and CHANGED_SINCE in result.stderr, (result.returncode,
                                                                      result.stderr))

# --- Selection never trusts a recording it cannot show is complete and of ----
# --- these files -------------------------------------------------------------
# merge-lane-2's review of round 1 (review 5373089211 on pull request
# "The test runner selects suites by their recorded inputs") and mac-claude's
# (review 5373031797): in each case below, a suite that reads a changed file
# was NOT SELECTED, and run directly it failed. Every case here fails against
# the runner at c43bad62, except the `git show` case, which fails there only
# where strace records (ned-box, run directly).


def path_without_strace(root):
    """A PATH holding git and nothing else, so the audit hook records alone,
    as on the Mac and inside a full run on ned-box."""
    bin_dir = root / "bin-without-strace"
    bin_dir.mkdir(exist_ok=True)
    if not (bin_dir / "git").exists():
        (bin_dir / "git").symlink_to(shutil.which("git"))
    return {"PATH": str(bin_dir)}


def select_since(root, since, environment_extra=None):
    (root / "ran.txt").unlink(missing_ok=True)
    return run(root, CHANGED_SINCE, since, environment_extra=environment_extra)


def head(repo):
    return git(repo, "rev-parse", "HEAD").stdout.strip()


# A recording made on another branch. The store is shared by every worktree
# and clone on a machine, so the recording selection reads may have been
# made where the suite read less than it reads here.
with tempfile.TemporaryDirectory() as scratch:
    root = pathlib.Path(scratch)
    repo = make_repo(root, {"reads-two-files-test.py": (
        "for name in ('p.txt', 'q.txt'):\n"
        "    assert pathlib.Path(name).read_text() == 'ok\\n', name\n")})
    reads_both = commit_files(repo, {"p.txt": "ok\n", "q.txt": "ok\n"}, "inputs")
    git(repo, "checkout", "-q", "-b", "reads-less")
    commit_files(repo, {"reads-two-files-test.py": SUITE_PREAMBLE + (
        "assert pathlib.Path('p.txt').read_text() == 'ok\\n'\n")}, "reads only p.txt")
    run(root)
    git(repo, "checkout", "-q", reads_both)
    (repo / "q.txt").write_text("broken\n")
    result = select_since(root, reads_both)
    check("a recording made on another branch, where the suite read fewer files, does not "
          "keep the suite from running",
          ran(root) == ["reads-two-files-test.py"] and result.returncode == 1,
          (ran(root), result.stdout))
    check("the SELECTED line says the recording read another copy of a file",
          "SELECTED reads-two-files-test.py: its recording read another copy of "
          "reads-two-files-test.py than the checkout holds, so what it reads here is unknown"
          in lines(result.stdout), result.stdout)

with tempfile.TemporaryDirectory() as scratch:
    root = pathlib.Path(scratch)
    repo = make_repo(root, {"reads-every-note-test.py": (
        "for name in sorted(os.listdir('notes')):\n"
        "    assert (pathlib.Path('notes') / name).read_text() == 'ok\\n', name\n")})
    commit_files(repo, {"notes/a.txt": "ok\n"}, "one note")
    run(root)
    two_notes = commit_files(repo, {"notes/b.txt": "ok\n"}, "a second note")
    (repo / "notes/b.txt").write_text("broken\n")
    result = select_since(root, two_notes)
    check("a recording that listed a directory holding other entries than the checkout's "
          "does not keep the suite from running",
          ran(root) == ["reads-every-note-test.py"] and result.returncode == 1,
          (ran(root), result.stdout))

with tempfile.TemporaryDirectory() as scratch:
    root = pathlib.Path(scratch)
    repo = make_repo(root, {"reads-what-git-lists-test.py": (
        "import subprocess\n"
        "listed = subprocess.run(['git', 'ls-files', 'data'], capture_output=True, text=True,\n"
        "                        check=True).stdout.split()\n"
        "for name in listed:\n"
        "    assert pathlib.Path(name).read_text() == 'ok\\n', name\n")})
    commit_files(repo, {"data/a.txt": "ok\n"}, "one data file")
    run(root)
    two_files = commit_files(repo, {"data/b.txt": "ok\n"}, "a second data file")
    (repo / "data/b.txt").write_text("broken\n")
    result = select_since(root, two_files)
    check("a suite running git on the checkout, recorded on another set of files, runs",
          ran(root) == ["reads-what-git-lists-test.py"] and result.returncode == 1,
          (ran(root), result.stdout))

with tempfile.TemporaryDirectory() as scratch:
    root = pathlib.Path(scratch)
    repo = make_repo(root, {"reads-p-unless-optional-test.py": (
        "if not pathlib.Path('optional.txt').exists():\n"
        "    assert pathlib.Path('p.txt').read_text() == 'ok\\n'\n")})
    without_optional = commit_files(repo, {"p.txt": "ok\n"}, "p.txt")
    git(repo, "checkout", "-q", "-b", "has-optional")
    commit_files(repo, {"optional.txt": "here\n"}, "optional.txt")
    run(root)
    git(repo, "checkout", "-q", without_optional)
    (repo / "p.txt").write_text("broken\n")
    result = select_since(root, without_optional)
    check("a recording that found a path the checkout does not have does not keep the "
          "suite from running",
          ran(root) == ["reads-p-unless-optional-test.py"] and result.returncode == 1,
          (ran(root), result.stdout))

# A run that did not finish. The suite reads p.txt, and q.txt only if it is
# not killed first.
with tempfile.TemporaryDirectory() as scratch:
    root = pathlib.Path(scratch)
    repo = make_repo(root, {"killed-partway-test.py": (
        "pathlib.Path('p.txt').read_text()\n"
        f"if (pathlib.Path(os.environ['{RAN_FILE_VARIABLE}']).parent / 'die.txt').exists():\n"
        "    os.kill(os.getpid(), signal.SIGTERM)\n"
        "    time.sleep(5)\n"
        "assert pathlib.Path('q.txt').read_text() == 'ok\\n'\n")})
    base = commit_files(repo, {"p.txt": "ok\n", "q.txt": "ok\n"}, "inputs")
    run(root)
    (root / "die.txt").write_text("die\n")
    killed = run(root)
    (root / "die.txt").unlink()
    commit_files(repo, {"q.txt": "broken\n"}, "change q.txt")
    result = select_since(root, base)
    check("a suite whose last run was killed partway runs, though its killed run never "
          "read the changed file",
          "FAIL killed-partway-test.py killed by SIGTERM" in killed.stdout
          and ran(root) == ["killed-partway-test.py"] and result.returncode == 1,
          (killed.stdout, ran(root), result.stdout))
    check("the SELECTED line says the last recorded run did not pass",
          "SELECTED killed-partway-test.py: its last recorded run did not pass: killed by "
          "SIGTERM" in lines(result.stdout), result.stdout)

with tempfile.TemporaryDirectory() as scratch:
    root = pathlib.Path(scratch)
    repo = make_repo(root, {"fails-test.py": "sys.exit(1)\n", "passes-test.py": PASSES})
    base = head(repo)
    run(root)
    result = select_since(root, base)
    check("a suite whose recorded run failed runs again with nothing changed, and the run "
          "exits 1",
          ran(root) == ["fails-test.py"] and result.returncode == 1
          and "SELECTED fails-test.py: its last recorded run did not pass: exit 1"
          in lines(result.stdout), (ran(root), result.stdout))

# A new directory under a listed one: the shape of a new system directory
# under nc-systems/, which a glob of `nc-systems/*/*.py` reads.
with tempfile.TemporaryDirectory() as scratch:
    root = pathlib.Path(scratch)
    repo = make_repo(root, {"globs-systems-test.py": (
        "import glob\n"
        "for name in glob.glob('systems/*/*.py'):\n"
        "    assert 'DUPLICATE' not in pathlib.Path(name).read_text(), name\n")})
    base = commit_files(repo, {"systems/one/one.py": "VALUE = 1\n"}, "one system")
    run(root)
    (repo / "systems/two").mkdir()
    (repo / "systems/two/two.py").write_text("DUPLICATE = 1\n")
    result = select_since(root, base)
    check("a file added in a new directory under a listed directory selects the suite",
          ran(root) == ["globs-systems-test.py"] and result.returncode == 1
          and "SELECTED globs-systems-test.py: it lists systems/, where systems/two was added"
          in lines(result.stdout), (ran(root), result.stdout))

# A path that was not there when the suite ran.
with tempfile.TemporaryDirectory() as scratch:
    root = pathlib.Path(scratch)
    repo = make_repo(root, {
        "checks-a-path-exists-test.py":
            "sys.exit(1 if pathlib.Path('optional.txt').exists() else 0)\n",
        "opens-a-path-that-may-be-absent-test.py": (
            "try:\n"
            "    open('extra/optional.txt').read()\n"
            "    sys.exit(1)\n"
            "except FileNotFoundError:\n"
            "    pass\n"),
        "reads-nothing-else-test.py": PASSES})
    base = head(repo)
    run(root)
    commit_files(repo, {"optional.txt": "here\n", "extra/optional.txt": "here\n"},
                 "add the optional paths")
    result = select_since(root, base)
    check("a path a suite checked for, or failed to open, selects the suite when it is added",
          ran(root) == ["checks-a-path-exists-test.py",
                        "opens-a-path-that-may-be-absent-test.py"]
          and result.returncode == 1, (ran(root), result.stdout))
    check("the SELECTED line names the path it looked for",
          "SELECTED checks-a-path-exists-test.py: it looks for optional.txt, which was added"
          in lines(result.stdout), result.stdout)

# git status reads a working file whose timestamps changed. With the audit
# hook alone, no recorder sees it.
with tempfile.TemporaryDirectory() as scratch:
    root = pathlib.Path(scratch)
    repo = make_repo(root, {"runs-git-status-test.py": (
        "import subprocess\n"
        "assert subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'],\n"
        "                      capture_output=True, text=True, check=True).stdout == ''\n")})
    base = commit_files(repo, {"data.txt": "a\n"}, "data")
    hook_only = path_without_strace(root)
    run(root, environment_extra=hook_only)
    (repo / "data.txt").write_text("b\n")
    result = select_since(root, base, environment_extra=hook_only)
    check("a suite running git status on the checkout runs when a file differs, with the "
          "audit hook recording alone",
          ran(root) == ["runs-git-status-test.py"] and result.returncode == 1,
          (ran(root), result.stdout))

# git show reads a file's content from the object store, where strace sees
# no working file opened.
with tempfile.TemporaryDirectory() as scratch:
    root = pathlib.Path(scratch)
    repo = make_repo(root, {"runs-git-show-test.py": (
        "import subprocess\n"
        "assert subprocess.run(['git', 'show', 'HEAD:data.txt'], capture_output=True,\n"
        "                      text=True, check=True).stdout == 'a\\n'\n")})
    base = commit_files(repo, {"data.txt": "a\n"}, "data")
    run(root)
    commit_files(repo, {"data.txt": "b\n"}, "change data")
    result = select_since(root, base)
    check("a suite running git show on the checkout runs when a file differs, whichever "
          "recorders recorded it",
          ran(root) == ["runs-git-show-test.py"] and result.returncode == 1,
          (ran(root), result.stdout))

# A recording that could not be saved.
with tempfile.TemporaryDirectory() as scratch:
    root = pathlib.Path(scratch)
    repo = make_repo(root, {"a-test.py": PASSES})
    base = head(repo)
    run(root)
    stored = next((root / "recordings").glob("*/a-test.py.json"))
    stored.with_suffix(".json.tmp").mkdir()
    result = run(root)
    check("when a recording cannot be saved, the report says the earlier one is removed",
          any(line.startswith("inputs of a-test.py not recorded: ")
              and "Its earlier recording is removed" in line
              for line in lines(result.stdout)) and not stored.exists(),
          (result.stdout, stored.exists()))
    result = select_since(root, base)
    check("so the next selective run selects the suite",
          ran(root) == ["a-test.py"], (ran(root), result.stdout))

# A run killed by SIGKILL leaves its suites' strace directories behind.
with tempfile.TemporaryDirectory() as scratch:
    root = pathlib.Path(scratch)
    make_repo(root, {"a-test.py": PASSES})
    killed_logs = root / "logs-of-a-killed-run"
    left = killed_logs / "recorded-inputs" / "a-test.py.strace"
    left.mkdir(parents=True)
    (left / "trace.4242").write_text("a trace nobody removed\n")
    hook_log = killed_logs / "recorded-inputs" / "a-test.py.hook"
    hook_log.write_text("read\t/elsewhere\n")
    (root / "run.lock").write_text(f"pid 4242, checkout {root / 'repo'}, started "
                                   f"2026-09-30T00:00:00Z, logs in {killed_logs}\n")
    result = run(root)
    check("a run removes the strace directories the lock's last holder left behind",
          result.returncode == 0 and not left.exists(), (result.stdout, left.exists()))
    check("and nothing else in that holder's log directory", hook_log.exists())
    holder = (root / "run.lock").read_text()
    check("the lock names its holder's log directory, on one line",
          holder.endswith(f", logs in {(root / 'logs').resolve()}\n")
          and holder.count("\n") == 1 and holder.startswith("pid "), holder)

# --- Git calls that read no file of the checkout -----------------------------
# Full arguments distinguish location and config reads from calls whose
# answers depend on files or objects, and another repository from this one.
for arguments in (
        *(["rev-parse", option] for option in (
            "--show-toplevel", "--git-dir", "--absolute-git-dir", "--git-common-dir",
            "--is-inside-work-tree", "--show-prefix")),
        ["rev-parse", "--show-toplevel", "--git-dir"],
        ["-C", "sub", "rev-parse", "--show-toplevel"],
        ["config", "user.email"], ["config", "--get", "user.name"],
        ["config", "--get-all", "user.name"], ["config", "user.useConfigOnly"]):
    call = {"arguments": arguments, "directory": "/checkout-top",
            "GIT_DIR": None, "GIT_WORK_TREE": None}
    answer = module.what_a_git_call_run_from_the_checkout_reads(
        call, "/checkout-top", "/checkout-top/.git")
    check(f"git {' '.join(arguments)} sees no file",
          answer == module.GIT_CALL_SEES_NO_FILE, answer)

for arguments in (
        ["rev-parse", "--short", "HEAD"], ["rev-parse", "HEAD"],
        ["rev-parse", "--verify", "--quiet", "08ddce3^{commit}"],
        ["rev-parse", "--show-toplevel", "HEAD"], ["rev-parse"],
        ["config", "user.name", "value"], ["config", "--unset", "user.name"],
        ["config", "--local", "--get", "user.name"],
        ["config", "--get", "user.name", "a-value-pattern"],
        ["-c", "core.hooksPath=/dev/null", "rev-parse", "--show-toplevel"],
        ["ls-files", "-z"], ["status", "--porcelain"],
        ["--no-pager", "rev-parse", "--show-toplevel"],
        ["config", "--global", "--get", "user.name"],
        ["config", "--file", "config.txt", "user.name"],
        ["config", "get", "user.name"], ["config", "user.name=value"],
        ["config", "user.name value"], ["config", "name"],
        ["--git-dir"], []):
    call = {"arguments": arguments, "directory": "/checkout-top",
            "GIT_DIR": None, "GIT_WORK_TREE": None}
    answer = module.what_a_git_call_run_from_the_checkout_reads(
        call, "/checkout-top", "/checkout-top/.git")
    check(f"git {' '.join(arguments)} stays git on the checkout",
          answer == module.GIT_CALL_READS_THE_CHECKOUT, answer)

for arguments, git_directory, work_tree in (
        (["--git-dir", "/tmp/elsewhere/origin.git", "rev-parse", "--verify", "--quiet",
          "refs/heads/clean"], None, None),
        (["--git-dir=/tmp/elsewhere/.git", "log", "--oneline"], None, None),
        (["--git-dir", "/tmp/elsewhere/.git", "worktree", "list", "--porcelain"], None, None),
        (["cat-file", "-t", "HEAD"], "/tmp/elsewhere/.git", None),
        (["--git-dir", "/tmp/elsewhere/.git", "for-each-ref"], None, None),
        (["--git-dir", "/tmp/elsewhere/.git", "show", "HEAD"], None, None),
        (["--git-dir", "/tmp/elsewhere/.git", "config", "user.name"], None, None),
        (["--git-dir", "/tmp/elsewhere/.git", "--work-tree", "/tmp/elsewhere",
          "status"], None, None),
        (["add", "-A"], "/tmp/elsewhere/.git", "/tmp/elsewhere"),
        (["--git-dir", "../elsewhere.git", "log"], None, None),
        (["-C", "sub", "-C", "../..", "--git-dir", "elsewhere.git", "log"], None, None),
        (["--git-dir", "/checkout-top/.git", "--git-dir", "/tmp/elsewhere/.git", "log"],
         "/checkout-top/.git", None),
        (["--git-dir", "/tmp/elsewhere/.git", "--work-tree=/tmp/elsewhere", "status"],
         None, "/checkout-top"),
        (["--git-dir", "/tmp/elsewhere/.git", "--work-tree", "/checkout-top", "log"],
         None, None)):
    call = {"arguments": arguments, "directory": "/checkout-top",
            "GIT_DIR": git_directory, "GIT_WORK_TREE": work_tree}
    answer = module.what_a_git_call_run_from_the_checkout_reads(
        call, "/checkout-top", "/checkout-top/.git")
    check(f"git {' '.join(arguments)} with environment {git_directory}, {work_tree} "
          "runs on another repository", answer == module.GIT_CALL_RUNS_ON_ANOTHER_REPOSITORY,
          answer)

for arguments in (
        *(["--git-dir", "/tmp/elsewhere/.git", *command] for command in (
            ["status"], ["diff"], ["add", "-A"], ["checkout", "main"], ["ls-files"],
            ["stash"], ["worktree", "add", "x"])),
        ["--git-dir", "/tmp/elsewhere/.git", "--work-tree", "/checkout-top", "status"],
        ["--git-dir", "/checkout-top/.git", "log"],
        ["--git-dir", "/tmp/elsewhere/.git", "-c", "a.b=c", "log"],
        ["--git-dir", "/tmp/elsewhere/.git", "--namespace", "elsewhere", "log"],
        ["--git-dir", "/tmp/elsewhere/.git", "--config-env", "a.b=VALUE", "log"],
        ["--git-dir", "/tmp/elsewhere/.git", "--no-pager", "log"],
        ["--git-dir", "/tmp/elsewhere/.git", "--git-dir", "/checkout-top/.git", "log"],
        ["--git-dir", "/tmp/elsewhere/.git", "--work-tree", "/tmp/elsewhere",
         "--work-tree", "/checkout-top", "status"]):
    call = {"arguments": arguments, "directory": "/checkout-top",
            "GIT_DIR": None, "GIT_WORK_TREE": None}
    answer = module.what_a_git_call_run_from_the_checkout_reads(
        call, "/checkout-top", "/checkout-top/.git")
    check(f"git {' '.join(arguments)} still reads the checkout",
          answer == module.GIT_CALL_READS_THE_CHECKOUT, answer)

for git_directory in ("/main-clone/.git/worktrees/wt", "/main-clone/.git"):
    call = {"arguments": ["--git-dir", git_directory, "log"], "directory": "/checkout-top",
            "GIT_DIR": None, "GIT_WORK_TREE": None}
    answer = module.what_a_git_call_run_from_the_checkout_reads(
        call, "/checkout-top", "/main-clone/.git")
    check(f"git naming {git_directory} reads the linked worktree's own repository",
          answer == module.GIT_CALL_READS_THE_CHECKOUT, answer)

for call in (None, {"arguments": None}, {}, {"arguments": [b"log"]}):
    answer = module.what_a_git_call_run_from_the_checkout_reads(
        call, "/checkout-top", "/checkout-top/.git")
    check(f"an unrecognised git call {call!r} reads the checkout",
          answer == module.GIT_CALL_READS_THE_CHECKOUT, answer)

with tempfile.TemporaryDirectory() as scratch:
    root = pathlib.Path(scratch)
    # Scratch setup runs with -C outside the checkout, so only the calls
    # made from the checkout are recorded.
    scratch_setup = '''import subprocess, tempfile, shutil
scratch = tempfile.mkdtemp()
subprocess.run(['git', '-C', scratch, 'init', '-q'], check=True, capture_output=True)
pathlib.Path(scratch, 'one.txt').write_text('one\\n')
subprocess.run(['git', '-C', scratch, 'add', 'one.txt'], check=True, capture_output=True)
subprocess.run(['git', '-C', scratch, '-c', 'user.name=x', '-c', 'user.email=x@invalid',
                '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null',
                'commit', '-q', '-m', 'one'], check=True, capture_output=True)
'''
    positive_suites = {
        "git-sees-no-file-test.py": '''import subprocess
subprocess.run(['git', 'rev-parse', '--show-toplevel'], check=True, capture_output=True)
subprocess.run(['git', 'rev-parse', '--show-toplevel'], cwd='sub',
               check=True, capture_output=True)
subprocess.run(['git', '-C', 'sub', 'rev-parse', '--git-dir'], check=True, capture_output=True)
subprocess.run(['git', 'config', 'user.email'], capture_output=True)
subprocess.run(['git', 'config', '--get', 'user.name'], capture_output=True)
''',
        "git-on-another-repository-test.py": scratch_setup + '''try:
    subprocess.run(['git', '--git-dir', scratch + '/.git', 'rev-parse', '--verify',
                    '--quiet', 'HEAD'], check=True, capture_output=True)
    subprocess.run(['git', '--git-dir=' + scratch + '/.git', 'log', '--oneline'],
                   check=True, capture_output=True)
    subprocess.run(['git', '--git-dir', scratch + '/.git', 'worktree', 'list', '--porcelain'],
                   check=True, capture_output=True)
    subprocess.run(['git', 'cat-file', '-t', 'HEAD'],
                   env=dict(os.environ, GIT_DIR=scratch + '/.git'),
                   check=True, capture_output=True)
    subprocess.run(['git', '--git-dir', scratch + '/.git', '--work-tree', scratch,
                    'status', '--porcelain'], check=True, capture_output=True)
finally:
    shutil.rmtree(scratch)
'''}
    negative_suites = {
        "git-status-with-git-dir-test.py": scratch_setup + '''try:
    subprocess.run(['git', '--git-dir', scratch + '/.git', 'status', '--porcelain'],
                   check=True, capture_output=True)
finally:
    shutil.rmtree(scratch)
''',
        "git-rev-parse-unknown-option-test.py": (
            "import subprocess\n"
            "subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], "
            "check=True, capture_output=True)\n"),
        "git-config-write-test.py": (
            "import subprocess\n"
            "subprocess.run(['git', 'config', 'run-all-test-suites-test.written', 'value'], "
            "check=True, capture_output=True)\n")}
    repo = make_repo(root, dict(positive_suites, **negative_suites))
    base = commit_files(repo, {"input.txt": "one\n", "sub/tracked.txt": "sub\n"}, "inputs")
    result = run(root)
    check("the git call fixture's full run passes", result.returncode == 0,
          (result.stdout, result.stderr))
    for suite, expected in (
            ("git-sees-no-file-test.py", module.GIT_CALL_SEES_NO_FILE),
            ("git-on-another-repository-test.py", module.GIT_CALL_RUNS_ON_ANOTHER_REPOSITORY)):
        recorded = recording(root, suite)
        calls = recorded.get("git_calls_run_from_the_checkout", [])
        check(f"{suite} records its calls with only {expected} classifications",
              recorded.get("git_commands_on_the_checkout") == [] and bool(calls)
              and all(call["reads"] == expected for call in calls), recorded)
    calls = recording(root, "git-on-another-repository-test.py").get(
        "git_calls_run_from_the_checkout", [])
    scratch_git_directory = next((call["arguments"][0].split("=", 1)[1]
                                  for call in calls if call["arguments"][0].startswith(
                                      "--git-dir=")), None)
    check("the cat-file call records the environment's scratch git directory and top cwd",
          any(call["arguments"] == ["cat-file", "-t", "HEAD"]
              and call["GIT_DIR"] == scratch_git_directory and call["directory"] == "."
              for call in calls) and scratch_git_directory is not None, calls)
    check("the other repository's status call keeps its work-tree argument",
          any(call["arguments"] == ["--git-dir", scratch_git_directory, "--work-tree",
                                    str(pathlib.Path(scratch_git_directory).parent),
                                    "status", "--porcelain"] for call in calls), calls)
    calls = recording(root, "git-sees-no-file-test.py").get(
        "git_calls_run_from_the_checkout", [])
    check("a git call started with cwd sub records that starting directory",
          any(call["directory"] == "sub"
              and call["arguments"] == ["rev-parse", "--show-toplevel"] for call in calls),
          calls)
    commands = {"git-status-with-git-dir-test.py": "status",
                "git-rev-parse-unknown-option-test.py": "rev-parse",
                "git-config-write-test.py": "config"}
    for suite, command in commands.items():
        recorded = recording(root, suite)
        check(f"{suite} records git {command} as reading the checkout",
              recorded.get("git_commands_on_the_checkout") == [command], recorded)

    added_head = commit_files(repo, {"notes/added.txt": "new\n"}, "add an unrelated file")
    result = select_since(root, added_head)
    out = lines(result.stdout)
    check("only calls reading the checkout select suites recorded on another set of files",
          result.returncode == 0 and ran(root) == sorted(negative_suites),
          (ran(root), result.stdout, result.stderr))
    for suite, command in commands.items():
        check(f"{suite} keeps the existing fingerprint SELECTED reason",
              f"SELECTED {suite}: it runs git {command} on the checkout, and its recording "
              "was made on another set of files" in out, out)
    recorded = recording(root, "git-sees-no-file-test.py")
    expected_calls = sorted(("git config --get user.name", "git config user.email",
                             "git rev-parse --git-dir", "git rev-parse --show-toplevel"))
    expected_line = (f"NOT SELECTED git-sees-no-file-test.py: none of the "
                     f"{len(recorded['reads'])} files it read differs since {added_head[:12]}, "
                     "and its git calls read no file of the checkout: "
                     + ", ".join(expected_calls) + " see no file")
    check("the location and config calls' NOT SELECTED line explains every distinct call",
          expected_line in out, out)
    check("the other repository calls' NOT SELECTED line explains every distinct command",
          any(line.startswith("NOT SELECTED git-on-another-repository-test.py: ")
              and line.endswith("its git calls read no file of the checkout: git cat-file, "
                                "git log, git rev-parse, git status, git worktree list "
                                "run on another repository") for line in out), out)

    result = select_since(root, base)
    out = lines(result.stdout)
    check("an unrelated added file selects only suites whose calls read the checkout",
          result.returncode == 0 and ran(root) == sorted(negative_suites),
          (ran(root), result.stdout))
    for suite, command in commands.items():
        check(f"{suite} keeps the existing added-file SELECTED reason",
              f"SELECTED {suite}: it runs git {command} on the checkout, and "
              "notes/added.txt was added" in out, out)

with tempfile.TemporaryDirectory() as scratch:
    root = pathlib.Path(scratch)
    repo = make_repo(root, {"a-test.py": PASSES})
    base = head(repo)
    run(root)
    stored = next((root / "recordings").glob("*/a-test.py.json"))
    recorded = json.loads(stored.read_text())
    recorded["format"] = 2
    stored.write_text(json.dumps(recorded))
    result = select_since(root, base)
    check("format 2 selects a suite once so its git calls can be recorded with format 3",
          result.returncode == 0 and ran(root) == ["a-test.py"]
          and "SELECTED a-test.py: its recording was made by an older version of this program"
          in lines(result.stdout) and recording(root, "a-test.py").get("format") == 3,
          (ran(root), result.stdout))

# --- The recorder runs the sitecustomize.py it shadows ------------------------
# Both machines' Pythons ship one (Homebrew's on the Mac sets sys.executable),
# and the recorder is put in front of it on PYTHONPATH. Here a PYTHONPATH the
# program is given carries one that writes down the process it ran in; the
# suite fails unless it ran in the suite's own process, not only in the
# program's, whose environment the suite inherits.
with tempfile.TemporaryDirectory() as scratch:
    root = pathlib.Path(scratch)
    make_repo(root, {"needs-the-shadowed-sitecustomize-test.py": (
        "ran_in = (here := pathlib.Path(os.environ['" + RAN_FILE_VARIABLE + "']).parent"
        " / 'shadowed-ran-in.txt').read_text().split()\n"
        "sys.exit(0 if str(os.getpid()) in ran_in else 1)\n")})
    shadowed = root / "shadowed"
    shadowed.mkdir()
    (shadowed / "sitecustomize.py").write_text(
        "import os, pathlib\n"
        "with open(pathlib.Path(os.environ['" + RAN_FILE_VARIABLE + "']).parent"
        " / 'shadowed-ran-in.txt', 'a') as ran_in:\n"
        "    ran_in.write(f'{os.getpid()}\\n')\n")
    result = run(root, environment_extra={"PYTHONPATH": str(shadowed)})
    check("a sitecustomize.py already on PYTHONPATH still runs beneath the recorder",
          result.returncode == 0, (result.stdout, result.stderr))

# --- The defaults -------------------------------------------------------------
defaults = module.parse_arguments([])
check("--checkout defaults to the checkout this program is in",
      pathlib.Path(defaults.checkout) == SCRIPTS_DIR.parent, defaults.checkout)
check("--python defaults to the interpreter running the program",
      defaults.python == sys.executable, defaults.python)
check("-j defaults to not given, so the run chooses the job count", defaults.jobs is None,
      defaults.jobs)
for jobs_given, suites_to_run, cores, expected, case in (
        (None, 100, 16, 16, "with no -j, one suite runs per core"),
        (None, 3, 16, 3, "with no -j, no more suites run at once than the run has"),
        (None, 0, 16, 1, "with no -j and no suite to run, the job count is 1, not 0"),
        (None, 100, None, 4, "with no -j and the core count unknown, 4 suites run at once"),
        (2, 100, 16, 2, "-j N overrides the core count"),
        (5, 2, 16, 5, "-j N is used as given, even above the number of suites")):
    answer = module.suites_run_at_once(jobs_given, suites_to_run, cores)
    check(case, answer == expected, (jobs_given, suites_to_run, cores, answer))
check("--lock-file defaults to one file per machine under ~/.claude",
      pathlib.Path(defaults.lock_file) == pathlib.Path.home() / ".claude"
      / ".run-all-test-suites.lock", defaults.lock_file)

print()
# The count is printed so a short run is visible on sight: a run that ends
# early leaves the cases it never reached with no trace at all.
print(f"{cases_run} cases run")
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
