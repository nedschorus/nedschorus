#!/usr/bin/env python3
"""Write the emergency-stop file: start a stop, add to the one in force, name
the agent-seat that coordinates the repair, record the push notification's
result, hand the lift to an agent-seat, and lift the stop.

The /emergency-stop skill runs this program; no agent writes the file by hand,
so its lines keep the exact form the hooks read. The folder and the stop
file's reading rules are in emergency-stop-file-in-force-read-common.py.

Subcommands:
  start --words TEXT | --evidence TEXT
      Starts a stop, or, when one is in force, appends the new words or
      evidence to it. The stop file is named by the UTC time and created with
      exclusive create, so of two agent-sessions starting at once one creates
      it and the other appends. The new file names the agent-seat running the
      program as the coordinating agent-seat, the repair brief beside it, a
      pending push notification, and the scheduled jobs, which keep running.
  coordinate --agent-seat NAME --words TEXT
      Names another coordinating agent-seat, on the user's word.
  push-notification sent | failed [--error TEXT]
      Records whether the push notification reached the user.
  hand-lift --agent-seat NAME --words TEXT
      Hands the lift to a named agent-seat; this does not lift the stop.
  lift --words TEXT
      Appends the lift line, `#emergency_stop_lifted <words>`, as the last line.
  status
      Prints the state the hooks see.

The agent-seat running the program is GIT_AUTHOR_NAME, which the launchers
export; --as-agent-seat overrides it.

Exit status: 0 on success; 1 with a line opening FAILED when the folder or
file cannot be written or read, or there is no stop to act on; 2 for bad
arguments. It never retries: an agent that cannot write the stop file tells the
user and stops only its own work."""

import argparse
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "emergency_stop_file_in_force_read_common", HERE / "emergency-stop-file-in-force-read-common.py")
common = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(common)

REPOSITORY_ROOT = HERE.parent.parent.parent
SCHEDULED_JOBS_FILE = REPOSITORY_ROOT / "nc-systems" / "general-tools" / "scheduled-jobs-on-each-machine.json"
HAND_LIFT_LINE_PREFIX = "#emergency_stop_lift_handed_over "


def now_utc():
    return datetime.now(timezone.utc).replace(microsecond=0)


def stop_file_name(moment):
    return moment.strftime("%Y-%m-%dT%H-%M-%SZ") + ".md"


def one_line(text):
    return " ".join(text.split())


def scheduled_job_lines(jobs_file):
    try:
        jobs = json.loads(jobs_file.read_text(encoding="utf-8"))["jobs"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        return [f"- the scheduled-jobs list {jobs_file} could not be read: {error}"]
    return [f"- {job['name']} ({', '.join(sorted(job.get('on', {})))}): {job['program']}" for job in jobs]


def new_stop_text(moment, path, agent_seat, kind, words, jobs_file):
    lines = [
        f"# Emergency stop started {moment.isoformat()}",
        "",
        f"started by: {agent_seat}",
        f"{kind}: {one_line(words)}",
        f"{common.COORDINATING_LINE_PREFIX}{agent_seat}",
        f"repair brief: {path.with_name(path.stem + '-repair-brief.md')}",
        "push notification: pending",
        "",
        "Scheduled jobs keep running during an emergency stop, pushes included; "
        "the coordinating agent-seat pauses by hand any that would harm the repair:",
        *scheduled_job_lines(jobs_file),
        "",
    ]
    return "\n".join(lines)


def append(path, line):
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(line.rstrip("\n") + "\n")


def failed(message):
    print(f"FAILED: {message}")
    return 1


def require_in_force(folder):
    state = common.read_state(folder)
    if isinstance(state, common.InForce):
        return state, None
    if isinstance(state, common.Unreadable):
        return None, f"the stop file {state.path} cannot be read: {state.error}"
    if isinstance(state, common.FolderUnreachable):
        return None, f"the emergency-stop folder {state.folder} cannot be reached: {state.error}"
    return None, f"no emergency stop is in force in {folder}"


def start(folder, agent_seat, kind, words, jobs_file, moment):
    state = common.read_state(folder)
    if isinstance(state, common.InForce):
        append(state.path, f"{moment.isoformat()} {kind} added by {agent_seat}: {one_line(words)}")
        return f"added to the emergency stop in force, {state.path}"
    if isinstance(state, common.FolderUnreachable):
        raise OSError(f"the emergency-stop folder {state.folder} cannot be reached: {state.error}")
    folder.mkdir(exist_ok=True)
    path = folder / stop_file_name(moment)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        append(path, f"{moment.isoformat()} {kind} added by {agent_seat}: {one_line(words)}")
        return f"added to the emergency stop started at the same second, {path}"
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(new_stop_text(moment, path, agent_seat, kind, words, jobs_file))
    return f"started the emergency stop {path}"


def run(arguments, environment):
    parser = argparse.ArgumentParser(description="Write the emergency-stop file.")
    parser.add_argument("--as-agent-seat")
    commands = parser.add_subparsers(dest="command", required=True)
    start_parser = commands.add_parser("start")
    source = start_parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--words")
    source.add_argument("--evidence")
    coordinate_parser = commands.add_parser("coordinate")
    coordinate_parser.add_argument("--agent-seat", required=True)
    coordinate_parser.add_argument("--words", required=True)
    push_parser = commands.add_parser("push-notification")
    push_parser.add_argument("result", choices=("sent", "failed"))
    push_parser.add_argument("--error", default="")
    hand_parser = commands.add_parser("hand-lift")
    hand_parser.add_argument("--agent-seat", required=True)
    hand_parser.add_argument("--words", required=True)
    lift_parser = commands.add_parser("lift")
    lift_parser.add_argument("--words", required=True)
    commands.add_parser("status")
    options = parser.parse_args(arguments)

    folder = common.emergency_stop_folder(environment)
    agent_seat = options.as_agent_seat or environment.get("GIT_AUTHOR_NAME")
    moment = now_utc()
    if options.command == "status":
        print(type(common.read_state(folder)).__name__)
        return 0
    if not agent_seat:
        return failed("no agent-seat is known: GIT_AUTHOR_NAME is unset; pass --as-agent-seat")
    try:
        if options.command == "start":
            kind, words = ("words", options.words) if options.words is not None else ("evidence", options.evidence)
            print(start(folder, agent_seat, kind, words, SCHEDULED_JOBS_FILE, moment))
            return 0
        state, problem = require_in_force(folder)
        if problem:
            return failed(problem)
        if options.command == "coordinate":
            append(state.path, f"{moment.isoformat()} named on the user's word, by {agent_seat}: "
                               f"{one_line(options.words)}")
            append(state.path, f"{common.COORDINATING_LINE_PREFIX}{options.agent_seat}")
        elif options.command == "push-notification":
            detail = f": {one_line(options.error)}" if options.error else ""
            append(state.path, f"push notification: {options.result} at {moment.isoformat()}{detail}")
        elif options.command == "hand-lift":
            append(state.path, f"{HAND_LIFT_LINE_PREFIX}{options.agent_seat} {one_line(options.words)}")
        elif options.command == "lift":
            append(state.path, f"{moment.isoformat()} lifted by {agent_seat}")
            append(state.path, f"{common.LIFT_LINE_PREFIX}{one_line(options.words)}")
        print(f"{options.command}: written to {state.path}")
        return 0
    except OSError as error:
        return failed(f"the emergency-stop file could not be written: {error}")


def main():
    return run(sys.argv[1:], os.environ)


if __name__ == "__main__":
    sys.exit(main())
