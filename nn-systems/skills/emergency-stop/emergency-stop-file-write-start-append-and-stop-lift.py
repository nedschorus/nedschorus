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
      evidence to it. The stop file is named by the UTC time, or, when the
      newest stop file is lifted and this machine's clock is behind the one
      that wrote it, by the second after that file's, so the new file sorts
      newest and is the one in force. Its whole text
      is written to a temporary file in the folder first, which is then
      hard-linked to the stop file's name, so a failed write leaves no
      partial stop file, and of two agent-sessions starting in the same second
      one creates it and the other appends. The new file names the agent-seat
      running the program as the coordinating agent-seat, the repair brief
      beside it, a pending push notification, and the scheduled jobs, which
      keep running. When the newest stop file cannot be read, start prints
      FAILED: that file counts as a stop in force, and a new file would hide it.
      After writing, start reads the folder again; when the stop it wrote or
      added to is not the one in force, it writes and reads back once more.
      When that succeeds, it deletes the first try's stop file unless that
      file is the one in force; when it also fails, it deletes the stop files
      it created, so a failed start never comes into force later, and prints
      FAILED, saying what the folder now holds.
  coordinate --agent-seat NAME --words TEXT
      Names another coordinating agent-seat, on the user's word.
  push-notification sent | failed [--error TEXT]
      Records whether the push notification reached the user.
  hand-over-lift --agent-seat NAME --words TEXT
      Hands the lift to a named agent-seat; this does not lift the stop.
  lift --words TEXT
      Appends the lift line, `#emergency_stop_lifted <words>`, as the last line.
  status
      Prints the state the hooks see.

The agent-seat running the program is GIT_AUTHOR_NAME, which the launchers
export; --as-agent-seat overrides it.

Exit status: 0 on success; 1 with a line opening FAILED when the folder or
file cannot be written or read, or there is no stop to act on; 2 for bad
arguments. Apart from start's second write after a failed read-back, it never
retries: an agent that cannot write the stop file tells the user and stops only
its own work."""

import argparse
import importlib.util
import json
import os
import shlex
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROGRAM_PATH = "nn-systems/skills/emergency-stop/emergency-stop-file-write-start-append-and-stop-lift.py"
_spec = importlib.util.spec_from_file_location(
    "emergency_stop_file_in_force_read_common", HERE / "emergency-stop-file-in-force-read-common.py")
common = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(common)

REPOSITORY_ROOT = HERE.parent.parent.parent
SCHEDULED_JOBS_FILE = REPOSITORY_ROOT / "nn-systems" / "general-tools" / "scheduled-jobs-on-each-machine.json"
HAND_OVER_LIFT_LINE_PREFIX = "#emergency_stop_lift_handed_over "


def now_utc():
    return datetime.now(timezone.utc).replace(microsecond=0)


STOP_FILE_NAME_TIME_FORMAT = "%Y-%m-%dT%H-%M-%SZ"


def stop_file_name(moment):
    return moment.strftime(STOP_FILE_NAME_TIME_FORMAT) + ".md"


def name_moment_after(moment, newest_path):
    """moment, or the second after newest_path's name when moment does not sort after it.

    The stop in force is the newest by file name, and machines' clocks differ, so a new stop file must be
    named after the newest one whatever this machine's clock says."""
    newest = datetime.strptime(newest_path.stem, STOP_FILE_NAME_TIME_FORMAT).replace(tzinfo=timezone.utc)
    return moment if moment > newest else newest + timedelta(seconds=1)


def one_line(text):
    return " ".join(text.split())


def scheduled_job_lines(jobs_file):
    try:
        jobs = json.loads(jobs_file.read_text(encoding="utf-8"))["jobs"]
        return [f"- {job['name']} ({', '.join(sorted(job.get('on', {})))}): {job['program']}" for job in jobs]
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        return [f"- the scheduled-jobs list {jobs_file} could not be read: {error!r}"]


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


def rerun_command(arguments):
    """The command line that runs this program again with the same arguments, to paste into a task."""
    return f"python3 {PROGRAM_PATH} {shlex.join(arguments)}"


