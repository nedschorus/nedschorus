#!/usr/bin/env python3
"""Print a pull request author's fix-round brief from merge-lane-2's blocking findings, and check the round.

Usage:
  scripts/pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py <number>
  scripts/pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py <number> --check [--answers FILE] [--commit REV] [--after-conflict-merge]

The round is set by merge-lane-2's latest review that requests changes, together with every later
review of merge-lane-2's that comments on the same commit, where merge-lane-2 can add or re-post
blockers. That commit is the frozen-head. The blocking findings are those reviews' inline comments
whose body starts BLOCKING_MARKER; the bodies' free text is never parsed for findings. A blocker
re-posted with the same path, line and body counts once. A review's stated **Blocking: N** is
checked against its own marked comments, or, when it has none, against those of the later reviews,
which then re-post its blockers.

Without --check, run in the author's checkout: refuse when the pull request's head has moved past
the frozen-head, else print the brief: the frozen-head, each blocking finding word for word, how to
dispatch the fix-round subagent in a git worktree of its own and push from it, the round's rules,
and the --check command to finish with, which names the answers file in the author's checkout.

With --check, run in the worktree or checkout that holds the round's commit: the commits from the frozen-head to --commit (default
HEAD) must be none, or one non-merge commit, or with --after-conflict-merge a merge of origin/main
followed by at most one non-merge commit. The answers file holds one entry per blocking finding,
each starting "<n>. " on its own line; by default it is ANSWERS_FILE_NAME_FORMAT inside the
checkout's own git directory, where git never commits it. It prints the files the fix commit changes that no blocking
finding names, and, once GitHub's head is the checked commit or the frozen-head, the message for
merge-lane-2, which the agent sends with SendMessage, since a program cannot.

Exit codes: 0 brief printed or round passes; 1 the review or the round breaks a rule, said on
stderr; 2 gh, git or the answers file could not be read, said on stderr.
"""

import argparse
import importlib.util
import json
import re
import shlex
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
ANSWERS_FILE_NAME_FORMAT = "fix-round-answers-pull-request-{number}.md"
PRE_PUSH_TEST_COMMAND = ("python3 scripts/run-all-test-suites.py "
                         "--only-suites-whose-recorded-inputs-changed-since origin/main")
WORKTREE_DISPATCH_INSTRUCTION = (
    "For the author: dispatch the fix-round subagent with the Agent tool, as a fork (subagent_type: "
    "\"fork\") with isolation: \"worktree\" and run_in_background: true, so that it works in a git "
    "worktree of its own and its commit cannot pick up edits you make in your checkout while it "
    "works. Give it this whole brief, and tell it that the two paragraphs starting \"For the "
    "author\", indented lines included, are yours, not its.")
# The review's id keeps two rounds on the same frozen-head apart: git will not switch a second
# worktree to a branch an earlier round's worktree still has checked out, and the agent harness
# may keep that worktree locked.
LOCAL_BRANCH_NAME_FORMAT = "fix-round-pull-request-{number}-review-{review_id}"
# The subagent works on a local branch, not a detached HEAD: .claude/hooks/session-location-write-guard.py
# refuses every Edit or Write to a tracked file while HEAD is detached.
WORKTREE_REMOVAL_INSTRUCTION = (
    "For the author, when the subagent has finished: remove its worktree, and then the local branch "
    "{local_branch}, which the subagent makes in step 0 of the rules below. <path> is the worktree's "
    "path, which the Agent tool reports when the subagent finishes.\n"
    "   1. Run: git worktree remove <path>\n"
    "      If git refuses because the worktree is locked and the lock reason starts with \"claude agent\", "
    "the agent harness holds the lock: run step 1 again once git worktree list no longer shows the "
    "worktree as locked. If git worktree list still shows it locked when you end your turn, tell the user the "
    "worktree's path and the lock reason, and go no further.\n"
    "      If git refuses because the worktree holds changed or untracked files, list them with "
    "git -C <path> status --short and read them. Copy out of the worktree any file that is work to "
    "keep, such as a fix the subagent did not push, and tell merge-lane-2 about it with SendMessage. "
    "Then run: git worktree remove --force <path>\n"
    "      If git refuses because the worktree is locked for any other reason, the lock reason names "
    "who locked it. If whoever it names may still be using the worktree, tell the user the worktree's "
    "path and the lock reason, and go no further. Otherwise list its changed or untracked files with "
    "git -C <path> status --short, read them, copy out any that is work to keep and tell merge-lane-2 "
    "about it with SendMessage. Then run: git worktree remove --force --force <path> (the second --force removes a "
    "locked worktree).\n"
    "   2. Once the worktree is removed, run: git branch -D {local_branch}")
