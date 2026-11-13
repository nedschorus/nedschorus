#!/usr/bin/env python3
"""Run nc-mutation-testing with cosmic-ray on the lines a change made, in its quick or its full pass, and print the survivors.

Usage:
  scripts/mutation-testing-changed-lines-quick-or-full-pass-survivors.py
      (--quick-mutation-pass | --full-mutation-pass)
      (--pull-request N | --head COMMIT --base COMMIT)
      [--checkout DIR] [--cosmic-ray-venv DIR] [--python INTERPRETER]
      [--recorded-inputs-directory DIR] [--mutant-timeout-seconds S]
      [--lock-file PATH] [--survived-and-errored-mutants-json-file PATH]
      [--parallel-mutant-workers N] [--cosmic-ray-sessions-directory-kept-to-resume DIR]
      [--mutants-run-at-most-shared-evenly-among-changed-files N]
      [--no-mutant-started-after-unix-time UNIX_TIME]
  scripts/mutation-testing-changed-lines-quick-or-full-pass-survivors.py
      --recorded-mutant-killed-check DIFF_FILE [DIFF_FILE ...] [--head COMMIT]
      [--checkout DIR] [--python INTERPRETER]
      [--recorded-inputs-directory DIR] [--lock-file PATH]
      [--recorded-mutant-killed-check-verdicts-json-file-to-write PATH]

The head is checked out in a detached scratch worktree, because cosmic-ray
edits each mutant into the file on disk; the worktree is removed afterwards,
whatever happens. Each changed Python file that is not itself a suite is
mutated on its changed lines only, against the merge base. A line that ends
in a `# pragma: no mutate` comment is never mutated: that comment records
why no test can kill the mutants of its line.

THE FULL MUTATION PASS mutates every changed line, and tests each mutant
with every suite whose recorded inputs read that file (the recordings
scripts/run-all-test-suites.py keeps), plus the file's sibling
`<name>-test.py` or `<name>-test.sh` when there is one.

THE QUICK MUTATION PASS mutates only the changed lines that are
failure-handling code: the changed lines inside an `except` clause,
or inside an `if` statement, `while` loop or conditional expression whose test
reads an exit code (a name or attribute named `returncode`, or ending in
`exit_code` or `exit_status`), each such clause or statement counted from its
first line to its last. A clause's or statement's lines that the change did
not touch are not mutated.
A changed file with no changed line of
failure-handling code is not mutated, and is printed as NO FAILURE-HANDLING
CHANGE. The quick mutation pass's mutants are tested with the full mutation
pass's suites less the
repository-wide checks, which check one rule across a whole class of the
repository's files and are listed in REPOSITORY_WIDE_CHECKS, and less
every suite whose recorded inputs read every Python file git tracked at the
commit the recording was made at. Those suites still run on the unmutated
code before a push and every day on main, and against mutants in the full
mutation pass.

The test command cosmic-ray runs, for the baseline on the unmutated head and
for each mutant, is this script, given
--cosmic-ray-test-command-run-test-suite-runner-stopped-after-seconds, a flag
this script writes into cosmic-ray's config and no caller gives, which runs
scripts/run-all-test-suites.py, the one beside this file, once, with its standard error sent to its standard
output, the only stream cosmic-ray records, so the runner's refusals reach this
script. That run is on the worktree the mutant is in, the test command's working
directory, given --only-suites-named with the file's
suites, --leave-recorded-inputs-and-failure-history-unchanged, so a mutant
changes no suite's recording, and --stop-at-first-failing-suite, so a mutant
one suite kills does not wait for the rest. The runner runs the suites in
parallel, each starting when the runner's admission lets it (on Linux in
nc-test-sandboxes, when the machine's CPU and memory have room: ADMISSION in the
runner's docstring), each in its signal sandbox and, on Linux with
bwrap, its nc-test-sandbox, each under its own time limit (see PER-SUITE TIMEOUT
in the runner's docstring), and passes on --python, --recorded-inputs-directory
and, when given, --lock-file. Where suites run without nc-test-sandboxes (macOS,
or Linux without bwrap), each of the runner's runs takes the machine's lock,
and the runner exits 3 without running a suite while another test run holds it.
On a mutant, that refusal judges no suite, so the mutant is printed as ERRORED
with the runner's refusal and the script goes on to the next mutant; on the
unmutated head it stops the script with exit 2.
When bwrap is on PATH but cannot start, the script exits 2 before making the
worktree.

LOG DIRECTORIES. Each run of the suite runner is given a --log-dir of its own
inside one directory per run of this script, made in the system temp
directory and named with TEST_SUITE_RUNNER_LOG_DIRECTORIES_PARENT_PREFIX. A
run's log directory is removed once its outcome is known, unless the script
reports that run's failure: a run on the unmutated head that fails, a mutant
printed as ERRORED, or a recorded mutant that could not be judged. A pass that
stops before a changed file's mutants are all judged, as on exit 2, keeps
every log directory of that file, and so does a file with an ERRORED mutant
whose output names no log directory, as when cosmic-ray stopped the run at its
own limit and recorded only "timeout". At the end,
that one directory is removed when it is empty, or when a stop signal ended
the script, since no one reads a stopped run's output, unless
--cosmic-ray-sessions-directory-kept-to-resume is given: a resumed run reports
the ERRORED mutants its kept sessions saved, with the log directories their
outputs name. Otherwise the script
names it on standard error, in a line opening with
TEST_SUITE_RUNNER_LOGS_KEPT_LINE_PREFIX, as holding the logs of the failures it
reported. At start, the script removes each such directory an earlier run left
that has not changed for TEST_SUITE_RUNNER_LOG_DIRECTORIES_PARENT_RETENTION_SECONDS,
two days. A log directory that cannot be removed is left there, and so named.

The limit on one run of the suites, per changed file, is the longest of its
suites' time limits, computed as the runner computes them from the
recordings, times the number of rounds the runner needs for them (the number
of suites divided by the number it runs at once, its suites_run_at_once(), the
same call the runner makes, rounded up), plus
TEST_SUITE_RUNNER_START_UP_SECONDS. --mutant-timeout-seconds, when given, sets
that limit for every file instead. The test command gives the runner that limit
as --run-time-limit-seconds-not-counting-admission-waits, so the time in which
a suite waits for the runner's ADMISSION is not counted against it; at the
limit the runner kills each running suite's process group and exits nonzero. A
suite waits for admission at most the runner's
TEST_SUITE_ADMISSION_WAIT_CEILING_SECONDS; past it the runner stops, saying
the suite got no test slot. As a backstop for a runner that does neither, the
test command sends the runner SIGTERM once the limit, that ceiling and
MUTANT_TIMEOUT_EXTRA_SECONDS_FOR_TEST_SUITE_RUNNER_TO_STOP_ITS_SUITES, 30 s,
have passed; cosmic-ray's own limit, which kills only the test command's
process group, is 30 s later still, since a suite runs in a session of its own
and, outside an nc-test-sandbox, outlives a runner killed with SIGKILL.

PARALLEL MUTANTS. --parallel-mutant-workers N runs N mutants at once, each in a
scratch worktree of its own at the head, since each worker edits its mutant into
the file on disk; the python of --cosmic-ray-venv runs the workers.
This script runs itself under that python with
--cosmic-ray-session-pending-mutants-run-by-parallel-workers, a flag no caller
gives, in place of `cosmic-ray exec`: it hands each mutant of the session with
no result to the next free worker, a process of its own started with
--cosmic-ray-one-work-item-mutate-and-test in that worker's worktree, which
mutates, tests and restores the file as cosmic-ray's own worker does, and it
records each result in the session. A mutant whose worker gives no result
stays without one, and the script exits 2 naming it. The baseline runs once,
in the first worktree. The suites of every worker still wait for the
runner's ADMISSION, so N above the machine's free cores only queues them.
Where suites do not run in nc-test-sandboxes, every run of the runner takes
the machine's lock, so an N above 1 exits 2 before making a worktree.
Without the flag, mutants run one at a time, by `cosmic-ray exec`.

KEPT SESSIONS. --cosmic-ray-sessions-directory-kept-to-resume DIR keeps each
changed file's cosmic-ray session in DIR, named by the head, the merge base,
the file and, for the quick pass, the pass, so that a run stopped part-way, as
by SIGTERM, keeps the result of every mutant it finished, and a quick and a
full pass never share a session. A session is put in place only once
cosmic-ray's filters have run on it. A later run of the same pass with the
same head and base finds the session, prints RESUMED for the file, and runs
only its mutants with no result, with no baseline when every mutant has one;
the SUMMARY line and the JSON file still cover all of its mutants. A session
that cannot be put in place exits 2. Without the flag, each session
is in the scratch directory and is removed with it.

SOME MUTANTS RUN, THE REST KEPT FOR A LATER RUN. Two flags of the full
mutation pass, each needing --parallel-mutant-workers and
--cosmic-ray-sessions-directory-kept-to-resume, leave mutants with no result
in the kept sessions, where a later run finds them. With either, the session
of every changed file that has a suite is made, or found kept, before any
baseline, so the sessions hold every mutant of the change; a file none of
whose mutants this run runs gets no baseline; and RESUMED is printed only for
a file whose every mutant has a result. The SUMMARY line counts each mutant
left with no result as not run, the JSON file gives their number, and the
exit code is then 1.
--mutants-run-at-most-shared-evenly-among-changed-files N runs N of the
change's mutants at most: one from each changed file in turn, until N are
chosen or none is left, so a short file is given as many as a long one. The
head commit seeds the order of the files and of each file's mutants, and the
N are chosen from every mutant cosmic-ray's filters did not skip, with or
without a result; so a later run with the same head, base and N chooses the
same mutants and runs only those of them with no result, and a run with a
larger N, or without the flag, runs others, never one that has a result.
cosmic-ray gives a mutant a new job id at each `cosmic-ray init`, so a mutant
is told from the others of its file by its operator, occurrence, start and end
position and operator arguments, which are the same at every init.
--no-mutant-started-after-unix-time UNIX_TIME starts no baseline and no
mutant from that time on; the mutants then running are judged, and the script
goes on to its SUMMARY line and JSON file.

A renamed file is mutated under its new name. A mutant cosmic-ray could not
judge, because its worker raised, its suites could not be launched, a suite
ran past its own time limit, which the runner's TIMEOUT line names, the
suites ran past the limit on one run of them, or the runner exited nonzero without a
suite failing by its own exit (it printed nothing, was not run to the end,
could not write its records, or a suite's nc-test-sandbox did not start), is
printed as ERRORED and counts against the run like a survivor. cosmic-ray
itself reports every nonzero exit of the runner as a kill; this script does
not. A mutant one of whose suites had a process killed at the suite's memory
ceiling (MEMORY CEILING in the runner's docstring), as a mutant that allocates
without end does, is killed: it fails that suite in seconds, and the rest of
the machine keeps its memory. On the unmutated head either a suite's own time limit or the limit on
one run of the suites stops the script with exit 2 and a message saying the suites ran out of time, with the limit,
and, for a suite's own limit, the suite; a suite that got no test slot stops it with exit 2 and a
message saying so. A suite that fails there by its own
exit or signal, in a run of the suite runner that ran to its end, stops the
script with EXIT_SUITE_FAILS_ON_UNMUTATED_HEAD, 3, and standard error names
each such suite on a line of its own opening with
SUITE_FAILS_ON_UNMUTATED_HEAD_LINE_PREFIX. Any other baseline that fails,
such as one whose result cosmic-ray could not dump, or whose suite runner
judged no suite, exits 2.

--survived-and-errored-mutants-json-file, when given, names a file this
script writes after its SUMMARY line, as one JSON object: "head" and
"merge_base", the two commits compared; "survived" and "errored", each a list
of mutants with "module_path", "line", "operator", "diff" and "reason", where
"line" is the line that must end with a `# pragma: no mutate` comment to skip
that mutant; "files_with_no_suite", a list of paths; and "mutants_not_run_count", how
many of the change's mutants have no result. A file that cannot be
written exits 2. A run that exits 2 or 3 because it could not run prints no
SUMMARY line and writes no such file.

THE RECORDED MUTANT KILLED CHECK, --recorded-mutant-killed-check DIFF_FILE
[DIFF_FILE ...], judges mutants a full mutation pass recorded: each DIFF_FILE
holds only one mutant's "diff" text, as the JSON file above gives it, not the
JSON file; it is the file
scripts/scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open.py
writes for each surviving mutant. It needs no cosmic-ray. In one detached
scratch worktree at --head, by default the HEAD of --checkout, so a change not
yet committed is left out, it runs once, on the unmutated code, every suite
the full mutation pass would choose for the mutated files. Then, for each
mutant in turn, it applies the diff to its file, reading the diff as
cosmic-ray wrote it: at the diff's own line; when the branch moved the line,
wherever the diff's lines appear exactly once; and when a later change edited
a context line, wherever the lines the diff replaces appear exactly once. Each
search reads a line ending with a `# pragma: no mutate` comment as that line
without it, and the mutant is applied at the place found, its context lines
left as the file has them. It runs that file's suites, stopping at the first failing suite, and puts the
file back. It prints one line per mutant, in the order given, starting with
its verdict and naming its diff file: MUTANT KILLED when a suite fails with
the mutant applied; MUTANT SURVIVED when every suite passes with it; MUTANT
NO LONGER EXISTS when there is nothing to kill, because the line it changes ends with a
`# pragma: no mutate` comment at the head, or the diff does not apply at the
head and origin/main, read without fetching, lacks the lines it replaces; and
MUTANT COULD NOT BE JUDGED, with what to do, when the diff file cannot be read or
names no file, the file has no suite while the mutant still applies at the
head, the diff does not apply at the head
while origin/main has those lines or cannot tell, the lines it replaces appear
more than once at the head when a trailing `# pragma: no mutate` comment is
read as absent, but only once when lines are compared exactly, or the runner judged no
suite with the mutant applied, as when a suite ran past its own time limit or
the runner was refused. When those lines appear more than once even when
compared exactly, as when every copy ends with the comment, the mutant does not apply
at the head, and origin/main decides between those two verdicts as above. Whether a mutant still exists is decided before
whether its file has a suite, so the mutant of a deleted file no longer exists
once origin/main lacks the file too. A line starting RECORDED MUTANTS counts each verdict.
--recorded-mutant-killed-check-verdicts-json-file-to-write, when given, names a file it then writes
as one JSON object: "head", the commit judged at, and "verdicts", which maps
each DIFF_FILE, as given, to its "verdict" ("killed", "survived", "no longer exists"
or "could not be judged") and "why", the rest of its line; a file that cannot be written
exits 2. It exits 0 when every mutant is killed or no longer exists, 1 when a
mutant survived and every other is killed or no longer exists, and 2 when a
mutant could not be judged, whatever the other verdicts, with the JSON file
written. It also exits 2,
printing no verdict line and writing no JSON file, when it cannot run at all:
when a suite fails without a mutant, or when the suite runner judges no suite
without a mutant, as when another test run holds the machine's lock, its
refusal printed. The scratch worktree is removed whatever happens.

Exit codes, for a quick or full mutation pass (the recorded mutant killed
check exits as its own paragraph says: 0 every mutant was killed or no longer
exists, 1 one survived, 2 one could not be judged or the check could not run,
a suite failing without a mutant included; never 3):
0 every mutant was killed, 1 a mutant survived, errored or was
not run, or a changed file has no suite, 2 could not run (cosmic-ray missing,
a git step failed, the nc-head-commit is already in the base, the worktree could
not be made, a changed file the quick mutation pass reads is not valid Python,
the JSON file could not be written, or a suite runs out of time, cannot be
launched, or fails without the suite runner naming it on the unmutated head),
3 a suite fails by its own exit or signal on the unmutated head, which
standard error names, so no mutant was judged, 143 or 129 stopped by SIGTERM or SIGHUP (128 plus the signal
number), after removing the scratch worktree, git's record of it included,
and the scratch directory.
"""

