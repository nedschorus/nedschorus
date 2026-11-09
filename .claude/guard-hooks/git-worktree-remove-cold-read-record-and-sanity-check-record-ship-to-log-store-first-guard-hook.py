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

A record whose being-written lock a running program holds, as the
cold-read-grid holds its record's for the 14 to 44 minutes of a
cold-read-full-run, is not shipped: that program rewrites files it has
already written, so a shipment now would make its own shipment, and every
later one, refuse the record, and the program ships the record itself when it
finishes. Such a record refuses the removal only when the command removes
the worktree it is in, because the removal would delete it first. When the
command is that one `git worktree remove` and nothing else, so that the shell
surely runs it, the hook defers the removal: for each such worktree it starts, detached, the
waiter GIT_WORKTREE_REMOVE_DEFERRED_WAITER_SCRIPT, which waits until no record in the
worktree is being written, ships the worktree's records, runs `git worktree
remove` on it, with -f when that removal gave -f or --force, and writes a
user-alert when that fails. Before starting it the hook takes an flock on the
worktree's directory and hands the descriptor to the waiter, which holds it
until it exits; when another process already holds that flock, a waiter
already waits on the worktree, and the hook starts none. Each waiter's output
goes to a log file of its own in GIT_WORKTREE_REMOVE_DEFERRED_WAITER_LOG_STORE_DIRECTORY_NAME in
the log-store, which on the Mac the hook writes through its mount of ned-box's
home.

The hook finds the worktree a `git worktree remove` names as git does: a path
argument that is the end of exactly one worktree's path, starting at a
directory boundary, names that worktree; otherwise the argument, resolved
against the hook's cwd and any -C before `worktree`, is compared with each
worktree's real path. When it cannot tell, because the path or a -C holds a
variable, a glob or a substitution, `worktree remove` is given an option
other than -f or --force or more than one path, or the command changes
directory before a path that depends on it, the hook refuses the removal
while any record is being written, starts no waiter, and asks for the path
written out in full, with -f when the command gave -f or --force. A removal
of a worktree in which a record is being written, in a command that does more
than that removal, as in `git push && git worktree remove /wt`, gets the same
refusal and starts no waiter, because the hook cannot tell whether the shell
would run the removal.

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
no record. Every shipment, whichever shipper runs it, adds the record's files
to the store and checks them by reading them back, and it replaces only two
store files, each by a rename that leaves the old file or the new one, never
part of either: the record's triage file, cold-read-triage.md or triage.md,
when the record's copy differs; and the README.md at the store's root, when
it differs from the text the shipper holds.

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
skips the records already shipped. When the worktree's directory cannot be
opened, the log file cannot be written, as on the Mac while ned-box's home is
not mounted, or the waiter cannot be started, the refusal says the removal was
not deferred and sends the agent to the user. The waiter's own failures are
in its docstring.

The messages follow
docs/nedschorus-wiki/nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md.
"""

import fcntl
import importlib.util
import json
import os
import pathlib
import re
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

_ned_box_home_spec = importlib.util.spec_from_file_location(
    "ned_box_home_directory_and_its_mac_mount_point_path_constants_common",
    REPOSITORY_ROOT / "nc-systems" / "general-tools" / "ned-box-home-directory-and-its-mac-mount-point-path-constants-common.py")
ned_box_home_paths = importlib.util.module_from_spec(_ned_box_home_spec)
_ned_box_home_spec.loader.exec_module(ned_box_home_paths)

CLEAN_WORKTREES_SCRIPT = REPOSITORY_ROOT / "scripts" / "clean-worktrees.py"
GIT_WORKTREE_REMOVE_DEFERRED_WAITER_SCRIPT = (
    REPOSITORY_ROOT / "nc-systems" / "general-tools"
    / "git-worktree-remove-deferred-until-cold-read-record-and-sanity-check-record-being-written-locks-release-then-ship-to-log-store-waiter.py")
GIT_WORKTREE_REMOVE_DEFERRED_WAITER_LOG_STORE_DIRECTORY_NAME = (
    "git-worktree-remove-deferred-until-cold-read-record-and-sanity-check-record-being-written-locks-release-then-ship-to-log-store-waiter-run-logs")

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
RECORD_BEING_WRITTEN_LINE_TEMPLATE = "Record {record} (worktree {worktree})\n"
RECORD_BEING_WRITTEN_IN_REMOVED_WORKTREE_REFUSAL_TEMPLATE = (
    "Refused on purpose: this command removes a worktree in which a running program, such as the "
    "cold-read-grid, is still writing a record. That program holds the record's being-written lock "
    "and ships the record to the log-store itself when it finishes; removing the worktree now would "
    "delete the record first.\n"
    "{records}"
    "{ending}")
REMOVAL_DEFERRED_ENDING = (
    "This hook has deferred the removal: a program waits until every record above is finished, ships "
    "the records, removes the worktree, and tells the user if that fails. You have nothing to do for the "
    "removal. If your command did anything else, none of it ran: run again now only the parts that do "
    "not need this worktree gone.")
REMOVAL_NOT_DEFERRED_ENDING_TEMPLATE = (
    "This hook could not defer the removal, so no program will remove the worktree once the record is "
    "finished: {failures}.\n"
    f"Leave the worktree in place, stop, and {TELL_THE_USER_OR_DISPATCHING_AGENT} that `git worktree "
    "remove` is refused while a program writes a record in that worktree, and that this hook could not "
    "defer the removal, quoting each Record line above, and the reason after \"once the record is "
    "finished:\", word for word.")
