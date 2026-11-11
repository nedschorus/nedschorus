#!/usr/bin/env python3
"""Tests for clean-worktrees.py.

Builds a scratch repository with an origin remote and one worktree per
classification, each with an owner file naming an agent-session whose
`claude` process has stopped unless the case needs another owner, then
asserts the report names each correctly and that --remove reaps exactly the
done ones. A done worktree is removed whatever files it holds; its
uncommitted, untracked and ignored files are named before it is removed, and
a stopped owner's uncommitted and untracked files go to a work-snapshot
first.

Every way the decision can fail — origin/main missing, git unable to list a
worktree's files, lsof missing, timing out or failing — is run under
--remove against a worktree holding an untracked file, and must keep it.

The vacancy check's unusable-answer cases cannot be produced by a real lsof
on a healthy machine, so they run the reaper with a stub lsof first on PATH.
Those cases guard the reaper's central promise — ambiguity keeps, never
reaps — which a worktree holding someone's uncommitted work depends on.

The cleaner lists pull requests with gh. Every run here finds this suite's
own gh first on PATH, which prints the JSON in FAKE_GH_PULL_REQUESTS, keeping
only the fields named after --json, or an empty list, or fails with exit FAKE_GH_EXIT_CODE, and never reaches GitHub.

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

A section covers the branch refs whose worktree is already gone: refs
attached to nothing, refs still carrying unlanded work, refs a live worktree
holds, the local main, a tag shadowing a branch name, remote-tracking refs,
and a git branch -d refusal — the ordinary state of a checkout whose local
main lags origin/main.

A section covers the owner rules under a scratch HOME: an owner that runs, an
agent-session's `claude` process standing in as a helper process, an
agent-seat's handoff-supervisor as a helper process running a file named
handoff-supervisor.py; a merged, a closed, an open and an earlier pull
request on a reused branch name; an owner whose state cannot be read, an
owner file that cannot be read, gh failing, and a work-snapshot or a branch
for commits on no branch that cannot be written, each of which keeps the
worktree; and the count lines.

A section covers the records whose home is the log-store: before --remove
removes a done worktree it ships the worktree's cold-read-records and
sanity-check records, and keeps the worktree when a record fails to ship, is
refused, or its shipper prints nothing. The shippers run for real, into a
scratch store named by COLD_READ_RECORD_SHIP_DESTINATION; the failure to reach
ned-box is a stub ssh and rsync that exit 255.

A section stops a real rebase on a conflict in a worktree under
.claude/worktrees/, with HEAD detached at origin/main, and --remove must keep
it; so must a worktree whose git directory git cannot locate.

Run: python3 scripts/clean-worktrees-test.py
"""

import atexit
import importlib.util
import io
import json
import os
import select
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import types
from datetime import datetime, timedelta, timezone
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

REMOVALS_LOG_OVERRIDE_VARIABLE = "CLEAN_WORKTREES_REMOVED_WORKTREES_AND_DELETED_BRANCHES_LOG_FILE_OVERRIDE"
# Without this, every --remove run in the suite would append to the real log-store's log of removals.
_removals_log_for_every_run = tempfile.mkdtemp(prefix="clean-worktrees-test-removals-log-")
atexit.register(shutil.rmtree, _removals_log_for_every_run, ignore_errors=True)
os.environ[REMOVALS_LOG_OVERRIDE_VARIABLE] = str(Path(_removals_log_for_every_run) / "log.txt")

TASK_LISTS_DIRECTORY_OVERRIDE_VARIABLE = "CLEAN_WORKTREES_TASK_LISTS_DIRECTORY_OVERRIDE"
# Without this, every run would judge the machine's open restored-branch tasks against this suite's
# scratch clones, and fail on any one whose restore commit a scratch clone lacks.
_task_lists_for_every_run = tempfile.mkdtemp(prefix="clean-worktrees-test-task-lists-")
atexit.register(shutil.rmtree, _task_lists_for_every_run, ignore_errors=True)
os.environ[TASK_LISTS_DIRECTORY_OVERRIDE_VARIABLE] = _task_lists_for_every_run

# Every run finds this gh first: it prints FAKE_GH_PULL_REQUESTS, an empty list by default, or fails
# with exit FAKE_GH_EXIT_CODE, so no run reaches GitHub. Like the real gh, it prints only the fields
# named after --json, so a field the cleaner forgets to ask for is missing from what it reads.
_fake_gh_directory = tempfile.mkdtemp(prefix="clean-worktrees-test-fake-gh-")
atexit.register(shutil.rmtree, _fake_gh_directory, ignore_errors=True)
FAKE_GH = Path(_fake_gh_directory) / "gh"
FAKE_GH.write_text(
    f"#!{sys.executable}\n"
    "import json, os, sys\n"
    "if os.environ.get('FAKE_GH_EXIT_CODE'):\n"
    "    print('gh: stand-in listing failure', file=sys.stderr)\n"
    "    sys.exit(int(os.environ['FAKE_GH_EXIT_CODE']))\n"
    "pull_requests = json.loads(os.environ.get('FAKE_GH_PULL_REQUESTS') or '[]')\n"
    "if '--json' in sys.argv:\n"
    "    fields = sys.argv[sys.argv.index('--json') + 1].split(',')\n"
    "    pull_requests = [{f: p[f] for f in fields if f in p} for p in pull_requests]\n"
    "print(json.dumps(pull_requests))\n", encoding="utf-8")
FAKE_GH.chmod(0o755)
os.environ["PATH"] = f"{_fake_gh_directory}{os.pathsep}{os.environ.get('PATH', '')}"
os.environ.pop("FAKE_GH_PULL_REQUESTS", None)
os.environ.pop("FAKE_GH_EXIT_CODE", None)

WORKTREE_OWNER_FILE_NAME = "worktree-owner.json"


def owner_file_path(worktree):
    completed = subprocess.run(["git", "-C", str(worktree), "rev-parse", "--absolute-git-dir"],
                               capture_output=True, text=True, check=True)
    return Path(completed.stdout.strip()) / WORKTREE_OWNER_FILE_NAME


def stopped_agent_session_owner_key():
    """An owner key of this platform's form whose process is not running."""
    if sys.platform.startswith("linux"):
        # A boot id that is not this boot's.
        return "0" * 32 + "-1-1"
    return "999999-1"


def give_owner(worktree, record):
    owner_file_path(worktree).write_text(json.dumps(record) + "\n", encoding="utf-8")
    return worktree


def give_stopped_owner(worktree):
    return give_owner(worktree, {"owner_kind": "agent-session", "agent_seat": "test-seat",
                                 "owner_key": stopped_agent_session_owner_key()})


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


def raised_by(call):
    """The exception the call raised, or None."""
    try:
        call()
    except Exception as error:
        return error
    return None


