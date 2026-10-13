#!/usr/bin/env python3
"""Refuse a push that loses a test case origin/main has, or that comes from a mutation-testing worktree.

Run by scripts/git-client-side-hooks/pre-push with git's pre-push arguments and the pushed refs
on standard input. Exit 10 refuses the push; exit 0 lets it through. A failure to look lets the
push through and says what was not checked, as the conflict check beside it does: a lost case
missed here can still be found in review, but a wrongly refused push stops work.

Lost test cases. A test case is a call to check() or case() whose first argument is a string,
or a def test_ function, in a *-test.py file. For each branch pushed to origin, other than main,
the cases of the test files the branch changes are read from git, never from the working tree,
at the branch's merge base with origin/main and at the pushed commit, and compared as one list,
so a case moved from one test file to another is not lost. A case at the merge base and not at
the pushed commit is lost unless a commit message between the two names it: its wording as
written, where each {...} of an f-string stands for any text, and any run of spaces and line
breaks matches any other. Tests pass whether or not a case is there, so nothing else shows that
one went. Not seen here: a case removed by deleting an item from a list that a check() call
loops over, and the cases of test files that use none of these forms.

Mutation-testing worktrees. scripts/run-suite-in-signal-sandbox.py runs a mutant only in a git
worktree whose directory name ends in MUTATION_TESTING_WORKTREE_LABEL, and removes the worktree after the
run. A push from a checkout whose top directory's name ends in the label, or of a branch whose
name ends in it, is refused, so a mutant cannot leave such a copy by a push.
"""

import ast
import collections
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

EXIT_ALLOW_PUSH = 0
EXIT_REFUSE_PUSH = 10
MUTATION_TESTING_WORKTREE_LABEL = "-mutation-testing-worktree"
CASE_FUNCTION_NAMES = ("check", "case")
TEST_FUNCTION_PREFIX = "test_"
TEST_FILE_PATHSPEC = "*-test.py"
BASE_REF = "origin/main"
MESSAGE_PREFIX = "pre-push: "
SHORT_COMMIT_LENGTH = 12
CONFLICT_CHECK_PATH = Path(__file__).resolve().parent / "git-client-side-hooks-pre-push-conflict-check.py"


