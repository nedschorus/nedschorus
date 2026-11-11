#!/usr/bin/env python3
"""List the shared names a branch adds that origin/main does not have, one per line.

A shared name is one other files or agents will meet: a new file path, a top-level
Python function, class or UPPER_CASE constant that another file in the checkout
names, a backquoted name or hyphenated phrase in markdown, a new glossary entry,
and the branch's own name when given. Every file the branch changed is considered
on each run, so a function written before its first caller is listed once the
caller exists; a caller may pass a per-file cache so unchanged files are not parsed
again.

Output lines are `<file>\t<kind>\t<name>`. Exit 0 with no output when nothing is new;
exit 2, naming the git command, when git cannot answer.
"""

import argparse
import ast
import hashlib
import importlib.util
import re
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

_git_output_spec = importlib.util.spec_from_file_location(
    "git_machine_readable_output_runner_and_parser_common",
    Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
    / "git-machine-readable-output-runner-and-parser-common.py")
git_output = importlib.util.module_from_spec(_git_output_spec)
_git_output_spec.loader.exec_module(git_output)

GIT_CALL_TIMEOUT_SECONDS = 20
MAIN_REF = "origin/main"
ORDINARY_HYPHENATED_WORDS_LIST_PATH = "docs/nedschorus-wiki/nedschorus-ordinary-hyphenated-words-list.md"
GLOSSARY_FILE_SUFFIX = "-glossary.md"
# One token set per main commit, shared by every caller on this machine.
MAIN_TOKEN_CACHE_DIRECTORY = Path(tempfile.gettempdir()) / "new-shared-names-main-token-cache"
# Files larger than this on main are data, not prose or code a name is defined in.
MAIN_BLOB_SIZE_LIMIT_BYTES = 2_000_000

NAMING_FRESH_AGENT_NAME = "new-name-propose-and-check-fresh-agent"
# A subagent cannot start NAMING_FRESH_AGENT_NAME, so it lists its new names under this heading in its final report.
# new-shared-names-reminder-hook.py writes the same heading into its reminder.
# A program that refuses until the agent that dispatched a subagent has checked its new names takes this flag.
CONFIRM_DISPATCHING_AGENT_CHECKED_NEW_SHARED_NAMES_COMMAND_LINE_FLAG = "--confirm-dispatching-agent-checked-new-shared-names"
SUBAGENT_REPORT_HEADING_ABOVE_NEW_SHARED_NAMES_FOR_DISPATCHING_AGENT_TO_CHECK = f"New shared names: send these to the {NAMING_FRESH_AGENT_NAME} subagent"

KIND_FILE_PATH = "file-path"
KIND_PYTHON_FUNCTION = "python-function"
KIND_PYTHON_CLASS = "python-class"
KIND_PYTHON_CONSTANT = "python-constant"
KIND_MARKDOWN_BACKQUOTED_NAME = "markdown-backquoted-name"
KIND_MARKDOWN_HYPHENATED_PHRASE = "markdown-hyphenated-phrase"
KIND_GLOSSARY_ENTRY = "glossary-entry"
KIND_BRANCH = "branch"
PYTHON_KINDS = frozenset({KIND_PYTHON_FUNCTION, KIND_PYTHON_CLASS, KIND_PYTHON_CONSTANT})

# A period ends the phrase unless a word character follows it, as in a file name.
HYPHENATED_PHRASE_PATTERN = re.compile(r"(?<![\w`/.-])([a-z]+(?:-[a-z]+)+)(?![\w`/-])(?!\.\w)")
FENCED_CODE_PATTERN = re.compile(r"```.*?```", re.S)
INLINE_CODE_PATTERN = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
# A backquoted span is a name only when it is one token that a separator joins; commands and flags are not.
BACKQUOTED_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9]*(?:[-_][A-Za-z0-9]+)+(?:\.[a-z]{1,5})?$")
GLOSSARY_ENTRY_PATTERN = re.compile(r"^- \*\*([^*]+)\*\*", re.M)
UPPER_CASE_CONSTANT_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*$")
ORDINARY_HYPHENATED_WORD_LINE_PATTERN = re.compile(r"^- ([a-z]+(?:-[a-z]+)+)\s*$", re.M)
# A token on main: what a candidate must equal whole to count as already there.
MAIN_TOKEN_PATTERN = re.compile(rb"[A-Za-z0-9_][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_-]+)*")


class GitFailure(Exception):
    pass