def text_or_none(path):
    """The file's text, or None when it is missing, so a check whose file was never written fails
    its own case instead of ending the test file."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


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
    (stub_directory / "gh").symlink_to(FAKE_GH)
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

    def add_worktree(name, where=None, owner=True):
        path = (where or managed) / name
        git(checkout, "worktree", "add", "-b", f"{name}-branch", str(path), "origin/main")
        return give_stopped_owner(path) if owner else path

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
    outside_wt = add_worktree("outside-wt", where=scratch, owner=False)
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
    give_stopped_owner(detached_landed_wt)
    detached_unlanded_wt = managed / "detached-unlanded-wt"
    git(checkout, "worktree", "add", "--detach", str(detached_unlanded_wt), "origin/main")
    give_stopped_owner(detached_unlanded_wt)
    (detached_unlanded_wt / "detached-work.txt").write_text("work\n", encoding="utf-8")
    git(detached_unlanded_wt, "add", "-A")
    git(detached_unlanded_wt, "commit", "-m", "unlanded detached work")
    locked_wt = add_worktree("locked-wt")
    (locked_wt / "locked-untracked.txt").write_text("held\n", encoding="utf-8")
    git(checkout, "worktree", "lock", "--reason", "test lock", str(locked_wt))
    # A directory whose files git cannot delete, so `git worktree remove --force` fails partway.
    stuck_wt = add_worktree("stuck-wt")
    (stuck_wt / "scratch-state").mkdir()
    (stuck_wt / "scratch-state" / "stuck.md").write_text("held\n", encoding="utf-8")
    (stuck_wt / "scratch-state").chmod(0o500)
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
        check("a detached worktree with a commit beyond origin/main, whose owner has stopped, is done, "
              "and --remove first puts the commit on a branch of its own",
              "detached-unlanded-wt: done" in report
              and "--remove first puts its 1 commit(s) on no branch on the new branch "
                  "worktree-cleaner-detached-commits-detached-unlanded-wt-" in report, report)
        check("a worktree whose uncommitted changes git cannot list is kept",
              "unreadable-wt: kept — git cannot list its uncommitted changes" in report, report)
        check("commits on a branch with no pull request do not keep a worktree whose owner has "
              "stopped: the branch keeps them",
              "unlanded-wt: done" in report and "has stopped" in report, report)
        check("a worktree with no owner file is kept, wherever it is",
              "outside-wt: kept — it has no owner file" in report, report)
        check("a locked worktree is kept, naming its lock reason",
              "locked-wt: kept — locked with git worktree lock (test lock)" in report, report)
        if occupied_wt is not None:
            check("a live process keeps a worktree",
                  "occupied-wt: kept" in report and "live process" in report, report)
        check("no dead-registration line while every directory exists",
              "git worktree prune" not in report, report)

        # --- Anchoring: a copy run from inside a worktree sees the same repo -
        from_inside = run_clean(dirty_wt).stdout
        check("run from inside a worktree, classifications are unchanged",
              "done-wt: done" in from_inside and "dirty-wt: done" in from_inside
              and "unlanded-wt: done" in from_inside
              and "outside-wt: kept" in from_inside, from_inside)

        # --- --only-done prints done worktrees and nothing else -------------
        only_done = run_clean(checkout, "--only-done").stdout
        check("--only-done names the done worktree and its removal command",
              "done-wt" in only_done and "--remove" in only_done, only_done)
        check("--only-done names a done worktree holding files, and the files",
              "dirty-wt: done" in only_done and "uncommitted.txt" in only_done,
              only_done)
        check("--only-done stays silent about kept worktrees, and prints no count line",
              "locked-wt" not in only_done and "outside-wt" not in only_done
              and "worktree counts:" not in only_done, only_done)
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
            listed = {path.resolve(): (branch, record)
                      for path, branch, record in clean_module.list_worktrees(checkout, checkout)}
            timed_out_classification = clean_module.classify(
                dirty_wt, *listed[dirty_wt.resolve()], clean_module.PullRequestsByHeadBranchLazyCache(checkout))
        finally:
            os.environ["PATH"] = saved_path
        check("an lsof that times out keeps the worktree",
              timed_out_reason == "the vacancy check (lsof) could not be run"
              and timed_out_classification.done is False,
              f"{timed_out_reason} {timed_out_classification}")

        killed_status_removal = run_clean_with_git_status_killed(
            checkout, scratch / "git-status-killed", "--remove")
        check("--remove with git status killed by a signal removes nothing, and says why",
              dirty_wt.exists() and done_wt.exists()
              and ": removed" not in killed_status_removal.stdout
              and "dirty-wt: kept — git cannot list its uncommitted changes"
              in killed_status_removal.stdout,
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
        check("--remove with origin/main missing stops at the branch-ref listing with exit 2, "
              "naming git's error, and reports no finished run",
              no_main_removal.returncode == 2
              and "clean-worktrees: stopped, because git for-each-ref" in no_main_removal.stderr
              and "origin/main" in no_main_removal.stderr
              and "clean-worktrees: finished" not in no_main_removal.stdout,
              (no_main_removal.returncode, no_main_removal.stdout, no_main_removal.stderr))
        check("--remove stopped after the worktrees were handled says it removed only what its "
              "removed and deleted lines name",
              'clean-worktrees removed only the worktrees and branches named on its lines containing '
              '": removed" or ": deleted", and checked nothing after the git command that failed.'
              in no_main_removal.stderr, no_main_removal.stderr)

        # --- Dead registrations are named, with the prune command ------------
        # A worktree registered under a temp directory leaves a dead entry
        # when the temp area clears (R25, ruled 2026-08-18). Simulate the
        # clearing: delete the directory behind git's back, so the
        # registration outlives it.
        dead_wt = add_worktree("dead-registration-wt", where=scratch, owner=False)
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
        surviving_wt = add_worktree("dotgit-deleted-wt", where=scratch, owner=False)
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
              outside_wt.exists()
              and (unreadable_wt / "unreadable-untracked.txt").exists()
              and (locked_wt / "locked-untracked.txt").exists()
              and (occupied_wt is None or occupied_wt.exists()),
              removal.stdout)
        check("--remove removes a worktree whose stopped owner left commits on a branch with no "
              "pull request, and keeps the branch, which holds commits origin/main lacks",
              not unlanded_wt.exists()
              and "unlanded-wt: removed, branch unlanded-wt-branch kept, since it holds commits "
                  "origin/main lacks" in removal.stdout
              and git(checkout, "rev-list", "--count", "origin/main..unlanded-wt-branch").strip() == "1",
              removal.stdout)
        detached_branches = git(checkout, "branch", "--list",
                                "worktree-cleaner-detached-commits-detached-unlanded-wt-*",
                                "--format=%(refname:short) %(objectname)").split()
        check("--remove puts a detached worktree's commits on no branch on a branch of their own, "
              "then removes the worktree",
              not detached_unlanded_wt.exists() and len(detached_branches) == 2
              and git(checkout, "log", "-1", "--format=%s", detached_branches[1]).strip()
                  == "unlanded detached work"
              and "detached-unlanded-wt: its commits on no branch are kept on the new branch "
                  in removal.stdout, removal.stdout)
        dirty_snapshots = git(checkout, "for-each-ref", "--format=%(refname)",
                              "refs/work-snapshots/").split()
        check("--remove copies a stopped owner's untracked file to a work-snapshot before the "
              "removal",
              any("uncommitted.txt" in git(checkout, "ls-tree", "-r", "--name-only", ref)
                  for ref in dirty_snapshots)
              and -1 < removal.stdout.find("dirty-wt: its uncommitted and untracked files are kept "
                                           "in the work-snapshot refs/work-snapshots/")
              < removal.stdout.find("dirty-wt: removed"), removal.stdout)
        check("a removal that fails is reported, and named its files beforehand",
              stuck_wt.exists() and "stuck-wt: removal FAILED" in removal.stdout
              and "stuck-wt: removing it will discard 1 uncommitted, untracked or ignored "
              "file(s): scratch-state/stuck.md" in removal.stdout
              and "stuck-wt: discarded" not in removal.stdout, removal.stdout)
        (stuck_wt / "scratch-state").chmod(0o755)
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
        # The local main, once no worktree has it checked out, is fully on origin/main and still
        # never named.
        git(checkout, "checkout", "-q", "--detach")
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
        check("the local main is not named, though no worktree has it checked out and it holds "
              "nothing origin/main lacks",
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
        check("--remove never deletes the local main",
              git(checkout, "branch", "--list", "main").strip() != "", orphan_removal.stdout)
        git(checkout, "checkout", "-q", "main")
        check("a run with no failure prints no line saying it finished with failures",
              "clean-worktrees: finished" not in orphan_removal.stdout, orphan_removal.stdout)

        # A local main behind origin/main is the ordinary state of a checkout
        # after somebody else's work lands, and in it git branch -d refuses a
        # ref that IS fully on origin/main: -d asks about HEAD and about the
        # ref's upstream, never about origin/main. The refusal is git's second
        # opinion, so the ref stays — but it is reported and counted, because a
        # sweep that silently keeps failing is a sweep nobody knows to fix.
        advance_wt = add_worktree("advance-wt", where=scratch, owner=False)
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


# --- The owner rules: while the owner runs, once it has stopped, and when neither can be told ---
# HOME is a scratch directory, so the handoff-supervisor locks the cleaner reads are this suite's.
with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch).resolve()
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
    fake_home = scratch / "home"
    handoffs = fake_home / ".claude" / "handoffs"
    handoffs.mkdir(parents=True)
    snapshots_module_spec = importlib.util.spec_from_file_location(
        "uncommitted_work_snapshots_for_owner_keys",
        CLEAN_SCRIPT.resolve().parent.parent / "nc-systems" / "handoff" / "uncommitted-work-snapshots.py")
    snapshots_module = importlib.util.module_from_spec(snapshots_module_spec)
    snapshots_module_spec.loader.exec_module(snapshots_module)

    # Stands in for a running agent-session's claude process; lives until its stdin closes.
    running_session = subprocess.Popen([sys.executable, "-c", "import sys; sys.stdin.read()"],
                                       stdin=subprocess.PIPE)
    # Stands in for the running handoff-supervisor of the agent-seat seat-running: ps shows a file
    # named handoff-supervisor.py run with --agent seat-running.
    fake_supervisor_script = scratch / "fake-supervisor" / "handoff-supervisor.py"
    fake_supervisor_script.parent.mkdir()
    fake_supervisor_script.write_text("import sys\nsys.stdin.read()\n", encoding="utf-8")
    running_supervisor = subprocess.Popen(
        [sys.executable, str(fake_supervisor_script), "--agent", "seat-running"],
        stdin=subprocess.PIPE)
    (handoffs / "seat-running-supervisor.lock").write_text(f"{running_supervisor.pid}\n",
                                                           encoding="utf-8")
    try:
        running_session_owner = {
            "owner_kind": "agent-session", "agent_seat": "seat-running",
            "owner_key": snapshots_module.owner_key_of_process(running_session.pid)}

        def owned_worktree(name, owner, detach=False):
            path = managed / name
            if detach:
                git(checkout, "worktree", "add", "--detach", str(path), "origin/main")
            else:
                git(checkout, "worktree", "add", "-b", f"{name}-branch", str(path), "origin/main")
            return give_owner(path, owner)

        def head_of(worktree):
            return git(worktree, "rev-parse", "HEAD").strip()

        def commit_in(worktree, message):
            (worktree / f"{message}.txt").write_text(message + "\n", encoding="utf-8")
            git(worktree, "add", "-A")
            git(worktree, "commit", "-m", message)

        fresh_wt = owned_worktree("fresh-wt", running_session_owner)
        merged_wt = owned_worktree("merged-wt", running_session_owner)
        closed_wt = owned_worktree("closed-wt", running_session_owner)
        commit_in(closed_wt, "closed-work")
        merged_untracked_wt = owned_worktree("merged-untracked-wt", running_session_owner)
        (merged_untracked_wt / "late.txt").write_text("written after the merge\n", encoding="utf-8")
        open_running_wt = owned_worktree("open-running-wt", running_session_owner)
        # A same-named tag makes git's --short form of the branch heads/<name>.
        tag_merged_wt = owned_worktree("tag-merged-wt", running_session_owner)
        git(checkout, "tag", "tag-merged-wt-branch", head_of(tag_merged_wt))
        reused_wt = owned_worktree("reused-wt", running_session_owner)
        seat_running_wt = owned_worktree("seat-running-wt",
                                         {"owner_kind": "agent-seat", "agent_seat": "seat-running"})
        seat_stopped_wt = owned_worktree("seat-stopped-wt",
                                         {"owner_kind": "agent-seat", "agent_seat": "seat-stopped"})
        stopped_open_wt = owned_worktree("stopped-open-wt", {
            "owner_kind": "agent-session", "agent_seat": "test-seat",
            "owner_key": stopped_agent_session_owner_key()})
        unknown_wt = owned_worktree("unknown-wt", {"owner_kind": "agent-session",
                                                   "agent_seat": "test-seat",
                                                   "owner_key": "not-an-owner-key"})
        unreadable_owner_wt = managed / "unreadable-owner-wt"
        git(checkout, "worktree", "add", "-b", "unreadable-owner-wt-branch",
            str(unreadable_owner_wt), "origin/main")
        owner_file_path(unreadable_owner_wt).write_text("{not json\n", encoding="utf-8")
        locked_owned_wt = give_stopped_owner(owned_worktree("locked-owned-wt", running_session_owner))
        # The lock names the running stand-in with its real start, so Claude Code's lock exception,
        # which unlocks a lock whose process has ended, leaves it locked.
        running_session_start = (snapshots_module.linux_start_ticks(running_session.pid)
                                 if sys.platform.startswith("linux") else "1")
        git(checkout, "worktree", "lock", "--reason",
            f"claude agent agent-a1 (pid {running_session.pid} start {running_session_start})",
            str(locked_owned_wt))

        pull_requests = [
            {"number": 1, "state": "MERGED", "headRefName": "merged-wt-branch",
             "headRefOid": head_of(merged_wt)},
            {"number": 2, "state": "CLOSED", "headRefName": "closed-wt-branch",
             "headRefOid": head_of(closed_wt)},
            {"number": 3, "state": "MERGED", "headRefName": "merged-untracked-wt-branch",
             "headRefOid": head_of(merged_untracked_wt)},
            {"number": 8, "state": "MERGED", "headRefName": "tag-merged-wt-branch",
             "headRefOid": head_of(tag_merged_wt)},
            {"number": 4, "state": "OPEN", "headRefName": "open-running-wt-branch",
             "headRefOid": head_of(open_running_wt)},
            # An earlier pull request on the same branch name, opened on another commit.
            {"number": 5, "state": "MERGED", "headRefName": "reused-wt-branch",
             "headRefOid": "0" * 40},
            {"number": 6, "state": "OPEN", "headRefName": "seat-stopped-wt-branch",
             "headRefOid": head_of(seat_stopped_wt)},
            {"number": 7, "state": "OPEN", "headRefName": "stopped-open-wt-branch",
             "headRefOid": head_of(stopped_open_wt)},
        ]

        def run_owner_rules(*flags, gh_exit=None):
            environment = dict(os.environ, HOME=str(fake_home),
                               FAKE_GH_PULL_REQUESTS=json.dumps(pull_requests))
            if gh_exit is not None:
                environment["FAKE_GH_EXIT_CODE"] = str(gh_exit)
            return subprocess.run([sys.executable, str(CLEAN_SCRIPT), "--repo", str(checkout), *flags],
                                  capture_output=True, text=True, check=False, env=environment)

        def line_of(output, name):
            return next((line for line in output.splitlines() if line.startswith(f"{name}:")), "")

        report = run_owner_rules().stdout
        check("a new worktree whose owner runs is kept though its branch has no pull request and "
              "no commit, as the topic worktrees removed 4 and 38 seconds after creation were not",
              line_of(report, "fresh-wt").startswith("fresh-wt: kept — its owner, an agent-session of "
                                                     "seat-running")
              and "has no merged or closed pull request whose head commit is its HEAD"
              in line_of(report, "fresh-wt"), report)
        check("a worktree whose owner runs is done once its branch's pull request has merged",
              line_of(report, "merged-wt").startswith("merged-wt: done — its owner")
              and "pull request #1 (merged) on its branch merged-wt-branch is finished"
              in line_of(report, "merged-wt"), report)
        check("a worktree whose owner runs is done once its branch's pull request is closed, "
              "commits not on origin/main included",
              line_of(report, "closed-wt").startswith("closed-wt: done"), report)
        check("a worktree whose owner runs is kept while it holds an untracked file, though its "
              "pull request has merged",
              line_of(report, "merged-untracked-wt").startswith("merged-untracked-wt: kept")
              and "1 uncommitted or untracked file(s): late.txt"
              in line_of(report, "merged-untracked-wt"), report)
        check("a worktree whose owner runs is kept while its pull request is open",
              line_of(report, "open-running-wt").startswith("open-running-wt: kept")
              and "pull request #4 (open)" in line_of(report, "open-running-wt"), report)
        check("an earlier merged pull request on a reused branch name, opened on another commit, "
              "does not make a new worktree done",
              line_of(report, "reused-wt").startswith("reused-wt: kept"), report)
        check("an agent-seat whose handoff-supervisor runs keeps its worktree",
              line_of(report, "seat-running-wt").startswith(
                  "seat-running-wt: kept — its owner, the agent-seat seat-running, runs"), report)
        check("an open pull request keeps the worktree of an agent-seat with no handoff-supervisor",
              line_of(report, "seat-stopped-wt").startswith(
                  "seat-stopped-wt: kept — its owner, the agent-seat seat-stopped, has stopped, and "
                  "pull request #6 (open)"), report)
        check("an open pull request keeps a worktree whose agent-session has stopped",
              line_of(report, "stopped-open-wt").startswith("stopped-open-wt: kept")
              and "has stopped" in line_of(report, "stopped-open-wt"), report)
        check("an owner whose state cannot be read keeps the worktree",
              line_of(report, "unknown-wt").startswith(
                  "unknown-wt: kept — whether its owner, an agent-session of test-seat"), report)
        check("an owner file that cannot be read keeps the worktree",
              line_of(report, "unreadable-owner-wt").startswith(
                  "unreadable-owner-wt: kept — its owner file could not be read:")
              and "is not JSON" in line_of(report, "unreadable-owner-wt"), report)
        check("a locked worktree is kept though its owner file says its owner stopped",
              line_of(report, "locked-owned-wt").startswith(
                  "locked-owned-wt: kept — locked with git worktree lock (claude agent agent-a1"),
              report)
        check("the count line gives the kept worktrees by reason, the worktrees with no owner file, "
              "the branches with no pull request and the work-snapshots present",
              "worktree counts: 10 kept (locked 1, no owner file 0, owner running 5, open pull "
              "request 2, in use 0, could not be checked 2); worktrees with no owner file 0; "
              "branches with no pull request 5; work-snapshots still present 0" in report, report)
        check("a line names the kept worktrees of an agent-seat whose handoff-supervisor is not "
              "running",
              f"worktrees kept whose agent-seat's handoff-supervisor is not running: "
              f"{seat_stopped_wt} (seat-stopped)" in report, report)

        failing_gh = run_owner_rules("--remove", gh_exit=1)
        check("when gh cannot list the pull requests, every worktree whose verdict needs one is "
              "kept, and the count line says the branch count is unknown",
              merged_wt.exists() and closed_wt.exists()
              and "merged-wt: kept — the pull requests of its branch merged-wt-branch could not be "
                  "read: `gh pr list" in failing_gh.stdout
              and "gh: stand-in listing failure" in failing_gh.stdout
              and "branches with no pull request unknown (" in failing_gh.stdout,
              failing_gh.stdout + failing_gh.stderr)

        removal = run_owner_rules("--remove")
        check("--remove removes the worktrees whose owner runs and whose pull request has merged or "
              "closed, and keeps every other",
              not merged_wt.exists() and not closed_wt.exists()
              and all(path.exists() for path in (
                  fresh_wt, merged_untracked_wt, open_running_wt, reused_wt, seat_running_wt,
                  seat_stopped_wt, stopped_open_wt, unknown_wt, unreadable_owner_wt,
                  locked_owned_wt)),
              removal.stdout + removal.stderr)
        check("--remove deletes the merged worktree's branch and keeps the closed one's, which "
              "holds commits origin/main lacks",
              "merged-wt: removed, branch merged-wt-branch deleted" in removal.stdout
              and "closed-wt: removed, branch closed-wt-branch kept" in removal.stdout
              and git(checkout, "branch", "--list", "closed-wt-branch").strip() != "",
              removal.stdout)
        check("--remove removes a worktree whose owner runs and whose pull request has merged, "
              "though a tag shares its branch's name",
              not tag_merged_wt.exists()
              and "tag-merged-wt: removed, branch tag-merged-wt-branch deleted" in removal.stdout,
              removal.stdout + removal.stderr)

        # Failure injection: a work-snapshot that cannot be written, and a branch for commits on no
        # branch that cannot be made, each keep the worktree and fail the run.
        stopped_owner = {"owner_kind": "agent-session", "agent_seat": "test-seat",
                         "owner_key": stopped_agent_session_owner_key()}
        snapshot_blocked_wt = owned_worktree("snapshot-blocked-wt", stopped_owner)
        (snapshot_blocked_wt / "unsaved.txt").write_text("only here\n", encoding="utf-8")
        common_git_directory = Path(git(checkout, "rev-parse", "--path-format=absolute",
                                        "--git-common-dir").strip())
        # A file where git must make the directory refs/work-snapshots/, so no work-snapshot ref
        # can be written.
        (common_git_directory / "refs" / "work-snapshots").write_text("", encoding="utf-8")
        branch_blocked_wt = owned_worktree("branch-blocked-wt", stopped_owner, detach=True)
        commit_in(branch_blocked_wt, "detached-work")
        blocked_branch = f"worktree-cleaner-detached-commits-branch-blocked-wt-{head_of(branch_blocked_wt)[:12]}"
        git(checkout, "branch", blocked_branch, "origin/main")
        # An earlier --remove made the branch for this worktree's commits on no branch, then failed
        # at a later step: the branch already names the very commit.
        premade_wt = owned_worktree("premade-branch-wt", stopped_owner, detach=True)
        commit_in(premade_wt, "detached-work-an-earlier-run-kept")
        premade_commit = head_of(premade_wt)
        premade_branch = f"worktree-cleaner-detached-commits-premade-branch-wt-{premade_commit[:12]}"
        git(checkout, "branch", premade_branch, premade_commit)
        blocked = run_owner_rules("--remove")
        check("a work-snapshot that cannot be written keeps a stopped owner's worktree and its file, "
              "fails the run, and says why",
              (snapshot_blocked_wt / "unsaved.txt").is_file()
              and "snapshot-blocked-wt: work-snapshot FAILED, worktree kept — its uncommitted and "
                  "untracked files could not be copied: " in blocked.stdout
              and "snapshot-blocked-wt: removed" not in blocked.stdout
              and blocked.returncode == 1, blocked.stdout + blocked.stderr)
        check("a branch for commits on no branch that cannot be made keeps the worktree and its "
              "commit, fails the run, and says why",
              branch_blocked_wt.exists()
              and f"branch-blocked-wt: branch for its commits on no branch FAILED, worktree kept — "
                  f"git branch {blocked_branch} " in blocked.stdout
              and "branch-blocked-wt: removed" not in blocked.stdout,
              blocked.stdout + blocked.stderr)
        check("a branch an earlier run made on the worktree's own detached commit counts as made, "
              "so the worktree is removed and the branch still holds the commit",
              not premade_wt.exists()
              and f"premade-branch-wt: its commits on no branch are already kept on the branch "
                  f"{premade_branch}, which an earlier scripts/clean-worktrees.py --remove run made"
                  in blocked.stdout
              and "premade-branch-wt: removed" in blocked.stdout
              and "premade-branch-wt: branch for its commits on no branch FAILED" not in blocked.stdout
              and git(checkout, "rev-parse", premade_branch).strip() == premade_commit,
              blocked.stdout + blocked.stderr)
        check("each of those failures is followed by a line, holding no FAILED, saying the next "
              "--remove tries again",
              all(f"{name}: do nothing now: the worktree and everything in it are kept, and the "
                  f"next scripts/clean-worktrees.py --remove" in blocked.stdout
                  for name in ("snapshot-blocked-wt", "branch-blocked-wt"))
              and not any("do nothing now" in line and "FAILED" in line
                          for line in blocked.stdout.splitlines()),
              blocked.stdout)

        # In this process: gh that cannot be run, gh that prints no list, and a file written
        # between the verdict and the removal.
        module = load_clean_worktrees_module()
        saved_path = os.environ["PATH"]
        not_json_gh = scratch / "not-json-gh"
        not_json_gh.mkdir()
        (not_json_gh / "gh").write_text("#!/bin/sh\necho 'not a list'\n", encoding="utf-8")
        (not_json_gh / "gh").chmod(0o755)
        no_gh = scratch / "no-gh"
        no_gh.mkdir()
        (no_gh / "git").symlink_to(shutil.which("git"))
        try:
            os.environ["PATH"] = f"{not_json_gh}{os.pathsep}{saved_path}"
            not_json = raised_by(lambda: module.list_all_pull_requests_grouped_by_head_branch(checkout))
            os.environ["PATH"] = str(no_gh)
            not_run = raised_by(lambda: module.list_all_pull_requests_grouped_by_head_branch(checkout))
        finally:
            os.environ["PATH"] = saved_path
        check("gh printing something other than a list of pull requests is a listing failure",
              isinstance(not_json, module.PullRequestListingFailed)
              and "printed something other than a list of pull requests" in str(not_json),
              repr(not_json))
        check("gh that cannot be run is a listing failure",
              isinstance(not_run, module.PullRequestListingFailed)
              and "could not be run" in str(not_run), repr(not_run))
        committed_late_wt = owned_worktree("committed-late-wt", running_session_owner)
        judged_head = head_of(committed_late_wt)
        commit_in(committed_late_wt, "committed-after-the-verdict")
        committed_late_output = io.StringIO()
        real_stdout = sys.stdout
        sys.stdout = committed_late_output
        try:
            committed_late_result = module.remove_worktree(
                committed_late_wt, "committed-late-wt-branch", checkout,
                module.Verdict(True, "", "", running_session_owner, module.owner_file.RUNNING,
                               judged_head=judged_head, judged_branch="committed-late-wt-branch"))
        finally:
            sys.stdout = real_stdout
        check("--remove keeps a worktree whose running owner committed after the verdict matched "
              "its finished pull request",
              committed_late_result is True and committed_late_wt.exists()
              and "committed-late-wt: kept — its owner, an agent-session of seat-running" in
                  committed_late_output.getvalue()
              and f"the worktree's HEAD or branch changed during this run: it was {judged_head} on "
                  f"committed-late-wt-branch, the head commit of a merged or closed pull request, "
                  f"and is now {head_of(committed_late_wt)} on committed-late-wt-branch"
                  in committed_late_output.getvalue(), committed_late_output.getvalue())
        tag_shares_name_wt = owned_worktree("tag-shares-name-wt", running_session_owner)
        git(checkout, "tag", "tag-shares-name-wt-branch", head_of(tag_shares_name_wt))
        check("git's --short form of a branch that a same-named tag shadows is heads/<name>, "
              "the case the branch read must not use",
              git(tag_shares_name_wt, "symbolic-ref", "--short", "HEAD").strip()
              == "heads/tag-shares-name-wt-branch")
        check("the branch read of a worktree whose branch shares its name with a tag is the "
              "branch's own name",
              module.checked_out_branch_name(tag_shares_name_wt) == "tag-shares-name-wt-branch",
              repr(module.checked_out_branch_name(tag_shares_name_wt)))
        detached_read_wt = owned_worktree("detached-read-wt", running_session_owner, detach=True)
        check("the branch read of a detached worktree is no branch",
              module.checked_out_branch_name(detached_read_wt) is None,
              repr(module.checked_out_branch_name(detached_read_wt)))
        check("a ref outside refs/heads/, or no ref, names no branch",
              module.local_branch_name_of_full_ref("refs/tags/tag-shares-name-wt-branch") is None
              and module.local_branch_name_of_full_ref(None) is None)
        late_wt = owned_worktree("late-wt", running_session_owner)
        (late_wt / "written-after-the-verdict.txt").write_text("new\n", encoding="utf-8")
        late_output = io.StringIO()
        real_stdout = sys.stdout
        sys.stdout = late_output
        try:
            late_result = module.remove_worktree(
                late_wt, "late-wt-branch", checkout,
                module.Verdict(True, "", "", running_session_owner, module.owner_file.RUNNING))
        finally:
            sys.stdout = real_stdout
        check("--remove keeps a worktree whose running owner wrote a file after the verdict",
              late_result is True and late_wt.exists()
              and "late-wt: kept — its owner, an agent-session of seat-running" in late_output.getvalue()
              and "runs, and it now holds 1 uncommitted or untracked file(s): "
                  "written-after-the-verdict.txt" in late_output.getvalue(), late_output.getvalue())
    finally:
        for helper in (running_session, running_supervisor):
            helper.stdin.close()
            helper.wait(timeout=30)


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
        give_stopped_owner(path)
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
          (newline_path, "newline-branch") in [(path, branch) for path, branch, _ in listed],
          str(listed))
    orphaned = module.branch_refs_with_no_worktree_fully_on_main(checkout)
    check("a lock reason that reads like a branch line does not attach that branch",
          "unattached-landed" in orphaned, str(orphaned))
    dead = module.dead_worktree_registrations(checkout)
    check("a prunable registration is reported with git's reason",
          [path for path, reason in dead] == [str(gone_path)] and dead[0][1] != "no reason given",
          str(dead))

# A git that cannot list the worktrees must stop the run with exit 2 and git's error,
# not read as a repository with nothing to clean.
LISTING_FAILURE_TEXT = "fatal: stand-in worktree listing failure"
with tempfile.TemporaryDirectory() as scratch:
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
    failing_listing_stubs = scratch / "failing-worktree-list-git"
    failing_listing_stubs.mkdir()
    (failing_listing_stubs / "git").write_text(
        "#!/bin/sh\n"
        f'case " $* " in *" worktree list "*) echo "{LISTING_FAILURE_TEXT}" >&2; exit 128 ;; esac\n'
        f'exec {shutil.which("git")} "$@"\n', encoding="utf-8")
    (failing_listing_stubs / "git").chmod(0o755)
    environment = dict(os.environ)
    environment["PATH"] = f"{failing_listing_stubs}{os.pathsep}{environment.get('PATH', '')}"
    for flags in ([], ["--only-done"], ["--remove"]):
        failed_listing = subprocess.run(
            [sys.executable, str(CLEAN_SCRIPT), "--repo", str(checkout), *flags],
            capture_output=True, text=True, check=False, env=environment)
        stderr_lines = failed_listing.stderr.strip().splitlines()
        rerun = shlex.join([sys.executable, str(CLEAN_SCRIPT.resolve()), "--repo", str(checkout), *flags])
        check(f"a failed worktree listing{' under ' + flags[0] if flags else ''} exits 2 "
              "with git's error on its first stderr line, and prints nothing as found",
              failed_listing.returncode == 2
              and failed_listing.stdout == ""
              and stderr_lines[:1] != []
              and stderr_lines[0].startswith("clean-worktrees: stopped, because git worktree list")
              and LISTING_FAILURE_TEXT in stderr_lines[0]
              and stderr_lines[0].endswith(
                  'clean-worktrees removed only the worktrees and branches named on its lines '
                  'containing ": removed" or ": deleted", and checked nothing after the git command '
                  'that failed.'
                  if flags == ["--remove"] else
                  "clean-worktrees removed nothing, since it ran without --remove, and checked "
                  "nothing after the git command that failed."),
              (failed_listing.returncode, failed_listing.stdout, failed_listing.stderr))
        check(f"a failed worktree listing{' under ' + flags[0] if flags else ''} gives the "
              "shared next steps, naming the command that was run",
              stderr_lines[1:] == load_clean_worktrees_module().next_step_lines.git_failure_next_step_lines(
                  rerun, text_the_failure_line_contains="clean-worktrees: stopped, because",
                  include_the_misspelt_branch_commit_or_path_line=False).splitlines(),
              failed_listing.stderr)

    module = load_clean_worktrees_module()
    saved_path = os.environ.get("PATH", "")
    os.environ["PATH"] = environment["PATH"]
    try:
        for name, call in (
                ("list_worktrees", lambda: module.list_worktrees(checkout, checkout)),
                ("branch_refs_with_no_worktree_fully_on_main",
                 lambda: module.branch_refs_with_no_worktree_fully_on_main(checkout)),
                ("dead_worktree_registrations",
                 lambda: module.dead_worktree_registrations(checkout))):
            try:
                answer = call()
            except module.git_output.GitCommandFailed as error:
                answer = error
            check(f"{name} raises git's error when git cannot list the worktrees",
                  isinstance(answer, module.git_output.GitCommandFailed)
                  and LISTING_FAILURE_TEXT in str(answer), repr(answer))
    finally:
        os.environ["PATH"] = saved_path

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
        "cold-read-records/\nsanity-check-records/\ndocs/walk/\n", encoding="utf-8")
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
        give_stopped_owner(path)
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
          and "whose line does not start REFUSED:" not in refused.stdout
          and "for each walk whose line starts REFUSED:" not in refused.stdout,
          refused.stdout)
    remove_worktree_for_next_case(refused_wt)

    # A shipper that dies before printing its line: a record file it cannot read raises, uncaught.
    silent_wt = worktree_holding_records("silent-wt")
    for record_file in silent_wt.glob("*-records/*/*.md"):
        record_file.chmod(0)
    silent = run_clean_shipping_to(str(scratch / "silent-store" / "cold-read-records"),
                                   None, "--remove")
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

# --- Walks in docs/walk/ are shipped before the removal; a REFUSED or FAILED walk keeps the worktree ---
    walk_name = "demo-walk-2026-10-31"

    def worktree_holding_a_walk(name):
        path = managed / name
        git(checkout, "worktree", "add", "-b", f"{name}-branch", str(path), "origin/main")
        give_stopped_owner(path)
        walk_directory = path / "docs" / "walk"
        walk_directory.mkdir(parents=True)
        for suffix, text in (("", "# walk\n\n## Item 1 of 1\n"), ("-minutes", "# minutes\n\nItem 1 ruled.\n"),
                             ("-draft", "# draft\n"), ("-suggestions", "# an earlier walk's fast read report\n")):
            (walk_directory / f"{walk_name}{suffix}.md").write_text(text, encoding="utf-8")
        (walk_directory / "never-presented-2026-10-31-draft.md").write_text("# draft\n", encoding="utf-8")
        (walk_directory / f"{walk_name}-round-1-draft.md").write_text("# round 1\n", encoding="utf-8")
        (walk_directory / "notes.txt").write_text("not a walk file\n", encoding="utf-8")
        return path

    walk_store = scratch / "walk-store"
    reported_walk_wt = worktree_holding_a_walk("reported-walk-wt")
    reported = run_clean_shipping_to(str(walk_store / "cold-read-records")).stdout
    check("the report names a done worktree's walk and says --remove ships it first",
          f"--remove first ships its 1 record(s) to the log-store and keeps the worktree if a record "
          f"does not ship; the records it ships: "
          f"docs/walk/{walk_name}.md" in reported, reported)
    check("the report ships no walk", not (walk_store / "walk").exists())
    remove_worktree_for_next_case(reported_walk_wt)

    walk_wt = worktree_holding_a_walk("walk-wt")
    shipped = run_clean_shipping_to(str(walk_store / "cold-read-records"), None, "--remove")
    check("--remove ships a done worktree's walk to the log-store's walk/ before removing it",
          (walk_store / "walk" / f"{walk_name}-minutes.md").is_file()
          and (walk_store / "walk" / f"{walk_name}.md").is_file()
          and f"walk-wt: shipped: {walk_name}" in shipped.stdout
          and not walk_wt.exists() and shipped.returncode == 0, shipped.stdout + shipped.stderr)
    check("--remove names the docs/walk/ files no walk ships, a walk never presented and a file of "
          "no walk role, and removes the worktree anyway",
          "walk-wt: 3 file(s) in docs/walk/ no walk ships" in shipped.stdout
          and "docs/walk/notes.txt" in shipped.stdout
          and "docs/walk/never-presented-2026-10-31-draft.md" in shipped.stdout
          and f"docs/walk/{walk_name}-round-1-draft.md" in shipped.stdout
          and not (walk_store / "walk" / "never-presented-2026-10-31-draft.md").exists(),
          shipped.stdout)
    check("--remove counts an earlier walk's <name>-suggestions.md as shipped, not as a file no walk ships",
          (walk_store / "walk" / f"{walk_name}-suggestions.md").is_file()
          and not any(f"docs/walk/{walk_name}-suggestions.md" in line
                      for line in shipped.stdout.splitlines() if "no walk ships" in line),
          shipped.stdout)
    remove_worktree_for_next_case(walk_wt)

    unreachable_walk_wt = worktree_holding_a_walk("unreachable-walk-wt")
    unreachable = run_clean_shipping_to(
        "nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records",
        unreachable_stubs, "--remove")
    check("--remove keeps a worktree whose walk fails to ship, exits 1, and says why",
          unreachable_walk_wt.exists()
          and (unreachable_walk_wt / "docs" / "walk" / f"{walk_name}-minutes.md").is_file()
          and f"unreachable-walk-wt: record shipment FAILED, worktree kept — removing it would delete "
          f"a record the log-store does not hold: docs/walk/{walk_name}.md (FAILED:"
          in unreachable.stdout
          and unreachable.returncode == 1
          and "unreachable-walk-wt: removed" not in unreachable.stdout,
          unreachable.stdout + unreachable.stderr)
    check("--remove tells a worktree whose walk failed to ship that the next --remove retries, "
          "on a line with no FAILED in it",
          "unreachable-walk-wt: for each record whose line does not start REFUSED:, do nothing now: "
          "the next scripts/clean-worktrees.py --remove, daily or at a handoff, ships the record again; "
          "if the record fails the same way there, fix the cause its line names" in unreachable.stdout
          and "whose line starts REFUSED:" not in unreachable.stdout
          and "file(s) in docs/walk/ no walk ships" not in unreachable.stdout,
          unreachable.stdout)
    remove_worktree_for_next_case(unreachable_walk_wt)

    refused_walk_store = scratch / "refused-walk-store"
    (refused_walk_store / "walk").mkdir(parents=True)
    (refused_walk_store / "walk" / f"{walk_name}-draft.md").write_text(
        "# another checkout's draft\n", encoding="utf-8")
    refused_walk_wt = worktree_holding_a_walk("refused-walk-wt")
    refused = run_clean_shipping_to(str(refused_walk_store / "cold-read-records"), None, "--remove")
    check("--remove keeps a worktree whose walk was REFUSED a draft, exits 1, and says the walk's "
          "owner decides which copy is right",
          refused_walk_wt.exists()
          and (refused_walk_wt / "docs" / "walk" / f"{walk_name}-draft.md").is_file()
          and "refused-walk-wt: record shipment FAILED, worktree kept — " in refused.stdout
          and f"(REFUSED: {walk_name}" in refused.stdout
          and "refused-walk-wt: for each walk whose line starts REFUSED:, the log-store holds "
          "another copy of each file that line names" in refused.stdout
          and "refused-walk-wt: removed" not in refused.stdout and refused.returncode == 1,
          refused.stdout + refused.stderr)
    remove_worktree_for_next_case(refused_walk_wt)

    # A walk shipped once, then revised in place: the store's walk text is not a prefix of the local one.
    revised_walk_store = scratch / "revised-walk-store"
    (revised_walk_store / "walk").mkdir(parents=True)
    (revised_walk_store / "walk" / f"{walk_name}.md").write_text(
        "# walk\n\n## Item 1 of 1, before its revision\n", encoding="utf-8")
    revised_walk_wt = worktree_holding_a_walk("revised-walk-wt")
    revised = run_clean_shipping_to(str(revised_walk_store / "cold-read-records"), None, "--remove")
    check("--remove ships a .claude/worktrees/ worktree's revised walk text as <name>-revised-1.md, "
          "keeping the store's first copy, before it removes the worktree",
          text_or_none(revised_walk_store / "walk" / f"{walk_name}-revised-1.md")
          == "# walk\n\n## Item 1 of 1\n"
          and text_or_none(revised_walk_store / "walk" / f"{walk_name}.md")
          == "# walk\n\n## Item 1 of 1, before its revision\n"
          and not revised_walk_wt.exists()
          and "REFUSED" not in revised.stdout,
          revised.stdout + revised.stderr)
    remove_worktree_for_next_case(revised_walk_wt)

    unreadable_walk_wt = worktree_holding_a_walk("unreadable-walk-wt")
    (unreadable_walk_wt / "docs" / "walk" / f"{walk_name}.md").chmod(0)
    unreadable = run_clean_shipping_to(str(scratch / "unreadable-walk-store" / "cold-read-records"),
                                       None, "--remove")
    check("--remove keeps a worktree whose walk text the walk shipper cannot read, and carries "
          "the shipper's FAILED line",
          unreadable_walk_wt.exists()
          and "unreadable-walk-wt: record shipment FAILED, worktree kept — " in unreadable.stdout
          and "Permission denied" in unreadable.stdout and unreadable.returncode == 1,
          unreadable.stdout + unreadable.stderr)
    # A case that wrongly removed the worktree has already failed; the next cases still run.
    if (unreadable_walk_wt / "docs" / "walk" / f"{walk_name}.md").exists():
        (unreadable_walk_wt / "docs" / "walk" / f"{walk_name}.md").chmod(0o644)
    remove_worktree_for_next_case(unreadable_walk_wt)

    # foo-minutes.md is both walk foo's minutes and walk foo-minutes's walk text; a shipper given that
    # path resolves it to the longer name, so each walk must be handed over by its own walk text.
    overlapping_name = "overlap-walk-2026-10-31"
    overlapping_walk_wt = managed / "overlapping-walk-wt"
    git(checkout, "worktree", "add", "-b", "overlapping-walk-wt-branch", str(overlapping_walk_wt), "origin/main")
    give_stopped_owner(overlapping_walk_wt)
    overlapping_directory = overlapping_walk_wt / "docs" / "walk"
    overlapping_directory.mkdir(parents=True)
    for file_name, text in ((f"{overlapping_name}.md", "# walk foo\n"),
                            (f"{overlapping_name}-minutes.md", "# minutes of foo, walk text of foo-minutes\n"),
                            (f"{overlapping_name}-minutes-minutes.md", "# minutes of foo-minutes\n")):
        (overlapping_directory / file_name).write_text(text, encoding="utf-8")
    overlapping_store = scratch / "overlapping-walk-store"
    overlapping = run_clean_shipping_to(str(overlapping_store / "cold-read-records"), None, "--remove")
    check("--remove ships both walks when one walk's name is another's name with -minutes added, "
          "the shorter walk's walk text included",
          all((overlapping_store / "walk" / file_name).is_file()
              for file_name in (f"{overlapping_name}.md", f"{overlapping_name}-minutes.md",
                                f"{overlapping_name}-minutes-minutes.md"))
          and f"overlapping-walk-wt: shipped: {overlapping_name} " in overlapping.stdout
          and f"overlapping-walk-wt: shipped: {overlapping_name}-minutes " in overlapping.stdout
          and overlapping.returncode == 0,
          overlapping.stdout + overlapping.stderr)
    remove_worktree_for_next_case(overlapping_walk_wt)

    # Walk foo-draft has minutes and no walk text, beside a whole walk foo: a shipper given foo-draft.md
    # would resolve it to foo, ship foo, and the removal would delete foo-draft's minutes.
    unpresented_walk_wt = managed / "unpresented-walk-wt"
    git(checkout, "worktree", "add", "-b", "unpresented-walk-wt-branch", str(unpresented_walk_wt), "origin/main")
    give_stopped_owner(unpresented_walk_wt)
    unpresented_directory = unpresented_walk_wt / "docs" / "walk"
    unpresented_directory.mkdir(parents=True)
    for file_name, text in ((f"{walk_name}.md", "# walk\n"), (f"{walk_name}-minutes.md", "# minutes\n"),
                            (f"{walk_name}-draft-minutes.md", "# minutes of a walk with no walk text\n")):
        (unpresented_directory / file_name).write_text(text, encoding="utf-8")
    unpresented = run_clean_shipping_to(str(scratch / "unpresented-walk-store" / "cold-read-records"),
                                        None, "--remove")
    check("--remove keeps a worktree holding the minutes of a walk with no walk text, whose name is "
          "another walk's name with a role suffix added",
          unpresented_walk_wt.exists()
          and f"unpresented-walk-wt: record shipment FAILED, worktree kept — removing it would delete "
          f"a record the log-store does not hold: docs/walk/{walk_name}-draft-minutes.md (FAILED:"
          in unpresented.stdout and unpresented.returncode == 1,
          unpresented.stdout + unpresented.stderr)
    remove_worktree_for_next_case(unpresented_walk_wt)

# --- A worktree with a git operation stopped partway is kept ---
# Mid-rebase, HEAD is detached at a commit already on origin/main, so the landed check passes, and a
# subagent working there from its agent-home is invisible to the vacancy check.
with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch).resolve()
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

    rebasing_wt = managed / "rebasing-wt"
    git(checkout, "worktree", "add", "-b", "rebasing-wt-branch", str(rebasing_wt), "origin/main")
    give_stopped_owner(rebasing_wt)
    (rebasing_wt / "README.md").write_text("# the worktree's change\n", encoding="utf-8")
    git(rebasing_wt, "commit", "-am", "the worktree's change")
    (checkout / "README.md").write_text("# main's change\n", encoding="utf-8")
    git(checkout, "commit", "-am", "main's change")
    git(checkout, "push", "origin", "main")
    stopped = subprocess.run(["git", "-C", str(rebasing_wt), "rebase", "origin/main"],
                             capture_output=True, text=True, check=False)
    (rebasing_wt / "work-in-progress.md").write_text("half done\n", encoding="utf-8")
    check("the rebase stops on its conflict, with HEAD detached at origin/main",
          stopped.returncode != 0
          and git(rebasing_wt, "rev-parse", "HEAD") == git(checkout, "rev-parse", "origin/main"),
          stopped.stdout + stopped.stderr)

    unlocatable_wt = managed / "unlocatable-wt"
    git(checkout, "worktree", "add", "-b", "unlocatable-wt-branch", str(unlocatable_wt),
        "origin/main")
    give_stopped_owner(unlocatable_wt)
    (unlocatable_wt / ".git").write_text(f"gitdir: {scratch / 'no-such-git-directory'}\n",
                                         encoding="utf-8")

    removal = run_clean(checkout, "--remove")
    check("--remove keeps a worktree in which a rebase stopped partway, naming the rebase",
          rebasing_wt.exists() and (rebasing_wt / "work-in-progress.md").is_file()
          and "rebasing-wt: kept — a rebase is in progress in it (its git directory holds "
              "rebase-merge)" in removal.stdout
          and "rebasing-wt: removed" not in removal.stdout,
          removal.stdout + removal.stderr)
    check("--remove keeps a worktree whose git directory git cannot locate",
          unlocatable_wt.exists()
          and "unlocatable-wt: kept — its owner file could not be read: git rev-parse in "
              in removal.stdout,
          removal.stdout + removal.stderr)

# --- The log of removals ---
with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch).resolve()
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
    main_commit = git(checkout, "rev-parse", "origin/main").strip()

    def run_clean_logging_to(log_file):
        environment = dict(os.environ)
        environment[REMOVALS_LOG_OVERRIDE_VARIABLE] = str(log_file)
        return subprocess.run(
            [sys.executable, str(CLEAN_SCRIPT), "--repo", str(checkout), "--remove"],
            capture_output=True, text=True, check=False, env=environment)

    def fields_of(line):
        time_field, machine, event, *pairs = line.split("\t")
        return time_field, machine, event, dict(pair.split("=", 1) for pair in pairs)

    logged_wt = managed / "logged-wt"
    git(checkout, "worktree", "add", "-b", "logged-wt-branch", str(logged_wt), "origin/main")
    give_stopped_owner(logged_wt)
    (logged_wt / "notes.txt").write_text("discarded\n", encoding="utf-8")
    git(checkout, "branch", "orphaned-branch", "origin/main")
    log_file = scratch / "store" / "kind" / "ned-box.txt"
    logged = run_clean_logging_to(log_file)
    lines = log_file.read_text(encoding="utf-8").splitlines() if log_file.is_file() else []
    by_event = {}
    for line in lines:
        time_field, machine, event, fields = fields_of(line)
        by_event.setdefault(event, []).append((time_field, machine, fields))
    removed = by_event.get("removed-worktree", [])
    deleted = {fields["branch"]: fields for _, _, fields in by_event.get("deleted-branch", [])}
    check("--remove logs a removed worktree with its UTC time, machine, path, branch, head commit, "
          "discarded-file count, repository and the process that ran it",
          logged.returncode == 0 and not logged_wt.exists() and len(removed) == 1
          and time.strptime(removed[0][0], "%Y-%m-%dT%H:%M:%SZ")
          and removed[0][1] in ("ned-box", "mac")
          and removed[0][2]["path"] == str(logged_wt)
          and removed[0][2]["branch"] == "logged-wt-branch"
          and removed[0][2]["head"] == main_commit
          and removed[0][2]["discarded-files"] == "1"
          and removed[0][2]["repo"] == str(checkout)
          and removed[0][2]["run-by"].startswith(f"{os.getpid()} "),
          logged.stdout + logged.stderr + "\n".join(lines))
    check("--remove logs the branch it deleted with its worktree and the orphaned branch it "
          "deleted, each with its commit",
          set(deleted) == {"logged-wt-branch", "orphaned-branch"}
          and all(fields["commit"] == main_commit for fields in deleted.values()),
          "\n".join(lines))

    unwritable_wt = managed / "unwritable-log-wt"
    git(checkout, "worktree", "add", "-b", "unwritable-log-wt-branch", str(unwritable_wt),
        "origin/main")
    give_stopped_owner(unwritable_wt)
    git(checkout, "branch", "second-orphaned-branch", "origin/main")
    not_a_directory = scratch / "a-file"
    not_a_directory.write_text("", encoding="utf-8")
    unwritten = run_clean_logging_to(not_a_directory / "ned-box.txt")
    output_lines = unwritten.stdout.splitlines()
    check("a log line that cannot be written is printed with FAILED and its cause, and the run "
          "still removes the worktree and deletes both branches, then exits 1",
          unwritten.returncode == 1 and not unwritable_wt.exists()
          and git(checkout, "branch", "--list", "unwritable-log-wt-branch",
                  "second-orphaned-branch") == ""
          and sum(1 for line in output_lines
                  if ": log of removals line(s) FAILED to be written to " in line) == 2
          and any(line.startswith("unwritable-log-wt: log of removals line(s) FAILED")
                  and "mkdir" in line for line in output_lines)
          and any(line.startswith("branch second-orphaned-branch: log of removals line(s) FAILED")
                  for line in output_lines)
          and "clean-worktrees: finished; each failure is named above" in output_lines,
          unwritten.stdout + unwritten.stderr)
    by_hand = [line for line in output_lines
               if line.startswith("unwritable-log-wt: to record it, run this once: ")]
    check("the failure names a command that writes the unwritten lines once the cause is fixed",
          len(by_hand) == 1, unwritten.stdout)
    if by_hand:
        # The cause removed, the printed command must write the line where the run could not.
        not_a_directory.unlink()
        command = by_hand[0].split("run this once: ", 1)[1]
        subprocess.run(["/bin/sh", "-c", command], capture_output=True, check=False)
        repaired = not_a_directory / "ned-box.txt"
        written = repaired.read_text(encoding="utf-8").splitlines() if repaired.is_file() else []
        check("that command appends the very lines the run could not write",
              [fields_of(line)[2] for line in written] == ["removed-worktree", "deleted-branch"]
              and fields_of(written[0])[3]["path"] == str(unwritable_wt)
              and fields_of(written[1])[3]["branch"] == "unwritable-log-wt-branch",
              command + "\n" + "\n".join(written))

    module = load_clean_worktrees_module()
    check("a commit git cannot read is logged as unknown",
          module.commit_of(scratch / "not-a-repository", "HEAD") == "unknown")
    real_run = module.subprocess.run

    def ps_that_cannot_start(arguments, *rest, **options):
        if arguments[0] == "ps":
            raise FileNotFoundError("ps")
        return real_run(arguments, *rest, **options)

    module.subprocess.run = ps_that_cannot_start
    try:
        unknown_caller = module.parent_process_id_and_command_line()
    finally:
        module.subprocess.run = real_run
    check("a parent process whose command line ps cannot give is logged by its pid and unknown",
          unknown_caller == f"{os.getppid()} unknown", unknown_caller)

    no_origin = scratch / "no-origin-main"
    no_origin.mkdir()
    git(no_origin, "init", "-b", "main")
    git(no_origin, "-c", "user.email=test@test.invalid", "-c", "user.name=test",
        "commit", "--allow-empty", "-m", "only commit")
    check("a branch git cannot compare with origin/main, because there is none, never counts as "
          "fully on origin/main, so the cleaner keeps it",
          module.fully_on_origin_main(no_origin, "main") is False)

    # The cleaner fed a real Mac lock reason, as Claude Code writes it, on macOS.
    mac_locked = scratch / "mac-locked"
    git(no_origin, "worktree", "add", "-b", "mac-locked", str(mac_locked))
    owner_module = module.owner_file
    real_running_state = owner_module.claude_code_subagent_worktree_lock_dispatching_process_running_state
    real_owner_key = owner_module.claude_code_subagent_worktree_lock_ended_agent_session_owner_key
    real_seats = owner_module.agent_seats_whose_claude_code_transcripts_name_subagent
    owner_module.claude_code_subagent_worktree_lock_dispatching_process_running_state = (
        lambda lock: real_running_state(lock, platform="darwin", macos_start_seconds=lambda pid: None))
    owner_module.claude_code_subagent_worktree_lock_ended_agent_session_owner_key = (
        lambda lock: real_owner_key(lock, platform="darwin"))
    owner_module.agent_seats_whose_claude_code_transcripts_name_subagent = lambda agent_id: ["seat-x"]
    try:
        mac_verdict, mac_ended = module.claude_code_subagent_lock_verdict_or_ended_lock(
            mac_locked, types.SimpleNamespace(locked_reason=(
                "claude agent agent-a9e3e2fe0e79f0a2c (pid 29741 start Tue Nov  3 21:24:32 2026)")))
    finally:
        owner_module.claude_code_subagent_worktree_lock_dispatching_process_running_state = real_running_state
        owner_module.claude_code_subagent_worktree_lock_ended_agent_session_owner_key = real_owner_key
        owner_module.agent_seats_whose_claude_code_transcripts_name_subagent = real_seats
    mac_start_seconds = str(int(time.mktime(time.strptime("Tue Nov 3 21:24:32 2026",
                                                          "%a %b %d %H:%M:%S %Y"))))
    check("on macOS the cleaner unlocks a worktree whose real-form Claude Code lock names an ended "
          "claude process, writing an owner file with the macOS owner key",
          mac_verdict is None and mac_ended is not None
          and mac_ended.owner_to_write == {"owner_kind": owner_module.OWNER_AGENT_SESSION,
                                           "agent_seat": "seat-x",
                                           "owner_key": f"29741-{mac_start_seconds}"},
          (mac_verdict, mac_ended))

# --- One named worktree or branch ---

REMOVE_WORKTREE_FLAG = "--remove-worktree-and-force-delete-its-branch"
FORCE_DELETE_BRANCH_FLAG = "--force-delete-branch"
with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch).resolve()
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
    one_named_log = scratch / "one-named-log.txt"
    stub_git_directory = scratch / "stub-git"
    stub_git_directory.mkdir()

    def run_one_named(*flags, git_refuses=None, lsof_body=None, log_file=one_named_log,
                      pull_requests=None, gh_exit_code=None):
        """Run the cleaner on one named worktree or branch; git_refuses is a pattern of git
        arguments a stub git exits 1 on, lsof_body a stub lsof's script."""
        environment = dict(os.environ)
        environment[REMOVALS_LOG_OVERRIDE_VARIABLE] = str(log_file)
        if pull_requests is not None:
            environment["FAKE_GH_PULL_REQUESTS"] = json.dumps(pull_requests)
        if gh_exit_code is not None:
            environment["FAKE_GH_EXIT_CODE"] = str(gh_exit_code)
        stubs = scratch / f"stubs-{len(list(scratch.glob('stubs-*')))}"
        stubs.mkdir()
        if git_refuses is not None:
            (stubs / "git").write_text(
                "#!/bin/sh\n"
                f'case " $* " in *"{git_refuses}"*) echo "stub git refuses" >&2; exit 1 ;; esac\n'
                f'exec {shutil.which("git")} "$@"\n', encoding="utf-8")
            (stubs / "git").chmod(0o755)
        if lsof_body is not None:
            (stubs / "lsof").write_text(lsof_body, encoding="utf-8")
            (stubs / "lsof").chmod(0o755)
        environment["PATH"] = f"{stubs}{os.pathsep}{environment['PATH']}"
        return subprocess.run(
            [sys.executable, str(CLEAN_SCRIPT), "--repo", str(checkout), *flags],
            capture_output=True, text=True, check=False, env=environment)

    def named_worktree(name, owner=None, detach=False):
        path = managed / name
        if detach:
            git(checkout, "worktree", "add", "--detach", str(path), "origin/main")
        else:
            git(checkout, "worktree", "add", "-b", f"{name}-branch", str(path), "origin/main")
        if owner is not False:
            give_owner(path, owner or {"owner_kind": "agent-session", "agent_seat": "test-seat",
                                       "owner_key": stopped_agent_session_owner_key()})
        return path

    def commit_in(worktree, message):
        (worktree / f"{message}.txt").write_text(message + "\n", encoding="utf-8")
        git(worktree, "add", "-A")
        git(worktree, "commit", "-m", message)
        return git(worktree, "rev-parse", "HEAD").strip()

    def logged_events():
        lines = text_or_none(one_named_log) or ""
        return [(line.split("\t")[2], dict(pair.split("=", 1) for pair in line.split("\t")[3:]))
                for line in lines.splitlines()]

    def kept_and_failed(run, name):
        """Whether the run kept the item with a reason, ended with a FAILED line and exited 1."""
        lines = run.stdout.splitlines()
        return (run.returncode == 1 and any(line.startswith(f"{name}: kept — ") for line in lines)
                and bool(lines) and lines[-1].startswith("FAILED: "))

    # A worktree of a stopped agent-session, with a commit origin/main lacks and an untracked file.
    gone_wt = named_worktree("gone-wt")
    gone_tip = commit_in(gone_wt, "unlanded-work")
    (gone_wt / "untracked.txt").write_text("keep me\n", encoding="utf-8")
    removed = run_one_named(REMOVE_WORKTREE_FLAG, str(gone_wt))
    events = logged_events()
    check(f"{REMOVE_WORKTREE_FLAG} removes a worktree whose branch has commits origin/main lacks, and "
          "deletes the branch with -D",
          removed.returncode == 0 and not gone_wt.exists()
          and git(checkout, "branch", "--list", "gone-wt-branch") == ""
          and f"gone-wt: removed, branch gone-wt-branch deleted, its last commit {gone_tip}"
          in removed.stdout, removed.stdout + removed.stderr)
    check(f"{REMOVE_WORKTREE_FLAG} logs the worktree and the branch's last commit in the log of removals",
          [event for event, _ in events] == ["removed-worktree", "deleted-branch"]
          and events[1][1]["commit"] == gone_tip, str(events))
    check(f"{REMOVE_WORKTREE_FLAG} first copies the untracked file to a work-snapshot",
          any("untracked.txt" in git(checkout, "ls-tree", "-r", "--name-only", ref)
              for ref in git(checkout, "for-each-ref", "--format=%(refname)",
                             "refs/work-snapshots/").split()), removed.stdout)

    # An agent-seat's own worktree goes too: the caller, not the owner's state, decides.
    seat_wt = named_worktree("seat-wt", {"owner_kind": "agent-seat", "agent_seat": "test-seat"})
    seat_removed = run_one_named(REMOVE_WORKTREE_FLAG, str(seat_wt))
    check(f"{REMOVE_WORKTREE_FLAG} removes an agent-seat's own worktree",
          seat_removed.returncode == 0 and not seat_wt.exists(), seat_removed.stdout)

    open_wt = named_worktree("open-wt")
    open_head = git(open_wt, "rev-parse", "HEAD").strip()
    open_kept = run_one_named(REMOVE_WORKTREE_FLAG, str(open_wt), pull_requests=[
        {"number": 31, "state": "OPEN", "headRefName": "open-wt-branch", "headRefOid": "0" * 40}])
    check(f"{REMOVE_WORKTREE_FLAG} keeps a worktree whose branch has an open pull request, with no "
          "FAILED line and exit 0",
          open_kept.returncode == 0 and open_wt.exists()
          and "open-wt: kept — pull request #31 (open) has its branch or its HEAD commit as its "
              "head" in open_kept.stdout
          and "FAILED" not in open_kept.stdout, open_kept.stdout + open_kept.stderr)
    detached_open_wt = named_worktree("detached-open-wt", detach=True)
    detached_kept = run_one_named(REMOVE_WORKTREE_FLAG, str(detached_open_wt), pull_requests=[
        {"number": 32, "state": "OPEN", "headRefName": "elsewhere", "headRefOid": open_head}])
    check(f"{REMOVE_WORKTREE_FLAG} keeps a detached worktree whose HEAD is an open pull request's head",
          detached_kept.returncode == 0 and detached_open_wt.exists()
          and "pull request #32 (open)" in detached_kept.stdout, detached_kept.stdout)
    closed_kept = run_one_named(REMOVE_WORKTREE_FLAG, str(detached_open_wt), pull_requests=[
        {"number": 33, "state": "CLOSED", "headRefName": "elsewhere", "headRefOid": open_head}])
    check("a closed pull request does not keep the worktree",
          closed_kept.returncode == 0 and not detached_open_wt.exists(), closed_kept.stdout)
    detached_removal_line = next((line for line in closed_kept.stdout.splitlines()
                                  if line.startswith("detached-open-wt: removed")), "")
    detached_logged = [fields for kind, fields in logged_events()
                       if kind == "removed-worktree" and fields.get("path", "").endswith(
                           "detached-open-wt")]
    check(f"{REMOVE_WORKTREE_FLAG} on a detached HEAD deletes no branch, and the log names its head "
          "commit", detached_removal_line == "detached-open-wt: removed"
          and bool(detached_logged) and detached_logged[-1].get("branch") == "none"
          and detached_logged[-1].get("head") == open_head,
          closed_kept.stdout + str(detached_logged))

    not_a_worktree = run_one_named(REMOVE_WORKTREE_FLAG, str(scratch / "nowhere"))
    check(f"{REMOVE_WORKTREE_FLAG} on a path that is no worktree keeps nothing removed and fails",
          kept_and_failed(not_a_worktree, str(scratch / "nowhere")), not_a_worktree.stdout)
    main_checkout_named = run_one_named(REMOVE_WORKTREE_FLAG, str(checkout))
    check(f"{REMOVE_WORKTREE_FLAG} never removes the main checkout",
          kept_and_failed(main_checkout_named, str(checkout)) and checkout.exists(),
          main_checkout_named.stdout)

    no_owner_wt = named_worktree("no-owner-wt", owner=False)
    no_owner = run_one_named(REMOVE_WORKTREE_FLAG, str(no_owner_wt))
    check(f"{REMOVE_WORKTREE_FLAG} keeps a worktree with no owner file and fails",
          kept_and_failed(no_owner, "no-owner-wt") and no_owner_wt.exists()
          and "no owner file" in no_owner.stdout, no_owner.stdout)
    unreadable_wt = named_worktree("unreadable-wt")
    owner_file_path(unreadable_wt).write_text("not json", encoding="utf-8")
    unreadable = run_one_named(REMOVE_WORKTREE_FLAG, str(unreadable_wt))
    check(f"{REMOVE_WORKTREE_FLAG} keeps a worktree whose owner file cannot be read and fails",
          kept_and_failed(unreadable, "unreadable-wt") and unreadable_wt.exists()
          and "owner file could not be read" in unreadable.stdout, unreadable.stdout)

    locked_wt = named_worktree("locked-wt")
    git(checkout, "worktree", "lock", "--reason", "claude agent test", str(locked_wt))
    locked = run_one_named(REMOVE_WORKTREE_FLAG, str(locked_wt))
    check(f"{REMOVE_WORKTREE_FLAG} keeps a locked worktree and fails",
          kept_and_failed(locked, "locked-wt") and locked_wt.exists()
          and "locked with git worktree lock (claude agent test)" in locked.stdout, locked.stdout)
    git(checkout, "worktree", "unlock", str(locked_wt))

    prunable_wt = named_worktree("prunable-wt")
    shutil.move(str(prunable_wt), str(scratch / "moved-away"))
    prunable = run_one_named(REMOVE_WORKTREE_FLAG, str(prunable_wt))
    check(f"{REMOVE_WORKTREE_FLAG} keeps a worktree git would prune and fails",
          kept_and_failed(prunable, "prunable-wt") and "would prune" in prunable.stdout,
          prunable.stdout)
    shutil.move(str(scratch / "moved-away"), str(prunable_wt))

    rebasing_wt = named_worktree("rebasing-wt")
    Path(git(rebasing_wt, "rev-parse", "--path-format=absolute", "--git-path",
             "rebase-merge").strip()).mkdir()
    rebasing = run_one_named(REMOVE_WORKTREE_FLAG, str(rebasing_wt))
    check(f"{REMOVE_WORKTREE_FLAG} keeps a worktree with a rebase in progress and fails",
          kept_and_failed(rebasing, "rebasing-wt") and rebasing_wt.exists()
          and "a rebase is in progress" in rebasing.stdout, rebasing.stdout)

    snapshots_module_spec = importlib.util.spec_from_file_location(
        "uncommitted_work_snapshots_for_one_named",
        CLEAN_SCRIPT.resolve().parent.parent / "nc-systems" / "handoff" / "uncommitted-work-snapshots.py")
    snapshots_module = importlib.util.module_from_spec(snapshots_module_spec)
    snapshots_module_spec.loader.exec_module(snapshots_module)
    live_session = subprocess.Popen([sys.executable, "-c", "import sys; sys.stdin.read()"],
                                    stdin=subprocess.PIPE)
    try:
        live_wt = named_worktree("live-wt", {
            "owner_kind": "agent-session", "agent_seat": "test-seat",
            "owner_key": snapshots_module.owner_key_of_process(live_session.pid)})
        live = run_one_named(REMOVE_WORKTREE_FLAG, str(live_wt))
    finally:
        live_session.stdin.close()
        live_session.wait()
    check(f"{REMOVE_WORKTREE_FLAG} keeps a worktree whose owning agent-session runs and fails",
          kept_and_failed(live, "live-wt") and live_wt.exists() and "runs" in live.stdout,
          live.stdout)

    gh_wt = named_worktree("gh-wt")
    gh_failed = run_one_named(REMOVE_WORKTREE_FLAG, str(gh_wt), gh_exit_code=3)
    check(f"{REMOVE_WORKTREE_FLAG} keeps the worktree when gh cannot list the pull requests and fails",
          kept_and_failed(gh_failed, "gh-wt") and gh_wt.exists()
          and "stand-in listing failure" in gh_failed.stdout, gh_failed.stdout)

    occupied = run_one_named(REMOVE_WORKTREE_FLAG, str(gh_wt),
                             lsof_body=f"#!/bin/sh\nprintf 'p1\\nn{gh_wt}\\n'\n")
    check(f"{REMOVE_WORKTREE_FLAG} keeps a worktree a live process has its working directory in and fails",
          kept_and_failed(occupied, "gh-wt") and gh_wt.exists()
          and "a live process is rooted inside it" in occupied.stdout, occupied.stdout)

    status_failed = run_one_named(REMOVE_WORKTREE_FLAG, str(gh_wt), git_refuses=" status ")
    check(f"{REMOVE_WORKTREE_FLAG} keeps the worktree when git cannot list its uncommitted changes",
          kept_and_failed(status_failed, "gh-wt") and gh_wt.exists()
          and "cannot list its uncommitted changes" in status_failed.stdout, status_failed.stdout)
    ignored_failed = run_one_named(REMOVE_WORKTREE_FLAG, str(gh_wt), git_refuses=" --ignored ")
    check(f"{REMOVE_WORKTREE_FLAG} keeps the worktree when git cannot list the files its removal "
          "discards", kept_and_failed(ignored_failed, "gh-wt") and gh_wt.exists()
          and "cannot list its files" in ignored_failed.stdout, ignored_failed.stdout)

    walk_wt = named_worktree("walk-wt")
    (walk_wt / "docs" / "walk").mkdir(parents=True)
    (walk_wt / "docs" / "walk" / "lonely-walk-minutes.md").write_text("# minutes\n", encoding="utf-8")
    walk_refused = run_one_named(REMOVE_WORKTREE_FLAG, str(walk_wt))
    check(f"{REMOVE_WORKTREE_FLAG} keeps a worktree whose walk does not ship, fails, and promises no "
          "daily retry", walk_refused.returncode == 1 and walk_wt.exists()
          and walk_refused.stdout.splitlines()[-1].startswith("FAILED: ")
          and "the next scripts/clean-worktrees.py --remove" not in walk_refused.stdout,
          walk_refused.stdout + walk_refused.stderr)

    snapshot_wt = named_worktree("snapshot-wt")
    (snapshot_wt / "unsaved.txt").write_text("unsaved\n", encoding="utf-8")
    common_git_directory = Path(git(checkout, "rev-parse", "--path-format=absolute",
                                    "--git-common-dir").strip())
    snapshot_refs = common_git_directory / "refs" / "work-snapshots"
    shutil.move(str(snapshot_refs), str(scratch / "work-snapshots-aside"))
    snapshot_refs.write_text("", encoding="utf-8")
    try:
        snapshot_failed = run_one_named(REMOVE_WORKTREE_FLAG, str(snapshot_wt))
    finally:
        snapshot_refs.unlink()
        shutil.move(str(scratch / "work-snapshots-aside"), str(snapshot_refs))
    check(f"{REMOVE_WORKTREE_FLAG} keeps the worktree when its work-snapshot cannot be written, fails, "
          "and promises no daily retry",
          snapshot_failed.returncode == 1 and (snapshot_wt / "unsaved.txt").is_file()
          and "snapshot-wt: work-snapshot FAILED" in snapshot_failed.stdout
          and "the next scripts/clean-worktrees.py --remove" not in snapshot_failed.stdout
          and snapshot_failed.stdout.splitlines()[-1].startswith("FAILED: "),
          snapshot_failed.stdout + snapshot_failed.stderr)

    removal_failed = run_one_named(REMOVE_WORKTREE_FLAG, str(gh_wt), git_refuses=" worktree remove ")
    check(f"{REMOVE_WORKTREE_FLAG} fails when git cannot remove the worktree",
          removal_failed.returncode == 1 and gh_wt.exists()
          and "gh-wt: removal FAILED" in removal_failed.stdout
          and removal_failed.stdout.splitlines()[-1].startswith("FAILED: "), removal_failed.stdout)

    branch_kept_wt = named_worktree("branch-kept-wt")
    branch_failed = run_one_named(REMOVE_WORKTREE_FLAG, str(branch_kept_wt), git_refuses=" branch -D ")
    check(f"{REMOVE_WORKTREE_FLAG} fails when the worktree goes but its branch cannot be deleted",
          branch_failed.returncode == 1 and not branch_kept_wt.exists()
          and git(checkout, "branch", "--list", "branch-kept-wt-branch") != ""
          and "deleting its branch branch-kept-wt-branch FAILED" in branch_failed.stdout
          and branch_failed.stdout.splitlines()[-1].startswith("FAILED: "), branch_failed.stdout)

    log_wt = named_worktree("log-wt")
    not_a_directory = scratch / "not-a-directory"
    not_a_directory.write_text("", encoding="utf-8")
    log_failed = run_one_named(REMOVE_WORKTREE_FLAG, str(log_wt),
                               log_file=not_a_directory / "log.txt")
    check(f"{REMOVE_WORKTREE_FLAG} fails when its log of removals line cannot be written",
          log_failed.returncode == 1 and not log_wt.exists()
          and "log of removals line(s) FAILED" in log_failed.stdout
          and log_failed.stdout.splitlines()[-1].startswith("FAILED: "), log_failed.stdout)

    listing_failed = run_one_named(REMOVE_WORKTREE_FLAG, str(gh_wt), git_refuses=" worktree list ")
    check(f"{REMOVE_WORKTREE_FLAG} fails with a FAILED line when git cannot list the worktrees",
          listing_failed.returncode == 1 and gh_wt.exists()
          and "git could not list the worktrees" in listing_failed.stdout
          and listing_failed.stdout.splitlines()[-1].startswith("FAILED: "),
          listing_failed.stdout + listing_failed.stderr)

    # --force-delete-branch
    one_named_log.unlink()
    git(checkout, "branch", "lone-branch", "origin/main")
    lone_wt = scratch / "lone-holder"
    git(checkout, "worktree", "add", str(lone_wt), "lone-branch")
    lone_tip = commit_in(lone_wt, "lone-work")
    git(checkout, "worktree", "remove", str(lone_wt))
    deleted = run_one_named(FORCE_DELETE_BRANCH_FLAG, "lone-branch")
    events = logged_events()
    check(f"{FORCE_DELETE_BRANCH_FLAG} deletes a branch with commits origin/main lacks and logs its last "
          "commit", deleted.returncode == 0
          and git(checkout, "branch", "--list", "lone-branch") == ""
          and f"branch lone-branch: deleted, its last commit {lone_tip}, with 1 commit(s)"
          in deleted.stdout
          and events == [("deleted-branch", {**events[0][1], "branch": "lone-branch",
                                             "commit": lone_tip,
                                             "commits-not-on-origin-main": "1"})],
          deleted.stdout + deleted.stderr + str(events))

    main_named = run_one_named(FORCE_DELETE_BRANCH_FLAG, "main")
    check(f"{FORCE_DELETE_BRANCH_FLAG} never deletes main", kept_and_failed(main_named, "branch main")
          and git(checkout, "branch", "--list", "main") != "", main_named.stdout)
    missing = run_one_named(FORCE_DELETE_BRANCH_FLAG, "no-such-branch")
    check(f"{FORCE_DELETE_BRANCH_FLAG} on a branch that does not exist fails",
          kept_and_failed(missing, "branch no-such-branch"), missing.stdout)
    held = run_one_named(FORCE_DELETE_BRANCH_FLAG, "gh-wt-branch")
    check(f"{FORCE_DELETE_BRANCH_FLAG} keeps a branch a worktree has checked out, and names the command that "
          "removes that worktree", kept_and_failed(held, "branch gh-wt-branch")
          and f"--repo {shlex.quote(str(checkout))} --remove-worktree-and-force-delete-its-branch {shlex.quote(str(gh_wt))}"
          in held.stdout, held.stdout)

    git(checkout, "branch", "reviewed-branch", "origin/main")
    reviewed = run_one_named(FORCE_DELETE_BRANCH_FLAG, "reviewed-branch", pull_requests=[
        {"number": 41, "state": "OPEN", "headRefName": "reviewed-branch", "headRefOid": "0" * 40}])
    check(f"{FORCE_DELETE_BRANCH_FLAG} keeps the head branch of an open pull request, with no FAILED line and "
          "exit 0", reviewed.returncode == 0
          and git(checkout, "branch", "--list", "reviewed-branch") != ""
          and "pull request #41 (open)" in reviewed.stdout and "FAILED" not in reviewed.stdout,
          reviewed.stdout)
    gh_branch = run_one_named(FORCE_DELETE_BRANCH_FLAG, "reviewed-branch", gh_exit_code=3)
    check(f"{FORCE_DELETE_BRANCH_FLAG} keeps the branch when gh cannot list the pull requests and fails",
          kept_and_failed(gh_branch, "branch reviewed-branch")
          and git(checkout, "branch", "--list", "reviewed-branch") != "", gh_branch.stdout)
    refused = run_one_named(FORCE_DELETE_BRANCH_FLAG, "reviewed-branch", git_refuses=" branch -D ")
    check(f"{FORCE_DELETE_BRANCH_FLAG} fails when git branch -D refuses",
          kept_and_failed(refused, "branch reviewed-branch")
          and git(checkout, "branch", "--list", "reviewed-branch") != "", refused.stdout)
    held_listing_failed = run_one_named(FORCE_DELETE_BRANCH_FLAG, "reviewed-branch",
                                        git_refuses=" worktree list ")
    check(f"{FORCE_DELETE_BRANCH_FLAG} fails with a FAILED line when git cannot list the worktrees",
          held_listing_failed.returncode == 1
          and git(checkout, "branch", "--list", "reviewed-branch") != ""
          and held_listing_failed.stdout.splitlines()[-1].startswith("FAILED: "),
          held_listing_failed.stdout + held_listing_failed.stderr)
    uncounted = run_one_named(FORCE_DELETE_BRANCH_FLAG, "reviewed-branch", git_refuses=" rev-list --count ")
    check(f"{FORCE_DELETE_BRANCH_FLAG} deletes the branch when its commits cannot be counted, and says unknown",
          uncounted.returncode == 0 and git(checkout, "branch", "--list", "reviewed-branch") == ""
          and "with unknown commit(s) origin/main lacks" in uncounted.stdout, uncounted.stdout)
    git(checkout, "branch", "log-branch", "origin/main")
    branch_log_failed = run_one_named(FORCE_DELETE_BRANCH_FLAG, "log-branch",
                                      log_file=not_a_directory / "log.txt")
    check(f"{FORCE_DELETE_BRANCH_FLAG} fails when its log of removals line cannot be written",
          branch_log_failed.returncode == 1
          and git(checkout, "branch", "--list", "log-branch") == ""
          and branch_log_failed.stdout.splitlines()[-1].startswith("FAILED: "),
          branch_log_failed.stdout)

    for flags, case in (([REMOVE_WORKTREE_FLAG], "a flag with no value"),
                        ([REMOVE_WORKTREE_FLAG, str(gh_wt), "--remove"], "with --remove"),
                        ([FORCE_DELETE_BRANCH_FLAG, "x", "--only-done"], "with --only-done"),
                        ([REMOVE_WORKTREE_FLAG, str(gh_wt), FORCE_DELETE_BRANCH_FLAG, "x"], "both flags")):
        bad = run_one_named(*flags)
        check(f"a bad invocation of the one-named modes exits 2: {case}",
              bad.returncode == 2 and gh_wt.exists(), bad.stdout + bad.stderr)

