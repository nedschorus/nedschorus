#!/usr/bin/env python3
"""Post a pull request review, the Claude reviewer's as mac-claude or merge-lane-2's as ned-review-merge, then read it back from GitHub.

Did the review get posted on the named nc-head-commit, as the review file
says? Exits 0 if the review was posted and read back as expected, 2 otherwise.

Usage:
  scripts/merge-lane-pull-request-reviewer-review-post-and-read-back.py
      --pull-request N --head-commit SHA
      [--github-account mac-claude|ned-review-merge] <review file>

The review file is one JSON object with exactly "verdict", APPROVE or
REQUEST_CHANGES; "body", the review's text; and "comments", a list of inline
comments. A COULD_NOT_REVIEW verdict is refused: nothing is posted for a
review that did not finish.

With --github-account mac-claude, the default, the file is the Claude
reviewer's answer without its "note", which is for merge-lane-2 and never
posted: the shape of merge-lane-pull-request-claude-reviewer-review-schema.json
less "note", each comment with exactly "path", "line" and "body". A file that
still carries "note" is refused, like any other extra key. It is posted with
the token in ~/.config/nedschorus/mac-claude.token, with the file's verdict.
Its event is the verdict when the pull request's author is ned-review-merge,
because GitHub refuses an approving review from a pull request's author and
merge-lane-2 approves as that account; for any other author the event is
COMMENT, and merge-lane-2 records the verdict itself.

With --github-account ned-review-merge, the file is merge-lane-2's own review,
which restates every finding the round's reviewers raised, each comment with
exactly "path", "line", "body" and "finding_category", one of FINDING_CATEGORIES, the
four categories of the goals and philosophy page. It is posted with the merge
account's token, read as
merge-lane-pull-request-helpers-common-options-paths-and-token.py reads it,
and its event is always the verdict; GitHub refuses that review on a pull
request ned-review-merge opened, and the post fails. For this file, this
program alone writes what the fix-round program,
pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py,
reads blocking findings by, using that program's BLOCKING_MARKER_PATTERN:
- each must-fix-now comment is posted opening with "**Blocks** ", and a
  comment whose body already opens with a blocking mark is refused;
- when N comments are must-fix-now, N at least 1, the body carries
  "**Blocking: N**". No count is written when N is 0, because the fix-round
  program checks a stated count on every review of the frozen-head, a
  COMMENTED one included, against the round's marked comments;
- the posted verdict is REQUEST_CHANGES when any comment is must-fix-now and
  APPROVE otherwise. A file whose verdict is REQUEST_CHANGES with no
  must-fix-now comment is refused rather than posted as an approval.

GitHub refuses a whole review when one inline comment is on a line outside the
pull request's diff, so each comment whose path and line are not on the new
side of the diff GitHub reports for the pull request is moved into the body,
under a heading, as `path:line: comment`, and the success line ends with how
many were moved. A file whose diff GitHub does not show, such as a binary
file, takes no inline comments. A must-fix-now comment moved into the body
still counts in N but carries no inline mark, so the fix-round program's count
check refuses that round instead of missing the finding.

The body starts with a line APPROVE or REQUEST_CHANGES, so the verdict shows
even when the review is posted as a comment. The posted review is then read
back by the id GitHub returned, and its state and commit must be the ones
asked for.

An interrupt or SIGTERM during the post or the read-back kills gh and exits 2,
saying the review may or may not be posted if it came during the post, and
that review <id> was posted if it came after GitHub returned the id.
"""

import argparse
import importlib.util
import json
import os
import re
import signal
import subprocess
import sys
from pathlib import Path


def load_program(file_name, module_name):
    spec = importlib.util.spec_from_file_location(
        module_name, Path(__file__).resolve().with_name(file_name))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


common = load_program("merge-lane-pull-request-helpers-common-options-paths-and-token.py",
                      "merge_lane_pull_request_helpers_common")
fix_round = load_program(
    "pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-"
    "answered-check.py", "pull_request_fix_round_author_brief")

REPOSITORY = "nedschorus/nedschorus"
MAC_CLAUDE_ACCOUNT = "mac-claude"
MERGE_LANE_ACCOUNT = "ned-review-merge"
POSTED_VERDICTS = ("APPROVE", "REQUEST_CHANGES")
# The goals and philosophy page's four categories of a finding; only the first blocks.
FINDING_CATEGORIES = ("must-fix-now", "fix-next", "fix-in-maintenance", "file-for-later")
BLOCKING_CATEGORY = "must-fix-now"
BLOCKING_MARK = "**Blocks** "
BLOCKING_COUNT_FORMAT = "**Blocking: {count}**"
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
    "If the file came from a reviewer's run, "
    "scripts/merge-lane-pull-request-claude-reviewer-headless-run-and-review-post.py, which ran "
    "the reviewer, should have refused this file instead of handing it to the posting script.\n"
    "In that case, do not run "
    "scripts/merge-lane-pull-request-claude-reviewer-headless-run-and-review-post.py again, for "
    "any pull request, until the user answers.\n"
    "Tell the user this whole message.")
