#!/usr/bin/env python3
"""Refuse pushes to origin branches only when the conflict check gives a trustworthy conflict."""
# Fail open: a missed conflict is caught in review, but a wrongly blocked push stops work.
# Keep Git’s environment so the check sees the repository actually being pushed.

import os
import signal
import subprocess
import sys
import time

EXIT_ALLOW_PUSH = 0
EXIT_REFUSE_PUSH = 10

CHECKED_REMOTE_NAME = "origin"
BRANCH_REF_PREFIX = "refs/heads/"
UNCHECKED_BRANCH_REF = "refs/heads/main"
BASE_NAME_FOR_MESSAGES = "origin/main"

CONFLICT_CHECK_FILE_NAME = "branch-conflict-check.py"
CHECK_EXIT_CLEAN = 0
CHECK_EXIT_CONFLICT = 1
CHECK_EXIT_NO_ANSWER = 2
CONFLICT_VERDICT_PREFIX = "VERDICT: CONFLICT"

DEFAULT_TIME_BUDGET_SECONDS = 60.0
TIME_BUDGET_ENVIRONMENT_VARIABLE = "NEDSCHORUS_PRE_PUSH_CONFLICT_CHECK_SECONDS"
TERMINATE_GRACE_SECONDS = 3.0

MESSAGE_PREFIX = "pre-push: "
SHORT_COMMIT_LENGTH = 12
HAND_CHECK_COMMAND = "python3 scripts/%s --head %%s" % CONFLICT_CHECK_FILE_NAME
TELL_USER_LINE = ("Tell the user this whole message, including any error printed just "
                  "above it: the next push on this machine may go unchecked the same way.")


def branches_to_check(pushed_refs_text):
    """Return (branch name, local object ID) for each eligible pushed ref."""
    branches = []
    for line in pushed_refs_text.splitlines():
        fields = line.split()
        if len(fields) != 4:
            continue
        _local_ref, local_object_id, remote_ref, _remote_object_id = fields
        if set(local_object_id) == {"0"}:
            continue
        if not remote_ref.startswith(BRANCH_REF_PREFIX):
            continue
        if remote_ref == UNCHECKED_BRANCH_REF:
            continue
        branches.append((remote_ref[len(BRANCH_REF_PREFIX):], local_object_id))
    return branches


def time_budget_seconds(environment):
    configured = environment.get(TIME_BUDGET_ENVIRONMENT_VARIABLE, "")
    try:
        seconds = float(configured)
    except ValueError:
        return DEFAULT_TIME_BUDGET_SECONDS
    if seconds > 0:
        return seconds
    return DEFAULT_TIME_BUDGET_SECONDS


def signal_process_group(process, signal_number):
    # Include the fetch child, which would otherwise keep the output pipe open.
    try:
        os.killpg(process.pid, signal_number)
    except (ProcessLookupError, PermissionError):
        pass


