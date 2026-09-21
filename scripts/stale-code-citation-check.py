#!/usr/bin/env python3
"""stale-code-citation-check — a design document's line-number citations still
point at the code they name.

Two modes, because the drift is found from either end:

  DOCUMENT. Named Markdown documents are checked one at a time. For each
  line-number citation into a code file, git is asked whether that file
  changed after the document's `design-as-of` stamp. If it did, the number
  is unverified and is reported.

  CHANGED PATHS. No document is named, so the code paths this change touches
  are read from the diff and every `design-as-of` document in the tree is
  swept for line-number citations into them. This is the direction that
  fires at the moment the author has the diff in hand.

Usage:
  scripts/stale-code-citation-check.py [--base <ref>] [FILE ...]

  --base    what to diff against in CHANGED PATHS mode; default origin/main.
  FILE ...  Markdown documents to check, which selects DOCUMENT mode. A file
            with no `design-as-of` stamp has nothing to check and is noted on
            stderr.

Output: one "path:line: problem" per finding on stdout, then one summary line
on stderr.
Exit codes: 0 clean, 1 findings, 2 bad invocation.

WHY (user-ruled at item 6 of walk md-skills-seat-open-decisions-2026-09-20).
The detector is a program with a test. The CORRECTING stays prose and is
deliberately not built: a program that tried to judge whether a sentence
still describes the code would pass wrong documents, block right ones, and be
ignored. That limit was stated to the user and accepted. So this program
judges nothing but whether git moved the code out from under a number.

THE CASE IT WAS BUILT FROM. docs/issues/413-cold-read-grid-cell-failure-
handling-design.md carried `design-as-of: 2026-09-17` and described code that
landed on 2026-09-18 in pull request [cold-read-grid: a failed cell is
retried once and reported with its cause, and every run closes with one
closing text](https://github.com/nedschorus/nedschorus/pull/508), merged as
02f4ede. Nobody edited the document; scripts/cold-read-grid.py moved
underneath it. By 2026-09-20 seven of its line-number citations named files
that had changed since its stamp, and six of the seven pointed at code that
was no longer there. The seventh, scripts/cold-read-codex-cell.py lines
108-111, still held the TIER_TO_CODEX_MODEL_CHAIN block it named: that file
changed after the stamp, but those four lines did not move. That is the limit
of what this program knows, and why its finding says the cited file changed
and asks for the number to be read rather than asserting the code is gone.
The document was reconciled by hand in pull request [The 413 cell-failure
design's citations match the code that landed](
https://github.com/nedschorus/nedschorus/pull/559), merged as b6fe18d.

That is why the key is THE CITED FILE'S HISTORY SINCE THE STAMP and not the
document's own modification time (the user's point 1). A rule hung on "when
we update the body we update the frontmatter" could never have fired here.

WHAT COUNTS AS A LINE-NUMBER CITATION. Two shapes, both anchored to the same
Markdown line as the file they cite:

  A backtick span naming a path with a line suffix, `scripts/x.py:120`, the
  shape scripts/md-drift-lint.py already strips in without_line_suffix.

  A `line N` or `lines N-M` phrase, attached to the NEAREST backticked code
  path earlier on the same line. Same-line and nearest-preceding, both
  measured on the 413 document: widening it to "the one code file the line
  names", the rule scripts/md-drift-lint.py's own number check uses, bound
  `lines 166-213` -- which names STUB_MODEL_RUNTIME in
  scripts/cold-read-grid-test.py -- to scripts/cold-read-fast-read-test.py,
  the only code file that line happened to name. A wrong file in a finding
  is worse than no finding. The cost of the narrow rule is that a phrase
  with no file on its own line is not attributable and is not checked; in
  the 413 document that lost `line 375` and `lines 591-643`, and widening to
  the paragraph would have bound `line 375` to scripts/cold-read-cell-
  common.py from the bullet above it, which is the wrong file again.

A number is only ever checked against a CODE file (md-drift-lint's
CODE_SOURCE_EXTENSIONS). The name of this program says code, and a line
number quoted into prose or data is a different claim.

PINNED CITATIONS ARE NOT CHECKED. A heading-section that names a commit this
repository holds and says "line numbers" is measuring that commit, and a
commit is immutable, so nothing in it can drift. The behaviour this defends
against is the merged reconciliation above: it kept section 1's numbers and
added "Facts from origin/main at ad9bfca ... Line numbers are that commit's,
and none of them holds today", and without this rule the check reports four
findings, forever, on the document its author just fixed by hand. Measured on
main at 3eb3a59: 4 findings without the rule, 0 with it. The count suppressed
is printed on stderr every run, so the exemption is never silent.

MEASURED, NOT ASSUMED. On main at 3eb3a59, nine Markdown files carry a
frontmatter `design-as-of` stamp; four others mention the token while citing
another document's stamp, and stamp nothing themselves. Against those nine:

  51 findings if EVERY code path a stamped document cites is checked rather
     than only the line-numbered ones. Scripts change weekly and the stamps
     are weeks old, so a check at that width would fail every pull request on
     prose its author never wrote -- the same shape as the 62 dangling
     citations measured for scripts/dangling-path-citation-check.py. This is
     the measurement that narrows the check to line numbers.
   4 findings from line-number citations alone, every one of them inside the
     pinned section of the 413 document.
   0 after the pin rule.

And on the tree immediately before the hand fix, b6fe18d^1, where the defect
this was built for was still standing: 7 from line-number citations alone,
4 of them inside that document's pinned section, 3 reported.

THE STAMP-OLDER-THAN-THE-BODY CHECK IS NOT HERE, and the reason is measured.
The user named it (his point 3) as "a stamp older than the body's own last
edit". On the nine documents it fires 9 out of 9, whether the last edit is
read as any commit touching the file or only as one that changed the body
below the frontmatter: every one of them has been edited since its stamp.
Narrowed to a post-stamp edit that touched a line citing code, 5 of 9.
Narrowed hardest, to a post-stamp edit that touched a line-number citation,
1 of 9 -- and the two commits that made it fire were a
terminology sweep (agent-cli became agent-binary) and a citation-form sweep
(issues cited by title, not bare number). Neither changed what the document
claims about the code. The mechanism cannot tell a sweep from a re-authored
claim, so at every width it reports documents whose designs are current.

THE STATUS CHECK RIDES ON THE FIRST CHECK, and cannot stand alone. The user
named it (also his point 3) as a `status:` claiming "design" when the code it
describes has landed. `status:` is free text and the nine values in use are
nine distinct sentences -- "design, not built", "specification", "design of
record", "overview of the tool as built", "landed design; built in pull
requests ...", "SUPERSEDED at walk item 1" and so on -- so no vocabulary test
applies. Worse, "the code has landed" has no mechanical signal of its own: a
design's cited paths exist both when its code landed and when the paths
pre-dated it, and are absent both when nothing was built and when the
citation is a forward reference to a program the project has decided to build
and has not. The one piece of evidence available is the git history the first
check already reads. So the status finding is raised only for a document that
already has a stale-citation finding and whose `status:` does not claim the
code is built -- the exact shape of the 413 fault, which read
"status: design; its cold-read-full-run of 2026-09-16 is triaged" while the
code had been in main for two days. It adds no findings of its own on main.

A STATUS CLAIMS THE CODE IS BUILT when "landed" or "built" appears in it as a
WHOLE WORD with no negating word in the two words before it. Both halves are
measured on the nine values in use, not on invented strings. A substring test,
which is what this check first shipped with, read "design, not built" as built
-- the clearest unbuilt claim a status can make, a value in use, and a value
quoted two paragraphs up -- so the rider was silent on the very shape it
exists to catch, and on "not yet built" and "specification (partially built --
see Implementation status)" with it. The whole-word half is what keeps "build
tracked in issue ..." from reading as "built". The negators are not, never,
nor, no, un and partially; "un" is in the list for a hyphenated "un-built",
since "unbuilt" is one word and so is already not the word "built".

The verdicts on the nine values on main at 3eb3a59. Built: "overview of the
tool as built; six changes ruled ...", "landed design; built in pull requests
508 ... and 521 ..." and "landed design; build tracked in issue [Build
ghi-info ...]" (on "landed", since "build" is not "built"). Not built:
"design, not built", "specification (partially built -- see Implementation
status)", "design of record; build tracked in issue [Fleet survives ...]",
"specification", "SUPERSEDED at walk item 1" and "draft for the user's walk".
Only the first two of those six change verdict against the substring test; the
other seven values are read as the substring test read them. The cost of the
whole-word half is that a status saying "rebuilt" would read as unbuilt too;
none of the nine says it, and one that did would be asked for one clause.

"partially built" reading as NOT built is the one judgement in this rule
rather than a measurement, and the one to ratify or overrule: part of the code
landing does not answer whether the code a stale number cites landed. It
changes nothing on main today: both documents whose verdict it moves --
docs/design-to-main/design-to-main-state-machine-design.md, which says
"design, not built", and nc-systems/main-gatekeeper/main-gatekeeper-design.md,
which says "partially built" -- carry no line-number citation at all, so
neither reaches the status check. The hole this closes is in the rider's
purpose, not in today's tree.

REUSE. scripts/md-drift-lint.py is imported by path, the way
scripts/walk-files-ship.py imports scripts/cold-read-record-ship.py, and its
citation reading is called rather than repeated, so its rulings hold here: a
backticked name with no directory is not checked (user-ruled 2026-09-17), a
leading "/" is repo-root-relative, a path the repository deliberately does
not track is skipped, a line naming git history or a foreign repository root
is skipped, a code fence is skipped, and a file under
FROZEN_MEASURED_DATA_DIRECTORIES is skipped whole. The one shape added here
is the `lines N-M` phrase, which the lint has no reason to read: its own
number check asks whether a BACKTICKED number appears anywhere in a cited
file's source, which a stale line number passes whenever some other line of
that file happens to hold the same digits. If a second caller ever wants the
phrase, it belongs in the lint rather than in a third extractor.

ITS SIBLING. scripts/dangling-path-citation-check.py asks whether a cited
path is there at all; this asks whether a number into a path that IS there
still means what it said. Neither subsumes the other and they share no
finding.

SAME-DAY IS NOT STALE. The stamp is a date and git's committer date is
compared as a date, so a code change on the stamp's own day does not fire.
A design stamped the day its code moved is the normal case for a document
written alongside the change, and reporting it would fire on every design
landing with its own code.
"""
import argparse
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

