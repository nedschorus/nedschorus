#!/usr/bin/env python3
"""Remove a worktree once no program is writing a record in it: wait for every record's being-written lock to be released, ship the worktree's records to the log-store, then run `git worktree remove`.

Started, detached, by .claude/guard-hooks/git-worktree-remove-cold-read-record-and-sanity-check-record-ship-to-log-store-first-guard-hook.py
when it refuses a `git worktree remove` of a worktree in which a running
program, such as the cold-read-grid, holds a cold-read-record's or a
sanity-check record's being-written lock. The hook takes an flock on the
worktree's directory and passes its descriptor to this program, which keeps it
open until it exits, so while this program runs the hook starts no second one
for that worktree.

Its own `git worktree remove` does not pass through the hook, so it does the
hook's checks itself, using the hook's own functions:

1. It waits until no process holds the being-written lock of any record given
   by --record, checking every POLL_SECONDS.
2. For each record whose lock was released, it waits up to
   WRITER_OWN_SHIPMENT_GRACE_SECONDS for the store to hold the record whole,
   because a writer that ends normally releases the lock just before it ships
   the record itself, and a second shipment of the same record at the same
   moment can fail. A writer killed early never ships, and its record is
   shipped in step 3 once the grace runs out.
3. It ships every record in the worktree that the store does not hold whole,
   with the hook's shippers, as the hook does.
4. If a record in the worktree is being written by then, it goes back to step
   1 with those records.
5. It runs `git -C <--git-directory> worktree remove [-f] <worktree>`.

One limit, TOTAL_LIMIT_SECONDS, counts from this program's start across every
step. Each check of the log-store and each shipping pass runs in a thread of its
own, bounded by that limit in real seconds, so a call that stalls, as an ssh to
ned-box can on the Mac, ends the wait when the limit runs out; the stalled
thread is left to end with this program. It writes one line per step to its standard output, which the hook sends
to this run's log file in the log-store.

How it can fail: when the limit runs out, a shipment fails or git refuses, or
anything else raises, it leaves the worktree in place, writes a user-alert
naming the worktree, the records and what failed, and exits 1. A record
written after step 4's check and before git runs is deleted with the
worktree. This program killed, as by a reboot, leaves the worktree in place
and writes no alert. The user-alert is written under --ned-box-home, which on
the Mac is the mount of ned-box's home: while it is not mounted, the alert and
the log are lost, and the hook starts no waiter at all, since it cannot open
the log.

The user-alert follows
docs/nedschorus-wiki/nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md.
"""

import argparse
import importlib.util
import os
import socket
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
HOOK_SCRIPT = (REPOSITORY_ROOT / ".claude" / "guard-hooks"
               / "git-worktree-remove-cold-read-record-and-sanity-check-record-ship-to-log-store-first-guard-hook.py")

TOTAL_LIMIT_SECONDS = 50 * 60
POLL_SECONDS = 5
# A writer ships its record within seconds of releasing the lock on ned-box; from the Mac, over ssh, longer.
WRITER_OWN_SHIPMENT_GRACE_SECONDS = 120
GIT_TIMEOUT_SECONDS = 60

ALERT_TITLE_TEMPLATE = "A deferred `git worktree remove` did not run: {worktree}"
ALERT_TEXT_TEMPLATE = (
    "On {machine}, a `git worktree remove` of {worktree} was refused because a program was still writing "
    "a record in it. A second program, started to remove the worktree once its records were written and "
    "shipped to the log-store, has stopped without removing it, so the worktree is still there. Why it "
    "stopped: {failure}\n"
    "{records}"
    "The second program's log file: {log}")
GIT_WORKTREE_REMOVE_DEFERRED_FAILED_USER_ALERT_ACTION_TEXT_SAYING_WHAT_AN_AGENT_CAN_DO = (
    "An agent on that machine can tell from the failure above whether a record is still being written or "
    "did not ship, ship it with the cold-read-record-ship.py or sanity-check-record-ship.py command for its "
    "folder, and then run `git worktree remove` on the worktree by its absolute path.")
WAITER_TIME_LIMIT_RAN_OUT_USER_ALERT_FAILURE_SENTENCE = "its time limit ran out while these records were still being written."
RECORDS_NOT_SHIPPED_USER_ALERT_FAILURE_SENTENCE = "these records did not ship to the log-store."
LOG_STORE_CALL_TIME_LIMIT_RAN_OUT_USER_ALERT_FAILURE_SENTENCE = (
    "its time limit ran out while it was checking the log-store or shipping a record, as when an ssh to "
    "ned-box stalls.")
