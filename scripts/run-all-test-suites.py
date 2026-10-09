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
  -j            how many suites run at once; default, the machine's core
                count, or the number of suites to run when that is fewer
  --log-dir     where each suite's output and the report are written;
                default, a new directory under the system temp directory,
                removed two days after its run ends. Two runs cannot share
                one --log-dir: the second exits 3
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

WHAT IT RUNS. Every file git lists matching `*-test.py` or `*-test.sh`
(`git ls-files -- '*-test.py' '*-test.sh'`, whose `*` crosses directory
boundaries), so a suite in a directory nobody has told this program about is
still run.
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
`<interpreter> -u <path>`, or `sh <path>` for a `*-test.sh` suite, from the
checkout's top directory, stdin closed,
stdout and stderr together into its own log file. A suite that starts
`python3` itself gets whatever PATH finds, not --python.

EACH SUITE RUNS IN A SIGNAL SANDBOX on Linux: `bwrap --dev-bind / /
--unshare-pid --die-with-parent --proc /proc`, so the suite and everything it
starts sit in a PID namespace of their own. The file system and network are
unchanged, and the suite runs as the same user, so a signal a suite sends can
reach only the processes it started, never the agent-seats that run as the
same account. bwrap also gives the suite a user namespace of its own, in which
every file owned by another user, root included, shows as owned by nobody: a
check of a file's owner, such as ssh's check of its config files, fails there. bwrap is
tried once before any suite runs; when it is on PATH but cannot start, the
run stops with exit 2 rather than run the suites unconfined. Without bwrap
the suites run unconfined and the report says so.

On macOS, which has no PID namespaces, each suite runs under
`/usr/bin/sandbox-exec` with a profile that refuses any signal to a process
outside the suite's own sandbox, broadcasts to -1 and to a process group
included, while the suite can still signal the processes it started. A
process the suite leaves running is not stopped when the suite ends, as it is
in a PID namespace. Before any suite runs, a trial process inside the sandbox
signals this program; the run stops with exit 2 when sandbox-exec is missing,
cannot start, or lets that signal through. A run that macOS already
confines in a sandbox, such as one inside Claude Code's sandbox, starts no
sandbox-exec: the sandbox it inherited already refuses signals to processes
outside it, and `ps` cannot run inside a sandbox-exec nested in another
sandbox. A run started
inside the sandbox, such as one a suite of this program starts, does not
start another: bwrap cannot start inside bwrap, and its suites are already
confined. The suites listed in SUITES_RUN_OUTSIDE_THE_SIGNAL_SANDBOX cannot
work inside it and run unconfined, each named in the report with the reason.
A suite bwrap reports as exiting 128+N is reported as killed by signal N;
sandbox-exec replaces itself with the suite, so a suite's exit passes through.

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
launched by this program and is not protected by this. Such a suite protects
itself: a suite or fixture that runs `git init` first takes the variables
listed above out of its own process, through
scripts/git-redirecting-environment-removal-test-fixture.py, which reads
GIT_REDIRECTING_ENVIRONMENT_VARIABLES from this file, and
scripts/test-suites-run-directly-ignore-git-redirecting-environment-test.py
checks that each one does. That is nedschorus#639's "Next action" item 2.

SKIPPED CASES are reported from text, because no exit code carries them: a
suite that skips a case still exits 0. Measured 2026-09-21: no suite uses
unittest's skip machinery, and the three that can skip
(scripts/resupervise-seat-test.py, scripts/recover-crashed-seats-test.py,
scripts/clean-worktrees-test.py) print a line opening `SKIP` followed by
a space.
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

RUN RECORDS, on Linux. Each run writes a record into the directory beside
its lock file (<lock file>.runs): its own process id and start time, its
log directory, and, for each suite, the process whose end ends the suite.
In the signal sandbox that process is the init of the suite's PID
namespace, which bwrap reports through --json-status-fd; when it ends, the
kernel ends every process in the namespace. A run started next removes what
an earlier run left (its strace traces, and its own temporary log
directory two days after the run ended) only when that run's process and
every suite process it recorded have ended. A suite of a killed run can
still be writing its traces, and a run that cleaned up after the lock's
last holder, as runs did before, could delete them while it wrote. A suite
run outside the sandbox is recorded by its own process, so a process it
started in a session of its own is not covered. The temporary log
directories runs made before records existed are removed once nothing in
them has changed for two days. macOS has no /proc to read start times
from, so there a run still cleans up after the lock's last holder.

