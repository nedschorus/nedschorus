#!/usr/bin/env python3
"""Tests for clean-worktrees.py.

Builds a scratch repository with an origin remote and one worktree per
classification — done, dirty, ignored-files-only, unlanded, occupied, and
outside the managed area — then asserts the report names each correctly and
that --remove reaps exactly the done ones. A landed, vacant worktree is done
whatever files it holds; its uncommitted, untracked and ignored files are
named before it is removed.

Every way the decision can fail — origin/main missing, git unable to list a
worktree's files, lsof missing, timing out or failing — is run under
--remove against a worktree holding an untracked file, and must keep it.

The vacancy check's unusable-answer cases cannot be produced by a real lsof
on a healthy machine, so they run the reaper with a stub lsof first on PATH.
Those cases guard the reaper's central promise — ambiguity keeps, never
reaps — which a worktree holding someone's uncommitted work depends on.

The classification cases run against the machine's REAL lsof, and that is the
one way this suite can fail for a reason that is not a defect. If lsof does not
answer within clean-worktrees.py's VACANCY_CHECK_TIMEOUT_SECONDS, every done
worktree is kept with "the vacancy check (lsof) could not be run" — the reaper
failing safe, correctly — and the cases that expect "done-wt: done" fail with
it. Seen once, 2026-09-17 ~00:44Z, in a 52-suite run concurrent with five
subagents and another suite set, against the 30 s timeout that has since become
120. A run that fails with that phrase in its detail is a load symptom: re-run
this suite alone before calling anything red. It is deliberately not skipped
automatically — a suite that hides its own cases under load is worse than one
that needs a second run.

A last section covers the branch refs whose worktree is already gone: refs
attached to nothing, refs still carrying unlanded work, refs a live worktree
or the main checkout holds, a tag shadowing a branch name, remote-tracking
refs, and a git branch -d refusal — the ordinary state of a checkout whose
local main lags origin/main.

A closing section covers the Agent-tool subagent's worktree, which the vacancy
check cannot see into: kept while its transcript or the worktree itself was
written in the last hour, removable after. It runs the reaper under a scratch
HOME so the transcripts it reads are the suite's own.

A last section covers the records whose home is the log-store: before --remove
removes a done worktree it ships the worktree's cold-read-records and
sanity-check records, and keeps the worktree when a record fails to ship, is
refused, or its shipper prints nothing. The shippers run for real, into a
scratch store named by COLD_READ_RECORD_SHIP_DESTINATION; the failure to reach
ned-box is a stub ssh and rsync that exit 255.

Run: python3 scripts/clean-worktrees-test.py
"""

import atexit
import importlib.util
import os
import select
import shutil
import subprocess
import sys
import tempfile
import time
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

CLEAN_SCRIPT = Path(__file__).with_name("clean-worktrees.py")

SHIP_DESTINATION_VARIABLE = "COLD_READ_RECORD_SHIP_DESTINATION"
# A worktree holding a record makes --remove run the real shipper; without this, a run would ship
# into the real log-store.
_ship_store_for_every_run = tempfile.mkdtemp(prefix="clean-worktrees-test-ship-store-")
atexit.register(shutil.rmtree, _ship_store_for_every_run, ignore_errors=True)
os.environ[SHIP_DESTINATION_VARIABLE] = str(Path(_ship_store_for_every_run) / "cold-read-records")

ORPHANED_BRANCH_REF_LINE_MARKER = (
    "branch ref(s) with no worktree, nothing beyond origin/main:")

failures = []


def orphaned_branch_refs_named(output):
    """The branch names on the orphaned-branch-ref line, [] when it is absent.

    Parsed rather than substring-matched: the line's own prose contains
    "origin/main", so a check that a remote-tracking ref went unnamed would
    pass against the sentence instead of against the names.
    """
    for line in output.splitlines():
        if line.startswith(ORPHANED_BRANCH_REF_LINE_MARKER):
            named = line[len(ORPHANED_BRANCH_REF_LINE_MARKER):]
            named = named.rsplit(" — ", 1)[0]
            return [name.strip() for name in named.split(",") if name.strip()]
    return []


def files_named_on(line):
    """The file names after the last "file(s): " on a line, the "and N more" tail left off."""
    if "file(s): " not in line:
        return []
    named = line.rsplit("file(s): ", 1)[1].rsplit(" and ", 1)[0]
    return named.split(", ")


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


def run_clean(repo, *flags):
    return subprocess.run(
        [sys.executable, str(CLEAN_SCRIPT), "--repo", str(repo), *flags],
        capture_output=True, text=True, check=False,
    )


def run_clean_with_stub_lsof(repo, stub_directory, stub_body, *flags):
    """Run the reaper with a fake lsof first on PATH.

    A real lsof exits 0 on both fleet machines even while printing warnings,
    so the failure paths it is supposed to have — nonzero exit, empty
    listing — have no natural trigger to test against. The stub supplies one.
    """
    stub_directory.mkdir(parents=True, exist_ok=True)
    stub = stub_directory / "lsof"
    stub.write_text(stub_body, encoding="utf-8")
    stub.chmod(0o755)
    environment = dict(os.environ)
    environment["PATH"] = f"{stub_directory}{os.pathsep}{environment.get('PATH', '')}"
    return subprocess.run(
        [sys.executable, str(CLEAN_SCRIPT), "--repo", str(repo), *flags],
        capture_output=True, text=True, check=False, env=environment,
    )


def run_clean_without_lsof(repo, stub_directory, *flags):
    """Run the reaper with a PATH holding git and nothing else, so lsof is missing."""
    stub_directory.mkdir(parents=True, exist_ok=True)
    (stub_directory / "git").symlink_to(shutil.which("git"))
    environment = dict(os.environ)
    environment["PATH"] = str(stub_directory)
    return subprocess.run(
        [sys.executable, str(CLEAN_SCRIPT), "--repo", str(repo), *flags],
        capture_output=True, text=True, check=False, env=environment,
    )


def run_clean_with_git_status_killed(repo, stub_directory, *flags):
    """Run the reaper with a git that kills itself with a signal on `git status`."""
    stub_directory.mkdir(parents=True, exist_ok=True)
    stub = stub_directory / "git"
    stub.write_text(
        "#!/bin/sh\n"
        'case " $* " in *" status "*) kill -9 $$ ;; esac\n'
        f'exec {shutil.which("git")} "$@"\n', encoding="utf-8")
    stub.chmod(0o755)
    environment = dict(os.environ)
    environment["PATH"] = f"{stub_directory}{os.pathsep}{environment.get('PATH', '')}"
    return subprocess.run(
        [sys.executable, str(CLEAN_SCRIPT), "--repo", str(repo), *flags],
        capture_output=True, text=True, check=False, env=environment,
    )


