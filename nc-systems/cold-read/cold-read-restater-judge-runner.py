#!/usr/bin/env python3
"""Score one restater: two judge runs over its restatements, and one result.

One invocation = one restater class judged. It takes that restater's
restatements beside the rough drafts they came from, the perfect versions and
the scrubbed defect lists, launches the two ruled judge runs in parallel
through nc-systems/cold-read/cold-read-restater-judge-cell.py, and writes their two reports
and one combined result into a cold-read-record of this restater's own --
its own, and no earlier judging's: the default directory name takes a -2, -3
suffix when the day's name is taken, the way nc-systems/cold-read/cold-read-grid.py's
`make_record_dir` does, because the shared module clears a report path before
every run and a second judging on one name would delete the first's reports.

Usage:
  nc-systems/cold-read/cold-read-restater-judge-runner.py --restater gemini-3.8-flash-low \\
      --prompt-file <the judge's instructions> \\
      --case <rough draft> <perfect version> <defect list> <restatement> \\
      --case ... --case ...

--prompt-file is required, and is handed to both runs unchanged. Neither this
program nor the judge cold-read-cell carries the judge's instructions:
that text is operative prose, and this project reads operative prose before
a pull request, by cold read and by the user, so it travels through the
user's walk rather than inside a program. The cold-read-cell's docstring
says where it lands.

THE RULED DESIGN THIS IMPLEMENTS (user-ruled 2026-09-05, "Opus max is the
backup to Fable. y"), from item 5 of the walk
docs/walk/fast-cold-read-perfect-test-cases.md at the cold-read-research seat,
uncommitted there, which is why the ruling is written out here and in the
cold-read-cell. One fresh Fable 5.1 instance at xhigh per restater class, given
the three rough drafts, the three perfect versions, the three defect lists and
that restater's three restatements; it counts the problems the restatements
caught, BY DEFECT NUMBER, and the places the restatement was stupid -- a
sentence the perfect version keeps unchanged that the restatement misread --
and reports one score weighted 80 percent caught and 20 percent stupid, with
the raw counts beside the composite. TWO judge runs per restater, the two shown
separately when they disagree. Opus 5 at max judges when Fable is unavailable,
marked as such in the record. Problems a restatement caught that are not on the
defect list go back to the scrub rather than being scored.

WHAT THE MODEL DOES AND WHAT THIS PROGRAM DOES. The judge reports items: one
line per defect it says the restatement caught, naming the defect's number;
one line per place the restatement was stupid; one line per problem caught
that no row of the list names. It is told, twice, to count nothing and score
nothing. THIS program counts the lines and computes the composite, because
the arithmetic is the part a model gets wrong and a program does not -- the
2026-08-29 trial's scorer "was wrong six ways until two agents hand-counted
it" (the walk, item 5) -- and because a total of the model's beside a total
of this program's would be two answers to one question.

THE SCORE, and the one thing in it the ruling did not settle. The ruling says
one score weighted 80 percent caught and 20 percent stupid, with the raw
counts beside it; it does not say what either count is divided by. This
program divides by nothing:

    composite = 0.8 x caught - 0.2 x stupid

on the counts themselves, per case and pooled, with caught and stupid printed
beside every composite. Two reasons. Every restater class is judged on the
same cases against the same defect lists, so a denominator constant across
the classes cannot change which class scores higher -- normalizing would buy
nothing the ranking uses. And the only denominators available are a row count
parsed out of a hand-written defect list or a total the model reports, and
both put a fragile step between the judge and the score for a number the
ruling never asked for. If the user wants rates, the denominator's source is
his to rule.

WHEN A RUN FAILS. Both runs' reports are the evidence; the combined result is
the reading of them. One run failing does not throw the other away: the
combined result is written from the run that landed, with a marker line at
the top naming what is missing, and this program exits 1. Both failing leaves
no combined result at all, because there is nothing to read. A run whose
report cannot be parsed -- no `## CASE` heading in it naming one of the cases
this run was given -- is a failed run, not a restater that caught nothing:
zero and unreadable are different answers and this program never prints one
as the other.

WHERE AN ITEM GOES WHEN ITS CASE IS NOT CERTAIN: into the set-aside section of
the combined result, named and quoted, never into a case's count. A `## CASE
4` heading in a three-case run, a `## Summary` heading after the last case, an
item before the first heading -- each ends this program's certainty about
which case the items below belong to, and each sends them to that section with
the heading they sat under. Nothing is dropped and nothing is guessed at; the
rule and its one cost are written out over `parse_judge_report`.

NO RETRY, deliberately. The cold-read-fast-read retries its cold-read-cell
once because a walk is waiting on it. A judge run has already tried both models
in the ruled chain by the time it fails, so the retry that would help has
happened; what is left is an outage, and the record should say so rather than
spend another xhigh run on it.

Exit codes: 0 both runs were judged and scored; 1 one or both runs failed (the
combined result is still written when one landed); 64 this program refused the
invocation and never launched a run, naming its own fix.

Output: exactly one line on stdout -- the combined result's path on success,
or a line opening `FAILED` -- and every cold-read-cell's own progress on
stderr, the launcher's lines and the runtime's alike.
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import pathlib
import re
import subprocess
import sys
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
_record_names_spec = importlib.util.spec_from_file_location(
    "cold_read_record_names",
    pathlib.Path(__file__).with_name("cold-read-record-names.py"))
record_names = importlib.util.module_from_spec(_record_names_spec)
_record_names_spec.loader.exec_module(record_names)
RECORDS_DIR = record_names.RECORDS_DIR
JUDGE_CELL_LAUNCHER = pathlib.Path(__file__).with_name("cold-read-restater-judge-cell.py")

_judge_cell_spec = importlib.util.spec_from_file_location(
    "cold_read_restater_judge_cell", JUDGE_CELL_LAUNCHER
)
judge_cell = importlib.util.module_from_spec(_judge_cell_spec)
_judge_cell_spec.loader.exec_module(judge_cell)

# Reuse the judge's module object: loading again creates a distinct CellRefusal class that except will miss.
cell_common = judge_cell.common

PROGRAM = "cold-read-restater-judge-runner"

# A fixed run count keeps restater scores comparable.
JUDGE_RUNS = 2

EXIT_BAD_INVOCATION = cell_common.EXIT_BAD_INVOCATION

CAUGHT_WEIGHT = 0.8
STUPID_WEIGHT = 0.2

# The judge prompt requires one item per line; wrapped continuations are not separate items.
CASE_HEADING_PATTERN = re.compile(r"^#{1,6}\s*CASE\s+(\d+)\s*$", re.IGNORECASE)
# Require whitespace after heading hashes so a defect reference such as #3 does not end a case.
NON_CASE_HEADING_PATTERN = re.compile(r"^#{1,6}\s+\S")
CAUGHT_ITEM_PREFIX = "CAUGHT:"
STUPID_ITEM_PREFIX = "STUPID:"
NOT_ON_LIST_ITEM_PREFIX = "NOT-ON-LIST:"
# Allow decoration around defect numbers; unnumbered catches cannot identify a scored defect.
CAUGHT_DEFECT_NUMBER_PATTERN = re.compile(r"^[\s*_`#\[\(]*[Dd]?\s*(\d+)")

PARTIAL_RESULT_MARKER_PREFIX = "<!-- PARTIAL RESULT:"


def build_runner_argument_parser():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--restater", required=True, metavar="CLASS",
        help="the restater class under judgment, named as the roster names "
             "its models (gemini-3.8-flash-low, gpt-6-sol, claude-opus-5)")
    parser.add_argument(
        "--case", required=True, action="append", nargs=4,
        metavar=("DRAFT", "PERFECT", "DEFECT_LIST", "RESTATEMENT"),
        help="one document's four files, in that order, each relative to the "
             "repository root or absolute. Repeat once per document; the "
             "ruled campaign passes three")
    parser.add_argument(
        "--prompt-file", required=True, metavar="PATH",
        help="the file holding the judge's instructions, passed to both runs "
             "unchanged; relative to the repository root unless absolute. "
             "Required, because neither this program nor the judge cell "
             "carries that text -- see the module docstring")
    parser.add_argument(
        "--record-dir", metavar="PATH",
        help="where the two reports and the combined result go, used exactly "
             "as named and created if absent: a caller who names a directory "
             "owns what is already in it. By default "
             "cold-read-records/<date>-restater-judge-<class>/ under the "
             "repository root, which is gitignored, with -2, -3 appended when "
             "that name is taken so a second judging of one restater on one "
             "day cannot land on the first")
    return parser


def make_record_directory_for(restater_class: str, today: str) -> pathlib.Path:
    """Create a fresh record directory for the restater."""
    # Reserve the name with mkdir: reusing a directory would let report pre-clearing erase earlier results.
    record_dir = record_names.fresh_record_directory(
        RECORDS_DIR / f"{today}-restater-judge-{restater_class}")
    record_dir.mkdir(parents=True)
    return record_dir


def judge_report_path(record_dir: pathlib.Path, run_number: int) -> pathlib.Path:
    # Distinct run filenames keep near-miss recovery from confusing the two judge runs.
    return record_dir / (
        f"{record_dir.name}--{judge_cell.JUDGE_RUNTIME}-{judge_cell.JUDGE_CELL}"
        f"-run{run_number}.md")


def combined_result_path(record_dir: pathlib.Path) -> pathlib.Path:
    return record_dir / f"{record_dir.name}--{judge_cell.JUDGE_CELL}-combined.md"


def judge_cell_status_line(line: str, phrase: str) -> bool:
    """Return whether a line is the judge cell's own status carrying the phrase."""
    # A substring match could mistake quoted model text for launcher status.
    stripped = line.strip()
    return stripped.startswith(f"{judge_cell.PROGRAM}: {phrase}")


