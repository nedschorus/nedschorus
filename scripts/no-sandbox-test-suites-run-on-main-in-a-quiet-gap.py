#!/usr/bin/env python3
"""Run the test suites that cannot run in a sandbox on main, in a quiet gap, and keep their result.

Usage:
  scripts/no-sandbox-test-suites-run-on-main-in-a-quiet-gap.py [seams below]
  scripts/no-sandbox-test-suites-run-on-main-in-a-quiet-gap.py --record-follow-up-request-sent
  scripts/no-sandbox-test-suites-run-on-main-in-a-quiet-gap.py --print-merge-gate-notice-of-last-failed-or-stopped-run

The design is GHI "Test suites that run without a sandbox leave per-change test
runs and run apart, when their own files change or in a quiet gap",
https://github.com/nedschorus/nedschorus/issues/2381, parts 2 and 4. A selective
run of scripts/run-all-test-suites.py leaves out every suite listed in its
SUITES_RUN_WITHOUT_ANY_SANDBOX, so this program is what runs them after a change
reaches main. It runs on ned-box under cron every 10 minutes.

WHAT ONE RUN DOES, in order:
  1. Takes its own lock, the state file's path with .lock added, without
     waiting; when another run holds it, exits 0.
  2. Reads the state file. A file that is missing or cannot be read counts as
     having no passing commit and no last run.
  3. Runs `git fetch origin` in the clone and resolves refs/remotes/origin/main.
  4. Exits 0 when no run is due. A run is due when there is no last run, the
     last run was at another commit, the last run stopped, or it failed more
     than RETRY_FAILED_RUN_AFTER_SECONDS ago.
  5. Takes the no-sandbox suites' lock in the runner's admission directory
     without waiting and releases it at once; when another run holds it, ned-box
     is not quiet, and this exits 0.
  6. Makes a detached worktree of that commit, removing first one a killed run
     left, and runs the worktree's runner once with --only-suites-named and the
     no-sandbox suites that worktree's runner lists, plus
     --only-suites-whose-recorded-inputs-changed-since <passing commit> when
     there is one. The runner gets RUNNER_TIMEOUT_SECONDS; past it, its
     process group gets SIGTERM, then SIGKILL after RUNNER_STOP_GRACE_SECONDS.
  7. Removes the worktree, writes the run's record to the log-store and the
     state file. Runner exit 0 is passed, and the commit becomes the passing
     commit; exit 1 is failed, with each suite the runner's FAIL lines name and
     its log copied beside the record; anything else is stopped, with the
     reason.

THE STATE FILE, written whole to a temporary file renamed into place:
  {"passing_commit": <hash or null>,
   "last_run": {"commit", "compared_with", "started", "ended", "result"
                ("passed", "failed" or "stopped"), "reason", "failing_suites":
                [{"suite", "log"}], "record", "follow_up_request_sent"}}
Times are UTC, as YYYY-MM-DDTHH:MM:SSZ.

THE RECORD, one file per run that reaches step 6:
  <log-store>/no-sandbox-test-suites-runs/<YYYY-MM-DD>/<HHMMSS>Z.txt
with each failing suite's log beside it as <HHMMSS>Z-<suite, / as __>.log.

--record-follow-up-request-sent writes the time into the last run, once
merge-lane-2 has sent the follow-up request for a failed or stopped run; it
refuses, exit 2, when the last run passed or there is none, or while a run holds
the program's lock, since that run rewrites the state file when it ends.

The runner is started with XDG_RUNTIME_DIR added as scripts/daily-full-test-run-of-main.py
adds it, because cron gives this program no user session bus.

--print-merge-gate-notice-of-last-failed-or-stopped-run prints, on stdout, the notice scripts/merge-gate.sh
puts on its stderr: nothing when the state file is missing or the last run
passed; for a failed run each failing suite, its log, the commit range and the
pull requests merged in it, read from the clone's first-parent merge commits;
for a stopped run its reason and record; for an unreadable state file, that.
After a follow-up was recorded, one line naming when.

EXIT. 0 the run finished, whatever the suites did, or no run was due, or
another run or a no-sandbox suite held its lock; 2 bad invocation or a refused
--record-follow-up-request-sent; 4 the run stopped: the fetch, the worktree, the
runner or a write failed, which the state file records where it can.

SCHEDULE. Installed on ned-box alone by
nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py, from the
table beside it, scheduled-jobs-on-each-machine.json:

    */10 * * * * /usr/bin/python3 /home/nedlern/Projects/nedschorus/scripts/no-sandbox-test-suites-run-on-main-in-a-quiet-gap.py >> /home/nedlern/.claude/no-sandbox-test-suites-run-on-main-in-a-quiet-gap.log 2>&1

What it does not handle: it sees only whether a no-sandbox suite holds the lock
at the moment it looks, not whether another run's suite is between two tries
for it; and a worktree a still-running runner from a killed run of this program
uses is removed under it, which can make that runner's suites fail.
"""

