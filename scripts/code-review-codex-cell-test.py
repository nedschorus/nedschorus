#!/usr/bin/env python3
"""Tests for code-review-codex-cell.py.

Builds a scratch git repository with one commit and runs the cell against
it with a stub `codex` first on PATH, so no real review is ever launched:
the stub is the seam that lets the cell's own logic be tested without the
model, the money, or the half hour.

Two things are pinned here.

  - Bad invocations are reported, not thrown -- asserted on the exit code AND
    on the absence of a traceback, because an unhandled exception exits 1 just
    as a reported failure does. The cell already answers a `--repo` that is
    not a checkout, and a `--base`/`--commit` that does not resolve, with a
    message on stderr and exit 2. An `--output` naming something that is not a
    regular file is the third of that kind: before 2026-08-23 a directory
    there reached `unlink()` and died on a traceback (PermissionError on
    macOS, IsADirectoryError on Linux). The guard is deliberately wider than
    "is a directory", so a FIFO case holds it there -- and the FIFO is the
    input where the old code did not traceback at all but silently succeeded,
    consuming the FIFO and writing a regular file over it.

  - The pre-run delete of the output file still happens. It is there so
    that a stale report from an earlier run cannot survive a run in which
    codex writes nothing and then be stamped with this run's provenance
    header — the defect fixed on pull request #110. The stub that exits 0
    without writing reproduces exactly that setup, so the case fails loudly
    if anyone ever "simplifies" the delete away.

Run: python3 scripts/code-review-codex-cell-test.py
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

CELL_SCRIPT = Path(__file__).with_name("code-review-codex-cell.py")

# A stub codex that writes the report it was asked for, then exits 0 — the
# successful-review path.
STUB_CODEX_WRITES_REPORT = """#!/usr/bin/env python3
import sys
argv = sys.argv
target = argv[argv.index("--output-last-message") + 1]
open(target, "w", encoding="utf-8").write("STUB CODEX REPORT: P3 nothing to see\\n")
sys.exit(0)
"""

# A stub codex that exits 0 having written nothing — the silent-absence path
# the cell must treat as a failure rather than as a clean review.
STUB_CODEX_WRITES_NOTHING = """#!/usr/bin/env python3
import sys
sys.exit(0)
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


def run_cell(stub_directory, stub_body, *arguments):
    """Run the cell with a stub codex first on PATH.

    Run as a subprocess, not by importing main(): on the unfixed code the
    directory case raises, and a subprocess turns that into a readable exit
    code and traceback on stderr instead of aborting the whole suite.
    """
    stub_directory.mkdir(parents=True, exist_ok=True)
    stub = stub_directory / "codex"
    stub.write_text(stub_body, encoding="utf-8")
    stub.chmod(0o755)
    environment = dict(os.environ)
    environment["PATH"] = f"{stub_directory}{os.pathsep}{environment.get('PATH', '')}"
    return subprocess.run(
        [sys.executable, str(CELL_SCRIPT), *arguments],
        capture_output=True, text=True, check=False, env=environment,
    )


