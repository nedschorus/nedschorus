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
    "cold-read-record-ship.py",
)
# Every read on the records route ships its record; here, to a scratch
# log-store inside the scratch checkout through the shipper's destination
# override, so no case reaches ned-box.
RECORD_SHIP_DESTINATION_VARIABLE = "COLD_READ_RECORD_SHIP_DESTINATION"
SCRATCH_LOG_STORE_RELATIVE = Path("log-store") / "cold-read-records"
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
                  counter_path, ship_destination=None):
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
    expected_prompt = (script_under_test_module().FAST_CLARIFY_PROMPT_TEMPLATE
                       .replace("{TARGET_PATH}", str(repository / walk_draft_relative))
                       .replace("{REPORT_PATH}", str(suggestions)))
    check("the model receives the template embedded in the script",
          result.returncode == 0 and received_prompt.strip() == expected_prompt.strip(),
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
    records_report = (repository / "cold-read-records" / f"{today}-a-design"
                      / "a-design-fast-read.md")
    result = run_fast_read(
        repository, stubs, {"*": {"report": "STUB FAST READ: of the design\n"}},
        records_report, other_relative, counter,
    )
    frozen = records_report.parent / "target" / other_relative
    check("the target's bytes are frozen under target/ at its repository path before the cell runs",
          result.returncode == 0 and frozen.is_file()
          and frozen.read_bytes() == (repository / other_relative).read_bytes(),
          f"exit {result.returncode}; frozen present={frozen.exists()}; stderr={result.stderr[-300:]!r}")
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
    # directory, so two frozen targets never share one (the grid's rule).
    second_report = (repository / "cold-read-records" / f"{today}-a-design-2"
                     / "a-design-fast-read.md")
    (repository / other_relative).write_text("# A design\n\nRevised line.\n", encoding="utf-8")
    result = run_fast_read(
        repository, stubs, {"*": {"report": "STUB FAST READ: of the revised design\n"}},
        second_report, other_relative, counter,
    )
    check("a second read on the same day takes the -2 directory",
          result.returncode == 0 and result.stdout.strip() == str(second_report)
          and second_report.is_file(),
          f"exit {result.returncode}; stdout={result.stdout!r}; stderr={result.stderr[-300:]!r}")
    check("each directory holds its own frozen target: the first the original, the second the revision",
          b"Revised" not in frozen.read_bytes()
          and b"Revised" in (second_report.parent / "target" / other_relative).read_bytes())

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
    records_report = (repository / "cold-read-records" / f"{today}-a-design"
                      / "a-design-fast-read.md")
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


print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
