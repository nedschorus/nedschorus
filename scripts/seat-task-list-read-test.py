#!/usr/bin/env python3
"""Cases for scripts/seat-task-list-read.py.

Every case builds its own store under a temporary directory and passes it in
with --store, so nothing here reads or writes the real ~/.claude/tasks and
nothing depends on HOME. That is deliberate: a sibling suite in this
repository was found redirecting nothing and reading the running machine's
own state, which passes everywhere and proves nothing
(merge-lane's finding on handoff-context-threshold-hook-test.py, 2026-09-21).

The property the program exists for is in `a missing store does not read as
an empty list`. Reporting "no tasks" on a machine that simply has no store is
the silent-wrong-answer shape this fleet has spent the week finding, so the
two outcomes are asserted to differ rather than merely to be non-empty.

A property this program holds must be pinned on EVERY entry path that can
meet it, one case per path, never on one path with the siblings trusted.
That is not a preference: both defects this file has had were the same shape.
The wrong-machine refusal was written out twice and only the --seats copy was
pinned, so emptying the other left every case green. Then the unreadable-file
notice was printed by the listing alone, so `--task <id>` denied a task whose
file was on disk and --seats printed a total that silently left it out
(reviewer's finding on pull request [seat-task-list-read: a task can be cited
and opened like the other
ID-types](https://github.com/nedschorus/nedschorus/pull/607), 2026-09-21).

Several cases assert a negative -- that something is NOT reported. Each is
paired with the positive that would report it, so an assertion cannot pass
because the check it exercises is dead. A check that cannot fail is worth
nothing, and proving it can speak on the case in dispute is the standard this
project arrived at on 2026-09-21.
"""

import importlib.util
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

sys.dont_write_bytecode = True  # never run a stale copy of the program

REPO_ROOT = Path(__file__).resolve().parent.parent
PROGRAM = REPO_ROOT / "scripts" / "seat-task-list-read.py"

spec = importlib.util.spec_from_file_location("seat_task_list_read", PROGRAM)
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def build_store(root, lists):
    """lists: {list_id: [task dicts]} -> the store directory."""
    store = Path(root) / "tasks"
    for list_id, tasks in lists.items():
        directory = store / list_id
        directory.mkdir(parents=True)
        for task in tasks:
            (directory / f"{task['id']}.json").write_text(json.dumps(task))
    store.mkdir(parents=True, exist_ok=True)
    return store


def task(identifier, subject, status="pending", **extra):
    return dict(id=str(identifier), subject=subject, status=status, **extra)


def run(argv):
    """The program's stdout, plus the SystemExit message if it exited."""
    out = io.StringIO()
    try:
        with redirect_stdout(out):
            reader.main(argv)
    except SystemExit as stop:
        return out.getvalue(), str(stop.code) if stop.code else ""
    return out.getvalue(), ""


SAMPLE = {
    "nedschorus-cold-read-research-tasks": [
        task(9, "Nine comes before ten"),
        task(10, "PR \"a commit-pinned citation\" — with merge-lane"),
        task(11, "Already done", status="completed"),
    ],
    "nedschorus-merge-lane-tasks": [task(1, "Review the lane")],
}

# --- seat_of ---------------------------------------------------------------

check("seat_of strips the project's prefix and suffix",
      reader.seat_of("nedschorus-cold-read-research-tasks")
      == "cold-read-research",
      reader.seat_of("nedschorus-cold-read-research-tasks"))

check("seat_of leaves a list id of another shape whole",
      reader.seat_of("some-other-store") == "some-other-store",
      "a name that does not carry the shape must not be guessed at")

# --- resolution ------------------------------------------------------------

with tempfile.TemporaryDirectory() as root:
    store = build_store(root, SAMPLE)

    check("a seat name resolves to its list",
          reader.resolve_list_directory(store, "cold-read-research").name
          == "nedschorus-cold-read-research-tasks")

    check("a whole list id resolves to its list",
          reader.resolve_list_directory(
              store, "nedschorus-merge-lane-tasks").name
          == "nedschorus-merge-lane-tasks")

    try:
        reader.resolve_list_directory(store, "no-such-seat")
        resolved, message = True, ""
    except SystemExit as stop:
        resolved, message = False, str(stop.code)
    check("an unknown seat is refused, and the refusal names the seats there",
          not resolved and "cold-read-research" in message
          and "merge-lane" in message, message)

# --- a missing store is not an empty list ----------------------------------

with tempfile.TemporaryDirectory() as root:
    empty_store = Path(root) / "tasks"          # never created
    # Both entry paths against the SAME missing store, so the two refusals can
    # be compared for being one message rather than two that merely look alike.
    _, missing_message = run(["--seats", "--store", str(empty_store)])
    _, resolve_message = run(["--seat", "cold-read-research", "--store",
                              str(empty_store)])

with tempfile.TemporaryDirectory() as root:
    store = build_store(root, {"nedschorus-quiet-seat-tasks": []})
    present_output, present_message = run(
        ["--seat", "quiet-seat", "--store", str(store)])