with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch)
    stubs = scratch / "stub-bin"

    checkout = scratch / "checkout"
    checkout.mkdir()
    git(checkout, "init", "-b", "main")
    git(checkout, "config", "user.email", "test@test.invalid")
    git(checkout, "config", "user.name", "code-review-codex-cell test")
    (checkout / "README.md").write_text("# scratch\n", encoding="utf-8")
    git(checkout, "add", "-A")
    git(checkout, "commit", "-m", "seed")
    head_sha = git(checkout, "rev-parse", "HEAD").strip()

    # --- The bad invocations the cell already answered ---------------------
    # Recorded here as the convention the --output check below matches: a
    # message on stderr and exit 2, never a traceback.
    not_a_checkout = scratch / "not-a-checkout"
    not_a_checkout.mkdir()
    result = run_cell(stubs, STUB_CODEX_WRITES_REPORT,
                      "--commit", head_sha, "--repo", str(not_a_checkout),
                      "--output", str(scratch / "report-a.md"))
    check("--repo that is not a checkout exits 2",
          result.returncode == 2, f"exit {result.returncode}; stderr={result.stderr!r}")
    check("--repo that is not a checkout says so on stderr",
          "is not a checkout" in result.stderr, repr(result.stderr))

    result = run_cell(stubs, STUB_CODEX_WRITES_REPORT,
                      "--commit", "no-such-commit", "--repo", str(checkout),
                      "--output", str(scratch / "report-b.md"))
    check("--commit that does not resolve exits 2",
          result.returncode == 2, f"exit {result.returncode}; stderr={result.stderr!r}")
    check("--commit that does not resolve says so on stderr",
          "does not resolve to a commit" in result.stderr, repr(result.stderr))

    # --- The third bad invocation: --output is not a regular file ----------
    # Before the 2026-08-23 fix this reached output_path.unlink() and died on
    # an unhandled OSError, exiting 1 with a traceback.
    existing_directory = scratch / "existing-dir-as-output"
    existing_directory.mkdir()
    result = run_cell(stubs, STUB_CODEX_WRITES_REPORT,
                      "--commit", head_sha, "--repo", str(checkout),
                      "--output", str(existing_directory))
    check("--output naming an existing directory exits 2",
          result.returncode == 2, f"exit {result.returncode}; stderr={result.stderr!r}")
    check("--output naming an existing directory says so on stderr",
          "is not a regular file" in result.stderr, repr(result.stderr))
    check("--output naming an existing directory does not raise",
          "Traceback" not in result.stderr, repr(result.stderr))
    check("--output naming an existing directory leaves it in place",
          existing_directory.is_dir(), "the check must report, not delete")

    # A FIFO is the other half of that guard, and the half that behaves
    # differently from a directory: unlink removes a FIFO perfectly well, so
    # before the guard this run SUCCEEDED -- the FIFO was consumed and a
    # regular file left in its place. The guard is deliberately wider than
    # "is a directory", and this case is what holds it there: narrowing it to
    # is_dir() passes every other case in this file.
    fifo_output = scratch / "a-fifo-as-output"
    os.mkfifo(fifo_output)
    result = run_cell(stubs, STUB_CODEX_WRITES_REPORT,
                      "--commit", head_sha, "--repo", str(checkout),
                      "--output", str(fifo_output))
    check("--output naming an existing FIFO exits 2",
          result.returncode == 2, f"exit {result.returncode}; stderr={result.stderr!r}")
    check("--output naming an existing FIFO says so on stderr",
          "is not a regular file" in result.stderr, repr(result.stderr))
    check("--output naming an existing FIFO leaves it a FIFO",
          fifo_output.is_fifo(),
          "the guard narrowed to directories only; the FIFO was consumed")

    # --- The normal paths, which must keep working -------------------------
    fresh_report = scratch / "fresh-report.md"
    result = run_cell(stubs, STUB_CODEX_WRITES_REPORT,
                      "--commit", head_sha, "--repo", str(checkout),
                      "--output", str(fresh_report))
    check("an --output that does not exist yet is accepted",
          result.returncode == 0, f"exit {result.returncode}; stderr={result.stderr!r}")
    text = fresh_report.read_text(encoding="utf-8") if fresh_report.is_file() else ""
    check("the report carries its provenance header",
          text.startswith("<!-- provenance: runtime=codex-exec-review"), repr(text[:120]))
    check("the report carries what codex wrote",
          "STUB CODEX REPORT" in text, repr(text[:200]))

    # An --output that already holds a file is still accepted, and the file
    # is replaced rather than appended to.
    overwritten_report = scratch / "overwritten-report.md"
    overwritten_report.write_text("STALE REPORT FROM AN EARLIER RUN\n", encoding="utf-8")
    result = run_cell(stubs, STUB_CODEX_WRITES_REPORT,
                      "--commit", head_sha, "--repo", str(checkout),
                      "--output", str(overwritten_report))
    check("an --output that already holds a file is accepted",
          result.returncode == 0, f"exit {result.returncode}; stderr={result.stderr!r}")
    text = overwritten_report.read_text(encoding="utf-8") if overwritten_report.is_file() else ""
    check("the stale text is gone from the new report",
          "STALE REPORT FROM AN EARLIER RUN" not in text, repr(text[:200]))

    # The pre-run delete, pinned. Codex exits 0 without writing; without the
    # delete, the stale file survives, passes the is_file()/non-empty check,
    # and gets stamped with this run's provenance — pull request #110's
    # defect. With the delete, the run is correctly reported as failed.
    stale_report = scratch / "stale-report.md"
    stale_report.write_text("STALE REPORT FROM AN EARLIER RUN\n", encoding="utf-8")
    result = run_cell(stubs, STUB_CODEX_WRITES_NOTHING,
                      "--commit", head_sha, "--repo", str(checkout),
                      "--output", str(stale_report))
    check("a run that writes no report is reported as failed",
          result.returncode == 1, f"exit {result.returncode}; stderr={result.stderr!r}")
    # Exit 1 alone cannot tell a reported failure from a thrown one: an
    # unhandled exception exits 1 too. Removing the empty-report check makes
    # this run die on FileNotFoundError at the read below it, still exiting 1.
    check("a run that writes no report is reported, not thrown",
          "Traceback" not in result.stderr, repr(result.stderr))
    check("a stale report does not survive a run that wrote nothing",
          not stale_report.exists(),
          "the pre-run delete is gone; a stale report can be stamped as fresh")

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
