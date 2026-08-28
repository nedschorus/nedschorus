#!/usr/bin/env python3
"""Tests for md-review-cell-common.py — everything an md-review cell does
except invoke its model.

HOW A CASE RUNS. Each case builds a throwaway git repository holding a copy
of the cell scripts and their prompt templates, and runs the Claude cell
launcher inside it with a stub `claude` first on PATH. Two seams make that
work. The cell takes its repository root from its own location on disk, so a
copy of the scripts is a cell whose whole world is the scratch repository —
no case can touch this checkout. And the stub is the model: it is driven by
MD_REVIEW_CELL_TEST_STUB_PLAN, a JSON map from model id to what that
attempt should do, so a chain of failures and fallbacks is arranged without
a model call, the money, or the half hour. Only the Claude leg is launched,
because what is under test is the module both legs share.

WHAT IS PINNED HERE.

  - The stray-write detector sees a MODIFICATION, not only a creation. The
    detector exists for the accident of 2026-08-24, when a reviewer edited
    the document under review mid-flight and invalidated a full eight-cell
    run. Until nedschorus#167 it compared the NAMES git called dirty before
    and after, and md-review's ordinary subject is a draft that has not
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

Run: python3 scripts/md-review-cell-common-test.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
PROMPTS_DIR = REPO_ROOT / ".claude" / "skills" / "md-review" / "prompts"
CELL_SCRIPT_NAMES = (
    "md-review-cell-common.py",
    "md-review-claude-cell.py",
    "md-review-codex-cell.py",
)

# The document each case reviews, and the one a reviewer would edit by
# accident: it is committed first, then modified without being committed, so
# the run starts with it dirty — md-review's ordinary condition.
TARGET_RELATIVE_PATH = "docs/drafts/md-review-cell-common-test-target.md"

# A stand-in for the `claude` CLI. It does what
# MD_REVIEW_CELL_TEST_STUB_PLAN tells it to for the model it was launched
# with: "report" is text to write to the report path (absent means write
# nothing, which is how a model that dies quietly looks), "edit" is a
# [path, text] pair to append to some other file — a reviewer editing the
# document instead of reviewing it — and "exit" is the code to exit with.
# The report path arrives by environment rather than by parsing the prompt,
# so a change to the prompt templates cannot silently unhook the stub.
STUB_MODEL_RUNTIME = """#!/usr/bin/env python3
import json, os, sys

try:
    sys.stdin.read()  # the Claude leg feeds the prompt on stdin
except OSError:
    pass
argv = sys.argv
model = argv[argv.index("--model") + 1] if "--model" in argv else "*"
plan = json.loads(os.environ["MD_REVIEW_CELL_TEST_STUB_PLAN"])
step = plan.get(model, plan.get("*", {}))
if "report" in step:
    with open(os.environ["MD_REVIEW_CELL_TEST_STUB_REPORT_PATH"], "w",
              encoding="utf-8") as handle:
        handle.write(step["report"])
if "edit" in step:
    edited_path, added_text = step["edit"]
    with open(edited_path, "a", encoding="utf-8") as handle:
        handle.write(added_text)
sys.exit(step.get("exit", 0))
"""

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
                    if "changed files outside its report" in line)


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
    scratch_prompts = repository / ".claude" / "skills" / "md-review" / "prompts"
    scratch_prompts.mkdir(parents=True)
    for prompt_path in PROMPTS_DIR.glob("*.md"):
        shutil.copy2(prompt_path, scratch_prompts / prompt_path.name)
    # The records tree is gitignored in the real repository, which is what
    # keeps a reviewer's own report out of the detector's sight.
    (repository / ".gitignore").write_text("md-review-records/\n", encoding="utf-8")
    target = repository / TARGET_RELATIVE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# Target\n\nOne committed line.\n", encoding="utf-8")
    git(repository, "init", "-b", "main")
    git(repository, "config", "user.email", "test@test.invalid")
    git(repository, "config", "user.name", "md-review-cell-common test")
    git(repository, "add", "-A")
    git(repository, "commit", "-m", "seed")
    return repository


def dirty_the_target(repository):
    """Leave the document under review modified and uncommitted.

    This is the ordinary state of an md-review subject, and the state in
    which the name-only detector went blind.
    """
    with (repository / TARGET_RELATIVE_PATH).open("a", encoding="utf-8") as handle:
        handle.write("An uncommitted revision, written before the review ran.\n")


def run_claude_cell(repository, stub_directory, plan, report_path, *arguments):
    stub_directory.mkdir(parents=True, exist_ok=True)
    stub = stub_directory / "claude"
    stub.write_text(STUB_MODEL_RUNTIME, encoding="utf-8")
    stub.chmod(0o755)
    environment = dict(os.environ)
    environment["PATH"] = f"{stub_directory}{os.pathsep}{environment.get('PATH', '')}"
    environment["MD_REVIEW_CELL_TEST_STUB_PLAN"] = json.dumps(plan)
    environment["MD_REVIEW_CELL_TEST_STUB_REPORT_PATH"] = str(report_path)
    return subprocess.run(
        [sys.executable, str(repository / "scripts" / "md-review-claude-cell.py"),
         "--cell", "restate", "--tier", "floor",
         "--target", TARGET_RELATIVE_PATH, "--report", str(report_path),
         *arguments],
        capture_output=True, text=True, check=False, env=environment,
    )


with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch)
    stubs = scratch / "stub-bin"

    # --- The already-dirty file the reviewer edits -------------------------
    # The whole finding, in one case: the document under review is dirty
    # before the run and the reviewer edits it again. Against the name-only
    # detector the delta is empty and nothing is printed.
    repository = build_scratch_repository(scratch)
    dirty_the_target(repository)
    report = repository / "md-review-records" / "run-a" / "claude-restate-floor.md"
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

    # A creation was always caught; it is here so the two halves of the
    # detector are pinned side by side and neither can be lost alone.
    shutil.rmtree(repository)
    repository = build_scratch_repository(scratch)
    dirty_the_target(repository)
    report = repository / "md-review-records" / "run-b" / "claude-restate-floor.md"
    created_relative_path = "docs/drafts/md-review-cell-common-test-created.md"
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
    report = repository / "md-review-records" / "run-c" / "claude-restate-floor.md"
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
    visible_report_relative_path = "docs/drafts/md-review-cell-common-test-report.md"
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
    report = repository / "md-review-records" / "run-d" / "claude-restate-good.md"
    result = run_claude_cell(
        repository, stubs,
        {"claude-fable-5": {"report": "STUB REVIEW: findings the first model wrote\n",
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
          "claude-fable-5" in result.stderr and "claude-opus-5" in result.stderr,
          repr(result.stderr))

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
    (SCRIPTS_DIR / "md-review-codex-cell.py").read_text(encoding="utf-8").split())
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
