#!/usr/bin/env python3
"""Run one judge cell over one restater's restatements.

One invocation = one judge run. A restater is a model that read a rough
draft and said, in its own words, what each sentence of it means; the judge
reads that restatement beside the draft it came from, the perfect version of
that document and the scrubbed defect list between them, and reports which
listed defects the restatement caught and where the restatement was stupid.
Two runs of this cell make one restater's score; the program that launches
both and scores them is scripts/cold-read-restater-judge-runner.py.

THE RULED DESIGN THIS IMPLEMENTS (user-ruled 2026-09-05, "Opus max is the
backup to Fable. y"). One fresh Claude Fable 5.1 instance at effort xhigh per
restater class, given the three rough drafts, the three perfect versions, the
three defect lists and that restater's three restatements. It counts the
problems the restatements caught, BY DEFECT NUMBER from the list, and the
places the restatement was stupid -- a sentence the perfect version keeps
unchanged that the restatement misread. Two judge runs per restater. When
Fable is unavailable -- the account limit, or a safeguard refusal that
returned no report -- Claude Opus 5 at max judges instead, and the record says
so. Problems a restatement caught that are not on the defect list go back to
the scrub rather than being scored. The walk that carries the ruling is
docs/walk/fast-cold-read-perfect-test-cases.md at the cold-read-research seat
(item 5, "Scoring, as ruled"; the critics are item 4), uncommitted there,
which is why the ruling is written out here.

Usage:
  scripts/cold-read-restater-judge-cell.py --restater gemini-3.8-flash-low \\
      --case <rough draft> <perfect version> <defect list> <restatement> \\
      --case ... --case ... \\
      --report cold-read-records/2026-09-07-restater-judge-gemini-3.8-flash-low/\\
2026-09-07-restater-judge-gemini-3.8-flash-low--claude-restater-judge-run1.md

The judge writes its report to --report. This program prints progress to
stderr and nothing to stdout.

Exit codes: 0 a model produced a report; 1 every model in the chain failed to
produce one; 64 this program refused the invocation and never launched a
model, naming its own fix. 64 rather than the conventional 2 for the reason
written beside EXIT_BAD_INVOCATION in scripts/cold-read-cell-common.py, which
every cell shares.

WHAT THIS LEG SHARES WITH THE OTHER CELLS, AND WHERE IT PARTS FROM THEM.
Everything after the prompt is composed is the shared module's: the model
chain and its fallback, the report-exists-iff-the-run-succeeded invariant, the
near-miss recovery, the stray-write detection, the provenance stamp, the exit
codes. The invocation is the Claude launcher's own -- this file imports
scripts/cold-read-claude-cell.py and calls its `invocation_builder`, so the
argv the judge runs under cannot drift from the argv every other Claude cell
runs under. Two things do part from the other cells, both because the ruled
design asks for something their shape cannot express:

  - FOUR PATHS PER CASE, NOT ONE TARGET. `common.run_cell` and its
    `--target` name one document; a judge run reads twelve files in four
    roles. So this program parses its own arguments (through the shared
    argparse subclass, so a mistyped flag still leaves by exit 64) and
    composes its own prompt, then hands the composed prompt to the shared
    chain runner. `target=` in the stamp is the restatements under judgment,
    comma-joined: they are what this run judged.

  - TWO MODELS AT TWO EFFORTS. Every other chain runs one effort, so the
    shared runner took one. The ruling pins Fable at xhigh and Opus at max,
    which is one chain at two efforts, and a stamp reading `model=claude-opus-5
    effort=xhigh` would name a run that never happened. The shared runner
    therefore takes an optional `model_to_effort` map (added with this cell)
    and stamps the effort of the model that actually produced the report.

WHY THE JUDGE'S INSTRUCTIONS ARE IN THIS FILE. Every other cell's prompt is a
file under .claude/skills/cold-read/prompts/, and that is where this one
belongs: JUDGE_PROMPT_TEMPLATE below is written to be moved there whole, and
--prompt-file already reads a template from anywhere. It is here because the
text is new prose that has had neither a cold read nor the user's walk, and
.claude/ changes only through that walk (.claude/hooks/instruction-file-guard.py,
user-walked 2026-08-07, nedschorus#45). Moving it is a one-hunk change once
the user has walked it: write the constant to
.claude/skills/cold-read/prompts/restater-judge.md and read it here through
the shared PROMPTS_DIR. This is not the fast read's ruling
(scripts/cold-read-fast-read.py holds its prompt in the file because the user
ruled that for the fast cell); it is a hold, not a home.

WHY THIS CELL HAS NO --tier. The other launchers take one because they pin
several measured tiers and the flag chooses among them. The judge has one
configuration, the ruled one, so there is nothing to choose: `tier=judge` is
stamped as a constant. --model and --effort still override, the way they do on
every leg, for a caller who must name a model; a --model this file pins no
effort for is refused unless --effort names one, rather than run at a level
nobody chose.

WHY THIS CELL'S STAMP CARRIES NO `tokens=` FIELD: the same reason the Claude
leg's does not -- the Claude CLI prints no "tokens used" line, so the field is
omitted rather than filled with a zero. If the CLI starts printing one, the
shared parser in scripts/cold-read-cell-common.py picks it up with no change
here.
"""

