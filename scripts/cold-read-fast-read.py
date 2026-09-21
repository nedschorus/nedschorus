#!/usr/bin/env python3
"""Give one document the cold-read-fast-read: one fast-clarify cold-read-cell
on the fast cold-read-tier.

Usage:
  scripts/cold-read-fast-read.py --target docs/walk/foo-draft.md

WHAT IT DOES. Picks the report path from the cold-read-target, runs
ONE fast-clarify cold-read-cell on the fast cold-read-tier through
scripts/cold-read-agy-cell.py (user-ruled 2026-09-07 after measurements,
superseding the earlier ruling for low: Gemini 3.8 Flash at medium, about
100-110 s per document in single runs on a 658-word skill and a 1,967-word walk
draft, recall 42% against 19% at low on the ghi-write candidate defect list,
replacing gpt-5.6-terra at low), retries once if that cold-read-cell fails, and
then prints exactly one line on stdout: the report's absolute path on success,
or a line opening `FAILED` on failure. Exit 0 on success, 1 on failure, 64 when
the invocation itself was wrong (a --target that is not a file) and nothing
was launched. When the cold-read-target belongs to a class the
/cold-read skill's step 2 sends to the cold-read-full-run -- a skill or its
prompt, a file under docs/agents/, a wiki file, a design, a test design, a
component-contract -- the read also says that this fast read does not finish the
review: one line on stderr and one line in the report (user-ruled 2026-09-17,
item 4 of nedschorus#418, after a skill change merged on a fast read alone).
It warns and never refuses, because the fast read is the cold-read-full-run's
first step. When the cold-read-target is a walk draft, the read also lists every
bare issue or pull request number in it -- `#426`, `nedschorus#418`, a link
whose text is the number, and a task number written `#N` too, because
CLAUDE.md's citation rule covers tasks -- with one line on stderr giving the
count and a section at the end of the suggestions file naming each by line;
when the read itself failed there is no suggestions file, so that line says so
and the numbers are listed on stderr instead, each with its line
(user-ruled 2026-09-17, item 5 of nedschorus#418: the walk-me-through skill
forbids bare numbers, and walk files had carried 33 and 35 of them
unchecked). Bare file names and the walk's 300-word item cap are deliberately
not checked, by the same rulings. Every cold-read-cell's own progress -- the
launcher's stderr, the runtime's stderr, the stray-write and recovery lines --
is re-emitted on this program's stderr, so a caller watching stdout gets the
one line and a caller reading stderr gets the whole account.

WHAT THE REVIEWER ACTUALLY READS is not the cold-read-target but a copy of it
with an id on every sentence, `<file stem>-with-sentence-ids.md`, written by
this program before the cold-read-cell launches (nedschorus#284 step 2).
Question 1 asks for a restatement under each id, so the author's check stops
being an eyeball match between a restatement and a four-word anchor. When the
report lands, this program puts each original sentence under the restatement
claiming its id and appends a coverage section naming the sentences no
restatement claimed and any id the reviewer cited that the cold-read-target
does not have. A sentence never restated is a sentence the reviewer may never
have read, which is the failure the four-word anchor could not surface.

The markup never alters the cold-read-target. sentence_id_markup inserts
exactly two shapes and strip_sentence_ids removes exactly those two, so the
marked copy returns the original bytes; the test asserts that round trip.
On the records route the marked copy is kept beside the report and ships
with the cold-read-record, as the evidence of what was put in front of the
reviewer, and `target/` still holds the cold-read-target's own bytes. On the
walk route it is scratch.

WHERE THE REPORT GOES. A walk draft, `docs/walk/<name>-draft.md`, gets its
suggestions file beside it: `docs/walk/<name>-suggestions.md`, which is what
the walk reads next. Anything else -- a design, a skill, a record copy, a
file outside this checkout -- gets a cold-read-record of its own under the
gitignored records tree:
`cold-read-records/<name>-<YYYY-MM-DD>/fast-read.md`, where <name> is the
cold-read-target's file name without its extension -- `SKILL-<skill name>`
for a skill, whose file is always SKILL.md -- the date is local, and the
directory takes a -2, -3 suffix when the day's name is taken, the
cold-read-grid's rule (user-ruled 2026-09-18). That directory
also gets `target/<repository path>`, the exact bytes the reviewer read,
frozen before the cold-read-cell launches, and once the report has landed the
directory is shipped to the log-store on ned-box by
scripts/cold-read-record-ship.py, whose one line is printed on stderr as
`record:` (user-ruled 2026-09-07; a shipping failure never fails the read).
The cold-read-cell launcher pre-clears the report path, so a suggestions file
left by an earlier read is replaced, never appended to.

THE REVIEWER'S INSTRUCTIONS LIVE IN THIS FILE (user ruling): the text the
model receives is FAST_CLARIFY_PROMPT_TEMPLATE below, fed to the launcher
through --prompt-file from a temporary file, with --cell fast-clarify naming
the pass. The cold-read-cell's provenance stamp therefore carries
a `prompt_file=` field naming that temporary file; its basename
says where the text came from. The template is the user's own text:
.claude/skills/cold-read/prompts/fast-clarify.md as he walked and ruled
it, landed by PR #274 on 2026-09-07, copied here verbatim. A change to the
instructions is a one-hunk change to that one constant; nothing else in this
file knows what the text says. The prompt file under the skill is not read by
this program, so the two are kept in step by hand.

ONE RETRY, AND WHY NOT MORE. The cold-read-fast-read is a walk's instrument,
and the walk is waiting on it: a cold-read-cell that fails once -- a transient
CLI error, a model that neither wrote the file nor answered in chat -- is
worth one more try, and a cold-read-cell that fails twice is worth reporting
so the walk can go on without it. A refusal from the launcher (exit 64,
a bad invocation) is not retried, because the same invocation would be
refused the same way.
"""

