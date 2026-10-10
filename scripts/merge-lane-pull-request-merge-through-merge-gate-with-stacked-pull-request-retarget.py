#!/usr/bin/env python3
"""Merge one pull request through merge-gate.sh, retargeting the pull requests stacked on it first.

Usage:
  scripts/merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py <pull request number>
      <head commit, all 40 characters> <reviewed-since>
      [--merge-lane-worktrees-and-outputs-directory DIR] [--review-tools-worktree-at-main DIR]

Runs --review-tools-worktree-at-main's scripts/merge-gate.sh, never the pull
request's own copy, with the three arguments. While the gate
refuses with "mergeStateStatus is UNKNOWN", it runs the gate again, 5 seconds
apart, at most 8 times in all. When the gate passes, the merge command it
prints must be exactly the one this program expects; then every open pull
request whose base branch is this pull request's branch is retargeted to this
pull request's base branch, and the merge command runs.

The merge command deletes the pull request's branch, and GitHub closes every
open pull request whose base branch is deleted. The retarget is here, not in
merge-gate.sh, because the gate only reads GitHub and its callers may run it
without merging; a retarget belongs just before a merge that is about to run.

Every gh call runs with GH_TOKEN read from the merge account's token file,
the file merge-gate.sh reads, so the gate, the retargets and the merge use one
token.

Before the gate runs, this program fetches origin in
--review-tools-worktree-at-main and refuses unless that worktree's HEAD is
origin/main, so a stale worktree never lets an older gate decide a merge.

Exit codes: 0 merged; 1 the gate refused, printed a merge command other than
the expected one, or the merge failed; 2 the token file could not be read or
was empty, --review-tools-worktree-at-main has no scripts/merge-gate.sh, could
not be fetched or is not at origin/main, the gate could not run or exited with
a code it does not document, or a read or a retarget on GitHub failed, each
before any merge.
"""

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

_common_spec = importlib.util.spec_from_file_location(
    "merge_lane_pull_request_helpers_common", Path(__file__).resolve().with_name(
        "merge-lane-pull-request-helpers-common-options-paths-and-token.py"))
common = importlib.util.module_from_spec(_common_spec)
_common_spec.loader.exec_module(common)

REPOSITORY = common.REPOSITORY

# merge-gate.sh keeps this text in the first line of its UNKNOWN refusal.
MERGE_STATE_UNKNOWN_REFUSAL = "mergeStateStatus is UNKNOWN"
MERGE_GATE_TRIES = 8
SECONDS_BETWEEN_MERGE_GATE_TRIES = 5
MERGE_COMMAND_HEADING = "MERGE WITH THIS EXACT COMMAND:"

# gh pr list returns 30 pull requests unless told otherwise; a stacked pull
# request beyond the limit would be missed and then closed by the merge.
OPEN_PULL_REQUEST_LIST_LIMIT = 1000

EXIT_MERGED = 0
EXIT_REFUSED = 1
EXIT_COULD_NOT_RUN = 2
MERGE_GATE_DOCUMENTED_EXITS = (0, 1, 2)
MERGE_GATE = Path("scripts") / "merge-gate.sh"


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        description="Run merge-gate.sh for one pull request; when it passes, retarget the "
                    "open pull requests based on its branch, then run the merge command the "
                    "gate printed.")
    parser.add_argument("pull_request", help="the pull request's number")
    parser.add_argument("head_commit", help="the head commit, all 40 characters")
    parser.add_argument("reviewed_since",
                        help="the reviewed-since time merge-gate.sh takes, YYYY-MM-DDTHH:MM:SSZ")
    common.add_directory_options(parser, "wt/")
    return common.resolve_path_options(parser.parse_args(argv))


def run(command, environment):
    return subprocess.run(command, capture_output=True, text=True, env=environment,
                          stdin=subprocess.DEVNULL)


def gh_error(completed):
    return completed.stderr.strip() or f"gh exited {completed.returncode} and printed no error"


def merge_gate_after_retries(arguments, environment, wait):
    """Return the last run of the gate, stdout and stderr together."""
    for attempt in range(1, MERGE_GATE_TRIES + 1):
        gate = subprocess.run(
            ["bash", str(arguments.review_tools_worktree_at_main / MERGE_GATE),
             arguments.pull_request, arguments.head_commit,
             arguments.reviewed_since],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=environment,
            stdin=subprocess.DEVNULL)
        if (gate.returncode == 0 or MERGE_STATE_UNKNOWN_REFUSAL not in gate.stdout
                or attempt == MERGE_GATE_TRIES):
            return gate
        print(f"try {attempt}: {MERGE_STATE_UNKNOWN_REFUSAL}", flush=True)
        wait(SECONDS_BETWEEN_MERGE_GATE_TRIES)


def review_tools_worktree_not_at_main_message(worktree):
    """Return None when worktree's HEAD is origin/main after a fetch; else what to do."""
    environment = common.run_all_test_suites.environment_without_git_redirecting_variables()

    def git(*arguments):
        return subprocess.run(["git", "-C", str(worktree), *arguments], capture_output=True,
                              text=True, env=environment, stdin=subprocess.DEVNULL)

    fetch = git("fetch", "--quiet", "origin")
    if fetch.returncode != 0:
        return (f"could not fetch origin in {worktree}, so whether its merge-gate.sh is "
                f"main's cannot be told: {fetch.stderr.strip()}\n"
                f"Run this again once; if it fails the same way, tell the user this message.")
    head = git("rev-parse", "HEAD")
    main = git("rev-parse", "origin/main")
    if head.returncode != 0 or main.returncode != 0:
        return (f"could not read HEAD and origin/main in {worktree}: "
                f"{(head.stderr or main.stderr).strip()}\n"
                f"Tell the user this message.")
    if head.stdout.strip() != main.stdout.strip():
        return (f"{worktree} is at {head.stdout.strip()[:8]}, not at origin/main "
                f"{main.stdout.strip()[:8]}, so its merge-gate.sh may not be main's.\n"
                f"Move it to main: git -C {worktree} checkout --detach origin/main\n"
                f"Then run this again.")
    return None