from __future__ import annotations

import argparse
import importlib.util
import pathlib
import re
import sys
import time

_common_spec = importlib.util.spec_from_file_location(
    "cold_read_cell_common", pathlib.Path(__file__).with_name("cold-read-cell-common.py")
)
common = importlib.util.module_from_spec(_common_spec)
_common_spec.loader.exec_module(common)

# The Claude leg itself, imported for its invocation: the judge is a Claude
# cell, and the one thing a cell owns is how it invokes its model. Importing
# rather than repeating means a change to the Claude invocation -- a flag the
# CLI renames, a tool the cells stop allowing -- reaches the judge with it.
_claude_cell_spec = importlib.util.spec_from_file_location(
    "cold_read_claude_cell", pathlib.Path(__file__).with_name("cold-read-claude-cell.py")
)
claude_cell = importlib.util.module_from_spec(_claude_cell_spec)
_claude_cell_spec.loader.exec_module(claude_cell)

PROGRAM = "cold-read-restater-judge-cell"

# The runtime and the two tokens the report's name and stamp carry. `cell` is
# the pass; `tier` is a constant here for the reason in the docstring.
JUDGE_RUNTIME = "claude"
JUDGE_CELL = "restater-judge"
JUDGE_TIER = "judge"

# The chain, in order (user-ruled 2026-09-05). Fable 5.1 judges; Opus 5 judges
# when Fable is unavailable, which the ruling names as the account limit or a
# safeguard refusal that returned no report -- the two ways the shared chain
# runner already recognises as an attempt that produced nothing (a non-zero
# exit, and an exit 0 with no report). The fallback is that chain and no
# separate mechanism: it clears the report path between attempts, records
# every failed attempt in `fallback_from=` on the stamp, and prints the
# shared FELL_BACK_PHRASE line the runner and the grid lift out of the log.
# This is the one chain in the fleet with a second entry; every tier the other
# legs pin has a single model (user-ruled 2026-09-04, Opus falling back to
# Fable is not valid for a REVIEW). A judgment is not a review, and the user
# ruled its backup explicitly, in those words.
JUDGE_MODEL_CHAIN = ("claude-fable-5-1", "claude-opus-5")

# Model -> the effort it judges at (user-ruled 2026-09-05: "fable at xhigh",
# "Opus max is the backup"). Two models, two efforts, which is why the shared
# chain runner takes this map: the stamp names the effort the model that
# produced the report actually ran at.
JUDGE_MODEL_TO_REASONING_EFFORT = {
    "claude-fable-5-1": "xhigh",
    "claude-opus-5": "max",
}

# What --restater may be: the restater class under judgment, named as the
# roster names its models (claude-opus-5, gpt-5.6-sol, gemini-3.8-flash-low).
# Lowercase letters and digits joined by single hyphens or dots, so the label
# is safe as a path segment -- the runner builds this restater's record
# directory name out of it -- and reads in a report as the model it names.
RESTATER_CLASS_LABEL_PATTERN = re.compile(r"^[a-z0-9]+([.-][a-z0-9]+)*$")

# The four files one case is made of, in the order --case takes them, each
# with the words the prompt introduces it by. The order is the pipeline's own:
# what the restater read, what it should have been, what is wrong with it,
# what the restater made of it.
CASE_FILE_ROLES = (
    ("rough draft", "the ROUGH DRAFT the restater read"),
    ("perfect version", "the PERFECT VERSION of that document"),
    ("defect list", "the DEFECT LIST, numbered, one row per defect"),
    ("restatement", "the RESTATEMENT under judgment"),
)
# The role whose paths become `target=` in the stamp: the restatements are
# what this run judged.
JUDGED_ROLE_INDEX = 3

