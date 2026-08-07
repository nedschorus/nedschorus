#!/usr/bin/env python3
"""Write the handoff file for a retiring session.

The handoff system's writer (specification:
docs/cross-project/fast-handoff-design.md). The retiring agent writes one
thing — the prompt telling its successor what to do first — and this script
fills in everything a machine can compute: the timestamp, the restart
counter, and the file's format.

Usage:
  handoff-write-file.py --agent <name> --next-step-file <path> [--dont-restart]

The next step arrives as a FILE rather than an argument so that backticks,
quotes, and newlines survive: a shell mangles all three inside an inline
argument. Newlines are collapsed to single spaces here, because the
supervisor reads the handoff as `key: value` lines and a value spanning
several lines would be silently truncated at the first one.

Exit codes: 0 written, 2 bad invocation or an empty next step.
"""

import argparse
import importlib.util
import json
import os
import re
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
        print(f"handoff-write-file: no such file: {next_step_path}", file=sys.stderr)
        return 2

    next_step = collapse_to_one_line(next_step_path.read_text(encoding="utf-8"))
    if not next_step:
        print(
            "handoff-write-file: the next-step file is empty — the successor would boot "
            "with no instruction, so nothing was written",
            file=sys.stderr,
        )
        return 2

    handoff_directory = Path(arguments.handoff_dir).expanduser()
    handoff_path = handoff_directory / f"{arguments.agent}-handoff.md"
    state_path = handoff_directory / f"{arguments.agent}-supervisor-state.json"

    counter = next_restart_counter(handoff_path, state_path)
    write_handoff_file(handoff_path, next_step, counter, arguments.dont_restart)

    print(f"handoff-write-file: wrote {handoff_path} (restart-counter {counter})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
