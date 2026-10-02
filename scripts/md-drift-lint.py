#!/usr/bin/env python3
"""Mechanical drift checks for MD (and JSON) files — the lint half of the sanity-check.

Grid-seat ruling (user-walked 2026-08-12, recorded in
docs/drafts/sanity-checker-prompt-draft.md): the worry band that needs no
judgment leaves the reviewer prompt for this script. It reports and never
edits. Zero model cost, so unlike the judgment review it may run repeatedly.

Checks, per file type:

  .md   - repo paths named in backticks or markdown links exist on disk
          (a path this repository deliberately does not track is skipped;
          a backtick citation with a line number, `file.md:120`, is checked
          as the file it names)
        - markdown link targets resolve (external schemes skipped; a target
          that is only a `<placeholder>` skipped; a target written in angle
          brackets, `[x](<docs/file.md>)`, checked as the path inside them
          when that path ends in a known extension; a link target keeps any
          line-number suffix, because a link written `file.md:120` is a
          broken link)
        - YYYY-MM-DD tokens are real calendar dates
        - a backtick command naming an existing project script also names
          only flags that appear in that script's source
        - a backtick span that is only a number, on a line naming exactly
          one existing project code file (.py/.sh), appears in that file's
          source, digit-group separators ignored. Prose numbers — counts,
          issue numbers, cardinalities — are never checked: backticks are
          what opt a number into the check.
  .json - no duplicate keys at any nesting depth (a duplicate key is legal
          JSON that parsers resolve silently: the second value wins and an
          edit to the first does nothing)

Usage:
  scripts/md-drift-lint.py FILE [FILE ...]

A file under a frozen-measured-data directory is skipped whole; see
FROZEN_MEASURED_DATA_DIRECTORIES.

Output: one "path:line: problem" per finding on stdout.
Exit codes: 0 clean, 1 findings, 2 bad invocation.
"""

import calendar
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PATH_EXTENSIONS = (".py", ".md", ".json", ".sh", ".toml", ".yml", ".yaml", ".txt", ".jsonl")

BACKTICK_TOKEN = re.compile(r"`([^`\n]+)`")
MARKDOWN_LINK = re.compile(r"\[[^\]\n]*\]\(([^)\s]+)\)")
DATE_TOKEN = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
FLAG_TOKEN = re.compile(r"--[a-z][a-z0-9-]+")
NUMBER_ONLY = re.compile(r"\d[\d_,]*(?:\.\d+)?")

# Prose-to-prose numbers are counts, not values quoted from code.
CODE_SOURCE_EXTENSIONS = (".py", ".sh")

SKIP_MARKERS = ("://", "<", "{", "*", "$", "~", "…")

# Collapse spaced placeholders before tokenizing; reject redirects and HTML comments.
# A leading slash may belong to a placeholder path, so do not exclude it.
PLACEHOLDER_SPAN = re.compile(r"<(?![!?])[^\s<>](?:[^<>]*[^\s<>])?>")


def unwrap_angle_link_target(target: str) -> str:
    """Unwrap angle-bracket file paths while leaving template placeholders intact."""
    inner = target[1:-1]
    if (PLACEHOLDER_SPAN.fullmatch(target)
            and inner.split("#", 1)[0].endswith(PATH_EXTENSIONS)):
        return inner
    return target

# Historical citations deliberately name paths absent from the working tree.
HISTORY_MARKERS = ("git history", "git show")

# References to another repository cannot be checked against this checkout.
FOREIGN_ROOT_MARKERS = ("~/Projects/nedlern", "nedlern/docs", "legacy system",
                        "~/Projects/nedsmessenger")

# These citations are frozen measurements; changing them invalidates published scores.
FROZEN_MEASURED_DATA_DIRECTORIES = ("cold-read-reviewer-test-cases",)

_basename_index_cache = {}
_git_ignore_cache = {}
_git_ignore_warned = set()


def repo_relative_candidates(token: str, md_path: Path, repo_root: Path):
    """Return possible repo-relative paths without requiring files to exist."""
    token = token.lstrip("/") or token
    for base in (repo_root, md_path.parent):
        candidate = os.path.normpath(os.path.join(str(base), token))
        try:
            relative = os.path.relpath(candidate, str(repo_root))
        except ValueError:  # Different drive on Windows.
            continue
        if not relative.startswith(".."):
            yield relative


def ignored_by_git(token: str, md_path: Path, repo_root: Path) -> bool:
    """Return whether the repository's ignore rules exclude the cited path."""
    return any(
        _git_says_ignored(relative, repo_root)
        for relative in repo_relative_candidates(token, md_path, repo_root)
    )


def _git_says_ignored(relative: str, repo_root: Path) -> bool:
    key = (str(repo_root), relative)
    if key in _git_ignore_cache:
        return _git_ignore_cache[key]
    _git_ignore_cache[key] = answer = _ask_git_check_ignore(relative, repo_root)
    return answer


