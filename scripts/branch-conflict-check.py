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

ONLY WHEN THE TWO ORACLES ARE ANSWERING ABOUT THE SAME COMMIT. GitHub answers
about the pull request's PUSHED head; git answers about whatever --head names.
Nothing tied those together until 2026-09-22, and the gap let GitHub's verdict
about one commit overrule git's verdict about a different one. Reproduced at the
merge-lane seat:

    branch-conflict-check.py --no-fetch --head origin/main --pull-request 605

printed CONFLICT for origin/main against origin/main -- main conflicting with
itself -- because pull request 605 genuinely conflicts and its verdict was
applied to a commit it was never about. Without --pull-request the same command
correctly printed CLEAN. The workflow version is worse than the demonstration:
the CONFLICT message below tells the agent to hand-merge the base, and after an
unpushed hand merge the local HEAD is the merge commit while GitHub still answers
about the old pushed head -- so a rerun orders the merge that just happened. So
GitHub's headRefOid is read too, and its verdict counts only when that equals the
resolved --head. When they differ the mismatch is disclosed, both short hashes
named, and the verdict is git's alone.

WHY THE BASE IS NOT BOUND THE SAME WAY. A reviewer proposed also requiring
GitHub's baseRefOid to equal the resolved --base, on the reasoning that a settled
mergeability value can have been computed against an older main. The window is
real; baseRefOid does not detect it. Measured 2026-09-22 on PR 605, whose
baseRefOid was 3fa1e8c216c5 while origin/main was 5f0fd4c5ebc6:

    git merge-tree --write-tree 3fa1e8c216c5 a370cc08f9b5  -> exit 0, clean
    git merge-tree --write-tree 5f0fd4c5ebc6 a370cc08f9b5  -> exit 1, conflict

GitHub reported CONFLICTING, which agrees with git against LIVE main and
disagrees with git against baseRefOid. So mergeability tracks the live base tip,
while baseRefOid is the base as of the pull request's open or last sync: 6 of the
9 open pull requests lagged main that day, and the 3 that matched (633, 634, 635)
were opened after 5f0fd4c landed. Binding it would discard correct GitHub
verdicts on most pull requests -- including the PR 353 shape, git clean against
GitHub CONFLICTING, which would then read CLEAN, the exact false answer this
program exists to prevent. The stale-value window is the UNKNOWN window, and the
poll above already covers it.

