#!/usr/bin/env python3
"""Give one document the fast cold read: one fast-clarify cell on the fast tier.

Usage:
  scripts/cold-read-fast-read.py --target docs/walk/foo-draft.md

WHAT IT DOES. Picks the report path from the target, runs ONE fast-clarify
cell on the fast tier through scripts/cold-read-agy-cell.py (user-ruled
2026-09-07: Gemini 3.8 Flash at low, expected under one minute, replacing
gpt-5.6-terra at low), retries once if that cell fails, and then prints
exactly one line on stdout: the report's absolute path on success, or a line
opening `FAILED` on failure. Exit 0 on success, 1 on failure, 64 when the
invocation itself was wrong (a --target that is not a file) and nothing was
launched. Every cell's own progress -- the launcher's stderr, the runtime's
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
from. The template is PROVISIONAL: it is the text of
.claude/skills/cold-read/prompts/fast-clarify.md as it stood on main on
2026-09-07, copied here unchanged, and it will be replaced after the MD-skills
seat walks the prompt text with the user (their task #57). Replacing it is a
one-hunk change to that one constant; nothing else in this file knows what
the text says. The prompt file under the skill is not read by this program
and is not edited by this change.

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

# PROVISIONAL (see the docstring): .claude/skills/cold-read/prompts/fast-clarify.md
# as on main 2026-09-07, verbatim. To be replaced after the MD-skills seat's
# walk of the prompt text with the user (their task #57). {TARGET_PATH} and
# {REPORT_PATH} are substituted by the cell launcher.
FAST_CLARIFY_PROMPT_TEMPLATE = """\
Read {TARGET_PATH} in full, including any YAML frontmatter, and answer three questions about it, in three sections, in the order below. Your context is deliberately minimal — what your runtime already loaded, the document under review, and whatever that document references by an explicit path. Nothing else: do not go looking. That limit is the point, because {TARGET_PATH} must be usable by a future agent who has only this much. {TARGET_PATH} is read-only: do not edit it or anything else in the checkout. The one file you create is your report, described at the end.

## 1. What it says

Go section by section and restate, in your own words, what you take the text to
mean. Write what you actually took it to mean, not what you suppose the author
meant to say. Do not repair anything and do not fill gaps. BE CONCISE: one to
three sentences per section, complete in meaning — every claim the section makes
should be recognizable in your restatement — but not elaborated: no quotes, no
examples, no commentary. This section exists so the author can check whether
what you understood matches what they meant.

## 2. Where you stumbled

Name every place you had to guess, every word you could not resolve, and anything you could read two ways. A word you resolved only by assuming something the document never says is a stumble, even when your assumption turns out to be right — the next reader may assume differently. So is a term the document uses as if it were already defined, a reference you could not follow, and a pronoun whose subject you had to pick. BE CONCISE: for each item, quote the exact phrase and then give AT MOST ONE OR TWO SENTENCES naming what is unclear and why it matters. Focus on the issues that would actually block a fresh reader from acting on the document; a wobble a reader would resolve correctly anyway can be a single short line. Do not pad, do not restate the document, and do not repeat yourself between items. Report every real issue you found — conciseness is about the length of each item, never about dropping a genuine problem.

## 3. What it does not cover

The text tells a reader what to do in the situations it names. Find the situations it does not settle: one that matches none of its cases, and one that matches two of its cases at once without saying which wins. Take each rule, instruction, list of cases, or definition the document sets out, and ask what a reader can hit that it does not answer — a boundary value falling between two cases, a state the document's own machinery reaches but never names, a step with no stated stopping point, a failure the text neither handles nor rules out. BE CONCISE here too: for each item, quote the rule involved and describe the unhandled situation in at most one or two sentences. The same rule applies — every real gap gets an item, and no item gets padding. Ask this only of what {TARGET_PATH} sets out to govern itself; a subject it never takes up is not a gap.

Number the items in sections 2 and 3 separately, ORDERED MOST IMPORTANT FIRST — the issue most likely to stop a fresh reader leads its section — each opening with the quoted phrase it is about. OPEN EVERY ITEM WITH A CRITERION TAG — one bracket token naming what the finding violates: [guess] you had to guess; [term] a word or name you could not resolve; [two-readings] readable two ways; [no-rule] a situation left without a rule; [rule-conflict] a situation matching two rules at once; [other] plus one word when none fits. The tag comes before the quoted phrase. A ROUTING RULE RIDES THE TAGS, in both numbered sections: when the document itself cannot answer the thing you found — an undefined name, a reference that goes nowhere, a term whose meaning the document nowhere contains, a rule the document never states, two rules with no stated winner — PHRASE THE ITEM AS A QUESTION for the document's author or owner. Never phrase it as a rewrite instruction and never suggest what the answer might be: a rewriter who is handed a gap phrased as an instruction will invent an answer, and two rewriters will invent two different ones. In section 2, tag such an item [question] in place of the tag it would otherwise take — a [term] is only a [term] when the document contains the answer. In section 3, keep the [no-rule] or [rule-conflict] tag and still write the item as the question the owner must answer. A question-phrased item is one sentence: the quoted phrase, then the question. Do not propose fixes and do not rate severity or importance. When a section has nothing in it, write the section heading and one sentence saying you found nothing there and what you examined — a section left out reads as a section you skipped.

HOW TO DELIVER YOUR ANSWER. Write your answer to {REPORT_PATH}, with whatever file-writing tool you have. That file is your entire deliverable: this cell discards what you say in conversation, so an answer given only in chat is a lost answer. Write it once, when your analysis is complete, rather than building it up across several writes.

Write {REPORT_PATH} even when all three sections come back empty: say so in a sentence and name what you examined. A missing or empty report is read as a run that did not happen, and it is discarded and rerun. {REPORT_PATH} is the only file to create; write nothing anywhere else.
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