def stop_process_group(process):
    """Return captured (stdout, stderr) after stopping the process group."""
    # SIGTERM lets git remove lock files; immediate SIGKILL can leave stale locks.
    for signal_number in (signal.SIGTERM, signal.SIGKILL):
        signal_process_group(process, signal_number)
        try:
            return process.communicate(timeout=TERMINATE_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            continue
    for pipe in (process.stdout, process.stderr):
        try:
            pipe.close()
        except OSError:
            pass
    return "", ""


class CheckResult:
    """A verdict with stdout lines and a reason when no verdict is available."""

    def __init__(self, kind, lines=(), reason=""):
        self.kind = kind
        self.lines = list(lines)
        self.reason = reason


def run_conflict_check(check_path, local_object_id, seconds_left, budget):
    try:
        process = subprocess.Popen(
            [sys.executable, check_path, "--head", local_object_id],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8",
            errors="replace", start_new_session=True)
    except (OSError, ValueError) as error:
        return CheckResult("no verdict", reason="it could not be started: %s" % error)
    try:
        stdout, stderr = process.communicate(timeout=seconds_left)
    except subprocess.TimeoutExpired:
        stop_process_group(process)
        return CheckResult("timed out")
    lines = stdout.splitlines()
    status = process.returncode
    has_conflict_verdict = any(line.startswith(CONFLICT_VERDICT_PREFIX) for line in lines)
    if status == CHECK_EXIT_CONFLICT and has_conflict_verdict:
        return CheckResult("conflict", lines)
    if status == CHECK_EXIT_CLEAN:
        return CheckResult("clean", lines)
    if status == CHECK_EXIT_NO_ANSWER:
        return CheckResult("no answer", lines)
    if status is not None and status < 0:
        reason = "it was killed by signal %d" % -status
    elif status == CHECK_EXIT_CONFLICT:
        reason = "it exited 1 without a %s line" % CONFLICT_VERDICT_PREFIX
    else:
        reason = "it exited %s" % status
    last_error_line = next(
        (line.strip() for line in reversed(stderr.splitlines()) if line.strip()), "")
    if last_error_line:
        reason = "%s: %s" % (reason, last_error_line)
    return CheckResult("no verdict", reason=reason)


def say(stream, text):
    stream.write(text + "\n")


def short_commit(object_id):
    return object_id[:SHORT_COMMIT_LENGTH]


def branch_list(branches):
    """The `{branches}` fill: each branch with its commit, separated by commas."""
    return ", ".join("%s (%s)" % (branch, short_commit(object_id))
                     for branch, object_id in branches)


def hand_check_line(branch, object_id):
    return "Check %s by hand from your worktree: %s" % (
        branch, HAND_CHECK_COMMAND % short_commit(object_id))


def unchecked_lines(branches):
    """The `{unchecked_lines}` fill: one hand-check line per branch."""
    return [hand_check_line(branch, object_id) for branch, object_id in branches]


def say_no_branch_checked(stream, cause, branches):
    say(stream, MESSAGE_PREFIX + "%s, so no branch in this push was checked for "
        "conflicts with %s: %s." % (cause, BASE_NAME_FOR_MESSAGES, branch_list(branches)))
    for line in unchecked_lines(branches):
        say(stream, line)
    say(stream, TELL_USER_LINE)


def say_error_before_branches_read(stream, error_text):
    say(stream, MESSAGE_PREFIX + "the pre-push conflict check failed with %s before "
        "reading which branches this push sends, so no branch in this push was checked "
        "for conflicts with %s." % (error_text, BASE_NAME_FOR_MESSAGES))
    say(stream, "For each branch this push sends to %s, other than main, run from your "
        "worktree: %s" % (CHECKED_REMOTE_NAME, HAND_CHECK_COMMAND % "<branch name>"))
    say(stream, TELL_USER_LINE)


def main(argv, pushed_refs_text, stderr, environment):
    """Return EXIT_ALLOW_PUSH or EXIT_REFUSE_PUSH for one push."""
    remote_name = argv[0] if argv else ""
    if remote_name != CHECKED_REMOTE_NAME:
        return EXIT_ALLOW_PUSH
    branches = branches_to_check(pushed_refs_text)
    if not branches:
        return EXIT_ALLOW_PUSH

    check_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), CONFLICT_CHECK_FILE_NAME)
    if not os.path.isfile(check_path):
        say_no_branch_checked(
            stderr, "the pre-push conflict check did not run, because %s is missing"
            % check_path, branches)
        return EXIT_ALLOW_PUSH

    budget = time_budget_seconds(environment)
    deadline = time.monotonic() + budget
    conflicts = []
    for branch, local_object_id in branches:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            say(stderr, MESSAGE_PREFIX + "branch %s was not checked for conflicts with "
                "%s, because the earlier branches in this push used up the %g-second "
                "time budget." % (branch, BASE_NAME_FOR_MESSAGES, budget))
            say(stderr, hand_check_line(branch, local_object_id))
            continue
        result = run_conflict_check(check_path, local_object_id, remaining, budget)
        if result.kind == "conflict":
            conflicts.append((branch, result))
        elif result.kind == "no answer":
            say(stderr, MESSAGE_PREFIX + "branch %s was not checked for conflicts with "
                "%s, because scripts/%s could not decide; its report follows."
                % (branch, BASE_NAME_FOR_MESSAGES, CONFLICT_CHECK_FILE_NAME))
            for line in result.lines:
                say(stderr, line)
            say(stderr, "Follow the report, then check %s again by hand from your "
                "worktree: %s" % (branch, HAND_CHECK_COMMAND % short_commit(local_object_id)))
            say(stderr, "If that run also prints no VERDICT line, tell the user this "
                "whole message and what that run printed.")
        elif result.kind == "timed out":
            say(stderr, MESSAGE_PREFIX + "branch %s was not checked for conflicts with "
                "%s, because scripts/%s had not finished when the %g-second time budget "
                "ran out, and was stopped."
                % (branch, BASE_NAME_FOR_MESSAGES, CONFLICT_CHECK_FILE_NAME, budget))
            say(stderr, hand_check_line(branch, local_object_id))
            say(stderr, "If that run also prints no VERDICT line, tell the user this "
                "whole message and what that run printed.")
        elif result.kind == "no verdict":
            say(stderr, MESSAGE_PREFIX + "branch %s was not checked for conflicts with "
                "%s, because scripts/%s gave no verdict: %s."
                % (branch, BASE_NAME_FOR_MESSAGES, CONFLICT_CHECK_FILE_NAME, result.reason))
            say(stderr, hand_check_line(branch, local_object_id))
            say(stderr, TELL_USER_LINE)

    if not conflicts:
        return EXIT_ALLOW_PUSH
    for branch, result in conflicts:
        say(stderr, MESSAGE_PREFIX + "branch %s conflicts with %s; this push is refused."
            % (branch, BASE_NAME_FOR_MESSAGES))
        for line in result.lines:
            say(stderr, line)
    say(stderr, "Once the merge is committed, push again.")
    return EXIT_REFUSE_PUSH


def report_unexpected_error(stream, error, argv, pushed_refs_text):
    """Message 7: name the unchecked branches when the pushed refs were read.

    Prints nothing when the refs were read and hold no branch the check would
    check, since no check was skipped."""
    error_text = "%s: %s" % (type(error).__name__, error)
    branches = None
    if pushed_refs_text is not None:
        try:
            remote_name = argv[0] if argv else ""
            branches = (branches_to_check(pushed_refs_text)
                        if remote_name == CHECKED_REMOTE_NAME else [])
        except Exception:
            branches = None
    if branches:
        say_no_branch_checked(
            stream, "the pre-push conflict check failed with %s" % error_text, branches)
    elif branches is None:
        say_error_before_branches_read(stream, error_text)


if __name__ == "__main__":
    # Fail open on every exception so a broken check cannot block pushes.
    pushed = None
    try:
        pushed = sys.stdin.buffer.read().decode("utf-8", "replace")
        exit_status = main(sys.argv[1:], pushed, sys.stderr, os.environ)
    except Exception as error:
        report_unexpected_error(sys.stderr, error, sys.argv[1:], pushed)
        exit_status = EXIT_ALLOW_PUSH
    sys.exit(exit_status)
