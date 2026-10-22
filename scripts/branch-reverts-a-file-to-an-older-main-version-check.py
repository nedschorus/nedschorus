#!/usr/bin/env python3
"""Report the files a branch sets back to a version main has since replaced.

Usage: branch-reverts-a-file-to-an-older-main-version-check.py [--head REF]
[--base REF]. The branch is --head, HEAD by default; the base is --base,
origin/main by default.

A branch squashed with `git reset --soft origin/main` after main moved keeps
its old index, so the squashed commit quietly undoes every change main made in
between to a file the branch's old base had at another version. Git merges such
a branch cleanly, because main has not changed the file since the new
merge-base, so neither the conflict check nor a merge notices.

For each file whose content the branch adds or changes against its merge-base
with the base, the check looks at the base's first-parent commits that changed
the file, by committer date, in the 30 days (WINDOW_DAYS) before the
merge-base. A pull request merged into main counts as its merge commit: the
report names the merge commit, not the pull request's own commits, and the
merge commit's hash is the one to name, as `git revert -m 1 <merge>` does. If
the branch's copy of the file has the same blob ID as the copy in one of those
commits' first parent, the branch undoes that commit for the file. Of the commits
that match, the newest is the one reported. A file the branch deletes is not
checked. A branch that means to undo the
reported commit names it, by at least its first 12 characters
(SHORT_COMMIT_LENGTH), anywhere in a commit message between the merge-base and
the branch, as `git revert` does; the check then accepts that file and looks no
further back in its history.

It does not fetch: run `git fetch origin` first.
scripts/git-client-side-hooks-pre-push-conflict-check.py runs this only on a
branch that scripts/branch-conflict-check.py, which fetches origin first, has
just found clean. It does not see an undo older than the window, or an undo
of part of a file, such as a branch that keeps main's new lines in one place and
an old copy of them in another.

Exit 0 when no file is set back, printing a `VERDICT: CLEAN` line on stdout.
Exit 1 when one is, printing on stdout a
`VERDICT: BRANCH-REVERTS-A-FILE-TO-AN-OLDER-MAIN-VERSION` line, then one line
per file naming the base's commit it undoes, then what to do. Exit 2 when git
fails, so no verdict can be given, printing nothing on stdout and, on stderr,
the failed git command and its error."""

import argparse
import re
import subprocess
import sys

DEFAULT_BASE = "origin/main"
# Long enough for a commit held unpushed for weeks; an undo older than this is
# rarely a stale index.
WINDOW_DAYS = 30
SECONDS_PER_DAY = 86400
SHORT_COMMIT_LENGTH = 12

EXIT_NOTHING_REVERTED = 0
EXIT_REVERTED = 1
EXIT_NO_ANSWER = 2

REVERTS_VERDICT_PREFIX = "VERDICT: BRANCH-REVERTS-A-FILE-TO-AN-OLDER-MAIN-VERSION"
HEX_WORD = re.compile(r"\b[0-9a-f]{%d,40}\b" % SHORT_COMMIT_LENGTH)


class GitFailed(Exception):
    pass


def run_git(arguments, input_text=None):
    """Return git's stdout, or raise GitFailed naming the command and its error."""
    command = ["git"] + arguments
    try:
        done = subprocess.run(command, input=input_text, capture_output=True,
                              text=True, encoding="utf-8", errors="replace")
    except (OSError, ValueError) as error:
        raise GitFailed("`%s` could not be started: %s" % (" ".join(command), error))
    if done.returncode != 0:
        raise GitFailed("`%s` exited %d: %s" % (" ".join(command), done.returncode,
                                                done.stderr.strip()))
    return done.stdout


def resolve_commit(rev):
    return run_git(["rev-parse", "--verify", rev + "^{commit}"]).strip()


def changed_paths(merge_base, head):
    """Return {path: head's blob ID} for every path whose content the branch adds or changes."""
    output = run_git(["diff", "--raw", "-z", "--no-abbrev", "--no-renames",
                      merge_base, head])
    fields = output.split("\0")
    states = {}
    for index in range(0, len(fields) - 1, 2):
        meta, path = fields[index].split(), fields[index + 1]
        # A deletion is left out: a branch that deletes or renames a file main
        # added recently would look like an undo of the commit that added it.
        # A mode-only change keeps main's current content, so it undoes nothing.
        if meta[4] != "D" and meta[2] != meta[3]:
            states[path] = meta[3]
    return states


