#!/usr/bin/env python3
"""Cases for nn-systems/cold-read/cold-read-fast-read-report-findings-parse-and-finding-outcomes-check-common.py:
which lines of a cold-read-fast-read report are findings and what id each gets; which --finding-outcome lists are
refused and why; the ready-made command's text; and whether a record's findings all have outcomes.

Run: python3 nn-systems/cold-read/tests/cold-read-fast-read-report-findings-parse-and-finding-outcomes-check-common-test.py
Prints one line per case and exits non-zero if any case fails.
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

MODULE_FILE = (Path(__file__).resolve().parents[1]
               / "cold-read-fast-read-report-findings-parse-and-finding-outcomes-check-common.py")
_spec = importlib.util.spec_from_file_location("finding_outcomes_common_under_test", MODULE_FILE)
module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(module)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def ids(findings):
    return [module.finding_id(finding.question, finding.number) for finding in findings]


REPORT = """\
<!-- provenance: runtime=agy -->
Files: docs/a.md

## Question 1: What it says

[s1]
> 1. A numbered sentence of the document, quoted under its restatement.
> ## Question 2: a heading of the document, quoted
- 1. a restatement bullet

## Question 2: Where you struggled

1. `"the rename freeze"`: undefined.
2) `"its kind"`: ambiguous.
   3. an indented line inside item 2, not a finding of its own

```
1. inside fenced code, not a finding
```

## Question 3: What it does not cover that it implies it should

No issues

## Question 4: What should be code

<!-- provenance: runtime=claude -->

### docs/a.md

1. "renames each of the 16" — a script can do it.

### docs/b.md

1. "the 16" — a hand count.
2. "after the freeze" — relies on memory.

## Sentence coverage (added by cold-read-fast-read)

