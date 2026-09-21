#!/usr/bin/env python3
"""Tests for cold-read-fast-read.py — the fast cold read's driver.

WHAT IS PINNED HERE.

  - The report-path rule. A walk draft, docs/walk/<name>-draft.md under the
    checkout, is read into docs/walk/<name>-suggestions.md beside it, and a
    suggestions file left by an earlier read is replaced, whatever the clock
    says. Anything else -- another directory in the checkout, a file outside
    it -- is read into
    cold-read-records/<stem>-<YYYY-MM-DD>/fast-read.md,
    the parent directory's leading dots stripped, with -2 for a second read
    started in the same minute (user-ruled 2026-09-16, for every document).
    No case reads the wall clock: the name functions are handed a clock
    reading, and every launched read runs with COLD_READ_RECORD_CLOCK_OVERRIDE
    set, so no case can flake across a minute boundary.

  - One retry. A cell that fails once is run again and, when the second run
    produces a report, the read succeeds. A cell that fails twice is not run
    a third time: the read prints a line opening FAILED on stdout, exits 1,
    and leaves no report.

  - The chat-instead-of-file quirk carries through: a model that answers a
    review-length text in chat and writes no file still gives the read a
    report, and the launcher's recovery line is on the read's stderr.

  - The fast tier pin shows in the stamp of what the read produces:
    runtime=agy, gemini-3.8-flash-medium, effort medium, tier fast.

  - The reviewer's instructions the model receives are the template embedded
    in the script -- not the skill's prompt file -- with both paths
    substituted and no placeholder left.

  - That embedded template is current: it is byte-for-byte the text of
    .claude/skills/cold-read/prompts/fast-clarify.md, the editable source of
    truth the user ruled on 2026-09-07. The constant in the script is a
    derived copy of that file, and this is the case that holds the two in
    step.

  - A --target that is not a file is refused, exit 64, with FAILED on stdout
    and nothing launched.

  - The full-run warning. A target in the class the /cold-read skill's step 2
    sends to the cold-read-full-run -- a skill or its prompt, a file under
    docs/agents/, a wiki file, a design, a test design, a component-contract --
    is read with one line on stderr and one line in the report saying the
    full run is still required; step 2's own exceptions (a walk file,
    CLAUDE.md) and everything else are read with nothing said. The warning
    never refuses and never touches stdout's one line.

  - The bare-number check. A walk draft is read with every bare issue, pull
    request or task number in it -- `#426`, `nedschorus#418`, a link whose
    text is the number -- counted on stderr and listed by line at the end of its
    suggestions file, or the section says there are none. A document on the
    records route gets no such section, whatever it contains. Headings, HTML
    entities, URLs and their fragments are not bare numbers.

Each case that launches the read builds a throwaway git repository holding a
copy of the scripts, as scripts/cold-read-cell-common-test.py does, so the
read's repository root -- and with it the docs/walk and cold-read-records
paths the rule names -- is the scratch tree. The one exception is the case
that compares the embedded template against the skill's prompt file: both of
those files live in the real checkout, so it reads them there. A stub `agy`
first on PATH stands in for the model, driven by
COLD_READ_AGY_CELL_TEST_STUB_PLAN the way scripts/cold-read-agy-cell-test.py
drives its stub, plus a counter file so the stub can fail the first N
launches and succeed after.

Run: python3 scripts/cold-read-fast-read-test.py
"""

import json
import os
import re
import pathlib
import shutil
import subprocess
import sys
import tempfile
import datetime
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
# Every read on the records route ships its record; here, to a scratch
# log-store inside the scratch checkout through the shipper's destination
# override, so no case reaches ned-box.
RECORD_SHIP_DESTINATION_VARIABLE = "COLD_READ_RECORD_SHIP_DESTINATION"
SCRATCH_LOG_STORE_RELATIVE = Path("log-store") / "cold-read-records"
# The clock every launched read is given instead of the wall clock, through
# the script's override, and the record stamp that clock must produce. A case
# that needs another minute passes its own.
RECORD_CLOCK_OVERRIDE_VARIABLE = "COLD_READ_RECORD_CLOCK_OVERRIDE"
FIXED_RECORD_CLOCK_FOR_TESTS = "2026-09-16T10:42"
FIXED_RECORD_STAMP_FOR_TESTS = "2026-09-16"
STDOUT_RECOVERY_PHRASE = "recovered the report from the model's chat output"
LONG_CHAT_REVIEW = " ".join(f"word{index}" for index in range(150)) + "\n"

# The script under test, imported so the cases below read the constants it
# actually carries instead of restating them. A fixed phrase was used until
# 2026-09-07, when the user's rewrite of the instructions (PR #271) dropped
# the phrase and the check failed on text, not on the mechanism; reading the
# constant keeps the check honest through every future edit of the
# instructions.
def script_under_test_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "cold_read_fast_read_under_test", SCRIPTS_DIR / "cold-read-fast-read.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Each pair is (constant name in scripts/cold-read-fast-read.py, path of the
# prompt file that constant is a derived copy of, relative to the repository
# root). One pair today, because only the fast cell has a second copy of its
# prompt: the user's ruling that the reviewer's instructions live in the .py
# that runs the cell was made about the fast cell. The other cold-read
# prompts -- defect-hunt.md, restate.md, terminology.md -- are read from the
# skill at run time and have no second copy anywhere, so nothing about them
# belongs here. If another cell ever embeds its prompt the same way, the same
# shape covers it: one more pair, on one more line.
EMBEDDED_PROMPT_COPY_AND_SOURCE_PAIRS = (
    ("FAST_CLARIFY_PROMPT_TEMPLATE",
     ".claude/skills/cold-read/prompts/fast-clarify.md"),
)

