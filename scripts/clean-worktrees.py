#!/usr/bin/env python3
"""Report or remove the worktrees whose work is done, judged by each worktree's owner file, or for
a merge-lane review checkout by its pull request, or, for any worktree, by its having been idle with
nothing unsaved in it.

WHICH WORKTREES. Every worktree of the clone except its main checkout, the
reference-checkout, wherever the worktree is. An idle worktree, as IDLE
WORKTREES below says, can be removed whatever its owner file says. Otherwise
only a worktree holding an owner file, or a merge-lane review checkout, as
MERGE-LANE REVIEW CHECKOUTS below says, can be removed:
scripts/worktree-owner-file-read-and-write.py says where the file is, what it
holds, and when its owner, an agent-seat or an agent-session, counts as
running. A worktree that is not idle is KEPT, with the reason, when:

  - its owner file cannot be read;
  - it has no owner file, as agent-homes and worktrees made by hand have,
    and is not a merge-lane review checkout;
  - it is locked with `git worktree lock`, as Claude Code locks a subagent's
    worktree while the subagent runs, apart from the lock CLAUDE CODE'S LOCK
    below unlocks;
  - git would prune it, its directory being gone, unless STOPPED PARTWAY
    below applies;
  - a rebase, merge, cherry-pick or revert is in progress in it, or git
    cannot locate the files that show one;
  - whether its owner runs cannot be read;
  - a live process has its working directory inside it, or the vacancy check
    (lsof) cannot be trusted: lsof missing, failing, timing out or listing no
    working directories at all.

Otherwise the owner and the branch's pull request decide. The pull requests
come from one `gh pr list --state all` per invocation; a pull request is the
branch's when its head branch has the branch's name, and, for a merged or
closed one, when its head commit is the worktree's HEAD, so a new worktree on a
reused branch name is not judged by an old pull request. If gh fails, every
worktree whose verdict needs a pull request is kept.

  WHILE ITS OWNER RUNS, a worktree is removed only when its branch's pull
  request has merged or been closed and it holds no uncommitted or untracked
  file; every other worktree is kept, a new one with no pull request among
  them.

  ONCE ITS OWNER HAS STOPPED, an open pull request on its branch keeps it.
  Otherwise it is removed, after two steps, each of which keeps it when it
  fails: commits on no branch, in a worktree whose detached HEAD has commits
  origin/main lacks, get a branch of their own, named
  worktree-cleaner-detached-commits-<worktree directory name>-<12 hex digits
  of the commit>; and its uncommitted and untracked files go to a
  work-snapshot (nc-systems/handoff/uncommitted-work-snapshots.py) owned by
  this invocation's own process and carrying the owner file's agent-seat, so
  the agent-seat's next agent-session is told of it once this invocation has
  ended. The branch is kept, unless BRANCHES deletes it.

IDLE WORKTREES. A worktree is idle, and is removed, owner file or not,
when all of these hold: it is not an agent-home, which is a worktree directly
inside ~/agents or one whose own git directory holds AGENT_HOME_MARKER_FILE_NAME;
no file or directory in it or in its own git directory, by mtime, has changed
for IDLE_WORKTREE_REMOVED_AFTER_DAYS days; it holds no uncommitted or untracked
file; every commit of its HEAD is on a remote-tracking ref of origin, as last
fetched; no open pull request has its branch as head branch or its HEAD as
head commit; and no rebase, merge, cherry-pick or revert is in progress in it.
The mtimes are read before any git command, and the cleaner's `git status`
runs with --no-optional-locks, so that its own index refresh does not reset
the clock. Removing an idle worktree loses nothing: its branch is kept, unless BRANCHES
deletes it. When any of these cannot be read, such as gh
failing or a file that cannot be read, the worktree is not idle and the other
rules judge it. A locked worktree is not idle, since the lock is judged first,
nor is one whose ended Claude Code lock --remove unlocks, since writing its
owner file changes its git directory. An idle worktree is still kept when the
vacancy check finds or cannot rule out a live process in it, or git cannot
list its files; its ignored files are named and discarded with it, as for any
removal.

CLAUDE CODE'S LOCK. A lock in the form Claude Code writes on a subagent's
worktree, "claude agent agent-<id> (pid N start T)", once no process N that
started at T runs, as /proc says on Linux and ps says on macOS, where T is the
date ps prints, such as "Tue Nov  3 21:24:32 2026", is not kept for: --remove unlocks
the worktree, first writing it an owner file when it has none, naming that
ended agent-session and the agent-seat whose Claude Code transcripts name
subagent agent-<id> (scripts/worktree-owner-file-read-and-write.py says which
transcripts those are), then judges it like any other. When no agent-seat's
transcripts name the subagent, or more than one's do, the worktree is kept,
locked, and named on a line of its own for the user to keep or delete. The
report modes say what --remove would do and change nothing. While whether
process N runs cannot be read, and on any platform but Linux and macOS, the lock
keeps the worktree, as does a lock in any other form.

MERGE-LANE REVIEW CHECKOUTS. A worktree with no owner file directly inside
~/.cache/merge-lane-review-worktrees, where merge-lane-2 checks out each pull
request it reviews, is a merge-lane review checkout, judged by the pull
request its directory name holds: the one part of the name, split at each
hyphen, that is digits, optionally after `pr`, optionally followed by `r`
and digits, then optionally by one letter, as in pr2700-head,
tools-main-2700r2, tools-main-2343b or verdict-2587r1. It is removed when that
pull request was merged or closed at least 24 hours ago, once the lock,
prune, in-progress operation and vacancy checks above pass. It is kept, with
the reason, when its name holds no such part or more than one, as main and
main-green-<commit> do, when the pull request is open, finished less than 24
hours ago, or missing from gh's listing, or when gh fails or gives no closing
time this program can read. The 24 hours are a margin, not a check: after a merge,
merge-lane-2's merge program removes the pull request's checkouts and tests
main in pr<n>-merge-commit-on-main-worktree, and between its steps no process
has a working directory there for the vacancy check to see. Its walks and its
cold-read and sanity-check records ship to the log-store before removal, as
for every worktree, and a record that does not ship keeps it. Its uncommitted,
untracked and ignored files are then named and discarded with it, with no
work-snapshot, since no agent-seat owns them and the pull request is
finished; commits on its detached HEAD get no branch, since a review
checkout's own commits, such as pr<n>-merged's local merge commit, are not
work anyone carries on.

Ignored files do not keep a worktree. Before --remove removes one, it ships
each walk in the worktree's docs/walk/, one for each <name>-minutes.md there,
with nc-systems/skills/walk-me-through/walk-files-ship.py, given by its walk text <name>.md, or by its
minutes when it has no walk text, which the shipper refuses, so the worktree
is kept, and each non-empty record directory under its cold-read-records/ and
sanity-check-records/ with the shipper of that kind
(LOG_STORE_RECORD_SHIPPERS), and keeps the worktree when any walk or record
is refused or fails to ship, printing the shipper's line. The shippers are
add-only, so a record already in the store ships as "nothing new". Files in
docs/walk/ that no walk ships, a walk never presented, which has no minutes,
or a file of no walk role, are named on a line of their own and go with the
worktree. The report modes name the walks and records and ship nothing. The
files a removal discards are listed, each file inside an untracked or ignored
directory named on its own; the report names them, and --remove names them
twice: before each removal, as files it will discard, and after a removal
succeeds, as files discarded with it. A removal that fails or is stopped
partway has named its files beforehand, so a loss is visible in the output
either way. Regenerable junk (.DS_Store, __pycache__, at any depth) is not
listed. If git cannot list a worktree's files, the worktree is kept. While
its owner runs, --remove checks again just before the removal, after the slow
checks and the shipments, that the worktree holds no uncommitted or untracked
file, so a file written meanwhile keeps it.

STOPPED PARTWAY. Just before `git worktree remove --force`, --remove writes
an unfinished-worktree removal record, a JSON file in clean-worktrees-unfinished-worktree-removal-records/ in the
clone's git directory, outside the worktree and its registration under
.git/worktrees/. It holds the worktree's path, its registration's path, its
branch, its HEAD and the files the removal discards, and it is deleted last,
after the removal is reported and logged, or its log line failed, so a run
killed or failing at any point of the removal leaves it whole. Each later --remove first finishes the removal of
every record: it deletes what is left of the worktree's directory and of its
registration, unless that registration's gitdir file names another worktree,
then deletes the branch as for any removal, --remove as BRANCHES says, and logs the removal with the record's discarded files.
--remove-worktree-and-force-delete-its-branch PATH finishes the record of
PATH the same way, deleting the branch with `git branch -D`. A record whose
worktree still has its .git file and a registration git would not prune
names a removal that never began: --remove deletes it, and the worktree is
judged as any other. The report modes name a recorded worktree as done, and
the dead-registration line leaves it out. A record that cannot be read is,
for --remove, a failure named with its file, and the run exits 1;
--remove-worktree-and-force-delete-its-branch names it as kept and goes on.

BRANCHES. The cleaner deletes a local branch other than main that no
worktree has checked out, and no other branch: with `git branch -d`, one
whose commits are all on origin/main; otherwise with `git branch -D`, one
that is the head branch of a merged or closed pull request and whose tip
equals that pull request's `refs/pull/<number>/head`, as GitHub reports just
before, and that no open task on that machine names in its `branches` field.
When GitHub cannot be reached, it deletes no branch with `-D`. It names each
deleted branch in the report modes. origin/main is read as fetched; a stale
ref only keeps more. A task list under ~/.claude/tasks/nedschorus-*-tasks
that cannot be read in full, or a ~/.claude/tasks that exists but cannot be
listed, stops every `-D` deletion, as GitHub out of reach does. GitHub out of
reach is named on a line of its own outside --only-done, and is no failure.
A task list not read is named, in every mode, on a line opening `FAILED: `,
and the run exits 1. The report modes also name a branch that only a done
worktree has checked out, which --remove deletes once it has removed that
worktree.

ONE NAMED WORKTREE OR BRANCH. --remove-worktree-and-force-delete-its-branch
PATH and --force-delete-branch NAME act on the one worktree or branch named,
for an agent-session that has decided its agent-seat will not carry it on;
the first prompt's list,
nc-systems/handoff/agent-seat-worktrees-and-branches-with-no-pull-request-first-prompt-list.py,
prints the command beside each entry. Unlike --remove,
--remove-worktree-and-force-delete-its-branch does not keep a worktree
because the agent-seat that owns it runs, since that agent-seat has decided;
an agent-session that owns it and runs still keeps it, as the next sentence
says. --remove-worktree-and-force-delete-its-branch keeps the worktree when it
is not a worktree of the clone other than its main checkout, has no owner file,
which a merge-lane review checkout always lacks, or one that cannot be read,
is locked, would be pruned, has a rebase, merge, cherry-pick or revert in
progress or git cannot say where to look for the
files that show one, is owned by an agent-session whose `claude` process runs or
whose state cannot be read, cannot be checked against the pull requests, has
an open pull request whose head branch is its branch or whose head commit is
its HEAD, holds a live process's working directory, or git cannot list its
files. Otherwise it ships its walks and records, puts its uncommitted and
untracked files in a work-snapshot, and removes it, keeping it when any of
these steps fails, as --remove does. A worktree on a detached HEAD has no
branch, so nothing more is deleted; its commits get no branch of their own,
and the removal's line in the log of removals names its head commit. A
worktree on a branch other than main then has that branch deleted with
`git branch -D`, even when origin/main lacks some of its commits, and the
branch's line in the log names its last commit. --force-delete-branch keeps
the branch when it is main,
does not exist, is checked out in a worktree, cannot be checked against the
pull requests, or is the head branch of an open pull request; otherwise it
deletes it with `git branch -D` and writes its last commit to the log of
removals. Before either flag removes anything, it asks origin for its refs
with `git ls-remote origin`, and when no ref of origin, a pull request's
refs/pull/<number>/head included, holds the branch's last commit, it pushes
the branch to origin with a plain push, so that GitHub keeps every commit the
deletion drops; when origin cannot be asked or the push fails, it keeps the branch, and the worktree that has it checked out, or that
an earlier run stopped partway through removing. A worktree or branch kept for
an open pull request is not a failure. Any other keep, and any failure, ends the run with a line opening
`FAILED: ` and exit 1.

THE COUNT LINE. The report and --remove end their worktree lines with one
line of counts: worktrees kept, by reason; worktrees with no owner file;
local branches other than main with no pull request; and work-snapshots
still present. A second line names the kept worktrees owned by an agent-seat
whose handoff-supervisor is not running, when there are any, and a third the
worktrees CLAUDE CODE'S LOCK keeps for the user to keep or delete.

Separately from the worktrees themselves, the report ends with one line
naming dead registrations — the ones `git worktree prune` would remove,
typically because the worktree's directory is gone, which is what a
temp-area clearing leaves behind — each with git's own reason, and the
prune command. The line prints in every mode and is report only: the prune
stays a deliberate human act (ruled 2026-08-18; R25 in
docs/nedschorus-wiki/nedschorus-fleet-git-worktree-working-model.md).

Separately again, it handles work-snapshots, the copies of uncommitted work
that scripts/uncommitted-work-snapshot-hook.py keeps under
refs/work-snapshots/ (nc-systems/handoff/uncommitted-work-snapshots.py). A
work-snapshot whose owner `claude` process is gone is reported with its age
and whether the handoff-supervisor has listed it in a first prompt, which it
does only when the worktree is gone or no longer holds its changes; --remove
deletes one first listed more than ten days ago and still not in its worktree,
naming its files, and one that a newer leftover work-snapshot of the same
worktree duplicates: the same parent commit and the same tree, by git object
id. --only-done prints only the ones --remove would delete.
A live owner's work-snapshot is never touched.

Last, it closes the tasks that `uncommitted-work-snapshots.py restore` opens,
in every task list on the machine, ~/.claude/tasks/nedschorus-*-tasks, or under
the directory CLEAN_WORKTREES_TASK_LISTS_DIRECTORY_OVERRIDE names, which is how
the tests keep out of the machine's task lists. Each
task not marked completed whose subject starts with
RESTORED_BRANCH_TASK_SUBJECT_PREFIX is judged by the commit its description's
`Restore commit: ` line names: --remove first runs `git fetch --prune
origin`, then marks the task completed, adding a line at the end of its
description saying why and when, when that commit is reachable from
origin/main, or when `git for-each-ref --contains` names no ref holding it.
Any other such task stays open. The report modes name each task --remove
would mark and change none; they do not fetch, and judge the refs as last
fetched, so a stale origin only keeps more open. When the fetch fails or runs
past RESTORED_BRANCH_TASKS_CLOSE_GIT_FETCH_TIMEOUT_SECONDS, a task list or a
task file cannot be read, a task file cannot be rewritten, a task has no
`Restore commit: ` line, or git cannot judge its commit, the task is left as
it was and a line opening `FAILED: ` says so.

Modes:
  (default)    report every worktree, one line each, then the count lines
  --only-done  print only what needs someone's attention — done worktrees,
               the orphaned-branch-ref line, and the dead-registration line
               when there are any; nothing otherwise (the launchers run this
               at boot, so a reapable worktree, an orphaned branch ref or a
               dead registration is named at the moment someone is looking)
  --remove     check each worktree and, when it is done, remove it at once,
               with `git worktree remove --force`, which removes untracked
               and modified files and still refuses a locked worktree, then
               delete the branches the BRANCHES paragraph names. A refusal
               there is a failure rather than a silence.
  --remove-worktree-and-force-delete-its-branch PATH,
  --force-delete-branch NAME
               remove the one worktree, or delete the one branch, named, as
               ONE NAMED WORKTREE OR BRANCH says

THE LOG OF REMOVALS. --remove appends one line for each worktree it removes
and each branch it deletes to its machine's file in the log-store, whichever
program ran it, so a removal can be traced afterwards without the caller's
output:

  nedlern@ned-box:/home/nedlern/nedschorus-logs/clean-worktrees-removed-worktrees-and-deleted-branches-log/<machine>.txt

<machine> is `ned-box` or `mac`. Each line is tab-separated: the UTC time,
the machine, `removed-worktree` or `deleted-branch`, then key=value fields:
for a worktree its path, its branch (`none` when detached), its head commit
and the number of uncommitted, untracked or ignored files discarded with
it; for a branch its name and the commit it pointed at; and for both the
repository given with --repo, and the parent process that ran this one, its
pid and command line, which tells the handoff-supervisor, cron and a shell
apart. A commit git could not read is written as `unknown`. On ned-box the
line is appended locally, on the Mac over ssh, with run_on_ned_box_or_here
from nc-systems/handoff/handoff-user-review-of-agent-memory-stores-mark.py.
When a line cannot be written, the run prints a line containing FAILED
with the cause, then the command that writes the unwritten line once the
cause is fixed, then what to do if that command fails; it carries on
removing, and exits 1 at the end. When the handoff-supervisor runs --remove
at a session-handoff, its report keeps all three lines. The environment variable
CLEAN_WORKTREES_REMOVED_WORKTREES_AND_DELETED_BRANCHES_LOG_FILE_OVERRIDE names
a local file to append to instead, which is how the tests keep out of the
log-store.

SCHEDULED. --remove runs once a day on both machines, from the reference
clone, and at every session-handoff. The job is declared in
nc-systems/general-tools/scheduled-jobs-on-each-machine.json and installed
with nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py: on
the Mac a launchd job at 06:30, so a run missed while the Mac sleeps starts at
the next wake; on ned-box the cron line

    30 6 * * * /usr/bin/python3 /home/nedlern/Projects/nedschorus/scripts/clean-worktrees.py --remove >> /home/nedlern/.claude/clean-worktrees.log 2>&1

It does not fetch, apart from the fetch before it judges the restored branches'
tasks; a stale origin/main only keeps more.

Usage:
  scripts/clean-worktrees.py [--only-done | --remove] [--repo PATH]
  scripts/clean-worktrees.py --remove-worktree-and-force-delete-its-branch PATH [--repo PATH]
  scripts/clean-worktrees.py --force-delete-branch NAME [--repo PATH]

Exit codes: 0 ok, 1 a removal, a record's shipment, a branch or work-snapshot
made before a removal, an owner file written or an unlock before a judgment,
a ref deletion, a line of the log of removals, a work-snapshot listing or
deletion, or the fetch, reading, judging or rewriting of a restored branch's
task failed, or the one named worktree or
branch was kept for a reason other than an open pull request, 2 bad
invocation, or git could not list the worktrees or the branches, which stops
the run where it failed; with --remove-worktree-and-force-delete-its-branch
or --force-delete-branch that is exit 1 with a FAILED line.
"""

