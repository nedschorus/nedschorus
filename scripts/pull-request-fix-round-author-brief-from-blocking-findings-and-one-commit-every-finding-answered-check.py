#!/usr/bin/env python3
"""Print a pull request author's fix-round brief from merge-lane-2's blocking findings and nits, and check the round.

Usage:
  scripts/pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py <number>
  scripts/pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py <number> --check [--answers FILE] [--commit REV] [--after-conflict-merge] [--confirm-dispatching-agent-checked-new-shared-names]
  scripts/pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py <number> --move-change-to-own-pull-request-cut-new-topic-branch NEW_TOPIC_BRANCH [PATH ...]
  scripts/pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py <number> --move-change-to-own-pull-request-finish --title TITLE --body-file FILE

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
BLOCKING_MARKER_PATTERN, and, in a review merge-lane-2's account posted, each such comment the
posting program moved into the body under OUTSIDE_THE_DIFF_HEADING, briefed with the review's
link; the bodies' other free text is never parsed for findings. A review states a
**Blocking: N** count only when merge-lane-2's account posted it and its body starts with the
lines merge-lane-pull-request-reviewer-review-post-and-read-back.py writes, matched by
BLOCKING_COUNT_PATTERN: the verdict REQUEST_CHANGES, a blank line, and the count alone on its
line; the same words anywhere else, or in another account's review, state nothing. When one of
merge-lane-2's reviews of the round carries such a comment and states a count, only the marked comments of merge-lane-2's own reviews of the round block, a later addendum
without a count included, since that review grades every finding of the round and the
commissioned reviewer's marks it leaves out were graded lower. A blocker re-posted
with the same path, line and body counts once. A review's stated **Blocking: N** is checked against
its own marked comments, or, when it has none, against those of the round's other reviews, such as
the commissioned reviewer's Blocks it grades or a later review that re-posts its blockers.
The nits are the inline comments of merge-lane-2's own reviews of the round whose body starts with
NIT_MARK, a re-posted nit counted once; a nit the posting program moved into a review's body is not
read, since the bodies' text is never parsed for findings. A round with nits but no blocking
finding is refused as a round with no blocking finding is, so nits alone produce no brief.

A pull request whose description has a #replaces line, read by REPLACES_READER_FILE_NAME, carries over
the pull requests it replaces, through replacements of replacements. The round's number adds each
replaced pull request's round count, counted as above. The blocking findings and nits of a replaced
pull request's latest round are carried, after this pull request's own and marked with that round's
review, only into this pull request's first round, and only when the replaced round was never answered:
the replaced pull request's head is still that round's frozen-head and no round record names it. A
round that was answered has its fix commit carried onto the replacing branch, and merge-lane-2's review
of the replacement, which the brief still needs, grades it. Once this pull request's first round is
answered, by a fix commit or a round record, that answer covers the carried findings, so its later
rounds carry none. For the same reason, when C replaces B and B replaces A, A's findings are not carried
into C when B's first round was answered, by a fix commit, a round record or merge-lane-2's later approval of B,
even of the round's unchanged frozen-head, since they were carried into that round. A carried finding or nit with the same path, line and body as one of this pull
request's own counts once. A #replaces line the reader cannot follow is refused.

Without --check, run in the author's checkout: refuse when the pull request's head has moved past
the frozen-head; else run that checkout's scripts/branch-conflict-check.py --pull-request <number>,
and when it reports a conflict answered replace, print its report and REPLACE_INSTEAD_OF_ROUND_INSTRUCTION
in place of the brief, since a fix-round would check and push the pull request being replaced; when it
cannot answer, fail. Else find the pull request's topic-worktree, the worktree of this clone that has the
pull request's branch checked out, or, when there is none, make one with that checkout's
scripts/agent-seat-worktree-create-with-owner-file.py, so it has an owner file from the start; a failure
of that program is a failure here, its message passed on. Refuse when the topic-worktree has uncommitted
changes or untracked files, ignored files apart, or its HEAD is not the frozen-head. Then print the brief:
the frozen-head, ADVISOR_FIX_ROUND_INSTRUCTION when the round's number is ADVISOR_FIX_ROUND_NUMBER and on
no other, each blocking finding word for word, then each nit word for word, numbered on from the blocking
findings, to fix in the same round, how to dispatch the fix-round subagent, a fork without Claude Code's
worktree isolation, to work in the topic-worktree, what the author does when the subagent hands back new
shared names, that nothing is removed by hand afterwards, the round's rules, and the --check command to
finish with. Every command the brief has the subagent run, and the answers file's path, name the
topic-worktree's path.

With --check, run in the topic-worktree, and refuse anywhere else, naming the topic-worktree when this
clone has one: the commits from the frozen-head to --commit (default
HEAD) must be none, or one non-merge commit, or with --after-conflict-merge a merge of origin/main
followed by at most one non-merge commit. The answers file holds one entry per blocking finding
and per nit, each starting "<n>. " on its own line; an entry that starts with MOVED_TO_PULL_REQUEST_PREFIX_PATTERN,
in any case, must go on with MOVED_TO_PULL_REQUEST_PATTERN naming a pull request gh pr view finds, or --check refuses it;
--check also refuses when, for any file of that pull request's gh pr diff, the file's whole patch reversed
applies cleanly to the checked commit's tree, since the moved change is then still on this branch. A file
whose moved part was undone but whose patch context the kept part changed is not caught. By default it is ANSWERS_FILE_NAME_FORMAT at the root of
the worktree --check runs in. Since that file outlives the round, --check refuses one last written before
merge-lane-2's latest changes-requested review was submitted, as an earlier round's answers; a review
GitHub gives no submitted_at is not compared. --check refuses when the checked commit's tree holds
an answers file the frozen-head's tree does not, since a branch cut before .gitignore named the file does not leave it out of
commits. It prints the files the fix commit changes that no blocking
finding or nit names. It reads the pushed head from origin's branch with git ls-remote, not from GitHub's
headRefOid, which can lag a push by seconds; it fails when origin has no such branch. While that head is
still the frozen-head and the round has a commit, it first
lists the shared names the round adds, read by the new-shared-names lister from the worktree's files that
the frozen-head to the checked commit changes, leaving out names the frozen-head's tree holds; unless
--confirm-dispatching-agent-checked-new-shared-names is given, it refuses while that list is not empty, printing the
names and SUBAGENT_REPORT_HEADING_ABOVE_NEW_SHARED_NAMES_FOR_DISPATCHING_AGENT_TO_CHECK, since a forked subagent cannot start the
naming fresh-agent and must hand the names to the agent that dispatched it before the push, so that
the renames go into the round's one commit; it fails when git cannot list them. Then it runs
the nc-test-suites, as the pull request ready command runs them, in a scratch worktree of the checked
commit; each suite that fails there is run again in a scratch worktree of the frozen-head, with that
checkout's own runner, recording nothing. It refuses when a suite fails at the checked commit and not
at the frozen-head, which includes a suite the frozen-head does not have; a suite that fails at both is
not the round's doing, so it passes, names the suite, and records it in
PULL_REQUEST_FIX_ROUND_CHECK_TEST_SUITES_ALSO_FAILING_AT_FROZEN_HEAD_RECORD_FILE_NAME in the git directory under the checked commit. Once
the pushed head is the checked commit or the frozen-head, it prints the message for merge-lane-2, which
the agent sends with SendMessage, since a program cannot, naming the suites that record holds for the
checked commit; it runs no suite then. When the round has no commit, it first posts the round record,
unless one already names the round's latest changes-requested review.

--move-change-to-own-pull-request-cut-new-topic-branch and --move-change-to-own-pull-request-finish carry a
change the round moves out of the pull request to a new topic branch, in the same worktree. The first runs on
the pull request's branch after the round's commit, with a clean worktree apart from the answers file: it
switches to NEW_TOPIC_BRANCH cut from origin/main and copies each PATH from the frozen-head, and only then
records the move in MOVE_STATE_FILE_NAME in the git directory and moves the answers file there, so a failed
switch or copy leaves nothing recorded and the answers file in place. The second refuses while an answers
file or the description file is in the worktree, stages every change, runs the nc-test-suites as the pull
request ready command runs them, commits,
pushes with the pre-push hook's time limit, opens the pull request with gh pr create, switches back,
restores the answers file, deletes the local NEW_TOPIC_BRANCH and checks that it is gone. A failure after
the commit undoes nothing and prints the commit, the steps done and the steps still to do, which are
done by hand. A run on NEW_TOPIC_BRANCH refuses when the branch already holds a commit beside origin/main,
and says how to undo it, keeping its changes, so that a new run tests and commits them again. Whatever git
push writes on stderr, such as the pre-push hook saying it skipped a check, is printed whole, labelled as
the pre-push hook's output: after the success line, or inside the failure report when a later step fails.
The finish step does not judge those lines, so it exits 0 when every step succeeded even if the hook
skipped a check; the agent reads the printed lines and does what they say.

Exit codes: 0 brief or replace steps printed, round passes or move step done; 1 the review or the round breaks
a rule, said on stderr; 2 gh, git or the answers file could not be read, the conflict check could not answer,
the new shared names could not be listed, the worktree creator failed, or the suite runner stopped before
judging every suite, said on stderr.
"""

