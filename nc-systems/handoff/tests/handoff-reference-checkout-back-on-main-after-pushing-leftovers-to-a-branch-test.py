#!/usr/bin/env python3
"""Tests for handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch.py.

Run: python3 nc-systems/handoff/tests/handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch-test.py

HOME is a scratch directory, set before the program is loaded, so the reference-checkout is a
fresh clone under it, made for each case from a bare origin of its own. A failed push is caused by
a pre-receive hook in that origin that refuses every push. One case installs this repository's own
client-side hooks in the scratch checkout, as both machines' clones have them.

Prints one line per case and exits non-zero if any case fails.
"""

import atexit
import contextlib
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

# Before anything runs git: a run started with GIT_DIR set, or another variable that redirects
# git, must keep this suite's git out of the repository the variable names.
_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().parents[3] / "scripts"
    / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

SCRATCH_HOME = Path(tempfile.mkdtemp(prefix="reference-checkout-back-on-main-test-home-"))
atexit.register(shutil.rmtree, SCRATCH_HOME, True)
os.environ["HOME"] = str(SCRATCH_HOME)
# A scratch HOME has no git identity, and the program commits.
os.environ.update(GIT_AUTHOR_NAME="test", GIT_AUTHOR_EMAIL="test@example.invalid",
                  GIT_COMMITTER_NAME="test", GIT_COMMITTER_EMAIL="test@example.invalid")

SCRIPT_PATH = (Path(__file__).resolve().parent.parent
               / "handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch.py")
_spec = importlib.util.spec_from_file_location("reference_checkout_back_on_main", SCRIPT_PATH)
program = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(program)

CHECKOUT = program.reference_checkout_steps.REFERENCE_CHECKOUT
ORIGIN = SCRATCH_HOME / "origin.git"
OTHER_CLONE = SCRATCH_HOME / "other-clone"
REPOSITORY_HOOKS = Path(__file__).resolve().parents[3] / "scripts" / "git-client-side-hooks"
TODAY = date(2026, 11, 4)
LEFTOVERS = "reference-checkout-leftovers-2026-11-04"

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def git(*arguments, cwd=CHECKOUT, check=True):
    return subprocess.run(["git", *arguments], cwd=str(cwd), capture_output=True, text=True,
                          check=check).stdout.strip()


def commit(message, cwd=CHECKOUT):
    path = Path(cwd) / "tracked.txt"
    path.write_text(path.read_text() + f"{message}\n")
    git("commit", "-q", "-am", message, cwd=cwd)
    return git("rev-parse", "HEAD", cwd=cwd)


def fresh_reference_checkout():
    """An origin with one commit on main, and the reference-checkout cloned from it, on main."""
    for path in (ORIGIN, CHECKOUT, OTHER_CLONE):
        shutil.rmtree(path, ignore_errors=True)
    git("init", "-q", "--bare", "-b", "main", str(ORIGIN), cwd=SCRATCH_HOME)
    git("clone", "-q", str(ORIGIN), str(OTHER_CLONE), cwd=SCRATCH_HOME)
    (OTHER_CLONE / "tracked.txt").write_text("one\n")
    git("add", "tracked.txt", cwd=OTHER_CLONE)
    git("commit", "-q", "-m", "one", cwd=OTHER_CLONE)
    git("push", "-q", "origin", "HEAD:main", cwd=OTHER_CLONE)
    CHECKOUT.parent.mkdir(parents=True, exist_ok=True)
    git("clone", "-q", str(ORIGIN), str(CHECKOUT), cwd=SCRATCH_HOME)


def advance_origin():
    commit("from elsewhere", cwd=OTHER_CLONE)
    git("push", "-q", "origin", "HEAD:main", cwd=OTHER_CLONE)
    return git("rev-parse", "HEAD", cwd=OTHER_CLONE)


def run_program():
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        status = program.main([], today=TODAY)
    return status, out.getvalue(), err.getvalue()


def origin_branch(name):
    return git("rev-parse", "--verify", "--quiet", f"refs/heads/{name}", cwd=ORIGIN, check=False)


def on_main_at_origin_main_and_clean():
    return (git("symbolic-ref", "HEAD") == "refs/heads/main"
            and git("rev-parse", "HEAD") == git("rev-parse", "main", cwd=ORIGIN)
            and git("status", "--porcelain", "--untracked-files=all") == "")


def tree_file(branch, path):
    return git("show", f"{branch}:{path}", cwd=ORIGIN, check=False)


