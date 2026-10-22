#!/usr/bin/env python3
"""Check branch conflicts using git and GitHub.

GitHub can refuse a merge that git resolves cleanly, so a matching GitHub
CONFLICTING verdict takes precedence. UNKNOWN is not evidence of a clean merge."""

import argparse
import importlib.util
import re
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath

_git_output_spec = importlib.util.spec_from_file_location(
    "git_machine_readable_output_runner_and_parser_common",
    Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
    / "git-machine-readable-output-runner-and-parser-common.py")
git_output = importlib.util.module_from_spec(_git_output_spec)
_git_output_spec.loader.exec_module(git_output)

DEFAULT_BASE = "origin/main"
DEFAULT_FETCH_REMOTE = "origin"
GITHUB_UNKNOWN_READS = 6
GITHUB_UNKNOWN_SLEEP_SECONDS = 10

EXIT_NO_CONFLICT = 0
EXIT_CONFLICT = 1
EXIT_BAD_INVOCATION = 2

# These are git merge-tree statuses, not this program's exit codes.
MERGE_TREE_CLEAN = 0
MERGE_TREE_CONFLICT = 1


def run(command):
    """Return (exit status, stripped stdout) without raising."""
    try:
        done = subprocess.run(command, capture_output=True, text=True)
    except (OSError, ValueError) as exc:
        return 127, str(exc)
    return done.returncode, done.stdout.strip()


def fetch_remote(remote, runner=run):
    # A stale base resolves successfully, so a failed fetch must stop the check.
    status, _ = runner(["git", "fetch", remote])
    return status == 0


def resolve_commit(rev, runner=run):
    """Return the full commit hash, or None."""
    # Resolve before merge-tree: an unresolved argument and a real conflict can both exit 1.
    status, out = runner(["git", "rev-parse", "--verify", "--quiet", rev + "^{commit}"])
    return out if status == 0 and out else None


def full_ref_name(rev, runner=run):
    """Return the full ref name, "" for no ref, or None if git fails."""
    status, out = runner(["git", "rev-parse", "--symbolic-full-name", rev])
    return out if status == 0 else None


def base_branch_name(full_ref, remote):
    """Return the branch name for a local or remote ref, otherwise None."""
    if not full_ref:
        return None
    if full_ref.startswith("refs/heads/"):
        return full_ref[len("refs/heads/"):]
    if full_ref.startswith("refs/remotes/"):
        rest = full_ref[len("refs/remotes/"):]
        if rest.startswith(remote + "/"):
            return rest[len(remote) + 1:]
        return rest.split("/", 1)[1] if "/" in rest else None
    return None


def merge_tree_answer(base_hash, head_hash, runner=run):
    """Return (merge-tree status, its -z output): 0 clean, 1 conflict, otherwise no answer."""
    # Other failures, including an unwritable object database, must not be reported as conflicts.
    return runner(["git", "merge-tree", "--write-tree", "-z", base_hash, head_hash])


conflicted_paths = git_output.merge_tree_conflicted_stages


# merge-tree stages some conflicts under a path that is not the file's own, and
# its message record names the staged path first and the other path second.
# Which records name the file's own path depends on whose file it is:
# - a file the base deleted and the branch kept: a rename/delete record gives
#   the name the base deleted, and a file/directory record the name before the
#   file was moved aside as "<file>~<side>";
# - any other conflicted file: only a file/directory record. A rename/delete
#   there is a rename the base made, and the base's new name is the one the
#   agent will find; a directory rename record only suggests a location.
RENAMES_FOR_A_FILE_THE_BASE_DELETED = ("CONFLICT (rename/delete)",
                                       "CONFLICT (file/directory)")
RENAMES_FOR_ANY_OTHER_CONFLICT = ("CONFLICT (file/directory)",)


def two_path_messages(merge_tree_output):
    """Return {staged path: (conflict kind, other path)} from merge-tree's -z messages."""
    # After the empty field, each message is "<count>", that many paths, the
    # conflict kind, and the message text.
    fields = merge_tree_output.split("\0")
    try:
        index = fields.index("", 1) + 1
    except ValueError:
        return {}
    messages = {}
    while index < len(fields) and fields[index]:
        try:
            count = int(fields[index])
        except ValueError:
            break
        paths = fields[index + 1:index + 1 + count]
        kind = fields[index + 1 + count] if index + 1 + count < len(fields) else ""
        if len(paths) == 2:
            messages[paths[0]] = (kind, paths[1])
        index += count + 3
    return messages


