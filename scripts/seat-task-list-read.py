#!/usr/bin/env python3
"""Read the agent-seats' task lists, on both machines, so a task can be cited
and opened like the other ID-types.

Built at the user's word, 2026-09-21, during the walk
open-questions-concerns-and-recommendations-2026-09-21: "lets build the task
viewer tool now." It comes out of that walk's item 1, which settled how the
citation rule's six ID-types are written. Five of them -- pull request, GitHub
issue, commit, session, seat -- can be cited so a reader can open the thing.
A task could not: its words sit in a per-seat JSON store the reader has no
way to reach, so "task 85" was the one citation that could only ever be a
number.

ONE VIEWER, NOT TWO (user-ruled 2026-09-22). A second seat, not knowing this
program was on main, built a second viewer that read both machines and listed
every seat at once, and opened pull request [Show every seat's task list,
from both machines](https://github.com/nedschorus/nedschorus/pull/634). The
user ruled that its capability folds in here and that the second program does
not land. What came across: reading the other machine over ssh, the
every-seat listing (--every-task-list) and the full-task form in a listing
(--in-full).

THE STORE, measured 2026-09-21 and again 2026-09-22 on both machines. One
directory per agent-seat beneath ~/.claude/tasks/, named by that seat's
CLAUDE_CODE_TASK_LIST_ID, which on this project reads nedschorus-<seat>-tasks
for all seven lists on the Mac and the one on ned-box. Inside it one JSON
file per task, named <id>.json. Across the Mac's 789 task files, id, subject,
description, status, blocks and blockedBy are on every one, activeForm on
559, metadata on 48 and owner on 29, so only the first six are relied on. The
statuses seen are pending, in_progress and completed. The directory also
holds .lock and .highwatermark, which are the harness's; the *.json glob
leaves them out.

TWO MACHINES, ONE SSH ROUTE. Each machine has a store of its own: ned-box
holds nedschorus-merge-lane-2-tasks, the merge lane's own list, measured
2026-09-22. Which machine this run is on is read from the hostname and never
from a constant. Both reviewers of the pull request above blocked on exactly
that: a THIS_MACHINE_NAME constant labelled ned-box's store as the Mac's when
the tool ran on ned-box, never read the Mac, and ssh'd to the machine it was
already running on.

The route runs one way. CLAUDE.md names `ssh nedlern@ned-box` and no route
back, and measured 2026-09-22 ned-box reaches the Mac's port 22 but has no
trusted key for it: ssh from ned-box to this Mac answers "Host key
verification failed." So from the Mac both stores are read, and from ned-box
only ned-box's is; asking for the Mac there names the condition, says where
to run instead, and exits non-zero rather than showing one machine's seats as
the fleet. Opening a route the other way is the user's call, not this
program's to assume.

ned-box's store is read as ONE tar over ssh and unpacked here with the
standard library into a temporary directory, so nothing depends on which
Python that machine has (3.14 there, 3.9.6 as this Mac's system Python), and
so the reader, the unreadable-file notice, the resolver and the formatters
below are one piece of code serving both machines. A property this file holds
on one path only is the defect it has now produced twice, both recorded
below.

TAR'S EXIT IS NOT SSH'S. Measured on ned-box 2026-09-22 while tasks were
being written: 53 of 60 runs of the archiving command exited 1, "file changed
as we read it", having written a COMPLETE archive. So exit 1 is taken and its
tasks are read; exit 2 is tar's fatal one, a missing store among them, and is
reported with where to look; 255 is ssh itself failing to connect or
authenticate, and carries what ssh said and the remedy, per CLAUDE.md's
standing rule about ned-box.

A MISSING STORE IS NOT AN EMPTY LIST. A machine that was read and has no
store is reported as having none, never answered as "no tasks". An empty list
reads as an answer, and answering "no tasks" for a machine whose store was
never reached is the silent-wrong-answer shape this fleet keeps finding. The
same rule covers a task file that cannot be read: it is named, and the run
exits non-zero, because a silently dropped task is a task the reader will
never learn exists.

WHAT THIS DOES NOT CHANGE. A task list is seat-local working state that does
not outlive the worktree (user-ruled 2026-09-11, queued at
docs/nedschorus-wiki/queue/task-list-is-not-durable-state-draft.md: "Tasks
only survive as long as the worktree - these should be incorporated in GHIs
or their paired design files. Or perhaps in a queue."). Readable is not
durable. Anything carrying pending state that must outlive the seat still
belongs in a GHI, its paired document, or a queue file. This program makes
working state legible to whoever was handed a citation; it is not a reason to
keep state here.

READ ONLY. Nothing here writes, moves or deletes a task, on either machine.
The harness owns the store; an agent changes its own tasks through the task
tools. The one thing written anywhere is ned-box's archive, unpacked into a
temporary directory this run creates and removes, and only names that stay
inside it are unpacked.
"""

