#!/usr/bin/env python3
"""Cases for scripts/seat-task-list-read.py.

Every case builds its own store under a temporary directory and passes it in
with --store, or hands the program a fake ssh runner, so nothing here reads or
writes the real ~/.claude/tasks, nothing depends on HOME, and nothing reaches
ned-box. That is deliberate: a sibling suite in this repository was found
redirecting nothing and reading the running machine's own state, which passes
everywhere and proves nothing (merge-lane's finding on
handoff-context-threshold-hook-test.py, 2026-09-21).

NO CASE MAY REACH FOR SSH. The runner every case gets by default records the
command and fails, and the last case in this file asserts it was never called.
That is how the self-ssh defect is pinned: run on ned-box, the superseded
second viewer ssh'd to the machine it was already running on.

THIS SUITE RUNS ON BOTH MACHINES, under scripts/run-all-test-suites.py. So a
case that depends on which machine it is on patches socket.gethostname in the
loaded module rather than assuming the Mac, the way
scripts/cold-read-record-ship-test.py and scripts/seat-shared-file-ship-test.py
do. A case that asserted "mac" unpatched would fail on ned-box, which is the
machine most of this program's new behaviour is about.

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
There are now four such paths -- the listing, --task, --seats and
--every-task-list -- and the notice is pinned on each.

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
import subprocess
import sys
import tarfile
import tempfile
from contextlib import contextmanager, redirect_stdout
from pathlib import Path

sys.dont_write_bytecode = True  # never run a stale copy of the program

REPO_ROOT = Path(__file__).resolve().parent.parent
PROGRAM = REPO_ROOT / "scripts" / "seat-task-list-read.py"

spec = importlib.util.spec_from_file_location("seat_task_list_read", PROGRAM)
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)

failures = []
runner_calls_that_should_not_have_happened = []


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


def a_runner_that_must_not_be_called(command):
    """The runner every case gets unless it asks for another one."""
    runner_calls_that_should_not_have_happened.append(command)
    return subprocess.CompletedProcess(
        command, 255, stdout=b"",
        stderr=b"this runner must not be called")


def a_runner_returning(stdout=b"", stderr=b"", returncode=0, calls=None):
    def runner(command):
        if calls is not None:
            calls.append(command)
        return subprocess.CompletedProcess(
            command, returncode, stdout=stdout, stderr=stderr)
    return runner


def directory_member(name):
    info = tarfile.TarInfo(name)
    info.type = tarfile.DIRTYPE
    info.mode = 0o755
    return info


def a_tar_of(lists, extra_files=(), empty_lists=()):
    """A tar shaped like `tar -C ~/.claude/tasks -cf - .` writes one.

    Measured against ned-box's own archive, 2026-09-22: the root arrives as
    the member ".", each task list as "./<list id>", each task file as
    "./<list id>/<id>.json", and .lock and .highwatermark come with them.
    """
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:") as archive:
        archive.addfile(directory_member("."))
        for list_id in list(lists) + list(empty_lists):
            archive.addfile(directory_member(f"./{list_id}"))
        for list_id, tasks in lists.items():
            for one in tasks:
                payload = json.dumps(one).encode("utf-8")
                info = tarfile.TarInfo(f"./{list_id}/{one['id']}.json")
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))
        for name, payload in extra_files:
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


@contextmanager
def pretending_the_host_is(hostname):
    """Run a case as though it were on that machine.

    The only way to reach the ned-box branch of this program from either
    machine; a subprocess's hostname cannot be faked.
    """
    kept = reader.socket.gethostname
    reader.socket.gethostname = lambda: hostname
    try:
        yield
    finally:
        reader.socket.gethostname = kept


def run_and_code(argv, runner=None):
    """The program's stdout, its SystemExit message, and its exit code.

    A run that raises anything else is reported as its own kind of answer
    rather than taken as the suite's death, so a defect that aborts the
    program fails the cases that were watching for it, by name, and the
    cases after it still run.
    """
    out = io.StringIO()
    runner = a_runner_that_must_not_be_called if runner is None else runner
    try:
        with redirect_stdout(out):
            code = reader.main(argv, runner=runner)
    except SystemExit as stop:
        return out.getvalue(), str(stop.code) if stop.code else "", 1
    except Exception as raised_instead:
        return out.getvalue(), f"raised {raised_instead!r}", None
    return out.getvalue(), "", code


def run(argv, runner=None):
    """The program's stdout, plus the SystemExit message if it exited."""
    output, message, _ = run_and_code(argv, runner)
    return output, message