WHAT EACH MESSAGE INSTRUCTS, AND WHY. Every message an agent acts on is one
instruction per line, each with the condition it applies under; the reasons live
here, where maintainers read them (CLAUDE.md, user-ruled 2026-09-18 on the
force-push guard's refusal; applied to this program by the user 2026-09-22 in
the walk "merge-lane rulings owed and concerns", item 1).

  - UNFETCHED: a failed fetch stops the run because a stale base gives a
    confident wrong answer (WHY IT FETCHES BEFORE IT ANSWERS, above). The
    --no-fetch line is conditioned on the base already being current, because
    that is the only case in which skipping the fetch is safe.
  - UNRESOLVED (base or head): a rev that does not resolve is either mistyped or
    not fetched, and each gets its own line. It is caught before merge-tree
    because merge-tree would report it as a conflict (exit 1).
  - VERDICT: CONFLICT: the hand merge takes the frozen head as first parent
    because a pushed head is frozen under review, and the resubmission is one
    commit on top of it, never a rewrite (CLAUDE.md, "How a change reaches
    main", ruled 2026-09-08). "Resolve the conflict and nothing else" keeps the
    merge reviewable as a merge. The suites rerun because a resolution is new
    code that no earlier run tested.
  - UNANSWERED: only merge-tree statuses 0 (clean) and 1 (conflict) are
    verdicts; any other status means git could not attempt the merge (see
    merge_tree_exit_status for the three known triggers). "Do not merge by
    hand" comes first because a hand merge is the costly wrong response to it.

HOW OUTPUT NAMES A COMMIT. Always as commit <12-char hash> ("<subject>"): the
hash for the machine, the subject for the reader, who cannot recognise a hash
(user-ruled 2026-09-22, same walk, item 1). The subject comes from
`git log -1 --format=%s`. When that fails -- GitHub's pushed head is often not
in the local checkout -- the commit is named by its hash alone, `commit <hash>`,
rather than fetching to find a subject, which would change what the run does.

Usage:
  scripts/branch-conflict-check.py [--head REV] [--base REV] [--pull-request N]
                                   [--no-fetch] [--fetch-remote NAME]

  --head           defaults to HEAD. Any rev git understands; resolved first.
  --base           defaults to origin/main.
  --pull-request   also ask GitHub, and let it overrule git -- but only when
                   GitHub's pushed head is the commit --head resolved to.
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

# git merge-tree's own exit statuses, which are not this program's exit codes.
MERGE_TREE_CLEAN = 0
MERGE_TREE_CONFLICT = 1


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


def merge_tree_exit_status(base_hash, head_hash, runner=run):
    """git merge-tree's exit status: 0 clean, 1 conflict, anything else no answer.

    git reserves 1 for "the merge completed and found conflicts". Every other
    nonzero status means git could not complete the merge at all, so there is
    no verdict to report in either direction. Three triggers are known. Measured
    on this Mac, git 2.55.0, 2026-09-22: 128 for unrelated histories, and 129
    for an option git does not recognise. The third is a read-only object
    database, because --write-tree creates temporary data to write the result
    into: merge-tree then exits 128 on a merge that is in fact clean.

    Returning the status rather than a bool is what lets the caller tell a
    conflict from a merge git could not attempt. Until 2026-09-22 this returned
    `status != 0`, so a 128 printed a CONFLICT verdict carrying the hand-merge
    instruction and sent an agent to resolve a conflict that does not exist
    (user-ruled 2026-09-22; raised independently by the Codex review cell, by
    merge-lane-2 in review 5281571823, and by a mutation run which found that
    changing this line to `status == 1` left all 35 cases of the day green).
    """
    status, _ = runner(["git", "merge-tree", "--write-tree", base_hash, head_hash])
    return status


def commit_label(commit_hash, runner=run):
    """How output names a commit: commit <short hash> ("<subject>").

    Falls back to commit <short hash> when git cannot read the subject, which
    happens for a GitHub head that was never fetched. See the module docstring.
    """
    short = commit_hash[:12]
    status, subject = runner(["git", "log", "-1", "--format=%s", commit_hash])
    if status != 0 or not subject:
        return "commit %s" % short
    return 'commit %s ("%s")' % (short, subject)


def github_head_commit(pull_request, runner=run):
    """The pushed head commit GitHub's mergeability answer is about, or None.

    None when gh could not be asked at all. Read before the mergeability poll,
    because a verdict about another commit cannot count and is not worth
    waiting up to six reads for.
    """
    status, out = runner([
        "gh", "pr", "view", str(pull_request),
        "--json", "headRefOid", "-q", ".headRefOid",
    ])
    return out if status == 0 and out else None


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


def unresolved_lines(side, rev):
    """The UNRESOLVED message for a --base or --head that names no commit."""
    return [
        "UNRESOLVED: %s %s does not resolve to a commit; do not act on any "
        "conflict answer until a run succeeds." % (side, rev),
        "If %s is mistyped, correct --%s, then rerun." % (rev, side),
        "If %s is not fetched, fetch it, then rerun." % rev,
    ]


def check(head, base, pull_request=None, runner=run, sleep=time.sleep,
          reads=GITHUB_UNKNOWN_READS, sleep_seconds=GITHUB_UNKNOWN_SLEEP_SECONDS,
          fetch=True, remote=DEFAULT_FETCH_REMOTE):
    """Decide, and return (exit status, lines to print)."""
    lines = []

    if fetch:
        if not fetch_remote(remote, runner):
            return EXIT_BAD_INVOCATION, [
                "UNFETCHED: git fetch %s failed; do not act on any conflict "
                "answer until a run succeeds." % remote,
                "Fix the fetch, then rerun.",
                "If %s in this checkout is already current, rerun with "
                "--no-fetch instead." % base,
            ]
    else:
        lines.append(
            "DISCLOSURE: --no-fetch, so %s is whatever this checkout already "
            "had; a stale base gives a confident wrong answer." % base)

    base_hash = resolve_commit(base, runner)
    if base_hash is None:
        return EXIT_BAD_INVOCATION, unresolved_lines("base", base)
    head_hash = resolve_commit(head, runner)
    if head_hash is None:
        return EXIT_BAD_INVOCATION, unresolved_lines("head", head)

    merge_status = merge_tree_exit_status(base_hash, head_hash, runner)
    if merge_status not in (MERGE_TREE_CLEAN, MERGE_TREE_CONFLICT):
        return EXIT_BAD_INVOCATION, [
            "UNANSWERED: git merge-tree exited %d merging %s into %s; do not "
            "act on it as a conflict or as clean."
            % (merge_status, commit_label(head_hash, runner),
               commit_label(base_hash, runner)),
            "Do not merge by hand on this result.",
            "If either commit is missing from this checkout, fetch it, then "
            "rerun.",
            "If the two commits share no history, check that --head and --base "
            "name the right commits, then rerun.",
            "If the object database is not writable, run from a checkout where "
            "it is, then rerun.",
        ]
    conflict = merge_status == MERGE_TREE_CONFLICT

    if pull_request is not None:
        github_head = github_head_commit(pull_request, runner)
        if github_head is None:
            lines.append(
                "GITHUB: could not be asked (gh failed) -- git's answer stands")
        elif github_head != head_hash:
            lines.append(
                "GITHUB: not consulted -- pull request %d's pushed head is %s, "
                "not the %s this run checked"
                % (pull_request, commit_label(github_head, runner),
                   commit_label(head_hash, runner)))
            lines.append(
                "DISCLOSURE: GitHub's mergeability is about pull request %d's "
                "pushed head %s, not the %s checked here, so it cannot overrule "
                "git about a commit it was never asked about; this verdict is "
                "git's alone. Say so in the pull request."
                % (pull_request, commit_label(github_head, runner),
                   commit_label(head_hash, runner)))
        else:
            verdict, taken = github_mergeable(
                pull_request, runner, sleep, reads, sleep_seconds)
            if verdict is None:
                lines.append(
                    "GITHUB: could not be asked (gh failed) -- git's answer "
                    "stands")
            else:
                lines.append("GITHUB: %s after %d read(s)" % (verdict, taken))
                if verdict == "UNKNOWN":
                    lines.append(
                        "DISCLOSURE: GitHub had not settled after %d read(s); "
                        "this verdict is git's alone. Say so in the pull "
                        "request." % taken)
                elif verdict == "CONFLICTING" and not conflict:
                    lines.append(
                        "DISCLOSURE: git finds no conflict but GitHub reports "
                        "CONFLICTING; GitHub decides whether the merge is "
                        "allowed, so the branch still needs the hand merge.")
                    conflict = True
                elif verdict == "MERGEABLE" and conflict:
                    lines.append(
                        "DISCLOSURE: git finds a conflict but GitHub reports "
                        "MERGEABLE; treating it as a conflict, because a merge "
                        "that git cannot do is not one to attempt.")

    if conflict:
        lines[0:0] = [
            "VERDICT: CONFLICT -- %s conflicts with %s."
            % (commit_label(head_hash, runner), base),
            "Merge %s into the branch by hand, with the frozen head as first "
            "parent." % base,
            "Resolve the conflict and change nothing else in the merge.",
            "Before pushing, rerun the test suites for what the merge touched.",
        ]
        return EXIT_CONFLICT, lines

    lines.insert(0, "VERDICT: CLEAN -- %s does not conflict with %s. Nothing to do."
                    % (commit_label(head_hash, runner), base))
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