def _ask_git_check_ignore(relative: str, repo_root: Path) -> bool:
    # A worktree's .git is a file, so test existence rather than is_dir().
    if not (repo_root / ".git").exists():
        return False
    # Ignore rules must be repository-local so both machines report the same findings.
    command = ["git", "-c", "core.excludesFile=/dev/null",
               "check-ignore", "--quiet", "--", relative]
    try:
        completed = subprocess.run(command, cwd=str(repo_root), capture_output=True)
    except OSError as error:
        _warn_once(repo_root, f"git could not be run ({error})")
        return False
    # git check-ignore uses 0 for ignored and 1 for not ignored; other exits are failures.
    if completed.returncode in (0, 1):
        return completed.returncode == 0
    detail = completed.stderr.decode("utf-8", "replace").strip() or f"exit {completed.returncode}"
    _warn_once(repo_root, f"git check-ignore failed ({detail})")
    return False


def _warn_once(repo_root: Path, detail: str):
    if str(repo_root) in _git_ignore_warned:
        return
    _git_ignore_warned.add(str(repo_root))
    print(f"md-drift-lint: {detail}; treating no path as deliberately untracked, "
          f"so citations of the record stores will be reported", file=sys.stderr)


LINE_SUFFIXED_PATH = re.compile(r"^(?P<path>[^\s:]+):(?P<line>\d+)$")


def without_line_suffix(token: str) -> str:
    """Remove a trailing :line number from a backtick citation."""
    match = LINE_SUFFIXED_PATH.match(token)
    return match.group("path") if match else token


def looks_like_repo_path(token: str) -> bool:
    token = without_line_suffix(token)
    if any(marker in token for marker in SKIP_MARKERS):
        return False
    if ":" in token:  # git show REF:path, URLs and drive letters.
        return False
    # Bare extensions describe file types, not files required at the repository root.
    if token.startswith(".") and "/" not in token:
        return False
    # Only known repo-root components make an absolute-looking path this repository's concern.
    if token.startswith("/"):
        first = token.lstrip("/").split("/", 1)[0]
        if not (REPO_ROOT / first).exists():
            return False
    return token.endswith(PATH_EXTENSIONS) and not token.startswith("-")


def basename_index(repo_root: Path) -> set:
    """Return an index of files by basename."""
    if repo_root not in _basename_index_cache:
        _basename_index_cache[repo_root] = {
            item.name for item in repo_root.rglob("*")
            if item.is_file() and ".git" not in item.parts
        }
    return _basename_index_cache[repo_root]


def resolve(token: str, md_path: Path, repo_root: Path):
    """Return an existing Path, a truthy marker, or None."""
    token = token.lstrip("/") or token
    candidates = [repo_root / token, md_path.parent / token]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    # Prose may cite a basename without its directory.
    if "/" not in token and token in basename_index(repo_root):
        matches = sorted(
            item for item in repo_root.rglob(token) if ".git" not in item.parts
        )
        if matches:
            return matches[0]
    return None


def check_dates(line: str):
    for match in DATE_TOKEN.finditer(line):
        year, month, day = (int(part) for part in match.groups())
        if not 1 <= month <= 12 or not 1 <= day <= calendar.monthrange(year, month)[1]:
            yield f"impossible date {match.group(0)}"


def check_backtick_paths(line: str, md_path: Path, repo_root: Path):
    for match in BACKTICK_TOKEN.finditer(line):
        token = match.group(1).strip()
        words = PLACEHOLDER_SPAN.sub("<placeholder>", token).split()
        for word in words:
            # A bare filename makes no claim about location and may describe a generated file.
            if "/" not in word:
                continue
            # Strip line numbers before check-ignore too; ignore patterns match paths, not citations.
            path = without_line_suffix(word)
            if (looks_like_repo_path(word)
                    and resolve(path, md_path, repo_root) is None
                    and not ignored_by_git(path, md_path, repo_root)):
                yield f"path does not exist: {word}"
        # Only the command's script owns its flags; a script path in git arguments does not.
        first = words[0] if words else ""
        if first in ("python", "python3", "python3.13") and len(words) > 1:
            first = words[1]
        script = resolve(first, md_path, repo_root) if first.endswith(".py") else None
        if script is not None:
            try:
                source = script.read_text(encoding="utf-8")
            except OSError:
                continue
            for flag in FLAG_TOKEN.findall(token):
                # Reject flag prefixes such as --dry when only --dry-run exists.
                if not re.search(rf"{re.escape(flag)}(?![a-z0-9-])", source):
                    yield f"flag {flag} not found in {script.name}"


def canonical_number(token: str) -> str:
    return token.replace("_", "").replace(",", "")


