#!/usr/bin/env python3
"""Tests for git-worktree-remove-cold-read-record-and-sanity-check-record-ship-to-log-store-first-guard-hook.py.

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

SHIP_DESTINATION_VARIABLE = "COLD_READ_RECORD_SHIP_DESTINATION"
# Any test run that reaches a shipper ships here, never into the real log-store.
# Resolved, because the hook names a worktree by its resolved path and the test sandbox's TMPDIR is a symlink.
_scratch = Path(tempfile.mkdtemp(prefix="git-worktree-remove-records-ship-first-test-")).resolve()
atexit.register(shutil.rmtree, _scratch, ignore_errors=True)
STORE = _scratch / "store"
os.environ[SHIP_DESTINATION_VARIABLE] = str(STORE / "cold-read-records")
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


def run_hook(payload, runner=subprocess.run, clock=None):
    """Run main in-process; return (exit code, parsed stdout or None)."""
    stdout = io.StringIO()
    keywords = {"runner": runner}
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


# Every worktree's unshipped records reach the log-store before the removal, which is let through.
checkout, worktree = checkout_with_worktree("shipped")
other_worktree = checkout.parent / "shipped-other-worktree"
git(checkout, "worktree", "add", "-q", "--detach", str(other_worktree))
other_record = other_worktree / "cold-read-records" / "shipped-other-doc-2026-11-03"
other_record.mkdir(parents=True)
(other_record / "fast-read.md").write_text("other report\n")
code, output, stderr = run_hook_process("git worktree remove some-worktree", checkout)
cold_read_copy = STORE / "cold-read-records" / "shipped-doc-2026-11-03" / "fast-read.md"
sanity_check_copy = STORE / "sanity-check-records" / "2026-11-03-shipped-doc" / "finding-dispositions.md"
check("unshipped records reach the log-store and the removal is let through silently",
      code == 0 and output is None and cold_read_copy.is_file() and sanity_check_copy.is_file()
      and cold_read_copy.read_text() == "shipped report\n",
      (code, output, stderr, sorted(str(path) for path in STORE.rglob("*"))))
check("the records of a worktree the command does not name ship too",
      (STORE / "cold-read-records" / other_record.name / "fast-read.md").is_file())
check("an empty record directory is not shipped",
      not (STORE / "cold-read-records" / "empty-record").exists())

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
check("the refusal opens by saying it refused on purpose, that every worktree's records are shipped, and how many failed",
      reason.startswith("Refused on purpose: before any `git worktree remove`, this hook ships the cold-read-records "
                        "and sanity-check records of every worktree of this repository to the log-store, and 2 "
                        "record(s) did not reach it."), reason)
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

# A record whose name the store holds with other content is refused by the real shipper, and the refusal quotes its mv.
checkout, worktree = checkout_with_worktree("clash")
clashing_store_copy = STORE / "cold-read-records" / "clash-doc-2026-11-03"
clashing_store_copy.mkdir(parents=True)
(clashing_store_copy / "fast-read.md").write_text("another read's report\n")
code, output, stderr = run_hook_process("git worktree remove anything", checkout)
reason = refusal(output) or ""
check("a record in any worktree that the shipper refuses refuses the removal, quoting the shipper's mv",
      f"Record {worktree / 'cold-read-records' / 'clash-doc-2026-11-03'} (worktree {worktree}): REFUSED:" in reason
      and "`mv " in reason and "clash-doc-2026-11-03-2" in reason, (code, output, stderr))
subprocess.run(["mv", str(worktree / "cold-read-records" / "clash-doc-2026-11-03"),
                str(worktree / "cold-read-records" / "clash-doc-2026-11-03-2")], check=True)
code, output, stderr = run_hook_process("git worktree remove anything", checkout)
check("once the refused record is renamed as the refusal says, the removal ships it and is let through",
      code == 0 and output is None
      and (STORE / "cold-read-records" / "clash-doc-2026-11-03-2" / "fast-read.md").read_text()
      == "clash report\n", (code, output, stderr))

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
not_checked_opening = ("Not checked: the hook that ships every worktree's cold-read-records and sanity-check "
                       "records to the log-store before `git worktree remove` could not list this repository's "
                       "worktrees (")
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
# here by a second process through the shipper's own function, as the grid takes it.
COLD_READ_RECORD_BEING_WRITTEN_LOCK_HOLDER_UNTIL_STDIN_CLOSES_PYTHON_SOURCE = """
import importlib.util, pathlib, sys
spec = importlib.util.spec_from_file_location("shipper", sys.argv[1])
shipper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shipper)
shipper.record_directory_being_written_lock_take(pathlib.Path(sys.argv[2]))
print("held", flush=True)
sys.stdin.read()
"""
checkout, worktree = checkout_with_worktree("beingwritten")
being_written = worktree / "cold-read-records" / "beingwritten-doc-2026-11-03"
other_worktree = checkout.parent / "beingwritten-other-worktree"
git(checkout, "worktree", "add", "-q", "--detach", str(other_worktree))
writer = subprocess.Popen(
    [sys.executable, "-c", COLD_READ_RECORD_BEING_WRITTEN_LOCK_HOLDER_UNTIL_STDIN_CLOSES_PYTHON_SOURCE,
     str(hook.REPOSITORY_ROOT / "nc-systems" / "cold-read" / "cold-read-record-ship.py"), str(being_written)],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
being_written_in_store = STORE / "cold-read-records" / being_written.name
removes_worktree_refusal_start = ("Refused on purpose: this command removes a worktree in which a running "
                                  "program, such as the cold-read-grid, is still writing a record.")
unresolved_refusal_start = "Refused on purpose: this hook could not tell which worktree this command removes ("
try:
    check("the writer holds its record's being-written lock", writer.stdout.readline() == "held\n")
    code, output = run_hook(payload_for(f"git worktree remove {other_worktree}", checkout))
    check("removing another worktree is let through while a record is being written, and the record is not "
          "shipped, while the other records are",
          code == 0 and output is None and not being_written_in_store.exists()
          and (STORE / "sanity-check-records" / "2026-11-03-beingwritten-doc" / "finding-dispositions.md").is_file(),
          (code, output))
    for label, command, cwd in (
            ("by its absolute path", f"git worktree remove --force {worktree}", checkout),
            ("by a path relative to the cwd", "git worktree remove ../beingwritten-worktree", checkout),
            ("by the end of its path alone, as git allows", "git worktree remove beingwritten-worktree", checkout),
            ("by a path relative to a -C directory", "git -C .. worktree remove ./beingwritten-worktree", checkout),
            ("inside bash -c", f"bash -c 'git worktree remove {worktree}'", checkout),
            ("after another command", f"ls && git worktree remove -f -- {worktree}", checkout)):
        code, output = run_hook(payload_for(command, cwd))
        reason = refusal(output) or ""
        check(f"removing the worktree a record is being written in, named {label}, is refused, naming the record",
              code == 0 and reason.startswith(removes_worktree_refusal_start)
              and f"Record {being_written} (worktree {worktree})\n" in reason
              and not being_written_in_store.exists(),
              (code, output))
    reason = refusal(run_hook(payload_for(f"git worktree remove {worktree}", checkout))[1]) or ""
    for line in ("If the program writing a record above is yours, wait until it prints its `record:` line, then "
                 "run your command again.",
                 "If it is not yours, leave the worktree in place, stop, and "
                 f"{hook.TELL_THE_USER_OR_DISPATCHING_AGENT} that `git worktree remove` is refused while a "
                 "program writes a record in that worktree, quoting each Record line above word for word."):
        check(f"the refusal carries the instruction {line[:50]!r}...", line in reason, reason)
    for label, command, why in (
            ("a variable", 'git worktree remove "$WORKTREE"', "holds a variable, a glob or a substitution"),
            ("a -C holding a variable", "git -C $HOME worktree remove x", "holds a variable, a glob or a substitution"),
            ("an option the hook does not read", "git worktree remove --frobnicate x", "is given the option --frobnicate"),
            ("a relative path after cd", "cd .. && git worktree remove ./beingwritten-worktree",
             "the command changes directory")):
        code, output = run_hook(payload_for(command, checkout))
        reason = refusal(output) or ""
        check(f"a removal the hook cannot place, by {label}, is refused while a record is being written",
              code == 0 and reason.startswith(unresolved_refusal_start) and why in reason
              and f"Record {being_written} (worktree {worktree})\n" in reason
              and "Run the removal again as `git worktree remove <path>`, with the worktree's path written out "
                  "in full, as an absolute path with no variable, in a command that does not change directory."
                  in reason,
              (code, output))
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
check("a removal naming no worktree removes none",
      hook.worktrees_removed_or_unresolved_reason("git worktree remove /a/nowhere", "/", worktrees) == (set(), None))

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