CONCURRENCY. -j N runs N suites at once. The default is the machine's core
count (4 when Python cannot tell), or the number of suites to run when that
is fewer. Suites start longest first, by the seconds their recordings
kept, ties in the order git lists them; a suite with no recording, or whose
recorded run did not pass, starts before them all, since it may be long. A
run lasts at least as long as its longest suite, and a suite slows when the
machine is busy, so more jobs pay off only once no single suite dominates.
-j 1 still runs one suite at a time when a run must.

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
  since both are run from the checkout on repositories that are not it, and
  an option's value (`-b main`) is not taken for either. For each git call it
  writes every argument after the program name, unchanged, the absolute
  normalised starting directory before any -C, and GIT_DIR and GIT_WORK_TREE
  from the call's environment (the inherited environment when none is
  given). These facts are JSON, so an argument's newline cannot break the
  log's line format. The recorder does not classify the calls. Python raises no
  audit event for a stat, so the recorder also wraps os.path's exists,
  lexists, isfile, isdir and islink, which pathlib's exists, is_file and
  is_dir call, and writes down each path inside the checkout they check. An
  open that fails is written down too: the event comes before the open.
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
  megabytes. A run killed before it deletes them leaves the traces of the
  suites it was running; a later run removes them once nothing of the killed
  run still runs (see RUN RECORDS below). Inside another strace (a
  full run that runs this program's own test) a second strace cannot
  attach, so the audit hook works alone there.

A recording keeps, per suite: its exit code and seconds; each file read,
with its git blob hash; each path it opened or checked for, and whether the
path was there; each directory it listed, with the entries the directory
held; the git calls run from the checkout, with their arguments, starting
directory, GIT_DIR, GIT_WORK_TREE and what each call reads; the command
names of only the calls that read the checkout, with a fingerprint of the
checkout's list of files; and which recorders made it. A starting directory
inside the checkout is kept relative to its top directory, with '.' for the
top itself; one outside is kept absolute. A recording made in an older
format than this program writes selects its suite once, so the suite is
recorded afresh. The files are those git tracks
or would add, untracked and not ignored, as the run found them when it
started. A `.pyc` read is recorded as the source file beside its
`__pycache__`, because an import that finds a valid cache never opens the
source. Recordings live outside every checkout, under
--recorded-inputs-directory and then the repository's root commit, one file
per suite: worktrees come and go and every one of a clone's worktrees, and
every clone, shares the same paths, so a recording made in one serves them
all. Every run replaces the recordings of the suites it ran, a failed or
killed run's included, so the last recording always says how the suite's
last run ended; the daily full run refreshes them all. Each recording is
written to a temporary file of its own and renamed into place under a short
lock held per suite, so runs in two checkouts saving one suite at once never
mix their contents, and a reader sees one whole recording. A run reads each
recording once, when it starts, and both selection and starting order use
what it read. A recording that cannot be saved removes the earlier one,
unless another run saved a newer one since this run read it; that one
records its own run's inputs, so it is kept.

SELECTION, with --only-suites-whose-recorded-inputs-changed-since COMMIT.
Two explicit allowlists set aside git calls that read no file of the
checkout. Every call is checked against its full arguments:

  a call sees no file when its only global options are -C <dir> pairs, and
  its command is rev-parse followed by at least one argument, all from
  --show-toplevel, --git-dir, --absolute-git-dir, --git-common-dir,
  --is-inside-work-tree and --show-prefix; or its command is config followed
  by exactly one key, exactly --get <key>, or exactly --get-all <key>.
  A key does not start with '-', contains a '.', contains no '=' and no
  whitespace; user.* keys are included. The six rev-parse options say where
  the checkout and its git directory are, from the current directory and
  the repository's location alone. Config reads answer from configuration
  in the git directory or the user's home, never from a file of the
  checkout. Anything else on the call fails this allowlist, including
  rev-parse --verify <abbreviated hash>, whose answer depends on the object
  store, which every commit changes: a new object can make the abbreviation
  ambiguous.

  a call runs on another repository when its only global options are
  -C <dir>, --git-dir <path>, --git-dir=<path>, --work-tree <path> and
  --work-tree=<path>; it names a git directory by its last --git-dir value,
  or otherwise its recorded GIT_DIR; that directory resolves outside both
  the checkout's top directory and its common git directory; and either
  its last --work-tree value, or otherwise its recorded GIT_WORK_TREE,
  resolves outside the top directory, or its command reads no work tree:
  rev-parse, log, show, cat-file, for-each-ref, config, or worktree whose
  first argument is list. Relative paths resolve against the starting
  directory after applying every -C in order, then through realpath.
  The common git directory is git rev-parse --git-common-dir, resolved
  against the top directory when relative, then through realpath; when
  unknown, only the top directory counts as the checkout. A linked
  worktree's own git directory is outside its top directory but inside
  its common git directory, so still belongs to the checkout's repository.
  The listed commands read the other repository's objects, refs and
  configuration. Status, diff, add, checkout, ls-files and stash given
  --git-dir without a work tree use the current directory as their work
  tree, so still read the checkout.

Anything else stays git on the checkout and follows the rules below,
including calls with no parseable command, a clone whose source is inside
the checkout, and an init naming a directory inside it. A call set aside
does not trigger any of the three git reasons below; the recorded files,
paths and directory listings are still compared. When every recorded git
call is set aside and those comparisons pass, the NOT SELECTED line says
which calls see no file and which commands run on another repository.

The files that differ are `git diff --no-renames COMMIT` against the
checkout's files, plus untracked files git does not ignore, as added. Every
suite runs when one of them is this program (it holds the recorder), under
.claude/hooks/, or .claude/settings.json. Otherwise a suite runs when: it
has no recording on this machine, or one made by an older version of this
program; its recorded run did not exit 0, since a run that failed or was
killed recorded only what it read before it stopped; its recorded run
skipped cases, since the cases skipped recorded nothing, and a skip can be
a run disturbed by another; the suite file itself
differs; a file it read differs; a path it looked for was added or deleted;
an entry was added to or deleted from a directory it listed, a new
subdirectory's name included; a file was added or deleted and it ran git on
the checkout; or it ran a git command on the checkout that reads file
contents (anything but the listing commands in GIT_COMMANDS_THAT_ONLY_LIST),
and any file differs — strace or not, because git reads a committed file's
content from the object store, where no recorder sees a working file.

Then, because every clone and worktree on a machine shares the store, the
recording may have been made on another branch, where the suite read other
files. A suite also runs when its recording does not match the checkout: a
file it read has another blob hash, a path it looked for is there or absent
where it was not, a directory it listed holds other entries, or it ran git
on the checkout and the checkout's list of files has another fingerprint.
So a suite is NOT SELECTED only when everything its recording saw is the
same at COMMIT, in the recording, and in the checkout. Each suite gets a
line saying SELECTED or NOT SELECTED and why, before any runs.

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

Measured again 2026-10-01 under the selection above, recording with a full
run at each of those pull requests' merge base and selecting at its head,
the way a head based on main is selected: 6, 6 and 5 of 79 suites, the same
suites on both machines. The one added to each count on each machine is the
suite running `git status` or `git grep` on the checkout that the machine
did not already choose; both now run on any change. Full runs at -j 4: the
Mac 278 s, ned-box 305 s; a store of 79 recordings is about 500 KB.

WHAT A RECORDING CANNOT SEE: a path a program other than Python checks for
or fails to open, on either machine, because strace's -z drops failed calls
(a suite that runs git on the checkout is selected whenever any file is
added or deleted, so git's own lookups are covered); a path Python checks
with os.stat or os.access directly; a directory a program other than Python
lists (strace's view of a directory opened is left out, because the import
system opens every directory on the path); on the Mac, what a shell script
a suite runs reads or sources; an ignored file; anything outside the checkout (a
tool upgrade, leftover machine state). The daily full run covers all of
these.

EXIT. 0 when every suite exited 0; 1 when any suite failed; 2 when the run
could not start (not a checkout's top directory, no suites listed, git or
the interpreter unusable, a COMMIT git cannot resolve); 3 when another run
holds the lock.
"""

import argparse
import codecs
import concurrent.futures
import contextlib
import ctypes
import datetime
import fcntl
import functools
import hashlib
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
# Python audit hooks cannot see shell reads; without strace, a shell recording
# would miss inputs. Leave shell suites unrecorded so selection always runs them.
SHELL_TEST_SUITE_PATHSPEC = "*-test.sh"
SKIPPED_CASE_LINE = re.compile(r"^SKIP\s")

# Git redirection variables can send scratch-repository writes into a live repository.
# Keep GIT_CEILING_DIRECTORIES: removing it widens repository discovery.
GIT_REDIRECTING_ENVIRONMENT_VARIABLES = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
)

# Suites run as the same account as every agent-seat, so a stray kill(-1) or
# killpg from a suite reaches all of them. In its own PID namespace a suite can
# signal only the processes it started. Children of bwrap cannot start bwrap
# again (Ubuntu's AppArmor profile denies them capabilities), so a run inside
# the sandbox, such as a suite that tests this program, runs its suites as they
# are: they are already inside.
SIGNAL_SANDBOX_BWRAP_ARGUMENTS = (
    "--dev-bind", "/", "/", "--unshare-pid", "--die-with-parent", "--proc", "/proc")
SIGNAL_SANDBOX_INSIDE_VARIABLE = "RUN_ALL_TEST_SUITES_INSIDE_SIGNAL_SANDBOX"
SIGNAL_SANDBOX_START_TIMEOUT_SECONDS = 60
# The profile the user's Mac run of the check passed on 2026-10-08 (macOS 26.6.2).
SIGNAL_SANDBOX_MACOS_SANDBOX_EXEC = "/usr/bin/sandbox-exec"
SIGNAL_SANDBOX_MACOS_LIBSYSTEM = "/usr/lib/libSystem.B.dylib"
SIGNAL_SANDBOX_MACOS_PROFILE = (
    "(version 1)(allow default)(deny signal)(allow signal (target same-sandbox))")
# The process outside the sandbox that a check inside it signals and must be refused by.
SIGNAL_SANDBOX_TRIAL_SIGNAL_TARGET_PROCESS_VARIABLE = "RUN_ALL_TEST_SUITES_SIGNAL_SANDBOX_TRIAL_SIGNAL_TARGET_PROCESS_ID"
# SIGWINCH, because a process that does not handle it ignores it: if the sandbox
# lets the probe through, nothing outside is stopped.
SIGNAL_SANDBOX_MACOS_PROBE_SIGNAL = signal.SIGWINCH
SIGNAL_SANDBOX_MACOS_TRIAL_SOURCE = (
    "import os, signal, sys\n"
    f"outside = int(os.environ[{SIGNAL_SANDBOX_TRIAL_SIGNAL_TARGET_PROCESS_VARIABLE!r}])\n"
    "try:\n"
    f"    os.kill(outside, {int(SIGNAL_SANDBOX_MACOS_PROBE_SIGNAL)})\n"
    "except PermissionError:\n"
    "    sys.exit(0)\n"
    "except OSError as error:\n"
    "    sys.exit(f'the trial signal to process {outside} outside the sandbox failed: {error}')\n"
    "sys.exit(f'a signal from inside the sandbox reached process {outside} outside it')\n")
SIGNAL_NUMBER_LIMIT = 64
# Suites that cannot work inside the sandbox run outside it, each named in the report.
SUITES_RUN_OUTSIDE_THE_SIGNAL_SANDBOX = {
    "nc-systems/cold-read/tests/cold-read-agy-cell-test.py":
        "it starts the agy cell's own bwrap, which cannot start inside bwrap",
    "nc-systems/cold-read/tests/cold-read-fast-read-test.py":
        "it starts the agy cell's own bwrap, which cannot start inside bwrap",
    "scripts/run-all-test-suites-cleanup-after-killed-runs-real-process-test.py":
        "it starts this program, whose suites run in bwrap, which cannot start inside bwrap",
    "scripts/mac-window-opened-for-ned-box-forced-command-test.py":
        "it runs the real ssh, which refuses its root-owned config files because "
        "inside the sandbox's user namespace they show as owned by nobody",
}

DEFAULT_LOCK_FILE = Path.home() / ".claude" / ".run-all-test-suites.lock"
RUN_RECORDS_DIRECTORY_SUFFIX = ".runs"
# Long enough for whoever reads a run's report and failed-suite logs to read them.
FINISHED_RUN_LOG_RETENTION_SECONDS = 2 * 24 * 3600
LOG_DIRECTORY_LOCK_FILE_NAME = ".run-all-test-suites-log-directory.lock"
REPORT_FILE_NAME = "report.txt"
SUITES_RUN_AT_ONCE_WHEN_CORE_COUNT_UNKNOWN = 4

DEFAULT_RECORDED_INPUTS_DIRECTORY = (
    Path.home() / ".cache" / "nedschorus-test-suite-recorded-inputs")
# Bump when the recording format changes so older recordings trigger a fresh run.
RECORDED_INPUTS_FORMAT_VERSION = 5
RECORDED_INPUTS_LOG_VARIABLE = "RUN_ALL_TEST_SUITES_RECORDED_INPUTS_LOG"
RECORDED_INPUTS_CHECKOUT_VARIABLE = "RUN_ALL_TEST_SUITES_RECORDED_INPUTS_CHECKOUT"
# Nested runs put multiple recorders on PYTHONPATH; skip all when chaining sitecustomize.
PYTHON_INPUT_RECORDER_MARKER_FILE_NAME = "run-all-test-suites-python-input-recorder"
PYTHON_INPUT_RECORDER_METHOD = "python-audit-hook"
STRACE_INPUT_RECORDER_METHOD = "strace"
# The runner, hooks and settings can affect every suite or session a suite starts.
EVERY_SUITE_RUNS_WHEN_THESE_CHANGE = (
    "scripts/run-all-test-suites.py", ".claude/hooks/", ".claude/settings.json")
# Object-store content reads evade recorders; only metadata-only commands belong here.
# status is excluded because stale timestamps can make it read working files.
GIT_COMMANDS_THAT_ONLY_LIST = frozenset((
    "ls-files", "ls-tree", "rev-parse", "rev-list", "log", "branch", "config",
    "remote", "worktree", "for-each-ref", "symbolic-ref", "merge-base",
    "describe", "show-ref", "check-ignore", "var", "version", "fetch", "init"))
# These options read repository location, not checkout files.
GIT_REV_PARSE_OPTIONS_THAT_SEE_NO_FILE = frozenset((
    "--show-toplevel", "--git-dir", "--absolute-git-dir", "--git-common-dir",
    "--is-inside-work-tree", "--show-prefix"))
# Single-key config reads use the git directory or home, not checkout files.
GIT_CONFIG_OPTIONS_THAT_READ_ONE_KEY = ("--get", "--get-all")
# These commands do not treat the current directory as a work tree.
GIT_COMMANDS_THAT_READ_NO_WORK_TREE = frozenset((
    "rev-parse", "log", "show", "cat-file", "for-each-ref", "config"))
GIT_CALL_SEES_NO_FILE = "sees no file"
GIT_CALL_RUNS_ON_ANOTHER_REPOSITORY = "runs on another repository"
GIT_CALL_READS_THE_CHECKOUT = "reads the checkout"
PYCACHE_FILE = re.compile(
    r"^(?P<directory>(?:.*/)?)__pycache__/(?P<stem>[^/]+?)\.[^/.]+(?:\.opt-\d)?\.pyc$")

# Keep the recorder here so editing it selects every suite.
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

    # Options of init and clone whose value is the next argument, so that
    # value is never taken for the directory or source the command names.
    options_taking_a_value = {
        "init": ("-b", "--initial-branch", "--template", "--separate-git-dir",
                 "--object-format", "--ref-format"),
        "clone": ("-b", "--branch", "-o", "--origin", "-u", "--upload-pack", "--template",
                  "--reference", "--reference-if-able", "--separate-git-dir", "--depth",
                  "--shallow-since", "--shallow-exclude", "-c", "--config", "-j", "--jobs",
                  "--filter", "--server-option", "--bundle-uri", "--ref-format", "--revision"),
    }
    is_file = _os.path.isfile

    def started(program, arguments, working_directory, environment):
        if isinstance(arguments, (str, bytes, _os.PathLike)):
            arguments = [arguments]
        arguments = list(arguments or [])
        for argument in ([program] if program is not None else []) + arguments:
            path = absolute(argument, working_directory)
            if inside(path) and is_file(path):
                write("read", path)
        if not arguments or _os.path.basename(_os.fsdecode(arguments[0])) != "git":
            return
        directory = absolute(working_directory) if working_directory is not None else _os.getcwd()
        target = directory
        git_arguments = [_os.fsdecode(argument) for argument in arguments[1:]]
        rest = git_arguments
        index = 0
        while index < len(rest) and rest[index].startswith("-"):
            if rest[index] == "-C" and index + 1 < len(rest):
                target = absolute(rest[index + 1], target)
                index += 2
            elif rest[index] in ("-c", "--git-dir", "--work-tree", "--namespace",
                                 "--config-env") and index + 1 < len(rest):
                index += 2
            else:
                index += 1
        if index >= len(rest):
            return
        command, rest = rest[index], rest[index + 1:]
        operands, index = [], 0
        while index < len(rest):
            if rest[index] == "--":
                operands.extend(rest[index + 1:])
                break
            if rest[index] in options_taking_a_value.get(command, ()):
                index += 2
                continue
            if not rest[index].startswith("-"):
                operands.append(rest[index])
            index += 1
        if command == "clone":
            # A clone reads its source, not the directory it is run from.
            sources = [absolute(operand[len("file://"):] if operand.startswith("file://")
                                else operand, target) for operand in operands[:1]]
            if not any(inside(_os.path.realpath(source)) for source in sources if source):
                return
        else:
            if command == "init" and operands:
                target = absolute(operands[0], target)
            if not inside(_os.path.realpath(target or "")):
                return
        import json
        environment = _os.environ if environment is None else environment
        call = {
            "arguments": git_arguments,
            "directory": directory,
        }
        for name in ("GIT_DIR", "GIT_WORK_TREE"):
            value = None
            for key in (name, _os.fsencode(name)):
                try:
                    value = environment.get(key)
                except TypeError:
                    continue
                if value is not None:
                    break
            call[name] = _os.fsdecode(value) if value is not None else None
        write("git", json.dumps(call))

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
                started(arguments[0], arguments[1], arguments[2], arguments[3])
            elif event in ("os.exec", "os.posix_spawn"):
                started(None, arguments[1], None, arguments[2])
        except Exception:
            pass

    _sys.addaudithook(hook)

    # Python raises no audit event for a stat, so a check that a path exists
    # is written down here instead; pathlib's exists, is_file and is_dir call
    # these. The import system stats through its own functions, not these.
    # os.stat itself is left alone: shutil decides at import whether rmtree
    # may use its fd-based walk by testing `os.stat in os.supports_dir_fd`,
    # which a wrapper would fail.
    def probing(original):
        def probe(path, *arguments, **keywords):
            try:
                path_probed = absolute(path)
                if inside(path_probed):
                    write("probe", path_probed)
            except Exception:
                pass
            return original(path, *arguments, **keywords)
        for attribute in ("__module__", "__name__", "__qualname__", "__doc__"):
            setattr(probe, attribute, getattr(original, attribute, None))
        probe.__wrapped__ = original
        return probe

    for name in ("exists", "lexists", "isfile", "isdir", "islink"):
        setattr(_os.path, name, probing(getattr(_os.path, name)))


_run_all_test_suites_install_input_recorder()


def _run_all_test_suites_run_the_shadowed_sitecustomize():
    import importlib.machinery
    import importlib.util
    marker = "run-all-test-suites-python-input-recorder"
    # The recorder's own lookups are not the suite's: no probe is written.
    exists = getattr(_os.path.exists, "__wrapped__", _os.path.exists)
    search = [entry for entry in _sys.path
              if not exists(_os.path.join(entry or _os.getcwd(), marker))]
    spec = importlib.machinery.PathFinder.find_spec("sitecustomize", search)
    if spec is not None and spec.loader is not None:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)


_run_all_test_suites_run_the_shadowed_sitecustomize()
'''

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


def git_call_global_options_command_and_arguments(arguments):
    """Separate global options from the command without guessing at operands."""
    global_options, index = [], 0
    while index < len(arguments):
        option = arguments[index]
        if not option.startswith("-"):
            return global_options, option, arguments[index + 1:]
        if option.startswith("--") and "=" in option:
            global_options.append(tuple(option.split("=", 1)))
        elif option in ("-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env"):
            if index + 1 >= len(arguments):
                return None
            index += 1
            global_options.append((option, arguments[index]))
        else:
            global_options.append((option, None))
        index += 1
    return None


@functools.lru_cache(maxsize=None)
def git_common_directory_of_checkout(top):
    """Return the checkout repository's shared git directory."""
    # A linked worktree's git directory can lie outside its top directory.
    answer = git(top, "rev-parse", "--git-common-dir")
    if answer.returncode != 0:
        return None
    return os.path.realpath(os.path.join(top, answer.stdout.strip()))


def what_a_git_call_run_from_the_checkout_reads(call, top, git_common_directory):
    """Set aside only calls whose full arguments satisfy one of the allowlists."""
    if not isinstance(call, dict) or not isinstance(call.get("arguments"), list) \
            or not all(isinstance(argument, str) for argument in call["arguments"]):
        return GIT_CALL_READS_THE_CHECKOUT
    parsed = git_call_global_options_command_and_arguments(call["arguments"])
    if parsed is None:
        return GIT_CALL_READS_THE_CHECKOUT
    global_options, command, command_arguments = parsed
    if all(option == "-C" and value is not None for option, value in global_options):
        if command == "rev-parse" and command_arguments \
                and all(argument in GIT_REV_PARSE_OPTIONS_THAT_SEE_NO_FILE
                        for argument in command_arguments):
            return GIT_CALL_SEES_NO_FILE
        if command == "config":
            operands = command_arguments
            if len(operands) == 2 and operands[0] in GIT_CONFIG_OPTIONS_THAT_READ_ONE_KEY:
                operands = operands[1:]
            if len(operands) == 1:
                key = operands[0]
                if not key.startswith("-") and "." in key and "=" not in key \
                        and not any(character.isspace() for character in key):
                    return GIT_CALL_SEES_NO_FILE
    if any(option not in ("-C", "--git-dir", "--work-tree") or value is None
           for option, value in global_options):
        return GIT_CALL_READS_THE_CHECKOUT
    directory = call.get("directory")
    if not isinstance(directory, str):
        return GIT_CALL_READS_THE_CHECKOUT
    git_directory, work_tree = call.get("GIT_DIR"), call.get("GIT_WORK_TREE")
    for option, value in global_options:
        if option == "-C":
            directory = os.path.join(directory, value)
        elif option == "--git-dir":
            git_directory = value
        elif option == "--work-tree":
            work_tree = value
    if not isinstance(git_directory, str) or not git_directory:
        return GIT_CALL_READS_THE_CHECKOUT
    git_directory = os.path.realpath(os.path.join(directory, git_directory))
    if relative_inside(top, git_directory) is not None \
            or (git_common_directory is not None
                and relative_inside(git_common_directory, git_directory) is not None):
        return GIT_CALL_READS_THE_CHECKOUT
    if isinstance(work_tree, str) and relative_inside(
            top, os.path.realpath(os.path.join(directory, work_tree))) is None:
        return GIT_CALL_RUNS_ON_ANOTHER_REPOSITORY
    if command in GIT_COMMANDS_THAT_READ_NO_WORK_TREE \
            or (command == "worktree" and command_arguments[:1] == ["list"]):
        return GIT_CALL_RUNS_ON_ANOTHER_REPOSITORY
    return GIT_CALL_READS_THE_CHECKOUT


def checkout_top_directory(given):
    """Return the checkout top directory or refuse a non-top-level path."""
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
    listed = git(top, "ls-files", "-z", "--", TEST_SUITE_PATHSPEC, SHELL_TEST_SUITE_PATHSPEC)
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
    """Return (handle, refusal, previous holder), with None for unavailable fields."""
    # Append mode preserves the holder's description when another run wins the lock.
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_file, "a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.seek(0)
        holder = handle.read().strip() or "a run that has not described itself yet"
        handle.close()
        return None, holder, None
    handle.seek(0)
    previous_holder = handle.read()
    handle.seek(0)
    handle.truncate()
    started = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    handle.write(f"pid {os.getpid()}, checkout {top}, started {started}\n")
    handle.flush()
    return handle, None, previous_holder


def name_log_directory_in_lock(handle, log_dir):
    # The next lock holder needs the log directory to remove traces after a killed run.
    handle.seek(0)
    description = handle.read().rstrip("\n")
    # Append mode ignores seek for writes; truncate before replacing the description.
    handle.truncate(0)
    handle.write(f"{description}, logs in {log_dir}\n")
    handle.flush()


def remove_traces_the_last_lock_holder_left(previous_holder):
    """Return the trace directories removed from the previous lock holder's logs."""
    named = re.search(r", logs in (?P<log_dir>[^\n]+)$", previous_holder.strip())
    if named is None:
        return []
    left = sorted(Path(named["log_dir"], "recorded-inputs").glob("*.strace"))
    for trace_dir in left:
        shutil.rmtree(trace_dir, ignore_errors=True)
    return left


def run_records_directory_for_lock_file(lock_file):
    """The directory of run records that goes with a lock file."""
    # Beside the lock, so a test that passes its own lock file also gets its own records.
    return Path(f"{lock_file}{RUN_RECORDS_DIRECTORY_SUFFIX}")


def process_start_ticks(pid, proc=Path("/proc")):
    """The process's start time in clock ticks since boot, or None when it is gone or a zombie."""
    try:
        stat = (proc / str(pid) / "stat").read_text()
    except (FileNotFoundError, ProcessLookupError):
        return None
    # The command name may hold spaces and ")", so split after its last ")".
    fields = stat.rsplit(")", 1)[1].split()
    if fields[0] == "Z":
        return None
    return int(fields[19])


def process_alive(pid, start_ticks, proc=Path("/proc")):
    """True while the process that had this pid and start time still runs.

    A process recorded without a start time had ended before it could be read,
    so it never counts as running."""
    if start_ticks is None:
        return False
    return process_start_ticks(pid, proc) == start_ticks


class RunRecord:
    """This run's record in the runs directory, which a later run reads to know
    whether this run, and every suite process it started, has ended."""

    def __init__(self, runs_dir, log_dir, log_dir_is_temporary, proc=Path("/proc")):
        runs_dir.mkdir(parents=True, exist_ok=True)
        start_ticks = process_start_ticks(os.getpid(), proc)
        self.path = runs_dir / f"{os.getpid()}-{start_ticks}.json"
        self.content = {
            "runner": {"pid": os.getpid(), "start_ticks": start_ticks},
            "log_dir": str(log_dir),
            "log_dir_is_temporary": log_dir_is_temporary,
            "started": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "suite_processes": [],
            "finished": None,
        }
        self.proc = proc
        self.lock = threading.Lock()
        self.write()

    def write(self):
        temporary = self.path.with_name(f".{self.path.name}.{threading.get_ident()}")
        temporary.write_text(json.dumps(self.content))
        os.replace(temporary, self.path)

    def note_suite_process(self, pid, namespace_init):
        # Recorded the moment the process exists, so a run killed later still names it.
        start_ticks = process_start_ticks(pid, self.proc)
        if start_ticks is None:
            return
        with self.lock:
            self.content["suite_processes"].append(
                {"pid": pid, "start_ticks": start_ticks, "namespace_init": namespace_init})
            self.write()

    def finish(self):
        with self.lock:
            if not self.content["log_dir_is_temporary"]:
                # A log directory the caller chose is the caller's to remove; nothing is left to reap.
                self.path.unlink(missing_ok=True)
                return
            self.content["finished"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self.write()


def remove_tree_or_say_why(path):
    """Delete a directory tree; return None when it is gone, or the reason it is not."""
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        return None
    except OSError as error:
        return str(error)
    return None


def write_run_record(path, content):
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}")
    temporary.write_text(json.dumps(content))
    os.replace(temporary, path)


def first_confirmed_end(path, record, now):
    """When this ended run was first seen ended, written into its record the first time.

    A finished run ended when it wrote "finished". A killed run's end is known
    only when a later run first finds all of its processes gone, so the time
    that later run looked is recorded and the retention counts from it."""
    if record.get("confirmed_ended") is not None:
        return record["confirmed_ended"]
    if record.get("finished"):
        ended = datetime.datetime.fromisoformat(record["finished"]).timestamp()
    else:
        ended = now
    record["confirmed_ended"] = ended
    write_run_record(path, record)
    return ended


def remove_leftovers_of_ended_runs_named_in_run_records(
        runs_dir, own_record=None, now=None, alive=process_alive,
        retention_seconds=FINISHED_RUN_LOG_RETENTION_SECONDS):
    """Remove what ended runs left behind; return one report line per run acted on or kept.

    A run is ended only when its runner and every suite process it recorded are
    gone: a suite process of a killed runner may still be writing its traces.
    A run's temporary log directory goes once the run has been ended for
    retention_seconds; its record goes only with it, so a directory that could
    not be removed is tried again by the next run."""
    now = time.time() if now is None else now
    lines = []
    for path in sorted(runs_dir.glob("*.json")) if runs_dir.is_dir() else []:
        if own_record is not None and path == own_record.path:
            continue
        try:
            record = json.loads(path.read_text())
        except (OSError, ValueError) as error:
            lines.append(f"run record {path} could not be read ({error}); it is kept")
            continue
        runner = record["runner"]
        if alive(runner["pid"], runner["start_ticks"]):
            continue
        running = [process for process in record["suite_processes"]
                   if alive(process["pid"], process["start_ticks"])]
        log_dir = Path(record["log_dir"])
        if running:
            lines.append(f"the run that logged to {log_dir} has no runner, but "
                         f"{len(running)} of its suite processes still run; its files are kept")
            continue
        traces = sorted((log_dir / "recorded-inputs").glob("*.strace"))
        failures = [(trace_dir, why) for trace_dir in traces
                    if (why := remove_tree_or_say_why(trace_dir)) is not None]
        removed_traces = len(traces) - len(failures)
        if removed_traces:
            lines.append(f"removed {removed_traces} strace directories the ended run left in "
                         f"{log_dir / 'recorded-inputs'}")
        if not record["log_dir_is_temporary"]:
            if not failures:
                path.unlink(missing_ok=True)
        else:
            try:
                ended = first_confirmed_end(path, record, now)
            except (OSError, ValueError) as error:
                lines.append(f"run record {path} could not be updated ({error}); it is kept")
                continue
            if not failures and now - ended >= retention_seconds:
                why = remove_tree_or_say_why(log_dir)
                if why is None:
                    path.unlink(missing_ok=True)
                    lines.append(f"removed the log directory {log_dir} of a run that ended "
                                 f"more than {retention_seconds // 3600} hours ago")
                else:
                    failures.append((log_dir, why))
        for failed, why in failures:
            lines.append(f"could not remove {failed} ({why}); its run record {path} is kept, "
                         f"so the next run tries again")
    return lines


def newest_modification_time_in_tree(directory):
    """The newest modification time of the directory and everything under it."""
    newest = directory.stat().st_mtime

    def fail(error):
        raise error
    for parent, subdirectories, files in os.walk(directory, onerror=fail):
        for name in subdirectories + files:
            newest = max(newest, (Path(parent) / name).lstat().st_mtime)
    return newest


def remove_old_temporary_log_directories_without_run_records(
        runs_dir, now=None, temp_dir=None,
        retention_seconds=FINISHED_RUN_LOG_RETENTION_SECONDS):
    """Remove old log directories that runs made before runs kept records.

    Returns (removed, failures), failures being (directory, reason) pairs. A
    directory a caller chose with --log-dir holds the log-directory lock file and
    is the caller's to remove, so it is never touched. A directory counts as old
    only when nothing anywhere under it changed for retention_seconds, because a
    suite of an old run may still be appending to a trace deep inside it."""
    now = time.time() if now is None else now
    temp_dir = Path(tempfile.gettempdir() if temp_dir is None else temp_dir)
    named = set()
    for path in runs_dir.glob("*.json") if runs_dir.is_dir() else []:
        with contextlib.suppress(OSError, ValueError, KeyError):
            named.add(Path(json.loads(path.read_text())["log_dir"]))
    removed, failures = [], []
    for log_dir in sorted(temp_dir.glob(f"{PROGRAM}-*")):
        if log_dir in named or not log_dir.is_dir():
            continue
        if (log_dir / LOG_DIRECTORY_LOCK_FILE_NAME).exists():
            continue
        try:
            newest = newest_modification_time_in_tree(log_dir)
        except OSError:
            continue
        if now - newest >= retention_seconds:
            why = remove_tree_or_say_why(log_dir)
            if why is None:
                removed.append(log_dir)
            else:
                failures.append((log_dir, why))
    return removed, failures


def clean_up_after_earlier_runs(lock_file, previous_holder, platform=None):
    """Remove what earlier runs left, once nothing of theirs still runs; return report lines.

    On Linux every run keeps a record of its runner and suite processes. On
    other platforms there is no /proc to read start times from, so the lock's
    last holder is cleaned up after, as before."""
    platform = sys.platform if platform is None else platform
    if not platform.startswith("linux"):
        left = remove_traces_the_last_lock_holder_left(previous_holder)
        return ([f"removed {len(left)} strace directories the run before this one left "
                 f"in {left[0].parent}"] if left else [])
    runs_dir = run_records_directory_for_lock_file(lock_file)
    lines = remove_leftovers_of_ended_runs_named_in_run_records(runs_dir)
    if Path(lock_file) == DEFAULT_LOCK_FILE:
        # Only the machine's own runs share the system temp directory with records this old.
        removed, failures = remove_old_temporary_log_directories_without_run_records(runs_dir)
        lines += [f"removed the log directory {log_dir}, left by a run from before run records"
                  for log_dir in removed]
        lines += [f"could not remove the log directory {log_dir}, left by a run from before "
                  f"run records ({why})" for log_dir, why in failures]
    return lines


def lock_explicit_log_directory(log_dir):
    """Hold the given log directory for this run, or return None when another run holds it."""
    handle = open(log_dir / LOG_DIRECTORY_LOCK_FILE_NAME, "a")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


def log_path_for(log_dir, suite):
    # Include the relative path to distinguish suites with the same filename.
    return log_dir / (suite.replace("/", "__") + ".log")


def skipped_case_lines(log_file):
    try:
        text = log_file.read_text(errors="replace")
    except OSError:
        return []
    return [line for line in text.splitlines() if SKIPPED_CASE_LINE.match(line)]


def environment_without_git_redirecting_variables():
    # Use a fresh dict because suites launch concurrently.
    environment = dict(os.environ)
    for variable in GIT_REDIRECTING_ENVIRONMENT_VARIABLES:
        environment.pop(variable, None)
    return environment


def being_traced():
    """Return whether Linux reports an attached tracer."""
    # A second strace cannot attach beneath an existing tracer.
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("TracerPid:"):
                return line.split()[1] != "0"
    except OSError:
        pass
    return False


def strace_usable():
    """Return the strace path if a trial trace succeeds, otherwise None."""
    if not sys.platform.startswith("linux") or being_traced():
        return None
    found = shutil.which("strace")
    if found is None:
        return None
    trial = subprocess.run([found, "-f", "-qq", "-e", "trace=none", "true"],
                           capture_output=True, stdin=subprocess.DEVNULL, check=False)
    return found if trial.returncode == 0 else None


def recording_paths_for(recording_dir, suite):
    """Return (audit log path, strace directory)."""
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


def is_shell_test_suite(suite):
    return suite.endswith(SHELL_TEST_SUITE_PATHSPEC[1:])


class SignalSandboxCouldNotStart(Exception):
    """The signal sandbox is expected here but could not start; the message says why."""


def macos_process_is_sandboxed(load_library=ctypes.CDLL):
    """Return whether macOS already confines this process in a sandbox.

    Raises SignalSandboxCouldNotStart when the check cannot be made, since a
    wrong answer either nests sandbox-exec or leaves the suites unconfined.
    """
    try:
        sandbox_check = load_library(SIGNAL_SANDBOX_MACOS_LIBSYSTEM, use_errno=True).sandbox_check
    except (OSError, AttributeError) as error:
        raise SignalSandboxCouldNotStart(
            f"sandbox_check could not be loaded from {SIGNAL_SANDBOX_MACOS_LIBSYSTEM}: "
            f"{error}") from error
    sandbox_check.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int)
    sandbox_check.restype = ctypes.c_int
    # No operation named: the answer is whether any sandbox applies to the process.
    result = sandbox_check(os.getpid(), None, 0)
    if result not in (0, 1):
        raise SignalSandboxCouldNotStart(
            f"sandbox_check({os.getpid()}, NULL, 0) returned {result}: "
            f"{os.strerror(ctypes.get_errno())}")
    return result == 1


def signal_sandbox(platform=None, environment=None, which=shutil.which,
                   runner=subprocess.run, sandbox_exec=SIGNAL_SANDBOX_MACOS_SANDBOX_EXEC,
                   outside_process_id=None, is_macos_process_sandboxed=None):
    """Return (prefix, None) to put before a suite's command, or ((), why) when it runs unconfined.

    Raises SignalSandboxCouldNotStart when bwrap is on PATH but fails to start,
    or on macOS when sandbox-exec is missing, fails to start or lets a trial
    signal out, since running unconfined then would hide a broken sandbox.
    On macOS, a process that a sandbox already confines gets ((), None), and a
    failed check of that raises the same error.
    outside_process_id is the process outside the sandbox that checks inside it
    signal; default this process.
    """
    platform = sys.platform if platform is None else platform
    environment = os.environ if environment is None else environment
    if environment.get(SIGNAL_SANDBOX_INSIDE_VARIABLE):
        return (), None
    if platform == "darwin":
        if (is_macos_process_sandboxed or macos_process_is_sandboxed)():
            return (), None
        return macos_signal_sandbox(
            runner, sandbox_exec,
            os.getpid() if outside_process_id is None else outside_process_id), None
    if not platform.startswith("linux"):
        return (), f"{platform} has no signal sandbox built for it"
    bwrap = which("bwrap")
    if bwrap is None:
        return (), "bwrap is not on PATH (Ubuntu: sudo apt install bubblewrap)"
    prefix = (bwrap, *SIGNAL_SANDBOX_BWRAP_ARGUMENTS,
              "--setenv", SIGNAL_SANDBOX_INSIDE_VARIABLE, "1")
    try:
        trial = runner([*prefix, "true"], stdin=subprocess.DEVNULL, capture_output=True,
                       text=True, timeout=SIGNAL_SANDBOX_START_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise SignalSandboxCouldNotStart(f"{' '.join(prefix)} true: {error}") from error
    if trial.returncode != 0:
        raise SignalSandboxCouldNotStart(
            f"{' '.join(prefix)} true exited {trial.returncode}: "
            f"{(trial.stderr or trial.stdout).strip()}")
    return prefix, None


def macos_signal_sandbox(runner, sandbox_exec, outside_process_id):
    """Return the sandbox-exec prefix once a trial inside it is refused a signal to outside_process_id."""
    if not Path(sandbox_exec).is_file():
        raise SignalSandboxCouldNotStart(f"{sandbox_exec} is not on this Mac")
    prefix = (sandbox_exec, "-p", SIGNAL_SANDBOX_MACOS_PROFILE, "/usr/bin/env",
              f"{SIGNAL_SANDBOX_INSIDE_VARIABLE}=1",
              f"{SIGNAL_SANDBOX_TRIAL_SIGNAL_TARGET_PROCESS_VARIABLE}={outside_process_id}")
    trial_command = [*prefix, sys.executable, "-c", SIGNAL_SANDBOX_MACOS_TRIAL_SOURCE]
    try:
        trial = runner(trial_command, stdin=subprocess.DEVNULL, capture_output=True,
                       text=True, timeout=SIGNAL_SANDBOX_START_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise SignalSandboxCouldNotStart(f"{sandbox_exec} trial: {error}") from error
    if trial.returncode != 0:
        raise SignalSandboxCouldNotStart(
            f"the trial inside {sandbox_exec} -p '{SIGNAL_SANDBOX_MACOS_PROFILE}' exited "
            f"{trial.returncode}: {(trial.stderr or trial.stdout).strip()}")
    return prefix


def does_signal_sandbox_report_killed_suite_as_exit_code_128_plus_signal(prefix):
    """bwrap stays the suite's parent and exits 128+N for a suite killed by signal N."""
    return bool(prefix) and Path(prefix[0]).name == "bwrap"


def signal_sandbox_refusal(error, program=PROGRAM):
    """The text a program prints when the signal sandbox is expected but cannot start."""
    return (f"{program}: not run — the signal sandbox could not start: {error}\n"
            f"Each suite runs inside the signal sandbox (bwrap on Linux, "
            f"sandbox-exec on macOS) so that a stray signal cannot reach the "
            f"agent-seats running as the same account.\n"
            f"If this run is itself inside a bwrap sandbox (for example a Codex "
            f"sandbox), run it from an ordinary shell instead.\n"
            f"If this run is inside such a sandbox and you cannot leave it, tell "
            f"the user the suites were not run and why, and ask the user to run "
            f"the same command from an ordinary shell on this machine.\n"
            f"On Linux, if this run is not inside another sandbox, check that "
            f"`bwrap {' '.join(SIGNAL_SANDBOX_BWRAP_ARGUMENTS)} true` "
            f"works on this machine, and report what it prints to the user.\n"
            f"On macOS, report the reason above to the user: the suites need "
            f"{SIGNAL_SANDBOX_MACOS_SANDBOX_EXEC} to refuse their signals to "
            f"processes outside the sandbox.")


def signal_sandbox_line(prefix, unconfined_because):
    if does_signal_sandbox_report_killed_suite_as_exit_code_128_plus_signal(prefix):
        return f"each suite runs in its own PID namespace: {' '.join(prefix)}"
    if prefix:
        return (f"each suite runs in a sandbox that refuses its signals to any process "
                f"outside it: {' '.join(prefix)}")
    if unconfined_because:
        return (f"suites run WITHOUT the signal sandbox, so a stray signal can reach "
                f"any process of this account: {unconfined_because}")
    return "suites run inside the sandbox this run was started in"


def suite_process_started(process, status_read, note_suite_process):
    """Record the process whose end ends the suite: bwrap's namespace init, or the suite itself."""
    if status_read is None:
        note_suite_process(process.pid, namespace_init=False)
        return
    # bwrap's first status line names the init of the suite's PID namespace; when
    # that init ends, the kernel ends every process inside it.
    line = status_read.readline()
    try:
        init = json.loads(line)["child-pid"]
    except (ValueError, KeyError, TypeError):
        # bwrap failed before starting the suite; the outer bwrap is all there is.
        note_suite_process(process.pid, namespace_init=False)
        return
    note_suite_process(init, namespace_init=True)


def run_one_suite(top, interpreter, suite, log_dir, recorder=None, sandbox_prefix=(),
                  note_suite_process=None):
    log_file = log_path_for(log_dir, suite)
    environment = environment_without_git_redirecting_variables()
    command = ["sh", suite] if is_shell_test_suite(suite) else [interpreter, "-u", suite]
    if recorder is not None:
        recorder_dir, recording_dir, strace = recorder
        hook_log, strace_dir = recording_paths_for(recording_dir, suite)
        # The audit hook appends; clear old logs so earlier reads do not count for this run.
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
    if suite in SUITES_RUN_OUTSIDE_THE_SIGNAL_SANDBOX:
        sandbox_prefix = ()
    status_read = status_write = None
    if sandbox_prefix and note_suite_process is not None:
        status_read_fd, status_write = os.pipe()
        status_read = os.fdopen(status_read_fd, "r")
        sandbox_prefix = (sandbox_prefix[0], "--json-status-fd", str(status_write),
                          *sandbox_prefix[1:])
    command = [*sandbox_prefix, *command]
    started = time.monotonic()
    try:
        with open(log_file, "wb") as log:
            process = subprocess.Popen(
                command, cwd=str(top), env=environment, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT,
                pass_fds=(status_write,) if status_write is not None else ())
            if status_write is not None:
                os.close(status_write)
                status_write = None
            if note_suite_process is not None:
                suite_process_started(process, status_read, note_suite_process)
            exit_code = process.wait()
    finally:
        if status_write is not None:
            os.close(status_write)
        # Closed only after bwrap exits: bwrap writes its exit status to this pipe last.
        if status_read is not None:
            status_read.close()
    # bwrap exits 128+N when the suite is killed by signal N; report it as the signal, as unsandboxed runs do.
    if does_signal_sandbox_report_killed_suite_as_exit_code_128_plus_signal(sandbox_prefix) and \
            128 < exit_code <= 128 + SIGNAL_NUMBER_LIMIT:
        exit_code = -(exit_code - 128)
    return {
        "suite": suite,
        "exit": exit_code,
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


def inside_git_directory(relative):
    return relative == ".git" or relative.startswith(".git/")


def checkout_files(top):
    """Return tracked and nonignored untracked files currently on disk."""
    listed = git(top, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    if listed.returncode != 0:
        raise CouldNotRun(
            f"{PROGRAM}: not run — git ls-files failed in {top}: {listed.stderr.strip()}\n"
            f"Fix what git reports, then run this again.")
    return {path for path in listed.stdout.split("\0")
            if path and os.path.lexists(top / path)}


def files_at_commit(top, commit):
    listed = git(top, "ls-tree", "-r", "--name-only", "-z", commit)
    if listed.returncode != 0:
        raise CouldNotRun(
            f"{PROGRAM}: not run — git ls-tree {commit} failed in {top}: "
            f"{listed.stderr.strip()}\nFix what git reports, then run this again.")
    return {path for path in listed.stdout.split("\0") if path}


def directory_entries(files):
    """Return directory-to-entry-name mappings; the top directory is the empty string."""
    entries = {}
    for path in files:
        parts = path.split("/")
        for depth in range(len(parts)):
            entries.setdefault("/".join(parts[:depth]), set()).add(parts[depth])
    return entries


def file_list_fingerprint(files):
    return hashlib.sha256("\0".join(sorted(files)).encode(
        "utf-8", "surrogateescape")).hexdigest()


def recording_of(top, suite, result, recording_dir, files, commit, strace_used):
    """Return the suite's recorded files, path checks, directory listings and git calls."""
    hook_log, strace_dir = recording_paths_for(recording_dir, suite)
    touched, probed, listed, git_commands = {suite}, set(), set(), set()
    git_calls = {}
    try:
        hook_lines = hook_log.read_text(errors="surrogateescape").splitlines()
    except OSError:
        hook_lines = []
    for line in hook_lines:
        kind, _, value = line.partition("\t")
        if kind == "git":
            try:
                call = json.loads(value)
            except ValueError:
                call = None
            if not isinstance(call, dict):
                call = {}
            call = {key: call.get(key) for key in (
                "arguments", "directory", "GIT_DIR", "GIT_WORK_TREE")}
            call["reads"] = what_a_git_call_run_from_the_checkout_reads(
                call, top, git_common_directory_of_checkout(str(top)))
            if call["reads"] == GIT_CALL_READS_THE_CHECKOUT:
                arguments = call["arguments"]
                parsed = (git_call_global_options_command_and_arguments(arguments)
                          if isinstance(arguments, list)
                          and all(isinstance(argument, str) for argument in arguments) else None)
                git_commands.add(parsed[1] if parsed is not None else "(unparsed)")
            if isinstance(call["directory"], str):
                relative = relative_inside(top, call["directory"])
                if relative is not None:
                    call["directory"] = relative
            git_calls[json.dumps(call, sort_keys=True)] = call
            continue
        relative = relative_inside(top, value)
        if relative is None or inside_git_directory(relative):
            continue
        if kind == "read":
            touched.add(source_of_cached_bytecode(relative))
        elif kind == "probe":
            probed.add(relative)
        elif kind == "list":
            listed.add("" if relative == "." else relative)
    if strace_used:
        for path in paths_strace_saw(strace_dir):
            relative = relative_inside(top, path)
            if relative is not None:
                touched.add(source_of_cached_bytecode(relative))
    entries = directory_entries(files)
    # Retain missing paths so their creation selects the suite. Ignore existing
    # untracked ignored paths, directory opens, git internals and bytecode caches.
    looked_for = {}
    for path in sorted(probed | (touched - files)):
        if path in files or path in entries:
            if path in probed:
                looked_for[path] = True
        elif (not inside_git_directory(path) and "__pycache__" not in path.split("/")
              and not os.path.lexists(top / path)):
            looked_for[path] = False
    return {
        "format": RECORDED_INPUTS_FORMAT_VERSION,
        "suite": suite,
        "recorded_at": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "commit": commit,
        "exit": result["exit"],
        "seconds": result["seconds"],
        "skipped_cases": len(result["skips"]),
        "recorded_by": [PYTHON_INPUT_RECORDER_METHOD]
                       + ([STRACE_INPUT_RECORDER_METHOD] if strace_used else []),
        "reads": blob_hashes(top, sorted(touched & files)),
        "looked_for": looked_for,
        "lists": {directory: sorted(entries.get(directory, ())) for directory in sorted(listed)},
        "git_commands_on_the_checkout": sorted(git_commands),
        "git_calls_run_from_the_checkout": [git_calls[key] for key in sorted(git_calls)],
        "files_fingerprint": file_list_fingerprint(files),
    }


def recordings_directory_for(given, top):
    # Key by root commit so clones and worktrees share recordings.
    roots = git(top, "rev-list", "--max-parents=0", "HEAD").stdout.split()
    return Path(given).expanduser() / (min(roots)[:16] if roots else "no-commit")


def recording_file_for(recordings_dir, suite):
    return recordings_dir / (suite.replace("/", "__") + ".json")


@contextlib.contextmanager
def recording_publication_lock(recordings_dir, suite):
    """Hold a suite's publication lock, so a rename into place and a check-then-remove never interleave."""
    recordings_dir.mkdir(parents=True, exist_ok=True)
    with open(recording_file_for(recordings_dir, suite).with_suffix(".json.lock"), "a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def save_recording(recordings_dir, recording):
    recordings_dir.mkdir(parents=True, exist_ok=True)
    target = recording_file_for(recordings_dir, recording["suite"])
    # A temporary file of its own: runs in other checkouts may save this suite at the same time.
    descriptor, temporary = tempfile.mkstemp(dir=recordings_dir, prefix=target.name + ".",
                                             suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w") as written:
            written.write(json.dumps(recording, indent=1, sort_keys=True) + "\n")
        with recording_publication_lock(recordings_dir, recording["suite"]):
            os.replace(temporary, target)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def recording_file_identity(status):
    return (status.st_dev, status.st_ino, status.st_mtime_ns, status.st_size)


def load_recording_and_identity(recordings_dir, suite):
    """(recording or None, identity of the file read or None) from one open of the file."""
    try:
        with open(recording_file_for(recordings_dir, suite), "rb") as stored:
            identity = recording_file_identity(os.fstat(stored.fileno()))
            content = stored.read()
    except OSError:
        return None, None
    try:
        return json.loads(content), identity
    except ValueError:
        return None, identity


def load_recording(recordings_dir, suite):
    return load_recording_and_identity(recordings_dir, suite)[0]


def remove_recording_if_unchanged(recordings_dir, suite, identity_read):
    """Remove the suite's recording if it is still the file this run read.

    Returns "removed", or "kept" when another run saved a newer recording since."""
    target = recording_file_for(recordings_dir, suite)
    with recording_publication_lock(recordings_dir, suite):
        try:
            identity_now = recording_file_identity(os.stat(target))
        except FileNotFoundError:
            return "removed"
        if identity_now != identity_read:
            return "kept"
        target.unlink()
        return "removed"


def suites_longest_recorded_first(suites, recordings):
    """Return the suites in starting order: no usable duration first, then longest first."""
    def starting_order(suite):
        recording = recordings.get(suite)
        # A run that did not pass may have stopped early, so its seconds may understate the suite.
        if not isinstance(recording, dict) or recording.get("exit") != 0:
            return (0, 0.0)
        seconds = recording.get("seconds")
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
            return (0, 0.0)
        return (1, -seconds)
    # sorted is stable, so ties keep the order git listed the suites in.
    return sorted(suites, key=starting_order)


def resolved_commit(top, given):
    answer = git(top, "rev-parse", "--verify", "--quiet", f"{given}^{{commit}}")
    if answer.returncode != 0 or not answer.stdout.strip():
        raise CouldNotRun(
            f"{PROGRAM}: not run — git cannot resolve {given} to a commit in {top}.\n"
            f"Pass --only-suites-whose-recorded-inputs-changed-since a commit this "
            f"checkout has, such as the output of `git merge-base HEAD origin/main`.")
    return answer.stdout.strip()


def files_that_differ_since(top, commit):
    """Return path-to-A/M/D changes, including nonignored untracked files as additions."""
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


class CheckoutComparedWithCommit:
    """Checkout and commit facts used to compare recorded suite inputs."""

    def __init__(self, top, commit, differ, recordings):
        self.differ = differ
        self.files_then = files_at_commit(top, commit)
        self.files_now = checkout_files(top)
        self.entries_then = directory_entries(self.files_then)
        self.entries_now = directory_entries(self.files_now)
        self.fingerprint_now = file_list_fingerprint(self.files_now)
        read = set()
        for recording in recordings:
            if isinstance(recording, dict) and recording.get("format") == \
                    RECORDED_INPUTS_FORMAT_VERSION:
                read.update(recording["reads"])
        self.hashes_now = blob_hashes(top, sorted(read & self.files_now))

    def there_then(self, path):
        return path in self.files_then or path in self.entries_then

    def there_now(self, path):
        return path in self.files_now or path in self.entries_now


def added_or_deleted_name(before, after):
    name = sorted(before ^ after)[0]
    return name, "added" if name in after else "deleted"


def selection_reason(suite, recording, checkout, commit):
    """Return (selected, reason) for one suite."""
    # Recordings are shared across branches; compare both against COMMIT and the recording.
    short, differ = commit[:12], checkout.differ
    if recording is None:
        return True, "no recording of its inputs on this machine yet"
    if not isinstance(recording, dict) \
            or recording.get("format") != RECORDED_INPUTS_FORMAT_VERSION:
        return True, "its recording was made by an older version of this program"
    exit_code = recording.get("exit")
    if exit_code != 0:
        # An unsuccessful run recorded only the inputs reached before it stopped.
        return True, ("its last recorded run did not pass: "
                      + (describe_exit(exit_code) if isinstance(exit_code, int)
                         else "no exit code recorded"))
    skipped = recording.get("skipped_cases")
    counted = isinstance(skipped, int) and not isinstance(skipped, bool)
    if not counted or skipped != 0:
        # A skipped case's reads were never recorded, and a skip can hide a run disturbed by another.
        return True, ("its last recorded run skipped "
                      + (f"{skipped} case(s)" if counted else "an unrecorded number of cases")
                      + ", so it recorded only what the cases that ran read")
    if suite in differ:
        return True, "the suite itself differs"
    reads, looked_for = recording["reads"], recording["looked_for"]
    lists, git_commands = recording["lists"], recording["git_commands_on_the_checkout"]

    changed_reads = [path for path in reads if path in differ]
    if changed_reads:
        more = f" and {len(changed_reads) - 1} more" if len(changed_reads) > 1 else ""
        return True, f"it reads {changed_reads[0]}, which differs{more}"
    for path in looked_for:
        if checkout.there_then(path) != checkout.there_now(path):
            verb = "added" if checkout.there_now(path) else "deleted"
            return True, f"it looks for {path}, which was {verb}"
    for directory in lists:
        before = checkout.entries_then.get(directory, set())
        after = checkout.entries_now.get(directory, set())
        if before != after:
            name, verb = added_or_deleted_name(before, after)
            path = f"{directory}/{name}" if directory else name
            return True, f"it lists {directory or '.'}/, where {path} was {verb}"
    added_or_deleted = sorted(path for path, status in differ.items() if status in "AD")
    if git_commands and added_or_deleted:
        path = added_or_deleted[0]
        verb = "added" if differ[path] == "A" else "deleted"
        return True, (f"it runs git {', '.join(git_commands)} on the checkout, "
                      f"and {path} was {verb}")
    reading = sorted(set(git_commands) - GIT_COMMANDS_THAT_ONLY_LIST)
    if reading and differ:
        return True, (f"it runs git {', '.join(reading)} on the checkout, which reads "
                      f"files no recorder here saw, and {sorted(differ)[0]} differs")

    stale = [path for path, blob in reads.items()
             if checkout.hashes_now.get(path, "not in the checkout") != blob]
    if stale:
        more = f" and {len(stale) - 1} more" if len(stale) > 1 else ""
        return True, (f"its recording read another copy of {stale[0]}{more} than the "
                      f"checkout holds, so what it reads here is unknown")
    for path, there in looked_for.items():
        if checkout.there_now(path) != there:
            return True, (f"its recording looked for {path} where it was "
                          f"{'there' if there else 'absent'}, and in the checkout it is not")
    for directory, recorded in lists.items():
        after = checkout.entries_now.get(directory, set())
        if set(recorded) != after:
            name, _ = added_or_deleted_name(set(recorded), after)
            return True, (f"its recording listed {directory or '.'}/ with other entries "
                          f"than the checkout's, {name} among them")
    if git_commands and recording.get("files_fingerprint") != checkout.fingerprint_now:
        return True, (f"it runs git {', '.join(git_commands)} on the checkout, and its "
                      f"recording was made on another set of files")
    reason = f"none of the {len(reads)} files it read differs since {short}"
    calls = recording.get("git_calls_run_from_the_checkout", [])
    if calls and all(call["reads"] != GIT_CALL_READS_THE_CHECKOUT for call in calls):
        sees_no_file, another_repository = set(), set()
        for call in calls:
            _, command, arguments = git_call_global_options_command_and_arguments(
                call["arguments"])
            if call["reads"] == GIT_CALL_SEES_NO_FILE:
                sees_no_file.add(" ".join(["git", command, *arguments]))
            elif call["reads"] == GIT_CALL_RUNS_ON_ANOTHER_REPOSITORY:
                another_repository.add("git " + command
                                       + (" list" if command == "worktree" else ""))
        groups = []
        if sees_no_file:
            verb = "sees" if len(sees_no_file) == 1 else "see"
            groups.append(f"{', '.join(sorted(sees_no_file))} {verb} no file")
        if another_repository:
            verb = "runs" if len(another_repository) == 1 else "run"
            groups.append(f"{', '.join(sorted(another_repository))} {verb} on another repository")
        reason += ", and its git calls read no file of the checkout: " + "; ".join(groups)
    return False, reason


def suites_selected_since(top, suites, recordings, commit):
    """[(suite, selected, why)] for every suite, in order."""
    differ = files_that_differ_since(top, commit)
    everything = [path for path in sorted(differ)
                  if any(path == prefix or (prefix.endswith("/") and path.startswith(prefix))
                         for prefix in EVERY_SUITE_RUNS_WHEN_THESE_CHANGE)]
    if everything:
        return [(suite, True, f"{everything[0]} differs, and every suite runs under it")
                for suite in suites]
    recorded = [recordings.get(suite) for suite in suites]
    checkout = CheckoutComparedWithCommit(top, commit, differ, recorded)
    return [(suite, *selection_reason(suite, recordings.get(suite), checkout, commit))
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
        prog=PROGRAM, description="Run every *-test.py and *-test.sh suite git lists in a checkout.")
    parser.add_argument("--checkout", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("-j", dest="jobs", type=int)
    parser.add_argument("--log-dir")
    parser.add_argument("--lock-file", default=str(DEFAULT_LOCK_FILE))
    parser.add_argument("--only-suites-whose-recorded-inputs-changed-since",
                        dest="changed_since", metavar="COMMIT")
    parser.add_argument("--recorded-inputs-directory",
                        default=str(DEFAULT_RECORDED_INPUTS_DIRECTORY))
    arguments = parser.parse_args(argv)
    if arguments.jobs is not None and arguments.jobs < 1:
        parser.error("-j takes a whole number of at least 1")
    return arguments


def suites_run_at_once(jobs_given, suites_to_run, cores):
    """-j as given; otherwise one suite per core, never more than the suites to run."""
    if jobs_given is not None:
        return jobs_given
    # At least 1: the thread pool refuses zero workers when nothing is selected.
    return max(1, min(cores or SUITES_RUN_AT_ONCE_WHEN_CORE_COUNT_UNKNOWN, suites_to_run))


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
    try:
        sandbox_prefix, unconfined_because = signal_sandbox()
    except SignalSandboxCouldNotStart as error:
        print(signal_sandbox_refusal(error), file=sys.stderr)
        return EXIT_COULD_NOT_RUN

    lock_handle, holder, previous_holder = take_machine_lock(Path(arguments.lock_file), top)
    if lock_handle is None:
        print(f"{PROGRAM}: not run — another run holds {arguments.lock_file}: {holder}.\n"
              f"Run this again after that run has finished.", file=sys.stderr)
        return EXIT_LOCKED

    log_dir_handle = run_record = None
    try:
        if arguments.log_dir:
            log_dir = Path(arguments.log_dir).resolve()
            log_dir.mkdir(parents=True, exist_ok=True)
            log_dir_handle = lock_explicit_log_directory(log_dir)
            if log_dir_handle is None:
                print(f"{PROGRAM}: not run — another run is writing to the log directory "
                      f"{log_dir}.\nRun this again with another --log-dir, or after that "
                      f"run has finished.", file=sys.stderr)
                return EXIT_LOCKED
        else:
            log_dir = Path(tempfile.mkdtemp(prefix=f"{PROGRAM}-"))
        if sys.platform.startswith("linux"):
            run_record = RunRecord(run_records_directory_for_lock_file(arguments.lock_file), log_dir,
                                   log_dir_is_temporary=not arguments.log_dir)
        name_log_directory_in_lock(lock_handle, log_dir)
        clean_up_lines = clean_up_after_earlier_runs(Path(arguments.lock_file), previous_holder)
        commit, state = commit_and_state(top)
        recordings_dir = recordings_directory_for(arguments.recorded_inputs_directory, top)
        # Each recording is read once, so selection and starting order see the same one
        # even while runs in other checkouts save it.
        recordings, identities_read = {}, {}
        for suite in suites:
            recordings[suite], identities_read[suite] = load_recording_and_identity(
                recordings_dir, suite)
        try:
            files = checkout_files(top)
            if changed_since is not None:
                selection = suites_selected_since(top, suites, recordings, changed_since)
            else:
                selection = [(suite, True, "every suite runs without "
                              "--only-suites-whose-recorded-inputs-changed-since")
                             for suite in suites]
        except CouldNotRun as refusal:
            print(refusal, file=sys.stderr)
            return EXIT_COULD_NOT_RUN
        chosen = suites_longest_recorded_first(
            [suite for suite, selected, _ in selection if selected], recordings)
        jobs = suites_run_at_once(arguments.jobs, len(chosen), os.cpu_count())
        strace = strace_usable()
        recording_dir = log_dir / "recorded-inputs"
        recording_dir.mkdir(parents=True, exist_ok=True)
        recorder = (install_python_input_recorder(log_dir), recording_dir, strace)
        report = Report(log_dir / REPORT_FILE_NAME)
        selected_note = (f"; {len(chosen)} selected by inputs changed since "
                         f"{changed_since[:12]}" if changed_since is not None else "")
        report.line(f"{PROGRAM}: {top} at {commit} ({state}); {len(suites)} suites "
                    f"listed by git{selected_note}; {version} ({interpreter}); "
                    f"-j {jobs}; logs in {log_dir}")
        report.line(f"inputs recorded by {PYTHON_INPUT_RECORDER_METHOD}"
                    + (f" and {STRACE_INPUT_RECORDER_METHOD} ({strace})" if strace else "")
                    + f", kept in {recordings_dir}")
        report.line(signal_sandbox_line(sandbox_prefix, unconfined_because))
        if sandbox_prefix:
            for suite in chosen:
                if suite in SUITES_RUN_OUTSIDE_THE_SIGNAL_SANDBOX:
                    report.line(f"{suite} runs WITHOUT the signal sandbox: "
                                f"{SUITES_RUN_OUTSIDE_THE_SIGNAL_SANDBOX[suite]}")
        for line in clean_up_lines:
            report.line(line)
        note_suite_process = run_record.note_suite_process if run_record else None
        if changed_since is not None:
            for suite, selected, why in selection:
                report.line(f"{'SELECTED' if selected else 'NOT SELECTED'} {suite}: {why}")

        def run_and_record(suite):
            if is_shell_test_suite(suite):
                return run_one_suite(top, interpreter, suite, log_dir,
                                     sandbox_prefix=sandbox_prefix,
                                     note_suite_process=note_suite_process)
            result = run_one_suite(top, interpreter, suite, log_dir, recorder,
                                   sandbox_prefix=sandbox_prefix,
                                   note_suite_process=note_suite_process)
            try:
                save_recording(recordings_dir, recording_of(
                    top, suite, result, recording_dir, files, commit, strace is not None))
            except OSError as error:
                # A failed save must not leave the previous run's recording usable; one
                # another run saved meanwhile records that run's own inputs, so it stays.
                earlier = recording_file_for(recordings_dir, suite)
                try:
                    outcome = remove_recording_if_unchanged(
                        recordings_dir, suite, identities_read.get(suite))
                except OSError as removal_error:
                    report.line(f"inputs of {suite} not recorded: {error}. Its earlier "
                                f"recording could not be removed either: {removal_error}. "
                                f"Delete {earlier} before the next run with "
                                f"--only-suites-whose-recorded-inputs-changed-since.")
                else:
                    if outcome == "kept":
                        report.line(f"inputs of {suite} not recorded: {error}. The recording "
                                    f"another run saved while this one ran is kept, since it "
                                    f"records that run's own inputs.")
                    else:
                        report.line(f"inputs of {suite} not recorded: {error}. Its earlier "
                                    f"recording is removed, so the next run with "
                                    f"--only-suites-whose-recorded-inputs-changed-since "
                                    f"selects it.")
            # Raw strace logs can occupy hundreds of megabytes per suite.
            shutil.rmtree(recording_paths_for(recording_dir, suite)[1], ignore_errors=True)
            return result

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
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
        if run_record is not None:
            run_record.finish()
        return EXIT_SOME_FAILED if failed else EXIT_ALL_PASSED
    finally:
        if log_dir_handle is not None:
            log_dir_handle.close()
        lock_handle.close()


if __name__ == "__main__":
    sys.exit(main())