PULL_REQUEST_FIELDS = ("url", "headRefOid", "headRefName")


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
    arguments = ["pr", "view", str(number), "--json", ",".join(PULL_REQUEST_FIELDS)]
    command = "gh " + " ".join(arguments)
    rerun = (f" Run {command} yourself: if it now prints an object with all three fields filled in, "
             f"run {shlex.join(['python3', *sys.argv])} again.")
    output = gh(arguments)
    try:
        facts = json.loads(output)
    except json.JSONDecodeError as error:
        raise StepFailed(f"{command} printed output that is not JSON; Python's JSON parser said: "
                         f"{error}. The output began: {output[:200]!r}." + rerun) from None
    if not isinstance(facts, dict):
        raise StepFailed(f"{command} printed JSON that is not an object with named fields: {facts!r}."
                         + rerun)
    missing = [field for field in PULL_REQUEST_FIELDS if not facts.get(field)]
    if missing:
        raise StepFailed(f"{command} printed JSON in which these fields are missing or empty: "
                         f"{', '.join(missing)}." + rerun)
    return tuple(facts[field] for field in PULL_REQUEST_FIELDS)


def round_reviews(number, reviewer_login):
    """merge-lane-2's latest changes-requested review, then its later reviews of the same commit."""
    reviews = gh_json_lines(["api", "--paginate", f"repos/{{owner}}/{{repo}}/pulls/{number}/reviews",
                             "--jq", ".[]"])
    own = [review for review in reviews
           if (review.get("user") or {}).get("login") == reviewer_login
           and review.get("state") != "PENDING"]
    if not own:
        raise Refused(f"Pull request {number} has no review by {reviewer_login}, merge-lane-2's "
                      "account, so there is no fix-round to brief.\n"
                      "Wait for merge-lane-2's review; run this again when it requests changes.")
    requested = [index for index, review in enumerate(own) if review.get("state") == "CHANGES_REQUESTED"]
    if requested:
        round_set = own[requested[-1]:]
        if all(review.get("state") == "COMMENTED"
               and review.get("commit_id") == round_set[0].get("commit_id") for review in round_set[1:]):
            return round_set
    latest = own[-1]
    on_commit = f" on commit {latest.get('commit_id')}" if latest.get("state") == "COMMENTED" else ""
    raise Refused(f"merge-lane-2's latest review of pull request {number} ({latest.get('html_url')}) "
                  f"is {latest.get('state')}{on_commit}, not CHANGES_REQUESTED, so there is no fix-round to brief.\n"
                  "If that review lists follow-ups, answer them in a new pull request or tell "
                  "merge-lane-2 why not, with SendMessage.")


def review_links(reviews):
    return " and ".join(str(review.get("html_url")) for review in reviews)


def finding_identity(comment):
    return (comment.get("path"), comment.get("line") or comment.get("original_line"),
            (comment.get("body") or "").strip())


def marked(comments):
    return [comment for comment in comments
            if (comment.get("body") or "").lstrip().startswith(BLOCKING_MARKER)]


def without_reposts(comments):
    seen, kept = set(), []
    for comment in comments:
        if finding_identity(comment) not in seen:
            seen.add(finding_identity(comment))
            kept.append(comment)
    return kept


