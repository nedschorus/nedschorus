#!/usr/bin/env python3
"""The reference-checkout ~/Projects/nedschorus, and the git steps that put it at origin/main.

Used by handoff-supervisor-restart-onto-main-code-by-relaunch-from-reference-checkout.py, whose
step 0 fetches and fast-forwards the reference-checkout, and by
handoff-reference-checkout-back-on-main-after-pushing-leftovers-to-a-branch.py, which ends with the
same fast-forward and check after saving any leftovers; handoff-supervisor.py takes
REFERENCE_CHECKOUT from it, to tell a reference-checkout's notice from another's. Each step raises
ReferenceCheckoutGitStepFailed, whose message names the git command and quotes what git printed.
git runs with the variables that redirect it to another repository removed.

Load it by path, under the snake_case form of its file name:

    spec = importlib.util.spec_from_file_location(
        "handoff_reference_checkout_fetch_and_fast_forward_to_origin_main_check_common", <path>)
"""

# Deferred annotations let the module load on the Mac's system Python 3.9.
from __future__ import annotations

import importlib.util
from pathlib import Path

_GENERAL_TOOLS_DIRECTORY = Path(__file__).resolve().parents[1] / "general-tools"


def _load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


git_output = _load_module(
    "git_machine_readable_output_runner_and_parser_common",
    _GENERAL_TOOLS_DIRECTORY / "git-machine-readable-output-runner-and-parser-common.py")
git_redirecting_removal = _load_module(
    "git_redirecting_environment_variables_removal_common",
    _GENERAL_TOOLS_DIRECTORY / "git-redirecting-environment-variables-removal-common.py")

REFERENCE_CHECKOUT = Path("~/Projects/nedschorus").expanduser()
# A fetch, a push or a fast-forward of the whole repository can take minutes on a slow link.
NETWORK_OR_TREE_GIT_STEP_TIMEOUT_SECONDS = 300
GIT_STEP_TIMEOUT_SECONDS = 60


class ReferenceCheckoutGitStepFailed(Exception):
    """A git step on the reference-checkout failed; the message says which and what git printed."""


def reference_checkout_git_output_or_raise(checkout: Path, arguments, *,
                                           timeout_seconds=GIT_STEP_TIMEOUT_SECONDS,
                                           accepted_exit_codes=(0,)) -> str:
    """Run `git -C <checkout> <arguments>` and return its standard output, stripped."""
    try:
        return git_output.run_git(
            checkout, arguments, timeout_seconds=timeout_seconds,
            accepted_exit_codes=accepted_exit_codes,
            environment=git_redirecting_removal.environment_without_git_redirecting_variables(),
        ).decode(errors="replace").strip()
    except git_output.GitCommandFailed as error:
        raise ReferenceCheckoutGitStepFailed(str(error)) from None


def git_fetch_origin_or_raise(checkout: Path) -> None:
    reference_checkout_git_output_or_raise(
        checkout, ["fetch", "origin"], timeout_seconds=NETWORK_OR_TREE_GIT_STEP_TIMEOUT_SECONDS)


def fast_forward_to_origin_main_and_check_or_raise(checkout: Path) -> str:
    """Fast-forward the checked-out branch to origin/main, as last fetched, and check that HEAD
    is origin/main and that no tracked file is changed; return origin/main's commit."""
    reference_checkout_git_output_or_raise(
        checkout, ["merge", "--ff-only", "origin/main"],
        timeout_seconds=NETWORK_OR_TREE_GIT_STEP_TIMEOUT_SECONDS)
    head = reference_checkout_git_output_or_raise(checkout, ["rev-parse", "HEAD"])
    main = reference_checkout_git_output_or_raise(checkout, ["rev-parse", "origin/main"])
    if head != main:
        raise ReferenceCheckoutGitStepFailed(
            f"the reference-checkout {checkout} is at {head}, not at origin/main {main}")
    changed = reference_checkout_git_output_or_raise(
        checkout, ["status", "--porcelain", "--untracked-files=no"])
    if changed:
        raise ReferenceCheckoutGitStepFailed(
            f"the reference-checkout {checkout} has changed tracked files:\n{changed}")
    return main