# The judge's instructions. Written to be moved whole to
# .claude/skills/cold-read/prompts/restater-judge.md once the user has walked
# the text -- see the docstring. {RESTATER_CLASS}, {CASES_BLOCK} and
# {REPORT_PATH} are the substitutions `compose_judge_prompt` makes; the other
# cells' templates take {TARGET_PATH} and {REPORT_PATH}, and this one takes a
# block of cases instead of one target because a judge run reads twelve files.
#
# THE JUDGE COUNTS NOTHING, and the prompt says so twice. The ruling's score
# is arithmetic over the items the judge reports, and the 2026-08-29 trial's
# scorer "was wrong six ways until two agents hand-counted it" (the walk, item
# 5). So the model reports items, one per line, each line naming a defect
# number or quoting a sentence, and the runner counts the lines and computes
# the composite. A total of the model's own beside a total of the runner's
# would be two answers to one question.
JUDGE_PROMPT_TEMPLATE = """\
You are the judge of one restater. A restater is a model that was given a rough draft and asked to say, in its own words, what each sentence of it means — completely and literally, repairing nothing. The restater under judgment here is {RESTATER_CLASS}, and you judge its work on the cases below and on nothing else.

Each case gives you four files:

- the ROUGH DRAFT the restater read;
- the PERFECT VERSION of that same document, which is the draft as it should have been written;
- the DEFECT LIST, one numbered row per defect between the two, scrubbed by hand;
- the RESTATEMENT that {RESTATER_CLASS} produced from the rough draft.

{CASES_BLOCK}

Read every file in full before you judge anything. Your context is deliberately minimal — what your runtime already loaded and these files. Nothing else: do not go looking. These files are read-only: do not edit them, or anything else in the checkout. The one file you create is your report, described at the end.

For each case, report three kinds of item.

CAUGHT — a defect on that case's defect list that the restatement caught. A restatement catches a defect when its reading of the rough draft shows that defect to someone reading the restatement alone: it gives two readings of a sentence that supports two, says a term or a reference defeated it, marks a gap, says the sentence made no sense, or restates the sentence in a way that is wrong in the way the defect list says the sentence is wrong. Restating a defective sentence smoothly, as though nothing were wrong with it, is not catching it. Name the defect BY ITS NUMBER on that case's own defect list, and name each number at most once per case.

STUPID — a place the restatement was stupid: a sentence that the perfect version keeps unchanged and the restatement misread. That the perfect version keeps the sentence is what makes the misreading the restatement's error rather than the draft's, so check the perfect version before you report one. Quote the sentence, then say what the restatement made of it.

NOT-ON-LIST — a problem the restatement caught that no row of that case's defect list names. Report it and move on: these are not scored here, they go back to the scrub that built the list.

DO NOT COUNT, AND DO NOT SCORE. Report the items and nothing else: no totals, no percentages, no ranking, no closing summary. The counting and the score are done from your lines by the program that launched you, and a number of your own beside a number of its own would be two answers to one question.

FORMAT. Write one `## CASE <number>` heading per case, with the number exactly as this prompt gives it above, and put every item under the heading of the case it belongs to. Under a heading write that case's items, each on a line of its own:

## CASE 1

CAUGHT: <defect number> — <what the restatement says, and how that shows the defect>
STUPID: "<the sentence, quoted>" — <what the restatement made of it, and why that is a misreading>
NOT-ON-LIST: <the problem the restatement caught, and why no row of the list names it>

Every item is a single line, however long that line runs, beginning with `CAUGHT:`, `STUPID:` or `NOT-ON-LIST:`. An item broken across two lines is read as half an item, which is to say as none. A case with no items of one kind simply has none; write no placeholder line for it.

HOW TO DELIVER YOUR ANSWER. Write your answer to {REPORT_PATH}, with whatever file-writing tool you have. That file is your entire deliverable: this cell discards what you say in conversation, so an answer given only in chat is a lost answer. Write it once, when your judgment is complete, rather than building it up across several writes. A missing or empty report is read as a run that did not happen, and it is discarded and rerun. {REPORT_PATH} is the only file to create; write nothing anywhere else.
"""


