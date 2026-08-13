#!/usr/bin/env python3
"""Write the handoff file for a retiring session, and report who is watching.

The handoff system's writer (specification:
docs/cross-project/fast-handoff-design.md). The retiring agent writes one
thing — the prompt telling its successor what to do first — and this script
does everything else a machine can do: it stamps the timestamp, derives the
restart counter, formats and writes the file, then checks whether a
supervisor is actually watching and tells the agent what that means for it.

Usage:
  handoff-write-and-check-supervisor.py --agent <name> --next-step-file <path>
                                        [--dont-restart]

The next step arrives as a FILE rather than an argument so that backticks,
quotes, and newlines survive: a shell mangles all three inside an inline
argument. Newlines are collapsed to single spaces here, because the
supervisor reads the handoff as `key: value` lines and a value spanning
several lines would be silently truncated at the first one.

The liveness report is part of this script rather than a second command
because the two are one decision: a handoff nobody is watching must not stop
the agent working, and an agent that runs only the first half of a two-step
procedure would stop anyway.

Exit codes: 0 written and a supervisor is watching, 1 written but nothing is
watching, 2 bad invocation or an empty next step.
"""

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_supervisor_spec = importlib.util.spec_from_file_location(
    "handoff_supervisor", Path(__file__).with_name("handoff-supervisor.py")
)
supervisor = importlib.util.module_from_spec(_supervisor_spec)
_supervisor_spec.loader.exec_module(supervisor)


def collapse_to_one_line(text: str) -> str:
    """Collapse every run of whitespace into a single space."""
    return re.sub(r"\s+", " ", text).strip()


def consumed_counter_from_state(state_path: Path):
    """Return the counter the supervisor has already acted on, if any."""
    if not state_path.is_file():
        return None
    try:
        value = json.loads(state_path.read_text(encoding="utf-8")).get("consumed_counter")
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None
    return value if isinstance(value, int) else None


def next_restart_counter(handoff_path: Path, state_path: Path) -> int:
    """Return a counter the supervisor is guaranteed to read as new.

    The previous handoff file is the ordinary source, but it can be missing,
    malformed, or older than what the supervisor has already consumed. Taking
    the higher of the two is what keeps this from writing a counter the
    supervisor will ignore — a silent failure to recycle, with a handoff on
    disk and nothing acting on it.
    """
    from_file = supervisor.counter_from(supervisor.parse_handoff_file(handoff_path)) \
        if handoff_path.is_file() else None
    from_state = consumed_counter_from_state(state_path)
    highest_seen = max(value for value in (from_file, from_state, 0) if value is not None)
    return highest_seen + 1


def write_handoff_file(handoff_path: Path, next_step: str, counter: int, dont_restart: bool) -> None:
    """Write the handoff file in one step, so no reader sees it half-written."""
    lines = [
        f"written-at: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"next-step: {next_step}",
        f"restart-counter: {counter}",
    ]
    if dont_restart:
        lines.append("dont-restart: the user asked to be consulted before a relaunch")

    handoff_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = handoff_path.with_suffix(handoff_path.suffix + ".partial")
    temporary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(temporary_path, handoff_path)


def app_hosted_ancestry(process_id: str) -> bool:
    """True when the session's process ancestry runs through the Claude desktop app.

    A supervisor takes over by killing the session and launching a successor on
    the same seat. A console seat survives that; the desktop app's conversation
    pane does not — its session process is a child of the app bundle, and a
    successor launched by a detached supervisor has no seat at all (observed
    2026-08-11: the successor ran its first turn and stalled at the first need
    for the user). The bundle's path in the ancestry is the observable
    difference between the two seats.
    """
    pid = process_id
    for _ in range(20):
        try:
            output = subprocess.run(
                ["ps", "-o", "ppid=,comm=", "-p", pid],
                capture_output=True, text=True, check=False,
            ).stdout.strip()
        except OSError:
            return False
        if not output:
            return False
        parts = output.split(None, 1)
        if len(parts) < 2:
            return False
        parent_pid, command = parts[0], parts[1]
        if "Claude.app" in command:
            return True
        if parent_pid in ("0", "1", pid):
            return False
        pid = parent_pid
    return False


