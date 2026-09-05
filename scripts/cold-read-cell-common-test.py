#!/usr/bin/env python3
"""Tests for cold-read-cell-common.py — everything a cold-read cell does
except invoke its model.

HOW A CASE RUNS. Each case builds a throwaway git repository holding a copy
of the cell scripts and their prompt templates, and runs the Claude cell
launcher inside it with a stub `claude` first on PATH. Two seams make that
work. The cell takes its repository root from its own location on disk, so a
copy of the scripts is a cell whose whole world is the scratch repository —
no case can touch this checkout. And the stub is the model: it is driven by
COLD_READ_CELL_TEST_STUB_PLAN, a JSON map from model id to what that
attempt should do, so a chain of failures and fallbacks is arranged without
a model call, the money, or the half hour. Most cases launch the Claude leg
alone, because what is under test is the module both legs share. The ones
that launch the Codex leg do so for a reason named where they sit: a token
total is a figure only the Codex CLI prints, the near-miss accident below
happened to a Codex cell, and the stray-write detector is driven once through
each launcher because a check that runs for one runtime and not the other is
precisely the defect nedschorus#161 records.

WHAT IS PINNED HERE.

  - The stray-write detector sees a MODIFICATION, not only a creation. The
    detector exists for the accident of 2026-08-24, when a reviewer edited
    the document under review mid-flight and invalidated a full eight-cell
    run. Until nedschorus#167 it compared the NAMES git called dirty before
    and after, and a cold read's ordinary subject is a draft that has not
    landed: the document under review is normally dirty already, its name is
    in both snapshots, and the guard was silent in exactly the case it was
    added for. The already-dirty case below fails against that code and the
    newly-created case passes, which is the shape the finding measured.

  - It still does not cry wolf. A run that leaves a dirty tree exactly as it
    found it names nothing, which is the property that keeps the warning
    worth reading; a detector that fired on every already-dirty path would
    fire on every real run.

  - A cell does not report its own report as a stray write. Reports
    ordinarily go under the gitignored records tree, which git never names,
    but the grid's failure note tells an operator to rerun a failed cell
    singly with the cell launchers — and a --report pointed somewhere git
    can see used to be named as a stray write, telling the operator to
    revert the review he had just asked for.

  - The claim the cell docstrings make about all this is true. The Codex
    cell's docstring told its reader that a clean `git status` afterwards
    means the reviewer wrote only where it was told, and that any
    tracked-file change is reported. Neither held: the ordinary run starts
    dirty, so status is never clean, and a change to an already-dirty file
    was exactly what went unreported.

  - A model that writes a report and then fails does not lend its text to
    the next model in the chain. The report path is the chain's only state
    variable and the loop clears it before each attempt; without that, a
    later model that exits 0 having written nothing is credited with its
    predecessor's findings, under a provenance stamp naming the wrong model.

  - Failing to look does not read as looking and finding nothing. When the
    baseline could not be taken, or `git status` could not answer afterwards,
    the cell says so in the words the grid lifts out of its log.

  - And when the model that wrote and then failed is the LAST in the chain,
    its file does not survive the run either. There is no next attempt to
    clear the path, so the cell used to say no report was produced while an
    unstamped one sat in the record directory — where the grid tells the
    reviewing agent failed reviews are absent, and the skill sends it to read
    every report present. A report exists if and only if the run succeeded.

  - A near-miss report is recovered before failure is declared. On
    2026-08-25 a Codex cell was given a record directory ending `-c6fb95f`
    and wrote a complete 33-finding review into `-c6fb95c`, a sibling it
    created itself, and the cell reported "the model exited without writing"
    — true of the path it watched and false of the work. Exactly one
    candidate is recovered; several are refused rather than guessed between,
    because a guess puts a review under a stamp that may not describe it; and
    a file that predates the attempt is left alone, so yesterday's abandoned
    stray is not stamped with today's model.

    The search covers the whole `cold-read-records/` tree — a neighbouring
    record directory, and the root of the tree itself — because the file name
    carries the run (user-ruled 2026-08-25): the grid writes
    `<record directory name>--<runtime>-<pass>-<tier>.md`, so an exact-name
    match belongs to this run and to no other. The case that proves the point
    is the concurrent one: a second grid's report for the same cell, written
    while this attempt ran, is NOT this attempt's report, and the cell fails
    rather than taking it.

  - The stamp carries what the cell cost. `duration_s=` on every stamp, and
    `tokens=` when the runtime reported a total. Absent is absent: a claude
    cell, and a codex cell whose CLI printed no total, carry no `tokens=`
    field rather than a guessed zero, because a zero would read as "this cell
    cost nothing". The total is read from the runtime's stderr and never from
    its stdout, which is the model talking — a reviewer of a document about
    model costs can write "tokens used: N" in its findings, and that sentence
    is not what the run cost.

  - The runtime's stderr survives a successful run. It used to be passed
    straight through to the log scripts/cold-read-grid.py deletes on success,
    which is why the only token figure recoverable from six grids on
    2026-08-25 came from the one cell that failed.

  - And the runtime's stdout survives a model that exits 0 having written
    nothing. That path used to discard it, so the grids of 2026-08-31 and
    2026-09-01 recorded claude-hunt-floor's silence with none of the model's
    own words to explain it.

  - The stray-write detector runs for both runtimes. The cases above drive
    the Claude launcher; the one at the end of the file drives the Codex
    launcher through the same shared call. The fleet's other review
    instrument gated the same comparison on `runtime == "codex"`, and on
    2026-08-21 a claude agent wrote a 25KB file into a worktree undetected
    (nedschorus#161). A pair of cases, one per launcher, is what makes a
    reintroduced gate fail loudly instead of quietly.

Run: python3 scripts/cold-read-cell-common-test.py
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
PROMPTS_DIR = REPO_ROOT / ".claude" / "skills" / "cold-read" / "prompts"
CELL_SCRIPT_NAMES = (
    "cold-read-cell-common.py",
    "cold-read-claude-cell.py",
    "cold-read-codex-cell.py",
)

# The document each case reviews, and the one a reviewer would edit by
# accident: it is committed first, then modified without being committed, so
# the run starts with it dirty — a cold read's ordinary condition.
TARGET_RELATIVE_PATH = "docs/drafts/cold-read-cell-common-test-target.md"

# The phrase both "the check did not run" messages must carry, spelled out
# here rather than imported: it is a contract with scripts/cold-read-grid.py,
# which greps a cell's stderr log for this text, and a test that read the
# phrase from the module it tests would pass however either side was reworded.
STRAY_WRITE_CHECK_SKIPPED_PHRASE = "stray writes were not checked for this run"

# What a stub writes when it puts its review somewhere other than the path it
# was given, so a case can tell each recovered review apart from one written
# where it was asked for.
NEAR_MISS_REVIEW_TEXT = "STUB REVIEW: written one character away\n"
RECORDS_ROOT_REVIEW_TEXT = "STUB REVIEW: written flat into the records root\n"
CONCURRENT_RUN_REVIEW_TEXT = (
    "STUB REVIEW: a concurrent grid's review of another document\n")

# A stand-in for the `claude` and `codex` CLIs. It does what
# COLD_READ_CELL_TEST_STUB_PLAN tells it to for the model it was launched
# with: "report" is text to write to the report path (absent means write
# nothing, which is how a model that dies quietly looks), "edit" is a
# [path, text] pair to append to some other file — a reviewer editing the
# document instead of reviewing it — "break_git" is a .git directory to
# rename aside, which leaves a cell whose baseline was taken and whose
# post-run check cannot run, "near_miss" reproduces the 2026-08-25 accident
# (see below), "report_at_records_root" and "concurrent_run_report" are the
# other two places a report can turn up, "stderr" and "stdout" are the
# runtime's own words on each stream, and "exit" is the code to exit with.
# The report path arrives by environment rather than by parsing the prompt,
# so a change to the prompt templates cannot silently unhook the stub.
STUB_MODEL_RUNTIME = """#!/usr/bin/env python3
import json, os, pathlib, sys