check("a missing store is refused rather than answered, by --seats",
      "No task lists" in missing_message, missing_message)

# The same refusal on the OTHER entry path. Mutation testing caught this
# hole: the refusal was written out twice, only the --seats copy was pinned,
# and emptying the resolving copy left every case green.
check("a missing store is refused rather than answered, when resolving a seat",
      "No task lists" in resolve_message, resolve_message)

check("both entry paths give the same refusal, so it is written once",
      missing_message == resolve_message,
      f"--seats said {missing_message!r}, --seat said {resolve_message!r}")

check("a seat with no tasks answers, and does not borrow the missing-store "
      "message",
      present_message == "" and "0 shown of 0" in present_output
      and "No task lists" not in present_output,
      f"output={present_output!r} message={present_message!r}")

check("a missing store and an empty list do not read alike",
      missing_message != present_message, "the two must be distinguishable")

# --- ordering --------------------------------------------------------------

check("a numeric id sorts numerically, so 9 precedes 10",
      reader.sort_key({"id": "9"}) < reader.sort_key({"id": "10"}),
      "string ordering would put 10 first")

check("a non-numeric id sorts after every numeric one",
      reader.sort_key({"id": "9"}) < reader.sort_key({"id": "later"}))

# --- listing ---------------------------------------------------------------

with tempfile.TemporaryDirectory() as root:
    store = build_store(root, SAMPLE)
    default_out, _ = run(["--seat", "cold-read-research", "--store",
                          str(store)])
    all_out, _ = run(["--seat", "cold-read-research", "--store", str(store),
                      "--all"])

    check("a completed task is hidden by default",
          "Already done" not in default_out, default_out)
    check("--all shows the completed task, so the hiding above is real",
          "Already done" in all_out, all_out)
    check("the default listing shows the open tasks",
          "Nine comes before ten" in default_out
          and "commit-pinned citation" in default_out, default_out)
    check("nine is listed before ten",
          default_out.index("Nine comes") < default_out.index("commit-pinned"),
          default_out)

# --- one task --------------------------------------------------------------

with tempfile.TemporaryDirectory() as root:
    store = build_store(root, {
        "nedschorus-cold-read-research-tasks": [
            task(85, "PR with merge-lane", description="Head 6f38854.",
                 owner="cold-read-research", blockedBy=["84"]),
        ]})
    one_out, _ = run(["--seat", "cold-read-research", "--task", "85",
                      "--store", str(store)])
    _, absent_message = run(["--seat", "cold-read-research", "--task", "999",
                             "--store", str(store)])

    check("one task prints its subject, description and relations",
          "PR with merge-lane" in one_out and "Head 6f38854." in one_out
          and "blocked by" in one_out and "84" in one_out, one_out)
    check("a task id that is not there is refused, not printed empty",
          "No task 999" in absent_message, absent_message)

# --- an unreadable file is reported, never silently dropped ----------------

with tempfile.TemporaryDirectory() as root:
    store = build_store(root, {
        "nedschorus-cold-read-research-tasks": [task(1, "Readable")]})
    directory = store / "nedschorus-cold-read-research-tasks"
    (directory / "2.json").write_text("{not json")
    tasks, unreadable = reader.read_tasks(directory)

    check("a readable task is returned", [t["subject"] for t in tasks]
          == ["Readable"], tasks)
    check("an unreadable task file is named, not skipped in silence",
          unreadable == ["2.json"], unreadable)
    listed, _ = run(["--seat", "cold-read-research", "--store", str(store)])
    check("the listing tells the reader a file could not be read",
          "unreadable" in listed and "2.json" in listed, listed)

# --- every entry path surfaces an unreadable file --------------------------
#
# Three entry paths can meet one -- the listing, --task and --seats -- and
# each is pinned below on its own store-reading invocation. Pinning one and
# trusting the others is exactly how this file's two defects were built: the
# wrong-machine refusal was written twice and only the --seats copy was
# pinned, and then the unreadable-file notice was printed by the listing
# alone, so --task denied a task whose file was on disk and --seats printed a
# total that left it out without saying so.

# Taken from the function so a change of wording moves the checks with it,
# rather than leaving them asserting a string nothing prints any more.
NOTICE_FOR_TWO = reader.unreadable_files_notice(["2.json", "3.json"])
NOTICE_WORDING = reader.unreadable_files_notice(["probe.json"]).split(":")[0]

check("the notice names the files it was given, so the checks below cannot "
      "pass against an empty string",
      "2.json" in NOTICE_FOR_TWO and "3.json" in NOTICE_FOR_TWO
      and NOTICE_WORDING != "", repr(NOTICE_FOR_TWO))