from __future__ import annotations

import argparse
import datetime
import os
import importlib.util
import pathlib
import re
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
AGY_CELL_LAUNCHER = pathlib.Path(__file__).with_name("cold-read-agy-cell.py")
# The program that copies a cold-read-record to the log-store on ned-box
# (user-ruled 2026-09-07: cold-read-records are logs, not system). Run after
# a read on the records route lands its report; its one line goes to stderr,
# since this program's stdout is the report path and nothing else, and a
# shipping failure never fails the read.
RECORD_SHIPPER = pathlib.Path(__file__).with_name("cold-read-record-ship.py")
# What a cold-read-record is called and where it lives, defined once in a
# module so no program keeps its own copy (user-ruled 2026-09-19, walk
# file-naming-and-location-standards-cold-read-findings, item 4). The
# convention -- importlib for a module whose filename has hyphens -- is
# scripts/cold-read-cell-common.py's.
_record_names_spec = importlib.util.spec_from_file_location(
    "cold_read_record_names",
    pathlib.Path(__file__).with_name("cold-read-record-names.py"))
record_names = importlib.util.module_from_spec(_record_names_spec)
_record_names_spec.loader.exec_module(record_names)
WALK_DIRECTORY_RELATIVE = pathlib.Path("docs") / "walk"
RECORDS_DIR = record_names.RECORDS_DIR

FAST_READ_CELL = "fast-clarify"
FAST_READ_TIER = "fast"
# Attempts in all: the first run and one retry.
FAST_READ_ATTEMPTS = 2
# The launcher's own refusal code (EXIT_BAD_INVOCATION in
# scripts/cold-read-cell-common.py), which this program also uses for its
# own refusal and never retries.
EXIT_BAD_INVOCATION = 64

# The basename of the temporary prompt file. It shows up in the report's
# `prompt_file=` stamp field, so it says where the text came from.
EMBEDDED_PROMPT_FILE_NAME = "cold-read-fast-read-embedded-fast-clarify-prompt.md"

