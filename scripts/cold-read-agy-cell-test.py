#!/usr/bin/env python3
"""Tests for cold-read-agy-cell.py — the Antigravity leg's pins and its one
quirk, driven through a stub `agy` so no model is ever called.

WHAT IS PINNED HERE.

  - The fast tier's pin (user-ruled 2026-09-07): --tier fast runs
    gemini-3.8-flash-low at effort low, and the stamp says so, with
    runtime=agy. The other tiers are refused by this launcher before agy
    runs: it pins no model for them, and a Gemini review under a good- or
    floor-tier stamp would be a tier the roster never measured it on.

  - The invocation is the one measured working in the 2026-09-04 campaign:
    --add-dir <repo> (or AGENTS.md does not load), --dangerously-skip-permissions
    (or the report's Write is blocked headless), --model, --effort,
    --print-timeout, --output-format text, and the prompt as the VALUE of
    --print, with both paths substituted into it.

  - The chat-instead-of-file quirk. The campaign measured gemini-3.8-flash
    sometimes answering the whole review in chat rather than writing the
    file. A model that exits 0 with no file and a stdout long enough to be a
    review (the campaign's 120-word threshold) has its stdout taken as the
    report, stamped, and the recovery announced on stderr. Three things
    bound that: a short stdout -- a remark, not a review -- still fails the
    cell with no report left behind; a non-zero exit is a failure whatever
    stdout holds, as on every leg; and a report the model wrote one directory
    away is recovered as the file it is, with stdout left alone, because the
    near-miss search runs first.

  - --model and --effort override the tier map and are stamped as what ran,
    the way they do on the other legs.

Each case builds a throwaway git repository holding a copy of the cell
scripts, as scripts/cold-read-cell-common-test.py does, and runs the launcher
inside it with the stub first on PATH. The stub is driven by
COLD_READ_AGY_CELL_TEST_STUB_PLAN, a JSON map from model id to what that
attempt should do.

Run: python3 scripts/cold-read-agy-cell-test.py
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
PROMPTS_DIR = REPO_ROOT / ".claude" / "skills" / "cold-read" / "prompts"
CELL_SCRIPT_NAMES = (
    "cold-read-cell-common.py",
    "cold-read-agy-cell.py",
)
TARGET_RELATIVE_PATH = "docs/drafts/cold-read-agy-cell-test-target.md"

# The phrases the launcher and the shared module print, spelled out here
# rather than imported so a reworded line fails here rather than passing
# however either side was reworded.
STDOUT_RECOVERY_PHRASE = "recovered the report from the model's chat output"
NEAR_MISS_RECOVERY_PHRASE = "recovered a near-miss report"

# A review-length chat answer and a remark-length one, either side of the
# launcher's 120-word threshold.
LONG_CHAT_REVIEW = " ".join(f"word{index}" for index in range(150)) + "\n"
SHORT_CHAT_REMARK = "I have written the report to the path you gave me.\n"

# A stand-in for the `agy` CLI. It reads the model from --model and the
# prompt from --print's value, then does what the plan says for that model:
# "report" is text to write to the report path (absent means write nothing),
# "near_miss" writes the report one directory away from where it was asked,
# "stdout" is the model's chat text, "dump_argv" and "dump_prompt" are paths
# to record what the stub was launched with, and "exit" is the code to exit
# with. The report path arrives by environment, as in the other cell tests,
# so a reworded template cannot unhook the stub.
STUB_AGY = """#!/usr/bin/env python3
import json, os, pathlib, sys
argv = sys.argv
model = argv[argv.index("--model") + 1] if "--model" in argv else "*"
prompt = argv[argv.index("--print") + 1] if "--print" in argv else ""
plan = json.loads(os.environ["COLD_READ_AGY_CELL_TEST_STUB_PLAN"])
step = plan.get(model, plan.get("*", {}))
report_path = pathlib.Path(os.environ["COLD_READ_AGY_CELL_TEST_STUB_REPORT_PATH"])
if "dump_argv" in step:
    pathlib.Path(step["dump_argv"]).write_text(json.dumps(argv), encoding="utf-8")
if "dump_prompt" in step:
    pathlib.Path(step["dump_prompt"]).write_text(prompt, encoding="utf-8")
