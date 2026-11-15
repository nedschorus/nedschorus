#!/usr/bin/env python3
"""UserPromptSubmit and PreToolUse hook: while an emergency stop is in force,
show the emergency-stop file and the rules agent-seats follow to every
agent-session, and refuse every `git push` and `gh pr merge` a Bash call
makes, except the coordinating agent-seat's.

Wired in .claude/settings.json for UserPromptSubmit and for PreToolUse on every
tool, so running work sees a stop at its next tool call. The stop file is read
by emergency-stop-file-in-force-read-common.py.

What it shows:
- In force: the rules and the file, cut to MAX_FILE_CHARACTERS, at every run.
- Newest stop file unreadable: the same rules and why the file could not be
  read; the stop is treated as in force, and no agent-seat is coordinating, so
  every push and merge is refused.
- Log-store unreachable, as on a Mac whose mount of ned-box is gone, or not
  read within READ_DEADLINE_SECONDS, as when that mount hangs: "emergency-stop
  state unknown" once per agent-session, and work continues.
- Lifted: a note saying so and that held-back work resumes, once per
  agent-session for each stop file.
- No stop: nothing.

The refusal matches `git push`, `gh pr merge` with -R or --repo anywhere
before `merge`, and `gh api` with method PUT on a `pulls/<number>/merge` path,
in a Bash call, read by
nc-systems/general-tools/shell-command-tree-sitter-bash-reader-common.py, also
inside a `bash -c` string and inside the remote command of `ssh`; a command the reader cannot read is refused too; a
push made inside another program, or by a scheduled job, is not refused.

The rules the hook shows hold, word for word, the first four rules of the
section "While a stop is in force" of .claude/skills/emergency-stop/SKILL.md;
the hook's test fails when the two drift apart. The agent-seat is GIT_AUTHOR_NAME, which the
launchers export; an agent-session without it is never the coordinating one.

The once-per-agent-session record is a JSON file per session_id under the
temporary directory; when it cannot be read or written the note is shown
again rather than lost. When the hook itself fails, it says so in the
agent-session's context, because Claude Code shows the model neither a
hook's stderr nor its exit status here."""

import importlib.util
import json
import os
import re
import sys
import tempfile
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "emergency_stop_file_in_force_read_common", HERE / "emergency-stop-file-in-force-read-common.py")
common = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(common)
_shell_reader_spec = importlib.util.spec_from_file_location(
    "shell_command_tree_sitter_bash_reader_common",
    HERE.parent.parent / "general-tools" / "shell-command-tree-sitter-bash-reader-common.py")
shell_reader = importlib.util.module_from_spec(_shell_reader_spec)
_shell_reader_spec.loader.exec_module(shell_reader)

MAX_FILE_CHARACTERS = 4000
# Under Claude Code's 30-second hook timeout, so a hung mount gives the state-unknown note, not a killed hook.
READ_DEADLINE_SECONDS = 5
NOTE_RECORD_DIRECTORY_NAME = "nedschorus-emergency-stop-hook-notes"
SESSION_ID_SAFE_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,128}")
GIT_OPTIONS_TAKING_A_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
GH_OPTIONS_TAKING_A_VALUE = {"-R", "--repo"}
GH_API_METHOD_OPTIONS = {"-X", "--method"}
GH_API_PULL_REQUEST_MERGE_PATH = re.compile(r"(^|/)pulls/[^/]+/merge/?$")
PROGRAM_PATH = "nc-systems/skills/emergency-stop/emergency-stop-file-write-start-append-and-stop-lift.py"

RULES = """EMERGENCY STOP in force: {path}
The coordinating agent-seat is {coordinating}; it carries on with the repair.
Every agent-seat follows these rules until the user lifts the emergency stop:
- Unless you are the coordinating agent-seat, finish the tool call you are in, then do no more work until the coordinating agent-seat or the user gives you work.
- If your own running work is what is losing or damaging work, kill your own background tasks now.
- Push and merge nothing unless you are the coordinating agent-seat; this hook refuses `git push` and `gh pr merge` from every other agent-seat.
- Ask the user nothing outside the repair, and show no approval-walk item; an open approval-walk resumes at its `#next_to_present` item after the lift.
- When the user tells you to lift the emergency stop, run the four lines below, with his words unchanged in place of the second line. When the command prints no line opening FAILED, re-enable the schedule, without running the job now, of every scheduled job the repair brief lists as paused, as "Lifting a stop" in .claude/skills/emergency-stop/SKILL.md says.
python3 {program} lift --words="$(cat <<'WORDS'
<his words>
WORDS
)\""""