def own_path(staged, messages, kinds):
    """Return the file's own path for a staged path, renamed only by a message of one of kinds."""
    kind, other = messages.get(staged, (None, staged))
    return other if kind in kinds else staged


def paths_deleted_on_base(stages):
    """Return the conflicted paths the base deleted and the head still has."""
    # The base is merge-tree's first side, so stage 2 is the base's version and
    # stage 3 the head's: a path with an ancestor and a head version but no base
    # version is one the base deleted while the branch changed it.
    return [path for path, found in stages.items()
            if "1" in found and "3" in found and "2" not in found]


def deleting_commit(path, base_hash, head_hash, runner=run):
    """Return the base-side commit that deleted path, or None."""
    status, out = runner(["git", "log", "-1", "--format=%H", "--diff-filter=D",
                          "%s..%s" % (head_hash, base_hash), "--", path])
    return out if status == 0 and out else None


# git pairs a deleted and an added file as a rename only when they are at
# least 50% alike, so a small file renamed and edited in one commit reaches
# merge-tree as a deletion. A lower threshold, and a name that differs only by
# leading or trailing words, find such a rename for the agent to confirm.
RENAME_SIMILARITY_THRESHOLD = "-M10%"
NAME_WORD_SEPARATORS = re.compile(r"[-_.]")


def name_words(path):
    """Return (extension, words of the file name before the extension)."""
    stem, dot, extension = PurePosixPath(path).name.rpartition(".")
    if not dot or not stem:
        stem, extension = PurePosixPath(path).name, ""
    return extension, [word for word in NAME_WORD_SEPARATORS.split(stem) if word]


def names_differ_by_end_words(old, new):
    """Return whether one file name is the other with words removed from its start or end."""
    old_extension, old_words = name_words(old)
    new_extension, new_words = name_words(new)
    if old_extension != new_extension:
        return False
    shorter, longer = sorted((old_words, new_words), key=len)
    # One shared word, such as "test" or "README", says nothing about a
    # rename, even when the whole name is that word.
    if len(shorter) < 2:
        return False
    return any(longer[start:start + len(shorter)] == shorter
               for start in range(len(longer) - len(shorter) + 1))


def renamed_to_candidates(path, commit, runner=run):
    """Return the files commit added that may be path renamed, or None if git fails."""
    status, out = runner(["git", "diff-tree", "-r", "-z", "--name-status",
                          RENAME_SIMILARITY_THRESHOLD, commit + "^", commit])
    if status != 0:
        return None
    fields = out.split("\0")
    paired, added = [], []
    index = 0
    while index < len(fields) and fields[index]:
        kind = fields[index]
        if kind.startswith("R"):
            if fields[index + 1] == path:
                paired.append(fields[index + 2])
            index += 3
            continue
        if kind == "A":
            added.append(fields[index + 1])
        index += 2
    return paired + [new for new in added
                     if new not in paired and names_differ_by_end_words(path, new)]


def path_exists_at(commit, path, runner=run):
    """Return whether path names a file in commit's tree, or None when git
    could not tell."""
    # git cat-file -e exits 128 both for a missing path and for a failure;
    # ls-tree exits 0 with no output for a missing path.
    status, out = runner(["git", "ls-tree", "-z", "--full-tree", "--name-only",
                          commit, "--", path])
    if status != 0:
        return None
    return bool(out)


def later_deleting_commit(path, after, base_hash, runner=run):
    """Return (whether git listed the commits, the first commit after `after`
    on the base that deleted path, or None)."""
    # A rename made on a side branch and merged leaves the path unchanged
    # between the merge and its first parent, and git log's default history
    # simplification then never visits the side branch.
    status, out = runner(["git", "log", "--full-history", "--reverse",
                          "--format=%H", "--diff-filter=D",
                          "%s..%s" % (after, base_hash), "--", path])
    if status != 0:
        return False, None
    hashes = out.split()
    return True, (hashes[0] if hashes else None)


