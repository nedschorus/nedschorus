#!/usr/bin/env python3
"""Tests for merge-lane-unreviewed-prs-count-then-next-agent-seat-go-ahead-to-open-surviving-mutant-test-prs.py.

The program is loaded by path and its main() is called in this process with a
scratch --state-directory and a fake `gh` first on PATH. The fake gh logs its
arguments and prints the pages a case writes, as `gh api graphql --paginate
--slurp` prints them, or exits with the code and error a case writes.

Run: python3 scripts/merge-lane-unreviewed-prs-count-then-next-agent-seat-go-ahead-to-open-surviving-mutant-test-prs-test.py
"""

import contextlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

PROGRAM = Path(__file__).with_name(
    "merge-lane-unreviewed-prs-count-then-next-agent-seat-go-ahead-to-open-surviving-mutant-test-prs.py")
_spec = importlib.util.spec_from_file_location("surviving_mutant_test_prs_go_ahead", PROGRAM)
program = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(program)

SEATS = ["reboot-test", "MD-skills", "agent-instructions-editor", "merge-lane-2"]

FAKE_GH = r'''#!/usr/bin/env python3
import json, os, sys
directory = os.environ["GO_AHEAD_TEST_DIRECTORY"]
with open(os.path.join(directory, "gh-calls.log"), "a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\n")
answer = json.load(open(os.path.join(directory, "gh-answer.json")))
sys.stdout.write(answer.get("stdout", ""))
sys.stderr.write(answer.get("stderr", ""))
sys.exit(answer.get("exit", 0))
'''

failures = []


def check(name, condition, detail=""):
    print(("PASS  " if condition else "FAIL  ") + name)
    if not condition:
        failures.append(name)
        if detail:
            print("      " + str(detail).replace("\n", "\n      "))


def pull_request(number, draft=False, reviewed_on=None, head=None):
    """reviewed_on: None, "head", "older" or "other-account-on-head"."""
    head = head or f"{number:040x}"
    reviews = {"head": [{"commit": {"oid": head}}], "older": [{"commit": {"oid": "f" * 40}}],
               None: [], "deleted-commit": [{"commit": None}]}
    return {"number": number, "isDraft": draft, "headRefOid": head,
            "reviews": {"nodes": reviews.get(reviewed_on, [])}}


def pages(*page_nodes):
    return json.dumps([{"data": {"repository": {"pullRequests": {
        "pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": nodes}}}}
        for nodes in page_nodes])