import argparse
import ast
import hashlib
import importlib.util
import json
import math
import os
import queue
import random
import re
import shlex
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

PROGRAM = "mutation-testing-changed-lines-quick-or-full-pass-survivors"

EXIT_EVERY_MUTANT_KILLED = 0
EXIT_SURVIVORS_OR_UNTESTED_FILES = 1
EXIT_COULD_NOT_RUN = 2
EXIT_SUITE_FAILS_ON_UNMUTATED_HEAD = 3

COSMIC_RAY_TOOLS = ("cosmic-ray", "cr-filter-git", "cr-filter-pragma", "cr-filter-lines")
# In a home directory, not /tmp, so the venv outlasts a reboot or a /tmp clean-up.
DEFAULT_COSMIC_RAY_VENV = Path.home() / ".local" / "share" / "nedschorus" / "cosmic-ray-venv"
COSMIC_RAY_VERSION = "8.7.0"

QUICK_MUTATION_PASS_COMMAND_LINE_FLAG = "--quick-mutation-pass"
FULL_MUTATION_PASS_COMMAND_LINE_FLAG = "--full-mutation-pass"
RECORDED_MUTANT_KILLED_CHECK_COMMAND_LINE_FLAG = "--recorded-mutant-killed-check"
MUTANT_KILLED_LINE_PREFIX = "MUTANT KILLED"
MUTANT_SURVIVED_LINE_PREFIX = "MUTANT SURVIVED"
MUTANT_NO_LONGER_EXISTS_LINE_PREFIX = "MUTANT NO LONGER EXISTS"
MUTANT_COULD_NOT_BE_JUDGED_LINE_PREFIX = "MUTANT COULD NOT BE JUDGED"
RECORDED_MUTANT_VERDICT_LINE_PREFIXES = {
    "killed": MUTANT_KILLED_LINE_PREFIX, "survived": MUTANT_SURVIVED_LINE_PREFIX,
    "no longer exists": MUTANT_NO_LONGER_EXISTS_LINE_PREFIX,
    "could not be judged": MUTANT_COULD_NOT_BE_JUDGED_LINE_PREFIX}
# cosmic-ray's cr-filter-pragma skips a line whose comment says `pragma: no mutate`.
PRAGMA_NO_MUTATE_COMMENT = re.compile(r"\s*#.*pragma: no mutate.*")

# Each checks one rule across a whole class of the repository's files, so its recording reads
# nearly every module; the quick mutation pass leaves it out.
REPOSITORY_WIDE_CHECKS = (
    "nc-systems/general-tools/tests/common-module-wording-copied-into-other-test-files-guard-for-each-wording-module-test.py",
    "scripts/code-comments-carry-no-history-markers-test.py",
    "scripts/edited-file-path-within-checkout-root-and-git-check-ignore-defined-once-test.py",
    "scripts/every-repository-program-help-option-test.py",
    "scripts/git-redirecting-environment-variables-defined-once-test.py",
    "scripts/git-redirecting-environment-variables-removed-by-every-caller-test.py",
    "scripts/python-files-carry-no-try-except-pass-ruff-s110-test.py",
    "scripts/registered-hook-messages-carry-no-citations-test.py",
    "scripts/supervisor-file-names-defined-once-test.py",
    "scripts/test-suites-run-directly-ignore-git-redirecting-environment-test.py",
    "scripts/test-suites-source-scan-for-skipped-case-prints-run-all-test-suites-cannot-count-test.py",
)

# A name or attribute that holds a process's exit code, as this project's code names one.
EXIT_CODE_NAME = re.compile(r"(?:^|_)(?:returncode|exit_code|exit_status)$")
TEST_SUITE_RUNNER_START_UP_SECONDS = 5
# The runner acts on SIGTERM within RUN_STOP_SIGNAL_CHECK_SECONDS, then waits up to
# TEST_SUITE_OUTPUT_DRAIN_SECONDS for each killed suite's output.
MUTANT_TIMEOUT_EXTRA_SECONDS_FOR_TEST_SUITE_RUNNER_TO_STOP_ITS_SUITES = 30
COSMIC_RAY_TEST_COMMAND_RUN_TEST_SUITE_RUNNER_STOPPED_AFTER_SECONDS_FLAG = "--cosmic-ray-test-command-run-test-suite-runner-stopped-after-seconds"
TEST_SUITE_RUNNER_STOPPED_AT_MUTANT_TIMEOUT_LINE_PREFIX = f"{PROGRAM}: stopped the suite runner with SIGTERM"
PARALLEL_MUTANT_WORKERS_FLAG = "--parallel-mutant-workers"
COSMIC_RAY_SESSIONS_DIRECTORY_KEPT_TO_RESUME_FLAG = "--cosmic-ray-sessions-directory-kept-to-resume"
COSMIC_RAY_SESSION_PENDING_MUTANTS_RUN_BY_PARALLEL_WORKERS_FLAG = "--cosmic-ray-session-pending-mutants-run-by-parallel-workers"
COSMIC_RAY_SESSION_PENDING_MUTANTS_COUNT_SQL_QUERY = (
    "SELECT COUNT(*) FROM work_items WHERE job_id NOT IN (SELECT job_id FROM work_results)")
COSMIC_RAY_ONE_WORK_ITEM_MUTATE_AND_TEST_FLAG = "--cosmic-ray-one-work-item-mutate-and-test"
MUTANTS_RUN_AT_MOST_SHARED_EVENLY_AMONG_CHANGED_FILES_FLAG = "--mutants-run-at-most-shared-evenly-among-changed-files"
NO_MUTANT_STARTED_AFTER_UNIX_TIME_FLAG = "--no-mutant-started-after-unix-time"
# cosmic-ray 8.7.0's session schema. `cosmic-ray init` gives each mutant a random job_id, so the
# columns of mutation_specs, the same at every init of one file at one commit, tell which
# mutant a work item is. A mutant its filters skipped has a result whose worker_outcome is
# SKIPPED.
COSMIC_RAY_SESSION_MUTANTS_NOT_SKIPPED_BY_FILTERS_SQL_QUERY = (
    "SELECT operator_name, occurrence, start_pos_row, start_pos_col, end_pos_row, end_pos_col, "
    "COALESCE(operator_args, ''), work_items.job_id, "
    "work_items.job_id IN (SELECT job_id FROM work_results) "
    "FROM work_items JOIN mutation_specs ON mutation_specs.job_id = work_items.job_id "
    "WHERE work_items.job_id NOT IN "
    "(SELECT job_id FROM work_results WHERE worker_outcome = 'SKIPPED')")
ALL_MUTANTS_WITH_NO_RESULT_ARGUMENT = "all"
NO_UNIX_TIME_AFTER_WHICH_NO_MUTANT_STARTS_ARGUMENT = "never"

TEST_SUITE_RUNNER_PATH = Path(__file__).resolve().with_name("run-all-test-suites.py")
# The scheduled full mutation pass reads the suites that fail on the unmutated head from the lines
# opening so.
SUITE_FAILS_ON_UNMUTATED_HEAD_LINE_PREFIX = "SUITE FAILS ON UNMUTATED HEAD  "
TEST_SUITE_RUNNER_LOG_DIRECTORIES_PARENT_PREFIX = f"{PROGRAM}-test-suite-runner-logs-"
# The scheduled full mutation pass quotes this script's last line; it skips a line opening so.
TEST_SUITE_RUNNER_LOGS_KEPT_LINE_PREFIX = (
    f"{PROGRAM}: the suite runner's logs of the runs whose failure is reported above are kept in ")
TEST_SUITE_RUNNER_LOG_DIRECTORIES_PARENT_RETENTION_SECONDS = 2 * 24 * 3600

_git_output_spec = importlib.util.spec_from_file_location(
    "git_machine_readable_output_runner_and_parser_common",
    Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
    / "git-machine-readable-output-runner-and-parser-common.py")
git_output = importlib.util.module_from_spec(_git_output_spec)
_git_output_spec.loader.exec_module(git_output)

_stop_signals_spec = importlib.util.spec_from_file_location(
    "stop_signal_sigterm_or_sighup_raises_system_exit_so_cleanup_runs_common",
    Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
    / "stop-signal-sigterm-or-sighup-raises-system-exit-so-cleanup-runs-common.py")
stop_signals = importlib.util.module_from_spec(_stop_signals_spec)
_stop_signals_spec.loader.exec_module(stop_signals)


def load_test_suite_runner():
    spec = importlib.util.spec_from_file_location("run_all_test_suites",
                                                  TEST_SUITE_RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CouldNotRun(Exception):
    """A step failed; the message says which and what to do."""


class SuiteFailsOnUnmutatedHead(CouldNotRun):
    """The suite runner, run to its end on the unmutated head, judged a suite failing by the
    suite's own exit or signal."""


def run(command, cwd, environment=None):
    return subprocess.run(command, cwd=str(cwd), env=environment, text=True,
                          capture_output=True, check=False)


def run_or_raise(command, cwd, environment=None, what=None):
    completed = run(command, cwd, environment)
    if completed.returncode != 0:
        raise CouldNotRun(
            f"{PROGRAM}: {what or ' '.join(command)} failed "
            f"(exit {completed.returncode}): "
            f"{(completed.stderr or completed.stdout).strip()}")
    return completed.stdout


COSMIC_RAY_VENV_FLAG = "--cosmic-ray-venv"
COSMIC_RAY_VENV_PLACEHOLDER = "<that venv>"
# argparse accepts only an unambiguous abbreviation, and --cosmic-ray-sessions-directory-kept-to-resume
# shares "--cosmic-ray-" with this flag, so the shortest abbreviation parse_arguments accepts is
# "--cosmic-ray-v". A shorter word, such as an empty option value, is never this flag.
SHORTEST_COSMIC_RAY_VENV_FLAG_ABBREVIATION_LENGTH = len("--cosmic-ray-v")


def build_argv_with_cosmic_ray_venv_flags_replaced_by_placeholder(argv):
    """Return argv with every --cosmic-ray-venv given, and its value, taken out, and
    `--cosmic-ray-venv <that venv>` put at its end."""
    kept, arguments = [], iter(argv)
    for argument in arguments:
        name, equals, _ = argument.partition("=")
        if (len(name) >= SHORTEST_COSMIC_RAY_VENV_FLAG_ABBREVIATION_LENGTH
                and COSMIC_RAY_VENV_FLAG.startswith(name)):
            if not equals:
                next(arguments, None)
            continue
        kept.append(argument)
    return kept + [COSMIC_RAY_VENV_FLAG, COSMIC_RAY_VENV_PLACEHOLDER]


def cosmic_ray_tool_paths(venv):
    """Return {tool: path} for the cosmic-ray commands, or raise naming how to install them."""
    found = {}
    for tool in COSMIC_RAY_TOOLS:
        candidate = Path(venv).expanduser().resolve() / "bin" / tool
        if not candidate.is_file():
            quoted = shlex.quote(str(Path(venv).expanduser()))
            existing_venv_argv = build_argv_with_cosmic_ray_venv_flags_replaced_by_placeholder(
                sys.argv)
            raise CouldNotRun(
                f"{PROGRAM}: not run — {tool} is not in {Path(venv).expanduser() / 'bin'}.\n"
                f"Do these steps on {socket.gethostname()}, the machine this ran on, because "
                f"the venv is a path there; from another machine, run them over ssh to it.\n"
                f"If a venv there already holds cosmic-ray=={COSMIC_RAY_VERSION}, skip the "
                f"install and run this, with <that venv> replaced by the venv's path:\n"
                f"  python3 {shlex.join(existing_venv_argv)}\n"
                f"Otherwise install cosmic-ray into {quoted}:\n"
                f"  python3 -m venv {quoted}\n"
                f"  {quoted}/bin/pip install cosmic-ray=={COSMIC_RAY_VERSION}\n"
                f"Then run again:\n"
                f"  python3 {shlex.join(sys.argv)}")
        found[tool] = str(candidate)
    return found


def head_and_base_of_pull_request(number, checkout, environment):
    """Return (nc-head-commit, base ref) of a pull request, fetching both."""
    view = json.loads(run_or_raise(
        ["gh", "pr", "view", str(number), "--json", "headRefOid,baseRefName"],
        checkout, environment, what=f"gh pr view {number}"))
    head, base_branch = view["headRefOid"], view["baseRefName"]
    run_or_raise(["git", "fetch", "--quiet", "origin", base_branch, head],
                 checkout, environment,
                 what=f"git fetch origin {base_branch} {head}")
    return head, f"origin/{base_branch}"


def changed_python_files_to_mutate(checkout, merge_base, head, environment):
    """Changed, added or renamed Python files at head, by their head names, suites excluded."""
    # R keeps a renamed-and-changed file, which --name-only lists by its new
    # name, the name cr-filter-git's own rename-detecting diff uses.
    listed = run_or_raise(
        ["git", "diff", "-z", "--name-only", "--diff-filter=AMR", merge_base, head,
         "--", "*.py"], checkout, environment, what="git diff --name-only")
    return [path for path in git_output.nul_separated_fields(listed)
            if not path.endswith("-test.py")]


def suites_at_head(checkout, head, environment):
    """The nc-test-suites git tracks at head."""
    listed = run_or_raise(["git", "ls-tree", "-r", "-z", "--name-only", head], checkout,
                          environment, what="git ls-tree")
    return [path for path in git_output.nul_separated_fields(listed)
            if path.endswith(("-test.py", "-test.sh"))]


def suites_for_file(path, suites_at_head, recordings_directory, runner):
    """Suites whose recorded inputs read the file, plus its sibling suite."""
    chosen = []
    for suite in suites_at_head:
        recording = runner.load_recording(recordings_directory, suite)
        if (isinstance(recording, dict) and recording.get("exit") == 0
                and path in recording.get("reads", {})):
            chosen.append(suite)
    stem = path[:-len(".py")]
    for sibling in (f"{stem}-test.py", f"{stem}-test.sh"):
        if sibling in suites_at_head and sibling not in chosen:
            chosen.append(sibling)
    return chosen


def tracked_python_files_at(commit, checkout, environment, cache):
    """The Python files git tracks at the commit, or None when git cannot list them."""
    if commit not in cache:
        listed = run(["git", "ls-tree", "-r", "-z", "--name-only", commit], checkout, environment)
        cache[commit] = None if listed.returncode else {
            path for path in git_output.nul_separated_fields(listed.stdout) if path.endswith(".py")}
    return cache[commit]


def quick_mutation_pass_suites(suites, recordings_directory, runner, checkout, environment,
                               tracked_python_files_cache):
    """The suites less the repository-wide checks and every suite whose recording read every
    Python file git tracked at the commit it was recorded at."""
    chosen = []
    for suite in suites:
        if suite in REPOSITORY_WIDE_CHECKS:
            continue
        recording = runner.load_recording(recordings_directory, suite)
        commit = recording.get("commit") if isinstance(recording, dict) else None
        # A commit this clone lacks leaves the suite in: it only costs time.
        tracked = (tracked_python_files_at(commit, checkout, environment,
                                           tracked_python_files_cache)
                   if isinstance(commit, str) else None)
        if tracked and tracked <= set(recording.get("reads", {})):
            continue
        chosen.append(suite)
    return chosen


def reads_an_exit_code(expression):
    return any(EXIT_CODE_NAME.search(node.attr if isinstance(node, ast.Attribute) else node.id)
               for node in ast.walk(expression) if isinstance(node, (ast.Attribute, ast.Name)))


def failure_handling_line_ranges(source):
    """(first line, last line) of each except clause, and of each if, while or conditional
    expression whose test reads an exit code."""
    return sorted(
        (node.lineno, node.end_lineno) for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ExceptHandler)
        or (isinstance(node, (ast.If, ast.While, ast.IfExp)) and reads_an_exit_code(node.test)))


HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
HUNK_COUNTS = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? \+\d+(?:,(?P<new_count>\d+))? @@")


def line_numbers_at_head_of_lines_changed_since_merge_base(checkout, merge_base, head, path, environment):
    """The numbers, at head, of the lines the change added or changed in the file."""
    diff = run_or_raise(["git", "--literal-pathspecs", "diff", "--unified=0", "--no-color",
                         "--no-ext-diff", merge_base, head, "--", path],
                        checkout, environment, what=f"git diff of {path}")
    changed = set()
    for line in diff.splitlines():
        hunk = HUNK_HEADER.match(line)
        if hunk:
            start = int(hunk[1])
            changed.update(range(start, start + int(hunk[2] if hunk[2] is not None else 1)))
    return changed


def failure_handling_line_ranges_of_file(worktree, path):
    try:
        return failure_handling_line_ranges((worktree / path).read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError) as error:
        raise CouldNotRun(
            f"{PROGRAM}: not run — {path} at the head commit is not valid Python ({error}), so "
            f"the quick mutation pass cannot find its failure-handling code.\n"
            f"Fix the file until python3 -m py_compile {shlex.quote(path)} passes.\n"
            f"Commit the fix, then run scripts/{PROGRAM}.py again with the same options and the new head "
            f"commit.") from error


def test_suite_runner_backstop_seconds(seconds, runner):
    """How long the test command waits for a runner given a run time limit of `seconds`:
    the longest it can wait for admission, that limit, and the time it takes to stop its suites
    at that limit.

    The admission wait is bounded so only while every suite of the run waits from its start,
    as where the runner runs all of them at once, its default with admission."""
    return (seconds + runner.TEST_SUITE_ADMISSION_WAIT_CEILING_SECONDS
            + MUTANT_TIMEOUT_EXTRA_SECONDS_FOR_TEST_SUITE_RUNNER_TO_STOP_ITS_SUITES)


def run_test_suite_runner_with_its_stderr_on_stdout_stopped_before_cosmic_ray_limit(
        seconds, log_directories_parent, command):
    """Run the suite runner's command, its standard error on standard output, with a new
    --log-dir in log_directories_parent and a run time limit of `seconds`, which the runner
    counts without its admission waits; past test_suite_runner_backstop_seconds(), say so on
    standard output and send it SIGTERM. Return its exit code.

    A runner a signal killed returns the negative signal number, which leaves this process
    nonzero."""
    backstop = test_suite_runner_backstop_seconds(seconds, load_test_suite_runner())
    log_dir = tempfile.mkdtemp(dir=log_directories_parent)
    test_suite_runner = subprocess.Popen(
        [*command, "--log-dir", log_dir,
         "--run-time-limit-seconds-not-counting-admission-waits", repr(float(seconds))],
        stderr=subprocess.STDOUT)
    try:
        exit_code = test_suite_runner.wait(backstop)
    except subprocess.TimeoutExpired:
        print(f"{TEST_SUITE_RUNNER_STOPPED_AT_MUTANT_TIMEOUT_LINE_PREFIX}: it ran past "
              f"{backstop:g} s, the longest admission wait, the run time limit of {seconds:g} s "
              f"and the time to stop its suites together", flush=True)
        test_suite_runner.terminate()
        exit_code = test_suite_runner.wait()
    return exit_code


def cosmic_ray_session_pending_mutants_run_by_parallel_workers(
        config_file, session_file, job_ids_to_run, not_started_after_unix_time, worktrees):
    """Run under the cosmic-ray venv's python: run every work item of the session that has no
    result, one worker per worktree at once, each in its own process with that worktree as its
    working directory, and record each result in the session as `cosmic-ray exec` does. With
    job_ids_to_run, only those work items run; a work item not yet started at
    not_started_after_unix_time, when given, is not run. Each work item not run stays without a
    result.

    Return 0, or 2 after naming each work item whose worker gave no result; that work item stays
    without a result, so a later run of the session runs it again.

    cosmic-ray 8.7.0's own http distributor cannot serve here: it calls asyncio.get_event_loop()
    with no loop running, which raises on Python 3.14, and its client gives up on a mutant after
    aiohttp's default 300 s, shorter than a mutant's limit."""
    from cosmic_ray.config import load_config
    from cosmic_ray.work_db import WorkDB
    from cosmic_ray.work_item import TestOutcome, WorkerOutcome, WorkResult
    config = load_config(config_file)
    work_db = WorkDB(session_file, WorkDB.Mode.open)
    try:
        pending = queue.SimpleQueue()
        count = 0
        for work_item in work_db.pending_work_items:
            if job_ids_to_run is None or work_item.job_id in job_ids_to_run:
                pending.put(work_item)
                count += 1
        # One None per worker, each ending the worker that takes it.
        for _ in worktrees:
            pending.put(None)
        results = queue.SimpleQueue()

        def work(worktree):
            while True:
                work_item = pending.get()
                if work_item is None:
                    return
                if not_started_after_unix_time is not None \
                        and time.time() >= not_started_after_unix_time:
                    results.put((work_item.job_id, None))
                    continue
                request = {"test_command": config.test_command, "timeout": config.timeout,
                           "mutations": [{
                               "module_path": str(mutation.module_path),
                               "operator_name": mutation.operator_name,
                               "operator_args": mutation.operator_args,
                               "occurrence": mutation.occurrence,
                               "start_pos": list(mutation.start_pos),
                               "end_pos": list(mutation.end_pos),
                               "definition_name": mutation.definition_name}
                               for mutation in work_item.mutations]}
                try:
                    completed = subprocess.run(
                        [sys.executable, str(Path(__file__).resolve()),
                         COSMIC_RAY_ONE_WORK_ITEM_MUTATE_AND_TEST_FLAG],
                        input=json.dumps(request), cwd=worktree, capture_output=True, text=True,
                        errors="replace", check=False)
                except OSError as error:
                    completed = error
                results.put((work_item.job_id, completed))

        workers = [threading.Thread(target=work, args=(worktree,), daemon=True)
                   for worktree in worktrees]
        for worker in workers:
            worker.start()
        no_result = []
        # Only this thread writes the session: a result is recorded only by a worker that
        # finished its mutant, never by one stopped part-way.
        for _ in range(count):
            job_id, completed = results.get()
            if completed is None:
                continue
            if isinstance(completed, OSError):
                no_result.append(f"work item {job_id}: its worker could not be started "
                                 f"({type(completed).__name__}: {completed})")
                continue
            try:
                if completed.returncode:
                    raise ValueError(f"the worker exited {completed.returncode}")
                said = json.loads(completed.stdout)
                work_db.set_result(job_id, WorkResult(
                    worker_outcome=WorkerOutcome(said["worker_outcome"]), output=said["output"],
                    test_outcome=(None if said["test_outcome"] is None
                                  else TestOutcome(said["test_outcome"])),
                    diff=said["diff"]))
            except (ValueError, KeyError, TypeError) as error:
                # All of it: a traceback names its cause before its last line.
                said = "".join(f"\n      {line}"
                               for line in (completed.stderr.strip() or "nothing").splitlines())
                no_result.append(f"work item {job_id}: {error}; it printed on standard "
                                 f"error:{said}")
        for worker in workers:
            worker.join()
    finally:
        work_db.close()
    if no_result:
        print(f"{PROGRAM}: {len(no_result)} of {count} mutant(s) of {session_file} got no "
              f"result, so they stay unrun in the session:\n"
              + "".join(f"  {line}\n" for line in no_result), file=sys.stderr, end="")
        return EXIT_COULD_NOT_RUN
    return 0


def cosmic_ray_one_work_item_mutate_and_test():
    """Run under the cosmic-ray venv's python, in a worker's worktree: apply the mutations the
    request on standard input names, run its test command, put the file back, and print the
    result as JSON, all as cosmic-ray's own worker does."""
    from cosmic_ray.mutating import mutate_and_test
    from cosmic_ray.work_item import MutationSpec
    request = json.load(sys.stdin)
    result = mutate_and_test([MutationSpec(
        module_path=Path(mutation["module_path"]), operator_name=mutation["operator_name"],
        occurrence=mutation["occurrence"], start_pos=tuple(mutation["start_pos"]),
        end_pos=tuple(mutation["end_pos"]), operator_args=mutation["operator_args"],
        definition_name=mutation["definition_name"]) for mutation in request["mutations"]],
        request["test_command"], request["timeout"])
    print(json.dumps({
        "worker_outcome": result.worker_outcome.value, "output": result.output,
        "test_outcome": None if result.test_outcome is None else result.test_outcome.value,
        "diff": result.diff}))
    return 0


def test_suite_runner_command(suites, worktree, arguments, recorded_inputs_directory):
    """The suite runner's command: one run of the suites on the worktree, changing no recording.

    Every caller adds a --log-dir in this script's log directories parent: without one, the
    runner keeps a log directory in the system temp directory for two days, and a run per
    mutant fills that directory's file system."""
    command = [sys.executable, str(TEST_SUITE_RUNNER_PATH), "--checkout", str(worktree),
               "--python", arguments.python,
               "--recorded-inputs-directory", str(recorded_inputs_directory),
               "--leave-recorded-inputs-and-failure-history-unchanged",
               "--stop-at-first-failing-suite"]
    # Left to the runner's default otherwise: every run that names one lock file shares the
    # admission kept beside it.
    if arguments.lock_file is not None:
        command += ["--lock-file", arguments.lock_file]
    return [*command, "--only-suites-named", *suites]


def test_command_for(suites, worktree, arguments, recorded_inputs_directory,
                     mutant_timeout_seconds, log_directories_parent):
    """The command cosmic-ray runs: this script, running the suite runner once on the worktree."""
    # cosmic-ray splits the command with shlex.
    return shlex.join([sys.executable, str(Path(__file__).resolve()),
                       COSMIC_RAY_TEST_COMMAND_RUN_TEST_SUITE_RUNNER_STOPPED_AFTER_SECONDS_FLAG,
                       repr(float(mutant_timeout_seconds)), str(log_directories_parent),
                       *test_suite_runner_command(suites, worktree, arguments,
                                                  recorded_inputs_directory)])


def default_mutant_timeout_seconds_from_test_suites_own_time_limits(
        suites, recordings_directory, runner, in_test_sandboxes):
    """The longest of the suites' own limits, times the runner's rounds of them, plus its start-up."""
    longest = max(runner.suite_timeout_and_the_recorded_seconds_it_came_from(
        runner.load_recording(recordings_directory, suite))[0] for suite in suites)
    at_once = runner.suites_run_at_once(None, len(suites), os.cpu_count(),
                                        admission_decides=in_test_sandboxes)
    return longest * math.ceil(len(suites) / at_once) + TEST_SUITE_RUNNER_START_UP_SECONDS


