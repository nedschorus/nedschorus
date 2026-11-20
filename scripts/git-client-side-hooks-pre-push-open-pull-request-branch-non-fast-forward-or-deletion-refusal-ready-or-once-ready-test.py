#!/usr/bin/env python3
"""Tests that scripts/git-client-side-hooks-pre-push-open-pull-request-branch-non-fast-forward-or-deletion-refusal.py
refuses a forced rewrite of every open pull request's head branch while the shared
rebase-or-replace answer is replace for every open pull request, and, once that module turns
on the rebase answer for a draft never marked ready, refuses one only when the pull request
is ready for review or once was, and lets one through for a draft that was never ready.

Run: python3 scripts/git-client-side-hooks-pre-push-open-pull-request-branch-non-fast-forward-or-deletion-refusal-ready-or-once-ready-test.py
Prints one line per case and exits non-zero if any case fails.

The check's main() is called with a fake runner standing in for git and gh, so each answer GitHub
can give, and each way gh can fail, is injected. The hook's wiring, and the rewrites of a ready
pull request with real git, are tested in scripts/git-client-side-hooks-pre-push-test.py.
"""

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

CHECK_PATH = (Path(__file__).resolve().parent / "git-client-side-hooks-pre-push-open-pull-request-"
              "branch-non-fast-forward-or-deletion-refusal.py")
_specification = importlib.util.spec_from_file_location("open_pull_request_branch_check",
                                                        CHECK_PATH)
check_module = importlib.util.module_from_spec(_specification)
_specification.loader.exec_module(check_module)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


PULL_REQUEST_URL = "https://github.com/example/example/pull/4242"
REWRITE_REFS = f"refs/heads/clean {'1' * 40} refs/heads/clean {'2' * 40}\n"
DELETION_REFS = f"(delete) {'0' * 40} refs/heads/clean {'2' * 40}\n"
FAST_FORWARD_REFS = REWRITE_REFS
SAVED_NOTE = (f"pre-push: the commit this push replaces on branch clean, {'2' * 40}, is saved "
              f"under refs/force-pushed-old-heads/clean/{'2' * 40}.\n")


def pull_request(**fields):
    entry = {"number": 4242, "title": "Clean work", "url": PULL_REQUEST_URL,
             "id": "PR_node_4242"}
    entry.update(fields)
    return entry


def graphql_answer(count, whole_timeline_count=7):
    """GitHub's answer: totalCount counts the whole timeline, filteredCount the events asked for."""
    return json.dumps({"data": {"node": {"timelineItems": {
        "totalCount": whole_timeline_count, "filteredCount": count}}}})


