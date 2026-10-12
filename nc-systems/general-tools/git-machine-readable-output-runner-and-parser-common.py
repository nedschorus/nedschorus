#!/usr/bin/env python3
"""Run git in its machine-readable output forms and return parsed values.

Without -z, git C-quotes any path holding a non-ASCII byte, a double quote, a
backslash or a control character ("caf\\303\\251.md"), shows a rename as
"old -> new", and ends each path at a newline a path may itself contain. A
program that splits such output on newlines or whitespace gets a name that is
no file. Every reader here takes the -z form, where each path is a NUL-ended
field, exactly as stored.

Two layers, so a program keeps its own way of running git (its timeout, its
environment, how it reports a failure) and still shares the parsing:

  * Parsers take the stdout of a -z command, as bytes or str, and return
    values. They run nothing.
  * Runners run `git -C <directory> ...` with -z already in place, raise
    GitCommandFailed when git fails, does not start or does not finish, and
    return what the matching parser returns.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "git_machine_readable_output_runner_and_parser_common", <path>)
"""

import codecs
import os
import subprocess
from typing import NamedTuple

GIT_TIMEOUT_SECONDS = 60


class GitCommandFailed(Exception):
    """git exited with a code the caller did not accept, did not start, or timed out.

    returncode is None when git did not start or did not finish.
    """

    def __init__(self, arguments, directory, returncode, stderr):
        self.arguments = list(arguments)
        self.directory = str(directory)
        self.returncode = returncode
        self.stderr = stderr
        if returncode is None:
            outcome = stderr
        else:
            outcome = f"exit {returncode}: {stderr.strip() or 'no error text'}"
        super().__init__(f"git {' '.join(self.arguments)} in {self.directory} failed ({outcome})")


class GitStatusEntry(NamedTuple):
    """One entry of `git status --porcelain -z`.

    code is the two-letter XY status; origin_path is the path a rename or
    copy came from, in either column, else None.
    """
    code: str
    path: str
    origin_path: str | None


class GitNameStatusEntry(NamedTuple):
    """One entry of `git diff --name-status -z` or `git diff-tree --name-status -z`.

    status is git's letter with any score, such as "M" or "R100"; for a rename
    or copy, path is the new path and origin_path the old one.
    """
    status: str
    path: str
    origin_path: str | None


class GitNumstatEntry(NamedTuple):
    """One entry of `git diff --numstat -z`; added and deleted are None for a binary file."""
    added: int | None
    deleted: int | None
    path: str
    origin_path: str | None


class GitTreeEntry(NamedTuple):
    """One entry of `git ls-tree -z`, with or without -l; size is None without -l and for a tree."""
    mode: str
    object_type: str
    object_name: str
    size: int | None
    path: str


class GitGrepMatch(NamedTuple):
    """One line of `git grep -z -n`; text is the matched part alone when -o was given."""
    path: str
    line_number: int
    text: str


class GitWorktreeRecord(NamedTuple):
    """One worktree of `git worktree list --porcelain -z`.

    branch is the full ref name, such as refs/heads/main, or None when
    detached or bare; locked_reason and prunable_reason are "" when git gave
    the attribute without a reason, and None when git did not give it.
    """
    path: str
    head: str | None
    branch: str | None
    bare: bool
    detached: bool
    locked_reason: str | None
    prunable_reason: str | None


def _text(output):
    if isinstance(output, bytes):
        return os.fsdecode(output)
    return output


def nul_separated_fields(output):
    """Return the non-empty NUL-ended fields of -z output, in git's order."""
    return [field for field in _text(output).split("\0") if field]


def status_entries(output):
    """Parse `git status --porcelain -z` (porcelain v1) into GitStatusEntry values."""
    fields = iter(nul_separated_fields(output))
    entries = []
    for field in fields:
        code, path = field[:2], field[3:]
        origin_path = next(fields, None) if ("R" in code or "C" in code) else None
        entries.append(GitStatusEntry(code, path, origin_path))
    return entries


