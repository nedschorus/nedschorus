#!/usr/bin/env python3
"""Ship every worktree's cold-read-records and sanity-check records to the log-store before `git worktree remove` runs.

Both record folders, cold-read-records/ and sanity-check-records/, are
gitignored, so `git worktree remove` deletes them without a word. Before a
Bash command that runs `git worktree remove`, this PreToolUse hook lists the
repository's worktrees with `git worktree list`, run in the hook's cwd, and
ships the records of every one of them; it does not work out which worktree
the command removes. The shippers, and the folder each serves, are the ones
scripts/clean-worktrees.py uses (LOG_STORE_RECORD_SHIPPERS), loaded from that
file so the two stay one list. A record whose every file the log-store
already holds with the same content is skipped without running its shipper,
the answer the shipper would give ("nothing new"); the others are shipped by
running the shipper.

It allows the command silently when every record shipped or none needed to.
It refuses the command, naming each record that did not ship, its worktree,
the shipper's own line and the command that ships it again, when a shipper
exits nonzero (FAILED or REFUSED), prints nothing, or has not finished when
SHIPPING_BUDGET_SECONDS run out, and for each record the budget left
unreached. A refusal in any worktree refuses every removal until the record
is renamed and shipped, as the shipper's REFUSED line says.
.claude/settings.json gives the hook a longer timeout than the budget,
because a hook that overruns its timeout lets the command through unchecked
and reports nothing.

What it reads: every simple command, through the shared shell module on
tree-sitter-bash, whose program, after wrappers such as env and timeout, is
git with the subcommand `worktree remove`, and the command string of bash,
sh or zsh -c, read the same way. Not read: the remote command of ssh,
commands run by eval or a script file, removals a program makes itself, and
removals typed in a terminal or by a Codex agent. Walk files under docs/walk/,
which scripts/clean-worktrees.py also ships, are not shipped here.

Everything after the worktree listing, reading the records, checking them
against the store and shipping them, runs in one worker thread, under one
deadline of SHIPPING_BUDGET_SECONDS counted from before the listing. A record
or worktree that vanishes while it is read, because another agent-session
removes it, has nothing left to ship and is skipped. Any other error checking
or shipping a record refuses the removal, naming the record and the error.
At the deadline the hook refuses the removal, naming each record the worker
has not confirmed shipped, the worker's own line for each it found unshipped,
and the budget line for the rest. A worker still running, as when an ssh to
ned-box stalls, is left to end on its own: its store check only reads the
store, and a shipper it started may go on writing to the store, which harms
no record, because a shipper only adds files and checks them by reading them
back.

How it can fail: when `git worktree list` fails or runs past
GIT_TIMEOUT_SECONDS, as in a cwd outside any repository, or when the shell
reader cannot run, the command is let through and the agent is told in
additionalContext that no records were shipped. When the worker fails before
it has read every worktree's records, as when a shipper module cannot be
loaded, or has not read them when the deadline passes, the command is let
through and the agent is told, the same way, that records may not have
shipped. A removal in another
repository, given by git's -C or --git-dir, ships the records of the
repository the hook's cwd is in, not of that one. On the Mac each record is
checked against the store over ssh, one record at a time, so with many
records the budget can run out and refuse the removal; a run after that
skips the records already shipped.

The messages follow
docs/nedschorus-wiki/nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md.
"""

import importlib.util
import json
import os
import pathlib
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

_shell_reader_spec = importlib.util.spec_from_file_location(
    "shell_command_tree_sitter_bash_reader_common",
    REPOSITORY_ROOT / "nc-systems" / "general-tools" / "shell-command-tree-sitter-bash-reader-common.py")
shell_reader = importlib.util.module_from_spec(_shell_reader_spec)
_shell_reader_spec.loader.exec_module(shell_reader)
is_program = shell_reader.is_program

_git_output_spec = importlib.util.spec_from_file_location(
    "git_machine_readable_output_runner_and_parser_common",
    REPOSITORY_ROOT / "nc-systems" / "general-tools" / "git-machine-readable-output-runner-and-parser-common.py")
git_output = importlib.util.module_from_spec(_git_output_spec)
_git_output_spec.loader.exec_module(git_output)

CLEAN_WORKTREES_SCRIPT = REPOSITORY_ROOT / "scripts" / "clean-worktrees.py"

# Below the hook's timeout in .claude/settings.json, so a slow shipment is refused, not let through.
SHIPPING_BUDGET_SECONDS = 240
GIT_TIMEOUT_SECONDS = 10

