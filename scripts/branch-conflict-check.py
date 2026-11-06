#!/usr/bin/env python3
"""Check branch conflicts using git and GitHub.

The head checked is --head; with --pull-request and no --head it is the pull
request's pushed head on GitHub, fetched by its hash from --fetch-remote when
this checkout lacks it, under --no-fetch too, and with no --pull-request it is
HEAD.

GitHub can refuse a merge that git resolves cleanly, so a matching GitHub
CONFLICTING verdict takes precedence. UNKNOWN is not evidence of a clean merge.

A CONFLICT report names, for each conflicting file, each commit on the base
that changed it since the branch forked, the commit's author, which the
launchers set to the agent-seat that wrote it, and the pull request whose merge
brought the commit in. It then says how the conflict is cleared, by the answer
of nc-systems/general-tools/pull-request-conflict-with-main-rebase-or-replace-answer-common.py
for the branch's open pull request: --pull-request names one; otherwise `gh pr
list` is asked about --branch, or, with neither --head nor --branch, about the
current branch. When no branch can be asked about, or gh cannot answer, the
report gives no answer and says how to rerun for one."""

import argparse
import importlib.util
import json
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

_rebase_or_replace_spec = importlib.util.spec_from_file_location(
    "pull_request_conflict_with_main_rebase_or_replace_answer_common",
    Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
    / "pull-request-conflict-with-main-rebase-or-replace-answer-common.py")
rebase_or_replace = importlib.util.module_from_spec(_rebase_or_replace_spec)
_rebase_or_replace_spec.loader.exec_module(rebase_or_replace)

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
            "Before you clear the conflict, find out for %s whether %s renamed it "
            "or deleted it: compare the branch's version of it with %s's version "
            "of each file named after \"possibly\" on its line, and do each "
            "RENAME CHECK that names it. A file with no \"possibly\" on its line and "
            "no RENAME CHECK naming it was deleted."
            % (marked, base, base))
    if unnamed:
        lines.append(
            "If a deleting commit is not named above, find it with git log "
            "--diff-filter=D %s -- <file>." % base)
    if renamed or checks:
        lines.append("Carry the branch's change to each renamed file onto its new name.")
    lines.append(
        "Drop the branch's change to each deleted file; if %s still lacks what "
        "that change was for, carry it in a file %s has." % (base, base))
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


def unresolved_lines(side, rev):
    """Return the UNRESOLVED message for a rev that names no commit."""
    return [
        "UNRESOLVED: %s %s does not resolve to a commit; do not act on any "
        "conflict answer until a run succeeds." % (side, rev),
        "If %s is mistyped, correct --%s, then rerun." % (rev, side),
        "If %s is not fetched, fetch it, then rerun." % rev,
    ]


def pull_request_frozen_head_gh_read_failure_report_lines(pull_request):
    """Return the UNREAD message for a pull request whose pushed head gh could not give."""
    return [
        "UNREAD: gh could not give pull request %d's pushed head, so there is "
        "no commit to check; do not act on any conflict answer until a run "
        "succeeds." % pull_request,
        "If gh is logged out or cannot reach GitHub, fix that, then rerun.",
        "If you meant to check a commit of your own, rerun with --head "
        "<commit>.",
    ]


def pull_request_frozen_head_fetch_failure_report_lines(pull_request, github_head, remote):
    """Return the UNRESOLVED message for a pushed head this checkout lacks and cannot fetch."""
    return [
        "UNRESOLVED: pull request %d's pushed head %s is not in this checkout, "
        "and git fetch %s %s did not bring it; do not act on any conflict "
        "answer until a run succeeds."
        % (pull_request, github_head, remote, github_head),
        "If --fetch-remote %s is not the repository the pull request is in, "
        "rerun with --fetch-remote naming that repository's remote." % remote,
        "Otherwise fix the fetch, then rerun.",
    ]


def pull_request_head(pull_request, remote, runner=run):
    """Return (pushed head hash, None), or (None, report lines) when it cannot be had."""
    github_head = github_head_commit(pull_request, runner)
    if github_head is None:
        return None, pull_request_frozen_head_gh_read_failure_report_lines(pull_request)
    if resolve_commit(github_head, runner) is None:
        # The default fetch skips a fork's pull request and a deleted branch.
        status, _ = runner(["git", "fetch", remote, github_head])
        if status != 0 or resolve_commit(github_head, runner) is None:
            return None, pull_request_frozen_head_fetch_failure_report_lines(
                pull_request, github_head, remote)
    return github_head, None


