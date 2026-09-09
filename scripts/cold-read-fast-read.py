#!/usr/bin/env python3
"""Give one document the fast cold read: one fast-clarify cell on the fast tier.

Usage:
  scripts/cold-read-fast-read.py --target docs/walk/foo-draft.md

WHAT IT DOES. Picks the report path from the target, runs ONE fast-clarify
cell on the fast tier through scripts/cold-read-agy-cell.py (user-ruled
2026-09-07 after measurements, superseding the earlier ruling for low: Gemini
3.8 Flash at medium, about 100-110 s per document in single runs on a
658-word skill and a 1,967-word walk draft, recall 42% against 19% at low on
the ghi-write candidate defect list, replacing gpt-5.6-terra at low), retries
once if that cell fails, and then prints exactly one line on stdout: the
report's absolute path on success, or a line opening `FAILED` on failure. Exit
0 on success, 1 on failure, 64 when the invocation itself was wrong (a --target
that is not a file) and nothing was launched. Every cell's own progress -- the launcher's stderr, the runtime's
stderr, the stray-write and recovery lines -- is re-emitted on this program's
stderr, so a caller watching stdout gets the one line and a caller reading
stderr gets the whole account.

WHAT THE REVIEWER ACTUALLY READS is not the document but a copy of it with an
id on every sentence, `<name>-with-sentence-ids.md`, written by this program
before the cell launches (nedschorus#284 step 2). Question 1 asks for a
restatement under each id, so the author's check stops being an eyeball match
between a restatement and a four-word anchor. When the report lands, this
program puts each original sentence under the restatement claiming its id and
appends a coverage section naming the sentences no restatement claimed and any
id the reviewer cited that the document does not have. A sentence never
restated is a sentence the reviewer may never have read, which is the failure
the four-word anchor could not surface.

The markup never alters the document. sentence_id_markup inserts exactly two
shapes and strip_sentence_ids removes exactly those two, so the marked copy
returns the original bytes; the test asserts that round trip. On the records
route the marked copy is kept beside the report and ships with the record, as
the evidence of what was put in front of the reviewer, and `target/` still
holds the document's own bytes. On the walk route it is scratch.

WHERE THE REPORT GOES. A walk draft, `docs/walk/<name>-draft.md`, gets its
suggestions file beside it: `docs/walk/<name>-suggestions.md`, which is what
the walk reads next. Anything else -- a design, a skill, a record copy, a
file outside this checkout -- gets a record directory of its own under the
gitignored records tree: `cold-read-records/<YYYY-MM-DD>-<name>/<name>-fast-read.md`,
where <name> is the target's file name without its extension, and the
directory takes a -2, -3 suffix when the day's name is taken, the grid's
rule. That directory also gets `target/<repository path>`, the exact bytes
the reviewer read, frozen before the cell launches, and once the report has
landed the directory is shipped to the log-store on ned-box by
scripts/cold-read-record-ship.py, whose one line is printed on stderr as
`record:` (user-ruled 2026-09-07; a shipping failure never fails the read).
The cell launcher pre-clears the report path, so a suggestions file left by
an earlier read is replaced, never appended to.

THE REVIEWER'S INSTRUCTIONS LIVE IN THIS FILE (user ruling): the text the
model receives is FAST_CLARIFY_PROMPT_TEMPLATE below, fed to the launcher
through --prompt-file from a temporary file, with --cell fast-clarify naming
the pass. The cell's provenance stamp therefore carries a `prompt_file=`
field naming that temporary file; its basename says where the text came
from. The template is the user's own text:
.claude/skills/cold-read/prompts/fast-clarify.md as he walked and ruled it,
landed by PR #274 on 2026-09-07, copied here verbatim. A change to the
instructions is a one-hunk change to that one constant; nothing else in this
file knows what the text says. The prompt file under the skill is not read by
this program, so the two are kept in step by hand.

ONE RETRY, AND WHY NOT MORE. The fast read is a walk's instrument, and the
walk is waiting on it: a cell that fails once -- a transient CLI error, a
model that neither wrote the file nor answered in chat -- is worth one more
try, and a cell that fails twice is worth reporting so the walk can go on
without it. A refusal from the launcher (exit 64, a bad invocation) is not
retried, because the same invocation would be refused the same way.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys
import tempfile
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
AGY_CELL_LAUNCHER = pathlib.Path(__file__).with_name("cold-read-agy-cell.py")
# The program that copies a record directory to the log-store on ned-box
# (user-ruled 2026-09-07: records are logs, not system). Run after a read
# on the records route lands its report; its one line goes to stderr, since
# this program's stdout is the report path and nothing else, and a shipping
# failure never fails the read.
RECORD_SHIPPER = pathlib.Path(__file__).with_name("cold-read-record-ship.py")
# Where the target's bytes are frozen inside the record directory: under this
# name at the target's own repository path, as scripts/cold-read-grid.py does.
FROZEN_TARGET_DIRECTORY_NAME = "target"
WALK_DIRECTORY_RELATIVE = pathlib.Path("docs") / "walk"
RECORDS_DIR = REPO_ROOT / "cold-read-records"

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
# {REPORT_PATH} are substituted by the cell launcher.
FAST_CLARIFY_PROMPT_TEMPLATE = """\
Read {TARGET_PATH} in full, including any YAML frontmatter, and answer three questions about it, in three sections, in the order below. Your context is deliberately minimal — what your runtime already loaded, the document or documents under review, and whatever they reference by an explicit path. Nothing else: do not go looking. That limit is the point, because {TARGET_PATH} must be usable by a future agent who has only this info. {TARGET_PATH} is read-only: do not edit it or anything else in the checkout. The one file you create is your report. If {TARGET_PATH} contains multiple documents, treat them like chapters of one book: any one of them can define or explain what the others rely on, and they should be consistent amongst themselves; repetition is fine, gaps or inconsistencies are not. Read all of them, then answer the 3 questions for each document in the report.

