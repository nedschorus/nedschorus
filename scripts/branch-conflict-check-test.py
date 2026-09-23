#!/usr/bin/env python3
"""Cases for branch-conflict-check.py.

Every case here is a measurement taken by hand on 2026-09-22 that the prose
version of this instruction got wrong. They are cases so that the next person
does not have to re-measure them, and so a regression cannot pass silently.

Run: scripts/branch-conflict-check-test.py
Exit codes: 0 all passed, 1 any failed.
"""

import importlib.util
import sys
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
                fetch_status=0, gh_head=RESOLVED_HEAD, gh_head_status=0):
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
    """
    gh_queue = list(gh_results or [])
    base_ok = resolves if base_resolves is None else base_resolves
    head_ok = resolves if head_resolves is None else head_resolves

    def runner(command):
        if log is not None:
            log.append(command)
        if command[:2] == ["git", "fetch"]:
            return fetch_status, ""
        if command[:2] == ["git", "rev-parse"]:
            rev = command[-1]
            is_base = rev.startswith("origin/")
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
        remote=CHECK.DEFAULT_FETCH_REMOTE):
    return CHECK.check(
        "HEAD", "origin/main", pull_request,
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
case("the fetch happens, and happens before anything is resolved",
     [c[:2] for c in log].index(["git", "fetch"])
     < [c[:2] for c in log].index(["git", "rev-parse"]))
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
     lines[3] == "Before pushing, rerun the test suites for what the merge "
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

# --- the original defect, pinned so it cannot come back ----------------------
# Plain `gh pr view <n>` prints no mergeability field, so nothing may key on it.
source = (HERE / "branch-conflict-check.py").read_text()
case("the program never asks gh for mergeability without --json",
     '"--json", "mergeable"' in source)

print("%d case(s), %d failed" % (case_count, len(failures)))
sys.exit(1 if failures else 0)
