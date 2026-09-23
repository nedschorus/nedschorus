#!/usr/bin/env python3
"""Cases for branch-conflict-check.py.

Every case in the first half is a measurement taken by hand on 2026-09-22 that
the prose version of this instruction got wrong. They are cases so that the
next person does not have to re-measure them, and so a regression cannot pass
silently.

The second half, added 2026-09-23, pins the whole answer matrix -- every
combination of git's answer, GitHub's answer, and whether GitHub is answering
about the commit checked -- by exit code AND whole output, then runs the
program itself against throwaway repositories and a stub gh. The user ruled
the behaviour stays as it is and that "this stuff has to carefully tested,
both success and failure cases" (walk "merge-lane-mac-helper-open-items-and-
questions-2026-09-23", item 3, 23:07Z).

Run: scripts/branch-conflict-check-test.py
Exit codes: 0 all passed, 1 any failed.
"""

import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "branch_conflict_check", HERE / "branch-conflict-check.py")
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)

RESOLVED_HEAD = "a" * 40
RESOLVED_BASE = "b" * 40
# Subjects the fake git reports for the two resolved commits. Any other hash
# (OTHER_COMMIT below, a GitHub head never fetched) has no subject locally.
COMMIT_SUBJECTS = {
    RESOLVED_HEAD: "Head commit subject",
    RESOLVED_BASE: "Base commit subject",
}
HEAD_LABEL = 'commit %s ("Head commit subject")' % RESOLVED_HEAD[:12]
BASE_LABEL = 'commit %s ("Base commit subject")' % RESOLVED_BASE[:12]

failures = []
case_count = 0


def case(name, condition):
    global case_count
    case_count += 1
    if not condition:
        failures.append(name)
        print("FAIL  %s" % name)


def fake_runner(*, resolves=True, base_resolves=None, head_resolves=None,
                merge_tree_status=0, gh_results=None, log=None,
                fetch_status=0, gh_head=RESOLVED_HEAD, gh_head_status=0,
                full_refs=None, gh_base="main", gh_base_status=0):
    """A runner that answers git and gh without touching either.

    base_resolves and head_resolves override `resolves` for one side, so a case
    can make exactly one rev unresolvable. Without that, both guards see a
    failure, the first one returns, and the second is never exercised -- which
    is how the head guard went unpinned until mutation testing found it.

    gh_head is the pushed head GitHub answers about, and defaults to the hash
    the fake git resolves HEAD to -- the matching case, so a case that says
    nothing about it gets a GitHub verdict that counts. gh_results answers only
    the mergeability reads; the headRefOid read is answered from gh_head, so
    adding it did not shift any existing case's queue.

    full_refs maps a rev to what `git rev-parse --symbolic-full-name` prints
    for it; a rev not in it gets refs/remotes/<rev> when it contains a slash,
    which is right for origin/main, the base every older case uses. gh_base is
    the branch the pull request targets, answered apart from the queue for the
    same reason as gh_head.
    """
    refs = dict(full_refs or {})
    gh_queue = list(gh_results or [])
    base_ok = resolves if base_resolves is None else base_resolves
    head_ok = resolves if head_resolves is None else head_resolves

    def runner(command):
        if log is not None:
            log.append(command)
        if command[:2] == ["git", "fetch"]:
            return fetch_status, ""
        if command[:3] == ["git", "rev-parse", "--symbolic-full-name"]:
            rev = command[-1]
            if rev in refs:
                return (0, refs[rev]) if refs[rev] is not None else (128, "")
            return 0, ("refs/remotes/" + rev) if "/" in rev else ""
        if command[:2] == ["git", "rev-parse"]:
            rev = command[-1]
            is_base = rev.startswith("origin/") or rev.startswith("upstream/") \
                or rev in ("main", "main^{commit}") or rev.startswith(RESOLVED_BASE)
            if not (base_ok if is_base else head_ok):
                return 1, ""
            return 0, RESOLVED_BASE if is_base else RESOLVED_HEAD
        if command[:2] == ["git", "merge-tree"]:
            return merge_tree_status, ""
        if command[:2] == ["git", "log"]:
            subject = COMMIT_SUBJECTS.get(command[-1])
            return (0, subject) if subject else (128, "")
        if command[:2] == ["gh", "pr"]:
            if "headRefOid" in command:
                return gh_head_status, (gh_head or "")
            if "baseRefName" in command:
                return gh_base_status, (gh_base or "")
            if not gh_queue:
                return 1, ""
            return gh_queue.pop(0)
        raise AssertionError("unexpected command: %r" % (command,))

    return runner


def mergeability_reads(log):
    """How many times the log asked GitHub for mergeability.

    Counted apart from the headRefOid read, which is a gh call too.
    """
    return sum(1 for c in log if c[:2] == ["gh", "pr"] and "mergeable" in c)


def run(runner, pull_request=None, reads=3, sleeps=None, fetch=True,
        remote=CHECK.DEFAULT_FETCH_REMOTE, base="origin/main"):
    return CHECK.check(
        "HEAD", base, pull_request,
        runner=runner,
        sleep=(sleeps.append if sleeps is not None else (lambda _s: None)),
        reads=reads, sleep_seconds=7, fetch=fetch, remote=remote)


# --- the trap that would have sent agents hand-merging over a typo -----------
# `git merge-tree --write-tree origin/main <bad hash>` exits 1, the SAME code as
# a real conflict (verified against a deadbeef hash, 2026-09-22). So an
# unresolvable rev must be caught BEFORE merge-tree, and reported as its own
# thing rather than as a conflict.
status, lines = run(fake_runner(head_resolves=False))
case("an unresolvable HEAD exits 2, not 1", status == CHECK.EXIT_BAD_INVOCATION)
case("an unresolvable HEAD says UNRESOLVED, not CONFLICT",
     lines[0].startswith("UNRESOLVED:") and "CONFLICT" not in lines[0])
case("an unresolvable HEAD names the head, not the base",
     "head HEAD" in lines[0])

status, lines = run(fake_runner(base_resolves=False))
case("an unresolvable BASE exits 2, not 1", status == CHECK.EXIT_BAD_INVOCATION)
case("an unresolvable BASE names the base, not the head",
     "base origin/main" in lines[0])

log = []
run(fake_runner(head_resolves=False, log=log))
case("merge-tree is never reached when the head does not resolve",
     not any(c[:2] == ["git", "merge-tree"] for c in log))

log = []
run(fake_runner(base_resolves=False, log=log))
case("merge-tree is never reached when the base does not resolve",
     not any(c[:2] == ["git", "merge-tree"] for c in log))

# --- the two plain answers ---------------------------------------------------
status, lines = run(fake_runner(merge_tree_status=0))
case("clean exits 0", status == CHECK.EXIT_NO_CONFLICT)
case("clean says CLEAN", lines[0].startswith("VERDICT: CLEAN"))