def read_lines_until(process, enough, deadline_seconds):
    """Read a child's stdout lines until enough(lines) holds, the pipe closes, or the
    deadline passes; return the lines.

    Reads raw bytes from the pipe's file descriptor and splits lines here. A text
    wrapper's readline() can pull several lines into its own buffer and return one,
    leaving the rest where select() cannot see them."""
    lines, pending = [], b""
    deadline = time.monotonic() + deadline_seconds
    descriptor = process.stdout.fileno()
    while not enough(lines) and time.monotonic() < deadline:
        ready, _, _ = select.select([descriptor], [], [], 1)
        if not ready:
            continue
        chunk = os.read(descriptor, 65536)
        if not chunk:
            break
        pending += chunk
        *complete, pending = pending.split(b"\n")
        lines.extend(line.decode("utf-8", "replace") for line in complete)
    return lines


def load_clean_worktrees_module():
    spec = importlib.util.spec_from_file_location("clean_worktrees", CLEAN_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch)
    checkout = scratch / "checkout"
    origin = scratch / "origin.git"

    # A checkout whose origin/main exists, so the landed check has its anchor.
    checkout.mkdir()
    git(checkout, "init", "-b", "main")
    git(checkout, "config", "user.email", "test@test.invalid")
    git(checkout, "config", "user.name", "clean-worktrees test")
    (checkout / "README.md").write_text("# scratch\n", encoding="utf-8")
    (checkout / ".gitignore").write_text(
        "scratch-state/\n.DS_Store\n__pycache__/\n", encoding="utf-8")
    git(checkout, "add", "-A")
    git(checkout, "commit", "-m", "seed")
    subprocess.run(["git", "init", "--bare", str(origin)],
                   capture_output=True, check=True)
    git(checkout, "remote", "add", "origin", str(origin))
    git(checkout, "push", "-u", "origin", "main")

    managed = checkout / ".claude" / "worktrees"
    managed.mkdir(parents=True)

    def add_worktree(name, where=None):
        path = (where or managed) / name
        git(checkout, "worktree", "add", "-b", f"{name}-branch", str(path), "origin/main")
        return path

    done_wt = add_worktree("done-wt")
    # Regenerable junk must not keep an otherwise-done worktree.
    (done_wt / ".DS_Store").write_text("junk", encoding="utf-8")
    (done_wt / "__pycache__").mkdir()
    (done_wt / "__pycache__" / "a.pyc").write_text("junk", encoding="utf-8")
    dirty_wt = add_worktree("dirty-wt")
    (dirty_wt / "uncommitted.txt").write_text("scratch\n", encoding="utf-8")
    ignored_wt = add_worktree("ignored-wt")
    (ignored_wt / "scratch-state").mkdir()
    (ignored_wt / "scratch-state" / "ledger.md").write_text("state\n", encoding="utf-8")
    unlanded_wt = add_worktree("unlanded-wt")
    (unlanded_wt / "new.txt").write_text("work\n", encoding="utf-8")
    git(unlanded_wt, "add", "-A")
    git(unlanded_wt, "commit", "-m", "unlanded work")
    outside_wt = add_worktree("outside-wt", where=scratch)
    # Junk listed before real files, junk nested below the top, and an
    # untracked directory, which git collapses into one entry.
    mixed_wt = add_worktree("mixed-wt")
    (mixed_wt / ".DS_Store").write_text("junk", encoding="utf-8")
    (mixed_wt / "scratch-state").mkdir()
    (mixed_wt / "scratch-state" / "kept-a.md").write_text("a\n", encoding="utf-8")
    (mixed_wt / "scratch-state" / "deep").mkdir()
    (mixed_wt / "scratch-state" / "deep" / "kept-b.md").write_text("b\n", encoding="utf-8")
    (mixed_wt / "sub" / "__pycache__").mkdir(parents=True)
    (mixed_wt / "sub" / "__pycache__" / "x.pyc").write_text("junk", encoding="utf-8")
    (mixed_wt / "sub" / ".DS_Store").write_text("junk", encoding="utf-8")
    (mixed_wt / "sub" / "real.txt").write_text("r\n", encoding="utf-8")
    (mixed_wt / "newdir" / "inner").mkdir(parents=True)
    (mixed_wt / "newdir" / "one.txt").write_text("1\n", encoding="utf-8")
    (mixed_wt / "newdir" / "inner" / "two.txt").write_text("2\n", encoding="utf-8")
    # A staged rename: git -z prints the old path as a second field.
    git(mixed_wt, "mv", "README.md", "moved-readme.md")
    # A rename in the worktree column (mv, then git add -N), and file names
    # one and two characters long, the shortest entries git prints.
    renamed_wt = add_worktree("renamed-wt")
    (renamed_wt / "README.md").rename(renamed_wt / "worktree-moved.md")
    git(renamed_wt, "add", "-N", "worktree-moved.md")
    (renamed_wt / "a").write_text("1\n", encoding="utf-8")
    (renamed_wt / "ab").write_text("2\n", encoding="utf-8")
    # Exactly at the ten-name cap, and one past it.
    ten_files_wt = add_worktree("ten-files-wt")
    for number in range(10):
        (ten_files_wt / f"note-{number:02d}.txt").write_text("n\n", encoding="utf-8")
    many_files_wt = add_worktree("many-files-wt")
    for number in range(11):
        (many_files_wt / f"note-{number:02d}.txt").write_text("n\n", encoding="utf-8")
    detached_landed_wt = managed / "detached-landed-wt"
    git(checkout, "worktree", "add", "--detach", str(detached_landed_wt), "origin/main")
    detached_unlanded_wt = managed / "detached-unlanded-wt"
    git(checkout, "worktree", "add", "--detach", str(detached_unlanded_wt), "origin/main")
    (detached_unlanded_wt / "detached-work.txt").write_text("work\n", encoding="utf-8")
    git(detached_unlanded_wt, "add", "-A")
    git(detached_unlanded_wt, "commit", "-m", "unlanded detached work")
    locked_wt = add_worktree("locked-wt")
    (locked_wt / "locked-untracked.txt").write_text("held\n", encoding="utf-8")
    git(checkout, "worktree", "lock", "--reason", "test lock", str(locked_wt))
    unreadable_wt = add_worktree("unreadable-wt")
    (unreadable_wt / "unreadable-untracked.txt").write_text("held\n", encoding="utf-8")
    # A corrupt index makes `git status` fail while `git log` still works, so
    # the status failure alone has to keep this worktree.
    unreadable_index = Path(git(unreadable_wt, "rev-parse", "--path-format=absolute",
                                "--git-path", "index").strip())
    unreadable_index.write_bytes(b"not an index")

    occupant = None
    occupied_wt = None
    if shutil.which("lsof"):
        occupied_wt = add_worktree("occupied-wt")
        # The occupant blocks on stdin rather than sleeping a fixed span, so
        # its lifetime is not a race against the suite's own runtime. It used
        # to sleep 120 s, which is less than this suite takes whenever lsof is
        # slow -- the load this suite's timeout note is about. The occupant
        # then exited before --remove ran, occupied-wt was vacant, --remove
        # reaped it, and the suite reported the reaper deleting an occupied
        # worktree: its central promise appearing to break, from load alone.
        # The finally below kills it; should this process die without reaching
        # that, the pipe's write end closes, stdin reads EOF, and it exits.
        occupant = subprocess.Popen(
            [sys.executable, "-c", "import sys; sys.stdin.read()"],
            cwd=str(occupied_wt), stdin=subprocess.PIPE,
        )
    else:
        print("SKIP  occupied cases: lsof is not installed on this machine")

    try:
        # --- The report classifies every worktree ---------------------------
        report = run_clean(checkout).stdout
        check("a clean, landed, vacant worktree reports done",
              "done-wt: done" in report, report)
        check("a landed, vacant worktree with an untracked file is done, the file named",
              "dirty-wt: done" in report
              and "discards 1 uncommitted, untracked or ignored file(s): uncommitted.txt"
              in report, report)
        check("a landed, vacant worktree with ignored files is done, the files named",
              "ignored-wt: done" in report and "scratch-state/ledger.md" in report, report)
        mixed_line = next((line for line in report.splitlines()
                           if line.startswith("mixed-wt:")), "")
        check("every file under an untracked or ignored directory is named on its own, "
              "and junk at any depth is not",
              "discards 6 " in mixed_line
              and all(name in mixed_line for name in (
                  "scratch-state/kept-a.md", "scratch-state/deep/kept-b.md",
                  "sub/real.txt", "newdir/one.txt", "newdir/inner/two.txt",
                  "moved-readme.md"))
              and "README.md," not in mixed_line and "DME.md" not in mixed_line
              and ".DS_Store" not in mixed_line and "__pycache__" not in mixed_line,
              mixed_line)
        check("regenerable junk is not named among the discarded files",
              ".DS_Store" not in report and "__pycache__" not in report, report)
        renamed_line = next((line for line in report.splitlines()
                             if line.startswith("renamed-wt:")), "")
        check("a rename in the worktree column names the new path once, and its old path not at all",
              "discards 3 " in renamed_line
              and sorted(files_named_on(renamed_line)) == ["a", "ab", "worktree-moved.md"],
              renamed_line)
        check("one- and two-character file names are named",
              "a" in files_named_on(renamed_line) and "ab" in files_named_on(renamed_line),
              renamed_line)
        check("a rename in the index column names the new path once, and its old path not at all",
              "moved-readme.md" in files_named_on(mixed_line)
              and "README.md" not in files_named_on(mixed_line)
              and len(files_named_on(mixed_line)) == 6, mixed_line)
        many_line = next((line for line in report.splitlines()
                          if line.startswith("many-files-wt:")), "")
        check("past ten files, ten are named and the rest are counted",
              "discards 11 " in many_line and "note-09.txt" in many_line
              and "note-10.txt" not in many_line and many_line.endswith(" and 1 more"),
              many_line)
        ten_line = next((line for line in report.splitlines()
                         if line.startswith("ten-files-wt:")), "")
        check("exactly ten files are all named, with no count of the rest",
              "discards 10 " in ten_line and ten_line.endswith("note-09.txt")
              and " more" not in ten_line, ten_line)
        check("a detached worktree at origin/main is judged landed",
              "detached-landed-wt: done" in report, report)
        check("a detached worktree with a commit beyond origin/main is kept",
              "detached-unlanded-wt: kept" in report
              and "1 commit(s) not on origin/main" in report, report)
        check("a worktree whose files git cannot list is kept",
              "unreadable-wt: kept" in report and "git cannot list its files" in report,
              report)
        check("unlanded commits keep a worktree",
              "unlanded-wt: kept" in report and "not on origin/main" in report, report)
        check("a worktree outside the managed area is kept",
              "outside-wt: kept" in report and "outside the managed area" in report,
              report)
        if occupied_wt is not None:
            check("a live process keeps a worktree",
                  "occupied-wt: kept" in report and "live process" in report, report)
        check("no dead-registration line while every directory exists",
              "git worktree prune" not in report, report)

        # --- Anchoring: a copy run from inside a worktree sees the same repo -
        from_inside = run_clean(dirty_wt).stdout
        check("run from inside a worktree, classifications are unchanged",
              "done-wt: done" in from_inside and "dirty-wt: done" in from_inside
              and "unlanded-wt: kept" in from_inside
              and "outside-wt: kept" in from_inside, from_inside)

        # --- --only-done prints done worktrees and nothing else -------------
        only_done = run_clean(checkout, "--only-done").stdout
        check("--only-done names the done worktree and its removal command",
              "done-wt" in only_done and "--remove" in only_done, only_done)
        check("--only-done names a done worktree holding files, and the files",
              "dirty-wt: done" in only_done and "uncommitted.txt" in only_done,
              only_done)
        check("--only-done stays silent about kept worktrees",
              "unlanded-wt" not in only_done and "outside-wt" not in only_done,
              only_done)
        # Every branch here is still attached to a worktree, so there is
        # nothing to name; the line must be absent rather than empty.
        check("--only-done says nothing about branch refs when none is orphaned",
              ORPHANED_BRANCH_REF_LINE_MARKER not in only_done, only_done)

        # --- An untrustworthy vacancy answer keeps, and says so honestly ----
        # Each case below reaps done-wt against the pre-fix implementation,
        # which read lsof's stdout and never its exit status: no path matched,
        # so it reported vacant and --remove would have deleted the worktree.
        stub_home = scratch / "stub-lsof"

        failed_lsof = run_clean_with_stub_lsof(
            checkout, stub_home / "nonzero", "#!/bin/sh\nexit 1\n").stdout
        check("an lsof that exits nonzero keeps the worktree",
              "done-wt: kept" in failed_lsof, failed_lsof)
        check("a failed vacancy check is reported as untrusted, not as occupancy",
              "done-wt: kept" in failed_lsof
              and "vacancy" in failed_lsof
              and "live process is rooted inside it" not in failed_lsof,
              failed_lsof)

        empty_lsof = run_clean_with_stub_lsof(
            checkout, stub_home / "empty", "#!/bin/sh\nexit 0\n").stdout
        check("an lsof reporting no working directories at all keeps the worktree",
              "done-wt: kept" in empty_lsof and "no working directories" in empty_lsof,
              empty_lsof)

        # The converse, so failing closed does not become ignoring the answer:
        # a listing that names the worktree is occupancy even if lsof exited
        # nonzero, which is the everyday partial-permissions case.
        matching_lsof = run_clean_with_stub_lsof(
            checkout, stub_home / "match",
            f"#!/bin/sh\necho 'n{done_wt.resolve()}'\nexit 1\n").stdout
        check("a path match counts as occupancy even when lsof exits nonzero",
              "done-wt: kept" in matching_lsof
              and "live process is rooted inside it" in matching_lsof,
              matching_lsof)

        # --- No failure to decide removes anything --------------------------
        # Each run below is --remove, against dirty-wt: landed, vacant to a
        # healthy lsof, and holding an untracked file. Each must keep it.
        failed_removal = run_clean_with_stub_lsof(
            checkout, stub_home / "nonzero-remove", "#!/bin/sh\nexit 1\n", "--remove")
        check("--remove with an lsof that exits nonzero removes nothing",
              dirty_wt.exists() and (dirty_wt / "uncommitted.txt").exists()
              and done_wt.exists() and ": removed" not in failed_removal.stdout,
              failed_removal.stdout)
        empty_removal = run_clean_with_stub_lsof(
            checkout, stub_home / "empty-remove", "#!/bin/sh\nexit 0\n", "--remove")
        check("--remove with an lsof that lists nothing removes nothing",
              dirty_wt.exists() and ": removed" not in empty_removal.stdout,
              empty_removal.stdout)
        no_lsof_removal = run_clean_without_lsof(
            checkout, scratch / "path-without-lsof", "--remove")
        check("--remove with lsof missing removes nothing, and says lsof is missing",
              dirty_wt.exists() and ": removed" not in no_lsof_removal.stdout
              and "lsof is not installed" in no_lsof_removal.stdout,
              no_lsof_removal.stdout + no_lsof_removal.stderr)

        clean_module = load_clean_worktrees_module()
        clean_module.VACANCY_CHECK_TIMEOUT_SECONDS = 1
        slow_stub = stub_home / "slow"
        slow_stub.mkdir(parents=True, exist_ok=True)
        (slow_stub / "lsof").write_text("#!/bin/sh\nexec sleep 5\n", encoding="utf-8")
        (slow_stub / "lsof").chmod(0o755)
        saved_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{slow_stub}{os.pathsep}{saved_path}"
        try:
            timed_out_reason = clean_module.worktree_vacancy_keep_reason(dirty_wt)
            timed_out_classification = clean_module.classify(
                dirty_wt, "dirty-wt-branch", checkout)
        finally:
            os.environ["PATH"] = saved_path
        check("an lsof that times out keeps the worktree",
              timed_out_reason == "the vacancy check (lsof) could not be run"
              and timed_out_classification[0] is False,
              f"{timed_out_reason} {timed_out_classification}")

        killed_status_removal = run_clean_with_git_status_killed(
            checkout, scratch / "git-status-killed", "--remove")
        check("--remove with git status killed by a signal removes nothing, and says why",
              dirty_wt.exists() and done_wt.exists()
              and ": removed" not in killed_status_removal.stdout
              and "dirty-wt: kept — git cannot list its files" in killed_status_removal.stdout,
              killed_status_removal.stdout + killed_status_removal.stderr)

        git(checkout, "update-ref", "-d", "refs/remotes/origin/main")
        try:
            no_main_removal = run_clean(checkout, "--remove")
        finally:
            git(checkout, "fetch", "origin")
        check("--remove with origin/main missing removes nothing, and says why",
              dirty_wt.exists() and done_wt.exists()
              and ": removed" not in no_main_removal.stdout
              and "dirty-wt: kept — cannot compare against origin/main"
              in no_main_removal.stdout, no_main_removal.stdout)

        # --- Dead registrations are named, with the prune command ------------
        # A worktree registered under a temp directory leaves a dead entry
        # when the temp area clears (R25, ruled 2026-08-18). Simulate the
        # clearing: delete the directory behind git's back, so the
        # registration outlives it.
        dead_wt = add_worktree("dead-registration-wt", where=scratch)
        shutil.rmtree(dead_wt)
        dead_report = run_clean(checkout).stdout
        dead_line = next((line for line in dead_report.splitlines()
                          if "git worktree prune" in line), "")
        check("a dead registration is named with the prune command",
              "dead-registration-wt" in dead_line, dead_report)
        # dead_line must be non-empty here, or this check would pass against
        # an empty haystack — asserting absence in a line that never printed.
        check("living worktrees are not named on the dead-registration line",
              dead_line != "" and "done-wt" not in dead_line
              and "dirty-wt" not in dead_line, dead_report)
        check("the dead-registration line carries git's own reason",
              "gitdir file points to non-existent location" in dead_line, dead_line)
        dead_only_done = run_clean(checkout, "--only-done").stdout
        check("--only-done carries the dead-registration line (the launchers' boot mode)",
              "dead-registration-wt" in dead_only_done
              and "git worktree prune" in dead_only_done, dead_only_done)

        # A prunable registration whose directory still EXISTS: only its inner
        # .git file is gone. git calls this prunable too, so the report must
        # name it — and must not claim the directory is gone, a condition it
        # never checked. Pruning here discards the registration for a
        # directory still holding uncommitted work, which is why the reason
        # the human reads has to be git's own.
        surviving_wt = add_worktree("dotgit-deleted-wt", where=scratch)
        (surviving_wt / "recoverable-file.txt").write_text("work\n", encoding="utf-8")
        (surviving_wt / ".git").unlink()
        surviving_report = run_clean(checkout).stdout
        surviving_line = next((line for line in surviving_report.splitlines()
                               if "git worktree prune" in line), "")
        check("a prunable registration whose directory survives is named too",
              "dotgit-deleted-wt" in surviving_line, surviving_report)
        check("the line claims git's judgment, never that the directory is gone",
              surviving_line != "" and "directory gone" not in surviving_line
              and surviving_wt.exists(), surviving_line)

        # --- --remove reaps exactly the done worktrees -----------------------
        removal = run_clean(checkout, "--remove")
        check("--remove removes the done worktree",
              not done_wt.exists() and "done-wt: removed" in removal.stdout,
              removal.stdout)
        branches = git(checkout, "branch", "--list", "done-wt-branch")
        check("--remove deletes the reaped worktree's merged branch",
              branches.strip() == "", branches)
        check("--remove names the files before the removal, as files it will discard",
              "dirty-wt: removing it will discard 1 uncommitted, untracked or ignored "
              "file(s): uncommitted.txt" in removal.stdout
              and -1 < removal.stdout.find("dirty-wt: removing it will discard")
              < removal.stdout.find("dirty-wt: removed"), removal.stdout)
        check("--remove names the files it discarded, after the removal succeeded",
              "dirty-wt: discarded with it 1 uncommitted, untracked or ignored file(s): "
              "uncommitted.txt" in removal.stdout
              and -1 < removal.stdout.find("dirty-wt: removed")
              < removal.stdout.find("dirty-wt: discarded with it"), removal.stdout)
        check("--remove removes a landed, vacant worktree with an untracked file",
              not dirty_wt.exists()
              and git(checkout, "branch", "--list", "dirty-wt-branch").strip() == "",
              removal.stdout)
        check("--remove removes a landed, vacant worktree with ignored files",
              not ignored_wt.exists() and "ignored-wt: discarded with it" in removal.stdout,
              removal.stdout)
        check("--remove prints no discard line for a worktree holding only junk",
              "done-wt: discarded" not in removal.stdout, removal.stdout)
        check("--remove keeps every not-done worktree",
              unlanded_wt.exists() and outside_wt.exists()
              and detached_unlanded_wt.exists()
              and (unreadable_wt / "unreadable-untracked.txt").exists()
              and (occupied_wt is None or occupied_wt.exists()),
              removal.stdout)
        check("a locked worktree is not removed, though it is done and holds files",
              (locked_wt / "locked-untracked.txt").exists()
              and "locked-wt: removal FAILED" in removal.stdout
              and "locked-wt: discarded" not in removal.stdout, removal.stdout)
        check("a removal that fails still named its files beforehand",
              "locked-wt: removing it will discard 1 uncommitted, untracked or ignored "
              "file(s): locked-untracked.txt" in removal.stdout, removal.stdout)
        check("--remove exits 1 when a removal failed", removal.returncode == 1,
              str(removal.returncode))
        check("--remove ends a run with failures on the line saying it finished",
              removal.stdout.splitlines()[-1:] == [
                  "clean-worktrees: finished; each failure is named above"],
              removal.stdout)
        check("--remove prints the finished line once, after every failure line",
              removal.stdout.count("clean-worktrees: finished; each failure is named above") == 1,
              removal.stdout)
        git(checkout, "worktree", "unlock", str(locked_wt))
        check("--remove reports the dead registration too",
              "dead-registration-wt" in removal.stdout
              and "git worktree prune" in removal.stdout, removal.stdout)
        still_listed = git(checkout, "worktree", "list", "--porcelain")
        check("the dead registration survives --remove — the prune stays deliberate",
              "dead-registration-wt" in still_listed, still_listed)

        # --- Branch refs whose worktree is already gone ----------------------
        # Removing a worktree does not remove its branch, and nothing swept a
        # branch left behind: list_worktrees() enumerates worktrees, not refs.
        # Counted 2026-08-31, 41 of this repository's 51 local branches had no
        # worktree — none of them landed yet, each one landing eventually.
        #
        # Ordering inside this block is load-bearing. The successful --remove
        # below must run BEFORE origin/main is advanced: once the checkout's
        # local main lags, git branch -d refuses even a ref that is fully on
        # origin/main, which is the refusal case at the end.

        # Attached to nothing, carrying nothing origin/main lacks.
        git(checkout, "branch", "--no-track", "landed-orphan-branch", "origin/main")
        # Attached to nothing, but carrying a commit origin/main lacks.
        git(checkout, "branch", "--no-track", "unlanded-orphan-branch",
            "unlanded-wt-branch")
        # A remote-tracking ref with no worktree, trivially inside origin/main:
        # a candidate the moment the sweep looks outside refs/heads/.
        git(checkout, "push", "origin", "main:refs/heads/landed-elsewhere")
        # A detached worktree: git's porcelain says `detached` where the branch
        # line would be, so it names no branch of its own.
        detached_wt = scratch / "detached-wt"
        git(checkout, "worktree", "add", "--detach", str(detached_wt), "origin/main")
        # A tag sharing a live worktree's branch name. %(refname:short) answers
        # `heads/<name>` for a branch a tag shadows, which matches nothing in
        # the attached set — so the sweep would name a branch that is in use.
        shadowed_wt = scratch / "tag-shadowed-name-wt"
        git(checkout, "worktree", "add", "-b", "tag-shadowed-name",
            str(shadowed_wt), "origin/main")
        git(checkout, "tag", "tag-shadowed-name", "origin/main")

        orphan_report = run_clean(checkout).stdout
        named = orphaned_branch_refs_named(orphan_report)
        check("a landed branch with no worktree is named",
              "landed-orphan-branch" in named, orphan_report)
        check("the orphaned-ref line carries the removal command",
              "scripts/clean-worktrees.py --remove" in "\n".join(
                  line for line in orphan_report.splitlines()
                  if line.startswith(ORPHANED_BRANCH_REF_LINE_MARKER)),
              orphan_report)
        check("a branch carrying commits origin/main lacks is not named",
              "unlanded-orphan-branch" not in named, orphan_report)
        # The precondition matters: without it the case passes vacuously
        # against a branch that would have been excluded as unlanded anyway.
        check("a branch a live worktree holds is not named, though it is landed",
              "outside-wt-branch" not in named
              and git(checkout, "rev-list", "--count",
                      "origin/main..outside-wt-branch").strip() == "0",
              orphan_report)
        check("a tag shadowing an attached branch's name does not orphan it",
              "tag-shadowed-name" not in named
              and "heads/tag-shadowed-name" not in named, orphan_report)
        check("the branch checked out in the main checkout is not named",
              "main" not in named
              and git(checkout, "rev-list", "--count",
                      "origin/main..main").strip() == "0",
              orphan_report)
        check("a detached worktree names no branch and suppresses no ref",
              "landed-orphan-branch" in named and "detached" not in named
              and not any(name.startswith("/") for name in named),
              orphan_report)
        check("remote-tracking refs are never named",
              not any(name.startswith("origin/") for name in named)
              and "landed-elsewhere" not in named, orphan_report)

        orphan_only_done = run_clean(checkout, "--only-done").stdout
        check("--only-done carries the orphaned-ref line (the launchers' boot mode)",
              "landed-orphan-branch" in orphaned_branch_refs_named(orphan_only_done),
              orphan_only_done)

        orphan_removal = run_clean(checkout, "--remove")
        check("--remove deletes the orphaned landed ref",
              git(checkout, "branch", "--list", "landed-orphan-branch").strip() == ""
              and "landed-orphan-branch" in orphan_removal.stdout,
              orphan_removal.stdout)
        check("--remove leaves a ref carrying commits origin/main lacks",
              git(checkout, "branch", "--list",
                  "unlanded-orphan-branch").strip() != "",
              orphan_removal.stdout)
        check("--remove leaves the branches live worktrees hold",
              git(checkout, "branch", "--list", "outside-wt-branch").strip() != ""
              and git(checkout, "branch", "--list",
                      "tag-shadowed-name").strip() != "",
              orphan_removal.stdout)
        check("--remove exits 0 when every named ref was deletable",
              orphan_removal.returncode == 0, str(orphan_removal.returncode))
        check("a run with no failure prints no line saying it finished with failures",
              "clean-worktrees: finished" not in orphan_removal.stdout, orphan_removal.stdout)

        # A local main behind origin/main is the ordinary state of a checkout
        # after somebody else's work lands, and in it git branch -d refuses a
        # ref that IS fully on origin/main: -d asks about HEAD and about the
        # ref's upstream, never about origin/main. The refusal is git's second
        # opinion, so the ref stays — but it is reported and counted, because a
        # sweep that silently keeps failing is a sweep nobody knows to fix.
        advance_wt = add_worktree("advance-wt", where=scratch)
        (advance_wt / "advanced.txt").write_text("landed elsewhere\n", encoding="utf-8")
        git(advance_wt, "add", "-A")
        git(advance_wt, "commit", "-m", "work that lands on origin/main")
        git(advance_wt, "push", "origin", "advance-wt-branch:main")
        git(checkout, "fetch", "origin")
        git(checkout, "branch", "--no-track",
            "landed-ahead-of-local-main", "origin/main")
        refused = run_clean(checkout, "--remove")
        check("a refused ref deletion is reported, not swallowed",
              "landed-ahead-of-local-main" in refused.stdout
              and "FAILED" in refused.stdout, refused.stdout)
        check("a refused ref deletion exits 1", refused.returncode == 1,
              str(refused.returncode))
        check("a refused ref deletion leaves the ref in place",
              git(checkout, "branch", "--list",
                  "landed-ahead-of-local-main").strip() != "", refused.stdout)
    finally:
        if occupant is not None:
            occupant.kill()
            occupant.wait()


