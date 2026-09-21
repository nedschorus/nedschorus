#!/usr/bin/env python3
"""dangling-path-citation-check — this change leaves no citation pointing at
a path that is not there.

Two directions, because a citation and the file it names break apart from
either end:

  FORWARD. A line this change adds or alters cites a repository path that
  does not exist in this change's own tree. The author wrote the citation.

  BACKWARD. This change removes a path -- deletes it, or renames it away --
  and something in the tree still cites the old one. The author moved the
  file and the citing line never changed, so no check on changed lines can
  see it. This is the direction that matters most, and the one the defect
  below actually was.

Usage:
  scripts/dangling-path-citation-check.py [--base <ref>] [FILE ...]

  --base    what to diff against; default origin/main.
  FILE ...  limit the FORWARD check to these paths; default every file the
            diff names. The backward check always reads the whole tree,
            because what cites a removed path is exactly what the author did
            not think to look at.

Output: one "path:line: problem" per finding on stdout, then one summary
line on stderr.
Exit codes: 0 clean, 1 findings, 2 bad invocation.

WHY (user-ruled 2026-09-20, walk
open-questions-concerns-and-recommendations-2026-09-19 item 3). On
2026-09-19 the main-gatekeeper moved whole into nc-systems/main-gatekeeper/
and its author swept every citation of the four old paths across 33 files.
Two survived: a comment in scripts/launch-claude-mac and another in
scripts/launch-claude-ubuntu, each naming the gate's write_atomically as the
precedent it follows. They survived because that sweep selected files by
extension and those two files have none. A fresh reviewer found them by
reading, which is the expensive way. Nothing executed them, but a reader
following either citation found no file there until a second pull request
landed.

That pull request did not touch those two files, and this is the point:
their citing lines never changed, so a check scoped to changed lines cannot
see them. Measured 2026-09-20: `git show --stat` on that merge names 35
files and neither launcher is among them. The backward check is the one that
catches it, by asking what still cites each path the change removed.

WHY THE DIFF AND NOT THE WHOLE TREE. Main carries dangling citations that
are nobody's defect: 62 on 2026-09-20, several of them forward references
to work the project has decided to do and has not done, such as
quality/runs.jsonl from the toolchain plan, absent from main on 2026-09-21.
A check over whole files would fail every pull request on prose its author
never touched. So a finding is reported only when its line is one the change
added or altered, the rule scripts/md-drift-lint.py's caller applies by hand
today.

WHY THE CHANGE'S OWN TREE AND NOT MAIN. A change that adds a file and cites
it in the same commit is correct. Existence is therefore tested in the
working tree, which for a checked-out topic branch is that branch's content.

WHAT COUNTS AS A CITATION. Two shapes, because the defect above was in
neither of the shapes a markdown linter reads:

  In a Markdown file, the citation shapes scripts/md-drift-lint.py already
  reads: a backtick span and a markdown link. This program calls that
  module's own checks rather than repeating them, so its rulings hold here
  too -- a backticked name with no directory is not checked at all
  (user-ruled 2026-09-17), a leading "/" is repo-root-relative, a path the
  repository deliberately does not track is skipped, and a file under
  FROZEN_MEASURED_DATA_DIRECTORIES is skipped whole.

  In any other text file, including one with no extension, a bare token
  that begins with a directory at the repository root -- `scripts/`,
  `docs/`, `nc-systems/`, `.claude/` and their siblings, read from the tree
  rather than listed here -- and ends in a known file extension. That is
  the narrowest shape that catches the defect above: the missed line read
  "# scripts/main-gatekeeper.py (ruled 2026-08-12), and this follows it
  with two". A token without a leading directory is not a citation, by the
  same reasoning as the 2026-09-17 ruling: it is usually relative to
  something the sentence is discussing.

AND THE SAME SHAPES IN BOTH DIRECTIONS, since 2026-09-21. The forward
question is "which paths does this line name", asked of a token and nothing
else, so it needs the two filters above to decide whether a token is a path
at all. The two questions asked of text rather than of the diff -- what
still cites a path this change removed, and what the file's own version at
the merge base already cited -- hold the path already, and are answered by
repository_paths_a_line_cites, which resolves what a line names instead of
matching a string. They were not, and the difference was a defect twice
over: a relative markdown link is a citation the forward direction reports
and the backward one could not see, and a path named only inside a code
fence -- which the lint never reads -- was enough raw base text to suppress
a genuinely new citation of it. Both measured 2026-09-21, each at a genuine
R100 rename or on two files given a byte-identical new citation.

  WHAT THIS DIRECTION READS THAT THE FORWARD ONE DOES NOT, and why it is not
  an inconsistency: a backticked path inside a non-Markdown file, and a path
  with no file extension at all. Neither can be admitted forward -- the
  first would report every fixture literal in a docstring, the second every
  word with a slash in it -- and both are plain citations of a file that has
  moved. Ten backticked ones are live in this repository's non-Markdown
  files, and three of the launchers this program was written about have no
  extension.

WHAT "AGAINST THE BASE" MEANS. The merge base of --base and HEAD, resolved
once and used for all three reads: the changed-line diff, the removed-path
diff and the base text a forward finding is compared against. The two diffs
were already three-dot and the text read was the base TIP, so on a branch
behind main the suppression below consulted a file version the branch never
saw, and the author's own new dangling citation went unreported.

AND AT WHICH NAME. A RENAMED file's own version stands at the merge base
under the name the change renamed it from, not under the name it now has.
Asked for under its HEAD name, git returned nothing, the suppression below
answered "the base did not cite this" about every path in the file, and a
rename plus an edit to any line resurrected that line's standing dangling
citations as findings against the author. Latent in the very move this
program was built from, the 2026-09-19 gatekeeper move being a rename and an
edit. So the old name is read from the rename rows of the removed-path diff,
which already carry it, and the base text is read there.

  THE LIMIT, stated rather than guarded: git decides what a rename is by
  similarity, and a move that also rewrites most of the file is a delete and
  an add, carrying no old name for this to read. Such a file's standing
  citations are still reported. Where that threshold falls is git's own
  business: measured 2026-09-21, one five-line document moved with a word
  changed in its citing line scored a delete and an add, and the same
  document with a dozen unrelated paragraphs in it scored 91% and a rename.

THE FIXTURE-CARRYING FILES ARE THE TESTS, by the project's own definition
of a test and not by a list. A test whose subject is paths names paths that
are deliberately absent, and against a base where the test did not exist
yet every one of those lines is new: this program's own test carried
seventeen such literals and reported every one of them. The FORWARD
direction skips a file the Test row of
docs/nedschorus-wiki/nedschorus-file-naming-and-location-standards.md calls
a test -- the stem plus "-test" before the extension, or any file in the
"tests" subdirectory a subsystem with its own directory puts its tests in.
Both halves earn their place. Measured with this program's own
plain_path_citations over origin/main on 2026-09-21: 162 absent-path tokens
in 23 non-Markdown files with no exemption at all, 15 in 9 files once
"-test.py" is exempt, and 14 in 8 once the "tests" directory is too. The one
file the second half adds is design-to-main's own test fixture, whose name
ends in neither "-test.py" nor anything else the first half reads. (The
reviewing seat measured the same three rows as 172/27, 18/13 and 17/12; the
rows here filter the two things this program filters, a gitignored path and
the frozen measured data, and were taken at a different main.)

  THE RESIDUAL IS THE COST, stated rather than guarded. Those 14 stand,
  half of them scripts/md-drift-lint.py's own documented examples, and they
  are reported only if a change touches the line they sit on. A list of
  names would have to grow every time a test was written; this does not.

  THIS FILE IS NOT A TEST and is no longer exempt, which the main-checkout
  measurement above could not see because this file is not on main yet.
  Measured on this branch 2026-09-21: two lines of this docstring quote the
  founding defect's own evidence, a path the 2026-09-19 move emptied, and
  the program reports them on its own pull request. They are quotations and
  not drift; correcting them would destroy the example.

  FORWARD ONLY, and that asymmetry is principled rather than an omission.
  The forward direction is where a test's fixture literals live, and they
  are the author's payload, not the author's mistake. The backward
  direction is where a test's citation of the module it tests lives, and
  when that module moves the citation is stale like any other -- it is the
  case a test file is MOST likely to carry and least likely to have swept,
  since nothing runs the test's prose. So a test is never exempt backward,
  and a case pins it. Do not simplify the two into one exemption.

  THE COST OF THE FORWARD HALF: a genuine forward-dangling citation newly
  written into a test is skipped too, and a path misspelled in this
  docstring's neighbours is not reported.

WHAT IT DOES NOT DO. It never edits, and it judges nothing but existence.
A link's text, a citation's revision pinning and an issue's title are the
wider work of nedschorus#42 and are deliberately absent.

AND IT IS CORRECT ONLY ON A CLEAN TREE. The changed lines come from
`git diff <merge base>..HEAD`, which reads committed content, while the
citation text and the existence test read the working tree. With uncommitted
edits the two disagree: a line number the diff gives can name different text
in the file, and a path added but not yet committed exists for the existence
test and not for the diff. Stated rather than guarded, because every caller
today runs it on a committed head, and a guard that refused a dirty tree
would refuse the author mid-edit, which is when a check like this is most
useful to run by hand.
"""
import argparse
import importlib.util
import pathlib
import re
import subprocess
import sys

