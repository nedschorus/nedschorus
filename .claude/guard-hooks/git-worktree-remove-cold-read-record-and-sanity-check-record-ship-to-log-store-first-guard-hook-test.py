#!/usr/bin/env python3
"""Tests for git-worktree-remove-cold-read-record-and-sanity-check-record-ship-to-log-store-first-guard-hook.py,
and for the waiter it starts, nc-systems/general-tools/git-worktree-remove-deferred-until-cold-read-record-and-sanity-check-record-being-written-locks-release-then-ship-to-log-store-waiter.py.

The shipping cases run the hook end to end as a subprocess, the way Claude
Code does, on real git worktrees in a scratch directory, with the real
shippers pointed at a scratch log-store by COLD_READ_RECORD_SHIP_DESTINATION,
as the shippers' own tests do. A failed shipment is a stub ssh and rsync that
exit 255 first on PATH, with the destination given a host, so the shippers
take ned-box to be unreachable. The cases for a shipper that prints nothing,
a shipment past the hook's time limit, and a failing worktree listing inject
those failures in-process through main's runner and clock; the case for a
shipment that fails while main reads the worker's results also holds main's
copy of them until the worker has written. The command
reading cases call command_runs_git_worktree_remove in-process.

A record still being written is a second process holding its being-written
lock. In-process runs of main record each waiter start instead of starting
one, except in the deferred-removal cases, which start the real waiter,
detached, with a scratch ned-box home for its log and user-alert and short
waits; a writer that finishes, one killed early, git refusing the removal
(untracked files and no -f) and a second removal while the waiter waits each
run on a worktree of their own. The waiter's other failures are injected
in-process through its main.

Run: python3 .claude/guard-hooks/git-worktree-remove-cold-read-record-and-sanity-check-record-ship-to-log-store-first-guard-hook-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import atexit
import contextlib
import importlib.util
import io
import itertools
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

HOOK_SCRIPT = Path(__file__).with_name(
    "git-worktree-remove-cold-read-record-and-sanity-check-record-ship-to-log-store-first-guard-hook.py")

_spec = importlib.util.spec_from_file_location("git_worktree_remove_records_ship_first_guard_hook", HOOK_SCRIPT)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

_waiter_spec = importlib.util.spec_from_file_location(
    "git_worktree_remove_deferred_until_records_being_written_locks_release_waiter", hook.GIT_WORKTREE_REMOVE_DEFERRED_WAITER_SCRIPT)
waiter = importlib.util.module_from_spec(_waiter_spec)
_waiter_spec.loader.exec_module(waiter)

SHIP_DESTINATION_VARIABLE = "COLD_READ_RECORD_SHIP_DESTINATION"
# Any test run that reaches a shipper ships here, never into the real log-store.
# Resolved, because the hook names a worktree by its resolved path and the test sandbox's TMPDIR is a symlink.
_scratch = Path(tempfile.mkdtemp(prefix="git-worktree-remove-records-ship-first-test-")).resolve()
atexit.register(shutil.rmtree, _scratch, ignore_errors=True)
STORE = _scratch / "store"
os.environ[SHIP_DESTINATION_VARIABLE] = str(STORE / "cold-read-records")
# Where the deferred-removal cases' waiters write their logs and user-alerts, never the real ned-box home.
SCRATCH_NED_BOX_HOME = _scratch / "ned-box-home"
WAITER_LOGS = SCRATCH_NED_BOX_HOME / "nedschorus-logs" / hook.GIT_WORKTREE_REMOVE_DEFERRED_WAITER_LOG_STORE_DIRECTORY_NAME
PENDING_ALERTS = SCRATCH_NED_BOX_HOME / ".local" / "state" / "nedschorus" / "user-alerts" / "pending"
# Before anything runs git, so a run started with GIT_DIR or another redirecting variable set builds its
# scratch repositories here and not in the repository the variable names.
_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    HOOK_SCRIPT.resolve().parents[2] / "scripts" / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def git(directory, *arguments):
    subprocess.run(["git", "-C", str(directory), *arguments], check=True, capture_output=True, text=True)


def checkout_with_worktree(name):
    """Return (main checkout, worktree) under the scratch directory; the worktree holds one
    cold-read-record, one sanity-check record and an empty record directory."""
    parent = _scratch / name
    checkout = parent / "checkout"
    checkout.mkdir(parents=True)
    git(checkout, "init", "-q")
    git(checkout, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "init")
    worktree = parent / f"{name}-worktree"
    git(checkout, "worktree", "add", "-q", str(worktree))
    cold_read_record = worktree / "cold-read-records" / f"{name}-doc-2026-11-03"
    cold_read_record.mkdir(parents=True)
    (cold_read_record / "fast-read.md").write_text(f"{name} report\n")
    sanity_check_record = worktree / "sanity-check-records" / f"2026-11-03-{name}-doc"
    sanity_check_record.mkdir(parents=True)
    (sanity_check_record / "finding-dispositions.md").write_text(f"{name} dispositions\n")
    (worktree / "cold-read-records" / "empty-record").mkdir()
    return checkout, worktree


def run_hook_process(command, cwd, environment=None):
    """Run the hook as Claude Code does; return (exit code, parsed stdout or None, stderr)."""
    completed = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)], capture_output=True, text=True, timeout=300,
        env=environment, input=json.dumps({"tool_name": "Bash", "cwd": str(cwd),
                                           "tool_input": {"command": command}}))
    text = completed.stdout.strip()
    return completed.returncode, (json.loads(text) if text else None), completed.stderr


waiter_starts = []


def start_waiter_recorded(worktree, force, records, git_directory):
    waiter_starts.append((worktree, force, list(records), git_directory))
    return None


def run_hook(payload, runner=subprocess.run, clock=None, start_waiter=start_waiter_recorded):
    """Run main in-process; return (exit code, parsed stdout or None)."""
    stdout = io.StringIO()
    keywords = {"runner": runner, "start_waiter": start_waiter}
    if clock is not None:
        keywords["clock"] = clock
    with contextlib.redirect_stdout(stdout):
        code = hook.main(stdin=io.StringIO(payload if isinstance(payload, str) else json.dumps(payload)),
                         **keywords)
    text = stdout.getvalue().strip()
    return code, (json.loads(text) if text else None)


def refusal(output):
    if output is None:
        return None
    return output["hookSpecificOutput"].get("permissionDecisionReason")


def shippers_only(runner):
    """Return a runner that injects runner into shipper calls only; the worktree listing runs real git."""
    def runner_for_shippers(argv, **keywords):
        if argv[0] == "git":
            return subprocess.run(argv, **keywords)
        return runner(argv, **keywords)
    return runner_for_shippers


def runner_answering(returncode, stdout, stderr=""):
    def runner(argv, **keywords):
        return subprocess.CompletedProcess(argv, returncode, stdout, stderr)
    return runner


def runner_raising(error):
    def runner(argv, **keywords):
        raise error
    return runner


def payload_for(command, cwd):
    return {"tool_name": "Bash", "cwd": str(cwd), "tool_input": {"command": command}}


# The removed worktree's unshipped records reach the log-store before the removal, which is let through.
checkout, worktree = checkout_with_worktree("shipped")
other_worktree = checkout.parent / "shipped-other-worktree"
git(checkout, "worktree", "add", "-q", "--detach", str(other_worktree))
other_record = other_worktree / "cold-read-records" / "shipped-other-doc-2026-11-03"
other_record.mkdir(parents=True)
(other_record / "fast-read.md").write_text("other report\n")
cold_read_copy = STORE / "cold-read-records" / "shipped-doc-2026-11-03" / "fast-read.md"
sanity_check_copy = STORE / "sanity-check-records" / "2026-11-03-shipped-doc" / "finding-dispositions.md"
code, output, stderr = run_hook_process(f"git worktree remove {worktree}", checkout)
check("unshipped records reach the log-store and the removal is let through silently",
      code == 0 and output is None and cold_read_copy.is_file() and sanity_check_copy.is_file()
      and cold_read_copy.read_text() == "shipped report\n",
      (code, output, stderr, sorted(str(path) for path in STORE.rglob("*"))))
check("the records of a worktree the command does not name are not shipped",
      not (STORE / "cold-read-records" / other_record.name).exists())
check("an empty record directory is not shipped",
      not (STORE / "cold-read-records" / "empty-record").exists())
other_copy = STORE / "cold-read-records" / other_record.name / "fast-read.md"
code, output, stderr = run_hook_process(f"echo {other_worktree} | xargs git worktree remove", checkout)
check("a removal whose path reaches git only at run time, through xargs, ships every worktree's records",
      code == 0 and output is None and other_copy.is_file(), (code, output, stderr))
shutil.rmtree(STORE / "cold-read-records" / other_record.name)
code, output, stderr = run_hook_process("git worktree remove some-worktree", checkout)
check("a removal whose path names no worktree ships every worktree's records, not none",
      code == 0 and output is None and other_copy.is_file(), (code, output, stderr))

# A record the store already holds whole is skipped without running its shipper.
shipper_calls = []


def runner_recording_shipper_calls(argv, **keywords):
    shipper_calls.append(argv)
    return subprocess.run(argv, **keywords)


code, output = run_hook(payload_for(f"git worktree remove {worktree}", checkout),
                        shippers_only(runner_recording_shipper_calls))
check("records the store already holds are not shipped again, and the removal is let through",
      code == 0 and output is None and shipper_calls == [], (code, output, shipper_calls))
(worktree / "cold-read-records" / "shipped-doc-2026-11-03" / "cold-read-triage.md").write_text("ruled\n")
code, output = run_hook(payload_for(f"git worktree remove {worktree}", checkout),
                        shippers_only(runner_recording_shipper_calls))
check("a record with a file the store lacks is shipped",
      code == 0 and output is None and len(shipper_calls) == 1
      and (STORE / "cold-read-records" / "shipped-doc-2026-11-03" / "cold-read-triage.md").is_file(),
      (code, output, shipper_calls))

# A failed shipment refuses the removal, naming each record, its worktree and the command that ships it again.
checkout, worktree = checkout_with_worktree("unreachable")
stubs = _scratch / "unreachable-stubs"
stubs.mkdir()
for tool in ("ssh", "rsync"):
    (stubs / tool).write_text("#!/bin/sh\nexit 255\n")
    (stubs / tool).chmod(0o755)
unreachable_environment = dict(os.environ)
unreachable_environment[SHIP_DESTINATION_VARIABLE] = "nedlern@ned-box:/nonexistent-test-log-store/cold-read-records"
unreachable_environment["PATH"] = f"{stubs}{os.pathsep}{os.environ['PATH']}"
code, output, stderr = run_hook_process(f"git worktree remove {worktree}", checkout, unreachable_environment)
reason = refusal(output) or ""
cold_read_record = worktree / "cold-read-records" / "unreachable-doc-2026-11-03"
sanity_check_record = worktree / "sanity-check-records" / "2026-11-03-unreachable-doc"
cold_read_rerun = f"python3 {hook.REPOSITORY_ROOT}/nc-systems/cold-read/cold-read-record-ship.py {cold_read_record}"
sanity_check_rerun = f"python3 {hook.REPOSITORY_ROOT}/scripts/sanity-check-record-ship.py {sanity_check_record}"
check("a failed shipment refuses the removal",
      code == 0 and output["hookSpecificOutput"]["permissionDecision"] == "deny", (code, output, stderr))
check("the refusal opens by saying it refused on purpose, that the removed worktree's records are shipped, and how "
      "many failed",
      reason.startswith("Refused on purpose: before a `git worktree remove`, this hook ships the cold-read-records "
                        "and sanity-check records of the worktree it removes to the log-store, and 2 "
                        "record(s) did not reach it."), reason)
check("a removal the hook placed gets no instruction to write its path out", "Run the removal again" not in reason,
      reason)
check("the refusal names each record and its worktree with the shipper's own FAILED line",
      f"Record {cold_read_record} (worktree {worktree}): FAILED:" in reason
      and f"Record {sanity_check_record} (worktree {worktree}): FAILED:" in reason
      and "could not reach the log-store" in reason, reason)
check("the refusal gives each record's ship command",
      f"  Shipped with: {cold_read_rerun}\n" in reason and f"  Shipped with: {sanity_check_rerun}\n" in reason,
      reason)
for line in (f"If a Record line says the log-store or ned-box could not be reached, leave the worktree in place, "
             f"stop, and {hook.TELL_THE_USER_OR_DISPATCHING_AGENT} that `git worktree remove` is refused because "
             f"records could not be shipped to the log-store, quoting each Record line above word for word.",
             "If a Record line gives an `mv` to a free name and its worktree is one your agent-seat made or owns, "
             "run that `mv`; you need not run the \"Shipped with\" commands, because this hook runs them itself. "
             "Then run your `git worktree remove` command again, once.",
             "If a Record line's worktree belongs to another agent-seat, leave that record as it is, stop, and "
             f"{hook.TELL_THE_USER_OR_DISPATCHING_AGENT} that `git worktree remove` is refused until that record "
             "is renamed and shipped, quoting its Record line word for word.",
             f"If this hook refuses your command again, leave the worktree in place, stop, and "
             f"{hook.TELL_THE_USER_OR_DISPATCHING_AGENT} that `git worktree remove` is refused because records "
             f"could not be shipped to the log-store, quoting each Record line of the second refusal word for "
             f"word."):
    check(f"the refusal carries the instruction {line[:50]!r}...", line in reason, reason)
check("the refused removal leaves the records in place", cold_read_record.is_dir() and sanity_check_record.is_dir())

# Run again once ned-box can be reached, the removal ships the records and is let through.
code, output, stderr = run_hook_process(f"git worktree remove {worktree}", checkout)
check("the removal run again ships the records and is let through",
      code == 0 and output is None
      and (STORE / "cold-read-records" / cold_read_record.name / "fast-read.md").is_file()
      and (STORE / "sanity-check-records" / sanity_check_record.name / "finding-dispositions.md").is_file(),
      (code, output, stderr))
reruns = [subprocess.run(rerun.split(), capture_output=True, text=True, check=False)
          for rerun in (cold_read_rerun, sanity_check_rerun)]
check("each ship command the refusal gives runs and ships its record",
      all(rerun.returncode == 0 and rerun.stdout.startswith("shipped:") for rerun in reruns),
      [(rerun.returncode, rerun.stdout, rerun.stderr) for rerun in reruns])

# A record whose name the store holds with other content is refused by the real shipper: removing its worktree is
# refused, quoting the shipper's mv, and removing another worktree goes ahead without touching it.
checkout, worktree = checkout_with_worktree("clash")
clash_other_worktree = checkout.parent / "clash-other-worktree"
git(checkout, "worktree", "add", "-q", "--detach", str(clash_other_worktree))
clash_record = worktree / "cold-read-records" / "clash-doc-2026-11-03"
clashing_store_copy = STORE / "cold-read-records" / "clash-doc-2026-11-03"
clashing_store_copy.mkdir(parents=True)
(clashing_store_copy / "fast-read.md").write_text("another read's report\n")
code, output, stderr = run_hook_process(f"git worktree remove {worktree}", checkout)
reason = refusal(output) or ""
check("a record the shipper refuses refuses the removal of its worktree, quoting the shipper's mv",
      f"Record {clash_record} (worktree {worktree}): REFUSED:" in reason
      and "`mv " in reason and "clash-doc-2026-11-03-2" in reason, (code, output, stderr))
code, output, stderr = run_hook_process(f"git worktree remove {clash_other_worktree}", checkout)
check("removing another worktree goes ahead while a record the log-store refuses is in the first",
      code == 0 and output is None
      and (clashing_store_copy / "fast-read.md").read_text() == "another read's report\n", (code, output, stderr))
code, output, stderr = run_hook_process('git worktree remove -f "$W"', checkout)
reason = refusal(output) or ""
check("a removal the hook cannot place is refused while any worktree holds a record the log-store refuses, saying "
      "it shipped every worktree's records",
      reason.startswith("Refused on purpose: before a `git worktree remove`, this hook ships the cold-read-records "
                        "and sanity-check records of the worktree it removes to the log-store; it could not tell "
                        "which worktree this command removes (the path $W holds a variable, a glob or a "
                        "substitution), so it shipped the records of every worktree of this repository, and 1 "
                        "record(s) did not reach it.")
      and f"Record {clash_record} (worktree {worktree}): REFUSED:" in reason, (code, output, stderr))
check("that refusal asks for the removal again with its path written out, keeping -f",
      "If the worktree you remove is not one that a Record line above names, do not follow the lines below; "
      "instead: Run the removal again as `git worktree remove -f <path>`, with the worktree's path written out in "
      "full, as an absolute path with no variable, in a command that does not change directory. This hook then "
      "ships and checks only that worktree's records.\n" in reason, reason)
subprocess.run(["mv", str(clash_record), str(worktree / "cold-read-records" / "clash-doc-2026-11-03-2")], check=True)
code, output, stderr = run_hook_process('git worktree remove "$W"', checkout)
check("once the refused record is renamed as the refusal says, a removal the hook cannot place ships every "
      "worktree's records and is let through",
      code == 0 and output is None
      and (STORE / "cold-read-records" / "clash-doc-2026-11-03-2" / "fast-read.md").read_text()
      == "clash report\n"
      and (STORE / "sanity-check-records" / "2026-11-03-clash-doc" / "finding-dispositions.md").is_file(),
      (code, output, stderr))

# A worktree with no records is let through silently, without running a shipper.
checkout, worktree = checkout_with_worktree("no-records")
shutil.rmtree(worktree / "cold-read-records")
shutil.rmtree(worktree / "sanity-check-records")
shipper_calls.clear()
code, output = run_hook(payload_for(f"git worktree remove {worktree}", checkout),
                        shippers_only(runner_recording_shipper_calls))
check("a repository whose worktrees hold no records is let through silently, with no shipper run",
      code == 0 and output is None and shipper_calls == [], (code, output, shipper_calls))

# A shipper that exits 0 but prints nothing, or exits nonzero, refuses the removal.
checkout, worktree = checkout_with_worktree("injected")
payload = payload_for(f"git worktree remove {worktree}", checkout)
code, output = run_hook(payload, shippers_only(runner_answering(0, "")))
check("a shipper that exits 0 and prints nothing refuses the removal, with its exit code",
      "Record " in (refusal(output) or "") and ": the shipper printed nothing (exit 0)\n" in refusal(output),
      output)
code, output = run_hook(payload, shippers_only(runner_answering(1, "", "Traceback ...\nOSError: disk full\n")))
check("a shipper that dies printing nothing refuses the removal, with its last stderr line",
      ": the shipper printed nothing (exit 1): OSError: disk full\n" in (refusal(output) or ""), output)
code, output = run_hook(payload, shippers_only(
    runner_answering(2, "REFUSED: x — already in the store with different content")))
check("a shipper's REFUSED line refuses the removal and is quoted",
      ": REFUSED: x — already in the store with different content\n" in (refusal(output) or ""), output)
code, output = run_hook(payload, shippers_only(runner_answering(-9, "shipped: x — 1 file added")))
check("a shipper killed by a signal refuses the removal, though it printed shipped:",
      "Refused on purpose:" in (refusal(output) or ""), output)
code, output = run_hook(payload, shippers_only(runner_answering(0, "shipped: x — 1 file added")))
check("shippers that print shipped: let the removal through", code == 0 and output is None, output)


# The time limit: a shipper still running when it runs out, and records it never reached, refuse.
def runner_timing_out(argv, **keywords):
    raise subprocess.TimeoutExpired(argv, keywords.get("timeout"))


budget_line = f"not shipped: this hook's limit of {hook.SHIPPING_BUDGET_SECONDS} seconds for shipping ran out first"
code, output = run_hook(payload, shippers_only(runner_timing_out))
check("a shipper past the time limit refuses the removal",
      (refusal(output) or "").count(f": {budget_line}\n") == 2, output)
# Clock reads: the deadline; the first record before and after its store check; the second record.
times = itertools.chain([0, 0, 0], itertools.repeat(hook.SHIPPING_BUDGET_SECONDS))
timeouts_given = []


def runner_recording_timeout(argv, **keywords):
    timeouts_given.append(keywords.get("timeout"))
    return subprocess.CompletedProcess(argv, 0, "shipped: x", "")


code, output = run_hook(payload, shippers_only(runner_recording_timeout), clock=lambda: next(times))
check("a record reached after the time limit ran out is not shipped and refuses the removal",
      timeouts_given == [hook.SHIPPING_BUDGET_SECONDS]
      and (refusal(output) or "").count(f": {budget_line}\n") == 1
      and "and 1 record(s) did not reach it" in refusal(output), (timeouts_given, output))

shipped_runner = shippers_only(runner_answering(0, "shipped: x — 1 file added"))
store_check_as_written = hook.store_holds_every_file_of


def run_with_store_check(store_check, hook_payload):
    hook.store_holds_every_file_of = store_check
    try:
        return run_hook(hook_payload, shipped_runner)
    finally:
        hook.store_holds_every_file_of = store_check_as_written


# A record that another agent-session removes while the hook checks it has nothing left to ship.
def store_check_after_the_record_vanishes(kind, record):
    shutil.rmtree(record)
    raise FileNotFoundError(2, "No such file or directory", str(record / "fast-read.md"))


vanishing_checkout, vanishing_worktree = checkout_with_worktree("vanishing")
code, output = run_with_store_check(
    store_check_after_the_record_vanishes,
    payload_for(f"git worktree remove {vanishing_worktree}", vanishing_checkout))
check("a record that vanishes while the hook checks it is skipped, and the removal is let through silently",
      code == 0 and output is None, output)
check("records_in leaves out a worktree that has vanished",
      hook.records_in(_scratch / "gone", hook.record_kinds()) == [])
all_kinds = hook.record_kinds()
not_a_folder_worktree = _scratch / "records-folder-is-a-file"
not_a_folder_worktree.mkdir()
(not_a_folder_worktree / all_kinds[0][0]).write_text("not a folder\n")
(not_a_folder_worktree / all_kinds[1][0] / "kept-record").mkdir(parents=True)
(not_a_folder_worktree / all_kinds[1][0] / "kept-record" / "report.md").write_text("kept\n")
check("records_in leaves out a records folder that is a file, and still reads the other records folder",
      [record.name for _, record in hook.records_in(not_a_folder_worktree, all_kinds)] == ["kept-record"])


class ListedRecord:
    """A record directory as listed; one that vanished raises when its contents are read."""

    def __init__(self, name, vanished):
        self.name, self.vanished = name, vanished

    def is_dir(self):
        return True

    def is_symlink(self):
        return False

    def iterdir(self):
        if self.vanished:
            raise FileNotFoundError(2, "No such file or directory", self.name)
        return iter(["report.md"])

    def __lt__(self, other):
        return self.name < other.name


class WorktreeListingAVanishingRecord:
    def __truediv__(self, name):
        return self

    def iterdir(self):
        return iter([ListedRecord("a-vanished-record", True), ListedRecord("b-kept-record", False)])


check("records_in leaves out a record that vanishes between its listing and its reading, and reads the next",
      [record.name for _, record in hook.records_in(WorktreeListingAVanishingRecord(), all_kinds[:1])]
      == ["b-kept-record"])


def store_check_failing(kind, record):
    raise PermissionError(13, "Permission denied", str(record))


code, output = run_with_store_check(store_check_failing, payload)
check("an error checking a record that is still there refuses the removal, naming the error",
      (refusal(output) or "").count(": not shipped: this hook could not check or ship it: PermissionError: ") == 2,
      output)


# A stalled store check, as an ssh to ned-box that never answers, is cut off by the one deadline.
def store_check_stalling(kind, record):
    time.sleep(60)
    return True


budget_as_written = hook.SHIPPING_BUDGET_SECONDS
hook.SHIPPING_BUDGET_SECONDS = 1
try:
    started = time.monotonic()
    code, output = run_with_store_check(store_check_stalling, payload)
    took = time.monotonic() - started
    check("a stalled store check refuses the removal at the deadline, naming every record not yet shipped",
          took < 10 and (refusal(output) or "").count(
              ": not shipped: this hook's limit of 1 seconds for shipping ran out first\n") == 2, (took, output))
finally:
    hook.SHIPPING_BUDGET_SECONDS = budget_as_written

# A shipment that fails just after the deadline, while the main thread is reading what the worker wrote,
# still refuses: the main thread's copy is held until the worker has written that record's failure.
late_checkout, late_worktree = checkout_with_worktree("late-failure")
shutil.rmtree(late_worktree / "sanity-check-records")
late_record = late_worktree / "cold-read-records" / "late-failure-doc-2026-11-03"
main_thread_reading = threading.Event()
worker_finished = threading.Event()
ship_every_record_as_written = hook.ship_every_record


def shipper_failing_once_the_main_thread_reads(argv, **keywords):
    main_thread_reading.wait(10)
    return subprocess.CompletedProcess(argv, 1, "FAILED: ned-box could not be reached", "")


def ship_every_record_then_say_so(*arguments):
    try:
        ship_every_record_as_written(*arguments)
    finally:
        worker_finished.set()


def set_copied_after_the_worker_writes(*arguments):
    if arguments:
        main_thread_reading.set()
        worker_finished.wait(10)
    return set(*arguments)


hook.SHIPPING_BUDGET_SECONDS = 1
hook.store_holds_every_file_of = lambda kind, record: False
hook.ship_every_record = ship_every_record_then_say_so
hook.set = set_copied_after_the_worker_writes
try:
    code, output = run_hook(payload_for(f"git worktree remove {late_worktree}", late_checkout),
                            shippers_only(shipper_failing_once_the_main_thread_reads))
finally:
    hook.SHIPPING_BUDGET_SECONDS = budget_as_written
    hook.store_holds_every_file_of = store_check_as_written
    hook.ship_every_record = ship_every_record_as_written
    del hook.set
    main_thread_reading.set()
check("a shipment that fails while the main thread reads the worker's results at the deadline refuses the removal",
      "and 1 record(s) did not reach it" in (refusal(output) or "")
      and f"Record {late_record} (worktree {late_worktree}): FAILED: ned-box could not be reached\n"
      in refusal(output), output)

# The worker failing before it has read the records lets the command through with the not-checked notice.
record_kinds_as_written = hook.record_kinds


def record_kinds_failing():
    raise ImportError("shipper module missing")


hook.record_kinds = record_kinds_failing
try:
    code, output = run_hook(payload, shipped_runner)
finally:
    hook.record_kinds = record_kinds_as_written
specific = (output or {}).get("hookSpecificOutput", {})
check("records that cannot be read let the command through with the not-checked notice and its reason",
      code == 0 and "permissionDecision" not in specific
      and specific.get("additionalContext", "").startswith(
          hook.RECORDS_NOT_READ_NOTICE.split("({reason})")[0] + "(ImportError: shipper module missing)"),
      output)

# A worktree listing that fails, cannot run or runs out of time lets the command through with a notice.
not_checked_opening = ("Not checked: the hook that ships a worktree's cold-read-records and sanity-check "
                       "records to the log-store before `git worktree remove` removes it could not list this "
                       "repository's worktrees (")
for name, runner, said in (
        ("exits nonzero", runner_answering(128, b"", b"fatal: not a git repository\n"),
         "`git worktree list` exited 128: fatal: not a git repository"),
        ("is killed by a signal", runner_answering(-9, b"worktree /x\0\0", b"warning: first\nkilled: last\n"),
         "`git worktree list` exited -9: killed: last"),
        ("exits nonzero and says nothing", runner_answering(1, b"", b""), "`git worktree list` exited 1"),
        ("cannot run", runner_raising(OSError("no git")), "`git worktree list` could not run: no git"),
        ("runs out of time", runner_raising(subprocess.TimeoutExpired("git", hook.GIT_TIMEOUT_SECONDS)),
         f"`git worktree list` ran past {hook.GIT_TIMEOUT_SECONDS} seconds")):
    code, output = run_hook(payload_for("git worktree remove wt", "/nonexistent"), runner)
    specific = (output or {}).get("hookSpecificOutput", {})
    notice = specific.get("additionalContext", "")
    check(f"a worktree listing that {name} lets the command through with the not-checked notice and its reason",
          code == 0 and "permissionDecision" not in specific and notice.startswith(not_checked_opening + said + ")")
          and hook.SHIP_RECORDS_YOURSELF_NEXT_STEP_LINES in notice, output)
code, output = run_hook(payload_for("git worktree remove wt", _scratch / "not-a-repository-at-all"))
check("a hook run outside any repository lets the command through with the not-checked notice",
      code == 0 and (output or {}).get("hookSpecificOutput", {}).get("additionalContext", "")
      .startswith(not_checked_opening + "`git worktree list` exited "), output)

# Reading the command: whether it runs git worktree remove.
for command, expected in (
        ("git worktree remove wt", True),
        ("git worktree remove --force wt", True),
        ("cd /x && git worktree remove wt", True),
        ("git -C /repo worktree remove wt", True),
        ("git --git-dir ~/r/.git -c a=b worktree remove wt", True),
        ("env -C /repo git worktree remove wt", True),
        ("timeout 60 git worktree remove wt", True),
        ('W=/a/wt; git worktree remove "$W"', True),
        ("for w in a b; do git worktree remove $w; done", True),
        ("cd $(pwd)/x && cd .. && git worktree remove wt", True),
        ("bash -c 'git worktree remove wt'", True),
        ("sh -c \"cd /x; git worktree remove wt\"", True),
        ("git worktree list", False),
        ("git worktree add wt", False),
        ("echo git worktree remove wt", False),
        ("git log --grep 'worktree remove'", False),
        ("ssh host git worktree remove wt", False),
        ("ls", False)):
    check(f"{command!r} {'runs' if expected else 'does not run'} git worktree remove",
          hook.command_runs_git_worktree_remove(command) == expected)

# Reading the command: whether a removal in it gives -f or --force.
for command, expected in (
        ("git worktree remove -f wt", True),
        ("git -C /r worktree remove --force wt", True),
        ("bash -c 'git worktree remove -f \"$W\"'", True),
        ("git worktree remove wt", False),
        ("git worktree remove -- -f", False),
        ("rm -f x && git worktree remove wt", False)):
    check(f"{command!r} {'gives' if expected else 'does not give'} a removal -f or --force",
          hook.shell_command_runs_git_worktree_remove_with_force_option(command) == expected)

for command, expected in (
        ("git worktree remove -f /wt", True),
        ("env X=1 git -C /r worktree remove /wt;", True),
        ("git worktree remove /wt  # a comment", True),
        ("git worktree remove /wt 2>&1", False),
        ("! git worktree remove /wt", False),
        ("cd /r; git worktree remove /wt", False),
        ("(git worktree remove /wt)", False),
        ("git worktree remove $(echo /wt)", False),
        ("git worktree remove /wt )", False),
        ("ls /wt", False)):
    check(f"{command!r} {'is' if expected else 'is not'} one git worktree remove and nothing else",
          hook.shell_command_is_one_git_worktree_remove_and_nothing_else(command) == expected)
parser_as_written = hook.shell_reader.parser


def parser_only_in_a_new_process():
    raise hook.shell_reader.ShellParserInstalledForANewProcess("tree-sitter-bash installed for a new process")


hook.shell_reader.parser = parser_only_in_a_new_process
try:
    alone_without_tree = hook.shell_command_is_one_git_worktree_remove_and_nothing_else("git worktree remove -f /wt")
finally:
    hook.shell_reader.parser = parser_as_written
check("without a syntax tree in this process, no removal counts as the whole command, so none is deferred",
      alone_without_tree is False, alone_without_tree)

# A slow shipment must be refused by the hook, not cut off by Claude Code, which lets the command through.
settings = json.loads((hook.REPOSITORY_ROOT / ".claude" / "settings.json").read_text())
hook_timeouts = [entry.get("timeout") for group in settings["hooks"]["PreToolUse"] for entry in group["hooks"]
                 if HOOK_SCRIPT.name in entry.get("command", "")]
check("the hook's timeout in .claude/settings.json exceeds its shipping limit plus its worktree listing",
      len(hook_timeouts) == 1 and isinstance(hook_timeouts[0], (int, float))
      and hook_timeouts[0] > hook.SHIPPING_BUDGET_SECONDS + hook.GIT_TIMEOUT_SECONDS, hook_timeouts)

for shipper in ("nc-systems/cold-read/cold-read-record-ship.py", "scripts/sanity-check-record-ship.py"):
    usage = subprocess.run([sys.executable, str(hook.REPOSITORY_ROOT / shipper), "--help"],
                           capture_output=True, text=True, check=False)
    check(f"{shipper}, which the ship-them-yourself lines name, takes --all",
          f"python3 {shipper} --all" in hook.SHIP_RECORDS_YOURSELF_NEXT_STEP_LINES and "--all" in usage.stdout,
          (usage.returncode, usage.stdout[-300:], usage.stderr))

check("a command with no removal is let through", run_hook(payload_for("ls", "/work")) == (0, None))
check("another tool is let through", run_hook({"tool_name": "Write", "tool_input": {"file_path": "x"}}) == (0, None))
check("unreadable hook input is let through", run_hook("not json") == (0, None))

# The shell reader cannot run: the command is let through, and the agent is told what to do.
readings_as_written = hook.shell_reader.simple_commands


def unavailable(command, *arguments):
    raise hook.shell_reader.ShellParserUnavailable("tree-sitter-bash missing")


hook.shell_reader.simple_commands = unavailable
try:
    code, output = run_hook(payload_for("git worktree remove wt", "/work"))
finally:
    hook.shell_reader.simple_commands = readings_as_written
specific = (output or {}).get("hookSpecificOutput", {})
check("when the shell reader cannot run, the command is let through with the next steps",
      code == 0 and "permissionDecision" not in specific
      and hook.PARSER_UNAVAILABLE_NEXT_STEP_LINES in specific.get("additionalContext", ""), output)

# Every shipper the hook loads can tell a record still being written: an AttributeError here would be
# reported for every record as "could not check or ship it" and refuse every removal.
for kind in hook.record_kinds():
    check(f"the store logic for {kind[0]} can tell a record still being written",
          callable(getattr(kind[2], "record_directory_being_written_lock_is_held_by_any_process", None)))

# A record a running program is still writing, such as a cold-read-grid's, is never shipped by the hook:
# the program rewrites files it has written, and ships the record itself when it finishes. Its lock is held
# here by a second process through the shipper's own function, as the grid takes it. When stdin closes, the
# writer finishes: with "finish-and-ship" as its third argument it first writes one more file, releases the
# lock and ships the record itself, as the grid does.
COLD_READ_RECORD_BEING_WRITTEN_LOCK_HOLDER_UNTIL_STDIN_CLOSES_PYTHON_SOURCE = """
import importlib.util, pathlib, subprocess, sys
spec = importlib.util.spec_from_file_location("shipper", sys.argv[1])
shipper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shipper)
record = pathlib.Path(sys.argv[2])
shipper.record_directory_being_written_lock_take(record)
print("held", flush=True)
sys.stdin.read()
if sys.argv[3:] == ["finish-and-ship"]:
    (record / "written-last.md").write_text("the writer's last file\\n")
    shipper.record_directory_being_written_lock_release(record)
    subprocess.run([sys.executable, sys.argv[1], str(record)], check=False, capture_output=True)