import contextlib
import fnmatch
import hashlib
import importlib.util
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_work_snapshots_spec = importlib.util.spec_from_file_location(
    "uncommitted_work_snapshots",
    REPO_ROOT / "nc-systems" / "handoff" / "uncommitted-work-snapshots.py")
work_snapshots = importlib.util.module_from_spec(_work_snapshots_spec)
_work_snapshots_spec.loader.exec_module(work_snapshots)

_git_output_spec = importlib.util.spec_from_file_location(
    "git_machine_readable_output_runner_and_parser_common",
    REPO_ROOT / "nc-systems" / "general-tools"
    / "git-machine-readable-output-runner-and-parser-common.py")
git_output = importlib.util.module_from_spec(_git_output_spec)
_git_output_spec.loader.exec_module(git_output)

_next_step_lines_spec = importlib.util.spec_from_file_location(
    "failed_command_tool_message_to_agent_rerun_once_then_stop_and_report_lines_common",
    REPO_ROOT / "nc-systems" / "general-tools"
    / "failed-command-tool-message-to-agent-rerun-once-then-stop-and-report-lines-common.py")
next_step_lines = importlib.util.module_from_spec(_next_step_lines_spec)
_next_step_lines_spec.loader.exec_module(next_step_lines)

_mark_spec = importlib.util.spec_from_file_location(
    "handoff_user_review_of_agent_memory_stores_mark",
    REPO_ROOT / "nc-systems" / "handoff" / "handoff-user-review-of-agent-memory-stores-mark.py")
mark = importlib.util.module_from_spec(_mark_spec)
_mark_spec.loader.exec_module(mark)

_merge_lane_common_spec = importlib.util.spec_from_file_location(
    "merge_lane_pull_request_helpers_common_options_paths_and_token",
    REPO_ROOT / "scripts" / "merge-lane-pull-request-helpers-common-options-paths-and-token.py")
merge_lane_common = importlib.util.module_from_spec(_merge_lane_common_spec)
_merge_lane_common_spec.loader.exec_module(merge_lane_common)

# After a merge, merge-lane-2's merge program removes pr<n>-head and pr<n>-merged and runs main's tests
# in pr<n>-merge-commit-on-main-worktree; between its steps no process has a working directory
# there, so the vacancy check alone could let a removal race it.
MERGE_LANE_REVIEW_CHECKOUT_KEPT_AFTER_ITS_PULL_REQUEST_FINISHED_HOURS = 24

IDLE_WORKTREE_REMOVED_AFTER_DAYS = 2

AGENT_HOME_MARKER_FILE_NAME = "agent-home-marker"

# One hyphen-separated part of a merge-lane review checkout's name: pr2700, 2700, 2700r2, 2420m.
MERGE_LANE_REVIEW_CHECKOUT_NAME_PULL_REQUEST_NUMBER_PART = re.compile(r"(?:pr)?(\d+)(?:r\d*)?[a-z]?")

REMOVED_WORKTREES_AND_DELETED_BRANCHES_LOG_DIRECTORY = (
    "/home/nedlern/nedschorus-logs/clean-worktrees-removed-worktrees-and-deleted-branches-log")
REMOVED_WORKTREES_AND_DELETED_BRANCHES_LOG_FILE_OVERRIDE_VARIABLE = (
    "CLEAN_WORKTREES_REMOVED_WORKTREES_AND_DELETED_BRANCHES_LOG_FILE_OVERRIDE")
REMOVED_WORKTREES_AND_DELETED_BRANCHES_LOG_WRITE_TIMEOUT_SECONDS = 30
# nc-systems/handoff/handoff-supervisor.py keeps the lines holding these in its handoff report.
LOG_OF_REMOVALS_RECORD_BY_HAND_PHRASE = ": to record it, run this once: "
LOG_OF_REMOVALS_RECORD_BY_HAND_FAILED_PHRASE = (
    ": if that printf command fails too, do not run scripts/clean-worktrees.py again; ")
# printf's own escape, so the command it starts stays on one line.
PRINTF_EACH_ARGUMENT_ON_ITS_OWN_LINE = r"%s\n"

# The reference clone's walk shipper, given the path of one walk's file, ships that walk; loaded
# as a module by walk_files_ship_module only so that which files make a walk is decided by its own rules.
WALK_FILES_SHIPPER = REPO_ROOT / "nc-systems" / "skills" / "walk-me-through" / "walk-files-ship.py"
WALK_MINUTES_SUFFIX = "-minutes.md"
_walk_files_ship = None


def walk_files_ship_module():
    """The walk shipper as a module, loaded on first use: only a worktree that holds docs/walk/
    needs it, and a test's copy of this program may run without the shipper beside it."""
    global _walk_files_ship
    if _walk_files_ship is None:
        spec = importlib.util.spec_from_file_location("walk_files_ship", WALK_FILES_SHIPPER)
        _walk_files_ship = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_walk_files_ship)
    return _walk_files_ship

# Regenerable junk is left out of the list of files a removal discards.
DISPOSABLE_JUNK_BASENAMES = (".DS_Store", "__pycache__")

DISCARDED_FILES_NAMED_AT_MOST = 10

# Never deleted, whatever it holds.
MAIN_BRANCH = "main"

# One listing of every pull request serves the whole invocation; gh pages through them all.
PULL_REQUEST_LISTING_TIMEOUT_SECONDS = 300
PULL_REQUEST_LISTING_LIMIT = 100000
PULL_REQUEST_HEAD_REFS_LISTING_TIMEOUT_SECONDS = 120
PULL_REQUEST_HEAD_REF = re.compile(r"refs/pull/(\d+)/head")
FINISHED_PULL_REQUEST_STATES = ("MERGED", "CLOSED")
FORCE_DELETABLE_BRANCH_LINE_START = (
    "branch ref(s) with no worktree, at the head of a merged or closed pull request, for "
    "git branch -D: ")

# Its reader of the open tasks' `branches` fields decides which branches a task holds.
FIRST_PROMPT_LIST = (REPO_ROOT / "nc-systems" / "handoff"
                     / "agent-seat-worktrees-and-branches-with-no-pull-request-first-prompt-list.py")
_first_prompt_list = None

# No next-step line may contain FAILED: the handoff-supervisor counts each such line as a failure.
WORKTREE_KEPT_AFTER_FAILURE_NEXT_REMOVE_RUN_RETRIES_LINE_TEMPLATE = (
    "{name}: do nothing now: the worktree and everything in it are kept, and the next "
    "scripts/clean-worktrees.py --remove, daily or at a handoff, tries again; if it fails the same "
    "way there, fix the cause the line above names")

DETACHED_COMMITS_BRANCH_NAME_TEMPLATE = "worktree-cleaner-detached-commits-{worktree_name}-{commit:.12}"

_owner_file_spec = importlib.util.spec_from_file_location(
    "worktree_owner_file_read_and_write", REPO_ROOT / "scripts" / "worktree-owner-file-read-and-write.py")
owner_file = importlib.util.module_from_spec(_owner_file_spec)
_owner_file_spec.loader.exec_module(owner_file)

# Gitignored directories whose records belong in the log-store, each with the program that ships one
# record of that kind. The reference clone's shippers, not the worktree's possibly older copies.
LOG_STORE_RECORD_SHIPPERS = (
    ("cold-read-records", REPO_ROOT / "nc-systems" / "cold-read" / "cold-read-record-ship.py"),
    ("sanity-check-records", REPO_ROOT / "scripts" / "sanity-check-record-ship.py"),
)

# Each file git keeps in a worktree's git directory while an operation is stopped partway, with the operation.
IN_PROGRESS_GIT_OPERATION_FILES = (
    ("rebase-merge", "a rebase"),
    ("rebase-apply", "a rebase or git am"),
    ("MERGE_HEAD", "a merge"),
    ("CHERRY_PICK_HEAD", "a cherry-pick"),
    ("REVERT_HEAD", "a revert"),
)

# lsof scans all processes and can be slow under load; a timeout must keep worktrees.
VACANCY_CHECK_TIMEOUT_SECONDS = 120


def run_git(repo, *arguments):
    return subprocess.run(
        ["git", "-C", str(repo), *arguments],
        capture_output=True, text=True, check=False,
    )


FINISHED_WITH_FAILURES_LINE = "clean-worktrees: finished; each failure is named above"
STOPPED_LINE_START = "clean-worktrees: stopped, because "
# Only the listing calls raise, so every removal before the stop has already printed its line on stdout.
WHAT_A_STOPPED_INVOCATION_REMOVED_WITH_REMOVE = (
    "clean-worktrees removed only the worktrees and branches named on its lines containing "
    "\": removed\" or \": deleted\", and checked nothing after the git command that failed.")
WHAT_A_STOPPED_INVOCATION_REMOVED_WITHOUT_REMOVE = (
    "clean-worktrees removed nothing, since it ran without --remove, and checked nothing after "
    "the git command that failed.")

def main_checkout_of(repo):
    """Return the primary checkout from the common git directory."""
    common = run_git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if common.returncode != 0:
        return None
    return Path(common.stdout.strip()).parent


def local_branch_name_of_full_ref(ref):
    """Return the branch name of a full `refs/heads/<name>` ref, or None for any other ref or None."""
    # Never git's --short form: it gives heads/<name> when a tag has the same name as the branch.
    if ref is not None and ref.startswith("refs/heads/"):
        return ref[len("refs/heads/"):]
    return None


def checked_out_branch_name(worktree):
    """Return the branch the worktree's HEAD names, or None when HEAD is detached."""
    read = run_git(worktree, "symbolic-ref", "--quiet", "HEAD")
    return local_branch_name_of_full_ref(read.stdout.strip()) if read.returncode == 0 else None


def list_worktrees(repo, main_checkout):
    """Return (path, branch-or-None, git's record) for each worktree but the primary checkout;
    raise git_output.GitCommandFailed when git cannot list them."""
    listing = git_output.run_git(repo, ["worktree", "list", "--porcelain", "-z"])
    worktrees = []
    for record in git_output.worktree_records(listing):
        path = Path(record.path)
        if path.resolve() == main_checkout.resolve():
            continue
        worktrees.append((path, local_branch_name_of_full_ref(record.branch), record))
    return worktrees


def dead_worktree_registrations(repo):
    """Return (path, git reason) for unlocked prunable registrations no removal record names;
    raise git_output.GitCommandFailed when git cannot list them."""
    recorded = {Path(record["worktree"]).resolve() for record in unfinished_worktree_removal_records(repo)[0]}
    # A prunable directory can still exist and hold work; report git's reason without inferring absence.
    listing = git_output.run_git(repo, ["worktree", "list", "--porcelain", "-z"])
    return [(record.path, record.prunable_reason or "no reason given")
            for record in git_output.worktree_records(listing)
            if record.prunable_reason is not None
            and Path(record.path).resolve() not in recorded]


UNFINISHED_WORKTREE_REMOVAL_RECORDS_DIRECTORY_NAME = "clean-worktrees-unfinished-worktree-removal-records"


def unfinished_worktree_removal_records_directory(repo):
    """Return the directory of unfinished-worktree removal records in the clone's git directory; raise
    git_output.GitCommandFailed when git cannot name it."""
    common = os.fsdecode(git_output.run_git(
        repo, ["rev-parse", "--path-format=absolute", "--git-common-dir"])).strip()
    return Path(common) / UNFINISHED_WORKTREE_REMOVAL_RECORDS_DIRECTORY_NAME


def unfinished_worktree_removal_record_file(repo, worktree):
    name = hashlib.sha256(os.fsencode(str(Path(worktree).resolve()))).hexdigest()[:16]
    return unfinished_worktree_removal_records_directory(repo) / f"{name}.json"


