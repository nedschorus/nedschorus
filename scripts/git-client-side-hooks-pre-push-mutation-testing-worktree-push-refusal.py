#!/usr/bin/env python3
"""Refuse a push from a mutation-testing worktree, or of a branch named like one.

Run by scripts/git-client-side-hooks/pre-push with git's pre-push arguments and the pushed refs
on standard input. Exit 10 refuses the push; exit 0 lets it through. Any other exit makes the
hook say the push went unchecked and to tell the user.

scripts/run-suite-in-signal-sandbox.py runs a mutant only in a git worktree whose directory name
ends in MUTATION_TESTING_WORKTREE_LABEL, and removes the worktree after the run. A push from a
checkout whose top directory's name ends in the label, or of a branch whose name ends in it, is
refused, so a mutant cannot leave such a worktree by a push.
"""

import subprocess
import sys
from pathlib import Path

EXIT_ALLOW_PUSH = 0
EXIT_REFUSE_PUSH = 10
EXIT_CHECK_FAILED = 1
MUTATION_TESTING_WORKTREE_LABEL = "-mutation-testing-worktree"
MESSAGE_PREFIX = "pre-push: "


def git_output(*arguments):
    """Return git's standard output; raise RuntimeError, naming the command, when git fails."""
    completed = subprocess.run(["git", *arguments], capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(arguments)} failed: {completed.stderr.strip()}")
    return completed.stdout


def say(line):
    print(MESSAGE_PREFIX + line, file=sys.stderr)


def mutation_testing_worktree_refusal(pushed_refs_text):
    """Return the refusal lines for a push from a mutation-testing worktree or of such a branch, or []."""
    top = git_output("rev-parse", "--show-toplevel").strip()
    if Path(top).name.endswith(MUTATION_TESTING_WORKTREE_LABEL):
        return [
            f"this push is refused, because it comes from {top}, whose directory name ends "
            f"in {MUTATION_TESTING_WORKTREE_LABEL}: a copy made to run a mutant in, where a file "
            f"may still hold the mutant.",
            "Push from the checkout you work in, not from this copy.",
            f"If no run is using this copy any more, remove it with: git worktree remove "
            f"--force {top}",
        ]
    labelled = sorted({fields[2][len("refs/heads/"):]
                       for fields in (line.split() for line in pushed_refs_text.splitlines())
                       if len(fields) == 4 and fields[2].startswith("refs/heads/")
                       and fields[2].endswith(MUTATION_TESTING_WORKTREE_LABEL)})
    if labelled:
        return [
            f"this push is refused, because it pushes {', '.join(labelled)}, whose name ends in "
            f"{MUTATION_TESTING_WORKTREE_LABEL}, the label that marks a copy made to run a mutant "
            f"in, where a file may still hold the mutant.",
            f"Push the work from the checkout you work in, under a branch name that does not "
            f"end in {MUTATION_TESTING_WORKTREE_LABEL}.",
        ]
    return []


def main():
    try:
        refusal = mutation_testing_worktree_refusal(sys.stdin.read())
    except RuntimeError as error:
        say(f"{error}, so this push was not checked for a mutation-testing worktree.")
        return EXIT_CHECK_FAILED
    for line in refusal:
        say(line)
    return EXIT_REFUSE_PUSH if refusal else EXIT_ALLOW_PUSH


if __name__ == "__main__":
    sys.exit(main())
