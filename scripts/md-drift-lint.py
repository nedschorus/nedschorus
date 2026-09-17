#!/usr/bin/env python3
"""Mechanical drift checks for MD (and JSON) files — the lint half of the sanity-check.

Grid-seat ruling (user-walked 2026-08-12, recorded in
docs/drafts/sanity-checker-prompt-draft.md): the worry band that needs no
judgment leaves the reviewer prompt for this script. It reports and never
edits. Zero model cost, so unlike the judgment review it may run repeatedly.

Checks, per file type:

  .md   - repo paths named in backticks or markdown links exist on disk
          (a path this repository deliberately does not track is skipped)
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

# A line pointing outside this repository names files this repo cannot vouch
# for (added 2026-08-14). The legacy tree is read-only reference material and
# is absent from some hosts entirely, so `git-clean-slate-plan.md` on a line
# that also names ~/Projects/nedlern is a correct citation, not drift.
FOREIGN_ROOT_MARKERS = ("~/Projects/nedlern", "nedlern/docs", "legacy system")

# Directories whose content is frozen measured data: every citation in them
# records what a document said when it was measured, so a finding there is
# never a defect and "fixing" one silently re-tunes every score already
# published against those files. cold-read-reviewer-test-cases/README.md makes
# this a requirement and names this script: "every mechanical reference or
# drift check must exclude this directory rather than report it". It is also
# carried as a requirement on nedschorus#42. Nine findings stood here when the
# README was written and nine stand today (user-ruled 2026-09-17).
FROZEN_MEASURED_DATA_DIRECTORIES = ("cold-read-reviewer-test-cases",)


# A line quoting text it says was deleted or replaced describes a former
# state; the quote's absence from today's source is the point, not drift.
QUOTE_SKIP_MARKERS = HISTORY_MARKERS + ("deleted", "removed", "retired", "was cut")

# Punctuation that closes the quoting sentence rides inside the quote marks
# without being part of the source text.
QUOTE_EDGE_PUNCTUATION = "?.!,;:"

_basename_index_cache = {}
_git_ignore_cache = {}
_git_ignore_warned = set()


def repo_relative_candidates(token: str, md_path: Path, repo_root: Path):
    """The repo-relative paths a token could name, whether or not they exist.

    Mirrors resolve()'s two candidates. Built with normpath rather than
    Path.resolve because the whole point is a path that is NOT on disk:
    resolve() of a missing file under a missing directory is unreliable, and
    a link target like `../wiki/page.md` has to be folded against the citing
    document's directory before git can be asked about it.
    """
    token = token.lstrip("/") or token
    for base in (repo_root, md_path.parent):
        candidate = os.path.normpath(os.path.join(str(base), token))
        try:
            relative = os.path.relpath(candidate, str(repo_root))
        except ValueError:  # different drive on Windows
            continue
        if not relative.startswith(".."):
            yield relative


def ignored_by_git(token: str, md_path: Path, repo_root: Path) -> bool:
    """True when this repository deliberately does not track what the token names.

    A path under a record store (`cold-read-records/`, `sanity-check-records/`,
    `md-review-records/`), under the walk minutes (`docs/walk/`,
    `walk-ledgers/`), under the issue mirror (`ghi-mirror/`), or a seat's own
    `CLAUDE.local.md`, is a correct citation of a real file that lives in the
    log-store on ned-box or in the seat that wrote it. It can never exist in a
    clean checkout, so the lint reported it forever and no edit could satisfy
    it -- while "fixing" one would delete accurate provenance. Ten of the
    standing findings on main `bb6df3f` were exactly this (user-ruled
    2026-09-17).

    Asking git, rather than listing those directories here, also makes the
    lint answer the same in a clean checkout and in a seat's own, where such a
    file IS present: present-and-ignored resolves, absent-and-ignored is
    skipped, and neither is reported. Running the lint in the wrong checkout
    is what put a wrong pair of numbers into a merged comment on 2026-09-17.
    """
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
    # Outside a git repository nothing is ignored. That is the answer, not a
    # degraded fallback, so it is silent: this script's own test fixtures are
    # plain temporary directories, and warning there would print on every run.
    # (A worktree's .git is a file, not a directory, so .exists() is the test.)
    if not (repo_root / ".git").exists():
        return False
    # core.excludesFile is neutralized so the answer comes from the
    # repository's own .gitignore. The fleet runs this lint on the Mac and on
    # ned-box, and a machine's global ignore file would otherwise make the two
    # report different findings for the same commit.
    command = ["git", "-c", "core.excludesFile=/dev/null",
               "check-ignore", "--quiet", "--", relative]
    try:
        completed = subprocess.run(command, cwd=str(repo_root), capture_output=True)
    except OSError as error:
        _warn_once(repo_root, f"git could not be run ({error})")
        return False
    # 0 ignored, 1 not ignored; anything else is git failing to answer, and a
    # fallback is never silent (project ruling).
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


def looks_like_repo_path(token: str) -> bool:
    if any(marker in token for marker in SKIP_MARKERS):
        return False
    if ":" in token:  # git show REF:path, URLs, drive letters
        return False
    # A bare ".ext" is a file TYPE, not a file: prose naming `.meta.json` or
    # `.gitignore` means the kind of file, and demanding one exist at the repo
    # root is noise (added 2026-08-14).
    if token.startswith(".") and "/" not in token:
        return False
    # A leading "/" is repo-root-relative when its first component names
    # something at the repo root, and a filesystem path otherwise (added
    # 2026-08-14). `/scripts/x.py` is this repo and is checked — including
    # when it is missing, which is real drift. `/usr/local/lib/...` is a
    # deploy location describing where something WILL live, correctly absent
    # from every development host, and is not this repo's business.
    if token.startswith("/"):
        first = token.lstrip("/").split("/", 1)[0]
        if not (REPO_ROOT / first).exists():
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
    """Return the existing Path a token names (or a truthy marker), or None.

    A leading "/" is read as repo-root-relative, never filesystem-absolute
    (fixed 2026-08-14). Treating it as filesystem-absolute produced standing
    false positives on correct content: the design's intended install path
    `/usr/local/lib/nedschorus-gatekeeper/main-gatekeeper.py` is deliberately
    absent from this machine, and `/CLAUDE.md` means the repo's own file. A
    linter that always complains about the central design document is one
    every reader learns to skim past.
    """
    token = token.lstrip("/") or token
    candidates = [repo_root / token, md_path.parent / token]
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
            # A name with no directory is not a claim about where the file
            # sits: prose writes `notes.md` or `state-exit.json` for a file
            # inside some directory it is discussing, or one a run creates.
            # Measured on main 2026-09-17, in a clean checkout: 138 of the 212
            # missing-path findings were such names, and the noise is what
            # would teach a reviewer to skim past this lint. Measure this in a
            # clean worktree: a first figure of 126 of 200 came from a seat's
            # own checkout, where gitignored files let bare names resolve that
            # a clean one cannot. User-ruled 2026-09-17, the
            # first of the three choices nedschorus#336 named: not checked at
            # all. A path carrying a directory is checked as before, and that
            # is where real drift shows. This is the existence check only —
            # looks_like_repo_path still admits a bare name for
            # referenced_files, whose job is finding the source a quote is
            # attributed to.
            if "/" not in word:
                continue
            if (looks_like_repo_path(word)
                    and resolve(word, md_path, repo_root) is None
                    and not ignored_by_git(word, md_path, repo_root)):
                yield f"path does not exist: {word}"
        # Flag check: a command whose FIRST word is a project script must name
        # only flags that script's source contains.
        #
        # Anchored at the first word (fixed 2026-08-14). Scanning the whole
        # token for any resolvable .py bound every flag in the line to that
        # script no matter which program owned it: `git log --follow --oneline
        # scripts/md-drift-lint.py` reported --follow and --oneline missing
        # from md-drift-lint.py. These documents are full of git commands
        # naming script paths, so the class was one sentence from firing.
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
                # Whole-flag match (fixed 2026-08-14): a plain substring test
                # let a prefix of a real flag pass, so a doc that drifted from
                # --dry-run to --dry reported nothing — exactly the drift this
                # check exists to catch.
                if not re.search(rf"{re.escape(flag)}(?![a-z0-9-])", source):
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
        if (resolve(bare, md_path, repo_root) is None
                and not ignored_by_git(bare, md_path, repo_root)):
            yield f"link target does not exist: {bare}"


def find_duplicate_keys(pairs, collisions):
    """Collect every duplicate key rather than raising on the first.

    Raising stopped at the first collision, so a file with three duplicated
    keys took three edit-and-rerun cycles to clear (fixed 2026-08-14).
    """
    seen = {}
    for key, value in pairs:
        if key in seen:
            collisions.append(key)
        seen[key] = value
    return seen


def find_key_line(text: str, key: str, occurrence: int) -> int:
    """The line of the Nth occurrence of a JSON key, 1-based; 1 if not found.

    The docstring promises `path:line: problem` and every duplicate used to
    report line 1, which was actively wrong (fixed 2026-08-14).
    """
    pattern = re.compile(rf'"{re.escape(key)}"\s*:')
    hits = 0
    for line_number, line in enumerate(text.splitlines(), 1):
        for _ in pattern.finditer(line):
            hits += 1
            if hits == occurrence:
                return line_number
    return 1


def in_frozen_measured_data(path: Path, repo_root: Path) -> bool:
    """True for a file under a directory whose citations are frozen data."""
    try:
        parts = path.resolve().relative_to(repo_root.resolve()).parts
    except ValueError:  # a file outside the repository is not frozen data
        return False
    return bool(parts) and parts[0] in FROZEN_MEASURED_DATA_DIRECTORIES


def lint_markdown(path: Path, repo_root: Path):
    # Skipped whole, not per check, and skipped even when the file is named
    # explicitly on the command line: the requirement is that no drift check
    # reports this directory, however the file was reached.
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
                check_quoted_text(line, path, repo_root),
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
    except ValueError as error:  # malformed JSON: report it and stop
        yield 1, str(error)
        return
    for key in collisions:
        # The second occurrence is the one that silently wins, so that is the
        # line a reader needs to see.
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
        # Guarded here as well as in lint_markdown, and for the same reason
        # in both: whatever the file type. lint_json has no repo_root to test
        # against, and the frozen directory holds only Markdown today, so this
        # is the check that would still hold if a .json landed there.
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