1. not a finding: after the last question
"""

findings = module.cold_read_fast_read_report_findings(REPORT)
check("findings are the numbered lines under Questions 2 to 4, numbered in report order within each question, "
      "and a Question 4 that numbers each document from 1 still gives each finding its own id",
      ids(findings) == ["Q2.1", "Q2.2", "Q4.1", "Q4.2", "Q4.3"], ids(findings))
check("a finding keeps the opening of its first line, for the agent to tell findings apart",
      findings[0].opening == '`"the rename freeze"`: undefined.' and findings[3].opening.startswith('"the 16"'),
      findings[:1])
other_levels = module.cold_read_fast_read_report_findings(
    "# Files examined\n\n1. docs/a.md\n\n# Question 2: Where you struggled\n\n1. a\n\n"
    "## Document: docs/b.md\n\n### Question 1: What it says\n\n1. not a finding\n\n"
    "### Question 3: What it does not cover that it implies it should\n\n1. b\n\n"
    "## Question 4: What should be code\n\n### docs/b.md\n\n1. c\n")
check("a question headed with # or ###, as some reviewers write them, holds findings too, and a # or ## heading "
      "that is no question ends the question before it",
      ids(other_levels) == ["Q2.1", "Q3.1", "Q4.1"], ids(other_levels))
check("a report with no numbered item under a finding question has no findings",
      module.cold_read_fast_read_report_findings("## Question 2: Where you struggled\n\nNo issues\n") == [])

long_finding = [module.Finding(2, 1, "x" * 150)]
check("a finding's opening is cut to FINDING_OPENING_CHARACTERS_SHOWN characters in the list",
      module.finding_list_lines(long_finding) == ["  Q2.1: " + "x" * 97 + "..."],
      module.finding_list_lines(long_finding))

command = module.cold_read_fast_read_finding_outcomes_record_command(
    Path("/repo/nn-systems/cold-read/cold-read-fast-read.py"), Path("/repo/cold-read-records/a b-2026-11-19"),
    findings[:2])
check("the ready-made command names the program and the record, quoted for the shell, and gives each finding a "
      "single-quoted value holding the placeholder, one option to a line",
      command == ("python3 /repo/nn-systems/cold-read/cold-read-fast-read.py "
                  "--record-finding-outcomes-in-cold-read-record '/repo/cold-read-records/a b-2026-11-19' \\\n"
                  "  --finding-outcome 'Q2.1=<applied, or declined: reason>' \\\n"
                  "  --finding-outcome 'Q2.2=<applied, or declined: reason>'"), command)
filled = command.replace("'Q2.1=<applied, or declined: reason>'", "'Q2.1=applied'").replace(
    "'Q2.2=<applied, or declined: reason>'", "'Q2.2=declined: `true` and $HOME are kept as typed'")
echoed = subprocess.run(["bash", "-c", "printf '%s\\n' " + filled.split(" ", 2)[2]],
                        capture_output=True, text=True, check=False).stdout.splitlines()
check("filled in, the command reaches the program with each reason exactly as typed, backquote and $ included",
      echoed[-1] == "Q2.2=declined: `true` and $HOME are kept as typed", echoed)

outcomes = module.cold_read_fast_read_finding_outcomes_from_values(
    ["Q2.1=applied", " Q2.2 = declined:  already checked by a test ", "Q4.1=applied", "Q4.2=applied",
     "Q4.3=declined: out of scope"], findings)
check("a complete list gives each finding its outcome in report order, a declined one with its reason",
      outcomes[0] == {"finding": "Q2.1", "question": 2, "number": 1, "outcome": "applied"}
      and outcomes[1] == {"finding": "Q2.2", "question": 2, "number": 2, "outcome": "declined",
                          "reason": "already checked by a test"}
      and [entry["finding"] for entry in outcomes] == ids(findings), outcomes)


def refusal(values):
    try:
        module.cold_read_fast_read_finding_outcomes_from_values(values, findings)
    except module.FindingOutcomesRefused as refused:
        return refused.args[0]
    return None


everything_else = ["Q2.2=applied", "Q4.1=applied", "Q4.2=applied", "Q4.3=applied"]
problems = refusal(["Q2.1=applied", "Q4.1=applied"])
check("a list that leaves findings out is refused, naming each one left out",
      problems == ["No outcome is given for Q2.2, Q4.2, Q4.3."], problems)
problems = refusal(["Q2.1=applied", "Q3.1=applied"] + everything_else)
check("a value naming a finding the report does not have is refused, naming it",
      problems == ["`Q3.1=applied` names Q3.1, which is no finding of the report."], problems)
problems = refusal(["Q2.1=applied", "Q2.1=declined: second thoughts"] + everything_else)
check("a finding given twice is refused", problems == [
    "`Q2.1=declined: second thoughts` gives Q2.1 an outcome a second time."], problems)
problems = refusal(["Q2.1=<applied, or declined: reason>"] + everything_else)
check("a value still holding the placeholder is refused, and its finding counts as left out",
      problems is not None and len(problems) == 2 and "neither `applied` nor `declined: <reason>`" in problems[0]
      and problems[1] == "No outcome is given for Q2.1.", problems)
problems = refusal(["Q2.1=declined:"] + everything_else)
check("a decline without a reason is refused", problems is not None and "neither" in problems[0], problems)
problems = refusal(["2.1=applied"] + everything_else)
check("a value not written Q<question>.<number>=<outcome> is refused",
      problems is not None and "is not written Q<question>.<number>=<outcome>" in problems[0], problems)

with tempfile.TemporaryDirectory() as scratch:
    record = Path(scratch) / "a-2026-11-19"
    record.mkdir()
    (record / "cold-read-fast-read.md").write_text(REPORT, encoding="utf-8")
    check("a record whose report has findings and no outcomes file lacks every finding's outcome",
          ids(module.cold_read_fast_read_findings_without_outcomes(record)) == ids(findings))
    text = module.finding_outcomes_file_text(REPORT.encode(), outcomes, "2026-11-19T10:00:00+00:00")
    module.finding_outcomes_file_path(record).write_text(text, encoding="utf-8")
    written = json.loads(text)
    check("the outcomes file names the report, holds its sha256, the time and each outcome",
          written["report"] == "cold-read-fast-read.md" and len(written["report_sha256"]) == 64
          and written["recorded_at"] == "2026-11-19T10:00:00+00:00" and written["findings"] == outcomes, written)
    check("a record whose outcomes file gives every finding its outcome lacks none",
          module.cold_read_fast_read_findings_without_outcomes(record) == [])
    module.finding_outcomes_file_path(record).write_text('{"findings": [{"outcome": "maybe"}]}', encoding="utf-8")
    try:
        module.cold_read_fast_read_findings_without_outcomes(record)
        malformed = None
    except ValueError as error:
        malformed = str(error)
    check("an outcomes file that is not the JSON the program writes raises ValueError naming it",
          malformed is not None and "cold-read-fast-read-finding-outcomes.json" in malformed, malformed)
    (record / "cold-read-fast-read.md").write_text("## Question 2: Where you struggled\n\nNo issues\n")
    check("a record whose report has no findings needs no outcomes, whatever its outcomes file holds",
          module.cold_read_fast_read_findings_without_outcomes(record) == [])
    old_record = Path(scratch) / "old-2026-09-01"
    old_record.mkdir()
    (old_record / "fast-read.md").write_text("## Question 2: Where you struggled\n\n1. x\n", encoding="utf-8")
    check("a record from before the cold-read- prefix is read under its report's older name",
          ids(module.cold_read_fast_read_findings_without_outcomes(old_record)) == ["Q2.1"])

check("the outcomes file's name cannot be taken for a finished report",
      module.record_names.COMPLETED_REPORT_NAME_PATTERN.match(module.FINDING_OUTCOMES_FILE_NAME) is None)

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
