#!/usr/bin/env python3
"""Tests for code-review-codex-cell.py.

Builds a scratch git repository with one commit and runs the cell against
it with a stub `codex` first on PATH, so no real review is ever launched:
the stub is the seam that lets the cell's own logic be tested without the
model, the money, or the half hour.

What is pinned here:

  - Bad invocations are reported, not thrown -- asserted on the exit code AND
    on the absence of a traceback, because an unhandled exception exits 1 just
    as a reported failure does. The cell already answers a `--repo` that is
    not a checkout, and a `--base`/`--commit` that does not resolve, with a
    message on stderr and its bad-invocation exit code. An `--output` naming
    something that is not a regular file is another of that kind: before 2026-08-23 a directory
    there reached `unlink()` and died on a traceback (PermissionError on
    macOS, IsADirectoryError on Linux). The guard is deliberately wider than
    "is a directory", so a FIFO case holds it there -- and the FIFO is the
    input where the old code did not traceback at all but silently succeeded,
    consuming the FIFO and writing a regular file over it.

  - This cell's own refusals and codex's failures carry DIFFERENT exit
    codes, and the cases below hold that seam from both sides: every bad
    invocation of the cell exits 64, while a codex that EXITS carries its
    own code through unchanged -- including 2, which is what codex returns
    when IT rejects a command line. A codex killed by a SIGNAL that this
    cell did not ask for is transformed rather than carried: Python reports
    the death as a negative returncode and sys.exit takes it modulo 256, so
    SIGKILL surfaces as 247 and SIGTERM as 241, measured by the cases below.
    Both stay clear of every code this cell spends on a meaning of its own,
    which is what the seam actually requires.

    Two other paths also do not carry codex's code, and both are the `1`
    row rather than this one: a codex that exits 0 having written no report
    (a case below pins it), and a codex still running at
    REVIEW_TIMEOUT_SECONDS, which subprocess kills with SIGKILL and which
    reaches the caller as 1 through the TimeoutExpired handler -- so "killed
    by SIGKILL" alone does not predict 247. No case here covers the timeout
    path. Until 2026-08-23 the cell used 2
    for its own refusals too, so two opposite meanings -- the caller invoked
    this cell wrongly, versus this cell invoked codex wrongly -- arrived as
    the same number, and only the second is a defect in this repository. The
    argparse cases are in the set deliberately: argparse's default is also 2,
    so moving only the hand-written checks would have left the commonest bad
    invocation there is, a mistyped flag, still colliding.

  - The pre-run delete of the output file still happens. It is there so
    that a stale report from an earlier run cannot survive a run in which
    codex writes nothing and then be stamped with this run's provenance
    header — the defect fixed on pull request #110. The stub that exits 0
    without writing reproduces exactly that setup, so the case fails loudly
    if anyone ever "simplifies" the delete away.

  - Codex's machine-wide memory store is off for the launch. A cell asked
    for a fresh judgement must not carry forward what Codex concluded
    reviewing this project before, and on 2026-08-23 it demonstrably was
    carrying it: the `## Memory` developer message was recovered from this
    cell's own review run on pull request #102. The full account is in the
    cell's docstring, under the heading
    WHY THE CODEX MEMORY STORE IS OFF FOR REVIEW CELLS
    Drop `--disable memories` from the command list and nothing else in this
    file notices, while every review from then on runs contaminated -- which
    is why the flag is pinned here and not left to the docstring.

Run: python3 scripts/code-review-codex-cell-test.py
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Before anything runs git: a run started with GIT_DIR set, or with another
# variable that redirects git, must still build this suite's scratch
# repositories where the suite says, not in the repository the variable names.
_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().with_name(
        "git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

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

# A stub codex that records the argv it was launched with, beside the report
# it writes, so a case can assert on the composed command without a model
# call. It dumps to <output>.argv.json rather than to a fixed path so the
# recording belongs to the run that made it.
STUB_CODEX_RECORDS_ARGV = """#!/usr/bin/env python3
import json, sys
argv = sys.argv
target = argv[argv.index("--output-last-message") + 1]
with open(target + ".argv.json", "w", encoding="utf-8") as handle:
    json.dump(argv, handle)
with open(target, "w", encoding="utf-8") as handle:
    handle.write("STUB CODEX REPORT: argv recorded\\n")