def build_judge_argument_parser():
    """This cell's own argument surface, on the shared argparse subclass.

    The subclass is what keeps a mistyped flag leaving by exit 64 rather than
    argparse's default 2, which is the collision every cell avoids. The flags
    themselves cannot be the shared `build_argument_parser`'s: that one names
    one --target and one --tier, and a judge run takes four paths per case and
    has one tier.
    """
    parser = common.BadInvocationArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--restater", required=True, metavar="CLASS",
        help="the restater class under judgment, named as the roster names "
             "its models (gemini-3.8-flash-low, gpt-5.6-sol, claude-opus-5); "
             "lowercase letters and digits joined by single hyphens or dots",
    )
    parser.add_argument(
        "--case", required=True, action="append", nargs=4,
        metavar=("DRAFT", "PERFECT", "DEFECT_LIST", "RESTATEMENT"),
        help="one document's four files, in that order, each relative to the "
             "repository root or absolute. Repeat once per document; the "
             "ruled campaign passes three. The cases are numbered in the "
             "order given, and the judge reports against those numbers",
    )
    parser.add_argument(
        "--report", required=True,
        help="file the judge writes its report to; the caller names it, and a "
             "run that leaves it absent or empty fails",
    )
    parser.add_argument(
        "--model", help="explicit Claude model id; overrides the ruled chain "
                        "and runs alone, with no fallback",
    )
    parser.add_argument(
        "--effort", choices=["low", "medium", "high", "xhigh", "max"],
        help="reasoning effort, overriding the ruled per-model efforts for "
             "every model in the chain. Honored exactly, with no fallback, "
             "the way --model is",
    )
    parser.add_argument(
        "--prompt-file", metavar="PATH",
        help="read the judge's instructions from this file instead of the "
             "template in this program, with the same {RESTATER_CLASS}, "
             "{CASES_BLOCK} and {REPORT_PATH} substitution; relative to the "
             "repository root unless absolute. The stamp records the path",
    )
    return parser


def validate_restater_class(restater_class: str) -> None:
    """The label names a model and becomes a path segment. Refuse anything else."""
    if not RESTATER_CLASS_LABEL_PATTERN.match(restater_class):
        raise common.CellRefusal(
            f"--restater {restater_class!r} cannot name a restater class: the "
            "label names the model under judgment and becomes a segment of "
            "this restater's record directory name, so it must be lowercase "
            "letters and digits joined by single hyphens or dots, like "
            "gemini-3.8-flash-low")


def resolve_case_file(case_number: int, role: str, path_argument: str) -> pathlib.Path:
    """One of a case's four files, made absolute the way --target is.

    Its own refusal rather than `resolve_target`'s, because "target not
    found" would not say which of twelve paths was wrong: a judge run is
    refused here with the case number and the role, which is what the caller
    has to fix.
    """
    path = pathlib.Path(path_argument)
    if not path.is_absolute():
        path = common.REPO_ROOT / path
    if not path.is_file():
        raise common.CellRefusal(
            f"case {case_number}: {role} not found: {path}")
    return path


def resolve_cases(case_arguments) -> list:
    """Every case's four files, in order, numbered from 1 as the prompt numbers them."""
    cases = []
    for case_number, case_argument in enumerate(case_arguments, start=1):
        files = [
            resolve_case_file(case_number, role, path_argument)
            for (role, _description), path_argument
            in zip(CASE_FILE_ROLES, case_argument)
        ]
        cases.append(files)
    return cases


def render_cases_block(cases) -> str:
    """The case list as the judge reads it: one block per case, numbered, each
    path on its own line under the words the prompt introduces its role by."""
    blocks = []
    for case_number, files in enumerate(cases, start=1):
        lines = [f"Case {case_number}:"]
        for (_role, description), path in zip(CASE_FILE_ROLES, files):
            lines.append(f"  {description}: {path}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def compose_judge_prompt(
    restater_class: str, cases, report: pathlib.Path, prompt_file=None,
) -> str:
    """The exact text the judge receives.

    `prompt_file`, when given, is the template to read in place of
    JUDGE_PROMPT_TEMPLATE; the substitution is the same either way. This is
    also what a test calls to see what the model would be given, so a check
    is made against the text that runs rather than an approximation of it.
    """
    template = (
        prompt_file.read_text(encoding="utf-8") if prompt_file is not None
        else JUDGE_PROMPT_TEMPLATE
    )
    return (
        template
        .replace("{RESTATER_CLASS}", restater_class)
        .replace("{CASES_BLOCK}", render_cases_block(cases))
        .replace("{REPORT_PATH}", str(report))
    )


