#!/usr/bin/env python3
"""Read an agent-seat's task list, so a task can be cited and opened like the
other ID-types.

Built at the user's word, 2026-09-21, during the walk
open-questions-concerns-and-recommendations-2026-09-21: "lets build the task
viewer tool now." It comes out of that walk's item 1, which settled how the
citation rule's six ID-types are written. Five of them -- pull request, GitHub
issue, commit, session, seat -- can be cited so a reader can open the thing.
A task could not: its words sit in a per-seat JSON store the reader has no
way to reach, so "task 85" was the one citation that could only ever be a
number.

THE STORE, measured 2026-09-21. One directory per agent-seat beneath
~/.claude/tasks/, named by that seat's CLAUDE_CODE_TASK_LIST_ID, which on
this project reads nedschorus-<seat>-tasks. Inside it one JSON file per task,
named <id>.json, carrying id, subject, description, status, activeForm,
owner, blocks and blockedBy.

WHAT THIS DOES NOT CHANGE. A task list is seat-local working state that does
not outlive the worktree (user-ruled 2026-09-11, queued at
docs/nedschorus-wiki/queue/task-list-is-not-durable-state-draft.md: "Tasks
only survive as long as the worktree - these should be incorporated in GHIs
or their paired design files. Or perhaps in a queue."). Readable is not
durable. Anything carrying pending state that must outlive the seat still
belongs in a GHI, its paired document, or a queue file. This program makes
working state legible to whoever was handed a citation; it is not a reason to
keep state here.

ONE MACHINE. The store lives on the machine the seat runs on, which for this
project is the user's Mac. ned-box has no copy. A missing store therefore
means "not this machine", not "no tasks", and the two are reported
differently on purpose: an empty list reads as an answer, and answering
"no tasks" on the wrong machine is the silent-wrong-answer shape this fleet
keeps finding.

READ ONLY. Nothing here writes, moves or deletes. The harness owns the store;
an agent changes its own tasks through the task tools.
"""

import argparse
import json
import os
import sys
from pathlib import Path

DEFAULT_STORE = Path.home() / ".claude" / "tasks"
LIST_ID_VARIABLE = "CLAUDE_CODE_TASK_LIST_ID"


def task_list_directories(store):
    """Every task list in the store, by directory name, sorted."""
    if not store.is_dir():
        return []
    return sorted(path for path in store.iterdir() if path.is_dir())


def task_list_directories_or_refuse(store):
    """The store's task lists, or the refusal that says this is the wrong
    machine.

    Defined once and called by both entry paths. It was written out twice,
    and mutation testing showed only one copy was pinned by a case: emptying
    the other one left every case green.
    """
    directories = task_list_directories(store)
    if not directories:
        raise SystemExit(
            f"No task lists under {store}.\n"
            f"Run this on the machine the seat runs on; this one has no "
            f"store.")
    return directories


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


def resolve_list_directory(store, wanted):
    """The one task list `wanted` names, or an explanatory SystemExit.

    `wanted` may be a seat name (cold-read-research) or a whole list id
    (nedschorus-cold-read-research-tasks). Matching an exact directory first
    means a seat whose name happens to sit inside another's cannot be
    resolved by accident.
    """
    directories = task_list_directories_or_refuse(store)
    if wanted is None:
        raise SystemExit(
            f"Name a seat with --seat, or set {LIST_ID_VARIABLE}.\n"
            f"Seats with a task list here: "
            f"{', '.join(seat_of(d.name) for d in directories)}")
    exact = [d for d in directories if d.name == wanted]
    if exact:
        return exact[0]
    matches = [d for d in directories if seat_of(d.name) == wanted]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise SystemExit(
            f"No task list for '{wanted}'.\n"
            f"Seats with a task list here: "
            f"{', '.join(seat_of(d.name) for d in directories)}")
    raise SystemExit(
        f"'{wanted}' names more than one task list: "
        f"{', '.join(d.name for d in matches)}.\n"
        f"Pass the whole list id instead of the seat name.")


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
    is one behaviour rather than three.
    """
    tasks, unreadable = [], []
    for path in sorted(directory.glob("*.json")):
        try:
            loaded = json.loads(path.read_text())
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

    Written once and printed by EVERY entry path -- the listing, --task and
    --seats -- because a property this file holds on one path only is the
    defect it has now produced twice. The first time, the wrong-machine
    refusal was written out twice and only the --seats copy was pinned by a
    case, so emptying the other left every case green; that is why
    task_list_directories_or_refuse above exists. The second time was this
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


def format_line(task):
    return (f"{str(task.get('id', '?')):>4}  "
            f"{str(task.get('status', '?')):<11}  "
            f"{task.get('subject', '(no subject)')}")


def format_task(task, list_id):
    """One task in full, headed by the citation a reader should write."""
    lines = [
        f"task {task.get('id', '?')} — {task.get('subject', '(no subject)')}",
        f"  seat:    {seat_of(list_id)}",
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


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Read an agent-seat's task list.")
    parser.add_argument("--seat", help="seat name or whole task list id")
    parser.add_argument("--task", help="show one task in full, by its id")
    parser.add_argument("--seats", action="store_true",
                        help="list the seats that have a task list here")
    parser.add_argument("--all", action="store_true",
                        help="include completed tasks")
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE,
                        help=f"task store directory (default {DEFAULT_STORE})")
    arguments = parser.parse_args(argv)

    store = arguments.store
    if arguments.seats:
        directories = task_list_directories_or_refuse(store)
        for directory in directories:
            tasks, unreadable = read_tasks(directory)
            open_count = sum(1 for task in tasks
                             if task.get("status") != "completed")
            print(f"{seat_of(directory.name):<28}{open_count:>4} open  "
                  f"{len(tasks):>4} total   {directory.name}")
            notice = unreadable_files_notice(unreadable)
            if notice:
                print(notice)
        return 0

    wanted = arguments.seat or os.environ.get(LIST_ID_VARIABLE) or None
    directory = resolve_list_directory(store, wanted)
    tasks, unreadable = read_tasks(directory)
    notice = unreadable_files_notice(unreadable)

    if arguments.task:
        for task in tasks:
            if str(task.get("id")) == str(arguments.task):
                print(format_task(task, directory.name))
                if notice:
                    print(notice)
                return 0
        refusal = [f"No task {arguments.task} among the readable tasks in "
                   f"{seat_of(directory.name)}."]
        if notice:
            refusal.append(notice)
        refusal.append(f"Run without --task to see the {len(tasks)} readable "
                       f"task(s) this seat has.")
        raise SystemExit("\n".join(refusal))

    shown = [task for task in tasks if matches_status(task, not arguments.all)]
    for task in shown:
        print(format_line(task))
    print()
    print(f"{len(shown)} shown of {len(tasks)} in {seat_of(directory.name)}"
          f"{'' if arguments.all else ' (completed hidden; --all shows them)'}")
    if notice:
        print(notice)
    return 0


if __name__ == "__main__":
    sys.exit(main())
