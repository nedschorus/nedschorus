#!/usr/bin/env python3
"""Refuse a push that rewrites the head branch of an open pull request on origin, or that deletes
the head branch of any open pull request on origin; and before a forced update to a branch on
origin goes through, save the commit it replaces under refs/force-pushed-old-heads/.

Run by scripts/git-client-side-hooks/pre-push with git's pre-push arguments and the pushed refs
on standard input. Exit 10 refuses the push; exit 0 lets it through. Any other exit makes the
hook say the push went unchecked and to tell the user.

Reviews are of a pull request's pushed head, so an update that does not build on that head
replaces the commits under review, and deleting the head branch closes the pull request.
Whether an open pull request's head may be rewritten is the rebase-or-replace answer of
nc-systems/general-tools/pull-request-conflict-with-main-rebase-or-replace-answer-common.py:
the replace answer refuses the update. That answer is replace for every open pull request until
the module turns on the rebase answer for a draft never marked ready; only then is GitHub asked
whether a draft was ever ready, which it was when its timeline holds a ready_for_review event,
or a convert_to_draft event, the only record left by a pull request opened ready and later
turned back into a draft.
git rejects an unforced non-fast-forward update before this hook runs, so the updates this
check refuses are forced ones, whatever command spelling sent them. GitHub's ruleset refuses
every non-fast-forward update to any branch, so this check only refuses one first, with the
remedy; the ruleset does not refuse a deletion.

Only branches on origin are checked. A new branch and a fast-forward are let through without
asking GitHub. Every other update to a branch is let through only when `gh pr list` answers
that the branch has no open pull request, or the rebase-or-replace answer for its open pull
request is rebase; GitHub then refuses it. A deletion is let through only when the
branch has no open pull request. When gh cannot answer either question, the push is refused,
because a forced update cannot be undone by the agent that sent it. When git cannot say whether
an update is a fast-forward, the push is refused too, after the other updates are checked, since
a forced update would go through with the commit it replaces saved nowhere. A remote commit
missing from the local repository cannot be shown to be an ancestor, so the update counts as
not a fast-forward.

A forced update this check lets through is sent only after its replaced commit is saved
under refs/force-pushed-old-heads/<branch>/<commit hash>, fetched from origin first when this
repository lacks it; when it cannot be saved, the push is refused. Nothing deletes these refs.
A push made with --no-verify skips this hook, and so skips the save.

ESCAPE_HATCH_ASSIGNMENT in front of the git push command lets a push merge-lane-2 asked for
through without the open pull request check; its forced updates' replaced commits are still
saved. .claude/guard-hooks/force-push-with-open-pull-request-guard-hook.py reads the same
assignment.
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

_rebase_or_replace_spec = importlib.util.spec_from_file_location(
    "pull_request_conflict_with_main_rebase_or_replace_answer_common",
    Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
    / "pull-request-conflict-with-main-rebase-or-replace-answer-common.py")
rebase_or_replace = importlib.util.module_from_spec(_rebase_or_replace_spec)
_rebase_or_replace_spec.loader.exec_module(rebase_or_replace)

EXIT_ALLOW_PUSH = 0
EXIT_REFUSE_PUSH = 10

CHECKED_REMOTE_NAME = "origin"
BRANCH_REF_PREFIX = "refs/heads/"
MESSAGE_PREFIX = "pre-push: "
GH_TIMEOUT_SECONDS = 10.0
GIT_TIMEOUT_SECONDS = 10.0
GIT_FETCH_TIMEOUT_SECONDS = 60.0
FORCE_PUSHED_OLD_HEAD_REF_PREFIX = "refs/force-pushed-old-heads/"
ESCAPE_HATCH_VARIABLE = "CLAUDE_MERGE_LANE_ASKED_FOR_THIS_REWRITE"
ESCAPE_HATCH_ASSIGNMENT = ESCAPE_HATCH_VARIABLE + "=1"

REWRITE_REFUSAL = (
    "this push is refused, because its update to branch {branch} does not build on "
    "origin/{branch}, the commits already pushed, and {branch} is the head of open pull request {pull_request}, which "
    "{ready_state}.")
READY_NOW = "is ready for review: the update would replace the commits under review"
DRAFT_ONCE_READY = ("is a draft now but was once ready for review: the update would replace the "
                    "commits under review")
DRAFT_HEAD_NOT_REWRITTEN = (
    "is a draft: no open pull request's head is rewritten, and one that conflicts with main is "
    "replaced by a new pull request")
DELETION_REFUSAL = (
    "this push is refused, because it deletes branch {branch}, the head of open pull request "
    "{pull_request}: deleting the head branch closes the pull request.")
REWRITE_INSTRUCTIONS = [
    "If you are adding work to the branch: run git fetch origin {branch}, put your change in a "
    "new commit on top of origin/{branch}, and push without --force.",
    "If the branch conflicts with main: run python3 scripts/branch-conflict-check.py --pull-request "
    "{number}, and do what it reports.",
    "If you already rebased or amended the branch locally: keep that work on another branch "
    "(git branch {branch}-rewritten), go back to the pushed head (git switch -C {branch} "
    "origin/{branch}), and redo your change as a new commit.",
    "If you are force-pushing to restore what an earlier force push replaced: stop, leave the "
    "branch as it is, and message merge-lane-2 with SendMessage (ListAgents lists its address).",
]
DELETION_INSTRUCTIONS = [
    "If the pull request should be closed: close it with a comment that says why (gh pr close "
    "{number} --comment '<why>'), then push the deletion again.",
]
ESCAPE_HATCH_INSTRUCTION = (
    "If merge-lane-2 asked you for this push: run it again with " + ESCAPE_HATCH_ASSIGNMENT
    + " directly in front of the git push command.")
LOOKUP_FAILED_REFUSAL = (
    "this push is refused, because it {action} branch {branch} on origin, and whether {branch} "
    "has an open pull request could not be checked: {detail}.")
READY_LOOKUP_FAILED_REFUSAL = (
    "this push is refused, because it forces an update to branch {branch} on origin, the head "
    "of draft pull request {pull_request}, and whether that pull request was ever ready for "
    "review could not be checked: {detail}. A draft's head may be rewritten only while it has "
    "never been ready for review, because until then nobody reviews it; once it has been ready, "
    "a review may hold its pushed commits, and the update would replace them.")
# totalCount counts the whole timeline whatever itemTypes asks for; only filteredCount counts the events asked for.
EVER_READY_QUERY = (
    "query($id: ID!) { node(id: $id) { ... on PullRequest { timelineItems(itemTypes: "
    "[READY_FOR_REVIEW_EVENT, CONVERT_TO_DRAFT_EVENT]) { filteredCount } } } }")
LOOKUP_FAILED_INSTRUCTION = (
    "Tell the user this whole message, and do not push {branch} again until he answers.")
OLD_HEAD_SAVE_FAILED_REFUSAL = (
    "this push is refused, because it forces an update to branch {branch} on origin, and the "
    "commit that update replaces there, {old_head}, could not first be saved under {ref}: "
    "{detail}. A forced update leaves the commits it replaces on no branch of origin, so this "
    "hook first keeps them under that ref in this repository, which lets the update be undone.")
OLD_HEAD_SAVE_FAILED_INSTRUCTIONS = [
    "If the cause this message gives is one you can fix, such as a failed fetch from origin or a "
    "full disk, fix it and push again.",
    "Otherwise tell the user this whole message, and do not push {branch} again until he "
    "answers.",
]
FAST_FORWARD_CHECK_FAILED_REFUSAL = (
    "this push is refused, because whether its update to branch {branch} on origin builds on "
    "origin/{branch} could not be checked, as the lines after the instructions say. An update that "
    "does not build on it is a forced update, which goes through only after the commit it "
    "replaces is saved.")
OLD_HEAD_SAVED_NOTE = ("the commit this push replaces on branch {branch}, {old_head}, is saved "
                       "under {ref}.")


class OpenPullRequestLookupFailed(Exception):
    """gh could not say whether a branch has an open pull request."""


class ReadyHistoryLookupFailed(Exception):
    """gh could not say whether a draft pull request was ever ready for review."""


class FastForwardCheckFailed(Exception):
    """git could not say whether an update is a fast-forward."""


class OldHeadSaveFailed(Exception):
    """git could not save the commit a forced update replaces."""


def updates_to_check(pushed_refs_text):
    """Return (branch, local object ID, remote object ID) for each update to an existing branch."""
    updates = []
    for line in pushed_refs_text.splitlines():
        fields = line.split()
        if len(fields) != 4:
            continue
        _local_ref, local_object_id, remote_ref, remote_object_id = fields
        if not remote_ref.startswith(BRANCH_REF_PREFIX) or set(remote_object_id) == {"0"}:
            continue
        updates.append((remote_ref[len(BRANCH_REF_PREFIX):], local_object_id, remote_object_id))
    return updates


def git_for_fast_forward_check(argv, runner, accepted_exit_codes, input_text=None,
                               failure=FastForwardCheckFailed, timeout=GIT_TIMEOUT_SECONDS):
    """Run git; raise failure unless it exits with an accepted code."""
    try:
        completed = runner(argv, input=input_text, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, text=True, timeout=timeout,
                           check=False)
    except subprocess.TimeoutExpired:
        raise failure(f"{' '.join(argv[:3])} did not answer within "
                      f"{timeout:.0f} seconds") from None
    except OSError as error:
        raise failure(f"git could not be run ({error})") from None
    if completed.returncode not in accepted_exit_codes:
        first_line = ((completed.stderr or "").strip().splitlines() or [""])[0]
        raise failure(
            f"{' '.join(argv[:3])} exited with status {completed.returncode}"
            + (f": {first_line}" if first_line else ""))
    return completed


def commit_is_here(object_id, runner, failure=FastForwardCheckFailed):
    """Whether this repository has the object; git failing raises failure."""
    # merge-base --is-ancestor exits 128 both for a commit missing here and for a broken
    # repository; cat-file --batch-check prints "missing" for the first and exits 0.
    present = git_for_fast_forward_check(["git", "cat-file", "--batch-check"], runner, (0,),
                                         input_text=object_id + "\n", failure=failure)
    return not present.stdout.rstrip().endswith(" missing")


def is_fast_forward(remote_object_id, local_object_id, runner):
    """True only when git shows the remote commit is an ancestor of the pushed one."""
    if not commit_is_here(remote_object_id, runner):
        return False
    ancestor = git_for_fast_forward_check(
        ["git", "merge-base", "--is-ancestor", remote_object_id, local_object_id], runner, (0, 1))
    return ancestor.returncode == 0


def open_pull_request(branch, runner):
    """Return the open pull request whose head is branch, as gh's JSON, or None."""
    argv = ["gh", "pr", "list", "--state", "open", "--head", branch, "--json",
            "number,title,url,id,isDraft"]
    try:
        completed = runner(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                           timeout=GH_TIMEOUT_SECONDS, check=False)
    except subprocess.TimeoutExpired:
        raise OpenPullRequestLookupFailed(
            f"gh pr list did not answer within {GH_TIMEOUT_SECONDS:.0f} seconds") from None
    except OSError as error:
        raise OpenPullRequestLookupFailed(f"gh could not be run ({error})") from None
    if completed.returncode != 0:
        first_line = ((completed.stderr or "").strip().splitlines() or [""])[0]
        raise OpenPullRequestLookupFailed(
            f"gh pr list exited with status {completed.returncode}"
            + (f": {first_line}" if first_line else ""))
    try:
        entries = json.loads(completed.stdout or "[]")
    except ValueError:
        raise OpenPullRequestLookupFailed("gh pr list printed output that is not JSON") from None
    return entries[0] if entries else None


