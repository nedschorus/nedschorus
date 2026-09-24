#!/usr/bin/env python3
"""Find every copy of a file by its name, on both machines, newest first.

WHAT PROBLEM THIS SOLVES. Between 2026-08-23 and 2026-09-23 agents told the
user fourteen times that a file did not exist when it did. Only two of the
fourteen were real deletions. The other twelve still existed somewhere the
agent had not looked: another seat's checkout, the git reflog, the log-store
under a different name, a handoff. None of those misses went through Glob or
Grep; every one was a Bash `find` or `git log` over too few places, or no
search at all. The research, and the episodes this program is measured
against, are at

    nedlern@ned-box:/home/nedlern/nedschorus-logs/seats/merge-lane/lost-file-research-report-2026-09-23.md

The user approved building this locator on 2026-09-23 (walk
"merge-lane-mac-helper-open-items-and-questions-2026-09-23", item 4.1, "Y").
It is the fast first step: it answers "where is it now?" in a couple of
seconds. scripts/find-deleted-path-across-backups.py is the slow second step,
for a file that no longer exists anywhere, and this program names it when it
finds nothing.

WHAT IT SEARCHES. By name only, never by content. The query is a file name or
a path; its last component's stem (the name without its final suffix) is
matched case-insensitively as a substring of each file's name, so
`pr-main-process-design.md` also finds the log-store's
`pr-main-process-design-draft-from-origin-merge-lane-28e4f5f.md`.

    Mac      checkouts  /Users/el/agents, /Users/el/Projects,
                        /private/tmp/claude-501 (scratch worktrees)
             handoffs   /Users/el/.claude/handoffs
             git        every clone found under the checkouts
    ned-box  checkouts  /home/nedlern/agents, /home/nedlern/Projects
             log-store  /home/nedlern/nedschorus-logs, except transcripts/
             handoffs   /home/nedlern/.claude/handoffs
             git        every clone found under the checkouts

The log-store's transcripts/ directory is left out on purpose: its files are
named by session id, and searching inside transcripts was not part of what
was approved. `.git`, `__pycache__`, `node_modules`, `.venv` and `venv`
directories are never descended into.

THE GIT SURFACE is `git log --reflog --all` over each clone, with a pathspec
that matches the name anywhere in the tree. `--reflog` is what the research's
episodes E11 and E14 needed: two commits of docs/drafts/pr-main-process-design.md
were reachable only from the merge-lane worktree's HEAD reflog after its
seat-branch was recreated. Measured 2026-09-23 with git 2.55 on the Mac: those
two commits sit only in .git/worktrees/merge-lane/logs/HEAD, and
`git log --reflog` run against the main clone's git directory lists them, so
one run per clone covers the HEAD reflogs of all its worktrees. The suite's
worktree case measures the same thing on each machine's git. A hit reports the
newest commit that touched each matching path, and prints the `git show`
command that reads the file's content there.

HOW THE OTHER MACHINE IS SEARCHED. From the Mac, ned-box is searched by
running this same program there, sent over one ssh call on stdin
(`python3 -`), with the surfaces to search passed on its command line. The
program therefore does not depend on ned-box's checkout being current, and
both machines search with one implementation. From ned-box the Mac is NOT
searched: no route from ned-box to the Mac is documented
(docs/nedschorus-wiki/nedschorus-fleet-machine-paths-and-checkouts.md
describes only the Mac to ned-box direction), so the program says the Mac was
not searched rather than building one.

WHAT IT PRINTS. Two lists, each newest first: copies with the same name as
the query, then files whose names contain its stem. Each line carries the
time (UTC), the machine, the surface, the path and the size; a git hit names
its commit as commit <hash> ("<subject>"), the form ruled on 2026-09-22.
Copies whose content is identical (compared by git's blob hash, so a checkout
file and the commit that holds the same bytes are recognised as one) are
printed under the newest of them as "same content" lines rather than as
separate entries. Then every place searched, every place that could not be
searched and why, and the time the search took.

The closing lines are instructions to the agent that ran it, one per line,
each with the condition it applies under, as CLAUDE.md requires of text a
program hands an agent at the moment it must act: tell the user when ned-box
could not be reached, with the remedy (CLAUDE.md also requires that); run the
backup search when nothing was found; report where it looked rather than that
the file does not exist.

EXIT CODES.
    0  at least one copy was found (a surface that failed is still printed)
    1  nothing was found, and every surface was searched
    2  bad invocation (argparse's own exit)
    3  nothing was found, and at least one surface or machine could NOT be
       searched -- so "not found" is not established
A failed surface never reads as "not found": that is why 3 exists apart
from 1.

TESTS. scripts/locate-file-copies-across-machines-test.py. The surfaces are
injectable through the LOCATE_FILE_COPIES_ACROSS_MACHINES_PLAN environment
variable, a JSON plan of the same shape as `production_plan()` returns, and
the suite puts a stand-in `ssh` on PATH for the other machine.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import hashlib
import json
import os
import pathlib
import shlex
import socket
import subprocess
import sys
import time

PROGRAM = "locate-file-copies-across-machines"

NED_BOX_HOSTNAME = "ned-box"
NED_BOX_SSH_TARGET = "nedlern@ned-box"
SSH_OPTIONS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=5"]
SSH_EXIT_CONNECTION_FAILED = 255
REMOTE_TIMEOUT_SECONDS = 30
LOCAL_COMMAND_TIMEOUT_SECONDS = 30

PLAN_ENVIRONMENT_VARIABLE = "LOCATE_FILE_COPIES_ACROSS_MACHINES_PLAN"
THIS_MACHINE_JSON_FLAG = "--this-machine-json"
BACKUP_SEARCH_PROGRAM = "scripts/find-deleted-path-across-backups.py"

# A match larger than this is listed but not hashed, so it is never collapsed
# with an identical copy. Hashing is the only part of a search whose cost
# grows with file size.
HASH_SIZE_LIMIT_BYTES = 64 * 1024 * 1024
# Per machine, only the newest this-many file matches are stat-sorted into the
# answer and hashed; per clone, only the newest this-many matching paths. A
# one-letter query must still answer in seconds.
MAX_FILE_HITS_PER_MACHINE = 300
MAX_GIT_PATHS_PER_CLONE = 300
# Entries printed per list; the rest are counted.
MAX_ENTRIES_PER_LIST = 25
# Directories never descended into, besides `.git`: bytecode, and third-party
# dependency trees no agent writes into. Measured 2026-09-23 on the Mac:
# /Users/el/Projects/route-spectrum took 0.44 s to search with its
# node_modules and 0.02 s without it.
SKIPPED_DIRECTORY_NAMES = ("__pycache__", "node_modules", ".venv", "venv")

MAC_SURFACES = {
    "machine": "mac",
    "surfaces": [
        {"name": "checkouts",
         "roots": ["/Users/el/agents", "/Users/el/Projects",
                   "/private/tmp/claude-501"],
         "git": True},
        {"name": "handoffs", "roots": ["/Users/el/.claude/handoffs"]},
    ],
}
NED_BOX_SURFACES = {
    "machine": "ned-box",
    "surfaces": [
        {"name": "checkouts",
         "roots": ["/home/nedlern/agents", "/home/nedlern/Projects"],
         "git": True},
        {"name": "log-store", "roots": ["/home/nedlern/nedschorus-logs"],
         "prune": ["/home/nedlern/nedschorus-logs/transcripts"]},
        {"name": "handoffs", "roots": ["/home/nedlern/.claude/handoffs"]},
    ],
}
MAC_NOT_REACHABLE_FROM_NED_BOX = (
    "no route from ned-box to the Mac is documented")

STATUS_WORDS = {"A": "added", "M": "modified", "D": "deleted",
                "T": "type changed"}


def production_plan() -> dict:
    """What to search, decided by which machine this is.

    `this` is searched here; `other` is searched over ssh when it carries an
    `ssh_target`, and reported as not searched when it carries a
    `not_searched_because` instead.
    """
    if socket.gethostname().split(".")[0] == NED_BOX_HOSTNAME:
        return {"this": NED_BOX_SURFACES,
                "other": dict(MAC_SURFACES,
                              not_searched_because=MAC_NOT_REACHABLE_FROM_NED_BOX)}
    return {"this": MAC_SURFACES,
            "other": dict(NED_BOX_SURFACES, ssh_target=NED_BOX_SSH_TARGET)}


def plan_for_this_run() -> dict:
    override = os.environ.get(PLAN_ENVIRONMENT_VARIABLE)
    if override:
        return json.loads(override)
    return production_plan()


def query_stem(query: str) -> str:
    """The part of the query that is matched: its last component's stem."""
    name = pathlib.PurePath(query.rstrip("/")).name
    return pathlib.PurePath(name).stem if name else ""


