#!/usr/bin/env python3
"""Tests for cold-read-restater-judge-runner.py — the two runs, the counting,
the ruled composite, and every way a run can fail to be scored.

Driven end to end through the real judge cell with a stub `claude` first on
PATH, so no model is ever called and the seam under test is the whole path
from the launch of two runs to the combined result they are read into.

WHAT IS PINNED HERE.

  - TWO RUNS PER RESTATER (user-ruled 2026-09-07), launched into one record
    directory named for the restater and the day, their reports named for the
    run so the shared module's near-miss recovery cannot move one run's report
    under the other's stamp.

  - THE COMPOSITE'S ARITHMETIC, with its raw counts: 0.8 x caught - 0.2 x
    stupid, per case and pooled, computed by the runner from the judge's
    lines. A defect number named twice in one case is one caught defect, per
    the ruling's "by defect number". A case the judge wrote no heading for
    scores zero and says so, rather than passing as a judgment.

  - A CAUGHT PROBLEM THAT IS ON NO DEFECT LIST IS SET ASIDE, not scored: it
    goes to a section of its own addressed to the scrub, and the caught count
    beside it does not move. A CAUGHT line naming no defect number is set
    aside the same way, for the same reason: the ruling counts by number.

  - THE TWO RUNS SHOWN SEPARATELY, one row each per case and pooled, with the
    defect numbers one run caught and the other missed named where they
    differ, and stated as agreement where they do not.

  - FABLE UNAVAILABLE, MARKED IN THE RECORD: a run whose Fable failed is
    shown in the combined result as judged by Opus at max, with what it fell
    back from, a line saying Fable was unavailable, and -- because the other
    run was judged by Fable -- a line saying the two runs are two judges.

  - THE FAILURE PATHS. One run producing no report still yields a combined
    result, marked PARTIAL at the top and exiting 1, because the run that
    landed cost an xhigh judgment and is evidence. Both failing yields no
    combined result and a FAILED line. A report with no `## CASE` heading is
    a failed run, not a restater that caught nothing. A bad invocation is
    refused before anything is launched.

Run: python3 scripts/cold-read-restater-judge-runner-test.py
"""

import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
SCRIPT_NAMES = (
    "cold-read-cell-common.py",
    "cold-read-claude-cell.py",
    "cold-read-restater-judge-cell.py",
    "cold-read-restater-judge-runner.py",
)

RESTATER_CLASS = "gemini-3.8-flash-low"
CASE_FILE_CONTENTS = {
    "test-cases/draft-one.md": "# Draft one\n\nA sentence the perfect version fixes.\n",
    "test-cases/perfect-one.md": "# Perfect one\n\nA sentence, fixed.\n",
    "test-cases/defects-one.md": "| 1 | the sentence | why it is wrong |\n",
    "test-cases/restatement-one.md": "1. The sentence seems to mean two things.\n",
    "test-cases/draft-two.md": "# Draft two\n\nAnother rough sentence.\n",
    "test-cases/perfect-two.md": "# Perfect two\n\nAnother sentence, fixed.\n",
    "test-cases/defects-two.md": "| 1 | another sentence | why it is wrong |\n",
    "test-cases/restatement-two.md": "1. I could not tell what this meant.\n",
    "test-cases/draft-three.md": "# Draft three\n\nA third rough sentence.\n",
    "test-cases/perfect-three.md": "# Perfect three\n\nA third sentence, fixed.\n",
    "test-cases/defects-three.md": "| 1 | a third sentence | why it is wrong |\n",
    "test-cases/restatement-three.md": "1. A restatement of the third.\n",
}
THREE_CASES = (
    ("test-cases/draft-one.md", "test-cases/perfect-one.md",
     "test-cases/defects-one.md", "test-cases/restatement-one.md"),
    ("test-cases/draft-two.md", "test-cases/perfect-two.md",
     "test-cases/defects-two.md", "test-cases/restatement-two.md"),
    ("test-cases/draft-three.md", "test-cases/perfect-three.md",
     "test-cases/defects-three.md", "test-cases/restatement-three.md"),
)

