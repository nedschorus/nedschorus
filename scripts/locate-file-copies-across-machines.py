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
                        /private/tmp/claude-501 (scratch worktrees),
                        and every worktree the main clone lists outside them
             handoffs   /Users/el/.claude/handoffs
             git        every clone found under the checkouts
    ned-box  checkouts  /home/nedlern/agents, /home/nedlern/Projects,
                        /tmp/claude-1000 (scratch worktrees),
                        and every worktree the main clone lists outside them
             log-store  /home/nedlern/nedschorus-logs, except transcripts/
             handoffs   /home/nedlern/.claude/handoffs
             git        every clone found under the checkouts

The worktrees a main clone lists (`git worktree list`) are searched even when
they sit outside every root: an ad-hoc worktree directly under /tmp, such as
ned-box's /tmp/pr619-fix-round-baseline or the Mac's /private/tmp/ghi-569-fix,
was never searched (PR 703 review 5299980640). Measured 2026-09-24: one such
worktree on each machine; listing them took 3 to 34 ms and searching one 12 ms.

FOUND MEANS THE SAME NAME, AND THE SAME PATH WHEN ONE IS GIVEN. A query that is
a bare file name, with no `/` in it, is found by a copy with that name, in any
case. Any other query names one path, and is found only at that path -- or,
inside this repository, at the same place in any of its checkouts and in its
history (see below): a dispositions.md in some other directory is not found
for `md-review-records/x/dispositions.md`. A query that is not absolute is made
absolute from the current directory BEFORE anything else looks at it, `./x`
and `../x` included, so it gets exactly the answer its absolute spelling gets
through the one code path. PR 703 review 5307849568 measured what a separate
path for relative queries did: `.claude/settings.local.json` asked from a
seat whose own copy was absent exited 0 on another project's file, and
`./CLAUDE.local.md` became the bare name and found every seat's. When the
current directory no longer exists -- a shell still standing in a removed
worktree, which two transcripts show (PR 703 review 5307798976) -- a relative
query cannot be placed: the program says so, searches nothing and exits 3.
The log-store reuses generic names across its records (measured 2026-09-24:
40 dispositions.md, 31 fast-read.md, 29 reference-check.md, 26 memory.md,
11 SKILL.md), and the backup search's log-store surface read an unrelated
record as the file until the same rule was applied there (PR 702 review
5298743638). Every other file whose name
contains the stem, including a same-name copy in another directory, is a
candidate, to be checked by content; candidates do not make the answer
"found".

A FILE GIT DOES NOT TRACK IS FOUND ONLY AT ITS OWN PATH. A file in a checkout
of this repository that git does not track there -- a seat's CLAUDE.local.md,
its .claude/settings.local.json, an uncommitted draft -- belongs to that one
checkout, so another checkout's file at the same place is a different file:
it is a candidate, never the copy found, unless the query names that file's
own path. A tracked file at the same place in another checkout is the same
file on another branch, and is found as before. PR 703 review 5299970582
measured the fault: on ned-box, /Users/el/agents/merge-lane/CLAUDE.local.md
exited 0 on merge-lane-2's CLAUDE.local.md, handing a seat another seat's
standing instructions as its own. A relative query names its own path from
the current directory, so a relative query from inside a checkout finds that
checkout's untracked file. A bare file name still finds every file of that
name, tracked or not: it asks for any file so named, and each copy is listed
with its machine and path. Which files git tracks is asked with one
`git ls-files` per checkout that holds a hit, and only for a query with
directories in it. When git cannot answer for a checkout, its files are
listed as "tracking unknown" and counted only at their own path, as an
untracked file is: an unanswered question is not an answer.

