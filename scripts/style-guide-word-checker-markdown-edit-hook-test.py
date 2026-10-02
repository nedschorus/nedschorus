#!/usr/bin/env python3
"""Tests for style-guide-word-checker-markdown-edit-hook.py and the word list
and scanner in style-guide-word-checker.py.

Run: python3 scripts/style-guide-word-checker-markdown-edit-hook-test.py
Prints one line per case and exits non-zero if any case fails.

The scanner's cases call the checker directly. The hook's cases run the hook
as Claude Code does, as a subprocess reading a PostToolUse payload on stdin,
against a throwaway repository under a temporary directory: a committed file,
a .gitignore that ignores one directory, and new files written by each case.
That repository's .gitignore deliberately does NOT ignore docs/walk/, so the
docs/walk/ case proves the hook's own skip rather than git's.

Every git call, the hook's included, runs with the variables that redirect
git (GIT_DIR and its kin) removed, and the scratch repository is checked to be
a repository at its own path before any case writes to it, so a GIT_DIR
inherited from the caller cannot point these writes at another repository.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK_PATH = Path(__file__).with_name("style-guide-word-checker-markdown-edit-hook.py")
CHECKER_PATH = Path(__file__).with_name("style-guide-word-checker.py")

GIT_REDIRECTING_VARIABLES = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
                             "GIT_OBJECT_DIRECTORY", "GIT_COMMON_DIR",
                             "GIT_ALTERNATE_OBJECT_DIRECTORIES")
CLEAN_ENVIRONMENT = {name: value for name, value in os.environ.items()
                     if name not in GIT_REDIRECTING_VARIABLES}

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


checker = load_module("style_guide_word_checker", CHECKER_PATH)
hook = load_module("style_guide_word_checker_markdown_edit_hook", HOOK_PATH)


def file_hit_forms(text):
    return [hit.form for hit in
            checker.find_style_guide_word_hits_in_markdown(text, checker.APPLIES_TO_FILES)]


# ---------------------------------------------------------------------------
# The scanner, called directly.
# ---------------------------------------------------------------------------

for word in ("land", "home", "draft", "walk", "seat", "head", "drain"):
    forms = file_hit_forms(f"The {word} is ready.\n")
    check(f'plain prose: "{word}" is flagged', forms == [word], forms)

for form in ("lands", "landed", "landing", "homes", "drafts", "walks", "walked", "walking",
             "seats", "seated", "heads", "drains", "drained", "draining"):
    forms = file_hit_forms(f"Then {form} again.\n")
    check(f'inflection: "{form}" is flagged', forms == [form], forms)

forms = file_hit_forms("Seat assignments changed.\n")
check("a form at the start of a sentence, capitalised, is flagged", forms == ["Seat"], forms)

hits = checker.find_style_guide_word_hits_in_markdown("# Title\n\nThe walk ended.\n",
                                                     checker.APPLIES_TO_FILES)
check("a hit carries its 1-based line and its offset in the text",
      [(hit.line_number, hit.offset, hit.entry.word) for hit in hits] == [(3, 13, "walk")],
      hits)

EXEMPT_TEXT_CASES = (
    ("an inline code span", "Run `the seat command` and `walk --all` now.\n"),
    ("a fenced code block, backticks", "```\nthe seat\n```\n"),
    ("a fenced code block, tildes", "~~~\nthe walk\n~~~\n"),
    ("a fenced code block indented in a list item", "- step\n  ```\n  the seat\n  ```\n"),
    ("a blockquote line", "> the seat said so\n"),
    ("a link target", "See [the page](head) and [another](#walk).\n"),
    ("a path in a URL query", "Search https://github.com/x/y/issues?q=queue+drain today.\n"),
    ("text in straight double quotes", 'The user said "the seat is home" and left.\n'),
    ("text in curly double quotes", "The user said \u201cthe seat is home\u201d and left.\n"),
    ("a file name with an extension", "Open seat.md first.\n"),
    ("a placeholder in angle brackets", "Replace <seat> with the name.\n"),
)
for case_name, text in EXEMPT_TEXT_CASES:
    forms = file_hit_forms(text)
    check(f"exempt: {case_name} is not flagged", forms == [], forms)

forms = file_hit_forms("```\ncode\n```\nThe seat after the fence.\n")
check("a fence closes: prose after the closing fence is flagged", forms == ["seat"], forms)

NAMED_COMPOUNDS = ("agent-seat", "seat-branch", "seat-brief", "reincarnate-seat", "retire-seat",
                   "agent-home", "queue-drain", "frozen-head", "approval-walk",
                   "approved-by-walk", "walk-document", "walk-minutes", "/walk-me-through",
                   "the -draft suffix")
for compound in NAMED_COMPOUNDS:
    forms = file_hit_forms(f"Read about the {compound} today.\n")
    check(f'exempt: the named compound "{compound}" is not flagged', forms == [], forms)

for phrase in ("head commit", "Head commit"):
    forms = file_hit_forms(f"{phrase} first, then the rest.\n")
    check(f'exempt: the two-word name "{phrase}" is not flagged', forms == [], forms)

forms = file_hit_forms("Check out HEAD before you start.\n")
check("exempt: `HEAD` in capitals is not flagged", forms == [], forms)

for path in ("/home/nedlern/x", "docs/drafts/", "docs/walk/"):
    forms = file_hit_forms(f"Look under {path} for the file.\n")
    check(f'exempt: the path "{path}" is not flagged', forms == [], forms)

for compound in ("seat-specific", "pre-walk"):
    forms = file_hit_forms(f"A {compound} rule.\n")
    check(f'exempt: an unlisted hyphenated compound "{compound}" is not flagged',
          forms == [], forms)

forms = file_hit_forms("The heading reads ahead, overhead, landscape, homepage, seating.\n")
check("words that only contain a form are not flagged", forms == [], forms)

forms = file_hit_forms("It is what this is, and they said that its parts work.\n")
check("a pronoun is not flagged by the file entries", forms == [], forms)

message_forms = [hit.form for hit in checker.find_style_guide_word_hits_in_markdown(
    "It is what this is.\n", checker.APPLIES_TO_AGENT_MESSAGES)]
check("the pronoun entries apply to agent messages", message_forms == ["It", "this"],
      message_forms)

entries_by_word = {entry.word: entry for entry in checker.STYLE_GUIDE_WORD_LIST}
schema_problems = []
for entry in checker.STYLE_GUIDE_WORD_LIST:
    if entry.word not in entry.inflected_forms:
        schema_problems.append(f"{entry.word}: the word is not among its forms")
    if not entry.names_to_choose_from.strip():
        schema_problems.append(f"{entry.word}: no names to choose from")
    if not entry.applies_to or not set(entry.applies_to) <= set(checker.APPLIES_TO_VALUES):
        schema_problems.append(f"{entry.word}: applies_to {entry.applies_to!r}")
for word in ("land", "home", "draft", "walk", "seat", "head", "drain"):
    if checker.APPLIES_TO_FILES not in entries_by_word.get(word, checker.StyleGuideWordListEntry(
            word, (), (), "", ())).applies_to:
        schema_problems.append(f"{word}: missing, or not applying to files")
for word in ("it", "its", "they", "this", "that"):
    applies_to = set(entries_by_word[word].applies_to) if word in entries_by_word else set()
    if applies_to != {checker.APPLIES_TO_AGENT_MESSAGES, checker.APPLIES_TO_USER_MESSAGES}:
        schema_problems.append(f"{word}: applies_to {sorted(applies_to)}")
check("every entry carries its forms, names and where it applies", not schema_problems,
      schema_problems)

NAMES_EACH_ENTRY_GIVES = {
    "home": ("agent-home", "canonical location"),
    "draft": ("-draft", "pending approval", "the `draft` label", "`docs/drafts/`"),
    "walk": ("approval-walk", "walk-document", "approved-by-walk",
             "put to the user in an approval-walk"),
    "seat": ("agent-seat", "agent-session", "the agent-seat's name", "working directory",
             "cold-read-cell"),
    "head": ("head commit", "frozen-head", "`HEAD`"),
    "drain": ("queue-drain", "is promoted to"),
    "land": ('"merge"', '"merged"'),
}
missing_names = [(word, name) for word, names in NAMES_EACH_ENTRY_GIVES.items()
                 for name in names
                 if name not in entries_by_word[word].names_to_choose_from]
check("each entry hands the writer the names the design gives", not missing_names,
      missing_names)

report_text = "\n".join(hook.REPORT_OPENING_LINES) + "\n" + hook.MORE_HITS_LINE
forms = file_hit_forms(report_text)
check("the report's own wording uses no listed word", forms == [], forms)


# ---------------------------------------------------------------------------
# The hook, run as a subprocess against a scratch repository.
# ---------------------------------------------------------------------------

def git(arguments, cwd):
    return subprocess.run(["git", *arguments], cwd=str(cwd), capture_output=True,
                          text=True, check=False, env=CLEAN_ENVIRONMENT)


def run_hook(payload, hook_path=HOOK_PATH):
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run([sys.executable, str(hook_path)], input=text,
                          capture_output=True, text=True, check=False, env=CLEAN_ENVIRONMENT)


# The payloads below have the keys of real PostToolUse payloads, captured from
# Claude Code 2.1.287 on the user's Mac by a headless run, `claude -p` with
# `--settings` naming a PostToolUse hook on Edit|Write whose command was
# `cat >> captured-post-tool-use-payloads.jsonl`, asked to Write a file, Edit
# the file once, and Edit the file again with replace_all. What the capture
# showed, and the hook relies on: `cwd` and `tool_input.file_path` are
# absolute; a Write's `tool_input` holds `file_path` and `content`; an Edit's
# holds `file_path`, `old_string`, `new_string` and `replace_all`, a boolean
# present whether true or false. The hook reads nothing else, so the
# tool_response values here are placeholders under the captured keys.
def payload_common_keys(cwd, tool_name):
    return {"session_id": "style-guide-word-checker-test-session",
            "transcript_path": "/dev/null", "cwd": str(cwd),
            "permission_mode": "acceptEdits", "prompt_id": "style-guide-word-checker-test-prompt",
            "hook_event_name": "PostToolUse", "tool_name": tool_name,
            "tool_use_id": "style-guide-word-checker-test-tool-use", "duration_ms": 1}


def edit_payload(cwd, file_path, old_string, new_string, replace_all=False):
    payload = payload_common_keys(cwd, "Edit")
    payload["tool_input"] = {"file_path": str(file_path), "old_string": old_string,
                             "new_string": new_string, "replace_all": replace_all}
    payload["tool_response"] = {"filePath": str(file_path), "oldString": old_string,
                                "newString": new_string, "originalFile": "",
                                "replaceAll": replace_all, "structuredPatch": [],
                                "userModified": False}
    return payload


def write_payload(cwd, file_path, content):
    payload = payload_common_keys(cwd, "Write")
    payload["tool_input"] = {"file_path": str(file_path), "content": content}
    payload["tool_response"] = {"type": "create", "filePath": str(file_path),
                                "content": content, "originalFile": None,
                                "structuredPatch": [], "userModified": False}
    return payload


def write_then_run(cwd, file_path, content):
    """What the Write tool leaves behind, then the hook that follows it."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    return run_hook(write_payload(cwd, file_path, content))