"""
COLD_READ_RECORD_SHIPPER = hook.REPOSITORY_ROOT / "nc-systems" / "cold-read" / "cold-read-record-ship.py"


def record_writer_started(record, *mode):
    writer = subprocess.Popen(
        [sys.executable, "-c", COLD_READ_RECORD_BEING_WRITTEN_LOCK_HOLDER_UNTIL_STDIN_CLOSES_PYTHON_SOURCE,
         str(COLD_READ_RECORD_SHIPPER), str(record), *mode],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    return writer, writer.stdout.readline() == "held\n"


checkout, worktree = checkout_with_worktree("beingwritten")
being_written = worktree / "cold-read-records" / "beingwritten-doc-2026-11-03"
other_worktree = checkout.parent / "beingwritten-other-worktree"
git(checkout, "worktree", "add", "-q", "--detach", str(other_worktree))
writer, held = record_writer_started(being_written)
being_written_in_store = STORE / "cold-read-records" / being_written.name
removes_worktree_refusal_start = ("Refused on purpose: this command removes a worktree in which a running "
                                  "program, such as the cold-read-grid, is still writing a record.")
unresolved_refusal_start = "Refused on purpose: this hook could not tell which worktree this command removes ("
deferred_ending = ("This hook has deferred the removal: a program waits until every record above is finished, "
                   "ships the records, removes the worktree, and tells the user if that fails. You have nothing "
                   "to do for the removal. If your command did anything else, none of it ran: run again now only "
                   "the parts that do not need this worktree gone.")
try:
    check("the writer holds its record's being-written lock", held)
    waiter_starts.clear()
    code, output = run_hook(payload_for(f"git worktree remove {other_worktree}", checkout))
    check("removing another worktree is let through while a record is being written, ships none of the writer's "
          "worktree's records, and starts no waiter",
          code == 0 and output is None and not being_written_in_store.exists() and waiter_starts == []
          and not (STORE / "sanity-check-records" / "2026-11-03-beingwritten-doc").exists(),
          (code, output, waiter_starts))
    for label, command, cwd, force in (
            ("by its absolute path", f"git worktree remove --force {worktree}", checkout, True),
            ("by a path relative to the cwd", "git worktree remove ../beingwritten-worktree", checkout, False),
            ("by the end of its path alone, as git allows", "git worktree remove beingwritten-worktree", checkout,
             False),
            ("by a path relative to a -C directory", "git -C .. worktree remove ./beingwritten-worktree", checkout,
             False),
            ("with a comment after it", f"git worktree remove -f -- {worktree}  # done", checkout, True)):
        waiter_starts.clear()
        code, output = run_hook(payload_for(command, cwd))
        reason = refusal(output) or ""
        check(f"removing the worktree a record is being written in, named {label}, is refused, naming the record, "
              f"and the removal is deferred",
              code == 0 and reason.startswith(removes_worktree_refusal_start)
              and f"Record {being_written} (worktree {worktree})\n" in reason
              and reason.endswith(deferred_ending)
              and not being_written_in_store.exists(),
              (code, output))
        check(f"the removal named {label} starts one waiter for that worktree and its record, "
              f"{'with' if force else 'without'} -f, run from the main checkout",
              waiter_starts == [(worktree, force, [being_written], checkout)], waiter_starts)
    # A removal the shell may not run, or that a command around it decides, is refused and never deferred.
    for label, command, force in (
            ("inside bash -c", f"bash -c 'git worktree remove -f {worktree}'", " -f"),
            ("after another command", f"ls && git worktree remove -f -- {worktree}", " -f"),
            ("after false &&", f"false && git worktree remove -f {worktree}", " -f"),
            ("after a git push that may fail", f"git push && git worktree remove {worktree}", ""),
            ("in the else branch of an if", f"if test -e /nowhere; then echo dirty; else git worktree remove -f {worktree}; "
                                            "fi", " -f"),
            ("as a fallback that adds --force", f"git worktree remove {worktree} || git worktree remove --force {worktree}",
             " -f"),
            ("in a loop that may not run", f"while false; do git worktree remove {worktree}; done", ""),
            ("with its output redirected", f"git worktree remove {worktree} > /nowhere/out", "")):
        waiter_starts.clear()
        code, output = run_hook(payload_for(command, checkout))
        reason = refusal(output) or ""
        check(f"a removal of the worktree a record is being written in, {label}, is refused, naming the record, "
              f"and no waiter is started",
              code == 0 and reason.startswith(unresolved_refusal_start)
              and hook.GIT_WORKTREE_REMOVE_NOT_THE_WHOLE_SHELL_COMMAND_REFUSAL_REASON in reason
              and f"Record {being_written} (worktree {worktree})\n" in reason and waiter_starts == []
              and f"Run the removal again as `git worktree remove{force} <path>`" in reason
              and not being_written_in_store.exists(),
              (code, output, waiter_starts))
    code, output = run_hook(payload_for(f"git worktree remove {worktree}", checkout),
                            start_waiter=lambda *arguments: "the waiter could not be started: [Errno 2] no python")
    reason = refusal(output) or ""
    check("a waiter that cannot start makes the refusal say the removal was not deferred, and send the agent on",
          reason.startswith(removes_worktree_refusal_start) and deferred_ending not in reason
          and f"This hook could not defer the removal, so no program will remove the worktree once the record is "
              f"finished: for {worktree}, the waiter could not be started: [Errno 2] no python.\n" in reason
          and f"Leave the worktree in place, stop, and {hook.TELL_THE_USER_OR_DISPATCHING_AGENT} that `git worktree "
              f"remove` is refused while a program writes a record in that worktree" in reason, reason)
    for label, command, why, force in (
            ("a variable", 'git worktree remove "$WORKTREE"', "holds a variable, a glob or a substitution", ""),
            ("a variable, with -f", 'git worktree remove -f "$WORKTREE"', "holds a variable, a glob or a substitution",
             " -f"),
            ("a -C holding a variable", "git -C $HOME worktree remove x", "holds a variable, a glob or a substitution",
             ""),
            ("an option the hook does not read", "git worktree remove --frobnicate x", "is given the option --frobnicate",
             ""),
            ("a relative path after cd", "cd .. && git worktree remove --force ./beingwritten-worktree",
             "the command changes directory", " -f")):
        waiter_starts.clear()
        code, output = run_hook(payload_for(command, checkout))
        reason = refusal(output) or ""
        check(f"a removal the hook cannot place, by {label}, is refused while a record is being written, "
              f"and no waiter is started",
              code == 0 and reason.startswith(unresolved_refusal_start) and why in reason
              and f"Record {being_written} (worktree {worktree})\n" in reason and waiter_starts == []
              and f"Run the removal again as `git worktree remove{force} <path>`, with the worktree's path written "
                  "out in full, as an absolute path with no variable, in a command that does not change directory."
                  in reason,
              (code, output, waiter_starts))
    for label, command, force in (("without -f", "git worktree remove /a/nowhere", ""),
                                  ("with -f", "git worktree remove -f /a/nowhere", " -f")):
        waiter_starts.clear()
        code, output = run_hook(payload_for(command, checkout))
        reason = refusal(output) or ""
        check(f"a removal whose written-out path names no worktree, {label}, is refused while a record is being "
              f"written, telling the agent to copy the path from git worktree list, not to write it out again",
              code == 0 and reason.startswith(unresolved_refusal_start)
              and "the path /a/nowhere names no worktree the hook can find" in reason
              and f"Record {being_written} (worktree {worktree})\n" in reason and waiter_starts == []
              and reason.endswith(hook.PATH_NAMES_NO_WORKTREE_RUN_AGAIN_INSTRUCTION_TEMPLATE.format(force=force))
              and "written out in full" not in reason,
              (code, output, waiter_starts))
    code, output = run_hook(payload_for(f"cd .. && git worktree remove {other_worktree}", checkout))
    check("an absolute path after cd still names its worktree, and another worktree's removal is let through",
          code == 0 and output is None, (code, output))
finally:
    writer.communicate("")
code, output = run_hook(payload_for(f"git worktree remove {worktree}", checkout))
check("once its writer has exited, the record ships and the removal is let through",
      code == 0 and output is None and (being_written_in_store / "fast-read.md").is_file(), (code, output))

# Which worktree a removal names, read as git's find_worktree reads it.
worktrees = [Path("/a/b/one"), Path("/a/c/one"), Path("/a/b/two")]
check("a path suffix shared by two worktrees names neither by suffix",
      hook.worktree_named_by_path_suffix("one", worktrees) is None
      and hook.worktree_named_by_path_suffix("b/one", worktrees) == Path("/a/b/one"))
check("a suffix must start at a directory boundary",
      hook.worktree_named_by_path_suffix("wo", worktrees) is None)
check("two paths given to one removal leave the hook unable to tell",
      hook.worktrees_removed_or_unresolved_reason("git worktree remove /a/b/one /a/b/two", "/", worktrees)
      == (None, "`worktree remove` is given 2 paths"))
check("a removal naming no worktree leaves the hook unable to tell, never removing none",
      hook.worktrees_removed_or_unresolved_reason("git worktree remove /a/nowhere", "/", worktrees)
      == (None, "the path /a/nowhere names no worktree the hook can find from the command's directory"))
unshipped = [(Path("/s/ship.py"), Path("/a/b/one"), Path("/a/b/one/cold-read-records/r"), "FAILED: no space")]
for label, unresolved, instruction in (
        ("a written-out path that names no worktree",
         hook.PATH_NAMES_NO_WORKTREE_REASON_TEMPLATE.format(argument="/a/nowhere"),
         hook.PATH_NAMES_NO_WORKTREE_RUN_AGAIN_INSTRUCTION_TEMPLATE.format(force=" -f")),
        ("a path holding a variable", "the path holds a variable, a glob or a substitution",
         hook.GIT_WORKTREE_REMOVE_PATH_WRITTEN_OUT_RUN_AGAIN_INSTRUCTION_TEMPLATE.format(force=" -f"))):
    reason = hook.shipment_failed_refusal(unshipped, unresolved, " -f")
    check(f"the shipment-failed refusal of a removal the hook cannot place, for {label}, gives that reason's "
          f"run-again instruction",
          unresolved in reason and instruction in reason
          and ("written out in full" in reason) == ("written out in full" in instruction), reason)
check("a removal naming no path in the command text, as through xargs, leaves the hook unable to tell",
      hook.worktrees_removed_or_unresolved_reason("echo /a/b/two | xargs git worktree remove", "/", worktrees)
      == (None, "`worktree remove` names no path in the command text, so the path reaches git only when "
                "the command runs, as through xargs"))
check("builtin cd before a relative path leaves the hook unable to tell",
      hook.worktrees_removed_or_unresolved_reason(
          "builtin cd .claude/worktrees && git worktree remove -f ./A", "/r",
          [Path("/r"), Path("/r/.claude/worktrees/A")])
      == (None, "the command changes directory, and the path ./A is relative"))
check("a worktree removed twice, once with -f, is removed with -f",
      hook.worktrees_removed_or_unresolved_reason(
          "git worktree remove /a/b/two; bash -c 'git worktree remove --force /a/b/two'", "/", worktrees)
      == ({Path("/a/b/two"): True}, None))

# A removal the shell or a wrapper resolves in another directory than the hook's cwd is unresolved, not let through.
repository_worktrees = [Path("/r"), Path("/r/.claude/worktrees/A"), Path("/r/.claude/worktrees/B")]
for label, command in (
        ("a relative path in bash -c after cd", "cd .claude/worktrees && bash -c 'git worktree remove ./A'"),
        ("a relative path climbing out in bash -c after cd", "cd docs && bash -c 'git worktree remove ../../writer'"),
        ("env -C", "env -C /a git worktree remove writer"),
        ("env -C with its directory attached", "env -C/a git worktree remove writer"),
        ("env --chdir=", "env --chdir=/a git worktree remove writer"),
        ("sudo -D", "sudo -D /a git worktree remove writer")):
    removed, reason = hook.worktrees_removed_or_unresolved_reason(command, "/r", repository_worktrees)
    check(f"{label} leaves the hook unable to tell which worktree is removed",
          removed is None and reason is not None and "changes directory" in reason, (removed, reason))
check("a bracket glob in the path leaves the hook unable to tell",
      hook.worktrees_removed_or_unresolved_reason("git worktree remove /a/wri[t]er", "/", worktrees)
      == (None, "the path /a/wri[t]er holds a variable, a glob or a substitution"))
check("env without a directory option still resolves the path against the cwd",
      hook.worktrees_removed_or_unresolved_reason("env -u X git worktree remove .claude/worktrees/A", "/r",
                                                  repository_worktrees)
      == ({Path("/r/.claude/worktrees/A"): False}, None))


# The deferred removal, end to end: the hook starts the real waiter, detached, which waits for the writer,
# ships the records and removes the worktree, or writes a user-alert.
def start_waiter_quickly(worktree, force, records, git_directory):
    return hook.git_worktree_remove_deferred_waiter_start_unless_one_already_waits(
        worktree, force, records, git_directory, ned_box_home=SCRATCH_NED_BOX_HOME,
        waiter_options=["--poll-seconds", "0.2", "--writer-own-shipment-grace-seconds", "2"])


def waiter_logs_of(worktree):
    return sorted(WAITER_LOGS.glob(f"*-{worktree.name}-*.log"))


def alerts_naming(worktree):
    return [alert for alert in (json.loads(path.read_text()) for path in sorted(PENDING_ALERTS.glob("*.json")))
            if str(worktree) in alert["title"]]


def waiter_ended(worktree):
    """True once the worktree's waiter has logged the line it writes last: its removal, or its user-alert.

    Git deletes the worktree before the waiter logs the removal, so a gone worktree does not mean the waiter
    has ended."""
    return any(line.partition(" ")[2].startswith(("removed: ", "user-alert written: "))
               for path in waiter_logs_of(worktree) for line in path.read_text().splitlines())


def waited_until(condition, seconds=60):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.2)
    return condition()


def deferred_removal_case(name, command_options, writer_mode=()):
    """Start a writer in a new worktree and run the hook's removal of it; return (checkout, worktree, record,
    writer, refusal text)."""
    case_checkout, case_worktree = checkout_with_worktree(name)
    record = case_worktree / "cold-read-records" / f"{name}-doc-2026-11-03"
    case_writer, case_held = record_writer_started(record, *writer_mode)
    check(f"{name}: the writer holds its record's being-written lock", case_held)
    _, case_output = run_hook(payload_for(f"git worktree remove {command_options}{case_worktree}", case_checkout),
                              start_waiter=start_waiter_quickly)
    return case_checkout, case_worktree, record, case_writer, refusal(case_output) or ""


# A writer that finishes, shipping its record itself; a second removal while the waiter waits starts no waiter.
_, finishes_worktree, finishes_record, writer, reason = deferred_removal_case(
    "deferred-writer-finishes", "-f ", ["finish-and-ship"])
try:
    check("a removal deferred while the writer runs is refused with the deferred ending, and the worktree stays",
          reason.endswith(deferred_ending) and finishes_worktree.is_dir(), reason)
    check("the hook started one waiter, whose log is in the log-store's waiter log directory",
          len(waiter_logs_of(finishes_worktree)) == 1, list(WAITER_LOGS.glob("*")))
    code, output = run_hook(payload_for(f"git worktree remove {finishes_worktree}", finishes_worktree),
                            start_waiter=start_waiter_quickly)
    check("a second removal while a waiter waits on the worktree is deferred too, and starts no second waiter",
          (refusal(output) or "").endswith(deferred_ending) and len(waiter_logs_of(finishes_worktree)) == 1,
          (output, waiter_logs_of(finishes_worktree)))
    check("the waiter holds the worktree's flock, so the start function itself starts none",
          start_waiter_quickly(finishes_worktree, True, [finishes_record], finishes_worktree) is None
          and len(waiter_logs_of(finishes_worktree)) == 1)
finally:
    writer.communicate("")
check("once the writer finishes, the waiter removes the worktree",
      waited_until(lambda: waiter_ended(finishes_worktree)) and not finishes_worktree.exists(),
      [path.read_text() for path in waiter_logs_of(finishes_worktree)])
check("the record the writer finished is in the log-store whole, with the file it wrote last",
      (STORE / "cold-read-records" / finishes_record.name / "written-last.md").is_file()
      and (STORE / "cold-read-records" / finishes_record.name / "fast-read.md").is_file())
log_text = "".join(path.read_text() for path in waiter_logs_of(finishes_worktree))
check("the waiter's log says it removed the worktree with -f, and it wrote no user-alert",
      f"removed: git -C " in log_text and f"worktree remove -f {finishes_worktree}" in log_text
      and alerts_naming(finishes_worktree) == [], log_text)

# A writer killed early never ships its record: the waiter ships it once the grace runs out, then removes.
_, killed_worktree, killed_record, writer, reason = deferred_removal_case("deferred-writer-killed", "--force ")
writer.kill()
writer.wait()
check("after a writer is killed early, the waiter removes the worktree",
      waited_until(lambda: waiter_ended(killed_worktree)) and not killed_worktree.exists(),[path.read_text() for path in waiter_logs_of(killed_worktree)])
log_text = "".join(path.read_text() for path in waiter_logs_of(killed_worktree))
check("the killed writer's record was shipped by the waiter, after the writer did not ship it",
      (STORE / "cold-read-records" / killed_record.name / "fast-read.md").is_file()
      and f"not shipped by their writers within 2.0 seconds: {killed_record}" in log_text, log_text)

# A second writer starts in the worktree after the deferral and before the first writer finishes: the waiter's
# step 4 finds it, waits again, and removes the worktree only once it too has finished.
_, second_worktree, second_first_record, writer, reason = deferred_removal_case(
    "deferred-second-writer", "-f ", ["finish-and-ship"])
second_record = second_worktree / "cold-read-records" / "deferred-second-writer-second-doc-2026-11-03"
second_record.mkdir(parents=True)
(second_record / "fast-read.md").write_text("the second writer's first file\n")
second_writer, second_held = record_writer_started(second_record, "finish-and-ship")
try:
    check("the second writer holds its record's being-written lock, and the removal was deferred",
          second_held and reason.endswith(deferred_ending), reason)
    writer.communicate("")
    check("once the first writer finishes, the waiter finds the second record being written and waits again",
          waited_until(lambda: "still being written, waiting again: " + str(second_record) in "".join(
              path.read_text() for path in waiter_logs_of(second_worktree))),
          [path.read_text() for path in waiter_logs_of(second_worktree)])
    check("while the second writer runs, the worktree and its record are still there",
          second_worktree.is_dir() and second_record.is_dir())
finally:
    second_writer.communicate("")
check("once the second writer finishes, the waiter removes the worktree, with both records in the log-store whole",
      waited_until(lambda: waiter_ended(second_worktree)) and not second_worktree.exists()
      and(STORE / "cold-read-records" / second_record.name / "written-last.md").is_file()
      and (STORE / "cold-read-records" / second_first_record.name / "written-last.md").is_file(),
      [path.read_text() for path in waiter_logs_of(second_worktree)])

# The process that starts the waiter returns at once, though the waiter waits: Claude Code reads the hook's output
# until it closes, so a waiter holding it would keep the hook running past its timeout, which lets the removal through.
detached_checkout, detached_worktree = checkout_with_worktree("deferred-start-detaches")
detached_record = detached_worktree / "cold-read-records" / "deferred-start-detaches-doc-2026-11-03"
writer, held = record_writer_started(detached_record)
WAITER_STARTED_IN_A_PROCESS_OF_ITS_OWN_PYTHON_SOURCE = """
import importlib.util, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("hook", sys.argv[1])
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)
print(hook.git_worktree_remove_deferred_waiter_start_unless_one_already_waits(
    Path(sys.argv[2]), True, [Path(sys.argv[3])], Path(sys.argv[4]), ned_box_home=Path(sys.argv[5]),
    waiter_options=["--poll-seconds", "0.2", "--writer-own-shipment-grace-seconds", "2"]))
