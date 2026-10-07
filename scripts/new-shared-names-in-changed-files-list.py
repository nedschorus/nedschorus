#!/usr/bin/env python3
"""List the shared names a branch adds that origin/main does not have, one per line.

A shared name is one other files or agents will meet: a new file path, a top-level
Python function, class or UPPER_CASE constant that another file in the checkout
names, a backquoted name or hyphenated phrase in markdown, a new glossary entry,
and the branch's own name when given. Every file the branch changed is rescanned
on each run, so a function written before its first caller is listed once the
caller exists.

Output lines are `<file>\t<kind>\t<name>`. Exit 0 with no output when nothing is new;
exit 2, naming the git command, when git cannot answer.
"""

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

GIT_CALL_TIMEOUT_SECONDS = 20
MAIN_REF = "origin/main"
ORDINARY_HYPHENATED_WORDS_LIST_PATH = "docs/nedschorus-wiki/nedschorus-ordinary-hyphenated-words-list.md"
GLOSSARY_FILE_SUFFIX = "-glossary.md"

KIND_FILE_PATH = "file-path"
KIND_PYTHON_FUNCTION = "python-function"
KIND_PYTHON_CLASS = "python-class"
KIND_PYTHON_CONSTANT = "python-constant"
KIND_MARKDOWN_BACKQUOTED_NAME = "markdown-backquoted-name"
KIND_MARKDOWN_HYPHENATED_PHRASE = "markdown-hyphenated-phrase"
KIND_GLOSSARY_ENTRY = "glossary-entry"
KIND_BRANCH = "branch"

HYPHENATED_PHRASE_PATTERN = re.compile(r"(?<![\w`/.-])([a-z]+(?:-[a-z]+)+)(?![\w`/.-])")
FENCED_OR_INLINE_CODE_PATTERN = re.compile(r"```.*?```|`[^`\n]*`", re.S)
INLINE_CODE_PATTERN = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
FENCED_CODE_PATTERN = re.compile(r"```.*?```", re.S)
# A backquoted span is a name only when it is one token that a separator joins; commands and flags are not.
BACKQUOTED_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9]*(?:[-_][A-Za-z0-9]+)+(?:\.[a-z]{1,5})?$")
GLOSSARY_ENTRY_PATTERN = re.compile(r"^- \*\*([^*]+)\*\*", re.M)
UPPER_CASE_CONSTANT_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$")
ORDINARY_HYPHENATED_WORD_LINE_PATTERN = re.compile(r"^- ([a-z]+(?:-[a-z]+)+)\s*$", re.M)


class GitFailure(Exception):
    pass