try:
    sys.stdin.read()  # the Claude leg feeds the prompt on stdin
except OSError:
    pass
argv = sys.argv
# --model is the Claude leg's flag and -m the Codex leg's. A stub that knew
# only one of them would answer every Codex plan with the "*" step, so no
# chain could be arranged for that leg and a per-model case would pass for
# the wrong reason.
model = "*"
for model_flag in ("--model", "-m"):
    if model_flag in argv:
        model = argv[argv.index(model_flag) + 1]
        break
plan = json.loads(os.environ["COLD_READ_CELL_TEST_STUB_PLAN"])
step = plan.get(model, plan.get("*", {}))
report_path = pathlib.Path(os.environ["COLD_READ_CELL_TEST_STUB_REPORT_PATH"])
if "report" in step:
    report_path.write_text(step["report"], encoding="utf-8")
# The 2026-08-25 near-miss, reproduced: the model writes its whole review into
# a record directory one character from the one it was given, having created
# that directory itself. Each entry is the character it puts in place of the
# last one of that directory's name, so several entries make several
# candidates for the recovery to refuse to guess between.
for replacement_character in step.get("near_miss", []):
    sibling = (report_path.parent.parent
               / (report_path.parent.name[:-1] + replacement_character))
    sibling.mkdir(parents=True, exist_ok=True)
    (sibling / report_path.name).write_text(
        NEAR_MISS_REVIEW_TEXT, encoding="utf-8")
# The right file name in the wrong place, twice over. Flat in the root of the
# records tree, the name still says which run wrote it, so it is recoverable.
# In another run's record directory under that run's own name, it is a second
# grid's finished review of some other document, and taking it would stamp
# this run's provenance onto the wrong text while leaving that run with
# nothing.
if step.get("report_at_records_root"):
    (report_path.parent.parent / report_path.name).write_text(
        RECORDS_ROOT_REVIEW_TEXT, encoding="utf-8")
concurrent_run_report = step.get("concurrent_run_report")
if concurrent_run_report:
    other_directory_name, other_file_name = concurrent_run_report
    other_directory = report_path.parent.parent / other_directory_name
    other_directory.mkdir(parents=True, exist_ok=True)
    (other_directory / other_file_name).write_text(
        CONCURRENT_RUN_REVIEW_TEXT, encoding="utf-8")
if "edit" in step:
    edited_path, added_text = step["edit"]
    with open(edited_path, "a", encoding="utf-8") as handle:
        handle.write(added_text)
if "break_git" in step:
    git_directory = pathlib.Path(step["break_git"])
    git_directory.rename(git_directory.with_name(".git-renamed-by-the-stub"))