def launch_judge_runs(
    restater_class: str, case_arguments, record_dir: pathlib.Path,
    prompt_file_argument: str,
) -> dict:
    """Launch both runs and return their processes, report paths, and log paths."""
    # Close the parent's log handles after spawning; each child keeps its own copy.
    running = {}
    for run_number in range(1, JUDGE_RUNS + 1):
        report_path = judge_report_path(record_dir, run_number)
        stderr_path = record_dir / (report_path.name + ".stderr.log")
        command = [
            sys.executable, str(JUDGE_CELL_LAUNCHER),
            "--restater", restater_class,
            "--prompt-file", prompt_file_argument,
            "--report", str(report_path),
        ]
        for case_argument in case_arguments:
            command += ["--case", *case_argument]
        err = open(stderr_path, "w", encoding="utf-8")  # pylint: disable=consider-using-with
        process = subprocess.Popen(  # pylint: disable=consider-using-with
            command, stdout=err, stderr=err, stdin=subprocess.DEVNULL,
            cwd=REPO_ROOT,
        )
        err.close()
        running[run_number] = (process, report_path, stderr_path)
    return running


def wait_for_judge_runs(running: dict) -> dict:
    """Wait for both runs and return their exit codes, relaying logs and status lines."""
    exit_codes = {}
    while running:
        time.sleep(1)
        for run_number in sorted(running):
            process, _report_path, stderr_path = running[run_number]
            code = process.poll()
            if code is None:
                continue
            del running[run_number]
            exit_codes[run_number] = code
            log_text = stderr_path.read_text(encoding="utf-8")
            for line in log_text.splitlines():
                if judge_cell_status_line(line, cell_common.FELL_BACK_PHRASE):
                    print(f"{PROGRAM}: run {run_number} FELL BACK: {line.strip()}",
                          file=sys.stderr)
                if judge_cell_status_line(line, cell_common.STRAY_WRITE_PHRASE):
                    print(f"{PROGRAM}: run {run_number} STRAY WRITE: {line.strip()}",
                          file=sys.stderr)
                if judge_cell_status_line(
                        line, cell_common.STRAY_WRITE_CHECK_SKIPPED_PHRASE):
                    print(f"{PROGRAM}: run {run_number} WRITE CHECK DID NOT RUN: "
                          f"{line.strip()}", file=sys.stderr)
                if judge_cell_status_line(line, cell_common.NEAR_MISS_RECOVERY_PHRASE):
                    print(f"{PROGRAM}: run {run_number} RECOVERED: {line.strip()}",
                          file=sys.stderr)
            print(log_text, file=sys.stderr, end="")
            print(f"{PROGRAM}: run {run_number} finished (exit {code}).",
                  file=sys.stderr)
    return exit_codes


