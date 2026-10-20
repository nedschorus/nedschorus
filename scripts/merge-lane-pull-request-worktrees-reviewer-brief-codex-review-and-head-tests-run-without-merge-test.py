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

# A stand-in git that fails as a broken repository does, only when asked whether
# the trigger names a commit, and runs the real git for everything else.
FAILING_REV_PARSE_GIT = r'''#!/usr/bin/env python3
import os, sys
if sys.argv[-1] == os.environ["MERGE_LANE_RUN_WITHOUT_MERGE_TEST_GIT_TRIGGER"] + "^{commit}":
    sys.stderr.write("fatal: injected repository failure\n")
    sys.exit(128)
os.execv(os.environ["MERGE_LANE_RUN_WITHOUT_MERGE_TEST_REAL_GIT"], ["git", *sys.argv[1:]])
'''

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
                failing_exit="3", number="7", environment_changes=None):
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
             "MERGE_LANE_RUN_WITHOUT_MERGE_TEST_FAILING_STEP_EXIT": failing_exit,
             **(environment_changes or {})})
    calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return completed, calls, specifications_file


def head_of(checkout):
    return git(checkout, "rev-parse", "HEAD")


def main():
    scratch = Path(tempfile.mkdtemp(prefix="merge-lane-run-without-merge-test-")).resolve()
    try:
        checkout, main_commit, head_reviewed_before, head_commit, merge_base = (
            build_repositories(scratch))
        helpers = scratch / "merge-helpers"
        filled_in_file = (helpers / "briefs"
                          / "reviewer-brief-specifications-pr7-with-head-and-main-commits-from-origin.json")
        directory_options = ["--merge-lane-worktrees-and-outputs-directory", str(helpers),
                             "--review-tools-worktree-at-main", str(checkout)]
        first_round = {"tag": "7a", "number": 7, "title": "t", "author": "a", "tests": [],
                       "hazards": "none", "overlaps": "none"}
        fix_round = {**first_round, "reviewed_before": head_reviewed_before,
                     "previous_reviews": "one review", "new_commits": "one commit",
                     "answer": "fixed"}

        check("the review tools worktree starts behind origin's main",
              head_of(checkout) == merge_base)
        completed, calls, specifications_file = run_program(scratch, checkout, helpers,
                                                            [first_round])
        detail = f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}\n{calls}"
        check("a first round with no head or main runs all four steps in order and exits 0",
              completed.returncode == 0 and [call["step"] for call in calls] == list(STEPS),
              detail)
        check("each step gets the one head and main commit, the filled-in copy, the merge "
              "base as the Codex base, and both directory options",
              [call["argv"] for call in calls] == [
                  ["7", head_commit, main_commit, *directory_options],
                  [str(filled_in_file), *directory_options],
                  ["7", merge_base, *directory_options],
                  ["7", *directory_options]], detail)
        filled_in = json.loads(filled_in_file.read_text()) if filled_in_file.exists() else None
        check("the filled-in copy is the entry with origin's full head and main added",
              filled_in == [{**first_round, "head": head_commit, "main": main_commit}],
              f"{filled_in}")
        check("the brief specifications file given is not changed",
              json.loads(specifications_file.read_text()) == [first_round])
        check("the review tools worktree is moved to origin's main",
              head_of(checkout) == main_commit, head_of(checkout))
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
                                          "main": main_commit,
                                          "reviewed_before": head_reviewed_before[:10]}],
            "--head-commit-reviewed-before", head_reviewed_before[:12])
        detail = f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}\n{calls}"
        check("a fix-round's Codex base is the full head commit reviewed before, and "
              "abbreviated commits in the file and the option are accepted",
              completed.returncode == 0 and len(calls) == 4
              and calls[2]["argv"] == ["7", head_reviewed_before, *directory_options]
              and "(head commit reviewed before)" in completed.stdout, detail)
        filled_in = json.loads(filled_in_file.read_text())
        check("a head named in the file is replaced by its full commit in the filled-in copy",
              filled_in[0]["head"] == head_commit and filled_in[0]["main"] == main_commit,
              f"{filled_in}")
        check("an abbreviated reviewed_before is written into the filled-in copy as the full "
              "commit the Codex review runs from",
              filled_in[0]["reviewed_before"] == head_reviewed_before, f"{filled_in}")

        stand_in_directory = scratch / "failing-rev-parse-git"
        stand_in_directory.mkdir()
        (stand_in_directory / "git").write_text(FAILING_REV_PARSE_GIT)
        (stand_in_directory / "git").chmod(0o755)
        completed, calls, _ = run_program(
            scratch, checkout, helpers, [fix_round],
            "--head-commit-reviewed-before", head_reviewed_before,
            environment_changes={
                "PATH": f"{stand_in_directory}{os.pathsep}{GIT_ENVIRONMENT['PATH']}",
                "MERGE_LANE_RUN_WITHOUT_MERGE_TEST_REAL_GIT": shutil.which("git"),
                "MERGE_LANE_RUN_WITHOUT_MERGE_TEST_GIT_TRIGGER": head_reviewed_before})
        detail = f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}\n{calls}"
        check("git failing while resolving --head-commit-reviewed-before exits 2 with git's "
              "exit code and error, not as a commit missing from the checkout",
              completed.returncode == 2 and calls == []
              and "exited 128: fatal: injected repository failure" in completed.stdout
              and "is not a commit in" not in completed.stdout, detail)

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

        generic_instruction = ("If the message above names a cause you can fix, fix it and "
                               "run this again.\nOtherwise, tell the user this message.")
        correct_the_file = "Correct the file and run this again."
        file_or_flag = ("Correct whichever of the two is wrong, the file's entry or the "
                        "--head-commit-reviewed-before option, which a first round leaves out, "
                        "and run this again.")
        def rewrite_or_delete(field, commit):
            return (f"If the entry's judgments hold for {commit}, delete {field} from the "
                    f"entry, and this program fills it in.\n"
                    f"If they do not, rewrite the judgments for {commit} and delete {field} "
                    f"from the entry.\nThen run this again.")
        # The instruction each refusal over the file must end with, when not correct_the_file.
        refusal_instructions = {
            "a head that is not origin's head": rewrite_or_delete("head", head_commit),
            "a head that names no commit": rewrite_or_delete("head", head_commit),
            "a main that is not origin's main": rewrite_or_delete("main", main_commit),
            "a fix-round entry without --head-commit-reviewed-before": file_or_flag,
            "--head-commit-reviewed-before with a first-round entry": file_or_flag,
            "a reviewed_before that differs from --head-commit-reviewed-before": file_or_flag,
        }
        specification_refusals = [
            ("a head that is not origin's head", [{**first_round, "head": head_reviewed_before}],
             [], f"its head is {head_reviewed_before}, but origin's head commit is "
                 f"{head_commit}"),
            ("a main that is not origin's main", [{**first_round, "main": merge_base}], [],
             f"its main is {merge_base}, but origin's main commit is {main_commit}"),
            ("a head that names no commit", [{**first_round, "head": "no-such-commit"}], [],
             "its head is no-such-commit"),
            ("two entries", [first_round, {**first_round, "number": 8}], [],
             "exactly one entry"),
            ("an entry for another pull request", [{**first_round, "number": 8}], [],
             "its one entry is not for pull request 7"),
            ("a first-round entry with no tag or hazards",
             [{k: v for k, v in first_round.items() if k not in ("tag", "hazards")}], [],
             "its entry has no tag, hazards, which the brief step reads"),
            ("a fix-round entry without --head-commit-reviewed-before", [fix_round], [],
             "but --head-commit-reviewed-before was not given"),
            ("--head-commit-reviewed-before with a first-round entry", [first_round],
             ["--head-commit-reviewed-before", head_reviewed_before],
             "but its entry has no reviewed_before"),
            ("a fix-round entry with no previous_reviews, new_commits or answer",
             [{k: v for k, v in fix_round.items()
               if k not in ("previous_reviews", "new_commits", "answer")}],
             ["--head-commit-reviewed-before", head_reviewed_before],
             "its entry has no previous_reviews, new_commits, answer, which the brief step "
             "reads"),
            ("a fix-round entry with no answer", [{k: v for k, v in fix_round.items()
                                                    if k != "answer"}],
             ["--head-commit-reviewed-before", head_reviewed_before],
             "its entry has no answer, which the brief step reads"),
            ("a reviewed_before that differs from --head-commit-reviewed-before",
             [{**fix_round, "reviewed_before": merge_base}],
             ["--head-commit-reviewed-before", head_reviewed_before],
             f"its reviewed_before is {merge_base}, but --head-commit-reviewed-before is "
             f"{head_reviewed_before}"),
        ]
        other_refusals = [
            ("--head-commit-reviewed-before that names no commit", [fix_round],
             ["--head-commit-reviewed-before", "no-such-commit"],
             "--head-commit-reviewed-before no-such-commit is not a commit"),
            ("a brief specifications file that is not JSON", "[{not json", [],
             "could not read the brief specifications file"),
            ("a missing brief specifications file", None, [],
             "could not read the brief specifications file"),
        ]
        # Behind origin's main again, so a refusal that moved it would show.
        git(checkout, "checkout", "-q", "--detach", merge_base)
        filled_in_file.unlink()
        for name, specifications, options, expected in specification_refusals + other_refusals:
            completed, calls, _ = run_program(scratch, checkout, helpers, specifications,
                                              *options)
            check(f"{name} exits 2 before any step runs, without moving the review tools "
                  f"worktree or writing the filled-in copy",
                  completed.returncode == 2 and calls == []
                  and completed.stdout.startswith("PR 7: no step run: ")
                  and expected in completed.stdout
                  and head_of(checkout) == merge_base and not filled_in_file.exists(),
                  f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}\n{calls}")
            if (name, specifications, options, expected) in specification_refusals:
                instruction = refusal_instructions.get(name, correct_the_file)
                check(f"{name} ends with its one instruction and not the generic one",
                      completed.stdout.rstrip().endswith(instruction)
                      and generic_instruction not in completed.stdout, completed.stdout)

        completed, _, _ = run_program(scratch, checkout, helpers, [fix_round],
                                      "--head-commit-reviewed-before", "no-such-commit")
        check("a --head-commit-reviewed-before that names no commit gets its own instructions, "
              "not the generic one",
              "If the commit is right, fetch it into" in completed.stdout
              and completed.stdout.rstrip().endswith(
                  "run this again with --head-commit-reviewed-before set to the head commit "
                  "that was reviewed before.")
              and generic_instruction not in completed.stdout, completed.stdout)
        completed, _, _ = run_program(scratch, checkout, helpers, "[{not json")
        check("an unreadable brief specifications file gets the generic instruction alone",
              completed.stdout.rstrip().endswith(generic_instruction)
              and correct_the_file not in completed.stdout, completed.stdout)

        completed, calls, _ = run_program(scratch, checkout, helpers,
                                          [{**first_round, "number": 9}], number="9")
        check("a pull request origin has no head for exits 2 before any step runs, with the "
              "generic instruction",
              completed.returncode == 2 and calls == []
              and "git fetch -q origin refs/pull/9/head" in completed.stdout
              and completed.stdout.rstrip().endswith(generic_instruction),
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}\n{calls}")

        helpers.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(helpers / "briefs", ignore_errors=True)
        (helpers / "briefs").write_text("a file where the briefs directory belongs\n")
        completed, calls, _ = run_program(scratch, checkout, helpers, [first_round])
        (helpers / "briefs").unlink()
        check("a filled-in copy that cannot be written exits 2 before any step runs, without "
              "moving the review tools worktree",
              completed.returncode == 2 and calls == []
              and "could not write the brief specifications with head and main filled in"
                  in completed.stdout
              and completed.stdout.rstrip().endswith(generic_instruction)
              and head_of(checkout) == merge_base,
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}\n{calls}")

        # An untracked file where main has a tracked one makes the checkout refuse.
        in_the_way = checkout / "main-moved-on.txt"
        in_the_way.write_text("not main's content\n")
        completed, calls, _ = run_program(scratch, checkout, helpers, [first_round])
        in_the_way.unlink()
        check("a checkout that would overwrite changes in the review tools worktree exits 2 "
              "before any step runs, with the one instruction to tell the user and keep the "
              "changes, and not the generic one",
              completed.returncode == 2 and calls == []
              and f"git checkout -q --detach {main_commit} in {checkout} exited"
                  in completed.stdout
              and completed.stdout.rstrip().endswith(
                  f"Tell the user this message and wait for the user's answer. Leave the "
                  f"changes in {checkout} as they are, whatever git suggests above: do not "
                  f"move, remove, discard, stash or overwrite them, because they may be "
                  f"someone's unsaved work.")
              and generic_instruction not in completed.stdout
              and head_of(checkout) == merge_base,
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}\n{calls}")

        # A held index lock makes the checkout fail for a reason other than local changes.
        index_lock = Path(git(checkout, "rev-parse", "--absolute-git-dir")) / "index.lock"
        index_lock.write_text("")
        completed, calls, _ = run_program(scratch, checkout, helpers, [first_round])
        index_lock.unlink()
        check("a checkout that fails for another reason exits 2 with the generic instruction "
              "alone",
              completed.returncode == 2 and calls == []
              and f"git checkout -q --detach {main_commit} in {checkout} exited"
                  in completed.stdout
              and completed.stdout.rstrip().endswith(generic_instruction)
              and "leave the changes" not in completed.stdout
              and head_of(checkout) == merge_base,
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}\n{calls}")

        completed, calls, _ = run_program(scratch, scratch / "no-such-worktree", helpers,
                                          [first_round])
        check("a review tools worktree that does not exist exits 2 before git runs, with the "
              "missing-tool instructions",
              completed.returncode == 2 and calls == []
              and f"{STEPS[0]} is missing" in completed.stdout
              and "worktree add --detach" in completed.stdout
              and completed.stdout.rstrip().endswith("Then run this again.")
              and generic_instruction not in completed.stdout,
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}\n{calls}")

        completed = subprocess.run([sys.executable, str(PROGRAM), "--help"],
                                   capture_output=True, text=True, env=GIT_ENVIRONMENT)
        check("--help says runs at the same time need separate review tools worktrees",
              "Runs at the same time need separate --review-tools-worktree-at-main worktrees"
              in " ".join(completed.stdout.split()), completed.stdout)

        for step in STEPS:
            stub = checkout / "scripts" / step
            stub.rename(stub.with_suffix(".away"))
            completed, calls, _ = run_program(scratch, checkout, helpers, [first_round])
            stub.with_suffix(".away").rename(stub)
            check(f"a review tools worktree without {step} exits 2 before any step runs, "
                  f"with the missing-tool instructions and not the generic one",
                  completed.returncode == 2 and calls == []
                  and f"{step} is missing" in completed.stdout
                  and completed.stdout.rstrip().endswith("Then run this again.")
                  and generic_instruction not in completed.stdout,
                  f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}\n{calls}")

        # Last, because it moves origin's main: main gains a step script that the review
        # tools worktree's older commit lacks, so the scripts are looked for only after
        # the worktree is checked out at main.
        author = scratch / "author"
        (author / "scripts").mkdir()
        (author / "scripts" / STEPS[3]).write_text(STUB_STEP)
        git(author, "add", ".")
        git(author, "commit", "-q", "-m", "a step script on main")
        main_with_step = git(author, "rev-parse", "HEAD")
        git(author, "push", "-q", str(scratch / "origin.git"), "main:refs/heads/main")
        git(checkout, "checkout", "-q", "--detach", merge_base)
        (checkout / "scripts" / STEPS[3]).unlink()
        completed, calls, _ = run_program(scratch, checkout, helpers, [first_round])
        check("a step script that only main has is found after the worktree is moved to main, "
              "and all four steps run",
              completed.returncode == 0 and [call["step"] for call in calls] == list(STEPS)
              and head_of(checkout) == main_with_step,
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
