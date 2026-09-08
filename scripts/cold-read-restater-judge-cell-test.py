#!/usr/bin/env python3
"""Tests for cold-read-restater-judge-cell.py — the ruled judge's pins, its
fallback, and its refusals, driven through a stub `claude` so no model is
ever called.

WHAT IS PINNED HERE.

  - The ruled chain and its two efforts (user-ruled 2026-09-07, "Opus max is
    the backup to Fable"): Fable 5.1 judges at xhigh, and the stamp says so,
    with runtime=claude, cell=restater-judge, tier=judge.

  - THE FALLBACK AND ITS MARK IN THE RECORD, which is the whole reason this
    cell has a chain at all. Both ways the ruling names Fable unavailable are
    driven: a Fable that exits non-zero (the account limit) and a Fable that
    exits 0 having written nothing (a safeguard refusal that returned no
    report). Either way Opus 5 judges AT MAX -- not at Fable's xhigh, which
    is the seam this cell added to the shared module -- the stamp carries
    `fallback_from=claude-fable-5-1(...)`, and the cell says on stderr that
    it fell back, in the words the runner and the grid lift out of a log.

  - The invocation is the Claude leg's own, because the judge imports that
    launcher rather than repeating it: `claude -p --model --effort
    --output-format text --allowedTools Read,Grep,Glob,Write`, with the
    prompt on stdin.

  - The prompt the judge receives: every one of a case's four paths, in the
    order --case takes them, under the words that name their roles; the
    restater class; the report path; and no placeholder left unfilled.

  - The refusals, all of which exit 64 without launching a model: a case file
    that is not there (named by case number and role), a --restater that
    cannot name a class, and a --model this cell pins no effort for unless
    --effort names one.

Each case builds a throwaway git repository holding a copy of the cell
scripts, as scripts/cold-read-agy-cell-test.py does, and runs the launcher
inside it with the stub first on PATH. The stub is driven by
COLD_READ_RESTATER_JUDGE_CELL_TEST_STUB_PLAN, a JSON map from model id to
what that attempt should do.

Run: python3 scripts/cold-read-restater-judge-cell-test.py
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
CELL_SCRIPT_NAMES = (
    "cold-read-cell-common.py",
    "cold-read-claude-cell.py",
    "cold-read-restater-judge-cell.py",
)

# The phrase the shared module prints when a chain falls back, spelled out
# here rather than imported so a reworded line fails here rather than passing
# however either side was reworded.
FELL_BACK_PHRASE = "fell back to"

# One trio of cases, as the campaign will pass them: four files each, in the
# order --case takes them. Committed into the scratch repository, so a run
# that leaves the tree dirty is the run's own doing.
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
RESTATER_CLASS = "gemini-3.8-flash-low"

STUB_JUDGE_REPORT = "## CASE 1\n\nCAUGHT: 1 — the restatement gave two readings.\n"

# A stand-in for the `claude` CLI. It reads the model from --model and the
# prompt from stdin, then does what the plan says for that model: "report" is
# text to write to the report path (absent means write nothing), "dump_argv"
# and "dump_prompt" are paths to record what the stub was launched with, and
# "exit" is the code to exit with. The report path arrives by environment, as
# in the other cell tests, so a reworded template cannot unhook the stub.
STUB_CLAUDE = """#!/usr/bin/env python3
import json, os, pathlib, sys
argv = sys.argv
model = argv[argv.index("--model") + 1] if "--model" in argv else "*"
prompt = sys.stdin.read()
plan = json.loads(os.environ["COLD_READ_RESTATER_JUDGE_CELL_TEST_STUB_PLAN"])
step = plan.get(model, plan.get("*", {}))
report_path = pathlib.Path(
    os.environ["COLD_READ_RESTATER_JUDGE_CELL_TEST_STUB_REPORT_PATH"])
if "dump_argv" in step:
    pathlib.Path(step["dump_argv"]).write_text(json.dumps(argv), encoding="utf-8")