def git(arguments, checkout: Path, allowed_exit_codes=(0,)) -> str:
    try:
        finished = subprocess.run(["git", *arguments], cwd=str(checkout), capture_output=True,
                                  text=True, check=False, timeout=GIT_CALL_TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise GitFailure(f"git {' '.join(arguments)}: {error}") from error
    if finished.returncode not in allowed_exit_codes:
        raise GitFailure(f"git {' '.join(arguments)} exited {finished.returncode}: "
                         f"{finished.stderr.strip()}")
    return finished.stdout


def changed_files(checkout: Path, merge_base: str):
    committed = git(["diff", "--name-only", "--diff-filter=AMR", merge_base, "HEAD"], checkout)
    uncommitted = git(["diff", "--name-only", "--diff-filter=AMR", "HEAD"], checkout)
    untracked = git(["ls-files", "--others", "--exclude-standard"], checkout)
    names = set()
    for listing in (committed, uncommitted, untracked):
        names.update(line for line in listing.splitlines() if line)
    return sorted(path for path in names if (checkout / path).is_file())


def main_text_of(path: str, checkout: Path) -> str:
    return git(["show", f"{MAIN_REF}:{path}"], checkout, allowed_exit_codes=(0, 128))


def names_main_has(candidates, checkout: Path):
    """Return the candidates that occur anywhere on main, as whole words."""
    if not candidates:
        return set()
    arguments = ["grep", "-h", "-o", "-w", "-F"]
    for candidate in sorted(candidates):
        arguments += ["-e", candidate]
    found = git(arguments + [MAIN_REF, "--"], checkout, allowed_exit_codes=(0, 1))
    return {line for line in found.splitlines() if line in candidates}


def name_used_in_another_file(name: str, defining_file: str, checkout: Path) -> bool:
    found = git(["grep", "--untracked", "-l", "-w", "-F", "-e", name], checkout,
                allowed_exit_codes=(0, 1))
    return any(path and path != defining_file for path in found.splitlines())


def python_top_level_names(text: str):
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return []
    names = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.append((KIND_PYTHON_FUNCTION, node.name))
        elif isinstance(node, ast.ClassDef):
            names.append((KIND_PYTHON_CLASS, node.name))
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and UPPER_CASE_CONSTANT_PATTERN.match(target.id):
                    names.append((KIND_PYTHON_CONSTANT, target.id))
    return names


def markdown_names(text: str):
    names = []
    prose = FENCED_CODE_PATTERN.sub(" ", text)
    for match in INLINE_CODE_PATTERN.finditer(prose):
        span = match.group(1).strip()
        if BACKQUOTED_NAME_PATTERN.match(span):
            names.append((KIND_MARKDOWN_BACKQUOTED_NAME, span))
    for match in HYPHENATED_PHRASE_PATTERN.finditer(FENCED_OR_INLINE_CODE_PATTERN.sub(" ", text)):
        names.append((KIND_MARKDOWN_HYPHENATED_PHRASE, match.group(1)))
    return names


def glossary_terms(text: str):
    return {match.group(1).strip() for match in GLOSSARY_ENTRY_PATTERN.finditer(text)}


def every_glossary_term(checkout: Path):
    terms = set()
    for path in git(["ls-files", f"*{GLOSSARY_FILE_SUFFIX}"], checkout).splitlines():
        try:
            terms.update(term.lower() for term in glossary_terms((checkout / path).read_text()))
        except OSError:
            continue
    return terms


def ordinary_hyphenated_words(checkout: Path):
    try:
        text = (checkout / ORDINARY_HYPHENATED_WORDS_LIST_PATH).read_text()
    except OSError:
        return set()
    return set(ORDINARY_HYPHENATED_WORD_LINE_PATTERN.findall(text))


def new_shared_names(checkout: Path, branch_name=None):
    """Return sorted (file, kind, name) triples for the shared names main does not have."""
    merge_base = git(["merge-base", "HEAD", MAIN_REF], checkout).strip()
    main_paths = set(git(["ls-tree", "-r", "--name-only", MAIN_REF], checkout).splitlines())
    known_terms = every_glossary_term(checkout)
    exempt_phrases = ordinary_hyphenated_words(checkout)

    found = []
    candidates = []
    for path in changed_files(checkout, merge_base):
        if path not in main_paths:
            found.append((path, KIND_FILE_PATH, path))
        try:
            text = (checkout / path).read_text()
        except (OSError, UnicodeDecodeError):
            continue
        suffix = PurePosixPath(path).suffix
        if suffix == ".py":
            for kind, name in python_top_level_names(text):
                if name_used_in_another_file(name, path, checkout):
                    candidates.append((path, kind, name))
        elif suffix == ".md":
            if path.endswith(GLOSSARY_FILE_SUFFIX):
                for term in sorted(glossary_terms(text) - glossary_terms(main_text_of(path, checkout))):
                    found.append((path, KIND_GLOSSARY_ENTRY, term))
            for kind, name in markdown_names(text):
                if kind == KIND_MARKDOWN_HYPHENATED_PHRASE and (
                        name in known_terms or name in exempt_phrases):
                    continue
                candidates.append((path, kind, name))

    on_main = names_main_has({name for _, _, name in candidates}, checkout)
    found.extend(triple for triple in candidates if triple[2] not in on_main)

    if branch_name:
        remote_branch = git(["branch", "-r", "--list", f"origin/{branch_name}"], checkout)
        if not remote_branch.strip():
            found.append(("", KIND_BRANCH, branch_name))
    return sorted(set(found))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--checkout", default=".", help="the checkout to scan (default: here)")
    parser.add_argument("--branch-name", help="a branch name about to be created, to list as well")
    arguments = parser.parse_args()
    try:
        checkout = Path(git(["rev-parse", "--show-toplevel"], Path(arguments.checkout)).strip())
        names = new_shared_names(checkout, arguments.branch_name)
    except GitFailure as failure:
        print(f"new-shared-names-in-changed-files-list: {failure}", file=sys.stderr)
        return 2
    for path, kind, name in names:
        print(f"{path}\t{kind}\t{name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
