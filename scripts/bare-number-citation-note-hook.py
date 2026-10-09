#!/usr/bin/env python3
"""Note each pull request, GitHub issue or task cited by a bare number, in
Markdown just written by Edit or Write, or in the agent's last message.

One program, two hook events, told apart by the payload's hook_event_name:

  PostToolUse on Edit and Write of a .md or .markdown file: scan the text just
      written, as style-guide-word-checker-markdown-edit-hook.py does. Edit
      scans new_string alone. Write scans only the lines HEAD does not already
      hold, so an edit to a file whose old bare numbers are kept on purpose
      (the agent-only files the glossary's bare-number-sweep entry names) is
      not reported for text it did not write. A file outside the session's
      checkout, or one git ignores, is not scanned.
  Stop: scan the agent's last message of the turn, read from transcript_path
      with read_turn() from absence-claim-locator-reminder-hook.py, so the
      two Stop hooks agree on what the last message is.

A BARE REFERENCE is an ID-type word followed by a number (PR, pull request,
issue, GHI or task, any case, optionally plural, optionally with `#`), or a
`#` followed by 2 to 5 digits that does not follow `&` or a word character,
which keeps an HTML entity and a URL's fragment out. A plain number never
matches. Not scanned: fenced code blocks, inline code spans, a whole Markdown
link `[text](target)` (its text included: a link is already a citation that
can be opened), a bare URL, and a line a program reads, which starts with
`supports-issues:` or `issue-marker:`.

OUTPUT is a note, never a refusal: hookSpecificOutput.additionalContext with
the hook's event name, listing up to HIT_LINES_LISTED_AT_MOST hits. A Stop
hook's additionalContext continues the conversation, so the Stop half stays
silent when stop_hook_active is set (the agent is already answering a Stop
hook, and a second note could loop) and in a headless `claude -p` child,
told apart as agent-seat-due-task-raise-hook.py does, whose last message its
caller reads as the answer. Nothing found, or any fault: nothing printed,
exit 0.
"""

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

MARKDOWN_SUFFIXES = (".md", ".markdown")
HIT_LINES_LISTED_AT_MOST = 10
GIT_TIMEOUT_SECONDS = 10
EXCERPT_CHARACTERS_EACH_SIDE = 40
REINCARNATION_OWNED_BY_CALLER_VARIABLE = "NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER"
SESSION_ATTENDED_VARIABLE = "CLAUDE_CODE_SESSION_ATTENDED"
SESSION_UNATTENDED_VALUE = "0"

ID_TYPE_WORD_FOLLOWED_BY_NUMBER = (
    r"\b(?:PRs?|pull\s+requests?|issues?|GHIs?|tasks?)(?:\s+#?|\s*#)\d+(?!\w)")
HASH_FOLLOWED_BY_TWO_TO_FIVE_DIGITS = r"(?<![&\w])#\d{2,5}(?![\w])"
# One alternation, so "PR #426" is one hit, not also a second hit for "#426".
BARE_REFERENCE_PATTERN = re.compile(
    ID_TYPE_WORD_FOLLOWED_BY_NUMBER + "|" + HASH_FOLLOWED_BY_TWO_TO_FIVE_DIGITS,
    re.IGNORECASE)
FENCE_PATTERN = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)?(`{3,}|~{3,})")
PROGRAM_READ_LINE_PATTERN = re.compile(r"^\s*(?:supports-issues|issue-marker):")
INLINE_CODE_PATTERN = re.compile(r"(`+)(?:(?!\1).)+?\1")
# Link text may hold one level of brackets, and a target one level of parentheses.
MARKDOWN_LINK_PATTERN = re.compile(
    r"!?\[(?:[^\[\]\n]|\[[^\[\]\n]*\])*\]\((?:[^()\s]|\([^()\s]*\))*(?:\s+\"[^\"\n]*\")?\)")
BARE_URL_PATTERN = re.compile(r"<?\b[a-z][a-z0-9+.-]*://[^\s>]+>?", re.IGNORECASE)