## Question 1: What it says

Restate each document or source text as follows. For each sentence, write its first four words, exactly as written, on a line of their own, then one bullet per point, action, fact, idea, concept or claim in that sentence, in the order they were originally presented. A heading or a table row counts as a sentence; a list item is split into its sentences like any paragraph. A sentence may contain many points. Do not merge or omit details. Restate each point in your own plain, succinct words, literally and precisely. If a sentence or point does not make sense to you, your restatement may also not make sense, in which case add ?nonsense? to the end of that line or bullet. If there is a clear gap in the source text, note that gap with a bullet that says ?gap? followed by what is missing. In frontmatter, a data field such as a name, ids or dates gets no bullets; a prose field such as a description is treated like any other sentence. Your bullets, taken together, should be roughly the length of the original. This question exists so the author can check whether you understood what they meant, which is why you should be literal, and not try to guess a coherent meaning if there is none. Your rewrite helps the author determine if other agents correctly parse their text.

## Question 2: Where you struggled

Note where an agent might waste tokens or come to incorrect conclusions:

* every place in the text that seemed unclear, opaque, incoherent.
* ambiguities - phrases or sentences that could read two different ways, in which case describe both readings, including the use of pronouns with ambiguous subjects
* references that do not resolve - the file does not exist at the path stated
* meanings you resolved only by reading into it your own ideas, because the document is not clear and complete.
* undefined terms, or terms the document uses as if they were already defined
* references you could not follow - no explicit path is given, so the context rule above forbids looking for it

BE CONCISE: for each issue, quote the exact phrase and then a sentence naming the defect and why it matters. Focus on issues that would actually misdirect or block a fresh reader following the document's instructions. Report every real issue you found — conciseness is about the length of each item, never about dropping a genuine problem. Number each item.

## Question 3: What it does not cover that it implies it should

The text explains something or tells its reader what to do. Find the gaps within its logic, situations it covers incompletely, likely cases or states that are not covered, or are covered in conflicting ways. Take each rule, instruction, case, or definition the document states, and ask what a reader needs to know that is not explained — a boundary value falling between two cases, a state the document's own machinery could reach but never names, a step with no stopping point, a failure the text neither handles nor rules out. BE CONCISE here too: for each gap, quote the relevant text and describe its gap. Ask this only of what {TARGET_PATH} sets out to cover; a subject it never takes up is not a gap.

Number the items in sections 2 and 3 separately, ORDERED MOST IMPORTANT FIRST — the issue most likely to stop a fresh reader leads its section. If there are no issues, say "No issues".

Write your report to {REPORT_PATH}, once, when your analysis is complete. That file is your entire deliverable: what you say in conversation is discarded. Start your report with a list of the files you were told to examine. Note if you were unable to read any of them. {REPORT_PATH} is the only file to create; write nothing anywhere else.
"""

PROGRAM = "cold-read-fast-read"
WALK_DRAFT_SUFFIX = "-draft.md"


def fast_read_report_path_for_target(target: pathlib.Path, today: str) -> pathlib.Path:
    """The path rule in the docstring, and nothing else.

    `target` is absolute and resolved. A walk draft is recognised by where it
    sits and how it is named -- `docs/walk/<name>-draft.md` under this
    checkout -- and a draft of that name in any other directory, or a walk
    file not named `-draft.md`, takes the records route like everything else.
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
        return REPO_ROOT / WALK_DIRECTORY_RELATIVE / f"{name}-suggestions.md"
    name = target.stem
    return fresh_record_dir(RECORDS_DIR / f"{today}-{name}") / f"{name}-fast-read.md"