status, lines = run(fake_runner(merge_tree_status=1))
case("a conflict exits 1", status == CHECK.EXIT_CONFLICT)
case("a conflict says CONFLICT", lines[0].startswith("VERDICT: CONFLICT"))
case("a conflict says what to do about it",
     any("into the branch by hand" in l for l in lines))

# A merge-tree status that is neither 0 nor 1 is NO ANSWER, not a conflict.
# git 2.55.0 exits 129 for an option it does not know and 128 for unrelated
# histories, measured 2026-09-22; a read-only object database is a third
# trigger, because --write-tree creates temporary data, and there merge-tree
# exits 128 on a merge that is actually clean.
#
# The open question these cases used to leave is RULED (user, 2026-09-22): such
# a status exits 2, the program's existing "no trustworthy answer" code. So the
# safety-only assertion below is now tightened to name the exit it must take.
for no_answer_status in (128, 129, 2, 127):
    status, lines = run(fake_runner(merge_tree_status=no_answer_status))
    case("merge-tree status %d exits 2, not a conflict" % no_answer_status,
         status == CHECK.EXIT_BAD_INVOCATION)
    case("merge-tree status %d is never reported CLEAN" % no_answer_status,
         not lines[0].startswith("VERDICT: CLEAN"))
    case("merge-tree status %d is never reported CONFLICT" % no_answer_status,
         not lines[0].startswith("VERDICT: CONFLICT"))
    case("merge-tree status %d never issues the hand-merge instruction"
         % no_answer_status,
         not any("into the branch by hand" in line for line in lines))
    case("merge-tree status %d names the status git returned" % no_answer_status,
         str(no_answer_status) in lines[0])

# The hand-merge instruction is the damage this prevents: before the ruling a
# 128 printed CONFLICT carrying it, sending an agent to resolve a conflict that
# does not exist. 0 and 1 keep their meanings, asserted above.
status, lines = run(fake_runner(merge_tree_status=128))
case("a no-answer status says the run gave no verdict",
     lines[0].startswith("UNANSWERED:"))
case("a no-answer status tells the agent not to hand-merge on it",
     "Do not merge by hand on this result." in lines)

# GitHub is not consulted when git could not answer: the run returns before the
# pull-request branch, so no gh call is made and no verdict can overrule a
# non-answer.
log = []
status, lines = run(fake_runner(merge_tree_status=128, log=log), pull_request=1)
case("a no-answer status does not consult GitHub",
     not any(c[:1] == ["gh"] for c in log))

# --- UNKNOWN: measured at eight of nine open pull requests after main moved ---
status, lines = run(
    fake_runner(merge_tree_status=0, gh_results=[(0, "UNKNOWN")] * 3),
    pull_request=600, reads=3)
case("UNKNOWN throughout still reports a verdict",
     lines[0].startswith("VERDICT: CLEAN"))
case("UNKNOWN throughout is disclosed",
     any(l.startswith("DISCLOSURE:") and "had not settled" in l for l in lines))
case("UNKNOWN throughout never claims GitHub agreed",
     not any("MERGEABLE" in l for l in lines))

sleeps = []
run(fake_runner(merge_tree_status=0, gh_results=[(0, "UNKNOWN")] * 3),
    pull_request=600, reads=3, sleeps=sleeps)
case("the UNKNOWN poll is bounded and does not sleep after its last read",
     len(sleeps) == 2)

log = []
run(fake_runner(merge_tree_status=0,
                gh_results=[(0, "UNKNOWN"), (0, "MERGEABLE"), (0, "MERGEABLE")],
                log=log),
    pull_request=600, reads=3)
case("polling stops as soon as GitHub settles",
     mergeability_reads(log) == 2)

# --- the two oracles disagreeing --------------------------------------------
# Measured 2026-09-16 on PR 353: git merged clean by following a rename where
# GitHub still reported CONFLICTING. GitHub decides whether the merge is
# allowed, so its CONFLICTING stands.
status, lines = run(
    fake_runner(merge_tree_status=0, gh_results=[(0, "CONFLICTING")]),
    pull_request=353, reads=3)
case("GitHub CONFLICTING overrules a clean git", status == CHECK.EXIT_CONFLICT)
case("the override is disclosed rather than silent",
     any("GitHub decides" in l for l in lines))

status, lines = run(
    fake_runner(merge_tree_status=1, gh_results=[(0, "MERGEABLE")]),
    pull_request=600, reads=3)
case("a git conflict is not waved through by GitHub MERGEABLE",
     status == CHECK.EXIT_CONFLICT)
case("that disagreement is disclosed too",
     any("not one to attempt" in l for l in lines))

# --- the two oracles must be answering about the SAME commit -----------------
# GitHub answers about the pull request's PUSHED head; git answers about
# whatever --head names. Nothing tied them together until 2026-09-22, and
# reproduced at the merge-lane seat that day, the gap let GitHub's verdict about
# one commit overrule git's about another:
#   branch-conflict-check.py --no-fetch --head origin/main --pull-request 605
# printed CONFLICT for origin/main against origin/main -- main conflicting with
# ITSELF -- because 605 genuinely conflicts. In the workflow it is worse: after
# the hand merge the CONFLICT message orders, the local HEAD is the merge commit
# while GitHub still answers about the old pushed head, so a rerun orders the
# merge that just happened.
OTHER_COMMIT = "c" * 40

# The matching case: nothing changes, GitHub still overrules a clean git.
status, lines = run(
    fake_runner(merge_tree_status=0, gh_head=RESOLVED_HEAD,
                gh_results=[(0, "CONFLICTING")]),
    pull_request=353, reads=3)
case("GitHub still overrules when it is answering about the checked commit",
     status == CHECK.EXIT_CONFLICT)

# The differing case: GitHub does not get to overrule git about another commit.
status, lines = run(
    fake_runner(merge_tree_status=0, gh_head=OTHER_COMMIT,
                gh_results=[(0, "CONFLICTING")]),
    pull_request=605, reads=3)
case("GitHub CONFLICTING about another commit does not overrule a clean git",
     status == CHECK.EXIT_NO_CONFLICT and lines[0].startswith("VERDICT: CLEAN"))
case("the commit mismatch is disclosed rather than silent",
     any(l.startswith("DISCLOSURE:") and "git's alone" in l for l in lines))
case("the disclosure names both commits, GitHub's and the one checked",
     any(OTHER_COMMIT[:12] in l and RESOLVED_HEAD[:12] in l for l in lines))

log = []
run(fake_runner(merge_tree_status=0, gh_head=OTHER_COMMIT,
                gh_results=[(0, "CONFLICTING")], log=log),
    pull_request=605, reads=3)
