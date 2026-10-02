#!/usr/bin/env python3
"""Tell the agent which words from the project's word list it just wrote into a
markdown file, with the names to choose from for each.

THE DESIGN is GHI [A project style guide: words to avoid, a mechanical
checker, and a check on unbacked promises](https://github.com/nedschorus/nedschorus/issues/14),
item 2, the first of the four places the checker runs: "a PostToolUse hook on
the Write and Edit tools checks the text just written and hands the agent each
hit and the names to choose from, while the file is open." The list and
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
  - Edit: the hits inside `new_string` itself, scanned on its own and never
    located in the file. Each hit is reported with the words around it in
    `new_string`, not with a line number: the agent has just written that
    text and finds the words in it. Locating `new_string` in the file took
    three review rounds and still missed cases (the same text standing twice,
    a patch's no-newline-at-end-of-file marker), so it was removed. The
    accepted cost: fences are read from `new_string` alone, so text added
    inside a fenced code block that `new_string` does not open may be
    flagged; the writer judges each hit and leaves that one as written.
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
hit with the file, where the hit is (its line for a Write, the words around it
for an Edit), the form and the names for its meanings. At most
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
then makes one git call, `git check-ignore`, and reads no file. A Write makes
one, `git show`, when the file is committed, since a committed file is
tracked, and a second, `git check-ignore`, only when the file is not
committed. Each call has a timeout. Only the text just written is searched.
"""

import importlib.util
import json
import re
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
EDIT_HIT_LINE = '{path}, in "{context}": "{form}": {names}'
CONTEXT_WORDS_EACH_SIDE = 4
WORDS_BEFORE_PATTERN = re.compile(r"(?:\S+\s+){0,%d}\S*$" % CONTEXT_WORDS_EACH_SIDE)
WORDS_AFTER_PATTERN = re.compile(r"\S*(?:\s+\S+){0,%d}" % CONTEXT_WORDS_EACH_SIDE)
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


def hits_in_edit(checker, root: Path, relative_path: str, tool_input: dict):
    new_string = tool_input.get("new_string")
    if not isinstance(new_string, str) or not new_string.strip():
        return []
    if not git_would_track(root, relative_path):
        return []
    return checker.find_style_guide_word_hits_in_markdown(new_string, checker.APPLIES_TO_FILES)


def words_around(text: str, offset: int, form: str) -> str:
    """The form with up to CONTEXT_WORDS_EACH_SIDE words either side of it,
    from the text the Edit added, its whitespace collapsed to single spaces.
    A word joined to the form, as "(head" is, comes along with it."""
    before = WORDS_BEFORE_PATTERN.search(text[:offset]).group(0)
    after = WORDS_AFTER_PATTERN.match(text[offset + len(form):]).group(0)
    return " ".join((before + form + after).split())


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


def word_report(relative_path: str, hits, edit_text=None) -> str:
    """The text handed to the agent: one hit per line and form, in order.
    `edit_text` is the Edit's new_string, whose hits are shown with the words
    around them instead of a line number."""
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
        if edit_text is None:
            lines.append(HIT_LINE.format(path=relative_path, line=hit.line_number,
                                         form=hit.form, names=hit.entry.names_to_choose_from))
        else:
            lines.append(EDIT_HIT_LINE.format(
                path=relative_path, form=hit.form, names=hit.entry.names_to_choose_from,
                context=words_around(edit_text, hit.offset, hit.form)))
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
        hits = hits_in_edit(checker, root, relative_path, tool_input)
        edit_text = tool_input.get("new_string")
    else:
        hits = hits_in_write(checker, root, relative_path, tool_input)
        edit_text = None
    if not hits:
        return 0

    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": word_report(relative_path, hits, edit_text),
    }}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # A word report is never worth a failed tool call, and a traceback on
        # stderr would read to the agent as a failed write.
        sys.exit(0)
