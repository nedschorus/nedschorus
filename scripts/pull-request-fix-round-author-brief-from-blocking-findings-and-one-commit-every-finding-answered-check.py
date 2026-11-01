#!/usr/bin/env python3
"""Print a pull request author's fix-round brief from merge-lane-2's blocking findings, and check the round.

Usage:
  scripts/pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py <number>
  scripts/pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py <number> --check [--answers FILE] [--commit REV] [--after-conflict-merge]
  scripts/pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py <number> --move-start NEW_TOPIC_BRANCH [PATH ...]
  scripts/pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py <number> --move-finish --title TITLE --body-file FILE

The round is set by merge-lane-2's latest review that requests changes, as long as every later
review of merge-lane-2's comments on the same commit, where merge-lane-2 can add or re-post
blockers. That commit is the frozen-head. The round's reviews are every review of the frozen-head,
in the order GitHub returns them, whoever posted it and whatever its state, apart from PENDING and
DISMISSED, and apart from those a round record names that does not name that latest review: the
commissioned reviewer posts its review as a comment, before merge-lane-2's, and merge-lane-2 may
split its own review of one head into several changes-requested reviews, or re-post an earlier
one's blockers in a later one. The brief names that latest review first. A round record is a pull request comment whose first line matches
ROUND_RECORD_PATTERN; --check posts one when a round ends with no commit, naming the frozen-head
and the round's reviews, because nothing else on GitHub tells that round's reviews apart from those
of a later round on the same head. The round's number counts merge-lane-2's changes-requested
reviews, taking as one those of the same commit that no round record tells apart. The blocking
findings are the round's reviews' inline comments whose body starts with a match of
BLOCKING_MARKER_PATTERN; the bodies' free text is never parsed for findings. A blocker re-posted
with the same path, line and body counts once. A review's stated **Blocking: N** is checked against
its own marked comments, or, when it has none, against those of the round's other reviews, such as
the commissioned reviewer's Blocks it grades or a later review that re-posts its blockers.

Without --check, run in the author's checkout: refuse when the pull request's head has moved past
the frozen-head, else print the brief: the frozen-head, ADVISOR_FIX_ROUND_INSTRUCTION when the
round's number is ADVISOR_FIX_ROUND_NUMBER and on no other, each blocking finding word for word, how to
dispatch the fix-round subagent in a git worktree of its own and push from it, the round's rules,
and the --check command to finish with, which the subagent runs in its own worktree.

With --check, run in the worktree or checkout that holds the round's commit: the commits from the frozen-head to --commit (default
HEAD) must be none, or one non-merge commit, or with --after-conflict-merge a merge of origin/main
followed by at most one non-merge commit. The answers file holds one entry per blocking finding,
each starting "<n>. " on its own line; an entry that starts with MOVED_TO_PULL_REQUEST_PREFIX_PATTERN,
in any case, must go on with MOVED_TO_PULL_REQUEST_PATTERN naming a pull request gh pr view finds, or --check refuses it;
--check also refuses when, for any file of that pull request's gh pr diff, the file's whole patch reversed
applies cleanly to the checked commit's tree, since the moved change is then still on this branch. A file
whose moved part was undone but whose patch context the kept part changed is not caught. By default it is ANSWERS_FILE_NAME_FORMAT at the root of
the worktree or checkout --check runs in, and --check refuses when the checked commit's tree holds
an answers file the frozen-head's tree does not, since a branch cut before .gitignore named the file does not leave it out of
commits. It prints the files the fix commit changes that no blocking
finding names, and, once GitHub's head is the checked commit or the frozen-head, the message for
merge-lane-2, which the agent sends with SendMessage, since a program cannot. When the round has no
commit, it first posts the round record, unless one already names the round's latest
changes-requested review.

--move-start and --move-finish carry a change the round moves out of the pull request to a new topic branch,
in the same worktree. --move-start runs on the round's local branch after the round's commit, with a clean
worktree apart from the answers file: it moves the answers file into the git directory, records the move in
MOVE_STATE_FILE_NAME there, switches to NEW_TOPIC_BRANCH cut from origin/main and copies each PATH from the
frozen-head. --move-finish refuses while an answers file or the description file is in the worktree, stages
every change, runs PRE_PUSH_TEST_COMMAND, commits, pushes, opens the pull request with gh pr create, switches
back, restores the answers file, deletes the local NEW_TOPIC_BRANCH and checks that it is gone. A failure
after the push prints the steps still to do; it undoes nothing, and a second --move-finish would commit again.

Exit codes: 0 brief printed, round passes or move step done; 1 the review or the round breaks a rule, said on
stderr; 2 gh, git or the answers file could not be read, said on stderr.
"""

