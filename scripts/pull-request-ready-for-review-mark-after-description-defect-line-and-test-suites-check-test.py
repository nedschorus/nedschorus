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
import tempfile
from pathlib import Path

_removal_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).with_name("git-redirecting-environment-removal-test-fixture.py"))
_removal_module = importlib.util.module_from_spec(_removal_spec)
_removal_spec.loader.exec_module(_removal_module)
_removal_module.remove_git_redirecting_environment_variables_from_this_process()

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
OTHER = "b" * 40
BRANCH = "example-topic-branch"
CHECKOUT = "/work/pull-request-checkout"
URL = "https://github.com/example/example/pull/77"
GOOD_BODY = "Adds a command.\n\n#no_defect_fixed\n"


def completed(command, status=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(command, status, stdout, stderr)


def view_answer(**fields):
    pull_request = {"number": 77, "title": "Adds a command", "url": URL, "state": "OPEN",
                    "isDraft": True, "headRefOid": HEAD, "headRefName": BRANCH,
                    "body": GOOD_BODY}
    pull_request.update(fields)
    return json.dumps(pull_request)


def ancestors(*pairs):
    """git merge-base --is-ancestor answering yes for each (ancestor, descendant) pair given,
    and no for every other."""
    return lambda command: completed(command, 0 if tuple(command[3:5]) in pairs else 1)


class FakeRunner:
    """Answers gh pr view, git rev-parse HEAD, git branch --show-current, git rev-parse --verify, git
    merge-base --is-ancestor, git status, the test suite runner and gh pr ready; any of them can
    be replaced by a behaviour(command) that returns or raises. Records each call."""

    def __init__(self, view=None, rev_parse=None, status=None, suites=None, ready=None,
                 branch=None, has_commit=None, ancestor=None):
        self.behaviours = {
            "view": view or (lambda command: completed(command, 0, view_answer())),
            "rev-parse": rev_parse or (lambda command: completed(command, 0,
                                                                   f"{CHECKOUT}\n{HEAD}\n")),
            "branch": branch or (lambda command: completed(command, 0, BRANCH + "\n")),
            "has-commit": has_commit or (lambda command: completed(command, 0)),
            "ancestor": ancestor or ancestors(),
            "status": status or (lambda command: completed(command, 0, "")),
            "suites": suites or (lambda command: completed(command, 0)),
            "ready": ready or (lambda command: completed(command, 0)),
        }
        self.calls = []

    def __call__(self, command, **options):
        if command[:3] == ["gh", "pr", "view"]:
            kind = "view"
        elif command[:3] == ["git", "rev-parse", "--verify"]:
            kind = "has-commit"
        elif command[:2] == ["git", "rev-parse"]:
            kind = "rev-parse"
        elif command == ["git", "branch", "--show-current"]:
            kind = "branch"
        elif command[:3] == ["git", "merge-base", "--is-ancestor"]:
            kind = "ancestor"
        elif command == program.UNCOMMITTED_CHANGES_COMMAND:
            kind = "status"
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
          status == program.EXIT_MARKED_READY
          and runner.calls == ["view", "rev-parse", "status", "suites", "ready"]
          and f"#77 ({URL}) is marked ready for review." in output
          and "merge-lane-2" not in output + errors,
          (status, runner.calls, output, errors))
    check("the test suites run with the checkout's own runner, selecting the suites whose recorded "
          "inputs changed since origin/main",
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
          and "already ready for review, so it was left as it is." in output
          and "merge-lane-2" not in output + errors,
          (status, output, errors))

    # Refusals, each before gh pr ready.
    for label, runner, expected_calls, expected_lines in [
            ("a closed pull request", FakeRunner(view=answers(view_answer(state="CLOSED"))),
             ["view"], ["is closed, not open, so it cannot be marked ready for review.",
                        "If you meant another pull request: run this again with its number.",
                        "If you meant this one: do not reopen it yourself. "
                        "Tell the user, in one sentence, that it is closed and you meant to mark "
                        "it ready for review, and ask whether to reopen it;",
                        "If the answer is yes: run gh pr reopen 77, then run this again.",
                        "If the answer is no: leave it closed, and do not run this again for "
                        "it."]),
            ("a merged pull request", FakeRunner(view=answers(view_answer(state="MERGED"))),
             ["view"], ["is merged, not open, so it cannot be marked ready for review.",
                        "If you meant this one: its review is over, so there "
                        "is nothing to mark."]),
            ("a pull request in a state gh did not report before",
             FakeRunner(view=answers(view_answer(state="LOCKED"))),
             ["view"], ["is locked, not open, so it cannot be marked ready for review.",
                        "If you meant this one: tell the user, in one sentence, that gh reports "
                        "its state as 'locked';"]),
            ("a checkout on another branch than the pull request's",
             FakeRunner(rev_parse=answers(f"{CHECKOUT}\n{OTHER}\n"),
                        branch=answers("some-other-branch\n")),
             ["view", "rev-parse", "branch"],
             [f"this checkout's HEAD, {'b' * 12}, is not #77 ({URL})'s pushed nc-head-commit, "
              f"{'a' * 12}", f"This checkout is on branch some-other-branch, not the pull "
              f"request's branch {BRANCH}: run this again from the checkout that has {BRANCH} "
              "checked out; git worktree list names each checkout of this clone with its "
              f"branch. If no checkout has it, make one with python3 "
              f"scripts/agent-seat-worktree-create-with-owner-file.py {BRANCH}, which prints its "
              "path, and run this again there."]),
            ("a checkout on a detached HEAD",
             FakeRunner(rev_parse=answers(f"{CHECKOUT}\n{OTHER}\n"), branch=answers("\n")),
             ["view", "rev-parse", "branch"],
             [f"This checkout is on a detached HEAD, not the pull request's branch {BRANCH}"]),
            ("a checkout that has not fetched the pushed head",
             FakeRunner(rev_parse=answers(f"{CHECKOUT}\n{OTHER}\n"),
                        has_commit=exits(1)),
             ["view", "rev-parse", "branch", "has-commit"],
             [f"This checkout does not have the pushed commit yet: run git fetch origin {BRANCH}, "
              "then run this again, and it names what to do next."]),
            ("a checkout with commits the pull request lacks",
             FakeRunner(rev_parse=answers(f"{CHECKOUT}\n{OTHER}\n"),
                        ancestor=ancestors((HEAD, OTHER))),
             ["view", "rev-parse", "branch", "has-commit", "ancestor"],
             [f"This checkout has commits the pull request lacks: push them with git push origin "
              f"HEAD:{BRANCH}, then run this again."]),
            ("a checkout behind the pull request",
             FakeRunner(rev_parse=answers(f"{CHECKOUT}\n{OTHER}\n"),
                        ancestor=ancestors((OTHER, HEAD))),
             ["view", "rev-parse", "branch", "has-commit", "ancestor", "ancestor"],
             [f"The pull request has commits this checkout lacks: run git pull --ff-only origin "
              f"{BRANCH}, then run this again."]),
            ("a checkout and pull request that each have commits the other lacks",
             FakeRunner(rev_parse=answers(f"{CHECKOUT}\n{OTHER}\n")),
             ["view", "rev-parse", "branch", "has-commit", "ancestor", "ancestor"],
             [f"This checkout and the pull request each have commits the other lacks: run git "
              f"pull --no-rebase origin {BRANCH}, which merges the pull request's commits into "
              f"this checkout, then git push origin HEAD:{BRANCH}, then run this again.",
              "If git reports a merge conflict: stop, run git merge --abort, and tell the user, "
              "or the agent that dispatched you, which files conflict."]),
            ("a checkout with an uncommitted change to a tracked file",
             FakeRunner(status=answers(" M scripts/example.py\n")),
             ["view", "rev-parse", "status"],
             ["this checkout has 1 uncommitted change(s), so the test suites would test files "
              f"that are not in #77 ({URL})'s pushed commits.",
              "The changes, as git status --porcelain lists them:\n  M scripts/example.py\n",
              "If the changes belong in the pull request: commit them, run the test suites and "
              "the mutation pass that CLAUDE.md asks for before a push, push with git push origin "
              f"HEAD:{BRANCH}, then run this again.",
              "If they do not: set them aside with git stash push -u -m <a name no entry in git "
              "stash list has>, then run this again. Keep them stashed until this command has "
              "marked the pull request ready, even if it refuses again for another reason; then "
              "bring them back: find your entry's commit, the "
              "first word of the line that ends with the name you gave with -m, with git stash list "
              "--format='%H %gs', and run git stash apply <that commit>.",
              "If the apply reports a conflict: keep the stash entry, and tell the user, or the "
              "agent that dispatched you, which files conflict.",
              "If the apply succeeds: find the entry's current stash@{<n>} on the line that "
              "ends with the name you gave with -m, with git stash list, and drop it with git stash drop "
              "stash@{<n>}."]),
            ("a checkout with an uncommitted change, on a branch whose name the shell would "
             "split",
             FakeRunner(view=answers(view_answer(headRefName="odd;branch")),
                        status=answers(" M scripts/example.py\n")),
             ["view", "rev-parse", "status"],
             ["push with git push origin HEAD:'odd;branch', then run this again."]),
            ("a pushed commit whose object fails its hash check, which git rev-parse --verify "
             "reports with exit 1 and an error",
             FakeRunner(rev_parse=answers(f"{CHECKOUT}\n{OTHER}\n"),
                        has_commit=exits(1, "error: hash mismatch " + HEAD)),
             ["view", "rev-parse", "branch", "has-commit"],
             ["looking for the pushed nc-head-commit in this checkout failed: git rev-parse "
              f"--verify exited with status 1: error: hash mismatch {HEAD}."]),
            ("a checkout with untracked files that are not ignored",
             FakeRunner(status=answers("?? notes.txt\n?? more.txt\n")),
             ["view", "rev-parse", "status"],
             ["this checkout has 2 uncommitted change(s)",
              "lists them:\n  ?? notes.txt\n  ?? more.txt\n"]),
            ("a placeholder description with no defect line",
             FakeRunner(view=answers(view_answer(body="Work in progress.\n"))),
             ["view", "rev-parse", "status"],
             ["description has no line beginning \"#root_cause\"",
              "Write the current description to a file outside this repository, such as a file "
              "in your scratchpad, with gh pr view 77 --json body -q .body > <file>.",
              "or, when the cause stays or was not found, \"#root_cause_not_fixed <the cause "
              "that stays, or that it was not found, and why> #follow_up <full https://github.com/ "
              "link to the issue or pull request that will fix it or look for it>\"; when "
              "neither exists yet, file an issue with the /ghi-write skill first.",
              "Put each such line on a line of its own, anywhere in the description, such as "
              "at its end. Replace any placeholder text with what the pull request changes,",
              "Then upload the file with gh pr edit 77 --body-file <file>, which replaces the "
              "whole description"]),
            ("an empty description", FakeRunner(view=answers(view_answer(body=None))),
             ["view", "rev-parse", "status"],
             ["description has no line beginning \"#root_cause\""]),
            ("a failing test suite", FakeRunner(suites=exits(1)),
             ["view", "rev-parse", "status", "suites"],
             ["the test suites exited with status 1, so #77",
              "The failing suites are named above.",
              "Fix the cause of each suite's failure and commit the fix. Before you push it, "
              "run the mutation pass that CLAUDE.md asks for before a push; then push, and run "
              "this again, which runs the test suites again.",
              "If git or a pre-push hook refuses the push: do what its message says, push again, "
              "then run this again; if it names nothing to do, tell the user, or the agent that "
              "dispatched you, what it printed."]),
            ("a test suite runner that stops before judging every suite",
             FakeRunner(suites=exits(2)), ["view", "rev-parse", "status", "suites"],
             ["scripts/run-all-test-suites.py exited with status 2, before judging every suite, "
              "so #77",
              "Its error is above.", RETRY_LINE])]:
        status, output, errors = run(runner)
        check(f"{label} is refused before gh pr ready, saying why and what to do",
              status == program.EXIT_MARK_READY_REFUSED_OR_FAILED and runner.calls == expected_calls
              and all(line in errors for line in expected_lines), (status, runner.calls, errors))

    # Only the lines for the pull request's actual state are printed.
    _, _, errors = run(FakeRunner(view=answers(view_answer(state="MERGED"))))
    check("a merged pull request's refusal leaves out what to do with a closed one",
          "reopen" not in errors and "If the answer is" not in errors, errors)
    _, _, errors = run(FakeRunner(view=answers(view_answer(state="CLOSED"))))
    check("a closed pull request's refusal leaves out what to do with a merged one",
          "review is over" not in errors, errors)
    _, _, errors = run(FakeRunner(rev_parse=answers(f"{CHECKOUT}\n{OTHER}\n"),
                                  ancestor=ancestors((HEAD, OTHER))))
    check("a checkout ahead of the pull request is told only how to push",
          "git pull" not in errors and "git fetch" not in errors
          and "not the pull request's branch" not in errors, errors)
    _, _, errors = run(FakeRunner(rev_parse=answers(f"{CHECKOUT}\n{OTHER}\n"),
                                  has_commit=exits(1, "error: hash mismatch " + HEAD)))
    check("a pushed commit that git reports as corrupt is not read as one to fetch",
          "git fetch" not in errors, errors)
    runner = FakeRunner(rev_parse=answers(f"{CHECKOUT}\n{OTHER}\n"),
                        has_commit=lambda command: completed(command, 0, "",
                                                             "warning: refname is ambiguous"))
    _, _, errors = run(runner)
    check("a yes from git that also prints a warning is still a yes",
          runner.calls == ["view", "rev-parse", "branch", "has-commit", "ancestor", "ancestor"]
          and "failed" not in errors, (runner.calls, errors))

    # A branch name the shell would split or expand is quoted in each command printed.
    odd = "it's-a-topic-branch"
    for label, runner, expected in [
            ("not fetched", FakeRunner(view=answers(view_answer(headRefName=odd)),
                                       rev_parse=answers(f"{CHECKOUT}\n{OTHER}\n"),
                                       branch=answers(odd + "\n"), has_commit=exits(1)),
             "git fetch origin 'it'\"'\"'s-a-topic-branch',"),
            ("ahead", FakeRunner(view=answers(view_answer(headRefName=odd)),
                                 rev_parse=answers(f"{CHECKOUT}\n{OTHER}\n"),
                                 branch=answers(odd + "\n"), ancestor=ancestors((HEAD, OTHER))),
             "git push origin HEAD:'it'\"'\"'s-a-topic-branch',"),
            ("behind", FakeRunner(view=answers(view_answer(headRefName=odd)),
                                  rev_parse=answers(f"{CHECKOUT}\n{OTHER}\n"),
                                  branch=answers(odd + "\n"), ancestor=ancestors((OTHER, HEAD))),
             "git pull --ff-only origin 'it'\"'\"'s-a-topic-branch',"),
            ("diverged", FakeRunner(view=answers(view_answer(headRefName=odd)),
                                    rev_parse=answers(f"{CHECKOUT}\n{OTHER}\n"),
                                    branch=answers(odd + "\n")),
             "git pull --no-rebase origin 'it'\"'\"'s-a-topic-branch', which")]:
        _, _, errors = run(runner)
        check(f"a branch name holding a quote is shell-quoted in the {label} command",
              expected in errors, errors)

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
             ["gh pr view exited 0 but did not print a JSON object holding state, isDraft, "
              "headRefOid and headRefName; it printed 'not json'.", RETRY_LINE]),
            ("gh pr view leaves out headRefOid",
             FakeRunner(view=answers(json.dumps({"state": "OPEN", "isDraft": True,
                                                 "headRefName": BRANCH}))),
             ["did not print a JSON object holding state, isDraft, headRefOid and headRefName; "
              "it printed '{\"state\": \"OPEN\", \"isDraft\": true, \"headRefName\": "
              f"\"{BRANCH}\"}}'."]),
            ("gh pr view leaves out headRefName",
             FakeRunner(view=answers(json.dumps({"state": "OPEN", "isDraft": True,
                                                 "headRefOid": HEAD}))),
             ["did not print a JSON object holding state, isDraft, headRefOid and headRefName"]),
            ("gh pr view prints a JSON list", FakeRunner(view=answers("[]")),
             ["did not print a JSON object holding state, isDraft, headRefOid and headRefName; "
              "it printed '[]'."]),
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
            ("git status fails",
             FakeRunner(status=exits(128, "fatal: index file corrupt")),
             ["reading this checkout's uncommitted changes failed: git status --porcelain "
              "exited with status 128: fatal: index file corrupt.",
              "If git gave any other error: Run this command again once."]),
            ("git branch --show-current fails",
             FakeRunner(rev_parse=answers(f"{CHECKOUT}\n{OTHER}\n"),
                        branch=exits(129, "error: unknown option")),
             ["reading this checkout's branch failed: git branch --show-current exited with "
              "status 129: error: unknown option.", "If git gave any other error: Run this "
              "command again once."]),
            ("the pushed commit is in the clone but cannot be read",
             FakeRunner(rev_parse=answers(f"{CHECKOUT}\n{OTHER}\n"),
                        has_commit=exits(128, "error: inflate: data stream error")),
             ["looking for the pushed nc-head-commit in this checkout failed: git rev-parse "
              "--verify exited with status 128: error: inflate: data stream error.",
              "If git gave any other error: Run this command again once."]),
            ("git merge-base fails",
             FakeRunner(rev_parse=answers(f"{CHECKOUT}\n{OTHER}\n"),
                        ancestor=exits(128, "fatal: Not a valid commit name")),
             ["comparing this checkout's HEAD with the pushed nc-head-commit failed: git "
              "merge-base --is-ancestor exited with status 128: fatal: Not a valid commit name.",
              "If git gave any other error: Run this command again once."]),
            ("git merge-base is killed by a signal",
             FakeRunner(rev_parse=answers(f"{CHECKOUT}\n{OTHER}\n"), ancestor=exits(-9)),
             ["comparing this checkout's HEAD with the pushed nc-head-commit failed: git "
              "merge-base --is-ancestor exited with status -9, printing no error."]),
            ("git merge-base cannot be run",
             FakeRunner(rev_parse=answers(f"{CHECKOUT}\n{OTHER}\n"),
                        ancestor=raises(FileNotFoundError(2, "No such file", "git"))),
             ["comparing this checkout's HEAD with the pushed nc-head-commit failed: git could "
              "not be run ("]),
            ("git merge-base does not answer in time",
             FakeRunner(rev_parse=answers(f"{CHECKOUT}\n{OTHER}\n"),
                        ancestor=raises(subprocess.TimeoutExpired(["git"], 30))),
             ["git merge-base --is-ancestor did not answer within 30 seconds."]),
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

    # The uncommitted-changes command with real git: an untracked file is listed even when the
    # clone's settings hide untracked files from git status.
    with tempfile.TemporaryDirectory() as clone:
        for setup in (["git", "init", "-q", clone],
                      ["git", "-C", clone, "config", "status.showUntrackedFiles", "no"]):
            subprocess.run(setup, check=True, timeout=60)
        Path(clone, "notes.txt").write_text("not committed\n")
        hidden = subprocess.run(["git", "status", "--porcelain"], cwd=clone, text=True,
                                stdout=subprocess.PIPE, check=True, timeout=60).stdout
        listed = subprocess.run(program.UNCOMMITTED_CHANGES_COMMAND, cwd=clone, text=True,
                                stdout=subprocess.PIPE, check=True, timeout=60).stdout
    check("with status.showUntrackedFiles=no, the program's git status still lists an "
          "untracked file, which plain git status --porcelain hides",
          hidden == "" and "?? notes.txt" in listed, (hidden, listed))

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