REMOVAL_NOT_DEFERRED_FAILURE_TEMPLATE = "for {worktree}, {error}"
REMOVED_WORKTREE_UNRESOLVED_REFUSAL_TEMPLATE = (
    "Refused on purpose: this hook could not tell which worktree this command removes ({reason}), "
    "and a running program, such as the cold-read-grid, is still writing a record in a worktree. "
    "That program ships the record to the log-store itself when it finishes; removing its worktree "
    "now would delete the record first.\n"
    "{records}"
    "Run the removal again as `git worktree remove{force} <path>`, with the worktree's path written "
    "out in full, as an absolute path with no variable, in a command that does not change directory.")
GIT_WORKTREE_REMOVE_NOT_THE_WHOLE_SHELL_COMMAND_REFUSAL_REASON = (
    "the command does more than the removal, so this hook cannot tell whether the shell runs the removal")
# A word the shell would still expand: a variable, a substitution or a glob.
UNEXPANDED_WORD_PATTERN = re.compile(r"[$`*?[]|\{\}")
DIRECTORY_CHANGING_PROGRAMS = ("cd", "pushd", "popd")
# The wrapper options that run the program in another directory, as in `env -C /a git ...`.
DIRECTORY_CHANGING_WRAPPER_OPTIONS = {"env": ("-C", "--chdir"), "sudo": ("-D", "--chdir")}
WORKTREE_REMOVE_FORCE_OPTIONS = {"-f", "--force"}

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


def worktree_remove_force_given(words, index):
    """True when the `git ... worktree remove ...` whose git is words[index] gives -f or --force before any --."""
    index += 1
    while index < len(words) and words[index].startswith("-"):
        index += 2 if words[index] in GIT_GLOBAL_VALUE_FLAGS else 1
    for word in words[index + 2:]:
        if word == "--":
            return False
        if word in WORKTREE_REMOVE_FORCE_OPTIONS:
            return True
    return False


