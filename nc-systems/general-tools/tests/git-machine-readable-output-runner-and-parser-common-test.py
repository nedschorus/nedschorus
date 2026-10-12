#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/git-machine-readable-output-runner-and-parser-common.py.

Runs real git in a throwaway repository whose paths are the ones hand-split
output gets wrong: a non-ASCII name, a name with a space, a name with a double
quote, a rename staged with `git mv`, and a rename that exists only in the
worktree column, which `git add -N` of a moved file produces.

Run: python3 nc-systems/general-tools/tests/git-machine-readable-output-runner-and-parser-common-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import ast
import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    REPOSITORY_ROOT / "scripts" / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

_spec = importlib.util.spec_from_file_location(
    "git_machine_readable_output_runner_and_parser_common",
    Path(__file__).resolve().parents[1] / "git-machine-readable-output-runner-and-parser-common.py")
git_output = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(git_output)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def git(directory, *arguments):
    subprocess.run(["git", "-C", str(directory), *arguments], check=True,
                   capture_output=True)


def output(directory, *arguments):
    return git_output.run_git(directory, list(arguments))


def scratch_repository(parent):
    """Commit one, then leave a staged rename, a worktree-column rename, a
    modified file with a space and an untracked file with a quote."""
    repository = Path(parent) / "repository"
    repository.mkdir()
    git(repository, "init", "-q", "-b", "main")
    git(repository, "config", "user.email", "test@example.com")
    git(repository, "config", "user.name", "test")
    (repository / "a.txt").write_text("a\n")
    (repository / "my notes.md").write_text("x\n")
    (repository / "café.md").write_text("c\n")
    git(repository, "add", "-A")
    git(repository, "commit", "-q", "-m", "one")
    git(repository, "mv", "a.txt", "moved-a.txt")
    (repository / "my notes.md").write_text("x\ny\n")
    (repository / "café.md").rename(repository / "cafe2.md")
    git(repository, "add", "-N", "cafe2.md")
    (repository / 'new "q".txt').write_text("u\n")
    return repository


def status_cases(repository):
    entries = git_output.status_entries(output(repository, "status", "--porcelain", "-z", "--untracked-files=all"))
    by_path = {entry.path: entry for entry in entries}
    check("status: a staged rename gives the new path and its origin",
          by_path.get("moved-a.txt") == ("R ", "moved-a.txt", "a.txt"), entries)
    check("status: a worktree-column rename (git add -N) keeps the walk in step",
          by_path.get("cafe2.md") == (" R", "cafe2.md", "café.md"), entries)
    check("status: a path with a space is one path",
          by_path.get("my notes.md") == (" M", "my notes.md", None), entries)
    check("status: a path with a double quote comes back unquoted",
          by_path.get('new "q".txt') == ("??", 'new "q".txt', None), entries)
    check("status: no other entries", len(entries) == 4, entries)


def path_list_cases(repository):
    tracked = git_output.nul_separated_fields(output(repository, "ls-files", "-z"))
    check("ls-files: the non-ASCII path is the real name",
          "café.md" in tracked and "my notes.md" in tracked, tracked)
    untracked = git_output.nul_separated_fields(
        output(repository, "ls-files", "-z", "--others", "--exclude-standard"))
    check("ls-files --others: the quoted name comes back as stored",
          untracked == ['new "q".txt'], untracked)
    names = git_output.nul_separated_fields(
        output(repository, "diff", "-z", "--name-only", "--no-renames", "HEAD"))
    check("diff --name-only: every path exactly as stored",
          sorted(names) == sorted(["a.txt", "moved-a.txt", "café.md", "cafe2.md", "my notes.md"]),
          names)
    at_head = git_output.nul_separated_fields(
        output(repository, "ls-tree", "-z", "-r", "--name-only", "HEAD"))
    check("ls-tree --name-only: real names", sorted(at_head) == ["a.txt", "café.md", "my notes.md"],
          at_head)


def name_status_and_numstat_cases(repository):
    entries = git_output.name_status_entries(
        output(repository, "diff", "-z", "--name-status", "-M", "HEAD"))
    by_path = {entry.path: entry for entry in entries}
    check("name-status: a rename gives its score, new path and old path",
          by_path.get("moved-a.txt") == ("R100", "moved-a.txt", "a.txt"), entries)
    check("name-status: a modification has no origin",
          by_path.get("my notes.md") == ("M", "my notes.md", None), entries)
    counts = git_output.numstat_entries(output(repository, "diff", "-z", "--numstat", "-M", "HEAD"))
    by_path = {entry.path: entry for entry in counts}
    check("numstat: a rename's empty path field is followed by old and new",
          by_path.get("moved-a.txt") == (0, 0, "moved-a.txt", "a.txt"), counts)
    check("numstat: counts of a path with a space",
          by_path.get("my notes.md") == (1, 0, "my notes.md", None), counts)
    binary = git_output.numstat_entries(b"-\t-\tpicture.png\0")
    check("numstat: a binary file has no counts", binary == [(None, None, "picture.png", None)],
          binary)