import argparse
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_git_output_spec = importlib.util.spec_from_file_location(
    "git_machine_readable_output_runner_and_parser_common",
    Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
    / "git-machine-readable-output-runner-and-parser-common.py")
git_output = importlib.util.module_from_spec(_git_output_spec)
_git_output_spec.loader.exec_module(git_output)

MERGE_LANE_2_REVIEWER_LOGIN = "ned-review-merge"
# Reviewers spell the mark several ways, such as "**Blocks.**", "**Blocks:**", "**Blocks**" or "**Blocks** (...)"; no instruction fixes one.
BLOCKING_MARKER_PATTERN = re.compile(r"\*\*Blocks\b[^*\n]*\*\*")
BLOCKING_MARKER_DESCRIPTION = "the bold word **Blocks**"
BLOCKING_COUNT_PATTERN = re.compile(r"\*\*Blocking:\s*(\d+)\*\*")
ROUND_RECORD_FORMAT = ("Fix-round answered without a commit: frozen-head {frozen_head}, reviews {review_ids}.\n"
                       "Posted by {program} --check. A changes-requested review of the same head posted "
                       "after this comment starts a new fix-round.")
ROUND_RECORD_PATTERN = re.compile(r"Fix-round answered without a commit: frozen-head ([0-9a-f]+), "
                                  r"reviews (\d+(?: \d+)*)\.")
ANSWER_START_PATTERN = re.compile(r"^(\d+)\.\s+(\S.*)$")
MOVED_TO_PULL_REQUEST_PREFIX = "Moved to pull request "
MOVED_TO_PULL_REQUEST_PREFIX_PATTERN = re.compile(
    re.escape(MOVED_TO_PULL_REQUEST_PREFIX.rstrip()) + r"\b", re.IGNORECASE)
MOVED_TO_PULL_REQUEST_PATTERN = re.compile(
    re.escape(MOVED_TO_PULL_REQUEST_PREFIX) + r"(#?\d+|https://github\.com/[^/\s]+/[^/\s]+/pull/\d+)\b",
    re.IGNORECASE)
MOVE_CHANGE_TO_OWN_PULL_REQUEST_INSTRUCTION = (
    "   If a blocking finding shows that one change in this pull request should not land with the rest, "
    "you may move that change to a pull request of its own instead of fixing it here, so that the rest "
    "can merge. Undo the change on this branch as part of step 4's one commit; never amend or rewrite a "
    "pushed commit. Once that commit is made, run: python3 {program} {number} --move-start "
    "<new topic branch> [<path> ...]\n"
    "   naming as <path> each file whose every change belongs to the moved change, its tests included. "
    "It puts you on <new topic branch>, cut from origin/main, with those files as the frozen-head has "
    "them. Then make by hand the moved part of each file that is only partly moved, write the new pull "
    "request's description as CLAUDE.md says in a file outside this worktree, and run: python3 {program} "
    "{number} --move-finish --title <title> --body-file <description file>\n"
    "   --move-finish runs step 6's test command, commits, pushes and opens the new pull request, then puts "
    "you back on {local_branch}. If either command refuses or fails, it says why and what to do next; do "
    "that. Answer the finding in step 5 with an entry that starts "
    f"\"{MOVED_TO_PULL_REQUEST_PREFIX}\" followed by the URL --move-finish prints; the check in "
    "step 7 refuses the entry when no such pull request exists, or when its change is still on this "
    "branch.")
MOVE_STATE_FILE_NAME = "fix-round-move-to-own-pull-request.json"
# The answers file waits in the git directory while the new topic branch is checked out, so no commit
# or check made there can pick it up.
ANSWERS_SET_ASIDE_DIRECTORY_NAME = "fix-round-answers-set-aside"
# What gh pr view prints on stderr for a number or URL that names no pull request.
PULL_REQUEST_NOT_FOUND_MARKER = "Could not resolve to a PullRequest"
GH_TIMEOUT_SECONDS = 60
PROGRAM = "scripts/" + Path(__file__).name
ANSWERS_FILE_NAME_FORMAT = "fix-round-answers-pull-request-{number}.md"
ANSWERS_FILE_NAME_PATTERN = re.compile(r"fix-round-answers-pull-request-\d+\.md")
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
# The subagent works on a local branch, not a detached HEAD: .claude/guard-hooks/session-location-write-guard.py
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
ADVISOR_FIX_ROUND_NUMBER = 3
ADVISOR_FIX_ROUND_INSTRUCTION = (
    "This is the pull request's third fix-round, its last before merge-lane-2 brings it to the user: "
    "before you change anything, call the advisor with the blocking findings and the fix you plan.")