# One judge report, written as the judge's prompt asks for it. Case 1 names
# defect 4 twice, which is one caught defect; case 2 carries a CAUGHT line
# with no number in it; case 3 has no heading at all. Counts that follow:
# case 1 caught 3 stupid 2, case 2 caught 1 stupid 0, case 3 nothing.
RUN_REPORT_BASE = """\
## CASE 1

CAUGHT: 1 — the restatement gave both readings of the sentence.
CAUGHT: 4 — it said the term defeated it.
CAUGHT: 4 — the same defect again, named twice in one case.
CAUGHT: 7 — it marked the gap the list names.
STUPID: "A sentence the perfect version keeps." — read as its opposite.
STUPID: "Another kept sentence." — invented a rule the draft never states.
NOT-ON-LIST: the section numbering skips 3, which no row of the list names.

## CASE 2

CAUGHT: 2 — it reported the sentence as two readings.
CAUGHT: the sentence about queues — a catch naming no defect number.
"""

# The second run, agreeing with the first on every case: the same defect
# numbers and the same number of stupid places, worded differently.
RUN_REPORT_AGREEING = """\
## CASE 1

CAUGHT: 1 — two readings given.
CAUGHT: 7 — the gap is marked.
CAUGHT: 4 — the undefined term is reported.
STUPID: "A sentence the perfect version keeps." — misread.
STUPID: "Another kept sentence." — misread.

## CASE 2

CAUGHT: 2 — the gap is reported.
NOT-ON-LIST: the draft's title contradicts its first line; no row names it.
"""

# The second run, disagreeing: it misses 4 and 7 on case 1, catches 9 there
# instead, and reports three stupid places rather than two.
RUN_REPORT_DISAGREEING = """\
## CASE 1

CAUGHT: 1 — two readings given.
CAUGHT: 9 — a defect the first run did not report.
STUPID: "A sentence the perfect version keeps." — misread.
STUPID: "Another kept sentence." — misread.
STUPID: "A third kept sentence." — misread.

## CASE 2

CAUGHT: 2 — the gap is reported.
"""

# A report the runner cannot place: judge text with no case heading in it.
RUN_REPORT_UNPARSEABLE = (
    "The restatements were generally good and caught most of the problems.\n")

# A stand-in for the `claude` CLI. It finds the report path in the prompt by
# the runner's own naming rule -- `...--claude-restater-judge-run<N>.md` --
# which is what makes one stub serve two runs at once; the plan is then keyed
# by that run token and by model, so a run can be made to fall back or fail
# independently of the other.
STUB_CLAUDE = """#!/usr/bin/env python3
import json, os, pathlib, re, sys
argv = sys.argv
model = argv[argv.index("--model") + 1] if "--model" in argv else "*"
prompt = sys.stdin.read()
match = re.search(r"\\S+--claude-restater-judge-run(\\d+)\\.md", prompt)
if match is None:
    sys.stderr.write("stub claude: no report path in the prompt\\n")
    sys.exit(3)
report_path = pathlib.Path(match.group(0))
run_token = "run" + match.group(1)
plan = json.loads(os.environ["COLD_READ_RESTATER_JUDGE_RUNNER_TEST_STUB_PLAN"])
for_run = plan.get(run_token, {})
step = for_run.get(model, for_run.get("*", {}))
if "report" in step:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(step["report"], encoding="utf-8")
if "stdout" in step:
    sys.stdout.write(step["stdout"])
sys.exit(step.get("exit", 0))
"""

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def git(repository, *arguments):
    completed = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        capture_output=True, text=True, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(arguments)}: {completed.stderr.strip()}")
    return completed.stdout


def build_scratch_repository(scratch):
    repository = scratch / "scratch-checkout"
    if repository.exists():
        shutil.rmtree(repository)
    (repository / "scripts").mkdir(parents=True)
    for script_name in SCRIPT_NAMES:
        shutil.copy2(SCRIPTS_DIR / script_name, repository / "scripts" / script_name)
    (repository / ".gitignore").write_text("cold-read-records/\n", encoding="utf-8")
    for relative_path, text in CASE_FILE_CONTENTS.items():
        path = repository / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    git(repository, "init", "-b", "main")
    git(repository, "config", "user.email", "test@test.invalid")
    git(repository, "config", "user.name", "cold-read-restater-judge-runner test")
    git(repository, "add", "-A")
    git(repository, "commit", "-m", "seed")
    return repository