def query_name(query: str) -> str:
    return pathlib.PurePath(query.rstrip("/")).name


def escape_glob(text: str) -> str:
    """`text` made literal inside a find -iname pattern or a git glob."""
    return "".join("\\" + ch if ch in "*?[]\\" else ch for ch in text)


def name_matches(basename: str, stem: str) -> bool:
    return stem.lower() in basename.lower()


def git_blob_id(path: str, size: int):
    """git's object id for this file's bytes, or None when it is not hashed.

    git's id rather than a plain sha256 so that a checkout file and a commit
    holding the same bytes collapse into one entry: `git log --raw` already
    reports every commit's blob ids, at no extra cost.
    """
    if size > HASH_SIZE_LIMIT_BYTES:
        return None
    digest = hashlib.sha1(b"blob %d\0" % size)
    try:
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def find_command(directory, prune, stem, print_git_entries):
    """One find over one directory: matching regular files, and, for a
    surface whose clones are searched, every `.git` entry (directory or
    worktree file). `.git` and SKIPPED_DIRECTORY_NAMES are pruned either
    way."""
    command = ["find", directory]
    for path in prune:
        command += ["-path", path, "-prune", "-o"]
    command += ["-name", ".git", "-prune"]
    if print_git_entries:
        command += ["-print0"]
    command += ["-o", "("]
    for index, name in enumerate(SKIPPED_DIRECTORY_NAMES):
        command += (["-o"] if index else []) + ["-name", name]
    command += [")", "-prune",
                "-o", "-type", "f", "-iname", f"*{escape_glob(stem)}*",
                "-print0"]
    return command