# The stub `agy`: the model from --model, the prompt from --print's value,
# the plan from the environment, and a counter file that counts launches so
# "fail_first_attempts": N fails the first N and succeeds after.
STUB_AGY = """#!/usr/bin/env python3
import json, os, pathlib, sys
argv = sys.argv
model = argv[argv.index("--model") + 1] if "--model" in argv else "*"
prompt = argv[argv.index("--print") + 1] if "--print" in argv else ""
plan = json.loads(os.environ["COLD_READ_AGY_CELL_TEST_STUB_PLAN"])
step = plan.get(model, plan.get("*", {}))
counter_path = pathlib.Path(os.environ["COLD_READ_AGY_CELL_TEST_STUB_COUNTER_PATH"])
launches = (int(counter_path.read_text()) if counter_path.is_file() else 0) + 1
counter_path.write_text(str(launches))
if "dump_prompt" in step:
    pathlib.Path(step["dump_prompt"]).write_text(prompt, encoding="utf-8")
if launches <= step.get("fail_first_attempts", 0):
    sys.stderr.write("stub agy: simulated failure on launch %d\\n" % launches)
    sys.exit(1)
report_path = pathlib.Path(os.environ["COLD_READ_AGY_CELL_TEST_STUB_REPORT_PATH"])
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
    # The whole scripts/ directory, __pycache__ aside, so a shared module
    # added tomorrow needs no edit here (user-ruled 2026-09-20, walk
    # md-skills-seat-open-decisions-2026-09-20 item 3).
    shutil.copytree(SCRIPTS_DIR, repository / "scripts",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (repository / ".gitignore").write_text("cold-read-records/\n", encoding="utf-8")
    walk_draft = repository / "docs" / "walk" / "a-walk-item-draft.md"
    walk_draft.parent.mkdir(parents=True)
    walk_draft.write_text("# A walk item\n\nOne committed line.\n", encoding="utf-8")
    other_document = repository / "docs" / "drafts" / "a-design.md"
    other_document.parent.mkdir(parents=True)
    other_document.write_text("# A design\n\nOne committed line.\n", encoding="utf-8")
    git(repository, "init", "-b", "main")
    # Auto maintenance off: with the whole scripts/ directory committed, git
    # 2.55 repacks this repository in the background, and its temporary files
    # race the deletion of these throwaway checkouts — measured 2026-09-20,
    # a FileNotFoundError on a `bitmap-ref-tips` file inside shutil.rmtree.
    git(repository, "config", "maintenance.auto", "false")
    git(repository, "config", "user.email", "test@test.invalid")
    git(repository, "config", "user.name", "cold-read-fast-read test")
    git(repository, "add", "-A")
    git(repository, "commit", "-m", "seed")
    return repository


def run_fast_read(repository, stub_directory, plan, expected_report, target_argument,
                  counter_path, ship_destination=None,
                  record_clock=FIXED_RECORD_CLOCK_FOR_TESTS):
    """The read as a subprocess, with the stub agy first on PATH.

    `expected_report` is where the stub writes -- the path the case expects
    the rule to choose. If the read chooses another, the cell finds no report
    and the read fails, which is how the rule is pinned.
    """
    stub_directory.mkdir(parents=True, exist_ok=True)
    stub = stub_directory / "agy"
    stub.write_text(STUB_AGY, encoding="utf-8")
    stub.chmod(0o755)
    counter_path.unlink(missing_ok=True)
    environment = dict(os.environ)
    environment["PATH"] = f"{stub_directory}{os.pathsep}{environment.get('PATH', '')}"
    environment["COLD_READ_AGY_CELL_TEST_STUB_PLAN"] = json.dumps(plan)
    environment["COLD_READ_AGY_CELL_TEST_STUB_REPORT_PATH"] = str(expected_report)
    environment["COLD_READ_AGY_CELL_TEST_STUB_COUNTER_PATH"] = str(counter_path)
    environment[RECORD_SHIP_DESTINATION_VARIABLE] = (
        ship_destination or str(repository / SCRATCH_LOG_STORE_RELATIVE))
    environment[RECORD_CLOCK_OVERRIDE_VARIABLE] = record_clock
    return subprocess.run(
        [sys.executable, str(repository / "scripts" / "cold-read-fast-read.py"),
         "--target", str(target_argument)],
        capture_output=True, text=True, check=False, env=environment,
    )


def launches_counted(counter_path):
    return int(counter_path.read_text()) if counter_path.is_file() else 0


def provenance_stamp_of(report):
    if not report.is_file():
        return ""
    return report.read_text(encoding="utf-8").splitlines()[0]


with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch).resolve()  # macOS: /var is a link to /private/var, and the scripts resolve
    stubs = scratch / "stub-bin"
    counter = scratch / "stub-launch-counter"
    record_stamp = FIXED_RECORD_STAMP_FOR_TESTS

    # --- The record-name rule: document stem, then date, then a count -------
    # User-ruled 2026-09-18 (walk cold-read-and-walk-file-names-and-dispositions,
    # item 4): `<file stem>-<YYYY-MM-DD>`, and `SKILL-<skill name>-<YYYY-MM-DD>`
    # for a skill. It reverses the date-first, parent-directory form of
    # 2026-09-16 so every read of one document sits together in the store's
    # listing, accepting that same-stem documents in different directories
    # read on one day become -2 of each other. The functions are handed a
    # clock reading, so these cases never read the wall clock.
    name_module = script_under_test_module()
    record_name = name_module.record_name_for_target
    record_directory_name = name_module.record_directory_name_for_target
    clock_at_1042 = datetime.datetime(2026, 9, 16, 10, 42)
    skill_target = Path("/r/.claude/skills/cold-read/SKILL.md")
    terminology_target = Path("/r/.claude/skills/cold-read/prompts/terminology.md")
    check("a skill's document part is SKILL, a hyphen, and the skill's name",
          record_name(skill_target) == "SKILL-cold-read", record_name(skill_target))
    check("a skill's prompt file is its stem alone, like any other document",
          record_name(terminology_target) == "terminology", record_name(terminology_target))
    check("an ordinary document is its stem, with no directory",
          record_name(Path("/r/docs/drafts/explain-skill-draft.md")) == "explain-skill-draft")
    check("README gets no special case",
          record_name(Path("/r/docs/nedschorus-wiki/README.md")) == "README")
    check("a file whose parent has no name is still its stem",
          record_name(Path("/CLAUDE.md")) == "CLAUDE", record_name(Path("/CLAUDE.md")))
    check("a SKILL.md record directory is the document part, then the date",
          record_directory_name(skill_target, clock_at_1042) == "SKILL-cold-read-2026-09-16",
          record_directory_name(skill_target, clock_at_1042))
    check("the time of day is not part of the name",
          record_directory_name(Path("/r/docs/drafts/a.md"), datetime.datetime(2026, 9, 16, 9, 5))
          == "a-2026-09-16"
          and record_directory_name(Path("/r/docs/drafts/a.md"), datetime.datetime(2026, 9, 16, 21, 5))
          == "a-2026-09-16")
    # RECORDS_DIR is pointed at scratch so the result cannot pick up a -2 from
    # whatever this checkout's own cold-read-records/ happens to hold.
    name_module.RECORDS_DIR = scratch / "in-process-records"
    skill_report = name_module.fast_read_report_path_for_target(skill_target, clock_at_1042)
    check("the fast read's report is bare fast-read.md inside the record",
          skill_report == scratch / "in-process-records" / "SKILL-cold-read-2026-09-16"
          / "fast-read.md",
          str(skill_report))
    walk_target = name_module.REPO_ROOT / "docs" / "walk" / "some-item-draft.md"
    check("the walk-draft route is untouched: docs/walk/<name>-suggestions.md, whatever the clock",
          name_module.fast_read_report_path_for_target(walk_target, clock_at_1042)
          == name_module.fast_read_report_path_for_target(
              walk_target, datetime.datetime(2027, 1, 1, 0, 0))
          == name_module.REPO_ROOT / "docs" / "walk" / "some-item-suggestions.md",
          str(name_module.fast_read_report_path_for_target(walk_target, clock_at_1042)))

    # --- The report-path rule: a walk draft ------------------------------
    repository = build_scratch_repository(scratch)
    walk_draft_relative = "docs/walk/a-walk-item-draft.md"
    suggestions = repository / "docs" / "walk" / "a-walk-item-suggestions.md"
    suggestions.write_text("LEFT BY AN EARLIER READ\n", encoding="utf-8")
    result = run_fast_read(
        repository, stubs, {"*": {"report": "STUB FAST READ: of the walk item\n"}},
        suggestions, walk_draft_relative, counter,
    )
    check("a walk draft's read exits 0",
          result.returncode == 0, f"exit {result.returncode}; stderr={result.stderr!r}")
    check("a walk draft docs/walk/<name>-draft.md is read into docs/walk/<name>-suggestions.md",
          result.stdout.strip() == str(suggestions) and suggestions.is_file(),
          f"stdout={result.stdout!r}")
    suggestions_text = suggestions.read_text(encoding="utf-8") if suggestions.is_file() else ""
    check("an earlier suggestions file is replaced, not appended to",
          "LEFT BY AN EARLIER READ" not in suggestions_text
          and "of the walk item" in suggestions_text, repr(suggestions_text[:200]))
    check("the fast tier pin shows in the stamp: runtime agy, gemini-3.8-flash-medium, medium, fast",
          provenance_stamp_of(suggestions).startswith(
              "<!-- provenance: runtime=agy model=gemini-3.8-flash-medium "
              "effort=medium cell=fast-clarify tier=fast "),
          repr(provenance_stamp_of(suggestions)))
    check("the stamp names the embedded prompt file",
          "prompt_file=" in provenance_stamp_of(suggestions)
          and "cold-read-fast-read-embedded-fast-clarify-prompt.md" in provenance_stamp_of(suggestions),
          repr(provenance_stamp_of(suggestions)))
    check("the read's own stdout is exactly the one line",
          len(result.stdout.splitlines()) == 1, repr(result.stdout))

    # --- The report-path rule: anything else -----------------------------
    repository = build_scratch_repository(scratch)
    other_relative = "docs/drafts/a-design.md"
    records_report = (repository / "cold-read-records" / f"a-design-{record_stamp}"
                      / "fast-read.md")
    result = run_fast_read(
        repository, stubs, {"*": {"report": "STUB FAST READ: of the design\n"}},
        records_report, other_relative, counter,
    )
    check("a document elsewhere in the checkout is read into cold-read-records/<stem>-<date>/fast-read.md",
          result.returncode == 0 and result.stdout.strip() == str(records_report)
          and records_report.is_file(),
          f"exit {result.returncode}; stdout={result.stdout!r}; stderr={result.stderr!r}")

    # A file outside the checkout entirely takes the same route, under its
    # own name, and the walk rule does not fire on a `-draft.md` name that
    # sits somewhere other than docs/walk.
    repository = build_scratch_repository(scratch)
    outside_draft = scratch / "elsewhere" / "some-item-draft.md"
    outside_draft.parent.mkdir(parents=True, exist_ok=True)
    outside_draft.write_text("# Outside\n", encoding="utf-8")
    outside_report = (repository / "cold-read-records" / f"some-item-draft-{record_stamp}"
                      / "fast-read.md")
    result = run_fast_read(
        repository, stubs, {"*": {"report": "STUB FAST READ: of the outside file\n"}},
        outside_report, outside_draft, counter,
    )
    check("a -draft.md outside docs/walk is read into the records tree, not into docs/walk",
          result.returncode == 0 and result.stdout.strip() == str(outside_report)
          and outside_report.is_file()
          and not (repository / "docs" / "walk" / "some-item-suggestions.md").exists(),
          f"exit {result.returncode}; stdout={result.stdout!r}; stderr={result.stderr!r}")

    # --- One retry --------------------------------------------------------
    repository = build_scratch_repository(scratch)
    suggestions = repository / "docs" / "walk" / "a-walk-item-suggestions.md"
    result = run_fast_read(
        repository, stubs,
        {"*": {"fail_first_attempts": 1, "report": "STUB FAST READ: second try\n"}},
        suggestions, walk_draft_relative, counter,
    )
    check("a cell that fails once is retried, and the retry's report is the read's",
          result.returncode == 0 and result.stdout.strip() == str(suggestions)
          and suggestions.is_file() and launches_counted(counter) == 2,
          f"exit {result.returncode}; launches={launches_counted(counter)}; "
          f"stderr={result.stderr!r}")
    check("the retry is announced on stderr",
          "retrying once" in result.stderr, repr(result.stderr))

    # --- FAILED after the second failure ----------------------------------
    repository = build_scratch_repository(scratch)
    suggestions = repository / "docs" / "walk" / "a-walk-item-suggestions.md"
    result = run_fast_read(
        repository, stubs,
        {"*": {"fail_first_attempts": 99, "report": "STUB FAST READ: never\n"}},
        suggestions, walk_draft_relative, counter,
    )
    check("a cell that fails twice fails the read with exit 1",
          result.returncode == 1, f"exit {result.returncode}; stderr={result.stderr!r}")
    check("the read prints one line opening FAILED on stdout",
          result.stdout.startswith("FAILED") and len(result.stdout.splitlines()) == 1,
          repr(result.stdout))
    check("exactly two launches were made: the run and one retry",
          launches_counted(counter) == 2, f"launches={launches_counted(counter)}")
    check("no report is left behind by a failed read",
          not suggestions.exists(), f"{suggestions} exists")

    # --- Chat instead of file, through the read ---------------------------
    repository = build_scratch_repository(scratch)
    suggestions = repository / "docs" / "walk" / "a-walk-item-suggestions.md"
    result = run_fast_read(
        repository, stubs, {"*": {"stdout": LONG_CHAT_REVIEW}},
        suggestions, walk_draft_relative, counter,
    )
    suggestions_text = suggestions.read_text(encoding="utf-8") if suggestions.is_file() else ""
    check("a model that answered in chat still gives the read a report, on the first launch",
          result.returncode == 0 and result.stdout.strip() == str(suggestions)
          and LONG_CHAT_REVIEW.strip() in suggestions_text
          and launches_counted(counter) == 1,
          f"exit {result.returncode}; launches={launches_counted(counter)}; "
          f"stdout={result.stdout!r}")
    check("the launcher's recovery line is on the read's stderr",
          STDOUT_RECOVERY_PHRASE in result.stderr, repr(result.stderr))

    # --- The embedded instructions: two cases, and why both are needed ---
    # The case below and the one after it are a pair. The first proves the
    # runtime uses the text embedded in the script: that text, and not the
    # skill's prompt file, is what the model receives. The second proves that
    # embedded text is current: still byte-for-byte the user's editable
    # source. Neither covers the other. The first compares the prompt the
    # cell received against the script's own constant, so it passes just as
    # happily on stale instructions -- which is how the constant sat stale
    # for several days after the user rewrote the prompt file (PR #271) with
    # nothing detecting it. The second says nothing about what the cell does
    # with the constant at run time.

    # --- The embedded instructions are what the model receives ------------
    repository = build_scratch_repository(scratch)
    suggestions = repository / "docs" / "walk" / "a-walk-item-suggestions.md"
    prompt_dump = scratch / "received-prompt.txt"
    result = run_fast_read(
        repository, stubs,
        {"*": {"report": "STUB FAST READ\n", "dump_prompt": str(prompt_dump)}},
        suggestions, walk_draft_relative, counter,
    )
    received_prompt = prompt_dump.read_text(encoding="utf-8") if prompt_dump.is_file() else ""
    # The reviewer is pointed at the marked copy, never at the document
    # itself (nedschorus#284 step 2). On the walk route that copy is scratch,
    # so the path is only known by its name.
    marked_copy_name = (pathlib.Path(walk_draft_relative).stem
                        + script_under_test_module().SENTENCE_ID_MARKED_COPY_SUFFIX)
    target_line = received_prompt.split("\n", 1)[0]
    expected_prompt = (script_under_test_module().FAST_CLARIFY_PROMPT_TEMPLATE
                       .replace("{TARGET_PATH}", "{TARGET_PATH}")
                       .replace("{REPORT_PATH}", str(suggestions)))
    check("the model receives the template embedded in the script",
          result.returncode == 0
          and received_prompt.strip().replace(
              target_line.split(" in full", 1)[0][len("Read "):], "{TARGET_PATH}")
          == expected_prompt.strip(),
          f"exit {result.returncode}; prompt={received_prompt[:200]!r}")
    check("the reviewer is pointed at the marked copy, not at the document",
          marked_copy_name in received_prompt
          and str(repository / walk_draft_relative) not in received_prompt,
          repr(received_prompt[:300]))
    check("both paths are substituted and no placeholder remains",
          str(suggestions) in received_prompt
          and "{TARGET_PATH}" not in received_prompt
          and "{REPORT_PATH}" not in received_prompt,
          repr(received_prompt[:300]))
    # The scratch checkout has no .claude/skills/cold-read/prompts/ tree at
    # all, so the case above also proves the read did not need the skill's
    # prompt file to run.

    # --- The embedded instructions are current ----------------------------
    # This case reads the real checkout, not a scratch one, because both
    # files it compares live there. REPO_ROOT comes from this test file's own
    # path, so the case finds them wherever the checkout sits and whatever
    # the working directory is.
    #
    # NOTHING IS NORMALISED, and the string literal is why nothing needs to
    # be. The constant opens `"""\`, so the backslash eats the newline after
    # the quotes and the constant's first byte is the file's first byte; its
    # closing `"""` sits on a line of its own, so the constant ends with
    # exactly the one trailing newline the file ends with. Measured on main
    # at ba8d754 (PR #275, which copied the file into the constant), the two
    # were byte-identical -- 4580 bytes each -- so no leading- or
    # trailing-newline allowance is needed, and none is made. The comparison
    # is on bytes rather than on str because read_text() translates line
    # endings, which would hide a CRLF drift.
    for constant_name, prompt_file_relative in EMBEDDED_PROMPT_COPY_AND_SOURCE_PAIRS:
        derived_copy_bytes = getattr(
            script_under_test_module(), constant_name).encode("utf-8")
        source_file = REPO_ROOT / prompt_file_relative
        source_bytes = source_file.read_bytes() if source_file.is_file() else b""
        check(f"{constant_name} is byte-for-byte the text of {prompt_file_relative}",
              derived_copy_bytes == source_bytes,
              "THE DERIVED COPY HAS DRIFTED FROM ITS SOURCE. "
              f"SOURCE OF TRUTH, the file to edit: {prompt_file_relative}, "
              f"{len(source_bytes)} bytes"
              f"{'' if source_file.is_file() else ' (NO SUCH FILE)'}. "
              "DERIVED COPY, a verbatim copy of that file kept in step by "
              f"hand: scripts/cold-read-fast-read.py, constant "
              f"{constant_name}, {len(derived_copy_bytes)} bytes. "
              "The dependency runs one way only, and the script alone does "
              f"not say which way: {prompt_file_relative} is the source and "
              f"{constant_name} is the copy of it. To fix, re-copy "
              f"{prompt_file_relative} into {constant_name} verbatim -- do "
              "not edit the .md to match the constant.")

    # --- A --target that is not a file ------------------------------------
    repository = build_scratch_repository(scratch)
    result = run_fast_read(
        repository, stubs, {"*": {"report": "STUB FAST READ\n"}},
        repository / "never-written.md", "docs/walk/no-such-item-draft.md", counter,
    )
    check("a --target that is not a file exits 64 with FAILED on stdout, launching nothing",
          result.returncode == 64 and result.stdout.startswith("FAILED")
          and "target not found" in result.stderr and launches_counted(counter) == 0
          and "Traceback" not in result.stderr,
          f"exit {result.returncode}; stdout={result.stdout!r}; stderr={result.stderr!r}")

    # --- The records route freezes the target and ships the record ----------
    # User-ruled 2026-09-07: a record carries the exact bytes reviewed at the
    # target's repository path, and goes to the log-store once the report has
    # landed. The walk route does neither: a suggestions file is not a record.
    repository = build_scratch_repository(scratch)
    other_relative = "docs/drafts/a-design.md"
    records_report = (repository / "cold-read-records" / f"a-design-{record_stamp}"
                      / "fast-read.md")
    result = run_fast_read(
        repository, stubs, {"*": {"report": "STUB FAST READ: of the design\n"}},
        records_report, other_relative, counter,
    )
    frozen = records_report.parent / "target" / other_relative
    check("the target's bytes are frozen under target/ at its repository path before the cell runs",
          result.returncode == 0 and frozen.is_file()
          and frozen.read_bytes() == (repository / other_relative).read_bytes(),
          f"exit {result.returncode}; frozen present={frozen.exists()}; stderr={result.stderr[-300:]!r}")
    marked_copy = records_report.parent / (
        "a-design" + script_under_test_module().SENTENCE_ID_MARKED_COPY_SUFFIX)
    check("the marked copy the reviewer read is kept beside the report as evidence",
          marked_copy.is_file()
          and script_under_test_module().strip_sentence_ids(
              marked_copy.read_text(encoding="utf-8"))
          == (repository / other_relative).read_text(encoding="utf-8"),
          f"marked copy present={marked_copy.exists()}")
    # Every read below survives an absent file: a record path this suite or
    # the script got wrong should fail these cases by name, not end the run in
    # a traceback that takes every later case with it (found by mutating the
    # record name while building the 2026-09-16 rule).
    check("the document itself is not touched by the markup",
          frozen.is_file() and (repository / other_relative).read_bytes() == frozen.read_bytes())
    records_report_text = (records_report.read_text(encoding="utf-8")
                           if records_report.is_file() else "")
    check("the report comes back carrying the coverage section",
          script_under_test_module().SENTENCE_COVERAGE_HEADING in records_report_text,
          records_report_text[-300:])
    record_lines = [line for line in result.stderr.splitlines() if "record: " in line]
    check("the read reports the shipping on stderr, and it shipped",
          len(record_lines) == 1 and "record: shipped:" in record_lines[0],
          f"{record_lines!r}; stderr={result.stderr[-400:]!r}")
    check("the read's stdout is still exactly the report path",
          result.stdout.strip() == str(records_report) and result.stdout.count("\n") == 1,
          result.stdout)
    store_copy = repository / SCRATCH_LOG_STORE_RELATIVE / records_report.parent.name
    check("the store holds the report and the frozen target",
          (store_copy / records_report.name).is_file()
          and (store_copy / "target" / other_relative).is_file(),
          sorted(str(p.relative_to(store_copy)) for p in store_copy.rglob("*")) if store_copy.exists() else "no store copy")

    # A second read of the same document on the same day takes a fresh -2
    # directory, so two frozen targets never share one (the grid's rule). The
    # clock is the same override as the first read's, so the two really are
    # on one day whatever the wall clock did.
    second_report = (repository / "cold-read-records" / f"a-design-{record_stamp}-2"
                     / "fast-read.md")
    (repository / other_relative).write_text("# A design\n\nRevised line.\n", encoding="utf-8")
    result = run_fast_read(
        repository, stubs, {"*": {"report": "STUB FAST READ: of the revised design\n"}},
        second_report, other_relative, counter,
    )
    check("a second read on the same day takes the -2 directory",
          result.returncode == 0 and result.stdout.strip() == str(second_report)
          and second_report.is_file(),
          f"exit {result.returncode}; stdout={result.stdout!r}; stderr={result.stderr[-300:]!r}")
    second_frozen = second_report.parent / "target" / other_relative
    check("each directory holds its own frozen target: the first the original, the second the revision",
          frozen.is_file() and second_frozen.is_file()
          and b"Revised" not in frozen.read_bytes()
          and b"Revised" in second_frozen.read_bytes())

    # A third read the next day is told apart by its date: its own name, no
    # suffix. A same-day re-read is -2 or -3, which says nothing about which
    # draft it read; that cost was accepted with the 2026-09-18 name.
    later_day_report = (repository / "cold-read-records" / "a-design-2026-09-17"
                           / "fast-read.md")
    result = run_fast_read(
        repository, stubs, {"*": {"report": "STUB FAST READ: a day later\n"}},
        later_day_report, other_relative, counter, record_clock="2026-09-17T10:42",
    )
    records_after_three_reads = sorted(
        path.name for path in (repository / "cold-read-records").iterdir()
    ) if (repository / "cold-read-records").is_dir() else []
    check("a read on a different day takes a distinct name with no suffix",
          result.returncode == 0 and result.stdout.strip() == str(later_day_report)
          and later_day_report.is_file()
          and records_after_three_reads == [
              "a-design-2026-09-16", "a-design-2026-09-16-2", "a-design-2026-09-17"],
          f"exit {result.returncode}; records={records_after_three_reads}; "
          f"stderr={result.stderr[-300:]!r}")

    # The walk route: no record, no freeze, no ship.
    repository = build_scratch_repository(scratch)
    walk_draft_relative = "docs/walk/a-walk-item-draft.md"
    suggestions = repository / "docs" / "walk" / "a-walk-item-suggestions.md"
    result = run_fast_read(
        repository, stubs, {"*": {"report": "STUB FAST READ: of the walk item\n"}},
        suggestions, walk_draft_relative, counter,
    )
    check("a walk draft's read freezes nothing and ships nothing",
          result.returncode == 0 and not (repository / "cold-read-records").exists()
          and "record: " not in result.stderr and not (repository / "log-store").exists(),
          f"exit {result.returncode}; stderr={result.stderr[-300:]!r}")

    # A store that cannot be reached: the read still succeeds, and says so.
    repository = build_scratch_repository(scratch)
    records_report = (repository / "cold-read-records" / f"a-design-{record_stamp}"
                      / "fast-read.md")
    result = run_fast_read(
        repository, stubs, {"*": {"report": "STUB FAST READ: of the design\n"}},
        records_report, other_relative, counter,
        ship_destination="nobody@no-such-host.invalid:/tmp/no-store",
    )
    check("an unreachable store is reported as record: FAILED on stderr and the read still exits 0",
          result.returncode == 0 and result.stdout.strip() == str(records_report)
          and any("record: FAILED:" in line for line in result.stderr.splitlines()),
          f"exit {result.returncode}; stderr={result.stderr[-400:]!r}")


# --- The sentence-id markup (nedschorus#284 step 2) ----------------------
# Called in-process: it is a pure function of the document's text, so these
# cases need no cell, no model and no scratch checkout.
import importlib.util as _importlib_util
_spec = _importlib_util.spec_from_file_location(
    "cold_read_fast_read", SCRIPTS_DIR / "cold-read-fast-read.py")
_fast_read = _importlib_util.module_from_spec(_spec)
_spec.loader.exec_module(_fast_read)
sentence_id_markup = _fast_read.sentence_id_markup
strip_sentence_ids = _fast_read.strip_sentence_ids

MARKUP_SAMPLE = """\
---
name: a-skill
description: Two sentences here. The second one follows.
---