def tree_and_grep_cases(repository):
    entries = git_output.tree_entries(output(repository, "ls-tree", "-z", "-r", "-l", "HEAD"))
    by_path = {entry.path: entry for entry in entries}
    check("ls-tree -l: size and real name",
          by_path.get("café.md") is not None and by_path["café.md"].size == 2
          and by_path["café.md"].object_type == "blob", entries)
    directories = git_output.tree_entries(b"040000 tree 0123abc\tdocs\0")
    check("ls-tree: a tree entry has no size", directories[0].size is None, directories)
    matches = git_output.grep_matches(
        output(repository, "grep", "-z", "-n", "-I", "-o", "-w", "-F", "-e", "y", "-e", "x"))
    check("grep -z -n -o: path, line number and the matched text",
          sorted(matches) == [("my notes.md", 1, "x"), ("my notes.md", 2, "y")], matches)
    check("grep: no output is no match",
          git_output.grep_matches(b"") == [])
    try:
        git_output.grep_matches(b"Binary file picture.png matches\nnotes.md\x001\x00x\n")
        check("grep: a line with no path and line number is refused", False, "no exception")
    except ValueError as error:
        check("grep: a line with no path and line number is refused",
              "Binary file picture.png matches" in str(error), error)
    for unreadable in (b"notes.md\x007", b"notes.md matches\n"):
        try:
            git_output.grep_matches(unreadable)
            check(f"grep: a record without its path and line-number NULs is refused: {unreadable!r}",
                  False, "no exception")
        except ValueError as error:
            check(f"grep: a record without its path and line-number NULs is refused: {unreadable!r}",
                  "ends without a path and line number" in str(error), error)
    newline_path = git_output.grep_matches(b"nl\nname.txt\x002\x00needle\nb.md\x001\x00x\n")
    check("grep: a path holding a newline is read whole",
          newline_path == [("nl\nname.txt", 2, "needle"), ("b.md", 1, "x")], newline_path)
    unended = git_output.grep_matches(b"notes.md\x007\x00last line")
    check("grep: output that ends without a newline still gives its last match",
          unended == [("notes.md", 7, "last line")], unended)
    colon = git_output.grep_matches(b"a:b.md\x003\x00text: with colon\n")
    check("grep: a colon in the path or the text does not split it",
          colon == [("a:b.md", 3, "text: with colon")], colon)


def patch_header_cases(repository):
    patch = subprocess.run(["git", "-C", str(repository), "diff", "--no-renames", "HEAD"],
                           capture_output=True, check=True).stdout.decode("ascii", "replace")
    headers = [line[len("+++ "):] for line in patch.splitlines()
               if line.startswith(("+++ ", "--- "))]
    paths = sorted(git_output.patch_header_path(header) for header in headers
                   if header != "/dev/null")
    check("patch header: a C-quoted path and a path with a space, as stored",
          paths == ["a/a.txt", "a/café.md", "a/my notes.md",
                    "b/cafe2.md", "b/moved-a.txt", "b/my notes.md"], paths)
    quoted = git_output.patch_header_path('"b/caf\\303\\251 \\"q\\"\\t\\\\.md"')
    check("patch header: octal bytes, a quote, a tab and a backslash",
          quoted == 'b/café "q"\t\\.md', repr(quoted))
    raw_utf8 = git_output.patch_header_path('"b/café \\"q\\".md"')
    check("patch header: raw UTF-8 inside quotes (core.quotePath=false) stays UTF-8",
          raw_utf8 == 'b/café "q".md', repr(raw_utf8))
    quoted_with_space = git_output.patch_header_path('"b/docs/caf\\303\\251 notes.md"\t')
    check("patch header: a quoted path holding a space, followed by git's tab",
          quoted_with_space == "b/docs/café notes.md", repr(quoted_with_space))
    check("patch header: an unquoted path is left alone",
          git_output.patch_header_path("b/plain.md") == "b/plain.md")


def worktree_cases(repository, parent):
    other = Path(parent) / "other worktree"
    git(repository, "worktree", "add", "-q", "-b", "side", str(other), "HEAD")
    git(repository, "worktree", "lock", "--reason", "two\nlines", str(other))
    records = git_output.worktree_records(output(repository, "worktree", "list", "--porcelain", "-z"))
    check("worktree list: two records", len(records) == 2, records)
    side = [record for record in records if record.branch == "refs/heads/side"]
    check("worktree list: a path with a space and a lock reason with a newline",
          len(side) == 1 and side[0].path == str(other) and side[0].locked_reason == "two\nlines"
          and not side[0].detached and side[0].prunable_reason is None, records)
    gone = Path(parent) / "gone worktree"
    git(repository, "worktree", "add", "-q", "--detach", str(gone), "HEAD")
    subprocess.run(["rm", "-rf", str(gone)], check=True)
    pruned = [record for record in git_output.worktree_records(
        output(repository, "worktree", "list", "--porcelain", "-z")) if record.path == str(gone)]
    check("worktree list: a removed worktree carries git's prunable reason",
          len(pruned) == 1 and bool(pruned[0].prunable_reason), pruned)
    detached = git_output.worktree_records(b"worktree /w\0HEAD abc\0detached\0locked\0\0")
    check("worktree list: detached, and locked without a reason",
          detached == [("/w", "abc", None, False, True, "", None)], detached)