def was_ever_ready_for_review(pull_request, runner):
    """True when GitHub's timeline for the draft pull_request holds a ready or draft event."""
    argv = ["gh", "api", "graphql", "-f", "query=" + EVER_READY_QUERY,
            "-f", f"id={pull_request.get('id')}"]
    try:
        completed = runner(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                           timeout=GH_TIMEOUT_SECONDS, check=False)
    except subprocess.TimeoutExpired:
        raise ReadyHistoryLookupFailed(
            f"gh api graphql did not answer within {GH_TIMEOUT_SECONDS:.0f} seconds") from None
    except OSError as error:
        raise ReadyHistoryLookupFailed(f"gh could not be run ({error})") from None
    if completed.returncode != 0:
        first_line = ((completed.stderr or "").strip().splitlines() or [""])[0]
        raise ReadyHistoryLookupFailed(
            f"gh api graphql exited with status {completed.returncode}"
            + (f": {first_line}" if first_line else ""))
    try:
        count = json.loads(completed.stdout)["data"]["node"]["timelineItems"]["filteredCount"]
    except (ValueError, KeyError, TypeError):
        raise ReadyHistoryLookupFailed(
            "gh api graphql printed no count of the pull request's ready and draft "
            "events") from None
    if not isinstance(count, int):
        raise ReadyHistoryLookupFailed(
            f"gh api graphql printed {count!r} as the count of the pull request's ready and "
            "draft events")
    return count > 0