# Messages to agents follow docs/nedschorus-wiki/nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md.
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


def round_records(number):
    """(frozen-head, set of review ids) for each round record on the pull request, oldest first."""
    comments = gh_json_lines(["api", "--paginate", f"repos/{{owner}}/{{repo}}/issues/{number}/comments",
                              "--jq", ".[]"])
    records = []
    for comment in comments:
        match = ROUND_RECORD_PATTERN.match(comment.get("body") or "")
        if match:
            records.append((match.group(1), {int(review_id) for review_id in match.group(2).split()}))
    return records


def round_count(requested_reviews, records):
    """Changes-requested reviews of one commit are one round, until a round record names some of them."""
    def round_key(review):
        commit = review.get("commit_id")
        naming = [index for index, (head, review_ids) in enumerate(records)
                  if head == commit and review.get("id") in review_ids]
        return commit, naming[0] if naming else None
    return len({round_key(review) for review in requested_reviews})


def round_reviews(number, reviewer_login):
    """merge-lane-2's latest changes-requested review; the round's reviews, in the order GitHub
    returns them; whether a round record already names that review; and the round's number."""
    reviews = gh_json_lines(["api", "--paginate", f"repos/{{owner}}/{{repo}}/pulls/{number}/reviews",
                             "--jq", ".[]"])
    records = round_records(number)
    own = [(position, review) for position, review in enumerate(reviews)
           if (review.get("user") or {}).get("login") == reviewer_login
           and review.get("state") != "PENDING"]
    if not own:
        raise Refused(f"Pull request {number} has no review by {reviewer_login}, merge-lane-2's "
                      "account, so there is no fix-round to brief.\n"
                      "Wait for merge-lane-2's review; run this again when it requests changes.")
    requested = [index for index, (_, review) in enumerate(own) if review.get("state") == "CHANGES_REQUESTED"]
    if requested:
        _, anchor = own[requested[-1]]
        frozen_head = anchor.get("commit_id")
        if all(review.get("state") == "COMMENTED" and review.get("commit_id") == frozen_head
               for _, review in own[requested[-1] + 1:]):
            on_head = [review_ids for head, review_ids in records if head == frozen_head]
            recorded = any(anchor.get("id") in review_ids for review_ids in on_head)
            earlier_rounds = set().union(*(review_ids for review_ids in on_head
                                           if anchor.get("id") not in review_ids))
            round_list = [review for review in reviews
                          if review.get("commit_id") == frozen_head and review.get("id") not in earlier_rounds
                          and review.get("state") not in ("PENDING", "DISMISSED")]
            return (anchor, round_list, recorded,
                    round_count([own[index][1] for index in requested], records))
    latest = own[-1][1]
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
            if BLOCKING_MARKER_PATTERN.match((comment.get("body") or "").lstrip())]


def without_reposts(comments):
    seen, kept = set(), []
    for comment in comments:
        if finding_identity(comment) not in seen:
            seen.add(finding_identity(comment))
            kept.append(comment)
    return kept


def latest_first(anchor, reviews):
    return [anchor, *(review for review in reviews if review is not anchor)]


def blocking_findings(number, anchor, reviews):
    comments_by_review = [gh_json_lines(["api", "--paginate",
                                         f"repos/{{owner}}/{{repo}}/pulls/{number}/reviews/{review['id']}/comments",
                                         "--jq", ".[]"]) for review in reviews]
    marked_by_review = [marked(comments) for comments in comments_by_review]
    findings = without_reposts([comment for found in marked_by_review for comment in found])
    named = review_links(latest_first(anchor, reviews))
    asked_about = anchor.get("html_url")
    whose = "its" if len(reviews) == 1 else f"the reviews {named}'"
    ask = ("Until merge-lane-2 answers, change nothing and push nothing.\n"
           f"Ask merge-lane-2 with SendMessage which findings block, naming its changes-requested review, "
           f"{asked_about}")
    if not findings:
        total = sum(len(comments) for comments in comments_by_review)
        raise Refused(f"merge-lane-2's review {asked_about} requests changes, but none of {whose} "
                      f"{total} inline comments starts with {BLOCKING_MARKER_DESCRIPTION}, the mark this "
                      "program reads blocking findings by.\n"
                      + ask + "; do not guess them from the reviews' text.")
    for index, review in enumerate(reviews):
        stated = BLOCKING_COUNT_PATTERN.search(review.get("body") or "")
        if not stated:
            continue
        own = without_reposts(marked_by_review[index])
        counted = own or findings
        if int(stated.group(1)) != len(counted):
            where = ("its own inline comments" if own or len(reviews) == 1
                     else "the inline comments of the round's other reviews")
            raise Refused(f"The review {review.get('html_url')} says **Blocking: {stated.group(1)}**, "
                          f"but {len(counted)} of {where} start with {BLOCKING_MARKER_DESCRIPTION}"
                          + (f" ({named})" if len(reviews) > 1 else "") + ".\n"
                          + ask + ", and both counts.")
    return findings