def provenance_fields(report_text: str) -> dict:
    """Return provenance fields, or an empty mapping when no stamp is present."""
    first_line = report_text.split("\n", 1)[0]
    if not first_line.startswith("<!-- provenance:"):
        return {}
    fields = {}
    for token in first_line.split():
        if "=" in token:
            name, _, value = token.partition("=")
            fields[name] = value
    return fields


def parse_judge_report(report_text: str, case_count: int) -> dict:
    """Parse report items by case, retaining unplaceable items separately."""
    # Count each defect number once; repeated mentions are not additional catches.
    # Any non-case heading ends attribution so later items are not scored against the wrong case.
    cases = {}
    outside = []
    headings_naming_no_case = []
    current_case = None
    current_heading = ""
    for raw_line in report_text.splitlines():
        line = raw_line.strip()
        case_heading = CASE_HEADING_PATTERN.match(line)
        if case_heading:
            current_heading = line
            case_number = int(case_heading.group(1))
            if 1 <= case_number <= case_count:
                current_case = case_number
                cases.setdefault(case_number, {
                    "caught": [], "caught_lines": [], "stupid": [],
                    "not_on_list": [], "unnumbered_caught": [],
                })
            else:
                # Do not create out-of-range cases: a report with no valid cases is unusable, not an empty score.
                current_case = None
                if line not in headings_naming_no_case:
                    headings_naming_no_case.append(line)
            continue
        if NON_CASE_HEADING_PATTERN.match(line):
            current_case = None
            current_heading = line
            continue
        for prefix, key in (
            (CAUGHT_ITEM_PREFIX, "caught"),
            (STUPID_ITEM_PREFIX, "stupid"),
            (NOT_ON_LIST_ITEM_PREFIX, "not_on_list"),
        ):
            # Case-insensitive prefixes accept Caught: as the same item type as CAUGHT:.
            if not line.upper().startswith(prefix):
                continue
            body = line[len(prefix):].strip()
            if current_case is None:
                outside.append((current_heading, line))
                break
            case = cases[current_case]
            if key != "caught":
                case[key].append(body)
                break
            case["caught_lines"].append(body)
            number_match = CAUGHT_DEFECT_NUMBER_PATTERN.match(body)
            if not number_match:
                case["unnumbered_caught"].append(body)
                break
            defect_number = int(number_match.group(1))
            if defect_number not in case["caught"]:
                case["caught"].append(defect_number)
            break
    return {
        "cases": cases,
        "items_outside_any_case": outside,
        "case_headings_naming_no_case_of_this_run": headings_naming_no_case,
    }


