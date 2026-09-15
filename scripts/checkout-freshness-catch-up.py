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
  3. Runs the MISBEHAVIOUR detectors, every turn, before anything else: a
     merge commit from main on the working branch (ruled out 2026-09-14,
     nedschorus#324), or a pushed head whose history was rewritten (an amend
     or rebase after a push, ruled out 2026-09-08). What they find is the
     ONLY thing the user hears from this hook — "If the agents are doing the
     wrong thing, or not doing the right thing, that's when I probably need
     to be told" (ruled 2026-09-15). Routine drift is never reported to the
     user; the stamp carries the numbers for the status line.
  4. If the branch is behind origin/main and has NEVER been pushed, REBASES
     it onto origin/main here, and tells the agent at its next turn what
     moved and which files changed. Skips a dirty tree; aborts cleanly on a
     conflict and names the files. This is not the merge #324 removed: that
     landed merge commits on FROZEN heads; this moves only heads nobody else
     has, creates no merge commit, and leaves the pushed-head rule untouched.
     Walked and ruled 2026-09-15 (docs/walk/keeping-branches-current-telling-
     and-rebase).
  5. If the branch is behind and HAS been pushed, never moves it. The agent
     is TOLD, once per update of main: how far behind, which files main has
     changed that it lacks — named, grouped by why they matter, computed from
     `git diff --name-only HEAD...origin/main`, never assumed — and to leave
     the branch alone and cut its next topic from origin/main.
  6. The machine's reference checkout — the main worktree of the same
     repository, parked on main — gets a fast-forward-only pull on the same
     rhythm, under its own stamp. Never a real merge there: the reference
     copy carries no work of its own by construction, and 2026-08-17 it sat
     33 commits stale, running a superseded extractor under every supervisor
     on the machine. A reference that cannot update — someone left work
     there — is a user line; a success is silent.

The agent's messages travel as the hook's `hookSpecificOutput.additionalContext`
and the user's as `systemMessage`, in one JSON object. Plain stdout on exit 0
reaches neither for a Stop hook — which is why, before 2026-09-15, every
report this script made was read by nobody.

Everything here exits 0: a freshness fault must never block a turn from
ending, and nothing here costs the agent a turn (the decision:block channel
went with the merge, and no `decision` field is ever emitted).
Silence is meaningful — no output means nothing changed. The stamp
(<git-dir>/checkout-freshness-stamp.json) is what the status line and boot
reports display, so "0 behind" is only ever claimed off a real fetch, with
its age known.

Modes (only the first speaks JSON; the operator-facing ones stay plain text,
because launchers read them on a terminal):
  (default)             Stop-hook mode; reads the hook payload from stdin
  --cwd PATH            hook mode without stdin (tests, ad-hoc runs)
  --report              print the stamp's one-line summary, fetch if stale
  --reference-pull      only the reference-checkout fast-forward
  --repo PATH           the checkout --report/--reference-pull operate on
  --interval-seconds    how long a fetch stays fresh (default 300)
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

# What the agent is told to DO, decided by one fact: whether the branch has
# ever been pushed. Walked and ruled 2026-09-15 (docs/walk/keeping-branches-
# current-telling-and-rebase). A never-pushed branch is rebased by this hook
# itself, so REBASE_ADVICE is what the agent gets only when the hook could
# not — a dirty tree, or a conflict it aborted. A pushed branch is never
# moved by anyone but its author, and then only forward.
REBASE_ADVICE = (
    "This branch has never been pushed, so nobody else has it. Bring it up to "
    "date now: commit or set aside any uncommitted work, run `git rebase "
    "origin/main`, then rerun the test suites for what you touched. If the "
    "rebase stops on a conflict, `git rebase --abort` puts everything back; then "
    "resolve it by hand or stay behind, which costs nothing at merge."
)
LEAVE_IT_ADVICE = (
    "This branch is pushed, so its review may be running. Do not rebase, merge "
    "or amend it. A fix for this topic is a new commit on top, pushed once. "
    "Start your next topic with `git checkout -b <name> origin/main`."
)
DETACHED_ADVICE = "You are on a detached HEAD; check out your branch before working."
AFTER_REBASE_ADVICE = "Rerun the test suites for what you touched: your work now sits on newer code."

