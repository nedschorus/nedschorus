#!/usr/bin/env python3
"""Run every test suite on main once a day on this machine, and record the result in the log-store.

Usage:
  scripts/daily-full-test-run-of-main.py [--clone DIR] [--log-store-root DIR]
                                         [--test-suite-runner-program PATH]
                                         [--temporary-directory DIR]
                                         [--recorded-inputs-directory DIR]

  --clone       the clone `git fetch origin` runs in and the worktree of main
                is made from; default, the clone this file is in
  --log-store-root
                the log-store's root, a path on ned-box; default
                /home/nedlern/nedschorus-logs
  --test-suite-runner-program
                the program run in place of the worktree's
                scripts/run-all-test-suites.py, by the same interpreter with
                the same arguments; default, the worktree's own
  --temporary-directory
                where this program keeps its one directory, which holds the
                worktree, the run's logs, the record's local copies and this
                program's lock; default, the system temp directory
  --recorded-inputs-directory
                passed through to the runner; default, not passed, so the
                runner uses the machine's own recordings store

Every option is a seam for scripts/daily-full-test-run-of-main-test.py, and
for a run made by hand that must not write to the real log-store or the real
recordings store. A scheduled run passes none.

WHY THIS EXISTS (user-ruled 2026-09-30, walk
open-questions-concerns-and-recommendations-2026-09-30, item 5, point 4, his
"y both" at 2026-09-30T22:10:33Z in Mac session 17e13623). A pull request's
head, and main after a merge, run only the suites the change reaches, chosen
by `scripts/run-all-test-suites.py
--only-suites-whose-recorded-inputs-changed-since`. A failure caused by a file
left on a machine shows up in no code diff, so no selection finds it. Each
machine therefore runs every suite on main once a day. The daily run blocks
no merge: it writes a record, and whoever reads the record acts on it. It is
also the run that records every suite's inputs afresh at main, which the
runner's docstring calls the daily full run.

WHAT ONE RUN DOES, in order.

  1. `git fetch origin` in the clone. A failed fetch stops the run and is
     written to the record.
  2. Resolves refs/remotes/origin/main to its full commit hash and makes a
     detached worktree at that hash (`git worktree add --detach`), so no
     branch is made and nothing rests on FETCH_HEAD, which another agent's
     fetch can move. A worktree a killed run left at the same path is removed
     first.
  3. Runs `<the Python running this program>
     <worktree>/scripts/run-all-test-suites.py -j 4 --log-dir <logs>` from the
     worktree, with no selection option. While the runner exits 3, another
     run holding the machine's lock, this program waits 2 seconds and runs it
     again, for up to an hour; after that the record says the lock was never
     released. The verdict is the runner's exit code and its `SUMMARY:` line,
     read from the runner's own captured output and never from a pipeline.
  4. Removes the worktree, whatever step 3 did. When `git worktree remove
     --force` leaves the directory, because the run left a directory in it
     that its owner may not write to, this program gives the owner read,
     write and search permission on every directory in the worktree and
     removes the worktree itself.
  5. Writes the record, replacing the day's earlier one.
  6. Prints the record's citation and exits.

THE RECORD is one text file per machine and day in the log-store:

  nedlern@ned-box:/home/nedlern/nedschorus-logs/daily-full-test-runs/<machine>/<YYYY-MM-DD>.txt

<machine> is `ned-box` or `mac`, the spellings the log-store's transcripts/
directory uses. The date is the date in America/Los_Angeles when the run
started, never the machine's own zone. The record holds: this program's
name, the machine, the date and the UTC time the run started; origin/main's
commit; the runner's first line (checkout, commit, suite count, Python);
every line the runner printed that opens `FAIL`; every line for a skipped
case, which the runner prints as `<suite>: SKIP ...`; the `SUMMARY:` line; the
runner's exit code; the seconds spent waiting for the machine's lock; the
wall-clock seconds from the fetch to the worktree's removal; and the
directory holding the run's logs. A step that failed is a line of the record
too: a failed fetch, a worktree that could not be made or removed, a lock
never released. A runner that printed no `SUMMARY:` line has its stderr in
the record in the line's place.

On ned-box the record is written locally. On the Mac it is written over ssh,
with the options the log-store's other writers pass. Before either, the
record is written beside the logs as its local copy,
daily-full-test-run-record-<YYYY-MM-DD>.txt, named by the record's own date,
so a record that could not reach the log-store is still on the machine that
made it, and the refusal names the one command that writes it once ned-box
answers. A later run on the same day replaces the day's local copy, as it
replaces the day's record; a run on another day writes another file, so the
command a refusal named still writes that day's record under that day's name
after later runs. This program removes no local copy: one is left per day a
run was made, each about a kilobyte, until the machine clears its temporary
directory.

THE LOGS stay on the machine: <temporary directory>/
nedschorus-daily-full-test-run-of-main/logs, which each run replaces and the
record names. They are not copied into the log-store.

ONE DAILY RUN AT A TIME PER MACHINE. The worktree and the logs are at fixed
paths, so that the next run replaces what a killed run left instead of adding
to it. A second run started by hand while the scheduled one is going would
therefore remove the worktree the first is testing. So a run holds an
exclusive lock on daily-full-test-run-of-main.lock in its directory, and a
second run exits 6 having done nothing.

The runner holds the lock too: its process is started with the lock's file
descriptor (`pass_fds`), and a lock taken with flock is held until every
process holding that descriptor has closed it or exited. A program stopped by
its process ID leaves its runner running, and the runner is what tests in the
worktree, so the lock is held until the runner exits as well. No other
process this program starts is given the descriptor. Nothing the runner
starts holds the descriptor either: the runner starts each suite, strace and
git with `subprocess.run`, which closes every descriptor above 2 in the
process it starts, so a process a suite leaves behind cannot keep later daily
runs out.

WHAT IS REUSED. nc-systems/handoff/daily-memory-review-mark.py is loaded by
path, the way nc-systems/handoff/handoff-supervisor.py loads it, for the
Pacific date (pacific_time_of), the test that this machine is ned-box
(this_machine_is_ned_box), ned-box's ssh target, and
run_on_ned_box_or_here, which runs one shell command over ssh or here with
the ssh options and carries the content on stdin. Its
write_daily_memory_review_mark is not reused: it builds its target from the
marks' directory, so this program hands run_on_ned_box_or_here the same
`mkdir -p ... && cat > ...` command over its own directory.
scripts/run-all-test-suites.py is loaded the same way for the runner's name,
its exit code for a held lock, and the environment its own git calls run in,
which drops the variables that send git into another repository.

SCHEDULE. Installed on each machine by hand; no scheduler file is in the
repository.

  ned-box: one cron line, run from the reference clone with the system's
  Python. ned-box's clock is America/Los_Angeles.

    30 3 * * * /usr/bin/python3 /home/nedlern/Projects/nedschorus/scripts/daily-full-test-run-of-main.py >> /home/nedlern/.claude/daily-full-test-run-of-main.log 2>&1

  Both streams are appended to that file because ned-box has no mail
  transfer agent, so cron discards what a job prints: a refusal that writes
  no record, exit 5 or exit 6, is read there.

  the Mac: a launchd job at 03:30 Pacific, the same time as ned-box. A run
  missed while the Mac sleeps starts at the next wake (user-ruled, his "y" at
  2026-10-01T04:38:17Z in Mac session 8db2e753, item 11 of the walk
  open-questions-concerns-and-recommendations-2026-09-30).

WHO READS THE RECORD. The seat merge-lane-2 reads ned-box's newest record at
each session start, and no other channel carries a failed or missing record
to the user (user-ruled, his "y" at 2026-10-01T04:43:20Z in the same Mac
session, item 12 of the same walk).

Exit codes: the runner's own when it ran and every step of this program
worked — 0 every suite passed, 1 a suite failed, 2 the runner could not
start; 2 also for a bad invocation of this program; 4 a step of this program
failed, which the record names, the runner was killed by a signal, or it
exited 0 or 1 without a `SUMMARY:` line, which is no verdict; 5 the record
was not written; 6 another daily run holds this program's lock.
"""

