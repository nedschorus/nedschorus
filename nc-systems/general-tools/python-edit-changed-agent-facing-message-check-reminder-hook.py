#!/usr/bin/env python3
"""After an agent's Edit, MultiEdit or Write of a Python file in the repository,
list the agent-facing-messages the tool call added or changed, tell the agent
to check each against the page on writing them, and give each listed message
its cold-read-fast-read command: the hook writes each message's text to a file
of its own under the temporary directory, because cold-read-fast-read.py reads
only files, and the file's name becomes the cold-read-record's name.

Each target file is named by the source file's repository-relative path and a
digest of the message's text alone, in one directory under the temporary
directory. The hook writes a target file only when it is missing, and never
removes one, so a command reads the text its reminder listed for as long as the
temporary directory keeps the file; a rewritten message gets a new file and a
new command.

A PostToolUse hook: the act has happened, and the agent rewrites any message
that fails the page. The reminder goes in hookSpecificOutput.additionalContext,
which the agent reads next; a PostToolUse hook's plain stdout reaches only the
debug log.

Which strings are agent-facing-messages is decided by
python-source-agent-facing-string-collector-common.py, which also says which
files are tests; a test file gets no reminder. A message counts as added or
changed when the tool call wrote one of the message's lines and the file at
HEAD holds no message with the same text, so code moved or re-indented around
an unchanged message brings no reminder. For an Edit or a MultiEdit, the
written lines are the "+" lines of tool_response.structuredPatch, plus any gap
a "-" line left inside a message, so a message shortened by a deleted line
counts; a Write wrote every line. A message the tool call removed needs no
reminder.

The hook never blocks, and main always exits 0; the two modules loaded below
run before main, so a missing or broken module exits 1 with a traceback, which
Claude Code treats as a non-blocking error. When it cannot inspect the file,
because the payload has no usable structuredPatch, the file cannot be read, git
cannot read HEAD or the hook itself fails, the agent is told that no message
was listed and to check its changed messages by hand. A file that does not
parse mid-edit is told the same, as an ordinary case.

The repository is the checkout holding the payload's cwd; CLAUDE_PROJECT_DIR
can name a different checkout in a forked agent-session. git runs from the
edited file's own directory, so a file in a worktree nested inside the
checkout is compared with that worktree's HEAD.
"""

import ast
import hashlib
import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

_collector_spec = importlib.util.spec_from_file_location(
    "python_source_agent_facing_string_collector_common",
    Path(__file__).resolve().with_name("python-source-agent-facing-string-collector-common.py"))
collector = importlib.util.module_from_spec(_collector_spec)
_collector_spec.loader.exec_module(collector)
_checkout_path_spec = importlib.util.spec_from_file_location(
    "edited_file_path_within_checkout_root_and_git_check_ignore_common",
    Path(__file__).resolve().with_name(
        "edited-file-path-within-checkout-root-and-git-check-ignore-common.py"))
checkout_path = importlib.util.module_from_spec(_checkout_path_spec)
_checkout_path_spec.loader.exec_module(checkout_path)

HOOK_NAME = "python-edit-changed-agent-facing-message-check-reminder"
PAGE_PATH = ("docs/nedschorus-wiki/"
             "nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md")
FAST_READ_COMMAND = "python3 nc-systems/cold-read/cold-read-fast-read.py --target {target}"
FAST_READ_TARGET_DIRECTORY_NAME = "agent-facing-message-fast-read-targets"
EDIT_TOOL_NAMES = ("Edit", "MultiEdit")
INSPECTED_TOOL_NAMES = (*EDIT_TOOL_NAMES, "Write")
LISTED_MESSAGE_LIMIT = 20
# Claude Code shows the agent only a 2,000-character preview of hook output
# longer than 10,000 characters.
REMINDER_CHARACTER_LIMIT = 9500
FIRST_LINE_CHARACTER_LIMIT = 100
REASON_CHARACTER_LIMIT = 300
GIT_TIMEOUT_SECONDS = 10