sys.exit(0)
"""

def stub_codex_writes_then_exits(code):
    """A stub codex that writes its report and THEN fails with `code`.

    Writing first is the point: it puts a report on disk for the failure
    path to delete, so a case can pin "a report exists if and only if the
    run succeeded" on the passthrough path too.
    """
    return (
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "argv = sys.argv\n"
        'target = argv[argv.index("--output-last-message") + 1]\n'
        'open(target, "w", encoding="utf-8").write("PARTIAL STUB REPORT\\n")\n'
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


def git(repo, *arguments):
    completed = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        capture_output=True, text=True, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(arguments)}: {completed.stderr.strip()}")
    return completed.stdout


def scratch_home_for(stub_directory):
    """The HOME every run of the cell gets: a scratch directory beside the
    stub directory."""
    home = stub_directory.parent / "scratch-home"
    home.mkdir(parents=True, exist_ok=True)
    return home


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
    # A scratch home, so the credential profile names paths in it and the
    # launch never scans or names the real home's credential files.
    environment["HOME"] = str(scratch_home_for(stub_directory))
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
    # message on stderr and exit 64, never a traceback.
    not_a_checkout = scratch / "not-a-checkout"
    not_a_checkout.mkdir()
    result = run_cell(stubs, STUB_CODEX_WRITES_REPORT,
                      "--commit", head_sha, "--repo", str(not_a_checkout),
                      "--output", str(scratch / "report-a.md"))
    check("--repo that is not a checkout exits 64",
          result.returncode == 64, f"exit {result.returncode}; stderr={result.stderr!r}")
    check("--repo that is not a checkout says so on stderr",
          "is not a checkout" in result.stderr, repr(result.stderr))

    result = run_cell(stubs, STUB_CODEX_WRITES_REPORT,
                      "--commit", "no-such-commit", "--repo", str(checkout),
                      "--output", str(scratch / "report-b.md"))
    check("--commit that does not resolve exits 64",
          result.returncode == 64, f"exit {result.returncode}; stderr={result.stderr!r}")
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
    check("--output naming an existing directory exits 64",
          result.returncode == 64, f"exit {result.returncode}; stderr={result.stderr!r}")
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
    check("--output naming an existing FIFO exits 64",
          result.returncode == 64, f"exit {result.returncode}; stderr={result.stderr!r}")
    check("--output naming an existing FIFO says so on stderr",
          "is not a regular file" in result.stderr, repr(result.stderr))
    check("--output naming an existing FIFO leaves it a FIFO",
          fifo_output.is_fifo(),
          "the guard narrowed to directories only; the FIFO was consumed")

    # --- The bad invocations argparse catches, not the cell's own code -----
    # These reach the same channel by a different route: argparse's default
    # is usage text and exit 2, which is exactly the code codex uses to
    # reject a command line, so the cell overrides it. A mistyped flag is
    # the commonest bad invocation there is; leaving it at 2 would have left
    # the collision in place for the case that happens most.
    result = run_cell(stubs, STUB_CODEX_WRITES_REPORT,
                      "--commit", head_sha, "--repo", str(checkout))
    check("a missing required option exits 64",
          result.returncode == 64, f"exit {result.returncode}; stderr={result.stderr!r}")
    check("a missing required option still prints argparse's usage text",
          "usage:" in result.stderr, repr(result.stderr))

    result = run_cell(stubs, STUB_CODEX_WRITES_REPORT,
                      "--commit", head_sha, "--repo", str(checkout),
                      "--output", str(scratch / "report-c.md"), "--no-such-flag")
    check("an unrecognized option exits 64",
          result.returncode == 64, f"exit {result.returncode}; stderr={result.stderr!r}")

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

    # --- Codex's own failures pass through, code intact --------------------
    # 2 is the case the cell's own refusals were moved off on 2026-08-23:
    # codex exits 2 when IT rejects a command line, so a 2 out of this cell
    # must mean "codex refused the command this cell composed" -- a defect in
    # this repository -- and nothing else. If a future edit routes the cell's
    # own refusals back onto 2, or normalizes codex's codes to a fixed
    # failure value, one of these two cases fails.
    for codex_exit_code in (2, 7):
        passthrough_report = scratch / f"passthrough-{codex_exit_code}.md"
        result = run_cell(stubs, stub_codex_writes_then_exits(codex_exit_code),
                          "--commit", head_sha, "--repo", str(checkout),
                          "--output", str(passthrough_report))
        check(f"a codex that exits {codex_exit_code} is passed through unchanged",
              result.returncode == codex_exit_code,
              f"exit {result.returncode}; stderr={result.stderr!r}")
        check(f"a codex that exits {codex_exit_code} is reported, not thrown",
              "Traceback" not in result.stderr, repr(result.stderr))
        check(f"no report survives a codex that exits {codex_exit_code}",
              not passthrough_report.exists(),
              "a partial report outlived a failed run and can be read as a review")

    # --- A codex killed by a signal, which is NOT passed through unchanged --
    # Python reports a signal death as a negative returncode, and this cell
    # hands that to sys.exit, which takes it modulo 256. So the number a
    # caller sees for SIGKILL is 247, not the 137 a shell would report for the
    # same death. The cell's docstring said "passed through unchanged" without
    # qualification until 2026-08-28, which read as a promise that the number
    # a caller sees is the number a shell would show.
    #
    # Nothing depends on the distinction today, and these cases exist to keep
    # it that way: what MUST hold is that these codes stay clear of the ones
    # this cell spends on its own meanings (64 refused, 1 no report, 2 codex
    # rejected the composed command). If a future edit normalises signal
    # deaths onto one of those, the second check here fails.
    for signal_number, expected_exit in ((9, 247), (15, 241)):
        signal_report = scratch / f"signal-{signal_number}.md"
        result = run_cell(stubs, f"#!/bin/sh\nkill -{signal_number} $$\n",
                          "--commit", head_sha, "--repo", str(checkout),
                          "--output", str(signal_report))
        check(f"a codex killed by signal {signal_number} exits {expected_exit}, "
              "not the shell's 128+N",
              result.returncode == expected_exit,
              f"exit {result.returncode}; stderr={result.stderr!r}")
        check(f"signal {signal_number}'s code cannot be mistaken for one this "
              "cell spends itself",
              result.returncode not in (0, 1, 2, 64),
              f"exit {result.returncode} collides with a code this cell means something by")
        check(f"no report survives a codex killed by signal {signal_number}",
              not signal_report.exists(),
              "a partial report outlived a killed run and can be read as a review")

    # --- The memory store is off for the launch ----------------------------
    # Why this matters and what it does not cover: the cell's own docstring,
    # under WHY THE CODEX MEMORY STORE IS OFF FOR REVIEW CELLS. What is
    # pinned here is only that the argument reaches codex, which is the part
    # that can be lost by an edit to the command list. Whether codex then
    # honours it is not measured by anyone, here or in the cell.
    #
    # The flag and its value are checked as an ADJACENT pair: `--disable`
    # takes a value, so finding both words somewhere in argv would also pass
    # for a command that disabled something else entirely.
    argv_report = scratch / "argv-report.md"
    # Two credential directories, `gh`'s login directory one of them, and a
    # reviewer program's login file in the scratch home, for the credential
    # profile checked below.
    scratch_home = scratch_home_for(stubs)
    (scratch_home / ".config" / "nedschorus").mkdir(parents=True, exist_ok=True)
    (scratch_home / ".config" / "gh").mkdir(parents=True, exist_ok=True)
    login_canary = scratch_home / ".codex" / "auth.json"
    login_canary.parent.mkdir(parents=True, exist_ok=True)
    login_canary.write_text("CANARY-NOT-A-SECRET-code-review-codex-cell-test\n", encoding="utf-8")
    result = run_cell(stubs, STUB_CODEX_RECORDS_ARGV,
                      "--commit", head_sha, "--repo", str(checkout),
                      "--output", str(argv_report))
    check("the argv-recording run succeeded",
          result.returncode == 0, f"exit {result.returncode}; stderr={result.stderr!r}")
    argv_recording = Path(f"{argv_report}.argv.json")
    launched_command = (
        json.loads(argv_recording.read_text(encoding="utf-8"))
        if argv_recording.is_file() else []
    )
    check("codex is launched with the memory store disabled",
          ("--disable", "memories") in list(zip(launched_command, launched_command[1:])),
          f"composed command was {launched_command}")

    # --- No credential file is readable (user-ruled 2026-09-29) -----------
    # A permission profile extending :read-only, which Codex will not combine
    # with --sandbox, placed AFTER `review`. `codex exec review` runs the
    # review's commands in a child thread, and on codex-cli 0.156.0 that
    # thread drops a profile placed before `review`: its commands ran with
    # the checkout and /tmp writable and no deny entry (GHI 804, "The Codex
    # review cell's commands run writable and without credential denials,
    # because `codex exec review` drops the cell's permission profile"). The
    # cell's docstring has the measurement, under WHERE THE PERMISSION
    # PROFILE GOES. The first profile check fails if the profile moves back
    # before `review`; the second fails if a copy is left there, where it
    # reads as protection and gives none.
    def config_overrides(arguments):
        return [value for flag, value in zip(arguments, arguments[1:]) if flag == "-c"]
    review_index = (launched_command.index("review") if "review" in launched_command
                    else len(launched_command))
    overrides_before_review = config_overrides(launched_command[:review_index])
    overrides_after_review = config_overrides(launched_command[review_index + 1:])
    denied_table = next((override.split("=", 1)[1] for override in overrides_after_review
                         if override.startswith("permissions.code-review-no-credentials.filesystem=")),
                        "")
    check("codex runs under no --sandbox, which Codex will not combine with a profile",
          "--sandbox" not in launched_command, f"composed command was {launched_command}")
    check("codex runs under the credential-denying profile, extending :read-only, after `review`",
          'default_permissions="code-review-no-credentials"' in overrides_after_review
          and 'permissions.code-review-no-credentials.extends=":read-only"' in overrides_after_review,
          repr(overrides_after_review))
    check("no permission override sits before `review`, where the review's commands drop it",
          not [override for override in overrides_before_review
               if override.startswith(("default_permissions=", "permissions."))],
          repr(overrides_before_review))
    check("the profile denies the credential directories and a reviewer program's login file",
          f'"{scratch_home}/.config/nedschorus"="deny"' in denied_table
          and f'"{scratch_home}/.config/gh"="deny"' in denied_table
          and f'"{login_canary}"="deny"' in denied_table, denied_table)

    # --- The pull request's description -----------------------------------
    # The description reaches Codex's review as `-c developer_instructions=`
    # placed AFTER `review`, the one placement measured to reach the
    # review's child thread on codex-cli 0.160.0 (the cell's docstring, under
    # THE PULL REQUEST'S DESCRIPTION). Without the option, the command must
    # carry no such override, so callers that pass nothing review exactly as
    # before.
    def developer_instruction_overrides(arguments):
        return [value for value in config_overrides(arguments)
                if value.startswith("developer_instructions=")]
    check("without --pull-request-description-file, no developer_instructions reach codex",
          not developer_instruction_overrides(launched_command), repr(launched_command))

    awkward_description = ('Please review the commands in "NOTES.md".\n'
                           "A backslash \\ and a tab\t and a non-ASCII word: café.\n")
    description_file = scratch / "description.md"
    description_file.write_text(awkward_description, encoding="utf-8")
    described_report = scratch / "described-report.md"
    result = run_cell(stubs, STUB_CODEX_RECORDS_ARGV,
                      "--commit", head_sha, "--repo", str(checkout),
                      "--output", str(described_report),
                      "--pull-request-description-file", str(description_file))
    check("a run given a description succeeds",
          result.returncode == 0, f"exit {result.returncode}; stderr={result.stderr!r}")
    described_command = json.loads(
        Path(f"{described_report}.argv.json").read_text(encoding="utf-8"))
    described_review_index = described_command.index("review")
    after_review = developer_instruction_overrides(described_command[described_review_index + 1:])
    before_review = developer_instruction_overrides(described_command[:described_review_index])
    check("the description reaches codex as one developer_instructions override after `review`",
          len(after_review) == 1 and not before_review, repr(described_command))
    try:
        import tomllib
    except ImportError:  # Apple's Python 3.9 has no tomllib
        tomllib = None
    if tomllib is None:
        print("SKIP  the override parses as TOML back to the description: no tomllib before Python 3.11")
    elif after_review:
        parsed = tomllib.loads(after_review[0])["developer_instructions"]
        check("the override parses as TOML back to the framing and the description",
              parsed.endswith(awkward_description.strip())
              and parsed.startswith("The text below is this pull request's description"),
              repr(parsed))
    described_text = described_report.read_text(encoding="utf-8")
    check("the provenance header says a description was given",
          "pull-request-description=given" in described_text.splitlines()[0],
          repr(described_text[:200]))

    blank_description = scratch / "blank-description.md"
    blank_description.write_text("  \n\n", encoding="utf-8")
    blank_report = scratch / "blank-report.md"
    result = run_cell(stubs, STUB_CODEX_RECORDS_ARGV,
                      "--commit", head_sha, "--repo", str(checkout),
                      "--output", str(blank_report),
                      "--pull-request-description-file", str(blank_description))
    blank_command = json.loads(Path(f"{blank_report}.argv.json").read_text(encoding="utf-8"))
    check("a blank description passes no developer_instructions",
          result.returncode == 0 and not developer_instruction_overrides(blank_command),
          f"exit {result.returncode}; command {blank_command}")

    result = run_cell(stubs, STUB_CODEX_RECORDS_ARGV,
                      "--commit", head_sha, "--repo", str(checkout),
                      "--output", str(scratch / "missing-description-report.md"),
                      "--pull-request-description-file", str(scratch / "no-such-description.md"))
    check("an unreadable description file exits 64, reported and not thrown",
          result.returncode == 64 and "cannot read --pull-request-description-file" in result.stderr
          and "Traceback" not in result.stderr,
          f"exit {result.returncode}; stderr={result.stderr!r}")

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
