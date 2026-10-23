#!/usr/bin/env python3
"""Post the Claude reviewer's review of a pull request as mac-claude, then read it back from GitHub.

Did the review get posted on the named head commit, as the verdict says? Exits 0
if the review was posted and read back as expected, 2 otherwise.

Usage:
  scripts/merge-lane-pull-request-reviewer-review-post-and-read-back.py
      --pull-request N --head-commit SHA <review file>

The review file is the reviewer's answer, one JSON object in the shape of
merge-lane-pull-request-claude-reviewer-review-schema.json: "verdict", APPROVE
or REQUEST_CHANGES; "body", the review's text; and "comments", a list of inline
comments, each with "path", "line" and "body". A COULD_NOT_REVIEW verdict is
refused: nothing is posted for a review that did not finish.

GitHub refuses a whole review when one inline comment is on a line outside the
pull request's diff, so each comment whose path and line are not on the new
side of the diff GitHub reports for the pull request is moved into the body,
under a heading, as `path:line: comment`. A file whose diff GitHub does not
show, such as a binary file, takes no inline comments.

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
import re
import subprocess
import sys
from pathlib import Path

REPOSITORY = "nedschorus/nedschorus"
MERGE_LANE_ACCOUNT = "ned-review-merge"
POSTED_VERDICTS = ("APPROVE", "REQUEST_CHANGES")
OUTSIDE_THE_DIFF_HEADING = "Comments on lines outside this pull request's diff:"
HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
# The state GitHub gives a review posted with each event.
EVENT_STATES = {"APPROVE": "APPROVED", "REQUEST_CHANGES": "CHANGES_REQUESTED",
                "COMMENT": "COMMENTED"}
EXIT_POSTED = 0
EXIT_NOT_POSTED = 2

REVIEW_FILE_UNUSABLE = (
    "review not posted: the review file {path} {reason}.\n"
    "Do not post the review any other way.\n"
    "If the file came from a reviewer's run, run that review again: the run should not have "
    "passed it.")
NOT_POSTED = (
    "review not posted: {reason}.\n"
    "Do not post the review any other way.\n"
    "If the cause above is one you can fix, fix it and run the same command again; otherwise, "
    "tell the user this message.")
POST_FAILED = (
    "review may or may not be posted: posting the review failed: {reason}\n"
    "Do not run this command again until you have looked: GitHub may have made the review "
    "before the failure, and a second post would add a second review.\n"
    "If pull request {number} has no review from mac-claude on commit {head}, run the same "
    "command again; if it has one, use that review.")
READ_BACK_FAILED = (
    "review {review_id} was posted, but reading it back failed: {reason}\n"
    "Do not post the review again: it is on the pull request.\n"
    "Check review {review_id} on pull request {number} yourself.")
READ_BACK_DIFFERS = (
    "review {review_id} was posted, but GitHub's copy differs from what was asked for: "
    "{differences}.\n"
    "Do not post the review again: it is on the pull request.\n"
    "Check review {review_id} on pull request {number} yourself.")


class ReviewFileUnusable(Exception):
    pass


class GhFailed(Exception):
    pass


def read_review_file(path):
    """Return (verdict, body, comments) from the review file, or raise ReviewFileUnusable."""
    try:
        review = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as error:
        raise ReviewFileUnusable(f"could not be read: {error}")
    except ValueError as error:
        raise ReviewFileUnusable(f"is not JSON: {error}")
    if not isinstance(review, dict) or set(review) != {"verdict", "body", "comments"}:
        raise ReviewFileUnusable(
            "must hold one JSON object with exactly \"verdict\", \"body\" and \"comments\"")
    verdict, body, comments = review["verdict"], review["body"], review["comments"]
    if verdict not in POSTED_VERDICTS:
        raise ReviewFileUnusable(
            f"has the verdict {verdict!r}; only {' and '.join(POSTED_VERDICTS)} are posted")
    if not isinstance(body, str) or not body.strip():
        raise ReviewFileUnusable("has no \"body\" text")
    if not isinstance(comments, list) or not all(
            isinstance(comment, dict) and set(comment) == {"path", "line", "body"}
            and isinstance(comment["path"], str)
            and isinstance(comment["line"], int) and not isinstance(comment["line"], bool)
            and isinstance(comment["body"], str)
            for comment in comments):
        raise ReviewFileUnusable(
            "has a \"comments\" entry without a text \"path\", a number \"line\" and a text \"body\"")
    return verdict, body, comments


def commentable_lines(files):
    """Map each path to the new-side line numbers its diff shows, from GitHub's pull request files."""
    lines = {}
    for entry in files:
        shown = lines.setdefault(entry["filename"], set())
        line = None
        for patch_line in (entry.get("patch") or "").split("\n"):
            header = HUNK_HEADER.match(patch_line)
            if header:
                line = int(header.group(1))
            elif line is not None and patch_line[:1] in ("+", " "):
                shown.add(line)
                line += 1
    return lines


