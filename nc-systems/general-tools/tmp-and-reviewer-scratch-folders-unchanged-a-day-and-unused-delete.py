#!/usr/bin/env python3
"""Delete each folder in /tmp and in the merge-lane reviewers' scratch place that no keep-check keeps.

    python3 <this file> [--dry-run] [--tmp-directory-whose-folders-are-swept DIR]
        [--merge-lane-pull-request-reviewer-scratch-directories-parent-directory DIR]
        [--deleted-folders-log-file FILE] [--proc-filesystem-directory DIR]

Killed tests and finished reviews leave folders that nothing removes, and they have filled
ned-box's /tmp. This program looks at each entry directly inside two places: the tmp place,
--tmp-directory-whose-folders-are-swept, default /tmp; and the reviewer scratch place,
--merge-lane-pull-request-reviewer-scratch-directories-parent-directory,
default ~/.cache/merge-lane-pull-request-reviewer-scratch-directories. It deletes each entry,
whatever its name, unless a keep-check below keeps it. It runs once a day on ned-box as the second step of
claude-code-temp-folders-of-exited-agent-sessions-delete.py, which runs it when given
--then-tmp-and-reviewer-scratch-folders-unchanged-a-day-and-unused-delete; that job's entry in
scheduled-jobs-on-each-machine.json, beside this file, passes it.

WHAT IS KEPT. An entry is kept when any of these holds:
- it is a symbolic link or not a directory, or an account other than the one the program runs
  as, nedlern from the cron job, owns it;
- something in it changed in the last 24 hours: the newest modification time of the folder and
  of every entry under it, at any depth, is under 24 hours old, or in the future;
- a process uses it: a process of the running account has its working directory, root
  directory, executable, an open file or a file mapped into its memory inside it, or a unix
  socket of any account is bound to a path inside it, as tmux's server socket is in /tmp/tmux-<uid>. The
  process table, --proc-filesystem-directory, default /proc, and its net/unix are read just
  before the deletions; a process that cannot be read, such as another account's or one that
  exited during the reading, is not seen;
- in the reviewer scratch place, its name is rv followed by a pull request's number, with or
  without a suffix such as the -r3 of rv1643-r3, and that
  pull request is neither MERGED nor CLOSED as `gh pr list --state all` lists the repository this
  file is in. When the listing fails, or does not hold the number, the folder is kept and the
  failure reported. A folder there whose name gives no number has no pull request to wait for;
- in the tmp place, it is claude-<uid>, which the first step of the 07:30 job looks after, since
  that step keeps the folders of agent-sessions that can still be resumed.

OUTPUT. Before each deletion, `deleting <folder>` on stdout, flushed, and the line
`<UTC time><tab>deleting<tab><folder>` appended to the deleted-folders log in the log-store,
--deleted-folders-log-file, default
/home/nedlern/nedschorus-logs/tmp-and-reviewer-scratch-folders-deleted-log/ned-box.txt, so the
log names every folder a run stopped part way may have deleted; then a summary line on stdout.
--dry-run prints `would delete`, and deletes nothing and writes nothing to the log. No user-alert
is written.

Exit status: 0 when done; 1 when anything could not be checked or done: a place, the process
table or its net/unix that cannot be listed, an entry whose owner cannot be checked, a folder
whose tree cannot be read in full, a pull
request state that cannot be looked up, the log that cannot be written, or a folder that cannot
be deleted. Each failure is a line on stderr naming what was not checked or done and why. A
process table, net/unix or log that cannot be read or written stops the deletions; after any
other failure the run goes on with the other folders. A run with a failure exits 1 and never
reports that nothing was left behind. Linux only: it reads /proc.
"""

import argparse
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Messages follow docs/nedschorus-wiki/nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md.
GENERAL_TOOLS = Path(__file__).resolve().parent
REPOSITORY_ROOT = GENERAL_TOOLS.parents[1]
DEFAULT_TMP_PLACE = Path("/tmp")
DEFAULT_REVIEWER_SCRATCH_DIRECTORIES_PLACE = Path.home() / ".cache" / "merge-lane-pull-request-reviewer-scratch-directories"
DEFAULT_DELETED_FOLDERS_LOG_FILE = Path("/home/nedlern/nedschorus-logs/tmp-and-reviewer-scratch-folders-deleted-log/ned-box.txt")
UNCHANGED_SECONDS = 24 * 60 * 60
PULL_REQUEST_LISTING_LIMIT = 100000
PULL_REQUEST_LISTING_TIMEOUT_SECONDS = 300
REVIEWER_SCRATCH_DIRECTORY_PULL_REQUEST_NUMBER = re.compile(r"rv([0-9]+)")
CLAUDE_CODE_TEMP_FOLDER_THE_FIRST_STEP_LOOKS_AFTER = f"claude-{os.getuid()}"
EXIT_DONE = 0
EXIT_FAILED = 1

THIS_PROGRAM_PYTHON3_COMMAND_LINE_ON_NED_BOX = ("python3 " + str(GENERAL_TOOLS
                                             / "tmp-and-reviewer-scratch-folders-unchanged-a-day-and-unused-delete.py"))
