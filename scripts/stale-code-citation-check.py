#!/usr/bin/env python3
"""Report line-number citations whose code files changed after a document's design-as-of date."""
# File history can show drift risk, not whether the cited code actually moved or the prose remains correct.
import argparse
import datetime
import importlib.util
import pathlib
import re
import subprocess
import sys

PROGRAM = "stale-code-citation-check"
SCRIPTS_DIRECTORY = pathlib.Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPTS_DIRECTORY.parent

EXIT_FINDINGS = 1
EXIT_BAD_INVOCATION = 2

DESIGN_AS_OF_NAME = "design-as-of"
STATUS_NAME = "status"
DESIGN_AS_OF_FIELD = DESIGN_AS_OF_NAME + ":"
STATUS_FIELD = STATUS_NAME + ":"
FRONTMATTER_FENCE = "---"

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# The project's prose uses en dashes as well as hyphens for line ranges.
LINE_NUMBER_PHRASE = re.compile(r"\blines?\s+(\d+)(?:\s*[-–]\s*(\d+))?\b")

# A hexadecimal shape alone does not prove the object is a commit; git must resolve it.
COMMIT_ISH_TOKEN = re.compile(r"\b[0-9a-f]{7,40}\b")

PINNED_SECTION_PHRASE = "line numbers"

STATUS_WORDS_MEANING_BUILT = ("landed", "built")
STATUS_BUILT_WORD = re.compile(
    r"\b(?:" + "|".join(STATUS_WORDS_MEANING_BUILT) + r")\b")

# Negation is local to the built word: a preceding clause may negate a different claim.
STATUS_WORDS_NEGATING_BUILT = ("not", "never", "nor", "no", "un", "partially")
STATUS_NEGATOR_LOOKBACK_WORDS = 2

STATUS_WORD = re.compile(r"[a-z]+")

LANDING_PIN_PREFIX = "**Pinned to what landed:** commit ["

LANDING_PIN_COMMIT = re.compile(re.escape(LANDING_PIN_PREFIX) + r"([0-9a-f]{7,40})\]")

_commit_ish_cache = {}
_last_change_cache = {}


