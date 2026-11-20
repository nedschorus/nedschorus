#!/usr/bin/env python3
"""Answer one question the same way for every program that asks it: is a branch that
conflicts with main brought up to date with main itself, or is its pull request replaced by a
new pull request cut from current main?

GitHub's ruleset refuses every non-fast-forward push to every branch of this repository, so
neither answer allows a force-push. The rebase answer says the branch is brought up to date
itself: scripts/branch-conflict-check.py says to rebase it while origin does not have it, and
otherwise to merge main into it; scripts/checkout-freshness-catch-up.py rebases a branch
never pushed. On the replace answer, .claude/guard-hooks/force-push-with-open-pull-request-guard-hook.py
and the pre-push hook's
scripts/git-client-side-hooks-pre-push-open-pull-request-branch-non-fast-forward-or-deletion-refusal.py
refuse a force-push to an open pull request's head before GitHub does.

A branch with no open pull request gets the rebase answer: nobody reviews it. An open pull
request that was ever marked ready for review is replaced, because its review holds its pushed
commits. An open pull request never marked ready gets the rebase answer only while
REBASE_ONTO_MAIN_FOR_PULL_REQUESTS_NEVER_MARKED_READY_FOR_REVIEW_TURNED_ON is True; it is
False, so every open pull request is replaced.

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