"""
try:
    started = time.monotonic()
    starter = subprocess.run(
        [sys.executable, "-c", WAITER_STARTED_IN_A_PROCESS_OF_ITS_OWN_PYTHON_SOURCE, str(HOOK_SCRIPT),
         str(detached_worktree), str(detached_record), str(detached_checkout), str(SCRATCH_NED_BOX_HOME)],
        capture_output=True, text=True, timeout=60)
    took = time.monotonic() - started
    check("a process that starts the waiter, its output captured, returns while the waiter still waits",
          starter.returncode == 0 and starter.stdout == "None\n" and took < 30 and detached_worktree.is_dir()
          and len(waiter_logs_of(detached_worktree)) == 1, (starter, took))
finally:
    writer.communicate("")
check("the waiter that process started removes the worktree once the writer finishes",
      waited_until(lambda: waiter_ended(detached_worktree)) and not detached_worktree.exists(),
      [path.read_text() for path in waiter_logs_of(detached_worktree)])

# Git refuses the removal: the worktree holds untracked files and the command gave no -f.
_, refused_worktree, refused_record, writer, reason = deferred_removal_case("deferred-git-refuses", "")
writer.communicate("")
check("when git refuses the deferred removal, the waiter writes a user-alert",
      waited_until(lambda: waiter_ended(refused_worktree)) and alerts_naming(refused_worktree) != [],
      [path.read_text() for path in waiter_logs_of(refused_worktree)])
alert = (alerts_naming(refused_worktree) or [{}])[0]
check("the user-alert names the worktree, its Record line, the git command that failed and the log",
      alert.get("title") == f"A deferred `git worktree remove` did not run: {refused_worktree}"
      and f"Record {refused_record} (worktree {refused_worktree})\n" in alert.get("alert_text", "")
      and f"worktree remove {refused_worktree}` exited 128: " in alert.get("alert_text", "")
      and f"The second program's log file: {waiter_logs_of(refused_worktree)[0]}" in alert.get("alert_text", "")
      and alert.get("action") == waiter.GIT_WORKTREE_REMOVE_DEFERRED_FAILED_USER_ALERT_ACTION_TEXT_SAYING_WHAT_AN_AGENT_CAN_DO, alert)
check("git refusing leaves the worktree in place, with its record shipped",
      refused_worktree.is_dir() and (STORE / "cold-read-records" / refused_record.name / "fast-read.md").is_file())

# The start function's own failures: a worktree directory it cannot open, a log it cannot write.
check("a worktree directory that cannot be opened starts no waiter, and says why",
      (start_waiter_quickly(_scratch / "no-such-worktree", False, [], _scratch) or "")
      .startswith("its directory could not be opened: "))
blocked_home = _scratch / "ned-box-home-is-a-file"
blocked_home.write_text("not a directory\n")
no_waiter_directory = _scratch / "directory-no-waiter-holds"
no_waiter_directory.mkdir()
check("a log that cannot be written starts no waiter, and says why",
      (hook.git_worktree_remove_deferred_waiter_start_unless_one_already_waits(no_waiter_directory, False, [], no_waiter_directory,
                                                           ned_box_home=blocked_home) or "")
      .startswith("the waiter could not be started: "))


# The waiter's other failures, injected in-process through its main.
def waiter_run(worktree, *options, runner=subprocess.run, injected_hook=hook, clock=time.monotonic, sleep=time.sleep):
    """Run the waiter's main in-process on worktree; return (exit code, its log, the alerts this run wrote)."""
    alerts_before = alerts_naming(worktree)
    log_output = io.StringIO()
    with contextlib.redirect_stdout(log_output):
        code = waiter.main(["--worktree", str(worktree), "--git-directory", str(worktree),
                            "--ned-box-home", str(SCRATCH_NED_BOX_HOME), "--poll-seconds", "0.05",
                            "--writer-own-shipment-grace-seconds", "0", *options],
                           runner=runner, hook=injected_hook, clock=clock, sleep=sleep)
    return code, log_output.getvalue(), [alert for alert in alerts_naming(worktree) if alert not in alerts_before]


