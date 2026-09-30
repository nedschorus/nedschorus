#!/usr/bin/env python3
"""Run every test suite in a checkout, and report each one by its exit code.

Usage:
  scripts/run-all-test-suites.py [--checkout DIR] [--python INTERPRETER]
                                 [-j N] [--log-dir DIR] [--lock-file PATH]
                                 [--only-suites-whose-recorded-inputs-changed-since COMMIT]
                                 [--recorded-inputs-directory DIR]

  --checkout    the top directory of the checkout to test; default, the
                checkout this file is in
  --python      the interpreter that runs each suite file; default, the one
                running this program
  -j            how many suites run at once; default 1
  --log-dir     where each suite's output and the report are written;
                default, a new directory under the system temp directory
  --lock-file   the lock that keeps two runs on one machine apart; default
                ~/.claude/.run-all-test-suites.lock
  --only-suites-whose-recorded-inputs-changed-since COMMIT
                run only the suites whose recorded inputs differ between
                COMMIT and the checkout's files; see RECORDED INPUTS below.
                Without it every suite runs.
  --recorded-inputs-directory
                where each suite's recorded inputs are kept; default
                ~/.cache/nedschorus-test-suite-recorded-inputs

WHY THIS EXISTS (user-ruled 2026-09-21, walk "redesigning how pull requests
are processed", items 3 and 6). Until this program, every full run of the
project's suites was a shell loop kept in the merge-lane seat's gitignored
walk-ledgers/, untested and on one machine only. Its suite list was four
fixed globs, and when two systems moved into new directories the loop kept
reporting green over 52 of the 66 suites, because nothing it ran could see
the suites it no longer found. This program carries that loop's behaviour
into scripts/, with its test, and fixes the ways it was measured to go
wrong. The design-to-main machine's test-suite-executing state needs the
same thing, so this outlives the merge lane.

WHAT IT RUNS. Every file git lists matching `*-test.py`
(`git ls-files -- '*-test.py'`, whose `*` crosses directory boundaries), so
a suite in a directory nobody has told this program about is still run.
Measured 2026-09-21: that list and the four globs found the same 65 files,
and git's list leaves out the fixture design-to-main-test-fixture.py by
itself. A file git does not track is not run: commit or add a new suite
before expecting it here. The checkout must be named by its top directory,
because `git ls-files` run from a subdirectory lists only that subdirectory,
which is the 52-of-66 failure in another form; any other directory is
refused.

HOW EACH SUITE IS JUDGED. By its exit code, and nothing else: 0 is PASS,
anything else is FAIL, and a suite killed by a signal is FAIL naming the
signal. The suites print at least four different success wordings, so no
text can be trusted to mean pass or fail. Each suite runs as
`<interpreter> -u <path>` from the checkout's top directory, stdin closed,
stdout and stderr together into its own log file. A suite that starts
`python3` itself gets whatever PATH finds, not --python.

THE ENVIRONMENT EACH SUITE IS LAUNCHED WITH is this program's own, less the
variables that redirect where git reads and writes. They are stripped
because 21 suites on main build a scratch repository with `git init` and
none of them checks that it worked: the pattern checks `commit`'s return
code, not `init`'s. With GIT_DIR set, `git -C <scratch> init` re-initialises
the repository GIT_DIR names and exits 0, no repository is created at
<scratch>, and every later `git -C <scratch> ...` call lands in that other
repository while the suite prints PASS. On 2026-09-22 this put 14 commits by
a test identity onto a live seat's branch, cut that branch's tree from 293
files to 2, and overwrote the `user.name` and `user.email` shared by every
worktree of that clone. Filed as nedschorus#639, whose "Next action" item 1
is this change. scripts/find-deleted-path-across-backups-test.py:793 already
did `env.pop("GIT_DIR", None)` for itself; this generalises it to every
suite, and needs nothing of the suites' authors.

STRIPPED, each measured on ned-box with git 2.53.0 on 2026-09-22 by running
the suites' own init/config/add/commit pattern against a throwaway victim
repository. Each writes into the victim, every command exiting 0:

  GIT_DIR                 the victim gains the commit, its tracked set is
                          replaced, and its `user.name` is overwritten; no
                          repository exists at <scratch> afterwards
  GIT_WORK_TREE           alone it makes `git -C <scratch> init` exit 128,
                          but this program's cwd is the checkout's top
                          directory, and there a bare `git add -A` stages
                          the named tree into the CHECKOUT's index and
                          stages its own files as deleted, exit 0 throughout
  GIT_INDEX_FILE          the victim's index is replaced by the scratch
                          repository's tree, so the victim's tracked set
                          changes with nothing said
  GIT_OBJECT_DIRECTORY    the scratch repository's objects are written into
                          the victim, and the scratch repository cannot read
                          its own commit back once the variable is gone
  GIT_COMMON_DIR          the victim's `user.name` is overwritten and its
                          object store written into — the config half of the
                          2026-09-22 damage on its own
  GIT_ALTERNATE_OBJECT_DIRECTORIES
                          nothing is written, but the scratch repository
                          resolves objects that live in the other repository
                          and stops resolving them once the variable is
                          gone, so a suite can assert over a repository it
                          does not hold

NOT STRIPPED, and why, measured the same day the same way:

  GIT_NAMESPACE           contained. Refs still land at refs/heads/<branch>
                          on disk, HEAD resolves with the variable gone, and
                          `git branch --list` answers with it still set. It
                          renames refs inside one repository; it does not
                          reach another one.
  GIT_CEILING_DIRECTORIES stripping it would widen, not narrow, where git
                          looks. It bounds the upward walk that discovers a
                          repository: measured, a `git -C <scratch>` under
                          an unrelated outer repository exits 128 with the
                          ceiling set and finds that outer repository with it
                          gone. Removing it is the wrong direction.

Everything else in the environment is passed through unchanged, so a suite
that reads a variable of its own still gets it.

THIS PROGRAM'S OWN git calls (`rev-parse`, `ls-files`, `status`) are run
with the same environment (user-ruled 2026-09-28, walk
merge-lane-2-meta-walk-open-items-2026-09-23, item 11). Measured
2026-09-22: with GIT_DIR set, `git -C <top> ls-files` listed the other
repository's files and exited 0, so the suite list itself was wrong while
`rev-parse --show-toplevel` still answered <top>.

WHAT THIS DOES NOT COVER, stated because it is the case that caused the
2026-09-22 damage: a suite a person or an agent runs DIRECTLY is not
launched by this program and is not protected by this. The durable answer is
nedschorus#639's "Next action" item 2 — a scratch repository that asserts
itself after `git init` — which is an open design question across 21 files
and is not this change.

SKIPPED CASES are reported from text, because no exit code carries them: a
suite that skips a case still exits 0. Measured 2026-09-21: no suite uses
unittest's skip machinery, and the four that can skip
(scripts/resupervise-seat-test.py, scripts/recover-crashed-seats-test.py,
scripts/clean-worktrees-test.py, nc-systems/main-gatekeeper/tests/
main-gatekeeper-test.py) print a line opening `SKIP` followed by a space.
Every such line in a suite's output is counted and printed. resupervise-seat
prints its skips and then "all cases passed", which is how a run that
dropped its end-to-end cases used to read as a full pass. A skip never
changes a verdict; it is reported beside it.

ONE RUN AT A TIME PER MACHINE. Measured 2026-09-21: two overlapping runs of
scripts/resupervise-seat-test.py both exit 0 and both print "all cases
passed" while silently dropping cases to SKIP, because the suites share
machine state. So a run takes an exclusive lock on --lock-file, and a
second run on the same machine exits 3 without running anything. The lock
file names its holder (process id, checkout, start time), and the refusal
prints it.

CONCURRENCY. -j N runs N suites at once. Measured on ned-box 2026-09-21
over the 65 suites: serial 479 s, -j4 247 s, -j8 235 s. -j8 buys little
because nc-systems/cold-read/tests/cold-read-grid-test.py alone takes 233 s. The default is 1,
which is what the walk-ledgers loop did; -j4 is the measured choice.

NO PER-SUITE TIMEOUT. No suite has been seen to hang, so none is imposed.
A hung suite hangs the run.

OUTPUT. A first line naming the checkout, its commit, whether tracked files
differ from that commit, the suite count, the interpreter's own --version
answer and path, -j, and the log directory. Then one line per suite as it
finishes: `PASS <path> (<seconds>s)` or `FAIL <path> exit <code>
(<seconds>s)`, with `, <n> skipped` when it printed SKIP lines. Then the
failed suites again, each with its log, and every SKIP line, each with its
suite, so the end of the output holds everything needed. The last line
opens `SUMMARY:` and carries the counts. The whole report is also written to
report.txt in the log directory, so a run in the background needs no pipe to
keep it.

RECORDED INPUTS (user-ruled 2026-09-30, walk
open-questions-concerns-and-recommendations-2026-09-30, item 5, "y both").
A suite is rerun only when a file it reads has changed: test result caching,
keyed on inputs recorded while the suite actually ran, the way pytest-testmon
keys it. merge-lane-2 counted, over 75 code pull requests from 2026-09-24 to
2026-09-30, what its repeated full runs caught: no defect that the touched
suites had missed, and two failures caused by directories a Codex run left
in /tmp. So a full run of every suite is kept for once a day per machine,
and a pull request's head, and main after a merge, run the suites whose
inputs changed.

Every run records, for each suite it runs, the tracked files of the checkout
that the suite and every process it starts read. Searching the test files
for a changed program's name was measured to be the wrong tool: 57 of the
79 suites on main load the program they test by file path, not by import,
and 68 start processes, so neither an import graph nor a name finds what a
suite depends on. Two recorders, whose findings are added together:

  a Python audit hook, on both machines. The run puts a directory holding a
  sitecustomize.py first on each suite's PYTHONPATH, so every Python process
  the suite starts, children included, installs `sys.addaudithook` before
  its first line runs. It writes down every file opened inside the checkout
  (`open` covers open(), io.open, os.open and the loader's io.open_code),
  the script a process runs (`cpython.run_file`), each path passed to a
  process it starts (`subprocess.Popen`, `os.exec`, `os.posix_spawn`), each
  directory listed by the suite's own code (`os.listdir`, `os.scandir`; the
  import system's listings are left out, because every import lists the
  suite's own directory), and each git command run on the checkout itself —
  where a clone counts by its source and an init by the directory it names,
  since both are run from the checkout on repositories that are not it.
  Both machines already run a sitecustomize.py of their own (Homebrew's on
  the Mac sets sys.executable; Debian's on ned-box), so the recorder runs
  the one it shadows after installing itself. A process started with -I,
  -E or -S, or with an environment that drops PYTHONPATH, is not recorded.

  strace, on Linux, when it is installed and this program is not itself
  being traced: `strace -f -ff --seccomp-bpf -z -y -e trace=%file` around
  each suite, which sees every path any process opens, stats or executes,
  git and shells included. --seccomp-bpf stops a traced process only at the
  calls traced, and -z writes only calls that succeeded; the trace is
  deleted once read, because the heaviest suites write hundreds of
  megabytes. Inside another strace (a full run that runs this program's own
  test) a second strace cannot attach, so the audit hook works alone there.

A recording keeps, per suite: each file read, with its git blob hash; the
directories it listed; the git commands it ran on the checkout; and which
recorders made it. A `.pyc` read is recorded as the source file beside its
`__pycache__`, because an import that finds a valid cache never opens the
source. Recordings live outside every checkout, under
--recorded-inputs-directory and then the repository's root commit, one file
per suite: worktrees come and go and every one of a clone's worktrees, and
every clone, shares the same paths, so a recording made in one serves them
all. Every run replaces the recordings of the suites it ran; the daily full
run refreshes them all.

SELECTION, with --only-suites-whose-recorded-inputs-changed-since COMMIT.
The files that differ are `git diff --no-renames COMMIT` against the
checkout's files, plus untracked files git does not ignore, as added. Every
suite runs when one of them is this program (it holds the recorder), under
.claude/hooks/, or .claude/settings.json. Otherwise a suite runs when: it
has no recording on this machine, or one made by an older version of this
program; the suite file itself differs; a file it read differs; a file was
added to or deleted from a directory it listed; a file was added or deleted
and it ran git on the checkout; or, where strace did not record it, it ran a
git command on the checkout that reads file contents (anything but the
listing commands in GIT_COMMANDS_THAT_ONLY_LIST), and any file differs. Each
suite gets a line saying SELECTED or NOT SELECTED and why, before any runs.

WHAT IT COSTS AND WHAT IT CHOOSES, measured 2026-09-30 at cd9fb859, full
runs at -j 4. The Mac, the audit hook alone: 284 s against 278 s without
recording. ned-box, hook and strace: 296 s against 277 s, the suites' own
seconds summed 838 against 550; strace without --seccomp-bpf and -z took
511 s and wrote 2.7 GB of traces, and recorded exactly the same files. strace
saw tracked files the hook did not in 8 of the 79 suites (433 files, 420 of
them one suite's `git status` over the whole checkout); the hook saw none
that strace missed. Over the diffs of three merged pull requests the
recordings chose 5, 5 and 4 of 79 suites on both machines, where a search
of the test files for the changed programs' names chose 8, 2 and 3 — and
missed three suites that read the changed program, while choosing suites
that only name it.

WHAT A RECORDING CANNOT SEE: a file a suite only checks exists, on the Mac,
because Python raises no audit event for a stat; what a shell script it runs
sources, on the Mac; anything outside the checkout (a tool upgrade, leftover
machine state). The daily full run covers all three.

EXIT. 0 when every suite exited 0; 1 when any suite failed; 2 when the run
could not start (not a checkout's top directory, no suites listed, git or
the interpreter unusable, a COMMIT git cannot resolve); 3 when another run
holds the lock.
"""