import argparse
import datetime
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
_ready_command_spec = importlib.util.spec_from_file_location(
    "pull_request_ready_for_review_mark_after_description_defect_line_and_test_suites_check",
    Path(__file__).resolve().parent
    / "pull-request-ready-for-review-mark-after-description-defect-line-and-test-suites-check.py")
ready_command = importlib.util.module_from_spec(_ready_command_spec)
_ready_command_spec.loader.exec_module(ready_command)
_test_suite_runner_spec = importlib.util.spec_from_file_location(
    "run_all_test_suites", Path(__file__).resolve().parent / "run-all-test-suites.py")
test_suite_runner = importlib.util.module_from_spec(_test_suite_runner_spec)
_test_suite_runner_spec.loader.exec_module(test_suite_runner)

_lister_spec = importlib.util.spec_from_file_location(
    "new_shared_names_in_changed_files_list", Path(__file__).resolve().parent / "new-shared-names-in-changed-files-list.py")
new_shared_names_lister = importlib.util.module_from_spec(_lister_spec)
_lister_spec.loader.exec_module(new_shared_names_lister)

REPLACES_READER_FILE_NAME = "pull-request-description-replaces-line-replaced-pull-request-chain-reader-common.py"
_replaces_reader_spec = importlib.util.spec_from_file_location(
    "pull_request_description_replaces_line_replaced_pull_request_chain_reader_common",
    Path(__file__).resolve().with_name(REPLACES_READER_FILE_NAME))
replaces_reader = importlib.util.module_from_spec(_replaces_reader_spec)
_replaces_reader_spec.loader.exec_module(replaces_reader)

MERGE_LANE_2_REVIEWER_LOGIN = "ned-review-merge"
# Reviewers spell the mark several ways, such as "**Blocks.**", "**Blocks:**", "**Blocks**" or "**Blocks** (...)"; no instruction fixes one.
BLOCKING_MARKER_PATTERN = re.compile(r"\*\*Blocks\b[^*\n]*\*\*")
BLOCKING_MARKER_DESCRIPTION = "the bold word **Blocks**"
# merge-lane-pull-request-reviewer-review-post-and-read-back.py writes the count as a line of its own after
# the verdict line and a blank line; the same words anywhere else, such as a reviewer quoting them, are prose.
BLOCKING_COUNT_PATTERN = re.compile(r"\AREQUEST_CHANGES\n\n\*\*Blocking: (\d+)\*\*\n")
# merge-lane-pull-request-reviewer-review-post-and-read-back.py opens a nit's comment with this mark;
# BLOCKING_MARKER_PATTERN must never match it, or a nit would block.
NIT_MARK = "**fix-in-maintenance, nit** "
# merge-lane-pull-request-reviewer-review-post-and-read-back.py moves each comment GitHub would refuse,
# on a line outside the diff, into its review's body under this heading, one comment each.
OUTSIDE_THE_DIFF_HEADING = "Comments on lines outside this pull request's diff:"
OUTSIDE_THE_DIFF_LINE_PATTERN = re.compile(r"^- `(?P<path>[^`]+):(?P<line>\d+)`: (?P<body>.*)$")
OUTSIDE_THE_DIFF_CONTINUATION_INDENT = "  "
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
    "pushed commit. Once that commit is made, run: cd {worktree} && python3 {program} {number} "
    "--move-change-to-own-pull-request-cut-new-topic-branch <new topic branch> [<path> ...]\n"
    "   naming as <path> each file whose every change belongs to the moved change, its tests included. "
    "It puts you on <new topic branch>, cut from origin/main, with those files as the frozen-head has "
    "them. Then make by hand the moved part of each file that is only partly moved; you need "
    "not stage or commit it, because the finish step does both. Write the new pull request's description "
    "as CLAUDE.md says in a file outside this worktree, and run: cd {worktree} && python3 {program} "
    "{number} --move-change-to-own-pull-request-finish --title <title> --body-file <description file>\n"
    "   --move-change-to-own-pull-request-finish runs the nc-test-suites, commits, pushes and opens the new pull request, then puts "
    "you back on {pull_request_branch}. If either command refuses or fails, it says why and what to do next; do "
    "that. Answer the finding in step 5 with an entry that starts "
    f"\"{MOVED_TO_PULL_REQUEST_PREFIX}\" followed by the URL --move-change-to-own-pull-request-finish prints; the check in "
    "step 6 refuses the entry when no such pull request exists, or when its change is still on this "
    "branch.")
GUARDED_FILE_CHANGE_CARRYING_OUT_USER_RULING_INSTRUCTION = (
    "   When a finding asks you to change a file the instruction-file guard protects, and the fix only "
    "makes the file do what a ruling of the user's already says, the change is a user-approved-change: "
    "before each edit, write the ruling's words, quoted from the walk-minutes item or the agent-session "
    "where he gave it, with its time, into the `.walk-approved` marker file at the root of the checkout your "
    "agent-session started in, which the instruction-file guard reads it from, not the topic-worktree's: the "
    "root git rev-parse --show-toplevel prints when run without the cd this brief puts before other commands; "
    "and cite the ruling in the commit message. A change the guard's refusal lets through without a "
    "ruling, such as an obvious-error-fix, goes as that refusal says. Leave out any other change to such "
    "a file, go on with the other findings, and name that change in your report to the agent that "
    "dispatched you.")
MOVE_STATE_FILE_NAME = "fix-round-move-to-own-pull-request.json"
# Written by the run before the push and read by the run after it, which runs no suite.
PULL_REQUEST_FIX_ROUND_CHECK_TEST_SUITES_ALSO_FAILING_AT_FROZEN_HEAD_RECORD_FILE_NAME = "pull-request-fix-round-check-test-suites-also-failing-at-frozen-head-record.json"
# The answers file waits in the git directory while the new topic branch is checked out, so no commit
# or check made there can pick it up.
ANSWERS_SET_ASIDE_DIRECTORY_NAME = "fix-round-answers-set-aside"
# What gh pr view prints on stderr for a number or URL that names no pull request.
PULL_REQUEST_NOT_FOUND_MARKER = "Could not resolve to a PullRequest"
GH_TIMEOUT_SECONDS = 60
PROGRAM = "scripts/" + Path(__file__).name
ANSWERS_FILE_NAME_FORMAT = "fix-round-answers-pull-request-{number}.md"
ANSWERS_FILE_NAME_PATTERN = re.compile(r"fix-round-answers-pull-request-\d+\.md")
# Claude Code's isolation worktree is locked to the author's agent-session and deleted, with the
# git-ignored answers file, when its subagent stops; the topic-worktree is neither.
TOPIC_WORKTREE_DISPATCH_INSTRUCTION = (
    "For the author: dispatch the fix-round subagent with the Agent tool, as a fork (subagent_type: "
    "\"fork\") with run_in_background: true and without isolation, so that it works in pull request "
    "{number}'s own topic-worktree, {worktree}. Edit nothing in that worktree until the subagent has "
    "finished, so that its commit holds only the round's changes. Give it this whole brief, and tell it "
    "that the paragraphs starting \"For the author\" are yours, not its.")