def load_md_drift_lint():
    path = SCRIPTS_DIRECTORY / "md-drift-lint.py"
    specification = importlib.util.spec_from_file_location("md_drift_lint", path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def git_output(arguments, repository_root: pathlib.Path) -> str:
    completed = subprocess.run(["git", *arguments], cwd=str(repository_root),
                               capture_output=True, text=True, check=False)
    return completed.stdout


def frontmatter_lines(text: str):
    """Yield (line_number, line) from the leading frontmatter block."""
    # A later --- is a horizontal rule and must not turn body prose into a frontmatter stamp.
    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONTMATTER_FENCE:
        return
    for number, line in enumerate(lines[1:], 2):
        if line.strip() == FRONTMATTER_FENCE:
            return
        yield number, line


def frontmatter_field(text: str, field: str):
    """Return (line_number, value) for a frontmatter field, or None."""
    for number, line in frontmatter_lines(text):
        if line.startswith(field):
            return number, line[len(field):].strip()
    return None


def stamp_is_a_calendar_date(stamp: str) -> bool:
    # Check both shape and calendar validity: impossible dates defeat lexical comparison, and ISO week dates are incompatible.
    if not ISO_DATE.match(stamp):
        return False
    try:
        datetime.date.fromisoformat(stamp)
    except ValueError:
        return False
    return True


def code_file_marks(line: str, document: pathlib.Path,
                    repository_root: pathlib.Path, lint) -> list:
    """Return (column, path, written_token) for each backticked code file on a line."""
    marks = []
    for match in lint.BACKTICK_TOKEN.finditer(line):
        for word in match.group(1).strip().split():
            if not lint.looks_like_repo_path(word):
                continue
            bare = lint.without_line_suffix(word)
            if "/" not in bare:
                continue
            found = lint.resolve(bare, document, repository_root)
            if found is None or not found.is_file():
                continue
            if found.suffix not in lint.CODE_SOURCE_EXTENSIONS:
                continue
            marks.append((match.start(), found, word))
    return marks


def line_number_citations(document: pathlib.Path, repository_root: pathlib.Path, lint):
    """Yield (document_line, cited_file, first, last, written_text) for each citation."""
    # Attach line-number phrases only to the nearest preceding path on the same line to avoid attributing unrelated prose.
    inside_code_fence = False
    for number, line in enumerate(document.read_text(encoding="utf-8").splitlines(), 1):
        if line.lstrip().startswith("```"):
            inside_code_fence = not inside_code_fence
            continue
        if inside_code_fence:
            continue
        if any(marker in line
               for marker in lint.HISTORY_MARKERS + lint.FOREIGN_ROOT_MARKERS):
            continue
        marks = code_file_marks(line, document, repository_root, lint)
        for column, found, word in marks:
            suffixed = lint.LINE_SUFFIXED_PATH.match(word)
            if suffixed:
                cited = int(suffixed.group("line"))
                yield number, found, cited, cited, word
        for match in LINE_NUMBER_PHRASE.finditer(line):
            earlier = [found for column, found, word in marks if column < match.start()]
            if not earlier:
                continue
            first = int(match.group(1))
            last = int(match.group(2)) if match.group(2) else first
            yield number, earlier[-1], first, last, match.group(0)


def heading_sections(text: str):
    """Yield (first_line, last_line, text) per heading block, including the preamble."""
    lines = text.splitlines()
    starts = []
    inside_code_fence = False
    for index, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            inside_code_fence = not inside_code_fence
            continue
        # A # inside a fence is not a heading; splitting there would remove citations from their pinned section.
        if not inside_code_fence and line.startswith("#"):
            starts.append(index)
    if not starts or starts[0] != 0:
        starts.insert(0, 0)
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        yield start + 1, end, "\n".join(lines[start:end])


def names_a_commit(text: str, repository_root: pathlib.Path) -> bool:
    for token in set(COMMIT_ISH_TOKEN.findall(text)):
        key = (str(repository_root), token)
        if key not in _commit_ish_cache:
            completed = subprocess.run(
                ["git", "rev-parse", "--verify", "--quiet", token + "^{commit}"],
                cwd=str(repository_root), capture_output=True, text=True, check=False)
            _commit_ish_cache[key] = completed.returncode == 0
        if _commit_ish_cache[key]:
            return True
    return False


def pinned_line_ranges(text: str, repository_root: pathlib.Path) -> list:
    """Return the line ranges of sections whose numbers are pinned to a commit."""
    # A citation pinned to an existing commit cannot drift because commits are immutable.
    pinned = []
    for first, last, section in heading_sections(text):
        if PINNED_SECTION_PHRASE not in section.lower():
            continue
        if names_a_commit(section, repository_root):
            pinned.append((first, last))
    return pinned


def last_change_date(relative: str, repository_root: pathlib.Path) -> str:
    """Return the newest commit date touching the path, or an empty string without history."""
    key = (str(repository_root), relative)
    if key not in _last_change_cache:
        _last_change_cache[key] = git_output(
            ["log", "-1", "--format=%cs", "--", relative], repository_root).strip()
    return _last_change_cache[key]


def stamped_documents(repository_root: pathlib.Path, lint) -> list:
    names = git_output(["ls-files", "-z", "--", "*.md"], repository_root).split("\0")
    found = []
    for name in names:
        if not name:
            continue
        path = repository_root / name
        if not path.is_file() or lint.in_frozen_measured_data(path, repository_root):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if frontmatter_field(text, DESIGN_AS_OF_FIELD) is not None:
            found.append(path)
    return found


def base_resolves(base: str, repository_root: pathlib.Path) -> bool:
    # git_output returns an empty string on failure; an invalid base would otherwise look like a clean diff.
    completed = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", base + "^{commit}"],
        cwd=str(repository_root), capture_output=True, text=True, check=False)
    return completed.returncode == 0


