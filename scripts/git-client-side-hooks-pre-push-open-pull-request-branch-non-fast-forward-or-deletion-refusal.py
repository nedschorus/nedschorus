#!/usr/bin/env python3
"""Refuse a push that rewrites or deletes the head branch of an open pull request on origin.

Run by scripts/git-client-side-hooks/pre-push with git's pre-push arguments and the pushed refs
on standard input. Exit 10 refuses the push; exit 0 lets it through. Any other exit makes the
hook say the push went unchecked and to tell the user.

Reviews are of a pull request's pushed head, so an update that does not build on that head
replaces the commits under review, and deleting the head branch closes the pull request.
git rejects an unforced non-fast-forward update before this hook runs, so the updates this
check refuses are forced ones, whatever command spelling sent them.

Only branches on origin are checked. A new branch and a fast-forward are let through without
asking GitHub. Every other update to a branch, or deletion of one, is let through only when
`gh pr list` answers that the branch has no open pull request: when gh cannot answer, the push
is refused, because a forced update cannot be undone by the agent that sent it. A remote commit
missing from the local repository cannot be shown to be an ancestor, so the update counts as
not a fast-forward.

ESCAPE_HATCH_ASSIGNMENT in front of the git push command lets a push merge-lane-2 asked for
through unchecked; scripts/force-push-with-open-pull-request-guard-hook.py reads the same one.
"""

import json
import os
import socket
import subprocess
import sys

EXIT_ALLOW_PUSH = 0
EXIT_REFUSE_PUSH = 10

CHECKED_REMOTE_NAME = "origin"
BRANCH_REF_PREFIX = "refs/heads/"
MESSAGE_PREFIX = "pre-push: "
GH_TIMEOUT_SECONDS = 10.0
GIT_TIMEOUT_SECONDS = 10.0
ESCAPE_HATCH_VARIABLE = "CLAUDE_MERGE_LANE_ASKED_FOR_THIS_REWRITE"
ESCAPE_HATCH_ASSIGNMENT = ESCAPE_HATCH_VARIABLE + "=1"

REWRITE_REFUSAL = (
    "this push is refused, because its update to branch {branch} does not build on the "
    "commits origin holds, and {branch} is the head of open pull request {pull_request}: the "
    "update would replace the commits under review.")
DELETION_REFUSAL = (
    "this push is refused, because it deletes branch {branch}, the head of open pull request "
    "{pull_request}: deleting the head branch closes the pull request.")
REWRITE_INSTRUCTIONS = [
    "If you are adding work to the branch: run git fetch origin {branch}, put your change in a "
    "new commit on top of origin/{branch}, and push without --force.",
    "If the branch conflicts with main: clear the conflict with the hand-merge that "
    "scripts/branch-conflict-check.py describes, and push without --force.",
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
LOOKUP_FAILED_INSTRUCTIONS = [
    "Run gh auth status to see whether gh on {machine} is logged in.",
    "If gh's error above says gh is not logged in: tell the user this whole message; he logs gh in "
    "himself, on the Mac with gh auth login in a Terminal, and on ned-box from a Terminal on his "
    "Mac with ssh -t nedlern@ned-box 'gh auth login'. Push again only after he says gh is "
    "logged in.",
    "If gh's error above says gh did not answer in time, or printed output that is not JSON: push "
    "again once. If that push is refused the same way, tell the user this whole message.",
    "If gh's error above says no git remote points to a known GitHub host: gh finds the "
    "repository from the remotes of this clone, not from the URL git handed this hook. Run git "
    "remote get-url origin, tell the user what it prints, and do not push {branch} again until "
    "he answers.",
    "If gh's error above is none of these: tell the user this whole message, and do not push "
    "{branch} again until he answers.",
    "If gh pr list --state open --head {branch} lists a pull request: {instead}",
]
LOOKUP_FAILED_REWRITE_INSTEAD = (
    "do not force the push; put your change in a new commit on top of origin/{branch} instead.")
LOOKUP_FAILED_DELETION_INSTEAD = (
    "close the pull request with a comment that says why before you delete the branch.")


class OpenPullRequestLookupFailed(Exception):
    """gh could not say whether a branch has an open pull request."""


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


def is_fast_forward(remote_object_id, local_object_id, runner):
    """True only when git shows the remote commit is an ancestor of the pushed one."""
    completed = runner(["git", "merge-base", "--is-ancestor", remote_object_id, local_object_id],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=GIT_TIMEOUT_SECONDS, check=False)
    return completed.returncode == 0


def open_pull_request(branch, runner):
    """Return the open pull request whose head is branch, as gh's JSON, or None."""
    argv = ["gh", "pr", "list", "--state", "open", "--head", branch, "--json", "number,title,url"]
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


def pull_request_name(pull_request):
    return f"#{pull_request.get('number')} ({pull_request.get('url')})"


def refusal_lines(pushed_refs_text, runner):
    """Return the lines that refuse this push, or [] to let it through."""
    lookup_failures = []
    for branch, local_object_id, remote_object_id in updates_to_check(pushed_refs_text):
        deletes = set(local_object_id) == {"0"}
        if not deletes and is_fast_forward(remote_object_id, local_object_id, runner):
            continue
        try:
            pull_request = open_pull_request(branch, runner)
        except OpenPullRequestLookupFailed as error:
            lookup_failures.append((branch, deletes, str(error)))
            continue
        if pull_request is None:
            continue
        refusal = DELETION_REFUSAL if deletes else REWRITE_REFUSAL
        instructions = DELETION_INSTRUCTIONS if deletes else REWRITE_INSTRUCTIONS
        return [refusal.format(branch=branch, pull_request=pull_request_name(pull_request)),
                *(line.format(branch=branch, number=pull_request.get("number"))
                  for line in instructions),
                ESCAPE_HATCH_INSTRUCTION]
    if lookup_failures:
        branch, deletes, detail = lookup_failures[0]
        return [LOOKUP_FAILED_REFUSAL.format(action="deletes" if deletes else "forces an update to",
                                             branch=branch, detail=detail),
                *(line.format(branch=branch, machine=socket.gethostname(), instead=(
                    LOOKUP_FAILED_DELETION_INSTEAD if deletes
                    else LOOKUP_FAILED_REWRITE_INSTEAD.format(branch=branch)))
                  for line in LOOKUP_FAILED_INSTRUCTIONS),
                ESCAPE_HATCH_INSTRUCTION]
    return []


def main(argv, pushed_refs_text, stderr, environment, runner=subprocess.run):
    """Return EXIT_ALLOW_PUSH or EXIT_REFUSE_PUSH for one push."""
    remote_name = argv[0] if argv else ""
    if remote_name != CHECKED_REMOTE_NAME or environment.get(ESCAPE_HATCH_VARIABLE) == "1":
        return EXIT_ALLOW_PUSH
    lines = refusal_lines(pushed_refs_text, runner)
    for line in lines[:1]:
        stderr.write(MESSAGE_PREFIX + line + "\n")
    for line in lines[1:]:
        stderr.write(line + "\n")
    return EXIT_REFUSE_PUSH if lines else EXIT_ALLOW_PUSH


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], sys.stdin.read(), sys.stderr, os.environ))