class Case:
    def __init__(self, root, name, seats=SEATS, released=None):
        self.directory = root / name
        self.state = self.directory / "state"
        (self.directory / "bin").mkdir(parents=True)
        self.state.mkdir()
        (self.directory / "bin" / "gh").write_text(FAKE_GH)
        (self.directory / "bin" / "gh").chmod(0o755)
        if seats is not None:
            (self.state / program.AGENT_SEATS_FILE_NAME).write_text("\n".join(seats) + "\n\n")
        if released is not None:
            (self.state / program.RELEASED_FILE_NAME).write_text(released)

    def gh_answer(self, stdout="", exit_code=0, stderr=""):
        (self.directory / "gh-answer.json").write_text(
            json.dumps({"stdout": stdout, "exit": exit_code, "stderr": stderr}))

    def run(self, *extra):
        saved_path = os.environ["PATH"]
        os.environ["PATH"] = f"{self.directory / 'bin'}{os.pathsep}{saved_path}"
        os.environ["GO_AHEAD_TEST_DIRECTORY"] = str(self.directory)
        output = io.StringIO()
        try:
            with contextlib.redirect_stdout(output):
                code = program.main(["--state-directory", str(self.state), *extra])
        finally:
            os.environ["PATH"] = saved_path
        return code, output.getvalue()

    def released(self):
        path = self.state / program.RELEASED_FILE_NAME
        return ([json.loads(line)["agent_seat"] for line in path.read_text().splitlines()]
                if path.exists() else [])

    def gh_calls(self):
        log = self.directory / "gh-calls.log"
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def main():
    root = Path(tempfile.mkdtemp(prefix="surviving-mutant-test-prs-go-ahead-test-"))
    try:
        cases(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print(f"\n{len(failures)} failed" if failures else "\nall passed")
    return 1 if failures else 0


def cases(root):

    ten_unreviewed = [pull_request(number) for number in range(1, 11)]
    case = Case(root, "ten")
    case.gh_answer(pages(ten_unreviewed))
    code, output = case.run()
    check("10 unreviewed open pull requests name the first agent-seat for release, exit 0",
          code == 0 and output.startswith("RELEASE reboot-test\n")
          and "10 open pull requests, not drafts, have no review from ned-review-merge" in output,
          f"exit {code}\n{output}")
    check("the message says the agent-seat may open them one per source file, at most 5 at a "
          "time",
          "You may now open your pull requests that only add tests for surviving mutants: one "
          "per source file, with at most 5 open at a time." in output, output)
    check("the output gives the --record-released command for that agent-seat",
          f"--record-released reboot-test --state-directory {case.state}" in output, output)
    check("naming an agent-seat records nothing", case.released() == [], case.released())
    code, output = case.run()
    check("an agent-seat named but not recorded is named again on the next run",
          code == 0 and output.startswith("RELEASE reboot-test\n"), output)
    check("gh reads every page of the open pull requests with the merge account's reviews",
          case.gh_calls() and case.gh_calls()[0][:4] == ["api", "graphql", "--paginate",
                                                         "--slurp"]
          and any('reviews(author: "ned-review-merge"' in argument
                  for argument in case.gh_calls()[0]), case.gh_calls())

    code, output = case.run("--record-released", "reboot-test")
    check("--record-released records the agent-seat, exit 0",
          code == 0 and case.released() == ["reboot-test"]
          and "recorded reboot-test as released" in output, f"exit {code}\n{output}")
    check("--record-released does not call gh", len(case.gh_calls()) == 2, case.gh_calls())
    code, output = case.run()
    check("once recorded, the next agent-seat in the file's order is named",
          code == 0 and output.startswith("RELEASE MD-skills\n"), output)
    code, output = case.run("--record-released", "reboot-test")
    check("recording an agent-seat already recorded writes nothing and exits 0",
          code == 0 and case.released() == ["reboot-test"] and "already recorded" in output,
          f"exit {code}\n{output}")
    code, output = case.run("--record-released", "not-a-listed-seat")
    check("--record-released refuses an agent-seat the agent-seats file does not name, exit 2",
          code == 2 and case.released() == ["reboot-test"]
          and "'not-a-listed-seat' is not named in" in output, f"exit {code}\n{output}")

    case = Case(root, "eleven")
    case.gh_answer(pages([pull_request(number) for number in range(1, 12)]))
    code, output = case.run()
    check("11 unreviewed open pull requests name no agent-seat and print the count, exit 1",
          code == 1 and "RELEASE" not in output
          and output.startswith("11 open pull requests, not drafts"), f"exit {code}\n{output}")

    case = Case(root, "counted-right")
    case.gh_answer(pages(
        ten_unreviewed[:5],
        ten_unreviewed[5:] + [pull_request(20, draft=True), pull_request(21, reviewed_on="head"),
                              pull_request(22, reviewed_on="older"),
                              pull_request(23, reviewed_on="deleted-commit")]))
    code, output = case.run()
    check("across pages, drafts and pull requests reviewed on their head commit are not counted, "
          "and a review on an older commit or on a commit GitHub no longer has does not count "
          "as one",
          code == 1 and output.startswith("12 open pull requests"), f"exit {code}\n{output}")

    case = Case(root, "all-released",
                released="".join(json.dumps({"agent_seat": seat}) + "\n" for seat in SEATS))
    case.gh_answer(pages(ten_unreviewed))
    code, output = case.run()
    check("when every listed agent-seat is recorded as released, none is named, exit 1",
          code == 1 and "RELEASE" not in output and "already recorded as released" in output,
          f"exit {code}\n{output}")

    case = Case(root, "gh-fails")
    case.gh_answer(exit_code=1, stderr="HTTP 502: Bad Gateway\n")
    code, output = case.run()
    check("gh failing exits 2, quoting gh's error, and names no agent-seat",
          code == 2 and "exited 1: HTTP 502: Bad Gateway" in output and "RELEASE" not in output
          and "Run it again once:" in output, f"exit {code}\n{output}")

    case = Case(root, "gh-wrong-shape")
    case.gh_answer('{"data": null}')
    code, output = case.run()
    check("gh output not in the shape read exits 2",
          code == 2 and "not in the shape this program reads" in output,
          f"exit {code}\n{output}")

    case = Case(root, "no-seats-file", seats=None)
    case.gh_answer(pages(ten_unreviewed))
    code, output = case.run()
    check("a missing agent-seats file exits 2, naming the file",
          code == 2 and f"could not read the agent-seats file {case.state}" in output,
          f"exit {code}\n{output}")

    case = Case(root, "bad-record", released='{"agent_seat": "reboot-test"}\nnot json\n')
    case.gh_answer(pages(ten_unreviewed))
    code, output = case.run()
    check("a released record that is not JSON exits 2, naming its line",
          code == 2 and "line 2 of the released records" in output, f"exit {code}\n{output}")

    case = Case(root, "record-unwritable")
    case.state.chmod(0o555)
    try:
        code, output = case.run("--record-released", "reboot-test")
    finally:
        case.state.chmod(0o755)
    check("a record that cannot be written exits 2 and says the agent-seat is named again",
          code == 2 and "could not record reboot-test as released" in output
          and "each merge names reboot-test for release again" in output,
          f"exit {code}\n{output}")

    case = Case(root, "crash")
    case.gh_answer(pages(ten_unreviewed))
    saved = program.agent_seats_in_release_order
    program.agent_seats_in_release_order = lambda directory: 1 / 0
    try:
        code, output = case.run()
    finally:
        program.agent_seats_in_release_order = saved
    check("an exception nothing caught exits 2, not Python's 1",
          code == 2 and "the program crashed: ZeroDivisionError" in output,
          f"exit {code}\n{output}")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:  # noqa: BLE001 - a crashed test file must exit 2, not 1
        print(f"the test file crashed: {type(error).__name__}: {error}")
        sys.exit(2)