import argparse
import codecs
import concurrent.futures
import datetime
import fcntl
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

PROGRAM = "run-all-test-suites"

TEST_SUITE_PATHSPEC = "*-test.py"
SKIPPED_CASE_LINE = re.compile(r"^SKIP\s")

# Stripped from the environment each suite is launched with; the docstring
# says what each one was measured to do, and why GIT_NAMESPACE and
# GIT_CEILING_DIRECTORIES are deliberately not here.
GIT_REDIRECTING_ENVIRONMENT_VARIABLES = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
)

DEFAULT_LOCK_FILE = Path.home() / ".claude" / ".run-all-test-suites.lock"
REPORT_FILE_NAME = "report.txt"

# Recorded inputs; the docstring's RECORDED INPUTS and SELECTION say how
# each piece is used.
DEFAULT_RECORDED_INPUTS_DIRECTORY = (
    Path.home() / ".cache" / "nedschorus-test-suite-recorded-inputs")
# Raised whenever what a recording holds changes, so an older recording is
# never read as a newer one: its suite runs, and is recorded afresh.
RECORDED_INPUTS_FORMAT_VERSION = 1
RECORDED_INPUTS_LOG_VARIABLE = "RUN_ALL_TEST_SUITES_RECORDED_INPUTS_LOG"
RECORDED_INPUTS_CHECKOUT_VARIABLE = "RUN_ALL_TEST_SUITES_RECORDED_INPUTS_CHECKOUT"
# Its presence marks a directory as holding this program's recorder, so a
# recorder chaining to the sitecustomize.py it shadows skips every recorder
# directory — a run inside a run has two on its PYTHONPATH.
PYTHON_INPUT_RECORDER_MARKER_FILE_NAME = "run-all-test-suites-python-input-recorder"
PYTHON_INPUT_RECORDER_METHOD = "python-audit-hook"
STRACE_INPUT_RECORDER_METHOD = "strace"
# A change to any of these reaches every suite: this program holds the
# recorder and launches each suite, and the hooks and settings shape every
# session a suite may start.
EVERY_SUITE_RUNS_WHEN_THESE_CHANGE = (
    "scripts/run-all-test-suites.py", ".claude/hooks/", ".claude/settings.json")
