#!/usr/bin/env python3
"""Save each agent-home's seat-branch commits to a pushed branch, then rest the agent-home
detached at origin/main and mark it as an agent-home.

Usage, on the machine whose agent-homes it moves, from any checkout of the repository:
  python3 scripts/agent-home-seat-branch-commits-save-to-pushed-branch-and-detach-at-origin-main.py
      [--agents-root PATH] [--handoff-directory PATH]

Which agent-homes: each directory directly under the agents root that is a git checkout and is
either an agent-seat, as scripts/recover-crashed-seats.py lists them (a handoff-supervisor state
file or a session-handoff file in the handoff directory), or on the branch named for it, which
is how a seat-branch was made. The agents root and the handoff directory default to the ones
scripts/recover-crashed-seats.py uses on this machine.

For each agent-home, in order:
  1. fetches origin, pruning the remote-tracking refs of branches origin no longer has;
  2. when the local branch named for the agent-seat, its seat-branch, holds commits origin/main
     lacks and some of them are on no branch on origin, pushes its tip to origin as
     <agent-seat>-seat-branch-commits-saved-<YYYY-MM-DD>, with -2, -3 and so on added when a
     local branch or a branch on origin already has that name. The push skips the clone's
     pre-push hook, whose conflict check would refuse a stale seat-branch: the pushed branch is
     a record, never a pull request's head;
  3. leaves the agent-home as it is, and says why, when a git operation that
     scripts/checkout-freshness-catch-up.py knows is in progress there,
     when `git status` lists any change, untracked files included, or when its HEAD is detached
     and holds commits no branch or remote branch holds;
  4. otherwise writes the file agent-home-marker into the agent-home's own git directory, which
     makes scripts/git-client-side-hooks/pre-commit refuse commits in it, then runs
     `git checkout --detach origin/main` there. The detach comes last so that, when either
     fails, the agent-home is still on the branch it was on, so a rerun finds it as this run
     did and finishes.
It deletes nothing: the seat-branch, any other branch the agent-home was on, and every untracked
or ignored file stay. It prints one line per agent-home, and with it the branch a step 2 pushed,
or a branch other than the seat-branch that the agent-home was on, holds commits origin/main
lacks and no branch on origin holds.

What it does not handle: an agent-home whose agent-session is running is moved under it, as the
freshness hook moves a detached checkout; the agent-session's CLAUDE.md and skills may then be
out of date until it reads them again. A seat-branch whose commits are all on a branch on
origin already is not pushed again, so running it twice pushes nothing new.

How it fails: a git step that fails is printed with git's error and the agent-home is left as
that step found it, apart from a marker step 4 wrote before its detach failed; a failed push
leaves the agent-home unmoved. The other agent-homes are still handled. Exit status: 0 when every agent-home now rests detached at origin/main and is marked; 1
when any was left or a step failed; 2 when the agent-homes could not be listed.
"""

import argparse
import datetime
import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_freshness_spec = importlib.util.spec_from_file_location(
    "checkout_freshness_catch_up", REPO_ROOT / "scripts" / "checkout-freshness-catch-up.py")
freshness = importlib.util.module_from_spec(_freshness_spec)
_freshness_spec.loader.exec_module(freshness)
AGENT_HOME_MARKER_NAME = "agent-home-marker"
SAVED_BRANCH_SUFFIX = "-seat-branch-commits-saved-"
GIT_TIMEOUT_SECONDS = 120


class GitStepFailed(Exception):
    pass


