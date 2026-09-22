#!/usr/bin/env python3
"""Does this branch conflict with main? — one answer, from two oracles that disagree.

Replaces a ten-bullet instruction that PR "A conflict is the one case a commit on
top cannot clear" (600) proposed adding to CLAUDE.md and to five call sites in
nc-systems/handoff/handoff-supervisor.py. User-ruled 2026-09-22 at the merge-lane
Mac seat: "seems like this needs to be a python script, not complex instructions."
The prose had gone through three revisions and was still wrong each time; the
measurements that forced those revisions are test cases here instead, where they
cannot silently regress.

WHY THE OBVIOUS ONE-LINERS ARE EACH WRONG. All three measured 2026-09-22 on this
Mac, gh 2.97.0, against live pull requests:

  - `gh pr view <n>` with no --json prints NO mergeability field at all. Zero
    occurrences of CONFLICTING in the output of a genuinely conflicting pull
    request, so an instruction keyed on that word can never fire.

  - `gh pr view <n> --json mergeable` has THREE values, not two, and UNKNOWN is
    common rather than rare. Immediately after main moved, EIGHT of NINE open
    pull requests read UNKNOWN — including one that genuinely conflicted. A
    moving main invalidates mergeability for every open pull request at once and
    GitHub recomputes over roughly a minute. Reading UNKNOWN as "no conflict" is
    therefore the original defect wearing a different hat, and it bites hardest
    right after a merge, which is exactly when a merge lane looks.

  - `git merge-tree --write-tree <base> <head>` exits 1 for a real conflict AND
    exits 1 for an argument it cannot resolve. Verified against a deadbeef hash.
    Exit code alone cannot tell them apart, so an unfetched or mistyped head
    reads as a conflict and sends an agent to hand-merge main for nothing. That
    is why the head is resolved first and a failure there is fatal.

WHY IT FETCHES BEFORE IT ANSWERS. A stale `origin/main` resolves perfectly well,
so no guard here can catch it: the program would answer confidently against a
base the branch was already rebuilt past. That is the same class of silent wrong
answer as reading UNKNOWN for "no conflict", and it is invisible for the same
reason — nothing in the output distinguishes a fresh base from a week-old one.
So the fetch is part of the answer, not preparation the caller is trusted to
remember, and a fetch that fails is fatal rather than a disclosure nobody reads.
`--no-fetch` is the deliberate opt-out for an offline or already-fetched caller,
and it says so in the output.

WHICH ORACLE WINS. git says whether a textual conflict exists; GitHub says
whether the merge will be ALLOWED, and they can disagree. Measured 2026-09-16 on
PR 353: git merged clean by following a rename where GitHub still reported
CONFLICTING. GitHub decides, so a CONFLICTING verdict from GitHub stands even
when merge-tree is clean. When GitHub never settles, the git answer is used and
the report says so rather than implying GitHub agreed.

Usage:
  scripts/branch-conflict-check.py [--head REV] [--base REV] [--pull-request N]
                                   [--no-fetch] [--fetch-remote NAME]

  --head           defaults to HEAD. Any rev git understands; resolved first.
  --base           defaults to origin/main.
  --pull-request   also ask GitHub, and let it overrule git.
  --no-fetch       skip the fetch; the base is whatever the checkout already has.
  --fetch-remote   remote to fetch, default origin.

Output: one VERDICT line, plus GITHUB and DISCLOSURE lines when they apply.
Exit codes: 0 no conflict, 1 conflict, 2 no trustworthy answer (bad invocation,
unresolvable rev, or a fetch that failed).
"""

import argparse
import subprocess
import sys
import time

DEFAULT_BASE = "origin/main"
DEFAULT_FETCH_REMOTE = "origin"
GITHUB_UNKNOWN_READS = 6
GITHUB_UNKNOWN_SLEEP_SECONDS = 10

EXIT_NO_CONFLICT = 0
EXIT_CONFLICT = 1
EXIT_BAD_INVOCATION = 2


def run(command):
    """Run a command, returning (exit status, stdout stripped). Never raises."""
    try:
        done = subprocess.run(command, capture_output=True, text=True)
    except (OSError, ValueError) as exc:
        return 127, str(exc)
    return done.returncode, done.stdout.strip()


def fetch_remote(remote, runner=run):
    """True when the remote was fetched, so the base is current.

    A stale base resolves fine, so nothing downstream can detect it. That is
    why a failed fetch stops the run instead of being disclosed and ignored.
    """
    status, _ = runner(["git", "fetch", remote])
    return status == 0


def resolve_commit(rev, runner=run):
    """The full hash rev names, or None when it does not resolve to a commit.

    Done before merge-tree because merge-tree cannot distinguish an
    unresolvable argument from a real conflict: both exit 1.
    """
    status, out = runner(["git", "rev-parse", "--verify", "--quiet", rev + "^{commit}"])
    return out if status == 0 and out else None