def run_clean_with_claude_home(repo, home, *flags, claude_config_directory=None):
    """Run the reaper with HOME, and CLAUDE_CONFIG_DIR when given, pointed at
    a scratch directory, so the subagent transcripts it reads are this suite's
    and never the machine's."""
    environment = dict(os.environ)
    environment["HOME"] = str(home)
    environment.pop("CLAUDE_CONFIG_DIR", None)
    if claude_config_directory is not None:
        environment["CLAUDE_CONFIG_DIR"] = str(claude_config_directory)
    return subprocess.run(
        [sys.executable, str(CLEAN_SCRIPT), "--repo", str(repo), *flags],
        capture_output=True, text=True, check=False, env=environment,
    )


# --- An Agent-tool subagent's worktree is kept while its subagent may live --
# The subagent runs inside its parent claude process, whose working directory
# is the seat home, so the vacancy check sees nothing inside its worktree
# between Bash calls (measured on ned-box 2026-09-23). Its transcript is the
# evidence of life, and the worktree's own age stands in when there is none.
with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch)
    checkout = scratch / "checkout"
    origin = scratch / "origin.git"
    checkout.mkdir()
    git(checkout, "init", "-b", "main")
    git(checkout, "config", "user.email", "test@test.invalid")
    git(checkout, "config", "user.name", "clean-worktrees test")
    (checkout / "README.md").write_text("# scratch\n", encoding="utf-8")
    git(checkout, "add", "-A")
    git(checkout, "commit", "-m", "seed")
    subprocess.run(["git", "init", "--bare", str(origin)],
                   capture_output=True, check=True)
    git(checkout, "remote", "add", "origin", str(origin))
    git(checkout, "push", "-u", "origin", "main")
    managed = checkout / ".claude" / "worktrees"
    managed.mkdir(parents=True)
    fake_home = scratch / "home"
    config_directory = scratch / "claude-config"
    two_hours_ago = time.time() - 7200

    def add_agent_worktree(name, aged):
        path = managed / name
        git(checkout, "worktree", "add", "-b", f"worktree-{name}", str(path), "origin/main")
        if aged:
            os.utime(path / ".git", (two_hours_ago, two_hours_ago))
        return path

    def write_transcript(base, agent_id, aged):
        transcript = (base / "projects" / "-home-seat" / "session-uuid" / "subagents"
                      / f"agent-{agent_id}.jsonl")
        transcript.parent.mkdir(parents=True, exist_ok=True)
        transcript.write_text("{}\n", encoding="utf-8")
        if aged:
            os.utime(transcript, (two_hours_ago, two_hours_ago))

    just_made = add_agent_worktree("agent-aaaaaaaaaaaaaaaa1", aged=False)
    talking = add_agent_worktree("agent-aaaaaaaaaaaaaaaa2", aged=True)
    write_transcript(fake_home / ".claude", "aaaaaaaaaaaaaaaa2", aged=False)
    quiet = add_agent_worktree("agent-aaaaaaaaaaaaaaaa3", aged=True)
    write_transcript(fake_home / ".claude", "aaaaaaaaaaaaaaaa3", aged=True)
    configured = add_agent_worktree("agent-aaaaaaaaaaaaaaaa4", aged=True)
    write_transcript(config_directory, "aaaaaaaaaaaaaaaa4", aged=False)
    git(checkout, "worktree", "add", "-b", "fresh-session-branch",
        str(managed / "fresh-session-wt"), "origin/main")

    report = run_clean_with_claude_home(checkout, fake_home).stdout
    check("an Agent-tool subagent's worktree made a moment ago is kept",
          "agent-aaaaaaaaaaaaaaaa1: kept" in report and "subagent" in report, report)
    check("an Agent-tool subagent's worktree whose transcript was just written is kept",
          "agent-aaaaaaaaaaaaaaaa2: kept" in report, report)
    check("an Agent-tool subagent's worktree quiet for over an hour is done",
          "agent-aaaaaaaaaaaaaaaa3: done" in report, report)
    check("a worktree not named agent-<id> is not judged by its age",
          "fresh-session-wt: done" in report, report)
    check("without CLAUDE_CONFIG_DIR, a transcript under it is not read",
          "agent-aaaaaaaaaaaaaaaa4: done" in report, report)

    configured_report = run_clean_with_claude_home(
        checkout, fake_home, claude_config_directory=config_directory).stdout
    check("with CLAUDE_CONFIG_DIR set, the subagent transcripts are read under it",
          "agent-aaaaaaaaaaaaaaaa4: kept" in configured_report, configured_report)

    removal = run_clean_with_claude_home(checkout, fake_home, "--remove")
    check("--remove keeps both live subagents' worktrees",
          just_made.exists() and talking.exists(), removal.stdout)
    check("--remove removes the quiet subagent's worktree and its branch",
          not quiet.exists()
          and git(checkout, "branch", "--list", "worktree-agent-aaaaaaaaaaaaaaaa3").strip() == "",
          removal.stdout)


