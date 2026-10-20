#!/usr/bin/env python3
"""Run main's pull-request-head-test-run.py on each pull request's wt/pr<n>-merged worktree.

Usage:
  scripts/merge-lane-pull-request-head-test-run-on-merged-worktree.py <pull request number>...
      [--merge-lane-worktrees-and-outputs-directory DIR] [--review-tools-worktree-at-main DIR]

For each pull request in turn, runs --review-tools-worktree-at-main's
scripts/pull-request-head-test-run.py, not the pull request's, so a pull
request cannot pass by changing its runner. Under the worktrees and outputs
directory it tests wt/pr<n>-merged, files the record under
hr/pr<n>/log-store, uses hr/pr<n>/tmp as its temporary directory and
hr/store as the recorded inputs, and writes its output to hr/pr<n>/stdout and
hr/pr<n>/stderr; each line of the run's stderr, where it copies the
runner's progress, is also printed on this program's stderr as it arrives,
so a run stopped before it ends has shown how far it got. tripwire-bin/ goes first on PATH: its claude and codex log
the call and exit 1, so no suite starts a real agent.

pull-request-head-test-run.py waits for the machine's test lock itself, so
nothing here retries.

Prints one line per pull request with the run's exit code and SUMMARY line.
Exit codes: 0 every run exited 0 and every copy of its stderr was written;
otherwise the code set by the first pull request that failed: 2 when a copy
of its run's stderr could not be written, even when the run exited nonzero,
else its run's exit code; 2 also when tripwire-bin/ or
--review-tools-worktree-at-main's scripts/pull-request-head-test-run.py is
missing, before any run.
"""

import argparse
import importlib.util
import os
import shlex
import subprocess
import sys
from pathlib import Path

SUMMARY_LINE_PREFIX = "SUMMARY:"
HEAD_TEST_RUNNER = Path("scripts") / "pull-request-head-test-run.py"

_common_spec = importlib.util.spec_from_file_location(
    "merge_lane_pull_request_helpers_common", Path(__file__).resolve().with_name(
        "merge-lane-pull-request-helpers-common-options-paths-and-token.py"))
common = importlib.util.module_from_spec(_common_spec)
_common_spec.loader.exec_module(common)
run_all_test_suites = common.run_all_test_suites


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        description="Run main's pull-request-head-test-run.py on wt/pr<n>-merged for each "
                    "pull request, with its outputs under the worktrees and outputs directory.")
    parser.add_argument("pull_requests", type=int, nargs="+", metavar="pull_request",
                        help="a pull request's number")
    common.add_directory_options(parser, "wt/, hr/ and tripwire-bin/")
    return common.resolve_path_options(parser.parse_args(argv))