def split_surface(surface, stem):
    """(directories to hand to find, matching files, report) for one
    surface, from one listing of each root.

    WHY ONE FIND PER DIRECTORY UNDER A ROOT, NOT ONE FIND PER ROOT. Measured
    2026-09-23 on the Mac: a single find over the three checkout roots
    (279,000 files, 222,000 of them under /Users/el/Projects) took 6.7 to 7.4
    s; the same search as one find per directory directly under the roots,
    sixteen at a time, took 1.7 s. The files directly in a root, and a `.git`
    directly in one, are taken from the listing itself."""
    prune = surface.get("prune", [])
    report = {"name": surface["name"], "roots": surface["roots"],
              "absent": [], "prune": prune, "failures": []}
    directories, files = [], []
    for root in surface["roots"]:
        if not os.path.isdir(root):
            report["absent"].append(root)
            continue
        try:
            entries = list(os.scandir(root))
        except OSError as error:
            report["failures"].append(
                f"{root} could not be listed: {error.strerror}")
            continue
        # A pruned path, a skipped name or a `.git` directly under a root
        # needs no check here: find applies its tests to its own starting
        # point too, so it prunes (and, for `.git`, prints) that directory.
        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    directories.append(entry.path)
                elif (entry.is_file(follow_symlinks=False)
                      and name_matches(entry.name, stem)):
                    files.append(entry.path)
            except OSError:
                continue
    return directories, files, report


