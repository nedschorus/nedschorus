#!/usr/bin/env python3
"""Tests for sanity-check-attacks.py — the worktree write detector, the record
directory claim, the cells' sanctioned scratch directories, the prompt-body
boundary, the cells' launch flags, the refusal of a captured text that is
not a report, the relaunch of a cell that saved no report with the
instructions a failed cell ends on (cases 38 to 43), and how a run ends when
it is stopped from outside, what the next run removes after a killed one, the
bytes an agent-binary may write, and the record of a run that saved no report
(cases 44 to 48), a stop that lands as a launch is prepared, after the
cells have ended, or while a review copy is claimed (cases 49 to 53), and an
agent-binary started as the stop begins, a stop that lands while a report is
saved, a review copy whose removal fails, and a cell that first runs after
the stop (cases 54 to 57), and a stop that lands while a cell's git call,
version probe or agent-binary runs as the cell saves its report (cases 58 to
60). No case
starts a real agent-binary: see CONTAINMENT below.

The detector's only value is being trustworthy about whether a review cell
wrote to the worktree. A hole in it is silent by construction, and a warning
it raises about a write no cell made is the same defect wearing the opposite
sign: it teaches its reader to skip the warning that means something. Each
case below builds a scratch repository, snapshots it, simulates a cell write —
or a legitimate one that must stay quiet — and asserts what is named. The
holes under test were found reviewing PRs #98, #102 and #147, and nedschorus#161:

  - a file already dirty before the run, rewritten by a cell (label
    comparison misses it; content hashes catch it)
  - a wholly-untracked directory, which porcelain collapses to one entry, so
    anything a cell writes under it is invisible without -uall
  - a non-ASCII pathname, which git C-quotes without -z, producing a path
    that matches nothing on disk and fingerprints as "absent" on both sides
  - a write to an ignored path, which `git status` never reports in any form:
    the runner's own report directory is ignored, so a cell overwriting a
    finished report was silent (PR #98, fixed 2026-08-23 by watching that
    directory directly — see IGNORED_PATHS_WATCHED_FOR_WRITES, whose
    deliberate limit case 11 records)
  - a write the runner's own report write erased before anything compared it:
    the artifact ended up correct and the cell's write was reported nowhere
  - two runs overlapping in one worktree, each naming the other's reports as
    its own cells' stray writes, and a ledger entry that assumed the record
    directory was still ignored, which named the runner's own report wherever
    that ignore rule was absent
  - the check itself gated to codex, so a claude cell's write went unseen: on
    2026-08-21 a claude cell wrote a 25,170-byte file to the worktree root and
    nothing caught it, because run_cell only ran the comparison for codex
    (nedschorus#161)

The cells' scratch directories (cases 19-22) are the other side of the same
subject. A cell needs working space for notes and drafts, and the prompts used
to answer that with "write no files" — which the cells did not reliably keep
and the detector then reported. Each cell now gets a directory of its own under
the run's record directory, named to it in its prompt, and the detector exempts
that subtree (user-ruled 2026-08-29): the cases below pin that the runner makes
the directory, that the path reaches the cell in place of the prompt MD's
placeholder token, that a write inside the subtree is silent while the rest of
the record directory stays watched, and that a claude cell launches with the
Write tool the instruction needs.

Run: python3 scripts/sanity-check-attacks-test.py
"""

import contextlib
import importlib.util
import inspect
import io
import os
import pathlib
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

# Before anything runs git: a run started with GIT_DIR set, or with another
# variable that redirects git, must still build this suite's scratch
# repositories where the suite says, not in the repository the variable names.
_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    pathlib.Path(__file__).resolve().with_name(
        "git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

RUNNER_SCRIPT = pathlib.Path(__file__).with_name("sanity-check-attacks.py")
SANITY_CHECK_RECORD_SHIPPER_SCRIPT = pathlib.Path(__file__).with_name(
    "sanity-check-record-ship.py")

# CONTAINMENT: no run of this suite reaches ned-box. Case 24 drives the
# runner's main() to completion with cells that wrote reports, so the run ends
# in print_run_completion -> ship_record -> the real
# scripts/sanity-check-record-ship.py, which with no destination override
# resolves to the production log-store. On 2026-09-17 a run of this suite
# copied its own fixture reports -- `model=a-test-model ... cli=1.1.1-test ...
# commit=test` -- into
# nedlern@ned-box:/home/nedlern/nedschorus-logs/sanity-check-records/, where
# they read as a real sanity check of a real document; found in review of
# nedschorus#453, the change that gave the runner its shipper. Every run now
# ships into a temporary directory of its own instead, the way
# nc-systems/cold-read/tests/cold-read-grid-test.py contains its own runs: the store is real and
# the copy is the real rsync, only the destination is scratch. The override
# names the cold-read kind because the shipper picks its own kind beside it,
# so records land in <scratch>/sanity-check-records/. It is set here, at
# import, so that it also covers a case that runs the runner as a subprocess,
# and the checks at the head of main() pin it before the first case runs.
RECORD_SHIP_DESTINATION_VARIABLE = "COLD_READ_RECORD_SHIP_DESTINATION"
SUITE_SCRATCH_LOG_STORE = tempfile.TemporaryDirectory(
    prefix="sanity-check-attacks-test-log-store-")
SUITE_SCRATCH_LOG_STORE_PATH = pathlib.Path(SUITE_SCRATCH_LOG_STORE.name)
os.environ[RECORD_SHIP_DESTINATION_VARIABLE] = str(
    SUITE_SCRATCH_LOG_STORE_PATH / "cold-read-records")

# CONTAINMENT, second half: no case starts a real agent-binary. The cases
# replace the runner's run_agent_binary_unless_run_stopped with stand-ins, and
# a runner whose launchers do not call that function (an older runner, or a
# deliberate break a reviewer runs this suite against) starts whatever
# `claude` or `codex` is on PATH, which costs a model call and lets an agent
# read the machine. So the suite runs with a `claude` and a `codex` first on
# PATH that write their arguments to a log and exit 1. main() checks before
# the first case that both names resolve to them, and after the last that
# none was asked for more than its version. A case that runs the runner as a
# process puts its own stand-ins first on that process's PATH.
AGENT_BINARY_TRIPWIRES = tempfile.TemporaryDirectory(
    prefix="sanity-check-attacks-test-agent-binary-tripwires-")
AGENT_BINARY_TRIPWIRE_DIRECTORY = pathlib.Path(AGENT_BINARY_TRIPWIRES.name).resolve()
AGENT_BINARY_TRIPWIRE_LOG = AGENT_BINARY_TRIPWIRE_DIRECTORY / "calls.log"
for _tripwire_name in ("claude", "codex"):
    _tripwire = AGENT_BINARY_TRIPWIRE_DIRECTORY / _tripwire_name
    _tripwire.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' \"{_tripwire_name} $*\" >> {shlex.quote(str(AGENT_BINARY_TRIPWIRE_LOG))}\n"
        "exit 1\n", encoding="utf-8")
    _tripwire.chmod(0o755)
os.environ["PATH"] = os.pathsep.join(
    [str(AGENT_BINARY_TRIPWIRE_DIRECTORY), os.environ.get("PATH", "")])

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def load_runner():
    spec = importlib.util.spec_from_file_location("sanity_check_attacks", RUNNER_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def agent_binary_launch_a_case_replaces(runner):
    """The runner's run_agent_binary_unless_run_stopped, which a case is about
    to replace with a stand-in and put back afterwards. Raises when the runner
    has none: a stand-in set on a name the launchers never call is never
    used, and the case would start the agent-binary on PATH instead."""
    launch = getattr(runner, "run_agent_binary_unless_run_stopped", None)
    if launch is None:
        raise AssertionError(
            "the runner under test has no run_agent_binary_unless_run_stopped, "
            "so the stand-ins these cases set on it would never be called; no "
            "further case runs")
    return launch


def git(repo, *arguments):
    completed = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        capture_output=True, text=True, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(arguments)}: {completed.stderr.strip()}")
    return completed.stdout