def cosmic_ray_config_text(module_path, test_command, merge_base,
                           mutant_timeout_seconds, failure_handling_ranges=None):
    """cosmic-ray's config; with failure_handling_ranges, cr-filter-lines keeps only those lines."""
    line_filter = "" if failure_handling_ranges is None else (
        "\n[cosmic-ray.filters.line-filter]\n"
        f"lines = {{ {json.dumps(module_path)} = "
        f"{json.dumps([f'{first}-{last}' for first, last in failure_handling_ranges])} }}\n")
    return (
        "[cosmic-ray]\n"
        f"module-path = {json.dumps(module_path)}\n"
        f"timeout = {float(mutant_timeout_seconds)!r}\n"
        "excluded-modules = []\n"
        f"test-command = {json.dumps(test_command)}\n"
        "\n"
        "[cosmic-ray.distributor]\n"
        "name = \"local\"\n"
        "\n"
        "[cosmic-ray.filters.git-filter]\n"
        f"branch = {json.dumps(merge_base)}\n"
        + line_filter)


OUTCOME_KEYS = ("killed", "survived", "errored", "no mutation", "skipped",
                "not run")

# cosmic-ray reports a worker that raised as exception/incompetent, and a test
# command it could not launch as normal/incompetent: errors of the run, not
# properties of the mutant. A no-test worker found nothing to mutate.
WORKER_OUTCOMES_THAT_ERRORED = ("exception", "abnormal")

# cosmic-ray reports suites that ran past the timeout as killed, with exactly
# this output: a slow run, not a test that failed under the mutant.
TIMED_OUT_OUTPUT = "timeout"


def is_recorded_output_of_a_run_stopped_at_mutant_timeout(output, runner):
    """True when the run was stopped at the limit, by the runner, the test command or cosmic-ray."""
    return output == TIMED_OUT_OUTPUT or any(
        line.startswith((TEST_SUITE_RUNNER_STOPPED_AT_MUTANT_TIMEOUT_LINE_PREFIX,
                         runner.RUN_STOPPED_AT_RUN_TIME_LIMIT_NOT_COUNTING_ADMISSION_WAITS_LINE_PREFIX))
        for line in output.splitlines())


def line_cr_filter_pragma_reads(mutation):
    """The line whose `# pragma: no mutate` skips this mutation: cosmic-ray 8.7.0's
    cr-filter-pragma reads the mutation's last line, or the line before it when the
    mutation ends at the start of a line, not its first line."""
    line, column = mutation["end_pos"]
    return line - 1 if column == 0 else line


def mutant_description(item, result, reason=""):
    mutation = item["mutations"][0]
    return {
        "module_path": mutation["module_path"],
        "line": line_cr_filter_pragma_reads(mutation),
        "operator": mutation["operator_name"],
        "diff": result.get("diff") or "",
        "reason": reason,
    }


def suite_timeouts_described(timed_out):
    return "; ".join(f"{suite} ran past its own limit of {limit} s"
                     for suite, limit in timed_out)


def runner_output_described(output, runner):
    """The runner's lines that say why it judged no suite, or that it printed nothing."""
    if not output.strip():
        return "was empty"
    lines = [line for line in output.splitlines()
             if line.startswith((f"{runner.PROGRAM}: not run", runner.FAILED_SUITE_LINE_PREFIX,
                                 runner.NOT_RUN_SUITE_LINE_PREFIX))]
    if not lines:
        return f"ended: {output.strip().splitlines()[-1]}"
    return f"says: {' | '.join(dict.fromkeys(lines))}"


def outcomes_from_dump(dump_text, mutant_timeout_seconds, runner):
    """Return (counts, survivors, errored, errored_outputs) from `cosmic-ray dump` output,
    errored_outputs holding the test command's output of each errored mutant.

    cosmic-ray counts a run past a suite's own limit, or the limit on one run of the suites,
    as a kill; each is an errored mutant here, whose reason says which limit it passed."""
    counts = dict.fromkeys(OUTCOME_KEYS, 0)
    survivors = []
    errored = []
    errored_outputs = []
    for line in dump_text.splitlines():
        if not line.strip():
            continue
        item, result = json.loads(line)
        if result is None:
            counts["not run"] += 1
            continue
        errored_before = len(errored)
        worker_outcome = result.get("worker_outcome")
        test_outcome = result.get("test_outcome")
        if worker_outcome == "skipped":
            counts["skipped"] += 1
        elif worker_outcome == "no-test":
            counts["no mutation"] += 1
        elif (worker_outcome not in WORKER_OUTCOMES_THAT_ERRORED
              and test_outcome == "survived"):
            counts["survived"] += 1
            survivors.append(mutant_description(item, result))
        elif (worker_outcome not in WORKER_OUTCOMES_THAT_ERRORED
              and test_outcome == "killed"
              and is_recorded_output_of_a_run_stopped_at_mutant_timeout(result.get("output") or "",
                                                                        runner)):
            counts["errored"] += 1
            errored.append(mutant_description(
                item, result,
                reason=f"timeout: the suites ran past the limit of "
                       f"{mutant_timeout_seconds:g} s on one run of them, so this mutant was "
                       f"not judged; rerun "
                       f"when the machine is quieter, or with a larger --mutant-timeout-seconds"))
        elif (worker_outcome not in WORKER_OUTCOMES_THAT_ERRORED
              and test_outcome == "killed"
              and runner.run_all_test_suites_output_timed_out_suites_and_limits_parse(
                  result.get("output") or "")):
            counts["errored"] += 1
            timed_out = runner.run_all_test_suites_output_timed_out_suites_and_limits_parse(
                result["output"])
            errored.append(mutant_description(
                item, result,
                reason=f"suite timeout: {suite_timeouts_described(timed_out)}, so this mutant "
                       f"was not judged: the mutant may make that suite hang, or the machine "
                       f"was busy; run this script again once, and if this mutant is ERRORED "
                       f"the same way again, it makes that suite hang: name it, with the "
                       f"suite, in the pull request's description"))
        elif (worker_outcome not in WORKER_OUTCOMES_THAT_ERRORED
              and test_outcome == "killed"
              and runner.run_all_test_suites_output_parse_whether_the_run_ended_with_a_suite_failed_by_its_exit_code_or_signal(
                  result.get("output") or "")):
            counts["killed"] += 1
        elif (worker_outcome not in WORKER_OUTCOMES_THAT_ERRORED
              and test_outcome == "killed"):
            counts["errored"] += 1
            errored.append(mutant_description(
                item, result,
                reason=f"no verdict: the suite runner exited nonzero but judged no suite "
                       f"failing, so this mutant was not judged; its output "
                       f"{runner_output_described(result.get('output') or '', runner)}"))
        else:
            counts["errored"] += 1
            errored.append(mutant_description(item, result))
        if len(errored) > errored_before:
            errored_outputs.append(result.get("output") or "")
    return counts, survivors, errored, errored_outputs


def test_suite_runner_log_directories_named_in_output(output, runner):
    """The log directories that the runner's first lines in output name."""
    mark = runner.FIRST_REPORT_LINE_LOG_DIRECTORY_MARK
    return {Path(line.split(mark, 1)[1]) for line in output.splitlines() if mark in line}


def remove_test_suite_runner_log_directories_not_kept(log_directories_parent, kept):
    """Remove each log directory in log_directories_parent that is not in kept.

    One that cannot be removed is left, and named by the line
    test_suite_runner_log_directories_parent_removed_or_named_as_kept prints."""
    for log_dir in log_directories_parent.iterdir():
        if log_dir not in kept:
            shutil.rmtree(log_dir, ignore_errors=True)


def test_suite_runner_log_directories_parent_removed_or_named_as_kept(log_directories_parent,
                                                                    stopped_by_signal=False):
    """Remove the parent when no log directory is left in it, or when a stop signal ended the
    script, since no one reads a stopped run's output; otherwise print where they are."""
    if stopped_by_signal:
        shutil.rmtree(log_directories_parent, ignore_errors=True)
    elif any(log_directories_parent.iterdir()):
        print(f"{TEST_SUITE_RUNNER_LOGS_KEPT_LINE_PREFIX}{log_directories_parent}; "
              f"remove that directory once you have read them; a later run of {PROGRAM}.py "
              f"removes it once it has not changed for two days.", file=sys.stderr)
    else:
        log_directories_parent.rmdir()


def test_suite_runner_log_directories_parents_past_retention_removed(
        temporary_directory, now, retention_seconds=TEST_SUITE_RUNNER_LOG_DIRECTORIES_PARENT_RETENTION_SECONDS):
    """Remove each log directories parent an earlier run of this script left in
    temporary_directory and last changed more than retention_seconds before now. One that
    cannot be read or removed is left."""
    for parent in Path(temporary_directory).glob(f"{TEST_SUITE_RUNNER_LOG_DIRECTORIES_PARENT_PREFIX}*"):
        try:
            if now - parent.stat().st_mtime > retention_seconds:
                shutil.rmtree(parent, ignore_errors=True)
        except OSError:
            continue


def scratch_file_name_stem_under_255_bytes_unique_to_repository_paths(*paths):
    """A 64-byte file-name stem unique to these repository paths.

    Repository paths here run long, so a name built from whole paths passes the 255-byte limit."""
    return hashlib.sha256("\0".join(paths).encode()).hexdigest()


def cosmic_ray_session_kept_to_resume_path_for_one_file_head_base_and_quick_or_full_mutation_pass(
        directory, head, merge_base, path, quick_mutation_pass):
    """The session file kept in `directory` for one file of one head and base. The quick
    pass's name differs from the full pass's, since the quick pass leaves the mutants outside
    the failure-handling lines out of its session; the full pass's name is the one earlier runs
    kept their sessions under."""
    keyed = (head, merge_base, path, "quick") if quick_mutation_pass else (head, merge_base, path)
    return (Path(directory).resolve()
            / f"{scratch_file_name_stem_under_255_bytes_unique_to_repository_paths(*keyed)}.sqlite")


def cosmic_ray_session_kept_to_resume_has_pending_mutants_or_is_unreadable(session):
    """True when the session holds a mutant with no result, or cannot be read as one: cosmic-ray
    then runs it, or reports why it cannot."""
    try:
        connection = sqlite3.connect(f"{session.as_uri()}?mode=ro", uri=True)
        try:
            with_no_result = connection.execute(
                COSMIC_RAY_SESSION_PENDING_MUTANTS_COUNT_SQL_QUERY).fetchone()[0]
            return with_no_result > 0
        finally:
            connection.close()
    except sqlite3.Error:
        return True


def suites_failed_by_their_own_exit_or_signal(outputs, runner):
    """Each suite, once, in the order first printed, that the suite runner judged failing by
    the suite's own exit or signal in an output of a run it ran to its end."""
    failed = {}
    for output in outputs:
        if runner.run_all_test_suites_output_parse_whether_the_run_ended_with_a_suite_failed_by_its_exit_code_or_signal(
                output):
            for line in output.splitlines():
                match = runner.SUITE_FAILED_LINE.match(line)
                if match:
                    failed.setdefault(match["suite"], None)
    return list(failed)


def baseline_refusal(path, suites, baseline, baseline_results, mutant_timeout_seconds,
                     runner):
    """The CouldNotRun to raise for a baseline cosmic-ray exited nonzero on: a suite that got
    no test slot, a timeout, or failing suites, as SuiteFailsOnUnmutatedHead when the suite
    runner names a suite failing by its own exit or signal."""
    outputs = [result.get("output") or "" for _, result in baseline_results
               if result and result.get("test_outcome") == "killed"]
    no_test_slot = [line for output in outputs for line in output.splitlines()
                    if line.startswith(runner.TEST_SUITE_ADMISSION_WAIT_CEILING_PASSED_LINE_PREFIX)]
    if no_test_slot:
        return CouldNotRun(f"{PROGRAM}: not run — on the unmutated head, a suite for {path} got no test "
                f"slot from scripts/run-all-test-suites.py's admission, so no mutant can be "
                f"judged; a larger --mutant-timeout-seconds does not help. Suites: "
                f"{' '.join(suites)}\n{no_test_slot[0]}\n"
                f"Run this again once the machine is quieter.")
    if any(is_recorded_output_of_a_run_stopped_at_mutant_timeout(output, runner)
           for output in outputs):
        return CouldNotRun(f"{PROGRAM}: not run — the suites for {path} ran out of time on the unmutated "
                f"head: they had not ended when the limit of "
                f"{mutant_timeout_seconds:g} s on one run of them passed, admission waits not "
                f"counted, so no mutant can be judged. Suites: {' '.join(suites)}\n"
                f"Run this again with --mutant-timeout-seconds larger than "
                f"{mutant_timeout_seconds:g}.")
    timed_out = runner.run_all_test_suites_output_timed_out_suites_and_limits_parse(
        "\n".join(outputs))
    if timed_out:
        suites_timed_out = " ".join(shlex.quote(suite) for suite, _ in timed_out)
        return CouldNotRun(f"{PROGRAM}: not run — on the unmutated head, {suite_timeouts_described(timed_out)}"
                f" in scripts/run-all-test-suites.py, so no mutant of {path} can be judged. A "
                f"suite's own limit comes from its last passing run (PER-SUITE TIMEOUT in that "
                f"file's docstring); a larger --mutant-timeout-seconds does not raise it.\n"
                f"Run the suite alone, in a checkout at the head: python3 "
                f"scripts/run-all-test-suites.py --only-suites-named {suites_timed_out}\n"
                f"If it passes there, it only ran slowly on a busy machine: run this again.\n"
                f"If it times out there too, the head makes it hang: fix that before mutation "
                f"testing.")
    said = (baseline.stderr or baseline.stdout).strip()
    failing = suites_failed_by_their_own_exit_or_signal(outputs, runner)
    if not failing:
        return CouldNotRun(f"{PROGRAM}: not run — the suites for {path} fail on the unmutated "
                           f"head, so no mutant can be judged: {' '.join(suites)}\n{said}")
    return SuiteFailsOnUnmutatedHead(
        f"{PROGRAM}: not run — a suite for {path} fails on the unmutated head, so no mutant "
        f"can be judged:\n"
        + "".join(f"{SUITE_FAILS_ON_UNMUTATED_HEAD_LINE_PREFIX}{suite}\n" for suite in failing)
        + f"Make the suite pass at the head, then run this again; or, when a later commit "
        f"already makes it pass, give that commit as --head with the same --base.\n{said}")