def run_runner(repository, stub_directory, plan, *arguments,
               cases=THREE_CASES, restater=RESTATER_CLASS):
    stub_directory.mkdir(parents=True, exist_ok=True)
    stub = stub_directory / "claude"
    stub.write_text(STUB_CLAUDE, encoding="utf-8")
    stub.chmod(0o755)
    environment = dict(os.environ)
    environment["PATH"] = f"{stub_directory}{os.pathsep}{environment.get('PATH', '')}"
    environment["COLD_READ_RESTATER_JUDGE_RUNNER_TEST_STUB_PLAN"] = json.dumps(plan)
    command = [
        sys.executable,
        str(repository / "scripts" / "cold-read-restater-judge-runner.py"),
        "--restater", restater,
    ]
    for case in cases:
        command += ["--case", *case]
    command += list(arguments)
    return subprocess.run(
        command, capture_output=True, text=True, check=False, env=environment)


def expected_record_directory(repository, restater=RESTATER_CLASS):
    today = datetime.date.today().strftime("%Y-%m-%d")
    return repository / "cold-read-records" / f"{today}-restater-judge-{restater}"


with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch).resolve()  # macOS: /var is a link to /private/var, and the scripts resolve
    stubs = scratch / "stub-bin"

    # --- Two runs that agree: the record, the counts, the composite -------
    repository = build_scratch_repository(scratch)
    result = run_runner(
        repository, stubs,
        {"run1": {"*": {"report": RUN_REPORT_BASE}},
         "run2": {"*": {"report": RUN_REPORT_AGREEING}}},
    )
    record_dir = expected_record_directory(repository)
    combined_path = record_dir / f"{record_dir.name}--restater-judge-combined.md"
    check("two judge runs that both land exit 0",
          result.returncode == 0, f"exit {result.returncode}; stderr={result.stderr[-2000:]!r}")
    check("the combined result's path is the one line on stdout",
          result.stdout.strip() == str(combined_path), repr(result.stdout))
    check("both runs' reports are in the restater's record directory, named for the run",
          (record_dir / f"{record_dir.name}--claude-restater-judge-run1.md").is_file()
          and (record_dir / f"{record_dir.name}--claude-restater-judge-run2.md").is_file(),
          f"{sorted(path.name for path in record_dir.iterdir())}")
    run1_text = (record_dir / f"{record_dir.name}--claude-restater-judge-run1.md"
                 ).read_text(encoding="utf-8")
    check("each run's report carries the judge's provenance stamp",
          run1_text.startswith("<!-- provenance: runtime=claude "
                               "model=claude-fable-5-1 effort=xhigh "
                               "cell=restater-judge tier=judge "),
          repr(run1_text[:160]))
    combined = combined_path.read_text(encoding="utf-8")
    check("the combined result is not marked partial when both runs landed",
          "<!-- PARTIAL RESULT:" not in combined, repr(combined[:200]))
    # Case 1: caught 1, 4, 7 (4 named twice is one) and two stupid places, so
    # 0.8 x 3 - 0.2 x 2 = 2.00. Case 2: one caught, none stupid, 0.80. Case 3:
    # no heading in either report, so 0.00 and said so. Pooled: 4 caught, 2
    # stupid, 0.8 x 4 - 0.2 x 2 = 2.80.
    check("case 1 counts a defect named twice once, and scores 0.8 x 3 - 0.2 x 2",
          "| 1 | 1 | 3 | 2 | 2.00 |" in combined, repr(combined))
    check("case 2 scores 0.8 x 1 - 0.2 x 0",
          "| 2 | 1 | 1 | 0 | 0.80 |" in combined, repr(combined))
    check("a case the judge wrote no heading for scores zero and says so",
          "| 3 | 1 | 0 | 0 | 0.00 (no heading in this run's report) |" in combined,
          repr(combined))
    check("the pooled row is the pooled counts, weighted 80/20",
          "| **pooled** | 1 | 4 | 2 | 2.80 |" in combined
          and "| **pooled** | 2 | 4 | 2 | 2.80 |" in combined, repr(combined))
    check("the caught defect numbers are named per case and per run",
          "- Case 1, run 1: 1, 4, 7" in combined
          and "- Case 1, run 2: 1, 4, 7" in combined, repr(combined))
    check("two runs that caught the same numbers are reported as agreeing",
          "The two runs agree on every case" in combined, repr(combined))
    check("a caught problem that is on no defect list is set aside for the scrub, "
          "not counted",
          "the section numbering skips 3, which no row of the list names" in combined
          and "Back to the scrub" in combined
          and "| 1 | 1 | 3 | 2 | 2.00 |" in combined, repr(combined))
    check("a caught line naming no defect number is set aside the same way",
          "Caught, but naming no defect number" in combined
          and "the sentence about queues" in combined, repr(combined))
    check("the composite's rule is stated beside the numbers",
          "composite = 0.8 × caught − 0.2 × stupid" in combined, repr(combined[:4000]))

    # --- Two runs that disagree: both shown, and the difference named -----
    repository = build_scratch_repository(scratch)
    result = run_runner(
        repository, stubs,
        {"run1": {"*": {"report": RUN_REPORT_BASE}},
         "run2": {"*": {"report": RUN_REPORT_DISAGREEING}}},
    )
    record_dir = expected_record_directory(repository)
    combined = (record_dir / f"{record_dir.name}--restater-judge-combined.md"
                ).read_text(encoding="utf-8")
    check("two runs that disagree still exit 0 — a disagreement is a result",
          result.returncode == 0, f"exit {result.returncode}; stderr={result.stderr[-2000:]!r}")
    check("each run keeps its own row in the score table",
          "| 1 | 1 | 3 | 2 | 2.00 |" in combined
          and "| 1 | 2 | 2 | 3 | 1.00 |" in combined, repr(combined))
    check("the disagreement names the numbers each run caught alone, and the "
          "stupid counts",
          "- Case 1: caught only in run 1: 4, 7; caught only in run 2: 9; "
          "stupid 2 in run 1 against 3 in run 2." in combined, repr(combined))
    check("a case the two runs agree on is not reported as a disagreement",
          "Case 2: caught only in run" not in combined, repr(combined))

    # --- Fable unavailable in one run: Opus judges, and the record says so -
    repository = build_scratch_repository(scratch)
    result = run_runner(
        repository, stubs,
        {"run1": {"claude-fable-5-1": {"exit": 1},
                  "claude-opus-5": {"report": RUN_REPORT_BASE}},
         "run2": {"*": {"report": RUN_REPORT_AGREEING}}},
    )
    record_dir = expected_record_directory(repository)
    combined = (record_dir / f"{record_dir.name}--restater-judge-combined.md"
                ).read_text(encoding="utf-8")
    check("a run whose Fable failed is still scored, and the pair exits 0",
          result.returncode == 0 and "| 1 | 1 | 3 | 2 | 2.00 |" in combined,
          f"exit {result.returncode}; stderr={result.stderr[-2000:]!r}")
    check("the combined result names the model that judged each run",
          "| 1 | claude-opus-5 | max | claude-fable-5-1(exit1) |" in combined
          and "| 2 | claude-fable-5-1 | xhigh | no fallback |" in combined,
          repr(combined))
    check("the combined result says Fable was unavailable for that run",
          "FABLE WAS UNAVAILABLE for run 1" in combined, repr(combined))
    check("it warns that the two runs were judged by different models",
          "THE TWO RUNS WERE JUDGED BY DIFFERENT MODELS" in combined, repr(combined))
    check("the fallback is lifted onto the runner's own stderr, not left in a log",
          any(line.startswith("cold-read-restater-judge-runner: run 1 FELL BACK: "
                              "cold-read-restater-judge-cell: fell back to "
                              "claude-opus-5")
              for line in result.stderr.splitlines()),
          repr(result.stderr[-3000:]))

    # --- One run produces no report at all ---------------------------------
    repository = build_scratch_repository(scratch)
    result = run_runner(
        repository, stubs,
        {"run1": {"*": {"exit": 1}},
         "run2": {"*": {"report": RUN_REPORT_AGREEING}}},
    )
    record_dir = expected_record_directory(repository)
    combined_path = record_dir / f"{record_dir.name}--restater-judge-combined.md"
    combined = combined_path.read_text(encoding="utf-8")
    check("one run failing exits 1 and still writes the combined result",
          result.returncode == 1 and combined_path.is_file(),
          f"exit {result.returncode}; stderr={result.stderr[-2000:]!r}")
    check("the combined result opens with the partial marker naming the missing run",
          combined.startswith("<!-- PARTIAL RESULT: run 1 was not scored — no report at"),
          repr(combined[:300]))
    check("the run that landed is scored, and it alone",
          "| 1 | 2 | 3 | 2 | 2.00 |" in combined
          and "| 1 | 1 | 3 | 2 | 2.00 |" not in combined, repr(combined))
    check("with one run there is nothing to compare, and it says so",
          "Only one run was scored, so there is nothing to compare." in combined,
          repr(combined))

    # --- A report with no case heading is a failed run, not a zero ---------
    repository = build_scratch_repository(scratch)
    result = run_runner(
        repository, stubs,
        {"run1": {"*": {"report": RUN_REPORT_UNPARSEABLE}},
         "run2": {"*": {"report": RUN_REPORT_AGREEING}}},
    )
    record_dir = expected_record_directory(repository)
    combined = (record_dir / f"{record_dir.name}--restater-judge-combined.md"
                ).read_text(encoding="utf-8")
    check("a report with no case heading makes the run unscored, and the pair exits 1",
          result.returncode == 1
          and "holds no `## CASE <number>` heading" in combined,
          f"exit {result.returncode}; combined={combined[:400]!r}")
    check("the unreadable run is not scored as a judge that caught nothing",
          "| 1 | 1 | 0 | 0 | 0.00 |" not in combined
          and "| **pooled** | 1 |" not in combined, repr(combined))
    check("the run that landed keeps its scores",
          "| **pooled** | 2 | 4 | 2 | 2.80 |" in combined, repr(combined))

    # --- Both runs fail ----------------------------------------------------
    repository = build_scratch_repository(scratch)
    result = run_runner(
        repository, stubs,
        {"run1": {"*": {"exit": 1}}, "run2": {"*": {"exit": 1}}},
    )
    record_dir = expected_record_directory(repository)
    combined_path = record_dir / f"{record_dir.name}--restater-judge-combined.md"
    check("both runs failing exits 1 and writes no combined result",
          result.returncode == 1 and not combined_path.exists(),
          f"exit {result.returncode}; stderr={result.stderr[-2000:]!r}")
    check("the failure is the one line on stdout, naming the record directory",
          result.stdout.startswith("FAILED (no judge run produced a report")
          and str(record_dir) in result.stdout, repr(result.stdout))

    # --- A bad invocation is refused before anything is launched -----------
    repository = build_scratch_repository(scratch)
    result = run_runner(
        repository, stubs, {"run1": {"*": {"report": RUN_REPORT_BASE}}},
        cases=(THREE_CASES[0],
               (THREE_CASES[1][0], "test-cases/perfect-two-that-is-not-there.md",
                THREE_CASES[1][2], THREE_CASES[1][3])),
    )
    check("a missing case file is refused with exit 64, naming case and role",
          result.returncode == 64
          and "case 2: perfect version not found:" in result.stderr
          and result.stdout.startswith("FAILED ("),
          f"exit {result.returncode}; stdout={result.stdout!r}; stderr={result.stderr!r}")
    check("a refused invocation creates no record directory",
          not expected_record_directory(repository).exists(),
          "the record directory was created before the invocation was checked")

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
