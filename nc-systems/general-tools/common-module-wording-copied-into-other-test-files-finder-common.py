#!/usr/bin/env python3
"""Find the test files that keep their own copy of a shared module's wording.

A `*-common.py` module that holds the master copy of wording programs print is
pinned word for word by its own tests alone. Every other test gets the wording
by calling the module, so a change to it fails one suite, not every suite of a
program that prints it. A guard suite calls
common_module_wording_copies_in_other_test_files for each such module, and
fails while a list it returns is not empty.

The module's wording is each string literal assigned at its top level, and each
literal piece of a string or f-string inside its top-level functions and
classes. Docstrings are left out, and so are strings inside a raise statement,
which tell a programmer how to call the module. A piece counts only when it has
at least MINIMUM_WORDS_IN_A_COPIED_PIECE words: a shorter one, such as
"fell back to", is a phrase other programs say in their own words.

A copy is a run of at least MINIMUM_WORDS_IN_A_COPIED_PIECE words in a row
that a piece and a string literal share, docstrings left out, in a test file of
the checkout, as path_is_test_file in
python-source-agent-facing-string-collector-common.py decides. Words are what
whitespace separates, compared without the punctuation at either end, so
"user." is the word "user". Implicitly concatenated literals count as one
literal; an f-string's fields split it, so a run must fall inside one literal
part. A test file whose name starts with the module's own file name, less
`.py`, is the module's own test and is skipped.

Not found: a copy split across `+` or across separate literals, a copy shorter
than the floor, a reworded copy, a copied run whose end word is only part of a
word in the literal, and wording the module builds at run time without a
literal piece of the floor's length.

The checkout's files are listed with `git ls-files`, run without the variables
that redirect git, such as GIT_DIR, so a guard started from a git hook still
searches checkout_root. A failing git, or a test
file that cannot be read or parsed, raises to the caller, so the guard that
called it fails and names the error rather than passing on a partial search.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "common_module_wording_copied_into_other_test_files_finder_common", <path>)
"""

import ast
import importlib.util
import re
import string
import subprocess
from pathlib import Path

MINIMUM_WORDS_IN_A_COPIED_PIECE = 7
GIT_LS_FILES_TIMEOUT_SECONDS = 60
# Stands in for an f-string field, so a piece cannot match across one.
F_STRING_FIELD_STAND_IN = "\0"

_collector_spec = importlib.util.spec_from_file_location(
    "python_source_agent_facing_string_collector_common",
    Path(__file__).resolve().parent / "python-source-agent-facing-string-collector-common.py")
_collector = importlib.util.module_from_spec(_collector_spec)
_collector_spec.loader.exec_module(_collector)
_git_environment_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_variables_removal_common",
    Path(__file__).resolve().parent / "git-redirecting-environment-variables-removal-common.py")
_git_environment = importlib.util.module_from_spec(_git_environment_spec)
_git_environment_spec.loader.exec_module(_git_environment)


def _whitespace_runs_made_single_spaces(text):
    return re.sub(r"\s+", " ", text)


def _docstring_nodes(tree):
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                    and isinstance(first.value.value, str):
                docstrings.add(first.value)
    return docstrings


def _literal_pieces(node, left_out):
    pieces = []
    for inner in ast.walk(node):
        if inner in left_out:
            continue
        if isinstance(inner, ast.Raise):
            left_out.update(ast.walk(inner))
        elif isinstance(inner, ast.Constant) and isinstance(inner.value, str):
            pieces.append(inner.value)
    return pieces


def common_module_wording_pieces(module_path):
    """Return {piece: sorted names of the constants and functions that hold it}, whitespace made single."""
    tree = ast.parse(Path(module_path).read_text(encoding="utf-8"))
    docstrings = _docstring_nodes(tree)
    names_by_piece = {}
    for statement in tree.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name, holder = statement.name, statement
        elif isinstance(statement, (ast.Assign, ast.AnnAssign)) and statement.value is not None:
            target = statement.targets[0] if isinstance(statement, ast.Assign) else statement.target
            name, holder = ast.unparse(target), statement.value
        else:
            continue
        for piece in _literal_pieces(holder, set(docstrings)):
            piece = _whitespace_runs_made_single_spaces(piece).strip()
            if len(piece.split()) >= MINIMUM_WORDS_IN_A_COPIED_PIECE:
                names_by_piece.setdefault(piece, set()).add(name)
    return {piece: sorted(names) for piece, names in names_by_piece.items()}