case("mergeability is not even polled when the commits differ",
     mergeability_reads(log) == 0)

# The mismatch withholds GitHub's verdict; it does not suppress git's own.
status, lines = run(
    fake_runner(merge_tree_status=1, gh_head=OTHER_COMMIT,
                gh_results=[(0, "MERGEABLE")]),
    pull_request=605, reads=3)
case("a commit mismatch still reports the conflict git itself found",
     status == CHECK.EXIT_CONFLICT)

# GitHub's head cannot be read at all: git's answer stands, as when gh fails.
status, lines = run(
    fake_runner(merge_tree_status=1, gh_head_status=1),
    pull_request=605, reads=3)
case("an unreadable GitHub head leaves git's answer standing",
     status == CHECK.EXIT_CONFLICT)
case("an unreadable GitHub head says GitHub could not be asked",
     any("could not be asked" in l for l in lines))

# --- gh unavailable ----------------------------------------------------------
status, lines = run(
    fake_runner(merge_tree_status=1, gh_results=[(1, "")]),
    pull_request=600, reads=3)
case("a failed gh leaves git's answer standing", status == CHECK.EXIT_CONFLICT)
case("a failed gh says so", any("could not be asked" in l for l in lines))

# --- the stale base, which no later guard can catch --------------------------
# A stale origin/main resolves perfectly well, so resolve_commit cannot tell a
# fresh base from a week-old one and the verdict is confidently wrong. The
# fetch is therefore part of the answer, and a failed fetch stops the run.
status, lines = run(fake_runner(fetch_status=1))
case("a failed fetch exits 2, not a verdict",
     status == CHECK.EXIT_BAD_INVOCATION)
case("a failed fetch says UNFETCHED, not CONFLICT or CLEAN",
     lines[0].startswith("UNFETCHED:")
     and "VERDICT" not in lines[0])
case("a failed fetch names the deliberate way past it",
     any("--no-fetch" in l for l in lines))

log = []
run(fake_runner(fetch_status=1, log=log))
case("nothing is resolved when the fetch fails",
     not any(c[:2] == ["git", "rev-parse"] for c in log))
case("merge-tree is never reached when the fetch fails",
     not any(c[:2] == ["git", "merge-tree"] for c in log))

log = []
run(fake_runner(merge_tree_status=0, log=log))
# Each ordering assertion checks membership first: a missing command must fail
# this case, not raise and stop every case after it from running.
kinds = [c[:2] for c in log]
case("the fetch happens, and happens before anything is resolved",
     ["git", "fetch"] in kinds and ["git", "rev-parse"] in kinds
     and kinds.index(["git", "fetch"]) < kinds.index(["git", "rev-parse"]))
case("the fetch uses the default remote", ["git", "fetch", "origin"] in log)

log = []
run(fake_runner(merge_tree_status=0, log=log), remote="upstream")
case("the fetch uses the remote it was given",
     ["git", "fetch", "upstream"] in log)

log = []
status, lines = run(fake_runner(merge_tree_status=0, log=log), fetch=False)
case("--no-fetch fetches nothing at all",
     not any(c[:2] == ["git", "fetch"] for c in log))
case("--no-fetch still reports a verdict", status == CHECK.EXIT_NO_CONFLICT)
case("--no-fetch discloses that the base was never refreshed",
     any(l.startswith("DISCLOSURE:") and "--no-fetch" in l for l in lines))

# --- the exact text of each message -----------------------------------------
# User-ruled 2026-09-22 (walk "merge-lane rulings owed and concerns", item 1):
# each message an agent acts on is one instruction per line with its condition,
# the rationale in the module docstring; and a commit is named as
# commit <hash> ("<subject>"). Pinned whole, so the old one-paragraph messages
# and bare hashes fail here.
status, lines = run(fake_runner(fetch_status=1))
case("UNFETCHED text is one instruction per line", lines == [
    "UNFETCHED: git fetch origin failed; do not act on any conflict answer "
    "until a run succeeds.",
    "Fix the fetch, then rerun.",
    "If origin/main in this checkout is already current, rerun with "
    "--no-fetch instead.",
])

status, lines = run(fake_runner(base_resolves=False))
case("UNRESOLVED base text is one instruction per line", lines == [
    "UNRESOLVED: base origin/main does not resolve to a commit; do not act on "
    "any conflict answer until a run succeeds.",
    "If origin/main is mistyped, correct --base, then rerun.",
    "If origin/main is not fetched, fetch it, then rerun.",
])

status, lines = run(fake_runner(head_resolves=False))
case("UNRESOLVED head text is one instruction per line", lines == [
    "UNRESOLVED: head HEAD does not resolve to a commit; do not act on any "
    "conflict answer until a run succeeds.",
    "If HEAD is mistyped, correct --head, then rerun.",
    "If HEAD is not fetched, fetch it, then rerun.",
])

status, lines = run(fake_runner(merge_tree_status=1))
case("CONFLICT text is one instruction per line, naming the commit", lines == [
    "VERDICT: CONFLICT -- %s conflicts with origin/main." % HEAD_LABEL,
    "Merge origin/main into the branch by hand, with the frozen head as "
    "first parent.",
    "Resolve the conflict and change nothing else in the merge.",
    "Before pushing, rerun the test suites for what the merge touched.",
])

status, lines = run(fake_runner(merge_tree_status=128))
case("UNANSWERED text is one instruction per line, naming both commits",
     lines == [
    "UNANSWERED: git merge-tree exited 128 merging %s into %s; do not act on "
    "it as a conflict or as clean." % (HEAD_LABEL, BASE_LABEL),
    "Do not merge by hand on this result.",
    "If either commit is missing from this checkout, fetch it, then rerun.",
    "If the two commits share no history, check that --head and --base name "
    "the right commits, then rerun.",
    "If the object database is not writable, run from a checkout where it "
    "is, then rerun.",
])

status, lines = run(fake_runner(merge_tree_status=0))
case("CLEAN names the commit by hash and quoted subject",
     lines == ["VERDICT: CLEAN -- %s does not conflict with origin/main. "
               "Nothing to do." % HEAD_LABEL])

# The GitHub-disclosure lines precede nothing: the verdict block stays first
# and contiguous even when GITHUB and DISCLOSURE lines were collected earlier.
status, lines = run(
    fake_runner(merge_tree_status=0, gh_results=[(0, "CONFLICTING")]),
    pull_request=353, reads=3)
case("the CONFLICT block stays contiguous ahead of GitHub's lines",
     len(lines) >= 5
     and lines[3] == "Before pushing, rerun the test suites for what the merge "
                     "touched." and lines[4].startswith("GITHUB:"))

