#!/usr/bin/env python3
"""Merge one pull request through merge-gate.sh, retargeting the pull requests stacked on it first.

Usage:
  scripts/merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py <pull request number>
      <nc-head-commit, all 40 characters> <reviewed-since>
      [--merge-lane-worktrees-and-outputs-directory DIR] [--merge-lane-review-worktrees-directory DIR] [--review-tools-worktree-at-main DIR]

Runs --review-tools-worktree-at-main's scripts/merge-gate.sh, never the pull
request's own copy, with the three arguments. While the gate
refuses with "mergeStateStatus is UNKNOWN", it runs the gate again, 5 seconds
apart, at most 8 times in all. When the gate passes, the merge command it
prints must be exactly the one this program expects; then every open pull
request whose base branch is this pull request's branch is retargeted to this
pull request's base branch, and the merge command runs. Once the merge
succeeds, git in --review-tools-worktree-at-main removes the pull request's
review worktrees, pr<n>-head and pr<n>-merged, with any changes in them; a
worktree not there is left alone.

Then main is tested where the merge changed it: the program fetches origin in
--review-tools-worktree-at-main, makes a detached worktree pr<n>-merge-commit-on-main-worktree
at the merge commit GitHub reports, and runs that worktree's own
scripts/run-all-test-suites.py --only-suites-whose-recorded-inputs-changed-since
<since>, so only the suites whose recorded inputs changed since a tested tree
run. <since> is the pr<n>-merged commit the head test run passed on: of the
records pull-request-head-test-run.py filed under hr/pr<n>/log-store in the
worktrees and outputs directory, one test log per pr<n>-merged commit, named
by its hash, the program takes each test log whose last record says it tested
that commit and exited 0, and uses the one started last. When there is no
such record, or a test log cannot be read, which the program prints, <since>
is the nc-head-commit, which predates main's newer merges and so selects more
suites, never fewer; the program prints that it fell back. The run's suite logs and test-run-report.txt go in
<merge-lane-worktrees-and-outputs-directory>/pr<n>-after-merge-test-run-logs-<the
merge commit's first 12 characters>. The program prints the run's SUMMARY line,
each failed suite's line, and that directory. Then, in that worktree, it adopts
into hr/store, the recordings every merge-lane head test run selects by, each
suite's first recording that passed and matches the merge commit's files, from
hr/pr<n>/recorded-inputs, where this pull request's head test runs saved theirs,
and then from the runner's default recorded-inputs directory, where the
after-merge test run saved its own; it prints how many it adopted. Then it
removes the worktree.

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

Exit codes: 0 merged, with the review worktrees removed, and main's after-merge
test run passed; 1 the gate refused,
printed a merge command other than the expected one, or the merge failed; 2 the token file could not be read or
was empty, --review-tools-worktree-at-main has no scripts/merge-gate.sh, could
not be fetched or is not at origin/main, the gate could not run or exited with
a code it does not document, or a read or a retarget on GitHub failed, each
before any merge; 3 merged, but a step after the merge was not done: a review
worktree or the pr<n>-merge-commit-on-main-worktree worktree could not be removed, or the
after-merge test run did not pass, because a suite failed, the runner gave no
full verdict, or the merge commit could not be read or its worktree made, or the
recordings could not be adopted; stdout names which.
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
_head_test_run_spec = importlib.util.spec_from_file_location(
    "pull_request_head_test_run", Path(__file__).resolve().with_name(
        "pull-request-head-test-run.py"))
head_test_run = importlib.util.module_from_spec(_head_test_run_spec)
_head_test_run_spec.loader.exec_module(head_test_run)

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
EXIT_MERGED_BUT_A_STEP_AFTER_THE_MERGE_NOT_DONE = 3
MERGE_GATE_DOCUMENTED_EXITS = (0, 1, 2)
MERGE_GATE = Path("scripts") / "merge-gate.sh"


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        description="Run merge-gate.sh for one pull request; when it passes, retarget the "
                    "open pull requests based on its branch, then run the merge command the "
                    "gate printed.")
    parser.add_argument("pull_request", help="the pull request's number")
    parser.add_argument("head_commit", help="the nc-head-commit, all 40 characters")
    parser.add_argument("reviewed_since",
                        help="the reviewed-since time merge-gate.sh takes, YYYY-MM-DDTHH:MM:SSZ")
    common.add_directory_options(parser, "the after-merge test runs' logs")
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


def review_worktrees_remove(arguments):
    """Remove the pull request's review worktrees; return an exit code."""
    checkout = arguments.review_tools_worktree_at_main
    exit_code = EXIT_MERGED
    for worktree in (common.pull_request_head_worktree(arguments, arguments.pull_request),
                     common.pull_request_merged_worktree(arguments, arguments.pull_request)):
        if not worktree.exists():
            continue
        removal = subprocess.run(
            ["git", "-C", str(checkout), "worktree", "remove", "--force", str(worktree)],
            capture_output=True, text=True, stdin=subprocess.DEVNULL,
            env=common.run_all_test_suites.environment_without_git_redirecting_variables())
        if removal.returncode != 0:
            print(f"STOP: merged, but the review worktree {worktree} was not removed: git "
                  f"worktree remove exited {removal.returncode}: {removal.stderr.strip()}\n"
                  f"If git names a cause you can fix, fix it and remove the worktree: "
                  f"git -C {checkout} worktree remove --force {worktree}\n"
                  f"Otherwise, tell the user this message.")
            exit_code = EXIT_MERGED_BUT_A_STEP_AFTER_THE_MERGE_NOT_DONE
            continue
        print(f"removed the review worktree {worktree}")
    return exit_code


