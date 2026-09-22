#!/usr/bin/env python3
"""Cases for scripts/show-seat-task-lists.py.

Every case builds a task store in a temporary directory, or a fake tar
over a fake ssh runner, and runs the real functions against it. Nothing
here reads the machine's own task store, and nothing reaches ned-box.

The refusal paths are the point of this suite. The tool's reason for
existing is that it must not print a short list as though it were the
whole fleet, so the cases that matter are the ones asserting a problem
is named AND the exit code carries it: an unreachable ned-box, an
unparseable task file, a missing store.
"""

import io
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import importlib.util as _util

_spec = _util.spec_from_file_location(
    "show_seat_task_lists",
    Path(__file__).resolve().parent / "show-seat-task-lists.py")
tool = _util.module_from_spec(_spec)
_spec.loader.exec_module(tool)

PASSES = []
FAILURES = []


def check(description, condition, detail=""):
    if condition:
        PASSES.append(description)
        print("PASS  %s" % description)
    else:
        FAILURES.append(description)
        print("FAIL  %s%s" % (description,
                              ("  -- " + detail) if detail else ""))


def a_task(task_id, subject, status, **extra):
    task = {"id": str(task_id), "subject": subject, "status": status,
            "description": extra.pop("description", "a description"),
            "blocks": [], "blockedBy": []}
    task.update(extra)
    return task


def build_a_task_store(root, seats_and_tasks):
    root.mkdir(parents=True, exist_ok=True)
    for seat, tasks in seats_and_tasks.items():
        seat_directory = root / ("nedschorus-%s-tasks" % seat)
        seat_directory.mkdir(parents=True, exist_ok=True)
        (seat_directory / ".lock").write_text("")
        (seat_directory / ".highwatermark").write_text("99")
        for task in tasks:
            (seat_directory / ("%s.json" % task["id"])).write_text(
                json.dumps(task), encoding="utf-8")
    return root


def a_runner_returning(stdout=b"", stderr=b"", returncode=0):
    def runner(command):
        return subprocess.CompletedProcess(
            command, returncode, stdout=stdout, stderr=stderr)
    return runner


def a_tar_of(seats_and_tasks):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:") as archive:
        for seat, tasks in seats_and_tasks.items():
            for task in tasks:
                payload = json.dumps(task).encode("utf-8")
                info = tarfile.TarInfo(
                    "./nedschorus-%s-tasks/%s.json" % (seat, task["id"]))
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


# --- seat names ------------------------------------------------------

check("a nedschorus task directory yields its seat name",
      tool.seat_name_from_directory_name(
          "nedschorus-reboot-test-tasks") == "reboot-test")
check("a directory without the project prefix is not ours",
      tool.seat_name_from_directory_name("other-thing-tasks") is None)
check("nor is a long one, where dropping the prefix check would "
      "otherwise yield a plausible seat",
      tool.seat_name_from_directory_name(
          "some-other-product-tasks") is None,
      repr(tool.seat_name_from_directory_name(
          "some-other-product-tasks")))
check("a directory without the tasks suffix is not ours",
      tool.seat_name_from_directory_name("nedschorus-reboot-test")
      is None)
check("a directory naming no seat is not ours",
      tool.seat_name_from_directory_name("nedschorus--tasks") is None)

# --- parsing one task ------------------------------------------------

good, problem = tool.task_from_json_text(
    json.dumps(a_task(1, "do a thing", "pending")), "somewhere")
check("a well-formed task file parses",
      good is not None and problem is None)

bad, problem = tool.task_from_json_text("{not json", "somewhere.json")
check("an unparseable task file is named, not raised",
      bad is None and problem is not None
      and "somewhere.json" in problem)

bad, problem = tool.task_from_json_text("[1,2,3]", "a-list.json")
check("a task file that is not an object is named",
      bad is None and problem is not None and "a-list.json" in problem)

bad, problem = tool.task_from_json_text(
    json.dumps({"id": "1", "subject": "x"}), "no-status.json")
check("a task file missing status is named",
      bad is None and problem is not None and "status" in problem)

# --- reading this machine's store -----------------------------------

with tempfile.TemporaryDirectory() as temporary:
    root = build_a_task_store(Path(temporary) / "tasks", {
        "reboot-test": [a_task(1, "first", "pending"),
                        a_task(2, "second", "completed")],
        "merge-lane": [a_task(3, "third", "in_progress")],
    })
    tasks, problems = tool.read_seat_task_lists_on_this_mac(root)
    check("every seat's tasks are read from this machine",
          len(tasks) == 3, "got %d" % len(tasks))
    check("the harness's own .lock and .highwatermark are skipped",
          problems == [], repr(problems))
    check("each task carries the seat it came from",
          sorted({each["seat"] for each in tasks})
          == ["merge-lane", "reboot-test"])
    check("each task read here is marked as this machine's",
          all(each["machine"] == tool.THIS_MACHINE_NAME
              for each in tasks))

with tempfile.TemporaryDirectory() as temporary:
    root = build_a_task_store(Path(temporary) / "tasks", {
        "reboot-test": [a_task(1, "first", "pending")]})
    (root / "nedschorus-reboot-test-tasks" / "9.json").write_text(
        "{half written", encoding="utf-8")
    tasks, problems = tool.read_seat_task_lists_on_this_mac(root)
    check("a task file that cannot be parsed does not stop the run",
          len(tasks) == 1, "got %d" % len(tasks))
    check("and that file is named as a problem",
          len(problems) == 1 and "9.json" in problems[0],
          repr(problems))