def locations_in(store, machine="mac"):
    """The task lists of one store, as the resolver takes them."""
    return reader.task_lists_in_store(store, machine)


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

# --- which machine this is -------------------------------------------------
#
# The blocking finding of pull request [Show every seat's task list, from both
# machines](https://github.com/nedschorus/nedschorus/pull/634), reproduced by
# both reviewers on ned-box: the machine was a constant, so on ned-box the
# tool called ned-box's store the Mac's, never read the Mac, and ssh'd to
# itself. These four cases and the four under `both machines` below are what
# a constant cannot pass.

with pretending_the_host_is("Edwards-MacBook-Air.local"):
    check("this machine is the Mac when the host is not ned-box",
          reader.this_machine_name() == reader.MACHINE_NAME_MAC,
          reader.this_machine_name())

with pretending_the_host_is("ned-box"):
    check("this machine is ned-box when the host says so",
          reader.this_machine_name() == reader.MACHINE_NAME_NED_BOX,
          reader.this_machine_name())

with pretending_the_host_is("ned-box.local"):
    check("a host with a domain after it is still ned-box",
          reader.this_machine_name() == reader.MACHINE_NAME_NED_BOX,
          reader.this_machine_name())

with tempfile.TemporaryDirectory() as root:
    store = build_store(root, SAMPLE)
    with pretending_the_host_is("ned-box"):
        on_box, _ = run(["--seats", "--store", str(store)])
    with pretending_the_host_is("Edwards-MacBook-Air.local"):
        on_mac, _ = run(["--seats", "--store", str(store)])

def machine_column(seats_output):
    """The machine named on a --seats line, which is its second column.

    Empty when there is no such line, so a run that refused where it should
    have answered fails the case by name rather than raising here.
    """
    lines = seats_output.splitlines()
    columns = lines[0].split() if lines else []
    return columns[1] if len(columns) > 1 else ""


check("the store in front of this run is labelled with the host's machine, "
      "so ned-box's seats are never shown as the Mac's",
      machine_column(on_box) == reader.MACHINE_NAME_NED_BOX
      and machine_column(on_mac) == reader.MACHINE_NAME_MAC,
      f"on ned-box={on_box!r} on the Mac={on_mac!r}")

# --- resolution ------------------------------------------------------------

with tempfile.TemporaryDirectory() as root:
    store = build_store(root, SAMPLE)

    check("a seat name resolves to its list",
          reader.resolve_task_list(
              locations_in(store), "cold-read-research").directory.name
          == "nedschorus-cold-read-research-tasks")

    check("a whole list id resolves to its list",
          reader.resolve_task_list(
              locations_in(store),
              "nedschorus-merge-lane-tasks").directory.name
          == "nedschorus-merge-lane-tasks")

    try:
        reader.resolve_task_list(locations_in(store), "no-such-seat")
        resolved, message = True, ""
    except SystemExit as stop:
        resolved, message = False, str(stop.code)
    check("an unknown seat is refused, and the refusal names the seats there",
          not resolved and "cold-read-research" in message
          and "merge-lane" in message, message)

    try:
        reader.resolve_task_list(locations_in(store), None)
        named, unnamed_message = True, ""
    except SystemExit as stop:
        named, unnamed_message = False, str(stop.code)
    check("naming no seat is refused, and the refusal says how to see every "
          "seat instead",
          not named and "--every-task-list" in unnamed_message,
          unnamed_message)