PROGRAM = "dangling-path-citation-check"
SCRIPTS_DIRECTORY = pathlib.Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPTS_DIRECTORY.parent

EXIT_FINDINGS = 1
EXIT_BAD_INVOCATION = 2

# A diff hunk header: @@ -old,count +new,count @@. The new-file side is what
# this program wants, because a finding is anchored to the line as it now
# stands. A count is absent when it is 1.
HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")

# What separates one word from the next when a line is read for the paths it
# SPELLS. The backtick is here and absent from PLAIN_PATH_TOKEN_SEPARATOR
# below, because those are two different questions: this one is asked of a
# path already in hand, and a backticked `<dir>/gate.py` in a shell script or
# a docstring names it. Ten such citations are live in this repository's
# non-Markdown files, measured 2026-09-21. The illustrations here are written
# with a placeholder directory on purpose: a real path in this file's prose is
# a citation the BACKWARD direction resolves, and this file is exempt only
# forward.
#
# NEITHER SEPARATOR BREAKS ON A PLACEHOLDER'S OWN BRACKETS, and that is the
# whole reason carries_a_marker_the_lint_skips can work: a separator that
# split <dir>/gate.py would leave /gate.py behind, and the marker test would
# have nothing left to see.
NAMED_PATH_TOKEN_SEPARATOR = re.compile(r"[\s'\"()\[\]`]+")
PLAIN_PATH_TOKEN_SEPARATOR = re.compile(r"[\s'\"()\[\]]+")

