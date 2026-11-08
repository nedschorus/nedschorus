#!/usr/bin/env python3
"""Run the full mutation pass on each pull request merged into main since the last run, open a task for each line with surviving mutants, and recheck each open task on main.

Usage:
  scripts/scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open.py
      [--clone DIR] [--log-store-root DIR] [--state-directory DIR]
      [--task-lists-directory DIR] [--agent-seats-directory DIR]
      [--cosmic-ray-venv DIR] [--mutation-testing-program PATH]
      [--merge-timeout-seconds S]
      [--survivor-task-recorded-mutant-killed-check-timeout-seconds S]

Every option is a seam for this program's test and for a run made by hand that
must not touch the real state, task lists or log-store. A scheduled run
passes none.

TERMS. A mutant's key is the SHA-256 of a JSON list of its file path, cosmic-ray
operator and diff. A mutant's diff file holds its diff, as
scheduled-full-mutation-pass-runs-of-merged-pull-requests/surviving-mutant-diffs/<key>.diff
under --log-store-root, which is where
--recorded-mutant-killed-check reads it from. A survivor task is a task this
program opens for the surviving mutants of one line; its subject starts
`Surviving mutants in <file>:<line>: ` (`Surviving mutant in` in a task an
earlier version opened). The task's owner is the agent-seat whose task list
holds it (TASKS below). The state file is state.json in --state-directory: the
last main commit mutation-tested, under last_tested_main_commit, and, under
tasks_opened, each surviving mutant's key with the agent-seat and id of the
survivor task that lists it.

WHAT ONE RUN DOES, in order.

  1. Takes an exclusive lock on
     scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open.lock
     in --state-directory; while another run holds it, this run exits
     EXIT_ANOTHER_RUN_HOLDS_THE_LOCK having done nothing, and the next
     scheduled run carries on.
  2. Runs `git fetch origin main` in the clone and resolves origin/main.
  3. Reads the state file. With no state file, it writes one naming
     origin/main and tests nothing: the merges after that commit are tested
     from the next run on.
  4. Checks that each survivor task the state names still lists each of its
     mutants: the task file is still on its owner's task list, not marked
     completed, and its description still names each mutant's diff file. A
     mutant whose task no longer holds it, because the task is marked
     completed, or its file is gone or cannot be read, or its description no
     longer names the diff file, goes one of three ways:
     - Moved: when exactly one other task on the same list, not marked
       completed, names its diff file, the state alone is changed to name that
       task, as when an agent moves the mutants of several survivor tasks into
       one and marks the others completed, whether or not the session-handoff
       has yet removed those completed tasks.
     - Finished: when its task is marked completed and no task not marked
       completed names its diff file, the state stops naming it.
     - Reported once: in every other case, which is a task not marked
       completed, gone or unreadable, with no other open task or with two or
       more naming the diff file; or a task marked completed with two or more
       other open tasks naming it.
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
  6. For each commit on main's first-parent line after the last one tested,
     oldest first, which is each merge of a pull request, runs
     scripts/mutation-testing-changed-lines-quick-or-full-pass-survivors.py
     with --full-mutation-pass, --head the commit and --base its first
     parent, so the lines that pull request changed are mutated, with
     --cosmic-ray-venv, --survived-and-errored-mutants-json-file,
     --parallel-mutant-workers and --cosmic-ray-sessions-directory-kept-to-resume
     (CARRYING A MERGE ON below). The worker count, read as each merge starts,
     is the machine's cores less its load average over the last minute, at
     least 1; each worker has a worktree of its own, and its suites still wait
     for the suite runner's admission.
  7. Opens a survivor task for each line with surviving mutants (TASKS
     below), then records the commit as tested, so a merge is
     mutation-tested once.
  8. Opens a task for each failure of the run (JOB FAILURE TASKS below).
  9. Writes the record (THE RECORD below), in full over any written at step
     4, and prints its citation.

CARRYING A MERGE ON. Each merge's cosmic-ray sessions are kept in
COSMIC_RAY_SESSIONS_KEPT_FOR_UNFINISHED_MERGES_DIRECTORY_NAME/<merge> under
--state-directory. A run of the mutation testing program still going after
--merge-timeout-seconds is sent SIGTERM, on which that program removes its
scratch worktrees; the merge is not recorded as tested, the run tests no
later merge, and the next run goes on with this merge from its first mutant
with no result. Each run first removes the kept sessions of every merge that
is no longer waiting to be tested.

A step that fails stops the run there, and steps 8 and 9 still run, to open
the failure's task and write the record: a failed fetch, a state file that
cannot be read or no longer names an ancestor of origin/main, a survivor task,
diff file or state file that the recheck cannot read or write, a missing
cosmic-ray venv, a kept session that cannot be read or removed, a mutation
testing run that exits other than 0 or 1 or writes no readable JSON, a
mutant's diff or task that cannot be written, and an error this program does
not handle, whose traceback the record keeps.
The commit it stopped at is not recorded as tested, so the next run tries it
again; a line already given a task is not given a second one, since a line
counts as given a task when the state names a task for each of its surviving
mutants or when its owner's list holds a survivor task for the line not
marked completed, which covers a task opened just before a write of the state
or the `.highwatermark` failed. The record names the failure, and the run
exits EXIT_STEP_FAILED. A mutant the mutation testing program reports
ERRORED, and a changed file with no suite, are named in the record and get no
task.

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
program can lose either rewrite; step 4 of the next run then reports each
mutant the task no longer lists.

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
as in a task an earlier version opened, is rewritten to list only them; its
other keys, status included, are kept. A mutant the program could not judge
stays listed. A run of the program still going after
--survivor-task-recorded-mutant-killed-check-timeout-seconds is sent SIGTERM;
a run that writes no readable verdicts leaves its task as it was, is named in
the record and on standard error, and the run goes on and exits
EXIT_SURVIVOR_TASK_MUTANTS_NOT_JUDGED_TASK_LEFT_AS_IT_WAS. Each rechecked
mutant adds about 30 seconds to the run.

JOB FAILURE TASKS. The run opens a task on the task list of the agent-seat
JOB_FAILURE_TASK_AGENT_SEAT names, saying what failed and what to do, for each
failure of the run itself: a step that failed, as above; a merge carried on
with no mutant judged beyond those its kept sessions held before the run; and
any merge still not recorded as tested
MERGE_STILL_UNTESTED_TASK_OPENED_AFTER_SECONDS_SINCE_MERGE, three days, after
its merge commit, the sign that the pass no longer keeps up and that the lines
it mutates must be chosen. A failed step's task has the first line of its
message as its subject, and a carried-on merge's task names the merge. The
untested merges share one task, with the fixed subject
MERGES_STILL_UNTESTED_THREE_DAYS_AFTER_MERGING_TASK_SUBJECT, whose
description gives their count and the oldest; each run rewrites the
description of that task while it is open. While a task with the same
subject is open on that list, no second one is opened, and the record names
the open one. No task is completed by this program: the agent-seat
completes it once the cause is fixed. A task that cannot be opened is named
in the record and on standard error, and the run exits EXIT_STEP_FAILED.

THE RECORD is one text file per run in the log-store:

  nedlern@ned-box:/home/nedlern/nedschorus-logs/scheduled-full-mutation-pass-runs-of-merged-pull-requests/<UTC start>.txt

It holds origin/main, the commit the run started after, a line per survivor
task rechecked with its verdicts and what was done to the task, a line per
merge with its worker count, the mutants its kept sessions already held and
the mutation testing program's SUMMARY line, or, for a merge carried on, how
many mutants are judged, a line per job failure task, a line per surviving
mutant with the task it was given or was added to, a line per ERRORED mutant
and changed file with no suite, each failure, and the wall-clock seconds.
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

The cron line:

    30 0 * * * /usr/bin/python3 /home/nedlern/Projects/nedschorus/scripts/scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open.py >> /home/nedlern/.claude/scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open.log 2>&1

Exit codes: 0 every survivor task was rechecked and every merge since the last
run was mutation-tested and its survivors given tasks, or the first run wrote
the state file; EXIT_STEP_FAILED (4) a step failed, as above;
EXIT_RECORD_NOT_WRITTEN (5) the record could not be written;
EXIT_ANOTHER_RUN_HOLDS_THE_LOCK (6);
EXIT_OPENED_TASK_NO_LONGER_HOLDS_ITS_SURVIVOR (7) no step failed, but a
mutant a survivor task an earlier run opened held was reported at step 4:
its task's file is gone or cannot be read, or its task, not marked completed,
no longer lists it, and no other open task or two or more name it; or its
task is marked completed and two or more other open tasks name it;
EXIT_SURVIVOR_TASK_MUTANTS_NOT_JUDGED_TASK_LEFT_AS_IT_WAS (8) no step failed
and no task was lost, but the recheck gave no verdicts for a survivor task;
EXIT_MERGE_CARRIED_ON_TO_NEXT_RUN (9) none of those, but a merge ran past the
limit and is carried on.
When more than one applies, the run exits with the first of 5, 4, 7, 8 and 9
that applies: an unwritten record outranks a failed step, which outranks a
lost task, which outranks an unjudged recheck, which outranks a carried-on
merge.
"""

