#!/usr/bin/env python3
"""Mark one draft pull request ready for review, after checking it is fit for review.

Usage: python3 scripts/pull-request-ready-for-review-mark-after-description-defect-line-and-test-suites-check.py <pull request number>

Run it from the pull request's own checkout, with its nc-head-commit checked out. In order, it:
1. reads the pull request with gh, and stops when it is not open, or is already ready for review;
2. refuses when the checkout's HEAD is not the pull request's pushed nc-head-commit, because the
   test suites would then test commits other than the ones under review;
3. refuses a description with no defect line (#root_cause, #root_cause_not_fixed or
   #no_defect_fixed), read by the same reader scripts/merge-gate.sh uses; a placeholder
   description has none;
4. runs this checkout's test suites, with this checkout's own scripts/run-all-test-suites.py, as
   CLAUDE.md says to before pushing, and refuses when any fails;
5. marks the pull request ready for review with gh pr ready.

It does not check what scripts/merge-gate.sh checks again before merging, such as a not-fixed
line's #follow_up link, and it does not stop anyone from marking a pull request ready for
review on GitHub's page. The test suites run on the working tree, so uncommitted changes in it
are tested too, as in the test run before a push. Every refusal comes before step 5, so a refusal changes nothing on
GitHub. A failure of gh, git or python3 is printed with its cause, and exits 1, like a refusal.

Exit codes: 0 marked ready for review, or already was; 1 refused or failed; 2 bad arguments.
"""

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
_defect_line_reader_spec = importlib.util.spec_from_file_location(
    "pull_request_description_defect_line_root_cause_status_and_follow_up_link_reader",
    SCRIPTS_DIRECTORY / "pull-request-description-defect-line-root-cause-status-and-follow-up-link-reader.py")
defect_line_reader = importlib.util.module_from_spec(_defect_line_reader_spec)
_defect_line_reader_spec.loader.exec_module(defect_line_reader)

EXIT_MARKED_READY = 0
EXIT_MARK_READY_REFUSED_OR_FAILED = 1
GH_TIMEOUT_SECONDS = 60.0
GIT_TIMEOUT_SECONDS = 30.0
MESSAGE_PREFIX = "pull request ready for review: "
# Messages follow docs/nedschorus-wiki/nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md.
NOTHING_CHANGED_LINE = "Nothing was changed on GitHub."
RETRY_THEN_USER_INSTRUCTION = (
    "Run this command again once. If it fails the same way, tell the user, in one sentence, that "
    "pull request {number} could not be marked ready for review, quoting the error above; if you "
    "are a subagent, tell the agent that dispatched you instead.")


class StepFailed(Exception):
    """A step refused the pull request, or could not run; the message says which and why."""


def selective_test_run_command(checkout):
    """The test run CLAUDE.md asks for before a push, with checkout's own runner, which tests
    the checkout it sits in; the runner beside this program may sit in another checkout."""
    return ["python3", str(Path(checkout) / "scripts" / "run-all-test-suites.py"),
            "--only-suites-whose-recorded-inputs-changed-since", "origin/main"]


def first_stderr_line(completed):
    return ((completed.stderr or "").strip().splitlines() or [""])[0]


