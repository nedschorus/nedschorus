#!/usr/bin/env python3
"""Tests for merge-lane-unreviewed-prs-count-then-next-agent-seat-go-ahead-to-open-surviving-mutant-test-prs.py.

The program is loaded by path and its main() is called in this process with a
scratch --state-directory and a fake `gh` first on PATH. The fake gh logs its
arguments and prints the pages a case writes, as `gh api graphql --paginate
--slurp` prints them, or exits with the code and error a case writes. The idle
sweep's run_headless is replaced by a fake sender that logs its prompt and
returns the outcome a case sets, so the idle sweep's own check judges it.

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
        self.sender_answers()

    def gh_answer(self, stdout="", exit_code=0, stderr=""):
        (self.directory / "gh-answer.json").write_text(
            json.dumps({"stdout": stdout, "exit": exit_code, "stderr": stderr}))

    def run(self, *extra):
        saved_path = os.environ["PATH"]
        saved_run_headless = program.idle_sweep.run_headless
        program.idle_sweep.run_headless = self.fake_run_headless
        os.environ["PATH"] = f"{self.directory / 'bin'}{os.pathsep}{saved_path}"
        os.environ["GO_AHEAD_TEST_DIRECTORY"] = str(self.directory)
        output = io.StringIO()
        try:
            with contextlib.redirect_stdout(output):
                code = program.main(["--state-directory", str(self.state), *extra])
        finally:
            os.environ["PATH"] = saved_path
            program.idle_sweep.run_headless = saved_run_headless
        return code, output.getvalue()

    def released(self):
        path = self.state / program.RELEASED_FILE_NAME
        return ([json.loads(line)["agent_seat"] for line in path.read_text().splitlines()]
                if path.exists() else [])

    def sender_answers(self, *outcomes):
        """Each outcome: ("sent", seat), ("error", text) or ("sent-to", other entry)."""
        self.outcomes = list(outcomes)
        self.prompts = []

    def fake_run_headless(self, prompt, schema, tools, working_directory, timeout_seconds):
        self.prompts.append({"prompt": prompt, "tools": tools, "schema": schema,
                             "working_directory": working_directory})
        kind, value = self.outcomes.pop(0)
        outcome = program.idle_sweep.HeadlessOutcome()
        if kind == "error":
            outcome.error = value
        else:
            outcome.sends = [{"to": f"{value} [1c88e6]", "message": "text", "succeeded": True,
                              "result": "ok"}]
            outcome.answer = {"sent": True, "reason": "sent"}
        return outcome

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
    case.sender_answers(("sent", "reboot-test"))
    code, output = case.run()
    check("10 unreviewed open pull requests: the first agent-seat is sent the message and "
          "recorded as released, and RELEASED is printed, exit 0",
          code == 0 and output.startswith("RELEASED reboot-test\n")
          and "10 open pull requests, not drafts, have no review from ned-review-merge" in output
          and case.released() == ["reboot-test"], f"exit {code}\n{output}")
    prompt = case.prompts[0]["prompt"] if case.prompts else ""
    check("the message is sent with the idle sweep's own sender prompt, tools and schema, and "
          "says the agent-seat may open them one per source file, at most 5 at a time",
          len(case.prompts) == 1
          and prompt.startswith(program.idle_sweep.SENDER_PROMPT.split("{seat}")[0])
          and program.idle_sweep.FIND_THE_ENTRY.format(seat="reboot-test") in prompt
          and "You may now open your pull requests that only add tests for surviving mutants: "
              "one per source file, with at most 5 open at a time." in prompt
          and program.idle_sweep.DO_NOT_REPLY_SENTENCE in prompt
          and case.prompts[0]["tools"] == program.idle_sweep.SENDING_TOOLS
          and case.prompts[0]["schema"] == program.idle_sweep.SEND_ANSWER_SCHEMA
          and case.prompts[0]["working_directory"]
              == case.state / program.SENDER_WORKING_DIRECTORY_NAME, case.prompts)
    check("gh reads every page of the open pull requests with the merge account's reviews",
          case.gh_calls() and case.gh_calls()[0][:4] == ["api", "graphql", "--paginate",
                                                         "--slurp"]
          and any('reviews(author: "ned-review-merge"' in argument
                  for argument in case.gh_calls()[0]), case.gh_calls())
    case.sender_answers(("sent", "MD-skills"))
    code, output = case.run()
    check("once one is released, the next run releases the next agent-seat in the file's order",
          code == 0 and output.startswith("RELEASED MD-skills\n")
          and case.released() == ["reboot-test", "MD-skills"], f"exit {code}\n{output}")

    for name, outcome, said in (
            ("send-fails", ("error", "stopped after 300 seconds"),
             "the headless agent-session that sends the message failed: stopped after 300 "
             "seconds"),
            ("check-fails", ("sent-to", "MD-skills"), "no SendMessage to reboot-test succeeded")):
        case = Case(root, name)
        case.gh_answer(pages(ten_unreviewed))
        case.sender_answers(outcome)
        code, output = case.run()
        check(f"when the {name.split('-')[0]} fails, nothing is recorded, what failed is printed, "
              f"no RELEASED line, exit 2, which the merge script reports without failing the "
              f"merge",
              code == 2 and case.released() == [] and said in output
              and "RELEASED" not in output and "the next merge tries again" in output,
              f"exit {code}\n{output}")
        case.sender_answers(("sent", "reboot-test"))
        code, output = case.run()
        check(f"after the {name.split('-')[0]} failed, the next run sends to the same agent-seat "
              f"again",
              code == 0 and output.startswith("RELEASED reboot-test\n"), f"exit {code}\n{output}")

    case = Case(root, "eleven")
    case.gh_answer(pages([pull_request(number) for number in range(1, 12)]))
    code, output = case.run()
    check("11 unreviewed open pull requests name no agent-seat and print the count, exit 1",
          code == 1 and "RELEASE" not in output and case.prompts == []
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
    case.gh_answer(pages(ten_unreviewed))
    case.sender_answers(("sent", "reboot-test"))
    case.state.chmod(0o555)
    try:
        code, output = case.run()
    finally:
        case.state.chmod(0o755)
    check("a sent release that cannot be recorded exits 2, says the message will be sent again, "
          "and gives the line to append",
          code == 2 and "reboot-test was sent the release message, but it could not be recorded"
          in output and "each merge sends reboot-test the message again" in output
          and '"agent_seat": "reboot-test"' in output, f"exit {code}\n{output}")

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
