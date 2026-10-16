#!/usr/bin/env python3
"""On ned-box, note each path under /home/nedlern/ that the agent's previous
reply gave the user in a form the user cannot open on the Mac, with the
file:///Volumes/nedhome/ link to write instead.

The user reads replies on the Mac, which mounts ned-box's /home/nedlern/ at
/Volumes/nedhome/, so file:///Volumes/nedhome/<rest> opens the file
/home/nedlern/<rest> and a /home/nedlern/ path or file:///home/nedlern/ link
opens nothing there.

A UserPromptSubmit hook, a sibling of
bare-number-citation-in-markdown-and-agent-reply-warning-hook.py, whose
functions it loads by path and uses for everything but the scan itself:
reading the previous reply from transcript_path (a turn starts where
is_human_or_parent_message() from absence-claim-locator-reminder-hook.py
says), masking fenced code, code spans, links and bare URLs, the record of
the last reply noted, the hook output, and the test for a headless
`claude -p` child, where the hook stays silent. It stays silent on every
machine but ned-box, as this_machine_is_ned_box() from
nc-systems/handoff/daily-memory-review-mark.py decides: a session on the Mac
names its own files by their Mac paths.

NOTED, outside fenced code blocks:
  - a link or an image whose target is /home/nedlern/...,
    file:///home/nedlern/... or file://localhost/home/nedlern/...; the link
    text is kept, so a log-store citation's scp-form text stays as CLAUDE.md
    prescribes;
  - a bare file:///home/nedlern/... URL, which ends where a bare path does, so
    emphasis or a bracket around it is not taken into the suggested link;
  - a bare /home/nedlern/... path in the text, outside any link, unless the
    scp form's host prefix, such as nedlern@ned-box:, stands right before it;
    underscore emphasis around the path is not taken into it;
  - a code span whose whole content is one such path or file URL, with or
    without angle brackets: the span cites the path, as a reader would click it.
NOT NOTED: a code span holding more than one word, which is a command, such
as one the user runs on ned-box; a fenced code block, which holds commands
or output, including any code span on its lines; a link whose target is
already file:///Volumes/nedhome/..., whatever its text holds; the scp form
written as plain text.

The suggested link keeps the link text a flagged link had. For a bare path in
the log-store, its text is the scp citation nedlern@ned-box:/home/nedlern/...;
for any other bare path, the path as written. A path is listed once however
often the reply repeats it, up to HIT_LINES_LISTED_AT_MOST lines.

ONE NOTE PER REPLY, keyed by the reply's message id in a record per
agent-session under the temporary directory, as the sibling hook keeps it: a
task notification submits a prompt with no reply in between. A record that
cannot be read or written leaves the note as it is and adds a line saying so.
Nothing found: nothing printed, exit 0. A fault: FAULT_LINES on stderr, naming
it and saying the reply went unchecked, nothing on stdout, exit 1, which Claude
Code records as a non-blocking error.
"""

import functools
import importlib.util
import json
import os
import re
import sys
import tempfile
from pathlib import Path

PROGRAM = "ned-box-path-in-agent-reply-unclickable-on-mac-warning-hook"
FAULT_LINES = (
    PROGRAM + ": your previous reply was not checked for /home/nedlern/ paths the user cannot "
    "open on the Mac, because the check failed: {reason}",
    "When you give the user a ned-box file to open, link the file as "
    "file:///Volumes/nedhome/<the path after /home/nedlern/>.",
    "If this failure is reported again on later prompts, tell the user, quoting the first line.",
)


def _load_module_by_path(module_name, path):
    specification = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def fault_exit(error):
    reason = f"{type(error).__name__}: {error}"
    print("\n".join(FAULT_LINES).format(reason=reason), file=sys.stderr)
    return 1


# The patterns below are built from these paths, so a load that fails ends the
# hook here, reported the way main() reports any other fault.
try:
    ned_box_home_path_constants = _load_module_by_path(
        "ned_box_home_directory_and_its_mac_mount_point_path_constants_common",
        Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
        / "ned-box-home-directory-and-its-mac-mount-point-path-constants-common.py")