# The user's text (see the docstring): .claude/skills/cold-read/prompts/fast-clarify.md
# as landed by PR #274 on 2026-09-07, verbatim. {TARGET_PATH} and
# {REPORT_PATH} are substituted by the cold-read-cell launcher.
FAST_CLARIFY_PROMPT_TEMPLATE = """\
Read {TARGET_PATH} in full, including any YAML frontmatter, and answer three questions about it, in three sections, in the order below. Your context is deliberately minimal — what your runtime already loaded, the project glossary at `docs/nedschorus-wiki/nedschorus-glossary.md`, which you read before the documents, the document or documents under review, and whatever they reference by an explicit path. Nothing else: do not go looking. That limit is the point, because {TARGET_PATH} must be usable by a future agent who has only this info. {TARGET_PATH} is read-only: do not edit it or anything else in the checkout. The one file you create is your report. If {TARGET_PATH} contains multiple documents, treat them like chapters of one book: any one of them can define or explain what the others rely on, and they should be consistent amongst themselves; repetition is fine, gaps or inconsistencies are not. Read all of them, then answer the 3 questions for each document in the report.

## Question 1: What it says

Restate each document or source text as follows. For each sentence, write its id — the bracketed marker `[s12]` that begins it, brackets and all — on a line of its own, then one bullet per point, action, fact, idea, concept or claim in that sentence, in the order they were originally presented. The ids mark where each sentence begins: restate the text under the id it carries, and never merge two ids into one restatement or split one id into two. A heading, a table row or a fenced code block counts as a sentence; a list item is split into its sentences like any paragraph. A sentence may contain many points. Do not merge or omit details. Restate each point in your own plain, succinct words, literally and precisely. If a sentence or point does not make sense to you, your restatement may also not make sense, in which case add ?nonsense? to the end of that line or bullet. If there is a clear gap in the source text, note that gap with a bullet that says ?gap? followed by what is missing. In frontmatter, a data field such as a name, ids or dates gets no bullets; a prose field such as a description is treated like any other sentence. Your bullets, taken together, should be roughly the length of the original. This question exists so the author can check whether you understood what they meant, which is why you should be literal, and not try to guess a coherent meaning if there is none. Your rewrite helps the author determine if other agents correctly parse their text.

## Question 2: Where you struggled

Note where an agent might waste tokens or come to incorrect conclusions:

* every place in the text that seemed unclear, opaque, incoherent.
* ambiguities - phrases or sentences that could read two different ways, in which case describe both readings, including the use of pronouns with ambiguous subjects
* references that do not resolve - the file does not exist at the path stated
* meanings you resolved only by reading into it your own ideas, because the document is not clear and complete.
* undefined terms, or terms the document uses as if they were already defined
* references you could not follow - no explicit path is given, so the context rule above forbids looking for it

BE CONCISE: for each issue, quote the exact phrase and then a sentence naming the defect and why it matters. Focus on issues that would actually misdirect or block a fresh-reader following the document's instructions. Report every real issue you found — conciseness is about the length of each item, never about dropping a genuine problem. Number each item.

## Question 3: What it does not cover that it implies it should

The text explains something or tells its reader what to do. Find the gaps within its logic, situations it covers incompletely, likely cases or states that are not covered, or are covered in conflicting ways. Take each rule, instruction, case, or definition the document states, and ask what a reader needs to know that is not explained — a boundary value falling between two cases, a state the document's own machinery could reach but never names, a step with no stopping point, a failure the text neither handles nor rules out. BE CONCISE here too: for each gap, quote the relevant text and describe its gap. Ask this only of what {TARGET_PATH} sets out to cover; a subject it never takes up is not a gap.

Number the items in sections 2 and 3 separately, ORDERED MOST IMPORTANT FIRST — the issue most likely to stop a fresh-reader leads its section. If there are no issues, say "No issues".

Write your report to {REPORT_PATH}, once, when your analysis is complete. That file is your entire deliverable: what you say in conversation is discarded. Start your report with a list of the files you were told to examine. Note if you were unable to read any of them. {REPORT_PATH} is the only file to create; write nothing anywhere else.
"""

PROGRAM = "cold-read-fast-read"
WALK_DRAFT_SUFFIX = "-draft.md"
# Both endings are the walk-me-through skill's to name; this program only
# follows them, and scripts/walk-file-endings-match-the-skill-test.py fails
# if these two drift from what .claude/skills/walk-me-through/SKILL.md says
# (user-ruled 2026-09-19, walk
# file-naming-and-location-standards-cold-read-findings, item 4).
WALK_SUGGESTIONS_SUFFIX = "-suggestions.md"

# WHICH DOCUMENTS THIS READ DOES NOT FINISH (user-ruled 2026-09-17, item 4 of
# nedschorus#418, after PR #332 merged a skill change on a fast read alone).
# The /cold-read skill's step 2 sends a class of documents to the
# cold-read-full-run and gives everything else the fast read only. Nothing
# enforced that, so this program says so when its target is in that class:
# one line on stderr, and one line in the report that ships with the record.
# It is a warning, not a refusal -- the fast read is the full run's first
# step, so running it here is right; landing on it alone is what the ruling
# is against.
FULL_RUN_DIRECTORIES_RELATIVE = (
    (pathlib.Path(".claude") / "skills", "a skill or a skill's prompt"),
    (pathlib.Path("docs") / "agents", "a file under docs/agents/"),
    (pathlib.Path("docs") / "nedschorus-wiki", "a wiki file"),
)
# Designs, test designs and component-contracts are named, not placed: this
# project's designs live beside the issues, the cross-project specs and in
# docs/design-to-main/, and the state-machine design names all three files
# `<component>-design.md`, `<component>-contract.md` and
# `<component>-test-design.md` (its section on where artifacts land). Step 2
# and this program both use the glossary's term, component-contract. No
# directory is a design class: a directory entry for
# docs/design-to-main/ once called that directory's glossary "a design", and a
# design's glossary is not in step 2's list. The suffixes are matched whole, so
# `-design-notes.md` -- notes about a design, not the design -- is not one.
FULL_RUN_NAME_SUFFIXES = (
    ("-test-design.md", "a test design"),
    ("-contract.md", "a component-contract"),
    ("-design.md", "a design"),
)
# Step 1's own exceptions, which beat the classes above: a walk file, a
# handoff, a pull request description, an issue body, and CLAUDE.md all take
# the fast read and nothing more. Only the two that are files in this
# checkout can be recognised here.
FAST_READ_ONLY_NAMES = ("CLAUDE.md", "CLAUDE.local.md")