GIT_GLOBAL_VALUE_FLAGS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env",
                            "--exec-path"}

_next_step_lines_spec = importlib.util.spec_from_file_location(
    "failed_command_agent_facing_message_rerun_once_then_stop_and_report_lines_common",
    REPOSITORY_ROOT / "nc-systems" / "general-tools"
    / "failed-command-agent-facing-message-rerun-once-then-stop-and-report-lines-common.py")
next_step_lines = importlib.util.module_from_spec(_next_step_lines_spec)
_next_step_lines_spec.loader.exec_module(next_step_lines)
TELL_THE_USER_OR_DISPATCHING_AGENT = "tell " + next_step_lines.REPORT_RECIPIENT_PHRASE_USER_OR_DISPATCHING_AGENT

SHIPMENT_FAILED_REFUSAL_TEMPLATE = (
    "Refused on purpose: before any `git worktree remove`, this hook ships the cold-read-records "
    "and sanity-check records of every worktree of this repository to the log-store, and "
    "{count} record(s) did not reach it. The folders cold-read-records/ and sanity-check-records/ "
    "are gitignored, so removing a worktree deletes them for good, and the log-store on ned-box "
    "is the only other place a record is kept. The hook does not work out which worktree a "
    "command removes, so it refuses every removal until each record below has shipped.\n"
    "{records}"
    "If a Record line says the log-store or ned-box could not be reached, leave the worktree in "
    f"place, stop, and {TELL_THE_USER_OR_DISPATCHING_AGENT} "
    "that `git worktree remove` is refused because records could not be shipped to the "
    "log-store, quoting each Record line above word for word.\n"
    "If a Record line gives an `mv` to a free name and its worktree is one your agent-seat made "
    "or owns, run that `mv`; you need not run the \"Shipped with\" commands, because this hook "
    "runs them itself. Then run your `git worktree remove` command again, once.\n"
    "If a Record line's worktree belongs to another agent-seat, leave that record as it is, "
    f"stop, and {TELL_THE_USER_OR_DISPATCHING_AGENT} that `git worktree remove` is refused until "
    "that record is renamed and shipped, quoting its Record line word for word.\n"
    f"If this hook refuses your command again, leave the worktree in place, stop, and {TELL_THE_USER_OR_DISPATCHING_AGENT} "
    "that `git worktree remove` is refused because records could not be shipped to the "
    "log-store, quoting each Record line of the second refusal word for word."
)
UNSHIPPED_RECORD_LINE_TEMPLATE = (
    "Record {record} (worktree {worktree}): {line}\n"
    "  Shipped with: {command}\n"
)
SHIPPER_PRINTED_NOTHING_LINE_TEMPLATE = "the shipper printed nothing (exit {code}){stderr}"
SHIPPING_BUDGET_SPENT_LINE_TEMPLATE = (
    "not shipped: this hook's limit of {budget} seconds for shipping ran out first")
RECORD_CHECK_FAILED_LINE_TEMPLATE = "not shipped: this hook could not check or ship it: {error}"

SHIP_RECORDS_YOURSELF_NEXT_STEP_LINES = (
    "Before you remove another worktree, ship its records yourself, from that worktree's root, "
    "with this command: `python3 nc-systems/cold-read/cold-read-record-ship.py --all && "
    "python3 scripts/sanity-check-record-ship.py --all`\n"
    "If it exits 0, remove the worktree.\n"
    f"If it exits nonzero, leave the worktree in place, and {TELL_THE_USER_OR_DISPATCHING_AGENT} "
    "which worktree is kept, quoting each line that begins FAILED or REFUSED.")

WORKTREE_LISTING_FAILED_NOTICE = (
    "Not checked: the hook that ships every worktree's cold-read-records and sanity-check records "
    "to the log-store before `git worktree remove` could not list this repository's worktrees "
    "({reason}), so it shipped no records and let the command run. If the removed worktree held "
    "a record that had not shipped, that record is gone; nothing can bring it back.\n"
    + SHIP_RECORDS_YOURSELF_NEXT_STEP_LINES)

RECORDS_NOT_READ_NOTICE = (
    "Not checked: the hook that ships every worktree's cold-read-records and sanity-check records "
    "to the log-store before `git worktree remove` could not read every worktree's records "
    "({reason}), so it let the command run without knowing that every record had shipped. If the "
    "removed worktree held a record that had not shipped, that record is gone; nothing can bring "
    "it back.\n"
    + SHIP_RECORDS_YOURSELF_NEXT_STEP_LINES)

