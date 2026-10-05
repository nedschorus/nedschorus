#!/usr/bin/env python3
"""Report or remove finished session worktrees under .claude/worktrees/.

Session worktrees pile up invisibly: every Claude session gets one, sessions
end, and nothing reaps them. A worktree is DONE — removable — when these
mechanical checks all pass:

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
are removed with it. The files are listed after the other checks, each file
inside an untracked or ignored directory named on its own; the report names
them, and --remove names them twice: before each removal, as files it will
discard, and after a removal succeeds, as files discarded with it. A removal
that fails or is stopped partway has named its files beforehand, so a loss
is visible in the output either way. Regenerable junk
(.DS_Store, __pycache__, at any depth) is not listed. If git cannot list a
worktree's files, the worktree is kept.

Anything that fails a check is KEPT, with the failing reason. Worktrees
outside <repo>/.claude/worktrees/ — agent seat homes, manual checkouts — are
always kept: their lifecycles belong to their owners, not to this script.

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
               modified files and still refuses a locked worktree. Orphaned branch refs are deleted the same way, and
               a refusal there is a failure rather than a silence.

SCHEDULED. --remove runs once a day on both machines, from the reference
clone, so worktrees that sessions and subagents leave behind do not pile up
between handoffs. The job is declared in
nc-systems/general-tools/scheduled-jobs-on-each-machine.json and installed
with nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py: on
the Mac a launchd job at 06:30, so a run missed while the Mac sleeps starts at
the next wake; on ned-box the cron line

    30 6 * * * /usr/bin/python3 /home/nedlern/Projects/nedschorus/scripts/clean-worktrees.py --remove >> /home/nedlern/.claude/daily-clean-worktrees.log 2>&1

It does not fetch; a stale origin/main only keeps more. A worktree still
locked by the claude process that made it fails to remove and is tried again
the next day.

Usage:
  scripts/clean-worktrees.py [--only-done | --remove] [--repo PATH]

Exit codes: 0 ok, 1 a removal or a ref deletion failed, 2 bad invocation.
"""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Regenerable junk is left out of the list of files a removal discards.
DISPOSABLE_JUNK_BASENAMES = (".DS_Store", "__pycache__")

DISCARDED_FILES_NAMED_AT_MOST = 10

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


def main_checkout_of(repo):
    """Return the primary checkout from the common git directory."""
    common = run_git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if common.returncode != 0:
        return None
    return Path(common.stdout.strip()).parent


def list_worktrees(repo, main_checkout):
    """Return (path, branch-or-None) pairs excluding the primary checkout."""
    listing = run_git(repo, "worktree", "list", "--porcelain")
    worktrees = []
    path, branch = None, None
    for line in listing.stdout.splitlines() + [""]:
        if line.startswith("worktree "):
            path = Path(line.split(" ", 1)[1])
        elif line.startswith("branch refs/heads/"):
            branch = line.split("refs/heads/", 1)[1]
        elif not line:
            if path is not None and path.resolve() != main_checkout.resolve():
                worktrees.append((path, branch))
            path, branch = None, None
    return worktrees


def dead_worktree_registrations(repo):
    """Return (path, git reason) for unlocked prunable registrations."""
    # A prunable directory can still exist and hold work; report git's reason without inferring absence.
    listing = run_git(repo, "worktree", "list", "--porcelain")
    dead = []
    path = None
    for line in listing.stdout.splitlines():
        if line.startswith("worktree "):
            path = line.split(" ", 1)[1]
        elif (line == "prunable" or line.startswith("prunable ")) and path:
            reason = line[len("prunable"):].strip() or "no reason given"
            dead.append((path, reason))
            path = None
    return dead


