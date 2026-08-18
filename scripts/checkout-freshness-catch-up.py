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
  3. If the branch is behind origin/main and it is safe — on a branch that
     is not main, no uncommitted tracked changes, no merge/rebase/bisect in
     progress — attempts the merge; a conflict aborts cleanly back to the
     pre-merge tree and reports instead. A merge that lands names the files
     it changed, so the agent re-reads before touching them (the harness
     independently refuses edits to files changed since last read).
  4. The machine's reference checkout — the main worktree of the same
     repository, parked on main — gets a fast-forward-only pull on the same
     rhythm, under its own stamp. Never a real merge there: the reference
     copy carries no work of its own by construction, and 2026-08-17 it sat
     33 commits stale, running a superseded extractor under every supervisor
     on the machine.

Everything here exits 0: a freshness fault must never block a turn from
ending. Silence is meaningful — no output means nothing needed doing; every
skipped merge states its reason. The stamp
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
import subprocess
import sys
import time
from pathlib import Path

STAMP_FILE_NAME = "checkout-freshness-stamp.json"
DEFAULT_FETCH_INTERVAL_SECONDS = 300
CHANGED_FILES_NAMED_LIMIT = 8

# In-progress operation markers: merging into a tree mid-anything is how an
# agent wakes to conflict markers it never created.
GIT_IN_PROGRESS_MARKERS = (
    "MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG",
    "rebase-merge", "rebase-apply",
)