# Git commands that read the checkout's list of files or its history, never
# the contents of its working files; any other git command run on the
# checkout is taken to read contents the audit hook cannot see.
GIT_COMMANDS_THAT_ONLY_LIST = frozenset((
    "ls-files", "ls-tree", "rev-parse", "rev-list", "log", "branch", "config",
    "remote", "worktree", "for-each-ref", "symbolic-ref", "merge-base",
    "describe", "show-ref", "check-ignore", "var", "version", "fetch", "status", "init"))
PYCACHE_FILE = re.compile(
    r"^(?P<directory>(?:.*/)?)__pycache__/(?P<stem>[^/]+?)\.[^/.]+(?:\.opt-\d)?\.pyc$")

# The recorder each suite's Python processes load at startup. Kept here, not
# in a file of its own, so a change to it is a change to this program, which
# runs every suite.
PYTHON_INPUT_RECORDER_SOURCE = r'''
import os as _os
import sys as _sys


def _run_all_test_suites_install_input_recorder():
    if getattr(_sys, "_run_all_test_suites_input_recorder_installed", False):
        return
    log_path = _os.environ.get("RUN_ALL_TEST_SUITES_RECORDED_INPUTS_LOG")
    checkout = _os.environ.get("RUN_ALL_TEST_SUITES_RECORDED_INPUTS_CHECKOUT")
    if not log_path or not checkout:
        return
    import _thread
    checkout = _os.path.realpath(checkout)
    inside_prefix = checkout + _os.sep
    try:
        log = open(log_path, "a", buffering=1, encoding="utf-8", errors="surrogateescape")
    except OSError:
        return
    written = set()
    lock = _thread.allocate_lock()
    _sys._run_all_test_suites_input_recorder_installed = True

    def write(kind, value):
        if (kind, value) in written:
            return
        with lock:
            if (kind, value) in written:
                return
            written.add((kind, value))
            log.write(kind + "\t" + value.replace("\n", " ") + "\n")

    def absolute(path, working_directory=None):
        if path is None or isinstance(path, int):
            return None
        try:
            path = _os.fsdecode(_os.fspath(path))
        except TypeError:
            return None
        if not _os.path.isabs(path):
            path = _os.path.join(working_directory or _os.getcwd(), path)
        return _os.path.normpath(path)

    def inside(path):
        return path is not None and (path == checkout or path.startswith(inside_prefix))

    def started(program, arguments, working_directory):
        if isinstance(arguments, (str, bytes, _os.PathLike)):
            arguments = [arguments]
        arguments = list(arguments or [])
        for argument in ([program] if program is not None else []) + arguments:
            path = absolute(argument, working_directory)
            if inside(path) and _os.path.isfile(path):
                write("read", path)
        if not arguments or _os.path.basename(_os.fsdecode(arguments[0])) != "git":
            return
        target = working_directory or _os.getcwd()
        rest = [_os.fsdecode(argument) for argument in arguments[1:]]
        index = 0
        while index < len(rest) and rest[index].startswith("-"):
            if rest[index] == "-C" and index + 1 < len(rest):
                target = absolute(rest[index + 1], target)
                index += 2
            elif rest[index] in ("-c", "--git-dir", "--work-tree", "--namespace") \
                    and index + 1 < len(rest):
                index += 2
            else:
                index += 1
        if index >= len(rest):
            return
        command, operands = rest[index], [a for a in rest[index + 1:] if not a.startswith("-")]
        if command == "clone":
            # A clone reads its source, not the directory it is run from.
            sources = [absolute(operand[len("file://"):] if operand.startswith("file://")
                                else operand, target) for operand in operands[:1]]
            if any(inside(_os.path.realpath(source)) for source in sources if source):
                write("git", command)
            return
        if command == "init" and operands:
            target = absolute(operands[0], target)
        if inside(_os.path.realpath(target or "")):
            write("git", command)

    def hook(event, arguments):
        try:
            if event == "open" or event == "cpython.run_file":
                path = absolute(arguments[0])
                if inside(path):
                    write("read", path)
            elif event in ("os.listdir", "os.scandir"):
                caller = _sys._getframe(1).f_code.co_filename
                if "importlib" in caller:
                    return
                path = absolute(arguments[0] if arguments and arguments[0] is not None else ".")
                if inside(path):
                    write("list", path)
            elif event == "subprocess.Popen":
                started(arguments[0], arguments[1], arguments[2])
            elif event in ("os.exec", "os.posix_spawn"):
                started(None, arguments[1], None)
        except Exception:
            pass

    _sys.addaudithook(hook)


_run_all_test_suites_install_input_recorder()


def _run_all_test_suites_run_the_shadowed_sitecustomize():
    import importlib.machinery
    import importlib.util
    marker = "run-all-test-suites-python-input-recorder"
    search = [entry for entry in _sys.path
              if not _os.path.exists(_os.path.join(entry or _os.getcwd(), marker))]
    spec = importlib.machinery.PathFinder.find_spec("sitecustomize", search)
    if spec is not None and spec.loader is not None:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)


_run_all_test_suites_run_the_shadowed_sitecustomize()
'''

