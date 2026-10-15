#!/usr/bin/env python3
"""Tests for merge-lane-pull-request-worktrees-reviewer-brief-codex-review-and-head-tests-run-without-merge.py.

Real git in a scratch directory: a bare origin holding main and a pull
request's head at refs/pull/7/head, as GitHub keeps it, and a clone of that
origin as the --review-tools-worktree-at-main. The clone's scripts/ holds a
stub for each of the four steps, which logs its arguments and exits with the
code the case gives it, so no worktree is built, no Codex runs and no network
is used. The program runs with GIT_DIR pointing at a directory that does not
exist, so a case passes only if the program drops the variables that
redirect git.

Run: python3 scripts/merge-lane-pull-request-worktrees-reviewer-brief-codex-review-and-head-tests-run-without-merge-test.py
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().with_name(
        "git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

PROGRAM = Path(__file__).with_name(
    "merge-lane-pull-request-worktrees-reviewer-brief-codex-review-and-head-tests-run-without-merge.py")
STEPS = ("merge-lane-pull-request-head-and-merged-worktrees-rebuild.py",
         "merge-lane-pull-request-reviewer-brief-compose-with-facts.py",
         "merge-lane-code-review-codex-cell-run-on-pull-request-head.py",
         "merge-lane-pull-request-head-test-run-on-merged-worktree.py")
GIT_ENVIRONMENT = {
    **{key: value for key, value in os.environ.items() if not key.startswith("GIT_")},
    "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid",
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
}

STUB_STEP = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
step = Path(__file__).name
with open(os.environ["MERGE_LANE_RUN_WITHOUT_MERGE_TEST_STEP_LOG"], "a") as log:
    log.write(json.dumps({"step": step, "argv": sys.argv[1:],
                          "git_dir": os.environ.get("GIT_DIR")}) + "\n")
print(step + " stub output")
sys.exit(int(os.environ.get("MERGE_LANE_RUN_WITHOUT_MERGE_TEST_FAILING_STEP_EXIT", "0"))
         if os.environ.get("MERGE_LANE_RUN_WITHOUT_MERGE_TEST_FAILING_STEP") == step else 0)
'''

failures = []


def check(name, condition, detail=""):
    print(("PASS  " if condition else "FAIL  ") + name)
    if not condition:
        failures.append(name)
        if detail:
            print("      " + detail.replace("\n", "\n      "))


def git(directory, *arguments):
    return subprocess.run(["git", "-C", str(directory), *arguments], capture_output=True,
                          text=True, check=True, env=GIT_ENVIRONMENT).stdout.strip()


def commit_file(repository, name):
    (repository / name).write_text(name + "\n")
    git(repository, "add", ".")
    git(repository, "commit", "-q", "-m", name)
    return git(repository, "rev-parse", "HEAD")


def build_repositories(scratch):
    """Return (checkout, main commit, head commit reviewed before, head commit, merge base)."""
    origin = scratch / "origin.git"
    author = scratch / "author"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True,
                   env=GIT_ENVIRONMENT)
    subprocess.run(["git", "init", "-q", "-b", "main", str(author)], check=True,
                   env=GIT_ENVIRONMENT)
    merge_base = commit_file(author, "base.txt")
    git(author, "checkout", "-q", "-b", "topic")
    head_reviewed_before = commit_file(author, "topic-round-1.txt")
    git(author, "push", "-q", str(origin), "main:refs/heads/main", "topic:refs/pull/7/head")
    checkout = scratch / "checkout"
    subprocess.run(["git", "clone", "-q", str(origin), str(checkout)], check=True,
                   env=GIT_ENVIRONMENT)
    # The checkout fetched the earlier head commit in the earlier round.
    git(checkout, "fetch", "-q", "origin", "refs/pull/7/head")
    head_commit = commit_file(author, "topic-round-2.txt")
    git(author, "checkout", "-q", "main")
    main_commit = commit_file(author, "main-moved-on.txt")
    git(author, "push", "-q", "--force", str(origin), "main:refs/heads/main",
        "topic:refs/pull/7/head")
    (checkout / "scripts").mkdir()
    for step in STEPS:
        (checkout / "scripts" / step).write_text(STUB_STEP)
    return checkout, main_commit, head_reviewed_before, head_commit, merge_base


def run_program(scratch, checkout, helpers, specifications, *options, failing_step=None,
                failing_exit="3", number="7"):
    log = scratch / "steps.log"
    log.unlink(missing_ok=True)
    specifications_file = scratch / "brief-specifications.json"
    if isinstance(specifications, str):
        specifications_file.write_text(specifications)
    elif specifications is None:
        specifications_file.unlink(missing_ok=True)
    else:
        specifications_file.write_text(json.dumps(specifications))
    completed = subprocess.run(
        [sys.executable, str(PROGRAM), number, str(specifications_file), *options,
         "--merge-lane-worktrees-and-outputs-directory", str(helpers),
         "--review-tools-worktree-at-main", str(checkout)],
        capture_output=True, text=True,
        env={**{key: value for key, value in GIT_ENVIRONMENT.items()
                if not key.startswith(("GIT_AUTHOR_", "GIT_COMMITTER_"))},
             "GIT_DIR": str(scratch / "no-such-git-directory"),
             "MERGE_LANE_RUN_WITHOUT_MERGE_TEST_STEP_LOG": str(log),
             "MERGE_LANE_RUN_WITHOUT_MERGE_TEST_FAILING_STEP": failing_step or "",
             "MERGE_LANE_RUN_WITHOUT_MERGE_TEST_FAILING_STEP_EXIT": failing_exit})
    calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return completed, calls, specifications_file


def main():
    scratch = Path(tempfile.mkdtemp(prefix="merge-lane-run-without-merge-test-")).resolve()
    try:
        checkout, main_commit, head_reviewed_before, head_commit, merge_base = (
            build_repositories(scratch))
        helpers = scratch / "merge-helpers"
        directory_options = ["--merge-lane-worktrees-and-outputs-directory", str(helpers),
                             "--review-tools-worktree-at-main", str(checkout)]
        first_round = {"tag": "7a", "number": 7, "title": "t", "author": "a",
                       "head": head_commit, "main": main_commit, "tests": [], "hazards": "none"}
        fix_round = {**first_round, "reviewed_before": head_reviewed_before,
                     "previous_reviews": "one review", "new_commits": "one commit",
                     "answer": "fixed"}

        completed, calls, specifications_file = run_program(scratch, checkout, helpers,
                                                            [first_round])
        detail = f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}\n{calls}"
        check("a first round runs all four steps in order and exits 0",
              completed.returncode == 0 and [call["step"] for call in calls] == list(STEPS),
              detail)
        check("each step gets the one head and main commit, the merge base as the Codex "
              "base, and both directory options",
              [call["argv"] for call in calls] == [
                  ["7", head_commit, main_commit, *directory_options],
                  [str(specifications_file), *directory_options],
                  ["7", merge_base, *directory_options],
                  ["7", *directory_options]], detail)
        check("GIT_DIR does not reach the steps",
              all(call["git_dir"] is None for call in calls), detail)
        check("the output names the commits, passes each step's output through and says "
              "nothing was merged",
              f"PR 7: head {head_commit}, main {main_commit}, Codex review base {merge_base} "
              f"(merge base)" in completed.stdout
              and all(f"{step} stub output" in completed.stdout for step in STEPS)
              and completed.stdout.rstrip().endswith(
                  "PR 7: all 4 steps exited 0; nothing was merged."), detail)

        completed, calls, _ = run_program(
            scratch, checkout, helpers, [{**fix_round, "head": head_commit[:10],
                                          "reviewed_before": head_reviewed_before[:10]}],
            "--head-commit-reviewed-before", head_reviewed_before[:12])
        detail = f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}\n{calls}"
        check("a fix-round's Codex base is the full head commit reviewed before, and "
              "abbreviated commits in the file and the option are accepted",
              completed.returncode == 0 and len(calls) == 4
              and calls[2]["argv"] == ["7", head_reviewed_before, *directory_options]
              and "(head commit reviewed before)" in completed.stdout, detail)

        for position, step in enumerate(STEPS, start=1):
            completed, calls, _ = run_program(scratch, checkout, helpers, [first_round],
                                              failing_step=step, failing_exit="5")
            detail = f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}\n{calls}"
            check(f"step {position} failing stops the run there, names the step and its exit "
                  f"code, and exits 1",
                  completed.returncode == 1
                  and [call["step"] for call in calls] == list(STEPS[:position])
                  and f"PR 7: stopped at step {position} of 4, {step}, which exited 5; "
                      f"no later step ran, and nothing was merged." in completed.stdout,
                  detail)

        refusals = [
            ("a head that is not origin's head", [{**first_round, "head": head_reviewed_before}],
             [], f"its head is {head_reviewed_before}, but origin's head commit is "
                 f"{head_commit}"),
            ("a main that is not origin's main", [{**first_round, "main": merge_base}], [],
             f"its main is {merge_base}, but origin's main commit is {main_commit}"),
            ("an entry with no head", [{k: v for k, v in first_round.items() if k != "head"}],
             [], f"its entry has no head; write {head_commit}"),
            ("a head that names no commit", [{**first_round, "head": "no-such-commit"}], [],
             "its head is no-such-commit"),
            ("two entries", [first_round, {**first_round, "number": 8}], [],
             "exactly one entry"),
            ("an entry for another pull request", [{**first_round, "number": 8}], [],
             "its one entry is not for pull request 7"),
            ("a fix-round entry without --head-commit-reviewed-before", [fix_round], [],
             "but --head-commit-reviewed-before was not given"),
            ("--head-commit-reviewed-before with a first-round entry", [first_round],
             ["--head-commit-reviewed-before", head_reviewed_before],
             "but its entry has no reviewed_before"),
            ("a reviewed_before that differs from --head-commit-reviewed-before",
             [{**fix_round, "reviewed_before": merge_base}],
             ["--head-commit-reviewed-before", head_reviewed_before],
             f"its reviewed_before is {merge_base}, but --head-commit-reviewed-before is "
             f"{head_reviewed_before}"),
            ("--head-commit-reviewed-before that names no commit", [fix_round],
             ["--head-commit-reviewed-before", "no-such-commit"],
             "--head-commit-reviewed-before no-such-commit is not a commit"),
            ("a brief specifications file that is not JSON", "[{not json", [],
             "could not read the brief specifications file"),
            ("a missing brief specifications file", None, [],
             "could not read the brief specifications file"),
        ]
        for name, specifications, options, expected in refusals:
            completed, calls, _ = run_program(scratch, checkout, helpers, specifications,
                                              *options)
            check(f"{name} exits 2 before any step runs",
                  completed.returncode == 2 and calls == []
                  and completed.stdout.startswith("PR 7: no step run: ")
                  and expected in completed.stdout,
                  f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}\n{calls}")

        completed, calls, _ = run_program(scratch, checkout, helpers,
                                          [{**first_round, "number": 9}], number="9")
        check("a pull request origin has no head for exits 2 before any step runs",
              completed.returncode == 2 and calls == []
              and "git fetch -q origin refs/pull/9/head" in completed.stdout,
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}\n{calls}")

        for step in STEPS:
            stub = checkout / "scripts" / step
            stub.rename(stub.with_suffix(".away"))
            completed, calls, _ = run_program(scratch, checkout, helpers, [first_round])
            stub.with_suffix(".away").rename(stub)
            check(f"a review tools worktree without {step} exits 2 before any step runs",
                  completed.returncode == 2 and calls == []
                  and f"{step} is missing" in completed.stdout,
                  f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}\n{calls}")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    if failures:
        print(f"\n{len(failures)} case(s) failed")
        return 1
    print("\nall cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
