#!/usr/bin/env python3
"""Run the test suites a pull request's head reaches, and file the test log under the head's commit hash.

Usage:
  scripts/pull-request-head-test-run.py [--checkout DIR] [--since COMMIT]
                                        [--log-store-root DIR]
                                        [--test-suite-runner-program PATH]
                                        [--temporary-directory DIR]
                                        [--recorded-inputs-directory DIR]

  --checkout    the top directory of a checkout at the commit to test, a pull
                request's head; default, the checkout this file is in
  --since       the commit the selection of suites starts from; default, the
                merge base of the checkout's commit and
                refs/remotes/origin/main as the checkout's clone has it, with
                no fetch
  --log-store-root
                the log-store's root, a path on ned-box; default
                /home/nedlern/nedschorus-logs
  --test-suite-runner-program
                the program run in place of the scripts/run-all-test-suites.py
                beside this file, by the same interpreter with the same
                arguments; a relative path is taken from the directory this
                program is started in, not from the checkout; default, the
                one beside this file
  --temporary-directory
                where this program keeps its directory, which holds each
                run's logs and the record's local copy; default, the system
                temp directory
  --recorded-inputs-directory
                passed through to the runner; default, not passed, so the
                runner uses the machine's own recordings store

The last four options are seams for scripts/pull-request-head-test-run-test.py,
and for a run made by hand that must not write to the real log-store or the
real recordings store.

WHY THIS EXISTS (user-ruled 2026-10-01, walk
per-pull-request-review-subagent-brief-standing-text-2026-09-29-4, item 2,
option (iii), his "Y" at 2026-10-01T05:09:20Z in Mac session 08e0087f). A
pull request's head runs only the suites its change reaches, chosen by
`scripts/run-all-test-suites.py
--only-suites-whose-recorded-inputs-changed-since`. Until this program the
only account of what was run at a head was two lines of the runner's output
that the pull request's author was to quote in the pull request, and that
walk's item 2 counted one pull request in 30 that quoted both. The run
merge-lane-2's review subagent made at a head left nothing a program could
read. The user's words on quoting a run: "I'd think the standard SDLC way
would be for there to be a test log, which would log all tests with enough
info that any program or agent could check exactly what tests were run on
exactly what code or whatever." So the machine that runs the tests writes the
test log, filed under the commit it tested, the way a continuous-integration
service attaches a check to a commit, and nobody quotes a run. The repository
has no such service: no workflow file, and no commit status or check run on
main.

WHAT ONE RUN DOES, in order.

  1. Resolves the checkout's HEAD to its full commit hash, the head. A
     checkout with no commit is refused.
  2. Refuses, running nothing and writing no record, when a tracked file of
     the checkout differs from the head (`git status --porcelain
     --untracked-files=no` prints a line, for a change that is staged as for
     one that is not): the record is filed under the head's hash, so it must
     be the head's files that were tested.
  3. Settles the commit the selection starts from: --since, or the merge base
     of the head and refs/remotes/origin/main. Nothing is fetched, so an
     origin/main the clone has not caught up with gives an older merge base
     or the same one, and an older one selects the same suites or more. A
     --since git cannot resolve, or a head with no merge base, is a failed
     step: the runner is not run, and the record says why.
  4. Runs `<the Python running this program> <the runner> --checkout
     <checkout> --only-suites-whose-recorded-inputs-changed-since <since> -j 4
     --log-dir <logs>` from the checkout. While the runner exits 3, another
     run holding the machine's lock, this program waits and runs it again
     as scripts/daily-full-test-run-of-main.py does, whose function and bound
     it uses: every 2 seconds for up to an hour, after which the record says
     the lock was never released. The verdict is the runner's
     exit code and its `SUMMARY:` line, read from the runner's own captured
     output and never from a pipeline.
  5. Checks that the runner's verdict, exit 0 or exit 1, is a verdict on the
     head. See THE HEAD IS COMPARED THREE TIMES below. When it is not, that
     is a failed step: the record says what differed and quotes the runner's
     first line, the `SUMMARY:` line is not printed, and the exit code is 4.
  6. Writes the record, replacing an earlier one of the same machine and
     head.
  7. Prints the runner's `SUMMARY:` line, when it printed one and step 5
     found nothing, then the record's citation, and exits.

THE HEAD IS COMPARED THREE TIMES, because the checkout this program is given
may be one a seat is working in, and the wait of step 4 can last an hour.
Step 2 compares before anything runs. Step 5 makes two more comparisons, and
each closes a window the other leaves open:

  - The runner's first line must name the head's full hash and say `tracked
    files match that commit`. The runner reads the checkout's commit and its
    tracked files once it holds the machine's lock, so that line is the
    runner's own account of what it was about to test, after the wait. It
    catches a change made during the wait, one put back before the runner
    exits included.
  - After the runner exits, HEAD must still be the head and no tracked file
    may differ. That catches a change made while the suites were running,
    after the runner wrote its first line.

A change made and put back while the suites are running is seen by neither.
A runner whose first line this program cannot read as naming the head fails
step 5 too, so a change to that line's wording in the runner shows as a
failed step on every run and never as a pass.

WHICH RUNNER RUNS. The scripts/run-all-test-suites.py beside this file, on
the checkout it is given, never the checkout's own copy. So main's copy of
this program tests a pull request's files with main's runner: a pull request
that edits the runner cannot be passed by its own edit, and the edited runner
is still tested, by scripts/run-all-test-suites-test.py in the checkout, which
the runner runs like any other suite. The record names the runner that ran
and the commit of the checkout that runner sits in.

THE RECORD is one text file per machine and head in the log-store:

  nedlern@ned-box:/home/nedlern/nedschorus-logs/pull-request-head-test-runs/<machine>/<full hash>.txt

<full hash> is the head's. <machine> is `ned-box` or `mac`, as in the daily
run's records, so that a run of one head on the Mac and a run of it on ned-box
each keep their record.
The record holds, in this order: this program's name, the machine and the
UTC time the run started; the head, as `commit <hash> ("<subject>")`; the
commit the selection started from, the same way, and whether it was the
merge base or given as --since; the runner's path and the commit of the
checkout it sits in, which says nothing of whether the runner's own file
matches that commit; each step that failed; the line `the runner's output,
<n> lines:` and then those n lines exactly as the runner printed them, which
are its first line (checkout, commit, whether tracked files match it, suite
count, how many were selected, Python), a `SELECTED` or `NOT SELECTED` line
with its reason for every suite, a `PASS` or `FAIL` line for every suite
run, each failed suite again with its log, every skipped case, and the
`SUMMARY:` line; the runner's exit code; the seconds spent waiting for the
machine's lock; the wall-clock seconds; the directory holding the run's logs;
and last, this program's own exit code for the run, as
`pull-request-head-test-run exit code: <n>`. That last line is the run's
verdict in one line: the runner's exit code and its `SUMMARY:` line say what
the runner found, and a failed step of this program makes the run no verdict
whatever they say. The code in that line is the one this program exits with
once the record is written. A run whose record could not be written exits 5
instead, and its record, kept beside the logs and never in the log-store
unless the remedy puts it there, carries the code the run would have exited
with. A runner that printed no `SUMMARY:` line has its stderr in the record
after its output. A run whose lock was never released records that and none
of the runner's refusals.

On ned-box the record is written locally. On the Mac it is written over ssh,
with the options the log-store's other writers pass. Either way the record is
written under a name of the run's own in the record's directory,
.<full hash>.txt.<UTC start>-<pid>.partial, and renamed over the record, so
that two runs writing at once leave one run's whole record and never a part
of each. Before the rename the command counts the bytes that arrived in that
file and compares the count with the count of the bytes this program sent:
an `ssh` client that dies while the far side is still reading gives the far
side an end of input like any other, so the far side cannot tell a record cut
short from a whole one except by its length. On a different count the command
removes that file, says so on stderr, renames nothing and exits 1, and the
record there stays as it was. It removes the file before it says so: once the
client is gone stderr has no reader, and the shell is killed at its first
write there. The command holds ASCII characters alone, apart from the paths
it is given: this program hands it to a process as an argument, which Python
encodes with the filesystem encoding, and a character that encoding lacks
would stop every run before anything is sent. Before either, the record is
written beside the logs as pull-request-head-test-run-record.txt, so a record
that could not reach the log-store is still on the machine that made it, and
the refusal names the one command that writes it once ned-box answers. That
command first takes its whole record, counted the same way, and then looks at
the record it finds. That record can be its own run's already: the far side
renamed the record and the client died before the exit status came back, so
this program said the record was not written, or the command was run before.
When the two hold the same bytes the command writes nothing, says the record
is written and exits 0. Otherwise the command may be running after another
run of the same head has written its record, so it reads the `started` moment
in the first line of the record it finds and writes nothing unless that moment
is earlier than its own run's. `started` is to the second, and two runs of
one head can start in the same second, so on the same moment too the record
there stays. A record there whose first line gives no such moment is replaced.

THE LOGS stay on the machine: <temporary directory>/
nedschorus-pull-request-head-test-run/<head>-<UTC start>-<pid>/logs, which the
record names. Each run has a directory of its own, because two runs of one
head can be started on one machine at once: merge-lane-2's review subagent
and the independent reviewer work on the same head in parallel on ned-box.
The runner's lock makes the second wait, and a directory the two shared would
have the second replacing logs the first is still writing. So this program
takes no lock of its own, and removes nothing.

WHAT IS REUSED. scripts/daily-full-test-run-of-main.py is loaded by path, the
way it loads its own two modules, for: the wait on the runner's lock
(run_test_suite_runner_waiting_for_the_machine_lock, with its bound, called
with no lock for the runner to hold: the daily run gives its runner the daily
run's own lock, and this program takes none); the
runner's `SUMMARY:` line; its git call, which drops the variables that send
git into another repository; the two machines' names; the log-store's default
root; the -j the runner is given; the write's timeout; and the exit codes for
a failed step and a record not written. Through it come the two modules it loads:
nc-systems/handoff/daily-memory-review-mark.py, for the test that this machine
is ned-box, ned-box's ssh target, and run_on_ned_box_or_here, which runs one
shell command over ssh or here and carries the record on stdin; and
scripts/run-all-test-suites.py, for the runner's name and exit codes.

Exit codes: the runner's own when it ran and every step of this program
worked — 0 every selected suite passed, 1 a suite failed, 2 the runner could
not start; 2 also when this program refuses the checkout it was given, with
no record written, and for a bad invocation; 4 a step of this program failed,
which the record names, the runner was killed by a signal, it exited 0 or 1
without a `SUMMARY:` line, which is no verdict, or its verdict was not a
verdict on the head; 5 the record was not written; 7 an exception nothing
caught stopped this program, a module it loads failing to load included: the
traceback is on stderr, and the run gives no verdict. Python's own exit code
for an uncaught exception is 1, the code for a failed suite, so this program
never leaves one uncaught.
"""

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

