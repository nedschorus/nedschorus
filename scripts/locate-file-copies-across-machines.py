#!/usr/bin/env python3
"""Find file copies by name across both machines, then search backups if none are found."""

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

# Remove Git redirects so each command answers for the named repository.
GIT_REDIRECTING_VARIABLES = (
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
    "GIT_COMMON_DIR", "GIT_ALTERNATE_OBJECT_DIRECTORIES")
# Printed recovery commands must also remove redirects from the shell where they are pasted.
PRINTED_GIT_INVOCATION_WITHOUT_REDIRECTING_VARIABLES = "env %s git" % " ".join(
    "-u %s" % name for name in GIT_REDIRECTING_VARIABLES)

PLAN_ENVIRONMENT_VARIABLE = "LOCATE_FILE_COPIES_ACROSS_MACHINES_PLAN"
THIS_MACHINE_JSON_FLAG = "--this-machine-json"
# Use this interpreter: the backup search file is not executable.
BACKUP_SEARCH_PROGRAM_NAME = "find-deleted-path-across-backups.py"
BACKUP_SEARCH_PROGRAM_VARIABLE = (
    "LOCATE_FILE_COPIES_ACROSS_MACHINES_BACKUP_SEARCH_PROGRAM")
BACKUP_SEARCH_SURFACES_ALREADY_SEARCHED = ("git", "reflog")
# Without a summary line, the backup search did not finish.
BACKUP_SEARCH_SUMMARY_OPENINGS = (
    "Recoverable from: ", "No surface that could be searched has it.")
BACKUP_SEARCH_FOUND_EXIT = 0
BACKUP_SEARCH_INCOMPLETE_EXIT = 3

# Bound hashing cost, the only search cost that grows with file size.
HASH_SIZE_LIMIT_BYTES = 64 * 1024 * 1024
# Cap candidates for broad queries, but never exact names: a more specific query cannot recover capped exact matches.
MAX_FILE_HITS_PER_MACHINE = 300
MAX_GIT_PATHS_PER_CLONE = 300
MAX_ENTRIES_PER_LIST = 25
SKIPPED_DIRECTORY_NAMES = ("__pycache__", "node_modules", ".venv", "venv")

NESTED_WORKTREE_PARTS = (".claude", "worktrees")
# Do not search all of /private/tmp: backup snapshot mounts can expand the search to the whole disk.
MAC_SURFACES = {
    "machine": "mac",
    "surfaces": [
        {"name": "checkouts",
         "roots": ["/Users/el/agents", "/Users/el/Projects",
                   "/private/tmp/claude-501"],
         "git": True},
        {"name": "handoffs", "roots": ["/Users/el/.claude/handoffs"]},
    ],
    "this_repository": {"clones": ["/Users/el/Projects/nedschorus"],
                        "checkout_parents": ["/Users/el/agents"],
                        "scratch_trees": ["/tmp"]},
    "spellings": [["/private/tmp", "/tmp"]],
}
# Transcript names are session IDs; locating files within transcripts requires a content search.
NED_BOX_SURFACES = {
    "machine": "ned-box",
    "surfaces": [
        {"name": "checkouts",
         "roots": ["/home/nedlern/agents", "/home/nedlern/Projects",
                   "/tmp/claude-1000"],
         "git": True},
        {"name": "log-store", "roots": ["/home/nedlern/nedschorus-logs"],
         "prune": ["/home/nedlern/nedschorus-logs/transcripts"]},
        {"name": "handoffs", "roots": ["/home/nedlern/.claude/handoffs"]},
    ],
    "this_repository": {"clones": ["/home/nedlern/Projects/nedschorus"],
                        "checkout_parents": ["/home/nedlern/agents"],
                        "scratch_trees": ["/tmp"]},
    # The Mac mounts ned-box's home here.
    "spellings": [["/Volumes/nedhome", "/home/nedlern"]],
}
KNOWN_HOST_HOMES = {NED_BOX_HOSTNAME: "/home/nedlern"}
MAC_NOT_REACHABLE_FROM_NED_BOX = (
    "no route from ned-box to the Mac is documented")

STATUS_WORDS = {"A": "added", "M": "modified", "D": "deleted",
                "T": "type changed"}


