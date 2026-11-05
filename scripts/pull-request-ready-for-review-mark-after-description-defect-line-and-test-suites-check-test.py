#!/usr/bin/env python3
"""Tests for scripts/pull-request-ready-for-review-mark-after-description-defect-line-and-test-suites-check.py.

Run: python3 scripts/pull-request-ready-for-review-mark-after-description-defect-line-and-test-suites-check-test.py
Prints one line per case and exits non-zero if any case fails.

main() is called with a fake runner standing in for gh, git and the test suite runner, so each
answer and each failure is injected and nothing reaches GitHub. One case runs the program as a
command, to show it starts and reads its argument.
"""

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

PROGRAM_PATH = (Path(__file__).resolve().parent / "pull-request-ready-for-review-mark-after-"
                "description-defect-line-and-test-suites-check.py")
_specification = importlib.util.spec_from_file_location("pull_request_ready_for_review_mark",
                                                        PROGRAM_PATH)
program = importlib.util.module_from_spec(_specification)
_specification.loader.exec_module(program)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


HEAD = "a" * 40
CHECKOUT = "/work/pull-request-checkout"
URL = "https://github.com/example/example/pull/77"
GOOD_BODY = "Adds a command.\n\n#no_defect_fixed\n"


def completed(command, status=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(command, status, stdout, stderr)


def view_answer(**fields):
    pull_request = {"number": 77, "title": "Adds a command", "url": URL, "state": "OPEN",
                    "isDraft": True, "headRefOid": HEAD, "body": GOOD_BODY}
    pull_request.update(fields)
    return json.dumps(pull_request)


class FakeRunner:
    """Answers gh pr view, git rev-parse HEAD, the test suite runner and gh pr ready; any of
    them can be replaced by a behaviour(command) that returns or raises. Records each call."""

    def __init__(self, view=None, rev_parse=None, suites=None, ready=None):
        self.behaviours = {
            "view": view or (lambda command: completed(command, 0, view_answer())),
            "rev-parse": rev_parse or (lambda command: completed(command, 0,
                                                                   f"{CHECKOUT}\n{HEAD}\n")),
            "suites": suites or (lambda command: completed(command, 0)),
            "ready": ready or (lambda command: completed(command, 0)),
        }
        self.calls = []

    def __call__(self, command, **options):
        if command[:3] == ["gh", "pr", "view"]:
            kind = "view"
        elif command[:2] == ["git", "rev-parse"]:
            kind = "rev-parse"
        elif command == program.selective_test_run_command(CHECKOUT):
            kind = "suites"
        elif command[:3] == ["gh", "pr", "ready"]:
            kind = "ready"
        else:
            raise AssertionError(f"unexpected command {command}")
        self.calls.append(kind)
        return self.behaviours[kind](command)


def run(runner, argv=("77",)):
    output, errors = io.StringIO(), io.StringIO()
    try:
        status = program.main(list(argv), runner, output, errors)
    except Exception as error:  # A crash is this case's failure, not the suite's.
        status = repr(error)
    return status, output.getvalue(), errors.getvalue()


def raises(error):
    def behaviour(command):
        raise error
    return behaviour


def answers(stdout):
    return lambda command: completed(command, 0, stdout)


def exits(status, stderr=""):
    return lambda command: completed(command, status, "", stderr)


RETRY_LINE = ("Run this command again once. If it fails the same way, tell the user, in one "
              "sentence, that pull request 77 could not be marked ready for review")


def main():
    # Every check passes: the pull request is marked ready, after the test suites ran.
    runner = FakeRunner()
    status, output, errors = run(runner)
    check("a draft with a defect line, its head checked out and passing suites is marked ready, "
          "the suites running before gh pr ready",
          status == program.EXIT_MARKED_READY and runner.calls == ["view", "rev-parse", "suites",
                                                                   "ready"]
          and f"#77 ({URL}) is marked ready for review." in output,
          (status, runner.calls, output, errors))
    check("the test suites run with the checkout's own runner, by the command CLAUDE.md gives "
          "for before a push",
          program.selective_test_run_command(CHECKOUT) == [
              "python3", CHECKOUT + "/scripts/run-all-test-suites.py",
              "--only-suites-whose-recorded-inputs-changed-since", "origin/main"]
          and f"running {CHECKOUT}/scripts/run-all-test-suites.py" in output,
          repr(program.selective_test_run_command(CHECKOUT)))

    # Already ready: nothing to do, nothing run.
    runner = FakeRunner(view=answers(view_answer(isDraft=False)))
    status, output, errors = run(runner)
    check("a pull request already ready for review is left as it is, with nothing run",
          status == program.EXIT_MARKED_READY and runner.calls == ["view"]
          and "already ready for review, so it was left as it is." in output,
          (status, output, errors))

    # Refusals, each before gh pr ready.
    for label, runner, expected_calls, expected_lines in [
            ("a closed pull request", FakeRunner(view=answers(view_answer(state="CLOSED"))),
             ["view"], ["is closed, not open, so it cannot be marked ready for review.",
                        "If you meant another pull request: run this again with its number.",
                        "If you meant this one and it is closed: read why with gh pr view 77 "
                        "--comments; when that reason no longer holds, reopen it with gh pr "
                        "reopen 77, then run this again; otherwise leave it closed."]),
            ("a merged pull request", FakeRunner(view=answers(view_answer(state="MERGED"))),
             ["view"], ["is merged, not open, so it cannot be marked ready for review.",
                        "If you meant this one and it is merged: its review is over, so there "
                        "is nothing to mark."]),
            ("a checkout whose HEAD is not the pushed head",
             FakeRunner(rev_parse=answers(f"{CHECKOUT}\n{'b' * 40}\n")), ["view", "rev-parse"],
             [f"this checkout's HEAD, {'b' * 12}, is not #77 ({URL})'s pushed nc-head-commit, "
              f"{'a' * 12}", "If this checkout has commits the pull request lacks: push them, "
              "then run this again.", "If the pull request has commits this checkout lacks: run "
              "git pull --ff-only, then run this again.", "If each has commits the other lacks: "
              "run git pull --no-rebase, which merges the pull request's commits into this "
              "checkout, then push, then run this again."]),
            ("a placeholder description with no defect line",
             FakeRunner(view=answers(view_answer(body="Work in progress.\n"))),
             ["view", "rev-parse"],
             ["description has no line beginning \"#root_cause\"",
              "Save the current description in a file with gh pr view 77 --json body -q .body > "
              "<file>",
              "#follow_up <full https://github.com/ link to the issue or pull request that will "
              "fix it>",
              "save the file with gh pr edit 77 --body-file <file>, which replaces the whole "
              "description"]),
            ("an empty description", FakeRunner(view=answers(view_answer(body=None))),
             ["view", "rev-parse"], ["description has no line beginning \"#root_cause\""]),
            ("a failing test suite", FakeRunner(suites=exits(1)), ["view", "rev-parse", "suites"],
             ["the test suites exited with status 1, so #77",
              "The failing suites are named above.",
              "Fix them, commit and push the fix, then run this again."]),
            ("a test suite runner that stops before judging every suite",
             FakeRunner(suites=exits(2)), ["view", "rev-parse", "suites"],
             ["scripts/run-all-test-suites.py exited with status 2, before judging every suite, "
              "so #77",
              "Its error is above.", RETRY_LINE])]:
        status, output, errors = run(runner)
        check(f"{label} is refused before gh pr ready, saying why and what to do",
              status == program.EXIT_MARK_READY_REFUSED_OR_FAILED and runner.calls == expected_calls
              and all(line in errors for line in expected_lines), (status, runner.calls, errors))

    # Failures of gh, git and python3, each reported with its cause and what to do.
    for label, runner, expected_lines in [
            ("gh pr view exits nonzero",
             FakeRunner(view=exits(4, "To get started with GitHub CLI, please run:  gh auth "
                                      "login\nmore")),
             ["reading pull request 77 failed: gh pr view exited with status 4: To get "
              "started with GitHub CLI, please run:  gh auth login.", RETRY_LINE]),
            ("gh pr view is killed by a signal", FakeRunner(view=exits(-9)),
             ["gh pr view exited with status -9, printing no error.", RETRY_LINE]),
            ("gh pr view exits nonzero printing nothing", FakeRunner(view=exits(1)),
             ["gh pr view exited with status 1, printing no error."]),
            ("gh cannot be run",
             FakeRunner(view=raises(FileNotFoundError(2, "No such file or directory", "gh"))),
             ["reading pull request 77 failed: gh could not be run (", RETRY_LINE]),
            ("gh pr view does not answer in time",
             FakeRunner(view=raises(subprocess.TimeoutExpired(["gh"], 60))),
             ["gh pr view did not answer within 60 seconds."]),
            ("gh pr view prints what is not JSON", FakeRunner(view=answers("not json")),
             ["gh pr view exited 0 but did not print a JSON object holding state, isDraft and "
              "headRefOid; it printed 'not json'.", RETRY_LINE]),
            ("gh pr view leaves out headRefOid",
             FakeRunner(view=answers(json.dumps({"state": "OPEN", "isDraft": True}))),
             ["did not print a JSON object holding state, isDraft and headRefOid; it printed "
              "'{\"state\": \"OPEN\", \"isDraft\": true}'."]),
            ("gh pr view prints a JSON list", FakeRunner(view=answers("[]")),
             ["did not print a JSON object holding state, isDraft and headRefOid; it printed "
              "'[]'."]),
            ("gh pr view prints more than the message shows",
             FakeRunner(view=answers("x" * 1000)),
             [f"it printed '{'x' * program.GH_PR_VIEW_NOT_JSON_OUTPUT_ERROR_EXCERPT_CHARACTERS}'."]),
            ("git rev-parse fails",
             FakeRunner(rev_parse=exits(128, "fatal: not a git repository")),
             ["reading this checkout's HEAD failed: git rev-parse --show-toplevel exited with "
              "status 128: fatal: not a git repository.",
              "If git's error says this is not a git repository: run this again from the pull "
              "request's own checkout.", "If git gave any other error: Run this command again "
              "once."]),
            ("git rev-parse prints one line, not the checkout and HEAD",
             FakeRunner(rev_parse=answers(HEAD + "\n")),
             ["reading this checkout's HEAD failed: git rev-parse --show-toplevel HEAD printed 1 "
              "lines, not 2.", RETRY_LINE]),
            ("python3 cannot run the test suites",
             FakeRunner(suites=raises(FileNotFoundError(2, "No such file", "python3"))),
             ["running the test suites failed: python3 could not be run (", RETRY_LINE]),
            ("gh pr ready fails",
             FakeRunner(ready=exits(1, "HTTP 502: Bad Gateway")),
             [f"marking #77 ({URL}) ready for review failed: gh pr ready exited with status "
              "1: HTTP 502: Bad Gateway.",
              "The test suites passed, but GitHub may or may not have marked it ready for "
              "review. Running this command again finds out", RETRY_LINE])]:
        status, output, errors = run(runner)
        check(f"when {label}, the program exits 1 and says what failed and what to do",
              status == program.EXIT_MARK_READY_REFUSED_OR_FAILED
              and all(line in errors for line in expected_lines), (status, errors))

    # The program as a command: a bad argument exits 2, before any gh call.
    command = subprocess.run([sys.executable, str(PROGRAM_PATH), "not-a-number"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                             timeout=60, check=False)
    check("run as a command with a pull request number that is not a number, it exits 2",
          command.returncode == 2 and "invalid int value" in command.stderr,
          (command.returncode, command.stderr))

    print()
    if failures:
        print(f"{len(failures)} case(s) failed")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
