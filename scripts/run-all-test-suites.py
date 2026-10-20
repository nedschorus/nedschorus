#!/usr/bin/env python3
"""Run every test suite in a checkout, and report each one by its exit code.

Usage:
  scripts/run-all-test-suites.py [--checkout DIR] [--python INTERPRETER]
                                 [-j N] [--log-dir DIR] [--lock-file PATH]
                                 [--wait-for-lock-seconds N]
                                 [--only-suites-whose-recorded-inputs-changed-since COMMIT]
                                 [--recorded-inputs-directory DIR]

  --checkout    the top directory of the checkout to test; default, the
                checkout this file is in
  --python      the interpreter that runs each suite file; default, the one
                running this program
  -j            how many suites of this run may run at once; default, on Linux
                in test sandboxes, every suite to run, up to admission's
                ceiling, and otherwise the machine's core count, or the number
                of suites to run when that is fewer
  --log-dir     where each suite's output and the report are written;
                default, a new directory under the system temp directory,
                removed two days after its run ends. Two runs cannot share
                one --log-dir: the second exits 3
  --lock-file   default ~/.claude/.run-all-test-suites.lock. Where each suite
                runs in a test sandbox (Linux with bwrap), no lock is taken: the
                run records and the admission directory beside this path are
                shared by every run that names it. Elsewhere (macOS, or Linux
                without bwrap), the lock that keeps two runs on one machine apart
  --wait-for-lock-seconds N
                where the lock is taken, wait up to N seconds for it, in the
                kernel's queue as `flock -w` waits, before exiting 3; default 0,
                no wait. Accepted and without effect where no lock is taken
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

EACH SUITE RUNS IN A SIGNAL SANDBOX on Linux: bwrap with
TEST_SANDBOX_BWRAP_ARGUMENTS_SHARED_BY_EVERY_SUITE, so the suite and everything it starts sit in a
PID namespace of their own. The suite runs as the same user, so a signal a
suite sends can reach only the processes it started, never the agent-seats
that run as the same account.

THE SIGNAL SANDBOX IS ALSO EACH SUITE'S TEST SANDBOX, built when the
suite starts and gone when it ends. It hides by default, because a list of
files or sockets to cover misses every one not on it and every one made after
the list. The file system is read-only, except: a private /tmp, which TMPDIR
and TMUX_TMPDIR name, so no tmux server or socket of an agent-seat is
reachable; a private /dev and System V IPC; the home directory, an empty
tmpfs the suite may write, into which only the paths in
TEST_SANDBOX_HOME_PATHS_SHOWN_READ_ONLY are bound, read-only, each with the
reason suites need it, so no credential in the home directory is there; the
checkout under test, a copy-on-write overlay the suite may write, so nothing
it writes there survives the suite;
and the suite's own input record and strace traces, which this program reads
after the suite ends. An interpreter given with --python from inside the home
directory is shown read-only too. The directories in
TEST_SANDBOX_FIXED_DIRECTORIES_HIDDEN_BY_EMPTY_TMPFS, such as /mnt, where the
backup drive holds copies of the home directory, are empty tmpfs, and so is
every other directory this account can create a file in, such as /var/tmp,
found by one scan of the machine per process: a socket or file a process
outside makes there after the suite starts is never visible inside. The run's
log directory, where this program writes, is out of the suite's reach, and
the input recorder is shown read-only; this program writes and reads the
files there without following a symbolic link. The checkout's git common
directory is bound read-only above the checkout, since every worktree of the
repository shares it, and so is a linked worktree's .git file, which names
the git directory every later git command in the checkout uses; when the
common directory cannot be found, the run stops with exit 2. No variable
that TEST_SUITE_CREDENTIAL_ENVIRONMENT_VARIABLE_PATTERNS matches reaches a
suite. /run is an empty tmpfs: it holds the machine's sockets, Docker's and
the system bus among them, and the session's runtime directory, with the
D-Bus session bus, through which `systemd-run --user` would start processes
outside the sandbox, and the sockets of the running agent-sessions. A
read-only mount does not stop a connection to a socket, so a listening Unix
socket still visible after that, made by a service in a directory this
account cannot write, is hidden with its whole directory, so one the service
makes there again stays hidden; one directly in a system directory such as
/var is covered by an empty file. The variables in
TEST_SANDBOX_OUTSIDE_SOCKET_VARIABLES, which name sockets
outside, are unset. The suite gets a network of its own, holding only loopback, so it
reaches no port and no abstract Unix socket outside, the X server's included;
a suite in SUITES_WHOSE_TEST_SANDBOX_SHARES_THE_MACHINE_NETWORK keeps the
machine's network, for the reason listed there.
scripts/run-all-test-suites-test-sandbox-escape-test.py tries
each escape and fails if one works. bwrap also gives the suite a user namespace of its own, in which
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
cannot start, or lets that signal through. A run started
inside the sandbox, such as one a suite of this program starts, does not
start another: bwrap cannot start inside bwrap, and its suites are already
confined. The suites listed in SUITES_RUN_WITHOUT_ANY_SANDBOX cannot
work inside it and run unconfined, each named in the report with the reason.
Three dicts say which sandbox a suite gets, each mapping a suite's path to the
reason it gets that sandbox: SUITES_RUN_WITHOUT_ANY_SANDBOX,
SUITES_GIVEN_A_COPY_ON_WRITE_OVERLAY_OF_THE_REPOSITORY_GIT_DIRECTORY (suites
whose sandbox gets a writable copy-on-write overlay of the repository's git
directory) and SUITES_WHOSE_TEST_SANDBOX_SHARES_THE_MACHINE_NETWORK (suites
whose sandbox keeps the machine's network). The three are read from the
scripts/run-all-test-suites.py of the checkout whose suites the run tests,
parsed and never run, and from this file only when that checkout has none;
the report names the file. A run refuses, exit 2, when that file does not
assign each of the three a literal dict.
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
GIT_REDIRECTING_ENVIRONMENT_VARIABLES from the module this file reads it
from, nc-systems/general-tools/git-redirecting-environment-variables-removal-common.py, and
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
A suite marks a skip whose cause is the machine itself, its platform or what
is installed on it, by putting SKIPPED_CASE_THIS_MACHINE_CANNOT_RUN_MARKER,
`[this machine cannot run it]`, right after `SKIP` and its spaces:
`SKIP  [this machine cannot run it] <case>: <reason>`. A marked skip is
counted and printed like any other; it only changes selection, below.

RUNS THAT OVERLAP, AND ONE RUN AT A TIME WITHOUT TEST SANDBOXES. Measured
2026-09-21: two overlapping runs of scripts/resupervise-seat-test.py both exit
0 and both print "all cases passed" while silently dropping cases to SKIP,
because the suites share machine state. On Linux with bwrap each suite runs in
a test sandbox of its own (see THE SIGNAL SANDBOX IS ALSO EACH SUITE'S TEST SANDBOX above), which shares no /tmp, tmux
directory or home directory writes with any other suite, so runs overlap
freely and no lock is taken; ADMISSION below decides when each suite starts.
Where suites do not run in test sandboxes, a run takes an exclusive lock on
--lock-file, and a second run on the same machine exits 3 without running
anything, or, with --wait-for-lock-seconds, waits for the lock first. A wait blocks in the
kernel's queue: a caller that instead retried every few seconds lost the lock
to every `flock -w` waiter on it and never ran. The lock file names its
holder (process id, checkout, start time), and the refusal prints it, unless
that process has ended.

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

ADMISSION, on Linux in test sandboxes.
Every run on the machine shares one admission, kept in the directory beside
--lock-file. A suite starts only while the machine's CPU use averaged over the
last 5 s is under 50% and its available memory is above 10 GB, read with
psutil; at most 4 suites start per second and at most 64 run at once on the
machine, each holding an flock on one of 64 slot files, so the kernel frees
the slot of a killed run. A suite run without any sandbox first takes the
lock those suites share, then a slot, so it never holds a slot while it waits.
A suite that cannot start waits with no time limit, and once a minute the run
reports what its suites wait for. A failure to decide, such as a machine
reading that fails or a slot file that cannot be opened, stops the run with
exit 2. Every suite runs at nice 10, in a cgroup scope of its own
(`systemd-run --user --scope`), whose counters give the suite's CPU seconds
and peak memory, every process it starts included. The
run records the machine's CPU use, available memory and load every second in
machine-cpu-and-memory-readings.tsv in its log directory, each suite's kind, admission wait,
CPU seconds and peak memory in test-suite-resource-use.tsv, each case line's time in
test-case-times.tsv, and all of it as JUnit XML in junit.xml. Every failing
case is added to test-case-failure-history.jsonl in
--recorded-inputs-directory, with its commit and branch.

CONCURRENCY. -j N runs N suites at once. The default is the machine's core
count (4 when Python cannot tell), or the number of suites to run when that
is fewer. Suites start longest first, by the seconds their recordings
kept, ties in the order git lists them; a suite with no recording, or whose
recorded run did not pass, starts before them all, since it may be long. A
run lasts at least as long as its longest suite, and a suite slows when the
machine is busy, so more jobs pay off only once no single suite dominates.
-j 1 still runs one suite at a time when a run must.

PER-SUITE TIMEOUT. Each suite has a time limit, counted from its start, after
admission: max(TEST_SUITE_TIMEOUT_FLOOR_SECONDS, 600, and
TEST_SUITE_TIMEOUT_MULTIPLE_OF_RECORDED_SECONDS, 4, times the seconds of its
last passing recording, the one the starting order reads). A suite with no
passing recording gets TEST_SUITE_TIMEOUT_WITHOUT_PASSING_RECORDING_SECONDS,
1800. Measured over 257 runs on ned-box, 21,701 passing suite runs: a suite
ran at most 3.3 times its fastest pass when that pass took 20 s or more, while
a fast suite can spike far past any multiple
(scripts/run-suite-in-signal-sandbox-test.py passed in 10.8 s and in 297 s),
which the floor covers; no pass exceeded this limit measured from the suite's
fastest pass. 1800 s is six times the longest pass seen. A suite past its limit
has its process group killed with SIGKILL; each suite starts in a session of
its own, so the group holds every process it started except one that starts a
session of its own. In a test sandbox the group holds the init of the suite's
PID namespace, whose end ends every process inside, so nothing is left; outside
one, such a process is not reached. It is reported FAIL with `TIMEOUT after
<n>s (limit <m>s, <k> times recorded <r>s)`, `(limit <m>s, the floor, more than
<k> times recorded <r>s)` or `(limit <m>s from no passing recording)`; its
cgroup counters are lost with the shell that keeps them, and the other suites
run on. Its recording keeps the kill's exit, so the next run starts it first,
under the limit for no passing recording.

A STOPPED RUN KILLS ITS SUITES. Since each suite runs in a session of its own,
a signal sent to the runner's process group no longer reaches them. So once its
suites start, the runner handles SIGTERM, SIGHUP and SIGINT: it kills every
running suite as a timeout does, starts no other, prints a line naming the
signal, and exits 2; a signal that comes after the last suite ended stops
nothing, and the run is reported as usual. A signal the runner was started
with ignored, as SIGHUP is under nohup and SIGINT is for a command put in the
background in a subshell, stops nothing: it gets a handler that does nothing.
Since the handlers are set before the first suite starts, and a handled signal
is reset to its default action when a suite's process is started, every suite
starts with the default action for these three signals either way. The stop
handler only records the signal; each suite's thread and the loop collecting results act on it within
RUN_STOP_SIGNAL_CHECK_SECONDS.
A runner killed with SIGKILL cannot do this: its suites in bwrap still die with
it, and a suite outside bwrap outlives it.

OUTPUT. A first line naming the checkout, its commit, whether tracked files
differ from that commit, the suite count, the interpreter's own --version
answer and path, -j, and the log directory. Then one line per suite as it
finishes: `PASS <path> (<seconds>s)` or `FAIL <path> exit <code>
(<seconds>s)`, with `, <n> skipped` when it printed SKIP lines. Then the
failed suites again, each with its log, and every SKIP line, each with its
suite, so the end of the output holds everything needed. The last line
opens `SUMMARY:` and carries the counts. The whole report is also written to
test-run-report.txt in the log directory, so a run in the background needs no
pipe to keep it.

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
skipped a case without the mark `[this machine cannot run it]`, since the
cases skipped recorded nothing, and a skip can be a run disturbed by
another (a marked case never runs on this machine, so what it would read
does not matter here); the suite file itself
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
holds the lock, where a lock is taken.
"""

import argparse
import ast
import codecs
import collections
import concurrent.futures
import contextlib
import datetime
import fcntl
import fnmatch
import functools
import hashlib
import importlib.util
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
import xml.etree.ElementTree
from pathlib import Path

PROGRAM = "run-all-test-suites"

TEST_SUITE_PATHSPEC = "*-test.py"
# Python audit hooks cannot see shell reads; without strace, a shell recording
# would miss inputs. Leave shell suites unrecorded so selection always runs them.
SHELL_TEST_SUITE_PATHSPEC = "*-test.sh"
SKIPPED_CASE_LINE = re.compile(r"^SKIP\s")
SKIPPED_CASE_THIS_MACHINE_CANNOT_RUN_MARKER = "[this machine cannot run it]"
SKIPPED_CASE_LINE_THIS_MACHINE_CANNOT_RUN = re.compile(
    r"^SKIP\s+" + re.escape(SKIPPED_CASE_THIS_MACHINE_CANNOT_RUN_MARKER))

# Git redirection variables can send scratch-repository writes into a live repository.
# The list is the shared module's; programs that load this runner read it here too.
_git_redirecting_removal_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_variables_removal_common",
    Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
    / "git-redirecting-environment-variables-removal-common.py")
git_redirecting_removal = importlib.util.module_from_spec(_git_redirecting_removal_spec)
_git_redirecting_removal_spec.loader.exec_module(git_redirecting_removal)
GIT_REDIRECTING_ENVIRONMENT_VARIABLES = git_redirecting_removal.GIT_REDIRECTING_ENVIRONMENT_VARIABLES