# What the project calls a test, from the Test row of
# docs/nedschorus-wiki/nedschorus-file-naming-and-location-standards.md: the
# stem plus "-test" before the extension, and a subsystem with its own
# directory puts its tests in a "tests" subdirectory of it. See "THE
# FIXTURE-CARRYING FILES" above for why the FORWARD direction skips them and
# what that costs.
PROJECT_TEST_FILE_NAME_ENDING = "-test.py"
PROJECT_TEST_DIRECTORY_NAME = "tests"


def fail_bad_invocation(detail: str):
    """Stop with EXIT_BAD_INVOCATION, which is not the findings code.

    SystemExit carrying a string prints it and exits 1 -- the code that means
    findings -- so every caller that distinguished a failed run from a dirty
    one was reading a lie. The docstring above promised 2 from the day it was
    written; this is what makes the promise true.
    """
    print(f"{PROGRAM}: {detail}", file=sys.stderr)
    raise SystemExit(EXIT_BAD_INVOCATION)


def carries_a_marker_the_lint_skips(token: str, lint) -> bool:
    """True when the drift lint's own SKIP_MARKERS say this token is not a
    path: a placeholder in angle brackets or braces, a glob, a shell
    variable, a home-relative path, an ellipsis, a URL.

    A TOKEN THAT CARRIED A PLACEHOLDER IS NOT A CITATION, in either
    direction. Asked of the whole token and not of what survives splitting
    it, because the collapse happens first and the resolution after:
    <dir>/gate.py reduced to /gate.py, and /gate.py folded against the citing
    file's own directory lands exactly on <dir>/gate.py when the citing file
    is a SIBLING of the one that moved. Measured 2026-09-21 on the same
    sentence in two places: reported from a sibling, silent from anywhere
    else -- and live in this program's own file, whose placeholder
    illustrations sit beside the scripts they illustrate. The same collapse
    reached the FORWARD direction once a leading "/" was stripped rather than
    dropped, so both ends ask this.

    The lint applies the same list in looks_like_repo_path, which is why its
    Markdown side never had either defect. This is that rule, at the two
    places that do not go through it."""
    return any(marker in token for marker in lint.SKIP_MARKERS)