# --- Merge-lane review checkouts: judged by the pull request their name holds ---
with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch).resolve()
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
    fake_home = scratch / "home"
    (fake_home / ".claude" / "handoffs").mkdir(parents=True)
    review_directory = fake_home / ".cache" / "merge-lane-review-worktrees"
    review_directory.mkdir(parents=True)

    def review_checkout(name, directory=review_directory):
        path = directory / name
        git(checkout, "worktree", "add", "--detach", str(path), "origin/main")
        return path

    merged_checkout = review_checkout("pr10-merged")
    # merge-lane-2's local merge commit: on no branch, and origin/main lacks it.
    (merged_checkout / "merged.txt").write_text("merged\n", encoding="utf-8")
    git(merged_checkout, "add", "-A")
    git(merged_checkout, "commit", "-m", "local merge commit")
    (merged_checkout / "test-output.txt").write_text("left by a test run\n", encoding="utf-8")
    closed_checkout = review_checkout("tools-main-11r2")
    open_checkout = review_checkout("pr12-head")
    main_checkout = review_checkout("main")
    main_green_checkout = review_checkout("main-green-0b3364167")
    unlisted_checkout = review_checkout("verdict-99r1")
    two_numbers_checkout = review_checkout("head-13-12345678")
    locked_checkout = review_checkout("pr14-head")
    git(checkout, "worktree", "lock", "--reason", "reviewing", str(locked_checkout))
    occupied_checkout = review_checkout("pr15-head")
    elsewhere = scratch / "elsewhere"
    elsewhere.mkdir()
    outside_checkout = review_checkout("pr16-head", elsewhere)
    # The merge program's after-merge window: merged an hour ago, its main test checkout still there.
    recently_merged_checkout = review_checkout("pr17-merge-commit-on-main-worktree")
    no_closing_time_checkout = review_checkout("pr18-head")
    long_ago = "2026-01-01T00:00:00Z"
    an_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    review_pull_requests = [
        {"number": 10, "state": "MERGED", "headRefName": "a", "headRefOid": "1" * 40,
         "closedAt": long_ago},
        {"number": 11, "state": "CLOSED", "headRefName": "b", "headRefOid": "2" * 40,
         "closedAt": long_ago},
        {"number": 12, "state": "OPEN", "headRefName": "c", "headRefOid": "3" * 40,
         "closedAt": None},
        {"number": 13, "state": "MERGED", "headRefName": "d", "headRefOid": "4" * 40,
         "closedAt": long_ago},
        {"number": 14, "state": "MERGED", "headRefName": "e", "headRefOid": "5" * 40,
         "closedAt": long_ago},
        {"number": 15, "state": "MERGED", "headRefName": "f", "headRefOid": "6" * 40,
         "closedAt": long_ago},
        {"number": 16, "state": "MERGED", "headRefName": "g", "headRefOid": "7" * 40,
         "closedAt": long_ago},
        {"number": 17, "state": "MERGED", "headRefName": "h", "headRefOid": "8" * 40,
         "closedAt": an_hour_ago},
        {"number": 18, "state": "MERGED", "headRefName": "i", "headRefOid": "9" * 40},
    ]
    review_log = scratch / "removals-log.txt"

    def run_review_cleanup(*flags, gh_exit=None):
        environment = dict(os.environ, HOME=str(fake_home),
                           FAKE_GH_PULL_REQUESTS=json.dumps(review_pull_requests))
        environment[REMOVALS_LOG_OVERRIDE_VARIABLE] = str(review_log)
        if gh_exit is not None:
            environment["FAKE_GH_EXIT_CODE"] = str(gh_exit)
        return subprocess.run([sys.executable, str(CLEAN_SCRIPT), "--repo", str(checkout), *flags],
                              capture_output=True, text=True, check=False, env=environment)

    def review_line(output, name):
        return next((line for line in output.splitlines() if line.startswith(f"{name}:")), "")

    every_checkout = (merged_checkout, closed_checkout, open_checkout, main_checkout,
                      main_green_checkout, unlisted_checkout, two_numbers_checkout, locked_checkout,
                      occupied_checkout, outside_checkout, recently_merged_checkout,
                      no_closing_time_checkout)
    # Stands in for a process working in a review checkout; lives until its stdin closes.
    review_occupant = subprocess.Popen([sys.executable, "-c", "import sys; sys.stdin.read()"],
                                       stdin=subprocess.PIPE, cwd=occupied_checkout)
    try:
        gh_failed = run_review_cleanup("--remove", gh_exit=1)
        check("when gh cannot list the pull requests, every merge-lane review checkout is kept and "
              "the line names gh's failure, as for other worktrees whose verdict needs a pull request",
              gh_failed.returncode == 0 and all(path.exists() for path in every_checkout)
              and review_line(gh_failed.stdout, "pr10-merged").startswith(
                  "pr10-merged: kept — it is a merge-lane review checkout of pull request #10, whose "
                  "state could not be read: `gh pr list")
              and "gh: stand-in listing failure" in review_line(gh_failed.stdout, "pr10-merged"),
              gh_failed.stdout + gh_failed.stderr)

        report = run_review_cleanup().stdout
        check("the report calls a merge-lane review checkout of a merged pull request done, naming "
              "the untracked file its removal discards",
              review_line(report, "pr10-merged").startswith(
                  "pr10-merged: done — it is a merge-lane review checkout of pull request #10 "
                  "(merged); removing it discards 1 uncommitted, untracked or ignored file(s): "
                  "test-output.txt"), report)

        removal = run_review_cleanup("--remove")
        check("--remove removes the merge-lane review checkouts of a merged and a closed pull request",
              not merged_checkout.exists() and not closed_checkout.exists()
              and "pr10-merged: removed" in removal.stdout
              and "tools-main-11r2: removed" in removal.stdout, removal.stdout + removal.stderr)
        check("removing a merge-lane review checkout puts its local merge commit on no branch, and "
              "its untracked file in no work-snapshot",
              "worktree-cleaner-detached-commits" not in git(checkout, "branch", "--list")
              and git(checkout, "for-each-ref", "refs/work-snapshots/") == "", removal.stdout)
        check("each removal of a merge-lane review checkout is written to the log of removals",
              f"path={merged_checkout}\t" in (text_or_none(review_log) or "")
              and f"path={closed_checkout}\t" in (text_or_none(review_log) or ""),
              text_or_none(review_log) or "no log written")
        check("a merge-lane review checkout of an open pull request is kept",
              open_checkout.exists() and review_line(removal.stdout, "pr12-head")
              == "pr12-head: kept — it is a merge-lane review checkout of pull request #12 (open)",
              removal.stdout)
        check("main and main-green-<commit> are kept, their names holding no pull request number",
              main_checkout.exists() and main_green_checkout.exists()
              and "name holds no single pull request number" in review_line(removal.stdout, "main")
              and "name holds no single pull request number"
              in review_line(removal.stdout, "main-green-0b3364167"), removal.stdout)
        check("a name holding two numbers is kept, though one is a merged pull request's",
              two_numbers_checkout.exists()
              and "name holds no single pull request number"
              in review_line(removal.stdout, "head-13-12345678"), removal.stdout)
        check("a pull request number gh's listing does not hold keeps the checkout",
              unlisted_checkout.exists()
              and "pull request #99, which gh's listing does not hold"
              in review_line(removal.stdout, "verdict-99r1"), removal.stdout)
        check("a locked merge-lane review checkout of a merged pull request is kept",
              locked_checkout.exists()
              and review_line(removal.stdout, "pr14-head").startswith(
                  "pr14-head: kept — locked with git worktree lock (reviewing)"), removal.stdout)
        check("a merge-lane review checkout of a merged pull request is kept while a live process "
              "works in it",
              occupied_checkout.exists()
              and review_line(removal.stdout, "pr15-head")
              == "pr15-head: kept — a live process is rooted inside it", removal.stdout)
        check("a worktree with no owner file outside the merge-lane review checkouts directory is "
              "kept, though its name holds a merged pull request's number",
              outside_checkout.exists()
              and "it has no owner file, and the cleaner removes only a worktree holding one"
              in review_line(removal.stdout, "pr16-head"), removal.stdout)
        check("a merge-lane review checkout of a pull request merged an hour ago is kept, while "
              "merge-lane-2's merge program may still be testing main in it",
              recently_merged_checkout.exists()
              and review_line(removal.stdout, "pr17-merge-commit-on-main-worktree")
              == "pr17-merge-commit-on-main-worktree: kept — it is a merge-lane review checkout of "
                 "pull request #17 (merged), finished less than 24 hours ago; the cleaner waits that "
                 "long because merge-lane-2's merge program may still be using it, unseen by the "
                 "vacancy check", removal.stdout)
        check("a merge-lane review checkout whose pull request gh gives no closing time for is kept",
              no_closing_time_checkout.exists()
              and "whose closing time gh did not give in a form this program reads: KeyError"
              in review_line(removal.stdout, "pr18-head"), removal.stdout)
        check("--remove exits 0 when it only removed and kept merge-lane review checkouts",
              removal.returncode == 0, removal.stdout + removal.stderr)
    finally:
        review_occupant.kill()
        review_occupant.wait()

