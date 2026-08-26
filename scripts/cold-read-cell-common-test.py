#!/usr/bin/env python3
"""Tests for cold-read-cell-common.py, driven through both cell launchers.

Builds a scratch repository shaped like this one — `scripts/`, the cold-read
prompt templates, a git checkout, a `.gitignore` that hides the records tree —
copies the three cell scripts into it, and runs them with a stub `claude` or
`codex` first on PATH. No model is ever launched: the stub is the seam that
lets the cell's own logic be tested without the model, the money, or the half
hour.

The scripts are COPIED rather than symlinked, and this is load-bearing: every
one of them computes `REPO_ROOT` as `Path(__file__).resolve().parent.parent`,
and `resolve()` follows a symlink back to the real checkout — which would
point the record directories, the prompt lookup and the stray-write detector
at the user's own repository instead of the scratch one.

Four behaviours are pinned here, all ruled 2026-08-25 under "the run reports
what it actually did".

  - A NEAR-MISS REPORT IS RECOVERED BEFORE FAILURE IS DECLARED. That day a
    Codex cell wrote a complete 33-finding review to a record directory one
    character from the one it was given, having created that directory itself,
    and the cell reported "the model exited without writing" — true of the
    path it watched, false of the work. Recovery accepts exactly one candidate
    and refuses to guess between several; a file that predates the attempt is
    not this attempt's report and is left alone.

    The search covers the whole `cold-read-records/` tree — a neighbouring
    record directory, and the root of the tree itself — because the file name
    carries the run (user-ruled 2026-08-25): the grid writes
    `<record directory name>--<runtime>-<pass>-<tier>.md`, so an exact-name
    match belongs to this run and to no other. The case that proves the point
    is the concurrent one: a second grid's report for the same cell, written
    while this attempt ran, is NOT this attempt's report, and the cell fails
    rather than taking it.

  - THE STAMP CARRIES WHAT THE CELL COST. `duration_s=` on every stamp,
    `tokens=` when the runtime reported a total. Absent is absent: a claude
    cell, and a codex cell whose CLI printed no total, carry no `tokens=`
    field rather than a guessed zero. The total is read from the runtime's
    stderr and never from stdout, which is the model's own text — a reviewer
    of a document about model costs can write "tokens used: N" in its
    findings, and that sentence is not what the run cost.

  - THE RUNTIME'S STDERR SURVIVES A SUCCESSFUL RUN. It used to be passed
    straight through to a log the grid deletes on success, which is why the
    only token figure recoverable from six grids that day came from the one
    cell that failed.

  - THE STRAY-WRITE DETECTOR RUNS FOR BOTH RUNTIMES. Pinned once per
    launcher, because the fleet's other review instrument
    (scripts/sanity-check-attacks.py) gates the same comparison on
    `runtime == "codex"` and a claude agent wrote a 25KB file into a worktree
    undetected during a live run — nedschorus#161. Here the call sits on the
    shared path, and these two cases are what make a reintroduced gate fail
    loudly instead of quietly.

Run: python3 scripts/cold-read-cell-common-test.py
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REAL_SCRIPTS_DIR = Path(__file__).resolve().parent
CELL_SCRIPT_NAMES = (
    "cold-read-cell-common.py",
    "cold-read-claude-cell.py",
    "cold-read-codex-cell.py",
)

# The stub prompt templates. Only two things matter about them: they are named
# what the cells look for, and they carry the report path in a form a stub can
# find. The real templates are prose for a model and would tell a stub nothing.
STUB_PROMPT_TEMPLATE = """STUB PROMPT for scripts/cold-read-cell-common-test.py.
TARGET_PATH_IS: {TARGET_PATH}
REPORT_PATH_IS: {REPORT_PATH}
"""

# Every stub is this frame plus a body. The frame recovers the report path the
# cell asked for, differing between runtimes in one line: the claude cell feeds
# its prompt on stdin, the codex cell passes it as the last argument.
STUB_FRAME = """#!/usr/bin/env python3
import os, pathlib, re, sys
{prompt_source}
report = re.search(r"REPORT_PATH_IS: (.*)", prompt).group(1).strip()
{body}
sys.exit(0)
"""
PROMPT_FROM_STDIN = "prompt = sys.stdin.read()"
PROMPT_FROM_LAST_ARGUMENT = "prompt = sys.argv[-1]"

BODY_WRITES_ITS_REPORT = """
pathlib.Path(report).write_text("STUB REPORT: one finding\\n", encoding="utf-8")
"""

# The 2026-08-25 incident, reproduced: the model creates a record directory one
# character from the one it was given and writes its whole review there.
BODY_WRITES_ONE_CHARACTER_AWAY = """
given = pathlib.Path(report)
sibling = given.parent.parent / (given.parent.name[:-1] + "X")
sibling.mkdir(parents=True, exist_ok=True)
(sibling / given.name).write_text(
    "STUB REPORT: written one character away\\n", encoding="utf-8")