PARSER_UNAVAILABLE_NEXT_STEP_LINES = (
    "If the command removed a git worktree, the cold-read-records and sanity-check records in it "
    "were not shipped to the log-store first, and are gone unless they had shipped before.\n"
    + SHIP_RECORDS_YOURSELF_NEXT_STEP_LINES)


def is_git_worktree_remove(words):
    """True for `git [global options] worktree remove ...`, after wrappers such as env and timeout."""
    index, _ = shell_reader.simple_command_program_index_skipping_wrappers(words)
    if index is None or not is_program(words[index], "git"):
        return False
    index += 1
    while index < len(words) and words[index].startswith("-"):
        index += 2 if words[index] in GIT_GLOBAL_VALUE_FLAGS else 1
    return list(words[index:index + 2]) == ["worktree", "remove"]


def command_runs_git_worktree_remove(command):
    """True when the command, or the command string of a bash, sh or zsh -c in it, runs `git worktree remove`.

    Reads only the command text, so a replay of recorded commands gives the same answer on any machine.
    """
    for words in shell_reader.simple_commands(command):
        if is_git_worktree_remove(words):
            return True
        index, _ = shell_reader.simple_command_program_index_skipping_wrappers(words)
        if index is not None and any(is_program(words[index], runner) for runner in shell_reader.SHELL_STRING_RUNNERS):
            inner = shell_reader.shell_command_string(words[index + 1:])
            if inner is not None and command_runs_git_worktree_remove(inner):
                return True
    return False


def worktrees_listed_or_failure_reason(directory, runner):
    """Return ([worktree directory], None), or (None, why git could not list them)."""
    try:
        listing = runner(["git", "-C", str(directory), "worktree", "list", "--porcelain", "-z"],
                         capture_output=True, timeout=GIT_TIMEOUT_SECONDS, check=False)
    except subprocess.TimeoutExpired:
        return None, f"`git worktree list` ran past {GIT_TIMEOUT_SECONDS} seconds"
    except OSError as error:
        return None, f"`git worktree list` could not run: {error}"
    if listing.returncode != 0:
        error_lines = os.fsdecode(listing.stderr or b"").strip().splitlines()
        return None, f"`git worktree list` exited {listing.returncode}" + (
            f": {error_lines[-1]}" if error_lines else "")
    return [Path(record.path) for record in git_output.worktree_records(listing.stdout)
            if os.path.isdir(record.path)], None