AN ABSOLUTE QUERY INTO THIS REPOSITORY IS COMPARED BY ITS PATH INSIDE ITS
CHECKOUT. A git hit's path is relative to its clone, and the same file sits in
every seat's checkout, so `/Users/el/agents/merge-lane/docs/x.md` is found by
commit <hash>'s `docs/x.md` and by `/home/nedlern/agents/<seat>/docs/x.md`.
Where a path sits in this repository is read from one ordered list of the
places this repository's checkouts live, written from the map of record,
docs/nedschorus-wiki/nedschorus-fleet-machine-paths-and-checkouts.md, and
checked on 2026-09-24 against `git worktree list` in each machine's main clone
(74 checkouts on the Mac, 15 on ned-box, every one in a place below):

    place                              Mac                  ned-box
    the main clone                     /Users/el/Projects/  /home/nedlern/
                                         nedschorus           Projects/nedschorus
    a seat's checkout, each child of   /Users/el/agents     /home/nedlern/agents
    a task worktree, nested in either  <checkout>/.claude/worktrees/<name>
      of the above
    a scratch or ad-hoc worktree,      /tmp                 /tmp
      at any depth

  - Under the main clone, or under a child of a seats directory, the path
    inside the checkout is what follows it, with a leading
    `.claude/worktrees/<name>/` taken off: that is where Claude Code puts a
    task worktree, and the file sits in that worktree, not in the checkout
    around it (PR 703 review 5299440729: a removed nested worktree turned a
    found query into a not-found one). This needs nothing on disk, so it
    answers the same whether the checkout is there, removed, or on the other
    machine.
  - Under /tmp a worktree can sit at any depth, so its root is not in the
    path. A query there is compared by the longest tail of the path, two
    components or more, that a copy of this repository holds. A tail of one
    component is not trusted, because `<worktree>/docs/README.md` would then
    be found by the clone's own README.md. A file found there, which is on
    disk, is placed by the nearest `.git` above it, when that `.git` belongs
    to this repository.
  - Other children of Projects are other projects (the Mac holds 31, 23 of
    them git checkouts, the legacy nedlern one among them), and so is
    anything else outside the list: a query there is found only by the file
    at that very path, or by a commit of that project's own clone at that
    path. The same holds for the log-store and the handoffs.
    Another project's files and git history never count as a copy of this
    repository's path, nor this repository's as a copy of theirs (PR 703
    review 5299487158: another project's root README.md under
    /Users/el/Projects counted as found for this repository's).
THIS REPOSITORY is the main clone's git directory on each machine: every seat
and task worktree resolves to it through its `.git` file (measured 2026-09-24:
no seat directory on either machine is a clone of its own). A git hit counts
for a path inside a checkout only when it comes from that git directory.
A file at a checkout's root, such as `/Users/el/agents/merge-lane/CLAUDE.md`,
is found only at the root of a checkout, not by a CLAUDE.md in some
subdirectory.
EVERY PATH IS COMPARED IN ONE SPELLING. On the Mac /tmp is /private/tmp, and
the Mac mounts ned-box's home at /Volumes/nedhome (named in
.claude/hooks/backup-and-snapshot-write-guard.py; the map of record does not
list it), so `/Volumes/nedhome/nedschorus-logs/x.md` is
`/home/nedlern/nedschorus-logs/x.md`. Both the query and every hit are put in
the canonical spelling before any comparison (PR 703 review 5299440729: a
scratchpad file asked as /tmp/claude-501/... was not found at its own path).
/private/tmp itself is not searched on the Mac, only /private/tmp/claude-501:
it holds the backup search's snapshot mounts of the whole disk, and a find
over it ran past 120 s on 2026-09-24. A worktree there is still found through
its commits.

THE QUERY MAY BE WRITTEN AS IT IS CITED. `nedlern@ned-box:/home/...`, the scp
form CLAUDE.md prescribes for log-store citations, is read as the path after
the colon; so is `ned-box:<path>`. A host is recognised when a user name comes
before it or when it is a machine this program knows, so a file name that
merely holds a colon is left alone. `~` is expanded, on ned-box to
/home/nedlern. A relative path after an scp host is inside that host's home,
when this program knows it; a relative path with directories after a host
whose home it does not know is a usage error, rather than a path guessed on
this machine. PR 703 review 5299114606 measured the scp form never being
found, even at its exact path.
Measured 2026-09-24: `plan.md`, a name no file has, matched 1,767 names on
the Mac alone, and this program exited 0 on them without naming the next
step. The same fault was found in the backup search's log-store surface on
PR "The lost-file tool searches git's reflog and the log-store, and prints
each place as it finishes" (review 5298558956), where a stem match printed a
recovery command for an unrelated file. A renamed copy, which the research's
E11 and E14 needed, is still listed, as a candidate.

The log-store's transcripts/ directory is left out on purpose: its files are
named by session id, and searching inside transcripts was not part of what
was approved. `.git`, `__pycache__`, `node_modules`, `.venv` and `venv`
directories are never descended into.