def printed_merge_command(gate_output):
    lines = gate_output.splitlines()
    for index, line in enumerate(lines[:-1]):
        if line == MERGE_COMMAND_HEADING:
            return lines[index + 1].strip()
    return None


def stacked_pull_requests_retarget(pull_request, environment):
    """Retarget the open pull requests based on this one's branch; return an exit code."""
    view = run(["gh", "pr", "view", pull_request, "--repo", REPOSITORY,
                "--json", "headRefName,baseRefName"], environment)
    if view.returncode != 0:
        print(f"STOP: not merged: could not read pull request {pull_request}'s branch, so the "
              f"pull requests based on it could not be found: {gh_error(view)}\n"
              f"Run this again once; if it fails the same way, tell the user this message.")
        return EXIT_COULD_NOT_RUN
    branches = json.loads(view.stdout)
    branch, base = branches["headRefName"], branches["baseRefName"]

    listing = run(["gh", "pr", "list", "--repo", REPOSITORY, "--state", "open",
                   "--limit", str(OPEN_PULL_REQUEST_LIST_LIMIT),
                   "--json", "number,baseRefName"], environment)
    if listing.returncode != 0:
        print(f"STOP: not merged: could not list the open pull requests, so those based on "
              f"{branch} could not be found: {gh_error(listing)}\n"
              f"Run this again once; if it fails the same way, tell the user this message.")
        return EXIT_COULD_NOT_RUN
    stacked = sorted(entry["number"] for entry in json.loads(listing.stdout)
                     if entry["baseRefName"] == branch)
    if not stacked:
        print(f"no open pull request is based on {branch}")
        return EXIT_MERGED

    for number in stacked:
        edit = run(["gh", "pr", "edit", str(number), "--repo", REPOSITORY, "--base", base],
                   environment)
        if edit.returncode != 0:
            print(f"STOP: not merged: could not retarget pull request #{number} from {branch} "
                  f"to {base}: {gh_error(edit)}\n"
                  f"The merge deletes {branch}, and GitHub would then close #{number}.\n"
                  f"Retarget #{number} by hand: gh pr edit {number} --repo {REPOSITORY} "
                  f"--base {base}\n"
                  f"Then run this again.")
            return EXIT_COULD_NOT_RUN
        print(f"retargeted pull request #{number} from {branch} to {base}; if this merge "
              f"does not happen, set it back with: gh pr edit {number} --repo {REPOSITORY} "
              f"--base {branch}", flush=True)
    return EXIT_MERGED


def main(argv=None, wait=time.sleep):
    arguments = parse_arguments(argv)
    try:
        token = common.read_merge_account_token()
    except common.MergeAccountTokenUnusable as unusable:
        print(f"STOP: not merged: {unusable}.\n"
              f"Tell the user this message: only the user can restore the token.")
        return EXIT_COULD_NOT_RUN
    environment = {**os.environ, "GH_TOKEN": token}

    refusal = (common.review_tool_missing_message(arguments, MERGE_GATE)
               or review_tools_worktree_not_at_main_message(
                   arguments.review_tools_worktree_at_main))
    if refusal:
        print(f"STOP: not merged: {refusal}")
        return EXIT_COULD_NOT_RUN

    gate = merge_gate_after_retries(arguments, environment, wait)
    print(gate.stdout, end="" if gate.stdout.endswith("\n") or not gate.stdout else "\n")
    if gate.returncode not in MERGE_GATE_DOCUMENTED_EXITS:
        print(f"STOP: not merged: merge-gate.sh exited {gate.returncode}, a code it never "
              f"exits with on its own, so bash could not run it as written.\n"
              f"Tell the user this message, with the output above.")
        return EXIT_COULD_NOT_RUN
    if gate.returncode != 0:
        print(f"STOP: not merged: merge-gate.sh exited {gate.returncode}.\n"
              f"Follow the gate's own instructions, printed above.")
        return gate.returncode

    expected = (f"gh pr merge {arguments.pull_request} --repo {REPOSITORY} --merge "
                f"--delete-branch --match-head-commit {arguments.head_commit}")
    printed = printed_merge_command(gate.stdout)
    if printed != expected:
        print(f"STOP: not merged: merge-gate.sh and this program disagree on the merge "
              f"command, so one of them is out of date.\n"
              f"The gate printed: {printed!r}\n"
              f"This program runs only: {expected!r}\n"
              f"Do not merge, by either command.\n"
              f"Tell the user this message: only the user decides which command is right.")
        return EXIT_REFUSED

    retarget_exit = stacked_pull_requests_retarget(arguments.pull_request, environment)
    if retarget_exit != EXIT_MERGED:
        return retarget_exit

    merge = subprocess.run(expected.split(), env=environment, stdin=subprocess.DEVNULL)
    print(f"merge exit {merge.returncode}", flush=True)
    state = run(["gh", "pr", "view", arguments.pull_request, "--repo", REPOSITORY,
                 "--json", "state,mergedAt,mergeCommit",
                 "-q", "{state,mergedAt,mc:.mergeCommit.oid}"], environment)
    print(state.stdout.strip() if state.returncode == 0
          else f"could not read pull request {arguments.pull_request}'s state after the "
               f"merge: {gh_error(state)}")
    return EXIT_MERGED if merge.returncode == 0 else EXIT_REFUSED


if __name__ == "__main__":
    sys.exit(main())
