#!/usr/bin/env python3
"""Tests for merge-lane-pull-request-reviewer-review-post-and-read-back.py.

Runs the program with HOME set to a scratch directory holding a mac-claude
token file, and a stand-in gh first on PATH, so no case reaches GitHub. The
stand-in gh logs each call, with the GH_TOKEN it was given and its standard
input, answers the author lookup with FAKE_GH_AUTHOR, answers the post with
review id 42, and answers the read-back with the event's state and the posted
commit unless FAKE_GH_READ_BACK_STATE or FAKE_GH_READ_BACK_COMMIT replaces
one. FAKE_GH_POST_REPLY and FAKE_GH_READ_BACK_REPLY replace the whole reply
to the post or the read-back. FAKE_GH_FAILS names the call that fails:
author, post or read-back. FAKE_GH_KILLED names the call whose gh prints its
usual reply and is then killed by a signal.

Run: python3 scripts/merge-lane-pull-request-reviewer-review-post-and-read-back-test.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROGRAM = Path(__file__).with_name("merge-lane-pull-request-reviewer-review-post-and-read-back.py")
HEAD = "0123456789abcdef0123456789abcdef01234567"
TOKEN = "stand-in-mac-claude-token-value"
FAKE_GH = """#!/usr/bin/env python3
import json, os, signal, sys
from pathlib import Path
state = Path(os.environ["FAKE_GH_STATE"])
arguments = sys.argv[1:]
stdin = sys.stdin.read() if "--input" in arguments else ""
with open(state / "calls.jsonl", "a") as log:
    log.write(json.dumps({"arguments": arguments, "token": os.environ.get("GH_TOKEN"),
                          "stdin": stdin}) + "\\n")
path = next(argument for argument in arguments if argument.startswith("repos/"))
call = ("post" if "POST" in arguments else "read-back" if "/reviews/" in path else "author")
if os.environ.get("FAKE_GH_FAILS") == call:
    print("gh: HTTP 502: Bad Gateway", file=sys.stderr)
    sys.exit(1)
if call == "author":
    print(json.dumps({"user": {"login": os.environ.get("FAKE_GH_AUTHOR", "an author")}}))
elif call == "post":
    (state / "posted.json").write_text(stdin)
    print(os.environ.get("FAKE_GH_POST_REPLY", json.dumps({"id": 42})))
elif "FAKE_GH_READ_BACK_REPLY" in os.environ:
    print(os.environ["FAKE_GH_READ_BACK_REPLY"])
else:
    posted = json.loads((state / "posted.json").read_text())
    states = {"APPROVE": "APPROVED", "REQUEST_CHANGES": "CHANGES_REQUESTED", "COMMENT": "COMMENTED"}
    print(json.dumps({"id": 42,
                      "state": os.environ.get("FAKE_GH_READ_BACK_STATE", states[posted["event"]]),
                      "commit_id": os.environ.get("FAKE_GH_READ_BACK_COMMIT", posted["commit_id"])}))
if os.environ.get("FAKE_GH_KILLED") == call:
    sys.stdout.flush()
    os.kill(os.getpid(), signal.SIGTERM)
