#!/usr/bin/env python3
"""Run one agent session and recycle it when it writes a handoff.

The handoff system's supervisor (specification:
docs/cross-project/fast-handoff-design.md). One supervisor per agent, run in
that agent's console. It owns the whole recycle cycle because an agent
cannot exit itself: /clear and /exit are unavailable to it, and self-SIGTERM
trips the safety classifier.

The cycle, per recycle:
  1. Watch the handoff file for a restart-counter above the last consumed.
  2. Kill the running session.
  3. Extract its dialog to disk before anything else proceeds.
  4. Copy the retiring session's tasks into the successor's task directory.
  5. Print one queue-status line.
  6. Launch the successor with the ignition prompt.
  7. Keep the current and previous handoff and extract; delete older ones.

The handoff file the agent writes (simple `key: value` lines):
  written-at:      UTC timestamp, ISO 8601
  next-step:       the first action the successor takes
  restart-counter: predecessor's counter plus one
  dont-restart:    optional; any value makes the supervisor ask before relaunching

How much dialog to carry is not among them: the extractor takes the tail that
clears its word floor, so the retiring agent exercises no judgment over what
its successor receives.

Never pass --allowedTools on the launch: it silently swallows the positional
prompt, so the successor would boot with no instructions at all.

Exit codes: 0 clean stop, 2 bad invocation, 3 the agent command is missing.
"""

import argparse
import json
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

TASKS_ROOT = Path.home() / ".claude" / "tasks"
EXTRACTOR_PATH = Path(__file__).with_name("handoff-extract-conversation.py")
HANDOFF_POLL_SECONDS = 2.0
GENERATIONS_KEPT = 2

# The supervisor stamps its state file while polling so anyone can ask whether
# a supervisor is still watching. Without this an agent can write a handoff,
# stop working, and wait forever on a supervisor that died — a hang that looks
# like obedience. Stamped on an interval rather than every poll to keep the
# write rate low; treated as dead at several times that interval, so a slow
# machine does not read as a corpse.
HEARTBEAT_INTERVAL_SECONDS = 10.0
HEARTBEAT_STALE_SECONDS = 60.0


def parse_handoff_file(handoff_path: Path) -> dict:
    """Read the agent-written handoff into a dict of its `key: value` lines."""
    fields = {}
    for line in handoff_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        key = key.strip().lower()
        if key not in fields:  # first occurrence wins; later prose cannot overwrite a field
            fields[key] = value.strip()
    return fields


def read_supervisor_state(state_path: Path) -> dict:
    if not state_path.is_file():
        return {"consumed_counter": None, "session_id": None, "generation": 0}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        print("handoff-supervisor: unreadable state file; starting fresh", file=sys.stderr)
        return {"consumed_counter": None, "session_id": None, "generation": 0}


def write_supervisor_state(state_path: Path, state: dict) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def stamp_heartbeat(state_path: Path, state: dict) -> None:
    """Record that a supervisor is alive and watching, right now."""
    state["last_poll_at"] = datetime.now(timezone.utc).isoformat()
    write_supervisor_state(state_path, state)


def supervisor_liveness(state_path: Path):
    """Return (is_alive, explanation) for the supervisor owning this state file."""
    if not state_path.is_file():
        return False, f"no supervisor state at {state_path} — none has ever run for this agent"

    state = read_supervisor_state(state_path)
    stamped = state.get("last_poll_at")
    if not stamped:
        return False, "supervisor state carries no heartbeat — it is from an older build or never polled"

    try:
        last_poll = datetime.fromisoformat(stamped)
    except ValueError:
        return False, f"unreadable heartbeat: {stamped!r}"

    age_seconds = (datetime.now(timezone.utc) - last_poll).total_seconds()
    if age_seconds > HEARTBEAT_STALE_SECONDS:
        return False, f"last heartbeat was {age_seconds:.0f}s ago — no supervisor is watching"
    return True, f"supervisor alive, last heartbeat {age_seconds:.0f}s ago"


