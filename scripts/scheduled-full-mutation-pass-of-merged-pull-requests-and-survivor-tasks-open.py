#!/usr/bin/env python3
"""Run the full mutation pass on each pull request merged into main since the last run, on at most 12 of its mutants first and on the rest as time allows, open a task for each line with surviving mutants, and recheck each open task on main.

Usage:
  scripts/scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open.py
      [--clone DIR] [--log-store-root DIR] [--state-directory DIR]
      [--task-lists-directory DIR] [--agent-seats-directory DIR]
      [--cosmic-ray-venv DIR] [--mutation-testing-program PATH]
      [--merge-timeout-seconds S]
      [--survivor-task-recorded-mutant-killed-check-timeout-seconds S]
      [--scheduled-jobs-on-each-machine-json-file PATH]
      [--second-pass-stops-starting-mutants-seconds-before-next-scheduled-run S]

Every option is a seam for this program's test and for a run made by hand that
must not touch the real state, task lists or log-store. A scheduled run
passes none.

TERMS. A mutant's key is the SHA-256 of a JSON list of its file path, cosmic-ray
operator and diff. A mutant's diff file holds its diff, as
scheduled-full-mutation-pass-runs-of-merged-pull-requests/surviving-mutant-diffs/<key>.diff
under --log-store-root, which is where
the --recorded-mutant-killed-check of
scripts/mutation-testing-changed-lines-quick-or-full-pass-survivors.py, the
mutation testing program, reads it from. A survivor task is a task this
program opens for the surviving mutants of one line; its subject starts
`Surviving mutants in <file>:<line>: ` (`Surviving mutant in` in a task an
earlier version opened). The task's owner is the agent-seat whose task list
holds it (TASKS below). The state file is state.json in --state-directory: the
last main commit mutation-tested, under last_tested_main_commit, and, under
tasks_opened, each surviving mutant's key with the agent-seat and id of the
survivor task that lists it, and, under untestable_merges, which a state file
may lack, each merge recorded as untestable (AN UNTESTABLE MERGE below) with
the suites that fail on its unchanged code, and, under
merges_with_mutants_not_run, which a state file may lack, each merge recorded
as tested whose mutants are not all run (THE TWO PASSES below).

WHAT ONE RUN DOES, in order.

  1. Takes an exclusive lock on
     scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open.lock
     in --state-directory; while another run holds it, this run exits
     EXIT_ANOTHER_RUN_HOLDS_THE_LOCK having done nothing, and the next
     scheduled run carries on. The command a job failure task gives for a
     hand run of one merge takes the same lock, but waits for it instead of
     exiting: that hand run resumes the kept sessions this program uses.
  2. Runs `git fetch origin main` in the clone and resolves origin/main.
  3. Reads the state file. With no state file, it writes one naming
     origin/main and tests nothing: the merges after that commit are tested
     from the next run on.
  4. Checks that each survivor task the state names still holds each of its
     mutants: the task file is still on its owner's task list and not marked
     completed. A task whose description no longer names a mutant's diff file,
     as after an agent rewrites the description, still holds the mutant unless
     exactly one other open task names the diff file, and the recheck writes
     the description again. A mutant whose task no longer holds it, because
     the task is marked completed, or its file is gone or cannot be read, or
     its description no longer names the diff file while another open task
     does, goes one of three ways:
     - Moved: when exactly one other task on the same list, not marked
       completed, names its diff file, the state alone is changed to name that
       task, as when an agent moves the mutants of several survivor tasks into
       one and marks the others completed, whether or not the session-handoff
       has yet removed those completed tasks.
     - Finished: when its task is marked completed and no task not marked
       completed names its diff file, the state stops naming it.
     - Reported once: in every other case, which is one of these:
       - its task's file is gone or cannot be read, and no other open task
         names the diff file, or two or more do;
       - its task is not marked completed but no longer names the diff file,
         and two or more other open tasks do;
       - its task is marked completed and two or more other open tasks name
         the diff file.
     Reporting it goes like this:
     the record naming it is written at once, and only then does the state
     stop naming it, so a run killed later has still reported it; standard
     error names it at the end, and the run goes on and exits
     EXIT_OPENED_TASK_NO_LONGER_HOLDS_ITS_SURVIVOR. A record that cannot be
     written then stops the run, with the state still naming the mutant. The
     run opens no task in its place: it cannot tell a task lost from one
     deleted after it was finished, such as by a session-handoff's removal of
     completed tasks.
  5. Rechecks each survivor task the state still names (THE RECHECK below).
  6. The first pass. For each commit on main's first-parent line after the
     last one tested, oldest first, which is each merge of a pull request,
     runs scripts/mutation-testing-changed-lines-quick-or-full-pass-survivors.py
     with --full-mutation-pass, --head the commit and --base its first
     parent, so the lines that pull request changed are mutated, with
     --cosmic-ray-venv, --survived-and-errored-mutants-json-file,
     --parallel-mutant-workers, --cosmic-ray-sessions-directory-kept-to-resume
     (CARRYING A MERGE ON below) and
     --mutants-run-at-most-shared-evenly-among-changed-files
     FIRST_PASS_MUTANTS_RUN_PER_MERGE_AT_MOST, 12 (THE TWO PASSES below). The
     worker count, read as each merge starts, is the machine's cores less its
     load average over the last minute, at least 1; each worker has a
     worktree of its own, and its suites still wait for the suite runner's
     admission.
  7. Opens a survivor task for each line with surviving mutants (TASKS
     below), and one job failure task for the merge's ERRORED mutants (JOB
     FAILURE TASKS below), then records the commit as tested, and, when
     mutants of it were not run, under merges_with_mutants_not_run in the
     state, so a merge has its first pass once. No ERRORED mutant is run
     again.
  8. The second pass, when the first pass reached every merge: runs the
     mutants not run, newest merge first (THE TWO PASSES below), and opens
     their survivor tasks.
  9. Opens a task for each failure of the run (JOB FAILURE TASKS below).
  10. Writes the record (THE RECORD below), in full over any written at step
     4, and prints its citation.

THE TWO PASSES. The first pass runs at most
FIRST_PASS_MUTANTS_RUN_PER_MERGE_AT_MOST mutants of a merge, which the
mutation testing program chooses: one from each changed file in turn, so a
short file is given as many as a long one, in an order the merge's commit
seeds, so a merge carried on or run again has the same mutants chosen. The
merge's kept cosmic-ray sessions (CARRYING A MERGE ON below) hold every mutant
of the merge and the result of each mutant run: they are this program's record
of which mutants are judged, and the mutation testing program runs no mutant
that has a result there. A merge with mutants not run is recorded under
merges_with_mutants_not_run in the state, with merged_at_unix_seconds, the
time of its commit, mutants_not_run_count, and
surviving_mutant_keys_already_handled, the key of each surviving mutant an
earlier run of the merge reported, which a later run of the merge leaves out,
since the mutation testing program reports the survivors of every run of a
merge each time, and errored_mutant_keys_already_reported, which an entry may
lack, the same for each ERRORED mutant, whose key holds its line as well.
The second pass takes the merges recorded there, newest first, and runs the
mutation testing program on each as the first pass does, but with
--no-mutant-started-after-unix-time in place of
--mutants-run-at-most-shared-evenly-among-changed-files, so every mutant of
the merge not yet run is run, until that time. That time is
--second-pass-stops-starting-mutants-seconds-before-next-scheduled-run, by
default 30 minutes, before cron next starts this program on ned-box, which
this program reads from its schedule in --scheduled-jobs-on-each-machine-json-file,
by default nc-systems/general-tools/scheduled-jobs-on-each-machine.json, a
schedule of the form `<minute> <hour> * * *`: a run still going when cron
starts the next one would make that one exit
EXIT_ANOTHER_RUN_HOLDS_THE_LOCK. From that time on the second pass starts on
no further merge. The mutation testing program is sent SIGTERM when it is
still going after --merge-timeout-seconds or, when sooner, once half of
--second-pass-stops-starting-mutants-seconds-before-next-scheduled-run has
passed since that time; the merge then keeps its place under
merges_with_mutants_not_run, and the run exits
EXIT_MERGE_CARRIED_ON_TO_NEXT_RUN. After each merge the second pass opens the
survivor tasks of the mutants it ran, as step 7 does, and writes the merge's
new mutants_not_run_count; a merge with none left leaves the state, and a
merge a suite now fails on with no mutant applied is recorded as untestable
(AN UNTESTABLE MERGE below) and leaves it too. The second pass never changes
last_tested_main_commit. No merge is dropped from merges_with_mutants_not_run
for being old.

CARRYING A MERGE ON. Each merge's cosmic-ray sessions are kept in
cosmic-ray-sessions-kept-for-unfinished-merges/<merge>
(COSMIC_RAY_SESSIONS_KEPT_FOR_UNFINISHED_MERGES_DIRECTORY_NAME) under
--state-directory. A run of the mutation testing program still going after
--merge-timeout-seconds is sent SIGTERM, on which that program removes its
scratch worktrees; in the first pass, the merge is not recorded as tested, the
run tests no later merge and has no second pass, and the next run goes on with
this merge from the first of its chosen mutants with no result. Each run
first removes the kept sessions of every merge that is neither waiting for
its first pass nor recorded under merges_with_mutants_not_run.

AN UNTESTABLE MERGE. When the mutation testing program exits
EXIT_SUITE_FAILS_ON_UNMUTATED_HEAD, because a suite fails on the merge's
unchanged code, and names each such suite on standard error, the run opens a
job failure task naming the merge and those suites, then records the merge
under untestable_merges in the state, with those suites, and as tested, and
goes on to the next merge, which it never tries again. A task that cannot be
opened is a failed step, and the merge is not recorded.

A step that fails stops the run there, and steps 9 and 10 still run, to open
the failure's task and write the record: a failed fetch, a state file that
cannot be read or no longer names an ancestor of origin/main, a scheduled jobs
file that cannot be read or gives this program no schedule of the form above,
a survivor task,
diff file or state file that the recheck cannot read or write, a missing
cosmic-ray venv, a kept session that cannot be read or removed, a mutation
testing run that exits other than 0, 1 or EXIT_SUITE_FAILS_ON_UNMUTATED_HEAD,
as when git fails, a suite runs out of time or the disk is full, or that
writes no readable JSON, a
mutant's diff or task that cannot be written, and an error this program does
not handle, whose traceback the record keeps.
The commit it stopped at is not recorded as tested, so the next run tries it
again; a line already given a task is not given a second one, since a line
counts as given a task when the state names a task for each of its surviving
mutants or when its owner's list holds a survivor task for the line not
marked completed, which covers a task opened just before a write of the state
or the `.highwatermark` failed. The record names the failure, and the run
exits EXIT_STEP_FAILED. A changed file with no suite is named in the record
and gets no task.

TASKS. The surviving mutants of one merge are grouped by file and line, and
each line gets at most one survivor task. A mutant the state already names is
left out of its line's group, and a line whose group is then empty gets no
task. The owner is the author `git blame` gives the line at the merge, since
each agent-seat commits under its own name; when that agent-seat has no task
list directory or no checkout under --agent-seats-directory, as after it is
retired, the owner is merge-lane-2, the agent-seat
SURVIVOR_TASK_AGENT_SEAT_WHEN_LINE_AUTHOR_IS_RETIRED_OR_UNKNOWN names. Before
a task is opened or rewritten, each new mutant's diff file is written. A task
is a Claude Code task file, `<id>.json` in the task list directory
`nedschorus-<owner>-tasks` under --task-lists-directory, with the keys id,
subject, description, status, blocks and blockedBy. Its id is one more than
the highest of the list's task ids and its `.highwatermark`, as Claude Code
numbers a new task; the file is linked into place only where no file of that
name exists, and the `.highwatermark` is raised to it, so a task Claude Code
creates at the same moment is not overwritten. The description names how
many of the line's mutants survived and their cosmic-ray operators, shows each
mutant's diff and diff file, and gives this task's command: the mutation
testing program's --recorded-mutant-killed-check with every diff file the
task lists. It asks the owner to add a test that kills the mutants and put
the command's output in the pull request, or to end the line with a `#
pragma: no mutate` comment saying why no test can, which every mutation pass
then skips; and to leave the task open for the recheck to complete. A line
whose owner's list holds a survivor task for it not marked completed gets no
second task: that task is rewritten to list its mutants the state names and
the line's new ones, with one command for them all, and the state names that
task for each. A task Claude Code rewrites at the same moment as this
program can lose either rewrite; the next run's recheck then lists again each
mutant the state gives the task.

THE RECHECK runs, for each survivor task the state names, the mutation
testing program's --recorded-mutant-killed-check with every diff file the
state gives the task, --head origin/main and
--recorded-mutant-killed-check-verdicts-json-file-to-write. A mutant it judges
killed, or no longer existing because its replaced lines are gone from main
or its line ends with a `# pragma: no mutate` comment, leaves the task and
the state. A task with no mutant left is marked completed, with a line saying
why at the end of its description. A task with fewer mutants left, or whose
description does not give the command for exactly the mutants left or does
not end with SURVIVOR_TASK_DESCRIPTION_LAST_LINE_LEAVE_TASK_OPEN_FOR_NIGHTLY_RECHECK,
"Leave this task open: the nightly mutation pass completes it once no mutant
it lists survives on main, or the line is gone or ends with a `# pragma: no
mutate` comment.",
as in a task an earlier version opened, is rewritten to list only them; its
other keys, status included, are kept. A mutant the program could not judge
stays listed. A run of the program still going after
--survivor-task-recorded-mutant-killed-check-timeout-seconds is sent SIGTERM;
a run that writes no readable verdicts leaves its task as it was, is named in
the record and on standard error, and the run goes on and exits
EXIT_SURVIVOR_TASK_MUTANTS_NOT_JUDGED_TASK_LEFT_AS_IT_WAS. Each rechecked
mutant adds about 30 seconds to the run.

JOB FAILURE TASKS. The run opens a task on the task list of the agent-seat
JOB_FAILURE_TASK_AGENT_SEAT names, fleet-restart-at-login, saying what failed and what to do, for each
failure of the run itself: a step that failed, as above; a merge recorded
as untestable, opened as AN UNTESTABLE MERGE above says; a merge carried on
in the first pass with no mutant judged beyond those its kept sessions held
before the run; a
survivor task whose recheck gave no verdicts; a run record that could not be
written, opened after the failed write; and any merge still not recorded as
tested MERGE_STILL_UNTESTED_TASK_OPENED_AFTER_SECONDS_SINCE_MERGE, three days,
after its merge commit, the sign that the first pass no longer keeps up and
that it must run fewer mutants; and a merge with mutants the mutation testing
program reports ERRORED, whose suites gave no verdict on them. A failed step's
task has the first line of its message as its subject; the task of an
untestable merge, a carried-on merge or a merge with ERRORED mutants names
the merge; an untestable merge's task also names the failing suites, and asks
for the merge's changed lines to be mutation-tested at a later main commit
where they pass.
A merge's ERRORED mutants get one task, opened before the merge is recorded
as tested, which the merge is all the same. The task names each such mutant
by file, line and cosmic-ray operator, with the reason the mutation testing
program gives from the mutant's output, such as `No space left on device` or
a timeout, or `cosmic-ray could not judge it` when it gives none, and asks
the agent-seat to judge each. The run never runs an ERRORED mutant again. A
later run of the merge, in the second pass, opens the task again, or
rewrites its description while it is open, only when it reports an ERRORED
mutant that errored_mutant_keys_already_reported does not hold. A task that
cannot be opened or rewritten is a failed step, and the merge is not
recorded.
Each of the other three kinds has one task with a fixed subject:
SURVIVOR_TASKS_NOT_RECHECKED_TASK_SUBJECT, "Nightly full mutation pass:
survivor tasks left as they were, because their recheck gave no verdicts",
whose description names the survivor tasks not rechecked;
RUN_RECORD_NOT_WRITTEN_TASK_SUBJECT, "Nightly full mutation pass: a run's
record was not written", whose description gives the error; and
MERGES_STILL_UNTESTED_THREE_DAYS_AFTER_MERGING_TASK_SUBJECT, "Nightly full
mutation pass: merges still untested three days after they merged", whose
description gives the untested merges' count and the oldest. Each run rewrites
the description of such a task while it is open. While a task with the same
subject is open on that list, no second one is opened, and the record names
the open one. No task is completed by this program: the agent-seat
completes it once the cause is fixed. A task that cannot be opened is named
in the record and on standard error, and the run exits EXIT_STEP_FAILED; the
task for a record not written, when it cannot be opened, is named on standard
error only, and the run still exits EXIT_RECORD_NOT_WRITTEN.

THE RECORD is one text file per run in the log-store:

  nedlern@ned-box:/home/nedlern/nedschorus-logs/scheduled-full-mutation-pass-runs-of-merged-pull-requests/<UTC start>.txt

It holds origin/main, the commit the run started after, a line per survivor
task rechecked with its verdicts and what was done to the task, a line per
merge with its worker count, the mutants its kept sessions already held and
the mutation testing program's SUMMARY line, or, for a merge recorded as
untestable, the suites that fail on its unchanged code, or, for a merge carried on, how
many mutants are judged, a line per job failure task, a line per surviving
mutant with the task it was given or was added to, a line per ERRORED mutant
with its reason and its job failure task, a line per changed file with no
suite, each failure, a line opening MUTANTS NOT RUN
with how many mutants of how many merges recorded as tested are not run, and
the oldest such merge with its age in days, read in the maintenance cycle,
where the user decides when old ones are dropped, and the wall-clock seconds.
A merge of the second pass has the same lines as one of the first, and repeats
the merge's ERRORED mutants and changed files with no suite.
This program runs on ned-box only, so the record is written locally. A record
that cannot be written is printed on standard output instead, and the run
exits EXIT_RECORD_NOT_WRITTEN.

SCHEDULE. Installed on ned-box by
nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py from
nc-systems/general-tools/scheduled-jobs-on-each-machine.json, with both output
streams appended to its log, which, with the record, is where its failures
are read. Run by hand on ned-box, from an agent's shell too, as a unit of the
user's systemd, which outlives the shell, with its output in the same log:

    systemd-run --user --unit=scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open-by-hand --collect -p StandardOutput=append:/home/nedlern/.claude/scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open.log -p StandardError=append:/home/nedlern/.claude/scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open.log /usr/bin/python3 /home/nedlern/Projects/nedschorus/scripts/scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open.py

The cron line, at 00:30 in ned-box's local time, America/Los_Angeles (Pacific):

    30 0 * * * /usr/bin/python3 /home/nedlern/Projects/nedschorus/scripts/scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open.py >> /home/nedlern/.claude/scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open.log 2>&1

Exit codes: 0 every survivor task was rechecked and every merge since the last
run had its first pass and its survivors and ERRORED mutants given tasks, or was recorded as
untestable with its job failure task opened, or the first run wrote the state
file; EXIT_STEP_FAILED (4) a step failed, as above;
EXIT_RECORD_NOT_WRITTEN (5) the record could not be written;
EXIT_ANOTHER_RUN_HOLDS_THE_LOCK (6) another run holds the lock;
EXIT_OPENED_TASK_NO_LONGER_HOLDS_ITS_SURVIVOR (7) no step failed, but a
mutant a survivor task an earlier run opened held was reported at step 4:
its task's file is gone or cannot be read, and no other open task or two or
more name it; or its task, not marked completed, no longer lists it, and two
or more other open tasks name it; or its task is marked completed and two or
more other open tasks name it;
EXIT_SURVIVOR_TASK_MUTANTS_NOT_JUDGED_TASK_LEFT_AS_IT_WAS (8) no step failed
and no task was lost, but the recheck gave no verdicts for a survivor task;
EXIT_MERGE_CARRIED_ON_TO_NEXT_RUN (9) none of those, but a merge ran past the
limit, in either pass, and is carried on.
EXIT_ANOTHER_RUN_HOLDS_THE_LOCK (6) comes before all the others: the run exits
with it at once, before any step, so none of them can apply. When more than one
of the others applies, the run exits with the first of 5, 4, 7, 8 and 9 that
applies: an unwritten record outranks a failed step, which outranks a lost
task, which outranks an unjudged recheck, which outranks a carried-on merge.
"""

