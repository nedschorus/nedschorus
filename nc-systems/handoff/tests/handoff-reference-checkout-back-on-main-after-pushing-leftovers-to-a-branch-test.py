#!/usr/bin/env python3
"""Tests for handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch.py.

Run: python3 nc-systems/handoff/tests/handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch-test.py

HOME is a scratch directory, set before the program is loaded, so the reference-checkout is a
fresh clone under it, made for each case from a bare origin of its own. A failed push is caused by
a pre-receive hook in that origin that refuses every push. One case installs this repository's own
client-side hooks in the scratch checkout, as both machines' clones have them; two install a
post-merge hook of their own.

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
          == program.LEFTOVERS_COMMIT_MESSAGE
          and local_branches() == ["refs/heads/main"], out + err)


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


def refuse_every_push():
    hook = ORIGIN / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\necho refused by the test hook >&2\nexit 1\n")
    hook.chmod(0o755)
    return hook


def local_branches():
    return git("for-each-ref", "--format=%(refname)", "refs/heads").splitlines()


def failed_push_then_rerun_case():
    fresh_reference_checkout()
    local = commit("local only")
    advance_origin()
    hook = refuse_every_push()
    status, out, err = run_program()
    check("failed push: exits 1 quoting git, puts the checkout on main at origin/main all the same, "
          "and keeps the leftovers on the local branch it names with its commit",
          status == 1 and "refused by the test hook" in err and "git push --no-verify origin" in err
          and on_main_at_origin_main_and_clean()
          and git("rev-parse", f"refs/heads/{LEFTOVERS}") == local
          and f"The leftovers branch {LEFTOVERS}, at commit {local}, holds leftovers" in err
          and "it pushes that same branch" in err
          and "is on main at origin/main" in err
          and not origin_branch(LEFTOVERS) and "a step failed" in err, out + err)
    hook.unlink()
    status, out, err = run_program()
    check("rerun after a failed push: pushes that same branch, with no new suffix, and deletes "
          "its local copy",
          status == 0 and LEFTOVERS in out and origin_branch(LEFTOVERS) == local
          and not origin_branch(f"{LEFTOVERS}-2") and local_branches() == ["refs/heads/main"]
          and on_main_at_origin_main_and_clean(), out + err)


def head_on_an_unpushed_leftovers_branch_case():
    """As a failed push left the checkout before the program went back to main after one."""
    fresh_reference_checkout()
    git("switch", "-q", "-c", LEFTOVERS)
    local = commit("left by an earlier run")
    (CHECKOUT / "untracked.txt").write_text("new by hand\n")
    status, out, err = run_program()
    saved = origin_branch(LEFTOVERS)
    check("HEAD on an unpushed leftovers branch with new changes: commits them on that same "
          "branch and pushes it, with no new suffix",
          status == 0 and saved and git("rev-parse", f"{saved}^", cwd=ORIGIN) == local
          and tree_file(LEFTOVERS, "untracked.txt") == "new by hand"
          and not origin_branch(f"{LEFTOVERS}-2") and on_main_at_origin_main_and_clean(),
          out + err)


def track_on_origin(path, content):
    (OTHER_CLONE / path).write_text(content)
    git("add", path, cwd=OTHER_CLONE)
    git("commit", "-q", "-m", f"track {path}", cwd=OTHER_CLONE)
    git("push", "-q", "origin", "HEAD:main", cwd=OTHER_CLONE)


def ignored_file_at_a_path_origin_main_tracks_case():
    fresh_reference_checkout()
    track_on_origin("kept.log", "from origin\n")
    (CHECKOUT / ".git" / "info" / "exclude").write_text("*.log\n")
    (CHECKOUT / "kept.log").write_text("ignored, and only here\n")
    head = git("rev-parse", "HEAD")
    status, out, err = run_program()
    check("ignored file at a path origin/main tracks: git refuses the fast-forward, the program "
          "exits 1 naming the file, and the file and HEAD are unchanged",
          status == 1 and "kept.log" in err and "--no-overwrite-ignore" in err
          and git("rev-parse", "HEAD") == head
          and (CHECKOUT / "kept.log").read_text() == "ignored, and only here\n"
          and local_branches() == ["refs/heads/main"], out + err)


def ignored_directory_where_origin_main_tracks_a_file_cases():
    for case, make_leftovers in (("the fast-forward", False), ("the switch", True)):
        fresh_reference_checkout()
        track_on_origin("cache", "a file on origin\n")
        (CHECKOUT / ".git" / "info" / "exclude").write_text("cache/\n")
        (CHECKOUT / "cache").mkdir()
        (CHECKOUT / "cache" / "private.log").write_text("ignored, and only here\n")
        local = commit("local only") if make_leftovers else None
        status, out, err = run_program()
        check(f"ignored directory where origin/main tracks a file, at {case}: git refuses, the "
              "program exits 1, and the ignored data is kept",
              status == 1 and "a step failed" in err
              and (CHECKOUT / "cache" / "private.log").read_text() == "ignored, and only here\n"
              and (not make_leftovers or origin_branch(LEFTOVERS) == local), out + err)


def post_merge_hook(body):
    hooks = SCRATCH_HOME / "hooks"
    hooks.mkdir(exist_ok=True)
    hook = hooks / "post-merge"
    hook.write_text(body)
    hook.chmod(0o755)
    git("config", "core.hooksPath", str(hooks))


def post_merge_hook_run_after_the_switch_case():
    fresh_reference_checkout()
    record = SCRATCH_HOME / "post-merge-ran"
    record.unlink(missing_ok=True)
    post_merge_hook(f"#!/bin/sh\ngit rev-parse ORIG_HEAD HEAD > {record}\n")
    local = commit("local only")
    advanced = advance_origin()
    status, out, err = run_program()
    check("after switching main to origin/main, the post-merge hook runs as after a merge, with "
          "ORIG_HEAD at the commit HEAD left",
          status == 0 and record.is_file()
          and record.read_text().split() == [local, advanced], out + err)


def post_merge_hook_failure_case():
    fresh_reference_checkout()
    post_merge_hook("#!/bin/sh\necho FAILED by the test hook >&2\nexit 1\n")
    commit("local only")
    status, out, err = run_program()
    check("a failed post-merge hook: exits 1 with what the hook printed, the checkout on main and "
          "the leftovers pushed",
          status == 1 and "FAILED by the test hook" in err and "post-merge" in err
          and origin_branch(LEFTOVERS) and on_main_at_origin_main_and_clean(), out + err)


def post_merge_hook_rerun_after_a_failure_case():
    fresh_reference_checkout()
    record = SCRATCH_HOME / "post-merge-ran"
    record.unlink(missing_ok=True)
    post_merge_hook("#!/bin/sh\necho FAILED by the test hook >&2\nexit 1\n")
    local = commit("local only")
    first_status, _, _ = run_program()
    post_merge_hook(f"#!/bin/sh\ngit rev-parse ORIG_HEAD HEAD > {record}\n")
    status, out, err = run_program()
    ran_on_rerun = record.is_file() and record.read_text().split() == [local, git("rev-parse", "HEAD")]
    record.unlink(missing_ok=True)
    third_status, _, _ = run_program()
    check("rerun after a failed post-merge hook: the hook runs again with the same ORIG_HEAD, the "
          "run succeeds, and the run after it does not run the hook",
          first_status == 1 and status == 0 and ran_on_rerun and third_status == 0
          and not record.is_file() and on_main_at_origin_main_and_clean(), out + err)


def post_merge_hook_kills_git_case():
    fresh_reference_checkout()
    # git itself then dies of the signal, so its exit status is negative.
    post_merge_hook("#!/bin/sh\nkill -TERM $PPID\nsleep 1\n")
    commit("local only")
    status, out, err = run_program()
    check("git killed by a signal while running the post-merge hook: exits 1, the checkout on main",
          status == 1 and "post-merge" in err and on_main_at_origin_main_and_clean(), out + err)


@contextlib.contextmanager
def step_failing(name, fail):
    """Make the program's git step, or the shared fast-forward step, raise when fail says so."""
    if name == "git":
        real = program.git

        def stub(checkout, arguments, **options):
            if fail(arguments):
                raise program.StepFailed(f"injected failure of git {' '.join(arguments)}")
            return real(checkout, arguments, **options)
        target, attribute = program, "git"
    else:
        real = program.reference_checkout_steps.fast_forward_to_origin_main_and_check_or_raise

        def stub(checkout):
            raise program.StepFailed("injected failure of the fast-forward and check")
        target, attribute = program.reference_checkout_steps, name
    setattr(target, attribute, stub)
    try:
        yield
    finally:
        setattr(target, attribute, real)


