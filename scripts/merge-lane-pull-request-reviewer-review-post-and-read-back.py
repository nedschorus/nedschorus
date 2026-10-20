#!/usr/bin/env python3
"""Post the mac-claude reviewer's review of a pull request, then read it back from GitHub.

Did the review get posted on the named head commit, as the verdict says? Exits 0
if the review was posted and read back as expected, 2 otherwise.

Usage:
  scripts/merge-lane-pull-request-reviewer-review-post-and-read-back.py
      --pull-request N --head-commit SHA <review file>

The review file's first line is #approve or #request_changes. The rest of the
file is one JSON object: "body", the review's text, and optionally "comments",
a list of inline comments, each with "path", "line" and "body", in the shape
GitHub's create-a-review API takes.

The review is posted as mac-claude, with the token in
~/.config/nedschorus/mac-claude.token, on the head commit given. Its body
starts with a line APPROVE or REQUEST_CHANGES, so the verdict shows even when
the review is posted as a comment. The review's event is the verdict when the
pull request's author is ned-review-merge, because GitHub refuses an approving
review from a pull request's author and merge-lane-2 approves as that account;
for any other author the event is COMMENT, and merge-lane-2 records the
verdict itself. The posted review is then read back by the id GitHub returned,
and its state and commit must be the ones asked for.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPOSITORY = "nedschorus/nedschorus"
MERGE_LANE_ACCOUNT = "ned-review-merge"
TAG_VERDICTS = {"#approve": "APPROVE", "#request_changes": "REQUEST_CHANGES"}
# The state GitHub gives a review posted with each event.
EVENT_STATES = {"APPROVE": "APPROVED", "REQUEST_CHANGES": "CHANGES_REQUESTED",
                "COMMENT": "COMMENTED"}
EXIT_POSTED = 0
EXIT_NOT_POSTED = 2

REVIEW_FILE_UNUSABLE = (
    "review not posted: the review file {path} {reason}.\n"
    "Fix the review file and run the same command again.\n"
    "The file's first line is #approve or #request_changes; the rest is one JSON object with "
    "\"body\" and, if you have inline comments, \"comments\", each with \"path\", \"line\" and "
    "\"body\".")
NOT_POSTED = (
    "review not posted: {reason}.\n"
    "Do not post the review any other way.\n"
    "Put this message in your report back to merge-lane-2, with your review file's path.")
POST_FAILED = (
    "review may or may not be posted: posting the review failed: {reason}\n"
    "Do not run this command again, and do not post the review any other way: GitHub may have "
    "made the review before the failure, and a second post would add a second review.\n"
    "Put this message in your report back to merge-lane-2, with your review file's path, so it "
    "can check the pull request's reviews.")
READ_BACK_FAILED = (
    "review {review_id} was posted, but reading it back failed: {reason}\n"
    "Do not post the review again: it is on the pull request.\n"
    "Put this message in your report back to merge-lane-2, so it can check review {review_id}.")
READ_BACK_DIFFERS = (
    "review {review_id} was posted, but GitHub's copy differs from what was asked for: "
    "{differences}.\n"
    "Do not post the review again: it is on the pull request.\n"
    "Put this message in your report back to merge-lane-2, so it can check review {review_id}.")


class ReviewFileUnusable(Exception):
    pass


class GhFailed(Exception):
    pass


def read_review_file(path):
    """Return (verdict, body, comments) from the review file, or raise ReviewFileUnusable."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ReviewFileUnusable(f"could not be read: {error}")
    tag, _, rest = text.partition("\n")
    verdict = TAG_VERDICTS.get(tag.strip())
    if verdict is None:
        raise ReviewFileUnusable(
            f"starts with {tag.strip()!r}, not #approve or #request_changes")
    try:
        review = json.loads(rest)
    except ValueError as error:
        raise ReviewFileUnusable(f"has no valid JSON after its first line: {error}")
    if not isinstance(review, dict) or set(review) - {"body", "comments"}:
        raise ReviewFileUnusable(
            "must hold, after its first line, a JSON object with only \"body\" and \"comments\"")
    body, comments = review.get("body"), review.get("comments", [])
    if not isinstance(body, str) or not body.strip():
        raise ReviewFileUnusable("has no \"body\" text")
    if not isinstance(comments, list) or not all(
            isinstance(comment, dict) and isinstance(comment.get("path"), str)
            and isinstance(comment.get("line"), int) and isinstance(comment.get("body"), str)
            for comment in comments):
        raise ReviewFileUnusable(
            "has a \"comments\" entry without a text \"path\", a number \"line\" and a text \"body\"")
    return verdict, body, comments