def branch_refs_with_no_worktree_fully_on_main(repo):
    listing = run_git(repo, "worktree", "list", "--porcelain")
    if listing.returncode != 0:
        return []
    attached = {
        line.split("refs/heads/", 1)[1]
        for line in listing.stdout.splitlines()
        if line.startswith("branch refs/heads/")
    }
    # Use lstrip=2: :short can return heads/<name> when a same-named tag shadows a branch.
    landed = run_git(repo, "for-each-ref", "--format=%(refname:lstrip=2)",
                     "--merged", "origin/main", "refs/heads/")
    if landed.returncode != 0:
        return []
    return [branch for branch in landed.stdout.splitlines()
            if branch not in attached]


def delete_orphaned_branch_ref(branch, repo):
    """Delete a ref and return whether git accepted the deletion."""
    # Keep -d: git's merged-branch check is independent of our containment test.
    deletion = run_git(repo, "branch", "-d", branch)
    if deletion.returncode != 0:
        print(f"branch {branch}: deletion FAILED — {deletion.stderr.strip()[:120]}")
        return False
    print(f"branch {branch}: deleted (no worktree, nothing beyond origin/main)")
    return True


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
    fields = iter([field for field in status.stdout.split("\0") if field])
    paths = []
    for entry in fields:
        code, path = entry[:2], entry[3:]
        # A rename or copy, in the index column or the worktree column, carries its old path as the next field.
        if "R" in code or "C" in code:
            next(fields, None)
        paths.append(path)
    return [path for path in paths if not is_disposable_junk(path)], None


def discarded_files_text(paths):
    named = ", ".join(paths[:DISCARDED_FILES_NAMED_AT_MOST])
    more = len(paths) - DISCARDED_FILES_NAMED_AT_MOST
    return named + (f" and {more} more" if more > 0 else "")


def classify(worktree, branch, main_checkout):
    """Return (done, reason, discarded paths) for a worktree."""
    managed_area = (main_checkout / ".claude" / "worktrees").resolve()
    if managed_area not in worktree.resolve().parents:
        return False, "outside the managed area (.claude/worktrees/) — its owner decides its lifecycle", []

    unlanded = run_git(worktree, "log", "--oneline", "origin/main..HEAD")
    if unlanded.returncode != 0:
        return False, "cannot compare against origin/main (" + unlanded.stderr.strip()[:80] + ")", []
    if unlanded.stdout.strip():
        commits = len(unlanded.stdout.splitlines())
        return False, f"{commits} commit(s) not on origin/main", []

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
    if discarded:
        return True, (f"landed and vacant; removing it discards {len(discarded)} "
                      f"uncommitted, untracked or ignored file(s): "
                      f"{discarded_files_text(discarded)}"), discarded
    return True, "landed and vacant", []


def remove_worktree(worktree, branch, repo, discarded):
    """Remove a done worktree and its merged branch; return success."""
    # Named before the removal too: a removal that fails or is killed partway may already have deleted some.
    if discarded:
        print(f"{worktree.name}: removing it will discard {len(discarded)} uncommitted, "
              f"untracked or ignored file(s): {discarded_files_text(discarded)}")
    # A single --force removes untracked and modified files but still refuses a locked worktree.
    removal = run_git(repo, "worktree", "remove", "--force", str(worktree))
    if removal.returncode != 0:
        print(f"{worktree.name}: removal FAILED — {removal.stderr.strip()[:120]}")
        return False
    line = f"{worktree.name}: removed"
    if branch:
        branch_deletion = run_git(repo, "branch", "-d", branch)
        if branch_deletion.returncode == 0:
            line += f", branch {branch} deleted"
        else:
            line += f", branch {branch} left in place (git branch -d refused)"
    print(line)
    if discarded:
        print(f"{worktree.name}: discarded with it {len(discarded)} uncommitted, untracked "
              f"or ignored file(s): {discarded_files_text(discarded)}")
    return True


def main(argv=None):
    arguments = sys.argv[1:] if argv is None else list(argv)
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

    failures = 0
    for worktree, branch in list_worktrees(repo, main_checkout):
        done, reason, discarded = classify(worktree, branch, main_checkout)
        if remove:
            if done and not remove_worktree(worktree, branch, repo, discarded):
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

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