# See Exit codes in the module docstring.
EXIT_STOPPED_BY_AN_UNCAUGHT_EXCEPTION = 7


def exit_code_after_reporting_the_uncaught_exception() -> int:
    """Called while an exception is being handled: the traceback on stderr,
    then what this exit means and what to do, and the exit code."""
    traceback.print_exc()
    print(f"{PROGRAM}: not finished — the error above stopped this program, and this run "
          f"gives no verdict.\n"
          f"Tell the user what the error above says.", file=sys.stderr)
    return EXIT_STOPPED_BY_AN_UNCAUGHT_EXCEPTION


def module_loaded_by_path(module_name: str, path: Path):
    """A module whose file name has hyphens, loaded the way
    scripts/daily-full-test-run-of-main.py loads its own."""
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# See WHAT IS REUSED in the module docstring. Run as a program, a module that
# does not load, or lacks a name taken from it here, ends the run with the exit
# code for an uncaught exception; a program that imports this file is handed
# the exception.
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

# The log-store's kind. Under it, one directory per machine, named as the
# daily run names them.
PULL_REQUEST_HEAD_TEST_RUNS_KIND_DIRECTORY_NAME = "pull-request-head-test-runs"

# This program's directory under the temporary directory, and what each run's
# own directory inside it holds.
PULL_REQUEST_HEAD_TEST_RUN_DIRECTORY_NAME = "nedschorus-pull-request-head-test-run"
PULL_REQUEST_HEAD_TEST_RUN_LOGS_DIRECTORY_NAME = "logs"
PULL_REQUEST_HEAD_TEST_RUN_RECORD_LOCAL_COPY_FILE_NAME = "pull-request-head-test-run-record.txt"