def new_repo(root):
    git(root, "init", "-q")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "test")
    (root / "tracked.md").write_text("original\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "initial")
    return root


def main():
    # Containment, checked before any case runs. The guard is the destination
    # override set at the top of this file; these two checks are what keeps it
    # from being quietly removed, and the early return is what keeps a suite
    # that lost it from shipping fixture reports to the log-store a second
    # time -- a failing check alone would still let case 24 drive the runner
    # to completion and ship.
    destination_override = os.environ.get(RECORD_SHIP_DESTINATION_VARIABLE, "")
    check("the record-ship destination override points into this suite's own scratch store",
          bool(destination_override)
          and pathlib.Path(destination_override).is_relative_to(SUITE_SCRATCH_LOG_STORE_PATH),
          f"{RECORD_SHIP_DESTINATION_VARIABLE}={destination_override!r}, "
          f"scratch store is {SUITE_SCRATCH_LOG_STORE_PATH}")
    shipper_spec = importlib.util.spec_from_file_location(
        "sanity_check_record_ship", SANITY_CHECK_RECORD_SHIPPER_SCRIPT)
    record_shipper = importlib.util.module_from_spec(shipper_spec)
    shipper_spec.loader.exec_module(record_shipper)
    shipper_host, shipper_path = record_shipper.destination_for_this_machine()
    check("and the shipper a run would call resolves there, to no host at all",
          shipper_host is None
          and pathlib.Path(shipper_path).is_relative_to(SUITE_SCRATCH_LOG_STORE_PATH),
          f"the shipper would ship to {shipper_host}:{shipper_path}")
    for name in ("claude", "codex"):
        resolved = shutil.which(name)
        check(f"`{name}` resolves to this suite's tripwire, which starts no agent",
              resolved is not None
              and pathlib.Path(resolved).resolve().parent == AGENT_BINARY_TRIPWIRE_DIRECTORY,
              f"`{name}` resolves to {resolved}")
    if failures:
        print("containment failed: no case runs, because a case that drove the "
              "runner to completion would ship this suite's fixture reports to "
              "the log-store on ned-box, or start a real agent-binary.")
        return 1

    runner = load_runner()
    snapshot = runner.worktree_snapshot
    strays = getattr(runner, "stray_paths", None)
    if strays is None:
        def strays(baseline, now):
            return sorted(path for path in set(now) | set(baseline)
                          if now.get(path) != baseline.get(path))

    # Case 1: a file already dirty before the run, rewritten by a cell.
    with tempfile.TemporaryDirectory() as scratch:
        repo = new_repo(pathlib.Path(scratch))
        (repo / "tracked.md").write_text("dirty before the run\n", encoding="utf-8")
        baseline = snapshot(repo)
        (repo / "tracked.md").write_text("a cell wrote this\n", encoding="utf-8")
        found = strays(baseline, snapshot(repo))
        check("already-dirty file rewritten by a cell is detected",
              "tracked.md" in found, f"stray list was {found}")

    # Case 2: a file written under a directory that was already untracked.
    with tempfile.TemporaryDirectory() as scratch:
        repo = new_repo(pathlib.Path(scratch))
        (repo / "untracked-dir").mkdir()
        (repo / "untracked-dir" / "already-here.md").write_text("x\n", encoding="utf-8")
        baseline = snapshot(repo)
        (repo / "untracked-dir" / "cell-wrote-this.md").write_text("y\n", encoding="utf-8")
        found = strays(baseline, snapshot(repo))
        check("file written under an already-untracked directory is detected",
              "untracked-dir/cell-wrote-this.md" in found, f"stray list was {found}")

    # Case 3: a non-ASCII pathname, which git C-quotes unless -z is used.
    with tempfile.TemporaryDirectory() as scratch:
        repo = new_repo(pathlib.Path(scratch))
        unicode_name = "dirty-ünicode.md"
        (repo / unicode_name).write_text("original\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "add unicode file")
        (repo / unicode_name).write_text("dirty before the run\n", encoding="utf-8")
        baseline = snapshot(repo)
        (repo / unicode_name).write_text("a cell wrote this\n", encoding="utf-8")
        found = strays(baseline, snapshot(repo))
        check("rewrite of a non-ASCII pathname is detected",
              unicode_name in found,
              f"stray list was {found}; baseline was {baseline}")

    # Case 4: a cell stages an already-dirty file. Staging changes the index
    # status without changing the file's bytes, so a content fingerprint alone
    # sees nothing — `git add` is exactly the write the detector exists to
    # catch, and the label comparison this replaced did catch it.
    with tempfile.TemporaryDirectory() as scratch:
        repo = new_repo(pathlib.Path(scratch))
        (repo / "tracked.md").write_text("dirty before the run\n", encoding="utf-8")
        baseline = snapshot(repo)
        git(repo, "add", "tracked.md")
        found = strays(baseline, snapshot(repo))
        check("an already-dirty file staged by a cell is detected",
              "tracked.md" in found, f"stray list was {found}; baseline was {baseline}")

    # Case 5: a quiet run reports nothing.
    with tempfile.TemporaryDirectory() as scratch:
        repo = new_repo(pathlib.Path(scratch))
        (repo / "untracked-dir").mkdir()
        (repo / "untracked-dir" / "already-here.md").write_text("x\n", encoding="utf-8")
        baseline = snapshot(repo)
        found = strays(baseline, snapshot(repo))
        check("a run that writes nothing produces no stray", found == [],
              f"stray list was {found}")

    # Case 6: a staged rename must not desynchronize the field walk. Under -z
    # the origin path is its own field, so a parser expecting " -> " consumes
    # one field too few and mistakes the origin path for the next entry.
    with tempfile.TemporaryDirectory() as scratch:
        repo = new_repo(pathlib.Path(scratch))
        (repo / "zz-last.md").write_text("tail\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "add tail file")
        git(repo, "mv", "tracked.md", "renamed.md")
        baseline = snapshot(repo)
        (repo / "zz-last.md").write_text("a cell wrote this\n", encoding="utf-8")
        found = strays(baseline, snapshot(repo))
        check("a write after a staged rename is still detected",
              "zz-last.md" in found, f"stray list was {found}; baseline was {baseline}")

    # Case 7: a cell writing to an ignored path. `git status` never reports an
    # ignored path in any form, so a write there was invisible to the detector
    # no matter how the porcelain was parsed. The record directory is the
    # ignored path that matters: it is where the runner puts every cell's
    # report, the reports exist to be compared against each other, and a cell
    # overwriting a finished one left the comparison running on corrupted
    # input with the run still reported clean (raised as an inline P2 on PR
    # #98, unfixed until 2026-08-23).
    records_name = runner.RECORDS_ROOT.name
    with tempfile.TemporaryDirectory() as scratch:
        repo = new_repo(pathlib.Path(scratch))
        (repo / ".gitignore").write_text(f"{records_name}/\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "ignore the record directory")
        report = repo / records_name / "2026-08-23-design" / "cut-claude.md"
        report.parent.mkdir(parents=True)
        report.write_text("a finished report\n", encoding="utf-8")
        # Precondition: git really is blind here. Without it the case below
        # could pass for the wrong reason — an un-ignored directory is listed
        # by -uall and detected with no ignored-path watch at all.
        ignored = subprocess.run(
            ["git", "-C", str(repo), "check-ignore", "-q", str(report)],
            check=False).returncode == 0
        check("precondition: git treats the record directory as ignored", ignored,
              "git check-ignore did not match the report path")
        baseline = snapshot(repo)
        report.write_text("a cell wrote over this report\n", encoding="utf-8")
        found = strays(baseline, snapshot(repo))
        check("a cell overwriting a report in the ignored record directory is detected",
              f"{records_name}/2026-08-23-design/cut-claude.md" in found,
              f"stray list was {found}; baseline was {baseline}")

    # Case 8: the runner writes every cell's report INTO the watched record
    # directory, so its own writes have to be told apart from a cell's, or the
    # first report written would be named as a stray by every cell that
    # finished after it. The ledger records what the runner wrote and what it
    # contained: a bare path exemption would excuse exactly the write case 7
    # exists to catch.
    ledger_class = getattr(runner, "RunnerReportWriteLedger", None)
    missing_ledger = "RunnerReportWriteLedger is not present on the runner under test"
    with tempfile.TemporaryDirectory() as scratch:
        repo = new_repo(pathlib.Path(scratch))
        (repo / ".gitignore").write_text(f"{records_name}/\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "ignore the record directory")
        out_dir = repo / records_name / "2026-08-23-design"
        out_dir.mkdir(parents=True)
        baseline = snapshot(repo)
        if ledger_class is None:
            check("a report the runner wrote itself is not reported as a stray",
                  False, missing_ledger)
            check("a cell overwriting another cell's finished report is detected",
                  False, missing_ledger)
        else:
            ledger = ledger_class()
            report = out_dir / "cut-claude.md"
            ledger.write_report(report, "the report this cell produced\n", repo)
            found = ledger.stray_paths_since(baseline, repo)
            check("a report the runner wrote itself is not reported as a stray",
                  found == [], f"stray list was {found}")
            report.write_text("a cell wrote over this finished report\n", encoding="utf-8")
            found = ledger.stray_paths_since(baseline, repo)
            check("a cell overwriting another cell's finished report is detected",
                  f"{records_name}/2026-08-23-design/cut-claude.md" in found,
                  f"stray list was {found}")

    # Case 9: the ledger under the concurrency main() actually creates. The
    # cells run in a ThreadPoolExecutor, so one cell's report write and
    # another cell's stray snapshot interleave, and a snapshot that catches a
    # report mid-write — or before its fingerprint is recorded — names a stray
    # where nothing strayed. A warning on an ordinary run is worse than no
    # warning: it teaches its reader to skip the one that means something.
    # Measured 2026-08-23 with the ledger's lock replaced by a no-op: 45 of 60
    # rounds reported a spurious stray; with the lock, none of 60.
    if ledger_class is None:
        check("concurrent report writes produce no spurious stray", False, missing_ledger)
    else:
        with tempfile.TemporaryDirectory() as scratch:
            repo = new_repo(pathlib.Path(scratch))
            (repo / ".gitignore").write_text(f"{records_name}/\n", encoding="utf-8")
            git(repo, "add", "-A")
            git(repo, "commit", "-qm", "ignore the record directory")
            out_dir = repo / records_name / "2026-08-23-design"
            out_dir.mkdir(parents=True)
            ledger = ledger_class()
            baseline = snapshot(repo)
            spurious = []

            def write_reports_and_check(cell_name):
                for round_number in range(15):
                    ledger.write_report(
                        out_dir / f"{cell_name}.md",
                        f"{cell_name} report body, round {round_number}\n" * 50, repo)
                    found = ledger.stray_paths_since(baseline, repo)
                    if found:
                        spurious.append((cell_name, round_number, found))

            workers = [threading.Thread(target=write_reports_and_check,
                                        args=(f"cell-{index}",)) for index in range(4)]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join()
            check("concurrent report writes produce no spurious stray", spurious == [],
                  f"{len(spurious)} spurious report(s); first was {spurious[:1]}")

    # Case 10: the watched ignored paths belong to the write detector, not to
    # the provenance line. They are not part of any commit, so a record
    # directory left over from an earlier run must not turn `worktree=clean`
    # into `dirty(N)` in every report's provenance header — which is what a
    # snapshot entry counted naively would do.
    ignored_status = getattr(runner, "IGNORED_PATH_STATUS_CODE", "!!")
    revision = runner.reviewed_revision(
        {f"{records_name}/2026-08-01-earlier-run/cut-codex.md": (ignored_status, "0" * 40)})
    check("a leftover record file does not make the reviewed revision dirty",
          "worktree=clean" in revision, f"provenance line said {revision!r}")

    # Case 11: the boundary of case 7, asserted rather than assumed. The
    # detector watches the paths named in IGNORED_PATHS_WATCHED_FOR_WRITES,
    # not every ignored path — enumerating and fingerprinting every ignored
    # file in the repository to catch a rare write was ruled out (user,
    # 2026-08-23). A write to any other ignored path (ghi-mirror/,
    # cold-read-records/, __pycache__/) is still invisible, and this case
    # states that limit in code. It passes both before and after case 7's
    # fix: it is documentation of the carve-out, never evidence for the fix,
    # and it fails if the watch ever silently becomes repository-wide.
    with tempfile.TemporaryDirectory() as scratch:
        repo = new_repo(pathlib.Path(scratch))
        (repo / ".gitignore").write_text("unwatched-ignored-dir/\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "ignore an unwatched directory")
        unwatched = repo / "unwatched-ignored-dir" / "notes.md"
        unwatched.parent.mkdir(parents=True)
        unwatched.write_text("original\n", encoding="utf-8")
        baseline = snapshot(repo)
        unwatched.write_text("a cell wrote over this\n", encoding="utf-8")
        found = strays(baseline, snapshot(repo))
        check("a write to an ignored path outside the watch list is NOT detected "
              "(the declared limit)", found == [], f"stray list was {found}")

    # A ledger for one run's own report directory. Before PR #147 the ledger
    # took no record directory, so a pre-fix runner raises TypeError here; the
    # cases below then report themselves failing rather than crashing the run.
    def new_ledger(own_record_dir):
        if ledger_class is None:
            return None
        try:
            return ledger_class(own_record_dir)
        except TypeError:
            return None

    ledger_takes_no_record_dir = ("the ledger under test takes no record "
                                  "directory (pre-PR-#147 signature)")

    # Case 12: two runner invocations overlapping in one worktree. Each run's
    # stray check walks the whole record root, so it sees the other run's
    # legitimately written reports — which are in neither its own baseline
    # (taken before the other run's directory had files) nor its own ledger,
    # which is per-invocation state. Reported on PR #147: both runs printed
    # `WARNING: cut-codex modified the worktree`, each naming a file the other
    # run's RUNNER wrote, one of them accusing its own cell of a write that
    # cell never made. Concurrent runs are a scenario this file supports on
    # purpose — see fresh_record_dir's docstring and case 17.
    with tempfile.TemporaryDirectory() as scratch:
        repo = new_repo(pathlib.Path(scratch))
        (repo / ".gitignore").write_text(f"{records_name}/\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "ignore the record directory")
        dir_a = repo / records_name / "2026-08-23-design"
        dir_b = repo / records_name / "2026-08-23-design-2"
        dir_a.mkdir(parents=True)
        dir_b.mkdir(parents=True)
        ledger_a, ledger_b = new_ledger(dir_a), new_ledger(dir_b)
        if ledger_a is None or ledger_b is None:
            for case_name in (
                    "a concurrent run's reports are not this run's stray",
                    "a concurrent run that started first is not this run's stray",
                    "a new file a cell writes in this run's own record directory is detected",
                    "a new file elsewhere under the record root is NOT reported "
                    "(the concurrency carve-out)"):
                check(case_name, False, ledger_takes_no_record_dir)
        else:
            # Run A takes its baseline, then run B writes a report of its own.
            baseline_a = snapshot(repo)
            ledger_b.write_report(dir_b / "cut-claude.md", "run B's report\n", repo)
            found = ledger_a.stray_paths_since(baseline_a, repo)
            check("a concurrent run's reports are not this run's stray",
                  found == [], f"stray list was {found}")

            # The other ordering: run A's directory already held a report when
            # run B took its baseline, and A goes on writing.
            ledger_a.write_report(dir_a / "cut-claude.md", "run A's report\n", repo)
            baseline_b = snapshot(repo)
            ledger_a.write_report(dir_a / "cut-codex.md", "run A's second report\n", repo)
            found = ledger_b.stray_paths_since(baseline_b, repo)
            check("a concurrent run that started first is not this run's stray",
                  found == [], f"stray list was {found}")

            # What the run's own directory still buys: a cell writing anything
            # into it is this run's business and is named.
            (dir_a / "cell-scribble.md").write_text("a cell wrote this\n", encoding="utf-8")
            found = ledger_a.stray_paths_since(baseline_a, repo)
            check("a new file a cell writes in this run's own record directory is detected",
                  f"{records_name}/2026-08-23-design/cell-scribble.md" in found,
                  f"stray list was {found}")

            # The price of the fix, asserted rather than left to be discovered:
            # a brand-new file under the record root but outside this run's own
            # directory is exactly what a concurrent run legitimately makes, so
            # it is no longer reported. Overwriting a file that was there when
            # the run started, or one this run wrote, is still reported — those
            # are the cases above and cases 7, 8 and 14.
            (repo / records_name / "cell-scribble-elsewhere.md").write_text(
                "a cell wrote this\n", encoding="utf-8")
            found = ledger_a.stray_paths_since(baseline_a, repo)
            check("a new file elsewhere under the record root is NOT reported "
                  "(the concurrency carve-out)",
                  f"{records_name}/cell-scribble-elsewhere.md" not in found,
                  f"stray list was {found}")

    # Case 13: the runner invoked where `sanity-check-records/` is NOT ignored
    # — a revision without that .gitignore line, or a worktree where it has
    # been edited. git then reports every report the runner writes as `??`,
    # while the ledger recorded `!!` on the assumption that the ignore rule
    # still held, so each later codex cell named the runner's own report as a
    # worktree modification even though its fingerprint matched
    # (chatgpt-codex-connector, P2 on PR #147).
    with tempfile.TemporaryDirectory() as scratch:
        repo = new_repo(pathlib.Path(scratch))  # no ignore rule for the record root
        out_dir = repo / records_name / "2026-08-23-design"
        out_dir.mkdir(parents=True)
        if ledger_class is None:
            check("a report written where the record root is not ignored is not a stray",
                  False, missing_ledger)
        else:
            ledger = ledger_class()
            baseline = snapshot(repo)
            ledger.write_report(out_dir / "cut-claude.md", "the report\n", repo)
            found = ledger.stray_paths_since(baseline, repo)
            check("a report written where the record root is not ignored is not a stray",
                  found == [], f"stray list was {found}")

    # Case 14: a cell running `git add -f` on a report the runner wrote. The
    # ledger records the status git gives the path, so a later change of that
    # status diverges from the record and is named — the property case 13's
    # fix must not trade away. Passes before and after case 13.
    with tempfile.TemporaryDirectory() as scratch:
        repo = new_repo(pathlib.Path(scratch))
        (repo / ".gitignore").write_text(f"{records_name}/\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "ignore the record directory")
        out_dir = repo / records_name / "2026-08-23-design"
        out_dir.mkdir(parents=True)
        if ledger_class is None:
            check("a cell force-adding a report the runner wrote is detected",
                  False, missing_ledger)
        else:
            ledger = ledger_class()
            baseline = snapshot(repo)
            report = out_dir / "cut-claude.md"
            ledger.write_report(report, "the report\n", repo)
            git(repo, "add", "-f", str(report))
            found = ledger.stray_paths_since(baseline, repo)
            check("a cell force-adding a report the runner wrote is detected",
                  f"{records_name}/2026-08-23-design/cut-claude.md" in found,
                  f"stray list was {found}")

    # Case 15: a cell writing to a report path BEFORE the runner writes its
    # report there. The runner's own write repaired the file, the ledger then
    # recorded the repaired content, and the cell's write was never reported
    # (PR #147 finding 2). The record directory is claimed fresh by mkdir and
    # only the ledger writes reports into it, so anything already at the path
    # was put there during this run by something else.
    with tempfile.TemporaryDirectory() as scratch:
        repo = new_repo(pathlib.Path(scratch))
        (repo / ".gitignore").write_text(f"{records_name}/\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "ignore the record directory")
        out_dir = repo / records_name / "2026-08-23-design"
        out_dir.mkdir(parents=True)
        if ledger_class is None:
            check("a report path a cell wrote to first is reported", False, missing_ledger)
            check("an unoccupied report path is not reported", False, missing_ledger)
        else:
            ledger = ledger_class()
            scribbled = out_dir / "cut-claude.md"
            scribbled.write_text("a cell scribbled here first\n", encoding="utf-8")
            check("a report path a cell wrote to first is reported",
                  ledger.write_report(scribbled, "the claude report\n", repo) is True,
                  "write_report did not report the occupied path")
            check("an unoccupied report path is not reported",
                  ledger.write_report(out_dir / "cut-codex.md",
                                      "the codex report\n", repo) is False,
                  "write_report reported an unoccupied path")

    # Case 16: the ledger fingerprints the text it was handed, not the file it
    # has just written — which closes the window where a cell writing between
    # those two steps would have its content recorded as the runner's own work,
    # and removes a subprocess per report (PR #147 finding 3, raised as a
    # simplification; the window is microseconds wide and was not reproduced).
    # The window cannot be hit on demand, so the mechanism is what is checked:
    # file_fingerprint is replaced by a sentinel for the duration of the write,
    # and a ledger that consults the disk records the sentinel — after which
    # its own report reads as a stray.
    with tempfile.TemporaryDirectory() as scratch:
        repo = new_repo(pathlib.Path(scratch))
        (repo / ".gitignore").write_text(f"{records_name}/\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "ignore the record directory")
        out_dir = repo / records_name / "2026-08-23-design"
        out_dir.mkdir(parents=True)
        if ledger_class is None:
            check("the ledger fingerprints the text it was handed, not the file on disk",
                  False, missing_ledger)
        else:
            ledger = ledger_class()
            baseline = snapshot(repo)
            real_file_fingerprint = runner.file_fingerprint
            try:
                runner.file_fingerprint = lambda *arguments: "SENTINEL-NOT-A-FINGERPRINT"
                ledger.write_report(out_dir / "cut-claude.md", "the report\n", repo)
            finally:
                runner.file_fingerprint = real_file_fingerprint
            found = ledger.stray_paths_since(baseline, repo)
            check("the ledger fingerprints the text it was handed, not the file on disk",
                  found == [], f"stray list was {found}")

    # Case 17: two runs starting together must not be handed the same record
    # directory. A look-then-create claim passes both when neither has written
    # its first report yet, and the second run overwrites the first.
    records_root = getattr(runner, "RECORDS_ROOT", None)
    with tempfile.TemporaryDirectory() as scratch:
        runner.RECORDS_ROOT = pathlib.Path(scratch) / "sanity-check-records"
        first = runner.fresh_record_dir("same-target")
        second = runner.fresh_record_dir("same-target")
        check("a second run for the same target and date gets its own directory",
              first != second, f"both runs got {first}")
        check("the second directory is suffixed", second.name.endswith("-2"),
              f"second directory was {second}")
    if records_root is not None:
        runner.RECORDS_ROOT = records_root

    # Case 18: run_cell's worktree check must run for a claude cell, not only
    # a codex one. On 2026-08-21 a claude cell wrote a 25,170-byte file to the
    # worktree root anyway, and run_cell's `if runtime == "codex":` gate never
    # looked (nedschorus#161). run_claude is replaced by a stand-in so no
    # model is called, and report_ledger is a bare stand-in too — cases 1-17
    # above already cover the real ledger's bookkeeping; this case is about
    # the gate in run_cell, exercised directly, not the ledger it calls.
    import contextlib
    import io

    class StubLedger:
        def __init__(self, stray):
            self._stray = stray

        def stray_paths_since(self, baseline):
            return self._stray

        def write_report(self, out_path, text):
            return False

    runner_gate = load_runner()
    stray_name = "stray-file-a-claude-cell-should-not-write.md"
    # Report-shaped, so the cell reaches the report write the way a real one
    # does: a text lacking the cut prompt's sections is refused (case 23).
    runner_gate.run_claude = lambda prompt, checkout=None: (
        0, "the cell's report body\n\n## Questions\n\nNone.\n\n"
           "## Leanness certification\n\n- the whole document\n",
        "claude-fable-5-1", "")
    buffer = io.StringIO()
    # A real record directory, in a temporary tree: run_cell makes the cell's
    # scratch directory under the one it is handed, and a relative path here
    # would leave that directory wherever this file happens to be run from.
    with tempfile.TemporaryDirectory() as scratch:
        with contextlib.redirect_stdout(buffer):
            runner_gate.run_cell(
                "cut", "claude", "docs/agents/sanity-checker-cut-attack-prompt.md",
                [], pathlib.Path("unused-problem-statement.md"),
                pathlib.Path(scratch), {}, (), StubLedger([stray_name]))
    output = buffer.getvalue()
    check("a claude cell that leaves a stray path behind is warned about, "
          "same as a codex cell",
          "WARNING: the review copy was modified outside the cells' scratch "
          f"directories, seen when cut-claude finished: {stray_name}" in output,
          f"output was {output!r}")

    # Case 19: the per-cell scratch directory the runner makes. The prompts
    # used to say "write no files", which the cells did not reliably keep and
    # the detector then reported; each cell now gets a sanctioned working space
    # of its own instead (user-ruled 2026-08-29). The runner makes it, so a
    # cell never has to, and it sits inside the run's record directory so the
    # record's disposal disposes of it too.
    with tempfile.TemporaryDirectory() as scratch:
        out_dir = pathlib.Path(scratch) / "2026-08-29-design"
        out_dir.mkdir()
        made = runner.cell_scratch_dir(out_dir, "cut-claude")
        check("the runner creates the cell's scratch directory", made.is_dir(),
              f"{made} is not a directory")
        check("the scratch directory is per cell, under the run's record directory",
              made == out_dir / "scratch" / "cut-claude", f"the runner made {made}")
        check("a scratch directory that already exists is not an error",
              runner.cell_scratch_dir(out_dir, "cut-claude") == made,
              "the second call did not return the same directory")

    # Case 20: the write detector exempts this run's scratch subtree. A cell
    # writing notes where its prompt told it to write must not be named as a
    # stray — a warning on ordinary behaviour teaches its reader to skip the
    # warning that means something, the same defect case 9 measures. The
    # exemption is of the subtree and only of THIS run's: everywhere else,
    # inside the run's own record directory included, is watched unchanged.
    with tempfile.TemporaryDirectory() as scratch:
        repo = new_repo(pathlib.Path(scratch))
        (repo / ".gitignore").write_text(f"{records_name}/\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "ignore the record directory")
        out_dir = repo / records_name / "2026-08-29-design"
        out_dir.mkdir(parents=True)
        earlier_scratch = (repo / records_name / "2026-08-28-design"
                           / "scratch" / "cut-claude")
        earlier_scratch.mkdir(parents=True)
        (earlier_scratch / "leftover.md").write_text("an earlier run's notes\n",
                                                     encoding="utf-8")
        ledger = new_ledger(out_dir)
        if ledger is None:
            for case_name in (
                    "a cell writing in its own scratch directory is not a stray",
                    "the exemption covers the whole scratch subtree",
                    "the scratch exemption does not reach the rest of the record directory",
                    "an earlier run's scratch is not exempt"):
                check(case_name, False, ledger_takes_no_record_dir)
        else:
            baseline = snapshot(repo)
            cell_scratch = runner.cell_scratch_dir(out_dir, "cut-claude")
            (cell_scratch / "working-notes.md").write_text(
                "the notes this cell took\n", encoding="utf-8")
            found = ledger.stray_paths_since(baseline, repo)
            check("a cell writing in its own scratch directory is not a stray",
                  found == [], f"stray list was {found}")

            # Every cell's directory, not just the one that happens to ask:
            # stray_paths_since is per run and cannot tell which cell is
            # calling it, so the exemption is of the whole subtree.
            other_scratch = runner.cell_scratch_dir(out_dir, "fresh-eyes-codex")
            (other_scratch / "sketch-draft.md").write_text(
                "another cell's draft\n", encoding="utf-8")
            found = ledger.stray_paths_since(baseline, repo)
            check("the exemption covers the whole scratch subtree",
                  found == [], f"stray list was {found}")

            # Where the exemption stops: the rest of the run's own record
            # directory is the reports, and a cell writing there is case 12's
            # third check — still named.
            (out_dir / "cell-scribble.md").write_text("a cell wrote this\n",
                                                      encoding="utf-8")
            found = ledger.stray_paths_since(baseline, repo)
            check("the scratch exemption does not reach the rest of the record directory",
                  f"{records_name}/2026-08-29-design/cell-scribble.md" in found,
                  f"stray list was {found}")

            # An earlier run's scratch belongs to nobody here: it was on disk
            # when this run started, sits in the baseline, and is compared like
            # any other file.
            (earlier_scratch / "leftover.md").write_text(
                "a cell wrote over this\n", encoding="utf-8")
            found = ledger.stray_paths_since(baseline, repo)
            check("an earlier run's scratch is not exempt",
                  f"{records_name}/2026-08-28-design/scratch/cut-claude/leftover.md"
                  in found, f"stray list was {found}")

    # Case 21: the boundary of case 20, asserted rather than assumed — the same
    # service case 11 does for the ignored-path watch. The exemption is of the
    # subtree, so it holds whatever git says about a path inside it: a cell
    # running `git add -f` on its own scratch file is not reported, where the
    # same act on a report is (case 14). This case passes before and after
    # case 20's exemption is written; it states the carve-out's price, and it
    # fails if the exemption ever silently narrows to unstaged files.
    with tempfile.TemporaryDirectory() as scratch:
        repo = new_repo(pathlib.Path(scratch))
        (repo / ".gitignore").write_text(f"{records_name}/\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "ignore the record directory")
        out_dir = repo / records_name / "2026-08-29-design"
        out_dir.mkdir(parents=True)
        ledger = new_ledger(out_dir)
        if ledger is None:
            check("a cell force-adding its own scratch file is NOT reported "
                  "(the declared limit)", False, ledger_takes_no_record_dir)
        else:
            baseline = snapshot(repo)
            note = runner.cell_scratch_dir(out_dir, "cut-claude") / "working-notes.md"
            note.write_text("the notes this cell took\n", encoding="utf-8")
            git(repo, "add", "-f", str(note))
            found = ledger.stray_paths_since(baseline, repo)
            check("a cell force-adding its own scratch file is NOT reported "
                  "(the declared limit)", found == [], f"stray list was {found}")

    # Case 22: the scratch path reaches the cell. The sentence granting the
    # working space lives in the prompt MD, where the cold read reviews it;
    # only the path — data, and different for every cell — comes from the
    # runner, which substitutes it for the MD's placeholder token. A cell that
    # received the token instead of a path would have nowhere to write.
    runner_substitution = load_runner()
    cell_scratch_path = "/tmp/records/2026-08-29-design/scratch/cut-claude"
    assembled = runner_substitution.assemble_prompt(
        "cut", "docs/x.md", [], pathlib.Path("unused-problem-statement.md"),
        cell_scratch_path)
    check("the assembled prompt names this cell's scratch directory",
          cell_scratch_path in assembled,
          f"assembled prompt began {assembled[:120]!r}")
    check("no placeholder token survives into the assembled prompt",
          runner_substitution.PROMPT_SCRATCH_DIRECTORY_PLACEHOLDER not in assembled,
          "the placeholder token reached the cell")

    # Case 23: a text that is not a report is refused, on both runtimes. On
    # 2026-09-15 a Stop hook's note reached two claude cells, each answered
    # it, and the runner saved the answer — the text below opens one of them —
    # in place of a 3,684-word review, printed `saved:` and
    # exited 0 (nedschorus#397). The runtime stand-ins return what a cell
    # captured; the ledger stand-in writes for real, so "no report" is
    # checked on disk rather than read off a write that never happens. The
    # stand-ins answer the same text at every launch, so the refused cell is
    # launched a second time and refused again (cases 38 to 43 are the
    # relaunch's own).
    non_report = ("The report above is my complete reply. The stop hook's "
                  "freshness note concerns the branch this worktree sits on, "
                  "not my review.\n")
    # Headings reshaped on purpose: the check reads phrases, not syntax.
    cut_report = ("# Cut audit\n\n## Finding 1: delete the section\n\n"
                  "**QUESTIONS**\n\nNone.\n\nLeanness Certification:\n\n"
                  "- the whole document\n")

    class WritingStubLedger(StubLedger):
        def __init__(self):
            super().__init__([])

        def write_report(self, out_path, text):
            out_path.write_text(text, encoding="utf-8")
            return False

    runner_refusal = load_runner()
    runner_refusal.CLI_VERSION_CACHE.update({"claude": "1.1.1-test",
                                             "codex": "2.2.2-test"})
    for runtime in runner_refusal.RUNTIMES:
        for captured_text, is_report in ((non_report, False), (cut_report, True)):
            answer = (0, captured_text, "a-test-model", "")
            runner_refusal.run_claude = lambda prompt, checkout=None, answer=answer: answer
            runner_refusal.run_codex = lambda prompt, checkout=None, answer=answer: answer
            buffer = io.StringIO()
            with tempfile.TemporaryDirectory() as scratch:
                out_dir = pathlib.Path(scratch)
                with contextlib.redirect_stdout(buffer):
                    _, cell_ok = runner_refusal.run_cell(
                        "cut", runtime, "docs/x.md", [],
                        pathlib.Path("unused-problem-statement.md"), out_dir,
                        {}, (), WritingStubLedger())
                report_written = (out_dir / f"cut-{runtime}.md").is_file()
            output = buffer.getvalue()
            if is_report:
                check(f"a {runtime} text carrying the cut sections is saved",
                      cell_ok and report_written and "saved:" in output
                      and "FAILED:" not in output, f"output was {output!r}")
            else:
                failed_line = (f"FAILED: cut-{runtime} — not-a-report — the text it "
                               f"returned lacks questions, leanness (relaunched once)\n")
                check(f"a {runtime} text that is not a report prints the FAILED line",
                      failed_line in output
                      and "saved:" not in output, f"output was {output!r}")
                check(f"a {runtime} text that is not a report is launched once more, "
                      f"and both refused texts are printed",
                      output.count(f"RETRYING: cut-{runtime} — not-a-report — ") == 1
                      and output.count(non_report) == 2, f"output was {output!r}")
                check(f"a {runtime} text that is not a report is printed before "
                      f"the FAILED line",
                      non_report in output and failed_line in output
                      and output.index(non_report) < output.index(failed_line),
                      f"output was {output!r}")
                check(f"a {runtime} text that is not a report writes no report "
                      f"and fails the cell", not cell_ok and not report_written,
                      f"cell_ok={cell_ok}, report written={report_written}")

    # Case 24: the refused cell reaches the exit code. main() is driven with
    # every expensive dependency replaced — no model, no git walk, no corpus —
    # and the record root in a temporary directory: one runtime answering with
    # a non-report must make the run exit 1, with only the other's report on
    # disk; both answering with reports exits 0.
    runner_exit = load_runner()
    runner_exit.CLI_VERSION_CACHE.update({"claude": "1.1.1-test",
                                          "codex": "2.2.2-test"})
    runner_exit.worktree_snapshot = lambda *arguments: {}
    runner_exit.tracked_files_corpus = lambda *arguments: ()
    runner_exit.reviewed_revision = lambda *arguments: "commit=test worktree=clean"
    # The review copy and the committed-target check are cases 27-31's
    # subject; here the target is this repository's own prompt, and the copy
    # is an empty directory, so no checkout of this repository is made.
    runner_exit.uncommitted_review_paths = lambda *arguments: []

    @contextlib.contextmanager
    def empty_review_copy(commit, record_name, repo_root):
        with tempfile.TemporaryDirectory() as copy:
            yield pathlib.Path(copy)

    runner_exit.review_copy_of_commit = empty_review_copy
    real_argv = sys.argv
    for claude_text, expected_exit in ((non_report, 1), (cut_report, 0)):
        runner_exit.run_claude = lambda prompt, checkout=None, text=claude_text: (
            0, text, "a-test-model", "")
        runner_exit.run_codex = lambda prompt, checkout=None: (
            0, cut_report, "a-test-model", "")
        with tempfile.TemporaryDirectory() as scratch:
            runner_exit.RECORDS_ROOT = pathlib.Path(scratch) / "sanity-check-records"
            sys.argv = [str(RUNNER_SCRIPT), "--attack", "cut", "--target",
                        "docs/agents/sanity-checker-cut-attack-prompt.md"]
            buffer = io.StringIO()
            try:
                with contextlib.redirect_stdout(buffer):
                    exit_code = runner_exit.main()
            finally:
                sys.argv = real_argv
            saved = sorted(path.name for path
                           in runner_exit.RECORDS_ROOT.glob("*/*.md"))
        expected_saved = (["cut-codex.md"] if expected_exit
                          else ["cut-claude.md", "cut-codex.md"])
        check(f"a run whose claude cell {'is refused' if expected_exit else 'reports'} "
              f"exits {expected_exit}, saving {', '.join(expected_saved)}",
              exit_code == expected_exit and saved == expected_saved,
              f"exit {exit_code}, saved {saved}, output {buffer.getvalue()!r}")

    # Case 25: a cell that times out prints what its runtime wrote before it
    # was cut off. subprocess.TimeoutExpired carries both piped streams, and
    # run_cell's handler printed only its FAILED line — the one ending that
    # dropped a failed runtime's words. The streams arrive in three forms:
    # text; bytes, which CPython hands back on a timeout even to a call that
    # asked for text, here ending partway through a character so the decoding
    # must replace rather than raise; and None, which is what a codex cell's
    # DEVNULL streams give. Neither text stream ends its line, as a stream cut
    # off mid-write rarely does, so the FAILED line must still start its own.
    # The cell fails in every form: whether a timeout should fall back to the
    # next model is not this case's subject.
    runner_timeout = load_runner()
    stdout_words = "partial review, cut off mid-sente"
    stderr_words = "still reading section 2"
    streams_by_form = (
        ("str", stdout_words, stderr_words),
        ("bytes", stdout_words.encode("utf-8") + b" \xe2\x80",
         stderr_words.encode("utf-8")),
        ("None", None, None),
    )
    for runtime in runner_timeout.RUNTIMES:
        for form, captured_stdout, captured_stderr in streams_by_form:
            def timing_out(prompt, checkout=None, out=captured_stdout,
                           err=captured_stderr):
                raise subprocess.TimeoutExpired(
                    ["a-runtime"], runner_timeout.CELL_TIMEOUT_SECONDS,
                    output=out, stderr=err)

            runner_timeout.run_claude = timing_out
            runner_timeout.run_codex = timing_out
            timeout_line = (f"FAILED: cut-{runtime} — timeout — after "
                            f"{runner_timeout.CELL_TIMEOUT_SECONDS}s\n")
            buffer = io.StringIO()
            cell_ok, raised = None, None
            with tempfile.TemporaryDirectory() as scratch:
                try:
                    with contextlib.redirect_stdout(buffer):
                        _, cell_ok = runner_timeout.run_cell(
                            "cut", runtime, "docs/x.md", [],
                            pathlib.Path("unused-problem-statement.md"),
                            pathlib.Path(scratch), {}, (), StubLedger([]))
                except Exception as error:
                    raised = error
            output = buffer.getvalue()
            if form == "None":
                check(f"a {runtime} cell timing out with no captured streams prints "
                      f"nothing before the FAILED timeout line and fails the cell",
                      raised is None and cell_ok is False
                      and output.startswith(timeout_line),
                      f"raised={raised!r}, cell_ok={cell_ok}, output was {output!r}")
                continue
            check(f"a {runtime} cell timing out with {form} streams prints both "
                  f"before the FAILED timeout line, which starts its own line",
                  raised is None
                  and stdout_words in output and stderr_words in output
                  and "\n" + timeout_line in output
                  and output.index(stdout_words) < output.index(timeout_line)
                  and output.index(stderr_words) < output.index(timeout_line),
                  f"raised={raised!r}, output was {output!r}")
            check(f"a {runtime} cell timing out with {form} streams still fails",
                  raised is None and cell_ok is False and "saved:" not in output,
                  f"raised={raised!r}, cell_ok={cell_ok}, output was {output!r}")
            if form == "bytes":
                check(f"a {runtime} cell's undecodable timeout bytes are replaced, "
                      f"not raised on", raised is None and "�" in output,
                      f"raised={raised!r}, output was {output!r}")

    # Case 26: a timeout partway through the claude chain. The first model
    # fails and run_claude prints its words as that attempt ends; the next
    # model times out. The words the timeout prints must be the timed-out
    # attempt's own, and the failed attempt's must appear exactly once — not
    # lost with the exception, not printed a second time. No model is called:
    # the launch is replaced for this one cell and put back in a finally, as
    # the chain cases below do.
    runner_chain_timeout = load_runner()
    first_model = runner_chain_timeout.CLAUDE_MODEL_CHAIN[0]

    def first_fails_then_next_times_out(command, *arguments, **keywords):
        if command[command.index("--model") + 1] == first_model:
            return subprocess.CompletedProcess(
                list(command), 1, "first model: not available\n",
                "first model: overloaded\n")
        raise subprocess.TimeoutExpired(
            list(command), keywords.get("timeout"),
            output=b"next model: partial review", stderr=b"next model: still reading")

    real_chain_timeout_run = agent_binary_launch_a_case_replaces(runner_chain_timeout)
    buffer = io.StringIO()
    cell_ok = None
    try:
        runner_chain_timeout.run_agent_binary_unless_run_stopped = first_fails_then_next_times_out
        with tempfile.TemporaryDirectory() as scratch:
            with contextlib.redirect_stdout(buffer):
                _, cell_ok = runner_chain_timeout.run_cell(
                    "cut", "claude", "docs/x.md", [],
                    pathlib.Path("unused-problem-statement.md"),
                    pathlib.Path(scratch), {}, (), StubLedger([]))
    finally:
        runner_chain_timeout.run_agent_binary_unless_run_stopped = real_chain_timeout_run
    output = buffer.getvalue()
    timeout_line = (f"FAILED: cut-claude — timeout — after "
                    f"{runner_chain_timeout.CELL_TIMEOUT_SECONDS}s\n")
    check("a claude cell timing out after a failed attempt prints the timed-out "
          "attempt's words once, after the failed attempt's and before the FAILED line",
          all(output.count(words) == 1 for words in
              ("next model: partial review", "next model: still reading"))
          and timeout_line in output
          and output.index("first model: not available")
          < output.index("next model: partial review")
          < output.index(timeout_line),
          f"output was {output!r}")
    check("and the failed attempt's words print exactly once",
          output.count("first model: not available") == 1
          and output.count("first model: overloaded") == 1,
          f"output was {output!r}")
    check("and the cell still fails", cell_ok is False, f"cell_ok={cell_ok}")

    # The prompt-body boundary. The marker replaced a bare `---` rule, which is
    # ordinary markdown: a horizontal rule anywhere above the intended split
    # silently truncated the prompt, and nothing failed.
    with tempfile.TemporaryDirectory() as scratch:
        scratch_dir = pathlib.Path(scratch)
        marker = runner.PROMPT_BODY_MARKER
        heading = runner.PROMPT_BODY_FIRST_LINE
        placeholder = runner.PROMPT_SCRATCH_DIRECTORY_PLACEHOLDER

        def prompt_file(name, text):
            path = scratch_dir / name
            path.write_text(text, encoding="utf-8")
            runner.ATTACK_PROMPT_FILES["cut"] = path
            return path

        def split_fails(name, text):
            prompt_file(name, text)
            import contextlib
            import io
            try:
                with contextlib.redirect_stderr(io.StringIO()):
                    runner.prompt_body("cut")
            except SystemExit as exc:
                # The documented contract: an unusable invocation exits 2.
                return exc.code == 2
            return False

        good = (f"# Header\n\nStatus: names the {marker} line inline.\n\n"
                f"{marker}\n\n{heading}\n\nBody text writing to {placeholder}.\n")
        prompt_file("good.md", good)
        body = runner.prompt_body("cut")
        check("a header naming the marker inline still splits at the marker line",
              body.startswith(heading) and "Status:" not in body,
              f"body began {body[:60]!r}")

        check("a prompt with no marker line is refused",
              split_fails("none.md", f"# Header\n\n{heading}\n\n{placeholder}\n"))
        check("a prompt with two marker lines is refused",
              split_fails("two.md",
                          f"# Header\n\n{marker}\n\n{heading}\n\n{marker}\n\n{placeholder}\n"))
        check("a body not opening with the expected heading is refused",
              split_fails("wrong.md",
                          f"# Header\n\n{marker}\n\nStray line.\n\n{heading}\n\n{placeholder}\n"))

        # The scratch placeholder, checked in the same place and for the same
        # reason: a body that stopped naming its scratch directory would send
        # a cell out with a directory it was never told about, and the failure
        # must land before any model cost. Counted in the body alone — a
        # header explaining the token is not a body that carries it, the same
        # distinction the marker search makes.
        check("a prompt body with no scratch placeholder is refused",
              split_fails("no-scratch.md",
                          f"# Header\n\n{marker}\n\n{heading}\n\nBody text.\n"))
        check("a prompt body with two scratch placeholders is refused",
              split_fails("two-scratch.md",
                          f"# Header\n\n{marker}\n\n{heading}\n\n"
                          f"{placeholder} and again {placeholder}.\n"))
        check("a header naming the scratch placeholder is not a body that carries it",
              split_fails("header-scratch.md",
                          f"# Header explaining {placeholder}.\n\n{marker}\n\n"
                          f"{heading}\n\nBody text.\n"))

        rules = (f"# Header\n\n---\n\nStatus text.\n\n---\n\n{marker}\n\n"
                 f"{heading}\n\nBody writing to {placeholder}.\n")
        prompt_file("rules.md", rules)
        body = runner.prompt_body("cut")
        check("horizontal rules above the marker no longer move the split",
              body.startswith(heading) and "Status text." not in body,
              f"body began {body[:60]!r}")

    # The quote scan: a verbatim quote is silent, words in no tracked file warn.
    import contextlib
    import io
    runner_scan = load_runner()
    corpus = (runner_scan.normalized_for_quote_match(
        "the gate records every legacy import cleanly"),)
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        runner_scan.quote_scan(corpus, 'It says "records every legacy import cleanly" here.', "q1")
    check("a verbatim quote raises no warning", buffer.getvalue() == "",
          f"output was {buffer.getvalue()!r}")
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        runner_scan.quote_scan(corpus, 'It says "words that appear in no file at all" here.', "q2")
    check("a quote found nowhere warns",
          "quote found in no tracked file" in buffer.getvalue(),
          f"output was {buffer.getvalue()!r}")

    # The print modes: each surface arrives on stdout, and the requester
    # surface carries both of its sources.
    import subprocess as sp
    requester = sp.run([str(RUNNER_SCRIPT), "--print", "requester"],
                       capture_output=True, text=True)
    check("--print requester emits the docstring and the requester section",
          requester.returncode == 0
          and "second review instrument" in requester.stdout
          and "Writing the problem statement" in requester.stdout,
          f"rc={requester.returncode}")
    cell_view = sp.run([str(RUNNER_SCRIPT), "--print", "cut",
                        "--target", "docs/agents/sanity-checker-cut-attack-prompt.md"],
                       capture_output=True, text=True)
    check("--print cut emits the assembled cell prompt",
          cell_view.returncode == 0
          and cell_view.stdout.startswith("## Your assignment")
          and "Document under review:" in cell_view.stdout,
          f"rc={cell_view.returncode}, began {cell_view.stdout[:40]!r}")

    # The three standing prompts must each split cleanly.
    runner_fresh = load_runner()
    for attack in runner_fresh.ATTACKS:
        body = runner_fresh.prompt_body(attack)
        check(f"the standing {attack} prompt splits at its marker",
              body.startswith(runner_fresh.PROMPT_BODY_FIRST_LINE),
              f"body began {body[:60]!r}")

    # The phrases a report must carry come from the prompts, so each must be
    # in its prompt's body: a section renamed there, or a phrase edited here,
    # fails this rather than refusing every genuine report of that attack.
    # Looked up with a default, so a runner without the table reports this
    # case failing rather than crashing the cases after it.
    required_phrases = getattr(runner_fresh, "ATTACK_REPORT_REQUIRED_PHRASES", {})
    check("every attack has required report phrases",
          set(required_phrases) == set(runner_fresh.ATTACKS),
          sorted(required_phrases))
    for attack in runner_fresh.ATTACKS:
        body = runner_fresh.prompt_body(attack).lower()
        absent = [phrase for phrase in required_phrases.get(attack, ())
                  if phrase not in body]
        check(f"every phrase a {attack} report must carry is in the {attack} prompt's body",
              absent == [], f"not in the body: {absent}")

    # The codex cells must launch with Codex's machine-wide memory store off,
    # so a cell does not carry forward what Codex concluded reviewing this
    # project before -- the measured half. Why, in full, and what the flag
    # does NOT settle about the writing half, in
    # scripts/code-review-codex-cell.py's docstring under the heading
    # WHY THE CODEX MEMORY STORE IS OFF FOR REVIEW CELLS
    # The composed command is inspected rather than run: launching a cell
    # costs a model call, and the defect this guards against is a missing
    # argument.
    #
    # The agent-binary's launch, run_agent_binary_unless_run_stopped, is
    # replaced for the length of one call only, and goes back in a finally.
    runner_memories = load_runner()
    captured = {}
    real_memories_launch = agent_binary_launch_a_case_replaces(runner_memories)

    def capture_command(command, *arguments, **keywords):
        captured["command"] = list(command)
        return subprocess.CompletedProcess(list(command), 0, "", "")

    # The credential lists are pointed at a scratch home for the call, so the
    # profile's denials name paths in it and the real home is neither scanned
    # nor named in a failure line. The credential directories are re-rooted
    # from the real list rather than listed here, so a directory dropped from
    # CREDENTIAL_DIRECTORIES drops out of the profile.
    credential_scratch = tempfile.TemporaryDirectory()
    scratch_home = pathlib.Path(credential_scratch.name)
    (scratch_home / ".config" / "nedschorus").mkdir(parents=True)
    (scratch_home / ".config" / "gh").mkdir(parents=True)
    login_canary = scratch_home / ".codex" / "auth.json"
    login_canary.parent.mkdir(parents=True)
    login_canary.write_text("CANARY-NOT-A-SECRET-sanity-check-attacks-test\n", encoding="utf-8")
    shared = runner_memories.common
    real_lists = (shared.CREDENTIAL_DIRECTORIES, shared.REVIEWER_PROGRAM_LOGIN_FILES,
                  shared.credential_files_found_now)
    try:
        runner_memories.run_agent_binary_unless_run_stopped = capture_command
        shared.CREDENTIAL_DIRECTORIES = tuple(
            scratch_home / directory.relative_to(pathlib.Path.home())
            for directory in real_lists[0])
        shared.REVIEWER_PROGRAM_LOGIN_FILES = {"codex": (login_canary,)}
        shared.credential_files_found_now = lambda: []
        runner_memories.run_codex("a prompt no model ever sees")
    finally:
        runner_memories.run_agent_binary_unless_run_stopped = real_memories_launch
        (shared.CREDENTIAL_DIRECTORIES, shared.REVIEWER_PROGRAM_LOGIN_FILES,
         shared.credential_files_found_now) = real_lists
    codex_command = captured.get("command", [])
    check("run_codex launches codex with memories disabled",
          ("--disable", "memories") in list(zip(codex_command, codex_command[1:])),
          f"composed command was {codex_command}")

    # No credential file is readable (user-ruled 2026-09-29): a permission
    # profile extending :workspace with network on, which Codex will not
    # combine with --sandbox, in place of workspace-write plus network.
    codex_overrides = [codex_command[index + 1] for index, argument
                       in enumerate(codex_command[:-1]) if argument == "-c"]
    denied_table = next((override.split("=", 1)[1] for override in codex_overrides
                         if override.startswith("permissions.sanity-check-no-credentials.filesystem=")),
                        "")
    check("run_codex runs under no --sandbox, which Codex will not combine with a profile",
          "--sandbox" not in codex_command, f"composed command was {codex_command}")
    check("run_codex runs under the credential-denying profile, extending :workspace, network on",
          'default_permissions="sanity-check-no-credentials"' in codex_overrides
          and 'permissions.sanity-check-no-credentials.extends=":workspace"' in codex_overrides
          and "permissions.sanity-check-no-credentials.network.enabled=true" in codex_overrides,
          repr(codex_overrides))
    check("run_codex's profile denies the credential directories and a reviewer program's login file",
          f'"{scratch_home}/.config/nedschorus"="deny"' in denied_table
          and f'"{scratch_home}/.config/gh"="deny"' in denied_table
          and f'"{login_canary}"="deny"' in denied_table, denied_table)
    credential_scratch.cleanup()

    # The claude cells must launch with Write in the tool set: each is given a
    # scratch directory and told to keep its notes and drafts there
    # (user-ruled 2026-08-29), and without the tool that instruction asks for
    # something the cell cannot do. Inspected, not run, for the same reason as
    # the memories check above.
    runner_tools = load_runner()
    captured_claude = {}

    def capture_claude_command(command, *arguments, **keywords):
        captured_claude["command"] = list(command)
        # A non-empty stdout, so the chain's first model counts as having
        # produced a review and the capture holds one invocation rather than
        # the last model's after a fallback.
        return subprocess.CompletedProcess(list(command), 0, "a review\n", "")

    real_claude_run = agent_binary_launch_a_case_replaces(runner_tools)
    try:
        runner_tools.run_agent_binary_unless_run_stopped = capture_claude_command
        runner_tools.run_claude("a prompt no model ever sees")
    finally:
        runner_tools.run_agent_binary_unless_run_stopped = real_claude_run
    claude_command = captured_claude.get("command", [])
    allowed_tools = (claude_command[claude_command.index("--allowedTools") + 1]
                     if "--allowedTools" in claude_command else "")
    check("run_claude launches claude with Write in the tool set",
          "Write" in allowed_tools.split(","),
          f"allowed tools were {allowed_tools!r}")
    check("the reading tools a review cell needs are still in the tool set",
          {"Read", "Grep", "Glob"} <= set(allowed_tools.split(",")),
          f"allowed tools were {allowed_tools!r}")
    # And with user settings only, so this repository's Stop hooks cannot
    # speak inside a cell and displace its review (nedschorus#397).
    check("run_claude launches claude with --setting-sources user",
          ("--setting-sources", "user") in list(zip(claude_command, claude_command[1:])),
          f"composed command was {claude_command}")

    # The claude runtime's model chain. Fable 5 is obsolete (user, 2026-09-04)
    # and Fable is sometimes unavailable (user, 2026-09-11: "sometimes fable is
    # not available, so it should fall back to opus in that case"), so the cell
    # tries Fable 5.1 and falls back to Opus 5. The three ways an attempt can
    # produce no review are the house chain's (run_model_chain in
    # nc-systems/cold-read/cold-read-cell-common.py). No model is called: the
    # launch is replaced for the length of these cases and answers per model.
    runner_chain = load_runner()
    fable, opus = runner_chain.CLAUDE_MODEL_CHAIN
    check("the chain is Fable 5.1 then Opus 5, and Opus ends it",
          runner_chain.CLAUDE_MODEL_CHAIN == ("claude-fable-5-1", "claude-opus-5"),
          runner_chain.CLAUDE_MODEL_CHAIN)

    def answering(answers):
        """A launch stand-in answering per model: (returncode, stdout)."""
        def fake_run(command, *arguments, **keywords):
            model = command[command.index("--model") + 1]
            code, out = answers[model]
            return subprocess.CompletedProcess(list(command), code, out, "")
        return fake_run

    real_chain_run = agent_binary_launch_a_case_replaces(runner_chain)
    try:
        runner_chain.run_agent_binary_unless_run_stopped = answering({fable: (0, "fable's review\n")})
        answered = runner_chain.run_claude("a prompt no model ever sees")
        check("the chain runs Fable first, and does not fall back when it answers",
              answered == (0, "fable's review\n", fable, "", None), answered)

        runner_chain.run_agent_binary_unless_run_stopped = answering(
            {fable: (1, ""), opus: (0, "opus's review\n")})
        code, output, model, fallback_from, cause = runner_chain.run_claude("a prompt")
        check("a Fable that exits non-zero falls back to Opus, which is named as the model",
              (code, output, model) == (0, "opus's review\n", opus)
              and fallback_from == f"{fable}(exit1)" and cause is None,
              (code, output, model, fallback_from, cause))

        runner_chain.run_agent_binary_unless_run_stopped = answering(
            {fable: (0, "   \n"), opus: (0, "opus's review\n")})
        code, output, model, fallback_from, cause = runner_chain.run_claude("a prompt")
        check("a Fable that exits 0 having written no review falls back too",
              (code, model) == (0, opus)
              and fallback_from == f"{fable}(no-report)",
              (code, model, fallback_from))

        runner_chain.run_agent_binary_unless_run_stopped = answering({fable: (1, ""), opus: (1, "")})
        code, output, model, fallback_from, cause = runner_chain.run_claude("a prompt")
        check("every model failing fails the cell, and both attempts are named",
              code != 0 and output == ""
              and fallback_from == f"{fable}(exit1)+{opus}(exit1)",
              (code, output, fallback_from))
        check("and the failed chain carries the cause of its last attempt",
              cause == ("exit-1", "no output"), cause)

        # A failed attempt keeps the runtime's own words. A CLI that is logged
        # out or out of credits explains itself on one of its streams and
        # nowhere else, and the chain CONTINUES past the failure -- so without
        # this the run saves a report and its whole account of the broken CLI
        # is one "failed (exit 1)" line. Both streams, because the claude CLI
        # has used either for its refusals.
        def explaining(command, *arguments, **keywords):
            model = command[command.index("--model") + 1]
            if model == fable:
                return subprocess.CompletedProcess(
                    list(command), 1, "Credit balance is too low\n",
                    "Invalid API key - run /login\n")
            return subprocess.CompletedProcess(list(command), 0, "opus's review\n", "")

        runner_chain.run_agent_binary_unless_run_stopped = explaining
        spoken = io.StringIO()
        with contextlib.redirect_stdout(spoken):
            code, output, model, fallback_from, cause = runner_chain.run_claude("a prompt")
        said = spoken.getvalue()
        check("a failed attempt re-emits the runtime's stderr, not just the exit code",
              "Invalid API key" in said, said)
        check("and the stdout it failed with, where a CLI puts its reason instead",
              "Credit balance is too low" in said, said)
        check("the cell still falls back, and the review is returned, never printed",
              (code, output, model) == (0, "opus's review\n", opus)
              and "opus's review" not in said, (code, output, model, said))
    finally:
        runner_chain.run_agent_binary_unless_run_stopped = real_chain_run

    # The report's provenance names the model that actually wrote it and what
    # it fell back from, the way the cold-read cells' stamp does.
    #
    # The cache is primed first because provenance_line asks
    # runtime_cli_version for a value, and an empty cache makes that launch the
    # machine's real `claude --version` and `codex --version`: a unit case
    # reaching out to whatever happens to be installed, and waiting on it. The
    # cli= case further down primes it for the same reason. subprocess.run is
    # then pinned to raise, so an edit that reintroduces the probe fails here
    # instead of silently shelling out again.
    runner_chain.CLI_VERSION_CACHE.update({"claude": "1.1.1-test", "codex": "2.2.2-test"})

    def no_cli_launch_here(command, *arguments, **keywords):
        raise AssertionError(f"a provenance case launched {list(command)}")

    real_version_probe_run = runner_chain.subprocess.run
    runner_chain.subprocess.run = no_cli_launch_here
    try:
        fell_back = runner_chain.provenance_line(
            "claude", "claude-opus-5", "cut", "docs/x.md", False, "commit=abc1234",
            "claude-fable-5-1(exit1)")
        straight_through = runner_chain.provenance_line(
            "codex", "gpt-5.6-sol", "cut", "docs/x.md", False, "commit=abc1234")
    finally:
        runner_chain.subprocess.run = real_version_probe_run
    check("the provenance line records the model that answered and the fallback",
          "model=claude-opus-5 " in fell_back
          and "fallback_from=claude-fable-5-1(exit1) " in fell_back, fell_back)
    check("a cell that did not fall back carries no fallback_from field",
          "fallback_from=" not in straight_through, straight_through)
    check("and neither line launched a CLI: both versions came from the cache",
          "cli=1.1.1-test" in fell_back and "cli=2.2.2-test" in straight_through,
          (fell_back, straight_through))

    # The provenance line carries the CLI version the RUNNER measured —
    # nedschorus#161's cross-version fact rested on the cells' own words.
    runner_cli = load_runner()
    real_run = runner_cli.subprocess.run

    def fake_version_run(command, *arguments, **keywords):
        return subprocess.CompletedProcess(
            list(command), 0, "9.9.9 (Test CLI)\n", "")

    try:
        runner_cli.subprocess.run = fake_version_run
        measured = runner_cli.runtime_cli_version("claude")
    finally:
        runner_cli.subprocess.run = real_run
    check("the CLI version is measured from the binary, spaces hyphenated",
          measured == "9.9.9-(Test-CLI)", f"measured {measured!r}")
    check("the measured version is cached per runtime",
          runner_cli.CLI_VERSION_CACHE.get("claude") == "9.9.9-(Test-CLI)",
          runner_cli.CLI_VERSION_CACHE)

    def failing_version_run(command, *arguments, **keywords):
        raise OSError("no such binary")

    runner_cli.CLI_VERSION_CACHE.clear()
    try:
        runner_cli.subprocess.run = failing_version_run
        measured = runner_cli.runtime_cli_version("codex")
    finally:
        runner_cli.subprocess.run = real_run
    check("a failed version probe answers unknown, never raises",
          measured == "unknown", f"measured {measured!r}")

    runner_cli.CLI_VERSION_CACHE["claude"] = "7.7.7-test"
    line = runner_cli.provenance_line(
        "claude", "some-model", "cut", "docs/x.md", False,
        "commit=abc worktree=clean")
    check("the provenance line carries cli= alongside the existing facts",
          "cli=7.7.7-test" in line and "runtime=claude" in line
          and "model=some-model" in line and "attack=cut" in line
          and "target=docs/x.md" in line and "worktree=clean" in line,
          line)

    # --- The record reaches the log-store by program (nedschorus#392) ---------
    # The runner calls scripts/sanity-check-record-ship.py when a run ends and
    # prints its one line. The shipper's own behaviour is its suite's; what is
    # pinned here is that the runner reports the outcome and never raises on it,
    # because a sanity check that found something has found it whether or not
    # ned-box was reachable.
    runner_ship = load_runner()
    real_ship_run = runner_ship.subprocess.run
    shipper_calls = []

    class ShipperResult:
        def __init__(self, returncode, stdout, stderr=""):
            self.returncode, self.stdout, self.stderr = returncode, stdout, stderr

    try:
        def fake_run(command, **kwargs):
            shipper_calls.append(command)
            return ShipperResult(0, "shipped: 2026-09-17-design — 3 file(s) added to "
                                    "nedlern@ned-box:/home/nedlern/nedschorus-logs/"
                                    "sanity-check-records/2026-09-17-design\n")
        runner_ship.subprocess.run = fake_run
        line = runner_ship.ship_record(pathlib.Path("sanity-check-records/2026-09-17-design"))
        check("the runner runs the sanity-check shipper on the record it just wrote",
              shipper_calls
              and str(runner_ship.RECORD_SHIPPER) in [str(part) for part in shipper_calls[0]]
              and "sanity-check-record-ship.py" in str(runner_ship.RECORD_SHIPPER),
              shipper_calls)
        check("and returns the shipper's own line to print",
              line.startswith("shipped: 2026-09-17-design"), line)

        def silent_run(command, **kwargs):
            return ShipperResult(1, "", "boom\n")
        runner_ship.subprocess.run = silent_run
        line = runner_ship.ship_record(pathlib.Path("sanity-check-records/2026-09-17-design"))
        check("a shipper that printed nothing is reported as FAILED, not raised",
              line.startswith("FAILED") and "stays on disk" in line, line)

        def cannot_run(command, **kwargs):
            raise OSError("no such file")
        runner_ship.subprocess.run = cannot_run
        line = runner_ship.ship_record(pathlib.Path("sanity-check-records/2026-09-17-design"))
        check("a shipper that could not be run at all is reported, not raised",
              line.startswith("FAILED") and "could not be run" in line, line)
    finally:
        runner_ship.subprocess.run = real_ship_run

    # The end of a run that wrote reports: the record goes to the store, and
    # the closing line tells the requesting agent to keep it and to ship again
    # after the dispositions file, rather than to delete it as it once did.
    shipped_records = []
    completion = io.StringIO()
    record_dir = pathlib.Path("sanity-check-records/2026-09-17-design")
    with contextlib.redirect_stdout(completion):
        runner_ship.print_run_completion(
            record_dir,
            ship=lambda directory: shipped_records.append(directory) or "shipped: fine")
    said = completion.getvalue()
    check("the completion block ships the record it just wrote",
          shipped_records == [record_dir], shipped_records)
    check("and prints the shipper's line as `record:`",
          said.splitlines()[0] == "record: shipped: fine", said.splitlines()[:1])
    check("the closing line names the shipper for the dispositions round",
          "scripts/sanity-check-record-ship.py" in said and "finding-dispositions.md" in said,
          said)
    check("and says the record is kept, not deleted",
          "not deleted" in said and "Delete the record directory" not in said, said)
    run_source = inspect.getsource(getattr(runner_ship, "run_cells_in_review_copy", runner_ship.main))
    check("main ends a run that saved reports through that block",
          "print_run_completion(out_dir)" in run_source,
          "main no longer calls print_run_completion")

    # Cases 27-33 make the runner ready for use (GHI "Build sanity-checker",
    # nedschorus#412). Each fails against the runner as it stood before them.
    #
    # Case 27: the cells read a copy of the reviewed commit. Cells
    # used to read the live checkout for tens of minutes, so the requester
    # could change nothing while they ran, a cell's write landed in the
    # checkout (nedschorus#161), and a text edited mid-run was not the text
    # reviewed. The copy holds the commit, not the checkout's uncommitted
    # edits, and is gone when the run ends, a run that fails included. A git
    # write made in it — a branch, a stash — leaves the live repository's refs
    # and stash untouched: a `git worktree` shares both with the repository,
    # and the stash with every session's checkout. The copy keeps the live
    # repository's `origin/*` refs and its history, and names no remote that
    # leads back into the checkout.
    runner_copy = load_runner()
    review_copy_of_commit = getattr(runner_copy, "review_copy_of_commit", None)
    with tempfile.TemporaryDirectory() as scratch:
        base = pathlib.Path(scratch)
        repo = base / "repo"
        repo.mkdir()
        new_repo(repo)
        commit = git(repo, "rev-parse", "HEAD").strip()
        (repo / "tracked.md").write_text("an uncommitted edit\n", encoding="utf-8")
        runner_copy.REVIEW_COPIES_ROOT = base / "review-copies"
        seen = {}
        if review_copy_of_commit is None:
            check("the runner makes a review copy of the reviewed commit", False,
                  "the runner has no review_copy_of_commit")
        else:
            with review_copy_of_commit(commit, "2026-09-30-tracked", repo) as checkout:
                seen["text"] = (checkout / "tracked.md").read_text(encoding="utf-8")
                seen["head"] = git(checkout, "rev-parse", "HEAD").strip()
                seen["path"] = checkout
            check("the review copy holds the reviewed commit's text, not the "
                  "checkout's uncommitted edit",
                  seen["text"] == "original\n" and seen["head"] == commit,
                  f"copy read {seen['text']!r} at {seen['head']}, commit {commit}")
            check("and the copy is gone, from disk and from git's worktree list, "
                  "when the run ends",
                  not seen["path"].exists()
                  and str(seen["path"]) not in git(repo, "worktree", "list"),
                  git(repo, "worktree", "list"))
            git(repo, "update-ref", "refs/remotes/origin/main", commit)
            live_refs = git(repo, "for-each-ref")
            live_stash = git(repo, "stash", "list")
            with review_copy_of_commit(commit, "2026-09-30-tracked", repo) as checkout:
                (checkout / "tracked.md").write_text("a cell's edit\n", encoding="utf-8")
                git(checkout, "checkout", "-q", "-b", "a-branch-a-cell-made")
                git(checkout, "-c", "user.email=test@example.com", "-c", "user.name=test",
                    "stash", "push", "-q", "-m", "a-stash-a-cell-made")
                seen["origin-main"] = subprocess.run(
                    ["git", "-C", str(checkout), "rev-parse", "--verify", "-q",
                     "origin/main"], capture_output=True, text=True,
                    check=False).stdout.strip()
                seen["remotes"] = git(checkout, "remote", "-v")
            check("a branch and a stash made in the copy leave the live "
                  "repository's refs and stash untouched",
                  git(repo, "for-each-ref") == live_refs
                  and git(repo, "stash", "list") == live_stash,
                  f"refs now {git(repo, 'for-each-ref')!r}, "
                  f"stash now {git(repo, 'stash', 'list')!r}")
            check("the copy keeps the live repository's origin/main and names no "
                  "remote leading back into the checkout",
                  seen["origin-main"] == commit and str(repo) not in seen["remotes"],
                  f"origin/main {seen['origin-main']}, remotes {seen['remotes']!r}")
            try:
                with review_copy_of_commit(commit, "2026-09-30-tracked", repo) as checkout:
                    seen["failed-run"] = checkout
                    raise RuntimeError("a run that fails partway")
            except RuntimeError:
                pass
            check("and gone when the run fails partway",
                  not seen["failed-run"].exists()
                  and str(seen["failed-run"]) not in git(repo, "worktree", "list"),
                  git(repo, "worktree", "list"))

    # Case 28: both runtimes launch in the copy handed to them. claude takes it
    # as its working directory; codex takes it as `-C`, which is also the root
    # its profile lets it write under. Commands are captured, never run.
    runner_launch = load_runner()
    launches = []

    def capture_launch(command, *arguments, **keywords):
        launches.append((list(command), keywords.get("cwd")))
        return subprocess.CompletedProcess(list(command), 0, "a review\n", "")

    review_checkout = pathlib.Path("/a/review/copy/of/the/commit")
    real_launch_run = agent_binary_launch_a_case_replaces(runner_launch)
    # On Linux the codex cell's profile lists the credential files under the
    # home by running `find` there: emptied, so the real home is not scanned.
    real_launch_files_found = runner_launch.common.credential_files_found_now
    launch_error = None
    try:
        runner_launch.run_agent_binary_unless_run_stopped = capture_launch
        runner_launch.common.credential_files_found_now = lambda: []
        runner_launch.run_claude("a prompt no model ever sees", review_checkout)
        runner_launch.run_codex("a prompt no model ever sees", review_checkout)
    except TypeError as error:
        launch_error = error
    finally:
        runner_launch.run_agent_binary_unless_run_stopped = real_launch_run
        runner_launch.common.credential_files_found_now = real_launch_files_found
    claude_launches = [cwd for command, cwd in launches if command[0] == "claude"]
    codex_commands = [command for command, _ in launches if command[0] == "codex"]
    check("a claude cell runs in the review copy it is handed",
          launch_error is None and claude_launches == [review_checkout],
          f"error {launch_error!r}, claude working directories {claude_launches}")
    check("a codex cell runs in the review copy it is handed",
          launch_error is None and len(codex_commands) == 1
          and codex_commands[0][codex_commands[0].index("-C") + 1] == str(review_checkout),
          f"error {launch_error!r}, codex commands {codex_commands}")

    # Cases 29-33 drive main() over a scratch repository with the runtimes
    # replaced, so no model is called. A text carrying every attack's required
    # phrases stands in for a report of any attack.
    any_attack_report = (
        "## Questions\n\nNone.\n\n## Leanness certification\n\n- all of it\n\n"
        "## Prompts-to-code table\n\nNone.\n\n## Coverage\n\nAll of it.\n\n"
        "## Sketch\n\nA sketch.\n\n## Hard parts\n\nNone.\n\n"
        "## Late discoveries\n\nNone.\n\n## Assumptions\n\nNone.\n\n"
        "## What I consulted\n\nNothing off-limits.\n")

    def scratch_repository_with_design(base, target="docs/design.md"):
        repo = base / "repo"
        repo.mkdir()
        new_repo(repo)
        (repo / ".gitignore").write_text("sanity-check-records/\n", encoding="utf-8")
        (repo / target).parent.mkdir(parents=True, exist_ok=True)
        (repo / target).write_text(
            "# Design\n\nThe `widget-frobnicator` runs nightly.\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "the design")
        return repo

    def runner_over(repo, base):
        driven = load_runner()
        driven.REPO_ROOT = repo
        driven.RECORDS_ROOT = repo / "sanity-check-records"
        driven.REVIEW_COPIES_ROOT = base / "review-copies"
        driven.CLI_VERSION_CACHE.update({"claude": "1.1.1-test", "codex": "2.2.2-test"})
        return driven

    def drive_main(driven, arguments):
        """main()'s exit code, stdout and stderr; SystemExit is an exit code."""
        out, err = io.StringIO(), io.StringIO()
        saved_argv = sys.argv
        sys.argv = [str(RUNNER_SCRIPT), *arguments]
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                try:
                    code = driven.main()
                except SystemExit as exit_:
                    code = exit_.code
        finally:
            sys.argv = saved_argv
        return code, out.getvalue(), err.getvalue()

    # Case 29: a whole run with the copy. One claude cell leaves a stray file
    # in the checkout it was given and a note in the scratch directory its
    # prompt names; meanwhile the requester keeps editing the design in the
    # live checkout. The stray is reported as a write to the review copy; the
    # requester's edit is not a cell's write and is not reported; the note is
    # archived in the record; the copy is gone. Case 30 reads the same run.
    with tempfile.TemporaryDirectory() as scratch:
        base = pathlib.Path(scratch)
        repo = scratch_repository_with_design(base)
        request = base / "sanity-check-request.md"
        request.write_text("Problem: schedule nightly work.\n\n"
                           "Off-limits: the widget-frobnicator design.\n",
                           encoding="utf-8")
        driven = runner_over(repo, base)
        cell_checkouts = []

        def claude_cell(prompt, checkout=None):
            if checkout is not None:
                cell_checkouts.append(pathlib.Path(checkout))
                (pathlib.Path(checkout) / "stray-in-the-review-copy.md").write_text(
                    "a cell wrote this\n", encoding="utf-8")
            (repo / "docs" / "design.md").write_text(
                "# Design\n\nThe requester's next edit, made mid-run.\n",
                encoding="utf-8")
            for scratch_path in re.findall(r"(/\S+/scratch/[\w-]+)", prompt):
                note = pathlib.Path(scratch_path.rstrip(".`'\""))
                if note.is_dir():
                    (note / "notes.md").write_text("working notes\n", encoding="utf-8")
            return 0, any_attack_report, "a-test-model", ""

        driven.run_claude = claude_cell
        driven.run_codex = lambda prompt, checkout=None: (
            0, any_attack_report, "a-test-model", "")
        code, out, err = drive_main(driven, [
            "--target", "docs/design.md", "--attack", "cut", "--attack", "fresh-eyes",
            "--problem-statement", str(request)])
        records = sorted(driven.RECORDS_ROOT.glob("*"))
        record = records[0] if len(records) == 1 else None
        copy_warnings = [line for line in out.splitlines()
                         if line.startswith("WARNING: the review copy was modified")]
        check("a run over the copy exits 0 with every cell saved",
              code == 0 and out.count("saved: ") == 4,
              f"exit {code}, stdout {out!r}, stderr {err!r}")
        check("the cells ran in a copy, not in the live checkout",
              bool(cell_checkouts)
              and all(checkout != repo for checkout in cell_checkouts),
              f"cells ran in {cell_checkouts}")
        check("a cell's write in the copy is reported as a write to the review copy",
              any("stray-in-the-review-copy.md" in line for line in copy_warnings)
              and not (repo / "stray-in-the-review-copy.md").exists(),
              f"stdout {out!r}")
        check("the requester's own edit in the live checkout, made mid-run, is "
              "not reported as a cell's write",
              "docs/design.md" not in out, f"stdout {out!r}")
        notes = sorted(record.glob("scratch/*/notes.md")) if record else []
        check("the cells' scratch notes are archived in the record",
              [note.parent.name for note in notes]
              == ["cut-claude", "fresh-eyes-claude"],
              f"record {record}, notes {notes}")
        check("and the copy is gone when the run ends",
              not any((base / "review-copies").glob("*/*"))
              and git(repo, "worktree", "list").count("\n") == 1,
              f"left: {sorted((base / 'review-copies').glob('*/*'))}, "
              f"worktrees {git(repo, 'worktree', 'list')!r}")

        # Case 30: the run saves its own output and the request in its record,
        # so a later reader can see which warnings it printed and what the
        # fresh-eyes cells were asked; an agent used to copy both by hand. The
        # log holds what was printed before the record directory existed —
        # the LEAK-WARNING for the design's name in the request — and ends
        # before the record is shipped, so the copy in the log-store is whole
        # and a later ship of the dispositions file does not find it changed.
        run_log = record / "sanity-check-run.log" if record else None
        log_text = (run_log.read_text(encoding="utf-8")
                    if run_log and run_log.is_file() else "")
        check("the run's output is saved in the record as sanity-check-run.log",
              log_text.count("saved: ") == 4
              and "LEAK-WARNING: design name `widget-frobnicator`" in log_text,
              f"log was {log_text!r}")
        check("and the log ends before the record is shipped",
              bool(log_text) and "record: " not in log_text
              and "record: " in out, f"log was {log_text!r}")
        request_copy = record / "sanity-check-request.md" if record else None
        check("the request the fresh-eyes cells were given is saved in the record",
              request_copy is not None and request_copy.is_file()
              and request_copy.read_text(encoding="utf-8")
              == request.read_text(encoding="utf-8"),
              f"record held {sorted(p.name for p in record.iterdir()) if record else None}")

    # Case 31: a target or context document that differs from the last commit
    # is refused before any cell runs: the copy holds the commit, so the cells
    # would review a text the requester did not mean.
    for label, edit, arguments in (
            ("an edited target",
             lambda repo: (repo / "docs" / "design.md").write_text(
                 "# Design\n\nAn uncommitted edit.\n", encoding="utf-8"),
             ["--target", "docs/design.md", "--attack", "cut"]),
            ("an untracked context document",
             lambda repo: (repo / "docs" / "context.md").write_text(
                 "context\n", encoding="utf-8"),
             ["--target", "docs/design.md", "--context", "docs/context.md",
              "--attack", "cut"])):
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            repo = scratch_repository_with_design(base)
            edit(repo)
            driven = runner_over(repo, base)
            launched = []
            driven.run_claude = lambda prompt, checkout=None: (
                launched.append("claude") or (0, any_attack_report, "a-test-model", ""))
            driven.run_codex = lambda prompt, checkout=None: (
                launched.append("codex") or (0, any_attack_report, "a-test-model", ""))
            code, out, err = drive_main(driven, arguments)
            check(f"{label} is refused, exit 2, with no cell launched and no record",
                  code == 2 and launched == []
                  and not driven.RECORDS_ROOT.exists()
                  and "commit it" in err,
                  f"exit {code}, launched {launched}, stderr {err!r}")

    # Case 32: a curly apostrophe or quotation mark in a cell's quote matches
    # the straight one in the source. One run's replay found 16 of 24 "quote
    # found in no tracked file" warnings were a curly apostrophe against the
    # document's straight one (nedschorus#412, item 4).
    runner_curly = load_runner()
    corpus = (runner_curly.normalized_for_quote_match(
        "the runner doesn't save its 'own' log anywhere"),)
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        runner_curly.quote_scan(
            corpus, "It says “the runner doesn’t save its ‘own’ log”.",
            "q3")
    check("a quote differing from its source only in curly quotes raises no warning",
          buffer.getvalue() == "", f"output was {buffer.getvalue()!r}")

    # Case 33: a LEAK-WARNING names the line it matched, so an expected hit on
    # the request's off-limits list is told from a real leak without searching
    # the file by hand (22 warnings in one run each named only the file).
    runner_leak = load_runner()
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        runner_leak.leak_scan({"widget-frobnicator"},
                              "Problem: schedule nightly work.\n"
                              "Off-limits: the widget-frobnicator design.\n",
                              "the problem statement (request.md)")
    check("a LEAK-WARNING names the line number and text it matched",
          "line 2: Off-limits: the widget-frobnicator design." in buffer.getvalue(),
          f"output was {buffer.getvalue()!r}")

    # Case 34: `--runtime` reruns one runtime; the other's cells do not launch.
    # A rerun used to repeat both. The target is a skill, and every skill's
    # file is SKILL.md, so its record is named for the skill's directory too:
    # two skills checked on one day no longer share a stem.
    with tempfile.TemporaryDirectory() as scratch:
        base = pathlib.Path(scratch)
        repo = scratch_repository_with_design(base, ".claude/skills/widget/SKILL.md")
        driven = runner_over(repo, base)
        launched = []
        driven.run_claude = lambda prompt, checkout=None: (
            launched.append("claude") or (0, any_attack_report, "a-test-model", ""))
        driven.run_codex = lambda prompt, checkout=None: (
            launched.append("codex") or (0, any_attack_report, "a-test-model", ""))
        code, out, err = drive_main(driven, [
            "--target", ".claude/skills/widget/SKILL.md", "--attack", "cut",
            "--runtime", "codex"])
        records = [path.name for path in driven.RECORDS_ROOT.glob("*")]
        check("--runtime codex launches only the codex cell",
              code == 0 and launched == ["codex"] and "cut-claude" not in out,
              f"exit {code}, launched {launched}, stderr {err!r}")
        check("a skill's record is named for its directory, not SKILL alone",
              len(records) == 1 and records[0].endswith("-widget-SKILL"),
              f"records {records}")

    # Case 35: the cells are given each document by its repository-relative
    # path, whatever form it was passed in. An absolute path inside the
    # checkout used to pass every check and reach the prompt as given, so the
    # cells read the requester's live file and not the copy's (a cold read of
    # the skill found it, 2026-10-01). The scratch repository is reached here
    # through the temporary directory's own name, which on macOS is a symbolic
    # link, so the absolute forms below do not start with the resolved root.
    with tempfile.TemporaryDirectory() as scratch:
        base = pathlib.Path(scratch)
        repo = scratch_repository_with_design(base)
        (repo / "docs" / "context.md").write_text("context\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "a context document")
        driven = runner_over(repo, base)
        prompts = []

        def capturing_cell(prompt, checkout=None):
            prompts.append(prompt)
            return 0, any_attack_report, "a-test-model", ""

        driven.run_claude = capturing_cell
        driven.run_codex = capturing_cell
        absolute_target = str(repo / "docs" / "design.md")
        absolute_context = str(repo / "docs" / "context.md")
        code, out, err = drive_main(driven, [
            "--print", "cut", "--target", absolute_target,
            "--context", absolute_context])
        check("--print names an absolute target and context repository-relative",
              code == 0 and "Document under review: `docs/design.md`" in out
              and "- docs/context.md" in out
              and str(repo / "docs") not in out
              and str(repo.resolve() / "docs") not in out,
              f"exit {code}, request {out[-300:]!r}, stderr {err!r}")
        code, out, err = drive_main(driven, [
            "--print", "cut", "--target", "docs/../docs/./design.md"])
        check("--print folds the `..` and `.` segments of a relative target",
              code == 0 and "Document under review: `docs/design.md`" in out,
              f"exit {code}, request {out[-200:]!r}, stderr {err!r}")
        (repo / "docs" / "alias.md").symlink_to("design.md")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "a link inside the checkout")
        code, out, err = drive_main(driven, [
            "--print", "cut", "--target", "docs/alias.md"])
        check("--print names a symbolic link inside the checkout by the file "
              "it leads to",
              code == 0 and "Document under review: `docs/design.md`" in out,
              f"exit {code}, request {out[-200:]!r}, stderr {err!r}")
        code, out, err = drive_main(driven, [
            "--target", absolute_target, "--context", absolute_context,
            "--attack", "cut", "--runtime", "claude"])
        records = sorted(driven.RECORDS_ROOT.glob("*"))
        report = (records[0] / "cut-claude.md").read_text(encoding="utf-8") \
            if len(records) == 1 and (records[0] / "cut-claude.md").is_file() else ""
        check("a run given absolute paths hands the cell the repository-relative "
              "names and never the live checkout's path",
              code == 0 and len(prompts) == 1
              and "Document under review: `docs/design.md`" in prompts[0]
              and "- docs/context.md" in prompts[0]
              and absolute_target not in prompts[0]
              and str(repo.resolve() / "docs") not in prompts[0],
              f"exit {code}, prompts {[prompt[-300:] for prompt in prompts]!r}, "
              f"stderr {err!r}")
        check("and the report's provenance line and the record's name take the "
              "repository-relative name too",
              " target=docs/design.md " in report.partition("\n")[0]
              and len(records) == 1 and records[0].name.endswith("-design"),
              f"records {[record.name for record in records]}, "
              f"provenance {report.partition(chr(10))[0]!r}")

    # Case 36: an absolute target with an uncommitted edit is still refused,
    # and the refusal names the repository-relative path: the rewrite comes
    # before the uncommitted-changes check, not after it.
    with tempfile.TemporaryDirectory() as scratch:
        base = pathlib.Path(scratch)
        repo = scratch_repository_with_design(base)
        (repo / "docs" / "design.md").write_text(
            "# Design\n\nAn uncommitted edit.\n", encoding="utf-8")
        driven = runner_over(repo, base)
        launched = []
        driven.run_claude = lambda prompt, checkout=None: (
            launched.append("claude") or (0, any_attack_report, "a-test-model", ""))
        driven.run_codex = lambda prompt, checkout=None: (
            launched.append("codex") or (0, any_attack_report, "a-test-model", ""))
        code, out, err = drive_main(driven, [
            "--target", str(repo / "docs" / "design.md"), "--attack", "cut"])
        check("an edited target passed as an absolute path is refused under its "
              "repository-relative name",
              code == 2 and launched == [] and not driven.RECORDS_ROOT.exists()
              and err.startswith("docs/design.md differs from the last commit"),
              f"exit {code}, launched {launched}, stderr {err!r}")

    # Case 37: a path that resolves outside the checkout has no name in the
    # copy and is refused before any cell runs, whichever way it leaves: `..`
    # segments, an absolute path, or a tracked symbolic link. The refusal says
    # what to pass; it used to say "commit it", which no commit could satisfy.
    def outside_file(repo):
        (repo.parent / "outside.md").write_text("outside\n", encoding="utf-8")

    def tracked_link_to_outside_file(repo):
        outside_file(repo)
        (repo / "docs" / "link.md").symlink_to(repo.parent / "outside.md")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "a link out of the checkout")

    for label, prepare, arguments in (
            ("a relative target that climbs out of the checkout", outside_file,
             lambda repo: ["--target", "../outside.md", "--attack", "cut"]),
            ("an absolute target outside the checkout", outside_file,
             lambda repo: ["--target", str(repo.parent / "outside.md"),
                           "--attack", "cut"]),
            ("a context document outside the checkout", outside_file,
             lambda repo: ["--target", "docs/design.md",
                           "--context", str(repo.parent / "outside.md"),
                           "--attack", "cut"]),
            ("a tracked symbolic link that leads out of the checkout",
             tracked_link_to_outside_file,
             lambda repo: ["--target", "docs/link.md", "--attack", "cut"])):
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            repo = scratch_repository_with_design(base)
            prepare(repo)
            driven = runner_over(repo, base)
            launched = []
            driven.run_claude = lambda prompt, checkout=None: (
                launched.append("claude") or (0, any_attack_report, "a-test-model", ""))
            driven.run_codex = lambda prompt, checkout=None: (
                launched.append("codex") or (0, any_attack_report, "a-test-model", ""))
            code, out, err = drive_main(driven, arguments(repo))
            check(f"{label} is refused, exit 2, with no cell launched and no record",
                  code == 2 and launched == []
                  and not driven.RECORDS_ROOT.exists()
                  and "resolves outside this checkout" in err
                  and "pass a file inside it" in err and "commit it" not in err,
                  f"exit {code}, launched {launched}, stderr {err!r}")
            code, out, err = drive_main(driven, ["--print", "cut", *arguments(repo)[:-2]])
            check(f"and --print refuses {label} the same way",
                  code == 2 and out == "" and "resolves outside this checkout" in err,
                  f"exit {code}, stdout {out[-200:]!r}, stderr {err!r}")

    # Cases 38 to 43: a cell that saves no report is launched once more by the
    # runner, unless only the user can clear the cause or the launch timed out,
    # and a cell that ends with no report prints, under its FAILED line, what
    # the requesting agent does next (user-ruled 2026-10-01, walk
    # SKILL-sanity-check-2026-09-30-2, item 2). The skill used to tell the
    # agent to rerun a failed cell once whatever the cause; the user asked
    # "doesn't it matter why a cell fails?" and then said "I don't think the
    # agents will magically know when to rerun", so the decision is the
    # runner's. No model is called: the launchers, or the launch under them,
    # are replaced, and each stand-in counts its launches.
    capacity = "ERROR: Selected model is at capacity. Please try a different model."

    def run_cell_capturing(module, runtime, ledger=None, target="docs/x.md",
                           context=(), problem_statement=None):
        """(cell_ok, output, raised, out_dir's report text or None) for one
        cut cell run through run_cell in a temporary record directory."""
        buffer = io.StringIO()
        cell_ok, raised, report = None, None, None
        with tempfile.TemporaryDirectory() as scratch:
            out_dir = pathlib.Path(scratch)
            try:
                with contextlib.redirect_stdout(buffer):
                    _, cell_ok = module.run_cell(
                        "cut", runtime, target, list(context), problem_statement,
                        out_dir, {}, (), ledger or WritingStubLedger())
            except Exception as error:
                raised = error
            report_path = out_dir / f"cut-{runtime}.md"
            if report_path.is_file():
                report = report_path.read_text(encoding="utf-8")
        return cell_ok, buffer.getvalue(), raised, report

    def answering_in_turn(answers, prompts=None):
        """A launcher stand-in answering its launches in order, the last
        answer repeated; an answer that is an exception is raised."""
        launches = []

        def launcher(prompt, checkout=None):
            launches.append(prompt)
            answer = answers[min(len(launches), len(answers)) - 1]
            if isinstance(answer, BaseException):
                raise answer
            return answer
        launcher.launches = launches
        return launcher

    def with_launcher(module, launcher):
        module.run_claude = launcher
        module.run_codex = launcher
        return launcher

    def words_of_command(line):
        """A printed command as a shell would split it, or [] when it would not."""
        try:
            return shlex.split(line)
        except ValueError:
            return []

    def triage_lines(runtime):
        other = "codex" if runtime == "claude" else "claude"
        return (f"When a run of this sanity-check saved cut-{other}'s report, "
                f"triage the cut-attack from that report.\n"
                f"When no run of this sanity-check saved a report of the "
                f"cut-attack, write in finding-dispositions.md that the "
                f"cut-attack is unreviewed.\n")

    runner_relaunch = load_runner()
    runner_relaunch.CLI_VERSION_CACHE.update({"claude": "1.1.1-test",
                                              "codex": "2.2.2-test"})

    # Case 38: a failure that passes by itself. The one cold-read retry on
    # record is a codex cell whose first launch ended "Selected model is at
    # capacity" and whose identical relaunch saved its report
    # (SKILL-cold-read-2026-09-18-2). The second launch gets the same prompt,
    # so the same scratch directory, and the report it saves says in its
    # provenance line that it took two launches.
    for runtime in runner_relaunch.RUNTIMES:
        launcher = with_launcher(runner_relaunch, answering_in_turn([
            (1, "", "a-test-model", "", ("exit-1", capacity)),
            (0, cut_report, "a-test-model", "", None)]))
        cell_ok, output, raised, report = run_cell_capturing(runner_relaunch, runtime)
        retrying_line = f"RETRYING: cut-{runtime} — exit-1 — {capacity}\n"
        check(f"a {runtime} cell whose first launch fails is launched once more "
              f"and saves its report",
              raised is None and cell_ok is True and len(launcher.launches) == 2
              and report is not None and "saved: " in output
              and "FAILED:" not in output,
              f"raised={raised!r}, cell_ok={cell_ok}, "
              f"launches={len(launcher.launches)}, output was {output!r}")
        check(f"the {runtime} relaunch prints one RETRYING line naming the cause, "
              f"before the saved line, and it is not a WARNING",
              raised is None and output.count(retrying_line) == 1
              and output.index(retrying_line) < output.index("saved: ")
              and "WARNING" not in output,
              f"raised={raised!r}, output was {output!r}")
        check(f"the {runtime} relaunch gets the first launch's prompt",
              len(launcher.launches) == 2
              and launcher.launches[0] == launcher.launches[1],
              f"launches={len(launcher.launches)}")
        check(f"a {runtime} report saved on the relaunch says so in its provenance line",
              report is not None
              and " relaunched_after=exit-1 " in report.splitlines()[0]
              and cut_report in report,
              f"report began {(report or '')[:300]!r}")
    launcher = with_launcher(runner_relaunch, answering_in_turn([
        (0, cut_report, "a-test-model", "", None)]))
    cell_ok, output, raised, report = run_cell_capturing(runner_relaunch, "codex")
    check("a cell that saves on its first launch is launched once and carries "
          "no relaunched_after field",
          raised is None and cell_ok is True and len(launcher.launches) == 1
          and report is not None and "relaunched_after=" not in report
          and "RETRYING:" not in output,
          f"raised={raised!r}, launches={len(launcher.launches)}, output was {output!r}")

    # Case 39: the relaunch fails too. The cell is launched twice and no more,
    # its FAILED line carries the last launch's cause and says it was
    # relaunched, and the two lines under it send the agent to the other
    # runtime's report or, without one, to record the attack as unreviewed.
    # Neither line depends on which cell finished first. A launcher that
    # returns the four values of the older contract, with no cause, is
    # reported by its exit code.
    for runtime in runner_relaunch.RUNTIMES:
        attempts = "claude-fable-5-1(exit1)+claude-opus-5(exit1)" if runtime == "claude" else ""
        launcher = with_launcher(runner_relaunch, answering_in_turn([
            (1, "", "", attempts, ("exit-1", "first launch: overloaded")),
            (1, "", "", attempts, ("exit-1", capacity))]))
        cell_ok, output, raised, report = run_cell_capturing(runner_relaunch, runtime)
        tried = f" (models tried: {attempts})" if attempts else ""
        failed_block = (f"FAILED: cut-{runtime} — exit-1 — {capacity} "
                        f"(relaunched once){tried}\n" + triage_lines(runtime))
        check(f"a {runtime} cell whose relaunch fails too is launched twice and fails",
              raised is None and cell_ok is False and len(launcher.launches) == 2
              and report is None and "saved:" not in output,
              f"raised={raised!r}, cell_ok={cell_ok}, "
              f"launches={len(launcher.launches)}, output was {output!r}")
        check(f"its FAILED line carries the relaunch's cause, and the triage "
              f"instructions follow it directly ({runtime})",
              raised is None and output.endswith(failed_block)
              and output.count("FAILED:") == 1
              and output.count(f"RETRYING: cut-{runtime} — exit-1 — "
                               f"first launch: overloaded\n") == 1,
              f"raised={raised!r}, output was {output!r}")
    launcher = with_launcher(runner_relaunch, answering_in_turn([(3, "", "a-test-model", "")]))
    cell_ok, output, raised, report = run_cell_capturing(runner_relaunch, "codex")
    check("a launcher that names no cause is reported by its exit code",
          raised is None and cell_ok is False
          and "RETRYING: cut-codex — exit-3 — no output\n" in output
          and "FAILED: cut-codex — exit-3 — no output (relaunched once)\n" in output,
          f"raised={raised!r}, output was {output!r}")

    # The FAILED line and its instructions are one write: the cells print from
    # their own threads, and "the FAILED line above" must be the line above.
    class WriteRecordingStream(io.StringIO):
        def __init__(self):
            super().__init__()
            self.writes = []

        def write(self, text):
            self.writes.append(text)
            return super().write(text)

    with_launcher(runner_relaunch, answering_in_turn([
        (1, "", "a-test-model", "", ("logged-out", "Not logged in"))]))
    runner_relaunch.CELLS_FINISHED.clear()
    recording = WriteRecordingStream()
    with tempfile.TemporaryDirectory() as scratch:
        with contextlib.redirect_stdout(recording):
            runner_relaunch.run_cell("cut", "codex", "docs/x.md", [], None,
                                     pathlib.Path(scratch), {}, (), StubLedger([]))
    failed_writes = [text for text in recording.writes if "FAILED:" in text]
    check("a cell that ends on its FAILED lines is counted as finished, so a stop "
          "after it does not make the run a stopped run",
          "cut-codex" in runner_relaunch.CELLS_FINISHED,
          f"finished {runner_relaunch.CELLS_FINISHED!r}")
    check("a failed cell's FAILED line and its instructions are printed as one write",
          len(failed_writes) == 1 and failed_writes[0].count("\n") == 4
          and failed_writes[0].startswith("FAILED: cut-codex — logged-out — ")
          and failed_writes[0].endswith("--attack cut --runtime codex\n"),
          f"writes were {recording.writes!r}")

    # Case 40: a cause only the user can clear is not relaunched. A logged-out
    # CLI, a missing one and a usage limit fail a second launch the way they
    # failed the first, so the cell is launched once, and the lines under its
    # FAILED line tell the agent to tell the user and give the command that
    # runs this one cell again: this run's target, each context document and
    # the request, and the cell's attack and runtime as the only --attack and
    # --runtime, quoted so a shell takes the line as it stands.
    request_path = pathlib.Path("a request.md")
    for cause_class in sorted(runner_relaunch.common.USER_CLEARABLE_CAUSE_CLASSES):
        for runtime in runner_relaunch.RUNTIMES:
            launcher = with_launcher(runner_relaunch, answering_in_turn([
                (1, "", "", "", (cause_class, "the CLI's own line"))]))
            cell_ok, output, raised, report = run_cell_capturing(
                runner_relaunch, runtime, target="docs/a design.md",
                context=("docs/c.md", "docs/d's notes.md"),
                problem_statement=request_path)
            lines = output.splitlines()
            command = words_of_command(lines[-1]) if lines else []
            check(f"a {runtime} cell failing as {cause_class} is launched once, "
                  f"with no RETRYING line",
                  raised is None and cell_ok is False and len(launcher.launches) == 1
                  and "RETRYING:" not in output and report is None,
                  f"raised={raised!r}, cell_ok={cell_ok}, "
                  f"launches={len(launcher.launches)}, output was {output!r}")
            check(f"and its FAILED line is followed by the two instructions and "
                  f"the command ({cause_class}, {runtime})",
                  lines[-4:-1] == [
                      f"FAILED: cut-{runtime} — {cause_class} — the CLI's own line",
                      "Tell the user what the FAILED line above says.",
                      "After the user has cleared the cause, run the command on "
                      "the next line."],
                  f"output was {output!r}")
            check(f"and the command reruns that one cell with this run's documents "
                  f"({cause_class}, {runtime})",
                  command == [
                      str(RUNNER_SCRIPT.resolve()), "--target", "docs/a design.md",
                      "--context", "docs/c.md", "--context", "docs/d's notes.md",
                      "--problem-statement", str(request_path.resolve()),
                      "--attack", "cut", "--runtime", runtime],
                  f"command was {command}")
    with_launcher(runner_relaunch, answering_in_turn([
        (1, "", "", "", ("logged-out", "Not logged in"))]))
    cell_ok, output, raised, report = run_cell_capturing(runner_relaunch, "claude")
    check("a run with no request and no context documents prints a command without them",
          raised is None and words_of_command(output.splitlines()[-1]) == [
              str(RUNNER_SCRIPT.resolve()), "--target", "docs/x.md",
              "--attack", "cut", "--runtime", "claude"],
          f"raised={raised!r}, output was {output!r}")

    # The classes come from what each CLI really prints, through the real
    # launchers: the launch is replaced under them. The texts are the
    # captured ones kept beside the cold-read cells
    # (nc-systems/cold-read/cold-read-claude-cell.py and
    # cold-read-codex-cell.py, recognised_failure_texts_for_model).
    runner_classes = load_runner()
    real_classes_run = agent_binary_launch_a_case_replaces(runner_classes)
    # On Linux the codex cell's permission profile lists the credential files
    # under the home, which it finds by running `find` there: emptied for
    # these launches, as the launch-flag case above does, so the real home is
    # not scanned and the only command the stand-ins see is the CLI's.
    real_credential_files_found_now = runner_classes.common.credential_files_found_now
    runner_classes.common.credential_files_found_now = lambda: []
    codex_logged_out = ("2026-09-18T19:37:41.140816Z ERROR codex_api::endpoint::"
                        "responses_websocket: failed to connect to websocket: HTTP "
                        "error: 401 Unauthorized, url: wss://api.openai.com/v1/responses")
    codex_session = "".join(f"session line {number}\n" for number in range(60))
    launched_commands = []

    def cli_answering(code, stdout, stderr):
        """A launch stand-in for one CLI. A stream comes back only
        when the launcher piped it, as from the real function: a launcher
        that discards a stream never sees the cause written there."""
        def fake_run(command, *arguments, **keywords):
            launched_commands.append(list(command))
            return subprocess.CompletedProcess(
                list(command), code,
                stdout if keywords.get("stdout") == subprocess.PIPE else None,
                stderr if keywords.get("stderr") == subprocess.PIPE else None)
        return fake_run

    def cli_missing(command, *arguments, **keywords):
        launched_commands.append(list(command))
        raise FileNotFoundError(2, "No such file or directory", command[0])

    # Each row: the runtime, the class its text must be given, the stand-in,
    # a piece of the detail, and how many times one launch calls the CLI (the
    # claude chain calls it once per model).
    real_cases = (
        ("codex", "logged-out", cli_answering(1, "", codex_session + codex_logged_out + "\n"),
         codex_logged_out.split(" ", 1)[1], 1),
        ("codex", "exit-1", cli_answering(1, "", codex_session + capacity + "\n"),
         capacity, 1),
        ("codex", "agent-binary-missing", cli_missing, "No such file or directory", 1),
        ("claude", "logged-out",
         cli_answering(1, "Not logged in · Please run /login\n", ""),
         "Not logged in · Please run /login", 2),
        ("claude", "account-limit",
         cli_answering(1, "You've hit your session limit · resets 8:50pm "
                          "(America/Los_Angeles)\n", ""),
         "resets 8:50pm (America/Los_Angeles)", 2),
        ("claude", "model-limit",
         cli_answering(1, "You've reached your Opus limit. Switch to another "
                          "model, or manage usage credits, to continue.\n", ""),
         "Opus", 2),
        ("claude", "agent-binary-missing", cli_missing, "No such file or directory", 2),
    )
    try:
        for runtime, expected_class, fake_run, expected_detail, calls_per_launch in real_cases:
            del launched_commands[:]
            runner_classes.run_agent_binary_unless_run_stopped = fake_run
            cell_ok, output, raised, report = run_cell_capturing(
                runner_classes, runtime, ledger=StubLedger([]))
            failed = [line for line in output.splitlines() if line.startswith("FAILED:")]
            relaunched = expected_class not in runner_classes.common.USER_CLEARABLE_CAUSE_CLASSES
            check(f"a {runtime} CLI's own failure text is classed {expected_class} "
                  f"and {'relaunched once' if relaunched else 'not relaunched'}",
                  raised is None and cell_ok is False and len(failed) == 1
                  and failed[0].startswith(
                      f"FAILED: cut-{runtime} — {expected_class} — ")
                  and expected_detail in failed[0]
                  and ("(relaunched once)" in failed[0]) == relaunched
                  and (output.count("RETRYING:") == 1) == relaunched
                  and len(launched_commands) == calls_per_launch * (2 if relaunched else 1),
                  f"raised={raised!r}, launches={len(launched_commands)}, "
                  f"output was {output[-700:]!r}")
            if runtime == "codex" and expected_class == "logged-out":
                check("a failed codex launch prints the last 20 lines its CLI wrote, "
                      "not its whole session",
                      codex_logged_out in output and "session line 59\n" in output
                      and "session line 41\n" in output
                      and "session line 40\n" not in output,
                      f"output was {output[:400]!r}")
    finally:
        runner_classes.run_agent_binary_unless_run_stopped = real_classes_run
        runner_classes.common.credential_files_found_now = real_credential_files_found_now

    # Case 41: a timeout is not relaunched: the same launch would cost the
    # same hour. The triage instructions follow its FAILED line. A relaunch
    # that times out is reported as a timeout that was relaunched, and a codex
    # cell cut off after writing a long session prints only its last lines.
    def timed_out(stderr=None):
        return subprocess.TimeoutExpired(
            ["a-runtime"], runner_relaunch.CELL_TIMEOUT_SECONDS, output=None,
            stderr=stderr)

    timeout_text = f"timeout — after {runner_relaunch.CELL_TIMEOUT_SECONDS}s"
    for runtime in runner_relaunch.RUNTIMES:
        launcher = with_launcher(runner_relaunch, answering_in_turn([timed_out()]))
        cell_ok, output, raised, report = run_cell_capturing(runner_relaunch, runtime)
        check(f"a {runtime} cell that times out is launched once, and its FAILED "
              f"line is followed by the triage instructions",
              raised is None and cell_ok is False and len(launcher.launches) == 1
              and output == f"FAILED: cut-{runtime} — {timeout_text}\n" + triage_lines(runtime),
              f"raised={raised!r}, launches={len(launcher.launches)}, output was {output!r}")
    launcher = with_launcher(runner_relaunch, answering_in_turn([
        (1, "", "a-test-model", "", ("exit-1", capacity)), timed_out()]))
    cell_ok, output, raised, report = run_cell_capturing(runner_relaunch, "codex")
    check("a relaunch that times out is reported as a timeout that was relaunched",
          raised is None and cell_ok is False and len(launcher.launches) == 2
          and f"FAILED: cut-codex — {timeout_text} (relaunched once)\n" in output,
          f"raised={raised!r}, output was {output!r}")
    with_launcher(runner_relaunch, answering_in_turn([
        timed_out(stderr=codex_session.encode("utf-8") + b"cut off mid-sente")]))
    cell_ok, output, raised, report = run_cell_capturing(runner_relaunch, "codex")
    check("a codex cell that times out prints only the last 20 lines of its session",
          raised is None and "cut off mid-sente\n" in output
          and "session line 41\n" in output and "session line 40\n" not in output,
          f"raised={raised!r}, output was {output[:300]!r}")

    # Case 42: the claude chain across a relaunch. Both models fail in the
    # first launch; in the second the first model fails again and the second
    # answers. The report names the model that wrote it, the model the second
    # launch fell back from, and the first launch's cause; the RETRYING line
    # carries the cause of the chain's last attempt.
    runner_chain_relaunch = load_runner()
    runner_chain_relaunch.CLI_VERSION_CACHE.update({"claude": "1.1.1-test",
                                                    "codex": "2.2.2-test"})
    real_chain_relaunch_run = agent_binary_launch_a_case_replaces(runner_chain_relaunch)
    chain_calls = []

    def chain_across_a_relaunch(command, *arguments, **keywords):
        model = command[command.index("--model") + 1]
        chain_calls.append(model)
        if model == opus and len(chain_calls) == 4:
            return subprocess.CompletedProcess(list(command), 0, cut_report, "")
        return subprocess.CompletedProcess(
            list(command), 1, "", f"{model}: overloaded, call {len(chain_calls)}\n")

    try:
        runner_chain_relaunch.run_agent_binary_unless_run_stopped = chain_across_a_relaunch
        cell_ok, output, raised, report = run_cell_capturing(
            runner_chain_relaunch, "claude")
    finally:
        runner_chain_relaunch.run_agent_binary_unless_run_stopped = real_chain_relaunch_run
    stamp = (report or "").splitlines()[0] if report else ""
    check("a claude cell whose whole chain fails is relaunched, and the chain "
          "runs again from its first model",
          raised is None and cell_ok is True
          and chain_calls == [fable, opus, fable, opus],
          f"raised={raised!r}, cell_ok={cell_ok}, calls={chain_calls}, "
          f"output was {output!r}")
    check("its RETRYING line carries the cause of the chain's last attempt",
          output.count(f"RETRYING: cut-claude — exit-1 — {opus}: overloaded, "
                       f"call 2\n") == 1,
          f"output was {output!r}")
    check("and the saved report names its model, the fallback of the launch "
          "that saved it, and the first launch's cause",
          f" model={opus} " in stamp
          and f" fallback_from={fable}(exit1) " in stamp
          and " relaunched_after=exit-1 " in stamp,
          f"stamp was {stamp!r}")

    # Case 43: whole runs. A run limited to codex whose cell fails twice exits
    # 1 and prints the same two triage instructions, which name the other
    # runtime's report without assuming this run launched it: the rerun the
    # runner itself prints is a run of one runtime, and the other runtime's
    # report is then in the first run's record. Every line reaches the
    # record's log. Then a run of both runtimes whose codex cell is logged
    # out: the command under its FAILED line, run as printed, launches that
    # one cell and no other, into a record directory of its own.
    with tempfile.TemporaryDirectory() as scratch:
        base = pathlib.Path(scratch)
        repo = scratch_repository_with_design(base)
        (repo / "docs" / "context notes.md").write_text("# Notes\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "the notes")
        request = base / "sanity-check-request.md"
        request.write_text("Problem: schedule nightly work.\n", encoding="utf-8")
        driven = runner_over(repo, base)
        launched = []

        def codex_failing_twice(prompt, checkout=None):
            launched.append("codex")
            return 1, "", "a-test-model", "", ("exit-1", capacity)

        def claude_never(prompt, checkout=None):
            launched.append("claude")
            return 0, any_attack_report, "a-test-model", "", None

        driven.run_codex = codex_failing_twice
        driven.run_claude = claude_never
        code, out, err = drive_main(driven, [
            "--target", "docs/design.md", "--attack", "cut", "--runtime", "codex"])
        failed_block = (f"FAILED: cut-codex — exit-1 — {capacity} (relaunched once)\n"
                        + triage_lines("codex"))
        check("a run limited to codex whose cell fails twice exits 1 with the "
              "triage instructions and no report",
              code == 1 and launched == ["codex", "codex"] and failed_block in out
              and "saved: " not in out
              and "sanity-check wrote no reports" in out,
              f"exit {code}, launched {launched}, stdout {out!r}, stderr {err!r}")
        logs = sorted(driven.RECORDS_ROOT.glob("*/sanity-check-run.log"))
        log_text = logs[0].read_text(encoding="utf-8") if len(logs) == 1 else ""
        check("the RETRYING line, the FAILED line and its instructions are in "
              "the record's log",
              f"RETRYING: cut-codex — exit-1 — {capacity}\n" in log_text
              and failed_block in log_text,
              f"logs {logs}, log was {log_text!r}")

    with tempfile.TemporaryDirectory() as scratch:
        base = pathlib.Path(scratch)
        repo = scratch_repository_with_design(base)
        (repo / "docs" / "context notes.md").write_text("# Notes\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "the notes")
        request = base / "sanity-check-request.md"
        request.write_text("Problem: schedule nightly work.\n", encoding="utf-8")
        driven = runner_over(repo, base)
        launched = []
        mechanization_codex_logged_out = [True]

        def codex_logged_out_then_in(prompt, checkout=None):
            # The cell is told apart by the scratch directory its prompt names.
            launched.append("codex")
            if "scratch/mechanization-codex" in prompt and mechanization_codex_logged_out[0]:
                return 1, "", "a-test-model", "", ("logged-out", "401 Unauthorized")
            return 0, any_attack_report, "a-test-model", "", None

        def claude_reporting(prompt, checkout=None):
            launched.append("claude")
            return 0, any_attack_report, "a-test-model", "", None

        driven.run_codex = codex_logged_out_then_in
        driven.run_claude = claude_reporting
        code, out, err = drive_main(driven, [
            "--target", "docs/design.md", "--context", "docs/context notes.md",
            "--attack", "cut", "--attack", "fresh-eyes", "--attack", "mechanization",
            "--problem-statement", str(request), "--runtime", "claude",
            "--runtime", "codex"])
        out_lines = out.splitlines()
        failed_at = [index for index, line in enumerate(out_lines)
                     if line.startswith("FAILED: mechanization-codex — logged-out — ")]
        printed = out_lines[failed_at[0] + 3] if len(failed_at) == 1 else ""
        command = words_of_command(printed)
        check("a logged-out codex cell in a full run is launched once and prints "
              "the command that reruns it alone",
              code == 1 and launched.count("codex") == 3 and launched.count("claude") == 3
              and out.count("RETRYING:") == 0 and out.count("FAILED:") == 1
              and command == [
                  str(RUNNER_SCRIPT.resolve()), "--target", "docs/design.md",
                  "--context", "docs/context notes.md",
                  "--problem-statement", str(request.resolve()),
                  "--attack", "mechanization", "--runtime", "codex"],
              f"exit {code}, launched {launched}, command {command}, "
              f"stdout {out!r}, stderr {err!r}")
        del launched[:]
        mechanization_codex_logged_out[0] = False
        code, out, err = drive_main(driven, command[1:])
        records = sorted(path.name for path in driven.RECORDS_ROOT.glob("*"))
        check("that command, run as printed, launches the one cell and saves its "
              "report in a record directory of its own",
              code == 0 and launched == ["codex"] and out.count("saved: ") == 1
              and len(records) == 2 and records[1] == records[0] + "-2"
              and (driven.RECORDS_ROOT / records[1] / "mechanization-codex.md").is_file(),
              f"exit {code}, launched {launched}, records {records}, "
              f"stdout {out!r}, stderr {err!r}")

    # Cases 44 to 48 came from review of the pull request that introduced the
    # review copy (2026-10-01). Cases 44 to 46 run the runner as a real
    # process over a scratch repository, with stand-in `claude` and `codex`
    # programs first on its PATH, and send it real signals: a signal handler
    # and a lock the operating system drops with the process cannot be shown
    # by a replaced function. No model is called, and nothing is written
    # under the real ~/.cache: the driver below points the runner's roots at
    # the scratch directory, as runner_over does for the in-process cases.
    stand_in_source = f"""#!{sys.executable}
import os, pathlib, subprocess, sys, time
name = pathlib.Path(sys.argv[0]).name
directory = pathlib.Path(os.environ["STAND_IN_DIRECTORY"])
mode = os.environ.get("STAND_IN_" + name.upper() + "_MODE", "wait")
report = {any_attack_report!r}
if name == "claude":
    sys.stdin.read()
last_message = (sys.argv[sys.argv.index("--output-last-message") + 1]
                if "--output-last-message" in sys.argv else None)
if mode == "report":
    if last_message:
        pathlib.Path(last_message).write_text(report, encoding="utf-8")
    else:
        sys.stdout.write(report)
    sys.exit(0)
if mode == "bad-byte":
    sys.stderr.buffer.write(b"a byte that is not UTF-8: \\xff\\n")
    if last_message:
        pathlib.Path(last_message).write_bytes(report.encode("utf-8") + b"\\xff\\n")
    else:
        sys.stdout.buffer.write(report.encode("utf-8") + b"\\xff\\n")
    sys.exit(0)
if mode == "fail-once" and not (directory / (name + "-failed-once")).exists():
    # A first launch that fails for a cause the runner relaunches; every
    # later launch waits, as below.
    (directory / (name + "-failed-once")).write_text("", encoding="utf-8")
    sys.stderr.write("ERROR: Selected model is at capacity. Please try a different model.\\n")
    sys.exit(1)
# "wait": a launch that is still working when the run is stopped, with a
# process of its own under it, as an agent-binary has.
child = subprocess.Popen(["sleep", "300"])
(directory / (name + "-" + str(os.getpid()) + ".pids")).write_text(
    str(os.getpid()) + " " + str(child.pid) + "\\n", encoding="utf-8")
time.sleep(300)
"""

    def stand_in_agent_binaries(base):
        """A directory holding stand-in `claude` and `codex` programs, and the
        directory each waiting launch records its process ids in."""
        programs = base / "stand-in-bin"
        programs.mkdir()
        for name in ("claude", "codex"):
            (programs / name).write_text(stand_in_source, encoding="utf-8")
            (programs / name).chmod(0o755)
        recorded = base / "stand-in-pids"
        recorded.mkdir()
        return programs, recorded

    def runner_process_environment(programs, recorded, **modes):
        environment = dict(os.environ)
        tool_directories = [str(pathlib.Path(shutil.which(tool)).parent)
                            for tool in ("git", "ps", "sleep")]
        environment["PATH"] = os.pathsep.join(
            [str(programs), *dict.fromkeys(tool_directories), "/usr/bin", "/bin"])
        environment["STAND_IN_DIRECTORY"] = str(recorded)
        for name, mode in modes.items():
            environment[f"STAND_IN_{name.upper()}_MODE"] = mode
        return environment

    def runner_driver(base, repo):
        """A program that runs the runner's main() over `repo`, as runner_over
        does in-process: what a real run does, with the roots in scratch.

        The codex profile's credential list comes back empty, so on Linux the
        real home is not walked for credential files. Three environment
        variables, each naming a file, hold the run at one moment so a case
        can send its signal there: DRIVER_HOLD_CODEX_RELAUNCH holds a codex
        cell's second launch while its profile is built, after run_cell has
        read RUN_STOPPED unset, until that file exists (`<file>.held` says the
        hold has begun); DRIVER_STOP_WALK_DONE is written once the stop
        handler has stopped the processes under the runner;
        DRIVER_HOLD_FIRST_SHIP holds the first shipping of the record until a
        signal ends the hold (`<file>.held` again); and
        DRIVER_HOLD_LAST_REPORT_CHECK holds the second cell to finish, after
        its agent-binary has exited and before its report is saved, until that
        file exists (`<file>.held` again). DRIVER_PROBE_VERSIONS, set to any
        value, leaves the CLI version cache empty, so a cell probes the
        stand-in's `--version` as a real run does."""
        driver = base / "run-the-runner.py"
        driver.write_text(f"""
import importlib.util, os, pathlib, sys, time
spec = importlib.util.spec_from_file_location("sanity_check_attacks", {str(RUNNER_SCRIPT)!r})
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.REPO_ROOT = pathlib.Path({str(repo)!r})
module.RECORDS_ROOT = module.REPO_ROOT / "sanity-check-records"
module.REVIEW_COPIES_ROOT = pathlib.Path({str(base / "review-copies")!r})
if not os.environ.get("DRIVER_PROBE_VERSIONS"):
    module.CLI_VERSION_CACHE.update({{"claude": "1.1.1-test", "codex": "2.2.2-test"}})
module.common.credential_files_found_now = lambda: []
if hasattr(module, "STOPPED_PROCESS_GRACE_SECONDS"):
    module.STOPPED_PROCESS_GRACE_SECONDS = 3.0

def held_until(path):
    pathlib.Path(path + ".held").write_text("", encoding="utf-8")
    deadline = time.monotonic() + 60
    while not pathlib.Path(path).exists() and time.monotonic() < deadline:
        time.sleep(0.02)

relaunch_hold = os.environ.get("DRIVER_HOLD_CODEX_RELAUNCH")
if relaunch_hold:
    profile = module.common.codex_credential_denying_permission_profile_arguments
    profiles_built = []
    def profile_held_at_the_relaunch(*arguments, **keywords):
        profiles_built.append(1)
        if len(profiles_built) == 2:
            held_until(relaunch_hold)
        return profile(*arguments, **keywords)
    module.common.codex_credential_denying_permission_profile_arguments = profile_held_at_the_relaunch
walk_done = os.environ.get("DRIVER_STOP_WALK_DONE")
if walk_done:
    stop_processes = module.stop_processes_this_run_started
    def stop_processes_then_say_so():
        stop_processes()
        pathlib.Path(walk_done).write_text("", encoding="utf-8")
    module.stop_processes_this_run_started = stop_processes_then_say_so
report_check_hold = os.environ.get("DRIVER_HOLD_LAST_REPORT_CHECK")
if report_check_hold:
    check_report = module.missing_report_phrases
    reports_checked = []
    def last_report_check_held(*arguments, **keywords):
        reports_checked.append(1)
        if len(reports_checked) == 2:
            held_until(report_check_hold)
        return check_report(*arguments, **keywords)
    module.missing_report_phrases = last_report_check_held
ship_hold = os.environ.get("DRIVER_HOLD_FIRST_SHIP")
if ship_hold:
    ship = module.ship_record
    ships = []
    def first_ship_held(record_directory):
        ships.append(1)
        if len(ships) == 1:
            held_until(ship_hold)
        return ship(record_directory)
    module.ship_record = first_ship_held
sys.argv = [{str(RUNNER_SCRIPT)!r}, *sys.argv[1:]]
sys.exit(module.main())
""", encoding="utf-8")
        return driver

    def recorded_process_ids(recorded, name):
        """The (launch, child) process ids of each waiting `name` launch."""
        return [tuple(int(field) for field in path.read_text(encoding="utf-8").split())
                for path in sorted(recorded.glob(f"{name}-*.pids"))]

    def process_is_running(pid):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)],
                               capture_output=True, text=True, check=False)
        return bool(state.stdout.strip()) and not state.stdout.strip().startswith("Z")

    def wait_until(condition, seconds=30.0):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if condition():
                return True
            time.sleep(0.05)
        return condition()

    def end_stand_ins(recorded):
        """Whatever a case's stand-ins are still running, ended, so a failing
        case leaves no process behind."""
        for path in recorded.glob("*.pids"):
            for field in path.read_text(encoding="utf-8").split():
                try:
                    os.kill(int(field), signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass

    def left_in_copies_root(base):
        root = base / "review-copies"
        return sorted(path.name for path in root.iterdir()) if root.is_dir() else []

    # Case 44: SIGTERM, SIGHUP or SIGINT to the runner while a cell runs. The skill
    # starts the runner as a background task, and a seat's handoff ends
    # background tasks, so this is an ordinary ending. Before the handler the
    # runner died at once: the review copy, a whole checkout, stayed for good,
    # and the cells ran on with nobody to save what they wrote. Here the codex
    # cell has saved its report and the claude cell is still working, with a
    # process of its own under it, when the signal arrives at the runner
    # alone. Afterwards: the runner ended by that signal; the claude launch
    # and the process under it are gone; the copy is gone;
    # the report already saved, the cells' scratch directories and a log that
    # says what happened are in the record, which is shipped; and nothing was
    # relaunched. SIGINT here goes to the runner's process alone, which used
    # to make the runner wait for its cells, up to their timeout. Each run has
    # a target of its own, so its record's name is one no other case of this
    # suite has shipped to the scratch store.
    for stop_signal in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
        signal_name = stop_signal.name
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch).resolve()
            target = f"docs/stopped-by-{signal_name.lower()}.md"
            repo = scratch_repository_with_design(base, target)
            programs, recorded = stand_in_agent_binaries(base)
            process = subprocess.Popen(
                [sys.executable, "-B", str(runner_driver(base, repo)),
                 "--target", target, "--attack", "cut"],
                env=runner_process_environment(programs, recorded, codex="report"),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                records_root = repo / "sanity-check-records"
                started = wait_until(
                    lambda: len(recorded_process_ids(recorded, "claude")) == 1
                    and any(records_root.glob("*/cut-codex.md")))
                copies_mid_run = left_in_copies_root(base)
                process.send_signal(stop_signal)
                try:
                    out, err = process.communicate(timeout=30)
                except subprocess.TimeoutExpired:
                    process.kill()
                    out, err = process.communicate()
                claude_launches = recorded_process_ids(recorded, "claude")
                still_running = [pid for launch in claude_launches for pid in launch
                                 if not wait_until(lambda: not process_is_running(pid), 5.0)]
                records = sorted(records_root.glob("*"))
                record = records[0] if len(records) == 1 else None
                log_text = ((record / "sanity-check-run.log").read_text(encoding="utf-8")
                            if record and (record / "sanity-check-run.log").is_file() else "")
                check(f"{signal_name} to the runner while a cell runs: the cells had "
                      f"started and the copy was there",
                      started and len(copies_mid_run) == 1
                      and not any(name.endswith(".owner") for name in copies_mid_run),
                      f"started {started}, copies root held {copies_mid_run}")
                check(f"the runner ends by {signal_name}, after its own steps",
                      process.returncode == -stop_signal,
                      f"exit {process.returncode}, stdout {out!r}, stderr {err!r}")
                check(f"the agent-binary still working when {signal_name} arrived, "
                      f"and the process under it, are stopped",
                      len(claude_launches) == 1 and still_running == [],
                      f"launches {claude_launches}, still running {still_running}")
                check(f"the review copy is gone after {signal_name}",
                      left_in_copies_root(base) == [],
                      f"copies root holds {left_in_copies_root(base)}")
                check(f"the report saved before {signal_name}, the scratch directories "
                      f"and the log are in the record",
                      record is not None and (record / "cut-codex.md").is_file()
                      and (record / "scratch" / "cut-claude").is_dir()
                      and "saved: " in log_text,
                      f"record {record}, holds "
                      f"{sorted(p.name for p in record.iterdir()) if record else None}, "
                      f"log {log_text!r}")
                stopped_lines = [line for line in out.splitlines()
                                 if line.startswith("STOPPED: ")]
                check(f"the run's STOPPED line says {signal_name} ended it, what to "
                      f"run, and where the record is, and the log keeps that line",
                      len(stopped_lines) == 1 and record is not None
                      and stopped_lines[0].startswith(
                          f"STOPPED: {signal_name} ended this run")
                      and "Run the same command again" in stopped_lines[0]
                      and str(record) in stopped_lines[0]
                      and stopped_lines[0] in log_text,
                      f"stdout {out!r}, log {log_text!r}")
                shipped_log = (SUITE_SCRATCH_LOG_STORE_PATH / "sanity-check-records"
                               / record.name / "sanity-check-run.log") if record else None
                check(f"and the record of the run {signal_name} stopped is shipped, "
                      f"its log whole",
                      out.splitlines()[-1:] != []
                      and out.splitlines()[-1].startswith("record: shipped: ")
                      and shipped_log is not None and shipped_log.is_file()
                      and shipped_log.read_text(encoding="utf-8") == log_text
                      and "record: " not in log_text,
                      f"stdout {out!r}, looked for {shipped_log}")
                check(f"a cell stopped with its run by {signal_name} is not relaunched "
                      f"and prints no FAILED instructions",
                      "RETRYING:" not in out and "FAILED:" not in out
                      and "WARNING: claude" not in out
                      and len(recorded_process_ids(recorded, "claude")) == 1,
                      f"stdout {out!r}")
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
                end_stand_ins(recorded)

    # Case 45: SIGINT sent to the runner's whole process group, as Ctrl-C at a
    # terminal sends it. Each agent-binary dies of the signal itself. The
    # runner used to take that for a failed launch: it printed RETRYING, ran
    # the codex cell again and went on to the claude chain's second model,
    # then waited for those launches. A stopped run launches nothing more.
    with tempfile.TemporaryDirectory() as scratch:
        base = pathlib.Path(scratch).resolve()
        repo = scratch_repository_with_design(base)
        programs, recorded = stand_in_agent_binaries(base)
        process = subprocess.Popen(
            [sys.executable, "-B", str(runner_driver(base, repo)),
             "--target", "docs/design.md", "--attack", "cut"],
            env=runner_process_environment(programs, recorded),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            start_new_session=True)
        try:
            started = wait_until(
                lambda: len(recorded_process_ids(recorded, "claude")) == 1
                and len(recorded_process_ids(recorded, "codex")) == 1)
            os.killpg(process.pid, signal.SIGINT)
            try:
                out, err = process.communicate(timeout=20)
                ended_by_itself = True
            except subprocess.TimeoutExpired:
                ended_by_itself = False
                os.killpg(process.pid, signal.SIGKILL)
                out, err = process.communicate()
            launches = (len(recorded_process_ids(recorded, "claude")),
                        len(recorded_process_ids(recorded, "codex")))
            check("SIGINT to the whole process group: no agent-binary is launched "
                  "again, by a relaunch or by the claude chain's next model",
                  started and launches == (1, 1) and "RETRYING:" not in out,
                  f"started {started}, (claude, codex) launches {launches}, "
                  f"stdout {out!r}")
            check("and the run ends by SIGINT with its copy removed, not waiting "
                  "for launches of its own",
                  ended_by_itself and process.returncode == -signal.SIGINT
                  and left_in_copies_root(base) == []
                  and sum(line.startswith("STOPPED: SIGINT ") for line in out.splitlines()) == 1,
                  f"ended by itself {ended_by_itself}, exit {process.returncode}, "
                  f"copies root {left_in_copies_root(base)}, stdout {out!r}, "
                  f"stderr {err!r}")
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
            end_stand_ins(recorded)

    # Still case 45, without a process: the places a thread reads the stop
    # before it launches an agent-binary. A cell's thread that reaches one
    # after the handler has looked at the process table for the last time
    # would otherwise start a launch the run then waits an hour for. Once the
    # run is stopped, the claude chain launches no model, and a cell launches
    # nothing and prints nothing. Starts are counted where a process would
    # begin, at subprocess.Popen.
    runner_stopped = load_runner()
    stopped_flag = getattr(runner_stopped, "RUN_STOPPED", None)
    launched_after_stop = []

    def counting_start(command, *arguments, **keywords):
        launched_after_stop.append(command[0])
        raise OSError(f"{command[0]} was started after the run was stopped")

    real_stopped_start = runner_stopped.subprocess.Popen
    if stopped_flag is not None:
        stopped_flag.set()
    buffer = io.StringIO()
    try:
        runner_stopped.subprocess.Popen = counting_start
        with contextlib.redirect_stdout(buffer):
            chain_result = runner_stopped.run_claude(
                "a prompt no model ever sees", pathlib.Path("/a/review/copy"))
    finally:
        runner_stopped.subprocess.Popen = real_stopped_start
    check("once the run is stopped the claude chain launches no model",
          stopped_flag is not None and launched_after_stop == []
          and chain_result[0] != 0 and buffer.getvalue() == "",
          f"launched {launched_after_stop}, returned {chain_result!r}, "
          f"printed {buffer.getvalue()!r}")
    runner_stopped.run_codex = lambda prompt, checkout=None: (
        launched_after_stop.append("codex") or (0, any_attack_report, "a-test-model", "", None))
    cell_ok, output, raised, report = run_cell_capturing(runner_stopped, "codex")
    check("and a cell launches nothing, saves nothing and prints nothing",
          stopped_flag is not None and launched_after_stop == [] and cell_ok is False
          and raised is None and report is None and output == "",
          f"launched {launched_after_stop}, cell_ok {cell_ok}, raised {raised!r}, "
          f"report {report!r}, output {output!r}")

    # Case 47: a byte that is not UTF-8 in what an agent-binary writes. A
    # Codex session's captured streams hold everything the model and its tools
    # wrote, and one such byte ended the whole run in a UnicodeDecodeError
    # traceback, with the cell's finished report lost. The launchers are run
    # here as they are, over the stand-in programs: the byte is in the codex
    # launch's standard error and in its last message, and in both of the
    # claude launch's streams. Each launch returns its review.
    with tempfile.TemporaryDirectory() as scratch:
        base = pathlib.Path(scratch).resolve()
        programs, recorded = stand_in_agent_binaries(base)
        runner_bytes = load_runner()
        environment = runner_process_environment(
            programs, recorded, codex="bad-byte", claude="bad-byte")
        saved_environment = dict(os.environ)
        results = {}
        buffer = io.StringIO()
        # On Linux the codex profile walks the home for credential files:
        # emptied, so the real home is not walked.
        real_bytes_files_found = runner_bytes.common.credential_files_found_now
        try:
            os.environ.update(environment)
            runner_bytes.common.credential_files_found_now = lambda: []
            with contextlib.redirect_stdout(buffer):
                for name, launcher in (("codex", runner_bytes.run_codex),
                                       ("claude", runner_bytes.run_claude)):
                    try:
                        results[name] = launcher("a prompt no model ever sees", base)
                    except UnicodeDecodeError as error:
                        results[name] = error
        finally:
            runner_bytes.common.credential_files_found_now = real_bytes_files_found
            os.environ.clear()
            os.environ.update(saved_environment)
        for name in ("codex", "claude"):
            result = results[name]
            check(f"a {name} launch that writes a byte that is not UTF-8 still "
                  f"returns its review",
                  isinstance(result, tuple) and result[0] == 0
                  and result[1].startswith(any_attack_report),
                  f"returned {result!r}, printed {buffer.getvalue()!r}")

    # Case 48: a run in which every launched cell failed. It used to ship
    # nothing and print the record's path nowhere, so the requesting agent
    # could not find the log the run had saved, which is where each FAILED
    # line and its instructions are kept. It ships the record, prints the
    # shipper's line as `record:`, and names the record directory.
    with tempfile.TemporaryDirectory() as scratch:
        base = pathlib.Path(scratch)
        # A target of its own, so the record's name is one no other case of
        # this suite has shipped to the scratch store, which refuses a second
        # record of one name whose log differs.
        repo = scratch_repository_with_design(base, "docs/every-cell-failed.md")
        driven = runner_over(repo, base)
        driven.run_codex = lambda prompt, checkout=None: (
            1, "", "a-test-model", "", ("logged-out", "401 Unauthorized"))
        code, out, err = drive_main(driven, [
            "--target", "docs/every-cell-failed.md", "--attack", "cut",
            "--runtime", "codex"])
        records = sorted(driven.RECORDS_ROOT.glob("*"))
        record = records[0] if len(records) == 1 else None
        shipped_log = (SUITE_SCRATCH_LOG_STORE_PATH / "sanity-check-records"
                       / record.name / "sanity-check-run.log") if record else None
        check("a run whose every cell failed prints the shipper's line as `record:` "
              "and names its record directory",
              code == 1 and record is not None
              and sum(line.startswith("record: shipped: ") for line in out.splitlines()) == 1
              and "sanity-check wrote no reports" in out
              and f"is in {record}." in out,
              f"exit {code}, records {records}, stdout {out!r}, stderr {err!r}")
        check("and its record, the log with the FAILED line in it, is in the store",
              shipped_log is not None and shipped_log.is_file()
              and "FAILED: cut-codex — logged-out — 401 Unauthorized"
              in shipped_log.read_text(encoding="utf-8")
              and "record: " not in shipped_log.read_text(encoding="utf-8"),
              f"looked for {shipped_log}")

    # Cases 49 to 53 came from round 2 of review of the pull request that
    # introduced the review copy (2026-10-01).
    #
    # Case 49: a stop signal that lands while a cell's relaunch is being
    # prepared, after run_cell has read RUN_STOPPED unset. The relaunch used
    # to start after the handler's last look at the process table: the
    # agent-binary was killed alone, the child it then started held its
    # pipes, and the runner waited for that child with every stop signal
    # ignored and its review copy left. The driver holds the codex cell's
    # second launch while its profile is built, the signal is sent there,
    # and the hold is let go once the handler has stopped the processes it
    # found. No agent-binary starts after the signal.
    with tempfile.TemporaryDirectory() as scratch:
        base = pathlib.Path(scratch).resolve()
        target = "docs/stopped-while-a-relaunch-is-prepared.md"
        repo = scratch_repository_with_design(base, target)
        programs, recorded = stand_in_agent_binaries(base)
        relaunch_hold = base / "relaunch-hold"
        walk_done = base / "stop-walk-done"
        environment = runner_process_environment(programs, recorded, codex="fail-once")
        environment["DRIVER_HOLD_CODEX_RELAUNCH"] = str(relaunch_hold)
        environment["DRIVER_STOP_WALK_DONE"] = str(walk_done)
        process = subprocess.Popen(
            [sys.executable, "-B", str(runner_driver(base, repo)),
             "--target", target, "--attack", "cut", "--runtime", "codex"],
            env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            held = wait_until(lambda: pathlib.Path(str(relaunch_hold) + ".held").exists())
            process.send_signal(signal.SIGTERM)
            walked = wait_until(walk_done.exists, 10.0)
            relaunch_hold.write_text("", encoding="utf-8")
            try:
                out, err = process.communicate(timeout=30)
                ended_by_itself = True
            except subprocess.TimeoutExpired:
                ended_by_itself = False
                process.kill()
                out, err = process.communicate()
            started_after_stop = recorded_process_ids(recorded, "codex")
            check("a stop that lands while a relaunch is prepared: the first launch "
                  "had failed and the relaunch was under way when the signal came",
                  held and walked and "RETRYING: cut-codex — exit-1 — " in out,
                  f"held {held}, walked {walked}, stdout {out!r}")
            check("and no agent-binary starts after the signal, and the run ends by "
                  "it with its copy removed",
                  ended_by_itself and started_after_stop == []
                  and process.returncode == -signal.SIGTERM
                  and left_in_copies_root(base) == []
                  and sum(line.startswith("STOPPED: SIGTERM ") for line in out.splitlines()) == 1
                  and "FAILED:" not in out,
                  f"ended by itself {ended_by_itself}, started {started_after_stop}, "
                  f"exit {process.returncode}, copies root {left_in_copies_root(base)}, "
                  f"stdout {out!r}, stderr {err!r}")
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
            end_stand_ins(recorded)

    # Case 50: the lock that makes the stop and a launch exclusive, without a
    # process. A cell's thread reads RUN_STOPPED and starts its agent-binary
    # under AGENT_BINARY_LAUNCH_LOCK, and the handler sets RUN_STOPPED under
    # it, so a launch is either started before the run is marked stopped, and
    # then in the table the handler reads, or not started at all.
    runner_gate = load_runner()
    gate = getattr(runner_gate, "run_agent_binary_unless_run_stopped", None)
    gate_lock = getattr(runner_gate, "AGENT_BINARY_LAUNCH_LOCK", None)
    starts = []

    def recorded_start(command, *arguments, **keywords):
        starts.append(command[0])
        raise OSError(f"{command[0]} was started")

    real_gate_start = runner_gate.subprocess.Popen
    gate_result = {}
    try:
        runner_gate.subprocess.Popen = recorded_start
        # The thread is held at the lock; the run is marked stopped; the
        # thread, let in, starts nothing.
        if gate is not None and gate_lock is not None:
            with gate_lock:
                launching = threading.Thread(
                    target=lambda: gate_result.update(returned=gate(["codex", "exec"])))
                launching.start()
                launching.join(0.3)
                runner_gate.RUN_STOPPED.set()
            launching.join(10)
    finally:
        runner_gate.subprocess.Popen = real_gate_start
    check("a launch that waits on the lock while the run is marked stopped starts "
          "nothing",
          gate is not None and gate_lock is not None
          and gate_result.get("returned", "never returned") is None and starts == [],
          f"gate {gate}, returned {gate_result}, started {starts}")

    # The other side: the handler waits for a start in progress, and marks the
    # run stopped only once that agent-binary is in the table.
    runner_gate = load_runner()
    order = []
    start_begun = threading.Event()

    class SlowStart:
        """A start that takes a while, then ends at once with nothing written."""
        def __init__(self, command, *arguments, **keywords):
            start_begun.set()
            time.sleep(0.3)
            order.append(f"started, run stopped: {runner_gate.RUN_STOPPED.is_set()}")
            self.returncode = 0

        def __enter__(self):
            return self

        def __exit__(self, *exception):
            return False

        def communicate(self, input=None, timeout=None):
            return "", ""

        def poll(self):
            return 0

    real_gate_start = runner_gate.subprocess.Popen
    real_stop_processes = runner_gate.stop_processes_this_run_started
    handlers_before = {number: signal.getsignal(number)
                       for number in runner_gate.RUN_STOP_SIGNALS}
    handler_raised = None
    try:
        runner_gate.subprocess.Popen = SlowStart
        runner_gate.stop_processes_this_run_started = lambda: order.append(
            f"table read, run stopped: {runner_gate.RUN_STOPPED.is_set()}")
        launching = threading.Thread(target=lambda: runner_gate.run_agent_binary_unless_run_stopped(
            ["claude", "-p"], stdout=subprocess.PIPE))
        launching.start()
        start_begun.wait(10)
        try:
            runner_gate.stop_run_on_signal(signal.SIGTERM, None)
        except BaseException as error:
            handler_raised = error
        launching.join(10)
    finally:
        runner_gate.subprocess.Popen = real_gate_start
        runner_gate.stop_processes_this_run_started = real_stop_processes
        for number, handler in handlers_before.items():
            if handler is not None:
                signal.signal(number, handler)
    check("the handler marks the run stopped only once a start in progress has "
          "finished, and reads the table after",
          order == ["started, run stopped: False", "table read, run stopped: True"]
          and type(handler_raised).__name__ == "RunStoppedBySignal",
          f"order {order}, handler raised {handler_raised!r}")

    # And a stop that lands while a codex launch builds its permission profile,
    # which on Linux runs `find` over the home after every check of the stop
    # before it: nothing is started, nothing is printed.
    runner_gate = load_runner()
    starts = []

    def profile_while_the_run_is_stopped(*arguments, **keywords):
        runner_gate.RUN_STOPPED.set()
        return []

    real_gate_start = runner_gate.subprocess.Popen
    real_profile = runner_gate.common.codex_credential_denying_permission_profile_arguments
    buffer = io.StringIO()
    try:
        runner_gate.subprocess.Popen = recorded_start
        runner_gate.common.codex_credential_denying_permission_profile_arguments = (
            profile_while_the_run_is_stopped)
        with contextlib.redirect_stdout(buffer):
            try:
                codex_result = runner_gate.run_codex("a prompt no model ever sees",
                                                     pathlib.Path("/a/review/copy"))
            except OSError as error:
                codex_result = error
    finally:
        runner_gate.subprocess.Popen = real_gate_start
        runner_gate.common.codex_credential_denying_permission_profile_arguments = real_profile
    check("a stop that lands while a codex launch builds its profile starts no codex",
          starts == [] and isinstance(codex_result, tuple)
          and codex_result[0] != 0 and codex_result[4] is None
          and buffer.getvalue() == "",
          f"started {starts}, returned {codex_result!r}, printed {buffer.getvalue()!r}")

    # Case 51: a launch the stop ended is not a failure of the agent's. Each
    # launcher reads the stop again once its agent-binary has ended, and
    # prints none of what that agent-binary wrote as it was ended: an
    # interrupted codex prints a KeyboardInterrupt traceback, which used to
    # land in the run's output above its STOPPED line. The claude chain does
    # not go on to its next model.
    for runtime in ("codex", "claude"):
        runner_ended = load_runner()
        calls = []

        def ended_by_the_stop(command, *arguments, runner=runner_ended, **keywords):
            calls.append(command[0])
            runner.RUN_STOPPED.set()
            return subprocess.CompletedProcess(
                list(command), -signal.SIGINT, "",
                "Traceback (most recent call last):\nKeyboardInterrupt\n")

        agent_binary_launch_a_case_replaces(runner_ended)
        runner_ended.run_agent_binary_unless_run_stopped = ended_by_the_stop
        real_ended_profile = runner_ended.common.codex_credential_denying_permission_profile_arguments
        runner_ended.common.codex_credential_denying_permission_profile_arguments = (
            lambda *arguments, **keywords: [])
        buffer = io.StringIO()
        try:
            with contextlib.redirect_stdout(buffer):
                launcher = runner_ended.run_codex if runtime == "codex" else runner_ended.run_claude
                ended = launcher("a prompt no model ever sees", pathlib.Path("/a/review/copy"))
        finally:
            runner_ended.common.codex_credential_denying_permission_profile_arguments = (
                real_ended_profile)
        check(f"a {runtime} launch the stop ended prints nothing it wrote, carries "
              f"no cause, and launches nothing more",
              buffer.getvalue() == "" and ended[0] != 0 and ended[4] is None
              and calls == [runtime],
              f"printed {buffer.getvalue()!r}, returned {ended!r}, launches {calls}")

    # Case 52: a stop signal that lands after every cell has saved its report,
    # here while the record ships. It stopped no agent, so the run does not
    # print a STOPPED line telling the agent to run the whole command again:
    # it prints what a finished run prints, ships the record, and ends by the
    # signal.
    with tempfile.TemporaryDirectory() as scratch:
        base = pathlib.Path(scratch).resolve()
        target = "docs/stopped-while-the-record-ships.md"
        repo = scratch_repository_with_design(base, target)
        programs, recorded = stand_in_agent_binaries(base)
        ship_hold = base / "ship-hold"
        environment = runner_process_environment(
            programs, recorded, codex="report", claude="report")
        environment["DRIVER_HOLD_FIRST_SHIP"] = str(ship_hold)
        process = subprocess.Popen(
            [sys.executable, "-B", str(runner_driver(base, repo)),
             "--target", target, "--attack", "cut"],
            env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            held = wait_until(lambda: pathlib.Path(str(ship_hold) + ".held").exists())
            process.send_signal(signal.SIGTERM)
            try:
                out, err = process.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                out, err = process.communicate()
            records = sorted((repo / "sanity-check-records").glob("*"))
            record = records[0] if len(records) == 1 else None
            check("a stop that lands after every cell saved its report prints what a "
                  "finished run prints, and no STOPPED line",
                  held and record is not None
                  and (record / "cut-codex.md").is_file() and (record / "cut-claude.md").is_file()
                  and "STOPPED:" not in out
                  and f"sanity-check complete: reports in {record}." in out
                  and sum(line.startswith("record: shipped: ") for line in out.splitlines()) == 1,
                  f"held {held}, record {record}, stdout {out!r}, stderr {err!r}")
            check("and the run still ends by the signal, its copy removed",
                  process.returncode == -signal.SIGTERM and left_in_copies_root(base) == [],
                  f"exit {process.returncode}, copies root {left_in_copies_root(base)}")
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
            end_stand_ins(recorded)

    # Case 54: an agent-binary started in the moment the stop handler waits
    # for the launch lock. The handler makes later stop signals do nothing
    # before it waits, and a cell's thread may be starting an agent-binary
    # under the lock right then. With SIG_IGN that disposition survived the
    # agent-binary's exec, so the SIGTERM that stops it did nothing and it ran
    # on until the SIGKILL after the grace. Here the launch is held inside the
    # lock until the handler has changed the dispositions, and the program it
    # starts reports which of the three stop signals it starts with ignored.
    runner_inherit = load_runner()
    stop_signal_numbers = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)
    dispositions_before = {number: signal.getsignal(number) for number in stop_signal_numbers}

    def before_the_handler(_number, _frame):
        pass

    for number in stop_signal_numbers:
        signal.signal(number, before_the_handler)
    reports_dispositions = (
        "import signal\n"
        "print(' '.join(str(signal.getsignal(number) == signal.SIG_IGN) for number in "
        "(signal.SIGTERM, signal.SIGINT, signal.SIGHUP)))\n"
        "# reports-its-stop-signal-dispositions\n")
    real_inherit_popen = runner_inherit.subprocess.Popen
    launch_entered = threading.Event()

    def launch_held_until_the_handler_has_begun(command, *arguments, **keywords):
        if command[-1] == reports_dispositions:
            launch_entered.set()
            deadline = time.monotonic() + 10
            while (any(signal.getsignal(number) is before_the_handler
                       for number in stop_signal_numbers)
                   and time.monotonic() < deadline):
                time.sleep(0.01)
        return real_inherit_popen(command, *arguments, **keywords)

    launched = {}
    handler_error = None
    try:
        runner_inherit.subprocess.Popen = launch_held_until_the_handler_has_begun
        runner_inherit.stop_processes_this_run_started = lambda: None
        launching = threading.Thread(target=lambda: launched.setdefault(
            "result", runner_inherit.run_agent_binary_unless_run_stopped(
                [sys.executable, "-c", reports_dispositions],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)))
        launching.start()
        launch_entered.wait(10)
        try:
            runner_inherit.stop_run_on_signal(signal.SIGTERM, None)
        except BaseException as error:
            handler_error = error
        launching.join(30)
    finally:
        runner_inherit.subprocess.Popen = real_inherit_popen
        for number, handler in dispositions_before.items():
            if handler is not None:
                signal.signal(number, handler)
    result = launched.get("result")
    check("an agent-binary started while the stop handler waits for the launch lock "
          "starts with SIGTERM, SIGINT and SIGHUP not ignored, so the stop's SIGTERM "
          "can end it",
          launch_entered.is_set()
          and type(handler_error).__name__ == "RunStoppedBySignal"
          and result is not None and result.stdout.split() == ["False", "False", "False"],
          f"entered {launch_entered.is_set()}, handler raised {handler_error!r}, "
          f"launched {result!r}")

    # Case 55: a stop signal that lands after the last cell's agent-binary has
    # exited and before its report is saved. The run is decided at the
    # signal, and that cell had not finished then, so the run ends with its
    # STOPPED line; the report the cell saves after the signal is kept.
    with tempfile.TemporaryDirectory() as scratch:
        base = pathlib.Path(scratch).resolve()
        target = "docs/stopped-while-a-report-is-saved.md"
        repo = scratch_repository_with_design(base, target)
        programs, recorded = stand_in_agent_binaries(base)
        report_check_hold = base / "report-check-hold"
        walk_done = base / "stop-walk-done"
        environment = runner_process_environment(
            programs, recorded, codex="report", claude="report")
        environment["DRIVER_HOLD_LAST_REPORT_CHECK"] = str(report_check_hold)
        environment["DRIVER_STOP_WALK_DONE"] = str(walk_done)
        process = subprocess.Popen(
            [sys.executable, "-B", str(runner_driver(base, repo)),
             "--target", target, "--attack", "cut"],
            env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            held = wait_until(lambda: pathlib.Path(str(report_check_hold) + ".held").exists())
            process.send_signal(signal.SIGTERM)
            walked = wait_until(walk_done.exists)
            report_check_hold.write_text("", encoding="utf-8")
            try:
                out, err = process.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                out, err = process.communicate()
            records = sorted((repo / "sanity-check-records").glob("*"))
            record = records[0] if len(records) == 1 else None
            check("a stop that lands while the last cell saves its report ends the run "
                  "with its STOPPED line, and the report is kept",
                  held and walked and record is not None
                  and (record / "cut-codex.md").is_file() and (record / "cut-claude.md").is_file()
                  and "STOPPED: SIGTERM ended this run" in out
                  and "sanity-check complete" not in out
                  and sum(line.startswith("record: shipped: ") for line in out.splitlines()) == 1,
                  f"held {held}, walked {walked}, record {record}, stdout {out!r}, "
                  f"stderr {err!r}")
            check("and that run still ends by the signal, its copy removed",
                  process.returncode == -signal.SIGTERM and left_in_copies_root(base) == [],
                  f"exit {process.returncode}, copies root {left_in_copies_root(base)}")
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
            end_stand_ins(recorded)

    # A failed removal must prevent a successful exit and name the manual action.
    with tempfile.TemporaryDirectory() as scratch:
        base = pathlib.Path(scratch).resolve()
        repo = scratch_repository_with_design(base)
        runner_removal = runner_over(repo, base)
        runner_removal.run_claude = lambda prompt, checkout=None: (
            0, any_attack_report, "a-test-model", "", None)
        runner_removal.remove_directory_whatever_signal_arrives = lambda directory: None
        code, out, err = drive_main(runner_removal, [
            "--target", "docs/design.md", "--attack", "cut", "--runtime", "claude"])
        holders = list(runner_removal.REVIEW_COPIES_ROOT.iterdir())
        holder = holders[0] if len(holders) == 1 else None
        expected = (f"WARNING: the review copy could not be removed: {holder}\n"
                    "Delete that directory by hand.\n")
        check("failed removal ends nonzero, names the full path and manual deletion, "
              "and still ships the record",
              code == 1 and holder is not None and holder.is_dir()
              and expected in out and "record: " in out,
              f"exit {code}, holders {holders}, stdout {out!r}, stderr {err!r}")
        runner_removal = runner_over(repo, base)
        head = git(repo, "rev-parse", "HEAD").strip()
        with runner_removal.review_copy_of_commit(head, "design", repo) as checkout:
            check("a new run creates only its directory and leaves earlier copies alone",
                  holder is not None and holder.is_dir()
                  and set(runner_removal.REVIEW_COPIES_ROOT.iterdir())
                  == {holder, checkout.parent},
                  str(list(runner_removal.REVIEW_COPIES_ROOT.iterdir())))
        check("a new run removes only its own copy",
              list(runner_removal.REVIEW_COPIES_ROOT.iterdir()) == holders,
              str(list(runner_removal.REVIEW_COPIES_ROOT.iterdir())))

        # A stop signal that lands during a removal that leaves the copy: the
        # signal still propagates, and the copy is still reported.
        runner_stopped_removal = runner_over(repo, base)

        def removal_stopped_by_signal(directory):
            raise runner_stopped_removal.RunStoppedBySignal(signal.SIGTERM)

        runner_stopped_removal.remove_directory_whatever_signal_arrives = (
            removal_stopped_by_signal)
        before = set(runner_stopped_removal.REVIEW_COPIES_ROOT.iterdir())
        printed = io.StringIO()
        propagated = None
        try:
            with contextlib.redirect_stdout(printed):
                with runner_stopped_removal.review_copy_of_commit(head, "design", repo):
                    pass
        except runner_stopped_removal.RunStoppedBySignal as raised:
            propagated = raised
        left = set(runner_stopped_removal.REVIEW_COPIES_ROOT.iterdir()) - before
        stopped_holder = next(iter(left)) if len(left) == 1 else None
        check("a removal a stop signal interrupts and that leaves the copy still "
              "names the copy and manual deletion, and the signal still propagates",
              propagated is not None and stopped_holder is not None
              and runner_stopped_removal.REVIEW_COPY_NOT_REMOVED == stopped_holder
              and (f"WARNING: the review copy could not be removed: "
                   f"{stopped_holder.resolve()}\nDelete that directory by hand.\n")
              in printed.getvalue(),
              f"propagated {propagated!r}, left {left}, stdout {printed.getvalue()!r}")

    # Case 57: a cell whose thread first runs after the run is stopped. It
    # launches nothing and does not count as finished, so the run ends with
    # its STOPPED line: a run that never launched that cell has not saved
    # every report it was going to.
    runner_late = load_runner()
    late_launches = []

    def launch_recorded(*arguments, **keywords):
        late_launches.append(1)
        return 0, "a review\n", "a-model", "", None

    runner_late.run_codex = launch_recorded
    runner_late.RUN_STOPPED.set()
    late_ok, late_output, late_raised, _ = run_cell_capturing(runner_late, "codex")
    check("a cell whose thread finds the run already stopped launches nothing, and is "
          "not counted as finished",
          late_raised is None and late_ok is False and not late_launches
          and late_output == ""
          and getattr(runner_late, "CELLS_FINISHED", None) == set(),
          f"raised {late_raised!r}, ok {late_ok}, launches {len(late_launches)}, "
          f"printed {late_output!r}, "
          f"finished {getattr(runner_late, 'CELLS_FINISHED', None)}")

    # Case 58: a stop signal that lands while the last cell is in a git call
    # it makes to save its report, after its agent-binary has exited. The
    # stop's walk ends that call; the call runs with check=False, so the cell
    # saves its report anyway, with `commit=unknown`. That report is what the
    # stop cut short, so the run ends with its STOPPED line, not as a finished
    # run over it. A stand-in `git`, first on the runner's PATH, holds the
    # cell inside its `git rev-parse --short HEAD`.
    with tempfile.TemporaryDirectory() as scratch:
        base = pathlib.Path(scratch).resolve()
        target = "docs/stopped-in-a-git-call.md"
        repo = scratch_repository_with_design(base, target)
        programs, recorded = stand_in_agent_binaries(base)
        real_git = shutil.which("git")
        (programs / "git").write_text(
            "#!/bin/sh\n"
            'if [ -n "$GIT_HOLD_REV_PARSE" ] && [ "$1" = rev-parse ] && [ "$2" = --short ]; then\n'
            '    : > "$GIT_HOLD_REV_PARSE.held"\n'
            '    while [ ! -e "$GIT_HOLD_REV_PARSE" ]; do sleep 0.05; done\n'
            "fi\n"
            f'exec {shlex.quote(real_git)} "$@"\n', encoding="utf-8")
        (programs / "git").chmod(0o755)
        git_hold = base / "git-hold"
        walk_done = base / "stop-walk-done"
        environment = runner_process_environment(programs, recorded, codex="report")
        environment["GIT_HOLD_REV_PARSE"] = str(git_hold)
        environment["DRIVER_STOP_WALK_DONE"] = str(walk_done)
        process = subprocess.Popen(
            [sys.executable, "-B", str(runner_driver(base, repo)),
             "--target", target, "--attack", "cut", "--runtime", "codex"],
            env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            held = wait_until(lambda: pathlib.Path(str(git_hold) + ".held").exists())
            process.send_signal(signal.SIGTERM)
            walked = wait_until(walk_done.exists)
            try:
                out, err = process.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                out, err = process.communicate()
            records = sorted((repo / "sanity-check-records").glob("*"))
            record = records[0] if len(records) == 1 else None
            report = record / "cut-codex.md" if record is not None else None
            report_text = (report.read_text(encoding="utf-8")
                           if report is not None and report.is_file() else "")
            check("a stop that ends the git call a cell makes to save its report ends "
                  "the run with its STOPPED line, not as a finished run",
                  held and walked and "commit=unknown" in report_text
                  and "STOPPED: SIGTERM ended this run" in out
                  and "sanity-check complete" not in out,
                  f"held {held}, walked {walked}, report {report_text[:200]!r}, "
                  f"stdout {out!r}, stderr {err!r}")
            check("and that run ends by the signal, its copy removed",
                  process.returncode == -signal.SIGTERM and left_in_copies_root(base) == [],
                  f"exit {process.returncode}, copies root {left_in_copies_root(base)}")
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
            end_stand_ins(recorded)

    # Case 59: a stop signal that lands while the last cell probes its
    # agent-binary's version to save its report, where the probe answers the
    # signal by exiting 0 with nothing on stdout, as the npm `codex` wrapper
    # on ned-box does when a signal ends its native child. The run is decided
    # at the signal: the cell had not finished then, so the run ends with its
    # STOPPED line, whatever the probe returned.
    with tempfile.TemporaryDirectory() as scratch:
        base = pathlib.Path(scratch).resolve()
        target = "docs/stopped-in-a-version-probe.md"
        repo = scratch_repository_with_design(base, target)
        programs, recorded = stand_in_agent_binaries(base)
        # The stand-in reads its mode from its own name, so it keeps the name
        # `codex`, in a directory of its own.
        (base / "stand-in-behind-the-wrapper").mkdir()
        behind_the_wrapper = base / "stand-in-behind-the-wrapper" / "codex"
        (programs / "codex").rename(behind_the_wrapper)
        (programs / "codex").write_text(
            "#!/bin/sh\n"
            'if [ "$1" = --version ] && [ -n "$CODEX_HOLD_VERSION" ]; then\n'
            '    : > "$CODEX_HOLD_VERSION.held"\n'
            "    trap 'exit 0' TERM\n"
            "    while :; do sleep 0.05; done\n"
            "fi\n"
            f'exec {shlex.quote(str(behind_the_wrapper))} "$@"\n',
            encoding="utf-8")
        (programs / "codex").chmod(0o755)
        probe_hold = base / "probe-hold"
        environment = runner_process_environment(programs, recorded, codex="report")
        environment["CODEX_HOLD_VERSION"] = str(probe_hold)
        environment["DRIVER_PROBE_VERSIONS"] = "1"
        process = subprocess.Popen(
            [sys.executable, "-B", str(runner_driver(base, repo)),
             "--target", target, "--attack", "cut", "--runtime", "codex"],
            env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            held = wait_until(lambda: pathlib.Path(str(probe_hold) + ".held").exists())
            process.send_signal(signal.SIGTERM)
            try:
                out, err = process.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                out, err = process.communicate()
            check("a stop during a cell's version probe, which then exits 0, ends the run "
                  "with its STOPPED line, not as a finished run",
                  held and "STOPPED: SIGTERM ended this run" in out
                  and "sanity-check complete" not in out
                  and process.returncode == -signal.SIGTERM,
                  f"held {held}, exit {process.returncode}, stdout {out!r}, "
                  f"stderr {err!r}")
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
            end_stand_ins(recorded)

    # Case 60: an agent-binary that is running when the run is stopped was
    # ended by the stop, whatever its exit code: one that answered SIGTERM by
    # exiting 0 with what it had written so far must not have that saved as a
    # report. run_codex returns a failed launch with no review.
    for stopped_while_it_ran in (True, False):
        codex_launches = []
        runner_exit_zero = load_runner()
        real_exit_zero_popen = runner_exit_zero.subprocess.Popen

        class RunStoppedWhileItRuns(real_exit_zero_popen):
            def __init__(self, command, *arguments, **keywords):
                # A stand-in codex: writes its last message where the runner
                # reads the review from, and exits 0. Any other command
                # run_codex starts (on Linux, more than the codex launch goes
                # through Popen) runs as given, and only the codex stand-in's
                # end stops the run, so the stop reaches the check after it.
                self.is_codex_launch = "--output-last-message" in command
                if self.is_codex_launch:
                    last_message = command[command.index("--output-last-message") + 1]
                    command = [sys.executable, "-c",
                               "import sys; open(sys.argv[1], 'w').write("
                               "'what it had written so far\\n')", last_message]
                    codex_launches.append(last_message)
                super().__init__(command, *arguments, **keywords)

            def communicate(self, *arguments, module=runner_exit_zero,
                            stop=stopped_while_it_ran, **keywords):
                answered = super().communicate(*arguments, **keywords)
                if stop and self.is_codex_launch:
                    module.RUN_STOPPED.set()
                return answered

        with tempfile.TemporaryDirectory() as exit_zero_copy:
            try:
                runner_exit_zero.subprocess.Popen = RunStoppedWhileItRuns
                code, review, _, _, _ = runner_exit_zero.run_codex(
                    "a prompt", pathlib.Path(exit_zero_copy))
            except Exception as error:
                code, review = f"raised {error!r}", None
            finally:
                runner_exit_zero.subprocess.Popen = real_exit_zero_popen
        if stopped_while_it_ran:
            check("an agent-binary that exits 0 while the run is stopped is a failed "
                  "launch with no review saved",
                  len(codex_launches) == 1 and code == 1 and review == "",
                  f"codex launches {len(codex_launches)}, exit {code!r}, review {review!r}")
        else:
            check("and one that exits 0 in a run not stopped returns its review",
                  code == 0 and "what it had written so far" in (review or ""),
                  f"exit {code!r}, review {review!r}")

    # A version probe that returns while the run is stopped, such as one the
    # stop ended with exit 0 and no output, is not cached as the runtime's
    # version.
    runner_probe = load_runner()
    real_probe_run = runner_probe.subprocess.run
    try:
        runner_probe.subprocess.run = lambda *a, **k: subprocess.CompletedProcess(
            a[0], 0, stdout="", stderr=None)
        runner_probe.RUN_STOPPED.set()
        probed = runner_probe.runtime_cli_version("codex")
    finally:
        runner_probe.subprocess.run = real_probe_run
        runner_probe.RUN_STOPPED.clear()
    check("a version probe that returns while the run is stopped is not cached",
          probed == "unknown" and "codex" not in runner_probe.CLI_VERSION_CACHE,
          f"probed {probed!r}, cache {runner_probe.CLI_VERSION_CACHE!r}")

    # The containment set at import: no case asked the PATH's `claude` or
    # `codex` for more than its version.
    tripwire_calls = (AGENT_BINARY_TRIPWIRE_LOG.read_text(encoding="utf-8").splitlines()
                      if AGENT_BINARY_TRIPWIRE_LOG.exists() else [])
    check("no case started a real agent-binary: the PATH's claude and codex were asked "
          "for nothing but their version",
          all(call.split(" ", 1)[1:] == ["--version"] for call in tripwire_calls),
          f"calls: {tripwire_calls}")

    print()
    if failures:
        print(f"{len(failures)} failing case(s): {', '.join(failures)}")
        return 1
    print("all cases pass")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        SUITE_SCRATCH_LOG_STORE.cleanup()
        AGENT_BINARY_TRIPWIRES.cleanup()
