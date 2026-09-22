#!/usr/bin/env python3
"""Run every test suite in a checkout, and report each one by its exit code.

Usage:
  scripts/run-all-test-suites.py [--checkout DIR] [--python INTERPRETER]
                                 [-j N] [--log-dir DIR] [--lock-file PATH]

  --checkout    the top directory of the checkout to test; default, the
                checkout this file is in
  --python      the interpreter that runs each suite file; default, the one
                running this program
  -j            how many suites run at once; default 1
  --log-dir     where each suite's output and the report are written;
                default, a new directory under the system temp directory
  --lock-file   the lock that keeps two runs on one machine apart; default
                ~/.claude/.run-all-test-suites.lock

WHY THIS EXISTS (user-ruled 2026-09-21, walk "redesigning how pull requests
are processed", items 3 and 6). Until this program, every full run of the
project's suites was a shell loop kept in the merge-lane seat's gitignored
walk-ledgers/, untested and on one machine only. Its suite list was four
fixed globs, and when two systems moved into new directories the loop kept
reporting green over 52 of the 66 suites, because nothing it ran could see
the suites it no longer found. This program carries that loop's behaviour
into scripts/, with its test, and fixes the ways it was measured to go
wrong. The design-to-main machine's test-suite-executing state needs the
same thing, so this outlives the merge lane.

WHAT IT RUNS. Every file git lists matching `*-test.py`
(`git ls-files -- '*-test.py'`, whose `*` crosses directory boundaries), so
a suite in a directory nobody has told this program about is still run.
Measured 2026-09-21: that list and the four globs found the same 65 files,
and git's list leaves out the fixture design-to-main-test-fixture.py by
itself. A file git does not track is not run: commit or add a new suite
before expecting it here. The checkout must be named by its top directory,
because `git ls-files` run from a subdirectory lists only that subdirectory,
which is the 52-of-66 failure in another form; any other directory is
refused.

HOW EACH SUITE IS JUDGED. By its exit code, and nothing else: 0 is PASS,
anything else is FAIL, and a suite killed by a signal is FAIL naming the
signal. The suites print at least four different success wordings, so no
text can be trusted to mean pass or fail. Each suite runs as
`<interpreter> -u <path>` from the checkout's top directory, stdin closed,
stdout and stderr together into its own log file. A suite that starts
`python3` itself gets whatever PATH finds, not --python.

SKIPPED CASES are reported from text, because no exit code carries them: a
suite that skips a case still exits 0. Measured 2026-09-21: no suite uses
unittest's skip machinery, and the four that can skip
(scripts/resupervise-seat-test.py, scripts/recover-crashed-seats-test.py,
scripts/clean-worktrees-test.py, nc-systems/main-gatekeeper/tests/
main-gatekeeper-test.py) print a line opening `SKIP` followed by a space.
Every such line in a suite's output is counted and printed. resupervise-seat
prints its skips and then "all cases passed", which is how a run that
dropped its end-to-end cases used to read as a full pass. A skip never
changes a verdict; it is reported beside it.

ONE RUN AT A TIME PER MACHINE. Measured 2026-09-21: two overlapping runs of
scripts/resupervise-seat-test.py both exit 0 and both print "all cases
passed" while silently dropping cases to SKIP, because the suites share
machine state. So a run takes an exclusive lock on --lock-file, and a
second run on the same machine exits 3 without running anything. The lock
file names its holder (process id, checkout, start time), and the refusal
prints it.

CONCURRENCY. -j N runs N suites at once. Measured on ned-box 2026-09-21
over the 65 suites: serial 479 s, -j4 247 s, -j8 235 s. -j8 buys little
because scripts/cold-read-grid-test.py alone takes 233 s. The default is 1,
which is what the walk-ledgers loop did; -j4 is the measured choice.

NO PER-SUITE TIMEOUT. No suite has been seen to hang, so none is imposed.
A hung suite hangs the run.

OUTPUT. A first line naming the checkout, its commit, whether tracked files
differ from that commit, the suite count, the interpreter's own --version
answer and path, -j, and the log directory. Then one line per suite as it
finishes: `PASS <path> (<seconds>s)` or `FAIL <path> exit <code>
(<seconds>s)`, with `, <n> skipped` when it printed SKIP lines. Then the
failed suites again, each with its log, and every SKIP line, each with its
suite, so the end of the output holds everything needed. The last line
opens `SUMMARY:` and carries the counts. The whole report is also written to
report.txt in the log directory, so a run in the background needs no pipe to
keep it.

EXIT. 0 when every suite exited 0; 1 when any suite failed; 2 when the run
could not start (not a checkout's top directory, no suites listed, git or
the interpreter unusable); 3 when another run holds the lock.
"""