def full_run_class_of_target(target: pathlib.Path):
    """The name of the class that sends this target to the cold-read-full-run,
    or None when the fast read is the whole review.

    `target` is absolute and resolved. A file outside this checkout is not
    classified: the class list is about where a document lives in the
    repository, and a copy somewhere else is not that document.
    """
    try:
        relative = target.relative_to(REPO_ROOT)
    except ValueError:
        return None
    if relative.parent == WALK_DIRECTORY_RELATIVE or relative.name in FAST_READ_ONLY_NAMES:
        return None
    for directory, class_name in FULL_RUN_DIRECTORIES_RELATIVE:
        if directory in relative.parents:
            return class_name
    for suffix, class_name in FULL_RUN_NAME_SUFFIXES:
        if relative.name.endswith(suffix) and len(relative.name) > len(suffix):
            return class_name
    return None


def full_run_required_line(class_name: str) -> str:
    """The one sentence said on stderr and written into the report."""
    return (f"the cold-read-full-run is required before this document lands "
            f"({class_name}); this fast read is its first step, not the whole "
            f"review. Run scripts/cold-read-grid.py --target on it.")


def fast_read_report_path_for_target(
    target: pathlib.Path, now: datetime.datetime,
) -> pathlib.Path:
    """The path rule in the docstring, and nothing else.

    `target` is absolute and resolved; `now` is the one clock reading the
    record's name is taken from, and the walk route does not use it. A walk
    draft is recognised by where it sits and how it is named --
    `docs/walk/<name>-draft.md` under this checkout -- and a draft of that
    name in any other directory, or a walk file not named `-draft.md`, takes
    the records route like everything else.
    """
    try:
        relative = target.relative_to(REPO_ROOT)
    except ValueError:
        relative = None
    if (relative is not None
            and relative.parent == WALK_DIRECTORY_RELATIVE
            and relative.name.endswith(WALK_DRAFT_SUFFIX)
            and len(relative.name) > len(WALK_DRAFT_SUFFIX)):
        name = relative.name[:-len(WALK_DRAFT_SUFFIX)]
        return (REPO_ROOT / WALK_DIRECTORY_RELATIVE
                / f"{name}{WALK_SUGGESTIONS_SUFFIX}")
    return (fresh_record_dir(RECORDS_DIR / record_directory_name_for_target(target, now))
            / "fast-read.md")


# THE RECORD-NAME RULE (user-ruled 2026-09-18, walk
# docs/walk/cold-read-and-walk-file-names-and-dispositions, item 4):
# `<file stem>-<YYYY-MM-DD>`, and `SKILL-<skill name>-<YYYY-MM-DD>` for a
# skill; a second read of one document on one day takes -2, -3. The document
# comes first so every read of one document sits together in the log-store's
# listing. It replaced `<YYYY-MM-DD>-<HHMM>-<parent directory>-<file stem>`
# (ruled 2026-09-16), and knowingly gives up what that form bought: two
# documents with the same stem in different directories read on one day come
# out as -2 of each other (target/ shows which was which), and the -N count
# says nothing about which draft each read was. Both accepted at the walk.
# The code implementing it is not restated: scripts/cold-read-record-names.py
# holds it, and this program and scripts/cold-read-grid.py both import it, so
# the two cannot drift apart. scripts/cold-read-record-names-test.py fails a
# program that writes its own copy back. The report inside the record is
# bare `fast-read.md` (item 5): the directory says which read, the file says
# what it is.
RECORD_CLOCK_OVERRIDE_VARIABLE = "COLD_READ_RECORD_CLOCK_OVERRIDE"
RECORD_CLOCK_OVERRIDE_FORMAT = "%Y-%m-%dT%H:%M"


def record_clock_reading() -> datetime.datetime:
    """The ONE local clock reading a cold-read-record's date and time are both
    taken from, so the two cannot disagree across midnight.

    COLD_READ_RECORD_CLOCK_OVERRIDE, when set as `YYYY-MM-DDTHH:MM`, is read
    instead of the clock: it is how the test suites name a cold-read-record
    exactly without depending on the wall clock or flaking across a minute
    boundary.
    The override is a clock value, not a finished name, so the tests still go
    through the formatting below.
    """
    override = os.environ.get(RECORD_CLOCK_OVERRIDE_VARIABLE)
    if override:
        return datetime.datetime.strptime(override, RECORD_CLOCK_OVERRIDE_FORMAT)
    return datetime.datetime.now()


record_name_for_target = record_names.record_name_for_target
record_directory_name_for_target = record_names.record_directory_name_for_target


fresh_record_dir = record_names.fresh_record_directory