# One line of `strace -y` output: the call, its arguments, and its result,
# with the path of a returned file descriptor when -y knows it.
STRACE_LINE = re.compile(
    r"^(?P<call>[a-z_0-9]+)\((?P<arguments>.*)\)\s+=\s+(?P<result>-?\d+|\?)"
    r"(?:<(?P<result_path>[^>]*)>)?")
STRACE_DIRECTORY_ARGUMENT = re.compile(r"^(?:AT_FDCWD|\d+)<(?P<directory>[^>]*)>,\s*")
STRACE_QUOTED_STRING = re.compile(r'"((?:[^"\\]|\\.)*)"')

EXIT_ALL_PASSED = 0
EXIT_SOME_FAILED = 1
EXIT_COULD_NOT_RUN = 2
EXIT_LOCKED = 3


class CouldNotRun(Exception):
    """The run cannot start; the message is printed as the refusal."""


def git(checkout, *arguments):
    return subprocess.run(["git", "-C", str(checkout), *arguments],
                          env=environment_without_git_redirecting_variables(),
                          capture_output=True, text=True, check=False)


def checkout_top_directory(given):
    """The checkout's top directory, when `given` is it; otherwise a refusal."""
    answer = git(given, "rev-parse", "--show-toplevel")
    if answer.returncode != 0:
        raise CouldNotRun(
            f"{PROGRAM}: not run — {given} is not inside a git checkout.\n"
            f"Pass --checkout the top directory of a checkout.")
    top = Path(answer.stdout.strip()).resolve()
    if top != Path(given).resolve():
        raise CouldNotRun(
            f"{PROGRAM}: not run — {given} is not the top directory of its checkout.\n"
            f"Pass --checkout {top}")
    return top


