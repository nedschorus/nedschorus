#!/usr/bin/env python3
"""Run the full mutation pass on each pull request merged into main since the last run, and open a task for each surviving mutant.

Usage:
  scripts/scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open.py
      [--clone DIR] [--log-store-root DIR] [--state-directory DIR]
      [--task-lists-directory DIR] [--agent-seats-directory DIR]
      [--cosmic-ray-venv DIR] [--mutation-testing-program PATH]
      [--merge-timeout-seconds S]

Every option is a seam for this program's test and for a run made by hand that
must not touch the real state, task lists or log-store. A scheduled run
passes none.

WHAT ONE RUN DOES, in order.

  1. Takes an exclusive lock on LOCK_FILE_NAME in the state directory; while
     another run holds it, this run exits EXIT_ANOTHER_RUN_HOLDS_THE_LOCK
     having done nothing, and the next scheduled run carries on.
  2. Runs `git fetch origin main` in the clone and resolves origin/main.
  3. Reads STATE_FILE_NAME in the state directory: the last main commit
     mutation-tested, and a key for each surviving mutant given a task. With
     no state file, it writes one naming origin/main and tests nothing: the
     merges after that commit are tested from the next run on.
  4. For each commit on main's first-parent line after the last one tested,
     oldest first, which is each merge of a pull request, runs
     scripts/mutation-testing-changed-lines-quick-or-full-pass-survivors.py
     with --full-mutation-pass, --head the commit and --base its first
     parent, so the lines that pull request changed are mutated, with
     --cosmic-ray-venv and --survived-and-errored-mutants-json-file. A run
     still going after --merge-timeout-seconds is sent SIGTERM, on which that
     program removes its scratch worktree.
  5. Opens a task for each surviving mutant (TASKS below), then records the
     commit as tested, so a merge is mutation-tested once.
  6. Writes the record (THE RECORD below) and prints its citation.

A step that fails stops the run there: a failed fetch, a state file that
cannot be read or no longer names an ancestor of origin/main, a missing
cosmic-ray venv, a mutation testing run that exits other than 0 or 1, runs
past the limit or writes no readable JSON, and a task that cannot be opened.
The commit it stopped at is not recorded as tested, so the next run tries it
again; a task already opened for one of its mutants is not opened twice. The
record names the failure, and the run exits EXIT_STEP_FAILED. A mutant the
mutation testing program reports ERRORED, and a changed file with no suite,
are named in the record and get no task.

TASKS. A task is a Claude Code task file, `<id>.json` in the task list
directory `nedschorus-<agent-seat>-tasks` under --task-lists-directory, with
the keys id, subject, description, status, blocks and blockedBy. The
agent-seat is the author `git blame` gives the mutant's line at the merge,
since each agent-seat commits under its own name. When that agent-seat has no
task list directory or no checkout under --agent-seats-directory, as after it
is retired, the task goes on the task list of SURVIVOR_TASK_AGENT_SEAT_WHEN_LINE_AUTHOR_IS_RETIRED_OR_UNKNOWN.
The id is one more than the highest of the list's task ids and its
`.highwatermark`, as Claude Code numbers a new task; the file is linked into
place only where no file of that name exists, and the `.highwatermark` is
raised to it, so a task Claude Code creates at the same moment is not
overwritten. The task asks the agent-seat to add a test that kills the
mutant, or to end the line with a `# pragma: no mutate` comment saying why no
test can, which every mutation pass then skips.

THE RECORD is one text file per run in the log-store:

  nedlern@ned-box:/home/nedlern/nedschorus-logs/scheduled-full-mutation-pass-runs-of-merged-pull-requests/<UTC start>.txt

It holds origin/main, the commit the run started after, a line per merge with
the mutation testing program's SUMMARY line, a line per surviving mutant with
the task it was given, a line per ERRORED mutant and changed file with no
suite, each failure, and the wall-clock seconds. This program runs on ned-box
only, so the record is written locally. A record that cannot be written is
printed on standard output instead, and the run exits EXIT_RECORD_NOT_WRITTEN.

SCHEDULE. Installed on ned-box by
nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py from
scheduled-jobs-on-each-machine.json, with both output streams appended to
~/.claude/scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open.log,
which, with the record, is where its failures are read.

Exit codes: 0 every merge since the last run was mutation-tested and its
survivors given tasks, or the first run wrote the state file;
EXIT_STEP_FAILED (4) a step failed, as above; EXIT_RECORD_NOT_WRITTEN (5) the
record could not be written;
EXIT_ANOTHER_RUN_HOLDS_THE_LOCK (6).
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
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

PROGRAM = "scheduled-full-mutation-pass-of-merged-pull-requests-and-survivor-tasks-open"
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
RUN_BY_HAND = f"cd /home/nedlern/Projects/nedschorus && python3 scripts/{PROGRAM}.py"

MUTATION_TESTING_PROGRAM = Path(__file__).resolve().with_name(
    "mutation-testing-changed-lines-quick-or-full-pass-survivors.py")
DEFAULT_LOG_STORE_ROOT = "/home/nedlern/nedschorus-logs"
RECORDS_DIRECTORY_NAME = "scheduled-full-mutation-pass-runs-of-merged-pull-requests"
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
SECONDS_FOR_MUTATION_TESTING_PROGRAM_TO_CLEAN_UP_AFTER_SIGTERM = 120

EXIT_ALL_DONE = 0
EXIT_STEP_FAILED = 4
EXIT_RECORD_NOT_WRITTEN = 5
EXIT_ANOTHER_RUN_HOLDS_THE_LOCK = 6
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
    if completed.returncode != 0:
        raise StepFailed(
            f"git {' '.join(arguments)} failed in {clone} (exit {completed.returncode}): "
            f"{(completed.stderr.strip().splitlines() or ['no detail'])[-1]}. "
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


def task_text(mutant, merge, merge_subject, author, owner_reason, record_citation):
    subject = (f"Surviving mutant in {mutant['module_path']}:{mutant['line']}: add a test that "
               f"kills it, or record why no test can")
    whose = ("You wrote the line." if owner_reason is None
             else f"Agent-seat {author} wrote the line; this task is on your list because "
                  f"{owner_reason}.")
    description = (
        f"The scheduled full mutation pass found a mutant that no test kills in "
        f"{mutant['module_path']}:{mutant['line']} (cosmic-ray operator {mutant['operator']}), "
        f"a line merged into main in {merge[:12]} ({merge_subject}). {whose} A surviving "
        f"mutant means the code can be changed this way while every suite that reads the file "
        f"still passes, so a defect there would go unnoticed.\n\n"
        f"The mutant, as a diff against main at {merge[:12]}:\n{mutant['diff']}\n\n"
        f"If the line is no longer on main as the diff shows it: mark this task completed; "
        f"there is nothing to do.\n"
        f"If a test can tell the mutant from the code: add that test in a new pull request, "
        f"and show it kills the mutant by applying the diff above to the file by hand, "
        f"running the test's suite, seeing it fail, and undoing the diff.\n"
        f"If no test can, because the mutant behaves exactly as the code does: in a new pull "
        f"request, end the line with a comment that starts `# pragma: no mutate` and goes on "
        f"to say why no test can kill its mutants, such as `# pragma: no mutate, both "
        f"branches return the same value`; every mutation pass skips a line whose comment "
        f"says `pragma: no mutate`.\n"
        f"The run's record: {record_citation}")
    return subject, description


def run_mutation_testing(arguments, merge, parent, json_file):
    """Return (exit code or None when it ran past the limit, stdout, stderr)."""
    command = [sys.executable, arguments.mutation_testing_program, "--full-mutation-pass",
               "--checkout", str(arguments.clone), "--head", merge, "--base", parent,
               "--cosmic-ray-venv", str(arguments.cosmic_ray_venv),
               "--survived-and-errored-mutants-json-file", str(json_file)]
    environment = daily_full_test_run_of_main.\
        environment_with_user_runtime_directory_when_the_user_session_bus_exists(
            dict(os.environ))
    process = subprocess.Popen(command, env=environment, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               errors="replace")
    try:
        stdout, stderr = process.communicate(timeout=arguments.merge_timeout_seconds)
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


def summary_line(stdout):
    lines = [line for line in stdout.splitlines() if line.startswith("SUMMARY:")]
    return lines[-1] if lines else "no SUMMARY line"


def test_one_merge(arguments, state, state_file, merge, record, record_citation, scratch):
    parent = git_or_raise(arguments.clone, "rev-parse", "--verify", f"{merge}^1^{{commit}}")
    merge_subject = git_or_raise(arguments.clone, "log", "-1", "--format=%s", merge)
    json_file = scratch / f"{merge}.json"
    exit_code, stdout, stderr = run_mutation_testing(arguments, merge, parent, json_file)
    command_shown = (f"python3 {arguments.mutation_testing_program} --full-mutation-pass "
                     f"--head {merge} --base {parent} --cosmic-ray-venv "
                     f"{shlex.quote(str(arguments.cosmic_ray_venv))}")
    said = (stderr.strip() or stdout.strip() or "nothing").splitlines()[-1]
    if exit_code is None:
        raise StepFailed(
            f"merge {merge[:12]} ({merge_subject}): the mutation testing program ran past the "
            f"limit of {arguments.merge_timeout_seconds:g} s and was stopped; its last line: "
            f"{said}. The next run tries this merge again.\n"
            f"If it runs past the limit again, run it by hand on ned-box to see how long it "
            f"takes: {command_shown}")
    if exit_code not in MUTATION_TESTING_EXITS_WITH_A_VERDICT:
        raise StepFailed(
            f"merge {merge[:12]} ({merge_subject}): the mutation testing program exited "
            f"{exit_code} with no verdict: {said}. The next run tries this merge again.\n"
            f"If it fails the same way again, run it by hand on ned-box, do what its message "
            f"says, and fix the cause: {command_shown}")
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
            f"If the next run fails the same way, {Path(arguments.mutation_testing_program).name} "
            f"and scripts/{PROGRAM}.py disagree on that file's contents: make the reader in "
            f"test_one_merge() match --survived-and-errored-mutants-json-file in the other "
            f"program's docstring, or the writer match the docstring.") from error
    record.append(f"merge {merge[:12]} {merge_subject}: {summary_line(stdout)}")
    for mutant in survived:
        place = f"{mutant['module_path']}:{mutant['line']} {mutant['operator']}"
        key = mutant_key(mutant)
        if key in state["tasks_opened"]:
            given = state["tasks_opened"][key]
            record.append(f"  SURVIVED {place}: already given task #{given['task_id']} on "
                          f"{given['agent_seat']}'s task list")
            continue
        blame = git_or_raise(arguments.clone, "blame", "--porcelain", "-L",
                             f"{mutant['line']},{mutant['line']}", merge, "--",
                             mutant["module_path"])
        author = next((line[len("author "):] for line in blame.splitlines()
                       if line.startswith("author ")), "")
        owner, owner_reason = task_list_owner(author, arguments.task_lists_directory,
                                              arguments.agent_seats_directory)
        subject, description = task_text(mutant, merge, merge_subject, author, owner_reason,
                                         record_citation)
        list_directory = arguments.task_lists_directory / f"nedschorus-{owner}-tasks"
        try:
            task_id = agent_seat_task_list_new_pending_task_write(list_directory, subject, description)
        except OSError as error:
            raise StepFailed(
                f"merge {merge[:12]}: no task could be opened on {owner}'s task list for the "
                f"surviving mutant {place} ({type(error).__name__}: {error}). The next run "
                f"tries this merge again, and opens no second task for a mutant already "
                f"given one.\n"
                f"Fix what the error names, such as a missing task list directory "
                f"{list_directory}, then run this program again on ned-box: {RUN_BY_HAND}") from error
        state["tasks_opened"][key] = {"agent_seat": owner, "task_id": task_id}
        write_state(state_file, state)
        record.append(f"  SURVIVED {place}: task #{task_id} opened on {owner}'s task list")
    for mutant in errored:
        record.append(f"  ERRORED {mutant['module_path']}:{mutant['line']} {mutant['operator']}"
                      f" ({mutant['reason'] or 'cosmic-ray could not judge it'}): no task")
    for path in files_with_no_suite:
        record.append(f"  NO SUITE {path}: its changed lines were not mutation-tested; no task")
    state["last_tested_main_commit"] = merge
    write_state(state_file, state)


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
            if git(arguments.clone, "merge-base", "--is-ancestor", last,
                   main_commit).returncode != 0:
                raise StepFailed(
                    f"the last tested commit {last}, from {state_file}, is not an ancestor of "
                    f"origin/main {main_commit}, so the merges since it cannot be listed.\n"
                    f"Set last_tested_main_commit in that file to the commit on origin/main "
                    f"from which merges should be tested, then run this program again on ned-box: {RUN_BY_HAND}")
            merges = git_or_raise(arguments.clone, "rev-list", "--first-parent", "--reverse",
                                  f"{last}..{main_commit}").split()
            if merges and not (arguments.cosmic_ray_venv / "bin" / "cosmic-ray").is_file():
                venv = shlex.quote(str(arguments.cosmic_ray_venv))
                raise StepFailed(
                    f"cosmic-ray is not installed in {arguments.cosmic_ray_venv}, so no merge "
                    f"can be mutation-tested.\n"
                    f"Install it on ned-box: python3 -m venv {venv} && {venv}/bin/pip install "
                    f"cosmic-ray=={COSMIC_RAY_VERSION}, then run this program again on ned-box: {RUN_BY_HAND}")
            with tempfile.TemporaryDirectory(prefix=f"{PROGRAM}-") as scratch:
                for merge in merges:
                    test_one_merge(arguments, state, state_file, merge, record,
                                   record_citation, Path(scratch))
            record.append(f"merges tested: {len(merges)}")
    except (StepFailed, OSError) as error:
        failure = str(error)
        record.append(f"FAILED: {failure}")
    record.append(f"wall-clock seconds: {time.monotonic() - started_monotonic:.0f}")
    text = "\n".join(record) + "\n"
    if failure is not None:
        print(f"{PROGRAM}: {failure}", file=sys.stderr)
    try:
        record_path.parent.mkdir(parents=True, exist_ok=True)
        record_path.write_text(text, encoding="utf-8")
    except OSError as error:
        print(text, end="")
        print(f"{PROGRAM}: the record above was not written to {record_citation} "
              f"({type(error).__name__}: {error}).\n"
              f"Fix what the error names; the next run writes its own record, and this one "
              f"stays only in this output.", file=sys.stderr)
        return EXIT_RECORD_NOT_WRITTEN
    print(f"{PROGRAM}: record written to {record_citation}")
    return EXIT_STEP_FAILED if failure is not None else EXIT_ALL_DONE


if __name__ == "__main__":
    sys.exit(main())