def cosmic_ray_session_not_kept_refusal(path, session_file, error):
    return (f"{PROGRAM}: not run — the cosmic-ray session of {path} could not be kept at "
            f"{session_file} ({type(error).__name__}: {error}), so its mutants cannot be run.\n"
            f"Fix what the error names, or give {COSMIC_RAY_SESSIONS_DIRECTORY_KEPT_TO_RESUME_FLAG} "
            f"a directory you can write to, then run this again with the same options.")


def mutants_chosen_one_per_file_in_turn_in_order_seeded_by_head(mutants_of_file, head, at_most):
    """At most `at_most` (file, mutant) pairs from `mutants_of_file`, which maps each changed
    file to its mutants: one mutant from each file in turn until that many are chosen or none
    is left, so a short file is given as many as a long one. The head commit seeds the order
    of the files and of each file's mutants, so the same head and mutants give the same
    pairs."""
    files = sorted(mutants_of_file)
    random.Random(head).shuffle(files)
    waiting = {}
    for path in files:
        waiting[path] = sorted(mutants_of_file[path])
        random.Random(f"{head} {path}").shuffle(waiting[path])
    chosen = []
    while len(chosen) < at_most and any(waiting.values()):
        for path in files:
            if waiting[path] and len(chosen) < at_most:
                chosen.append((path, waiting[path].pop()))
    return chosen


def cosmic_ray_session_mutants_not_skipped_by_filters(path, session):
    """{mutant: (job id, whether it has a result)} for each mutant of the session that
    cosmic-ray's filters did not skip, a mutant being its operator, occurrence, start and end
    position and operator arguments. Raises CouldNotRun when the session cannot be read."""
    try:
        # Not read-only: a run killed while writing a result leaves a hot journal, which only
        # a connection that can write rolls back.
        connection = sqlite3.connect(session)
        try:
            return {tuple(row[:7]): (row[7], bool(row[8])) for row in connection.execute(
                COSMIC_RAY_SESSION_MUTANTS_NOT_SKIPPED_BY_FILTERS_SQL_QUERY)}
        finally:
            connection.close()
    except sqlite3.Error as error:
        raise CouldNotRun(
            f"{PROGRAM}: not run — the cosmic-ray session of {path}, {session}, cannot be read "
            f"({type(error).__name__}: {error}), so the mutants to run cannot be chosen.\n"
            f"Delete that session file, and no other file, then run this again with the same "
            f"options: the mutants of {path} are then judged again from the first.") from error


def cosmic_ray_sessions_made_for_every_file_and_mutant_job_ids_to_run_chosen(
        files_and_suites, worktree, scratch, tools, head, merge_base, arguments, environment,
        runner, recorded_inputs_directory, recordings_directory, in_test_sandboxes,
        log_directories_parent):
    """Make and filter the kept session of each file that has none, before any baseline, so
    that every mutant of the change is in a session however few this run reaches. Return, for
    each file, the job ids of the mutants this run may run: every mutant with no result, as
    None, or, with MUTANTS_RUN_AT_MOST_SHARED_EVENLY_AMONG_CHANGED_FILES_FLAG, those with no
    result among the mutants chosen. The mutants are chosen from all that the filters did not
    skip, with or without a result, so a later run with the same number chooses the same ones
    and runs none of them twice."""
    mutants_of_file = {}
    for path, suites in files_and_suites:
        config, session, _ = cosmic_ray_config_written_and_session_path_of_one_file(
            path, suites, scratch, head, merge_base, arguments, runner,
            recorded_inputs_directory, recordings_directory, in_test_sandboxes,
            log_directories_parent, None)
        if not session.is_file():
            cosmic_ray_session_made_and_filtered(path, config, session, tools, worktree,
                                                 environment, None)
        mutants_of_file[path] = cosmic_ray_session_mutants_not_skipped_by_filters(path, session)
    at_most = arguments.mutants_run_at_most_shared_evenly_among_changed_files
    if at_most is None:
        return dict.fromkeys(mutants_of_file)
    job_ids_to_run = {path: [] for path in mutants_of_file}
    for path, mutant in mutants_chosen_one_per_file_in_turn_in_order_seeded_by_head(
            mutants_of_file, head, at_most):
        job_id, has_result = mutants_of_file[path][mutant]
        if not has_result:
            job_ids_to_run[path].append(job_id)
    return job_ids_to_run


def cosmic_ray_config_written_and_session_path_of_one_file(
        path, suites, scratch, head, merge_base, arguments, runner, recorded_inputs_directory,
        recordings_directory, in_test_sandboxes, log_directories_parent,
        failure_handling_ranges):
    """Write cosmic-ray's config for one file; return (the config, the file's session, kept or
    in scratch, the limit on one run of its suites)."""
    name = scratch_file_name_stem_under_255_bytes_unique_to_repository_paths(path)
    config = scratch / f"{name}.toml"
    session = scratch / f"{name}.sqlite"
    if arguments.cosmic_ray_sessions_directory_kept_to_resume is not None:
        session = \
            cosmic_ray_session_kept_to_resume_path_for_one_file_head_base_and_quick_or_full_mutation_pass(
                arguments.cosmic_ray_sessions_directory_kept_to_resume, head, merge_base, path,
                arguments.quick_mutation_pass)
    mutant_timeout_seconds = (
        arguments.mutant_timeout_seconds if arguments.mutant_timeout_seconds is not None
        else default_mutant_timeout_seconds_from_test_suites_own_time_limits(
            suites, recordings_directory, runner, in_test_sandboxes))
    config.write_text(cosmic_ray_config_text(
        path, test_command_for(suites, ".", arguments, recorded_inputs_directory,
                               mutant_timeout_seconds, log_directories_parent),
        merge_base,
        test_suite_runner_backstop_seconds(mutant_timeout_seconds, runner)
        + MUTANT_TIMEOUT_EXTRA_SECONDS_FOR_TEST_SUITE_RUNNER_TO_STOP_ITS_SUITES,
        failure_handling_ranges))
    return config, session, mutant_timeout_seconds


def cosmic_ray_session_made_and_filtered(path, config, session, tools, worktree, environment,
                                         failure_handling_ranges):
    """Run `cosmic-ray init` and the filters, then put the session in place."""
    # Renamed into place only once filtered, so a run stopped before then leaves no
    # session that a later run would resume with its filtered mutants unfiltered.
    unfiltered = session.with_name(session.name + ".partial")
    try:
        unfiltered.parent.mkdir(parents=True, exist_ok=True)
        unfiltered.unlink(missing_ok=True)
    except OSError as error:
        raise CouldNotRun(cosmic_ray_session_not_kept_refusal(path, unfiltered, error)) \
            from error
    run_or_raise([tools["cosmic-ray"], "init", str(config), str(unfiltered)], worktree,
                 environment, what=f"cosmic-ray init for {path}")
    run_or_raise([tools["cr-filter-git"], "--config", str(config), str(unfiltered)],
                 worktree, environment, what=f"cr-filter-git for {path}")
    run_or_raise([tools["cr-filter-pragma"], str(unfiltered)],
                 worktree, environment, what=f"cr-filter-pragma for {path}")
    if failure_handling_ranges is not None:
        run_or_raise([tools["cr-filter-lines"], "--config", str(config), str(unfiltered)],
                     worktree, environment, what=f"cr-filter-lines for {path}")
    try:
        os.replace(unfiltered, session)
    except OSError as error:
        raise CouldNotRun(cosmic_ray_session_not_kept_refusal(path, session, error)) \
            from error


def mutation_test_one_file(path, suites, worktrees, scratch, tools, head, merge_base,
                           arguments, environment, runner, recorded_inputs_directory,
                           recordings_directory, in_test_sandboxes, log_directories_parent,
                           failure_handling_ranges=None, mutants_run_are_limited=False,
                           mutant_job_ids_to_run=None):
    """Run cosmic-ray on one file's changed lines; return outcomes_from_dump()'s four values.

    Each run of the suite runner logs to a directory of its own in log_directories_parent.

    The baseline and cosmic-ray's own steps run in worktrees[0]; with --parallel-mutant-workers,
    each worktree gets one worker. With failure_handling_ranges, only the changed lines inside
    them are mutated. With mutants_run_are_limited, the file's session is already made, only
    the mutants with mutant_job_ids_to_run run, all with no result when that is None, and
    neither the baseline nor a mutant runs when there is none to run or the time after which
    no mutant starts has come."""
    worktree = worktrees[0]
    config, session, mutant_timeout_seconds = \
        cosmic_ray_config_written_and_session_path_of_one_file(
            path, suites, scratch, head, merge_base, arguments, runner,
            recorded_inputs_directory, recordings_directory, in_test_sandboxes,
            log_directories_parent, failure_handling_ranges)
    baseline_session = scratch / (
        f"{scratch_file_name_stem_under_255_bytes_unique_to_repository_paths(path)}"
        f".baseline.sqlite")
    cosmic_ray = [tools["cosmic-ray"]]
    not_started_after = arguments.no_mutant_started_after_unix_time
    if mutants_run_are_limited and (
            mutant_job_ids_to_run == []
            or not_started_after is not None and time.time() >= not_started_after):
        return outcomes_from_dump(run_or_raise(
            [*cosmic_ray, "dump", str(session)], worktree, environment,
            what=f"cosmic-ray dump for {path}"), mutant_timeout_seconds, runner)
    # A file an earlier run finished needs no baseline: running one would spend the merge's
    # time limit, night after night, on files with nothing left to judge.
    if session.is_file() \
            and not cosmic_ray_session_kept_to_resume_has_pending_mutants_or_is_unreadable(session):
        print(f"RESUMED  {path}: its cosmic-ray session {session} is kept from an earlier run "
              f"and has a result for every mutant, so neither its baseline nor any mutant runs: "
              f"those results are counted in the SUMMARY line", flush=True)
        return outcomes_from_dump(run_or_raise(
            [*cosmic_ray, "dump", str(session)], worktree, environment,
            what=f"cosmic-ray dump for {path}"), mutant_timeout_seconds, runner)
    baseline = run([*cosmic_ray, "baseline", "--session-file",
                    str(baseline_session), str(config)], worktree, environment)
    if baseline.returncode != 0:
        # cosmic-ray writes the baseline's result before it exits 1; a baseline that crashed
        # before writing it leaves nothing to dump, and is reported as failing suites.
        dumped = run([*cosmic_ray, "dump", str(baseline_session)], worktree, environment)
        baseline_results = ([json.loads(line) for line in dumped.stdout.splitlines()
                             if line.strip()] if dumped.returncode == 0 else [])
        raise baseline_refusal(path, suites, baseline, baseline_results,
                               mutant_timeout_seconds, runner)
    # cosmic-ray's baseline exits 0 unless the suites failed, so a suite it
    # could not launch at all passes it; only a survived baseline means they ran.
    baseline_results = [json.loads(line) for line in run_or_raise(
        [*cosmic_ray, "dump", str(baseline_session)], worktree, environment,
        what=f"cosmic-ray dump of the baseline for {path}").splitlines()
        if line.strip()]
    if not any(result and result.get("test_outcome") == "survived"
               for _, result in baseline_results):
        raise CouldNotRun(
            f"{PROGRAM}: not run — the suites for {path} could not be run on "
            f"the unmutated head, so no mutant can be judged: "
            f"{' '.join(suites)}\n"
            + "\n".join((result or {}).get("output") or ""
                        for _, result in baseline_results).strip())
    # With the mutants run limited, the session was made before any file's baseline.
    if not mutants_run_are_limited:
        if session.is_file():
            print(f"RESUMED  {path}: its cosmic-ray session {session} is kept from an earlier "
                  f"run, so only its mutants with no result run", flush=True)
        else:
            cosmic_ray_session_made_and_filtered(path, config, session, tools, worktree,
                                                 environment, failure_handling_ranges)
    if arguments.parallel_mutant_workers is None:
        run_or_raise([*cosmic_ray, "exec", str(config), str(session)], worktree,
                     environment, what=f"cosmic-ray exec for {path}")
    else:
        run_or_raise([tools["python"], str(Path(__file__).resolve()),
                      COSMIC_RAY_SESSION_PENDING_MUTANTS_RUN_BY_PARALLEL_WORKERS_FLAG,
                      str(config), str(session),
                      (ALL_MUTANTS_WITH_NO_RESULT_ARGUMENT if mutant_job_ids_to_run is None
                       else ",".join(mutant_job_ids_to_run)),
                      (NO_UNIX_TIME_AFTER_WHICH_NO_MUTANT_STARTS_ARGUMENT
                       if not_started_after is None else repr(not_started_after)),
                      *map(str, worktrees)], worktree, environment,
                     what=f"the {len(worktrees)} parallel mutant workers for {path}")
    return outcomes_from_dump(run_or_raise(
        [*cosmic_ray, "dump", str(session)], worktree, environment,
        what=f"cosmic-ray dump for {path}"), mutant_timeout_seconds, runner)


def remove_worktree(checkout, worktree, environment):
    removed = run(["git", "worktree", "remove", "--force", str(worktree)], checkout,
                  environment)
    if removed.returncode != 0 and worktree.exists():
        print(f"{PROGRAM}: could not remove the scratch worktree {worktree}: "
              f"{removed.stderr.strip()}\n"
              f"Remove it with: git worktree remove --force {worktree}",
              file=sys.stderr)


def recorded_mutant_module_path_and_hunks(diff_text):
    """(the path the mutant's diff changes or None, its hunks as (first old line, old lines,
    new lines)), read by each hunk header's line counts."""
    lines = diff_text.split("\n")
    path, hunks, index = None, [], 0
    while index < len(lines):
        line = lines[index]
        index += 1
        if path is None and line.startswith("+++ b/"):
            path = line[len("+++ b/"):]
        hunk = HUNK_COUNTS.match(line)
        if not hunk:
            continue
        old_count = int(hunk["old_count"]) if hunk["old_count"] is not None else 1
        new_count = int(hunk["new_count"]) if hunk["new_count"] is not None else 1
        old, new = [], []
        while (len(old) < old_count or len(new) < new_count) and index < len(lines):
            body = lines[index]
            index += 1
            if body[:1] in (" ", "-"):
                old.append(body[1:])
            if body[:1] in (" ", "+"):
                new.append(body[1:])
        hunks.append((int(hunk["old_start"]), old, new))
    return path, hunks