def with_outside_comments_in_body(body, comments, lines):
    """Return (body, comments) with every comment GitHub would refuse moved into the body."""
    inside = [comment for comment in comments if comment["line"] in lines.get(comment["path"], ())]
    outside = [comment for comment in comments if comment not in inside]
    if outside:
        body = (body.rstrip("\n") + "\n\n" + OUTSIDE_THE_DIFF_HEADING + "\n"
                + "\n".join(f"- `{comment['path']}:{comment['line']}`: {comment['body']}"
                            for comment in outside))
    return body, inside


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
                        help="the review: a JSON object with verdict, body and comments")
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
    try:
        pages = gh_json(token, ["--paginate", "--slurp",
                                f"repos/{REPOSITORY}/pulls/{number}/files?per_page=100"])
        lines = commentable_lines(entry for page in pages for entry in page)
    except (GhFailed, KeyError, TypeError, AttributeError) as error:
        print(NOT_POSTED.format(reason=f"reading the pull request's diff failed: {reason_of(error)}"),
              file=sys.stderr)
        return EXIT_NOT_POSTED
    body, comments = with_outside_comments_in_body(body, comments, lines)
    event = verdict if author == MERGE_LANE_ACCOUNT else "COMMENT"
    try:
        posted = gh_json(token, ["-X", "POST", f"repos/{REPOSITORY}/pulls/{number}/reviews",
                                 "--input", "-"],
                         input_text=json.dumps({"commit_id": head, "event": event,
                                                "body": f"{verdict}\n\n{body}",
                                                "comments": comments}))
        review_id = posted["id"]
    except (GhFailed, KeyError, TypeError) as error:
        print(POST_FAILED.format(reason=reason_of(error), number=number, head=head),
              file=sys.stderr)
        return EXIT_NOT_POSTED
    try:
        copy = gh_json(token, [f"repos/{REPOSITORY}/pulls/{number}/reviews/{review_id}"])
        differences = [f"{field} is {copy.get(field)!r}, not {wanted!r}"
                       for field, wanted in (("state", EVENT_STATES[event]), ("commit_id", head))
                       if copy.get(field) != wanted]
    except (GhFailed, AttributeError) as error:
        print(READ_BACK_FAILED.format(review_id=review_id, reason=reason_of(error), number=number),
              file=sys.stderr)
        return EXIT_NOT_POSTED
    if differences:
        print(READ_BACK_DIFFERS.format(review_id=review_id, differences="; ".join(differences),
                                       number=number),
              file=sys.stderr)
        return EXIT_NOT_POSTED
    print(f"review {review_id} posted on pull request {number} as {event}, verdict {verdict}, "
          f"on commit {head}; GitHub's copy reads back as {EVENT_STATES[event]}")
    return EXIT_POSTED


if __name__ == "__main__":
    sys.exit(main())
