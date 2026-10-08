#!/usr/bin/env python3
"""Tests for new-shared-names-in-changed-files-list.py and new-shared-names-reminder-hook.py.

Run: python3 scripts/new-shared-names-in-changed-files-list-test.py
Prints one line per case and exits non-zero if any case fails.

Most cases build a throwaway origin repository and a clone whose branch adds files,
then run the lister or the hook as a program against the clone; the cache, timeout
and reminder cases import them as modules. The first case is the positive one, so the
lister is shown able to report before any case asserts that it stays silent.
"""

import importlib.util
import io
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


def case_file_cache(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    write(clone, "notes.md", "A `cached-name-one` here.\n")
    lister = load_module("lister_for_cache_case", LISTER_PATH)
    lister.MAIN_TOKEN_CACHE_DIRECTORY = root / "token-cache"
    cache = {}
    first = lister.new_shared_names(clone, file_cache=cache)
    check("the first run lists the name", "cached-name-one" in names_only(first), str(first))
    check("the first run fills the file cache", "notes.md" in cache)

    def parse_must_not_run(*_arguments):
        raise AssertionError("an unchanged file was parsed again")
    lister.candidates_in_file = parse_must_not_run
    try:
        second = lister.new_shared_names(clone, file_cache=cache)
        reused = "cached-name-one" in names_only(second)
    except AssertionError:
        reused = False
    check("an unchanged file is not parsed again", reused)
    reported = lister.new_shared_names(clone, already_reported=frozenset(
        {"markdown-backquoted-name\tcached-name-one", "file-path\tnotes.md"}), file_cache=cache)
    check("names already reported are not returned", not reported, str(reported))


def case_file_only_main_has_counts_as_on_main(root):
    clone = make_clone(root, dict(BASE_MAIN_FILES, **{"tools/quiet-tool-file.py": "print(1)\n"}))
    write(clone, "mentions.md", "Run `quiet-tool-file.py` and the `tools/quiet-tool-file.py` copy.\n")
    _, listed, _ = run_lister(clone)
    names = names_only(listed)
    check("a file name main has only as a file is not listed", "quiet-tool-file.py" not in names, str(listed))
    check("a path main has only as a file is not listed", "tools/quiet-tool-file.py" not in names, str(listed))


def state_file_bytes(state_root: Path, session_id: str) -> bytes:
    return (state_root / "new-shared-names-reminder-hook-state" / f"{session_id}.json").read_bytes()


def case_hook_reports_this_worktrees_new_branch(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    state_root = root / "state"
    state_root.mkdir()
    _, first = run_hook(clone, state_root, {"tool_name": "Bash", "tool_input": {"command": "git switch -c topic"}})
    check("a branch made by the first hooked call of an agent-session is reported",
          "  topic (branch)" in first, first)
    before = state_file_bytes(state_root, "session-one")
    _, quiet = run_hook(clone, state_root, {"tool_name": "Bash", "tool_input": {"command": "ls"}})
    check("a shell command that changed nothing is silent", quiet == "", quiet)
    check("a shell command that changed nothing leaves the state file as it was",
          state_file_bytes(state_root, "session-one") == before)
    commands = {
        "git branch side-topic": None,
        "env -u GH_TOKEN git switch -q -c env-switched-topic": "env-switched-topic",
        "git checkout -q --detach": None,
        "git checkout -q main": None,
        "git -c user.name='A;B' checkout -q -b quoted-option-topic 2>&1 | cat": "quoted-option-topic",
    }
    for command, branch in commands.items():
        subprocess.run(command, shell=True, cwd=str(clone), capture_output=True)
        _, context = run_hook(clone, state_root, {"tool_name": "Bash", "tool_input": {"command": command}})
        reported = set(re.findall(r"^  (\S+) \(branch\)", context, re.M))
        expected = {branch} if branch else set()
        check(f"after {command!r} the hook reports {expected or 'no branch'}", reported == expected, context)


def case_branch_origin_already_has_is_not_reported(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    git(["switch", "-q", "-c", "pushed-topic"], clone)
    git(["push", "-q", "-u", "origin", "pushed-topic"], clone)
    state_root = root / "state"
    state_root.mkdir()
    code, context = run_hook(clone, state_root, {"tool_name": "Bash", "session_id": "session-on-pushed-branch",
                                                 "tool_input": {"command": "git push -u origin pushed-topic"}})
    check("on a branch other than main that origin already has, the hook exits 0 and says nothing",
          code == 0 and context == "", context)


def case_two_worktrees_each_report_their_own_branch(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    second = root / "second-worktree"
    git(["worktree", "add", "-q", "-b", "second-worktree-topic", str(second)], clone)
    state_root = root / "state"
    state_root.mkdir()
    _, first = run_hook(clone, state_root, {"tool_name": "Bash", "session_id": "session-a",
                                            "tool_input": {"command": "ls"}})
    _, other = run_hook(second, state_root, {"tool_name": "Bash", "session_id": "session-b",
                                             "tool_input": {"command": "ls"}})
    check("the first worktree's agent-session reports only its own branch",
          set(re.findall(r"^  (\S+) \(branch\)", first, re.M)) == {"topic"}, first)
    check("the second worktree's agent-session reports only its own branch",
          set(re.findall(r"^  (\S+) \(branch\)", other, re.M)) == {"second-worktree-topic"}, other)


def run_hook_in_process(hook, root: Path, clone: Path, payload: dict, planted_failures: dict):
    """Run the hook's main() with git subcommands named in planted_failures failing; return (exit, context).

    planted_failures maps a git subcommand to a CompletedProcess exit code, or to "timeout".
    """
    real_run = subprocess.run

    def run_with_planted_failures(arguments, **options):
        planted = planted_failures.get(arguments[1]) if len(arguments) > 1 and arguments[0] == "git" else None
        if planted == "timeout":
            raise subprocess.TimeoutExpired(arguments, 10)
        if planted is not None:
            return subprocess.CompletedProcess(arguments, planted, "", "fatal: planted failure\n")
        return real_run(arguments, **options)
    hook.STATE_DIRECTORY = root / "state"
    hook.subprocess.run = run_with_planted_failures
    # The lister the hook loads keeps its token cache under the temporary directory; keep it inside this case.
    original_tempdir = tempfile.tempdir
    (root / "tmp").mkdir(exist_ok=True)
    tempfile.tempdir = str(root / "tmp")
    body = json.dumps(dict({"session_id": "session-one", "cwd": str(clone)}, **payload))
    original_stdin, original_stdout = sys.stdin, sys.stdout
    sys.stdin, sys.stdout = io.StringIO(body), io.StringIO()
    try:
        code = hook.main()
        output = sys.stdout.getvalue()
    finally:
        sys.stdin, sys.stdout = original_stdin, original_stdout
        hook.subprocess.run = real_run
        tempfile.tempdir = original_tempdir
    context = json.loads(output)["hookSpecificOutput"]["additionalContext"] if output.strip() else ""
    return code, context


def case_branch_check_failure_is_told_and_the_file_check_still_runs(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    write(clone, "after-failure.md", "A `still-checked-name` here.\n")
    hook = load_module("hook_for_branch_failure_case", HOOK_PATH)
    code, context = run_hook_in_process(hook, root, clone, {"tool_name": "Write",
                                        "tool_input": {"file_path": "after-failure.md"}}, {"symbolic-ref": 128})
    check("a failing branch check exits 0", code == 0)
    check("a failing branch check is told to the agent", "git symbolic-ref exited 128" in context, context)
    check("the file-name check still runs after a failing branch check", "still-checked-name" in context, context)


def case_remote_branch_lookup_failure_is_told_and_no_branch_reported(root):
    for planted, expected_text in ((128, "git show-ref exited 128"), ("timeout", "git show-ref timed out")):
        case_root = root / f"lookup-{planted}"
        case_root.mkdir()
        clone = make_clone(case_root, BASE_MAIN_FILES)
        hook = load_module(f"hook_for_lookup_failure_{planted}", HOOK_PATH)
        code, context = run_hook_in_process(hook, case_root, clone, {"tool_name": "Bash",
                                            "tool_input": {"command": "ls"}}, {"show-ref": planted})
        check(f"a remote-branch lookup that fails ({planted}) is told to the agent",
              code == 0 and expected_text in context, context)
        check(f"a remote-branch lookup that fails ({planted}) reports no branch", "(branch)" not in context, context)


def case_branch_check_failure_on_a_quiet_shell_call_is_told(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    hook = load_module("hook_for_quiet_failure_case", HOOK_PATH)
    run_hook_in_process(hook, root, clone, {"tool_name": "Bash", "tool_input": {"command": "ls"}}, {})
    _, quiet = run_hook_in_process(hook, root, clone, {"tool_name": "Bash", "tool_input": {"command": "ls"}}, {})
    check("a quiet shell call with a working branch check is silent", quiet == "", quiet)
    _, context = run_hook_in_process(hook, root, clone, {"tool_name": "Bash", "tool_input": {"command": "ls"}},
                                     {"symbolic-ref": 128})
    check("a branch check that fails during a quiet shell call is still told to the agent",
          "git symbolic-ref exited 128" in context, context)


def case_reminder_is_capped():
    hook = load_module("hook_for_cap_case", HOOK_PATH)
    many = [("a.md", "markdown-backquoted-name", f"listed-name-{index:02d}") for index in range(35)]
    text = hook.reminder_text(many)
    check("the reminder lists the first 30 names", "listed-name-29" in text and "listed-name-30" not in text, text)
    check("the reminder says how many more and how to see them",
          "and 5 more" in text and "new-shared-names-in-changed-files-list.py" in text, text)
    check("the more-names line gives a command that runs the lister with python3",
          "python3 scripts/new-shared-names-in-changed-files-list.py" in text, text)
    few = hook.reminder_text(many[:3])
    check("a short reminder has no more-names line", " more," not in few, few)
    exactly_at_cap = hook.reminder_text(many[:30])
    check("a reminder of exactly 30 names has no more-names line", " more," not in exactly_at_cap, exactly_at_cap)


def case_timeout_failure_text_is_stable(root):
    lister = load_module("lister_for_timeout_case", LISTER_PATH)

    def time_out(arguments, **_options):
        raise subprocess.TimeoutExpired(arguments, 0.5)
    real_run = subprocess.run
    lister.subprocess.run = time_out
    texts = set()
    try:
        for pending_names in (["first-name"], ["first-name", "second-name", "third-name"]):
            arguments = ["grep", "--untracked", "-n", "-o", "-w", "-F"]
            for name in pending_names:
                arguments += ["-e", name]
            try:
                lister.git(arguments, root)
            except lister.GitFailure as failure:
                texts.add(str(failure))
    finally:
        lister.subprocess.run = real_run
    check("a git timeout fails with the same short text whatever the arguments",
          texts == {"git grep timed out"}, str(texts))


def case_hook_shows_names_past_the_cap_later(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    state_root = root / "state"
    state_root.mkdir()
    write(clone, "many.md", "".join(f"Name `capped-name-{index:02d}` here.\n" for index in range(35)))
    _, first = run_hook(clone, state_root, {"tool_name": "Write", "tool_input": {"file_path": "many.md"}})
    shown_first = set(re.findall(r"capped-name-\d\d", first))
    check("the first reminder shows 30 names: the new branch, the new file path, then 28 of the 35 backquoted names",
          len(shown_first) == 28 and "topic (branch)" in first and "many.md (file-path)" in first,
          str(len(shown_first)))
    _, second = run_hook(clone, state_root, {"tool_name": "Edit", "tool_input": {"file_path": "many.md"}})
    shown_second = set(re.findall(r"capped-name-\d\d", second))
    check("the next reminder shows the names past the cap",
          shown_first | shown_second == {f"capped-name-{index:02d}" for index in range(35)}
          and not shown_first & shown_second, f"{len(shown_first)} then {len(shown_second)}")


def case_hook_reports_once_per_worktree(root):
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
    git_directory = subprocess.run(["git", "rev-parse", "--absolute-git-dir"], cwd=str(clone), check=True,
                                   capture_output=True, text=True).stdout.strip()
    record = Path(git_directory) / "new-shared-names-reported.json"
    check("the reported names are kept in the worktree's own git directory, under its branch",
          "python-function\tshared_helper" in json.loads(record.read_text()).get("topic", []), str(record))
    _, later_session = run_hook(clone, state_root, {"tool_name": "Write", "session_id": "session-two",
                                                     "tool_input": {"file_path": "beta.py"}})
    check("a later agent-session in the same worktree is not told the same names again",
          later_session == "", later_session)
    write(clone, "gamma.py", "import alpha\ndef second_helper():\n    return alpha.shared_helper()\n")
    write(clone, "delta.py", "import gamma\ngamma.second_helper()\n")
    _, later_new = run_hook(clone, state_root, {"tool_name": "Write", "session_id": "session-two",
                                                 "tool_input": {"file_path": "delta.py"}})
    check("the later agent-session is told only the names that are new to the worktree",
          "second_helper" in later_new and "shared_helper (" not in later_new, later_new)


def record_path_of(clone: Path) -> Path:
    git_directory = subprocess.run(["git", "rev-parse", "--absolute-git-dir"], cwd=str(clone), check=True,
                                   capture_output=True, text=True).stdout.strip()
    return Path(git_directory) / "new-shared-names-reported.json"


def case_new_branch_is_told_a_name_again_and_gone_branches_are_dropped(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    state_root = root / "state"
    state_root.mkdir()
    write(clone, "alpha.py", "def shared_helper():\n    return 1\n")
    write(clone, "beta.py", "import alpha\nalpha.shared_helper()\n")
    _, first = run_hook(clone, state_root, {"tool_name": "Write", "tool_input": {"file_path": "beta.py"}})
    check("the name is told on the first branch", "shared_helper" in first, first)
    git(["stash", "-q", "-u"], clone)
    git(["switch", "-q", "main"], clone)
    git(["branch", "-q", "-D", "topic"], clone)
    git(["switch", "-q", "-c", "later-topic"], clone)
    git(["stash", "pop", "-q"], clone)
    _, again = run_hook(clone, state_root, {"tool_name": "Write", "tool_input": {"file_path": "beta.py"}})
    check("a later branch that adds the same name is told it again", "shared_helper" in again, again)
    record = json.loads(record_path_of(clone).read_text())
    check("the abandoned branch's entries are dropped from the record",
          "topic" not in record and "later-topic" in record, str(sorted(record)))


def case_unreadable_record_is_told_and_names_are_told_again(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    state_root = root / "state"
    state_root.mkdir()
    record_path_of(clone).write_text("{not json")
    write(clone, "alpha.py", "def shared_helper():\n    return 1\n")
    write(clone, "beta.py", "import alpha\nalpha.shared_helper()\n")
    code, context = run_hook(clone, state_root, {"tool_name": "Write", "tool_input": {"file_path": "beta.py"}})
    check("an unreadable record exits 0", code == 0)
    check("an unreadable record is told to the agent",
          "could not be read (not valid JSON)" in context, context)
    check("the names are still listed after an unreadable record", "shared_helper" in context, context)
    check("the record is rewritten as valid JSON",
          isinstance(json.loads(record_path_of(clone).read_text()), dict))
    unreadable = record_path_of(clone).with_name("new-shared-names-reported.json.unreadable")
    check("the unreadable record is moved aside, unchanged, to inspect",
          unreadable.exists() and unreadable.read_text() == "{not json", str(unreadable))
    check("the agent is told where the unreadable record was moved", str(unreadable) in context, context)
    record_path_of(clone).write_text("{second bad record")
    write(clone, "gamma.py", "import alpha\ndef second_helper():\n    return alpha.shared_helper()\n")
    write(clone, "delta.py", "import gamma\ngamma.second_helper()\n")
    run_hook(clone, state_root, {"tool_name": "Write", "session_id": "session-two",
                                 "tool_input": {"file_path": "delta.py"}})
    check("a later unreadable record replaces the older moved-aside one",
          unreadable.read_text() == "{second bad record", unreadable.read_text())


def case_unreadable_record_that_cannot_be_moved_stays_and_is_told(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    state_root = root / "state"
    state_root.mkdir()
    record = record_path_of(clone)
    record.write_text("{not json")
    blocking_directory = record.with_name("new-shared-names-reported.json.unreadable")
    blocking_directory.mkdir()
    (blocking_directory / "keep").write_text("a non-empty directory cannot be replaced by a file")
    write(clone, "alpha.py", "def shared_helper():\n    return 1\n")
    write(clone, "beta.py", "import alpha\nalpha.shared_helper()\n")
    code, context = run_hook(clone, state_root, {"tool_name": "Write", "tool_input": {"file_path": "beta.py"}})
    check("an unreadable record that cannot be moved exits 0", code == 0)
    check("an unreadable record that cannot be moved is told, with both reasons, and not as moved",
          "could not be read (not valid JSON)" in context and "could not be moved to" in context
          and "stays in place" in context and "was moved" not in context, context)
    check("the names are still listed when the record cannot be moved", "shared_helper" in context, context)
    check("the unreadable record stays in place, unchanged", record.read_text() == "{not json")


def case_write_failure_after_moving_an_unreadable_record_aside_tells_both(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    record = record_path_of(clone)
    record.write_text("{not json")
    unreadable = record.with_name("new-shared-names-reported.json.unreadable")
    write(clone, "alpha.py", "def shared_helper():\n    return 1\n")
    write(clone, "beta.py", "import alpha\nalpha.shared_helper()\n")
    hook = load_module("hook_for_write_failure_after_move_case", HOOK_PATH)
    real_replace = hook.os.replace

    def replace_failing_with_no_space_onto_the_record(source, destination, *arguments, **options):
        # Moving the unreadable record aside succeeds; only writing the new record over it fails.
        if Path(destination).name == record.name:
            raise OSError(28, "No space left on device")
        return real_replace(source, destination, *arguments, **options)
    hook.os.replace = replace_failing_with_no_space_onto_the_record
    try:
        code, context = run_hook_in_process(hook, root, clone, {"tool_name": "Write",
                                            "tool_input": {"file_path": "beta.py"}}, {})
    finally:
        hook.os.replace = real_replace
    check("a write that fails after moving an unreadable record aside exits 0", code == 0)
    check("the agent is told the unreadable record was moved, with where",
          "could not be read (not valid JSON)" in context and f"was moved to {unreadable}" in context, context)
    check("the agent is also told the new record could not be written",
          "could not be written (No space left on device)" in context, context)
    check("the moved record holds the original bytes", unreadable.read_text() == "{not json")


def case_each_record_notice_is_told_once_per_agent_session(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    record_path_of(clone).write_text(json.dumps({"topic": ["branch\ttopic"]}))
    hook = load_module("hook_for_notice_once_case", HOOK_PATH)
    _, first = run_hook_in_process(hook, root, clone, {"tool_name": "Write", "tool_input": {"file_path": "x"}},
                                   {"for-each-ref": 128})
    _, second = run_hook_in_process(hook, root, clone, {"tool_name": "Write", "tool_input": {"file_path": "x"}},
                                    {"for-each-ref": 128})
    check("the branch-list notice is told on the first call", "git for-each-ref failed" in first, first)
    check("the same notice is not told again later in the same agent-session",
          "git for-each-ref failed" not in second, second)


def case_branch_list_failure_with_nothing_new_to_record_is_told(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    # This worktree's branch is already reported and nothing has changed, so the writer returns early.
    record_path_of(clone).write_text(json.dumps({"topic": ["branch\ttopic"]}))
    before = record_path_of(clone).read_bytes()
    hook = load_module("hook_for_branch_list_failure_nothing_new_case", HOOK_PATH)
    code, context = run_hook_in_process(hook, root, clone, {"tool_name": "Bash",
                                        "tool_input": {"command": "ls"}}, {"for-each-ref": 128})
    check("a failing branch list with nothing new to record exits 0", code == 0)
    check("a failing branch list with nothing new to record is told to the agent",
          "git for-each-ref failed" in context, context)
    check("the record is not rewritten when nothing changes", record_path_of(clone).read_bytes() == before)


def case_missing_record_is_silent_about_the_record(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    state_root = root / "state"
    state_root.mkdir()
    check("a fresh worktree has no record", not record_path_of(clone).exists())
    write(clone, "alpha.py", "def shared_helper():\n    return 1\n")
    write(clone, "beta.py", "import alpha\nalpha.shared_helper()\n")
    _, context = run_hook(clone, state_root, {"tool_name": "Write", "tool_input": {"file_path": "beta.py"}})
    check("a missing record is the normal first run and says nothing about the record",
          "failed" not in context and "shared_helper" in context, context)


def case_failed_write_after_a_good_read_is_told_and_leaves_no_temporary_file(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    state_root = root / "state"
    state_root.mkdir()
    write(clone, "alpha.py", "def shared_helper():\n    return 1\n")
    write(clone, "beta.py", "import alpha\nalpha.shared_helper()\n")
    run_hook(clone, state_root, {"tool_name": "Write", "tool_input": {"file_path": "beta.py"}})
    record = record_path_of(clone)
    before = record.read_bytes()
    write(clone, "gamma.py", "import alpha\ndef second_helper():\n    return alpha.shared_helper()\n")
    write(clone, "delta.py", "import gamma\ngamma.second_helper()\n")
    hook = load_module("hook_for_failed_write_case", HOOK_PATH)
    real_replace = hook.os.replace

    def replace_failing_for_the_record(source, destination, *arguments, **options):
        if Path(destination).name == record.name:
            raise PermissionError(13, "Permission denied")
        return real_replace(source, destination, *arguments, **options)
    hook.os.replace = replace_failing_for_the_record
    try:
        code, context = run_hook_in_process(hook, root, clone, {"tool_name": "Write",
                                            "tool_input": {"file_path": "delta.py"}}, {})
    finally:
        hook.os.replace = real_replace
    check("a write that fails after a good read exits 0", code == 0)
    check("a write that fails after a good read is told to the agent",
          "could not be written (Permission denied)" in context, context)
    check("the names are still listed when the write fails", "second_helper" in context, context)
    check("the record is left as it was", record.read_bytes() == before)
    leftovers = [path.name for path in record.parent.iterdir() if path.name.endswith(".partial")]
    check("a failed write removes its temporary file", leftovers == [], str(leftovers))


def case_branch_recorded_by_a_concurrent_run_while_scanning_survives(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    write(clone, "alpha.py", "def shared_helper():\n    return 1\n")
    write(clone, "beta.py", "import alpha\nalpha.shared_helper()\n")
    hook = load_module("hook_for_concurrent_branch_case", HOOK_PATH)
    record = record_path_of(clone)
    second = root / "second-worktree"
    real_load_lister = hook.load_lister

    def lister_that_lets_a_second_run_record_meanwhile():
        lister = real_load_lister()
        real_new_shared_names = lister.new_shared_names

        def new_shared_names_with_a_concurrent_run(*arguments, **options):
            # While the first run scans, a second run creates a branch and records a name on it.
            git(["worktree", "add", "-q", "-b", "concurrent-topic", str(second)], clone)
            hook.reported_names_record_merge_prune_and_write(
                record, "concurrent-topic", {"python-function\tconcurrent_helper"}, second)
            return real_new_shared_names(*arguments, **options)
        lister.new_shared_names = new_shared_names_with_a_concurrent_run
        return lister
    hook.load_lister = lister_that_lets_a_second_run_record_meanwhile
    code, context = run_hook_in_process(hook, root, clone, {"tool_name": "Write",
                                        "tool_input": {"file_path": "beta.py"}}, {})
    stored = json.loads(record.read_text())
    check("the first run exits 0 and lists its names", code == 0 and "shared_helper" in context, context)
    check("the first run's names are recorded under its branch",
          "python-function\tshared_helper" in stored.get("topic", []), str(stored))
    check("a branch another run created and recorded while this run scanned is not dropped",
          stored.get("concurrent-topic") == ["python-function\tconcurrent_helper"], str(stored))


def case_failed_prune_write_with_no_new_names_is_told(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    record = record_path_of(clone)
    # The worktree's own branch is already reported, so this run has no new names and writes only to prune.
    record.write_text(json.dumps({"long-gone-topic": ["python-function\told_name"], "topic": ["branch\ttopic"]}))
    hook = load_module("hook_for_failed_prune_case", HOOK_PATH)
    real_replace = hook.os.replace

    def replace_failing_for_the_record(source, destination, *arguments, **options):
        if Path(destination).name == record.name:
            raise PermissionError(13, "Permission denied")
        return real_replace(source, destination, *arguments, **options)
    hook.os.replace = replace_failing_for_the_record
    try:
        code, context = run_hook_in_process(hook, root, clone, {"tool_name": "Bash",
                                            "tool_input": {"command": "ls"}}, {})
    finally:
        hook.os.replace = real_replace
    check("a prune write that fails exits 0", code == 0)
    check("a prune write that fails, in a run with no new names, is told to the agent",
          "could not be written (Permission denied)" in context, context)
    check("the record is left as it was after a failed prune",
          "long-gone-topic" in json.loads(record.read_text()))


def case_record_that_is_not_utf8_is_told(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    state_root = root / "state"
    state_root.mkdir()
    record_path_of(clone).write_bytes(b'{"topic": ["\xff\xfe"]}')
    write(clone, "alpha.py", "def shared_helper():\n    return 1\n")
    write(clone, "beta.py", "import alpha\nalpha.shared_helper()\n")
    code, context = run_hook(clone, state_root, {"tool_name": "Write", "tool_input": {"file_path": "beta.py"}})
    check("a record that is not UTF-8 exits 0", code == 0)
    check("a record that is not UTF-8 is told to the agent",
          "could not be read (not valid UTF-8)" in context, context)
    check("the names are still listed after a record that is not UTF-8", "shared_helper" in context, context)


def case_local_branch_list_failure_is_told_and_keeps_the_record(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    record_path_of(clone).write_text(json.dumps({"long-gone-topic": ["python-function\told_name"]}))
    write(clone, "alpha.py", "def shared_helper():\n    return 1\n")
    write(clone, "beta.py", "import alpha\nalpha.shared_helper()\n")
    hook = load_module("hook_for_branch_list_failure_case", HOOK_PATH)
    code, context = run_hook_in_process(hook, root, clone, {"tool_name": "Write",
                                        "tool_input": {"file_path": "beta.py"}}, {"for-each-ref": 128})
    check("a failing branch list exits 0", code == 0)
    check("a failing branch list is told to the agent", "git for-each-ref failed" in context, context)
    check("the names are still listed when the branch list fails", "shared_helper" in context, context)
    check("a failing branch list keeps every branch's entries",
          "long-gone-topic" in json.loads(record_path_of(clone).read_text()))


def case_branch_list_failure_inside_the_final_write_is_told(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    record_path_of(clone).write_text(json.dumps({"long-gone-topic": ["python-function\told_name"]}))
    write(clone, "alpha.py", "def shared_helper():\n    return 1\n")
    write(clone, "beta.py", "import alpha\nalpha.shared_helper()\n")
    hook = load_module("hook_for_late_branch_list_failure_case", HOOK_PATH)
    real_local_branches = hook.local_branches
    calls = []

    def branch_list_that_fails_after_the_first_read(checkout):
        calls.append(checkout)
        return real_local_branches(checkout) if len(calls) == 1 else None
    hook.local_branches = branch_list_that_fails_after_the_first_read
    code, context = run_hook_in_process(hook, root, clone, {"tool_name": "Write",
                                        "tool_input": {"file_path": "beta.py"}}, {})
    stored = json.loads(record_path_of(clone).read_text())
    check("the branch list is read inside the lock once per write: the prune, then the final write",
          len(calls) == 2, str(len(calls)))
    check("a branch list that fails only inside the final write is told to the agent",
          code == 0 and "git for-each-ref failed" in context, context)
    check("the final write still records this run's names when the branch list fails",
          "python-function\tshared_helper" in stored.get("topic", []), str(stored))


def case_same_branch_name_recreated_is_told_names_again(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    state_root = root / "state"
    state_root.mkdir()
    write(clone, "alpha.py", "def shared_helper():\n    return 1\n")
    write(clone, "beta.py", "import alpha\nalpha.shared_helper()\n")
    _, first = run_hook(clone, state_root, {"tool_name": "Write", "tool_input": {"file_path": "beta.py"}})
    check("the name is told on topic", "shared_helper" in first, first)
    for command in (["stash", "-q", "-u"], ["switch", "-q", "main"], ["branch", "-q", "-D", "topic"]):
        git(command, clone)
        run_hook(clone, state_root, {"tool_name": "Bash", "tool_input": {"command": "git " + " ".join(command)}})
    check("deleting topic drops its entries even with no new names to write",
          "topic" not in json.loads(record_path_of(clone).read_text()))
    git(["switch", "-q", "-c", "topic"], clone)
    git(["stash", "pop", "-q"], clone)
    _, again = run_hook(clone, state_root, {"tool_name": "Write", "tool_input": {"file_path": "beta.py"}})
    check("a recreated branch of the same name is told the name again", "shared_helper" in again, again)


def case_switch_to_a_branch_origin_has_lists_its_names(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    git(["branch", "-q", "pushed-topic"], clone)
    git(["push", "-q", "origin", "pushed-topic"], clone)
    state_root = root / "state"
    state_root.mkdir()
    write(clone, "alpha.py", "def shared_helper():\n    return 1\n")
    write(clone, "beta.py", "import alpha\nalpha.shared_helper()\n")
    _, first = run_hook(clone, state_root, {"tool_name": "Write", "tool_input": {"file_path": "beta.py"}})
    check("the name is told on topic", "shared_helper" in first, first)
    git(["switch", "-q", "pushed-topic"], clone)
    _, after_switch = run_hook(clone, state_root, {"tool_name": "Bash",
                                                   "tool_input": {"command": "git switch pushed-topic"}})
    check("a switch to another branch at the same commit, with the same changes, lists that branch's names",
          "shared_helper" in after_switch, after_switch)


OVERLAPPING_WRITER_SCRIPT = """
import importlib.util, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("hook", sys.argv[1])
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)
record = Path(sys.argv[2])
writer = sys.argv[3]
checkout = Path(sys.argv[4])
for index in range(40):
    hook.reported_names_record_merge_prune_and_write(record, "topic", {f"python-function\\t{writer}_{index}"}, checkout)
"""


def case_overlapping_writers_never_leave_invalid_json_and_keep_every_name(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    record = record_path_of(clone)
    hook_path = Path(__file__).resolve().parent / "new-shared-names-reminder-hook.py"
    writers = [subprocess.Popen([sys.executable, "-c", OVERLAPPING_WRITER_SCRIPT, str(hook_path), str(record),
                                 f"writer{number}", str(clone)]) for number in range(4)]
    invalid_reads = 0
    reads = 0
    while any(writer.poll() is None for writer in writers):
        try:
            json.loads(record.read_text())
        except FileNotFoundError:
            continue
        except ValueError:
            invalid_reads += 1
        reads += 1
    codes = [writer.wait() for writer in writers]
    check("the overlapping writers all exit 0", codes == [0, 0, 0, 0], str(codes))
    check("no read of the record during overlapping writes is invalid JSON",
          invalid_reads == 0, f"{invalid_reads} invalid of {reads}")
    stored = set(json.loads(record.read_text()).get("topic", []))
    expected = {f"python-function\twriter{number}_{index}" for number in range(4) for index in range(40)}
    check("every writer's names are kept", stored == expected, f"{len(stored)} of {len(expected)}")
    leftovers = [path.name for path in record.parent.iterdir() if path.name.endswith(".partial")]
    check("no temporary files are left behind", leftovers == [], str(leftovers))


def case_two_worktrees_keep_separate_records(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    second = root / "second-worktree"
    git(["worktree", "add", "-q", "-b", "second-worktree-topic", str(second)], clone)
    state_root = root / "state"
    state_root.mkdir()
    for worktree in (clone, second):
        write(worktree, "alpha.py", "def shared_helper():\n    return 1\n")
        write(worktree, "beta.py", "import alpha\nalpha.shared_helper()\n")
    _, first = run_hook(clone, state_root, {"tool_name": "Write", "session_id": "session-a",
                                            "tool_input": {"file_path": "beta.py"}})
    _, other = run_hook(second, state_root, {"tool_name": "Write", "session_id": "session-b",
                                             "tool_input": {"file_path": "beta.py"}})
    check("the first worktree is told its new function", "shared_helper" in first, first)
    check("a second worktree of the same clone is told the same name, from its own record",
          "shared_helper" in other, other)


def case_hook_shell_commands(root):
    clone = make_clone(root, BASE_MAIN_FILES)
    state_root = root / "state"
    state_root.mkdir()
    run_hook(clone, state_root, {"tool_name": "Bash", "tool_input": {"command": "ls"}})
    _, quiet = run_hook(clone, state_root, {"tool_name": "Bash", "tool_input": {"command": "ls"}})
    check("a second shell command that changed nothing is silent", quiet == "", quiet)
    subprocess.run(["git", "checkout", "-q", "-b", "brand-new-topic"], cwd=str(clone), check=True, capture_output=True)
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
    check("the failure text is short", len(first) < 800, str(len(first)))
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
             case_nothing_new_is_silent, case_git_failure_exits_nonzero, case_file_cache, case_file_only_main_has_counts_as_on_main,
             case_timeout_failure_text_is_stable, case_hook_shows_names_past_the_cap_later,
             case_hook_reports_this_worktrees_new_branch, case_two_worktrees_each_report_their_own_branch,
             case_branch_origin_already_has_is_not_reported,
             case_branch_check_failure_is_told_and_the_file_check_still_runs,
             case_remote_branch_lookup_failure_is_told_and_no_branch_reported,
             case_branch_check_failure_on_a_quiet_shell_call_is_told,
             case_hook_reports_once_per_worktree, case_two_worktrees_keep_separate_records,
             case_new_branch_is_told_a_name_again_and_gone_branches_are_dropped,
             case_unreadable_record_is_told_and_names_are_told_again,
             case_missing_record_is_silent_about_the_record,
             case_failed_write_after_a_good_read_is_told_and_leaves_no_temporary_file,
             case_branch_recorded_by_a_concurrent_run_while_scanning_survives,
             case_failed_prune_write_with_no_new_names_is_told,
             case_record_that_is_not_utf8_is_told, case_local_branch_list_failure_is_told_and_keeps_the_record,
             case_branch_list_failure_inside_the_final_write_is_told,
             case_branch_list_failure_with_nothing_new_to_record_is_told,
             case_unreadable_record_that_cannot_be_moved_stays_and_is_told,
             case_write_failure_after_moving_an_unreadable_record_aside_tells_both,
             case_each_record_notice_is_told_once_per_agent_session,
             case_same_branch_name_recreated_is_told_names_again, case_switch_to_a_branch_origin_has_lists_its_names,
             case_overlapping_writers_never_leave_invalid_json_and_keep_every_name,
             case_hook_shell_commands,
             case_hook_reports_failure_once, case_hook_ignores_other_input]
    for case in cases:
        with tempfile.TemporaryDirectory() as directory:
            case(Path(directory).resolve())
    case_reminder_is_capped()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} case(s) failed")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