THE GIT SURFACE is `git log --reflog --all --full-history` over each clone,
with a pathspec that matches the name anywhere in the tree. `--full-history`
is needed because with a pathspec git otherwise simplifies history: at a
merge that leaves the path as its first parent had it, git follows that
parent alone, so a file added and deleted on a merged topic branch is never
reached. Measured 2026-09-24: in ned-box's shared clone, `git log --reflog
--all -- docs/drafts/simplification-review-prompt-draft.md` printed nothing,
and with `--full-history` it printed commits 40fef4e and ae3b93a, both on
origin/main; 32 of the 662 deleted paths in that clone were hidden that way
(PR 703 review 5298686798). The flag cost about 0.04 s on the Mac's main
clone. scripts/find-deleted-path-across-backups.py passes it for the same
reason. `--reflog` is what the research's
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

WHAT IT PRINTS. Two lists: the copies found (see FOUND MEANS above), every one
of them, newest first; then the candidates, cut to the newest few, those with
the query's name first. Each line carries the time (UTC), the machine, the surface, the path and the size; a git hit names
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
    0  at least one copy was found, as FOUND MEANS above defines it (a
       surface that failed is still printed)
    1  no copy was found, and every surface was searched; candidates may
       still be listed
    2  bad invocation (argparse's own exit)
    3  no copy was found, and at least one surface or machine could NOT be
       searched -- so "not found" is not established; or the query was a
       relative path and the current directory no longer exists, so nothing
       was searched
A failed surface never reads as "not found": that is why 3 exists apart
from 1. A candidate never reads as "found": that is why 1 and 3 allow them.

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

# The variables that point git at another repository. They are dropped from
# the environment of every git this program runs in a checkout by its path,
# so a caller's GIT_DIR cannot answer for the checkout asked about; the same
# six scripts/run-all-test-suites.py strips.
GIT_REDIRECTING_VARIABLES = (
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
    "GIT_COMMON_DIR", "GIT_ALTERNATE_OBJECT_DIRECTORIES")

PLAN_ENVIRONMENT_VARIABLE = "LOCATE_FILE_COPIES_ACROSS_MACHINES_PLAN"
THIS_MACHINE_JSON_FLAG = "--this-machine-json"
# The backup search, beside this program in the same checkout. It is printed
# as `python3 <absolute path>`, because the file is not executable (mode
# 100644 on main) and an agent may be in any directory when it runs it.
BACKUP_SEARCH_PROGRAM_NAME = "find-deleted-path-across-backups.py"

# A match larger than this is listed but not hashed, so it is never collapsed
# with an identical copy. Hashing is the only part of a search whose cost
# grows with file size.
HASH_SIZE_LIMIT_BYTES = 64 * 1024 * 1024
# Per machine, only the newest this-many candidate file matches are hashed
# into the answer; per clone, only the newest this-many candidate paths. A
# one-letter query must still answer in seconds. A copy with the query's own
# name is never cut by either cap: the remedy the answer offers for a cut,
# "run again with more of the name", cannot help when the query is already
# the whole name (PR 703 review 5298659418: `CLAUDE.md` lost two copies to
# the cap on ned-box).
MAX_FILE_HITS_PER_MACHINE = 300
MAX_GIT_PATHS_PER_CLONE = 300
# Candidate entries printed; the rest are counted. Same-name copies are all
# printed.
MAX_ENTRIES_PER_LIST = 25
# Directories never descended into, besides `.git`: bytecode, and third-party
# dependency trees no agent writes into. Measured 2026-09-23 on the Mac:
# /Users/el/Projects/route-spectrum took 0.44 s to search with its
# node_modules and 0.02 s without it.
SKIPPED_DIRECTORY_NAMES = ("__pycache__", "node_modules", ".venv", "venv")

# A machine plan has three parts. `surfaces` are the places searched.
# `this_repository` is where this repository's checkouts live on that
# machine, the ordered list the module docstring sets out: `clones` (the main
# clone), `checkout_parents` (every child a checkout) and `scratch_trees` (a
# worktree at any depth); a task worktree nested at NESTED_WORKTREE_PARTS
# inside a clone or a parent's child is recognised under both. `spellings` are
# [alias, canonical] pairs: a path under the alias is compared as the same
# path under the canonical prefix.
NESTED_WORKTREE_PARTS = (".claude", "worktrees")
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
    # How the Mac spells this machine's paths: its mount of ned-box's home.
    "spellings": [["/Volumes/nedhome", "/home/nedlern"]],
}
# The machines a bare `<host>:<path>` query may name, and where `~` is there.
KNOWN_HOST_HOMES = {NED_BOX_HOSTNAME: "/home/nedlern"}
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


def is_same_name(basename: str, name: str) -> bool:
    """Whether a file named `basename` is a copy of the query named `name`:
    the same name in any case, or, for a query with no suffix, the same stem.
    Only these count as found; every other name that holds the stem is a
    candidate."""
    basename, name = basename.lower(), name.lower()
    return basename == name or (
        "." not in name and pathlib.PurePath(basename).stem == name)


def split_host(query):
    """(host, path) for a query in the scp form `[user@]host:path`, or
    (None, query). A host is taken only when a user name comes before it or
    it is in KNOWN_HOST_HOMES, and never when a `/` comes before the colon."""
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
    """A relative path was asked for from a directory that no longer
    exists, so there is nothing to make it absolute from."""


def resolve_query(query, cwd=None):
    """The query as a plain path: an scp host prefix taken off, `~`
    expanded, and every path with a `/` in it that is not absolute made
    absolute from `cwd` (the current directory by default). A bare file name,
    with no `/` at all, is returned as it is. Raises CurrentDirectoryIsGone
    when the current directory is needed and no longer exists, and
    ValueError for a relative path with directories on a host whose home
    is not known."""
    host, path = split_host(query)
    if host is not None and not path.startswith("/"):
        # A relative path after a host is inside that host's home.
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
    """`path` in its canonical spelling: under the first alias it starts
    with, that alias is replaced by its canonical prefix."""
    for alias, canonical in spellings:
        alias, canonical = alias.rstrip("/"), canonical.rstrip("/")
        if path == alias or path.startswith(alias + "/"):
            return canonical + path[len(alias):]
    return path


def parts_below(path, root):
    """`path`'s components below `root`, or None when it is not under it.
    Both are in one spelling already."""
    root = root.rstrip("/")
    if path == root:
        return []
    if path.startswith(root + "/"):
        return parts_of(path[len(root) + 1:])
    return None


def inside_nested_worktree(parts):
    """A path inside a checkout, with a task worktree nested at
    NESTED_WORKTREE_PARTS/<name>/ taken off its front."""
    depth = len(NESTED_WORKTREE_PARTS)
    if (len(parts) > depth + 1
            and tuple(parts[:depth]) == NESTED_WORKTREE_PARTS):
        return parts[depth + 1:]
    return parts


def place_in_this_repository(path, layouts):
    """Where the canonical absolute `path` sits among this repository's
    checkouts, walking the ordered list the module docstring sets out:
    ("checkout", its path inside the checkout), ("scratch", its components
    below the scratch tree, the checkout's root being unknown), or None when
    it is in none of the places this repository's checkouts live."""
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
    """(this repository's layouts, every spelling pair) of both machines."""
    layouts, spellings = [], []
    for machine in (plan.get("this"), plan.get("other")):
        if machine:
            layouts.append(machine.get("this_repository", {}))
            spellings += machine.get("spellings", [])
    return layouts, spellings


def this_repository_git_dirs(layout):
    """The git directories that are this repository on this machine: each
    main clone's, as git_dirs_of names them."""
    return set(git_dirs_of([os.path.join(clone, ".git")
                            for clone in layout.get("clones", [])]))


def place_of_file(path, layout, spellings, this_git_dirs, cache):
    """(the checkout's root, the file's path inside it, "/"-joined) for a
    file on this disk, or None when the file is not in a checkout of this
    repository. Under a scratch tree, where the path does not say where the
    worktree starts, the nearest `.git` above the file decides, and only
    when it is this repository's; `cache` remembers each directory's
    answer."""
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


def tracked_in_checkout(root, relative_paths):
    """(the paths among `relative_paths` that git tracks in the checkout at
    `root`, failure or None). A root with no `.git` tracks nothing."""
    if not os.path.lexists(os.path.join(root, ".git")):
        return set(), None
    environment = {key: value for key, value in os.environ.items()
                   if key not in GIT_REDIRECTING_VARIABLES}
    command = ["git", "-C", root, "ls-files", "-z", "--",
               *[":(literal)" + path for path in relative_paths]]
    try:
        result = subprocess.run(command, capture_output=True, env=environment,
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


def listed_worktrees_outside(layout, surfaces):
    """(directories, failures): each worktree a main clone of this
    repository lists that exists and lies under none of `surfaces`' roots.
    Both sides are compared resolved, since git records a worktree's path
    with its symbolic links resolved (/private/tmp for the Mac's /tmp), and
    a worktree under a root would otherwise be searched twice."""
    roots = [os.path.realpath(root)
             for surface in surfaces for root in surface["roots"]]
    outside, failures = set(), []
    for clone in layout.get("clones", []):
        git_dir = os.path.join(clone, ".git")
        if not os.path.isdir(git_dir):
            continue
        try:
            result = subprocess.run(
                ["git", "--git-dir", git_dir, "worktree", "list",
                 "--porcelain"], capture_output=True,
                timeout=LOCAL_COMMAND_TIMEOUT_SECONDS)
        except (subprocess.TimeoutExpired, OSError) as error:
            failures.append(f"the worktrees {clone} lists could not be read: "
                            f"{error}")
            continue
        if result.returncode != 0:
            lines = result.stderr.decode("utf-8", "replace").strip().splitlines()
            failures.append(f"the worktrees {clone} lists could not be read: "
                            + (lines[-1] if lines else "no message"))
            continue
        for line in result.stdout.decode("utf-8", "surrogateescape").splitlines():
            if not line.startswith("worktree "):
                continue
            worktree = line[len("worktree "):]
            if os.path.isdir(worktree) and not any(
                    parts_below(os.path.realpath(worktree), root) is not None
                    for root in roots):
                outside.add(worktree)
    return sorted(outside), failures


def query_target(resolved, layouts, spellings):
    """What a found copy must match, for a query resolve_query returned:
    either a bare file name or an absolute path. `kind` is "name" (a bare
    file name), "checkout" (a path whose path inside this repository's
    checkout is `parts`), "scratch" (a path under a scratch tree: `parts` are
    its components below the tree), or "absolute" (any other path). `path` is
    the resolved query; `canonical` is it in the canonical spelling, which
    every comparison uses, and the one place a file git does not track is
    found for it."""
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
    """Whether two component lists name the same path: the directories equal
    in any case, the names the same by is_same_name."""
    return (bool(parts) and bool(wanted)
            and [part.lower() for part in parts[:-1]]
            == [part.lower() for part in wanted[:-1]]
            and is_same_name(parts[-1], wanted[-1]))


def ends_with(parts, tail):
    return len(parts) >= len(tail) and same_parts(parts[len(parts) - len(tail):],
                                                   tail)


def keep_same_name_and_newest(items, name, cap, basename_of):
    """`items`, newest first, with every same-name item kept and only the
    newest `cap` of the others."""
    kept, others = [], 0
    for item in items:
        if is_same_name(basename_of(item), name):
            kept.append(item)
        elif others < cap:
            kept.append(item)
            others += 1
    return kept


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
        # A directory without git's three markers -- a HEAD file, objects/
        # and refs/ -- is not a repository, and git log refuses it ("not a
        # git repository"). Measured: on 2026-09-23 five on the Mac, probe
        # repositories under /private/tmp with no HEAD; on 2026-09-24 seven
        # on ned-box under /tmp/claude-1000, git-variable experiments whose
        # objects/ was written elsewhere. They hold nothing to search, so
        # they are skipped rather than reported as places not searched.
        if (os.path.isfile(os.path.join(git_dir, "HEAD"))
                and os.path.isdir(os.path.join(git_dir, "objects"))
                and os.path.isdir(os.path.join(git_dir, "refs"))):
            found.setdefault(os.path.realpath(git_dir), git_dir)
    return sorted(found)


def git_log_command(git_dir, stem):
    return ["git", "--git-dir", git_dir, "log", "--reflog", "--all",
            "--full-history", "--topo-order", "--no-renames", "--raw",
            "--no-abbrev", "-z",
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


def run_git_log(git_dir, stem, name):
    """(hits, failure, candidate paths cut by the cap) for one clone."""
    try:
        result = subprocess.run(git_log_command(git_dir, stem),
                                capture_output=True,
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
    """Everything this machine holds under the plan, as one JSON-ready dict:
    the hits, a report per surface, and the git report. With
    `check_tracked`, a file hit in a checkout of this repository carries
    `untracked` when git does not track it there, or `tracking_unknown` when
    git could not say. A git hit from a clone that is not this repository
    carries `canonical`, the path it had in that clone's own work tree."""
    surfaces = machine_plan["surfaces"]
    layout = machine_plan.get("this_repository", {})
    spellings = machine_plan.get("spellings", [])
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
    # A file git does not track in its checkout is that checkout's own, and
    # counts as a copy only at its own path (see the module docstring).
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
        # Another project's clone: its path is the path in that clone's own
        # work tree, so a query for that very path finds its history.
        if (not hit["this_repository"]
                and os.path.basename(hit["clone"]) == ".git"):
            hit["canonical"] = canonical_path(
                os.path.join(os.path.dirname(hit["clone"]), hit["path"]),
                spellings)
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
    """The command line ssh hands the other machine's shell: this program,
    read from stdin, told which surfaces to search."""
    surfaces = {key: machine_plan[key]
                for key in ("machine", "surfaces", "this_repository",
                            "spellings")
                if key in machine_plan}
    return " ".join(["python3", "-", THIS_MACHINE_JSON_FLAG,
                     shlex.quote(json.dumps(surfaces)), "--",
                     shlex.quote(query)])


def start_remote_search(other, query):
    """(process, error) for the other machine's search. The ssh connection
    starts at once, so its handshake overlaps this machine's search; the
    program is sent on stdin, and the search there runs, only when
    finish_remote_search is called. PR 703 review 5299114606 measured it: the
    search there runs after this machine's, adding its own time, about 0.3 s,
    in series."""
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


def render(query, target, results, not_searched, elapsed):
    """(text, exit code) for the merged results of both machines. `query` is
    the resolved query and `target` its query_target."""
    stem = query_stem(query)
    name = query_name(query)
    kind, wanted = target["kind"], target["parts"]
    entries = [{"machine": result["machine"], "hit": hit}
               for result in results for hit in result["hits"]]

    def checkout_parts(entry):
        """A hit's path inside this repository's checkout, or None when it is
        not a copy of this repository: a git hit from another repository's
        clone, or a file outside this repository's checkouts."""
        hit = entry["hit"]
        if hit["kind"] == "git":
            return parts_of(hit["path"]) if hit.get("this_repository") else None
        place = hit.get("in_this_repository")
        return parts_of(place) if place else None

    def own_path_only(entry):
        """A file git does not track in its checkout, or where git could not
        say: it counts only at its own path."""
        hit = entry["hit"]
        return hit["kind"] == "file" and bool(
            hit.get("untracked") or hit.get("tracking_unknown"))

    # Under a scratch tree the checkout's own directory is not in the path:
    # its path inside the checkout is the longest tail of the query, two
    # components or more, that a copy of this repository holds. A file git
    # does not track is no copy of the repository's, so it sets no anchor.
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
        if hit.get("canonical") and same_parts(
                parts_of(hit["canonical"]), parts_of(target["canonical"])):
            return True
        # A file git does not track in its checkout counts only at its own
        # path, just tested (PR 703 review 5299970582: another seat's
        # CLAUDE.local.md was found for this seat's).
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

    # Found copies and candidates are separated BEFORE copies are grouped by
    # content, so an identical file at some other path stays a candidate
    # rather than printing as "same content" under the found list (PR 703,
    # Codex's review in 5299487158).
    same = group_by_content([entry for entry in entries if found_copy(entry)])
    other = group_by_content([entry for entry in entries
                              if not found_copy(entry)])
    # A candidate group is led by its newest same-name copy, and candidate
    # groups holding one come first.
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
        backup_search = pathlib.Path(__file__).resolve().parent / \
            BACKUP_SEARCH_PROGRAM_NAME
        command = (f"`python3 {shlex.quote(str(backup_search))} "
                   f"{shlex.quote(query)}`")
        if other:
            instructions += [
                f"No copy {wanted_label} was found: the files above are "
                f"candidates only; check a candidate's content before you "
                f"say it is the file.",
                f"Run next {command}, which searches git history and the "
                f"backups.",
            ]
        else:
            instructions.append(
                f"Nothing was found: run next {command}, which searches git "
                f"history and the backups.")
        instructions += [
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
    stem = query_stem(query)
    if not stem:
        parser.error("the query has no file name to match")
    name = query_name(query)
    # Only a query with directories asks for a path, and only a path query
    # needs to know which files git tracks.
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
    # A path that is not valid UTF-8 prints with a replacement character
    # rather than stopping the whole answer with an encoding error.
    sys.stdout.write(text.encode("utf-8", "surrogateescape")
                     .decode("utf-8", "replace"))
    return code


if __name__ == "__main__":
    sys.exit(main())