def candidates_at_base(path, commit, base_hash, runner=run):
    """Return ((name at the base, commit that gave that name) pairs, commits
    git could not list, (candidate, commit) pairs whose later deletions git
    could not list, candidates git could not look up at the base).

    A file the deleting commit renamed may have been renamed or deleted again
    later on the base, so each candidate is kept only under a name the base
    holds: one it has, or the one a later rename gave it.
    """
    found, unlisted, unfollowed, unchecked, seen = [], [], [], [], set()
    pending = [(path, commit)]
    while pending:
        old, deleting = pending.pop(0)
        candidates = renamed_to_candidates(old, deleting, runner)
        if candidates is None:
            unlisted.append(deleting)
            continue
        for candidate in candidates:
            # A name can come back after a later rename, so the same name
            # reached through a different commit is followed again.
            if (candidate, deleting) in seen:
                continue
            seen.add((candidate, deleting))
            exists = path_exists_at(base_hash, candidate, runner)
            if exists is None:
                unchecked.append(candidate)
                continue
            if exists:
                found.append((candidate, deleting))
                continue
            listed, later = later_deleting_commit(candidate, deleting,
                                                  base_hash, runner)
            if not listed:
                unfollowed.append((candidate, deleting))
            elif later is not None:
                pending.append((candidate, later))
    return found, unlisted, unfollowed, unchecked


def deleted_on_base_lines(head_hash, base, base_hash, stages, deleted,
                          messages=None, runner=run):
    """Return the VERDICT lines for a conflict where the base deleted files the branch changes."""
    messages = messages or {}
    lines = [
        "VERDICT: CONFLICT -- %s conflicts with %s, and %s deleted %d file(s) "
        "the branch changes." % (commit_label(head_hash, runner), base, base,
                                 len(deleted)),
    ]
    unnamed = False
    renamed = 0
    checks = []
    for staged in deleted:
        path = own_path(staged, messages, RENAMES_FOR_A_FILE_THE_BASE_DELETED)
        commit = deleting_commit(path, base_hash, head_hash, runner)
        if commit is None:
            unnamed = True
            lines.append("DELETED ON %s: %s, by a commit this run could not find"
                         % (base, path))
            continue
        found, unlisted, unfollowed, unchecked = candidates_at_base(
            path, commit, base_hash, runner)
        if found:
            renamed += 1
            # A name a later commit gave says which commit holds it, so a
            # reader does not look for it in the deleting commit.
            named = [candidate if naming == commit
                     else "%s (the name %s gave it)"
                     % (candidate, commit_label(naming, runner))
                     for candidate, naming in found]
            lines.append("DELETED OR RENAMED ON %s: %s, deleted by %s -> "
                         "possibly %s" % (base, path, commit_label(commit, runner),
                                          " or ".join(named)))
        else:
            lines.append("DELETED ON %s: %s, by %s"
                         % (base, path, commit_label(commit, runner)))
        checks += [
            "RENAME CHECK: git could not list the files %s added, so %s may "
            "have been renamed to a name this run could not find; check that "
            "commit with git show --stat %s."
            % (commit_label(unlisted_commit, runner), path, unlisted_commit[:12])
            for unlisted_commit in dict.fromkeys(unlisted)]
        checks += [
            "RENAME CHECK: git could not list the commits on %s after %s that "
            "deleted %s, so %s may have been renamed again, to a name this run "
            "could not find; check with git log --full-history --diff-filter=D "
            "%s..%s -- %s." % (base, commit_label(after, runner), candidate, path,
                               after[:12], base_hash[:12], candidate)
            for candidate, after in dict.fromkeys(unfollowed)]
        checks += [
            "RENAME CHECK: git could not tell whether %s holds %s, so %s may "
            "have been renamed to it; check with git ls-tree --full-tree "
            "--name-only %s -- %s." % (base, candidate, path, base_hash[:12],
                                       candidate)
            for candidate in dict.fromkeys(unchecked)]
    others = [path for path in stages if path not in deleted]
    for path in others:
        lines.append("ALSO CONFLICTS: %s"
                     % own_path(path, messages, RENAMES_FOR_ANY_OTHER_CONFLICT))
    lines += checks
    if renamed or checks:
        # One instruction for every file, so no line about one file can be
        # read against a line about another.
        marked = "each file marked DELETED ON or DELETED OR RENAMED"
        lines.append(
            "git paired none of the files marked DELETED ON or DELETED OR RENAMED "
            "with a new name, but %s may have renamed one and changed it in the "
            "same commit, so much that git saw a deletion." % base)
        lines.append(
            "Before you act, find out for %s whether %s renamed it "
            "or deleted it: compare the branch's version of it with %s's version "
            "of each file named after \"possibly\" on its line, and do each "
            "RENAME CHECK that names it. A file with no \"possibly\" on its line and "
            "no RENAME CHECK naming it was deleted."
            % (marked, base, base))
        if unnamed:
            lines.append(
                "If a deleting commit is not named above, find it with git log "
                "--diff-filter=D %s -- <file>." % base)
        lines += [
            "Do not merge %s into this branch, and do not push this branch "
            "again: a conflicting pull request is replaced by a new one cut "
            "from current %s." % (base, base),
            "If every file marked DELETED ON or DELETED OR RENAMED was renamed, "
            "cut a new topic branch from current %s and apply this branch's "
            "change to it, carrying the change to each file onto its new name "
            "and resolving any ALSO CONFLICTS file too; rerun the test suites "
            "for what the change touches, push the new branch once, open a new "
            "pull request from it whose description links the old one, and "
            "close the old one with a comment linking the new one." % base,
            "If any file marked DELETED ON or DELETED OR RENAMED was deleted, "
            "close the pull request with a comment naming the commit that "
            "deleted it, and carry what %s still lacks on a new topic branch "
            "cut from current %s, in a new pull request that names the closed "
            "one; on that branch, carry the branch's change to each renamed "
            "file onto its new name%s."
            % (base, base,
               ", and start each ALSO CONFLICTS file from %s's version and "
               "reapply the branch's change to it by hand" % base
               if others else ""),
        ]
        return lines
    lines.append(
        "Do not merge %s into the branch: %s removed the file(s) above, so "
        "the branch's change to each of them has nothing left to apply to."
        % (base, base))
    if unnamed:
        lines.append(
            "If a deleting commit is not named above, find it with git log "
            "--diff-filter=D %s -- <file>." % base)
    lines += [
        "If the branch has a pull request, close it with a comment naming the "
        "commit that deleted each file.",
        "If %s still lacks any of the branch's work, including what its change "
        "to each deleted file was for, carry that work on a new topic branch "
        "cut from current %s, in a new pull request that names the closed one."
        % (base, base),
    ]
    if others:
        lines.append(
            "On the new topic branch, start each ALSO CONFLICTS file from %s's "
            "version and reapply the branch's change to it by hand." % base)
    return lines