if "dump_prompt" in step:
    pathlib.Path(step["dump_prompt"]).write_text(prompt, encoding="utf-8")
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
    """A git repository the cell scripts believe they live in: the cell
    derives its repository root from its own path, so a copy is the seam."""
    repository = scratch / "scratch-checkout"
    if repository.exists():
        shutil.rmtree(repository)
    (repository / "scripts").mkdir(parents=True)
    for script_name in CELL_SCRIPT_NAMES:
        shutil.copy2(SCRIPTS_DIR / script_name, repository / "scripts" / script_name)
    (repository / ".gitignore").write_text("cold-read-records/\n", encoding="utf-8")
    for relative_path, text in CASE_FILE_CONTENTS.items():
        path = repository / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    git(repository, "init", "-b", "main")
    git(repository, "config", "user.email", "test@test.invalid")
    git(repository, "config", "user.name", "cold-read-restater-judge-cell test")
    git(repository, "add", "-A")
    git(repository, "commit", "-m", "seed")
    return repository


def report_path_for(repository, case_slug, run_number=1):
    record_directory_name = f"2026-09-07-restater-judge-{case_slug}"
    return (repository / "cold-read-records" / record_directory_name
            / f"{record_directory_name}--claude-restater-judge-run{run_number}.md")


def run_judge_cell(repository, stub_directory, plan, report_path, *arguments,
                   cases=THREE_CASES, restater=RESTATER_CLASS):
    stub_directory.mkdir(parents=True, exist_ok=True)
    stub = stub_directory / "claude"
    stub.write_text(STUB_CLAUDE, encoding="utf-8")
    stub.chmod(0o755)
    environment = dict(os.environ)
    environment["PATH"] = f"{stub_directory}{os.pathsep}{environment.get('PATH', '')}"
    environment["COLD_READ_RESTATER_JUDGE_CELL_TEST_STUB_PLAN"] = json.dumps(plan)
    environment["COLD_READ_RESTATER_JUDGE_CELL_TEST_STUB_REPORT_PATH"] = str(report_path)
    command = [
        sys.executable,
        str(repository / "scripts" / "cold-read-restater-judge-cell.py"),
        "--restater", restater, "--report", str(report_path),
    ]
    for case in cases:
        command += ["--case", *case]
    command += list(arguments)
    return subprocess.run(
        command, capture_output=True, text=True, check=False, env=environment)


def provenance_stamp_of(report):
    if not report.is_file():
        return ""
    return report.read_text(encoding="utf-8").splitlines()[0]


