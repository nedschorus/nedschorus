#!/usr/bin/env python3
"""Run the selective test run on the checkout being pushed, and refuse the push when a suite fails.

Run by scripts/git-client-side-hooks/pre-push, with no arguments and nothing on stdin, only for a
push to origin of a branch other than main, after the conflict check has let the push through.
Exit 10 refuses the push; exit 0 lets it through. Any other exit makes the hook say the push went
without the selective test run and to tell the user.

The selective test run is scripts/run-all-test-suites.py with
--only-suites-whose-recorded-inputs-changed-since origin/main, run with the copy of that program
beside this file on the checkout git is pushing from, its top directory. It tests the checkout's
files, uncommitted changes included, not the pushed commit. A push made with GIT_DIR from a
directory outside the checkout gives that directory as the top, which the runner refuses, so
such a push goes ahead with the message for a run that could not start.

Only a suite's failure refuses the push. Every way the run can end without a verdict lets the push
through with a message saying how to run it by hand: another run holding the machine's test lock
past LOCK_WAIT_SECONDS, the run not finishing within the time budget, the run unable to start, and
this file failing. A wrong refusal stops an agent's work, and the pull request's head is tested
again before it merges.

The time budget, DEFAULT_TIME_BUDGET_SECONDS or the number of seconds in
TIME_BUDGET_ENVIRONMENT_VARIABLE, includes the wait for the lock. With the conflict check's
60 seconds before it, the hook ends within the 600 seconds a Claude Code agent can give one
command.
"""

import os
import re
import signal
import subprocess
import sys
from pathlib import Path

EXIT_ALLOW_PUSH = 0
EXIT_REFUSE_PUSH = 10

RUNNER_FILE_NAME = "run-all-test-suites.py"
RUNNER_EXIT_ALL_PASSED = 0
RUNNER_EXIT_SOME_FAILED = 1
RUNNER_EXIT_LOCKED = 3
BASE = "origin/main"
SELECTION_OPTION = "--only-suites-whose-recorded-inputs-changed-since"
LOCK_WAIT_OPTION = "--wait-for-lock-seconds"
LOCK_WAIT_SECONDS = 60
HAND_RUN_LOCK_WAIT_SECONDS = 600
HAND_RUN_COMMAND = "python3 scripts/%s %s %s %s %d" % (
    RUNNER_FILE_NAME, SELECTION_OPTION, BASE, LOCK_WAIT_OPTION, HAND_RUN_LOCK_WAIT_SECONDS)

DEFAULT_TIME_BUDGET_SECONDS = 480.0
TIME_BUDGET_ENVIRONMENT_VARIABLE = "NEDSCHORUS_PRE_PUSH_SELECTIVE_TEST_RUN_SECONDS"
TERMINATE_GRACE_SECONDS = 5.0

LOG_DIRECTORY_PATTERN = re.compile(r"; logs in (.+)$")
REPORT_FILE_NAME = "report.txt"
FAILED_SUITE_LINE_PREFIX = "FAIL "
FAILED_SUITE_LINE_LOG_MARK = " — log "
SUMMARY_LINE_PREFIX = "SUMMARY:"
LOCK_REFUSAL_LINE_PREFIX = "run-all-test-suites: not run"

MESSAGE_PREFIX = "pre-push: "
TELL_USER_LINE = ("Tell the user this whole message, including any error printed just "
                  "above it: the next push on this machine may go unchecked the same way.")


def say(stream, text):
    stream.write(text + "\n")
    stream.flush()


def time_budget_seconds(environment):
    try:
        seconds = float(environment.get(TIME_BUDGET_ENVIRONMENT_VARIABLE, ""))
    except ValueError:
        return DEFAULT_TIME_BUDGET_SECONDS
    return seconds if seconds > 0 else DEFAULT_TIME_BUDGET_SECONDS


