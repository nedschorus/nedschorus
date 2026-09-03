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
leg as an argument — writes a line to it and exits 0, so four cells complete
in seconds without a model call. A real grid run is four reviews and half an
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

  - The model's echoed words are not the cell's status. The cell re-emits its
    runtime's stderr into the log the grid lifts from, and the Codex CLI
    copies the model's own text onto stderr — so on 2026-09-02 a reviewed
    document that quoted a code comment containing "fell back to" made two
    cells read as fallen back when both had run on the models asked for
    (nedschorus#244). The grid now lifts a phrase only from a line the cell
    program itself began. The case echoes a passage carrying all four lifted
    phrases while one cell really falls back: the real line is lifted, the
    echo is not.

  - The line that names changed files still reaches the grid's output, and
    the log is still deleted on success. Those are the two halves the fix
    must not trade against each other: lifting more lines is worthless if the
    lift stops happening, and keeping the log would leave four files in
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

  - Every file the grid writes into a record directory is named for the run
    (user-ruled 2026-08-25) — `<record directory name>--<runtime>-<pass>-<tier>.md`,
    and `<record directory name>--reference-check.md` for the pre-pass. Before
    that prefix, all eight of a run's reports were named for the cell alone,
    so a report on its own said nothing about which run produced it, and two
    grids running at once in one checkout each held a file of every one of
    those eight names. The cases below assert the prefix on every file in the
    set, so a report that loses it fails here rather than in a record nobody
    can place.

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
# its four cells a different one and only the prompt carries which: the
# Claude leg feeds the prompt on stdin, the Codex leg passes it as an
# argument, so the stub reads both and looks for a path under the records
# tree. COLD_READ_GRID_TEST_STUB_EDIT_PATH, when set, is a file to append to
# — a reviewer editing the document instead of reviewing it.
# COLD_READ_GRID_TEST_STUB_FAILING_MODEL, when set, is a comma-separated list
# of model ids the stub refuses to be: launched as one of them it writes
# nothing and exits 1, which is what sends a cell down its chain to the next
# model. Naming one model makes a cell fall back; naming a cell's whole chain
# makes the cell fail outright, which is the only way this suite can produce a
# failed cell.
# COLD_READ_GRID_TEST_STUB_NEAR_MISS_CHARACTER, when set, is the character the
# stub puts in place of the last one of the record directory's name before
# writing its report there — the 2026-08-25 accident, in which a model created
# a directory one character from the one it was given and wrote a complete
# review into it. The cell's recovery is what puts the report back.
# COLD_READ_GRID_TEST_STUB_ECHO_STDERR_TEXT, when set, is text the stub writes
# to its stderr before doing anything else — the Codex CLI's habit of copying
# the model's own words onto stderr, which the cell re-emits into the log the
# grid reads (nedschorus#244).
STUB_MODEL_RUNTIME = r'''#!/usr/bin/env python3
import os, pathlib, re, sys

echoed_text = os.environ.get("COLD_READ_GRID_TEST_STUB_ECHO_STDERR_TEXT")
if echoed_text:
    sys.stderr.write(echoed_text + "\n")
prompt = ""
try:
    prompt = sys.stdin.read()
except OSError:
    pass
prompt += " " + " ".join(sys.argv)
failing_models = os.environ.get("COLD_READ_GRID_TEST_STUB_FAILING_MODEL", "")
if any(model in sys.argv for model in failing_models.split(",") if model):
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
          len(not_checked_lines) == 4, f"{len(not_checked_lines)} of 4: {not_checked_lines!r}")
    check("the four reviews still land and the grid still exits 0",
          result.returncode == 0 and len(saved_lines) == 4,
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
    # under the reviewers. The run therefore exits 3, not 0 — a set of four
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
    check("the four reviews land, and a target edited under them exits 3",
          result.returncode == 3 and len(saved_lines) == 4,
          f"exit {result.returncode}, {len(saved_lines)} saved; stdout={result.stdout!r}")
    check("the grid says the target changed, on its own output, in one line",
          result.stdout.count("TARGET CHANGED DURING RUN:") == 1, repr(result.stdout))
    check("the line names the window the two fingerprints bound",
          "the moment the cells launched" in result.stdout
          and "the moment the last one finished" in result.stdout, repr(result.stdout))
    # The two fingerprints prove the bytes differed across the window and
    # nothing else. Claiming the edit landed *while* a reviewer was reading, or
    # that every report describes the text as it was before the edit, is false
    # in the ordinary case — an edit part-way through, some cells having opened
    # the file before it and some after. These records are kept, so a marker
    # claiming more than the check knows would outlive the run that wrote it.
    check("the line does not claim to know when in the window the edit landed",
          "while these reviews ran" not in result.stdout, repr(result.stdout))
    check("the line does not claim every report describes the earlier text",
          "reviews the earlier text" not in result.stdout, repr(result.stdout))
    # A moved target and a settled one call for opposite next actions, so the
    # exit-3 path must not close with the instructions to triage the set.
    check("a moved target does not get the closing instructions to triage",
          "All four reviews are complete" not in result.stdout, repr(result.stdout))
    check("a moved target is told to stop editing and run the grid again",
          "Stop editing the document" in result.stdout
          and "Do not triage this set" in result.stdout, repr(result.stdout))
    record_directory = record_directory_of(repository)
    check("the stderr logs are deleted on this path too",
          record_directory is not None
          and list(record_directory.glob("*.stderr.log")) == [],
          f"logs left in {record_directory}")
    # The reports are marked, never deleted: each still records truthfully
    # what one reviewer read, which is evidence. Four cell reports plus the
    # reference-integrity pre-pass.
    reports = sorted(record_directory.glob("*.md"))
    check("every report in the set is still on disk — they are evidence",
          len(reports) == 5, [report.name for report in reports])
    check("every report in the set carries the marker",
          all("<!-- TARGET CHANGED DURING RUN:" in report.read_text(encoding="utf-8")
              for report in reports),
          [report.name for report in reports
           if "<!-- TARGET CHANGED DURING RUN:" not in report.read_text(encoding="utf-8")])
    stamped = record_directory / f"{record_directory.name}--claude-hunt-good.md"
    check("the set holds a report named for both the run and the cell",
          stamped.is_file(), sorted(path.name for path in record_directory.iterdir()))
    # Read once, and survive an absent file: a name this suite got wrong should
    # fail by name above, not end the run in a traceback that takes the
    # remaining cases with it.
    stamped_text = stamped.read_text(encoding="utf-8") if stamped.is_file() else ""
    stamped_lines = stamped_text.split("\n") if stamped_text else ["", ""]
    check("a stamped report keeps its provenance stamp as the first line",
          stamped_lines[0].startswith("<!-- provenance:"), repr(stamped_lines[0]))
    check("the marker goes immediately after the stamp",
          stamped_lines[1].startswith("<!-- TARGET CHANGED DURING RUN:"),
          repr(stamped_lines[1]))
    check("the reviewer's own text survives the marking",
          "STUB REVIEW: one restatement" in stamped_text, repr(stamped_text[:200]))
    # The reference-integrity pre-pass carries no provenance stamp, so its
    # marker goes at the very top.
    unstamped = record_directory / f"{record_directory.name}--reference-check.md"
    check("the reference-integrity pre-pass is named for the run too",
          unstamped.is_file(), sorted(path.name for path in record_directory.iterdir()))
    unstamped_text = unstamped.read_text(encoding="utf-8") if unstamped.is_file() else ""
    unstamped_lines = unstamped_text.split("\n") if unstamped_text else [""]
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
    check("a stray write outside the target is not a failure: four reviews, exit 0",
          result.returncode == 0 and len(saved_lines) == 4,
          f"exit {result.returncode}, {len(saved_lines)} saved; stdout={result.stdout!r}")
    check("a target nobody edited is not reported as changed",
          "TARGET CHANGED DURING RUN" not in result.stdout, repr(result.stdout))
    check("a settled target still gets the closing instructions to triage",
          "All four reviews are complete" in result.stdout
          and "Stop editing the document" not in result.stdout, repr(result.stdout))

    # --- A target that moved while a cell also failed -----------------------
    # The two conditions are independent and land together often enough to
    # write down: the closing text follows the target change (do not triage,
    # run the grid again), so the note naming the failed cells must not send
    # the reader back to a triage that is not happening. The good-tier Claude
    # cell fails outright here — the stub refuses every model in its chain —
    # while the floor and Codex cells save their reports and edit the document
    # under review on the way out.
    repository = build_scratch_repository(scratch, "checkout-changed-and-failed")
    result = run_grid(
        repository, stubs,
        {"COLD_READ_GRID_TEST_STUB_EDIT_PATH": str(repository / TARGET_RELATIVE_PATH),
         "COLD_READ_GRID_TEST_STUB_FAILING_MODEL": "claude-opus-5,claude-fable-5"},
    )
    saved_lines = [line for line in result.stdout.splitlines()
                   if line.startswith("saved:")]
    check("a run can lose a cell and its target at once: three saved, exit 3",
          result.returncode == 3 and len(saved_lines) == 3,
          f"exit {result.returncode}, {len(saved_lines)} saved; stdout={result.stdout!r}")
    # Read the NOTE line itself rather than the whole output: the per-cell
    # STRAY WRITE line also says "before triage", and it is emitted while the
    # cells run, before the grid can know the target moved.
    note_lines = [line for line in result.stdout.splitlines()
                  if line.startswith("NOTE: ")]
    check("the failed cell is still named on the moved-target path",
          note_lines != [] and "1 review(s) failed" in note_lines[0],
          f"note lines were {note_lines!r}")
    check("that note does not send the reader back to triage a short set",
          note_lines != [] and "before triage" not in note_lines[0],
          f"note lines were {note_lines!r}")
    check("that note says why rerunning the failed cells singly would not help",
          note_lines != []
          and "being replaced by a run against the settled document" in note_lines[0],
          f"note lines were {note_lines!r}")

    # --- A cell that fell back says so ------------------------------------
    # The stub refuses to be claude-opus-5, which leads the Claude good tier.
    # The good-tier Claude cell therefore falls back to claude-fable-5 and
    # produces its report under it; the floor cell and the two Codex cells
    # are untouched, so four reviews still land.
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
    check("the cell that fell back is named",
          len(fell_back_lines) == 1 and all("claude" in line and "good" in line
                                            for line in fell_back_lines),
          f"lifted lines were {fell_back_lines!r}")
    check("the line names the model that actually wrote the report",
          all("claude-fable-5" in line for line in fell_back_lines),
          f"lifted lines were {fell_back_lines!r}")
    check("a fallback is not a failure: four reviews still land, grid exits 0",
          result.returncode == 0 and len(saved_lines) == 4,
          f"exit {result.returncode}, {len(saved_lines)} saved; stdout={result.stdout!r}")
    record_directory = record_directory_of(repository)
    check("the stderr logs are deleted once the fallback line has been lifted",
          record_directory is not None
          and list(record_directory.glob("*.stderr.log")) == [],
          f"logs left in {record_directory}")

    # --- The model's echoed words are not the cell's status -----------------
    # The 2026-09-02 false positive (nedschorus#244): the Codex CLI copies the
    # model's text onto stderr, the cell re-emits that stderr into the log the
    # grid reads, and a reviewed document that quoted a comment containing
    # "fell back to" made two cells read as fallen back. Here every runtime
    # echoes a passage carrying all four lifted phrases mid-line, while ONE
    # cell really does fall back, so the case discriminates: the cell's own
    # line is lifted, the echoed passage never is, and nothing else fires.
    echoed_passage = (
        "As the document says: the supervisor fell back to its own default, "
        "then stray writes were not checked for this run, then files outside "
        "its report changed while it ran, and it recovered a near-miss report."
    )
    repository = build_scratch_repository(scratch, "checkout-echoed-phrases")
    result = run_grid(
        repository, stubs,
        {"COLD_READ_GRID_TEST_STUB_ECHO_STDERR_TEXT": echoed_passage,
         "COLD_READ_GRID_TEST_STUB_FAILING_MODEL": "claude-opus-5"},
    )
    saved_lines = [line for line in result.stdout.splitlines()
                   if line.startswith("saved:")]
    fell_back_lines = [line for line in result.stdout.splitlines()
                       if line.startswith("FELL BACK:")]
    check("echoed text carrying the fallback phrase does not read as a fallback: "
          "exactly the one real fallback is lifted",
          len(fell_back_lines) == 1 and "claude-fable-5" in fell_back_lines[0],
          f"lifted lines were {fell_back_lines!r}; stdout={result.stdout!r}")
    check("the real fallback line is the cell's own, not the echo",
          fell_back_lines != [] and "cold-read-claude-cell: fell back to" in fell_back_lines[0]
          and "As the document says" not in fell_back_lines[0],
          f"lifted lines were {fell_back_lines!r}")
    check("echoed text carrying the other three phrases lifts nothing",
          not any(line.startswith(("STRAY WRITE:", "RECOVERED:",
                                   "WRITE CHECK DID NOT RUN:"))
                  for line in result.stdout.splitlines()),
          f"stdout was {result.stdout!r}")
    check("the echo costs nothing: four reviews land, grid exits 0",
          result.returncode == 0 and len(saved_lines) == 4,
          f"exit {result.returncode}, {len(saved_lines)} saved; stdout={result.stdout!r}")

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
          result.returncode == 0 and len(saved_lines) == 4,
          f"exit {result.returncode}, {len(saved_lines)} saved; stdout={result.stdout!r}")
    check("the grid prints RECOVERED: for each cell that recovered a report",
          len(recovered_lines) == 4, f"lifted lines were {recovered_lines!r}")
    # Two directories now: the one the grid made and the one the stubs
    # invented. The grid's is the one holding the reference-integrity
    # pre-pass, which no stub ever writes — the invented one's name differs by
    # a character, so picking either by sort order would be picking by luck.
    record_directories = sorted(
        directory for directory in (repository / "cold-read-records").iterdir()
        if directory.is_dir())
    grid_record_directories = [
        directory for directory in record_directories
        if (directory / f"{directory.name}--reference-check.md").is_file()]
    recovered_record_directory_name = (
        grid_record_directories[0].name if grid_record_directories else "")
    check("the RECOVERED line names the cell it belongs to, run and all",
          any(line.startswith(
              f"RECOVERED: {recovered_record_directory_name}--claude-hunt-good.md")
              for line in recovered_lines),
          f"lifted lines were {recovered_lines!r}")
    check("the recovered reports are back in the directory the grid made",
          len(grid_record_directories) == 1
          and len(list(grid_record_directories[0].glob("*.md"))) == 5,
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
          result.returncode == 0 and len(saved_lines) == 4,
          f"exit {result.returncode}, {len(saved_lines)} saved; stderr={result.stderr!r}")
    check("an accepted run says nothing about a genre suffix",
          "genre suffix" not in result.stderr, repr(result.stderr))

    # --- Every file in the set is named for the run ------------------------
    # A report carried out of its directory, or read beside another run's,
    # still says which run wrote it. That prefix is also what lets a cell's
    # recovery search the whole records tree by exact name.
    record_directories = sorted(
        directory for directory in (repository / "cold-read-records").iterdir()
        if directory.is_dir())
    check("the accepted run left exactly one record directory",
          len(record_directories) == 1,
          [directory.name for directory in record_directories])
    record_directory = record_directories[0]
    written_names = sorted(path.name for path in record_directory.iterdir())
    check("every file the run wrote carries the record directory's name",
          all(name.startswith(f"{record_directory.name}--")
              for name in written_names),
          [name for name in written_names
           if not name.startswith(f"{record_directory.name}--")])
    expected_names = sorted(
        [f"{record_directory.name}--reference-check.md"]
        + [f"{record_directory.name}--{runtime}-{pass_token}-{tier}.md"
           for runtime in ("claude", "codex")
           for pass_token in ("hunt",)
           for tier in ("good", "floor")])
    check("the set holds the four cells plus the reference-integrity pre-pass",
          written_names == expected_names, written_names)

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