AUTHOR_INSTRUCTION_WHEN_FIX_ROUND_SUBAGENT_HANDS_BACK_NEW_SHARED_NAMES_TO_CHECK = (
    "For the author, when the subagent's final report ends with a line for the agent that dispatched it, "
    "as it does when it lists new shared names under the heading "
    f"`{new_shared_names_lister.SUBAGENT_REPORT_HEADING_ABOVE_NEW_SHARED_NAMES_FOR_DISPATCHING_AGENT_TO_CHECK}`: do what that line says "
    "before anything the next paragraph calls for.")
TOPIC_WORKTREE_CLEANUP_INSTRUCTION = (
    "For the author, when the subagent has finished: remove nothing by hand. scripts/clean-worktrees.py "
    "removes {worktree} and its branch after the pull request has merged, when the worktree has an owner "
    "file, as every worktree scripts/agent-seat-worktree-create-with-owner-file.py makes has. If the "
    "subagent stopped before its last step, read what it left in {worktree}: git -C {quoted} status and its "
    "answers file. If it made its commit and wrote every answer, run step 6's check command yourself and go on "
    "from step 6; otherwise run python3 {program} {number} again, which says how to clear the worktree for "
    "a new subagent.")
WORKTREE_CREATOR_FILE_NAME = "agent-seat-worktree-create-with-owner-file.py"
# git fetch, then git worktree add, which checks out the whole tree.
WORKTREE_CREATOR_TIMEOUT_SECONDS = 300
PULL_REQUEST_FIELDS = ("url", "headRefOid", "headRefName")
# scripts/branch-conflict-check.py's exit code for a conflict, and the answer line that replaces the pull request.
CONFLICT_CHECK_EXIT_CONFLICT = 1
CONFLICT_CHECK_EXIT_NO_CONFLICT = 0
CONFLICT_CHECK_REPLACE_ANSWER_PREFIX = "ANSWER: replace"
# The check reads GitHub up to 6 times, 10 seconds apart, after a fetch.
CONFLICT_CHECK_TIMEOUT_SECONDS = 300
REPLACE_INSTEAD_OF_ROUND_INSTRUCTION = (
    "No fix-round runs: pull request {number} conflicts with main, and the conflict check above answers "
    "replace, so a round would check and push the pull request being replaced.\n"
    "Do what the report above says yourself. When it has you open the new pull request, its #replaces line "
    "carries this round's findings into the new pull request's first round.\n"
    "Then tell merge-lane-2 with SendMessage that this round stopped on a conflict with main, naming the new "
    "pull request's link and head, or the comment that closed this one.")
ADVISOR_FIX_ROUND_NUMBER = 3
ADVISOR_FIX_ROUND_INSTRUCTION = (
    "This is the pull request's third fix-round, its last before merge-lane-2 brings it to the user: "
    "before you change anything, call the advisor with the blocking findings and the fix you plan.")


# Messages to agents follow docs/nedschorus-wiki/nedschorus-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md.
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
    """(url, head, branch, description) of the pull request; the description may be empty."""
    arguments = ["pr", "view", str(number), "--json", ",".join((*PULL_REQUEST_FIELDS, "body"))]
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
    return (*(facts[field] for field in PULL_REQUEST_FIELDS), facts.get("body") or "")


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


def changes_requested_round_count(number, reviewer_login):
    """The round count round_reviews gives, read also for a pull request with no open round."""
    reviews = gh_json_lines(["api", "--paginate", f"repos/{{owner}}/{{repo}}/pulls/{number}/reviews",
                             "--jq", ".[]"])
    return round_count([review for review in reviews
                        if (review.get("user") or {}).get("login") == reviewer_login
                        and review.get("state") == "CHANGES_REQUESTED"], round_records(number))


def replaced_pull_requests(number, url, description):
    """(number, head, numbers it replaces directly) of each pull request this one replaces, oldest first, by the
    #replaces lines."""
    repository = "/".join(url.split("/")[3:5])
    facts = {number: (url, None, None, description)}

    def read_description(replaced):
        if replaced not in facts:
            facts[replaced] = pull_request(replaced)
        return facts[replaced][3]
    try:
        chain = replaces_reader.replaced_pull_request_chain_numbers_oldest_first(number, repository, read_description)
    except replaces_reader.ReplacedPullRequestChainUnreadable as error:
        raise Refused(str(error)) from None
    return [(replaced, facts[replaced][1],
             replaces_reader.replaced_pull_request_numbers_on_replaces_lines(facts[replaced][3], repository, replaced))
            for replaced in chain]


def unanswered_round_findings_of_replaced_pull_requests(replaced, reviewer_login):
    """The blocking findings and nits of each replaced pull request's latest round that was never answered,
    each marked with that round's review under "carried_from", leaving out the pull requests that a replaced
    pull request whose first round was answered replaces, directly or through others: that answer covered them."""
    open_rounds, answered_first_round = {}, []
    for replaced_number, replaced_head, _replaces in replaced:
        try:
            anchor, reviews, recorded, round_number = round_reviews(replaced_number, reviewer_login)
        except Refused:
            # No open round: any changes-requested round it had was answered.
            if changes_requested_round_count(replaced_number, reviewer_login):
                answered_first_round.append(replaced_number)
            continue
        if not recorded and anchor.get("commit_id") == replaced_head:
            open_rounds[replaced_number] = (anchor, reviews)
        if round_number > 1 or replaced_number not in open_rounds:
            answered_first_round.append(replaced_number)
    replaces = {replaced_number: direct for replaced_number, _head, direct in replaced}
    covered = set()
    pending = [older for number in answered_first_round for older in replaces[number]]
    while pending:
        older = pending.pop()
        if older not in covered:
            covered.add(older)
            pending += replaces.get(older, [])
    blocking, nits = [], []
    for replaced_number, _head, _replaces in replaced:
        if replaced_number not in open_rounds or replaced_number in covered:
            continue
        anchor, reviews = open_rounds[replaced_number]
        carried = {"carried_from": anchor.get("html_url")}
        blocking += [{**finding, **carried}
                     for finding in blocking_findings(replaced_number, anchor, reviews, reviewer_login)]
        nits += [{**nit, **carried}
                 for nit in nit_findings_of_merge_lane_2_reviews_in_round(replaced_number, reviews, reviewer_login)]
    return blocking, nits


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


def stated_blocking_count(review, reviewer_login):
    """Return the **Blocking: N** count of a review merge-lane-2's account posted, or None."""
    if (review.get("user") or {}).get("login") != reviewer_login:
        return None
    stated = BLOCKING_COUNT_PATTERN.match(review.get("body") or "")
    return int(stated.group(1)) if stated else None


def outside_the_diff_comments_read_back_from_review_body(body):
    """The comments merge-lane-pull-request-reviewer-review-post-and-read-back.py moved into a posted
    review body, each a dict of path, line and body. A comment starts at a line matching
    OUTSIDE_THE_DIFF_LINE_PATTERN after OUTSIDE_THE_DIFF_HEADING; each indented line after it continues
    it, with OUTSIDE_THE_DIFF_CONTINUATION_INDENT removed."""
    lines = iter(body.split("\n"))
    # `in` consumes the iterator through the heading, so the loop below reads only the lines after it.
    if OUTSIDE_THE_DIFF_HEADING not in lines:
        return []
    comments = []
    for line in lines:
        match = OUTSIDE_THE_DIFF_LINE_PATTERN.match(line)
        if match:
            comments.append({"path": match.group("path"), "line": int(match.group("line")),
                             "body": match.group("body")})
        elif comments and line.startswith(OUTSIDE_THE_DIFF_CONTINUATION_INDENT):
            comments[-1]["body"] += "\n" + line[len(OUTSIDE_THE_DIFF_CONTINUATION_INDENT):]
    return comments