failing_checkout, failing_worktree = checkout_with_worktree("waiter-failures")
failing_record = failing_worktree / "cold-read-records" / "waiter-failures-doc-2026-11-03"
writer, held = record_writer_started(failing_record)
try:
    code, log_text, alerts = waiter_run(failing_worktree, "--record", str(failing_record),
                                        "--total-limit-seconds", "0.3")
finally:
    writer.communicate("")
check("a record still being written when the time limit runs out leaves the worktree and writes a user-alert",
      code == 1 and failing_worktree.is_dir() and len(alerts) == 1
      and waiter.WAITER_TIME_LIMIT_RAN_OUT_USER_ALERT_FAILURE_SENTENCE in alerts[0]["alert_text"]
      and f"Record {failing_record} (worktree {failing_worktree})\n" in alerts[0]["alert_text"], (code, log_text))

# The default limit, on a clock that only the waiter's own sleeps move: 30-second polls land on 49.5 and 50 minutes.
simulated = {"now": 0.0, "slept_at": []}


def simulated_sleep(seconds):
    simulated["slept_at"].append(simulated["now"])
    simulated["now"] += seconds


writer, held = record_writer_started(failing_record)
try:
    code, log_text, alerts = waiter_run(failing_worktree, "--record", str(failing_record), "--poll-seconds", "30",
                                        clock=lambda: simulated["now"], sleep=simulated_sleep)