# Whether a user attends the agent-session changes what some messages under test say, so a suite
# is launched without them and each test sets them itself.
AGENT_SESSION_ATTENDANCE_ENVIRONMENT_VARIABLES = (
    "CLAUDE_CODE_SESSION_ATTENDED",
    "NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER",
)

# Suites run as the same account as every agent-seat, so a stray kill(-1) or
# killpg from a suite reaches all of them. In its own PID namespace a suite can
# signal only the processes it started. Children of bwrap cannot start bwrap
# again (Ubuntu's AppArmor profile denies them capabilities), so a run inside
# the sandbox, such as a suite that tests this program, runs its suites as they
# are: they are already inside.
#
# On Linux, each suite's test sandbox is these signal-sandbox arguments, shared by every
# suite, plus the per-suite arguments of bwrap_arguments_for_one_suites_test_sandbox();
# on macOS the signal sandbox is sandbox-exec alone and there is no test sandbox. The
# test sandbox hides by default: the
# file system read-only, a private /tmp, /dev and System V IPC, the home directory an
# empty tmpfs into which only the paths in TEST_SANDBOX_HOME_PATHS_SHOWN_READ_ONLY are
# bound, and /run hidden, since it holds the machine's sockets: Docker's, the system bus,
# and in the session's runtime directory the D-Bus session bus, through which
# `systemd-run --user` starts processes outside the sandbox, and the sockets of the
# running agent-sessions. A Unix socket accepts a connection through a read-only mount,
# so hiding it is the only protection, and a list of files to cover misses every file
# not on it, so whole directories are hidden instead.
# bwrap_arguments_for_one_suites_test_sandbox() adds, per suite, the paths the suite may
# write for real and every other directory this account can create a file in.
REAL_HOME_DIRECTORY_PATH_HIDDEN_BY_EMPTY_TMPFS_IN_TEST_SANDBOX = str(Path.home())
# Relative to the home directory: the only paths of it a suite sees, each read-only, with
# why suites need it. Nothing else of the home directory is there, credentials included.
TEST_SANDBOX_HOME_PATHS_SHOWN_READ_ONLY = {
    ".local/lib": "the Python libraries pip installs for this account, tree-sitter and "
                  "coverage among them, which suites import",
    ".local/bin/ruff": "the Ruff binary pip installs for this account, which `python3 -m ruff` "
                       "looks for here",
    ".gitconfig": "git's settings for this account, which suites that run git read",
    "nedschorus-logs/seats/ned-box-helper/absence-claim-trigger-phrases-2026-10-05/out/"
    "precision/labels.csv": "the labelled replies scripts/absence-claim-locator-reminder-"
                            "hook-test.py measures the reminder's precision against",
}
# Directories hidden whole, with why: each holds what no suite needs and a scan for
# writable directories should not walk.
TEST_SANDBOX_FIXED_DIRECTORIES_HIDDEN_BY_EMPTY_TMPFS = {
    "/mnt": "mounted file systems such as the backup drive, whose snapshots hold copies "
            "of the home directory, credentials included",
    "/media": "removable media",
    "/var/snap": "snap services' data and listening sockets, which a snap refresh "
                 "re-creates under a new directory",
}
XDG_RUNTIME_DIRECTORY_PATH_HIDDEN_BY_EMPTY_TMPFS_IN_TEST_SANDBOX = f"/run/user/{os.getuid()}"
# Variables naming a socket or a server outside the test sandbox.
TEST_SANDBOX_OUTSIDE_SOCKET_VARIABLES = (
    "TMUX",
    "TMUX_PANE",
    "DBUS_SESSION_BUS_ADDRESS",
    "SSH_AUTH_SOCK",
    "CLAUDE_CODE_MESSAGING_SOCKET",
    "DISPLAY",
    "WAYLAND_DISPLAY",
    "GPG_AGENT_INFO",
)
# Environment variables that carry a credential; no suite is given one. Matched against
# the variable's name in capitals.
TEST_SUITE_CREDENTIAL_ENVIRONMENT_VARIABLE_PATTERNS = (
    "*_TOKEN", "*_TOKEN_*", "*_API_KEY", "*_SECRET", "*_SECRET_*", "*PASSWORD*",
    "*_CREDENTIALS",
)
TEST_SANDBOX_BWRAP_ARGUMENTS_SHARED_BY_EVERY_SUITE = (
    "--ro-bind", "/", "/", "--dev", "/dev", "--tmpfs", "/dev/shm", "--proc", "/proc",
    "--tmpfs", "/tmp", "--tmpfs", "/run",
    *(("--tmpfs", XDG_RUNTIME_DIRECTORY_PATH_HIDDEN_BY_EMPTY_TMPFS_IN_TEST_SANDBOX,
       "--setenv", "XDG_RUNTIME_DIR", XDG_RUNTIME_DIRECTORY_PATH_HIDDEN_BY_EMPTY_TMPFS_IN_TEST_SANDBOX)
      if os.path.isdir(XDG_RUNTIME_DIRECTORY_PATH_HIDDEN_BY_EMPTY_TMPFS_IN_TEST_SANDBOX)
      else ("--unsetenv", "XDG_RUNTIME_DIR")),
    "--tmpfs", REAL_HOME_DIRECTORY_PATH_HIDDEN_BY_EMPTY_TMPFS_IN_TEST_SANDBOX,
    *(argument for relative in TEST_SANDBOX_HOME_PATHS_SHOWN_READ_ONLY
      for argument in ("--ro-bind-try",
                       os.path.join(REAL_HOME_DIRECTORY_PATH_HIDDEN_BY_EMPTY_TMPFS_IN_TEST_SANDBOX, relative),
                       os.path.join(REAL_HOME_DIRECTORY_PATH_HIDDEN_BY_EMPTY_TMPFS_IN_TEST_SANDBOX, relative))),
    *(argument for directory in TEST_SANDBOX_FIXED_DIRECTORIES_HIDDEN_BY_EMPTY_TMPFS
      if os.path.isdir(directory) for argument in ("--tmpfs", directory)),
    "--unshare-pid", "--unshare-ipc", "--die-with-parent",
    "--setenv", "TMPDIR", "/tmp", "--setenv", "TMUX_TMPDIR", "/tmp",
    *(argument for variable in TEST_SANDBOX_OUTSIDE_SOCKET_VARIABLES
      for argument in ("--unsetenv", variable)))
SIGNAL_SANDBOX_INSIDE_VARIABLE = "RUN_ALL_TEST_SUITES_INSIDE_SIGNAL_SANDBOX"
SIGNAL_SANDBOX_START_TIMEOUT_SECONDS = 60
# The profile the user's Mac run of the check passed on 2026-10-08 (macOS 26.6.2).
# macOS refuses to exec a setuid program such as /bin/ps inside sandbox-exec, so
# ps runs outside the sandbox; ps sends no signals.
SIGNAL_SANDBOX_MACOS_SANDBOX_EXEC = "/usr/bin/sandbox-exec"
SIGNAL_SANDBOX_MACOS_PROFILE = (
    "(version 1)(allow default)(deny signal)(allow signal (target same-sandbox))"
    '(allow process-exec (literal "/bin/ps") (with no-sandbox))')
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
SUITES_RUN_WITHOUT_ANY_SANDBOX = {
    "nc-systems/cold-read/tests/cold-read-agy-cell-test.py":
        "it starts the agy cell's own bwrap, which cannot start inside bwrap",
    "nc-systems/cold-read/tests/cold-read-fast-read-test.py":
        "it starts the agy cell's own bwrap, which cannot start inside bwrap",
    "scripts/run-all-test-suites-cleanup-after-killed-runs-real-process-test.py":
        "it starts this program, whose suites run in bwrap, which cannot start inside bwrap",
    "scripts/run-all-test-suites-test-sandbox-escape-test.py":
        "it builds test sandboxes itself with bwrap, which cannot start inside bwrap",
    "scripts/run-all-test-suites-overlapping-runs-real-process-test.py":
        "it starts this program, whose suites run in bwrap, which cannot start inside bwrap",
    "scripts/mac-request-from-ned-box-forced-command-test.py":
        "it runs the real ssh, which refuses its root-owned config files because "
        "inside the sandbox's user namespace they show as owned by nobody",
}

# Suites that must write the git directory of the repository under test, such as with
# `git worktree add`. Their git directory is a copy-on-write overlay instead of read-only,
# so the writes work inside the suite and vanish when it ends.
SUITES_GIVEN_A_COPY_ON_WRITE_OVERLAY_OF_THE_REPOSITORY_GIT_DIRECTORY = {
    "nc-systems/general-tools/tests/bash-guards-verdict-changes-between-two-git-refs-on-transcript-recorded-commands-check-test.py":
        "it replays at two refs, each in a worktree it adds to this repository",
}

# Suites whose test sandbox keeps the machine's network, each with its reason. Every
# other suite's test sandbox has a network of its own with only loopback, so no
# suite reaches a port or an abstract Unix socket (such as the X server's) outside it.
SUITES_WHOSE_TEST_SANDBOX_SHARES_THE_MACHINE_NETWORK = {}

# A run uses the checkout under test's own copies of these lists, not the ones above,
# whenever the checkout has a scripts/run-all-test-suites.py.
SUITE_SANDBOX_LIST_NAMES_READ_FROM_CHECKOUT_UNDER_TEST = (
    "SUITES_RUN_WITHOUT_ANY_SANDBOX",
    "SUITES_GIVEN_A_COPY_ON_WRITE_OVERLAY_OF_THE_REPOSITORY_GIT_DIRECTORY",
    "SUITES_WHOSE_TEST_SANDBOX_SHARES_THE_MACHINE_NETWORK")
SUITE_SANDBOX_LISTS_SOURCE_LINE_PREFIX = "which sandbox each suite runs in, from the lists in "
SUITE_SANDBOX_LISTS_OF_THIS_PROGRAM = {
    name: dict(globals()[name]) for name in SUITE_SANDBOX_LIST_NAMES_READ_FROM_CHECKOUT_UNDER_TEST}

# Admission, shared by every run on this machine: a suite starts only while the
# machine has room for it. The run records the machine's readings every second
# (MACHINE_CPU_AND_MEMORY_READINGS_FILE_NAME), so these thresholds can be moved from evidence.
TEST_SUITE_ADMISSION_CPU_PERCENT_BELOW = 50
TEST_SUITE_ADMISSION_CPU_AVERAGE_SECONDS = 5
TEST_SUITE_ADMISSION_AVAILABLE_MEMORY_BYTES_ABOVE = 10 * 10**9
TEST_SUITE_ADMISSION_STARTS_PER_SECOND = 4
TEST_SUITE_ADMISSION_SUITES_RUNNING_AT_ONCE_CEILING = 64
TEST_SUITE_ADMISSION_WAIT_REPORT_INTERVAL_SECONDS = 60
TEST_SUITE_ADMISSION_RETRY_SECONDS = 0.25
# Beside the lock file, so a test that passes its own lock file also gets its own admission.
TEST_SUITE_ADMISSION_DIRECTORY_SUFFIX = ".test-suite-admission"
TEST_SUITE_ADMISSION_START_TIMES_FILE_NAME = "start-times"
TEST_SUITE_ADMISSION_SLOT_FILE_PREFIX = "slot-"
# The file keeps its earlier name because runners of different versions share the lock.
SUITES_RUN_WITHOUT_ANY_SANDBOX_LOCK_FILE_NAME = "suites-run-outside-the-signal-sandbox.lock"
TEST_SUITE_NICE_INCREMENT = 10
MACHINE_READINGS_INTERVAL_SECONDS = 1
MACHINE_CPU_AND_MEMORY_READINGS_FILE_NAME = "machine-cpu-and-memory-readings.tsv"
TEST_SUITE_RESOURCE_USE_FILE_NAME = "test-suite-resource-use.tsv"
TEST_CASE_TIMES_FILE_NAME = "test-case-times.tsv"
JUNIT_XML_FILE_NAME = "junit.xml"
TEST_CASE_FAILURE_HISTORY_FILE_NAME = "test-case-failure-history.jsonl"
ADMISSION_WAITED_LINE_PREFIX = "seconds suites waited for admission: "
# The suites print one line per case opening PASS, FAIL or ok.
TEST_CASE_LINE = re.compile(r"^\s*(?P<verdict>PASS|FAIL|ok)\b:?\s*(?P<text>.*)$")
# A process a suite run without any sandbox leaves running can hold its output open.
TEST_SUITE_OUTPUT_DRAIN_SECONDS = 10
# A suite's time limit is the larger of the floor and the multiple of its last passing
# run's seconds; see PER-SUITE TIMEOUT in the docstring for why these numbers.
TEST_SUITE_TIMEOUT_FLOOR_SECONDS = 600
TEST_SUITE_TIMEOUT_MULTIPLE_OF_RECORDED_SECONDS = 4
TEST_SUITE_TIMEOUT_WITHOUT_PASSING_RECORDING_SECONDS = 1800
# How often a running suite's thread, and the loop that collects results, look for a
# stop signal the runner received.
RUN_STOP_SIGNAL_CHECK_SECONDS = 0.5
RUN_STOP_SIGNALS = (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)
# Runs inside the suite's own cgroup scope and reads the scope's counters just before
# the scope ends, because systemd removes a scope's cgroup when its last process exits.
# $0 is the open file descriptor the counters go to, which the suite does not inherit;
# the suite's command follows. bash, because dash cannot name a descriptor above 9.
TEST_SUITE_CGROUP_STATISTICS_WRAPPER = (
    'if [ "$0" != 3 ]; then eval "exec 3>&$0 $0>&-"; fi\n'
    'cgroup=$(sed -n "s/^0:://p" /proc/self/cgroup)\n'
    '"$@" 3>&-\n'
    'status=$?\n'
    '{ cat "/sys/fs/cgroup$cgroup/cpu.stat" && '
    'printf "memory.peak %s\\n" "$(cat "/sys/fs/cgroup$cgroup/memory.peak")"; } >&3 2>&1\n'
    'exit $status\n')
TEST_SUITE_CGROUP_SCOPE_COMMAND = (
    "systemd-run", "--user", "--scope", "--quiet", "--expand-environment=no", "--")
