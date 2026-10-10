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
hr/pr<n>/stderr. tripwire-bin/ goes first on PATH: its claude and codex log
the call and exit 1, so no suite starts a real agent.

pull-request-head-test-run.py waits for the machine's test lock itself, so
nothing here retries.

Prints one line per pull request with the run's exit code and SUMMARY line.
Exit codes: 0 every run exited 0; otherwise the first nonzero exit code; 2
also when tripwire-bin/ or --review-tools-worktree-at-main's
scripts/pull-request-head-test-run.py is missing, before any run.
"""

import argparse
import importlib.util
import os
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
            completed = subprocess.run(
                [sys.executable, str(review_tools_worktree / HEAD_TEST_RUNNER),
                 "--checkout", str(helpers / "wt" / f"pr{number}-merged"),
                 "--log-store-root", str(outputs / "log-store"),
                 "--temporary-directory", str(outputs / "tmp"),
                 "--recorded-inputs-directory", str(helpers / "hr" / "store")],
                cwd=helpers, env=environment, stdin=subprocess.DEVNULL,
                stdout=stdout, stderr=stderr)
        summaries = [line for line in (outputs / "stdout").read_text().splitlines()
                     if line.startswith(SUMMARY_LINE_PREFIX)]
        summary = summaries[-1] if summaries else f"no SUMMARY line; see {outputs}/stderr"
        print(f"PR {number} head test run: exit {completed.returncode}; {summary}", flush=True)
        if completed.returncode != 0 and first_failure == 0:
            first_failure = completed.returncode
    return first_failure


if __name__ == "__main__":
    sys.exit(main())