# --- Claude Code's lock exception: a lock whose claude process has ended is unlocked ---
# Linux only: the case reads its ended process's start and the boot id from /proc.
if sys.platform.startswith("linux"):
    with tempfile.TemporaryDirectory() as scratch:
        scratch = Path(scratch).resolve()
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
        lock_home = scratch / "home"
        (lock_home / ".claude" / "handoffs").mkdir(parents=True)
        for seat in ("seat-one", "seat-two"):
            (lock_home / "agents" / seat).mkdir(parents=True)
            (lock_home / ".claude" / "handoffs" / f"{seat}-handoff.md").write_text(
                "handoff\n", encoding="utf-8")

        def transcript_names_subagent(seat, agent_id):
            project = lock_home / ".claude" / "projects" / ("-" + "-".join(
                (lock_home / "agents" / seat).parts[1:]).replace(".", "-").replace("_", "-"))
            directory = project / "session-1" / "subagents"
            directory.mkdir(parents=True, exist_ok=True)
            (directory / f"agent-{agent_id}.jsonl").write_text("{}\n", encoding="utf-8")

        snapshots_module_spec = importlib.util.spec_from_file_location(
            "uncommitted_work_snapshots_for_lock_cases",
            CLEAN_SCRIPT.resolve().parent.parent / "nc-systems" / "handoff"
            / "uncommitted-work-snapshots.py")
        snapshots_module = importlib.util.module_from_spec(snapshots_module_spec)
        snapshots_module_spec.loader.exec_module(snapshots_module)
        ended = subprocess.Popen([sys.executable, "-c", "pass"])
        ended_start = snapshots_module.linux_start_ticks(ended.pid)
        ended.wait()
        ended_owner_key = f"{snapshots_module.linux_boot_id()}-{ended.pid}-{ended_start}"

        def locked_worktree(name, agent_id, owner=None):
            path = managed / name
            git(checkout, "worktree", "add", "-b", f"{name}-branch", str(path), "origin/main")
            if owner is not None:
                give_owner(path, owner)
            git(checkout, "worktree", "lock", "--reason",
                f"claude agent agent-{agent_id} (pid {ended.pid} start {ended_start})", str(path))
            return path

        def is_locked(path):
            return (owner_file_path(path).parent / "locked").exists()

        owned = locked_worktree("ended-lock-owned-wt", "aowned", {
            "owner_kind": "agent-session", "agent_seat": "seat-one", "owner_key": ended_owner_key})
        (owned / "unsaved.txt").write_text("only here\n", encoding="utf-8")
        named = locked_worktree("ended-lock-named-wt", "anamed")
        transcript_names_subagent("seat-one", "anamed")
        open_named = locked_worktree("ended-lock-open-pull-request-wt", "aopen")
        transcript_names_subagent("seat-two", "aopen")
        unnamed = locked_worktree("ended-lock-unnamed-wt", "aunnamed")
        twice = locked_worktree("ended-lock-two-seats-wt", "atwice")
        transcript_names_subagent("seat-one", "atwice")
        transcript_names_subagent("seat-two", "atwice")
        open_pull_requests = json.dumps([{
            "number": 31, "state": "OPEN", "headRefName": "ended-lock-open-pull-request-wt-branch",
            "headRefOid": git(open_named, "rev-parse", "HEAD").strip(), "closedAt": None}])

        def run_with_lock_home(*flags, path_prefix=None):
            environment = dict(os.environ, HOME=str(lock_home),
                               FAKE_GH_PULL_REQUESTS=open_pull_requests)
            if path_prefix is not None:
                environment["PATH"] = f"{path_prefix}{os.pathsep}{environment['PATH']}"
            return subprocess.run([sys.executable, str(CLEAN_SCRIPT), "--repo", str(checkout),
                                   *flags], capture_output=True, text=True, check=False,
                                  env=environment)

        def lock_line(output, name):
            return next((line for line in output.splitlines()
                         if line.startswith(f"{name}: kept") or line.startswith(f"{name}: done")),
                        "")

        report = run_with_lock_home().stdout
        check("the report says --remove unlocks a worktree whose Claude Code lock names an ended "
              "process, then judges it by its owner file",
              lock_line(report, "ended-lock-owned-wt").startswith(
                  f"ended-lock-owned-wt: done — Claude Code's lock names claude process {ended.pid}")
              and "has ended, so --remove unlocks it, then judges it: its owner, an agent-session "
                  "of seat-one" in lock_line(report, "ended-lock-owned-wt"), report)
        check("the report says --remove first writes the owner file naming the ended agent-session "
              "and the agent-seat whose transcripts name the subagent",
              f"so --remove unlocks it, writing first its owner file naming an agent-session of "
              f"seat-one (claude process {ended_owner_key}), then judges it: its owner"
              in lock_line(report, "ended-lock-named-wt")
              and lock_line(report, "ended-lock-named-wt").startswith("ended-lock-named-wt: done"),
              report)
        check("the report changes nothing: every lock stays and no owner file is written",
              all(is_locked(path) for path in (owned, named, open_named, unnamed, twice))
              and not owner_file_path(named).exists(), report)
        for path, why in ((unnamed, "no agent-seat's Claude Code transcripts name subagent "
                                    "agent-aunnamed"),
                          (twice, "the Claude Code transcripts of 2 agent-seats, seat-one, "
                                  "seat-two, name subagent agent-atwice")):
            check(f"a worktree with no owner file is kept, locked, for the user when {why}",
                  why in lock_line(report, path.name)
                  and lock_line(report, path.name).startswith(f"{path.name}: kept")
                  and "the user keeps or deletes it" in lock_line(report, path.name), report)
        check("the count lines name the worktrees for the user to keep or delete",
              "worktrees for the user to keep or delete, locked by Claude Code for a subagent whose "
              f"claude process has ended and which no one agent-seat's Claude Code transcripts "
              f"name: {twice}, {unnamed}" in report, report)

        failing_git = scratch / "failing-git"
        failing_git.mkdir()
        (failing_git / "git").write_text(
            "#!/bin/sh\n"
            'case " $* " in *" worktree unlock "*) printf "unlock refused%0200d" 0 >&2; kill -9 $$ ;; esac\n'
            f'exec {shutil.which("git")} "$@"\n', encoding="utf-8")
        (failing_git / "git").chmod(0o755)
        refused = run_with_lock_home("--remove", path_prefix=failing_git)
        check("an unlock that fails keeps the worktree locked, says FAILED and exits 1, after the "
              "owner file is written",
              refused.returncode == 1 and is_locked(named) and owner_file_path(named).exists()
              and "ended-lock-named-wt: unlock FAILED, worktree kept — git worktree unlock exited "
                  "-9: unlock refused" + "0" * 146 + "\n" in refused.stdout
              and "ended-lock-named-wt: removal" not in refused.stdout,
              refused.stdout + refused.stderr)

        garbled = locked_worktree("ended-lock-unreadable-owner-wt", "agarbled")
        owner_file_path(garbled).write_text("{not json", encoding="utf-8")
        garbled_line = lock_line(run_with_lock_home().stdout, "ended-lock-unreadable-owner-wt")
        check("an owner file that cannot be read keeps a worktree whose lock's process has ended",
              garbled_line.startswith("ended-lock-unreadable-owner-wt: kept — locked with git "
                                      "worktree lock")
              and "whose claude process has ended, and its owner file could not be read"
              in garbled_line, garbled_line)
        exiting_git = scratch / "exiting-git"
        exiting_git.mkdir()
        (exiting_git / "git").write_text(
            "#!/bin/sh\n"
            'case " $* " in *" worktree unlock "*) echo "unlock refused" >&2; exit 1 ;; esac\n'
            f'exec {shutil.which("git")} "$@"\n', encoding="utf-8")
        (exiting_git / "git").chmod(0o755)
        refused_again = run_with_lock_home("--remove", path_prefix=exiting_git)
        check("an unlock that exits nonzero keeps the worktree locked and says FAILED",
              refused_again.returncode == 1 and is_locked(named)
              and "ended-lock-named-wt: unlock FAILED, worktree kept — git worktree unlock exited "
                  "1: unlock refused" in refused_again.stdout,
              refused_again.stdout + refused_again.stderr)
        unwritable = locked_worktree("ended-lock-unwritable-owner-wt", "aunwritable")
        transcript_names_subagent("seat-one", "aunwritable")
        owner_file_path(unwritable).parent.chmod(0o500)
        try:
            removal = run_with_lock_home("--remove")
        finally:
            owner_file_path(unwritable).parent.chmod(0o755)
        check("an owner file that cannot be written keeps the worktree locked, says FAILED and "
              "exits 1",
              removal.returncode == 1 and is_locked(unwritable)
              and not owner_file_path(unwritable).exists()
              and "ended-lock-unwritable-owner-wt: owner file FAILED, worktree kept locked"
              in removal.stdout, removal.stdout + removal.stderr)
        check("--remove unlocks a worktree whose owner has stopped and removes it, its files in a "
              "work-snapshot",
              not owned.exists() and "ended-lock-owned-wt: unlocked, since Claude Code's lock names "
              f"claude process {ended.pid}" in removal.stdout
              and "ended-lock-owned-wt: its uncommitted and untracked files are kept in the "
                  "work-snapshot" in removal.stdout, removal.stdout + removal.stderr)
        check("--remove removes the worktree it unlocked whose owner file it had written",
              not named.exists() and "ended-lock-named-wt: removed" in removal.stdout,
              removal.stdout)
        owner_written = json.loads(text_or_none(owner_file_path(open_named)) or "null")
        check("--remove writes the owner file naming the ended agent-session and the agent-seat "
              "whose transcripts name the subagent, unlocks it, and an open pull request keeps it",
              open_named.exists() and not is_locked(open_named)
              and owner_written == {"owner_kind": "agent-session", "agent_seat": "seat-two",
                                    "owner_key": ended_owner_key}
              and "pull request #31 (open)" in lock_line(removal.stdout,
                                                          "ended-lock-open-pull-request-wt"),
              f"{owner_written} {removal.stdout}")
        check("--remove leaves locked, with no owner file, the worktrees for the user",
              all(path.exists() and is_locked(path) and not owner_file_path(path).exists()
                  for path in (unnamed, twice)), removal.stdout)

        (lock_home / "agents").chmod(0o000)
        try:
            unreadable = run_with_lock_home()
        finally:
            (lock_home / "agents").chmod(0o755)
        check("an agent-seat lookup that fails keeps the worktree, as one that could not be checked",
              "ended-lock-unnamed-wt: kept — locked with git worktree lock" in unreadable.stdout
              and "could not be read: PermissionError" in lock_line(unreadable.stdout,
                                                                     "ended-lock-unnamed-wt"),
              unreadable.stdout + unreadable.stderr)