import argparse
import fcntl
import importlib.util
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

PROGRAM = "daily-full-test-run-of-main"

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent


def module_loaded_by_path(module_name: str, path: Path):
    """A module whose file name has hyphens, loaded the way
    nc-systems/handoff/handoff-supervisor.py loads the mark program."""
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# See WHAT IS REUSED in the module docstring.
daily_memory_review_mark = module_loaded_by_path(
    "daily_memory_review_mark",
    REPOSITORY_ROOT / "nc-systems" / "handoff" / "daily-memory-review-mark.py")
run_all_test_suites = module_loaded_by_path(
    "run_all_test_suites", Path(__file__).resolve().with_name("run-all-test-suites.py"))

DAILY_FULL_TEST_RUN_DEFAULT_LOG_STORE_ROOT = "/home/nedlern/nedschorus-logs"
# The log-store's kind, and the two machines' names under it: the spellings
# the log-store's transcripts/ directory uses.
DAILY_FULL_TEST_RUNS_KIND_DIRECTORY_NAME = "daily-full-test-runs"
DAILY_FULL_TEST_RUN_MACHINE_NAME_ON_NED_BOX = "ned-box"
DAILY_FULL_TEST_RUN_MACHINE_NAME_ELSEWHERE = "mac"

# This program's one directory under the temporary directory, and what it holds.
DAILY_FULL_TEST_RUN_DIRECTORY_NAME = "nedschorus-daily-full-test-run-of-main"
DAILY_FULL_TEST_RUN_WORKTREE_DIRECTORY_NAME = "worktree-of-main"
DAILY_FULL_TEST_RUN_LOGS_DIRECTORY_NAME = "logs"
# The record's local copy is this prefix, the record's date and `.txt`.
DAILY_FULL_TEST_RUN_RECORD_LOCAL_COPY_FILE_NAME_PREFIX = "daily-full-test-run-record-"
DAILY_FULL_TEST_RUN_LOCK_FILE_NAME = "daily-full-test-run-of-main.lock"

