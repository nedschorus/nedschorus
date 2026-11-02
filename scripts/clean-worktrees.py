#!/usr/bin/env python3
"""Report or remove the worktrees whose work is done, judged by each worktree's owner file.

WHICH WORKTREES. Every worktree of the clone except its main checkout, the
reference-checkout, wherever the worktree is. Only a worktree holding an owner
file can be removed: scripts/worktree-owner-file-read-and-write.py says where
the file is, what it holds, and when its owner, an agent-seat or an
agent-session, counts as running. A worktree is KEPT, with the reason, when:

  - it has no owner file, as agent-homes, merge-lane review checkouts and
    worktrees made by hand have, or its owner file cannot be read;
  - it is locked with `git worktree lock`, as Claude Code locks a subagent's
    worktree while the subagent runs;
  - git would prune it, its directory being gone;
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
  ended. The branch keeps its commits.

Ignored files do not keep a worktree. Before --remove removes one, it ships
each walk in the worktree's docs/walk/, one for each <name>-minutes.md there,
with scripts/walk-files-ship.py, given by its walk text <name>.md, or by its
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

BRANCHES. The cleaner deletes a local branch other than main whose commits
are all on origin/main and which no worktree has checked out, with
`git branch -d`, and no other branch: the removed worktree's branch when it
qualifies, and every other such branch, named on one line in the report
modes. origin/main is read as fetched; a stale ref only keeps more.

THE COUNT LINE. The report and --remove end their worktree lines with one
line of counts: worktrees kept, by reason; worktrees with no owner file;
local branches other than main with no pull request; and work-snapshots
still present. A second line names the kept worktrees owned by an agent-seat
whose handoff-supervisor is not running, when there are any.

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

It does not fetch; a stale origin/main only keeps more.

Usage:
  scripts/clean-worktrees.py [--only-done | --remove] [--repo PATH]

Exit codes: 0 ok, 1 a removal, a record's shipment, a branch or work-snapshot
made before a removal, a ref deletion, a line of the log of removals, or a
work-snapshot listing or deletion failed, 2 bad invocation, or git could not
list the worktrees or the branches, which stops the run where it failed.
"""

import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
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
    "failed_command_agent_facing_message_rerun_once_then_stop_and_report_lines_common",
    REPO_ROOT / "nc-systems" / "general-tools"
    / "failed-command-agent-facing-message-rerun-once-then-stop-and-report-lines-common.py")
next_step_lines = importlib.util.module_from_spec(_next_step_lines_spec)
_next_step_lines_spec.loader.exec_module(next_step_lines)

_mark_spec = importlib.util.spec_from_file_location(
    "handoff_user_review_of_agent_memory_stores_mark",
    REPO_ROOT / "nc-systems" / "handoff" / "handoff-user-review-of-agent-memory-stores-mark.py")
mark = importlib.util.module_from_spec(_mark_spec)
_mark_spec.loader.exec_module(mark)

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
WALK_FILES_SHIPPER = REPO_ROOT / "scripts" / "walk-files-ship.py"
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


def list_worktrees(repo, main_checkout):
    """Return (path, branch-or-None, git's record) for each worktree but the primary checkout;
    raise git_output.GitCommandFailed when git cannot list them."""
    listing = git_output.run_git(repo, ["worktree", "list", "--porcelain", "-z"])
    worktrees = []
    for record in git_output.worktree_records(listing):
        path = Path(record.path)
        if path.resolve() == main_checkout.resolve():
            continue
        branch = record.branch
        if branch is not None and branch.startswith("refs/heads/"):
            branch = branch[len("refs/heads/"):]
        else:
            branch = None
        worktrees.append((path, branch, record))
    return worktrees


def dead_worktree_registrations(repo):
    """Return (path, git reason) for unlocked prunable registrations; raise
    git_output.GitCommandFailed when git cannot list them."""
    # A prunable directory can still exist and hold work; report git's reason without inferring absence.
    listing = git_output.run_git(repo, ["worktree", "list", "--porcelain", "-z"])
    return [(record.path, record.prunable_reason or "no reason given")
            for record in git_output.worktree_records(listing)
            if record.prunable_reason is not None]


def branch_refs_with_no_worktree_fully_on_main(repo):
    """Return the local branches no worktree holds that carry nothing beyond origin/main;
    raise git_output.GitCommandFailed when git cannot list either."""
    listing = git_output.run_git(repo, ["worktree", "list", "--porcelain", "-z"])
    attached = {
        record.branch[len("refs/heads/"):]
        for record in git_output.worktree_records(listing)
        if record.branch is not None and record.branch.startswith("refs/heads/")
    }
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