except Exception as error:
    sys.exit(fault_exit(error))

HIT_LINES_LISTED_AT_MOST = 10
NOTE_RECORD_DIRECTORY_NAME = "ned-box-path-in-agent-reply-unclickable-on-mac-warning-hook-state"
NED_BOX_HOME = ned_box_home_path_constants.NED_BOX_HOME + "/"
MAC_MOUNT_OF_NED_BOX_HOME = ned_box_home_path_constants.MAC_MOUNT_OF_NED_BOX_HOME + "/"
LOG_STORE_DIRECTORY_UNDER_NED_BOX_HOME = "nedschorus-logs/"
SCP_CITATION_HOST_PREFIX = "nedlern@ned-box:"

# Characters that end a path in prose: whitespace, quotes, brackets, Markdown
# emphasis and table bars, and the barrier the sibling hook's masking writes.
# An underscore is allowed in a path, so underscore emphasis is matched by
# its opening run and the same run is cut from the path's end.
PATH_REST = r"[^\s`'\"<>()\[\]{}|*\x00]*"
PATH_REST_PATTERN = re.compile(PATH_REST)
BARE_PATH_PATTERN = re.compile(r"(?<![\w/.~-])(?P<emphasis>_*)(?P<path>" + re.escape(NED_BOX_HOME) + PATH_REST + ")")
SCP_HOST_PREFIX_BEFORE_PATH_PATTERN = re.compile(r"(?:[\w.-]+@)?ned-box:$")
UNOPENABLE_TARGET_PATTERN = re.compile(
    r"^<?(?:file://(?:localhost)?)?" + re.escape(NED_BOX_HOME) + r"(?P<rest>[^<>\s]*?)>?$", re.IGNORECASE)
UNOPENABLE_FILE_URL_PATTERN = re.compile(
    r"^<?file://(?:localhost)?" + re.escape(NED_BOX_HOME) + r"(?P<rest>[^<>\s]*?)>?$", re.IGNORECASE)
TRAILING_SENTENCE_PUNCTUATION = ".,;:!?"

PREVIOUS_REPLY_OPENING_LINES = (
    PROGRAM + ": your previous reply to the user showed {count} path(s) under /home/nedlern/ "
    "that the user cannot open from the reply. The user reads replies on the Mac, which mounts "
    "ned-box's /home/nedlern/ at /Volumes/nedhome/, so only a file:///Volumes/nedhome/ link opens "
    "a ned-box file there.",
    "When you give the user a ned-box file to open, link the file as "
    "file:///Volumes/nedhome/<the path after /home/nedlern/>. Each line below shows the link to "
    "write in place of what your reply wrote.",
    "In your next reply, write in that form each file listed below that you mention again.",
    "For a log-store file, keep the scp citation nedlern@ned-box:/home/nedlern/nedschorus-logs/<path> "
    "as the link text, as the lines below do; only the link target takes the /Volumes/nedhome form.",
    "A path inside a shell command, written in a code span or a fenced code block, is not listed "
    "and needs no change: the command runs on ned-box, where the path is right.",
)
HIT_LINE = '"{written}" in "{excerpt}": write {replacement}'
MORE_HITS_LINE = ("{count} more not listed: reread the rest of the same reply for paths under "
                  "/home/nedlern/ given the same way.")
SUGGESTED_LINK_TEMPLATE = "[{text}](file://" + MAC_MOUNT_OF_NED_BOX_HOME + "{rest})"
NOTE_RECORD_FAILED_LINE = (
    PROGRAM + ": its record of the replies it has noted, {record}, could not be {action} "
    "({reason}), so this note may be sent again for the same reply. Nothing needs doing about "
    "the record.")