# --- Sentence ids -------------------------------------------------------
#
# nedschorus#284 step 2. The reader is handed a copy of the cold-read-target
# with an id on every sentence, and Question 1 asks it to restate each sentence
# under its id. That replaces the four-word anchor, which the 2026-09-07
# measurement found suppresses paraphrase but still leaves the author matching
# restatements to sentences by eye. With ids the match is mechanical, so this
# program can attach each original sentence to the restatement that claims it
# and name the sentences no restatement claimed.
#
# THE SPLIT IS MECHANICAL AND IMPERFECT BY RULING (the user, 2026-09-07: "I'm
# fine with 1 and 2", accepting a marked temporary copy and an imperfect
# split). A wrong boundary costs one mismatched id; it never loses text,
# because every line of the original is emitted unchanged apart from the
# inserted ids.
SENTENCE_ID_MARKED_COPY_SUFFIX = "-with-sentence-ids.md"
SENTENCE_ID_PATTERN = re.compile(r"\[s(\d+)\]")

# A sentence ends at . ! or ? plus any closing quote or bracket, then
# whitespace, then a character that can open a sentence. Abbreviations and
# decimals are the known misses and are accepted.
SENTENCE_END_PATTERN = re.compile(r"""[.!?]["')\]]*\s+""")
SENTENCE_OPENERS = "\"'(`[*_"
# The closing marks a sentence end may carry after its full stop. Stripped
# before asking whether a line's last sentence is finished, so `word."` reads
# as finished and not as a sentence still running (reviewer of PR #303).
SENTENCE_CLOSERS = "\"')]"

# A unit with no letter and no digit carries nothing to restate: a table's
# separator row `|---|---|`, a horizontal rule, a bare list marker. Giving it
# an id put it in the never-restated list of every report, which is a false
# signal in exactly the check the ids exist to provide (reviewer of PR #303).
def carries_words(text: str) -> bool:
    return any(character.isalnum() for character in text)

# Structures that are one unit each, whatever punctuation they contain: a
# heading, a table row, a fenced code block. Splitting a heading at its colon
# or a table row at a cell boundary would produce ids for fragments no reader
# thinks of as sentences.
HEADING_PATTERN = re.compile(r"^(\s*#{1,6}\s+)(.*)$")
TABLE_ROW_PATTERN = re.compile(r"^(\s*\|)(.*)$")
LIST_ITEM_PATTERN = re.compile(r"^(\s*(?:[-*+]|\d+[.)])\s+)(.*)$")
BLOCKQUOTE_PATTERN = re.compile(r"^(\s*>+\s*)(.*)$")
FRONTMATTER_FIELD_PATTERN = re.compile(r"^(\s*[A-Za-z0-9_.-]+:\s+)(\S.*)$")
CODE_FENCE_PATTERN = re.compile(r"^\s*(```|~~~)")


def split_into_sentences(text: str) -> list:
    """Split one line's prose into sentences, keeping every character.

    The pieces rejoin to exactly the input, trailing spaces included, so a
    marked line differs from the original only by the ids inserted into it.
    """
    pieces = []
    start = 0
    for match in SENTENCE_END_PATTERN.finditer(text):
        following = text[match.end():match.end() + 1]
        if following and (following.isupper() or following.isdigit()
                          or following in SENTENCE_OPENERS):
            pieces.append(text[start:match.end()])
            start = match.end()
    pieces.append(text[start:])
    return [piece for piece in pieces if piece.strip()] or [text]


def strip_sentence_ids(text: str) -> str:
    """The inverse of sentence_id_markup: return the document as it was.

    Exactly two shapes are ever inserted -- `[sN] ` immediately before a
    sentence, and ` [sN]` at the end of a code block's opening fence line --
    so removing exactly those two returns the original bytes. That invariant
    is what lets the marked copy be thrown away and the ids be trusted: a
    marked copy that does not strip back has altered the
    cold-read-target.
    """
    text = re.sub(r"\[s\d+\] ", "", text)
    return re.sub(r" \[s\d+\]$", "", text, flags=re.MULTILINE)