def citation_tokens_on_line(line: str, citing_path: pathlib.Path, lint):
    """Every token on this line that is spelled as a path, under the citation
    shapes the drift lint reads and the rulings it applies to them.

    A markdown link's target, in a Markdown file: the shape that is a citation
    one way and was invisible the other. `[the target](target.md)` written
    from a sibling directory holds no repository-relative path at all, so
    nothing that searches for one can find it -- while the FORWARD direction,
    through the same lint, already reports "link target does not exist" about
    exactly that text. A URL, a mail address and a bare fragment are not
    repository paths, and a target's "#anchor" is not part of the file name;
    all four are the lint's own rules in check_markdown_links.

    And any word, in a file of any type, that carries a directory separator.
    A name with no separator is not a claim about where a file sits
    (user-ruled 2026-09-17) and is dropped here as the lint drops it, except
    as a link target, where it is relative to the citing document and the
    lint resolves it. A colon still means `git show REF:path` or a URL, once
    a trailing line number is off.

    What this does NOT do is decide whether a token names a file at all: no
    extension test, no test that the first component is a directory of this
    repository. Those belong to the FORWARD question, "which paths does this
    line name", where the token is all there is to go on. The callers here
    ask the other question, "does this line name THIS path", and already hold
    the path; filtering first would only lose spellings -- an extensionless
    launcher among them, which is the very kind of file the founding defect
    was written in.
    """
    if citing_path.suffix == ".md":
        for target in lint.MARKDOWN_LINK.findall(line):
            if "://" in target or target.startswith(("mailto:", "#")):
                continue
            bare = lint.without_line_suffix(target.split("#", 1)[0])
            if bare and ":" not in bare and not carries_a_marker_the_lint_skips(bare, lint):
                yield bare
    for token in NAMED_PATH_TOKEN_SEPARATOR.split(line):
        token = lint.without_line_suffix(token.rstrip(".,;:!?").lstrip("#*-"))
        if not token or ":" in token or "/" not in token:
            continue
        if carries_a_marker_the_lint_skips(token, lint):
            continue
        yield token


def repository_paths_a_line_cites(line: str, citing_path: pathlib.Path, lint,
                                  repository_root: pathlib.Path):
    """The repository-relative paths this line's citations could name.

    THE ONE DEFINITION OF A CITATION for both questions this program asks of
    text rather than of the diff -- what still cites a path this change
    removed, and what the file's own version at the merge base already cited.
    They were two definitions until 2026-09-21: the backward end matched the
    repository-relative path as a literal string, so a relative link naming
    the same file was invisible to it, and the base-text end searched raw
    text, so a path named only inside a code fence -- which the lint never
    reads -- suppressed a genuinely new citation of it.

    Resolution is the lint's own repo_relative_candidates, the same folding
    of a token against the repository root and against the citing document's
    directory that resolve() does, built for paths that are NOT on disk. Both
    candidates are yielded and the caller compares for equality, which is
    also what retired the boundary predicate this function replaced: a move
    that only deepens a path leaves the old one a suffix of the new, and
    <system>/<dir>/gate.py is simply not equal to <dir>/gate.py. The
    placeholder spelling is this file's own practice, stated at
    NAMED_PATH_TOKEN_SEPARATOR: a real path written here is one both
    directions read.
    """
    for token in citation_tokens_on_line(line, citing_path, lint):
        yield from lint.repo_relative_candidates(token, citing_path, repository_root)


# A token in a non-Markdown file is a citation only when it starts with one
# of these and ends in a file extension the drift lint already knows. The
# set is read from the tree, so a new top-level directory needs no edit here.
def repository_root_directories(repository_root: pathlib.Path) -> tuple:
    names = subprocess.run(["git", "ls-tree", "HEAD", "--name-only", "-d"],
                           cwd=repository_root, capture_output=True, text=True, check=False)
    return tuple(sorted(name for name in names.stdout.split() if name))


