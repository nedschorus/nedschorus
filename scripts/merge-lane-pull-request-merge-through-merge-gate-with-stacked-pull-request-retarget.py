#!/usr/bin/env python3
"""Merge one pull request through merge-gate.sh, retargeting the pull requests stacked on it first.

Usage:
  scripts/merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py <pull request number>
      <head commit, all 40 characters> <reviewed-since> [--token-file PATH]

Runs merge-gate.sh beside this file with the three arguments. While the gate
refuses with "mergeStateStatus is UNKNOWN", it runs the gate again, 5 seconds
apart, at most 8 times in all. When the gate passes, the merge command it
prints must be exactly the one this program expects; then every open pull
request whose base branch is this pull request's branch is retargeted to this
pull request's base branch, and the merge command runs.

The merge command deletes the pull request's branch, and GitHub closes every
open pull request whose base branch is deleted. The retarget is here, not in
merge-gate.sh, because the gate only reads GitHub and its callers may run it
without merging; a retarget belongs just before a merge that is about to run.

Every gh call runs with GH_TOKEN read from --token-file, so the retargets and
the merge are made as the merge account.

Exit codes: 0 merged; 1 the gate refused, printed a merge command other than
the expected one, or the merge failed; 2 the gate could not run, the token file
could not be read, or a read or a retarget on GitHub failed, each before any
merge.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPOSITORY = "nedschorus/nedschorus"
MERGE_GATE_SCRIPT = Path(__file__).resolve().with_name("merge-gate.sh")
DEFAULT_TOKEN_FILE = Path.home() / ".config" / "nedschorus" / "ned-review-merge.token"

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


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        description="Run merge-gate.sh for one pull request; when it passes, retarget the "
                    "open pull requests based on its branch, then run the merge command the "
                    "gate printed.")
    parser.add_argument("pull_request", help="the pull request's number")
    parser.add_argument("head_commit", help="the head commit, all 40 characters")
    parser.add_argument("reviewed_since",
                        help="the reviewed-since time merge-gate.sh takes, YYYY-MM-DDTHH:MM:SSZ")
    parser.add_argument("--token-file", type=Path, default=DEFAULT_TOKEN_FILE,
                        help=f"the merge account's GitHub token (default: {DEFAULT_TOKEN_FILE})")
    return parser.parse_args(argv)


def run(command, environment):
    return subprocess.run(command, capture_output=True, text=True, env=environment,
                          stdin=subprocess.DEVNULL)


def gh_error(completed):
    return completed.stderr.strip() or f"gh exited {completed.returncode} and printed no error"


def merge_gate_after_retries(arguments, environment, wait):
    """Return the last run of the gate, stdout and stderr together."""
    for attempt in range(1, MERGE_GATE_TRIES + 1):
        gate = subprocess.run(
            ["bash", str(MERGE_GATE_SCRIPT), arguments.pull_request, arguments.head_commit,
             arguments.reviewed_since],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=environment,
            stdin=subprocess.DEVNULL)
        if (gate.returncode == 0 or MERGE_STATE_UNKNOWN_REFUSAL not in gate.stdout
                or attempt == MERGE_GATE_TRIES):
            return gate
        print(f"try {attempt}: {MERGE_STATE_UNKNOWN_REFUSAL}", flush=True)
        wait(SECONDS_BETWEEN_MERGE_GATE_TRIES)


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
        token = arguments.token_file.read_text(encoding="utf-8").strip()
    except OSError as error:
        print(f"STOP: not merged: could not read the merge account's token at "
              f"{arguments.token_file}: {error.strerror or error}\n"
              f"Tell the user this message: only the user can restore the token.")
        return EXIT_COULD_NOT_RUN
    if not token:
        print(f"STOP: not merged: the token file {arguments.token_file} is empty.\n"
              f"Tell the user this message: only the user can restore the token.")
        return EXIT_COULD_NOT_RUN
    environment = {**os.environ, "GH_TOKEN": token}

    gate = merge_gate_after_retries(arguments, environment, wait)
    print(gate.stdout, end="" if gate.stdout.endswith("\n") or not gate.stdout else "\n")
    if gate.returncode != 0:
        print(f"STOP: merge-gate.sh exited {gate.returncode}; not merged.")
        return gate.returncode

    expected = (f"gh pr merge {arguments.pull_request} --repo {REPOSITORY} --merge "
                f"--delete-branch --match-head-commit {arguments.head_commit}")
    printed = printed_merge_command(gate.stdout)
    if printed != expected:
        print(f"STOP: not merged: the gate printed the merge command {printed!r}, and this "
              f"program runs only {expected!r}.\n"
              f"Read the gate's output above, and merge by hand only if the printed command "
              f"is right.")
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