NOT_POSTED = (
    "review not posted: {reason}.\n"
    "Do not post the review any other way.\n"
    "If the cause above is one you can fix, fix it and run the same command again; otherwise, "
    "tell the user this message.")
POST_FAILED = (
    "review may or may not be posted: posting the review failed: {reason}\n"
    "GitHub may have made the review before the failure, and a second post would add a second "
    "review.\n"
    "Before running this command again, list {account}'s reviews on commit {head} of pull "
    "request {number}:\n"
    "  gh api --paginate 'repos/{repository}/pulls/{number}/reviews' --jq "
    "'.[] | select(.user.login == \"{account}\" and .commit_id == \"{head}\") "
    "| [.id, .state, .html_url] | @tsv'\n"
    "If it lists nothing, run the posting command that printed this message again.\n"
    "If it lists one or more reviews, do not post again: {account} already has a review on this "
    "commit, whether this command's post or an earlier one, and the list gives each one's id and "
    "link.")
READ_BACK_FAILED = (
    "review {review_id} was posted, but reading it back failed: {reason}\n"
    "Do not post the review again: it is on the pull request.\n"
    "Check review {review_id} on pull request {number} yourself.")
READ_BACK_DIFFERS = (
    "review {review_id} was posted on pull request {number}, but GitHub's copy differs from what "
    "was asked for: {differences}.\n"
    "The review is on the pull request as GitHub kept it: in each difference above, the first "
    "value is what GitHub kept and the second is what was asked for.\n"
    "Do not post the review again: a second post adds a second review and leaves this one as "
    "it is.\n"
    "Look at the review with:\n"
    "  gh api 'repos/{repository}/pulls/{number}/reviews/{review_id}' --jq "
    "'[.state, .commit_id, .html_url] | @tsv'\n"
    "Then tell the user this whole message and what that command printed, and do nothing more "
    "with this review or this pull request's merge until the user answers.")


class ReviewFileUnusable(Exception):
    pass


class GhFailed(Exception):
    pass


def read_review_file(path, account):
    """Return (verdict, body, comments) from the account's review file, or raise ReviewFileUnusable."""
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
    categorized = account == MERGE_LANE_ACCOUNT
    keys = {"path", "line", "body", "finding_category"} if categorized else {"path", "line", "body"}
    if not isinstance(comments, list) or not all(
            isinstance(comment, dict) and set(comment) == keys
            and isinstance(comment["path"], str)
            and isinstance(comment["line"], int) and not isinstance(comment["line"], bool)
            and isinstance(comment["body"], str)
            for comment in comments):
        raise ReviewFileUnusable(
            "has a \"comments\" entry that is not exactly a text \"path\", a number \"line\" and "
            "a text \"body\"" + (", and a \"finding_category\"," if categorized else ",")
            + " with no other keys")
    if not categorized:
        return verdict, body, comments
    for comment in comments:
        where = f"{comment['path']}:{comment['line']}"
        if comment["finding_category"] not in FINDING_CATEGORIES:
            raise ReviewFileUnusable(
                f"has a comment on {where} whose \"finding_category\" is {comment['finding_category']!r}, not one "
                f"of {', '.join(FINDING_CATEGORIES)}")
        mark = fix_round.BLOCKING_MARKER_PATTERN.match(comment["body"].lstrip())
        if mark:
            raise ReviewFileUnusable(
                f"has a comment on {where} whose body already opens with the blocking mark "
                f"{mark.group(0)}; this program writes that mark for each {BLOCKING_CATEGORY} "
                f"comment, so leave it out of the body")
    if verdict == "REQUEST_CHANGES" and not any(
            comment["finding_category"] == BLOCKING_CATEGORY for comment in comments):
        raise ReviewFileUnusable(
            f"has the verdict 'REQUEST_CHANGES' but no comment whose \"finding_category\" is "
            f"{BLOCKING_CATEGORY}, so it would be posted as an approval")
    return verdict, body, comments


def with_blocking_marks(body, comments):
    """Return (verdict, body, comments) as posted for categorized comments: the verdict set by
    the must-fix-now ones, their count in the body, each opened with the mark, and no finding_category
    key left."""
    blocking = [comment["finding_category"] == BLOCKING_CATEGORY for comment in comments]
    count = sum(blocking)
    verdict = "REQUEST_CHANGES" if count else "APPROVE"
    if count:
        body = BLOCKING_COUNT_FORMAT.format(count=count) + "\n\n" + body
    comments = [{"path": comment["path"], "line": comment["line"],
                 "body": (BLOCKING_MARK if blocks else "") + comment["body"]}
                for comment, blocks in zip(comments, blocking)]
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


