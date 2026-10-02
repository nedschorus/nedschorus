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
        return CheckResult(
            "no verdict",
            reason="it had not finished when the %g-second budget ran out, and "
                   "was stopped" % budget)
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
        say(stderr, MESSAGE_PREFIX + "the conflict check did not run (%s is missing); "
            "the push goes ahead unchecked." % check_path)
        return EXIT_ALLOW_PUSH

    budget = time_budget_seconds(environment)
    deadline = time.monotonic() + budget
    conflicts = []
    for branch, local_object_id in branches:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            say(stderr, MESSAGE_PREFIX + "the conflict check did not run for branch %s "
                "(the %g-second budget was spent); the push goes ahead unchecked."
                % (branch, budget))
            continue
        result = run_conflict_check(check_path, local_object_id, remaining, budget)
        if result.kind == "conflict":
            conflicts.append((branch, result))
        elif result.kind == "no answer":
            say(stderr, MESSAGE_PREFIX + "the conflict check gave no answer for branch "
                "%s; the push goes ahead unchecked." % branch)
            for line in result.lines:
                say(stderr, line)
            say(stderr, "To get an answer, run scripts/%s --head %s from this checkout."
                % (CONFLICT_CHECK_FILE_NAME, local_object_id))
        elif result.kind == "no verdict":
            say(stderr, MESSAGE_PREFIX + "the conflict check gave no verdict for branch "
                "%s (%s); the push goes ahead unchecked." % (branch, result.reason))

    if not conflicts:
        return EXIT_ALLOW_PUSH
    for branch, result in conflicts:
        say(stderr, MESSAGE_PREFIX + "branch %s conflicts with %s; this push is refused."
            % (branch, BASE_NAME_FOR_MESSAGES))
        for line in result.lines:
            say(stderr, line)
    say(stderr, "Once the merge is committed, push again.")
    return EXIT_REFUSE_PUSH


if __name__ == "__main__":
    # Fail open on every exception so a broken check cannot block pushes.
    try:
        pushed = sys.stdin.buffer.read().decode("utf-8", "replace")
        exit_status = main(sys.argv[1:], pushed, sys.stderr, os.environ)
    except Exception as error:
        say(sys.stderr, MESSAGE_PREFIX + "the conflict check failed (%s: %s); the push "
            "goes ahead unchecked." % (type(error).__name__, error))
        exit_status = EXIT_ALLOW_PUSH
    sys.exit(exit_status)
