#!/usr/bin/env python3
"""Tests for cold-read-grid.py.

Builds a scratch repository shaped like this one and copies the grid into it,
then puts stub cell launchers where the grid expects the real ones. No model,
and no runtime, is ever launched: a stub launcher writes the report it was
told to write and exits, which is the seam that lets the grid's own logic be
tested in seconds.

The grid is COPIED into the scratch tree rather than symlinked because it
computes `REPO_ROOT` as `Path(__file__).resolve().parent.parent`, and
`resolve()` follows a symlink back to the real checkout — which would make
these cases write record directories into the user's own repository.

Two behaviours are pinned here, both ruled 2026-08-25 under "the run reports
what it actually did".

  - AN UNREVIEWABLE TARGET IS REFUSED, AND THE REFUSAL NAMES THE RULE.
    nedschorus#152 takes documents whose stem ends in `-log`, `-report` or
    `-capture` out of the review path: they only record what happened. The
    same issue rules the skip must be announced — "A suffix list can miss a
    genre nobody anticipated; announcing the skip is what makes that visible
    instead of silent." All three suffixes are cased, and a name that ends in
    none of them is cased too, because a check that refuses everything also
    passes every refusal case.

  - A TARGET EDITED MID-RUN COMPROMISES THE WHOLE SET. On 2026-08-24 the
    merge-lane seat had to mark a record set COMPROMISED by hand after the
    target was edited under it; the only tell was a clean-looking report whose
    "clean sections" quietly omitted the sections that had changed. The
    reports are kept — they are evidence — but marked, announced, and the run
    exits non-zero.

Also pinned: the grid lifts a cell's near-miss recovery onto its own output as
`RECOVERED:`, the way it already lifts `STRAY WRITE:` and `FELL BACK:`. That
branch is also the branch that deletes the cell's log, so a line not lifted
there is a line destroyed on the one path that produces it.

Run: python3 scripts/cold-read-grid-test.py
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REAL_SCRIPTS_DIR = Path(__file__).resolve().parent
GRID_SCRIPT_NAME = "cold-read-grid.py"

# Every stub launcher is this frame plus a body. The grid execs the launcher
# directly, so these are real executables with a shebang, not modules.
STUB_LAUNCHER_FRAME = """#!/usr/bin/env python3
import pathlib, sys
argv = sys.argv
report = pathlib.Path(argv[argv.index("--report") + 1])
target = pathlib.Path(argv[argv.index("--target") + 1])
{body}
sys.exit(0)
"""

# A report that opens with a provenance stamp, as every real report does — the
# half of the target-changed marking that must insert AFTER the first line.
BODY_WRITES_A_STAMPED_REPORT = """
report.write_text(
    "<!-- provenance: runtime=stub model=stub-model effort=high "
    "cell=defect-hunt tier=floor duration_s=0 target=" + str(target) + " -->\\n"
    "\\nSTUB REPORT: one finding\\n", encoding="utf-8")
"""

BODY_WRITES_A_STAMPED_REPORT_AND_ANNOUNCES_A_RECOVERY = BODY_WRITES_A_STAMPED_REPORT + """
sys.stderr.write(
    "cold-read-codex-cell: recovered a near-miss report — the model wrote "
    "a sibling path instead of " + str(report) + ".\\n")
"""

BODY_WRITES_A_STAMPED_REPORT_AND_EDITS_THE_TARGET = BODY_WRITES_A_STAMPED_REPORT + """
with target.open("a", encoding="utf-8") as handle:
    handle.write("a sentence added while the reviewers were reading\\n")
