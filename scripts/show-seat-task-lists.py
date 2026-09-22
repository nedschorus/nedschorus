#!/usr/bin/env python3
"""Print every agent-seat's harness task list, from both machines.

WHY THIS EXISTS. The user cannot see what the fleet's seats are
holding. A seat's harness task list is where its rulings and owed
announcements survive a handoff, and until now reading one meant
attaching to that seat's terminal. Seats on ned-box could not be read
at all from the Mac. GHI "Agent-introspection research bundle" item 5
names the need: "a method for the boss to SEE and review agents'
harness task lists — until this exists the boss is blind to them."

Built by direction of the user, 2026-09-22, item 6 of the walk
ghi-write-session-open-rulings-and-concerns (minutes at
nedlern@ned-box:/home/nedlern/nedschorus-logs/walk/). He proposed the
build in place of filing a GHI first — "I'm assuming a task viewer is
pretty simple. Build now?" — on the ground that the issue describing
the work would cost more than the work.

TWO DESIGN DECISIONS, stated to him and not contradicted.

It READS ONLY. Nothing here writes, moves or deletes a task. A task is
another seat's working memory, and a viewer that can damage it is a
worse trade than no viewer.

It REFUSES RATHER THAN OMITS. A machine it cannot reach, or a task
file it cannot parse, makes it exit non-zero and say so. It never
prints a short list as though that were the whole fleet. This follows
item 1 of the same walk, where scripts/cold-read-grid.py exited 0
having produced six zero-byte reports during an authentication outage:
a program that answers success when its output is missing is the
defect being fixed there, and a viewer that quietly drops a seat is
the same shape. CLAUDE.md's standing rule about ned-box applies to the
unreachable case — the message carries what ssh said and the remedy.

THE STORE, measured on 2026-09-22 rather than assumed. One JSON file
per task at ~/.claude/tasks/nedschorus-<seat>-tasks/<id>.json, on each
machine. Across 770 task files the keys were id, subject, description,
status, blocks and blockedBy on every one, activeForm on 559, metadata
on 48 and owner on 29 — so only the first six may be relied on. The
three statuses seen were pending, in_progress and completed. The
directory also holds .lock and .highwatermark, which are the harness's
and are skipped.

Directories of seats whose sessions have ended are read like any
other. That is deliberate: a task outliving its seat is the case this
tool exists for.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path

THIS_MACHINE_NAME = "mac"
NED_BOX_MACHINE_NAME = "ned-box"
NED_BOX_SSH_TARGET = "nedlern@ned-box"

SEAT_TASK_DIRECTORY_PREFIX = "nedschorus-"
SEAT_TASK_DIRECTORY_SUFFIX = "-tasks"
TASKS_ROOT_RELATIVE_TO_HOME = Path(".claude") / "tasks"

STATUSES_SHOWN_BY_DEFAULT = ("in_progress", "pending")
EVERY_STATUS = ("in_progress", "pending", "completed")

EXIT_EVERYTHING_READ = 0
EXIT_SOMETHING_COULD_NOT_BE_READ = 1
EXIT_BAD_INVOCATION = 64

NED_BOX_UNREACHABLE_REMEDY = (
    "Check ned-box is up and on the LAN, and that this Mac's key still "
    "reaches it: ssh " + NED_BOX_SSH_TARGET + " true"
)


def seat_name_from_directory_name(directory_name):
    """Return the seat a task directory belongs to, or None.

    Only nedschorus-<seat>-tasks belongs to this project. The harness
    keeps other directories beside it and they are not ours to read.
    """
    if not directory_name.startswith(SEAT_TASK_DIRECTORY_PREFIX):
        return None
    if not directory_name.endswith(SEAT_TASK_DIRECTORY_SUFFIX):
        return None
    seat = directory_name[
        len(SEAT_TASK_DIRECTORY_PREFIX):
        -len(SEAT_TASK_DIRECTORY_SUFFIX)
    ]
    return seat or None


def task_from_json_text(text, where_it_came_from):
    """Parse one task file. Returns (task, problem); one is None.

    A task file can be read mid-write — the harness writes these while
    this tool runs, and the directory carries a .lock to prove it — so
    an unparseable file is an expected event, not a corruption. It is
    named and the run continues, and the exit code carries it.
    """
    try:
        parsed = json.loads(text)
    except ValueError as parse_failure:
        return None, "%s could not be parsed: %s" % (
            where_it_came_from, parse_failure)
    if not isinstance(parsed, dict):
        return None, "%s is not a task object" % where_it_came_from
    for required_key in ("id", "subject", "status"):
        if required_key not in parsed:
            return None, "%s has no %s" % (
                where_it_came_from, required_key)
    return parsed, None


def read_seat_task_lists_on_this_mac(tasks_root):
    """Read every seat's tasks from a directory on this machine."""
    found_tasks = []
    problems = []
    if not tasks_root.is_dir():
        problems.append(
            "No task store on this Mac at %s" % tasks_root)
        return found_tasks, problems
    for seat_directory in sorted(tasks_root.iterdir()):
        if not seat_directory.is_dir():
            continue
        seat = seat_name_from_directory_name(seat_directory.name)
        if seat is None:
            continue
        for task_file in sorted(seat_directory.iterdir()):
            if task_file.suffix != ".json":
                continue
            where = "%s on the Mac" % task_file
            try:
                text = task_file.read_text(encoding="utf-8")
            except OSError as read_failure:
                problems.append(
                    "%s could not be read: %s" % (where, read_failure))
                continue
            task, problem = task_from_json_text(text, where)
            if problem is not None:
                problems.append(problem)
                continue
            task["seat"] = seat
            task["machine"] = THIS_MACHINE_NAME
            found_tasks.append(task)
    return found_tasks, problems