MARKDOWN_OPENING_LINES = (
    "bare-number-citation-note: the text just written to {path} cites {count} pull "
    "request(s), GitHub issue(s) or task(s) by a bare number. A number alone tells a "
    "reader almost nothing; a title and a link are what a reader can read and open.",
    "Cite each one by its ID-type and its name, as a clickable link where it can be "
    "opened: PR [title](url), not a bare number.",
    "Look a title and link up with: gh pr view <number> --json title,url, or "
    "gh issue view <number> --json title,url.",
    "Where the number quotes the wrong form on purpose, leave it as written.",
)
LAST_MESSAGE_OPENING_LINES = (
    "bare-number-citation-note: your last message cites {count} pull request(s), "
    "GitHub issue(s) or task(s) by a bare number. A number alone tells a reader "
    "almost nothing; a title and a link are what a reader can read and open.",
    "Your message has already been shown. Send a short follow-up that gives each one "
    "below by its ID-type and its name, as a clickable link where it can be opened: "
    "PR [title](url), not a bare number.",
    "Look a title and link up with: gh pr view <number> --json title,url, or "
    "gh issue view <number> --json title,url.",
    "Where the number quotes the wrong form on purpose, no follow-up is needed.",
)
WRITE_HIT_LINE = '{path}:{line}: "{reference}" in "{excerpt}"'
EXCERPT_HIT_LINE = '"{reference}" in "{excerpt}"'
MORE_HITS_LINE = ("{count} more not listed: reread the rest of the same text for "
                  "numbers cited the same way.")


class BareReference:
    def __init__(self, line_number, reference, excerpt):
        self.line_number = line_number
        self.reference = reference
        self.excerpt = excerpt


def _blank(match):
    return " " * len(match.group(0))


def scannable_lines(text: str):
    """Return the lines of text with every skipped part blanked to spaces, so
    line numbers and columns still point into the original text."""
    lines = []
    fence = None
    for line in text.split("\n"):
        fence_match = FENCE_PATTERN.match(line)
        if fence is not None:
            if (fence_match and fence_match.group(1)[0] == fence[0]
                    and len(fence_match.group(1)) >= len(fence)):
                fence = None
            lines.append("")
            continue
        if fence_match:
            fence = fence_match.group(1)
            lines.append("")
            continue
        if PROGRAM_READ_LINE_PATTERN.match(line):
            lines.append("")
            continue
        line = INLINE_CODE_PATTERN.sub(_blank, line)
        line = MARKDOWN_LINK_PATTERN.sub(_blank, line)
        line = BARE_URL_PATTERN.sub(_blank, line)
        lines.append(line)
    return lines


def excerpt_around(line: str, start: int, end: int) -> str:
    before = line[max(0, start - EXCERPT_CHARACTERS_EACH_SIDE):start]
    after = line[end:end + EXCERPT_CHARACTERS_EACH_SIDE]
    excerpt = " ".join((before + line[start:end] + after).split())
    if start > EXCERPT_CHARACTERS_EACH_SIDE:
        excerpt = "..." + excerpt
    if end + EXCERPT_CHARACTERS_EACH_SIDE < len(line):
        excerpt += "..."
    return excerpt


def bare_references_in(text: str, line_numbers_to_report=None):
    """Every bare reference in text, in reading order, numbering lines from 1.
    With line_numbers_to_report, only hits on those lines."""
    original_lines = text.split("\n")
    found = []
    for index, line in enumerate(scannable_lines(text)):
        line_number = index + 1
        if line_numbers_to_report is not None and line_number not in line_numbers_to_report:
            continue
        for match in BARE_REFERENCE_PATTERN.finditer(line):
            found.append(BareReference(
                line_number, match.group(0),
                excerpt_around(original_lines[index], match.start(), match.end())))
    return found


def note_text(opening_lines, references, path=None, with_line_numbers=False) -> str:
    lines = [line.format(path=path, count=len(references)) for line in opening_lines]
    for reference in references[:HIT_LINES_LISTED_AT_MOST]:
        if with_line_numbers:
            lines.append(WRITE_HIT_LINE.format(
                path=path, line=reference.line_number,
                reference=reference.reference, excerpt=reference.excerpt))
        else:
            lines.append(EXCERPT_HIT_LINE.format(
                reference=reference.reference, excerpt=reference.excerpt))
    if len(references) > HIT_LINES_LISTED_AT_MOST:
        lines.append(MORE_HITS_LINE.format(count=len(references) - HIT_LINES_LISTED_AT_MOST))
    return "\n".join(lines)


def hook_output(event_name: str, text: str) -> str:
    return json.dumps({"hookSpecificOutput": {
        "hookEventName": event_name, "additionalContext": text}}, ensure_ascii=False)