def in_progress_git_operation_keep_reason(worktree):
    """Return why a worktree with a git operation stopped partway must be kept, or None."""
    arguments = ["rev-parse", "--path-format=absolute"]
    for file_name, _ in IN_PROGRESS_GIT_OPERATION_FILES:
        arguments += ["--git-path", file_name]
    located = run_git(worktree, *arguments)
    if located.returncode != 0:
        return (f"git cannot locate the files that show a rebase or merge in progress "
                f"({located.stderr.strip()[:80]})")
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
    status = run_git(worktree, "status", "--porcelain", "-z", "--untracked-files=all")
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
    status = run_git(worktree, "status", "--porcelain", "-z", "--ignored",
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
                     for name in walk_names for suffix, _ in walk_files_ship.WALK_FILE_ROLES}
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


def list_all_pull_requests_grouped_by_head_branch(repo):
    """Return {head branch name: [{number, state, headRefName, headRefOid}]} for every pull request
    of the repository's GitHub remote; raise PullRequestListingFailed when gh cannot list them."""
    command = ["gh", "pr", "list", "--state", "all", "--limit", str(PULL_REQUEST_LISTING_LIMIT),
               "--json", "number,state,headRefName,headRefOid"]
    try:
        listing = subprocess.run(command, cwd=repo, capture_output=True, text=True, check=False,
                                 timeout=PULL_REQUEST_LISTING_TIMEOUT_SECONDS)
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


def owner_text(owner):
    if owner["owner_kind"] == owner_file.OWNER_AGENT_SEAT:
        return f"the agent-seat {owner['agent_seat']}"
    return f"an agent-session of {owner['agent_seat']} (claude process {owner['owner_key']})"


def pull_request_text(pull_request):
    return f"pull request #{pull_request['number']} ({pull_request['state'].lower()})"


def classify(worktree, branch, record, pull_requests):
    """Return the Verdict for a worktree: whether its work is done, and why."""
    if record.locked_reason is not None:
        return Verdict(False, f"locked with git worktree lock "
                              f"({record.locked_reason or 'no reason given'})", KEPT_LOCKED)
    if record.prunable_reason is not None:
        return Verdict(False, f"git would prune its registration ({record.prunable_reason}); "
                              f"the dead registration line below names it", KEPT_NOT_CHECKABLE)
    try:
        owner = owner_file.worktree_owner_file_read(worktree)
    except owner_file.WorktreeOwnerFileError as error:
        return Verdict(False, f"its owner file could not be read: {error}", KEPT_NOT_CHECKABLE)
    if owner is None:
        return Verdict(False, "it has no owner file, and the cleaner removes only a worktree "
                              "holding one", KEPT_NO_OWNER_FILE)

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
                              if pull_request["state"] in ("MERGED", "CLOSED")
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
    records = log_store_records_in(worktree)
    if records:
        why += (f"; --remove first ships its {len(records)} record(s) to the log-store "
                f"and keeps it if one does not ship: "
                + ", ".join(str(record_path.relative_to(worktree)) for _, record_path in records))
    if discarded:
        why += (f"; removing it discards {len(discarded)} uncommitted, untracked or ignored "
                f"file(s): {discarded_files_text(discarded)}")
    return Verdict(True, why, "", owner, state, uncommitted, discarded, detached_commit,
                   record.head if running else None, branch if running else None)


def detached_commits_branch_name(worktree, commit):
    return DETACHED_COMMITS_BRANCH_NAME_TEMPLATE.format(worktree_name=worktree.name, commit=commit)


def fully_on_origin_main(repo, branch):
    """Whether every commit of the branch is on origin/main; False when git cannot say."""
    return run_git(repo, "merge-base", "--is-ancestor", f"refs/heads/{branch}",
                   "origin/main").returncode == 0


def keep_what_removal_would_lose(worktree, repo, verdict):
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
            print(WORKTREE_KEPT_AFTER_FAILURE_NEXT_REMOVE_RUN_RETRIES_LINE_TEMPLATE.format(name=worktree.name))
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
                            if outcome == "written" else None)
        except Exception as error:
            print(f"{worktree.name}: work-snapshot FAILED, worktree kept — its uncommitted and "
                  f"untracked files could not be copied: {type(error).__name__}: {error}")
            print(WORKTREE_KEPT_AFTER_FAILURE_NEXT_REMOVE_RUN_RETRIES_LINE_TEMPLATE.format(name=worktree.name))
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