def commits_changing(path, merge_base, since_seconds):
    output = run_git(["log", "--format=%H", "--no-renames", "--first-parent",
                      "--since=@%d" % since_seconds, merge_base, "--", path])
    return output.split()


def states_before(commit_path_pairs):
    """Return the blob ID, or None, of each path in each commit's first parent."""
    if not commit_path_pairs:
        return []
    lines = "".join("%s^:%s\n" % pair for pair in commit_path_pairs)
    output = run_git(["cat-file", "--batch-check=%(objectname) %(objecttype)"],
                     input_text=lines)
    states = []
    for line in output.splitlines():
        # A missing object's line is its name, which holds the path, then "missing".
        states.append(None if line.endswith(" missing") else line.split()[0])
    return states


def named_commit_prefixes(merge_base, head):
    messages = run_git(["log", "--format=%B", "%s..%s" % (merge_base, head)])
    return set(HEX_WORD.findall(messages.lower()))


def is_named(commit, prefixes):
    return any(commit.startswith(prefix) for prefix in prefixes)


def find_reverted_files(head, base):
    """Return (head hash, [(path, main's commit the branch undoes for it)])."""
    head_hash = resolve_commit(head)
    base_hash = resolve_commit(base)
    merge_base = run_git(["merge-base", head_hash, base_hash]).strip()
    head_states = changed_paths(merge_base, head_hash)
    if not head_states:
        return head_hash, []
    merge_base_seconds = int(run_git(["log", "-1", "--format=%ct", merge_base]).strip())
    since_seconds = merge_base_seconds - WINDOW_DAYS * SECONDS_PER_DAY
    pairs = [(commit, path) for path in sorted(head_states)
             for commit in commits_changing(path, merge_base, since_seconds)]
    prefixes = named_commit_prefixes(merge_base, head_hash)
    reverted = []
    decided_paths = set()
    # Newest first, so a named undo of main's newest change settles the file.
    for (commit, path), before in zip(pairs, states_before(pairs)):
        if path in decided_paths or before != head_states[path]:
            continue
        decided_paths.add(path)
        if not is_named(commit, prefixes):
            reverted.append((path, commit))
    return head_hash, reverted


def commit_subject(commit):
    return run_git(["log", "-1", "--format=%s", commit]).strip()


def report_lines(head_hash, base, reverted):
    head_label = head_hash[:SHORT_COMMIT_LENGTH]
    if not reverted:
        return ["VERDICT: CLEAN -- %s sets no file back to a version that %s replaced "
                "in the %d days before their merge-base. Nothing to do."
                % (head_label, base, WINDOW_DAYS)]
    lines = ["%s -- %s sets %d file(s) back to a version that a commit on %s "
             "replaced, so merging it would undo that commit for those files."
             % (REVERTS_VERDICT_PREFIX, head_label, len(reverted), base)]
    for path, commit in reverted:
        lines.append("  %s: back to its version before %s (%s)"
                     % (path, commit[:SHORT_COMMIT_LENGTH], commit_subject(commit)))
    lines += [
        "This usually means the branch was squashed or rebuilt from an index older "
        "than its new base, such as with `git reset --soft %s`." % base,
        "If you did not mean to undo that commit: for each file above, run "
        "`git checkout %s -- <path>`, put this branch's own changes to the file "
        "back on top, and commit." % base,
        "If you mean to undo it: name the commit, by at least its first %d "
        "characters, in a commit message on this branch, as `git revert` does."
        % SHORT_COMMIT_LENGTH,
        "Then push again.",
    ]
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--base", default=DEFAULT_BASE)
    args = parser.parse_args(argv)
    try:
        head_hash, reverted = find_reverted_files(args.head, args.base)
        lines = report_lines(head_hash, args.base, reverted)
    except GitFailed as error:
        print("branch-reverts-a-file-to-an-older-main-version-check: could not tell "
              "whether this branch sets a file back to a version %s has replaced, because "
              "%s; fix what git reports, then run this check again from your worktree: "
              "python3 scripts/branch-reverts-a-file-to-an-older-main-version-check.py "
              "--head %s --base %s" % (args.base, error, args.head, args.base),
              file=sys.stderr)
        return EXIT_NO_ANSWER
    for line in lines:
        print(line)
    return EXIT_REVERTED if reverted else EXIT_NOTHING_REVERTED


if __name__ == "__main__":
    sys.exit(main())
