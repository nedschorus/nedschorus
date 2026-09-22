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
                fetch_status=0):
    """A runner that answers git and gh without touching either.

    base_resolves and head_resolves override `resolves` for one side, so a case
    can make exactly one rev unresolvable. Without that, both guards see a
    failure, the first one returns, and the second is never exercised -- which
    is how the head guard went unpinned until mutation testing found it.
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
        if command[:2] == ["gh", "pr"]:
            if not gh_queue:
                return 1, ""
            return gh_queue.pop(0)
        raise AssertionError("unexpected command: %r" % (command,))

    return runner


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
case("a conflict says what to do about it", "by hand" in lines[0])

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
     sum(1 for c in log if c[:2] == ["gh", "pr"]) == 2)

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
     "--no-fetch" in lines[0])

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

# --- the original defect, pinned so it cannot come back ----------------------
# Plain `gh pr view <n>` prints no mergeability field, so nothing may key on it.
source = (HERE / "branch-conflict-check.py").read_text()
case("the program never asks gh for mergeability without --json",
     '"--json", "mergeable"' in source)

print("%d case(s), %d failed" % (case_count, len(failures)))
sys.exit(1 if failures else 0)