# Messages here follow docs/nedschorus-wiki/nedschorus-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md.

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import shlex
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

PROGRAM = "scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open"
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
JOB_LOG_FILE = f"/home/nedlern/.claude/{PROGRAM}.log"
# Run from an agent's shell, a plain command dies with the shell's time limit; a unit of the
# user's systemd outlives it.
RUN_BY_HAND = (f"systemd-run --user --unit={PROGRAM}-by-hand --collect "
               f"-p StandardOutput=append:{JOB_LOG_FILE} -p StandardError=append:{JOB_LOG_FILE} "
               f"/usr/bin/python3 /home/nedlern/Projects/nedschorus/scripts/{PROGRAM}.py")
HAND_RUNS_DIRECTORY_NAME = "scheduled-full-mutation-pass-hand-runs"

MUTATION_TESTING_PROGRAM = Path(__file__).resolve().with_name(
    "mutation-testing-changed-lines-quick-or-full-pass-survivors.py")
DEFAULT_LOG_STORE_ROOT = "/home/nedlern/nedschorus-logs"
RECORDS_DIRECTORY_NAME = "scheduled-full-mutation-pass-runs-of-merged-pull-requests"
SURVIVING_MUTANT_DIFFS_DIRECTORY_NAME = "surviving-mutant-diffs"
LOG_STORE_HOST = "nedlern@ned-box"
DEFAULT_STATE_DIRECTORY = (Path.home() / ".local" / "state" / "nedschorus"
                           / "scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open")
STATE_FILE_NAME = "state.json"
UNTESTABLE_MERGES_STATE_KEY = "untestable_merges"
MERGES_WITH_MUTANTS_NOT_RUN_STATE_KEY = "merges_with_mutants_not_run"
ERRORED_MUTANT_KEYS_ALREADY_REPORTED_STATE_KEY = "errored_mutant_keys_already_reported"
FIRST_PASS_MUTANTS_RUN_PER_MERGE_AT_MOST = 12
SCHEDULED_JOBS_ON_EACH_MACHINE_JSON_FILE = (
    REPOSITORY_ROOT / "nc-systems" / "general-tools" / "scheduled-jobs-on-each-machine.json")
DEFAULT_SECOND_PASS_STOPS_STARTING_MUTANTS_SECONDS_BEFORE_NEXT_SCHEDULED_RUN = 30 * 60
LOCK_FILE_NAME = "scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open.lock"
DEFAULT_TASK_LISTS_DIRECTORY = Path.home() / ".claude" / "tasks"
DEFAULT_AGENT_SEATS_DIRECTORY = Path.home() / "agents"
SURVIVOR_TASK_AGENT_SEAT_WHEN_LINE_AUTHOR_IS_RETIRED_OR_UNKNOWN = "merge-lane-2"
TASK_FILE_NAME_PATTERN = re.compile(r"[1-9][0-9]*\.json")
TASK_HIGH_WATER_MARK_FILE_NAME = ".highwatermark"
DEFAULT_MERGE_TIMEOUT_SECONDS = 6 * 3600
COSMIC_RAY_SESSIONS_KEPT_FOR_UNFINISHED_MERGES_DIRECTORY_NAME = (
    "cosmic-ray-sessions-kept-for-unfinished-merges")