# A seat name that two machines both hold. Answering with one machine's tasks
# would be the silent wrong answer in its purest form.
with tempfile.TemporaryDirectory() as root:
    here = build_store(root, {"nedschorus-merge-lane-tasks": [task(1, "A")]})
    there = build_store(Path(root) / "other",
                        {"nedschorus-merge-lane-tasks": [task(1, "B")]})
    two_machines = (locations_in(here, "mac")
                    + locations_in(there, "ned-box"))
    try:
        reader.resolve_task_list(two_machines, "merge-lane")
        picked, ambiguous_message = True, ""
    except SystemExit as stop:
        picked, ambiguous_message = False, str(stop.code)
    check("a seat name held by both machines is refused, not picked between",
          not picked and "more than one" in ambiguous_message
          and "mac" in ambiguous_message and "ned-box" in ambiguous_message,
          ambiguous_message)
    check("and the refusal says how to choose: --machine",
          "--machine" in ambiguous_message, ambiguous_message)

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

check("the missing-store refusal says where to run instead",
      "Run this on the machine the seat runs on" in missing_message,
      missing_message)

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
    in_full_out, _ = run(["--seat", "cold-read-research", "--store",
                          str(store), "--in-full"])

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
    check("the listing says which machine the seat is on",
          "in cold-read-research on " in default_out, default_out)
    check("--in-full prints each listed task as --task does, and the "
          "one-line form does not",
          "status:  pending" in in_full_out
          and "status:  pending" not in default_out, in_full_out)

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
    check("one task names the machine it is on, so the citation can be "
          "followed to the right store",
          "machine:" in one_out, one_out)
    check("a task id that is not there is refused, not printed empty",
          "No task 999" in absent_message, absent_message)

# --- an unreadable file is reported, never silently dropped ----------------

with tempfile.TemporaryDirectory() as root:
    store = build_store(root, {
        "nedschorus-cold-read-research-tasks": [task(1, "Readable")]})
    directory = store / "nedschorus-cold-read-research-tasks"
    (directory / "2.json").write_text("{not json")
    # A file that does not parse must come back named, not raised, so the
    # raise fails these two cases by name rather than ending the suite.
    read_abort, tasks, unreadable = "", [], []
    try:
        tasks, unreadable = reader.read_tasks(directory)
    except Exception as raised_instead:
        read_abort = repr(raised_instead)

    check("a readable task is returned",
          read_abort == ""
          and [t["subject"] for t in tasks] == ["Readable"],
          f"{read_abort} {tasks}")
    check("an unreadable task file is named, not skipped in silence and not "
          "raised",
          read_abort == "" and unreadable == ["2.json"],
          f"{read_abort} {unreadable}")
    listed, _ = run(["--seat", "cold-read-research", "--store", str(store)])
    check("the listing tells the reader a file could not be read",
          "unreadable" in listed and "2.json" in listed, listed)

# A file cut off in the middle of a multibyte character. A reviewer of the
# superseded second viewer reproduced its traceback with a truncated em dash,
# 2026-09-22; here the file is named like any other unreadable one.
with tempfile.TemporaryDirectory() as root:
    store = build_store(root, {
        "nedschorus-cold-read-research-tasks": [task(1, "Readable")]})
    directory = store / "nedschorus-cold-read-research-tasks"
    (directory / "4.json").write_bytes(
        b'{"id": "4", "subject": "cut here \xe2\x80')
    # The defect this pins raises out of the program, so the raise is caught
    # here and fails the case by name instead of taking the suite with it.
    truncated_abort = ""
    truncated_out, truncated_message, truncated_code = "", "", None
    try:
        truncated_out, truncated_message, truncated_code = run_and_code(
            ["--seat", "cold-read-research", "--store", str(store)])
    except Exception as raised_instead:
        truncated_abort = repr(raised_instead)

    check("a task file cut off mid-character is named, not a traceback",
          truncated_abort == "" and "4.json" in truncated_out
          and truncated_message == "",
          f"{truncated_abort} {truncated_out!r} {truncated_message!r}")
    check("and that run exits non-zero, because the answer is short one "
          "task",
          truncated_code == reader.EXIT_SOMETHING_COULD_NOT_BE_READ,
          truncated_code)

