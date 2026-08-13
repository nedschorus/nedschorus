#!/usr/bin/env python3
"""Mechanical drift checks for MD (and JSON) files — the lint half of the sanity-check.

Grid-seat ruling (user-walked 2026-08-12, recorded in
docs/drafts/sanity-checker-prompt-draft.md): the worry band that needs no
judgment leaves the reviewer prompt for this script. It reports and never
edits. Zero model cost, so unlike the judgment review it may run repeatedly.

Checks, per file type:

  .md   - repo paths named in backticks or markdown links exist on disk
        - markdown link targets resolve (external schemes skipped)
        - YYYY-MM-DD tokens are real calendar dates
        - a backtick command naming an existing project script also names
          only flags that appear in that script's source
  .json - no duplicate keys at any nesting depth (a duplicate key is legal
          JSON that parsers resolve silently: the second value wins and an
          edit to the first does nothing)

Usage:
  scripts/md-drift-lint.py FILE [FILE ...]

Output: one "path:line: problem" per finding on stdout.
Exit codes: 0 clean, 1 findings, 2 bad invocation.
"""

import calendar
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PATH_EXTENSIONS = (".py", ".md", ".json", ".sh", ".toml", ".yml", ".yaml", ".txt", ".jsonl")

BACKTICK_TOKEN = re.compile(r"`([^`\n]+)`")
MARKDOWN_LINK = re.compile(r"\[[^\]\n]*\]\(([^)\s]+)\)")
DATE_TOKEN = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
FLAG_TOKEN = re.compile(r"--[a-z][a-z0-9-]+")

# Tokens that look like paths but are not checkable file references.
SKIP_MARKERS = ("://", "<", "{", "*", "$", "~", "…")

# A line saying a file lives in git history references something deliberately
# absent from the working tree; its paths are not drift.
HISTORY_MARKERS = ("git history", "git show")

_basename_index_cache = {}


def looks_like_repo_path(token: str) -> bool:
    if any(marker in token for marker in SKIP_MARKERS):
        return False
    if ":" in token:  # git show REF:path, URLs, drive letters
        return False
    return token.endswith(PATH_EXTENSIONS) and not token.startswith("-")


def basename_index(repo_root: Path) -> set:
    """All file basenames under the root, for resolving bare-name references."""
    if repo_root not in _basename_index_cache:
        _basename_index_cache[repo_root] = {
            item.name for item in repo_root.rglob("*")
            if item.is_file() and ".git" not in item.parts
        }
    return _basename_index_cache[repo_root]


def resolve(token: str, md_path: Path, repo_root: Path):
    """Return the existing Path a token names (or a truthy marker), or None."""
    candidates = [repo_root / token, md_path.parent / token]
    if token.startswith("/"):
        candidates = [Path(token)]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    # A bare basename (no directory) may name a file anywhere in the repo —
    # documents legitimately say "handoff-supervisor.py" without its path.
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
        # A command line: first word may be a script, later words flags.
        words = token.split()
        for word in words:
            if looks_like_repo_path(word) and resolve(word, md_path, repo_root) is None:
                yield f"path does not exist: {word}"
        # Flag check: a token naming an existing project script must name
        # only flags that script's source contains.
        script = next(
            (resolve(word, md_path, repo_root) for word in words
             if word.endswith(".py") and resolve(word, md_path, repo_root)),
            None,
        )
        if script is not None:
            try:
                source = script.read_text(encoding="utf-8")
            except OSError:
                continue
            for flag in FLAG_TOKEN.findall(token):
                if flag not in source:
                    yield f"flag {flag} not found in {script.name}"


def check_markdown_links(line: str, md_path: Path, repo_root: Path):
    for match in MARKDOWN_LINK.finditer(line):
        target = match.group(1)
        if "://" in target or target.startswith(("mailto:", "#")):
            continue
        bare = target.split("#", 1)[0]
        if not bare:
            continue
        if resolve(bare, md_path, repo_root) is None:
            yield f"link target does not exist: {bare}"


def find_duplicate_keys(pairs):
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError(f"duplicate key: {key!r}")
        seen[key] = value
    return seen


def lint_markdown(path: Path, repo_root: Path):
    in_code_fence = False
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence:
            continue
        if any(marker in line for marker in HISTORY_MARKERS):
            checks = (check_dates(line),)
        else:
            checks = (
                check_dates(line),
                check_backtick_paths(line, path, repo_root),
                check_markdown_links(line, path, repo_root),
            )
        for check in checks:
            for problem in check:
                yield line_number, problem


def lint_json(path: Path):
    try:
        json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=find_duplicate_keys)
    except ValueError as error:
        yield 1, str(error)


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