# Where the shell that keeps the counters stands between this program and bwrap, it is
# killed when this program dies, so bwrap's --die-with-parent still ends the suite.
TEST_SUITE_COUNTER_SHELL_DIES_WITH_THIS_PROGRAM = ("setpriv", "--pdeathsig", "KILL")

DEFAULT_LOCK_FILE = Path.home() / ".claude" / ".run-all-test-suites.lock"
RUN_RECORDS_DIRECTORY_SUFFIX = ".runs"
# Long enough for whoever reads a run's report and failed-suite logs to read them.
FINISHED_RUN_LOG_RETENTION_SECONDS = 2 * 24 * 3600
LOG_DIRECTORY_LOCK_FILE_NAME = ".run-all-test-suites-log-directory.lock"
REPORT_FILE_NAME = "test-run-report.txt"
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
MACHINE_LOCK_WAIT_SECONDS_SUGGESTED = 3600
MACHINE_LOCK_WAITED_LINE_PREFIX = "seconds waiting for the machine's lock: "


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


def suite_sandbox_lists_read_from_checkout_under_test(top):
    """Return ({list name: {suite: reason}}, the file they came from) for the checkout under test.

    The lists name the checkout's suites by path, so they come from the checkout's own copy
    of this program: a pull request head test run runs main's runner on the merged tree, and
    a pull request that renames a listed suite renames its entry too. That copy is parsed,
    never run, so none of the checkout's code runs in this program. A checkout without the
    file, such as a test's scratch checkout, gets this program's own lists."""
    source_file = top / "scripts" / "run-all-test-suites.py"
    try:
        source = source_file.read_text(encoding="utf-8")
    except FileNotFoundError:
        own = {name: dict(entries) for name, entries in SUITE_SANDBOX_LISTS_OF_THIS_PROGRAM.items()}
        return own, (f"{Path(__file__).resolve()}, since the checkout has no "
                     f"{source_file.relative_to(top)}")
    except (OSError, UnicodeDecodeError) as error:
        restore = f"git -C {top} checkout -- {source_file.relative_to(top)}"
        rerun = "Once the step for your case succeeds, rerun the command you ran.\n"
        tell_the_user = ("this same error appears again after you rerun, stop and tell the user, "
                         "quoting this message; a subagent tells the agent that dispatched it "
                         "instead.")
        if isinstance(error, UnicodeDecodeError):
            raise CouldNotRun(
                f"{PROGRAM}: not run — {source_file} is not UTF-8 text "
                f"({type(error).__name__}: {error}), so which sandbox each suite runs in is "
                f"unknown.\n"
                f"If the file holds no uncommitted change you need, restore it with: {restore}\n"
                f"If it holds an uncommitted change you need, re-save it as UTF-8, keeping "
                f"that change.\n"
                f"{rerun}"
                f"If a step fails, or {tell_the_user}")
        raise CouldNotRun(
            f"{PROGRAM}: not run — {source_file} could not be read "
            f"({type(error).__name__}: {error}), so which sandbox each suite runs in is unknown.\n"
            f"If you lack permission to read the file, grant yourself read permission, such as "
            f"with: chmod u+r {source_file}\n"
            f"If a directory or anything else that is not a regular file stands at that path, "
            f"move it aside and restore the file with: "
            f"mv {source_file} {source_file}.moved-aside && {restore}\n"
            f"{rerun}"
            f"If neither case fits, a step fails, or {tell_the_user}")
    try:
        tree = ast.parse(source, filename=str(source_file))
    except (SyntaxError, ValueError) as error:
        raise CouldNotRun(
            f"{PROGRAM}: not run — {source_file} is not valid Python ({error}), so which "
            f"sandbox each suite runs in is unknown.\n"
            f"Correct the syntax error in {source_file}, which belongs to the checkout whose suites "
            f"this run tests, then rerun the command you ran.")
    found = {}
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id in SUITE_SANDBOX_LIST_NAMES_READ_FROM_CHECKOUT_UNDER_TEST):
            try:
                found[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, TypeError, SyntaxError, RecursionError):
                found[node.targets[0].id] = None
    unreadable = [name for name in SUITE_SANDBOX_LIST_NAMES_READ_FROM_CHECKOUT_UNDER_TEST
                  if not isinstance(found.get(name), dict)]
    if unreadable:
        raise CouldNotRun(
            f"{PROGRAM}: not run — {source_file} does not assign "
            f"{', '.join(unreadable)} a literal dict of suite path to reason at its top "
            f"level, so which sandbox each suite runs in is unknown.\n"
            f"In {source_file}, assign each of {', '.join(unreadable)} once, at the top level, "
            f"a dict written out literally, then rerun the command you ran.")
    return found, str(source_file)


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


def git_failure_next_step_lines(program_file):
    """The lines that end a refusal after a git failure, for a run of program_file."""
    rerun = f"the same {program_file} command"
    return "\n".join([
        f"If git's error names a lock file, such as .git/index.lock, wait one minute, then run "
        f"{rerun}; do not delete the lock file yourself.",
        f"If git's error names a branch, commit or path that does not exist, and you gave that "
        f"name to {program_file}, correct it in your command, then run the corrected command.",
        f"In any other case, run {rerun} once more.",
        f"If {rerun} fails again, stop and tell the user what {program_file} printed, git's "
        f"error included; a subagent tells the agent that dispatched it instead."])


def first_line_of_error(completed):
    return ((completed.stderr or "").strip().splitlines() or [""])[0]


def commit_and_state(top):
    # --verify --quiet exits 1 for a branch with no commit yet.
    head = git(top, "rev-parse", "--verify", "--quiet", "HEAD")
    if head.returncode == 0:
        commit = head.stdout.strip()
    elif head.returncode == 1:
        commit = "no commit"
    else:
        commit = (f"commit unknown (git rev-parse HEAD exited {head.returncode}: "
                  f"{first_line_of_error(head)})")
    changed = git(top, "status", "--porcelain", "--untracked-files=no")
    if changed.returncode != 0:
        state = "tracked-file state unknown"
    elif changed.stdout.strip():
        state = "tracked files differ from that commit"
    else:
        state = "tracked files match that commit"
    return commit, state


class _MachineLockWaitEnded(Exception):
    """The wait for the machine's lock reached its deadline."""


def flock_exclusive_waiting_up_to(handle, wait_seconds):
    """Take an exclusive flock on handle, waiting up to wait_seconds; False if not taken.

    A wait blocks in the kernel's queue, like `flock -w`, rather than retrying: the
    kernel hands a released lock to a blocked waiter, so a program that retries loses
    to every blocked waiter and can wait forever. The deadline is a SIGALRM timer, so
    a wait works only in the main thread."""
    if wait_seconds <= 0:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return False
        return True

    def deadline_reached(signum, frame):
        raise _MachineLockWaitEnded()

    previous_handler = signal.signal(signal.SIGALRM, deadline_reached)
    try:
        signal.setitimer(signal.ITIMER_REAL, wait_seconds)
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        except _MachineLockWaitEnded:
            return False
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
    finally:
        signal.signal(signal.SIGALRM, previous_handler)
    return True


def lock_holder_described(description):
    """The lock file's holder description, or why it does not name the holder.

    flock frees the lock when its holder dies, but nothing clears the description, and
    a holder that is not a run of this program, such as `flock -w` on the lock, writes
    none; so a description naming a process that has ended is from an earlier run."""
    named = re.match(r"pid (?P<pid>\d+),", description)
    if not description:
        return "a process that wrote no description of itself"
    if named is None or process_running(int(named["pid"])):
        return description
    return (f"a process that wrote no description of itself; the lock file still holds "
            f"\"{description}\", from an earlier run whose process has ended")


def process_running(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def take_machine_lock(lock_file, top, wait_seconds=0):
    """Return (handle, refusal, previous holder), with None for unavailable fields.

    With wait_seconds above 0, wait up to that long for the lock before refusing."""
    # Append mode preserves the holder's description when another run wins the lock.
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_file, "a+")
    if not flock_exclusive_waiting_up_to(handle, wait_seconds):
        handle.seek(0)
        holder = lock_holder_described(handle.read().strip())
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


class MachineWideTestSuiteAdmissionCouldNotDecide(Exception):
    """Admission could not be decided, such as a slot file that cannot be opened."""


class TestRunStoppedBeforeSuiteStarted(Exception):
    """The runner received a stop signal before this suite started."""


class MachineWideTestSuiteAdmissionCancelled(Exception):
    """The run stopped admitting suites, so a suite still waiting does not start."""


class TestSuiteAdmissionMachineCpuAndMemoryReadingsSampler:
    """The machine's CPU use, available memory and load, read every second by a thread.

    Each reading is also written to a file, so the admission thresholds can be
    moved from what the machine did. psutil is passed in, so a test can stub it."""

    def __init__(self, psutil, readings_file=None, interval=MACHINE_READINGS_INTERVAL_SECONDS,
                 average_seconds=TEST_SUITE_ADMISSION_CPU_AVERAGE_SECONDS):
        self.psutil = psutil
        self.readings_file = readings_file
        self.interval = interval
        self.cpu = collections.deque(maxlen=max(1, round(average_seconds / interval)))
        self.lock = threading.Lock()
        self.stopped = threading.Event()
        self.thread = None
        self.failure = None

    def read_once(self, blocking_seconds=None):
        cpu = self.psutil.cpu_percent(interval=blocking_seconds)
        available = self.psutil.virtual_memory().available
        load = os.getloadavg()[0]
        with self.lock:
            self.cpu.append(cpu)
        if self.readings_file is not None:
            with open_for_writing_without_following_symlinks(self.readings_file,
                                                             append=True) as readings:
                readings.write(f"{time.time():.3f}\t{cpu:.1f}\t{available}\t{load:.2f}\n")

    def start(self):
        try:
            if self.readings_file is not None:
                with open_for_writing_without_following_symlinks(self.readings_file) as readings:
                    readings.write("unix time\tcpu percent\tavailable memory bytes\tload average 1 min\n")
            # The first reading blocks for one interval: psutil measures CPU use between two calls.
            self.read_once(blocking_seconds=self.interval)
        except Exception as error:
            raise MachineWideTestSuiteAdmissionCouldNotDecide(
                f"the machine's first reading failed: {error!r}") from error
        self.thread = threading.Thread(target=self.read_every_interval, daemon=True)
        self.thread.start()

    def read_every_interval(self):
        # Each reading blocks for one interval: psutil keeps the CPU baseline of a
        # nonblocking reading per thread, so this thread's first one would read 0.
        while not self.stopped.is_set():
            try:
                self.read_once(blocking_seconds=self.interval)
            except Exception as error:
                # Admission must not decide on readings that stopped; it reports this instead.
                with self.lock:
                    self.failure = error
                return

    def stop(self):
        self.stopped.set()
        if self.thread is not None:
            self.thread.join()

    def failure_or_none(self):
        """What stopped the readings, or None while they ran to the end."""
        with self.lock:
            return self.failure

    def cpu_percent_average(self):
        with self.lock:
            if self.failure is not None:
                raise MachineWideTestSuiteAdmissionCouldNotDecide(
                    f"the machine's readings stopped: {self.failure!r}")
            return sum(self.cpu) / len(self.cpu) if self.cpu else 0.0

    def available_memory_bytes(self):
        try:
            return self.psutil.virtual_memory().available
        except Exception as error:
            raise MachineWideTestSuiteAdmissionCouldNotDecide(
                f"the machine's available memory could not be read: {error!r}") from error


def test_suite_admission_directory_for_lock_file(lock_file):
    return Path(f"{lock_file}{TEST_SUITE_ADMISSION_DIRECTORY_SUFFIX}")