def newest_commit_date_in_range(relative: str, base: str,
                                repository_root: pathlib.Path) -> str:
    """Return the newest date touching this path in the change, or an empty string."""
    # Use two dots for commits: three dots includes base-side commits; the diff separately needs the merge base.
    return git_output(["log", "-1", "--format=%cs", f"{base}..HEAD", "--", relative],
                      repository_root).strip()


def changed_code_paths(base: str, repository_root: pathlib.Path, lint) -> dict:
    """Return changed code paths mapped to their individual change dates."""
    # Uncommitted edits need today's date; HEAD's date can hide a newer edit.
    # Committed paths need their own dates so later changes to other files cannot make them appear stale.
    head_commit_date = git_output(["log", "-1", "--format=%cs"],
                                  repository_root).strip()
    today = datetime.date.today().isoformat()
    moved_on_by_path = {}
    for name in git_output(["diff", "--name-only", f"{base}...HEAD"],
                           repository_root).split():
        if pathlib.PurePath(name).suffix in lint.CODE_SOURCE_EXTENSIONS:
            moved_on_by_path[name] = (
                newest_commit_date_in_range(name, base, repository_root)
                or head_commit_date)
    for arguments in (["diff", "--name-only", "HEAD"],
                      ["ls-files", "--others", "--exclude-standard"]):
        for name in git_output(arguments, repository_root).split():
            if pathlib.PurePath(name).suffix in lint.CODE_SOURCE_EXTENSIONS:
                moved_on_by_path[name] = today
    return moved_on_by_path


def status_means_built(status: str) -> bool:
    lowered = status.lower()
    for match in STATUS_BUILT_WORD.finditer(lowered):
        before = STATUS_WORD.findall(lowered[:match.start()])
        if any(word in STATUS_WORDS_NEGATING_BUILT
               for word in before[-STATUS_NEGATOR_LOOKBACK_WORDS:]):
            continue
        return True
    return False


def landing_pin_commits(text: str, repository_root: pathlib.Path) -> list:
    """Return resolvable pinned commit SHAs in document order, as written."""
    # Resolve every SHA: an unfilled template or a nonexistent commit must not suppress findings.
    commits = []
    for line in text.splitlines():
        pinned = LANDING_PIN_COMMIT.match(line.strip())
        if pinned and names_a_commit(pinned.group(1), repository_root):
            commits.append(pinned.group(1))
    return commits


def carries_landing_pin(text: str, repository_root: pathlib.Path) -> bool:
    return bool(landing_pin_commits(text, repository_root))


def repository_relative_name(found: pathlib.Path, repository_root: pathlib.Path):
    """Return the repository-relative cited path, or None for an outside file."""
    try:
        return str(found.resolve().relative_to(repository_root.resolve()))
    except ValueError:
        return None