def changes_only_case():
    fresh_reference_checkout()
    (CHECKOUT / "tracked.txt").write_text("changed by hand\n")
    (CHECKOUT / "untracked.txt").write_text("new by hand\n")
    status, out, err = run_program()
    check("changes only: saved in one commit on a pushed leftovers branch, then on main",
          status == 0 and LEFTOVERS in out and on_main_at_origin_main_and_clean()
          and tree_file(LEFTOVERS, "tracked.txt") == "changed by hand"
          and tree_file(LEFTOVERS, "untracked.txt") == "new by hand"
          and git("log", "-1", "--format=%s", LEFTOVERS, cwd=ORIGIN)
          == program.LEFTOVERS_COMMIT_MESSAGE, out + err)


def commits_only_case():
    fresh_reference_checkout()
    local = commit("local only")
    status, out, err = run_program()
    check("commits only: the commit is pushed as the leftovers branch, with no new commit, "
          "then main is at origin/main",
          status == 0 and LEFTOVERS in out and origin_branch(LEFTOVERS) == local
          and on_main_at_origin_main_and_clean(), out + err)


def changes_and_commits_case():
    fresh_reference_checkout()
    local = commit("local only")
    (CHECKOUT / "untracked.txt").write_text("new by hand\n")
    advance_origin()
    status, out, err = run_program()
    saved = origin_branch(LEFTOVERS)
    check("changes and commits: both saved on the pushed leftovers branch, then main is at "
          "origin/main",
          status == 0 and saved and git("rev-parse", f"{saved}^", cwd=ORIGIN) == local
          and tree_file(LEFTOVERS, "untracked.txt") == "new by hand"
          and on_main_at_origin_main_and_clean(), out + err)


def neither_case():
    fresh_reference_checkout()
    head = git("rev-parse", "HEAD")
    status, out, err = run_program()
    check("neither: nothing is saved and nothing changes",
          status == 0 and "no leftovers" in out and git("rev-parse", "HEAD") == head
          and on_main_at_origin_main_and_clean()
          and git("for-each-ref", "--format=%(refname)", "refs/heads") == "refs/heads/main"
          and not origin_branch(LEFTOVERS), out + err)


def behind_origin_only_case():
    fresh_reference_checkout()
    advanced = advance_origin()
    status, out, err = run_program()
    check("behind origin only: main is fast-forwarded, and no branch is made",
          status == 0 and "no leftovers" in out and git("rev-parse", "HEAD") == advanced
          and on_main_at_origin_main_and_clean() and not origin_branch(LEFTOVERS), out + err)


def failed_push_case():
    fresh_reference_checkout()
    local = commit("local only")
    advance_origin()
    hook = ORIGIN / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\necho refused by the test hook >&2\nexit 1\n")
    hook.chmod(0o755)
    status, out, err = run_program()
    check("failed push: exits 1 quoting git, and leaves main untouched on the leftovers branch",
          status == 1 and "refused by the test hook" in err and "git push --no-verify origin" in err
          and git("rev-parse", "refs/heads/main") == local
          and git("symbolic-ref", "HEAD") == f"refs/heads/{LEFTOVERS}"
          and f"now on the branch {LEFTOVERS}, at commit {git('rev-parse', 'HEAD')}" in err
          and not origin_branch(LEFTOVERS) and "was not put back on main" in err, out + err)


def leftovers_conflicting_with_origin_main_under_repository_hooks_case():
    fresh_reference_checkout()
    git("config", "core.hooksPath", str(REPOSITORY_HOOKS))
    local = commit("local only")
    advance_origin()
    status, out, err = run_program()
    check("leftovers that conflict with origin/main, with the repository's hooks installed: "
          "pushed all the same, then on main",
          status == 0 and origin_branch(LEFTOVERS) == local and on_main_at_origin_main_and_clean(),
          out + err)


def branch_name_taken_case():
    fresh_reference_checkout()
    git("push", "-q", "origin", f"HEAD:refs/heads/{LEFTOVERS}", cwd=OTHER_CLONE)
    git("branch", f"{LEFTOVERS}-2")
    (CHECKOUT / "untracked.txt").write_text("new by hand\n")
    status, out, err = run_program()
    check("branch name taken on origin and locally: the next free suffix is used",
          status == 0 and f"{LEFTOVERS}-3" in out
          and tree_file(f"{LEFTOVERS}-3", "untracked.txt") == "new by hand"
          and on_main_at_origin_main_and_clean(), out + err)