finally:
    writer.communicate("")
check("with the default time limit, a record still being written is still waited for at 49.5 minutes and the "
      "waiter gives up at 50, leaving the worktree and writing a user-alert",
      code == 1 and failing_worktree.is_dir() and len(alerts) == 1
      and waiter.WAITER_TIME_LIMIT_RAN_OUT_USER_ALERT_FAILURE_SENTENCE in alerts[0]["alert_text"]
      and max(simulated["slept_at"]) == 49.5 * 60 and simulated["now"] == 50 * 60,
      (code, simulated["now"], simulated["slept_at"][-3:], log_text))


def shipper_failing_runner(argv, **keywords):
    if argv[0] == sys.executable:
        return subprocess.CompletedProcess(argv, 1, "FAILED: ned-box could not be reached", "")
    return subprocess.run(argv, **keywords)


code, log_text, alerts = waiter_run(failing_worktree, runner=shipper_failing_runner)
check("a shipment that fails leaves the worktree and writes a user-alert quoting the shipper's line",
      code == 1 and failing_worktree.is_dir() and len(alerts) == 1
      and waiter.RECORDS_NOT_SHIPPED_USER_ALERT_FAILURE_SENTENCE in alerts[0]["alert_text"]
      and f"Record {failing_record} (worktree {failing_worktree}): FAILED: ned-box could not be reached\n"
      in alerts[0]["alert_text"], (code, log_text, alerts))


