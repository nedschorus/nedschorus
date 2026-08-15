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
        - a double-quoted span of four or more words, on a line naming
          exactly one existing repo file, appears in that file (whitespace
          and markdown emphasis normalized; an ellipsis splits the quote
          into separately-checked fragments; a quote touching a backtick
          span is skipped)
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
STRAIGHT_QUOTE_SPAN = re.compile(r'"([^"\n]+)"')
CURLY_QUOTE_SPAN = re.compile(r"“([^”\n]+)”")
NUMBER_ONLY = re.compile(r"\d[\d_,]*(?:\.\d+)?")

# Below this size a quoted span is a label or a term, not a quotation.
QUOTE_MINIMUM_WORDS = 4

# Numbers are checked only against code sources; MD-to-MD number claims are
# counts and cardinalities, not values quoted from an implementation.
CODE_SOURCE_EXTENSIONS = (".py", ".sh")

# Tokens that look like paths but are not checkable file references.
SKIP_MARKERS = ("://", "<", "{", "*", "$", "~", "…")

# A line saying a file lives in git history references something deliberately
# absent from the working tree; its paths are not drift.
HISTORY_MARKERS = ("git history", "git show")

# A line quoting text it says was deleted or replaced describes a former
# state; the quote's absence from today's source is the point, not drift.
QUOTE_SKIP_MARKERS = HISTORY_MARKERS + ("deleted", "removed", "retired", "was cut")

# Punctuation that closes the quoting sentence rides inside the quote marks
# without being part of the source text.
QUOTE_EDGE_PUNCTUATION = "?.!,;:"

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


def normalized_for_quote_match(text: str) -> str:
    """Whitespace and markdown emphasis vary freely between a quote and its
    source; both sides are compared with them normalized away."""
    return re.sub(r"\s+", " ", re.sub(r"[*_`]", "", text)).strip()


def canonical_number(token: str) -> str:
    return token.replace("_", "").replace(",", "")


def referenced_files(line: str, md_path: Path, repo_root: Path):
    """The distinct existing files a line names in backticks or links."""
    tokens = []
    for match in BACKTICK_TOKEN.finditer(line):
        tokens.extend(word for word in match.group(1).strip().split()
                      if looks_like_repo_path(word))
    for match in MARKDOWN_LINK.finditer(line):
        target = match.group(1)
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


def check_quoted_text(line: str, md_path: Path, repo_root: Path):
    """A quotation on a line naming exactly one file must appear in that file.

    Attribution is the line itself: one named file plus a quoted span of
    QUOTE_MINIMUM_WORDS or more reads as "this file says this". A line naming
    two files attributes nothing checkable and is skipped, as is a quote that
    touches a backtick span (code, not quotation, and not normalizable).
    """
    lowered = line.lower()
    if any(marker in lowered for marker in QUOTE_SKIP_MARKERS):
        return
    code_spans = [match.span() for match in BACKTICK_TOKEN.finditer(line)]
    quotes = []
    for match in list(STRAIGHT_QUOTE_SPAN.finditer(line)) + list(CURLY_QUOTE_SPAN.finditer(line)):
        start, end = match.span()
        if any(span_start < end and start < span_end
               for span_start, span_end in code_spans):
            continue
        if len(match.group(1).split()) >= QUOTE_MINIMUM_WORDS:
            quotes.append(match.group(1))
    if not quotes:
        return
    sources = referenced_files(line, md_path, repo_root)
    if len(sources) != 1:
        return
    try:
        source_text = normalized_for_quote_match(sources[0].read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return
    for quote in quotes:
        for fragment in re.split(r"\.\.\.|…", quote):
            fragment = fragment.strip().rstrip(QUOTE_EDGE_PUNCTUATION)
            if len(fragment.split()) < 2:
                continue  # an ellipsis stub too short to identify
            if normalized_for_quote_match(fragment) not in source_text:
                yield (f"quoted text not found in {sources[0].name}: "
                       f'"{fragment.strip()[:60]}"')


def check_code_numbers(line: str, md_path: Path, repo_root: Path):
    """A backtick span that is only a number is a value quoted from code; it
    must appear in the one code file the line names. Prose numbers stay
    unchecked — backticks are the opt-in that marks a number as from-code."""
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
                check_quoted_text(line, path, repo_root),
                check_code_numbers(line, path, repo_root),
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