def production_plan() -> dict:
    """Return local and remote search plans for this machine."""
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
    name = pathlib.PurePath(query.rstrip("/")).name
    return pathlib.PurePath(name).stem if name else ""


def query_name(query: str) -> str:
    return pathlib.PurePath(query.rstrip("/")).name


def escape_glob(text: str) -> str:
    """Make text literal inside a find pattern or Git glob."""
    return "".join("\\" + ch if ch in "*?[]\\" else ch for ch in text)


def name_matches(basename: str, stem: str) -> bool:
    return stem.lower() in basename.lower()


def is_same_name(basename: str, name: str) -> bool:
    """Match names case-insensitively, or stems when the query has no suffix."""
    basename, name = basename.lower(), name.lower()
    return basename == name or (
        "." not in name and pathlib.PurePath(basename).stem == name)


def split_host(query):
    """Return (host, path) for a recognized scp query, otherwise (None, query)."""
    head, colon, path = query.partition(":")
    if not colon or not path or "/" in head:
        return None, query
    user, at, host = head.rpartition("@")
    if at and user and host:
        return host, path
    if head in KNOWN_HOST_HOMES:
        return head, path
    return None, query


class CurrentDirectoryIsGone(Exception):
    """A relative query cannot be resolved from a removed working directory."""


def resolve_query(query, cwd=None):
    """Resolve scp and relative paths, leaving bare file names unchanged."""
    host, path = split_host(query)
    if host is not None and not path.startswith("/"):
        # An scp-relative path is relative to the remote home.
        home = KNOWN_HOST_HOMES.get(host.split(".")[0])
        inside = path[2:] if path.startswith("~/") else (
            "" if path == "~" else path)
        if home:
            path = home + ("/" + inside if inside else "")
        elif "/" in inside.rstrip("/"):
            raise ValueError(
                f"the query names host {host}, whose home this program does "
                f"not know: give the file's absolute path on {host}")
        else:
            path = inside
    elif host is None and (path == "~" or path.startswith("~/")):
        path = os.path.expanduser(path)
    bare = "/" not in path
    path = os.path.normpath(path.rstrip("/") or path)
    if not bare and not os.path.isabs(path):
        if cwd is None:
            try:
                cwd = os.getcwd()
            except OSError as error:
                raise CurrentDirectoryIsGone(str(error)) from error
        path = os.path.normpath(os.path.join(cwd, path))
    return path


def parts_of(path):
    return [part for part in pathlib.PurePath(path).parts
            if part not in (os.sep, ".")]


def canonical_path(path, spellings):
    """Replace the first matching path alias with its canonical prefix."""
    for alias, canonical in spellings:
        alias, canonical = alias.rstrip("/"), canonical.rstrip("/")
        if path == alias or path.startswith(alias + "/"):
            return canonical + path[len(alias):]
    return path


def parts_below(path, root):
    """Return the path components below root, or None for a path outside root."""
    root = root.rstrip("/")
    if path == root:
        return []
    if path.startswith(root + "/"):
        return parts_of(path[len(root) + 1:])
    return None


def inside_nested_worktree(parts):
    """Remove a nested task worktree prefix from a checkout-relative path."""
    depth = len(NESTED_WORKTREE_PARTS)
    if (len(parts) > depth + 1
            and tuple(parts[:depth]) == NESTED_WORKTREE_PARTS):
        return parts[depth + 1:]
    return parts


def place_in_this_repository(path, layouts):
    """Return (checkout kind, relative path parts), or None outside repository locations."""
    for layout in layouts:
        for clone in layout.get("clones", []):
            below = parts_below(path, clone)
            if below:
                return "checkout", inside_nested_worktree(below)
    for layout in layouts:
        for parent in layout.get("checkout_parents", []):
            below = parts_below(path, parent)
            if below and len(below) >= 2:
                return "checkout", inside_nested_worktree(below[1:])
    for layout in layouts:
        for tree in layout.get("scratch_trees", []):
            below = parts_below(path, tree)
            if below:
                return "scratch", below
    return None


