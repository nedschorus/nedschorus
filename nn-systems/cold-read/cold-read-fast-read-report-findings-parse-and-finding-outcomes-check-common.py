#!/usr/bin/env python3
"""Find the numbered findings of a cold-read-fast-read report, check an agent's outcome for each, and build the
ready-made command that records them.

A finding is a numbered item, a line opening `1.` or `1)` at the line's start, outside fenced code, under a
`## Question N` heading, or one headed with `#` or `###`, for a question that asks for findings: 2, Where you struggled; 3, What it does not
cover; and 4, What should be code. Question 1 restates the document and holds no findings. A finding's id is
`Q<question>.<number>`, as in `Q2.1`; the number counts the question's findings in the order the report gives
them, so a report that numbers each document's findings from 1 under one question, as a Question 4 answer
about several documents does, still gives every finding an id of its own.

cold-read-fast-read.py prints the ready-made command after each read whose report has findings, and runs it
with --record-finding-outcomes-in-cold-read-record; the walk-me-through check program prints the same command and
asks whether a record's outcomes are complete; the counting script reads the outcomes file each record holds.
"""
import collections
import hashlib
import importlib.util
import json
import pathlib
import re
import shlex

_record_names_spec = importlib.util.spec_from_file_location(
    "cold_read_record_names", pathlib.Path(__file__).with_name("cold-read-record-names-common.py"))
record_names = importlib.util.module_from_spec(_record_names_spec)
_record_names_spec.loader.exec_module(record_names)

FINDING_OUTCOMES_FILE_NAME = record_names.COLD_READ_FAST_READ_FINDING_OUTCOMES_FILE_NAME
FINDING_QUESTION_TITLES = {2: "Where you struggled", 3: "What it does not cover that it implies it should",
                           4: "What should be code"}
FINDING_QUESTION_NUMBERS = tuple(FINDING_QUESTION_TITLES)
FINDING_OUTCOMES_RECORD_OPTION = "--record-finding-outcomes-in-cold-read-record"
FINDING_OUTCOME_OPTION = "--finding-outcome"
APPLIED = "applied"
DECLINED = "declined"
FINDING_OUTCOME_PLACEHOLDER = "<applied, or declined: reason>"
FINDING_OPENING_CHARACTERS_SHOWN = 100

# A reviewer sometimes heads Questions 1 to 3 with `#`, or with `###` under a `##` heading naming the document; any
# other `###` heading stays inside its question, as a document's name under Question 4 does.
QUESTION_HEADING = re.compile(r"^#{1,3}\s+Question\s+(\d+)\b")
FIRST_OR_SECOND_LEVEL_HEADING = re.compile(r"^#{1,2}\s")
NUMBERED_ITEM = re.compile(r"^\d+[.)]\s+(\S.*)$")
CODE_FENCE = re.compile(r"^\s*(```|~~~)")
FINDING_OUTCOME_VALUE = re.compile(r"^\s*Q(\d+)\.(\d+)\s*=\s*(.*?)\s*$", re.DOTALL)
DECLINED_WITH_REASON = re.compile(DECLINED + r"\s*:\s*(\S.*)$", re.DOTALL)

Finding = collections.namedtuple("Finding", "question number opening")


def finding_id(question, number):
    return f"Q{question}.{number}"


def cold_read_fast_read_report_findings(report_text):
    """Every finding of the report, in report order, each with the opening of its first line."""
    findings = []
    counts = collections.Counter()
    question, fenced = None, False
    for line in report_text.split("\n"):
        if CODE_FENCE.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        heading = QUESTION_HEADING.match(line)
        if heading:
            question = int(heading.group(1))
            continue
        if FIRST_OR_SECOND_LEVEL_HEADING.match(line):
            question = None
            continue
        item = NUMBERED_ITEM.match(line)
        if item and question in FINDING_QUESTION_NUMBERS:
            counts[question] += 1
            findings.append(Finding(question, counts[question], item.group(1)))
    return findings


def cold_read_fast_read_record_report_path(record_dir):
    return record_names.cold_read_record_file_path_prefixed_name_else_name_before_prefix(
        pathlib.Path(record_dir), record_names.COLD_READ_FAST_READ_REPORT_FILE_NAME)


def cold_read_fast_read_record_findings(record_dir):
    """The findings of the fast read report record_dir holds; OSError when it holds none that can be read."""
    return cold_read_fast_read_report_findings(
        cold_read_fast_read_record_report_path(record_dir).read_text(encoding="utf-8"))


def finding_outcomes_file_path(record_dir):
    return pathlib.Path(record_dir) / FINDING_OUTCOMES_FILE_NAME