REMINDER_MESSAGE_TEMPLATE = (
    HOOK_NAME + ": your {tool} of {path} added or changed {count} agent-facing-message(s), "
    "text that a program hands an agent to act on:\n"
    "{listing}\n"
    "An agent that meets one of these messages has only the message to go on, so each "
    "message must follow " + PAGE_PATH + ".\n"
    "This hook changed nothing: your edit stands as you wrote it.\n"
    "Read that page now, unless you have already read the page in this agent-session, and "
    "check each message listed above against the page.\n"
    "If a message fails the page, rewrite that message in this turn, and update any test "
    "that asserts the message's text.\n"
    "{fast_read}\n"
    "If every listed message passes, carry on; nothing needs saying to the user.\n"
    "This hook finds only strings that are printed, written to sys.stdout or sys.stderr, "
    "raised, assigned to a name ending in {suffixes}, or given in a dict literal as {keys}.\n"
    "If your edit changed a message held in a local variable or built any other way, check "
    "that message against the page too.\n"
    "Before you write or change an agent-facing-message from now on, read the page first."
)
FAST_READ_MESSAGE_TEMPLATE = (
    "Give each listed message its cold-read-fast-read before you open the pull request, "
    "because a fresh reader shows whether an agent with only the message understands it. "
    "This hook wrote the text of each listed message to its own file; run each command "
    "below from your checkout once the message passes the page:\n"
    "{commands}\n"
    "Each command prints the path of its report; the report's directory under "
    "cold-read-records/ is that message's cold-read-record.\n"
    "If a report shows the message misread, rewrite the message and run the command from the "
    "reminder your rewrite brings; an earlier reminder's command reads the earlier text, or "
    "finds no file once the temporary directory has been cleaned.\n"
    "Name each message's cold-read-record in the pull request's description."
)
FAST_READ_FILES_NOT_WRITTEN_TEMPLATE = (
    "This hook could not write the listed messages to files for their cold-read-fast-read, "
    "because {reason}.\n"
    "Before you open the pull request, write each listed message's text to a file of its "
    "own and run " + FAST_READ_COMMAND.format(target="<that file>") + " from your checkout "
    "on each.\n"
    "Name each message's cold-read-record, the report's directory under cold-read-records/, "
    "in the pull request's description."
)
LISTING_LINE_TEMPLATE = "  {path}:{line}  {first_line}"
MORE_NOT_LISTED_LINE_TEMPLATE = (
    "  and {more} more in {path}, not listed here; check those against the page too.")
NOT_INSPECTED_MESSAGE_TEMPLATE = (
    HOOK_NAME + ": this hook could not inspect your {tool} of {path}, because {reason}. "
    "No agent-facing-message your edit added or changed has been listed for checking "
    "against " + PAGE_PATH + ".\n"
    "If your edit added or changed an agent-facing-message, such as the text of a refusal, "
    "a warning, a reminder or an error that a program hands an agent, check that message "
    "against the page yourself, and rewrite the message in this turn if the message fails "
    "the page."
)
FILE_DID_NOT_PARSE_MESSAGE_TEMPLATE = (
    HOOK_NAME + ": {path} does not parse as Python after your {tool} ({error}), so this "
    "hook could not find the agent-facing-messages your edit added or changed. A file "
    "often does not parse partway through an edit; the hook looks again after your next "
    "edit of {path}, but then lists only the messages that next edit writes.\n"
    "If this edit added or changed an agent-facing-message, check that message against "
    + PAGE_PATH + " yourself once the file parses, and rewrite the message in this turn "
    "if the message fails the page."
)


class HookCouldNotInspect(Exception):
    """The reason, worded to follow "because", that the edit was not inspected."""


def edit_written_lines_and_gaps(tool_response):
    """From an Edit's or MultiEdit's tool_response.structuredPatch, the 1-based
    numbers of the lines the edit added, and the 1-based numbers of the lines
    that follow a place where the edit deleted lines."""
    patch = tool_response.get("structuredPatch") if isinstance(tool_response, dict) else None
    if not isinstance(patch, list):
        raise HookCouldNotInspect("the payload carries no tool_response.structuredPatch list")
    added, gaps = set(), set()
    for hunk in patch:
        if not isinstance(hunk, dict) or not isinstance(hunk.get("newStart"), int):
            raise HookCouldNotInspect("a tool_response.structuredPatch hunk has no newStart")
        line_number = hunk["newStart"]
        for line in hunk.get("lines") or []:
            if not isinstance(line, str):
                raise HookCouldNotInspect("a tool_response.structuredPatch line is not text")
            if line.startswith("+"):
                added.add(line_number)
                line_number += 1
            elif line.startswith("-"):
                gaps.add(line_number)
            elif line.startswith(" "):
                line_number += 1
    return added, gaps