# --- every entry path surfaces an unreadable file --------------------------
#
# Four entry paths can meet one -- the listing, --task, --seats and
# --every-task-list -- and each is pinned below on its own store-reading
# invocation. Pinning one and trusting the others is exactly how this file's
# two defects were built: the wrong-machine refusal was written twice and only
# the --seats copy was pinned, and then the unreadable-file notice was printed
# by the listing alone, so --task denied a task whose file was on disk and
# --seats printed a total that left it out without saying so.

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
    path_every, _ = run(["--every-task-list", "--store", str(store)])

    check("a payload that is JSON but not a task is unreadable too, not a "
          "task with no fields",
          reader.read_tasks(broken_directory)[1] == ["2.json", "3.json"],
          reader.read_tasks(broken_directory)[1])

    # The reproduction from the review of pull request 607: 2.json is ON
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

    check("--every-task-list: the grouped listing names them too",
          NOTICE_FOR_TWO in path_every, path_every)

    # A run that printed every unreadable name at the end would pass the
    # check above while telling the reader nothing about WHICH seat is short.
    check("--seats: the notice sits under the seat whose files they are",
          NOTICE_FOR_TWO in path_seats
          and path_seats.index("nedschorus-cold-read-research-tasks")
          < path_seats.index(NOTICE_FOR_TWO)
          < path_seats.index("nedschorus-merge-lane-tasks"), path_seats)

    check("--every-task-list: the notice sits under the seat whose files "
          "they are",
          NOTICE_FOR_TWO in path_every
          and path_every.index("cold-read-research on")
          < path_every.index(NOTICE_FOR_TWO)
          < path_every.index("merge-lane on"), path_every)

    check("all four entry paths carry the same notice, so it is written "
          "once and cannot drift apart again",
          NOTICE_FOR_TWO in denied and NOTICE_FOR_TWO in path_listed
          and NOTICE_FOR_TWO in path_seats and NOTICE_FOR_TWO in path_every,
          f"denied={denied!r} listed={path_listed!r} seats={path_seats!r} "
          f"every={path_every!r}")

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
    clean_every, clean_message, clean_code = run_and_code(
        ["--every-task-list", "--store", str(clean_store)])

check("a store where every file reads says nothing about unreadable files, "
      "on any of the four paths",
      not any(NOTICE_WORDING in text for text in
              (clean_denied, clean_answered, clean_listed, clean_seats,
               clean_every)),
      f"{clean_denied!r} {clean_answered!r} {clean_listed!r} "
      f"{clean_seats!r} {clean_every!r}")

check("a clean read of one machine exits zero",
      clean_code == reader.EXIT_EVERYTHING_ASKED_FOR_WAS_READ
      and clean_message == "", f"{clean_code!r} {clean_message!r}")

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

# --- --every-task-list -----------------------------------------------------

with tempfile.TemporaryDirectory() as root:
    store = build_store(root, SAMPLE)
    every_out, _ = run(["--every-task-list", "--store", str(store)])
    every_all_out, _ = run(["--every-task-list", "--store", str(store),
                            "--all"])
    every_full_out, _ = run(["--every-task-list", "--store", str(store),
                             "--in-full"])
    _, both_seat_message = run(["--every-task-list", "--seat", "merge-lane",
                                "--store", str(store)])
    _, both_task_message = run(["--every-task-list", "--task", "9",
                                "--store", str(store)])

    check("--every-task-list shows every seat's tasks in one answer",
          "Nine comes before ten" in every_out
          and "Review the lane" in every_out, every_out)
    check("--every-task-list groups the tasks under seat and machine",
          "cold-read-research on " in every_out
          and "merge-lane on " in every_out, every_out)
    check("--every-task-list hides completed tasks by default",
          "Already done" not in every_out, every_out)
    check("--every-task-list --all shows them, so the hiding above is real",
          "Already done" in every_all_out, every_all_out)
    check("--every-task-list counts what it showed and what it read",
          "3 shown of 4 in 2 task list(s)" in every_out, every_out)
    check("--every-task-list --in-full prints each task in full",
          "status:  pending" in every_full_out
          and "status:  pending" not in every_out, every_full_out)
    check("--every-task-list with --seat is refused rather than guessed at",
          "not both" in both_seat_message, both_seat_message)
    check("--every-task-list with --task is refused rather than guessed at",
          "--seat" in both_task_message
          and "--every-task-list" in both_task_message, both_task_message)

