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

  - A cell that recovered a near-miss report says so on the grid's output.
    `RECOVERED:` is lifted out of the cell's log by the same branch that
    deletes that log, so a line not lifted there is a line destroyed on the
    one path that produces it. The case drives the real cells: the stub
    writes each report into a record directory one character from the one it
    was given, exactly as the model did on 2026-08-25, and what is checked is
    that the recovery reaches the reader.

  - A target edited while the reviewers read it compromises the whole set.
    On 2026-08-24 the merge-lane seat had to mark a record set COMPROMISED by
    hand; the only tell was a clean-looking report whose "clean sections"
    quietly omitted the sections that had changed underneath it. The reports
    are kept — they are evidence of what a reviewer read — but every one is
    marked, the grid says so on its output, and the run exits 3.

    A reviewer that edits the document under review trips both signals at
    once, and the stray-write case below is that run: it is reported as a
    stray write AND as a changed target, and the exit code is 3 rather than
    0. The case after it keeps the other path pinned — a reviewer that
    strays into some other file is reported and the run still exits 0, so a
    stray write on its own is a warning and not a failure.

  - An unreviewable target is refused before anything is created. Documents
    whose stem ends in `-log`, `-report` or `-capture` only record what
    happened, and nedschorus#152 takes them out of the review path; the same
    issue rules that the skip be announced rather than silent — "A suffix
    list can miss a genre nobody anticipated; announcing the skip is what
    makes that visible instead of silent." All three suffixes are cased, and
    so is a name ending in none of them, because a check that refused every
    target would pass every refusal case.

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
# COLD_READ_GRID_TEST_STUB_NEAR_MISS_CHARACTER, when set, is the character the
# stub puts in place of the last one of the record directory's name before
# writing its report there — the 2026-08-25 accident, in which a model created
# a directory one character from the one it was given and wrote a complete
# review into it. The cell's recovery is what puts the report back.
STUB_MODEL_RUNTIME = r'''#!/usr/bin/env python3
import os, pathlib, re, sys

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
given = pathlib.Path(match.group(0))
near_miss_character = os.environ.get("COLD_READ_GRID_TEST_STUB_NEAR_MISS_CHARACTER")
if near_miss_character:
    given = (given.parent.parent / (given.parent.name[:-1] + near_miss_character)
             / given.name)
    given.parent.mkdir(parents=True, exist_ok=True)
with open(given, "w", encoding="utf-8") as handle:
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


def write_target(repository, relative_path):
    """A second document in the scratch repository, for a case that needs a
    target of its own name — the genre-suffix cases below turn entirely on
    what the file is called."""
    target = repository / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# Target\n\nOne uncommitted line.\n", encoding="utf-8")
    return target


def run_grid(repository, stub_directory, environment_overrides=None,
             target_relative_path=TARGET_RELATIVE_PATH):
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
         "--target", target_relative_path],
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
    #
    # What the reviewer edits here is the document under review, so this one
    # run trips both guards at once and the two are checked together: the
    # stray write is named, and the target is reported as having changed
    # under the reviewers. The run therefore exits 3, not 0 — a set of eight
    # reports describing text that no longer exists is the condition a caller
    # most needs to branch on, and it outranks the fact that every cell
    # succeeded. The case after this one keeps the plain stray-write path
    # pinned at exit 0.
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
    check("the eight reviews land, and a target edited under them exits 3",
          result.returncode == 3 and len(saved_lines) == 8,
          f"exit {result.returncode}, {len(saved_lines)} saved; stdout={result.stdout!r}")
    check("the grid says the target changed, on its own output, in one line",
          result.stdout.count("TARGET CHANGED DURING RUN:") == 1, repr(result.stdout))
    check("the line names both fingerprints",
          "when the cells launched" in result.stdout
          and "when the last one finished" in result.stdout, repr(result.stdout))
    record_directory = record_directory_of(repository)
    check("the stderr logs are deleted on this path too",
          record_directory is not None
          and list(record_directory.glob("*.stderr.log")) == [],
          f"logs left in {record_directory}")
    # The reports are marked, never deleted: each still records truthfully
    # what one reviewer read, which is evidence. Eight cell reports plus the
    # reference-integrity pre-pass.
    reports = sorted(record_directory.glob("*.md"))
    check("every report in the set is still on disk — they are evidence",
          len(reports) == 9, [report.name for report in reports])
    check("every report in the set carries the marker",
          all("<!-- TARGET CHANGED DURING RUN:" in report.read_text(encoding="utf-8")
              for report in reports),
          [report.name for report in reports
           if "<!-- TARGET CHANGED DURING RUN:" not in report.read_text(encoding="utf-8")])
    stamped_lines = (record_directory / "claude-restate-good.md").read_text(
        encoding="utf-8").split("\n")
    check("a stamped report keeps its provenance stamp as the first line",
          stamped_lines[0].startswith("<!-- provenance:"), repr(stamped_lines[0]))
    check("the marker goes immediately after the stamp",
          stamped_lines[1].startswith("<!-- TARGET CHANGED DURING RUN:"),
          repr(stamped_lines[1]))
    check("the reviewer's own text survives the marking",
          "STUB REVIEW: one restatement" in "\n".join(stamped_lines),
          repr(stamped_lines[:4]))
    # The reference-integrity pre-pass carries no provenance stamp, so its
    # marker goes at the very top.
    unstamped_lines = (record_directory / "reference-check.md").read_text(
        encoding="utf-8").split("\n")
    check("a report with no stamp takes the marker at the top",
          unstamped_lines[0].startswith("<!-- TARGET CHANGED DURING RUN:"),
          repr(unstamped_lines[0]))

    # --- A stray write that is not a target change --------------------------
    # A reviewer that writes somewhere other than the document under review is
    # reported and the run still exits 0: a stray write is cleanup for the
    # reviewing agent, not a failed run. Without this case the exit-0
    # stray-write path would have no pin at all, because the case above now
    # ends at 3.
    repository = build_scratch_repository(scratch, "checkout-stray-write-elsewhere")
    stray_relative_path = "docs/drafts/cold-read-grid-test-stray.md"
    result = run_grid(
        repository, stubs,
        {"COLD_READ_GRID_TEST_STUB_EDIT_PATH": str(repository / stray_relative_path)},
    )
    saved_lines = [line for line in result.stdout.splitlines()
                   if line.startswith("saved:")]
    stray_lines = [line for line in result.stdout.splitlines()
                   if line.startswith("STRAY WRITE:")]
    check("a reviewer that strayed into another file is reported too",
          stray_lines != [] and all(stray_relative_path in line for line in stray_lines),
          f"lifted lines were {stray_lines!r}")
    check("a stray write outside the target is not a failure: eight reviews, exit 0",
          result.returncode == 0 and len(saved_lines) == 8,
          f"exit {result.returncode}, {len(saved_lines)} saved; stdout={result.stdout!r}")
    check("a target nobody edited is not reported as changed",
          "TARGET CHANGED DURING RUN" not in result.stdout, repr(result.stdout))

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

    # --- A cell that recovered a near-miss says so -------------------------
    # The 2026-08-25 accident, driven through the real cells: every stub
    # writes its report into a record directory one character from the one it
    # was given, having created that directory itself, and each cell's
    # recovery moves it back. What is pinned here is the reader's end of it —
    # `RECOVERED:` is lifted by the same branch that deletes the cell's log,
    # so a line not lifted there is a line nobody can ever read.
    repository = build_scratch_repository(scratch, "checkout-recovered")
    result = run_grid(
        repository, stubs,
        {"COLD_READ_GRID_TEST_STUB_NEAR_MISS_CHARACTER": "X"},
    )
    saved_lines = [line for line in result.stdout.splitlines()
                   if line.startswith("saved:")]
    recovered_lines = [line for line in result.stdout.splitlines()
                       if line.startswith("RECOVERED:")]
    check("a run whose cells recovered a near-miss still succeeds",
          result.returncode == 0 and len(saved_lines) == 8,
          f"exit {result.returncode}, {len(saved_lines)} saved; stdout={result.stdout!r}")
    check("the grid prints RECOVERED: for each cell that recovered a report",
          len(recovered_lines) == 8, f"lifted lines were {recovered_lines!r}")
    check("the RECOVERED line names the cell it belongs to",
          any(line.startswith("RECOVERED: claude-restate-good.md")
              for line in recovered_lines),
          f"lifted lines were {recovered_lines!r}")
    # Two directories now: the one the grid made and the one the stubs
    # invented. The grid's is the one holding the reference-integrity
    # pre-pass, which no stub ever writes.
    record_directories = sorted(
        directory for directory in (repository / "cold-read-records").iterdir()
        if directory.is_dir())
    grid_record_directories = [directory for directory in record_directories
                               if (directory / "reference-check.md").is_file()]
    check("the recovered reports are back in the directory the grid made",
          len(grid_record_directories) == 1
          and len(list(grid_record_directories[0].glob("*.md"))) == 9,
          [directory.name for directory in record_directories])
    check("the reports are moved out of the mistyped directory, not copied",
          all(list(directory.glob("*.md")) == [] for directory in record_directories
              if directory not in grid_record_directories),
          "two directories hold one review each, which is the ambiguity "
          "recovery exists to remove")
    check("the stderr logs are deleted once the recovery line has been lifted",
          grid_record_directories != []
          and list(grid_record_directories[0].glob("*.stderr.log")) == [],
          f"logs left in {grid_record_directories}")

    # --- The target this instrument will not review ------------------------
    # nedschorus#152 takes a `-log`, `-report` or `-capture` out of the review
    # path: those documents only record what happened, and the rulings they
    # carry are content rather than defects. The refusal comes before the
    # record directory is created and before any reviewer is launched, so
    # these cases never wait on the grid's polling loop.
    repository = build_scratch_repository(scratch, "checkout-genre-suffix")
    for genre_suffix in ("-log", "-report", "-capture"):
        genre_relative_path = f"docs/drafts/the-thing-that-happened{genre_suffix}.md"
        write_target(repository, genre_relative_path)
        result = run_grid(repository, stubs,
                          target_relative_path=genre_relative_path)
        check(f"a `{genre_suffix}` target is refused with exit 2",
              result.returncode == 2,
              f"exit {result.returncode}; stderr={result.stderr!r}")
        check(f"the `{genre_suffix}` refusal names the suffix that fired",
              f"`{genre_suffix}`" in result.stderr, repr(result.stderr))
        check(f"the `{genre_suffix}` refusal names the issue that rules it",
              "nedschorus#152" in result.stderr, repr(result.stderr))
        check(f"a `{genre_suffix}` refusal creates no record directory",
              not (repository / "cold-read-records").exists(),
              "the refusal ran after the record directory was made")

    # The other half of the check: a name ending in none of the suffixes is
    # not refused. Without this case a check that refused every target would
    # pass every case above.
    result = run_grid(repository, stubs)
    saved_lines = [line for line in result.stdout.splitlines()
                   if line.startswith("saved:")]
    check("a name ending in no genre suffix is not refused",
          result.returncode == 0 and len(saved_lines) == 8,
          f"exit {result.returncode}, {len(saved_lines)} saved; stderr={result.stderr!r}")
    check("an accepted run says nothing about a genre suffix",
          "genre suffix" not in result.stderr, repr(result.stderr))

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
