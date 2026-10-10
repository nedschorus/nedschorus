#!/usr/bin/env python3
"""Run main's code-review-codex-cell.py on a pull request's wt/pr<n>-head worktree.

Usage:
  scripts/merge-lane-code-review-codex-cell-run-on-pull-request-head.py <pull request number>
      <base commit> [--merge-lane-worktrees-and-outputs-directory DIR] [--review-tools-worktree-at-main DIR] [--token-file PATH]

The base commit is the merge base for a first review, or the head commit
reviewed before for a fix-round. Saves the pull request's description from
GitHub to cx/pr<n>-<first 8 characters of the base>/description.md under the
worktrees and outputs directory, then runs --review-tools-worktree-at-main's
scripts/code-review-codex-cell.py, not the pull request's, on wt/pr<n>-head
from the base commit. The report, stdout and stderr go to the same directory.

Exit codes: the review's exit code; 2 when the description could not be read,
before the review runs.
"""

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

REPOSITORY = "nedschorus/nedschorus"
DEFAULT_MERGE_LANE_WORKTREES_AND_OUTPUTS_DIRECTORY = Path(
    "/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers")
DEFAULT_TOKEN_FILE = Path.home() / ".config" / "nedschorus" / "ned-review-merge.token"

_runner_spec = importlib.util.spec_from_file_location(
    "run_all_test_suites", Path(__file__).resolve().with_name("run-all-test-suites.py"))
run_all_test_suites = importlib.util.module_from_spec(_runner_spec)
_runner_spec.loader.exec_module(run_all_test_suites)


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        description="Run main's code-review-codex-cell.py on wt/pr<n>-head from a base "
                    "commit, with the pull request's description.")
    parser.add_argument("pull_request", type=int, help="the pull request's number")
    parser.add_argument("base_commit",
                        help="the merge base, or for a fix-round the head commit reviewed before")
    parser.add_argument("--merge-lane-worktrees-and-outputs-directory", type=Path,
                        default=DEFAULT_MERGE_LANE_WORKTREES_AND_OUTPUTS_DIRECTORY,
                        help=f"holds wt/ and cx/ (default: {DEFAULT_MERGE_LANE_WORKTREES_AND_OUTPUTS_DIRECTORY})")
    parser.add_argument("--review-tools-worktree-at-main", type=Path,
                        help="the checkout at main whose scripts/code-review-codex-cell.py runs "
                             "(default: <merge-lane-worktrees-and-outputs-directory>/wt/main)")
    parser.add_argument("--token-file", type=Path, default=DEFAULT_TOKEN_FILE,
                        help=f"the GitHub token gh reads the description with "
                             f"(default: {DEFAULT_TOKEN_FILE})")
    return parser.parse_args(argv)


def main(argv=None):
    arguments = parse_arguments(argv)
    number, base = arguments.pull_request, arguments.base_commit
    helpers = arguments.merge_lane_worktrees_and_outputs_directory
    review_tools_worktree = arguments.review_tools_worktree_at_main or helpers / "wt" / "main"
    outputs = helpers / "cx" / f"pr{number}-{base[:8]}"
    outputs.mkdir(parents=True, exist_ok=True)
    environment = run_all_test_suites.environment_without_git_redirecting_variables()

    try:
        environment["GH_TOKEN"] = arguments.token_file.read_text(encoding="utf-8").strip()
    except OSError as error:
        print(f"PR {number}: Codex review not run: could not read the token file "
              f"{arguments.token_file}: {error.strerror or error}")
        return 2
    description = subprocess.run(
        ["gh", "pr", "view", str(number), "--repo", REPOSITORY, "--json", "body",
         "--jq", ".body"], capture_output=True, text=True, env=environment,
        stdin=subprocess.DEVNULL)
    if description.returncode != 0:
        print(f"PR {number}: Codex review not run: could not read the pull request's "
              f"description: {description.stderr.strip()}")
        return 2
    (outputs / "description.md").write_text(description.stdout)
    del environment["GH_TOKEN"]

    with open(outputs / "stdout", "w") as stdout, open(outputs / "stderr", "w") as stderr:
        review = subprocess.run(
            [sys.executable, str(review_tools_worktree / "scripts" / "code-review-codex-cell.py"),
             "--base", base, "--repo", str(helpers / "wt" / f"pr{number}-head"),
             "--pull-request-description-file", str(outputs / "description.md"),
             "--output", str(outputs / "report.md")],
            env=environment, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr)
    print(f"PR {number} codex cell (base {base[:8]}) exit {review.returncode}; "
          f"report {outputs / 'report.md'}")
    return review.returncode


if __name__ == "__main__":
    sys.exit(main())