"""

BODY_WRITES_TO_TWO_SIBLINGS = """
given = pathlib.Path(report)
for replacement in ("X", "Y"):
    sibling = given.parent.parent / (given.parent.name[:-1] + replacement)
    sibling.mkdir(parents=True, exist_ok=True)
    (sibling / given.name).write_text(
        "STUB REPORT: one of two candidates\\n", encoding="utf-8")
"""

# A model that writes its report under the right file name into the root of
# the records tree rather than into any record directory.
BODY_WRITES_FLAT_INTO_THE_RECORDS_ROOT = """
given = pathlib.Path(report)
(given.parent.parent / given.name).write_text(
    "STUB REPORT: written flat into the records root\\n", encoding="utf-8")
"""

# A SECOND GRID'S REPORT, landing while this attempt runs. Same cell, same
# runtime, same day, different run — so a different prefix. This is the file
# the recovery must not take: it is a finished review of whatever THAT grid was
# reviewing, and moving it here would put the wrong document's review under
# this run's stamp and leave the other run with no report at all.
BODY_WRITES_A_CONCURRENT_RUNS_REPORT = """
given = pathlib.Path(report)
other_run = given.parent.name.replace("aaaaaaa", "bbbbbbb")
other_dir = given.parent.parent / other_run
other_dir.mkdir(parents=True, exist_ok=True)
(other_dir / given.name.replace("aaaaaaa", "bbbbbbb")).write_text(
    "STUB REPORT: a concurrent grid's review of another document\\n",
    encoding="utf-8")
"""

BODY_WRITES_NOTHING = """
pass
"""

# A reviewer that writes its report AND edits something else in the worktree —
# the accident the stray-write detector exists for.
STRAY_FILE_NAME = "stray-file-the-reviewer-wrote.md"
BODY_WRITES_ITS_REPORT_AND_A_STRAY_FILE = """
pathlib.Path(report).write_text("STUB REPORT: one finding\\n", encoding="utf-8")
pathlib.Path(os.getcwd(), "%s").write_text(
    "the reviewer wrote here and should not have\\n", encoding="utf-8")