with tempfile.TemporaryDirectory() as root:
    store = build_store(root, {
        "nedschorus-cold-read-research-tasks": [task(1, "Readable")],
        "nedschorus-merge-lane-tasks": [task(1, "Nothing broken here")],
    })
    broken_directory = store / "nedschorus-cold-read-research-tasks"
    (broken_directory / "2.json").write_text("{not json")   # not JSON at all
    (broken_directory / "3.json").write_text("[]")          # JSON, not a task

    _, denied = run(["--seat", "cold-read-research", "--task", "2",
                     "--store", str(store)])
    answered, _ = run(["--seat", "cold-read-research", "--task", "1",
                       "--store", str(store)])
    path_listed, _ = run(["--seat", "cold-read-research", "--store",
                          str(store)])
    path_seats, _ = run(["--seats", "--store", str(store)])

    check("a payload that is JSON but not a task is unreadable too, not a "
          "task with no fields",
          reader.read_tasks(broken_directory)[1] == ["2.json", "3.json"],
          reader.read_tasks(broken_directory)[1])

    # The reproduction from the review of this pull request: 2.json is ON
    # DISK, and --task 2 answered that no such task existed.
    check("--task: a task whose file is on disk but unreadable is not denied "
          "as absent; the refusal names the file",
          "2.json" in denied and NOTICE_FOR_TWO in denied, denied)

    check("--task: an answer that left an unreadable file out says which",
          "Readable" in answered and NOTICE_FOR_TWO in answered, answered)

    check("--seat: the listing says which files could not be read",
          NOTICE_FOR_TWO in path_listed, path_listed)

    check("--seats: the totals name the files they left out, rather than "
          "undercounting in silence",
          NOTICE_FOR_TWO in path_seats, path_seats)

    # A run that printed every unreadable name at the end would pass the
    # check above while telling the reader nothing about WHICH seat is short.
    check("--seats: the notice sits under the seat whose files they are",
          NOTICE_FOR_TWO in path_seats
          and path_seats.index("nedschorus-cold-read-research-tasks")
          < path_seats.index(NOTICE_FOR_TWO)
          < path_seats.index("nedschorus-merge-lane-tasks"), path_seats)

    check("all three entry paths carry the same notice, so it is written "
          "once and cannot drift apart again",
          NOTICE_FOR_TWO in denied and NOTICE_FOR_TWO in path_listed
          and NOTICE_FOR_TWO in path_seats,
          f"denied={denied!r} listed={path_listed!r} seats={path_seats!r}")

# The negative that pairs with the five positives above: on a store where
# every file reads, no path mentions an unreadable one. Without this, a
# program that printed the notice unconditionally would pass them all.
with tempfile.TemporaryDirectory() as root:
    clean_store = build_store(root, {
        "nedschorus-cold-read-research-tasks": [task(1, "Readable")]})
    _, clean_denied = run(["--seat", "cold-read-research", "--task", "999",
                           "--store", str(clean_store)])
    clean_answered, _ = run(["--seat", "cold-read-research", "--task", "1",
                             "--store", str(clean_store)])
    clean_listed, _ = run(["--seat", "cold-read-research", "--store",
                           str(clean_store)])
    clean_seats, _ = run(["--seats", "--store", str(clean_store)])

check("a store where every file reads says nothing about unreadable files, "
      "on any of the three paths",
      not any(NOTICE_WORDING in text for text in
              (clean_denied, clean_answered, clean_listed, clean_seats)),
      f"{clean_denied!r} {clean_answered!r} {clean_listed!r} {clean_seats!r}")

check("the notice is empty when there is nothing to name",
      reader.unreadable_files_notice([]) == "",
      repr(reader.unreadable_files_notice([])))

# --- --seats ---------------------------------------------------------------

with tempfile.TemporaryDirectory() as root:
    store = build_store(root, SAMPLE)
    seats_out, _ = run(["--seats", "--store", str(store)])
    check("--seats names every seat with a list, and counts the open ones",
          "cold-read-research" in seats_out and "merge-lane" in seats_out
          and "2 open" in seats_out, seats_out)

# --- read only -------------------------------------------------------------

with tempfile.TemporaryDirectory() as root:
    store = build_store(root, SAMPLE)
    before = {p: p.read_bytes() for p in sorted(store.rglob("*.json"))}
    run(["--seat", "cold-read-research", "--store", str(store)])
    run(["--seat", "cold-read-research", "--task", "9", "--store", str(store)])
    run(["--seats", "--store", str(store)])
    after = {p: p.read_bytes() for p in sorted(store.rglob("*.json"))}
    check("reading the store changes nothing in it", before == after,
          "the harness owns the store; this program only reads")

# --- the environment variable is a fallback, not an override ---------------

with tempfile.TemporaryDirectory() as root:
    store = build_store(root, SAMPLE)
    kept = os.environ.get(reader.LIST_ID_VARIABLE)
    os.environ[reader.LIST_ID_VARIABLE] = "nedschorus-merge-lane-tasks"
    try:
        from_env, _ = run(["--store", str(store)])
        from_flag, _ = run(["--seat", "cold-read-research", "--store",
                            str(store)])
    finally:
        if kept is None:
            os.environ.pop(reader.LIST_ID_VARIABLE, None)
        else:
            os.environ[reader.LIST_ID_VARIABLE] = kept

    check("the task list id in the environment picks the seat when none is "
          "named", "Review the lane" in from_env, from_env)
    check("--seat wins over the environment", "Nine comes before ten"
          in from_flag and "Review the lane" not in from_flag, from_flag)

print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