def blocks_moved_into_review_body(review, reviewer_login):
    """The blocking findings a merge-lane-2 review's body lists under OUTSIDE_THE_DIFF_HEADING, each
    shaped like an inline comment and linked to the review, since GitHub gives it no link of its own."""
    if (review.get("user") or {}).get("login") != reviewer_login:
        return []
    moved = outside_the_diff_comments_read_back_from_review_body(review.get("body") or "")
    return [{**comment, "html_url": review.get("html_url")} for comment in marked(moved)]


def blocking_findings(number, anchor, reviews, reviewer_login=MERGE_LANE_2_REVIEWER_LOGIN):
    comments_by_review = [gh_json_lines(["api", "--paginate",
                                         f"repos/{{owner}}/{{repo}}/pulls/{number}/reviews/{review['id']}/comments",
                                         "--jq", ".[]"]) for review in reviews]
    marked_by_review = [marked(comments) + blocks_moved_into_review_body(review, reviewer_login)
                        for review, comments in zip(reviews, comments_by_review)]
    # A merge-lane-2 review with its own marks and a stated count was posted from categorized
    # findings, so it grades every finding of the round, and another reviewer's Blocks it graded
    # below must-fix-now does not block. merge-lane-2's own marks in its other reviews of the
    # round, such as a later addendum posted without a count, still block. A round without such a
    # review may leave some blockers marked only in the commissioned reviewer's comments.
    lane_marks = [found for review, found in zip(reviews, marked_by_review)
                  if (review.get("user") or {}).get("login") == reviewer_login and found]
    graded = any(found and stated_blocking_count(review, reviewer_login) is not None
                 for review, found in zip(reviews, marked_by_review))
    deciding = lane_marks if graded else marked_by_review
    findings = without_reposts([comment for found in deciding for comment in found])
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
        stated = stated_blocking_count(review, reviewer_login)
        if stated is None:
            continue
        own = without_reposts(marked_by_review[index])
        counted = own or findings
        if stated != len(counted):
            where = ("its own inline comments" if own or len(reviews) == 1
                     else "the inline comments of the round's other reviews")
            raise Refused(f"The review {review.get('html_url')} says **Blocking: {stated}**, "
                          f"but {len(counted)} of {where} start with {BLOCKING_MARKER_DESCRIPTION}"
                          + (f" ({named})" if len(reviews) > 1 else "") + ".\n"
                          + ask + ", and both counts.")
    return findings


def nit_findings_of_merge_lane_2_reviews_in_round(number, reviews, reviewer_login=MERGE_LANE_2_REVIEWER_LOGIN):
    """The inline comments of merge-lane-2's reviews of the round that open with NIT_MARK, reposts dropped."""
    nits = []
    for review in reviews:
        if (review.get("user") or {}).get("login") != reviewer_login:
            continue
        comments = gh_json_lines(["api", "--paginate",
                                  f"repos/{{owner}}/{{repo}}/pulls/{number}/reviews/{review['id']}/comments",
                                  "--jq", ".[]"])
        nits += [comment for comment in comments if (comment.get("body") or "").lstrip().startswith(NIT_MARK)]
    return without_reposts(nits)


def finding_place(comment):
    line = comment.get("line") or comment.get("original_line")
    place = f"{comment.get('path')}:{line}" if line else str(comment.get("path"))
    if comment.get("carried_from"):
        place += f", carried over from the replaced pull request's review {comment['carried_from']}"
    return place


def round_facts(number, reviewer_login):
    url, head, branch, description = pull_request(number)
    anchor, reviews, recorded, own_round_number = round_reviews(number, reviewer_login)
    frozen_head = anchor.get("commit_id")
    if not frozen_head:
        raise StepFailed(f"merge-lane-2's review {anchor.get('html_url')} carries no commit_id")
    # blocking_findings refuses a round with no blocking finding, so nits are read only beside one.
    findings = blocking_findings(number, anchor, reviews, reviewer_login)
    nits = nit_findings_of_merge_lane_2_reviews_in_round(number, reviews, reviewer_login)
    replaced = replaced_pull_requests(number, url, description)
    fix_round_number = own_round_number + sum(changes_requested_round_count(replaced_number, reviewer_login)
                                              for replaced_number, _head, _replaces in replaced)
    # The answer to this pull request's first round, a fix commit or a round record, answers the carried
    # findings too, so a later round carries none.
    if own_round_number == 1:
        carried_blocking, carried_nits = unanswered_round_findings_of_replaced_pull_requests(replaced, reviewer_login)
        findings = without_reposts(findings + carried_blocking)
        nits = without_reposts(nits + carried_nits)
    return (url, head, branch, review_links(latest_first(anchor, reviews)), frozen_head,
            findings, nits, fix_round_number,
            None if recorded else [review.get("id") for review in reviews], anchor.get("submitted_at"))