def commit_label(commit_hash, runner=run):
    """Return a short hash with the subject when available."""
    short = commit_hash[:12]
    status, subject = runner(["git", "log", "-1", "--format=%s", commit_hash])
    if status != 0 or not subject:
        return "commit %s" % short
    return 'commit %s ("%s")' % (short, subject)


def github_head_commit(pull_request, runner=run):
    """Return the pushed head hash, or None if unavailable."""
    status, out = runner([
        "gh", "pr", "view", str(pull_request),
        "--json", "headRefOid", "-q", ".headRefOid",
    ])
    return out if status == 0 and out else None


def github_base_branch(pull_request, runner=run):
    """Return the target branch, or None if unavailable."""
    status, out = runner([
        "gh", "pr", "view", str(pull_request),
        "--json", "baseRefName", "-q", ".baseRefName",
    ])
    return out if status == 0 and out else None


def github_mergeable(pull_request, runner=run, sleep=time.sleep,
                     reads=GITHUB_UNKNOWN_READS,
                     sleep_seconds=GITHUB_UNKNOWN_SLEEP_SECONDS):
    """Return (verdict, reads), polling past UNKNOWN; None means gh failed."""
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


def github_verdict_for_base(pull_request, base, base_branch, lines,
                            runner=run, sleep=time.sleep,
                            reads=GITHUB_UNKNOWN_READS,
                            sleep_seconds=GITHUB_UNKNOWN_SLEEP_SECONDS):
    """Return (verdict, reads), or (False, 0) when the base does not match."""
    # Match branch names: baseRefOid can lag the live base used for GitHub mergeability.
    if base_branch is None:
        lines.append(
            "GITHUB: not consulted -- --base %s names no branch, so no pull "
            "request's mergeability is about it" % base)
        lines.append(
            "DISCLOSURE: this verdict is git's alone. Say so in the pull "
            "request.")
        return False, 0
    github_base = github_base_branch(pull_request, runner)
    if github_base is None:
        return None, 1
    if github_base != base_branch:
        lines.append(
            "GITHUB: not consulted -- pull request %d targets %s, not the %s "
            "that --base %s names" % (pull_request, github_base, base_branch,
                                      base))
        lines.append(
            "DISCLOSURE: GitHub's mergeability is about merging into %s, so it "
            "cannot overrule git about merging into %s; this verdict is git's "
            "alone. Say so in the pull request." % (github_base, base))
        return False, 0
    return github_mergeable(pull_request, runner, sleep, reads, sleep_seconds)


