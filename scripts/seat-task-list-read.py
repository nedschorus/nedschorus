#!/usr/bin/env python3
"""Read and cite seat task lists from both machines without modifying the stores.

The only configured ssh route is Mac to ned-box; on ned-box the Mac is
reported unread without failing the run. A requested store that cannot be
read is a failure, not an empty task list."""

import argparse
import importlib.util
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

_records_reader_spec = importlib.util.spec_from_file_location(
    "agent_seat_state_records_reader", Path(__file__).resolve().parent.parent
    / "nc-systems" / "handoff" / "agent-seat-state-records-reader.py")
records_reader = importlib.util.module_from_spec(_records_reader_spec)
_records_reader_spec.loader.exec_module(records_reader)

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

TaskListLocation = namedtuple("TaskListLocation", "machine directory")


def this_machine_name():
    hostname = socket.gethostname().split(".")[0]
    if hostname == NED_BOX_HOSTNAME:
        return MACHINE_NAME_NED_BOX
    return MACHINE_NAME_MAC


def machine_shown(machine):
    """Return a display name marking the machine running this process."""
    if machine == this_machine_name():
        return f"{machine} (this machine)"
    return machine


def task_list_directories(store):
    if not store.is_dir():
        return []
    return sorted(path for path in store.iterdir() if path.is_dir())


def task_lists_in_store(store, machine):
    """Return task lists paired with their source machine."""
    return [TaskListLocation(machine, directory)
            for directory in task_list_directories(store)]


def no_store_notice(machine, store):
    return (f"No task store on {machine} at {store}.\n"
            f"Run this on the machine the seat runs on; this one has no "
            f"store.")


def no_route_notice(machine):
    return (f"No ssh route from {this_machine_name()} to {machine}, so "
            f"{machine}'s task lists were not read.\n"
            f"Run this program on {machine} to read them.\n"
            f"Pass --machine {this_machine_name()} to ask for this machine "
            f"alone.")


def ssh_failed_notice(machine, what_ssh_said):
    return (f"{machine} could not be read (ssh exited "
            f"{SSH_ITSELF_FAILED_EXIT}): "
            f"{what_ssh_said or 'ssh said nothing'}.\n"
            f"Check {machine} is up and this machine's key reaches it: ssh "
            f"{SSH_TARGET_BY_MACHINE[machine]} true\n"
            f"Pass --machine {this_machine_name()} to read this machine "
            f"alone.")


def tar_failed_notice(machine, exit_code, what_tar_said):
    return (f"{machine}'s task store was not archived (tar exited "
            f"{exit_code}): {what_tar_said or 'tar said nothing'}.\n"
            f"Check the store is there: ssh "
            f"{SSH_TARGET_BY_MACHINE[machine]} ls ~/{STORE_UNDER_HOME}\n"
            f"Pass --machine {this_machine_name()} to read this machine "
            f"alone.")


def archive_unreadable_notice(machine, detail):
    return (f"{machine}'s task store did not arrive as a readable archive: "
            f"{detail}.\n"
            f"Run the read again; if it says this twice, read the store on "
            f"{machine} itself.")


def fetch_task_store_archive(machine, runner):
    """Return (archive_bytes_or_None, problems) for one machine’s task store."""
    # One archive keeps parsing local and independent of the remote Python version.
    # tar exit 1 can mean a complete archive changed while reading; exit 2 is fatal, 255 is ssh failure.
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
    """Return whether an archive member stays within the destination directory."""
    return name not in ("", ".", "..") and os.sep not in name


def unpack_task_store_archive(archive_bytes, into_directory, machine):
    """Return (store_directory, problems), or (None, problems) for an incomplete archive."""
    # tarfile can accept an archive cut at a member boundary; require its two trailing zero blocks.
    # ReadError may occur during iteration, so the whole read must remain inside the try.
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
    """Write archive members under store and return encountered problems."""
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
    """Return (locations, problems, machines_read, unrouted) for the requested machines."""
    locations, problems, machines_read, unrouted = [], [], [], []
    for machine in machines:
        if machine == this_machine_name():
            if not store.is_dir():
                problems.append(no_store_notice(machine, store))
                continue
            machines_read.append(machine)
            locations.extend(task_lists_in_store(store, machine))
            continue
        if machine not in SSH_TARGET_BY_MACHINE:
            unrouted.append(no_route_notice(machine))
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
    return sorted(locations), problems, machines_read, unrouted


def task_lists_or_refuse(locations, machines_read):
    """Return task lists, or raise a refusal naming the machines actually read."""
    if locations:
        return locations
    shown = ", ".join(machine_shown(m) for m in machines_read) or "none"
    raise SystemExit(f"No task lists on the machines read: {shown}.")


seat_of = records_reader.seat_of


def where_shown(location):
    """Return a task list citation: seat, then machine."""
    return f"{seat_of(location.directory.name)} on {location.machine}"


def resolve_task_list(locations, wanted):
    """Return the uniquely matching task list, or raise an explanatory SystemExit."""
    # Prefer exact IDs to avoid accidental substring matches; a name on two machines is ambiguous.
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
    """Sort numeric IDs numerically, so 9 precedes 10."""
    identifier = str(task.get("id", ""))
    return (0, int(identifier)) if identifier.isdigit() else (1, identifier)


def read_tasks(directory):
    """Return (tasks_in_id_order, unreadable_files) for one list."""
    # UnicodeDecodeError is a ValueError, including a truncated multibyte character.
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
    """Return lines naming unreadable files, or an empty string."""
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
    if show_all:
        return ""
    return " (completed hidden; --all shows them)"


def format_line(task):
    return (f"{str(task.get('id', '?')):>4}  "
            f"{str(task.get('status', '?')):<11}  "
            f"{task.get('subject', '(no subject)')}")


def format_task(task, location):
    """Return a full task headed by its citation."""
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
    for task in tasks:
        if in_full:
            print(format_task(task, location))
            print()
        else:
            print(format_line(task))


def machines_read_line(machines_read):
    if not machines_read:
        return "Machines read: none."
    return (f"Machines read: "
            f"{', '.join(machine_shown(m) for m in machines_read)}.")


def print_problems(problems):
    if not problems:
        return
    print()
    print("This answer is incomplete; what follows was not read.")
    for problem in problems:
        print(problem)


def print_unrouted(unrouted):
    # An unconfigured route limits coverage but is not a failed read.
    if not unrouted:
        return
    print()
    print("Not read, because this machine has no route to it:")
    for notice in unrouted:
        print(notice)


def report_seats(locations):
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
    # A custom store defaults to local-only so fixture reads do not initiate ssh.
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
        locations, problems, machines_read, unrouted = read_task_lists(
            machines, store, Path(scratch), runner)
        try:
            task_lists = task_lists_or_refuse(locations, machines_read)

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
            # An unread machine must not make a seat appear nonexistent.
            raise SystemExit(
                "\n".join([str(refusal.code)] + problems + unrouted))

        print(machines_read_line(machines_read))
        print_unrouted(unrouted)
        print_problems(problems)

    if problems or unreadable_seen:
        return EXIT_SOMETHING_COULD_NOT_BE_READ
    return EXIT_EVERYTHING_ASKED_FOR_WAS_READ


if __name__ == "__main__":
    sys.exit(main())