def unfinished_worktree_removal_records(repo):
    """Return (records, unreadable): each readable removal record as a dict with its "file",
    and (file, error text) for each that cannot be read; raise git_output.GitCommandFailed
    when git cannot name the directory."""
    records, unreadable = [], []
    directory = unfinished_worktree_removal_records_directory(repo)
    if not directory.is_dir():
        return records, unreadable
    for record_file in sorted(directory.glob("*.json")):
        try:
            record = json.loads(record_file.read_text(encoding="utf-8"))
            record["worktree"], record["registration"]
        except (OSError, ValueError, KeyError, TypeError) as error:
            unreadable.append((record_file, f"{type(error).__name__}: {error}"))
            continue
        record["file"] = record_file
        records.append(record)
    return records, unreadable


def removal_never_began(record, listed):
    """Whether the worktree a record names still has its .git file and a registration git
    would not prune, as `git worktree list` showed it in listed."""
    worktree = Path(record["worktree"])
    entry = listed.get(worktree.resolve())
    return entry is not None and entry.prunable_reason is None and (worktree / ".git").exists()


def branch_refs_with_no_worktree_fully_on_main(repo):
    """Return the local branches no worktree holds that carry nothing beyond origin/main;
    raise git_output.GitCommandFailed when git cannot list either."""
    listing = git_output.run_git(repo, ["worktree", "list", "--porcelain", "-z"])
    attached = {local_branch_name_of_full_ref(record.branch)
                for record in git_output.worktree_records(listing)}
    # Use lstrip=2: :short can return heads/<name> when a same-named tag shadows a branch.
    landed = git_output.run_git(repo, ["for-each-ref", "--format=%(refname:lstrip=2)",
                                       "--merged", "origin/main", "refs/heads/"])
    return [branch for branch in os.fsdecode(landed).splitlines()
            if branch not in attached and branch != MAIN_BRANCH]


def commit_of(repo, revision):
    """Return the commit a revision names, or "unknown" when git cannot read it."""
    resolved = run_git(repo, "rev-parse", "--verify", "--quiet", f"{revision}^{{commit}}")
    return resolved.stdout.strip() if resolved.returncode == 0 else "unknown"


