#!/usr/bin/env python3
"""Run main's code-review-codex-cell.py on a pull request's wt/pr<n>-head worktree.

Usage:
  scripts/merge-lane-code-review-codex-cell-run-on-pull-request-head.py <pull request number>
      <base commit> [--merge-lane-worktrees-and-outputs-directory DIR] [--review-tools-worktree-at-main DIR]

The base commit is the merge base for a first review, or the head commit
reviewed before for a fix-round. Saves the pull request's description from
GitHub to cx/pr<n>-<first 8 characters of the base>/description.md under the
worktrees and outputs directory, then runs --review-tools-worktree-at-main's
scripts/code-review-codex-cell.py, not the pull request's, on wt/pr<n>-head
from the base commit. The report, stdout and stderr go to the same directory.
gh reads the description with the merge account's token, the one file every
merge-lane helper and merge-gate.sh read.

Exit codes: the review's exit code; 2 when the token, the description or
--review-tools-worktree-at-main's scripts/code-review-codex-cell.py could not
be read, before the review runs.
"""

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

CODEX_CELL = Path("scripts") / "code-review-codex-cell.py"

_common_spec = importlib.util.spec_from_file_location(
    "merge_lane_pull_request_helpers_common", Path(__file__).resolve().with_name(
        "merge-lane-pull-request-helpers-common-options-paths-and-token.py"))
common = importlib.util.module_from_spec(_common_spec)
_common_spec.loader.exec_module(common)
run_all_test_suites = common.run_all_test_suites
REPOSITORY = common.REPOSITORY


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        description="Run main's code-review-codex-cell.py on wt/pr<n>-head from a base "
                    "commit, with the pull request's description.")
    parser.add_argument("pull_request", type=int, help="the pull request's number")
    parser.add_argument("base_commit",
                        help="the merge base, or for a fix-round the head commit reviewed before")
    common.add_directory_options(parser, "wt/ and cx/")
    return common.resolve_path_options(parser.parse_args(argv))


def main(argv=None):
    arguments = parse_arguments(argv)
    number, base = arguments.pull_request, arguments.base_commit
    helpers = arguments.merge_lane_worktrees_and_outputs_directory
    review_tools_worktree = arguments.review_tools_worktree_at_main
    outputs = helpers / "cx" / f"pr{number}-{base[:8]}"
    outputs.mkdir(parents=True, exist_ok=True)
    environment = run_all_test_suites.environment_without_git_redirecting_variables()

    missing = common.review_tool_missing_message(arguments, CODEX_CELL)
    if missing:
        print(f"PR {number}: Codex review not run: {missing}")
        return 2
    try:
        environment["GH_TOKEN"] = common.read_merge_account_token()
    except common.MergeAccountTokenUnusable as unusable:
        print(f"PR {number}: Codex review not run: {unusable}.\n"
              f"Tell the user this message: only the user can restore the token.")
        return 2
    description = subprocess.run(
        ["gh", "pr", "view", str(number), "--repo", REPOSITORY, "--json", "body",
         "--jq", ".body"], capture_output=True, text=True, env=environment,
        stdin=subprocess.DEVNULL)
    if description.returncode != 0:
        print(f"PR {number}: Codex review not run: could not read the pull request's "
              f"description: {description.stderr.strip()}\n"
              f"Run this again once; if it fails the same way, tell the user this message.")
        return 2
    (outputs / "description.md").write_text(description.stdout)
    del environment["GH_TOKEN"]

    with open(outputs / "stdout", "w") as stdout, open(outputs / "stderr", "w") as stderr:
        review = subprocess.run(
            [sys.executable, str(review_tools_worktree / CODEX_CELL),
             "--base", base, "--repo", str(helpers / "wt" / f"pr{number}-head"),
             "--pull-request-description-file", str(outputs / "description.md"),
             "--output", str(outputs / "report.md")],
            env=environment, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr)
    print(f"PR {number} codex cell (base {base[:8]}) exit {review.returncode}; "
          f"report {outputs / 'report.md'}")
    return review.returncode


if __name__ == "__main__":
    sys.exit(main())
