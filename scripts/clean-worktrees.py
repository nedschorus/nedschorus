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
                worktree (lsof). Vacancy must be proven, never assumed: if
                lsof is missing, cannot be run, exits nonzero, or reports no
                working directories at all, the worktree is kept and the
                reason says the check could not be trusted — it does not
                claim a process that was never seen.

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
docs/cross-project/fleet-git-worktree-working-model.md).

Modes:
  (default)    report every worktree, one line each
  --only-done  print only what needs someone's attention — done worktrees,
               the orphaned-branch-ref line, and the dead-registration line
               when there are any; nothing otherwise (the launchers run this
               at boot, so a reapable worktree, an orphaned branch ref or a
               dead registration is named at the moment someone is looking)
  --remove     re-check and remove the done worktrees; each removal also
               deletes the worktree's fully-merged branch (git branch -d,
               which refuses anything unmerged). Never --force. Orphaned
               branch refs are deleted the same way, and a refusal there is
               a failure rather than a silence.

Usage:
  scripts/clean-worktrees.py [--only-done | --remove] [--repo PATH]

Exit codes: 0 ok, 1 a removal or a ref deletion failed, 2 bad invocation.
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


def dead_worktree_registrations(repo):
    """(path, git's reason) for each registration `git worktree prune` would
    remove — typically because the worktree's directory is gone, which is what
    a temp-area clearing leaves behind.

    Deadness is git's own judgment, read from the `prunable` annotation of
    `git worktree list --porcelain` (git >= 2.36), never from a filesystem
    check of our own, and git's reason is carried rather than restated. The
    two are not the same claim: a directory that still exists but has lost
    its `.git` file is prunable too (verified, git 2.55.0), and pruning it
    discards the registration for a directory that may still hold someone's
    uncommitted work — so the reason the human reads must be the one git
    actually gave. A locked registration is never named, because prune skips
    it too."""
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
    """Local branch names that no worktree has checked out AND that carry
    nothing origin/main lacks — the refs removable losing nothing.

    Removing a worktree does not remove the branch it was on. Three mechanisms
    leave one behind: the Agent tool's worktree isolation, which creates a
    `worktree-agent-<id>` branch whose worktree is later reaped; a seat home
    retired by hand; and `git worktree remove` run directly. Counted on
    2026-08-31 with `git for-each-ref refs/heads/`, BEFORE a hand sweep that
    same night: 143 local branches, 81 of them landed orphans — every commit
    already on origin/main, no worktree, and nothing in this project reaping
    them. Those 81 were deleted by hand, along with 15 stale review refs, and
    the count of commits reachable from local branches but from no remote did
    not move (264 before, 264 after), which is what proved the 81 held nothing
    of their own.

    That is why counting again AFTER the sweep gives a different answer, and
    why a later reader should not read it as the first count being wrong: 51
    local branches remain, 41 with no worktree, and the landed-orphan
    population is momentarily ZERO because the hand sweep just took all of
    them. It does not stay zero. Each of the 41 becomes a landed ref the
    moment its work reaches main, and the reaper's own removals are the only
    thing that deletes a branch today — which is the whole reason this
    function exists rather than a second hand sweep six weeks from now.

    Orphaned refs that DO carry commits origin/main lacks are deliberately not
    reported: 41 of the 51 local branches left after the sweep were in that
    state. They are nobody's to delete on a boot-time report, and naming
    them every run is noise that teaches a reader to skip the line. Their
    disposal is a judgment, not a sweep.

    A branch is treated as attached when any worktree — the main checkout
    included — has it checked out, so a branch in use is never named. A
    detached worktree contributes no name, which is git's own answer: its
    porcelain record says `detached` where a branch line would be.

    Containment is git's answer too — a reachability question asked once for
    every ref, never inferred from a branch's name or from its upstream,
    which can be configured to a remote branch that no longer exists. Asking
    per branch with `rev-list` would instead cost one subprocess per branch
    on a path the launchers run at boot: 51 of them here. Either query
    failing yields nothing to report, so a repository this script cannot read
    loses no refs.
    """
    listing = run_git(repo, "worktree", "list", "--porcelain")
    if listing.returncode != 0:
        return []
    attached = {
        line.split("refs/heads/", 1)[1]
        for line in listing.stdout.splitlines()
        if line.startswith("branch refs/heads/")
    }
    # refs/heads/ scopes the question to local branches, so remote-tracking
    # refs are never candidates. lstrip=2 rather than :short because :short
    # answers `heads/<name>` for a branch that a tag of the same name shadows
    # (verified, git 2.55.0) — a name that matches nothing in `attached` and
    # that `git branch -d` cannot take, so an in-use branch would be named.
    landed = run_git(repo, "for-each-ref", "--format=%(refname:lstrip=2)",
                     "--merged", "origin/main", "refs/heads/")
    if landed.returncode != 0:
        return []
    return [branch for branch in landed.stdout.splitlines()
            if branch not in attached]


def delete_orphaned_branch_ref(branch, repo):
    """Delete one orphaned ref. True on success.

    `git branch -d` rather than `-D`, deliberately and for the same reason the
    worktree path uses it: the containment test above and git's own refusal are
    two independent answers to the same question, and a ref that only one of
    them clears is a ref this script does not delete.
    """
    deletion = run_git(repo, "branch", "-d", branch)
    if deletion.returncode != 0:
        print(f"branch {branch}: deletion FAILED — {deletion.stderr.strip()[:120]}")
        return False
    print(f"branch {branch}: deleted (no worktree, nothing beyond origin/main)")
    return True


def worktree_vacancy_keep_reason(worktree):
    """Why this worktree must be kept on the vacancy check, or None when it is
    provably vacant.

    Ambiguity must keep, never reap, so this answers with a reason rather than
    a bare boolean: a worktree kept because lsof could not be trusted has not
    been shown to hold a live process, and the report must not say it does.

    Vacancy is only ever proven by a usable listing that names no path inside
    the worktree. lsof missing, failing to launch, timing out, exiting
    nonzero, or returning a listing with no cwd paths at all are all
    unusable answers, and each keeps. A path match keeps regardless of how the
    run exited: a partial listing that names this worktree is still positive
    evidence of occupancy, and the pre-existing warnings lsof prints on both
    fleet machines (Time Machine snapshots on the Mac, docker overlayfs on the
    box) do not make a match less true.
    """
    if shutil.which("lsof") is None:
        return "lsof is not installed, so vacancy cannot be checked"
    try:
        cwd_listing = subprocess.run(
            ["lsof", "-a", "-d", "cwd", "-F", "n"],
            capture_output=True, text=True, timeout=30, check=False,
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
    # No match found — but only a usable listing can turn that into vacancy.
    # Both fleet machines exit 0 here in normal operation (measured
    # 2026-08-19: Mac 397 cwd paths, box 382, warnings on stderr, exit 0
    # both), so a nonzero exit or an empty listing is genuinely abnormal
    # rather than the everyday warning case.
    if cwd_listing.returncode != 0:
        return (f"the vacancy check (lsof) failed with exit "
                f"{cwd_listing.returncode}, so vacancy cannot be trusted")
    if reported_paths == 0:
        return "the vacancy check (lsof) reported no working directories at all"
    return None


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

    keep_reason = worktree_vacancy_keep_reason(worktree)
    if keep_reason is not None:
        return False, keep_reason

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