def finding_place(comment):
    line = comment.get("line") or comment.get("original_line")
    return f"{comment.get('path')}:{line}" if line else str(comment.get("path"))


def round_facts(number, reviewer_login):
    url, head, branch = pull_request(number)
    anchor, reviews, recorded, fix_round_number = round_reviews(number, reviewer_login)
    frozen_head = anchor.get("commit_id")
    if not frozen_head:
        raise StepFailed(f"merge-lane-2's review {anchor.get('html_url')} carries no commit_id")
    return (url, head, branch, review_links(latest_first(anchor, reviews)), anchor.get("id"), frozen_head,
            blocking_findings(number, anchor, reviews), fix_round_number,
            None if recorded else [review.get("id") for review in reviews])


def print_brief(number, reviewer_login):
    (url, head, branch, review_link, review_id, frozen_head, findings,
     fix_round_number, _unrecorded_review_ids) = round_facts(number, reviewer_login)
    if head != frozen_head:
        raise Refused(f"Pull request {url} has head {head}, but merge-lane-2 reviewed {frozen_head}; "
                      "a commit was pushed after the review, so this fix-round has already pushed.\n"
                      "Wait for merge-lane-2's review of the new head, and run this again if it "
                      "requests changes.")
    lines = [
        f"Fix-round brief for pull request {url}",
        f"Frozen-head: {frozen_head}",
        f"The round's reviews: {review_link}",
    ]
    if fix_round_number == ADVISOR_FIX_ROUND_NUMBER:
        lines += ["", ADVISOR_FIX_ROUND_INSTRUCTION]
    lines += [
        "",
        f"Blocking findings ({len(findings)}), word for word:",
    ]
    for index, finding in enumerate(findings, 1):
        lines += ["", f"{index}. {finding_place(finding)} ({finding.get('html_url')})",
                  (finding.get("body") or "").strip()]
    answers_name = ANSWERS_FILE_NAME_FORMAT.format(number=number)
    local_branch = LOCAL_BRANCH_NAME_FORMAT.format(number=number, review_id=review_id)
    check_command = f"python3 {PROGRAM} {number} --check"
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
        MOVE_CHANGE_TO_OWN_PULL_REQUEST_INSTRUCTION.format(program=PROGRAM, number=number,
                                                           local_branch=local_branch),
        "4. Put every change in one commit on top of the branch as step 1 left it. "
        "If no finding holds, make no commit.",
        f"5. Write the answers file {answers_name} at the root of your worktree, one entry per "
        "finding above, each starting \"<n>. \" on its own line, with any further lines of the "
        "entry after it: what you fixed, why the finding does not hold, or, for a change moved as "
        "step 3 says, the new pull request. Never commit it: "
        "the branch's .gitignore may not leave it out, and the check in step 7 refuses a commit "
        "that holds it.",
        f"6. Run the affected nc-test-suites: {PRE_PUSH_TEST_COMMAND}",
        "   If a suite fails because of this round's change, fix it in the same commit; if it "
        "fails for another cause, tell merge-lane-2 with SendMessage before pushing.",
        f"7. Run the check: {check_command}",
        "   adding --after-conflict-merge if step 1's report had you merge origin/main. If it refuses, change the "
        "answers file or the unpushed commit as it says (git commit --amend is allowed before the "
        "push) and run the check again.",
        f"8. When it passes with a commit not yet pushed, push once, with: git push origin HEAD:{shlex.quote(branch)}",
        "   Then run the same check command "
        "again. When it passes and prints a message for merge-lane-2, which it does at once if you "
        "made no commit, after recording on the pull request, in a comment, which reviews this round "
        "answered, send that message to merge-lane-2 with SendMessage.",
        "9. If anything fails after the push, do not push again or rewrite the branch: tell "
        "merge-lane-2 with SendMessage what failed, and the next fix-round takes it.",
        "   If the push itself fails, do not retry it by force or rewrite the branch: tell "
        "merge-lane-2 with SendMessage what git printed.",
    ]
    print("\n".join(lines))