class MachineWideTestSuiteAdmission:
    """Decide, for every run on this machine together, when each suite may start.

    A suite starts only while the machine's CPU use, averaged over the last few
    seconds, is under TEST_SUITE_ADMISSION_CPU_PERCENT_BELOW, its available memory
    is above TEST_SUITE_ADMISSION_AVAILABLE_MEMORY_BYTES_ABOVE, fewer than
    TEST_SUITE_ADMISSION_STARTS_PER_SECOND suites started in the last second, and
    one of TEST_SUITE_ADMISSION_SUITES_RUNNING_AT_ONCE_CEILING slots is free. A slot
    is an flock on a slot file, so the kernel frees the slot of a run that is killed.
    A suite run without any sandbox first takes the lock those suites share,
    and only then a slot, so it never holds a slot while it waits for that lock;
    when no slot is free, it lets the lock go before it waits, so it never holds
    the lock while it waits for room.
    A suite that cannot start waits, with no time limit; once a minute the run
    reports what the suites wait for."""

    def __init__(self, directory, readings, say, clock=time.monotonic, sleep=time.sleep,
                 machine_clock=time.monotonic):
        self.directory = Path(directory)
        self.readings = readings
        self.say = say
        self.clock = clock
        self.sleep = sleep
        # Start times are compared across the runs of this machine, so the clock is one
        # every process shares and that never steps back: Linux's monotonic clock.
        self.machine_clock = machine_clock
        self.lock = threading.Lock()
        self.waiting = {}
        self.last_report = None
        self.cancelled = threading.Event()
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise MachineWideTestSuiteAdmissionCouldNotDecide(
                f"the admission directory {self.directory} could not be made: {error}") from error

    def open_locked(self, path, blocking):
        """An open handle holding an exclusive flock on path, or None when another holds it."""
        try:
            handle = open(path, "a")
        except OSError as error:
            raise MachineWideTestSuiteAdmissionCouldNotDecide(
                f"{path} could not be opened: {error}") from error
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except BlockingIOError:
            handle.close()
            return None
        except OSError as error:
            handle.close()
            raise MachineWideTestSuiteAdmissionCouldNotDecide(f"flock on {path} failed: {error}") from error
        return handle

    def free_slot(self):
        for number in range(TEST_SUITE_ADMISSION_SUITES_RUNNING_AT_ONCE_CEILING):
            slot = self.open_locked(
                self.directory / f"{TEST_SUITE_ADMISSION_SLOT_FILE_PREFIX}{number:02d}",
                blocking=False)
            if slot is not None:
                return slot
        return None

    def why_not_now(self):
        """What keeps a suite from starting now, or None when only a slot is needed."""
        cpu = self.readings.cpu_percent_average()
        if cpu >= TEST_SUITE_ADMISSION_CPU_PERCENT_BELOW:
            return (f"the machine's CPU use, {cpu:.0f}% over the last "
                    f"{TEST_SUITE_ADMISSION_CPU_AVERAGE_SECONDS} s, is not under "
                    f"{TEST_SUITE_ADMISSION_CPU_PERCENT_BELOW}%")
        available = self.readings.available_memory_bytes()
        if available <= TEST_SUITE_ADMISSION_AVAILABLE_MEMORY_BYTES_ABOVE:
            return (f"the machine's available memory, {available / 10**9:.1f} GB, is not "
                    f"above {TEST_SUITE_ADMISSION_AVAILABLE_MEMORY_BYTES_ABOVE / 10**9:g} GB")
        return None

    def take_a_start_and_a_slot(self):
        """(slot handle, None) once this suite may start, or (None, why it may not)."""
        why = self.why_not_now()
        if why is not None:
            return None, why
        # One machine-wide decision at a time, so two runs cannot both take the last start.
        times_lock = self.open_locked(
            self.directory / f".{TEST_SUITE_ADMISSION_START_TIMES_FILE_NAME}.lock", blocking=True)
        try:
            times_file = self.directory / TEST_SUITE_ADMISSION_START_TIMES_FILE_NAME
            now = self.machine_clock()
            try:
                recent = [float(line) for line in times_file.read_text().split()
                          if 0.0 <= now - float(line) < 1.0]
            except FileNotFoundError:
                recent = []
            except (OSError, ValueError) as error:
                # Read as empty, it would lift the start-rate limit and overwrite the history.
                raise MachineWideTestSuiteAdmissionCouldNotDecide(
                    f"{times_file} could not be read: {error}") from error
            if len(recent) >= TEST_SUITE_ADMISSION_STARTS_PER_SECOND:
                return None, (f"{TEST_SUITE_ADMISSION_STARTS_PER_SECOND} suites started on this "
                              f"machine in the last second, the most allowed")
            slot = self.free_slot()
            if slot is None:
                return None, (f"{TEST_SUITE_ADMISSION_SUITES_RUNNING_AT_ONCE_CEILING} suites are "
                              f"running on this machine, the most allowed")
            try:
                times_file.write_text("".join(f"{moment!r}\n" for moment in [*recent, now]))
            except OSError as error:
                slot.close()
                raise MachineWideTestSuiteAdmissionCouldNotDecide(
                    f"{times_file} could not be written: {error}") from error
            return slot, None
        finally:
            times_lock.close()

    def report_waiting(self, suite, why):
        with self.lock:
            self.waiting[suite] = why
            now = self.clock()
            if self.last_report is not None and \
                    now - self.last_report < TEST_SUITE_ADMISSION_WAIT_REPORT_INTERVAL_SECONDS:
                return
            self.last_report = now
            reasons = sorted(set(self.waiting.values()))
            count = len(self.waiting)
        self.say(f"{count} suite{'s' if count != 1 else ''} of this run "
                 f"{'wait' if count != 1 else 'waits'} to start: " + "; ".join(reasons)
                 + ". Each suite starts by itself once the reason it waits for clears.")

    def cancel(self):
        """Stop admitting: every suite still waiting raises MachineWideTestSuiteAdmissionCancelled."""
        self.cancelled.set()

    def raise_if_cancelled(self, suite):
        if self.cancelled.is_set():
            raise MachineWideTestSuiteAdmissionCancelled(
                f"{suite} was not started: the run stopped admitting suites")

    @contextlib.contextmanager
    def admitted(self, suite, without_any_sandbox=False):
        """Hold a slot, and for a suite run without any sandbox that lock first, while the suite runs.

        Yields the seconds the suite waited. Raises MachineWideTestSuiteAdmissionCancelled
        once cancel() is called while the suite waits."""
        started = self.clock()
        held = []
        try:
            # Polled rather than a blocking flock, so a cancel reaches a suite waiting here.
            while True:
                self.raise_if_cancelled(suite)
                outside_lock = None
                if without_any_sandbox:
                    outside_lock = self.open_locked(
                        self.directory / SUITES_RUN_WITHOUT_ANY_SANDBOX_LOCK_FILE_NAME,
                        blocking=False)
                    if outside_lock is None:
                        self.report_waiting(suite, "another run is running a suite that has no sandbox, "
                                                   "and that run holds the lock all such suites share")
                        self.sleep(TEST_SUITE_ADMISSION_RETRY_SECONDS)
                        continue
                try:
                    slot, why = self.take_a_start_and_a_slot()
                except BaseException:
                    if outside_lock is not None:
                        outside_lock.close()
                    raise
                if slot is not None:
                    held.extend(handle for handle in (outside_lock, slot) if handle is not None)
                    break
                # Held through a wait for room, the lock would keep every other run's
                # suites run without any sandbox waiting while this one runs nothing.
                if outside_lock is not None:
                    outside_lock.close()
                self.report_waiting(suite, why)
                self.sleep(TEST_SUITE_ADMISSION_RETRY_SECONDS)
            with self.lock:
                self.waiting.pop(suite, None)
            yield self.clock() - started
        finally:
            with self.lock:
                self.waiting.pop(suite, None)
            for handle in reversed(held):
                handle.close()


def psutil_imported_or_why_not():
    """(psutil, None), or (None, the refusal to print) when this Python has no psutil."""
    try:
        import psutil
    except ImportError as error:
        return None, (
            f"{PROGRAM}: not run — {sys.executable} cannot import psutil ({error}), which "
            f"this program needs on Linux to read the machine's CPU use and available memory "
            f"before it starts each suite.\n"
            f"Install the pinned libraries, psutil among them, by running "
            f"`python3 nc-systems/general-tools/python-libraries-pinned-requirements-check-and-install.py`, "
            f"then run this again.\n"
            f"If that install fails, tell the user what it printed.")
    return psutil, None