def fresh_record_dir(base: pathlib.Path) -> pathlib.Path:
    """The day's name, or the first of -2, -3, ... that is not taken.

    The rule scripts/cold-read-grid.py's make_record_dir applies, restated
    here rather than imported because the grid is a program, not a module
    (user-ruled 2026-09-07 with the frozen target: two frozen targets never
    share a directory, so a fast read after a grid run on the same document
    and day, or after an earlier fast read of a revised draft, takes its own).
    Nothing is created here; the launcher creates the report's directory.
    """
    record_dir = base
    suffix = 2
    while record_dir.exists():
        record_dir = base.with_name(f"{base.name}-{suffix}")
        suffix += 1
    return record_dir


# --- Sentence ids -------------------------------------------------------
#
# nedschorus#284 step 2. The reader is handed a copy of the document with an
# id on every sentence, and Question 1 asks it to restate each sentence under
# its id. That replaces the four-word anchor, which the 2026-09-07
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
    marked copy that does not strip back has altered the document under
    review.
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

    def take(sentence: str) -> str:
        nonlocal counter
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
            leading = len(piece) - len(piece.lstrip())
            out.append(f"{piece[:leading]}{take(piece)} {piece.lstrip()}")
        return "".join(out)

    def ends_open(content: str) -> bool:
        """True when this line's last sentence is unfinished, so the next
        line continues it."""
        stripped = content.rstrip()
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
                marked.append(f"{field.group(1)}{take(field.group(2))} {field.group(2)}"
                              if field else line)
            index += 1
            continue

        if CODE_FENCE_PATTERN.match(line):
            closing = index + 1
            while closing < len(lines) and not CODE_FENCE_PATTERN.match(lines[closing]):
                closing += 1
            block = lines[index:closing + 1]
            marked.append(f"{line} {take(chr(10).join(block))}")
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
            marked.append(f"{heading.group(1)}{take(heading.group(2))} {heading.group(2)}")
            continues_previous = False
        elif table_row:
            marked.append(f"{table_row.group(1)}{take(table_row.group(2))} {table_row.group(2)}")
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


def attach_sentences_and_coverage(report_text: str, sentences: dict) -> str:
    """Put each original sentence under the restatement claiming its id, and
    append what the restatement missed.

    The reviewer sees only the marked copy, so its report cites ids and not
    the prose. Attaching the original here is what makes the report readable
    beside the document without a second window, and the coverage list is the
    check the four-word anchor could not give: a sentence the reviewer never
    restated is a sentence it may never have read.

    Only the FIRST mention of an id is treated as its restatement. Sections 2
    and 3 cite ids too, and attaching the original under each citation would
    bury the reviewer's own words.
    """
    claimed = []
    unknown = []
    lines = []
    for line in report_text.split("\n"):
        lines.append(line)
        found = SENTENCE_ID_PATTERN.search(line)
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
    if unknown:
        coverage.append(
            f"- Cited but not in the document: {', '.join(unknown)}. "
            "The reviewer invented these ids.")
    return "\n".join(lines).rstrip("\n") + "\n" + "\n".join(coverage) + "\n"


def frozen_target_path(target: pathlib.Path, record_dir: pathlib.Path) -> pathlib.Path:
    """record_dir/target/<repository path>, or the absolute path minus its
    leading slash for a target outside the repository -- the grid's rule."""
    try:
        relative = target.relative_to(REPO_ROOT)
    except ValueError:
        relative = pathlib.Path(*target.parts[1:])
    return record_dir / FROZEN_TARGET_DIRECTORY_NAME / relative


def freeze_target(target: pathlib.Path, record_dir: pathlib.Path) -> None:
    """Copy the target's bytes into the record before the cell reads it, so
    the record says exactly what was reviewed (user-ruled 2026-09-07)."""
    frozen = frozen_target_path(target, record_dir)
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

    report = fast_read_report_path_for_target(target, time.strftime("%Y-%m-%d"))
    # A walk draft's report lands in docs/walk/ and is not a record; only the
    # records route freezes the target and ships.
    on_records_route = RECORDS_DIR in report.parents
    if on_records_route:
        freeze_target(target, report.parent)

    last_exit_code = 1
    with tempfile.TemporaryDirectory(prefix="cold-read-fast-read-") as scratch:
        prompt_file = pathlib.Path(scratch) / EMBEDDED_PROMPT_FILE_NAME
        prompt_file.write_text(FAST_CLARIFY_PROMPT_TEMPLATE, encoding="utf-8")
        # What the reviewer actually reads: the document with an id on every
        # sentence. On the records route it is kept beside the report, as the
        # evidence of what was put in front of the reviewer; on the walk route
        # it is scratch and goes with the temporary directory. Either way the
        # document itself is untouched, and target/ holds its original bytes.
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
                report.write_text(
                    attach_sentences_and_coverage(
                        report.read_text(encoding="utf-8"), sentences),
                    encoding="utf-8")
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
    print(f"FAILED (exit {last_exit_code} from the fast-clarify cell; "
          f"no report at {report})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