def layouts_and_spellings(plan):
    """Return both machines' repository layouts and path spelling pairs."""
    layouts, spellings = [], []
    for machine in (plan.get("this"), plan.get("other")):
        if machine:
            layouts.append(machine.get("this_repository", {}))
            spellings += machine.get("spellings", [])
    return layouts, spellings


def this_repository_git_dirs(layout):
    return set(git_dirs_of([os.path.join(clone, ".git")
                            for clone in layout.get("clones", [])]))


def place_of_file(path, layout, spellings, this_git_dirs, cache):
    """Return (checkout root, relative path), or None outside this repository."""
    placed = place_in_this_repository(canonical_path(path, spellings),
                                      [layout])
    if placed is None:
        return None
    kind, parts = placed
    if kind == "checkout":
        if not parts:
            return None
        root = path
        for _ in parts:
            root = os.path.dirname(root)
        return root, "/".join(parts)
    directory = os.path.dirname(path)
    walked = []
    while directory not in cache:
        walked.append(directory)
        if os.path.lexists(os.path.join(directory, ".git")):
            owners = git_dirs_of([os.path.join(directory, ".git")])
            cache[directory] = (directory if owners
                                and owners[0] in this_git_dirs else None)
            break
        parent = os.path.dirname(directory)
        if (parent == directory
                or place_in_this_repository(canonical_path(parent, spellings),
                                            [layout]) is None):
            cache[directory] = None
            break
        directory = parent
    root = cache[directory]
    for step in walked:
        cache[step] = root
    if root is None:
        return None
    return root, "/".join(parts_of(os.path.relpath(path, root)))


def environment_without_git_redirecting_variables():
    # Keep this helper local: the complete program is sent over ssh without sibling modules.
    return {key: value for key, value in os.environ.items()
            if key not in GIT_REDIRECTING_VARIABLES}