def lines_equal(line, wanted):
    return line == wanted


def line_equal_or_with_pragma_no_mutate_after(line, wanted):
    return line == wanted or (line.startswith(wanted)
                              and PRAGMA_NO_MUTATE_COMMENT.fullmatch(line[len(wanted):]))


def places_of_lines(lines, wanted, same=lines_equal):
    return [place for place in range(len(lines) - len(wanted) + 1)
            if all(same(line, want) for line, want in zip(lines[place:place + len(wanted)], wanted))]


def recorded_mutant_hunk_place(lines, old_start, old, new, same=lines_equal):
    """(where the hunk applies, its old lines, its new lines), the lines cut to the replaced
    lines when only those were found, or None when the hunk is not found once.

    A hunk is looked for at its own line first, then anywhere, since the branch may have moved
    the line; then, since a later change may have edited a context line, its replaced lines
    alone are looked for anywhere. same(line, wanted) says whether a source line matches a
    hunk's line."""
    at = old_start - 1 if old else old_start
    if len(lines[at:at + len(old)]) == len(old) and all(
            same(line, want) for line, want in zip(lines[at:at + len(old)], old)):
        return at, old, new
    places = places_of_lines(lines, old, same)
    if len(places) == 1:
        return places[0], old, new
    start, end = hunk_shared_context_line_counts(old, new)
    replaced = old[start:len(old) - end]
    places = places_of_lines(lines, replaced, same) if replaced else []
    if len(places) != 1:
        return None
    return places[0], replaced, new[start:len(new) - end]


def source_with_recorded_mutant_applied(source, hunks):
    """The source with the hunks applied, or None when a hunk is not found once.

    The source is split on "\\n", as cosmic-ray splits it to make the diff, so a file ending in
    a newline has the empty last line the diff's last context line stands for. Each hunk is
    found as recorded_mutant_hunk_place finds it."""
    lines = source.split("\n")
    for old_start, old, new in sorted(hunks, reverse=True):
        place = recorded_mutant_hunk_place(lines, old_start, old, new)
        if place is None:
            return None
        at, old, new = place
        lines[at:at + len(old)] = new
    return "\n".join(lines)


def hunk_shared_context_line_counts(old, new):
    """(lines at the start, lines at the end) that a hunk's old and new lines share."""
    start = 0
    while start < min(len(old), len(new)) and old[start] == new[start]:  # pragma: no mutate, `!=` stops where `<` does: start counts up by 1 from 0 to the bound at most
        start += 1
    end = 0
    while (end < min(len(old), len(new)) - start  # pragma: no mutate, `!=` stops where `<` does: end counts up by 1 from 0 to the bound at most, and the bound is never below 0
           and old[len(old) - 1 - end] == new[len(new) - 1 - end]):
        end += 1
    return start, end


def hunk_replaced_lines(old, new):
    """The lines a hunk replaces: its old lines without the context lines it shares with its
    new lines at the start and the end."""
    start, end = hunk_shared_context_line_counts(old, new)
    return old[start:len(old) - end]


def recorded_mutant_lines_on_main(checkout, path, hunks, environment):
    """"applies" when origin/main's file takes the mutant, "gone" when the file is not in
    origin/main's tree or some hunk's replaced lines are nowhere in it, None when it cannot
    tell: no origin/main, git fails to read the tree or the file, or a hunk's replaced lines
    appear in it more than once. Context lines alone never make "gone", since a change beside
    the mutated lines leaves the survivor live."""
    if run(["git", "rev-parse", "--verify", "--quiet", "refs/remotes/origin/main^{commit}"],
           checkout, environment).returncode:
        return None
    listed = run(["git", "ls-tree", "refs/remotes/origin/main", "--", path], checkout,
                 environment)
    if listed.returncode:
        return None
    if not listed.stdout.strip():
        return "gone"
    shown = run(["git", "show", f"refs/remotes/origin/main:{path}"], checkout, environment)
    if shown.returncode:
        return None
    if source_with_recorded_mutant_applied(shown.stdout, hunks) is not None:
        return "applies"
    lines = shown.stdout.split("\n")
    for _, old, new in hunks:
        replaced = hunk_replaced_lines(old, new)
        if replaced and not any(lines[place:place + len(replaced)] == replaced
                                for place in range(len(lines) - len(replaced) + 1)):  # pragma: no mutate, a mutant that only lengthens the range adds places whose slices are shorter than replaced, so never equal to it
            return "gone"
    return None


def recorded_mutant_run_verdict(exit_code, output, runner):
    """("killed" or "survived", None) for the suite runner's run with the mutant applied, or
    (None, why) when the runner judged no suite."""
    if exit_code == 0:
        return "survived", None
    timed_out = runner.run_all_test_suites_output_timed_out_suites_and_limits_parse(output)
    if timed_out:
        return None, suite_timeouts_described(timed_out)
    if runner.run_all_test_suites_output_parse_whether_the_run_ended_with_a_suite_failed_by_its_exit_code_or_signal(
            output):
        return "killed", None
    return None, (f"the suite runner exited {exit_code} but judged no suite failing; its output "
                  f"{runner_output_described(output, runner)}")


def recorded_mutant_places_reading_pragma_as_absent(lines, hunks):
    """For each hunk, (where it applies, its old lines, its new lines) or None when it is not
    found once, found as recorded_mutant_hunk_place finds it but reading a line with a
    `# pragma: no mutate` comment as the line without it. The pragma check and the mutant's
    application both use these places, so a twin of the hunk's lines elsewhere in the file,
    which an exact search could find once, is never the one mutated."""
    return [recorded_mutant_hunk_place(lines, old_start, old, new,
                                       line_equal_or_with_pragma_no_mutate_after)
            for old_start, old, new in hunks]


def recorded_mutant_place_ends_with_pragma(lines, place):
    """True when the last line the hunk at place replaces has a `# pragma: no mutate` comment
    after it, so no mutation pass makes the mutant any more."""
    at, old, new = place
    start, end = hunk_shared_context_line_counts(old, new)
    return len(old) - end > start and lines[at + len(old) - end - 1] != old[len(old) - end - 1]


def source_with_recorded_mutant_applied_at_places(lines, places):
    """The source with each hunk's replaced lines replaced at its place; its context lines
    stay as the source has them, a `# pragma: no mutate` comment included."""
    lines = list(lines)
    for at, old, new in sorted(places, key=lambda place: place[0], reverse=True):
        start, end = hunk_shared_context_line_counts(old, new)
        lines[at + start:at + len(old) - end] = new[start:len(new) - end]
    return "\n".join(lines)


def recorded_mutant_verdict_without_a_suite_run(checkout, path, hunks, head, source,
                                                why_source_unreadable, environment):
    """((verdict, why), None) when the mutant is judged without running a suite: its file
    cannot be read at the head (source None), its line ends with a `# pragma: no mutate`
    comment, its place is ambiguous, or it does not apply; else (None, the mutated source)."""
    if source is None:
        return recorded_mutant_not_applied_verdict(
            checkout, path, hunks, head, why_source_unreadable, environment), None
    lines = source.split("\n")
    places = recorded_mutant_places_reading_pragma_as_absent(lines, hunks)
    if any(place is not None and recorded_mutant_place_ends_with_pragma(lines, place)
           for place in places):
        return ("no longer exists", (
            f"the line it changes in {path} ends with a `# pragma: no mutate` comment at head "
            f"{head[:12]}, so no mutation pass makes it; the nightly mutation pass drops it from "
            f"its task once that is on main.")), None
    if all(place is not None for place in places):
        return None, source_with_recorded_mutant_applied_at_places(lines, places)
    if source_with_recorded_mutant_applied(source, hunks) is None:
        return recorded_mutant_not_applied_verdict(
            checkout, path, hunks, head,
            "the lines it replaces are missing from the file or appear in it more than once",
            environment), None
    # Read as exact lines the hunk is found once, but reading the comment as absent it is not.
    return ("could not be judged", (
        f"in {path} at head {head[:12]}, the lines this diff file replaces appear more than "
        f"once when each line's trailing `# pragma: no mutate` comment is stripped before "
        f"comparing: some copies end with that comment and some do not, so which copy is "
        f"the mutant's own line cannot be told, and no suite was run. The diff's `@@` line "
        f"gives the line number the mutant had when it was recorded; read the copies "
        f"around that number to tell which is the mutant's.\n"
        f"If the mutant's own line ends with the comment on origin/main: no mutation pass "
        f"makes the mutant any more; mark the survivor task that names this diff file "
        f"completed, saying why in the task's description.\n"
        f"Otherwise: write a test that fails when the diff's change is made on the mutant's "
        f"own line; check that by making the change by hand, running the test, and putting "
        f"the line back before you commit; say so in your pull request; and mark the "
        f"survivor task completed once that pull request merges, since every rerun of this "
        f"command gives this same verdict.")), None


def recorded_mutant_not_applied_verdict(checkout, path, hunks, head, why_not_applied,
                                        environment):
    """(verdict, why) for a recorded mutant that does not apply to its file at the head."""
    on_main = recorded_mutant_lines_on_main(checkout, path, hunks, environment)
    if on_main == "gone":
        return "no longer exists", (
            f"the lines it replaces in {path} are gone from origin/main too, so there is "
            f"nothing to kill; the nightly mutation pass drops it from its task.")
    if on_main == "applies":
        return "could not be judged", (
            f"it does not apply to {path} at head {head[:12]}: {why_not_applied}. origin/main "
            f"still has the lines it replaces, so your branch changed them.\n"
            f"If your branch changed them on purpose, the mutant is gone from your branch: once "
            f"your branch is merged, the nightly mutation pass drops it from its task.\n"
            f"Otherwise, put {path} back as origin/main has it, with git checkout origin/main -- "
            f"{shlex.quote(path)}, keep your test in another file, commit both, and run this "
            f"command again.")
    return "could not be judged", (
        f"it does not apply to {path} at head {head[:12]}: {why_not_applied}, and whether "
        f"origin/main still has the lines it replaces cannot be told: there is no local "
        f"origin/main, git could not read {path} there, or the lines appear there more than "
        f"once.\n"
        f"If your branch changed those lines on purpose, the mutant is gone from your branch: "
        f"once your branch is merged, the nightly mutation pass drops it from its task.\n"
        f"Otherwise, make sure your branch's head has {path} as origin/main has it, commit your "
        f"test in another file, and run this command again.")


