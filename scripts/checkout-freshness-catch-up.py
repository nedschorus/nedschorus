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
     merge commit from main on the working branch whose parents merge cleanly
     both with git's rename detection and without it (ruled out 2026-09-14,
     nedschorus#324; one whose parents CONFLICT either way is the hand-merge
     the user allowed 2026-09-21 and is not reported), or a pushed
     head whose history was rewritten (an amend or rebase after a push, ruled
     out 2026-09-08). What they find is the ONLY thing the user hears from
     this hook — "If the agents are doing the wrong thing, or not doing the
     right thing, that's when I probably need to be told" (ruled 2026-09-15).
     Routine drift is never reported to the user; the stamp carries the
     numbers for the status line.
  4. If the branch is behind origin/main and has NEVER been pushed, REBASES
     it onto origin/main here, and tells the agent at its next turn what
     moved and which files changed. Skips a dirty tree; aborts cleanly on a
     conflict and names the files. This is not the merge #324 removed: that
     landed merge commits on FROZEN heads; this moves only heads nobody else
     has, creates no merge commit, and leaves the pushed-head rule untouched.
     Walked and ruled 2026-09-15 (docs/walk/keeping-branches-current-telling-
     and-rebase). "Never pushed" takes two facts, not one: no branch of this
     name is on origin, AND none of the branch's own commits is on any remote
     branch. A branch cut under a new name at a pull request's pushed head
     passes the first test and fails the second; its commits are that pull
     request's, under review, so it is left alone like a pushed branch (head
     state "pushed-history", see head_state()).
  5. If the branch is behind and HAS been pushed, never moves it. The agent
     is TOLD, once per update of main: how far behind, which files main has
     changed that it lacks — named, grouped by why they matter, computed from
     `git diff --name-only --no-renames HEAD...origin/main`, never assumed —
     and to leave the branch alone and cut its next topic from origin/main.
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
report this script made was read by nobody. Every note the agent receives
ends by saying it is not for the user, because agents were repeating these
notes to him (ruled 2026-09-18: "you don't need to tell me what other agents
are doing").

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
# not exist"), and synthesizing 1 for a launch failure would make the two
# indistinguishable. Aligned here so the same function name does not mean two
# different things in two files.
GIT_DID_NOT_RUN = -1
DEFAULT_FETCH_INTERVAL_SECONDS = 300

# `git merge-tree --write-tree` exits 1 for a real conflict AND 1 for an
# argument it cannot resolve — measured on a deadbeef hash and recorded in
# scripts/branch-conflict-check.py's docstring. Every other exit — 128 for
# unrelated histories, 129 from a git too old for --write-tree or for -X,
# GIT_DID_NOT_RUN when git cannot be launched — is an error, not an answer.
# A conflict therefore has to prove itself twice: this exit code AND the merged
# tree's object id on stdout, which --write-tree prints first on a conflict and
# no error path prints at all.
MERGE_TREE_CONFLICT_EXIT_CODE = 1
MERGE_TREE_OID_LENGTHS = (40, 64)  # sha1 and sha256 object ids
MERGE_TREE_OID_CHARACTERS = "0123456789abcdef"

# In-progress operation markers: the reference fast-forward must not run in
# a tree that is mid-anything.
GIT_IN_PROGRESS_MARKERS = (
    "MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG",
    "rebase-merge", "rebase-apply",
)

# What the agent is told to DO, decided by one fact: whether the branch has
# ever been pushed. A never-pushed branch is rebased by this hook
# itself, so REBASE_ADVICE is what the agent gets only when the hook could
# not — a dirty tree, or a conflict it aborted. A pushed branch is never
# moved by anyone but its author, and then only forward.
# A pushed branch that conflicts with main is the one exception: no commit on
# top can clear a conflict, so it is cleared by a hand-merge (CLAUDE.md, "How a
# change reaches main"). Forbidding every merge here would send an agent with a
# conflict away from the one move that clears it.
# The runner selects the suites a change can affect, so no agent picks them by hand.
SELECTIVE_TEST_RUN_COMMAND = (
    "python3 scripts/run-all-test-suites.py "
    "--only-suites-whose-recorded-inputs-changed-since origin/main"
)
# The last line names the pre-push check because that check, not the agent,
# fetches origin and refuses a conflicting push.
REBASE_ADVICE = (
    "This branch has never been pushed, so nobody else has it. Bring the branch up "
    "to date now: commit or set aside any uncommitted work, run `git rebase "
    f"origin/main`, then run `{SELECTIVE_TEST_RUN_COMMAND}`.\n"
    "If the rebase stops on a conflict that you can resolve now, resolve the "
    "conflict and run `git rebase --continue`.\n"
    "If the rebase stops on a conflict that you cannot resolve now, run `git rebase "
    "--abort`, which puts everything back, and finish what you are doing first; this "
    "note comes back at each turn's end until the branch is up to date.\n"
    "A push that conflicts with origin/main is refused by the pre-push check, which "
    "names the conflicting commit; if you cannot resolve that conflict, stop and tell "
    "the user which files conflict: a conflict you cannot resolve changes the work "
    "you are doing with him, so the last line of this note does not forbid telling him."
)
LEAVE_IT_ADVICE = (
    "This branch is pushed, so its review may be running. Do not rebase or "
    "amend it. A fix for this topic is a new commit on top, pushed once. If it "
    "conflicts with main, clear the conflict with the hand-merge that "
    "scripts/branch-conflict-check.py describes. "
    "Start your next topic with `git checkout -b <name> origin/main`."
)
# A branch whose own commits are already on a remote branch, under another
# name: the shape a fix-round agent makes when it cuts a branch at a pull
# request's pushed head, because that pull request's own branch is checked out
# in another worktree. Rebasing it would rewrite the pull request's commits
# under their review, so it gets the pushed branch's instructions. Read by
# obsolete-file-edit-warning-hook.py too, so both hooks say the same thing.
PUSHED_HISTORY_ADVICE = (
    "This branch's commits are already on GitHub under another branch name, so the "
    "branch is treated as pushed and is not rebased: a pushed head may be under "
    "review, and a rebase would rewrite it. Do not rebase or amend those commits. A "
    "fix is a new commit on top. If it conflicts with main, clear the conflict with "
    "the hand-merge that scripts/branch-conflict-check.py describes."
)
DETACHED_ADVICE = "You are on a detached HEAD; check out your branch before working."
UNKNOWN_ADVICE = ("Your head state could not be determined (a git command failed); nothing "
                  "was changed. Check `git status` before working.")
AFTER_REBASE_ADVICE = f"Run `{SELECTIVE_TEST_RUN_COMMAND}`: your work now sits on newer code."

# Appended to EVERY note the agent receives, by tell() itself, so no note can
# forget it. Without it, agents relay these notes to the user, who does not
# need to hear what other agents merged.
NOT_FOR_THE_USER_ADVICE = (
    "Do not report this to the user: he does not need to hear that main moved, or "
    "what other agents merged, unless it changes the work you are doing with him."
)

# Categories worth naming, most consequential first, each labelled with WHY an
# agent should care where that is not self-evident. A file's category is
# decided by path, and the first match wins.
#
# nc-systems/ holds the project's systems kept whole — a system's code, its
# tests and its design of record in one directory — so a change there is
# neither a loose script nor a document the agent merely cites: the design it
# builds to may have moved under it. Without its own category it would fall to
# the catch-all and be reported under the least informative label. Placed
# above scripts/ because a system kept whole outranks a loose script, per
# "most consequential first" above.
DRIFT_PATH_CATEGORIES = (
    ("your standing instructions",
     lambda path: path == "CLAUDE.md" or path.endswith("/CLAUDE.md")),
    ("skills you run under",
     lambda path: path.startswith(".claude/skills/")),
    ("hooks and wiring that run on your work",
     lambda path: path.startswith(".claude/hooks/") or path == ".claude/settings.json"),
    ("systems you build on, code and design of record",
     lambda path: path.startswith("nc-systems/")),
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

    NAMED RATHER THAN ASSUMED. A fixed sentence such as "your tests, hooks,
    skills and documents here are older than main" is false wherever one of
    those kinds did not move, which is most gaps, and an agent that reads one
    false clause learns to discount the whole line. So the files are measured
    and only the kinds that moved are named.

    Three dots, not two: `HEAD...origin/main` diffs from the MERGE BASE, so it
    answers "what did main change that I do not have". Two dots would compare
    the trees outright and report this branch's OWN work as though main had
    changed it, claiming the branch's own new files as ones it was missing.

    --no-renames, because rename detection is on by default and prints only a
    rename's DESTINATION. Without the flag, a file main renamed away from the
    path this branch still holds it at goes unlisted — the one file guaranteed
    to conflict, since main has deleted that path. With it, a rename lists both
    paths: the old one main deleted and the new one main added. The same fix,
    for the same reason, is in obsolete-file-edit-warning-hook.py's
    obsolete_path_set(), so both programs run the same diff.
    """
    listed = run_git(["diff", "--name-only", "--no-renames", "HEAD...origin/main"],
                     checkout, timeout=30)
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
    """Queue text for the AGENT's context, ending with the line that says it
    is not for the user — here, the one place every note passes through."""
    AGENT_LINES.append(f"{text}\n{NOT_FOR_THE_USER_ADVICE}")


def flush_report() -> None:
    """Print everything queued, plain text — the operator-facing modes."""
    for queued_line in REPORT_LINES:
        print(queued_line)


def flush_hook_output() -> None:
    """The Stop hook's one JSON object: what the user sees, what the agent reads.

    A Stop hook's plain stdout on exit 0 reaches neither — only
    `UserPromptSubmit`, `SessionStart` and their kin get plain stdout added to
    the agent's context, so plain stdout here would be read by nobody.
    `systemMessage` is shown to the user;
    `hookSpecificOutput.additionalContext` is added to the AGENT's context.

    No `decision` field, ever: blocking costs the agent a turn, and this hook
    only tells. Silence stays meaningful: nothing queued prints nothing at all.
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
    fast-forward reports git's own refusal text, and a word matched in a
    translated message can be missed. Forcing the C locale keeps every
    message stable, whatever the host is configured for.
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


def remote_branches_holding_own_commits(checkout: Path):
    """The remote branches that already hold commits of this branch, as a list
    of names; [] when none does; None when git could not answer.

    "This branch's commits" are those in origin/main..HEAD, merge commits and
    the commits a merge brought in alike: if any one of them is on a remote
    branch, rebasing the branch would rewrite history someone else has. The
    test is a set difference of two local-ref walks, `origin/main..HEAD`
    against `HEAD --not --remotes`, so it needs no fetch and no network, and
    it sees past the agent's own new commits on top, which are on no remote
    branch yet, to the pushed commits beneath them. A third call, made only
    when a pushed commit is found, names the remote branches that hold the
    newest one, for the agent's message.

    Every remote-tracking ref counts, origin's and any other remote's, and so
    does a ref left behind by a branch deleted on GitHub: a commit that was
    ever pushed may be under review or in someone's hands, and leaving such a
    branch unrebased costs only a hand-merge if it ever conflicts.
    """
    own = run_git(["rev-list", "origin/main..HEAD"], checkout, timeout=30)
    if own.returncode != 0:
        return None
    own_commits = own.stdout.split()
    if not own_commits:
        return []
    not_on_any_remote = run_git(["rev-list", "HEAD", "--not", "--remotes"], checkout,
                                timeout=30)
    if not_on_any_remote.returncode != 0:
        return None
    unpushed = set(not_on_any_remote.stdout.split())
    # rev-list lists newest first, so this is the newest pushed commit: the one
    # a remote branch's tip is likeliest to be.
    newest_pushed = next((sha for sha in own_commits if sha not in unpushed), None)
    if newest_pushed is None:
        return []
    holders = run_git(["for-each-ref", "--format=%(refname:short)", "--contains",
                       newest_pushed, "refs/remotes"], checkout, timeout=15)
    names = holders.stdout.split() if holders.returncode == 0 else []
    # Already known to be on a remote branch; failing to name it changes
    # nothing about what may be done with it.
    return names or ["a remote branch"]


# How many of the remote branches holding a branch's commits the head state
# names before it counts the rest.
PUSHED_HISTORY_BRANCHES_NAMED = 2


def head_state(checkout: Path, branch: str):
    """(key, text) for where HEAD stands against its remote branch. The
    frozen-head rule in CLAUDE.md freezes a head the moment it is
    pushed, so "pushed and equal to origin/<branch>" is the fact the rule
    keys on; whether a pull request is open is not asked, because that
    needs gh and the network at every turn end, and the rule does not.

    PUSHED HISTORY UNDER A NEW NAME. No origin/<branch> does not, on its own,
    mean nobody else has the branch. An agent that fixes a pull request from
    a worktree of its own cannot check out the pull request's branch there,
    since git checks a branch out in one worktree at a time, so it cuts a new
    branch at the pushed head. That branch has no remote branch of its name,
    yet every commit under the agent's fix is the pull request's, under
    review. Read as "unpushed", the Stop hook would rebase it, moving the
    frozen head, and the obsolete-file warning would tell the agent to rebase
    it. So before answering
    "unpushed", the branch's own commits are checked against every remote
    branch, and a branch carrying any of them is "pushed-history": treated
    as pushed, never rebased. A new key rather
    than "pushed", because "pushed" says HEAD equals origin/<branch>, which
    is false here, and the head state is what the agent and the stamp read.
    A git failure in that check is "unknown", never "unpushed": "unpushed" is
    the one answer that authorises a rebase."""
    if branch in ("", "HEAD"):
        return "detached", "detached HEAD"
    remote = run_git(["rev-parse", "--verify", "--quiet", f"origin/{branch}"],
                     checkout, timeout=15)
    if remote.returncode == GIT_DID_NOT_RUN:
        # "git did not run" is not "no such ref": it must never read as
        # "unpushed", the one answer that authorises a rebase, and so must
        # match counts_against_main, which treats the same failure class as
        # unknowable.
        return "unknown", "head state unknowable (git did not run)"
    if remote.returncode != 0:
        holders = remote_branches_holding_own_commits(checkout)
        if holders is None:
            return "unknown", ("head state unknowable (git could not check whether this "
                               "branch's commits are on a remote branch)")
        if not holders:
            return "unpushed", "head unpushed"
        named = ", ".join(holders[:PUSHED_HISTORY_BRANCHES_NAMED])
        if len(holders) > PUSHED_HISTORY_BRANCHES_NAMED:
            named += f" and {len(holders) - PUSHED_HISTORY_BRANCHES_NAMED} more"
        return "pushed-history", (f"no branch of this name on origin, but its commits are "
                                  f"already on {named} (pushed history: a fix is a new "
                                  f"commit on top, never a rebase)")
    head = run_git(["rev-parse", "HEAD"], checkout, timeout=15).stdout.strip()
    if remote.stdout.strip() == head:
        return "pushed", (f"head pushed and equal to origin/{branch} (frozen: a fix is a "
                          "new commit on top, never an amend; a conflict with main is "
                          "cleared by a hand-merge)")
    local = run_git(["rev-list", "--count", f"origin/{branch}..HEAD"], checkout, timeout=30)
    count = local.stdout.strip() if local.returncode == 0 else "some"
    if count == "0":
        # HEAD is behind its own remote branch: the shape the fix-on-frozen-head
        # process leaves once the authoring seat fetches a fresh agent's fix
        # commit. The truth is that the remote is ahead.
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
        # its reviewer (CLAUDE.md's frozen-head rule). Named to the user.
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
        # exactly the tree nothing could inspect.
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


def merge_parents_conflict(checkout: Path, first_parent: str, second_parent: str) -> bool:
    """True only when git, re-merging these two already-resolved parent hashes,
    reports a CONFLICT under at least one of two strategies: with rename
    detection off (-X no-renames), or with git's default rename detection.
    False when neither re-merge reports one, whether each was clean or errored.

    TWO RE-MERGES, BECAUSE EACH SEES CONFLICTS THE OTHER MERGES CLEANLY, and a
    hand-merge of either kind is one the author had no choice about. The two
    paragraphs below say which hand-merge each re-merge exists to recognise.

    -X NO-RENAMES IS LOAD-BEARING, not tidiness. When main renames a file out
    of a directory while the branch holds edits to the old path, git's default
    rename detection follows the move silently and the parents re-merge CLEAN.
    GitHub's merge candidate does not follow it, so the branch shows
    CONFLICTING and has to be merged by hand. The conflict the author actually
    faced is the one seen WITHOUT rename detection, and with detection alone
    this function would return False for the exact case it exists to
    recognise.

    THE DEFAULT RE-MERGE IS LOAD-BEARING TOO. Some conflicts exist only WITH
    rename detection: a file added under a directory the other side moved is
    CONFLICT (file location), and -X no-renames merges it cleanly. Those are
    conflicts the author really faced, because scripts/branch-conflict-check.py
    asks git with detection on, and so do `git merge` and the pre-push hook that
    runs that check: the check prints VERDICT: CONFLICT, CLAUDE.md sends the
    author to the hand-merge, and git's own merge stops until it is resolved by
    hand. With the no-renames re-merge alone this function would return False
    for that hand-merge, and the user would be told the branch had made a
    banned catch-up merge. merges_from_main's docstring says why asking both
    ways loses nothing.

    EXIT 1 IS NOT ENOUGH ON ITS OWN, for either re-merge. merge-tree exits 1 for
    an argument it cannot resolve as well as for a conflict
    (scripts/branch-conflict-check.py's docstring, measured on a deadbeef hash).
    That file resolves both arguments first so that exit 1 can only mean
    conflict, and the caller here does the same — but the cost of being wrong
    differs by direction, so this one also requires the answer itself:
    --write-tree prints the merged tree's object id as its first line, on a
    conflict as much as on a clean merge, and no error path prints one.

    EVERY OTHER OUTCOME IS AN ERROR, AND AN ERROR IS NEVER A CONFLICT. A git too
    old for --write-tree (before 2.38) or for -X exits 129 on usage, unrelated
    histories exit 128, an unlaunchable git is GIT_DID_NOT_RUN. A re-merge that
    errors says nothing, so the answer is the other re-merge's alone: the merge
    is skipped only when that one positively shows a conflict, and is reported
    when that one is clean or errors as well. With both erroring this detector
    degrades to exactly what it did before this exception existed — it reports
    every merge from main. A false report is visible to the user and corrects
    itself in one exchange; a misbehaviour that is skipped is invisible for
    good. Nothing here can block a turn either way: the caller only shortens a
    list.
    """
    for strategy_arguments in (["-X", "no-renames"], []):
        remerged = run_git(["merge-tree", "--write-tree", *strategy_arguments,
                            first_parent, second_parent], checkout, timeout=60)
        if remerged.returncode != MERGE_TREE_CONFLICT_EXIT_CODE:
            continue
        merged_tree = remerged.stdout.split("\n", 1)[0].strip()
        if (len(merged_tree) in MERGE_TREE_OID_LENGTHS
                and all(character in MERGE_TREE_OID_CHARACTERS for character in merged_tree)):
            return True
    return False


def merges_from_main(checkout: Path):
    """Short SHAs of merge commits on this branch whose second parent lies on
    origin/main AND whose two parents merge cleanly, with rename detection and
    without it — the catch-up merge CLAUDE.md bans, because such merges moved
    frozen heads under running reviews.

    A merge of another topic branch is not the banned thing, so the second
    parent is tested for being on main rather than every merge being flagged.
    A branch that carries older catch-up merges is flagged once, which is
    correct: those merges are real and the user has not been told of them.

    WHY A CLEAN RE-MERGE IS THE TEST. CLAUDE.md allows one exception: a branch
    that genuinely CONFLICTS with main merges origin/main in by hand, once,
    resolves only the conflict, reruns its tests and announces the new head.
    That hand-merge has the same shape as the banned one — a merge commit whose
    second parent is on main — so shape alone would report every author who
    obeys the rule. Re-merging the parents tells the two apart: parents that
    CONFLICT mean the author had no choice, so the merge is skipped; parents
    that merge cleanly mean the merge was unnecessary, which is the banned
    catch-up, and it is still reported. Over main's own history, the merges
    this skips are, almost to a merge, ones whose commit messages say they
    resolved a conflict and whose recorded trees differ from the clean
    automatic merge of their parents.

    WHY THE TEST ASKS BOTH WAYS. A directory rename produces CONFLICT (file
    location), which only rename DETECTION can see, so -X no-renames merges it
    cleanly and would report a real conflict resolution as a catch-up.
    scripts/branch-conflict-check.py's own answer from git and `git merge` both
    use default rename detection, so parents that conflict under it are a
    branch that check reports as VERDICT: CONFLICT and a merge that stopped
    until it was resolved by hand: a conflict resolution, not a catch-up. No
    catch-up merge is made to look conflicted by rename detection alone, so
    asking both ways loses no misbehaviour. merge_parents_conflict therefore
    re-merges both ways and the merge is skipped when either conflicts.

    WHAT ASKING BOTH WAYS GIVES UP. CLAUDE.md's conflict rule has two branches:
    a conflict with work main deleted or replaced closes the pull request, and
    any other conflict is cleared by a hand-merge. This detector does not tell
    the two apart: a merge made over a modify/delete conflict is skipped, and
    so is one made over a branch that RENAMED a file main deleted, which
    conflicts only with rename detection.
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
        if on_main.returncode != 0:
            continue
        first = run_git(["rev-parse", "--verify", "--quiet", f"{sha}^1"], checkout, timeout=15)
        # A first parent that does not resolve cannot be re-merged, so the merge
        # is reported: an error is not an answer.
        if first.returncode == 0 and merge_parents_conflict(checkout, first.stdout.strip(),
                                                            second.stdout.strip()):
            continue
        flagged.append(sha[:12])
    return flagged


def rebase_never_pushed_branch(checkout: Path, git_dir: Path):
    """Move a never-pushed branch onto origin/main, or say why not.

    Returns (outcome, detail): "rebased"; "skipped" with the blockers; "conflict"
    with the conflicting paths, the tree put back exactly as it was; or
    "abort-failed", the one outcome that is a fault — the tree was left
    mid-rebase — and is reported to the user.

    WHY THIS HOOK MAY MOVE A BRANCH AT ALL, when it must never merge: a merge
    from main lands a merge commit on a head that may be FROZEN — pushed, with
    a review running. This is a rebase of a branch that has NEVER been pushed:
    no review exists to disturb, no merge commit is created, and the
    pushed-head rule is untouched. Rewriting files under a running agent is
    answered by telling the agent, at its next turn, exactly which files
    moved.

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
    def rebase_state_exists() -> bool:
        return any((git_dir / marker).exists() for marker in ("rebase-merge", "rebase-apply"))

    if not rebase_state_exists():
        # git refused BEFORE detaching HEAD — an untracked file at a path main
        # just added ("could not detach HEAD"), or --no-autostash on a dirty
        # tree. Nothing was touched and there is nothing to abort: `git rebase
        # --abort` here exits 128 "no rebase in progress", and reading that as
        # a failed abort would tell the user the tree was left mid-rebase,
        # every turn end, about a tree git never entered.
        detail = "; ".join(line.strip() for line in rebased.stderr.splitlines() if line.strip())
        return "refused", detail or "no detail"
    conflicting = run_git(["diff", "--name-only", "--diff-filter=U"], checkout,
                          timeout=15).stdout.split()
    aborted = run_git(["rebase", "--abort"], checkout, timeout=30)
    # Whether the abort worked is decided by whether rebase state REMAINS, never
    # by the abort's exit code: the state on disk is the truth about the tree.
    # And a failed abort shows ITS OWN error, not the rebase's.
    if rebase_state_exists():
        return "abort-failed", (aborted.stderr.strip() or rebased.stderr.strip() or "no detail")
    return "conflict", ", ".join(conflicting) or (rebased.stderr.strip() or "no detail")


def fetch_failure_note(stamp: dict, what_may_be_stale: str = "this list") -> str:
    """One line when the numbers rest on a fetch that failed, or "".
    A stale list must say it is stale. The reference checkout's path passes
    its own subject, because what may be stale there is a count, not a
    list."""
    if stamp.get("fetch_ok", True):
        return ""
    when = time.strftime("%H:%M", time.localtime(stamp.get("fetched_at", 0)))
    return f"\n(fetch failed at {when}; {what_may_be_stale} may be stale)"


def catch_up_session_checkout(checkout: Path, interval_seconds: int) -> None:
    """The Stop-hook body for the session's own checkout:

      1. Misbehaviour detectors run EVERY turn, before and independent of the
         drift path — a branch that merged main into itself is 0 behind, which
         is exactly where a drift-first design would return early. What they
         find goes to the USER, and it is the only thing the user hears: agents
         doing the wrong thing, or not doing the right thing. Routine drift is
         not reported to the user at all.
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
    # The heading must be true of every path the diff lists: changed, added,
    # and deleted. "Older here than on main" would be false of a file main
    # ADDED, since this checkout has no copy at all.
    changed_on_main_clause = (f"\nChanged on main since your merge base:\n{listing}"
                              if listing else "")
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
                 f"never pushed, so nothing was under review).{changed_on_main_clause}\n"
                 f"{AFTER_REBASE_ADVICE}")
        elif outcome == "abort-failed":
            # No repeat key needed: this fires at most once per real
            # occurrence, and NOT because merge_blockers sees the rebase
            # marker — on this path merge_blockers is consulted only inside
            # rebase_never_pushed_branch, which is never reached again (its
            # other caller, fast_forward_reference_checkout, is the reference
            # checkout's path, not this one). A tree parked mid-rebase has a
            # DETACHED HEAD that DESCENDS from origin/main's tip — the tip
            # plus whatever commits were replayed before the conflict — so at
            # the next turn end drift_facts counts 0 behind and returns
            # early; and were main to advance meanwhile, head_state answers
            # "detached", not "unpushed", so this branch is not taken either.
            # While main is still nothing is said
            # on either channel; once main advances the agent is told about
            # its detached HEAD once per main tip. The user channel stays
            # empty either way.
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
                if outcome == "skipped":
                    reason = f"Not updated: {detail}."
                elif outcome == "refused":
                    reason = f"Not updated: git refused — {detail}."
                else:
                    reason = (f"A rebase onto origin/main was tried and put back: it "
                              f"conflicts on {detail}.")
                tell(f"{heading} {reason}{changed_on_main_clause}{note}\n{REBASE_ADVICE}")
        write_stamp(stamp_path, stamp)
        return

    # 3b. Pushed, or detached: never moved. Told once per update of main.
    stamp["last_action"] = "reported, not merged (ruled 2026-09-14)"
    if not already_told:
        stamp["last_told"] = told
        advice = {"detached": DETACHED_ADVICE, "unknown": UNKNOWN_ADVICE,
                  "pushed-history": PUSHED_HISTORY_ADVICE}.get(state_key, LEAVE_IT_ADVICE)
        tell(f"{heading}{changed_on_main_clause}{note}\n{advice}")
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
                                    operator_facing: bool = True) -> None:
    """ff-only pull of a checkout parked on main; never a real merge.

    Safe by construction only when the reference carries nothing of its own:
    any local commit, any tracked change, any in-progress operation, and it
    is left alone with a line saying so — to the USER, because a reference
    checkout that cannot update is someone having left work where none
    belongs, which is the kind of thing the user asked to hear.

    Two audiences, two rates. operator_facing=True is --reference-pull, which
    launchers print at launch: every outcome is reported, every time,
    including a success. operator_facing=False is the Stop hook, whose
    report() is the user's systemMessage: a success is silent, and a skip or
    refusal is reported ONCE PER REASON, keyed in the stamp as
    `last_reference_blockers` — never per turn, and never on `behind`, which
    would re-fire at every update of main. This function runs at every turn
    end off local refs regardless of the fetch throttle, so without that key
    a reference with one uncommitted edit would name itself to the user at
    every turn end.

    A failed fetch is a reason like any other: otherwise a reference whose
    fetch failed would count "0 behind" off the refs that fetch never updated
    and return silently, which reads as up to date. Its reason key is the
    constant "fetch failed", not the failure's time, so a network that stays
    down is reported once rather than at every fetch interval; the key is
    cleared by the next run that is 0 behind off a fetch that worked. The
    skip line's key is its blockers plus "fetch failed" while the fetch is
    failing, so the same blockers are reported again when the fetch starts or
    stops failing; with the blockers alone, a failure that began after the
    blockers were reported would never reach the user.
    """
    git_dir = git_directory(reference)
    if git_dir is None:
        return
    stamp_path = git_dir / STAMP_FILE_NAME
    stamp = fetch_if_stale(reference, stamp_path, interval_seconds)
    fetch_note = fetch_failure_note(stamp, "this count")

    def report_reason(reasons, line):
        """Report a skip or refusal: always for the operator, once per reason
        for the user."""
        if operator_facing or stamp.get("last_reference_blockers") != reasons:
            report(line)
        stamp["last_reference_blockers"] = reasons

    counts = counts_against_main(reference)
    if counts is None:
        # Unknowable is not "still whatever it was" — same silent-safety rule
        # the seat's own path applies. Leaving the previous numbers in place
        # renders a stale count as knowledge.
        stamp["behind"] = stamp["ahead"] = None
        write_stamp(stamp_path, stamp)
        return
    behind, ahead = counts
    stamp["behind"], stamp["ahead"] = behind, ahead

    if behind == 0:
        if fetch_note:
            stamp["last_action"] = "reference fetch failed"
            report_reason(["fetch failed"],
                          f"catch-up: reference checkout {reference} is 0 behind origin/main "
                          f"as last fetched{fetch_note}")
        else:
            stamp.pop("last_reference_blockers", None)
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
        report_reason(real_blockers + (["fetch failed"] if fetch_note else []),
                      f"catch-up: reference checkout {reference} is {behind} behind and was "
                      f"left alone — {'; '.join(real_blockers)}{fetch_note}")
        write_stamp(stamp_path, stamp)
        return

    pulled = run_git(["merge", "--ff-only", "origin/main"], reference, timeout=120)
    if pulled.returncode != 0:
        detail = pulled.stderr.strip() or "no detail"
        stamp["last_action"] = "reference ff-only refused"
        report_reason([f"ff-only refused: {detail}"],
                      f"catch-up: reference checkout {reference} could not fast-forward: "
                      f"{detail}")
        write_stamp(stamp_path, stamp)
        return
    stamp["behind"], stamp["last_action"] = 0, f"reference fast-forwarded {behind}"
    stamp.pop("last_reference_blockers", None)
    write_stamp(stamp_path, stamp)
    if operator_facing:
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
        # number.
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
                                            operator_facing=False)
        else:
            catch_up_session_checkout(root, arguments.interval_seconds)
            reference = reference_checkout_of(root)
            if reference is not None and reference != root:
                fast_forward_reference_checkout(reference, arguments.interval_seconds,
                                                operator_facing=False)
    flush_hook_output()
    return 0


if __name__ == "__main__":
    sys.exit(main())
