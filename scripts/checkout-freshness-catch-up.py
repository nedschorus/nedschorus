#!/usr/bin/env python3
"""Keep a session's checkout current with origin/main — the mid-session half.

User-walked 2026-08-17 (git-infra rules walk, deployment-boundary item). The
fleet already had the between-sessions half: handoff-supervisor.py's
sync_working_branch_with_main fast-forwards a clean seat branch at launch,
and its own docstring names the gap — "a long-lived session drifts
arbitrarily far from main with nothing announcing it." This script is the
announcing, and where safe the catching up, DURING a session:

Wired as a Stop hook, so it runs at every turn boundary. Each run:

  1. Resolves the session's checkout from the hook payload's cwd (the
     session's own view — $CLAUDE_PROJECT_DIR lies in forked sessions).
  2. Fetches origin, throttled by a stamp file in the checkout's git
     directory (default 300s between fetches; fetching touches refs only and
     is always safe — it is the MERGE that needs guarding).
  3. If the branch is behind origin/main, REPORTS — how far behind, how
     many commits are the branch's own (merges excluded), and whether the
     head is unpushed, pushed and equal to origin/<branch> (frozen: a review
     may be running against it), or pushed with local commits on top — and
     never merges into the working branch. Ruled 2026-09-14 (nedschorus#324):
     the merge it used to make landed on heads frozen under review five
     times in one evening, and seeded the very drift it existed to remove;
     main's branch protection makes being behind cost nothing at merge
     time. The report is for the agent's knowledge, not a prompt to act:
     new work starts from origin/main, and a frozen head is never moved.
     It is printed when the facts change, not at every turn end, so a
     seat that stays behind for the life of a review is not nagged; the
     stamp carries the numbers for the status line regardless.
  4. The machine's reference checkout — the main worktree of the same
     repository, parked on main — gets a fast-forward-only pull on the same
     rhythm, under its own stamp. Never a real merge there: the reference
     copy carries no work of its own by construction, and 2026-08-17 it sat
     33 commits stale, running a superseded extractor under every supervisor
     on the machine.

Everything here exits 0 and speaks plain text: a freshness fault must never
block a turn from ending, and nothing here costs the agent a turn (the
decision:block channel went with the merge — a Stop hook's plain stdout
reaches the transcript display, and that is where a report belongs).
Silence is meaningful — no output means nothing changed. The stamp
(<git-dir>/checkout-freshness-stamp.json) is what the status line and boot
reports display, so "0 behind" is only ever claimed off a real fetch, with
its age known.

Modes:
  (default)          Stop-hook mode; reads the hook payload from stdin
  --cwd PATH         hook mode without stdin (tests, ad-hoc runs)
  --report           print the stamp's one-line summary, fetch if stale
  --reference-pull   only the reference-checkout fast-forward
  --repo PATH        the checkout --report/--reference-pull operate on
  --interval-seconds how long a fetch stays fresh (default 300)
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

STAMP_FILE_NAME = "checkout-freshness-stamp.json"

# A git that never ran reports a code git itself cannot return, so "no answer"
# can never be read as an answer. NOT 1: git uses 1 as a real answer in this
# project's guards (`rev-parse --verify --quiet HEAD` exits 1 for "HEAD does
# not exist"), and synthesizing 1 for a launch failure made the two
# indistinguishable — the defect found on PR #103. Aligned here so the same
# function name does not mean two different things in two files.
GIT_DID_NOT_RUN = -1
DEFAULT_FETCH_INTERVAL_SECONDS = 300

# In-progress operation markers: the reference fast-forward must not run in
# a tree that is mid-anything.
GIT_IN_PROGRESS_MARKERS = (
    "MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG",
    "rebase-merge", "rebase-apply",
)


# Hook-mode output is queued and printed once at the end of the run, so the
# session's report and the reference checkout's read as one message.
REPORT_LINES = []


def report(line: str) -> None:
    """Queue one line of hook output."""
    REPORT_LINES.append(line)


def flush_report() -> None:
    """Print everything queued, plain text."""
    for queued_line in REPORT_LINES:
        print(queued_line)


def run_git(arguments, working_directory: Path, timeout: int = 60):
    """Run git somewhere; never raise, whatever goes wrong.

    LC_ALL=C because this script READS git's prose. The merge path decides
    whether it owns a conflict by looking for the word "CONFLICT" in git's
    output, and git translates that word: a German-locale host prints
    "KONFLIKT", the test fails to match, and the cleanup that should abort the
    merge is skipped — leaving the seat's tree parked mid-merge (PR #87's
    review). Forcing the C locale makes every message this script matches on
    stable, whatever the host is configured for.
    """
    try:
        return subprocess.run(
            ["git", *arguments], cwd=str(working_directory),
            capture_output=True, text=True, check=False, timeout=timeout,
            env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.SubprocessError) as error:
        return subprocess.CompletedProcess(arguments, GIT_DID_NOT_RUN, "",
                                           f"{type(error).__name__}: {error}")


def checkout_root(directory: Path):
    result = run_git(["rev-parse", "--show-toplevel"], directory, timeout=15)
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def git_directory(checkout: Path):
    result = run_git(["rev-parse", "--absolute-git-dir"], checkout, timeout=15)
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def read_stamp(stamp_path: Path) -> dict:
    try:
        return json.loads(stamp_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def write_stamp(stamp_path: Path, stamp: dict) -> None:
    try:
        stamp_path.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass  # a stamp is telemetry; losing one must not fail the hook


def fetch_if_stale(checkout: Path, stamp_path: Path, interval_seconds: int) -> dict:
    """Fetch origin unless a recent fetch is on record; return the stamp."""
    stamp = read_stamp(stamp_path)
    now = time.time()
    last = stamp.get("fetched_at", 0)
    if isinstance(last, (int, float)) and now - last < interval_seconds:
        return stamp
    # 20s, not more: this runs at every turn boundary, and two checkouts
    # each fetching against a dead network must not stall a turn for minutes.
    fetched = run_git(["fetch", "--quiet", "origin"], checkout, timeout=20)
    stamp["fetched_at"] = now
    stamp["fetch_ok"] = fetched.returncode == 0
    return stamp


def counts_against_main(checkout: Path):
    """(behind, ahead) of HEAD against origin/main, or None when unknowable."""
    if run_git(["rev-parse", "--verify", "--quiet", "origin/main"], checkout,
               timeout=15).returncode != 0:
        return None
    behind = run_git(["rev-list", "--count", "HEAD..origin/main"], checkout, timeout=30)
    ahead = run_git(["rev-list", "--count", "origin/main..HEAD"], checkout, timeout=30)
    if behind.returncode != 0 or ahead.returncode != 0:
        return None
    try:
        return int(behind.stdout.strip()), int(ahead.stdout.strip())
    except ValueError:
        return None


def own_commit_count(checkout: Path):
    """Commits on HEAD that main lacks, merges excluded — the branch's own
    work, as distinct from catch-up merges it may carry; None when
    unknowable."""
    counted = run_git(["rev-list", "--count", "--no-merges", "origin/main..HEAD"],
                      checkout, timeout=30)
    if counted.returncode != 0:
        return None
    try:
        return int(counted.stdout.strip())
    except ValueError:
        return None


def head_state(checkout: Path, branch: str):
    """(key, text) for where HEAD stands against its remote branch. The
    frozen-head rule (CLAUDE.md, 2026-09-08) freezes a head the moment it is
    pushed, so "pushed and equal to origin/<branch>" is the fact the rule
    keys on; whether a pull request is open is not asked, because that
    needs gh and the network at every turn end, and the rule does not."""
    if branch in ("", "HEAD"):
        return "detached", "detached HEAD"
    remote = run_git(["rev-parse", "--verify", "--quiet", f"origin/{branch}"],
                     checkout, timeout=15)
    if remote.returncode != 0:
        return "unpushed", "head unpushed"
    head = run_git(["rev-parse", "HEAD"], checkout, timeout=15).stdout.strip()
    if remote.stdout.strip() == head:
        return "pushed", (f"head pushed and equal to origin/{branch} (frozen: a fix is a "
                          "new commit on top, never an amend or a merge)")
    local = run_git(["rev-list", "--count", f"origin/{branch}..HEAD"], checkout, timeout=30)
    count = local.stdout.strip() if local.returncode == 0 else "some"
    return "pushed-with-local-commits", (f"head pushed, with {count} local commit(s) not "
                                         f"on origin/{branch}")


def merge_blockers(checkout: Path, git_dir: Path):
    """Why the reference fast-forward must not run here right now; empty
    list means safe."""
    blockers = []
    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"], checkout,
                     timeout=15).stdout.strip()
    if branch in ("", "HEAD"):
        blockers.append("detached HEAD")
    if branch == "main":
        blockers.append("parked on main (reference checkouts fast-forward only)")
    status = run_git(["status", "--porcelain"], checkout, timeout=30)
    if status.returncode != 0:
        # An unreadable tree must read as unsafe, never as clean — a status
        # failure that passed for "no changes" would authorize a merge on
        # exactly the tree nothing could inspect (review finding, PR #87).
        blockers.append("git status unreadable")
    else:
        tracked_changes = [line for line in status.stdout.splitlines()
                           if not line.startswith("??")]
        if tracked_changes:
            blockers.append(f"{len(tracked_changes)} uncommitted tracked change(s)")
    for marker in GIT_IN_PROGRESS_MARKERS:
        if (git_dir / marker).exists():
            blockers.append(f"a git operation in progress ({marker})")
            break
    return blockers, branch


def catch_up_session_checkout(checkout: Path, interval_seconds: int) -> None:
    """The Stop-hook body for the session's own checkout: fetch, count,
    report on change. It never merges (ruled 2026-09-14, nedschorus#324)."""
    git_dir = git_directory(checkout)
    if git_dir is None:
        return
    stamp_path = git_dir / STAMP_FILE_NAME
    stamp = fetch_if_stale(checkout, stamp_path, interval_seconds)

    counts = counts_against_main(checkout)
    if counts is None:
        # Unknowable is not "still whatever it was": a preserved stale count
        # would render as knowledge (silent-safety rule).
        stamp["behind"] = stamp["ahead"] = None
        stamp.pop("last_reported", None)
        write_stamp(stamp_path, stamp)
        return
    behind, ahead = counts
    stamp["behind"], stamp["ahead"] = behind, ahead

    if behind == 0:
        stamp.pop("last_reported", None)
        write_stamp(stamp_path, stamp)
        return

    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"], checkout,
                     timeout=15).stdout.strip()
    own = own_commit_count(checkout)
    state_key, state_text = head_state(checkout, branch)
    main_tip = run_git(["rev-parse", "origin/main"], checkout, timeout=15).stdout.strip()
    stamp["branch"], stamp["own"], stamp["head_state"] = branch, own, state_key
    stamp["last_action"] = "reported, not merged (ruled 2026-09-14)"

    # Reported when the facts change, not at every turn end: a seat with a
    # pull request in review stays behind for the life of the review, and a
    # line repeating that is the "does something when there is nothing to
    # do" the ruling answered.
    facts = {"behind": behind, "own": own, "head_state": state_key, "main_tip": main_tip}
    if stamp.get("last_reported") == facts:
        write_stamp(stamp_path, stamp)
        return
    stamp["last_reported"] = facts
    write_stamp(stamp_path, stamp)
    own_text = "own commits unknowable" if own is None else f"{own} own commit(s)"
    report(f"catch-up: {branch or 'detached HEAD'} is {behind} behind origin/main — "
           f"{own_text}, {ahead} ahead counting merges; {state_text}. Not merged "
           f"(ruled 2026-09-14): new work starts from origin/main, and a frozen head "
           f"is never moved.")