# A commit git cannot read the subject of -- GitHub's pushed head, never
# fetched -- is named by its hash alone; the run's verdict is unchanged.
status, lines = run(
    fake_runner(merge_tree_status=0, gh_head=OTHER_COMMIT,
                gh_results=[(0, "CONFLICTING")]),
    pull_request=605, reads=3)
case("an unfetched GitHub head is named by hash alone, the checked head in full",
     any(("pushed head is commit %s, not the %s" % (OTHER_COMMIT[:12], HEAD_LABEL))
         in l for l in lines))
case("a subject that cannot be read does not change the verdict",
     status == CHECK.EXIT_NO_CONFLICT)

# --- the fetch must move the base -------------------------------------------
# `git fetch origin` moves refs/remotes/origin/* and nothing else, so with
# `--base main`, a local branch, the fetch runs and the base stays wherever main
# was left: a confident answer about old code. Raised by the Codex review cell
# on PR 635 after its merge; ruled "y" as superwalk item 10, 2026-09-23.
LOCAL_MAIN = {"main": "refs/heads/main"}
log = []
status, lines = run(fake_runner(merge_tree_status=0, full_refs=LOCAL_MAIN,
                                log=log), base="main")
case("a local-branch --base with fetching on exits 2, not a verdict",
     status == CHECK.EXIT_BAD_INVOCATION)
case("a local-branch --base says UNMATCHED", lines[0].startswith("UNMATCHED:"))
case("a local-branch --base is refused before merge-tree",
     not any(c[:2] == ["git", "merge-tree"] for c in log))
case("UNMATCHED text is one instruction per line", lines == [
    "UNMATCHED: --base main is not a branch of origin, the remote this run "
    "fetched, so the fetch did not move it; do not act on any conflict answer "
    "until a run succeeds.",
    "If you meant origin's branch, rerun with --base origin/<branch>.",
    "If you meant main exactly as this checkout has it, rerun with --no-fetch.",
])

# Another remote's branch is not moved by fetching this one either.
status, lines = run(fake_runner(merge_tree_status=0), remote="upstream")
case("a --base under a remote other than the fetched one is refused",
     status == CHECK.EXIT_BAD_INVOCATION and lines[0].startswith("UNMATCHED:"))
status, lines = run(fake_runner(merge_tree_status=0), remote="upstream",
                    base="upstream/main")
case("a --base under the fetched remote is answered",
     status == CHECK.EXIT_NO_CONFLICT)

# A pinned commit does not move with a fetch: refused with fetching on.
status, lines = run(fake_runner(merge_tree_status=0,
                                full_refs={RESOLVED_BASE: ""}),
                    base=RESOLVED_BASE)
case("a bare-hash --base with fetching on is refused",
     status == CHECK.EXIT_BAD_INVOCATION and lines[0].startswith("UNMATCHED:"))

# --no-fetch is the caller's statement that the base is what it wants, so the
# local branch and the pinned commit are both answered, with the disclosure.
status, lines = run(fake_runner(merge_tree_status=0, full_refs=LOCAL_MAIN),
                    base="main", fetch=False)
case("--no-fetch answers about a local-branch --base",
     status == CHECK.EXIT_NO_CONFLICT)
case("--no-fetch with a local-branch --base still discloses it",
     any(l.startswith("DISCLOSURE:") and "--no-fetch" in l for l in lines))

# A --base that does not resolve at all is still UNRESOLVED, not UNMATCHED:
# the symbolic lookup fails, and the resolve step reports it.
status, lines = run(fake_runner(base_resolves=False,
                                full_refs={"origin/main": None}))
case("an unresolvable --base is UNRESOLVED, not UNMATCHED",
     lines[0].startswith("UNRESOLVED:"))

# --- GitHub must be answering about the same base branch ---------------------
# A pull request's mergeability is computed against the branch it targets. When
# that is not the branch --base names -- a stacked pull request, a mistyped
# number -- GitHub's CONFLICTING is about a different merge and cannot
# overrule git. Same review, same ruling.
status, lines = run(
    fake_runner(merge_tree_status=0, gh_base="release",
                gh_results=[(0, "CONFLICTING")]),
    pull_request=700, reads=3)
case("GitHub CONFLICTING against another base branch does not overrule git",
     status == CHECK.EXIT_NO_CONFLICT and lines[0].startswith("VERDICT: CLEAN"))
case("the base-branch mismatch names both branches",
     any("targets release, not the main" in l for l in lines))
case("the base-branch mismatch is disclosed as git's alone",
     any(l.startswith("DISCLOSURE:") and "git's alone" in l for l in lines))

log = []
run(fake_runner(merge_tree_status=0, gh_base="release",
                gh_results=[(0, "CONFLICTING")], log=log),
    pull_request=700, reads=3)
case("mergeability is not even polled when the base branches differ",
     mergeability_reads(log) == 0)

# The matching branch, written as the remote's (origin/main) or as a local
# branch under --no-fetch (main), both count as GitHub's main.
status, lines = run(
    fake_runner(merge_tree_status=0, gh_results=[(0, "CONFLICTING")]),
    pull_request=353, reads=3)
case("origin/main matches a pull request targeting main",
     status == CHECK.EXIT_CONFLICT)
status, lines = run(
    fake_runner(merge_tree_status=0, full_refs=LOCAL_MAIN,
                gh_results=[(0, "CONFLICTING")]),
    pull_request=353, reads=3, base="main", fetch=False)
case("a local main under --no-fetch matches a pull request targeting main",
     status == CHECK.EXIT_CONFLICT)

# A bare hash names no branch, so no pull request's verdict is about it.
status, lines = run(
    fake_runner(merge_tree_status=0, full_refs={RESOLVED_BASE: ""},
                gh_results=[(0, "CONFLICTING")]),
    pull_request=353, reads=3, base=RESOLVED_BASE, fetch=False)
case("a bare-hash --base does not take GitHub's verdict",
     status == CHECK.EXIT_NO_CONFLICT)
case("a bare-hash --base says GitHub was not consulted",
     any(l.startswith("GITHUB: not consulted") and "names no branch" in l
         for l in lines))

# The pull request's base cannot be read: git's answer stands.
status, lines = run(
    fake_runner(merge_tree_status=1, gh_base_status=1),
    pull_request=353, reads=3)
case("an unreadable pull request base leaves git's answer standing",
     status == CHECK.EXIT_CONFLICT
     and any("could not be asked" in l for l in lines))

# --- the whole answer matrix, pinned by exit code and whole output ------------
# The cases above grew one measurement at a time, so several cells had their
# exit code pinned and not their lines, or the reverse, and some cells had
# neither: git clean with GitHub MERGEABLE, the commonest answer of all, was
# never asserted. Each cell below asserts both, so a regression in either
# fails. The expected lines are the program's own messages, copied from
# check() and its helpers, not recomputed by calling them.
def clean_block(base="origin/main", label=HEAD_LABEL):
    return ["VERDICT: CLEAN -- %s does not conflict with %s. Nothing to do."
            % (label, base)]