def suites_listed_by_git(top):
    listed = git(top, "ls-files", "-z", "--", TEST_SUITE_PATHSPEC)
    if listed.returncode != 0:
        raise CouldNotRun(
            f"{PROGRAM}: not run — git ls-files failed in {top}: "
            f"{listed.stderr.strip()}\n"
            f"Fix what git reports, then run this again.")
    suites = [path for path in listed.stdout.split("\0") if path]
    if not suites:
        raise CouldNotRun(
            f"{PROGRAM}: not run — git lists no {TEST_SUITE_PATHSPEC} file in {top}.\n"
            f"Pass --checkout a checkout that has its suites committed or added.")
    return suites


def interpreter_and_version(given):
    found = shutil.which(given)
    if found is None:
        raise CouldNotRun(
            f"{PROGRAM}: not run — no interpreter found for --python {given}.\n"
            f"Pass --python a path or command name that exists.")
    try:
        answer = subprocess.run([found, "--version"], capture_output=True,
                                text=True, stdin=subprocess.DEVNULL, check=False)
    except OSError as error:
        raise CouldNotRun(
            f"{PROGRAM}: not run — {found} could not be started: {error}\n"
            f"Pass --python an interpreter that runs.") from error
    version = (answer.stdout.strip() or answer.stderr.strip()).splitlines()
    if answer.returncode != 0 or not version:
        raise CouldNotRun(
            f"{PROGRAM}: not run — {found} --version exited {answer.returncode}.\n"
            f"Pass --python an interpreter that runs.")
    return found, version[0]


def commit_and_state(top):
    head = git(top, "rev-parse", "HEAD")
    commit = head.stdout.strip() if head.returncode == 0 else "no commit"
    changed = git(top, "status", "--porcelain", "--untracked-files=no")
    if changed.returncode != 0:
        state = "tracked-file state unknown"
    elif changed.stdout.strip():
        state = "tracked files differ from that commit"
    else:
        state = "tracked files match that commit"
    return commit, state


def take_machine_lock(lock_file, top):
    """(the open, locked handle, None) when this run takes the lock;
    (None, the holder's description of itself) when another run holds it.

    Opened for append, so a run that loses the race never truncates the
    holder's description of itself before reading it.
    """
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_file, "a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.seek(0)
        holder = handle.read().strip() or "a run that has not described itself yet"
        handle.close()
        return None, holder
    handle.seek(0)
    handle.truncate()
    started = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    handle.write(f"pid {os.getpid()}, checkout {top}, started {started}\n")
    handle.flush()
    return handle, None


def log_path_for(log_dir, suite):
    # The whole relative path, so two suites with one file name in
    # different directories cannot overwrite each other's log.
    return log_dir / (suite.replace("/", "__") + ".log")


def skipped_case_lines(log_file):
    try:
        text = log_file.read_text(errors="replace")
    except OSError:
        return []
    return [line for line in text.splitlines() if SKIPPED_CASE_LINE.match(line)]


def environment_without_git_redirecting_variables():
    """This program's environment, less the variables that send a suite's git
    commands into whatever repository the environment names. A fresh dict per
    call, because suites are launched from several threads at once."""
    environment = dict(os.environ)
    for variable in GIT_REDIRECTING_ENVIRONMENT_VARIABLES:
        environment.pop(variable, None)
    return environment


def being_traced():
    """True when a tracer is attached to this process, which a second strace
    could not attach beneath. Linux says so in /proc/self/status."""
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("TracerPid:"):
                return line.split()[1] != "0"
    except OSError:
        pass
    return False


def strace_usable():
    """strace's path when it can record here, else None: Linux, installed,
    this process not already traced, and a trial trace that succeeds."""
    if not sys.platform.startswith("linux") or being_traced():
        return None
    found = shutil.which("strace")
    if found is None:
        return None
    trial = subprocess.run([found, "-f", "-qq", "-e", "trace=none", "true"],
                           capture_output=True, stdin=subprocess.DEVNULL, check=False)
    return found if trial.returncode == 0 else None


def recording_paths_for(recording_dir, suite):
    """(the audit hook's log, the directory strace writes one file per process into)."""
    name = suite.replace("/", "__")
    return recording_dir / (name + ".hook"), recording_dir / (name + ".strace")


def install_python_input_recorder(log_dir):
    """The directory to put first on each suite's PYTHONPATH."""
    recorder_dir = log_dir / "python-input-recorder"
    recorder_dir.mkdir(parents=True, exist_ok=True)
    (recorder_dir / "sitecustomize.py").write_text(PYTHON_INPUT_RECORDER_SOURCE)
    (recorder_dir / PYTHON_INPUT_RECORDER_MARKER_FILE_NAME).write_text(
        "This directory holds scripts/run-all-test-suites.py's input recorder.\n")
    return recorder_dir