def read_token():
    """Return mac-claude's token, or raise GhFailed naming why it cannot be used."""
    token_file = Path.home() / ".config" / "nedschorus" / "mac-claude.token"
    try:
        token = token_file.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as error:
        raise GhFailed(f"could not read mac-claude's token at {token_file}: {error}")
    # An empty GH_TOKEN makes gh fall back to its stored account, which is not mac-claude.
    if not token:
        raise GhFailed(f"mac-claude's token file {token_file} is empty")
    return token


def reason_of(error):
    if isinstance(error, GhFailed):
        return str(error)
    return f"GitHub's reply was not in the expected shape: {type(error).__name__}: {error}"


def gh_json(token, arguments, input_text=None):
    completed = subprocess.run(
        ["gh", "api", *arguments], input=input_text, capture_output=True, text=True,
        env={**os.environ, "GH_TOKEN": token},
        stdin=None if input_text is not None else subprocess.DEVNULL)
    if completed.returncode != 0:
        raise GhFailed(f"gh exited {completed.returncode}: {completed.stderr.strip()}")
    try:
        return json.loads(completed.stdout)
    except ValueError as error:
        raise GhFailed(f"gh printed no JSON: {error}")


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        description="Post the mac-claude reviewer's review of a pull request, then read it "
                    "back. Exits 0 if the review was posted and read back as expected, "
                    "2 otherwise.")
    parser.add_argument("--pull-request", type=int, required=True,
                        help="the pull request's number")
    parser.add_argument("--head-commit", required=True,
                        help="the full hash of the head commit the review is on")
    parser.add_argument("review_file", type=Path,
                        help="the review: a first line #approve or #request_changes, "
                             "then a JSON object with body and comments")
    return parser.parse_args(argv)


def main(argv=None):
    arguments = parse_arguments(argv)
    number, head = arguments.pull_request, arguments.head_commit
    try:
        verdict, body, comments = read_review_file(arguments.review_file)
    except ReviewFileUnusable as error:
        print(REVIEW_FILE_UNUSABLE.format(path=arguments.review_file, reason=error),
              file=sys.stderr)
        return EXIT_NOT_POSTED
    try:
        token = read_token()
    except GhFailed as error:
        print(NOT_POSTED.format(reason=error), file=sys.stderr)
        return EXIT_NOT_POSTED
    try:
        author = gh_json(token, [f"repos/{REPOSITORY}/pulls/{number}"])["user"]["login"]
    except (GhFailed, KeyError, TypeError) as error:
        print(NOT_POSTED.format(reason=f"reading the pull request's author failed: {reason_of(error)}"),
              file=sys.stderr)
        return EXIT_NOT_POSTED
    event = verdict if author == MERGE_LANE_ACCOUNT else "COMMENT"
    try:
        posted = gh_json(token, ["-X", "POST", f"repos/{REPOSITORY}/pulls/{number}/reviews",
                                 "--input", "-"],
                         input_text=json.dumps({"commit_id": head, "event": event,
                                                "body": f"{verdict}\n\n{body}",
                                                "comments": comments}))
        review_id = posted["id"]
    except (GhFailed, KeyError, TypeError) as error:
        print(POST_FAILED.format(reason=reason_of(error)), file=sys.stderr)
        return EXIT_NOT_POSTED
    try:
        copy = gh_json(token, [f"repos/{REPOSITORY}/pulls/{number}/reviews/{review_id}"])
        differences = [f"{field} is {copy.get(field)!r}, not {wanted!r}"
                       for field, wanted in (("state", EVENT_STATES[event]), ("commit_id", head))
                       if copy.get(field) != wanted]
    except (GhFailed, AttributeError) as error:
        print(READ_BACK_FAILED.format(review_id=review_id, reason=reason_of(error)),
              file=sys.stderr)
        return EXIT_NOT_POSTED
    if differences:
        print(READ_BACK_DIFFERS.format(review_id=review_id, differences="; ".join(differences)),
              file=sys.stderr)
        return EXIT_NOT_POSTED
    print(f"review {review_id} posted on pull request {number} as {event}, verdict {verdict}, "
          f"on commit {head}; GitHub's copy reads back as {EVENT_STATES[event]}")
    return EXIT_POSTED


if __name__ == "__main__":
    sys.exit(main())