def shell_command_runs_git_worktree_remove_with_force_option(command):
    """True when a `git worktree remove` in the command, or in a bash, sh or zsh -c string in it, gives -f or --force."""
    for words in shell_reader.simple_commands(command):
        index, _ = shell_reader.simple_command_program_index_skipping_wrappers(words)
        if index is None:
            continue
        if is_git_worktree_remove(words) and worktree_remove_force_given(words, index):
            return True
        if any(is_program(words[index], runner) for runner in shell_reader.SHELL_STRING_RUNNERS):
            inner = shell_reader.shell_command_string(words[index + 1:])
            if inner is not None and shell_command_runs_git_worktree_remove_with_force_option(inner):
                return True
    return False


def shell_command_is_one_git_worktree_remove_and_nothing_else(command):
    """True when the whole command is one `git worktree remove` simple command, which the shell always runs:
    no list, condition, loop, redirection, substitution or bash -c around it or in it.

    False when the parser can only run in a new process, as this needs the syntax tree itself.
    """
    try:
        root = shell_reader.parser().parse(command.encode("utf-8", "surrogateescape")).root_node
    except shell_reader.ShellParserUnavailable:
        return False
    statements = [node for node in root.named_children if node.type != "comment"]
    if root.has_error or len(statements) != 1 or statements[0].type != "command":
        return False
    commands = list(shell_reader.simple_commands(command))
    return len(commands) == 1 and is_git_worktree_remove(commands[0])


def worktree_named_by_path_suffix(argument, worktrees):
    """The one worktree whose path ends with the argument, starting at a directory boundary, or None:
    the first way git's find_worktree finds the worktree `git worktree remove <argument>` names."""
    if not argument:
        return None
    named = [worktree for worktree in worktrees
             if str(worktree).endswith(argument)
             and (len(str(worktree)) == len(argument) or str(worktree)[-len(argument) - 1] == "/")]
    return named[0] if len(named) == 1 else None


def worktree_named_by_real_path(path, worktrees):
    """The worktree whose real path is the real path of path, or None: git's second way."""
    named = os.path.realpath(path)
    return next((worktree for worktree in worktrees if os.path.realpath(worktree) == named), None)


def removal_path_argument_and_path_or_unresolved_reason(words, index):
    """For the `git ... worktree remove ...` whose git is words[index]: (the path argument, that
    path joined to each -C before it, None), (None, None, None) for a removal naming no path, or
    (None, None, why the hook cannot tell). The joined path is relative when it depends on the cwd."""
    directories = []
    index += 1
    while index < len(words) and words[index].startswith("-"):
        if words[index] == "-C" and index + 1 < len(words):
            if UNEXPANDED_WORD_PATTERN.search(words[index + 1]):
                return None, None, f"the -C directory {words[index + 1]} holds a variable, a glob or a substitution"
            directories.append(shell_reader.shell_word_tilde_prefix_expand_as_bash_would(words[index + 1]))
        index += 2 if words[index] in GIT_GLOBAL_VALUE_FLAGS else 1
    paths = []
    options_ended = False
    for word in words[index + 2:]:
        if not options_ended and word == "--":
            options_ended = True
        elif not options_ended and word in WORKTREE_REMOVE_FORCE_OPTIONS:
            continue
        elif not options_ended and word.startswith("-"):
            return None, None, f"`worktree remove` is given the option {word}"
        else:
            paths.append(word)
    if len(paths) > 1:
        return None, None, f"`worktree remove` is given {len(paths)} paths"
    if not paths:
        return None, None, None
    if UNEXPANDED_WORD_PATTERN.search(paths[0]):
        return None, None, f"the path {paths[0]} holds a variable, a glob or a substitution"
    argument = shell_reader.shell_word_tilde_prefix_expand_as_bash_would(paths[0])
    return argument, os.path.join(*directories, argument), None