import argparse
import contextlib
import datetime
import fcntl
import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PROGRAM = "no-sandbox-test-suites-run-on-main-in-a-quiet-gap"
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_STATE_FILE = (Path.home() / ".local" / "state" / "nedschorus"
                      / f"{PROGRAM}.json")
DEFAULT_LOG_STORE_ROOT = "/home/nedlern/nedschorus-logs"
NO_SANDBOX_TEST_SUITES_RUNS_KIND_DIRECTORY_NAME = "no-sandbox-test-suites-runs"
RUNNER_PATH_IN_WORKTREE = Path("scripts") / "run-all-test-suites.py"

# Read at run time, so the tests can shorten them.
RETRY_FAILED_RUN_AFTER_SECONDS = 3600
RUNNER_TIMEOUT_SECONDS = 3600
RUNNER_STOP_GRACE_SECONDS = 60
GIT_FETCH_TIMEOUT_SECONDS = 300
GIT_READ_TIMEOUT_SECONDS = 60

EXIT_DONE = 0
EXIT_REFUSED = 2
EXIT_RUN_STOPPED_BY_A_FAILED_STEP = 4

RESULT_PASSED = "passed"
RESULT_FAILED = "failed"
RESULT_STOPPED = "stopped"

TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def module_loaded_by_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


git_redirecting_environment = module_loaded_by_path(
    "git_redirecting_environment_variables_removal_common",
    REPOSITORY_ROOT / "nc-systems" / "general-tools"
    / "git-redirecting-environment-variables-removal-common.py")


def runner_module():
    """scripts/run-all-test-suites.py beside this program, loaded by path when first needed,
    so --print-merge-gate-notice-of-last-failed-or-stopped-run, which the merge gate runs, never loads it."""
    spec = importlib.util.spec_from_file_location(
        "run_all_test_suites", Path(__file__).resolve().with_name("run-all-test-suites.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


def stamp(moment):
    return moment.strftime(TIME_FORMAT)


def parsed_stamp(text):
    return datetime.datetime.strptime(text, TIME_FORMAT).replace(tzinfo=datetime.timezone.utc)


class StateUnreadable(Exception):
    pass


def read_state(state_file):
    """The state as a dict; {} when the file is missing. Raises StateUnreadable otherwise."""
    try:
        text = Path(state_file).read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeDecodeError) as error:
        raise StateUnreadable(f"{state_file} could not be read: {error}") from error
    try:
        state = json.loads(text)
    except json.JSONDecodeError as error:
        raise StateUnreadable(f"{state_file} is not JSON: {error}") from error
    if not isinstance(state, dict) or not isinstance(state.get("last_run", {}), dict):
        raise StateUnreadable(f"{state_file} does not hold the state's fields")
    return state


def write_state(state_file, state):
    state_file = Path(state_file)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=state_file.parent, prefix=f".{state_file.name}.")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as written:
            json.dump(state, written, indent=2, sort_keys=True)
            written.write("\n")
        os.replace(temporary, state_file)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def take_lock_without_waiting(path):
    """An open handle holding an exclusive flock on path, or None when another holds it."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "a")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    return handle


def git(clone, *arguments, time_limit=None):
    """git's completed process; a run past its time limit reads as exit 124 with the reason."""
    limit = GIT_READ_TIMEOUT_SECONDS if time_limit is None else time_limit
    environment = git_redirecting_environment.environment_without_git_redirecting_variables()
    try:
        return subprocess.run(["git", "-C", str(clone), *arguments], env=environment,
                              stdin=subprocess.DEVNULL, capture_output=True, text=True,
                              errors="replace", timeout=limit, check=False)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            ["git", *arguments], 124, "", f"git {arguments[0]} ran past {limit:g} s")


def first_line(text):
    return (text.strip().splitlines() or ["no detail"])[0]