def sentence_id_markup(text: str):
    """Return (the marked copy, {id: original sentence}).

    Every line of the input survives in the output. Ids are inserted after a
    heading's hashes, after a list item's marker, after a table row's opening
    pipe, after a frontmatter field's key, and before each sentence of a
    paragraph. A fenced code block gets its id on a line of its own above the
    fence, because there is nowhere inside it to put one that markdown would
    not treat as code.

    A paragraph wrapped across several lines is not re-flowed. A line whose
    predecessor ended mid-sentence continues that sentence and gets no id of
    its own, so a wrapped sentence carries exactly one id.
    """
    lines = text.split("\n")
    marked = []
    sentences = {}
    counter = 0
    index = 0
    in_frontmatter = bool(lines) and lines[0].strip() == "---"
    continues_previous = False

    def take(sentence: str):
        """The id marker for this sentence, or None when there is nothing to
        restate; a caller that gets None emits the line unchanged."""
        nonlocal counter
        if not carries_words(sentence):
            return None
        counter += 1
        name = f"s{counter}"
        sentences[name] = sentence.strip()
        return f"[{name}]"

    def mark_prose(content: str, already_open: bool) -> str:
        """Insert an id before each sentence of one line's content."""
        out = []
        for position, piece in enumerate(split_into_sentences(content)):
            if position == 0 and already_open:
                out.append(piece)
                continue
            marker = take(piece)
            if marker is None:
                out.append(piece)
                continue
            leading = len(piece) - len(piece.lstrip())
            out.append(f"{piece[:leading]}{marker} {piece.lstrip()}")
        return "".join(out)

    def ends_open(content: str) -> bool:
        """True when this line's last sentence is unfinished, so the next
        line continues it."""
        stripped = content.rstrip().rstrip(SENTENCE_CLOSERS)
        return bool(stripped) and stripped[-1] not in ".!?:;|"

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if in_frontmatter:
            if index > 0 and stripped == "---":
                in_frontmatter = False
                marked.append(line)
            elif index == 0:
                marked.append(line)
            else:
                field = FRONTMATTER_FIELD_PATTERN.match(line)
                marker = take(field.group(2)) if field else None
                marked.append(f"{field.group(1)}{marker} {field.group(2)}"
                              if marker else line)
            index += 1
            continue

        if CODE_FENCE_PATTERN.match(line):
            closing = index + 1
            while closing < len(lines) and not CODE_FENCE_PATTERN.match(lines[closing]):
                closing += 1
            block = lines[index:closing + 1]
            marker = take(chr(10).join(block))
            marked.append(line if marker is None else f"{line} {marker}")
            marked.extend(block[1:])
            index = closing + 1
            continues_previous = False
            continue

        if not stripped:
            marked.append(line)
            continues_previous = False
            index += 1
            continue

        heading = HEADING_PATTERN.match(line)
        table_row = TABLE_ROW_PATTERN.match(line)
        if heading:
            marker = take(heading.group(2))
            marked.append(line if marker is None
                          else f"{heading.group(1)}{marker} {heading.group(2)}")
            continues_previous = False
        elif table_row:
            marker = take(table_row.group(2))
            marked.append(line if marker is None
                          else f"{table_row.group(1)}{marker} {table_row.group(2)}")
            continues_previous = False
        else:
            prefix_match = LIST_ITEM_PATTERN.match(line) or BLOCKQUOTE_PATTERN.match(line)
            prefix = prefix_match.group(1) if prefix_match else ""
            content = prefix_match.group(2) if prefix_match else line
            open_here = continues_previous and not prefix_match
            marked.append(prefix + mark_prose(content, open_here))
            continues_previous = ends_open(content)
        index += 1

    return "\n".join(marked), sentences


# The heading this program appends to the report. Named so a reader can tell
# the machine-written section from the reviewer's own text, and so a later
# pass can find it.
SENTENCE_COVERAGE_HEADING = "## Sentence coverage (added by cold-read-fast-read)"


def attach_sentences_and_coverage(report_text: str, sentences: dict,
                                  document: pathlib.Path = None,
                                  marked_copy_kept: pathlib.Path = None,
                                  full_run_class_name: str = None) -> str:
    """Put each original sentence under the restatement claiming its id, and
    append what the restatement missed.

    The reviewer sees only the marked copy, so its report cites ids and not
    the prose. Attaching the original here is what makes the report readable
    beside the cold-read-target without a second window, and the coverage list
    is the check the four-word anchor could not give: a sentence the reviewer
    never restated is a sentence it may never have read.

    Only an id STANDING ALONE on its line is treated as a restatement, which
    is the shape Question 1 asks for. An id cited inside a sentence of
    Question 2 or 3 is a reference to that sentence, not a restatement of it,
    and counting it as one marked a skipped sentence covered (reviewer of PR
    #303). Such a citation gets no original attached either, because attaching
    one under each would bury the reviewer's own words.
    """
    claimed = []
    unknown = []
    lines = []
    for line in report_text.split("\n"):
        lines.append(line)
        found = SENTENCE_ID_PATTERN.fullmatch(line.strip())
        if not found:
            continue
        name = f"s{found.group(1)}"
        if name in claimed or name in unknown:
            continue
        if name not in sentences:
            unknown.append(name)
            continue
        claimed.append(name)
        quoted = sentences[name].replace("\n", "\n> ")
        lines.append(f"> {quoted}")

    missing = [name for name in sentences if name not in claimed]
    coverage = [
        "",
        SENTENCE_COVERAGE_HEADING,
        "",
        f"- {len(sentences)} sentences in the document, {len(claimed)} restated.",
    ]
    coverage.append(
        f"- Never restated: {', '.join(missing)}. Check whether the reviewer read them."
        if missing else "- Every sentence was restated.")
    if document is not None:
        # The provenance stamp at the top of the report names the marked copy
        # the reviewer read, not the cold-read-target, so this line says which
        # cold-read-target that was (reviewer of PR #303). Whether the copy
        # is still there depends on the route, and saying it is gone when it
        # is not was the defect the reviewer of PR #307 caught: the records
        # route keeps it beside the report as evidence, and only the walk
        # route's copy is temporary.
        coverage.append(
            f"- The reviewer read `{marked_copy_kept}`, the marked copy of "
            f"`{document}`, kept beside this report."
            if marked_copy_kept is not None else
            f"- The reviewer read a marked copy of `{document}`; the `target=` "
            "stamp above names that copy, which was temporary and is gone.")
    if unknown:
        coverage.append(
            f"- Cited but not in the document: {', '.join(unknown)}. "
            "The reviewer invented these ids.")
    if full_run_class_name is not None:
        # The record ships to the log-store, so whoever reads it later sees
        # the same sentence the author saw on stderr.
        sentence = full_run_required_line(full_run_class_name)
        coverage.append(f"- {sentence[0].upper()}{sentence[1:]}")
    return "\n".join(lines).rstrip("\n") + "\n" + "\n".join(coverage) + "\n"