import argparse
import concurrent.futures
import datetime
import fcntl
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

PROGRAM = "run-all-test-suites"

TEST_SUITE_PATHSPEC = "*-test.py"
SKIPPED_CASE_LINE = re.compile(r"^SKIP\s")
DEFAULT_LOCK_FILE = Path.home() / ".claude" / ".run-all-test-suites.lock"
REPORT_FILE_NAME = "report.txt"

EXIT_ALL_PASSED = 0
EXIT_SOME_FAILED = 1
EXIT_COULD_NOT_RUN = 2
EXIT_LOCKED = 3


class CouldNotRun(Exception):
    """The run cannot start; the message is printed as the refusal."""


def git(checkout, *arguments):
    return subprocess.run(["git", "-C", str(checkout), *arguments],
                          capture_output=True, text=True, check=False)


def checkout_top_directory(given):
    """The checkout's top directory, when `given` is it; otherwise a refusal."""
    answer = git(given, "rev-parse", "--show-toplevel")
    if answer.returncode != 0:
        raise CouldNotRun(
            f"{PROGRAM}: not run — {given} is not inside a git checkout.\n"
            f"Pass --checkout the top directory of a checkout.")
    top = Path(answer.stdout.strip()).resolve()
    if top != Path(given).resolve():
        raise CouldNotRun(
            f"{PROGRAM}: not run — {given} is not the top directory of its checkout.\n"
            f"Pass --checkout {top}")
    return top


def suites_listed_by_git(top):
    listed = git(top, "ls-files", "-z", "--", TEST_SUITE_PATHSPEC)
    if listed.returncode != 0:
        raise CouldNotRun(
            f"{PROGRAM}: not run — git ls-files failed in {top}: "
            f"{listed.stderr.strip()}\n"
            f"Fix what git reports, then run this again.")
    suites = [path for path in listed.stdout.split("\0") if path]
    if not suites:
        raise CouldNotRun(
            f"{PROGRAM}: not run — git lists no {TEST_SUITE_PATHSPEC} file in {top}.\n"
            f"Pass --checkout a checkout that has its suites committed or added.")
    return suites


def interpreter_and_version(given):
    found = shutil.which(given)
    if found is None:
        raise CouldNotRun(
            f"{PROGRAM}: not run — no interpreter found for --python {given}.\n"
            f"Pass --python a path or command name that exists.")
    try:
        answer = subprocess.run([found, "--version"], capture_output=True,
                                text=True, stdin=subprocess.DEVNULL, check=False)
    except OSError as error:
        raise CouldNotRun(
            f"{PROGRAM}: not run — {found} could not be started: {error}\n"
            f"Pass --python an interpreter that runs.") from error
    version = (answer.stdout.strip() or answer.stderr.strip()).splitlines()
    if answer.returncode != 0 or not version:
        raise CouldNotRun(
            f"{PROGRAM}: not run — {found} --version exited {answer.returncode}.\n"
            f"Pass --python an interpreter that runs.")
    return found, version[0]


def commit_and_state(top):
    head = git(top, "rev-parse", "HEAD")
    commit = head.stdout.strip() if head.returncode == 0 else "no commit"
    changed = git(top, "status", "--porcelain", "--untracked-files=no")
    if changed.returncode != 0:
        state = "tracked-file state unknown"
    elif changed.stdout.strip():
        state = "tracked files differ from that commit"
    else:
        state = "tracked files match that commit"
    return commit, state


def take_machine_lock(lock_file, top):
    """(the open, locked handle, None) when this run takes the lock;
    (None, the holder's description of itself) when another run holds it.

    Opened for append, so a run that loses the race never truncates the
    holder's description of itself before reading it.
    """
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_file, "a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.seek(0)
        holder = handle.read().strip() or "a run that has not described itself yet"
        handle.close()
        return None, holder
    handle.seek(0)
    handle.truncate()
    started = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    handle.write(f"pid {os.getpid()}, checkout {top}, started {started}\n")
    handle.flush()
    return handle, None


def log_path_for(log_dir, suite):
    # The whole relative path, so two suites with one file name in
    # different directories cannot overwrite each other's log.
    return log_dir / (suite.replace("/", "__") + ".log")


def skipped_case_lines(log_file):
    try:
        text = log_file.read_text(errors="replace")
    except OSError:
        return []
    return [line for line in text.splitlines() if SKIPPED_CASE_LINE.match(line)]


