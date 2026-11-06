#!/usr/bin/env python3
"""Read the #replaces lines of a pull request's description and follow them to every pull request it replaces.

A pull request that replaces another, as scripts/branch-conflict-check.py says to do when an open pull
request conflicts with main, carries a line in its description that begins, after optional indentation,
an optional bullet and optional bold markers, with #replaces followed by the old pull request's full
https://github.com/<owner>/<repo>/pull/<number> link. A description may carry more than one such line.

The fix-round program, scripts/pull-request-review-plan.py and the follow-up request program import this
module, so that a replaced pull request's findings and review rounds count on the pull request that
replaces it. Each passes a function that reads a pull request's description, so this module runs no gh.

replaced_pull_request_chain_numbers_oldest_first follows the lines through replacements of replacements: when C
replaces B and B replaces A, C's chain is A, B. It raises ReplacedPullRequestChainUnreadable when a #replaces line
carries no link to a pull request of the same repository, when it names the pull request whose
description carries it, or when the chain comes back to a pull request it already passed; a malformed
line would otherwise drop the old pull request's findings with no one seeing it.

Not handled: a link written in another form, such as a pull request number with no link, or a link to an issue, which is
refused, not guessed at; and reading the descriptions, which the caller's function does, raising what
it raises.
"""

import re

PULL_REQUEST_DESCRIPTION_REPLACES_HASHTAG = "#replaces"
READER_PATH = "scripts/pull-request-description-replaces-line-replaced-pull-request-chain-reader-common.py"

_REPLACES_LINE = re.compile(
    r"\s*(?:[-*+]\s+)?(?:\*\*|__)?" + re.escape(PULL_REQUEST_DESCRIPTION_REPLACES_HASHTAG) + r"(?!\w)(?P<rest>.*)")
_PULL_REQUEST_LINK = re.compile(
    r"https://github\.com/(?P<repository>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/pull/(?P<number>[0-9]+)\b")


class ReplacedPullRequestChainUnreadable(Exception):
    """A #replaces line, or the chain of them, cannot be followed; the text says which and what to do."""


def replaced_pull_request_numbers_on_replaces_lines(description, repository, number=None):
    """The pull request numbers the #replaces lines of `description` name, in order, each once.

    `repository` is "<owner>/<repo>"; `number`, when given, is the pull request the description belongs to."""
    found = []
    for line in (description or "").split("\n"):
        matched = _REPLACES_LINE.match(line.removesuffix("\r"))
        if matched is None:
            continue
        link = _PULL_REQUEST_LINK.search(matched.group("rest"))
        if link is None or link.group("repository").lower() != repository.lower():
            raise ReplacedPullRequestChainUnreadable(
                f"pull request {number}'s description has the line `{line.strip()}`, which does not name, after "
                f"{PULL_REQUEST_DESCRIPTION_REPLACES_HASHTAG}, a full https://github.com/{repository}/pull/<number> "
                "link, so the findings and review rounds of the pull request it replaces cannot be carried over.\n"
                f"Have the pull request's author write the line as {PULL_REQUEST_DESCRIPTION_REPLACES_HASHTAG} "
                f"https://github.com/{repository}/pull/<the old pull request's number>, editing only the "
                "description, then run this again.")
        replaced = int(link.group("number"))
        if replaced == number:
            raise ReplacedPullRequestChainUnreadable(
                f"pull request {number}'s description has the line `{line.strip()}`, which names pull request "
                f"{number} itself after {PULL_REQUEST_DESCRIPTION_REPLACES_HASHTAG}.\n"
                "Have the pull request's author put the old pull request's link on the line, or remove the line "
                "when the pull request replaces none, then run this again.")
        if replaced not in found:
            found.append(replaced)
    return found


def replaced_pull_request_chain_numbers_oldest_first(number, repository, read_description):
    """Every pull request `number` replaces, directly or through the #replaces lines of the pull requests it
    replaces, oldest first: those deepest in the chain come first.

    `read_description(n)` returns pull request n's description."""
    order = []
    on_path = []

    def follow(current):
        on_path.append(current)
        for replaced in replaced_pull_request_numbers_on_replaces_lines(
                read_description(current), repository, current):
            if replaced in on_path:
                raise ReplacedPullRequestChainUnreadable(
                    f"the {PULL_REQUEST_DESCRIPTION_REPLACES_HASHTAG} lines loop: "
                    + " replaces ".join(f"pull request {step}" for step in [*on_path, replaced])
                    + ", so no pull request in the loop is the oldest.\n"
                    f"In the loop, find the pull request whose {PULL_REQUEST_DESCRIPTION_REPLACES_HASHTAG} line names a pull request opened after "
                    "it, have its author remove that line, then run this again.")
            if replaced not in order:
                follow(replaced)
                order.append(replaced)
        on_path.pop()

    follow(number)
    return order