# --- reading the other machine over ssh ------------------------------------

BOX_LIST = "nedschorus-merge-lane-2-tasks"
BOX_TAR = a_tar_of({BOX_LIST: [task(7, "Box task"),
                               task(8, "Box task done", status="completed")]},
                   extra_files=[(f"./{BOX_LIST}/.lock", b""),
                                (f"./{BOX_LIST}/.highwatermark", b"99")],
                   empty_lists=["nedschorus-quiet-box-seat-tasks"])

with tempfile.TemporaryDirectory() as root:
    store = build_store(root, {
        "nedschorus-merge-lane-tasks": [task(1, "Mac task")]})
    ssh_calls = []
    with pretending_the_host_is("Edwards-MacBook-Air.local"):
        both_out, both_message, both_code = run_and_code(
            ["--seats", "--store", str(store), "--machine", "both"],
            runner=a_runner_returning(stdout=BOX_TAR, calls=ssh_calls))

    check("from the Mac, both machines are read into one answer",
          "merge-lane " in both_out and "merge-lane-2" in both_out
          and "ned-box" in both_out, both_out)
    check("and the run says which machines it read",
          "Machines read: mac (this machine), ned-box." in both_out,
          both_out)
    check("and that run exits zero", both_code == 0 and both_message == "",
          f"{both_code!r} {both_message!r}")
    check("the other machine is read with one ssh, carrying the project's "
          "ssh target and one tar",
          len(ssh_calls) == 1 and ssh_calls[0][0] == "ssh"
          and "nedlern@ned-box" in ssh_calls[0]
          and any("tar" in part for part in ssh_calls[0]), ssh_calls)
    check("the harness's own .lock and .highwatermark do not become tasks",
          ".lock" not in both_out and ".highwatermark" not in both_out,
          both_out)
    check("a seat on the other machine whose list is empty is still shown "
          "as a seat",
          "quiet-box-seat" in both_out, both_out)

    with pretending_the_host_is("Edwards-MacBook-Air.local"):
        box_task_out, _ = run_and_code(
            ["--seat", "merge-lane-2", "--task", "7", "--store", str(store),
             "--machine", "both"],
            runner=a_runner_returning(stdout=BOX_TAR))[:2]
    check("a task on the other machine can be cited and opened from here",
          "Box task" in box_task_out and "machine: ned-box" in box_task_out,
          box_task_out)

    with pretending_the_host_is("Edwards-MacBook-Air.local"):
        only_box_out, _ = run(
            ["--seats", "--store", str(store), "--machine", "ned-box"],
            runner=a_runner_returning(stdout=BOX_TAR))
    check("--machine ned-box reads that machine alone",
          "merge-lane-2" in only_box_out
          and "nedschorus-merge-lane-tasks" not in only_box_out,
          only_box_out)

# --- ned-box never ssh's to itself -----------------------------------------
#
# The blocking finding. On ned-box the local store IS ned-box's, and the
# machine with no route from there is the Mac.

with tempfile.TemporaryDirectory() as root:
    store = build_store(root, {BOX_LIST: [task(7, "Box task")]})
    self_calls = []
    with pretending_the_host_is("ned-box"):
        box_out, box_message, box_code = run_and_code(
            ["--seats", "--store", str(store), "--machine", "both"],
            runner=a_runner_returning(stdout=BOX_TAR, calls=self_calls))

    check("on ned-box, no ssh is run at all: the store in front of it is "
          "ned-box's own",
          self_calls == [], self_calls)
    check("on ned-box, the seats it shows are ned-box's, not the Mac's",
          "merge-lane-2" in box_out and "ned-box" in box_out
          and "Machines read: ned-box (this machine)." in box_out, box_out)
    with pretending_the_host_is("ned-box"):
        expected_no_route = reader.no_route_notice(reader.MACHINE_NAME_MAC)
    check("on ned-box, asking for both machines says the Mac was not read",
          expected_no_route in box_out
          and "No ssh route from ned-box to mac" in box_out, box_out)
    check("and says where to run to read it, and how to ask for this "
          "machine alone",
          "Run this program on mac" in box_out
          and "--machine ned-box" in box_out, box_out)
    check("and the run exits non-zero, because a short list is not the "
          "fleet",
          box_code == reader.EXIT_SOMETHING_COULD_NOT_BE_READ, box_code)

    with pretending_the_host_is("ned-box"):
        box_alone_out, _, box_alone_code = run_and_code(
            ["--seats", "--store", str(store), "--machine", "ned-box"],
            runner=a_runner_returning(stdout=BOX_TAR, calls=self_calls))
    check("on ned-box, --machine ned-box is a complete answer and exits "
          "zero",
          box_alone_code == 0 and "not read" not in box_alone_out
          and self_calls == [], f"{box_alone_code!r} {box_alone_out!r}")