# cosmic-ray 8.7.0's session schema: one row of work_results per mutant with a result, the
# mutants its filters skipped included, under worker_outcome SKIPPED.
COSMIC_RAY_SESSION_JUDGED_MUTANTS_QUERY = (
    "SELECT COUNT(*) FROM work_results WHERE worker_outcome != 'SKIPPED'")
JOB_FAILURE_TASK_AGENT_SEAT = "fleet-restart-at-login"
MERGE_STILL_UNTESTED_TASK_OPENED_AFTER_SECONDS_SINCE_MERGE = 3 * 24 * 3600
MERGES_STILL_UNTESTED_THREE_DAYS_AFTER_MERGING_TASK_SUBJECT = (
    "Nightly full mutation pass: merges still untested three days after they merged")
SURVIVOR_TASKS_NOT_RECHECKED_TASK_SUBJECT = (
    "Nightly full mutation pass: survivor tasks left as they were, because their recheck gave "
    "no verdicts")
RUN_RECORD_NOT_WRITTEN_TASK_SUBJECT = "Nightly full mutation pass: a run's record was not written"
DEFAULT_SURVIVOR_TASK_RECORDED_MUTANT_KILLED_CHECK_TIMEOUT_SECONDS = 2 * 3600
RECORDED_MUTANT_KILLED_CHECK_FLAG = "--recorded-mutant-killed-check"
SURVIVOR_TASK_SUBJECT_PLACE = re.compile(r"Surviving mutants? in (\S+:[0-9]+): ")
SURVIVOR_TASK_DESCRIPTION_LAST_LINE_LEAVE_TASK_OPEN_FOR_NIGHTLY_RECHECK = (
    "Leave this task open: the nightly mutation pass completes it once no mutant it lists "
    "survives on main, or the line is gone or ends with a `# pragma: no mutate` comment.")
SECONDS_FOR_MUTATION_TESTING_PROGRAM_TO_CLEAN_UP_AFTER_SIGTERM = 120

EXIT_ALL_DONE = 0
EXIT_STEP_FAILED = 4
EXIT_RECORD_NOT_WRITTEN = 5
EXIT_ANOTHER_RUN_HOLDS_THE_LOCK = 6
EXIT_OPENED_TASK_NO_LONGER_HOLDS_ITS_SURVIVOR = 7
EXIT_SURVIVOR_TASK_MUTANTS_NOT_JUDGED_TASK_LEFT_AS_IT_WAS = 8
EXIT_MERGE_CARRIED_ON_TO_NEXT_RUN = 9
MUTATION_TESTING_EXITS_WITH_A_VERDICT = (0, 1)