def composite_score(caught_count: int, stupid_count: int) -> float:
    # Round to avoid displaying binary floating-point artifacts as different scores.
    return round(CAUGHT_WEIGHT * caught_count - STUPID_WEIGHT * stupid_count, 2)


def score_run(parsed: dict, case_count: int) -> dict:
    """Return counts and composite scores per case and pooled."""
    # A missing case heading means no report on that case, not zero findings.
    per_case = []
    pooled_caught = 0
    pooled_stupid = 0
    for case_number in range(1, case_count + 1):
        case = parsed["cases"].get(case_number)
        caught_count = len(case["caught"]) if case else 0
        stupid_count = len(case["stupid"]) if case else 0
        pooled_caught += caught_count
        pooled_stupid += stupid_count
        per_case.append({
            "case": case_number,
            "reported": case is not None,
            "caught": caught_count,
            "caught_numbers": list(case["caught"]) if case else [],
            "stupid": stupid_count,
            "not_on_list": list(case["not_on_list"]) if case else [],
            "unnumbered_caught": list(case["unnumbered_caught"]) if case else [],
            "composite": composite_score(caught_count, stupid_count),
        })
    return {
        "per_case": per_case,
        "pooled_caught": pooled_caught,
        "pooled_stupid": pooled_stupid,
        "pooled_composite": composite_score(pooled_caught, pooled_stupid),
    }