FILE_HEADING = "The emergency-stop file:"
UNREADABLE_LINE = ("The emergency-stop file {path} cannot be read: {error}. It is treated as an emergency stop "
                   "in force. Tell the user its path and this error; only he repairs or moves that file.")
UNKNOWN_NOTE = ("emergency-stop state unknown: ned-box's log-store cannot be read ({error}). "
                "This hook refuses nothing while it cannot read the log-store, so carry on with your work, "
                "and tell the user that this machine cannot reach ned-box's log-store. "
                "This note is shown once per agent-session.")
LIFTED_NOTE = ("The emergency stop {path} was lifted: {lift_line}\n"
               "Its rules no longer apply: resume the work you held back, and push and merge as usual.")
REFUSAL = ("Refused: an emergency stop is in force ({path}), and during it only the coordinating "
           "agent-seat ({coordinating}) pushes or merges; this agent-seat is {agent_seat}.\n"
           "Leave the work committed locally; pushing and merging resume after the user lifts the emergency stop.\n"
           "If the repair needs this push or merge, commit it on a branch and send the coordinating agent-seat "
           "the branch's name by SendMessage; it pushes and merges it. When no coordinating agent-seat is named, "
           "tell the user instead.")
UNREAD_COMMAND_LINE = "\nThe command could not be read, so it is refused in case it pushes or merges: {error}"
FAILURE_NOTE = ("The emergency-stop hook failed, so whether an emergency stop is in force is unknown: "
                "{error!r}. {what} went ahead without the hook's check.\n"
                "Before you push or merge, run: python3 {program} status\n"
                "If it prints InForce or Unreadable, follow .claude/skills/emergency-stop/SKILL.md.")
WHAT_WENT_AHEAD = {"PreToolUse": "This tool call", "UserPromptSubmit": "This prompt"}


def bash_command_pushes_or_merges(command):
    """Whether a simple command in command, or in a `bash -c` string it runs, is `git push` or `gh pr merge`.

    Raises the shell reader's ShellParserUnavailable when the command cannot be read."""
    for words in shell_reader.simple_commands(command):
        words = list(words)
        index, _ = shell_reader.simple_command_program_index_skipping_wrappers(words)
        if index is None:
            continue
        program, arguments = words[index], words[index + 1:]
        inner = nested_command_string(program, arguments)
        if inner is not None and bash_command_pushes_or_merges(inner):
            return True
        if shell_reader.is_program(program, "gh") and gh_arguments_merge_a_pull_request(arguments):
            return True
        if shell_reader.is_program(program, "git"):
            position = 0
            while position < len(arguments) and arguments[position].startswith("-"):
                position += 2 if arguments[position] in GIT_OPTIONS_TAKING_A_VALUE else 1
            if position < len(arguments) and arguments[position] == "push":
                return True
    return False


def nested_command_string(program, arguments):
    """The command program runs as a string: ssh's remote command, or a shell's -c string; else None."""
    if shell_reader.is_program(program, "ssh"):
        return shell_reader.ssh_remote_command(arguments)
    if any(shell_reader.is_program(program, runner) for runner in shell_reader.SHELL_STRING_RUNNERS):
        return shell_reader.shell_command_string(arguments)
    return None


def gh_words_without_repository_options(arguments):
    """arguments with every -R/--repo option and its value removed."""
    words, position = [], 0
    while position < len(arguments):
        word = arguments[position]
        if word in GH_OPTIONS_TAKING_A_VALUE:
            position += 2
            continue
        if not (word.startswith("--repo=") or (word.startswith("-R") and len(word) > 2)):
            words.append(word)
        position += 1
    return words


def gh_arguments_merge_a_pull_request(arguments):
    """Whether gh's arguments are `pr merge`, with -R or --repo anywhere, or a PUT to the REST merge endpoint."""
    words = gh_words_without_repository_options(arguments)
    if words[:2] == ["pr", "merge"]:
        return True
    if words[:1] != ["api"]:
        return False
    method, merge_path = None, False
    for index, word in enumerate(words[1:], start=1):
        if word in GH_API_METHOD_OPTIONS and index + 1 < len(words):
            method = words[index + 1]
        elif word.startswith("--method="):
            method = word[len("--method="):]
        elif word.startswith("-X") and len(word) > 2:
            method = word[2:]
        elif GH_API_PULL_REQUEST_MERGE_PATH.search(word):
            merge_path = True
    return merge_path and (method or "").upper() == "PUT"


