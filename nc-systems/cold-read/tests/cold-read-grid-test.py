#!/usr/bin/env python3
"""Tests for cold-read-grid.py — what a grid run tells the agent reading it.

HOW A CASE RUNS. Each case builds a throwaway git repository holding a copy
of the whole scripts/ directory and of the prompt templates, and runs the grid
inside it with stub `claude` and `codex` executables first on PATH. Two seams
make that work. The grid and the cells take their repository root from their
own location on disk, so a copy is a grid whose record directories and whose
`git status` are the scratch tree's and never this checkout's. And the stubs
are the models: each finds the report path in the prompt it was handed — the
Claude leg on stdin, the Codex leg as an argument — writes a line to it and
exits 0, so six cells complete in seconds without a model call. A real grid
run is six reviews and half an hour; these cases are about what the grid says,
not about what a reviewer finds.

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
    nc-systems/cold-read/cold-read-grid-cell-failure-handling-design.md, whose
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
    marked INCOMPLETE SET, an agent-binary whose every cell is absent for one
    agent-binary-wide cause gets one AGENT-BINARY DOWN: line, and a cause the user
    can clear ends the text with "Tell the user:". A cause changes what is
    reported, never what is decided: the cases below drive the stub through
    the real limit texts and check that the retry, the closing text and the
    exit code are the same whatever the cause said. The grid's FELL BACK
    line (2026-08-25, "I just don't want it to fail silently") has no
    positive control through the grid since no pinned chain has a second
    model; the lift machinery stays.

  - The read is six cells: the defect-hunt pass on both tiers of both
    runtimes, and the terminology pass (user-ruled 2026-09-05) on the
    `deep` tier of both. The terminology cells run at the effort the grid pins,
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

    A move seen while reviewers are still reading stops the run there
    (user-ruled 2026-09-23: "n, and yes abort early"): the reviewers still
    running are stopped with their children, the closing text names them, the
    reports the set holds are marked, and the run exits 3 long before the
    readers would have finished. A move seen only after the last reviewer
    finished stops nothing and is reported by the end-of-run comparison as
    before, and a target nobody edits survives several polls untouched.

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
    the recovery itself (nc-systems/cold-read/tests/cold-read-cell-common-test.py pins it). The
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

Run: python3 nc-systems/cold-read/tests/cold-read-grid-test.py
"""

import datetime
import hashlib
import importlib.util
import inspect
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

# This suite sits in nc-systems/cold-read/tests/; the programs it tests are
# one directory up.
SYSTEM_DIRECTORY = Path(__file__).resolve().parent.parent
REPO_ROOT = SYSTEM_DIRECTORY.parent.parent
PROMPTS_DIR = REPO_ROOT / ".claude" / "skills" / "cold-read" / "prompts"

# A variable that redirects git, left in this process, would send the scratch
# repositories' git writes into the repository it names. Removed before any
# git runs, so the programs this suite starts inherit the removal too.
_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    REPO_ROOT / "scripts" / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

# The scratch repository every cold-read suite builds, defined once.
_scratch_repository_fixture_spec = importlib.util.spec_from_file_location(
    "cold_read_scratch_repository_test_fixture",
    SYSTEM_DIRECTORY / "tests" / "cold-read-scratch-repository-test-fixture.py")
scratch_repository_fixture = importlib.util.module_from_spec(
    _scratch_repository_fixture_spec)
_scratch_repository_fixture_spec.loader.exec_module(scratch_repository_fixture)

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
# A case whose subject is the END-OF-RUN comparison is given this, so no poll
# looks at the target mid-run: every stub edits the target as it exits, and a
# poll landing between one cell's edit and another's exit would otherwise stop
# cells at random. A case about the mid-run stop leaves it unset.
TARGET_CHECK_INTERVAL_OVERRIDE_VARIABLE = "COLD_READ_GRID_TARGET_CHECK_INTERVAL_SECONDS"
END_OF_RUN_COMPARISON_ONLY = {TARGET_CHECK_INTERVAL_OVERRIDE_VARIABLE: "86400"}
# Every run here polls its cells this often instead of every 5 seconds, through
# the grid's override: the stubs finish at once, so the production poll is only
# waiting.
CELL_POLL_INTERVAL_OVERRIDE_VARIABLE = "COLD_READ_GRID_CELL_POLL_INTERVAL_SECONDS"
CELL_POLL_INTERVAL_FOR_TESTS_SECONDS = "0.1"

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
# cells (Opus is the `deep` Claude cell of both passes), so
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
# `claude` agent-binary's model-limit message names it -- or the attempt's own
# text from "stdout_by_attempt" ({"2": ...}), and appending to the file
# "edit" before failing, for a stray write by a failed first attempt.
# COLD_READ_GRID_TEST_STUB_SLEEP_SECONDS, when set, is how long the stub waits
# before writing its report -- a reviewer still reading -- except in a cell
# whose report name contains COLD_READ_GRID_TEST_STUB_FAST_REPORT_NAME_FRAGMENT,
# which does not wait. One fast cell that edits the target while five slow
# ones read is how a case moves the target mid-run.
STUB_MODEL_RUNTIME = r'''#!/usr/bin/env python3
import json, os, pathlib, re, sys, time

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
# The report path and the cold-read-target's path are BOTH inside the record
# since the cells were pointed at the frozen copy (2026-09-22), and both end
# in .md. The copy is the one under <record>/target/, so it is excluded here:
# without that, this stub writes its report over the document it was asked to
# review, which is a defect in the stub and looks exactly like a product one.
report_candidates = [
    found for found in re.findall(r"[^\s\"']+cold-read-records/[^\s\"']+\.md", prompt)
    if "/target/" not in found
]
if not report_candidates:
    sys.stderr.write("stub runtime: no report path found in the prompt\n")
    sys.exit(3)
given = pathlib.Path(report_candidates[0])
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
sleep_seconds = float(os.environ.get("COLD_READ_GRID_TEST_STUB_SLEEP_SECONDS") or 0)
fast_fragment = os.environ.get("COLD_READ_GRID_TEST_STUB_FAST_REPORT_NAME_FRAGMENT")
if sleep_seconds and not (fast_fragment and fast_fragment in given.name):
    time.sleep(sleep_seconds)
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
target_match = re.search(r"[^\s\"']+cold-read-grid-test-target\.md", prompt)
target_log = os.environ.get("COLD_READ_GRID_TEST_STUB_TARGET_LOG")
if target_log and target_match:
    with open(target_log, "a", encoding="utf-8") as handle:
        handle.write(target_match.group(0) + "\n")
prompt_log = os.environ.get("COLD_READ_GRID_TEST_STUB_PROMPT_LOG")
if prompt_log:
    with open(prompt_log, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(prompt) + "\n")
if os.environ.get("COLD_READ_GRID_TEST_STUB_EDIT_GIVEN_TARGET") and target_match:
    # A reviewer editing the very document it was handed. The frozen copy is
    # read-only, so this forces the mode first: the point of the case is the
    # fingerprint catching an edit to the copy, not the mode bit stopping a
    # determined writer.
    given_target = pathlib.Path(target_match.group(0))
    os.chmod(given_target, 0o644)
    with open(given_target, "a", encoding="utf-8") as handle:
        handle.write("The reviewer's edit to the document it was given.\n")
sys.exit(0)
'''

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def build_scratch_repository(scratch, name):
    """This suite's own seeding only; the scripts copy and the seed commit
    are the fixture's."""
    repository = scratch / name
    scratch_prompts = repository / ".claude" / "skills" / "cold-read" / "prompts"
    scratch_prompts.mkdir(parents=True)
    for prompt_path in PROMPTS_DIR.glob("*.md"):
        shutil.copy2(prompt_path, scratch_prompts / prompt_path.name)
    target = repository / TARGET_RELATIVE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# Target\n\nOne committed line.\n", encoding="utf-8")
    return scratch_repository_fixture.commit_seeded_cold_read_scratch_repository(
        repository)


def write_target(repository, relative_path):
    """A second document in the scratch repository, for a case that needs a
    target of its own name — the genre-suffix cases below turn entirely on
    what the file is called."""
    target = repository / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# Target\n\nOne uncommitted line.\n", encoding="utf-8")
    return target


def run_grid(repository, stub_directory, environment_overrides=None,
             target_relative_path=TARGET_RELATIVE_PATH, extra_arguments=()):
    stub_directory.mkdir(parents=True, exist_ok=True)
    for runtime_name in ("claude", "codex"):
        stub = stub_directory / runtime_name
        stub.write_text(STUB_MODEL_RUNTIME, encoding="utf-8")
        stub.chmod(0o755)
    # Every Codex cell scans HOME for credential files at launch, and the
    # real home takes seconds to walk.
    scratch_home = repository.parent / "scratch-home"
    scratch_home.mkdir(exist_ok=True)
    environment = dict(os.environ)
    environment["HOME"] = str(scratch_home)
    environment["PATH"] = f"{stub_directory}{os.pathsep}{environment.get('PATH', '')}"
    environment[RECORD_SHIP_DESTINATION_VARIABLE] = str(repository / SCRATCH_LOG_STORE_RELATIVE)
    # The grid lists the store to count earlier runs, and a store it cannot list stops it.
    (repository / SCRATCH_LOG_STORE_RELATIVE).mkdir(parents=True, exist_ok=True)
    environment[RECORD_CLOCK_OVERRIDE_VARIABLE] = FIXED_RECORD_CLOCK_FOR_TESTS
    environment[CELL_POLL_INTERVAL_OVERRIDE_VARIABLE] = CELL_POLL_INTERVAL_FOR_TESTS_SECONDS
    environment["COLD_READ_GRID_TEST_STUB_ATTEMPT_COUNTER_DIRECTORY"] = str(
        repository.parent / "stub-attempt-counts" / repository.name / str(time.time_ns()))
    environment.update(environment_overrides or {})
    return subprocess.run(
        [sys.executable, str(repository / "nc-systems" / "cold-read" / "cold-read-grid.py"),
         "--target", target_relative_path, *extra_arguments],
        capture_output=True, text=True, check=False, env=environment,
    )


def seed_log_store_record(repository, directory_name, file_names,
                          frozen_relative=TARGET_RELATIVE_PATH, written_at=None,
                          tree=SCRATCH_LOG_STORE_RELATIVE):
    """A record as an earlier run would have left it: its files, and the
    document it froze under target/."""
    directory = repository / tree / directory_name
    for relative in [*file_names, f"target/{frozen_relative}"]:
        path = directory / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("earlier run\n", encoding="utf-8")
        if written_at is not None:
            os.utime(path, (written_at, written_at))


def record_directory_of(repository):
    """The record directory the run just made. One per case, by construction."""
    directories = sorted((repository / "cold-read-records").glob("*"))
    return directories[-1] if directories else None


