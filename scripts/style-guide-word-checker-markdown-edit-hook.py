#!/usr/bin/env python3
"""Tell the agent which words from the project's word list it just wrote into a
markdown file, with the names to choose from for each.

THE DESIGN is GHI [A project style guide: words to avoid, a mechanical
checker, and a check on unbacked promises](https://github.com/nedschorus/nedschorus/issues/14),
item 2, the first of the four places the checker runs: "a PostToolUse hook on
the Write and Edit tools checks the text just written and hands the agent each
hit's line and the names to choose from, while the file is open." The list and
the scanner live in scripts/style-guide-word-checker.py, loaded by path; this
file decides which files and which text are checked, and words the report.

Wired as a `PostToolUse` hook matching `Edit|Write`, beside
obsolete-file-edit-warning-hook.py and file-name-collision-warning-hook.py.
NotebookEdit is not matched, because a notebook is not a markdown file. The
Claude Code this was built against (2.1.287) offers no MultiEdit tool, and no
hook on main matches one.

THE CHANNEL. One JSON object on stdout carrying
`hookSpecificOutput.additionalContext`, which reaches the agent's context.
Plain stdout on a PostToolUse hook that exits 0 reaches only the debug log;
obsolete-file-edit-warning-hook.py's docstring gives the reference for that.
No `decision` field: a hit is a candidate for the writer to judge, never a
reason to block a write or cost the agent a turn.

ONLY THE TEXT JUST WRITTEN is reported, because a report on text the agent did
not write in this call would be noise the agent cannot act on:
  - Edit: the hits inside `new_string`, located in the file as it now stands
    (the hook runs after the edit). The whole file is read for its fences, so
    a `new_string` written inside a fenced code block is known to be code, and
    a hit is reported with its line in the file. The occurrences this call
    wrote are the ones that overlap a line the tool's own patch,
    `tool_response.structuredPatch`, marks as added: the text of `new_string`
    may already stand elsewhere in the file, and a `replace_all` adds
    occurrences beside any the file already held. Each hunk gives `newStart`
    and its `lines`, each line prefixed " " (unchanged), "-" (removed) or "+"
    (added). When the patch is missing or unreadable, the first occurrence is
    located, and every occurrence when `replace_all` is set. When `new_string`
    cannot be found in the file (another writer changed the file in between,
    say), nothing is reported.
  - Write: the hits on lines whose text is absent from `git show
    HEAD:<path>`, so rewriting a file whole reports only its new lines. A file
    `HEAD` does not hold is new in every line.

WHICH FILES. A markdown file (`.md` or `.markdown`) inside the checkout of the
session's own working directory, read from the payload's `cwd` and never from
$CLAUDE_PROJECT_DIR, which names the main checkout in a forked session. Within
the checkout: every file git tracks, and every new file git does not ignore.
`docs/walk/` is skipped by name as well as by being ignored: its
walk-documents quote the user, and the user's words are not the writer's to
change.

THE TEXT HANDED TO THE AGENT says what was flagged and why, then one line per
hit with the file, the line, the form and the names for its meanings. At most
HIT_LINES_LISTED_AT_MOST hits are listed: a long new document can hold dozens,
and a list the agent skims helps nobody. The text names none of the listed
words bare, so the report is not itself a hit. Each hit line is the entry's
own names_to_choose_from, so the list stays the one place a name is changed.

EVERY FAULT IS SILENCE: an unreadable payload, a missing git, a path outside
the checkout, a checker file that fails to load, any exception. A word report
is never worth a failed tool call.

SPEED. The hook runs after every Edit and Write an agent makes, so it spends as
little as it can; measured on the user's Mac, each git call costs 10 to 15 ms
and the interpreter's start about 45 ms. The checkout is found by walking up
from `cwd` to the directory holding `.git`, the way
.claude/hooks/instruction-file-guard.py finds it, with no git call. An Edit
then makes one git call, `git check-ignore`. A Write makes one, `git show`,
when the file is committed, since a committed file is tracked, and a second,
`git check-ignore`, only when the file is not committed. Each call has a
timeout. Only the lines just written are searched for words; the rest of the
file is read only for its fences.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

MARKDOWN_SUFFIXES = (".md", ".markdown")
SKIPPED_DIRECTORY_PREFIXES = ("docs/walk/",)
HIT_LINES_LISTED_AT_MOST = 20
GIT_TIMEOUT_SECONDS = 10

REPORT_OPENING_LINES = (
    "style-guide-word-checker: the text just written to {path} uses {count} word(s) "
    "from the project's list of words to avoid. Each listed word either carries more "
    "than one meaning in this project, so a reader cannot tell which meaning the writer "
    "intended, or is replaced in this project by another word.",
    "Judge each hit below in its sentence: only the writer knows which meaning was "
    "intended.",
    "Where the word carries one of the project meanings listed, replace the word with "
    "the name given for that meaning.",
    "Where the word has its ordinary English meaning, leave the word as written.",
)
HIT_LINE = '{path}:{line}: "{form}": {names}'
MORE_HITS_LINE = ("{count} more hit(s) in the same text are not listed: reread the rest "
                  "of the text just written for the same words.")


def _load_style_guide_word_checker():
    """scripts/style-guide-word-checker.py as a module, or None.

    Loaded by path because a hyphenated file name cannot be imported by name;
    the same way obsolete-file-edit-warning-hook.py loads
    checkout-freshness-catch-up.py.
    """
    try:
        specification = importlib.util.spec_from_file_location(
            "style_guide_word_checker",
            Path(__file__).resolve().with_name("style-guide-word-checker.py"))
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
        return module
    except Exception:
        return None


def run_git(arguments, working_directory: Path):
    return subprocess.run(["git", *arguments], cwd=str(working_directory),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=GIT_TIMEOUT_SECONDS, check=False)


def enclosing_checkout_root(directory: Path):
    """The nearest directory, `directory` or above, holding `.git` as git
    recognises it: a `.git` file, which marks a linked worktree, or a `.git`
    directory holding HEAD. None when there is none."""
    for candidate in (directory, *directory.parents):
        git_marker = candidate / ".git"
        try:
            if git_marker.is_file() or (git_marker / "HEAD").is_file():
                return candidate
        except OSError:
            continue
    return None


def checkout_relative_path(file_path: str, working_directory: Path):
    """(checkout root, the file's path as git names it), or None when the file
    is outside the session's checkout.

    Both sides are resolved: on macOS a payload path through /tmp and the same
    directory under /private/tmp must compare equal.
    """
    try:
        root = enclosing_checkout_root(working_directory.resolve())
        if root is None:
            return None
        return root, Path(file_path).resolve().relative_to(root).as_posix()
    except (ValueError, OSError, RuntimeError):
        return None


def git_would_track(root: Path, relative_path: str) -> bool:
    """Whether git tracks the file or would track the file if added.

    `git check-ignore -q` exits 0 for an ignored path, 1 for a path git would
    track, and 128 when it cannot answer, which is silence like the rest. A
    tracked file is never reported as ignored, whatever .gitignore says.
    """
    return run_git(["check-ignore", "-q", "--", relative_path], root).returncode == 1


def lines_added_by_structured_patch(tool_response):
    """The 1-based line numbers, in the file as it now stands, that the tool's
    patch marks as added, or None when the patch is missing or unreadable.

    A real Edit result carries hunks of this shape (Claude Code 2.1.287):
    {"oldStart": 49, "oldLines": 8, "newStart": 49, "newLines": 12,
     "lines": [" unchanged", "-removed", "+added", ...]}.
    """
    if not isinstance(tool_response, dict):
        return None
    hunks = tool_response.get("structuredPatch")
    if not isinstance(hunks, list) or not hunks:
        return None
    added = set()
    for hunk in hunks:
        if not isinstance(hunk, dict):
            return None
        new_line = hunk.get("newStart")
        hunk_lines = hunk.get("lines")
        if not isinstance(new_line, int) or not isinstance(hunk_lines, list):
            return None
        for hunk_line in hunk_lines:
            if not isinstance(hunk_line, str):
                return None
            if hunk_line.startswith("+"):
                added.add(new_line)
                new_line += 1
            elif not hunk_line.startswith("-"):
                new_line += 1
    return added


def hits_in_edit(checker, root: Path, relative_path: str, tool_input: dict,
                 tool_response=None):
    new_string = tool_input.get("new_string")
    if not isinstance(new_string, str) or not new_string.strip():
        return []
    if not git_would_track(root, relative_path):
        return []
    try:
        file_text = (root / relative_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    occurrences = []
    start = file_text.find(new_string)
    while start != -1:
        occurrences.append((start, start + len(new_string)))
        start = file_text.find(new_string, start + len(new_string))
    added_lines = lines_added_by_structured_patch(tool_response)
    if added_lines is not None:
        spans = [(span_start, span_end) for span_start, span_end in occurrences
                 if added_lines.intersection(range(
                     file_text.count("\n", 0, span_start) + 1,
                     file_text.count("\n", 0, max(span_start, span_end - 1)) + 2))]
    elif tool_input.get("replace_all") is True:
        spans = occurrences
    else:
        spans = occurrences[:1]
    if not spans:
        return []
    line_numbers = set()
    for span_start, span_end in spans:
        first_line = file_text.count("\n", 0, span_start) + 1
        line_numbers.update(range(first_line,
                                  first_line + file_text.count("\n", span_start, span_end) + 1))
    # The lines bound the search; the offsets then drop the older text that
    # shares a first or last line with new_string.
    return [hit for hit in checker.find_style_guide_word_hits_in_markdown(
                file_text, checker.APPLIES_TO_FILES, line_numbers)
            if any(span_start <= hit.offset < span_end for span_start, span_end in spans)]


def hits_in_write(checker, root: Path, relative_path: str, tool_input: dict):
    content = tool_input.get("content")
    if not isinstance(content, str) or not content.strip():
        return []
    committed = run_git(["show", "HEAD:" + relative_path], root)
    if committed.returncode == 0:
        committed_lines = set(line.rstrip() for line in committed.stdout.split("\n"))
    elif git_would_track(root, relative_path):
        committed_lines = set()
    else:
        return []
    new_line_numbers = set(
        index + 1 for index, line in enumerate(content.split("\n"))
        if line.rstrip() not in committed_lines)
    return checker.find_style_guide_word_hits_in_markdown(
        content, checker.APPLIES_TO_FILES, new_line_numbers)


def word_report(relative_path: str, hits) -> str:
    """The text handed to the agent: one hit per line and form, in file order."""
    seen = set()
    distinct_hits = []
    for hit in hits:
        key = (hit.line_number, hit.form)
        if key not in seen:
            seen.add(key)
            distinct_hits.append(hit)
    lines = [line.format(path=relative_path, count=len(distinct_hits))
             for line in REPORT_OPENING_LINES]
    for hit in distinct_hits[:HIT_LINES_LISTED_AT_MOST]:
        lines.append(HIT_LINE.format(path=relative_path, line=hit.line_number,
                                     form=hit.form, names=hit.entry.names_to_choose_from))
    if len(distinct_hits) > HIT_LINES_LISTED_AT_MOST:
        lines.append(MORE_HITS_LINE.format(
            count=len(distinct_hits) - HIT_LINES_LISTED_AT_MOST))
    return "\n".join(lines)


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, ValueError, OSError):
        return 0
    if not isinstance(payload, dict):
        return 0
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if tool_name not in ("Edit", "Write") or not isinstance(tool_input, dict):
        return 0
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path.lower().endswith(MARKDOWN_SUFFIXES):
        return 0
    working_directory = payload.get("cwd")
    if not isinstance(working_directory, str) or not Path(working_directory).is_dir():
        return 0

    located = checkout_relative_path(file_path, Path(working_directory))
    if located is None:
        return 0
    root, relative_path = located
    if relative_path.startswith(SKIPPED_DIRECTORY_PREFIXES):
        return 0

    checker = _load_style_guide_word_checker()
    if checker is None:
        return 0
    if tool_name == "Edit":
        hits = hits_in_edit(checker, root, relative_path, tool_input,
                            payload.get("tool_response"))
    else:
        hits = hits_in_write(checker, root, relative_path, tool_input)
    if not hits:
        return 0

    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": word_report(relative_path, hits),
    }}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # A word report is never worth a failed tool call, and a traceback on
        # stderr would read to the agent as a failed write.
        sys.exit(0)