def remove_worktree(worktree, branch, repo, verdict):
    """Ship its log-store records, keep what the removal would lose, then remove a done worktree
    and delete its branch when every commit of the branch is on origin/main; return False when
    something failed."""
    unshipped = ship_log_store_records(worktree)
    if unshipped:
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
        branch_read = run_git(worktree, "symbolic-ref", "--quiet", "--short", "HEAD")
        branch_now = branch_read.stdout.strip() if branch_read.returncode == 0 else None
        if head_now != verdict.judged_head or branch_now != verdict.judged_branch:
            print(f"{worktree.name}: kept — its owner, {owner_text(verdict.owner)}, runs, and the "
                  f"worktree's HEAD or branch changed during this run: it was {verdict.judged_head} "
                  f"on {verdict.judged_branch or 'no branch'}, the head commit of a merged or "
                  f"closed pull request, and is now {head_now} on {branch_now or 'no branch'}. "
                  f"A merged or closed pull request counts only for the commit at its head, on "
                  f"its branch. Nothing needs doing now: the next scripts/clean-worktrees.py "
                  f"--remove run, daily or at a handoff, judges the worktree again")
            return True
    elif not keep_what_removal_would_lose(worktree, repo, verdict):
        return False
    # Named before the removal too: a removal that fails or is killed partway may already have deleted some.
    discarded = verdict.discarded
    if discarded:
        print(f"{worktree.name}: removing it will discard {len(discarded)} uncommitted, "
              f"untracked or ignored file(s): {discarded_files_text(discarded)}")
    head = commit_of(worktree, "HEAD")
    # A single --force removes untracked and modified files but still refuses a locked worktree.
    removal = run_git(repo, "worktree", "remove", "--force", str(worktree))
    if removal.returncode != 0:
        print(f"{worktree.name}: removal FAILED — {removal.stderr.strip()[:120]}")
        return False
    line = f"{worktree.name}: removed"
    branch_deleted = False
    if branch and branch != MAIN_BRANCH:
        if not fully_on_origin_main(repo, branch):
            line += f", branch {branch} kept, since it holds commits origin/main lacks"
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
                                    "discarded-files": len(discarded)})]
    if branch_deleted:
        events.append(("deleted-branch", {"branch": branch, "commit": head}))
    return append_removed_worktree_or_deleted_branch_log_lines(events, repo, worktree.name)


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


def clean_worktrees_and_branch_refs(repo, main_checkout, remove, only_done):
    """Report or remove the worktrees and orphaned branch refs, and report dead registrations;
    return the number of failures, or raise git_output.GitCommandFailed when git cannot list them."""
    failures = 0
    pull_requests = PullRequestsByHeadBranchLazyCache(repo)
    kept_verdicts = []
    for worktree, branch, record in list_worktrees(repo, main_checkout):
        verdict = classify(worktree, branch, record, pull_requests)
        if not verdict.done:
            kept_verdicts.append((worktree, verdict))
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

    if not only_done:
        print_count_lines(repo, kept_verdicts, pull_requests)

    dead_registrations = dead_worktree_registrations(repo)
    if dead_registrations:
        print("dead registration(s) git would prune: "
              + ", ".join(f"{path} ({reason})" for path, reason in dead_registrations)
              + " — remove with: git worktree prune")

    return failures


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
    only_done = "--only-done" in arguments
    remove = "--remove" in arguments
    leftover = [a for a in arguments if a not in ("--only-done", "--remove")]
    if leftover or (only_done and remove):
        print(__doc__, file=sys.stderr)
        return 2

    main_checkout = main_checkout_of(repo)
    if main_checkout is None:
        print(f"clean-worktrees: {repo} is not a git repository", file=sys.stderr)
        return 2

    try:
        failures = clean_worktrees_and_branch_refs(repo, main_checkout, remove, only_done)
    except git_output.GitCommandFailed as error:
        # The cause stays on one line: the handoff-supervisor reports this line alone.
        rerun = shlex.join([sys.executable, str(Path(__file__).resolve()), *given_arguments])
        removed = (WHAT_A_STOPPED_INVOCATION_REMOVED_WITH_REMOVE if remove
                   else WHAT_A_STOPPED_INVOCATION_REMOVED_WITHOUT_REMOVE)
        print(f"{STOPPED_LINE_START}{' '.join(str(error).split())}; {removed}\n"
              + next_step_lines.git_failure_next_step_lines(
                  rerun, text_the_failure_line_contains=STOPPED_LINE_START.strip(),
                  include_the_misspelt_branch_commit_or_path_line=False),
              file=sys.stderr)
        return 2

    # The handoff-supervisor records each agent-seat's first listings in its handoff directory.
    failures += work_snapshots.clean_leftover_work_snapshots(
        repo, remove=remove, only_due=only_done,
        handoff_directory=Path.home() / ".claude" / "handoffs")

    # Printed only by a run that got this far, so a reader can tell a finished run from one that aborted.
    if failures:
        print(FINISHED_WITH_FAILURES_LINE)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