# --- what the other machine's failures say ---------------------------------

with tempfile.TemporaryDirectory() as root:
    store = build_store(root, {
        "nedschorus-merge-lane-tasks": [task(1, "Mac task")]})
    unreachable = a_runner_returning(
        stderr=b"ssh: connect to host ned-box port 22: No route to host",
        returncode=255)
    with pretending_the_host_is("Edwards-MacBook-Air.local"):
        down_out, down_message, down_code = run_and_code(
            ["--seats", "--store", str(store), "--machine", "both"],
            runner=unreachable)

    check("an unreachable ned-box is a problem, not an empty list",
          "could not be read" in down_out and "ssh exited 255" in down_out,
          down_out)
    check("and the problem repeats what ssh itself said",
          "No route to host" in down_out, down_out)
    check("and carries the remedy, per CLAUDE.md's rule about ned-box",
          "ssh nedlern@ned-box true" in down_out, down_out)
    check("and the run exits non-zero",
          down_code == reader.EXIT_SOMETHING_COULD_NOT_BE_READ, down_code)
    check("and this machine's tasks are still printed beside the problem",
          "merge-lane" in down_out and "incomplete" in down_out, down_out)
    check("and the machines-read line does not claim the machine it could "
          "not read",
          "Machines read: mac (this machine)." in down_out, down_out)

    # GNU tar exits 1 for "file changed as we read it" while writing a
    # COMPLETE archive -- 53 of 60 runs on ned-box while tasks were being
    # created, measured 2026-09-22. Discarding that archive would report a
    # healthy machine unreadable most of the time.
    with pretending_the_host_is("Edwards-MacBook-Air.local"):
        warned_out, _, warned_code = run_and_code(
            ["--seats", "--store", str(store), "--machine", "both"],
            runner=a_runner_returning(
                stdout=BOX_TAR, returncode=1,
                stderr=b"tar: ./x.json: file changed as we read it"))
    check("a tar that warned but wrote everything is read, not thrown away",
          "merge-lane-2" in warned_out, warned_out)
    check("and that run exits zero, because nothing was missed",
          warned_code == 0, warned_code)

    # tar's fatal exit, which is what a missing store on that machine looks
    # like. Reported as tar's, not as ssh being unreachable.
    with pretending_the_host_is("Edwards-MacBook-Air.local"):
        fatal_out, _, fatal_code = run_and_code(
            ["--seats", "--store", str(store), "--machine", "both"],
            runner=a_runner_returning(
                stdout=b"", returncode=2,
                stderr=b"tar: /home/nedlern/.claude/tasks: Cannot open: "
                       b"No such file or directory"))
    check("a tar that failed is reported as tar's exit, not as ssh's",
          "tar exited 2" in fatal_out and "ssh exited" not in fatal_out,
          fatal_out)
    check("and the problem says what tar said and where to look",
          "Cannot open" in fatal_out
          and "ls ~/.claude/tasks" in fatal_out, fatal_out)
    check("and that run exits non-zero",
          fatal_code == reader.EXIT_SOMETHING_COULD_NOT_BE_READ, fatal_code)

    with pretending_the_host_is("Edwards-MacBook-Air.local"):
        garbage_out, _, garbage_code = run_and_code(
            ["--seats", "--store", str(store), "--machine", "both"],
            runner=a_runner_returning(
                stdout=b"this is not a tar archive at all"))
    check("a reply that is not a readable archive is a problem, not silence",
          "readable archive" in garbage_out
          and garbage_code == reader.EXIT_SOMETHING_COULD_NOT_BE_READ,
          garbage_out)

