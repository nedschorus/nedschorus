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
to programs the project has decided to build and has not built, such as
scripts/ghi-issue-write.py under nedschorus#46 and quality/runs.jsonl from
the toolchain plan. A check over whole files would fail every pull request
on prose its author never touched. So a finding is reported only when its
line is one the change added or altered, the rule
scripts/md-drift-lint.py's caller applies by hand today.

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


def changed_lines_by_file(base: str, repository_root: pathlib.Path) -> dict:
    """{path relative to the root: set of line numbers the diff adds or
    alters}. A deleted file has no lines and does not appear. --unified=0 so
    a hunk covers only what changed, not three lines of neighbours whose
    citations are not this change's business."""
    diff = subprocess.run(
        ["git", "diff", "--unified=0", "--no-color", "--no-ext-diff", f"{base}...HEAD"],
        cwd=repository_root, capture_output=True, text=True, check=False)
    if diff.returncode != 0:
        raise SystemExit(f"{PROGRAM}: git diff against {base} failed: "
                         f"{diff.stderr.strip() or diff.returncode}")
    changed: dict = {}
    current = None
    for line in diff.stdout.splitlines():
        if line.startswith("+++ "):
            target = line[4:].strip()
            current = None if target == "/dev/null" else target[2:] if target.startswith("b/") else target
            continue
        match = HUNK_HEADER.match(line)
        if match and current:
            start = int(match.group(1))
            count = int(match.group(2)) if match.group(2) is not None else 1
            changed.setdefault(current, set()).update(range(start, start + count))
    return changed


def plain_path_citations(line: str, root_directories: tuple, extensions: tuple):
    """The repo-root-relative paths a non-Markdown line names, unbackticked.
    Punctuation a sentence puts after a path is stripped, so
    "# scripts/main-gatekeeper.py (ruled 2026-08-12)," yields the path."""
    for token in re.split(r"[\s'\"(){}\[\]<>]+", line):
        token = token.rstrip(".,;:!?").lstrip("#*-")
        if not token or "://" in token or ":" in token:
            continue
        head = token.split("/", 1)[0]
        if head not in root_directories:
            continue
        if not token.endswith(extensions):
            continue
        yield token


def file_at_base(relative: str, base: str, repository_root: pathlib.Path) -> str:
    """The file's text at `base`, or "" when it was not there."""
    shown = subprocess.run(["git", "show", f"{base}:{relative}"],
                           cwd=repository_root, capture_output=True, text=True, check=False)
    return shown.stdout if shown.returncode == 0 else ""


def cited_path_of(problem: str) -> str:
    """The path a forward finding names, for comparison with the base."""
    return problem.rsplit(": ", 1)[-1].strip()


def findings_for_file(path: pathlib.Path, changed: set, lint, root_directories: tuple):
    """(line number, problem) for each finding on a changed line of `path`."""
    relative = path.relative_to(REPOSITORY_ROOT)
    if lint.in_frozen_measured_data(path, REPOSITORY_ROOT):
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
        for token in plain_path_citations(line, root_directories, lint.PATH_EXTENSIONS):
            if lint.ignored_by_git(token, path, REPOSITORY_ROOT):
                continue
            if not (REPOSITORY_ROOT / token).exists():
                yield line_number, f"path does not exist: {token}"


def paths_this_change_removed(base: str, repository_root: pathlib.Path) -> list:
    """The repository paths that existed at `base` and do not exist now: a
    deletion, or a rename's old name. Read from --name-status rather than
    from the tree, so a file moved and a file deleted are one case."""
    names = subprocess.run(
        ["git", "diff", "--name-status", "--no-color", "--no-ext-diff", f"{base}...HEAD"],
        cwd=repository_root, capture_output=True, text=True, check=False)
    if names.returncode != 0:
        raise SystemExit(f"{PROGRAM}: git diff --name-status against {base} failed: "
                         f"{names.stderr.strip() or names.returncode}")
    removed = []
    for row in names.stdout.splitlines():
        fields = row.split("\t")
        if len(fields) < 2:
            continue
        status, old = fields[0], fields[1]
        if status.startswith("D") or status.startswith("R"):
            if not (repository_root / old).exists():
                removed.append(old)
    return removed


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
            number, _, _text = rest.partition(":")
            if not number.isdigit():
                continue
            citing_path = repository_root / citing
            # The frozen measured data records what documents said when they
            # were measured; a path inside it is history, not a citation.
            if lint.in_frozen_measured_data(citing_path, repository_root):
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
    changed = changed_lines_by_file(arguments.base, REPOSITORY_ROOT)
    if arguments.files:
        wanted = {str(pathlib.Path(name)) for name in arguments.files}
        changed = {name: lines for name, lines in changed.items() if name in wanted}

    findings = []
    removed = paths_this_change_removed(arguments.base, REPOSITORY_ROOT)
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
            # of scripts/md-drift-lint.py makes by hand.
            if base_text is None:
                base_text = file_at_base(name, arguments.base, REPOSITORY_ROOT)
            if cited_path_of(problem) in base_text:
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