def require_in_force(folder, rerun):
    state = common.read_state(folder)
    if isinstance(state, common.InForce):
        return state, None
    if isinstance(state, common.Unreadable):
        return None, f"the emergency-stop file {state.path} cannot be read: {state.error}"
    if isinstance(state, common.FolderUnreachable):
        return None, (f"the emergency-stop folder {state.folder} cannot be reached: {state.error}; nothing was "
                      "written, so the folder holds what it held before. While this machine cannot reach the "
                      "folder, its emergency-stop hook refuses no pushes or merges here."
                      f"\nAdd a task to run this command again once this machine can reach that folder: {rerun}"
                      "\nTell the user now that this machine cannot reach that folder.")
    return None, f"no emergency stop is in force in {folder}"


class StartRefused(Exception):
    """start cannot act without hiding or losing a stop; the message says why."""


class ReadBackNotInForce(Exception):
    """start wrote its stop, but the folder read back did not hold that stop in force."""


def start(folder, agent_seat, kind, words, jobs_file, moment, rerun=None):
    rerun = rerun or rerun_command(["start", f"--{kind}", words])
    created = []
    try:
        return start_once(folder, agent_seat, kind, words, jobs_file, moment, rerun, created)[0]
    except ReadBackNotInForce:
        pass
    try:
        report, in_force_path = start_once(folder, agent_seat, kind, words, jobs_file, moment, rerun, created)
    except (StartRefused, ReadBackNotInForce) as failure:
        for path in created:
            path.unlink()
        if isinstance(failure, StartRefused):
            raise
        state = common.read_state(folder)
        raise StartRefused("start wrote its emergency stop and read the emergency-stop folder back, twice, and "
                           "neither time found its stop in force, so it deleted the stop files it wrote. A read of "
                           f"the folder now finds that {folder_state_description(state)}. {refused_clause(state)}"
                           f"\nTell the user this whole message.\nRun start again only if the user says to: {rerun}")
    for path in created:
        # The second try can append to the first try's file, which is then the stop in force.
        if path != in_force_path:
            path.unlink()
    return report


def start_once(folder, agent_seat, kind, words, jobs_file, moment, rerun, created):
    """(report, path of the stop file in force); appends each stop file it creates to created.

    Raises ReadBackNotInForce when the folder read back after the write does not hold its stop in force."""
    state = common.read_state(folder)
    if isinstance(state, common.InForce):
        append(state.path, f"{moment.isoformat()} {kind} added by {agent_seat}: {one_line(words)}")
        return f"added to the emergency stop in force, {state.path}", state.path
    if isinstance(state, common.Unreadable):
        raise StartRefused(f"start wrote no emergency-stop file: the newest emergency-stop file, {state.path}, "
                           f"cannot be read: {state.error}. That unreadable file already counts as an emergency "
                           "stop in force, so pushes and merges stay refused; writing a newer emergency-stop file "
                           "would hide the unreadable one.\nTell the user the file's path and this error, and "
                           "leave the file as it is: only the user repairs or moves it.")
    if isinstance(state, common.FolderUnreachable):
        raise StartRefused(f"start wrote nothing: the emergency-stop folder {state.folder} cannot be reached: "
                           f"{state.error}. No emergency stop was started. This machine cannot tell whether "
                           "another emergency stop is in force, so its emergency-stop hook refuses no pushes or "
                           "merges here.\nTell the user at once that the emergency stop was not started, and why."
                           f"\nRun this command again only if the user says to: {rerun}")
    folder.mkdir(exist_ok=True)
    named = name_moment_after(moment, state.path) if isinstance(state, common.Lifted) else moment
    path = folder / stop_file_name(named)
    text = new_stop_text(moment, path, agent_seat, kind, words, jobs_file)
    descriptor, temporary = tempfile.mkstemp(dir=folder, prefix=".", suffix=".partial")
    try:
        os.fchmod(descriptor, 0o644 & ~current_umask())
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.link(temporary, path)
    except FileExistsError:
        append(path, f"{moment.isoformat()} {kind} added by {agent_seat}: {one_line(words)}")
        return in_force_check(folder, path, f"added to the emergency stop started at the same second, {path}")
    finally:
        os.unlink(temporary)
    created.append(path)
    return in_force_check(folder, path, f"started the emergency stop {path}")


