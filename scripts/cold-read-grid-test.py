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
leg as an argument — writes a line to it and exits 0, so six cells complete
in seconds without a model call. A real grid run is six reviews and half an
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

  - A failed cell is retried once, with the same model, and no cell is
    special (user-ruled 2026-09-11; the design is
    docs/issues/413-cold-read-grid-cell-failure-handling-design.md, whose
    section 8 lists the cases below). The first failure prints RETRYING:
    with the attempt's cause and keeps the attempt-1 log; a retry that
    lands prints saved: and its log is deleted; a retry that fails prints
    FAILED (exit N): with the second attempt's cause, keeps both logs, and
    the report is absent. Every run closes with ONE closing text in four
    variants built from what landed -- all landed, some landed (the set is
    valid and incomplete, and is triaged), none landed, or the target
    changed -- replacing the Opus-absent and Fable-only branches of
    2026-09-04 ("why is opus special? I don't think it should be"). Absent
    reports are listed with their causes, every .md file in the record is
    marked INCOMPLETE SET, an agent-cli whose every cell is absent for one
    agent-cli-wide cause gets one AGENT-CLI DOWN: line, and a cause the user
    can clear ends the text with "Tell the user:". A cause changes what is
    reported, never what is decided: the cases below drive the stub through
    the real limit texts and check that the retry, the closing text and the
    exit code are the same whatever the cause said. The grid's FELL BACK
    line (2026-08-25, "I just don't want it to fail silently") has no
    positive control through the grid since no pinned chain has a second
    model; the lift machinery stays.

  - The read is six cells: the defect-hunt pass on both tiers of both
    runtimes, and the terminology pass (user-ruled 2026-09-05) on the good
    tier of both. The terminology cells run at the effort the grid pins,
    which the stub reads off its own command line.

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

  - Every file the grid writes into a record directory is a bare role name
    (user-ruled 2026-09-18) — `<runtime>-<pass>-<tier>.md` for a report and
    `reference-check.md` for the pre-pass; the directory's name says which
    read. From 2026-09-15 to 2026-09-18 every file carried the record's name
    as a prefix, added because two cold-read runs going at once in one
    checkout each held a file of every one of those names and a cell's
    near-miss recovery could take the other run's; that case is now met in
    the recovery itself (scripts/cold-read-cell-common-test.py pins it). The
    cases below assert the bare names on every file in the set.

  - A record directory is named `<file stem>-<YYYY-MM-DD>`, or
    `SKILL-<skill name>-<YYYY-MM-DD>` for a skill (user-ruled 2026-09-18,
    reversing the date-first order of 2026-09-16), and a second run of the
    same document on the same day takes -2. The name function is handed a
    clock reading in-process, and every grid run here is given
    COLD_READ_RECORD_CLOCK_OVERRIDE, so no case reads the wall clock.

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

