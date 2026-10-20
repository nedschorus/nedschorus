#!/usr/bin/env python3
"""Compose the mac-claude reviewer brief for each pull request in a JSON file of brief specifications.

Usage:
  scripts/merge-lane-pull-request-reviewer-brief-compose-with-facts.py <brief specifications file>
      [--merge-lane-worktrees-and-outputs-directory DIR] [--review-tools-worktree-at-main DIR] [--brief-file PATH]
      [--ned-box-reviewer-brief-environment-addendum-file PATH] [--instructions-file PATH]
      [--merge-lane-pull-request-reviewer-scratch-directories-parent-directory DIR]

The file holds a JSON list. Each entry has tag, number, title, author, head,
main, tests and hazards, and may have overlaps. A fix-round entry also has
reviewed_before, previous_reviews, new_commits and answer.

The pull request's author is read from GitHub with gh. When it is
ned-review-merge, the facts tell the reviewer to post its verdict as the
review's event, in place of the standing text's COMMENT.

Each brief is three parts: the standing text, composed by --review-tools-worktree-at-main's
scripts/compose-pull-request-reviewer-brief.py with the reviewing
instructions inserted; the ned-box environment addendum; and a section of
facts, which git reads in --review-tools-worktree-at-main and in the worktrees
and outputs directory's wt/pr<n>-merged. The brief is written to
briefs/brief-<tag>-mac-claude.md under the worktrees and outputs directory, and
rv<tag>/ is made under --merge-lane-pull-request-reviewer-scratch-directories-parent-directory as the reviewer's
scratch directory. That parent is outside the log-store, because the standing
text forbids the reviewer to write to the log-store.

Exit codes: 0 every brief written; 1 a step failed, named on stderr, and no
later brief is composed.
"""

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

DEFAULT_BRIEF_FILE = Path(
    "/home/nedlern/agents/merge-lane-2/walk-ledgers/mac-claude-reviewer-brief-standing-text.md")
DEFAULT_NED_BOX_REVIEWER_BRIEF_ENVIRONMENT_ADDENDUM_FILE = Path(
    "/home/nedlern/agents/merge-lane-2/walk-ledgers/"
    "ned-box-reviewer-brief-environment-addendum.md")
DEFAULT_MERGE_LANE_PULL_REQUEST_REVIEWER_SCRATCH_DIRECTORIES_PARENT_DIRECTORY = Path(
    "/home/nedlern/.cache/merge-lane-pull-request-reviewer-scratch-directories")

_common_spec = importlib.util.spec_from_file_location(
    "merge_lane_pull_request_helpers_common", Path(__file__).resolve().with_name(
        "merge-lane-pull-request-helpers-common-options-paths-and-token.py"))
common = importlib.util.module_from_spec(_common_spec)
_common_spec.loader.exec_module(common)
run_all_test_suites = common.run_all_test_suites
_git_output_spec = importlib.util.spec_from_file_location(
    "git_machine_readable_output_runner_and_parser_common",
    Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
    / "git-machine-readable-output-runner-and-parser-common.py")
git_output = importlib.util.module_from_spec(_git_output_spec)
_git_output_spec.loader.exec_module(git_output)


MERGE_LANE_ACCOUNT = "ned-review-merge"
# GitHub refuses an approving review from a pull request's own author, so on a pull request
# merge-lane-2 opened as MERGE_LANE_ACCOUNT the reviewer's review is the only approval it can get.
POST_VERDICT_AS_REVIEW_EVENT_LINE = (
    f"- This pull request's author is `{MERGE_LANE_ACCOUNT}`, the account merge-lane-2 approves "
    f"with, and GitHub refuses an approving review from a pull request's author. So post your "
    f"review with `event` set to your verdict, `APPROVE` or `REQUEST_CHANGES`, in place of "
    f"`COMMENT`, and still put the verdict as the body's first line.")


class StepFailed(Exception):
    pass


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        description="Compose one mac-claude reviewer brief per entry of a brief "
                    "specifications file: standing text, ned-box addendum, then facts.")
    parser.add_argument("brief_specifications_file", type=Path,
                        help="a JSON list of brief specifications")
    common.add_directory_options(parser, "wt/; the briefs are written there")
    parser.add_argument("--brief-file", type=Path, default=DEFAULT_BRIEF_FILE,
                        help=f"the brief's standing text (default: {DEFAULT_BRIEF_FILE})")
    parser.add_argument("--ned-box-reviewer-brief-environment-addendum-file", type=Path,
                        default=DEFAULT_NED_BOX_REVIEWER_BRIEF_ENVIRONMENT_ADDENDUM_FILE,
                        help=f"the ned-box environment addendum "
                             f"(default: {DEFAULT_NED_BOX_REVIEWER_BRIEF_ENVIRONMENT_ADDENDUM_FILE})")
    parser.add_argument("--instructions-file", type=Path,
                        help="the reviewing instructions inserted into the standing text "
                             "(default: <review-tools-worktree-at-main>/docs/agents/pr-reviewer-instructions.md)")
    parser.add_argument("--merge-lane-pull-request-reviewer-scratch-directories-parent-directory", type=Path,
                        default=DEFAULT_MERGE_LANE_PULL_REQUEST_REVIEWER_SCRATCH_DIRECTORIES_PARENT_DIRECTORY,
                        help=f"the directory in which each reviewer's scratch directory rv<tag>/ is made, "
                             f"<tag> being the tag field of that pull request's entry in the brief "
                             f"specifications file, such as 1630 or 1630r1 "
                             f"(default: {DEFAULT_MERGE_LANE_PULL_REQUEST_REVIEWER_SCRATCH_DIRECTORIES_PARENT_DIRECTORY})")
    return common.resolve_path_options(parser.parse_args(argv))


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


