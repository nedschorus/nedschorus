#!/usr/bin/env python3
"""Report or remove finished session worktrees under .claude/worktrees/, and finished
topic-worktrees beside the agent-homes in ~/agents/.

Session worktrees pile up invisibly: every Claude session gets one, sessions
end, and nothing reaps them. A worktree is DONE — removable — when these
mechanical checks all pass:

  0. at rest  - no rebase, merge, cherry-pick or revert is in progress in
                it: its git directory holds none of rebase-merge,
                rebase-apply, MERGE_HEAD, CHERRY_PICK_HEAD and REVERT_HEAD.
                Mid-rebase, HEAD is detached at a commit already on
                origin/main, so the landed check alone reads the work as
                finished. If git cannot locate those files, the worktree is
                kept.
  1. landed   - no commits beyond origin/main (`git log origin/main..HEAD`
                is empty, and git exits 0), so everything the worktree's
                branch carries is already on main. origin/main is read as
                fetched; a stale ref only errs toward keeping. If
                origin/main is missing or git cannot compare, the worktree
                is kept and the reason says so.
  2. vacant   - no live process has its working directory inside the
                worktree (lsof). Vacancy must be proven, never assumed: if
                lsof is missing, cannot be run, times out, exits nonzero, or
                reports no working directories at all, the worktree is kept
                and the reason says the check could not be trusted — it does
                not claim a process that was never seen.
  3. quiet    - for a worktree the Agent tool made for a subagent
                (`agent-<id>`), neither the subagent's transcript nor the
                worktree itself was written in the last
                AGENT_WORKTREE_QUIET_SECONDS. The vacancy check cannot see
                such a subagent: it runs inside its parent `claude` process,
                whose working directory stays the seat home, and only the
                short-lived shell of each Bash call sits in the worktree. The
                subagent's transcript, written on every message, is the one
                trace of it that lives outside a process.

Uncommitted, untracked and ignored files do NOT keep a done worktree: they
are removed with it. The one exception is the records whose home is the
log-store: before --remove removes a done worktree, it ships each non-empty
record directory under the worktree's cold-read-records/ and
sanity-check-records/ to the log-store, with the shipper of that kind
(LOG_STORE_RECORD_SHIPPERS), and keeps the worktree when any record is
refused or fails to ship, printing the shipper's line. The shippers are
add-only, so a record already in the store ships as "nothing new". The report
modes name the records and ship nothing. The files are listed after the other checks, each file
inside an untracked or ignored directory named on its own; the report names
them, and --remove names them twice: before each removal, as files it will
discard, and after a removal succeeds, as files discarded with it. A removal
that fails or is stopped partway has named its files beforehand, so a loss
is visible in the output either way. Regenerable junk
(.DS_Store, __pycache__, at any depth) is not listed. If git cannot list a
worktree's files, the worktree is kept.

Anything that fails a check is KEPT, with the failing reason.

TOPIC-WORKTREES BESIDE THE AGENT-HOMES. A worktree directly in ~/agents/ of
the machine it runs on (the home directory's agents/, read from HOME) is
judged too, when its directory name is an agent-home's name followed by a
hyphen and more, such as cold-read-improvement-claude-md-batching-sentence,
and it is no agent-home itself. An agent-home here is a worktree directly
in ~/agents/ that is on a branch named like its directory or holds a
seat-brief (CLAUDE.local.md); the seat-brief keeps an agent-home checked
out on another branch from being judged. Such a
topic-worktree passes the four checks above and four more, each of which
keeps it:

  4. clean    - no uncommitted change and no untracked file (ignored files
                do not count). Unlike a worktree under .claude/worktrees/,
                such files keep it: an agent-seat may still want them.
                --remove checks this again just before the removal, after
                the slow checks and the shipments, so a file written while
                they ran keeps the worktree.
  5. on a branch - its HEAD is not detached.
  6. quiet    - no file or directory in it was written in the last
                TOPIC_WORKTREE_QUIET_SECONDS. An agent-seat working there
                runs from its agent-home, so the vacancy check cannot see it.
                If a time cannot be read, the worktree is kept.
  7. walks shipped - before --remove removes it, each walk in its
                docs/walk/ (each <name>-minutes.md names one) is shipped to
                the log-store with scripts/walk-files-ship.py, as the
                records are, and a walk that is refused or fails to ship
                keeps the worktree, printed as a record that did not ship.

Every other worktree outside <repo>/.claude/worktrees/ — the agent-homes, the
reference-checkout, a worktree deeper in ~/agents/, such as one under
~/agents/agent-instructions-editor-worktrees/, the merge-lane's review
checkouts — is always kept: its lifecycle belongs to its
owner, not to this script.

Removing a worktree does not remove the branch it was on, and nothing has
ever swept a branch whose worktree is already gone — list_worktrees()
enumerates worktrees, not refs. So the report also carries one line naming
every local branch that no worktree has checked out and that carries nothing
origin/main lacks: the refs removable losing nothing. Orphaned refs that DO
carry commits origin/main lacks are deliberately NOT named — 41 of the 51
local branches left after 2026-08-31's hand sweep were in that state. Their
disposal is a judgment rather than a sweep, and printing them at every boot
teaches a reader to skip the line. The line prints in every mode; --remove
deletes the refs it names.

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
  (default)    report every worktree, one line each
  --only-done  print only what needs someone's attention — done worktrees,
               the orphaned-branch-ref line, and the dead-registration line
               when there are any; nothing otherwise (the launchers run this
               at boot, so a reapable worktree, an orphaned branch ref or a
               dead registration is named at the moment someone is looking)
  --remove     check each worktree and, when it is done, remove it at once;
               each removal also deletes the worktree's fully-merged branch
               (git branch -d, which refuses anything unmerged). Removal is
               `git worktree remove --force`, which removes untracked and
               modified files and still refuses a locked worktree. Before
               the removal it ships the worktree's cold-read-records and
               sanity-check records to the log-store, and keeps the
               worktree when one does not ship. Orphaned branch refs are deleted the same way, and
               a refusal there is a failure rather than a silence.

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
line is appended locally, on the Mac over ssh, with the helper the
log-store's other writers share. When a line cannot be written, the run
prints it with the cause on a line containing FAILED, carries on removing,
and exits 1 at the end. The environment variable
CLEAN_WORKTREES_REMOVED_WORKTREES_AND_DELETED_BRANCHES_LOG_FILE_OVERRIDE names
a local file to append to instead, which is how the tests keep out of the
log-store.

SCHEDULED. --remove runs once a day on both machines, from the reference
clone, so worktrees that sessions and subagents leave behind do not pile up
between handoffs. The job is declared in
nc-systems/general-tools/scheduled-jobs-on-each-machine.json and installed
with nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py: on
the Mac a launchd job at 06:30, so a run missed while the Mac sleeps starts at
the next wake; on ned-box the cron line

    30 6 * * * /usr/bin/python3 /home/nedlern/Projects/nedschorus/scripts/clean-worktrees.py --remove >> /home/nedlern/.claude/clean-worktrees.log 2>&1

It does not fetch; a stale origin/main only keeps more. A worktree still
locked by the claude process that made it fails to remove and is tried again
the next day.

Usage:
  scripts/clean-worktrees.py [--only-done | --remove] [--repo PATH]

Exit codes: 0 ok, 1 a removal, a record's shipment, a ref deletion, a line
of the log of removals, or a work-snapshot listing or deletion failed, 2 bad invocation, or git could not
list the worktrees or the branches, which stops the run where it failed.
"""