# A bare issue, pull request or task number: `#` and digits, with whatever
# repository name is glued to its front (`nedschorus#418`,
# `nedschorus/nedschorus#418`), because each is a number where CLAUDE.md wants
# a link-type and a title. A repository name may not start after a word
# character or any of `& / . : -`, so no piece of a URL's path becomes one. A
# bare `#` may not follow `&` or a word character, which keeps an HTML entity
# (`&#123;`) and a URL's fragment (`https://x.com/page#12`) out and still finds
# every number in `#214/#169` and `#264-#268`. A URL without a scheme is not
# kept out, nor one with `/` right before its `#` (`x.com/page#12` reads as an
# owner/repo reference), and no walk file has either. A markdown heading needs
# a space after its `#`, so `## 3` never matches. Measured on the 53 walk files
# in this checkout, 2026-09-18: 340, of which 269 bare `#N`, 53 with a
# repository prefix and 18 links whose text is the number; 32 follow the word
# task, and 10 sit in inline code quoting a draft.
BARE_REFERENCE_PATTERN = re.compile(
    r"(?:(?<![&\w/.:-])[A-Za-z0-9][\w.-]*(?:/[\w.-]+)?|(?<![&\w]))#\d+(?!\w)")

# The heading of the section this program appends to a walk draft's
# suggestions file, in the coverage heading's style.
BARE_REFERENCES_HEADING = (
    "## Bare issue, pull request and task numbers (added by cold-read-fast-read)")


def bare_references_in(text: str) -> list:
    """Every bare issue, pull request or task number in `text`, as (line number,
    reference) pairs in reading order, numbering lines from 1 the way an
    editor does."""
    return [(line_number, found.group(0))
            for line_number, line in enumerate(text.split("\n"), start=1)
            for found in BARE_REFERENCE_PATTERN.finditer(line)]


def bare_references_section(references: list) -> str:
    """The section a walk draft's suggestions file ends with: one instruction
    and a line per reference, or a line saying there are none. Text an agent
    reads and acts on, so it is the instruction and the list, nothing else."""
    lines = ["", BARE_REFERENCES_HEADING, ""]
    if not references:
        lines.append("- None.")
    else:
        lines.append("Replace each with its link-type and its title, as a link "
                     "when it can be opened: write PR [its title](its URL), "
                     "not PR #426.")
        lines.append("")
        lines.extend(f"- Line {line_number}: {reference}"
                     for line_number, reference in references)
    return "\n".join(lines) + "\n"


def freeze_target(target: pathlib.Path, record_dir: pathlib.Path) -> None:
    """Copy the cold-read-target's bytes into the cold-read-record before the
    cold-read-cell reads it, so the cold-read-record says exactly what was
    reviewed (user-ruled 2026-09-07)."""
    frozen = record_names.frozen_target_path(target, record_dir)
    frozen.parent.mkdir(parents=True, exist_ok=True)
    frozen.write_bytes(target.read_bytes())


def ship_record(record_dir: pathlib.Path) -> str:
    """The shipper's one line, or a FAILED line of this program's own when
    it could not run. Reported on stderr by the caller, never fatal."""
    try:
        completed = subprocess.run(
            [sys.executable, str(RECORD_SHIPPER), str(record_dir)],
            capture_output=True, text=True, check=False)
    except OSError as error:
        return f"FAILED: the shipper could not be run ({error}); the record stays on disk."
    sys.stderr.write(completed.stderr)
    lines = completed.stdout.strip().splitlines()
    return lines[0] if lines else (
        f"FAILED: the shipper printed nothing (exit {completed.returncode}); "
        f"the record stays on disk.")