def name_status_entries(output):
    """Parse `--name-status -z` output into GitNameStatusEntry values."""
    fields = iter(nul_separated_fields(output))
    entries = []
    for status in fields:
        if status[:1] in ("R", "C"):
            origin_path = next(fields, None)
            entries.append(GitNameStatusEntry(status, next(fields, None), origin_path))
        else:
            entries.append(GitNameStatusEntry(status, next(fields, None), None))
    return entries


def numstat_entries(output):
    """Parse `git diff --numstat -z` output into GitNumstatEntry values."""
    # A rename or copy prints its counts with an empty path, then the old
    # path and the new path as fields of their own.
    fields = iter(_text(output).split("\0"))
    entries = []
    for field in fields:
        if not field:
            continue
        added, deleted, path = field.split("\t", 2)
        counts = (None if added == "-" else int(added),
                  None if deleted == "-" else int(deleted))
        if path:
            entries.append(GitNumstatEntry(*counts, path, None))
        else:
            origin_path = next(fields, None)
            entries.append(GitNumstatEntry(*counts, next(fields, None), origin_path))
    return entries


def tree_entries(output):
    """Parse `git ls-tree -z` output, with or without -l, into GitTreeEntry values."""
    entries = []
    for field in nul_separated_fields(output):
        meta, _, path = field.partition("\t")
        parts = meta.split()
        size = int(parts[3]) if len(parts) > 3 and parts[3] != "-" else None
        entries.append(GitTreeEntry(parts[0], parts[1], parts[2], size, path))
    return entries


def grep_matches(output):
    """Parse `git grep -z -n` output, with or without -o, into GitGrepMatch values."""
    # With -z the path and the line number each end at a NUL; the text ends at
    # the newline, and only the text can hold neither.
    text = _text(output)
    matches = []
    position = 0
    while position < len(text):
        path_end = text.index("\0", position)
        number_end = text.index("\0", path_end + 1)
        line_end = text.find("\n", number_end + 1)
        if line_end == -1:
            line_end = len(text)
        matches.append(GitGrepMatch(text[position:path_end],
                                    int(text[path_end + 1:number_end]),
                                    text[number_end + 1:line_end]))
        position = line_end + 1
    return matches


def worktree_records(output):
    """Parse `git worktree list --porcelain -z` into GitWorktreeRecord values."""
    # Each attribute is one NUL-ended field; an empty field ends a worktree.
    records = []
    attributes = {}
    for field in _text(output).split("\0"):
        if field:
            name, _, value = field.partition(" ")
            attributes[name] = value
            continue
        if "worktree" in attributes:
            records.append(GitWorktreeRecord(
                path=attributes["worktree"],
                head=attributes.get("HEAD"),
                branch=attributes.get("branch"),
                bare="bare" in attributes,
                detached="detached" in attributes,
                locked_reason=attributes.get("locked"),
                prunable_reason=attributes.get("prunable")))
        attributes = {}
    return records


def merge_tree_conflicted_stages(output):
    """Return {path: set of index stages} from `git merge-tree --write-tree -z`, in git's order."""
    # The tree hash comes first, then one "<mode> <object> <stage>\t<path>"
    # field per conflicted stage, then an empty field before the messages.
    stages = {}
    for field in _text(output).split("\0")[1:]:
        meta, tab, path = field.partition("\t")
        parts = meta.split(" ")
        if not tab or len(parts) != 3:
            break
        stages.setdefault(path, set()).add(parts[2])
    return stages


def merge_tree_conflicted_names(output):
    """Return the conflicted paths from `git merge-tree --write-tree --name-only -z`."""
    # The tree hash comes first; the names end at the first empty field.
    names = []
    for field in _text(output).split("\0")[1:]:
        if not field:
            break
        names.append(field)
    return names


def patch_header_path(text):
    """Return the path in a patch's `--- ` or `+++ ` header line, the prefix
    removed, as stored.

    A patch has no -z form. git writes a path holding a non-ASCII byte, a
    double quote, a backslash or a control character inside double quotes,
    with C escapes, and ends an unquoted path holding a space with a tab.
    """
    if len(text) >= 2 and text.startswith('"') and text.endswith('"'):
        raw, _ = codecs.escape_decode(text[1:-1].encode("ascii", "backslashreplace"))
        return os.fsdecode(raw)
    return text[:-1] if text.endswith("\t") else text