def default_answers_path(number):
    """The answers file at the root of the worktree or checkout this runs in."""
    try:
        top_level = git(["rev-parse", "--show-toplevel"]).strip()
    except StepFailed as failure:
        raise Refused(f"This must run in the worktree or checkout of pull request {number}'s branch "
                      f"whose root holds the answers file, but git found no worktree here: {failure}.\n"
                      "Change to that worktree and run this again.") from None
    return str(Path(top_level) / ANSWERS_FILE_NAME_FORMAT.format(number=number))


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


def refuse_moved_to_missing_pull_request(answers, path):
    """An entry that says its change moved to a new pull request must name one that exists."""
    for index, answer in answers.items():
        if not MOVED_TO_PULL_REQUEST_PREFIX_PATTERN.match(answer):
            continue
        moved = MOVED_TO_PULL_REQUEST_PATTERN.match(answer)
        if not moved:
            raise Refused(f"The answers file {path} says in entry {index} that the finding's change moved "
                          "to a new pull request, but no pull request number or URL follows "
                          f"\"{MOVED_TO_PULL_REQUEST_PREFIX}\". An entry that moves a change must name the "
                          "pull request that now carries it, or the change leaves this pull request and "
                          "lands nowhere.\n"
                          "If you have not opened the new pull request yet, open it as CLAUDE.md says, "
                          f"make the entry start \"{MOVED_TO_PULL_REQUEST_PREFIX}\" followed by its number "
                          "or URL, then run the check again.\n"
                          "If the change did not move after all, put it back in the round's commit, rewrite "
                          "the entry to say what you fixed or why the finding does not hold, then run the "
                          "check again.\n"
                          f"The check is: {shlex.join(['python3', *sys.argv])}")
        named = moved.group(1).lstrip("#")
        try:
            gh(["pr", "view", named, "--json", "number"])
        except StepFailed as failure:
            if PULL_REQUEST_NOT_FOUND_MARKER not in str(failure):
                raise
            raise Refused(f"The answers file {path} says in entry {index} that the finding's change moved "
                          f"to pull request {named}, but GitHub has no such pull request ({failure}). "
                          "An entry that moves a change must name the pull request that now carries it, "
                          "or the change leaves this pull request and lands nowhere.\n"
                          "If you have not opened the new pull request yet, open it as CLAUDE.md says, "
                          f"make the entry start \"{MOVED_TO_PULL_REQUEST_PREFIX}\" followed by its number "
                          "or URL, then run the check again.\n"
                          "If the entry names the wrong number or URL, correct it so that the entry starts "
                          f"\"{MOVED_TO_PULL_REQUEST_PREFIX}\" followed by the number or URL of the pull "
                          "request that carries the change, then run the check again.\n"
                          "If the change did not move after all, put it back in the round's commit, rewrite "
                          "the entry to say what you fixed or why the finding does not hold, then run the "
                          "check again.\n"
                          f"The check is: {shlex.join(['python3', *sys.argv])}") from None


def moved_pull_requests(answers):
    """{finding number: the pull request an entry says its change moved to}, for the entries that say so."""
    moved = {}
    for index, answer in answers.items():
        match = MOVED_TO_PULL_REQUEST_PATTERN.match(answer)
        if match:
            moved[index] = match.group(1).lstrip("#")
    return moved


def patch_by_file(patch):
    """Split a unified diff, as gh pr diff prints it, into one patch per file."""
    pieces = re.split(r"(?m)^(?=diff --git )", patch)
    return [piece for piece in pieces if piece.startswith("diff --git ")]


def files_whose_moved_change_is_still_here(named, commit):
    """Files of pull request named whose whole change, reversed, applies cleanly to commit's tree."""
    patch = gh(["pr", "diff", named])
    still_here = []
    with tempfile.TemporaryDirectory() as scratch:
        # A scratch index holding commit's tree, so the check reads that tree and not the worktree's index.
        environment = dict(os.environ, GIT_INDEX_FILE=str(Path(scratch) / "index"))
        git(["read-tree", commit], environment=environment)
        patch_file = Path(scratch) / "file.patch"
        for piece in patch_by_file(patch):
            patch_file.write_text(piece)
            check = ["apply", "--cached", "--reverse", "--check", str(patch_file)]
            try:
                completed = subprocess.run(["git", *check], capture_output=True, text=True,
                                           stdin=subprocess.DEVNULL, env=environment,
                                           timeout=git_output.GIT_TIMEOUT_SECONDS)
            except (subprocess.TimeoutExpired, OSError) as error:
                raise StepFailed(f"git {' '.join(check)} did not run: {error}") from None
            if completed.returncode not in (0, 1):
                raise StepFailed(f"git {' '.join(check)} exited {completed.returncode} on pull request "
                                 f"{named}'s patch: {completed.stderr.strip()}")
            if completed.returncode == 0:
                still_here.append(piece.splitlines()[0].removeprefix("diff --git "))
    return still_here