def conflict_check_report(number):
    """The report lines of this checkout's scripts/branch-conflict-check.py when it answers that the pull request
    conflicts with main and is replaced, else None."""
    try:
        top_level = git(["rev-parse", "--show-toplevel"]).strip()
    except StepFailed as failure:
        raise StepFailed(f"git found no checkout here to run the conflict check from: {failure}") from failure
    command = [sys.executable, str(Path(top_level) / "scripts" / "branch-conflict-check.py"),
               "--pull-request", str(number)]
    try:
        completed = subprocess.run(command, cwd=top_level, capture_output=True, text=True,
                                   stdin=subprocess.DEVNULL, timeout=CONFLICT_CHECK_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        raise StepFailed(f"{shlex.join(command)} did not finish in {CONFLICT_CHECK_TIMEOUT_SECONDS} seconds, so "
                         "whether this pull request conflicts with main is not known") from None
    report = completed.stdout.splitlines()
    if completed.returncode == CONFLICT_CHECK_EXIT_NO_CONFLICT:
        return None
    if completed.returncode != CONFLICT_CHECK_EXIT_CONFLICT:
        raise StepFailed(f"{shlex.join(command)} exited {completed.returncode}, so whether this pull request "
                         "conflicts with main is not known. It printed:\n"
                         + (completed.stdout + completed.stderr).strip())
    if any(line.startswith(CONFLICT_CHECK_REPLACE_ANSWER_PREFIX) for line in report):
        return report
    return None


def topic_worktree_of_branch(branch):
    """The path of the worktree of this clone that has branch checked out, or None."""
    for record in git_output.worktree_records(git(["worktree", "list", "--porcelain", "-z"])):
        if record.branch == f"refs/heads/{branch}" and not record.prunable_reason:
            return Path(record.path)
    return None


def topic_worktree_made_by_creator(branch):
    """Make a worktree on branch with this checkout's worktree creator and return its path."""
    top_level = git(["rev-parse", "--show-toplevel"]).strip()
    command = [sys.executable, str(Path(top_level) / "scripts" / WORKTREE_CREATOR_FILE_NAME), branch]
    try:
        completed = subprocess.run(command, cwd=top_level, capture_output=True, text=True,
                                   stdin=subprocess.DEVNULL, timeout=WORKTREE_CREATOR_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        raise StepFailed(f"{shlex.join(command)} did not finish in {WORKTREE_CREATOR_TIMEOUT_SECONDS} seconds, "
                         f"so no topic-worktree for {branch} was made") from None
    if completed.returncode != 0:
        raise StepFailed(f"no worktree of this clone has {branch} checked out, and {shlex.join(command)}, run to "
                         f"make one, exited {completed.returncode}. Do what its message says, then run this "
                         "again. It printed:\n" + (completed.stdout + completed.stderr).strip())
    return Path(completed.stdout.strip())


def topic_worktree_at_frozen_head(number, branch, frozen_head):
    """The pull request's topic-worktree, made when this clone has none; refuse unless it is clean at frozen_head."""
    worktree = topic_worktree_of_branch(branch) or topic_worktree_made_by_creator(branch)
    in_worktree = ["-C", str(worktree)]
    # Ignored files, the answers file among them, are left out: they never reach a commit.
    changed = git_output.nul_separated_fields(git([*in_worktree, "status", "--porcelain", "-z",
                                                   "--untracked-files=all"]))
    quoted = shlex.quote(str(worktree))
    if changed:
        raise Refused(f"Pull request {number}'s topic-worktree {worktree} has uncommitted changes or untracked "
                      "files, so the fix-round's commit would carry them: "
                      + ", ".join(entry[3:] for entry in changed) + ".\n"
                      "If a fix-round subagent is still working there, wait for it to finish.\n"
                      "If they are your own work, finish it elsewhere or set it aside first; the fix-round waits.\n"
                      "If an earlier fix-round subagent left them, read them, keep what the next subagent "
                      f"should know, then remove them with git -C {quoted} restore --staged --worktree . and "
                      f"git -C {quoted} clean -d --force, which leaves the ignored answers file in place.\n"
                      "Then run this again.")
    head = git([*in_worktree, "rev-parse", "HEAD"]).strip()
    if head == frozen_head:
        return worktree
    if subprocess.run(["git", *in_worktree, "cat-file", "-e", f"{frozen_head}^{{commit}}"], capture_output=True,
                      stdin=subprocess.DEVNULL, timeout=git_output.GIT_TIMEOUT_SECONDS).returncode != 0:
        git([*in_worktree, "fetch", "--quiet", "origin"])
    if is_ancestor(head, frozen_head):
        raise Refused(f"Pull request {number}'s topic-worktree {worktree} is at {head[:12]}, behind the "
                      f"frozen-head {frozen_head[:12]} that merge-lane-2 reviewed.\n"
                      f"Bring it up to the frozen-head with git -C {quoted} merge --ff-only {frozen_head}, "
                      "then run this again.")
    raise Refused(f"Pull request {number}'s topic-worktree {worktree} is at {head[:12]}, which holds commits "
                  f"that the frozen-head {frozen_head[:12]}, which merge-lane-2 reviewed, does not, such as a "
                  "fix-round commit that was never pushed. A fix-round starts from the frozen-head.\n"
                  "If a fix-round subagent made that commit for this round and stopped before its push, finish "
                  f"the round instead: run cd {quoted} && python3 {PROGRAM} {number} --check, and do what it says.\n"
                  f"Otherwise keep those commits on a branch of their own and move {branch} back with git -C {quoted} "
                  f"branch <a new branch name> HEAD && git -C {quoted} reset --keep {frozen_head}, then run this "
                  "again, and tell the next subagent about the kept branch if it holds a fix to reuse.")


def print_brief(number, reviewer_login):
    (url, head, branch, review_link, frozen_head, findings, nits,
     fix_round_number, _unrecorded_review_ids, _review_submitted_at) = round_facts(number, reviewer_login)
    if head != frozen_head:
        raise Refused(f"Pull request {url} has head {head}, but merge-lane-2 reviewed {frozen_head}; "
                      "a commit was pushed after the review, so this fix-round has already pushed.\n"
                      "Wait for merge-lane-2's review of the new head, and run this again if it "
                      "requests changes.")
    conflict_report = conflict_check_report(number)
    if conflict_report is not None:
        print("\n".join([f"Pull request {url} is not given a fix-round.", f"Frozen-head: {frozen_head}",
                         f"The round's reviews: {review_link}", "", *conflict_report, "",
                         REPLACE_INSTEAD_OF_ROUND_INSTRUCTION.format(number=number)]))
        return
    worktree = topic_worktree_at_frozen_head(number, branch, frozen_head)
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
    if nits:
        lines += ["", f"Nits to fix in this round too ({len(nits)}), word for word, numbered on from the "
                      "blocking findings:"]
    for index, nit in enumerate(nits, len(findings) + 1):
        lines += ["", f"{index}. {finding_place(nit)} ({nit.get('html_url')})", (nit.get("body") or "").strip()]
    answers_name = ANSWERS_FILE_NAME_FORMAT.format(number=number)
    in_worktree = f"cd {shlex.quote(str(worktree))} && "
    check_command = f"{in_worktree}python3 {PROGRAM} {number} --check"
    lines += [
        "",
        TOPIC_WORKTREE_DISPATCH_INSTRUCTION.format(number=number, worktree=worktree),
        AUTHOR_INSTRUCTION_WHEN_FIX_ROUND_SUBAGENT_HANDS_BACK_NEW_SHARED_NAMES_TO_CHECK,
        TOPIC_WORKTREE_CLEANUP_INSTRUCTION.format(worktree=worktree, quoted=shlex.quote(str(worktree)),
                                                  program=PROGRAM, number=number),
        "",
        f"For the subagent, the rules of the round, in order, run in the pull request's topic-worktree {worktree}, "
        f"on its branch {branch} at the frozen-head: edit only files under it, and start every command you run "
        f"with {in_worktree.strip()}, as each command below does.",
        f"1. Before changing anything, run: {in_worktree}python3 scripts/branch-conflict-check.py --pull-request {number}",
        "   If it reports VERDICT: CONFLICT with ANSWER: replace, stop and tell the agent that dispatched you "
        f"what it printed: that agent runs python3 {PROGRAM} {number} again, which prints what to do instead.",
        "   If it reports VERDICT: CONFLICT with any other answer, do what its report says.",
        "2. Check each finding against the code. Fix each one that holds, root cause included, "
        "with a test that fails without the fix; a nit needs no test.",
        GUARDED_FILE_CHANGE_CARRYING_OUT_USER_RULING_INSTRUCTION,
        "3. Change nothing else, apart from the tests, callers, documents and citations that "
        "keep the pull request atomic. Findings that do not block, in this review or any other, "
        "are not part of this round, apart from the nits listed above: merge-lane-2 sends them after the merge.",
        MOVE_CHANGE_TO_OWN_PULL_REQUEST_INSTRUCTION.format(program=PROGRAM, number=number,
                                                           worktree=shlex.quote(str(worktree)),
                                                           pull_request_branch=branch),
        "4. Put every change in one commit on top of the branch as step 1 left it. "
        "If no finding holds, make no commit.",
        f"5. Write the answers file {worktree / answers_name}, replacing any earlier round's file there, with "
        "one entry per finding above, each starting \"<n>. \" on its own line, with any further lines of the "
        "entry after it: what you fixed, why the finding does not hold, or, for a change moved as "
        "step 3 says, the new pull request. Never commit it: "
        "the branch's .gitignore may not leave it out, and the check in step 6 refuses a commit "
        "that holds it.",
        f"6. Run the check: {check_command}",
        "   If it refuses, change the "
        "answers file or the unpushed commit as it says (git commit --amend is allowed before the "
        "push; first stage each changed file with git add <path>, never the answers file) and run the "
        "check again. Before the push, the check runs the nc-test-suites, which can "
        "take many minutes, and refuses when one fails because of the round's change. Before the suites, "
        "it refuses when the round's commit adds shared names no agent has checked; do what it prints.",
        f"7. When it passes with a commit not yet pushed, push once, with: {in_worktree}git push origin HEAD:{shlex.quote(branch)}",
        "   Then run the same check command "
        "again. When it passes and prints a message for merge-lane-2, which it does at once if you "
        "made no commit, after recording on the pull request, in a comment, which reviews this round "
        "answered, send that message to merge-lane-2 with SendMessage.",
        "8. If anything fails after the push, do not push again or rewrite the branch: tell "
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


def read_answers(path, blocking_count, nit_count):
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
    finding_count = blocking_count + nit_count
    expected = set(range(1, finding_count + 1))
    missing = sorted(expected - answers.keys())
    extra = sorted(answers.keys() - expected)
    if missing or extra:
        problems = []
        if missing:
            problems.append(f"no entry for finding {', '.join(map(str, missing))}")
        if extra:
            problems.append(f"an entry for finding {', '.join(map(str, extra))}, which does not exist")
        nits = f" and {nit_count} nit{'' if nit_count == 1 else 's'}" if nit_count else ""
        raise Refused(f"The answers file {path} has {' and '.join(problems)}; the review has "
                      f"{blocking_count} blocking findings{nits}.\n"
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
            if completed.returncode == 0:  # pragma: no mutate, returncode is 0 or 1 here, so `<=` matches only 0 as `==` does
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


def file_exists_at(commit, path):
    return subprocess.run(["git", "cat-file", "-e", f"{commit}:{path}"], capture_output=True,
                          stdin=subprocess.DEVNULL, timeout=git_output.GIT_TIMEOUT_SECONDS).returncode == 0


def failing_suites_in_scratch_worktree(commit, command_for_checkout):
    """Run the suite runner command_for_checkout(checkout) names in a scratch worktree of commit, passing
    its output through as it arrives; return each suite it reports failing, once, in its order."""
    failing = []
    unfinished = []
    with tempfile.TemporaryDirectory(prefix="fix-round-check-suites-") as scratch:
        checkout = Path(scratch) / "checkout"
        git(["worktree", "add", "--quiet", "--detach", str(checkout), commit])
        try:
            command = command_for_checkout(checkout)
            print(f"Running the nc-test-suites in a scratch worktree of {commit[:12]}: {shlex.join(command)}",
                  flush=True)
            with subprocess.Popen(command, cwd=checkout, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                  text=True) as runner:
                for line in runner.stdout:
                    sys.stdout.write(line)
                    sys.stdout.flush()
                    if line.startswith(test_suite_runner.FAILED_SUITE_LINE_PREFIX):
                        suite = line[len(test_suite_runner.FAILED_SUITE_LINE_PREFIX):].split(" ", 1)[0].strip()
                        if suite not in failing:
                            failing.append(suite)
                    elif line.startswith((test_suite_runner.NOT_RUN_SUITE_LINE_PREFIX,
                                          *test_suite_runner.TEST_RUNNER_WHOLE_RUN_NOT_RUN_TO_THE_END_LINE_PREFIXES_FILE_PATH_AND_BARE_NAME_FORMS)):
                        unfinished.append(line.strip())
            status = runner.returncode
        finally:
            git(["worktree", "remove", "--force", str(checkout)])
    # The runner exits 1 when a suite failed even if others never ran, so a failure the
    # frozen-head shares must not let an unfinished run through.
    if unfinished:
        raise StepFailed(f"the suite runner, {shlex.join(command)}, run on {commit[:12]}, did not judge every "
                         "suite: it printed\n" + "".join(f"  {line}\n" for line in unfinished)
                         + "Its output is above. Nothing was pushed.\n"
                         "Run this --check again once, not the suite runner by itself.\n"
                         "If the runner again prints a line opening 'NOT RUN' or "
                         + " or ".join(f"'{prefix}'" for prefix in test_suite_runner.TEST_RUNNER_WHOLE_RUN_NOT_RUN_TO_THE_END_LINE_PREFIXES_FILE_PATH_AND_BARE_NAME_FORMS)
                         + ", tell merge-lane-2 with SendMessage, quoting each such line, and do "
                         "not push.")
    if status == test_suite_runner.EXIT_ALL_PASSED or (status == test_suite_runner.EXIT_SOME_FAILED and failing):
        return failing
    raise StepFailed(f"the suite runner, {shlex.join(command)}, run on {commit[:12]}, ended with "
                     f"{test_suite_runner.describe_exit(status)} and named no failing suite, so it stopped "
                     "before judging every suite; its output is above. Nothing was pushed.\n"
                     "Run the check again once. If the runner stops the same way, tell merge-lane-2 with "
                     "SendMessage what it printed, and do not push.")


def suites_the_round_broke_and_suites_failing_at_frozen_head_too(frozen_head, commit):
    """Run the suites at commit, and those that fail there at frozen_head too; return
    (failing at commit only, failing at both)."""
    at_commit = failing_suites_in_scratch_worktree(commit, ready_command.selective_test_run_command)
    at_frozen_head = [suite for suite in at_commit if file_exists_at(frozen_head, suite)]
    if at_frozen_head:
        failing_there = failing_suites_in_scratch_worktree(frozen_head, lambda checkout: [
            "python3", str(checkout / "scripts" / "run-all-test-suites.py"),
            "--leave-recorded-inputs-and-failure-history-unchanged", "--only-suites-named", *at_frozen_head])
        at_frozen_head = [suite for suite in at_frozen_head if suite in failing_there]
    return [suite for suite in at_commit if suite not in at_frozen_head], at_frozen_head


def suites_failing_at_frozen_head_too_record_path():
    return Path(git(["rev-parse", "--absolute-git-dir"]).strip()) / PULL_REQUEST_FIX_ROUND_CHECK_TEST_SUITES_ALSO_FAILING_AT_FROZEN_HEAD_RECORD_FILE_NAME


def suites_failing_at_frozen_head_too_recorded_for(commit):
    path = suites_failing_at_frozen_head_too_record_path()
    if not path.exists():
        return []
    record = json.loads(path.read_text())
    return record["suites"] if record["commit"] == commit else []


def refuse_new_shared_names_the_dispatching_agent_has_not_checked(number, frozen_head, commit):
    try:
        names = new_shared_names_lister.new_shared_names_in_files_changed_since(Path.cwd(), frozen_head, commit)
    except new_shared_names_lister.GitFailure as failure:
        raise StepFailed(f"the new shared names the round's commit adds could not be listed: {failure}") from None
    if names:
        raise Refused(new_shared_names_lister.unchecked_new_shared_names_refusal_text(
            names, "The check stopped before the nc-test-suites, and nothing may be pushed yet",
            "Make every rename in the round's one commit: stage each changed file with git add <path>, never the "
            "answers file, and run git commit --amend.",
            "the same check command again, with "
            f"{new_shared_names_lister.CONFIRM_DISPATCHING_AGENT_CHECKED_NEW_SHARED_NAMES_COMMAND_LINE_FLAG} added"))


def refuse_outside_topic_worktree(number, branch):
    """The round's commit and answers file are in the topic-worktree, so --check runs nowhere else."""
    here = git(["branch", "--show-current"]).strip()
    if here == branch:
        return
    worktree = topic_worktree_of_branch(branch)
    where = (f"Run it there: cd {shlex.quote(str(worktree))} && python3 {PROGRAM} {number} --check"
             if worktree else
             f"No worktree of this clone has {branch} checked out: run python3 {PROGRAM} {number}, which makes "
             "one and prints the fix-round brief.")
    raise Refused(f"--check runs only in pull request {number}'s topic-worktree, the worktree that has its branch "
                  f"{branch} checked out, but this worktree, {worktree_root()}, is on "
                  f"{here or 'a detached HEAD'}.\n" + where)


def refuse_answers_written_before_review(answers_path, review_submitted_at, review_link):
    """An answers file older than the round's latest changes-requested review answers an earlier round; read_answers
    has read the file already."""
    if not review_submitted_at:
        return
    written = os.stat(answers_path).st_mtime
    # Python before 3.11 reads no "Z" suffix, and GitHub writes one.
    submitted = datetime.datetime.fromisoformat(review_submitted_at.replace("Z", "+00:00")).timestamp()
    if written < submitted:
        raise Refused(f"The answers file {answers_path} was last written before merge-lane-2 submitted the "
                      f"review that opened this round ({review_link}), so it answers an earlier round.\n"
                      "Write this round's answers into it, one entry per finding of this round's brief, and "
                      "run the check again.")


def origin_branch_head(url, branch):
    """The commit origin's branch points at now; GitHub's headRefOid can lag a push by seconds."""
    ref = f"refs/heads/{branch}"
    for line in git(["ls-remote", "origin", ref]).splitlines():
        commit, _, name = line.partition("\t")
        if name == ref:
            return commit
    raise StepFailed(f"git ls-remote origin {ref} found no branch {branch} on origin, though pull request {url} "
                     "names it as its head branch, so the round's commit is not on origin, and whether the pull "
                     "request still takes pushes to that branch is in doubt.\n"
                     "Do not push.\n"
                     "Send merge-lane-2 this message with Claude Code's SendMessage tool: \"The fix-round check of "
                     f"{url} found no branch {branch} on origin, so the round's commit is not pushed.\" The round "
                     "stops there, and merge-lane-2's answer says how it goes on.")


def check_round(number, reviewer_login, answers_path, commit_name, after_conflict_merge,
                confirm_dispatching_agent_checked_new_shared_names=False):
    (url, _github_head, branch, review_link, frozen_head, blocking, nits,
     _fix_round_number, unrecorded_review_ids, review_submitted_at) = round_facts(number, reviewer_login)
    findings = blocking + nits
    answers_path = answers_path or default_answers_path(number)
    refuse_outside_topic_worktree(number, branch)
    answers = read_answers(answers_path, len(blocking), len(nits))
    refuse_answers_written_before_review(answers_path, review_submitted_at, review_link)
    refuse_moved_to_missing_pull_request(answers, answers_path)
    commit = git(["rev-parse", "--verify", f"{commit_name}^{{commit}}"]).strip()
    refuse_moved_change_still_here(answers, commit, answers_path)
    git(["cat-file", "-e", f"{frozen_head}^{{commit}}"])
    fix_range = fix_commit_range(frozen_head, commits_since(frozen_head, commit), after_conflict_merge)
    refuse_committed_answers_file(frozen_head, commit)
    leftovers = unnamed_files(*(fix_range or (None, None)), findings)
    lines = [f"PASS: the fix-round on {url} keeps to its rules; {len(findings)} findings answered."]
    if leftovers:
        lines += ["Files the fix commit changes that no blocking finding or nit names; say in the message "
                  "why each belongs in this round, or take it out:"]
        lines += [f"  {path}" for path in leftovers]
    head = origin_branch_head(url, branch)
    if head not in (commit, frozen_head):
        raise Refused(f"origin's branch {branch} of {url} is at {head}, which is neither the checked commit "
                      f"{commit} nor the frozen-head {frozen_head}.\n"
                      "Check --commit names what you pushed; if someone else pushed, tell "
                      "merge-lane-2 with SendMessage.")
    if head == frozen_head and commit != frozen_head:
        if not confirm_dispatching_agent_checked_new_shared_names:
            refuse_new_shared_names_the_dispatching_agent_has_not_checked(number, frozen_head, commit)
        broken, failing_at_frozen_head_too = suites_the_round_broke_and_suites_failing_at_frozen_head_too(
            frozen_head, commit)
        if broken:
            too = (f" These fail at the frozen-head too, so they are not the round's doing: "
                   f"{', '.join(failing_at_frozen_head_too)}." if failing_at_frozen_head_too else "")
            raise Refused(f"The round does not pass: these nc-test-suites fail at the round's commit {commit[:12]} "
                          f"and not at the frozen-head {frozen_head[:12]}, so the round's change broke them: "
                          f"{', '.join(broken)}. Each one's log is named in the runner's output above.{too}\n"
                          "Fix the cause of each failure in the round's commit, which is not pushed yet, amend "
                          "it with git commit --amend, and run the check again.\n"
                          "If a suite named here fails for a cause outside the round's change, such as a test "
                          "case that fails only now and then, run the check again once; if that suite fails "
                          "again, tell merge-lane-2 with SendMessage the suite and its log, and do not push.")
        suites_failing_at_frozen_head_too_record_path().write_text(
            json.dumps({"commit": commit, "suites": failing_at_frozen_head_too}))
        if failing_at_frozen_head_too:
            lines += ["These nc-test-suites fail at the round's commit and at the frozen-head too, so not "
                      "because of this round; the message for merge-lane-2 will name them: "
                      + ", ".join(failing_at_frozen_head_too)]
        lines += ["Not pushed yet. Push once, then run this same command again to get the message "
                  "for merge-lane-2."]
        print("\n".join(lines))
        return
    pushed = (f"New head {commit}, one fix-round on top of the frozen-head {frozen_head}."
              if commit != frozen_head else
              f"Nothing pushed; the head stays the frozen-head {frozen_head}.")
    message = [f"Fix-round on pull request {url}, answering the round's reviews "
               f"{review_link}. {pushed}"]
    message += [f"{index}. {finding_place(findings[index - 1])}{' (nit)' if index > len(blocking) else ''}: "
                f"{answers[index]}" for index in answers]
    if leftovers:
        message += ["Files the fix commit changes that no blocking finding or nit names: "
                    + ", ".join(leftovers) + ". Why each belongs: <fill in>"]
    recorded_suites = suites_failing_at_frozen_head_too_recorded_for(commit) if commit != frozen_head else []
    if recorded_suites:
        message += ["nc-test-suites that fail at the frozen-head too, so not because of this round: "
                    + ", ".join(recorded_suites) + "."]
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
                      "Switch to the pull request's branch, and run this again.")
    return branch


def push_time_limit_seconds():
    """The pre-push hook's own time budgets, as scripts/ghi-issue-write.py sizes its pushes."""
    # Loaded here, not at import, so that only a move's push pays for loading that program and its hooks.
    spec = importlib.util.spec_from_file_location("ghi_issue_write", Path(__file__).resolve().parent / "ghi-issue-write.py")
    ghi_issue_write = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ghi_issue_write)
    return ghi_issue_write.push_time_limit_seconds(os.environ)


def local_branch_exists(branch):
    return bool(git(["branch", "--list", branch]).strip())


def move_start(number, reviewer_login, new_branch, whole_file_paths):
    (_url, _head, pull_request_branch, _review_link, frozen_head, _findings, _nits,
     _fix_round_number, _unrecorded_review_ids, _review_submitted_at) = round_facts(number, reviewer_login)
    state_path = move_state_path()
    if state_path.exists():
        state = json.loads(state_path.read_text())
        raise Refused(f"A move to {state['new_branch']} is already under way in this worktree.\n"
                      f"Finish it with python3 {PROGRAM} {number} --move-change-to-own-pull-request-finish "
                      "before you start another.")
    if current_branch() != pull_request_branch:
        raise Refused(f"--move-change-to-own-pull-request-cut-new-topic-branch runs on the pull request's branch {pull_request_branch}, but this worktree is on "
                      f"{current_branch()}.\n"
                      f"Switch to {pull_request_branch} and run this again.")
    if git(["rev-parse", "HEAD"]).strip() == frozen_head:
        raise Refused("The round has no commit on top of the frozen-head yet, so nothing has undone the change "
                      "this branch is to lose.\n"
                      "Make step 4's one commit first, undoing the moved change in it, then run this again.")
    if local_branch_exists(new_branch):
        raise Refused(f"A local branch {new_branch} already exists.\n"
                      "Name a new topic branch that does not exist yet, and run this again.")
    missing = [path for path in whole_file_paths if not file_exists_at(frozen_head, path)]
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
    git(["switch", "-q", "--no-overwrite-ignore", "-c", new_branch, "origin/main"])
    if whole_file_paths:
        git(["checkout", frozen_head, "--", *whole_file_paths])
    state_path.write_text(json.dumps({"new_branch": new_branch, "return_branch": pull_request_branch,
                                      "answers": str(answers), "set_aside": str(set_aside)}))
    if answers.exists():
        set_aside.parent.mkdir(exist_ok=True)
        shutil.move(answers, set_aside)
    print(f"On {new_branch}, cut from origin/main, with {len(whole_file_paths)} whole file(s) copied from the "
          f"frozen-head {frozen_head[:12]}.\n"
          "Make by hand the moved part of each file that is only partly moved, and leave it uncommitted: the "
          "finish step runs the tests and commits it. Write the new pull request's description in a file outside "
          "this worktree, then run:\n"
          f"python3 {PROGRAM} {number} --move-change-to-own-pull-request-finish --title <title> "
          "--body-file <description file>")


def move_finish(number, title, body_file):
    state_path = move_state_path()
    if not state_path.exists():
        raise Refused("No move is under way in this worktree.\n"
                      f"Start one with python3 {PROGRAM} {number} "
                      "--move-change-to-own-pull-request-cut-new-topic-branch <new topic branch> [<path> ...].")
    state = json.loads(state_path.read_text())
    new_branch, return_branch = state["new_branch"], state["return_branch"]
    answers, set_aside = Path(state["answers"]), Path(state["set_aside"])
    if current_branch() != new_branch:
        raise Refused(f"--move-change-to-own-pull-request-finish runs on {new_branch}, which "
                      "--move-change-to-own-pull-request-cut-new-topic-branch made, but this worktree is on "
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
    if git(["rev-list", "--count", "origin/main..HEAD"]).strip() != "0":  # pragma: no mutate, a count has no leading zero, so `>` matches every count but "0" as `!=` does, and so does `is not`, as CPython keeps one "0" string
        head = git(["rev-parse", "HEAD"]).strip()
        base = git(["merge-base", "HEAD", "origin/main"]).strip()
        raise Refused(f"{new_branch} already holds commit {head[:12]} beside origin/main, and this step must make "
                      "the moved change's only commit itself, after its test run.\n"
                      "If an earlier run of this step made the commit and then failed, do by hand the steps still "
                      "to do that its message listed, instead of running it again.\n"
                      f"Otherwise undo the commit, keeping its changes staged, with git reset --soft {base}, then "
                      "run this again: it runs the tests and commits the moved change.")
    git(["add", "-A"])
    if not git(["diff", "--cached", "--name-only"]).strip():
        raise Refused(f"{new_branch} holds no change beside origin/main, so there is nothing to move.\n"
                      "Bring the moved change onto it, by hand or by naming whole files to "
                      "--move-change-to-own-pull-request-cut-new-topic-branch, and run this again.")
    test_command = ready_command.selective_test_run_command(root)
    tests = subprocess.run(test_command, cwd=root, stdin=subprocess.DEVNULL)
    if tests.returncode:
        raise Refused(f"The test command exited {tests.returncode} on {new_branch}: {shlex.join(test_command)}\n"
                      f"Fix the moved change on {new_branch} and run this again; nothing is committed yet.")
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as message:
        message.write(title + "\n\n" + Path(body_file).read_text())
    try:
        git(["commit", "-q", "-F", message.name])
    finally:
        os.unlink(message.name)
    commit = git(["rev-parse", "HEAD"]).strip()
    created = {}
    hook_output = []

    def push():
        # git() shows stderr only on failure, and the pre-push hook writes to stderr, with exit 0, on a
        # push it checked and on one it let through without a check alike.
        try:
            pushed = subprocess.run(["git", "push", "-q", "origin", new_branch], capture_output=True, text=True,
                                    stdin=subprocess.DEVNULL, timeout=push_time_limit_seconds())
        except subprocess.TimeoutExpired:
            raise StepFailed(f"git push origin {new_branch} ran past {push_time_limit_seconds()} seconds") from None
        if pushed.returncode:
            raise StepFailed(f"git push origin {new_branch} failed: {pushed.stderr.strip()}")
        hook_output.extend(line for line in pushed.stderr.splitlines() if line.strip())

    def open_pull_request():
        created["url"] = gh(["pr", "create", "--base", "main", "--head", new_branch, "--title", title,
                             "--body-file", body_file]).strip().splitlines()[-1]

    def restore_answers():
        if set_aside.exists():
            shutil.move(set_aside, answers)

    def delete_branch():
        git(["branch", "-D", new_branch])
        if local_branch_exists(new_branch):
            raise StepFailed(f"git branch -D {new_branch} left the branch in place")

    steps = [(f"push {new_branch} with git push origin {new_branch}", push),
             (f"open its pull request with gh pr create --base main --head {new_branch}, if gh pr list --head "
              f"{new_branch} shows none", open_pull_request),
             (f"git switch {return_branch}", lambda: git(["switch", "-q", return_branch])),
             (f"move {set_aside} back to {answers} if it is there", restore_answers),
             (f"git branch -D {new_branch}", delete_branch),
             (f"delete {state_path}", state_path.unlink)]
    def labelled_hook_output():
        if not hook_output:
            return ""
        return ("\n\nThe pre-push hook, scripts/git-client-side-hooks/pre-push, printed the lines below on stderr "
                "during the push. If they say a check did not run, as in \"was not checked\", \"goes ahead "
                "without\" or \"lets the push through without checking\", run the check they name, as they say. "
                "When the check that did not run is the one for mutation-testing worktrees or the one for open pull "
                "requests' head branches, there is nothing to run: this push came from the pull request's own "
                "worktree and pushed a new branch, so neither check would have refused it. Either way, tell the "
                "user, as those lines say:\n" + "\n".join(hook_output))

    for index, (_description, step) in enumerate(steps):
        try:
            step()
        except (StepFailed, OSError) as failure:
            done = "".join(f"; {description}" for description, _step in steps[:index])
            still_to_do = "; ".join(description for description, _step in steps[index:])
            raise StepFailed(f"{failure}. Nothing was rolled back. Done: the moved change is committed on {new_branch} as "
                             f"{commit[:12]}{done}. Still to do, in order: {still_to_do}. Do these by hand; running "
                             "the program again refuses, because the branch already holds the commit."
                             + labelled_hook_output()) from None
    url = created["url"]
    print(f"Moved to {url}; you are back on {return_branch}.\n"
          f"Answer each finding whose change you moved in the answers file, {answers}, with an entry that starts "
          f"with that finding's number, as every entry does: <n>. {MOVED_TO_PULL_REQUEST_PREFIX}{url}"
          + labelled_hook_output())


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
    parser.add_argument(new_shared_names_lister.CONFIRM_DISPATCHING_AGENT_CHECKED_NEW_SHARED_NAMES_COMMAND_LINE_FLAG, action="store_true",
                        help="with --check: the agent that dispatched the round has checked the shared names "
                             "the round's commit adds, and its renames are in that commit")
    parser.add_argument("--reviewer-login", default=MERGE_LANE_2_REVIEWER_LOGIN,
                        help=f"merge-lane-2's GitHub account (default: {MERGE_LANE_2_REVIEWER_LOGIN})")
    parser.add_argument("--move-change-to-own-pull-request-cut-new-topic-branch", dest="move_start", nargs="+",
                        metavar=("NEW_TOPIC_BRANCH", "PATH"),
                        help="after the round's commit: cut NEW_TOPIC_BRANCH from origin/main and copy each "
                             "PATH, a file whose every change moves, whole from the frozen-head")
    parser.add_argument("--move-change-to-own-pull-request-finish", dest="move_finish", action="store_true",
                        help="test, commit, push and open the moved change's pull request, then switch back")
    parser.add_argument("--title", help="with --move-change-to-own-pull-request-finish: the new pull request's title")
    parser.add_argument("--body-file",
                        help="with --move-change-to-own-pull-request-finish: the new pull request's description file")
    arguments = parser.parse_args(argv)
    if arguments.move_finish and not (arguments.title and arguments.body_file):
        parser.error("--move-change-to-own-pull-request-finish needs --title and --body-file")
    try:
        if arguments.move_start:
            move_start(arguments.number, arguments.reviewer_login, arguments.move_start[0],
                       arguments.move_start[1:])
        elif arguments.move_finish:
            move_finish(arguments.number, arguments.title, arguments.body_file)
        elif arguments.check:
            check_round(arguments.number, arguments.reviewer_login, arguments.answers,
                        arguments.commit, arguments.after_conflict_merge,
                        arguments.confirm_dispatching_agent_checked_new_shared_names)
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