def module_at(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def record_kinds():
    """Return (records folder name, shipper path, store logic module, store host, store path) for each kind."""
    kinds = []
    for directory_name, shipper in module_at(CLEAN_WORKTREES_SCRIPT, "clean_worktrees").LOG_STORE_RECORD_SHIPPERS:
        module = module_at(shipper, f"record_shipper_{directory_name.replace('-', '_')}")
        host, store_path = module.destination_for_this_machine()
        # The sanity-check shipper keeps the store logic in the cold-read shipper it imports as `shipper`.
        kinds.append((directory_name, shipper, getattr(module, "shipper", module), host, store_path))
    return kinds


def records_in(worktree, kinds):
    """Return (kind, record directory) for each non-empty record directory in the worktree.

    A records folder or record that vanishes while it is read has nothing left to ship and is left out.
    """
    records = []
    for kind in kinds:
        try:
            entries = sorted((worktree / kind[0]).iterdir())
        except (FileNotFoundError, NotADirectoryError):
            continue
        for record in entries:
            try:
                if record.is_dir() and not record.is_symlink() and any(record.iterdir()):
                    records.append((kind, record))
            except FileNotFoundError:
                continue
    return records


def store_holds_every_file_of(kind, record):
    """True when the store holds each of the record's files with the same content: the shipper would ship nothing."""
    _, _, store_logic, host, store_path = kind
    _, in_store = store_logic.store_inventory(host, pathlib.PurePosixPath(store_path) / record.name)
    if not in_store:
        return False
    return all(in_store.get(relative) == digest
               for relative, digest in store_logic.local_inventory(record).items())


def shipper_line(shipment):
    """The one line the shipper printed, or its exit code and last stderr line when it printed none."""
    line = shipment.stdout.strip()
    if line:
        return line
    error_lines = shipment.stderr.strip().splitlines()
    return SHIPPER_PRINTED_NOTHING_LINE_TEMPLATE.format(
        code=shipment.returncode, stderr=f": {error_lines[-1]}" if error_lines else "")


def budget_spent_line():
    return SHIPPING_BUDGET_SPENT_LINE_TEMPLATE.format(budget=SHIPPING_BUDGET_SECONDS)


def unshipped_line_for(record, kind, runner, clock, deadline):
    """Ship the record if the store lacks it; return None when it shipped or needed not, else the reason line."""
    if deadline - clock() <= 0:
        return budget_spent_line()
    if store_holds_every_file_of(kind, record):
        return None
    # Recomputed after the store check, which on the Mac is an ssh round trip.
    remaining = deadline - clock()
    if remaining <= 0:
        return budget_spent_line()
    try:
        shipment = runner([sys.executable, str(kind[1]), str(record)],
                          capture_output=True, text=True, timeout=remaining, check=False)
    except subprocess.TimeoutExpired:
        return budget_spent_line()
    if shipment.returncode != 0 or not shipment.stdout.strip():
        return shipper_line(shipment)
    return None


def ship_every_record(worktrees, runner, clock, deadline, progress):
    """The worker: read every worktree's records into progress["records"], then ship each, adding to
    progress["shipped"] each record that shipped or needed no shipping, and to progress["lines"] the reason
    line of each that did not ship. An error before every worktree's records are read goes in progress["error"]."""
    try:
        kinds = record_kinds()
        progress["records"] = [(worktree, kind, record) for worktree in dict.fromkeys(worktrees)
                               for kind, record in records_in(worktree, kinds)]
    except Exception as error:
        progress["error"] = f"{type(error).__name__}: {error}"
        return
    for worktree, kind, record in progress["records"]:
        try:
            line = unshipped_line_for(record, kind, runner, clock, deadline)
        except Exception as error:
            # A record another agent-session removed mid-check has nothing left to ship.
            line = None if not os.path.lexists(record) else RECORD_CHECK_FAILED_LINE_TEMPLATE.format(
                error=f"{type(error).__name__}: {error}")
        if line is None:
            progress["shipped"].add(record)
        else:
            progress["lines"][record] = line


def shipment_failed_refusal(unshipped):
    lines = "".join(UNSHIPPED_RECORD_LINE_TEMPLATE.format(
        record=record, worktree=worktree, line=line, command=shlex.join(["python3", str(shipper), str(record)]))
        for shipper, worktree, record, line in unshipped)
    return SHIPMENT_FAILED_REFUSAL_TEMPLATE.format(count=len(unshipped), records=lines)


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))


def note_unchecked(notice):
    # No permission decision: an allow would bypass the user's permission rules.
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "additionalContext": notice,
    }}))


def main(stdin=sys.stdin, runner=subprocess.run, clock=time.monotonic):
    try:
        payload = json.load(stdin)
    except ValueError:
        return 0
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command")
    if not isinstance(command, str):
        return 0
    try:
        removes = command_runs_git_worktree_remove(command)
    except shell_reader.ShellParserUnavailable as error:
        print(shell_reader.parser_unavailable_hook_output(
            "The hook that ships every worktree's records before git worktree remove", error,
            PARSER_UNAVAILABLE_NEXT_STEP_LINES))
        return 0
    if not removes:
        return 0
    deadline = clock() + SHIPPING_BUDGET_SECONDS
    # The same deadline in real seconds, for the worker: an injected clock cannot bound a stalled call.
    wall_deadline = time.monotonic() + SHIPPING_BUDGET_SECONDS
    worktrees, reason = worktrees_listed_or_failure_reason(payload.get("cwd") or os.getcwd(), runner)
    if worktrees is None:
        note_unchecked(WORKTREE_LISTING_FAILED_NOTICE.format(reason=reason))
        return 0
    progress = {"shipped": set(), "lines": {}}
    worker = threading.Thread(target=ship_every_record, args=(worktrees, runner, clock, deadline, progress),
                              daemon=True)
    worker.start()
    worker.join(max(0.0, wall_deadline - time.monotonic()))
    if "error" in progress:
        note_unchecked(RECORDS_NOT_READ_NOTICE.format(reason=progress["error"]))
        return 0
    records = progress.get("records")
    if records is None:
        note_unchecked(RECORDS_NOT_READ_NOTICE.format(
            reason=f"reading them ran past {SHIPPING_BUDGET_SECONDS} seconds"))
        return 0
    # No lock: CPython copies a set or a dict in one step, and a worker still running only adds to them,
    # so a record it ships after this copy is refused, never let through unshipped.
    shipped = set(progress["shipped"])
    lines = dict(progress["lines"])
    unshipped = [(kind[1], worktree, record, lines.get(record) or budget_spent_line())
                 for worktree, kind, record in records if record not in shipped]
    if unshipped:
        deny(shipment_failed_refusal(unshipped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
