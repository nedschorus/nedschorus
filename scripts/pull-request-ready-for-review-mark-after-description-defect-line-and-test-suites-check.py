#!/usr/bin/env python3
"""Mark one draft pull request ready for review, after checking it is fit for review.

Usage: python3 scripts/pull-request-ready-for-review-mark-after-description-defect-line-and-test-suites-check.py <pull request number>

Run it from the pull request's own checkout, with its nc-head-commit checked out. In order, it:
1. reads the pull request with gh, and stops when it is not open, or is already ready for review;
2. refuses when the checkout's HEAD is not the pull request's pushed nc-head-commit, naming the
   one case that applies (another branch is checked out, the pushed commit has not been fetched,
   or the checkout is ahead, behind, or both), or when git status shows an uncommitted change or
   an untracked file that is not ignored, whatever status.showUntrackedFiles says, because the
   test suites would then test files other than the ones under review;
3. refuses a description with no defect line (#root_cause, #root_cause_not_fixed or
   #no_defect_fixed), read by the same reader scripts/merge-gate.sh uses; a placeholder
   description has none;
4. runs this checkout's test suites, with this checkout's own scripts/run-all-test-suites.py, as
   CLAUDE.md says to before pushing, and refuses when any fails;
5. marks the pull request ready for review with gh pr ready.

It does not check what scripts/merge-gate.sh checks again before merging, such as a not-fixed
line's #follow_up link, and it does not stop anyone from marking a pull request ready for
review on GitHub's page. Every refusal comes before step 5, so a refusal changes nothing on
GitHub. A failure of gh, git or python3 is printed with its cause, and exits 1, like a refusal.

Exit codes: 0 marked ready for review, or already was; 1 refused or failed; 2 bad arguments.
"""

import argparse
import importlib.util
import json
import shlex
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
GH_PR_VIEW_NOT_JSON_OUTPUT_ERROR_EXCERPT_CHARACTERS = 300
TEST_RUNNER_EXIT_SOME_SUITE_FAILED = 1
GIT_MERGE_BASE_IS_ANCESTOR_NO = 1
# --untracked-files=normal overrides a status.showUntrackedFiles=no setting, which would hide
# untracked files from the check.
UNCOMMITTED_CHANGES_COMMAND = ["git", "status", "--porcelain", "--untracked-files=normal"]
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


