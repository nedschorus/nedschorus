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

WHERE THE REPORT GOES. A walk draft, `docs/walk/<name>-draft.md`, gets its
suggestions file beside it: `docs/walk/<name>-suggestions.md`, which is what
the walk reads next. Anything else -- a design, a skill, a record copy, a
file outside this checkout -- gets a record directory of its own under the
gitignored records tree: `cold-read-records/<YYYY-MM-DD>-<name>/<name>-fast-read.md`,
where <name> is the target's file name without its extension. The cell
launcher pre-clears the report path, so a suggestions file left by an earlier
read is replaced, never appended to.

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
import subprocess
import sys
import tempfile
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
AGY_CELL_LAUNCHER = pathlib.Path(__file__).with_name("cold-read-agy-cell.py")
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
    return RECORDS_DIR / f"{today}-{name}" / f"{name}-fast-read.md"


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

    last_exit_code = 1
    with tempfile.TemporaryDirectory(prefix="cold-read-fast-read-") as scratch:
        prompt_file = pathlib.Path(scratch) / EMBEDDED_PROMPT_FILE_NAME
        prompt_file.write_text(FAST_CLARIFY_PROMPT_TEMPLATE, encoding="utf-8")
        for attempt in range(1, FAST_READ_ATTEMPTS + 1):
            last_exit_code = run_one_fast_clarify_cell(target, report, prompt_file)
            if last_exit_code == 0:
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
