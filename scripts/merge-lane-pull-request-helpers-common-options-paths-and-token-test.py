#!/usr/bin/env python3
"""Tests for merge-lane-pull-request-helpers-common-options-paths-and-token.py.

Parses arguments with the module's directory options from a scratch working
directory, and reads the merge account's token with HOME pointing at a scratch
home.

Run: python3 scripts/merge-lane-pull-request-helpers-common-options-paths-and-token-test.py
"""

import argparse
import importlib.util
import os
import shutil
import sys
import tempfile
from pathlib import Path

MODULE = Path(__file__).with_name("merge-lane-pull-request-helpers-common-options-paths-and-token.py")
_spec = importlib.util.spec_from_file_location("merge_lane_pull_request_helpers_common", MODULE)
common = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(common)

failures = []


def check(name, condition, detail=""):
    print(("PASS  " if condition else "FAIL  ") + name)
    if not condition:
        failures.append(name)
        if detail:
            print("      " + detail.replace("\n", "\n      "))


def parse(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--some-file", type=Path)
    common.add_directory_options(parser, "wt/")
    return common.resolve_path_options(parser.parse_args(argv))


def main():
    scratch = Path(tempfile.mkdtemp(prefix="merge-lane-common-test-")).resolve()
    saved_directory, saved_home = os.getcwd(), os.environ.get("HOME")
    try:
        os.chdir(scratch)
        arguments = parse(["--merge-lane-worktrees-and-outputs-directory", "helpers",
                           "--some-file", "specs/brief.json"])
        check("a relative outputs directory is made absolute against the working directory",
              arguments.merge_lane_worktrees_and_outputs_directory == scratch / "helpers",
              str(arguments.merge_lane_worktrees_and_outputs_directory))
        check("every other Path option is made absolute too",
              arguments.some_file == scratch / "specs" / "brief.json", str(arguments.some_file))
        check("the review tools worktree defaults to the absolute outputs directory's wt/main",
              arguments.review_tools_worktree_at_main == scratch / "helpers" / "wt" / "main",
              str(arguments.review_tools_worktree_at_main))

        arguments = parse(["--merge-lane-worktrees-and-outputs-directory", "helpers",
                           "--review-tools-worktree-at-main", "../elsewhere/main"])
        check("a relative review tools worktree resolves against the working directory, "
              "not under the outputs directory",
              arguments.review_tools_worktree_at_main == scratch.parent / "elsewhere" / "main",
              str(arguments.review_tools_worktree_at_main))

        arguments = parse([])
        check("with no options the outputs directory is merge-lane-2's",
              arguments.merge_lane_worktrees_and_outputs_directory
              == common.DEFAULT_MERGE_LANE_WORKTREES_AND_OUTPUTS_DIRECTORY,
              str(arguments.merge_lane_worktrees_and_outputs_directory))

        home = scratch / "home"
        os.environ["HOME"] = str(home)
        check("the token file is the one merge-gate.sh reads, under HOME at call time",
              common.merge_account_token_file()
              == home / ".config" / "nedschorus" / "ned-review-merge.token",
              str(common.merge_account_token_file()))
        try:
            common.read_merge_account_token()
            check("a missing token file is refused", False)
        except common.MergeAccountTokenUnusable as unusable:
            check("a missing token file is refused, naming the file",
                  "could not read the merge account's token" in str(unusable)
                  and str(common.merge_account_token_file()) in str(unusable), str(unusable))
        common.merge_account_token_file().parent.mkdir(parents=True)
        common.merge_account_token_file().write_text(" \n\t\n")
        try:
            common.read_merge_account_token()
            check("a token file holding only whitespace is refused", False)
        except common.MergeAccountTokenUnusable as unusable:
            check("a token file holding only whitespace is refused",
                  "is empty" in str(unusable), str(unusable))
        common.merge_account_token_file().write_text("a-token-not-a-credential\n")
        check("a token is read without its surrounding whitespace",
              common.read_merge_account_token() == "a-token-not-a-credential")
    finally:
        os.chdir(saved_directory)
        if saved_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = saved_home
        shutil.rmtree(scratch, ignore_errors=True)

    if failures:
        print(f"\n{len(failures)} case(s) failed")
        return 1
    print("\nall cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