def main(argv=None):
    arguments = parse_arguments(argv)
    helpers = arguments.merge_lane_worktrees_and_outputs_directory
    review_tools_worktree = arguments.review_tools_worktree_at_main
    tripwire = helpers / "tripwire-bin"
    if not tripwire.is_dir():
        print(f"not run: {tripwire} is missing, and without it a suite could start a real "
              f"claude or codex.\n"
              f"Restore {tripwire} with a claude and a codex that exit 1, or pass the "
              f"--merge-lane-worktrees-and-outputs-directory that holds it.")
        return 2
    missing = common.review_tool_missing_message(arguments, HEAD_TEST_RUNNER)
    if missing:
        print(f"not run: {missing}")
        return 2
    environment = run_all_test_suites.environment_without_git_redirecting_variables()
    environment["PATH"] = f"{tripwire}{os.pathsep}{environment.get('PATH', '')}"

    first_failure = 0
    for number in arguments.pull_requests:
        outputs = helpers / "hr" / f"pr{number}"
        (outputs / "log-store").mkdir(parents=True, exist_ok=True)
        (outputs / "tmp").mkdir(parents=True, exist_ok=True)
        with open(outputs / "stdout", "w") as stdout, open(outputs / "stderr", "w") as stderr:
            run = subprocess.Popen(
                [sys.executable, str(review_tools_worktree / HEAD_TEST_RUNNER),
                 "--checkout", str(helpers / "wt" / f"pr{number}-merged"),
                 "--log-store-root", str(outputs / "log-store"),
                 "--temporary-directory", str(outputs / "tmp"),
                 "--recorded-inputs-directory", str(helpers / "hr" / "store")],
                cwd=helpers, env=environment, stdin=subprocess.DEVNULL,
                stdout=stdout, stderr=subprocess.PIPE, text=True, errors="replace")
            copy_failures = {}
            # A failed write stops copying to that target only; the pipe is still read
            # to its end, so the run is never left blocked on it.
            for line in run.stderr:
                for target, name in ((stderr, f"{outputs}/stderr"), (sys.stderr, "stderr")):
                    if name in copy_failures:
                        continue
                    try:
                        target.write(line)
                        target.flush()
                    except (OSError, ValueError) as error:
                        copy_failures[name] = f"{type(error).__name__}: {error}"
                        if target is stderr:
                            # The line that failed stays in the file's buffer, and the close
                            # at the end of the with block would raise the same error on it.
                            try:
                                stderr.close()
                            except OSError as close_error:
                                copy_failures[name] += (f"; closing it then failed too "
                                                        f"({type(close_error).__name__}: "
                                                        f"{close_error})")
                        if target is sys.stderr:
                            # Python flushes sys.stderr again at exit, and a failure there
                            # would replace this program's exit code with 120.
                            sys.stderr = open(os.devnull, "w")
            completed = subprocess.CompletedProcess(run.args, run.wait())
        rerun = shlex.join([
            sys.executable, str(Path(__file__).resolve()), str(number),
            "--merge-lane-worktrees-and-outputs-directory", str(helpers),
            "--review-tools-worktree-at-main", str(review_tools_worktree)])
        for name, failure in copy_failures.items():
            # Only the copy to this program's own stderr failed, so the file has every line.
            if f"{outputs}/stderr" not in copy_failures:
                where_to_find_it = (f"When you need the lost stderr, read {outputs}/stderr, "
                                    f"which holds all of it.")
            else:
                where_to_find_it = (
                    f"When you need the lost stderr, run the head test run for PR {number} "
                    f"again with this command, from any directory: {rerun}\n"
                    f"Before you run it, give it a stderr that takes every write: do not "
                    f"close its stderr, pipe it to a program that exits before the run ends, "
                    f"or redirect it to a read-only file or a file on a full disk; and when "
                    f"{outputs}/stderr is the copy that failed, fix what {failure} names "
                    f"first.")
            print(f"PR {number} head test run, process {run.pid}: writing its stderr to "
                  f"{name} failed ({failure}); the run went on to its end, and that copy "
                  f"lacks the run's stderr from the first line that could not be written to "
                  f"it onward.\n"
                  f"The run's verdict still stands: the line below gives the run's exit code and "
                  f"SUMMARY line, from the run's stdout, not from this copy. "
                  f"{Path(__file__).name} exits 2 for the failed copy, even when this run "
                  f"exited nonzero, unless an earlier pull request's run or failed copy "
                  f"already set a nonzero exit code; that 2 says nothing about the tests.\n"
                  f"{where_to_find_it}",
                  flush=True)
            if first_failure == 0:
                first_failure = 2
        summaries = [line for line in (outputs / "stdout").read_text().splitlines()
                     if line.startswith(SUMMARY_LINE_PREFIX)]
        summary = summaries[-1] if summaries else f"no SUMMARY line; see {outputs}/stderr"
        print(f"PR {number} head test run: exit {completed.returncode}; {summary}", flush=True)
        if completed.returncode != 0 and first_failure == 0:
            first_failure = completed.returncode
    return first_failure


if __name__ == "__main__":
    sys.exit(main())