import argparse
import io
import json
import os
import socket
import subprocess
import sys
import tarfile
import tempfile
from collections import namedtuple
from pathlib import Path

DEFAULT_STORE = Path.home() / ".claude" / "tasks"
STORE_UNDER_HOME = Path(".claude") / "tasks"
LIST_ID_VARIABLE = "CLAUDE_CODE_TASK_LIST_ID"

MACHINE_NAME_MAC = "mac"
MACHINE_NAME_NED_BOX = "ned-box"
MACHINE_NAMES = (MACHINE_NAME_MAC, MACHINE_NAME_NED_BOX)
NED_BOX_HOSTNAME = "ned-box"
SSH_TARGET_BY_MACHINE = {MACHINE_NAME_NED_BOX: "nedlern@ned-box"}

SSH_ITSELF_FAILED_EXIT = 255
TAR_WROTE_EVERYTHING_BUT_WARNED_EXIT = 1
END_OF_TAR_ARCHIVE = bytes(2 * tarfile.BLOCKSIZE)

EXIT_EVERYTHING_ASKED_FOR_WAS_READ = 0
EXIT_SOMETHING_COULD_NOT_BE_READ = 1

# One task list on one machine: the machine's name, and a directory here that
# holds its task files -- the real store on this machine, and ned-box's
# unpacked archive for ned-box.
TaskListLocation = namedtuple("TaskListLocation", "machine directory")


def this_machine_name():
    """Which of the project's two machines this run is on, from the host.

    Never a constant. Both reviewers of the pull request named in the module
    docstring blocked on a constant here: on ned-box it labelled ned-box's
    store as the Mac's, left the Mac unread, and ssh'd to ned-box from
    ned-box.
    """
    hostname = socket.gethostname().split(".")[0]
    if hostname == NED_BOX_HOSTNAME:
        return MACHINE_NAME_NED_BOX
    return MACHINE_NAME_MAC


def machine_shown(machine):
    """A machine's name for display, marking the one this run is on."""
    if machine == this_machine_name():
        return f"{machine} (this machine)"
    return machine


def task_list_directories(store):
    """Every task list in the store, by directory name, sorted."""
    if not store.is_dir():
        return []
    return sorted(path for path in store.iterdir() if path.is_dir())


def task_lists_in_store(store, machine):
    """The store's task lists, each tied to the machine it came from."""
    return [TaskListLocation(machine, directory)
            for directory in task_list_directories(store)]


def no_store_notice(machine, store):
    """Said when a machine was reached and has no store at all."""
    return (f"No task store on {machine} at {store}.\n"
            f"Run this on the machine the seat runs on; this one has no "
            f"store.")


def no_route_notice(machine):
    """Said when this machine has no ssh route to the machine asked for.

    The project has one route, the Mac to ned-box, so this is what ned-box
    says when the Mac is asked for. Measured 2026-09-22: ned-box reaches the
    Mac's port 22 and is refused at the host key.
    """
    return (f"No ssh route from {this_machine_name()} to {machine}, so "
            f"{machine}'s task lists were not read.\n"
            f"Run this program on {machine} to read them.\n"
            f"Pass --machine {this_machine_name()} to ask for this machine "
            f"alone.")