def note_record_path(session_id):
    if not isinstance(session_id, str) or not SESSION_ID_SAFE_PATTERN.fullmatch(session_id):
        return None
    return Path(tempfile.gettempdir()) / NOTE_RECORD_DIRECTORY_NAME / f"{session_id}.json"


def shown_before(record_path, key):
    """Whether this agent-session has seen the note named key; records it as seen."""
    if record_path is None:
        return False
    try:
        seen = json.loads(record_path.read_text(encoding="utf-8"))
        if not isinstance(seen, list):
            seen = []
    except (OSError, ValueError):
        seen = []
    if key in seen:
        return True
    try:
        record_path.parent.mkdir(parents=True, exist_ok=True)
        record_path.write_text(json.dumps(seen + [key]), encoding="utf-8")
    except OSError:
        pass
    return False


def context_output(event, text):
    return json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}},
                      ensure_ascii=False)


def refusal_output(reason):
    return json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                              "permissionDecisionReason": reason}}, ensure_ascii=False)


def read_state_within_deadline(folder, deadline_seconds=READ_DEADLINE_SECONDS, reader=None):
    """common.read_state(folder), or FolderUnreachable when it has not returned within deadline_seconds.

    An error the read raises is raised here, so main() reports the hook as failed."""
    reader = reader or common.read_state
    outcome = {}

    def read():
        try:
            outcome["state"] = reader(folder)
        except BaseException as error:
            outcome["error"] = error

    # A daemon thread, because a read blocked on a hung mount cannot be interrupted, and must not hold the exit.
    worker = threading.Thread(target=read, daemon=True)
    worker.start()
    worker.join(deadline_seconds)
    if "error" in outcome:
        raise outcome["error"]
    if "state" in outcome:
        return outcome["state"]
    return common.FolderUnreachable(folder, f"reading {folder} took longer than {deadline_seconds} seconds")


def output_for(payload, environment, read_state=read_state_within_deadline):
    event = payload.get("hook_event_name") or "UserPromptSubmit"
    state = read_state(common.emergency_stop_folder(environment))
    record_path = note_record_path(payload.get("session_id"))
    if isinstance(state, common.NoStop):
        return None
    if isinstance(state, common.FolderUnreachable):
        if shown_before(record_path, "unknown"):
            return None
        return context_output(event, UNKNOWN_NOTE.format(error=state.error))
    if isinstance(state, common.Lifted):
        if shown_before(record_path, f"lifted:{state.path.name}"):
            return None
        return context_output(event, LIFTED_NOTE.format(path=state.path, lift_line=state.lift_line))
    if isinstance(state, common.InForce):
        coordinating = common.coordinating_agent_seat(state.text)
        body = FILE_HEADING + "\n" + state.text[:MAX_FILE_CHARACTERS]
    else:
        coordinating = None
        body = UNREADABLE_LINE.format(path=state.path, error=state.error)
    agent_seat = environment.get("GIT_AUTHOR_NAME") or "unknown"
    if event == "PreToolUse" and payload.get("tool_name") == "Bash" and agent_seat != coordinating:
        unread = ""
        try:
            pushes_or_merges = bash_command_pushes_or_merges(str((payload.get("tool_input") or {}).get("command", "")))
        except shell_reader.ShellParserUnavailable as error:
            # A command that cannot be read may push or merge, so during a stop it is refused.
            pushes_or_merges, unread = True, UNREAD_COMMAND_LINE.format(error=error)
        if pushes_or_merges:
            return refusal_output(REFUSAL.format(path=state.path, coordinating=coordinating or "none named",
                                                 agent_seat=agent_seat) + unread)
    rules = RULES.format(path=state.path, coordinating=coordinating or "none named", program=PROGRAM_PATH)
    return context_output(event, rules + "\n" + body)


def main():
    payload = {}
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        output = output_for(payload, os.environ)
    except Exception as error:
        event = payload.get("hook_event_name") if isinstance(payload, dict) else None
        event = event if event in WHAT_WENT_AHEAD else "UserPromptSubmit"
        print(context_output(event, FAILURE_NOTE.format(error=error, what=WHAT_WENT_AHEAD[event],
                                                         program=PROGRAM_PATH)))
        return 0
    if output is not None:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