def git(directory: Path, *arguments, accepted=(0,)) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(["git", "-C", str(directory), *arguments], capture_output=True,
                                text=True, stdin=subprocess.DEVNULL, timeout=GIT_TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise GitStepFailed(f"git {' '.join(arguments)} in {directory} did not run: {error}")
    if result.returncode not in accepted:
        raise GitStepFailed(f"git {' '.join(arguments)} in {directory} exited "
                            f"{result.returncode}: {result.stderr.strip() or 'no error printed'}")
    return result


def output(directory: Path, *arguments, accepted=(0,)) -> str:
    return git(directory, *arguments, accepted=accepted).stdout.strip()


def ref_exists(directory: Path, ref: str) -> bool:
    # --verify --quiet exits 1 for a name that does not exist.
    return git(directory, "rev-parse", "--verify", "--quiet", ref, accepted=(0, 1)).returncode == 0


def current_branch(directory: Path) -> str:
    """The checked-out branch's name, or "" on a detached HEAD."""
    # symbolic-ref -q exits 1 on a detached HEAD.
    return output(directory, "symbolic-ref", "-q", "--short", "HEAD", accepted=(0, 1))


def is_checkout(directory: Path) -> bool:
    # rev-parse exits 128 outside a git checkout; git raises GitStepFailed when it cannot run.
    top = git(directory, "rev-parse", "--show-toplevel", accepted=(0, 128))
    return top.returncode == 0 and Path(top.stdout.strip()).resolve() == directory.resolve()


def list_agent_homes(agents_root: Path, agent_seat_names) -> list:
    homes = []
    if not agents_root.is_dir():
        return homes
    for entry in sorted(agents_root.iterdir()):
        if not entry.is_dir() or not is_checkout(entry):
            continue
        if entry.name in agent_seat_names or current_branch(entry) == entry.name:
            homes.append(entry)
    return homes


def free_saved_branch_name(home: Path, seat: str, today: datetime.date) -> str:
    base = f"{seat}{SAVED_BRANCH_SUFFIX}{today.isoformat()}"
    name, suffix = base, 1
    while ref_exists(home, f"refs/heads/{name}") or ref_exists(home, f"refs/remotes/origin/{name}"):
        suffix += 1
        name = f"{base}-{suffix}"
    return name


def commits_on_no_origin_branch(home: Path, ref: str) -> int:
    # Only origin's remote-tracking refs are pruned by the fetch; another remote's may be stale.
    return len(output(home, "rev-list", ref, "--not", "--remotes=origin").split())


def save_seat_branch(home: Path, seat: str, today: datetime.date) -> str:
    """Push the seat-branch's tip when it holds commits origin/main lacks and some are on no
    branch on origin; return what was done, as part of the agent-home's line."""
    seat_ref = f"refs/heads/{seat}"
    if not ref_exists(home, seat_ref):
        return "no seat-branch"
    not_on_main = int(output(home, "rev-list", "--count", f"origin/main..{seat_ref}"))
    if not_on_main == 0:
        return f"seat-branch {seat} holds no commit origin/main lacks"
    if commits_on_no_origin_branch(home, seat_ref) == 0:
        return (f"seat-branch {seat} holds {not_on_main} commit(s) origin/main lacks, all already "
                "on a branch on origin")
    saved = free_saved_branch_name(home, seat, today)
    git(home, "push", "--no-verify", "origin", f"{seat_ref}:refs/heads/{saved}")
    return (f"seat-branch {seat} holds {not_on_main} commit(s) origin/main lacks; its tip is "
            f"pushed to origin as {saved}")


def reasons_to_leave(home: Path) -> list:
    reasons = []
    git_directory = Path(output(home, "rev-parse", "--absolute-git-dir"))
    marker = freshness.in_progress_marker(git_directory)
    if marker is not None:
        reasons.append(f"a {freshness.in_progress_operation(git_directory, marker)} is in progress")
    changes = output(home, "status", "--porcelain", "--untracked-files=normal").splitlines()
    if changes:
        reasons.append(f"git status lists {len(changes)} uncommitted change(s), untracked files "
                       "included")
    if not current_branch(home):
        on_no_branch = len(output(home, "rev-list", "HEAD", "--not", "--branches",
                                  "--remotes").split())
        if on_no_branch:
            reasons.append(f"its detached HEAD holds {on_no_branch} commit(s) no branch holds")
    return reasons


def other_branch_note(home: Path, seat: str) -> str:
    branch = current_branch(home)
    if not branch or branch == seat:
        return ""
    unpushed = commits_on_no_origin_branch(home, f"refs/heads/{branch}")
    not_on_main = int(output(home, "rev-list", "--count", f"origin/main..refs/heads/{branch}"))
    if not (unpushed and not_on_main):
        return ""
    return (f"; it was on the branch {branch}, which is kept and holds {unpushed} commit(s) no "
            "branch on origin holds")


def move_agent_home(home: Path, today: datetime.date):
    """Return (moved, line) for one agent-home."""
    seat = home.name
    try:
        git(home, "fetch", "--quiet", "--prune", "origin")
        saved = save_seat_branch(home, seat, today)
    except GitStepFailed as error:
        return False, f"{home}: left as it was, because saving its seat-branch failed: {error}"
    try:
        reasons = reasons_to_leave(home)
        if reasons:
            return False, f"{home}: left as it was, because {'; '.join(reasons)}; {saved}"
        note = other_branch_note(home, seat)
        marker = Path(output(home, "rev-parse", "--absolute-git-dir")) / AGENT_HOME_MARKER_NAME
        marker.touch()
        git(home, "checkout", "--quiet", "--detach", "origin/main")
    except (GitStepFailed, OSError) as error:
        return False, f"{home}: not moved: {error}; {saved}"
    return True, f"{home}: now detached at origin/main and marked as an agent-home; {saved}{note}"


LEFT_INSTRUCTIONS = (
    "For each agent-home left as it was: if its changes or commits are work, carry them to a "
    "worktree on an nc-topic-branch, or ask that agent-seat to, then run this program again.\n"
    "If a step failed, fix what git's error names, then run this program again: it pushes "
    "nothing twice and moves only what is still to move."
)


def load_recover_crashed_seats():
    spec = importlib.util.spec_from_file_location(
        "recover_crashed_seats", REPO_ROOT / "scripts" / "recover-crashed-seats.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--agents-root", type=Path)
    parser.add_argument("--handoff-directory", type=Path)
    arguments = parser.parse_args(argv)
    try:
        seats_module = load_recover_crashed_seats()
        agents_root = arguments.agents_root or seats_module.default_agents_root()
        handoff_directory = arguments.handoff_directory or seats_module.default_handoff_directory()
        seat_names = set(seats_module.list_agent_seat_names_with_agent_session_records(
            agents_root, handoff_directory))
        homes = list_agent_homes(agents_root, seat_names)
    except Exception as error:
        print(f"agent-home migration: the agent-homes could not be listed, so nothing was moved: "
              f"{type(error).__name__}: {error}", file=sys.stderr)
        return 2
    if not homes:
        print(f"agent-home migration: no agent-home under {agents_root}; nothing to do")
        return 0
    today = datetime.date.today()
    all_moved = True
    for home in homes:
        moved, line = move_agent_home(home, today)
        all_moved = all_moved and moved
        print(line)
    if not all_moved:
        print(LEFT_INSTRUCTIONS)
    return 0 if all_moved else 1


if __name__ == "__main__":
    sys.exit(main())
