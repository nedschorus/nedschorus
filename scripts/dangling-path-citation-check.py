#!/usr/bin/env python3
"""Check new citations and citations of removed paths for dangling references.

Run on a clean tree: diff line numbers come from HEAD, but citation text and
existence checks read the working tree."""
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

HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")

# Keep placeholder brackets intact so marker checks can reject the whole token.
# Backticks delimit known-path citations, but forward plain-path checks exclude backticked fixtures.
NAMED_PATH_TOKEN_SEPARATOR = re.compile(r"[\s'\"()\[\]`]+")
PLAIN_PATH_TOKEN_SEPARATOR = re.compile(r"[\s'\"()\[\]]+")

# Project tests use a -test stem or a tests directory, regardless of extension.
PROJECT_TEST_FILE_STEM_ENDING = "-test"
PROJECT_TEST_DIRECTORY_NAME = "tests"


def fail_bad_invocation(detail: str):
    # SystemExit with a string exits 1, which means findings here, not an invalid invocation.
    print(f"{PROGRAM}: {detail}", file=sys.stderr)
    raise SystemExit(EXIT_BAD_INVOCATION)


def carries_a_marker_the_lint_skips(token: str, lint) -> bool:
    # Check the whole token before resolution: normpath can erase a placeholder component followed by "..".
    return any(marker in token for marker in lint.SKIP_MARKERS)


def citation_tokens_on_line(line: str, citing_path: pathlib.Path, lint):
    """Yield path tokens and Markdown link targets."""
    # Known removed paths may lack extensions; forward-only path filters would miss those citations.
    if citing_path.suffix == ".md":
        for target in lint.MARKDOWN_LINK.findall(line):
            target = lint.unwrap_angle_link_target(target)
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
    """Yield repository-relative candidates for the line's citations."""
    for token in citation_tokens_on_line(line, citing_path, lint):
        yield from lint.repo_relative_candidates(token, citing_path, repository_root)


def repository_root_directories(repository_root: pathlib.Path) -> tuple:
    names = subprocess.run(["git", "ls-tree", "HEAD", "--name-only", "-d"],
                           cwd=repository_root, capture_output=True, text=True, check=False)
    return tuple(sorted(name for name in names.stdout.split() if name))