# Categories worth naming, most consequential first, each labelled with WHY an
# agent should care where that is not self-evident (user, 2026-09-15: "explain
# which files should be updated (and perhaps why, unless that is obvious)").
# A file's category is decided by path, and the first match wins.
DRIFT_PATH_CATEGORIES = (
    ("your standing instructions",
     lambda path: path == "CLAUDE.md" or path.endswith("/CLAUDE.md")),
    ("skills you run under",
     lambda path: path.startswith(".claude/skills/")),
    ("hooks and wiring that run on your work",
     lambda path: path.startswith(".claude/hooks/") or path == ".claude/settings.json"),
    ("scripts your tests run against",
     lambda path: path.startswith("scripts/")),
    ("documents you may cite",
     lambda path: path.startswith("docs/")),
    ("other files", lambda path: True),
)

# How many to name per category before falling back to a count. Naming every
# path in a wide gap would be a wall the agent skims; four is enough to
# recognise whether the drift touches what it is about to do.
DRIFT_FILES_NAMED_PER_CATEGORY = 4


def obsolete_files_by_category(checkout: Path):
    """[(label, [path, ...]), ...] — the files main has moved that this
    checkout has not, grouped by why they matter. Empty when there is nothing
    to say or the comparison cannot be made.

    NAMED RATHER THAN ASSUMED. The first draft of the agent's line ended with a
    fixed sentence: "your tests, hooks, skills and documents here are older than
    main." The user asked "are you sure they are older than main — or are you
    just saying that?" (2026-09-15). Just saying it. Measured on the seat that
    built the feature, in a twelve-commit gap: ten scripts and four documents
    had moved, and ZERO hooks and ZERO skills had. Two thirds of the sentence
    was false at every printing, and an agent that reads one false clause learns
    to discount the whole line — the ignoring this exists to end.

    Three dots, not two: `HEAD...origin/main` diffs from the MERGE BASE, so it
    answers "what did main change that I do not have". Two dots would compare
    the trees outright and report this branch's OWN work as though main had
    changed it — the branch that built this would have claimed its own new files
    as ones it was missing.
    """
    listed = run_git(["diff", "--name-only", "HEAD...origin/main"], checkout, timeout=30)
    if listed.returncode != 0:
        return []
    paths = sorted(line.strip() for line in listed.stdout.splitlines() if line.strip())
    if not paths:
        return []

    grouped = {}
    for path in paths:
        for label, matches in DRIFT_PATH_CATEGORIES:
            if matches(path):
                grouped.setdefault(label, []).append(path)
                break
    return [(label, grouped[label]) for label, _ in DRIFT_PATH_CATEGORIES
            if label in grouped]


def format_obsolete_files(groups) -> str:
    """The grouped files as lines an agent reads, or "" for nothing to say."""
    lines = []
    for label, paths in groups:
        named = paths[:DRIFT_FILES_NAMED_PER_CATEGORY]
        remainder = len(paths) - len(named)
        listing = ", ".join(named)
        if remainder:
            listing += f" and {remainder} more"
        lines.append(f"  {label} ({len(paths)}): {listing}")
    return "\n".join(lines)


# Two queues, two audiences, flushed once at the end of the run so the
# session's report and the reference checkout's read as one message.
REPORT_LINES = []   # the user, on the display
AGENT_LINES = []    # the agent, in its context


def report(line: str) -> None:
    """Queue one line for the USER's display."""
    REPORT_LINES.append(line)


def tell(text: str) -> None:
    """Queue text for the AGENT's context."""
    AGENT_LINES.append(text)