def conflict_block(base="origin/main", label=HEAD_LABEL):
    return [
        "VERDICT: CONFLICT -- %s conflicts with %s." % (label, base),
        "Merge %s into the branch by hand, with the frozen head as first "
        "parent." % base,
        "Resolve the conflict and change nothing else in the merge.",
        "Before pushing, rerun the test suites for what the merge touched.",
    ]


def verdict_block(exit_status, base="origin/main", label=HEAD_LABEL):
    if exit_status == CHECK.EXIT_CONFLICT:
        return conflict_block(base, label)
    return clean_block(base, label)


# (git's answer, merge-tree status, the exit git's answer alone gives)
GIT_ANSWERS = (
    ("clean", 0, CHECK.EXIT_NO_CONFLICT),
    ("conflict", 1, CHECK.EXIT_CONFLICT),
)
GITHUB_FAILED = "GITHUB: could not be asked (gh failed) -- git's answer stands"
GITHUB_DECIDES = (
    "DISCLOSURE: git finds no conflict but GitHub reports CONFLICTING; GitHub "
    "decides whether the merge is allowed, so the branch still needs the hand "
    "merge.")
NOT_ONE_TO_ATTEMPT = (
    "DISCLOSURE: git finds a conflict but GitHub reports MERGEABLE; treating "
    "it as a conflict, because a merge that git cannot do is not one to "
    "attempt.")


def github_line(verdict, reads):
    return "GITHUB: %s after %d read(s)" % (verdict, reads)


def unsettled(reads):
    return ("DISCLOSURE: GitHub had not settled after %d read(s); this verdict "
            "is git's alone. Say so in the pull request." % reads)


def no_fetch_disclosure(base="origin/main"):
    return ("DISCLOSURE: --no-fetch, so %s is whatever this checkout already "
            "had; a stale base gives a confident wrong answer." % base)


def gh_calls(log):
    return [c for c in log if c[:1] == ["gh"]]


def gh_reads_of(log, field):
    return sum(1 for c in log if c[:2] == ["gh", "pr"] and field in c)


# Axis A absent: no --pull-request. GitHub is never asked, and the output is
# git's verdict alone, plus the --no-fetch disclosure when the fetch is skipped.
for git_name, merge_status, git_exit in GIT_ANSWERS:
    for fetch in (True, False):
        log = []
        status, lines = run(fake_runner(merge_tree_status=merge_status, log=log),
                            fetch=fetch)
        label = "no --pull-request, git %s, %s" % (
            git_name, "fetching" if fetch else "--no-fetch")
        want = verdict_block(git_exit) + ([] if fetch else [no_fetch_disclosure()])
        case(label + ": the exit is git's", status == git_exit)
        case(label + ": the whole output", lines == want)
        case(label + ": gh is never run", gh_calls(log) == [])

# Axis A equal, axis C every answer: GitHub is answering about the checked
# commit and the branch --base names, so its verdict counts as the docstring
# says. (GitHub's answer, the mergeability reads it gives, {git's answer: (exit,
# lines after the verdict block)}, mergeability reads taken, sleeps taken)
MATCHED_HEAD_CELLS = [
    ("MERGEABLE at once", [(0, "MERGEABLE")],
     {"clean": (CHECK.EXIT_NO_CONFLICT, [github_line("MERGEABLE", 1)]),
      "conflict": (CHECK.EXIT_CONFLICT,
                   [github_line("MERGEABLE", 1), NOT_ONE_TO_ATTEMPT])},
     1, 0),
    ("CONFLICTING at once", [(0, "CONFLICTING")],
     {"clean": (CHECK.EXIT_CONFLICT,
                [github_line("CONFLICTING", 1), GITHUB_DECIDES]),
      "conflict": (CHECK.EXIT_CONFLICT, [github_line("CONFLICTING", 1)])},
     1, 0),
    ("UNKNOWN on every read", [(0, "UNKNOWN")] * 3,
     {"clean": (CHECK.EXIT_NO_CONFLICT,
                [github_line("UNKNOWN", 3), unsettled(3)]),
      "conflict": (CHECK.EXIT_CONFLICT,
                   [github_line("UNKNOWN", 3), unsettled(3)])},
     3, 2),
    ("UNKNOWN, then MERGEABLE", [(0, "UNKNOWN"), (0, "MERGEABLE")],
     {"clean": (CHECK.EXIT_NO_CONFLICT, [github_line("MERGEABLE", 2)]),
      "conflict": (CHECK.EXIT_CONFLICT,
                   [github_line("MERGEABLE", 2), NOT_ONE_TO_ATTEMPT])},
     2, 1),
    ("UNKNOWN, then CONFLICTING", [(0, "UNKNOWN"), (0, "CONFLICTING")],
     {"clean": (CHECK.EXIT_CONFLICT,
                [github_line("CONFLICTING", 2), GITHUB_DECIDES]),
      "conflict": (CHECK.EXIT_CONFLICT, [github_line("CONFLICTING", 2)])},
     2, 1),
    ("gh failing on the first mergeability read", [(1, "")],
     {"clean": (CHECK.EXIT_NO_CONFLICT, [GITHUB_FAILED]),
      "conflict": (CHECK.EXIT_CONFLICT, [GITHUB_FAILED])},
     1, 0),
    ("UNKNOWN, then gh failing", [(0, "UNKNOWN"), (1, "")],
     {"clean": (CHECK.EXIT_NO_CONFLICT, [GITHUB_FAILED]),
      "conflict": (CHECK.EXIT_CONFLICT, [GITHUB_FAILED])},
     2, 1),
]
for github_name, gh_results, by_git, reads_taken, sleeps_taken in MATCHED_HEAD_CELLS:
    for git_name, merge_status, _git_exit in GIT_ANSWERS:
        want_exit, tail = by_git[git_name]
        log, sleeps = [], []
        status, lines = run(
            fake_runner(merge_tree_status=merge_status, gh_results=gh_results,
                        log=log),
            pull_request=353, reads=3, sleeps=sleeps)
        label = "heads match, git %s, GitHub %s" % (git_name, github_name)
        case(label + ": exits %d" % want_exit, status == want_exit)
        case(label + ": the whole output",
             lines == verdict_block(want_exit) + tail)
        case(label + ": %d mergeability read(s)" % reads_taken,
             gh_reads_of(log, "mergeable") == reads_taken)
        case(label + ": %d sleep(s) between reads" % sleeps_taken,
             len(sleeps) == sleeps_taken)

