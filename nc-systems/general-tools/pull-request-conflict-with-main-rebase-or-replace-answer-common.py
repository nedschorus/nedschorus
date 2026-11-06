#!/usr/bin/env python3
"""Answer one question the same way for every program that asks it: is a branch that
conflicts with main cleared by rebasing it onto main and force-pushing it, or is its pull
request replaced by a new pull request cut from current main?

The same answer says whether a pull request's head branch may be force-pushed at all: the
rebase answer allows it, the replace answer does not. So
.claude/guard-hooks/force-push-with-open-pull-request-guard-hook.py, the pre-push hook's
scripts/git-client-side-hooks-pre-push-open-pull-request-branch-non-fast-forward-or-deletion-refusal.py,
scripts/branch-conflict-check.py and scripts/checkout-freshness-catch-up.py all ask here.

A branch with no open pull request is rebased: nobody reviews it. An open pull request that
was ever marked ready for review is replaced, because its review holds its pushed commits. An
open pull request never marked ready gets the rebase answer only while
REBASE_ONTO_MAIN_FOR_PULL_REQUESTS_NEVER_MARKED_READY_FOR_REVIEW_TURNED_ON is True; it stays False until both push
guards let such a pull request's head be force-pushed, because until then the rebase answer
would send an agent into a push a guard refuses.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "pull_request_conflict_with_main_rebase_or_replace_answer_common", <path>)
"""

REBASE_ONTO_MAIN = "rebase onto main"
REPLACE_WITH_NEW_PULL_REQUEST = "replace with a new pull request"

REBASE_ONTO_MAIN_FOR_PULL_REQUESTS_NEVER_MARKED_READY_FOR_REVIEW_TURNED_ON = False


def pull_request_conflict_with_main_rebase_or_replace_answer(open_pull_request_found,
                                                            ever_marked_ready_read=None):
    """Return REBASE_ONTO_MAIN or REPLACE_WITH_NEW_PULL_REQUEST for one branch.

    ever_marked_ready_read is called with no arguments only when its answer decides, and
    returns whether the open pull request was ever marked ready for review; what it raises
    reaches the caller. A caller that cannot read that history passes None, and gets the
    replace answer for every open pull request.
    """
    if not open_pull_request_found:
        return REBASE_ONTO_MAIN
    if not REBASE_ONTO_MAIN_FOR_PULL_REQUESTS_NEVER_MARKED_READY_FOR_REVIEW_TURNED_ON or ever_marked_ready_read is None:
        return REPLACE_WITH_NEW_PULL_REQUEST
    return REPLACE_WITH_NEW_PULL_REQUEST if ever_marked_ready_read() else REBASE_ONTO_MAIN