def head_test_run_passed_merged_commit(arguments):
    """Return (the pr<n>-merged commit of the newest passing head test run record, None),
    or (None, why no record gave one)."""
    kind = (common.pull_request_head_test_run_log_store_root_directory(arguments, arguments.pull_request)
            / head_test_run.PULL_REQUEST_HEAD_TEST_RUNS_KIND_DIRECTORY_NAME)
    newest = None
    for test_log in sorted(kind.glob("*/*.txt")):
        commit = test_log.stem
        try:
            started, record = (
                head_test_run.pull_request_head_test_run_test_log_split_into_records(
                    test_log.read_text(encoding="utf-8"))[-1])
        except (OSError, UnicodeDecodeError,
                head_test_run.PullRequestHeadTestRunTestLogNotWholeRecordsError) as error:
            print(f"the head test run record {test_log} could not be read, so it is not "
                  f"used: {error}\n"
                  f"Nothing to do: without it the test run selects more suites, never fewer.")
            continue
        if not head_test_run.pull_request_head_test_run_record_passed_on_commit_check(
                record, commit):
            continue
        if newest is None or started > newest[0]:
            newest = (started, commit)
    if newest is None:
        return None, f"no readable head test run record under {kind} passed"
    return newest[1], None


def after_merge_test_run(arguments, merge_commit):
    """Run the selective test run in a fresh worktree at merge_commit; return an exit code."""
    checkout = arguments.review_tools_worktree_at_main
    since, why_not = head_test_run_passed_merged_commit(arguments)
    if since is None:
        since = arguments.head_commit
        print(f"selecting the nc-test-suites whose recorded inputs changed since the head "
              f"commit {since[:12]}, which selects more suites than "
              f"the merge changed: {why_not}.\n"
              f"Nothing to do: this run still tests every suite the merge could have changed.",
              flush=True)
    else:
        print(f"selecting the nc-test-suites whose recorded inputs changed since "
              f"{since[:12]}, the commit the head test run passed on: "
              f"pull request {arguments.pull_request}'s head merged with main as main was "
              f"when that run started", flush=True)
    by_hand = (f"python3 scripts/run-all-test-suites.py "
               f"--only-suites-whose-recorded-inputs-changed-since {since}")
    if not merge_commit:
        print(f"STOP: merged, but the merge commit could not be read, so main was not "
              f"tested.\n"
              f"Read it: gh pr view {arguments.pull_request} --repo {REPOSITORY} "
              f"--json mergeCommit\n"
              f"Then, in a detached worktree at that commit, run: {by_hand}")
        return EXIT_MERGED_BUT_A_STEP_AFTER_THE_MERGE_NOT_DONE
    environment = common.run_all_test_suites.environment_without_git_redirecting_variables()

    def git(*git_arguments):
        return subprocess.run(["git", "-C", str(checkout), *git_arguments],
                              capture_output=True, text=True, env=environment,
                              stdin=subprocess.DEVNULL)

    worktree = arguments.merge_lane_review_worktrees_directory / f"pr{arguments.pull_request}-merge-commit-on-main-worktree"
    log_dir = (arguments.merge_lane_worktrees_and_outputs_directory
               / f"pr{arguments.pull_request}-after-merge-test-run-logs-{merge_commit[:12]}")
    fetch = git("fetch", "--quiet", "origin")
    add = (git("worktree", "add", "--detach", str(worktree), merge_commit)
           if fetch.returncode == 0 else fetch)
    if add.returncode != 0:
        print(f"STOP: merged, but main was not tested: could not make a worktree at the "
              f"merge commit {merge_commit} from {checkout}: {add.stderr.strip()}\n"
              f"If git names a cause you can fix, fix it; then, in a detached worktree at "
              f"{merge_commit}, run: {by_hand}\n"
              f"Otherwise, tell the user this message.")
        return EXIT_MERGED_BUT_A_STEP_AFTER_THE_MERGE_NOT_DONE

    print(f"testing main at the merge commit {merge_commit[:12]}: the suites whose recorded "
          f"inputs changed since {since[:12]}", flush=True)
    run_all = subprocess.run(
        [sys.executable, str(worktree / "scripts" / "run-all-test-suites.py"),
         "--only-suites-whose-recorded-inputs-changed-since", since,
         "--log-dir", str(log_dir)],
        cwd=worktree, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        env=environment, stdin=subprocess.DEVNULL)
    runner = common.run_all_test_suites
    lines = run_all.stdout.splitlines()
    summaries = [line for line in lines if line.startswith(runner.SUMMARY_LINE_PREFIX)]
    for line in lines:
        if line.startswith((runner.FAILED_SUITE_LINE_PREFIX, runner.NOT_RUN_SUITE_LINE_PREFIX)):
            print(line)
    print(summaries[-1] if summaries
          else f"the test run printed no {runner.SUMMARY_LINE_PREFIX} line; its output was:\n"
               f"{run_all.stdout.rstrip()}")
    print(f"the test run's logs and test-run-report.txt: {log_dir}")
    exit_code = EXIT_MERGED
    if run_all.returncode != 0:
        print(f"STOP: merged, but the test run of main at {merge_commit} exited "
              f"{run_all.returncode}, so main may be broken; the failed suites, if any, are "
              f"listed above, each with its log.\n"
              f"Tell the pull request's author, and the user, this message.")
        exit_code = EXIT_MERGED_BUT_A_STEP_AFTER_THE_MERGE_NOT_DONE
    elif not summaries:
        print(f"STOP: merged, but the test run of main at {merge_commit} exited 0 and printed "
              f"no {runner.SUMMARY_LINE_PREFIX} line, so it gave no verdict on main.\n"
              f"In a detached worktree at {merge_commit}, run: {by_hand}\n"
              f"If that run also prints no {runner.SUMMARY_LINE_PREFIX} line, tell the user "
              f"this message.")
        exit_code = EXIT_MERGED_BUT_A_STEP_AFTER_THE_MERGE_NOT_DONE

    store = common.merge_lane_head_test_run_recorded_inputs_store_directory(arguments)
    try:
        adopted = runner.adopt_passing_recordings_that_match_the_checkout(
            worktree, store,
            [common.pull_request_head_test_run_saved_recorded_inputs_directory(
                arguments, arguments.pull_request),
             runner.DEFAULT_RECORDED_INPUTS_DIRECTORY])
    except (runner.CouldNotRun, OSError) as error:
        print(f"STOP: merged, but no recording that matches the merge commit was adopted "
              f"into {store}: {error}\n"
              f"Until a later merge adopts them, merge-lane head test runs select the suites "
              f"whose recordings in {store} are stale, and so run more suites than they need.\n"
              f"If the error names a cause you can fix, fix it; the next merge then adopts "
              f"them. Otherwise, tell the user this message.")
        exit_code = EXIT_MERGED_BUT_A_STEP_AFTER_THE_MERGE_NOT_DONE
    else:
        print(f"adopted into {store} {len(adopted)} recordings that passed and match the "
              f"merge commit")

    removal = git("worktree", "remove", "--force", str(worktree))
    if removal.returncode != 0:
        print(f"STOP: merged, but the worktree {worktree} was not removed: git worktree "
              f"remove exited {removal.returncode}: {removal.stderr.strip()}\n"
              f"If git names a cause you can fix, fix it and remove the worktree: "
              f"git -C {checkout} worktree remove --force {worktree}\n"
              f"Otherwise, tell the user this message.")
        return EXIT_MERGED_BUT_A_STEP_AFTER_THE_MERGE_NOT_DONE
    print(f"removed the worktree {worktree}")
    return exit_code


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
    if merge.returncode != 0:
        return EXIT_REFUSED
    removal_exit = review_worktrees_remove(arguments)
    # A failed read prints nothing on stdout, which json.loads refuses.
    try:
        merge_commit = json.loads(state.stdout).get("mc") or ""
    except (ValueError, AttributeError):
        merge_commit = ""
    test_exit = after_merge_test_run(arguments, merge_commit)
    return removal_exit if test_exit == EXIT_MERGED else test_exit


if __name__ == "__main__":
    sys.exit(main())