def git_stalling_runner(argv, **keywords):
    if argv[0] == "git":
        raise subprocess.TimeoutExpired(argv, keywords.get("timeout"))
    return subprocess.run(argv, **keywords)


code, log_text, alerts = waiter_run(failing_worktree, "--force", runner=git_stalling_runner)
check("a git removal past its time limit leaves the worktree and writes a user-alert",
      code == 1 and failing_worktree.is_dir() and len(alerts) == 1
      and f"ran past {waiter.GIT_TIMEOUT_SECONDS} seconds." in alerts[0]["alert_text"], (code, log_text))


class HookWhoseRecordReadingFails:
    """The hook's functions, except that the worker fails before it has read the records."""

    def __getattr__(self, name):
        return getattr(hook, name)

    def ship_every_record(self, worktrees, runner, clock, deadline, progress):
        progress["error"] = "ImportError: shipper module missing"


code, log_text, alerts = waiter_run(failing_worktree, injected_hook=HookWhoseRecordReadingFails())
check("records the waiter cannot read leave the worktree and write a user-alert naming the error",
      code == 1 and len(alerts) == 1
      and "it could not read the worktree's records (ImportError: shipper module missing)."
      in alerts[0]["alert_text"], (code, log_text))
code, log_text, alerts = waiter_run(failing_worktree, injected_hook=object())
check("an unexpected error in the waiter leaves the worktree and writes a user-alert naming it",
      code == 1 and failing_worktree.is_dir() and len(alerts) == 1
      and "the waiter stopped on an error: AttributeError: " in alerts[0]["alert_text"], (code, log_text))


