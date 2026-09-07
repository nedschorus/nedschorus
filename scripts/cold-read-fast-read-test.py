#!/usr/bin/env python3
"""Tests for cold-read-fast-read.py — the fast cold read's driver.

WHAT IS PINNED HERE.

  - The report-path rule. A walk draft, docs/walk/<name>-draft.md under the
    checkout, is read into docs/walk/<name>-suggestions.md beside it, and a
    suggestions file left by an earlier read is replaced. Anything else --
    another directory in the checkout, a file outside it -- is read into
    cold-read-records/<YYYY-MM-DD>-<name>/<name>-fast-read.md.

  - One retry. A cell that fails once is run again and, when the second run
    produces a report, the read succeeds. A cell that fails twice is not run
    a third time: the read prints a line opening FAILED on stdout, exits 1,
    and leaves no report.

  - The chat-instead-of-file quirk carries through: a model that answers a
    review-length text in chat and writes no file still gives the read a
    report, and the launcher's recovery line is on the read's stderr.

  - The fast tier pin shows in the stamp of what the read produces:
    runtime=agy, gemini-3.8-flash-low, effort low, tier fast.

  - The reviewer's instructions the model receives are the template embedded
    in the script -- not the skill's prompt file -- with both paths
    substituted and no placeholder left.

  - A --target that is not a file is refused, exit 64, with FAILED on stdout
    and nothing launched.

Each case builds a throwaway git repository holding a copy of the scripts,
as scripts/cold-read-cell-common-test.py does, so the read's repository root
-- and with it the docs/walk and cold-read-records paths the rule names --
is the scratch tree. A stub `agy` first on PATH stands in for the model,
driven by COLD_READ_AGY_CELL_TEST_STUB_PLAN the way scripts/cold-read-agy-cell-test.py
drives its stub, plus a counter file so the stub can fail the first N
launches and succeed after.

Run: python3 scripts/cold-read-fast-read-test.py
"""

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
SCRIPT_NAMES = (
    "cold-read-cell-common.py",
    "cold-read-agy-cell.py",
    "cold-read-fast-read.py",
)
STDOUT_RECOVERY_PHRASE = "recovered the report from the model's chat output"
LONG_CHAT_REVIEW = " ".join(f"word{index}" for index in range(150)) + "\n"

# A phrase the embedded template carries and no case's own text does, so a
# prompt read from the wrong place fails here by content.
EMBEDDED_PROMPT_MARKER = "HOW TO DELIVER YOUR ANSWER"

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
    (repository / "scripts").mkdir(parents=True)
    for script_name in SCRIPT_NAMES:
        shutil.copy2(SCRIPTS_DIR / script_name, repository / "scripts" / script_name)
    (repository / ".gitignore").write_text("cold-read-records/\n", encoding="utf-8")
    walk_draft = repository / "docs" / "walk" / "a-walk-item-draft.md"
    walk_draft.parent.mkdir(parents=True)
    walk_draft.write_text("# A walk item\n\nOne committed line.\n", encoding="utf-8")
    other_document = repository / "docs" / "drafts" / "a-design.md"
    other_document.parent.mkdir(parents=True)
    other_document.write_text("# A design\n\nOne committed line.\n", encoding="utf-8")
    git(repository, "init", "-b", "main")
    git(repository, "config", "user.email", "test@test.invalid")
    git(repository, "config", "user.name", "cold-read-fast-read test")
    git(repository, "add", "-A")
    git(repository, "commit", "-m", "seed")
    return repository


def run_fast_read(repository, stub_directory, plan, expected_report, target_argument,
                  counter_path):
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
    today = time.strftime("%Y-%m-%d")

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
    check("the fast tier pin shows in the stamp: runtime agy, gemini-3.8-flash-low, low, fast",
          provenance_stamp_of(suggestions).startswith(
              "<!-- provenance: runtime=agy model=gemini-3.8-flash-low "
              "effort=low cell=fast-clarify tier=fast "),
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
    records_report = (repository / "cold-read-records" / f"{today}-a-design"
                      / "a-design-fast-read.md")
    result = run_fast_read(
        repository, stubs, {"*": {"report": "STUB FAST READ: of the design\n"}},
        records_report, other_relative, counter,
    )
    check("a document elsewhere in the checkout is read into cold-read-records/<date>-<name>/<name>-fast-read.md",
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
    outside_report = (repository / "cold-read-records" / f"{today}-some-item-draft"
                      / "some-item-draft-fast-read.md")
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
    check("the model receives the template embedded in the script",
          result.returncode == 0 and EMBEDDED_PROMPT_MARKER in received_prompt,
          f"exit {result.returncode}; prompt={received_prompt[:200]!r}")
    check("both paths are substituted and no placeholder remains",
          str(repository / walk_draft_relative) in received_prompt
          and str(suggestions) in received_prompt
          and "{TARGET_PATH}" not in received_prompt
          and "{REPORT_PATH}" not in received_prompt,
          repr(received_prompt[:300]))
    # The scratch checkout has no .claude/skills/cold-read/prompts/ tree at
    # all, so the case above also proves the read did not need the skill's
    # prompt file to run.

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

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