def git_says_conflict(base_hash, head_hash, runner=run):
    """True when git finds a real conflict merging head into base.

    Both arguments must already be resolved hashes, so a nonzero status here
    means a conflict and nothing else.
    """
    status, _ = runner(["git", "merge-tree", "--write-tree", base_hash, head_hash])
    return status != 0


def github_mergeable(pull_request, runner=run, sleep=time.sleep,
                     reads=GITHUB_UNKNOWN_READS,
                     sleep_seconds=GITHUB_UNKNOWN_SLEEP_SECONDS):
    """GitHub's verdict, polled past UNKNOWN.

    Returns (verdict, reads_taken). verdict is CONFLICTING, MERGEABLE, UNKNOWN
    when it never settled, or None when gh could not be asked at all.
    """
    verdict = None
    for attempt in range(1, reads + 1):
        status, out = runner([
            "gh", "pr", "view", str(pull_request),
            "--json", "mergeable", "-q", ".mergeable",
        ])
        if status != 0:
            return None, attempt
        verdict = out
        if verdict in ("CONFLICTING", "MERGEABLE"):
            return verdict, attempt
        if attempt < reads:
            sleep(sleep_seconds)
    return verdict or "UNKNOWN", reads


def check(head, base, pull_request=None, runner=run, sleep=time.sleep,
          reads=GITHUB_UNKNOWN_READS, sleep_seconds=GITHUB_UNKNOWN_SLEEP_SECONDS,
          fetch=True, remote=DEFAULT_FETCH_REMOTE):
    """Decide, and return (exit status, lines to print)."""
    lines = []

    if fetch:
        if not fetch_remote(remote, runner):
            return EXIT_BAD_INVOCATION, [
                "UNFETCHED: git fetch %s failed, so %s may be stale and any "
                "verdict against it untrustworthy -- fix the fetch, or pass "
                "--no-fetch to answer against the checkout as it stands"
                % (remote, base)
            ]
    else:
        lines.append(
            "DISCLOSURE: --no-fetch, so %s is whatever this checkout already "
            "had; a stale base gives a confident wrong answer." % base)

    base_hash = resolve_commit(base, runner)
    if base_hash is None:
        return EXIT_BAD_INVOCATION, [
            "UNRESOLVED: base %s does not resolve to a commit -- "
            "fetch it before trusting any conflict answer" % base
        ]
    head_hash = resolve_commit(head, runner)
    if head_hash is None:
        return EXIT_BAD_INVOCATION, [
            "UNRESOLVED: head %s does not resolve to a commit -- "
            "fetch it before trusting any conflict answer" % head
        ]

    conflict = git_says_conflict(base_hash, head_hash, runner)

    if pull_request is not None:
        verdict, taken = github_mergeable(
            pull_request, runner, sleep, reads, sleep_seconds)
        if verdict is None:
            lines.append(
                "GITHUB: could not be asked (gh failed) -- git's answer stands")
        else:
            lines.append("GITHUB: %s after %d read(s)" % (verdict, taken))
            if verdict == "UNKNOWN":
                lines.append(
                    "DISCLOSURE: GitHub had not settled after %d read(s); this "
                    "verdict is git's alone. Say so in the pull request." % taken)
            elif verdict == "CONFLICTING" and not conflict:
                lines.append(
                    "DISCLOSURE: git finds no conflict but GitHub reports "
                    "CONFLICTING; GitHub decides whether the merge is allowed, "
                    "so the branch still needs the hand merge.")
                conflict = True
            elif verdict == "MERGEABLE" and conflict:
                lines.append(
                    "DISCLOSURE: git finds a conflict but GitHub reports "
                    "MERGEABLE; treating it as a conflict, because a merge that "
                    "git cannot do is not one to attempt.")

    if conflict:
        lines.insert(0, "VERDICT: CONFLICT -- %s conflicts with %s. Merge %s into "
                        "the branch by hand, the frozen head as first parent, "
                        "resolving the conflict and nothing else, then rerun the "
                        "suites for what the merge touched before pushing."
                        % (head_hash[:12], base, base))
        return EXIT_CONFLICT, lines

    lines.insert(0, "VERDICT: CLEAN -- %s does not conflict with %s. Nothing to do."
                    % (head_hash[:12], base))
    return EXIT_NO_CONFLICT, lines


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Report whether a branch conflicts with main.")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--pull-request", type=int, default=None)
    parser.add_argument("--no-fetch", dest="fetch", action="store_false",
                        default=True)
    parser.add_argument("--fetch-remote", default=DEFAULT_FETCH_REMOTE)
    parser.add_argument("--unknown-reads", type=int, default=GITHUB_UNKNOWN_READS)
    parser.add_argument("--unknown-sleep-seconds", type=float,
                        default=GITHUB_UNKNOWN_SLEEP_SECONDS)
    args = parser.parse_args(argv)

    status, lines = check(
        args.head, args.base, args.pull_request,
        reads=args.unknown_reads, sleep_seconds=args.unknown_sleep_seconds,
        fetch=args.fetch, remote=args.fetch_remote)
    for line in lines:
        print(line)
    return status


if __name__ == "__main__":
    sys.exit(main())
