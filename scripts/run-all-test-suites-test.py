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


def run(root, *arguments, checkout=None, lock_file=None, rendezvous_seconds="20"):
    """The program run against root/repo with its own lock and log directory."""
    environment = dict(os.environ)
    environment[RAN_FILE_VARIABLE] = str(root / "ran.txt")
    environment[RENDEZVOUS_WAIT_VARIABLE] = rendezvous_seconds
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

# --- The defaults -------------------------------------------------------------
module = load_program_module()
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
