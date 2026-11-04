#!/usr/bin/env python3
"""Ship a worktree's cold-read-records and sanity-check records to the log-store before `git worktree remove` deletes them.

Both record folders, cold-read-records/ and sanity-check-records/, are
gitignored, so `git worktree remove` deletes them without a word. Before a
Bash command that removes a worktree runs, this PreToolUse hook runs the
shipper of each record kind on each non-empty record directory in that
worktree: the shippers, and the way each is called, are the ones
scripts/clean-worktrees.py uses (LOG_STORE_RECORD_SHIPPERS), loaded from
that file so the two stay one list. The shippers are add-only, so a record
already in the log-store ships as "nothing new".

It allows the command silently when every record shipped or the worktree
holds none. It refuses the command, naming each record that did not ship,
the shipper's own line and the command that ships it again, when a shipper
exits nonzero (FAILED or REFUSED), prints nothing, or has not finished when
SHIPPING_BUDGET_SECONDS run out; .claude/settings.json gives the hook a
longer timeout than that budget, because a hook that overruns its timeout
lets the command through unchecked and reports nothing.

What it reads: every simple command, through the shared shell module on
tree-sitter-bash, whose program, after wrappers such as env and timeout, is
git with the subcommand `worktree remove`; the directory git runs in is the
hook's cwd, changed by a literal cd before it, an env -C or sudo -D wrapper,
and git's -C. The command string of bash, sh or zsh -c is read the same way.
A `$NAME` or `${NAME}` in the worktree path, a cd directory or a -C
directory is replaced by the value a literal NAME=value anywhere in the
command text gives it, the last such assignment winning, since the shell
reader does not return bare assignments; this ignores order and scope, so a
variable assigned twice can be read as the wrong path, which ships the
wrong worktree's records and leaves the removed one's unshipped. A path
still holding an expansion, such as a loop variable or a command
substitution, cannot be read: the command is let through, and the agent is
told in additionalContext that its records were not shipped. Refusing it
instead would stop the many scripted removals of scratch worktrees agents
run. A worktree path that is not a directory is looked up as git does, as
the last path components of one worktree `git worktree list` names; a path
that names no worktree is let through, since git refuses it too. Not read:
the remote command of ssh, commands run by eval or a script file, removals a
program makes itself, and removals typed in a terminal or by a Codex agent.
Walk files under docs/walk/, which scripts/clean-worktrees.py also ships,
are not shipped here.

When the shell reader cannot run, the command is let through unchecked and
the hook says so in additionalContext.

The messages follow
docs/nedschorus-wiki/nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md.
"""

import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
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

GIT_GLOBAL_VALUE_OPTIONS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env",
                            "--exec-path"}
WRAPPER_DIRECTORY_OPTIONS = {("env", "-C"), ("env", "--chdir"), ("sudo", "-D"), ("sudo", "--chdir")}
# A word the shell expands at run time; the reader keeps it as written.
UNREADABLE_WORD_PATTERN = re.compile(r"[$`*?\[]")
LITERAL_ASSIGNMENT_PATTERN = re.compile(
    r"""(?:^|(?<=[\s;&|(]))(?:export\s+|declare\s+-x\s+|local\s+)?([A-Za-z_][A-Za-z0-9_]*)="""
    r"""("[^"`]*"|'[^']*'|[^\s;&|`'"()<>]*)""")
VARIABLE_REFERENCE_PATTERN = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))")

_next_step_lines_spec = importlib.util.spec_from_file_location(
    "failed_command_agent_facing_message_rerun_once_then_stop_and_report_lines_common",
    REPOSITORY_ROOT / "nc-systems" / "general-tools"
    / "failed-command-agent-facing-message-rerun-once-then-stop-and-report-lines-common.py")
next_step_lines = importlib.util.module_from_spec(_next_step_lines_spec)
_next_step_lines_spec.loader.exec_module(next_step_lines)
TELL_THE_USER_OR_DISPATCHING_AGENT = "tell " + next_step_lines.REPORT_RECIPIENT_PHRASE_USER_OR_DISPATCHING_AGENT

