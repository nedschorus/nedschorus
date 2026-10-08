#!/usr/bin/env python3
"""Tests for new-shared-names-in-changed-files-list.py and new-shared-names-reminder-hook.py.

Run: python3 scripts/new-shared-names-in-changed-files-list-test.py
Prints one line per case and exits non-zero if any case fails.

Most cases build a throwaway origin repository and a clone whose branch adds files,
then run the lister or the hook as a program against the clone; the cache, deadline
and pattern cases import them as modules. The first case is the positive one, so the
lister is shown able to report before any case asserts that it stays silent.
"""

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
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


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    environment = dict(os.environ, TMPDIR=str(clone.parent / "lister-tmp"))
    (clone.parent / "lister-tmp").mkdir(exist_ok=True)
    finished = subprocess.run([sys.executable, str(LISTER_PATH), "--checkout", str(clone), *extra],
                              capture_output=True, text=True, env=environment)
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
    "README.md": "A project about `existing-tool-name`, `review-cell-runner` and agent-seat work.\n",
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


def case_committed_changes_are_listed(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    write(clone, "committed-notes.md", "A `committed-only-name` here.\n")
    git(["add", "-A"], clone)
    git(["commit", "-q", "-m", "topic"], clone)
    _, listed, _ = run_lister(clone)
    check("a file committed on the branch is listed", ("committed-notes.md", "file-path", "committed-notes.md") in listed, str(listed))
    check("a name in a committed file is listed", "committed-only-name" in names_only(listed), str(listed))


def case_changed_file_on_main_is_not_a_new_path(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    write(clone, "README.md", BASE_MAIN_FILES["README.md"] + "More text.\n")
    _, listed, _ = run_lister(clone)
    check("an edited file main already has is not listed as a new file path",
          ("README.md", "file-path", "README.md") not in listed, str(listed))


def case_function_listed_once_its_caller_appears(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    write(clone, "alpha.py", "def spawner():\n    return 1\n")
    _, before, _ = run_lister(clone)
    check("a function with no caller yet is not listed", "spawner" not in names_only(before))
    write(clone, "beta.py", "import alpha\nalpha.spawner()\n")
    _, after, _ = run_lister(clone)
    check("the same function is listed once a caller appears in another changed file",
          "spawner" in names_only(after), str(after))


def case_same_name_defined_in_two_files_is_not_a_use(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    write(clone, "alpha.py", "LOCAL_LOG_PATH = 'a'\nprint(LOCAL_LOG_PATH)\n")
    write(clone, "beta.py", "LOCAL_LOG_PATH = 'b'\nprint(LOCAL_LOG_PATH)\n")
    _, listed, _ = run_lister(clone)
    check("a constant each file defines for itself is not listed", "LOCAL_LOG_PATH" not in names_only(listed), str(listed))


def case_one_word_constant_used_elsewhere_is_listed(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    write(clone, "alpha.py", "DEADLINE = 20\nX = 1\n")
    write(clone, "beta.py", "from alpha import DEADLINE, X\nprint(DEADLINE, X)\n")
    _, listed, _ = run_lister(clone)
    check("a one-word upper-case constant another file uses is listed", "DEADLINE" in names_only(listed), str(listed))
    check("a one-letter name is not listed", "X" not in names_only(listed))


def case_markdown_names(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    write(clone, "notes.md",
          "Run `brand-new-checker.py` beside `existing-tool-name`. A two-word name and a "
          "sentence that ends in other-thing.\n\n```\nfenced-code-word `fenced-backquoted-name`\n```\n"
          "Also `review-cell` beside the existing runner.\n")
    _, listed, _ = run_lister(clone)
    names = names_only(listed)
    check("a new backquoted name is listed", "brand-new-checker.py" in names, str(listed))
    check("a backquoted name main already has is not listed", "existing-tool-name" not in names)
    check("a made-up hyphenated phrase is listed", "two-word" in names, str(listed))
    check("a hyphenated phrase before a sentence-ending period is listed", "other-thing" in names, str(listed))
    check("text inside a fenced code block is not listed", "fenced-code-word" not in names)
    check("a backquoted name inside a fenced code block is not listed", "fenced-backquoted-name" not in names)
    check("a new name that main has only inside a longer name is listed", "review-cell" in names, str(listed))


def case_exemptions(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    write(clone, "docs/project-glossary.md",
          BASE_MAIN_FILES["docs/project-glossary.md"] + "- **fresh-term-x** — a new term.\n")
    write(clone, EXCEPTION_LIST_PATH, BASE_MAIN_FILES[EXCEPTION_LIST_PATH] + "- brand-old\n")
    write(clone, "usage.md", "We use fresh-term-x and a brand-old idea now.\n")
    _, listed, _ = run_lister(clone)
    phrases = {name for _, kind, name in listed if kind == "markdown-hyphenated-phrase"}
    check("a term in a glossary is not listed as a hyphenated phrase", "fresh-term-x" not in phrases, str(listed))
    check("a word on the ordinary hyphenated words list is not listed", "brand-old" not in phrases, str(listed))
    check("the new glossary entry itself is listed",
          ("docs/project-glossary.md", "glossary-entry", "fresh-term-x") in listed, str(listed))


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


def case_file_cache_and_deadline(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    write(clone, "notes.md", "A `cached-name-one` here.\n")
    lister = load_module("lister_for_cache_case", LISTER_PATH)
    lister.MAIN_TOKEN_CACHE_DIRECTORY = root / "token-cache"
    cache = {}
    first = lister.new_shared_names(clone, file_cache=cache)
    check("the first run lists the name", "cached-name-one" in names_only(first.names), str(first.names))
    check("the first run fills the file cache", "notes.md" in cache)

    def parse_must_not_run(*_arguments):
        raise AssertionError("an unchanged file was parsed again")
    lister.candidates_in_file = parse_must_not_run
    try:
        second = lister.new_shared_names(clone, file_cache=cache)
        reused = "cached-name-one" in names_only(second.names)
    except AssertionError:
        reused = False
    check("an unchanged file is not parsed again", reused)
    reported = lister.new_shared_names(clone, already_reported=frozenset(
        {"markdown-backquoted-name\tcached-name-one", "file-path\tnotes.md"}), file_cache=cache)
    check("names already reported are not returned", not reported.names, str(reported.names))
    stopped = lister.new_shared_names(clone, file_cache={}, deadline=time.monotonic() - 1)
    check("a passed deadline stops the scan and says so",
          not stopped.complete and stopped.files_scanned == 0 and stopped.files_total == 1,
          f"{stopped.files_scanned} of {stopped.files_total}")


def case_branch_creation_pattern():
    hook = load_module("hook_for_pattern_case", HOOK_PATH)
    expected = {
        "git switch -c topic-one": "topic-one",
        "git checkout -q -b topic-two": "topic-two",
        "git switch --quiet -c topic-three": "topic-three",
        "git -C /some/path checkout -b topic-four": "topic-four",
        "cd x && git checkout -b topic-five && ls": "topic-five",
        "git checkout main": None,
    }
    for command, branch in expected.items():
        match = hook.BRANCH_CREATION_PATTERN.search(command)
        check(f"branch creation pattern on {command!r}", (match.group(1) if match else None) == branch,
              str(match.group(1) if match else None))


def case_partial_scan_is_reported():
    hook = load_module("hook_for_partial_case", HOOK_PATH)

    class Partial:
        complete = False
        files_scanned = 3
        files_total = 9
    text = hook.reminder_text([("a.md", "markdown-backquoted-name", "some-name")], Partial())
    check("a partial scan says how far it got", "3 of 9" in text, text)


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
                                             "tool_input": {"command": "git checkout -q -b brand-new-topic"}})
    check("a branch made with options before -b is reported", "brand-new-topic" in branch, branch)
    write(clone, "made-by-shell.md", "A `shell-made-name` here.\n")
    _, shell_written = run_hook(clone, state_root, {"tool_name": "Bash",
                                                    "tool_input": {"command": "cat > made-by-shell.md"}})
    check("a file a shell command wrote is scanned", "shell-made-name" in shell_written, shell_written)
    time.sleep(0.01)
    write(clone, "made-by-shell.md", "A `shell-made-name` and `second-shell-name` here.\n")
    _, rewritten = run_hook(clone, state_root, {"tool_name": "Bash",
                                                "tool_input": {"command": "cat >> made-by-shell.md"}})
    check("a shell edit to an untracked file already scanned is scanned again", "second-shell-name" in rewritten, rewritten)


def case_hook_reports_failure_once(root):
    lonely = root / "lonely"
    git(["init", "-q", "-b", "main", str(lonely)], root)
    for config in (["user.email", "test@example.com"], ["user.name", "test"]):
        git(["config", *config], lonely)
    write(lonely, "a.md", "text\n")
    git(["add", "-A"], lonely)
    git(["commit", "-q", "-m", "one"], lonely)
    state_root = root / "state"
    state_root.mkdir()
    code, first = run_hook(lonely, state_root, {"tool_name": "Write", "tool_input": {"file_path": "a.md"}})
    check("a failing check exits 0", code == 0)
    check("a failing check tells the agent the check failed", "failed" in first and "origin/main" in first, first)
    _, second = run_hook(lonely, state_root, {"tool_name": "Write", "tool_input": {"file_path": "a.md"}})
    check("the same failure is told only once per agent-session", second == "", second)
    state = json.loads(next((state_root / "new-shared-names-reminder-hook-state").glob("session-one.json")).read_text())
    check("the worktree fingerprint is saved after a failure", bool(state.get("worktree_fingerprint")))


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


def main() -> int:
    cases = [case_python_function_used_from_another_file_is_listed,
             case_no_listed_word_is_a_glossary_term, case_committed_changes_are_listed,
             case_changed_file_on_main_is_not_a_new_path, case_function_listed_once_its_caller_appears,
             case_same_name_defined_in_two_files_is_not_a_use, case_one_word_constant_used_elsewhere_is_listed,
             case_markdown_names, case_exemptions, case_new_glossary_entry, case_branch_name,
             case_nothing_new_is_silent, case_git_failure_exits_nonzero, case_file_cache_and_deadline,
             case_hook_reports_once_per_session, case_hook_shell_commands,
             case_hook_reports_failure_once, case_hook_ignores_other_input]
    for case in cases:
        with tempfile.TemporaryDirectory() as directory:
            case(Path(directory).resolve())
    case_branch_creation_pattern()
    case_partial_scan_is_reported()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} case(s) failed")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