def run_one_suite(top, interpreter, suite, log_dir):
    log_file = log_path_for(log_dir, suite)
    started = time.monotonic()
    with open(log_file, "wb") as log:
        completed = subprocess.run([interpreter, "-u", suite], cwd=str(top),
                                   stdin=subprocess.DEVNULL, stdout=log,
                                   stderr=subprocess.STDOUT, check=False)
    return {
        "suite": suite,
        "exit": completed.returncode,
        "seconds": time.monotonic() - started,
        "log": log_file,
        "skips": skipped_case_lines(log_file),
    }


def describe_exit(code):
    if code >= 0:
        return f"exit {code}"
    try:
        return f"killed by {signal.Signals(-code).name}"
    except ValueError:
        return f"killed by signal {-code}"


def suite_line(result):
    detail = f"{result['seconds']:.1f}s"
    if result["skips"]:
        detail += f", {len(result['skips'])} skipped"
    if result["exit"] == 0:
        return f"PASS {result['suite']} ({detail})"
    return f"FAIL {result['suite']} {describe_exit(result['exit'])} ({detail})"


class Report:
    """Every line goes to stdout at once and to report.txt in the log directory."""

    def __init__(self, report_file):
        self.lock = threading.Lock()
        self.file = open(report_file, "w")

    def line(self, text):
        with self.lock:
            print(text, flush=True)
            self.file.write(text + "\n")
            self.file.flush()

    def close(self):
        self.file.close()


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        prog=PROGRAM, description="Run every *-test.py suite git lists in a checkout.")
    parser.add_argument("--checkout", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("-j", dest="jobs", type=int, default=1)
    parser.add_argument("--log-dir")
    parser.add_argument("--lock-file", default=str(DEFAULT_LOCK_FILE))
    arguments = parser.parse_args(argv)
    if arguments.jobs < 1:
        parser.error("-j takes a whole number of at least 1")
    return arguments


def main(argv=None):
    arguments = parse_arguments(argv)
    try:
        top = checkout_top_directory(arguments.checkout)
        suites = suites_listed_by_git(top)
        interpreter, version = interpreter_and_version(arguments.python)
    except CouldNotRun as refusal:
        print(refusal, file=sys.stderr)
        return EXIT_COULD_NOT_RUN

    lock_handle, holder = take_machine_lock(Path(arguments.lock_file), top)
    if lock_handle is None:
        print(f"{PROGRAM}: not run — another run holds {arguments.lock_file}: {holder}.\n"
              f"Run this again after that run has finished.", file=sys.stderr)
        return EXIT_LOCKED

    try:
        if arguments.log_dir:
            log_dir = Path(arguments.log_dir).resolve()
            log_dir.mkdir(parents=True, exist_ok=True)
        else:
            log_dir = Path(tempfile.mkdtemp(prefix=f"{PROGRAM}-"))
        commit, state = commit_and_state(top)
        report = Report(log_dir / REPORT_FILE_NAME)
        report.line(f"{PROGRAM}: {top} at {commit} ({state}); {len(suites)} suites "
                    f"listed by git; {version} ({interpreter}); -j {arguments.jobs}; "
                    f"logs in {log_dir}")

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=arguments.jobs) as pool:
            running = [pool.submit(run_one_suite, top, interpreter, suite, log_dir)
                       for suite in suites]
            for finished in concurrent.futures.as_completed(running):
                result = finished.result()
                results.append(result)
                report.line(suite_line(result))

        results.sort(key=lambda result: result["suite"])
        failed = [result for result in results if result["exit"] != 0]
        skipping = [result for result in results if result["skips"]]
        if failed:
            report.line("")
            report.line(f"{len(failed)} failed:")
            for result in failed:
                report.line(f"FAIL {result['suite']} {describe_exit(result['exit'])}"
                            f" — log {result['log']}")
        if skipping:
            report.line("")
            report.line("skipped cases:")
            for result in skipping:
                for skip in result["skips"]:
                    report.line(f"{result['suite']}: {skip}")
        skip_count = sum(len(result["skips"]) for result in results)
        report.line(f"SUMMARY: {len(results) - len(failed)} passed, {len(failed)} failed, "
                    f"{len(results)} total; {skip_count} cases skipped in {len(skipping)} "
                    f"suites; {top.name} at {commit[:12]}; {version}")
        report.close()
        return EXIT_SOME_FAILED if failed else EXIT_ALL_PASSED
    finally:
        lock_handle.close()


if __name__ == "__main__":
    sys.exit(main())