class HookWhoseLogStoreCallsStall:
    """The hook's functions, except that the store check, or the shipping pass, stalls as an ssh to ned-box can."""

    def __init__(self, stalling):
        self.stalling = stalling
        self.released = threading.Event()

    def __getattr__(self, name):
        return getattr(hook, name)

    def store_holds_every_file_of(self, kind, record):
        if self.stalling == "store check":
            self.released.wait(30)
        return hook.store_holds_every_file_of(kind, record)

    def ship_every_record(self, worktrees, runner, clock, deadline, progress):
        if self.stalling == "shipping pass":
            self.released.wait(30)
        return hook.ship_every_record(worktrees, runner, clock, deadline, progress)


for stalling in ("store check", "shipping pass"):
    stalling_hook = HookWhoseLogStoreCallsStall(stalling)
    started = time.monotonic()
    try:
        code, log_text, alerts = waiter_run(failing_worktree, "--record", str(failing_record), "--total-limit-seconds",
                                            "1", "--writer-own-shipment-grace-seconds", "30",
                                            injected_hook=stalling_hook)
    finally:
        stalling_hook.released.set()
    took = time.monotonic() - started
    check(f"a {stalling} that stalls ends the wait when the time limit runs out, leaving the worktree and writing "
          f"a user-alert",
          code == 1 and took < 15 and failing_worktree.is_dir() and len(alerts) == 1
          and waiter.LOG_STORE_CALL_TIME_LIMIT_RAN_OUT_USER_ALERT_FAILURE_SENTENCE in alerts[0]["alert_text"],
          (code, took, log_text, alerts))


class HookWhoseStoreCheckRaises:
    """The hook's functions, except that the store check raises, as an unreadable store inventory can."""

    def __getattr__(self, name):
        return getattr(hook, name)

    def store_holds_every_file_of(self, kind, record):
        raise OSError("store inventory unreadable")


code, log_text, alerts = waiter_run(failing_worktree, "--record", str(failing_record),
                                    "--writer-own-shipment-grace-seconds", "30", "--total-limit-seconds", "5",
                                    injected_hook=HookWhoseStoreCheckRaises())
check("an error raised in a bounded log-store call reaches the waiter, whose user-alert names that error",
      code == 1 and failing_worktree.is_dir() and len(alerts) == 1
      and "the waiter stopped on an error: OSError: store inventory unreadable" in alerts[0]["alert_text"],
      (code, log_text, alerts))
check("a record gone holds no being-written lock",
      waiter.record_directory_being_written_lock_is_held_by_any_process({kind[0]: kind for kind in hook.record_kinds()},
                          failing_worktree / "cold-read-records" / "never-written") is False)

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
