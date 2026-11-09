#!/usr/bin/env python3
"""Delete the throwaway folders of each kind the user approved for deletion, and show him each other kind once.

    python3 <this file> [--dry-run] [--approved-kinds-file FILE] [--kinds-shown-state-file FILE]
                        [--proc-filesystem-directory DIR]

Killed tests and finished reviews leave folders that nothing removes, and they have filled
ned-box's /tmp. This program deletes such a folder only when its kind is in the approved-kinds
file, by default throwaway-folder-kinds-the-user-approved-for-deletion.json beside this file,
to which only the user's answer adds a kind. It runs once a day on ned-box as the second step of
claude-code-temp-folders-of-exited-agent-sessions-delete.py, which runs it when given
--then-throwaway-folders-of-user-approved-kinds-delete; that job's entry in
scheduled-jobs-on-each-machine.json, beside this file, passes it.

THE APPROVED-KINDS FILE is a JSON object whose `kinds` list holds one object per kind:
`kind`, its name; `place`, the directory the folders are in, `~` meaning the home directory;
`name`, a regular expression the folder's whole name matches; `holding`, the name of an entry
the folder must hold directly inside it, or null; `only_once_its_pull_request_is_merged_or_closed`,
true when the folder is deleted only after the pull request whose number the expression's
group `pull_request` reads from the name is merged or closed; and `approved`, where the user
approved the kind. A file that cannot be read or is malformed stops the run before anything is
deleted.

WHAT IS DELETED. A folder directly inside a kind's place that matches the kind, and also:
- is a directory, not a symbolic link, owned by the account the program runs as, nedlern from
  the cron job;
- has nothing in it, at any depth, changed for 24 hours: the newest modification time of the
  folder and of every entry under it is over 24 hours old, so a folder with a time in the future
  is kept;
- is used by no process: no process of the running account has its working directory, root
  directory, executable, an open file or a file mapped into its memory inside it. The process table, --proc-filesystem-directory,
  default /proc, is read just before the deletions; a process that cannot be read, such as
  another account's or one that exited during the reading, is not seen;
- for a kind with only_once_its_pull_request_is_merged_or_closed, its pull request is MERGED or
  CLOSED as `gh pr list --state all` lists the repository this file is in. When the listing
  fails, or does not hold the number, the folder is kept and the failure reported.

WHAT IS SHOWN. A folder in a kind's place that passes the first three tests above but matches no
approved kind is a leftover of an unapproved kind, apart from the folders another program
removes: claude-<uid> (the first step of the 07:30 job), and run-all-test-suites- or rts- followed
by mkdtemp's eight characters (scripts/run-all-test-suites.py). Such a folder's kind is found from its name by one fixed rule:
when the name ends in `-` or `_` followed by eight characters of [a-z0-9_], the suffix
tempfile.mkdtemp adds, or is `tmp` followed by eight such characters, or ends in `.` followed by
six or more letters and digits, the suffix the shell's mktemp adds, the kind is the name with
that suffix replaced by `*`, so pymp-a1b2c3d4 is `pymp-*`, tmpab_12cde is `tmp*` and
tmp.Xq3vT9aBcD is `tmp.*`;
otherwise the kind is the name up to its first digit followed by `*`, so rv2144r1 is `rv*`; a name
with no digit is its own kind. Each unapproved kind is printed on every run with its folder count,
file count and size. The first run that finds a kind writes a user-alert for it, with the
user-alerts module beside this file, and records the kind in --kinds-shown-state-file, default
~/.local/state/nedschorus/throwaway-folder-kinds-shown-to-the-user.json, so each kind is raised
once.

OUTPUT. `deleting <folder>`, flushed, before each deletion, so the log names every folder a run
stopped part way may have deleted; then each unapproved kind; then a summary line. --dry-run
prints `would delete`, and deletes nothing, writes no user-alert and records no kind as shown.

Exit status: 0 when done; 1 when anything could not be checked or done: the approved-kinds file
unreadable or malformed (nothing is deleted), a place or the process table that cannot be listed,
a folder whose tree cannot be read in full, a pull request state that cannot be looked up, a
folder that cannot be deleted, or a user-alert or the state file that cannot be written. Each
failure is a line on stderr naming the place or folder not checked and why, and the run goes on
with the others, so a run with a failure never reports that nothing was left behind. Linux only:
it reads /proc.
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
DEFAULT_APPROVED_KINDS_FILE = GENERAL_TOOLS / "throwaway-folder-kinds-the-user-approved-for-deletion.json"
APPROVED_KINDS_FILE_IN_THE_REPOSITORY = ("nc-systems/general-tools/"
                                         "throwaway-folder-kinds-the-user-approved-for-deletion.json")
KINDS_SHOWN_STATE_FILE_RELATIVE_TO_HOME = (Path(".local") / "state" / "nedschorus"
                                           / "throwaway-folder-kinds-shown-to-the-user.json")
UNCHANGED_SECONDS = 24 * 60 * 60
PULL_REQUEST_LISTING_LIMIT = 100000
PULL_REQUEST_LISTING_TIMEOUT_SECONDS = 300
KIND_FIELDS = ("kind", "place", "name", "holding", "only_once_its_pull_request_is_merged_or_closed",
               "approved")
EXAMPLES_IN_AN_ALERT = 5
EXIT_DONE = 0
EXIT_FAILED = 1

FAILURES_INSTRUCTION = (
    "Each failure above kept its folders, or left a place unchecked; the next day's run tries again.\n"
    "To clear a failure now: find its cause from the error and fix it, then on ned-box run "
    "`python3 " + str(REPOSITORY_ROOT / "nc-systems" / "general-tools"
                      / "throwaway-folders-of-user-approved-kinds-delete.py") + " --dry-run`, which "
    "lists what it would delete and the failures it still meets.\n"
    "If you cannot fix the cause yourself, tell the user which place or folder is unchecked and "
    "why; a subagent tells the agent that dispatched it instead.")
ALERT_TITLE_TEMPLATE = "Throwaway folders of a kind not approved for deletion: {place}/{kind}"
ALERT_TEXT_TEMPLATE = (
    "The daily throwaway-folder sweep on ned-box found {folders} folders of kind `{kind}` in "
    "{place}, owned by nedlern, unchanged for 24 hours and used by no process: {files} files, "
    "{megabytes:.1f} MB. Some of them: {examples}. The sweep deletes only kinds the user approved "
    "in " + APPROVED_KINDS_FILE_IN_THE_REPOSITORY + ", and this kind is not there, so it keeps them "
    "and raises this kind only this once.")
ALERT_ACTION_TEXT = (
    "Only the user can approve a kind for deletion. If he approves this one, an agent on ned-box "
    "adds it to " + APPROVED_KINDS_FILE_IN_THE_REPOSITORY + " in a pull request, with a `name` "
    "expression that matches only folders of this kind and his answer as `approved`. If he does "
    "not, nothing needs doing.")

_user_alerts_specification = importlib.util.spec_from_file_location(
    "user_alerts_pending_and_claimed_files_write_claim_release_and_delete_common",
    GENERAL_TOOLS / "user-alerts-pending-and-claimed-files-write-claim-release-and-delete-common.py")
user_alerts = importlib.util.module_from_spec(_user_alerts_specification)
_user_alerts_specification.loader.exec_module(user_alerts)
_test_scratch_specification = importlib.util.spec_from_file_location(
    "test_scratch_directory_whose_earlier_killed_runs_leftovers_are_removed_first_common",
    GENERAL_TOOLS / "test-scratch-directory-whose-earlier-killed-runs-leftovers-are-removed-first-common.py")
test_scratch = importlib.util.module_from_spec(_test_scratch_specification)
_test_scratch_specification.loader.exec_module(test_scratch)

RANDOM_SUFFIX_AT_THE_END = re.compile(r"(.*(?:[-_]|^tmp))" + test_scratch.MKDTEMP_SUFFIX_SHAPE
                                      + r"|(.*\.)[A-Za-z0-9]{6,}")
REMOVED_BY_ANOTHER_PROGRAM = re.compile(rf"claude-{os.getuid()}|(?:run-all-test-suites-|rts-)"
                                        + test_scratch.MKDTEMP_SUFFIX_SHAPE)


class Unusable(Exception):
    """A file or listing this run needs could not be read as it must be."""


def approved_kinds_read(path: Path) -> list:
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise Unusable(f"the approved-kinds file {path} could not be read as JSON: "
                       f"{type(error).__name__}: {error}")
    kinds = content.get("kinds") if isinstance(content, dict) else None
    if not isinstance(kinds, list):
        raise Unusable(f"the approved-kinds file {path} holds no `kinds` list")
    for kind in kinds:
        if not isinstance(kind, dict) or set(kind) != set(KIND_FIELDS):
            raise Unusable(f"an entry of the approved-kinds file {path} does not have exactly the "
                           f"fields {', '.join(KIND_FIELDS)}: {json.dumps(kind)}")
        try:
            pattern = re.compile(kind["name"])
        except (re.error, TypeError) as error:
            raise Unusable(f"the `name` of kind {kind['kind']!r} in {path} is not a regular "
                           f"expression: {error}")
        if kind["only_once_its_pull_request_is_merged_or_closed"] is True:
            if "pull_request" not in pattern.groupindex:
                raise Unusable(f"kind {kind['kind']!r} in {path} is deleted only once its pull "
                               "request is merged or closed, but its `name` has no group "
                               "`pull_request` to read the number from")
        elif kind["only_once_its_pull_request_is_merged_or_closed"] is not False:
            raise Unusable(f"kind {kind['kind']!r} in {path}: "
                           "only_once_its_pull_request_is_merged_or_closed must be true or false")
        if not isinstance(kind["place"], str) or not (kind["holding"] is None
                                                      or isinstance(kind["holding"], str)):
            raise Unusable(f"kind {kind['kind']!r} in {path}: `place` must be a string and "
                           "`holding` a string or null")
        kind["pattern"] = pattern
        kind["place_path"] = Path(kind["place"]).expanduser()
    return kinds


def tree_measure(folder: Path):
    """Return (newest modification time, entries, bytes) of the folder and everything under it;
    raise OSError when any part cannot be read, since an unread part may be the newest."""
    status = folder.lstat()
    newest, entries, size = status.st_mtime, 1, 0

    def fail(error):
        raise error
    for parent, subdirectories, files in os.walk(folder, onerror=fail):
        for name in subdirectories + files:
            status = os.lstat(os.path.join(parent, name))
            newest, entries, size = max(newest, status.st_mtime), entries + 1, size + status.st_size
    return newest, entries, size


def paths_processes_use(proc: Path) -> list:
    """Return every working directory, root, executable and open file of the readable processes."""
    try:
        pids = [name for name in os.listdir(proc) if name.isdigit()]
    except OSError as error:
        raise Unusable(f"the process table {proc} could not be listed: {error.strerror}")
    used = []
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


def in_use(folder: Path, used: list) -> bool:
    inside = str(folder) + "/"
    return any(path == str(folder) or path.startswith(inside) for path in used)


def pull_request_states(repository: Path) -> dict:
    command = ["gh", "pr", "list", "--state", "all", "--limit", str(PULL_REQUEST_LISTING_LIMIT),
               "--json", "number,state"]
    try:
        listing = subprocess.run(command, cwd=repository, capture_output=True, text=True, check=False,
                                 timeout=PULL_REQUEST_LISTING_TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise Unusable(f"`{shlex.join(command)}` could not be run: {error}")
    if listing.returncode != 0:
        raise Unusable(f"`{shlex.join(command)}` exited {listing.returncode}: "
                       f"{' '.join(listing.stderr.split())[:200] or 'no error text'}")
    try:
        return {int(pull_request["number"]): pull_request["state"]
                for pull_request in json.loads(listing.stdout)}
    except (ValueError, TypeError, KeyError) as error:
        raise Unusable(f"`{shlex.join(command)}` printed something other than a list of pull "
                       f"requests: {type(error).__name__}: {error}")


def unapproved_kind_of(name: str) -> str:
    suffixed = RANDOM_SUFFIX_AT_THE_END.fullmatch(name)
    if suffixed:
        return (suffixed.group(1) or suffixed.group(2)) + "*"
    digit = re.search(r"[0-9]", name)
    return name[:digit.start()] + "*" if digit else name


def approved_kind_matching(folder: Path, kinds_here: list):
    for kind in kinds_here:
        if kind["pattern"].fullmatch(folder.name) and (
                kind["holding"] is None or (folder / kind["holding"]).exists()):
            return kind
    return None


def kinds_shown_read(path: Path) -> dict:
    try:
        shown = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as error:
        raise Unusable(f"the state file {path} could not be read as JSON: {type(error).__name__}: {error}")
    if not isinstance(shown, dict):
        raise Unusable(f"the state file {path} holds no JSON object")
    return shown


def kinds_shown_write(path: Path, shown: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    written = path.with_name(path.name + ".being-written")
    written.write_text(json.dumps(shown, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.rename(written, path)


def throwaway_folders_of_user_approved_kinds_delete(approved_kinds_file: Path, kinds_shown_state_file: Path,
                                                    proc: Path, dry_run: bool, now=time.time,
                                                    repository: Path = REPOSITORY_ROOT) -> dict:
    """Delete what may go, show the unapproved kinds, and return the counts, kinds and failures."""
    result = {"deleted": 0, "kept_open_pull_request": 0, "kept_in_use": 0, "unapproved": {},
              "failures": []}
    try:
        kinds = approved_kinds_read(approved_kinds_file)
    except Unusable as error:
        result["failures"].append(f"nothing was deleted: {error}")
        return result
    places = {}
    for kind in kinds:
        places.setdefault(kind["place_path"], []).append(kind)
    candidates, leftovers = [], []
    for place, kinds_here in places.items():
        try:
            entries = sorted(os.scandir(place), key=lambda entry: entry.name)
        except OSError as error:
            result["failures"].append(f"{place} was not checked: it could not be listed: {error.strerror}")
            continue
        for entry in entries:
            folder = Path(entry.path)
            try:
                if not entry.is_dir(follow_symlinks=False) or entry.stat(follow_symlinks=False).st_uid != os.getuid():
                    continue
                kind = approved_kind_matching(folder, kinds_here)
                if kind is None and REMOVED_BY_ANOTHER_PROGRAM.fullmatch(folder.name):
                    continue
                newest, entries_in_tree, size = tree_measure(folder)
            except FileNotFoundError:
                continue
            except OSError as error:
                result["failures"].append(f"{folder} was kept: it could not be read in full: "
                                          f"{error.filename}: {error.strerror}")
                continue
            if now() - newest < UNCHANGED_SECONDS:
                continue
            if kind is None:
                leftovers.append((place, folder, entries_in_tree, size))
            else:
                candidates.append((kind, folder))
    try:
        used = paths_processes_use(proc)
    except Unusable as error:
        result["failures"].append(f"nothing was deleted and no kind was shown: {error}")
        return result
    states = None
    for kind, folder in candidates:
        if in_use(folder, used):
            result["kept_in_use"] += 1
            continue
        if kind["only_once_its_pull_request_is_merged_or_closed"]:
            if states is None:
                try:
                    states = pull_request_states(repository)
                except Unusable as error:
                    states = error
            if isinstance(states, Unusable):
                result["failures"].append(f"{folder} was kept: its pull request's state could not "
                                          f"be looked up: {states}")
                continue
            number = int(kind["pattern"].fullmatch(folder.name).group("pull_request"))
            if number not in states:
                result["failures"].append(f"{folder} was kept: pull request {number}, read from its "
                                          "name, is not in the repository's list of pull requests")
                continue
            if states[number] not in ("MERGED", "CLOSED"):
                result["kept_open_pull_request"] += 1
                continue
        print(f"{'would delete' if dry_run else 'deleting'} {folder} (kind {kind['kind']})", flush=True)
        try:
            if not dry_run:
                shutil.rmtree(folder)
            result["deleted"] += 1
        except OSError as error:
            result["failures"].append(f"{folder} could not be deleted in full: {error.filename}: "
                                      f"{error.strerror}")
    for place, folder, entries_in_tree, size in leftovers:
        if in_use(folder, used):
            continue
        group = result["unapproved"].setdefault(
            (str(place), unapproved_kind_of(folder.name)), {"folders": [], "files": 0, "bytes": 0})
        group["folders"].append(folder.name)
        group["files"] += entries_in_tree
        group["bytes"] += size
    if result["unapproved"] and not dry_run:
        alerts_for_new_kinds_write(result, kinds_shown_state_file)
    return result


def alerts_for_new_kinds_write(result: dict, kinds_shown_state_file: Path):
    try:
        shown = kinds_shown_read(kinds_shown_state_file)
    except Unusable as error:
        result["failures"].append(f"no user-alert was written for a new kind: {error}")
        return
    for (place, kind), group in sorted(result["unapproved"].items()):
        key = f"{place}/{kind}"
        if key in shown:
            continue
        try:
            user_alerts.user_alert_write_to_pending(
                ALERT_TITLE_TEMPLATE.format(place=place, kind=kind),
                ALERT_TEXT_TEMPLATE.format(folders=len(group["folders"]), kind=kind, place=place,
                                           files=group["files"], megabytes=group["bytes"] / 1e6,
                                           examples=", ".join(group["folders"][:EXAMPLES_IN_AN_ALERT])),
                ALERT_ACTION_TEXT)
            shown[key] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            kinds_shown_write(kinds_shown_state_file, shown)
        except OSError as error:
            result["failures"].append(f"the user-alert for kind {key} could not be written, or not "
                                      f"recorded as shown in {kinds_shown_state_file}: "
                                      f"{error.filename}: {error.strerror}")
            return


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would be deleted; delete nothing, write no user-alert")
    parser.add_argument("--approved-kinds-file", type=Path, default=DEFAULT_APPROVED_KINDS_FILE,
                        help="the kinds the user approved for deletion")
    parser.add_argument("--kinds-shown-state-file", type=Path,
                        default=Path.home() / KINDS_SHOWN_STATE_FILE_RELATIVE_TO_HOME,
                        help="the unapproved kinds already raised in a user-alert")
    parser.add_argument("--proc-filesystem-directory", type=Path, default=Path("/proc"),
                        help="the process table, for the paths each process uses")
    options = parser.parse_args(arguments)
    result = throwaway_folders_of_user_approved_kinds_delete(
        options.approved_kinds_file, options.kinds_shown_state_file, options.proc_filesystem_directory,
        options.dry_run)
    for (place, kind), group in sorted(result["unapproved"].items()):
        print(f"kept, of the unapproved kind {kind} in {place}: {len(group['folders'])} folders, "
              f"{group['files']} files, {group['bytes'] / 1e6:.1f} MB", flush=True)
    for failure in result["failures"]:
        print(failure, file=sys.stderr)
    if result["failures"]:
        print(FAILURES_INSTRUCTION, file=sys.stderr)
    print(f"throwaway folders {'that would be deleted' if options.dry_run else 'deleted'}: "
          f"{result['deleted']}; kept because their pull request is open: "
          f"{result['kept_open_pull_request']}; kept because a process uses them: "
          f"{result['kept_in_use']}; unapproved kinds: {len(result['unapproved'])}; "
          f"failures: {len(result['failures'])}", flush=True)
    return EXIT_FAILED if result["failures"] else EXIT_DONE


if __name__ == "__main__":
    sys.exit(main())