def failed_push_then_failed_later_step_cases():
    for case, name, fail, injected in (
            ("the switch to main", "git",
             lambda arguments: arguments[0] == "switch" and "-C" in arguments,
             "injected failure of git switch --no-overwrite-ignore -C main origin/main"),
            ("the fast-forward and check", "fast_forward_to_origin_main_and_check_or_raise",
             None, "injected failure of the fast-forward and check")):
        fresh_reference_checkout()
        commit("local only")
        hook = refuse_every_push()
        with step_failing(name, fail):
            status, out, err = run_program()
        hook.unlink()
        check(f"failed push, then a failure of {case}: exits 1 reporting both",
              status == 1 and "refused by the test hook" in err and injected in err
              and f"The leftovers branch {LEFTOVERS}" in err, out + err)


def failure_after_the_pushes_keeps_earlier_problems_cases():
    for case, set_up, fail, injected, earlier in (
            ("a failed push, then a failed update-ref", refuse_every_push,
             lambda arguments: arguments[0] == "update-ref",
             "injected failure of git update-ref", "refused by the test hook"),
            ("a failed post-merge hook, then a failed branch -D",
             lambda: post_merge_hook("#!/bin/sh\necho FAILED by the test hook >&2\nexit 1\n"),
             lambda arguments: arguments[:2] == ["branch", "-D"],
             "injected failure of git branch -D", "FAILED by the test hook")):
        fresh_reference_checkout()
        commit("local only")
        made = set_up()
        with step_failing("git", fail):
            status, out, err = run_program()
        if isinstance(made, Path):
            made.unlink()
        check(f"{case}: exits 1 reporting both",
              status == 1 and injected in err and earlier in err, out + err)