def pull_request_author(number):
    return run(["gh", "pr", "view", str(number), "--repo", common.REPOSITORY,
                "--json", "author", "--jq", ".author.login"]).strip()


def files_touched_text(review_tools_worktree, base, head):
    """The files changed between base and head, each with its line counts, for the brief."""
    entries = git_output.numstat_entries(
        run(["git", "-C", str(review_tools_worktree), "diff", "-z", "--numstat", base, head]))
    texts = []
    for entry in entries:
        counts = ("binary" if entry.added is None
                  else f"+{entry.added}/-{entry.deleted}")
        if entry.origin_path is not None:
            texts.append(f"`{entry.path}` (renamed from `{entry.origin_path}`, {counts})")
        else:
            texts.append(f"`{entry.path}` ({counts})")
    return ", ".join(texts)


def compose(spec, arguments, review_tools_worktree, instructions_file):
    tag, number = spec["tag"], spec["number"]
    head, main = spec["head"], spec["main"]
    helpers = arguments.merge_lane_worktrees_and_outputs_directory
    merge_base = git(review_tools_worktree, "merge-base", main, head)
    merged_tree = git(helpers / "wt" / f"pr{number}-merged", "rev-parse", "HEAD^{tree}")
    author = pull_request_author(number)
    standing = run([sys.executable,
                    str(review_tools_worktree / "scripts" / "compose-pull-request-reviewer-brief.py"),
                    "--pull-request", str(number),
                    "--brief-file", str(arguments.brief_file),
                    "--instructions-file", str(instructions_file)])
    scratch = arguments.merge_lane_pull_request_reviewer_scratch_directories_parent_directory / f"rv{tag}"
    scratch.mkdir(parents=True, exist_ok=True)
    facts = ["## This pull request (facts from merge-lane-2)", "",
             f"- Pull request: #{number}, \"{spec['title']}\", author `{spec['author']}`.",
             f"- Head commit: `{head}`.",
             f"- Merge base: `{merge_base}`.",
             f"- Main's tip when commissioned: `{main}`.",
             f"- Merged tree (head merged onto main by merge-lane-2): `{merged_tree}`.",
             f"- Your scratch directory: `{scratch}`. Use it as `<your scratchpad>`."]
    if "reviewed_before" in spec:
        facts.append(f"- This head commit is a fix-round. Head commit reviewed before: "
                     f"`{spec['reviewed_before']}` ({spec['previous_reviews']}). "
                     f"{spec['new_commits']}")
        facts.append("- Files the new commit touches: "
                     + files_touched_text(review_tools_worktree, spec["reviewed_before"], head)
                     + ".")
        facts.append(f"- The author's answer to each finding: {spec['answer']}")
        facts.append("- Test files the whole pull request touches: "
                     + ", ".join(f"`{t}`" for t in spec["tests"]) + ".")
    else:
        facts.append("- Files the change touches: "
                     + files_touched_text(review_tools_worktree, merge_base, head) + ".")
        facts.append("- Test files the change touches: "
                     + ", ".join(f"`{t}`" for t in spec["tests"]) + ".")
        facts.append("- First round: no head commit was reviewed before.")
    facts.append("- Other open pull requests changing the same files: "
                 + spec.get("overlaps", "none") + ".")
    facts.append(f"- Hazards: {spec['hazards']}")
    if author == MERGE_LANE_ACCOUNT:
        facts.append(POST_VERDICT_AS_REVIEW_EVENT_LINE)
    addendum = arguments.ned_box_reviewer_brief_environment_addendum_file.read_text()
    brief = (standing.rstrip("\n") + "\n\n" + addendum.rstrip("\n") + "\n\n"
             + "\n".join(facts) + "\n")
    out = helpers / "briefs" / f"brief-{tag}-mac-claude.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(brief)
    print("composed", out, len(brief.split()), "words")


def main(argv=None):
    arguments = parse_arguments(argv)
    review_tools_worktree = arguments.review_tools_worktree_at_main
    instructions_file = (arguments.instructions_file
                         or review_tools_worktree / "docs" / "agents" / "pr-reviewer-instructions.md")
    try:
        specs = json.loads(arguments.brief_specifications_file.read_text())
        for spec in specs:
            compose(spec, arguments, review_tools_worktree, instructions_file)
    except (StepFailed, OSError, ValueError, KeyError) as failure:
        print(f"brief not composed: {type(failure).__name__}: {failure}\n"
              f"Briefs for entries before the failing one were written; none after it.\n"
              f"If the error names an entry of the specifications file or a missing file, fix "
              f"that and run this again.\n"
              f"Otherwise, tell the user this message.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