def read_token(account):
    """Return the account's token, or raise GhFailed naming why it cannot be used."""
    if account == MERGE_LANE_ACCOUNT:
        try:
            return common.read_merge_account_token()
        except common.MergeAccountTokenUnusable as error:
            raise GhFailed(str(error))
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
        description="Post a pull request review, the Claude reviewer's as mac-claude or "
                    "merge-lane-2's as ned-review-merge, then read it back. Exits 0 if the review was posted and read back as "
                    "expected, 2 otherwise.")
    parser.add_argument("--pull-request", type=int, required=True,
                        help="the pull request's number")
    parser.add_argument("--head-commit", required=True,
                        help="the full hash of the nc-head-commit the review is on")
    parser.add_argument("--github-account", choices=(MAC_CLAUDE_ACCOUNT, MERGE_LANE_ACCOUNT),
                        default=MAC_CLAUDE_ACCOUNT,
                        help="the GitHub account the review is posted as, which also sets the "
                             "review file's format (default: mac-claude)")
    parser.add_argument("review_file", type=Path,
                        help="the review: a JSON object with verdict, body and comments")
    return parser.parse_args(argv)


def exit_on_sigterm(signal_number, frame):
    raise SystemExit(128 + signal_number)


def main(argv=None):
    # SIGTERM must raise, as an interrupt does, so the post and the read-back can report
    # what they leave on GitHub.
    signal.signal(signal.SIGTERM, exit_on_sigterm)
    arguments = parse_arguments(argv)
    number, head, account = arguments.pull_request, arguments.head_commit, arguments.github_account
    try:
        verdict, body, comments = read_review_file(arguments.review_file, account)
    except ReviewFileUnusable as error:
        print(REVIEW_FILE_UNUSABLE.format(path=arguments.review_file, reason=error),
              file=sys.stderr)
        return EXIT_NOT_POSTED
    try:
        token = read_token(account)
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
    if account == MERGE_LANE_ACCOUNT:
        verdict, body, comments = with_blocking_marks(body, comments)
    body, inline_comments = with_outside_comments_in_body(body, comments, lines)
    moved_count = len(comments) - len(inline_comments)
    comments = inline_comments
    event = (verdict if account == MERGE_LANE_ACCOUNT or author == MERGE_LANE_ACCOUNT
             else "COMMENT")
    review_id = None
    try:
        try:
            posted = gh_json(token, ["-X", "POST", f"repos/{REPOSITORY}/pulls/{number}/reviews",
                                     "--input", "-"],
                             input_text=json.dumps({"commit_id": head, "event": event,
                                                    "body": f"{verdict}\n\n{body}",
                                                    "comments": comments}))
            review_id = posted["id"]
        except (GhFailed, KeyError, TypeError) as error:
            print(POST_FAILED.format(reason=reason_of(error), number=number, head=head,
                                     repository=REPOSITORY, account=account),
                  file=sys.stderr)
            return EXIT_NOT_POSTED
        try:
            copy = gh_json(token, [f"repos/{REPOSITORY}/pulls/{number}/reviews/{review_id}"])
            differences = [f"{field} is {copy.get(field)!r}, not {wanted!r}"
                           for field, wanted in (("state", EVENT_STATES[event]),
                                                 ("commit_id", head))
                           if copy.get(field) != wanted]
        except (GhFailed, AttributeError) as error:
            print(READ_BACK_FAILED.format(review_id=review_id, reason=reason_of(error),
                                          number=number),
                  file=sys.stderr)
            return EXIT_NOT_POSTED
        if differences:
            print(READ_BACK_DIFFERS.format(review_id=review_id,
                                           differences="; ".join(differences), number=number,
                                           repository=REPOSITORY),
                  file=sys.stderr)
            return EXIT_NOT_POSTED
        moved = f"; {moved_count} comment(s) moved into the body" if moved_count else ""
        print(f"review {review_id} posted on pull request {number} by {account} as {event}, verdict "
              f"{verdict}, on commit {head}; GitHub's copy reads back as {EVENT_STATES[event]}"
              f"{moved}")
        return EXIT_POSTED
    except (KeyboardInterrupt, SystemExit):
        # gh_json's subprocess.run has killed gh before this runs, so nothing more is sent.
        reason = "this command was interrupted"
        if review_id is None:
            print(POST_FAILED.format(reason=reason, number=number, head=head,
                                     repository=REPOSITORY, account=account),
                  file=sys.stderr)
        else:
            print(READ_BACK_FAILED.format(review_id=review_id, reason=reason, number=number),
                  file=sys.stderr)
        return EXIT_NOT_POSTED


if __name__ == "__main__":
    sys.exit(main())