"""

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def build_scratch_repository(root, launcher_body):
    repo = root / "scratch-repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copy2(REAL_SCRIPTS_DIR / GRID_SCRIPT_NAME, repo / "scripts" / GRID_SCRIPT_NAME)
    for runtime in ("claude", "codex"):
        launcher = repo / "scripts" / f"cold-read-{runtime}-cell.py"
        launcher.write_text(STUB_LAUNCHER_FRAME.format(body=launcher_body),
                            encoding="utf-8")
        launcher.chmod(0o755)
    (repo / "docs").mkdir()
    return repo


def write_target(repo, name):
    target = repo / "docs" / name
    target.write_text("# A document\n\nOne sentence to review.\n", encoding="utf-8")
    return target


def run_grid(repo, target_relative_path):
    return subprocess.run(
        [sys.executable, str(repo / "scripts" / GRID_SCRIPT_NAME),
         "--target", target_relative_path],
        capture_output=True, text=True, check=False,
    )


# --- The genre-suffix refusal ---------------------------------------------
# Free to test: a refused target exits before any cell is launched, so these
# cases never wait on the grid's polling loop.
with tempfile.TemporaryDirectory() as scratch:
    repo = build_scratch_repository(Path(scratch), BODY_WRITES_A_STAMPED_REPORT)
    for genre_suffix in ("-log", "-report", "-capture"):
        name = f"the-thing-that-happened{genre_suffix}.md"
        write_target(repo, name)
        result = run_grid(repo, f"docs/{name}")
        check(f"a `{genre_suffix}` target is refused with exit 2",
              result.returncode == 2,
              f"exit {result.returncode}; stderr={result.stderr!r}")
        check(f"the `{genre_suffix}` refusal names the suffix that fired",
              f"`{genre_suffix}`" in result.stderr, repr(result.stderr))
        check(f"the `{genre_suffix}` refusal names the issue that rules it",
              "nedschorus#152" in result.stderr, repr(result.stderr))
        check(f"a `{genre_suffix}` refusal creates no record directory",
              not (repo / "cold-read-records").exists(),
              "the refusal ran after the record directory was made")

    # The other half of the check: a name ending in none of the suffixes is not
    # refused. Without this case, a check that refused every target would pass
    # every case above.
    name = "a-document-worth-reading-notes.md"
    write_target(repo, name)
    result = run_grid(repo, f"docs/{name}")
    check("a name ending in no genre suffix is not refused",
          result.returncode == 0,
          f"exit {result.returncode}; stdout={result.stdout!r}; stderr={result.stderr!r}")
    check("a name ending in no genre suffix reaches the reviewers",
          result.stdout.count("saved: ") == 8, repr(result.stdout))
    check("an accepted run says nothing about a genre suffix",
          "genre suffix" not in result.stderr, repr(result.stderr))
    check("an unedited target is not reported as changed",
          "TARGET CHANGED DURING RUN" not in result.stdout, repr(result.stdout))

# --- The grid lifts a cell's recovery onto its own output ------------------
with tempfile.TemporaryDirectory() as scratch:
    repo = build_scratch_repository(
        Path(scratch), BODY_WRITES_A_STAMPED_REPORT_AND_ANNOUNCES_A_RECOVERY)
    write_target(repo, "a-recovered-run.md")
    result = run_grid(repo, "docs/a-recovered-run.md")
    check("a run whose cells recovered a near-miss still succeeds",
          result.returncode == 0,
          f"exit {result.returncode}; stdout={result.stdout!r}; stderr={result.stderr!r}")
    check("the grid prints RECOVERED: for each cell that recovered a report",
          result.stdout.count("RECOVERED: ") == 8, repr(result.stdout))
    check("the RECOVERED line names the cell it belongs to",
          "RECOVERED: codex-hunt-floor.md" in result.stdout, repr(result.stdout))

# --- The target is frozen for the run --------------------------------------
with tempfile.TemporaryDirectory() as scratch:
    repo = build_scratch_repository(
        Path(scratch), BODY_WRITES_A_STAMPED_REPORT_AND_EDITS_THE_TARGET)
    write_target(repo, "a-document-edited-mid-run.md")
    result = run_grid(repo, "docs/a-document-edited-mid-run.md")
    check("a target edited mid-run exits non-zero, and with its own code",
          result.returncode == 3,
          f"exit {result.returncode}; stdout={result.stdout!r}; stderr={result.stderr!r}")
    check("the grid says so on its own output, in one line",
          result.stdout.count("TARGET CHANGED DURING RUN:") == 1, repr(result.stdout))
    check("the grid names both fingerprints",
          "when the cells launched" in result.stdout
          and "when the last one finished" in result.stdout, repr(result.stdout))

    record_dirs = sorted((repo / "cold-read-records").iterdir())
    check("the run left exactly one record directory",
          len(record_dirs) == 1, [str(d) for d in record_dirs])
    record_dir = record_dirs[0]
    reports = sorted(record_dir.glob("*.md"))
    # Eight cell reports plus the reference-integrity pre-pass.
    check("every report in the set is still on disk — they are evidence",
          len(reports) == 9, [r.name for r in reports])
    check("every report in the set carries the marker",
          all("<!-- TARGET CHANGED DURING RUN:" in r.read_text(encoding="utf-8")
              for r in reports),
          [r.name for r in reports
           if "<!-- TARGET CHANGED DURING RUN:" not in r.read_text(encoding="utf-8")])

    stamped = record_dir / "codex-hunt-floor.md"
    stamped_lines = stamped.read_text(encoding="utf-8").split("\n")
    check("a stamped report keeps its provenance stamp as the first line",
          stamped_lines[0].startswith("<!-- provenance:"), repr(stamped_lines[0]))
    check("the marker goes immediately after the stamp",
          stamped_lines[1].startswith("<!-- TARGET CHANGED DURING RUN:"),
          repr(stamped_lines[1]))
    check("the reviewer's own text survives the marking",
          "STUB REPORT: one finding" in stamped.read_text(encoding="utf-8"),
          repr(stamped.read_text(encoding="utf-8")[:200]))

    unstamped_lines = (record_dir / "reference-check.md").read_text(
        encoding="utf-8").split("\n")
    check("a report with no stamp takes the marker at the top",
          unstamped_lines[0].startswith("<!-- TARGET CHANGED DURING RUN:"),
          repr(unstamped_lines[0]))

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