@functools.lru_cache(maxsize=None)
def bare_number_hook():
    return _load_module_by_path(
        "bare_number_citation_in_markdown_and_agent_reply_warning_hook",
        Path(__file__).resolve().with_name(
            "bare-number-citation-in-markdown-and-agent-reply-warning-hook.py"))


@functools.lru_cache(maxsize=None)
def daily_memory_review_mark():
    return _load_module_by_path(
        "daily_memory_review_mark",
        Path(__file__).resolve().parents[1] / "nc-systems" / "handoff" / "daily-memory-review-mark.py")


class UnopenablePath:
    def __init__(self, written, excerpt, replacement):
        self.written = written
        self.excerpt = excerpt
        self.replacement = replacement


def suggested_link(rest, link_text=None):
    """The file:///Volumes/nedhome/ link for /home/nedlern/<rest>, under
    link_text, or, for a bare path, under the citation a reader expects."""
    if link_text is None:
        link_text = (SCP_CITATION_HOST_PREFIX if rest.startswith(LOG_STORE_DIRECTORY_UNDER_NED_BOX_HOME)
                     else "") + NED_BOX_HOME + rest
    return SUGGESTED_LINK_TEMPLATE.format(text=link_text, rest=rest)


def without_trailing_punctuation(path):
    return path.rstrip(TRAILING_SENTENCE_PUNCTUATION)


def path_rest_as_in_prose(rest):
    """rest cut where a bare path in prose would end, without the
    sentence's punctuation."""
    return without_trailing_punctuation(PATH_REST_PATTERN.match(rest).group(0))


def spans_of(pattern, line):
    return [match.span() for match in pattern.finditer(line)]


def inside_any(start, end, spans):
    return any(span_start <= start and end <= span_end for span_start, span_end in spans)


def unopenable_paths_in(text):
    """Every path under /home/nedlern/ in text the Mac cannot open, in
    reading order, one per distinct replacement."""
    hook = bare_number_hook()
    original_lines = text.split("\n")
    # Fenced code, code spans, links and bare URLs blanked: what is left is prose.
    prose_lines = hook.scannable_lines(text)
    # Fenced code and code spans blanked, links and bare URLs kept.
    linked_lines = hook.scannable_lines(text, keep_links=True)
    found = []
    for original, prose, linked in zip(original_lines, prose_lines, linked_lines):
        if original and not prose:
            # A line of a fenced code block, or a line a program reads.
            continue
        hits = []
        link_spans = spans_of(hook.MARKDOWN_LINK_PATTERN, linked)
        for start, end in link_spans:
            image_marker = "!" if linked[start] == "!" else ""
            # Matched on linked, where a code span in the link text is blanked
            # and cannot end the text early; columns are the same as original's.
            parts = hook.LINK_TEXT_AND_TARGET_PATTERN.match(linked, start + len(image_marker))
            target = UNOPENABLE_TARGET_PATTERN.match(parts.group("target"))
            if target:
                text = original[parts.start("text"):parts.end("text")]
                hits.append((start, original[start:end],
                             image_marker + suggested_link(target.group("rest"), text)))
        links_blanked = hook.MARKDOWN_LINK_PATTERN.sub(hook._blank, linked)
        for match in hook.BARE_URL_PATTERN.finditer(links_blanked):
            file_url = UNOPENABLE_FILE_URL_PATTERN.match(match.group(0))
            if file_url:
                rest = path_rest_as_in_prose(file_url.group("rest"))
                url_start = 1 if match.group(0).startswith("<") else 0
                written = match.group(0)[url_start:file_url.start("rest") + len(rest)]
                hits.append((match.start() + url_start, written, suggested_link(rest)))
        for match in hook.INLINE_CODE_PATTERN.finditer(original):
            if inside_any(match.start(), match.end(), link_spans):
                continue
            content = match.group(0).strip("`").strip()
            path = UNOPENABLE_TARGET_PATTERN.match(without_trailing_punctuation(content))
            if path:
                hits.append((match.start(), match.group(0), suggested_link(path.group("rest"))))
        for match in BARE_PATH_PATTERN.finditer(prose):
            if SCP_HOST_PREFIX_BEFORE_PATH_PATTERN.search(prose, 0, match.start()):
                continue
            path = without_trailing_punctuation(match.group("path"))
            emphasis = match.group("emphasis")
            if emphasis and path.endswith(emphasis):
                path = without_trailing_punctuation(path[:-len(emphasis)])
            hits.append((match.start("path"), path, suggested_link(path[len(NED_BOX_HOME):])))
        for start, written, replacement in sorted(hits, key=lambda hit: hit[0]):
            if any(earlier.replacement == replacement for earlier in found):
                continue
            found.append(UnopenablePath(
                written, hook.excerpt_around(original, start, start + len(written)), replacement))
    return found