def run_is_due(state, commit, now):
    """Why a run is due, or None when it is not."""
    last = state.get("last_run")
    if not last:
        return "no run of these suites is recorded"
    if last.get("commit") != commit:
        return f"main moved to {commit[:12]} since the last run"
    if last.get("result") == RESULT_STOPPED:
        return "the last run stopped"
    if last.get("result") == RESULT_FAILED:
        try:
            ended = parsed_stamp(last.get("ended", ""))
        except ValueError:
            return "the last run failed, at a time that cannot be read"
        if (now - ended).total_seconds() > RETRY_FAILED_RUN_AFTER_SECONDS:
            return "the last run failed over an hour ago, and a failure may have passed"
    return None


def remove_worktree(clone, worktree):
    """None once the worktree is gone, or why it is not."""
    removed = git(clone, "worktree", "remove", "--force", str(worktree))
    if worktree.exists():
        shutil.rmtree(worktree, ignore_errors=True)
    git(clone, "worktree", "prune")
    if worktree.exists():
        return first_line(removed.stderr)
    return None


def runner_environment():
    """This process's environment, with XDG_RUNTIME_DIR added as the daily full run adds it,
    because cron starts this program without the user's session bus and the runner's
    `systemd-run --user --scope` then puts no CPU weight or memory ceiling on any suite."""
    daily = module_loaded_by_path("daily_full_test_run_of_main",
                                  Path(__file__).resolve().with_name("daily-full-test-run-of-main.py"))
    return daily.environment_with_user_runtime_directory_when_the_user_session_bus_exists(
        dict(os.environ))