DAILY_FULL_TEST_RUN_RUNNER_PATH_IN_WORKTREE = Path("scripts") / "run-all-test-suites.py"
# The runner's docstring: -j 4 is the measured choice.
DAILY_FULL_TEST_RUN_SUITES_AT_ONCE = "4"

# How long the runner's exit 3 is waited out, and how long between attempts.
# Read from the module inside main rather than bound as default arguments, so
# a case can lower the bound.
DAILY_FULL_TEST_RUN_LOCK_WAIT_SECONDS = 2
DAILY_FULL_TEST_RUN_LOCK_WAIT_BOUND_SECONDS = 3600

# How long the record's write gets before it is given up on.
DAILY_FULL_TEST_RUN_RECORD_WRITE_TIMEOUT_SECONDS = 30

# The runner prints a skipped case as `<suite>: SKIP <the suite's own words>`,
# under its `skipped cases:` heading.
RUNNER_SKIPPED_CASE_LINE = re.compile(r"^(?:\S+: )?SKIP\s")
RUNNER_FAILED_SUITE_LINE_PREFIX = "FAIL "
RUNNER_SUMMARY_LINE_PREFIX = "SUMMARY:"

EXIT_STEP_OF_THIS_PROGRAM_FAILED = 4
EXIT_RECORD_NOT_WRITTEN = 5
EXIT_ANOTHER_DAILY_RUN_HOLDS_THE_LOCK = 6


def git(clone: Path, *arguments):
    return subprocess.run(
        ["git", "-C", str(clone), *arguments],
        env=run_all_test_suites.environment_without_git_redirecting_variables(),
        stdin=subprocess.DEVNULL, capture_output=True, text=True, errors="replace",
        check=False)


def first_stderr_line_or_no_detail(text: str) -> str:
    return (text.strip().splitlines() or ["no detail"])[0]


def first_fatal_or_error_stderr_line_or_no_detail(text: str) -> str:
    """git's error line when git wrote a progress line before it: the first
    line opening `fatal:` or `error:`, else the first line. `git worktree add`
    writes `Preparing worktree (detached HEAD ...)` first and its error
    second."""
    for line in text.strip().splitlines():
        if line.startswith(("fatal:", "error:")):
            return line
    return first_stderr_line_or_no_detail(text)


def take_daily_full_test_run_lock(lock_file: Path):
    """The open, locked handle, or None when another daily run holds it."""
    handle = open(lock_file, "a")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


def give_owner_read_write_and_search_on_every_directory_under(directory: Path):
    """Give the owner read, write and search permission on the directory and
    on every directory in it, so that what they hold can be removed: removing
    a name needs write and search permission on the directory holding it. A
    symbolic link is neither changed nor followed, so nothing outside the
    directory is changed, and a directory whose mode cannot be changed is left
    for the removal to fail on."""
    def give(path) -> bool:
        """Whether the path is a directory and not a symbolic link to one."""
        try:
            mode = os.lstat(path).st_mode
            if not stat.S_ISDIR(mode):
                return False
            os.chmod(path, stat.S_IMODE(mode) | stat.S_IRWXU)
        except OSError:
            pass
        return True

    if not give(directory):
        return
    # Top-down, so each directory is made readable before it is listed.
    for parent, directory_names, _ in os.walk(directory):
        for name in directory_names:
            give(os.path.join(parent, name))