def run_find(directory, prune, stem, print_git_entries):
    """(matching file paths, `.git` entries, failure or None) for one
    directory."""
    command = find_command(directory, prune, stem, print_git_entries)
    try:
        result = subprocess.run(command, capture_output=True,
                                timeout=LOCAL_COMMAND_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return [], [], (f"find in {directory} did not finish within "
                        f"{LOCAL_COMMAND_TIMEOUT_SECONDS} s")
    except OSError as error:
        return [], [], f"find could not run: {error}"
    failure = None
    if result.returncode != 0:
        lines = result.stderr.decode("utf-8", "replace").strip().splitlines()
        failure = (f"find in {directory} exited {result.returncode}: "
                   + (lines[0] if lines else "no message"))
    files, git_entries = [], []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        path = os.fsdecode(raw)
        if os.path.basename(path) == ".git":
            git_entries.append(path)
        else:
            files.append(path)
    return files, git_entries, failure


def git_dirs_of(git_entries):
    """The distinct repositories behind a list of `.git` entries.

    A `.git` directory is a clone's own git directory. A `.git` FILE is a
    worktree's pointer, `gitdir: <common>/worktrees/<name>`, and stands for
    the clone at <common>; one `git log --reflog` there covers every
    worktree's HEAD reflog (measured; see the module docstring)."""
    found = {}
    for entry in git_entries:
        if os.path.isdir(entry):
            git_dir = entry
            # A `.git` directory with no HEAD is not a repository, and git
            # log refuses it ("not a git repository"). Measured 2026-09-23:
            # five on the Mac, probe repositories under /private/tmp whose
            # files are gone and whose directories remain. They hold nothing
            # to search, so they are skipped rather than reported as failed.
            if not os.path.isfile(os.path.join(git_dir, "HEAD")):
                continue
        else:
            try:
                with open(entry, encoding="utf-8") as handle:
                    line = handle.readline().strip()
            except OSError:
                continue
            if not line.startswith("gitdir:"):
                continue
            pointed = line[len("gitdir:"):].strip()
            if not os.path.isabs(pointed):
                pointed = os.path.join(os.path.dirname(entry), pointed)
            parent = os.path.dirname(os.path.normpath(pointed))
            if os.path.basename(parent) != "worktrees":
                continue
            git_dir = os.path.dirname(parent)
        if os.path.isdir(git_dir):
            found.setdefault(os.path.realpath(git_dir), git_dir)
    return sorted(found)


def git_log_command(git_dir, stem):
    return ["git", "--git-dir", git_dir, "log", "--reflog", "--all",
            "--topo-order", "--no-renames", "--raw", "--no-abbrev", "-z",
            "--format=%x01%H%x00%ct%x00%s", "--",
            f":(glob,icase)**/*{escape_glob(stem)}*"]


def parse_git_log(output: bytes, stem: str):
    """{path: newest hit} from `git_log_command`'s output.

    The output is a run of commits, each `\\x01<hash>\\0<time>\\0<subject>\\0`
    followed by its raw entries, `:<modes> <old> <new> <status>\\0<path>\\0`.
    A merge commit carries no entries. The pathspec also matches files under
    a directory whose name contains the stem, so the stem is checked again
    against each path's own name.

    NEWEST IS THE FIRST SEEN, unless a later entry is strictly newer. The log
    runs in --topo-order, so a commit always comes before its parents: two
    commits made in the same second -- an add and the delete that follows
    it, as the suite makes them -- are ordered by ancestry, which their
    one-second timestamps cannot do. Between unrelated commits the later
    timestamp still wins.
    """
    newest = {}
    for chunk in output.split(b"\x01"):
        if not chunk:
            continue
        fields = chunk.split(b"\0")
        if len(fields) < 3:
            continue
        commit = fields[0].decode("ascii", "replace")
        try:
            when = int(fields[1])
        except ValueError:
            continue
        subject = fields[2].decode("utf-8", "replace")
        rest = [field for field in fields[3:] if field.strip(b"\n")]
        for meta, raw_path in zip(rest[0::2], rest[1::2]):
            parts = meta.strip(b"\n").decode("ascii", "replace").split()
            if len(parts) < 5:
                continue
            old_blob, new_blob, status = parts[2], parts[3], parts[4][:1]
            path = os.fsdecode(raw_path)
            if not name_matches(os.path.basename(path), stem):
                continue
            blob = old_blob if status == "D" else new_blob
            if set(blob) == {"0"}:
                blob = None
            current = newest.get(path)
            if current is None or when > current["time"]:
                newest[path] = {"commit": commit, "time": when,
                                "subject": subject, "status": status,
                                "blob": blob}
    return newest


def run_git_log(git_dir, stem):
    """(hits, failure) for one clone."""
    try:
        result = subprocess.run(git_log_command(git_dir, stem),
                                capture_output=True,
                                timeout=LOCAL_COMMAND_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return [], (f"git log in {git_dir} did not finish within "
                    f"{LOCAL_COMMAND_TIMEOUT_SECONDS} s")
    except OSError as error:
        return [], f"git could not run: {error}"
    if result.returncode != 0:
        lines = result.stderr.decode("utf-8", "replace").strip().splitlines()
        return [], (f"git log in {git_dir} exited {result.returncode}: "
                    + (lines[-1] if lines else "no message"))
    newest = parse_git_log(result.stdout, stem)
    ordered = sorted(newest.items(), key=lambda item: -item[1]["time"])
    hits = []
    for path, found in ordered[:MAX_GIT_PATHS_PER_CLONE]:
        hits.append(dict(found, kind="git", surface="git", path=path,
                         clone=git_dir, size=None))
    return hits, None


def search_this_machine(machine_plan, stem):
    """Everything this machine holds under the plan, as one JSON-ready dict:
    the hits, a report per surface, and the git report."""
    surfaces = machine_plan["surfaces"]
    file_paths = []  # (surface name, path)
    reports = []
    git_dirs, logs = set(), []
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:

        def search_clones(git_entries):
            # A clone's log starts as soon as the find that met it returns,
            # so the git surface overlaps the slower finds instead of
            # waiting for all of them.
            for git_dir in git_dirs_of(git_entries):
                if git_dir not in git_dirs:
                    git_dirs.add(git_dir)
                    logs.append(pool.submit(run_git_log, git_dir, stem))

        pending = {}
        for surface in surfaces:
            directories, files, report = split_surface(surface, stem)
            reports.append(report)
            file_paths += [(surface["name"], path) for path in files]
            for directory in directories:
                future = pool.submit(run_find, directory,
                                     surface.get("prune", []), stem,
                                     surface.get("git", False))
                pending[future] = (surface, report)
        for future in concurrent.futures.as_completed(pending):
            surface, report = pending[future]
            files, entries, failure = future.result()
            file_paths += [(surface["name"], path) for path in files]
            search_clones(entries)
            if failure:
                report["failures"].append(failure)
        git_hits, git_failures = [], []
        for future in logs:
            hits, failure = future.result()
            git_hits += hits
            if failure:
                git_failures.append(failure)

    stated = []
    for surface_name, path in file_paths:
        try:
            status = os.stat(path)
        except OSError:
            continue
        stated.append((status.st_mtime, surface_name, path, status.st_size))
    stated.sort(key=lambda entry: -entry[0])
    hits = []
    for mtime, surface_name, path, size in stated[:MAX_FILE_HITS_PER_MACHINE]:
        hits.append({"kind": "file", "surface": surface_name, "path": path,
                     "time": mtime, "size": size,
                     "blob": git_blob_id(path, size)})
    hits += git_hits

    git_surfaces = [surface["name"] for surface in surfaces
                    if surface.get("git")]
    return {"machine": machine_plan["machine"], "hits": hits,
            "surfaces": reports,
            "git": ({"under": git_surfaces, "clones": len(git_dirs),
                     "failed": git_failures} if git_surfaces else None),
            "file_matches_total": len(stated)}


def remote_command(machine_plan, query):
    """The command line ssh hands the other machine's shell: this program,
    read from stdin, told which surfaces to search."""
    surfaces = {"machine": machine_plan["machine"],
                "surfaces": machine_plan["surfaces"]}
    return " ".join(["python3", "-", THIS_MACHINE_JSON_FLAG,
                     shlex.quote(json.dumps(surfaces)), "--",
                     shlex.quote(query)])


def start_remote_search(other, query):
    """(process, error) for the other machine's search, started at once so it
    runs while this machine searches."""
    try:
        source = pathlib.Path(__file__).read_bytes()
        process = subprocess.Popen(
            ["ssh", *SSH_OPTIONS, other["ssh_target"],
             remote_command(other, query)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
    except OSError as error:
        return None, f"ssh could not run: {error}"
    return (process, source), None


def finish_remote_search(started, other):
    """The other machine's result dict, or a string saying why there is none."""
    process, source = started
    timeout = other.get("timeout_seconds", REMOTE_TIMEOUT_SECONDS)
    try:
        stdout, stderr = process.communicate(source, timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        return f"it did not answer within {timeout} s"
    message = stderr.decode("utf-8", "replace").strip().splitlines()
    last_line = message[-1] if message else "no message"
    if process.returncode == SSH_EXIT_CONNECTION_FAILED:
        return f"ssh {other['ssh_target']} failed: {last_line}"
    if process.returncode != 0:
        return (f"the search there exited {process.returncode}: {last_line}")
    try:
        return json.loads(stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "the search there printed something that is not its answer"


def format_time(epoch):
    return datetime.datetime.fromtimestamp(
        epoch, tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%MZ")


def describe(hit, machine):
    """The part of an entry's line after its time: machine, surface, what."""
    if hit["kind"] == "file":
        what = f"{hit['path']}  ({hit['size']:,} bytes)"
    else:
        status = STATUS_WORDS.get(hit["status"], hit["status"])
        what = (f"commit {hit['commit'][:12]} (\"{hit['subject']}\"), "
                f"{hit['path']}, {status}")
    return f"{machine:<8} {hit['surface']:<10} {what}"


def read_command(hit, machine):
    revision = hit["commit"][:12] + ("^" if hit["status"] == "D" else "")
    command = (f"git --git-dir={shlex.quote(hit['clone'])} show "
               f"{shlex.quote(revision + ':' + hit['path'])}")
    return command if machine != NED_BOX_HOSTNAME else f"on ned-box: {command}"


def group_by_content(entries):
    """Entries sharing a blob id become one group, newest member first; an
    entry with no blob id is its own group. Groups are ordered newest first."""
    groups, by_blob = [], {}
    for entry in sorted(entries, key=lambda item: -item["hit"]["time"]):
        blob = entry["hit"].get("blob")
        if blob and blob in by_blob:
            by_blob[blob].append(entry)
            continue
        group = [entry]
        groups.append(group)
        if blob:
            by_blob[blob] = group
    return groups


def render_group(group, lines):
    first = group[0]
    lines.append(f"  {format_time(first['hit']['time'])}  "
                 f"{describe(first['hit'], first['machine'])}")
    if first["hit"]["kind"] == "git":
        lines.append(f"                     read it: "
                     f"{read_command(first['hit'], first['machine'])}")
    for member in group[1:]:
        lines.append(f"                     same content, "
                     f"{format_time(member['hit']['time'])}: "
                     f"{describe(member['hit'], member['machine'])}")


def render(query, results, not_searched, elapsed):
    """(text, exit code) for the merged results of both machines."""
    stem = query_stem(query)
    name = query_name(query).lower()
    entries = [{"machine": result["machine"], "hit": hit}
               for result in results for hit in result["hits"]]

    def same_name(entry):
        basename = os.path.basename(entry["hit"]["path"]).lower()
        return basename == name or (
            "." not in name and pathlib.PurePath(basename).stem == name)

    groups = group_by_content(entries)
    same = [group for group in groups if any(map(same_name, group))]
    other = [group for group in groups if not any(map(same_name, group))]
    # In the same-name list a group is led by its newest same-name copy,
    # not by a renamed copy that happens to be newer.
    for group in same:
        group.sort(key=lambda entry: (not same_name(entry),
                                      -entry["hit"]["time"]))
    same.sort(key=lambda group: -group[0]["hit"]["time"])

    lines = [f"{PROGRAM}: file names containing \"{stem}\", any case"]
    truncated = False
    for title, chosen in (
            (f"Same name ({query_name(query)}), newest first:", same),
            (f"Other names containing \"{stem}\", newest first:", other)):
        if not chosen:
            continue
        lines += ["", title]
        for group in chosen[:MAX_ENTRIES_PER_LIST]:
            render_group(group, lines)
        if len(chosen) > MAX_ENTRIES_PER_LIST:
            truncated = True
            lines.append(f"  ... and {len(chosen) - MAX_ENTRIES_PER_LIST} "
                         f"more not shown")

    failed = []
    lines += ["", "Searched:"]
    for result in results:
        machine = result["machine"]
        for report in result["surfaces"]:
            roots = ", ".join(
                root + (" (absent)" if root in report["absent"] else "")
                for root in report["roots"])
            excepting = "".join(f", except {path}" for path in report["prune"])
            lines.append(f"  {machine} {report['name']}: {roots}{excepting}")
            failed += [f"{machine} {report['name']}: {failure}"
                       for failure in report["failures"]]
        git = result.get("git")
        if git:
            lines.append(f"  {machine} git: every commit a branch or a reflog "
                         f"reaches, in the {git['clones']} clone(s) under "
                         f"{', '.join(git['under'])}")
            failed += [f"{machine} git: {failure}"
                       for failure in git["failed"]]
        if result.get("file_matches_total", 0) > MAX_FILE_HITS_PER_MACHINE:
            truncated = True
            lines.append(f"  {machine}: {result['file_matches_total']} files "
                         f"matched; only the newest "
                         f"{MAX_FILE_HITS_PER_MACHINE} were considered")
    if failed or not_searched:
        lines += ["", "NOT searched, or searched only in part:"]
        lines += [f"  {machine}: {reason}" for machine, reason in not_searched]
        lines += [f"  {failure}" for failure in failed]
    lines += ["", f"Took {elapsed:.1f} s."]

    found = bool(entries)
    incomplete = bool(failed or not_searched)
    instructions = []
    for machine, reason in not_searched:
        if machine == NED_BOX_HOSTNAME:
            instructions += [
                f"Tell the user ned-box was not searched: {reason}.",
                "Give the user this remedy: make sure ned-box is on and on "
                f"the LAN, then check that `ssh {NED_BOX_SSH_TARGET} true` "
                "succeeds.",
            ]
        elif reason == MAC_NOT_REACHABLE_FROM_NED_BOX:
            instructions.append("To search the Mac as well, run this program "
                                "on the Mac.")
        else:
            instructions.append(f"Tell the user {machine} was not searched: "
                                f"{reason}.")
    if failed:
        instructions.append("Tell the user which places above could not be "
                            "searched, and why.")
    if truncated:
        instructions.append("To see the entries not shown, run again with "
                            "more of the name.")
    if not found:
        instructions += [
            f"Nothing was found: run next "
            f"`{BACKUP_SEARCH_PROGRAM} {shlex.quote(query)}`, which searches "
            f"git history and the backups.",
            "When you report this, say where you looked (the Searched lines "
            "above); do not say the file does not exist.",
        ]
    if instructions:
        lines += [""] + instructions
    if found:
        code = 0
    elif incomplete:
        code = 3
    else:
        code = 1
    return "\n".join(lines) + "\n", code


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog=PROGRAM,
        description="Find every copy of a file by its name, on the Mac and "
                    "ned-box, newest first: checkouts, the log-store, the "
                    "handoffs, and git history including the reflog.")
    parser.add_argument("query", help="a file name or a path; its name's "
                        "stem is matched, case-insensitively, anywhere in a "
                        "file's name")
    parser.add_argument(THIS_MACHINE_JSON_FLAG, metavar="SURFACES_JSON",
                        help="search only this machine, over these surfaces, "
                             "and print the answer as JSON: what the program "
                             "runs on the other machine over ssh")
    args = parser.parse_args(argv)
    stem = query_stem(args.query)
    if not stem:
        parser.error("the query has no file name to match")

    if args.this_machine_json:
        result = search_this_machine(json.loads(args.this_machine_json), stem)
        json.dump(result, sys.stdout)
        return 0

    started_at = time.monotonic()
    plan = plan_for_this_run()
    other = plan.get("other")
    not_searched = []
    remote = None
    if other and other.get("ssh_target"):
        remote, error = start_remote_search(other, args.query)
        if error:
            not_searched.append((other["machine"], error))
    elif other:
        not_searched.append((other["machine"],
                             other.get("not_searched_because", "no route")))

    results = [search_this_machine(plan["this"], stem)]
    if remote:
        answer = finish_remote_search(remote, other)
        if isinstance(answer, dict):
            results.append(answer)
        else:
            not_searched.append((other["machine"], answer))

    text, code = render(args.query, results, not_searched,
                        time.monotonic() - started_at)
    # A path that is not valid UTF-8 prints with a replacement character
    # rather than stopping the whole answer with an encoding error.
    sys.stdout.write(text.encode("utf-8", "surrogateescape")
                     .decode("utf-8", "replace"))
    return code


if __name__ == "__main__":
    sys.exit(main())