def counter_from(fields: dict):
    raw = fields.get("restart-counter")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def elapsed_phrase(written_at: str) -> str:
    """Describe how stale a handoff is, for the ignition prompt."""
    try:
        written = datetime.fromisoformat(written_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return "written at an unrecorded time — treat every pointer in it as possibly stale"

    minutes = (datetime.now(timezone.utc) - written).total_seconds() / 60
    if minutes < 90:
        amount = f"{int(minutes)} minutes"
    elif minutes < 60 * 48:
        amount = f"{int(minutes / 60)} hours"
    else:
        amount = f"{int(minutes / 60 / 24)} days"
    return f"written {amount} ago — the longer the gap, the more will have changed since"


def task_count_for(session_id: str) -> int:
    directory = TASKS_ROOT / session_id
    return len(list(directory.glob("*.json"))) if directory.is_dir() else 0


def preseed_tasks(retiring_session_id: str, successor_session_id: str) -> int:
    """Copy task records into the successor's directory before it boots.

    Rides undocumented harness state: tasks are <N>.json files under
    ~/.claude/tasks/<session-id>/, and a session started with an explicit id
    reads whatever is already there. Re-run the canaries in
    handoff-supervisor-test.py after every Claude Code upgrade.
    """
    source = TASKS_ROOT / retiring_session_id
    if not source.is_dir():
        return 0
    destination = TASKS_ROOT / successor_session_id
    destination.mkdir(parents=True, exist_ok=True)
    copied = 0
    for task_file in sorted(source.glob("*.json")):
        shutil.copy2(task_file, destination / task_file.name)
        copied += 1
    return copied


def queue_status_line(working_directory: Path) -> str:
    """Report each queue's depth and oldest item, so rot stays visible."""
    reports = []
    for queue_directory in ("nc-queue", "docs/issues/queue", "docs/wiki/queue", "legacy-feature-queue"):
        directory = working_directory / queue_directory
        if not directory.is_dir():
            continue
        entries = sorted(
            item for item in directory.glob("*.md") if item.name.lower() != "readme.md"
        )
        if not entries:
            reports.append(f"{queue_directory}: empty")
            continue
        oldest = min(entries, key=lambda item: item.name)
        reports.append(f"{queue_directory}: {len(entries)}, oldest {oldest.name}")
    return "queues — " + ("; ".join(reports) if reports else "none found")


def extract_dialog(session_id: str, working_directory: Path, output_path: Path) -> bool:
    """Write the retiring session's dialog to disk. Returns True on success.

    No boundary is passed: the extractor carries the tail that clears its word
    floor, so nothing here depends on a judgment the retiring agent made.
    """
    result = subprocess.run(
        [
            sys.executable, str(EXTRACTOR_PATH),
            "--session-id", session_id,
            "--cd", str(working_directory),
            "--output", str(output_path),
        ],
        check=False,
    )
    return result.returncode == 0


def build_ignition_prompt(extract_path: Path, handoff_fields: dict, task_count: int) -> str:
    next_step = handoff_fields.get("next-step", "").strip()
    elapsed = elapsed_phrase(handoff_fields.get("written-at", ""))
    lines = [
        f"Read {extract_path} — it is the dialog from the session you are continuing, {elapsed}.",
        f"Confirm {task_count} task(s) are visible to you; if the count differs, say so before starting work.",
    ]
    if next_step:
        lines.append(f"Then take the next step: {next_step}")
    else:
        lines.append("Then continue from where that dialog ends.")
    return " ".join(lines)


def prune_old_generations(directory: Path, stem: str) -> None:
    """Keep the newest GENERATIONS_KEPT files of one family; delete older."""
    generations = sorted(directory.glob(f"{stem}-*.md"), key=lambda item: item.name)
    for stale in generations[:-GENERATIONS_KEPT]:
        stale.unlink()


def launch_agent_session(agent_command: str, session_id: str, working_directory: Path, prompt: str):
    """Start one interactive session, inheriting this console's terminal."""
    return subprocess.Popen(
        [agent_command, "--session-id", session_id, prompt],
        cwd=str(working_directory),
    )


def wait_for_handoff(process, handoff_path: Path, consumed_counter, state_path: Path, state: dict):
    """Block until the agent writes a new handoff, or the session exits.

    Returns the handoff fields when a counter above `consumed_counter`
    appears, or None if the session ended on its own. Stamps the heartbeat
    while it waits, so the watched agent can tell a live supervisor from a
    dead one.
    """
    last_stamp = 0.0
    while True:
        if process.poll() is not None:
            return None

        if time.monotonic() - last_stamp >= HEARTBEAT_INTERVAL_SECONDS:
            stamp_heartbeat(state_path, state)
            last_stamp = time.monotonic()

        if handoff_path.is_file():
            fields = parse_handoff_file(handoff_path)
            counter = counter_from(fields)
            if counter is not None and (consumed_counter is None or counter > consumed_counter):
                return fields

        time.sleep(HANDOFF_POLL_SECONDS)


def stop_session(process) -> None:
    process.terminate()
    try:
        process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        print("handoff-supervisor: session ignored terminate; killing", file=sys.stderr)
        process.kill()
        process.wait()


@dataclass
class SupervisorSettings:
    """Everything one supervisor needs, resolved from the command line."""

    agent: str
    working_directory: Path
    handoff_directory: Path
    agent_command: str
    first_prompt: str

    @property
    def handoff_path(self) -> Path:
        return self.handoff_directory / f"{self.agent}-handoff.md"

    @property
    def state_path(self) -> Path:
        return self.handoff_directory / f"{self.agent}-supervisor-state.json"


def carry_over_to_successor(settings: SupervisorSettings, retiring_session_id: str,
                            handoff_fields: dict, generation: int):
    """Extract, archive, prune, and build the successor's launch.

    Returns (successor_session_id, ignition_prompt), or (None, None) when
    extraction failed and relaunching would lose the dialog.
    """
    extract_path = settings.handoff_directory / f"{settings.agent}-dialog-{generation:04d}.md"
    extracted = extract_dialog(retiring_session_id, settings.working_directory, extract_path)
    if not extracted:
        print(
            "handoff-supervisor: extraction failed; not relaunching "
            "(the transcript is intact — recover by hand)",
            file=sys.stderr,
        )
        return None, None

    shutil.copy2(
        settings.handoff_path,
        settings.handoff_directory / f"{settings.agent}-handoff-{generation:04d}.md",
    )
    prune_old_generations(settings.handoff_directory, f"{settings.agent}-dialog")
    prune_old_generations(settings.handoff_directory, f"{settings.agent}-handoff")

    print(f"handoff-supervisor: {queue_status_line(settings.working_directory)}")

    successor_session_id = str(uuid.uuid4())
    copied = preseed_tasks(retiring_session_id, successor_session_id)
    print(f"handoff-supervisor: carried {copied} task record(s) to the successor")

    prompt = build_ignition_prompt(
        extract_path, handoff_fields, task_count_for(successor_session_id)
    )
    return successor_session_id, prompt


def supervise_sessions(settings: SupervisorSettings) -> int:
    """Launch, watch, and recycle sessions until one ends without a handoff."""
    state = read_supervisor_state(settings.state_path)
    session_id = state.get("session_id") or str(uuid.uuid4())
    generation = state.get("generation", 0)
    prompt = settings.first_prompt or (
        f"You are {settings.agent}. No handoff exists yet; ask what to work on."
    )

    print(f"handoff-supervisor: {settings.agent} in {settings.working_directory}")
    print(f"handoff-supervisor: watching {settings.handoff_path}")

    while True:
        state.update({"session_id": session_id, "generation": generation})
        write_supervisor_state(settings.state_path, state)

        print(f"handoff-supervisor: launching session {session_id} (generation {generation})")
        process = launch_agent_session(
            settings.agent_command, session_id, settings.working_directory, prompt
        )

        handoff_fields = wait_for_handoff(
            process, settings.handoff_path, state.get("consumed_counter"), settings.state_path, state
        )
        if handoff_fields is None:
            print("handoff-supervisor: session ended without a handoff; supervisor stopping")
            return 0

        stop_session(process)
        generation += 1

        if handoff_fields.get("dont-restart"):
            answer = input("handoff-supervisor: restart? y/n ").strip().lower()
            if answer != "y":
                print("handoff-supervisor: stopping at the agent's request")
                state["consumed_counter"] = counter_from(handoff_fields)
                write_supervisor_state(settings.state_path, state)
                return 0

        successor_session_id, prompt = carry_over_to_successor(
            settings, session_id, handoff_fields, generation
        )
        if successor_session_id is None:
            return 0

        state["consumed_counter"] = counter_from(handoff_fields)
        session_id = successor_session_id


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Run and recycle one agent session.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--agent", required=True, help="agent name; names the handoff and state files")
    parser.add_argument("--cd", default=".", help="the agent's worktree")
    parser.add_argument("--handoff-dir", default="~/.claude/handoffs", help="machine-local handoff directory")
    parser.add_argument("--agent-command", default="claude", help="the CLI to launch")
    parser.add_argument("--first-prompt", default="", help="prompt for the first session (no handoff yet)")
    parser.add_argument(
        "--check", action="store_true",
        help="report whether a supervisor is watching this agent, then exit (0 alive, 1 not)",
    )
    arguments = parser.parse_args(argv)

    if arguments.check:
        state_path = (
            Path(arguments.handoff_dir).expanduser() / f"{arguments.agent}-supervisor-state.json"
        )
        alive, explanation = supervisor_liveness(state_path)
        print(explanation)
        return 0 if alive else 1

    working_directory = Path(arguments.cd).expanduser().resolve()
    if not working_directory.is_dir():
        parser.error(f"--cd is not a directory: {working_directory}")
    if shutil.which(arguments.agent_command) is None:
        print(f"handoff-supervisor: no such command: {arguments.agent_command}", file=sys.stderr)
        return 3

    handoff_directory = Path(arguments.handoff_dir).expanduser()
    handoff_directory.mkdir(parents=True, exist_ok=True)

    return supervise_sessions(
        SupervisorSettings(
            agent=arguments.agent,
            working_directory=working_directory,
            handoff_directory=handoff_directory,
            agent_command=arguments.agent_command,
            first_prompt=arguments.first_prompt,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