def run_one_suite(top, interpreter, suite, log_dir, recorder=None):
    """Runs one suite; with `recorder` (the recorder directory, the recording
    directory, and strace's path or None) its inputs are recorded as it runs."""
    log_file = log_path_for(log_dir, suite)
    environment = environment_without_git_redirecting_variables()
    command = [interpreter, "-u", suite]
    if recorder is not None:
        recorder_dir, recording_dir, strace = recorder
        hook_log, strace_dir = recording_paths_for(recording_dir, suite)
        # A --log-dir used before holds the last run's logs, and the hook
        # appends: what an earlier run read must not be credited to this one.
        hook_log.unlink(missing_ok=True)
        shutil.rmtree(strace_dir, ignore_errors=True)
        environment["PYTHONPATH"] = os.pathsep.join(
            [str(recorder_dir)] + [entry for entry in
                                   environment.get("PYTHONPATH", "").split(os.pathsep) if entry])
        environment[RECORDED_INPUTS_LOG_VARIABLE] = str(hook_log)
        environment[RECORDED_INPUTS_CHECKOUT_VARIABLE] = str(top)
        if strace is not None:
            strace_dir.mkdir(parents=True, exist_ok=True)
            command = [strace, "-f", "-ff", "--seccomp-bpf", "-z", "-qq", "-y", "-s", "4096",
                       "-e", "trace=%file", "-e", "signal=none",
                       "-o", str(strace_dir / "trace"), *command]
    started = time.monotonic()
    with open(log_file, "wb") as log:
        completed = subprocess.run(command, cwd=str(top), env=environment,
                                   stdin=subprocess.DEVNULL, stdout=log,
                                   stderr=subprocess.STDOUT, check=False)
    return {
        "suite": suite,
        "exit": completed.returncode,
        "seconds": time.monotonic() - started,
        "log": log_file,
        "skips": skipped_case_lines(log_file),
    }


def unescaped_strace_string(text):
    return codecs.escape_decode(text.encode("utf-8"))[0].decode("utf-8", "surrogateescape")


def paths_strace_saw(strace_dir):
    """Every absolute path a traced process opened, statted or executed."""
    seen = set()
    for trace_file in sorted(strace_dir.glob("trace*")):
        try:
            text = trace_file.read_text(errors="surrogateescape")
        except OSError:
            continue
        for line in text.splitlines():
            parsed = STRACE_LINE.match(line)
            if parsed is None:
                continue
            if parsed["result_path"] and parsed["result"].isdigit():
                seen.add(parsed["result_path"])
                continue
            arguments = parsed["arguments"]
            directory = STRACE_DIRECTORY_ARGUMENT.match(arguments)
            quoted = STRACE_QUOTED_STRING.search(arguments)
            if quoted is None:
                continue
            path = unescaped_strace_string(quoted.group(1))
            if os.path.isabs(path):
                seen.add(path)
            elif directory is not None:
                seen.add(os.path.join(directory["directory"], path))
    return seen


def relative_inside(top, path):
    """`path` relative to the checkout's top directory, or None outside it."""
    try:
        return Path(os.path.realpath(path)).relative_to(top).as_posix()
    except ValueError:
        return None


def source_of_cached_bytecode(relative):
    """A `.pyc` in a `__pycache__` stands for the source beside the cache."""
    cached = PYCACHE_FILE.match(relative)
    if cached is None:
        return relative
    return f"{cached['directory']}{cached['stem']}.py"


def blob_hashes(top, paths):
    """Each path's git blob hash as the checkout has it now."""
    if not paths:
        return {}
    answer = subprocess.run(["git", "-C", str(top), "hash-object", "--stdin-paths"],
                            input="\n".join(paths) + "\n", capture_output=True, text=True,
                            env=environment_without_git_redirecting_variables(), check=False)
    hashes = answer.stdout.split()
    if answer.returncode != 0 or len(hashes) != len(paths):
        return {path: "unknown" for path in paths}
    return dict(zip(paths, hashes))


def recording_of(top, suite, result, recording_dir, tracked, commit, strace_used):
    """What `suite` read, listed and ran git on, from both recorders' logs."""
    hook_log, strace_dir = recording_paths_for(recording_dir, suite)
    reads, listed, git_commands = {suite}, set(), set()
    try:
        hook_lines = hook_log.read_text(errors="surrogateescape").splitlines()
    except OSError:
        hook_lines = []
    for line in hook_lines:
        kind, _, value = line.partition("\t")
        if kind == "git":
            git_commands.add(value)
            continue
        relative = relative_inside(top, value)
        if relative is None:
            continue
        if kind == "read":
            reads.add(source_of_cached_bytecode(relative))
        elif kind == "list" and not relative.startswith(".git"):
            listed.add("" if relative == "." else relative)
    if strace_used:
        for path in paths_strace_saw(strace_dir):
            relative = relative_inside(top, path)
            if relative is not None:
                reads.add(source_of_cached_bytecode(relative))
    reads = sorted(path for path in reads if path in tracked)
    return {
        "format": RECORDED_INPUTS_FORMAT_VERSION,
        "suite": suite,
        "recorded_at": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "commit": commit,
        "exit": result["exit"],
        "recorded_by": [PYTHON_INPUT_RECORDER_METHOD]
                       + ([STRACE_INPUT_RECORDER_METHOD] if strace_used else []),
        "reads": blob_hashes(top, reads),
        "lists": sorted(listed),
        "git_commands_on_the_checkout": sorted(git_commands),
    }


