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
import subprocess
import sys
import tempfile

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
# fixture pattern scripts/cold-read-grid-test.py and
# scripts/cold-read-cell-common-test.py are built on.
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

    It tracks `suite_path` under that name because the program's own
    `git ls-files` resolves through GIT_DIR too, so the suite list it reads is
    the victim's. That is the 2026-09-22 incident's own shape — a second clone
    of the same project, with the same paths in it — and it is what lets this
    case reach the thing it is about, which is the environment the program
    launches a suite WITH."""
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
    result = run(root, rendezvous_seconds="0.5")
    check("the default runs one suite at a time", result.returncode == 1
          and lines(result.stdout)[-1].startswith("SUMMARY: 1 passed, 1 failed"),
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

# --- Which variables are stripped, and which are deliberately kept -----------
# The five beyond GIT_DIR cannot be driven through a whole run: each of them
# also redirects the program's OWN `git ls-files` and `rev-parse`, so a run
# carrying them refuses at exit 2 before any suite is launched (measured
# 2026-09-22; the program's docstring records it as a limit). They are pinned
# here at the seam they act on instead. GIT_NAMESPACE and
# GIT_CEILING_DIRECTORIES are checked as KEPT, because deciding against them
# was a measured decision and widening the list later should trip a case.
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

# --- The defaults -------------------------------------------------------------
defaults = module.parse_arguments([])
check("--checkout defaults to the checkout this program is in",
      pathlib.Path(defaults.checkout) == SCRIPTS_DIR.parent, defaults.checkout)
check("--python defaults to the interpreter running the program",
      defaults.python == sys.executable, defaults.python)
check("-j defaults to 1", defaults.jobs == 1, defaults.jobs)
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