# An unreadable task file on the other machine goes through the same notice
# as one on this machine, because it is the same reader reading it.
with tempfile.TemporaryDirectory() as root:
    store = build_store(root, {
        "nedschorus-merge-lane-tasks": [task(1, "Mac task")]})
    half_written = a_tar_of({BOX_LIST: [task(7, "Box task")]},
                            extra_files=[(f"./{BOX_LIST}/9.json",
                                          b"{half written")])
    with pretending_the_host_is("Edwards-MacBook-Air.local"):
        remote_broken_out, _, remote_broken_code = run_and_code(
            ["--seats", "--store", str(store), "--machine", "both"],
            runner=a_runner_returning(stdout=half_written))
    check("a task file the other machine could not hand over whole is named "
          "by the same notice this machine's are",
          NOTICE_WORDING in remote_broken_out
          and "9.json" in remote_broken_out, remote_broken_out)
    check("and that run exits non-zero too",
          remote_broken_code == reader.EXIT_SOMETHING_COULD_NOT_BE_READ,
          remote_broken_code)

# --- nothing is written outside the directory this run made ----------------

with tempfile.TemporaryDirectory() as root:
    scratch = Path(root) / "scratch"
    scratch.mkdir()
    escaping = a_tar_of(
        {BOX_LIST: [task(7, "Box task")]},
        extra_files=[("../escaped.json", b'{"id": "1"}'),
                     ("/absolute.json", b'{"id": "2"}')])
    # Writing outside the directory can raise rather than land, so the raise
    # fails this case by name instead of taking the suite with it.
    escaping_abort, unpacked = "", scratch
    try:
        unpacked, problems = reader.unpack_task_store_archive(
            escaping, scratch, "ned-box")
    except Exception as raised_instead:
        escaping_abort = repr(raised_instead)
    check("a member that would be written outside the directory is skipped",
          escaping_abort == ""
          and not (Path(root) / "escaped.json").exists()
          and not Path("/absolute.json").exists(),
          f"{escaping_abort} "
          f"{sorted(str(p) for p in Path(root).rglob('*'))}")
    check("and the task files beside it are still unpacked",
          (unpacked / BOX_LIST / "7.json").exists(),
          sorted(str(p) for p in unpacked.rglob("*")))

# --- read only -------------------------------------------------------------

with tempfile.TemporaryDirectory() as root:
    store = build_store(root, SAMPLE)
    before = {p: p.read_bytes() for p in sorted(store.rglob("*.json"))}
    run(["--seat", "cold-read-research", "--store", str(store)])
    run(["--seat", "cold-read-research", "--task", "9", "--store", str(store)])
    run(["--seats", "--store", str(store)])
    run(["--every-task-list", "--store", str(store)])
    after = {p: p.read_bytes() for p in sorted(store.rglob("*.json"))}
    check("reading the store changes nothing in it", before == after,
          "the harness owns the store; this program only reads")

with tempfile.TemporaryDirectory() as root:
    store = build_store(root, {
        "nedschorus-merge-lane-tasks": [task(1, "Mac task")]})
    commands = []
    with pretending_the_host_is("Edwards-MacBook-Air.local"):
        run(["--seats", "--store", str(store), "--machine", "both"],
            runner=a_runner_returning(stdout=BOX_TAR, calls=commands))
    check("reading the other machine runs nothing but the one ssh that "
          "archives its store",
          len(commands) == 1
          and not any("rm" in part or ">" in part
                      for part in commands[0]), commands)

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

# --- no case reached for ssh on its own ------------------------------------

check("no case ran a command this suite did not hand it a runner for",
      runner_calls_that_should_not_have_happened == [],
      runner_calls_that_should_not_have_happened)

print()
if failures:
    print(f"{len(failures)} case(s) failed")
    sys.exit(1)
print("all cases passed")