def ssh_failed_notice(machine, what_ssh_said):
    """Said when ssh itself could not reach the machine."""
    return (f"{machine} could not be read (ssh exited "
            f"{SSH_ITSELF_FAILED_EXIT}): "
            f"{what_ssh_said or 'ssh said nothing'}.\n"
            f"Check {machine} is up and this machine's key reaches it: ssh "
            f"{SSH_TARGET_BY_MACHINE[machine]} true\n"
            f"Pass --machine {this_machine_name()} to read this machine "
            f"alone.")


def tar_failed_notice(machine, exit_code, what_tar_said):
    """Said when ssh connected and the archiving command failed."""
    return (f"{machine}'s task store was not archived (tar exited "
            f"{exit_code}): {what_tar_said or 'tar said nothing'}.\n"
            f"Check the store is there: ssh "
            f"{SSH_TARGET_BY_MACHINE[machine]} ls ~/{STORE_UNDER_HOME}\n"
            f"Pass --machine {this_machine_name()} to read this machine "
            f"alone.")


def archive_unreadable_notice(machine, detail):
    """Said when what arrived over ssh is not a readable archive."""
    return (f"{machine}'s task store did not arrive as a readable archive: "
            f"{detail}.\n"
            f"Run the read again; if it says this twice, read the store on "
            f"{machine} itself.")


def fetch_task_store_archive(machine, runner):
    """One machine's whole task store as one tar, or why it did not come.

    Returns (archive bytes or None, problems). One tar rather than a file by
    file copy, and read here rather than there, so nothing depends on the
    other machine's Python.
    """
    completed = runner([
        "ssh",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=10",
        SSH_TARGET_BY_MACHINE[machine],
        'tar -C "$HOME/%s" -cf - .' % STORE_UNDER_HOME,
    ])
    what_it_said = (completed.stderr or b"").decode("utf-8", "replace").strip()
    if completed.returncode == SSH_ITSELF_FAILED_EXIT:
        return None, [ssh_failed_notice(machine, what_it_said)]
    if completed.returncode not in (0, TAR_WROTE_EVERYTHING_BUT_WARNED_EXIT):
        return None, [tar_failed_notice(machine, completed.returncode,
                                        what_it_said)]
    return completed.stdout, []


def stays_inside(name):
    """Whether a name from an archive names something in the directory.

    The temporary directory is the only thing this program writes, and this
    keeps that true of an archive whose member names are not what was asked
    for.
    """
    return name not in ("", ".", "..") and os.sep not in name


def unpack_task_store_archive(archive_bytes, into_directory, machine):
    """Write a fetched store's task files into a directory of our own.

    Returns (store directory, problems), or (None, problems) when the
    archive could not be read whole: then the machine was not read, and its
    caller must say so rather than list the part that arrived. Unpacked
    rather than parsed in place so that every task list, on either machine,
    is a directory the one reader below reads. Directories are made even
    when they hold no task file, so a seat whose list is empty is still
    shown as a seat. Every file in a list's directory is written, .lock and
    .highwatermark included: what counts as a task file is read_tasks's
    *.json glob and is decided there alone, for both machines.

    A stream cut short, which ssh can deliver with exit 0 or 1, is caught
    both ways it arrives. Cut inside a member, tarfile raises ReadError while
    the members are read, not when the archive is opened, so the whole read
    is inside the try (merge-lane-2's finding on pull request [Fold every
    seat, on both machines, into the one task
    viewer](https://github.com/nedschorus/nedschorus/pull/646)). Cut at a
    member boundary, tarfile raises nothing and returns fewer files, so the
    stream must also end in tar's end-of-archive marker, two zero blocks,
    which `tar -cf -` always writes. Measured 2026-09-22 on a three-file
    archive cut every 97 bytes: 93 cuts raised and 113 returned clean with
    files missing.
    """
    store = into_directory / machine
    store.mkdir(parents=True, exist_ok=True)
    if not archive_bytes.endswith(END_OF_TAR_ARCHIVE):
        return None, [archive_unreadable_notice(
            machine, "it ended before tar's end-of-archive marker")]
    try:
        with tarfile.open(fileobj=io.BytesIO(archive_bytes),
                          mode="r:") as archive:
            problems = unpack_task_store_members(archive, store, machine)
    except tarfile.TarError as tar_failure:
        return None, [archive_unreadable_notice(machine, tar_failure)]
    return store, problems