def module_loaded_by_path(module_name, path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mutation_testing = module_loaded_by_path(
    "mutation_testing_changed_lines_quick_or_full_pass_survivors", MUTATION_TESTING_PROGRAM)
git_redirecting_removal = module_loaded_by_path(
    "git_redirecting_environment_variables_removal_common",
    REPOSITORY_ROOT / "nc-systems" / "general-tools"
    / "git-redirecting-environment-variables-removal-common.py")
agent_seat_task_list = module_loaded_by_path(
    "agent_seat_task_list_new_pending_task_write_common",
    REPOSITORY_ROOT / "nc-systems" / "general-tools"
    / "agent-seat-task-list-new-pending-task-write-common.py")
agent_seat_task_list_new_pending_task_write = (
    agent_seat_task_list.agent_seat_task_list_new_pending_task_write)


class StepFailed(Exception):
    """A step failed; the message says which, and what to do."""


def git(clone, *arguments):
    return subprocess.run(
        ["git", "-C", str(clone), *arguments],
        env=git_redirecting_removal.environment_without_git_redirecting_variables(),
        stdin=subprocess.DEVNULL, capture_output=True, text=True, errors="replace", check=False)


def git_or_raise(clone, *arguments):
    completed = git(clone, *arguments)
    if completed.returncode:
        raise StepFailed(
            f"git {' '.join(arguments)} failed in {clone} (exit {completed.returncode}): "
            f"{' '.join(completed.stderr.split()) or 'no detail'}. "
            f"Fix what git reports, then run this program again on ned-box: {RUN_BY_HAND}")
    return completed.stdout.strip()


def take_lock(lock_file):
    """Return the locked handle, or None while another run holds the lock."""
    handle = open(lock_file, "a")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


def write_state(state_file, state):
    partial = state_file.with_name(state_file.name + ".partial")
    partial.write_text(json.dumps(state, indent=1) + "\n", encoding="utf-8")
    os.replace(partial, state_file)


def read_state(state_file):
    """The state, or None when there is no state file."""
    try:
        text = state_file.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    try:
        state = json.loads(text)
        if not isinstance(state["last_tested_main_commit"], str) \
                or not isinstance(state["tasks_opened"], dict) \
                or not isinstance(state.get(MERGES_WITH_MUTANTS_NOT_RUN_STATE_KEY, {}), dict):
            raise TypeError("a key holds the wrong type")
        for not_run in state.get(MERGES_WITH_MUTANTS_NOT_RUN_STATE_KEY, {}).values():
            if not isinstance(not_run["merged_at_unix_seconds"], int) \
                    or not isinstance(not_run["mutants_not_run_count"], int) \
                    or not isinstance(not_run["surviving_mutant_keys_already_handled"], list) \
                    or not isinstance(
                        not_run.get(ERRORED_MUTANT_KEYS_ALREADY_REPORTED_STATE_KEY, []), list):
                raise TypeError(f"a merge under {MERGES_WITH_MUTANTS_NOT_RUN_STATE_KEY} holds "
                                f"the wrong type")
    except (ValueError, KeyError, TypeError) as error:
        raise StepFailed(
            f"the state file {state_file} cannot be read ({type(error).__name__}: {error}), so "
            f"this run does not know which merges are already tested or which mutants already "
            f"have tasks. Nothing was tested.\n"
            f"If the file can be repaired by hand, repair it: it holds last_tested_main_commit, "
            f"a commit hash, and tasks_opened, an object, and may hold "
            f"{MERGES_WITH_MUTANTS_NOT_RUN_STATE_KEY}, an object that gives each merge an "
            f"object holding merged_at_unix_seconds and mutants_not_run_count, both whole "
            f"numbers, and surviving_mutant_keys_already_handled, a list, and may hold "
            f"{ERRORED_MUTANT_KEYS_ALREADY_REPORTED_STATE_KEY}, a list.\n"
            f"Otherwise delete it: the next run then starts from origin/main, and merges since "
            f"the last good run go untested.") from error
    return state


def mutant_key(mutant):
    return hashlib.sha256(json.dumps(
        [mutant["module_path"], mutant["operator"], mutant["diff"]]).encode()).hexdigest()


def task_list_owner(author, task_lists_directory, agent_seats_directory):
    """(agent-seat whose list gets the task, why, when not the author)."""
    if (task_lists_directory / f"nedschorus-{author}-tasks").is_dir() \
            and (agent_seats_directory / author).is_dir():
        return author, None
    return (SURVIVOR_TASK_AGENT_SEAT_WHEN_LINE_AUTHOR_IS_RETIRED_OR_UNKNOWN,
            f"its author, {author}, has no task list or no checkout on ned-box")


def mutant_diff_file_path(log_store_root, key):
    return (Path(log_store_root) / RECORDS_DIRECTORY_NAME
            / SURVIVING_MUTANT_DIFFS_DIRECTORY_NAME / f"{key}.diff")


def task_file_read(task_file):
    """The task as a dict, or None when the file is not a JSON object. Raises OSError."""
    try:
        task = json.loads(task_file.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    return task if isinstance(task, dict) else None


def task_names_mutant(task, key):
    return task is not None and f"{key}.diff" in str(task.get("description", ""))


def task_on_list_open_for_line(list_directory, place):
    """(id, task) of a task on the list, not marked completed, whose subject names the
    file:line `place`, or None. Raises OSError."""
    # The trailing colon keeps scripts/a.py:74 from matching a task for scripts/a.py:745; the
    # optional "s" matches the subject of a task opened for a single mutant.
    subject = re.compile(rf"Surviving mutants? in {re.escape(place)}:")
    if not list_directory.is_dir():
        return None
    for path in sorted(list_directory.iterdir(), key=lambda path: path.name):
        if not TASK_FILE_NAME_PATTERN.fullmatch(path.name):
            continue
        task = task_file_read(path)
        if task is not None and task.get("status") != "completed" \
                and subject.match(str(task.get("subject", ""))):
            return int(path.stem), task
    return None


def task_ids_on_list_open_naming_mutant(list_directory, key):
    """Ids of the tasks on the list, not marked completed, whose description names the
    mutant's diff file. Raises OSError."""
    if not list_directory.is_dir():
        return []
    ids = []
    for path in sorted(list_directory.iterdir(), key=lambda path: path.name):
        if not TASK_FILE_NAME_PATTERN.fullmatch(path.name):
            continue
        task = task_file_read(path)
        if task_names_mutant(task, key) and task.get("status") != "completed":
            ids.append(int(path.stem))
    return ids


def lost_tasks_reported(state, arguments, record):
    """Drop from the state in memory each task that is completed or no longer holds its mutant,
    and re-point a mutant to the one other open task on its owner's list that names it. An open
    task whose description no longer names its mutant keeps the mutant while no other open task
    names it.

    Return one line per task whose file is gone or is not a task and that has no single open
    task on the list naming the mutant, and per task, open or completed, whose mutant more than
    one other open task names; the caller writes the state. Raises OSError when another task
    file on the list cannot be read."""
    lost = []
    for key, given in list(state["tasks_opened"].items()):
        list_directory = arguments.task_lists_directory / f"nedschorus-{given['agent_seat']}-tasks"
        task_file = list_directory / f"{given['task_id']}.json"
        completed = False
        open_task = False
        try:
            task = task_file_read(task_file)
        except OSError as error:
            why = f"the task file cannot be read ({type(error).__name__}: {error})"
        else:
            completed = task is not None and task.get("status") == "completed"
            open_task = task is not None and not completed
            if open_task and task_names_mutant(task, key):
                continue
            why = ("it is marked completed" if completed
                   else "its description no longer names the mutant's diff file")
        # A task fold moves mutants into another task and marks the task they left completed;
        # the handoff prune later deletes that task, so a run may find it either way.
        naming = task_ids_on_list_open_naming_mutant(list_directory, key)
        if completed and not naming:
            del state["tasks_opened"][key]
            continue
        if len(naming) == 1:
            record.append(f"TASK MOVED: the surviving mutant "
                          f"{mutant_diff_file_path(arguments.log_store_root, key)} is now held by "
                          f"task #{naming[0]} on {given['agent_seat']}'s task list, not task "
                          f"#{given['task_id']} ({why})")
            state["tasks_opened"][key] = dict(given, task_id=naming[0])
            continue
        if open_task and not naming:
            # The state, not the description, records which task holds the mutant: agents
            # rewrite descriptions, and the recheck lists the state's mutants in it again.
            continue
        lost.append(f"task #{given['task_id']} on {given['agent_seat']}'s task list "
                    f"({task_file}) no longer holds the surviving mutant "
                    f"{mutant_diff_file_path(arguments.log_store_root, key)}: {why}")
        record.append(f"TASK LOST: {lost[-1]}")
        del state["tasks_opened"][key]
    return lost


def record_write(record_path, record):
    """Raises OSError."""
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text("\n".join(record) + "\n", encoding="utf-8")


def survivor_task_recorded_mutant_killed_check_command_line(diff_files):
    return (f"python3 scripts/{MUTATION_TESTING_PROGRAM.name} {RECORDED_MUTANT_KILLED_CHECK_FLAG} "
            + " ".join(shlex.quote(str(diff_file)) for diff_file in diff_files))


def survivor_task_subject(place, count):
    return (f"Surviving mutants in {place}: {count}; add a test that kills them, or record why no "
            f"test can")


def survivor_task_description(opening, diffs_and_diff_files, record_citation):
    """The description of a task for the surviving mutants of one line: `opening`, then each
    (diff, diff file), in the order of their diff files, then this task's command and what to
    do."""
    shown = sorted(diffs_and_diff_files, key=lambda pair: str(pair[1]))
    count = len(shown)
    mutants = "\n\n".join(f"Mutant {number} of {count}, in {diff_file}:\n{diff.rstrip()}"
                          for number, (diff, diff_file) in enumerate(shown, start=1))
    return (
        f"{opening} A surviving mutant means the code can be changed this way while every suite "
        f"that reads the file still passes, so a defect there would go unnoticed. One test often "
        f"kills every mutant of a line.\n\n"
        f"{mutants}\n\n"
        f"This task's command: {survivor_task_recorded_mutant_killed_check_command_line(diff_file for _, diff_file in shown)}\n"
        f"If a test can tell a mutant from the code: write that test, run this task's command on "
        f"your branch, and open a pull request with the test, putting the command's output in its "
        f"description.\n"
        f"Run the command on ned-box at the root of your checkout with the test committed.\n"
        f"If no test can kill a mutant, because it behaves exactly as the code does: in a new "
        f"pull request, end the line with a comment that starts `# pragma: no mutate` and goes "
        f"on to say why no test can kill its mutants, such as `# pragma: no mutate, both "
        f"branches return the same value`; every mutation pass skips a line whose comment "
        f"says `pragma: no mutate`.\n"
        f"The latest record of the scheduled full mutation pass for this task: {record_citation}\n"
        f"{SURVIVOR_TASK_DESCRIPTION_LAST_LINE_LEAVE_TASK_OPEN_FOR_NIGHTLY_RECHECK}")


def survivor_task_is_current(description, diff_files):
    """True when the description gives the command for exactly these diff files and ends with
    the line that says to leave the task open."""
    return (f"This task's command: {survivor_task_recorded_mutant_killed_check_command_line(sorted(diff_files, key=str))}\n"
            in description and description.endswith(
                SURVIVOR_TASK_DESCRIPTION_LAST_LINE_LEAVE_TASK_OPEN_FOR_NIGHTLY_RECHECK))


def task_file_rewrite(task_file, task):
    """Replace the task file with `task`. Raises OSError."""
    partial = task_file.with_name(f".{task_file.name}.partial")
    partial.write_text(json.dumps(task, indent=2), encoding="utf-8")
    os.replace(partial, task_file)


def program_run_with_limit(command, timeout_seconds):
    """Return (exit code or None when it ran past the limit, stdout, stderr)."""
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               errors="replace")
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
        return process.returncode, stdout, stderr
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            stdout, stderr = process.communicate(
                timeout=SECONDS_FOR_MUTATION_TESTING_PROGRAM_TO_CLEAN_UP_AFTER_SIGTERM)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
        return None, stdout, stderr


def mutation_testing_program_command_line_options_for_one_merge(
        arguments, merge, parent, workers, sessions_directory, which_mutants_run_options):
    """The mutation testing program's options for one merge, shared by this run and the hand
    run a task gives, so the hand run resumes the same kept sessions."""
    return ["--full-mutation-pass", "--checkout", str(arguments.clone), "--head", merge,
            "--base", parent, "--cosmic-ray-venv", str(arguments.cosmic_ray_venv),
            "--parallel-mutant-workers", str(workers),
            "--cosmic-ray-sessions-directory-kept-to-resume", str(sessions_directory),
            *which_mutants_run_options]


FIRST_PASS_WHICH_MUTANTS_RUN_OPTIONS = [
    mutation_testing.MUTANTS_RUN_AT_MOST_SHARED_EVENLY_AMONG_CHANGED_FILES_FLAG,
    str(FIRST_PASS_MUTANTS_RUN_PER_MERGE_AT_MOST)]


def run_mutation_testing(arguments, merge, parent, json_file, workers, sessions_directory,
                         which_mutants_run_options, limit_seconds):
    """Return (exit code or None when it ran past the limit, stdout, stderr)."""
    return program_run_with_limit(
        [sys.executable, arguments.mutation_testing_program,
         *mutation_testing_program_command_line_options_for_one_merge(
             arguments, merge, parent, workers, sessions_directory, which_mutants_run_options),
         "--survived-and-errored-mutants-json-file", str(json_file)],
        limit_seconds)


def mutant_worker_count_for_free_cores(cores, load):
    """The cores less the load average, at least 1 and at most the cores."""
    return max(1, min(cores, int(cores - load)))


def sessions_directory_of_merge(arguments, merge):
    return (arguments.state_directory / COSMIC_RAY_SESSIONS_KEPT_FOR_UNFINISHED_MERGES_DIRECTORY_NAME
            / merge)


def count_of_mutants_judged_in_kept_cosmic_ray_sessions(directory):
    """Mutants with a result, other than those cosmic-ray's filters skipped, in the sessions the
    mutation testing program kept in `directory`; 0 when there are none. Raises StepFailed when
    a session cannot be read."""
    count = 0
    for session in sorted(directory.glob("*.sqlite")) if directory.is_dir() else ():
        try:
            # Not read-only: a run killed while writing a result leaves a hot journal, which
            # only a connection that can write rolls back.
            connection = sqlite3.connect(session)
            try:
                count += connection.execute(COSMIC_RAY_SESSION_JUDGED_MUTANTS_QUERY).fetchone()[0]
            finally:
                connection.close()
        except sqlite3.Error as error:
            raise StepFailed(
                f"the kept cosmic-ray session {session} cannot be read "
                f"({type(error).__name__}: {error}), so this run cannot tell how far its merge "
                f"got.\n"
                f"Delete the session file {session} on ned-box, and no other file: the next run "
                f"mutation-tests again, from its first mutant, the source file whose mutants "
                f"that session held. Then run this program again on ned-box: {RUN_BY_HAND}") \
                from error
    return count


def mutation_testing_hand_run_command(arguments, merge, parent, workers, sessions_directory,
                                      which_mutants_run_options):
    """The command that runs the mutation testing program on one merge as this run does,
    resuming its kept sessions with as many workers, outliving the shell it is typed in, with
    its output in the log-store. It holds this job's lock while it runs, because it shares the
    kept sessions with the nightly run: it waits while a run holds the lock, and a nightly run
    that starts during it exits EXIT_ANOTHER_RUN_HOLDS_THE_LOCK."""
    log = (Path(arguments.log_store_root) / HAND_RUNS_DIRECTORY_NAME
           / f"merge-{merge[:8]}-hand-run.log")
    return (f"systemd-run --user --unit=mutation-hand-run-{merge[:8]} --collect "
            f"-p StandardOutput=append:{log} -p StandardError=append:{log} "
            f"/usr/bin/flock --verbose "
            f"{shlex.quote(str(arguments.state_directory / LOCK_FILE_NAME))} "
            f"/usr/bin/python3 {shlex.quote(str(arguments.mutation_testing_program))} "
            + shlex.join(mutation_testing_program_command_line_options_for_one_merge(
                arguments, merge, parent, workers, sessions_directory,
                which_mutants_run_options)))


def job_failure_task_opened_unless_open(subject, description, arguments,
                                        open_task_description_rewritten=False):
    """Open a task with this subject on JOB_FAILURE_TASK_AGENT_SEAT's task list, unless a task
    there not marked completed has the same subject; with open_task_description_rewritten,
    that open task's description is replaced by this one. Return (its id, True when opened
    now). Raises OSError."""
    list_directory = (arguments.task_lists_directory
                      / f"nedschorus-{JOB_FAILURE_TASK_AGENT_SEAT}-tasks")
    if list_directory.is_dir():
        for path in sorted(list_directory.iterdir(), key=lambda path: path.name):
            if not TASK_FILE_NAME_PATTERN.fullmatch(path.name):
                continue
            task = task_file_read(path)
            if task is not None and task.get("status") != "completed" \
                    and task.get("subject") == subject:
                if open_task_description_rewritten and task.get("description") != description:
                    task_file_rewrite(path, {**task, "description": description})
                return int(path.stem), False
    return agent_seat_task_list_new_pending_task_write(list_directory, subject,
                                                       description), True


def last_line_said(stdout, stderr):
    """The mutation testing program's last line, on standard error when it wrote any there,
    leaving out the line that only names where it kept the suite runner's logs."""
    def said(text):
        return [line for line in text.strip().splitlines()
                if not line.startswith(mutation_testing.TEST_SUITE_RUNNER_LOGS_KEPT_LINE_PREFIX)]
    return (said(stderr) or said(stdout) or ["nothing"])[-1]


def all_said_on_stderr_or_last_line_of_stdout_indented(stdout, stderr):
    """Every line of standard error, or, when it is empty, the last line of standard output,
    each indented under the sentence that introduces it. Not the last line alone: a refusal's
    first line says what failed, and the error it quotes, such as git's, can put the cause
    before its last line."""
    said = stderr.strip() or last_line_said(stdout, "")
    return "\n".join(f"    {line}" for line in said.splitlines())


def survivor_tasks_rechecked(state, state_file, arguments, main_commit, record, record_citation,
                             scratch):
    """Run the recorded mutant killed check on main for each task the state names; drop each
    mutant killed or no longer existing from the task and the state, and complete a task none
    of whose mutants survive. Return one line per task the check gave no verdicts for. Raises
    StepFailed when a task, a diff file or the state cannot be read or written."""
    tasks = {}
    for key, given in state["tasks_opened"].items():
        tasks.setdefault((given["agent_seat"], given["task_id"]), []).append(key)
    limit = arguments.survivor_task_recorded_mutant_killed_check_timeout_seconds
    not_rechecked = []
    for (agent_seat, task_id), keys in tasks.items():
        named = f"task #{task_id} on {agent_seat}'s task list"
        task_file = (arguments.task_lists_directory / f"nedschorus-{agent_seat}-tasks"
                     / f"{task_id}.json")
        diff_files = {key: mutant_diff_file_path(arguments.log_store_root, key) for key in keys}
        verdicts_file = scratch / f"{agent_seat}-{task_id}-verdicts.json"
        exit_code, stdout, stderr = program_run_with_limit(
            [sys.executable, arguments.mutation_testing_program, RECORDED_MUTANT_KILLED_CHECK_FLAG,
             *map(str, diff_files.values()), "--head", main_commit,
             "--checkout", str(arguments.clone),
             "--recorded-mutant-killed-check-verdicts-json-file-to-write", str(verdicts_file)],
            limit)
        try:
            verdicts = json.loads(verdicts_file.read_text(encoding="utf-8"))["verdicts"]
            verdict_of = {key: verdicts[str(diff_file)]["verdict"]
                          for key, diff_file in diff_files.items()}
        except (OSError, ValueError, KeyError, TypeError) as error:
            how = (f"ran past the limit of {limit:g} s" if exit_code is None
                   else f"exited {exit_code}")
            not_rechecked.append(
                f"{named} ({task_file}): the recorded mutant killed check {how} without "
                f"verdicts ({type(error).__name__}: {error}); it printed:\n"
                f"{all_said_on_stderr_or_last_line_of_stdout_indented(stdout, stderr)}")
            record.append(f"NOT RECHECKED: {not_rechecked[-1]}")
            continue
        surviving = [key for key in keys if verdict_of[key] not in ("killed", "no longer exists")]
        counted = ", ".join(f"{list(verdict_of.values()).count(verdict)} {verdict}" for verdict
                            in ("killed", "no longer exists", "survived", "could not be judged"))
        try:
            outcome = survivor_task_rechecked_write(
                task_file, [diff_files[key] for key in keys],
                [diff_files[key] for key in surviving], main_commit, record_citation)
            for key in keys:
                if key not in surviving:
                    del state["tasks_opened"][key]
            write_state(state_file, state)
        except OSError as error:
            raise StepFailed(
                f"{named} ({task_file}) was rechecked on main ({counted}), but a file could "
                f"not be read or written ({type(error).__name__}: {error}). No merge was tested.\n"
                f"Fix what the error names, then run this program again on ned-box: "
                f"{RUN_BY_HAND}") from error
        record.append(f"RECHECKED {named}: {counted}; {outcome}")
    return not_rechecked


def survivor_task_rechecked_write(task_file, diff_files, surviving_diff_files, main_commit,
                                  record_citation):
    """Complete the task when no mutant survives, rewrite it to list only the surviving ones when
    it lists more or is not current, and say which. Raises OSError."""
    task = task_file_read(task_file)
    if task is None:
        return "left as it was: its file is not a task"
    description = str(task.get("description", ""))
    if not surviving_diff_files:
        task_file_rewrite(task_file, dict(task, status="completed", description=(
            f"{description}\n\nCompleted by the scheduled full mutation pass: on main at "
            f"{main_commit[:12]}, every mutant this task listed is killed or no longer exists. "
            f"Its record: {record_citation}")))
        return "completed"
    if len(surviving_diff_files) == len(diff_files) and survivor_task_is_current(description,
                                                                                 diff_files):
        return "unchanged"
    place_named = SURVIVOR_TASK_SUBJECT_PLACE.match(str(task.get("subject", "")))
    place = place_named[1] if place_named else "the line the diffs below show"
    updated = dict(task, description=survivor_task_description(
        f"The scheduled full mutation pass found mutants that no test kills in {place}; on main "
        f"at {main_commit[:12]}, {len(surviving_diff_files)} of them still survive.",
        [(diff_file.read_text(encoding="utf-8"), diff_file)
         for diff_file in surviving_diff_files], record_citation))
    if place_named:
        updated["subject"] = survivor_task_subject(place, len(surviving_diff_files))
    task_file_rewrite(task_file, updated)
    return "rewritten to list only the surviving mutants"


def untestable_merge_job_failure_task_subject(merge):
    return (f"Nightly full mutation pass skipped merge {merge[:12]}, untestable: a suite fails "
            f"on its unchanged code")


def untestable_merge_recorded(arguments, state, state_file, merge, parent, merge_subject,
                              exit_code, stderr, record, record_citation, in_second_pass):
    """Open the job failure task for a merge the mutation testing program found a suite failing
    on with no mutant applied, then record the merge in the state as untestable and, in the
    first pass, as the last tested commit, so the run goes on to the next merge; in the second
    pass, the merge leaves the merges with mutants not run. Raises StepFailed when the task
    cannot be opened, leaving the state as it was, so the next run tries the merge again."""
    suites = [line[len(mutation_testing.SUITE_FAILS_ON_UNMUTATED_HEAD_LINE_PREFIX):].strip()
              for line in stderr.splitlines()
              if line.startswith(mutation_testing.SUITE_FAILS_ON_UNMUTATED_HEAD_LINE_PREFIX)]
    named = ", ".join(suites)
    subject = untestable_merge_job_failure_task_subject(merge)
    description = (
        f"The scheduled full mutation pass on ned-box could not mutation-test merge {merge} "
        f"({merge_subject}): on that merge's unchanged code, the suite(s) {named} fail, so the "
        f"mutation testing program judged no mutant and exited {exit_code}. The run recorded "
        f"the merge as untestable under {UNTESTABLE_MERGES_STATE_KEY} in {state_file}, went on "
        f"to the next merge, and does not try this merge again. The program printed:\n"
        f"{all_said_on_stderr_or_last_line_of_stdout_indented('', stderr)}\n"
        f"Its record: {record_citation}\n"
        f"Mutation-test this merge's changed lines at a later main commit where that suite "
        f"passes: run on ned-box python3 {arguments.mutation_testing_program} "
        f"--full-mutation-pass --checkout {shlex.quote(str(arguments.clone))} --head <that "
        f"commit> --base {parent} --cosmic-ray-venv "
        f"{shlex.quote(str(arguments.cosmic_ray_venv))}, and give each surviving mutant in a "
        f"file that `git diff --name-only {parent} {merge} -- '*.py'` lists a task on the task "
        f"list of the agent-seat that wrote its line. That range also holds the merges after "
        f"this one, which the nightly run tests itself.\n"
        f"Mark this task completed once those lines are mutation-tested and their survivors "
        f"have tasks.")
    try:
        task_id, opened = job_failure_task_opened_unless_open(subject, description, arguments)
    except OSError as error:
        raise StepFailed(
            f"merge {merge[:12]} ({merge_subject}): a suite fails on its unchanged code ({named}), "
            f"so it is untestable, but its job failure task could not be opened on "
            f"{JOB_FAILURE_TASK_AGENT_SEAT}'s task list ({type(error).__name__}: {error}), so "
            f"the merge is not recorded as untestable and no later merge is tested. The next "
            f"run tries this merge again.\n"
            f"Fix what the error names, such as a task list directory that does not exist, "
            f"then run this program again on ned-box: {RUN_BY_HAND}") from error
    record.append(f"UNTESTABLE: merge {merge[:12]} ({merge_subject}): on its unchanged code the "
                  f"suite(s) {named} fail, so no mutant can be judged; recorded as untestable, "
                  f"and the run goes on to the next merge")
    record.append(f"JOB FAILURE TASK: {'opened' if opened else 'already open, so none opened:'}"
                  f" task #{task_id} on {JOB_FAILURE_TASK_AGENT_SEAT}'s task list, {subject}")
    state.setdefault(UNTESTABLE_MERGES_STATE_KEY, {})[merge] = suites
    if in_second_pass:
        del state[MERGES_WITH_MUTANTS_NOT_RUN_STATE_KEY][merge]
    else:
        state["last_tested_main_commit"] = merge
    write_state(state_file, state)


def errored_mutant_key(mutant):
    """The SHA-256 of a JSON list of the mutant's file path, line, cosmic-ray operator and diff.
    Unlike mutant_key(), it holds the line, because an ERRORED mutant's diff can be empty."""
    return hashlib.sha256(json.dumps(
        [mutant["module_path"], mutant["line"], mutant["operator"], mutant["diff"]]
    ).encode()).hexdigest()


def errored_mutant_named(mutant):
    return f"{mutant['module_path']}:{mutant['line']} {mutant['operator']}"


def errored_mutant_reason(mutant):
    """The reason the mutation testing program gives from the mutant's output; it gives none
    when cosmic-ray itself recorded the mutant as not judgeable."""
    return mutant["reason"] or "cosmic-ray could not judge it"


def errored_mutants_job_failure_task_subject(merge):
    return (f"Nightly full mutation pass: mutants of merge {merge[:12]} ended ERRORED, judged "
            f"neither killed nor survived")


def errored_mutants_job_failure_task_opened(arguments, merge, merge_subject, errored, record,
                                            record_citation):
    """Open the one job failure task of a merge with ERRORED mutants, naming each with its
    reason, or rewrite the open one's description to name every ERRORED mutant this run
    reported. Raises StepFailed when the task cannot be opened or rewritten, before the merge
    is recorded as tested, so the next run tries the merge again."""
    subject = errored_mutants_job_failure_task_subject(merge)
    named = "\n".join(
        f"- {errored_mutant_named(mutant)}, reason: {errored_mutant_reason(mutant)}"
        + "".join(f"\n      {line}" for line in mutant["diff"].splitlines())
        for mutant in errored)
    description = (
        f"The scheduled full mutation pass on ned-box ran the mutation testing program on merge "
        f"{merge} ({merge_subject}), and {len(errored)} of its mutants ended ERRORED: their "
        f"suites gave no verdict, so each is neither killed nor survived. The run recorded the "
        f"merge as tested anyway, and does not run these mutants again. Each mutant, as file, "
        f"line and cosmic-ray operator, with the reason the mutation testing program gives "
        f"from its output and its diff when it has one:\n\n"
        f"{named}\n\n"
        f"Its record: {record_citation}\n"
        f"A reason's advice to run the mutation testing program again is written for a hand "
        f"run of it; the nightly run follows none.\n"
        f"For each mutant, judge from its reason where the cause is. A cause in this project, "
        f"such as a mutant that makes a suite hang or a suite that cannot start: fix it in a "
        f"pull request. A cause outside the code that has passed, such as a full disk or a "
        f"busy machine: nothing to fix.\n"
        f"Mark this task completed once every mutant listed is judged.")
    try:
        task_id, opened = job_failure_task_opened_unless_open(subject, description, arguments,
                                                              True)
    except OSError as error:
        raise StepFailed(
            f"merge {merge[:12]} ({merge_subject}): {len(errored)} of its mutants ended "
            f"ERRORED, but their job failure task could not be opened or rewritten on "
            f"{JOB_FAILURE_TASK_AGENT_SEAT}'s task list ({type(error).__name__}: {error}), so "
            f"the merge is not recorded as tested and no later merge is tested. The next run "
            f"tries this merge again, and gives no surviving mutant a second task.\n"
            f"Fix what the error names, such as a task list directory that does not exist, "
            f"then run this program again on ned-box: {RUN_BY_HAND}") from error
    for mutant in errored:
        record.append(f"  ERRORED {errored_mutant_named(mutant)} "
                      f"({errored_mutant_reason(mutant)}): named in task #{task_id}")
    how = ("opened" if opened else "already open, so none opened, and its description now names "
           "the ERRORED mutants this run reported:")
    record.append(f"JOB FAILURE TASK: {how} task #{task_id} on {JOB_FAILURE_TASK_AGENT_SEAT}'s "
                  f"task list, {subject}")


def summary_line(stdout):
    lines = [line for line in stdout.splitlines() if line.startswith("SUMMARY:")]
    return lines[-1] if lines else "no SUMMARY line"


def test_one_merge(arguments, state, state_file, merge, record, record_citation, scratch,
                   second_pass_no_mutant_started_after_unix_time=None,
                   second_pass_limit_seconds=None):
    """Mutation-test one merge and give its survivors tasks: in its first pass, or, given
    second_pass_no_mutant_started_after_unix_time and second_pass_limit_seconds, in its
    second. Return (whether the mutation testing program ran past the limit, so the merge is
    carried on to the next run, and, when it then judged no new mutant in the first pass, the
    job failure task to open, as (subject, description))."""
    in_second_pass = second_pass_no_mutant_started_after_unix_time is not None
    which_mutants_run_options = FIRST_PASS_WHICH_MUTANTS_RUN_OPTIONS
    limit_seconds = arguments.merge_timeout_seconds
    not_run_before = {}
    if in_second_pass:
        which_mutants_run_options = [
            mutation_testing.NO_MUTANT_STARTED_AFTER_UNIX_TIME_FLAG,
            repr(second_pass_no_mutant_started_after_unix_time)]
        limit_seconds = second_pass_limit_seconds
        not_run_before = state[MERGES_WITH_MUTANTS_NOT_RUN_STATE_KEY][merge]
    parent = git_or_raise(arguments.clone, "rev-parse", "--verify", f"{merge}^1^{{commit}}")
    merged_at, _, merge_subject = git_or_raise(arguments.clone, "log", "-1", "--format=%ct %s",
                                               merge).partition(" ")
    json_file = scratch / f"{merge}.json"
    sessions_directory = sessions_directory_of_merge(arguments, merge)
    judged_before = count_of_mutants_judged_in_kept_cosmic_ray_sessions(sessions_directory)
    cores, load = os.cpu_count() or 1, os.getloadavg()[0]
    workers = mutant_worker_count_for_free_cores(cores, load)
    record.append(f"merge {merge[:12]}{', second pass' if in_second_pass else ''}: {workers} "
                  f"mutant worker(s), from {cores} cores and a "
                  f"load average over the last minute of {load:.1f}; {judged_before} mutant(s) "
                  f"already judged in its kept sessions")
    exit_code, stdout, stderr = run_mutation_testing(
        arguments, merge, parent, json_file, workers, sessions_directory,
        which_mutants_run_options, limit_seconds)
    # A hand run of a second pass merge takes no stop time, so it runs every mutant not run.
    command_shown = mutation_testing_hand_run_command(
        arguments, merge, parent, workers, sessions_directory,
        [] if in_second_pass else which_mutants_run_options)
    said = last_line_said(stdout, stderr)
    if exit_code is None:
        judged = count_of_mutants_judged_in_kept_cosmic_ray_sessions(sessions_directory)
        record.append(f"CARRIED ON: merge {merge[:12]} ({merge_subject}) ran past the limit of "
                      f"{limit_seconds:g} s with {judged} mutant(s) judged, "
                      f"{judged - judged_before} of them in this run; "
                      + ("a later second pass goes on with its mutants not yet run."
                         if in_second_pass else
                         "the next run goes on from its first mutant not yet run, and the "
                         "merges after it wait.") + f" Its last line: {said}")
        if judged > judged_before or in_second_pass:
            return True, None
        subject = (f"Nightly full mutation pass judged no new mutant of merge {merge[:12]} in a "
                   f"night, before the per-merge time limit")
        return True, (subject, (
                f"The scheduled full mutation pass on ned-box ran the mutation testing program "
                f"on merge {merge} ({merge_subject}) until its limit of "
                f"{arguments.merge_timeout_seconds:g} s and judged no mutant beyond the "
                f"{judged_before} its kept cosmic-ray sessions in {sessions_directory} already "
                f"held. Carried on night after night, the merge would never finish, and every "
                f"merge after it waits. The program's last line: {said}\n"
                f"Its record: {record_citation}\n"
                f"Find what its mutants wait on: run the program on this merge by hand on "
                f"ned-box, {command_shown}, and read its output in that log; a suite the "
                f"runner's admission keeps waiting, or one that runs out of time, is named "
                f"there.\n"
                f"Fix the cause in a pull request. The nightly run carries the merge on until "
                f"then; mark this task completed once a run records the merge as tested or "
                f"carries it on with new mutants judged."))
    if exit_code == mutation_testing.EXIT_SUITE_FAILS_ON_UNMUTATED_HEAD:  # pragma: no mutate, `is` compares this small int as `==` does; the test's exit-143 case fails `>=`
        untestable_merge_recorded(arguments, state, state_file, merge, parent, merge_subject,
                                  exit_code, stderr, record, record_citation, in_second_pass)
        return False, None
    if exit_code not in MUTATION_TESTING_EXITS_WITH_A_VERDICT:
        raise StepFailed(
            f"merge {merge[:12]} ({merge_subject}): the mutation testing program exited "
            f"{exit_code} without saying whether each mutant was killed. The next run tries "
            f"this merge again. It printed:\n"
            f"{all_said_on_stderr_or_last_line_of_stdout_indented(stdout, stderr)}\n"
            f"If it fails the same way again, run this command by hand on ned-box, do what it "
            f"prints in its log, and fix the cause: {command_shown}")
    try:
        result = json.loads(json_file.read_text(encoding="utf-8"))
        survived, errored = result["survived"], result["errored"]
        files_with_no_suite = result["files_with_no_suite"]
        mutants_not_run_count = result["mutants_not_run_count"]
    except (OSError, ValueError, KeyError) as error:
        raise StepFailed(
            f"merge {merge[:12]} ({merge_subject}): the mutation testing program exited "
            f"{exit_code} but its JSON file {json_file} cannot be read "
            f"({type(error).__name__}: {error}), so its survivors are not known. The next run "
            f"tries this merge again.\n"
            f"If the next run fails the same way, {arguments.mutation_testing_program} writes "
            f"that file in a form scripts/{PROGRAM}.py does not read: make the two agree on "
            f"what the docstring of {arguments.mutation_testing_program} says under "
            f"--survived-and-errored-mutants-json-file, by changing test_one_merge() in "
            f"scripts/{PROGRAM}.py or the code that writes the file.") from error
    record.append(f"merge {merge[:12]} {merge_subject}: {summary_line(stdout)}")
    # The program reports the survivors of every run of the merge; an earlier run's may since
    # have left tasks_opened, killed, and must get no second task.
    already_handled = set(not_run_before.get("surviving_mutant_keys_already_handled", ()))
    survived_by_line = {}
    for mutant in survived:
        if mutant_key(mutant) not in already_handled:
            survived_by_line.setdefault((mutant["module_path"], mutant["line"]),
                                        []).append(mutant)
    for (module_path, line), mutants in survived_by_line.items():
        place = f"{module_path}:{line}"
        not_given = []
        for mutant in mutants:
            given = state["tasks_opened"].get(mutant_key(mutant))
            if given is None:
                not_given.append(mutant)
            else:
                record.append(f"  SURVIVED {place} {mutant['operator']}: already given task "
                              f"#{given['task_id']} on {given['agent_seat']}'s task list")
        if not not_given:
            continue
        blame = git_or_raise(arguments.clone, "blame", "--porcelain", "-L", f"{line},{line}",
                             merge, "--", module_path)
        author = next((blame_line[len("author "):] for blame_line in blame.splitlines()
                       if blame_line.startswith("author ")), "")
        owner, owner_reason = task_list_owner(author, arguments.task_lists_directory,
                                              arguments.agent_seats_directory)
        list_directory = arguments.task_lists_directory / f"nedschorus-{owner}-tasks"
        mutants_and_diff_files = [
            (mutant, mutant_diff_file_path(arguments.log_store_root, mutant_key(mutant)))
            for mutant in not_given]
        try:
            found = task_on_list_open_for_line(list_directory, place)
            # A mutant whose diff file the open task already names was added to it by a run
            # stopped before it wrote the state.
            to_add = [(mutant, diff_file) for mutant, diff_file in mutants_and_diff_files
                      if found is None or not task_names_mutant(found[1], mutant_key(mutant))]
            for mutant, diff_file in to_add:
                diff_file.parent.mkdir(parents=True, exist_ok=True)
                diff_file.write_text(mutant["diff"], encoding="utf-8")
            if found is None:
                operators = {}
                for mutant in not_given:
                    operators[mutant["operator"]] = operators.get(mutant["operator"], 0) + 1
                whose = ("You wrote the line." if owner_reason is None
                         else f"Agent-seat {author} wrote the line; this task is on your list "
                              f"because {owner_reason}.")
                description = survivor_task_description(
                    f"The scheduled full mutation pass found {len(not_given)} mutant(s) that no "
                    f"test kills in {place} (cosmic-ray operators, with how many mutants each: "
                    + ", ".join(f"{operator} ({number})" for operator, number in operators.items())
                    + f"), a line merged into main in {merge[:12]} ({merge_subject}). {whose}",
                    [(mutant["diff"], diff_file) for mutant, diff_file in mutants_and_diff_files],
                    record_citation)
                task_id = agent_seat_task_list_new_pending_task_write(
                    list_directory, survivor_task_subject(place, len(not_given)), description)
            elif to_add:
                found_id, found_task = found
                listed = {mutant_diff_file_path(arguments.log_store_root, key): None
                          for key, given in state["tasks_opened"].items()
                          if (given["agent_seat"], given["task_id"]) == (owner, found_id)}
                listed.update((diff_file, mutant["diff"])
                              for mutant, diff_file in mutants_and_diff_files)
                description = survivor_task_description(
                    f"The scheduled full mutation pass found mutants that no test kills in "
                    f"{place}; merge {merge[:12]} ({merge_subject}) added {len(to_add)} of them "
                    f"to this task.",
                    [(diff if diff is not None else diff_file.read_text(encoding="utf-8"),
                      diff_file) for diff_file, diff in listed.items()], record_citation)
                task_file_rewrite(list_directory / f"{found_id}.json", dict(
                    found_task, subject=survivor_task_subject(place, len(listed)),
                    description=description))
        except OSError as error:
            raise StepFailed(
                f"merge {merge[:12]}: no task could be opened on {owner}'s task list, or "
                f"rewritten there, for the {len(not_given)} surviving mutant(s) in {place} "
                f"({type(error).__name__}: {error}). No later merge is tested until this one "
                f"is. The next run tries this merge again, and gives no line of it a second "
                f"task.\n"
                f"Fix what the error names, such as a task list directory that does not exist "
                f"or a file that cannot be written, then run this program again on ned-box: "
                f"{RUN_BY_HAND}") from error
        if found is None:
            for mutant in not_given:
                state["tasks_opened"][mutant_key(mutant)] = {"agent_seat": owner,
                                                             "task_id": task_id}
                record.append(f"  SURVIVED {place} {mutant['operator']}: task #{task_id} "
                              f"opened on {owner}'s task list")
            write_state(state_file, state)
            continue
        found_id = found[0]
        added_keys = {mutant_key(mutant) for mutant, _ in to_add}
        for mutant in not_given:
            key = mutant_key(mutant)
            state["tasks_opened"][key] = {"agent_seat": owner, "task_id": found_id}
            record.append(f"  SURVIVED {place} {mutant['operator']}: "
                          + (f"added to task #{found_id}, open for this line,"
                             if key in added_keys else f"already given task #{found_id}")
                          + f" on {owner}'s task list")
        write_state(state_file, state)
    errored_already_reported = set(
        not_run_before.get(ERRORED_MUTANT_KEYS_ALREADY_REPORTED_STATE_KEY, ()))
    if any(errored_mutant_key(mutant) not in errored_already_reported for mutant in errored):
        errored_mutants_job_failure_task_opened(arguments, merge, merge_subject, errored, record,
                                                record_citation)
    else:
        for mutant in errored:
            record.append(f"  ERRORED {errored_mutant_named(mutant)} "
                          f"({errored_mutant_reason(mutant)}): an earlier run of this merge "
                          f"already gave it a job failure task")
    for path in files_with_no_suite:
        record.append(f"  NO SUITE {path}: its changed lines were not mutation-tested; no task")
    if mutants_not_run_count:
        not_run = {
            "merged_at_unix_seconds": int(merged_at),
            "mutants_not_run_count": mutants_not_run_count,
            "surviving_mutant_keys_already_handled": sorted(
                already_handled | {mutant_key(mutant) for mutant in survived})}
        errored_reported = errored_already_reported | {errored_mutant_key(mutant)
                                                       for mutant in errored}
        if errored_reported:
            not_run[ERRORED_MUTANT_KEYS_ALREADY_REPORTED_STATE_KEY] = sorted(errored_reported)
        state.setdefault(MERGES_WITH_MUTANTS_NOT_RUN_STATE_KEY, {})[merge] = not_run
    elif in_second_pass:
        del state[MERGES_WITH_MUTANTS_NOT_RUN_STATE_KEY][merge]
    if not in_second_pass:
        state["last_tested_main_commit"] = merge
    write_state(state_file, state)
    return False, None


def unix_time_cron_next_starts_this_program_on_ned_box(scheduled_jobs_file, now):
    """The first time after `now`, in ned-box's local time as cron reads the schedule, at which
    cron starts this program. Raises StepFailed when the scheduled jobs file cannot be read or
    does not give this program a schedule of the form `<minute> <hour> * * *`."""
    try:
        jobs = json.loads(Path(scheduled_jobs_file).read_text(encoding="utf-8"))["jobs"]
        schedule = [job["on"]["ned-box"]["schedule"] for job in jobs
                    if job["name"] == PROGRAM][0]
        minute, hour, *every_day = schedule.split()
        if every_day != ["*", "*", "*"]:
            raise ValueError(f"the schedule {schedule!r} is not `<minute> <hour> * * *`")
        minute, hour = int(minute), int(hour)
    except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError) as error:
        raise StepFailed(
            f"the schedule of {PROGRAM} on ned-box cannot be read from {scheduled_jobs_file} "
            f"({type(error).__name__}: {error}), so the second pass does not know when to "
            f"stop for the next scheduled run, and ran no mutant. The first pass is done.\n"
            f"Give the job named {PROGRAM} in that file, under on, ned-box, a schedule of the "
            f"form `<minute> <hour> * * *`, or, when the job must run on another schedule, "
            f"change unix_time_cron_next_starts_this_program_on_ned_box() in "
            f"scripts/{PROGRAM}.py to read it.") from error
    today = time.localtime(now)
    for day in (today.tm_mday, today.tm_mday + 1):
        # mktime reads a day past the month's end as a day of the next month.
        due = time.mktime((today.tm_year, today.tm_mon, day, hour, minute, 0, 0, 0, -1))
        if due > now:
            break
    return due


