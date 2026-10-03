#!/usr/bin/env python3
"""Run affected suites at a pull request head and append a test record per machine and commit.

The checkout must match the recorded head before testing, at runner startup, and after testing;
a change made and reverted during the suites remains undetectable.

A writer killed during a partial append can leave a torn record that prevents subsequent records from being read.

Exit codes: 0 suites passed, 1 suite failed, 2 refused or unable to start, 4 failed step,
5 record not written, 7 uncaught exception. Local logs and the record remain available for recovery."""

import argparse
import importlib.util
import locale
import os
import shlex
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

PROGRAM = "pull-request-head-test-run"

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent

EXIT_STOPPED_BY_AN_UNCAUGHT_EXCEPTION = 7


def exit_code_after_reporting_the_uncaught_exception() -> int:
    """Report the active exception and return an exit code distinct from a failed suite."""
    traceback.print_exc()
    print(f"{PROGRAM}: not finished — the error above stopped this program, and this run "
          f"gives no verdict.\n"
          f"Tell the user what the error above says.", file=sys.stderr)
    return EXIT_STOPPED_BY_AN_UNCAUGHT_EXCEPTION


def module_loaded_by_path(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


try:
    daily_full_test_run_of_main = module_loaded_by_path(
        "daily_full_test_run_of_main",
        Path(__file__).resolve().with_name("daily-full-test-run-of-main.py"))
    daily_memory_review_mark = daily_full_test_run_of_main.daily_memory_review_mark
    run_all_test_suites = daily_full_test_run_of_main.run_all_test_suites
    EXIT_CHECKOUT_REFUSED = run_all_test_suites.EXIT_COULD_NOT_RUN
except Exception:
    if __name__ != "__main__":
        raise
    sys.exit(exit_code_after_reporting_the_uncaught_exception())

PULL_REQUEST_HEAD_TEST_RUNS_KIND_DIRECTORY_NAME = "pull-request-head-test-runs"

PULL_REQUEST_HEAD_TEST_RUN_DIRECTORY_NAME = "nedschorus-pull-request-head-test-run"
PULL_REQUEST_HEAD_TEST_RUN_LOGS_DIRECTORY_NAME = "logs"
PULL_REQUEST_HEAD_TEST_RUN_RECORD_LOCAL_COPY_FILE_NAME = "pull-request-head-test-run-record.txt"

# Use the runner beside this program so a pull request cannot pass itself by modifying its runner.
PULL_REQUEST_HEAD_TEST_RUN_RUNNER_BESIDE_THIS_FILE = Path(__file__).resolve().with_name(
    "run-all-test-suites.py")

MAIN_AS_THE_CLONE_HAS_IT = "refs/remotes/origin/main"

# Must match the runner's commit_and_state wording.
RUNNER_STATE_WHEN_TRACKED_FILES_MATCH = "tracked files match that commit"

# Keep this one-line command ASCII and free of single quotes so the recovery command remains shell-copyable.
# Check byte length before locking: interrupted ssh input otherwise looks like a complete record.
PULL_REQUEST_HEAD_TEST_LOG_APPEND_PROGRAM = "; ".join((
    "import fcntl, os, sys",
    f'sys.excepthook = lambda kind, error, trace: sys.stderr.write("{PROGRAM}: not written: '
    f'%s: %s\\n" % (kind.__name__, error))',
    "test_log, bytes_sent = sys.argv[1], int(sys.argv[2])",
    "record = sys.stdin.buffer.read()",
    f'len(record) == bytes_sent or sys.exit("{PROGRAM}: not written: %d bytes of the record '
    f'were sent and another count arrived.\\nRun this command again." % bytes_sent)',
    "os.makedirs(os.path.dirname(test_log), exist_ok=True)",
    "log = os.open(test_log, os.O_RDWR | os.O_APPEND | os.O_CREAT, 0o666)",
    "fcntl.flock(log, fcntl.LOCK_EX)",
    "length = os.fstat(log).st_size",
    "there = os.pread(log, length, 0)",
    f'(there.startswith(record) or b"\\n" + record in there) and (print("{PROGRAM}: already '
    f'written: the test log there holds the whole record of this run, byte for byte.\\nTell '
    f'the user the record is written."), sys.exit())',
    f'os.write(log, record) == bytes_sent or (os.ftruncate(log, length), sys.exit("{PROGRAM}: '
    f'not written: the test log took part of the record and is cut back to what it held.'
    f'\\nRun this command again."))',
))


def commit_named_for_the_record(checkout: Path, commit: str) -> str:
    """Format a commit hash and subject, falling back to the hash when unavailable."""
    subject = daily_full_test_run_of_main.git(checkout, "log", "-1", "--format=%s", commit)
    if subject.returncode != 0:
        return f"commit {commit}"
    return f'commit {commit} ("{subject.stdout.strip()}")'


def runner_named_for_the_record(runner: Path) -> str:
    resolved = daily_full_test_run_of_main.git(
        runner.parent, "rev-parse", "--verify", "--quiet", "HEAD^{commit}")
    if resolved.returncode != 0 or not resolved.stdout.strip():
        return f"{runner}, in no git checkout"
    return f"{runner}, from {commit_named_for_the_record(runner.parent, resolved.stdout.strip())}"


def first_tracked_file_that_differs(checkout: Path):
    """Return (first differing tracked file or None, git status failure or None)."""
    changed = daily_full_test_run_of_main.git(
        checkout, "status", "--porcelain", "--untracked-files=no")
    if changed.returncode != 0:
        return None, daily_full_test_run_of_main.first_stderr_line_or_no_detail(
            changed.stderr)
    if changed.stdout.strip():
        return changed.stdout.splitlines()[0][3:], None
    return None, None


def why_the_run_is_no_verdict_on_the_head(checkout: Path, head: str, completed) -> list:
    """Return reasons the completed run cannot count as a verdict on the head."""
    # The runner banner catches changes during lock waiting; the final check catches changes during testing.
    reasons = []
    first_line = (completed.stdout.splitlines() or [""])[0]
    if not (first_line.startswith(f"{run_all_test_suites.PROGRAM}: ")
            and f" at {head} ({RUNNER_STATE_WHEN_TRACKED_FILES_MATCH}); " in first_line):
        reasons.append(f"the runner's first line does not say it tested {head} with "
                       f"tracked files matching that commit")
    resolved = daily_full_test_run_of_main.git(
        checkout, "rev-parse", "--verify", "--quiet", "HEAD^{commit}")
    head_after_the_run = resolved.stdout.strip()
    if resolved.returncode != 0 or not head_after_the_run:
        reasons.append(f"after the run git cannot resolve HEAD to a commit in {checkout}")
    elif head_after_the_run != head:
        reasons.append(f"after the run HEAD of {checkout} is "
                       f"{commit_named_for_the_record(checkout, head_after_the_run)}")
    differing, why_status_failed = first_tracked_file_that_differs(checkout)
    if why_status_failed is not None:
        reasons.append(f"after the run git status failed in {checkout}: {why_status_failed}")
    elif differing is not None:
        reasons.append(f"after the run a tracked file in {checkout} differs from its "
                       f"commit: {differing}")
    return reasons


def write_record_command(log_store_root: str, machine: str, file_name: str,
                         bytes_sent: int) -> str:
    """Build an idempotent append command for the record supplied on stdin."""
    # exec makes the timeout kill the lock holder; keep the command ASCII for filesystem encoding.
    test_log = (f"{log_store_root}/{PULL_REQUEST_HEAD_TEST_RUNS_KIND_DIRECTORY_NAME}/"
                f"{machine}/{file_name}")
    return (f"exec python3 -c {shlex.quote(PULL_REQUEST_HEAD_TEST_LOG_APPEND_PROGRAM)} "
            f"{shlex.quote(test_log)} {int(bytes_sent)}")


def bytes_of_text_sent_to_a_command(text: str) -> int:
    """Return the byte count subprocess text mode will send."""
    # Match the locale encoding used by subprocess.run(text=True) without an explicit encoding.
    return len(text.encode(locale.getpreferredencoding(False)))


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        prog=PROGRAM,
        description="Run the test suites a pull request's head reaches and file the test "
                    "log in the log-store under the head's commit hash.")
    parser.add_argument("--checkout", default=str(REPOSITORY_ROOT))
    parser.add_argument("--since", metavar="COMMIT")
    parser.add_argument(
        "--log-store-root",
        default=daily_full_test_run_of_main.DAILY_FULL_TEST_RUN_DEFAULT_LOG_STORE_ROOT)
    parser.add_argument("--test-suite-runner-program")
    parser.add_argument("--temporary-directory")
    parser.add_argument("--recorded-inputs-directory")
    return parser.parse_args(argv)