def run_runner_with_time_limit(command, worktree):
    """(exit code or None when stopped at the time limit, stdout, stderr)."""
    process = subprocess.Popen(command, cwd=str(worktree), env=runner_environment(),
                               stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               errors="replace", start_new_session=True)
    try:
        out, err = process.communicate(timeout=RUNNER_TIMEOUT_SECONDS)
        return process.returncode, out, err
    except subprocess.TimeoutExpired:
        # The group may have ended between the time limit and the signal.
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
        try:
            out, err = process.communicate(timeout=RUNNER_STOP_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            out, err = process.communicate()
        return None, out, err


def failing_suites_and_logs(stdout, fail_prefix, log_mark):
    """[(suite, log path)] from the runner's FAIL lines that carry a log.

    The runner prints each failing suite twice: a progress line without a log, then one in
    its closing list with the log; only the second is read."""
    found = []
    for line in stdout.splitlines():
        if not line.startswith(fail_prefix) or log_mark not in line:
            continue
        rest = line[len(fail_prefix):]
        suite = rest.split(" ", 1)[0]
        found.append((suite, rest.split(log_mark, 1)[1].strip()))
    return found


def record_paths(log_store_root, started):
    directory = (Path(log_store_root) / NO_SANDBOX_TEST_SUITES_RUNS_KIND_DIRECTORY_NAME
                 / started.strftime("%Y-%m-%d"))
    return directory, directory / f"{started.strftime('%H%M%S')}Z.txt"


def write_record(log_store_root, started, last_run, stdout_tail, failing):
    """Write the record and copy each failing suite's log beside it; return the record's path."""
    directory, record = record_paths(log_store_root, started)
    directory.mkdir(parents=True, exist_ok=True)
    copied = []
    for suite, log in failing:
        target = directory / f"{record.stem}-{suite.replace('/', '__')}.log"
        try:
            shutil.copyfile(log, target)
            copied.append({"suite": suite, "log": str(target)})
        except OSError as error:
            copied.append({"suite": suite, "log": f"not copied from {log}: {error}"})
    lines = [f"{PROGRAM}: run of the no-sandbox test suites on main",
             f"commit tested: {last_run['commit']}",
             f"compared with the passing commit: {last_run.get('compared_with') or 'none'}",
             f"started: {last_run['started']}", f"ended: {last_run['ended']}",
             f"result: {last_run['result']}"]
    if last_run.get("reason"):
        lines.append(f"reason: {last_run['reason']}")
    for entry in copied:
        lines.append(f"failing suite: {entry['suite']} — log {entry['log']}")
    lines.append("runner's output:")
    lines.extend(stdout_tail)
    record.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(record), copied


def stopped(state_file, state, commit, started, reason, compared_with=None):
    """Record a stopped run where the state file can be written, print why, return EXIT_RUN_STOPPED_BY_A_FAILED_STEP."""
    print(f"{PROGRAM}: stopped — {reason}", file=sys.stderr)
    state = dict(state)
    state["last_run"] = {"commit": commit, "compared_with": compared_with,
                         "started": stamp(started), "ended": stamp(utc_now()),
                         "result": RESULT_STOPPED, "reason": reason, "failing_suites": [],
                         "record": None, "follow_up_request_sent": None}
    try:
        write_state(state_file, state)
    except OSError as error:
        print(f"{PROGRAM}: the state file {state_file} could not be written either: {error}",
              file=sys.stderr)
    return EXIT_RUN_STOPPED_BY_A_FAILED_STEP


def run(arguments):
    state_file = Path(arguments.state_file).expanduser()
    try:
        lock = take_lock_without_waiting(f"{state_file}.lock")
    except OSError as error:
        print(f"{PROGRAM}: stopped — its lock {state_file}.lock could not be taken: {error}",
              file=sys.stderr)
        return EXIT_RUN_STOPPED_BY_A_FAILED_STEP
    if lock is None:
        print(f"{PROGRAM}: another run holds {state_file}.lock; nothing to do")
        return EXIT_DONE
    try:
        return run_under_lock(arguments, state_file)
    finally:
        lock.close()


def run_under_lock(arguments, state_file):
    started = utc_now()
    try:
        state = read_state(state_file)
    except StateUnreadable as error:
        print(f"{PROGRAM}: {error}; it counts as empty", file=sys.stderr)
        state = {}
    clone = Path(arguments.clone)
    fetched = git(clone, "fetch", "origin", time_limit=GIT_FETCH_TIMEOUT_SECONDS)
    if fetched.returncode != 0:
        return stopped(state_file, state, None, started,
                       f"git fetch origin failed: {first_line(fetched.stderr)}")
    resolved = git(clone, "rev-parse", "--verify", "refs/remotes/origin/main^{commit}")
    if resolved.returncode != 0:
        return stopped(state_file, state, None, started,
                       f"origin/main could not be resolved: {first_line(resolved.stderr)}")
    commit = resolved.stdout.strip()
    why_due = run_is_due(state, commit, started)
    if why_due is None:
        print(f"{PROGRAM}: no run due at {commit[:12]}")
        return EXIT_DONE
    runner = runner_module()
    admission_directory = runner.test_suite_admission_directory_for_lock_file(
        Path(arguments.runner_lock_file).expanduser())
    quiet = take_lock_without_waiting(
        admission_directory / runner.SUITES_RUN_WITHOUT_ANY_SANDBOX_LOCK_FILE_NAME)
    if quiet is None:
        print(f"{PROGRAM}: a no-sandbox suite is running; ned-box is not quiet, so no run now")
        return EXIT_DONE
    quiet.close()
    print(f"{PROGRAM}: running, because {why_due}")
    passing = state.get("passing_commit")
    base = Path(arguments.temporary_directory) / PROGRAM
    worktree, log_dir = base / "worktree-of-main", base / "logs"
    base.mkdir(parents=True, exist_ok=True)
    if worktree.exists():
        leftover = remove_worktree(clone, worktree)
        if leftover is not None:
            return stopped(state_file, state, commit, started,
                           f"a worktree a killed run left at {worktree} could not be removed: "
                           f"{leftover}", passing)
    shutil.rmtree(log_dir, ignore_errors=True)
    added = git(clone, "worktree", "add", "--detach", str(worktree), commit)
    if added.returncode != 0:
        return stopped(state_file, state, commit, started,
                       f"the worktree of {commit[:12]} could not be made: "
                       f"{first_line(added.stderr)}", passing)
    try:
        try:
            lists, _ = runner.suite_sandbox_lists_read_from_checkout_under_test(worktree)
        except runner.CouldNotRun as refusal:
            return stopped(state_file, state, commit, started,
                           f"the no-sandbox suites could not be read: {first_line(str(refusal))}",
                           passing)
        suites = sorted(lists["SUITES_RUN_WITHOUT_ANY_SANDBOX"])
        runner_program = (Path(arguments.test_suite_runner_program)
                          if arguments.test_suite_runner_program
                          else worktree / RUNNER_PATH_IN_WORKTREE)
        command = [sys.executable, str(runner_program), "--checkout", str(worktree),
                   "--log-dir", str(log_dir), "--lock-file", str(arguments.runner_lock_file),
                   "--only-suites-named", *suites]
        if passing:
            command += ["--only-suites-whose-recorded-inputs-changed-since", passing]
        code, out, err = run_runner_with_time_limit(command, worktree)
    finally:
        left = remove_worktree(clone, worktree)
    if left is not None:
        print(f"{PROGRAM}: the worktree {worktree} could not be removed: {left}",
              file=sys.stderr)
    failing = []
    if code == runner.EXIT_ALL_PASSED:
        result, reason = RESULT_PASSED, None
    elif code == runner.EXIT_SOME_FAILED:
        result, reason = RESULT_FAILED, None
        failing = failing_suites_and_logs(out, runner.FAILED_SUITE_LINE_PREFIX,
                                          runner.SUITE_LINE_LOG_MARK)
    elif code is None:
        result, reason = RESULT_STOPPED, (f"the runner ran past {RUNNER_TIMEOUT_SECONDS:g} s "
                                          f"and was stopped")
    else:
        refusal = [line for line in err.splitlines() if line.strip()]
        result, reason = RESULT_STOPPED, (f"the runner exited {code}: "
                                          f"{refusal[0] if refusal else 'no detail'}")
    last_run = {"commit": commit, "compared_with": passing, "started": stamp(started),
                "ended": stamp(utc_now()), "result": result, "reason": reason,
                "failing_suites": [], "record": None, "follow_up_request_sent": None}
    tail = [line for line in out.splitlines()
            if line.startswith((runner.FAILED_SUITE_LINE_PREFIX,
                                runner.NOT_RUN_SUITE_LINE_PREFIX,
                                runner.SUMMARY_LINE_PREFIX))]
    try:
        record, copied = write_record(arguments.log_store_root, started, last_run, tail, failing)
    except OSError as error:
        return stopped(state_file, state, commit, started,
                       f"the record could not be written to the log-store: {error}", passing)
    last_run.update(record=record, failing_suites=copied)
    new_state = {"passing_commit": commit if result == RESULT_PASSED else passing,
                 "last_run": last_run}
    try:
        write_state(state_file, new_state)
    except OSError as error:
        print(f"{PROGRAM}: stopped — the state file {state_file} could not be written: {error}",
              file=sys.stderr)
        return EXIT_RUN_STOPPED_BY_A_FAILED_STEP
    print(f"{PROGRAM}: {result} at {commit[:12]}; record {record}")
    return EXIT_RUN_STOPPED_BY_A_FAILED_STEP if result == RESULT_STOPPED else EXIT_DONE


def record_follow_up_request_sent(arguments):
    """Under the run's own lock, so a run that ends meanwhile cannot have its result overwritten."""
    state_file = Path(arguments.state_file).expanduser()
    try:
        lock = take_lock_without_waiting(f"{state_file}.lock")
    except OSError as error:
        print(f"{PROGRAM}: the follow-up request was not recorded — the lock file "
              f"{state_file}.lock could not be opened: {error}.\n"
              f"If the error names a cause you can fix, such as a missing directory, fix it, "
              f"then run again: python3 scripts/{PROGRAM}.py --record-follow-up-request-sent\n"
              f"If you cannot fix it, or the rerun fails again, send agent-seat reboot-test "
              f"these lines with SendMessage, since it owns this program.", file=sys.stderr)
        return EXIT_REFUSED
    if lock is None:
        print(f"{PROGRAM}: the follow-up request was not recorded — a run of the test "
              f"suites that run without a sandbox holds {state_file}.lock, and that run "
              f"rewrites the state file when it ends.\n"
              f"Run again in 10 minutes: python3 scripts/{PROGRAM}.py "
              f"--record-follow-up-request-sent\n"
              f"While the run still holds the lock, this refusal repeats; once it ends, the "
              f"command records the follow-up if the run that held the lock failed or "
              f"stopped, and says no follow-up is owed if it passed.", file=sys.stderr)
        return EXIT_REFUSED
    try:
        return record_follow_up_request_sent_under_lock(state_file)
    finally:
        lock.close()


def record_follow_up_request_sent_under_lock(state_file):
    try:
        state = read_state(state_file)
    except StateUnreadable as error:
        print(f"{PROGRAM}: not recorded — {error}.\nThe next run of this program replaces "
              f"the file; there is no run to record a follow-up for until then.",
              file=sys.stderr)
        return EXIT_REFUSED
    last = state.get("last_run")
    if not last or last.get("result") not in (RESULT_FAILED, RESULT_STOPPED):
        print(f"{PROGRAM}: not recorded — the last run in {state_file} did not fail or stop, "
              f"so no follow-up request is owed.", file=sys.stderr)
        return EXIT_REFUSED
    last["follow_up_request_sent"] = stamp(utc_now())
    write_state(state_file, state)
    # A run stopped before it resolved main records commit null.
    print(f"{PROGRAM}: follow-up request recorded for the run at "
          f"{(last.get('commit') or 'no commit')[:12]}")
    return EXIT_DONE


MERGE_LINE = re.compile(r"^Merge pull request #(\d+)")


def pull_requests_merged_between(clone, older, newer):
    """['#N: subject'] from the first-parent merge commits in older..newer, or why not."""
    listed = git(clone, "log", "--first-parent", "--merges", "--format=%s%x09%b",
                 f"{older}..{newer}")
    if listed.returncode != 0:
        return [f"the merged pull requests could not be read: {first_line(listed.stderr)}"]
    found = []
    for entry in listed.stdout.split("\n"):
        subject = entry.split("\t", 1)[0]
        matched = MERGE_LINE.match(subject)
        if matched:
            found.append(f"#{matched.group(1)}")
    return found or ["none found"]


def merge_gate_notice(state_file, clone):
    """The notice's lines, or [] when there is nothing to say."""
    heading = f"NO-SANDBOX TEST SUITES ON MAIN ({PROGRAM}):"
    try:
        state = read_state(state_file)
    except StateUnreadable as error:
        return [heading, f"the state file cannot be read: {error}.",
                "Send reboot-test a follow-up request naming this line; it owns the runner."]
    last = state.get("last_run")
    if not last or last.get("result") == RESULT_PASSED:
        return []
    if last.get("follow_up_request_sent"):
        return [f"{heading} the {last.get('result')} run at {str(last.get('commit'))[:12]} "
                f"already has a follow-up request, sent {last['follow_up_request_sent']}."]
    done = (f"After sending it, run: python3 scripts/{PROGRAM}.py "
            f"--record-follow-up-request-sent")
    if last.get("result") == RESULT_STOPPED:
        lines = [heading, f"the last run, at {str(last.get('commit'))[:12]}, stopped: "
                          f"{last.get('reason')}"]
        if last.get("record"):
            lines.append(f"record: nedlern@ned-box:{last['record']}")
        return lines + ["Send reboot-test a follow-up request naming this run; it owns the "
                        "runner. " + done]
    lines = [heading, f"the last run, at {str(last.get('commit'))[:12]}, failed:"]
    for entry in last.get("failing_suites") or []:
        lines.append(f"  {entry.get('suite')} — log nedlern@ned-box:{entry.get('log')}")
    older, newer = last.get("compared_with"), last.get("commit")
    if older and newer:
        merged = pull_requests_merged_between(clone, older, newer)
        lines.append(f"range: {older[:12]}..{newer[:12]}, pull requests merged in it: "
                     f"{', '.join(merged)}")
        lines.append("Judge from the logs and those pull requests which change most likely "
                     "broke the suite, and send its author a follow-up request, as for a "
                     "non-blocking finding; when you cannot place it, send it to reboot-test. "
                     + done)
    else:
        lines.append("range: none, since no run has passed yet.")
        lines.append("Send reboot-test a follow-up request naming this run; it owns the runner. "
                     + done)
    return lines


def parse_arguments(argv):
    parser = argparse.ArgumentParser(prog=PROGRAM, description=__doc__.split("\n")[0])
    parser.add_argument("--clone", default=str(REPOSITORY_ROOT))
    parser.add_argument("--state-file", default=str(DEFAULT_STATE_FILE))
    parser.add_argument("--log-store-root", default=DEFAULT_LOG_STORE_ROOT)
    parser.add_argument("--temporary-directory", default=tempfile.gettempdir())
    parser.add_argument("--runner-lock-file",
                        default=str(Path.home() / ".claude" / ".run-all-test-suites.lock"))
    parser.add_argument("--test-suite-runner-program")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--record-follow-up-request-sent", action="store_true")
    mode.add_argument("--print-merge-gate-notice-of-last-failed-or-stopped-run", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    arguments = parse_arguments(argv)
    if arguments.record_follow_up_request_sent:
        return record_follow_up_request_sent(arguments)
    if arguments.print_merge_gate_notice_of_last_failed_or_stopped_run:
        for line in merge_gate_notice(Path(arguments.state_file).expanduser(),
                                      Path(arguments.clone)):
            print(line)
        return EXIT_DONE
    return run(arguments)


if __name__ == "__main__":
    sys.exit(main())