SHIPMENT_FAILED_REFUSAL_TEMPLATE = (
    "Refused on purpose: this `git worktree remove` would delete {count} record(s) in {worktree} "
    "that did not reach the log-store. The folders cold-read-records/ and sanity-check-records/ "
    "are gitignored, so removing the worktree deletes them for good, and the log-store on ned-box "
    "is the only other place a record is kept.\n"
    "{records}"
    "If a Record line says the log-store or ned-box could not be reached, leave the worktree in "
    f"place, stop, and {TELL_THE_USER_OR_DISPATCHING_AGENT} "
    "that the worktree {worktree} is kept because records in it could not be shipped to the "
    "log-store, quoting each Record line above word for word.\n"
    "Otherwise, first run any command a Record line gives, such as an `mv` to a free name; you "
    "need not run the \"Shipped with\" commands, because this hook runs them itself. Then run "
    "your `git worktree remove` command again, once.\n"
    f"If this hook refuses it again, leave the worktree in place, stop, and {TELL_THE_USER_OR_DISPATCHING_AGENT} "
    "that the worktree {worktree} is kept "
    "because records in it could not be shipped to the log-store, quoting each Record line of "
    "the second refusal word for word."
)
UNSHIPPED_RECORD_LINE_TEMPLATE = (
    "Record {record}: {line}\n"
    "  Shipped with: {command}\n"
)
SHIPPER_PRINTED_NOTHING_LINE_TEMPLATE = "the shipper printed nothing (exit {code}){stderr}"
SHIPPING_BUDGET_SPENT_LINE_TEMPLATE = (
    "not shipped: this hook's limit of {budget} seconds for shipping ran out first")

UNREADABLE_WORKTREE_PATH_NOTICE = (
    "Not checked: the hook that ships a worktree's cold-read-records and sanity-check records to "
    "the log-store before `git worktree remove` could not read {word} in this command, so it did "
    "not ship them, and let the command run. If the removed worktree held a record that had not "
    "shipped, that record is gone; nothing can bring it back.\n"
    "From now on, write out the path of the worktree each `git worktree remove` removes, one "
    "command per worktree rather than a loop, or set the path earlier in the same command, as in "
    "`W=<path>; git worktree remove \"$W\"`, with no variable in <path>, so this hook can ship "
    "the worktree's records first."
)

PARSER_UNAVAILABLE_NEXT_STEP_LINES = (
    "If the command removed a git worktree, the cold-read-records and sanity-check records in it "
    "were not shipped to the log-store first, and are gone unless they had shipped before.\n"
    "Before you remove another worktree, ship its records yourself, from that worktree's root, "
    "with this command: `python3 nc-systems/cold-read/cold-read-record-ship.py --all && "
    "python3 scripts/sanity-check-record-ship.py --all`\n"
    "If it exits 0, remove the worktree.\n"
    f"If it exits nonzero, leave the worktree in place, and {TELL_THE_USER_OR_DISPATCHING_AGENT} "
    "which worktree is kept, quoting each line that begins FAILED or REFUSED.")


def variables_substituted(word, variables):
    """Return word with each $NAME and ${NAME} replaced from variables; a name not there stays as written."""
    substituted = VARIABLE_REFERENCE_PATTERN.sub(
        lambda match: variables.get(match.group(1) or match.group(2), match.group(0)), word)
    if substituted == word:
        return word
    # A ~ the shell would expand stays marked only on a word nothing was put into.
    return os.path.expanduser(substituted) if substituted.startswith("~/") else substituted


def literal_shell_variables(command):
    """Return {NAME: value} for each NAME=value in the command text whose value holds no expansion once
    the earlier assignments are put in; a later assignment wins, and one left holding an expansion
    removes the name."""
    variables = {}
    for name, value in LITERAL_ASSIGNMENT_PATTERN.findall(command):
        if value.startswith("'"):
            variables[name] = value[1:-1]
            continue
        if value.startswith('"'):
            value = value[1:-1]
        elif value == "~" or value.startswith("~/"):
            value = os.path.expanduser(value)
        value = variables_substituted(value, variables)
        if UNREADABLE_WORD_PATTERN.search(value):
            variables.pop(name, None)
        else:
            variables[name] = value
    return variables