def unpack_task_store_members(archive, store, machine):
    """Write an opened archive's task files under store; the problems met."""
    problems = []
    for member in archive.getmembers():
        parts = Path(member.name).parts
        if not all(stays_inside(part) for part in parts):
            continue
        if member.isdir() and len(parts) == 1:
            (store / parts[0]).mkdir(exist_ok=True)
            continue
        if not member.isfile() or len(parts) != 2:
            continue
        extracted = archive.extractfile(member)
        if extracted is None:
            problems.append(
                f"{member.name} on {machine} could not be read out of "
                f"the archive.\n"
                f"Read that file on {machine} itself if the task you "
                f"want is in it.")
            continue
        (store / parts[0]).mkdir(exist_ok=True)
        (store / parts[0] / parts[1]).write_bytes(extracted.read())
    return problems


def read_task_lists(machines, store, scratch, runner):
    """Every task list on the machines asked for, and what was not read.

    Returns (locations, problems, machines actually read). A machine is
    counted as read when its store was reached, empty or not; one that was
    not appears in problems and nowhere else, so no caller can mistake a
    short answer for the whole.
    """
    locations, problems, machines_read = [], [], []
    for machine in machines:
        if machine == this_machine_name():
            if not store.is_dir():
                problems.append(no_store_notice(machine, store))
                continue
            machines_read.append(machine)
            locations.extend(task_lists_in_store(store, machine))
            continue
        if machine not in SSH_TARGET_BY_MACHINE:
            problems.append(no_route_notice(machine))
            continue
        archive_bytes, fetch_problems = fetch_task_store_archive(
            machine, runner)
        problems.extend(fetch_problems)
        if archive_bytes is None:
            continue
        unpacked, unpack_problems = unpack_task_store_archive(
            archive_bytes, scratch, machine)
        problems.extend(unpack_problems)
        if unpacked is None:
            continue
        machines_read.append(machine)
        locations.extend(task_lists_in_store(unpacked, machine))
    return sorted(locations), problems, machines_read


def task_lists_or_refuse(locations, machines):
    """The task lists found, or the refusal that says none were.

    Defined once and called by every entry path. It was written out twice
    once before, and mutation testing showed only one copy was pinned by a
    case: emptying the other one left every case green. What could not be
    read is added to this and to every other refusal in one place, in main.
    """
    if locations:
        return locations
    raise SystemExit(
        f"No task lists on the machines read: "
        f"{', '.join(machine_shown(m) for m in machines)}.")


def seat_of(list_id):
    """The seat name inside a list id, for display.

    nedschorus-merge-lane-tasks -> merge-lane. A list id that does not carry
    the project's shape is shown whole rather than guessed at.
    """
    name = list_id
    if name.startswith("nedschorus-"):
        name = name[len("nedschorus-"):]
    if name.endswith("-tasks"):
        name = name[: -len("-tasks")]
    return name or list_id


def where_shown(location):
    """One task list named as a reader would cite it: seat, then machine."""
    return f"{seat_of(location.directory.name)} on {location.machine}"


