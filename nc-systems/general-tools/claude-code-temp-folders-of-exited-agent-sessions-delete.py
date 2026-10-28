#!/usr/bin/env python3
"""Delete the temporary folder of each Claude Code agent-session whose Claude Code process has exited.

    python3 <this file> [--dry-run] [--temp-parent DIR ...] [--sessions-directory DIR]
                        [--proc-directory DIR] [--projects-directory DIR]
                        [--minimum-age-seconds N]

Claude Code gives each agent-session a folder <parent>/claude-<uid>/<project>/<session id>/,
holding its background tasks' output (tasks/) and its scratchpad (scratchpad/). <parent> is
/tmp, or the directory CLAUDE_CODE_TMPDIR names. Claude Code does not delete the folder when the
agent-session ends; its retention sweep removes only the scratchpad, with the transcript, after
cleanupPeriodDays, 30 days by default. On ned-box /tmp is a tmpfs with a per-user quota, and the
folders have filled it, so every shell command in every agent-session failed. This program runs once
a day on ned-box and deletes those folders under both parents: /tmp, which agent-sessions
started before handoff-supervisor.py set CLAUDE_CODE_TMPDIR still use, and
/home/nedlern/.cache/claude-code-tmp, the value it sets. --temp-parent replaces that list.

WHICH AGENT-SESSIONS ARE LIVE. Each running Claude Code process keeps a file
<sessions directory>/<pid>.json, by default ~/.claude/sessions/, naming its pid, the id of the
agent-session it is running now (sessionId) and the process's start time (procStart, field 22
of /proc/<pid>/stat). An agent-session is live when some such file names it and its pid runs
with that start time; a pid the system has since given to another process has another start
time. A process that exits cleanly removes its file; one that crashed leaves a file whose pid
is gone. A <session id> folder no live agent-session names is deleted. A process that moved on
to another agent-session names only its current one, so the folder of its earlier one is deleted
too.

WHAT IS KEPT.
- The folder of a live agent-session.
- The folder of the agent-session crash recovery would resume for its <project>: the one
  scripts/recover-crashed-seats.py picks, the newest real transcript in
  <projects directory>/<project>/, by default ~/.claude/projects/. `claude --resume` reuses the
  folder, so a seat that crashed and stays down keeps its scratchpad and task output. When that
  transcript cannot be chosen, such as when <projects directory>/<project>/ cannot be read, that
  project's folders are all kept and the failure is reported; the run goes on with the other
  projects and exits 1. A project with no transcript keeps no folder for this reason.
- A folder changed within --minimum-age-seconds, default one hour: the folder itself or one of
  the entries directly inside it, so a process that made its folder before its sessions file
  keeps it.
- Everything under claude-<uid>/ that is not a <project>/<session id>/ folder, where the session
  id is a UUID: files there, such as cache-break-state-<session id>.json, and folders agents
  made by hand. A <project> folder this run emptied is removed.
The live set is read again just before each folder is deleted, so a session that started
during the run keeps its folder, unless it starts in the instant between that read and the
delete.

OUTPUT. A real run prints `deleting <folder>`, flushed, before it deletes each folder, so the
log names every folder a run stopped part way may have deleted, then a summary line. --dry-run
prints "would delete" and deletes nothing. A parent with no claude-<uid>/ folder is not a
failure: /home/nedlern/.cache/claude-code-tmp has none until an agent-session launched with it writes.

SCHEDULE. Once a day at 07:30 on ned-box, installed by
nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py from the table beside it,
scheduled-jobs-on-each-machine.json, where a change to the schedule is made. Linux only: it
reads /proc.

  ned-box: one cron line.

    30 7 * * * /usr/bin/python3 /home/nedlern/Projects/nedschorus/nc-systems/general-tools/claude-code-temp-folders-of-exited-agent-sessions-delete.py >> /home/nedlern/.claude/claude-code-temp-folders-of-exited-agent-sessions-delete.log 2>&1


Exit status: 0 when done; 1 when a failure stopped a deletion or the whole run. When the live set
cannot be read in full, because the sessions directory or a sessions file cannot be read or
parsed, or a process's start time cannot be read for a reason other than the process being
gone, nothing is deleted, since any folder might belong to the agent-session it would have
named. A folder that cannot be read or deleted, or a claude-<uid>/ folder that cannot be
listed, is reported and the run goes on to the others. Each failure is a line on stderr saying
what failed.
"""

import argparse
import errno
import importlib.util
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