def blocking_findings(number, reviews):
    comments_by_review = [gh_json_lines(["api", "--paginate",
                                         f"repos/{{owner}}/{{repo}}/pulls/{number}/reviews/{review['id']}/comments",
                                         "--jq", ".[]"]) for review in reviews]
    marked_by_review = [marked(comments) for comments in comments_by_review]
    findings = without_reposts([comment for found in marked_by_review for comment in found])
    named = review_links(reviews)
    whose = "its" if len(reviews) == 1 else "their"
    asked_about = reviews[0].get("html_url")
    ask = ("Until merge-lane-2 answers, change nothing and push nothing.\n"
           f"Ask merge-lane-2 with SendMessage which findings block, naming its changes-requested review, "
           f"{asked_about}")
    if not findings:
        total = sum(len(comments) for comments in comments_by_review)
        raise Refused(f"merge-lane-2's review {named} requests changes, but none of {whose} "
                      f"{total} inline comments starts with {BLOCKING_MARKER}, the mark this "
                      "program reads blocking findings by.\n"
                      + ask + "; do not guess them from the reviews' text.")
    for index, review in enumerate(reviews):
        stated = BLOCKING_COUNT_PATTERN.search(review.get("body") or "")
        if not stated:
            continue
        own = without_reposts(marked_by_review[index])
        counted = own or without_reposts([comment for found in marked_by_review[index + 1:]
                                          for comment in found])
        if int(stated.group(1)) != len(counted):
            where = ("its own inline comments" if own or len(reviews) == 1
                     else "the inline comments of the reviews after it")
            raise Refused(f"merge-lane-2's review {review.get('html_url')} says **Blocking: {stated.group(1)}**, "
                          f"but {len(counted)} of {where} start with {BLOCKING_MARKER}"
                          + (f" ({named})" if len(reviews) > 1 else "") + ".\n"
                          + ask + ", and both counts.")
    return findings


def finding_place(comment):
    line = comment.get("line") or comment.get("original_line")
    return f"{comment.get('path')}:{line}" if line else str(comment.get("path"))


def round_facts(number, reviewer_login):
    url, head, branch = pull_request(number)
    reviews = round_reviews(number, reviewer_login)
    review = reviews[0]
    frozen_head = review.get("commit_id")
    if not frozen_head:
        raise StepFailed(f"merge-lane-2's review {review.get('html_url')} carries no commit_id")
    return (url, head, branch, review_links(reviews), review.get("id"), frozen_head,
            blocking_findings(number, reviews))


def print_brief(number, reviewer_login):
    url, head, branch, review_link, review_id, frozen_head, findings = round_facts(number, reviewer_login)
    if head != frozen_head:
        raise Refused(f"Pull request {url} has head {head}, but merge-lane-2 reviewed {frozen_head}; "
                      "a commit was pushed after the review, so this fix-round has already pushed.\n"
                      "Wait for merge-lane-2's review of the new head, and run this again if it "
                      "requests changes.")
    lines = [
        f"Fix-round brief for pull request {url}",
        f"Frozen-head: {frozen_head}",
        f"merge-lane-2's review: {review_link}",
        "",
        f"Blocking findings ({len(findings)}), word for word:",
    ]
    for index, finding in enumerate(findings, 1):
        lines += ["", f"{index}. {finding_place(finding)} ({finding.get('html_url')})",
                  (finding.get("body") or "").strip()]
    answers_path = default_answers_path(number)
    local_branch = LOCAL_BRANCH_NAME_FORMAT.format(number=number, review_id=review_id)
    # --answers names the file in this checkout's git directory, which the subagent's own
    # worktree does not hold by default.
    check_command = f"python3 {PROGRAM} {number} --check --answers {shlex.quote(answers_path)}"
    lines += [
        "",
        WORKTREE_DISPATCH_INSTRUCTION,
        WORKTREE_REMOVAL_INSTRUCTION.format(local_branch=local_branch),
        "",
        "For the subagent, the rules of the round, in order, run in your own worktree:",
        f"0. Make a local branch at the frozen-head and switch to it: git fetch origin && git switch -C {local_branch} {frozen_head}",
        f"1. Before changing anything, run: python3 scripts/branch-conflict-check.py --pull-request {number}",
        "   If it reports VERDICT: CONFLICT, do what its report says.",
        "2. Check each finding against the code. Fix each one that holds, root cause included, "
        "with a test that fails without the fix.",
        "3. Change nothing else, apart from the tests, callers, documents and citations that "
        "keep the pull request atomic. Findings that do not block, in this review or any other, "
        "are not part of this round: merge-lane-2 sends them after the merge.",
        "4. Put every change in one commit on top of the branch as step 1 left it. "
        "If no finding holds, make no commit.",
        f"5. Write the answers file {answers_path}, one entry per finding above, each starting "
        "\"<n>. \" on its own line, with any further lines of the entry after it: what you fixed, "
        "or why the finding does not hold. It is inside git's own directory, so it is never "
        "committed.",
        f"6. Run the affected test suites: {PRE_PUSH_TEST_COMMAND}",
        "   If a suite fails because of this round's change, fix it in the same commit; if it "
        "fails for another cause, tell merge-lane-2 with SendMessage before pushing.",
        f"7. Run the check: {check_command}",
        "   adding --after-conflict-merge if step 1's report had you merge origin/main. If it refuses, change the "
        "answers file or the unpushed commit as it says (git commit --amend is allowed before the "
        "push) and run the check again.",
        f"8. When it passes with a commit not yet pushed, push once, with: git push origin HEAD:{shlex.quote(branch)}",
        "   Then run the same check command "
        "again. When it passes and prints a message for merge-lane-2, which it does at once if you "
        "made no commit, send that message to merge-lane-2 with SendMessage.",
        "9. If anything fails after the push, do not push again or rewrite the branch: tell "
        "merge-lane-2 with SendMessage what failed, and the next fix-round takes it.",
        "   If the push itself fails, do not retry it by force or rewrite the branch: tell "
        "merge-lane-2 with SendMessage what git printed.",
    ]
    print("\n".join(lines))