def run_command(argv, runner, timeout, what, instructions):
    """Run argv for its output; raise StepFailed, ending with instructions, when it cannot run
    or exits nonzero."""
    try:
        completed = runner(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                           timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        cause = f"{' '.join(argv[:3])} did not answer within {timeout:.0f} seconds"
    except OSError as error:
        cause = f"{argv[0]} could not be run ({error})"
    else:
        if completed.returncode == 0:
            return completed.stdout or ""
        line = first_stderr_line(completed)
        cause = (f"{' '.join(argv[:3])} exited with status {completed.returncode}"
                 + (f": {line}" if line else ", printing no error"))
    raise StepFailed(f"{what} failed: {cause}.\n{instructions}")


def read_pull_request(number, runner):
    retry = NOTHING_CHANGED_LINE + "\n" + RETRY_THEN_USER_INSTRUCTION.format(number=number)
    text = run_command(["gh", "pr", "view", str(number), "--json",
                        "number,title,url,state,isDraft,headRefOid,body"],
                       runner, GH_TIMEOUT_SECONDS, f"reading pull request {number}", retry)
    try:
        pull_request = json.loads(text)
        if not all(field in pull_request for field in ("state", "isDraft", "headRefOid")):
            raise KeyError("state, isDraft or headRefOid")
    except (ValueError, KeyError, TypeError):
        raise StepFailed(f"reading pull request {number} failed: gh pr view did not print a JSON "
                         f"object holding state, isDraft and headRefOid.\n{retry}") from None
    return pull_request


def check_and_mark_ready(number, runner, output):
    pull_request = read_pull_request(number, runner)
    name = f"#{number} ({pull_request.get('url')})"
    send_to_merge_lane = (f"Send merge-lane-2 the pull request's title, \"{pull_request.get('title')}\", "
                          f"and link, {pull_request.get('url')}, with SendMessage, unless you "
                          "already have since it was marked ready for review: its watcher of "
                          "open pull requests reports a new head commit, not a draft marked ready "
                          "for review.")
    if pull_request["state"] != "OPEN":
        raise StepFailed(f"{name} is {str(pull_request['state']).lower()}, not open, so it cannot "
                         f"be marked ready for review. {NOTHING_CHANGED_LINE}\n"
                         "If you meant another pull request: run this again with its number.")
    if pull_request["isDraft"] is not True:
        output.write(MESSAGE_PREFIX + f"{name} is already ready for review, so it was left as "
                     f"it is.\n{send_to_merge_lane}\n")
        return
    rev_parse_failed = (
        NOTHING_CHANGED_LINE + "\n"
        "If git's error says this is not a git repository: run this again from the pull "
        "request's own checkout.\n"
        "If git gave any other error: " + RETRY_THEN_USER_INSTRUCTION.format(number=number))
    printed = run_command(
        ["git", "rev-parse", "--show-toplevel", "HEAD"], runner, GIT_TIMEOUT_SECONDS,
        "reading this checkout's HEAD", rev_parse_failed).splitlines()
    if len(printed) != 2:
        raise StepFailed("reading this checkout's HEAD failed: git rev-parse --show-toplevel HEAD "
                         f"printed {len(printed)} lines, not 2.\n{rev_parse_failed}")
    checkout, head = printed
    if head != pull_request["headRefOid"]:
        raise StepFailed(
            f"this checkout's HEAD, {head[:12]}, is not {name}'s pushed nc-head-commit, "
            f"{str(pull_request['headRefOid'])[:12]}, so the test suites would not test the "
            f"commits under review. {NOTHING_CHANGED_LINE}\n"
            "If this checkout has commits the pull request lacks: push them, then run this "
            "again.\n"
            "If the pull request has commits this checkout lacks: run git pull --ff-only, then "
            "run this again.\n"
            "If you are in another checkout: run this again from the pull request's own "
            "checkout.")
    if not defect_line_reader.pull_request_description_defect_lines(pull_request.get("body") or ""):
        raise StepFailed(
            f"{name}'s description has no line beginning \"#root_cause\", "
            "\"#root_cause_not_fixed\" or \"#no_defect_fixed\", so it is still a placeholder, "
            "or does not say whether the pull request fixes a defect, and scripts/merge-gate.sh "
            f"would refuse to merge it. {NOTHING_CHANGED_LINE}\n"
            "Write the whole description, with one of those lines, in a file, save it with gh pr "
            f"edit {number} --body-file <that file>, which replaces the old description, then "
            "run this again.")
    command = selective_test_run_command(checkout)
    output.write(MESSAGE_PREFIX + "running " + " ".join(command[1:]) + "\n")
    output.flush()
    try:
        status = runner(command, check=False).returncode
    except OSError as error:
        raise StepFailed(f"running the test suites failed: python3 could not be run ({error}). "
                         f"{NOTHING_CHANGED_LINE}\n"
                         + RETRY_THEN_USER_INSTRUCTION.format(number=number)) from None
    if status != 0:
        raise StepFailed(
            f"the test suites exited with status {status}, so {name} stays a draft pull "
            "request, because a pull request marked ready for review is reviewed as it stands. "
            "The failing suites are named above.\n"
            "Fix them, commit and push the fix, then run this again.")
    run_command(
        ["gh", "pr", "ready", str(number)], runner, GH_TIMEOUT_SECONDS,
        f"marking {name} ready for review",
        "The test suites passed, but GitHub may or may not have marked it ready for review. "
        "Running this command again finds out: it says so when the pull request is already "
        "ready for review, and otherwise runs the test suites again before gh pr ready.\n"
        + RETRY_THEN_USER_INSTRUCTION.format(number=number))
    output.write(MESSAGE_PREFIX + f"{name} is marked ready for review.\n{send_to_merge_lane}\n")


def main(argv=None, runner=subprocess.run, output=sys.stdout, errors=sys.stderr):
    parser = argparse.ArgumentParser(
        description="Mark one draft pull request ready for review, after checking that this "
                    "checkout's HEAD is its pushed nc-head-commit, that its description has a "
                    "defect line, and that the test suites pass.")
    parser.add_argument("pull_request_number", type=int)
    arguments = parser.parse_args(argv)
    try:
        check_and_mark_ready(arguments.pull_request_number, runner, output)
    except StepFailed as refusal:
        errors.write(MESSAGE_PREFIX + str(refusal) + "\n")
        return EXIT_MARK_READY_REFUSED_OR_FAILED
    return EXIT_MARKED_READY


if __name__ == "__main__":
    sys.exit(main())