# Axis A different -- the case the user ruled on 2026-09-23 (walk item 3): the
# commit checked is not the pull request's pushed head, as after a hand merge
# not yet pushed. The program keeps git's answer and says why in two lines,
# whatever GitHub would have said: GitHub is not even asked for mergeability.
MISMATCH_LINES = [
    "GITHUB: not consulted -- pull request 605's pushed head is commit %s, not "
    "the %s this run checked" % (OTHER_COMMIT[:12], HEAD_LABEL),
    "DISCLOSURE: GitHub's mergeability is about pull request 605's pushed head "
    "commit %s, not the %s checked here, so it cannot overrule git about a "
    "commit it was never asked about; this verdict is git's alone. Say so in "
    "the pull request." % (OTHER_COMMIT[:12], HEAD_LABEL),
]
for git_name, merge_status, git_exit in GIT_ANSWERS:
    for github_would_say in ("CONFLICTING", "MERGEABLE", "UNKNOWN"):
        log = []
        status, lines = run(
            fake_runner(merge_tree_status=merge_status, gh_head=OTHER_COMMIT,
                        gh_results=[(0, github_would_say)] * 3, log=log),
            pull_request=605, reads=3)
        label = "heads differ, git %s, GitHub would say %s" % (
            git_name, github_would_say)
        case(label + ": the exit is git's", status == git_exit)
        case(label + ": the whole output is git's verdict and two disclosure lines",
             lines == verdict_block(git_exit) + MISMATCH_LINES)
        case(label + ": each disclosure line names both short hashes",
             len(lines) >= 2 and all(OTHER_COMMIT[:12] in line
                                     and RESOLVED_HEAD[:12] in line
                                     for line in lines[-2:]))
        case(label + ": GitHub is never asked for mergeability",
             gh_reads_of(log, "mergeable") == 0)

# GitHub's head or base cannot be read -- gh exits non-zero, or prints nothing.
# Either way GitHub could not be asked, and git's answer stands, said once.
for git_name, merge_status, git_exit in GIT_ANSWERS:
    for what, runner_args in (
            ("head, gh failing", dict(gh_head_status=1)),
            ("head, gh printing nothing", dict(gh_head="")),
            ("base, gh failing", dict(gh_base_status=1)),
            ("base, gh printing nothing", dict(gh_base=""))):
        log = []
        status, lines = run(
            fake_runner(merge_tree_status=merge_status, log=log,
                        gh_results=[(0, "CONFLICTING")] * 3, **runner_args),
            pull_request=605, reads=3)
        label = "GitHub's %s, git %s" % (what, git_name)
        case(label + ": the exit is git's", status == git_exit)
        case(label + ": the whole output",
             lines == verdict_block(git_exit) + [GITHUB_FAILED])
        case(label + ": GitHub is never asked for mergeability",
             gh_reads_of(log, "mergeable") == 0)

# The pull request targets another branch than --base names: GitHub's answer
# is about another merge, so git's stands, whatever GitHub says.
BASE_MISMATCH_LINES = [
    "GITHUB: not consulted -- pull request 700 targets release, not the main "
    "that --base origin/main names",
    "DISCLOSURE: GitHub's mergeability is about merging into release, so it "
    "cannot overrule git about merging into origin/main; this verdict is git's "
    "alone. Say so in the pull request.",
]
for git_name, merge_status, git_exit in GIT_ANSWERS:
    for github_would_say in ("CONFLICTING", "MERGEABLE"):
        log = []
        status, lines = run(
            fake_runner(merge_tree_status=merge_status, gh_base="release",
                        gh_results=[(0, github_would_say)] * 3, log=log),
            pull_request=700, reads=3)
        label = "base branches differ, git %s, GitHub would say %s" % (
            git_name, github_would_say)
        case(label + ": the exit is git's", status == git_exit)
        case(label + ": the whole output",
             lines == verdict_block(git_exit) + BASE_MISMATCH_LINES)
        case(label + ": GitHub is never asked for mergeability",
             gh_reads_of(log, "mergeable") == 0)

# A bare-hash --base, possible only under --no-fetch, names no branch: GitHub
# is not asked about the base or the mergeability, and says why.
for git_name, merge_status, git_exit in GIT_ANSWERS:
    log = []
    status, lines = run(
        fake_runner(merge_tree_status=merge_status, full_refs={RESOLVED_BASE: ""},
                    gh_results=[(0, "CONFLICTING")] * 3, log=log),
        pull_request=353, reads=3, base=RESOLVED_BASE, fetch=False)
    label = "a bare-hash --base with a pull request, git %s" % git_name
    case(label + ": the exit is git's", status == git_exit)
    case(label + ": the whole output", lines == verdict_block(
        git_exit, base=RESOLVED_BASE) + [
        no_fetch_disclosure(RESOLVED_BASE),
        "GITHUB: not consulted -- --base %s names no branch, so no pull "
        "request's mergeability is about it" % RESOLVED_BASE,
        "DISCLOSURE: this verdict is git's alone. Say so in the pull request.",
    ])
    case(label + ": GitHub is asked neither the base nor the mergeability",
         gh_reads_of(log, "baseRefName") == 0
         and gh_reads_of(log, "mergeable") == 0)

# --no-fetch with a pull request whose verdict counts: the verdict block comes
# first, then the --no-fetch disclosure, then GitHub's lines.
status, lines = run(
    fake_runner(merge_tree_status=0, gh_results=[(0, "CONFLICTING")]),
    pull_request=353, reads=3, fetch=False)
case("--no-fetch, heads match, git clean, GitHub CONFLICTING: exits 1",
     status == CHECK.EXIT_CONFLICT)
case("--no-fetch, heads match, git clean, GitHub CONFLICTING: the whole output",
     lines == conflict_block() + [no_fetch_disclosure(),
                                  github_line("CONFLICTING", 1), GITHUB_DECIDES])

# Every run that gives no answer stops before GitHub, even with a pull
# request: a failed fetch, a --base the fetch does not move, a base or head
# that does not resolve.
for what, runner_args, run_args in (
        ("a failed fetch", dict(fetch_status=1), {}),
        ("a --base the fetch does not move",
         dict(full_refs={"main": "refs/heads/main"}), dict(base="main")),
        ("an unresolvable base", dict(base_resolves=False), {}),
        ("an unresolvable head", dict(head_resolves=False), {})):
    log = []
    status, lines = run(
        fake_runner(merge_tree_status=1, gh_results=[(0, "CONFLICTING")] * 3,
                    log=log, **runner_args),
        pull_request=353, reads=3, **run_args)
    case("%s with a pull request exits 2" % what,
         status == CHECK.EXIT_BAD_INVOCATION)
    case("%s with a pull request never runs gh" % what, gh_calls(log) == [])
    case("%s with a pull request gives no verdict" % what,
         not any(line.startswith("VERDICT:") for line in lines))

