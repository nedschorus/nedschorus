#!/usr/bin/env python3
"""Tests for obsolete-file-edit-warning-hook.py.

Run: python3 scripts/obsolete-file-edit-warning-hook-test.py
Prints one line per case and exits non-zero if any case fails. Every case
runs against throwaway repositories under a temporary directory: an "origin"
reached by path, and a clone on a topic branch standing in for a seat's
checkout.

Two things are asserted by INSTRUMENT rather than by inspection, because
neither shows in the hook's output: that the second warning about the same
state costs no `git diff` (a `git` shim first on PATH records every call the
hook makes), and that nothing in this hook ever fetches. Both are properties
of a hook that runs at every edit an agent makes.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name("obsolete-file-edit-warning-hook.py")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def git(arguments, cwd: Path):
    return subprocess.run(["git", *arguments], cwd=str(cwd),
                          capture_output=True, text=True, check=False)


def configure_identity(repository: Path):
    git(["config", "user.email", "test@example.invalid"], repository)
    git(["config", "user.name", "obsolete-file-edit-warning test"], repository)


def commit_file(repository: Path, name: str, content: str, message: str):
    (repository / name).parent.mkdir(parents=True, exist_ok=True)
    (repository / name).write_text(content, encoding="utf-8")
    git(["add", name], repository)
    git(["commit", "-q", "-m", message], repository)


def hook_payload(cwd, file_path, tool_name="Edit") -> dict:
    """The shape a PostToolUse hook is handed: the session's own cwd, the
    tool's name, and tool_input.file_path — absolute for both Edit and
    Write."""
    return {
        "session_id": "obsolete-file-edit-warning-test-session",
        "transcript_path": "/dev/null",
        "cwd": str(cwd),
        "hook_event_name": "PostToolUse",
        "tool_name": tool_name,
        "tool_input": {"file_path": str(file_path)},
        "tool_response": {"filePath": str(file_path), "success": True},
    }


def run_hook(payload, path_prefix=None, path_replacement=None):
    environment = dict(os.environ)
    if path_replacement is not None:
        environment["PATH"] = str(path_replacement)
    elif path_prefix is not None:
        environment["PATH"] = f"{path_prefix}{os.pathsep}{environment['PATH']}"
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run([sys.executable, str(SCRIPT_PATH)], input=text,
                          capture_output=True, text=True, check=False,
                          env=environment)


def emitted_object(result):
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def agent_text(result) -> str:
    """What the AGENT was told. Plain stdout on a PostToolUse hook reaches
    the debug log and nobody else — the hooks reference names
    UserPromptSubmit, UserPromptExpansion, SessionStart and PostModelSwitch
    as the only events where plain stdout becomes context. Only
    hookSpecificOutput.additionalContext arrives."""
    return ((emitted_object(result) or {})
            .get("hookSpecificOutput", {})
            .get("additionalContext", ""))


def silent(result) -> bool:
    return result.returncode == 0 and result.stdout.strip() == ""


with tempfile.TemporaryDirectory() as temporary_directory:
    tmp = Path(temporary_directory)

    # A `git` shim first on PATH that records the subcommand of every call the
    # hook makes and hands the call to the real binary. It is what proves the
    # cache, and what proves this hook never fetches.
    # TWO logs. The first is cleared between cases, so a case can count what
    # IT cost; the second is never cleared, so the "never fetches" case at the
    # end can speak for every hook run in the file rather than for the last
    # one only.
    real_git = shutil.which("git")
    call_log = tmp / "git-calls.log"
    every_call_log = tmp / "git-calls-cumulative.log"
    recording_git_directory = tmp / "recording-git"
    recording_git_directory.mkdir()
    (recording_git_directory / "git").write_text(
        "#!/bin/sh\n"
        f'printf "%s\\n" "$1" >> "{call_log}"\n'
        f'printf "%s\\n" "$1" >> "{every_call_log}"\n'
        f'exec "{real_git}" "$@"\n', encoding="utf-8")
    (recording_git_directory / "git").chmod(0o755)

    # A `git` that always fails, and a PATH with no git on it at all.
    failing_git_directory = tmp / "failing-git"
    failing_git_directory.mkdir()
    (failing_git_directory / "git").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    (failing_git_directory / "git").chmod(0o755)
    no_git_directory = tmp / "no-git-on-path"
    no_git_directory.mkdir()

    # A `git` whose DIFF fails and whose everything-else works: the shape that
    # separates "git could not say" from "nothing is obsolete". It records its
    # calls like the plain recording shim, so the retry can be counted.
    diff_failing_git_directory = tmp / "diff-failing-git"
    diff_failing_git_directory.mkdir()
    (diff_failing_git_directory / "git").write_text(
        "#!/bin/sh\n"
        f'printf "%s\\n" "$1" >> "{call_log}"\n'
        f'printf "%s\\n" "$1" >> "{every_call_log}"\n'
        'if [ "$1" = "diff" ]; then\n'
        '  printf "shimmed: this diff fails, every other call does not\\n" >&2\n'
        "  exit 3\n"
        "fi\n"
        f'exec "{real_git}" "$@"\n', encoding="utf-8")
    (diff_failing_git_directory / "git").chmod(0o755)

    def recorded_calls(subcommand: str, log=None) -> int:
        log = call_log if log is None else log
        if not log.exists():
            return 0
        return [line.strip() for line in
                log.read_text(encoding="utf-8").splitlines()].count(subcommand)

    # The "remote", and a clone standing in for a seat's checkout, on its own
    # topic branch cut from main.
    origin = tmp / "origin-repo"
    origin.mkdir()
    git(["init", "-q", "-b", "main"], origin)
    configure_identity(origin)
    commit_file(origin, "scripts/recover-crashed-seats.py", "def assess_seat():\n    pass\n",
                "first commit")
    commit_file(origin, "scripts/untouched-by-main.py", "steady\n", "a file main will leave alone")
    # Remembered for the pushed-head case further down, which needs a merge
    # base old enough that MORE THAN ONE commit on main has touched the file.
    early_main_sha = git(["rev-parse", "HEAD"], origin).stdout.strip()

    checkout = tmp / "seat-checkout"
    git(["clone", "-q", str(origin), str(checkout)], tmp)
    configure_identity(checkout)
    git(["checkout", "-q", "-b", "a-topic-branch"], checkout)
    checkout_git_dir = Path(git(["rev-parse", "--absolute-git-dir"], checkout).stdout.strip())
    cache_path = checkout_git_dir / "obsolete-file-edit-warning-path-set-cache.json"

    edited_file = checkout / "scripts/recover-crashed-seats.py"
    untouched_file = checkout / "scripts/untouched-by-main.py"

    # -----------------------------------------------------------------------
    # Level with main: nothing has gone obsolete, so nothing is said.
    # -----------------------------------------------------------------------
    result = run_hook(hook_payload(checkout, edited_file), path_prefix=recording_git_directory)
    check("a checkout level with main says nothing about the file just edited",
          silent(result), result.stdout + result.stderr)

    # -----------------------------------------------------------------------
    # Main moves the very file the agent is editing. This is the 2026-09-17
    # case: twenty minutes spent on assess_seat while a pull request changing
    # assess_seat merged.
    # -----------------------------------------------------------------------
    commit_file(origin, "scripts/recover-crashed-seats.py",
                "def assess_seat():\n    return 'rewritten on main'\n",
                "recover-crashed-seats: rework assess_seat")
    commit_file(origin, "docs/some-design.md", "prose\n", "a document main also moved")
    # The TEST fetches. The hook must never do it.
    git(["fetch", "-q", "origin"], checkout)

    if call_log.exists():
        call_log.unlink()
    result = run_hook(hook_payload(checkout, edited_file), path_prefix=recording_git_directory)
    warning = agent_text(result)
    check("a file main changed since the merge base warns the agent",
          "scripts/recover-crashed-seats.py" in warning, result.stdout + result.stderr)
    check("the warning is one line",
          warning != "" and "\n" not in warning, repr(warning))
    check("the warning counts the commits on main that touched that file",
          "1 commit(s) on origin/main have changed since this branch's merge base" in warning,
          warning)
    check("the warning reaches the agent on additionalContext, under the PostToolUse event",
          (emitted_object(result) or {}).get("hookSpecificOutput", {})
          .get("hookEventName") == "PostToolUse",
          result.stdout)
    check("the emitted object is valid JSON and carries nothing else",
          list((emitted_object(result) or {}).keys()) == ["hookSpecificOutput"],
          result.stdout)
    check("never a block: no decision field, and exit 0",
          "decision" not in (emitted_object(result) or {}) and result.returncode == 0,
          result.stdout)
    check("a never-pushed branch is told to rebase it itself, not that something will",
          "never been pushed" in warning and "git rebase origin/main" in warning, warning)
    check("and told the Stop hook's rebase needs a clean tree",
          "only when the tree is clean" in warning, warning)
    check("the first warning cost exactly one three-dot diff",
          recorded_calls("diff") == 1, call_log.read_text(encoding="utf-8"))

    # -----------------------------------------------------------------------
    # A file main has NOT changed stays silent even while the checkout is
    # behind: the warning is about the file in the agent's hands, not the
    # branch. The branch-level telling is the Stop hook's job.
    # -----------------------------------------------------------------------
    result = run_hook(hook_payload(checkout, untouched_file),
                      path_prefix=recording_git_directory)
    check("a file main has not changed is silent, even from a behind checkout",
          silent(result), result.stdout + result.stderr)

    # -----------------------------------------------------------------------
    # THE THREE-DOT RULE. A file this BRANCH changed and main did not is the
    # branch's own work; two dots would report it as something main moved.
    # -----------------------------------------------------------------------
    commit_file(checkout, "scripts/the-branchs-own-work.py", "mine\n",
                "the branch's own new file")
    git(["fetch", "-q", "origin"], checkout)
    result = run_hook(hook_payload(checkout, checkout / "scripts/the-branchs-own-work.py"),
                      path_prefix=recording_git_directory)
    check("a file the BRANCH changed but main did not is silent (three dots, not two)",
          silent(result), result.stdout + result.stderr)

    # -----------------------------------------------------------------------
    # THE CACHE. Same origin/main tip, same HEAD: the answer cannot have
    # changed, and the diff is not run again.
    # -----------------------------------------------------------------------
    call_log.unlink()
    first = run_hook(hook_payload(checkout, edited_file), path_prefix=recording_git_directory)
    diffs_after_first = recorded_calls("diff")
    second = run_hook(hook_payload(checkout, edited_file), path_prefix=recording_git_directory)
    check("the cached path set still warns on a second edit of the same file",
          "scripts/recover-crashed-seats.py" in agent_text(second), second.stdout)
    check("and the second call runs no further diff — the set was cached",
          recorded_calls("diff") == diffs_after_first,
          f"{diffs_after_first} then {recorded_calls('diff')}: "
          + call_log.read_text(encoding="utf-8"))
    check("the cache is keyed on both origin/main's tip and this checkout's HEAD",
          sorted(json.loads(cache_path.read_text(encoding="utf-8")).keys())
          == ["head", "main_tip", "paths"],
          cache_path.read_text(encoding="utf-8") if cache_path.exists() else "no cache written")
    check("the cache sits in the checkout's own git directory, beside the freshness stamp",
          cache_path.parent == checkout_git_dir, str(cache_path))

    # -----------------------------------------------------------------------
    # MAIN MOVES: the cached answer is stale and is recomputed.
    # -----------------------------------------------------------------------
    commit_file(origin, "scripts/untouched-by-main.py", "steady no longer\n",
                "main moves a second file")
    git(["fetch", "-q", "origin"], checkout)
    call_log.unlink()
    result = run_hook(hook_payload(checkout, untouched_file),
                      path_prefix=recording_git_directory)
    check("when main moves, the cache is invalidated and the diff runs again",
          recorded_calls("diff") == 1, call_log.read_text(encoding="utf-8"))
    check("and a file that has only just gone obsolete now warns",
          "scripts/untouched-by-main.py" in agent_text(result), result.stdout)

    # -----------------------------------------------------------------------
    # HEAD MOVES: so does the merge base, so the answer can change.
    # -----------------------------------------------------------------------
    call_log.unlink()
    commit_file(checkout, "scripts/a-second-branch-commit.py", "also mine\n",
                "the branch commits again")
    result = run_hook(hook_payload(checkout, edited_file), path_prefix=recording_git_directory)
    check("when HEAD moves, the cache is invalidated and the diff runs again",
          recorded_calls("diff") == 1, call_log.read_text(encoding="utf-8"))
    check("and the warning is still made from the fresh set",
          "scripts/recover-crashed-seats.py" in agent_text(result), result.stdout)

    # -----------------------------------------------------------------------
    # A PUSHED head gets the other advice: the frozen-head rule, not a rebase.
    # -----------------------------------------------------------------------
    pushed_checkout = tmp / "pushed-seat-checkout"
    git(["clone", "-q", str(origin), str(pushed_checkout)], tmp)
    configure_identity(pushed_checkout)
    git(["checkout", "-q", "-b", "a-pushed-topic-branch", early_main_sha], pushed_checkout)
    commit_file(pushed_checkout, "scripts/pushed-work.py", "reviewed\n", "work under review")
    git(["push", "-q", "origin", "a-pushed-topic-branch"], pushed_checkout)
    commit_file(origin, "scripts/recover-crashed-seats.py",
                "def assess_seat():\n    return 'rewritten again'\n",
                "recover-crashed-seats: assess_seat again")
    git(["fetch", "-q", "origin"], pushed_checkout)
    result = run_hook(hook_payload(pushed_checkout,
                                   pushed_checkout / "scripts/recover-crashed-seats.py"),
                      path_prefix=recording_git_directory)
    pushed_warning = agent_text(result)
    check("a pushed head is told to leave the branch alone, never to rebase",
          "is pushed" in pushed_warning and "do not rebase" in pushed_warning
          and "git rebase origin/main" not in pushed_warning, pushed_warning)
    check("and told its next topic starts from origin/main",
          "git checkout -b <name> origin/main" in pushed_warning, pushed_warning)
    check("the pushed warning is also one line",
          pushed_warning != "" and "\n" not in pushed_warning, repr(pushed_warning))
    check("two commits on main touching the file are counted as two",
          "2 commit(s) on origin/main" in pushed_warning, pushed_warning)

    # -----------------------------------------------------------------------
    # OUTSIDE THE CHECKOUT. Another worktree of the same repository, and a
    # scratch directory: in neither is a comparison against THIS checkout's
    # merge base meaningful, so neither is warned about — even when the path
    # inside it is one main has moved.
    # -----------------------------------------------------------------------
    other_worktree = tmp / "another-worktree"
    git(["worktree", "add", "-q", "-b", "another-branch", str(other_worktree), "main"], checkout)
    result = run_hook(hook_payload(checkout,
                                   other_worktree / "scripts/recover-crashed-seats.py"),
                      path_prefix=recording_git_directory)
    check("an edit in ANOTHER worktree of the same repository is not warned about",
          silent(result), result.stdout + result.stderr)

    scratch = tmp / "a-scratch-directory" / "scripts"
    scratch.mkdir(parents=True)
    (scratch / "recover-crashed-seats.py").write_text("elsewhere\n", encoding="utf-8")
    result = run_hook(hook_payload(checkout, scratch / "recover-crashed-seats.py"),
                      path_prefix=recording_git_directory)
    check("an edit outside any checkout is not warned about, whatever it is named",
          silent(result), result.stdout + result.stderr)

    # -----------------------------------------------------------------------
    # BROKEN OR ABSENT INPUT. Every one of these exits 0 and prints nothing:
    # a staleness warning must never be why an agent's edit reports a failure.
    # -----------------------------------------------------------------------
    no_file_path = hook_payload(checkout, edited_file)
    no_file_path["tool_input"] = {}
    check("a payload with no file_path exits 0 and prints nothing",
          silent(run_hook(no_file_path)), "")

    no_tool_input = hook_payload(checkout, edited_file)
    del no_tool_input["tool_input"]
    check("a payload with no tool_input at all exits 0 and prints nothing",
          silent(run_hook(no_tool_input)), "")

    check("an unreadable payload exits 0 and prints nothing",
          silent(run_hook("{not json at all")), "")
    check("empty stdin exits 0 and prints nothing", silent(run_hook("")), "")

    not_a_repository = tmp / "not-a-repository"
    not_a_repository.mkdir()
    (not_a_repository / "a-file.py").write_text("loose\n", encoding="utf-8")
    check("a cwd in no repository at all exits 0 and prints nothing",
          silent(run_hook(hook_payload(not_a_repository, not_a_repository / "a-file.py"))), "")

    vanished = hook_payload(tmp / "a-directory-that-does-not-exist", edited_file)
    check("a cwd that no longer exists exits 0 and prints nothing",
          silent(run_hook(vanished)), "")

    # -----------------------------------------------------------------------
    # GIT ITSELF FAILING. A shim that exits 1, and a PATH carrying no git.
    # Both are silence, not a traceback on the agent's tool call.
    # -----------------------------------------------------------------------
    result = run_hook(hook_payload(checkout, edited_file), path_prefix=failing_git_directory)
    check("a git that exits 1 on every call exits 0 and prints nothing",
          silent(result), result.stdout + result.stderr)

    result = run_hook(hook_payload(checkout, edited_file),
                      path_replacement=no_git_directory)
    check("no git on PATH at all exits 0 and prints nothing",
          silent(result), result.stdout + result.stderr)

    # -----------------------------------------------------------------------
    # A FAILED DIFF IS NOT AN EMPTY ANSWER (user-ruled 2026-09-17). git answers
    # every other call here, so the hook gets as far as the diff and the diff
    # alone fails. It must stay silent AND cache nothing: a failure written to
    # the cache as "nothing obsolete" would silence this hook for every edit
    # until the next commit or fetch. The file below is one the checkout is
    # genuinely behind on, so anything cached would be wrong as well as sticky.
    # -----------------------------------------------------------------------
    if cache_path.exists():
        cache_path.unlink()
    call_log.unlink()
    result = run_hook(hook_payload(checkout, edited_file),
                      path_prefix=diff_failing_git_directory)
    check("a git whose diff fails exits 0 and prints nothing",
          silent(result), result.stdout + result.stderr)
    check("the failed diff was actually reached, not short-circuited earlier",
          recorded_calls("diff") == 1, call_log.read_text(encoding="utf-8"))
    check("a failed diff writes NO cache file",
          not cache_path.exists(),
          cache_path.read_text(encoding="utf-8") if cache_path.exists() else "")

    call_log.unlink()
    result = run_hook(hook_payload(checkout, edited_file),
                      path_prefix=diff_failing_git_directory)
    check("and the NEXT call attempts the diff again rather than trusting a cache",
          recorded_calls("diff") == 1 and silent(result),
          call_log.read_text(encoding="utf-8") + result.stdout)

    call_log.unlink()
    result = run_hook(hook_payload(checkout, edited_file),
                      path_prefix=recording_git_directory)
    check("once git answers again, the warning comes back and the cache is written",
          "scripts/recover-crashed-seats.py" in agent_text(result) and cache_path.exists(),
          result.stdout + result.stderr)

    # A checkout with no origin/main — a repository, but nothing to compare to.
    lonely = tmp / "no-origin-main-repo"
    lonely.mkdir()
    git(["init", "-q", "-b", "main"], lonely)
    configure_identity(lonely)
    commit_file(lonely, "scripts/alone.py", "alone\n", "the only commit")
    result = run_hook(hook_payload(lonely, lonely / "scripts/alone.py"))
    check("a repository with no origin/main exits 0 and prints nothing",
          silent(result), result.stdout + result.stderr)

    # -----------------------------------------------------------------------
    # NEVER FETCHES. The Stop hook fetches on its own throttle; a PostToolUse
    # hook runs at every edit and must not touch the network. Asserted LAST,
    # and against the cumulative log, so it speaks for every run in this file
    # rather than for whichever one happened to precede it.
    # -----------------------------------------------------------------------
    every_call = (every_call_log.read_text(encoding="utf-8")
                  if every_call_log.exists() else "")
    check("the shim recorded real calls, so the fetch case below is not vacuous",
          every_call.count("\n") > 20, every_call)
    check("not one call this hook made in any case above was a fetch",
          recorded_calls("fetch", every_call_log) == 0, every_call)


print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