def resolve_task_list(locations, wanted):
    """The one task list `wanted` names, or an explanatory SystemExit.

    `wanted` may be a seat name (cold-read-research) or a whole list id
    (nedschorus-cold-read-research-tasks). Matching an exact directory first
    means a seat whose name happens to sit inside another's cannot be
    resolved by accident. A name held by two machines is refused rather than
    picked between: answering with one machine's tasks for a seat that runs
    on both is the silent-wrong-answer shape this program exists to avoid.
    """
    seats_here = ", ".join(where_shown(each) for each in locations)
    if wanted is None:
        raise SystemExit(
            f"Name a seat with --seat, or set {LIST_ID_VARIABLE}.\n"
            f"Pass --every-task-list for every seat at once.\n"
            f"Seats with a task list: {seats_here}")
    matches = [each for each in locations
               if each.directory.name == wanted]
    if not matches:
        matches = [each for each in locations
                   if seat_of(each.directory.name) == wanted]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise SystemExit(
            f"No task list for '{wanted}'.\n"
            f"Seats with a task list: {seats_here}")
    named = ", ".join(f"{each.directory.name} on {each.machine}"
                      for each in matches)
    raise SystemExit(
        f"'{wanted}' names more than one task list: {named}.\n"
        f"Pass --machine to read one machine, or the whole list id instead "
        f"of the seat name.")


def sort_key(task):
    """Numeric where the id is a number, so 9 comes before 10."""
    identifier = str(task.get("id", ""))
    return (0, int(identifier)) if identifier.isdigit() else (1, identifier)


def read_tasks(directory):
    """Every task in one list, in id order.

    A file that is not readable JSON is reported rather than skipped: a
    silently dropped task is a task the reader will never learn exists. The
    second return value carries those names to whichever entry path called;
    each one hands them to unreadable_files_notice below, so the reporting
    is one behaviour rather than four.

    The text is decoded as UTF-8 by name, not by whatever locale the run
    inherits, and a file cut off in the middle of a multibyte character is
    caught here: UnicodeDecodeError is a ValueError. A reviewer of the
    superseded second viewer reproduced that abort with a truncated em dash,
    2026-09-22.
    """
    tasks, unreadable = [], []
    for path in sorted(directory.glob("*.json")):
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            unreadable.append(path.name)
            continue
        if isinstance(loaded, dict):
            loaded.setdefault("id", path.stem)
            tasks.append(loaded)
        else:
            unreadable.append(path.name)
    return sorted(tasks, key=sort_key), unreadable


def unreadable_files_notice(unreadable):
    """The lines that name the files this run could not read, or "".

    Written once and printed by EVERY entry path -- the listing, --task,
    --seats and --every-task-list -- because a property this file holds on
    one path only is the defect it has now produced twice. The first time,
    the wrong-machine refusal was written out twice and only the --seats
    copy was pinned by a case, so emptying the other left every case green;
    that is why task_lists_or_refuse above exists. The second time was this
    notice: read_tasks collected an unreadable file from the start and only
    the listing said so, so `--seat <seat> --task <id>` -- the invocation a
    citation-follower uses -- answered "No task <id>" for a task whose file
    was sitting on disk, and --seats printed a total that silently left it
    out. Found by the reviewer of pull request [seat-task-list-read: a task
    can be cited and opened like the other
    ID-types](https://github.com/nedschorus/nedschorus/pull/607),
    2026-09-21.

    The file is named and nothing more. This program does not parse, guess
    at or repair it: it is read-only by charter, and a repaired guess is a
    wrong task reported as a right one.
    """
    if not unreadable:
        return ""
    return (f"These files could not be read and are left out of this "
            f"answer: {', '.join(unreadable)}.\n"
            f"Open an unreadable file yourself if the task you want is in "
            f"it.")


def matches_status(task, wanted_open_only):
    if not wanted_open_only:
        return True
    return task.get("status") != "completed"


def completed_hidden_note(show_all):
    """What a count line says about the tasks it is not showing."""
    if show_all:
        return ""
    return " (completed hidden; --all shows them)"


