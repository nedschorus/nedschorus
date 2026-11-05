#!/usr/bin/env python3
"""Put the reference-checkout ~/Projects/nedschorus back on main, first saving any leftovers to a pushed branch.

Usage, on the machine whose reference-checkout will not fast-forward to main:
  python3 ~/Projects/nedschorus/nc-systems/handoff/handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch.py

The handoff-supervisor restarts itself on main's code at a session-handoff only when its checkout
fast-forwards to main or is current with it. When the reference-checkout is that checkout and does
neither, the handoff-supervisor runs this program's put_reference_checkout_back_on_main itself and,
when it succeeds, restarts; when it fails, the successor's not-restarted notice carries what failed
and names this program, for the agent-seat to run again once it has fixed the cause. No agent works
in the reference-checkout, so what stops it is left over.

The program:
- fetches origin;
- finds the leftovers: uncommitted changes, untracked files included; commits on HEAD that
  origin/main lacks; and local branches named reference-checkout-leftovers-*, which exist only
  while their push has not succeeded;
- when there are uncommitted changes or commits, saves them on a branch: the leftovers branch HEAD
  is already on, else a new branch reference-checkout-leftovers-<YYYY-MM-DD>, with -2, -3 and so on
  added when a local branch or a branch on origin already has that name; commits the changes there
  if there are any;
- pushes every local leftovers branch to origin, and deletes the local copy of each one pushed;
- when HEAD is not on main, or was moved off it to save leftovers, runs `git switch -C main
  origin/main`, which puts the local main at origin/main and checks it out, whether or not every
  push succeeded, because every agent-seat's git hooks and the cron jobs run from this checkout;
  and then runs the clone's post-merge hook, with ORIG_HEAD at the commit HEAD left, as a merge
  would have, since the switch runs none;
- fast-forwards to origin/main and checks that HEAD is origin/main with no changed tracked file,
  with the same shared function as the restart program's step 0.
It prints the pushed leftovers branches, or that there were none. On a checkout already on main, at
origin/main, with nothing uncommitted and no local leftovers branch, it changes nothing, so it can
be run again to check a fix.

What it does not handle:
- a merge, rebase, cherry-pick or revert in progress, or a lock another git process holds, such as
  index.lock: git refuses the step, and the program fails as below;
- ignored files: they are neither saved nor removed. An ignored file at a path origin/main tracks,
  which the switch or the fast-forward would overwrite, makes the program fail before changing
  anything;
- commits on the local main that neither origin/main nor HEAD holds, when HEAD is not on main:
  switching main to origin/main would drop them, so the program fails before changing anything.

How it fails: it prints what failed, with what git or the hook printed, to standard error and exits
1. A failed fetch, local main's own commits, or an ignored file in the way, change nothing. Any
other failed step stops the program, except a failed push, which still lets the checkout go back on
main: the unpushed branch stays in the checkout, and the message names it and its commit; run again,
the program pushes that same branch. A failed post-merge hook leaves the checkout on main, and its
message is the hook's. The push skips the clone's pre-push hook, so leftovers that conflict with
origin/main, the usual state of a stuck reference-checkout, are pushed all the same. It changes the
clone every agent-seat's worktrees hang off, but moves main only after a branch holds whatever main
is moved away from.

Exit status: 0 on main at origin/main with every leftovers branch pushed; 1 a step failed.
"""

import argparse
import importlib.util
import subprocess
import sys
from datetime import date
from pathlib import Path

SYSTEM_DIRECTORY = Path(__file__).resolve().parent
_reference_checkout_steps_spec = importlib.util.spec_from_file_location(
    "handoff_reference_checkout_fetch_and_fast_forward_to_origin_main_check_common",
    SYSTEM_DIRECTORY / "handoff-reference-checkout-fetch-and-fast-forward-to-origin-main-check-common.py")
reference_checkout_steps = importlib.util.module_from_spec(_reference_checkout_steps_spec)
_reference_checkout_steps_spec.loader.exec_module(reference_checkout_steps)

