#!/usr/bin/env python3
"""Tests for cold-read-grid.py — what a grid run tells the agent reading it.

HOW A CASE RUNS. Each case builds a throwaway git repository holding a copy
of the grid, the two cell launchers, the module they share and the prompt
templates, and runs the grid inside it with stub `claude` and `codex`
executables first on PATH. Two seams make that work. The grid and the cells
take their repository root from their own location on disk, so a copy is a
grid whose record directories and whose `git status` are the scratch tree's
and never this checkout's. And the stubs are the models: each finds the
report path in the prompt it was handed — the Claude leg on stdin, the Codex
leg as an argument — writes a line to it and exits 0, so eight cells complete
in seconds without a model call. A real grid run is eight reviews and half an
hour; these cases are about what the grid says, not about what a reviewer
finds.

WHAT IS PINNED HERE.

  - A run in which the stray-write check never ran does not read like a clean
    one. The check lives in the cell, which writes its outcome to a stderr
    log; the grid's success path lifts lines out of that log and then deletes
    it. Until nedschorus#167 it lifted only the line naming changed files, so
    a cell whose `git status` could not answer — an index.lock held by
    another agent in the same checkout is the ordinary way — had both of its
    warnings deleted with the log, and the grid's output was byte-identical
    to a run where the detector ran and found nothing. Reproduced by pointing
    GIT_DIR at a directory that does not exist: eight `saved:` lines, and not
    one word saying nothing had been checked.

  - A cell that fell back to a later model in its chain says so on the
    grid's output. Until 2026-08-25 a fallback was recorded only in the
    report's own `fallback_from=` provenance stamp, which nobody sees unless
    they open that file — and the grid deleted the cell's log, so a report
    written by the chain's second model was indistinguishable here from one
    written by the model asked for (user-ruled that day: "I'm ok with the
    fable falling back to opus too. I just don't want it to fail silently").
    The rename commit that added the lift verified it by a hand-run probe;
    this case is that probe, kept.

  - The line that names changed files still reaches the grid's output, and
    the log is still deleted on success. Those are the two halves the fix
    must not trade against each other: lifting more lines is worthless if the
    lift stops happening, and keeping the log would leave eight files in
    every record set for the reviewing agent to sort through.

Run: python3 scripts/cold-read-grid-test.py
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
PROMPTS_DIR = REPO_ROOT / ".claude" / "skills" / "cold-read" / "prompts"
GRID_SCRIPT_NAMES = (
    "cold-read-grid.py",
    "cold-read-cell-common.py",
    "cold-read-claude-cell.py",
    "cold-read-codex-cell.py",
)

TARGET_RELATIVE_PATH = "docs/drafts/cold-read-grid-test-target.md"

# A stand-in for both runtimes. It takes the report path from the prompt it
# was given rather than from the environment, because the grid gives each of
# its eight cells a different one and only the prompt carries which: the
# Claude leg feeds the prompt on stdin, the Codex leg passes it as an
# argument, so the stub reads both and looks for a path under the records
# tree. COLD_READ_GRID_TEST_STUB_EDIT_PATH, when set, is a file to append to
# — a reviewer editing the document instead of reviewing it.
# COLD_READ_GRID_TEST_STUB_FAILING_MODEL, when set, is a model id the stub
# refuses to be: launched as that model it writes nothing and exits 1, which
# is what sends a cell down its chain to the next model.
STUB_MODEL_RUNTIME = r'''#!/usr/bin/env python3
import os, re, sys

prompt = ""
try:
    prompt = sys.stdin.read()
except OSError:
    pass
prompt += " " + " ".join(sys.argv)
failing_model = os.environ.get("COLD_READ_GRID_TEST_STUB_FAILING_MODEL")
if failing_model and failing_model in sys.argv:
    sys.stderr.write("stub runtime: this model is unavailable today\n")
    sys.exit(1)
match = re.search(r"[^\s\"']+cold-read-records/[^\s\"']+\.md", prompt)
if match is None:
    sys.stderr.write("stub runtime: no report path found in the prompt\n")
    sys.exit(3)
with open(match.group(0), "w", encoding="utf-8") as handle:
    handle.write("STUB REVIEW: one restatement\n")
edited_path = os.environ.get("COLD_READ_GRID_TEST_STUB_EDIT_PATH")
if edited_path:
    with open(edited_path, "a", encoding="utf-8") as handle:
        handle.write("The reviewer's own edit, which it should not have made.\n")
sys.exit(0)
'''

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


def build_scratch_repository(scratch, name):
    repository = scratch / name
    (repository / "scripts").mkdir(parents=True)
    for script_name in GRID_SCRIPT_NAMES:
        shutil.copy2(SCRIPTS_DIR / script_name, repository / "scripts" / script_name)
        (repository / "scripts" / script_name).chmod(0o755)
    scratch_prompts = repository / ".claude" / "skills" / "cold-read" / "prompts"
    scratch_prompts.mkdir(parents=True)
    for prompt_path in PROMPTS_DIR.glob("*.md"):
        shutil.copy2(prompt_path, scratch_prompts / prompt_path.name)
    (repository / ".gitignore").write_text("cold-read-records/\n", encoding="utf-8")
    target = repository / TARGET_RELATIVE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# Target\n\nOne committed line.\n", encoding="utf-8")
    git(repository, "init", "-b", "main")
    git(repository, "config", "user.email", "test@test.invalid")
    git(repository, "config", "user.name", "cold-read-grid test")
    git(repository, "add", "-A")
    git(repository, "commit", "-m", "seed")
    return repository


def run_grid(repository, stub_directory, environment_overrides=None):
    stub_directory.mkdir(parents=True, exist_ok=True)
    for runtime_name in ("claude", "codex"):
        stub = stub_directory / runtime_name
        stub.write_text(STUB_MODEL_RUNTIME, encoding="utf-8")
        stub.chmod(0o755)
    environment = dict(os.environ)
    environment["PATH"] = f"{stub_directory}{os.pathsep}{environment.get('PATH', '')}"
    environment.update(environment_overrides or {})
    return subprocess.run(
        [sys.executable, str(repository / "scripts" / "cold-read-grid.py"),
         "--target", TARGET_RELATIVE_PATH],
        capture_output=True, text=True, check=False, env=environment,
    )


def record_directory_of(repository):
    """The record directory the run just made. One per case, by construction."""
    directories = sorted((repository / "cold-read-records").glob("*"))
    return directories[-1] if directories else None


with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch)
    stubs = scratch / "stub-bin"

    # --- The check that could not run ---------------------------------------
    # GIT_DIR points at nothing, so every cell's baseline snapshot fails and
    # every cell says the run was not checked. Before nedschorus#167 the grid
    # deleted all eight of those lines with the logs that carried them.
    repository = build_scratch_repository(scratch, "checkout-detector-unavailable")
    result = run_grid(repository, stubs,
                      {"GIT_DIR": str(scratch / "no-such-git-directory")})
    saved_lines = [line for line in result.stdout.splitlines()
                   if line.startswith("saved:")]
    not_checked_lines = [line for line in result.stdout.splitlines()
                         if "WRITE CHECK DID NOT RUN" in line]
    check("a grid whose cells could not check for stray writes says so",
          not_checked_lines != [],
          f"stdout was {result.stdout!r}")
    check("the lifted line keeps the words that distinguish it from a clean run",
          any("failure to look, not a clean result" in line
              for line in not_checked_lines),
          f"lifted lines were {not_checked_lines!r}")
    check("every cell that could not be checked is named",
          len(not_checked_lines) == 8, f"{len(not_checked_lines)} of 8: {not_checked_lines!r}")
    check("the eight reviews still land and the grid still exits 0",
          result.returncode == 0 and len(saved_lines) == 8,
          f"exit {result.returncode}, {len(saved_lines)} saved; stdout={result.stdout!r}")
    record_directory = record_directory_of(repository)
    check("the stderr logs are still deleted once their lines have been lifted",
          record_directory is not None
          and list(record_directory.glob("*.stderr.log")) == [],
          f"logs left in {record_directory}")

    # --- The check that ran and found something -----------------------------
    # The other half of the same loop, kept honest: the line naming changed
    # files still reaches the grid's output, and it is not confused with the
    # line above it.
    repository = build_scratch_repository(scratch, "checkout-stray-write")
    result = run_grid(
        repository, stubs,
        {"COLD_READ_GRID_TEST_STUB_EDIT_PATH": str(repository / TARGET_RELATIVE_PATH)},
    )
    saved_lines = [line for line in result.stdout.splitlines()
                   if line.startswith("saved:")]
    stray_lines = [line for line in result.stdout.splitlines()
                   if line.startswith("STRAY WRITE:")]
    check("a reviewer that edited the document is reported on the grid's output",
          stray_lines != [], f"stdout was {result.stdout!r}")
    check("the stray-write line names the file that was edited",
          all(TARGET_RELATIVE_PATH in line for line in stray_lines),
          f"lifted lines were {stray_lines!r}")
    check("a run whose check did run is not also reported as unchecked",
          "WRITE CHECK DID NOT RUN" not in result.stdout, repr(result.stdout))
    check("the eight reviews land and the grid exits 0",
          result.returncode == 0 and len(saved_lines) == 8,
          f"exit {result.returncode}, {len(saved_lines)} saved; stdout={result.stdout!r}")
    record_directory = record_directory_of(repository)
    check("the stderr logs are deleted on this path too",
          record_directory is not None
          and list(record_directory.glob("*.stderr.log")) == [],
          f"logs left in {record_directory}")

    # --- A cell that fell back says so ------------------------------------
    # The stub refuses to be claude-opus-5, which leads the Claude good tier.
    # Both good-tier Claude cells therefore fall back to claude-fable-5 and
    # produce their reports under it; the two floor cells and the four Codex
    # cells are untouched, so eight reviews still land.
    repository = build_scratch_repository(scratch, "checkout-fell-back")
    result = run_grid(
        repository, stubs,
        {"COLD_READ_GRID_TEST_STUB_FAILING_MODEL": "claude-opus-5"},
    )
    saved_lines = [line for line in result.stdout.splitlines()
                   if line.startswith("saved:")]
    fell_back_lines = [line for line in result.stdout.splitlines()
                       if line.startswith("FELL BACK:")]
    check("a cell whose first-choice model failed says so on the grid's output",
          fell_back_lines != [], f"stdout was {result.stdout!r}")
    check("both cells of the tier that fell back are named",
          len(fell_back_lines) == 2 and all("claude" in line and "good" in line
                                            for line in fell_back_lines),
          f"lifted lines were {fell_back_lines!r}")
    check("the line names the model that actually wrote the report",
          all("claude-fable-5" in line for line in fell_back_lines),
          f"lifted lines were {fell_back_lines!r}")
    check("a fallback is not a failure: eight reviews still land, grid exits 0",
          result.returncode == 0 and len(saved_lines) == 8,
          f"exit {result.returncode}, {len(saved_lines)} saved; stdout={result.stdout!r}")
    record_directory = record_directory_of(repository)
    check("the stderr logs are deleted once the fallback line has been lifted",
          record_directory is not None
          and list(record_directory.glob("*.stderr.log")) == [],
          f"logs left in {record_directory}")

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