def format_line(task):
    return (f"{str(task.get('id', '?')):>4}  "
            f"{str(task.get('status', '?')):<11}  "
            f"{task.get('subject', '(no subject)')}")


def format_task(task, location):
    """One task in full, headed by the citation a reader should write."""
    lines = [
        f"task {task.get('id', '?')} — {task.get('subject', '(no subject)')}",
        f"  seat:    {seat_of(location.directory.name)}",
        f"  machine: {location.machine}",
        f"  status:  {task.get('status', '?')}",
    ]
    for field, label in (("owner", "owner"), ("blocks", "blocks"),
                         ("blockedBy", "blocked by")):
        value = task.get(field)
        if value:
            shown = ", ".join(str(item) for item in value) if isinstance(
                value, list) else str(value)
            lines.append(f"  {label + ':':<9}{shown}")
    description = (task.get("description") or "").rstrip()
    if description:
        lines.append("")
        lines.extend("  " + line if line else "" for line in
                     description.splitlines())
    return "\n".join(lines)


def print_tasks(tasks, location, in_full):
    """The tasks of one list, one line each or each one in full."""
    for task in tasks:
        if in_full:
            print(format_task(task, location))
            print()
        else:
            print(format_line(task))


def machines_read_line(machines_read):
    """The line that says which machines this answer covers.

    Printed by every entry path, so no answer here can be taken for the
    whole fleet when it is one machine's half of it.
    """
    if not machines_read:
        return "Machines read: none."
    return (f"Machines read: "
            f"{', '.join(machine_shown(m) for m in machines_read)}.")


def print_problems(problems):
    """The block that says the answer above is short, and of what."""
    if not problems:
        return
    print()
    print("This answer is incomplete; what follows was not read.")
    for problem in problems:
        print(problem)


def report_seats(locations):
    """One line per task list: its seat, machine and counts."""
    unreadable_seen = False
    for location in locations:
        tasks, unreadable = read_tasks(location.directory)
        open_count = sum(1 for task in tasks
                         if task.get("status") != "completed")
        print(f"{seat_of(location.directory.name):<26}"
              f"{location.machine:<9}{open_count:>4} open  "
              f"{len(tasks):>4} total   {location.directory.name}")
        notice = unreadable_files_notice(unreadable)
        if notice:
            unreadable_seen = True
            print(notice)
    return unreadable_seen


def report_every_task_list(locations, arguments):
    """Every task list, grouped by machine and seat."""
    unreadable_seen = False
    shown_total, read_total = 0, 0
    for location in locations:
        tasks, unreadable = read_tasks(location.directory)
        shown = [task for task in tasks
                 if matches_status(task, not arguments.all)]
        shown_total += len(shown)
        read_total += len(tasks)
        print()
        print(f"{seat_of(location.directory.name)} on {location.machine}"
              f"  —  {len(shown)} of {len(tasks)} task(s)")
        print("-" * 70)
        print_tasks(shown, location, arguments.in_full)
        notice = unreadable_files_notice(unreadable)
        if notice:
            unreadable_seen = True
            print(notice)
    print()
    print(f"{shown_total} shown of {read_total} in {len(locations)} task "
          f"list(s){completed_hidden_note(arguments.all)}")
    return unreadable_seen


def report_one_task_list(location, arguments):
    """One seat's list, or one task of it in full."""
    tasks, unreadable = read_tasks(location.directory)
    notice = unreadable_files_notice(unreadable)

    if arguments.task:
        for task in tasks:
            if str(task.get("id")) == str(arguments.task):
                print(format_task(task, location))
                if notice:
                    print(notice)
                return bool(notice)
        refusal = [f"No task {arguments.task} among the readable tasks in "
                   f"{where_shown(location)}."]
        if notice:
            refusal.append(notice)
        refusal.append(f"Run without --task to see the {len(tasks)} readable "
                       f"task(s) this seat has.")
        raise SystemExit("\n".join(refusal))

    shown = [task for task in tasks
             if matches_status(task, not arguments.all)]
    print_tasks(shown, location, arguments.in_full)
    print()
    print(f"{len(shown)} shown of {len(tasks)} in {where_shown(location)}"
          f"{completed_hidden_note(arguments.all)}")
    if notice:
        print(notice)
    return bool(notice)