def ned_box_task_store_as_tar(runner):
    """Fetch ned-box's whole task store as one tar archive.

    One tar over ssh rather than a file-by-file copy, and read here
    with the standard library, so nothing depends on which Python
    ned-box has. Its Python is 3.14 and this Mac's system one is 3.9.6;
    a remote script would have to work under both.
    """
    completed = runner([
        "ssh",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=10",
        NED_BOX_SSH_TARGET,
        'tar -C "$HOME/%s" -cf - .' % TASKS_ROOT_RELATIVE_TO_HOME,
    ])
    return completed


def read_seat_task_lists_on_ned_box(runner):
    """Read every seat's tasks from ned-box, over ssh."""
    found_tasks = []
    problems = []
    completed = ned_box_task_store_as_tar(runner)
    if completed.returncode != 0:
        what_ssh_said = (completed.stderr or b"").decode(
            "utf-8", "replace").strip()
        problems.append(
            "ned-box could not be read (ssh exited %d): %s\n  Remedy: %s"
            % (completed.returncode, what_ssh_said or "no message",
               NED_BOX_UNREACHABLE_REMEDY))
        return found_tasks, problems
    try:
        archive = tarfile.open(
            fileobj=io.BytesIO(completed.stdout), mode="r:")
    except tarfile.TarError as tar_failure:
        problems.append(
            "ned-box's task store did not arrive as a readable "
            "archive: %s\n  Remedy: %s"
            % (tar_failure, NED_BOX_UNREACHABLE_REMEDY))
        return found_tasks, problems
    with archive:
        for member in sorted(archive.getmembers(),
                             key=lambda each: each.name):
            if not member.isfile():
                continue
            member_path = Path(member.name)
            if member_path.suffix != ".json":
                continue
            if len(member_path.parts) < 2:
                continue
            seat = seat_name_from_directory_name(member_path.parts[-2])
            if seat is None:
                continue
            where = "%s on ned-box" % member.name
            extracted = archive.extractfile(member)
            if extracted is None:
                problems.append("%s could not be read" % where)
                continue
            text = extracted.read().decode("utf-8", "replace")
            task, problem = task_from_json_text(text, where)
            if problem is not None:
                problems.append(problem)
                continue
            task["seat"] = seat
            task["machine"] = NED_BOX_MACHINE_NAME
            found_tasks.append(task)
    return found_tasks, problems