def simple_command_changes_directory(words):
    """True for cd, pushd or popd, and for a command run by a wrapper option such as env -C."""
    index, _ = shell_reader.simple_command_program_index_skipping_wrappers(words)
    if index is not None and any(is_program(words[index], name) for name in DIRECTORY_CHANGING_PROGRAMS):
        return True
    for wrapper, options in shell_reader.simple_command_wrapper_options_and_values_parsed_from_words(words):
        changing = DIRECTORY_CHANGING_WRAPPER_OPTIONS.get(wrapper, ())
        # A short option may carry its value attached, as in env -C/a.
        if any(option in changing or (option[:2] in changing and not option.startswith("--"))
               for option, _ in options):
            return True
    return False


def worktrees_removed_or_unresolved_reason(command, cwd, worktrees, outer_command_changes_directory=False):
    """Return ({worktree the command removes: whether a removal of it gives -f or --force}, None),
    or (None, why the hook cannot tell).

    A path that depends on the cwd is unresolved in a command that changes directory anywhere,
    because the hook does not follow the directory changes; a bash -c string inherits that
    from the command that runs it.
    """
    commands = list(shell_reader.simple_commands(command))
    changes_directory = outer_command_changes_directory or any(
        simple_command_changes_directory(words) for words in commands)
    removed = {}
    for words in commands:
        index, _ = shell_reader.simple_command_program_index_skipping_wrappers(words)
        if index is None:
            continue
        if any(is_program(words[index], runner) for runner in shell_reader.SHELL_STRING_RUNNERS):
            inner = shell_reader.shell_command_string(words[index + 1:])
            if inner is None:
                continue
            inner_removed, reason = worktrees_removed_or_unresolved_reason(
                inner, cwd, worktrees, changes_directory)
            if reason is not None:
                return None, reason
            for worktree, force in inner_removed.items():
                removed[worktree] = removed.get(worktree, False) or force
            continue
        if not is_git_worktree_remove(words):
            continue
        argument, path, reason = removal_path_argument_and_path_or_unresolved_reason(words, index)
        if reason is not None:
            return None, reason
        if argument is None:
            continue
        worktree = worktree_named_by_path_suffix(argument, worktrees)
        if worktree is None:
            if changes_directory and not os.path.isabs(path):
                return None, f"the command changes directory, and the path {argument} is relative"
            worktree = worktree_named_by_real_path(os.path.join(cwd, path), worktrees)
        if worktree is not None:
            removed[worktree] = removed.get(worktree, False) or worktree_remove_force_given(words, index)
    return removed, None


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
    progress["shipped"] each record that shipped or needed no shipping, to progress["being_written"] each
    left unshipped because a running program holds its being-written lock, and to progress["lines"] the
    reason line of each that did not ship. An error before every worktree's records are read goes in
    progress["error"]."""
    try:
        kinds = record_kinds()
        progress["records"] = [(worktree, kind, record) for worktree in dict.fromkeys(worktrees)
                               for kind, record in records_in(worktree, kinds)]
    except Exception as error:
        progress["error"] = f"{type(error).__name__}: {error}"
        return
    for worktree, kind, record in progress["records"]:
        try:
            if kind[2].record_directory_being_written_lock_is_held_by_any_process(record):
                progress["being_written"].append((worktree, record))
                continue
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


def ned_box_home_as_this_machine_reaches_it():
    """ned-box's home directory on ned-box, and the Mac's mount of it on the Mac."""
    if sys.platform == "linux":
        return Path(ned_box_home_paths.NED_BOX_HOME)
    return Path(ned_box_home_paths.MAC_MOUNT_OF_NED_BOX_HOME)


def git_worktree_remove_deferred_waiter_start_unless_one_already_waits(worktree, force, records, git_directory,
                                                   ned_box_home=None, waiter_options=()):
    """Start the waiter that removes the worktree once no record in it is being written, unless one waits on it already.

    Returns None when a waiter now waits on the worktree, this one or an earlier one, else why none could start.
    The flock on the worktree's directory, taken here and handed to the waiter, is what tells the next call
    that a waiter waits; taking it before the start leaves no moment in which two calls both find none.
    """
    ned_box_home = Path(ned_box_home or ned_box_home_as_this_machine_reaches_it())
    try:
        descriptor = os.open(worktree, os.O_RDONLY)
    except OSError as error:
        return f"its directory could not be opened: {error}"
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return None
        log_directory = ned_box_home / "nedschorus-logs" / GIT_WORKTREE_REMOVE_DEFERRED_WAITER_LOG_STORE_DIRECTORY_NAME
        log_directory.mkdir(parents=True, exist_ok=True)
        log_path = log_directory / f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{Path(worktree).name}-{os.getpid()}.log"
        command = [sys.executable, str(GIT_WORKTREE_REMOVE_DEFERRED_WAITER_SCRIPT), "--worktree", str(worktree),
                   "--git-directory", str(git_directory), "--ned-box-home", str(ned_box_home),
                   "--log-file", str(log_path), *(["--force"] if force else [])]
        for record in records:
            command += ["--record", str(record)]
        # Its standard streams go to the log, not to the hook's: Claude Code waits for the hook's to close.
        with open(log_path, "a", encoding="utf-8") as log_file:
            subprocess.Popen(command + list(waiter_options), stdin=subprocess.DEVNULL, stdout=log_file,
                             stderr=subprocess.STDOUT, start_new_session=True, pass_fds=(descriptor,))
    except OSError as error:
        return f"the waiter could not be started: {error}"
    finally:
        os.close(descriptor)
    return None


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


def main(stdin=sys.stdin, runner=subprocess.run, clock=time.monotonic, start_waiter=None):
    start_waiter = start_waiter or git_worktree_remove_deferred_waiter_start_unless_one_already_waits
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
    progress = {"shipped": set(), "lines": {}, "being_written": []}
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
    being_written = list(progress["being_written"])
    left_to_their_writers = {record for _, record in being_written}
    unshipped = [(kind[1], worktree, record, lines.get(record) or budget_spent_line())
                 for worktree, kind, record in records
                 if record not in shipped and record not in left_to_their_writers]
    refusals = [shipment_failed_refusal(unshipped)] if unshipped else []
    if being_written:
        removed, unresolved = worktrees_removed_or_unresolved_reason(
            command, payload.get("cwd") or os.getcwd(), worktrees)
        in_removed = [(worktree, record) for worktree, record in being_written
                      if unresolved is not None or worktree in removed]
        listed = "".join(RECORD_BEING_WRITTEN_LINE_TEMPLATE.format(record=record, worktree=worktree)
                         for worktree, record in in_removed)
        if unresolved is None and in_removed and not shell_command_is_one_git_worktree_remove_and_nothing_else(command):
            unresolved = GIT_WORKTREE_REMOVE_NOT_THE_WHOLE_SHELL_COMMAND_REFUSAL_REASON
        if unresolved is not None:
            refusals.append(REMOVED_WORKTREE_UNRESOLVED_REFUSAL_TEMPLATE.format(
                reason=unresolved, records=listed,
                force=" -f" if shell_command_runs_git_worktree_remove_with_force_option(command) else ""))
        elif in_removed:
            failures = []
            for worktree in dict.fromkeys(worktree for worktree, _ in in_removed):
                error = start_waiter(worktree, removed[worktree],
                                     [record for held_in, record in in_removed if held_in == worktree],
                                     worktrees[0])
                if error is not None:
                    failures.append(REMOVAL_NOT_DEFERRED_FAILURE_TEMPLATE.format(worktree=worktree, error=error))
            ending = (REMOVAL_NOT_DEFERRED_ENDING_TEMPLATE.format(failures="; ".join(failures)) if failures
                      else REMOVAL_DEFERRED_ENDING)
            refusals.append(RECORD_BEING_WRITTEN_IN_REMOVED_WORKTREE_REFUSAL_TEMPLATE.format(
                records=listed, ending=ending))
    if refusals:
        deny("\n\n".join(refusals))
    return 0


if __name__ == "__main__":
    sys.exit(main())