def directory_joined(base, target):
    """Return target with a ~ bash expands expanded, taken relative to base when base is given."""
    target = shell_reader.shell_word_tilde_prefix_expand_as_bash_would(target)
    return target if base is None else os.path.join(base, target)


def directory_a_wrapper_sets(words):
    """Return the directory the wrappers in front of the program run it in, or None."""
    directory = None
    for wrapper, options in shell_reader.simple_command_wrapper_options_and_values_parsed_from_words(words):
        own = [value for option, value in options if (wrapper, option) in WRAPPER_DIRECTORY_OPTIONS]
        if own and own[-1] is not None:
            directory = directory_joined(directory, own[-1])
    return directory


def worktree_remove_directory_and_targets(words):
    """For `git ... worktree remove ...`, return (directory override or None, [worktree word]); else None."""
    index, _ = shell_reader.simple_command_program_index_skipping_wrappers(words)
    if index is None or not is_program(words[index], "git"):
        return None
    directory = directory_a_wrapper_sets(words)
    index += 1
    while index < len(words) and words[index].startswith("-"):
        word = words[index]
        if word == "-C" and index + 1 < len(words):
            directory = directory_joined(directory, words[index + 1])
        elif word.startswith("-C") and len(word) > 2:
            directory = directory_joined(directory, word[2:])
            index += 1
            continue
        index += 2 if word in GIT_GLOBAL_VALUE_OPTIONS else 1
    if words[index:index + 2] != ["worktree", "remove"]:
        return None
    targets = []
    options_ended = False
    for word in words[index + 2:]:
        if not options_ended and word == "--":
            options_ended = True
        elif options_ended or not word.startswith("-"):
            targets.append(word)
    return directory, targets


def worktree_removals_in_command(command, working_directory, variables=None):
    """Return (directory, worktree word, unreadable word or None) for each worktree the command removes.

    Reads only the command text: nothing here touches the file system, so a replay of recorded
    commands gives the same answer on any machine. directory is where git runs; every value is a
    plain str.
    """
    variables = {**(variables or {}), **literal_shell_variables(command)}
    # A child shell's cd does not change the directory of the shell around it.
    directories = {(): (working_directory, None)}
    removals = []
    for words in shell_reader.simple_commands(command):
        shells = words.child_shell
        enclosing = shells
        while enclosing not in directories:
            enclosing = enclosing[:-1]
        directory, unreadable = directories[enclosing]
        index, _ = shell_reader.simple_command_program_index_skipping_wrappers(words)
        if index is None:
            continue
        program, arguments = words[index], words[index + 1:]
        if is_program(program, "cd"):
            # The last word, so that an option such as -P is not read as the directory.
            target = variables_substituted(arguments[-1], variables) if arguments else "~"
            if UNREADABLE_WORD_PATTERN.search(target):
                directories[shells] = (directory, str(target))
            else:
                directories[shells] = (os.path.normpath(directory_joined(directory, target)), None)
            continue
        if any(is_program(program, runner) for runner in shell_reader.SHELL_STRING_RUNNERS):
            inner = shell_reader.shell_command_string(arguments)
            if inner is not None:
                removals.extend((inner_directory, word, unreadable or inner_unreadable)
                                for inner_directory, word, inner_unreadable
                                in worktree_removals_in_command(inner, directory, variables))
            continue
        found = worktree_remove_directory_and_targets(words)
        if found is None:
            continue
        override, targets = found
        git_directory = directory
        if override is not None:
            override = variables_substituted(override, variables)
            if UNREADABLE_WORD_PATTERN.search(override):
                unreadable = unreadable or str(override)
            else:
                git_directory = os.path.normpath(directory_joined(directory, override))
        for target in targets:
            target = variables_substituted(target, variables)
            target_unreadable = unreadable or (str(target) if UNREADABLE_WORD_PATTERN.search(target) else None)
            removals.append((str(git_directory), str(directory_joined(None, target)), target_unreadable))
    return removals