def load_md_drift_lint():
    """The drift lint as a module, imported by path the way
    scripts/walk-files-ship.py imports scripts/cold-read-record-ship.py: its
    file name is not an identifier, and its checks are this program's."""
    path = SCRIPTS_DIRECTORY / "md-drift-lint.py"
    specification = importlib.util.spec_from_file_location("md_drift_lint", path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def merge_base_with_head(base: str, repository_root: pathlib.Path) -> str:
    """The commit --base and HEAD share, resolved once for all three reads.

    Read here rather than left to `base...HEAD` in each diff, because the
    third read is `git show`, which has no three-dot spelling and was reading
    the base TIP. On a branch behind main that is a file version the branch
    never saw."""
    found = subprocess.run(["git", "merge-base", base, "HEAD"],
                           cwd=repository_root, capture_output=True, text=True, check=False)
    if found.returncode != 0 or not found.stdout.strip():
        fail_bad_invocation(f"no merge base between {base} and HEAD: "
                            f"{found.stderr.strip() or found.returncode}")
    return found.stdout.strip()


def changed_lines_by_file(merge_base: str, repository_root: pathlib.Path) -> dict:
    """{path relative to the root: set of line numbers the diff adds or
    alters}. A deleted file has no lines and does not appear. --unified=0 so
    a hunk covers only what changed, not three lines of neighbours whose
    citations are not this change's business."""
    diff = subprocess.run(
        ["git", "diff", "--unified=0", "--no-color", "--no-ext-diff", f"{merge_base}..HEAD"],
        cwd=repository_root, capture_output=True, text=True, check=False)
    if diff.returncode != 0:
        fail_bad_invocation(f"git diff against {merge_base} failed: "
                            f"{diff.stderr.strip() or diff.returncode}")
    changed: dict = {}
    current = None
    # A "+++ " line is a file header only in the preamble a "diff --git" line
    # opens. An ADDED line whose own text begins "++ " renders as "+++ " and
    # is otherwise indistinguishable: it set `current` to a path that does not
    # exist, and every later hunk of the real file went there instead, unread.
    # The preamble is the anchor rather than the "--- " line above, because a
    # REMOVED line beginning "-- " -- a SQL or Lua comment -- renders as
    # "--- " and has the mirror defect. A content line always carries its own
    # one-character prefix, so "diff --git" at column zero is unambiguous.
    in_file_preamble = False
    for line in diff.stdout.splitlines():
        if line.startswith("diff --git "):
            in_file_preamble = True
            current = None
            continue
        if in_file_preamble and line.startswith("+++ "):
            target = line[4:].strip()
            current = None if target == "/dev/null" else target[2:] if target.startswith("b/") else target
            in_file_preamble = False
            continue
        match = HUNK_HEADER.match(line)
        if match:
            in_file_preamble = False
            if current:
                start = int(match.group(1))
                count = int(match.group(2)) if match.group(2) is not None else 1
                changed.setdefault(current, set()).update(range(start, start + count))
    return changed


def plain_path_citations(line: str, root_directories: tuple, lint):
    """The repo-root-relative paths a non-Markdown line names, unbackticked.
    Punctuation a sentence puts after a path is stripped, so
    "# scripts/main-gatekeeper.py (ruled 2026-08-12)," yields the path.

    A trailing line number is stripped before the colon test, the drift
    lint's own rule and its own function. Rejecting the whole token for its
    colon dropped every line-numbered citation in a non-Markdown file --
    including the shape this program prints its own findings in. What the
    colon test is there for, `git show REF:path` and a URL, still has a colon
    once the line number is off and is still dropped.

    A leading "/" or "./" is part of the spelling and not of the path, and is
    taken off before the first component is read. token.split("/", 1)[0]
    yielded "" for the one and "." for the other, neither a directory of this
    repository, so both were dropped -- and that is how every hook command in
    .claude/settings.json is written, "$CLAUDE_PROJECT_DIR"/scripts/<name>.py,
    and how a launcher runs a program from the repository root. The FORWARD
    direction was blind to the project's own live callers. The drift lint's
    2026-08-14 ruling is that a leading "/" is repo-root-relative and IS
    checked; what that ruling holds back, a deploy location such as
    /usr/local/lib/<name>.py, is held back here by its own first component
    not being a directory of this repository.

    That strip is also what made a placeholder dangerous here. This split
    used to break on a placeholder's own brackets, so <dir>/gate.py fell
    apart and the /gate.py left behind was dropped for having no directory
    at its head -- silence by accident. Strip the slash and the same
    fragment becomes gate.py, and <system>/<dir>/gate.py becomes a citation
    of <dir>/gate.py that nobody wrote -- a sentence that could not be
    written here without the fix it describes. The brackets are no
    longer separators and carries_a_marker_the_lint_skips refuses the whole
    token, which is the drift lint's own rule for its Markdown side."""
    for token in PLAIN_PATH_TOKEN_SEPARATOR.split(line):
        token = lint.without_line_suffix(token.rstrip(".,;:!?").lstrip("#*-"))
        if not token or ":" in token:
            continue
        if carries_a_marker_the_lint_skips(token, lint):
            continue
        token = token[2:] if token.startswith("./") else token.lstrip("/")
        head = token.split("/", 1)[0]
        if head not in root_directories:
            continue
        if not token.endswith(lint.PATH_EXTENSIONS):
            continue
        yield token


def file_at_merge_base(relative: str, merge_base: str, repository_root: pathlib.Path) -> str:
    """The file's text at the merge base, or "" when it was not there."""
    shown = subprocess.run(["git", "show", f"{merge_base}:{relative}"],
                           cwd=repository_root, capture_output=True, text=True, check=False)
    return shown.stdout if shown.returncode == 0 else ""


def cited_path_of(problem: str) -> str:
    """The path a forward finding names, for comparison with the base."""
    return problem.rsplit(": ", 1)[-1].strip()


def paths_the_base_text_cites(base_text: str, base_name: str, lint,
                              repository_root: pathlib.Path) -> set:
    """Every repository-relative path the file's version at the merge base
    cites, read the way the FORWARD direction read the version at HEAD.

    Read as raw text until 2026-09-21, which is not the same question. The
    lint never reads a line inside a code fence, so a forward finding can
    never come from one -- but the raw base text holds fenced lines like any
    other, and a path a base named only inside a ```sh fence silently
    dropped a genuinely new citation of it written in prose. Measured
    2026-09-21 on two files given a byte-identical new citation: the one
    whose base fenced the path was not reported and the other was.

    So a Markdown base is walked the way lint_markdown walks a Markdown file:
    fenced lines skipped, and a line carrying one of the lint's history or
    foreign-root markers skipped, because a forward finding cannot come from
    one of those either. A base of any other type is read line by line with
    no marker rule, which is what findings_for_file does with such a file at
    HEAD. The suppression compares like with like at each type."""
    citing_path = repository_root / base_name
    walk_as_markdown = citing_path.suffix == ".md"
    skipped_markers = lint.HISTORY_MARKERS + lint.FOREIGN_ROOT_MARKERS
    cited = set()
    in_code_fence = False
    for line in base_text.splitlines():
        if walk_as_markdown:
            if line.lstrip().startswith("```"):
                in_code_fence = not in_code_fence
                continue
            if in_code_fence or any(marker in line for marker in skipped_markers):
                continue
        cited.update(repository_paths_a_line_cites(line, citing_path, lint, repository_root))
    return cited


def base_already_cites(cited: str, base_cited_paths: set, citing_path: pathlib.Path,
                       lint, repository_root: pathlib.Path) -> bool:
    """True when the file's own version at the merge base already cited this
    path -- so this change did not introduce the citation.

    Both sides are resolved to repository-relative paths and compared for
    equality. Asked as containment until 2026-09-21: a base holding
    <dir>/page.md.bak answered yes to a citation of <dir>/page.md, and the
    author's new dangling citation was dropped. A line number is not part of
    the path, so it comes off before the comparison."""
    candidates = set(lint.repo_relative_candidates(
        lint.without_line_suffix(cited), citing_path, repository_root))
    return bool(candidates & base_cited_paths)


def is_project_test_file(path: pathlib.Path, repository_root: pathlib.Path) -> bool:
    """True for a file the project's own Test row calls a test: a name ending
    in "-test.py", or any file in a "tests" directory.

    FORWARD only: the one caller is findings_for_file. Adding it to
    citations_of_removed_paths would hide a test's stale citation of a path
    that moved, and a case pins that."""
    try:
        relative = path.resolve().relative_to(repository_root.resolve())
    except ValueError:  # a file outside the repository is not one of these
        return False
    return (relative.name.endswith(PROJECT_TEST_FILE_NAME_ENDING)
            or PROJECT_TEST_DIRECTORY_NAME in relative.parts[:-1])


def findings_for_file(path: pathlib.Path, changed: set, lint, root_directories: tuple):
    """(line number, problem) for each finding on a changed line of `path`."""
    relative = path.relative_to(REPOSITORY_ROOT)
    if lint.in_frozen_measured_data(path, REPOSITORY_ROOT):
        return
    # Forward only, and never from citations_of_removed_paths; the cost of
    # this line is stated in this module's docstring.
    if is_project_test_file(path, REPOSITORY_ROOT):
        return
    if path.suffix == ".md":
        # The drift lint's own walk, so its code-fence tracking, its marker
        # exemptions and its rulings apply; only its path checks are kept,
        # because a date or a flag is not this program's business.
        for line_number, problem in lint.lint_markdown(path, REPOSITORY_ROOT):
            if line_number in changed and ("does not exist" in problem):
                yield line_number, problem
        return
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return  # a binary or unreadable file cites nothing
    for line_number, line in enumerate(text.splitlines(), 1):
        if line_number not in changed:
            continue
        for token in plain_path_citations(line, root_directories, lint):
            if lint.ignored_by_git(token, path, REPOSITORY_ROOT):
                continue
            if not (REPOSITORY_ROOT / token).exists():
                yield line_number, f"path does not exist: {token}"


def name_status_rows_against_merge_base(merge_base: str, repository_root: pathlib.Path) -> list:
    """The rows of `git diff --name-status` against the merge base, each split
    into its tab-separated fields, and dropped when it carries no path.

    Read once, because two questions are asked of the same output: which paths
    this change removed, and which of the files it now has stood under another
    name at the merge base. A rename row carries both names, and is the only
    place the second question is answered."""
    names = subprocess.run(
        ["git", "diff", "--name-status", "--no-color", "--no-ext-diff", f"{merge_base}..HEAD"],
        cwd=repository_root, capture_output=True, text=True, check=False)
    if names.returncode != 0:
        fail_bad_invocation(f"git diff --name-status against {merge_base} failed: "
                            f"{names.stderr.strip() or names.returncode}")
    return [fields for fields in (row.split("\t") for row in names.stdout.splitlines())
            if len(fields) >= 2]


def paths_this_change_removed(name_status_rows: list, repository_root: pathlib.Path) -> list:
    """The repository paths that existed at the merge base and do not exist
    now: a deletion, or a rename's old name. Read from --name-status rather
    than from the tree, so a file moved and a file deleted are one case."""
    removed = []
    for fields in name_status_rows:
        status, old = fields[0], fields[1]
        if status.startswith("D") or status.startswith("R"):
            if not (repository_root / old).exists():
                removed.append(old)
    return removed


def merge_base_names_of_renamed_files(name_status_rows: list) -> dict:
    """{a path as this change leaves it: the name it stood under at the merge
    base}, for every file this change renamed.

    Only a rename row carries an old name. A move git scores below its
    similarity threshold is a delete and an add rather than a rename, carries
    no old name, and is absent here; so is a file this change merely edited,
    whose two names are the same one."""
    return {fields[2]: fields[1] for fields in name_status_rows
            if len(fields) >= 3 and fields[0].startswith("R")}


def files_that_might_name_a_removed_path(removed: list, repository_root: pathlib.Path) -> set:
    """The tracked files whose text holds the BASE NAME of a path this change
    removed, which is the widest net a search can cast for the files worth
    reading in full.

    Searched by base name and not by the repository-relative path, because a
    relative link to a sibling document holds only the base name -- and a
    file holding the whole path holds the base name too, so nothing the
    narrower search reached is lost. This is a filter and not the test: what
    a candidate file actually cites is decided by reading it.

    git grep -F, fixed strings: a name is not a pattern, and one holding a
    regex character would otherwise match somewhere else or nowhere. -I
    leaves binary files out, as they cite nothing."""
    candidates = set()
    for gone in removed:
        base_name = gone.rsplit("/", 1)[-1]
        if not base_name:
            continue
        hits = subprocess.run(
            ["git", "grep", "-l", "-I", "--no-color", "-F", base_name, "--", "."],
            cwd=repository_root, capture_output=True, text=True, check=False)
        candidates.update(row for row in hits.stdout.splitlines() if row)
    return candidates


def citations_of_removed_paths(removed: list, repository_root: pathlib.Path, lint) -> list:
    """(citing file, line number, problem) for every tracked file that still
    cites a path this change removed.

    Each candidate file is read and its citations resolved, rather than its
    lines matched against the removed path as a literal string. The literal
    match could only ever see a citation that spells the whole path out, so a
    markdown link to a moved sibling was invisible to this direction while
    the FORWARD direction, in the same program and through the same lint,
    reported the very same text as a broken link."""
    wanted = set(removed)
    findings = []
    for citing in sorted(files_that_might_name_a_removed_path(removed, repository_root)):
        citing_path = repository_root / citing
        # The frozen measured data records what documents said when they were
        # measured; a path inside it is history, not a citation.
        if lint.in_frozen_measured_data(citing_path, repository_root):
            continue
        try:
            text = citing_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue  # a binary or unreadable file cites nothing
        for number, line in enumerate(text.splitlines(), 1):
            # A line saying a file lives in git history names something
            # deliberately absent from the tree, so a move does not make it
            # stale. The drift lint's own exemption, by its own list, applied
            # here to every file type because this direction reads every file
            # type. Fenced content is NOT exempted: a usage example running a
            # script by path does need sweeping when the script moves, and
            # what marks the noise is the history marker, not the fence.
            if any(marker in line for marker in lint.HISTORY_MARKERS):
                continue
            cited = set(repository_paths_a_line_cites(
                line, citing_path, lint, repository_root))
            for gone in sorted(cited & wanted):
                findings.append((citing, number,
                                 f"cites {gone}, which this change removed"))
    return findings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog=f"scripts/{PROGRAM}.py",
        description="Every repository path cited on a line this change touches exists.")
    parser.add_argument("--base", default="origin/main",
                        help="what to diff against (default: origin/main)")
    parser.add_argument("files", nargs="*", metavar="FILE",
                        help="limit the check to these paths (default: the diff's)")
    arguments = parser.parse_args(argv)

    lint = load_md_drift_lint()
    root_directories = repository_root_directories(REPOSITORY_ROOT)
    merge_base = merge_base_with_head(arguments.base, REPOSITORY_ROOT)
    changed = changed_lines_by_file(merge_base, REPOSITORY_ROOT)
    if arguments.files:
        wanted = {str(pathlib.Path(name)) for name in arguments.files}
        changed = {name: lines for name, lines in changed.items() if name in wanted}

    findings = []
    name_status_rows = name_status_rows_against_merge_base(merge_base, REPOSITORY_ROOT)
    removed = paths_this_change_removed(name_status_rows, REPOSITORY_ROOT)
    merge_base_name_of_renamed_file = merge_base_names_of_renamed_files(name_status_rows)
    for citing, line_number, problem in citations_of_removed_paths(
            removed, REPOSITORY_ROOT, lint):
        findings.append(f"{citing}:{line_number}: {problem}")
    for name in sorted(changed):
        path = REPOSITORY_ROOT / name
        if not path.is_file():
            continue  # renamed away or deleted between the diff and now
        base_cited_paths = None
        for line_number, problem in findings_for_file(path, changed[name], lint, root_directories):
            # A citation this change did not introduce is not this change's
            # finding, even on a line it touched. Measured on the gatekeeper
            # move of 2026-09-19: its sweep rewrote one path on a line that
            # also carried an unrelated forward reference to a test the
            # project has not built, and reporting that would have been a
            # false alarm for its author. This is the comparison the caller
            # of scripts/md-drift-lint.py makes by hand. A renamed file's own
            # version stands at the merge base under the name it was renamed
            # FROM; asking for it under its HEAD name got nothing back and
            # resurrected every standing citation in it. See "AND AT WHICH
            # NAME" above, which states what this does not cover.
            if base_cited_paths is None:
                base_name = merge_base_name_of_renamed_file.get(name, name)
                base_cited_paths = paths_the_base_text_cites(
                    file_at_merge_base(base_name, merge_base, REPOSITORY_ROOT),
                    base_name, lint, REPOSITORY_ROOT)
            if base_already_cites(cited_path_of(problem), base_cited_paths,
                                  path, lint, REPOSITORY_ROOT):
                continue
            findings.append(f"{name}:{line_number}: {problem}")
    for finding in findings:
        print(finding)
    print(f"{PROGRAM}: {len(findings)} finding(s) — the lines "
          f"{len(changed)} changed file(s) touch, and what still cites the "
          f"{len(removed)} path(s) this change removed, against {arguments.base}.",
          file=sys.stderr)
    return EXIT_FINDINGS if findings else 0


if __name__ == "__main__":
    sys.exit(main())