def recorded_mutant_killed_check(arguments, checkout, environment, runner,
                                 log_directories_parent):
    """Judge each recorded mutant against the suites at --head, print a line for each, and
    write the verdicts JSON file when asked; return the exit code."""
    diff_files = list(dict.fromkeys(arguments.recorded_mutant_killed_check))
    head = run_or_raise(["git", "rev-parse", "--verify", f"{arguments.head}^{{commit}}"],
                        checkout, environment, what=f"git rev-parse {arguments.head}").strip()
    recorded_inputs_directory = (arguments.recorded_inputs_directory
                                 or runner.DEFAULT_RECORDED_INPUTS_DIRECTORY)
    try:
        recordings_directory = runner.recordings_directory_for(recorded_inputs_directory, checkout)
    except runner.CouldNotRun as refusal:
        raise CouldNotRun(str(refusal).splitlines()[0].replace(
            f"{runner.PROGRAM}:", f"{PROGRAM}:", 1) + "\n"
            + runner.git_failure_next_step_lines(Path(__file__).name)) from refusal
    suites_at = suites_at_head(checkout, head, environment)
    verdicts = {}
    to_run = []
    for diff_file in diff_files:
        try:
            path, hunks = recorded_mutant_module_path_and_hunks(
                Path(diff_file).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as error:
            verdicts[diff_file] = ("could not be judged", (
                f"the diff file cannot be read ({error}), so there is no mutant to apply.\n"
                f"Give {RECORDED_MUTANT_KILLED_CHECK_COMMAND_LINE_FLAG} the diff files the task "
                f"names, on ned-box, where they are kept."))
            continue
        if path is None or not hunks:
            verdicts[diff_file] = ("could not be judged", (
                "the diff file holds no line starting `+++ b/` or no line starting `@@`, so it "
                "names no file to mutate or no change to make in it.\n"
                f"Give {RECORDED_MUTANT_KILLED_CHECK_COMMAND_LINE_FLAG} the diff files the task "
                f"names, unchanged."))
            continue
        suites = suites_for_file(path, suites_at, recordings_directory, runner)
        if not suites:
            # A deleted module leaves no suite reading it, yet its mutant no longer exists.
            shown = run(["git", "show", f"{head}:{path}"], checkout, environment)
            verdict, _ = recorded_mutant_verdict_without_a_suite_run(
                checkout, path, hunks, head, None if shown.returncode else shown.stdout,
                "the file is not there, or git cannot read it", environment)
            if verdict is not None:
                verdicts[diff_file] = verdict
                continue
            verdicts[diff_file] = ("could not be judged", (
                f"at head {head[:12]} no recorded suite reads {path} and it has no sibling suite "
                f"(a {path[:-len('.py')]}-test.py or -test.sh), so no suite can kill the mutant.\n"
                f"If your new test is in a suite whose recording does not yet read {path}, such "
                f"as a new suite, run that suite once with python3 "
                f"scripts/run-all-test-suites.py --only-suites-named <the suite's path>, which "
                f"records what it reads, and run this command again."))
            continue
        to_run.append((diff_file, path, hunks, suites))
    if to_run:
        verdicts.update(recorded_mutants_judged_in_one_worktree(
            to_run, head, arguments, checkout, environment, runner, recorded_inputs_directory,
            log_directories_parent))
    counts = {verdict: 0 for verdict in RECORDED_MUTANT_VERDICT_LINE_PREFIXES}
    for diff_file in diff_files:
        verdict, why = verdicts[diff_file]
        counts[verdict] += 1
        print(f"{RECORDED_MUTANT_VERDICT_LINE_PREFIXES[verdict]}: {diff_file}: {why}")
    print(f"RECORDED MUTANTS at head {head[:12]}: {counts['killed']} killed, "
          f"{counts['survived']} survived, {counts['no longer exists']} no longer exist, "
          f"{counts['could not be judged']} could not be judged")
    if counts["survived"]:
        print("Write or change a test that fails with each surviving mutant and passes without "
              "it, commit the test as a new commit, and run this command again.")
    verdicts_json_file = arguments.recorded_mutant_killed_check_verdicts_json_file_to_write
    if verdicts_json_file is not None:
        try:
            Path(verdicts_json_file).write_text(json.dumps({
                "head": head, "verdicts": {diff_file: {"verdict": verdicts[diff_file][0],
                                                       "why": verdicts[diff_file][1]}
                                           for diff_file in diff_files}}, indent=1) + "\n",
                encoding="utf-8")
        except OSError as error:
            print(f"{PROGRAM}: the verdicts were not written to {verdicts_json_file}: {error}. "
                  f"The lines above are this command's whole result.\n"
                  f"Run it again with --recorded-mutant-killed-check-verdicts-json-file-to-write "
                  f"naming a path in a directory you can write to, or without that option if you "
                  f"need no JSON file.",
                  file=sys.stderr)
            return EXIT_COULD_NOT_RUN
    if counts["could not be judged"]:
        return EXIT_COULD_NOT_RUN
    if counts["survived"]:
        return EXIT_SURVIVORS_OR_UNTESTED_FILES
    return EXIT_EVERY_MUTANT_KILLED


def recorded_mutants_judged_in_one_worktree(to_run, head, arguments, checkout, environment, runner,
                                            recorded_inputs_directory, log_directories_parent):
    """{diff file: (verdict, why)} for each (diff file, path, hunks, suites), judged in one
    scratch worktree at the head, after one run of all their suites without a mutant.

    Each run's log directory, in log_directories_parent, is removed unless the run's failure is
    reported: the run without a mutant failed, or a mutant could not be judged."""
    # An inherited PYTHONPYCACHEPREFIX, as the signal-sandbox runner's --mutant run sets, would
    # put the suites' bytecode where removing the worktree's __pycache__ cannot reach it.
    environment = {name: value for name, value in environment.items()
                   if name != "PYTHONPYCACHEPREFIX"}
    all_suites = list(dict.fromkeys(suite for _, _, _, suites in to_run for suite in suites))
    verdicts = {}
    with tempfile.TemporaryDirectory(prefix=f"{PROGRAM}-") as scratch_name:
        worktree = Path(scratch_name).resolve() / "worktree"
        try:
            run_or_raise(["git", "worktree", "add", "--detach", str(worktree), head], checkout,
                         environment, what=f"git worktree add at {head}")
            unmutated_log_dir = Path(tempfile.mkdtemp(dir=log_directories_parent))
            unmutated = subprocess.run(
                [*test_suite_runner_command(all_suites, worktree, arguments,
                                            recorded_inputs_directory),
                 "--log-dir", str(unmutated_log_dir)],
                cwd=str(worktree), env=environment, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, check=False)
            if unmutated.returncode == runner.EXIT_LOCKED:  # pragma: no mutate, `is` matches a small int as `==` does, and the runner exits no higher than EXIT_LOCKED but by a signal, which is negative
                raise CouldNotRun(
                    f"{PROGRAM}: not run — the suite runner scripts/run-all-test-suites.py, run "
                    f"at head {head[:12]} without a mutant, exited {runner.EXIT_LOCKED}, which "
                    f"means it ran no suite: another test run holds a lock the runner takes (the "
                    f"machine's lock, or the lock on the runner's log directory), so no mutant "
                    f"can be judged. The runner's refusal, which names the lock and the process "
                    f"holding it:\n"
                    f"{unmutated.stdout.strip()}\n"
                    f"Run scripts/{PROGRAM}.py again, with the same options, once that process "
                    f"has ended.")
            if unmutated.returncode and not runner.run_all_test_suites_output_parse_whether_the_run_ended_with_a_suite_failed_by_its_exit_code_or_signal(
                    unmutated.stdout):
                raise CouldNotRun(
                    f"{PROGRAM}: not run — the suite runner scripts/run-all-test-suites.py, run "
                    f"at head {head[:12]} without a mutant, exited {unmutated.returncode} "
                    f"without reporting any suite as failed, so no mutant can be judged; the "
                    f"runner's output {runner_output_described(unmutated.stdout, runner)}\n"
                    f"{unmutated.stdout.strip()}\n"
                    f"If that output names a cause, fix it, then run scripts/{PROGRAM}.py again "
                    f"with the same options.\n"
                    f"If it names none, as when it is empty, run scripts/{PROGRAM}.py once more "
                    f"with the same options; if that run fails the same way, put both outputs in "
                    f"the description of the pull request you are checking.")
            if unmutated.returncode != 0:
                raise CouldNotRun(
                    f"{PROGRAM}: not run — the suites for the mutated files do not pass at head "
                    f"{head[:12]} without a mutant (the suite runner exited "
                    f"{unmutated.returncode}), so no failure with a mutant can be the mutant's: "
                    f"{' '.join(all_suites)}\n{unmutated.stdout.strip()}\n"
                    f"Make those suites pass at your branch's head, commit, and run this command "
                    f"again.")
            shutil.rmtree(unmutated_log_dir, ignore_errors=True)
            for diff_file, path, hunks, suites in to_run:
                source_file = worktree / path
                try:
                    source, why_unreadable = source_file.read_text(encoding="utf-8"), None
                except (OSError, UnicodeDecodeError) as error:
                    source, why_unreadable = None, f"the file cannot be read ({error})"
                verdict, mutated_source = recorded_mutant_verdict_without_a_suite_run(
                    checkout, path, hunks, head, source, why_unreadable, environment)
                if verdict is not None:
                    verdicts[diff_file] = verdict
                    continue
                source_file.write_text(mutated_source, encoding="utf-8")
                # Python checks cached bytecode by the source's size and whole-second mtime,
                # which a mutant such as + to * written within the second leaves the same.
                for cache in list(worktree.rglob("__pycache__")):
                    shutil.rmtree(cache)
                mutated_log_dir = Path(tempfile.mkdtemp(dir=log_directories_parent))
                mutated = subprocess.run(
                    [*test_suite_runner_command(suites, worktree, arguments,
                                                recorded_inputs_directory),
                     "--log-dir", str(mutated_log_dir)],
                    cwd=str(worktree), env=environment, text=True, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, check=False)
                source_file.write_text(source, encoding="utf-8")
                verdict, why = recorded_mutant_run_verdict(mutated.returncode, mutated.stdout,
                                                           runner)
                if verdict in ("killed", "survived"):
                    shutil.rmtree(mutated_log_dir, ignore_errors=True)
                if verdict == "killed":
                    verdicts[diff_file] = ("killed", (
                        f"at head {head[:12]}, the suites for {path} ({' '.join(suites)}) pass "
                        f"without the mutant, and one of them fails with it applied."))
                elif verdict == "survived":
                    verdicts[diff_file] = ("survived", (
                        f"at head {head[:12]}, every suite for {path} passes with the mutant "
                        f"applied: {' '.join(suites)}"))
                else:
                    verdicts[diff_file] = ("could not be judged", (
                        f"with the mutant applied at head {head[:12]}, {why}, so the mutant "
                        f"could not be judged.\n"
                        f"Run this command again once. If the mutant still cannot be judged, put "
                        f"that second output in the description of the pull request with your "
                        f"test."))
        finally:
            remove_worktree(checkout, worktree, environment)
    return verdicts


def parse_arguments(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    which_pass = parser.add_mutually_exclusive_group(required=True)
    which_pass.add_argument(QUICK_MUTATION_PASS_COMMAND_LINE_FLAG, action="store_true",
                            help="mutate only the changed failure-handling code, without the "
                                 "repository-wide checks")
    which_pass.add_argument(FULL_MUTATION_PASS_COMMAND_LINE_FLAG, action="store_true",
                            help="mutate every changed line, with every suite that reads the "
                                 "file; the pass the daily maintenance-job runs")
    which_pass.add_argument(RECORDED_MUTANT_KILLED_CHECK_COMMAND_LINE_FLAG, metavar="DIFF_FILE",
                            nargs="+", default=None,
                            help="apply each recorded mutant's diff at --head, by default HEAD, "
                                 "and say whether a suite kills it")
    which = parser.add_mutually_exclusive_group()
    which.add_argument("--pull-request", type=int,
                       help="the pull request to test; its head and base are read with gh and fetched")
    which.add_argument("--head", help="the nc-head-commit to test (needs --base, except with "
                                      f"{RECORDED_MUTANT_KILLED_CHECK_COMMAND_LINE_FLAG})")
    parser.add_argument("--base", help="the base the head is compared with (with --head)")
    parser.add_argument("--checkout", default=str(Path(__file__).resolve().parent.parent),
                        help="the checkout the worktree is made from; default, the one this file is in")
    parser.add_argument("--cosmic-ray-venv", default=str(DEFAULT_COSMIC_RAY_VENV),
                        help=f"a venv holding cosmic-ray; default, {DEFAULT_COSMIC_RAY_VENV}")
    parser.add_argument("--python", default=sys.executable,
                        help="the interpreter that runs each Python suite; default, this one")
    parser.add_argument("--recorded-inputs-directory", default=None,
                        help="where the suite runner keeps recorded inputs; default, the runner's")
    parser.add_argument("--lock-file", default=None,
                        help="the --lock-file given to the suite runner; default, the runner's")
    parser.add_argument("--mutant-timeout-seconds", type=float, default=None,
                        help="the limit on one run of a file's suites; default, the "
                             "longest suite's own limit times the runner's rounds, plus its "
                             "start-up")
    parser.add_argument(PARALLEL_MUTANT_WORKERS_FLAG, type=int, default=None, metavar="N",
                        help="run N mutants at once, each in a scratch worktree of its own, "
                             "with the python of --cosmic-ray-venv; default, one at a time, "
                             "by cosmic-ray exec")
    parser.add_argument(COSMIC_RAY_SESSIONS_DIRECTORY_KEPT_TO_RESUME_FLAG, default=None,
                        metavar="DIR",
                        help="keep each file's cosmic-ray session in DIR, and resume a session "
                             "already there, running only its mutants with no result")
    parser.add_argument(MUTANTS_RUN_AT_MOST_SHARED_EVENLY_AMONG_CHANGED_FILES_FLAG, type=int,
                        default=None, metavar="N",
                        help="in the full pass, run only N of the change's mutants, one from "
                             "each changed file in turn, in an order the head commit seeds; "
                             "the rest stay with no result in the kept sessions")
    parser.add_argument(NO_MUTANT_STARTED_AFTER_UNIX_TIME_FLAG, type=float, default=None,
                        metavar="UNIX_TIME",
                        help="in the full pass, start no mutant after this time; those not "
                             "started stay with no result in the kept sessions")
    parser.add_argument("--survived-and-errored-mutants-json-file", default=None,
                        help="a file to write the survived and errored mutants to, as JSON")
    parser.add_argument("--recorded-mutant-killed-check-verdicts-json-file-to-write", default=None,
                        help=f"with {RECORDED_MUTANT_KILLED_CHECK_COMMAND_LINE_FLAG}, a file to "
                             f"write each recorded mutant's verdict to, as JSON")
    arguments = parser.parse_args(argv)
    if arguments.recorded_mutant_killed_check is not None:
        if arguments.pull_request is not None or arguments.base is not None:
            parser.error(f"{RECORDED_MUTANT_KILLED_CHECK_COMMAND_LINE_FLAG} takes --head, or "
                         f"checks HEAD; not --pull-request or --base")
        if arguments.head is None:
            arguments.head = "HEAD"
        return arguments
    if arguments.parallel_mutant_workers is not None:
        if arguments.parallel_mutant_workers < 1:
            parser.error(f"{PARALLEL_MUTANT_WORKERS_FLAG} needs a count of 1 or more")
    for flag, value in (
            (MUTANTS_RUN_AT_MOST_SHARED_EVENLY_AMONG_CHANGED_FILES_FLAG,
             arguments.mutants_run_at_most_shared_evenly_among_changed_files),
            (NO_MUTANT_STARTED_AFTER_UNIX_TIME_FLAG,
             arguments.no_mutant_started_after_unix_time)):
        if value is not None and not (
                arguments.full_mutation_pass and arguments.parallel_mutant_workers is not None
                and arguments.cosmic_ray_sessions_directory_kept_to_resume is not None):
            parser.error(f"{flag} needs {FULL_MUTATION_PASS_COMMAND_LINE_FLAG}, "
                         f"{PARALLEL_MUTANT_WORKERS_FLAG}, whose workers run the mutants it "
                         f"leaves in, and {COSMIC_RAY_SESSIONS_DIRECTORY_KEPT_TO_RESUME_FLAG}, "
                         f"where the mutants it leaves out stay for a later run")
    if arguments.pull_request is None and arguments.head is None:
        parser.error("one of the arguments --pull-request --head is required")
    if arguments.head is not None and arguments.base is None:
        parser.error("--head needs --base")
    if arguments.pull_request is not None and arguments.base is not None:
        parser.error("--base goes with --head; a pull request's base is read with gh")
    return arguments


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == [COSMIC_RAY_TEST_COMMAND_RUN_TEST_SUITE_RUNNER_STOPPED_AFTER_SECONDS_FLAG]:
        return run_test_suite_runner_with_its_stderr_on_stdout_stopped_before_cosmic_ray_limit(
            float(argv[1]), argv[2], argv[3:])
    if argv[:1] == [COSMIC_RAY_SESSION_PENDING_MUTANTS_RUN_BY_PARALLEL_WORKERS_FLAG]:
        return cosmic_ray_session_pending_mutants_run_by_parallel_workers(
            argv[1], argv[2],
            None if argv[3] == ALL_MUTANTS_WITH_NO_RESULT_ARGUMENT else argv[3].split(","),
            (None if argv[4] == NO_UNIX_TIME_AFTER_WHICH_NO_MUTANT_STARTS_ARGUMENT
             else float(argv[4])),
            argv[5:])
    if argv[:1] == [COSMIC_RAY_ONE_WORK_ITEM_MUTATE_AND_TEST_FLAG]:
        return cosmic_ray_one_work_item_mutate_and_test()
    # A Bash tool timeout or TaskStop sends SIGTERM; raised as SystemExit, the stop still runs the
    # finally that removes the scratch worktree, and the TemporaryDirectory's exit.
    with stop_signals.stop_signals_raise_system_exit_so_cleanup_runs():
        return main_with_stop_signals_raising_system_exit(argv)


def main_with_stop_signals_raising_system_exit(argv):
    arguments = parse_arguments(argv)
    checkout = Path(arguments.checkout).resolve()
    runner = load_test_suite_runner()
    # An inherited GIT_DIR or GIT_WORK_TREE would point every git command at another repository,
    # and cosmic-ray launches the suites with this environment, as the runner launches them.
    environment = runner.launch_environment_for_a_test_suite_with_git_redirecting_agent_session_attendance_and_credential_variables_removed()
    test_suite_runner_log_directories_parents_past_retention_removed(tempfile.gettempdir(),
                                                                     time.time())
    # Resolved, as the runner resolves the --log-dir it names in its first line.
    log_directories_parent = Path(tempfile.mkdtemp(
        prefix=TEST_SUITE_RUNNER_LOG_DIRECTORIES_PARENT_PREFIX)).resolve()
    stopped_by_signal = False
    try:
        return quick_or_full_mutation_pass_or_recorded_mutant_killed_check(
            arguments, checkout, runner, environment, log_directories_parent)
    except SystemExit as stop:
        stopped_by_signal = stop.code in {128 + number for number in stop_signals.STOP_SIGNALS}
        raise
    finally:
        test_suite_runner_log_directories_parent_removed_or_named_as_kept(
            log_directories_parent,
            stopped_by_signal and arguments.cosmic_ray_sessions_directory_kept_to_resume is None)


def quick_or_full_mutation_pass_or_recorded_mutant_killed_check(
        arguments, checkout, runner, environment, log_directories_parent):
    try:
        if arguments.recorded_mutant_killed_check is not None:
            return recorded_mutant_killed_check(arguments, checkout, environment, runner,
                                                log_directories_parent)
        tools = cosmic_ray_tool_paths(arguments.cosmic_ray_venv)
        if arguments.parallel_mutant_workers is not None:
            # Not resolved: the venv's python is a link, and only run by that name does it
            # import the venv's cosmic-ray.
            tools["python"] = str(Path(arguments.cosmic_ray_venv).expanduser().resolve()
                                  / "bin" / "python")
            if not Path(tools["python"]).is_file():
                raise CouldNotRun(
                    f"{PROGRAM}: not run — {tools['python']} is not there, and "
                    f"{PARALLEL_MUTANT_WORKERS_FLAG} runs its workers with the python of "
                    f"the cosmic-ray venv, the one that imports cosmic-ray.\n"
                    f"Give --cosmic-ray-venv the venv cosmic-ray was installed into with pip, "
                    f"or run this again without {PARALLEL_MUTANT_WORKERS_FLAG}.")
        if arguments.pull_request is not None:
            # gh needs the credential that the suites' environment leaves out.
            head, base = head_and_base_of_pull_request(
                arguments.pull_request, checkout,
                runner.environment_without_git_redirecting_variables())
        else:
            head, base = arguments.head, arguments.base
        head = run_or_raise(["git", "rev-parse", "--verify", f"{head}^{{commit}}"],
                            checkout, environment,
                            what=f"git rev-parse {head}").strip()
        merge_base = run_or_raise(["git", "merge-base", head, base], checkout,
                                  environment,
                                  what=f"git merge-base {head} {base}").strip()
        if merge_base == head:
            number = (arguments.pull_request if arguments.pull_request is not None
                      else "<number>")
            raise CouldNotRun(
                f"{PROGRAM}: not run — head {head[:12]} is already in {base}, so "
                f"there are no changed lines to test. Either the pull request is "
                f"merged, or it adds no commits of its own.\n"
                f"If it is merged and you want to test what it changed:\n"
                f"  gh pr view {number} --json headRefOid,baseRefOid\n"
                f"  git fetch origin <baseRefOid>\n"
                f"  then run this again with --head <headRefOid> --base <baseRefOid>.\n"
                f"If it adds no commits of its own, there is nothing to test.")
        files = changed_python_files_to_mutate(checkout, merge_base, head,
                                               environment)
        try:
            recordings_directory = runner.recordings_directory_for(
                arguments.recorded_inputs_directory
                or runner.DEFAULT_RECORDED_INPUTS_DIRECTORY, checkout)
        except runner.CouldNotRun as refusal:
            # The runner's first line says what failed; the lines after it name the runner's
            # own command, so this program's next steps replace them.
            what_failed = str(refusal).splitlines()[0].replace(f"{runner.PROGRAM}:",
                                                               f"{PROGRAM}:", 1)
            raise CouldNotRun(what_failed + "\n"
                              + runner.git_failure_next_step_lines(Path(__file__).name)) \
                from refusal
        suites_listed_at_head = suites_at_head(checkout, head, environment)

        try:
            sandbox_prefix, unconfined_because = runner.signal_sandbox()
        except runner.SignalSandboxCouldNotStart as error:
            raise CouldNotRun(runner.signal_sandbox_refusal(error, PROGRAM)) from error
        print(runner.signal_sandbox_line(sandbox_prefix, unconfined_because), flush=True)

        totals = dict.fromkeys(OUTCOME_KEYS, 0)
        untested = []
        no_failure_handling_change = []
        all_survivors = []
        all_errored = []
        kept_log_directories = set()
        tracked_python_files_cache = {}
        # As the runner decides it, since the runner's rounds of suites set the limit.
        in_test_sandboxes = sys.platform.startswith("linux") and \
            runner.does_signal_sandbox_report_killed_suite_as_exit_code_128_plus_signal(
                sandbox_prefix)
        if (arguments.parallel_mutant_workers or 1) > 1 and not in_test_sandboxes:
            raise CouldNotRun(
                f"{PROGRAM}: not run — {PARALLEL_MUTANT_WORKERS_FLAG} "
                f"{arguments.parallel_mutant_workers} needs the suites to run in "
                f"nc-test-sandboxes, which they do not here, so each run of the suite runner "
                f"takes the machine's lock and every worker but one would be refused it.\n"
                f"Run this again with {PARALLEL_MUTANT_WORKERS_FLAG} 1, or without it.")
        if in_test_sandboxes:
            # The runner needs psutil there; refused here once, not once per mutant.
            psutil, refusal = runner.psutil_imported_or_why_not()
            if psutil is None:
                raise CouldNotRun(refusal.replace(f"{runner.PROGRAM}:", f"{PROGRAM}:", 1))
        recorded_inputs_directory = (arguments.recorded_inputs_directory
                                     or runner.DEFAULT_RECORDED_INPUTS_DIRECTORY)
        with tempfile.TemporaryDirectory(prefix=f"{PROGRAM}-") as scratch_name:
            # Resolved, as the cwd of every process run there reports it: on macOS the temporary
            # directory is under /var, a symbolic link to /private/var.
            scratch = Path(scratch_name).resolve()
            worktree = scratch / "worktree"
            worktrees = [worktree] + [scratch / f"worktree-of-mutant-worker-{number}" for number
                                      in range(2, (arguments.parallel_mutant_workers or 1) + 1)]
            try:
                for each in worktrees:
                    run_or_raise(["git", "worktree", "add", "--detach", str(each),
                                  head], checkout, environment,
                                 what=f"git worktree add at {head}")
                mutants_run_are_limited = (
                    arguments.mutants_run_at_most_shared_evenly_among_changed_files is not None
                    or arguments.no_mutant_started_after_unix_time is not None)
                mutant_job_ids_to_run_of_file = {}
                if mutants_run_are_limited:
                    mutant_job_ids_to_run_of_file = \
                        cosmic_ray_sessions_made_for_every_file_and_mutant_job_ids_to_run_chosen(
                            [(path, suites) for path, suites in (
                                (path, suites_for_file(path, suites_listed_at_head,
                                                       recordings_directory, runner))
                                for path in files) if suites],
                            worktree, scratch, tools, head, merge_base, arguments, environment,
                            runner, recorded_inputs_directory, recordings_directory,
                            in_test_sandboxes, log_directories_parent)
                for path in files:
                    suites = suites_for_file(path, suites_listed_at_head,
                                             recordings_directory, runner)
                    failure_handling_ranges = None
                    if arguments.quick_mutation_pass:
                        failure_handling_ranges = failure_handling_line_ranges_of_file(
                            worktree, path)
                        changed = line_numbers_at_head_of_lines_changed_since_merge_base(checkout, merge_base, head,
                                                               path, environment)
                        if not any(first <= number <= last for number in changed
                                   for first, last in failure_handling_ranges):
                            no_failure_handling_change.append(path)
                            print(f"NO FAILURE-HANDLING CHANGE  {path}: none of its changed "
                                  f"lines is in an except clause, or in an if, while or "
                                  f"conditional expression that tests an exit code, so the "
                                  f"quick mutation pass does not mutate it; nothing to do "
                                  f"for it")
                            continue
                        suites = quick_mutation_pass_suites(
                            suites, recordings_directory, runner, checkout, environment,
                            tracked_python_files_cache)
                    if not suites:
                        untested.append(path)
                        if arguments.quick_mutation_pass:
                            print(f"NO SUITE  {path}: once the repository-wide checks and "
                                  f"the suites that read every tracked Python file are left "
                                  f"out, no recorded suite reads it and it has no sibling "
                                  f"suite, so its changed failure-handling code is untested.\n"
                                  f"Write a suite that makes that code handle its failure, "
                                  f"and commit it.\n"
                                  f"Run it once with python3 scripts/run-all-test-suites.py "
                                  f"--only-suites-named <the suite's path>, which records "
                                  f"what it reads, so this program finds it.\n"
                                  f"Run scripts/{PROGRAM}.py again with the same options and the new head "
                                  f"commit.")
                        else:
                            print(f"NO SUITE  {path}: no recorded suite reads it and it "
                                  f"has no sibling suite, so its changed lines are untested")
                        continue
                    print(f"MUTATING  {path} with {', '.join(suites)}", flush=True)
                    outside = runner.SUITES_RUN_WITHOUT_ANY_SANDBOX
                    for suite in suites:
                        if sandbox_prefix and suite in outside:
                            print(f"NO SANDBOX  {suite} runs WITHOUT the signal "
                                  f"sandbox: {outside[suite]}", flush=True)
                    counts, survivors, errored, errored_outputs = mutation_test_one_file(
                        path, suites, worktrees, scratch, tools, head, merge_base, arguments,
                        environment, runner, recorded_inputs_directory, recordings_directory,
                        in_test_sandboxes, log_directories_parent, failure_handling_ranges,
                        mutants_run_are_limited, mutant_job_ids_to_run_of_file.get(path))
                    # Only an errored mutant's log shows a failure reported; a killed mutant's
                    # and the passing baseline's are not read.
                    kept_log_directories |= {
                        log_dir for output in errored_outputs
                        for log_dir in test_suite_runner_log_directories_named_in_output(
                            output, runner)}
                    # An ERRORED mutant whose output names no log directory, such as one
                    # cosmic-ray recorded only as "timeout", may own any of this file's.
                    if any(not test_suite_runner_log_directories_named_in_output(output, runner)
                           for output in errored_outputs):
                        kept_log_directories |= set(log_directories_parent.iterdir())
                    remove_test_suite_runner_log_directories_not_kept(log_directories_parent,
                                                                      kept_log_directories)
                    all_survivors += survivors
                    all_errored += errored
                    for key in totals:
                        totals[key] += counts[key]
                    for label, mutants in (("SURVIVED", survivors),
                                           ("ERRORED ", errored)):
                        for mutant in mutants:
                            reason = f" ({mutant['reason']})" if mutant["reason"] else ""
                            print(f"{label}  {mutant['module_path']}:{mutant['line']} "
                                  f"{mutant['operator']}{reason}")
                            for diff_line in mutant["diff"].splitlines():
                                print(f"    {diff_line}")
            finally:
                for each in worktrees:
                    remove_worktree(checkout, each, environment)
    except SuiteFailsOnUnmutatedHead as failure:
        print(str(failure), file=sys.stderr)
        return EXIT_SUITE_FAILS_ON_UNMUTATED_HEAD
    except CouldNotRun as failure:
        print(str(failure), file=sys.stderr)
        return EXIT_COULD_NOT_RUN

    tested = totals["killed"] + totals["survived"] + totals["errored"]
    lines_mutated = ("changed failure-handling lines" if arguments.quick_mutation_pass
                     else "changed lines")
    no_failure_handling_change_count = (
        f"{len(no_failure_handling_change)} changed file(s) with no failure-handling change; "
        if arguments.quick_mutation_pass else "")
    print(f"SUMMARY: {tested} mutants on {lines_mutated} of "
          f"{len(files) - len(untested) - len(no_failure_handling_change)} "
          f"file(s): {totals['killed']} killed, {totals['survived']} survived, "
          f"{totals['errored']} errored, {totals['not run']} not run; "
          f"{no_failure_handling_change_count}{len(untested)} changed file(s) "
          f"with no suite; head {head[:12]}, merge base {merge_base[:12]}")
    if arguments.survived_and_errored_mutants_json_file is not None:
        try:
            Path(arguments.survived_and_errored_mutants_json_file).write_text(json.dumps({
                "head": head, "merge_base": merge_base, "survived": all_survivors,
                "errored": all_errored, "files_with_no_suite": untested,
                "mutants_not_run_count": totals["not run"]}, indent=1) + "\n",
                encoding="utf-8")
        except OSError as error:
            print(f"{PROGRAM}: the survived and errored mutants were not written to "
                  f"{arguments.survived_and_errored_mutants_json_file}: {error}. The lines "
                  f"above are this run's whole result.\n"
                  f"Run scripts/{PROGRAM}.py again with "
                  f"--survived-and-errored-mutants-json-file naming a path in a directory "
                  f"you can write to, or without that option if you need no JSON file.",
                  file=sys.stderr)
            return EXIT_COULD_NOT_RUN
    if totals["survived"] or totals["errored"] or totals["not run"] or untested:
        return EXIT_SURVIVORS_OR_UNTESTED_FILES
    return EXIT_EVERY_MUTANT_KILLED


if __name__ == "__main__":
    sys.exit(main())