def judge_invocation_builder(model_to_effort: dict, uniform_effort: str):
    """The argv the judge runs under: the Claude leg's own, per model.

    `model_to_effort` is empty when --effort was named, and `uniform_effort`
    is then that level for every model in the chain; otherwise the map is the
    ruled one and `uniform_effort` is the level for a model it does not name,
    which the parser has already refused. The Claude launcher's builder is
    called per attempt rather than once, because the effort is what its
    closure holds and the two models in this chain do not share one.
    """
    def build_invocation(model: str, prompt: str):
        effort = model_to_effort.get(model, uniform_effort)
        return claude_cell.invocation_builder(effort)(model, prompt)
    return build_invocation


def main() -> int:
    # The cell's clock starts before anything else, so `duration_s=` in the
    # stamp is the cost of the whole cell -- a failed Fable attempt included --
    # rather than of the attempt that happened to succeed. The other legs take
    # it in the shared `run_cell`, which this leg's argument surface cannot use.
    cell_started_at = time.time()
    parser = build_judge_argument_parser()
    args = parser.parse_args()

    # The baseline is taken BEFORE anything runs, so what the detector reports
    # afterwards is what this run changed rather than what the tree already
    # held. A snapshot that cannot be taken yields None, which every reader
    # treats as "not checked" rather than as "nothing found".
    try:
        baseline = common.working_tree_state()
    except common.WriteDetectorUnavailable as error:
        baseline = None
        print(f"{PROGRAM}: could not snapshot the working tree ({error}); "
              "stray writes will not be checked for this run.", file=sys.stderr)

    # None until resolve_report_path returns one: a refusal raised before that
    # point still reports stray writes, and there is no report path to
    # subtract from them yet.
    report = None
    try:
        validate_restater_class(args.restater)
        cases = resolve_cases(args.case)
        report = common.resolve_report_path(args.report)
        prompt_file = (
            common.resolve_prompt_file(args.prompt_file) if args.prompt_file else None)
        prompt = compose_judge_prompt(args.restater, cases, report, prompt_file)
        chain = (args.model,) if args.model else JUDGE_MODEL_CHAIN
        # --effort names one level for the whole chain; without it each model
        # judges at the level the ruling pins for it. A --model this program
        # pins no effort for is refused rather than run at a level nobody
        # chose: the caller who named the model is the one who knows what to
        # ask for.
        model_to_effort = {} if args.effort else JUDGE_MODEL_TO_REASONING_EFFORT
        unpinned = [model for model in chain if model not in model_to_effort]
        if unpinned and not args.effort:
            raise common.CellRefusal(
                f"--model {', '.join(unpinned)} has no effort pinned in this "
                "program, and --effort names none: this cell pins "
                + ", ".join(f"{model} at {effort}" for model, effort
                            in JUDGE_MODEL_TO_REASONING_EFFORT.items())
                + ". Name --effort to run a model outside that map.")
    except common.CellRefusal as refusal:
        print(f"{PROGRAM}: {refusal}", file=sys.stderr)
        common.report_stray_writes(PROGRAM, baseline, report)
        return refusal.exit_code

    # The effort for a model the map does not name -- which, past the refusal
    # above, means --effort was given and holds for every model in the chain.
    uniform_effort = args.effort or JUDGE_MODEL_TO_REASONING_EFFORT[chain[0]]
    target_argument = ",".join(
        case_argument[JUDGED_ROLE_INDEX] for case_argument in args.case)

    return common.run_model_chain(
        program=PROGRAM, runtime=JUDGE_RUNTIME, chain=chain,
        effort=uniform_effort,
        build_invocation=judge_invocation_builder(model_to_effort, uniform_effort),
        prompt=prompt, report=report, cell=JUDGE_CELL, tier=JUDGE_TIER,
        target_argument=target_argument, baseline=baseline,
        cell_started_at=cell_started_at,
        prompt_file_argument=args.prompt_file or "",
        model_to_effort=model_to_effort,
    )


if __name__ == "__main__":
    sys.exit(main())