MERGED_PULL_REQUEST_SUBJECT = re.compile(r"^Merge pull request #(\d+) ")
SQUASHED_PULL_REQUEST_SUBJECT = re.compile(r"\(#(\d+)\)$")


def merging_pull_request(commit_hash, base_hash, runner=run):
    """Return the number of the pull request whose merge brought commit_hash
    onto the base, or the number a squashed commit's subject ends with when the
    commit is on the base's first-parent line itself; None when neither names one."""
    status, subject = runner(["git", "log", "-1", "--format=%s", commit_hash])
    squashed = SQUASHED_PULL_REQUEST_SUBJECT.search(subject) if status == 0 else None
    # The oldest first-parent commit that descends from the commit is the merge
    # that brought it onto the base, unless its first parent is the commit
    # itself: then the commit is on the first-parent line, and every later
    # merge only descends from it.
    status, out = runner(["git", "log", "--first-parent", "--ancestry-path", "--reverse",
                          "--format=%P%x1f%s", "%s..%s" % (commit_hash, base_hash)])
    if status == 0 and out:
        parents, _, oldest_subject = out.splitlines()[0].partition("\x1f")
        merged = MERGED_PULL_REQUEST_SUBJECT.match(oldest_subject)
        if merged and parents.split()[:1] != [commit_hash]:
            return merged.group(1)
    return squashed.group(1) if squashed else None


def main_side_change_lines(paths, head_hash, base, base_hash, runner=run):
    """Return a MAIN'S SIDE line for each commit on the base that changed one of
    paths since the head forked, naming its author and its pull request."""
    lines = []
    for path in paths:
        status, out = runner(["git", "log", "--no-merges", "--format=%H%x1f%an",
                              "%s..%s" % (head_hash, base_hash), "--", path])
        if status != 0:
            lines.append(
                "MAIN'S SIDE: %s -- git could not list the commits on %s that "
                "changed it; list them with git log %s..%s -- %s."
                % (path, base, head_hash[:12], base_hash[:12], path))
            continue
        for entry in out.splitlines():
            commit_hash, _, author = entry.partition("\x1f")
            number = merging_pull_request(commit_hash, base_hash, runner)
            lines.append(
                "MAIN'S SIDE: %s -- changed on %s by %s, written by agent-seat %s, %s."
                % (path, base, commit_label(commit_hash, runner), author,
                   "merged by pull request #%s" % number if number
                   else "in no pull request this run could find"))
    return lines


def current_branch_name(runner=run):
    """Return the current branch's name, or None on a detached HEAD or a git failure."""
    status, out = runner(["git", "symbolic-ref", "--quiet", "--short", "HEAD"])
    return out if status == 0 and out else None


def open_pull_request_of_branch(branch, runner=run):
    """Return (the open pull request's number, or False for none, None), or
    (None, why) when gh cannot answer."""
    status, out = runner(["gh", "pr", "list", "--state", "open", "--head", branch,
                          "--json", "number"])
    if status != 0:
        return None, "gh pr list exited %d" % status
    try:
        entries = json.loads(out or "[]")
        return (entries[0]["number"] if entries else False), None
    except (ValueError, KeyError, IndexError, TypeError):
        return None, "gh pr list printed what this run could not read"