import datetime
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
PROMPTS_DIR = REPO_ROOT / ".claude" / "skills" / "cold-read" / "prompts"
GRID_SCRIPT_NAMES = (
    "cold-read-grid.py",
    "cold-read-cell-common.py",
    "cold-read-claude-cell.py",
    "cold-read-codex-cell.py",
    "cold-read-record-ship.py",
)
# Every run here ships its record to a scratch log-store inside the scratch
# repository, through the shipper's destination override, so no case reaches
# ned-box; the store is real, the copy is the real rsync. A case that wants the
# shipping to fail overrides the override with an unreachable host.
RECORD_SHIP_DESTINATION_VARIABLE = "COLD_READ_RECORD_SHIP_DESTINATION"
SCRATCH_LOG_STORE_RELATIVE = Path("log-store") / "cold-read-records"
# Every run here is given this clock instead of the wall clock, through the
# grid's override; a case that needs another minute overrides it in turn.
RECORD_CLOCK_OVERRIDE_VARIABLE = "COLD_READ_RECORD_CLOCK_OVERRIDE"
FIXED_RECORD_CLOCK_FOR_TESTS = "2026-09-16T10:42"

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
# makes the cell fail outright. Since the second pass, one model serves two
# cells (Opus is the good Claude cell of both passes), so
# COLD_READ_GRID_TEST_STUB_FAILING_REPORT_NAME_FRAGMENT, when set, fails
# exactly the cells whose report name contains it -- the way to fail one
# pass's cell and not the other's.
# COLD_READ_GRID_TEST_STUB_EFFORT_LOG, when set, is a file the stub appends
# one line to per launch: the report name it found and the effort on its
# command line, so a case can check what effort each cell was launched at.
# COLD_READ_GRID_TEST_STUB_NEAR_MISS_CHARACTER, when set, is the character the
# stub puts in place of the last one of the record directory's name before
# writing its report there — the 2026-08-25 accident, in which a model created
# a directory one character from the one it was given and wrote a complete
# review into it. The cell's recovery is what puts the report back.
# COLD_READ_GRID_TEST_STUB_ECHO_STDERR_TEXT, when set, is text the stub writes
# to its stderr before doing anything else — the Codex CLI's habit of copying
# the model's own words onto stderr, which the cell re-emits into the log the
# grid reads (nedschorus#244).
# COLD_READ_GRID_TEST_STUB_ATTEMPT_COUNTER_DIRECTORY is a directory outside
# the scratch repository (inside it, the counter file would be a stray write)
# where the stub counts its launches per report name, which is how it knows
# whether it is a cell's first attempt or its retry: the grid launches the
# same command twice and the stub keeps no other state.
# COLD_READ_GRID_TEST_STUB_FAILURE_PLAN, when set, is a JSON list of entries
# {"fragment", "attempts", "stdout", "stdout_by_attempt", "edit"}: a cell
# whose report name contains "fragment" (the first matching entry wins)
# writes nothing and exits 1 on its first "attempts" launches, printing
# "stdout" on stdout first -- the real limit texts of the cases below, with
# `{family}` standing for the model's family name (Opus, Fable), as the
# `claude` agent-cli's model-limit message names it -- or the attempt's own
# text from "stdout_by_attempt" ({"2": ...}), and appending to the file
# "edit" before failing, for a stray write by a failed first attempt.
STUB_MODEL_RUNTIME = r'''#!/usr/bin/env python3
import json, os, pathlib, re, sys

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
failing_fragment = os.environ.get("COLD_READ_GRID_TEST_STUB_FAILING_REPORT_NAME_FRAGMENT")
if failing_fragment and failing_fragment in given.name:
    sys.stderr.write("stub runtime: this cell is refused by report name\n")
    sys.exit(1)
attempt = 1
counter_directory = os.environ.get("COLD_READ_GRID_TEST_STUB_ATTEMPT_COUNTER_DIRECTORY")
if counter_directory:
    counter = pathlib.Path(counter_directory) / given.name
    counter.parent.mkdir(parents=True, exist_ok=True)
    attempt = len(counter.read_text().splitlines()) + 1 if counter.is_file() else 1
    with open(counter, "a", encoding="utf-8") as handle:
        handle.write(f"attempt {attempt}\n")
model = ""
for flag in ("--model", "-m"):
    if flag in sys.argv:
        model = sys.argv[sys.argv.index(flag) + 1]
family = model.split("-")[1].capitalize() if model.count("-") else model
for entry in json.loads(os.environ.get("COLD_READ_GRID_TEST_STUB_FAILURE_PLAN") or "[]"):
    if entry["fragment"] not in given.name:
        continue
    if attempt <= entry.get("attempts", 1):
        text = entry.get("stdout_by_attempt", {}).get(str(attempt), entry.get("stdout", ""))
        if text:
            sys.stdout.write(text.replace("{family}", family) + "\n")
        if entry.get("edit"):
            with open(entry["edit"], "a", encoding="utf-8") as handle:
                handle.write("The reviewer's own edit on a failed attempt.\n")
        sys.stderr.write(f"stub runtime: attempt {attempt} of this cell fails by plan\n")
        sys.exit(1)
    break
effort_log = os.environ.get("COLD_READ_GRID_TEST_STUB_EFFORT_LOG")
if effort_log:
    effort = ""
    for index, argument in enumerate(sys.argv):
        if argument == "--effort" and index + 1 < len(sys.argv):
            effort = sys.argv[index + 1]
        elif argument.startswith("model_reasoning_effort="):
            effort = argument.split("=", 1)[1]
    with open(effort_log, "a", encoding="utf-8") as handle:
        handle.write(f"{given.name} {effort}\n")
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
    environment[RECORD_SHIP_DESTINATION_VARIABLE] = str(repository / SCRATCH_LOG_STORE_RELATIVE)
    environment[RECORD_CLOCK_OVERRIDE_VARIABLE] = FIXED_RECORD_CLOCK_FOR_TESTS
    environment["COLD_READ_GRID_TEST_STUB_ATTEMPT_COUNTER_DIRECTORY"] = str(
        repository.parent / "stub-attempt-counts" / repository.name / str(time.time_ns()))
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
          len(not_checked_lines) == 6, f"{len(not_checked_lines)} of 6: {not_checked_lines!r}")
    check("the six reviews still land and the grid still exits 0",
          result.returncode == 0 and len(saved_lines) == 6,
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
    # under the reviewers. The run therefore exits 3, not 0 — a set of six
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
    check("the six reviews land, and a target edited under them exits 3",
          result.returncode == 3 and len(saved_lines) == 6,
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
          "All six reports landed" not in result.stdout, repr(result.stdout))
    check("a moved target is told to stop editing and start a new cold-read run",
          "Stop editing the document" in result.stdout
          and "Do not triage this set" in result.stdout
          and "start a new cold-read run" in result.stdout, repr(result.stdout))
    record_directory = record_directory_of(repository)
    check("the stderr logs are deleted on this path too",
          record_directory is not None
          and list(record_directory.glob("*.stderr.log")) == [],
          f"logs left in {record_directory}")
    # The reports are marked, never deleted: each still records truthfully
    # what one reviewer read, which is evidence. Six cell reports plus the
    # reference-integrity pre-pass.
    reports = sorted(record_directory.glob("*.md"))
    check("every report in the set is still on disk — they are evidence",
          len(reports) == 7, [report.name for report in reports])
    check("every report in the set carries the marker",
          all("<!-- TARGET CHANGED DURING RUN:" in report.read_text(encoding="utf-8")
              for report in reports),
          [report.name for report in reports
           if "<!-- TARGET CHANGED DURING RUN:" not in report.read_text(encoding="utf-8")])
    stamped = record_directory / "claude-hunt-good.md"
    check("the set holds a report named for the cell",
          stamped.is_file(), sorted(path.name for path in record_directory.iterdir()))
    # Read once, and survive an absent file: a name this suite got wrong should
    # fail by name above, not end the run in a traceback that takes the
    # remaining cases with it.
    stamped_text = stamped.read_text(encoding="utf-8") if stamped.is_file() else ""
    stamped_lines = stamped_text.split("\n") if stamped_text else ["", ""]
    check("a stamped report keeps its provenance stamp as the first line",
          stamped_lines[0].startswith("<!-- provenance:"), repr(stamped_lines[0]))
    check("the marker goes immediately after the stamp",
          stamped_lines[1].startswith("<!-- TARGET CHANGED DURING RUN:")
          and "start a new cold-read run" in stamped_lines[1]
          and "re-run the grid" not in stamped_lines[1],
          repr(stamped_lines[1]))
    check("the reviewer's own text survives the marking",
          "STUB REVIEW: one restatement" in stamped_text, repr(stamped_text[:200]))
    # The reference-integrity pre-pass carries no provenance stamp, so its
    # marker goes at the very top.
    unstamped = record_directory / "reference-check.md"
    check("the reference-integrity pre-pass is named reference-check.md",
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
    check("a stray write outside the target is not a failure: six reviews, exit 0",
          result.returncode == 0 and len(saved_lines) == 6,
          f"exit {result.returncode}, {len(saved_lines)} saved; stdout={result.stdout!r}")
    check("a target nobody edited is not reported as changed",
          "TARGET CHANGED DURING RUN" not in result.stdout, repr(result.stdout))
    check("a settled target still gets the closing instructions to triage",
          "All six reports landed" in result.stdout
          and "Stop editing the document" not in result.stdout, repr(result.stdout))
    # Line breaks collapsed first: the closing text is wrapped, and a check
    # that missed the sentence because of where its line ended would fail for
    # the wrong reason.
    closing_text = " ".join(result.stdout.split())
    check("the closing text says what the terminology reports are and how to triage them",
          "The terminology reports list the document's key-terms that fail one of "
          "five criteria, with the criteria numbers per item and a closing counts "
          "line; triage them the same way as the defect-hunt reports." in closing_text,
          repr(result.stdout))

    # --- Every failure case below, in the design's terms ---------------------
    # docs/issues/413-cold-read-grid-cell-failure-handling-design.md, section
    # 8. The real limit texts (section 4) are the fixtures: line 2 of the two
    # kept logs it cites, and the 2026-09-18 logged-out capture on ned-box.
    SESSION_LIMIT_LINE = "You've hit your session limit · resets 8:50pm (America/Los_Angeles)"
    MODEL_LIMIT_LINE = ("You've reached your {family} limit. Switch to another model, or "
                        "manage usage credits at claude.ai/settings/usage?from=cc_cli_limit_message, "
                        "to continue.")

    def lines_opening(result, prefix):
        return [line for line in result.stdout.splitlines() if line.startswith(prefix)]

    def markers_in(record_directory, prefix):
        """The .md files of the set carrying a marker that opens `prefix`."""
        return [path.name for path in sorted(record_directory.glob("*.md"))
                if any(line.startswith(prefix)
                       for line in path.read_text(encoding="utf-8").split("\n"))]

    # --- A cell fails once and lands on retry --------------------------------
    repository = build_scratch_repository(scratch, "checkout-retry-lands")
    result = run_grid(repository, stubs, {"COLD_READ_GRID_TEST_STUB_FAILURE_PLAN": json.dumps(
        [{"fragment": "claude-hunt-floor.md", "attempts": 1}])})
    saved_lines = lines_opening(result, "saved:")
    retrying_lines = lines_opening(result, "RETRYING:")
    check("a first failure prints RETRYING: naming the cell and its cause",
          len(retrying_lines) == 1
          and retrying_lines[0].startswith("RETRYING: claude-hunt-floor — exit-1 — ")
          and "first attempt's log kept:" in retrying_lines[0],
          f"stdout was {result.stdout!r}")
    check("the retry lands: six saved, no FAILED line, the all-landed text, exit 0",
          result.returncode == 0 and len(saved_lines) == 6
          and lines_opening(result, "FAILED") == []
          and "All six reports landed" in result.stdout,
          f"exit {result.returncode}, {len(saved_lines)} saved; stdout={result.stdout!r}")
    record_directory = record_directory_of(repository)
    check("the attempt-1 log is kept and the attempt-2 log is deleted with the landed cells'",
          sorted(path.name for path in record_directory.glob("*.stderr.log"))
          == ["claude-hunt-floor.md.attempt-1.stderr.log"],
          sorted(path.name for path in record_directory.glob("*.stderr.log")))
    check("a set with no absent report carries no INCOMPLETE SET marker",
          markers_in(record_directory, "<!-- INCOMPLETE SET:") == [])

    # --- A failed first attempt's stray write is still reported ---------------
    # The retry takes its own baseline after the first attempt's write, so
    # the line has to be lifted from the first attempt's log before relaunch.
    repository = build_scratch_repository(scratch, "checkout-stray-write-on-failed-attempt")
    stray_relative_path = "docs/drafts/cold-read-grid-test-stray.md"
    result = run_grid(repository, stubs, {"COLD_READ_GRID_TEST_STUB_FAILURE_PLAN": json.dumps(
        [{"fragment": "codex-hunt-good.md", "attempts": 1,
          "edit": str(repository / stray_relative_path)}])})
    stray_lines = lines_opening(result, "STRAY WRITE:")
    check("a stray write by a failed first attempt reaches the grid's output",
          stray_lines != [] and all(stray_relative_path in line for line in stray_lines),
          f"stdout was {result.stdout!r}")
    check("the stray line comes before the RETRYING line, from the attempt that wrote it",
          result.stdout.index("STRAY WRITE:") < result.stdout.index("RETRYING:"),
          repr(result.stdout))
    check("that run still lands six and exits 0",
          result.returncode == 0 and len(lines_opening(result, "saved:")) == 6,
          f"exit {result.returncode}; stdout={result.stdout!r}")

    # --- A cell fails both attempts: absent, the some-landed text, the marker -
    repository = build_scratch_repository(scratch, "checkout-one-cell-absent")
    result = run_grid(repository, stubs, {"COLD_READ_GRID_TEST_STUB_FAILURE_PLAN": json.dumps(
        [{"fragment": "claude-terminology-good.md", "attempts": 2}])})
    failed_lines = lines_opening(result, "FAILED")
    check("RETRYING: then FAILED (exit 1) with the second attempt's cause",
          len(lines_opening(result, "RETRYING:")) == 1 and len(failed_lines) == 1
          and failed_lines[0].startswith("FAILED (exit 1): claude-terminology-good — exit-1 — ")
          and "attempt-2.stderr.log" in failed_lines[0],
          f"stdout was {result.stdout!r}")
    check("five land and the grid exits 1",
          result.returncode == 1 and len(lines_opening(result, "saved:")) == 5,
          f"exit {result.returncode}; stdout={result.stdout!r}")
    check("the some-landed text: valid and incomplete, triage what landed",
          "5 of 6 reports landed in" in result.stdout
          and "The set is valid and incomplete: triage the reports that landed." in result.stdout
          and "All six reports landed" not in result.stdout
          and "Stop here" not in result.stdout and "Wait for Opus" not in result.stdout,
          repr(result.stdout))
    check("the absent report is listed with its cause and its attempt-2 log",
          any(line.startswith("- claude-terminology-good: exit-1 — ")
              and line.endswith("claude-terminology-good.md.attempt-2.stderr.log)")
              for line in result.stdout.splitlines()),
          repr(result.stdout))
    closing_text = " ".join(result.stdout.split())
    check("the triage instructions read to every report that landed and record the absence",
          "until you have read every report that landed" in closing_text
          and "Record each absent report and its cause in triage.md." in closing_text
          and "read all six" not in closing_text, repr(result.stdout))
    check("an exit-N cause is not one the user can clear: no Tell the user sentence, no AGENT-CLI DOWN",
          "Tell the user:" not in result.stdout and "AGENT-CLI DOWN:" not in result.stdout,
          repr(result.stdout))
    record_directory = record_directory_of(repository)
    check("the INCOMPLETE SET marker is in all six .md files of the record",
          len(markers_in(record_directory, "<!-- INCOMPLETE SET: 1 of 6 reports absent — "
                                            "claude-terminology-good (exit-1 — ")) == 6,
          markers_in(record_directory, "<!-- INCOMPLETE SET:"))
    stamped = (record_directory / "claude-hunt-good.md").read_text(encoding="utf-8").split("\n")
    check("the marker goes after the provenance stamp",
          stamped[0].startswith("<!-- provenance:") and stamped[1].startswith("<!-- INCOMPLETE SET:"),
          repr(stamped[:2]))
    check("both attempts' logs of the absent cell are kept, the landed cells' deleted",
          sorted(path.name for path in record_directory.glob("*.stderr.log"))
          == ["claude-terminology-good.md.attempt-1.stderr.log",
              "claude-terminology-good.md.attempt-2.stderr.log"],
          sorted(path.name for path in record_directory.glob("*.stderr.log")))

    # --- All three Claude cells fail both attempts with the account limit ----
    # The 2026-09-10 outage, eight records of three unrelated FAILED lines.
    repository = build_scratch_repository(scratch, "checkout-claude-down")
    result = run_grid(repository, stubs, {"COLD_READ_GRID_TEST_STUB_FAILURE_PLAN": json.dumps(
        [{"fragment": "claude-", "attempts": 2, "stdout": SESSION_LIMIT_LINE}])})
    down_lines = lines_opening(result, "AGENT-CLI DOWN:")
    check("one AGENT-CLI DOWN line, naming claude, the class and the reset text",
          down_lines == ["AGENT-CLI DOWN: claude — account-limit — resets 8:50pm "
                         "(America/Los_Angeles); 3 reports absent"],
          f"down lines were {down_lines!r}; stdout={result.stdout!r}")
    check("every RETRYING and FAILED line names account-limit with the reset text",
          len(lines_opening(result, "RETRYING:")) == 3
          and all("account-limit — resets 8:50pm (America/Los_Angeles)" in line
                  for line in lines_opening(result, "RETRYING:") + lines_opening(result, "FAILED")),
          repr(result.stdout))
    check("the closing text restates the down line without the prefix, once",
          result.stdout.count("- claude is down: account-limit — resets 8:50pm "
                              "(America/Los_Angeles); 3 reports absent") == 1
          and result.stdout.count("AGENT-CLI DOWN:") == 1, repr(result.stdout))
    check("the closing text ends by telling the user the cause, with the log to check",
          result.stdout.rstrip().splitlines()[-1].startswith(
              "Tell the user: claude account-limit — resets 8:50pm (America/Los_Angeles) (log: ")
          and result.stdout.rstrip().endswith("attempt-2.stderr.log)."),
          repr(result.stdout.rstrip().splitlines()[-1]))
    check("three land, the some-landed text, exit 1",
          result.returncode == 1 and len(lines_opening(result, "saved:")) == 3
          and "3 of 6 reports landed in" in result.stdout,
          f"exit {result.returncode}; stdout={result.stdout!r}")

    # --- Two Claude cells hit the account limit after the third landed -------
    # The rule as the user revised it at item 3 of the design's walk
    # (2026-09-16): the down line prints when a cell becomes absent with an
    # agent-cli-wide class and every other cell of its agent-cli has either
    # LANDED or is absent with the same class -- a report that landed before
    # the limit hit does not stop the agent-cli from being reported down.
    repository = build_scratch_repository(scratch, "checkout-claude-down-after-one-landed")
    result = run_grid(repository, stubs, {"COLD_READ_GRID_TEST_STUB_FAILURE_PLAN": json.dumps(
        [{"fragment": "claude-hunt-floor.md", "attempts": 0},
         {"fragment": "claude-", "attempts": 2, "stdout": SESSION_LIMIT_LINE}])})
    check("one landed Claude cell and two absent with the account limit is still claude down",
          lines_opening(result, "AGENT-CLI DOWN:")
          == ["AGENT-CLI DOWN: claude — account-limit — resets 8:50pm "
              "(America/Los_Angeles); 2 reports absent"]
          and "- claude is down: account-limit — resets 8:50pm (America/Los_Angeles); 2 reports absent"
          in result.stdout
          and result.returncode == 1 and len(lines_opening(result, "saved:")) == 4,
          f"exit {result.returncode}; stdout={result.stdout!r}")

    # --- All three Claude cells fail with a model limit: no agent-cli is down --
    repository = build_scratch_repository(scratch, "checkout-model-limits")
    result = run_grid(repository, stubs, {"COLD_READ_GRID_TEST_STUB_FAILURE_PLAN": json.dumps(
        [{"fragment": "claude-", "attempts": 2, "stdout": MODEL_LIMIT_LINE}])})
    check("a model limit on every Claude cell is three absences, not an agent-cli down",
          "AGENT-CLI DOWN:" not in result.stdout and "is down:" not in result.stdout
          and len(lines_opening(result, "- claude-")) == 3, repr(result.stdout))
    check("each absence names model-limit and the model's family",
          any(line.startswith("- claude-hunt-good: model-limit — Opus (log:")
              for line in result.stdout.splitlines())
          and any(line.startswith("- claude-hunt-floor: model-limit — Fable (log:")
                  for line in result.stdout.splitlines()), repr(result.stdout))
    check("the user is told, one cause per agent-cli and class",
          result.stdout.count("Tell the user: claude model-limit — ") == 1, repr(result.stdout))

    # --- First attempts all account-limit; one retry fails otherwise ---------
    repository = build_scratch_repository(scratch, "checkout-mixed-causes")
    result = run_grid(repository, stubs, {"COLD_READ_GRID_TEST_STUB_FAILURE_PLAN": json.dumps(
        [{"fragment": "claude-hunt-floor.md", "attempts": 2,
          "stdout_by_attempt": {"1": SESSION_LIMIT_LINE, "2": ""}},
         {"fragment": "claude-", "attempts": 2, "stdout": SESSION_LIMIT_LINE}])})
    retrying_lines = lines_opening(result, "RETRYING:")
    check("three RETRYING lines name account-limit",
          len(retrying_lines) == 3 and all("account-limit" in line for line in retrying_lines),
          repr(retrying_lines))
    check("the retry that failed otherwise is FAILED as exit-1, the others as account-limit",
          any(line.startswith("FAILED (exit 1): claude-hunt-floor — exit-1 — ")
              for line in lines_opening(result, "FAILED"))
          and sum("account-limit" in line for line in lines_opening(result, "FAILED")) == 2,
          repr(lines_opening(result, "FAILED")))
    check("differing causes on one agent-cli are three facts, not one down line",
          "AGENT-CLI DOWN:" not in result.stdout, repr(result.stdout))

    # --- Three Codex cells fail both attempts with exit-N ----------------------
    repository = build_scratch_repository(scratch, "checkout-codex-exits")
    result = run_grid(repository, stubs, {"COLD_READ_GRID_TEST_STUB_FAILURE_PLAN": json.dumps(
        [{"fragment": "codex-", "attempts": 2}])})
    check("three exit-1 absences on codex: listed one by one, no down line, no Tell the user",
          result.returncode == 1 and len(lines_opening(result, "- codex-")) == 3
          and all("exit-1 — " in line for line in lines_opening(result, "- codex-"))
          and "AGENT-CLI DOWN:" not in result.stdout and "Tell the user:" not in result.stdout,
          repr(result.stdout))

    # --- All six fail both attempts: the none-landed text ---------------------
    repository = build_scratch_repository(scratch, "checkout-none-landed")
    result = run_grid(repository, stubs, {"COLD_READ_GRID_TEST_STUB_FAILURE_PLAN": json.dumps(
        [{"fragment": "-", "attempts": 2}])})
    check("no report landed: the none-landed text, six absences, exit 1",
          result.returncode == 1 and lines_opening(result, "saved:") == []
          and "No report landed in" in result.stdout
          and "so there is nothing to triage." in result.stdout
          and len(lines_opening(result, "- ")) == 6
          and "Start a new cold-read-full-run once the causes above that the user can "
              "clear are cleared, or at once if none of them is." in result.stdout
          and "Read every report in full" not in result.stdout,
          f"exit {result.returncode}; stdout={result.stdout!r}")
    record_directory = record_directory_of(repository)
    check("the marker still goes into the reference-check file, the set's one .md",
          markers_in(record_directory, "<!-- INCOMPLETE SET: 6 of 6 reports absent") == ["reference-check.md"],
          markers_in(record_directory, "<!-- INCOMPLETE SET:"))

    # --- A cell program the grid cannot start (user-ruled 2026-09-16) --------
    # The copied Claude launcher loses its execute permission, so Popen
    # raises for all three Claude cells. Each is a failed attempt like any
    # other: retried, then absent as program-unstartable, which is not
    # agent-cli-wide; the run goes on rather than ending in a traceback.
    repository = build_scratch_repository(scratch, "checkout-unstartable")
    (repository / "scripts" / "cold-read-claude-cell.py").chmod(0o644)
    result = run_grid(repository, stubs)
    failed_lines = lines_opening(result, "FAILED")
    check("an unstartable program is RETRYING then FAILED (exit none) as program-unstartable",
          len(lines_opening(result, "RETRYING:")) == 3 and len(failed_lines) == 3
          and all(line.startswith("FAILED (exit none): claude-")
                  and "program-unstartable — " in line for line in failed_lines),
          f"stdout={result.stdout!r}; stderr={result.stderr[-400:]!r}")
    check("the three Codex cells are unaffected: three land, some-landed text, exit 1",
          result.returncode == 1 and len(lines_opening(result, "saved:")) == 3
          and "3 of 6 reports landed in" in result.stdout, repr(result.stdout))
    check("program-unstartable says nothing about the agent-cli: no down line",
          "AGENT-CLI DOWN:" not in result.stdout, repr(result.stdout))
    record_directory = record_directory_of(repository)
    check("the unstartable attempts' logs hold the start error and are kept",
          (record_directory / "claude-hunt-good.md.attempt-1.stderr.log").is_file()
          and "could not start" in (record_directory / "claude-hunt-good.md.attempt-2.stderr.log")
          .read_text(encoding="utf-8"),
          sorted(path.name for path in record_directory.glob("*.stderr.log")))

    # --- The target changes during a run that has an absent report ------------
    # The two conditions are independent and land together often enough to
    # write down: the Fable cell fails both attempts (what the account's Fable
    # limit does) while the other five land and edit the document under review.
    repository = build_scratch_repository(scratch, "checkout-changed-and-absent")
    result = run_grid(
        repository, stubs,
        {"COLD_READ_GRID_TEST_STUB_EDIT_PATH": str(repository / TARGET_RELATIVE_PATH),
         "COLD_READ_GRID_TEST_STUB_FAILING_MODEL": "claude-fable-5-1"},
    )
    check("a run can lose a cell and its target at once: five saved, exit 3",
          result.returncode == 3 and len(lines_opening(result, "saved:")) == 5,
          f"exit {result.returncode}; stdout={result.stdout!r}")
    check("the target-changed text prints, then the absent report",
          "Do not triage this set" in result.stdout
          and result.stdout.index("Do not triage this set")
          < result.stdout.index("- claude-hunt-floor: exit-1 — "),
          repr(result.stdout))
    check("the changed-target path carries no triage instructions",
          "reports landed in" not in result.stdout and "Read every report in full" not in result.stdout,
          repr(result.stdout))
    record_directory = record_directory_of(repository)
    marked = (record_directory / "claude-hunt-good.md").read_text(encoding="utf-8").split("\n")
    check("both markers are written, the target-changed marker first, after the stamp",
          marked[0].startswith("<!-- provenance:")
          and marked[1].startswith("<!-- TARGET CHANGED DURING RUN:")
          and marked[2].startswith("<!-- INCOMPLETE SET: 1 of 6 reports absent"),
          repr(marked[:3]))

    # --- A Codex attempt's output holds the Claude limit text ----------------
    # No Codex text is recognised, so the class is exit-1 whatever the line
    # says, and the run is otherwise the same as that failure without the
    # line: the cause changes what is reported, never what is decided.
    repository = build_scratch_repository(scratch, "checkout-codex-quotes-limit")
    result = run_grid(repository, stubs, {"COLD_READ_GRID_TEST_STUB_FAILURE_PLAN": json.dumps(
        [{"fragment": "codex-terminology-good.md", "attempts": 2, "stdout": SESSION_LIMIT_LINE}])})
    repository_plain = build_scratch_repository(scratch, "checkout-codex-plain-failure")
    result_plain = run_grid(repository_plain, stubs, {"COLD_READ_GRID_TEST_STUB_FAILURE_PLAN": json.dumps(
        [{"fragment": "codex-terminology-good.md", "attempts": 2}])})
    check("a Codex failure whose output starts with the Claude limit text is exit-1",
          any(line.startswith("FAILED (exit 1): codex-terminology-good — exit-1 — ")
              for line in lines_opening(result, "FAILED"))
          and "account-limit" not in result.stdout and "AGENT-CLI DOWN:" not in result.stdout,
          repr(result.stdout))
    def decisions(text):
        return (text.count("RETRYING:"), text.count("FAILED (exit"), text.count("saved:"),
                "5 of 6 reports landed in" in text, "Tell the user:" in text)
    check("the retry, the closing text and the exit code are the same as without the line",
          result.returncode == result_plain.returncode == 1
          and decisions(result.stdout) == decisions(result_plain.stdout),
          f"{decisions(result.stdout)} vs {decisions(result_plain.stdout)}")

    # --- The terminology cells run at the effort the grid pins ---------------
    # max on both runtimes (user-ruled 2026-09-05, measured on the final
    # prompt: opus-max 20/15/28 flags on three targets, sol-max 44/41/49).
    # The grid passes it explicitly; the defect-hunt cells carry no override
    # and run at their launchers' own pins, which this case does not restate.
    repository = build_scratch_repository(scratch, "checkout-terminology-effort")
    effort_log = scratch / "terminology-effort.log"
    result = run_grid(
        repository, stubs, {"COLD_READ_GRID_TEST_STUB_EFFORT_LOG": str(effort_log)},
    )
    effort_by_report = dict(
        line.split(" ", 1) for line in
        (effort_log.read_text(encoding="utf-8").splitlines() if effort_log.is_file() else [])
        if " " in line)
    terminology_efforts = {name: effort for name, effort in effort_by_report.items()
                           if "-terminology-" in name}
    check("both terminology cells are launched at max",
          result.returncode == 0 and len(terminology_efforts) == 2
          and set(terminology_efforts.values()) == {"max"},
          f"exit {result.returncode}; efforts={effort_by_report!r}")
    record_directory = record_directory_of(repository)
    terminology_stamps = [
        path.read_text(encoding="utf-8").splitlines()[0]
        for path in sorted(record_directory.glob("*-terminology-good.md"))] if record_directory else []
    check("both terminology stamps record effort=max and cell=terminology",
          len(terminology_stamps) == 2
          and all("effort=max" in stamp and "cell=terminology" in stamp
                  for stamp in terminology_stamps),
          repr(terminology_stamps))

    # --- The model's echoed words are not the cell's status -----------------
    # The 2026-09-02 false positive (nedschorus#244): the Codex CLI copies the
    # model's text onto stderr, the cell re-emits that stderr into the log the
    # grid reads, and a reviewed document that quoted a comment containing
    # "fell back to" made two cells read as fallen back. Here every runtime
    # echoes a passage carrying all four lifted phrases mid-line, and nothing
    # is lifted. This case used to carry its own positive control, one cell
    # that really fell back; since the 2026-09-04 ruling no pinned chain has
    # a second model, so the positive control for the program-prefix matcher
    # is the stray-write case above, where a real STRAY WRITE line is lifted
    # through the same `cell_status_line` test.
    echoed_passage = (
        "As the document says: the supervisor fell back to its own default, "
        "then stray writes were not checked for this run, then files outside "
        "its report changed while it ran, and it recovered a near-miss report."
    )
    repository = build_scratch_repository(scratch, "checkout-echoed-phrases")
    result = run_grid(
        repository, stubs,
        {"COLD_READ_GRID_TEST_STUB_ECHO_STDERR_TEXT": echoed_passage},
    )
    saved_lines = [line for line in result.stdout.splitlines()
                   if line.startswith("saved:")]
    check("echoed text carrying the four lifted phrases lifts nothing",
          not any(line.startswith(("FELL BACK:", "STRAY WRITE:", "RECOVERED:",
                                   "WRITE CHECK DID NOT RUN:"))
                  for line in result.stdout.splitlines()),
          f"stdout was {result.stdout!r}")
    check("the echo costs nothing: six reviews land, grid exits 0",
          result.returncode == 0 and len(saved_lines) == 6,
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
          result.returncode == 0 and len(saved_lines) == 6,
          f"exit {result.returncode}, {len(saved_lines)} saved; stdout={result.stdout!r}")
    check("the grid prints RECOVERED: for each cell that recovered a report",
          len(recovered_lines) == 6, f"lifted lines were {recovered_lines!r}")
    # Two directories now: the one the grid made and the one the stubs
    # invented. The grid's is the one holding the reference-integrity
    # pre-pass, which no stub ever writes — the invented one's name differs by
    # a character, so picking either by sort order would be picking by luck.
    record_directories = sorted(
        directory for directory in (repository / "cold-read-records").iterdir()
        if directory.is_dir())
    grid_record_directories = [
        directory for directory in record_directories
        if (directory / "reference-check.md").is_file()]
    recovered_record_directory_name = (
        grid_record_directories[0].name if grid_record_directories else "")
    check("the RECOVERED line names the cell it belongs to",
          any(line.startswith("RECOVERED: claude-hunt-good.md")
              for line in recovered_lines),
          f"lifted lines were {recovered_lines!r}")
    check("the recovered reports are back in the directory the grid made",
          len(grid_record_directories) == 1
          and len(list(grid_record_directories[0].glob("*.md"))) == 7,
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
          result.returncode == 0 and len(saved_lines) == 6,
          f"exit {result.returncode}, {len(saved_lines)} saved; stderr={result.stderr!r}")
    check("an accepted run says nothing about a genre suffix",
          "genre suffix" not in result.stderr, repr(result.stderr))

    # --- The record-name rule: document stem, then date, then a count -------
    # User-ruled 2026-09-18 (walk cold-read-and-walk-file-names-and-dispositions,
    # item 4): `<file stem>-<YYYY-MM-DD>`, and `SKILL-<skill name>-<YYYY-MM-DD>`
    # for a skill, whose stem is always SKILL. It reverses the date-first,
    # parent-directory form of 2026-09-16 so that every read of one document
    # sits together in the store's listing, and accepts what that form
    # bought: same-stem documents in different directories read on one day
    # become -2 of each other, and the count says nothing about which draft
    # each read was. The grid is loaded in-process for the name function
    # alone, which is handed its clock; nothing runs.
    grid_spec = importlib.util.spec_from_file_location(
        "cold_read_grid_under_test", SCRIPTS_DIR / "cold-read-grid.py")
    grid_module = importlib.util.module_from_spec(grid_spec)
    grid_spec.loader.exec_module(grid_module)
    clock_at_1042 = datetime.datetime(2026, 9, 16, 10, 42)

    def grid_record_name(path, clock=clock_at_1042):
        return grid_module.record_directory_name_for_target(Path(path), clock)

    check("grid: a SKILL.md record is SKILL, the skill's name, then the date",
          grid_record_name("/r/.claude/skills/cold-read/SKILL.md")
          == "SKILL-cold-read-2026-09-16",
          grid_record_name("/r/.claude/skills/cold-read/SKILL.md"))
    check("grid: an ordinary document is its stem, then the date, with no directory",
          grid_record_name("/r/docs/drafts/explain-skill-draft.md")
          == "explain-skill-draft-2026-09-16",
          grid_record_name("/r/docs/drafts/explain-skill-draft.md"))
    check("grid: a skill's prompt file is its stem alone, like any other document",
          grid_record_name("/r/.claude/skills/cold-read/prompts/terminology.md")
          == "terminology-2026-09-16",
          grid_record_name("/r/.claude/skills/cold-read/prompts/terminology.md"))
    check("grid: README and index get no special case",
          grid_record_name("/r/docs/nedschorus-wiki/README.md") == "README-2026-09-16"
          and grid_record_name("/r/docs/index.md") == "index-2026-09-16")
    check("grid: a file whose parent has no name is still its stem and the date",
          grid_record_name("/CLAUDE.md") == "CLAUDE-2026-09-16",
          grid_record_name("/CLAUDE.md"))
    check("grid: the time of day is not part of the name",
          grid_record_name("/r/docs/drafts/a.md", datetime.datetime(2026, 9, 16, 9, 5))
          == "a-2026-09-16"
          and grid_record_name("/r/docs/drafts/a.md", datetime.datetime(2026, 9, 16, 21, 5))
          == "a-2026-09-16")

    # Through the real grid: a skill read twice in one day, then once the
    # next day. The first run takes the plain name, the second -2, and the
    # third its own later name with no suffix.
    repository = build_scratch_repository(scratch, "checkout-skill-record-name")
    skill_relative_path = ".claude/skills/some-named-skill/SKILL.md"
    write_target(repository, skill_relative_path)
    first_result = run_grid(repository, stubs, target_relative_path=skill_relative_path)
    second_result = run_grid(repository, stubs, target_relative_path=skill_relative_path)
    records_after_one_day = sorted(
        p.name for p in (repository / "cold-read-records").glob("*"))
    check("a skill target's record is named SKILL, the skill's directory, and the date",
          first_result.returncode == 0
          and "SKILL-some-named-skill-2026-09-16" in records_after_one_day,
          f"exit {first_result.returncode}; records={records_after_one_day}; "
          f"stderr={first_result.stderr[-300:]!r}")
    check("a second run on the same day takes the -2 directory",
          second_result.returncode == 0
          and records_after_one_day == ["SKILL-some-named-skill-2026-09-16",
                                        "SKILL-some-named-skill-2026-09-16-2"],
          f"exit {second_result.returncode}; records={records_after_one_day}")
    third_result = run_grid(
        repository, stubs, {RECORD_CLOCK_OVERRIDE_VARIABLE: "2026-09-17T10:42"},
        target_relative_path=skill_relative_path)
    records_after_two_days = sorted(
        p.name for p in (repository / "cold-read-records").glob("*"))
    check("a run on a different day takes a distinct name with no suffix",
          third_result.returncode == 0
          and records_after_two_days == ["SKILL-some-named-skill-2026-09-16",
                                         "SKILL-some-named-skill-2026-09-16-2",
                                         "SKILL-some-named-skill-2026-09-17"],
          f"exit {third_result.returncode}; records={records_after_two_days}")
    suffixed_record = repository / "cold-read-records" / "SKILL-some-named-skill-2026-09-16-2"
    check("the files in a suffixed record are bare role names too",
          (suffixed_record / "claude-hunt-good.md").is_file()
          and (suffixed_record / "reference-check.md").is_file(),
          sorted(p.name for p in suffixed_record.iterdir()) if suffixed_record.is_dir() else "absent")


    # --- The target is frozen into the record, and the record is shipped ------
    # User-ruled 2026-09-07: the record carries the exact bytes reviewed at the
    # target's repository path, and goes to the log-store at the end of every
    # run. The plain run: the frozen copy equals the target, the `record:`
    # line says shipped, and the store holds the same files as the record.
    repository = build_scratch_repository(scratch, "checkout-frozen-and-shipped")
    result = run_grid(repository, stubs)
    record_directory = record_directory_of(repository)
    frozen = record_directory / "target" / TARGET_RELATIVE_PATH
    check("the target's bytes are frozen under target/ at its repository path",
          frozen.is_file() and frozen.read_bytes() == (repository / TARGET_RELATIVE_PATH).read_bytes(),
          f"{frozen} present={frozen.exists()}")
    record_lines = [line for line in result.stdout.splitlines() if line.startswith("record: ")]
    check("the run prints one record: line, and it says shipped",
          len(record_lines) == 1 and record_lines[0].startswith("record: shipped:"),
          f"{record_lines!r}; stderr={result.stderr[-400:]!r}")
    store_copy = repository / SCRATCH_LOG_STORE_RELATIVE / record_directory.name
    check("the store holds every file the record holds, the frozen target included",
          store_copy.is_dir() and sorted(p.relative_to(store_copy) for p in store_copy.rglob("*") if p.is_file())
          == sorted(p.relative_to(record_directory) for p in record_directory.rglob("*") if p.is_file()),
          f"store={sorted(str(p) for p in store_copy.rglob('*'))}")
    check("the closing text names the ship command for after triage.md",
          f"scripts/cold-read-record-ship.py {record_directory.resolve()}" in result.stdout
          and "gitignored" in result.stdout and "user-ruled 2026-08-14" not in result.stdout,
          result.stdout[-900:])
    check("a settled run that shipped still exits 0",
          result.returncode == 0, f"exit {result.returncode}")

    # --- A store that cannot be reached does not fail the read ----------------
    repository = build_scratch_repository(scratch, "checkout-store-unreachable")
    result = run_grid(repository, stubs, {
        RECORD_SHIP_DESTINATION_VARIABLE: "nobody@no-such-host.invalid:/tmp/no-store"})
    record_lines = [line for line in result.stdout.splitlines() if line.startswith("record: ")]
    check("an unreachable store prints record: FAILED and the run exits 0 all the same",
          len(record_lines) == 1 and record_lines[0].startswith("record: FAILED:")
          and result.returncode == 0,
          f"exit {result.returncode}; {record_lines!r}")
    record_directory = record_directory_of(repository)
    check("the record, frozen target included, stays on disk for a later ship",
          record_directory is not None and (record_directory / "target" / TARGET_RELATIVE_PATH).is_file())

    # --- A changed target is still shipped: it is evidence -------------------
    repository = build_scratch_repository(scratch, "checkout-changed-still-shipped")
    result = run_grid(repository, stubs, {
        "COLD_READ_GRID_TEST_STUB_EDIT_PATH": str(repository / TARGET_RELATIVE_PATH)})
    record_lines = [line for line in result.stdout.splitlines() if line.startswith("record: ")]
    check("a run whose target moved ships its marked record and exits 3",
          result.returncode == 3 and record_lines and record_lines[0].startswith("record: shipped:"),
          f"exit {result.returncode}; {record_lines!r}")
    record_directory = record_directory_of(repository)
    frozen = record_directory / "target" / TARGET_RELATIVE_PATH
    check("the frozen target is the launch-time text, not the edited one",
          frozen.is_file() and b"reviewer's own edit" not in frozen.read_bytes()
          and b"reviewer's own edit" in (repository / TARGET_RELATIVE_PATH).read_bytes())

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
    # The frozen target lives under target/ at its own repository path: it
    # says where the reviewed file lived. Every file the run itself wrote is
    # a bare role name; none carries the record directory's name.
    written_names = sorted(path.name for path in record_directory.iterdir()
                           if path.name != "target")
    check("no file the run wrote carries the record directory's name",
          not any(record_directory.name in name for name in written_names),
          [name for name in written_names if record_directory.name in name])
    check("beside them, the record holds only the frozen target directory",
          sorted(path.name for path in record_directory.iterdir()
                 if not path.name.endswith(".md")) == ["target"])
    expected_names = sorted(
        ["reference-check.md"]
        + [f"{runtime}-{pass_token}-{tier}.md"
           for runtime in ("claude", "codex")
           for pass_token, tier in (("hunt", "good"), ("hunt", "floor"),
                                    ("terminology", "good"))])
    check("the set holds the six cells plus the reference-integrity pre-pass",
          written_names == expected_names, written_names)

    # --- A path under a dot directory keeps its dot --------------------------
    # The pre-pass trimmed punctuation from both ends of every candidate, so
    # a path under a dot directory lost its leading dot and was reported
    # UNRESOLVED. Every instruction file in this project lives under
    # `.claude/`, so the check was least useful exactly where it mattered
    # most. Found by the 2026-09-11 cold read, which caught the grid calling
    # its own terminology prompt unresolved inside that run's own record.
    repository = build_scratch_repository(scratch, "dot-directory-reference")
    dotted = ".claude/skills/cold-read/prompts/terminology.md"
    (repository / TARGET_RELATIVE_PATH).write_text(
        f"# Target\n\nThe terminology prompt is `{dotted}`, and here it ends\n"
        f"a sentence: {dotted}.\n", encoding="utf-8")
    run_grid(repository, stubs / "dot-directory-reference")
    record_directory = record_directory_of(repository)
    reference_check = (
        record_directory / "reference-check.md"
    ).read_text(encoding="utf-8")
    check("a path under a dot directory resolves with its dot intact",
          f"- ok: `{dotted}`" in reference_check, reference_check)
    check("and nothing in that target is left unresolved",
          "UNRESOLVED" not in reference_check, reference_check)


print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
