#!/usr/bin/env python3
"""Does merge-lane-2's verdict review carry the marks the posting program writes?

scripts/merge-gate.sh runs this on ned-review-merge's latest review whose state is APPROVED or
CHANGES_REQUESTED. Standard input is one JSON object: "review", the review as GitHub's reviews
endpoint returns it, and "comments", the list of its inline comments. The marks are the ones
scripts/merge-lane-pull-request-reviewer-review-post-and-read-back.py writes, read by its
verdict_review_posting_program_marks_missing().

Exits 0 when the review has the marks; 1 when it lacks them, printing why on standard output;
2 when standard input is not that object.
"""

import importlib.util
import json
import sys
from pathlib import Path

_posting_spec = importlib.util.spec_from_file_location(
    "merge_lane_pull_request_reviewer_review_post_and_read_back",
    Path(__file__).resolve().with_name("merge-lane-pull-request-reviewer-review-post-and-read-back.py"))
posting = importlib.util.module_from_spec(_posting_spec)
_posting_spec.loader.exec_module(posting)

EXIT_HAS_MARKS = 0
EXIT_LACKS_MARKS = 1
EXIT_INPUT_UNUSABLE = 2


def main():
    try:
        given = json.loads(sys.stdin.read())
        review, comments = given["review"], given["comments"]
        if not isinstance(review, dict) or not isinstance(comments, list):
            raise TypeError("review must be an object and comments a list")
        missing = posting.verdict_review_posting_program_marks_missing(review, comments)
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        print(f"merge-gate-verdict-review-posting-program-marks-check.py: standard input is not one JSON object "
              f"with a \"review\" object and a \"comments\" list: {type(error).__name__}: {error}", file=sys.stderr)
        return EXIT_INPUT_UNUSABLE
    if missing:
        print(missing)
        return EXIT_LACKS_MARKS
    return EXIT_HAS_MARKS


if __name__ == "__main__":
    sys.exit(main())
