#!/usr/bin/env python3
"""Compose the mac-claude reviewer brief for each pull request in a JSON file of brief specifications.

Usage:
  scripts/merge-lane-pull-request-reviewer-brief-compose-with-facts.py <brief specifications file>
      [--merge-lane-worktrees-and-outputs-directory DIR] [--review-tools-worktree-at-main DIR] [--brief-file PATH]
      [--ned-box-reviewer-brief-environment-addendum-file PATH] [--instructions-file PATH]

The file holds a JSON list. Each entry has tag, number, title, author, head,
main, tests and hazards, and may have overlaps. A fix-round entry also has
reviewed_before, previous_reviews, new_commits and answer.

Each brief is three parts: the standing text, composed by --review-tools-worktree-at-main's
scripts/compose-pull-request-reviewer-brief.py with the reviewing
instructions inserted; the ned-box environment addendum; and a section of
facts, which git reads in --review-tools-worktree-at-main and in the worktrees
and outputs directory's wt/pr<n>-merged. The brief is written to
briefs/brief-<tag>-mac-claude.md under the worktrees and outputs directory, and
rv<tag>/ is made there as the reviewer's scratch directory.

Exit codes: 0 every brief written; 1 a step failed, named on stderr, and no
later brief is composed.
"""

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

DEFAULT_MERGE_LANE_WORKTREES_AND_OUTPUTS_DIRECTORY = Path(
    "/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers")
DEFAULT_BRIEF_FILE = Path(
    "/home/nedlern/agents/merge-lane-2/walk-ledgers/mac-claude-reviewer-brief-standing-text.md")
DEFAULT_NED_BOX_REVIEWER_BRIEF_ENVIRONMENT_ADDENDUM_FILE = Path(
    "/home/nedlern/agents/merge-lane-2/walk-ledgers/"
    "ned-box-reviewer-brief-environment-addendum.md")

_runner_spec = importlib.util.spec_from_file_location(
    "run_all_test_suites", Path(__file__).resolve().with_name("run-all-test-suites.py"))
run_all_test_suites = importlib.util.module_from_spec(_runner_spec)
_runner_spec.loader.exec_module(run_all_test_suites)


class StepFailed(Exception):
    pass


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        description="Compose one mac-claude reviewer brief per entry of a brief "
                    "specifications file: standing text, ned-box addendum, then facts.")
    parser.add_argument("brief_specifications_file", type=Path,
                        help="a JSON list of brief specifications")
    parser.add_argument("--merge-lane-worktrees-and-outputs-directory", type=Path,
                        default=DEFAULT_MERGE_LANE_WORKTREES_AND_OUTPUTS_DIRECTORY,
                        help=f"holds wt/; the briefs and scratch directories are written there "
                             f"(default: {DEFAULT_MERGE_LANE_WORKTREES_AND_OUTPUTS_DIRECTORY})")
    parser.add_argument("--review-tools-worktree-at-main", type=Path,
                        help="the checkout at main whose composer and reviewing instructions "
                             "are used (default: <merge-lane-worktrees-and-outputs-directory>/wt/main)")
    parser.add_argument("--brief-file", type=Path, default=DEFAULT_BRIEF_FILE,
                        help=f"the brief's standing text (default: {DEFAULT_BRIEF_FILE})")
    parser.add_argument("--ned-box-reviewer-brief-environment-addendum-file", type=Path,
                        default=DEFAULT_NED_BOX_REVIEWER_BRIEF_ENVIRONMENT_ADDENDUM_FILE,
                        help=f"the ned-box environment addendum "
                             f"(default: {DEFAULT_NED_BOX_REVIEWER_BRIEF_ENVIRONMENT_ADDENDUM_FILE})")
    parser.add_argument("--instructions-file", type=Path,
                        help="the reviewing instructions inserted into the standing text "
                             "(default: <review-tools-worktree-at-main>/docs/agents/pr-reviewer-instructions.md)")
    return parser.parse_args(argv)