def why_test_suites_cannot_run_in_cgroup_scopes_on_this_machine_or_none(which=shutil.which,
                                                                        runner=subprocess.run):
    """None when each suite can run in a cgroup scope of its own, or why it cannot."""
    for program in ("systemd-run", "setpriv", "bash"):
        if which(program) is None:
            return f"{program} is not on PATH"
    trial_line = " ".join((*TEST_SUITE_CGROUP_SCOPE_COMMAND,
                           *TEST_SUITE_COUNTER_SHELL_DIES_WITH_THIS_PROGRAM))
    try:
        trial = runner([*TEST_SUITE_CGROUP_SCOPE_COMMAND,
                        *TEST_SUITE_COUNTER_SHELL_DIES_WITH_THIS_PROGRAM, "true"],
                       stdin=subprocess.DEVNULL,
                       capture_output=True, text=True,
                       timeout=SIGNAL_SANDBOX_START_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return f"{trial_line} true: {error}"
    if trial.returncode != 0:
        return (f"{trial_line} true exited {trial.returncode}: "
                f"{(trial.stderr or trial.stdout).strip()}")
    return None


def command_prefix_running_one_suite_in_its_cgroup_scope(statistics_descriptor, in_bwrap):
    """The command prefix that runs a suite in a cgroup scope of its own and keeps its counters.

    The counters are written to statistics_descriptor, an open file the caller passes on.
    A suite outside bwrap outlives a killed run, as before, and the shell, which waits
    for it, outlives the run with it, so the run's record still sees the suite running."""
    return (*TEST_SUITE_CGROUP_SCOPE_COMMAND,
            *(TEST_SUITE_COUNTER_SHELL_DIES_WITH_THIS_PROGRAM if in_bwrap else ()),
            "bash", "-c", TEST_SUITE_CGROUP_STATISTICS_WRAPPER, str(statistics_descriptor))


def cpu_seconds_and_peak_memory_from_suite_cgroup_statistics(text):
    """(CPU seconds, peak memory bytes, None), or (None, None, why they are missing)."""
    if not text.strip():
        return None, None, "the suite's cgroup counters were not written"
    fields = dict(line.split(None, 1) for line in text.splitlines() if len(line.split(None, 1)) == 2)
    try:
        return (int(fields["usage_usec"]) / 10**6, int(fields["memory.peak"]), None)
    except (KeyError, ValueError):
        return None, None, f"the suite's cgroup counters could not be read: {text.strip()[:200]!r}"


def copy_suite_output_to_log_noting_each_case_line(stream, log, started, cases, failures):
    """Copy a suite's output to its open log, timing each PASS, FAIL or ok line as it arrives.

    A write to the log that fails is appended to failures, and the rest of the output is
    read and dropped, so the suite does not block on a full pipe."""
    try:
        with log:
            copy_lines_of_suite_output(stream, log, started, cases)
    except OSError as error:
        failures.append(error)
        for _ in iter(lambda: stream.read(1 << 16), b""):
            pass
    finally:
        stream.close()


def copy_lines_of_suite_output(stream, log, started, cases):
    for raw in iter(stream.readline, b""):
        log.write(raw)
        log.flush()
        arrived = time.monotonic() - started
        found = TEST_CASE_LINE.match(raw.decode("utf-8", "replace").rstrip("\r\n"))
        if found is None:
            continue
        text = found["text"]
        name, detail = text, ""
        if found["verdict"] == "FAIL" and ": " in text:
            name, detail = text.split(": ", 1)
        begun = cases[-1]["ended"] if cases else 0.0
        cases.append({"verdict": "FAIL" if found["verdict"] == "FAIL" else "PASS",
                      "name": name.strip(), "detail": detail.strip(),
                      "began": begun, "ended": arrived, "seconds": arrived - begun,
                      "unix_time": time.time()})


def write_case_times_suite_resources_and_junit_xml_of_run(log_dir, results):
    """Write the per-case times, per-suite resources and the JUnit XML of a run."""
    with open_for_writing_without_following_symlinks(log_dir / TEST_CASE_TIMES_FILE_NAME) as times:
        times.write("suite\tverdict\tseconds\tseconds from suite start\tunix time\tcase\n")
        for result in results:
            for case in result.get("cases", ()):
                times.write(f"{result['suite']}\t{case['verdict']}\t{case['seconds']:.3f}\t"
                            f"{case['ended']:.3f}\t{case['unix_time']:.3f}\t"
                            f"{case['name']}\n")
    with open_for_writing_without_following_symlinks(
            log_dir / TEST_SUITE_RESOURCE_USE_FILE_NAME) as resources:
        resources.write("suite\tkind\texit\tseconds\tseconds waiting for admission\t"
                        "cpu seconds\tpeak memory bytes\tnote\n")
        for result in results:
            resources.write(
                f"{result['suite']}\t{result.get('kind', '')}\t{result['exit']}\t"
                f"{result['seconds']:.3f}\t{result.get('admission_wait', 0.0):.3f}\t"
                f"{'' if result.get('cpu_seconds') is None else format(result['cpu_seconds'], '.3f')}\t"
                f"{'' if result.get('peak_memory_bytes') is None else result['peak_memory_bytes']}\t"
                f"{result.get('resources_note') or ''}\n")
    root = xml.etree.ElementTree.Element("testsuites", name=PROGRAM)
    for result in results:
        cases = result.get("cases") or []
        failed = sum(1 for case in cases if case["verdict"] == "FAIL")
        # A suite that fails after its last case line gets one more, failing, case below.
        failed_after_last_case = int(bool(cases) and result["exit"] != 0 and not failed)
        suite_element = xml.etree.ElementTree.SubElement(
            root, "testsuite", name=result["suite"],
            tests=str(len(cases) + failed_after_last_case if cases else 1),
            failures=str(failed + failed_after_last_case if cases else int(result["exit"] != 0)),
            skipped=str(len(result["skips"])), time=f"{result['seconds']:.3f}")
        if not cases:
            # A suite that printed no case line is one case, judged by its exit code.
            case_element = xml.etree.ElementTree.SubElement(
                suite_element, "testcase", classname=result["suite"], name=result["suite"],
                time=f"{result['seconds']:.3f}")
            if result["exit"] != 0:
                xml.etree.ElementTree.SubElement(
                    case_element, "failure", message=why_suite_failed(result))
            continue
        for case in cases:
            case_element = xml.etree.ElementTree.SubElement(
                suite_element, "testcase", classname=result["suite"], name=case["name"],
                time=f"{case['seconds']:.3f}")
            if case["verdict"] == "FAIL":
                xml.etree.ElementTree.SubElement(case_element, "failure",
                                                 message=case["detail"] or case["name"])
        if failed_after_last_case:
            # The suite failed after its last case line, such as by a crash.
            case_element = xml.etree.ElementTree.SubElement(
                suite_element, "testcase", classname=result["suite"],
                name=f"{result['suite']} exit", time="0.000")
            xml.etree.ElementTree.SubElement(case_element, "failure",
                                             message=why_suite_failed(result))
    with open_for_writing_without_following_symlinks(log_dir / JUNIT_XML_FILE_NAME,
                                                     binary=True) as junit:
        xml.etree.ElementTree.ElementTree(root).write(junit, encoding="utf-8",
                                                       xml_declaration=True)


def append_test_case_failure_history(history_file, top, commit, branch, log_dir, results):
    """Add each failing case of this run to the history of failing cases, one JSON line each."""
    lines = []
    for result in results:
        if result["exit"] == 0:
            continue
        failing = [case for case in result.get("cases", ()) if case["verdict"] == "FAIL"]
        for case in failing or [{"name": None, "detail": why_suite_failed(result)}]:
            lines.append(json.dumps({
                "unix_time": time.time(), "suite": result["suite"], "case": case["name"],
                "detail": case["detail"], "exit": result["exit"], "commit": commit,
                "branch": branch, "checkout": str(top), "log": str(result["log"]),
                "run_log_directory": str(log_dir)}))
    if not lines:
        return
    history_file.parent.mkdir(parents=True, exist_ok=True)
    with open(history_file, "a") as history:
        fcntl.flock(history.fileno(), fcntl.LOCK_EX)
        history.write("".join(line + "\n" for line in lines))


@contextlib.contextmanager
def lock_held_while_cleaning_up_after_earlier_runs(lock_file):
    """Held while one of several overlapping runs cleans up after earlier runs."""
    path = Path(f"{lock_file}.clean-up-after-earlier-runs.lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield


def branch_of_checkout(top):
    # symbolic-ref -q exits 1 for a detached HEAD, recorded as "HEAD" as rev-parse
    # --abbrev-ref names it.
    named = git(top, "symbolic-ref", "-q", "--short", "HEAD")
    if named.returncode == 0:
        return named.stdout.strip()
    if named.returncode == 1:
        return "HEAD"
    return (f"branch unknown (git symbolic-ref HEAD exited {named.returncode}: "
            f"{first_line_of_error(named)})")


def lock_explicit_log_directory(log_dir):
    """Hold the given log directory for this run, or return None when another run holds it."""
    handle = open(log_dir / LOG_DIRECTORY_LOCK_FILE_NAME, "a")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


def open_for_writing_without_following_symlinks(path, append=False, binary=False):
    """Open path for writing, refusing a symbolic link there in place of following it."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | (os.O_APPEND if append else os.O_TRUNC)
    return os.fdopen(os.open(path, flags, 0o644),
                     ("a" if append else "w") + ("b" if binary else ""))


def read_text_without_following_symlinks(path, errors="surrogateescape"):
    """The text of the regular file at path; OSError for a symbolic link or any other kind.

    A suite writes the files this reads, and could leave a link to another file, or a
    named pipe, whose open would wait for a writer that never comes."""
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "r", errors=errors) as handle:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError(f"{path} is not a regular file")
        return handle.read()


def log_path_for(log_dir, suite):
    # Include the relative path to distinguish suites with the same filename.
    return log_dir / (suite.replace("/", "__") + ".log")


def skipped_case_lines(log_file):
    try:
        text = read_text_without_following_symlinks(log_file, errors="replace")
    except OSError:
        return []
    return [line for line in text.splitlines() if SKIPPED_CASE_LINE.match(line)]


def environment_without_git_redirecting_variables():
    # A fresh dict each call, because suites launch concurrently.
    return git_redirecting_removal.environment_without_git_redirecting_variables()


def is_credential_environment_variable(name):
    return any(fnmatch.fnmatchcase(name.upper(), pattern)
               for pattern in TEST_SUITE_CREDENTIAL_ENVIRONMENT_VARIABLE_PATTERNS)


def launch_environment_for_a_test_suite_with_git_redirecting_agent_session_attendance_and_credential_variables_removed():
    """Return the environment every path that launches a test suite gives the suite."""
    environment = environment_without_git_redirecting_variables()
    for variable in AGENT_SESSION_ATTENDANCE_ENVIRONMENT_VARIABLES:
        environment.pop(variable, None)
    for variable in [name for name in environment if is_credential_environment_variable(name)]:
        del environment[variable]
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


def signal_sandbox(platform=None, environment=None, which=shutil.which,
                   runner=subprocess.run, sandbox_exec=SIGNAL_SANDBOX_MACOS_SANDBOX_EXEC,
                   outside_process_id=None):
    """Return (prefix, None) to put before a suite's command, or ((), why) when it runs unconfined.

    Raises SignalSandboxCouldNotStart when bwrap is on PATH but fails to start,
    or on macOS when sandbox-exec is missing, fails to start or lets a trial
    signal out, since running unconfined then would hide a broken sandbox.
    outside_process_id is the process outside the sandbox that checks inside it
    signal; default this process.
    """
    platform = sys.platform if platform is None else platform
    environment = os.environ if environment is None else environment
    if environment.get(SIGNAL_SANDBOX_INSIDE_VARIABLE):
        return (), None
    if platform == "darwin":
        return macos_signal_sandbox(
            runner, sandbox_exec,
            os.getpid() if outside_process_id is None else outside_process_id), None
    if not platform.startswith("linux"):
        return (), f"{platform} has no signal sandbox built for it"
    bwrap = which("bwrap")
    if bwrap is None:
        return (), "bwrap is not on PATH (Ubuntu: sudo apt install bubblewrap)"
    prefix = (bwrap, *TEST_SANDBOX_BWRAP_ARGUMENTS_SHARED_BY_EVERY_SUITE,
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


# Directories the test sandbox already makes private or hides, which the scan for
# writable directories does not walk.
TEST_SANDBOX_PRIVATE_DIRECTORY_PATHS_NOT_SCANNED_FOR_WRITABLE_DIRECTORIES = ("/proc", "/sys", "/dev", "/tmp", "/run")


# The scan never walks these, whatever the lists of hidden directories say, since walking
# one is slow (the backup drive under /mnt holds the home directory many times over) or
# meaningless; each must be hidden whole, or the scan refuses, so that a change to those
# lists cannot make the scan crawl them instead.
TEST_SANDBOX_DIRECTORIES_THE_WRITABLE_DIRECTORY_SCAN_NEVER_WALKS = (
    "/proc", "/sys", "/dev", "/tmp", "/run", "/mnt", "/media", "/var/snap",
    REAL_HOME_DIRECTORY_PATH_HIDDEN_BY_EMPTY_TMPFS_IN_TEST_SANDBOX)


@functools.cache
def directories_this_account_can_create_files_in_hidden_in_test_sandbox():
    """Each topmost directory outside the sandbox's private ones that this account can write.

    A suite that sees one could find there a socket or a file that some process outside
    makes after the suite starts, so each is hidden whole by an empty tmpfs. A directory
    made later sits inside one of these, so a scan once per process is enough. Raises
    SignalSandboxCouldNotStart when the scan cannot run."""
    pruned = (*TEST_SANDBOX_PRIVATE_DIRECTORY_PATHS_NOT_SCANNED_FOR_WRITABLE_DIRECTORIES,
              REAL_HOME_DIRECTORY_PATH_HIDDEN_BY_EMPTY_TMPFS_IN_TEST_SANDBOX,
              *TEST_SANDBOX_FIXED_DIRECTORIES_HIDDEN_BY_EMPTY_TMPFS)
    unhidden = [path for path in TEST_SANDBOX_DIRECTORIES_THE_WRITABLE_DIRECTORY_SCAN_NEVER_WALKS
                if path not in pruned and os.path.isdir(path)]
    if unhidden:
        raise SignalSandboxCouldNotStart(
            f"{', '.join(unhidden)}, which the scan for directories this account can write "
            f"never walks, would not be hidden whole in the test sandbox, so what "
            f"{'it holds' if len(unhidden) == 1 else 'they hold'} would show inside it")
    pruned = tuple(dict.fromkeys(
        (*pruned, *TEST_SANDBOX_DIRECTORIES_THE_WRITABLE_DIRECTORY_SCAN_NEVER_WALKS)))
    expression = []
    for path in pruned:
        expression += (["-o"] if expression else []) + ["-path", path]
    command = ["find", "/", "(", *expression, ")", "-prune", "-o",
               "-type", "d", "-writable", "-print", "-prune"]
    try:
        # find exits 1 when some directory cannot be read; it still lists every
        # directory it could, and a directory it cannot read it cannot write into either.
        answer = subprocess.run(command, capture_output=True, text=True,
                                stdin=subprocess.DEVNULL, check=False,
                                timeout=SIGNAL_SANDBOX_START_TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise SignalSandboxCouldNotStart(
            f"the scan for directories this account can write ({' '.join(command)}) could "
            f"not run: {error}") from error
    if answer.returncode not in (0, 1):
        raise SignalSandboxCouldNotStart(
            f"the scan for directories this account can write exited {answer.returncode}: "
            f"{answer.stderr.strip()[-500:]}")
    return tuple(line for line in answer.stdout.splitlines() if line.startswith("/"))


# Asked of the interpreter itself: exactly the files and directories it loads, never a whole
# installation prefix, since a prefix in the home directory such as ~/.local also holds
# credentials. In a virtual environment, sysconfig names the base installation's standard
# library and the environment's own site-packages.
INTERPRETER_LOADED_PATHS_SOURCE = (
    "import os, sys, sysconfig\n"
    "paths = sysconfig.get_paths()\n"
    "loaded = [sys.executable, os.path.realpath(sys.executable)]\n"
    "loaded += [paths[name] for name in ('stdlib', 'platstdlib', 'purelib', 'platlib')]\n"
    "configuration = os.path.join(sys.prefix, 'pyvenv.cfg')\n"
    "if os.path.isfile(configuration):\n"
    "    loaded.append(configuration)\n"
    "library = os.path.join(sysconfig.get_config_var('LIBDIR') or '',\n"
    "                       sysconfig.get_config_var('LDLIBRARY') or '')\n"
    "if os.path.isfile(library):\n"
    "    loaded.append(library)\n"
    "print(chr(0).join(loaded))\n")
INTERPRETER_LOADED_PATHS_TIMEOUT_SECONDS = 60


@functools.lru_cache(maxsize=None)
def interpreter_directories_shown_read_only_in_test_sandbox(interpreter, hidden=None):
    """The paths an interpreter loads that a test sandbox would hide: its executable under
    the name given and its real one, its standard library, its site-packages, a virtual
    environment's pyvenv.cfg and its shared libpython, each as the interpreter reports it;
    none for an interpreter that loads nothing hidden.

    Raises SignalSandboxCouldNotStart when the interpreter cannot report them, or when one
    of them is or holds a directory the sandbox hides whole, since showing it would show
    that directory."""
    hidden = directories_hidden_whole_in_test_sandbox() if hidden is None else hidden
    # A bare name, such as python3, is the one PATH finds, as the suite's command finds it.
    given = os.path.abspath(interpreter if os.sep in interpreter
                            else shutil.which(interpreter) or interpreter)
    try:
        answer = subprocess.run([given, "-I", "-c", INTERPRETER_LOADED_PATHS_SOURCE],
                                capture_output=True, text=True, stdin=subprocess.DEVNULL,
                                timeout=INTERPRETER_LOADED_PATHS_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise SignalSandboxCouldNotStart(
            f"the interpreter {given} could not report the paths it loads, so what it needs "
            f"inside the test sandbox is not known: {error}") from error
    loaded = answer.stdout.strip().split("\0")
    if answer.returncode != 0 or len(loaded) < 6 or not all(map(os.path.isabs, loaded)):
        raise SignalSandboxCouldNotStart(
            f"the interpreter {given} could not report the paths it loads, so what it needs "
            f"inside the test sandbox is not known: exit {answer.returncode}: "
            f"{(answer.stderr or answer.stdout).strip()}")
    shown = []
    for path in [given, *loaded]:
        if not os.path.lexists(path):
            continue
        real = os.path.realpath(path)
        for candidate in dict.fromkeys((os.path.abspath(path), real)):
            if not any(candidate == top or candidate.startswith(top + "/") for top in hidden):
                continue
            if any(top == candidate or top.startswith(candidate.rstrip("/") + "/")
                   for top in hidden):
                raise SignalSandboxCouldNotStart(
                    f"the interpreter {given} loads {candidate}, which is or holds a "
                    f"directory the test sandbox hides whole, so showing it would show that "
                    f"directory; run the suites with an interpreter installed elsewhere")
            if candidate not in shown:
                shown.append(candidate)
    # A path inside another one shown is shown with it.
    return [path for path in shown
            if not any(path.startswith(other.rstrip("/") + "/") for other in shown)]


def paths_one_suite_launch_needs_shown_read_only_in_test_sandbox(interpreters, program_files=(),
                                                                checkout=None):
    """Every path a suite's launch reads that a test sandbox would hide: each interpreter's
    directories, and for each program file run inside the sandbox, such as the launcher that
    checks the sandbox from inside it, the git checkout holding it, since the program loads
    repository modules from beside and above its own directory. A program file in the
    checkout under test needs nothing shown: the sandbox shows the checkout writable, and a
    read-only directory bound over it would make the suite's writes there fail. For the same
    reason, a program's checkout that holds the checkout under test shows only the program's
    own directory."""
    hidden = directories_hidden_whole_in_test_sandbox()
    inside_checkout = os.path.realpath(checkout) if checkout is not None else None
    shown = []
    for interpreter in interpreters:
        for path in interpreter_directories_shown_read_only_in_test_sandbox(interpreter, hidden):
            if path not in shown:
                shown.append(path)
    for program_file in program_files:
        directory = os.path.dirname(os.path.realpath(program_file))
        if inside_checkout is not None and (directory == inside_checkout
                                            or directory.startswith(inside_checkout + "/")):
            continue
        program_checkout = git_checkout_holding_directory_or_none(directory) or directory
        if inside_checkout is None or not (inside_checkout == program_checkout
                                           or inside_checkout.startswith(program_checkout + "/")):
            directory = program_checkout
        if any(directory == top or directory.startswith(top + "/") for top in hidden) and \
                directory not in shown:
            shown.append(directory)
    return shown


def git_checkout_holding_directory_or_none(directory):
    """The nearest directory at or above directory that holds a .git entry, or None."""
    for candidate in (directory, *map(str, Path(directory).parents)):
        if os.path.lexists(os.path.join(candidate, ".git")):
            return candidate
    return None


def directories_hidden_whole_in_test_sandbox():
    """Every directory a test sandbox shows as private or empty, the scanned ones included."""
    return (*TEST_SANDBOX_PRIVATE_DIRECTORY_PATHS_NOT_SCANNED_FOR_WRITABLE_DIRECTORIES,
            REAL_HOME_DIRECTORY_PATH_HIDDEN_BY_EMPTY_TMPFS_IN_TEST_SANDBOX,
            *TEST_SANDBOX_FIXED_DIRECTORIES_HIDDEN_BY_EMPTY_TMPFS,
            *directories_this_account_can_create_files_in_hidden_in_test_sandbox())


# A directory whose hiding would hide what every program needs; a socket directly in one
# is covered by an empty file instead, which a re-created socket would escape.
TEST_SANDBOX_DIRECTORIES_WHERE_A_LISTENING_SOCKET_IS_COVERED_BY_AN_EMPTY_FILE_NOT_HIDDEN_WHOLE = (
    "/", "/bin", "/boot", "/etc", "/lib", "/lib64", "/opt", "/sbin", "/srv", "/usr", "/var")


def empty_file_bound_over_a_listening_socket_in_test_sandbox():
    """An empty, read-only regular file to bind over a listening socket.

    Fails rather than return a file that is not empty, which would hand a suite that
    content."""
    path = Path(tempfile.gettempdir()) / f"{PROGRAM}-empty-file-covering-sockets-{os.getuid()}"
    descriptor = os.open(path, os.O_RDONLY | os.O_CREAT | os.O_NOFOLLOW, 0o444)
    try:
        status = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if not stat.S_ISREG(status.st_mode) or status.st_size != 0 or status.st_uid != os.getuid():
        raise SignalSandboxCouldNotStart(
            f"{path}, the empty file that covers a listening socket inside the test "
            f"sandbox, is not an empty regular file of this account; delete it, "
            f"then run this again")
    return str(path)


def bwrap_arguments_for_one_suites_test_sandbox(checkout, writable_paths=(), suite=None,
                                                read_only_paths=()):
    """bwrap arguments, after TEST_SANDBOX_BWRAP_ARGUMENTS_SHARED_BY_EVERY_SUITE, for one suite's environment.

    The checkout under test is a copy-on-write overlay, so a suite can write in it but
    nothing it writes there survives it: a suite could otherwise leave code in the
    checkout that a suite outside the sandbox, or an agent's next command there, would
    run. writable_paths, files or directories, are bound writable, so what a suite writes
    there stays after it ends; read_only_paths are bound read-only. Above them the checkout's git common directory is bound read-only, since
    every worktree of the repository shares it, or for a suite in
    SUITES_GIVEN_A_COPY_ON_WRITE_OVERLAY_OF_THE_REPOSITORY_GIT_DIRECTORY is a
    copy-on-write overlay, and so is a linked worktree's `.git` file, which names the
    git directory every later git command in the checkout uses. Every directory this
    account can create a file in is an empty tmpfs, and so is the directory of a
    listening socket left visible. The sandbox gets a network of its own, unless the
    suite is in SUITES_WHOSE_TEST_SANDBOX_SHARES_THE_MACHINE_NETWORK.

    Raises SignalSandboxCouldNotStart when the checkout's git common directory cannot be
    found, since the suite would then be able to write it."""
    arguments = []
    if suite not in SUITES_WHOSE_TEST_SANDBOX_SHARES_THE_MACHINE_NETWORK:
        arguments.append("--unshare-net")
    # bwrap mounts in order and a later mount hides what an earlier one put beneath it, so
    # every broad cover comes first; then each path the suite reads or writes, a path
    # before any path inside it, so a read-only path inside a writable one stays read-only
    # and a writable one inside a read-only one stays writable; then the git directory's
    # protection over the checkout.
    arguments += broad_covers_of_one_suites_test_sandbox()
    binds = []
    for paths, bind in (((checkout,), "--tmp-overlay"), (writable_paths, "--bind"),
                        (read_only_paths, "--ro-bind")):
        for path in paths:
            real = os.path.realpath(path)
            binds.append((bind, real, real))
            given = os.path.abspath(path)
            if given != real:
                binds.append((bind, real, given))
    for bind, source, place in sorted(binds, key=lambda entry: len(Path(entry[2]).parts)):
        # A checkout reached under two names gets one overlay under each, so a write under
        # one name is not seen under the other; both are gone after the suite.
        arguments += (["--overlay-src", source, "--tmp-overlay", place]
                      if bind == "--tmp-overlay" else [bind, source, place])
    real_checkout = Path(os.path.realpath(checkout))
    common = git_common_directory_of_checkout(real_checkout)
    if common is None or not os.path.isdir(common):
        raise SignalSandboxCouldNotStart(
            f"the git common directory of the checkout {real_checkout} could not be found "
            f"(git rev-parse --git-common-dir named {common!r}), so it could not be kept "
            f"read-only inside the test sandbox")
    # A bind made after the checkout's does not show under a second name the checkout was
    # bound at, so each protection is made under every name the checkout has.
    given_checkout = Path(os.path.abspath(checkout))
    names = [real_checkout] + ([given_checkout] if given_checkout != real_checkout else [])

    def under_each_name(path):
        path = Path(path)
        if not path.is_relative_to(real_checkout):
            return [str(path)]
        return [str(name / path.relative_to(real_checkout)) for name in names]

    for place in under_each_name(common):
        if suite in SUITES_GIVEN_A_COPY_ON_WRITE_OVERLAY_OF_THE_REPOSITORY_GIT_DIRECTORY:
            arguments += ["--overlay-src", common, "--tmp-overlay", place]
        else:
            arguments += ["--ro-bind", common, place]
    git_file = real_checkout / ".git"
    if git_file.is_file() and not git_file.is_symlink():
        for place in under_each_name(git_file):
            arguments += ["--ro-bind", str(git_file), place]
    return arguments


def broad_covers_of_one_suites_test_sandbox():
    """The bwrap arguments that hide whole directories and listening sockets in a test
    sandbox, to come before every bind of a path the suite needs."""
    arguments = []
    for directory in directories_this_account_can_create_files_in_hidden_in_test_sandbox():
        arguments += ["--tmpfs", directory]
    # A socket left visible, made by a service in a directory this account cannot write,
    # is hidden with its whole directory, so one the service makes again there stays hidden.
    for path in listening_unix_sockets_the_test_sandbox_would_show(
            hidden=directories_hidden_whole_in_test_sandbox()):
        directory = os.path.dirname(path)
        if directory in TEST_SANDBOX_DIRECTORIES_WHERE_A_LISTENING_SOCKET_IS_COVERED_BY_AN_EMPTY_FILE_NOT_HIDDEN_WHOLE:
            arguments += ["--ro-bind", empty_file_bound_over_a_listening_socket_in_test_sandbox(),
                          path]
        else:
            arguments += ["--tmpfs", directory]
    return arguments


def listening_unix_sockets_the_test_sandbox_would_show(proc_net_unix="/proc/net/unix",
                                                      unreachable=None,
                                                      hidden=TEST_SANDBOX_PRIVATE_DIRECTORY_PATHS_NOT_SCANNED_FOR_WRITABLE_DIRECTORIES):
    """Each listening Unix socket on this machine outside the directories in hidden.

    A read-only mount does not stop a connection to a socket, so each left visible is
    hidden too. A socket this program cannot lstat is left out, since a suite, running as
    the same account with fewer rights, cannot reach it either; each such socket and its
    error is appended to unreachable, when given. A socket gone before the lstat is left
    out too."""
    found = []
    try:
        rows = Path(proc_net_unix).read_text().splitlines()[1:]
    except OSError as error:
        raise SignalSandboxCouldNotStart(
            f"{proc_net_unix}, the list of this machine's Unix sockets, could not be read, so "
            f"the sockets a suite could connect to could not be covered: {error}") from error
    for row in rows:
        fields = row.split()
        if len(fields) < 8 or not int(fields[3], 16) & 0x10000 or not fields[7].startswith("/"):
            continue
        real = os.path.realpath(fields[7])
        if any(real == top or real.startswith(top + "/") for top in hidden):
            continue
        try:
            if stat.S_ISSOCK(os.lstat(real).st_mode) and real not in found:
                found.append(real)
        except FileNotFoundError:
            continue
        except OSError as error:
            if unreachable is not None:
                unreachable.append(f"{real} ({error.strerror})")
    return found


def uncovered_listening_sockets_report_line_or_none(proc_net_unix="/proc/net/unix"):
    """The report's line naming listening sockets the test sandbox does not hide, because this program cannot reach them."""
    unreachable = []
    listening_unix_sockets_the_test_sandbox_would_show(
        proc_net_unix, unreachable, hidden=directories_hidden_whole_in_test_sandbox())
    if not unreachable:
        return None
    names = sorted(set(unreachable))
    if len(names) == 1:
        start = "a listening socket that the test sandbox does not hide, because this program cannot reach it"
    else:
        start = "listening sockets that the test sandbox does not hide, because this program cannot reach them"
    return f"{start} and so neither can a suite: {', '.join(names)}; the run goes on, and nothing needs doing"


def command_prefix_starting_one_suite_in_its_test_sandbox(sandbox_prefix, checkout, writable_paths=(),
                                                         suite=None, read_only_paths=()):
    """The sandbox prefix with one suite's test sandbox added under bwrap."""
    if not does_signal_sandbox_report_killed_suite_as_exit_code_128_plus_signal(sandbox_prefix):
        return tuple(sandbox_prefix)
    return (*sandbox_prefix,
            *bwrap_arguments_for_one_suites_test_sandbox(checkout, writable_paths, suite,
                                                         read_only_paths))


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
            f"`bwrap {' '.join(TEST_SANDBOX_BWRAP_ARGUMENTS_SHARED_BY_EVERY_SUITE)} true` "
            f"works on this machine, and report what it prints to the user.\n"
            f"On macOS, report the reason above to the user: the suites need "
            f"{SIGNAL_SANDBOX_MACOS_SANDBOX_EXEC} to refuse their signals to "
            f"processes outside the sandbox.")


def signal_sandbox_line(prefix, unconfined_because):
    if does_signal_sandbox_report_killed_suite_as_exit_code_128_plus_signal(prefix):
        return f"each suite runs in its own test sandbox: {' '.join(prefix)}"
    if prefix:
        return (f"each suite runs in a sandbox that refuses its signals to any process "
                f"outside it: {' '.join(prefix)}")
    if unconfined_because:
        return (f"suites run WITHOUT the signal sandbox, so a stray signal can reach "
                f"any process of this account: {unconfined_because}")
    return "suites run inside the signal sandbox this run was started in"


TEST_SANDBOX_DID_NOT_START_NOTE = (
    f"\n{PROGRAM}: the suite did not start: bwrap could not build its test sandbox, for the "
    f"reason bwrap printed above.\n"
    f"If bwrap says it can't create a file at a path, that path is a socket or credential "
    f"file that disappeared between this program's scan and the sandbox's start: run the "
    f"suite again.\n"
    f"Otherwise, report bwrap's message to the user.\n")


def suite_process_started(process, status_read, note_suite_process):
    """Record the process whose end ends the suite: bwrap's namespace init, or the suite itself.

    Returns False when bwrap failed before starting the suite, True when it started it,
    and None when there is no bwrap status to tell."""
    if status_read is None:
        note_suite_process(process.pid, namespace_init=False)
        return None
    # bwrap's first status line names the init of the suite's PID namespace; when
    # that init ends, the kernel ends every process inside it.
    line = status_read.readline()
    try:
        init = json.loads(line)["child-pid"]
    except (ValueError, KeyError, TypeError):
        # bwrap failed before starting the suite; the outer bwrap is all there is.
        note_suite_process(process.pid, namespace_init=False)
        return False
    note_suite_process(init, namespace_init=True)
    return True


def run_one_suite(top, interpreter, suite, log_dir, recorder=None, sandbox_prefix=(),
                  note_suite_process=None, in_cgroup_scope=False, nice=False, platform=None,
                  time_limit=None, run_stop_signals=None):
    """Run one suite; return its result, on Linux with each case line it printed timed.

    time_limit is (limit seconds, recorded seconds or None) from
    suite_timeout_and_the_recorded_seconds_it_came_from(); a suite still running at its limit
    has its process group killed, and its result carries "timeout". Once run_stop_signals,
    a list a signal handler appends to, is not empty, the suite is killed the same way,
    and its result carries "stopped by".

    With in_cgroup_scope, the suite runs in a cgroup scope of its own and its CPU seconds
    and peak memory are read from there; with nice, at low priority. Inside its test
    sandbox the suite may write only the checkout and its own recorded-input files: the
    run's log directory, where this program writes, stays out of its reach."""
    platform = sys.platform if platform is None else platform
    log_file = log_path_for(log_dir, suite)
    environment = launch_environment_for_a_test_suite_with_git_redirecting_agent_session_attendance_and_credential_variables_removed()
    command = ["sh", suite] if is_shell_test_suite(suite) else [interpreter, "-u", suite]
    writable_paths, read_only_paths = [], []
    if recorder is not None:
        recorder_dir, recording_dir, strace = recorder
        hook_log, strace_dir = recording_paths_for(recording_dir, suite)
        # The audit hook appends; clear old logs so earlier reads do not count for this run.
        hook_log.unlink(missing_ok=True)
        shutil.rmtree(strace_dir, ignore_errors=True)
        # Made here, so the sandbox binds this file itself, which the suite cannot swap
        # for a symbolic link while it is bound.
        os.close(os.open(hook_log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644))
        writable_paths.append(hook_log)
        read_only_paths.append(recorder_dir)
        environment["PYTHONPATH"] = os.pathsep.join(
            [str(recorder_dir)] + [entry for entry in
                                   environment.get("PYTHONPATH", "").split(os.pathsep) if entry])
        environment[RECORDED_INPUTS_LOG_VARIABLE] = str(hook_log)
        environment[RECORDED_INPUTS_CHECKOUT_VARIABLE] = str(top)
        if strace is not None:
            strace_dir.mkdir(parents=True, exist_ok=True)
            writable_paths.append(strace_dir)
            command = [strace, "-f", "-ff", "--seccomp-bpf", "-z", "-qq", "-y", "-s", "4096",
                       "-e", "trace=%file", "-e", "signal=none",
                       "-o", str(strace_dir / "trace"), *command]
    if suite in SUITES_RUN_WITHOUT_ANY_SANDBOX:
        sandbox_prefix = ()
    # The test sandbox is built from Linux's /proc and bwrap, so nothing of it is built
    # on another platform, whatever the prefix.
    if platform.startswith("linux"):
        if does_signal_sandbox_report_killed_suite_as_exit_code_128_plus_signal(sandbox_prefix):
            read_only_paths += paths_one_suite_launch_needs_shown_read_only_in_test_sandbox(
                [interpreter])
        sandbox_prefix = command_prefix_starting_one_suite_in_its_test_sandbox(
            sandbox_prefix, top, writable_paths, suite, read_only_paths)
    status_read = status_write = None
    if sandbox_prefix and note_suite_process is not None:
        status_read_fd, status_write = os.pipe()
        status_read = os.fdopen(status_read_fd, "r")
        sandbox_prefix = (sandbox_prefix[0], "--json-status-fd", str(status_write),
                          *sandbox_prefix[1:])
    resource_prefix = ()
    statistics = None
    if in_cgroup_scope:
        # A file with no name, so nothing a suite can reach stands where the counters go.
        statistics = tempfile.TemporaryFile()
        resource_prefix += command_prefix_running_one_suite_in_its_cgroup_scope(
            statistics.fileno(),
            does_signal_sandbox_report_killed_suite_as_exit_code_128_plus_signal(sandbox_prefix))
    if nice:
        resource_prefix += ("nice", "-n", str(TEST_SUITE_NICE_INCREMENT))
    # bwrap, and the shell that keeps the cgroup counters, exit 128+N when the suite is
    # killed by signal N.
    exit_reports_signal_as_128_plus = (
        does_signal_sandbox_report_killed_suite_as_exit_code_128_plus_signal(sandbox_prefix)
        or in_cgroup_scope)
    command = [*resource_prefix, *sandbox_prefix, *command]
    passed = tuple(descriptor for descriptor in
                   (status_write, statistics.fileno() if statistics is not None else None)
                   if descriptor is not None)
    cases = []
    copy_failures = []
    output_note = None
    # Case lines are timed on Linux only; elsewhere the output goes to the log as it always did.
    time_case_lines = platform.startswith("linux")
    started = time.monotonic()
    copier = None
    timed_out = stopped_by = None
    try:
        log = open_for_writing_without_following_symlinks(log_file, binary=True)
        try:
            process = subprocess.Popen(
                command, cwd=str(top), env=environment, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE if time_case_lines else log,
                stderr=subprocess.STDOUT, pass_fds=passed,
                # Its own process group, so a timeout can kill everything it started.
                start_new_session=True)
        except BaseException:
            log.close()
            raise
        if time_case_lines:
            # The copier closes the log when the suite's output ends.
            copier = threading.Thread(
                target=copy_suite_output_to_log_noting_each_case_line,
                args=(process.stdout, log, started, cases, copy_failures), daemon=True)
            copier.start()
        else:
            log.close()
        if status_write is not None:
            os.close(status_write)
            status_write = None
        sandbox_started = None
        if note_suite_process is not None:
            sandbox_started = suite_process_started(process, status_read, note_suite_process)
        deadline = None if time_limit is None else started + time_limit[0]
        while True:
            wait_seconds = None if run_stop_signals is None else RUN_STOP_SIGNAL_CHECK_SECONDS
            if deadline is not None:
                left = max(0.0, deadline - time.monotonic())
                wait_seconds = left if wait_seconds is None else min(wait_seconds, left)
            try:
                exit_code = process.wait(wait_seconds)
                break
            except subprocess.TimeoutExpired:
                pass
            if run_stop_signals:
                stopped_by = run_stop_signals[0]
            elif deadline is not None and time.monotonic() >= deadline:
                timed_out = time_limit
            else:
                continue
            kill_test_suite_process_group(process)
            exit_code = process.wait()
            break
        seconds = time.monotonic() - started
        if copier is not None:
            copier.join(TEST_SUITE_OUTPUT_DRAIN_SECONDS)
            if copier.is_alive():
                output_note = (f"a process the suite started still held its output open "
                               f"{TEST_SUITE_OUTPUT_DRAIN_SECONDS} s after the suite ended; "
                               f"its log may grow after this report")
    finally:
        if status_write is not None:
            os.close(status_write)
        # Closed only after bwrap exits: bwrap writes its exit status to this pipe last.
        if status_read is not None:
            status_read.close()
    if copy_failures:
        raise OSError(f"the log of {suite}, {log_file}, could not be written while the suite "
                      f"ran, so its output is incomplete: {copy_failures[0]}")
    if sandbox_started is False:
        with open_for_writing_without_following_symlinks(log_file, append=True) as log:
            log.write(TEST_SANDBOX_DID_NOT_START_NOTE)
    if exit_reports_signal_as_128_plus and 128 < exit_code <= 128 + SIGNAL_NUMBER_LIMIT:
        exit_code = -(exit_code - 128)
    result = {
        "suite": suite,
        "exit": exit_code,
        "seconds": seconds,
        "log": log_file,
        "skips": skipped_case_lines(log_file),
        "cases": list(cases),
        "output_note": output_note,
        "cpu_seconds": None,
        "peak_memory_bytes": None,
        "resources_note": None,
    }
    # A suite that ended on its own as its limit passed keeps its own verdict.
    if timed_out is not None and exit_code != 0:
        result["timeout"] = {"limit": timed_out[0], "recorded": timed_out[1]}
    if stopped_by is not None and exit_code != 0:
        result["stopped by"] = stopped_by
    if statistics is not None:
        with statistics:
            statistics.seek(0)
            counters = statistics.read().decode("utf-8", "replace")
        result["cpu_seconds"], result["peak_memory_bytes"], result["resources_note"] = \
            cpu_seconds_and_peak_memory_from_suite_cgroup_statistics(counters)
    return result


def kill_test_suite_process_group(process):
    """SIGKILL the suite's process group, which every process it started stays in unless
    it starts a session of its own.

    In a test sandbox the group holds the init of the suite's PID namespace, since bwrap
    is not given --new-session, and the init's end ends every process in the namespace.
    Called before the suite's first process is reaped, so its process group id is still
    its own."""
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGKILL)