""" % STRAY_FILE_NAME

# The Codex CLI's end-of-run token total, on stderr, comma-grouped as it prints
# it. The frame runs before the report is written so the ordering the real CLI
# uses is not accidentally depended on.
BODY_WRITES_ITS_REPORT_AND_PRINTS_A_TOKEN_TOTAL = """
sys.stderr.write("[2026-08-25T12:00:00] tokens used: 12,345\\n")
pathlib.Path(report).write_text("STUB REPORT: one finding\\n", encoding="utf-8")
"""

# A reviewer whose own commentary contains the phrase — entirely ordinary when
# the document under review is about model costs. stdout is the model talking,
# not the CLI reporting, and a stamp that took this number would price the run
# from a sentence the reviewer wrote.
BODY_WRITES_ITS_REPORT_AND_SAYS_TOKENS_USED_IN_ITS_FINDINGS = """
sys.stdout.write("The draft claims tokens used: 99,999 per run, which I doubt.\\n")
pathlib.Path(report).write_text("STUB REPORT: one finding\\n", encoding="utf-8")
"""

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def git(repo, *arguments):
    completed = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        capture_output=True, text=True, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(arguments)}: {completed.stderr.strip()}")
    return completed.stdout


def build_scratch_repository(root):
    """A checkout shaped like this one, with the cell scripts copied into it."""
    repo = root / "scratch-repo"
    (repo / "scripts").mkdir(parents=True)
    prompts = repo / ".claude" / "skills" / "cold-read" / "prompts"
    prompts.mkdir(parents=True)
    for name in CELL_SCRIPT_NAMES:
        shutil.copy2(REAL_SCRIPTS_DIR / name, repo / "scripts" / name)
    for cell in ("restate", "defect-hunt"):
        (prompts / f"{cell}.md").write_text(STUB_PROMPT_TEMPLATE, encoding="utf-8")
    (repo / "docs").mkdir()
    (repo / "docs" / "target-under-review.md").write_text(
        "# A document\n\nOne sentence to review.\n", encoding="utf-8")
    # The records tree is gitignored here exactly as it is in the real
    # repository, so a cell's own report never reads as a stray write.
    (repo / ".gitignore").write_text("cold-read-records/\n", encoding="utf-8")
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "test@test.invalid")
    git(repo, "config", "user.name", "cold-read-cell-common test")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "seed")
    return repo


def report_path_for(repo, case_slug, runtime):
    """A report path shaped exactly as the grid names one: the record
    directory's own name, then `--`, then the cell.

    A fresh record directory per case, so one case's near-miss leavings are
    never a candidate for the next case's recovery — and with the run in the
    file name, that isolation now holds by name rather than by mtime alone.
    """
    record_dir_name = f"2026-08-25-{case_slug}-aaaaaaa"
    return (repo / "cold-read-records" / record_dir_name
            / f"{record_dir_name}--{runtime}-hunt-floor.md")


def run_cell(repo, stub_bin, runtime, body, report, extra_arguments=()):
    stub_body_source = STUB_FRAME.format(
        prompt_source=(PROMPT_FROM_STDIN if runtime == "claude"
                       else PROMPT_FROM_LAST_ARGUMENT),
        body=body,
    )
    stub_bin.mkdir(parents=True, exist_ok=True)
    stub = stub_bin / runtime
    stub.write_text(stub_body_source, encoding="utf-8")
    stub.chmod(0o755)
    environment = dict(os.environ)
    environment["PATH"] = f"{stub_bin}{os.pathsep}{environment.get('PATH', '')}"
    return subprocess.run(
        [sys.executable, str(repo / "scripts" / f"cold-read-{runtime}-cell.py"),
         "--cell", "defect-hunt", "--tier", "floor",
         "--target", "docs/target-under-review.md",
         "--report", str(report), *extra_arguments],
        capture_output=True, text=True, check=False, env=environment,
    )


def stamp_line_of(report):
    if not report.is_file():
        return ""
    return report.read_text(encoding="utf-8").splitlines()[0]


with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch)
    repo = build_scratch_repository(scratch)
    stub_bin = scratch / "stub-bin"

    # --- 1. The near-miss report is recovered ------------------------------
    report = report_path_for(repo, "near-miss", "codex")
    result = run_cell(repo, stub_bin, "codex", BODY_WRITES_ONE_CHARACTER_AWAY, report)
    check("a report written one directory away is recovered, and the cell succeeds",
          result.returncode == 0, f"exit {result.returncode}; stderr={result.stderr!r}")
    check("the recovered report is at the path the cell was given",
          report.is_file(), f"{report} absent")
    text = report.read_text(encoding="utf-8") if report.is_file() else ""
    check("the recovered report holds what the model actually wrote",
          "written one character away" in text, repr(text[:200]))
    check("the recovered report is stamped like any other",
          text.startswith("<!-- provenance: runtime=codex"), repr(text[:120]))
    check("the recovery is announced on stderr for the grid to lift",
          "recovered a near-miss report" in result.stderr, repr(result.stderr))
    near_miss_sibling = (report.parent.parent
                         / (report.parent.name[:-1] + "X") / report.name)
    check("the near-miss copy is moved, not copied",
          not near_miss_sibling.exists(),
          "two files now hold one review, which is the ambiguity recovery removes")

    # Two candidates is ambiguous, and a guess would put a review under a stamp
    # that may not describe it. Refused, and the refusal names both.
    report = report_path_for(repo, "two-candidates", "codex")
    result = run_cell(repo, stub_bin, "codex", BODY_WRITES_TO_TWO_SIBLINGS, report)
    check("two near-miss candidates fail the cell rather than being guessed between",
          result.returncode == 1, f"exit {result.returncode}; stderr={result.stderr!r}")
    check("the refusal says the candidates were ambiguous",
          "more than one, which is ambiguous" in result.stderr, repr(result.stderr))
    check("neither candidate was moved into place",
          not report.is_file(), f"{report} exists")

    # No candidate at all is the ordinary failure, and it still names where it
    # looked — that is the whole difference from the message that lost a review.
    report = report_path_for(repo, "no-candidate", "codex")
    result = run_cell(repo, stub_bin, "codex", BODY_WRITES_NOTHING, report)
    check("a run that wrote nothing anywhere still fails",
          result.returncode == 1, f"exit {result.returncode}; stderr={result.stderr!r}")
    check("the failure names what it looked for",
          "no near-miss report to recover" in result.stderr
          and report.name in result.stderr
          and "anywhere under" in result.stderr
          and str(repo / "cold-read-records") in result.stderr, repr(result.stderr))

    # A file that predates the attempt is not this attempt's report. Without the
    # mtime cutoff, yesterday's abandoned stray would be recovered today and
    # stamped with today's model.
    report = report_path_for(repo, "stale-sibling", "codex")
    stale_sibling = report.parent.parent / (report.parent.name[:-1] + "X")
    stale_sibling.mkdir(parents=True, exist_ok=True)
    stale_file = stale_sibling / report.name
    stale_file.write_text("STUB REPORT: from a run that finished yesterday\n",
                          encoding="utf-8")
    an_hour_ago = time.time() - 3600
    os.utime(stale_file, (an_hour_ago, an_hour_ago))
    result = run_cell(repo, stub_bin, "codex", BODY_WRITES_NOTHING, report)
    check("a sibling file older than the attempt is not recovered",
          result.returncode == 1, f"exit {result.returncode}; stderr={result.stderr!r}")
    check("the stale sibling is left where it was",
          stale_file.is_file(), "an older run's file was consumed by this one")
    check("no report was fabricated from the stale sibling",
          not report.is_file(), f"{report} exists")

    # A report written flat into the records root, rather than into any record
    # directory, is still this run's report: the name says so. The search
    # covers the root of the tree and not only the directories under it.
    report = report_path_for(repo, "flat-in-records-root", "codex")
    result = run_cell(repo, stub_bin, "codex",
                      BODY_WRITES_FLAT_INTO_THE_RECORDS_ROOT, report)
    check("a report written flat into cold-read-records/ is recovered",
          result.returncode == 0, f"exit {result.returncode}; stderr={result.stderr!r}")
    check("the report recovered from the records root is at the path given",
          report.is_file(), f"{report} absent")
    text = report.read_text(encoding="utf-8") if report.is_file() else ""
    check("it holds what the model wrote in the records root",
          "written flat into the records root" in text, repr(text[:200]))
    check("the copy in the records root is moved, not copied",
          not (report.parent.parent / report.name).exists(),
          "two files now hold one review")

    # THE CASE THE RUN-NAMED FILE EXISTS FOR (user-ruled 2026-08-25). A second
    # grid, running at the same time in the same checkout, writes its own
    # report for the same cell while this attempt runs. Under the old bare
    # names both files were `codex-hunt-floor.md`, and this cell could recover
    # the other run's correctly placed report: this run would then hold a
    # review of the wrong document under its stamp, and the other run would
    # lose the review it produced. The prefix is what makes the two
    # distinguishable, and this case is what proves the distinction holds.
    report = report_path_for(repo, "concurrent-run", "codex")
    result = run_cell(repo, stub_bin, "codex",
                      BODY_WRITES_A_CONCURRENT_RUNS_REPORT, report)
    check("a concurrent run's report is not recovered as this run's",
          result.returncode == 1, f"exit {result.returncode}; stderr={result.stderr!r}")
    check("no report was fabricated from the concurrent run's file",
          not report.is_file(), f"{report} exists")
    concurrent_report = (
        report.parent.parent / report.parent.name.replace("aaaaaaa", "bbbbbbb")
        / report.name.replace("aaaaaaa", "bbbbbbb"))
    check("the concurrent run keeps the report it wrote",
          concurrent_report.is_file(),
          f"{concurrent_report} was taken from the run that wrote it")
    check("the failure names the file it looked for, prefix and all",
          "no near-miss report to recover" in result.stderr
          and report.name in result.stderr
          and "anywhere under" in result.stderr
          and str(repo / "cold-read-records") in result.stderr, repr(result.stderr))

    # --- 2. The stamp carries what the cell cost ---------------------------
    report = report_path_for(repo, "duration-claude", "claude")
    result = run_cell(repo, stub_bin, "claude", BODY_WRITES_ITS_REPORT, report)
    check("a claude cell succeeds with a stub runtime",
          result.returncode == 0, f"exit {result.returncode}; stderr={result.stderr!r}")
    stamp = stamp_line_of(report)
    check("a claude stamp carries duration_s",
          re.search(r"\bduration_s=\d+\b", stamp) is not None, repr(stamp))
    check("a claude stamp carries no tokens field, because claude reports none",
          "tokens=" not in stamp, repr(stamp))
    check("target= stays the last field, so a path with a space cannot swallow one",
          re.search(r"target=docs/target-under-review\.md -->$", stamp) is not None,
          repr(stamp))

    report = report_path_for(repo, "tokens-codex", "codex")
    result = run_cell(repo, stub_bin, "codex",
                      BODY_WRITES_ITS_REPORT_AND_PRINTS_A_TOKEN_TOTAL, report)
    check("a codex cell whose CLI printed a token total succeeds",
          result.returncode == 0, f"exit {result.returncode}; stderr={result.stderr!r}")
    stamp = stamp_line_of(report)
    check("the token total reaches the stamp, comma-free",
          "tokens=12345" in stamp, repr(stamp))
    check("that stamp carries duration_s too",
          re.search(r"\bduration_s=\d+\b", stamp) is not None, repr(stamp))
    # The regression this guards: stderr used to go straight to a log the grid
    # deletes on success, so a successful run left no trace of the token line.
    check("the runtime's stderr survives a successful run",
          "tokens used: 12,345" in result.stderr, repr(result.stderr))

    report = report_path_for(repo, "tokens-in-chat-text", "codex")
    result = run_cell(repo, stub_bin, "codex",
                      BODY_WRITES_ITS_REPORT_AND_SAYS_TOKENS_USED_IN_ITS_FINDINGS,
                      report)
    check("a cell whose reviewer only talked about tokens succeeds",
          result.returncode == 0, f"exit {result.returncode}; stderr={result.stderr!r}")
    stamp = stamp_line_of(report)
    check("a number in the reviewer's own words is not stamped as the run's cost",
          "tokens=" not in stamp, repr(stamp))

    report = report_path_for(repo, "no-tokens-codex", "codex")
    result = run_cell(repo, stub_bin, "codex", BODY_WRITES_ITS_REPORT, report)
    check("a codex cell whose CLI printed no total succeeds",
          result.returncode == 0, f"exit {result.returncode}; stderr={result.stderr!r}")
    stamp = stamp_line_of(report)
    check("an unreported token total is omitted, never guessed at",
          "tokens=" not in stamp, repr(stamp))

    # --- 4. The stray-write detector runs for BOTH runtimes ----------------
    # nedschorus#161: the other instrument checks one runtime and a claude
    # agent wrote through the gap. One case per launcher, so removing the check
    # for either one fails here.
    for runtime in ("claude", "codex"):
        stray_file = repo / STRAY_FILE_NAME
        stray_file.unlink(missing_ok=True)
        report = report_path_for(repo, f"stray-{runtime}", runtime)
        result = run_cell(repo, stub_bin, runtime,
                          BODY_WRITES_ITS_REPORT_AND_A_STRAY_FILE, report)
        check(f"the {runtime} cell still succeeds when the reviewer strays",
              result.returncode == 0,
              f"exit {result.returncode}; stderr={result.stderr!r}")
        check(f"the {runtime} cell reports the stray write",
              "changed files outside its report" in result.stderr, repr(result.stderr))
        check(f"the {runtime} cell names the strayed path",
              STRAY_FILE_NAME in result.stderr, repr(result.stderr))
        check(f"the {runtime} cell's own report is not counted as a stray write",
              "cold-read-records" not in result.stderr.split(
                  "changed files outside its report")[-1].split("\n")[0],
              repr(result.stderr))
        stray_file.unlink(missing_ok=True)

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