# The two streams the cell treats differently: stderr is the CLI reporting,
# which is where the Codex token total appears, and stdout is the model
# talking. A case that needs the difference to matter writes both.
if "stderr" in step:
    sys.stderr.write(step["stderr"])
if "stdout" in step:
    sys.stdout.write(step["stdout"])
sys.exit(step.get("exit", 0))
""".replace("NEAR_MISS_REVIEW_TEXT", repr(NEAR_MISS_REVIEW_TEXT)
).replace("RECORDS_ROOT_REVIEW_TEXT", repr(RECORDS_ROOT_REVIEW_TEXT)
).replace("CONCURRENT_RUN_REVIEW_TEXT", repr(CONCURRENT_RUN_REVIEW_TEXT))

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def stray_write_warning(stderr_text):
    """The cell's stray-write warning alone, or "" when it printed none.

    Isolated because the cell's last line names the report path too, and a
    case that searched the whole of stderr for a path would pass or fail on
    that line rather than on the warning it means to read.
    """
    return " ".join(line for line in stderr_text.splitlines()
                    if "files outside its report changed while it ran" in line)


def git(repository, *arguments):
    completed = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        capture_output=True, text=True, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(arguments)}: {completed.stderr.strip()}")
    return completed.stdout


def build_scratch_repository(scratch):
    """A git repository the cell scripts believe they live in.

    The scripts are copied rather than imported because the cell derives its
    repository root — the tree its detector runs `git status` over — from
    its own path. A copy is the only way to point that at a scratch tree.
    """
    repository = scratch / "scratch-checkout"
    (repository / "scripts").mkdir(parents=True)
    for script_name in CELL_SCRIPT_NAMES:
        shutil.copy2(SCRIPTS_DIR / script_name, repository / "scripts" / script_name)
        (repository / "scripts" / script_name).chmod(0o755)
    scratch_prompts = repository / ".claude" / "skills" / "cold-read" / "prompts"
    scratch_prompts.mkdir(parents=True)
    for prompt_path in PROMPTS_DIR.glob("*.md"):
        shutil.copy2(prompt_path, scratch_prompts / prompt_path.name)
    # The records tree is gitignored in the real repository, which is what
    # keeps a reviewer's own report out of the detector's sight.
    (repository / ".gitignore").write_text("cold-read-records/\n", encoding="utf-8")
    target = repository / TARGET_RELATIVE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# Target\n\nOne committed line.\n", encoding="utf-8")
    git(repository, "init", "-b", "main")
    git(repository, "config", "user.email", "test@test.invalid")
    git(repository, "config", "user.name", "cold-read-cell-common test")
    git(repository, "add", "-A")
    git(repository, "commit", "-m", "seed")
    return repository


def dirty_the_target(repository):
    """Leave the document under review modified and uncommitted.

    This is the ordinary state of a cold-read subject, and the state in
    which the name-only detector went blind.
    """
    with (repository / TARGET_RELATIVE_PATH).open("a", encoding="utf-8") as handle:
        handle.write("An uncommitted revision, written before the review ran.\n")


def run_cell_launcher(repository, stub_directory, plan, report_path, *arguments,
                      runtime="claude", environment_overrides=None):
    """One cell launcher, run against a stub standing in for its runtime.

    The stub is installed under the runtime's own name, because that is how
    each launcher finds its CLI: `cold-read-claude-cell.py` execs `claude`
    and `cold-read-codex-cell.py` execs `codex`, and a stub on PATH under
    that name is the whole seam. Both legs share this one function so a case
    written for either reads the same and neither leg can drift into a
    private harness.
    """
    stub_directory.mkdir(parents=True, exist_ok=True)
    stub = stub_directory / runtime
    stub.write_text(STUB_MODEL_RUNTIME, encoding="utf-8")
    stub.chmod(0o755)
    environment = dict(os.environ)
    environment["PATH"] = f"{stub_directory}{os.pathsep}{environment.get('PATH', '')}"
    environment["COLD_READ_CELL_TEST_STUB_PLAN"] = json.dumps(plan)
    environment["COLD_READ_CELL_TEST_STUB_REPORT_PATH"] = str(report_path)
    environment.update(environment_overrides or {})
    return subprocess.run(
        [sys.executable, str(repository / "scripts" / f"cold-read-{runtime}-cell.py"),
         "--cell", "restate", "--tier", "floor",
         "--target", TARGET_RELATIVE_PATH, "--report", str(report_path),
         *arguments],
        capture_output=True, text=True, check=False, env=environment,
    )


def run_claude_cell(repository, stub_directory, plan, report_path, *arguments,
                    environment_overrides=None):
    return run_cell_launcher(repository, stub_directory, plan, report_path,
                             *arguments, runtime="claude",
                             environment_overrides=environment_overrides)


def run_codex_cell(repository, stub_directory, plan, report_path, *arguments,
                   environment_overrides=None):
    return run_cell_launcher(repository, stub_directory, plan, report_path,
                             *arguments, runtime="codex",
                             environment_overrides=environment_overrides)


def report_path_for(repository, case_slug, runtime):
    """A report path shaped exactly as the grid names one: the record
    directory's own name, then `--`, then the cell.

    The prefix is what makes the recovery below safe to search the whole
    records tree with (user-ruled 2026-08-25): one file name belongs to one
    run. It also gives each case a record directory of its own, so one case's
    leavings can never be a candidate for the next case's recovery. The cases
    at the top of this file name their reports directly instead, because what
    they pin — the stray-write detector — does not turn on the name.
    """
    record_directory_name = f"2026-08-25-{case_slug}-aaaaaaa"
    return (repository / "cold-read-records" / record_directory_name
            / f"{record_directory_name}--{runtime}-hunt-floor.md")


def near_miss_directory_of(report):
    """Where a stub writes when its plan says to write one character away:
    the record directory's name with its last character replaced."""
    return report.parent.parent / (report.parent.name[:-1] + "X")