def in_force_check(folder, path, report):
    """(report, path) when the stop file at path is the one in force; else raises ReadBackNotInForce."""
    state = common.read_state(folder)
    if isinstance(state, common.InForce) and state.path == path:
        return report, path
    raise ReadBackNotInForce()


def folder_state_description(state):
    if isinstance(state, common.InForce):
        return f"the emergency-stop file in force is {state.path}"
    if isinstance(state, common.Lifted):
        return f"the newest emergency-stop file, {state.path}, is lifted"
    if isinstance(state, common.Unreadable):
        return f"the newest emergency-stop file, {state.path}, cannot be read: {state.error}"
    if isinstance(state, common.FolderUnreachable):
        return f"the folder {state.folder} cannot be reached: {state.error}"
    return f"no emergency-stop file in {state.folder} is in force"


def refused_clause(state):
    """Whether the push-and-merge refusal hook refuses pushes and merges, given the state it reads."""
    if isinstance(state, (common.InForce, common.Unreadable)):
        return "So an emergency stop counts as in force, and pushes and merges are refused."
    if isinstance(state, common.FolderUnreachable):
        return ("So no one on this machine can tell whether an emergency stop is in force, and pushes and "
                "merges are not refused here.")
    return "So no emergency stop is in force, and pushes and merges are not refused."


def failed_write_message(command, folder, error, rerun):
    state = common.read_state(folder)
    last_line = (f"Run this command again only if the user says to: {rerun}" if command == "start"
                 else f"Add a task to run this command again once a write to that folder can succeed: {rerun}")
    return (f"{command} could not finish writing to the emergency-stop folder {folder}: {error}. A read of the "
            f"folder now finds that {folder_state_description(state)}. {refused_clause(state)}"
            f"\nTell the user this whole message.\n{last_line}")


def without_agent_seat_option(arguments):
    """arguments from the subcommand on: the --as-agent-seat option before it is dropped."""
    rest = list(arguments)
    while rest and rest[0].startswith("--as-agent-seat"):
        rest = rest[2:] if rest[0] == "--as-agent-seat" else rest[1:]
    return rest


def current_umask():
    mask = os.umask(0)
    os.umask(mask)
    return mask


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
    hand_parser = commands.add_parser("hand-over-lift")
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
        return failed(f"{options.command} wrote nothing: no agent-seat is known, because GIT_AUTHOR_NAME is "
                      f"unset or empty.\nRun this command, with your agent-seat's name in place of "
                      f"<your agent-seat name>:\npython3 {PROGRAM_PATH} --as-agent-seat <your agent-seat name> "
                      f"{shlex.join(without_agent_seat_option(arguments))}")
    try:
        if options.command == "start":
            kind, words = ("words", options.words) if options.words is not None else ("evidence", options.evidence)
            print(start(folder, agent_seat, kind, words, SCHEDULED_JOBS_FILE, moment, rerun_command(arguments)))
            return 0
        state, problem = require_in_force(folder, rerun_command(arguments))
        if problem:
            return failed(problem)
        if options.command == "coordinate":
            append(state.path, f"{moment.isoformat()} named on the user's word, by {agent_seat}: "
                               f"{one_line(options.words)}")
            append(state.path, f"{common.COORDINATING_LINE_PREFIX}{options.agent_seat}")
        elif options.command == "push-notification":
            detail = f": {one_line(options.error)}" if options.error else ""
            append(state.path, f"push notification: {options.result} at {moment.isoformat()}{detail}")
        elif options.command == "hand-over-lift":
            append(state.path, f"{HAND_OVER_LIFT_LINE_PREFIX}{options.agent_seat} {one_line(options.words)}")
        elif options.command == "lift":
            append(state.path, f"{moment.isoformat()} lifted by {agent_seat}")
            append(state.path, f"{common.LIFT_LINE_PREFIX}{one_line(options.words)}")
        print(f"{options.command}: written to {state.path}")
        return 0
    except StartRefused as refusal:
        return failed(str(refusal))
    except OSError as error:
        return failed(failed_write_message(options.command, folder, error, rerun_command(arguments)))


def main():
    return run(sys.argv[1:], os.environ)


if __name__ == "__main__":
    sys.exit(main())
