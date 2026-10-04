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

import atexit
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Before anything runs git: a run started with GIT_DIR set, or with another
# variable that redirects git, must still build this suite's scratch
# repositories where the suite says, not in the repository the variable names.
_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().with_name(
        "git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

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


# The behavioural cases run against FIXTURE_PAGE, a copy of the page's table
# frozen here, through copies of the hook and the checker laid out as in the
# repository, so a row edited on the real page needs no edit to these cases.
# The real page is checked only for loading into a well-formed list.
FIXTURE_PAGE = '# Style guide (test fixture)\n\n## Words to avoid\n\n| Word | Forms flagged | Forms not flagged | Write instead | Applies to |\n|---|---|---|---|---|\n| `land` | `land`, `lands`, `landed`, `landing` | | "merge", "merges", "merged" or "merging", matching the form written | files, messages to other agents, messages to the user |\n| `home` | `home`, `homes` | `agent-home`, `/home/`, `home directory` | agent-home for the directory an agent-seat works in; canonical location for the one authoritative place a document or fact is kept | files, messages to other agents, messages to the user |\n| `draft` | `draft`, `drafts` | `-draft`, `docs/drafts/`, `draft pull request` | -draft for the filename suffix; "pending approval" for text that waits for the user\'s approval; "the `draft` label" for the GitHub label; `docs/drafts/` for the directory | files, messages to other agents, messages to the user |\n| `walk` | `walk`, `walks`, `walked`, `walking` | `approval-walk`, `approved-by-walk`, `walk-document`, `walk-minutes`, `/walk-me-through`, `docs/walk/` | approval-walk for the event; walk-document for the file `docs/walk/<name>.md`; approved-by-walk for what the user approved in an approval-walk; "put to the user in an approval-walk" for the act | files, messages to other agents, messages to the user |\n| `seat` | `seat`, `seats`, `seated` | `agent-seat`, `seat-branch`, `seat-brief`, `reincarnate-seat`, `retire-seat` | agent-seat for the identity; agent-session for one running conversation; "the agent-seat\'s name" for the name of an agent-seat; working directory for where an agent-session works when that is not its agent-seat\'s agent-home; cold-read-cell for one reviewer in a cold-read-full-run | files, messages to other agents, messages to the user |\n| `head` | `head`, `heads` | `head commit`, `frozen-head`, `HEAD`, `head branch` | head commit for the commit at the tip of a pull request\'s branch; frozen-head when the point is that the pushed head commit must not be amended; `HEAD`, in capitals, for what a Git checkout has checked out | files, messages to other agents, messages to the user |\n| `drain` | `drain`, `drains`, `drained`, `draining` | `queue-drain` | queue-drain for the procedure that empties the four queue directories and `docs/drafts/`; "is promoted to" for an item that leaves a queue for its approved location | files, messages to other agents, messages to the user |\n| `it` | `it` | | the noun the pronoun stands for, unless the noun is in the same sentence and no other noun there could be meant; a pronoun with no noun behind it, as in "it is raining", stays | messages to other agents, messages to the user |\n| `its` | `its` | | the noun the pronoun stands for, unless the noun is in the same sentence and no other noun there could be meant; a pronoun with no noun behind it, as in "it is raining", stays | messages to other agents, messages to the user |\n| `they` | `they` | | the noun the pronoun stands for, unless the noun is in the same sentence and no other noun there could be meant; a pronoun with no noun behind it, as in "it is raining", stays | messages to other agents, messages to the user |\n| `this` | `this` | | where "this" is used as a pronoun, the noun it stands for, unless the noun is in the same sentence and no other noun there could be meant; a pronoun with no noun behind it, as in "it is raining", stays | messages to other agents, messages to the user |\n| `that` | `that` | | where "that" is used as a pronoun, the noun it stands for, unless the noun is in the same sentence and no other noun there could be meant; a pronoun with no noun behind it, as in "it is raining", stays | messages to other agents, messages to the user |\n'


def build_checker_tree(root, page_text):
    """Lay out scripts/ and the style guide page under root; return (checker, hook) paths."""
    scripts_directory = Path(root) / "scripts"
    scripts_directory.mkdir(parents=True)
    page_path = Path(root) / "docs" / "nedschorus-wiki" / "nedschorus-style-guide.md"
    page_path.parent.mkdir(parents=True)
    page_path.write_text(page_text, encoding="utf-8")
    checker_copy = scripts_directory / CHECKER_PATH.name
    hook_copy = scripts_directory / HOOK_PATH.name
    shutil.copy(str(CHECKER_PATH), str(checker_copy))
    shutil.copy(str(HOOK_PATH), str(hook_copy))
    return checker_copy, hook_copy


FIXTURE_TREES_ROOT = Path(tempfile.mkdtemp(prefix="style-guide-word-checker-fixture-"))
atexit.register(shutil.rmtree, str(FIXTURE_TREES_ROOT), True)
FIXTURE_CHECKER_PATH, FIXTURE_HOOK_PATH = build_checker_tree(
    FIXTURE_TREES_ROOT / "fixture-page", FIXTURE_PAGE)

live_checker = load_module("style_guide_word_checker_live", CHECKER_PATH)
checker = load_module("style_guide_word_checker", FIXTURE_CHECKER_PATH)
hook = load_module("style_guide_word_checker_markdown_edit_hook", FIXTURE_HOOK_PATH)


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

forms = file_hit_forms("Intro.\n\n- ```sh\n  git switch seat\n  ```\n\nThe seat is free.\n")
check("a fence opened on a list item's marker line is code, and prose after it is read",
      forms == ["seat"]
      and [hit.line_number for hit in checker.find_style_guide_word_hits_in_markdown(
          "Intro.\n\n- ```sh\n  git switch seat\n  ```\n\nThe seat is free.\n",
          checker.APPLIES_TO_FILES)] == [7], forms)

forms = file_hit_forms("Run `git\nswitch seat --quiet` now.\n")
check("a code span that wraps across a line break is code on both lines", forms == [], forms)
forms = file_hit_forms("Run `git\nswitch seat` now, then the seat moves.\n")
check("prose after a wrapped code span closes is still read", forms == ["seat"], forms)
forms = file_hit_forms("A lone ` backtick.\nThe seat is free.\n")
check("a backtick never closed in its paragraph is literal, and later prose is read",
      forms == ["seat"], forms)

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

schema_problems = []
for entry in live_checker.STYLE_GUIDE_WORD_LIST:
    if entry.word not in entry.inflected_forms:
        schema_problems.append(f"{entry.word}: the word is not among its forms")
    if not entry.names_to_choose_from.strip():
        schema_problems.append(f"{entry.word}: no names to choose from")
    if not entry.applies_to or not set(entry.applies_to) <= set(checker.APPLIES_TO_VALUES):
        schema_problems.append(f"{entry.word}: applies_to {entry.applies_to!r}")
check("every entry of the real page carries its forms, names and where it applies", not schema_problems,
      schema_problems)

# The page is the list: a row edited on the page changes what the checker
# reports with no code change, so the real page is checked only for parsing
# into a non-empty, well-formed list.
check("the style guide page's table loads at least one entry",
      len(live_checker.STYLE_GUIDE_WORD_LIST) > 0, len(live_checker.STYLE_GUIDE_WORD_LIST))

WELL_FORMED_PAGE = """# Style guide

## Words to avoid

| Word | Forms flagged | Forms not flagged | Write instead | Applies to |
|---|---|---|---|---|
| `land` | `land`, `landed` | | "merge" | files, messages to other agents |
"""
parsed = checker.parse_words_to_avoid_table(WELL_FORMED_PAGE)
check("a well-formed table row parses into its entry",
      parsed == (checker.StyleGuideWordListEntry(
          "land", ("land", "landed"), (), '"merge"',
          (checker.APPLIES_TO_FILES, checker.APPLIES_TO_AGENT_MESSAGES)),), parsed)

MALFORMED_PAGES = {
    "a row with four cells": WELL_FORMED_PAGE.replace(' | files, messages to other agents |', ' |'),
    "a row whose word is not among its forms":
        WELL_FORMED_PAGE.replace("| `land` | `land`", "| `land` | `lands`"),
    "a row naming an unknown place to check":
        WELL_FORMED_PAGE.replace("files, messages to other agents", "files, commit messages"),
    "a forms cell with text outside code spans":
        WELL_FORMED_PAGE.replace("`land`, `landed`", "land, landed"),
    "a page without the heading": WELL_FORMED_PAGE.replace("## Words to avoid", "## Words"),
    "a table with other columns": WELL_FORMED_PAGE.replace("| Applies to |", "| Where |"),
    "a row without its leading pipe":
        WELL_FORMED_PAGE + "`home` | `home` | | agent-home | files |\n",
    "a row without its leading pipe between two rows":
        WELL_FORMED_PAGE + "`home` | `home` | | agent-home | files |\n"
        + "| `seat` | `seat` | | agent-seat | files |\n",
    "a table without its separator row":
        WELL_FORMED_PAGE.replace("|---|---|---|---|---|\n", "")
        + "| `seat` | `seat` | | agent-seat | files |\n",
}
for case_name, page in MALFORMED_PAGES.items():
    try:
        checker.parse_words_to_avoid_table(page)
        raised = False
    except checker.StyleGuidePageError:
        raised = True
    check(f"malformed table: {case_name} raises StyleGuidePageError", raised)



def load_checker_from_page(tree_name, page_text):
    checker_copy, _ = build_checker_tree(FIXTURE_TREES_ROOT / tree_name, page_text)
    return load_module("style_guide_word_checker_" + tree_name.replace("-", "_"), checker_copy)


try:
    no_exemptions = load_checker_from_page("no-forms-not-flagged", WELL_FORMED_PAGE)
    forms = [hit.form for hit in no_exemptions.find_style_guide_word_hits_in_markdown(
        "It landed.\n", no_exemptions.APPLIES_TO_FILES)]
    check("a page whose rows have no forms not flagged loads and flags", forms == ["landed"],
          forms)
except Exception as error:
    check("a page whose rows have no forms not flagged loads and flags", False, repr(error))

go_went_page = WELL_FORMED_PAGE.replace("| `land` | `land`, `landed` | | \"merge\" |",
                                        "| `go` | `go`, `went` | `go-ahead` | \"proceed\" |")
go_went = load_checker_from_page("form-not-beginning-with-its-word", go_went_page)
forms = [hit.form for hit in go_went.find_style_guide_word_hits_in_markdown(
    "They went home.\n", go_went.APPLIES_TO_FILES)]
check("a flagged form that does not begin with its row's word is flagged", forms == ["went"],
      forms)

capitalised_form_page = WELL_FORMED_PAGE.replace("| `land` | `land`, `landed` | | \"merge\" |",
                                                 "| `PR` | `PR`, `PRs` | | \"pull request\" |")
try:
    capitalised = load_checker_from_page("capitalised-flagged-form", capitalised_form_page)
    forms = [hit.form for hit in capitalised.find_style_guide_word_hits_in_markdown(
        "Open the PR now.\n", capitalised.APPLIES_TO_FILES)]
    check("a flagged form written with a capital is flagged", forms == ["PR"], forms)
except Exception as error:
    check("a flagged form written with a capital is flagged", False, repr(error))

PARSEABLE_TABLE_VARIANTS = {
    "a separator row without a trailing pipe":
        WELL_FORMED_PAGE.replace("|---|---|---|---|---|", "|---|---|---|---|---"),
    "an indented heading straight after the table": WELL_FORMED_PAGE + "  ## Next section\n",
}
for case_name, page in PARSEABLE_TABLE_VARIANTS.items():
    try:
        entries = checker.parse_words_to_avoid_table(page)
        check(f"parses: {case_name}", len(entries) == 1, entries)
    except checker.StyleGuidePageError as error:
        check(f"parses: {case_name}", False, repr(error))

INDENTED_CODE_CASES = {
    "an indented code block after prose": ("Some prose here.\n\n    git switch seat\n", []),
    "an indented code block at the start": ("    git switch seat\n", []),
    "a tab-indented code block": ("Prose.\n\n\tgit switch seat\n", []),
    "a list item's indented continuation is prose":
        ("- an item\n\n    continued about the seat\n", ["seat"]),
    "an indented line inside a paragraph is prose": ("prose\n    about the seat\n", ["seat"]),
    "prose after a list, then an indented code block":
        ("- a\n\nthe seat\n\n    code seat\n", ["seat"]),
    "a four-space paragraph after a two-space continuation of a list item is prose":
        ("- item\n\n  continuation\n\n    about the seat\n", ["seat"]),
    "a lazy continuation keeps the list item open":
        ("- item\nlazy line\n\n    about the seat\n", ["seat"]),
    "a list marker inside an indented code block is code, and a fence there opens nothing":
        ("    ~~~\n    - walk\n    ~~~\n\nThe seat is free.\n", ["seat"]),
    "a line indented one space after a blank keeps the list item open":
        ("- a\n\n x seat\n\n    code seat\n", ["seat", "seat"]),
    "an unindented line after a blank ends the list item, whatever its second character":
        ("- a\n\nA seat\n\n    code seat\n", ["seat"]),
}
for case_name, (text, expected) in INDENTED_CODE_CASES.items():
    forms = file_hit_forms(text)
    check(f"indented code: {case_name}", forms == expected, forms)

report_text = "\n".join(hook.REPORT_OPENING_LINES) + "\n" + hook.MORE_HITS_LINE
forms = file_hit_forms(report_text)
check("the report's own wording uses no listed word", forms == [], forms)


# ---------------------------------------------------------------------------
# The hook, run as a subprocess against a scratch repository.
# ---------------------------------------------------------------------------

def git(arguments, cwd):
    return subprocess.run(["git", *arguments], cwd=str(cwd), capture_output=True,
                          text=True, check=False, env=CLEAN_ENVIRONMENT)


def run_hook(payload, hook_path=FIXTURE_HOOK_PATH):
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
                                "newString": new_string, "originalFile": None,
                                "replaceAll": replace_all,
                                "structuredPatch": [],
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


def edit_hits(result, relative_path):
    """(form, the words around it) for every Edit hit line the agent was
    handed: `<path>, in "<words around>": "<form>": <names>`."""
    found = []
    prefix = relative_path + ', in "'
    for line in agent_text(result).split("\n"):
        if line.startswith(prefix):
            context, _, rest = line[len(prefix):].partition('": "')
            found.append((rest.partition('": ')[0], context))
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
    # An Edit's hits come from its new_string alone, reported with the words
    # around them and no line number: the file is never searched for the
    # text, so text that already stood in the file is never reported.
    edited = COMMITTED_TEXT.replace("here before.", "here before the drain.")
    committed_file.write_text(edited, encoding="utf-8")
    result = run_hook(edit_payload(checkout, committed_file, "here before.",
                                   "here before the drain."))
    check("an Edit flags only its new_string, not an older hit on the same line",
          edit_hits(result, "docs/committed.md") == [("drain", "here before the drain.")],
          result.stdout + result.stderr)

    reply = json.loads(result.stdout) if result.stdout.strip() else {}
    check("the real stdin-to-stdout path: one PostToolUse JSON object, exit 0, nothing on stderr",
          result.returncode == 0 and result.stderr == ""
          and reply.get("hookSpecificOutput", {}).get("hookEventName") == "PostToolUse"
          and agent_text(result).startswith("style-guide-word-checker: the text just written "
                                            "to docs/committed.md uses 1 word(s)")
          and 'docs/committed.md, in "here before the drain.": "drain": queue-drain for the '
              'procedure' in agent_text(result)
          and "decision" not in reply,
          result.stdout + result.stderr)

    committed_file.write_text("The seat stays.\nLater: the table.", encoding="utf-8")
    result = run_hook(edit_payload(checkout, committed_file, "the chair.", "the table."))
    check("an Edit whose new_string holds no listed word reports nothing, whatever the file "
          "already holds", silent(result), result.stdout + result.stderr)

    result = run_hook(edit_payload(checkout, committed_file, "x",
                                   "```\nthe seat in code\n```\n"))
    check("a fence that new_string opens is code", silent(result),
          result.stdout + result.stderr)

    # The accepted cost of not reading the file: text added inside a fence
    # the file already holds is read as prose, and the writer leaves it.
    result = run_hook(edit_payload(checkout, committed_file, "code block\n",
                                   "code block\nthe seat in code\n"))
    check("text added inside a fence the file already holds is flagged, the accepted cost",
          [form for form, _ in edit_hits(result, "docs/committed.md")] == ["seat"],
          result.stdout + result.stderr)

    # The piece may continue a list item the file holds above it, so an indented
    # line in an Edit's new_string is prose, never an indented code block.
    result = run_hook(edit_payload(checkout, committed_file, "x",
                                   "    The record is deleted once the work lands.\n\n"
                                   "    A second paragraph about the seat.\n"))
    check("an Edit whose new_string starts indented is searched as prose",
          [form for form, _ in edit_hits(result, "docs/committed.md")] == ["lands", "seat"],
          result.stdout + result.stderr)

    result = run_hook(edit_payload(checkout, committed_file, "x", "One walk.",
                                   replace_all=True))
    check("a replace_all Edit reports its new_string's hits once",
          edit_hits(result, "docs/committed.md") == [("walk", "One walk.")],
          result.stdout + result.stderr)

    result = run_hook(edit_payload(
        checkout, committed_file, "x",
        "one two three four five six head seven eight nine ten eleven"))
    check("an Edit hit is shown with four words either side of it",
          edit_hits(result, "docs/committed.md")
          == [("head", "three four five six head seven eight nine ten")],
          result.stdout + result.stderr)

    result = run_hook(edit_payload(checkout, committed_file, "x",
                                   "Read it\n\nsee (head)\n\nfirst"))
    check("the words around a hit keep the punctuation joined to the form and fold line "
          "breaks into spaces",
          edit_hits(result, "docs/committed.md") == [("head", "Read it see (head) first")],
          result.stdout + result.stderr)

    result = run_hook(edit_payload(checkout, committed_file, "x",
                                   "Notes kept at the end of the\nwalk minutes."))
    check("a hit that starts a line after five words keeps the line break as a space",
          edit_hits(result, "docs/committed.md")
          == [("walk", "the end of the walk minutes.")],
          result.stdout + result.stderr)

    started = time.monotonic()
    result = run_hook(edit_payload(checkout, committed_file, "x",
                                   "x" * 60000 + " one two three four five six head"))
    elapsed = time.monotonic() - started
    check("a 60 KB run with no whitespace before a hit is reported within 5 seconds",
          elapsed < 5 and edit_hits(result, "docs/committed.md")
          == [("head", "three four five six head")],
          "%.1f s; %s" % (elapsed, result.stdout + result.stderr))
    reset_committed_file()

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
    result = run_hook(edit_payload(checkout, checkout / "ignored-notes" / "notes.md",
                                   "The chair.", "The seat."))
    check("an Edit of a markdown file git ignores produces no output", silent(result),
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

    # A checker whose style guide page is missing raises at import, so the hook
    # loads no checker and stays silent rather than flagging against no list.
    pageless_scripts_directory = tmp / "pageless-checkout" / "scripts"
    pageless_scripts_directory.mkdir(parents=True)
    pageless_hook = pageless_scripts_directory / HOOK_PATH.name
    shutil.copy(str(HOOK_PATH), str(pageless_hook))
    shutil.copy(str(CHECKER_PATH), str(pageless_scripts_directory / CHECKER_PATH.name))
    result = run_hook(write_payload(checkout, new_page, "The seat.\n"), hook_path=pageless_hook)
    check("a checker without its style guide page exits 0 with no output", silent(result),
          result.stdout + result.stderr)

    # A page whose table is broken: the checker refuses to load rather than
    # flagging against the rows it could read, and the hook stays silent.
    broken_checker_path, broken_hook_path = build_checker_tree(
        tmp / "broken-page-checkout",
        FIXTURE_PAGE.replace("\n| `seat` |", "\n`seat` |"))
    try:
        load_module("style_guide_word_checker_broken_page", broken_checker_path)
        broken_load_raised = False
    except Exception as error:
        broken_load_raised = type(error).__name__ == "StyleGuidePageError"
    check("a broken style guide page makes the checker raise StyleGuidePageError at load",
          broken_load_raised)
    result = run_hook(write_payload(checkout, new_page, "The seat.\n"),
                      hook_path=broken_hook_path)
    check("a hook whose style guide page is broken exits 0 with no output", silent(result),
          result.stdout + result.stderr)

    # The last-resort handler: git missing from PATH raises FileNotFoundError
    # inside the hook, and only the top-level handler keeps that from
    # becoming a traceback after every markdown Edit.
    empty_path_directory = tmp / "empty-path-directory"
    empty_path_directory.mkdir()
    reset_committed_file()
    payload = edit_payload(checkout, committed_file, "here before.", "here before.")
    no_git = subprocess.run([sys.executable, str(HOOK_PATH)], input=json.dumps(payload),
                            capture_output=True, text=True, check=False,
                            env=dict(CLEAN_ENVIRONMENT, PATH=str(empty_path_directory)))
    check("a hook whose git cannot be found exits 0 with no output", silent(no_git),
          no_git.stdout + no_git.stderr)

if failures:
    print(f"\n{len(failures)} case(s) failed")
    sys.exit(1)
print("\nall cases passed")