def refuse_moved_change_still_here(answers, commit, path):
    """A change moved to its own pull request must be undone on this branch, or it lands twice."""
    for index, named in moved_pull_requests(answers).items():
        still_here = files_whose_moved_change_is_still_here(named, commit)
        if still_here:
            raise Refused(f"The answers file {path} says in entry {index} that the finding's change moved to "
                          f"pull request {named}, but {commit[:12]} still holds that pull request's change to "
                          f"{', '.join(still_here)}, so the change would land twice.\n"
                          "If the round's commit is not pushed, undo the moved change in it, amend it with "
                          "git commit --amend, and run the check again.\n"
                          "If it is pushed, tell merge-lane-2 with SendMessage which files still hold the "
                          "moved change; do not force-push.")


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


def files_added_since(frozen_head, commit):
    """Files commit's tree holds that frozen_head's tree does not, whichever commit of the round added them."""
    # --no-renames, so that an answers file renamed from a file the frozen-head holds still counts as added.
    listing = git(["diff", "-z", "--name-only", "--no-renames", "--diff-filter=A", frozen_head, commit])
    return git_output.nul_separated_fields(listing)


def refuse_committed_answers_file(frozen_head, commit):
    committed = [path for path in files_added_since(frozen_head, commit)
                 if ANSWERS_FILE_NAME_PATTERN.fullmatch(Path(path).name)]
    if committed:
        raise Refused(f"The round does not pass: its commits after the frozen-head {frozen_head[:12]} "
                      f"add these answers files: {', '.join(committed)}. An answers file must never "
                      "reach the pull request.\n"
                      "If the round's commit is not pushed, run git rm --cached on each answers file "
                      "named above, then git commit --amend --no-edit, and check again.\n"
                      "If the round's commit is pushed, tell merge-lane-2 with SendMessage which "
                      "answers files the pushed commit holds; do not force-push.")


def unnamed_files(base, fix_commit, findings):
    if base is None:
        return []
    changed = git_output.nul_separated_fields(git(["diff", "-z", "--name-only", base, fix_commit]))
    named_text = "\n".join(f"{finding.get('path')}\n{finding.get('body') or ''}" for finding in findings)
    # A finding names a file by its path or by its file name alone, and a path holds its file name.
    return [path for path in changed if Path(path).name not in named_text]


def check_round(number, reviewer_login, answers_path, commit_name, after_conflict_merge):
    (url, head, _branch, review_link, _review_id, frozen_head, findings,
     _fix_round_number, unrecorded_review_ids) = round_facts(number, reviewer_login)
    answers_path = answers_path or default_answers_path(number)
    answers = read_answers(answers_path, len(findings))
    refuse_moved_to_missing_pull_request(answers, answers_path)
    commit = git(["rev-parse", "--verify", f"{commit_name}^{{commit}}"]).strip()
    refuse_moved_change_still_here(answers, commit, answers_path)
    git(["cat-file", "-e", f"{frozen_head}^{{commit}}"])
    fix_range = fix_commit_range(frozen_head, commits_since(frozen_head, commit), after_conflict_merge)
    refuse_committed_answers_file(frozen_head, commit)
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
    message = [f"Fix-round on pull request {url}, answering the round's reviews "
               f"{review_link}. {pushed}"]
    message += [f"{index}. {finding_place(findings[index - 1])}: {answers[index]}"
                for index in answers]
    if leftovers:
        message += ["Files the fix commit changes that no blocking finding names: "
                    + ", ".join(leftovers) + ". Why each belongs: <fill in>"]
    if commit == frozen_head and unrecorded_review_ids:
        gh(["api", f"repos/{{owner}}/{{repo}}/issues/{number}/comments", "-f", "body=" + ROUND_RECORD_FORMAT.format(
            frozen_head=frozen_head, review_ids=" ".join(map(str, unrecorded_review_ids)), program=PROGRAM)])
    lines += ["", "Send merge-lane-2 this message with SendMessage:", "", *message]
    print("\n".join(lines))


def worktree_root():
    return Path(git(["rev-parse", "--show-toplevel"]).strip())