def recordings_directory_for(given, top):
    """One directory per repository, named by its root commit, so every clone
    and worktree of one repository shares its recordings."""
    roots = git(top, "rev-list", "--max-parents=0", "HEAD").stdout.split()
    return Path(given).expanduser() / (min(roots)[:16] if roots else "no-commit")


def recording_file_for(recordings_dir, suite):
    return recordings_dir / (suite.replace("/", "__") + ".json")


def save_recording(recordings_dir, recording):
    recordings_dir.mkdir(parents=True, exist_ok=True)
    target = recording_file_for(recordings_dir, recording["suite"])
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(recording, indent=1, sort_keys=True) + "\n")
    temporary.replace(target)


def load_recording(recordings_dir, suite):
    try:
        return json.loads(recording_file_for(recordings_dir, suite).read_text())
    except (OSError, ValueError):
        return None


def resolved_commit(top, given):
    answer = git(top, "rev-parse", "--verify", "--quiet", f"{given}^{{commit}}")
    if answer.returncode != 0 or not answer.stdout.strip():
        raise CouldNotRun(
            f"{PROGRAM}: not run — git cannot resolve {given} to a commit in {top}.\n"
            f"Pass --only-suites-whose-recorded-inputs-changed-since a commit this "
            f"checkout has, such as the output of `git merge-base HEAD origin/main`.")
    return answer.stdout.strip()


def files_that_differ_since(top, commit):
    """{path: 'A', 'M' or 'D'} for every file that differs between `commit`
    and the checkout's files, untracked files git does not ignore as 'A'."""
    differ = {}
    diff = git(top, "diff", "--no-renames", "--name-status", "-z", commit)
    if diff.returncode != 0:
        raise CouldNotRun(
            f"{PROGRAM}: not run — git diff {commit} failed in {top}: {diff.stderr.strip()}\n"
            f"Fix what git reports, then run this again.")
    fields = [field for field in diff.stdout.split("\0") if field]
    for status, path in zip(fields[0::2], fields[1::2]):
        differ[path] = "A" if status.startswith("A") else "D" if status.startswith("D") else "M"
    untracked = git(top, "ls-files", "--others", "--exclude-standard", "-z")
    for path in untracked.stdout.split("\0"):
        if path:
            differ.setdefault(path, "A")
    return differ


def listed_directory_holds(directory, path):
    parent = os.path.dirname(path)
    return parent == directory


def selection_reason(suite, recording, differ, commit):
    """(selected, why) for one suite, given the files that differ."""
    short = commit[:12]
    if recording is None:
        return True, "no recording of its inputs on this machine yet"
    if recording.get("format") != RECORDED_INPUTS_FORMAT_VERSION:
        return True, "its recording was made by an older version of this program"
    if suite in differ:
        return True, "the suite itself differs"
    changed_reads = [path for path in recording.get("reads", {}) if path in differ]
    if changed_reads:
        more = f" and {len(changed_reads) - 1} more" if len(changed_reads) > 1 else ""
        return True, f"it reads {changed_reads[0]}, which differs{more}"
    added_or_deleted = sorted(path for path, status in differ.items() if status in "AD")
    for directory in recording.get("lists", []):
        for path in added_or_deleted:
            if listed_directory_holds(directory, path):
                verb = "added" if differ[path] == "A" else "deleted"
                return True, f"it lists {directory or '.'}/, where {path} was {verb}"
    git_commands = recording.get("git_commands_on_the_checkout", [])
    if git_commands and added_or_deleted:
        path = added_or_deleted[0]
        verb = "added" if differ[path] == "A" else "deleted"
        return True, (f"it runs git {', '.join(git_commands)} on the checkout, "
                      f"and {path} was {verb}")
    if STRACE_INPUT_RECORDER_METHOD not in recording.get("recorded_by", []):
        reading = sorted(set(git_commands) - GIT_COMMANDS_THAT_ONLY_LIST)
        if reading and differ:
            return True, (f"it runs git {', '.join(reading)} on the checkout, which reads "
                          f"files no recorder here saw, and {sorted(differ)[0]} differs")
    return False, (f"none of the {len(recording.get('reads', {}))} files it read "
                   f"differs since {short}")


def suites_selected_since(top, suites, recordings_dir, commit):
    """[(suite, selected, why)] for every suite, in order."""
    differ = files_that_differ_since(top, commit)
    everything = [path for path in sorted(differ)
                  if any(path == prefix or (prefix.endswith("/") and path.startswith(prefix))
                         for prefix in EVERY_SUITE_RUNS_WHEN_THESE_CHANGE)]
    if everything:
        return [(suite, True, f"{everything[0]} differs, and every suite runs under it")
                for suite in suites]
    return [(suite, *selection_reason(suite, load_recording(recordings_dir, suite),
                                      differ, commit))
            for suite in suites]


def describe_exit(code):
    if code >= 0:
        return f"exit {code}"
    try:
        return f"killed by {signal.Signals(-code).name}"
    except ValueError:
        return f"killed by signal {-code}"


def suite_line(result):
    detail = f"{result['seconds']:.1f}s"
    if result["skips"]:
        detail += f", {len(result['skips'])} skipped"
    if result["exit"] == 0:
        return f"PASS {result['suite']} ({detail})"
    return f"FAIL {result['suite']} {describe_exit(result['exit'])} ({detail})"