# See WHICH RUNNER RUNS in the module docstring.
PULL_REQUEST_HEAD_TEST_RUN_RUNNER_BESIDE_THIS_FILE = Path(__file__).resolve().with_name(
    "run-all-test-suites.py")

MAIN_AS_THE_CLONE_HAS_IT = "refs/remotes/origin/main"

# What the runner's first line says of a checkout whose tracked files match
# its commit: the words of commit_and_state in scripts/run-all-test-suites.py.
RUNNER_STATE_WHEN_TRACKED_FILES_MATCH = "tracked files match that commit"


def commit_named_for_the_record(checkout: Path, commit: str) -> str:
    """`commit <hash> ("<subject>")`, or the hash alone when git gives no
    subject."""
    subject = daily_full_test_run_of_main.git(checkout, "log", "-1", "--format=%s", commit)
    if subject.returncode != 0:
        return f"commit {commit}"
    return f'commit {commit} ("{subject.stdout.strip()}")'


def runner_named_for_the_record(runner: Path) -> str:
    """The runner's path and the commit of the checkout it sits in."""
    resolved = daily_full_test_run_of_main.git(
        runner.parent, "rev-parse", "--verify", "--quiet", "HEAD^{commit}")
    if resolved.returncode != 0 or not resolved.stdout.strip():
        return f"{runner}, in no git checkout"
    return f"{runner}, from {commit_named_for_the_record(runner.parent, resolved.stdout.strip())}"