def default_answers_path(number):
    """The answers file inside the checkout's own git directory, which git never commits."""
    try:
        git_directory = git(["rev-parse", "--absolute-git-dir"]).strip()
    except StepFailed as failure:
        raise Refused(f"This must run in your checkout of pull request {number}'s branch, whose "
                      f"git directory holds the answers file, but git could not find one: {failure}.\n"
                      "Change to that checkout and run this again.") from None
    return str(Path(git_directory) / ANSWERS_FILE_NAME_FORMAT.format(number=number))


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
    described = ", ".join(f"{sha[:12]} ({len(parents)} parent{'' if len(parents) == 1 else 's'})"
                          for sha, parents in commits)
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
    url, head, _branch, review_link, _review_id, frozen_head, findings = round_facts(number, reviewer_login)
    answers = read_answers(answers_path or default_answers_path(number), len(findings))
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
        lines += ["Not pushed yet. Push once, then run this same command again to get the message "
                  "for merge-lane-2."]
        print("\n".join(lines))
        return
    pushed = (f"New head {commit}, one fix-round on top of the frozen-head {frozen_head}."
              if commit != frozen_head else
              f"Nothing pushed; the head stays the frozen-head {frozen_head}.")
    message = [f"Fix-round on pull request {url}, answering merge-lane-2's review "
               f"{review_link}. {pushed}"]
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
    parser.add_argument("--answers",
                        help="with --check: the answers file, one \"<n>. \" entry per finding "
                             "(default: " + ANSWERS_FILE_NAME_FORMAT.format(number="<number>")
                             + " in the checkout's git directory)")
    parser.add_argument("--commit", default="HEAD",
                        help="with --check: the round's last commit (default: HEAD)")
    parser.add_argument("--after-conflict-merge", action="store_true",
                        help="with --check: the round starts with a merge of origin/main, made "
                             "because branch-conflict-check.py reported a conflict")
    parser.add_argument("--reviewer-login", default=MERGE_LANE_2_REVIEWER_LOGIN,
                        help=f"merge-lane-2's GitHub account (default: {MERGE_LANE_2_REVIEWER_LOGIN})")
    arguments = parser.parse_args(argv)
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
              "This program stopped there: it printed no brief and checked no round.\n"
              "If the failure above names a commit or ref this checkout does not have, run git "
              "fetch origin and run this again.\n"
              "If gh is not logged in, tell the user: only the user can log gh in.\n"
              "Otherwise, tell the user this whole message.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