def provenance_stamp_of(report):
    """The report's provenance line, or "" when no report was written.

    The stamp is the first line of every report the shared module produces,
    and a case that searched the whole file for a field name could find one
    the reviewer had written in its own findings.
    """
    if not report.is_file():
        return ""
    return report.read_text(encoding="utf-8").splitlines()[0]


with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch)
    stubs = scratch / "stub-bin"

    # --- The already-dirty file the reviewer edits -------------------------
    # The whole finding, in one case: the document under review is dirty
    # before the run and the reviewer edits it again. Against the name-only
    # detector the delta is empty and nothing is printed.
    repository = build_scratch_repository(scratch)
    dirty_the_target(repository)
    report = repository / "cold-read-records" / "run-a" / "claude-restate-floor.md"
    result = run_claude_cell(
        repository, stubs,
        {"*": {"report": "STUB REVIEW: one restatement\n",
               "edit": [str(repository / TARGET_RELATIVE_PATH),
                        "The reviewer's own edit, which it should not have made.\n"]}},
        report,
    )
    check("a reviewer edit inside an already-dirty file is reported as a stray write",
          stray_write_warning(result.stderr) != "", repr(result.stderr))
    check("the stray-write warning names the file that was edited",
          TARGET_RELATIVE_PATH in stray_write_warning(result.stderr), repr(result.stderr))
    check("the cell still succeeds — writes are detected, not blocked",
          result.returncode == 0, f"exit {result.returncode}; stderr={result.stderr!r}")
    # The warning says what the snapshot comparison can know and no more. On
    # 2026-09-02 two cells named a file the commissioning seat was itself
    # appending to as "the reviewer changed" (nedschorus#244); the check cannot
    # see who wrote, so the sentence must not say.
    check("the warning does not name the reviewer as the one who wrote",
          "the reviewer changed" not in stray_write_warning(result.stderr),
          repr(result.stderr))
    check("the warning says the cell cannot tell who wrote the files",
          "cannot tell whether the reviewer wrote them" in stray_write_warning(result.stderr),
          repr(result.stderr))
    check("the warning opens with the cell's own name and the pinned phrase, "
          "which is what the grid lifts on",
          any(line.startswith("cold-read-claude-cell: files outside its report changed while it ran")
              for line in result.stderr.splitlines()),
          repr(result.stderr))

    # A creation was always caught; it is here so the two halves of the
    # detector are pinned side by side and neither can be lost alone.
    shutil.rmtree(repository)
    repository = build_scratch_repository(scratch)
    dirty_the_target(repository)
    report = repository / "cold-read-records" / "run-b" / "claude-restate-floor.md"
    created_relative_path = "docs/drafts/cold-read-cell-common-test-created.md"
    result = run_claude_cell(
        repository, stubs,
        {"*": {"report": "STUB REVIEW: one restatement\n",
               "edit": [str(repository / created_relative_path),
                        "A file the reviewer created where it was not asked to.\n"]}},
        report,
    )
    check("a file the reviewer newly creates is reported as a stray write",
          created_relative_path in stray_write_warning(result.stderr), repr(result.stderr))

    # --- And it does not cry wolf ------------------------------------------
    # The tree is dirty and the reviewer touched nothing but its report. A
    # detector that named the already-dirty document here would accuse every
    # reviewer of every real run, and its readers would learn to skip it.
    shutil.rmtree(repository)
    repository = build_scratch_repository(scratch)
    dirty_the_target(repository)
    report = repository / "cold-read-records" / "run-c" / "claude-restate-floor.md"
    result = run_claude_cell(
        repository, stubs, {"*": {"report": "STUB REVIEW: one restatement\n"}}, report,
    )
    check("a run that changed nothing reports no stray write, though the tree is dirty",
          stray_write_warning(result.stderr) == "", repr(result.stderr))
    check("the report is written and the cell succeeds",
          result.returncode == 0 and report.is_file(),
          f"exit {result.returncode}; stderr={result.stderr!r}")

    # --- The cell's own report is not a stray write ------------------------
    # A cell rerun by hand with --report outside the gitignored records tree
    # — which the grid's failure note invites — used to be told to revert the
    # review it had just written.
    shutil.rmtree(repository)
    repository = build_scratch_repository(scratch)
    dirty_the_target(repository)
    visible_report_relative_path = "docs/drafts/cold-read-cell-common-test-report.md"
    report = repository / visible_report_relative_path
    result = run_claude_cell(
        repository, stubs, {"*": {"report": "STUB REVIEW: one restatement\n"}}, report,
    )
    check("a --report git can see is not reported as the reviewer's stray write",
          stray_write_warning(result.stderr) == "", repr(result.stderr))
    check("the hand-run cell with a visible --report still succeeds",
          result.returncode == 0 and report.is_file(),
          f"exit {result.returncode}; stderr={result.stderr!r}")

    # The subtraction is exactly one path wide: a real stray edit in the same
    # run is still named, and the report is still not.
    shutil.rmtree(repository)
    repository = build_scratch_repository(scratch)
    dirty_the_target(repository)
    report = repository / visible_report_relative_path
    result = run_claude_cell(
        repository, stubs,
        {"*": {"report": "STUB REVIEW: one restatement\n",
               "edit": [str(repository / TARGET_RELATIVE_PATH),
                        "The reviewer's own edit, which it should not have made.\n"]}},
        report,
    )
    check("a visible --report does not hide a real stray write in the same run",
          TARGET_RELATIVE_PATH in stray_write_warning(result.stderr), repr(result.stderr))
    check("the report itself is still left out of the stray-write warning",
          visible_report_relative_path not in stray_write_warning(result.stderr),
          repr(result.stderr))

    # --- The chain does not lend one model's text to another ---------------
    # The first model writes a report and then fails; the second exits 0
    # having written nothing. Without the reset at the top of the loop the
    # second is credited with the first's findings and stamped as their
    # author. Both must fail, and the cell must say so.
    shutil.rmtree(repository)
    repository = build_scratch_repository(scratch)
    report = repository / "cold-read-records" / "run-d" / "claude-restate-good.md"
    result = run_claude_cell(
        repository, stubs,
        {"claude-fable-5-1": {"report": "STUB REVIEW: findings the first model wrote\n",
                              "exit": 1},
         "claude-opus-5": {"exit": 0}},
        report, "--tier", "good",
    )
    check("a chain whose models all fail to produce a report exits 1",
          result.returncode == 1, f"exit {result.returncode}; stderr={result.stderr!r}")
    check("a model that writes then fails does not lend its text to the next model",
          not report.exists(),
          "the first model's report survived into the second model's attempt")
    check("the failed chain names both attempts",
          "claude-fable-5-1" in result.stderr and "claude-opus-5" in result.stderr,
          repr(result.stderr))

    # --- The last model's report does not outlive its failure -------------
    # The credit exhaustion of 2026-08-23 in one case: a model writes its
    # findings and then exits non-zero. It is the last model in the chain, so
    # nothing clears the path after it, and the cell announces a failure over
    # a file that is still there and carries no provenance stamp.
    shutil.rmtree(repository)
    repository = build_scratch_repository(scratch)
    report = repository / "cold-read-records" / "run-e" / "claude-restate-floor.md"
    result = run_claude_cell(
        repository, stubs,
        {"*": {"report": "FINDINGS: 1. something real\nclean sections: none\n",
               "exit": 1}},
        report, "--model", "stub-model-that-writes-then-fails",
    )
    check("a cell whose only model wrote a report and then failed exits 1",
          result.returncode == 1, f"exit {result.returncode}; stderr={result.stderr!r}")
    check("the cell says no report was produced",
          "No report was produced" in result.stderr, repr(result.stderr))
    check("no report is left behind for a reader to mistake for a review",
          not report.exists(),
          "an unstamped report survived a run the cell called failed")

    # --- The quiet death keeps the model's own account --------------------
    # A model that exits 0 having written nothing is the ending that explains
    # itself least, and it was the one keeping no evidence: the non-zero path
    # printed the runtime's stdout, this one dropped it. claude-hunt-floor
    # produced no report on the grids of 2026-08-31 and 2026-09-01 and left
    # three refusal lines and nothing of the model's in either log, while the
    # same argv rerun by hand put 512 bytes on stdout. What the model said
    # must reach the log the grid keeps on failure.
    shutil.rmtree(repository)
    repository = build_scratch_repository(scratch)
    report = repository / "cold-read-records" / "run-h" / "claude-restate-floor.md"
    result = run_claude_cell(
        repository, stubs,
        {"*": {"stdout": "STUB CHAT: I read the document and then wrote nothing.\n",
               "exit": 0}},
        report, "--model", "stub-model-that-talks-then-writes-nothing",
    )
    check("a model that exits 0 writing nothing still fails the cell",
          result.returncode == 1 and not report.exists(),
          f"exit {result.returncode}; stderr={result.stderr!r}")
    check("the model's own words survive the no-report path",
          "I read the document and then wrote nothing." in result.stderr,
          repr(result.stderr))

    # --- Failing to look says so, in the words the grid lifts -------------
    # Two ways the check cannot run, and both must be distinguishable from a
    # clean result — that is the whole reason WriteDetectorUnavailable is an
    # exception and not a path-shaped string. Both lines carry the phrase
    # scripts/cold-read-grid.py greps this cell's log for before deleting it;
    # scripts/cold-read-grid-test.py pins the other end of that contract.
    shutil.rmtree(repository)
    repository = build_scratch_repository(scratch)
    report = repository / "cold-read-records" / "run-f" / "claude-restate-floor.md"
    result = run_claude_cell(
        repository, stubs, {"*": {"report": "STUB REVIEW: one restatement\n"}}, report,
        environment_overrides={"GIT_DIR": str(scratch / "no-such-git-directory")},
    )
    check("a cell that could not take a baseline says the check did not run",
          STRAY_WRITE_CHECK_SKIPPED_PHRASE in result.stderr, repr(result.stderr))
    check("...and says a missing check is not a clean result",
          "failure to look, not a clean result" in result.stderr, repr(result.stderr))

    shutil.rmtree(repository)
    repository = build_scratch_repository(scratch)
    report = repository / "cold-read-records" / "run-g" / "claude-restate-floor.md"
    result = run_claude_cell(
        repository, stubs,
        {"*": {"report": "STUB REVIEW: one restatement\n",
               "break_git": str(repository / ".git")}},
        report,
    )
    check("a cell whose post-run git status fails says the check did not run",
          STRAY_WRITE_CHECK_SKIPPED_PHRASE in result.stderr, repr(result.stderr))
    check("...and that line too says it is not a clean result",
          "failure to look, not a clean result" in result.stderr, repr(result.stderr))

    # --- The near-miss report, found before failure is declared -----------
    # The 2026-08-25 accident in one case: the model creates a record
    # directory one character from the one it was given and writes its whole
    # review there. The cell used to report "the model exited without
    # writing", which was true of the path it watched and false of the work.
    # Driven through the Codex launcher because that is the leg it happened
    # to; the recovery itself lives on the shared path and serves both.
    shutil.rmtree(repository)
    repository = build_scratch_repository(scratch)
    report = report_path_for(repository, "near-miss", "codex")
    result = run_codex_cell(repository, stubs, {"*": {"near_miss": ["X"]}}, report)
    check("a report written one directory away is recovered, and the cell succeeds",
          result.returncode == 0, f"exit {result.returncode}; stderr={result.stderr!r}")
    check("the recovered report is at the path the cell was given",
          report.is_file(), f"{report} absent")
    recovered_text = report.read_text(encoding="utf-8") if report.is_file() else ""
    check("the recovered report holds what the model actually wrote",
          NEAR_MISS_REVIEW_TEXT.strip() in recovered_text, repr(recovered_text[:200]))
    check("the recovered report is stamped like any other",
          recovered_text.startswith("<!-- provenance: runtime=codex"),
          repr(recovered_text[:120]))
    check("the recovery is announced on stderr for the grid to lift",
          "recovered a near-miss report" in result.stderr, repr(result.stderr))
    check("the near-miss copy is moved, not copied",
          not (near_miss_directory_of(report) / report.name).exists(),
          "two files now hold one review, which is the ambiguity recovery removes")

    # Two candidates is ambiguous, and a guess would put a review under a
    # stamp that may not describe it. Refused, and the refusal names both.
    shutil.rmtree(repository)
    repository = build_scratch_repository(scratch)
    report = report_path_for(repository, "two-candidates", "codex")
    result = run_codex_cell(repository, stubs, {"*": {"near_miss": ["X", "Y"]}}, report)
    check("two near-miss candidates fail the cell rather than being guessed between",
          result.returncode == 1, f"exit {result.returncode}; stderr={result.stderr!r}")
    check("the refusal says the candidates were ambiguous",
          "more than one, which is ambiguous" in result.stderr, repr(result.stderr))
    check("neither candidate was moved into place",
          not report.is_file(), f"{report} exists")

    # No candidate at all is the ordinary failure and stays one — but it now
    # names where it looked, which is the whole difference from the message
    # that lost a review.
    shutil.rmtree(repository)
    repository = build_scratch_repository(scratch)
    report = report_path_for(repository, "no-candidate", "codex")
    result = run_codex_cell(repository, stubs, {"*": {}}, report)
    check("a run that wrote nothing anywhere still fails",
          result.returncode == 1, f"exit {result.returncode}; stderr={result.stderr!r}")
    check("the failure names what it looked for",
          "no near-miss report to recover" in result.stderr
          and report.name in result.stderr
          and "anywhere under" in result.stderr
          and str(repository / "cold-read-records") in result.stderr,
          repr(result.stderr))

    # A file that predates the attempt is not this attempt's report. Without
    # the mtime cutoff, yesterday's abandoned stray would be recovered today
    # and stamped with today's model.
    shutil.rmtree(repository)
    repository = build_scratch_repository(scratch)
    report = report_path_for(repository, "stale-sibling", "codex")
    stale_sibling_report = near_miss_directory_of(report) / report.name
    stale_sibling_report.parent.mkdir(parents=True, exist_ok=True)
    stale_sibling_report.write_text("STUB REVIEW: from a run that finished yesterday\n",
                                    encoding="utf-8")
    an_hour_ago = time.time() - 3600
    os.utime(stale_sibling_report, (an_hour_ago, an_hour_ago))
    result = run_codex_cell(repository, stubs, {"*": {}}, report)
    check("a sibling file older than the attempt is not recovered",
          result.returncode == 1, f"exit {result.returncode}; stderr={result.stderr!r}")
    check("the stale sibling is left where it was",
          stale_sibling_report.is_file(), "an older run's file was consumed by this one")
    check("no report was fabricated from the stale sibling",
          not report.is_file(), f"{report} exists")

    # A report written flat into the records root, rather than into any record
    # directory, is still this run's report: the name says so. The search
    # covers the root of the tree and not only the directories under it.
    shutil.rmtree(repository)
    repository = build_scratch_repository(scratch)
    report = report_path_for(repository, "flat-in-records-root", "codex")
    result = run_codex_cell(
        repository, stubs, {"*": {"report_at_records_root": True}}, report,
    )
    check("a report written flat into cold-read-records/ is recovered",
          result.returncode == 0, f"exit {result.returncode}; stderr={result.stderr!r}")
    check("the report recovered from the records root is at the path given",
          report.is_file(), f"{report} absent")
    recovered_text = report.read_text(encoding="utf-8") if report.is_file() else ""
    check("it holds what the model wrote in the records root",
          RECORDS_ROOT_REVIEW_TEXT.strip() in recovered_text, repr(recovered_text[:200]))
    check("the copy in the records root is moved, not copied",
          not (report.parent.parent / report.name).exists(),
          "two files now hold one review")

    # THE CASE THE RUN-NAMED FILE EXISTS FOR (user-ruled 2026-08-25). A second
    # grid, running at the same time in the same checkout, writes its own
    # report for the same cell while this attempt runs. Under the old bare
    # names both files were `codex-hunt-floor.md`, and this cell could recover
    # the other run's correctly placed report: this run would then hold a
    # review of the wrong document under its stamp, and the other run would
    # lose the review it produced. The prefix is what makes the two
    # distinguishable, and this case is what proves the distinction holds.
    shutil.rmtree(repository)
    repository = build_scratch_repository(scratch)
    report = report_path_for(repository, "concurrent-run", "codex")
    concurrent_report = (
        report.parent.parent / report.parent.name.replace("aaaaaaa", "bbbbbbb")
        / report.name.replace("aaaaaaa", "bbbbbbb"))
    result = run_codex_cell(
        repository, stubs,
        {"*": {"concurrent_run_report": [concurrent_report.parent.name,
                                         concurrent_report.name]}},
        report,
    )
    check("a concurrent run's report is not recovered as this run's",
          result.returncode == 1, f"exit {result.returncode}; stderr={result.stderr!r}")
    check("no report was fabricated from the concurrent run's file",
          not report.is_file(), f"{report} exists")
    check("the concurrent run keeps the report it wrote",
          concurrent_report.is_file(),
          f"{concurrent_report} was taken from the run that wrote it")
    check("the failure names the file it looked for, prefix and all",
          "no near-miss report to recover" in result.stderr
          and report.name in result.stderr
          and "anywhere under" in result.stderr
          and str(repository / "cold-read-records") in result.stderr,
          repr(result.stderr))

    # --- What the cell cost is part of what it did ------------------------
    # Until 2026-08-25 the stamp recorded every input to the run — runtime,
    # model, effort, cell, tier, target — and nothing about the run itself,
    # so a record set answered "what was asked for" and could not answer
    # "what did this cost".
    shutil.rmtree(repository)
    repository = build_scratch_repository(scratch)
    report = report_path_for(repository, "duration-claude", "claude")
    result = run_claude_cell(
        repository, stubs, {"*": {"report": "STUB REVIEW: one restatement\n"}}, report,
    )
    check("a claude cell succeeds with a stub runtime",
          result.returncode == 0, f"exit {result.returncode}; stderr={result.stderr!r}")
    stamp = provenance_stamp_of(report)
    check("a claude stamp carries duration_s",
          re.search(r"\bduration_s=\d+\b", stamp) is not None, repr(stamp))
    check("a claude stamp carries no tokens field, because claude reports none",
          "tokens=" not in stamp, repr(stamp))
    check("target= stays the last field, so a path with a space cannot swallow one",
          stamp.endswith(f"target={TARGET_RELATIVE_PATH} -->"), repr(stamp))

    # The Codex CLI ends a run with its token total on stderr. The regression
    # underneath this one: stderr used to be passed straight to a log the
    # grid deletes on success, so across six grids that day the only
    # recoverable token figure came from the single cell that FAILED.
    shutil.rmtree(repository)
    repository = build_scratch_repository(scratch)
    report = report_path_for(repository, "tokens-codex", "codex")
    result = run_codex_cell(
        repository, stubs,
        {"*": {"report": "STUB REVIEW: one restatement\n",
               "stderr": "[2026-08-25T12:00:00] tokens used: 12,345\n"}},
        report,
    )
    check("a codex cell whose CLI printed a token total succeeds",
          result.returncode == 0, f"exit {result.returncode}; stderr={result.stderr!r}")
    stamp = provenance_stamp_of(report)
    check("the token total reaches the stamp, comma-free",
          "tokens=12345" in stamp, repr(stamp))
    check("that stamp carries duration_s too",
          re.search(r"\bduration_s=\d+\b", stamp) is not None, repr(stamp))
    check("the runtime's stderr survives a successful run",
          "tokens used: 12,345" in result.stderr, repr(result.stderr))

    # stdout is the model talking, and a reviewer of a document about model
    # costs can quite reasonably write "tokens used: N" in its findings.
    # Reading stdout would stamp the reviewer's sentence as the run's price.
    shutil.rmtree(repository)
    repository = build_scratch_repository(scratch)
    report = report_path_for(repository, "tokens-in-chat-text", "codex")
    result = run_codex_cell(
        repository, stubs,
        {"*": {"report": "STUB REVIEW: one restatement\n",
               "stdout": "The draft claims tokens used: 99,999 per run, which I doubt.\n"}},
        report,
    )
    check("a cell whose reviewer only talked about tokens succeeds",
          result.returncode == 0, f"exit {result.returncode}; stderr={result.stderr!r}")
    check("a number in the reviewer's own words is not stamped as the run's cost",
          "tokens=" not in provenance_stamp_of(report), repr(provenance_stamp_of(report)))

    # And an absent figure is absent: an omitted field reads as "not
    # reported", where a zero would read as "this cell cost nothing".
    shutil.rmtree(repository)
    repository = build_scratch_repository(scratch)
    report = report_path_for(repository, "no-tokens-codex", "codex")
    result = run_codex_cell(
        repository, stubs, {"*": {"report": "STUB REVIEW: one restatement\n"}}, report,
    )
    check("a codex cell whose CLI printed no total succeeds",
          result.returncode == 0, f"exit {result.returncode}; stderr={result.stderr!r}")
    check("an unreported token total is omitted, never guessed at",
          "tokens=" not in provenance_stamp_of(report), repr(provenance_stamp_of(report)))

    # --- The effort a cell runs at is the caller's to name ----------------
    # The tier maps pin an effort per tier, and --effort overrides them the
    # way --model overrides the model chain: honored exactly, no fallback.
    # The behavior this pins showed up in the 2026-08-29 walk-reviewer model
    # trial: every cell had to run at a named effort while the Codex tier map
    # pins xhigh, and an override quietly running the mapped level would have
    # measured the wrong configuration under a stamp naming the right one.
    # The ruled fast tier (2026-08-30: gpt-5.6-terra at low) runs through
    # this same flag.
    shutil.rmtree(repository)
    repository = build_scratch_repository(scratch)
    report = report_path_for(repository, "effort-default", "claude")
    result = run_claude_cell(
        repository, stubs, {"*": {"report": "STUB REVIEW: one restatement\n"}}, report,
    )
    check("a cell given no --effort runs at the tier map's level",
          result.returncode == 0
          and "effort=max" in provenance_stamp_of(report),
          f"exit {result.returncode}; stamp={provenance_stamp_of(report)!r}")

    shutil.rmtree(repository)
    repository = build_scratch_repository(scratch)
    report = report_path_for(repository, "effort-override", "claude")
    result = run_claude_cell(
        repository, stubs, {"*": {"report": "STUB REVIEW: one restatement\n"}},
        report, "--effort", "low",
    )
    check("--effort overrides the tier map and is stamped as what ran",
          result.returncode == 0
          and "effort=low" in provenance_stamp_of(report),
          f"exit {result.returncode}; stamp={provenance_stamp_of(report)!r}")

    shutil.rmtree(repository)
    repository = build_scratch_repository(scratch)
    report = report_path_for(repository, "effort-unknown", "claude")
    result = run_claude_cell(
        repository, stubs, {"*": {"report": "STUB REVIEW: one restatement\n"}},
        report, "--effort", "extreme",
    )
    check("an effort level the runtimes do not accept is refused, not passed on",
          result.returncode == 64 and not report.is_file(),
          f"exit {result.returncode}; stderr={result.stderr!r}")

    # --- The stray-write detector runs for the Codex leg too --------------
    # The cases at the top of this file drive the Claude launcher; this one
    # drives the Codex launcher through the same shared call, so the pair is
    # one case per launcher. nedschorus#161: the fleet's other review
    # instrument ran this comparison only after codex cells, and a claude
    # agent wrote a 25KB file into a worktree that nothing reported. Removing
    # the check for either leg fails here.
    shutil.rmtree(repository)
    repository = build_scratch_repository(scratch)
    dirty_the_target(repository)
    report = report_path_for(repository, "stray-codex", "codex")
    result = run_codex_cell(
        repository, stubs,
        {"*": {"report": "STUB REVIEW: one restatement\n",
               "edit": [str(repository / TARGET_RELATIVE_PATH),
                        "The reviewer's own edit, which it should not have made.\n"]}},
        report,
    )
    check("a reviewer edit is reported as a stray write through the Codex launcher too",
          stray_write_warning(result.stderr) != "", repr(result.stderr))
    check("the Codex leg's warning names the file that was edited",
          TARGET_RELATIVE_PATH in stray_write_warning(result.stderr), repr(result.stderr))
    check("the Codex cell still succeeds — writes are detected, not blocked",
          result.returncode == 0, f"exit {result.returncode}; stderr={result.stderr!r}")


# --- What the cell docstrings promise about the detector -------------------
# Prose, checked because prose is what the next reader believes. The Codex
# cell's docstring claimed a clean `git status` afterwards proves the
# reviewer wrote only where it was told, and that the shared module reports
# any tracked-file change. The ordinary run starts dirty, so status is never
# clean; and a change to an already-dirty file was the case that went
# unreported. Both sentences outlived the code they described.
# Line breaks are collapsed first: both sentences are wrapped in the source,
# and a check that missed a claim because of where its line ended would be a
# check that passes for the wrong reason.
codex_cell_prose = " ".join(
    (SCRIPTS_DIR / "cold-read-codex-cell.py").read_text(encoding="utf-8").split())
check("the Codex cell does not claim a clean git status proves anything",
      "a clean `git status` afterwards means" not in codex_cell_prose,
      "the docstring still promises a guarantee the ordinary dirty tree cannot give")
check("the Codex cell does not claim every tracked-file change is reported",
      "reports any tracked-file change as a stray write" not in codex_cell_prose,
      "the docstring still describes the name-only detector replaced in nedschorus#167")

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