def read_run(report_path: pathlib.Path, exit_code: int, case_count: int) -> dict:
    """Read a run's provenance and findings, distinguishing missing, unusable, and scoreable reports."""
    run = {
        "report_path": report_path, "exit_code": exit_code, "model": "",
        "effort": "", "fallback_from": "", "usable": False, "why_unusable": "",
        "parsed": None, "score": None,
    }
    report_text = (
        report_path.read_text(encoding="utf-8") if report_path.is_file() else "")
    if not report_text.strip():
        run["why_unusable"] = (
            f"no report at {report_path} (the cell exited {exit_code}); a run "
            "that produced no report is not a judge that found nothing")
        return run
    fields = provenance_fields(report_text)
    run["model"] = fields.get("model", "")
    run["effort"] = fields.get("effort", "")
    run["fallback_from"] = fields.get("fallback_from", "")
    parsed = parse_judge_report(report_text, case_count)
    run["parsed"] = parsed
    if not parsed["cases"]:
        naming_no_case = parsed["case_headings_naming_no_case_of_this_run"]
        found = (
            " (its heading" + ("s name" if len(naming_no_case) > 1 else " names")
            + " no case of this run: " + ", ".join(f"`{heading}`"
                                                   for heading in naming_no_case)
            + ")" if naming_no_case else "")
        run["why_unusable"] = (
            f"{report_path.name} holds no `## CASE <number>` heading naming "
            f"one of this run's {case_count} case(s){found}, so none of its "
            "text can be placed on a case; that is a report this program "
            "cannot read, not a restater that caught nothing")
        return run
    run["usable"] = True
    run["score"] = score_run(parsed, case_count)
    return run


def format_defect_numbers(numbers) -> str:
    return ", ".join(str(number) for number in sorted(numbers)) if numbers else "none"


