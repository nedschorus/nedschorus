#!/usr/bin/env python3
"""Run one judge cold-read-cell over one restater's restatements.

One invocation = one judge run. A restater is a model that read a rough
draft and said, in its own words, what each sentence of it means; the judge
reads that restatement beside the draft it came from, the perfect version of
that document and the scrubbed defect list between them, and reports which
listed defects the restatement caught and where the restatement was stupid.
Two runs of this cold-read-cell make one restater's score; the program that
launches both and scores them is nc-systems/cold-read/cold-read-restater-judge-runner.py.

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
  nc-systems/cold-read/cold-read-restater-judge-cell.py --restater gemini-3.8-flash-low \\
      --case <rough draft> <perfect version> <defect list> <restatement> \\
      --case ... --case ... \\
      --prompt-file <the judge's instructions> \\
      --report cold-read-records/2026-09-07-restater-judge-gemini-3.8-flash-low/\\
2026-09-07-restater-judge-gemini-3.8-flash-low--claude-restater-judge-run1.md

The judge writes its report to --report. This program prints progress to
stderr and nothing to stdout.

Exit codes: 0 a model produced a report; 1 every model in the chain failed to
produce one; 64 this program refused the invocation and never launched a
model, naming its own fix -- a --prompt-file naming no file, or naming an
empty one, is refused that way like any other bad invocation. 64 rather than the conventional 2 for the reason
written beside EXIT_BAD_INVOCATION in nc-systems/cold-read/cold-read-cell-common.py, which
every cold-read-cell shares.

WHAT THIS LEG SHARES WITH THE OTHER COLD-READ-CELLS, AND WHERE IT PARTS FROM THEM.
Everything after the prompt is composed is the shared module's: the model
chain and its fallback, the report-exists-iff-the-run-succeeded invariant, the
near-miss recovery, the stray-write detection, the provenance stamp, the exit
codes. The invocation is the Claude launcher's own -- this file imports
nc-systems/cold-read/cold-read-claude-cell.py and calls its `invocation_builder`, so the
argv the judge runs under cannot drift from the argv every other Claude
cold-read-cell runs under. Two things do part from the other cold-read-cells,
both because the ruled design asks for something their shape cannot express:

  - FOUR PATHS PER CASE, NOT ONE COLD-READ-TARGET. `common.run_cell` and its
    `--target` name one cold-read-target; a judge run reads twelve files in four
    roles. So this program parses its own arguments (through the shared
    argparse subclass, so a mistyped flag still leaves by exit 64) and
    composes its own prompt, then hands the composed prompt to the shared
    chain runner. `target=` in the stamp is the restatements under judgment,
    comma-joined: they are what this run judged.

  - TWO MODELS AT TWO EFFORTS. Every other chain runs one effort, so the
    shared runner took one. The ruling pins Fable at xhigh and Opus at max,
    which is one chain at two efforts, and a stamp reading `model=claude-opus-5
    effort=xhigh` would name a run that never happened. The shared runner
    therefore takes an optional `model_to_effort` map (added with this
    cold-read-cell) and stamps the effort of the model that actually
    produced the report.

WHERE THE JUDGE'S INSTRUCTIONS COME FROM: --prompt-file, and nowhere else.
This program holds no prompt of its own, and the flag is REQUIRED rather than
an override, which is the one thing about this cold-read-cell that is
not like the others. The judge's instructions are operative prose, and
this project reads operative prose BEFORE a pull request, by cold read
and by the user, because the pull-request process is the wrong instrument
for prose. Carrying the text inside this program would have landed it
through that wrong door. So the text travels separately, through the
user's walk, and this cold-read-cell refuses to run until a file holds
it -- which is the correct refusal: nothing should judge anything until
the user has read what the judge is told to do. The file's home once
he has walked it is .claude/skills/cold-read/prompts/restater-judge.md,
beside every other cold-read-cell's prompt, and .claude/ changes only
through that walk (.claude/hooks/instruction-file-guard.py, user-walked
2026-08-07, nedschorus#45). This is not the cold-read-fast-read's ruling
(nc-systems/cold-read/cold-read-fast-read.py holds its prompt in the file because the user
ruled that for the fast cold-read-cell).

WHY THIS COLD-READ-CELL HAS NO --tier. The other launchers take one because
they pin several measured cold-read-tiers and the flag chooses among them.
The judge has one configuration, the ruled one, so there is nothing to choose:
`tier=judge` is stamped as a constant. --model and --effort still override,
the way they do on every leg, for a caller who must name a model; a --model
this file pins no effort for is refused unless --effort names one, rather than
run at a level nobody chose.

WHY THIS COLD-READ-CELL'S STAMP CARRIES NO `tokens=` FIELD: the same reason
the Claude leg's does not -- the Claude CLI prints no "tokens used" line,
so the field is omitted rather than filled with a zero. If the CLI starts
printing one, the shared parser in nc-systems/cold-read/cold-read-cell-common.py picks
it up with no change here.
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

# Share the Claude invocation so CLI changes reach the judge too.
_claude_cell_spec = importlib.util.spec_from_file_location(
    "cold_read_claude_cell", pathlib.Path(__file__).with_name("cold-read-claude-cell.py")
)
claude_cell = importlib.util.module_from_spec(_claude_cell_spec)
_claude_cell_spec.loader.exec_module(claude_cell)

PROGRAM = "cold-read-restater-judge-cell"

JUDGE_RUNTIME = "claude"
JUDGE_CELL = "restater-judge"
JUDGE_TIER = "judge"

JUDGE_MODEL_CHAIN = ("claude-fable-5-1", "claude-opus-5")

# Stamp the effort of the model that actually produced the report.
JUDGE_MODEL_TO_REASONING_EFFORT = {
    "claude-fable-5-1": "xhigh",
    "claude-opus-5": "max",
}

# The restater label becomes a path segment in the runner’s record name.
RESTATER_CLASS_LABEL_PATTERN = re.compile(r"^[a-z0-9]+([.-][a-z0-9]+)*$")

CASE_FILE_ROLES = (
    ("rough draft", "the ROUGH DRAFT the restater read"),
    ("perfect version", "the PERFECT VERSION of that document"),
    ("defect list", "the DEFECT LIST, numbered, one row per defect"),
    ("restatement", "the RESTATEMENT under judgment"),
)
# The stamp’s target is the restatement being judged.
JUDGED_ROLE_INDEX = 3

# The runner counts reported items; model-generated totals would create a second answer to the same question.


def build_judge_argument_parser():
    # The shared parser preserves exit 64 for invocation errors; the judge needs four paths per case.
    parser = common.BadInvocationArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--restater", required=True, metavar="CLASS",
        help="the restater class under judgment, named as the roster names "
             "its models (gemini-3.8-flash-low, gpt-6-sol, claude-opus-5); "
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
        "--prompt-file", required=True, metavar="PATH",
        help="the file holding the judge's instructions, with "
             "{RESTATER_CLASS}, {CASES_BLOCK} and {REPORT_PATH} substituted "
             "into it; relative to the repository root unless absolute. "
             "Required: this program carries no prompt of its own, because "
             "the judge's instructions are prose the user reads before they "
             "land, not code that rides in on a pull request. The stamp "
             "records the path",
    )
    return parser


def validate_restater_class(restater_class: str) -> None:
    if not RESTATER_CLASS_LABEL_PATTERN.match(restater_class):
        raise common.CellRefusal(
            f"--restater {restater_class!r} cannot name a restater class: the "
            "label names the model under judgment and becomes a segment of "
            "this restater's record directory name, so it must be lowercase "
            "letters and digits joined by single hyphens or dots, like "
            "gemini-3.8-flash-low")


def resolve_judge_prompt_file(path_argument: str) -> pathlib.Path:
    # There is no default prompt; an empty file would launch a judge with no instructions.
    prompt_file = common.resolve_prompt_file(path_argument)
    if not prompt_file.read_text(encoding="utf-8").strip():
        raise common.CellRefusal(
            f"--prompt-file {prompt_file} is empty: it must hold the judge's "
            "instructions, with {RESTATER_CLASS}, {CASES_BLOCK} and "
            "{REPORT_PATH} in them. This program carries no prompt of its own")
    return prompt_file


def resolve_case_file(case_number: int, role: str, path_argument: str) -> pathlib.Path:
    """Resolve a case path, reporting its case number and role on failure."""
    path = pathlib.Path(path_argument)
    if not path.is_absolute():
        path = common.REPO_ROOT / path
    if not path.is_file():
        raise common.CellRefusal(
            f"case {case_number}: {role} not found: {path}")
    return path


def resolve_cases(case_arguments) -> list:
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
    blocks = []
    for case_number, files in enumerate(cases, start=1):
        lines = [f"Case {case_number}:"]
        for (_role, description), path in zip(CASE_FILE_ROLES, files):
            lines.append(f"  {description}: {path}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def compose_judge_prompt(
    restater_class: str, cases, report: pathlib.Path, prompt_file: pathlib.Path,
) -> str:
    template = prompt_file.read_text(encoding="utf-8")
    return (
        template
        .replace("{RESTATER_CLASS}", restater_class)
        .replace("{CASES_BLOCK}", render_cases_block(cases))
        .replace("{REPORT_PATH}", str(report))
    )


def judge_invocation_builder(model_to_effort: dict, uniform_effort: str):
    """Return an invocation builder using each model’s effort."""
    # Build per attempt: the Claude builder captures effort, and the models use different levels.
    def build_invocation(model: str, prompt: str):
        effort = model_to_effort.get(model, uniform_effort)
        return claude_cell.invocation_builder(effort)(model, prompt)
    return build_invocation


def main() -> int:
    # Start timing before fallback attempts so duration includes the whole run.
    cell_started_at = time.time()
    parser = build_judge_argument_parser()
    args = parser.parse_args()

    # Snapshot before launch to distinguish this run’s writes; None means unchecked, not clean.
    try:
        baseline = common.working_tree_state()
    except common.WriteDetectorUnavailable as error:
        baseline = None
        print(f"{PROGRAM}: could not snapshot the working tree ({error}); "
              "stray writes will not be checked for this run.", file=sys.stderr)

    # Refusals can precede report resolution, leaving no report path to exclude from stray writes.
    report = None
    try:
        validate_restater_class(args.restater)
        cases = resolve_cases(args.case)
        report = common.resolve_report_path(args.report)
        prompt_file = resolve_judge_prompt_file(args.prompt_file)
        prompt = compose_judge_prompt(args.restater, cases, report, prompt_file)
        chain = (args.model,) if args.model else JUDGE_MODEL_CHAIN
        # An unconfigured model needs explicit effort; do not invent an effort level.
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
        prompt_file_argument=args.prompt_file,
        model_to_effort=model_to_effort,
    )


if __name__ == "__main__":
    sys.exit(main())
