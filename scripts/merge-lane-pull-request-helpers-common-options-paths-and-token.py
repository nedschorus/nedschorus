"""What the merge-lane pull request helpers share: their directory options, path resolution and the merge account's token.

Loaded by path by the five merge-lane-pull-request-* and
merge-lane-code-review-* scripts beside it; not run on its own.

Every path option is made absolute when the arguments are parsed, before any
script changes directory or hands a path to git -C, so a relative path means
the same directory everywhere a script uses it.

The merge account's token is read from the one file merge-gate.sh reads, so
the gate, the retargets, the merge and every other gh call use one token.
"""

import importlib.util
from pathlib import Path

REPOSITORY = "nedschorus/nedschorus"
DEFAULT_MERGE_LANE_WORKTREES_AND_OUTPUTS_DIRECTORY = Path(
    "/home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers")

_runner_spec = importlib.util.spec_from_file_location(
    "run_all_test_suites", Path(__file__).resolve().with_name("run-all-test-suites.py"))
run_all_test_suites = importlib.util.module_from_spec(_runner_spec)
_runner_spec.loader.exec_module(run_all_test_suites)


class MergeAccountTokenUnusable(Exception):
    pass


def merge_account_token_file():
    # Read at call time, as merge-gate.sh reads $HOME at run time.
    return Path.home() / ".config" / "nedschorus" / "ned-review-merge.token"


def read_merge_account_token():
    """Return the merge account's token, or raise MergeAccountTokenUnusable naming why."""
    token_file = merge_account_token_file()
    try:
        token = token_file.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise MergeAccountTokenUnusable(
            f"could not read the merge account's token at {token_file}: "
            f"{error.strerror or error}") from error
    # An empty GH_TOKEN makes gh fall back to its stored account.
    if not token:
        raise MergeAccountTokenUnusable(f"the token file {token_file} is empty")
    return token


def add_directory_options(parser, holds):
    parser.add_argument("--merge-lane-worktrees-and-outputs-directory", type=Path,
                        default=DEFAULT_MERGE_LANE_WORKTREES_AND_OUTPUTS_DIRECTORY,
                        help=f"holds {holds} "
                             f"(default: {DEFAULT_MERGE_LANE_WORKTREES_AND_OUTPUTS_DIRECTORY})")
    parser.add_argument("--review-tools-worktree-at-main", type=Path,
                        help="the checkout at main whose scripts run, never the pull "
                             "request's own (default: "
                             "<merge-lane-worktrees-and-outputs-directory>/wt/main)")


def review_tool_missing_message(arguments, relative_path):
    """Return None when the review tools worktree holds relative_path; else what to do."""
    worktree = arguments.review_tools_worktree_at_main
    tool = worktree / relative_path
    if tool.is_file():
        return None
    # Without this check a missing tool surfaces as the interpreter's own exit
    # code, which the callers' exit codes do not document.
    return (f"{tool} is missing, so --review-tools-worktree-at-main, {worktree}, is not a "
            f"checkout of main.\n"
            f"If {worktree} exists, move it to main: git -C {worktree} fetch origin && "
            f"git -C {worktree} checkout --detach origin/main\n"
            f"If {worktree} does not exist, make it from any clone of this repository: "
            f"git -C <clone> worktree add --detach {worktree} origin/main\n"
            f"Then run this again.")


def resolve_path_options(arguments):
    """Make every Path argument absolute, then default the review tools worktree."""
    for name, value in vars(arguments).items():
        if isinstance(value, Path):
            setattr(arguments, name, value.resolve())
    if arguments.review_tools_worktree_at_main is None:
        arguments.review_tools_worktree_at_main = (
            arguments.merge_lane_worktrees_and_outputs_directory / "wt" / "main")
    return arguments