def run_one_fast_clarify_cell(
    target: pathlib.Path, report: pathlib.Path, prompt_file: pathlib.Path,
) -> int:
    """One attempt through the launcher. Returns the launcher's exit code.

    Both of the launcher's streams are re-emitted on stderr: the launcher
    itself prints nothing on stdout, and this program's stdout is reserved
    for its one line.
    """
    command = [
        sys.executable, str(AGY_CELL_LAUNCHER),
        "--cell", FAST_READ_CELL, "--tier", FAST_READ_TIER,
        "--target", str(target), "--report", str(report),
        "--prompt-file", str(prompt_file),
    ]
    completed = subprocess.run(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL, cwd=REPO_ROOT, text=True, check=False,
    )
    if completed.stderr:
        print(completed.stderr, file=sys.stderr, end="")
    if completed.stdout:
        print(completed.stdout, file=sys.stderr, end="")
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--target", required=True,
        help="document path, relative to the repo root or absolute")
    args = parser.parse_args()

    target = pathlib.Path(args.target)
    if not target.is_absolute():
        target = REPO_ROOT / target
    target = target.resolve()
    if not target.is_file():
        print(f"{PROGRAM}: target not found: {target}", file=sys.stderr)
        print(f"FAILED (target not found: {target})")
        return EXIT_BAD_INVOCATION

    full_run_class_name = full_run_class_of_target(target)
    if full_run_class_name is not None:
        print(f"{PROGRAM}: {full_run_required_line(full_run_class_name)}",
              file=sys.stderr)

    report = fast_read_report_path_for_target(target, record_clock_reading())
    # A walk draft's report lands in docs/walk/ and is not a cold-read-record;
    # only the records route freezes the cold-read-target and ships.
    on_records_route = RECORDS_DIR in report.parents
    if on_records_route:
        freeze_target(target, report.parent)

    # Only a walk draft is checked for bare numbers. The author hears them
    # whether or not the read succeeds: a successful read lists them in the
    # suggestions file, and a failed one, which writes no file, lists them on
    # stderr instead. Each message is printed only once it is true.
    bare_references = (None if on_records_route
                       else bare_references_in(target.read_text(encoding="utf-8")))

    last_exit_code = 1
    with tempfile.TemporaryDirectory(prefix="cold-read-fast-read-") as scratch:
        prompt_file = pathlib.Path(scratch) / EMBEDDED_PROMPT_FILE_NAME
        prompt_file.write_text(FAST_CLARIFY_PROMPT_TEMPLATE, encoding="utf-8")
        # What the reviewer actually reads: the cold-read-target with an id on
        # every sentence. On the records route it is kept beside the report,
        # as the evidence of what was put in front of the reviewer; on the
        # walk route it is scratch and goes with the temporary directory.
        # Either way the cold-read-target itself is untouched, and target/
        # holds its original bytes.
        marked_text, sentences = sentence_id_markup(
            target.read_text(encoding="utf-8"))
        marked_copy = (report.parent if on_records_route else pathlib.Path(scratch)) / (
            f"{target.stem}{SENTENCE_ID_MARKED_COPY_SUFFIX}")
        marked_copy.write_text(marked_text, encoding="utf-8")
        for attempt in range(1, FAST_READ_ATTEMPTS + 1):
            last_exit_code = run_one_fast_clarify_cell(marked_copy, report, prompt_file)
            if last_exit_code == 0:
                # Before anything reads or ships it: put each original
                # sentence under the restatement claiming its id, and say
                # which sentences no restatement claimed.
                attached = attach_sentences_and_coverage(
                    report.read_text(encoding="utf-8"), sentences, target,
                    marked_copy if on_records_route else None,
                    full_run_class_name)
                if bare_references is not None:
                    attached += bare_references_section(bare_references)
                report.write_text(attached, encoding="utf-8")
                if bare_references:
                    print(f"{PROGRAM}: bare issue, pull request or task numbers in "
                          f"this walk draft: {len(bare_references)}; the suggestions "
                          "file lists each one.", file=sys.stderr)
                if on_records_route:
                    print(f"{PROGRAM}: record: {ship_record(report.parent)}", file=sys.stderr)
                print(report)
                return 0
            if last_exit_code == EXIT_BAD_INVOCATION:
                print(f"{PROGRAM}: the cell launcher refused the invocation "
                      f"(exit {EXIT_BAD_INVOCATION}); not retried, because the "
                      "same invocation would be refused the same way.",
                      file=sys.stderr)
                break
            if attempt < FAST_READ_ATTEMPTS:
                print(f"{PROGRAM}: attempt {attempt} of {FAST_READ_ATTEMPTS} failed "
                      f"(exit {last_exit_code}); retrying once.", file=sys.stderr)
    if bare_references:
        print(f"{PROGRAM}: bare issue, pull request or task numbers in this walk "
              f"draft: {len(bare_references)}. The read failed, so no suggestions "
              "file lists them. They are:", file=sys.stderr)
        for line_number, reference in bare_references:
            print(f"{PROGRAM}:   line {line_number}: {reference}", file=sys.stderr)
    print(f"FAILED (exit {last_exit_code} from the fast-clarify cell; "
          f"no report at {report})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
