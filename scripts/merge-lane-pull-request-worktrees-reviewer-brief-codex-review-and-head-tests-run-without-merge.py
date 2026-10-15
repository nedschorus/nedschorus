#!/usr/bin/env python3
"""Run the four merge-lane steps that come before a pull request's review, and stop at the first that fails.

Usage:
  scripts/merge-lane-pull-request-worktrees-reviewer-brief-codex-review-and-head-tests-run-without-merge.py
      <pull request number> <brief specifications file> [--head-commit-reviewed-before COMMIT]
      [--merge-lane-worktrees-and-outputs-directory DIR] [--review-tools-worktree-at-main DIR]

Before any step runs, git in --review-tools-worktree-at-main fetches main and
refs/pull/<n>/head from origin and reads the two commits once. The Codex
review's base is the merge base of those two commits, or, for a fix-round,
the commit given as --head-commit-reviewed-before. The brief specifications
file must hold exactly one entry, for this pull request, whose head and main
name those same commits, and whose reviewed_before is present exactly when
--head-commit-reviewed-before is given, naming the same commit.

Then each step runs from --review-tools-worktree-at-main's scripts/, never
the pull request's, with those commits and both directory options:
  1. merge-lane-pull-request-head-and-merged-worktrees-rebuild.py <n> <head> <main>
  2. merge-lane-pull-request-reviewer-brief-compose-with-facts.py <brief specifications file>
  3. merge-lane-code-review-codex-cell-run-on-pull-request-head.py <n> <base>
  4. merge-lane-pull-request-head-test-run-on-merged-worktree.py <n>
Each step's own output passes straight through. The steps run one after
another, so nothing here waits on a process. Nothing here merges: merging is
merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py.

Exit codes: 0 all four steps exited 0; 1 a step exited nonzero, named on
stdout, and no later step ran; 2 refused before any step ran: a step script
is missing, git could not fetch or read a commit, or the brief specifications
file is unreadable or disagrees with the commits, named on stdout.
"""

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

WORKTREES_REBUILD_STEP = "merge-lane-pull-request-head-and-merged-worktrees-rebuild.py"
REVIEWER_BRIEF_STEP = "merge-lane-pull-request-reviewer-brief-compose-with-facts.py"
CODEX_REVIEW_STEP = "merge-lane-code-review-codex-cell-run-on-pull-request-head.py"
HEAD_TEST_RUN_STEP = "merge-lane-pull-request-head-test-run-on-merged-worktree.py"
STEPS = (WORKTREES_REBUILD_STEP, REVIEWER_BRIEF_STEP, CODEX_REVIEW_STEP, HEAD_TEST_RUN_STEP)

_common_spec = importlib.util.spec_from_file_location(
    "merge_lane_pull_request_helpers_common", Path(__file__).resolve().with_name(
        "merge-lane-pull-request-helpers-common-options-paths-and-token.py"))
common = importlib.util.module_from_spec(_common_spec)
_common_spec.loader.exec_module(common)
run_all_test_suites = common.run_all_test_suites


class RefusedBeforeAnyStep(Exception):
    pass


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        description="Rebuild a pull request's worktrees, compose its reviewer brief, run the "
                    "Codex review and run the head tests, stopping at the first step that "
                    "fails. Does not merge.")
    parser.add_argument("pull_request", type=int, help="the pull request's number")
    parser.add_argument("brief_specifications_file", type=Path,
                        help="the JSON brief specifications file for this pull request, "
                             "as merge-lane-pull-request-reviewer-brief-compose-with-facts.py "
                             "reads it")
    parser.add_argument("--head-commit-reviewed-before",
                        help="for a fix-round, the head commit reviewed before; the Codex "
                             "review runs from it instead of from the merge base")
    common.add_directory_options(parser, "wt/, briefs/, cx/, hr/ and tripwire-bin/")
    return common.resolve_path_options(parser.parse_args(argv))


def git(directory, *arguments):
    completed = subprocess.run(
        ["git", "-C", str(directory), *arguments], capture_output=True, text=True,
        stdin=subprocess.DEVNULL,
        env=run_all_test_suites.environment_without_git_redirecting_variables())
    if completed.returncode != 0:
        raise RefusedBeforeAnyStep(
            f"git {' '.join(arguments)} in {directory} exited {completed.returncode}: "
            f"{completed.stderr.strip()}")
    return completed.stdout.strip()


def fetched_commit(checkout, reference):
    # One reference per fetch, so FETCH_HEAD names that reference's commit alone.
    git(checkout, "fetch", "-q", "origin", reference)
    return git(checkout, "rev-parse", "--verify", "FETCH_HEAD^{commit}")


def resolved_commit(checkout, commit):
    """Return commit's full name, or None when the checkout has no such commit."""
    try:
        return git(checkout, "rev-parse", "--verify", f"{commit}^{{commit}}")
    except RefusedBeforeAnyStep:
        return None