# A date, and nothing looser: the stamp is compared as a date and a stamp that
# is not one cannot be compared at all.
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# "line 375", "lines 428-432", "lines 428 - 432". An en dash because the
# project's prose uses one.
LINE_NUMBER_PHRASE = re.compile(r"\blines?\s+(\d+)(?:\s*[-–]\s*(\d+))?\b")

# A candidate abbreviated object name. Whether it is a commit is git's answer,
# not this pattern's.
COMMIT_ISH_TOKEN = re.compile(r"\b[0-9a-f]{7,40}\b")

# The phrase a section must carry, beside a commit this repository holds, for
# its numbers to count as pinned to that commit. See PINNED CITATIONS in the
# docstring.
PINNED_SECTION_PHRASE = "line numbers"

# A status value claims the code is built when it names one of these as a
# whole word with no negating word just before it. See A STATUS CLAIMS THE
# CODE IS BUILT in the docstring for why each half of that is there.
STATUS_WORDS_MEANING_BUILT = ("landed", "built")
STATUS_BUILT_WORD = re.compile(
    r"\b(?:" + "|".join(STATUS_WORDS_MEANING_BUILT) + r")\b")

# A word that takes a built word back: "design, not built", "not yet built",
# "specification (partially built ...)". Read from the words just before the
# built word, not from the whole value, so "not a design; built in pull
# request 508" still claims built.
STATUS_WORDS_NEGATING_BUILT = ("not", "never", "nor", "no", "un", "partially")
STATUS_NEGATOR_LOOKBACK_WORDS = 2