def force_pushed_old_head_save(branch, remote_object_id, runner):
    """Point refs/force-pushed-old-heads/<branch>/<remote_object_id> at the commit a forced update
    replaces, fetching it from origin when this repository lacks it; return the ref, or raise
    OldHeadSaveFailed."""
    ref = f"{FORCE_PUSHED_OLD_HEAD_REF_PREFIX}{branch}/{remote_object_id}"
    if not commit_is_here(remote_object_id, runner, failure=OldHeadSaveFailed):
        git_for_fast_forward_check(["git", "fetch", "--quiet", CHECKED_REMOTE_NAME,
                                    remote_object_id], runner, (0,), failure=OldHeadSaveFailed,
                                   timeout=GIT_FETCH_TIMEOUT_SECONDS)
    git_for_fast_forward_check(["git", "update-ref", ref, remote_object_id], runner, (0,),
                               failure=OldHeadSaveFailed)
    return ref


def old_heads_save(forced_updates, runner):
    """Save the replaced commit of each forced update; return (refusal lines for the first that
    could not be saved, or [], a note for each one saved)."""
    notes = []
    for branch, remote_object_id in forced_updates:
        try:
            ref = force_pushed_old_head_save(branch, remote_object_id, runner)
        except OldHeadSaveFailed as error:
            ref = f"{FORCE_PUSHED_OLD_HEAD_REF_PREFIX}{branch}/{remote_object_id}"
            return [OLD_HEAD_SAVE_FAILED_REFUSAL.format(branch=branch, old_head=remote_object_id,
                                                        ref=ref, detail=str(error)),
                    *(line.format(branch=branch) for line in OLD_HEAD_SAVE_FAILED_INSTRUCTIONS)
                    ], notes
        notes.append(OLD_HEAD_SAVED_NOTE.format(branch=branch, old_head=remote_object_id,
                                                ref=ref))
    return [], notes