def first_tracked_file_that_differs(checkout: Path):
    """(the first tracked file git lists as differing from the checkout's
    commit, or None when none does; why `git status` failed, or None). A
    change that is staged is listed as one that is not."""
    changed = daily_full_test_run_of_main.git(
        checkout, "status", "--porcelain", "--untracked-files=no")
    if changed.returncode != 0:
        return None, daily_full_test_run_of_main.first_stderr_line_or_no_detail(
            changed.stderr)
    if changed.stdout.strip():
        return changed.stdout.splitlines()[0][3:], None
    return None, None


def why_the_run_is_no_verdict_on_the_head(checkout: Path, head: str, completed) -> list:
    """Each reason the runner's finished run is no verdict on the head; none
    when it is one. See THE HEAD IS COMPARED THREE TIMES in the module
    docstring."""
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


def write_record_command(log_store_root: str, machine: str, file_name: str, run_name: str,
                         bytes_sent: int,
                         unless_the_record_there_started_no_earlier_than=None) -> str:
    """The shell command that writes the record from its stdin, replacing an
    earlier one of the same machine and head. It has two parts. The first
    takes what arrives on stdin into a file of the run's own in the record's
    directory, and counts its bytes: bytes_sent is how many the sender sends,
    and any other count is a record cut short, which is removed, with exit 1
    and the record there left as it was. The file is removed before the
    command says so on stderr: with no reader there, as when the ssh client
    has died, the shell is killed at that write and runs nothing after it.
    The second puts that whole file in place, today by renaming it over the
    record, so two writers at once leave one writer's whole record.

    Given a moment, as the record's first line spells its `started`, the
    command has two more parts between those, each run once the whole record
    has arrived: the form the remedy for a failed write is printed in. When
    the record it finds holds the same bytes as the record that arrived, it
    writes nothing, says on stdout that the record is written, and exits 0.
    Otherwise it reads the first line of the record it finds, and writes
    nothing and exits 1 unless the moment there is earlier. The same moment
    is not earlier, so the record of another run started in the same second
    stays. A record there whose first line gives no moment, an empty file
    among them, reads as earlier and is replaced. Each of the two removes the
    run's own file before it says anything, as the first part does.

    What this function adds to the command is ASCII: see THE RECORD in the
    module docstring."""
    directory = (f"{log_store_root}/{PULL_REQUEST_HEAD_TEST_RUNS_KIND_DIRECTORY_NAME}/"
                 f"{machine}")
    record = shlex.quote(f"{directory}/{file_name}")
    partial = shlex.quote(f"{directory}/.{file_name}.{run_name}.partial")
    cut_short = shlex.quote(
        f"{PROGRAM}: not written: {bytes_sent} bytes of the record were sent and another "
        f"count arrived.")
    run_again = shlex.quote("Run this command again.")
    # `wc -c` pads its count with spaces on macOS; -eq compares the numbers.
    # The `rm` comes before the first `echo`: see the docstring.
    take_the_whole_record = (
        f"cat > {partial} && {{ [ \"$(wc -c < {partial})\" -eq {int(bytes_sent)} ] || "
        f"{{ rm -f {partial}; echo {cut_short} >&2; echo {run_again} >&2; false; }}; }}")
    put_it_in_place = f"mv -f {partial} {record}"
    leave_the_record_there = ""
    if unless_the_record_there_started_no_earlier_than is not None:
        already_written = shlex.quote(
            f"{PROGRAM}: already written: the record there is the whole record of this "
            f"run, byte for byte.")
        tell_the_user = shlex.quote("Tell the user the record is written.")
        not_written = shlex.quote(
            f"{PROGRAM}: not written: the record there is of a run that started in the "
            f"same second or later.")
        instruction = shlex.quote("Leave that record as it is.")
        # The run's own record first, then a record that started no earlier.
        # Not `\>`: two runs started in one second spell `started` the same.
        leave_the_record_there = (
            f"if [ -e {record} ] && cmp -s {partial} {record}; then rm -f {partial}; "
            f"echo {already_written}; echo {tell_the_user}; exit 0; fi && "
            f"if [ -e {record} ] && ! [ \"$(sed -n '1s/^.*, started //p' {record})\" \\< "
            f"{shlex.quote(unless_the_record_there_started_no_earlier_than)} ]; then "
            f"rm -f {partial}; echo {not_written} >&2; echo {instruction} >&2; exit 1; "
            f"fi && ")
    return (f"mkdir -p {shlex.quote(directory)} && {take_the_whole_record} && "
            f"{leave_the_record_there}{put_it_in_place} || {{ rm -f {partial}; exit 1; }}")