def note_text(paths):
    lines = [line.format(count=len(paths)) for line in PREVIOUS_REPLY_OPENING_LINES]
    for path in paths[:HIT_LINES_LISTED_AT_MOST]:
        lines.append(HIT_LINE.format(written=path.written, excerpt=path.excerpt,
                                     replacement=path.replacement))
    if len(paths) > HIT_LINES_LISTED_AT_MOST:
        lines.append(MORE_HITS_LINE.format(count=len(paths) - HIT_LINES_LISTED_AT_MOST))
    return "\n".join(lines)


def note_record_path_for(session_id):
    """The agent-session's record of the reply last noted, or None when the
    payload names no session this hook can use as a file name."""
    if not isinstance(session_id, str) or not bare_number_hook().SESSION_ID_SAFE_PATTERN.match(session_id):
        return None
    return Path(tempfile.gettempdir()) / NOTE_RECORD_DIRECTORY_NAME / f"{session_id}.json"


def previous_reply_note(payload, environment):
    hook = bare_number_hook()
    if (environment.get(hook.REINCARNATION_OWNED_BY_CALLER_VARIABLE)
            or environment.get(hook.SESSION_ATTENDED_VARIABLE) == hook.SESSION_UNATTENDED_VALUE):
        return None
    transcript_path = payload.get("transcript_path")
    if not isinstance(transcript_path, str) or not transcript_path:
        return None
    transcript_file = Path(transcript_path).expanduser()
    if not transcript_file.exists():
        return None
    records = hook.transcript_records(transcript_file)
    reply, message_id = hook.previous_reply(
        records, hook._load_absence_claim_hook().is_human_or_parent_message)
    if not reply.strip():
        return None
    record_path = note_record_path_for(payload.get("session_id"))
    record, read_failure = hook.note_record_read(record_path) if record_path else ({}, None)
    if message_id is not None and record.get("noted_message_id") == message_id:
        return None
    paths = unopenable_paths_in(reply)
    if not paths:
        return None
    failures = []
    if record_path is not None:
        record["noted_message_id"] = message_id
        if read_failure is not None:
            failures.append(NOTE_RECORD_FAILED_LINE.format(record=record_path, action="read",
                                                           reason=read_failure))
        write_failure = hook.note_record_write(record_path, record)
        if write_failure is not None:
            failures.append(NOTE_RECORD_FAILED_LINE.format(record=record_path, action="written",
                                                           reason=write_failure))
    return hook.hook_output("UserPromptSubmit", "\n".join([note_text(paths)] + failures))


def run(stdin_text, environment, on_ned_box):
    """Return the text to print, or None."""
    payload = json.loads(stdin_text or "{}")
    if not isinstance(payload, dict) or payload.get("hook_event_name") != "UserPromptSubmit":
        return None
    if not on_ned_box:
        return None
    return previous_reply_note(payload, environment)


def main():
    try:
        output = run(sys.stdin.read(), os.environ, daily_memory_review_mark().this_machine_is_ned_box())
        if output is not None:
            print(output)
    except Exception as error:
        return fault_exit(error)
    return 0


if __name__ == "__main__":
    sys.exit(main())