def finding_list_lines(findings):
    """One line per finding: its id and the opening of its text, so the agent can tell which finding is which."""
    lines = []
    for finding in findings:
        opening = finding.opening
        if len(opening) > FINDING_OPENING_CHARACTERS_SHOWN:
            opening = opening[:FINDING_OPENING_CHARACTERS_SHOWN - 3].rstrip() + "..."
        lines.append(f"  {finding_id(finding.question, finding.number)}: {opening}")
    return lines


def cold_read_fast_read_finding_outcomes_record_command(fast_read_program, record_dir, findings):
    """The command, one option to a line, that records an outcome for every finding once each placeholder is
    replaced. Each value is in single quotes, so a backquote or a $ in a reason is not run by the shell."""
    lines = [f"python3 {shlex.quote(str(fast_read_program))} {FINDING_OUTCOMES_RECORD_OPTION} "
             f"{shlex.quote(str(record_dir))}"]
    lines += [f"  {FINDING_OUTCOME_OPTION} '{finding_id(finding.question, finding.number)}="
              f"{FINDING_OUTCOME_PLACEHOLDER}'" for finding in findings]
    return " \\\n".join(lines)


class FindingOutcomesRefused(Exception):
    """The outcome list is wrong; its argument is the list of problems, one line each."""


def cold_read_fast_read_finding_outcomes_from_values(values, findings):
    """The outcome of every finding, in report order, from the --finding-outcome values; raise
    FindingOutcomesRefused naming every problem when a value is malformed, names no finding of the report or a
    finding given before, or when a finding has no value."""
    known = {finding_id(finding.question, finding.number) for finding in findings}
    given, problems = {}, []
    for value in values:
        parsed = FINDING_OUTCOME_VALUE.match(value)
        if parsed is None:
            problems.append(f"`{value}` is not written Q<question>.<number>=<outcome>, as in `Q2.1={APPLIED}`.")
            continue
        name = finding_id(int(parsed.group(1)), int(parsed.group(2)))
        outcome_text = parsed.group(3)
        declined = DECLINED_WITH_REASON.match(outcome_text)
        if outcome_text == APPLIED:
            outcome = {"outcome": APPLIED}
        elif declined:
            outcome = {"outcome": DECLINED, "reason": declined.group(1)}
        else:
            problems.append(f"`{value}` gives {name} the outcome `{outcome_text}`, which is neither `{APPLIED}` "
                            f"nor `{DECLINED}: <reason>` with a reason after the colon.")
            continue
        if name not in known:
            problems.append(f"`{value}` names {name}, which is no finding of the report.")
        elif name in given:
            problems.append(f"`{value}` gives {name} an outcome a second time.")
        else:
            given[name] = outcome
    missing = [name for name in (finding_id(f.question, f.number) for f in findings) if name not in given]
    if missing:
        problems.append(f"No outcome is given for {', '.join(missing)}.")
    if problems:
        raise FindingOutcomesRefused(problems)
    return [dict(finding=finding_id(finding.question, finding.number), question=finding.question,
                 number=finding.number, **given[finding_id(finding.question, finding.number)])
            for finding in findings]


def finding_outcomes_file_text(report_bytes, outcomes, recorded_at):
    """The outcomes file's JSON: the report's sha256, when the outcomes were recorded, and each finding's
    outcome, so a reader needs neither the report nor this module to count them."""
    return json.dumps({"report": record_names.COLD_READ_FAST_READ_REPORT_FILE_NAME,
                       "report_sha256": hashlib.sha256(report_bytes).hexdigest(),
                       "recorded_at": recorded_at, "findings": outcomes},
                      ensure_ascii=False, indent=1) + "\n"


def finding_outcomes_read(record_dir):
    """The outcomes file's findings list, or None when record_dir holds no outcomes file. ValueError when the file
    is not the JSON finding_outcomes_file_text writes."""
    path = finding_outcomes_file_path(record_dir)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    try:
        recorded = json.loads(text)
    except ValueError:
        recorded = None
    if not isinstance(recorded, dict) or not isinstance(recorded.get("findings"), list) or not all(
            isinstance(entry, dict) and entry.get("outcome") in (APPLIED, DECLINED)
            and isinstance(entry.get("question"), int) for entry in recorded["findings"]):
        raise ValueError(f"{path} is not the finding outcomes file cold-read-fast-read.py writes")
    return recorded["findings"]


def cold_read_fast_read_findings_without_outcomes(record_dir):
    """The findings of record_dir's fast read report that its outcomes file gives no outcome; empty when the
    report has no findings or every finding has its outcome. OSError when the report cannot be read, ValueError
    when the outcomes file is malformed."""
    findings = cold_read_fast_read_record_findings(record_dir)
    if not findings:
        return []
    recorded = finding_outcomes_read(record_dir) or []
    have = {entry.get("finding") for entry in recorded}
    return [finding for finding in findings if finding_id(finding.question, finding.number) not in have]