# Its messages reach an agent: docs/nedschorus-wiki/nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md
PROGRAM = "handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch"
LEFTOVERS_BRANCH_PREFIX = "reference-checkout-leftovers-"
LEFTOVERS_COMMIT_MESSAGE = "Leftovers found in the reference-checkout"
StepFailed = reference_checkout_steps.ReferenceCheckoutGitStepFailed
TREE_STEP_TIMEOUT_SECONDS = reference_checkout_steps.NETWORK_OR_TREE_GIT_STEP_TIMEOUT_SECONDS


def git(checkout: Path, arguments, **options) -> str:
    return reference_checkout_steps.reference_checkout_git_output_or_raise(checkout, arguments,
                                                                          **options)


def ref_exists(checkout: Path, ref: str) -> bool:
    # --verify --quiet exits 1 for a name that does not exist.
    return bool(git(checkout, ["rev-parse", "--verify", "--quiet", ref], accepted_exit_codes=(0, 1)))


def free_leftovers_branch_name(checkout: Path, today: date) -> str:
    base = f"{LEFTOVERS_BRANCH_PREFIX}{today.isoformat()}"
    name, suffix = base, 1
    while ref_exists(checkout, f"refs/heads/{name}") or ref_exists(checkout,
                                                                  f"refs/remotes/origin/{name}"):
        suffix += 1
        name = f"{base}-{suffix}"
    return name


def local_leftovers_branches(checkout: Path) -> list:
    listed = git(checkout, ["for-each-ref", "--format=%(refname:short)",
                            f"refs/heads/{LEFTOVERS_BRANCH_PREFIX}*"])
    return listed.splitlines()


def ignored_files_at_paths_origin_main_tracks(checkout: Path) -> list:
    ignored = git(checkout, ["ls-files", "-z", "--others", "--ignored", "--exclude-standard"],
                  timeout_seconds=TREE_STEP_TIMEOUT_SECONDS).split("\0")
    ignored = {path for path in ignored if path}
    if not ignored:
        return []
    tracked = git(checkout, ["ls-tree", "-r", "-z", "--name-only", "origin/main"],
                  timeout_seconds=TREE_STEP_TIMEOUT_SECONDS).split("\0")
    return sorted(ignored.intersection(tracked))


def push_failure_text(checkout: Path, branch: str, error: StepFailed) -> str:
    commit = git(checkout, ["rev-parse", f"refs/heads/{branch}"])
    return (f"{error}\nThe leftovers branch {branch}, at commit {commit}, holds leftovers and is "
            "kept in the reference-checkout, but is not on origin. Fix what made the push fail, as "
            "git's message above shows, then run this program again, as python3 "
            f"{Path(__file__).resolve()}: it pushes that same branch.")


def post_merge_hook_run_as_after_a_merge(checkout: Path, head_before_the_switch: str) -> str:
    """Return "" when the clone's post-merge hook succeeded or there is none, else what failed."""
    git(checkout, ["update-ref", "ORIG_HEAD", head_before_the_switch])
    try:
        # The hook's own exit status is needed, which the shared runner does not return.
        finished = subprocess.run(
            ["git", "-C", str(checkout), "hook", "run", "--ignore-missing", "post-merge", "--", "0"],
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            timeout=TREE_STEP_TIMEOUT_SECONDS,
            env=reference_checkout_steps.git_redirecting_removal.environment_without_git_redirecting_variables())
    except (OSError, subprocess.TimeoutExpired) as error:
        return f"`git hook run post-merge` could not be run: {error}"
    if finished.returncode == 0:
        return ""
    return (f"`git hook run post-merge` exited {finished.returncode} after the reference-checkout "
            f"was put on main; the hook printed:\n{(finished.stdout + finished.stderr).strip()}")