def referenced_files(line: str, md_path: Path, repo_root: Path):
    """Return distinct existing files named in backticks or links."""
    tokens = []
    # Backtick citations allow :line suffixes; GitHub link targets do not.
    for match in BACKTICK_TOKEN.finditer(line):
        tokens.extend(without_line_suffix(word)
                      for word in match.group(1).strip().split()
                      if looks_like_repo_path(word))
    for match in MARKDOWN_LINK.finditer(line):
        target = unwrap_angle_link_target(match.group(1))
        if "://" in target or target.startswith(("mailto:", "#")):
            continue
        bare = target.split("#", 1)[0]
        if bare:
            tokens.append(bare)
    distinct = {}
    for token in tokens:
        found = resolve(token, md_path, repo_root)
        if found is not None and found.is_file():
            distinct[found.resolve()] = found
    return list(distinct.values())


def check_code_numbers(line: str, md_path: Path, repo_root: Path):
    """Yield findings for backticked numbers absent from the line's sole referenced code file."""
    number_spans = [
        match.group(1).strip() for match in BACKTICK_TOKEN.finditer(line)
        if NUMBER_ONLY.fullmatch(match.group(1).strip())
    ]
    if not number_spans:
        return
    sources = [
        source for source in referenced_files(line, md_path, repo_root)
        if source.suffix in CODE_SOURCE_EXTENSIONS
    ]
    if len(sources) != 1:
        return
    try:
        source_numbers = {
            canonical_number(token)
            for token in NUMBER_ONLY.findall(sources[0].read_text(encoding="utf-8"))
        }
    except (OSError, UnicodeDecodeError):
        return
    for span in number_spans:
        if canonical_number(span) not in source_numbers:
            yield f"number {span} not found in {sources[0].name}"


def check_markdown_links(line: str, md_path: Path, repo_root: Path):
    for match in MARKDOWN_LINK.finditer(line):
        target = unwrap_angle_link_target(match.group(1))
        if "://" in target or target.startswith(("mailto:", "#")):
            continue
        # A whole placeholder target is a template address supplied by the reader.
        if PLACEHOLDER_SPAN.fullmatch(target):
            continue
        bare = target.split("#", 1)[0]
        if not bare:
            continue
        if (resolve(bare, md_path, repo_root) is None
                and not ignored_by_git(bare, md_path, repo_root)):
            yield f"link target does not exist: {bare}"


def find_duplicate_keys(pairs, collisions):
    """Record all duplicate keys and return the last value for each key."""
    seen = {}
    for key, value in pairs:
        if key in seen:
            collisions.append(key)
        seen[key] = value
    return seen


def find_key_line(text: str, key: str, occurrence: int) -> int:
    """Return the 1-based line of the Nth key occurrence, or 1 if absent."""
    pattern = re.compile(rf'"{re.escape(key)}"\s*:')
    hits = 0
    for line_number, line in enumerate(text.splitlines(), 1):
        for _ in pattern.finditer(line):
            hits += 1
            if hits == occurrence:
                return line_number
    return 1


def in_frozen_measured_data(path: Path, repo_root: Path) -> bool:
    try:
        parts = path.resolve().relative_to(repo_root.resolve()).parts
    except ValueError:
        return False
    return bool(parts) and parts[0] in FROZEN_MEASURED_DATA_DIRECTORIES


def lint_markdown(path: Path, repo_root: Path):
    if in_frozen_measured_data(path, repo_root):
        return
    in_code_fence = False
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence:
            continue
        if any(marker in line for marker in HISTORY_MARKERS + FOREIGN_ROOT_MARKERS):
            checks = (check_dates(line),)
        else:
            checks = (
                check_dates(line),
                check_backtick_paths(line, path, repo_root),
                check_markdown_links(line, path, repo_root),
                check_code_numbers(line, path, repo_root),
            )
        for check in checks:
            for problem in check:
                yield line_number, problem


def lint_json(path: Path):
    text = path.read_text(encoding="utf-8")
    collisions = []
    try:
        json.loads(text, object_pairs_hook=lambda pairs: find_duplicate_keys(pairs, collisions))
    except ValueError as error:
        yield 1, str(error)
        return
    for key in collisions:
        # The second occurrence silently wins, so report that line.
        yield find_key_line(text, key, 2), f"duplicate key: {key!r}"


def main(argv=None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if not arguments:
        print(__doc__, file=sys.stderr)
        return 2

    findings = 0
    for name in arguments:
        path = Path(name)
        if not path.is_file():
            print(f"{name}:0: file not found", file=sys.stdout)
            findings += 1
            continue
        # Check here too: JSON linting has no repository root with which to enforce frozen-data exclusions.
        if in_frozen_measured_data(path, REPO_ROOT):
            continue
        if path.suffix == ".json":
            problems = lint_json(path)
        else:
            problems = lint_markdown(path, REPO_ROOT)
        for line_number, problem in problems:
            print(f"{name}:{line_number}: {problem}")
            findings += 1

    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