# A mergeability value GitHub does not document ("null", or a word added
# later) is not a verdict. Pinned here: it never overrules git and is never
# read as agreement. NOT pinned: what the output says about it. Today the
# program prints "GITHUB: <value> after N read(s)" and no DISCLOSURE that the
# verdict is git's alone, which github_mergeable's docstring does not allow
# (it names CONFLICTING, MERGEABLE, UNKNOWN or None as its only returns).
# That was reported on 2026-09-23 rather than pinned here as correct.
for git_name, merge_status, git_exit in GIT_ANSWERS:
    for value in ("null", "SOMETHING_NEW"):
        status, lines = run(
            fake_runner(merge_tree_status=merge_status,
                        gh_results=[(0, value)] * 3),
            pull_request=353, reads=3)
        label = "GitHub answering %r, git %s" % (value, git_name)
        case(label + ": the exit is git's", status == git_exit)
        case(label + ": the verdict block is git's",
             lines[:len(verdict_block(git_exit))] == verdict_block(git_exit))
        case(label + ": never disclosed as GitHub agreeing or overruling",
             GITHUB_DECIDES not in lines and NOT_ONE_TO_ATTEMPT not in lines)


# --- the program itself, run against real repositories -----------------------
# Everything above drives check() through a fake git. These cases run the
# program as a command, the way agents and hooks run it, against throwaway
# repositories and a stub gh first on PATH. So main()'s wiring -- the flags,
# the exit status, stdout -- is pinned, and so are the git behaviours the fake
# encodes: merge-tree exiting 1 for a hash that does not resolve, 128 for
# unrelated histories, and a fetch that moves origin/main. Nothing here reaches
# a real repository or GitHub: every GIT_ variable the caller exported is
# dropped, git's global and system config are switched off, and gh is the stub.
REAL_ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
REAL_ENV.update(
    GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
    GIT_AUTHOR_NAME="Case", GIT_AUTHOR_EMAIL="case@example.invalid",
    GIT_COMMITTER_NAME="Case", GIT_COMMITTER_EMAIL="case@example.invalid")

# The stub answers `gh pr view <n> --json <field> -q .<field>` from
# STUB_GH_<FIELD>, exits 1 when STUB_GH_FAIL is set, and logs every call.
STUB_GH_PROGRAM = '''import os, sys
with open(os.environ["STUB_GH_LOG"], "a") as log:
    log.write(" ".join(sys.argv[1:]) + "\\n")
if os.environ.get("STUB_GH_FAIL"):
    sys.exit(1)
field = sys.argv[sys.argv.index("--json") + 1]
print(os.environ.get("STUB_GH_" + field.upper(), ""))
'''


class SetupFailed(Exception):
    pass


def git_in(repo, *args):
    done = subprocess.run(["git", *args], cwd=repo, env=REAL_ENV,
                          capture_output=True, text=True, timeout=60)
    if done.returncode != 0:
        raise SetupFailed("git %s in %s: %s"
                          % (" ".join(args), repo, done.stderr.strip()))
    return done.stdout.strip()


def commit_in(repo, name, text, message):
    (Path(repo) / name).write_text(text)
    git_in(repo, "add", name)
    git_in(repo, "commit", "-q", "-m", message)
    return git_in(repo, "rev-parse", "HEAD")


def real_label(commit_hash, subject):
    return 'commit %s ("%s")' % (commit_hash[:12], subject)


def run_program(cwd, stub_bin, gh_log, *args, gh=None):
    """Run the program as a command: (exit status, stdout lines, gh calls)."""
    env = dict(REAL_ENV)
    env["PATH"] = str(stub_bin) + os.pathsep + env.get("PATH", "")
    env["STUB_GH_LOG"] = str(gh_log)
    for field, value in (gh or {}).items():
        env["STUB_GH_" + field] = value
    gh_log.write_text("")
    done = subprocess.run(
        [sys.executable, str(HERE / "branch-conflict-check.py"), *args],
        cwd=cwd, env=env, capture_output=True, text=True, timeout=120)
    return done.returncode, done.stdout.splitlines(), gh_log.read_text().splitlines()