def reference_checkout_of(checkout: Path):
    """The main worktree of the same repository — the machine's reference copy."""
    listing = run_git(["worktree", "list", "--porcelain"], checkout, timeout=15)
    if listing.returncode != 0:
        return None
    for line in listing.stdout.splitlines():
        if line.startswith("worktree "):
            return Path(line.split(" ", 1)[1])
    return None


def fast_forward_reference_checkout(reference: Path, interval_seconds: int) -> None:
    """ff-only pull of a checkout parked on main; never a real merge.

    Safe by construction only when the reference carries nothing of its own:
    any local commit, any tracked change, any in-progress operation, and it
    is left alone with a line saying so.
    """
    git_dir = git_directory(reference)
    if git_dir is None:
        return
    stamp_path = git_dir / STAMP_FILE_NAME
    stamp = fetch_if_stale(reference, stamp_path, interval_seconds)

    counts = counts_against_main(reference)
    if counts is None:
        # Unknowable is not "still whatever it was" — same silent-safety rule
        # the seat's own path applies. Leaving the previous numbers in place
        # renders a stale count as knowledge (PR #87's review).
        stamp["behind"] = stamp["ahead"] = None
        write_stamp(stamp_path, stamp)
        return
    behind, ahead = counts
    stamp["behind"], stamp["ahead"] = behind, ahead

    if behind == 0:
        write_stamp(stamp_path, stamp)
        return

    blockers, branch = merge_blockers(reference, git_dir)
    stamp["branch"] = branch
    # For the reference the "parked on main" blocker is the requirement, not
    # a blocker; everything else still blocks.
    real_blockers = [blocker for blocker in blockers if "parked on main" not in blocker]
    if branch != "main":
        real_blockers.append(f"on {branch or 'no branch'}, not main")
    if ahead:
        real_blockers.append(f"{ahead} local commit(s) main does not have")
    if real_blockers:
        stamp["last_action"] = f"reference skipped: {'; '.join(real_blockers)}"
        write_stamp(stamp_path, stamp)
        report(f"catch-up: reference checkout {reference} is {behind} behind and was "
               f"left alone — {'; '.join(real_blockers)}")
        return

    pulled = run_git(["merge", "--ff-only", "origin/main"], reference, timeout=120)
    if pulled.returncode != 0:
        stamp["last_action"] = "reference ff-only refused"
        write_stamp(stamp_path, stamp)
        report(f"catch-up: reference checkout {reference} could not fast-forward: "
               f"{pulled.stderr.strip() or 'no detail'}")
        return
    stamp["behind"], stamp["last_action"] = 0, f"reference fast-forwarded {behind}"
    write_stamp(stamp_path, stamp)
    report(f"catch-up: reference checkout {reference} fast-forwarded {behind} commit(s) "
           f"to origin/main")


