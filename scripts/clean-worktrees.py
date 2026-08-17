#!/usr/bin/env python3
"""Report or remove finished session worktrees under .claude/worktrees/.

Session worktrees pile up invisibly: every Claude session gets one, sessions
end, and nothing reaps them. A worktree is DONE — removable losing nothing —
only when three mechanical checks all pass:

  1. clean    - no uncommitted, untracked, or ignored files (`git status
                --porcelain --ignored` is empty). Ignored files count as dirt
                on purpose: machine-local state like a walk ledger or an
                identity file must never be reaped with its worktree. The one
                exception is regenerable junk every worktree accumulates —
                .DS_Store and __pycache__ — which counts as nothing (git
                worktree remove tolerates it, verified).
  2. landed   - no commits beyond origin/main (`git log origin/main..HEAD`
                is empty), so everything the worktree's branch carries is
                already on main. origin/main is read as fetched; a stale ref
                only errs toward keeping.
  3. vacant   - no live process has its working directory inside the
                worktree (lsof). An unreadable or ambiguous answer counts
                as occupied.

Anything that fails a check is KEPT, with the failing reason. Worktrees
outside <repo>/.claude/worktrees/ — agent seat homes, manual checkouts — are
always kept: their lifecycles belong to their owners, not to this script.

Modes:
  (default)    report every worktree, one line each
  --only-done  print only the done ones, nothing when there are none
               (the launchers run this at boot, so a reapable worktree is
               named at the moment someone is looking)
  --remove     re-check and remove the done worktrees; each removal also
               deletes the worktree's fully-merged branch (git branch -d,
               which refuses anything unmerged). Never --force.

Usage:
  scripts/clean-worktrees.py [--only-done | --remove] [--repo PATH]

Exit codes: 0 ok, 1 a removal failed, 2 bad invocation.
"""

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Ignored entries whose basename is one of these are regenerable junk, not
# state: they never block a removal. Everything else ignored is somebody's
# machine-local state and keeps the worktree.
DISPOSABLE_JUNK_BASENAMES = (".DS_Store", "__pycache__")


def run_git(repo, *arguments):
    return subprocess.run(
        ["git", "-C", str(repo), *arguments],
        capture_output=True, text=True, check=False,
    )


def main_checkout_of(repo):
    """The repository's primary checkout, regardless of which worktree this
    script's copy lives in — the parent of the common git directory."""
    common = run_git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if common.returncode != 0:
        return None
    return Path(common.stdout.strip()).parent


def list_worktrees(repo, main_checkout):
    """(path, branch-or-None) per worktree, the main checkout excluded."""
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


def occupied_by_processes(worktree):
    """True when any process has its cwd inside the worktree — or when the
    answer cannot be trusted, because ambiguity must keep, never reap."""
    if shutil.which("lsof") is None:
        return True
    try:
        cwd_listing = subprocess.run(
            ["lsof", "-a", "-d", "cwd", "-F", "n"],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return True
    prefix = str(worktree.resolve())
    for line in cwd_listing.stdout.splitlines():
        if line.startswith("n"):
            cwd = line[1:]
            if cwd == prefix or cwd.startswith(prefix + "/"):
                return True
    return False


def classify(worktree, branch, main_checkout):
    """Return (done: bool, reason: str) for one worktree."""
    managed_area = (main_checkout / ".claude" / "worktrees").resolve()
    if managed_area not in worktree.resolve().parents:
        return False, "outside the managed area (.claude/worktrees/) — its owner decides its lifecycle"

    status = run_git(worktree, "status", "--porcelain", "--ignored")
    if status.returncode != 0:
        return False, "git cannot read it (" + status.stderr.strip()[:80] + ")"
    dirt = [
        line for line in status.stdout.splitlines()
        if not (line.startswith("!!") and
                line[2:].strip().rstrip("/").rsplit("/", 1)[-1]
                in DISPOSABLE_JUNK_BASENAMES)
    ]
    if dirt:
        return False, f"{len(dirt)} uncommitted, untracked, or ignored file(s)"

    unlanded = run_git(worktree, "log", "--oneline", "origin/main..HEAD")
    if unlanded.returncode != 0:
        return False, "cannot compare against origin/main (" + unlanded.stderr.strip()[:80] + ")"
    if unlanded.stdout.strip():
        commits = len(unlanded.stdout.splitlines())
        return False, f"{commits} commit(s) not on origin/main"

    if occupied_by_processes(worktree):
        return False, "a live process is rooted inside it"

    return True, "clean, landed, and vacant"


def remove_worktree(worktree, branch, repo):
    """Remove one done worktree and its fully-merged branch. True on success."""
    removal = run_git(repo, "worktree", "remove", str(worktree))
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
        done, reason = classify(worktree, branch, main_checkout)
        if remove:
            if done and not remove_worktree(worktree, branch, repo):
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

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