def frozen_target_path_in_scratch_repository(repository, record_directory):
    """Where the grid in `repository` froze TARGET_RELATIVE_PATH inside
    `record_directory`, as frozen_target_path() itself answers it.

    Loaded from the scratch repository's own copy of
    nc-systems/cold-read/cold-read-record-names.py, not from this checkout's:
    the function makes the target relative to its module's REPO_ROOT, so this
    checkout's copy would find the scratch target outside its repository and
    return the absolute-path fallback. The scratch copy is also the very file
    the grid under test loaded."""
    record_names_spec = importlib.util.spec_from_file_location(
        "cold_read_record_names_in_scratch_repository",
        repository / "nc-systems" / "cold-read" / "cold-read-record-names.py")
    record_names = importlib.util.module_from_spec(record_names_spec)
    record_names_spec.loader.exec_module(record_names)
    return record_names.frozen_target_path(
        repository / TARGET_RELATIVE_PATH, record_directory)


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
    # What the reviewer edits here is the original document, which every cell
    # read through its frozen copy. The copy did not move, so the set stands:
    # six reviews, exit 0, no report marked, and one line naming the copy the
    # set reviewed.
    repository = build_scratch_repository(scratch, "checkout-stray-write")
    result = run_grid(
        repository, stubs,
        {"COLD_READ_GRID_TEST_STUB_EDIT_PATH": str(repository / TARGET_RELATIVE_PATH),
         **END_OF_RUN_COMPARISON_ONLY},
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
    check("an edited original stops nothing: six reviews land and the run exits 0",
          result.returncode == 0 and len(saved_lines) == 6,
          f"exit {result.returncode}, {len(saved_lines)} saved; stdout={result.stdout!r}")
    check("an edited original is not reported as a changed target",
          "#frozen_copy_changed_during_run" not in result.stdout, repr(result.stdout))
    original_lines = [line for line in result.stdout.splitlines()
                      if line.startswith("#cold_read_target_changed_during_run")]
    record_directory = record_directory_of(repository)
    frozen = frozen_target_path_in_scratch_repository(repository, record_directory)
    check("the grid says the original changed, in one line",
          len(original_lines) == 1, repr(result.stdout))
    check("the line names the frozen copy the set reviewed",
          original_lines != [] and str(frozen.resolve()) in original_lines[0]
          and "carry each fix to the document as it now stands" in original_lines[0],
          repr(original_lines))
    check("the frozen copy is the launch-time text, not the edited one",
          frozen.is_file() and b"reviewer's own edit" not in frozen.read_bytes()
          and b"reviewer's own edit" in (repository / TARGET_RELATIVE_PATH).read_bytes())
    check("an edited original still gets the closing instructions to triage",
          "All six reports landed" in result.stdout
          and "Do not triage any finding in this set" not in result.stdout, repr(result.stdout))
    reports = sorted(record_directory.glob("*.md"))
    check("no report is marked when only the original changed",
          reports != [] and not any(
              "<!-- #frozen_copy_changed_during_run" in report.read_text(encoding="utf-8")
              for report in reports),
          [report.name for report in reports])
    stamped = record_directory / "claude-hunt-deep.md"
    stamped_text = stamped.read_text(encoding="utf-8") if stamped.is_file() else ""
    stamp = stamped_text.split("\n", 1)[0]
    frozen_sha256 = hashlib.sha256(frozen.read_bytes()).hexdigest() if frozen.is_file() else "absent"
    check("each report's stamp names the frozen copy it reviewed, by path and sha256",
          stamp.startswith("<!-- provenance:")
          and f"target_sha256={frozen_sha256} " in stamp
          and Path(stamp.rsplit("target=", 1)[-1].removesuffix(" -->")).resolve()
          == frozen.resolve(),
          repr(stamp))
    check("the reviewer's own text survives",
          "STUB REVIEW: one restatement" in stamped_text, repr(stamped_text[:200]))

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
          "#frozen_copy_changed_during_run" not in result.stdout, repr(result.stdout))
    check("a settled target still gets the closing instructions to triage",
          "All six reports landed" in result.stdout
          and "Stop editing the document" not in result.stdout, repr(result.stdout))
    # Line breaks collapsed first: the closing text is wrapped, and a check
    # that missed the sentence because of where its line ended would fail for
    # the wrong reason.
    closing_text = " ".join(result.stdout.split())
    check("the closing text says what the terminology reports are and how to triage them",
          "The terminology reports list the document's terms that fail one of "
          "five criteria, with the criteria numbers per item and a closing counts "
          "line; triage them the same way as the defect-hunt reports." in closing_text,
          repr(result.stdout))
    check("the closing text counts one reviewer's problem and defers to step 9 of the skill",
          "A problem one reviewer alone reports is real. Then apply your changes, "
          "and take to the user only what step 9 of the /cold-read skill sends to "
          "the user." in closing_text
          and "walk-me-through" not in closing_text,
          repr(result.stdout))

    # --- A frozen copy that moves while reviewers are still reading ----------
    # The run stops at the first poll that sees the copy move (user-ruled
    # 2026-09-23: "n, and yes abort early"), because no report can then say
    # which text it read. One cell edits the copy it was given and exits at
    # once; the other five would read for two minutes.
    # A separate stub directory, so a stub left running is this case's and can
    # be found by its path.
    def processes_mentioning(*fragments):
        listing = subprocess.run(["ps", "-A", "-o", "pid=", "-o", "command="],
                                 capture_output=True, text=True, check=False).stdout
        return [line.strip() for line in listing.splitlines()
                if any(fragment in line for fragment in fragments)]

    repository = build_scratch_repository(scratch, "checkout-target-moves-mid-run")
    slow_stubs = scratch / "stub-bin-target-moves-mid-run"
    started = time.monotonic()
    result = run_grid(repository, slow_stubs, {
        "COLD_READ_GRID_TEST_STUB_SLEEP_SECONDS": "120",
        "COLD_READ_GRID_TEST_STUB_FAST_REPORT_NAME_FRAGMENT": "codex-hunt-second",
        "COLD_READ_GRID_TEST_STUB_EDIT_GIVEN_TARGET": "1"})
    elapsed = time.monotonic() - started
    check("a frozen copy moved mid-run stops the run long before the readers finish",
          elapsed < 60, f"{elapsed:.0f} s; stdout={result.stdout!r}")
    check("a run stopped for a moved frozen copy exits 3",
          result.returncode == 3, f"exit {result.returncode}; stdout={result.stdout!r}")
    check("the stopped run says the target changed, on its own output, in one line",
          result.stdout.count("#frozen_copy_changed_during_run") == 1, repr(result.stdout))
    check("the line says the run stopped the cells still reading",
          "run stopped those cells" in result.stdout
          and "the moment the last one finished" not in result.stdout, repr(result.stdout))
    # The editing cell itself lands or is stopped depending on whether a poll
    # fell between its edit and its exit; the five still reading are stopped
    # either way, and none of them lands.
    stopped_line = next((line for line in result.stdout.splitlines()
                         if line.startswith("Stopped before finishing:")), "")
    check("the closing text names the five cells still reading as stopped",
          all(name in stopped_line for name in (
              "claude-hunt-deep", "claude-hunt-second", "claude-terminology-deep",
              "codex-hunt-deep", "codex-terminology-deep")), repr(stopped_line))
    saved_lines = [line for line in result.stdout.splitlines() if line.startswith("saved:")]
    check("no cell that was still reading lands",
          all("codex-hunt-second" in line for line in saved_lines), repr(saved_lines))
    check("a stopped run is told not to triage and to start a new cold-read run",
          "Do not triage any finding in this set" in result.stdout
          and "Start a new cold-read run" in result.stdout, repr(result.stdout))
    check("a stopped run's closing text names the frozen copy and how to compare it with the original",
          "Before any new run, find what edited the frozen copy" in result.stdout
          and "diff " in result.stdout and "frozen copy /" in result.stdout, repr(result.stdout))
    record_directory = record_directory_of(repository)
    reports = sorted(record_directory.glob("*.md")) if record_directory else []
    check("every report the stopped set holds carries the marker",
          reports != [] and all(
              "<!-- #frozen_copy_changed_during_run" in report.read_text(encoding="utf-8")
              for report in reports),
          [report.name for report in reports])
    check("the stopped run leaves the stop marker file, which keeps it out of every later count",
          record_directory is not None
          and (record_directory / "frozen-copy-changed-during-run-stop-marker.txt").is_file(),
          f"record {record_directory}")
    check("the first stop is told it does not count and is stop 1 of 3, and to start a new run",
          "Start a new cold-read run once nothing but cold-read-grid.py will write "
          "under the record directory, or once the user says to. "
          "This run does not count toward the 3 cold-read-full-runs: "
          "it is stop 1 of 3 in a row because the frozen copy changed." in result.stdout,
          repr(result.stdout))
    check("no stopped reviewer or its launcher is left running",
          processes_mentioning(str(slow_stubs), str(repository)) == [],
          processes_mentioning(str(slow_stubs), str(repository)))
    # A stopped cell never reaches its stray-write check, which runs after the
    # model exits; without a line saying so the run reads as checked and
    # clean (nedschorus#167, and PR 699's review).
    unchecked_lines = [line for line in result.stdout.splitlines()
                       if line.startswith("WRITE CHECK DID NOT RUN:")]
    # A third stop allows no new run, so the stopped cell's line must not assume one.
    check("the not-checked line does not assume a new run follows",
          unchecked_lines != [] and not any("new run" in line for line in unchecked_lines),
          repr(unchecked_lines))
    check("every stopped cell is named as not checked for stray writes",
          all(any(line.startswith(f"WRITE CHECK DID NOT RUN: {name}.md — ")
                  for line in unchecked_lines)
              for name in ("claude-hunt-deep", "claude-hunt-second",
                           "claude-terminology-deep", "codex-hunt-deep",
                           "codex-terminology-deep")),
          repr(unchecked_lines))
    check("each not-checked line names its stopped cell and opens a sentence with a capital",
          unchecked_lines != [] and all(
              line.split(" — ", 1)[1].startswith(
                  f"The {line.split(': ', 1)[1].split('.md', 1)[0]} cell was stopped")
              for line in unchecked_lines),
          repr(unchecked_lines))
    check("the not-checked line says it is a failure to look, not a clean result",
          unchecked_lines != []
          and all("failure to look, not a clean result" in line for line in unchecked_lines),
          repr(unchecked_lines))

    # --- An original that moves while reviewers are still reading ------------
    # The other side of the same rule: one cell edits the original at once
    # while five read on; every cell reads the frozen copy,
    # so nothing is stopped and all six land.
    repository = build_scratch_repository(scratch, "checkout-original-moves-mid-run")
    still_reading_seconds = 10 * float(CELL_POLL_INTERVAL_FOR_TESTS_SECONDS)
    result = run_grid(repository, scratch / "stub-bin-original-moves-mid-run", {
        "COLD_READ_GRID_TEST_STUB_SLEEP_SECONDS": str(still_reading_seconds),
        "COLD_READ_GRID_TEST_STUB_FAST_REPORT_NAME_FRAGMENT": "codex-hunt-second",
        "COLD_READ_GRID_TEST_STUB_EDIT_PATH": str(repository / TARGET_RELATIVE_PATH)})
    check("an original edited mid-run lets every cell finish: six reviews, exit 0",
          result.returncode == 0
          and len([line for line in result.stdout.splitlines()
                   if line.startswith("saved:")]) == 6,
          f"exit {result.returncode}; stdout={result.stdout!r}")
    check("an original edited mid-run stops no cell",
          "Stopped before finishing" not in result.stdout
          and "#frozen_copy_changed_during_run" not in result.stdout, repr(result.stdout))
    check("an original edited mid-run is named in one line",
          result.stdout.count("#cold_read_target_changed_during_run") == 1, repr(result.stdout))

    # --- A target nobody touches, across several polls ------------------------
    # The other side of the same check: readers slow enough to be polled more
    # than once, and a target nobody edits, finish as an ordinary run.
    repository = build_scratch_repository(scratch, "checkout-target-still-over-polls")
    # Readers that take ten of this suite's polls to finish.
    still_reading_seconds = 10 * float(CELL_POLL_INTERVAL_FOR_TESTS_SECONDS)
    result = run_grid(repository, scratch / "stub-bin-target-still-over-polls",
                      {"COLD_READ_GRID_TEST_STUB_SLEEP_SECONDS": str(still_reading_seconds)})
    check("a settled target over several polls stops nothing: six reviews, exit 0",
          result.returncode == 0
          and len([line for line in result.stdout.splitlines()
                   if line.startswith("saved:")]) == 6,
          f"exit {result.returncode}; stdout={result.stdout!r}")
    check("a settled target over several polls is not reported as changed",
          "#frozen_copy_changed_during_run" not in result.stdout
          and "Stopped before finishing" not in result.stdout, repr(result.stdout))

    # --- Every failure case below, in the design's terms ---------------------
    # nc-systems/cold-read/cold-read-grid-cell-failure-handling-design.md, section
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
        [{"fragment": "claude-hunt-second.md", "attempts": 1}])})
    saved_lines = lines_opening(result, "saved:")
    retrying_lines = lines_opening(result, "RETRYING:")
    check("a first failure prints RETRYING: naming the cell and its cause",
          len(retrying_lines) == 1
          and retrying_lines[0].startswith("RETRYING: claude-hunt-second — exit-1 — ")
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
          == ["claude-hunt-second.md.attempt-1.stderr.log"],
          sorted(path.name for path in record_directory.glob("*.stderr.log")))
    check("a set with no absent report carries no INCOMPLETE SET marker",
          markers_in(record_directory, "<!-- INCOMPLETE SET:") == [])

    # --- A failed first attempt's stray write is still reported ---------------
    # The retry takes its own baseline after the first attempt's write, so
    # the line has to be lifted from the first attempt's log before relaunch.
    repository = build_scratch_repository(scratch, "checkout-stray-write-on-failed-attempt")
    stray_relative_path = "docs/drafts/cold-read-grid-test-stray.md"
    result = run_grid(repository, stubs, {"COLD_READ_GRID_TEST_STUB_FAILURE_PLAN": json.dumps(
        [{"fragment": "codex-hunt-deep.md", "attempts": 1,
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
        [{"fragment": "claude-terminology-deep.md", "attempts": 2}])})
    failed_lines = lines_opening(result, "FAILED")
    check("RETRYING: then FAILED (exit 1) with the second attempt's cause",
          len(lines_opening(result, "RETRYING:")) == 1 and len(failed_lines) == 1
          and failed_lines[0].startswith("FAILED (exit 1): claude-terminology-deep — exit-1 — ")
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
          any(line.startswith("- claude-terminology-deep: exit-1 — ")
              and line.endswith("claude-terminology-deep.md.attempt-2.stderr.log)")
              for line in result.stdout.splitlines()),
          repr(result.stdout))
    closing_text = " ".join(result.stdout.split())
    check("the triage instructions read to every report that landed and record the absence",
          "until you have read every report that landed" in closing_text
          and "Record each absent report and its cause in triage.md." in closing_text
          and "read all six" not in closing_text, repr(result.stdout))
    check("an exit-N cause is not one the user can clear: no Tell the user sentence, no AGENT-BINARY DOWN",
          "Tell the user:" not in result.stdout and "AGENT-BINARY DOWN:" not in result.stdout,
          repr(result.stdout))
    record_directory = record_directory_of(repository)
    check("the INCOMPLETE SET marker is in all six .md files of the record",
          len(markers_in(record_directory, "<!-- INCOMPLETE SET: 1 of 6 reports absent — "
                                            "claude-terminology-deep (exit-1 — ")) == 6,
          markers_in(record_directory, "<!-- INCOMPLETE SET:"))
    stamped = (record_directory / "claude-hunt-deep.md").read_text(encoding="utf-8").split("\n")
    check("the marker goes after the provenance stamp",
          stamped[0].startswith("<!-- provenance:") and stamped[1].startswith("<!-- INCOMPLETE SET:"),
          repr(stamped[:2]))
    check("both attempts' logs of the absent cell are kept, the landed cells' deleted",
          sorted(path.name for path in record_directory.glob("*.stderr.log"))
          == ["claude-terminology-deep.md.attempt-1.stderr.log",
              "claude-terminology-deep.md.attempt-2.stderr.log"],
          sorted(path.name for path in record_directory.glob("*.stderr.log")))

    # --- All three Claude cells fail both attempts with the account limit ----
    # The 2026-09-10 outage, eight records of three unrelated FAILED lines.
    repository = build_scratch_repository(scratch, "checkout-claude-down")
    result = run_grid(repository, stubs, {"COLD_READ_GRID_TEST_STUB_FAILURE_PLAN": json.dumps(
        [{"fragment": "claude-", "attempts": 2, "stdout": SESSION_LIMIT_LINE}])})
    down_lines = lines_opening(result, "AGENT-BINARY DOWN:")
    check("one AGENT-BINARY DOWN line, naming claude, the class and the reset text",
          down_lines == ["AGENT-BINARY DOWN: claude — account-limit — resets 8:50pm "
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
          and result.stdout.count("AGENT-BINARY DOWN:") == 1, repr(result.stdout))
    check("the closing text ends by telling the user the cause, with the log to check",
          result.stdout.rstrip().splitlines()[-1].startswith(
              "Tell the user: claude account-limit — resets 8:50pm (America/Los_Angeles) (log: ")
          and result.stdout.rstrip().endswith("attempt-2.stderr.log)."),
          repr(result.stdout.rstrip().splitlines()[-1]))
    check("three land, the some-landed text, exit 1",
          result.returncode == 1 and len(lines_opening(result, "saved:")) == 3
          and "3 of 6 reports landed in" in result.stdout,
          f"exit {result.returncode}; stdout={result.stdout!r}")

    # --- The account limit printed bare: an empty detail still names the class
    # The agent-binary printed "You've hit your session limit" with nothing after
    # it, so the cell's cause line ends `account-limit — ` and the grid's
    # strip() took the separator's trailing space with it; partitioning on
    # the full separator then found none, and the class "account-limit —"
    # matched no class the grid knows, losing the AGENT-BINARY DOWN line and
    # the Tell-the-user sentence. Found by the same review as the marker
    # case above:
    # https://github.com/nedschorus/nedschorus/pull/508#pullrequestreview-5252230189
    repository = build_scratch_repository(scratch, "checkout-claude-down-bare-limit")
    result = run_grid(repository, stubs, {"COLD_READ_GRID_TEST_STUB_FAILURE_PLAN": json.dumps(
        [{"fragment": "claude-", "attempts": 2, "stdout": "You've hit your session limit"}])})
    down_lines = lines_opening(result, "AGENT-BINARY DOWN:")
    check("a bare limit text is still one AGENT-BINARY DOWN line naming account-limit",
          len(down_lines) == 1 and result.stdout.count("AGENT-BINARY DOWN:") == 1
          and down_lines[0].startswith("AGENT-BINARY DOWN: claude — account-limit — ")
          and down_lines[0].endswith("; 3 reports absent"),
          f"down lines were {down_lines!r}; stdout={result.stdout!r}")
    check("the user is still told the bare cause",
          "Tell the user: claude account-limit — " in result.stdout, repr(result.stdout))

    # --- Two Claude cells hit the account limit after the third landed -------
    # The rule as the user revised it at item 3 of the design's walk
    # (2026-09-16): the down line prints when a cell becomes absent with an
    # agent-binary-wide class and every other cell of its agent-binary has either
    # LANDED or is absent with the same class -- a report that landed before
    # the limit hit does not stop the agent-binary from being reported down.
    repository = build_scratch_repository(scratch, "checkout-claude-down-after-one-landed")
    result = run_grid(repository, stubs, {"COLD_READ_GRID_TEST_STUB_FAILURE_PLAN": json.dumps(
        [{"fragment": "claude-hunt-second.md", "attempts": 0},
         {"fragment": "claude-", "attempts": 2, "stdout": SESSION_LIMIT_LINE}])})
    check("one landed Claude cell and two absent with the account limit is still claude down",
          lines_opening(result, "AGENT-BINARY DOWN:")
          == ["AGENT-BINARY DOWN: claude — account-limit — resets 8:50pm "
              "(America/Los_Angeles); 2 reports absent"]
          and "- claude is down: account-limit — resets 8:50pm (America/Los_Angeles); 2 reports absent"
          in result.stdout
          and result.returncode == 1 and len(lines_opening(result, "saved:")) == 4,
          f"exit {result.returncode}; stdout={result.stdout!r}")

    # --- All three Claude cells fail with a model limit: no agent-binary is down --
    repository = build_scratch_repository(scratch, "checkout-model-limits")
    result = run_grid(repository, stubs, {"COLD_READ_GRID_TEST_STUB_FAILURE_PLAN": json.dumps(
        [{"fragment": "claude-", "attempts": 2, "stdout": MODEL_LIMIT_LINE}])})
    check("a model limit on every Claude cell is three absences, not an agent-binary down",
          "AGENT-BINARY DOWN:" not in result.stdout and "is down:" not in result.stdout
          and len(lines_opening(result, "- claude-")) == 3, repr(result.stdout))
    check("each absence names model-limit and the model's family",
          any(line.startswith("- claude-hunt-deep: model-limit — Opus (log:")
              for line in result.stdout.splitlines())
          and any(line.startswith("- claude-hunt-second: model-limit — Fable (log:")
                  for line in result.stdout.splitlines()), repr(result.stdout))
    check("the user is told, one cause per agent-binary and class",
          result.stdout.count("Tell the user: claude model-limit — ") == 1, repr(result.stdout))

    # --- First attempts all account-limit; one retry fails otherwise ---------
    repository = build_scratch_repository(scratch, "checkout-mixed-causes")
    result = run_grid(repository, stubs, {"COLD_READ_GRID_TEST_STUB_FAILURE_PLAN": json.dumps(
        [{"fragment": "claude-hunt-second.md", "attempts": 2,
          "stdout_by_attempt": {"1": SESSION_LIMIT_LINE, "2": ""}},
         {"fragment": "claude-", "attempts": 2, "stdout": SESSION_LIMIT_LINE}])})
    retrying_lines = lines_opening(result, "RETRYING:")
    check("three RETRYING lines name account-limit",
          len(retrying_lines) == 3 and all("account-limit" in line for line in retrying_lines),
          repr(retrying_lines))
    check("the retry that failed otherwise is FAILED as exit-1, the others as account-limit",
          any(line.startswith("FAILED (exit 1): claude-hunt-second — exit-1 — ")
              for line in lines_opening(result, "FAILED"))
          and sum("account-limit" in line for line in lines_opening(result, "FAILED")) == 2,
          repr(lines_opening(result, "FAILED")))
    check("differing causes on one agent-binary are three facts, not one down line",
          "AGENT-BINARY DOWN:" not in result.stdout, repr(result.stdout))

    # --- Three Codex cells fail both attempts with exit-N ----------------------
    repository = build_scratch_repository(scratch, "checkout-codex-exits")
    result = run_grid(repository, stubs, {"COLD_READ_GRID_TEST_STUB_FAILURE_PLAN": json.dumps(
        [{"fragment": "codex-", "attempts": 2}])})
    check("three exit-1 absences on codex: listed one by one, no down line, no Tell the user",
          result.returncode == 1 and len(lines_opening(result, "- codex-")) == 3
          and all("exit-1 — " in line for line in lines_opening(result, "- codex-"))
          and "AGENT-BINARY DOWN:" not in result.stdout and "Tell the user:" not in result.stdout,
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
    # agent-binary-wide; the run goes on rather than ending in a traceback.
    repository = build_scratch_repository(scratch, "checkout-unstartable")
    (repository / "nc-systems" / "cold-read" / "cold-read-claude-cell.py").chmod(0o644)
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
    check("program-unstartable says nothing about the agent-binary: no down line",
          "AGENT-BINARY DOWN:" not in result.stdout, repr(result.stdout))
    record_directory = record_directory_of(repository)
    check("the unstartable attempts' logs hold the start error and are kept",
          (record_directory / "claude-hunt-deep.md.attempt-1.stderr.log").is_file()
          and "could not start" in (record_directory / "claude-hunt-deep.md.attempt-2.stderr.log")
          .read_text(encoding="utf-8"),
          sorted(path.name for path in record_directory.glob("*.stderr.log")))

    # --- The target changes during a run that has an absent report ------------
    # The two conditions are independent and land together often enough to
    # write down: the Fable cell fails both attempts (what the account's Fable
    # limit does) while the other five land and edit the frozen copy they read.
    repository = build_scratch_repository(scratch, "checkout-changed-and-absent")
    result = run_grid(
        repository, stubs,
        {"COLD_READ_GRID_TEST_STUB_EDIT_GIVEN_TARGET": "1",
         "COLD_READ_GRID_TEST_STUB_FAILING_MODEL": "claude-fable-5-1",
         **END_OF_RUN_COMPARISON_ONLY},
    )
    check("a run can lose a cell and its target at once: five saved, exit 3",
          result.returncode == 3 and len(lines_opening(result, "saved:")) == 5,
          f"exit {result.returncode}; stdout={result.stdout!r}")
    check("the target-changed text prints, then the absent report",
          "Do not triage any finding in this set" in result.stdout
          and result.stdout.index("Do not triage any finding in this set")
          < result.stdout.index("- claude-hunt-second: exit-1 — "),
          repr(result.stdout))
    check("the changed-target path carries no triage instructions",
          "reports landed in" not in result.stdout and "Read every report in full" not in result.stdout,
          repr(result.stdout))
    record_directory = record_directory_of(repository)
    marked = (record_directory / "claude-hunt-deep.md").read_text(encoding="utf-8").split("\n")
    check("both markers are written, the target-changed marker first, after the stamp",
          marked[0].startswith("<!-- provenance:")
          and marked[1].startswith("<!-- #frozen_copy_changed_during_run")
          and marked[2].startswith("<!-- INCOMPLETE SET: 1 of 6 reports absent"),
          repr(marked[:3]))

    # --- A Codex attempt's output holds the Claude limit text ----------------
    # No Codex text is recognised, so the class is exit-1 whatever the line
    # says, and the run is otherwise the same as that failure without the
    # line: the cause changes what is reported, never what is decided.
    repository = build_scratch_repository(scratch, "checkout-codex-quotes-limit")
    result = run_grid(repository, stubs, {"COLD_READ_GRID_TEST_STUB_FAILURE_PLAN": json.dumps(
        [{"fragment": "codex-terminology-deep.md", "attempts": 2, "stdout": SESSION_LIMIT_LINE}])})
    repository_plain = build_scratch_repository(scratch, "checkout-codex-plain-failure")
    result_plain = run_grid(repository_plain, stubs, {"COLD_READ_GRID_TEST_STUB_FAILURE_PLAN": json.dumps(
        [{"fragment": "codex-terminology-deep.md", "attempts": 2}])})
    check("a Codex failure whose output starts with the Claude limit text is exit-1",
          any(line.startswith("FAILED (exit 1): codex-terminology-deep — exit-1 — ")
              for line in lines_opening(result, "FAILED"))
          and "account-limit" not in result.stdout and "AGENT-BINARY DOWN:" not in result.stdout,
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
        for path in sorted(record_directory.glob("*-terminology-deep.md"))] if record_directory else []
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
          any(line.startswith("RECOVERED: claude-hunt-deep.md")
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
    # each read was. The name function is handed its clock.
    grid_spec = importlib.util.spec_from_file_location(
        "cold_read_grid_under_test", SYSTEM_DIRECTORY / "cold-read-grid.py")
    grid_module = importlib.util.module_from_spec(grid_spec)
    grid_spec.loader.exec_module(grid_module)
    attempt = grid_module.start_attempt(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        scratch / "report.md", 1, scratch / "cell.stderr.log")
    try:
        check("a cell launches in its own process group and session",
              attempt.process is not None
              and os.getpgid(attempt.process.pid) == attempt.process.pid
              and os.getsid(attempt.process.pid) == attempt.process.pid)
    finally:
        if attempt.process is not None:
            grid_module.stop_process_tree(attempt.process, grace_seconds=0.1)
    check("stopping a cell reaps its launcher", attempt.process.returncode is not None)

    for result in (0, subprocess.TimeoutExpired("cell", 5.0)):
        with mock.patch.object(grid_module.os, "killpg") as killed:
            process = mock.Mock(pid=12345)
            process.wait.side_effect = [result, 0]
            grid_module.stop_process_tree(process)
            check("group termination escalates even when the launcher exits",
                  killed.call_args_list == [
                      mock.call(process.pid, grid_module.signal.SIGTERM),
                      mock.call(process.pid, grid_module.signal.SIGKILL)]
                  and process.wait.call_args_list == [mock.call(timeout=5.0), mock.call()])
    process.wait.side_effect = None
    process.wait.reset_mock()
    with mock.patch.object(grid_module.os, "killpg", side_effect=ProcessLookupError):
        grid_module.stop_process_tree(process)
        check("an already absent group still reaps its launcher", process.wait.called)
    process.wait.reset_mock()
    # macOS answers a group whose members have all exited with EPERM.
    with mock.patch.object(grid_module.os, "killpg", side_effect=PermissionError):
        grid_module.stop_process_tree(process)
        check("a group with no live member left still reaps its launcher", process.wait.called)

    # --- The reference pre-pass: a web link is not a path, a bare name is looked up --
    reference_directory = scratch / "reference-pre-pass"
    reference_directory.mkdir()
    reference_target = reference_directory / "target.md"
    reference_target.write_text(
        "See [PR 661](https://github.com/nedschorus/nedschorus/pull/661) and"
        " defect-hunt.md, then no-such-prompt-anywhere.md and"
        " nc-systems/cold-read/no-such-file.py.\n", encoding="utf-8")
    grid_module.reference_integrity_pre_pass(reference_target, reference_directory)
    reference_lines = (reference_directory / "reference-check.md").read_text(
        encoding="utf-8").splitlines()
    check("reference pre-pass: when git lists files, no skipped-lookup line",
          not any("not looked up" in line for line in reference_lines), repr(reference_lines))
    check("reference pre-pass: a web link is not listed as a path",
          not any("github.com" in line for line in reference_lines), repr(reference_lines))
    check("reference pre-pass: a bare file name that a tracked file has is ok",
          "- ok: `defect-hunt.md`" in reference_lines, repr(reference_lines))
    check("reference pre-pass: a bare file name no tracked file has is UNRESOLVED",
          "- UNRESOLVED: `no-such-prompt-anywhere.md`" in reference_lines, repr(reference_lines))
    check("reference pre-pass: a missing path is UNRESOLVED",
          "- UNRESOLVED: `nc-systems/cold-read/no-such-file.py`" in reference_lines,
          repr(reference_lines))
    link_followed_by_path_target = reference_directory / "link-then-path.md"
    link_followed_by_path_target.write_text(
        "[PR 661](https://github.com/nedschorus/nedschorus/pull/661)nc-systems/cold-read/"
        "no-such-file-after-link.py\n", encoding="utf-8")
    grid_module.reference_integrity_pre_pass(link_followed_by_path_target, reference_directory)
    reference_lines = (reference_directory / "reference-check.md").read_text(
        encoding="utf-8").splitlines()
    check("reference pre-pass: a path written straight after a link's closing parenthesis is listed",
          "- UNRESOLVED: `nc-systems/cold-read/no-such-file-after-link.py`" in reference_lines,
          repr(reference_lines))
    existing_file_link = reference_directory / "linked file.md"
    existing_file_link.write_text("linked\n", encoding="utf-8")
    file_link_target = reference_directory / "file-links.md"
    file_link_target.write_text(
        f"[ok](file://{str(existing_file_link).replace(' ', '%20')}) and"
        f" [broken](file://{reference_directory}/no-such-linked-file.md)\n",
        encoding="utf-8")
    grid_module.reference_integrity_pre_pass(file_link_target, reference_directory)
    reference_lines = (reference_directory / "reference-check.md").read_text(
        encoding="utf-8").splitlines()
    check("reference pre-pass: a file link to an existing file is ok",
          f"- ok: `{existing_file_link}`" in reference_lines, repr(reference_lines))
    check("reference pre-pass: a file link to a missing file is UNRESOLVED",
          f"- UNRESOLVED: `{reference_directory}/no-such-linked-file.md`" in reference_lines,
          repr(reference_lines))
    with mock.patch.object(grid_module, "NED_BOX_HOME", str(reference_directory) + "/"):
        mac_link_target = reference_directory / "mac-link.md"
        mac_link_target.write_text(
            "[mac](file:///Volumes/nedhome/linked%20file.md) and"
            " [broken mount](file:///Volumes/nedhome/no-such-directory-under-the-home/x.md) and"
            f" [missing home file](file://{reference_directory}/no-such-home-file.md)\n",
            encoding="utf-8")
        grid_module.reference_integrity_pre_pass(mac_link_target, reference_directory)
    reference_lines = (reference_directory / "reference-check.md").read_text(
        encoding="utf-8").splitlines()
    check("reference pre-pass: a /Volumes/nedhome file link read on ned-box resolves under the home",
          "- ok: `/Volumes/nedhome/linked file.md`" in reference_lines, repr(reference_lines))
    check("reference pre-pass: a broken /Volumes/nedhome file link read on ned-box is UNRESOLVED",
          "- UNRESOLVED: `/Volumes/nedhome/no-such-directory-under-the-home/x.md`"
          in reference_lines, repr(reference_lines))
    check("reference pre-pass: a missing file under a home this machine has is UNRESOLVED, not uncheckable",
          f"- UNRESOLVED: `{reference_directory}/no-such-home-file.md`" in reference_lines,
          repr(reference_lines))
    linked_file = reference_directory / "linked-for-cleanup.md"
    linked_file.write_text("x\n", encoding="utf-8")
    cleanup_target = reference_directory / "link-cleanup.md"
    cleanup_target.write_text(
        f"[part](file://{linked_file}#a-section) and see file://{linked_file}.\n"
        "[other machine](file:///no-such-top-directory-for-the-grid-test/el/x.md)\n"
        f"[missing here](file:///tmp/no-such-directory-for-the-grid-test-{os.getpid()}/x.md)"
        f" and [placeholder](file://{reference_directory}/...)\n"
        f"or see file://{reference_directory}/elided/..., then\n",
        encoding="utf-8")
    with mock.patch.object(grid_module, "MAC_HOME", "/no-such-top-directory-for-the-grid-test/el/"):
        grid_module.reference_integrity_pre_pass(cleanup_target, reference_directory)
    reference_lines = (reference_directory / "reference-check.md").read_text(
        encoding="utf-8").splitlines()
    check("reference pre-pass: a file link with a #fragment resolves to its file",
          f"- ok: `{linked_file}`" in reference_lines
          and not any("#a-section" in line for line in reference_lines), repr(reference_lines))
    check("reference pre-pass: a file link that ends a sentence loses the period",
          not any(f"`{linked_file}.`" in line for line in reference_lines), repr(reference_lines))
    check("reference pre-pass: a file link whose home is not on this machine is not checkable here",
          "- not checkable on this machine: `/no-such-top-directory-for-the-grid-test/el/x.md`"
          in reference_lines, repr(reference_lines))
    check("reference pre-pass: a missing file under a directory this machine has is UNRESOLVED, not uncheckable",
          f"- UNRESOLVED: `/tmp/no-such-directory-for-the-grid-test-{os.getpid()}/x.md`" in reference_lines,
          repr(reference_lines))
    check("reference pre-pass: a ... placeholder link keeps its dots and is not read as its directory",
          f"- UNRESOLVED: `{reference_directory}/...`" in reference_lines
          and f"- ok: `{reference_directory}/`" not in reference_lines, repr(reference_lines))
    check("reference pre-pass: a comma after a ... placeholder link is stripped like any sentence mark",
          f"- UNRESOLVED: `{reference_directory}/elided/...`" in reference_lines
          and not any("...," in line for line in reference_lines), repr(reference_lines))
    other_top_directory = scratch / "reference-pre-pass-other-machine-top"
    other_top_directory.mkdir()
    other_machine_target = reference_directory / "other-machine-links.md"
    other_machine_target.write_text(
        f"[sibling of a home](file://{other_top_directory}/no-such-user/x.md)\n", encoding="utf-8")
    with mock.patch.object(grid_module, "MAC_HOME", str(other_top_directory) + "/el/"):
        grid_module.reference_integrity_pre_pass(other_machine_target, reference_directory)
    reference_lines = (reference_directory / "reference-check.md").read_text(
        encoding="utf-8").splitlines()
    check("reference pre-pass: only the named root of the other machine is not checkable, not its parent's other entries",
          f"- UNRESOLVED: `{other_top_directory}/no-such-user/x.md`" in reference_lines,
          repr(reference_lines))
    mac_mount = scratch / "reference-pre-pass-mac-mount"
    mac_mount.mkdir()
    (mac_mount / "on-the-mac.md").write_text("x\n", encoding="utf-8")
    (reference_directory / "notes#1.md").write_text("x\n", encoding="utf-8")
    mac_view_target = reference_directory / "mac-view.md"
    mac_view_target.write_text(
        f"[mounted](file://{mac_mount}/on-the-mac.md) and"
        f" [escaped](file://{reference_directory}/notes%231.md)\n", encoding="utf-8")
    with mock.patch.object(grid_module, "MAC_MOUNT_OF_NED_BOX_HOME", str(mac_mount) + "/"), \
            mock.patch.object(grid_module, "NED_BOX_HOME", str(scratch / "no-ned-box-home-on-the-mac") + "/"):
        grid_module.reference_integrity_pre_pass(mac_view_target, reference_directory)
    reference_lines = (reference_directory / "reference-check.md").read_text(
        encoding="utf-8").splitlines()
    check("reference pre-pass: a valid mount link read on the Mac is ok, checked as written",
          f"- ok: `{mac_mount}/on-the-mac.md`" in reference_lines, repr(reference_lines))
    check("reference pre-pass: an escaped # in a file link is part of the file name",
          f"- ok: `{reference_directory}/notes#1.md`" in reference_lines, repr(reference_lines))
    unmounted_target = reference_directory / "unmounted.md"
    unmounted_target.write_text(
        f"[unmounted](file://{scratch}/no-mount-here/x.md)\n", encoding="utf-8")
    with mock.patch.object(grid_module, "MAC_MOUNT_OF_NED_BOX_HOME", str(scratch / "no-mount-here") + "/"), \
            mock.patch.object(grid_module, "NED_BOX_HOME", str(scratch / "no-ned-box-home-here") + "/"):
        grid_module.reference_integrity_pre_pass(unmounted_target, reference_directory)
    reference_lines = (reference_directory / "reference-check.md").read_text(
        encoding="utf-8").splitlines()
    check("reference pre-pass: a mount link is not checkable where neither the mount nor ned-box's home is",
          f"- not checkable on this machine: `{scratch}/no-mount-here/x.md`" in reference_lines,
          repr(reference_lines))
    shared_name_target = reference_directory / "shared-name.md"
    shared_name_target.write_text("See SKILL.md.\n", encoding="utf-8")
    grid_module.reference_integrity_pre_pass(shared_name_target, reference_directory)
    reference_lines = (reference_directory / "reference-check.md").read_text(
        encoding="utf-8").splitlines()
    check("reference pre-pass: a bare name that several files share is UNRESOLVED, with the count",
          any(line.startswith("- UNRESOLVED: `SKILL.md` (") and line.endswith(" files have this name)")
              for line in reference_lines), repr(reference_lines))
    untracked_name = "reference-pre-pass-untracked-new-file-for-the-grid-test.md"
    untracked_repository = scratch / "reference-pre-pass-untracked-repository"
    (untracked_repository / "nc-systems").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(untracked_repository)], check=True,
                   env=grid_module.git_redirecting_removal.environment_without_git_redirecting_variables())
    (untracked_repository / "nc-systems" / untracked_name).write_text("new\n", encoding="utf-8")
    bare_untracked_target = reference_directory / "bare-untracked.md"
    bare_untracked_target.write_text(f"See {untracked_name}.\n", encoding="utf-8")
    with mock.patch.object(grid_module, "REPO_ROOT", untracked_repository):
        grid_module.reference_integrity_pre_pass(bare_untracked_target, reference_directory)
    reference_lines = (reference_directory / "reference-check.md").read_text(
        encoding="utf-8").splitlines()
    check("reference pre-pass: a bare name of a new, not yet tracked file is ok",
          f"- ok: `{untracked_name}`" in reference_lines, repr(reference_lines))
    with mock.patch.dict(os.environ, {"GIT_DIR": str(scratch / "no-such-git-directory")}):
        grid_module.reference_integrity_pre_pass(reference_target, reference_directory)
    reference_lines = (reference_directory / "reference-check.md").read_text(
        encoding="utf-8").splitlines()
    check("reference pre-pass: an inherited GIT_DIR does not stop the bare-name lookup",
          "- ok: `defect-hunt.md`" in reference_lines, repr(reference_lines))
    not_a_repository = scratch / "reference-pre-pass-not-a-repository"
    not_a_repository.mkdir()
    with mock.patch.object(grid_module, "REPO_ROOT", not_a_repository):
        grid_module.reference_integrity_pre_pass(reference_target, reference_directory)
    reference_lines = (reference_directory / "reference-check.md").read_text(
        encoding="utf-8").splitlines()
    check("reference pre-pass: when git cannot list files, the check says the lookup was skipped",
          any(line.startswith("- bare file names were not looked up: git ls-files exited 128")
              for line in reference_lines), repr(reference_lines))
    check("reference pre-pass: when git cannot list files, the bare name is still listed",
          "- UNRESOLVED: `defect-hunt.md`" in reference_lines, repr(reference_lines))

    clock_at_1042 = datetime.datetime(2026, 9, 16, 10, 42)

    # Every run in this suite overrides the poll, so no run shows the default.
    cell_poll_parameter = inspect.signature(grid_module.wait_for_cells).parameters.get(
        "cell_poll_interval_seconds")
    check("grid: the cell poll interval's default, and wait_for_cells', is 5 seconds",
          grid_module.CELL_POLL_INTERVAL_DEFAULT_SECONDS == 5
          and cell_poll_parameter is not None and cell_poll_parameter.default == 5,
          f"default {grid_module.CELL_POLL_INTERVAL_DEFAULT_SECONDS!r}, "
          f"parameter {cell_poll_parameter!r}")

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
          (suffixed_record / "claude-hunt-deep.md").is_file()
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
    frozen = frozen_target_path_in_scratch_repository(repository, record_directory)
    check("the target's bytes are frozen under target/ at its repository path",
          frozen.is_file() and frozen.read_bytes() == (repository / TARGET_RELATIVE_PATH).read_bytes(),
          f"{frozen} present={frozen.exists()}")
    check("the frozen copy is read-only",
          frozen.is_file() and (frozen.stat().st_mode & 0o222) == 0,
          oct(frozen.stat().st_mode) if frozen.exists() else "absent")
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
          f"nc-systems/cold-read/cold-read-record-ship.py {record_directory.resolve()}" in result.stdout
          and "gitignored" in result.stdout and "user-ruled 2026-08-14" not in result.stdout,
          result.stdout[-900:])
    check("a settled run that shipped still exits 0",
          result.returncode == 0, f"exit {result.returncode}")

    # --- An incomplete set ships with its marker, so triage.md can follow ----
    # The shipper is add-only and refuses a record whose stored file differs
    # from the local one, so the INCOMPLETE SET marker must be in the reports
    # BEFORE the run ships them: a marker written after the ship left the
    # store's reports without it, and the post-triage ship the closing text
    # asks for was refused, triage.md never reaching the store. Found by
    # the reviewer's review on PR "cold-read-grid: a failed cell is retried
    # once and reported with its cause, and every run closes with one
    # closing text":
    # https://github.com/nedschorus/nedschorus/pull/508#pullrequestreview-5252230189
    repository = build_scratch_repository(scratch, "checkout-incomplete-set-ships-marked")
    result = run_grid(repository, stubs, {"COLD_READ_GRID_TEST_STUB_FAILURE_PLAN": json.dumps(
        [{"fragment": "claude-terminology-deep.md", "attempts": 2}])})
    record_directory = record_directory_of(repository)
    record_lines = [line for line in result.stdout.splitlines() if line.startswith("record: ")]
    check("an incomplete set's run still says record: shipped:",
          len(record_lines) == 1 and record_lines[0].startswith("record: shipped:"),
          f"{record_lines!r}; stderr={result.stderr[-400:]!r}")
    store_copy = repository / SCRATCH_LOG_STORE_RELATIVE / record_directory.name

    def files_under(root):
        return {path.relative_to(root): path.read_bytes()
                for path in sorted(root.rglob("*")) if path.is_file()}

    def ship_again():
        environment = dict(os.environ)
        environment[RECORD_SHIP_DESTINATION_VARIABLE] = str(repository / SCRATCH_LOG_STORE_RELATIVE)
        return subprocess.run(
            [sys.executable, str(repository / "nc-systems" / "cold-read" / "cold-read-record-ship.py"),
             str(record_directory)],
            capture_output=True, text=True, check=False, env=environment)

    second_ship = ship_again()
    check("shipping the marked record again is accepted, not REFUSED",
          second_ship.returncode == 0 and second_ship.stdout.startswith("shipped:"),
          f"exit {second_ship.returncode}; stdout={second_ship.stdout!r}; "
          f"stderr={second_ship.stderr[-400:]!r}")
    check("the store's copy equals the record byte for byte, the marker included",
          store_copy.is_dir() and files_under(store_copy) == files_under(record_directory),
          f"store={sorted(str(p) for p in store_copy.rglob('*'))}")
    stored_report = store_copy / "claude-hunt-deep.md"
    check("the store's copy of a report carries the INCOMPLETE SET marker",
          stored_report.is_file()
          and "<!-- INCOMPLETE SET:" in stored_report.read_text(encoding="utf-8"),
          stored_report.read_text(encoding="utf-8")[:300] if stored_report.is_file() else "absent")
    (record_directory / "triage.md").write_text("# Triage\n\nOne absent report.\n", encoding="utf-8")
    third_ship = ship_again()
    check("triage.md written after the run lands in the store on the next ship",
          third_ship.returncode == 0 and third_ship.stdout.startswith("shipped:")
          and "1 file(s) added" in third_ship.stdout
          and (store_copy / "triage.md").is_file(),
          f"exit {third_ship.returncode}; stdout={third_ship.stdout!r}")

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
          record_directory is not None
          and frozen_target_path_in_scratch_repository(repository, record_directory).is_file())

    # --- A changed target is still shipped: it is evidence -------------------
    repository = build_scratch_repository(scratch, "checkout-changed-still-shipped")
    result = run_grid(repository, stubs, {
        "COLD_READ_GRID_TEST_STUB_EDIT_GIVEN_TARGET": "1",
        **END_OF_RUN_COMPARISON_ONLY})
    record_lines = [line for line in result.stdout.splitlines() if line.startswith("record: ")]
    check("a run whose frozen copy moved ships its marked record and exits 3",
          result.returncode == 3 and record_lines and record_lines[0].startswith("record: shipped:"),
          f"exit {result.returncode}; {record_lines!r}")

    # --- The cells read the frozen copy, never the live document -------------
    # USER-RULED 2026-08-28, "freeze sounds like the right solution", built
    # 2026-09-22. Before it, every cell opened the original, so an edit
    # part-way through a run left some reports describing the old text and
    # some the new. The whole guarantee is this: what the reviewers were
    # handed is a copy nothing outside the record can reach.
    repository = build_scratch_repository(scratch, "checkout-cells-read-the-copy")
    target_log = scratch / "cells-read-the-copy-targets.log"
    result = run_grid(repository, stubs,
                      {"COLD_READ_GRID_TEST_STUB_TARGET_LOG": str(target_log)})
    logged = target_log.read_text(encoding="utf-8").splitlines() if target_log.is_file() else []
    record_directory = record_directory_of(repository)
    frozen = frozen_target_path_in_scratch_repository(repository, record_directory)
    check("every cell was given a path, and there is one per cell",
          len(logged) == 6, f"{len(logged)} logged: {logged!r}")
    # Resolved before comparing: on macOS the scratch tree lives under /tmp,
    # which is a symbolic link to /private/tmp, and the grid resolves the
    # cold-read-target before freezing it — so the same file is spelled two
    # ways and a string comparison fails on a run that is correct.
    logged_resolved = {Path(path).resolve() for path in logged}
    check("every cell was given the frozen copy inside the record",
          logged != [] and logged_resolved == {frozen.resolve()},
          f"expected {frozen.resolve()}, logged {sorted(logged_resolved)!r}")
    check("no cell was given the live document",
          (repository / TARGET_RELATIVE_PATH).resolve() not in logged_resolved,
          f"logged {sorted(logged_resolved)!r}")

    # --- Relative references resolve from the original's directory ----------
    # Only the document is copied into the record, so a link it makes to a
    # sibling -- `../issues/x.md` -- reaches nothing beside the copy. Both
    # reviews of 2026-09-23 blocked on this: the cells lost the context the
    # author linked, while the reference pre-pass, which resolves against the
    # original, marked the same links ok. Each prompt must name the original
    # and its directory as the place relative references resolve from.
    repository = build_scratch_repository(scratch, "checkout-cells-told-the-origin")
    prompt_log = scratch / "cells-told-the-origin-prompts.log"
    result = run_grid(repository, stubs,
                      {"COLD_READ_GRID_TEST_STUB_PROMPT_LOG": str(prompt_log)})
    prompts = ([json.loads(line) for line in prompt_log.read_text(encoding="utf-8").splitlines()]
               if prompt_log.is_file() else [])
    original = (repository / TARGET_RELATIVE_PATH).resolve()
    record_directory = record_directory_of(repository)
    frozen = frozen_target_path_in_scratch_repository(repository, record_directory).resolve()

    def names_path(prompt, path):
        # Either spelling: the grid resolves the target, the scratch path may
        # be reached through a symbolic link.
        return any(str(candidate) in prompt
                   for candidate in {path, Path(os.path.realpath(path))})

    check("every cell's prompt names the original as what the copy was frozen from",
          len(prompts) == 6 and all(
              names_path(prompt, frozen) and names_path(prompt, original)
              and "is a frozen copy of" in prompt for prompt in prompts),
          f"{len(prompts)} prompts; first={prompts[:1]!r}")
    check("every cell's prompt says relative references resolve from the original's directory",
          len(prompts) == 6 and all(
              f"from {original.parent}, the original's directory" in prompt
              for prompt in prompts),
          f"expected directory {original.parent}; first={prompts[:1]!r}")
    root_phrase = f"from the repository root, {repository.resolve()},"
    check("every cell's prompt resolves a path from the repository root before the original's directory",
          len(prompts) == 6 and all(
              root_phrase in prompt
              and prompt.index(root_phrase)
              < prompt.index(f"from {original.parent}, the original's directory")
              for prompt in prompts),
          f"expected root {repository.resolve()}; first={prompts[:1]!r}")

    # --- An edit to the COPY is caught, which is where the risk moved --------
    # The records tree is gitignored, so the cell's own stray-write detector
    # cannot see an edit to the copy: `git status` never mentions it. That is
    # why the run fingerprints the copy as well as the original. The stub
    # forces the read-only mode off first — the mode bit stops an accident,
    # and this case is about the detector behind it.
    repository = build_scratch_repository(scratch, "checkout-copy-edited")
    result = run_grid(repository, stubs,
                      {"COLD_READ_GRID_TEST_STUB_EDIT_GIVEN_TARGET": "1",
                       **END_OF_RUN_COMPARISON_ONLY})
    record_directory = record_directory_of(repository)
    frozen = frozen_target_path_in_scratch_repository(repository, record_directory)
    check("an edit to the frozen copy is reported and the run exits 3",
          result.returncode == 3
          and result.stdout.count("#frozen_copy_changed_during_run") == 1,
          f"exit {result.returncode}; stdout={result.stdout!r}")
    # Resolved before comparing, as the two checks in the case above are: the
    # grid resolves the cold-read-target before freezing it, so on a machine
    # whose temporary directory is reached through a symbolic link the same
    # file is spelled two ways and a correct run fails this check. On a Mac
    # the unresolved spelling happens to be a substring of the resolved one
    # (/private/tmp/x contains /tmp/x), which is why this passed here and
    # failed on ned-box under a symbolic-link TMPDIR.
    check("the line names the copy that changed, not the untouched original",
          str(frozen.resolve()) in result.stdout
          and b"edit to the document it was given" in frozen.read_bytes(),
          repr([line for line in result.stdout.splitlines()
                if line.startswith("#frozen_copy_changed_during_run")]))
    check("the original is untouched while the copy is what moved",
          b"edit to the document it was given"
          not in (repository / TARGET_RELATIVE_PATH).read_bytes())
    # The copy is what the cells read, so a copy that moved leaves exactly the
    # unknown the marker was written for: the edit may have landed before a
    # given cell opened it or after. This is the one case that keeps that
    # sentence, and the case above is the one that must not have it.
    check("a moved copy does leave which text was reviewed unknown",
          "which version any one report reviews is unknown"
          in result.stdout, repr(result.stdout))

    # --- The original and the frozen copy both change ------------------------
    # The original-changed line must not vouch for a copy that moved too.
    both_directory = scratch / "original-and-copy-changed"
    both_directory.mkdir()
    original = both_directory / "document.md"
    original.write_text("launch-time text\n", encoding="utf-8")
    launch_sha256 = hashlib.sha256(original.read_bytes()).hexdigest()
    original.write_text("edited text\n", encoding="utf-8")
    copy = both_directory / "frozen-document.md"
    line = grid_module.original_changed_line(original, copy, launch_sha256, True)
    check("an original changed beside a moved copy does not say the copy stood",
          line.startswith("#cold_read_target_changed_during_run")
          and "did not change" not in line and "the set stands" not in line
          and str(copy) in line and "#frozen_copy_changed_during_run" in line, repr(line))
    line = grid_module.original_changed_line(original, copy, launch_sha256, False)
    check("an original changed beside a still copy says the set stands",
          "which did not change, so the set stands" in line, repr(line))

    # --- The third stop in a row ends the attempt ----------------------------
    # The marker detail is printed and written into every report on every stop,
    # so it must leave whether to start a new run to the stop-count line.
    detail_directory = scratch / "frozen-copy-detail"
    detail_directory.mkdir()
    (detail_directory / "report.md").write_text("report\n", encoding="utf-8")
    detail = grid_module.mark_reports_target_changed(
        detail_directory, detail_directory / "frozen-document.md", "a" * 64, "b" * 64)
    check("the frozen-copy detail leaves starting a new run to the stop-count line",
          "new cold-read run" not in detail.lower(), repr(detail))
    spaced = Path("/tmp/read me/record")
    instructions = grid_module.target_changed_instructions(
        spaced, spaced / "target" / "read me.md", Path("/tmp/read me.md"),
        grid_module.WINDOW_SEEN_AT_END)
    diff_command = instructions.split("as in `", 1)[1].split("`", 1)[0]
    check("the closing text's diff command keeps a path with a space as one operand",
          shlex.split(diff_command) == ["diff", "/tmp/read me.md", "/tmp/read me/record/target/read me.md"],
          repr(diff_command))
    line = grid_module.frozen_copy_stop_count_line(3)
    check("the third stop in a row says not to start a new run and to tell the user",
          "do not start a new cold-read run" in line and "Tell the user" in line
          and "Start a new cold-read run" not in line, repr(line))
    line = grid_module.frozen_copy_stop_count_line(2)
    check("the second stop in a row still asks for a new run",
          line.startswith("Start a new cold-read run once") and "stop 2 of 3" in line, repr(line))

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
    # This run's copy moved, so its record also holds the stop marker file.
    check("beside them, the record holds only the frozen target directory and the stop marker",
          sorted(path.name for path in record_directory.iterdir()
                 if not path.name.endswith(".md"))
          == ["frozen-copy-changed-during-run-stop-marker.txt", "target"])
    expected_names = sorted(
        ["reference-check.md", "frozen-copy-changed-during-run-stop-marker.txt"]
        + [f"{runtime}-{pass_token}-{tier}.md"
           for runtime in ("claude", "codex")
           for pass_token, tier in (("hunt", "deep"), ("hunt", "second"),
                                    ("terminology", "deep"))])
    check("the set holds the six cells, the reference-integrity pre-pass and the stop marker",
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

    # --- A bare file name with more than one dot keeps its whole name --------
    # The bare-name alternative matched only one word before the extension,
    # so `CLAUDE.local.md` was cut to `local.md` and reported UNRESOLVED.
    # User-approved 2026-09-17, backlog-recheck walk item 1, fix 4.
    repository = build_scratch_repository(scratch, "multi-dot-file-name-reference")
    (repository / "CLAUDE.local.md").write_text("# Local\n", encoding="utf-8")
    (repository / "notes.md").write_text("# Notes\n", encoding="utf-8")
    (repository / TARGET_RELATIVE_PATH).write_text(
        "# Target\n\nThe seat's rules are in `CLAUDE.local.md`, and a sentence\n"
        "can end on it: CLAUDE.local.md. A one-dot name still reads: notes.md.\n",
        encoding="utf-8")
    run_grid(repository, stubs / "multi-dot-file-name-reference")
    record_directory = record_directory_of(repository)
    reference_check = (
        record_directory / "reference-check.md"
    ).read_text(encoding="utf-8")
    check("a bare file name with two dots resolves with its whole name",
          "- ok: `CLAUDE.local.md`" in reference_check, reference_check)
    check("a bare file name with one dot still resolves",
          "- ok: `notes.md`" in reference_check, reference_check)
    check("and no truncated name is listed",
          "`local.md`" not in reference_check
          and "UNRESOLVED" not in reference_check, reference_check)


    # --- At most three cold-read-full-runs of a document ---------------------
    # A design had six full runs, each drawing about as many findings as the
    # last; the user ruled that a document gets three, then he decides.
    repository = build_scratch_repository(scratch, "full-run-count-first")
    result = run_grid(repository, stubs / "full-run-count-first")
    check("a document's first full run is announced as 1 of 3",
          "cold-read-full-run 1 of 3 for cold-read-grid-test-target.md." in result.stdout
          and result.returncode == 0, f"exit {result.returncode}; stdout={result.stdout!r}")

    repository = build_scratch_repository(scratch, "full-run-count-refused")
    for day in ("2026-09-01", "2026-09-02"):
        seed_log_store_record(repository, f"cold-read-grid-test-target-{day}",
                              ["claude-hunt-deep.md", "reference-check.md"])
    # A run whose shipping failed is only in the checkout, and counts.
    seed_log_store_record(repository, "cold-read-grid-test-target-2026-09-03",
                          ["codex-hunt-deep.md"], tree=Path("cold-read-records"))
    # A fast read of the same document, and a full run of a document with the
    # same file name in another directory, do not count.
    seed_log_store_record(repository, "cold-read-grid-test-target-2026-09-04", ["fast-read.md"])
    seed_log_store_record(repository, "cold-read-grid-test-target-2026-09-05",
                          ["claude-hunt-deep.md"],
                          frozen_relative="docs/other/cold-read-grid-test-target.md")
    result = run_grid(repository, stubs / "full-run-count-refused")
    check("a fourth full run is refused with exit 2 and the three earlier records named",
          result.returncode == 2 and "refusing cold-read-full-run 4" in result.stderr
          and "cold-read-grid-test-target-2026-09-03" in result.stderr
          and "2026-09-04" not in result.stderr and "2026-09-05" not in result.stderr,
          f"exit {result.returncode}; stderr={result.stderr!r}")
    check("the refusal tells the agent what to do on each of the user's answers",
          "--user-ruled-cold-read-full-run-count-restart" in result.stderr
          and "If the user rules to stop" in result.stderr, result.stderr)
    check("a refused run creates no record and launches no reviewer",
          sorted(p.name for p in (repository / "cold-read-records").iterdir())
          == ["cold-read-grid-test-target-2026-09-03"] and "saved:" not in result.stdout,
          f"records {sorted((repository / 'cold-read-records').iterdir())}; stdout={result.stdout!r}")

    flagged = run_grid(repository, stubs / "full-run-count-refused",
                       extra_arguments=["--user-ruled-cold-read-full-run-count-restart"])
    marked_record = record_directory_of(repository)
    check("the user's ruling runs a fourth as 1 of 3 and marks its record",
          flagged.returncode == 0
          and "cold-read-full-run 1 of 3 for" in flagged.stdout
          and marked_record is not None
          and (marked_record / "user-ruled-cold-read-full-run-count-restart-marker.txt").is_file(),
          f"exit {flagged.returncode}; stdout={flagged.stdout!r}; stderr={flagged.stderr!r}")
    result = run_grid(repository, stubs / "full-run-count-refused",
                      {RECORD_CLOCK_OVERRIDE_VARIABLE: "2026-09-17T10:42"})
    check("the marked record starts the count again: the next run is 2 of 3",
          result.returncode == 0 and "cold-read-full-run 2 of 3 for" in result.stdout,
          f"exit {result.returncode}; stdout={result.stdout!r}; stderr={result.stderr!r}")

    # A renamed document keeps the runs it had under its earlier file name.
    repository = build_scratch_repository(scratch, "full-run-count-renamed")
    earlier_relative = "docs/drafts/earlier-name-of-the-target.md"
    subprocess.run(["git", "-C", str(repository), "mv", TARGET_RELATIVE_PATH, earlier_relative],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repository), "commit", "-q", "-m", "rename to the earlier name"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repository), "mv", earlier_relative, TARGET_RELATIVE_PATH],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repository), "commit", "-q", "-m", "rename back"],
                   check=True, capture_output=True)
    for day in ("2026-09-01", "2026-09-02", "2026-09-03"):
        seed_log_store_record(repository, f"earlier-name-of-the-target-{day}",
                              ["codex-hunt-deep.md"], frozen_relative=earlier_relative)
    result = run_grid(repository, stubs / "full-run-count-renamed")
    check("runs under a document's earlier file name count toward its three",
          result.returncode == 2 and "earlier-name-of-the-target-2026-09-03" in result.stderr,
          f"exit {result.returncode}; stderr={result.stderr!r}")

    # Runs of an earlier change, made before main last took the document, do
    # not count toward the change in hand.
    repository = build_scratch_repository(scratch, "full-run-count-earlier-change")
    subprocess.run(["git", "-C", str(repository), "update-ref", "refs/remotes/origin/main", "HEAD"],
                   check=True, capture_output=True)
    landed_at = int(subprocess.run(
        ["git", "-C", str(repository), "log", "-1", "--format=%ct"],
        check=True, capture_output=True, text=True).stdout)
    for day in ("2026-09-01", "2026-09-02", "2026-09-03"):
        seed_log_store_record(repository, f"cold-read-grid-test-target-{day}",
                              ["claude-hunt-deep.md"], written_at=landed_at - 3600)
    seed_log_store_record(repository, "cold-read-grid-test-target-2026-09-04",
                          ["claude-hunt-deep.md"], written_at=landed_at + 3600)
    result = run_grid(repository, stubs / "full-run-count-earlier-change")
    check("only runs written after main last took the document count",
          result.returncode == 0 and "cold-read-full-run 2 of 3 for" in result.stdout,
          f"exit {result.returncode}; stdout={result.stdout!r}; stderr={result.stderr!r}")

    # A fast read of a document whose stem starts claude- saves its
    # sentence-id copy as claude-...-with-sentence-ids.md, a name a grid
    # report also matches; that copy is not a report.
    repository = build_scratch_repository(scratch, "full-run-count-fast-read-claude-stem")
    claude_stem_relative = "docs/drafts/claude-notes.md"
    write_target(repository, claude_stem_relative)
    for day in ("2026-09-01", "2026-09-02", "2026-09-03"):
        seed_log_store_record(repository, f"claude-notes-{day}",
                              ["fast-read.md", "claude-notes-with-sentence-ids.md"],
                              frozen_relative=claude_stem_relative)
    result = run_grid(repository, stubs / "full-run-count-fast-read-claude-stem",
                      target_relative_path=claude_stem_relative)
    check("a fast read's sentence-id copy of a claude- document does not count as a full run",
          result.returncode == 0 and "cold-read-full-run 1 of 3 for claude-notes.md." in result.stdout,
          f"exit {result.returncode}; stdout={result.stdout!r}; stderr={result.stderr!r}")

    # The Mac's find has no -printf; listing this checkout's records must not need it.
    repository = build_scratch_repository(scratch, "full-run-count-find-without-printf")
    find_stub_directory = stubs / "full-run-count-find-without-printf"
    find_stub_directory.mkdir(parents=True, exist_ok=True)
    real_find = shutil.which("find")
    (find_stub_directory / "find").write_text(
        "#!/bin/sh\nfor argument in \"$@\"; do\n"
        "  if [ \"$argument\" = -printf ]; then echo 'find: -printf: unknown primary or operator' >&2; exit 1; fi\n"
        f"done\nexec {real_find} \"$@\"\n", encoding="utf-8")
    (find_stub_directory / "find").chmod(0o755)
    for day in ("2026-09-01", "2026-09-02", "2026-09-03"):
        seed_log_store_record(repository, f"cold-read-grid-test-target-{day}",
                              ["claude-hunt-deep.md"], tree=Path("cold-read-records"))
    result = run_grid(repository, find_stub_directory)
    check("with a find that has no -printf, the records are still counted and a fourth run refused",
          result.returncode == 2 and "refusing cold-read-full-run 4" in result.stderr,
          f"exit {result.returncode}; stdout={result.stdout!r}; stderr={result.stderr!r}")

    # A change merged from a topic branch lands at the merge, not at the
    # topic's commit: runs between the two reviewed that change and do not count.
    repository = build_scratch_repository(scratch, "full-run-count-merged-topic")
    git_in = lambda *arguments, when=None: subprocess.run(
        ["git", "-C", str(repository), *arguments], check=True, capture_output=True,
        env={**os.environ, **({"GIT_COMMITTER_DATE": f"@{when} +0000",
                               "GIT_AUTHOR_DATE": f"@{when} +0000"} if when else {})})
    topic_committed_at = int(time.time()) - 20000
    git_in("checkout", "-q", "-b", "topic")
    (repository / TARGET_RELATIVE_PATH).write_text("# Target\n\nA topic change.\n", encoding="utf-8")
    git_in("commit", "-q", "-am", "topic change", when=topic_committed_at)
    git_in("checkout", "-q", "main")
    git_in("merge", "-q", "--no-ff", "-m", "merge topic", "topic", when=topic_committed_at + 10000)
    git_in("update-ref", "refs/remotes/origin/main", "HEAD")
    for offset, day in ((1000, "2026-09-01"), (2000, "2026-09-02"), (3000, "2026-09-03")):
        seed_log_store_record(repository, f"cold-read-grid-test-target-{day}",
                              ["claude-hunt-deep.md"], written_at=topic_committed_at + offset)
    result = run_grid(repository, stubs / "full-run-count-merged-topic")
    check("runs made before the merge that landed the change do not count",
          result.returncode == 0 and "cold-read-full-run 1 of 3 for" in result.stdout,
          f"exit {result.returncode}; stdout={result.stdout!r}; stderr={result.stderr!r}")

    # A run on the user's ruling whose every cell failed leaves its marker and
    # no report; the ruling still starts the count again.
    repository = build_scratch_repository(scratch, "full-run-count-marker-without-report")
    now = int(time.time())
    for offset, day in ((7200, "2026-09-01"), (6000, "2026-09-02"), (4800, "2026-09-03")):
        seed_log_store_record(repository, f"cold-read-grid-test-target-{day}",
                              ["claude-hunt-deep.md"], written_at=now - offset)
    seed_log_store_record(repository, "cold-read-grid-test-target-2026-09-04",
                          ["user-ruled-cold-read-full-run-count-restart-marker.txt"],
                          written_at=now - 3600)
    result = run_grid(repository, stubs / "full-run-count-marker-without-report")
    check("a marker in a record with no report still restarts the count",
          result.returncode == 0 and "cold-read-full-run 1 of 3 for" in result.stdout,
          f"exit {result.returncode}; stdout={result.stdout!r}; stderr={result.stderr!r}")

    # Inside design-to-main a writer's cold reads are bounded by the machine's
    # own two rounds: such a run is neither counted nor refused, and its record
    # never counts toward the three outside the machine.
    repository = build_scratch_repository(scratch, "full-run-count-skipped-inside-design-to-main")
    for day in ("2026-09-01", "2026-09-02", "2026-09-03"):
        seed_log_store_record(repository, f"cold-read-grid-test-target-{day}", ["claude-hunt-deep.md"])
    skipped = run_grid(repository, stubs / "full-run-count-skipped-inside-design-to-main",
                       extra_arguments=["--cold-read-full-run-count-skipped-inside-design-to-main"])
    skipped_record = record_directory_of(repository)
    check("inside design-to-main a fourth run goes ahead and says its count was skipped",
          skipped.returncode == 0
          and "cold-read-full-run count skipped for cold-read-grid-test-target.md: "
              "this run is inside design-to-main." in skipped.stdout
          and "cold-read-full-run 4" not in skipped.stdout + skipped.stderr,
          f"exit {skipped.returncode}; stdout={skipped.stdout!r}; stderr={skipped.stderr!r}")
    check("and its record holds the skip marker",
          skipped_record is not None
          and (skipped_record / "cold-read-full-run-count-skipped-inside-design-to-main-marker.txt").is_file(),
          f"record {skipped_record}")
    result = run_grid(repository, stubs / "full-run-count-skipped-inside-design-to-main",
                      {RECORD_CLOCK_OVERRIDE_VARIABLE: "2026-09-17T10:42"})
    check("a later run outside design-to-main is still refused, naming only the three counted runs",
          result.returncode == 2 and "refusing cold-read-full-run 4" in result.stderr
          and skipped_record.name not in result.stderr,
          f"exit {result.returncode}; stderr={result.stderr!r}")

    repository = build_scratch_repository(scratch, "full-run-count-skip-marker-not-counted")
    seed_log_store_record(repository, "cold-read-grid-test-target-2026-09-01", ["claude-hunt-deep.md"])
    for day in ("2026-09-02", "2026-09-03"):
        seed_log_store_record(repository, f"cold-read-grid-test-target-{day}",
                              ["claude-hunt-deep.md",
                               "cold-read-full-run-count-skipped-inside-design-to-main-marker.txt"])
    result = run_grid(repository, stubs / "full-run-count-skip-marker-not-counted")
    check("records holding the skip marker do not count: one counted run makes this 2 of 3",
          result.returncode == 0 and "cold-read-full-run 2 of 3 for" in result.stdout,
          f"exit {result.returncode}; stdout={result.stdout!r}; stderr={result.stderr!r}")

    # A run stopped because its frozen copy moved does not count toward the
    # three, so the new run the stop asks for is never refused as a fourth;
    # three such stops in a row end the attempt instead.
    stop_marker = "frozen-copy-changed-during-run-stop-marker.txt"
    repository = build_scratch_repository(scratch, "full-run-count-stops-not-counted")
    for index, day in enumerate(("2026-09-01", "2026-09-02")):
        seed_log_store_record(repository, f"cold-read-grid-test-target-{day}",
                              ["claude-hunt-deep.md"], written_at=1_800_000_000 + index)
    seed_log_store_record(repository, "cold-read-grid-test-target-2026-09-03",
                          ["claude-hunt-deep.md", stop_marker], written_at=1_800_000_010)
    result = run_grid(repository, stubs / "full-run-count-stops-not-counted")
    check("a record holding the stop marker does not count: two counted runs make this 3 of 3",
          result.returncode == 0 and "cold-read-full-run 3 of 3 for" in result.stdout,
          f"exit {result.returncode}; stdout={result.stdout!r}; stderr={result.stderr!r}")

    repository = build_scratch_repository(scratch, "full-run-count-three-stops-in-a-row")
    seed_log_store_record(repository, "cold-read-grid-test-target-2026-09-01",
                          ["claude-hunt-deep.md"], written_at=1_800_000_000)
    for index, day in enumerate(("2026-09-02", "2026-09-03", "2026-09-04")):
        seed_log_store_record(repository, f"cold-read-grid-test-target-{day}",
                              ["claude-hunt-deep.md", stop_marker],
                              written_at=1_800_000_010 + index)
    result = run_grid(repository, stubs / "full-run-count-three-stops-in-a-row")
    check("after three stops in a row the next run is refused with exit 2 and told to tell the user",
          result.returncode == 2
          and "its last 3 cold-read-full-runs in a row stopped because the frozen copy changed"
          in result.stderr and "Tell the user" in result.stderr
          and "--user-ruled-cold-read-full-run-count-restart" in result.stderr
          and not (repository / "cold-read-records").exists(),
          f"exit {result.returncode}; stderr={result.stderr!r}")
    flagged = run_grid(repository, stubs / "full-run-count-three-stops-in-a-row",
                       extra_arguments=["--user-ruled-cold-read-full-run-count-restart"])
    check("the user's ruling lets a run go ahead after three stops in a row",
          flagged.returncode == 0 and "cold-read-full-run 1 of 3 for" in flagged.stdout,
          f"exit {flagged.returncode}; stdout={flagged.stdout!r}; stderr={flagged.stderr!r}")

    repository = build_scratch_repository(scratch, "full-run-count-stops-broken-by-a-counted-run")
    for index, (day, extra) in enumerate((("2026-09-01", [stop_marker]),
                                          ("2026-09-02", [stop_marker]),
                                          ("2026-09-03", []),
                                          ("2026-09-04", [stop_marker]))):
        seed_log_store_record(repository, f"cold-read-grid-test-target-{day}",
                              ["claude-hunt-deep.md", *extra], written_at=1_800_000_000 + index)
    result = run_grid(repository, stubs / "full-run-count-stops-broken-by-a-counted-run")
    check("a counted run between stops breaks the row: three stops in all are not three in a row",
          result.returncode == 0 and "cold-read-full-run 2 of 3 for" in result.stdout,
          f"exit {result.returncode}; stdout={result.stdout!r}; stderr={result.stderr!r}")

    repository = build_scratch_repository(scratch, "full-run-count-both-flags-refused")
    result = run_grid(repository, stubs / "full-run-count-both-flags-refused",
                      extra_arguments=["--cold-read-full-run-count-skipped-inside-design-to-main",
                                       "--user-ruled-cold-read-full-run-count-restart"])
    records_tree = repository / "cold-read-records"
    check("both flags together are refused with exit 2, naming both, and create no record",
          result.returncode == 2
          and "--cold-read-full-run-count-skipped-inside-design-to-main" in result.stderr
          and "--user-ruled-cold-read-full-run-count-restart" in result.stderr
          and (not records_tree.exists() or not any(records_tree.iterdir()))
          and "saved:" not in result.stdout,
          f"exit {result.returncode}; stdout={result.stdout!r}; stderr={result.stderr!r}")

    # A document renamed on a branch main has not taken: main last took it
    # under its earlier name, and runs from before that do not count.
    repository = build_scratch_repository(scratch, "full-run-count-renamed-unmerged")
    later_relative = "docs/drafts/later-name-of-the-target.md"
    git_in = lambda *arguments: subprocess.run(
        ["git", "-C", str(repository), *arguments], check=True, capture_output=True)
    git_in("update-ref", "refs/remotes/origin/main", "HEAD")
    landed_at = int(subprocess.run(["git", "-C", str(repository), "log", "-1", "--format=%ct"],
                                   check=True, capture_output=True, text=True).stdout)
    git_in("mv", TARGET_RELATIVE_PATH, later_relative)
    git_in("commit", "-q", "-m", "renamed on the branch")
    for day in ("2026-09-01", "2026-09-02", "2026-09-03"):
        seed_log_store_record(repository, f"cold-read-grid-test-target-{day}",
                              ["codex-hunt-deep.md"], written_at=landed_at - 3600)
    result = run_grid(repository, stubs / "full-run-count-renamed-unmerged",
                      target_relative_path=later_relative)
    check("runs under the earlier name from before main took it do not count after a rename main lacks",
          result.returncode == 0 and "cold-read-full-run 1 of 3 for" in result.stdout,
          f"exit {result.returncode}; stdout={result.stdout!r}; stderr={result.stderr!r}")

    # An interrupted shipment's staging copy beside its record is not a second run.
    repository = build_scratch_repository(scratch, "full-run-count-staging-copy")
    for name in ("cold-read-grid-test-target-2026-09-01", "cold-read-grid-test-target-2026-09-02",
                 ".ship-staging-cold-read-grid-test-target-2026-09-02-a1b2c3d4e5f6"):
        seed_log_store_record(repository, name, ["claude-hunt-deep.md"])
    result = run_grid(repository, stubs / "full-run-count-staging-copy")
    check("a shipment's staging copy does not count as a run",
          result.returncode == 0 and "cold-read-full-run 3 of 3 for" in result.stdout,
          f"exit {result.returncode}; stdout={result.stdout!r}; stderr={result.stderr!r}")

    # A record directory that cannot be read is reported, not skipped: skipping
    # it would count fewer runs and lift the limit without saying so.
    repository = build_scratch_repository(scratch, "full-run-count-record-unreadable")
    for day in ("2026-09-01", "2026-09-02", "2026-09-03"):
        seed_log_store_record(repository, f"cold-read-grid-test-target-{day}", ["claude-hunt-deep.md"])
    unreadable_record = repository / SCRATCH_LOG_STORE_RELATIVE / "cold-read-grid-test-target-2026-09-03"
    unreadable_record.chmod(0o000)
    try:
        result = run_grid(repository, stubs / "full-run-count-record-unreadable")
    finally:
        unreadable_record.chmod(0o755)
    check("an unreadable record directory is reported as EARLIER COLD-READ-FULL-RUNS NOT COUNTED",
          result.returncode == 0 and "EARLIER COLD-READ-FULL-RUNS NOT COUNTED:" in result.stdout
          and " of 3 for " not in result.stdout,
          f"exit {result.returncode}; stdout={result.stdout!r}; stderr={result.stderr!r}")

    # A log-store that cannot be listed does not stop the read, as with
    # shipping, and the run says it went uncounted rather than counting zero.
    repository = build_scratch_repository(scratch, "full-run-count-store-unreadable")
    result = run_grid(repository, stubs / "full-run-count-store-unreadable",
                      {RECORD_SHIP_DESTINATION_VARIABLE: str(scratch / "no-such-log-store")})
    check("an unlistable log-store is reported as EARLIER COLD-READ-FULL-RUNS NOT COUNTED and the read goes ahead",
          result.returncode == 0 and "EARLIER COLD-READ-FULL-RUNS NOT COUNTED:" in result.stdout
          and "no-such-log-store" in result.stdout and " of 3 for " not in result.stdout
          and len([line for line in result.stdout.splitlines() if line.startswith("saved:")]) == 6,
          f"exit {result.returncode}; stdout={result.stdout!r}")

    # A git history that cannot be read is reported the same way: a
    # repository with no commit has a top level but no log.
    repository = build_scratch_repository(scratch, "full-run-count-history-unreadable")
    empty_repository = scratch / "repository-without-commits"
    subprocess.run(["git", "init", "-q", str(empty_repository)], check=True)
    uncommitted_target = empty_repository / "uncommitted-target.md"
    uncommitted_target.write_text("# Target\n", encoding="utf-8")
    result = run_grid(repository, stubs / "full-run-count-history-unreadable",
                      target_relative_path=str(uncommitted_target))
    check("an unreadable git history is reported as EARLIER COLD-READ-FULL-RUNS NOT COUNTED",
          "EARLIER COLD-READ-FULL-RUNS NOT COUNTED:" in result.stdout and "git log --follow" in result.stdout,
          f"exit {result.returncode}; stdout={result.stdout!r}; stderr={result.stderr!r}")

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