def flush_report() -> None:
    """Print everything queued, plain text — the operator-facing modes."""
    for queued_line in REPORT_LINES:
        print(queued_line)


def flush_hook_output() -> None:
    """The Stop hook's one JSON object: what the user sees, what the agent reads.

    A Stop hook's plain stdout on exit 0 reaches neither — only
    `UserPromptSubmit`, `SessionStart` and their kin get plain stdout added to
    the agent's context. That is why every report this script made before
    2026-09-15 was read by nobody: it was speaking on the one channel with no
    listener at either end. `systemMessage` is shown to the user;
    `hookSpecificOutput.additionalContext` is added to the AGENT's context.

    No `decision` field, ever. Blocking costs the agent a turn, and the
    blocking channel went with the merge (ruled 2026-09-14, nedschorus#324).
    Silence stays meaningful: nothing queued prints nothing at all.
    """
    if not REPORT_LINES and not AGENT_LINES:
        return
    payload = {}
    if REPORT_LINES:
        payload["systemMessage"] = "\n".join(REPORT_LINES)
    if AGENT_LINES:
        payload["hookSpecificOutput"] = {
            "hookEventName": "Stop",
            "additionalContext": "\n".join(AGENT_LINES),
        }
    # ensure_ascii=False: the display line carries em dashes, and a
    # \u2014 in a log is a line a human has to decode.
    print(json.dumps(payload, ensure_ascii=False))


