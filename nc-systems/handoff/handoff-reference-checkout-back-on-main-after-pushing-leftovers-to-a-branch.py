#!/usr/bin/env python3
"""Put the reference-checkout ~/Projects/nedschorus back on main, first saving any leftovers to a pushed branch.

Usage, on the machine whose reference-checkout will not fast-forward to main:
  python3 ~/Projects/nedschorus/nc-systems/handoff/handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch.py

The handoff-supervisor restarts itself on main's code at a session-handoff only when its checkout
fast-forwards to main or is current with it, and its not-restarted notice names this program when
the reference-checkout is that checkout and does neither. No agent works in the reference-checkout,
so what stops it is left over.

The program:
- fetches origin;
- finds the leftovers: uncommitted changes, untracked files included, and commits on HEAD that
  origin/main lacks;
- when there are any, switches to a new branch reference-checkout-leftovers-<YYYY-MM-DD>, with -2,
  -3 and so on added when a local branch or a branch on origin already has that name, commits the
  changes there if there are any, and pushes the branch to origin;
- only after the push succeeds, or when there were no leftovers and HEAD is not on main, runs
  `git switch -C main origin/main`, which puts the local main at origin/main and checks it out;
- fast-forwards to origin/main and checks that HEAD is origin/main with no changed tracked file,
  with the same shared function as the restart program's step 0.
It prints the leftovers branch's name, or that there were none. On a checkout already on main, at
origin/main and with nothing uncommitted, it changes nothing, so it can be run again to check a fix.

What it does not handle:
- a merge, rebase, cherry-pick or revert in progress, or a lock another git process holds, such as
  index.lock: git refuses the step, and the program fails as below;
- ignored files: they are neither saved nor removed;
- commits on the local main that neither origin/main nor HEAD holds, when HEAD is not on main:
  switching main to origin/main would drop them, so the program fails before changing anything.

How it fails: it prints the failed step and what git printed to standard error and exits 1, and runs
no step after the failed one. A failed fetch, or local main's own commits, change nothing. A failed
push leaves the checkout on the leftovers branch, holding the commit, with main untouched; run again,
it saves the same leftovers to a branch with the next suffix. It changes the clone every agent-seat's
worktrees hang off, but moves main only after the push holds whatever main is moved away from.

Exit status: 0 on main at origin/main; 1 a step failed.
"""

import argparse
import importlib.util
import sys
from datetime import date
from pathlib import Path

SYSTEM_DIRECTORY = Path(__file__).resolve().parent
_reference_checkout_steps_spec = importlib.util.spec_from_file_location(
    "handoff_reference_checkout_fetch_and_fast_forward_to_origin_main_check_common",
    SYSTEM_DIRECTORY / "handoff-reference-checkout-fetch-and-fast-forward-to-origin-main-check-common.py")
reference_checkout_steps = importlib.util.module_from_spec(_reference_checkout_steps_spec)
_reference_checkout_steps_spec.loader.exec_module(reference_checkout_steps)

PROGRAM = "handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch"
LEFTOVERS_BRANCH_PREFIX = "reference-checkout-leftovers-"
LEFTOVERS_COMMIT_MESSAGE = "Leftovers found in the reference-checkout"
StepFailed = reference_checkout_steps.ReferenceCheckoutGitStepFailed


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


def save_leftovers_to_pushed_branch(checkout: Path, today: date, changes: str) -> str:
    branch = free_leftovers_branch_name(checkout, today)
    git(checkout, ["switch", "-c", branch])
    if changes:
        git(checkout, ["add", "-A"])
        git(checkout, ["commit", "-q", "-m", LEFTOVERS_COMMIT_MESSAGE])
    git(checkout, ["push", "origin", f"refs/heads/{branch}"],
        timeout_seconds=reference_checkout_steps.NETWORK_OR_TREE_GIT_STEP_TIMEOUT_SECONDS)
    return branch


def put_reference_checkout_back_on_main(checkout: Path, today: date) -> str:
    """Return the line to print on success; raise StepFailed, having run no later step."""
    reference_checkout_steps.git_fetch_origin_or_raise(checkout)
    changes = git(checkout, ["status", "--porcelain", "--untracked-files=all"])
    commits_origin_main_lacks = int(git(checkout, ["rev-list", "--count", "HEAD", "--not",
                                                   "origin/main"]))
    on_main = git(checkout, ["symbolic-ref", "-q", "HEAD"], accepted_exit_codes=(0, 1)) == "refs/heads/main"
    if ref_exists(checkout, "refs/heads/main"):
        main_only = int(git(checkout, ["rev-list", "--count", "refs/heads/main", "--not",
                                       "origin/main", "HEAD"]))
        if main_only:
            raise StepFailed(
                f"the local main of {checkout} has {main_only} commit(s) that neither origin/main "
                "nor HEAD holds; putting main at origin/main would drop them, so nothing was changed")
    branch = None
    if changes or commits_origin_main_lacks:
        branch = save_leftovers_to_pushed_branch(checkout, today, changes)
    if branch or not on_main:
        git(checkout, ["switch", "-C", "main", "origin/main"],
            timeout_seconds=reference_checkout_steps.NETWORK_OR_TREE_GIT_STEP_TIMEOUT_SECONDS)
    main = reference_checkout_steps.fast_forward_to_origin_main_and_check_or_raise(checkout)
    saved = (f"its leftovers are saved on the branch {branch}, pushed to origin" if branch
             else "it had no leftovers")
    return f"{PROGRAM}: the reference-checkout {checkout} is on main at origin/main {main}; {saved}."


def main(argv=None, today=None) -> int:
    argparse.ArgumentParser(
        description="Put the reference-checkout back on main, saving leftovers to a pushed branch.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__).parse_args(argv)
    checkout = reference_checkout_steps.REFERENCE_CHECKOUT
    try:
        print(put_reference_checkout_back_on_main(checkout, today or date.today()))
    except StepFailed as error:
        print(f"{PROGRAM}: the reference-checkout {checkout} was not put back on main; the step that "
              f"failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