def load_md_drift_lint():
    path = SCRIPTS_DIRECTORY / "md-drift-lint.py"
    specification = importlib.util.spec_from_file_location("md_drift_lint", path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def merge_base_with_head(base: str, repository_root: pathlib.Path) -> str:
    # Use the same merge base for diffs and file text; the base tip can contain changes this branch never saw.
    found = subprocess.run(["git", "merge-base", base, "HEAD"],
                           cwd=repository_root, capture_output=True, text=True, check=False)
    if found.returncode != 0 or not found.stdout.strip():
        fail_bad_invocation(f"no merge base between {base} and HEAD: "
                            f"{found.stderr.strip() or found.returncode}")
    return found.stdout.strip()


def changed_lines_by_file(merge_base: str, repository_root: pathlib.Path) -> dict:
    """Return {repository-relative path: added or altered line numbers}."""
    diff = subprocess.run(
        ["git", "diff", "--unified=0", "--no-color", "--no-ext-diff", f"{merge_base}..HEAD"],
        cwd=repository_root, capture_output=True, text=True, check=False)
    if diff.returncode != 0:
        fail_bad_invocation(f"git diff against {merge_base} failed: "
                            f"{diff.stderr.strip() or diff.returncode}")
    changed: dict = {}
    current = None
    # Only the diff preamble identifies +++ headers; added "++ " and removed "-- " text can mimic headers.
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
    """Yield unbackticked repository paths from a non-Markdown line."""
    # Strip line-number suffixes before rejecting colons, so numbered citations remain eligible.
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
    """Return the file's merge-base text, or "" if absent."""
    shown = subprocess.run(["git", "show", f"{merge_base}:{relative}"],
                           cwd=repository_root, capture_output=True, text=True, check=False)
    return shown.stdout if shown.returncode == 0 else ""


def cited_path_of(problem: str) -> str:
    """Return the path named by a forward finding."""
    return problem.rsplit(": ", 1)[-1].strip()


def paths_the_base_text_cites(base_text: str, base_name: str, lint,
                              repository_root: pathlib.Path) -> set:
    # Apply the forward check's fence and marker rules so non-citations cannot suppress new citations.
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
    # Compare resolved paths for equality: a suffix or prefix match can suppress a different citation.
    candidates = set(lint.repo_relative_candidates(
        lint.without_line_suffix(cited), citing_path, repository_root))
    return bool(candidates & base_cited_paths)


def is_project_test_file(path: pathlib.Path, repository_root: pathlib.Path) -> bool:
    try:
        relative = path.resolve().relative_to(repository_root.resolve())
    except ValueError:
        return False
    return (relative.stem.endswith(PROJECT_TEST_FILE_STEM_ENDING)
            or PROJECT_TEST_DIRECTORY_NAME in relative.parts[:-1])


def findings_for_file(path: pathlib.Path, changed: set, lint, root_directories: tuple):
    """Yield (line number, problem) for changed lines."""
    relative = path.relative_to(REPOSITORY_ROOT)
    if lint.in_frozen_measured_data(path, REPOSITORY_ROOT):
        return
    # Skip test fixtures only forward; backward checks must still catch stale module citations.
    if is_project_test_file(path, REPOSITORY_ROOT):
        return
    if path.suffix == ".md":
        for line_number, problem in lint.lint_markdown(path, REPOSITORY_ROOT):
            if line_number in changed and ("does not exist" in problem):
                yield line_number, problem
        return
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return
    for line_number, line in enumerate(text.splitlines(), 1):
        if line_number not in changed:
            continue
        for token in plain_path_citations(line, root_directories, lint):
            if lint.ignored_by_git(token, path, REPOSITORY_ROOT):
                continue
            if not (REPOSITORY_ROOT / token).exists():
                yield line_number, f"path does not exist: {token}"


def name_status_rows_against_merge_base(merge_base: str, repository_root: pathlib.Path) -> list:
    """Return tab-split name-status rows that carry paths."""
    names = subprocess.run(
        ["git", "diff", "--name-status", "--no-color", "--no-ext-diff", f"{merge_base}..HEAD"],
        cwd=repository_root, capture_output=True, text=True, check=False)
    if names.returncode != 0:
        fail_bad_invocation(f"git diff --name-status against {merge_base} failed: "
                            f"{names.stderr.strip() or names.returncode}")
    return [fields for fields in (row.split("\t") for row in names.stdout.splitlines())
            if len(fields) >= 2]


def paths_this_change_removed(name_status_rows: list, repository_root: pathlib.Path) -> list:
    """Return deleted paths and old names of renamed files that no longer exist."""
    # A case-folding filesystem cannot detect case-only renames through exists().
    removed = []
    for fields in name_status_rows:
        status, old = fields[0], fields[1]
        if status.startswith("D") or status.startswith("R"):
            if not (repository_root / old).exists():
                removed.append(old)
    return removed


def ancestor_directories_of(relative: str) -> list:
    """Yield ancestor directories, deepest first, excluding the repository root."""
    components = relative.split("/")[:-1]
    return ["/".join(components[:depth]) for depth in range(len(components), 0, -1)]


def directories_in_the_head_tree(repository_root: pathlib.Path) -> frozenset:
    # git mv can leave empty source directories on disk; HEAD gives the same answer in fresh and existing checkouts.
    listed = subprocess.run(["git", "ls-tree", "-r", "-d", "--name-only", "HEAD"],
                            cwd=repository_root, capture_output=True, text=True, check=False)
    if listed.returncode != 0:
        fail_bad_invocation(f"git ls-tree of HEAD failed: "
                            f"{listed.stderr.strip() or listed.returncode}")
    return frozenset(name for name in listed.stdout.splitlines() if name)


def directories_this_change_emptied(removed_files: list, repository_root: pathlib.Path) -> list:
    # Git name-status rows contain files only, so removed directories must be derived from their ancestors.
    surviving = directories_in_the_head_tree(repository_root)
    return sorted({ancestor for gone in removed_files
                   for ancestor in ancestor_directories_of(gone)
                   if ancestor not in surviving})


def removed_paths_a_line_is_reported_for(cited_and_removed: set) -> list:
    """Return the deepest removed paths cited on this line."""
    # Suppress ancestors per line, not per document: a separate sentence still needs correction.
    return sorted(path for path in cited_and_removed
                  if not any(other.startswith(path + "/") for other in cited_and_removed))


def merge_base_names_of_renamed_files(name_status_rows: list) -> dict:
    """Return {current path: merge-base path} for detected renames."""
    # Moves below Git's similarity threshold appear as delete/add pairs and have no old name here.
    return {fields[2]: fields[1] for fields in name_status_rows
            if len(fields) >= 3 and fields[0].startswith("R")}


def files_that_might_name_a_removed_path(removed: list, repository_root: pathlib.Path) -> set:
    # Search by basename to include relative sibling links; full-path searches miss those citations.
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
    """Yield (file, line number, problem) for citations of removed paths."""
    wanted = set(removed)
    findings = []
    for citing in sorted(files_that_might_name_a_removed_path(removed, repository_root)):
        citing_path = repository_root / citing
        # Frozen measurements record historical text, not current citations.
        if lint.in_frozen_measured_data(citing_path, repository_root):
            continue
        try:
            text = citing_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            # History markers denote deliberately absent paths; fences alone do not, since examples can go stale.
            if any(marker in line for marker in lint.HISTORY_MARKERS):
                continue
            cited = set(repository_paths_a_line_cites(
                line, citing_path, lint, repository_root))
            for gone in removed_paths_a_line_is_reported_for(cited & wanted):
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
    removed_files = paths_this_change_removed(name_status_rows, REPOSITORY_ROOT)
    removed = removed_files + directories_this_change_emptied(removed_files, REPOSITORY_ROOT)
    merge_base_name_of_renamed_file = merge_base_names_of_renamed_files(name_status_rows)
    for citing, line_number, problem in citations_of_removed_paths(
            removed, REPOSITORY_ROOT, lint):
        findings.append(f"{citing}:{line_number}: {problem}")
    for name in sorted(changed):
        path = REPOSITORY_ROOT / name
        if not path.is_file():
            continue
        base_cited_paths = None
        for line_number, problem in findings_for_file(path, changed[name], lint, root_directories):
            # A changed line can retain old citations; compare with the file's merge-base text under its old name.
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