def start_adopting_supervisor(agent: str, handoff_directory: Path):
    """Start a supervisor that adopts THIS session. Returns (started, detail).

    A supervisor normally launches the session it watches, so a session
    started by hand can never recycle — the founding boot included. The
    running session identifies itself from the environment, which is the only
    place both facts are available: CLAUDE_CODE_SESSION_ID and CLAUDE_PID.

    The supervisor is detached into its own process group so it survives the
    kill it is about to perform on this session.
    """
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    process_id = os.environ.get("CLAUDE_PID", "")
    if not session_id or not process_id.isdigit():
        return False, "this session does not report its id and process id in the environment"

    if app_hosted_ancestry(process_id):
        return False, (
            "this session is hosted by the Claude desktop app, and a supervisor cannot take "
            "over an app conversation — the successor it launches has no seat. Ask the user "
            "to clear this session and point the fresh one at the handoff file"
        )

    supervisor_path = Path(__file__).with_name("handoff-supervisor.py")
    log_path = handoff_directory / f"{agent}-supervisor.log"
    try:
        with log_path.open("ab") as log:
            # Deliberately not waited on: the supervisor outlives this script,
            # and the session that started it.
            subprocess.Popen(  # pylint: disable=consider-using-with
                [
                    sys.executable, str(supervisor_path),
                    "--agent", agent,
                    "--cd", str(Path.cwd()),
                    "--handoff-dir", str(handoff_directory),
                    "--adopt-session-id", session_id,
                    "--adopt-process-id", process_id,
                ],
                stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
    except OSError as error:
        return False, f"{error}"
    return True, f"started a supervisor for session {session_id} (its log is {log_path})"


def run_branch_protection_audit() -> str:
    """Slice 5's ruled anchor (2026-08-12): the branch-protection audit rides
    each session recycle. One line, never blocking — an unreadable wall is a
    named finding, and a broken audit must never break a handoff."""
    if os.environ.get("HANDOFF_SKIP_PROTECTION_AUDIT"):
        return "branch-protection audit: skipped (HANDOFF_SKIP_PROTECTION_AUDIT set)"
    gatekeeper_path = Path(__file__).with_name("git-gatekeeper.py")
    if not gatekeeper_path.is_file():
        return "branch-protection audit: audit-failed — no gatekeeper beside this script"
    try:
        completed = subprocess.run(
            [sys.executable, str(gatekeeper_path), "audit"],
            capture_output=True, text=True, check=False, timeout=45,
        )
        payload = json.loads(completed.stdout)
        return f"branch-protection audit: {payload.get('summary', completed.stdout.strip())}"
    except Exception as error:  # noqa: BLE001 - the audit never blocks a handoff
        return f"branch-protection audit: audit-failed — {type(error).__name__}: {error}"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Write the handoff file that retires this session.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--agent", required=True, help="agent name; names the handoff file")
    parser.add_argument(
        "--next-step-file", required=True,
        help="file holding the prompt for the successor; its whitespace is collapsed to one line",
    )
    parser.add_argument(
        "--dont-restart", action="store_true",
        help="ask the supervisor to confirm before relaunching, instead of relaunching automatically",
    )
    parser.add_argument("--handoff-dir", default="~/.claude/handoffs", help="machine-local handoff directory")
    arguments = parser.parse_args(argv)

    next_step_path = Path(arguments.next_step_file).expanduser()
    if not next_step_path.is_file():
        print(f"handoff-write-and-check-supervisor: no such file: {next_step_path}", file=sys.stderr)
        return 2

    next_step = collapse_to_one_line(next_step_path.read_text(encoding="utf-8"))
    if not next_step:
        print(
            "handoff-write-and-check-supervisor: the next-step file is empty — the successor would boot "
            "with no instruction, so nothing was written",
            file=sys.stderr,
        )
        return 2

    handoff_directory = Path(arguments.handoff_dir).expanduser()
    handoff_path = handoff_directory / f"{arguments.agent}-handoff.md"
    state_path = handoff_directory / f"{arguments.agent}-supervisor-state.json"

    counter = next_restart_counter(handoff_path, state_path)
    write_handoff_file(handoff_path, next_step, counter, arguments.dont_restart)
    print(f"handoff-write-and-check-supervisor: wrote {handoff_path} (restart-counter {counter})")
    print(f"handoff-write-and-check-supervisor: {run_branch_protection_audit()}")

    alive, explanation = supervisor.supervisor_liveness(state_path)
    if alive:
        print(
            f"handoff-write-and-check-supervisor: {explanation}. Stop working now and wait — "
            "it takes over within seconds."
        )
        return 0

    print(f"handoff-write-and-check-supervisor: {explanation}; starting one.")
    started, detail = start_adopting_supervisor(arguments.agent, handoff_directory)
    if started:
        print(
            f"handoff-write-and-check-supervisor: {detail}. Stop working now and wait — "
            "it takes over within seconds."
        )
        return 0

    print(
        f"handoff-write-and-check-supervisor: could not start a supervisor ({detail}). The handoff "
        "is written, but nothing will act on it: keep working, and tell the user.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