def forced_updates_unchecked_for_pull_requests(pushed_refs_text, runner):
    """Return ((branch, remote object ID) for each update that is not a fast-forward, and
    (branch, detail) for each update git could not say is a fast-forward)."""
    forced_updates = []
    fast_forward_check_failures = []
    for branch, local_object_id, remote_object_id in updates_to_check(pushed_refs_text):
        if set(local_object_id) == {"0"}:
            continue
        try:
            if not is_fast_forward(remote_object_id, local_object_id, runner):
                forced_updates.append((branch, remote_object_id))
        except FastForwardCheckFailed as error:
            fast_forward_check_failures.append((branch, str(error)))
    return forced_updates, fast_forward_check_failures


def pull_request_name(pull_request):
    return f"#{pull_request.get('number')} ({pull_request.get('url')})"


def refusal_lines(pushed_refs_text, runner):
    """Return the lines that refuse this push, or [] to let it through; (branch, detail) for
    each update git could not say is a fast-forward; and (branch, remote object ID) for each
    forced update let through."""
    forced_updates = []
    lookup_failures = []
    ready_lookup_failures = []
    fast_forward_check_failures = []
    for branch, local_object_id, remote_object_id in updates_to_check(pushed_refs_text):
        deletes = set(local_object_id) == {"0"}
        if not deletes:
            try:
                if is_fast_forward(remote_object_id, local_object_id, runner):
                    continue
            except FastForwardCheckFailed as error:
                fast_forward_check_failures.append((branch, str(error)))
                continue
        try:
            pull_request = open_pull_request(branch, runner)
        except OpenPullRequestLookupFailed as error:
            lookup_failures.append((branch, deletes, str(error)))
            continue
        if pull_request is None:
            if not deletes:
                forced_updates.append((branch, remote_object_id))
            continue
        ready_state = READY_NOW
        if not deletes:
            draft = pull_request.get("isDraft") is True
            ready_history = {}

            def ever_marked_ready():
                if not draft:
                    return True
                ready_history["read"] = was_ever_ready_for_review(pull_request, runner)
                return ready_history["read"]
            try:
                answer = rebase_or_replace.pull_request_conflict_with_main_rebase_or_replace_answer(
                    True, ever_marked_ready)
            except ReadyHistoryLookupFailed as error:
                ready_lookup_failures.append((branch, pull_request, str(error)))
                continue
            if answer == rebase_or_replace.REBASE_ONTO_MAIN:
                forced_updates.append((branch, remote_object_id))
                continue
            if draft:
                ready_state = (DRAFT_ONCE_READY if ready_history.get("read")
                               else DRAFT_HEAD_NOT_REWRITTEN)
        refusal = DELETION_REFUSAL if deletes else REWRITE_REFUSAL
        instructions = DELETION_INSTRUCTIONS if deletes else REWRITE_INSTRUCTIONS
        return [refusal.format(branch=branch, pull_request=pull_request_name(pull_request),
                               ready_state=ready_state),
                *(line.format(branch=branch, number=pull_request.get("number"))
                  for line in instructions),
                ESCAPE_HATCH_INSTRUCTION], fast_forward_check_failures, forced_updates
    if lookup_failures:
        branch, deletes, detail = lookup_failures[0]
        return [LOOKUP_FAILED_REFUSAL.format(action="deletes" if deletes else "forces an update to",
                                             branch=branch, detail=detail),
                LOOKUP_FAILED_INSTRUCTION.format(branch=branch),
                ESCAPE_HATCH_INSTRUCTION], fast_forward_check_failures, forced_updates
    if ready_lookup_failures:
        branch, pull_request, detail = ready_lookup_failures[0]
        return [READY_LOOKUP_FAILED_REFUSAL.format(
                    branch=branch, pull_request=pull_request_name(pull_request), detail=detail),
                LOOKUP_FAILED_INSTRUCTION.format(branch=branch),
                ESCAPE_HATCH_INSTRUCTION], fast_forward_check_failures, forced_updates
    return [], fast_forward_check_failures, forced_updates