def entry_was_written(entry, added, gaps):
    return (any(entry["line"] <= line <= entry["end_line"] for line in added)
            or any(entry["line"] < line <= entry["end_line"] for line in gaps))


def run_git(arguments, directory: Path):
    try:
        completed = subprocess.run(["git", *arguments], cwd=str(directory), capture_output=True,
                                   text=True, encoding="utf-8", errors="replace",
                                   timeout=GIT_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.SubprocessError) as error:
        raise HookCouldNotInspect(f"git {arguments[0]} could not run: {error}") from error
    if completed.returncode != 0:
        detail = completed.stderr.strip().splitlines()
        raise HookCouldNotInspect(f"git {arguments[0]} exited {completed.returncode}"
                                  + (f": {detail[0]}" if detail else ""))
    return completed.stdout


def message_texts_at_head(file_path: Path):
    """The texts of the agent-facing-messages in the file at HEAD; none for a
    file HEAD does not hold."""
    directory = file_path.parent
    if not run_git(["ls-tree", "-z", "--name-only", "HEAD", "--", file_path.name], directory):
        return set()
    source = run_git(["show", f"HEAD:./{file_path.name}"], directory)
    return {entry["text"] for entry in collector.agent_facing_string_nodes_in_source(source)}


def first_line_of(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    first_line = lines[0] if lines else repr(text)
    if len(first_line) > FIRST_LINE_CHARACTER_LIMIT:
        first_line = first_line[:FIRST_LINE_CHARACTER_LIMIT] + "..."
    return first_line


def messages_not_at_head(entries, file_path: Path):
    """The entries whose text the file at HEAD holds in no message, each line
    and text once; an entry with no letter in its literal text, outside
    {...} placeholders, such as a separator like "-" * 20 or report.render() + "\n", is no
    message for a fast read."""
    texts_at_head = message_texts_at_head(file_path)
    changed, seen = [], set()
    for entry in entries:
        key = (entry["line"], entry["text"])
        if entry["text"] in texts_at_head or key in seen or not re.search(r"[A-Za-z]", entry["literal_text"]):
            continue
        seen.add(key)
        changed.append(entry)
    return changed


def fast_read_target_path(relative_path: str, text: str) -> Path:
    """The file for one message's text; its name becomes the cold-read-record's
    name. The text's digest keeps checkouts sharing the temporary directory, and
    source paths sharing a slug, from reading each other's texts."""
    slug = re.sub(r"[^A-Za-z0-9]+", "-", relative_path.removesuffix(".py")).strip("-")
    digest = hashlib.sha256(text.encode()).hexdigest()[:16]
    return (Path(tempfile.gettempdir()) / FAST_READ_TARGET_DIRECTORY_NAME
            / f"{slug}-{digest}-agent-facing-message.md")


def fast_read_command(target: Path) -> str:
    """The cold-read-fast-read command for a target file, with the path shell-quoted
    so a temporary directory with a space or a quote in its name still runs."""
    return FAST_READ_COMMAND.format(target=shlex.quote(str(target)))


def fast_read_target_written(relative_path: str, text: str) -> Path:
    """The text's target file, written if missing. It is written under a
    temporary name and renamed into place, so a concurrent hook run never reads
    or leaves a half-written file, and a failed write or rename removes the
    temporary file."""
    target = fast_read_target_path(relative_path, text)
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, partial = tempfile.mkstemp(dir=target.parent, prefix=".", suffix=".partial")
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(text.rstrip("\n") + "\n")
            os.replace(partial, target)
        except OSError:
            Path(partial).unlink(missing_ok=True)
            raise
    return target


def reminder_text(tool_name, relative_path, entries, targets, targets_error):
    """The reminder, listing as many entries as fit under REMINDER_CHARACTER_LIMIT."""
    for listed_count in range(min(len(entries), LISTED_MESSAGE_LIMIT), 0, -1):
        text = reminder_text_listing(tool_name, relative_path, entries, listed_count, targets,
                                     targets_error)
        if len(text) <= REMINDER_CHARACTER_LIMIT:
            break
    return text


def reminder_text_listing(tool_name, relative_path, entries, listed_count, targets, targets_error):
    listed = entries[:listed_count]
    listing = [LISTING_LINE_TEMPLATE.format(path=relative_path, line=entry["line"],
                                            first_line=first_line_of(entry["text"]))
               for entry in listed]
    if len(entries) > listed_count:
        listing.append(MORE_NOT_LISTED_LINE_TEMPLATE.format(
            more=len(entries) - listed_count, path=relative_path))
    if targets_error is None:
        fast_read = FAST_READ_MESSAGE_TEMPLATE.format(commands="\n".join(
            "  " + fast_read_command(targets[entry["text"]])
            for entry in listed))
    else:
        fast_read = FAST_READ_FILES_NOT_WRITTEN_TEMPLATE.format(reason=targets_error)
    return REMINDER_MESSAGE_TEMPLATE.format(
        tool=tool_name, path=relative_path, count=len(entries), listing="\n".join(listing),
        fast_read=fast_read,
        suffixes=words_joined_with_or(collector.AGENT_STRING_NAME_SUFFIXES),
        keys=words_joined_with_or(collector.AGENT_FACING_HOOK_OUTPUT_KEYS))


def words_joined_with_or(words):
    return ", ".join(words[:-1]) + " or " + words[-1]


def inspection_text(payload, relative_path: str):
    """The text to hand the agent, or None when the edit changed no message."""
    tool_name = payload["tool_name"]
    file_path = Path(payload["tool_input"]["file_path"])
    try:
        source = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise HookCouldNotInspect(f"the file could not be read: {error}") from error
    try:
        ast.parse(source)
    except (SyntaxError, ValueError) as error:
        return FILE_DID_NOT_PARSE_MESSAGE_TEMPLATE.format(path=relative_path, tool=tool_name, error=error)
    written = collector.agent_facing_string_nodes_in_source(source)
    if tool_name in EDIT_TOOL_NAMES:
        added, gaps = edit_written_lines_and_gaps(payload.get("tool_response"))
        written = [entry for entry in written if entry_was_written(entry, added, gaps)]
    if not written:
        return None
    listed = messages_not_at_head(written, file_path)
    if not listed:
        return None
    try:
        targets = {entry["text"]: fast_read_target_written(relative_path, entry["text"])
                   for entry in listed}
        targets_error = None
    except OSError as error:
        targets, targets_error = {}, f"{type(error).__name__}: {error}"[:REASON_CHARACTER_LIMIT]
    return reminder_text(tool_name, relative_path, listed, targets, targets_error)


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, ValueError, OSError):
        return 0
    if not isinstance(payload, dict) or payload.get("tool_name") not in INSPECTED_TOOL_NAMES:
        return 0
    tool_input = payload.get("tool_input")
    file_path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    working_directory = payload.get("cwd")
    if (not isinstance(file_path, str) or not file_path.endswith(".py")
            or not isinstance(working_directory, str)):
        return 0
    found = checkout_path.checkout_relative_path(file_path, Path(working_directory))
    if found is None or collector.path_is_test_file(found[1]):
        return 0
    relative_path = found[1]
    try:
        text = inspection_text(payload, relative_path)
    except Exception as error:
        reason = str(error) if isinstance(error, HookCouldNotInspect) else (
            f"the hook failed with {type(error).__name__}: {error}")
        text = NOT_INSPECTED_MESSAGE_TEMPLATE.format(
            tool=payload["tool_name"], path=relative_path, reason=reason[:REASON_CHARACTER_LIMIT])
    if text is not None:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                                 "additionalContext": text}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # A reminder must not turn a successful edit into an apparent tool failure.
        sys.exit(0)
