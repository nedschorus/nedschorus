#!/usr/bin/env python3
"""Tests for merge-lane-pull-request-reviewer-review-post-and-read-back.py.

Runs the program with HOME set to a scratch directory holding a mac-claude
token file and a ned-review-merge token file, and a stand-in gh first on PATH,
so no case reaches GitHub. The
stand-in gh logs each call, with the GH_TOKEN it was given and its standard
input, answers the author lookup with FAKE_GH_AUTHOR, answers the pull
request's files with FAKE_GH_FILES or one page holding scripts/thing.py with
new-side lines 1 to 4 in its diff, answers the post with
review id 42, and answers the read-back with the event's state and the posted
commit unless FAKE_GH_READ_BACK_STATE or FAKE_GH_READ_BACK_COMMIT replaces
one. FAKE_GH_POST_REPLY and FAKE_GH_READ_BACK_REPLY replace the whole reply
to the post or the read-back. FAKE_GH_FAILS names the call that fails:
author, files, post or read-back. FAKE_GH_KILLED names the call whose gh prints its
usual reply and is then killed by a signal. FAKE_GH_HANGS names the call whose gh
writes its pid to gh-hanging and sleeps, for a case that signals the program then.

The round-trip cases load the fix-round program, which reads blocking findings,
and hand its blocking_findings the posted body and comments in place of what
its gh would read from GitHub.

Run: python3 scripts/merge-lane-pull-request-reviewer-review-post-and-read-back-test.py
"""

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import importlib.util
import time
from pathlib import Path

PROGRAM = Path(__file__).with_name("merge-lane-pull-request-reviewer-review-post-and-read-back.py")
HEAD = "0123456789abcdef0123456789abcdef01234567"
TOKEN = "stand-in-mac-claude-token-value"
MERGE_TOKEN = "stand-in-ned-review-merge-token-value"
FIX_ROUND_PROGRAM = Path(__file__).with_name(
    "pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-"
    "answered-check.py")
