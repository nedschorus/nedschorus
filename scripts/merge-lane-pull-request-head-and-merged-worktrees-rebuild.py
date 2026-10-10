#!/usr/bin/env python3
"""Rebuild a pull request's two detached worktrees under the worktrees and outputs directory.

Usage:
  scripts/merge-lane-pull-request-head-and-merged-worktrees-rebuild.py <pull request number>
      <head commit> <main commit> [--merge-lane-worktrees-and-outputs-directory DIR] [--review-tools-worktree-at-main DIR]

Fetches the pull request's head from origin, then makes wt/pr<n>-head at the
head commit and wt/pr<n>-merged at the main commit with the head commit merged
in, as merge-lane-2, always with a merge commit. A worktree already at either
path is removed first, with any changes in it.

Git runs in --review-tools-worktree-at-main. Every worktree of one repository shares its
objects, so the fetched head commit is visible to the new worktrees.

Exit codes: 0 both worktrees made; 1 a git step failed, named on stdout.
"""

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

MERGE_COMMIT_IDENTITY = ("-c", "user.name=merge-lane-2", "-c", "user.email=noreply@anthropic.com")

_common_spec = importlib.util.spec_from_file_location(
    "merge_lane_pull_request_helpers_common", Path(__file__).resolve().with_name(
        "merge-lane-pull-request-helpers-common-options-paths-and-token.py"))
common = importlib.util.module_from_spec(_common_spec)
_common_spec.loader.exec_module(common)
run_all_test_suites = common.run_all_test_suites


class GitStepFailed(Exception):
    pass


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        description="Make wt/pr<n>-head at a pull request's head commit and wt/pr<n>-merged "
                    "at that head merged onto main, both detached.")
    parser.add_argument("pull_request", type=int, help="the pull request's number")
    parser.add_argument("head_commit", help="the pull request's head commit")
    parser.add_argument("main_commit", help="the main commit to merge the head commit onto")
    common.add_directory_options(parser, "wt/")
    return common.resolve_path_options(parser.parse_args(argv))


def git(directory, *arguments):
    completed = subprocess.run(
        ["git", "-C", str(directory), *arguments], capture_output=True, text=True,
        stdin=subprocess.DEVNULL,
        env=run_all_test_suites.environment_without_git_redirecting_variables())
    if completed.returncode != 0:
        raise GitStepFailed(f"git {' '.join(arguments)} in {directory} exited "
                            f"{completed.returncode}: {completed.stderr.strip()}")
    return completed.stdout.strip()


def main(argv=None):
    arguments = parse_arguments(argv)
    number = arguments.pull_request
    worktrees = arguments.merge_lane_worktrees_and_outputs_directory / "wt"
    checkout = arguments.review_tools_worktree_at_main
    head_worktree = worktrees / f"pr{number}-head"
    merged_worktree = worktrees / f"pr{number}-merged"
    try:
        git(checkout, "fetch", "-q", "origin", f"pull/{number}/head")
        for worktree in (head_worktree, merged_worktree):
            if worktree.exists():
                git(checkout, "worktree", "remove", "--force", str(worktree))
        git(checkout, "worktree", "add", "-q", "--detach", str(head_worktree),
            arguments.head_commit)
        git(checkout, "worktree", "add", "-q", "--detach", str(merged_worktree),
            arguments.main_commit)
        git(merged_worktree, *MERGE_COMMIT_IDENTITY, "merge", "-q", "--no-edit", "--no-ff",
            arguments.head_commit)
        head_short = git(head_worktree, "rev-parse", "--short", "HEAD")
        merged_short = git(merged_worktree, "rev-parse", "--short", "HEAD")
        merged_tree = git(merged_worktree, "rev-parse", "HEAD^{tree}")
    except GitStepFailed as failure:
        print(f"PR {number}: worktrees not rebuilt: {failure}\n"
              f"If the git error above names a cause you can fix, such as a wrong commit, fix "
              f"it and run this again.\n"
              f"Otherwise, tell the user this message.")
        return 1
    print(f"PR {number}: head {head_short}, merged {merged_short} tree {merged_tree} "
          f"on main {arguments.main_commit[:8]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