def worktree_directory(directory, word, runner):
    """Return the worktree directory git would remove for word run in directory, or None.

    git takes a path, or the last path components of one worktree's path.
    """
    path = Path(directory_joined(directory, word))
    if path.is_dir():
        return path.resolve()
    try:
        listing = runner(["git", "-C", str(directory), "worktree", "list", "--porcelain", "-z"],
                         capture_output=True, timeout=GIT_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if listing.returncode != 0:
        return None
    suffix = "/" + word.strip("/")
    matches = [record.path for record in git_output.worktree_records(listing.stdout)
               if record.path.endswith(suffix)]
    return Path(matches[0]) if len(matches) == 1 and Path(matches[0]).is_dir() else None


def clean_worktrees_module():
    spec = importlib.util.spec_from_file_location("clean_worktrees", CLEAN_WORKTREES_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def records_in(worktree, clean_worktrees):
    """Return (shipper, record directory) for each non-empty record directory in the worktree."""
    records = []
    for directory_name, shipper in clean_worktrees.LOG_STORE_RECORD_SHIPPERS:
        records_directory = worktree / directory_name
        if records_directory.is_dir():
            records.extend((shipper, record) for record in sorted(records_directory.iterdir())
                           if record.is_dir() and any(record.iterdir()))
    return records


def shipper_line(shipment):
    """The one line the shipper printed, or its exit code and last stderr line when it printed none."""
    line = shipment.stdout.strip()
    if line:
        return line
    error_lines = shipment.stderr.strip().splitlines()
    return SHIPPER_PRINTED_NOTHING_LINE_TEMPLATE.format(
        code=shipment.returncode, stderr=f": {error_lines[-1]}" if error_lines else "")


def unshipped_records(records, runner, clock, deadline):
    """Ship each record; return (shipper, record, line) for each that did not ship."""
    budget_spent_line = SHIPPING_BUDGET_SPENT_LINE_TEMPLATE.format(budget=SHIPPING_BUDGET_SECONDS)
    unshipped = []
    for shipper, record in records:
        remaining = deadline - clock()
        if remaining <= 0:
            unshipped.append((shipper, record, budget_spent_line))
            continue
        try:
            shipment = runner([sys.executable, str(shipper), str(record)],
                              capture_output=True, text=True, timeout=remaining, check=False)
        except subprocess.TimeoutExpired:
            unshipped.append((shipper, record, budget_spent_line))
            continue
        if shipment.returncode != 0 or not shipment.stdout.strip():
            unshipped.append((shipper, record, shipper_line(shipment)))
    return unshipped


def shipment_failed_refusal(worktree, unshipped):
    lines = "".join(UNSHIPPED_RECORD_LINE_TEMPLATE.format(
        record=record, line=line, command=shlex.join(["python3", str(shipper), str(record)]))
        for shipper, record, line in unshipped)
    return SHIPMENT_FAILED_REFUSAL_TEMPLATE.format(count=len(unshipped), worktree=worktree, records=lines)


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
    working_directory = payload.get("cwd") or os.getcwd()
    try:
        removals = worktree_removals_in_command(command, working_directory)
    except shell_reader.ShellParserUnavailable as error:
        print(shell_reader.parser_unavailable_hook_output(
            "The hook that ships a worktree's records before git worktree remove", error,
            PARSER_UNAVAILABLE_NEXT_STEP_LINES))
        return 0
    if not removals:
        return 0
    deadline = clock() + SHIPPING_BUDGET_SECONDS
    clean_worktrees = clean_worktrees_module()
    refusals = []
    unreadable_words = []
    for directory, word, unreadable in removals:
        if unreadable is not None:
            unreadable_words.append(unreadable)
            continue
        worktree = worktree_directory(directory, word, runner)
        if worktree is None:
            continue
        unshipped = unshipped_records(records_in(worktree, clean_worktrees), runner, clock, deadline)
        if unshipped:
            refusals.append(shipment_failed_refusal(worktree, unshipped))
    if refusals:
        deny("\n\n".join(refusals))
    elif unreadable_words:
        note_unchecked(UNREADABLE_WORKTREE_PATH_NOTICE.format(word=unreadable_words[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