def stop_process_group(process):
    """Stop the run and the suites it started; return its captured (stdout, stderr)."""
    # SIGTERM first, so the run can release its lock and finish its run record.
    for signal_number in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, signal_number)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            return process.communicate(timeout=TERMINATE_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            continue
    return "", ""


def checkout_top_directory():
    completed = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                               text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError("git rev-parse --show-toplevel failed: %s" % completed.stderr.strip())
    return completed.stdout.strip()


def last_line(text):
    return next((line.strip() for line in reversed(text.splitlines()) if line.strip()), "")


def lock_holder_line(stderr):
    """The runner's line naming the lock's holder; the lines after it advise its own caller."""
    return next((line.strip() for line in stderr.splitlines()
                 if line.startswith(LOCK_REFUSAL_LINE_PREFIX)), last_line(stderr))


def log_directory_named_in(stdout):
    return next((match.group(1) for match in map(LOG_DIRECTORY_PATTERN.search,
                                                  stdout.splitlines()) if match), None)


def say_not_run(stream, cause, tell_user):
    say(stream, MESSAGE_PREFIX + "%s, so this push goes ahead without the selective test run."
        % cause)
    say(stream, "Run it by hand from your worktree: %s" % HAND_RUN_COMMAND)
    say(stream, "If a suite fails, fix it, commit the fix and push again.")
    if tell_user:
        say(stream, TELL_USER_LINE)


def say_refusal(stream, stdout):
    lines = stdout.splitlines()
    summary = next((line for line in reversed(lines) if line.startswith(SUMMARY_LINE_PREFIX)), "")
    say(stream, MESSAGE_PREFIX + "a test suite failed in the selective test run, so this push "
        "is refused. %s" % summary)
    for line in lines:
        if line.startswith(FAILED_SUITE_LINE_PREFIX) and FAILED_SUITE_LINE_LOG_MARK in line:
            say(stream, line)
    log_directory = log_directory_named_in(stdout)
    if log_directory:
        say(stream, "The whole report: %s" % os.path.join(log_directory, REPORT_FILE_NAME))
    say(stream, "Fix what each failing suite's log shows, commit the fix and push again; the "
        "push runs the failing suites again.")
    say(stream, "If a failing suite's log shows the failure in code your change does not touch, "
        "push again once without changing anything, since some suites fail only when the "
        "machine is busy.")
    say(stream, "If it fails a second time, tell the user which suite fails and where its log is.")


def main(stream, environment):
    """Return EXIT_ALLOW_PUSH or EXIT_REFUSE_PUSH for one push."""
    runner = Path(__file__).resolve().with_name(RUNNER_FILE_NAME)
    if not runner.is_file():
        say_not_run(stream, "the selective test run did not start, because %s is missing"
                    % runner, tell_user=True)
        return EXIT_ALLOW_PUSH
    try:
        top = checkout_top_directory()
    except RuntimeError as error:
        say_not_run(stream, "the selective test run did not start, because %s" % error,
                    tell_user=True)
        return EXIT_ALLOW_PUSH

    budget = time_budget_seconds(environment)
    lock_wait = min(LOCK_WAIT_SECONDS, int(budget))
    say(stream, MESSAGE_PREFIX + "starting the selective test run on %s, which can take up to "
        "%d seconds. If your git push command times out before this hook finishes, run git "
        "push again with a timeout of 10 minutes." % (top, budget))
    try:
        process = subprocess.Popen(
            [sys.executable, str(runner), "--checkout", top, SELECTION_OPTION, BASE,
             LOCK_WAIT_OPTION, str(lock_wait)],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding="utf-8", errors="replace", start_new_session=True)
    except (OSError, ValueError) as error:
        say_not_run(stream, "the selective test run could not be started: %s" % error,
                    tell_user=True)
        return EXIT_ALLOW_PUSH
    try:
        stdout, stderr = process.communicate(timeout=budget)
    except subprocess.TimeoutExpired:
        stdout, _stderr = stop_process_group(process)
        log_directory = log_directory_named_in(stdout)
        cause = ("the selective test run had not finished when the %d-second time budget ran "
                 "out, and was stopped" % budget)
        if log_directory:
            cause += "; the logs of the suites it ran are in %s" % log_directory
        say_not_run(stream, cause, tell_user=False)
        return EXIT_ALLOW_PUSH

    status = process.returncode
    if status == RUNNER_EXIT_ALL_PASSED:
        summary = next((line for line in reversed(stdout.splitlines())
                        if line.startswith(SUMMARY_LINE_PREFIX)), "")
        say(stream, MESSAGE_PREFIX + "the selective test run passed. %s" % summary)
        return EXIT_ALLOW_PUSH
    if status == RUNNER_EXIT_SOME_FAILED:
        say_refusal(stream, stdout)
        return EXIT_REFUSE_PUSH
    if status == RUNNER_EXIT_LOCKED:
        say_not_run(stream, "another run of the test suites still held this machine's test "
                    "lock after %d seconds: %s" % (lock_wait, lock_holder_line(stderr)),
                    tell_user=False)
        return EXIT_ALLOW_PUSH
    if status < 0:
        reason = "it was killed by signal %d" % -status
    else:
        reason = "it exited %d" % status
    error_line = last_line(stderr)
    if error_line:
        reason = "%s: %s" % (reason, error_line)
    say_not_run(stream, "the selective test run gave no verdict, because %s" % reason,
                tell_user=True)
    return EXIT_ALLOW_PUSH


if __name__ == "__main__":
    # An uncaught exception exits 1, which the hook reports while letting the push through.
    sys.exit(main(sys.stderr, os.environ))