# A heading with a period. And more

A paragraph sentence one. A second one, which wraps
onto a second line and ends here.

- A list item. With two sentences.
- Another item

| a | b |
|---|---|
| one cell. still one row | two |

```python
x = 1  # not a sentence. really
```

Last line.
"""

marked, sentences = sentence_id_markup(MARKUP_SAMPLE)
stripped = strip_sentence_ids(marked)
check("strip_sentence_ids returns the document unchanged, byte for byte",
      stripped == MARKUP_SAMPLE,
      f"{stripped!r}")
check("ids are numbered from s1 with no gaps",
      list(sentences) == [f"s{n}" for n in range(1, len(sentences) + 1)],
      str(list(sentences)))
check("a heading is one unit, its id after the hashes",
      "# [s" in marked and sum(1 for s in sentences.values()
                              if s == "A heading with a period. And more") == 1,
      marked)
check("a frontmatter field takes its id after the key",
      "name: [s1] a-skill" in marked, marked)
check("a table row is one unit, whatever punctuation it holds",
      any(s == "one cell. still one row | two |" for s in sentences.values()),
      str(list(sentences.values())))
check("a fenced code block is one unit, its id on the opening fence line",
      any(s.startswith("```python") and "x = 1" in s for s in sentences.values())
      and "[s" not in marked.split("\n")[marked.split("\n").index(
          [line for line in marked.split("\n") if line.startswith("x = 1")][0])],
      marked)
check("a list item's id follows its marker and a second sentence gets its own",
      "- [s" in marked and any(s == "A list item." for s in sentences.values())
      and any(s == "With two sentences." for s in sentences.values()),
      str(list(sentences.values())))
check("a sentence wrapped across two lines carries exactly one id",
      sum(1 for s in sentences.values() if s.startswith("A second one, which wraps")) == 1
      and "onto a second line" in marked.split("\n")[
          [i for i, line in enumerate(marked.split("\n")) if "A second one" in line][0] + 1],
      marked)
check("every id in the marked copy has an entry in the returned sentences",
      set(re.findall(r"\[s(\d+)\]", marked)) == {name[1:] for name in sentences},
      marked)



# --- Attaching the originals and the coverage list -----------------------
attach = _fast_read.attach_sentences_and_coverage
SENTENCES = {"s1": "The first sentence.", "s2": "The second one.",
             "s3": "A third, never restated."}

attached = attach("## Question 1\n\n[s1]\n- a point\n\n[s2]\n- another\n", SENTENCES)
check("each original sentence is quoted under the restatement claiming its id",
      "[s1]\n> The first sentence." in attached
      and "[s2]\n> The second one." in attached, attached)
check("a sentence no restatement claimed is named in the coverage list",
      "Never restated: s3" in attached and "3 sentences in the document, 2 restated" in attached,
      attached)
check("the coverage section carries the heading that says a machine wrote it",
      _fast_read.SENTENCE_COVERAGE_HEADING in attached, attached)

full = attach("[s1]\n- a\n\n[s2]\n- b\n\n[s3]\n- c\n", SENTENCES)
check("a report that restates every sentence says so instead of listing none",
      "Every sentence was restated." in full and "Never restated" not in full, full)

invented = attach("[s1]\n- a\n\n[s9]\n- from nowhere\n", SENTENCES)
check("an id the document does not have is reported as invented, not attached",
      "Cited but not in the document: s9" in invented
      and "> from nowhere" not in invented, invented)

repeated = attach("[s1]\n- a\n\nSection 2: [s1] is unclear.\n", SENTENCES)
check("only the first mention of an id gets the original under it",
      repeated.count("> The first sentence.") == 1, repeated)



# --- The four signal-quality fixes from the PR #303 review ---------------
# Each of these degraded the coverage check itself: a sentence wrongly listed
# as skipped, two sentences sharing one id, a skipped sentence counted as
# covered, or a citation pointing at a file that no longer exists.

SIGNAL_SAMPLE = """\
| a | b |
|---|---|
| one | two |

