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

THE FIXTURE-CARRYING FILES. This program and its test are the one pair in
this repository whose subject matter IS dangling paths: every negative case
names a path deliberately absent, and against a base where those files did
not exist yet, every one of those lines is new. It reported twenty findings
on its own pull request. DECLARED_PATH_FIXTURE_FILES names them and the
FORWARD direction skips them whole.

  THE COST, stated rather than guarded: a genuine forward-dangling citation
  newly written into either file is skipped too. A path misspelled in this
  docstring is not reported. The backward direction is not exempted and
  never should be -- when a path these files cite is moved away, they are
  reported like any other file, which is what makes the stale reference in
  a test's own fixtures visible. A case pins that.

WHAT IT DOES NOT DO. It never edits, and it judges nothing but existence.
A link's text, a citation's revision pinning and an issue's title are the
wider work of nedschorus#42 and are deliberately absent.
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

# What may continue a path where one ends. "." is absent deliberately: a
# citation at the end of a sentence reads "<dir>/gate.py." and the stop is not
# part of the path, while "<dir>/gate.py.bak" is a different file. So a
# trailing "." counts as continuation only when a name character follows it;
# see names_path_at_segment_boundary. The illustrations here are written with
# a placeholder directory on purpose: a real path in this file's prose is a
# string the BACKWARD direction can grep, and this file is exempt only
# forward.
PATH_SEGMENT_CHARACTER = re.compile(r"[A-Za-z0-9_/~+-]")

# The files whose subject matter is dangling paths, skipped by the FORWARD
# direction only. See "THE FIXTURE-CARRYING FILES" above for what that costs.
# Repository-relative, posix spelling.
DECLARED_PATH_FIXTURE_FILES = (
    "scripts/dangling-path-citation-check.py",
    "scripts/dangling-path-citation-check-test.py",
)


def fail_bad_invocation(detail: str):
    """Stop with EXIT_BAD_INVOCATION, which is not the findings code.

    SystemExit carrying a string prints it and exits 1 -- the code that means
    findings -- so every caller that distinguished a failed run from a dirty
    one was reading a lie. The docstring above promised 2 from the day it was
    written; this is what makes the promise true.
    """
    print(f"{PROGRAM}: {detail}", file=sys.stderr)
    raise SystemExit(EXIT_BAD_INVOCATION)


def names_path_at_segment_boundary(text: str, path: str) -> bool:
    """True when `text` names `path` as a path in its own right.

    Plain containment answers yes to two wrong questions. A move that only
    deepens a path -- gate.py into a system's own scripts directory -- leaves
    the old path as a suffix of the new one, so the backward check reported a
    correct sweep as a stale citation. And a base holding a longer name
    suppressed a forward finding about the shorter one it contains. Both ends
    are anchored, because the first case is a leading boundary and the second
    a trailing one.

    A leading "/" or "./" belongs to the citation, not to a longer path in
    front of it, so the leading boundary is looked for BEHIND them. The six
    hook commands in .claude/settings.json are written with one, and so is
    every launcher that runs a program from the repository root; anchoring on
    the bare character before the match stopped seeing all of them.
    """
    if not path:
        return False
    for match in re.finditer(re.escape(path), text):
        start = match.start()
        while start and text[start - 1] in "./":
            start -= 1
        after = text[match.end():match.end() + 2]
        if start and PATH_SEGMENT_CHARACTER.match(text[start - 1]):
            continue
        if after[:1] == ".":
            if after[1:2] and PATH_SEGMENT_CHARACTER.match(after[1]):
                continue
        elif after[:1] and PATH_SEGMENT_CHARACTER.match(after[0]):
            continue
        return True
    return False


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
    once the line number is off and is still dropped."""
    for token in re.split(r"[\s'\"(){}\[\]<>]+", line):
        token = lint.without_line_suffix(token.rstrip(".,;:!?").lstrip("#*-"))
        if not token or ":" in token:
            continue
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


def base_already_cites(cited: str, base_text: str, lint) -> bool:
    """True when the file's own version at the merge base already named this
    path -- so this change did not introduce the citation.

    Asked as containment until 2026-09-21, which is a different question: a
    base holding <dir>/page.md.bak answered yes to a citation of
    <dir>/page.md, and the author's new dangling citation was dropped. A line
    number is not part of the path, so it comes off before the comparison."""
    return names_path_at_segment_boundary(base_text, lint.without_line_suffix(cited))


def is_declared_path_fixture_file(path: pathlib.Path, repository_root: pathlib.Path) -> bool:
    """True for a file DECLARED_PATH_FIXTURE_FILES names. FORWARD only: the
    one caller is findings_for_file. Adding it to citations_of_removed_paths
    would hide a fixture file's stale citation of a path that moved, and a
    case pins that."""
    try:
        relative = path.resolve().relative_to(repository_root.resolve())
    except ValueError:  # a file outside the repository is not declared
        return False
    return relative.as_posix() in DECLARED_PATH_FIXTURE_FILES


def findings_for_file(path: pathlib.Path, changed: set, lint, root_directories: tuple):
    """(line number, problem) for each finding on a changed line of `path`."""
    relative = path.relative_to(REPOSITORY_ROOT)
    if lint.in_frozen_measured_data(path, REPOSITORY_ROOT):
        return
    # Forward only, and never from citations_of_removed_paths; the cost of
    # this line is stated in this module's docstring.
    if is_declared_path_fixture_file(path, REPOSITORY_ROOT):
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


def citations_of_removed_paths(removed: list, repository_root: pathlib.Path, lint) -> list:
    """(citing file, line number, problem) for every tracked file that still
    names a path this change removed. git grep -F, fixed strings: a path is
    not a pattern, and a file name holding a regex character would otherwise
    match somewhere else or nowhere."""
    findings = []
    for gone in removed:
        hits = subprocess.run(
            ["git", "grep", "-n", "-I", "--no-color", "-F", gone, "--", "."],
            cwd=repository_root, capture_output=True, text=True, check=False)
        for row in hits.stdout.splitlines():
            citing, _, rest = row.partition(":")
            number, _, text = rest.partition(":")
            if not number.isdigit():
                continue
            citing_path = repository_root / citing
            # The frozen measured data records what documents said when they
            # were measured; a path inside it is history, not a citation.
            if lint.in_frozen_measured_data(citing_path, repository_root):
                continue
            # A line saying a file lives in git history names something
            # deliberately absent from the tree, so a move does not make it
            # stale. The drift lint's own exemption, by its own list, applied
            # here to every file type because this direction reads every file
            # type. Fenced content is NOT exempted: a usage example running a
            # script by path does need sweeping when the script moves, and
            # what marks the noise is the history marker, not the fence.
            if any(marker in text for marker in lint.HISTORY_MARKERS):
                continue
            # -F matches anywhere in the line, including inside a longer path
            # that ends with this one -- which is what a move that only
            # deepens a path leaves behind, so a correct sweep reported
            # itself as a stale citation.
            if not names_path_at_segment_boundary(text, gone):
                continue
            findings.append((citing, int(number),
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
        base_text = None
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
            if base_text is None:
                base_text = file_at_merge_base(
                    merge_base_name_of_renamed_file.get(name, name), merge_base, REPOSITORY_ROOT)
            if base_already_cites(cited_path_of(problem), base_text, lint):
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