FAKE_GH = """#!/usr/bin/env python3
import json, os, signal, sys, time
from pathlib import Path
state = Path(os.environ["FAKE_GH_STATE"])
arguments = sys.argv[1:]
stdin = sys.stdin.read() if "--input" in arguments else ""
with open(state / "calls.jsonl", "a") as log:
    log.write(json.dumps({"arguments": arguments, "token": os.environ.get("GH_TOKEN"),
                          "stdin": stdin}) + "\\n")
path = next(argument for argument in arguments if argument.startswith("repos/"))
call = ("post" if "POST" in arguments else "read-back" if "/reviews/" in path
        else "files" if "/files" in path else "author")
if os.environ.get("FAKE_GH_HANGS") == call:
    (state / "gh-hanging").write_text(str(os.getpid()))
    time.sleep(60)
if os.environ.get("FAKE_GH_FAILS") == call:
    print("gh: HTTP 502: Bad Gateway", file=sys.stderr)
    sys.exit(1)
if call == "author":
    print(json.dumps({"user": {"login": os.environ.get("FAKE_GH_AUTHOR", "an author")}}))
elif call == "files":
    print(os.environ.get("FAKE_GH_FILES", json.dumps(
        [[{"filename": "scripts/thing.py", "patch": "@@ -1,2 +1,4 @@\\n a\\n+b\\n+c\\n d"}]])))
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


def running(pid):
    """Whether pid is a live process, not gone and not a zombie."""
    try:
        status = Path(f"/proc/{pid}/status").read_text()
    except OSError:
        return False
    return "\nState:\tZ" not in status


def run_program(scratch, review_text, token=TOKEN, arguments=("--pull-request", "7", "--head-commit", HEAD),
                interrupt=None, merge_token=MERGE_TOKEN, **fake_gh_environment):
    """Run the program; with interrupt, a signal, send it once the stand-in gh is hanging."""
    case = Path(tempfile.mkdtemp(dir=scratch))
    home, state, fake_gh_directory = case / "home", case / "state", case / "fake-gh"
    for directory in (home, state, fake_gh_directory):
        directory.mkdir()
    if token is not None:
        (home / ".config" / "nedschorus").mkdir(parents=True)
        (home / ".config" / "nedschorus" / "mac-claude.token").write_text(token + "\n")
    if merge_token is not None:
        (home / ".config" / "nedschorus").mkdir(parents=True, exist_ok=True)
        (home / ".config" / "nedschorus" / "ned-review-merge.token").write_text(merge_token + "\n")
    (fake_gh_directory / "gh").write_text(FAKE_GH)
    (fake_gh_directory / "gh").chmod(0o755)
    review_file = case / "review-to-post.txt"
    if review_text is not None:
        review_file.write_text(review_text)
    process = subprocess.Popen(
        [sys.executable, str(PROGRAM), *arguments, str(review_file)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env={**os.environ, "HOME": str(home), "FAKE_GH_STATE": str(state),
             "PATH": f"{fake_gh_directory}{os.pathsep}{os.environ.get('PATH', '')}",
             **fake_gh_environment})
    hanging = state / "gh-hanging"
    if interrupt is not None:
        deadline = time.monotonic() + 20
        while not (hanging.exists() and hanging.read_text()) and time.monotonic() < deadline:
            time.sleep(0.05)
        process.send_signal(interrupt)
    try:
        stdout, stderr = process.communicate(timeout=30)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        stderr += "\n(the program was still running 30 s after the signal)"
    completed = subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)
    calls_file = state / "calls.jsonl"
    calls = ([json.loads(line) for line in calls_file.read_text().splitlines()]
             if calls_file.exists() else [])
    posted_file = state / "posted.json"
    posted = json.loads(posted_file.read_text()) if posted_file.exists() else None
    run = Run(completed, calls, posted)
    time.sleep(0.2 if interrupt is not None else 0)
    run.gh_left_running = hanging.exists() and running(int(hanging.read_text()))
    return run


def review(verdict, body="The review body.", comments=None):
    return json.dumps({"verdict": verdict, "body": body, "comments": comments or []})


def finding(line, category, body=None):
    return {"path": "scripts/thing.py", "line": line, "body": body or f"Finding on line {line}.",
            "category": category}


MERGE_LANE_ARGUMENTS = ("--pull-request", "7", "--head-commit", HEAD,
                        "--github-account", "ned-review-merge")


def load_fix_round_program():
    spec = importlib.util.spec_from_file_location("fix_round_program", FIX_ROUND_PROGRAM)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fix_round_blocking_findings(fix_round, posted_reviews):
    """Run the fix-round program's blocking_findings on posted reviews, the first the anchor;
    return its findings, or the text of its refusal."""
    reviews = [{"id": index + 1, "html_url": f"review-{index + 1}", "body": posted["body"]}
               for index, posted in enumerate(posted_reviews)]
    comments_by_id = {review["id"]: posted["comments"]
                      for review, posted in zip(reviews, posted_reviews)}
    fix_round.gh_json_lines = lambda arguments: comments_by_id[
        int(next(argument for argument in arguments if "/reviews/" in argument).split("/")[-2])]
    try:
        return fix_round.blocking_findings(7, reviews[0], reviews)
    except fix_round.Refused as refusal:
        return str(refusal)


def merge_lane_cases(scratch):
    """merge-lane-2's categorized review file, posted as ned-review-merge."""
    must, nxt, maintenance, later = (finding(2, "must-fix-now"), finding(3, "fix-next"),
                                     finding(4, "must-fix-now"), finding(1, "fix-in-maintenance"))
    result = run_program(scratch, review("REQUEST_CHANGES", comments=[must, nxt, maintenance, later]),
                         arguments=MERGE_LANE_ARGUMENTS)
    check("merge-lane-2's file is posted as REQUEST_CHANGES with the merge account's token, the "
          "must-fix-now count in the body, each must-fix-now comment opened with the mark, the "
          "others unmarked, and no category key sent",
          result.code == 0 and result.posted == {
              "commit_id": HEAD, "event": "REQUEST_CHANGES",
              "body": "REQUEST_CHANGES\n\n**Blocking: 2**\n\nThe review body.",
              "comments": [
                  {"path": "scripts/thing.py", "line": 2, "body": "**Blocks** Finding on line 2."},
                  {"path": "scripts/thing.py", "line": 3, "body": "Finding on line 3."},
                  {"path": "scripts/thing.py", "line": 4, "body": "**Blocks** Finding on line 4."},
                  {"path": "scripts/thing.py", "line": 1, "body": "Finding on line 1."}]}
          and len(result.calls) == 4 and all(call["token"] == MERGE_TOKEN for call in result.calls)
          and "by ned-review-merge as REQUEST_CHANGES" in result.stdout
          and MERGE_TOKEN not in result.stdout + result.stderr, result.detail)
    merge_lane_posted = result.posted

    result = run_program(scratch, review("APPROVE", comments=[finding(2, "fix-next"),
                                                              finding(3, "file-for-later")]),
                         arguments=MERGE_LANE_ARGUMENTS, FAKE_GH_AUTHOR="an author")
    check("merge-lane-2's file with no must-fix-now comment is posted as an approval with event "
          "APPROVE on another author's pull request, and states no blocking count",
          result.code == 0 and result.posted is not None and result.posted["event"] == "APPROVE"
          and result.posted["body"] == "APPROVE\n\nThe review body."
          and "Blocks" not in json.dumps(result.posted["comments"]), result.detail)
    result = run_program(scratch, review("APPROVE", comments=[finding(2, "must-fix-now")]),
                         arguments=MERGE_LANE_ARGUMENTS)
    check("merge-lane-2's APPROVE file with a must-fix-now comment is posted as REQUEST_CHANGES",
          result.code == 0 and result.posted is not None
          and result.posted["event"] == "REQUEST_CHANGES"
          and result.posted["body"].startswith("REQUEST_CHANGES\n\n**Blocking: 1**\n\n"),
          result.detail)

    for name, comments, verdict, reason in (
            ("a finding without a category", [{"path": "p", "line": 1, "body": "b"}], "APPROVE",
             "and a \"category\", with no other keys"),
            ("a finding whose category is not one of the four", [finding(2, "blocking")],
             "APPROVE", "whose \"category\" is 'blocking', not one of must-fix-now, fix-next, "
                        "fix-in-maintenance, file-for-later"),
            ("a finding whose category is not text", [finding(2, ["must-fix-now"])],
             "REQUEST_CHANGES", "whose \"category\" is ['must-fix-now'], not one of"),
            ("a finding opening with a hand-written blocking mark",
             [finding(2, "must-fix-now", "**Blocks** b")], "REQUEST_CHANGES",
             "comment on scripts/thing.py:2 whose body already opens with the blocking mark "
             "**Blocks**"),
            ("a fix-next finding opening, after spaces, with a hand-written mark",
             [finding(3, "fix-next", "  **Blocks:** b")], "APPROVE",
             "already opens with the blocking mark **Blocks:**"),
            ("a REQUEST_CHANGES verdict with nothing must-fix-now", [finding(2, "fix-next")],
             "REQUEST_CHANGES", "has the verdict 'REQUEST_CHANGES' but no comment whose "
                                "\"category\" is must-fix-now"),
            ("a COULD_NOT_REVIEW verdict", [], "COULD_NOT_REVIEW",
             "has the verdict 'COULD_NOT_REVIEW'")):
        result = run_program(scratch, review(verdict, comments=comments),
                             arguments=MERGE_LANE_ARGUMENTS)
        check(f"merge-lane-2's file with {name} exits 2, says why, and calls no gh",
              result.code == 2 and reason in result.stderr and "review not posted" in result.stderr
              and not result.calls, result.detail)
    result = run_program(scratch, review("APPROVE", comments=[finding(2, "fix-next")]))
    check("a mac-claude file whose comments carry a category is refused, since the Claude "
          "reviewer's comments have exactly path, line and body",
          result.code == 2 and "a text \"body\", with no other keys" in result.stderr
          and not result.calls, result.detail)

    result = run_program(scratch, review("APPROVE"), arguments=MERGE_LANE_ARGUMENTS,
                         merge_token=None)
    check("--github-account ned-review-merge with no merge account token file exits 2 before any "
          "gh call", result.code == 2 and "could not read the merge account's token"
          in result.stderr and "review not posted" in result.stderr and not result.calls,
          result.detail)
    result = run_program(scratch, review("APPROVE"), arguments=MERGE_LANE_ARGUMENTS,
                         merge_token="")
    check("--github-account ned-review-merge with an empty merge account token file exits 2 "
          "before any gh call", result.code == 2 and "is empty" in result.stderr
          and not result.calls, result.detail)
    result = run_program(scratch, review("APPROVE"), arguments=MERGE_LANE_ARGUMENTS,
                         FAKE_GH_FAILS="post")
    check("a failed post as ned-review-merge gives the command that lists ned-review-merge's "
          "reviews on the nc-head-commit",
          result.code == 2 and "list ned-review-merge's reviews" in result.stderr
          and '.user.login == "ned-review-merge"' in result.stderr, result.detail)
    result = run_program(scratch, review("APPROVE"), arguments=(
        "--pull-request", "7", "--head-commit", HEAD, "--github-account", "someone-else"))
    check("a --github-account other than mac-claude and ned-review-merge exits 2 and calls no gh",
          result.code == 2 and "--github-account" in result.stderr and not result.calls,
          result.detail)

    fix_round = load_fix_round_program()
    found = fix_round_blocking_findings(fix_round, [merge_lane_posted])
    check("round trip: the fix-round program reads the two posted must-fix-now comments, and "
          "the posted count agrees with them",
          isinstance(found, list) and [item["line"] for item in found] == [2, 4], str(found))
    mac_claude = run_program(scratch, review("APPROVE", comments=[
        {"path": "scripts/thing.py", "line": 3, "body": "A remark."}]))
    found = fix_round_blocking_findings(fix_round, [merge_lane_posted, mac_claude.posted])
    check("round trip: a mac-claude review of the same head with no count beside it leaves the "
          "fix-round program's count check passing",
          isinstance(found, list) and [item["line"] for item in found] == [2, 4], str(found))
    approving = run_program(scratch, review("APPROVE", comments=[finding(3, "fix-next")]),
                            arguments=MERGE_LANE_ARGUMENTS)
    found = fix_round_blocking_findings(fix_round, [merge_lane_posted, approving.posted])
    check("round trip: a merge-lane-2 review of the same head with nothing must-fix-now states "
          "no count, so the fix-round program's count check still passes",
          isinstance(found, list) and [item["line"] for item in found] == [2, 4]
          and fix_round.BLOCKING_COUNT_PATTERN.search(approving.posted["body"]) is None,
          f"{found}\n{approving.detail}")
    moved = run_program(scratch, review("REQUEST_CHANGES", comments=[
        finding(2, "must-fix-now"),
        {"path": "scripts/other.py", "line": 1, "body": "Outside.", "category": "must-fix-now"}]),
        arguments=MERGE_LANE_ARGUMENTS)
    found = fix_round_blocking_findings(fix_round, [moved.posted])
    check("round trip: a must-fix-now comment moved into the body counts in the posted count, "
          "so the fix-round program refuses the round instead of missing the finding",
          isinstance(found, str) and "says **Blocking: 2**, but 1" in found,
          f"{found}\n{moved.detail}")