def run(command):
    completed = subprocess.run(
        command, capture_output=True, text=True, stdin=subprocess.DEVNULL,
        env=run_all_test_suites.environment_without_git_redirecting_variables())
    if completed.returncode != 0:
        raise StepFailed(f"{' '.join(command)} exited {completed.returncode}: "
                         f"{completed.stderr.strip()}")
    return completed.stdout


def git(directory, *arguments):
    return run(["git", "-C", str(directory), *arguments]).strip()


def numstat(review_tools_worktree, base, head):
    rows = []
    for line in git(review_tools_worktree, "diff", "--numstat", base, head).splitlines():
        added, removed, path = line.split("\t")
        rows.append((path, added, removed))
    return rows


def compose(spec, arguments, review_tools_worktree, instructions_file):
    tag, number = spec["tag"], spec["number"]
    head, main = spec["head"], spec["main"]
    helpers = arguments.merge_lane_worktrees_and_outputs_directory
    merge_base = git(review_tools_worktree, "merge-base", main, head)
    merged_tree = git(helpers / "wt" / f"pr{number}-merged", "rev-parse", "HEAD^{tree}")
    standing = run([sys.executable,
                    str(review_tools_worktree / "scripts" / "compose-pull-request-reviewer-brief.py"),
                    "--pull-request", str(number),
                    "--brief-file", str(arguments.brief_file),
                    "--instructions-file", str(instructions_file)])
    scratch = helpers / f"rv{tag}"
    scratch.mkdir(parents=True, exist_ok=True)
    facts = ["## This pull request (facts from merge-lane-2)", "",
             f"- Pull request: #{number}, \"{spec['title']}\", author `{spec['author']}`.",
             f"- Head commit: `{head}`.",
             f"- Merge base: `{merge_base}`.",
             f"- Main's tip when commissioned: `{main}`.",
             f"- Merged tree (head merged onto main by merge-lane-2): `{merged_tree}`.",
             f"- Your scratch directory: `{scratch}`. Use it as `<your scratchpad>`."]
    if "reviewed_before" in spec:
        rows = numstat(review_tools_worktree, spec["reviewed_before"], head)
        facts.append(f"- This head commit is a fix-round. Head commit reviewed before: "
                     f"`{spec['reviewed_before']}` ({spec['previous_reviews']}). "
                     f"{spec['new_commits']}")
        facts.append("- Files the new commit touches: "
                     + ", ".join(f"`{p}` (+{a}/-{r})" for p, a, r in rows) + ".")
        facts.append(f"- The author's answer to each finding: {spec['answer']}")
        facts.append("- Test files the whole pull request touches: "
                     + ", ".join(f"`{t}`" for t in spec["tests"]) + ".")
    else:
        rows = numstat(review_tools_worktree, merge_base, head)
        facts.append("- Files the change touches: "
                     + ", ".join(f"`{p}` (+{a}/-{r})" for p, a, r in rows) + ".")
        facts.append("- Test files the change touches: "
                     + ", ".join(f"`{t}`" for t in spec["tests"]) + ".")
        facts.append("- First round: no head commit was reviewed before.")
    facts.append("- Other open pull requests changing the same files: "
                 + spec.get("overlaps", "none") + ".")
    facts.append(f"- Hazards: {spec['hazards']}")
    addendum = arguments.ned_box_reviewer_brief_environment_addendum_file.read_text()
    brief = (standing.rstrip("\n") + "\n\n" + addendum.rstrip("\n") + "\n\n"
             + "\n".join(facts) + "\n")
    out = helpers / "briefs" / f"brief-{tag}-mac-claude.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(brief)
    print("composed", out, len(brief.split()), "words")


def main(argv=None):
    arguments = parse_arguments(argv)
    review_tools_worktree = (arguments.review_tools_worktree_at_main
                     or arguments.merge_lane_worktrees_and_outputs_directory / "wt" / "main")
    instructions_file = (arguments.instructions_file
                         or review_tools_worktree / "docs" / "agents" / "pr-reviewer-instructions.md")
    try:
        specs = json.loads(arguments.brief_specifications_file.read_text())
        for spec in specs:
            compose(spec, arguments, review_tools_worktree, instructions_file)
    except (StepFailed, OSError, ValueError, KeyError) as failure:
        print(f"brief not composed: {type(failure).__name__}: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