if "report" in step:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(step["report"], encoding="utf-8")
if "near_miss" in step:
    sibling = report_path.parent.parent / (report_path.parent.name[:-1] + "X")
    sibling.mkdir(parents=True, exist_ok=True)
    (sibling / report_path.name).write_text(step["near_miss"], encoding="utf-8")
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
    """A git repository the cell scripts believe they live in: the cell
    derives its repository root from its own path, so a copy is the seam."""
    repository = scratch / "scratch-checkout"
    if repository.exists():
        shutil.rmtree(repository)
    (repository / "scripts").mkdir(parents=True)
    for script_name in CELL_SCRIPT_NAMES:
        shutil.copy2(SCRIPTS_DIR / script_name, repository / "scripts" / script_name)
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
    git(repository, "config", "user.name", "cold-read-agy-cell test")
    git(repository, "add", "-A")
    git(repository, "commit", "-m", "seed")
    return repository


def report_path_for(repository, case_slug):
    record_directory_name = f"2026-09-07-{case_slug}-aaaaaaa"
    return (repository / "cold-read-records" / record_directory_name
            / f"{record_directory_name}--agy-fast-clarify-fast.md")


def run_agy_cell(repository, stub_directory, plan, report_path, *arguments,
                 tier="fast"):
    stub_directory.mkdir(parents=True, exist_ok=True)
    stub = stub_directory / "agy"
    stub.write_text(STUB_AGY, encoding="utf-8")
    stub.chmod(0o755)
    environment = dict(os.environ)
    environment["PATH"] = f"{stub_directory}{os.pathsep}{environment.get('PATH', '')}"
    environment["COLD_READ_AGY_CELL_TEST_STUB_PLAN"] = json.dumps(plan)
    environment["COLD_READ_AGY_CELL_TEST_STUB_REPORT_PATH"] = str(report_path)
    return subprocess.run(
        [sys.executable, str(repository / "scripts" / "cold-read-agy-cell.py"),
         "--cell", "fast-clarify", "--tier", tier,
         "--target", TARGET_RELATIVE_PATH, "--report", str(report_path),
         *arguments],
        capture_output=True, text=True, check=False, env=environment,
    )


def provenance_stamp_of(report):
    if not report.is_file():
        return ""
    return report.read_text(encoding="utf-8").splitlines()[0]