# Messages follow docs/nedschorus-wiki/nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md.
PROGRAM_PATH_ON_NED_BOX = ("/home/nedlern/Projects/nedschorus/nc-systems/general-tools/"
                           "claude-code-temp-folders-of-exited-agent-sessions-delete.py")
FAILURES_INSTRUCTION = (
    "Each failure above left its folder in place, whole or in part; after \"nothing was "
    "deleted\", every folder. The next day's run tries again.\n"
    "To clear a failure now: find its cause from the error and fix it, then on ned-box run "
    "`python3 " + PROGRAM_PATH_ON_NED_BOX + " --dry-run`, which lists the folders it would delete "
    "and the failures it still meets, and then the same command without --dry-run, which deletes "
    "them.\n"
    "If you cannot fix the cause yourself, such as a folder only root may delete, tell the user "
    "which folder is kept and why, since ned-box's /tmp can fill up and stop every agent-session's "
    "shell commands; a subagent tells the agent that dispatched it instead.")

DEFAULT_CLAUDE_CODE_TEMP_FOLDER_PARENT_DIRECTORIES = ["/tmp", "/home/nedlern/.cache/claude-code-tmp"]
SESSION_FOLDER_NAME = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
EXIT_DONE = 0
EXIT_FAILED = 1

_worth_resuming_specification = importlib.util.spec_from_file_location(
    "seat_transcript_worth_resuming",
    Path(__file__).resolve().parents[2] / "scripts" / "agent-seat-transcript-worth-resuming-common.py")
worth_resuming = importlib.util.module_from_spec(_worth_resuming_specification)
_worth_resuming_specification.loader.exec_module(worth_resuming)


class LiveSessionsUnreadable(Exception):
    """The live set could not be read in full, so no folder may be deleted."""