def findings_for_document(document: pathlib.Path, repository_root: pathlib.Path,
                          lint, wanted_paths=None, moved_on_by_path=None):
    """Return findings as (line_number, problem) pairs and the count of pinned citations."""
    text = document.read_text(encoding="utf-8")
    stamp_field = frontmatter_field(text, DESIGN_AS_OF_FIELD)
    if stamp_field is None:
        return [], 0
    stamp_line, stamp = stamp_field

    # Determine changed-path scope before judging stamps, so unrelated documents cannot fail this change.
    citations = [(number, repository_relative_name(found, repository_root),
                  first, last)
                 for number, found, first, last, _written
                 in line_number_citations(document, repository_root, lint)]
    cites_a_wanted_path = wanted_paths is None or any(
        relative in wanted_paths
        for _number, relative, _first, _last in citations)

    if not stamp_is_a_calendar_date(stamp):
        if not cites_a_wanted_path:
            return [], 0
        return [(stamp_line,
                 f"{DESIGN_AS_OF_NAME} is {stamp!r}, which is not a date: "
                 f"write a day the calendar has, as YYYY-MM-DD, so a cited "
                 f"file's history can be compared against it")], 0

    pinned = pinned_line_ranges(text, repository_root)
    findings = []
    pinned_count = 0
    for number, relative, first, last in citations:
        if relative is None:
            continue
        if wanted_paths is not None and relative not in wanted_paths:
            continue
        changed = (moved_on_by_path[relative] if moved_on_by_path is not None
                   else last_change_date(relative, repository_root))
        if not changed or changed <= stamp:
            continue
        if any(low <= number <= high for low, high in pinned):
            pinned_count += 1
            continue
        where = f"line {first}" if first == last else f"lines {first}-{last}"
        findings.append((
            number,
            f"{relative} changed {changed}, after {DESIGN_AS_OF_NAME} {stamp}: "
            f"read {where} and cite the function or constant by name, or "
            f"restamp the document once the citation is verified"))

    if findings and not carries_landing_pin(text, repository_root):
        status_field = frontmatter_field(text, STATUS_FIELD)
        if status_field is not None:
            status_line, status = status_field
            if not status_means_built(status):
                findings.append((
                    status_line,
                    f"code this document cites by line number moved after "
                    f"{DESIGN_AS_OF_NAME} {stamp}, and neither a pinned line "
                    f"naming a commit this repository holds nor {STATUS_NAME} "
                    f"says the code landed: if it landed, "
                    f"append the pinned line, "
                    f"{LANDING_PIN_PREFIX}<sha>](<commit url>) on "
                    f"<YYYY-MM-DD> — <what landed>."))
    return findings, pinned_count


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog=f"scripts/{PROGRAM}.py",
        description="A design document's line-number citations still point at "
                    "the code they name.")
    parser.add_argument("--base", default="origin/main",
                        help="what to diff against in CHANGED PATHS mode "
                             "(default: origin/main)")
    parser.add_argument("files", nargs="*", metavar="FILE",
                        help="Markdown documents to check (default: sweep every "
                             "design-as-of document against the diff's code paths)")
    arguments = parser.parse_args(argv)

    lint = load_md_drift_lint()
    findings = []
    pinned_total = 0

    if arguments.files:
        mode = "document"
        for name in arguments.files:
            path = pathlib.Path(name)
            if not path.is_file():
                print(f"{name}:0: file not found")
                findings.append(name)
                continue
            if lint.in_frozen_measured_data(path, REPOSITORY_ROOT):
                continue
            text = path.read_text(encoding="utf-8")
            if frontmatter_field(text, DESIGN_AS_OF_FIELD) is None:
                print(f"{PROGRAM}: {name} carries no {DESIGN_AS_OF_NAME} stamp, "
                      f"so no citation in it is dated; not checked",
                      file=sys.stderr)
                continue
            problems, pinned = findings_for_document(path, REPOSITORY_ROOT, lint)
            pinned_total += pinned
            for number, problem in sorted(problems):
                print(f"{name}:{number}: {problem}")
                findings.append(name)
        scope = f"{len(arguments.files)} named document(s)"
    else:
        mode = "changed paths"
        if not base_resolves(arguments.base, REPOSITORY_ROOT):
            print(f"{PROGRAM}: pass --base a ref this repository holds; "
                  f"{arguments.base!r} names no commit. Fetch it, or name "
                  f"origin/main.", file=sys.stderr)
            return EXIT_BAD_INVOCATION
        changed = changed_code_paths(arguments.base, REPOSITORY_ROOT, lint)
        wanted = set(changed)
        for document in stamped_documents(REPOSITORY_ROOT, lint) if changed else []:
            relative = document.relative_to(REPOSITORY_ROOT)
            problems, pinned = findings_for_document(
                document, REPOSITORY_ROOT, lint, wanted_paths=wanted,
                moved_on_by_path=changed)
            pinned_total += pinned
            for number, problem in sorted(problems):
                print(f"{relative}:{number}: {problem}")
                findings.append(str(relative))
        scope = (f"{len(changed)} changed code path(s) against "
                 f"{arguments.base}")

    summary = f"{PROGRAM}: {len(findings)} finding(s) — {mode} mode, {scope}."
    if pinned_total:
        summary += (f" {pinned_total} citation(s) not checked: pinned to a "
                    f"commit by a section that says its line numbers are "
                    f"that commit's.")
    print(summary, file=sys.stderr)
    return EXIT_FINDINGS if findings else 0


if __name__ == "__main__":
    sys.exit(main())