with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch).resolve()  # macOS: /var is a link to /private/var, and the scripts resolve
    stubs = scratch / "stub-bin"

    # --- The fast tier's pin, and the invocation -------------------------
    repository = build_scratch_repository(scratch)
    report = report_path_for(repository, "fast-pin")
    argv_dump = scratch / "fast-pin-argv.json"
    prompt_dump = scratch / "fast-pin-prompt.txt"
    result = run_agy_cell(
        repository, stubs,
        {"*": {"report": "STUB AGY REVIEW: three sections\n",
               "dump_argv": str(argv_dump), "dump_prompt": str(prompt_dump)}},
        report,
    )
    check("a fast-tier cell whose agy writes the report exits 0",
          result.returncode == 0, f"exit {result.returncode}; stderr={result.stderr!r}")
    stamp = provenance_stamp_of(report)
    check("the fast tier is pinned to gemini-3.8-flash-low at low, stamped as runtime agy",
          stamp.startswith("<!-- provenance: runtime=agy model=gemini-3.8-flash-low "
                           "effort=low cell=fast-clarify tier=fast "),
          repr(stamp))
    check("the stamp carries duration_s and no tokens field",
          re.search(r"\bduration_s=\d+\b", stamp) is not None and "tokens=" not in stamp,
          repr(stamp))
    check("the successful cell prints nothing to stdout",
          result.stdout == "", repr(result.stdout[:200]))
    argv = json.loads(argv_dump.read_text(encoding="utf-8")) if argv_dump.is_file() else []
    check("agy is given the repository with --add-dir",
          "--add-dir" in argv and argv[argv.index("--add-dir") + 1] == str(repository),
          repr(argv))
    check("agy is told to skip permission prompts",
          "--dangerously-skip-permissions" in argv, repr(argv))
    check("the model, effort, print timeout and text output are on the command line",
          argv[argv.index("--model") + 1] == "gemini-3.8-flash-low"
          and argv[argv.index("--effort") + 1] == "low"
          and argv[argv.index("--print-timeout") + 1] == "30m"
          and argv[argv.index("--output-format") + 1] == "text",
          repr(argv))
    received_prompt = prompt_dump.read_text(encoding="utf-8") if prompt_dump.is_file() else ""
    check("the prompt is the value of --print, with both paths substituted",
          "--print" in argv and argv[argv.index("--print") + 1] == received_prompt
          and str(repository / TARGET_RELATIVE_PATH) in received_prompt
          and str(report) in received_prompt
          and "{TARGET_PATH}" not in received_prompt
          and "{REPORT_PATH}" not in received_prompt,
          repr(received_prompt[:300]))

    # --- The other tiers are refused before agy runs ----------------------
    for other_tier in ("good", "floor"):
        repository = build_scratch_repository(scratch)
        report = report_path_for(repository, f"tier-{other_tier}")
        result = run_agy_cell(
            repository, stubs, {"*": {"report": "STUB AGY REVIEW\n"}}, report,
            tier=other_tier,
        )
        check(f"--tier {other_tier} is refused by this launcher with exit 64",
              result.returncode == 64 and "Traceback" not in result.stderr,
              f"exit {result.returncode}; stderr={result.stderr!r}")
        check(f"--tier {other_tier} never launches agy",
              not report.exists(), "the stub agy ran and wrote the report")

    # --- Chat instead of file: a long stdout is the review ---------------
    repository = build_scratch_repository(scratch)
    report = report_path_for(repository, "chat-review")
    result = run_agy_cell(
        repository, stubs, {"*": {"stdout": LONG_CHAT_REVIEW}}, report,
    )
    check("a model that answered a review-length text in chat, writing no file, exits 0",
          result.returncode == 0, f"exit {result.returncode}; stderr={result.stderr!r}")
    report_text = report.read_text(encoding="utf-8") if report.is_file() else ""
    check("its stdout is the report, under a stamp",
          report_text.startswith("<!-- provenance: runtime=agy model=gemini-3.8-flash-low ")
          and LONG_CHAT_REVIEW.strip() in report_text,
          repr(report_text[:200]))
    check("the recovery is announced on stderr under the pinned phrase",
          any(line.startswith(f"cold-read-agy-cell: {STDOUT_RECOVERY_PHRASE}")
              for line in result.stderr.splitlines()),
          repr(result.stderr))

    # --- A short stdout is a remark, not a review -------------------------
    repository = build_scratch_repository(scratch)
    report = report_path_for(repository, "chat-remark")
    result = run_agy_cell(
        repository, stubs, {"*": {"stdout": SHORT_CHAT_REMARK}}, report,
    )
    check("a model that wrote no file and only remarked in chat fails the cell",
          result.returncode == 1 and not report.exists(),
          f"exit {result.returncode}; stderr={result.stderr!r}")
    check("no stdout recovery is announced for a remark",
          STDOUT_RECOVERY_PHRASE not in result.stderr, repr(result.stderr))
    check("the remark itself still reaches stderr, as the model's own account",
          SHORT_CHAT_REMARK.strip() in result.stderr, repr(result.stderr))

    # --- A non-zero exit is a failure whatever stdout holds ---------------
    repository = build_scratch_repository(scratch)
    report = report_path_for(repository, "chat-then-crash")
    result = run_agy_cell(
        repository, stubs, {"*": {"stdout": LONG_CHAT_REVIEW, "exit": 1}}, report,
    )
    check("a review-length stdout from a model that exited non-zero is not a report",
          result.returncode == 1 and not report.exists(),
          f"exit {result.returncode}; stderr={result.stderr!r}")

    # --- A file one directory away wins over stdout ------------------------
    repository = build_scratch_repository(scratch)
    report = report_path_for(repository, "near-miss-beats-chat")
    result = run_agy_cell(
        repository, stubs,
        {"*": {"near_miss": "STUB AGY REVIEW: written one character away\n",
               "stdout": LONG_CHAT_REVIEW}},
        report,
    )
    report_text = report.read_text(encoding="utf-8") if report.is_file() else ""
    check("a near-miss file is recovered as the report, and stdout is left alone",
          result.returncode == 0
          and "written one character away" in report_text
          and LONG_CHAT_REVIEW.strip() not in report_text,
          f"exit {result.returncode}; report={report_text[:200]!r}")
    check("the near-miss recovery, not the stdout one, is what is announced",
          NEAR_MISS_RECOVERY_PHRASE in result.stderr
          and STDOUT_RECOVERY_PHRASE not in result.stderr,
          repr(result.stderr))

    # --- --model and --effort override the pin and are stamped as run -----
    repository = build_scratch_repository(scratch)
    report = report_path_for(repository, "override")
    result = run_agy_cell(
        repository, stubs,
        {"gemini-3.8-flash-high": {"report": "STUB AGY REVIEW: at high\n"}},
        report, "--model", "gemini-3.8-flash-high", "--effort", "high",
    )
    stamp = provenance_stamp_of(report)
    check("--model and --effort are honored and stamped",
          result.returncode == 0
          and " model=gemini-3.8-flash-high " in stamp and " effort=high " in stamp,
          f"exit {result.returncode}; stamp={stamp!r}; stderr={result.stderr!r}")

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