def brief_specification_disagreement(checkout, specifications, number, head, main,
                                     head_reviewed_before):
    """Return what is wrong with the brief specifications for these commits, or None."""
    if not isinstance(specifications, list) or len(specifications) != 1:
        return (f"it must hold a JSON list of exactly one entry, for pull request {number}, "
                f"because the brief step composes a brief for every entry")
    entry = specifications[0]
    if not isinstance(entry, dict) or entry.get("number") != number:
        return f"its one entry is not for pull request {number}"
    for field, commit in (("head", head), ("main", main)):
        if field not in entry:
            return f"its entry has no {field}; write {commit}"
        if resolved_commit(checkout, str(entry[field])) != commit:
            return (f"its {field} is {entry[field]}, but origin's {field} commit is {commit}; "
                    f"write {commit} if the facts in the entry hold for that commit")
    if head_reviewed_before is None and "reviewed_before" in entry:
        return (f"its entry is a fix-round, with reviewed_before {entry['reviewed_before']}, "
                f"but --head-commit-reviewed-before was not given, so the Codex review would "
                f"run from the merge base")
    if head_reviewed_before is not None:
        if "reviewed_before" not in entry:
            return (f"--head-commit-reviewed-before {head_reviewed_before} makes this a "
                    f"fix-round, but its entry has no reviewed_before, previous_reviews, "
                    f"new_commits or answer, so the brief would describe a first round")
        if resolved_commit(checkout, str(entry["reviewed_before"])) != head_reviewed_before:
            return (f"its reviewed_before is {entry['reviewed_before']}, but "
                    f"--head-commit-reviewed-before is {head_reviewed_before}")
    return None


def run_step(position, step, arguments, step_arguments):
    command = [sys.executable, str(arguments.review_tools_worktree_at_main / "scripts" / step),
               *step_arguments,
               "--merge-lane-worktrees-and-outputs-directory",
               str(arguments.merge_lane_worktrees_and_outputs_directory),
               "--review-tools-worktree-at-main", str(arguments.review_tools_worktree_at_main)]
    print(f"step {position} of {len(STEPS)}: {step}", flush=True)
    return subprocess.run(
        command, stdin=subprocess.DEVNULL,
        env=run_all_test_suites.environment_without_git_redirecting_variables()).returncode


def main(argv=None):
    arguments = parse_arguments(argv)
    number = arguments.pull_request
    checkout = arguments.review_tools_worktree_at_main
    try:
        for step in STEPS:
            missing = common.review_tool_missing_message(arguments, Path("scripts") / step)
            if missing:
                raise RefusedBeforeAnyStep(missing)
        main_commit = fetched_commit(checkout, "refs/heads/main")
        head_commit = fetched_commit(checkout, f"refs/pull/{number}/head")
        head_reviewed_before = None
        if arguments.head_commit_reviewed_before is not None:
            head_reviewed_before = resolved_commit(checkout, arguments.head_commit_reviewed_before)
            if head_reviewed_before is None:
                raise RefusedBeforeAnyStep(
                    f"--head-commit-reviewed-before {arguments.head_commit_reviewed_before} "
                    f"is not a commit in {checkout}.\n"
                    f"If the commit is right, fetch it into {checkout} and run this again.")
            base, base_kind = head_reviewed_before, "head commit reviewed before"
        else:
            base, base_kind = git(checkout, "merge-base", main_commit, head_commit), "merge base"
        try:
            specifications = json.loads(arguments.brief_specifications_file.read_text())
        except (OSError, ValueError) as failure:
            raise RefusedBeforeAnyStep(
                f"could not read the brief specifications file "
                f"{arguments.brief_specifications_file}: {failure}") from failure
        disagreement = brief_specification_disagreement(
            checkout, specifications, number, head_commit, main_commit, head_reviewed_before)
        if disagreement:
            raise RefusedBeforeAnyStep(
                f"the brief specifications file {arguments.brief_specifications_file} does "
                f"not match the commits: {disagreement}.\n"
                f"Correct the file and run this again.")
    except RefusedBeforeAnyStep as refusal:
        print(f"PR {number}: no step run: {refusal}\n"
              f"If the message above names a cause you can fix, fix it and run this again.\n"
              f"Otherwise, tell the user this message.", flush=True)
        return 2

    print(f"PR {number}: head {head_commit}, main {main_commit}, Codex review base {base} "
          f"({base_kind})", flush=True)
    steps = ((WORKTREES_REBUILD_STEP, [str(number), head_commit, main_commit]),
             (REVIEWER_BRIEF_STEP, [str(arguments.brief_specifications_file)]),
             (CODEX_REVIEW_STEP, [str(number), base]),
             (HEAD_TEST_RUN_STEP, [str(number)]))
    for position, (step, step_arguments) in enumerate(steps, start=1):
        exit_code = run_step(position, step, arguments, step_arguments)
        if exit_code != 0:
            print(f"PR {number}: stopped at step {position} of {len(STEPS)}, {step}, which "
                  f"exited {exit_code}; no later step ran, and nothing was merged.\n"
                  f"Act on that step's own message, printed above.\n"
                  f"If that message says to run the step again, run this program again "
                  f"instead, so every step uses the same commits.", flush=True)
            return 1
    print(f"PR {number}: all {len(STEPS)} steps exited 0; nothing was merged.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