def second_pass_mutation_tests_mutants_not_run_newest_merge_first_until_stop_time(
        no_mutant_started_after_unix_time, arguments, state, state_file, record,
        record_citation, scratch, clock=time.time):
    """The second pass. Return whether a merge ran past its limit and is carried on."""
    not_run = state.get(MERGES_WITH_MUTANTS_NOT_RUN_STATE_KEY, {})
    stops = datetime.fromtimestamp(no_mutant_started_after_unix_time, timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    record.append(f"second pass: {len(not_run)} merge(s) have mutants not run; it starts none "
                  f"after {stops}")
    for merge in sorted(not_run, key=lambda merge: (not_run[merge]["merged_at_unix_seconds"],
                                                    merge), reverse=True):
        now = clock()
        if now >= no_mutant_started_after_unix_time:
            record.append(f"second pass stopped for the next scheduled run, before merge "
                          f"{merge[:12]}")
            break
        carried_on, _ = test_one_merge(
            arguments, state, state_file, merge, record, record_citation, scratch,
            no_mutant_started_after_unix_time,
            min(arguments.merge_timeout_seconds,
                no_mutant_started_after_unix_time - now
                + arguments.second_pass_stops_starting_mutants_seconds_before_next_scheduled_run
                / 2))
        if carried_on:
            return True
    return False


def run_record_line_counting_mutants_not_run_and_naming_oldest_merge_with_one(state, now):
    """The record's line counting the mutants not run and naming the oldest merge with one."""
    not_run = state.get(MERGES_WITH_MUTANTS_NOT_RUN_STATE_KEY, {})
    if not not_run:
        return "MUTANTS NOT RUN: 0, in no merge recorded as tested"
    count = sum(each["mutants_not_run_count"] for each in not_run.values())
    oldest = min(not_run, key=lambda merge: (not_run[merge]["merged_at_unix_seconds"], merge))
    merged_at = not_run[oldest]["merged_at_unix_seconds"]
    merged = datetime.fromtimestamp(merged_at, timezone.utc).strftime("%Y-%m-%d %H:%M")
    return (f"MUTANTS NOT RUN: {count}, in {len(not_run)} merge(s) recorded as tested; the "
            f"oldest such merge is {oldest[:12]}, merged {merged} UTC, "
            f"{(now - merged_at) / 86400:.1f} days ago")


def parse_arguments(argv):
    parser = argparse.ArgumentParser(prog=PROGRAM, description=__doc__.split("\n\n")[0])
    parser.add_argument("--clone", type=Path, default=REPOSITORY_ROOT,
                        help="the clone fetched and mutation-tested; default, this file's")
    parser.add_argument("--log-store-root", default=DEFAULT_LOG_STORE_ROOT,
                        help="the log-store's root on ned-box")
    parser.add_argument("--state-directory", type=Path, default=DEFAULT_STATE_DIRECTORY,
                        help="where the state file and the lock are kept")
    parser.add_argument("--task-lists-directory", type=Path,
                        default=DEFAULT_TASK_LISTS_DIRECTORY,
                        help="Claude Code's task list directories")
    parser.add_argument("--agent-seats-directory", type=Path,
                        default=DEFAULT_AGENT_SEATS_DIRECTORY,
                        help="where each agent-seat's checkout is, named for the agent-seat")
    parser.add_argument("--cosmic-ray-venv", type=Path,
                        default=mutation_testing.DEFAULT_COSMIC_RAY_VENV,
                        help="the venv holding cosmic-ray")
    parser.add_argument("--mutation-testing-program", default=str(MUTATION_TESTING_PROGRAM),
                        help="the program run for each merge; default, the one beside this file")
    parser.add_argument("--merge-timeout-seconds", type=float,
                        default=DEFAULT_MERGE_TIMEOUT_SECONDS,
                        help="the limit on mutation-testing one merge")
    parser.add_argument("--survivor-task-recorded-mutant-killed-check-timeout-seconds", type=float,
                        default=DEFAULT_SURVIVOR_TASK_RECORDED_MUTANT_KILLED_CHECK_TIMEOUT_SECONDS,
                        help="the limit on the recorded mutant killed check of one survivor task")
    parser.add_argument("--scheduled-jobs-on-each-machine-json-file", type=Path,
                        default=SCHEDULED_JOBS_ON_EACH_MACHINE_JSON_FILE,
                        help="the file this program's cron schedule on ned-box is read from")
    parser.add_argument(
        "--second-pass-stops-starting-mutants-seconds-before-next-scheduled-run", type=float,
        default=DEFAULT_SECOND_PASS_STOPS_STARTING_MUTANTS_SECONDS_BEFORE_NEXT_SCHEDULED_RUN,
        help="how long before cron next starts this program the second pass starts no "
             "further mutant")
    return parser.parse_args(argv)


def main(argv=None):
    # The job log takes stdout and stderr in one file; block-buffered stdout would land there
    # after stderr lines printed later, below the messages that point "above" at it.
    sys.stdout.reconfigure(line_buffering=True)
    arguments = parse_arguments(argv)
    arguments.clone = arguments.clone.resolve()
    arguments.state_directory.mkdir(parents=True, exist_ok=True)
    lock_handle = take_lock(arguments.state_directory / LOCK_FILE_NAME)
    if lock_handle is None:
        print(f"{PROGRAM}: not run — another run holds "
              f"{arguments.state_directory / LOCK_FILE_NAME}, and two runs would test the same "
              f"merges. Nothing to do: the next scheduled run carries on where that one "
              f"stops.", file=sys.stderr)
        return EXIT_ANOTHER_RUN_HOLDS_THE_LOCK
    try:
        return main_under_lock(arguments)
    finally:
        lock_handle.close()


def main_under_lock(arguments):
    started = datetime.now(timezone.utc)
    started_monotonic = time.monotonic()
    file_name = f"{started.strftime('%Y-%m-%dT%H%M%SZ')}.txt"
    record_path = Path(arguments.log_store_root) / RECORDS_DIRECTORY_NAME / file_name
    record_citation = f"{LOG_STORE_HOST}:{record_path}"
    record = [f"{PROGRAM}: started {started.strftime('%Y-%m-%dT%H:%M:%SZ')}"]
    state_file = arguments.state_directory / STATE_FILE_NAME
    failure = None
    lost_tasks = []
    not_rechecked = []
    job_failure_tasks = []
    untested_merges_and_times = []
    carried_on = False
    state = None
    try:
        git_or_raise(arguments.clone, "fetch", "--quiet", "origin", "main")
        main_commit = git_or_raise(arguments.clone, "rev-parse", "--verify",
                                   "refs/remotes/origin/main^{commit}")
        record.append(f"origin/main: {main_commit}")
        state = read_state(state_file)
        if state is None:
            write_state(state_file, {"last_tested_main_commit": main_commit,
                                     "tasks_opened": {}})
            record.append(f"first run: no state file, so {state_file} now names origin/main; "
                          f"the merges after it are tested from the next run on")
        else:
            last = state["last_tested_main_commit"]
            record.append(f"after: {last}")
            last_is_an_ancestor = not git(arguments.clone, "merge-base", "--is-ancestor", last,
                                          main_commit).returncode
            # Listed before the steps that can fail, so that a failure of one of them still has
            # the merges three days untested reported.
            if last_is_an_ancestor:
                untested_merges_and_times = [
                    (merge, int(merged_at)) for merge, merged_at in (
                        line.split() for line in git_or_raise(
                            arguments.clone, "log", "--first-parent", "--reverse",
                            "--format=%H %ct", f"{last}..{main_commit}").splitlines())]
            tasks_before = dict(state["tasks_opened"])
            lost = lost_tasks_reported(state, arguments, record)
            # A run killed later writes no record, so the lost tasks reach one before the
            # state stops naming them.
            if lost:
                try:
                    record_write(record_path, record)
                except OSError as error:
                    raise StepFailed(
                        f"the record {record_citation} cannot be written "
                        f"({type(error).__name__}: {error}), so the {len(lost)} lost task(s) "
                        f"above are kept in the state, and the next run reports them again. "
                        f"Nothing was tested.\n"
                        f"Fix what the error names, then run this program again on ned-box: "
                        f"{RUN_BY_HAND}") from error
            if state["tasks_opened"] != tasks_before:
                write_state(state_file, state)
            lost_tasks = lost
            with tempfile.TemporaryDirectory(prefix=f"{PROGRAM}-") as scratch:
                not_rechecked = survivor_tasks_rechecked(state, state_file, arguments, main_commit,
                                                         record, record_citation, Path(scratch))
            if not last_is_an_ancestor:
                raise StepFailed(
                    f"the last tested commit {last}, from {state_file}, is not an ancestor of "
                    f"origin/main {main_commit}, so the merges since it cannot be listed.\n"
                    f"Set last_tested_main_commit in that file to the last commit on origin/main "
                    f"already mutation-tested; the next run tests the merges after it. Then run this program again on ned-box: {RUN_BY_HAND}")
            merges = [merge for merge, _ in untested_merges_and_times]
            if merges and not (arguments.cosmic_ray_venv / "bin" / "cosmic-ray").is_file():
                venv = shlex.quote(str(arguments.cosmic_ray_venv))
                raise StepFailed(
                    f"cosmic-ray is not installed in {arguments.cosmic_ray_venv}, so no merge "
                    f"can be mutation-tested.\n"
                    f"Install it on ned-box: python3 -m venv {venv} && {venv}/bin/pip install "
                    f"cosmic-ray=={mutation_testing.COSMIC_RAY_VERSION}, then run this program again on ned-box: {RUN_BY_HAND}")
            sessions_root = (arguments.state_directory
                             / COSMIC_RAY_SESSIONS_KEPT_FOR_UNFINISHED_MERGES_DIRECTORY_NAME)
            for kept in sorted(sessions_root.iterdir()) if sessions_root.is_dir() else ():
                if kept.name not in merges \
                        and kept.name not in state.get(MERGES_WITH_MUTANTS_NOT_RUN_STATE_KEY, {}):
                    shutil.rmtree(kept)
            with tempfile.TemporaryDirectory(prefix=f"{PROGRAM}-") as scratch:
                for merge in merges:
                    carried_on, no_progress_task = test_one_merge(
                        arguments, state, state_file, merge, record, record_citation,
                        Path(scratch))
                    if carried_on:
                        job_failure_tasks += [no_progress_task] if no_progress_task else []
                        break
                    untested_merges_and_times.pop(0)
            untestable = [merge for merge in merges
                          if merge in state.get(UNTESTABLE_MERGES_STATE_KEY, {})]
            record.append(f"merges tested: {len(merges) - len(untested_merges_and_times)} of "
                          f"{len(merges)}"
                          + (f", {len(untestable)} of them recorded as untestable"
                             if untestable else ""))
            if not untested_merges_and_times:
                no_mutant_started_after_unix_time = (
                    unix_time_cron_next_starts_this_program_on_ned_box(
                        arguments.scheduled_jobs_on_each_machine_json_file, time.time())
                    - arguments.second_pass_stops_starting_mutants_seconds_before_next_scheduled_run)
                with tempfile.TemporaryDirectory(prefix=f"{PROGRAM}-") as scratch:
                    carried_on = \
                        second_pass_mutation_tests_mutants_not_run_newest_merge_first_until_stop_time(
                            no_mutant_started_after_unix_time, arguments, state, state_file,
                            record, record_citation, Path(scratch))
    except (StepFailed, OSError) as error:
        failure = str(error)
        record.append(f"FAILED: {failure}")
    except Exception as error:
        failure = (f"the run raised {type(error).__name__}: {error}, which this program does "
                   f"not handle; fix the cause in scripts/{PROGRAM}.py.\n"
                   f"{traceback.format_exc().rstrip()}")
        record.append(f"FAILED: {failure}")
    if failure is not None:
        job_failure_tasks.insert(0, (
            f"Nightly full mutation pass stopped at a failed step: {failure.splitlines()[0][:200]}",
            (f"The scheduled full mutation pass on ned-box stopped at a failed step in its run "
            f"of {started.strftime('%Y-%m-%d %H:%M')} UTC, so the merges after the failed step "
            f"were not mutation-tested. It said:\n\n{failure}\n\n"
            f"Its record: {record_citation}\n"
            f"Do what the failure says. The next nightly run tries the step again, and opens no "
            f"second task while this one is open with the same subject.\n"
            f"Mark this task completed once a run gets past the step; to check sooner, run it by "
            f"hand on ned-box: {RUN_BY_HAND}")))
    checked_at = time.time()
    overdue = [(merge, merged_at) for merge, merged_at in untested_merges_and_times
               if checked_at - merged_at
               >= MERGE_STILL_UNTESTED_TASK_OPENED_AFTER_SECONDS_SINCE_MERGE]
    if overdue:
        oldest, oldest_merged_at = overdue[0]
        merged = datetime.fromtimestamp(oldest_merged_at, timezone.utc).strftime(
            "%Y-%m-%d %H:%M")
        job_failure_tasks.append((
            MERGES_STILL_UNTESTED_THREE_DAYS_AFTER_MERGING_TASK_SUBJECT,
            (f"{len(overdue)} merge(s) into main are not yet recorded as mutation-tested by the "
            f"scheduled full mutation pass on ned-box three days or more after they merged, as "
            f"of its run of {started.strftime('%Y-%m-%d %H:%M')} UTC. The oldest is merge "
            f"{oldest}, made {merged} UTC. The pass tests the merges in order, so it no longer "
            f"keeps up with what is merged. Each night's run rewrites this description with "
            f"that night's count and oldest merge.\n"
            f"Its latest record: {record_citation}\n"
            f"The first pass already runs at most {FIRST_PASS_MUTANTS_RUN_PER_MERGE_AT_MOST} "
            f"mutants of each merge, in order, so it must run fewer: bring the user an "
            f"approval-walk item proposing how.\n"
            f"Mark this task completed once the user has ruled on that, or once no merge is "
            f"three days untested."),
            True))
    if not_rechecked:
        job_failure_tasks.append((
            SURVIVOR_TASKS_NOT_RECHECKED_TASK_SUBJECT,
            (f"The scheduled full mutation pass on ned-box left {len(not_rechecked)} survivor "
             f"task(s) as they were in its run of {started.strftime('%Y-%m-%d %H:%M')} UTC, "
             f"because the recorded mutant killed check gave no verdicts for them on main:\n\n"
             + "".join(f"- {line}\n" for line in not_rechecked)
             + f"\nIts latest record: {record_citation}\n"
             f"Run each named task's command, given in the task, on ned-box with --head "
             f"origin/main added at its end, and fix what it prints. Each night's run rewrites "
             f"this description with that night's tasks.\n"
             f"Mark this task completed once a run rechecks every survivor task."),
            True))
    tasks_not_written = []
    for subject, description, *rewritten in job_failure_tasks:
        try:
            task_id, opened = job_failure_task_opened_unless_open(
                subject, description, arguments, *rewritten)
        except OSError as error:
            tasks_not_written.append(
                f"{subject} ({type(error).__name__}: {error})")
            record.append(f"FAILED: no job failure task could be opened on "
                          f"{JOB_FAILURE_TASK_AGENT_SEAT}'s task list: {tasks_not_written[-1]}")
            continue
        record.append(f"JOB FAILURE TASK: {'opened' if opened else 'already open, so none opened:'}"
                      f" task #{task_id} on {JOB_FAILURE_TASK_AGENT_SEAT}'s task list, {subject}")
    if state is not None:
        record.append(run_record_line_counting_mutants_not_run_and_naming_oldest_merge_with_one(
            state, started.timestamp()))
    record.append(f"wall-clock seconds: {time.monotonic() - started_monotonic:.0f}")
    if failure is not None:
        print(f"{PROGRAM}: {failure}", file=sys.stderr)
    if tasks_not_written:
        print(f"{PROGRAM}: {len(tasks_not_written)} task(s) for a failure of this run could not "
              f"be opened on {JOB_FAILURE_TASK_AGENT_SEAT}'s task list, so no agent is told of "
              f"them:\n" + "".join(f"  {line}\n" for line in tasks_not_written)
              + f"Fix what the error names, such as a task list directory that does not exist, "
              f"then run this program again on ned-box: {RUN_BY_HAND}", file=sys.stderr)
    if lost_tasks:
        print(f"{PROGRAM}: {len(lost_tasks)} task(s) that an earlier run opened for a surviving "
              f"mutant, and that are not marked completed, no longer hold it:\n"
              + "".join(f"  {line}\n" for line in lost_tasks)
              + "This run opened no task in their place, and later runs do not report them "
              "again.\n"
              "If a task above was finished and then deleted, nothing needs doing.\n"
              "Otherwise its mutant has no task: open one on the owner's task list that cites "
              "the mutant's diff file the line names.", file=sys.stderr)
    if not_rechecked:
        print(f"{PROGRAM}: {len(not_rechecked)} survivor task(s) were left as they were, because "
              f"the recorded mutant killed check gave no verdicts for them on main:\n"
              + "".join(f"  {line}\n" for line in not_rechecked)
              + "The next run checks them again.\n"
              "If the next run names a task again, run that task's command, given in the task, "
              "on ned-box with --head origin/main added at its end, and fix what it prints.",
              file=sys.stderr)
    try:
        record_write(record_path, record)
    except OSError as error:
        print("\n".join(record) + "\n", end="")
        print(f"{PROGRAM}: the record above was not written to {record_citation} "
              f"({type(error).__name__}: {error}); the record stays only in this run's "
              f"output.", file=sys.stderr)
        try:
            task_id, opened = job_failure_task_opened_unless_open(
                RUN_RECORD_NOT_WRITTEN_TASK_SUBJECT,
                (f"The scheduled full mutation pass on ned-box could not write the record of its "
                 f"run of {started.strftime('%Y-%m-%d %H:%M')} UTC to {record_citation} "
                 f"({type(error).__name__}: {error}). The record is in the job's log instead, "
                 f"{LOG_STORE_HOST}:{JOB_LOG_FILE}, under that run's start line.\n"
                 f"Fix what the error names, such as a log-store directory that cannot be "
                 f"written. Each night's run whose record is not written rewrites this "
                 f"description.\n"
                 f"Mark this task completed once a run's record is written to the log-store."),
                arguments, True)
        except OSError as task_error:
            print(f"{PROGRAM}: the task that tells an agent this run's record was not written "
                  f"could not be opened on {JOB_FAILURE_TASK_AGENT_SEAT}'s task list "
                  f"({type(task_error).__name__}: {task_error}), so only this job's log, "
                  f"{LOG_STORE_HOST}:{JOB_LOG_FILE}, shows that the record was not written.\n"
                  f"Fix what both errors name: the record's, in the line that begins "
                  f"\"{PROGRAM}: the record above was not written\", and the task's, in the "
                  f"first line of this message, such as the task list directory "
                  f"{arguments.task_lists_directory / f'nedschorus-{JOB_FAILURE_TASK_AGENT_SEAT}-tasks'} "
                  f"not existing.\n"
                  f"Nothing this run found is lost: the tasks it opened for surviving mutants "
                  f"stay open, and {state_file} records the merges it tested, so the next run "
                  f"does not test them again. Only the record is missing from the log-store, "
                  f"and this job's log holds the record.\n"
                  f"No hand run is needed: the job's next scheduled run, the next night, "
                  f"writes its own record and, if that record cannot be written either, tries "
                  f"again to open a task for it.\n"
                  f"To check your fix sooner, run on ned-box: {RUN_BY_HAND}", file=sys.stderr)
        else:
            how = ("opened" if opened
                   else "was already open, so this run rewrote its description with this run's "
                        "error")
            print(f"{PROGRAM}: JOB FAILURE TASK: task #{task_id} on "
                  f"{JOB_FAILURE_TASK_AGENT_SEAT}'s task list, "
                  f"\"{RUN_RECORD_NOT_WRITTEN_TASK_SUBJECT}\", {how}. "
                  f"The agent-seat {JOB_FAILURE_TASK_AGENT_SEAT} acts on that task; no one needs to act on "
                  f"this log line.", file=sys.stderr)
        return EXIT_RECORD_NOT_WRITTEN
    print(f"{PROGRAM}: record written to {record_citation}")
    if failure is not None or tasks_not_written:
        return EXIT_STEP_FAILED
    if lost_tasks:
        return EXIT_OPENED_TASK_NO_LONGER_HOLDS_ITS_SURVIVOR
    if not_rechecked:
        return EXIT_SURVIVOR_TASK_MUTANTS_NOT_JUDGED_TASK_LEFT_AS_IT_WAS
    if carried_on:
        return EXIT_MERGE_CARRIED_ON_TO_NEXT_RUN
    return EXIT_ALL_DONE


if __name__ == "__main__":
    sys.exit(main())