def real_repository_cases(root):
    origin, work = root / "origin", root / "work"
    stub_bin, gh_log = root / "bin", root / "gh-calls.log"
    stub_bin.mkdir()
    (root / "stub-gh.py").write_text(STUB_GH_PROGRAM)
    (stub_bin / "gh").write_text("#!/bin/sh\nexec '%s' '%s' \"$@\"\n"
                                 % (sys.executable, root / "stub-gh.py"))
    (stub_bin / "gh").chmod(0o755)

    # origin is an ordinary repository that commits are made in directly, so
    # the cases never push; work fetches from it as a seat's checkout does.
    origin.mkdir()
    git_in(origin, "init", "-q", "-b", "main")
    commit_in(origin, "f", "one\ntwo\n", "base")
    git_in(root, "clone", "-q", str(origin), str(work))
    git_in(work, "checkout", "-q", "-b", "clean-topic")
    clean_head = commit_in(work, "g", "new file\n", "clean topic")
    git_in(work, "checkout", "-q", "-b", "conflict-topic", "main")
    conflict_head = commit_in(work, "f", "one\ntwo, topic\n", "conflict topic")
    git_in(work, "checkout", "-q", "--orphan", "unrelated-topic")
    git_in(work, "rm", "-q", "-r", "-f", ".")
    commit_in(work, "h", "unrelated\n", "unrelated history")
    git_in(work, "checkout", "-q", "main")
    # main moves after the clone, so work's origin/main is stale until fetched.
    main_head = commit_in(origin, "f", "one\ntwo, main\n", "main moves")
    clean_label = real_label(clean_head, "clean topic")
    conflict_label = real_label(conflict_head, "conflict topic")
    main_label = real_label(main_head, "main moves")

    def run_here(*args, cwd=work, gh=None):
        return run_program(cwd, stub_bin, gh_log, *args, gh=gh)

    # The fetch moves the base. With --no-fetch, the stale origin/main says
    # the conflicting branch is clean, and says the base was never refreshed;
    # fetching then finds the conflict.
    status, lines, calls = run_here("--head", "conflict-topic", "--no-fetch")
    case("real: --no-fetch against a stale origin/main answers about the stale "
         "base", status == CHECK.EXIT_NO_CONFLICT
         and lines == clean_block(label=conflict_label) + [no_fetch_disclosure()])
    status, lines, calls = run_here("--head", "conflict-topic")
    case("real: the fetch moves origin/main, and the conflict is found",
         status == CHECK.EXIT_CONFLICT
         and lines == conflict_block(label=conflict_label))
    case("real: without --pull-request gh is never run", calls == [])

    status, lines, _ = run_here("--head", "clean-topic")
    case("real: a clean branch exits 0 with the one CLEAN line",
         status == CHECK.EXIT_NO_CONFLICT
         and lines == clean_block(label=clean_label))

    # The trap: merge-tree exits 1 for a hash it cannot resolve, the same as a
    # conflict. The program must say UNRESOLVED, exit 2, and never CONFLICT.
    bad_hash = "d" * 40
    status, lines, _ = run_here("--head", bad_hash)
    case("real: a head that resolves to nothing exits 2, not 1",
         status == CHECK.EXIT_BAD_INVOCATION)
    case("real: a head that resolves to nothing is UNRESOLVED, not CONFLICT",
         lines == CHECK.unresolved_lines("head", bad_hash))

    status, lines, _ = run_here("--base", "origin/no-such-branch",
                                "--head", "clean-topic")
    case("real: a base that resolves to nothing exits 2 as UNRESOLVED",
         status == CHECK.EXIT_BAD_INVOCATION
         and lines == CHECK.unresolved_lines("base", "origin/no-such-branch"))

    status, lines, _ = run_here("--head", "unrelated-topic")
    case("real: unrelated histories exit 2, not a conflict",
         status == CHECK.EXIT_BAD_INVOCATION)
    case("real: unrelated histories are UNANSWERED, with no hand merge",
         bool(lines) and lines[0].startswith("UNANSWERED: git merge-tree exited ")
         and "Do not merge by hand on this result." in lines
         and not any("into the branch by hand" in line for line in lines))

    # A local branch is not moved by fetching origin: refused while fetching,
    # answered with the disclosure under --no-fetch. Local main never moved.
    status, lines, _ = run_here("--base", "main", "--head", "conflict-topic")
    case("real: a local-branch --base while fetching exits 2 as UNMATCHED",
         status == CHECK.EXIT_BAD_INVOCATION
         and bool(lines) and lines[0].startswith("UNMATCHED: --base main "))
    status, lines, _ = run_here("--base", "main", "--head", "conflict-topic",
                                "--no-fetch")
    case("real: a local-branch --base under --no-fetch is answered, disclosed",
         status == CHECK.EXIT_NO_CONFLICT
         and lines == clean_block(base="main", label=conflict_label)
         + [no_fetch_disclosure("main")])

    # A linked worktree, where agents and hooks run: the default --head HEAD
    # is the worktree's own commit.
    linked = root / "linked"
    git_in(work, "worktree", "add", "-q", "--detach", str(linked),
           "conflict-topic")
    status, lines, _ = run_here(cwd=linked)
    case("real: in a linked worktree, HEAD is the worktree's commit",
         status == CHECK.EXIT_CONFLICT
         and lines == conflict_block(label=conflict_label))

    # A fetch that fails stops the run, even though a stale origin/main is
    # sitting right there and would resolve.
    unreachable = root / "unreachable"
    git_in(root, "clone", "-q", str(origin), str(unreachable))
    git_in(unreachable, "remote", "set-url", "origin", str(root / "no-such-origin"))
    status, lines, _ = run_here(cwd=unreachable)
    case("real: a fetch that fails exits 2 as UNFETCHED",
         status == CHECK.EXIT_BAD_INVOCATION and lines == [
             "UNFETCHED: git fetch origin failed; do not act on any conflict "
             "answer until a run succeeds.",
             "Fix the fetch, then rerun.",
             "If origin/main in this checkout is already current, rerun with "
             "--no-fetch instead.",
         ])

    pull_request_args = ("--pull-request", "605", "--unknown-reads", "1",
                         "--unknown-sleep-seconds", "0")

    # Heads match: GitHub's CONFLICTING overrules a clean git, through the CLI.
    status, lines, calls = run_here(
        "--head", "clean-topic", *pull_request_args,
        gh=dict(HEADREFOID=clean_head, BASEREFNAME="main",
                MERGEABLE="CONFLICTING"))
    case("real: heads match, GitHub CONFLICTING overrules a clean git",
         status == CHECK.EXIT_CONFLICT
         and lines == conflict_block(label=clean_label)
         + [github_line("CONFLICTING", 1), GITHUB_DECIDES])
    case("real: heads match, GitHub is asked for mergeability",
         any("mergeable" in call for call in calls))

    # Heads differ (the user's 2026-09-23 ruling), through the CLI: GitHub's
    # pushed head is main's commit, the checked commit is the topic's.
    for head, head_label, head_status, github_says in (
            ("clean-topic", clean_label, CHECK.EXIT_NO_CONFLICT, "CONFLICTING"),
            ("conflict-topic", conflict_label, CHECK.EXIT_CONFLICT, "MERGEABLE")):
        status, lines, calls = run_here(
            "--head", head, *pull_request_args,
            gh=dict(HEADREFOID=main_head, BASEREFNAME="main",
                    MERGEABLE=github_says))
        label = "real: heads differ, %s, GitHub would say %s" % (head, github_says)
        case(label + ": the exit is git's", status == head_status)
        case(label + ": the whole output", lines == verdict_block(
            head_status, label=head_label) + [
            "GITHUB: not consulted -- pull request 605's pushed head is %s, "
            "not the %s this run checked" % (main_label, head_label),
            "DISCLOSURE: GitHub's mergeability is about pull request 605's "
            "pushed head %s, not the %s checked here, so it cannot overrule "
            "git about a commit it was never asked about; this verdict is "
            "git's alone. Say so in the pull request." % (main_label, head_label),
        ])
        case(label + ": GitHub is never asked for mergeability",
             not any("mergeable" in call for call in calls))

    status, lines, _ = run_here("--head", "clean-topic", *pull_request_args,
                                gh=dict(FAIL="1"))
    case("real: gh failing leaves git's answer standing, said once",
         status == CHECK.EXIT_NO_CONFLICT
         and lines == clean_block(label=clean_label) + [GITHUB_FAILED])


with tempfile.TemporaryDirectory(prefix="branch-conflict-check-test-") as scratch:
    try:
        real_repository_cases(Path(scratch).resolve())
    except (SetupFailed, subprocess.TimeoutExpired, OSError) as exc:
        case("real: the throwaway repositories could be built and run (%s)" % exc,
             False)


# --- the original defect, pinned so it cannot come back ----------------------
# Plain `gh pr view <n>` prints no mergeability field, so nothing may key on it.
source = (HERE / "branch-conflict-check.py").read_text()
case("the program never asks gh for mergeability without --json",
     '"--json", "mergeable"' in source)

print("%d case(s), %d failed" % (case_count, len(failures)))
sys.exit(1 if failures else 0)