def main():
    scratch = Path(tempfile.mkdtemp(prefix="reviewer-review-post-test-")).resolve()
    try:
        merge_lane_cases(scratch)
        comment = {"path": "scripts/thing.py", "line": 3, "body": "A finding."}
        result = run_program(scratch, review("APPROVE", comments=[comment]),
                             FAKE_GH_AUTHOR="ned-review-merge")
        check("an approval on a pull request ned-review-merge opened is posted with event "
              "APPROVE, on the nc-head-commit, with the verdict as the body's first line and the "
              "inline comments", result.code == 0 and result.posted == {
                  "commit_id": HEAD, "event": "APPROVE",
                  "body": "APPROVE\n\nThe review body.", "comments": [comment]}, result.detail)
        check("every gh call uses mac-claude's token from its token file",
              len(result.calls) == 4 and all(call["token"] == TOKEN for call in result.calls),
              result.detail)
        check("the review is read back by the id the post returned",
              result.calls[-1]["arguments"] == ["api", "repos/nedschorus/nedschorus/pulls/7/reviews/42"]
              if result.calls else False, result.detail)
        check("success names the review, the event and the commit, and never prints the token",
              "review 42 posted on pull request 7 by mac-claude as APPROVE" in result.stdout
              and HEAD in result.stdout and TOKEN not in result.stdout + result.stderr,
              result.detail)
        check("when no comment moved into the body, the success line says nothing of moving",
              "moved" not in result.stdout, result.detail)

        result = run_program(scratch, review("REQUEST_CHANGES"))
        check("a request for changes on a pull request another account opened is posted with "
              "event COMMENT and REQUEST_CHANGES as the body's first line",
              result.code == 0 and result.posted is not None
              and result.posted["event"] == "COMMENT"
              and result.posted["body"] == "REQUEST_CHANGES\n\nThe review body."
              and result.posted["comments"] == [], result.detail)

        result = run_program(scratch, review("APPROVE"), FAKE_GH_AUTHOR="ubuntu-claude")
        check("an approval on a pull request opened by an account whose name sorts after "
              "ned-review-merge is posted with event COMMENT", result.code == 0
              and result.posted is not None and result.posted["event"] == "COMMENT", result.detail)

        result = run_program(scratch, review("REQUEST_CHANGES"), FAKE_GH_AUTHOR="ned-review-merge")
        check("a request for changes on a pull request ned-review-merge opened is posted with "
              "event REQUEST_CHANGES", result.code == 0 and result.posted is not None
              and result.posted["event"] == "REQUEST_CHANGES", result.detail)

        result = run_program(scratch, review("APPROVE"), FAKE_GH_READ_BACK_STATE="PENDING")
        check("a read-back state other than the event's exits 2 and names the state",
              result.code == 2 and "state is 'PENDING', not 'COMMENTED'" in result.stderr
              and "was posted" in result.stderr and "Do not post the review again" in result.stderr,
              result.detail)

        result = run_program(scratch, review("APPROVE"), FAKE_GH_READ_BACK_COMMIT="f" * 40)
        check("a read-back commit other than the nc-head-commit exits 2 and names the commit",
              result.code == 2 and f"commit_id is '{'f' * 40}', not '{HEAD}'" in result.stderr,
              result.detail)

        result = run_program(scratch, review("APPROVE"), FAKE_GH_READ_BACK_COMMIT="0" * 40)
        check("a read-back commit that sorts before the nc-head-commit exits 2 and names the commit",
              result.code == 2 and f"commit_id is '{'0' * 40}', not '{HEAD}'" in result.stderr,
              result.detail)

        for missing, arguments in (("--pull-request", ("--head-commit", HEAD)),
                                   ("--head-commit", ("--pull-request", "7"))):
            result = run_program(scratch, review("APPROVE"), arguments=arguments)
            check(f"a command without {missing} exits 2, names the option, and calls no gh",
                  result.code == 2 and missing in result.stderr and not result.calls, result.detail)

        result = run_program(scratch, None)
        check("a missing review file exits 2 before any gh call",
              result.code == 2 and "could not be read" in result.stderr and not result.calls,
              result.detail)
        for name, text, reason in (
                ("a COULD_NOT_REVIEW verdict", review("COULD_NOT_REVIEW"),
                 "has the verdict 'COULD_NOT_REVIEW'"),
                ("a verdict that is not one of the schema's", review("MAYBE"), "'MAYBE'"),
                ("text that is not JSON", "#approve\nThe review body.", "is not JSON"),
                ("a JSON object with a key other than verdict, body and comments",
                 json.dumps({"verdict": "APPROVE", "body": "b", "comments": [], "event": "APPROVE"}),
                 "exactly \"verdict\""),
                ("a reviewer's answer that still carries its note",
                 json.dumps({"verdict": "APPROVE", "body": "b", "comments": [], "note": "n"}),
                 "exactly \"verdict\""),
                ("a JSON object without comments",
                 json.dumps({"verdict": "APPROVE", "body": "b"}), "exactly \"verdict\""),
                ("an empty body", review("APPROVE", body=" "), "no \"body\" text"),
                ("a comment without a line", review("APPROVE", comments=[{"path": "p", "body": "b"}]),
                 "a number \"line\""),
                ("a comment whose line is true", review("APPROVE", comments=[
                    {"path": "p", "line": True, "body": "b"}]), "a number \"line\"")):
            result = run_program(scratch, text)
            check(f"a review file with {name} exits 2, says why, and calls no gh",
                  result.code == 2 and reason in result.stderr and "review not posted" in result.stderr
                  and not result.calls, result.detail)

        result = run_program(scratch, review("APPROVE"), token=None)
        check("a missing token file exits 2 before any gh call",
              result.code == 2 and "could not read mac-claude's token" in result.stderr
              and not result.calls, result.detail)
        result = run_program(scratch, review("APPROVE"), token="")
        check("an empty token file exits 2 before any gh call",
              result.code == 2 and "is empty" in result.stderr and not result.calls, result.detail)

        result = run_program(scratch, review("APPROVE"), FAKE_GH_FAILS="author")
        check("a failed author lookup exits 2, says the review was not posted, names gh's "
              "error, and posts nothing", result.code == 2
              and "review not posted: reading the pull request's author failed: gh exited 1: "
              "gh: HTTP 502" in result.stderr and result.posted is None, result.detail)
        result = run_program(scratch, review("APPROVE"), FAKE_GH_FAILS="files")
        check("a failed read of the pull request's diff exits 2, says the review was not "
              "posted, names gh's error, and posts nothing", result.code == 2
              and "review not posted: reading the pull request's diff failed: gh exited 1: "
              "gh: HTTP 502" in result.stderr and result.posted is None, result.detail)
        result = run_program(scratch, review("APPROVE"), FAKE_GH_FILES=json.dumps([{"a": 1}]))
        check("a pull request files reply in an unexpected shape exits 2 and posts nothing",
              result.code == 2 and "reading the pull request's diff failed: GitHub's reply was "
              "not in the expected shape" in result.stderr and result.posted is None, result.detail)

        inside = {"path": "scripts/thing.py", "line": 4, "body": "On a context line."}
        outside_line = {"path": "scripts/thing.py", "line": 9, "body": "Below the hunk."}
        outside_file = {"path": "scripts/other.py", "line": 1, "body": "In a file the diff lacks."}
        binary = {"path": "image.png", "line": 1, "body": "On a binary file."}
        result = run_program(
            scratch, review("REQUEST_CHANGES", comments=[inside, outside_line, outside_file, binary]),
            FAKE_GH_FILES=json.dumps([[{"filename": "scripts/thing.py",
                                        "patch": "@@ -1,2 +1,4 @@\n a\n+b\n+c\n d"}],
                                      [{"filename": "image.png"}]]))
        check("comments on lines, files and binary files outside the diff move into the body "
              "under a heading, a comment on a context line stays inline, and pages are joined",
              result.code == 0 and result.posted is not None
              and result.posted["comments"] == [inside]
              and result.posted["body"] == (
                  "REQUEST_CHANGES\n\nThe review body.\n\n"
                  "Comments on lines outside this pull request's diff:\n"
                  "- `scripts/thing.py:9`: Below the hunk.\n"
                  "- `scripts/other.py:1`: In a file the diff lacks.\n"
                  "- `image.png:1`: On a binary file."), result.detail)
        check("the success line says how many comments moved into the body",
              result.stdout.rstrip("\n").endswith("; 3 comment(s) moved into the body"),
              result.detail)
        removed = {"path": "scripts/thing.py", "line": 2, "body": "On the old side only."}
        result = run_program(
            scratch, review("APPROVE", comments=[removed]),
            FAKE_GH_FILES=json.dumps([[{"filename": "scripts/thing.py",
                                        "patch": "@@ -1,3 +1,1 @@\n a\n-gone\n-also"}]]))
        check("a removed line does not count as a new-side line",
              result.code == 0 and result.posted is not None and result.posted["comments"] == []
              and "`scripts/thing.py:2`" in result.posted["body"], result.detail)
        second_hunk = {"path": "scripts/thing.py", "line": 21, "body": "In the second hunk."}
        between = {"path": "scripts/thing.py", "line": 4, "body": "Between the hunks."}
        result = run_program(
            scratch, review("APPROVE", comments=[second_hunk, between]),
            FAKE_GH_FILES=json.dumps([[{"filename": "scripts/thing.py",
                                        "patch": "@@ -1,1 +1,2 @@\n a\n+b\n"
                                                 "@@ -19,2 +20,3 @@\n x\n+y\n z"}]]))
        check("each hunk header restarts the line count: a comment in the second hunk stays "
              "inline, and one between the hunks moves into the body",
              result.code == 0 and result.posted is not None
              and result.posted["comments"] == [second_hunk]
              and "`scripts/thing.py:4`: Between the hunks." in result.posted["body"],
              result.detail)
        files_call = [call for call in result.calls if "/files" in " ".join(call["arguments"])]
        check("the pull request's files are read every page at once",
              bool(files_call) and files_call[0]["arguments"][:3] == ["api", "--paginate", "--slurp"],
              result.detail)

        result = run_program(scratch, review("APPROVE"), FAKE_GH_FAILS="post")
        check("a failed post exits 2, says the review may be posted, names gh's error, and "
              "gives the command that lists mac-claude's reviews on the nc-head-commit",
              result.code == 2
              and "review may or may not be posted: posting the review failed: gh exited 1: "
              "gh: HTTP 502" in result.stderr
              and "Before running this command again, list mac-claude's reviews" in result.stderr
              and "gh api --paginate 'repos/nedschorus/nedschorus/pulls/7/reviews'" in result.stderr
              and f'.commit_id == "{HEAD}"' in result.stderr, result.detail)
        result = run_program(scratch, review("APPROVE"), FAKE_GH_FAILS="read-back")
        check("a failed read-back exits 2, says review 42 was posted, and names gh's error",
              result.code == 2 and "review 42 was posted, but reading it back failed: "
              "gh exited 1: gh: HTTP 502" in result.stderr, result.detail)
        result = run_program(scratch, review("APPROVE"), FAKE_GH_KILLED="author")
        check("an author lookup whose gh is killed by a signal after printing its reply exits 2 "
              "and posts nothing", result.code == 2
              and "review not posted: reading the pull request's author failed: gh exited -15"
              in result.stderr and result.posted is None, result.detail)
        result = run_program(scratch, review("APPROVE"), FAKE_GH_POST_REPLY="{}")
        check("a post reply without a review id exits 2 and says the review may be posted",
              result.code == 2 and "review may or may not be posted: posting the review failed: "
              "GitHub's reply was not in the expected shape: KeyError: 'id'" in result.stderr, result.detail)
        result = run_program(scratch, review("APPROVE"), FAKE_GH_POST_REPLY="not json")
        check("a post reply that is not JSON exits 2 and says the review may be posted",
              result.code == 2 and "review may or may not be posted: posting the review failed: gh "
              "printed no JSON" in result.stderr, result.detail)
        result = run_program(scratch, review("APPROVE"), FAKE_GH_READ_BACK_REPLY="[]")
        check("a read-back reply that is not an object exits 2 and says review 42 was posted",
              result.code == 2 and "review 42 was posted, but reading it back failed: GitHub's "
              "reply was not in the expected shape: AttributeError" in result.stderr, result.detail)

        for signal_number in (signal.SIGINT, signal.SIGTERM):
            name = signal.Signals(signal_number).name
            result = run_program(scratch, review("APPROVE"), interrupt=signal_number,
                                 FAKE_GH_HANGS="post")
            check(f"{name} during the post kills gh, exits 2, says the review may or may not be "
                  f"posted, and gives the command that lists mac-claude's reviews on the head "
                  f"commit",
                  result.code == 2 and not result.gh_left_running
                  and "review may or may not be posted: posting the review failed: this command "
                  "was interrupted" in result.stderr
                  and "gh api --paginate 'repos/nedschorus/nedschorus/pulls/7/reviews'"
                  in result.stderr and f'.commit_id == "{HEAD}"' in result.stderr, result.detail)
            result = run_program(scratch, review("APPROVE"), interrupt=signal_number,
                                 FAKE_GH_HANGS="read-back")
            check(f"{name} between the post and the end of the read-back kills gh, exits 2, and "
                  f"says review 42 was posted and not to post it again",
                  result.code == 2 and not result.gh_left_running
                  and "review 42 was posted, but reading it back failed: this command was "
                  "interrupted" in result.stderr
                  and "Do not post the review again: it is on the pull request." in result.stderr,
                  result.detail)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    if failures:
        print(f"\n{len(failures)} case(s) failed")
        return 1
    print("\nall cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