def unescaped_strace_string(text):
    return codecs.escape_decode(text.encode("utf-8"))[0].decode("utf-8", "surrogateescape")


def paths_strace_saw(strace_dir):
    """Every absolute path a traced process opened, statted or executed."""
    seen = set()
    for trace_file in sorted(strace_dir.glob("trace*")):
        try:
            text = read_text_without_following_symlinks(trace_file)
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
    # A suite can write the checkout's .gitattributes; --no-filters runs no filter it names.
    answer = subprocess.run(["git", "-C", str(top), "hash-object", "--no-filters", "--stdin-paths"],
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
        hook_lines = read_text_without_following_symlinks(hook_log).splitlines()
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
        "skipped_cases_this_machine_cannot_run": sum(
            1 for line in result["skips"] if SKIPPED_CASE_LINE_THIS_MACHINE_CANNOT_RUN.match(line)),
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
    head = git(top, "rev-parse", "--verify", "--quiet", "HEAD")
    if head.returncode == 1:
        return Path(given).expanduser() / "no-commit"
    roots = git(top, "rev-list", "--max-parents=0", "HEAD") if head.returncode == 0 else head
    if roots.returncode != 0 or not roots.stdout.split():
        raise CouldNotRun(
            f"{PROGRAM}: not run — git could not list the root commits of HEAD in {top}, so "
            f"this run cannot find its directory of recorded suite inputs, which is named "
            f"after a root commit of HEAD: "
            f"{first_line_of_error(roots) or 'git printed no error'}\n"
            + git_failure_next_step_lines(Path(__file__).name))
    return Path(given).expanduser() / min(roots.stdout.split())[:16]


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


def recorded_passing_seconds_or_none(recording):
    """The seconds of a recorded run that passed, or None when there are none to use."""
    # A run that did not pass may have stopped early, so its seconds may understate the suite.
    if not isinstance(recording, dict) or recording.get("exit") != 0:
        return None
    seconds = recording.get("seconds")
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
        return None
    return seconds


def suite_timeout_and_the_recorded_seconds_it_came_from(recording):
    """(the suite's time limit in seconds, the recorded seconds it came from or None)."""
    recorded = recorded_passing_seconds_or_none(recording)
    if recorded is None:
        return TEST_SUITE_TIMEOUT_WITHOUT_PASSING_RECORDING_SECONDS, None
    return (max(TEST_SUITE_TIMEOUT_FLOOR_SECONDS,
                TEST_SUITE_TIMEOUT_MULTIPLE_OF_RECORDED_SECONDS * recorded), recorded)


def suites_longest_recorded_first(suites, recordings):
    """Return the suites in starting order: no usable duration first, then longest first."""
    def starting_order(suite):
        seconds = recorded_passing_seconds_or_none(recordings.get(suite))
        return (0, 0.0) if seconds is None else (1, -seconds)
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
    if untracked.returncode != 0:
        raise CouldNotRun(
            f"{PROGRAM}: not run — git ls-files --others failed in {top}: "
            f"{untracked.stderr.strip()}\n"
            + git_failure_next_step_lines(Path(__file__).name))
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
    marked = recording.get("skipped_cases_this_machine_cannot_run")
    if not isinstance(marked, int) or isinstance(marked, bool):
        marked = 0
    if not counted or skipped != marked:
        # A skipped case's reads were never recorded, and a skip can hide a run disturbed by another.
        # A machine change that lets a marked case run does not select the suite by itself.
        return True, ("its last recorded run skipped "
                      + (f"{skipped - marked} case(s) without the mark "
                         f"{SKIPPED_CASE_THIS_MACHINE_CANNOT_RUN_MARKER}" if counted
                         else "an unrecorded number of cases")
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


def why_suite_failed(result):
    """What a failed suite's line says after its path: its timeout, or how it exited."""
    if result.get("stopped by"):
        return f"killed when the run was stopped by {result['stopped by']}"
    timeout = result.get("timeout")
    if timeout is None:
        return describe_exit(result["exit"])
    recorded = timeout["recorded"]
    multiple = TEST_SUITE_TIMEOUT_MULTIPLE_OF_RECORDED_SECONDS
    if recorded is None:
        source = " from no passing recording"
    elif timeout["limit"] > multiple * recorded:
        source = f", the floor, more than {multiple} times recorded {recorded:.0f}s"
    else:
        source = f", {multiple} times recorded {recorded:.0f}s"
    return f"TIMEOUT after {result['seconds']:.0f}s (limit {timeout['limit']:.0f}s{source})"


def suite_line(result):
    detail = f"{result['seconds']:.1f}s"
    if result["skips"]:
        detail += f", {len(result['skips'])} skipped"
    if result.get("admitted"):
        detail += (f", {'without any sandbox' if result['kind'] != 'test sandbox' else 'test sandbox'}"
                   f", waited {result['admission_wait']:.1f}s to start")
        if result.get("cpu_seconds") is not None:
            detail += (f", {result['cpu_seconds']:.1f} CPU s, peak "
                       f"{result['peak_memory_bytes'] / 10**6:.0f} MB")
    if result["exit"] == 0:
        return f"PASS {result['suite']} ({detail})"
    return f"FAIL {result['suite']} {why_suite_failed(result)} ({detail})"


class Report:
    """Every line goes to stdout at once and to test-run-report.txt in the log directory."""

    def __init__(self, report_file):
        self.lock = threading.Lock()
        self.file = open_for_writing_without_following_symlinks(report_file)

    def line(self, text):
        with self.lock:
            print(text, flush=True)
            self.file.write(text + "\n")
            self.file.flush()

    def close(self):
        self.file.close()


def machine_lock_refusal(lock_file, holder, wait_seconds):
    """The refusal printed when this run could not take the machine's lock."""
    if wait_seconds > 0:
        return (f"{PROGRAM}: not run — waited {wait_seconds:g} s for {lock_file}, the lock "
                f"that keeps test runs on one machine apart, and it was still held by "
                f"{holder}.\n"
                f"If you started this program under flock on that lock, that flock is the "
                f"holder: run this program without flock, since it takes the lock itself.\n"
                f"Otherwise, tell the user which process holds the lock, and do not run "
                f"this again until the lock is released.")
    return (f"{PROGRAM}: not run — another run holds {lock_file}: {holder}.\n"
            f"To wait for the lock, run this again with --wait-for-lock-seconds "
            f"{MACHINE_LOCK_WAIT_SECONDS_SUGGESTED}, instead of retrying in a loop: a "
            f"process waiting on the lock always gets the lock before a process that "
            f"retries.")


def restore_signal_handlers(replaced):
    """Put back the handlers a run replaced, so a stop signal after its suites acts as before."""
    while replaced:
        stop_signal, handler = replaced.popitem()
        signal.signal(stop_signal, handler)


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        prog=PROGRAM, description="Run every *-test.py and *-test.sh suite git lists in a checkout.")
    parser.add_argument("--checkout", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("-j", dest="jobs", type=int)
    parser.add_argument("--log-dir")
    parser.add_argument("--lock-file", default=str(DEFAULT_LOCK_FILE))
    parser.add_argument("--wait-for-lock-seconds", type=float, default=0)
    parser.add_argument("--only-suites-whose-recorded-inputs-changed-since",
                        dest="changed_since", metavar="COMMIT")
    parser.add_argument("--recorded-inputs-directory",
                        default=str(DEFAULT_RECORDED_INPUTS_DIRECTORY))
    arguments = parser.parse_args(argv)
    if arguments.jobs is not None and arguments.jobs < 1:
        parser.error("-j takes a whole number of at least 1")
    if arguments.wait_for_lock_seconds < 0:
        parser.error("--wait-for-lock-seconds takes a number of seconds of at least 0")
    return arguments


def suites_run_at_once(jobs_given, suites_to_run, cores, admission_decides=False):
    """-j as given; otherwise one suite per core, never more than the suites to run.

    Where admission decides when each suite starts, the default is every suite to run,
    up to admission's ceiling."""
    if jobs_given is not None:
        return jobs_given
    if admission_decides:
        return max(1, min(suites_to_run, TEST_SUITE_ADMISSION_SUITES_RUNNING_AT_ONCE_CEILING))
    # At least 1: the thread pool refuses zero workers when nothing is selected.
    return max(1, min(cores or SUITES_RUN_AT_ONCE_WHEN_CORE_COUNT_UNKNOWN, suites_to_run))


def main(argv=None, platform=None):
    platform = sys.platform if platform is None else platform
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
        sandbox_prefix, unconfined_because = signal_sandbox(platform=platform)
    except SignalSandboxCouldNotStart as error:
        print(signal_sandbox_refusal(error), file=sys.stderr)
        return EXIT_COULD_NOT_RUN

    # In a test sandbox of its own each suite shares no machine state with another run's
    # suites, so runs overlap, and admission decides when each suite starts.
    in_test_sandboxes = platform.startswith("linux") and \
        does_signal_sandbox_report_killed_suite_as_exit_code_128_plus_signal(sandbox_prefix)
    lock_handle = None
    previous_holder = ""
    seconds_waiting_for_lock = 0.0
    if in_test_sandboxes:
        psutil, refusal = psutil_imported_or_why_not()
        if psutil is None:
            print(refusal, file=sys.stderr)
            return EXIT_COULD_NOT_RUN
    else:
        if arguments.wait_for_lock_seconds > 0:
            # A caller waiting under a timeout of its own sees why nothing has happened yet.
            print(f"{PROGRAM}: waiting up to {arguments.wait_for_lock_seconds:g} s for "
                  f"{arguments.lock_file}", file=sys.stderr, flush=True)
        lock_wait_started = time.monotonic()
        lock_handle, holder, previous_holder = take_machine_lock(
            Path(arguments.lock_file), top, arguments.wait_for_lock_seconds)
        seconds_waiting_for_lock = time.monotonic() - lock_wait_started
        if lock_handle is None:
            print(machine_lock_refusal(arguments.lock_file, holder,
                                       arguments.wait_for_lock_seconds), file=sys.stderr)
            return EXIT_LOCKED

    log_dir_handle = run_record = readings = None
    signal_handlers_replaced = {}
    try:
        # Read again under the lock: the checkout may have changed while this run waited,
        # and the commit this run reports is read under the lock too.
        try:
            suites = suites_listed_by_git(top)
            sandbox_lists, sandbox_lists_source = (
                suite_sandbox_lists_read_from_checkout_under_test(top))
        except CouldNotRun as refusal:
            print(refusal, file=sys.stderr)
            return EXIT_COULD_NOT_RUN
        globals().update(sandbox_lists)
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
        if platform.startswith("linux"):
            run_record = RunRecord(run_records_directory_for_lock_file(arguments.lock_file), log_dir,
                                   log_dir_is_temporary=not arguments.log_dir)
        if lock_handle is not None:
            name_log_directory_in_lock(lock_handle, log_dir)
            clean_up_lines = clean_up_after_earlier_runs(Path(arguments.lock_file),
                                                         previous_holder, platform)
        else:
            # Runs overlap here, so one cleans up at a time; a live run's files are never touched.
            with lock_held_while_cleaning_up_after_earlier_runs(Path(arguments.lock_file)):
                clean_up_lines = clean_up_after_earlier_runs(Path(arguments.lock_file),
                                                             previous_holder, platform)
        commit, state = commit_and_state(top)
        try:
            recordings_dir = recordings_directory_for(arguments.recorded_inputs_directory, top)
        except CouldNotRun as refusal:
            print(refusal, file=sys.stderr)
            return EXIT_COULD_NOT_RUN
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
        jobs = suites_run_at_once(arguments.jobs, len(chosen), os.cpu_count(),
                                  admission_decides=in_test_sandboxes)
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
        report.line(f"{SUITE_SANDBOX_LISTS_SOURCE_LINE_PREFIX}{sandbox_lists_source}")
        if lock_handle is not None and arguments.wait_for_lock_seconds > 0:
            report.line(f"{MACHINE_LOCK_WAITED_LINE_PREFIX}{seconds_waiting_for_lock:.0f}")
        if sandbox_prefix:
            for suite in chosen:
                if suite in SUITES_RUN_WITHOUT_ANY_SANDBOX:
                    report.line(f"{suite} runs WITHOUT the signal sandbox: "
                                f"{SUITES_RUN_WITHOUT_ANY_SANDBOX[suite]}")
        if in_test_sandboxes:
            uncovered = uncovered_listening_sockets_report_line_or_none()
            if uncovered is not None:
                report.line(uncovered)
        admission = None
        cgroup_unavailable_because = None
        if in_test_sandboxes:
            try:
                readings = TestSuiteAdmissionMachineCpuAndMemoryReadingsSampler(
                    psutil, log_dir / MACHINE_CPU_AND_MEMORY_READINGS_FILE_NAME)
                readings.start()
                admission = MachineWideTestSuiteAdmission(
                    test_suite_admission_directory_for_lock_file(arguments.lock_file), readings,
                    report.line)
            except MachineWideTestSuiteAdmissionCouldNotDecide as error:
                report.line(f"{PROGRAM}: not run — admission could not start: {error}")
                report.line("Fix what it names, then run this again.")
                report.close()
                return EXIT_COULD_NOT_RUN
            report.line(
                f"each suite starts only while the machine's CPU use over "
                f"{TEST_SUITE_ADMISSION_CPU_AVERAGE_SECONDS} s is under "
                f"{TEST_SUITE_ADMISSION_CPU_PERCENT_BELOW}% and its available memory is above "
                f"{TEST_SUITE_ADMISSION_AVAILABLE_MEMORY_BYTES_ABOVE / 10**9:g} GB, at most "
                f"{TEST_SUITE_ADMISSION_STARTS_PER_SECOND} starts a second and "
                f"{TEST_SUITE_ADMISSION_SUITES_RUNNING_AT_ONCE_CEILING} suites at once on this "
                f"machine, at nice {TEST_SUITE_NICE_INCREMENT}; readings every "
                f"{MACHINE_READINGS_INTERVAL_SECONDS} s in "
                f"{log_dir / MACHINE_CPU_AND_MEMORY_READINGS_FILE_NAME}")
            cgroup_unavailable_because = why_test_suites_cannot_run_in_cgroup_scopes_on_this_machine_or_none()
            if cgroup_unavailable_because is not None:
                report.line(f"suites run without a cgroup scope each, so their CPU seconds "
                            f"and peak memory are not recorded: {cgroup_unavailable_because}")
        for line in clean_up_lines:
            report.line(line)
        note_suite_process = run_record.note_suite_process if run_record else None
        if changed_since is not None:
            for suite, selected, why in selection:
                report.line(f"{'SELECTED' if selected else 'NOT SELECTED'} {suite}: {why}")

        run_stop_signals = []

        def run_admitted(suite, **options):
            if run_stop_signals:
                raise TestRunStoppedBeforeSuiteStarted(suite)
            options["run_stop_signals"] = run_stop_signals
            options["time_limit"] = suite_timeout_and_the_recorded_seconds_it_came_from(
                recordings.get(suite))
            outside = suite in SUITES_RUN_WITHOUT_ANY_SANDBOX
            kind = (f"without any sandbox: {SUITES_RUN_WITHOUT_ANY_SANDBOX[suite]}"
                    if outside and sandbox_prefix else
                    "test sandbox" if in_test_sandboxes else
                    "macOS sandbox" if platform == "darwin" and sandbox_prefix else
                    "no sandbox")
            if admission is None:
                result = run_one_suite(top, interpreter, suite, log_dir,
                                       sandbox_prefix=sandbox_prefix,
                                       note_suite_process=note_suite_process,
                                       platform=platform, **options)
                result.update(kind=kind, admission_wait=0.0)
                return result
            with admission.admitted(suite, without_any_sandbox=outside) as waited:
                result = run_one_suite(top, interpreter, suite, log_dir,
                                       sandbox_prefix=sandbox_prefix,
                                       note_suite_process=note_suite_process,
                                       in_cgroup_scope=cgroup_unavailable_because is None,
                                       nice=True, platform=platform, **options)
            result.update(kind=kind, admission_wait=waited, admitted=True)
            if cgroup_unavailable_because is not None:
                result["resources_note"] = cgroup_unavailable_because
            return result

        def run_and_record(suite):
            if is_shell_test_suite(suite):
                return run_admitted(suite)
            result = run_admitted(suite, recorder=recorder)
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

        def record_run_stop(signal_number, frame):
            # Only recorded here: the suites' threads and the loop below act on it where it
            # is safe, since raising inside subprocess code can leave a child unreaped.
            run_stop_signals.append(signal.Signals(signal_number).name)

        def ignore_run_stop(signal_number, frame):
            pass

        # A signal the runner was started with ignored, as under nohup, stays without
        # effect on the run; it gets a handler that does nothing rather than SIG_IGN,
        # because a handled signal starts each suite with its default action, while an
        # ignored one would pass on to every suite.
        for stop_signal in RUN_STOP_SIGNALS:
            handler = (ignore_run_stop if signal.getsignal(stop_signal) == signal.SIG_IGN
                       else record_run_stop)
            signal_handlers_replaced[stop_signal] = signal.signal(stop_signal, handler)
        with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
            running = [pool.submit(run_and_record, suite) for suite in chosen]
            pending = set(running)
            stop_acted_on = False
            while pending:
                done, pending = concurrent.futures.wait(
                    pending, timeout=RUN_STOP_SIGNAL_CHECK_SECONDS,
                    return_when=concurrent.futures.FIRST_COMPLETED)
                if run_stop_signals and not stop_acted_on:
                    stop_acted_on = True
                    for waiting in running:
                        waiting.cancel()
                    if admission is not None:
                        admission.cancel()
                for finished in done:
                    if finished.cancelled():
                        continue
                    try:
                        result = finished.result()
                    except (TestRunStoppedBeforeSuiteStarted,
                            MachineWideTestSuiteAdmissionCancelled):
                        if run_stop_signals:
                            continue
                        raise
                    except (MachineWideTestSuiteAdmissionCouldNotDecide, SignalSandboxCouldNotStart,
                            OSError) as error:
                        for waiting in running:
                            waiting.cancel()
                        # A suite already waiting for admission is running as far as its future knows.
                        if admission is not None:
                            admission.cancel()
                        what = ("admission failed" if isinstance(error, MachineWideTestSuiteAdmissionCouldNotDecide)
                                else "a suite's test sandbox could not be built"
                                if isinstance(error, SignalSandboxCouldNotStart)
                                else "a suite could not be started")
                        report.line(f"{PROGRAM}: not run to the end — {what}: {error}")
                        report.line("Fix what it names, then run this again. The suites already "
                                    "running finish first.")
                        report.close()
                        return EXIT_COULD_NOT_RUN
                    results.append(result)
                    report.line(suite_line(result))
                    if result.get("output_note"):
                        report.line(f"{result['suite']}: {result['output_note']}")
        restore_signal_handlers(signal_handlers_replaced)
        # A stop that came after the last suite ended cut nothing short, so the run is
        # reported and recorded as usual.
        if run_stop_signals and (len(results) < len(chosen)
                                 or any(result.get("stopped by") for result in results)):
            report.line(f"{PROGRAM}: not run to the end — stopped by {run_stop_signals[0]}. "
                        f"The process group of every suite still running was killed, which "
                        f"in a test sandbox ends every process the suite started; outside "
                        f"one, a process a suite started in a session of its own is not "
                        f"reached and may still be running. The suites not yet started "
                        f"were not run.")
            report.close()
            if run_record is not None:
                run_record.finish()
            return EXIT_COULD_NOT_RUN

        results.sort(key=lambda result: result["suite"])
        failed = [result for result in results if result["exit"] != 0]
        skipping = [result for result in results if result["skips"]]
        if failed:
            report.line("")
            report.line(f"{len(failed)} failed:")
            for result in failed:
                report.line(f"FAIL {result['suite']} {why_suite_failed(result)}"
                            f" — log {result['log']}")
        if skipping:
            report.line("")
            report.line("skipped cases:")
            for result in skipping:
                for skip in result["skips"]:
                    report.line(f"{result['suite']}: {skip}")
        records_failed = False
        if admission is not None:
            waits = [result["admission_wait"] for result in results]
            report.line(f"{ADMISSION_WAITED_LINE_PREFIX}{sum(waits):.0f} in all, the longest "
                        f"{max(waits, default=0.0):.0f}")
            # A reading that fails after the last admission reaches no admission decision.
            readings.stop()
            stopped_by = readings.failure_or_none()
            if stopped_by is not None:
                records_failed = True
                report.line(f"{PROGRAM}: the machine's readings stopped before the run ended: "
                            f"{stopped_by!r}")
                report.line(f"The suites' verdicts below stand, but "
                            f"{log_dir / MACHINE_CPU_AND_MEMORY_READINGS_FILE_NAME} is cut "
                            f"short, so this run exits 2 if every suite passed, and 1 if any "
                            f"failed. Fix what it names, then run this again.")
        # The case times, suite resources and failure history come with the test sandboxes.
        if admission is not None:
            try:
                write_case_times_suite_resources_and_junit_xml_of_run(log_dir, results)
                append_test_case_failure_history(
                    Path(arguments.recorded_inputs_directory).expanduser()
                    / TEST_CASE_FAILURE_HISTORY_FILE_NAME,
                    top, commit, branch_of_checkout(top), log_dir, results)
            except OSError as error:
                records_failed = True
                report.line(f"{PROGRAM}: the run's case times, suite resources, JUnit XML or "
                            f"failure history could not be written: {error}")
                report.line("The suites' verdicts below stand, but their records are "
                            "missing, so this run exits 2 if every suite passed, and 1 if "
                            "any failed. Fix what it names, then run this again.")
            else:
                report.line(f"case times, suite resources and JUnit XML in {log_dir}")
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
        # A failing suite outranks missing records, since a caller that reads exit 2 as
        # "no verdict" would otherwise let a failure through.
        if failed:
            return EXIT_SOME_FAILED
        return EXIT_COULD_NOT_RUN if records_failed else EXIT_ALL_PASSED
    finally:
        restore_signal_handlers(signal_handlers_replaced)
        if readings is not None:
            readings.stop()
        if log_dir_handle is not None:
            log_dir_handle.close()
        if lock_handle is not None:
            lock_handle.close()


if __name__ == "__main__":
    sys.exit(main())