def git_failure_text(subcommand: str, outcome: str, stderr: str = "") -> str:
    """Return a short failure text that is the same each time the same failure recurs."""
    first_line = stderr.strip().splitlines()[0][:200] if stderr.strip() else ""
    return f"git {subcommand} {outcome}" + (f": {first_line}" if first_line else "")


def git(arguments, checkout: Path, allowed_exit_codes=(0,)) -> str:
    try:
        finished = subprocess.run(["git", *arguments], cwd=str(checkout), capture_output=True,
                                  text=True, check=False, timeout=GIT_CALL_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as error:
        raise GitFailure(git_failure_text(arguments[0], "timed out")) from error
    except OSError as error:
        raise GitFailure(git_failure_text(arguments[0], "could not start", error.strerror or "")) from error
    if finished.returncode not in allowed_exit_codes:
        raise GitFailure(git_failure_text(arguments[0], f"exited {finished.returncode}", finished.stderr))
    return finished.stdout


def changed_files(checkout: Path, merge_base: str):
    committed = git(["diff", "-z", "--name-only", "--diff-filter=AMR", merge_base, "HEAD"], checkout)
    uncommitted = git(["diff", "-z", "--name-only", "--diff-filter=AMR", "HEAD"], checkout)
    untracked = git(["ls-files", "-z", "--others", "--exclude-standard"], checkout)
    names = set()
    for listing in (committed, uncommitted, untracked):
        names.update(git_output.nul_separated_fields(listing))
    return sorted(path for path in names if (checkout / path).is_file())


def main_token_set(checkout: Path, main_commit: str):
    """Return every token in main's files, read once per main commit and cached on disk."""
    cache_path = MAIN_TOKEN_CACHE_DIRECTORY / f"{main_commit}.txt"
    try:
        return set(cache_path.read_text().split("\n"))
    except OSError:
        pass
    entries = git_output.tree_entries(git(["ls-tree", "-r", "-l", "-z", main_commit], checkout))
    blob_ids = [entry.object_name for entry in entries
                if entry.object_type == "blob" and entry.size is not None
                and entry.size <= MAIN_BLOB_SIZE_LIMIT_BYTES]
    try:
        finished = subprocess.run(["git", "cat-file", "--batch"], cwd=str(checkout),
                                  input=("\n".join(blob_ids) + "\n").encode(),
                                  capture_output=True, check=False, timeout=GIT_CALL_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as error:
        raise GitFailure(git_failure_text("cat-file", "timed out")) from error
    except OSError as error:
        raise GitFailure(git_failure_text("cat-file", "could not start", error.strerror or "")) from error
    if finished.returncode != 0:
        raise GitFailure(git_failure_text("cat-file", f"exited {finished.returncode}",
                                          finished.stderr.decode(errors="replace")))
    tokens = {token.decode("ascii") for token in MAIN_TOKEN_PATTERN.findall(finished.stdout)}
    # A file main only has as a file, named in none of its texts, is still on main: add each path and its parts.
    for entry in entries:
        tokens.add(entry.path)
        tokens.update(PurePosixPath(entry.path).parts)
    try:
        MAIN_TOKEN_CACHE_DIRECTORY.mkdir(parents=True, exist_ok=True)
        for stale in MAIN_TOKEN_CACHE_DIRECTORY.glob("*.txt"):
            stale.unlink()
        temporary = cache_path.with_suffix(".partial")
        temporary.write_text("\n".join(sorted(tokens)))
        temporary.replace(cache_path)
    except OSError:
        pass
    return tokens


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
                if (isinstance(target, ast.Name) and len(target.id) > 1
                        and UPPER_CASE_CONSTANT_PATTERN.match(target.id)):
                    names.append((KIND_PYTHON_CONSTANT, target.id))
    return names


def markdown_names(text: str):
    names = []
    prose = FENCED_CODE_PATTERN.sub(" ", text)
    for match in INLINE_CODE_PATTERN.finditer(prose):
        span = match.group(1).strip()
        if BACKQUOTED_NAME_PATTERN.match(span):
            names.append((KIND_MARKDOWN_BACKQUOTED_NAME, span))
    for match in HYPHENATED_PHRASE_PATTERN.finditer(INLINE_CODE_PATTERN.sub(" ", prose)):
        names.append((KIND_MARKDOWN_HYPHENATED_PHRASE, match.group(1)))
    return names


def glossary_terms(text: str):
    return {match.group(1).strip() for match in GLOSSARY_ENTRY_PATTERN.finditer(text)}


def every_glossary_term(checkout: Path):
    terms = set()
    for path in git_output.nul_separated_fields(
            git(["ls-files", "-z", f"*{GLOSSARY_FILE_SUFFIX}"], checkout)):
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


def listed_word_or_its_form(phrase: str, listed_words) -> bool:
    """Say whether phrase is a listed word or its -s, -ed or -ing form, such as re-runs,
    re-running, near-misses or hard-coding.

    The spelling rules are loose, so a misspelt form of a listed word also passes.
    """
    if phrase in listed_words:
        return True
    for suffix in ("s", "es", "d", "ed", "ing"):
        if not phrase.endswith(suffix):
            continue
        stem = phrase[:-len(suffix)]
        bases = {stem}
        if suffix in ("ed", "ing") and len(stem) >= 2 and stem[-1] == stem[-2]:
            bases.add(stem[:-1])
        if suffix == "ing":
            bases.add(stem + "e")
        if bases & listed_words:
            return True
    return False


def candidates_in_file(path: str, text: str, checkout: Path, main_commit: str):
    """Return the (kind, name) candidates one file defines, before any check against main."""
    suffix = PurePosixPath(path).suffix
    if suffix == ".py":
        return python_top_level_names(text)
    if suffix != ".md":
        return []
    candidates = list(markdown_names(text))
    if path.endswith(GLOSSARY_FILE_SUFFIX):
        main_text = git(["show", f"{main_commit}:{path}"], checkout, allowed_exit_codes=(0, 128))
        candidates += [(KIND_GLOSSARY_ENTRY, term)
                       for term in sorted(glossary_terms(text) - glossary_terms(main_text))]
    return candidates


def names_used_in_other_files(names_and_files, checkout: Path):
    """Return the names that some file other than the files defining them mentions."""
    if not names_and_files:
        return set()
    arguments = ["grep", "-z", "--untracked", "-I", "-n", "-o", "-w", "-F"]
    for name in sorted({name for name, _ in names_and_files}):
        arguments += ["-e", name]
    found = git(arguments, checkout, allowed_exit_codes=(0, 1))
    files_mentioning = {}
    for match in git_output.grep_matches(found):
        files_mentioning.setdefault(match.text, set()).add(match.path)
    # A file that defines the same name itself, such as its own LOG_PATH, is not a user of this one.
    defining_files = {}
    for name, defining_file in names_and_files:
        defining_files.setdefault(name, set()).add(defining_file)
    return {name for name in defining_files
            if files_mentioning.get(name, set()) - defining_files[name]}


def new_shared_names(checkout: Path, branch_names=(), already_reported=frozenset(),
                     file_cache=None):
    """Find the branch's new shared names.

    already_reported holds "kind\\tname" keys the caller has already shown, which are
    skipped before the costly checks. file_cache maps a path to its content digest and
    candidates, and is updated in place. Returns sorted (file, kind, name) triples.
    """
    file_cache = {} if file_cache is None else file_cache
    main_commit = git(["rev-parse", MAIN_REF], checkout).strip()
    merge_base = git(["merge-base", "HEAD", MAIN_REF], checkout).strip()
    main_paths = set(git_output.nul_separated_fields(
        git(["ls-tree", "-r", "--name-only", "-z", main_commit], checkout)))
    known_terms = every_glossary_term(checkout)
    exempt_phrases = ordinary_hyphenated_words(checkout)
    paths = changed_files(checkout, merge_base)

    found = []
    candidates = []
    for path in paths:
        if path not in main_paths:
            found.append((path, KIND_FILE_PATH, path))
        try:
            content = (checkout / path).read_bytes()
        except OSError:
            continue
        digest = hashlib.sha256(content + main_commit.encode()).hexdigest()
        cached = file_cache.get(path)
        if cached and cached.get("digest") == digest:
            file_candidates = [tuple(pair) for pair in cached["candidates"]]
        else:
            try:
                text = content.decode()
            except UnicodeDecodeError:
                text = ""
            file_candidates = candidates_in_file(path, text, checkout, main_commit) if text else []
            file_cache[path] = {"digest": digest, "candidates": [list(pair) for pair in file_candidates]}
        for kind, name in file_candidates:
            if f"{kind}\t{name}" in already_reported:
                continue
            if kind == KIND_MARKDOWN_HYPHENATED_PHRASE and (
                    name in known_terms or listed_word_or_its_form(name, exempt_phrases)):
                continue
            candidates.append((path, kind, name))
    for stale in set(file_cache) - set(paths):
        del file_cache[stale]

    if candidates:
        on_main = main_token_set(checkout, main_commit)
        candidates = [triple for triple in candidates
                      if triple[2] not in on_main or triple[1] == KIND_GLOSSARY_ENTRY]
    python_candidates = [(name, path) for path, kind, name in candidates if kind in PYTHON_KINDS]
    used_elsewhere = names_used_in_other_files(python_candidates, checkout)
    found.extend(triple for triple in candidates
                 if triple[1] not in PYTHON_KINDS or triple[2] in used_elsewhere)

    for branch_name in branch_names:
        remote_branch = git(["branch", "-r", "--list", f"origin/{branch_name}"], checkout)
        if not remote_branch.strip():
            found.append(("", KIND_BRANCH, branch_name))
    found = [triple for triple in found if f"{triple[1]}\t{triple[2]}" not in already_reported]
    return sorted(set(found))


def new_shared_names_in_files_changed_since(checkout: Path, base_commit: str, commit: str = "HEAD"):
    """Return new_shared_names() limited to the files changed from base_commit to commit, leaving out each
    name base_commit's tree already holds, such as one a pull request added before its fix-round.

    Contents are read from the checkout's files, as new_shared_names() reads them, so commit should be
    what the checkout has checked out. Raises GitFailure when git cannot answer.
    """
    changed = set(git_output.nul_separated_fields(
        git(["diff", "-z", "--name-only", "--diff-filter=AMR", base_commit, commit], checkout)))
    names = [triple for triple in new_shared_names(checkout) if triple[0] in changed]
    if not names:
        return []
    base_paths = set(git_output.nul_separated_fields(
        git(["ls-tree", "-r", "--name-only", "-z", base_commit], checkout)))
    patterns = []
    for name in sorted({name for _, kind, name in names if kind != KIND_FILE_PATH}):
        patterns += ["-e", name]
    in_base = (set(git(["grep", "-h", "-o", "-w", "-F", "-I", *patterns, base_commit], checkout,
                       allowed_exit_codes=(0, 1)).splitlines()) if patterns else set())
    return [(path, kind, name) for path, kind, name in names
            if name not in (base_paths if kind == KIND_FILE_PATH else in_base)]


def unchecked_new_shared_names_refusal_text(names, what_stopped, rename_instruction, rerun_command):
    """The refusal a program prints when names, (file, kind, name) triples, would go out unchecked.

    what_stopped says what the program did not do; rename_instruction says where each rename goes; the
    agent runs rerun_command, which carries CONFIRM_DISPATCHING_AGENT_CHECKED_NEW_SHARED_NAMES_COMMAND_LINE_FLAG, once the names are checked.
    """
    listed = [f"  {name} ({kind}{', in ' + path if path and path != name else ''})" for path, kind, name in names]
    return (
        f"{what_stopped}, because no agent has checked these new shared names against the naming page:\n"
        + "\n".join(listed) + "\n"
        f"If you are a subagent, you cannot start the {NAMING_FRESH_AGENT_NAME} subagent, so stop here: end "
        f"your final report with the heading `{SUBAGENT_REPORT_HEADING_ABOVE_NEW_SHARED_NAMES_FOR_DISPATCHING_AGENT_TO_CHECK}`, under it one "
        "line per name, <name>: <one sentence saying what it names and which file it is in>, and last this line, "
        "word for word: \"For the agent that dispatched me: send the lines under that heading to the "
        f"{NAMING_FRESH_AGENT_NAME} subagent, check by hand each name its report lists under Not checked:, then send "
        "me with SendMessage each rename its report or your check calls for, or that none is needed. I go on "
        "with my work then, so do nothing else my ending calls for until I end again.\"\n"
        f"If you can start a subagent, send those lines to the {NAMING_FRESH_AGENT_NAME} subagent yourself.\n"
        f"{rename_instruction} Then run: {rerun_command}\n"
        "If a listed name is not one you chose, such as quoted text or an existing name written differently, "
        "leave it off the list; if no name is left, run that command at once.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--checkout", default=".", help="the checkout to scan (default: here)")
    parser.add_argument("--branch-name", help="a branch name about to be created, to list as well")
    arguments = parser.parse_args()
    try:
        checkout = Path(git(["rev-parse", "--show-toplevel"], Path(arguments.checkout)).strip())
        names = new_shared_names(checkout, [arguments.branch_name] if arguments.branch_name else [])
    except GitFailure as failure:
        print(f"new-shared-names-in-changed-files-list: {failure}", file=sys.stderr)
        return 2
    for path, kind, name in names:
        print(f"{path}\t{kind}\t{name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