def silent(result):
    return result.returncode == 0 and result.stdout.strip() == "" and result.stderr.strip() == ""


def agent_text(result):
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        return ""
    if not isinstance(parsed, dict):
        return ""
    return parsed.get("hookSpecificOutput", {}).get("additionalContext", "")


def hit_lines(result, relative_path):
    """(line number, form) for every hit line the agent was handed."""
    found = []
    for line in agent_text(result).split("\n"):
        if line.startswith(relative_path + ":"):
            line_number, _, rest = line[len(relative_path) + 1:].partition(": ")
            found.append((int(line_number), rest.split('"')[1]))
    return found


COMMITTED_TEXT = ("# Notes\n"
                  "\n"
                  "The seat was here before.\n"
                  "\n"
                  "```\n"
                  "code block\n"
                  "```\n")

with tempfile.TemporaryDirectory() as temporary_directory:
    tmp = Path(temporary_directory)
    checkout = tmp / "checkout"
    checkout.mkdir()
    git(["init", "-q", "-b", "main"], checkout)
    toplevel = git(["rev-parse", "--show-toplevel"], checkout).stdout.strip()
    if not toplevel or Path(toplevel).resolve() != checkout.resolve():
        print(f"ABORT: the scratch repository is not a repository at {checkout} "
              f"(git answered {toplevel!r}); no case was run against the hook")
        sys.exit(1)
    git(["config", "user.email", "test@example.invalid"], checkout)
    git(["config", "user.name", "style-guide-word-checker test"], checkout)
    (checkout / "docs").mkdir()
    (checkout / "docs" / "committed.md").write_text(COMMITTED_TEXT, encoding="utf-8")
    (checkout / ".gitignore").write_text("ignored-notes/\n", encoding="utf-8")
    git(["add", "-A"], checkout)
    committed = git(["commit", "-q", "-m", "a committed markdown file"], checkout)
    if committed.returncode != 0:
        print(f"ABORT: the scratch commit failed: {committed.stderr}")
        sys.exit(1)
    committed_file = checkout / "docs" / "committed.md"

    def reset_committed_file():
        committed_file.write_text(COMMITTED_TEXT, encoding="utf-8")

    # --- Edit -------------------------------------------------------------
    edited = COMMITTED_TEXT.replace("here before.", "here before the drain.")
    committed_file.write_text(edited, encoding="utf-8")
    result = run_hook(edit_payload(checkout, committed_file, "here before.",
                                   "here before the drain."))
    check("an Edit flags only its new_string, on a line that also holds an older hit",
          hit_lines(result, "docs/committed.md") == [(3, "drain")], result.stdout + result.stderr)

    reply = json.loads(result.stdout) if result.stdout.strip() else {}
    check("the real stdin-to-stdout path: one PostToolUse JSON object, exit 0, nothing on stderr",
          result.returncode == 0 and result.stderr == ""
          and reply.get("hookSpecificOutput", {}).get("hookEventName") == "PostToolUse"
          and agent_text(result).startswith("style-guide-word-checker: the text just written "
                                            "to docs/committed.md uses 1 word(s)")
          and 'docs/committed.md:3: "drain": queue-drain for the procedure' in agent_text(result)
          and "decision" not in reply,
          result.stdout + result.stderr)

    edited = COMMITTED_TEXT.replace("code block\n", "code block\nthe seat in code\n")
    committed_file.write_text(edited, encoding="utf-8")
    result = run_hook(edit_payload(checkout, committed_file, "code block\n",
                                   "code block\nthe seat in code\n"))
    check("an Edit inside a fenced code block in the file is not flagged", silent(result),
          result.stdout + result.stderr)

    edited = COMMITTED_TEXT + "\nOne walk.\n\nTwo: One walk.\n"
    committed_file.write_text(edited, encoding="utf-8")
    result = run_hook(edit_payload(checkout, committed_file, "x", "One walk.", replace_all=True))
    check("an Edit with replace_all flags every occurrence of its new_string",
          hit_lines(result, "docs/committed.md") == [(9, "walk"), (11, "walk")],
          result.stdout + result.stderr)

    reset_committed_file()
    result = run_hook(edit_payload(checkout, committed_file, "x", "a walk the file never got"))
    check("an Edit whose new_string is not in the file reports nothing", silent(result),
          result.stdout + result.stderr)

    # --- Write ------------------------------------------------------------
    result = write_then_run(checkout, committed_file, COMMITTED_TEXT + "\nThe drain is new.\n")
    check("a Write flags only the lines new against the committed file",
          hit_lines(result, "docs/committed.md") == [(9, "drain")], result.stdout + result.stderr)

    result = write_then_run(checkout, committed_file, COMMITTED_TEXT)
    check("a Write that rewrites a committed file unchanged reports nothing", silent(result),
          result.stdout + result.stderr)
    reset_committed_file()

    result = write_then_run(checkout, checkout / "docs" / "new-page.md",
                            "# New\n\nThe seat.\nThe walk.\n")
    check("a Write of a file git does not hold flags every line",
          hit_lines(result, "docs/new-page.md") == [(3, "seat"), (4, "walk")],
          result.stdout + result.stderr)

    result = write_then_run(checkout, checkout / "docs" / "pronouns.md",
                            "It is this, and they said that its parts work.\n")
    check("a pronoun is not flagged by the hook", silent(result), result.stdout + result.stderr)

    many = "".join(f"Line {number}: the seat.\n" for number in range(25))
    result = write_then_run(checkout, checkout / "docs" / "many-hits.md", many)
    listed = hit_lines(result, "docs/many-hits.md")
    check("at most 20 hits are listed, and the rest are counted",
          len(listed) == 20 and "5 more hit(s) in the same text are not listed"
          in agent_text(result), (len(listed), agent_text(result)[-200:]))

    # --- Files the hook leaves alone --------------------------------------
    result = write_then_run(checkout, checkout / "notes.txt", "The seat.\n")
    check("a non-markdown file produces no output", silent(result),
          result.stdout + result.stderr)

    result = write_then_run(checkout, checkout / "docs" / "walk" / "a-walk-document.md",
                            "The seat.\n")
    check("a file under docs/walk/ produces no output, even where git does not ignore it",
          silent(result), result.stdout + result.stderr)

    result = write_then_run(checkout, checkout / "ignored-notes" / "notes.md", "The seat.\n")
    check("a markdown file git ignores produces no output", silent(result),
          result.stdout + result.stderr)

    outside = tmp / "outside-the-checkout" / "notes.md"
    result = write_then_run(checkout, outside, "The seat.\n")
    check("a markdown file outside the session's checkout produces no output", silent(result),
          result.stdout + result.stderr)

    # --- Faults are silence -----------------------------------------------
    for case_name, payload in (("malformed JSON", "{not json"), ("a JSON list", "[1, 2]"),
                               ("empty input", "")):
        result = run_hook(payload)
        check(f"{case_name} on stdin exits 0 with no output", silent(result),
              result.stdout + result.stderr)

    lone_hook_directory = tmp / "hook-without-its-checker"
    lone_hook_directory.mkdir()
    lone_hook = lone_hook_directory / HOOK_PATH.name
    shutil.copy(str(HOOK_PATH), str(lone_hook))
    new_page = checkout / "docs" / "new-page.md"
    result = run_hook(write_payload(checkout, new_page, "The seat.\n"), hook_path=lone_hook)
    check("a checker that fails to load exits 0 with no output", silent(result),
          result.stdout + result.stderr)

if failures:
    print(f"\n{len(failures)} case(s) failed")
    sys.exit(1)
print("\nall cases passed")