def move_state_path():
    return Path(git(["rev-parse", "--absolute-git-dir"]).strip()) / MOVE_STATE_FILE_NAME


def current_branch():
    branch = git(["branch", "--show-current"]).strip()
    if not branch:
        raise Refused("HEAD is detached, so there is no branch to move a change from or back to.\n"
                      "Switch to the round's local branch, as step 0 of the brief makes it, and run this again.")
    return branch


def local_branch_exists(branch):
    return bool(git(["branch", "--list", branch]).strip())


def move_start(number, reviewer_login, new_branch, whole_file_paths):
    (_url, _head, _branch, _review_link, review_id, frozen_head, _findings,
     _fix_round_number, _unrecorded_review_ids) = round_facts(number, reviewer_login)
    local_branch = LOCAL_BRANCH_NAME_FORMAT.format(number=number, review_id=review_id)
    state_path = move_state_path()
    if state_path.exists():
        state = json.loads(state_path.read_text())
        raise Refused(f"A move to {state['new_branch']} is already under way in this worktree.\n"
                      f"Finish it with python3 {PROGRAM} {number} --move-finish before you start another.")
    if current_branch() != local_branch:
        raise Refused(f"--move-start runs on the round's local branch {local_branch}, but this worktree is on "
                      f"{current_branch()}.\n"
                      f"Switch to {local_branch} and run this again.")
    if git(["rev-parse", "HEAD"]).strip() == frozen_head:
        raise Refused("The round has no commit on top of the frozen-head yet, so nothing has undone the change "
                      "this branch is to lose.\n"
                      "Make step 4's one commit first, undoing the moved change in it, then run this again.")
    if local_branch_exists(new_branch):
        raise Refused(f"A local branch {new_branch} already exists.\n"
                      "Name a new topic branch that does not exist yet, and run this again.")
    missing = [path for path in whole_file_paths
               if subprocess.run(["git", "cat-file", "-e", f"{frozen_head}:{path}"], capture_output=True,
                                 stdin=subprocess.DEVNULL, timeout=git_output.GIT_TIMEOUT_SECONDS).returncode]
    if missing:
        raise Refused(f"The frozen-head {frozen_head[:12]} has no file {', '.join(missing)}.\n"
                      "Name each path as the frozen-head holds it, relative to the worktree's root, and run this again.")
    root = worktree_root()
    answers_name = ANSWERS_FILE_NAME_FORMAT.format(number=number)
    changed = [entry for entry in git_output.nul_separated_fields(
                   git(["status", "--porcelain", "-z", "--untracked-files=all"]))
               if entry[3:] != answers_name]
    if changed:
        raise Refused(f"This worktree has changes outside the round's commit: {', '.join(changed)}.\n"
                      "Put each one in the round's commit, or remove it, and run this again; the new topic "
                      "branch must start with nothing but the moved change.")
    answers = root / answers_name
    set_aside = state_path.parent / ANSWERS_SET_ASIDE_DIRECTORY_NAME / answers_name
    state_path.write_text(json.dumps({"new_branch": new_branch, "return_branch": local_branch,
                                      "answers": str(answers), "set_aside": str(set_aside)}))
    if answers.exists():
        set_aside.parent.mkdir(exist_ok=True)
        shutil.move(answers, set_aside)
    git(["switch", "-q", "-c", new_branch, "origin/main"])
    if whole_file_paths:
        git(["checkout", frozen_head, "--", *whole_file_paths])
    print(f"On {new_branch}, cut from origin/main, with {len(whole_file_paths)} whole file(s) copied from the "
          f"frozen-head {frozen_head[:12]}.\n"
          "Make by hand the moved part of each file that is only partly moved, write the new pull request's "
          "description in a file outside this worktree, then run:\n"
          f"python3 {PROGRAM} {number} --move-finish --title <title> --body-file <description file>")