def remove_worktree_of_main(clone: Path, worktree: Path):
    """Remove the worktree and its registration in the clone; None when it is
    gone, or why it is not. `git worktree remove --force` also clears a
    registration whose directory is already gone, and a directory git does
    not know is removed as a plain directory. When git could not delete the
    directory, git has dropped the registration all the same, and what is
    left is removed here, with permission restored on its directories
    first."""
    removed = git(clone, "worktree", "remove", "--force", str(worktree))
    if worktree.exists():
        give_owner_read_write_and_search_on_every_directory_under(worktree)
        shutil.rmtree(worktree, ignore_errors=True)
    if worktree.exists():
        return first_stderr_line_or_no_detail(removed.stderr)
    return None


def run_test_suite_runner_waiting_for_the_machine_lock(command, worktree: Path, wait,
                                                       monotonic, lock_handle):
    """(the runner's finished run, seconds spent waiting for the lock, whether
    the lock was never released). The runner is run again every
    DAILY_FULL_TEST_RUN_LOCK_WAIT_SECONDS while it exits 3, until an attempt
    starts DAILY_FULL_TEST_RUN_LOCK_WAIT_BOUND_SECONDS or more after the first.
    The runner is given this program's lock; see ONE DAILY RUN AT A TIME PER
    MACHINE in the module docstring."""
    waiting_started = monotonic()
    while True:
        attempt_started = monotonic()
        completed = subprocess.run(
            command, cwd=str(worktree),
            env=run_all_test_suites.environment_without_git_redirecting_variables(),
            stdin=subprocess.DEVNULL, capture_output=True, text=True, errors="replace",
            check=False, pass_fds=(lock_handle.fileno(),))
        waited = attempt_started - waiting_started
        if completed.returncode != run_all_test_suites.EXIT_LOCKED:
            return completed, waited, False
        if waited >= DAILY_FULL_TEST_RUN_LOCK_WAIT_BOUND_SECONDS:
            return completed, waited, True
        wait(DAILY_FULL_TEST_RUN_LOCK_WAIT_SECONDS)


def runner_summary_line(completed):
    """The runner's last line opening `SUMMARY:`, or None when it printed none."""
    summary = [line for line in completed.stdout.splitlines()
               if line.startswith(RUNNER_SUMMARY_LINE_PREFIX)]
    return summary[-1] if summary else None


def runner_output_lines_for_the_record(completed):
    """The lines of the runner's output the record keeps, in the runner's own
    order; see THE RECORD in the module docstring."""
    printed = completed.stdout.splitlines()
    kept = []
    if printed and printed[0].startswith(f"{run_all_test_suites.PROGRAM}: "):
        kept.append(printed[0])
    kept.extend(line for line in printed
                if line.startswith(RUNNER_FAILED_SUITE_LINE_PREFIX)
                or RUNNER_SKIPPED_CASE_LINE.match(line))
    summary = runner_summary_line(completed)
    if summary is not None:
        kept.append(summary)
    else:
        kept.append(f"the runner printed no {RUNNER_SUMMARY_LINE_PREFIX} line; its stderr:")
        kept.extend(f"  {line}" for line in completed.stderr.strip().splitlines())
    return kept


def write_record_command(log_store_root: str, machine: str, file_name: str) -> str:
    """The shell command that writes the record from its stdin, replacing the
    day's earlier one."""
    directory = f"{log_store_root}/{DAILY_FULL_TEST_RUNS_KIND_DIRECTORY_NAME}/{machine}"
    return f"mkdir -p {shlex.quote(directory)} && cat > {shlex.quote(f'{directory}/{file_name}')}"


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        prog=PROGRAM,
        description="Run every test suite on main on this machine and record the result "
                    "in the log-store.")
    parser.add_argument("--clone", default=str(REPOSITORY_ROOT))
    parser.add_argument("--log-store-root", default=DAILY_FULL_TEST_RUN_DEFAULT_LOG_STORE_ROOT)
    parser.add_argument("--test-suite-runner-program")
    parser.add_argument("--temporary-directory")
    parser.add_argument("--recorded-inputs-directory")
    return parser.parse_args(argv)