RECORDS_NOT_READ_FAILURE_TEMPLATE = "it could not read the worktree's records ({error})."
GIT_FAILURE_TEMPLATE = "`{command}` exited {code}: {error}"
UNEXPECTED_FAILURE_TEMPLATE = "the waiter stopped on an error: {error}"


def module_at(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def log(text):
    print(f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} {text}", flush=True)


def record_directory_being_written_lock_is_held_by_any_process(kinds, record):
    """True while a process holds the record's being-written lock; a record gone has none."""
    try:
        return kinds[record.parent.name][2].record_directory_being_written_lock_is_held_by_any_process(record)
    except FileNotFoundError:
        return False


class LogStoreCallTimeLimitRanOut(Exception):
    pass


def finished_by(wall_deadline, function, *arguments):
    """Return function(*arguments), run in a thread of its own; raise LogStoreCallTimeLimitRanOut when
    time.monotonic() reaches wall_deadline first, leaving the thread to end on its own."""
    outcome = {}

    def run():
        try:
            outcome["result"] = function(*arguments)
        except BaseException as error:
            outcome["error"] = error

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(max(0.0, wall_deadline - time.monotonic()))
    if thread.is_alive():
        raise LogStoreCallTimeLimitRanOut()
    if "error" in outcome:
        raise outcome["error"]
    return outcome["result"]


class WaiterFailed(Exception):
    def __init__(self, failure, records_text):
        super().__init__(failure)
        self.failure, self.records_text = failure, records_text


def being_written_lines(hook, worktree, records):
    return "".join(hook.RECORD_BEING_WRITTEN_LINE_TEMPLATE.format(record=record, worktree=worktree)
                   for record in records)


def wait_until_released_and_shipped_by_writer(hook, kinds, worktree, records, deadline, wall_deadline, clock,
                                              sleep, poll_seconds, grace_seconds):
    """Steps 1 and 2 for these records; raises WaiterFailed when the deadline passes first."""
    while any(record_directory_being_written_lock_is_held_by_any_process(kinds, record) for record in records):
        if clock() >= deadline:
            raise WaiterFailed(WAITER_TIME_LIMIT_RAN_OUT_USER_ALERT_FAILURE_SENTENCE,
                               being_written_lines(hook, worktree, records))
        sleep(poll_seconds)
    log("every listed record's being-written lock is released")
    grace_end = min(deadline, clock() + grace_seconds)
    waiting = [record for record in records if record.exists()]
    while waiting and clock() < grace_end:
        try:
            waiting = [record for record in waiting
                       if record.exists() and not finished_by(wall_deadline, hook.store_holds_every_file_of,
                                                              kinds[record.parent.name], record)]
        except LogStoreCallTimeLimitRanOut:
            raise WaiterFailed(LOG_STORE_CALL_TIME_LIMIT_RAN_OUT_USER_ALERT_FAILURE_SENTENCE,
                               being_written_lines(hook, worktree, records))
        if waiting:
            sleep(poll_seconds)
    if waiting:
        log(f"not shipped by their writers within {grace_seconds} seconds: {', '.join(map(str, waiting))}")


def ship_until_none_is_being_written(hook, kinds, worktree, records, deadline, wall_deadline, clock, sleep,
                                     poll_seconds, grace_seconds, runner):
    """Steps 1 to 4: return once every record in the worktree is shipped and none is being written."""
    while True:
        wait_until_released_and_shipped_by_writer(hook, kinds, worktree, records, deadline, wall_deadline, clock,
                                                  sleep, poll_seconds, grace_seconds)
        progress = {"shipped": set(), "lines": {}, "being_written": []}
        try:
            finished_by(wall_deadline, hook.ship_every_record, [worktree], runner, clock, deadline, progress)
        except LogStoreCallTimeLimitRanOut:
            raise WaiterFailed(LOG_STORE_CALL_TIME_LIMIT_RAN_OUT_USER_ALERT_FAILURE_SENTENCE,
                               being_written_lines(hook, worktree, records))
        if "error" in progress:
            raise WaiterFailed(RECORDS_NOT_READ_FAILURE_TEMPLATE.format(error=progress["error"]),
                               being_written_lines(hook, worktree, records))
        if progress["lines"]:
            raise WaiterFailed(RECORDS_NOT_SHIPPED_USER_ALERT_FAILURE_SENTENCE, "".join(hook.UNSHIPPED_RECORD_LINE_TEMPLATE.format(
                record=record, worktree=worktree, line=line,
                command=f"python3 {kinds[record.parent.name][1]} {record}")
                for record, line in progress["lines"].items()))
        log(f"shipped or already in the log-store: {len(progress['shipped'])} record(s)")
        if not progress["being_written"]:
            return
        records = [record for _, record in progress["being_written"]]
        log(f"still being written, waiting again: {', '.join(map(str, records))}")


def remove_worktree(worktree, git_directory, force, records_text, runner):
    command = ["git", "-C", str(git_directory), "worktree", "remove", *(["-f"] if force else []), str(worktree)]
    try:
        removal = runner(command, capture_output=True, text=True, timeout=GIT_TIMEOUT_SECONDS, check=False)
    except subprocess.TimeoutExpired:
        raise WaiterFailed(f"`{' '.join(command)}` ran past {GIT_TIMEOUT_SECONDS} seconds.", records_text)
    if removal.returncode != 0:
        error_lines = removal.stderr.strip().splitlines()
        raise WaiterFailed(GIT_FAILURE_TEMPLATE.format(
            command=" ".join(command), code=removal.returncode,
            error=error_lines[-1] if error_lines else "it printed nothing"), records_text)
    log(f"removed: {' '.join(command)}")


def user_alert_write(ned_box_home, worktree, failure, records_text, log_path):
    """Write the user-alert under ned_box_home, which the user-alerts module reads from HOME."""
    alerts = module_at(REPOSITORY_ROOT / "nc-systems" / "general-tools"
                       / "user-alerts-pending-and-claimed-files-write-claim-release-and-delete-common.py",
                       "user_alerts_pending_and_claimed_files_write_claim_release_and_delete_common")
    home_as_given = os.environ.get("HOME")
    os.environ["HOME"] = str(ned_box_home)
    try:
        return alerts.user_alert_write_to_pending(
            ALERT_TITLE_TEMPLATE.format(worktree=worktree),
            ALERT_TEXT_TEMPLATE.format(machine=socket.gethostname(), worktree=worktree, failure=failure,
                                       records=records_text, log=log_path),
            GIT_WORKTREE_REMOVE_DEFERRED_FAILED_USER_ALERT_ACTION_TEXT_SAYING_WHAT_AN_AGENT_CAN_DO)
    finally:
        if home_as_given is None:
            del os.environ["HOME"]
        else:
            os.environ["HOME"] = home_as_given


def main(argv=None, clock=time.monotonic, sleep=time.sleep, runner=subprocess.run, hook=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--worktree", type=Path, required=True, help="the worktree to remove, as an absolute path")
    parser.add_argument("--git-directory", type=Path, required=True,
                        help="a worktree of the same repository that git runs in")
    parser.add_argument("--force", action="store_true", help="remove with -f")
    parser.add_argument("--record", type=Path, action="append", default=[],
                        help="a record whose being-written lock to wait for; repeat for each")
    parser.add_argument("--ned-box-home", type=Path, required=True,
                        help="ned-box's home directory as this machine reaches it, where the user-alert goes")
    parser.add_argument("--log-file", default="", help="this run's log file, named in the user-alert")
    parser.add_argument("--total-limit-seconds", type=float, default=TOTAL_LIMIT_SECONDS)
    parser.add_argument("--poll-seconds", type=float, default=POLL_SECONDS)
    parser.add_argument("--writer-own-shipment-grace-seconds", type=float, default=WRITER_OWN_SHIPMENT_GRACE_SECONDS)
    arguments = parser.parse_args(argv)
    deadline = clock() + arguments.total_limit_seconds
    # The same limit in real seconds: an injected clock cannot bound a stalled call.
    wall_deadline = time.monotonic() + arguments.total_limit_seconds
    records_text = ""
    log(f"waiting to remove {arguments.worktree}{' with -f' if arguments.force else ''}; records: "
        + ", ".join(map(str, arguments.record)))
    try:
        hook = hook or module_at(HOOK_SCRIPT, "git_worktree_remove_records_ship_first_guard_hook")
        kinds = {kind[0]: kind for kind in hook.record_kinds()}
        records_text = being_written_lines(hook, arguments.worktree, arguments.record)
        ship_until_none_is_being_written(hook, kinds, arguments.worktree, arguments.record, deadline, wall_deadline,
                                         clock, sleep, arguments.poll_seconds,
                                         arguments.writer_own_shipment_grace_seconds, runner)
        remove_worktree(arguments.worktree, arguments.git_directory, arguments.force, records_text, runner)
        return 0
    except WaiterFailed as failed:
        failure, records_text = failed.failure, failed.records_text or records_text
    except Exception as error:
        traceback.print_exc(file=sys.stdout)
        failure = UNEXPECTED_FAILURE_TEMPLATE.format(error=f"{type(error).__name__}: {error}")
    log(f"FAILED, worktree left in place: {failure}")
    alert_id = user_alert_write(arguments.ned_box_home, arguments.worktree, failure, records_text,
                                arguments.log_file)
    log(f"user-alert written: {alert_id}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