def merge_tree_cases(parent):
    repository = Path(parent) / "merging"
    repository.mkdir()
    git(repository, "init", "-q", "-b", "main")
    git(repository, "config", "user.email", "test@example.com")
    git(repository, "config", "user.name", "test")
    (repository / "côté.md").write_text("base\n")
    git(repository, "add", "-A")
    git(repository, "commit", "-q", "-m", "base")
    git(repository, "checkout", "-q", "-b", "side")
    (repository / "côté.md").write_text("side\n")
    git(repository, "commit", "-q", "-am", "side")
    git(repository, "checkout", "-q", "main")
    (repository / "côté.md").write_text("main\n")
    git(repository, "commit", "-q", "-am", "main")
    names = git_output.merge_tree_conflicted_names(git_output.run_git(
        repository, ["merge-tree", "--write-tree", "--name-only", "--no-messages", "-z",
                     "main", "side"], accepted_exit_codes=(1,)))
    check("merge-tree --name-only -z: the conflicted path as stored", names == ["côté.md"], names)
    stages = git_output.merge_tree_conflicted_stages(git_output.run_git(
        repository, ["merge-tree", "--write-tree", "-z", "main", "side"],
        accepted_exit_codes=(1,)))
    check("merge-tree -z: each conflicted stage", stages == {"côté.md": {"1", "2", "3"}}, stages)


def failure_cases(parent):
    outside = Path(parent) / "not a repository"
    outside.mkdir()
    try:
        git_output.run_git(outside, ["ls-files", "-z"])
        check("a failed git raises GitCommandFailed", False, "no exception")
    except git_output.GitCommandFailed as failure:
        check("a failed git raises GitCommandFailed with its exit code and stderr",
              failure.returncode == 128 and "not a git repository" in failure.stderr, failure)
    check("outside a repository: None",
          git_output.run_git_unless_outside_a_repository(outside, ["rev-parse", "--git-dir"])
          is None)
    # ned-box has no translated locale installed, so record what git is given.
    given = {}
    real_run_git = git_output.run_git

    def recording_run_git(directory, arguments, **run_options):
        given.update(run_options["environment"])
        return real_run_git(directory, arguments, **run_options)

    git_output.run_git = recording_run_git
    try:
        git_output.run_git_unless_outside_a_repository(
            outside, ["rev-parse", "--git-dir"],
            environment=dict(os.environ, LC_ALL="de_DE.UTF-8"))
    finally:
        git_output.run_git = real_run_git
    check("git's message is read untranslated: LC_ALL=C overrides the caller's locale",
          given.get("LC_ALL") == "C", given.get("LC_ALL"))
    try:
        git_output.run_git_unless_outside_a_repository(outside, ["no-such-subcommand"])
        check("another failure outside a repository is raised", False, "no exception")
    except git_output.GitCommandFailed as failure:
        check("another failure outside a repository is raised", failure.returncode == 1, failure)
    try:
        git_output.run_git(outside, ["--version"], environment={"PATH": str(outside)})
        check("git that cannot start raises", False, "no exception")
    except git_output.GitCommandFailed as failure:
        check("git that cannot start raises with no exit code",
              failure.returncode is None and "could not start git" in failure.stderr, failure)
    try:
        git_output.run_git(outside, ["hash-object", "--stdin"], timeout_seconds=0.000001)
        check("git that does not finish raises", False, "no exception")
    except git_output.GitCommandFailed as failure:
        check("git that does not finish raises with no exit code",
              failure.returncode is None and "did not finish" in failure.stderr, failure)


def python_3_9_cases():
    # The Mac's system Python is 3.9: an annotation written X | None is
    # evaluated when a NamedTuple class is made, unless annotations are deferred.
    source = Path(_spec.origin).read_text(encoding="utf-8")
    tree = ast.parse(source, feature_version=(3, 9))
    deferred = any(isinstance(node, ast.ImportFrom) and node.module == "__future__"
                   and any(alias.name == "annotations" for alias in node.names)
                   for node in tree.body)
    union_annotations = [node for node in ast.walk(tree)
                         if isinstance(node, ast.AnnAssign)
                         and isinstance(node.annotation, ast.BinOp)
                         and isinstance(node.annotation.op, ast.BitOr)]
    check("the module parses as Python 3.9, and its X | None annotations are deferred",
          deferred or not union_annotations, f"{len(union_annotations)} undeferred")


def main():
    with tempfile.TemporaryDirectory() as parent:
        repository = scratch_repository(parent)
        status_cases(repository)
        path_list_cases(repository)
        name_status_and_numstat_cases(repository)
        tree_and_grep_cases(repository)
        patch_header_cases(repository)
        worktree_cases(repository, parent)
        merge_tree_cases(parent)
        failure_cases(parent)
    python_3_9_cases()
    if failures:
        print(f"{len(failures)} case(s) failed")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
