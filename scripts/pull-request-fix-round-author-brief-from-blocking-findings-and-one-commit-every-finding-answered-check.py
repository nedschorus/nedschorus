#!/usr/bin/env python3
"""Print a pull request author's fix-round brief from merge-lane-2's blocking findings, and check the round.

Usage:
  scripts/pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py <number>
  scripts/pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py <number> --check --answers FILE [--commit REV] [--after-conflict-merge]

The round is set by merge-lane-2's latest review of the pull request, which must request changes.
Its commit is the frozen-head. Its blocking findings are its inline comments whose body starts
BLOCKING_MARKER; the body's free text is never parsed for findings.

Without --check: refuse when the pull request's head has moved past the frozen-head, else print
the brief: the frozen-head, each blocking finding word for word, the round's rules, and the
--check command to finish with.

With --check, run in the author's checkout: the commits from the frozen-head to --commit (default
HEAD) must be none, or one non-merge commit, or with --after-conflict-merge a merge of origin/main
followed by at most one non-merge commit. --answers holds one entry per blocking finding, each
starting "<n>. " on its own line. It prints the files the fix commit changes that no blocking
finding names, and, once GitHub's head is the checked commit or the frozen-head, the message for
merge-lane-2, which the agent sends with SendMessage, since a program cannot.

Exit codes: 0 brief printed or round passes; 1 the review or the round breaks a rule, said on
stderr; 2 gh, git or the answers file could not be read, said on stderr.
"""

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

_git_output_spec = importlib.util.spec_from_file_location(
    "git_machine_readable_output_runner_and_parser_common",
    Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
    / "git-machine-readable-output-runner-and-parser-common.py")
git_output = importlib.util.module_from_spec(_git_output_spec)
_git_output_spec.loader.exec_module(git_output)

MERGE_LANE_2_REVIEWER_LOGIN = "ned-review-merge"
BLOCKING_MARKER = "**Blocks.**"
BLOCKING_COUNT_PATTERN = re.compile(r"\*\*Blocking:\s*(\d+)\*\*")
ANSWER_START_PATTERN = re.compile(r"^(\d+)\.\s+(\S.*)$")
GH_TIMEOUT_SECONDS = 60
PROGRAM = "scripts/" + Path(__file__).name


class Refused(Exception):
    """The review or the round breaks a rule; the text says which and what to do."""


class StepFailed(Exception):
    """gh, git or a file could not be read."""