def run_git(arguments, working_directory: Path, timeout: int = 60):
    """Run git somewhere; never raise, whatever goes wrong.

    LC_ALL=C because this script READS git's prose: the reference
    fast-forward reports git's own refusal text, and a matched word in a
    translated message once skipped a cleanup entirely (PR #87's review, on
    the merge path this script no longer has). Forcing the C locale keeps
    every message stable, whatever the host is configured for.
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
    if count == "0":
        # HEAD is behind its own remote branch: the shape the fix-on-frozen-head
        # process leaves once the authoring seat fetches a fresh agent's fix
        # commit (PR #372 review). The truth is that the remote is ahead.
        remote_only = run_git(["rev-list", "--count", f"HEAD..origin/{branch}"], checkout,
                              timeout=30)
        remote_count = remote_only.stdout.strip() if remote_only.returncode == 0 else "some"
        return "behind-remote", (f"head behind origin/{branch} by {remote_count} commit(s) "
                                 f"pushed from elsewhere (a fix on the frozen head, most "
                                 f"likely); fast-forward to it before working here")
    ancestor = run_git(["merge-base", "--is-ancestor", f"origin/{branch}", "HEAD"],
                       checkout, timeout=15)
    if ancestor.returncode != 0:
        # Neither side contains the other: the pushed history was rewritten —
        # an amend or a rebase after a push, which moves a frozen head under
        # its reviewer (CLAUDE.md, ruled 2026-09-08). Named to the user.
        return "diverged-from-remote", (f"head has diverged from origin/{branch}: the pushed "
                                        f"history was rewritten after the push")
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


def drift_facts(checkout: Path, stamp: dict, branch: str, state_key: str, state_text: str):
    """(facts, parts) for a checkout's drift from origin/main, or (None, None)
    when there is nothing to say: not behind, or unknowable.

    The stamp fields the status line reads (behind, ahead, branch, own,
    head_state) are written here; the caller writes the stamp. The branch and
    head state are computed by the caller, because the caller needs them every
    turn — the misbehaviour detectors run whether or not the branch is behind —
    and computing them twice would be two chances to disagree.
    """
    counts = counts_against_main(checkout)
    if counts is None:
        # Unknowable is not "still whatever it was": a preserved stale count
        # would render as knowledge (silent-safety rule).
        stamp["behind"] = stamp["ahead"] = None
        return None, None
    behind, ahead = counts
    stamp["behind"], stamp["ahead"] = behind, ahead
    if behind == 0:
        return None, None

    own = own_commit_count(checkout)
    main_tip = run_git(["rev-parse", "origin/main"], checkout, timeout=15).stdout.strip()
    stamp["branch"], stamp["own"], stamp["head_state"] = branch, own, state_key
    facts = {"behind": behind, "own": own, "head_state": state_key, "main_tip": main_tip}
    parts = {
        "branch": branch or "detached HEAD",
        "behind": behind,
        "ahead": ahead,
        "own_text": "own commits unknowable" if own is None else f"{own} own commit(s)",
        "state_text": state_text,
    }
    return facts, parts


def merges_from_main(checkout: Path):
    """Short SHAs of merge commits on this branch whose second parent lies on
    origin/main — the catch-up merge this hook itself used to make, and which
    nedschorus#324 ruled out after nine landed on frozen heads in five days.

    A merge of another topic branch is not the banned thing, so the second
    parent is tested for being on main rather than every merge being flagged.
    A branch that carries pre-#324 merges is flagged once at rollout, which is
    correct: those merges are real and the user has not been told of them.
    """
    merges = run_git(["rev-list", "--merges", "origin/main..HEAD"], checkout, timeout=30)
    if merges.returncode != 0:
        return []
    flagged = []
    for sha in merges.stdout.split():
        second = run_git(["rev-parse", "--verify", "--quiet", f"{sha}^2"], checkout, timeout=15)
        if second.returncode != 0:
            continue
        on_main = run_git(["merge-base", "--is-ancestor", second.stdout.strip(), "origin/main"],
                          checkout, timeout=15)
        if on_main.returncode == 0:
            flagged.append(sha[:12])
    return flagged


def rebase_never_pushed_branch(checkout: Path, git_dir: Path):
    """Move a never-pushed branch onto origin/main, or say why not.

    Returns (outcome, detail): "rebased"; "skipped" with the blockers; "conflict"
    with the conflicting paths, the tree put back exactly as it was; or
    "abort-failed", the one outcome that is a fault — the tree was left
    mid-rebase — and is reported to the user.

    WHY THIS HOOK MAY MOVE A BRANCH AT ALL, when nedschorus#324 removed its
    merge: #324's merge landed merge commits on FROZEN heads — pushed, with a
    review running — nine times in five days. This is a rebase of a branch that
    has NEVER been pushed: no review exists to disturb, no merge commit is
    created, and the pushed-head rule is untouched. The 2026-08-13 objection to
    rewriting files under a running agent is answered by telling the agent, at
    its next turn, exactly which files moved. Walked and ruled 2026-09-15.

    --no-autostash: a user-level rebase.autoStash would stash a dirty tree and
    rebase anyway, and "skip if dirty" is a promise. The timeout is short
    because the Stop hook has a budget of its own and a rebase of a few commits
    is sub-second; a rebase that takes longer is one to abort, not wait on.
    """
    blockers, _ = merge_blockers(checkout, git_dir)
    if blockers:
        return "skipped", "; ".join(blockers)
    rebased = run_git(["rebase", "--no-autostash", "origin/main"], checkout, timeout=30)
    if rebased.returncode == 0:
        return "rebased", ""
    conflicting = run_git(["diff", "--name-only", "--diff-filter=U"], checkout,
                          timeout=15).stdout.split()
    aborted = run_git(["rebase", "--abort"], checkout, timeout=30)
    still_in_progress = any((git_dir / marker).exists()
                            for marker in ("rebase-merge", "rebase-apply"))
    if aborted.returncode != 0 or still_in_progress:
        return "abort-failed", rebased.stderr.strip() or "no detail"
    return "conflict", ", ".join(conflicting) or (rebased.stderr.strip() or "no detail")


def fetch_failure_note(stamp: dict) -> str:
    """One line when the numbers rest on a fetch that failed, or "".
    Ruled 2026-09-15: a stale list must say it is stale."""
    if stamp.get("fetch_ok", True):
        return ""
    when = time.strftime("%H:%M", time.localtime(stamp.get("fetched_at", 0)))
    return f"\n(fetch failed at {when}; this list may be stale)"


def catch_up_session_checkout(checkout: Path, interval_seconds: int) -> None:
    """The Stop-hook body for the session's own checkout. Walked and ruled
    2026-09-15 (docs/walk/keeping-branches-current-telling-and-rebase):

      1. Misbehaviour detectors run EVERY turn, before and independent of the
         drift path — a branch that merged main into itself is 0 behind, which
         is exactly where a drift-first design would return early. What they
         find goes to the USER, and it is the only thing the user hears:
         "If the agents are doing the wrong thing, or not doing the right
         thing, that's when I probably need to be told." Routine drift is not
         reported to the user at all.
      2. Drift is counted. If none, every "already said" key is cleared.
      3. A never-pushed branch is REBASED onto origin/main here, and the agent
         told what moved. A pushed branch is never moved; the agent is TOLD,
         once per update of main, which files are stale and to leave it.
    """
    git_dir = git_directory(checkout)
    if git_dir is None:
        return
    stamp_path = git_dir / STAMP_FILE_NAME
    stamp = fetch_if_stale(checkout, stamp_path, interval_seconds)
    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"], checkout, timeout=15).stdout.strip()
    state_key, state_text = head_state(checkout, branch)

    # 1. Misbehaviour, to the user, once per distinct finding.
    found = {}
    merged = merges_from_main(checkout)
    if merged:
        found["merges_from_main"] = merged
    if state_key == "diverged-from-remote":
        head = run_git(["rev-parse", "HEAD"], checkout, timeout=15).stdout.strip()[:12]
        remote = run_git(["rev-parse", f"origin/{branch}"], checkout, timeout=15).stdout.strip()[:12]
        found["rewritten_head"] = [head, remote]
    if found and stamp.get("last_misbehaviour") != found:
        if "merges_from_main" in found:
            report(f"catch-up: {branch} carries {len(merged)} merge commit(s) from main "
                   f"({', '.join(merged)}); merging main into a working branch was ruled "
                   f"out 2026-09-14 (nedschorus#324)")
        if "rewritten_head" in found:
            head, remote = found["rewritten_head"]
            report(f"catch-up: {branch} rewrote its pushed head — origin/{branch} ({remote}) "
                   f"is no longer an ancestor of HEAD ({head}); an amend or rebase after a "
                   f"push moves a frozen head under its reviewer (ruled 2026-09-08)")
    if found:
        stamp["last_misbehaviour"] = found
    else:
        stamp.pop("last_misbehaviour", None)

    # 2. Drift.
    facts, parts = drift_facts(checkout, stamp, branch, state_key, state_text)
    if facts is None:
        stamp.pop("last_told", None)
        write_stamp(stamp_path, stamp)
        return
    told = {"branch": parts["branch"], "main_tip": facts["main_tip"],
            "pushed": state_key != "unpushed"}
    already_told = stamp.get("last_told") == told
    heading = (f"checkout-freshness: {parts['branch']} is {parts['behind']} behind "
               f"origin/main ({parts['own_text']}; {parts['state_text']}).")
    # Computed BEFORE any rebase: afterwards it is empty, and it is the list of
    # what moved under the agent.
    listing = format_obsolete_files(obsolete_files_by_category(checkout))
    older = f"\nOlder here than on main:\n{listing}" if listing else ""
    note = fetch_failure_note(stamp)

    # 3a. Never pushed: this hook moves the branch. A success is ALWAYS told —
    # files just changed under the agent, and that is never deduplicated. A
    # skip or a conflict is told once per key, but ATTEMPTED every turn end,
    # so the moment the tree is clean it goes.
    if state_key == "unpushed":
        outcome, detail = rebase_never_pushed_branch(checkout, git_dir)
        if outcome == "rebased":
            stamp["behind"], stamp["ahead"] = 0, stamp.get("own")
            stamp["last_action"] = f"rebased {parts['behind']} under a never-pushed head"
            stamp.pop("last_told", None)
            tell(f"checkout-freshness: {parts['branch']} was rebased onto origin/main "
                 f"({parts['behind']} commit(s) moved under your {parts['own_text']}; "
                 f"never pushed, so nothing was under review).{older}\n{AFTER_REBASE_ADVICE}")
        elif outcome == "abort-failed":
            stamp["last_action"] = "rebase failed AND could not abort"
            report(f"catch-up: {branch} was left mid-rebase — the rebase onto origin/main "
                   f"failed and `git rebase --abort` did not restore it ({detail}); "
                   f"the tree needs a hand")
            tell(f"{heading} A rebase onto origin/main was attempted here and could not be "
                 f"aborted cleanly ({detail}). Inspect `git status` before doing anything else.")
        else:
            stamp["last_action"] = f"rebase {outcome}: {detail}"
            if not already_told:
                stamp["last_told"] = told
                reason = (f"Not updated: {detail}." if outcome == "skipped"
                          else f"A rebase onto origin/main was tried and put back: it "
                               f"conflicts on {detail}.")
                tell(f"{heading} {reason}{older}{note}\n{REBASE_ADVICE}")
        write_stamp(stamp_path, stamp)
        return

    # 3b. Pushed, or detached: never moved. Told once per update of main.
    stamp["last_action"] = "reported, not merged (ruled 2026-09-14)"
    if not already_told:
        stamp["last_told"] = told
        advice = DETACHED_ADVICE if state_key == "detached" else LEAVE_IT_ADVICE
        tell(f"{heading}{older}{note}\n{advice}")
    write_stamp(stamp_path, stamp)


def reference_checkout_of(checkout: Path):
    """The main worktree of the same repository — the machine's reference copy."""
    listing = run_git(["worktree", "list", "--porcelain"], checkout, timeout=15)
    if listing.returncode != 0:
        return None
    for line in listing.stdout.splitlines():
        if line.startswith("worktree "):
            return Path(line.split(" ", 1)[1])
    return None