def live_session_ids(sessions_directory: Path, proc_directory: Path) -> set:
    try:
        names = sorted(os.listdir(sessions_directory))
    except FileNotFoundError:
        # Claude Code makes the directory at its first start; with none, no session runs.
        return set()
    except OSError as error:
        raise LiveSessionsUnreadable(
            f"the sessions directory {sessions_directory} could not be listed: {error.strerror}")
    live = set()
    for name in names:
        if not name.endswith(".json"):
            continue
        path = sessions_directory / name
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            pid, session_id, start_time = (int(record["pid"]), str(record["sessionId"]),
                                           str(record["procStart"]))
        except FileNotFoundError:
            # Its process exited between the listing and this read.
            continue
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise LiveSessionsUnreadable(
                f"the sessions file {path}, Claude Code's record of one running process, could not "
                f"be read as pid, sessionId and procStart: {type(error).__name__}: {error}. While "
                "a sessions file cannot be read, any folder might belong to a live agent-session. "
                "If no process with the pid in the file's name runs, the file is stale: delete it")
        try:
            stat_fields = (proc_directory / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()
        except (FileNotFoundError, ProcessLookupError):
            continue
        except OSError as error:
            raise LiveSessionsUnreadable(
                f"the start time of pid {pid}, named by {path}, could not be read: {error.strerror}")
        # Fields after the parenthesised command start at field 3, so field 22 is index 19.
        if stat_fields[19] == start_time:
            live.add(session_id)
    return live


def newest_change(folder: Path) -> float:
    newest = folder.lstat().st_mtime
    with os.scandir(folder) as entries:
        for entry in entries:
            newest = max(newest, entry.stat(follow_symlinks=False).st_mtime)
    return newest


def claude_code_temp_folders_of_exited_agent_sessions_delete(temp_parents, sessions_directory: Path,
                                      proc_directory: Path, minimum_age_seconds: float,
                                      dry_run: bool, now=time.time,
                                      projects_directory: Path = Path.home() / ".claude" / "projects") -> dict:
    """Delete what may go, and return the counts and the failures, one line each."""
    result = {"deleted": 0, "kept_live": 0, "kept_resumable": 0, "kept_recent": 0, "failures": []}
    try:
        live = live_session_ids(sessions_directory, proc_directory)
    except LiveSessionsUnreadable as error:
        result["failures"].append(f"nothing was deleted: {error}")
        return result
    for parent in temp_parents:
        root = Path(parent) / f"claude-{os.getuid()}"
        try:
            projects = sorted((entry for entry in os.scandir(root) if entry.is_dir(follow_symlinks=False)),
                              key=lambda entry: entry.name)
        except FileNotFoundError:
            continue
        except OSError as error:
            result["failures"].append(f"{root} could not be listed: {error.strerror}")
            continue
        for project in projects:
            try:
                folders = sorted(entry.name for entry in os.scandir(project.path)
                                 if entry.is_dir(follow_symlinks=False)
                                 and SESSION_FOLDER_NAME.fullmatch(entry.name))
            except OSError as error:
                result["failures"].append(f"{project.path} could not be listed: {error.strerror}")
                continue
            transcripts = projects_directory / project.name
            try:
                # Path.glob in the chooser returns nothing for a folder it cannot read, which
                # would look like a project with no transcripts; listing it here raises instead.
                try:
                    with os.scandir(transcripts):
                        pass
                except FileNotFoundError:
                    pass
                resumable, _ = worth_resuming.newest_real_transcript(transcripts)
            except OSError as error:
                result["failures"].append(
                    f"the folders in {project.path} were kept: the transcript crash recovery would "
                    f"resume could not be chosen from {transcripts}: {error.filename}: {error.strerror}")
                continue
            deleted_here = False
            for name in folders:
                folder = Path(project.path) / name
                try:
                    if name in live:
                        result["kept_live"] += 1
                        continue
                    if name == resumable:
                        result["kept_resumable"] += 1
                        continue
                    if now() - newest_change(folder) < minimum_age_seconds:
                        result["kept_recent"] += 1
                        continue
                    if name in live_session_ids(sessions_directory, proc_directory):
                        result["kept_live"] += 1
                        continue
                    print(f"{'would delete' if dry_run else 'deleting'} {folder}", flush=True)
                    if not dry_run:
                        shutil.rmtree(folder)
                    result["deleted"] += 1
                    deleted_here = True
                except LiveSessionsUnreadable as error:
                    result["failures"].append(f"{folder} was kept: {error}")
                except OSError as error:
                    result["failures"].append(
                        f"{folder} could not be read or deleted in full: "
                        f"{error.filename}: {error.strerror}")
            if deleted_here and not dry_run:
                try:
                    os.rmdir(project.path)
                except OSError as error:
                    # Not empty, or gone: an agent-session wrote there, or another run removed it.
                    if error.errno in (errno.ENOTEMPTY, errno.EEXIST, errno.ENOENT):
                        continue
                    result["failures"].append(
                        f"the emptied folder {project.path} could not be removed: {error.strerror}")
    return result


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would be deleted, and delete nothing")
    parser.add_argument("--temp-parent", action="append", dest="temp_parents",
                        help="a directory holding a claude-<uid>/ folder; repeat for several; "
                             f"default {' and '.join(DEFAULT_CLAUDE_CODE_TEMP_FOLDER_PARENT_DIRECTORIES)}")
    parser.add_argument("--sessions-directory", type=Path,
                        default=Path.home() / ".claude" / "sessions",
                        help="where Claude Code keeps a <pid>.json file per running process")
    parser.add_argument("--proc-directory", type=Path, default=Path("/proc"),
                        help="the process table, for each pid's start time")
    parser.add_argument("--projects-directory", type=Path,
                        default=Path.home() / ".claude" / "projects",
                        help="where Claude Code keeps each project's transcripts")
    parser.add_argument("--minimum-age-seconds", type=float, default=3600,
                        help="keep a folder changed more recently than this")
    options = parser.parse_args(arguments)
    result = claude_code_temp_folders_of_exited_agent_sessions_delete(
        options.temp_parents or DEFAULT_CLAUDE_CODE_TEMP_FOLDER_PARENT_DIRECTORIES, options.sessions_directory,
        options.proc_directory, options.minimum_age_seconds, options.dry_run,
        projects_directory=options.projects_directory)
    for failure in result["failures"]:
        print(failure, file=sys.stderr)
    if result["failures"]:
        print(FAILURES_INSTRUCTION, file=sys.stderr)
    print(f"folders of exited agent-sessions "
          f"{'that would be deleted' if options.dry_run else 'deleted'}: {result['deleted']}; "
          f"folders kept because their agent-session is live: {result['kept_live']}; "
          f"folders kept because crash recovery would resume their agent-session: "
          f"{result['kept_resumable']}; "
          f"folders kept because they changed in the last {options.minimum_age_seconds:g} "
          f"seconds: {result['kept_recent']}; failures: {len(result['failures'])}", flush=True)
    return EXIT_FAILED if result["failures"] else EXIT_DONE


if __name__ == "__main__":
    sys.exit(main())