def put_reference_checkout_back_on_main(checkout: Path, today: date):
    """Return (origin/main's commit, the leftovers branches pushed); raise StepFailed."""
    reference_checkout_steps.git_fetch_origin_or_raise(checkout)
    changes = git(checkout, ["status", "--porcelain", "--untracked-files=all"])
    commits_origin_main_lacks = int(git(checkout, ["rev-list", "--count", "HEAD", "--not",
                                                   "origin/main"]))
    head_ref = git(checkout, ["symbolic-ref", "-q", "HEAD"], accepted_exit_codes=(0, 1))
    if ref_exists(checkout, "refs/heads/main"):
        main_only = int(git(checkout, ["rev-list", "--count", "refs/heads/main", "--not",
                                       "origin/main", "HEAD"]))
        if main_only:
            raise StepFailed(
                f"the local main of {checkout} has {main_only} commit(s) that neither origin/main "
                "nor HEAD holds; putting main at origin/main would drop them, so nothing was changed")
    in_the_way = ignored_files_at_paths_origin_main_tracks(checkout)
    if in_the_way:
        raise StepFailed(
            f"{checkout} holds {len(in_the_way)} ignored file(s) at paths origin/main tracks, which "
            "putting the checkout on origin/main would overwrite, so nothing was changed: "
            f"{', '.join(in_the_way)}. Move each out of the checkout, keeping any you need, then "
            "run this program again.")
    switch_to_main = head_ref != "refs/heads/main"
    if changes or commits_origin_main_lacks:
        if not head_ref.startswith(f"refs/heads/{LEFTOVERS_BRANCH_PREFIX}"):
            git(checkout, ["switch", "-c", free_leftovers_branch_name(checkout, today)])
            switch_to_main = True
        if changes:
            git(checkout, ["add", "-A"])
            git(checkout, ["commit", "-q", "-m", LEFTOVERS_COMMIT_MESSAGE])
    problems, pushed = [], []
    for branch in local_leftovers_branches(checkout):
        # The pre-push hook's conflict check would refuse the very leftovers this saves; the branch
        # is an archive, never a pull request's head.
        try:
            git(checkout, ["push", "--no-verify", "origin", f"refs/heads/{branch}"],
                timeout_seconds=TREE_STEP_TIMEOUT_SECONDS)
            pushed.append(branch)
        except StepFailed as error:
            problems.append(push_failure_text(checkout, branch, error))
    if switch_to_main:
        head_before_the_switch = git(checkout, ["rev-parse", "HEAD"])
        try:
            git(checkout, ["switch", "-C", "main", "origin/main"],
                timeout_seconds=TREE_STEP_TIMEOUT_SECONDS)
        except StepFailed as error:
            raise StepFailed("\n".join(problems + [str(error)])) from error
        if head_before_the_switch != git(checkout, ["rev-parse", "HEAD"]):
            hook_failure = post_merge_hook_run_as_after_a_merge(checkout, head_before_the_switch)
            if hook_failure:
                problems.append(hook_failure)
    for branch in pushed:
        git(checkout, ["branch", "-D", "-q", branch])
    try:
        main = reference_checkout_steps.fast_forward_to_origin_main_and_check_or_raise(checkout)
    except StepFailed as error:
        raise StepFailed("\n".join(problems + [str(error)])) from error
    if problems:
        raise StepFailed("\n".join(problems + [
            f"The reference-checkout {checkout} is on main at origin/main {main}."]))
    return main, pushed


def reference_checkout_back_on_main_success_line(checkout: Path, main: str, pushed: list) -> str:
    saved = (f"its leftovers are saved on {', '.join(pushed)}, pushed to origin" if pushed
             else "it had no leftovers")
    return f"{PROGRAM}: the reference-checkout {checkout} is on main at origin/main {main}; {saved}."


def reference_checkout_back_on_main_failure_text(checkout: Path, error: StepFailed) -> str:
    return f"{PROGRAM}: a step failed, for the reference-checkout {checkout}: {error}"


def main(argv=None, today=None) -> int:
    argparse.ArgumentParser(
        description="Put the reference-checkout back on main, saving leftovers to a pushed branch.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__).parse_args(argv)
    checkout = reference_checkout_steps.REFERENCE_CHECKOUT
    try:
        main_commit, pushed = put_reference_checkout_back_on_main(checkout, today or date.today())
    except StepFailed as error:
        print(reference_checkout_back_on_main_failure_text(checkout, error), file=sys.stderr)
        return 1
    print(reference_checkout_back_on_main_success_line(checkout, main_commit, pushed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