class Report:
    """Every line goes to stdout at once and to report.txt in the log directory."""

    def __init__(self, report_file):
        self.lock = threading.Lock()
        self.file = open(report_file, "w")

    def line(self, text):
        with self.lock:
            print(text, flush=True)
            self.file.write(text + "\n")
            self.file.flush()

    def close(self):
        self.file.close()


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        prog=PROGRAM, description="Run every *-test.py suite git lists in a checkout.")
    parser.add_argument("--checkout", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("-j", dest="jobs", type=int, default=1)
    parser.add_argument("--log-dir")
    parser.add_argument("--lock-file", default=str(DEFAULT_LOCK_FILE))
    parser.add_argument("--only-suites-whose-recorded-inputs-changed-since",
                        dest="changed_since", metavar="COMMIT")
    parser.add_argument("--recorded-inputs-directory",
                        default=str(DEFAULT_RECORDED_INPUTS_DIRECTORY))
    arguments = parser.parse_args(argv)
    if arguments.jobs < 1:
        parser.error("-j takes a whole number of at least 1")
    return arguments


def main(argv=None):
    arguments = parse_arguments(argv)
    try:
        top = checkout_top_directory(arguments.checkout)
        suites = suites_listed_by_git(top)
        interpreter, version = interpreter_and_version(arguments.python)
        changed_since = (resolved_commit(top, arguments.changed_since)
                         if arguments.changed_since else None)
    except CouldNotRun as refusal:
        print(refusal, file=sys.stderr)
        return EXIT_COULD_NOT_RUN

    lock_handle, holder = take_machine_lock(Path(arguments.lock_file), top)
    if lock_handle is None:
        print(f"{PROGRAM}: not run — another run holds {arguments.lock_file}: {holder}.\n"
              f"Run this again after that run has finished.", file=sys.stderr)
        return EXIT_LOCKED

    try:
        if arguments.log_dir:
            log_dir = Path(arguments.log_dir).resolve()
            log_dir.mkdir(parents=True, exist_ok=True)
        else:
            log_dir = Path(tempfile.mkdtemp(prefix=f"{PROGRAM}-"))
        commit, state = commit_and_state(top)
        recordings_dir = recordings_directory_for(arguments.recorded_inputs_directory, top)
        if changed_since is not None:
            try:
                selection = suites_selected_since(top, suites, recordings_dir, changed_since)
            except CouldNotRun as refusal:
                print(refusal, file=sys.stderr)
                return EXIT_COULD_NOT_RUN
        else:
            selection = [(suite, True, "every suite runs without "
                          "--only-suites-whose-recorded-inputs-changed-since")
                         for suite in suites]
        chosen = [suite for suite, selected, _ in selection if selected]
        strace = strace_usable()
        recording_dir = log_dir / "recorded-inputs"
        recording_dir.mkdir(parents=True, exist_ok=True)
        recorder = (install_python_input_recorder(log_dir), recording_dir, strace)
        tracked = set(path for path in git(top, "ls-files", "-z").stdout.split("\0") if path)
        report = Report(log_dir / REPORT_FILE_NAME)
        selected_note = (f"; {len(chosen)} selected by inputs changed since "
                         f"{changed_since[:12]}" if changed_since is not None else "")
        report.line(f"{PROGRAM}: {top} at {commit} ({state}); {len(suites)} suites "
                    f"listed by git{selected_note}; {version} ({interpreter}); "
                    f"-j {arguments.jobs}; logs in {log_dir}")
        report.line(f"inputs recorded by {PYTHON_INPUT_RECORDER_METHOD}"
                    + (f" and {STRACE_INPUT_RECORDER_METHOD} ({strace})" if strace else "")
                    + f", kept in {recordings_dir}")
        if changed_since is not None:
            for suite, selected, why in selection:
                report.line(f"{'SELECTED' if selected else 'NOT SELECTED'} {suite}: {why}")

        def run_and_record(suite):
            result = run_one_suite(top, interpreter, suite, log_dir, recorder)
            try:
                save_recording(recordings_dir, recording_of(
                    top, suite, result, recording_dir, tracked, commit, strace is not None))
            except OSError as error:
                report.line(f"inputs of {suite} not recorded: {error}; it runs again "
                            f"next time, with or without the option")
            # strace writes hundreds of megabytes for the heaviest suites;
            # once read into the recording, the trace is not kept.
            shutil.rmtree(recording_paths_for(recording_dir, suite)[1], ignore_errors=True)
            return result

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=arguments.jobs) as pool:
            running = [pool.submit(run_and_record, suite) for suite in chosen]
            for finished in concurrent.futures.as_completed(running):
                result = finished.result()
                results.append(result)
                report.line(suite_line(result))

        results.sort(key=lambda result: result["suite"])
        failed = [result for result in results if result["exit"] != 0]
        skipping = [result for result in results if result["skips"]]
        if failed:
            report.line("")
            report.line(f"{len(failed)} failed:")
            for result in failed:
                report.line(f"FAIL {result['suite']} {describe_exit(result['exit'])}"
                            f" — log {result['log']}")
        if skipping:
            report.line("")
            report.line("skipped cases:")
            for result in skipping:
                for skip in result["skips"]:
                    report.line(f"{result['suite']}: {skip}")
        skip_count = sum(len(result["skips"]) for result in results)
        not_selected = (f"; {len(suites) - len(chosen)} suites not selected, their recorded "
                        f"inputs unchanged since {changed_since[:12]}"
                        if changed_since is not None else "")
        report.line(f"SUMMARY: {len(results) - len(failed)} passed, {len(failed)} failed, "
                    f"{len(results)} total; {skip_count} cases skipped in {len(skipping)} "
                    f"suites; {top.name} at {commit[:12]}; {version}{not_selected}")
        report.close()
        return EXIT_SOME_FAILED if failed else EXIT_ALL_PASSED
    finally:
        lock_handle.close()


if __name__ == "__main__":
    sys.exit(main())