with tempfile.TemporaryDirectory() as temporary:
    missing = Path(temporary) / "there-is-no-store-here"
    tasks, problems = tool.read_seat_task_lists_on_this_mac(missing)
    check("a missing store on this machine is a problem, not silence",
          tasks == [] and len(problems) == 1, repr(problems))

# --- reading ned-box -------------------------------------------------

tasks, problems = tool.read_seat_task_lists_on_ned_box(
    a_runner_returning(stdout=a_tar_of({
        "merge-lane-2": [a_task(7, "box task", "pending")]})))
check("ned-box's tasks are read out of the tar it sends",
      len(tasks) == 1 and tasks[0]["subject"] == "box task",
      repr(tasks))
check("a task read from ned-box is marked as ned-box's",
      tasks and tasks[0]["machine"] == tool.NED_BOX_MACHINE_NAME)
check("and carries the seat its directory names",
      tasks and tasks[0]["seat"] == "merge-lane-2")
check("reading ned-box cleanly reports no problem", problems == [],
      repr(problems))

tasks, problems = tool.read_seat_task_lists_on_ned_box(
    a_runner_returning(
        stderr=b"ssh: connect to host ned-box port 22: No route to host",
        returncode=255))
check("an unreachable ned-box is a problem, not an empty list",
      tasks == [] and len(problems) == 1, repr(problems))
check("and the problem repeats what ssh itself said",
      problems and "No route to host" in problems[0], repr(problems))
check("and the problem carries the remedy, per CLAUDE.md",
      problems and "ssh nedlern@ned-box" in problems[0], repr(problems))

tasks, problems = tool.read_seat_task_lists_on_ned_box(
    a_runner_returning(stdout=b"this is not a tar archive at all"))
check("a reply that is not a readable archive is a problem",
      tasks == [] and len(problems) == 1, repr(problems))

# --- the report ------------------------------------------------------

sample = [
    dict(a_task(1, "a pending one", "pending"),
         seat="reboot-test", machine="mac"),
    dict(a_task(2, "a done one", "completed"),
         seat="reboot-test", machine="mac"),
    dict(a_task(3, "a running one", "in_progress"),
         seat="merge-lane-2", machine="ned-box"),
]

default_report = "\n".join(tool.report_lines(
    sample, [], tool.STATUSES_SHOWN_BY_DEFAULT, False, None))
check("by default a completed task is not printed",
      "a done one" not in default_report)
check("by default a pending task is printed",
      "a pending one" in default_report)
check("by default an in-progress task is printed",
      "a running one" in default_report)
check("by default a description is not printed",
      "a description" not in default_report)
check("both machines appear in one report",
      "ned-box" in default_report and "mac" in default_report)

every_report = "\n".join(tool.report_lines(
    sample, [], tool.EVERY_STATUS, False, None))
check("asking for all statuses prints the completed one",
      "a done one" in every_report)

described = "\n".join(tool.report_lines(
    sample, [], tool.STATUSES_SHOWN_BY_DEFAULT, True, None))
check("asking for descriptions prints them",
      "a description" in described)

one_seat = "\n".join(tool.report_lines(
    sample, [], tool.EVERY_STATUS, False, "merge-lane-2"))
check("asking for one seat prints only that seat's tasks",
      "a running one" in one_seat and "a pending one" not in one_seat)

with_problem = "\n".join(tool.report_lines(
    sample, ["ned-box could not be read"],
    tool.STATUSES_SHOWN_BY_DEFAULT, False, None))
check("a report with a problem says the list is incomplete",
      "incomplete" in with_problem
      and "ned-box could not be read" in with_problem)

# --- exit codes ------------------------------------------------------

with tempfile.TemporaryDirectory() as temporary:
    root = build_a_task_store(Path(temporary) / "tasks", {
        "reboot-test": [a_task(1, "first", "pending")]})
    out = io.StringIO()
    code = tool.main(
        argv=["--machine", "mac"], tasks_root=root,
        runner=a_runner_returning(), out=out)
    check("a clean read of one machine exits zero",
          code == tool.EXIT_EVERYTHING_READ, "got %r" % code)

    out = io.StringIO()
    code = tool.main(
        argv=[], tasks_root=root,
        runner=a_runner_returning(stderr=b"nope", returncode=255),
        out=out)
    check("an unreachable ned-box makes the whole run exit non-zero",
          code == tool.EXIT_SOMETHING_COULD_NOT_BE_READ, "got %r" % code)
    check("and the Mac's tasks are still printed alongside the problem",
          "first" in out.getvalue() and "incomplete" in out.getvalue())

with tempfile.TemporaryDirectory() as temporary:
    root = build_a_task_store(Path(temporary) / "tasks", {
        "reboot-test": [a_task(1, "first", "pending")]})
    (root / "nedschorus-reboot-test-tasks" / "9.json").write_text(
        "{half written", encoding="utf-8")
    out = io.StringIO()
    code = tool.main(
        argv=["--machine", "mac"], tasks_root=root,
        runner=a_runner_returning(), out=out)
    check("one unparseable task file makes the run exit non-zero",
          code == tool.EXIT_SOMETHING_COULD_NOT_BE_READ, "got %r" % code)

print()
if FAILURES:
    print("%d PASS, %d FAIL" % (len(PASSES), len(FAILURES)))
    sys.exit(1)
print("all cases passed")
