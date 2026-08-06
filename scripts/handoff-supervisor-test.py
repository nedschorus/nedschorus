#!/usr/bin/env python3
"""Tests for handoff-supervisor.py.

Run: python3 scripts/handoff-supervisor-test.py
Add --canary to also run the two live task-preseed canaries, which launch
real headless sessions. Run those after every Claude Code upgrade: pre-seed
rides undocumented harness state, and these two cases are what detect it
breaking.

Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name("handoff-supervisor.py")

_spec = importlib.util.spec_from_file_location("handoff_supervisor", SCRIPT_PATH)
supervisor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(supervisor)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def run_offline_cases(workspace: Path):
    # --- Handoff parsing --------------------------------------------------
    handoff_path = workspace / "agent-handoff.md"
    handoff_path.write_text(
        "# Handoff\n"
        "\n"
        "written-at: 2026-08-06T12:00:00Z\n"
        "read-starting-here: the prompt that opened this topic\n"
        "next-step: land the supervisor tests\n"
        "restart-counter: 7\n"
        "\n"
        "Prose below the fields: next-step: this later line must not win.\n",
        encoding="utf-8",
    )
    fields = supervisor.parse_handoff_file(handoff_path)
    check("parses each handoff field", fields["restart-counter"] == "7", str(fields))
    check("first occurrence of a field wins", fields["next-step"] == "land the supervisor tests", fields["next-step"])
    check("reads the counter as an integer", supervisor.counter_from(fields) == 7)
    check("a missing counter reads as None", supervisor.counter_from({}) is None)
    check("a non-numeric counter reads as None", supervisor.counter_from({"restart-counter": "soon"}) is None)

    # --- Consumed-marker semantics ---------------------------------------
    state_path = workspace / "agent-supervisor-state.json"
    check("absent state starts fresh", supervisor.read_supervisor_state(state_path)["consumed_counter"] is None)
    supervisor.write_supervisor_state(state_path, {"consumed_counter": 7, "session_id": "s", "generation": 3})
    check("state round-trips", supervisor.read_supervisor_state(state_path)["consumed_counter"] == 7)
    state_path.write_text("{ not json", encoding="utf-8")
    check("unreadable state starts fresh", supervisor.read_supervisor_state(state_path)["generation"] == 0)

    # --- Elapsed-time phrasing -------------------------------------------
    recent = (datetime.now(timezone.utc) - timedelta(minutes=12)).isoformat()
    old = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    check(
        "recent handoff reports minutes",
        "minutes ago" in supervisor.elapsed_phrase(recent),
        supervisor.elapsed_phrase(recent),
    )
    check("old handoff reports days", "days ago" in supervisor.elapsed_phrase(old), supervisor.elapsed_phrase(old))
    check("unparseable timestamp still warns", "stale" in supervisor.elapsed_phrase("whenever"))
    return recent


def run_launch_and_retention_cases(workspace: Path, recent: str):
    # --- Ignition prompt --------------------------------------------------
    prompt = supervisor.build_ignition_prompt(
        Path("/tmp/dialog-0002.md"),
        {"written-at": recent, "next-step": "finish the supervisor"},
        4,
    )
    check("ignition names the dialog path", "/tmp/dialog-0002.md" in prompt, prompt)
    check("ignition carries the elapsed line", "minutes ago" in prompt, prompt)
    check("ignition states the task count", "4 task(s)" in prompt, prompt)
    check("ignition carries the next step", "finish the supervisor" in prompt, prompt)
    prompt_without_step = supervisor.build_ignition_prompt(Path("/tmp/d.md"), {"written-at": recent}, 0)
    check("ignition survives a missing next-step", "continue from where that dialog ends" in prompt_without_step)

    # --- Retention --------------------------------------------------------
    for generation in range(1, 6):
        (workspace / f"agent-dialog-{generation:04d}.md").write_text("x", encoding="utf-8")
    supervisor.prune_old_generations(workspace, "agent-dialog")
    remaining = sorted(item.name for item in workspace.glob("agent-dialog-*.md"))
    check(
        "retention keeps the newest two generations",
        remaining == ["agent-dialog-0004.md", "agent-dialog-0005.md"],
        str(remaining),
    )

    # --- Queue status -----------------------------------------------------
    project = workspace / "project"
    (project / "nc-queue").mkdir(parents=True)
    (project / "nc-queue" / "2026-07-28-older-note.md").write_text("x", encoding="utf-8")
    (project / "nc-queue" / "2026-08-01-newer-note.md").write_text("x", encoding="utf-8")
    (project / "nc-queue" / "README.md").write_text("x", encoding="utf-8")
    (project / "docs" / "wiki" / "queue").mkdir(parents=True)
    line = supervisor.queue_status_line(project)
    check("queue status counts a loaded queue", "nc-queue: 2" in line, line)
    check("queue status names the oldest item", "2026-07-28-older-note.md" in line, line)
    check("queue status reports an empty queue", "docs/wiki/queue: empty" in line, line)

    # --- Task pre-seed (file mechanics, no session) -----------------------
    original_tasks_root = supervisor.TASKS_ROOT
    try:
        supervisor.TASKS_ROOT = workspace / "tasks"
        retiring, successor = "old-session", "new-session"
        (supervisor.TASKS_ROOT / retiring).mkdir(parents=True)
        for task_id in (1, 2):
            (supervisor.TASKS_ROOT / retiring / f"{task_id}.json").write_text(
                json.dumps({"id": task_id, "status": "pending"}), encoding="utf-8"
            )
        copied = supervisor.preseed_tasks(retiring, successor)
        check("pre-seed copies every task record", copied == 2, f"copied {copied}")
        check("pre-seed counts what the successor will see", supervisor.task_count_for(successor) == 2)
        check("pre-seed leaves the source intact", supervisor.task_count_for(retiring) == 2)
        check("pre-seed of a taskless session copies nothing", supervisor.preseed_tasks("never-existed", "x") == 0)
    finally:
        supervisor.TASKS_ROOT = original_tasks_root


def run_preseed_canaries() -> None:
    """Live canaries: does a fresh session read pre-seeded task files?

    Canary 1: a session started with an explicit id reads task records that
    were on disk before it booted.
    Canary 2: a task the successor creates allocates above the seeded ids,
    leaving the migrated records untouched.
    """
    session_id = str(uuid.uuid4())
    task_directory = supervisor.TASKS_ROOT / session_id
    task_directory.mkdir(parents=True, exist_ok=True)
    # The record shape is the harness's own, read from live task stores: the
    # id is a STRING, and blocks/blockedBy are present. A record with an
    # integer id is silently dropped by TaskList while still counting toward
    # the next allocated id — measured 2026-08-06, and the reason this
    # fixture is written out longhand rather than approximated.
    for task_id, subject in (("1", "carried task alpha"), ("2", "carried task beta")):
        (task_directory / f"{task_id}.json").write_text(
            json.dumps(
                {
                    "id": task_id,
                    "subject": subject,
                    "description": f"seeded by the canary: {subject}",
                    "status": "pending",
                    "blocks": [],
                    "blockedBy": [],
                }
            ),
            encoding="utf-8",
        )

    result = subprocess.run(
        [
            "claude", "-p", "--session-id", session_id,
            "List your current tasks with the TaskList tool, then create one new task "
            "titled 'canary successor task'. Report the subjects you saw and the new task's id.",
        ],
        capture_output=True, text=True, timeout=300, check=False,
    )
    transcript = result.stdout

    check("canary 1: successor reads seeded tasks", "alpha" in transcript and "beta" in transcript, transcript[:400])

    seeded_intact = all((task_directory / f"{n}.json").is_file() for n in (1, 2))
    new_files = sorted(int(p.stem) for p in task_directory.glob("*.json") if p.stem.isdigit())
    check("canary 2: seeded records are untouched", seeded_intact, str(new_files))
    check("canary 2: new task ids allocate above the seeded maximum", max(new_files) >= 3, str(new_files))


with tempfile.TemporaryDirectory() as temporary_directory:
    recent_timestamp = run_offline_cases(Path(temporary_directory))
    run_launch_and_retention_cases(Path(temporary_directory), recent_timestamp)

if "--canary" in sys.argv:
    print("\n-- live pre-seed canaries (launching real sessions) --")
    run_preseed_canaries()
else:
    print("\n(skipped the live pre-seed canaries; pass --canary to run them)")

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