def clearing_lines(pull_request, branch, head, base, runner=run):
    """Return the lines that say how this conflict is cleared."""
    if pull_request is None:
        if branch is None and head is None:
            branch = current_branch_name(runner)
        if branch is None:
            return [
                "ANSWER: none -- this run was given no branch to look up an open pull "
                "request for, so it cannot say whether the branch is rebased or its "
                "pull request replaced.",
                "Rerun with --pull-request <number> if the branch has an open pull "
                "request, or with --branch <branch name> otherwise.",
            ]
        pull_request, why = open_pull_request_of_branch(branch, runner)
        if pull_request is None:
            return [
                "ANSWER: none -- whether branch %s has an open pull request could not "
                "be looked up (%s), so this run cannot say whether it is rebased or "
                "its pull request replaced." % (branch, why),
                "If gh is logged out or cannot reach GitHub, fix that, then rerun.",
            ]
    answer = rebase_or_replace.pull_request_conflict_with_main_rebase_or_replace_answer(
        pull_request is not False)
    understand = [
        "Read each pull request a MAIN'S SIDE line names to learn what its change "
        "was for; %s's side is already reviewed, so leave its lines working." % base,
        "If you cannot tell what %s's change to a file meant, ask the agent-seat "
        "its MAIN'S SIDE line names, with SendMessage, naming the file and the "
        "pull request on that line." % base,
    ]
    if answer == rebase_or_replace.REPLACE_WITH_NEW_PULL_REQUEST:
        return [
            "ANSWER: replace -- pull request #%s is open, so it is replaced by a new "
            "pull request; its branch is never rebased, merged into or force-pushed."
            % pull_request,
            "If %s already holds this branch's work, close pull request #%s with a "
            "comment naming the commit or pull request on %s that holds it, and stop."
            % (base, pull_request, base),
        ] + understand + [
            "Cut a new nc-topic-branch from current %s and carry this branch's work "
            "onto it, rewriting this branch's lines so that both changes work." % base,
            "Run python3 scripts/run-all-test-suites.py "
            "--only-suites-whose-recorded-inputs-changed-since %s." % base,
            "Open a new pull request whose description has the line #replaces "
            "followed by pull request #%s's URL, then close pull request #%s with a "
            "comment naming the new one." % (pull_request, pull_request),
        ]
    return [
        "ANSWER: rebase -- the branch has no open pull request, so it is rebased "
        "onto %s, even if it is already on origin." % base,
    ] + understand + [
        "Run git rebase %s, resolving each conflict so that both changes work." % base,
        "If the branch is built on another branch, run git rebase --onto %s "
        "<the other branch's head> instead." % base,
        "Run python3 scripts/run-all-test-suites.py "
        "--only-suites-whose-recorded-inputs-changed-since %s." % base,
        "If the branch is already on origin, push it with git push --force-with-lease; "
        "the pre-push hook saves the commit it replaces.",
    ]


def check(head, base, pull_request=None, runner=run, sleep=time.sleep,
          reads=GITHUB_UNKNOWN_READS, sleep_seconds=GITHUB_UNKNOWN_SLEEP_SECONDS,
          fetch=True, remote=DEFAULT_FETCH_REMOTE, branch=None):
    """Return (exit status, report lines); a head of None is chosen as the
    module docstring says."""
    lines = []
    head_given = head

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
    github_head = None
    if head is None and pull_request is None:
        head = "HEAD"
    elif head is None:
        github_head, refusal = pull_request_head(pull_request, remote, runner)
        if refusal:
            return EXIT_BAD_INVOCATION, refusal
        head = github_head
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
            "Do not rebase, replace or close anything on this result.",
            "If either commit is missing from this checkout, fetch it, then "
            "rerun.",
            "If the two commits share no history, check that --head and --base "
            "name the right commits, then rerun.",
            "If the object database is not writable, run from a checkout where "
            "it is, then rerun.",
        ]
    conflict = merge_status == MERGE_TREE_CONFLICT

    if pull_request is not None:
        if github_head is None:
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
                        "allowed, so the conflict is still cleared as below.")
                    conflict = True
                elif verdict == "MERGEABLE" and conflict:
                    lines.append(
                        "DISCLOSURE: git finds a conflict but GitHub reports "
                        "MERGEABLE; treating it as a conflict, because a merge "
                        "that git cannot do is not one to attempt.")

    if conflict:
        stages = conflicted_paths(merge_output)
        messages = two_path_messages(merge_output)
        deleted = paths_deleted_on_base(stages)
        if deleted:
            report = deleted_on_base_lines(
                head_hash, base, base_hash, stages, deleted, messages, runner)
        else:
            report = ["VERDICT: CONFLICT -- %s conflicts with %s."
                      % (commit_label(head_hash, runner), base)]
        own_paths = [own_path(path, messages,
                              RENAMES_FOR_A_FILE_THE_BASE_DELETED if path in deleted
                              else RENAMES_FOR_ANY_OTHER_CONFLICT)
                     for path in stages]
        report += main_side_change_lines(own_paths, head_hash, base, base_hash, runner)
        report += clearing_lines(pull_request, branch, head_given, base, runner)
        lines[0:0] = report
        return EXIT_CONFLICT, lines

    lines.insert(0, "VERDICT: CLEAN -- %s does not conflict with %s. Nothing to do."
                    % (commit_label(head_hash, runner), base))
    return EXIT_NO_CONFLICT, lines


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Report whether a branch conflicts with main.")
    parser.add_argument(
        "--head", default=None,
        help="the commit to check; default: the pull request's pushed head "
             "with --pull-request, otherwise HEAD")
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--pull-request", type=int, default=None)
    parser.add_argument(
        "--branch", default=None,
        help="the branch whose open pull request says how a conflict is cleared; "
             "default: the current branch when --head is not given")
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
        fetch=args.fetch, remote=args.fetch_remote, branch=args.branch)
    for line in lines:
        print(line)
    return status


if __name__ == "__main__":
    sys.exit(main())
