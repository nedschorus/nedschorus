#!/usr/bin/env python3
"""Tests for md-review-codex-cell.py — its exit codes, and only those.

WHY THIS SEAM. Until 2026-08-23 the cell used 2 for its own refusals and
passed `codex exec`'s exit code through when codex failed, and codex exits 2
as well (measured on codex-cli 0.147.0 that day: a command line codex rejects
exits 2, every non-parsing failure exits 1). One number meant both "the caller
invoked this cell wrongly" and "this cell invoked codex wrongly", and only the
second is a defect in this repository. The cell's own refusals moved to 64 —
sysexits.h's EX_USAGE, chosen because it sits outside every band codex
plausibly returns.

WHAT CHANGED SINCE THAT FIX, and why half of this file was rewritten. The
cell no longer passes codex's exit code through, so the passthrough cases
that pinned it have nothing left to pin. The reviewer now writes its findings
to --report rather than answering in chat, and the cell hands its models to
the chain runner in scripts/md-review-cell-common.py: a model that fails is a
model the chain falls back from, and the caller is told whether ANY model
produced a review — 1 when none did, however each of them failed. The old
cases are replaced by what the chain actually does when codex exits 2 or 7,
which is the same thing in both cases and is the point: the code no longer
selects the cell's own. It is not lost, either. The two replacement cases
check that codex's code and codex's own words still reach stderr, which is
where a defect in the command this cell composes is diagnosed, and which the
grid keeps whenever a cell fails.

So what is pinned here is the seam from both sides: a caller's bad invocation
comes back as 64 and never launches codex; a codex that fails comes back as
1, with its own code visible on stderr and no report left behind; and a codex
that succeeds comes back as 0 with the report written to --report and nothing
at all on stdout.

The argparse cases are in the set deliberately, not for completeness:
argparse's own default is also 2, so moving only the hand-written checks
would have left the collision standing for the commonest bad invocation there
is, a mistyped flag.

Everything else about this cell — the model and effort pins, the memory store
being off for the launch, the stray-write detector, the provenance stamp's
fields — is NOT covered here; this file was written for the exit-code seam
and does not stand in for a full suite. The shared module's own behaviour is
covered in scripts/md-review-cell-common-test.py.

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

# A stub codex that writes the report the cell is waiting for, then exits 0 —
# the successful-cell path. The path arrives by environment: the cell puts it
# in the prompt, and a stub that parsed the prompt for it would fail for a
# reason having nothing to do with exit codes the next time a template is
# reworded.
STUB_CODEX_WRITES_REPORT = """#!/usr/bin/env python3
import os, sys
with open(os.environ["MD_REVIEW_CODEX_CELL_TEST_STUB_REPORT_PATH"], "w",
          encoding="utf-8") as handle:
    handle.write("STUB CODEX CELL REPORT\\n")
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


def run_cell(stub_directory, stub_body, report_path, *arguments):
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
    environment["MD_REVIEW_CODEX_CELL_TEST_STUB_REPORT_PATH"] = str(report_path)
    return subprocess.run(
        [sys.executable, str(CELL_SCRIPT), "--report", str(report_path), *arguments],
        capture_output=True, text=True, check=False, env=environment,
    )


with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch)
    stubs = scratch / "stub-bin"
    target = scratch / "a-document.md"
    target.write_text("# a document for the cell to be pointed at\n", encoding="utf-8")
    report = scratch / "a-report.md"

    # --- The cell's own refusals ------------------------------------------
    result = run_cell(stubs, STUB_CODEX_WRITES_REPORT, report,
                      "--cell", "restate", "--tier", "good",
                      "--target", str(scratch / "no-such-document.md"))
    check("a --target that is not a file exits 64",
          result.returncode == 64, f"exit {result.returncode}; stderr={result.stderr!r}")
    check("a --target that is not a file says so on stderr",
          "target not found" in result.stderr, repr(result.stderr))
    check("a --target that is not a file does not raise",
          "Traceback" not in result.stderr, repr(result.stderr))

    # The refusal the report file brought with it, which leaves by the same
    # door: a --report naming something that is not a file at all.
    existing_directory = scratch / "a-directory-as-report"
    existing_directory.mkdir()
    result = run_cell(stubs, STUB_CODEX_WRITES_REPORT, existing_directory,
                      "--cell", "restate", "--tier", "good", "--target", str(target))
    check("a --report naming an existing directory exits 64",
          result.returncode == 64, f"exit {result.returncode}; stderr={result.stderr!r}")
    check("a --report naming an existing directory says so on stderr",
          "report path is not a file" in result.stderr, repr(result.stderr))

    # argparse's route into the same channel.
    result = run_cell(stubs, STUB_CODEX_WRITES_REPORT, report,
                      "--cell", "restate", "--target", str(target))
    check("a missing required option exits 64",
          result.returncode == 64, f"exit {result.returncode}; stderr={result.stderr!r}")
    check("a missing required option still prints argparse's usage text",
          "usage:" in result.stderr, repr(result.stderr))

    result = run_cell(stubs, STUB_CODEX_WRITES_REPORT, report,
                      "--cell", "restate", "--tier", "good",
                      "--target", str(target), "--no-such-flag")
    check("an unrecognized option exits 64",
          result.returncode == 64, f"exit {result.returncode}; stderr={result.stderr!r}")

    # --- A codex that fails is a chain that produced no report -------------
    # These two codes are the ones the passthrough used to carry out, and 2 is
    # the code the cell's own refusals were moved off. Both now come back as
    # 1, which is what "no model in this tier's chain produced a review" is
    # spelled as — and both must still show codex's own code on stderr, or the
    # move would have thrown away the diagnosis along with the collision.
    for codex_exit_code in (2, 7):
        report.unlink(missing_ok=True)
        result = run_cell(stubs, stub_codex_exits(codex_exit_code), report,
                          "--cell", "restate", "--tier", "good", "--target", str(target))
        check(f"a codex that exits {codex_exit_code} leaves the cell exiting 1",
              result.returncode == 1, f"exit {result.returncode}; stderr={result.stderr!r}")
        check(f"a codex that exits {codex_exit_code} is reported, not thrown",
              "Traceback" not in result.stderr, repr(result.stderr))
        check(f"codex's own exit code {codex_exit_code} still reaches stderr",
              f"(exit {codex_exit_code})" in result.stderr, repr(result.stderr))
        check(f"a codex that exits {codex_exit_code} leaves no report behind",
              not report.exists(),
              "a report survived a run that produced no review")

    # --- The successful path, which must keep working ----------------------
    report.unlink(missing_ok=True)
    result = run_cell(stubs, STUB_CODEX_WRITES_REPORT, report,
                      "--cell", "restate", "--tier", "good", "--target", str(target))
    check("a cell whose codex succeeds exits 0",
          result.returncode == 0, f"exit {result.returncode}; stderr={result.stderr!r}")
    report_text = report.read_text(encoding="utf-8") if report.is_file() else ""
    check("the report is written to --report under its provenance stamp",
          report_text.startswith("<!-- provenance: runtime=codex")
          and "STUB CODEX CELL REPORT" in report_text, repr(report_text[:200]))
    check("the successful cell prints nothing to stdout",
          result.stdout == "", repr(result.stdout[:200]))

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