# A word of a status value, for that lookback. The value is lowercased first,
# so a-z is every letter there is to match.
STATUS_WORD = re.compile(r"[a-z]+")

_commit_ish_cache = {}
_last_change_cache = {}


def load_md_drift_lint():
    """The drift lint as a module, imported by path the way
    scripts/walk-files-ship.py imports scripts/cold-read-record-ship.py: its
    file name is not an identifier, and its citation reading is this
    program's."""
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
    """(line number, line) for each line of the leading frontmatter block.

    Only a block opened by the file's first line counts. A "---" later in the
    body is a horizontal rule, and reading a field out of one would take a
    stamp from prose.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONTMATTER_FENCE:
        return
    for number, line in enumerate(lines[1:], 2):
        if line.strip() == FRONTMATTER_FENCE:
            return
        yield number, line


def frontmatter_field(text: str, field: str):
    """(line number, value) of a frontmatter field, or None."""
    for number, line in frontmatter_lines(text):
        if line.startswith(field):
            return number, line[len(field):].strip()
    return None


def code_file_marks(line: str, document: pathlib.Path,
                    repository_root: pathlib.Path, lint) -> list:
    """[(column, path, token as written)] per backticked code file on this line.

    The lint's own admission rules decide what is a path; a name with no
    directory is not one (user-ruled 2026-09-17), which is why the "/" test
    is here and not a looser one.
    """
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
    """(document line, cited file, first, last, text as written) per citation.

    A code fence, a line naming git history and a line naming a foreign
    repository root are skipped, as the lint skips them.
    """
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
                continue  # not attributable to a file; see the docstring
            first = int(match.group(1))
            last = int(match.group(2)) if match.group(2) else first
            yield number, earlier[-1], first, last, match.group(0)


def heading_sections(text: str):
    """(first line, last line, section text) per Markdown heading block.

    The text before the first heading is a section too: a document's terms
    and preamble carry citations, and the 413 document's `landed` definition
    was one of them.
    """
    lines = text.splitlines()
    starts = []
    inside_code_fence = False
    for index, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            inside_code_fence = not inside_code_fence
            continue
        # A "#" inside a fence is a shell comment, not a heading. Reading one
        # as a heading would end a section early and carry a pinned section's
        # citations out of the pin.
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
    """[(first line, last line)] of each section whose numbers are pinned."""
    pinned = []
    for first, last, section in heading_sections(text):
        if PINNED_SECTION_PHRASE not in section.lower():
            continue
        if names_a_commit(section, repository_root):
            pinned.append((first, last))
    return pinned


def last_change_date(relative: str, repository_root: pathlib.Path) -> str:
    """The date of the newest commit touching this path, or "" if git has none.

    An empty answer means the path is untracked, and an untracked file has no
    history to have moved: the lint skips such a path and so does this.
    """
    key = (str(repository_root), relative)
    if key not in _last_change_cache:
        _last_change_cache[key] = git_output(
            ["log", "-1", "--format=%cs", "--", relative], repository_root).strip()
    return _last_change_cache[key]


def stamped_documents(repository_root: pathlib.Path, lint) -> list:
    """Every tracked Markdown file carrying a frontmatter design-as-of stamp."""
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
    """Whether git can name a commit for --base.

    Asked before the diff because git_output returns "" for a command that
    failed, and an unresolvable base would otherwise read as a change that
    touches no code and pass every document silently. A fallback is never
    silent (project ruling).
    """
    completed = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", base + "^{commit}"],
        cwd=str(repository_root), capture_output=True, text=True, check=False)
    return completed.returncode == 0


def changed_code_paths(base: str, repository_root: pathlib.Path, lint) -> list:
    """The code paths this change touches, committed and not yet committed.

    Three dots against the base, so a base that has moved on since the branch
    was cut does not put its own commits into this change's diff.
    """
    names = set()
    for arguments in (["diff", "--name-only", f"{base}...HEAD"],
                      ["diff", "--name-only", "HEAD"],
                      ["ls-files", "--others", "--exclude-standard"]):
        names.update(git_output(arguments, repository_root).split())
    return sorted(name for name in names
                  if pathlib.PurePath(name).suffix in lint.CODE_SOURCE_EXTENSIONS)


def status_means_built(status: str) -> bool:
    """Whether a `status:` value claims the code this document describes is built.

    A whole-word "landed" or "built" with no negating word in the two words
    before it. A substring test read "design, not built" as built, so the
    status finding was silent on the clearest unbuilt claim a status can make;
    see A STATUS CLAIMS THE CODE IS BUILT in the docstring for the rule and
    for its verdict on each of the nine values in use.
    """
    lowered = status.lower()
    for match in STATUS_BUILT_WORD.finditer(lowered):
        before = STATUS_WORD.findall(lowered[:match.start()])
        if any(word in STATUS_WORDS_NEGATING_BUILT
               for word in before[-STATUS_NEGATOR_LOOKBACK_WORDS:]):
            continue
        return True
    return False


def findings_for_document(document: pathlib.Path, repository_root: pathlib.Path,
                          lint, wanted_paths=None, moved_on=None):
    """(line number, problem) per finding, and the count of pinned citations.

    wanted_paths limits the cited files considered, which is CHANGED PATHS
    mode. moved_on, when given, is the date the change lands and replaces
    git's history as the answer to "when did this file move": the change is
    not committed yet, so its own date is the only one there is.
    """
    text = document.read_text(encoding="utf-8")
    stamp_field = frontmatter_field(text, DESIGN_AS_OF_FIELD)
    if stamp_field is None:
        return [], 0
    stamp_line, stamp = stamp_field
    if not ISO_DATE.match(stamp):
        # Raised in DOCUMENT mode only. In CHANGED PATHS mode the sweep reads
        # every stamped document in the tree, and a broken stamp in one the
        # change never touched is not that change's finding -- reporting it
        # would fail a pull request on prose its author never wrote, which is
        # the failure scripts/dangling-path-citation-check.py measured at 62
        # dangling citations on main.
        if wanted_paths is not None:
            return [], 0
        return [(stamp_line,
                 f"{DESIGN_AS_OF_NAME} is {stamp!r}, which is not a date: "
                 f"write it as YYYY-MM-DD, so a cited file's history can be "
                 f"compared against it")], 0

    pinned = pinned_line_ranges(text, repository_root)
    findings = []
    pinned_count = 0
    for number, found, first, last, written in line_number_citations(
            document, repository_root, lint):
        try:
            relative = str(found.resolve().relative_to(repository_root.resolve()))
        except ValueError:
            continue  # outside this repository; its history is not ours to read
        if wanted_paths is not None and relative not in wanted_paths:
            continue
        changed = moved_on if moved_on is not None else last_change_date(
            relative, repository_root)
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

    if findings:
        status_field = frontmatter_field(text, STATUS_FIELD)
        if status_field is not None:
            status_line, status = status_field
            if not status_means_built(status):
                findings.append((
                    status_line,
                    f"{STATUS_NAME} does not claim the code landed or was "
                    f"built, and code this document cites by line number "
                    f"moved after {DESIGN_AS_OF_NAME} {stamp}: say in "
                    f"{STATUS_NAME} whether the code has landed"))
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
        # The date of the change's newest commit, not git's history of each
        # path: the change is what moved the code, and asking history instead
        # would answer for the base rather than for this change. Reading it
        # from the commit rather than from the clock also makes a replay of an
        # old change report what it reported then.
        change_date = git_output(["log", "-1", "--format=%cs"],
                                 REPOSITORY_ROOT).strip()
        wanted = set(changed)
        for document in stamped_documents(REPOSITORY_ROOT, lint) if changed else []:
            relative = document.relative_to(REPOSITORY_ROOT)
            problems, pinned = findings_for_document(
                document, REPOSITORY_ROOT, lint, wanted_paths=wanted,
                moved_on=change_date)
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
