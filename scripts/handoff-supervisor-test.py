#!/usr/bin/env python3
"""Tests for handoff-supervisor.py.

Run: python3 scripts/handoff-supervisor-test.py
Add --canary to also run the two live task-preseed canaries, which launch
real headless sessions. Pre-seed rides undocumented harness state; an
upgrade breaking it is detected at the successor's ignition count-check
(the queues are the backstop), and these two cases are the diagnosis to
run when that fires.

Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

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

    # --- Heartbeat and liveness ------------------------------------------
    heartbeat_state_path = workspace / "heartbeat-supervisor-state.json"
    alive, explanation = supervisor.supervisor_liveness(heartbeat_state_path)
    check(
        "no state file reads as no supervisor",
        not alive and "no supervisor state" in explanation,
        explanation,
    )

    supervisor.write_supervisor_state(heartbeat_state_path, {"session_id": "s"})
    alive, explanation = supervisor.supervisor_liveness(heartbeat_state_path)
    check("state without a heartbeat reads as dead", not alive and "no heartbeat" in explanation, explanation)

    supervisor.stamp_heartbeat(heartbeat_state_path, {"session_id": "s"})
    alive, explanation = supervisor.supervisor_liveness(heartbeat_state_path)
    check("a fresh stamp reads as alive", alive, explanation)

    supervisor.write_supervisor_state(
        heartbeat_state_path,
        {"last_poll_at": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()},
    )
    alive, explanation = supervisor.supervisor_liveness(heartbeat_state_path)
    check("a stale stamp reads as dead", not alive and "no supervisor is watching" in explanation, explanation)

    supervisor.write_supervisor_state(heartbeat_state_path, {"last_poll_at": "not a timestamp"})
    alive, explanation = supervisor.supervisor_liveness(heartbeat_state_path)
    check("an unreadable stamp reads as dead", not alive and "unreadable" in explanation, explanation)

    check_result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--check", "--agent", "heartbeat",
         "--handoff-dir", str(workspace)],
        capture_output=True, text=True, check=False,
    )
    check("--check exits non-zero for a dead supervisor", check_result.returncode == 1,
          f"code {check_result.returncode}: {check_result.stdout.strip()}")

    supervisor.stamp_heartbeat(heartbeat_state_path, {"session_id": "s"})
    check_result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--check", "--agent", "heartbeat",
         "--handoff-dir", str(workspace)],
        capture_output=True, text=True, check=False,
    )
    check("--check exits zero for a live supervisor", check_result.returncode == 0,
          f"code {check_result.returncode}: {check_result.stdout.strip()}")

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


def stub_process(poll_result):
    """A stand-in for a session process: poll() reports the given exit state."""
    return SimpleNamespace(poll=lambda: poll_result)


def run_exit_handoff_cases(workspace: Path):
    """A headless session exits when its turn ends, so its handoff arrives AS
    a process exit. Exit with a new counter on disk must read as a handoff;
    exit without one is abandonment."""
    handoff_path = workspace / "exitcase-handoff.md"
    state_path = workspace / "exitcase-supervisor-state.json"

    handoff_path.write_text(
        "written-at: 2026-08-06T12:00:00Z\nnext-step: drain the tasks\nrestart-counter: 8\n",
        encoding="utf-8",
    )
    fields = supervisor.wait_for_handoff(stub_process(0), handoff_path, 7, state_path, {})
    check(
        "exit with a new counter reads as a handoff",
        fields is not None and supervisor.counter_from(fields) == 8,
        str(fields),
    )

    fields = supervisor.wait_for_handoff(stub_process(0), handoff_path, 8, state_path, {})
    check("exit with the already-consumed counter reads as abandonment", fields is None, str(fields))

    fields = supervisor.wait_for_handoff(
        stub_process(0), workspace / "never-written-handoff.md", 7, state_path, {}
    )
    check("exit with no handoff file reads as abandonment", fields is None, str(fields))

    fields = supervisor.wait_for_handoff(stub_process(None), handoff_path, 7, state_path, {})
    check(
        "a running session's new handoff is seen without an exit",
        fields is not None and supervisor.counter_from(fields) == 8,
        str(fields),
    )


def run_adoption_cases(workspace: Path):
    """Adopting a running session is what lets a hand-started agent recycle:
    a supervisor normally owns only the process it launched itself."""
    # Not a context manager: the point is a process this test does NOT own a
    # handle to in the supervisor, which is what adoption exists for.
    sleeper = subprocess.Popen(  # pylint: disable=consider-using-with
        [sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        adopted = supervisor.AdoptedSession("some-session-id", sleeper.pid)
        check("an adopted live process reads as running", adopted.poll() is None)
        adopted.terminate()
        sleeper.wait(timeout=10)
        check("an adopted process can be terminated", adopted.poll() == 0)
        check("terminating an already-gone process is not an error",
              adopted.terminate() is None)
    finally:
        if sleeper.poll() is None:
            sleeper.kill()
            sleeper.wait()

    gone = supervisor.AdoptedSession("some-session-id", 99999999)
    check("a process id that does not exist reads as gone", gone.poll() == 0)

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--agent", "adopter",
         "--handoff-dir", str(workspace), "--adopt-session-id", "an-id"],
        capture_output=True, text=True, check=False,
    )
    check("adopting without a process id is refused", result.returncode == 2, result.stderr)

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--agent", "adopter", "--cd", str(workspace),
         "--handoff-dir", str(workspace), "--adopt-session-id", "an-id",
         "--adopt-process-id", "99999999"],
        capture_output=True, text=True, check=False,
    )
    check("adopting a process that is already gone is refused",
          result.returncode == 2 and "already gone" in result.stderr, result.stderr)


def run_dont_restart_without_a_terminal_case(workspace: Path):
    """A supervisor an agent started has no terminal. Asking `restart? y/n`
    there raises EOFError before the consumed counter is recorded, so the next
    supervisor re-fires on the stale handoff — launching a session and killing
    it immediately."""
    handoff_directory = workspace / "noterm"
    handoff_directory.mkdir(parents=True, exist_ok=True)
    (handoff_directory / "noterm-handoff.md").write_text(
        "written-at: 2026-08-06T12:00:00Z\n"
        "next-step: should not relaunch\n"
        "restart-counter: 1\n"
        "dont-restart: the user asked to be consulted\n",
        encoding="utf-8",
    )
    stub_agent = handoff_directory / "stub-agent"
    stub_agent.write_text("#!/bin/sh\nsleep 30\n", encoding="utf-8")
    stub_agent.chmod(0o755)

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--agent", "noterm", "--cd", str(workspace),
         "--handoff-dir", str(handoff_directory), "--agent-command", str(stub_agent)],
        capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL, timeout=60,
    )
    check("dont-restart without a terminal exits cleanly, not on EOFError",
          result.returncode == 0 and "EOFError" not in result.stderr, result.stderr[-300:])
    check("dont-restart without a terminal says why it stopped",
          "no terminal to ask on" in result.stdout, result.stdout[-300:])

    state = supervisor.read_supervisor_state(handoff_directory / "noterm-supervisor-state.json")
    check("the consumed counter is recorded before stopping",
          state.get("consumed_counter") == 1, str(state))


def run_first_prompt_file_cases(workspace: Path):
    """The founding boot passes its prompt as a file the supervisor reads
    itself, so the content never rides through nested shell quoting."""
    prompt_path = workspace / "founding-prompt.txt"
    prompt_path.write_text("You are choirmaster.\nRead the plan.\n", encoding="utf-8")
    stub_agent = workspace / "prompt-stub-agent"
    stub_agent.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    stub_agent.chmod(0o755)

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--agent", "promptcase", "--cd", str(workspace),
         "--handoff-dir", str(workspace / "prompt-handoffs"),
         "--agent-command", str(stub_agent),
         "--first-prompt-file", str(workspace / "no-such-prompt.txt")],
        capture_output=True, text=True, check=False, timeout=30,
    )
    check("a missing first-prompt file is refused before launch",
          result.returncode == 2 and "does not exist" in result.stderr, result.stderr[-200:])

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--agent", "promptcase", "--cd", str(workspace),
         "--handoff-dir", str(workspace / "prompt-handoffs"),
         "--agent-command", str(stub_agent),
         "--first-prompt-file", str(prompt_path)],
        capture_output=True, text=True, check=False, timeout=30,
    )
    check("a first-prompt file launches cleanly", result.returncode == 0, result.stderr[-200:])


def run_lock_cases(workspace: Path):
    """Two supervisors on one agent would each kill the session and each launch
    a successor, so the second must refuse to start."""
    lock_path = workspace / "locktest-supervisor.lock"
    check("the lock is claimable when free", supervisor.claim_supervisor_lock(lock_path))
    check("the lock records the holder", lock_path.read_text().strip() == str(os.getpid()))
    check("the same process may re-enter its own lock", supervisor.claim_supervisor_lock(lock_path))

    lock_path.write_text("99999999\n", encoding="utf-8")
    check("a lock held by a dead process is reclaimed", supervisor.claim_supervisor_lock(lock_path))

    live_holder = subprocess.Popen(  # pylint: disable=consider-using-with
        [sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        lock_path.write_text(f"{live_holder.pid}\n", encoding="utf-8")
        check("a lock held by a live process blocks a second supervisor",
              not supervisor.claim_supervisor_lock(lock_path))
    finally:
        live_holder.kill()
        live_holder.wait()

    lock_path.write_text("not a number\n", encoding="utf-8")
    check("an unreadable lock is reclaimed", supervisor.claim_supervisor_lock(lock_path))
    lock_path.unlink(missing_ok=True)


def run_launch_and_retention_cases(workspace: Path, recent: str):
    # --- Ignition prompt --------------------------------------------------
    prompt = supervisor.build_ignition_prompt(
        Path("/tmp/dialog-0002.md"),
        {"written-at": recent, "next-step": "finish the supervisor"},
        4,
        "queues — nc-queue: 3, oldest 001-stale-item.md",
    )
    check("ignition names the dialog path", "/tmp/dialog-0002.md" in prompt, prompt)
    check("ignition carries the elapsed line", "minutes ago" in prompt, prompt)
    check("ignition states the task count", "4 task(s)" in prompt, prompt)
    check("ignition carries the next step", "finish the supervisor" in prompt, prompt)
    # The rot-visibility duty (#32): the successor reads the queue depths.
    check("ignition carries the queue status", "oldest 001-stale-item.md" in prompt, prompt)
    prompt_without_step = supervisor.build_ignition_prompt(Path("/tmp/d.md"), {"written-at": recent}, 0)
    check("ignition survives a missing next-step", "continue from where that dialog ends" in prompt_without_step)
    check("ignition omits an empty queue status", "Queue status" not in prompt_without_step)

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


def git_in(arguments, cwd):
    completed = subprocess.run(["git", *arguments], cwd=str(cwd),
                               capture_output=True, text=True, check=False)
    if completed.returncode != 0 and arguments[0] not in ("merge",):
        raise AssertionError(f"git {' '.join(arguments)} failed: {completed.stderr}")
    return completed


def run_branch_sync_cases(workspace: Path):
    """Every branch of sync_working_branch_with_main, against real repositories.

    The function only ever fast-forwards, so the cases that matter most are the
    ones where it must NOT act: a dirty tree, a diverged branch, a directory
    that is not a checkout at all.
    """
    root = workspace / "branch-sync"
    root.mkdir()

    check("a directory that is not a checkout syncs to nothing",
          "nothing to sync" in supervisor.sync_working_branch_with_main(root))

    remote = root / "remote.git"
    git_in(["init", "--quiet", "--bare", "--initial-branch=main", str(remote)], root)
    seed = root / "seed"
    git_in(["clone", "--quiet", str(remote), str(seed)], root)
    git_in(["config", "user.name", "fixture"], seed)
    git_in(["config", "user.email", "fixture@nedschorus.invalid"], seed)
    (seed / "README.md").write_text("seed\n", encoding="utf-8")
    git_in(["add", "-A"], seed)
    git_in(["commit", "--quiet", "-m", "seed"], seed)
    git_in(["push", "--quiet", "origin", "main"], seed)

    # The agent's home: a clone on its own branch, as every agent home is.
    home = root / "agent-home"
    git_in(["clone", "--quiet", str(remote), str(home)], root)
    git_in(["config", "user.name", "agent"], home)
    git_in(["config", "user.email", "agent@nedschorus.invalid"], home)
    git_in(["checkout", "--quiet", "-b", "agent-branch"], home)

    check("a branch level with main reports current",
          "current with main" in supervisor.sync_working_branch_with_main(home))

    # Main moves ahead; the agent's clean branch must fast-forward onto it.
    (seed / "README.md").write_text("seed\nfrom main\n", encoding="utf-8")
    git_in(["add", "-A"], seed)
    git_in(["commit", "--quiet", "-m", "main moves ahead"], seed)
    git_in(["push", "--quiet", "origin", "main"], seed)

    report = supervisor.sync_working_branch_with_main(home)
    check("a clean branch behind main fast-forwards", "fast-forwarded to main" in report, report)
    check("the fast-forward really moved the files",
          (home / "README.md").read_text(encoding="utf-8") == "seed\nfrom main\n")

    # Uncommitted work is never disturbed, however far behind the branch is.
    (seed / "README.md").write_text("seed\nfrom main\nfurther\n", encoding="utf-8")
    git_in(["add", "-A"], seed)
    git_in(["commit", "--quiet", "-m", "main moves again"], seed)
    git_in(["push", "--quiet", "origin", "main"], seed)
    (home / "work-in-progress.txt").write_text("half a thought\n", encoding="utf-8")

    report = supervisor.sync_working_branch_with_main(home)
    check("a dirty tree is left exactly as it is", "left as is" in report, report)
    check("the uncommitted file survives the sync", (home / "work-in-progress.txt").is_file())
    check("a dirty tree is not fast-forwarded",
          (home / "README.md").read_text(encoding="utf-8") == "seed\nfrom main\n")

    # A branch carrying its own commits is reported, never merged: a conflicted
    # merge waiting for an agent that has not woken up is worse than being behind.
    (home / "work-in-progress.txt").unlink()
    (home / "agent-note.txt").write_text("finished thought\n", encoding="utf-8")
    git_in(["add", "-A"], home)
    git_in(["commit", "--quiet", "-m", "the agent's own work"], home)

    report = supervisor.sync_working_branch_with_main(home)
    check("a diverged branch is reported, not merged", "merge when ready" in report, report)
    check("the diverged report counts both directions",
          "1 ahead of main" in report and "1 behind" in report, report)
    check("a diverged branch keeps its own commit",
          git_in(["log", "-1", "--format=%s"], home).stdout.strip() == "the agent's own work")

    # Ahead-only: everything main has, plus local work. Nothing to pull.
    git_in(["merge", "--no-edit", "--quiet", "origin/main"], home)
    report = supervisor.sync_working_branch_with_main(home)
    check("a branch ahead of main with all of main reports nothing to pull",
          "nothing to pull" in report, report)


with tempfile.TemporaryDirectory() as temporary_directory:
    recent_timestamp = run_offline_cases(Path(temporary_directory))
    run_branch_sync_cases(Path(temporary_directory))
    run_exit_handoff_cases(Path(temporary_directory))
    run_adoption_cases(Path(temporary_directory))
    run_dont_restart_without_a_terminal_case(Path(temporary_directory))
    run_first_prompt_file_cases(Path(temporary_directory))
    run_lock_cases(Path(temporary_directory))
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