def main(argv=None, now=None, wait=time.sleep, monotonic=time.monotonic) -> int:
    arguments = parse_arguments(argv)
    now = now or datetime.now(timezone.utc)
    daily = daily_full_test_run_of_main
    mark = daily_memory_review_mark
    on_ned_box = mark.this_machine_is_ned_box()
    machine = (daily.DAILY_FULL_TEST_RUN_MACHINE_NAME_ON_NED_BOX if on_ned_box
               else daily.DAILY_FULL_TEST_RUN_MACHINE_NAME_ELSEWHERE)
    checkout = Path(arguments.checkout).resolve()
    run_started = monotonic()

    resolved = daily.git(checkout, "rev-parse", "--verify", "--quiet", "HEAD^{commit}")
    if resolved.returncode != 0 or not resolved.stdout.strip():
        print(f"{PROGRAM}: not run — git cannot resolve HEAD to a commit in {checkout}.\n"
              f"Pass --checkout the top directory of a checkout at the commit to test.",
              file=sys.stderr)
        return EXIT_CHECKOUT_REFUSED
    head = resolved.stdout.strip()
    differing, why_status_failed = first_tracked_file_that_differs(checkout)
    if why_status_failed is not None:
        print(f"{PROGRAM}: not run — git status failed in {checkout}: {why_status_failed}\n"
              f"Fix what git reports, then run this again.", file=sys.stderr)
        return EXIT_CHECKOUT_REFUSED
    if differing is not None:
        print(f"{PROGRAM}: not run — a tracked file in {checkout} differs from its commit "
              f"{head}: {differing}\n"
              f"Pass --checkout a checkout whose tracked files match the commit to test, "
              f"such as a detached worktree at that commit.", file=sys.stderr)
        return EXIT_CHECKOUT_REFUSED

    steps_failed = []
    since = None
    since_for_the_record = "not resolved"
    if arguments.since:
        given = daily.git(checkout, "rev-parse", "--verify", "--quiet",
                          f"{arguments.since}^{{commit}}")
        if given.returncode != 0 or not given.stdout.strip():
            steps_failed.append((
                f"not run — git cannot resolve --since {arguments.since} to a commit in "
                f"{checkout}",
                "Pass --since a commit this checkout has, then run this again."))
        else:
            since = given.stdout.strip()
            since_for_the_record = (f"{commit_named_for_the_record(checkout, since)}, given "
                                    f"as --since")
    else:
        merge_base = daily.git(checkout, "merge-base", head, MAIN_AS_THE_CLONE_HAS_IT)
        if merge_base.returncode != 0 or not merge_base.stdout.strip():
            steps_failed.append((
                f"not run — git finds no merge base of {head} and "
                f"{MAIN_AS_THE_CLONE_HAS_IT} in {checkout}: "
                f"{daily.first_stderr_line_or_no_detail(merge_base.stderr)}",
                "Pass --since the commit the selection starts from, then run this again."))
        else:
            since = merge_base.stdout.strip()
            since_for_the_record = (f"{commit_named_for_the_record(checkout, since)}, the "
                                    f"merge base of the head and {MAIN_AS_THE_CLONE_HAS_IT}")

    started = now.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    run_name = f"{now.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{os.getpid()}"
    directory = (Path(arguments.temporary_directory or tempfile.gettempdir()).resolve()
                 / PULL_REQUEST_HEAD_TEST_RUN_DIRECTORY_NAME / f"{head}-{run_name}")
    directory.mkdir(parents=True, exist_ok=True)
    logs = directory / PULL_REQUEST_HEAD_TEST_RUN_LOGS_DIRECTORY_NAME
    # Resolve before changing cwd so a relative override cannot select the checkout's own runner.
    runner = (Path(arguments.test_suite_runner_program).resolve()
              if arguments.test_suite_runner_program
              else PULL_REQUEST_HEAD_TEST_RUN_RUNNER_BESIDE_THIS_FILE)
    completed = None
    verdict_is_on_the_head = True
    seconds_waiting_for_lock = 0
    if since is not None:
        command = [
            sys.executable, str(runner), "--checkout", str(checkout),
            "--only-suites-whose-recorded-inputs-changed-since", since,
            "--log-dir", str(logs)]
        if arguments.recorded_inputs_directory:
            command += ["--recorded-inputs-directory", arguments.recorded_inputs_directory]
        completed, seconds_waiting_for_lock, lock_never_released = (
            daily.run_test_suite_runner_waiting_for_the_machine_lock(
                command, checkout, wait, monotonic))
        if lock_never_released:
            steps_failed.append((
                f"not run — the lock was never released: {run_all_test_suites.PROGRAM} "
                f"exited {run_all_test_suites.EXIT_LOCKED} on every attempt for "
                f"{seconds_waiting_for_lock:.0f} s; its last refusal: "
                f"{daily.first_stderr_line_or_no_detail(completed.stderr)}",
                "Run this again after the run holding that lock has finished."))
        elif completed.returncode < 0:
            steps_failed.append((
                f"{run_all_test_suites.PROGRAM} was "
                f"{run_all_test_suites.describe_exit(completed.returncode)}",
                "Run this again."))
        elif (completed.returncode in (run_all_test_suites.EXIT_ALL_PASSED,
                                       run_all_test_suites.EXIT_SOME_FAILED)
              and daily.runner_summary_line(completed) is None):
            steps_failed.append((
                f"{run_all_test_suites.PROGRAM} exited {completed.returncode} and printed "
                f"no {daily.RUNNER_SUMMARY_LINE_PREFIX} line, which is no verdict",
                "Read the runner's stderr in the record, then run this again."))
        if completed.returncode in (run_all_test_suites.EXIT_ALL_PASSED,
                                    run_all_test_suites.EXIT_SOME_FAILED):
            reasons = why_the_run_is_no_verdict_on_the_head(checkout, head, completed)
            if reasons:
                verdict_is_on_the_head = False
                steps_failed.append((
                    f"no verdict on commit {head} — {'; '.join(reasons)}; the runner's "
                    f"first line: {(completed.stdout.splitlines() or ['none printed'])[0]}",
                    "Run this again on a checkout that nothing else changes while the run "
                    "lasts, such as a detached worktree at the commit to test."))

    summary = daily.runner_summary_line(completed) if completed is not None else None
    record_lines = [
        f"head: {commit_named_for_the_record(checkout, head)}",
        f"selecting since: {since_for_the_record}",
        f"runner: {runner_named_for_the_record(runner)}"]
    record_lines.extend(what_failed for what_failed, _ in steps_failed)
    if completed is None:
        record_lines.append("runner exit code: none, the runner was not run")
    else:
        if completed.returncode != run_all_test_suites.EXIT_LOCKED:
            printed = completed.stdout.splitlines()
            record_lines.append(f"the runner's output, {len(printed)} lines:")
            record_lines.extend(printed)
            if summary is None:
                record_lines.append(
                    f"the runner printed no {daily.RUNNER_SUMMARY_LINE_PREFIX} line; its "
                    f"stderr:")
                record_lines.extend(f"  {line}"
                                    for line in completed.stderr.strip().splitlines())
        record_lines.append(f"runner exit code: {completed.returncode}")
    record_lines.append(
        f"seconds waiting for the machine's lock: {seconds_waiting_for_lock:.0f}")
    record_lines.append(f"wall-clock seconds: {monotonic() - run_started:.0f}")
    record_lines.append(f"logs: {logs} on {machine}")
    exit_code_once_the_record_is_written = (
        daily.EXIT_STEP_OF_THIS_PROGRAM_FAILED if steps_failed else completed.returncode)
    record_lines.append(f"{PROGRAM} exit code: {exit_code_once_the_record_is_written}")
    # Count the complete record, including this header, so quoted runner output cannot impersonate records.
    after_the_first_line = "\n".join(record_lines)
    record = (f"{PROGRAM}: {machine}, started {started}, a record of "
              f"{after_the_first_line.count(chr(10)) + 2} lines\n{after_the_first_line}")

    for what_failed, instruction in steps_failed:
        print(f"{PROGRAM}: {what_failed}\n{instruction}", file=sys.stderr)

    file_name = f"{head}.txt"
    citation = (f"{mark.NED_BOX_SSH_TARGET}:{arguments.log_store_root}/"
                f"{PULL_REQUEST_HEAD_TEST_RUNS_KIND_DIRECTORY_NAME}/{machine}/{file_name}")
    ssh_target = None if on_ned_box else mark.NED_BOX_SSH_TARGET
    local_copy = directory / PULL_REQUEST_HEAD_TEST_RUN_RECORD_LOCAL_COPY_FILE_NAME
    try:
        local_copy.write_text(record + "\n", encoding="utf-8")
    except OSError as error:
        print(f"{PROGRAM}: the record was not written: its local copy {local_copy} could "
              f"not be written ({type(error).__name__}: {error}).\n"
              f"Tell the user what the line above says.\n"
              f"Fix what the error names, then run this again.", file=sys.stderr)
        return daily.EXIT_RECORD_NOT_WRITTEN
    write_command = write_record_command(
        arguments.log_store_root, machine, file_name,
        bytes_of_text_sent_to_a_command(record + "\n"))
    try:
        mark.run_on_ned_box_or_here(
            write_command, ssh_target, daily.DAILY_FULL_TEST_RUN_RECORD_WRITE_TIMEOUT_SECONDS,
            stdin_text=record + "\n")
    except mark.DailyMemoryReviewReadOrWriteFailed as error:
        # The saved retry input is UTF-8; count its bytes rather than the subprocess locale encoding.
        remedy_command = write_record_command(
            arguments.log_store_root, machine, file_name,
            len((record + "\n").encode("utf-8")))
        by_hand = ([*mark.NED_BOX_SSH_COMMAND, ssh_target, remedy_command] if ssh_target
                   else ["/bin/sh", "-c", remedy_command])
        when = ("When ned-box answers ssh again" if ssh_target
                else "When the cause is fixed")
        print(f"{PROGRAM}: the record was not written to {citation} ({error}).\n"
              f"Tell the user what the line above says, and the remedy in the line below.\n"
              f"{when}, write the record by running on this machine: "
              f"{' '.join(shlex.quote(part) for part in by_hand)} < "
              f"{shlex.quote(str(local_copy))}", file=sys.stderr)
        return daily.EXIT_RECORD_NOT_WRITTEN

    if summary is not None and verdict_is_on_the_head:
        print(summary)
    print(f"{PROGRAM}: record written to {citation}")
    return exit_code_once_the_record_is_written


def main_that_leaves_no_exception_uncaught(argv=None) -> int:
    try:
        return main(argv)
    except Exception:
        return exit_code_after_reporting_the_uncaught_exception()


if __name__ == "__main__":
    sys.exit(main_that_leaves_no_exception_uncaught())