def head_off_main_case():
    fresh_reference_checkout()
    git("switch", "-q", "-c", "someone-elses-branch")
    advanced = advance_origin()
    status, out, err = run_program()
    check("HEAD off main with no leftovers: switched to main at origin/main, the branch kept",
          status == 0 and "no leftovers" in out and git("rev-parse", "HEAD") == advanced
          and on_main_at_origin_main_and_clean()
          and git("rev-parse", "--verify", "--quiet", "refs/heads/someone-elses-branch"),
          out + err)


def detached_head_with_commits_case():
    fresh_reference_checkout()
    git("switch", "-q", "--detach")
    local = commit("detached only")
    status, out, err = run_program()
    check("detached HEAD with a commit: the commit is pushed as the leftovers branch, then on main",
          status == 0 and origin_branch(LEFTOVERS) == local and on_main_at_origin_main_and_clean(),
          out + err)


def rerun_after_success_case():
    fresh_reference_checkout()
    (CHECKOUT / "untracked.txt").write_text("new by hand\n")
    first_status, _, _ = run_program()
    head = git("rev-parse", "HEAD")
    branches = git("for-each-ref", "--format=%(refname)", "refs/heads")
    status, out, err = run_program()
    check("rerun after success: succeeds, saves nothing and changes nothing",
          first_status == 0 and status == 0 and "no leftovers" in out
          and git("rev-parse", "HEAD") == head
          and git("for-each-ref", "--format=%(refname)", "refs/heads") == branches
          and not origin_branch(f"{LEFTOVERS}-2"), out + err)


def failed_fetch_case():
    fresh_reference_checkout()
    (CHECKOUT / "untracked.txt").write_text("new by hand\n")
    git("remote", "set-url", "origin", str(SCRATCH_HOME / "no-such-origin.git"))
    status, out, err = run_program()
    check("failed fetch: exits 1 quoting git, and changes nothing",
          status == 1 and "git fetch origin" in err and "no-such-origin" in err
          and git("symbolic-ref", "HEAD") == "refs/heads/main"
          and git("for-each-ref", "--format=%(refname)", "refs/heads") == "refs/heads/main"
          and (CHECKOUT / "untracked.txt").is_file(), out + err)


def local_main_only_commits_case():
    fresh_reference_checkout()
    main_only = commit("on the local main only")
    git("switch", "-q", "-c", "someone-elses-branch", "origin/main")
    status, out, err = run_program()
    check("local main holds commits neither origin/main nor HEAD holds: exits 1, changing nothing",
          status == 1 and "would drop them" in err
          and git("rev-parse", "refs/heads/main") == main_only
          and git("symbolic-ref", "HEAD") == "refs/heads/someone-elses-branch"
          and not origin_branch(LEFTOVERS), out + err)


def merge_in_progress_case():
    fresh_reference_checkout()
    git("switch", "-q", "-c", "side")
    commit("on side")
    git("switch", "-q", "main")
    commit("on main")
    git("merge", "-q", "side", check=False)
    main_before = git("rev-parse", "refs/heads/main")
    status, out, err = run_program()
    check("merge in progress: git refuses to switch, the program exits 1 quoting it, main untouched",
          status == 1 and "git switch -c" in err and "merging" in err
          and git("rev-parse", "refs/heads/main") == main_before
          and (CHECKOUT / ".git" / "MERGE_HEAD").is_file() and not origin_branch(LEFTOVERS),
          out + err)


def script_exit_status_case():
    fresh_reference_checkout()
    git("remote", "set-url", "origin", str(SCRATCH_HOME / "no-such-origin.git"))
    result = subprocess.run([sys.executable, str(SCRIPT_PATH)], capture_output=True, text=True,
                            check=False)
    check("run as a script, a failure exits 1", result.returncode == 1, result.stderr)


changes_only_case()
commits_only_case()
changes_and_commits_case()
neither_case()
behind_origin_only_case()
failed_push_case()
leftovers_conflicting_with_origin_main_under_repository_hooks_case()
branch_name_taken_case()
head_off_main_case()
detached_head_with_commits_case()
rerun_after_success_case()
failed_fetch_case()
local_main_only_commits_case()
merge_in_progress_case()
script_exit_status_case()

if failures:
    print(f"\n{len(failures)} case(s) failed")
    sys.exit(1)
print("\nall cases passed")