# --- A run killed mid-removal has already shown what it announced ---------
# The daily job runs the cleaner without -u, writing to a log. A git that
# hangs on the second removal stands in for a run killed partway; every
# line printed before the hang must be readable while the run is alive.
with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch)
    checkout = scratch / "checkout"
    origin = scratch / "origin.git"
    checkout.mkdir()
    git(checkout, "init", "-b", "main")
    git(checkout, "config", "user.email", "test@test.invalid")
    git(checkout, "config", "user.name", "clean-worktrees test")
    (checkout / "README.md").write_text("# scratch\n", encoding="utf-8")
    git(checkout, "add", "-A")
    git(checkout, "commit", "-m", "seed")
    subprocess.run(["git", "init", "--bare", str(origin)], capture_output=True, check=True)
    git(checkout, "remote", "add", "origin", str(origin))
    git(checkout, "push", "-u", "origin", "main")
    managed = checkout / ".claude" / "worktrees"
    managed.mkdir(parents=True)
    for name in ("flush-first-wt", "flush-second-wt"):
        path = managed / name
        git(checkout, "worktree", "add", "-b", f"{name}-branch", str(path), "origin/main")
        (path / f"{name}.txt").write_text("held\n", encoding="utf-8")

    stub_directory = scratch / "hanging-git"
    stub_directory.mkdir()
    counter = scratch / "removal-count"
    (stub_directory / "git").write_text(
        "#!/bin/sh\n"
        'case " $* " in *" worktree remove "*)\n'
        f'  echo x >> "{counter}"\n'
        f'  if [ "$(wc -l < "{counter}")" -ge 2 ]; then exec sleep 60; fi ;;\n'
        "esac\n"
        f'exec {shutil.which("git")} "$@"\n', encoding="utf-8")
    (stub_directory / "git").chmod(0o755)
    environment = dict(os.environ)
    environment["PATH"] = f"{stub_directory}{os.pathsep}{environment.get('PATH', '')}"
    environment.pop("PYTHONUNBUFFERED", None)
    hanging = subprocess.Popen(
        [sys.executable, str(CLEAN_SCRIPT), "--repo", str(checkout), "--remove"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=environment,
        start_new_session=True,
    )
    seen = read_lines_until(
        hanging,
        lambda lines: (sum(": removing it will discard " in line for line in lines) == 2
                       and sum(": discarded with it " in line for line in lines) == 1),
        60)
    os.killpg(hanging.pid, 9)
    hanging.wait()
    burst = subprocess.Popen(
        [sys.executable, "-c",
         "import sys, time\n"
         "sys.stdout.write('one\\ntwo\\nthree\\nfour\\n'); sys.stdout.flush()\n"
         "time.sleep(30)\n"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True)
    time.sleep(1)
    burst_lines = read_lines_until(burst, lambda lines: len(lines) == 4, 5)
    os.killpg(burst.pid, 9)
    burst.wait()
    check("the reader returns every line a child wrote in one burst, while it is alive",
          burst_lines == ["one", "two", "three", "four"], str(burst_lines))
    confirmed = [line for line in seen if ": discarded with it " in line]
    announced = [line for line in seen if ": removing it will discard " in line]
    check("a run stopped mid-removal has already shown the first removal, confirmed",
          len(confirmed) == 1 and any(": removed" in line for line in seen), "\n".join(seen))
    check("a run stopped mid-removal has already shown what the stopped removal announced",
          len(announced) == 2
          and confirmed[0].partition(":")[0] != announced[-1].partition(":")[0]
          if confirmed and announced else False, "\n".join(seen))

# git worktree list without -z ends each attribute at a newline, so a newline
# in a worktree path or a lock reason was read as the start of another line.
with tempfile.TemporaryDirectory() as scratch:
    # git reports a worktree's resolved path; macOS's temporary directory sits
    # under the /var -> /private/var link, so compare against the resolved one.
    scratch = Path(scratch).resolve()
    checkout = scratch / "checkout"
    checkout.mkdir()
    git(checkout, "init", "-b", "main")
    git(checkout, "config", "user.email", "test@test.invalid")
    git(checkout, "config", "user.name", "clean-worktrees test")
    (checkout / "README.md").write_text("# scratch\n", encoding="utf-8")
    git(checkout, "add", "-A")
    git(checkout, "commit", "-m", "seed")
    git(checkout, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(checkout, "branch", "unattached-landed")
    newline_path = scratch / "two\nlines-wt"
    git(checkout, "worktree", "add", "-b", "newline-branch", str(newline_path), "HEAD")
    git(checkout, "worktree", "lock", "--reason",
        "held\nbranch refs/heads/unattached-landed", str(newline_path))
    gone_path = scratch / "gone-wt"
    git(checkout, "worktree", "add", "-b", "gone-branch", str(gone_path), "HEAD")
    shutil.rmtree(gone_path)
    module = load_clean_worktrees_module()
    listed = module.list_worktrees(checkout, checkout)
    check("a worktree path holding a newline is listed whole, with its branch",
          (newline_path, "newline-branch") in listed, str(listed))
    orphaned = module.branch_refs_with_no_worktree_fully_on_main(checkout)
    check("a lock reason that reads like a branch line does not attach that branch",
          "unattached-landed" in orphaned, str(orphaned))
    dead = module.dead_worktree_registrations(checkout)
    check("a prunable registration is reported with git's reason",
          [path for path, reason in dead] == [str(gone_path)] and dead[0][1] != "no reason given",
          str(dead))

# --- Records whose home is the log-store are shipped before the removal ---
with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch).resolve()
    checkout = scratch / "checkout"
    origin = scratch / "origin.git"
    checkout.mkdir()
    git(checkout, "init", "-b", "main")
    git(checkout, "config", "user.email", "test@test.invalid")
    git(checkout, "config", "user.name", "clean-worktrees test")
    (checkout / "README.md").write_text("# scratch\n", encoding="utf-8")
    (checkout / ".gitignore").write_text(
        "cold-read-records/\nsanity-check-records/\n", encoding="utf-8")
    git(checkout, "add", "-A")
    git(checkout, "commit", "-m", "seed")
    subprocess.run(["git", "init", "--bare", str(origin)], capture_output=True, check=True)
    git(checkout, "remote", "add", "origin", str(origin))
    git(checkout, "push", "-u", "origin", "main")
    managed = checkout / ".claude" / "worktrees"
    managed.mkdir(parents=True)
    cold_read_record_name = "foo-2026-10-19"
    sanity_check_record_name = "bar-2026-10-19"

    def worktree_holding_records(name):
        path = managed / name
        git(checkout, "worktree", "add", "-b", f"{name}-branch", str(path), "origin/main")
        cold_read_record = path / "cold-read-records" / cold_read_record_name
        cold_read_record.mkdir(parents=True)
        (cold_read_record / "fast-read.md").write_text("report\n", encoding="utf-8")
        sanity_check_record = path / "sanity-check-records" / sanity_check_record_name
        sanity_check_record.mkdir(parents=True)
        (sanity_check_record / "cell-1.md").write_text("cell\n", encoding="utf-8")
        return path

    def run_clean_shipping_to(destination, path_prefix=None, *flags):
        environment = dict(os.environ)
        environment[SHIP_DESTINATION_VARIABLE] = destination
        if path_prefix is not None:
            environment["PATH"] = f"{path_prefix}{os.pathsep}{environment['PATH']}"
        return subprocess.run(
            [sys.executable, str(CLEAN_SCRIPT), "--repo", str(checkout), *flags],
            capture_output=True, text=True, check=False, env=environment)

    def remove_worktree_for_next_case(path):
        # A case that wrongly removed the worktree has already failed; the next cases still run.
        if path.exists():
            git(checkout, "worktree", "remove", "--force", str(path))

    # The report modes name the records and ship nothing.
    store = scratch / "store"
    reported_wt = worktree_holding_records("reported-wt")
    report = run_clean_shipping_to(str(store / "cold-read-records")).stdout
    reported_line = next((line for line in report.splitlines()
                          if line.startswith("reported-wt:")), "")
    check("the report names a done worktree's records and says --remove ships them first",
          "reported-wt: done" in reported_line
          and "--remove first ships its 2 record(s)" in reported_line
          and f"cold-read-records/{cold_read_record_name}" in reported_line
          and f"sanity-check-records/{sanity_check_record_name}" in reported_line,
          reported_line)
    check("the report ships nothing", not store.exists(), str(list(store.rglob("*"))))
    remove_worktree_for_next_case(reported_wt)

    # The loss: --remove deleted a record the log-store did not hold.
    shipped_wt = worktree_holding_records("shipped-wt")
    empty_record = shipped_wt / "cold-read-records" / "empty-2026-10-19"
    empty_record.mkdir()
    shipped = run_clean_shipping_to(str(store / "cold-read-records"), None, "--remove")
    check("--remove ships a done worktree's cold-read-record to the log-store before removing it",
          (store / "cold-read-records" / cold_read_record_name / "fast-read.md").is_file()
          and not shipped_wt.exists(), shipped.stdout + shipped.stderr)
    check("--remove ships a done worktree's sanity-check record to the log-store before removing it",
          (store / "sanity-check-records" / sanity_check_record_name / "cell-1.md").is_file(),
          shipped.stdout + shipped.stderr)
    check("--remove prints each shipper's line and an empty record directory is not shipped",
          f"shipped-wt: shipped: {cold_read_record_name}" in shipped.stdout
          and f"shipped-wt: shipped: {sanity_check_record_name}" in shipped.stdout
          and not (store / "cold-read-records" / "empty-2026-10-19").exists()
          and shipped.returncode == 0, shipped.stdout + shipped.stderr)

    # A worktree holding only one kind of record directory.
    sanity_only_wt = worktree_holding_records("sanity-only-wt")
    shutil.rmtree(sanity_only_wt / "cold-read-records")
    sanity_only_store = scratch / "sanity-only-store"
    sanity_only = run_clean_shipping_to(
        str(sanity_only_store / "cold-read-records"), None, "--remove")
    check("--remove ships a sanity-check record from a worktree without cold-read-records/",
          (sanity_only_store / "sanity-check-records" / sanity_check_record_name
           / "cell-1.md").is_file() and not sanity_only_wt.exists(),
          sanity_only.stdout + sanity_only.stderr)

    # ned-box cannot be reached: ssh and rsync exit 255, as the shipper's own tests stub them.
    unreachable_stubs = scratch / "unreachable-stubs"
    unreachable_stubs.mkdir()
    for tool in ("ssh", "rsync"):
        (unreachable_stubs / tool).write_text("#!/bin/sh\nexit 255\n", encoding="utf-8")
        (unreachable_stubs / tool).chmod(0o755)
    unreachable_wt = worktree_holding_records("unreachable-wt")
    unreachable = run_clean_shipping_to(
        "nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records",
        unreachable_stubs, "--remove")
    check("--remove keeps a worktree whose record fails to ship, exits 1, and says why",
          unreachable_wt.exists()
          and (unreachable_wt / "cold-read-records" / cold_read_record_name / "fast-read.md").is_file()
          and "unreachable-wt: record shipment FAILED, worktree kept — removing it would delete "
          "a record the log-store does not hold" in unreachable.stdout
          and "FAILED:" in unreachable.stdout and unreachable.returncode == 1
          and "unreachable-wt: removed" not in unreachable.stdout,
          unreachable.stdout + unreachable.stderr)
    check("--remove prints each failed shipment's line once, inside a record shipment FAILED line "
          "of its own",
          unreachable.stdout.count("FAILED:") == 2
          and len([line for line in unreachable.stdout.splitlines()
                   if line.startswith("unreachable-wt: record shipment FAILED")
                   and line.count("FAILED:") == 1]) == 2
          and "unreachable-wt: FAILED" not in unreachable.stdout,
          unreachable.stdout)
    check("--remove tells a worktree whose records failed to ship that the next --remove retries, "
          "and gives no rename step when no record was refused",
          "unreachable-wt: for each record whose line does not start REFUSED:, do nothing now: "
          "the next scripts/clean-worktrees.py --remove, daily or at a handoff, ships the record again; "
          "if the record fails the same way there, fix the cause its line names"
          in unreachable.stdout
          and "whose line starts REFUSED:" not in unreachable.stdout,
          unreachable.stdout)
    unreachable_lines = unreachable.stdout.splitlines()
    finished_line = "clean-worktrees: finished; each failure is named above"
    check("--remove names each unshipped record on a FAILED line before the finished line, "
          "and those are the run's only FAILED lines",
          finished_line in unreachable_lines
          and [line for line in unreachable_lines if "FAILED" in line]
          == [line for line in unreachable_lines[:unreachable_lines.index(finished_line)]
              if line.startswith("unreachable-wt: record shipment FAILED")],
          unreachable.stdout)
    remove_worktree_for_next_case(unreachable_wt)

    # A record the store holds with other bytes is a second read: refused, so the worktree stays.
    refused_store = scratch / "refused-store"
    stored_record = refused_store / "cold-read-records" / cold_read_record_name
    stored_record.mkdir(parents=True)
    (stored_record / "fast-read.md").write_text("another read's report\n", encoding="utf-8")
    refused_wt = worktree_holding_records("refused-wt")
    refused = run_clean_shipping_to(str(refused_store / "cold-read-records"), None, "--remove")
    check("--remove keeps a worktree whose record the log-store refuses, and exits 1",
          refused_wt.exists() and "REFUSED:" in refused.stdout
          and "refused-wt: record shipment FAILED, worktree kept — " in refused.stdout
          and refused.returncode == 1,
          refused.stdout + refused.stderr)
    check("--remove tells a worktree whose record was refused to rename it, and gives no retry "
          "step when every unshipped record was refused",
          "refused-wt: for each record whose line starts REFUSED:, rename its directory as that "
          "line says; the next scripts/clean-worktrees.py --remove then ships it and removes "
          "the worktree" in refused.stdout
          and "whose line does not start REFUSED:" not in refused.stdout,
          refused.stdout)
    remove_worktree_for_next_case(refused_wt)

    # A shipper that dies before printing its line: a store path under a regular file cannot be made.
    not_a_directory = scratch / "not-a-directory"
    not_a_directory.write_text("a file\n", encoding="utf-8")
    silent_wt = worktree_holding_records("silent-wt")
    silent = run_clean_shipping_to(str(not_a_directory / "cold-read-records"), None, "--remove")
    check("--remove keeps a worktree whose shipper printed nothing, and says so",
          silent_wt.exists() and "the shipper printed nothing (exit 1)" in silent.stdout
          and "silent-wt: record shipment FAILED, worktree kept — " in silent.stdout
          and silent.returncode == 1,
          silent.stdout + silent.stderr)
    check("--remove carries a silent shipper's last error line into the kept line",
          "the shipper printed nothing (exit 1): " in silent.stdout
          and silent.stderr.strip().splitlines()[-1] in silent.stdout,
          silent.stdout + silent.stderr)
    remove_worktree_for_next_case(silent_wt)

check("no run of the suite shipped into the store every run defaults to",
      not any(Path(_ship_store_for_every_run).iterdir()),
      str(list(Path(_ship_store_for_every_run).rglob("*"))))

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