def another_run_committed_onto_main_before_the_switch_case():
    """As when a concurrent run's switch carried this run's changes onto main before its commit."""
    fresh_reference_checkout()
    (CHECKOUT / "untracked.txt").write_text("new by hand\n")
    landed = []
    real = program.git

    def stub(checkout, arguments, **options):
        result = real(checkout, arguments, **options)
        if arguments[0] == "push" and not landed:
            git("switch", "-q", "-C", "main", "origin/main")
            landed.append(commit("landed on main"))
        return result
    program.git = stub
    try:
        status, out, err = run_program()
    finally:
        program.git = real
    check("HEAD's commit held by neither origin/main nor a leftovers branch: exits 1 naming it, "
          "without switching, and the commit stays on the local main",
          status == 1 and landed and landed[0] in err and "was not switched" in err
          and git("rev-parse", "refs/heads/main") == landed[0], out + err)
    status, out, err = run_program()
    check("rerun after that: the commit is saved on a pushed leftovers branch, then on main",
          status == 0 and origin_branch(f"{LEFTOVERS}-2") == landed[0]
          and on_main_at_origin_main_and_clean(), out + err)


def post_merge_hook_timeout_case():
    fresh_reference_checkout()
    post_merge_hook("#!/bin/sh\nsleep 30\n")
    commit("local only")
    saved_timeout = program.POST_MERGE_HOOK_TIMEOUT_SECONDS
    program.POST_MERGE_HOOK_TIMEOUT_SECONDS = 1
    try:
        status, out, err = run_program()
    finally:
        program.POST_MERGE_HOOK_TIMEOUT_SECONDS = saved_timeout
    check("a post-merge hook that does not finish: exits 1 saying so, the checkout on main",
          status == 1 and "post-merge" in err and "did not finish" in err
          and on_main_at_origin_main_and_clean(), out + err)


def leftovers_conflicting_with_origin_main_under_repository_hooks_case():
    fresh_reference_checkout()
    git("config", "core.hooksPath", str(REPOSITORY_HOOKS))
    # The pre-commit hook refuses a commit made in a Claude session when the clone's own config
    # lacks the unconfigured-agent identity, which the real reference-checkout holds.
    git("config", "user.name", "unconfigured-agent")
    git("config", "user.email", "unconfigured-agent@nedschorus.invalid")
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
          and (CHECKOUT / ".git" / "MERGE_HEAD").is_file() and not origin_branch(LEFTOVERS)
          and "a step failed" in err,
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
failed_push_then_rerun_case()
head_on_an_unpushed_leftovers_branch_case()
ignored_file_at_a_path_origin_main_tracks_case()
ignored_directory_where_origin_main_tracks_a_file_cases()
post_merge_hook_run_after_the_switch_case()
post_merge_hook_failure_case()
post_merge_hook_rerun_after_a_failure_case()
post_merge_hook_timeout_case()
post_merge_hook_kills_git_case()
failed_push_then_failed_later_step_cases()
failure_after_the_pushes_keeps_earlier_problems_cases()
another_run_committed_onto_main_before_the_switch_case()
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