def run_git(directory, arguments, *, accepted_exit_codes=(0,),
            timeout_seconds=GIT_TIMEOUT_SECONDS, environment=None):
    """Run `git -C <directory> <arguments>` and return its stdout as bytes."""
    arguments = list(arguments)
    try:
        result = subprocess.run(["git", "-C", str(directory), *arguments],
                                stdin=subprocess.DEVNULL, capture_output=True,
                                timeout=timeout_seconds, env=environment)
    except subprocess.TimeoutExpired:
        raise GitCommandFailed(arguments, directory, None,
                               f"did not finish within {timeout_seconds} s") from None
    except OSError as error:
        raise GitCommandFailed(arguments, directory, None,
                               f"could not start git: {error}") from None
    if result.returncode not in accepted_exit_codes:
        raise GitCommandFailed(arguments, directory, result.returncode,
                               os.fsdecode(result.stderr))
    return result.stdout


def _with_nul_separator(subcommand, arguments):
    return [subcommand, "-z", *arguments]


def git_paths(directory, subcommand, *arguments, **run_options):
    """Run a git subcommand that lists paths, such as `diff --name-only` or
    `ls-files`, with -z, and return the paths in git's order.

    Give the subcommand and its options without -z: `git_paths(top, "diff",
    "--name-only", "HEAD")`.
    """
    return nul_separated_fields(
        run_git(directory, _with_nul_separator(subcommand, arguments), **run_options))


def git_status(directory, *arguments, **run_options):
    """Run `git status --porcelain -z <arguments>` and return GitStatusEntry values."""
    return status_entries(run_git(directory, ["status", "--porcelain", "-z", *arguments],
                                  **run_options))


def git_name_status(directory, subcommand, *arguments, **run_options):
    """Run `git <diff or diff-tree> -z --name-status <arguments>` and return GitNameStatusEntry values."""
    return name_status_entries(run_git(
        directory, _with_nul_separator(subcommand, ["--name-status", *arguments]),
        **run_options))


def git_numstat(directory, *arguments, **run_options):
    """Run `git diff -z --numstat <arguments>` and return GitNumstatEntry values."""
    return numstat_entries(run_git(directory, ["diff", "-z", "--numstat", *arguments],
                                   **run_options))


def git_tree_entries(directory, *arguments, **run_options):
    """Run `git ls-tree -z <arguments>` and return GitTreeEntry values."""
    return tree_entries(run_git(directory, ["ls-tree", "-z", *arguments], **run_options))


def git_grep_matches(directory, *arguments, **run_options):
    """Run `git grep -z -n <arguments>` and return GitGrepMatch values; no match is []."""
    run_options.setdefault("accepted_exit_codes", (0, 1))
    return grep_matches(run_git(directory, ["grep", "-z", "-n", *arguments], **run_options))


def git_worktrees(directory, **run_options):
    """Run `git worktree list --porcelain -z` and return GitWorktreeRecord values."""
    return worktree_records(run_git(directory, ["worktree", "list", "--porcelain", "-z"],
                                    **run_options))


def run_git_unless_outside_a_repository(directory, arguments, **run_options):
    """Run `git -C <directory> <arguments>` and return its stdout as bytes, or
    None when directory is in no git repository.

    Raises GitCommandFailed for any other failure.
    """
    # git exits 128 both for "not a repository" and for other fatal errors, and
    # the message is the one way to tell them apart. LC_ALL=C keeps the message
    # untranslated, and this is the one place in the project that reads it.
    environment = dict(run_options.pop("environment", None) or os.environ)
    environment["LC_ALL"] = "C"
    try:
        return run_git(directory, arguments, environment=environment, **run_options)
    except GitCommandFailed as failure:
        if failure.returncode is not None and "not a git repository" in failure.stderr:
            return None
        raise
