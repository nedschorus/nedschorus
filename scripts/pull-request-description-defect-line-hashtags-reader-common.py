#!/usr/bin/env python3
"""Read the defect lines of a pull request's description.

A defect line says whether the pull request fixes a defect and, if it does,
whether the change removes the defect's root cause. It begins, after optional
indentation, an optional bullet and optional bold markers, with one of the
hashtags #root_cause, #root_cause_not_fixed or #no_defect_fixed, or with one of
the colon-and-period labels "Root cause:", "Root cause not fixed:" or
"No defect fixed.", which descriptions written before the hashtags carry.

A not-fixed line names after #follow_up the issue or pull request that will fix
its cause or look for it. Only the first link after #follow_up is read, with
trailing punctuation dropped, and it is cut back to the issue or pull request it
names when it carries a #fragment, a sub-path or a query; a link that names no
GitHub issue or pull request is read as no link.

Imported by the programs that read descriptions. Run as a command, it reads one
description on stdin and prints its defect lines as a JSON list of
{"kind", "line", "link"}, for scripts/merge-gate.sh.

Exit codes: 0 the lines were printed, possibly none; 2 stdin was not UTF-8 text,
or the command was given an argument other than --help.
"""

import argparse
import json
import re
import sys

ROOT_CAUSE_HASHTAG = "#root_cause"
ROOT_CAUSE_NOT_FIXED_HASHTAG = "#root_cause_not_fixed"
NO_DEFECT_FIXED_HASHTAG = "#no_defect_fixed"
PULL_REQUEST_DESCRIPTION_FOLLOW_UP_HASHTAG = "#follow_up"
ROOT_CAUSE_COLON_LABEL = "Root cause:"
ROOT_CAUSE_NOT_FIXED_COLON_LABEL = "Root cause not fixed:"
NO_DEFECT_FIXED_PERIOD_LABEL = "No defect fixed."

ROOT_CAUSE = "root_cause"
ROOT_CAUSE_NOT_FIXED = "root_cause_not_fixed"
NO_DEFECT_FIXED = "no_defect_fixed"

_LINE_START = r"\s*(?:[-*+]\s+)?(?:\*\*|__)?"
_BOLD_END = r"(?:\*\*|__)?"


def _label_pattern(label):
    # A bold label may close its bold type before its colon or period.
    return re.escape(label[:-1]) + _BOLD_END + re.escape(label[-1])


_KIND_PATTERNS = (
    (ROOT_CAUSE_NOT_FIXED, re.compile(
        _LINE_START + "(?:" + re.escape(ROOT_CAUSE_NOT_FIXED_HASHTAG) + r"(?!\w)|"
        + _label_pattern(ROOT_CAUSE_NOT_FIXED_COLON_LABEL) + ")")),
    (ROOT_CAUSE, re.compile(
        _LINE_START + "(?:" + re.escape(ROOT_CAUSE_HASHTAG) + r"(?!\w)|"
        + _label_pattern(ROOT_CAUSE_COLON_LABEL) + ")")),
    (NO_DEFECT_FIXED, re.compile(
        _LINE_START + "(?:" + re.escape(NO_DEFECT_FIXED_HASHTAG) + r"(?!\w)|"
        + _label_pattern(NO_DEFECT_FIXED_PERIOD_LABEL) + ")")),
)
_FOLLOW_UP_LINK = re.compile(
    re.escape(PULL_REQUEST_DESCRIPTION_FOLLOW_UP_HASHTAG) + r"(?!\w).*?(?P<url>https?://[^\s)>\]`]+)")
_GITHUB_ISSUE_OR_PULL_REQUEST = re.compile(
    r"(?P<item>https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/(?:issues|pull)/[0-9]+)(?:[/#?].*)?")


def follow_up_link(line):
    """The issue or pull request link that follows #follow_up on `line`, or None."""
    found = _FOLLOW_UP_LINK.search(line)
    if found is None:
        return None
    item = _GITHUB_ISSUE_OR_PULL_REQUEST.fullmatch(found.group("url").rstrip(".,;:"))
    return None if item is None else item.group("item")


def pull_request_description_defect_lines(description):
    """Each defect line of `description`, in order, as {"kind", "line", "link"}:
    kind is ROOT_CAUSE, ROOT_CAUSE_NOT_FIXED or NO_DEFECT_FIXED; line is the whole
    line without its carriage return; link is follow_up_link(line) on a not-fixed
    line and None on the others."""
    if not isinstance(description, str):
        raise TypeError(f"a pull request description is text, not {type(description).__name__}")
    found = []
    for line in description.split("\n"):
        line = line.removesuffix("\r")
        for kind, pattern in _KIND_PATTERNS:
            if pattern.match(line):
                link = follow_up_link(line) if kind == ROOT_CAUSE_NOT_FIXED else None
                found.append({"kind": kind, "line": line, "link": link})
                break
    return found


def main():
    argparse.ArgumentParser(
        description="Read one pull request description on stdin and print its defect lines "
                    "as a JSON list of {\"kind\", \"line\", \"link\"}.").parse_args()
    try:
        description = sys.stdin.buffer.read().decode("utf-8")
    except UnicodeDecodeError as error:
        print(f"pull-request-description-defect-line-hashtags-reader-common: the description on "
              f"stdin is not UTF-8 text: {error}", file=sys.stderr)
        return 2
    print(json.dumps(pull_request_description_defect_lines(description)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