"""

failures = []


def check(name, condition, detail=""):
    print(("PASS  " if condition else "FAIL  ") + name)
    if not condition:
        failures.append(name)
        if detail:
            print("      " + detail.replace("\n", "\n      "))


class Run:
    def __init__(self, completed, calls, posted):
        self.code = completed.returncode
        self.stdout, self.stderr = completed.stdout, completed.stderr
        self.calls, self.posted = calls, posted
        self.detail = (f"exit {self.code}\nstdout: {self.stdout}\nstderr: {self.stderr}"
                       f"\ncalls: {calls}")


def run_program(scratch, review_text, token=TOKEN, arguments=("--pull-request", "7", "--head-commit", HEAD),
                **fake_gh_environment):
    case = Path(tempfile.mkdtemp(dir=scratch))
    home, state, fake_gh_directory = case / "home", case / "state", case / "fake-gh"
    for directory in (home, state, fake_gh_directory):
        directory.mkdir()
    if token is not None:
        (home / ".config" / "nedschorus").mkdir(parents=True)
        (home / ".config" / "nedschorus" / "mac-claude.token").write_text(token + "\n")
    (fake_gh_directory / "gh").write_text(FAKE_GH)
    (fake_gh_directory / "gh").chmod(0o755)
    review_file = case / "review-to-post.txt"
    if review_text is not None:
        review_file.write_text(review_text)
    completed = subprocess.run(
        [sys.executable, str(PROGRAM), *arguments, str(review_file)],
        capture_output=True, text=True,
        env={**os.environ, "HOME": str(home), "FAKE_GH_STATE": str(state),
             "PATH": f"{fake_gh_directory}{os.pathsep}{os.environ.get('PATH', '')}",
             **fake_gh_environment})
    calls_file = state / "calls.jsonl"
    calls = ([json.loads(line) for line in calls_file.read_text().splitlines()]
             if calls_file.exists() else [])
    posted_file = state / "posted.json"
    posted = json.loads(posted_file.read_text()) if posted_file.exists() else None
    return Run(completed, calls, posted)


def review(tag, body="The review body.", comments=None):
    content = {"body": body}
    if comments is not None:
        content["comments"] = comments
    return tag + "\n" + json.dumps(content)


def main():
    scratch = Path(tempfile.mkdtemp(prefix="reviewer-review-post-test-")).resolve()
    try:
        comment = {"path": "scripts/thing.py", "line": 3, "body": "A finding."}
        result = run_program(scratch, review("#approve", comments=[comment]),
                             FAKE_GH_AUTHOR="ned-review-merge")
        check("an approval on a pull request ned-review-merge opened is posted with event "
              "APPROVE, on the head commit, with the verdict as the body's first line and the "
              "inline comments", result.code == 0 and result.posted == {
                  "commit_id": HEAD, "event": "APPROVE",
                  "body": "APPROVE\n\nThe review body.", "comments": [comment]}, result.detail)
        check("every gh call uses mac-claude's token from its token file",
              len(result.calls) == 3 and all(call["token"] == TOKEN for call in result.calls),
              result.detail)
        check("the review is read back by the id the post returned",
              result.calls[-1]["arguments"] == ["api", "repos/nedschorus/nedschorus/pulls/7/reviews/42"]
              if result.calls else False, result.detail)
        check("success names the review, the event and the commit, and never prints the token",
              "review 42 posted on pull request 7 as APPROVE" in result.stdout
              and HEAD in result.stdout and TOKEN not in result.stdout + result.stderr,
              result.detail)

        result = run_program(scratch, review("#request_changes"))
        check("a request for changes on a pull request another account opened is posted with "
              "event COMMENT and REQUEST_CHANGES as the body's first line",
              result.code == 0 and result.posted is not None
              and result.posted["event"] == "COMMENT"
              and result.posted["body"] == "REQUEST_CHANGES\n\nThe review body."
              and result.posted["comments"] == [], result.detail)

        result = run_program(scratch, review("#approve"), FAKE_GH_AUTHOR="ubuntu-claude")
        check("an approval on a pull request opened by an account whose name sorts after "
              "ned-review-merge is posted with event COMMENT", result.code == 0
              and result.posted is not None and result.posted["event"] == "COMMENT", result.detail)

        result = run_program(scratch, review("#request_changes"), FAKE_GH_AUTHOR="ned-review-merge")
        check("a request for changes on a pull request ned-review-merge opened is posted with "
              "event REQUEST_CHANGES", result.code == 0 and result.posted is not None
              and result.posted["event"] == "REQUEST_CHANGES", result.detail)

        result = run_program(scratch, review("#approve"), FAKE_GH_READ_BACK_STATE="PENDING")
        check("a read-back state other than the event's exits 2 and names the state",
              result.code == 2 and "state is 'PENDING', not 'COMMENTED'" in result.stderr
              and "was posted" in result.stderr and "Do not post the review again" in result.stderr,
              result.detail)

        result = run_program(scratch, review("#approve"), FAKE_GH_READ_BACK_COMMIT="f" * 40)
        check("a read-back commit other than the head commit exits 2 and names the commit",
              result.code == 2 and f"commit_id is '{'f' * 40}', not '{HEAD}'" in result.stderr,
              result.detail)

        result = run_program(scratch, review("#approve"), FAKE_GH_READ_BACK_COMMIT="0" * 40)
        check("a read-back commit that sorts before the head commit exits 2 and names the commit",
              result.code == 2 and f"commit_id is '{'0' * 40}', not '{HEAD}'" in result.stderr,
              result.detail)

        for missing, arguments in (("--pull-request", ("--head-commit", HEAD)),
                                   ("--head-commit", ("--pull-request", "7"))):
            result = run_program(scratch, review("#approve"), arguments=arguments)
            check(f"a command without {missing} exits 2, names the option, and calls no gh",
                  result.code == 2 and missing in result.stderr and not result.calls, result.detail)

        result = run_program(scratch, None)
        check("a missing review file exits 2 before any gh call",
              result.code == 2 and "could not be read" in result.stderr and not result.calls,
              result.detail)
        for name, text, reason in (
                ("a first line that is not a verdict tag", review("APPROVE"), "starts with 'APPROVE'"),
                ("text after the tag that is not JSON", "#approve\nThe review body.", "no valid JSON"),
                ("a JSON object with a key other than body and comments",
                 "#approve\n" + json.dumps({"body": "b", "event": "APPROVE"}), "only \"body\""),
                ("an empty body", review("#approve", body=" "), "no \"body\" text"),
                ("a comment without a line", review("#approve", comments=[{"path": "p", "body": "b"}]),
                 "a number \"line\"")):
            result = run_program(scratch, text)
            check(f"a review file with {name} exits 2, says why, and calls no gh",
                  result.code == 2 and reason in result.stderr and "review not posted" in result.stderr
                  and not result.calls, result.detail)

        result = run_program(scratch, review("#approve"), token=None)
        check("a missing token file exits 2 before any gh call",
              result.code == 2 and "could not read mac-claude's token" in result.stderr
              and not result.calls, result.detail)
        result = run_program(scratch, review("#approve"), token="")
        check("an empty token file exits 2 before any gh call",
              result.code == 2 and "is empty" in result.stderr and not result.calls, result.detail)

        result = run_program(scratch, review("#approve"), FAKE_GH_FAILS="author")
        check("a failed author lookup exits 2, says the review was not posted, names gh's "
              "error, and posts nothing", result.code == 2
              and "review not posted: reading the pull request's author failed: gh exited 1: "
              "gh: HTTP 502" in result.stderr and result.posted is None, result.detail)
        result = run_program(scratch, review("#approve"), FAKE_GH_FAILS="post")
        check("a failed post exits 2, says the review may be posted, names gh's error, and "
              "says not to run the command again", result.code == 2
              and "review may or may not be posted: posting the review failed: gh exited 1: "
              "gh: HTTP 502" in result.stderr
              and "Do not run this command again" in result.stderr, result.detail)
        result = run_program(scratch, review("#approve"), FAKE_GH_FAILS="read-back")
        check("a failed read-back exits 2, says review 42 was posted, and names gh's error",
              result.code == 2 and "review 42 was posted, but reading it back failed: "
              "gh exited 1: gh: HTTP 502" in result.stderr, result.detail)
        result = run_program(scratch, review("#approve"), FAKE_GH_KILLED="author")
        check("an author lookup whose gh is killed by a signal after printing its reply exits 2 "
              "and posts nothing", result.code == 2
              and "review not posted: reading the pull request's author failed: gh exited -15"
              in result.stderr and result.posted is None, result.detail)
        result = run_program(scratch, review("#approve"), FAKE_GH_POST_REPLY="{}")
        check("a post reply without a review id exits 2 and says the review may be posted",
              result.code == 2 and "review may or may not be posted: posting the review failed: "
              "GitHub's reply was not in the expected shape: KeyError: 'id'" in result.stderr, result.detail)
        result = run_program(scratch, review("#approve"), FAKE_GH_POST_REPLY="not json")
        check("a post reply that is not JSON exits 2 and says the review may be posted",
              result.code == 2 and "review may or may not be posted: posting the review failed: gh "
              "printed no JSON" in result.stderr, result.detail)
        result = run_program(scratch, review("#approve"), FAKE_GH_READ_BACK_REPLY="[]")
        check("a read-back reply that is not an object exits 2 and says review 42 was posted",
              result.code == 2 and "review 42 was posted, but reading it back failed: GitHub's "
              "reply was not in the expected shape: AttributeError" in result.stderr, result.detail)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    if failures:
        print(f"\n{len(failures)} case(s) failed")
        return 1
    print("\nall cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