def main(argv=None, now=None, wait=time.sleep, monotonic=time.monotonic) -> int:
    arguments = parse_arguments(argv)
    now = now or datetime.now(timezone.utc)
    mark = daily_memory_review_mark
    on_ned_box = mark.this_machine_is_ned_box()
    machine = (DAILY_FULL_TEST_RUN_MACHINE_NAME_ON_NED_BOX if on_ned_box
               else DAILY_FULL_TEST_RUN_MACHINE_NAME_ELSEWHERE)
    pacific_date = mark.pacific_time_of(now).date().isoformat()
    clone = Path(arguments.clone).resolve()
    directory = (Path(arguments.temporary_directory or tempfile.gettempdir()).resolve()
                 / DAILY_FULL_TEST_RUN_DIRECTORY_NAME)
    directory.mkdir(parents=True, exist_ok=True)
    lock_file = directory / DAILY_FULL_TEST_RUN_LOCK_FILE_NAME
    lock_handle = take_daily_full_test_run_lock(lock_file)
    if lock_handle is None:
        print(f"{PROGRAM}: not run — another daily full test run holds {lock_file}.\n"
              f"Run this again after that run has finished.", file=sys.stderr)
        return EXIT_ANOTHER_DAILY_RUN_HOLDS_THE_LOCK
    try:
        return daily_full_test_run_under_lock(
            arguments, now, wait, monotonic, on_ned_box, machine, pacific_date, clone,
            directory, lock_handle)
    finally:
        lock_handle.close()