def parent_process_id_and_command_line():
    """Return the parent process's pid and command line: they tell which caller ran this run."""
    parent = os.getppid()
    try:
        command = subprocess.run(["ps", "-o", "args=", "-p", str(parent)], capture_output=True,
                                 text=True, check=False, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        command = ""
    return f"{parent} {' '.join(command.split()) or 'unknown'}"


def append_removed_worktree_or_deleted_branch_log_lines(events, repo, name):
    """Append one line per (event, fields) to this machine's log of removals, in one write; print
    why and return False when it fails."""
    on_ned_box = mark.this_machine_is_ned_box()
    machine = "ned-box" if on_ned_box else "mac"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_by = parent_process_id_and_command_line()
    text = "".join(
        "\t".join([now, machine, event,
                   *(f"{key}={' '.join(str(value).split())}"
                     for key, value in {**fields, "repo": repo, "run-by": run_by}.items())]) + "\n"
        for event, fields in events)
    override = os.environ.get(REMOVED_WORKTREES_AND_DELETED_BRANCHES_LOG_FILE_OVERRIDE_VARIABLE)
    if override:
        log_file, ssh_target = override, None
    else:
        log_file = f"{REMOVED_WORKTREES_AND_DELETED_BRANCHES_LOG_DIRECTORY}/{machine}.txt"
        ssh_target = None if on_ned_box else mark.NED_BOX_SSH_TARGET
    command = (f"mkdir -p {shlex.quote(os.path.dirname(log_file) or '.')} && "
               f"cat >> {shlex.quote(log_file)}")
    try:
        mark.run_on_ned_box_or_here(command, ssh_target,
                                    REMOVED_WORKTREES_AND_DELETED_BRANCHES_LOG_WRITE_TIMEOUT_SECONDS,
                                    stdin_text=text)
    except mark.DailyMemoryReviewReadOrWriteFailed as error:
        # No line may contain ": removed", ": deleted" or ": removal FAILED": the handoff-supervisor counts those.
        place = f"{mark.NED_BOX_SSH_TARGET if ssh_target else machine}:{log_file}"
        writer = ([*mark.NED_BOX_SSH_COMMAND, ssh_target, command] if ssh_target
                  else ["/bin/sh", "-c", command])
        # The handoff-supervisor keeps the two lines after a FAILED line by these phrases.
        print(f"{name}: log of removals line(s) FAILED to be written to {place} — {error}. "
              f"The removal or branch deletion named above stands, but no file outside this "
              f"run's output records it.\n"
              f"{name}{LOG_OF_REMOVALS_RECORD_BY_HAND_PHRASE}"
              f"{shlex.join(['printf', PRINTF_EACH_ARGUMENT_ON_ITS_OWN_LINE, *text.splitlines()])} | "
              f"{shlex.join(writer)}\n"
              f"{name}{LOG_OF_REMOVALS_RECORD_BY_HAND_FAILED_PHRASE}"
              f"tell the user that scripts/clean-worktrees.py on {machine} could not write "
              f"its log of removals at {place}, quoting both the error above and the one the printf "
              f"command printed; a subagent tells the agent that dispatched it instead.")
        return False
    return True


def delete_orphaned_branch_ref(branch, repo):
    """Delete a ref and log it; return whether git deleted it and its log line was written."""
    commit = commit_of(repo, f"refs/heads/{branch}")
    # Keep -d: git's merged-branch check is independent of our containment test.
    deletion = run_git(repo, "branch", "-d", branch)
    if deletion.returncode != 0:
        print(f"branch {branch}: deletion FAILED — {deletion.stderr.strip()[:120]}")
        return False
    print(f"branch {branch}: deleted (no worktree, nothing beyond origin/main)")
    return append_removed_worktree_or_deleted_branch_log_lines(
        [("deleted-branch", {"branch": branch, "commit": commit})], repo, f"branch {branch}")


def branch_refs_and_tips_with_no_worktree_not_fully_on_main(repo, freed_branches=frozenset()):
    """Return (branch, tip commit) for each local branch other than main that no worktree holds,
    or that only a worktree in freed_branches' removal holds, and that carries a commit origin/main
    lacks; raise git_output.GitCommandFailed when git cannot list either."""
    listing = git_output.run_git(repo, ["worktree", "list", "--porcelain", "-z"])
    attached = {local_branch_name_of_full_ref(record.branch)
                for record in git_output.worktree_records(listing)} - set(freed_branches)
    unlanded = git_output.run_git(repo, ["for-each-ref", "--format=%(objectname) %(refname:lstrip=2)",
                                         "--no-merged", "origin/main", "refs/heads/"])
    refs = [line.split(" ", 1) for line in os.fsdecode(unlanded).splitlines()]
    return [(branch, tip) for tip, branch in refs if branch not in attached and branch != MAIN_BRANCH]


def first_prompt_list_module():
    """The first prompt's list as a module, loaded on first use, for its reader of the task-held
    branches; only a run with a branch to judge for `git branch -D` needs it."""
    global _first_prompt_list
    if _first_prompt_list is None:
        spec = importlib.util.spec_from_file_location(
            "agent_seat_worktrees_and_branches_with_no_pull_request_first_prompt_list", FIRST_PROMPT_LIST)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _first_prompt_list = module
    return _first_prompt_list


def open_task_held_branches_or_unreadable_text(task_lists_directory):
    """Return (the names the open tasks of every agent-seat task list name in their `branches`
    field, None), or (None, why a task list could not be read in full)."""
    try:
        list_directories = nedschorus_task_list_directories(task_lists_directory)
    except OSError as error:
        return None, (f"the task lists' directory {task_lists_directory} cannot be listed "
                      f"({type(error).__name__}: {error})")
    held = set()
    for list_directory in list_directories:
        holding = first_prompt_list_module().tasks_holding(None, list_directory)
        if holding.unreadable:
            return None, (f"the task list {list_directory} could not be read in full: "
                          f"{', '.join(holding.unreadable)}")
        held.update(holding.held)
    return held, None


def pull_request_head_commits_or_failure(repo):
    """Return ({pull request number: the commit its refs/pull/<number>/head names}, None), as
    origin reports now, or (None, why origin could not be asked)."""
    arguments = ["ls-remote", "origin", "refs/pull/*/head"]
    try:
        listing = subprocess.run(["git", "-C", str(repo), *arguments], capture_output=True,
                                 text=True, check=False,
                                 timeout=PULL_REQUEST_HEAD_REFS_LISTING_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as error:
        return None, f"`git {shlex.join(arguments)}` did not finish: {error}"
    if listing.returncode != 0:
        return None, (f"`git {shlex.join(arguments)}` exited {listing.returncode}: "
                      f"{' '.join(listing.stderr.split())[:200] or 'no error text'}")
    heads = {}
    for line in listing.stdout.splitlines():
        commit, _, ref = line.partition("\t")
        number = PULL_REQUEST_HEAD_REF.fullmatch(ref)
        if number:
            heads[int(number.group(1))] = commit
    return heads, None


def finished_pull_request_head_branches_to_force_delete(repo, pull_requests, freed_branches=frozenset()):
    """Return ([(branch, tip, pull request)] for each branch BRANCHES deletes with `git branch -D`,
    None, None), or ([], why GitHub could not tell which, None), or ([], None, why the task lists
    could not); a branch in freed_branches counts as checked out in no worktree. Raise
    git_output.GitCommandFailed when git cannot list the branches."""
    candidates = branch_refs_and_tips_with_no_worktree_not_fully_on_main(repo, freed_branches)
    if not candidates:
        return [], None, None
    try:
        by_head_branch = pull_requests.by_head_branch()
    except PullRequestListingFailed as error:
        return [], f"GitHub could not be reached: {error}", None
    finished = [(branch, tip, [pull_request for pull_request in by_head_branch.get(branch, ())
                               if pull_request["state"] in FINISHED_PULL_REQUEST_STATES])
                for branch, tip in candidates]
    finished = [entry for entry in finished if entry[2]]
    if not finished:
        return [], None, None
    held, unreadable = open_task_held_branches_or_unreadable_text(
        task_lists_directory_from_override_or_home_claude_tasks())
    if unreadable:
        return [], None, unreadable
    heads, failure = pull_request_head_commits_or_failure(repo)
    if failure:
        return [], f"GitHub could not be reached: {failure}", None
    chosen = []
    for branch, tip, pull_requests_of_branch in finished:
        at_head = [pull_request for pull_request in pull_requests_of_branch
                   if heads.get(pull_request["number"]) == tip]
        if at_head and branch not in held:
            chosen.append((branch, tip, at_head[0]))
    return chosen, None, None


def force_delete_finished_pull_request_head_branch(branch, tip, pull_request, repo):
    """Delete the branch with `git branch -D` and log it; return whether git deleted it at the
    checked tip and its log line was written."""
    # git branch -D deletes by name, so another agent may have moved the branch since its tip was
    # checked; git's own "(was <sha>)" says which commit it deleted. LC_ALL=C keeps that text English.
    deletion = subprocess.run(["git", "-C", str(repo), "branch", "-D", branch],
                              capture_output=True, text=True, check=False,
                              env={**os.environ, "LC_ALL": "C"})
    if deletion.returncode != 0:
        print(f"branch {branch}: deletion FAILED — git branch -D exited {deletion.returncode}: "
              f"{deletion.stderr.strip()[:120] or 'no error text'}")
        return False
    was = re.search(r"\(was ([0-9a-f]+)\)", deletion.stdout)
    deleted = was and run_git(repo, "rev-parse", "--verify", "--quiet",
                              f"{was.group(1)}^{{commit}}").stdout.strip()
    if deleted == tip:
        print(f"branch {branch}: deleted with git branch -D, its last commit {tip} being the head of "
              f"{pull_request_text(pull_request)}")
        return append_removed_worktree_or_deleted_branch_log_lines(
            [("deleted-branch", {"branch": branch, "commit": tip})], repo, f"branch {branch}")
    # One line each, so the handoff-supervisor's summary, which keeps FAILED lines, keeps the restore command.
    restore = f"git -C {shlex.quote(str(repo))} branch {shlex.quote(branch)} {deleted or tip}"
    if not deleted:
        print(f"branch {branch}: deletion FAILED to be confirmed — git branch -D deleted it without "
              f"saying which commit it pointed at, so commits made on it after its tip {tip} was "
              f"checked may have no branch now; restore the checked tip with: {restore}, and look "
              f"for newer commits with: git -C {shlex.quote(str(repo))} fsck --lost-found")
    else:
        print(f"branch {branch}: deletion FAILED — it had moved after its check, so git branch -D "
              f"deleted its commit {deleted}, not the checked tip {tip} of "
              f"{pull_request_text(pull_request)}; restore it with: {restore}")
    append_removed_worktree_or_deleted_branch_log_lines(
        [("deleted-branch", {"branch": branch, "commit": deleted or "unknown"})], repo,
        f"branch {branch}")
    return False


def in_progress_git_operation_keep_reason(worktree):
    """Return why a worktree with a git operation stopped partway must be kept, or None."""
    arguments = ["rev-parse", "--path-format=absolute"]
    for file_name, _ in IN_PROGRESS_GIT_OPERATION_FILES:
        arguments += ["--git-path", file_name]
    located = run_git(worktree, *arguments)
    if located.returncode != 0:
        return ("git could not say where to look for the files that show a rebase, merge, "
                f"cherry-pick or revert in progress ({located.stderr.strip()[:80]})")
    for path, (file_name, operation) in zip(located.stdout.splitlines(),
                                            IN_PROGRESS_GIT_OPERATION_FILES):
        if Path(path).exists():
            return (f"{operation} is in progress in it (its git directory holds {file_name}), "
                    f"so its HEAD does not show its owner's finished work")
    return None


def worktree_vacancy_keep_reason(worktree):
    """Return why vacancy is unproven, or None for a provably vacant worktree."""
    # Even a partial listing proves occupancy when it contains a matching cwd.
    if shutil.which("lsof") is None:
        return "lsof is not installed, so vacancy cannot be checked"
    try:
        cwd_listing = subprocess.run(
            ["lsof", "-a", "-d", "cwd", "-F", "n"],
            capture_output=True, text=True, check=False,
            timeout=VACANCY_CHECK_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "the vacancy check (lsof) could not be run"
    prefix = str(worktree.resolve())
    reported_paths = 0
    for line in cwd_listing.stdout.splitlines():
        if line.startswith("n"):
            reported_paths += 1
            cwd = line[1:]
            if cwd == prefix or cwd.startswith(prefix + "/"):
                return "a live process is rooted inside it"
    # No match proves vacancy only when lsof returned a usable listing.
    if cwd_listing.returncode != 0:
        return (f"the vacancy check (lsof) failed with exit "
                f"{cwd_listing.returncode}, so vacancy cannot be trusted")
    if reported_paths == 0:
        return "the vacancy check (lsof) reported no working directories at all"
    return None


def uncommitted_or_untracked_files(worktree):
    """Return (paths, None) for every uncommitted or untracked file, junk left out, or (None, git's
    error) when git cannot list them. Ignored files are not among them."""
    # --no-optional-locks: a status that refreshed the index would reset the idle clock it is read for.
    status = run_git(worktree, "--no-optional-locks", "status", "--porcelain", "-z",
                     "--untracked-files=all")
    if status.returncode != 0:
        return None, status.stderr.strip()[:80]
    return [entry.path for entry in git_output.status_entries(status.stdout)
            if not is_disposable_junk(entry.path)], None


def is_disposable_junk(relative_path):
    return any(part in DISPOSABLE_JUNK_BASENAMES for part in Path(relative_path).parts)


def files_a_removal_discards(worktree):
    """Return (paths, None) for every uncommitted, untracked or ignored file, junk left out,
    or (None, git's error) when git cannot list them."""
    # --untracked-files=all with --ignored names each file; without it git names only a directory.
    status = run_git(worktree, "--no-optional-locks", "status", "--porcelain", "-z", "--ignored",
                     "--untracked-files=all")
    if status.returncode != 0:
        return None, status.stderr.strip()[:80]
    paths = [entry.path for entry in git_output.status_entries(status.stdout)]
    return [path for path in paths if not is_disposable_junk(path)], None


def discarded_files_text(paths):
    named = ", ".join(paths[:DISCARDED_FILES_NAMED_AT_MOST])
    more = len(paths) - DISCARDED_FILES_NAMED_AT_MOST
    return named + (f" and {more} more" if more > 0 else "")


def log_store_records_in(worktree):
    """Return (shipper, path to ship) for each walk in the worktree's docs/walk/, one for each
    <name>-minutes.md, and for each non-empty record directory it holds. A walk is given by its walk
    text <name>.md: the shipper resolves a path to the longest walk name whose walk text and minutes
    are present, so the minutes of walk foo, foo-minutes.md, would name walk foo-minutes when that
    walk is there too, while foo.md names only foo. A walk without its walk text is given by its
    minutes, which the shipper then refuses, keeping the worktree."""
    records = []
    for minutes in sorted((worktree / "docs" / "walk").glob(f"*{WALK_MINUTES_SUFFIX}")):
        walk_text = minutes.with_name(minutes.name[:-len(WALK_MINUTES_SUFFIX)] + ".md")
        records.append((WALK_FILES_SHIPPER, walk_text if walk_text.is_file() else minutes))
    for directory_name, shipper in LOG_STORE_RECORD_SHIPPERS:
        records_directory = worktree / directory_name
        if not records_directory.is_dir():
            continue
        for record in sorted(records_directory.iterdir()):
            if record.is_dir() and any(record.iterdir()):
                records.append((shipper, record))
    return records


def shipper_line(shipment):
    """The one line a shipper printed for one record or walk, or, when it printed none, as when
    it died before printing, its exit code and last stderr line."""
    line = shipment.stdout.strip()
    if not line:
        error_lines = shipment.stderr.strip().splitlines()
        line = (f"the shipper printed nothing (exit {shipment.returncode})"
                + (f": {error_lines[-1]}" if error_lines else ""))
    return line


def worktree_removal_unshippable_approval_walk_files_relative_paths(worktree):
    """Return the sorted relative paths of the files in the worktree's docs/walk/ that no walk the
    shipper can ship holds: a walk never presented, which lacks its walk text or minutes, or a file
    of no walk role."""
    directory = worktree / "docs" / "walk"
    if not directory.is_dir():
        return []
    files = sorted(path for path in directory.iterdir() if path.is_file())
    walk_files_ship = walk_files_ship_module()
    walk_names = set()
    for path in files:
        name, _ = walk_files_ship.walk_name_and_directory(str(path))
        if all((directory / walk_files_ship.walk_file_name(name, suffix)).is_file()
               for suffix in walk_files_ship.REQUIRED_ROLE_SUFFIXES):
            walk_names.add(name)
    shipped_names = {walk_files_ship.walk_file_name(name, suffix)
                     for name in walk_names for suffix, _ in walk_files_ship.APPROVAL_WALK_FILE_SUFFIX_AND_ROLE_PAIRS_SHIPPED_INCLUDING_EARLIER_WALKS_SUGGESTIONS_SUFFIX}
    return [str(path.relative_to(worktree)) for path in files if path.name not in shipped_names]


def worktree_removal_unshippable_approval_walk_files_report(worktree):
    """Print a line naming the files in the worktree's docs/walk/ that no walk ships, which the
    removal discards with its other ignored files."""
    unshippable = worktree_removal_unshippable_approval_walk_files_relative_paths(worktree)
    if unshippable:
        print(f"{worktree.name}: {len(unshippable)} file(s) in docs/walk/ no walk ships, a walk never "
              f"presented or a file of no walk role, are discarded with the worktree: "
              f"{discarded_files_text(unshippable)}")


def ship_log_store_records(worktree):
    """Ship every record the worktree holds, printing a line for each; return (shipper, line) for
    each that did not ship."""
    unshipped = []
    for shipper, record in log_store_records_in(worktree):
        shipment = subprocess.run([sys.executable, str(shipper), str(record)],
                                  capture_output=True, text=True, check=False)
        sys.stderr.write(shipment.stderr)
        # One record directory, so the shipper prints at most one line.
        line = shipper_line(shipment)
        if shipment.returncode:
            # Printed now, not after the loop: a later shipment can hang until the handoff's timeout kills this run.
            # The shipper's line appears only inside this FAILED line, so a reader counts it once.
            print(f"{worktree.name}: record shipment FAILED, worktree kept — removing it would delete "
                  f"a record the log-store does not hold: {record.relative_to(worktree)} ({line})")
            unshipped.append((shipper, line))
        else:
            print(f"{worktree.name}: {line}")
    return unshipped


class PullRequestListingFailed(Exception):
    """gh could not list the repository's pull requests."""


class PullRequestsByHeadBranchLazyCache:
    """The repository's pull requests by head branch, listed once per invocation, on first need."""

    def __init__(self, repo):
        self.repo = repo
        self._by_head_branch = None
        self._error = None

    def by_head_branch(self):
        """Return {head branch name: [pull request]}; raise PullRequestListingFailed."""
        if self._by_head_branch is None and self._error is None:
            try:
                self._by_head_branch = list_all_pull_requests_grouped_by_head_branch(self.repo)
            except PullRequestListingFailed as error:
                self._error = str(error)
        if self._error is not None:
            raise PullRequestListingFailed(self._error)
        return self._by_head_branch

    def by_number(self):
        """Return {pull request number: pull request}; raise PullRequestListingFailed."""
        return {pull_request["number"]: pull_request
                for pull_requests in self.by_head_branch().values()
                for pull_request in pull_requests}


def list_all_pull_requests_grouped_by_head_branch(repo,
                                                  timeout_seconds=PULL_REQUEST_LISTING_TIMEOUT_SECONDS):
    """Return {head branch name: [{number, state, headRefName, headRefOid, closedAt}]} for every pull request
    of the repository's GitHub remote; raise PullRequestListingFailed when gh cannot list them, or
    does not finish within timeout_seconds."""
    command = ["gh", "pr", "list", "--state", "all", "--limit", str(PULL_REQUEST_LISTING_LIMIT),
               "--json", "number,state,headRefName,headRefOid,closedAt"]
    try:
        listing = subprocess.run(command, cwd=repo, capture_output=True, text=True, check=False,
                                 timeout=timeout_seconds)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise PullRequestListingFailed(f"`{shlex.join(command)}` could not be run: {error}") from None
    if listing.returncode != 0:
        raise PullRequestListingFailed(
            f"`{shlex.join(command)}` exited {listing.returncode}: "
            f"{' '.join(listing.stderr.split())[:200] or 'no error text'}")
    try:
        by_head_branch = {}
        for pull_request in json.loads(listing.stdout):
            by_head_branch.setdefault(pull_request["headRefName"], []).append(pull_request)
    except (ValueError, TypeError, KeyError) as error:
        raise PullRequestListingFailed(
            f"`{shlex.join(command)}` printed something other than a list of pull requests: "
            f"{type(error).__name__}: {error}") from None
    return by_head_branch


# Why a worktree is kept, as the count line groups the reasons, in the order it prints them.
KEPT_LOCKED = "locked"
KEPT_NO_OWNER_FILE = "no owner file"
KEPT_OWNER_RUNNING = "owner running"
KEPT_OPEN_PULL_REQUEST = "open pull request"
KEPT_IN_USE = "in use"
KEPT_NOT_CHECKABLE = "could not be checked"
KEPT_REASONS_IN_ORDER = (KEPT_LOCKED, KEPT_NO_OWNER_FILE, KEPT_OWNER_RUNNING,
                         KEPT_OPEN_PULL_REQUEST, KEPT_IN_USE, KEPT_NOT_CHECKABLE)


@dataclass
class Verdict:
    done: bool
    reason: str
    kept_for: str = ""
    owner: dict | None = None
    owner_state: str = ""
    uncommitted: list = field(default_factory=list)
    discarded: list = field(default_factory=list)
    # The detached HEAD whose commits origin/main lacks, which --remove first puts on a branch.
    detached_commit: str | None = None
    # The HEAD and branch a running owner's finished pull request was matched against; --remove
    # keeps the worktree when either has changed since.
    judged_head: str | None = None
    judged_branch: str | None = None
    # When the idle rule judged the worktree, in seconds since the epoch; --remove keeps the
    # worktree when anything in it changed since, or its HEAD did.
    idle_judged_at: float | None = None
    # Kept locked by Claude Code's lock of an ended agent-session that no agent-seat's
    # transcripts name: the count lines name it for the user.
    for_the_user_to_keep_or_delete: bool = False


def owner_text(owner):
    if owner["owner_kind"] == owner_file.OWNER_AGENT_SEAT:
        return f"the agent-seat {owner['agent_seat']}"
    return f"an agent-session of {owner['agent_seat']} (claude process {owner['owner_key']})"


def pull_request_text(pull_request):
    return f"pull request #{pull_request['number']} ({pull_request['state'].lower()})"


@dataclass
class EndedClaudeCodeSubagentLock:
    """Claude Code's lock on a worktree, naming a `claude` process that has ended, which
    --remove unlocks, first writing owner_to_write as the worktree's owner file when it is set."""
    lock: object
    explanation: str
    owner_to_write: dict | None


def claude_code_subagent_lock_verdict_or_ended_lock(worktree, record):
    """For a locked worktree, return (the Verdict that keeps it, None), or (None, the
    EndedClaudeCodeSubagentLock that --remove unlocks), as CLAUDE CODE'S LOCK says."""
    lock = owner_file.claude_code_subagent_worktree_lock_reason_parse(record.locked_reason)
    locked = f"locked with git worktree lock ({record.locked_reason or 'no reason given'})"
    if lock is None:
        return Verdict(False, locked, KEPT_LOCKED), None
    state, explanation = owner_file.claude_code_subagent_worktree_lock_dispatching_process_running_state(lock)
    if state != owner_file.STOPPED:
        return Verdict(False, f"{locked}: {explanation}", KEPT_LOCKED), None
    try:
        owner = owner_file.worktree_owner_file_read(worktree)
    except owner_file.WorktreeOwnerFileError as error:
        return Verdict(False, f"{locked}, whose claude process has ended, and its owner file "
                              f"could not be read: {error}", KEPT_NOT_CHECKABLE), None
    if owner is not None:
        return None, EndedClaudeCodeSubagentLock(lock, explanation, None)
    try:
        seats = owner_file.agent_seats_whose_claude_code_transcripts_name_subagent(lock.agent_id)
        owner_key = owner_file.claude_code_subagent_worktree_lock_ended_agent_session_owner_key(lock)
    except Exception as error:
        return Verdict(False, f"{locked}, whose claude process has ended, and the agent-seat whose "
                              f"Claude Code transcripts name subagent agent-{lock.agent_id} could "
                              f"not be read: {type(error).__name__}: {error}",
                       KEPT_NOT_CHECKABLE), None
    if len(seats) != 1:
        whose = ("no agent-seat's Claude Code transcripts name" if not seats
                 else f"the Claude Code transcripts of {len(seats)} agent-seats, "
                      f"{', '.join(seats)}, name")
        return Verdict(False, f"{locked}, whose claude process has ended, it has no owner file, "
                              f"and {whose} subagent agent-{lock.agent_id}, so no agent-seat "
                              f"owns it; the user keeps or deletes it", KEPT_LOCKED,
                       for_the_user_to_keep_or_delete=True), None
    return None, EndedClaudeCodeSubagentLock(lock, explanation, {
        "owner_kind": owner_file.OWNER_AGENT_SESSION, "agent_seat": seats[0],
        "owner_key": owner_key})


def ended_claude_code_subagent_lock_unlock(worktree, repo, ended):
    """Write the owner file ended names, then unlock the worktree; print and return False when
    either fails, leaving the worktree locked or unlocked as git left it."""
    if ended.owner_to_write is not None:
        try:
            owner_file.worktree_owner_file_write(
                worktree, ended.owner_to_write["owner_kind"], ended.owner_to_write["agent_seat"],
                ended.owner_to_write["owner_key"])
        except owner_file.WorktreeOwnerFileError as error:
            print(f"{worktree.name}: owner file FAILED, worktree kept locked — {error}")
            print(WORKTREE_KEPT_AFTER_FAILURE_NEXT_REMOVE_RUN_RETRIES_LINE_TEMPLATE.format(
                name=worktree.name))
            return False
        print(f"{worktree.name}: owner file written, naming {owner_text(ended.owner_to_write)}, "
              f"whose subagent agent-{ended.lock.agent_id} its Claude Code transcripts name")
    unlocked = run_git(repo, "worktree", "unlock", str(worktree))
    if unlocked.returncode != 0:
        print(f"{worktree.name}: unlock FAILED, worktree kept — git worktree unlock exited "
              f"{unlocked.returncode}: {unlocked.stderr.strip()[:160] or 'no error text'}")
        print(WORKTREE_KEPT_AFTER_FAILURE_NEXT_REMOVE_RUN_RETRIES_LINE_TEMPLATE.format(
            name=worktree.name))
        return False
    print(f"{worktree.name}: unlocked, since {ended.explanation}")
    return True


def classify(worktree, branch, record, pull_requests):
    """Return the Verdict for a worktree: whether its work is done, and why."""
    ended_lock = None
    if record.locked_reason is not None:
        verdict, ended_lock = claude_code_subagent_lock_verdict_or_ended_lock(worktree, record)
        if verdict is not None:
            return verdict
    verdict = classify_unlocked(worktree, branch, record, pull_requests,
                                None if ended_lock is None else ended_lock.owner_to_write)
    if ended_lock is not None:
        writes = ("" if ended_lock.owner_to_write is None
                  else f", writing first its owner file naming "
                       f"{owner_text(ended_lock.owner_to_write)}")
        verdict.reason = (f"{ended_lock.explanation}, so --remove unlocks it{writes}, then judges "
                          f"it: {verdict.reason}")
    return verdict


def is_agent_home(worktree, git_directory):
    """Whether the worktree is an agent-home: ~/agents/<seat>, or marked by AGENT_HOME_MARKER_FILE_NAME
    in its own git directory."""
    # Most agent-homes predate the marker, so the location counts too.
    return (worktree.resolve().parent == (Path.home() / "agents").resolve()
            or (git_directory / AGENT_HOME_MARKER_FILE_NAME).exists())


def path_changed_since(roots, cutoff):
    """Return the first file or directory under roots, the roots included, whose mtime is at or after
    cutoff (seconds since the epoch), or None when none is; raise OSError when one cannot be read."""
    def raise_error(error):
        raise error
    for root in roots:
        if os.lstat(root).st_mtime >= cutoff:
            return root
        for directory, directory_names, file_names in os.walk(root, onerror=raise_error):
            for name in directory_names + file_names:
                path = os.path.join(directory, name)
                if os.lstat(path).st_mtime >= cutoff:
                    return Path(path)
    return None


def idle_worktree_verdict(worktree, branch, record, pull_requests):
    """Return the Verdict for a worktree that holds no unsaved work and in which nothing has changed
    for IDLE_WORKTREE_REMOVED_AFTER_DAYS, owner file or not; or None when the rule does not apply, so
    that the other rules judge it."""
    try:
        git_directory = Path(os.fsdecode(
            git_output.run_git(worktree, ["rev-parse", "--absolute-git-dir"])).strip())
    except git_output.GitCommandFailed:
        return None
    if is_agent_home(worktree, git_directory):
        return None
    # Taken before the checks below, so that a file written while they run counts as changed.
    judged_at = time.time()
    cutoff = judged_at - IDLE_WORKTREE_REMOVED_AFTER_DAYS * 86400
    try:
        if path_changed_since([worktree, git_directory], cutoff) is not None:
            return None
    except OSError:
        return None
    # The re-check before removal compares HEAD with this commit, the one rev-list checks: a HEAD
    # read later, after the checks below, could be a commit made meanwhile that GitHub lacks.
    # An unreadable HEAD reads as "unknown", which rev-list then fails on.
    judged_head = commit_of(worktree, "HEAD")
    try:
        if git_output.run_git(worktree, ["rev-list", judged_head, "--not", "--remotes=origin"]).strip():
            return None
    except git_output.GitCommandFailed:
        return None
    uncommitted, _ = uncommitted_or_untracked_files(worktree)
    if uncommitted is None or uncommitted:
        return None
    try:
        by_head_branch = pull_requests.by_head_branch()
    except PullRequestListingFailed:
        return None
    if any(pull_request["state"] == "OPEN"
           and (pull_request["headRefName"] == branch or pull_request["headRefOid"] == record.head)
           for pull_requests_of_branch in by_head_branch.values()
           for pull_request in pull_requests_of_branch):
        return None
    if in_progress_git_operation_keep_reason(worktree) is not None:
        return None
    why = (f"nothing in it, its git directory included, has changed for "
           f"{IDLE_WORKTREE_REMOVED_AFTER_DAYS} days, it holds no uncommitted or untracked file, "
           f"GitHub holds every commit of its HEAD, and no open pull request is its")
    keep_reason = worktree_vacancy_keep_reason(worktree)
    if keep_reason is not None:
        return Verdict(False, f"{why}, but {keep_reason}", KEPT_IN_USE)
    discarded, listing_error = files_a_removal_discards(worktree)
    if discarded is None:
        return Verdict(False, f"{why}, but git cannot list its files ({listing_error})",
                       KEPT_NOT_CHECKABLE)
    return Verdict(True, why + removal_records_and_discarded_files_text(worktree, discarded),
                   "", discarded=discarded, judged_head=judged_head,
                   idle_judged_at=judged_at)


def idle_worktree_removal_keep_reason(worktree, verdict):
    """Return why a worktree the idle rule judged done must be kept after all, because it changed
    after the idle rule judged it, or None when it may still go."""
    uncommitted, listing_error = uncommitted_or_untracked_files(worktree)
    if uncommitted is None:
        return f"git cannot list its uncommitted changes ({listing_error})"
    if uncommitted:
        return (f"it now holds {len(uncommitted)} uncommitted or untracked file(s): "
                f"{discarded_files_text(uncommitted)}")
    head_now = commit_of(worktree, "HEAD")
    if head_now != verdict.judged_head:
        return f"its HEAD changed during this run, from {verdict.judged_head} to {head_now}"
    # Only the worktree itself: git's own reads during this run may rewrite files in its git directory.
    try:
        changed = path_changed_since([worktree], verdict.idle_judged_at)
    except OSError as error:
        return f"a file in it cannot be read ({error})"
    if changed is not None:
        return f"{changed} changed during this run"
    return None


def classify_unlocked(worktree, branch, record, pull_requests, owner_to_write=None):
    """Return the Verdict for an unlocked worktree, or one --remove will have unlocked and given
    owner_to_write as its owner file."""
    if record.prunable_reason is not None:
        return Verdict(False, f"git would prune its registration ({record.prunable_reason}); "
                              f"the dead registration line below names it", KEPT_NOT_CHECKABLE)
    # An ended lock's owner file is written only by --remove, so the report judges the worktree
    # as --remove will find it after the write: changed today, so not idle.
    if owner_to_write is None:
        verdict = idle_worktree_verdict(worktree, branch, record, pull_requests)
        if verdict is not None:
            return verdict
    try:
        owner = owner_to_write or owner_file.worktree_owner_file_read(worktree)
    except owner_file.WorktreeOwnerFileError as error:
        return Verdict(False, f"its owner file could not be read: {error}", KEPT_NOT_CHECKABLE)
    if owner is None:
        if is_merge_lane_review_checkout(worktree):
            return merge_lane_review_checkout_verdict(worktree, pull_requests)
        return Verdict(False, "it has no owner file and is not idle: the cleaner removes a "
                              "worktree with no owner file only once nothing in it has changed "
                              "for 2 days and it holds no uncommitted or untracked file",
                       KEPT_NO_OWNER_FILE)

    keep_reason = in_progress_git_operation_keep_reason(worktree)
    if keep_reason is not None:
        return Verdict(False, keep_reason, KEPT_IN_USE, owner)

    state, explanation = owner_file.worktree_owner_running_state(owner)
    if state == owner_file.UNKNOWN:
        return Verdict(False, f"whether its owner, {owner_text(owner)}, runs could not be read: "
                              f"{explanation}", KEPT_NOT_CHECKABLE, owner, state)
    running = state == owner_file.RUNNING

    uncommitted, listing_error = uncommitted_or_untracked_files(worktree)
    if uncommitted is None:
        return Verdict(False, f"git cannot list its uncommitted changes ({listing_error})",
                       KEPT_NOT_CHECKABLE, owner, state)
    unlanded = run_git(worktree, "rev-list", "--count", "origin/main..HEAD")
    if unlanded.returncode != 0:
        return Verdict(False, f"cannot compare against origin/main "
                              f"({unlanded.stderr.strip()[:80]})", KEPT_NOT_CHECKABLE, owner, state)
    commits_not_on_main = int(unlanded.stdout.strip() or 0)

    pull_requests_of_branch = []
    if branch is not None:
        try:
            pull_requests_of_branch = pull_requests.by_head_branch().get(branch, [])
        except PullRequestListingFailed as error:
            return Verdict(False, f"the pull requests of its branch {branch} could not be read: "
                                  f"{error}", KEPT_NOT_CHECKABLE, owner, state)
    open_pull_requests = [pull_request for pull_request in pull_requests_of_branch
                          if pull_request["state"] == "OPEN"]
    # A merged or closed pull request counts only for the commit it was opened on, so a new
    # worktree on a reused branch name is not judged by an earlier pull request.
    finished_pull_requests = [pull_request for pull_request in pull_requests_of_branch
                              if pull_request["state"] in FINISHED_PULL_REQUEST_STATES
                              and pull_request["headRefOid"] == record.head]

    detached_commit = None
    if running:
        if open_pull_requests:
            return Verdict(False, f"its owner, {owner_text(owner)}, runs, and "
                                  f"{pull_request_text(open_pull_requests[0])} on its branch "
                                  f"{branch} is open", KEPT_OWNER_RUNNING, owner, state)
        if not finished_pull_requests:
            what = (f"its branch {branch} has no merged or closed pull request whose head commit "
                    f"is its HEAD" if branch is not None
                    else "its HEAD is detached, so no pull request is its")
            return Verdict(False, f"its owner, {owner_text(owner)}, runs, and {what}",
                           KEPT_OWNER_RUNNING, owner, state)
        if uncommitted:
            return Verdict(False, f"its owner, {owner_text(owner)}, runs, and it holds "
                                  f"{len(uncommitted)} uncommitted or untracked file(s): "
                                  f"{discarded_files_text(uncommitted)}",
                           KEPT_OWNER_RUNNING, owner, state)
        why = (f"its owner, {owner_text(owner)}, runs, and "
               f"{pull_request_text(finished_pull_requests[0])} on its branch {branch} is finished")
    else:
        if open_pull_requests:
            return Verdict(False, f"its owner, {owner_text(owner)}, has stopped, and "
                                  f"{pull_request_text(open_pull_requests[0])} on its branch "
                                  f"{branch} is open", KEPT_OPEN_PULL_REQUEST, owner, state)
        why = f"its owner, {owner_text(owner)}, has stopped ({explanation})"
        if branch is None and commits_not_on_main:
            detached_commit = record.head
            why += (f"; --remove first puts its {commits_not_on_main} commit(s) on no branch on the "
                    f"new branch {detached_commits_branch_name(worktree, detached_commit)}")
        if uncommitted:
            why += (f"; --remove first copies its {len(uncommitted)} uncommitted or untracked "
                    f"file(s) to a work-snapshot")

    # The slowest check, scanning every process, comes after every check that can keep the worktree.
    keep_reason = worktree_vacancy_keep_reason(worktree)
    if keep_reason is not None:
        return Verdict(False, keep_reason, KEPT_IN_USE, owner, state)

    # Listed last, after the slow vacancy check, so the list is as close to the removal as it can be.
    discarded, listing_error = files_a_removal_discards(worktree)
    if discarded is None:
        return Verdict(False, f"git cannot list its files ({listing_error})",
                       KEPT_NOT_CHECKABLE, owner, state)
    why += removal_records_and_discarded_files_text(worktree, discarded)
    return Verdict(True, why, "", owner, state, uncommitted, discarded, detached_commit,
                   record.head if running else None, branch if running else None)


def removal_records_and_discarded_files_text(worktree, discarded):
    """The end of a done worktree's line: the records --remove ships first and the files it discards."""
    text = ""
    records = log_store_records_in(worktree)
    if records:
        text += (f"; --remove first ships its {len(records)} record(s) to the log-store and "
                 f"keeps the worktree if a record does not ship; the records it ships: "
                 + ", ".join(str(record_path.relative_to(worktree)) for _, record_path in records))
    if discarded:
        text += (f"; removing it discards {len(discarded)} uncommitted, untracked or ignored "
                 f"file(s): {discarded_files_text(discarded)}")
    return text


def is_merge_lane_review_checkout(worktree):
    # HOME is read at call time: the tests point it at a scratch directory.
    directory = Path.home() / merge_lane_common.REVIEW_WORKTREES_DIRECTORY_UNDER_HOME
    return worktree.resolve().parent == directory.resolve()


def merge_lane_review_checkout_pull_request_number(name):
    """The pull request number a merge-lane review checkout's directory name holds, or None when
    it holds none or more than one."""
    numbers = [match.group(1) for part in name.split("-")
               if (match := MERGE_LANE_REVIEW_CHECKOUT_NAME_PULL_REQUEST_NUMBER_PART.fullmatch(part))]
    return int(numbers[0]) if len(numbers) == 1 else None


def merge_lane_review_checkout_verdict(worktree, pull_requests):
    """Return the Verdict for a merge-lane review checkout, as MERGE-LANE REVIEW CHECKOUTS says."""
    keep_reason = in_progress_git_operation_keep_reason(worktree)
    if keep_reason is not None:
        return Verdict(False, keep_reason, KEPT_IN_USE)
    number = merge_lane_review_checkout_pull_request_number(worktree.name)
    if number is None:
        return Verdict(False, "it is a merge-lane review checkout with no owner file, and its "
                              "name holds no single pull request number", KEPT_NO_OWNER_FILE)
    try:
        pull_request = pull_requests.by_number().get(number)
    except PullRequestListingFailed as error:
        return Verdict(False, f"it is a merge-lane review checkout of pull request #{number}, "
                              f"whose state could not be read: {error}", KEPT_NOT_CHECKABLE)
    if pull_request is None:
        return Verdict(False, f"it is a merge-lane review checkout of pull request #{number}, "
                              f"which gh's listing does not hold", KEPT_NO_OWNER_FILE)
    if pull_request["state"] not in FINISHED_PULL_REQUEST_STATES:
        return Verdict(False, f"it is a merge-lane review checkout of "
                              f"{pull_request_text(pull_request)}", KEPT_OPEN_PULL_REQUEST)
    try:
        finished = datetime.fromisoformat(pull_request["closedAt"])
        hours_since_finished = (datetime.now(timezone.utc) - finished).total_seconds() / 3600
    except (KeyError, TypeError, ValueError) as error:
        return Verdict(False, f"it is a merge-lane review checkout of "
                              f"{pull_request_text(pull_request)}, whose closing time gh did not "
                              f"give in a form this program reads: {type(error).__name__}: {error}",
                       KEPT_NOT_CHECKABLE)
    if hours_since_finished < MERGE_LANE_REVIEW_CHECKOUT_KEPT_AFTER_ITS_PULL_REQUEST_FINISHED_HOURS:
        return Verdict(False, f"it is a merge-lane review checkout of "
                              f"{pull_request_text(pull_request)}, finished less than "
                              f"{MERGE_LANE_REVIEW_CHECKOUT_KEPT_AFTER_ITS_PULL_REQUEST_FINISHED_HOURS} "
                              f"hours ago; the cleaner waits that long because merge-lane-2's merge "
                              f"program may still be using it, unseen by the vacancy check",
                       KEPT_IN_USE)
    keep_reason = worktree_vacancy_keep_reason(worktree)
    if keep_reason is not None:
        return Verdict(False, keep_reason, KEPT_IN_USE)
    discarded, listing_error = files_a_removal_discards(worktree)
    if discarded is None:
        return Verdict(False, f"git cannot list its files ({listing_error})", KEPT_NOT_CHECKABLE)
    why = f"it is a merge-lane review checkout of {pull_request_text(pull_request)}"
    why += removal_records_and_discarded_files_text(worktree, discarded)
    # No uncommitted list and no detached commit: no agent-seat owns a review checkout's files or
    # commits, so nothing goes to a work-snapshot or a branch.
    return Verdict(True, why, "", discarded=discarded)


def detached_commits_branch_name(worktree, commit):
    return DETACHED_COMMITS_BRANCH_NAME_TEMPLATE.format(worktree_name=worktree.name, commit=commit)


def branch_fully_on_origin_main_true_false_or_none_with_git_error(repo, branch):
    """Return (True, None) when every commit of the branch is on origin/main, (False, None) when
    one is not, and (None, git's error) when git cannot say."""
    result = run_git(repo, "merge-base", "--is-ancestor", f"refs/heads/{branch}", "origin/main")
    if result.returncode == 0:
        return True, None
    if result.returncode == 1:
        return False, None
    return None, (f"git merge-base --is-ancestor exited {result.returncode}: "
                  f"{' '.join(result.stderr.split()) or 'no error text'}")


def fully_on_origin_main(repo, branch):
    """Whether every commit of the branch is on origin/main; False when git cannot say."""
    return branch_fully_on_origin_main_true_false_or_none_with_git_error(repo, branch)[0] is True


def print_next_remove_run_line(line, one_named):
    """Print a line telling the reader the daily --remove retries, unless the run acts on one named
    worktree: the daily run judges an agent-seat's own worktree by its owner, and keeps it."""
    if not one_named:
        print(line)


def keep_what_removal_would_lose(worktree, repo, verdict, one_named=False):
    """Put a stopped owner's commits on no branch on a branch, and its uncommitted and untracked
    files in a work-snapshot; print and return False when either fails."""
    if verdict.detached_commit:
        name = detached_commits_branch_name(worktree, verdict.detached_commit)
        # An earlier --remove may have made this branch and then failed at a later step.
        if commit_of(repo, f"refs/heads/{name}") == verdict.detached_commit:
            made = None
        else:
            made = run_git(repo, "branch", name, verdict.detached_commit)
        if made is not None and made.returncode != 0:
            print(f"{worktree.name}: branch for its commits on no branch FAILED, worktree kept — "
                  f"git branch {name} {verdict.detached_commit} exited {made.returncode}: "
                  f"{made.stderr.strip()[:160] or 'no error text'}")
            print_next_remove_run_line(
                WORKTREE_KEPT_AFTER_FAILURE_NEXT_REMOVE_RUN_RETRIES_LINE_TEMPLATE.format(name=worktree.name),
                one_named)
            return False
        if made is None:
            print(f"{worktree.name}: its commits on no branch are already kept on the branch "
                  f"{name}, which an earlier scripts/clean-worktrees.py --remove run made before "
                  f"that run failed")
        else:
            print(f"{worktree.name}: its commits on no branch are kept on the new branch {name}")
    if verdict.uncommitted:
        agent_seat = verdict.owner["agent_seat"]
        try:
            existing = work_snapshot_holding_worktree_state(repo, worktree, agent_seat)
            if existing is None:
                # Owned by this invocation's process, which has ended by the time an agent-session
                # lists leftovers, so the agent-seat's next agent-session is told of it.
                owner_key = work_snapshots.owner_key_of_process(os.getpid())
                outcome = work_snapshots.refresh_work_snapshot(worktree, owner_key, agent_seat, "")
                existing = (work_snapshots.work_snapshot_ref(owner_key, worktree)
                            if outcome in ("written", "unchanged") else None)
        except Exception as error:
            print(f"{worktree.name}: work-snapshot FAILED, worktree kept — its uncommitted and "
                  f"untracked files could not be copied: {type(error).__name__}: {error}")
            print_next_remove_run_line(
                WORKTREE_KEPT_AFTER_FAILURE_NEXT_REMOVE_RUN_RETRIES_LINE_TEMPLATE.format(name=worktree.name),
                one_named)
            return False
        if existing:
            print(f"{worktree.name}: its uncommitted and untracked files are kept in the "
                  f"work-snapshot {existing}")
    return True


def work_snapshot_holding_worktree_state(repo, worktree, agent_seat):
    """The ref of a work-snapshot of the agent-seat that already holds exactly the worktree's
    uncommitted and untracked files on its HEAD, such as the hook's last one, or None."""
    tree = work_snapshots.tree_of_worktree_now(worktree)
    head = work_snapshots.head_commit_or_raise(worktree) or ""
    cache = {}
    for snapshot in work_snapshots.all_work_snapshots(repo):
        if (snapshot["worktree"] and Path(snapshot["worktree"]).resolve() == worktree.resolve()
                and snapshot["agent_seat"] == agent_seat
                and work_snapshots.tree_and_parents(repo, snapshot["commit"], cache) == (tree, head)):
            return snapshot["ref"]
    return None


def remove_worktree(worktree, branch, repo, verdict, one_named=False):
    """Ship its log-store records, keep what the removal would lose, then remove a done worktree
    and delete its branch when every commit of the branch is on origin/main, or, for one named
    worktree, whatever the branch holds; return False when something failed."""
    unshipped = ship_log_store_records(worktree)
    if unshipped:
        if one_named:
            # The run's FAILED line says what to do; the lines below promise a daily retry, which
            # keeps an agent-seat's own worktree while its owner runs.
            return False
        # No next-step line may contain FAILED: the handoff-supervisor counts each such line as a failure.
        if any(line.startswith("REFUSED:") and shipper != WALK_FILES_SHIPPER
               for shipper, line in unshipped):
            print(f"{worktree.name}: for each record whose line starts REFUSED:, rename its directory "
                  f"as that line says; the next scripts/clean-worktrees.py --remove then ships it "
                  f"and removes the worktree")
        # A walk's refusal names add-only files the store holds with other bytes; no rename resolves it.
        if any(line.startswith("REFUSED:") and shipper == WALK_FILES_SHIPPER
               for shipper, line in unshipped):
            print(f"{worktree.name}: for each walk whose line starts REFUSED:, the log-store holds "
                  f"another copy of each file that line names; the walk's owner decides which copy "
                  f"is right and makes the worktree's file match it; the next "
                  f"scripts/clean-worktrees.py --remove then ships the walk and removes the worktree")
        if not all(line.startswith("REFUSED:") for _, line in unshipped):
            print(f"{worktree.name}: for each record whose line does not start REFUSED:, do nothing "
                  f"now: the next scripts/clean-worktrees.py --remove, daily or at a handoff, "
                  f"ships the record again; "
                  f"if the record fails the same way there, fix the cause its line names")
        return False
    worktree_removal_unshippable_approval_walk_files_report(worktree)
    if verdict.idle_judged_at is not None:
        # The vacancy check, the pull request listing and the shipments ran after the idle rule
        # judged it; whoever left it may have come back since.
        keep_reason = idle_worktree_removal_keep_reason(worktree, verdict)
        if keep_reason is not None:
            print(f"{worktree.name}: kept — the idle rule judged it done, but {keep_reason}. "
                  f"Nothing needs doing now: the next scripts/clean-worktrees.py --remove run, "
                  f"daily or at a handoff, judges it again")
            return True
    if verdict.owner_state == owner_file.RUNNING:
        # classify() found it clean before the slow vacancy check and the shipments; its owner may
        # have written since.
        uncommitted, listing_error = uncommitted_or_untracked_files(worktree)
        if uncommitted is None or uncommitted:
            why = (f"git cannot list its uncommitted changes ({listing_error})" if uncommitted is None
                   else f"its owner, {owner_text(verdict.owner)}, runs, and it now holds "
                        f"{len(uncommitted)} uncommitted or untracked file(s): "
                        f"{discarded_files_text(uncommitted)}")
            print(f"{worktree.name}: kept — {why}")
            return True
        # The owner may have committed, or switched branch, since classify() matched the finished
        # pull request to the HEAD it read; that pull request does not cover new commits.
        head_now = commit_of(worktree, "HEAD")
        branch_now = checked_out_branch_name(worktree)
        if head_now != verdict.judged_head or branch_now != verdict.judged_branch:
            print(f"{worktree.name}: kept — its owner, {owner_text(verdict.owner)}, runs, and the "
                  f"worktree's HEAD or branch changed during this run: it was {verdict.judged_head} "
                  f"on {verdict.judged_branch or 'no branch'}, the head commit of a merged or "
                  f"closed pull request, and is now {head_now} on {branch_now or 'no branch'}. "
                  f"A merged or closed pull request counts only for the commit at its head, on "
                  f"its branch. Nothing needs doing now: the next scripts/clean-worktrees.py "
                  f"--remove run, daily or at a handoff, judges the worktree again")
            return True
    elif not keep_what_removal_would_lose(worktree, repo, verdict, one_named):
        return False
    # Named before the removal too: a removal that fails or is killed partway may already have deleted some.
    discarded = verdict.discarded
    if discarded:
        print(f"{worktree.name}: removing it will discard {len(discarded)} uncommitted, "
              f"untracked or ignored file(s): {discarded_files_text(discarded)}")
    head = commit_of(worktree, "HEAD")
    git_directory = os.fsdecode(git_output.run_git(worktree, ["rev-parse", "--absolute-git-dir"]))
    record_file = unfinished_worktree_removal_record_file(repo, worktree)
    record = {"worktree": str(worktree.resolve()), "registration": git_directory.strip(),
              "branch": branch, "head": head, "discarded": list(discarded)}
    try:
        record_file.parent.mkdir(exist_ok=True)
        written = record_file.with_suffix(".json.writing")
        written.write_text(json.dumps(record), encoding="utf-8")
        os.replace(written, record_file)
    except OSError as error:
        print(f"{worktree.name}: removal FAILED, worktree kept — scripts/clean-worktrees.py could "
              f"not write its removal record {record_file}: {error}. It writes that record before "
              f"every removal, so that a later run can finish a removal stopped partway")
        print_next_remove_run_line(
            WORKTREE_KEPT_AFTER_FAILURE_NEXT_REMOVE_RUN_RETRIES_LINE_TEMPLATE.format(name=worktree.name),
            one_named)
        return False
    # A single --force removes untracked and modified files but still refuses a locked worktree.
    removal = run_git(repo, "worktree", "remove", "--force", str(worktree))
    if removal.returncode != 0:
        # A refusal that deleted nothing leaves a record the next run drops as never begun.
        print(f"{worktree.name}: removal FAILED — {removal.stderr.strip()[:120]}")
        return False
    record["file"] = record_file
    return report_removal_and_delete_branch_then_delete_unfinished_worktree_removal_record(record, repo, one_named)


def finish_recorded_removal(record, repo, one_named):
    """Delete what a removal stopped partway left of the worktree's directory and of its
    registration, then report the removal, delete its branch and delete its record; return False
    when something failed, keeping the record for the next run."""
    worktree = Path(record["worktree"])
    registration = Path(record["registration"])
    try:
        if worktree.exists():
            shutil.rmtree(worktree)
        if registration.exists() and registration_points_to_worktree_or_has_no_gitdir_file(registration, worktree):
            shutil.rmtree(registration)
    except OSError as error:
        print(f"{worktree.name}: removal FAILED — an earlier scripts/clean-worktrees.py --remove "
              f"was stopped partway through removing this worktree, and deleting what that run "
              f"left of its directory and of its registration directory {registration} "
              f"failed: {error}")
        print_next_remove_run_line(
            f"{worktree.name}: do nothing now: the next scripts/clean-worktrees.py --remove, daily "
            f"or at a handoff, tries again to finish the removal from its record "
            f"{record['file']}; if it fails the same way there, fix the cause the line above "
            f"names", one_named)
        return False
    branch = record.get("branch")
    if branch:
        lookup = run_git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}")
        # --verify --quiet exits 1 only for a missing ref; any other failure says nothing of it.
        if lookup.returncode == 1:
            branch = None
        elif lookup.returncode != 0:
            print(f"{worktree.name}: removal FAILED — an earlier scripts/clean-worktrees.py "
                  f"--remove was stopped partway through removing this worktree, and git "
                  f"rev-parse could not tell whether its branch {branch} is still there (exit "
                  f"{lookup.returncode}): {lookup.stderr.strip()[:120]}")
            print_next_remove_run_line(
                f"{worktree.name}: do nothing now: the next scripts/clean-worktrees.py --remove, "
                f"daily or at a handoff, tries again to finish the removal from its record "
                f"{record['file']}; if it fails the same way there, fix the cause the line above "
                f"names", one_named)
            return False
    record["branch"] = branch
    return report_removal_and_delete_branch_then_delete_unfinished_worktree_removal_record(record, repo, one_named)


def registration_points_to_worktree_or_has_no_gitdir_file(registration, worktree):
    """Whether the registration's gitdir file names the worktree's .git file, or is gone; a
    registration git has since given to another worktree is not deleted. Raise OSError when the
    gitdir file is there but cannot be read."""
    try:
        # git writes a relative gitdir, under --relative-paths, relative to the registration.
        named = registration / os.fsdecode((registration / "gitdir").read_bytes().strip())
    except FileNotFoundError:
        return True
    return named.resolve() == (worktree / ".git").resolve()


def report_removal_and_delete_branch_then_delete_unfinished_worktree_removal_record(record, repo, one_named):
    """Report the recorded removal and delete its branch, then delete its record; return False
    when something failed."""
    worktree = Path(record["worktree"])
    reported = report_removal_and_delete_branch(
        worktree, record.get("branch"), repo, record.get("head") or "unknown",
        record.get("discarded"), one_named)
    try:
        record["file"].unlink()
    except OSError as error:
        print(f"{worktree.name}: deleting its removal record {record['file']} FAILED: {error}; "
              f"the next scripts/clean-worktrees.py --remove finds the worktree gone and "
              f"deletes the record then")
        return False
    return reported


def finish_or_drop_recorded_removals(repo, main_checkout, remove):
    """Finish, with --remove, each recorded removal that began, and drop each that never began;
    in the report modes name each that began as done. Return (failures, the worktree paths the
    worktree loop leaves out); raise git_output.GitCommandFailed when git cannot list them."""
    records, unreadable = unfinished_worktree_removal_records(repo)
    failures = 0
    for record_file, error in unreadable:
        print(f"{record_file.name}: FAILED — scripts/clean-worktrees.py cannot read this removal "
              f"record in {record_file.parent}: {error}. Read it; finish the removal it names by "
              f"hand, or delete the file if it names none")
        failures += 1
    listed = {Path(worktree).resolve(): record
              for worktree, _, record in list_worktrees(repo, main_checkout)}
    handled = set()
    for record in records:
        worktree = Path(record["worktree"])
        if removal_never_began(record, listed):
            if remove:
                try:
                    record["file"].unlink()
                except OSError as error:
                    print(f"{worktree.name}: deleting its removal record {record['file']}, "
                          f"whose removal never began, FAILED: {error}")
                    failures += 1
            continue
        handled.add(worktree.resolve())
        if not remove:
            print(f"{worktree.name}: done — an earlier scripts/clean-worktrees.py --remove was "
                  f"stopped while removing this worktree, and the next --remove finishes that "
                  f"removal")
        elif not finish_recorded_removal(record, repo, one_named=False):
            failures += 1
    return failures, handled


def report_removal_and_delete_branch(worktree, branch, repo, head, discarded, one_named):
    """Print the removal's line, delete its branch as BRANCHES and ONE NAMED WORKTREE OR BRANCH
    say, and write the log of removals, with discarded None when the files deleted with the
    worktree cannot be known; return False when something failed."""
    line = f"{worktree.name}: removed"
    branch_deleted = False
    branch_failed = False
    branch_tip = head
    if branch and branch != MAIN_BRANCH and one_named:
        # The caller has decided the branch is not carried on; the log of removals keeps its tip.
        branch_tip = commit_of(repo, f"refs/heads/{branch}")
        deletion = run_git(repo, "branch", "-D", branch)
        branch_deleted = deletion.returncode == 0
        branch_failed = not branch_deleted
        if branch_deleted:
            line += f", branch {branch} deleted, its last commit {branch_tip}"
        else:
            line += (f", but deleting its branch {branch} FAILED: git branch -D exited "
                     f"{deletion.returncode}: {deletion.stderr.strip()[:120] or 'no error text'}")
    elif branch and branch != MAIN_BRANCH:
        if not fully_on_origin_main(repo, branch):
            line += f", branch {branch} not deleted with git branch -d, since it holds commits origin/main lacks"
        else:
            branch_deleted = run_git(repo, "branch", "-d", branch).returncode == 0
            if branch_deleted:
                line += f", branch {branch} deleted"
            else:
                line += f", branch {branch} left in place (git branch -d refused)"
    print(line)
    if discarded:
        print(f"{worktree.name}: discarded with it {len(discarded)} uncommitted, untracked "
              f"or ignored file(s): {discarded_files_text(discarded)}")
    events = [("removed-worktree", {"path": worktree, "branch": branch or "none", "head": head,
                                    "discarded-files": "unknown" if discarded is None
                                    else len(discarded)})]
    if branch_deleted:
        events.append(("deleted-branch", {"branch": branch, "commit": branch_tip}))
    logged = append_removed_worktree_or_deleted_branch_log_lines(events, repo, worktree.name)
    return logged and not branch_failed


def local_branches_with_no_pull_request_text(repo, pull_requests):
    """The count of local branches other than main that no pull request has as its head branch,
    or why it could not be counted."""
    listing = run_git(repo, "for-each-ref", "--format=%(refname:lstrip=2)", "refs/heads/")
    if listing.returncode != 0:
        return f"unknown (git cannot list the branches: {listing.stderr.strip()[:80]})"
    try:
        by_head_branch = pull_requests.by_head_branch()
    except PullRequestListingFailed as error:
        return f"unknown ({error})"
    return str(sum(1 for branch in listing.stdout.splitlines()
                   if branch != MAIN_BRANCH and branch not in by_head_branch))


def work_snapshots_present_text(repo):
    try:
        return str(len(work_snapshots.all_work_snapshots(repo)))
    except Exception as error:
        return f"unknown ({type(error).__name__}: {error})"


def print_count_lines(repo, kept_verdicts, pull_requests):
    """Print the count line, and the line naming the kept worktrees of stopped agent-seats."""
    by_reason = Counter(verdict.kept_for for _, verdict in kept_verdicts)
    print(f"worktree counts: {len(kept_verdicts)} kept ("
          + ", ".join(f"{reason} {by_reason[reason]}" for reason in KEPT_REASONS_IN_ORDER)
          + f"); worktrees with no owner file {by_reason[KEPT_NO_OWNER_FILE]}; branches with no "
            f"pull request {local_branches_with_no_pull_request_text(repo, pull_requests)}; "
            f"work-snapshots still present {work_snapshots_present_text(repo)}")
    stopped_seats = [(worktree, verdict.owner["agent_seat"]) for worktree, verdict in kept_verdicts
                     if verdict.owner is not None
                     and verdict.owner["owner_kind"] == owner_file.OWNER_AGENT_SEAT
                     and verdict.owner_state == owner_file.STOPPED]
    if stopped_seats:
        print("worktrees kept whose agent-seat's handoff-supervisor is not running: "
              + ", ".join(f"{worktree} ({seat})" for worktree, seat in stopped_seats))
    for_the_user = [worktree for worktree, verdict in kept_verdicts
                    if verdict.for_the_user_to_keep_or_delete]
    if for_the_user:
        print("worktrees for the user to keep or delete, locked by Claude Code for a subagent "
              "whose claude process has ended and which no one agent-seat's Claude Code "
              "transcripts name: " + ", ".join(str(worktree) for worktree in for_the_user))


def clean_worktrees_and_branch_refs(repo, main_checkout, remove, only_done):
    """Report or remove the worktrees and orphaned branch refs, and report dead registrations;
    return the number of failures, or raise git_output.GitCommandFailed when git cannot list them."""
    failures, recorded = finish_or_drop_recorded_removals(repo, main_checkout, remove)
    pull_requests = PullRequestsByHeadBranchLazyCache(repo)
    kept_verdicts = []
    # --remove deletes with -D a branch whose done worktree it has just removed; the report says so too.
    branches_of_done_worktrees = set()
    for worktree, branch, record in list_worktrees(repo, main_checkout):
        if worktree.resolve() in recorded:
            continue
        verdict = None
        if remove and record.locked_reason is not None:
            verdict, ended_lock = claude_code_subagent_lock_verdict_or_ended_lock(worktree, record)
            if ended_lock is not None:
                if not ended_claude_code_subagent_lock_unlock(worktree, repo, ended_lock):
                    failures += 1
                    kept_verdicts.append((worktree, Verdict(
                        False, "its owner file or its unlock failed", KEPT_NOT_CHECKABLE)))
                    continue
                record = record._replace(locked_reason=None)
        if verdict is None:
            verdict = classify(worktree, branch, record, pull_requests)
        if not verdict.done:
            kept_verdicts.append((worktree, verdict))
        elif branch is not None:
            branches_of_done_worktrees.add(branch)
        if remove:
            if verdict.done and not remove_worktree(worktree, branch, repo, verdict):
                failures += 1
            elif not verdict.done:
                print(f"{worktree.name}: kept — {verdict.reason}")
        elif only_done:
            if verdict.done:
                print(f"{worktree.name}: done ({verdict.reason}) — remove with "
                      f"scripts/clean-worktrees.py --remove")
        else:
            state = "done" if verdict.done else "kept"
            print(f"{worktree.name}: {state} — {verdict.reason}")

    orphaned_refs = branch_refs_with_no_worktree_fully_on_main(repo)
    if orphaned_refs:
        if remove:
            for branch in orphaned_refs:
                if not delete_orphaned_branch_ref(branch, repo):
                    failures += 1
        else:
            print("branch ref(s) with no worktree, nothing beyond origin/main: "
                  + ", ".join(orphaned_refs)
                  + " — remove with: scripts/clean-worktrees.py --remove")

    force_deletable, not_judged, task_lists_unreadable = finished_pull_request_head_branches_to_force_delete(
        repo, pull_requests, frozenset() if remove else branches_of_done_worktrees)
    if not_judged and not only_done:
        print(f"branches: none deleted with git branch -D, since {not_judged}")
    if task_lists_unreadable:
        print(f"FAILED: no branch deleted with git branch -D, since {task_lists_unreadable}; "
              f"each branch is kept, and the next scripts/clean-worktrees.py --remove judges it "
              f"again once every task list can be read in full")
        failures += 1
    if force_deletable:
        if remove:
            for branch, tip, pull_request in force_deletable:
                if not force_delete_finished_pull_request_head_branch(branch, tip, pull_request, repo):
                    failures += 1
        else:
            print(f"{FORCE_DELETABLE_BRANCH_LINE_START}"
                  + ", ".join(f"{branch} (#{pull_request['number']})"
                              for branch, _, pull_request in force_deletable)
                  + " — remove with: scripts/clean-worktrees.py --remove")

    if not only_done:
        print_count_lines(repo, kept_verdicts, pull_requests)

    dead_registrations = dead_worktree_registrations(repo)
    if dead_registrations:
        print("dead registration(s) git would prune: "
              + ", ".join(f"{path} ({reason})" for path, reason in dead_registrations)
              + " — remove with: git worktree prune")

    return failures


TASK_LISTS_DIRECTORY_OVERRIDE_VARIABLE = "CLEAN_WORKTREES_TASK_LISTS_DIRECTORY_OVERRIDE"


def task_lists_directory_from_override_or_home_claude_tasks():
    """The directory of Claude Code task lists the cleaner judges: the override's, when set, or
    ~/.claude/tasks."""
    override = os.environ.get(TASK_LISTS_DIRECTORY_OVERRIDE_VARIABLE)
    return Path(override) if override else Path.home() / ".claude" / "tasks"


NEDSCHORUS_TASK_LISTS_GLOB = "nedschorus-*-tasks"


def nedschorus_task_list_directories(task_lists_directory):
    """Return the agent-seat task lists' directories in task_lists_directory, sorted, and none when
    it does not exist; raise OSError when it, or one of them, exists but cannot be listed or
    looked at."""
    # Path.exists and Path.glob both answer an unreadable path as an absent one.
    try:
        names = os.listdir(task_lists_directory)
    except FileNotFoundError:
        return []
    return [path for path in sorted(Path(task_lists_directory) / name for name in names
                                    if fnmatch.fnmatchcase(name, NEDSCHORUS_TASK_LISTS_GLOB))
            if stat.S_ISDIR(os.stat(path).st_mode)]
RESTORED_BRANCH_TASKS_CLOSE_GIT_FETCH_TIMEOUT_SECONDS = 300


def open_restored_branch_tasks(task_lists_directory, out):
    """(task file, task) for each task restore opened that is not marked completed, and the
    number of task files that could not be read, each named in a FAILED line."""
    tasks, failures = [], 0
    try:
        list_directories = nedschorus_task_list_directories(task_lists_directory)
    except OSError as error:
        out(f"FAILED: the task lists' directory {task_lists_directory} could not be listed "
            f"({type(error).__name__}: {error}), so no restored branch's task in it was judged")
        return tasks, 1
    for list_directory in list_directories:
        try:
            task_files = sorted(list_directory.iterdir())
        except OSError as error:
            out(f"FAILED: the task list {list_directory} could not be read ({type(error).__name__}: "
                f"{error}), so its restored branches' tasks are left as they were")
            failures += 1
            continue
        for task_file in task_files:
            if not work_snapshots.agent_seat_task_list.TASK_FILE_NAME_PATTERN.fullmatch(task_file.name):
                continue
            try:
                task = json.loads(task_file.read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                out(f"FAILED: the task file {task_file} could not be read ({type(error).__name__}: "
                    f"{error}), so whether it is a restored branch's task to close is unknown; "
                    f"it is left as it was")
                failures += 1
                continue
            if (isinstance(task, dict) and task.get("status") != "completed"
                    and str(task.get("subject", "")).startswith(
                        work_snapshots.RESTORED_BRANCH_TASK_SUBJECT_PREFIX)):
                tasks.append((task_file, task))
    return tasks, failures


def restore_commit_of_task(task):
    prefix = work_snapshots.RESTORED_BRANCH_TASK_DESCRIPTION_RESTORE_COMMIT_LINE_PREFIX
    for line in str(task.get("description", "")).splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return None


def restore_commit_done_reason(repo, commit):
    """(why the restored branch's task is done, or None while a ref holds work main lacks;
    the git failure that kept it from being judged, or None)."""
    on_main = run_git(repo, "merge-base", "--is-ancestor", commit, "origin/main")
    if not on_main.returncode:
        return f"the restore commit {commit} is reachable from origin/main", None
    if on_main.returncode != 1:  # pragma: no mutate, > 1 differs only for a git killed by a signal
        return None, (f"git merge-base --is-ancestor {commit} origin/main "
                      f"{work_snapshots.git_failure_text(on_main)}")
    holders = run_git(repo, "for-each-ref", "--contains", commit, "--format=%(refname)")
    if holders.returncode:
        return None, (f"git for-each-ref --contains {commit} "
                      f"{work_snapshots.git_failure_text(holders)}")
    if holders.stdout.strip():
        return None, None
    return f"no ref holds the restore commit {commit} any more", None


def close_restored_branch_tasks(repo, remove, only_done, task_lists_directory=None, out=print):
    """Mark completed each task restore opened whose restore commit is on origin/main or held
    by no ref; return the number of failures. Without remove, name them and change nothing."""
    if task_lists_directory is None:
        task_lists_directory = task_lists_directory_from_override_or_home_claude_tasks()
    tasks, failures = open_restored_branch_tasks(task_lists_directory, out)
    if not tasks:
        return failures
    if remove:
        try:
            fetched = subprocess.run(["git", "-C", str(repo), "fetch", "--prune", "origin"],
                                     capture_output=True, text=True, check=False,
                                     timeout=RESTORED_BRANCH_TASKS_CLOSE_GIT_FETCH_TIMEOUT_SECONDS)
            fetch_failure = (work_snapshots.git_failure_text(fetched) if fetched.returncode
                             else None)
        except subprocess.TimeoutExpired:
            fetch_failure = (f"ran past {RESTORED_BRANCH_TASKS_CLOSE_GIT_FETCH_TIMEOUT_SECONDS} "
                             f"seconds")
        if fetch_failure:
            out(f"FAILED: git fetch --prune origin {fetch_failure}, so the restored branches' "
                f"tasks were not judged and are left as they were: "
                + ", ".join(str(task_file) for task_file, _task in tasks))
            return failures + 1
    for task_file, task in tasks:
        name = f"task {task_file.parent.name}/{task_file.stem} ({task.get('subject')})"
        commit = restore_commit_of_task(task)
        if commit is None:
            out(f"FAILED: {name} has no line opening "
                f"\"{work_snapshots.RESTORED_BRANCH_TASK_DESCRIPTION_RESTORE_COMMIT_LINE_PREFIX}\", "
                f"so its restore commit is unknown; it is left as it was")
            failures += 1
            continue
        reason, git_failure = restore_commit_done_reason(repo, commit)
        if git_failure:
            out(f"FAILED: {name} could not be judged ({git_failure}); it is left as it was")
            failures += 1
            continue
        if reason is None:
            if not only_done:
                out(f"{name}: kept open — a ref still holds its restore commit {commit}, "
                    f"which origin/main lacks")
            continue
        if not remove:
            out(f"{name}: would be marked completed, as {reason} — mark it with: "
                f"scripts/clean-worktrees.py --remove")
            continue
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        task = dict(task, status="completed", description=(
            str(task.get("description", "")).rstrip("\n")
            + f"\nMarked completed by scripts/clean-worktrees.py at {now}: {reason}."))
        partial = None
        try:
            # A partial file of its own: cleaners run at the same time, one per session-handoff.
            descriptor, partial = tempfile.mkstemp(prefix=f".{task_file.name}.", suffix=".partial",
                                                   dir=task_file.parent)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(json.dumps(task, indent=2))
            os.replace(partial, task_file)
        except OSError as error:
            if partial is not None:
                with contextlib.suppress(OSError):
                    os.unlink(partial)
            out(f"FAILED: {name} could not be rewritten as completed ({type(error).__name__}: "
                f"{error}); it is left as it was")
            failures += 1
        else:
            out(f"{name}: marked completed, as {reason}")
    return failures


REMOVE_WORKTREE_AND_FORCE_DELETE_ITS_BRANCH_COMMAND_LINE_FLAG = "--remove-worktree-and-force-delete-its-branch"
FORCE_DELETE_BRANCH_FLAG = "--force-delete-branch"
# The first prompt's list tells the agent to keep the item and tell the user when a line opens so.
ONE_NAMED_FAILED_LINE_TEMPLATE = (
    "FAILED: {what} was not fully removed or deleted; the line above says what was done to it "
    "and why the rest was not")


def commits_the_clone_holds(repo, shas):
    """The ones of shas whose objects the clone holds."""
    present = subprocess.run(["git", "-C", str(repo), "cat-file", "--batch-check=%(objectname)"],
                             input="".join(f"{sha}\n" for sha in shas),
                             capture_output=True, text=True, check=False)
    return {line for line in present.stdout.splitlines() if not line.endswith(" missing")}


def commit_unreached_from(repo, tip, tips):
    """git rev-list's run naming tip when none of tips reaches it, and nothing when one does."""
    # --not on the command line does not reach revisions read from --stdin, so each carries its own ^.
    return subprocess.run(["git", "-C", str(repo), "rev-list", "--max-count=1", tip, "--stdin"],
                          input="".join(f"^{sha}\n" for sha in sorted(tips)),
                          capture_output=True, text=True, check=False)


def push_branch_unless_origin_holds_its_last_commit_failure(repo, branch):
    """Push the branch to origin with a plain push, skipping the clone's client hooks, when no ref of origin, a pull request's
    refs/pull/<number>/head included, holds its last commit, as git ls-remote finds origin now;
    return why that failed, or None."""
    tip = commit_of(repo, f"refs/heads/{branch}")
    # Remote-tracking refs can name a branch GitHub has since deleted, and leave out pull request refs.
    listing = run_git(repo, "ls-remote", "origin")
    if listing.returncode != 0:
        return (f"git ls-remote origin exited {listing.returncode}, so whether origin holds its "
                f"last commit {tip} is unknown: {listing.stderr.strip()[:160] or 'no error text'}")
    ref_of_tip = {}
    for line in listing.stdout.splitlines():
        if line:
            sha, _, ref = line.partition("\t")
            # A peeled annotated tag, refs/tags/<tag>^{}, is no refspec git fetch takes; the tag's
            # own line brings its commit.
            if not ref.endswith("^{}"):
                ref_of_tip.setdefault(sha, ref)
    known = commits_the_clone_holds(repo, ref_of_tip)
    unreached = commit_unreached_from(repo, tip, known)
    missing = sorted(set(ref_of_tip) - known)
    if unreached.returncode == 0 and unreached.stdout.strip() and missing:
        # rev-list refuses an object the clone lacks, and a tip it has not fetched, such as a pull
        # request ref another machine moved, may hold the commit: fetch those tips and look again.
        fetch = run_git(repo, "fetch", "--no-write-fetch-head", "origin",
                        *sorted({ref_of_tip[sha] for sha in missing}))
        if fetch.returncode != 0:
            return (f"git fetch origin exited {fetch.returncode}, so whether origin holds its "
                    f"last commit {tip} is unknown: {fetch.stderr.strip()[:160] or 'no error text'}")
        unreached = commit_unreached_from(repo, tip, commits_the_clone_holds(repo, ref_of_tip))
    if unreached.returncode != 0:
        return (f"git rev-list exited {unreached.returncode}, so whether origin holds its last "
                f"commit {tip} is unknown: {unreached.stderr.strip()[:160] or 'no error text'}")
    if not unreached.stdout.strip():
        return None
    # A backup is never a pull request branch, so the clone's pre-push conflict check, which would
    # refuse the old leftover branches deleted here, does not apply.
    push = run_git(repo, "push", "--no-verify", "origin", f"refs/heads/{branch}:refs/heads/{branch}")
    if push.returncode != 0:
        return (f"origin lacks its last commit {tip}, and git push origin exited "
                f"{push.returncode}: {' '.join(push.stderr.split())[:200] or 'no error text'}")
    print(f"branch {branch}: pushed to origin, which lacked its last commit {tip}")
    return None


def open_pull_request_of(by_head_branch, branch, head):
    """The open pull request whose head branch is the branch, or whose head commit is the head,
    or None."""
    for pull_requests in by_head_branch.values():
        for pull_request in pull_requests:
            if pull_request["state"] == "OPEN" and (
                    (branch is not None and pull_request["headRefName"] == branch)
                    or (head and pull_request["headRefOid"] == head)):
                return pull_request
    return None


def one_named_worktree_keep_reason(worktree, branch, record, by_head_branch):
    """Return (why the named worktree must be kept, whether that is not a failure, the owner,
    its uncommitted files, the files its removal discards); the reason is None when it may go."""
    if record.locked_reason is not None:
        return (f"it is locked with git worktree lock "
                f"({record.locked_reason or 'no reason given'})", False, None, None, None)
    if record.prunable_reason is not None:
        return (f"git would prune its registration ({record.prunable_reason})",
                False, None, None, None)
    try:
        owner = owner_file.worktree_owner_file_read(worktree)
    except owner_file.WorktreeOwnerFileError as error:
        return f"its owner file could not be read: {error}", False, None, None, None
    if owner is None:
        return ("it has no owner file, and a named removal removes only a worktree holding one",
                False, None, None, None)
    keep_reason = in_progress_git_operation_keep_reason(worktree)
    if keep_reason is not None:
        return keep_reason, False, owner, None, None
    if owner["owner_kind"] == owner_file.OWNER_AGENT_SESSION:
        state, explanation = owner_file.worktree_owner_running_state(owner)
        if state != owner_file.STOPPED:
            return (f"its owner, {owner_text(owner)}, runs or cannot be read ({explanation}), "
                    f"so the work in it may still be in progress", False, owner, None, None)
    pull_request = open_pull_request_of(by_head_branch, branch, record.head)
    if pull_request is not None:
        return (f"{pull_request_text(pull_request)} has its branch or its HEAD commit as its head, "
                f"so the work in it is still under review", True, owner, None, None)
    keep_reason = worktree_vacancy_keep_reason(worktree)
    if keep_reason is not None:
        return keep_reason, False, owner, None, None
    uncommitted, listing_error = uncommitted_or_untracked_files(worktree)
    if uncommitted is None:
        return (f"git cannot list its uncommitted changes ({listing_error})",
                False, owner, None, None)
    discarded, listing_error = files_a_removal_discards(worktree)
    if discarded is None:
        return f"git cannot list its files ({listing_error})", False, owner, None, None
    return None, False, owner, uncommitted, discarded


def remove_one_named_worktree(repo, main_checkout, path):
    """Remove the one worktree named, as ONE NAMED WORKTREE OR BRANCH says; return whether it was
    removed, or kept for an open pull request, with nothing failing. Raise
    git_output.GitCommandFailed when git cannot list the worktrees."""
    wanted = Path(path).resolve()
    listed = {Path(worktree).resolve(): record
              for worktree, _, record in list_worktrees(repo, main_checkout)}
    records, unreadable = unfinished_worktree_removal_records(repo)
    for record_file, error in unreadable:
        print(f"{record_file.name}: kept — scripts/clean-worktrees.py cannot read this removal "
              f"record in {record_file.parent}: {error}")
    for record in records:
        if Path(record["worktree"]).resolve() != wanted:
            continue
        if not removal_never_began(record, listed):
            branch = record.get("branch")
            if branch and branch != MAIN_BRANCH and commit_of(repo, f"refs/heads/{branch}") != "unknown":
                failure = push_branch_unless_origin_holds_its_last_commit_failure(repo, branch)
                if failure is not None:
                    print(f"{Path(path).name}: kept — an earlier run of scripts/clean-worktrees.py "
                          f"stopped partway through removing this worktree; this run keeps what "
                          f"is left of it and its branch {branch}, because this run could not make sure "
                          f"origin holds the branch's last commit: {failure}")
                    return False
            return finish_recorded_removal(record, repo, one_named=True)
        try:
            record["file"].unlink()
        except OSError as error:
            print(f"{Path(path).name}: deleting its removal record {record['file']}, whose "
                  f"removal never began, FAILED: {error}")
            return False
    found = [(worktree, branch, record)
             for worktree, branch, record in list_worktrees(repo, main_checkout)
             if worktree.resolve() == wanted]
    if not found:
        print(f"{path}: kept — it is not a worktree of {repo} other than its main checkout, "
              f"as `git worktree list` shows them")
        return False
    worktree, branch, record = found[0]
    try:
        by_head_branch = list_all_pull_requests_grouped_by_head_branch(repo)
    except PullRequestListingFailed as error:
        print(f"{worktree.name}: kept — whether a pull request is open on it could not be read: "
              f"{error}")
        return False
    reason, not_a_failure, owner, uncommitted, discarded = one_named_worktree_keep_reason(
        worktree, branch, record, by_head_branch)
    if reason is not None:
        print(f"{worktree.name}: kept — {reason}")
        return not_a_failure
    if branch and branch != MAIN_BRANCH:
        failure = push_branch_unless_origin_holds_its_last_commit_failure(repo, branch)
        if failure is not None:
            print(f"{worktree.name}: kept — its branch {branch} is kept too, since {failure}")
            return False
    verdict = Verdict(True, "", "", owner, "", uncommitted, discarded)
    return remove_worktree(worktree, branch, repo, verdict, one_named=True)


def delete_one_named_branch(repo, branch):
    """Delete the one branch named, as ONE NAMED WORKTREE OR BRANCH says; return whether it was
    deleted, or kept for an open pull request, with nothing failing. Raise
    git_output.GitCommandFailed when git cannot list the worktrees."""
    name = f"branch {branch}"
    if branch == MAIN_BRANCH:
        print(f"{name}: kept — the cleaner never deletes {MAIN_BRANCH}")
        return False
    tip = commit_of(repo, f"refs/heads/{branch}")
    if tip == "unknown":
        print(f"{name}: kept — there is no local branch of that name in {repo}")
        return False
    listing = git_output.run_git(repo, ["worktree", "list", "--porcelain", "-z"])
    for record in git_output.worktree_records(listing):
        if local_branch_name_of_full_ref(record.branch) == branch:
            print(f"{name}: kept — the worktree {record.path} has it checked out; remove that "
                  f"worktree with scripts/clean-worktrees.py --repo {shlex.quote(str(repo))} "
                  f"{REMOVE_WORKTREE_AND_FORCE_DELETE_ITS_BRANCH_COMMAND_LINE_FLAG} {shlex.quote(record.path)}, which deletes "
                  f"its branch too")
            return False
    try:
        by_head_branch = list_all_pull_requests_grouped_by_head_branch(repo)
    except PullRequestListingFailed as error:
        print(f"{name}: kept — whether a pull request is open on it could not be read: {error}")
        return False
    pull_request = open_pull_request_of(by_head_branch, branch, None)
    if pull_request is not None:
        print(f"{name}: kept — {pull_request_text(pull_request)} has it as its head branch, so "
              f"its work is still under review")
        return True
    failure = push_branch_unless_origin_holds_its_last_commit_failure(repo, branch)
    if failure is not None:
        print(f"{name}: kept — {failure}")
        return False
    unlanded = run_git(repo, "rev-list", "--count", f"origin/main..{tip}")
    count = unlanded.stdout.strip() if unlanded.returncode == 0 else "unknown"
    deletion = run_git(repo, "branch", "-D", branch)
    if deletion.returncode != 0:
        print(f"{name}: kept — git branch -D exited {deletion.returncode}: "
              f"{deletion.stderr.strip()[:160] or 'no error text'}")
        return False
    print(f"{name}: deleted, its last commit {tip}, with {count} commit(s) origin/main lacks")
    return append_removed_worktree_or_deleted_branch_log_lines(
        [("deleted-branch", {"branch": branch, "commit": tip,
                             "commits-not-on-origin-main": count})], repo, name)


def one_named_worktree_or_branch_exit_code(repo, main_checkout, worktree_path, branch):
    """Act on the one named worktree or branch; print the FAILED line and return 1 when it was
    kept for a reason other than an open pull request, or something failed."""
    what = f"the worktree {worktree_path}" if worktree_path is not None else f"the branch {branch}"
    try:
        if worktree_path is not None:
            done = remove_one_named_worktree(repo, main_checkout, worktree_path)
        else:
            done = delete_one_named_branch(repo, branch)
    except git_output.GitCommandFailed as error:
        print(f"{what}: kept — git could not list the worktrees: {' '.join(str(error).split())}")
        done = False
    if done:
        return 0
    print(ONE_NAMED_FAILED_LINE_TEMPLATE.format(what=what))
    return 1


def main(argv=None):
    # The daily job writes to a log without -u; a run killed mid-removal must still show what it announced.
    sys.stdout.reconfigure(line_buffering=True)
    arguments = sys.argv[1:] if argv is None else list(argv)
    given_arguments = list(arguments)
    if arguments in (["--help"], ["-h"]):
        print(__doc__)
        return 0
    repo = REPO_ROOT
    if "--repo" in arguments:
        flag_position = arguments.index("--repo")
        try:
            repo = Path(arguments[flag_position + 1])
        except IndexError:
            print("clean-worktrees: --repo needs a path", file=sys.stderr)
            return 2
        del arguments[flag_position:flag_position + 2]
    named = {}
    for flag in (REMOVE_WORKTREE_AND_FORCE_DELETE_ITS_BRANCH_COMMAND_LINE_FLAG, FORCE_DELETE_BRANCH_FLAG):
        if flag in arguments:
            flag_position = arguments.index(flag)
            if flag_position + 1 >= len(arguments):
                print(f"clean-worktrees: {flag} needs a value", file=sys.stderr)
                return 2
            named[flag] = arguments[flag_position + 1]
            del arguments[flag_position:flag_position + 2]
    only_done = "--only-done" in arguments
    remove = "--remove" in arguments
    leftover = [a for a in arguments if a not in ("--only-done", "--remove")]
    if leftover or (only_done and remove) or (named and (only_done or remove)) or len(named) > 1:
        print(__doc__, file=sys.stderr)
        return 2

    main_checkout = main_checkout_of(repo)
    if main_checkout is None:
        print(f"clean-worktrees: {repo} is not a git repository", file=sys.stderr)
        return 2

    if named:
        return one_named_worktree_or_branch_exit_code(
            repo, main_checkout, named.get(REMOVE_WORKTREE_AND_FORCE_DELETE_ITS_BRANCH_COMMAND_LINE_FLAG),
            named.get(FORCE_DELETE_BRANCH_FLAG))

    try:
        failures = clean_worktrees_and_branch_refs(repo, main_checkout, remove, only_done)
    except git_output.GitCommandFailed as error:
        # The cause stays on one line: the handoff-supervisor reports this line alone.
        rerun = shlex.join([sys.executable, str(Path(__file__).resolve()), *given_arguments])
        removed = (WHAT_A_STOPPED_INVOCATION_REMOVED_WITH_REMOVE if remove
                   else WHAT_A_STOPPED_INVOCATION_REMOVED_WITHOUT_REMOVE)
        print(f"{STOPPED_LINE_START}{' '.join(str(error).split())}; {removed}\n"
              + next_step_lines.git_failure_next_step_lines(
                  rerun, text_the_failure_line_contains=STOPPED_LINE_START.strip()),
              file=sys.stderr)
        return 2

    # The handoff-supervisor records each agent-seat's first listings in its handoff directory.
    failures += work_snapshots.clean_leftover_work_snapshots(
        repo, remove=remove, only_due=only_done,
        handoff_directory=Path.home() / ".claude" / "handoffs")
    failures += close_restored_branch_tasks(repo, remove=remove, only_done=only_done)

    # Printed only by a run that got this far, so a reader can tell a finished run from one that aborted.
    if failures:
        print(FINISHED_WITH_FAILURES_LINE)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
