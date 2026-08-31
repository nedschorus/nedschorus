#!/usr/bin/env python3
"""Tests for sanity-check-attacks.py — the worktree write detector, the record
directory claim, the cells' sanctioned scratch directories, the prompt-body
boundary, and the cells' launch flags.

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

import importlib.util
import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading

RUNNER_SCRIPT = pathlib.Path(__file__).with_name("sanity-check-attacks.py")

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
    runner_gate.run_claude = lambda prompt: (0, "the cell's report body\n")
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
          f"WARNING: cut-claude modified the worktree: {stray_name}" in output,
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
    # subprocess.run is replaced for the length of one call only. The module
    # object is shared with this file's own git() helper, so the real function
    # goes back in a finally, never left swapped.
    runner_memories = load_runner()
    captured = {}
    real_subprocess_run = runner_memories.subprocess.run

    def capture_command(command, *arguments, **keywords):
        captured["command"] = list(command)
        return subprocess.CompletedProcess(list(command), 0, "", "")

    try:
        runner_memories.subprocess.run = capture_command
        runner_memories.run_codex("a prompt no model ever sees")
    finally:
        runner_memories.subprocess.run = real_subprocess_run
    codex_command = captured.get("command", [])
    check("run_codex launches codex with memories disabled",
          ("--disable", "memories") in list(zip(codex_command, codex_command[1:])),
          f"composed command was {codex_command}")

    # The claude cells must launch with Write in the tool set: each is given a
    # scratch directory and told to keep its notes and drafts there
    # (user-ruled 2026-08-29), and without the tool that instruction asks for
    # something the cell cannot do. Inspected, not run, for the same reason as
    # the memories check above.
    runner_tools = load_runner()
    captured_claude = {}

    def capture_claude_command(command, *arguments, **keywords):
        captured_claude["command"] = list(command)
        return subprocess.CompletedProcess(list(command), 0, "", "")

    real_claude_run = runner_tools.subprocess.run
    try:
        runner_tools.subprocess.run = capture_claude_command
        runner_tools.run_claude("a prompt no model ever sees")
    finally:
        runner_tools.subprocess.run = real_claude_run
    claude_command = captured_claude.get("command", [])
    allowed_tools = (claude_command[claude_command.index("--allowedTools") + 1]
                     if "--allowedTools" in claude_command else "")
    check("run_claude launches claude with Write in the tool set",
          "Write" in allowed_tools.split(","),
          f"allowed tools were {allowed_tools!r}")
    check("the reading tools a review cell needs are still in the tool set",
          {"Read", "Grep", "Glob"} <= set(allowed_tools.split(",")),
          f"allowed tools were {allowed_tools!r}")

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

    print()
    if failures:
        print(f"{len(failures)} failing case(s): {', '.join(failures)}")
        return 1
    print("all cases pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