def replacement_pull_request_lines(base):
    """Return the instructions for clearing a conflict with a new pull request."""
    return [
        "Do not merge %s into this branch: a conflict with %s is never cleared "
        "by a merge." % (base, base),
        "If this branch has never been pushed, rebase it onto current %s, "
        "resolving the conflict, rerun the test suites for what the change "
        "touches, and push it; the lines below do not apply." % base,
        "If it has been pushed, do not push it again: its pull request is "
        "closed, and replaced by a new one only if %s still lacks some of its "
        "work. To see which commits on %s changed each conflicting file, run "
        "git log --oneline HEAD..%s -- <file>." % (base, base, base),
        "If %s already holds all of this branch's work, close the pull request "
        "with a comment naming the commit or pull request on %s that holds it, "
        "and open no new pull request." % (base, base),
        "Otherwise, cut a new topic branch from current %s and apply to it the "
        "part of this branch's change that %s lacks, resolving the conflict."
        % (base, base),
        "Before pushing the new branch, rerun the test suites for what the "
        "change touches.",
        "Push the new branch once, and open a new pull request from it whose "
        "description links the old pull request.",
        "Then close the old pull request with one comment that links the new "
        "pull request and names any commit or pull request on %s that already "
        "holds part of the work." % base,
    ]


def unresolved_lines(side, rev):
    """Return the UNRESOLVED message for a rev that names no commit."""
    return [
        "UNRESOLVED: %s %s does not resolve to a commit; do not act on any "
        "conflict answer until a run succeeds." % (side, rev),
        "If %s is mistyped, correct --%s, then rerun." % (rev, side),
        "If %s is not fetched, fetch it, then rerun." % rev,
    ]


def check(head, base, pull_request=None, runner=run, sleep=time.sleep,
          reads=GITHUB_UNKNOWN_READS, sleep_seconds=GITHUB_UNKNOWN_SLEEP_SECONDS,
          fetch=True, remote=DEFAULT_FETCH_REMOTE):
    """Return (exit status, report lines)."""
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

    base_full_ref = full_ref_name(base, runner)
    if (fetch and base_full_ref is not None
            and not base_full_ref.startswith("refs/remotes/%s/" % remote)):
        return EXIT_BAD_INVOCATION, [
            "UNMATCHED: --base %s is not a branch of %s, the remote this run "
            "fetched, so the fetch did not move it; do not act on any conflict "
            "answer until a run succeeds." % (base, remote),
            "If you meant %s's branch, rerun with --base %s/<branch>."
            % (remote, remote),
            "If you meant %s exactly as this checkout has it, rerun with "
            "--no-fetch." % base,
        ]

    base_hash = resolve_commit(base, runner)
    if base_hash is None:
        return EXIT_BAD_INVOCATION, unresolved_lines("base", base)
    head_hash = resolve_commit(head, runner)
    if head_hash is None:
        return EXIT_BAD_INVOCATION, unresolved_lines("head", head)

    merge_status, merge_output = merge_tree_answer(base_hash, head_hash, runner)
    if merge_status not in (MERGE_TREE_CLEAN, MERGE_TREE_CONFLICT):
        return EXIT_BAD_INVOCATION, [
            "UNANSWERED: git merge-tree exited %d merging %s into %s; do not "
            "act on it as a conflict or as clean."
            % (merge_status, commit_label(head_hash, runner),
               commit_label(base_hash, runner)),
            "Do not act on this result: open no new pull request and close "
            "none.",
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
            verdict, taken = github_verdict_for_base(
                pull_request, base, base_branch_name(base_full_ref, remote),
                lines, runner, sleep, reads, sleep_seconds)
            if verdict is None:
                lines.append(
                    "GITHUB: could not be asked (gh failed) -- git's answer "
                    "stands")
            elif verdict is not False:
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
                        "allowed, so the pull request still needs replacing "
                        "with a new one cut from current main.")
                    conflict = True
                elif verdict == "MERGEABLE" and conflict:
                    lines.append(
                        "DISCLOSURE: git finds a conflict but GitHub reports "
                        "MERGEABLE; treating it as a conflict, because a merge "
                        "that git cannot do is not one to attempt.")

    if conflict:
        stages = conflicted_paths(merge_output)
        deleted = paths_deleted_on_base(stages)
        if deleted:
            lines[0:0] = deleted_on_base_lines(
                head_hash, base, base_hash, stages, deleted,
                two_path_messages(merge_output), runner)
            return EXIT_CONFLICT, lines

    if conflict:
        lines[0:0] = [
            "VERDICT: CONFLICT -- %s conflicts with %s."
            % (commit_label(head_hash, runner), base),
        ] + replacement_pull_request_lines(base)
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