def tracked_in_checkout(root, relative_paths):
    """Return (tracked paths, failure or None) for the checkout."""
    if not os.path.lexists(os.path.join(root, ".git")):
        return set(), None
    command = ["git", "-C", root, "ls-files", "-z", "--",
               *[":(literal)" + path for path in relative_paths]]
    try:
        result = subprocess.run(
            command, capture_output=True,
            env=environment_without_git_redirecting_variables(),
            timeout=LOCAL_COMMAND_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return set(), (f"git ls-files in {root} did not finish within "
                       f"{LOCAL_COMMAND_TIMEOUT_SECONDS} s")
    except OSError as error:
        return set(), f"git could not run: {error}"
    if result.returncode != 0:
        lines = result.stderr.decode("utf-8", "replace").strip().splitlines()
        return set(), (f"git ls-files in {root} exited {result.returncode}, "
                       f"so which files it tracks is unknown: "
                       + (lines[-1] if lines else "no message"))
    return {os.fsdecode(raw) for raw in result.stdout.split(b"\0") if raw}, None


def worktrees_listed_by(git_dir):
    """Return (worktree paths, failure or None) for the repository."""
    # Git records worktree paths with symbolic links resolved.
    try:
        result = subprocess.run(
            ["git", "--git-dir", git_dir, "worktree", "list", "--porcelain"],
            capture_output=True,
            env=environment_without_git_redirecting_variables(),
            timeout=LOCAL_COMMAND_TIMEOUT_SECONDS)
    except (subprocess.TimeoutExpired, OSError) as error:
        return [], str(error)
    if result.returncode != 0:
        lines = result.stderr.decode("utf-8", "replace").strip().splitlines()
        return [], lines[-1] if lines else "no message"
    return [line[len("worktree "):] for line in
            result.stdout.decode("utf-8", "surrogateescape").splitlines()
            if line.startswith("worktree ")], None


def listed_worktrees_outside(layout, surfaces):
    """Return (worktrees outside the search roots, failures)."""
    # Resolve both sides so symlink aliases do not cause duplicate searches.
    roots = [os.path.realpath(root)
             for surface in surfaces for root in surface["roots"]]
    outside, failures = set(), []
    for clone in layout.get("clones", []):
        git_dir = os.path.join(clone, ".git")
        if not os.path.isdir(git_dir):
            continue
        worktrees, failure = worktrees_listed_by(git_dir)
        if failure:
            failures.append(f"the worktrees {clone} lists could not be read: "
                            f"{failure}")
            continue
        for worktree in worktrees:
            if os.path.isdir(worktree) and not any(
                    parts_below(os.path.realpath(worktree), root) is not None
                    for root in roots):
                outside.add(worktree)
    return sorted(outside), failures


def query_target(resolved, layouts, spellings):
    """Return the query kind, canonical path, and parts needed to match copies."""
    parts = parts_of(resolved)
    if not os.path.isabs(resolved):
        return {"kind": "name", "parts": parts, "path": resolved}
    canonical = canonical_path(resolved, spellings)
    placed = place_in_this_repository(canonical, layouts)
    if placed and placed[1]:
        return {"kind": placed[0], "parts": placed[1], "path": resolved,
                "canonical": canonical}
    return {"kind": "absolute", "parts": parts_of(canonical), "path": resolved,
            "canonical": canonical}


def same_parts(parts, wanted):
    """Compare directories case-insensitively and file names with is_same_name."""
    return (bool(parts) and bool(wanted)
            and [part.lower() for part in parts[:-1]]
            == [part.lower() for part in wanted[:-1]]
            and is_same_name(parts[-1], wanted[-1]))


def ends_with(parts, tail):
    return len(parts) >= len(tail) and same_parts(parts[len(parts) - len(tail):],
                                                   tail)


def keep_same_name_and_newest(items, name, cap, basename_of):
    """Return all same-name items and up to cap other items, newest first."""
    kept, others = [], 0
    for item in items:
        if is_same_name(basename_of(item), name):
            kept.append(item)
        elif others < cap:
            kept.append(item)
            others += 1
    return kept


def git_blob_id(path: str, size: int):
    """Return the Git blob ID, or None when the file is not hashed."""
    # Git blob IDs let checkout files and history entries with identical bytes share a group.
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
    """Build a find command for matching files and, when requested, Git entries."""
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
    """Return (directories to search, matching files, report) from a surface listing."""
    # Search child directories separately so slow roots can be searched in parallel.
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
        # find tests its starting point too, so pruned roots need no separate handling.
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
    """Return (matching paths, Git entries, failure or None) for one directory."""
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
    """Return distinct clone Git directories from clone and worktree entries."""
    # One git log --reflog on the common directory covers every worktree's HEAD reflog.
    found = {}
    for entry in git_entries:
        if os.path.isdir(entry):
            git_dir = entry
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
        # Git requires HEAD, objects, and refs; incomplete probe directories hold no searchable repository.
        if (os.path.isfile(os.path.join(git_dir, "HEAD"))
                and os.path.isdir(os.path.join(git_dir, "objects"))
                and os.path.isdir(os.path.join(git_dir, "refs"))):
            found.setdefault(os.path.realpath(git_dir), git_dir)
    return sorted(found)


def git_log_command(git_dir, stem):
    # --full-history keeps paths added and deleted on merged branches visible despite merge simplification.
    return ["git", "--git-dir", git_dir, "log", "--reflog", "--all",
            "--full-history", "--topo-order", "--no-renames", "--raw",
            "--no-abbrev", "-z",
            "--format=%x01%H%x00%ct%x00%s", "--",
            f":(glob,icase)**/*{escape_glob(stem)}*"]


def parse_git_log(output: bytes, stem: str):
    """Return the newest hit per path from raw Git log output."""
    # Topo-order breaks equal-timestamp ties by ancestry; only a strictly newer timestamp replaces a hit.
    # Recheck the basename: the pathspec also matches files beneath matching directory names.
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


def run_git_log(git_dir, stem, name):
    """Return (hits, failure, capped candidate count) for one clone."""
    try:
        result = subprocess.run(
            git_log_command(git_dir, stem), capture_output=True,
            env=environment_without_git_redirecting_variables(),
            timeout=LOCAL_COMMAND_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return [], (f"git log in {git_dir} did not finish within "
                    f"{LOCAL_COMMAND_TIMEOUT_SECONDS} s"), 0
    except OSError as error:
        return [], f"git could not run: {error}", 0
    if result.returncode != 0:
        lines = result.stderr.decode("utf-8", "replace").strip().splitlines()
        return [], (f"git log in {git_dir} exited {result.returncode}: "
                    + (lines[-1] if lines else "no message")), 0
    newest = parse_git_log(result.stdout, stem)
    ordered = sorted(newest.items(), key=lambda item: -item[1]["time"])
    kept = keep_same_name_and_newest(
        ordered, name, MAX_GIT_PATHS_PER_CLONE,
        lambda item: os.path.basename(item[0]))
    hits = [dict(found, kind="git", surface="git", path=path, clone=git_dir,
                 size=None)
            for path, found in kept]
    return hits, None, len(ordered) - len(kept)


def search_this_machine(machine_plan, stem, name, check_tracked=False):
    """Return JSON-ready hits and surface reports, optionally checking checkout tracking."""
    surfaces = machine_plan["surfaces"]
    layout = machine_plan.get("this_repository", {})
    spellings = machine_plan.get("spellings", [])
    file_paths = []  # (surface name, path)
    reports = []
    git_dirs, logs = set(), []
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:

        def search_clones(git_entries):
            # Overlap clone history searches with the remaining slower file searches.
            for git_dir in git_dirs_of(git_entries):
                if git_dir not in git_dirs:
                    git_dirs.add(git_dir)
                    logs.append(pool.submit(run_git_log, git_dir, stem,
                                            name))

        pending = {}
        for surface in surfaces:
            directories, files, report = split_surface(surface, stem)
            if surface.get("git"):
                listed, failures = listed_worktrees_outside(layout, surfaces)
                if listed:
                    report["listed_worktrees"] = listed
                directories += listed
                report["failures"] += failures
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
        git_hits, git_failures, git_cut = [], [], 0
        for future in logs:
            hits, failure, cut = future.result()
            git_hits += hits
            git_cut += cut
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
    this_git_dirs = this_repository_git_dirs(layout)
    place_cache = {}
    hits = []
    in_checkouts = {}  # checkout root: [(hit, path inside it)]
    for mtime, surface_name, path, size in keep_same_name_and_newest(
            stated, name, MAX_FILE_HITS_PER_MACHINE,
            lambda entry: os.path.basename(entry[2])):
        placed = place_of_file(path, layout, spellings, this_git_dirs,
                               place_cache)
        hit = {"kind": "file", "surface": surface_name, "path": path,
               "canonical": canonical_path(path, spellings),
               "time": mtime, "size": size,
               "blob": git_blob_id(path, size),
               "in_this_repository": placed[1] if placed else None}
        hits.append(hit)
        if placed and check_tracked:
            in_checkouts.setdefault(placed[0], []).append((hit, placed[1]))
    # An untracked file belongs only to its checkout, not to equivalent paths in other seats.
    reports_by_surface = {report["name"]: report for report in reports}
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        asked = {pool.submit(tracked_in_checkout, root,
                             sorted({inside for _, inside in placed_hits})):
                 placed_hits
                 for root, placed_hits in in_checkouts.items()}
        for future in concurrent.futures.as_completed(asked):
            tracked, failure = future.result()
            for hit, inside in asked[future]:
                if failure:
                    hit["tracking_unknown"] = True
                else:
                    hit["untracked"] = inside not in tracked
            if failure:
                reports_by_surface[asked[future][0][0]["surface"]][
                    "failures"].append(failure)
    for hit in git_hits:
        hit["this_repository"] = hit["clone"] in this_git_dirs
    # Include linked-worktree paths for other projects; a failed listing leaves their history coverage unknown.
    other_clones = (sorted({hit["clone"] for hit in git_hits
                            if not hit["this_repository"]})
                    if check_tracked else [])
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        listings = dict(zip(other_clones,
                            pool.map(worktrees_listed_by, other_clones)))
    for clone, (_, failure) in listings.items():
        if failure:
            git_failures.append(f"the worktrees {clone} lists could not be "
                                f"read: {failure}")
    for hit in git_hits:
        if hit["this_repository"]:
            continue
        if os.path.basename(hit["clone"]) == ".git":
            hit["canonical"] = canonical_path(
                os.path.join(os.path.dirname(hit["clone"]), hit["path"]),
                spellings)
        linked = []
        for tree in listings.get(hit["clone"], ([], None))[0]:
            path = canonical_path(os.path.join(tree, hit["path"]), spellings)
            if path != hit.get("canonical") and path not in linked:
                linked.append(path)
        if linked:
            hit["canonical_in_linked_worktrees"] = linked
    hits += git_hits

    git_surfaces = [surface["name"] for surface in surfaces
                    if surface.get("git")]
    return {"machine": machine_plan["machine"], "hits": hits,
            "surfaces": reports,
            "git": ({"under": git_surfaces, "clones": len(git_dirs),
                     "failed": git_failures, "candidates_cut": git_cut}
                    if git_surfaces else None),
            "file_matches_total": len(stated),
            "candidate_matches_total": sum(
                1 for entry in stated
                if not is_same_name(os.path.basename(entry[2]), name))}


def remote_command(machine_plan, query):
    """Build the ssh shell command to run this program from stdin."""
    surfaces = {key: machine_plan[key]
                for key in ("machine", "surfaces", "this_repository",
                            "spellings")
                if key in machine_plan}
    return " ".join(["python3", "-", THIS_MACHINE_JSON_FLAG,
                     shlex.quote(json.dumps(surfaces)), "--",
                     shlex.quote(query)])


def start_remote_search(other, query):
    """Return (process, error) for a remote search."""
    # Only the ssh handshake overlaps the local search; finish_remote_search sends the program.
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
    """Return the remote result dict, or an error string."""
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
    """Format an entry's machine, surface, and location."""
    if hit["kind"] == "file":
        untracked = (", not tracked by git" if hit.get("untracked")
                     else ", tracking unknown" if hit.get("tracking_unknown")
                     else "")
        what = f"{hit['path']}  ({hit['size']:,} bytes{untracked})"
    else:
        status = STATUS_WORDS.get(hit["status"], hit["status"])
        what = (f"commit {hit['commit'][:12]} (\"{hit['subject']}\"), "
                f"{hit['path']}, {status}")
    return f"{machine:<8} {hit['surface']:<10} {what}"


def read_command(hit, machine):
    revision = hit["commit"][:12] + ("^" if hit["status"] == "D" else "")
    command = (f"{PRINTED_GIT_INVOCATION_WITHOUT_REDIRECTING_VARIABLES} "
               f"--git-dir={shlex.quote(hit['clone'])} show "
               f"{shlex.quote(revision + ':' + hit['path'])}")
    return command if machine != NED_BOX_HOSTNAME else f"on ned-box: {command}"


def group_by_content(entries):
    """Group entries by blob ID, keeping unhashed entries separate and newest entries first."""
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


def render(query, target, results, not_searched, elapsed):
    """Return (report text, exit code) for both machines."""
    stem = query_stem(query)
    name = query_name(query)
    kind, wanted = target["kind"], target["parts"]
    entries = [{"machine": result["machine"], "hit": hit}
               for result in results for hit in result["hits"]]

    def checkout_parts(entry):
        """Return the hit path within this repository, or None for other repositories."""
        hit = entry["hit"]
        if hit["kind"] == "git":
            return parts_of(hit["path"]) if hit.get("this_repository") else None
        place = hit.get("in_this_repository")
        return parts_of(place) if place else None

    def own_path_only(entry):
        """Return whether an untracked or tracking-unknown file must match its own path."""
        hit = entry["hit"]
        return hit["kind"] == "file" and bool(
            hit.get("untracked") or hit.get("tracking_unknown"))

    # Use a repository-backed tail of at least two components: a basename alone could match a different directory.
    anchor = wanted if kind == "checkout" else None
    if kind == "scratch":
        held = [len(parts) for entry, parts in
                ((entry, checkout_parts(entry)) for entry in entries)
                if parts and len(parts) >= 2 and ends_with(wanted, parts)
                and not own_path_only(entry)]
        if held:
            anchor = wanted[len(wanted) - max(held):]

    def found_copy(entry):
        hit = entry["hit"]
        if kind == "name":
            return is_same_name(os.path.basename(hit["path"]), name)
        if any(same_parts(parts_of(path), parts_of(target["canonical"]))
               for path in (hit.get("canonical"),
                            *hit.get("canonical_in_linked_worktrees", ()))
               if path):
            return True
        if own_path_only(entry):
            return False
        parts = checkout_parts(entry)
        return bool(anchor and parts) and same_parts(parts, anchor)

    if kind == "name":
        heading, wanted_label = f"Same name ({name})", f"named {name}"
    else:
        shown = "/".join(anchor) if anchor else target["path"]
        heading, wanted_label = f"Same path ({shown})", f"at {shown}"

    def same_name(entry):
        return is_same_name(os.path.basename(entry["hit"]["path"]), name)

    # Separate candidates before grouping: identical content at a different path must not count as found.
    same = group_by_content([entry for entry in entries if found_copy(entry)])
    other = group_by_content([entry for entry in entries
                              if not found_copy(entry)])
    for group in other:
        group.sort(key=lambda entry: (not same_name(entry),
                                      -entry["hit"]["time"]))
    other.sort(key=lambda group: (not same_name(group[0]),
                                  -group[0]["hit"]["time"]))

    lines = [f"{PROGRAM}: file names containing \"{stem}\", any case"]
    truncated = False
    if same:
        lines += ["", f"{heading}, newest first:"]
        for group in same:
            render_group(group, lines)
    if other:
        lines += ["", f"Candidates only, not counted as found: names "
                      f"containing \"{stem}\", any named {name} first, then "
                      f"newest first:"]
        for group in other[:MAX_ENTRIES_PER_LIST]:
            render_group(group, lines)
        if len(other) > MAX_ENTRIES_PER_LIST:
            truncated = True
            lines.append(f"  ... and {len(other) - MAX_ENTRIES_PER_LIST} "
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
            listed = report.get("listed_worktrees")
            if listed:
                excepting += (", and the worktree(s) the main clone lists "
                              "outside them: " + ", ".join(listed))
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
            if git.get("candidates_cut"):
                truncated = True
                lines.append(f"  {machine} git: every path named {name} was "
                             f"kept, and {git['candidates_cut']} older "
                             f"candidate path(s) were cut, past the newest "
                             f"{MAX_GIT_PATHS_PER_CLONE} per clone")
        if result.get("candidate_matches_total", 0) > MAX_FILE_HITS_PER_MACHINE:
            truncated = True
            lines.append(f"  {machine}: {result['file_matches_total']} files "
                         f"matched; every one named {name} was kept, and "
                         f"only the newest {MAX_FILE_HITS_PER_MACHINE} of the "
                         f"others were considered")
    if failed or not_searched:
        lines += ["", "NOT searched, or searched only in part:"]
        lines += [f"  {machine}: {reason}" for machine, reason in not_searched]
        lines += [f"  {failure}" for failure in failed]
    lines += ["", f"Took {elapsed:.1f} s."]

    found = bool(same)
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
        if other:
            instructions.append(
                f"No copy {wanted_label} was found: the files above are "
                f"candidates only; check a candidate's content before you "
                f"say it is the file.")
        instructions.append(
            "When you report this, say where you looked (the Searched lines "
            "above, and the places the backup search below prints); do not "
            "say the file does not exist.")
    if instructions:
        lines += [""] + instructions
    if found:
        code = 0
    elif incomplete:
        code = 3
    else:
        code = 1
    return "\n".join(lines) + "\n", code


def write_text(text):
    """Write and flush stdout, replacing characters the output encoding cannot represent."""
    sys.stdout.write(text.encode("utf-8", "surrogateescape")
                     .decode("utf-8", "replace"))
    sys.stdout.flush()


def run_backup_search_after_nothing_found(query, git_search_complete):
    """Run the backup search and return closing lines describing the result."""
    # Run as a subprocess to avoid circular imports; keep absolute paths to avoid matching another seat.
    # Backup transcript hits can name files that never existed, so they cannot change the locator exit code.
    program = (os.environ.get(BACKUP_SEARCH_PROGRAM_VARIABLE)
               or str(pathlib.Path(__file__).resolve().parent
                      / BACKUP_SEARCH_PROGRAM_NAME))
    command = [sys.executable, program, query]
    for surface in BACKUP_SEARCH_SURFACES_ALREADY_SEARCHED:
        command += ["--skip", surface]
    covered = (", which the git search above covered" if git_search_complete
               else "")
    write_text("\nNo copy was found, so the backup search runs now, without "
               f"its git surfaces{covered}:\n"
               f"  $ {shlex.join(command)}\n\n")
    try:
        process = subprocess.Popen(
            command, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env=environment_without_git_redirecting_variables())
    except OSError as error:
        return [f"The backup search could not start ({error}): tell the user "
                f"it did not run, and do not say the file does not exist."]
    summary_printed = False
    for line in process.stdout:
        text = line.decode("utf-8", "replace")
        write_text(text)
        summary_printed = summary_printed or text.startswith(
            BACKUP_SEARCH_SUMMARY_OPENINGS)
    code = process.wait()
    if not summary_printed:
        how = (f"it was stopped by signal {-code}" if code < 0
               else f"it exited {code}")
        return [f"The backup search did not finish ({how} before its summary "
                f"line): tell the user that the places it did not print were "
                f"not searched, and do not say the file does not exist."]
    if code == BACKUP_SEARCH_FOUND_EXIT:
        return ["The backup search found it: before you say it can be "
                "recovered, check that the place a FOUND line names holds the "
                "file's content, since a transcript matches whenever the path "
                "was only typed in it."]
    if code == BACKUP_SEARCH_INCOMPLETE_EXIT:
        return ["Tell the user which places the backup search could NOT "
                "search, and why: its Could NOT search line names them."]
    return []


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog=PROGRAM,
        description="Find every copy of a file by its name, on the Mac and "
                    "ned-box, newest first: checkouts, the log-store, the "
                    "handoffs, and git history including the reflog.")
    parser.add_argument("query", help="a file name or a path, which may be "
                        "written in the scp form nedlern@ned-box:<path>; its "
                        "name's stem is matched, case-insensitively, anywhere "
                        "in a file's name")
    parser.add_argument(THIS_MACHINE_JSON_FLAG, metavar="SURFACES_JSON",
                        help="search only this machine, over these surfaces, "
                             "and print the answer as JSON: what the program "
                             "runs on the other machine over ssh")
    args = parser.parse_args(argv)
    try:
        query = resolve_query(args.query)
    except ValueError as error:
        parser.error(str(error))
    except CurrentDirectoryIsGone as error:
        sys.stdout.write(
            f"{PROGRAM}: the current directory no longer exists ({error}), so "
            f"the relative path {args.query!r} cannot be made absolute; "
            f"nothing was searched.\n\n"
            f"Run again with the file's absolute path, or from a directory "
            f"that exists.\n"
            f"When you report this, do not say the file does not exist: "
            f"nothing was searched.\n")
        return 3
    # Git cannot start from a removed working directory; the resolved query no longer needs cwd.
    os.chdir("/")
    stem = query_stem(query)
    if not stem:
        parser.error("the query has no file name to match")
    name = query_name(query)
    check_tracked = len(parts_of(query)) > 1

    if args.this_machine_json:
        result = search_this_machine(json.loads(args.this_machine_json), stem,
                                     name, check_tracked)
        json.dump(result, sys.stdout)
        return 0

    started_at = time.monotonic()
    plan = plan_for_this_run()
    other = plan.get("other")
    not_searched = []
    remote = None
    if other and other.get("ssh_target"):
        remote, error = start_remote_search(other, query)
        if error:
            not_searched.append((other["machine"], error))
    elif other:
        not_searched.append((other["machine"],
                             other.get("not_searched_because", "no route")))

    results = [search_this_machine(plan["this"], stem, name, check_tracked)]
    if remote:
        answer = finish_remote_search(remote, other)
        if isinstance(answer, dict):
            results.append(answer)
        else:
            not_searched.append((other["machine"], answer))

    target = query_target(query, *layouts_and_spellings(plan))
    text, code = render(query, target, results, not_searched,
                        time.monotonic() - started_at)
    write_text(text)
    if code != 0:
        closing = run_backup_search_after_nothing_found(
            target.get("canonical", target["path"]), code == 1)
        if closing:
            write_text("\n" + "\n".join(closing) + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