def report_line(checkout: Path, interval_seconds: int) -> str:
    git_dir = git_directory(checkout)
    if git_dir is None:
        return f"freshness: {checkout} is not a git checkout"
    stamp_path = git_dir / STAMP_FILE_NAME
    stamp = fetch_if_stale(checkout, stamp_path, interval_seconds)
    counts = counts_against_main(checkout)
    if counts is None:
        # Same rule again: the line about to be printed says the comparison
        # could not be made, so the stamp behind it must not keep claiming a
        # number (PR #87's review).
        stamp["behind"] = stamp["ahead"] = None
        write_stamp(stamp_path, stamp)
        return f"freshness: {checkout} has no origin/main to compare against"
    behind, ahead = counts
    stamp["behind"], stamp["ahead"] = behind, ahead
    write_stamp(stamp_path, stamp)
    age = int(time.time() - stamp.get("fetched_at", 0))
    fetch_note = f"fetched {age}s ago" if stamp.get("fetch_ok") else "last fetch FAILED"
    return f"freshness: {checkout.name} is {behind} behind, {ahead} ahead of origin/main ({fetch_note})"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Keep a session's checkout current with origin/main.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__,
    )
    parser.add_argument("--cwd", default=None,
                        help="operate as hook mode on this directory instead of reading stdin")
    parser.add_argument("--report", action="store_true",
                        help="print a one-line freshness summary and exit")
    parser.add_argument("--reference-pull", action="store_true",
                        help="only fast-forward the reference checkout of --repo")
    parser.add_argument("--repo", default=".",
                        help="the checkout --report / --reference-pull operate on")
    parser.add_argument("--interval-seconds", type=int, default=DEFAULT_FETCH_INTERVAL_SECONDS,
                        help="how long a fetch stays fresh")
    arguments = parser.parse_args(argv)

    if arguments.report:
        print(report_line(Path(arguments.repo).resolve(), arguments.interval_seconds))
        return 0

    if arguments.reference_pull:
        root = checkout_root(Path(arguments.repo).resolve())
        if root is not None:
            reference = reference_checkout_of(root)
            if reference is not None:
                fast_forward_reference_checkout(reference, arguments.interval_seconds)
        flush_report()
        return 0

    # Hook mode: the session's own checkout, then the machine's reference copy.
    if arguments.cwd is not None:
        session_cwd = Path(arguments.cwd)
    else:
        try:
            payload = json.loads(sys.stdin.read() or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {}
        session_cwd = Path(payload.get("cwd") or ".")

    # One exit, one flush: an early return here would be a silent hook, which
    # is the failure mode this queue introduces if it is not funnelled.
    root = checkout_root(session_cwd)
    if root is not None:
        branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"], root,
                         timeout=15).stdout.strip()
        if branch == "main":
            # A session seated in the reference copy itself: ff-only, never merge.
            fast_forward_reference_checkout(root, arguments.interval_seconds)
        else:
            catch_up_session_checkout(root, arguments.interval_seconds)
            reference = reference_checkout_of(root)
            if reference is not None and reference != root:
                fast_forward_reference_checkout(reference, arguments.interval_seconds)
    flush_report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