import importlib.util
import os
import shlex
import shutil
import subprocess
import sys
import time
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
# printf's own escape, so the command it starts stays on one line.
PRINTF_EACH_ARGUMENT_ON_ITS_OWN_LINE = r"%s\n"

# Regenerable junk is left out of the list of files a removal discards.
DISPOSABLE_JUNK_BASENAMES = (".DS_Store", "__pycache__")

DISCARDED_FILES_NAMED_AT_MOST = 10

# A topic-worktree's agent-seat runs from its agent-home, out of lsof's sight; a few hours without a
# write is the evidence it has finished there.
TOPIC_WORKTREE_QUIET_SECONDS = 4 * 3600

# The reference clone's walk shipper, given the path of one walk's minutes, ships that walk.
WALK_FILES_SHIPPER = REPO_ROOT / "scripts" / "walk-files-ship.py"
WALK_MINUTES_SUFFIX = "-minutes.md"

# Marks a directory in ~/agents/ as an agent-home whatever branch it is on.
SEAT_BRIEF_FILE_NAME = "CLAUDE.local.md"

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

# An isolated subagent's cwd may remain outside its worktree between tool calls.
# Require transcript and .git quiet time as well as the process vacancy check.
AGENT_WORKTREE_QUIET_SECONDS = 3600
AGENT_WORKTREE_NAME_PREFIX = "agent-"


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
    """Return (path, branch-or-None) pairs excluding the primary checkout; raise
    git_output.GitCommandFailed when git cannot list them."""
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
        worktrees.append((path, branch))
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
            if branch not in attached]


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
        print(f"{name}: log of removals line(s) FAILED to be written to {place} — {error}. "
              f"The removal or branch deletion named above stands, but no file outside this "
              f"run's output records it.\n"
              f"{name}: to record it, run this once: "
              f"{shlex.join(['printf', PRINTF_EACH_ARGUMENT_ON_ITS_OWN_LINE, *text.splitlines()])} | "
              f"{shlex.join(writer)}\n"
              f"{name}: if that printf command fails too, do not run scripts/clean-worktrees.py "
              f"again; tell the user that scripts/clean-worktrees.py on {machine} could not write "
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


def claude_projects_directory():
    configured = os.environ.get("CLAUDE_CONFIG_DIR")
    base = Path(configured) if configured else Path.home() / ".claude"
    return base / "projects"


def agent_worktree_quiet_keep_reason(worktree, now=None):
    """Return why a subagent worktree must be kept, or None after sufficient quiet."""
    # The .git timestamp covers new or pruned transcripts; unreadable times cannot prove quiet.
    if not worktree.name.startswith(AGENT_WORKTREE_NAME_PREFIX):
        return None
    agent_id = worktree.name[len(AGENT_WORKTREE_NAME_PREFIX):]
    now = time.time() if now is None else now
    written = []
    try:
        written.append((worktree / ".git").stat().st_mtime)
        for transcript in claude_projects_directory().glob(
                f"*/*/subagents/agent-{agent_id}.jsonl"):
            written.append(transcript.stat().st_mtime)
    except OSError as error:
        return f"its subagent's activity could not be read ({error.strerror})"
    quiet_seconds = now - max(written)
    if quiet_seconds < AGENT_WORKTREE_QUIET_SECONDS:
        return (f"its Agent-tool subagent or the worktree was written "
                f"{int(quiet_seconds // 60)} min ago, so the subagent may still be "
                f"working in it (quiet for {AGENT_WORKTREE_QUIET_SECONDS // 60} min "
                f"before removal)")
    return None


def is_agent_home(path, branch):
    # An agent-seat may check its agent-home out on another branch, as ned-box-helper does, so the
    # branch alone cannot tell an agent-home from a topic-worktree.
    return branch == path.name or (path / SEAT_BRIEF_FILE_NAME).exists()


def topic_worktrees_beside_agent_homes(worktrees):
    """Return the resolved paths of the topic-worktrees directly in ~/agents/ that this script judges."""
    agents_directory = (Path.home() / "agents").resolve()
    in_agents_directory = [(path.resolve(), branch) for path, branch in worktrees
                           if path.resolve().parent == agents_directory]
    agent_home_names = {path.name for path, branch in in_agents_directory
                        if is_agent_home(path, branch)}
    return {path for path, branch in in_agents_directory
            if path.name not in agent_home_names and branch not in agent_home_names
            and any(path.name.startswith(f"{home}-") for home in agent_home_names)}


def raise_error(error):
    raise error


def topic_worktree_quiet_keep_reason(worktree, now=None):
    """Return why a topic-worktree written too recently must be kept, or None after sufficient quiet."""
    now = time.time() if now is None else now
    try:
        newest = worktree.lstat().st_mtime
        # os.walk ignores unreadable directories unless told to raise, and an unread time cannot prove quiet.
        for directory, subdirectories, files in os.walk(worktree, onerror=raise_error):
            for name in subdirectories + files:
                newest = max(newest, os.lstat(os.path.join(directory, name)).st_mtime)
    except OSError as error:
        return f"when its files were last written could not be read ({error.strerror})"
    quiet_seconds = now - newest
    if quiet_seconds < TOPIC_WORKTREE_QUIET_SECONDS:
        return (f"a file in it was written {int(quiet_seconds // 60)} min ago, so an agent-seat "
                f"may still be working in it from its agent-home, where the vacancy check cannot "
                f"see it (quiet for {TOPIC_WORKTREE_QUIET_SECONDS // 3600} h before removal)")
    return None


def topic_worktree_keep_reason(worktree, branch):
    """Return why a landed topic-worktree must be kept before the vacancy check, or None."""
    if branch is None:
        return "its HEAD is detached, so its owner may be partway through a rebase or a bisect"
    return (topic_worktree_uncommitted_files_keep_reason(worktree)
            or topic_worktree_quiet_keep_reason(worktree))


def topic_worktree_uncommitted_files_keep_reason(worktree):
    """Return why a topic-worktree holding uncommitted or untracked files must be kept, or None."""
    status = run_git(worktree, "status", "--porcelain", "-z", "--untracked-files=all")
    if status.returncode != 0:
        return f"git cannot list its uncommitted changes ({status.stderr.strip()[:80]})"
    changed = [entry.path for entry in git_output.status_entries(status.stdout)
               if not is_disposable_junk(entry.path)]
    if changed:
        return (f"{len(changed)} uncommitted or untracked file(s), which only its owner "
                f"may discard: {discarded_files_text(changed)}")
    return None


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


def log_store_records_in(worktree, topic_worktree):
    """Return (shipper, path to ship) for each non-empty record directory the worktree holds and,
    in a topic-worktree, for the minutes file of each walk in its docs/walk/."""
    records = []
    if topic_worktree:
        records.extend((WALK_FILES_SHIPPER, minutes)
                       for minutes in sorted((worktree / "docs" / "walk").glob(f"*{WALK_MINUTES_SUFFIX}")))
    for directory_name, shipper in LOG_STORE_RECORD_SHIPPERS:
        records_directory = worktree / directory_name
        if not records_directory.is_dir():
            continue
        for record in sorted(records_directory.iterdir()):
            if record.is_dir() and any(record.iterdir()):
                records.append((shipper, record))
    return records


def ship_log_store_records(worktree, topic_worktree):
    """Ship every record the worktree holds, printing a line for each; return (shipper, line) for
    each that did not ship."""
    unshipped = []
    for shipper, record in log_store_records_in(worktree, topic_worktree):
        shipment = subprocess.run([sys.executable, str(shipper), str(record)],
                                  capture_output=True, text=True, check=False)
        sys.stderr.write(shipment.stderr)
        # One record directory, so the shipper prints at most one line.
        line = shipment.stdout.strip()
        if not line:
            last_error = shipment.stderr.strip().splitlines()[-1:]
            line = (f"the shipper printed nothing (exit {shipment.returncode})"
                    + (f": {last_error[0]}" if last_error else ""))
        if shipment.returncode:
            # Printed now, not after the loop: a later shipment can hang until the handoff's timeout kills this run.
            # The shipper's line appears only inside this FAILED line, so a reader counts it once.
            print(f"{worktree.name}: record shipment FAILED, worktree kept — removing it would delete "
                  f"a record the log-store does not hold: {record.relative_to(worktree)} ({line})")
            unshipped.append((shipper, line))
        else:
            print(f"{worktree.name}: {line}")
    return unshipped


def classify(worktree, branch, main_checkout, topic_worktree):
    """Return (done, reason, discarded paths) for a worktree."""
    managed_area = (main_checkout / ".claude" / "worktrees").resolve()
    if not topic_worktree and managed_area not in worktree.resolve().parents:
        return False, "outside the managed area (.claude/worktrees/) — its owner decides its lifecycle", []

    keep_reason = in_progress_git_operation_keep_reason(worktree)
    if keep_reason is not None:
        return False, keep_reason, []

    unlanded = run_git(worktree, "log", "--oneline", "origin/main..HEAD")
    if unlanded.returncode != 0:
        return False, "cannot compare against origin/main (" + unlanded.stderr.strip()[:80] + ")", []
    if unlanded.stdout.strip():
        commits = len(unlanded.stdout.splitlines())
        return False, f"{commits} commit(s) not on origin/main", []

    # Before the vacancy check, which scans every process and is the slowest.
    if topic_worktree:
        keep_reason = topic_worktree_keep_reason(worktree, branch)
        if keep_reason is not None:
            return False, keep_reason, []

    keep_reason = worktree_vacancy_keep_reason(worktree)
    if keep_reason is not None:
        return False, keep_reason, []

    keep_reason = agent_worktree_quiet_keep_reason(worktree)
    if keep_reason is not None:
        return False, keep_reason, []

    # Listed last, after the slow vacancy check, so the list is as close to the removal as it can be.
    discarded, listing_error = files_a_removal_discards(worktree)
    if discarded is None:
        return False, f"git cannot list its files ({listing_error})", []
    records = log_store_records_in(worktree, topic_worktree)
    shipped_first = (f"; --remove first ships its {len(records)} record(s) to the log-store "
                     f"and keeps it if one does not ship: "
                     + ", ".join(str(record.relative_to(worktree)) for _, record in records)
                     if records else "")
    if discarded:
        return True, (f"landed and vacant; removing it discards {len(discarded)} "
                      f"uncommitted, untracked or ignored file(s): "
                      f"{discarded_files_text(discarded)}{shipped_first}"), discarded
    return True, "landed and vacant" + shipped_first, []


def remove_worktree(worktree, branch, repo, discarded, topic_worktree):
    """Ship its log-store records, then remove a done worktree and its merged branch; return False
    when something failed."""
    unshipped = ship_log_store_records(worktree, topic_worktree)
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
    # classify() judged it clean before the slow vacancy check and the shipments; an agent may have written since.
    if topic_worktree:
        keep_reason = topic_worktree_uncommitted_files_keep_reason(worktree)
        if keep_reason is not None:
            print(f"{worktree.name}: kept — {keep_reason}")
            return True
    # Named before the removal too: a removal that fails or is killed partway may already have deleted some.
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
    if branch:
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


def clean_worktrees_and_branch_refs(repo, main_checkout, remove, only_done):
    """Report or remove the worktrees and orphaned branch refs, and report dead registrations;
    return the number of failures, or raise git_output.GitCommandFailed when git cannot list them."""
    failures = 0
    worktrees = list_worktrees(repo, main_checkout)
    topic_worktrees = topic_worktrees_beside_agent_homes(worktrees)
    for worktree, branch in worktrees:
        topic_worktree = worktree.resolve() in topic_worktrees
        done, reason, discarded = classify(worktree, branch, main_checkout, topic_worktree)
        if remove:
            if done and not remove_worktree(worktree, branch, repo, discarded, topic_worktree):
                failures += 1
            elif not done:
                print(f"{worktree.name}: kept — {reason}")
        elif only_done:
            if done:
                print(f"{worktree.name}: done ({reason}) — remove with "
                      f"scripts/clean-worktrees.py --remove")
        else:
            state = "done" if done else "kept"
            print(f"{worktree.name}: {state} — {reason}")

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