def load_conflict_check():
    spec = importlib.util.spec_from_file_location("pre_push_conflict_check", CONFLICT_CHECK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(*arguments):
    return subprocess.run(["git", *arguments], capture_output=True, text=True, check=False)


def say(line):
    print(MESSAGE_PREFIX + line, file=sys.stderr)


def mutation_testing_worktree_refusal(pushed_refs_text):
    """Return the refusal lines for a push from a mutation-testing worktree or of such a branch, or []."""
    top = git("rev-parse", "--show-toplevel")
    if top.returncode == 0 and Path(top.stdout.strip()).name.endswith(MUTATION_TESTING_WORKTREE_LABEL):
        copy = top.stdout.strip()
        return [
            f"this push is refused, because it comes from {copy}, whose directory name ends "
            f"in {MUTATION_TESTING_WORKTREE_LABEL}: a copy made to run a mutant in, where a file may still "
            f"hold the mutant.",
            "Push from the checkout you work in, not from this copy.",
            f"If no run is using this copy any more, remove it with: git worktree remove "
            f"--force {copy}",
        ]
    labelled = sorted({fields[2][len("refs/heads/"):]
                       for fields in (line.split() for line in pushed_refs_text.splitlines())
                       if len(fields) == 4 and fields[2].startswith("refs/heads/")
                       and fields[2].endswith(MUTATION_TESTING_WORKTREE_LABEL)})
    if labelled:
        return [
            f"this push is refused, because it pushes {', '.join(labelled)}, whose name ends in "
            f"{MUTATION_TESTING_WORKTREE_LABEL}, the label that marks a copy made to run a mutant in, where a "
            f"file may still hold the mutant.",
            f"Push the work from the checkout you work in, under a branch name that does not "
            f"end in {MUTATION_TESTING_WORKTREE_LABEL}.",
        ]
    return []


def case_patterns_in(source):
    """Return [(wording, pattern)] for each test case the Python source defines.

    Raises SyntaxError when the source is not Python.
    """
    cases = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name.startswith(TEST_FUNCTION_PREFIX):
            cases.append((node.name, re.escape(node.name)))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in CASE_FUNCTION_NAMES and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                cases.append((first.value, words_pattern(first.value)))
            elif isinstance(first, ast.JoinedStr):
                wording, patterns = [], []
                for part in first.values:
                    if isinstance(part, ast.Constant):
                        wording.append(part.value)
                        patterns.append(words_pattern(part.value))
                    else:
                        wording.append("{" + ast.unparse(part.value) + "}")
                        patterns.append(".*?")
                cases.append(("".join(wording), "".join(patterns)))
    return cases


def words_pattern(text):
    """Return a pattern for text in which any run of spaces and line breaks matches any other."""
    return r"\s+".join(re.escape(word) for word in text.split())


def test_files_changed(base, head):
    changed = git("diff", "--name-only", "--no-renames", "-z", base, head, "--", TEST_FILE_PATHSPEC)
    if changed.returncode != 0:
        raise RuntimeError(f"git diff failed: {changed.stderr.strip()}")
    return [path for path in changed.stdout.split("\0") if path]


def cases_of(revision, path):
    """Return the test cases of path at revision, [] when it is not there; raise SyntaxError."""
    shown = git("show", f"{revision}:{path}")
    return case_patterns_in(shown.stdout) if shown.returncode == 0 else []


def cases_at_both_ends(base, head, paths, unchecked):
    """Return ({wording: (path, pattern)} at base, Counter at base, Counter at head).

    A file that is not Python at either end is left out at both, and named in unchecked.
    """
    found, base_counts, head_counts = {}, collections.Counter(), collections.Counter()
    for path in paths:
        try:
            at_base, at_head = cases_of(base, path), cases_of(head, path)
        except SyntaxError as error:
            unchecked.append(f"{path} could not be read as Python ({error.msg}, line "
                             f"{error.lineno}), so its test cases were not compared.")
            continue
        for wording, pattern in at_base:
            found.setdefault(wording, (path, pattern))
            base_counts[wording] += 1
        for wording, _ in at_head:
            head_counts[wording] += 1
    return found, base_counts, head_counts


def lost_test_cases(branch, head, unchecked):
    """Return [(path, wording)] for the cases the branch loses without a commit message naming them."""
    base = git("merge-base", BASE_REF, head)
    if base.returncode != 0:
        unchecked.append(f"{branch} has no merge base with {BASE_REF} here, so its test cases "
                         f"were not compared.")
        return []
    base = base.stdout.strip()
    paths = test_files_changed(base, head)
    if not paths:
        return []
    at_base, base_counts, head_counts = cases_at_both_ends(base, head, paths, unchecked)
    gone = base_counts - head_counts
    if not gone:
        return []
    messages = git("log", "--format=%B", f"{base}..{head}")
    if messages.returncode != 0:
        raise RuntimeError(f"git log failed: {messages.stderr.strip()}")
    said = " ".join(messages.stdout.split())
    return [(at_base[wording][0], wording) for wording in sorted(gone)
            if not re.search(at_base[wording][1], said)]


def lost_test_case_refusal(branch, head, lost):
    lines = [f"this push is refused, because branch {branch} ({head[:SHORT_COMMIT_LENGTH]}) no "
             f"longer has these test cases, which {BASE_REF} has, and no commit message on the "
             f"branch names them:"]
    lines += [f"  {path}: {wording}" for path, wording in lost]
    lines += [
        "A test case that is gone stops checking what it checked, and the tests that remain "
        "still pass, so nothing else shows that it went.",
        "If a case went by mistake, put it back, commit, and push again.",
        f"If a case went on purpose, or was reworded, commit a message that names each case "
        f"above by its wording on {BASE_REF} and says why it went, then push again; an empty "
        f"commit (git commit --allow-empty) can carry that message.",
    ]
    return lines


def main():
    pushed_refs = sys.stdin.read()
    remote_name = sys.argv[1] if len(sys.argv) > 1 else ""
    refusal = mutation_testing_worktree_refusal(pushed_refs)
    if refusal:
        for line in refusal:
            say(line)
        return EXIT_REFUSE_PUSH
    conflict_check = load_conflict_check()
    if remote_name != conflict_check.CHECKED_REMOTE_NAME:
        return EXIT_ALLOW_PUSH
    refused = False
    unchecked = []
    for branch, head in conflict_check.branches_to_check(pushed_refs):
        lost = lost_test_cases(branch, head, unchecked)
        if lost:
            refused = True
            for line in lost_test_case_refusal(branch, head, lost):
                say(line)
    for line in unchecked:
        say(line)
    return EXIT_REFUSE_PUSH if refused else EXIT_ALLOW_PUSH


if __name__ == "__main__":
    sys.exit(main())