def gh(arguments):
    try:
        completed = subprocess.run(["gh", *arguments], capture_output=True, text=True,
                                   stdin=subprocess.DEVNULL, timeout=GH_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        raise StepFailed(f"gh {' '.join(arguments)} did not finish within "
                         f"{GH_TIMEOUT_SECONDS} s") from None
    except OSError as error:
        raise StepFailed(f"could not start gh: {error}") from None
    if completed.returncode != 0:
        raise StepFailed(f"gh {' '.join(arguments)} exited {completed.returncode}: "
                         f"{completed.stderr.strip()}")
    return completed.stdout


def gh_json_lines(arguments):
    """Each line of `gh api --paginate ... --jq '.[]'` is one JSON object."""
    output = gh(arguments)
    try:
        return [json.loads(line) for line in output.splitlines() if line.strip()]
    except json.JSONDecodeError as error:
        raise StepFailed(f"gh {' '.join(arguments)} printed a line that is not JSON: {error}") from None


def git(arguments, **options):
    try:
        return git_output.run_git(".", arguments, **options).decode()
    except git_output.GitCommandFailed as failure:
        raise StepFailed(f"git {' '.join(failure.arguments)} failed: {failure.stderr.strip()}") from None


def is_ancestor(ancestor, descendant):
    try:
        completed = subprocess.run(["git", "merge-base", "--is-ancestor", ancestor, descendant],
                                   capture_output=True, text=True, stdin=subprocess.DEVNULL,
                                   timeout=git_output.GIT_TIMEOUT_SECONDS)
    except (subprocess.TimeoutExpired, OSError) as error:
        raise StepFailed(f"git merge-base --is-ancestor {ancestor} {descendant} did not run: {error}") from None
    if completed.returncode not in (0, 1):
        raise StepFailed(f"git merge-base --is-ancestor {ancestor} {descendant} exited "
                         f"{completed.returncode}: {completed.stderr.strip()}")
    return completed.returncode == 0


def pull_request(number):
    try:
        facts = json.loads(gh(["pr", "view", str(number), "--json", "url,headRefOid"]))
        return facts["url"], facts["headRefOid"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise StepFailed(f"gh pr view {number} gave no url and headRefOid: {error!r}") from None


def latest_review(number, reviewer_login):
    reviews = gh_json_lines(["api", "--paginate", f"repos/{{owner}}/{{repo}}/pulls/{number}/reviews",
                             "--jq", ".[]"])
    own = [review for review in reviews
           if (review.get("user") or {}).get("login") == reviewer_login
           and review.get("state") != "PENDING"]
    if not own:
        raise Refused(f"Pull request {number} has no review by {reviewer_login}, merge-lane-2's "
                      "account, so there is no fix-round to brief.\n"
                      "Wait for merge-lane-2's review; run this again when it requests changes.")
    review = own[-1]
    if review.get("state") != "CHANGES_REQUESTED":
        raise Refused(f"merge-lane-2's latest review of pull request {number} ({review.get('html_url')}) "
                      f"is {review.get('state')}, not CHANGES_REQUESTED, so there is no fix-round to brief.\n"
                      "If that review lists follow-ups, answer them in a new pull request or tell "
                      "merge-lane-2 why not.")
    return review


def blocking_findings(number, review):
    comments = gh_json_lines(["api", "--paginate",
                              f"repos/{{owner}}/{{repo}}/pulls/{number}/reviews/{review['id']}/comments",
                              "--jq", ".[]"])
    findings = [comment for comment in comments
                if (comment.get("body") or "").lstrip().startswith(BLOCKING_MARKER)]
    if not findings:
        raise Refused(f"merge-lane-2's review {review.get('html_url')} requests changes, but none of its "
                      f"{len(comments)} inline comments starts with {BLOCKING_MARKER}, the mark this "
                      "program reads blocking findings by.\n"
                      "Ask merge-lane-2 with SendMessage which findings block, naming the review; "
                      "do not guess them from the review's text.")
    stated = BLOCKING_COUNT_PATTERN.search(review.get("body") or "")
    if stated and int(stated.group(1)) != len(findings):
        raise Refused(f"merge-lane-2's review {review.get('html_url')} says **Blocking: {stated.group(1)}**, "
                      f"but {len(findings)} of its inline comments start with {BLOCKING_MARKER}.\n"
                      "Ask merge-lane-2 with SendMessage which findings block, naming the review "
                      "and both counts.")
    return findings


def finding_place(comment):
    line = comment.get("line") or comment.get("original_line")
    return f"{comment.get('path')}:{line}" if line else str(comment.get("path"))


def round_facts(number, reviewer_login):
    url, head = pull_request(number)
    review = latest_review(number, reviewer_login)
    frozen_head = review.get("commit_id")
    if not frozen_head:
        raise StepFailed(f"merge-lane-2's review {review.get('html_url')} carries no commit_id")
    return url, head, review, frozen_head, blocking_findings(number, review)


def print_brief(number, reviewer_login):
    url, head, review, frozen_head, findings = round_facts(number, reviewer_login)
    if head != frozen_head:
        raise Refused(f"Pull request {url} has head {head}, but merge-lane-2 reviewed {frozen_head}; "
                      "a commit was pushed after the review, so this fix-round has already pushed.\n"
                      "Wait for merge-lane-2's review of the new head, and run this again if it "
                      "requests changes.")
    lines = [
        f"Fix-round brief for pull request {url}",
        f"Frozen-head: {frozen_head}",
        f"merge-lane-2's review: {review.get('html_url')}",
        "",
        f"Blocking findings ({len(findings)}), word for word:",
    ]
    for index, finding in enumerate(findings, 1):
        lines += ["", f"{index}. {finding_place(finding)} ({finding.get('html_url')})",
                  (finding.get("body") or "").strip()]
    lines += [
        "",
        "Rules of the round:",
        "- Check each finding against the code. Fix each one that holds, root cause included, "
        "with a test that fails without the fix.",
        "- Change nothing else, apart from the tests, callers, documents and citations that "
        "keep the pull request atomic.",
        "- Make at most one commit, on top of the frozen-head. If branch-conflict-check.py "
        "reported VERDICT: CONFLICT, merge origin/main first as its report says, then make "
        "the one commit.",
        "- Write an answers file with one entry per finding, each starting \"<n>. \" on its own "
        "line: what you fixed, or why the finding does not hold.",
        "- Before pushing, run:",
        f"  python3 {PROGRAM} {number} --check --answers <answers file>"
        " [--after-conflict-merge]",
        "  Push once when it passes, run it again, and send merge-lane-2 the message it prints, "
        "with SendMessage.",
    ]
    print("\n".join(lines))


def read_answers(path, finding_count):
    try:
        text = Path(path).read_text()
    except OSError as error:
        raise StepFailed(f"could not read the answers file {path}: {error}") from None
    answers = {}
    current = None
    for line in text.splitlines():
        match = ANSWER_START_PATTERN.match(line)
        if match:
            current = int(match.group(1))
            if current in answers:
                raise Refused(f"The answers file {path} has two entries for finding {current}.\n"
                              "Merge them into one entry.")
            answers[current] = [match.group(2)]
        elif current is not None and line.strip():
            answers[current].append(line.strip())
    expected = set(range(1, finding_count + 1))
    missing = sorted(expected - answers.keys())
    extra = sorted(answers.keys() - expected)
    if missing or extra:
        problems = []
        if missing:
            problems.append(f"no entry for finding {', '.join(map(str, missing))}")
        if extra:
            problems.append(f"an entry for finding {', '.join(map(str, extra))}, which does not exist")
        raise Refused(f"The answers file {path} has {' and '.join(problems)}; the review has "
                      f"{finding_count} blocking findings.\n"
                      "Give each finding, numbered as the brief numbers it, exactly one entry "
                      "starting \"<n>. \" on its own line.")
    return {number: " ".join(parts) for number, parts in sorted(answers.items())}


def commits_since(frozen_head, commit):
    """The round's own commits after frozen_head up to commit, oldest first, as (sha, [parents])."""
    if not is_ancestor(frozen_head, commit):
        raise Refused(f"The checked commit {commit} does not have the frozen-head {frozen_head} in "
                      "its history, so the round rewrote or replaced the reviewed commits.\n"
                      "Put the fix in one commit on top of the frozen-head; never amend or rebase "
                      "a pushed head.")
    # --first-parent leaves out the commits a merge of origin/main brings in.
    listing = git(["rev-list", "--reverse", "--first-parent", "--parents", f"{frozen_head}..{commit}"])
    return [(fields[0], fields[1:]) for fields in (line.split() for line in listing.splitlines())]


def fix_commit_range(frozen_head, commits, after_conflict_merge):
    """Check the shape of the round; return (base, fix commit) for its file list, or None."""
    described = ", ".join(f"{sha[:12]} ({len(parents)} parents)" for sha, parents in commits)
    if not commits:
        return None
    if after_conflict_merge:
        merge_sha, merge_parents = commits[0]
        shape_holds = (len(merge_parents) == 2 and merge_parents[0] == frozen_head
                       and len(commits) <= 2
                       and all(len(parents) == 1 for _, parents in commits[1:]))
        if shape_holds:
            if not is_ancestor(merge_parents[1], "origin/main"):
                raise Refused(f"The merge {merge_sha[:12]} brings in {merge_parents[1][:12]}, "
                              "which is not on origin/main.\n"
                              "If origin/main is out of date, run git fetch origin and check again; "
                              "otherwise merge origin/main itself.")
            return (merge_sha, commits[1][0]) if len(commits) == 2 else None
        rule = ("a merge of origin/main whose first parent is the frozen-head, followed by at most "
                "one non-merge commit")
    else:
        if len(commits) == 1 and commits[0][1] == [frozen_head]:
            return frozen_head, commits[0][0]
        rule = "one non-merge commit whose parent is the frozen-head"
    raise Refused(f"The round has {len(commits)} commits after the frozen-head {frozen_head[:12]}: "
                  f"{described}. A fix-round is {rule}.\n"
                  "If the commits are not pushed, squash them into one commit on top of the "
                  "frozen-head.\n"
                  "If they are pushed, tell merge-lane-2 with SendMessage; do not force-push.")


def unnamed_files(base, fix_commit, findings):
    if base is None:
        return []
    changed = git_output.nul_separated_fields(git(["diff", "-z", "--name-only", base, fix_commit]))
    named_text = "\n".join(f"{finding.get('path')}\n{finding.get('body') or ''}" for finding in findings)
    # A finding names a file by its path or by its file name alone, and a path holds its file name.
    return [path for path in changed if Path(path).name not in named_text]


def check_round(number, reviewer_login, answers_path, commit_name, after_conflict_merge):
    url, head, review, frozen_head, findings = round_facts(number, reviewer_login)
    answers = read_answers(answers_path, len(findings))
    commit = git(["rev-parse", "--verify", f"{commit_name}^{{commit}}"]).strip()
    git(["cat-file", "-e", f"{frozen_head}^{{commit}}"])
    fix_range = fix_commit_range(frozen_head, commits_since(frozen_head, commit), after_conflict_merge)
    leftovers = unnamed_files(*(fix_range or (None, None)), findings)
    lines = [f"PASS: the fix-round on {url} keeps to its rules; {len(findings)} findings answered."]
    if leftovers:
        lines += ["Files the fix commit changes that no blocking finding names; say in the message "
                  "why each belongs in this round, or take it out:"]
        lines += [f"  {path}" for path in leftovers]
    if head not in (commit, frozen_head):
        raise Refused(f"GitHub's head of {url} is {head}, which is neither the checked commit "
                      f"{commit} nor the frozen-head {frozen_head}.\n"
                      "Check --commit names what you pushed; if someone else pushed, tell "
                      "merge-lane-2 with SendMessage.")
    if head == frozen_head and commit != frozen_head:
        lines += ["Not pushed yet. Push once, then run this again to get the message for merge-lane-2."]
        print("\n".join(lines))
        return
    pushed = (f"New head {commit}, one fix-round on top of the frozen-head {frozen_head}."
              if commit != frozen_head else
              f"Nothing pushed; the head stays the frozen-head {frozen_head}.")
    message = [f"Fix-round on pull request {url}, answering merge-lane-2's review "
               f"{review.get('html_url')}. {pushed}"]
    message += [f"{index}. {finding_place(findings[index - 1])}: {answers[index]}"
                for index in answers]
    if leftovers:
        message += ["Files the fix commit changes that no blocking finding names: "
                    + ", ".join(leftovers) + ". Why each belongs: <fill in>"]
    lines += ["", "Send merge-lane-2 this message with SendMessage:", "", *message]
    print("\n".join(lines))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Print a pull request author's fix-round brief from merge-lane-2's blocking "
                    "findings, or with --check, check the round against it.")
    parser.add_argument("number", type=int, help="the pull request's number")
    parser.add_argument("--check", action="store_true",
                        help="check the round in this checkout instead of printing the brief")
    parser.add_argument("--answers", help="with --check: the answers file, one \"<n>. \" entry per finding")
    parser.add_argument("--commit", default="HEAD",
                        help="with --check: the round's last commit (default: HEAD)")
    parser.add_argument("--after-conflict-merge", action="store_true",
                        help="with --check: the round starts with a merge of origin/main, made "
                             "because branch-conflict-check.py reported a conflict")
    parser.add_argument("--reviewer-login", default=MERGE_LANE_2_REVIEWER_LOGIN,
                        help=f"merge-lane-2's GitHub account (default: {MERGE_LANE_2_REVIEWER_LOGIN})")
    arguments = parser.parse_args(argv)
    if arguments.check and not arguments.answers:
        parser.error("--check needs --answers")
    try:
        if arguments.check:
            check_round(arguments.number, arguments.reviewer_login, arguments.answers,
                        arguments.commit, arguments.after_conflict_merge)
        else:
            print_brief(arguments.number, arguments.reviewer_login)
    except Refused as refusal:
        print(f"REFUSED: {refusal}", file=sys.stderr)
        return 1
    except StepFailed as failure:
        print(f"FAILED: {failure}\n"
              "If the failure names a cause you can fix, such as gh being logged out or a commit "
              "not fetched, fix it and run this again.\n"
              "Otherwise, tell the user this message.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