def run_git(arguments, working_directory: Path, timeout: int = 60):
    """Run git somewhere; never raise, whatever goes wrong."""
    try:
        return subprocess.run(
            ["git", *arguments], cwd=str(working_directory),
            capture_output=True, text=True, check=False, timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return subprocess.CompletedProcess(arguments, 1, "", f"{type(error).__name__}: {error}")


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


def merge_blockers(checkout: Path, git_dir: Path):
    """Why a merge must not run here right now; empty list means safe."""
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
    """The Stop-hook body for the session's own checkout."""
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
        write_stamp(stamp_path, stamp)
        return
    behind, ahead = counts
    stamp["behind"], stamp["ahead"] = behind, ahead

    if behind == 0:
        write_stamp(stamp_path, stamp)
        return

    blockers, branch = merge_blockers(checkout, git_dir)
    stamp["branch"] = branch
    if blockers:
        stamp["last_action"] = f"skipped: {'; '.join(blockers)}"
        write_stamp(stamp_path, stamp)
        print(f"catch-up: {branch} is {behind} behind origin/main; not merged — "
              f"{'; '.join(blockers)}")
        return

    before = run_git(["rev-parse", "HEAD"], checkout, timeout=15).stdout.strip()
    main_tip = run_git(["rev-parse", "origin/main"], checkout, timeout=15).stdout.strip()

    # A standing conflict must not be re-attempted every turn: each attempt
    # clobbers ORIG_HEAD and churns the tree for a known answer. The stamp
    # remembers which (HEAD, origin/main) pair conflicted; the same pair is
    # reported, not retried (review finding, PR #87).
    conflict_pair = f"{before}:{main_tip}"
    if stamp.get("conflict_pair") == conflict_pair:
        write_stamp(stamp_path, stamp)
        print(f"catch-up: {branch} is {behind} behind origin/main; the merge still "
              f"conflicts (not retried) — merge by hand at a clean point "
              f"(git merge origin/main)")
        return

    # Immediately before merging, re-verify no merge state appeared since the
    # blockers ran: an abort may only ever destroy state THIS run created,
    # because a human's half-resolved merge is unrecoverable once aborted
    # (blocking review finding, PR #87).
    if (git_dir / "MERGE_HEAD").exists():
        stamp["last_action"] = "skipped: a foreign merge appeared mid-check"
        write_stamp(stamp_path, stamp)
        print(f"catch-up: {branch} is {behind} behind origin/main; not merged — "
              f"another merge is in progress here, left exactly as found")
        return

    merged = run_git(["-c", "core.editor=true", "merge", "--no-edit", "origin/main"],
                     checkout, timeout=120)
    if merged.returncode != 0:
        conflicted = "CONFLICT" in (merged.stdout + merged.stderr)
        own_merge_state = (git_dir / "MERGE_HEAD").exists()
        if not (conflicted and own_merge_state):
            # Failed for some other reason (index.lock, a racing operation,
            # an odd tree). Nothing here is ours to abort; touch nothing.
            detail = (merged.stderr or merged.stdout).strip().splitlines()
            stamp["last_action"] = "merge failed without a conflict; nothing touched"
            write_stamp(stamp_path, stamp)
            print(f"catch-up: {branch} is {behind} behind origin/main; the merge "
                  f"failed without conflicting and nothing was aborted — "
                  f"{detail[0] if detail else 'no detail'}")
            return
        aborted = run_git(["merge", "--abort"], checkout, timeout=60)
        if aborted.returncode != 0 or (git_dir / "MERGE_HEAD").exists():
            # A failed abort may NOT report success: the tree is mid-conflict
            # and someone must look (silent-safety rule).
            stamp["last_action"] = "conflict: ABORT FAILED, tree needs attention"
            write_stamp(stamp_path, stamp)
            print(f"catch-up: {branch} conflicted with origin/main and the abort "
                  f"FAILED — the tree is mid-merge and needs manual attention: "
                  f"{aborted.stderr.strip() or 'no detail'}")
            return
        stamp["conflict_pair"] = conflict_pair
        stamp["last_action"] = "conflict: merge aborted cleanly"
        write_stamp(stamp_path, stamp)
        print(f"catch-up: {branch} is {behind} behind origin/main; the merge would "
              f"conflict, so nothing was touched — merge by hand at a clean point "
              f"(git merge origin/main)")
        return
    stamp.pop("conflict_pair", None)

    changed = run_git(["diff", "--name-only", f"{before}..HEAD"], checkout,
                      timeout=30).stdout.split()
    named = ", ".join(changed[:CHANGED_FILES_NAMED_LIMIT])
    if len(changed) > CHANGED_FILES_NAMED_LIMIT:
        named += f", … {len(changed) - CHANGED_FILES_NAMED_LIMIT} more"
    stamp["behind"], stamp["last_action"] = 0, f"merged {behind} commit(s)"
    write_stamp(stamp_path, stamp)
    print(f"catch-up: merged origin/main into {branch} ({behind} commit(s)). "
          f"Changed: {named or 'no files'} — re-read any of these before editing them.")


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
        print(f"catch-up: reference checkout {reference} is {behind} behind and was "
              f"left alone — {'; '.join(real_blockers)}")
        return

    pulled = run_git(["merge", "--ff-only", "origin/main"], reference, timeout=120)
    if pulled.returncode != 0:
        stamp["last_action"] = "reference ff-only refused"
        write_stamp(stamp_path, stamp)
        print(f"catch-up: reference checkout {reference} could not fast-forward: "
              f"{pulled.stderr.strip() or 'no detail'}")
        return
    stamp["behind"], stamp["last_action"] = 0, f"reference fast-forwarded {behind}"
    write_stamp(stamp_path, stamp)
    print(f"catch-up: reference checkout {reference} fast-forwarded {behind} commit(s) "
          f"to origin/main")


def report_line(checkout: Path, interval_seconds: int) -> str:
    git_dir = git_directory(checkout)
    if git_dir is None:
        return f"freshness: {checkout} is not a git checkout"
    stamp_path = git_dir / STAMP_FILE_NAME
    stamp = fetch_if_stale(checkout, stamp_path, interval_seconds)
    counts = counts_against_main(checkout)
    if counts is None:
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
        if root is None:
            return 0
        reference = reference_checkout_of(root)
        if reference is not None:
            fast_forward_reference_checkout(reference, arguments.interval_seconds)
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

    root = checkout_root(session_cwd)
    if root is None:
        return 0
    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"], root, timeout=15).stdout.strip()
    if branch == "main":
        # A session seated in the reference copy itself: ff-only, never merge.
        fast_forward_reference_checkout(root, arguments.interval_seconds)
        return 0
    catch_up_session_checkout(root, arguments.interval_seconds)
    reference = reference_checkout_of(root)
    if reference is not None and reference != root:
        fast_forward_reference_checkout(reference, arguments.interval_seconds)
    return 0


if __name__ == "__main__":
    sys.exit(main())