def run_one_command(command):
    return subprocess.run(command, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE)


def machines_to_read(arguments):
    """Which machines this run reads.

    Both by default, so a seat that runs on the other machine is found
    rather than denied. A named --store is one machine's store, so it reads
    this machine alone unless --machine says otherwise; that is what keeps a
    run against a store built for a test from reaching for ssh.
    """
    if arguments.machine in MACHINE_NAMES:
        return (arguments.machine,)
    if arguments.machine is None and arguments.store is not None:
        return (this_machine_name(),)
    return MACHINE_NAMES


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        description="Read the agent-seats' task lists, on both machines. "
                    "Reads only.")
    parser.add_argument("--seat", help="seat name or whole task list id")
    parser.add_argument("--task", help="show one task in full, by its id")
    parser.add_argument("--seats", action="store_true",
                        help="one line per task list: seat, machine, counts")
    parser.add_argument("--every-task-list", action="store_true",
                        help="every seat's tasks, grouped by machine and "
                             "seat")
    parser.add_argument("--in-full", action="store_true",
                        help="print each listed task in full, as --task does")
    parser.add_argument("--all", action="store_true",
                        help="include completed tasks")
    parser.add_argument("--machine", choices=("both",) + MACHINE_NAMES,
                        default=None,
                        help="which machine to read (default: both, or this "
                             "machine alone when --store is given)")
    parser.add_argument("--store", type=Path, default=None,
                        help=f"this machine's task store (default "
                             f"{DEFAULT_STORE}); reads this machine alone "
                             f"unless --machine says otherwise")
    return parser.parse_args(argv)


def refuse_contradictory_arguments(arguments):
    """The combinations that would have to guess at what was meant."""
    if arguments.every_task_list and arguments.seat:
        raise SystemExit(
            "Pass --seat for one seat, or --every-task-list for all of "
            "them, not both.")
    if arguments.every_task_list and arguments.task:
        raise SystemExit(
            "Name the seat the task is on with --seat, and drop "
            "--every-task-list.")


def main(argv=None, runner=None):
    arguments = parse_arguments(argv)
    refuse_contradictory_arguments(arguments)
    runner = run_one_command if runner is None else runner
    machines = machines_to_read(arguments)
    store = DEFAULT_STORE if arguments.store is None else arguments.store

    with tempfile.TemporaryDirectory(
            prefix="seat-task-list-read-") as scratch:
        locations, problems, machines_read = read_task_lists(
            machines, store, Path(scratch), runner)
        try:
            task_lists = task_lists_or_refuse(locations, machines)

            if arguments.seats:
                unreadable_seen = report_seats(task_lists)
            elif arguments.every_task_list:
                unreadable_seen = report_every_task_list(
                    task_lists, arguments)
            else:
                wanted = (arguments.seat
                          or os.environ.get(LIST_ID_VARIABLE) or None)
                location = resolve_task_list(task_lists, wanted)
                unreadable_seen = report_one_task_list(location, arguments)
        except SystemExit as refusal:
            # Every refusal carries what could not be read, in one place: a
            # seat missing from an answer because its machine was never
            # reached must not read as a seat that does not exist.
            raise SystemExit("\n".join([str(refusal.code)] + problems))

        print(machines_read_line(machines_read))
        print_problems(problems)

    if problems or unreadable_seen:
        return EXIT_SOMETHING_COULD_NOT_BE_READ
    return EXIT_EVERYTHING_ASKED_FOR_WAS_READ


if __name__ == "__main__":
    sys.exit(main())