def run_or_failure_cause(argv, runner, timeout, ok_codes):
    """Run argv; return (completed, None) when it exits with one of ok_codes, else (None, the
    cause of the failure in words)."""
    try:
        completed = runner(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                           timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return None, f"{' '.join(argv[:3])} did not answer within {timeout:.0f} seconds"
    except OSError as error:
        return None, f"{argv[0]} could not be run ({error})"
    if completed.returncode in ok_codes:
        return completed, None
    line = first_stderr_line(completed)
    return None, (f"{' '.join(argv[:3])} exited with status {completed.returncode}"
                  + (f": {line}" if line else ", printing no error"))


def run_command(argv, runner, timeout, what, instructions):
    """Run argv for its output; raise StepFailed, ending with instructions, when it cannot run
    or exits nonzero."""
    completed, cause = run_or_failure_cause(argv, runner, timeout, (0,))
    if cause:
        raise StepFailed(f"{what} failed: {cause}.\n{instructions}")
    return completed.stdout or ""


def read_pull_request(number, runner):
    retry = NOTHING_CHANGED_LINE + "\n" + RETRY_THEN_USER_INSTRUCTION.format(number=number)
    text = run_command(["gh", "pr", "view", str(number), "--json",
                        "number,title,url,state,isDraft,headRefOid,headRefName,body"],
                       runner, GH_TIMEOUT_SECONDS, f"reading pull request {number}", retry)
    try:
        pull_request = json.loads(text)
        if not all(field in pull_request
                   for field in ("state", "isDraft", "headRefOid", "headRefName")):
            raise KeyError("state, isDraft, headRefOid or headRefName")
    except (ValueError, KeyError, TypeError):
        raise StepFailed(f"reading pull request {number} failed: gh pr view exited 0 but did not "
                         "print a JSON object holding state, isDraft, headRefOid and headRefName; it printed "
                         f"{text[:GH_PR_VIEW_NOT_JSON_OUTPUT_ERROR_EXCERPT_CHARACTERS]!r}.\n{retry}") from None
    return pull_request


def git_answers_yes(argv, runner, what, instructions,
                    no_codes=(GIT_MERGE_BASE_IS_ANCESTOR_NO,)):
    """Run a git command that answers yes by exiting 0 and no by exiting with one of no_codes;
    raise StepFailed when it exits otherwise or cannot run."""
    completed, cause = run_or_failure_cause(argv, runner, GIT_TIMEOUT_SECONDS,
                                            (0, *no_codes))
    if cause:
        raise StepFailed(f"{what} failed: {cause}.\n{instructions}")
    return completed.returncode == 0


def head_mismatch_next_steps(pull_request, head, runner, git_failed):
    """What to do when the checkout's HEAD is not the pushed head: only the case that applies,
    with commands that name the pull request's branch."""
    branch = pull_request["headRefName"]
    quoted = shlex.quote(branch)
    pushed = str(pull_request["headRefOid"])
    current = run_command(["git", "branch", "--show-current"], runner, GIT_TIMEOUT_SECONDS,
                          "reading this checkout's branch", git_failed).strip()
    if current != branch:
        on = f"branch {current}" if current else "a detached HEAD"
        return (f"This checkout is on {on}, not the pull request's branch {branch}: run this "
                f"again from the checkout that has {branch} checked out; git worktree list "
                f"names each checkout of this clone with its branch.")
    # rev-parse --verify --quiet exits 1, silently, only for a commit this clone lacks; an object
    # that is there but unreadable exits 128 with an error, which is a failure, not "not fetched".
    pushed_is_here = git_answers_yes(
        ["git", "rev-parse", "--verify", "--quiet", pushed + "^{commit}"], runner,
        "looking for the pushed nc-head-commit in this checkout", git_failed)
    if not pushed_is_here:
        return (f"This checkout does not have the pushed commit yet: run git fetch origin "
                f"{quoted}, then run this again, and it names what to do next.")
    comparing = "comparing this checkout's HEAD with the pushed nc-head-commit"
    if git_answers_yes(["git", "merge-base", "--is-ancestor", pushed, head], runner, comparing,
                       git_failed):
        return (f"This checkout has commits the pull request lacks: push them with git push "
                f"origin HEAD:{quoted}, then run this again.")
    if git_answers_yes(["git", "merge-base", "--is-ancestor", head, pushed], runner, comparing,
                       git_failed):
        return (f"The pull request has commits this checkout lacks: run git pull --ff-only "
                f"origin {quoted}, then run this again.")
    return (f"This checkout and the pull request each have commits the other lacks: run git "
            f"pull --no-rebase origin {quoted}, which merges the pull request's commits into "
            f"this checkout, then git push origin HEAD:{quoted}, then run this again.\n"
            "If git reports a merge conflict: stop, run git merge --abort, and tell the user, or "
            "the agent that dispatched you, which files conflict.")


def check_and_mark_ready(number, runner, output):
    pull_request = read_pull_request(number, runner)
    name = f"#{number} ({pull_request.get('url')})"
    if pull_request["state"] != "OPEN":
        state = str(pull_request["state"]).lower()
        if state == "merged":
            next_steps = ("If you meant this one: its review is over, so there is nothing to "
                          "mark.")
        elif state == "closed":
            next_steps = (
                "If you meant this one: do not reopen it yourself. Tell the user, in one "
                "sentence, that it is closed and you meant to mark it ready for review, and ask "
                "whether to reopen it; if you are a subagent, tell the agent that dispatched you "
                f"instead.\nIf the answer is yes: run gh pr reopen {number}, then run this "
                "again.\nIf the answer is no: leave it closed, and do not run this again for it.")
        else:
            next_steps = ("If you meant this one: tell the user, in one sentence, that gh "
                          f"reports its state as {state!r}; if you are a subagent, tell the "
                          "agent that dispatched you instead.")
        raise StepFailed(f"{name} is {state}, not open, so it cannot be marked ready for review. "
                         f"{NOTHING_CHANGED_LINE}\n"
                         "If you meant another pull request: run this again with its number.\n"
                         + next_steps)
    if pull_request["isDraft"] is not True:
        output.write(MESSAGE_PREFIX + f"{name} is already ready for review, so it was left as "
                     "it is.\n")
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
            + head_mismatch_next_steps(pull_request, head, runner, rev_parse_failed))
    changed = run_command(
        UNCOMMITTED_CHANGES_COMMAND, runner, GIT_TIMEOUT_SECONDS,
        "reading this checkout's uncommitted changes", rev_parse_failed).splitlines()
    if changed:
        raise StepFailed(
            f"this checkout has {len(changed)} uncommitted change(s), so the test suites would "
            f"test files that are not in {name}'s pushed commits. {NOTHING_CHANGED_LINE}\n"
            "The changes, as git status --porcelain lists them:\n"
            + "".join(f"  {line.strip()}\n" for line in changed)
            + "If the changes belong in the pull request: commit them, run the test suites and "
            "the mutation pass that CLAUDE.md asks for before a push, push with git push origin "
            f"HEAD:{shlex.quote(pull_request['headRefName'])}, then run this again.\n"
            "If they do not: set them aside with git stash push -u -m <a name of your own>, then "
            "run this again. Once this command has marked the pull request ready, bring them "
            "back: find your entry's commit, the first "
            "word of the line that ends with the name you gave with -m, with git stash list --format='%H %gs', "
            "and run git stash apply <that commit>.\n"
            "If the apply reports a conflict: keep the stash entry, and tell the user, or the "
            "agent that dispatched you, which files conflict.\n"
            "If the apply succeeds: find the entry's current stash@{<n>} on the line that ends "
            "with the name you gave with -m, with git stash list, and drop it with git stash drop "
            "stash@{<n>}.")
    if not defect_line_reader.pull_request_description_defect_lines(pull_request.get("body") or ""):
        raise StepFailed(
            f"{name}'s description has no line beginning \"#root_cause\", "
            "\"#root_cause_not_fixed\" or \"#no_defect_fixed\", so it is still a placeholder, "
            "or does not say whether the pull request fixes a defect, and scripts/merge-gate.sh "
            f"would refuse to merge it. {NOTHING_CHANGED_LINE}\n"
            "Write the current description to a file outside this repository, such as a file in "
            f"your scratchpad, with gh pr view {number} --json body -q .body > <file>. Add to that "
            "file, for each defect the pull request fixes, a line \"#root_cause <the cause the "
            "change removes>\", or, when the cause stays or was not found, \"#root_cause_not_fixed "
            "<the cause that stays, or that it was not found, and why> #follow_up <full "
            "https://github.com/ link to the issue or pull request that will fix it or look for "
            "it>\"; when neither exists yet, file an issue with the /ghi-write skill first. When "
            "the pull request fixes no defect, add the line \"#no_defect_fixed\". Put each such "
            "line on a line of its own, anywhere in the description, such as at its end. Replace "
            "any placeholder text with what the pull request changes, because its reviewers read "
            "the description once it is ready for review; this command checks only the defect "
            "lines. Then upload the "
            f"file with gh pr edit {number} --body-file <file>, which replaces the whole "
            "description, and run this again.")
    command = selective_test_run_command(checkout)
    output.write(MESSAGE_PREFIX + "running " + " ".join(command[1:]) + "\n")
    output.flush()
    try:
        status = runner(command, check=False).returncode
    except OSError as error:
        raise StepFailed(f"running the test suites failed: python3 could not be run ({error}). "
                         f"{NOTHING_CHANGED_LINE}\n"
                         + RETRY_THEN_USER_INSTRUCTION.format(number=number)) from None
    stays_a_draft = (f"so {name} stays a draft pull request: its pushed commits must pass the "
                     "test suites before it is marked ready for review, which starts their review.")
    if status == TEST_RUNNER_EXIT_SOME_SUITE_FAILED:
        raise StepFailed(
            f"the test suites exited with status {status}, {stays_a_draft} The failing suites "
            "are named above.\n"
            "Fix the cause of each suite's failure and commit the fix. Before you push it, run "
            "the test suites and the mutation pass that CLAUDE.md asks for before a push; then "
            "push, and run this again.\n"
            "If git or a pre-push hook refuses the push: do what its message says, then run this "
            "again; if it names nothing to do, tell the user, or the agent that dispatched you, "
            "what it printed.")
    if status != 0:
        raise StepFailed(
            f"scripts/run-all-test-suites.py exited with status {status}, before judging every "
            "suite, "
            f"{stays_a_draft} Its error is above.\n"
            + RETRY_THEN_USER_INSTRUCTION.format(number=number))
    run_command(
        ["gh", "pr", "ready", str(number)], runner, GH_TIMEOUT_SECONDS,
        f"marking {name} ready for review",
        "The test suites passed, but GitHub may or may not have marked it ready for review. "
        "Running this command again finds out: it says so when the pull request is already "
        "ready for review, and otherwise runs the test suites again before gh pr ready.\n"
        + RETRY_THEN_USER_INSTRUCTION.format(number=number))
    output.write(MESSAGE_PREFIX + f"{name} is marked ready for review.\n")


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