FAILURES_INSTRUCTION = (
    "Each failure above, from the daily sweep of throwaway folders, kept the folders it names, or "
    "left the place it names unchecked; nothing was deleted that a failure names, and the next "
    "day's run tries again.\n"
    "To clear a failure now: find its cause from the error line and fix it, then on ned-box run "
    "`" + THIS_PROGRAM_PYTHON3_COMMAND_LINE_ON_NED_BOX + " --dry-run`, which lists what it would delete and the "
    "failures it still meets; when it lists no failure, run the same command without --dry-run, "
    "which deletes the folders it listed.\n"
    "If you cannot fix the cause yourself, such as a folder only root may delete, tell the user "
    "which folder or place is kept or unchecked, and why; a subagent tells the agent that "
    "dispatched it instead.")

_test_scratch_specification = importlib.util.spec_from_file_location(
    "test_scratch_directory_whose_earlier_killed_runs_leftovers_are_removed_first_common",
    GENERAL_TOOLS / "test-scratch-directory-whose-earlier-killed-runs-leftovers-are-removed-first-common.py")
test_scratch = importlib.util.module_from_spec(_test_scratch_specification)
_test_scratch_specification.loader.exec_module(test_scratch)


class NeededFileOrListingUnreadable(Exception):
    """A file or listing this run needs could not be read as it must be."""


def paths_processes_use(proc: Path) -> list:
    """Return every working directory, root, executable, open file and memory-mapped file of the
    readable processes, and every path a unix socket is bound to."""
    try:
        pids = sorted(name for name in os.listdir(proc) if name.isdigit())
    except OSError as error:
        raise NeededFileOrListingUnreadable(f"the process table {proc} could not be listed: {error.strerror}")
    try:
        # An open socket's fd link reads socket:[inode], so a bound socket's path is only here:
        # the eighth field of a line, when there is one. It is the path as given to bind(), which
        # may hold "//" or "/./", so it is normalized before it is compared.
        used = [os.path.normpath(fields[7]) for fields in (line.split(maxsplit=7)
                                         for line in (proc / "net" / "unix").read_text().splitlines()[1:])
                if len(fields) == 8]
    except OSError as error:
        raise NeededFileOrListingUnreadable(f"the unix socket table {proc / 'net' / 'unix'} could not be "
                                            f"read: {error.strerror}")
    for pid in pids:
        links = [proc / pid / "cwd", proc / pid / "root", proc / pid / "exe"]
        try:
            links += [proc / pid / "fd" / fd for fd in os.listdir(proc / pid / "fd")]
        except OSError:
            pass
        for link in links:
            try:
                used.append(os.readlink(link))
            except OSError:
                continue
        try:
            # The sixth field of a line, when there is one, is the path of a file mapped into memory.
            used += [fields[5] for fields in (line.split(maxsplit=5)
                                              for line in (proc / pid / "maps").read_text().splitlines())
                     if len(fields) == 6]
        except OSError:
            continue
    return used


def folder_used_by_any_process(folder: Path, used: list) -> bool:
    inside = str(folder) + "/"
    return any(path == str(folder) or path.startswith(inside) for path in used)