with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch).resolve()  # macOS: /var is a link to /private/var, and the scripts resolve
    stubs = scratch / "stub-bin"

    # --- The ruled pin, the invocation, and the prompt --------------------
    repository = build_scratch_repository(scratch)
    report = report_path_for(repository, "pin")
    argv_dump = scratch / "pin-argv.json"
    prompt_dump = scratch / "pin-prompt.txt"
    result = run_judge_cell(
        repository, stubs,
        {"*": {"report": STUB_JUDGE_REPORT, "dump_argv": str(argv_dump),
               "dump_prompt": str(prompt_dump)}},
        report,
    )
    check("a judge cell whose Fable writes the report exits 0",
          result.returncode == 0, f"exit {result.returncode}; stderr={result.stderr!r}")
    stamp = provenance_stamp_of(report)
    check("the judge is pinned to claude-fable-5-1 at xhigh, stamped restater-judge/judge",
          stamp.startswith("<!-- provenance: runtime=claude model=claude-fable-5-1 "
                           "effort=xhigh cell=restater-judge tier=judge "),
          repr(stamp))
    check("the stamp carries duration_s and no tokens field",
          re.search(r"\bduration_s=\d+\b", stamp) is not None and "tokens=" not in stamp,
          repr(stamp))
    check("the stamp's target is the restatements this run judged",
          " target=test-cases/restatement-one.md,test-cases/restatement-two.md,"
          "test-cases/restatement-three.md " in stamp + " ",
          repr(stamp))
    check("the successful cell prints nothing to stdout",
          result.stdout == "", repr(result.stdout[:200]))
    argv = json.loads(argv_dump.read_text(encoding="utf-8")) if argv_dump.is_file() else []
    check("the invocation is the Claude leg's own, at the judge's effort",
          # argv[0] is the stub's own path, which is how PATH resolution
          # hands it over; its basename is the binary the cell asked for.
          Path(argv[0]).name == "claude" and argv[1] == "-p"
          and argv[argv.index("--model") + 1] == "claude-fable-5-1"
          and argv[argv.index("--effort") + 1] == "xhigh"
          and argv[argv.index("--output-format") + 1] == "text"
          and argv[argv.index("--allowedTools") + 1] == "Read,Grep,Glob,Write",
          repr(argv))
    prompt = prompt_dump.read_text(encoding="utf-8") if prompt_dump.is_file() else ""
    check("the prompt names the restater class and the report path",
          RESTATER_CLASS in prompt and str(report) in prompt, repr(prompt[:200]))
    check("the prompt carries all twelve case paths, numbered in the order given",
          all(str(repository / relative_path) in prompt
              for case in THREE_CASES for relative_path in case)
          and "Case 1:" in prompt and "Case 2:" in prompt and "Case 3:" in prompt,
          repr(prompt[-800:]))
    check("each case's four paths are introduced by their roles, in order",
          prompt.index(str(repository / "test-cases/draft-one.md"))
          < prompt.index(str(repository / "test-cases/perfect-one.md"))
          < prompt.index(str(repository / "test-cases/defects-one.md"))
          < prompt.index(str(repository / "test-cases/restatement-one.md"))
          < prompt.index(str(repository / "test-cases/draft-two.md")),
          repr(prompt[-800:]))
    check("no placeholder is left unfilled in the prompt",
          "{RESTATER_CLASS}" not in prompt and "{CASES_BLOCK}" not in prompt
          and "{REPORT_PATH}" not in prompt, repr(prompt[:200]))

    # --- Fable unavailable, way one: it exits non-zero --------------------
    repository = build_scratch_repository(scratch)
    report = report_path_for(repository, "fallback-exit")
    argv_dump = scratch / "fallback-argv.json"
    result = run_judge_cell(
        repository, stubs,
        {"claude-fable-5-1": {"exit": 1},
         "claude-opus-5": {"report": STUB_JUDGE_REPORT, "dump_argv": str(argv_dump)}},
        report,
    )
    stamp = provenance_stamp_of(report)
    check("a Fable that exits non-zero falls back to Opus, and the cell exits 0",
          result.returncode == 0 and " model=claude-opus-5 " in stamp,
          f"exit {result.returncode}; stamp={stamp!r}; stderr={result.stderr!r}")
    check("the backup judges at max, not at Fable's xhigh",
          " effort=max " in stamp, repr(stamp))
    argv = json.loads(argv_dump.read_text(encoding="utf-8")) if argv_dump.is_file() else []
    check("Opus was actually invoked at max, not merely stamped so",
          argv[argv.index("--effort") + 1] == "max", repr(argv))
    check("the record says what it fell back from",
          " fallback_from=claude-fable-5-1(exit1) " in stamp, repr(stamp))
    check("the fallback is announced on stderr in the phrase the runner lifts",
          any(line.startswith("cold-read-restater-judge-cell: "
                              f"{FELL_BACK_PHRASE} claude-opus-5")
              for line in result.stderr.splitlines()),
          repr(result.stderr))

    # --- Fable unavailable, way two: it exits 0 and writes nothing --------
    repository = build_scratch_repository(scratch)
    report = report_path_for(repository, "fallback-no-report")
    result = run_judge_cell(
        repository, stubs,
        {"claude-fable-5-1": {"stdout": "I cannot help with that request.\n"},
         "claude-opus-5": {"report": STUB_JUDGE_REPORT}},
        report,
    )
    stamp = provenance_stamp_of(report)
    check("a Fable that exits 0 having written nothing falls back to Opus at max",
          result.returncode == 0 and " model=claude-opus-5 " in stamp
          and " effort=max " in stamp,
          f"exit {result.returncode}; stamp={stamp!r}")
    check("the record marks that refusal as the thing it fell back from",
          " fallback_from=claude-fable-5-1(no-report) " in stamp, repr(stamp))
    check("the refusing model's own words still reach stderr",
          "I cannot help with that request." in result.stderr, repr(result.stderr))

    # --- Both models fail --------------------------------------------------
    repository = build_scratch_repository(scratch)
    report = report_path_for(repository, "both-fail")
    result = run_judge_cell(
        repository, stubs,
        {"claude-fable-5-1": {"exit": 1}, "claude-opus-5": {"exit": 1}}, report,
    )
    check("a judge run whose models both fail exits 1 and leaves no report",
          result.returncode == 1 and not report.exists(),
          f"exit {result.returncode}; stderr={result.stderr!r}")
    check("the failure names every model it tried",
          "claude-fable-5-1(exit1)" in result.stderr
          and "claude-opus-5(exit1)" in result.stderr, repr(result.stderr))

    # --- A case file that is not there -------------------------------------
    repository = build_scratch_repository(scratch)
    report = report_path_for(repository, "missing-case-file")
    result = run_judge_cell(
        repository, stubs, {"*": {"report": STUB_JUDGE_REPORT}}, report,
        cases=(THREE_CASES[0],
               (THREE_CASES[1][0], THREE_CASES[1][1],
                "test-cases/defects-two-that-is-not-there.md", THREE_CASES[1][3])),
    )
    check("a missing case file is refused with exit 64, naming case and role",
          result.returncode == 64
          and "case 2: defect list not found:" in result.stderr
          and "Traceback" not in result.stderr,
          f"exit {result.returncode}; stderr={result.stderr!r}")
    check("a refused invocation never launches a model",
          not report.exists(), "the stub claude ran and wrote the report")

    # --- A --restater that cannot name a class -----------------------------
    repository = build_scratch_repository(scratch)
    report = report_path_for(repository, "bad-label")
    result = run_judge_cell(
        repository, stubs, {"*": {"report": STUB_JUDGE_REPORT}}, report,
        restater="Gemini 3.8/flash",
    )
    check("a --restater that cannot be a path segment is refused with exit 64",
          result.returncode == 64 and not report.exists()
          and "cannot name a restater class" in result.stderr,
          f"exit {result.returncode}; stderr={result.stderr!r}")

    # --- A --model this cell pins no effort for ----------------------------
    repository = build_scratch_repository(scratch)
    report = report_path_for(repository, "unpinned-model")
    result = run_judge_cell(
        repository, stubs, {"*": {"report": STUB_JUDGE_REPORT}}, report,
        "--model", "claude-sonnet-5",
    )
    check("a --model with no pinned effort is refused with exit 64, naming its fix",
          result.returncode == 64 and not report.exists()
          and "has no effort pinned" in result.stderr
          and "--effort" in result.stderr,
          f"exit {result.returncode}; stderr={result.stderr!r}")

    repository = build_scratch_repository(scratch)
    report = report_path_for(repository, "unpinned-model-with-effort")
    argv_dump = scratch / "unpinned-argv.json"
    result = run_judge_cell(
        repository, stubs,
        {"claude-sonnet-5": {"report": STUB_JUDGE_REPORT, "dump_argv": str(argv_dump)}},
        report, "--model", "claude-sonnet-5", "--effort", "high",
    )
    stamp = provenance_stamp_of(report)
    check("--model with --effort runs alone and is stamped as what ran",
          result.returncode == 0 and " model=claude-sonnet-5 " in stamp
          and " effort=high " in stamp and "fallback_from=" not in stamp,
          f"exit {result.returncode}; stamp={stamp!r}; stderr={result.stderr!r}")

    # --- --effort alone overrides the ruled efforts for every model --------
    repository = build_scratch_repository(scratch)
    report = report_path_for(repository, "effort-override")
    argv_dump = scratch / "effort-override-argv.json"
    result = run_judge_cell(
        repository, stubs,
        {"claude-fable-5-1": {"report": STUB_JUDGE_REPORT, "dump_argv": str(argv_dump)}},
        report, "--effort", "high",
    )
    stamp = provenance_stamp_of(report)
    argv = json.loads(argv_dump.read_text(encoding="utf-8")) if argv_dump.is_file() else []
    check("--effort overrides the ruled per-model efforts, in the argv and the stamp",
          result.returncode == 0 and " effort=high " in stamp
          and argv[argv.index("--effort") + 1] == "high",
          f"exit {result.returncode}; stamp={stamp!r}; argv={argv!r}")

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