def _test_file_literals(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    docstrings = _docstring_nodes(tree)
    inside_f_strings = set()
    literals = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            inside_f_strings.update(node.values)
            literals.append((node.lineno, "".join(
                part.value if isinstance(part, ast.Constant) else F_STRING_FIELD_STAND_IN
                for part in node.values)))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and node not in docstrings and node not in inside_f_strings:
            literals.append((node.lineno, node.value))
    return [(line, _whitespace_runs_made_single_spaces(text)) for line, text in literals]


def _words_compared(words):
    return tuple(word.strip(string.punctuation) for word in words)


def _piece_windows_of_the_floor_length(pieces):
    """Return {compared words of a run of the floor's length: [(piece, index of its first word in the piece)]}."""
    windows = {}
    for piece in pieces:
        compared = _words_compared(piece.split())
        for start in range(len(compared) - MINIMUM_WORDS_IN_A_COPIED_PIECE + 1):
            windows.setdefault(compared[start:start + MINIMUM_WORDS_IN_A_COPIED_PIECE], []).append((piece, start))
    return windows


def _runs_shared_with_pieces(text, windows):
    """Return the set of (piece, run) for each longest run of words a part of text between fields shares with a piece."""
    runs = set()
    for part in text.split(F_STRING_FIELD_STAND_IN):
        compared = _words_compared(part.split())
        # (piece, index in the piece of the latest window's first word): index in the piece of the run's first word.
        open_runs = {}
        for start in range(len(compared) - MINIMUM_WORDS_IN_A_COPIED_PIECE + 1):
            window = compared[start:start + MINIMUM_WORDS_IN_A_COPIED_PIECE]
            continued = {(piece, at): open_runs.get((piece, at - 1), at) for piece, at in windows.get(window, [])}
            runs.update(_run_words(piece, first, at) for (piece, at), first in open_runs.items()
                        if (piece, at + 1) not in continued)
            open_runs = continued
        runs.update(_run_words(piece, first, at) for (piece, at), first in open_runs.items())
    return runs


def _run_words(piece, first, last_window_start):
    words = piece.split()[first:last_window_start + MINIMUM_WORDS_IN_A_COPIED_PIECE]
    return piece, " ".join(words).strip(string.punctuation)


def common_module_wording_copies_in_other_test_files(module_path, checkout_root):
    """Return (test file path relative to checkout_root, line, run, names) for each copy, in path and line order.

    line is the first line of the literal holding the copy; run is the longest run of words the literal shares
    with a piece, in the module's words, less the punctuation at its two ends; names are those of the constants and functions whose pieces hold it.
    """
    checkout_root = Path(checkout_root)
    own_test_prefix = Path(module_path).name[:-len(".py")]
    pieces = common_module_wording_pieces(module_path)
    listed = subprocess.run(["git", "-C", str(checkout_root), "ls-files", "-z", "--", "*.py"],
                            capture_output=True, text=True, check=True,
                            timeout=GIT_LS_FILES_TIMEOUT_SECONDS,
                            env=_git_environment.environment_without_git_redirecting_variables()).stdout.split("\0")
    windows = _piece_windows_of_the_floor_length(pieces)
    names_by_copy = {}
    for relative in sorted(path for path in listed if path):
        if not _collector.path_is_test_file(relative) or Path(relative).name.startswith(own_test_prefix):
            continue
        for line, text in _test_file_literals(checkout_root / relative):
            for piece, run in _runs_shared_with_pieces(text, windows):
                names_by_copy.setdefault((relative, line, run), set()).update(pieces[piece])
    return sorted((relative, line, run, sorted(names)) for (relative, line, run), names in names_by_copy.items())


def copied_wording_report_line(copy):
    """The line a failing guard prints for one copy that common_module_wording_copies_in_other_test_files found."""
    relative, line, piece, names = copy
    return (f"{relative}:{line} keeps its own copy of wording that {' or '.join(names)} holds: "
            f"\"{piece}\". Get it by calling {' or '.join(names)} from the module instead.")