def main(argv, pushed_refs_text, stderr, environment, runner=subprocess.run):
    """Return EXIT_ALLOW_PUSH or EXIT_REFUSE_PUSH for one push."""
    remote_name = argv[0] if argv else ""
    if remote_name != CHECKED_REMOTE_NAME:
        return EXIT_ALLOW_PUSH
    if environment.get(ESCAPE_HATCH_VARIABLE) == "1":
        lines = []
        forced_updates, fast_forward_check_failures = forced_updates_unchecked_for_pull_requests(
            pushed_refs_text, runner)
    else:
        lines, fast_forward_check_failures, forced_updates = refusal_lines(pushed_refs_text,
                                                                           runner)
    saved_notes = []
    if not lines and fast_forward_check_failures:
        branch = fast_forward_check_failures[0][0]
        lines = [FAST_FORWARD_CHECK_FAILED_REFUSAL.format(branch=branch),
                 *(line.format(branch=branch) for line in OLD_HEAD_SAVE_FAILED_INSTRUCTIONS)]
    if not lines:
        lines, saved_notes = old_heads_save(forced_updates, runner)
    for note in saved_notes:
        stderr.write(MESSAGE_PREFIX + note + "\n")
    for line in lines[:1]:
        stderr.write(MESSAGE_PREFIX + line + "\n")
    for line in lines[1:]:
        stderr.write(line + "\n")
    for branch, detail in fast_forward_check_failures:
        stderr.write(f"{MESSAGE_PREFIX}whether this push's update to branch {branch} is a "
                     f"fast-forward could not be checked: {detail}.\n")
    return EXIT_REFUSE_PUSH if lines else EXIT_ALLOW_PUSH


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], sys.stdin.read(), sys.stderr, os.environ))