def render_combined_result(
    restater_class: str, cases, runs: dict, case_arguments,
) -> str:
    usable_runs = {number: run for number, run in runs.items() if run["usable"]}
    lines = []

    missing = [number for number in sorted(runs) if not runs[number]["usable"]]
    if missing:
        lines.append(
            f"{PARTIAL_RESULT_MARKER_PREFIX} "
            + "; ".join(f"run {number} was not scored — {runs[number]['why_unusable']}"
                        for number in missing)
            + f". What follows reads {len(usable_runs)} of {JUDGE_RUNS} judge runs, "
              "so it is not the two-run result the ruling asks for. Re-run the "
              "restater's judging before quoting these numbers against another "
              "restater's. -->")
        lines.append("")

    lines.append(f"# Restater judge — {restater_class}")
    lines.append("")
    lines.append(
        "The ruled restater score (user-ruled 2026-09-05): two judge runs, "
        "Claude Fable 5.1 at xhigh with Claude Opus 5 at max as the backup "
        "when Fable is unavailable, over one restater's restatements beside "
        "the rough drafts, the perfect versions and the defect lists. The "
        "judge reported items; this file's counts and composites were "
        f"computed from those items by {PROGRAM}, never by the model.")
    lines.append("")

    lines.append("## Who judged")
    lines.append("")
    lines.append("| Run | Model | Effort | Fell back from | Report |")
    lines.append("|---|---|---|---|---|")
    for run_number in sorted(runs):
        run = runs[run_number]
        lines.append(
            f"| {run_number} | {run['model'] or '—'} | {run['effort'] or '—'} | "
            f"{run['fallback_from'] or 'no fallback'} | {run['report_path'].name} |")
    lines.append("")
    judging_models = {run["model"] for run in usable_runs.values() if run["model"]}
    fell_back = [number for number in sorted(usable_runs)
                 if usable_runs[number]["fallback_from"]]
    if fell_back:
        lines.append(
            "FABLE WAS UNAVAILABLE for "
            + ", ".join(f"run {number}" for number in fell_back)
            + ": the backup judged, and the report's provenance stamp names "
              "what it fell back from. This is the ruling's marked case, not "
              "a defect.")
        lines.append("")
    if len(judging_models) > 1:
        lines.append(
            "THE TWO RUNS WERE JUDGED BY DIFFERENT MODELS ("
            + ", ".join(sorted(judging_models))
            + "). Where they disagree below, the disagreement is between two "
              "judges as much as between two runs.")
        lines.append("")

    lines.append("## The cases judged")
    lines.append("")
    lines.append("| Case | Rough draft | Perfect version | Defect list | Restatement |")
    lines.append("|---|---|---|---|---|")
    for case_number, case_argument in enumerate(case_arguments, start=1):
        lines.append(f"| {case_number} | " + " | ".join(case_argument) + " |")
    lines.append("")

    lines.append("## Score")
    lines.append("")
    lines.append(
        "composite = 0.8 × caught − 0.2 × stupid, on the counts themselves. "
        "The ruling weights caught 80 percent and stupid 20 percent and does "
        "not say what either is divided by; this program divides by nothing "
        "and prints the raw counts beside every composite, which is the other "
        "half of the ruling. Comparable across restater classes only when the "
        "classes were judged on the same cases against the same defect lists.")
    lines.append("")
    lines.append("| Case | Run | Caught | Stupid | Composite |")
    lines.append("|---|---|---|---|---|")
    for case_number, _files in enumerate(cases, start=1):
        for run_number in sorted(usable_runs):
            row = usable_runs[run_number]["score"]["per_case"][case_number - 1]
            reported = "" if row["reported"] else " (no heading in this run's report)"
            lines.append(
                f"| {case_number} | {run_number} | {row['caught']} | "
                f"{row['stupid']} | {row['composite']:.2f}{reported} |")
    for run_number in sorted(usable_runs):
        score = usable_runs[run_number]["score"]
        lines.append(
            f"| **pooled** | {run_number} | {score['pooled_caught']} | "
            f"{score['pooled_stupid']} | {score['pooled_composite']:.2f} |")
    lines.append("")

    lines.append("## Where the runs disagree")
    lines.append("")
    if len(usable_runs) < 2:
        lines.append(
            "Only one run was scored, so there is nothing to compare. The "
            "marker at the top of this file says which run is missing and why.")
    else:
        first, second = sorted(usable_runs)
        disagreements = []
        for case_number, _files in enumerate(cases, start=1):
            first_row = usable_runs[first]["score"]["per_case"][case_number - 1]
            second_row = usable_runs[second]["score"]["per_case"][case_number - 1]
            only_first = set(first_row["caught_numbers"]) - set(second_row["caught_numbers"])
            only_second = set(second_row["caught_numbers"]) - set(first_row["caught_numbers"])
            if not only_first and not only_second \
                    and first_row["stupid"] == second_row["stupid"]:
                continue
            disagreements.append(
                f"- Case {case_number}: caught only in run {first}: "
                f"{format_defect_numbers(only_first)}; caught only in run "
                f"{second}: {format_defect_numbers(only_second)}; stupid "
                f"{first_row['stupid']} in run {first} against "
                f"{second_row['stupid']} in run {second}.")
        if disagreements:
            lines.extend(disagreements)
        else:
            lines.append(
                "The two runs agree on every case: the same defect numbers "
                "caught and the same number of stupid places.")
    lines.append("")

    lines.append("## Caught, by defect number")
    lines.append("")
    for case_number, _files in enumerate(cases, start=1):
        for run_number in sorted(usable_runs):
            row = usable_runs[run_number]["score"]["per_case"][case_number - 1]
            lines.append(
                f"- Case {case_number}, run {run_number}: "
                f"{format_defect_numbers(row['caught_numbers'])}")
    lines.append("")

    unnumbered = [
        (case_number, run_number, item)
        for run_number in sorted(usable_runs)
        for case_number, row in enumerate(
            usable_runs[run_number]["score"]["per_case"], start=1)
        for item in row["unnumbered_caught"]
    ]
    if unnumbered:
        lines.append("## Caught, but naming no defect number")
        lines.append("")
        lines.append(
            "Not counted: the ruling counts caught problems by defect number, "
            "and these lines name none, so which row they claim cannot be "
            "read. They are kept here as the judge wrote them.")
        lines.append("")
        for case_number, run_number, item in unnumbered:
            lines.append(f"- Case {case_number}, run {run_number}: {item}")
        lines.append("")

    lines.append("## Back to the scrub — problems caught that are on no defect list")
    lines.append("")
    lines.append(
        "NOT SCORED (user-ruled 2026-09-05). These go back to the scrub that "
        "built the defect lists; if the scrub accepts one it joins the list, "
        "and every hunter and restater is rescored against the longer list.")
    lines.append("")
    off_list = [
        (case_number, run_number, item)
        for run_number in sorted(usable_runs)
        for case_number, row in enumerate(
            usable_runs[run_number]["score"]["per_case"], start=1)
        for item in row["not_on_list"]
    ]
    if off_list:
        for case_number, run_number, item in off_list:
            lines.append(f"- Case {case_number}, run {run_number}: {item}")
    else:
        lines.append("Neither run reported a problem outside the defect lists.")
    lines.append("")

    stray_items = [
        (run_number, heading, item)
        for run_number in sorted(usable_runs)
        for heading, item in usable_runs[run_number]["parsed"]["items_outside_any_case"]
    ]
    headings_naming_no_case = [
        (run_number, heading)
        for run_number in sorted(usable_runs)
        for heading in usable_runs[run_number]["parsed"][
            "case_headings_naming_no_case_of_this_run"]
    ]
    if stray_items or headings_naming_no_case:
        lines.append("## Items the judge wrote under no case of this run")
        lines.append("")
        lines.append(
            "Not counted: which case each belongs to is exactly what is "
            "missing, and putting a number in a column it may not belong in "
            "is worse than leaving it out. Kept as the judge wrote them, with "
            "the heading each sat under. READ THE NOT-ON-LIST LINES HERE "
            "BESIDE THE SECTION ABOVE: an off-list problem is one the ruling "
            "sends back to the scrub whichever heading the judge filed it "
            "under.")
        lines.append("")
        for run_number, heading in headings_naming_no_case:
            lines.append(
                f"- Run {run_number}: `{heading}` names no case of this run, "
                f"which judged {len(cases)} case(s) numbered 1 to "
                f"{len(cases)}. Everything the judge wrote under it is below.")
        for run_number, heading, item in stray_items:
            under = f"under `{heading}`" if heading else "under no heading"
            lines.append(f"- Run {run_number}, {under}: {item}")
        lines.append("")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = build_runner_argument_parser()
    args = parser.parse_args()

    # Validate before spawning to report bad inputs once, without creating a record for two refused runs.
    try:
        judge_cell.validate_restater_class(args.restater)
        judge_cell.resolve_judge_prompt_file(args.prompt_file)
        cases = judge_cell.resolve_cases(args.case)
    except cell_common.CellRefusal as refusal:
        print(f"{PROGRAM}: {refusal}", file=sys.stderr)
        print(f"FAILED ({refusal})")
        return EXIT_BAD_INVOCATION

    if args.record_dir:
        record_dir = pathlib.Path(args.record_dir)
        if not record_dir.is_absolute():
            record_dir = REPO_ROOT / record_dir
        record_dir.mkdir(parents=True, exist_ok=True)
    else:
        record_dir = make_record_directory_for(
            args.restater, datetime.date.today().strftime("%Y-%m-%d"))

    print(f"{PROGRAM}: judging restater {args.restater} on {len(cases)} case(s), "
          f"{JUDGE_RUNS} runs, into {record_dir}", file=sys.stderr)
    exit_codes = wait_for_judge_runs(
        launch_judge_runs(
            args.restater, args.case, record_dir, args.prompt_file))

    runs = {
        run_number: read_run(
            judge_report_path(record_dir, run_number),
            exit_codes.get(run_number, 1), len(cases))
        for run_number in range(1, JUDGE_RUNS + 1)
    }
    unusable = [number for number in sorted(runs) if not runs[number]["usable"]]
    for run_number in unusable:
        print(f"{PROGRAM}: run {run_number} was not scored — "
              f"{runs[run_number]['why_unusable']}", file=sys.stderr)

    if len(unusable) == JUDGE_RUNS:
        print(f"FAILED (no judge run produced a report this program could "
              f"score; see {record_dir})")
        return 1

    combined_path = combined_result_path(record_dir)
    combined_path.write_text(
        render_combined_result(args.restater, cases, runs, args.case),
        encoding="utf-8")
    print(f"{PROGRAM}: combined result written to {combined_path}", file=sys.stderr)
    print(combined_path)
    return 1 if unusable else 0


if __name__ == "__main__":
    sys.exit(main())