---

A wrapped sentence that runs
onto a second line and stops here.

- 
- A real item.
"""
marked, sentences = sentence_id_markup(SIGNAL_SAMPLE)
check("strip_sentence_ids still returns the document unchanged with the fixes in",
      strip_sentence_ids(marked) == SIGNAL_SAMPLE, repr(marked))
check("a table separator row gets no id: there is nothing in it to restate",
      "|---|---|" in marked and "[s" not in [line for line in marked.split("\n")
                                             if line.startswith("|---")][0],
      marked)
check("a horizontal rule and a bare list marker get no id either",
      not any(value.strip() in ("---", "-", "") for value in sentences.values()),
      str(list(sentences.values())))
# This case uses a two-line document on purpose. With both sentences on one
# line the sentence-end pattern splits them and ends_open is never consulted,
# so the earlier version of this case passed with the fix reverted and
# guarded nothing (reviewer of PR #307). Across a line break ends_open is the
# only thing deciding, and reverting its rstrip(SENTENCE_CLOSERS) fails here.
quote_marked, quote_sentences = sentence_id_markup(
    'He said "that is done."\nShe agreed with him.\n')
check("a line ending in a closing quote is finished, so the next line starts its own id",
      any(value == 'He said "that is done."' for value in quote_sentences.values())
      and any(value == "She agreed with him." for value in quote_sentences.values()),
      str(list(quote_sentences.values())))
check("a sentence wrapped across lines still carries one id, not one per line",
      sum(1 for value in sentences.values() if value.startswith("A wrapped sentence")) == 1
      and not any(value.startswith("onto a second line") for value in sentences.values()),
      str(list(sentences.values())))

# An id cited inside a Question 2 sentence is a reference, not a restatement.
CITED = {"s1": "The first sentence.", "s2": "The second one."}
cited_later = attach("## Question 1\n\n[s1]\n- a point\n\n"
                     "## Question 2\n\n1. [s2] is unclear here.\n", CITED)
check("an id cited inside a later sentence does not count as restated",
      "Never restated: s2" in cited_later
      and "2 sentences in the document, 1 restated" in cited_later,
      cited_later)
check("that citation gets no original attached under it",
      "> The second one." not in cited_later, cited_later)

named = attach("[s1]\n- a point\n", {"s1": "The first sentence."},
               pathlib.Path("/tmp/a-document.md"))
kept = attach("[s1]\n- a point\n", {"s1": "The first sentence."},
              pathlib.Path("/tmp/a-document.md"),
              pathlib.Path("/tmp/record/a-document-with-sentence-ids.md"))
check("on the records route the coverage line says the copy is kept, and where",
      "kept beside this report" in kept
      and "/tmp/record/a-document-with-sentence-ids.md" in kept
      and "is gone" not in kept, kept)

check("on the walk route it says the copy was temporary and is gone",
      "marked copy of `/tmp/a-document.md`" in named
      and "was temporary and is gone" in named, named)


# --- The full-run warning (item 4 of nedschorus#418, user-ruled 2026-09-17) --
# The /cold-read skill's step 2 sends a class of documents to the
# cold-read-full-run; PR #332 merged a skill change on a fast read alone
# because nothing said so. The read now says it, and these cases pin which
# targets it says it about.
warning_module = script_under_test_module()
class_of = warning_module.full_run_class_of_target
root = warning_module.REPO_ROOT
check("a skill is in the class",
      class_of(root / ".claude/skills/cold-read/SKILL.md") == "a skill or a skill's prompt")
check("a skill's prompt is in the class",
      class_of(root / ".claude/skills/cold-read/prompts/terminology.md")
      == "a skill or a skill's prompt")
check("a file under docs/agents/ is in the class",
      class_of(root / "docs/agents/ghi-instructions.md") == "a file under docs/agents/")
check("so is one in its queue, which becomes such a file",
      class_of(root / "docs/agents/queue/some-agent-instructions.md")
      == "a file under docs/agents/")
check("a wiki file is in the class",
      class_of(root / "docs/nedschorus-wiki/nedschorus-glossary.md") == "a wiki file")
check("a design is recognised by its name, wherever it sits",
      class_of(root / "nc-systems/main-gatekeeper/main-gatekeeper-design.md") == "a design"
      and class_of(root / "docs/issues/46-ghi-info-agent-design.md") == "a design")
check("a test design and a component-contract have their own names",
      class_of(root / "docs/issues/x-test-design.md") == "a test design"
      and class_of(root / "docs/designs/queue/x-contract.md") == "a component-contract")
check("a component-contract is named as the state-machine design names it",
      class_of(root / "docs/design-to-main/some-component-contract.md")
      == "a component-contract")
check("a design in docs/design-to-main/ is a design, by its name",
      class_of(root / "docs/design-to-main/design-to-main-state-machine-design.md")
      == "a design")
check("a design's glossary is not in step 2's list, so it is not called a design",
      class_of(root / "docs/design-to-main/design-to-main-glossary.md") is None)
check("notes about a design are not the design",
      class_of(root / "docs/issues/142-draft-md-skill-design-notes.md") is None)
check("step 2's own exceptions are not in the class: a walk file and CLAUDE.md",
      class_of(root / "docs/walk/an-item-draft.md") is None
      and class_of(root / "CLAUDE.md") is None
      and class_of(root / "docs/agents/CLAUDE.local.md") is None)
check("an ordinary document is not in the class",
      class_of(root / "docs/issues/32-preservation-and-placement.md") is None)
check("a file outside the checkout is not classified",
      class_of(Path("/tmp/somewhere/a-design.md")) is None)

# And the read itself says it, on stderr before the cell runs and in the
# report that ships with the record. Its own scratch tree, because the one
# above went with its temporary directory.
with tempfile.TemporaryDirectory() as warning_scratch:
    warning_scratch = Path(warning_scratch).resolve()
    warning_stubs = warning_scratch / "stub-bin"
    warning_counter = warning_scratch / "stub-launch-counter"
    # run_fast_read reads the record clock from FIXED_RECORD_CLOCK_FOR_TESTS.
    warning_stamp = FIXED_RECORD_STAMP_FOR_TESTS

    repository = build_scratch_repository(warning_scratch)
    brief_relative = "docs/agents/a-seat-instructions.md"
    brief = repository / brief_relative
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text("# A seat\n\nOne sentence.\n", encoding="utf-8")
    brief_report = (repository / "cold-read-records"
                    / f"a-seat-instructions-{warning_stamp}"
                    / "fast-read.md")
    result = run_fast_read(
        repository, warning_stubs, {"*": {"report": "STUB FAST READ: of the brief\n"}},
        brief_report, brief_relative, warning_counter,
    )
    check("the read still succeeds: the warning never refuses",
          result.returncode == 0 and brief_report.is_file(),
          f"exit {result.returncode}; stderr={result.stderr!r}")
    check("the warning is on stderr, naming the class",
          "the cold-read-full-run is required before this document lands "
          "(a file under docs/agents/)" in result.stderr, repr(result.stderr))
    check("stdout is still exactly the report path",
          result.stdout.strip() == str(brief_report)
          and len(result.stdout.splitlines()) == 1, repr(result.stdout))
    brief_report_text = brief_report.read_text(encoding="utf-8") if brief_report.is_file() else ""
    check("the report carries the same sentence, so the shipped record says it too",
          "The cold-read-full-run is required before this document lands" in brief_report_text,
          repr(brief_report_text[-400:]))

    # A document outside the class is read with nothing said.
    repository = build_scratch_repository(warning_scratch)
    plain_relative = "docs/issues/a-plain-document.md"
    plain = repository / plain_relative
    plain.parent.mkdir(parents=True, exist_ok=True)
    plain.write_text("# A plain document\n\nOne sentence.\n", encoding="utf-8")
    plain_report = (repository / "cold-read-records"
                    / f"a-plain-document-{warning_stamp}"
                    / "fast-read.md")
    result = run_fast_read(
        repository, warning_stubs, {"*": {"report": "STUB FAST READ: of a plain document\n"}},
        plain_report, plain_relative, warning_counter,
    )
    check("nothing is said about a document the fast read finishes",
          result.returncode == 0
          and "cold-read-full-run is required" not in result.stderr
          and "cold-read-full-run is required" not in plain_report.read_text(encoding="utf-8"),
          f"exit {result.returncode}; stderr={result.stderr!r}")


# --- The bare-number check (item 5 of nedschorus#418, user-ruled 2026-09-17) --
# The walk-me-through skill forbids citing an issue or a pull request by bare
# number, and walk files carried 33 and 35 of them with nothing checking. A
# walk draft's read now lists every one; these cases pin what counts.
bare_module = script_under_test_module()
found = bare_module.bare_references_in
check("a bare number is found, with its line",
      found("One.\nMerged as PR #466 today.") == [(2, "#466")])
check("a repository prefix is kept with the number it cites",
      found("see nedschorus#418.") == [(1, "nedschorus#418")]
      and found("in nedschorus/nedschorus#39") == [(1, "nedschorus/nedschorus#39")])
check("a link whose text is the number is still a bare number",
      found("[nedschorus#46](https://github.com/nedschorus/nedschorus/issues/46)")
      == [(1, "nedschorus#46")])
check("a quoted reference keeps its repository prefix",
      found('`[s106] "nedschorus#385"`') == [(1, "nedschorus#385")])
check("a number in parentheses is found", found("merged (#12) today") == [(1, "#12")])
check("a range is two numbers", found("PRs #264–#268") == [(1, "#264"), (1, "#268")])
check("a range with an ASCII hyphen is two numbers",
      found("PRs #264-#268") == [(1, "#264"), (1, "#268")]
      and found("#15-#23") == [(1, "#15"), (1, "#23")])
check("numbers joined by slashes are each found, in order",
      found("#214/#169/#170") == [(1, "#214"), (1, "#169"), (1, "#170")])
check("a task number is found, since the citation rule covers tasks",
      found("task #37") == [(1, "#37")])
check("`#3` at the start of a line is text, not a heading, and is found",
      found("#3 is the one") == [(1, "#3")])
check("a markdown heading is not a number", found("## 3 things") == [])
check("an HTML entity is not a number", found("a &#123; b") == [])
check("a URL's fragment is not a number",
      found("https://x.com/page#12 and "
            "https://github.com/o/r/issues/5#issuecomment-9") == [])
check("a link by title, whose URL carries the number, is clean",
      found("[Fast read: say when](https://github.com/o/r/pull/466)") == [])
check("a number glued to letters on both sides is not a reference",
      found("abc#12b") == [])
check("a number without `#` is not checked", found("issue 418 and task 37") == [])

section = bare_module.bare_references_section
listed = section([(2, "#466"), (5, "nedschorus#418")])
check("the section's heading names issues, pull requests and tasks",
      bare_module.BARE_REFERENCES_HEADING
      == "## Bare issue, pull request and task numbers (added by cold-read-fast-read)",
      bare_module.BARE_REFERENCES_HEADING)
check("the section gives one instruction and a line per number",
      bare_module.BARE_REFERENCES_HEADING in listed
      and "Replace each with its type word and its title, as a link when it can "
          "be opened: write PR [its title](its URL), not PR #426." in listed
      and "- Line 2: #466" in listed and "- Line 5: nedschorus#418" in listed,
      listed)
check("a clean draft's section says so",
      section([]).rstrip().endswith("- None."), section([]))

# And the read itself: a walk draft is told on stderr and in its suggestions
# file; a clean walk draft's section says none; a document on the records
# route gets nothing, however many numbers it carries.
with tempfile.TemporaryDirectory() as bare_scratch:
    bare_scratch = Path(bare_scratch).resolve()
    bare_stubs = bare_scratch / "stub-bin"
    bare_counter = bare_scratch / "stub-launch-counter"

    repository = build_scratch_repository(bare_scratch)
    draft = repository / "docs" / "walk" / "a-bare-walk-draft.md"
    draft.parent.mkdir(parents=True, exist_ok=True)
    draft.write_text("# A walk\n\nPR #466 merged.\n\n"
                     "It closes [nedschorus#418](https://example.com/418).\n",
                     encoding="utf-8")
    draft_suggestions = repository / "docs" / "walk" / "a-bare-walk-suggestions.md"
    result = run_fast_read(
        repository, bare_stubs, {"*": {"report": "STUB FAST READ: of the draft\n"}},
        draft_suggestions, "docs/walk/a-bare-walk-draft.md", bare_counter,
    )
    check("a walk draft with bare numbers is still read: the check never refuses",
          result.returncode == 0 and draft_suggestions.is_file(),
          f"exit {result.returncode}; stderr={result.stderr!r}")
    check("the count is on stderr",
          "cold-read-fast-read: bare issue, pull request or task numbers in this "
          "walk draft: 2; the suggestions file lists each one." in result.stderr,
          repr(result.stderr))
    check("stdout is still exactly the report path",
          result.stdout.strip() == str(draft_suggestions)
          and len(result.stdout.splitlines()) == 1, repr(result.stdout))
    suggestions_text = (draft_suggestions.read_text(encoding="utf-8")
                        if draft_suggestions.is_file() else "")
    check("the suggestions file lists each number by line",
          "- Line 3: #466" in suggestions_text
          and "- Line 5: nedschorus#418" in suggestions_text,
          repr(suggestions_text[-500:]))
    check("the section comes after the coverage section, at the end",
          suggestions_text.find(bare_module.BARE_REFERENCES_HEADING)
          > suggestions_text.find("## Sentence coverage (added by cold-read-fast-read)")
          > 0, repr(suggestions_text[-500:]))

    repository = build_scratch_repository(bare_scratch)
    clean = repository / "docs" / "walk" / "a-clean-walk-draft.md"
    clean.parent.mkdir(parents=True, exist_ok=True)
    clean.write_text("# A walk\n\nThe pull request "
                     "[Fast read: say when](https://example.com/466) merged.\n",
                     encoding="utf-8")
    clean_suggestions = repository / "docs" / "walk" / "a-clean-walk-suggestions.md"
    result = run_fast_read(
        repository, bare_stubs, {"*": {"report": "STUB FAST READ: of a clean draft\n"}},
        clean_suggestions, "docs/walk/a-clean-walk-draft.md", bare_counter,
    )
    clean_text = (clean_suggestions.read_text(encoding="utf-8")
                  if clean_suggestions.is_file() else "")
    check("a clean walk draft is told nothing on stderr, and its section says none",
          result.returncode == 0
          and "bare issue, pull request or task numbers" not in result.stderr
          and clean_text.rstrip().endswith("- None."),
          f"exit {result.returncode}; tail={clean_text[-200:]!r}")

    repository = build_scratch_repository(bare_scratch)
    record_relative = "docs/issues/a-numbered-document.md"
    numbered = repository / record_relative
    numbered.parent.mkdir(parents=True, exist_ok=True)
    numbered.write_text("# A document\n\nSee #466 and #418.\n", encoding="utf-8")
    numbered_report = (repository / "cold-read-records"
                       / f"a-numbered-document-{FIXED_RECORD_STAMP_FOR_TESTS}"
                       / "fast-read.md")
    result = run_fast_read(
        repository, bare_stubs, {"*": {"report": "STUB FAST READ: of a record\n"}},
        numbered_report, record_relative, bare_counter,
    )
    numbered_text = (numbered_report.read_text(encoding="utf-8")
                     if numbered_report.is_file() else "")
    check("a document on the records route is not checked, whatever it carries",
          result.returncode == 0
          and "bare issue, pull request or task numbers" not in result.stderr
          and bare_module.BARE_REFERENCES_HEADING not in numbered_text,
          f"exit {result.returncode}; stderr={result.stderr!r}")

    # A failed read writes no suggestions file, so it must not say one lists
    # the numbers: it lists them on stderr itself (a merge-lane review note on
    # the pull request that added the check found the promise printed before
    # the cell ran, and broken whenever the read then failed).
    repository = build_scratch_repository(bare_scratch)
    failing = repository / "docs" / "walk" / "a-failing-walk-draft.md"
    failing.parent.mkdir(parents=True, exist_ok=True)
    failing.write_text("# A walk\n\nPR #466 merged.\n\nSee #418/#419.\n",
                       encoding="utf-8")
    failing_suggestions = repository / "docs" / "walk" / "a-failing-walk-suggestions.md"
    result = run_fast_read(
        repository, bare_stubs,
        {"*": {"fail_first_attempts": 99, "report": "STUB FAST READ: never\n"}},
        failing_suggestions, "docs/walk/a-failing-walk-draft.md", bare_counter,
    )
    check("a failed read of a walk draft with bare numbers still fails, with no file",
          result.returncode == 1 and result.stdout.startswith("FAILED")
          and not failing_suggestions.exists(),
          f"exit {result.returncode}; stdout={result.stdout!r}")
    check("a failed read never says the suggestions file lists the numbers",
          "the suggestions file lists each one" not in result.stderr,
          repr(result.stderr))
    check("a failed read lists each bare number by line on stderr",
          "walk draft: 3. The read failed, so no suggestions file lists them." in result.stderr
          and "line 3: #466" in result.stderr
          and "line 5: #418" in result.stderr
          and "line 5: #419" in result.stderr,
          repr(result.stderr))

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