def move_finish(number, title, body_file):
    state_path = move_state_path()
    if not state_path.exists():
        raise Refused("No move is under way in this worktree.\n"
                      f"Start one with python3 {PROGRAM} {number} --move-start <new topic branch> [<path> ...].")
    state = json.loads(state_path.read_text())
    new_branch, return_branch = state["new_branch"], state["return_branch"]
    answers, set_aside = Path(state["answers"]), Path(state["set_aside"])
    if current_branch() != new_branch:
        raise Refused(f"--move-finish runs on {new_branch}, which --move-start made, but this worktree is on "
                      f"{current_branch()}.\n"
                      f"Switch to {new_branch} and run this again.")
    root = worktree_root()
    if Path(body_file).resolve().is_relative_to(root):
        raise Refused(f"The description file {body_file} is inside this worktree, so the commit would carry it.\n"
                      "Move it outside the worktree and run this again.")
    if answers.exists():
        raise Refused(f"An answers file {answers} is in this worktree, so the commit would carry it to "
                      f"{new_branch}.\n"
                      f"Move it to {set_aside} and run this again; it comes back when the move ends.")
    git(["add", "-A"])
    if not git(["diff", "--cached", "--name-only"]).strip():
        raise Refused(f"{new_branch} holds no change beside origin/main, so there is nothing to move.\n"
                      "Bring the moved change onto it, by hand or by naming whole files to --move-start, and "
                      "run this again.")
    tests = subprocess.run(shlex.split(PRE_PUSH_TEST_COMMAND), cwd=root, stdin=subprocess.DEVNULL)
    if tests.returncode:
        raise Refused(f"The test command exited {tests.returncode} on {new_branch}: {PRE_PUSH_TEST_COMMAND}\n"
                      f"Fix the moved change on {new_branch} and run this again; nothing is committed yet.")
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as message:
        message.write(title + "\n\n" + Path(body_file).read_text())
    try:
        git(["commit", "-q", "-F", message.name])
    finally:
        os.unlink(message.name)
    git(["push", "-q", "origin", new_branch])
    try:
        url = gh(["pr", "create", "--base", "main", "--head", new_branch, "--title", title,
                  "--body-file", body_file]).strip().splitlines()[-1]
        git(["switch", "-q", return_branch])
        if set_aside.exists():
            shutil.move(set_aside, answers)
        git(["branch", "-D", new_branch])
        if local_branch_exists(new_branch):
            raise StepFailed(f"git branch -D {new_branch} left the branch in place")
    except StepFailed as failure:
        raise StepFailed(f"{failure}. {new_branch} is pushed. Still to do, by hand, in order: open its pull "
                         f"request if gh pr list --head {new_branch} shows none; git switch {return_branch}; "
                         f"move {set_aside} back to {answers} if it is there; git branch -D {new_branch}; "
                         f"delete {state_path}") from None
    state_path.unlink()
    print(f"Moved to {url}; you are back on {return_branch}.\n"
          f"Answer the finding with an entry that starts: {MOVED_TO_PULL_REQUEST_PREFIX}{url}")


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
                             + " at the root of this worktree)")
    parser.add_argument("--commit", default="HEAD",
                        help="with --check: the round's last commit (default: HEAD)")
    parser.add_argument("--after-conflict-merge", action="store_true",
                        help="with --check: the round starts with a merge of origin/main, made "
                             "because branch-conflict-check.py reported a conflict")
    parser.add_argument("--reviewer-login", default=MERGE_LANE_2_REVIEWER_LOGIN,
                        help=f"merge-lane-2's GitHub account (default: {MERGE_LANE_2_REVIEWER_LOGIN})")
    parser.add_argument("--move-start", nargs="+", metavar=("NEW_TOPIC_BRANCH", "PATH"),
                        help="after the round's commit: cut NEW_TOPIC_BRANCH from origin/main and copy each "
                             "PATH, a file whose every change moves, whole from the frozen-head")
    parser.add_argument("--move-finish", action="store_true",
                        help="test, commit, push and open the moved change's pull request, then switch back")
    parser.add_argument("--title", help="with --move-finish: the new pull request's title")
    parser.add_argument("--body-file", help="with --move-finish: the new pull request's description file")
    arguments = parser.parse_args(argv)
    if arguments.move_finish and not (arguments.title and arguments.body_file):
        parser.error("--move-finish needs --title and --body-file")
    try:
        if arguments.move_start:
            move_start(arguments.number, arguments.reviewer_login, arguments.move_start[0],
                       arguments.move_start[1:])
        elif arguments.move_finish:
            move_finish(arguments.number, arguments.title, arguments.body_file)
        elif arguments.check:
            check_round(arguments.number, arguments.reviewer_login, arguments.answers,
                        arguments.commit, arguments.after_conflict_merge)
        else:
            print_brief(arguments.number, arguments.reviewer_login)
    except Refused as refusal:
        print(f"REFUSED: {refusal}", file=sys.stderr)
        return 1
    except StepFailed as failure:
        print(f"FAILED: {failure}\n"
              "This program stopped at the step named above.\n"
              "If the failure above names a commit or ref this checkout does not have, run git "
              "fetch origin and run this again.\n"
              "If gh is not logged in, tell the user: only the user can log gh in.\n"
              "Otherwise, tell the user this whole message.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