# Messages here follow docs/nedschorus-wiki/nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md.

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
LOCK_FILE_NAME = "scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open.lock"
DEFAULT_TASK_LISTS_DIRECTORY = Path.home() / ".claude" / "tasks"
DEFAULT_AGENT_SEATS_DIRECTORY = Path.home() / "agents"
DEFAULT_COSMIC_RAY_VENV = Path.home() / ".local" / "share" / "nedschorus" / "cosmic-ray-venv"
COSMIC_RAY_VERSION = "8.7.0"
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


git_redirecting_removal = module_loaded_by_path(
    "git_redirecting_environment_variables_removal_common",
    REPOSITORY_ROOT / "nc-systems" / "general-tools"
    / "git-redirecting-environment-variables-removal-common.py")
daily_full_test_run_of_main = module_loaded_by_path(
    "daily_full_test_run_of_main", Path(__file__).resolve().with_name(
        "daily-full-test-run-of-main.py"))


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
                or not isinstance(state["tasks_opened"], dict):
            raise TypeError("a key holds the wrong type")
    except (ValueError, KeyError, TypeError) as error:
        raise StepFailed(
            f"the state file {state_file} cannot be read ({type(error).__name__}: {error}), so "
            f"this run does not know which merges are already tested or which mutants already "
            f"have tasks. Nothing was tested.\n"
            f"If the file can be repaired by hand, repair it: it holds last_tested_main_commit, "
            f"a commit hash, and tasks_opened, an object.\n"
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
    and re-point a mutant to the one other open task on its owner's list that names it.

    Return one line per task that no longer holds its mutant, is not completed, and has no
    single open task on the list naming the mutant, and per completed task whose mutant more
    than one open task names; the caller writes the state. Raises OSError when another task
    file on the list cannot be read."""
    lost = []
    for key, given in list(state["tasks_opened"].items()):
        list_directory = arguments.task_lists_directory / f"nedschorus-{given['agent_seat']}-tasks"
        task_file = list_directory / f"{given['task_id']}.json"
        completed = False
        try:
            task = task_file_read(task_file)
        except OSError as error:
            why = f"the task file cannot be read ({type(error).__name__}: {error})"
        else:
            completed = task is not None and task.get("status") == "completed"
            if not completed and task_names_mutant(task, key):
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


def agent_seat_task_list_new_pending_task_write(list_directory, subject, description):
    """Write a new pending task into the list; return its id. Raises OSError."""
    if not list_directory.is_dir():
        raise FileNotFoundError(f"the task list directory {list_directory} does not exist")
    highest = 0
    for path in list_directory.iterdir():
        if TASK_FILE_NAME_PATTERN.fullmatch(path.name):
            highest = max(highest, int(path.stem))
    mark_path = list_directory / TASK_HIGH_WATER_MARK_FILE_NAME
    mark = mark_path.read_text(encoding="utf-8").strip() if mark_path.is_file() else ""
    if mark.isdigit():
        highest = max(highest, int(mark))
    task_id = highest + 1
    with tempfile.NamedTemporaryFile("w", dir=list_directory, prefix=".task-", suffix=".partial",
                                     delete=False, encoding="utf-8") as partial:
        partial_path = Path(partial.name)
    try:
        while True:
            partial_path.write_text(json.dumps({
                "id": str(task_id), "subject": subject, "description": description,
                "status": "pending", "blocks": [], "blockedBy": []}, indent=2), encoding="utf-8")
            try:
                os.link(partial_path, list_directory / f"{task_id}.json")
                break
            except FileExistsError:
                task_id += 1
    finally:
        partial_path.unlink(missing_ok=True)
    mark_partial = list_directory / (TASK_HIGH_WATER_MARK_FILE_NAME + ".partial")
    mark_partial.write_text(str(task_id), encoding="utf-8")
    os.replace(mark_partial, mark_path)
    return task_id


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
    environment = daily_full_test_run_of_main.\
        environment_with_user_runtime_directory_when_the_user_session_bus_exists(
            dict(os.environ))
    process = subprocess.Popen(command, env=environment, stdin=subprocess.DEVNULL,
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


def mutation_testing_program_command_line_options_for_one_merge(arguments, merge, parent, workers,
                                                                sessions_directory):
    """The mutation testing program's options for one merge, shared by this run and the hand
    run a task gives, so the hand run resumes the same kept sessions."""
    return ["--full-mutation-pass", "--checkout", str(arguments.clone), "--head", merge,
            "--base", parent, "--cosmic-ray-venv", str(arguments.cosmic_ray_venv),
            "--parallel-mutant-workers", str(workers),
            "--cosmic-ray-sessions-directory-kept-to-resume", str(sessions_directory)]


def run_mutation_testing(arguments, merge, parent, json_file, workers, sessions_directory):
    """Return (exit code or None when it ran past the limit, stdout, stderr)."""
    return program_run_with_limit(
        [sys.executable, arguments.mutation_testing_program,
         *mutation_testing_program_command_line_options_for_one_merge(
             arguments, merge, parent, workers, sessions_directory),
         "--survived-and-errored-mutants-json-file", str(json_file)],
        arguments.merge_timeout_seconds)


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


def mutation_testing_hand_run_command(arguments, merge, parent, workers, sessions_directory):
    """The command that runs the mutation testing program on one merge as this run does,
    resuming its kept sessions with as many workers, outliving the shell it is typed in, with
    its output in the log-store."""
    log = (Path(arguments.log_store_root) / HAND_RUNS_DIRECTORY_NAME
           / f"merge-{merge[:8]}-hand-run.log")
    return (f"systemd-run --user --unit=mutation-hand-run-{merge[:8]} --collect "
            f"-p StandardOutput=append:{log} -p StandardError=append:{log} "
            f"/usr/bin/python3 {shlex.quote(str(arguments.mutation_testing_program))} "
            + shlex.join(mutation_testing_program_command_line_options_for_one_merge(
                arguments, merge, parent, workers, sessions_directory)))


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
    return (stderr.strip() or stdout.strip() or "nothing").splitlines()[-1]


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
                f"verdicts ({type(error).__name__}: {error}); its last line: "
                f"{last_line_said(stdout, stderr)}")
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


def summary_line(stdout):
    lines = [line for line in stdout.splitlines() if line.startswith("SUMMARY:")]
    return lines[-1] if lines else "no SUMMARY line"


def test_one_merge(arguments, state, state_file, merge, record, record_citation, scratch):
    """Mutation-test one merge and give its survivors tasks. Return (whether the mutation
    testing program ran past the limit, so the merge is carried on to the next run, and, when
    it then judged no new mutant, the job failure task to open, as (subject, description))."""
    parent = git_or_raise(arguments.clone, "rev-parse", "--verify", f"{merge}^1^{{commit}}")
    merge_subject = git_or_raise(arguments.clone, "log", "-1", "--format=%s", merge)
    json_file = scratch / f"{merge}.json"
    sessions_directory = sessions_directory_of_merge(arguments, merge)
    judged_before = count_of_mutants_judged_in_kept_cosmic_ray_sessions(sessions_directory)
    cores, load = os.cpu_count() or 1, os.getloadavg()[0]
    workers = mutant_worker_count_for_free_cores(cores, load)
    record.append(f"merge {merge[:12]}: {workers} mutant worker(s), from {cores} cores and a "
                  f"load average over the last minute of {load:.1f}; {judged_before} mutant(s) "
                  f"already judged in its kept sessions")
    exit_code, stdout, stderr = run_mutation_testing(arguments, merge, parent, json_file,
                                                     workers, sessions_directory)
    command_shown = mutation_testing_hand_run_command(arguments, merge, parent, workers,
                                                      sessions_directory)
    said = last_line_said(stdout, stderr)
    if exit_code is None:
        judged = count_of_mutants_judged_in_kept_cosmic_ray_sessions(sessions_directory)
        record.append(f"CARRIED ON: merge {merge[:12]} ({merge_subject}) ran past the limit of "
                      f"{arguments.merge_timeout_seconds:g} s with {judged} mutant(s) judged, "
                      f"{judged - judged_before} of them in this run; the next run goes on from "
                      f"its first mutant not yet run, and the merges after it wait. Its last "
                      f"line: {said}")
        if judged > judged_before:
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
    if exit_code not in MUTATION_TESTING_EXITS_WITH_A_VERDICT:
        raise StepFailed(
            f"merge {merge[:12]} ({merge_subject}): the mutation testing program exited "
            f"{exit_code} without saying whether each mutant was killed: {said}. The next run "
            f"tries this merge again.\n"
            f"If it fails the same way again, run this command by hand on ned-box, do what it "
            f"prints in its log, and fix the cause: {command_shown}")
    try:
        result = json.loads(json_file.read_text(encoding="utf-8"))
        survived, errored = result["survived"], result["errored"]
        files_with_no_suite = result["files_with_no_suite"]
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
    survived_by_line = {}
    for mutant in survived:
        survived_by_line.setdefault((mutant["module_path"], mutant["line"]), []).append(mutant)
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
    for mutant in errored:
        record.append(f"  ERRORED {mutant['module_path']}:{mutant['line']} {mutant['operator']}"
                      f" ({mutant['reason'] or 'cosmic-ray could not judge it'}): no task")
    for path in files_with_no_suite:
        record.append(f"  NO SUITE {path}: its changed lines were not mutation-tested; no task")
    state["last_tested_main_commit"] = merge
    write_state(state_file, state)
    return False, None


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
    parser.add_argument("--cosmic-ray-venv", type=Path, default=DEFAULT_COSMIC_RAY_VENV,
                        help="the venv holding cosmic-ray")
    parser.add_argument("--mutation-testing-program", default=str(MUTATION_TESTING_PROGRAM),
                        help="the program run for each merge; default, the one beside this file")
    parser.add_argument("--merge-timeout-seconds", type=float,
                        default=DEFAULT_MERGE_TIMEOUT_SECONDS,
                        help="the limit on mutation-testing one merge")
    parser.add_argument("--survivor-task-recorded-mutant-killed-check-timeout-seconds", type=float,
                        default=DEFAULT_SURVIVOR_TASK_RECORDED_MUTANT_KILLED_CHECK_TIMEOUT_SECONDS,
                        help="the limit on the recorded mutant killed check of one survivor task")
    return parser.parse_args(argv)


def main(argv=None):
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
                    f"cosmic-ray=={COSMIC_RAY_VERSION}, then run this program again on ned-box: {RUN_BY_HAND}")
            sessions_root = (arguments.state_directory
                             / COSMIC_RAY_SESSIONS_KEPT_FOR_UNFINISHED_MERGES_DIRECTORY_NAME)
            for kept in sorted(sessions_root.iterdir()) if sessions_root.is_dir() else ():
                if kept.name not in merges:
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
            record.append(f"merges tested: {len(merges) - len(untested_merges_and_times)} of "
                          f"{len(merges)}")
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
            f"Choose which changed lines matter most to mutation-test: bring the user an "
            f"approval-walk item proposing how the pass should choose them, since until then it "
            f"tests every changed line of every merge, in order.\n"
            f"Mark this task completed once the user has ruled on that, or once no merge is "
            f"three days untested."),
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
              f"({type(error).__name__}: {error}).\n"
              f"Fix what the error names; the next run writes its own record, and this one "
              f"stays only in this output.", file=sys.stderr)
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