def daily_full_test_run_under_lock(arguments, now, wait, monotonic, on_ned_box, machine,
                                   pacific_date, clone, directory, lock_handle) -> int:
    mark = daily_memory_review_mark
    worktree = directory / DAILY_FULL_TEST_RUN_WORKTREE_DIRECTORY_NAME
    logs = directory / DAILY_FULL_TEST_RUN_LOGS_DIRECTORY_NAME
    run_started = monotonic()
    # Each is one line of the record, and one refusal on stderr: what failed,
    # then the instruction.
    steps_failed = []
    commit = None
    completed = None
    seconds_waiting_for_lock = 0

    fetched = git(clone, "fetch", "origin")
    if fetched.returncode != 0:
        steps_failed.append((
            f"not run — git fetch origin failed in {clone}: "
            f"{first_stderr_line_or_no_detail(fetched.stderr)}",
            "Fix what git reports, then run this again."))
    else:
        resolved = git(clone, "rev-parse", "--verify", "--quiet",
                       "refs/remotes/origin/main^{commit}")
        if resolved.returncode != 0 or not resolved.stdout.strip():
            steps_failed.append((
                f"not run — git cannot resolve refs/remotes/origin/main in {clone}",
                "Fix the clone's origin remote, then run this again."))
        else:
            commit = resolved.stdout.strip()
    if commit is not None:
        remove_worktree_of_main(clone, worktree)
        added = git(clone, "worktree", "add", "--detach", str(worktree), commit)
        if added.returncode != 0:
            steps_failed.append((
                f"not run — git worktree add --detach {worktree} {commit} failed in "
                f"{clone}: {first_fatal_or_error_stderr_line_or_no_detail(added.stderr)}",
                "Fix what git reports, then run this again."))
        else:
            try:
                shutil.rmtree(logs, ignore_errors=True)
                command = [
                    sys.executable,
                    arguments.test_suite_runner_program
                    or str(worktree / DAILY_FULL_TEST_RUN_RUNNER_PATH_IN_WORKTREE),
                    "-j", DAILY_FULL_TEST_RUN_SUITES_AT_ONCE, "--log-dir", str(logs)]
                if arguments.recorded_inputs_directory:
                    command += ["--recorded-inputs-directory",
                                arguments.recorded_inputs_directory]
                completed, seconds_waiting_for_lock, lock_never_released = (
                    run_test_suite_runner_waiting_for_the_machine_lock(
                        command, worktree, wait, monotonic, lock_handle))
                if lock_never_released:
                    steps_failed.append((
                        f"not run — the lock was never released: "
                        f"{run_all_test_suites.PROGRAM} exited "
                        f"{run_all_test_suites.EXIT_LOCKED} on every attempt for "
                        f"{seconds_waiting_for_lock:.0f} s; its last refusal: "
                        f"{first_stderr_line_or_no_detail(completed.stderr)}",
                        "Run this again after the run holding that lock has finished."))
                elif completed.returncode < 0:
                    steps_failed.append((
                        f"{run_all_test_suites.PROGRAM} was "
                        f"{run_all_test_suites.describe_exit(completed.returncode)}",
                        "Run this again."))
                elif (completed.returncode in (run_all_test_suites.EXIT_ALL_PASSED,
                                               run_all_test_suites.EXIT_SOME_FAILED)
                      and runner_summary_line(completed) is None):
                    steps_failed.append((
                        f"{run_all_test_suites.PROGRAM} exited {completed.returncode} "
                        f"and printed no {RUNNER_SUMMARY_LINE_PREFIX} line, which is no "
                        f"verdict",
                        "Read the runner's stderr in the record, then run this again."))
            finally:
                not_removed = remove_worktree_of_main(clone, worktree)
                if not_removed is not None:
                    steps_failed.append((
                        f"the worktree {worktree} was not removed: {not_removed}",
                        f"Remove it with: chmod -R u+rwx {shlex.quote(str(worktree))} && "
                        f"rm -rf {shlex.quote(str(worktree))} && "
                        f"git -C {shlex.quote(str(clone))} worktree prune"))

    record_lines = [
        f"{PROGRAM}: {machine}, {pacific_date} in {mark.PACIFIC_TIME_ZONE_NAME}, started "
        f"{now.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"origin/main: {commit or 'not resolved'}"]
    record_lines.extend(what_failed for what_failed, _ in steps_failed)
    if completed is None:
        record_lines.append("runner exit code: none, the runner was not run")
    else:
        if completed.returncode != run_all_test_suites.EXIT_LOCKED:
            record_lines.extend(runner_output_lines_for_the_record(completed))
        record_lines.append(f"runner exit code: {completed.returncode}")
    record_lines.append(
        f"seconds waiting for the machine's lock: {seconds_waiting_for_lock:.0f}")
    record_lines.append(f"wall-clock seconds: {monotonic() - run_started:.0f}")
    record_lines.append(f"logs: {logs} on {machine}")
    record = "\n".join(record_lines)

    for what_failed, instruction in steps_failed:
        print(f"{PROGRAM}: {what_failed}\n{instruction}", file=sys.stderr)

    file_name = f"{pacific_date}.txt"
    citation = (f"{mark.NED_BOX_SSH_TARGET}:{arguments.log_store_root}/"
                f"{DAILY_FULL_TEST_RUNS_KIND_DIRECTORY_NAME}/{machine}/{file_name}")
    ssh_target = None if on_ned_box else mark.NED_BOX_SSH_TARGET
    write_command = write_record_command(arguments.log_store_root, machine, file_name)
    local_copy = directory / (
        f"{DAILY_FULL_TEST_RUN_RECORD_LOCAL_COPY_FILE_NAME_PREFIX}{pacific_date}.txt")
    try:
        local_copy.write_text(record + "\n", encoding="utf-8")
    except OSError as error:
        print(f"{PROGRAM}: the record was not written: its local copy {local_copy} could "
              f"not be written ({type(error).__name__}: {error}).\n"
              f"Tell the user what the line above says.\n"
              f"Fix what the error names, then run this again.", file=sys.stderr)
        return EXIT_RECORD_NOT_WRITTEN
    try:
        mark.run_on_ned_box_or_here(
            write_command, ssh_target, DAILY_FULL_TEST_RUN_RECORD_WRITE_TIMEOUT_SECONDS,
            stdin_text=record + "\n")
    except mark.DailyMemoryReviewReadOrWriteFailed as error:
        by_hand = ([*mark.NED_BOX_SSH_COMMAND, ssh_target, write_command] if ssh_target
                   else ["/bin/sh", "-c", write_command])
        when = ("When ned-box answers ssh again" if ssh_target
                else "When the cause is fixed")
        print(f"{PROGRAM}: the record was not written to {citation} ({error}).\n"
              f"Tell the user what the line above says, and the remedy in the line below.\n"
              f"{when}, write the record by running on this machine: "
              f"{' '.join(shlex.quote(part) for part in by_hand)} < "
              f"{shlex.quote(str(local_copy))}", file=sys.stderr)
        return EXIT_RECORD_NOT_WRITTEN

    print(f"{PROGRAM}: record written to {citation}")
    if steps_failed:
        return EXIT_STEP_OF_THIS_PROGRAM_FAILED
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