# --- A removal stopped partway ---
# A real kill cannot be timed to land inside `git worktree remove`, so a stub git does what git
# does first, deleting the worktree's .git file and some files, then kills the cleaner that ran it.
with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch).resolve()
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
    killing_git = scratch / "killing-git"
    killing_git.mkdir()
    (killing_git / "git").write_text(
        f"#!{sys.executable}\n"
        "import os, signal, sys\n"
        "from pathlib import Path\n"
        "if 'worktree' in sys.argv and 'remove' in sys.argv:\n"
        "    left = Path(sys.argv[-1])\n"
        "    (left / '.git').unlink()\n"
        "    (left / 'README.md').unlink()\n"
        "    os.kill(os.getppid(), signal.SIGKILL)\n"
        "    sys.exit(0)\n"
        f"os.execv({shutil.which('git')!r}, ['git'] + sys.argv[1:])\n", encoding="utf-8")
    (killing_git / "git").chmod(0o755)

    def stopped_partway(name):
        """A done worktree whose --remove run was killed inside `git worktree remove`."""
        path = managed / name
        git(checkout, "worktree", "add", "-b", f"{name}-branch", str(path), "origin/main")
        give_stopped_owner(path)
        (path / "untracked.txt").write_text("x\n", encoding="utf-8")
        environment = dict(os.environ)
        environment["PATH"] = f"{killing_git}{os.pathsep}{environment['PATH']}"
        killed = subprocess.run(
            [sys.executable, str(CLEAN_SCRIPT), "--repo", str(checkout), "--remove"],
            capture_output=True, text=True, check=False, env=environment)
        return path, killed

    def registered(path):
        return str(path) in git(checkout, "worktree", "list", "--porcelain")

    first, killed = stopped_partway("stopped-partway-wt")
    check("the stub git kills the cleaner inside the removal, leaving the worktree half removed",
          killed.returncode == -signal.SIGKILL and first.exists()
          and not (first / ".git").exists() and registered(first),
          f"{killed.returncode} {killed.stdout}{killed.stderr}")
    report = run_clean(checkout)
    check("the report names a removal stopped partway as done, and not as a dead registration",
          "stopped-partway-wt: done — an earlier scripts/clean-worktrees.py --remove was stopped "
          "while removing this worktree"
          in report.stdout
          and "stopped-partway-wt" not in next((line for line in report.stdout.splitlines()
                                                if "git worktree prune" in line), ""),
          report.stdout)
    finished = run_clean(checkout, "--remove")
    check("the next --remove finishes the removal: directory, registration and branch go",
          finished.returncode == 0 and "stopped-partway-wt: removed, branch stopped-partway-wt-"
          "branch deleted" in finished.stdout
          and not first.exists() and not registered(first)
          and git(checkout, "branch", "--list", "stopped-partway-wt-branch").strip() == "",
          finished.stdout + finished.stderr)

    without_file = managed / "dotgit-deleted-by-hand-wt"
    git(checkout, "worktree", "add", "-b", "dotgit-deleted-by-hand-wt-branch", str(without_file),
        "origin/main")
    give_stopped_owner(without_file)
    (without_file / ".git").unlink()
    by_hand = run_clean(checkout, "--remove")
    check("a worktree whose .git file went with no removal begun is kept, as before",
          without_file.exists() and registered(without_file)
          and "dotgit-deleted-by-hand-wt: kept — git would prune its registration" in by_hand.stdout,
          by_hand.stdout)

    named, _ = stopped_partway("stopped-partway-named-wt")
    named_run = run_clean(checkout, "--remove-worktree-and-force-delete-its-branch", str(named))
    check("--remove-worktree-and-force-delete-its-branch finishes a removal stopped partway",
          named_run.returncode == 0 and not named.exists() and not registered(named)
          and git(checkout, "branch", "--list", "stopped-partway-named-wt-branch").strip() == "",
          named_run.stdout + named_run.stderr)

    stuck, _ = stopped_partway("stopped-partway-undeletable-wt")
    (stuck / "kept-dir").mkdir()
    (stuck / "kept-dir" / "file").write_text("x\n", encoding="utf-8")
    (stuck / "kept-dir").chmod(0o500)
    try:
        undeletable = run_clean(checkout, "--remove")
    finally:
        (stuck / "kept-dir").chmod(0o755)
    check("a finish that cannot delete what is left fails, exit 1, and keeps the registration",
          undeletable.returncode == 1 and registered(stuck)
          and "stopped-partway-undeletable-wt: removal FAILED — an earlier "
              "scripts/clean-worktrees.py --remove was stopped partway" in undeletable.stdout,
          undeletable.stdout + undeletable.stderr)

    sought = managed / "zz-sought-wt"
    git(checkout, "worktree", "add", "-b", "zz-sought-wt-branch", str(sought), "origin/main")
    unreadable_first = managed / "aa-unreadable-gitdir-wt"
    git(checkout, "worktree", "add", "-b", "aa-unreadable-gitdir-wt-branch", str(unreadable_first),
        "origin/main")
    gitdir_file = Path(git(unreadable_first, "rev-parse", "--absolute-git-dir").strip()) / "gitdir"
    gitdir_file.chmod(0o000)
    try:
        found = load_clean_worktrees_module().worktree_own_git_directory_find_even_with_its_dot_git_file_gone(checkout, sought)
    finally:
        gitdir_file.chmod(0o644)
    check("a registration whose gitdir file cannot be read is passed over, and the search goes on",
          found is not None and (found / "gitdir").read_text(encoding="utf-8").strip()
          == str((sought / ".git").resolve()), str(found))

    relative = managed / "relative-gitdir-wt"
    git(checkout, "worktree", "add", "-b", "relative-gitdir-wt-branch", str(relative), "origin/main")
    relative_registration = Path(git(relative, "rev-parse", "--absolute-git-dir").strip())
    (relative_registration / "gitdir").write_text(
        os.path.relpath(relative / ".git", relative_registration) + "\n", encoding="utf-8")
    module = load_clean_worktrees_module()
    found_relative = module.worktree_own_git_directory_find_even_with_its_dot_git_file_gone(
        checkout, relative)
    check("a registration whose gitdir is relative, as --relative-paths writes it, is found",
          found_relative == relative_registration, f"{found_relative} {relative_registration}")

    undecodable = Path(git(checkout, "rev-parse", "--path-format=absolute",
                           "--git-common-dir").strip()) / "worktrees" / "aa-undecodable-gitdir"
    undecodable.mkdir()
    (undecodable / "gitdir").write_bytes(b"/tmp/not-utf-8-\xff/.git\n")
    try:
        found_past_undecodable = module.worktree_own_git_directory_find_even_with_its_dot_git_file_gone(
            checkout, sought)
    finally:
        shutil.rmtree(undecodable)
    check("a registration whose gitdir is not valid UTF-8 is read, and the search goes on",
          found_past_undecodable is not None
          and (found_past_undecodable / "gitdir").read_text(encoding="utf-8").strip()
          == str((sought / ".git").resolve()), str(found_past_undecodable))

    held, _ = stopped_partway("stopped-partway-registration-held-wt")
    held_registration = module.worktree_own_git_directory_find_even_with_its_dot_git_file_gone(
        checkout, held)
    (held_registration / "logs").mkdir(exist_ok=True)
    (held_registration / "logs" / "HEAD").write_text("x\n", encoding="utf-8")
    (held_registration / "logs").chmod(0o500)
    try:
        held_run = run_clean(checkout, "--remove")
    finally:
        (held_registration / "logs").chmod(0o755)
    check("a finish that cannot delete all of the registration keeps its gitdir and marker",
          held_run.returncode == 1 and (held_registration / "gitdir").exists()
          and (held_registration / module.REMOVAL_STARTED_MARKER_FILE_NAME).exists(),
          held_run.stdout + held_run.stderr)
    held_log = scratch / "held-removals-log.txt"
    held_environment = dict(os.environ)
    held_environment[REMOVALS_LOG_OVERRIDE_VARIABLE] = str(held_log)
    held_again = subprocess.run(
        [sys.executable, str(CLEAN_SCRIPT), "--repo", str(checkout), "--remove"],
        capture_output=True, text=True, check=False, env=held_environment)
    held_logged = held_log.read_text(encoding="utf-8") if held_log.is_file() else ""
    check("the next --remove then finishes it, logging the files deleted with it as unknown",
          held_again.returncode == 0 and not held_registration.exists() and not registered(held)
          and f"path={held}\t" in held_logged and "discarded-files=unknown" in held_logged,
          held_again.stdout + held_again.stderr + held_logged)

    unwritable = managed / "removal-file-unwritable-wt"
    git(checkout, "worktree", "add", "-b", "removal-file-unwritable-wt-branch", str(unwritable),
        "origin/main")
    give_stopped_owner(unwritable)
    registration = Path(git(unwritable, "rev-parse", "--absolute-git-dir").strip())
    registration.chmod(0o500)
    try:
        refused = run_clean(checkout, "--remove")
    finally:
        registration.chmod(0o755)
    check("a removal whose removal-started file cannot be written is not begun, and fails",
          refused.returncode == 1 and (unwritable / ".git").exists()
          and "removal-file-unwritable-wt: removal FAILED, worktree kept" in refused.stdout,
          refused.stdout + refused.stderr)

# --- The machine's task lists stay out of the suite's runs ---
with tempfile.TemporaryDirectory() as scratch:
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
    home = scratch / "home"
    machine_task_list = home / ".claude" / "tasks" / "nedschorus-someseat-tasks"
    machine_task_list.mkdir(parents=True)
    (machine_task_list / "1.json").write_text(json.dumps({
        "id": "1", "subject": "Restored branch restored-1-abc: open its pull request or delete it",
        "status": "pending",
        "description": "Restore commit: 1234567890abcdef1234567890abcdef12345678\n"}),
        encoding="utf-8")
    reported = run_clean_with_claude_home(checkout, home)
    check("an open restored-branch task in HOME's task lists is not judged while the override "
          "names the suite's own task lists",
          reported.returncode == 0 and "FAILED" not in reported.stdout
          and "restored-1-abc" not in reported.stdout,
          reported.stdout + reported.stderr)

check("no run of the suite shipped into the store every run defaults to",
      not any(Path(_ship_store_for_every_run).iterdir()),
      str(list(Path(_ship_store_for_every_run).rglob("*"))))

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