def run_a_command(command):
    return subprocess.run(command, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE)


def task_sort_key(task):
    status_order = {"in_progress": 0, "pending": 1, "completed": 2}
    try:
        numeric_id = int(task.get("id", "0"))
    except (TypeError, ValueError):
        numeric_id = 0
    return (status_order.get(task.get("status"), 3), numeric_id)


def report_lines(tasks, problems, statuses_to_show, show_descriptions,
                 only_this_seat):
    """Build the report. Returns a list of lines."""
    lines = []
    shown = [
        task for task in tasks
        if task.get("status") in statuses_to_show
        and (only_this_seat is None or task.get("seat") == only_this_seat)
    ]
    by_machine_and_seat = {}
    for task in shown:
        by_machine_and_seat.setdefault(
            (task["machine"], task["seat"]), []).append(task)
    for machine, seat in sorted(by_machine_and_seat):
        seat_tasks = sorted(by_machine_and_seat[(machine, seat)],
                            key=task_sort_key)
        lines.append("")
        lines.append("%s  (%s)  %d task(s)"
                     % (seat, machine, len(seat_tasks)))
        lines.append("-" * 70)
        for task in seat_tasks:
            lines.append("  [%s] %s  %s"
                         % (task.get("status"), task.get("id"),
                            task.get("subject")))
            owner = task.get("owner")
            if owner:
                lines.append("        owner: %s" % owner)
            blocked_by = task.get("blockedBy") or []
            if blocked_by:
                lines.append("        blocked by: %s"
                             % ", ".join(str(each) for each in blocked_by))
            if show_descriptions:
                description = (task.get("description") or "").rstrip()
                for description_line in description.split("\n"):
                    lines.append("        | %s" % description_line)
                lines.append("")
    lines.append("")
    lines.append("%d task(s) shown, from %d seat(s), of %d read."
                 % (len(shown), len(by_machine_and_seat), len(tasks)))
    if problems:
        lines.append("")
        lines.append("COULD NOT BE READ — this list is incomplete:")
        for problem in problems:
            lines.append("  %s" % problem)
    return lines


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        description="Print every agent-seat's harness task list, from "
                    "both machines. Reads only.")
    parser.add_argument(
        "--all", action="store_true",
        help="include completed tasks (default: in_progress and "
             "pending only)")
    parser.add_argument(
        "--descriptions", action="store_true",
        help="print each task's full description")
    parser.add_argument(
        "--seat", default=None,
        help="only this seat's tasks")
    parser.add_argument(
        "--machine", choices=("both", THIS_MACHINE_NAME,
                              NED_BOX_MACHINE_NAME),
        default="both",
        help="which machine to read (default: both)")
    return parser.parse_args(argv)


def main(argv=None, runner=None, tasks_root=None, out=None):
    arguments = parse_arguments(
        sys.argv[1:] if argv is None else argv)
    runner = run_a_command if runner is None else runner
    if tasks_root is None:
        tasks_root = Path(
            os.path.expanduser("~")) / TASKS_ROOT_RELATIVE_TO_HOME
    out = sys.stdout if out is None else out

    tasks = []
    problems = []
    if arguments.machine in ("both", THIS_MACHINE_NAME):
        mac_tasks, mac_problems = read_seat_task_lists_on_this_mac(
            tasks_root)
        tasks.extend(mac_tasks)
        problems.extend(mac_problems)
    if arguments.machine in ("both", NED_BOX_MACHINE_NAME):
        box_tasks, box_problems = read_seat_task_lists_on_ned_box(runner)
        tasks.extend(box_tasks)
        problems.extend(box_problems)

    statuses_to_show = (
        EVERY_STATUS if arguments.all else STATUSES_SHOWN_BY_DEFAULT)
    for line in report_lines(tasks, problems, statuses_to_show,
                             arguments.descriptions, arguments.seat):
        print(line, file=out)
    if problems:
        return EXIT_SOMETHING_COULD_NOT_BE_READ
    return EXIT_EVERYTHING_READ


if __name__ == "__main__":
    sys.exit(main())