# --- PostToolUse: the Markdown file just written ---------------------------

def run_git(arguments, working_directory: Path):
    return subprocess.run(["git", *arguments], cwd=str(working_directory),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=GIT_TIMEOUT_SECONDS, check=False)


def enclosing_checkout_root(directory: Path):
    """Return the nearest checkout root at or above directory, or None."""
    for candidate in (directory, *directory.parents):
        git_marker = candidate / ".git"
        try:
            if git_marker.is_file() or (git_marker / "HEAD").is_file():
                return candidate
        except OSError:
            continue
    return None


def checkout_relative_path(file_path: str, working_directory: Path):
    """Return (checkout root, Git-relative path), or None outside the session checkout."""
    # Resolve both paths so macOS /tmp and /private/tmp compare equal.
    try:
        root = enclosing_checkout_root(working_directory.resolve())
        if root is None:
            return None
        return root, Path(file_path).resolve().relative_to(root).as_posix()
    except (ValueError, OSError, RuntimeError):
        return None


def git_would_track(root: Path, relative_path: str) -> bool:
    # check-ignore exits 0 for ignored, 1 for trackable, and 128 for failure; tracked files are never ignored.
    return run_git(["check-ignore", "-q", "--", relative_path], root).returncode == 1


def markdown_edit_note(payload: dict):
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if tool_name not in ("Edit", "Write") or not isinstance(tool_input, dict):
        return None
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path.lower().endswith(MARKDOWN_SUFFIXES):
        return None
    working_directory = payload.get("cwd")
    if not isinstance(working_directory, str) or not Path(working_directory).is_dir():
        return None
    located = checkout_relative_path(file_path, Path(working_directory))
    if located is None:
        return None
    root, relative_path = located

    if tool_name == "Edit":
        new_string = tool_input.get("new_string")
        if not isinstance(new_string, str) or not new_string.strip():
            return None
        if not git_would_track(root, relative_path):
            return None
        references = bare_references_in(new_string)
        with_line_numbers = False
    else:
        content = tool_input.get("content")
        if not isinstance(content, str) or not content.strip():
            return None
        committed = run_git(["show", "HEAD:" + relative_path], root)
        if committed.returncode == 0:
            committed_lines = set(line.rstrip() for line in committed.stdout.split("\n"))
        elif git_would_track(root, relative_path):
            committed_lines = set()
        else:
            return None
        new_line_numbers = set(
            index + 1 for index, line in enumerate(content.split("\n"))
            if line.rstrip() not in committed_lines)
        references = bare_references_in(content, new_line_numbers)
        with_line_numbers = True
    if not references:
        return None
    return hook_output("PostToolUse", note_text(
        MARKDOWN_OPENING_LINES, references, relative_path, with_line_numbers))


# --- Stop: the agent's last message -----------------------------------------

def _load_absence_claim_hook():
    specification = importlib.util.spec_from_file_location(
        "absence_claim_locator_reminder_hook",
        Path(__file__).resolve().with_name("absence-claim-locator-reminder-hook.py"))
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def last_message_note(payload: dict, environment):
    if payload.get("stop_hook_active"):
        return None
    if (environment.get(REINCARNATION_OWNED_BY_CALLER_VARIABLE)
            or environment.get(SESSION_ATTENDED_VARIABLE) == SESSION_UNATTENDED_VALUE):
        return None
    transcript_path = payload.get("transcript_path")
    if not isinstance(transcript_path, str) or not transcript_path:
        return None
    reply, _ = _load_absence_claim_hook().read_turn(Path(transcript_path).expanduser())
    if not isinstance(reply, str) or not reply.strip():
        return None
    references = bare_references_in(reply)
    if not references:
        return None
    return hook_output("Stop", note_text(LAST_MESSAGE_OPENING_LINES, references))


def run(stdin_text: str, environment):
    """Return the text to print, or None."""
    payload = json.loads(stdin_text or "{}")
    if not isinstance(payload, dict):
        return None
    event_name = payload.get("hook_event_name")
    if event_name == "PostToolUse":
        return markdown_edit_note(payload)
    if event_name == "Stop":
        return last_message_note(payload, environment)
    return None


def main() -> int:
    try:
        output = run(sys.stdin.read(), os.environ)
        if output is not None:
            print(output)
    except Exception:
        # A note must not turn a successful write, or a turn's end, into a failure.
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