def bytes_of_text_sent_to_a_command(text: str) -> int:
    """How many bytes run_on_ned_box_or_here sends for the text. It calls
    subprocess.run with text=True and no encoding, which encodes the text as
    locale.getpreferredencoding(False) names: UTF-8 on both machines, and
    under Python's UTF-8 mode."""
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

    # Each is one line of the record, and one refusal on stderr: what failed,
    # then the instruction.
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
    # Resolved here, in the directory this program was started in: the runner
    # is started in the checkout, where a relative path names the checkout's
    # own copy.
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
            "-j", daily.DAILY_FULL_TEST_RUN_SUITES_AT_ONCE, "--log-dir", str(logs)]
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
        f"{PROGRAM}: {machine}, started {started}",
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
    # See THE RECORD in the module docstring: the last line is the verdict.
    exit_code_once_the_record_is_written = (
        daily.EXIT_STEP_OF_THIS_PROGRAM_FAILED if steps_failed else completed.returncode)
    record_lines.append(f"{PROGRAM} exit code: {exit_code_once_the_record_is_written}")
    record = "\n".join(record_lines)

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
        arguments.log_store_root, machine, file_name, run_name,
        bytes_of_text_sent_to_a_command(record + "\n"))
    try:
        mark.run_on_ned_box_or_here(
            write_command, ssh_target, daily.DAILY_FULL_TEST_RUN_RECORD_WRITE_TIMEOUT_SECONDS,
            stdin_text=record + "\n")
    except mark.DailyMemoryReviewReadOrWriteFailed as error:
        # Printed to be run later, when another run of this head may have
        # written its record: see write_record_command.
        # Its stdin is the local copy, which is written as UTF-8.
        remedy_command = write_record_command(
            arguments.log_store_root, machine, file_name, run_name,
            len((record + "\n").encode("utf-8")),
            unless_the_record_there_started_no_earlier_than=started)
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
    """main's exit code, or the exit code for an uncaught exception after its
    traceback: see Exit codes in the module docstring."""
    try:
        return main(argv)
    except Exception:
        return exit_code_after_reporting_the_uncaught_exception()


if __name__ == "__main__":
    sys.exit(main_that_leaves_no_exception_uncaught())