def completed(command, status=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(command, status, stdout, stderr)


class FakeRunner:
    """Answers git as for a rewrite (or a fast-forward), gh pr list with listed, and gh api
    graphql with graphql(command); records every gh call."""

    def __init__(self, listed, graphql=None, fast_forward=False):
        self.listed = listed
        self.graphql = graphql
        self.fast_forward = fast_forward
        self.gh_calls = []

    def __call__(self, command, **options):
        if command[:2] == ["git", "cat-file"]:
            return completed(command, 0, options["input"].strip() + " commit 200\n")
        if command[:3] == ["git", "merge-base", "--is-ancestor"]:
            return completed(command, 0 if self.fast_forward else 1)
        if command[:2] == ["git", "update-ref"]:
            return completed(command, 0)
        self.gh_calls.append(command)
        if command[:3] == ["gh", "pr", "list"]:
            listed = self.listed
            if isinstance(listed, dict):
                listed = listed.get(command[command.index("--head") + 1], [])
            return completed(command, 0, json.dumps(listed))
        if command[:3] == ["gh", "api", "graphql"]:
            if self.graphql is None:
                raise AssertionError("gh api graphql was asked")
            return self.graphql(command)
        raise AssertionError(f"unexpected command {command}")


def run(pushed_refs, runner):
    printed = io.StringIO()
    try:
        status = check_module.main(["origin", "url"], pushed_refs, printed, runner)
    except Exception as error:  # A crash is this case's failure, not the suite's.
        status = repr(error)
    return status, printed.getvalue()


def graphql_calls(runner):
    return [call for call in runner.gh_calls if call[:3] == ["gh", "api", "graphql"]]


def main():
    rebase_or_replace = check_module.rebase_or_replace
    gate = "REBASE_ONTO_MAIN_FOR_PULL_REQUESTS_NEVER_MARKED_READY_FOR_REVIEW_TURNED_ON"

    # While the shared answer is replace for every open pull request, a never-ready draft's
    # head is not rewritten either, and the timeline is not asked.
    setattr(rebase_or_replace, gate, False)
    runner = FakeRunner([pull_request(isDraft=True)])
    status, printed = run(REWRITE_REFS, runner)
    check("while the rebase answer is off, a forced rewrite of a never-ready draft is refused "
          "without asking the timeline, saying a draft's head is not rewritten either",
          status == check_module.EXIT_REFUSE_PUSH and graphql_calls(runner) == []
          and f"#4242 ({PULL_REQUEST_URL}), which is a draft: no open pull request's head is "
          "rewritten, and one that conflicts with main is replaced by a new pull request."
          in printed, (status, printed))

    # Every case below is the rebase answer turned on for a draft never marked ready.
    setattr(rebase_or_replace, gate, True)

    # A draft that was never ready may be rewritten; the timeline is asked about its node id.
    runner = FakeRunner([pull_request(isDraft=True)], lambda command: completed(
        command, 0, graphql_answer(0)))
    status, printed = run(REWRITE_REFS, runner)
    calls = graphql_calls(runner)
    check("a forced rewrite of a draft pull request that was never ready goes through",
          status == check_module.EXIT_ALLOW_PUSH and printed == SAVED_NOTE, (status, printed))
    check("the timeline lookup names the pull request's node id and asks for ready and "
          "convert-to-draft events",
          len(calls) == 1 and "id=PR_node_4242" in calls[0]
          and any("READY_FOR_REVIEW_EVENT, CONVERT_TO_DRAFT_EVENT" in word for word in calls[0])
          and "--json" in runner.gh_calls[0]
          and "isDraft" in runner.gh_calls[0][runner.gh_calls[0].index("--json") + 1],
          repr(runner.gh_calls))

    # A never-ready draft whose whole timeline holds commits, as every draft's does, may still
    # be rewritten: only the count of ready and convert-to-draft events decides.
    runner = FakeRunner([pull_request(isDraft=True)], lambda command: completed(
        command, 0, graphql_answer(0, whole_timeline_count=2)))
    status, printed = run(REWRITE_REFS, runner)
    calls = graphql_calls(runner)
    check("a never-ready draft whose timeline holds other items, totalCount 2 and filteredCount "
          "0, may be rewritten, and the lookup asks for filteredCount",
          status == check_module.EXIT_ALLOW_PUSH and printed == SAVED_NOTE
          and len(calls) == 1 and any("filteredCount" in word for word in calls[0]),
          (status, printed, calls))

    # A draft whose timeline holds a ready or convert-to-draft event was once ready: refused.
    runner = FakeRunner([pull_request(isDraft=True)], lambda command: completed(
        command, 0, graphql_answer(2)))
    status, printed = run(REWRITE_REFS, runner)
    check("a forced rewrite of a draft pull request that was once ready is refused, saying it "
          "was once ready",
          status == check_module.EXIT_REFUSE_PUSH
          and f"open pull request #4242 ({PULL_REQUEST_URL}), which is a draft now but was once "
          "ready for review: the update would replace the commits under review." in printed
          and "new commit on top of origin/clean" in printed, (status, printed))

    # A ready pull request is refused without asking the timeline.
    runner = FakeRunner([pull_request(isDraft=False)])
    status, printed = run(REWRITE_REFS, runner)
    check("a forced rewrite of a ready pull request is refused without asking the timeline",
          status == check_module.EXIT_REFUSE_PUSH and graphql_calls(runner) == []
          and f"#4242 ({PULL_REQUEST_URL}), which is ready for review:" in printed,
          (status, printed))

    # gh's answer without isDraft is read as ready, the safe side.
    runner = FakeRunner([pull_request()])
    status, printed = run(REWRITE_REFS, runner)
    check("an open pull request whose isDraft gh did not give is treated as ready",
          status == check_module.EXIT_REFUSE_PUSH and graphql_calls(runner) == [],
          (status, printed))

    # Deleting a never-ready draft's head branch still closes the pull request: refused.
    runner = FakeRunner([pull_request(isDraft=True)])
    status, printed = run(DELETION_REFS, runner)
    check("deleting the head branch of a draft pull request that was never ready is refused, "
          "without asking the timeline",
          status == check_module.EXIT_REFUSE_PUSH and graphql_calls(runner) == []
          and "it deletes branch clean, the head of open pull request #4242" in printed,
          (status, printed))

    # A fast-forward needs no lookup at all.
    runner = FakeRunner([pull_request(isDraft=False)], fast_forward=True)
    status, printed = run(FAST_FORWARD_REFS, runner)
    check("a fast-forward to a ready pull request's head goes through without asking gh",
          status == check_module.EXIT_ALLOW_PUSH and runner.gh_calls == [], (status, printed))

    # Every way the timeline lookup can fail refuses the push, saying what failed.
    def raises(error):
        def behaviour(command):
            raise error
        return behaviour

    for label, behaviour, detail in [
            ("gh exits nonzero",
             lambda command: completed(command, 1, "", "HTTP 502: Bad Gateway\nmore"),
             "gh api graphql exited with status 1: HTTP 502: Bad Gateway"),
            ("gh is killed by a signal", lambda command: completed(command, -9),
             "gh api graphql exited with status -9"),
            ("gh cannot be run", raises(FileNotFoundError(2, "No such file or directory", "gh")),
             "gh could not be run ("),
            ("gh does not answer in time", raises(subprocess.TimeoutExpired(["gh"], 10)),
             "gh api graphql did not answer within 10 seconds"),
            ("gh prints what is not JSON", lambda command: completed(command, 0, "not json"),
             "gh api graphql printed no count of the pull request's ready and draft events"),
            ("gh prints JSON with no count",
             lambda command: completed(command, 0, json.dumps({"data": {"node": None}})),
             "gh api graphql printed no count of the pull request's ready and draft events"),
            ("gh prints a count that is not a number",
             lambda command: completed(command, 0, graphql_answer("3")),
             "gh api graphql printed '3' as the count")]:
        runner = FakeRunner([pull_request(isDraft=True)], behaviour)
        status, printed = run(REWRITE_REFS, runner)
        check(f"when the timeline lookup fails because {label}, the rewrite is refused, saying "
              f"what failed and to tell the user, and offers no way past the refusal",
              status == check_module.EXIT_REFUSE_PUSH
              and "pre-push: this push is refused, because it forces an update to branch clean "
              f"on origin, the head of draft pull request #4242 ({PULL_REQUEST_URL}), and "
              "whether that pull request was ever ready for review could not be checked: "
              + detail in printed
              and "A draft's head may be rewritten only while it has never been ready for "
              "review, because until then nobody reviews it; once it has been ready, a review "
              "may hold its pushed commits, and the update would replace them." in printed
              and "Tell the user this whole message, and do not push clean again until he "
              "answers." in printed
              and "CLAUDE_MERGE_LANE_ASKED_FOR_THIS_REWRITE" not in printed, (status, printed))

    # A failed timeline lookup for one branch does not stop the check of the others: a rewrite
    # of a ready pull request's head later in the same push is refused as a rewrite.
    other_url = "https://github.com/example/example/pull/4343"
    runner = FakeRunner(
        {"clean": [pull_request(isDraft=True)],
         "other": [pull_request(number=4343, url=other_url, isDraft=False)]},
        lambda command: completed(command, 1, "", "HTTP 502: Bad Gateway"))
    several_refs = REWRITE_REFS + f"refs/heads/other {'3' * 40} refs/heads/other {'4' * 40}\n"
    status, printed = run(several_refs, runner)
    check("when the timeline lookup fails for one branch, a rewrite of a ready pull request's "
          "head later in the same push is still refused as a rewrite",
          status == check_module.EXIT_REFUSE_PUSH
          and f"open pull request #4343 ({other_url}), which is ready for review:" in printed,
          (status, printed))

    print()
    if failures:
        print(f"{len(failures)} case(s) failed")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