def pull_request_states(repository: Path) -> dict:
    command = ["gh", "pr", "list", "--state", "all", "--limit", str(PULL_REQUEST_LISTING_LIMIT),
               "--json", "number,state"]
    try:
        listing = subprocess.run(command, cwd=repository, capture_output=True, text=True, check=False,
                                 timeout=PULL_REQUEST_LISTING_TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise NeededFileOrListingUnreadable(f"`{shlex.join(command)}` could not be run: {error}")
    if listing.returncode != 0:
        raise NeededFileOrListingUnreadable(f"`{shlex.join(command)}` exited {listing.returncode}: "
                       f"{' '.join(listing.stderr.split())[:200] or 'no error text'}")
    try:
        return {int(pull_request["number"]): pull_request["state"]
                for pull_request in json.loads(listing.stdout)}
    except (ValueError, TypeError, KeyError) as error:
        raise NeededFileOrListingUnreadable(f"`{shlex.join(command)}` printed something other than a list of pull "
                       f"requests: {type(error).__name__}: {error}")


def pull_request_number_of(folder: Path, reviewer_scratch_place: Path):
    if folder.parent != reviewer_scratch_place:
        return None
    named = REVIEWER_SCRATCH_DIRECTORY_PULL_REQUEST_NUMBER.match(folder.name)
    return int(named.group(1)) if named else None


def tmp_and_reviewer_scratch_folders_unchanged_a_day_and_unused_delete(
        tmp_place: Path, reviewer_scratch_place: Path, deleted_folders_log_file: Path, proc: Path,
        dry_run: bool, now=time.time, repository: Path = REPOSITORY_ROOT) -> dict:
    """Delete each folder no keep-check keeps, and return the counts and failures."""
    result = {"deleted": 0, "kept_open_pull_request": 0, "kept_in_use": 0, "failures": []}
    # Resolved, because /proc gives each process's paths with every symlink resolved.
    tmp_place, reviewer_scratch_place = tmp_place.resolve(), reviewer_scratch_place.resolve()
    folders = []
    for place in (tmp_place, reviewer_scratch_place):
        try:
            entries = sorted(os.scandir(place), key=lambda entry: entry.name)
        except OSError as error:
            result["failures"].append(f"{place} was not checked: it could not be listed: {error.strerror}")
            continue
        for entry in entries:
            if place == tmp_place and entry.name == CLAUDE_CODE_TEMP_FOLDER_THE_FIRST_STEP_LOOKS_AFTER:
                continue
            try:
                if entry.is_dir(follow_symlinks=False) and entry.stat(follow_symlinks=False).st_uid == os.getuid():
                    folders.append(Path(entry.path))
            except FileNotFoundError:
                continue
            except OSError as error:
                result["failures"].append(f"{entry.path} was kept: it could not be checked: {error.strerror}")
    # The pull requests are looked up before the age check and the process snapshot, so that a
    # folder changed or put to use during the lookup, which may take minutes, is still seen.
    states = None
    if any(pull_request_number_of(folder, reviewer_scratch_place) is not None for folder in folders):
        try:
            states = pull_request_states(repository)
        except NeededFileOrListingUnreadable as error:
            states = error
    candidates = []
    for folder in folders:
        try:
            newest = test_scratch.newest_modification_time_in_tree(folder)
        except FileNotFoundError:
            continue
        except OSError as error:
            result["failures"].append(f"{folder} was kept: it could not be read in full: "
                                      f"{error.filename}: {error.strerror}")
            continue
        if now() - newest >= UNCHANGED_SECONDS:
            candidates.append(folder)
    try:
        used = paths_processes_use(proc)
    except NeededFileOrListingUnreadable as error:
        result["failures"].append(f"nothing was deleted: {error}")
        return result
    for folder in candidates:
        if folder_used_by_any_process(folder, used):
            result["kept_in_use"] += 1
            continue
        number = pull_request_number_of(folder, reviewer_scratch_place)
        if number is not None:
            if isinstance(states, NeededFileOrListingUnreadable):
                result["failures"].append(f"{folder} was kept: its pull request's state could not "
                                          f"be looked up: {states}")
                continue
            if number not in states:
                result["failures"].append(f"{folder} was kept: pull request {number}, read from its "
                                          "name, is not in the repository's list of pull requests")
                continue
            if states[number] not in ("MERGED", "CLOSED"):
                result["kept_open_pull_request"] += 1
                continue
        print(f"{'would delete' if dry_run else 'deleting'} {folder}", flush=True)
        if dry_run:
            result["deleted"] += 1
            continue
        try:
            deleted_folders_log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(deleted_folders_log_file, "a", encoding="utf-8") as log:
                log.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\tdeleting\t{folder}\n")
        except OSError as error:
            result["failures"].append(f"{folder} and every folder after it were kept: the deleted-folders "
                                      f"log could not be written: {error.filename}: {error.strerror}")
            return result
        try:
            shutil.rmtree(folder)
            result["deleted"] += 1
        except OSError as error:
            result["failures"].append(f"{folder} could not be deleted in full: {error.filename}: "
                                      f"{error.strerror}")
    return result


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would be deleted; delete nothing and write nothing to the log")
    parser.add_argument("--tmp-directory-whose-folders-are-swept", type=Path, default=DEFAULT_TMP_PLACE,
                        help="the tmp place, whose folders are deleted unless a keep-check keeps them")
    parser.add_argument("--merge-lane-pull-request-reviewer-scratch-directories-parent-directory", type=Path,
                        default=DEFAULT_REVIEWER_SCRATCH_DIRECTORIES_PLACE,
                        help="the merge-lane reviewers' scratch place, whose folders are also kept "
                             "until their pull request is merged or closed")
    parser.add_argument("--deleted-folders-log-file", type=Path, default=DEFAULT_DELETED_FOLDERS_LOG_FILE,
                        help="the log in the log-store each deleted folder is appended to")
    parser.add_argument("--proc-filesystem-directory", type=Path, default=Path("/proc"),
                        help="the process table, for the paths each process uses")
    options = parser.parse_args(arguments)
    result = tmp_and_reviewer_scratch_folders_unchanged_a_day_and_unused_delete(
        options.tmp_directory_whose_folders_are_swept, options.merge_lane_pull_request_reviewer_scratch_directories_parent_directory, options.deleted_folders_log_file,
        options.proc_filesystem_directory, options.dry_run)
    for failure in result["failures"]:
        print(failure, file=sys.stderr)
    if result["failures"]:
        print(FAILURES_INSTRUCTION, file=sys.stderr)
    print(f"throwaway folders {'that would be deleted' if options.dry_run else 'deleted'}: "
          f"{result['deleted']}; kept because their pull request is open: "
          f"{result['kept_open_pull_request']}; kept because a process uses them: "
          f"{result['kept_in_use']}; failures: {len(result['failures'])}", flush=True)
    return EXIT_FAILED if result["failures"] else EXIT_DONE


if __name__ == "__main__":
    sys.exit(main())
