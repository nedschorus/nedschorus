#!/usr/bin/env python3
"""Tests for merge-lane-pull-request-reviewer-brief-compose-with-facts.py.

Runs the program against real git in a scratch repository that serves as
--review-tools-worktree-at-main: main, a first head commit and a fix-round head commit, with a
copy of this directory's compose-pull-request-reviewer-brief.py and an
instructions file committed on main. wt/pr7-merged is a worktree of that
repository. The program runs with GIT_DIR pointing at a directory that does
not exist, so a case passes only if the program drops it.

Run: python3 scripts/merge-lane-pull-request-reviewer-brief-compose-with-facts-test.py
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

PROGRAM = Path(__file__).with_name("merge-lane-pull-request-reviewer-brief-compose-with-facts.py")
COMPOSER = Path(__file__).with_name("compose-pull-request-reviewer-brief.py")
GIT_ENVIRONMENT = {
    **{key: value for key, value in os.environ.items() if not key.startswith("GIT_")},
    "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid",
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
}
STANDING_TEXT = "Review pull request <N>.\n<<PR-REVIEWER-INSTRUCTIONS>>\nEnd of standing text.\n"
INSTRUCTIONS = "The reviewing instructions.\n"
ADDENDUM = "The ned-box addendum.\n"

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


def commit_file(repository, path, text, message):
    (repository / path).parent.mkdir(parents=True, exist_ok=True)
    (repository / path).write_text(text)
    git(repository, "add", path)
    git(repository, "commit", "-q", "-m", message)
    return git(repository, "rev-parse", "HEAD")


def run_program(scratch, helpers, specs, *extra):
    specs_file = scratch / "brief-specs.json"
    specs_file.write_text(json.dumps(specs))
    return subprocess.run(
        [sys.executable, str(PROGRAM), str(specs_file),
         "--merge-lane-worktrees-and-outputs-directory", str(helpers),
         "--review-tools-worktree-at-main", str(scratch / "main-checkout"),
         "--brief-file", str(scratch / "standing.md"),
         "--ned-box-reviewer-brief-environment-addendum-file", str(scratch / "addendum.md"), *extra],
        capture_output=True, text=True,
        env={**GIT_ENVIRONMENT, "GIT_DIR": str(scratch / "no-such-git-directory")})


def main():
    # Resolved, because macOS's mkdtemp path is a symlink and the program resolves its paths.
    scratch = Path(tempfile.mkdtemp(prefix="merge-lane-brief-compose-test-")).resolve()
    try:
        repository = scratch / "main-checkout"
        subprocess.run(["git", "init", "-q", "-b", "main", str(repository)], check=True,
                       env=GIT_ENVIRONMENT)
        commit_file(repository, "scripts/compose-pull-request-reviewer-brief.py",
                    COMPOSER.read_text(), "composer")
        main_commit = commit_file(repository, "docs/agents/pr-reviewer-instructions.md",
                                  INSTRUCTIONS, "instructions")
        git(repository, "checkout", "-q", "-b", "topic")
        first_head = commit_file(repository, "scripts/thing.py", "one\ntwo\n", "first head")
        fix_head = commit_file(repository, "scripts/thing.py", "one\nthree\n", "fix-round")
        git(repository, "checkout", "-q", "main")
        helpers = scratch / "merge-helpers"
        git(repository, "worktree", "add", "-q", "--detach",
            str(helpers / "wt" / "pr7-merged"), fix_head)
        merged_tree = git(helpers / "wt" / "pr7-merged", "rev-parse", "HEAD^{tree}")
        (scratch / "standing.md").write_text(STANDING_TEXT)
        (scratch / "addendum.md").write_text(ADDENDUM)

        first_round = {"tag": "7", "number": 7, "title": "A title", "author": "an author",
                       "head": first_head, "main": main_commit,
                       "tests": ["scripts/thing-test.py"], "hazards": "Check the thing."}
        completed = run_program(scratch, helpers, [first_round])
        brief_file = helpers / "briefs" / "brief-7-mac-claude.md"
        expected = (
            "Review pull request 7.\nThe reviewing instructions.\nEnd of standing text.\n\n"
            "The ned-box addendum.\n\n"
            "## This pull request (facts from merge-lane-2)\n\n"
            f"- Pull request: #7, \"A title\", author `an author`.\n"
            f"- Head commit: `{first_head}`.\n"
            f"- Merge base: `{main_commit}`.\n"
            f"- Main's tip when commissioned: `{main_commit}`.\n"
            f"- Merged tree (head merged onto main by merge-lane-2): `{merged_tree}`.\n"
            f"- Your scratch directory: `{helpers / 'rv7'}`. Use it as `<your scratchpad>`.\n"
            "- Files the change touches: `scripts/thing.py` (+2/-0).\n"
            "- Test files the change touches: `scripts/thing-test.py`.\n"
            "- First round: no head commit was reviewed before.\n"
            "- Other open pull requests changing the same files: none.\n"
            "- Hazards: Check the thing.\n")
        detail = f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}"
        brief = brief_file.read_text() if brief_file.exists() else ""
        check("a first-round brief is the standing text, the addendum and the facts",
              completed.returncode == 0 and brief == expected,
              detail + "\n--- brief ---\n" + brief)
        check("the reviewer's scratch directory is made", (helpers / "rv7").is_dir(), detail)
        check("the output names the brief and its word count",
              completed.stdout == f"composed {brief_file} {len(expected.split())} words\n",
              detail)

        fix_round = {**first_round, "tag": "7r2", "head": fix_head,
                     "reviewed_before": first_head, "previous_reviews": "review 1",
                     "new_commits": "One new commit.", "answer": "fixed it",
                     "overlaps": "PR 9"}
        completed = run_program(scratch, helpers, [fix_round])
        brief_file = helpers / "briefs" / "brief-7r2-mac-claude.md"
        brief = brief_file.read_text() if brief_file.exists() else ""
        detail = (f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}"
                  f"\n--- brief ---\n{brief}")
        check("a fix-round brief names the head commit reviewed before and the answer",
              completed.returncode == 0
              and (f"- This head commit is a fix-round. Head commit reviewed before: "
                   f"`{first_head}` (review 1). One new commit.\n") in brief
              and "- The author's answer to each finding: fixed it\n" in brief, detail)
        check("a fix-round brief counts only the new commit's changes",
              "- Files the new commit touches: `scripts/thing.py` (+1/-1).\n" in brief, detail)
        check("a fix-round brief names the whole pull request's test files and the overlaps",
              "- Test files the whole pull request touches: `scripts/thing-test.py`.\n" in brief
              and "- Other open pull requests changing the same files: PR 9.\n" in brief,
              detail)

        other_instructions = scratch / "other-instructions.md"
        other_instructions.write_text("Other instructions.\n")
        completed = run_program(scratch, helpers, [first_round],
                                "--instructions-file", str(other_instructions))
        brief = (helpers / "briefs" / "brief-7-mac-claude.md").read_text()
        check("--instructions-file replaces the review tools worktree's instructions",
              completed.returncode == 0 and "Other instructions.\n" in brief
              and INSTRUCTIONS not in brief, brief)

        completed = run_program(scratch, helpers, [{**first_round, "tag": "8", "number": 8}])
        check("a pull request with no merged worktree exits 1, writing no brief",
              completed.returncode == 1 and "brief not composed" in completed.stderr
              and not (helpers / "briefs" / "brief-8-mac-claude.md").exists(),
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")

        (scratch / "standing.md").write_text("A standing text with no instructions line.\n")
        completed = run_program(scratch, helpers, [{**first_round, "tag": "9"}])
        check("a composer refusal exits 1 and names the composer's reason",
              completed.returncode == 1 and "marker lines" in completed.stderr
              and not (helpers / "briefs" / "brief-9-mac-claude.md").exists(),
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    if failures:
        print(f"\n{len(failures)} case(s) failed")
        return 1
    print("\nall cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
