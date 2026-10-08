#!/usr/bin/env python3
"""Tests for new-shared-names-in-changed-files-list.py and new-shared-names-reminder-hook.py.

Run: python3 scripts/new-shared-names-in-changed-files-list-test.py
Prints one line per case and exits non-zero if any case fails.

Each case builds a throwaway origin repository and a clone whose branch adds files,
then runs the lister or the hook as a program against the clone. The first case is
the positive one, so the lister is shown able to report before any case asserts
that it stays silent.
"""

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# Before anything runs git, so scratch repositories are built where this suite says.
_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().with_name("git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

LISTER_PATH = Path(__file__).with_name("new-shared-names-in-changed-files-list.py")
HOOK_PATH = Path(__file__).with_name("new-shared-names-reminder-hook.py")
EXCEPTION_LIST_PATH = "docs/nedschorus-wiki/nedschorus-ordinary-hyphenated-words-list.md"

FAILURES = []


def check(description, condition, detail=""):
    if condition:
        print(f"ok: {description}")
    else:
        print(f"FAIL: {description}{': ' + detail if detail else ''}")
        FAILURES.append(description)


def git(arguments, cwd):
    subprocess.run(["git", *arguments], cwd=str(cwd), check=True, capture_output=True, text=True)


def make_clone(root: Path, main_files: dict) -> Path:
    """Return a clone on branch topic whose origin/main holds main_files."""
    origin = root / "origin.git"
    seed = root / "seed"
    clone = root / "clone"
    git(["init", "-q", "--bare", "-b", "main", str(origin)], root)
    git(["init", "-q", "-b", "main", str(seed)], root)
    for config in (["user.email", "test@example.com"], ["user.name", "test"]):
        git(["config", *config], seed)
    for path, text in main_files.items():
        (seed / path).parent.mkdir(parents=True, exist_ok=True)
        (seed / path).write_text(text)
    git(["add", "-A"], seed)
    git(["commit", "-q", "-m", "main"], seed)
    git(["remote", "add", "origin", str(origin)], seed)
    git(["push", "-q", "origin", "main"], seed)
    git(["clone", "-q", str(origin), str(clone)], root)
    for config in (["user.email", "test@example.com"], ["user.name", "test"]):
        git(["config", *config], clone)
    git(["switch", "-q", "-c", "topic"], clone)
    return clone


def write(clone: Path, path: str, text: str):
    (clone / path).parent.mkdir(parents=True, exist_ok=True)
    (clone / path).write_text(text)


def run_lister(clone: Path, *extra):
    finished = subprocess.run([sys.executable, str(LISTER_PATH), "--checkout", str(clone), *extra],
                              capture_output=True, text=True)
    names = {tuple(line.split("\t")) for line in finished.stdout.splitlines() if line}
    return finished.returncode, names, finished.stderr


def names_only(listed):
    return {name for _, _, name in listed}


def run_hook(clone: Path, state_root: Path, payload: dict):
    environment = dict(os.environ, TMPDIR=str(state_root))
    body = dict({"session_id": "session-one", "cwd": str(clone)}, **payload)
    finished = subprocess.run([sys.executable, str(HOOK_PATH)], input=json.dumps(body),
                              capture_output=True, text=True, env=environment)
    context = ""
    if finished.stdout.strip():
        context = json.loads(finished.stdout)["hookSpecificOutput"]["additionalContext"]
    return finished.returncode, context


BASE_MAIN_FILES = {
    "README.md": "A project about `existing-tool-name` and agent-seat work.\n",
    "docs/project-glossary.md": "- **agent-seat** — an identity.\n",
    EXCEPTION_LIST_PATH: "# Ordinary hyphenated words\n\n- follow-up\n",
}


def case_python_function_used_from_another_file_is_listed(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    write(clone, "alpha.py", "def shared_helper():\n    return 1\n\ndef local_only():\n    return 2\n")
    write(clone, "beta.py", "from alpha import shared_helper\nprint(shared_helper())\n")
    code, listed, _ = run_lister(clone)
    check("exit 0 when names are found", code == 0)
    check("a new file path is listed", ("alpha.py", "file-path", "alpha.py") in listed, str(listed))
    check("a function another file uses is listed",
          ("alpha.py", "python-function", "shared_helper") in listed, str(listed))
    check("a function only its own file uses is not listed", "local_only" not in names_only(listed))


def case_function_listed_once_its_caller_appears(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    write(clone, "alpha.py", "def spawner():\n    return 1\n")
    _, before, _ = run_lister(clone)
    check("a function with no caller yet is not listed", "spawner" not in names_only(before))
    write(clone, "beta.py", "import alpha\nalpha.spawner()\n")
    _, after, _ = run_lister(clone)
    check("the same function is listed once a caller appears in another changed file",
          "spawner" in names_only(after), str(after))


def case_markdown_names(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    write(clone, "notes.md",
          "Run `brand-new-checker.py` beside `existing-tool-name`. A two-word name, a follow-up "
          "and an agent-seat.\n\n```\nfenced-code-word\n```\n")
    _, listed, _ = run_lister(clone)
    names = names_only(listed)
    check("a new backquoted name is listed", "brand-new-checker.py" in names, str(listed))
    check("a backquoted name main already has is not listed", "existing-tool-name" not in names)
    check("a made-up hyphenated phrase is listed", "two-word" in names, str(listed))
    check("a word on the ordinary hyphenated words list is not listed", "follow-up" not in names)
    check("a glossary term is not listed", "agent-seat" not in names)
    check("text inside a fenced code block is not listed", "fenced-code-word" not in names)


def case_new_glossary_entry(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    write(clone, "docs/project-glossary.md",
          "- **agent-seat** — an identity.\n- **worker-spawner** — starts workers.\n")
    _, listed, _ = run_lister(clone)
    check("a new glossary entry is listed",
          ("docs/project-glossary.md", "glossary-entry", "worker-spawner") in listed, str(listed))
    check("an existing glossary entry is not listed as a new entry",
          ("docs/project-glossary.md", "glossary-entry", "agent-seat") not in listed)


def case_branch_name(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    _, listed, _ = run_lister(clone, "--branch-name", "brand-new-topic")
    check("a new branch name is listed", ("", "branch", "brand-new-topic") in listed, str(listed))
    _, existing, _ = run_lister(clone, "--branch-name", "main")
    check("a branch origin already has is not listed", ("", "branch", "main") not in existing)


def case_nothing_new_is_silent(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    code, listed, _ = run_lister(clone)
    check("a branch with no changes lists nothing and exits 0", code == 0 and not listed, str(listed))


def case_git_failure_exits_nonzero(root):
    lonely = root / "lonely"
    git(["init", "-q", "-b", "main", str(lonely)], root)
    code, _, error = run_lister(lonely)
    check("a checkout with no origin/main exits 2", code == 2, f"exit {code}")
    check("the failure names the git command", "git " in error, error)


def case_hook_reports_once_per_session(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    state_root = root / "state"
    state_root.mkdir()
    write(clone, "alpha.py", "def shared_helper():\n    return 1\n")
    write(clone, "beta.py", "import alpha\nalpha.shared_helper()\n")
    code, first = run_hook(clone, state_root, {"tool_name": "Write", "tool_input": {"file_path": "beta.py"}})
    check("the hook exits 0", code == 0)
    check("the hook names the new function", "shared_helper" in first, first)
    check("the hook names the naming fresh-agent", "new-name-propose-and-check-fresh-agent" in first)
    _, second = run_hook(clone, state_root, {"tool_name": "Edit", "tool_input": {"file_path": "beta.py"}})
    check("the same names are not reported twice in one agent-session", second == "", second)
    _, other_session = run_hook(clone, state_root, {"tool_name": "Write", "session_id": "session-two",
                                                     "tool_input": {"file_path": "beta.py"}})
    check("another agent-session hears about them", "shared_helper" in other_session, other_session)


def case_hook_shell_commands(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    state_root = root / "state"
    state_root.mkdir()
    run_hook(clone, state_root, {"tool_name": "Bash", "tool_input": {"command": "ls"}})
    _, quiet = run_hook(clone, state_root, {"tool_name": "Bash", "tool_input": {"command": "ls"}})
    check("a shell command that changed nothing is silent", quiet == "", quiet)
    _, branch = run_hook(clone, state_root, {"tool_name": "Bash",
                                             "tool_input": {"command": "git switch -c brand-new-topic"}})
    check("a branch made with git switch -c is reported", "brand-new-topic" in branch, branch)
    write(clone, "made-by-shell.md", "A `shell-made-name` here.\n")
    _, shell_written = run_hook(clone, state_root, {"tool_name": "Bash",
                                                    "tool_input": {"command": "cat > made-by-shell.md"}})
    check("a file a shell command wrote is scanned", "shell-made-name" in shell_written, shell_written)


def case_hook_ignores_other_input(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    state_root = root / "state"
    state_root.mkdir()
    write(clone, "alpha.md", "A `brand-new-name` here.\n")
    _, other_tool = run_hook(clone, state_root, {"tool_name": "Read", "tool_input": {"file_path": "alpha.md"}})
    check("a tool that writes nothing is silent", other_tool == "", other_tool)
    finished = subprocess.run([sys.executable, str(HOOK_PATH)], input="not json",
                              capture_output=True, text=True)
    check("unreadable input exits 0 silently", finished.returncode == 0 and not finished.stdout.strip())


def words_on_list(text: str):
    return {line[2:].strip() for line in text.splitlines() if line.startswith("- ")}


def glossary_terms_in(text: str):
    return {match.group(1).strip().lower()
            for match in re.finditer(r"^- \*\*([^*]+)\*\*", text, re.M)}


def case_no_listed_word_is_a_glossary_term(root):
    planted = words_on_list("- follow-up\n- agent-seat\n") & glossary_terms_in("- **agent-seat** — x\n")
    check("the overlap check finds a word planted in both a list and a glossary", planted == {"agent-seat"})
    repository = Path(__file__).resolve().parent.parent
    listed = words_on_list((repository / EXCEPTION_LIST_PATH).read_text())
    check("the ordinary hyphenated words list is not empty", bool(listed))
    terms = set()
    for glossary in subprocess.run(["git", "ls-files", "*-glossary.md"], cwd=str(repository),
                                   capture_output=True, text=True, check=True).stdout.split():
        terms |= glossary_terms_in((repository / glossary).read_text())
    overlap = sorted(listed & terms)
    check("no word on the ordinary hyphenated words list is a term in a glossary", not overlap,
          ", ".join(overlap))


def main() -> int:
    cases = [case_no_listed_word_is_a_glossary_term,case_python_function_used_from_another_file_is_listed,
             case_function_listed_once_its_caller_appears, case_markdown_names,
             case_new_glossary_entry, case_branch_name, case_nothing_new_is_silent,
             case_git_failure_exits_nonzero, case_hook_reports_once_per_session,
             case_hook_shell_commands, case_hook_ignores_other_input]
    for case in cases:
        with tempfile.TemporaryDirectory() as directory:
            case(Path(directory).resolve())
    print()
    if FAILURES:
        print(f"{len(FAILURES)} case(s) failed")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