def fast_forward_reference_checkout(reference: Path, interval_seconds: int,
                                    announce_success: bool = True) -> None:
    """ff-only pull of a checkout parked on main; never a real merge.

    Safe by construction only when the reference carries nothing of its own:
    any local commit, any tracked change, any in-progress operation, and it
    is left alone with a line saying so — to the USER, because a reference
    checkout that cannot update is someone having left work where none
    belongs, which is the kind of thing the user asked to hear (ruled
    2026-09-15). A success is routine: announced only for the operator-facing
    --reference-pull, which launchers print at launch.
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
    if announce_success:
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

    # Stop-hook mode: the session's own checkout, then the machine's reference
    # copy. --cwd means "no stdin": an ad-hoc run on a terminal would otherwise
    # block forever waiting for a payload nobody is going to type.
    payload = {}
    if arguments.cwd is None:
        try:
            payload = json.loads(sys.stdin.read() or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {}
    session_cwd = (Path(arguments.cwd) if arguments.cwd is not None
                   else Path(payload.get("cwd") or "."))

    # One exit, one flush: an early return here would be a silent hook, which
    # is the failure mode this queue introduces if it is not funnelled.
    root = checkout_root(session_cwd)
    if root is not None:
        branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"], root,
                         timeout=15).stdout.strip()
        if branch == "main":
            # A session seated in the reference copy itself: ff-only, never
            # merge, and no telling — it has no branch of its own to be told
            # about, and this path keeps it current.
            fast_forward_reference_checkout(root, arguments.interval_seconds,
                                            announce_success=False)
        else:
            catch_up_session_checkout(root, arguments.interval_seconds)
            reference = reference_checkout_of(root)
            if reference is not None and reference != root:
                fast_forward_reference_checkout(reference, arguments.interval_seconds,
                                                announce_success=False)
    flush_hook_output()
    return 0


if __name__ == "__main__":
    sys.exit(main())
