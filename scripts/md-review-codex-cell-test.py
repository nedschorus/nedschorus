#!/usr/bin/env python3
"""Tests for md-review-codex-cell.py — its exit codes, and only those.

The cell passes `codex exec`'s exit code through when codex fails, so the
codes it produces itself must not be codes codex also produces. Until
2026-08-23 the cell used 2 for its own refusals and codex exits 2 as well
(measured on codex-cli 0.147.0 that day: a command line codex rejects exits
2, every non-parsing failure exits 1), so one number meant both "the caller
invoked this cell wrongly" and "this cell invoked codex wrongly" — and only
the second is a defect in this repository. The cell's own refusals now exit
64; codex's codes still pass through untouched. What is pinned here is that
seam, from both sides.

The argparse cases are in the set deliberately, not for completeness:
argparse's own default is also 2, so moving only the hand-written checks
would have left the collision standing for the commonest bad invocation
there is, a mistyped flag.

Everything else about this cell — the model and effort pins, the memory
store being off for the launch, the provenance stamp's fields — is NOT
covered here; this file was written for the exit-code seam and does not
stand in for a full suite.

Every case runs the cell with a stub `codex` first on PATH, so no model is
ever called: the stub is the seam that lets the cell's own logic be tested
without the model, the money, or the wait.

Run: python3 scripts/md-review-codex-cell-test.py
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

CELL_SCRIPT = Path(__file__).with_name("md-review-codex-cell.py")

# A stub codex that writes the last message it was asked for, then exits 0 —
# the successful-cell path.
STUB_CODEX_WRITES_REPORT = """#!/usr/bin/env python3
import sys
argv = sys.argv
target = argv[argv.index("--output-last-message") + 1]
open(target, "w", encoding="utf-8").write("STUB CODEX CELL REPORT\\n")
sys.exit(0)
"""


def stub_codex_exits(code):
    """A stub codex that fails with `code` without writing anything."""
    return (
        "#!/usr/bin/env python3\n"
        "import sys\n"
        'sys.stderr.write("stub codex: simulated failure\\n")\n'
        f"sys.exit({code})\n"
    )


failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def run_cell(stub_directory, stub_body, *arguments):
    """Run the cell as a subprocess with a stub codex first on PATH.

    A subprocess, not an import of main(): the exit code is the subject
    here, and a thrown failure has to show up as a code and a traceback on
    stderr rather than aborting this file.
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
    target = scratch / "a-document.md"
    target.write_text("# a document for the cell to be pointed at\n", encoding="utf-8")

    # --- The cell's own refusals ------------------------------------------
    result = run_cell(stubs, STUB_CODEX_WRITES_REPORT,
                      "--cell", "restate", "--tier", "good",
                      "--target", str(scratch / "no-such-document.md"))
    check("a --target that is not a file exits 64",
          result.returncode == 64, f"exit {result.returncode}; stderr={result.stderr!r}")
    check("a --target that is not a file says so on stderr",
          "target not found" in result.stderr, repr(result.stderr))
    check("a --target that is not a file does not raise",
          "Traceback" not in result.stderr, repr(result.stderr))

    # argparse's route into the same channel.
    result = run_cell(stubs, STUB_CODEX_WRITES_REPORT,
                      "--cell", "restate", "--target", str(target))
    check("a missing required option exits 64",
          result.returncode == 64, f"exit {result.returncode}; stderr={result.stderr!r}")
    check("a missing required option still prints argparse's usage text",
          "usage:" in result.stderr, repr(result.stderr))

    result = run_cell(stubs, STUB_CODEX_WRITES_REPORT,
                      "--cell", "restate", "--tier", "good",
                      "--target", str(target), "--no-such-flag")
    check("an unrecognized option exits 64",
          result.returncode == 64, f"exit {result.returncode}; stderr={result.stderr!r}")

    # --- Codex's own failures pass through, code intact --------------------
    # 2 is the case the cell's own refusals were moved off: a 2 out of this
    # cell must mean "codex refused the command this cell composed" and
    # nothing else. If a future edit routes the cell's own refusals back onto
    # 2, or normalizes codex's codes to a fixed failure value, one of these
    # fails.
    for codex_exit_code in (2, 7):
        result = run_cell(stubs, stub_codex_exits(codex_exit_code),
                          "--cell", "restate", "--tier", "good", "--target", str(target))
        check(f"a codex that exits {codex_exit_code} is passed through unchanged",
              result.returncode == codex_exit_code,
              f"exit {result.returncode}; stderr={result.stderr!r}")
        check(f"a codex that exits {codex_exit_code} is reported, not thrown",
              "Traceback" not in result.stderr, repr(result.stderr))
        check(f"a codex that exits {codex_exit_code} says so on stderr",
              f"codex exec failed (exit {codex_exit_code})" in result.stderr,
              repr(result.stderr))

    # --- The successful path, which must keep working ----------------------
    result = run_cell(stubs, STUB_CODEX_WRITES_REPORT,
                      "--cell", "restate", "--tier", "good", "--target", str(target))
    check("a cell whose codex succeeds exits 0",
          result.returncode == 0, f"exit {result.returncode}; stderr={result.stderr!r}")
    check("the report prints to stdout under its provenance stamp",
          result.stdout.startswith("<!-- provenance: runtime=codex")
          and "STUB CODEX CELL REPORT" in result.stdout, repr(result.stdout[:200]))

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
