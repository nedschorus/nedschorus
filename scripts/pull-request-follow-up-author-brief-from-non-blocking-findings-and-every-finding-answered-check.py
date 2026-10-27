#!/usr/bin/env python3
"""Print a pull request author's follow-up brief from merge-lane-2's non-blocking findings, and check every finding is answered.

Usage:
  scripts/pull-request-follow-up-author-brief-from-non-blocking-findings-and-every-finding-answered-check.py <number> [--print-brief-again-after-subagent-died]
  scripts/pull-request-follow-up-author-brief-from-non-blocking-findings-and-every-finding-answered-check.py <number> --check [--answers FILE]

merge-lane-2 ends a merge message that asks for follow-ups with the line
"#follow_up_request pull request <number>", then each non-blocking finding on a
numbered line of its own, "1. ", "2. " and so on. nc-systems/general-tools/pull-request-follow-up-request-from-merge-lane-2-message-save-and-author-brief-run-reminder-user-prompt-submit-hook.py saves that block, word
for word, to SAVED_FINDINGS_FILE_NAME_FORMAT in PULL_REQUEST_FOLLOW_UP_REQUESTS_DIRECTORY_NAME under the
checkout's git common directory, which every worktree of the checkout shares,
and tells the agent to run this program.

Without --check, run in the author's checkout: print the saved findings word for
word, how to dispatch a forked subagent in a git worktree of its own, the rules
it follows to open follow-up pull requests from origin/main, and the --check
command to finish with. The brief is printed once per pull request: a second
invocation refuses until that pull request's --check has passed, unless
--print-brief-again-after-subagent-died is given, and refuses for good once --check has
passed.

With --check, run in the subagent's worktree: read the answers file, by default
ANSWERS_FILE_NAME_FORMAT at the root of the worktree --check runs in, which holds
one entry per finding, each starting "<n>. " on its own line, and is either the
link of the pull request that handles the finding or the reason the finding is
left out. Refuse, naming each finding without an entry, until every finding has
exactly one; then mark the pull request's follow-up request answered and print
the message for merge-lane-2, which the agent sends with SendMessage, since a
program cannot.

Not handled: whether a linked pull request exists or handles its finding, which
merge-lane-2 judges from the message; a block whose findings span more than one
line each, which the hook does not save.

Exit codes: 0 brief printed or every finding answered; 1 refused, said on stderr,
with what to do; 2 git or a file could not be read or written, said on stderr,
and nothing was printed on stdout or marked.
"""

import argparse
import datetime
import importlib.util
import re
import sys
from pathlib import Path

_fix_round_spec = importlib.util.spec_from_file_location(
    "pull_request_fix_round_author_brief_from_blocking_findings_and_one_commit_every_finding_answered_check",
    Path(__file__).resolve().with_name(
        "pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py"))
fix_round = importlib.util.module_from_spec(_fix_round_spec)
_fix_round_spec.loader.exec_module(fix_round)

Refused = fix_round.Refused
StepFailed = fix_round.StepFailed

PROGRAM = "scripts/" + Path(__file__).name
FOLLOW_UP_REQUEST_LINE_PATTERN = re.compile(r"^#follow_up_request pull request (\d+)[ \t]*$")
FINDING_LINE_PATTERN = fix_round.ANSWER_START_PATTERN
PULL_REQUEST_LINK_PATTERN = re.compile(r"https://github\.com/[^/\s]+/[^/\s]+/pull/\d+")
PULL_REQUEST_FOLLOW_UP_REQUESTS_DIRECTORY_NAME = "pull-request-follow-up-requests"
SAVED_FINDINGS_FILE_NAME_FORMAT = "pull-request-{number}-non-blocking-findings.md"
BRIEF_PRINTED_FILE_NAME_FORMAT = "pull-request-{number}-brief-printed-marker"
EVERY_FINDING_ANSWERED_FILE_NAME_FORMAT = "pull-request-{number}-every-finding-answered-check-passed-marker"
ANSWERS_FILE_NAME_FORMAT = "follow-up-answers-pull-request-{number}.md"
RESTART_FLAG = "--print-brief-again-after-subagent-died"
DISPATCH_INSTRUCTION = (
    "For the author: dispatch one subagent now with the Agent tool, as a fork (subagent_type: "
    "\"fork\") with isolation: \"worktree\" and run_in_background: true, so that it works in a git "
    "worktree of its own and its commits cannot pick up edits you make in your checkout while it "
    "works. Give it this whole brief, and tell it that the two paragraphs starting \"For the "
    "author\", indented lines included, are yours, not its.")
WORKTREE_REMOVAL_INSTRUCTION = (
    "For the author, when the subagent has finished: remove its worktree, and then each local "
    "branch the subagent names in its last message. <path> is the worktree's path, which the Agent "
    "tool reports when the subagent finishes.\n"
    + fix_round.SUBAGENT_WORKTREE_REMOVAL_STEP_INSTRUCTION_TEXT
    + "   2. Once the worktree is removed, run git branch -D on each local branch the subagent named.")


class FollowUpRequest:
    """One "#follow_up_request pull request <number>" line and the numbered findings after it."""

    def __init__(self, number, lines):
        self.number = number
        self.lines = lines

    @property
    def text(self):
        return "\n".join(self.lines) + "\n"

    @property
    def finding_count(self):
        return len(self.lines) - 1


def parse_follow_up_request_blocks_from_message_text(text):
    """Every follow-up request block in text, in order.

    A block ends at the first line after its request line that is not a numbered finding. Raises
    ValueError, naming the pull request, for a block whose findings are not numbered 1, 2, 3 and so
    on, or that has none."""
    lines = text.splitlines()
    requests = []
    for index, line in enumerate(lines):
        request = FOLLOW_UP_REQUEST_LINE_PATTERN.match(line)
        if not request:
            continue
        number = int(request.group(1))
        findings = []
        for following in lines[index + 1:]:
            finding = FINDING_LINE_PATTERN.match(following)
            if not finding:
                break
            findings.append(following)
        numbers = [int(FINDING_LINE_PATTERN.match(finding).group(1)) for finding in findings]
        if not findings or numbers != list(range(1, len(findings) + 1)):
            raise ValueError(f"the lines after `#follow_up_request pull request {number}` are not "
                             "findings numbered 1, 2, 3 and so on, one finding to a line")
        requests.append(FollowUpRequest(number, [line, *findings]))
    return requests


def state_directory(directory="."):
    """PULL_REQUEST_FOLLOW_UP_REQUESTS_DIRECTORY_NAME in the git common directory, which the checkout and its worktrees share."""
    try:
        common = fix_round.git_output.run_git(
            directory, ["rev-parse", "--path-format=absolute", "--git-common-dir"]).decode().strip()
    except fix_round.git_output.GitCommandFailed as failure:
        raise StepFailed(f"git {' '.join(failure.arguments)} failed in {directory}: "
                         f"{failure.stderr.strip()}") from None
    return Path(common) / PULL_REQUEST_FOLLOW_UP_REQUESTS_DIRECTORY_NAME


def state_file(directory, name_format, number):
    return directory / name_format.format(number=number)


def read_text_if_present(path):
    try:
        return path.read_text()
    except FileNotFoundError:
        return None
    except OSError as error:
        raise StepFailed(f"could not read {path}: {error}") from None


def write_text(path, text):
    try:
        path.parent.mkdir(exist_ok=True)
        path.write_text(text)
    except OSError as error:
        raise StepFailed(f"could not write {path}: {error}") from None


def save_follow_up_request_and_clear_its_markers(request, directory="."):
    """Save request's block for its pull request, as the hook does. A block that differs from the one
    saved is a new request, so the brief-printed and every-finding-answered marks are removed."""
    states = state_directory(directory)
    saved = state_file(states, SAVED_FINDINGS_FILE_NAME_FORMAT, request.number)
    if read_text_if_present(saved) == request.text:
        return saved
    write_text(saved, request.text)
    for name_format in (BRIEF_PRINTED_FILE_NAME_FORMAT, EVERY_FINDING_ANSWERED_FILE_NAME_FORMAT):
        try:
            state_file(states, name_format, request.number).unlink(missing_ok=True)
        except OSError as error:
            raise StepFailed(f"could not remove {state_file(states, name_format, request.number)}: "
                             f"{error}") from None
    return saved


def saved_follow_up_request(states, number):
    saved = state_file(states, SAVED_FINDINGS_FILE_NAME_FORMAT, number)
    text = read_text_if_present(saved)
    if text is None:
        raise Refused(f"No follow-up request from merge-lane-2 is saved for pull request {number}: "
                      f"{saved} does not exist.\n"
                      "If merge-lane-2's message for that pull request has no line "
                      f"\"#follow_up_request pull request {number}\", there is nothing for this "
                      "program to brief: follow up the message's findings as CLAUDE.md says.\n"
                      "If the message has that line, the hook did not save the block: follow up the "
                      "message's findings as CLAUDE.md says, and tell the user, in one sentence, that "
                      "the follow-up request hook did not save merge-lane-2's findings for pull request "
                      f"{number}.\n"
                      "If you are a subagent, pass that sentence to the agent that dispatched you instead.")
    try:
        requests = parse_follow_up_request_blocks_from_message_text(text)
    except ValueError as error:
        requests, problem = [], str(error)
    else:
        problem = "it does not hold exactly one block, for this pull request"
    if len(requests) != 1 or requests[0].number != number:
        raise StepFailed(f"the saved follow-up request {saved} cannot be read: {problem}")
    return requests[0]


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def print_brief(number, restart):
    states = state_directory()
    request = saved_follow_up_request(states, number)
    answered = read_text_if_present(state_file(states, EVERY_FINDING_ANSWERED_FILE_NAME_FORMAT, number))
    if answered is not None:
        raise Refused(f"merge-lane-2's follow-up request for pull request {number} is already "
                      f"answered: its --check passed at {answered.strip()}.\n"
                      "Do not dispatch another subagent for it. If merge-lane-2 says a finding is "
                      "still open, answer merge-lane-2 with SendMessage.")
    printed = read_text_if_present(state_file(states, BRIEF_PRINTED_FILE_NAME_FORMAT, number))
    if printed is not None and not restart:
        raise Refused(f"The follow-up brief for pull request {number} was already printed at "
                      f"{printed.strip()}, and its --check has not passed, so the subagent it "
                      "dispatched may still be working.\n"
                      "If that subagent is still running, wait for it to finish; do not dispatch "
                      "another.\n"
                      "If that subagent died, or finished without its --check passing, print the "
                      f"brief again with: python3 {PROGRAM} {number} {RESTART_FLAG}")
    write_text(state_file(states, BRIEF_PRINTED_FILE_NAME_FORMAT, number), now() + "\n")
    answers_name = ANSWERS_FILE_NAME_FORMAT.format(number=number)
    lines = [
        f"Follow-up brief for pull request {number}",
        f"merge-lane-2 merged pull request {number} and sent {request.finding_count} non-blocking "
        "findings to follow up, word for word:",
        "",
        *request.lines,
        "",
        DISPATCH_INSTRUCTION,
        WORKTREE_REMOVAL_INSTRUCTION,
        "",
        "For the subagent, the rules, in order, run in your own worktree:",
        "1. CLAUDE.md applies to every step, its rules on atomic pull requests, names, tests, "
        "mutation testing and pull request descriptions included.",
        "2. Run git fetch origin, then check each finding against the code on origin/main, which "
        f"already holds pull request {number}. Take on each finding that holds, root cause included; "
        "for each finding you leave out, such as one already fixed or a guard CLAUDE.md's rule on "
        "guards does not call for, note the reason.",
        "3. Findings on one topic go in one pull request; findings on unrelated topics may go in "
        "separate pull requests.",
        "4. For each pull request, starting from origin/main: git switch -c <topic-branch> origin/main, "
        "make the change with its tests, run "
        f"{fix_round.PRE_PUSH_TEST_COMMAND}, commit, push with git push -u origin <topic-branch>, "
        "and open the pull request with gh pr create.",
        f"5. Write the answers file {answers_name} at the root of your worktree, one entry per "
        "finding above, each starting \"<n>. \" on its own line: the link of the pull request that "
        "handles the finding, or the reason the finding is left out. Never commit it.",
        f"6. Run: python3 {PROGRAM} {number} --check",
        "   If it refuses, change the answers file as it says and run it again.",
        "7. When it passes, send the message it prints to merge-lane-2 with SendMessage. End with a "
        "last message that names each local branch you made, for the author to remove.",
    ]
    print("\n".join(lines))


def default_answers_path(number):
    """The answers file at the root of the worktree or checkout this runs in."""
    top_level = fix_round.git(["rev-parse", "--show-toplevel"]).strip()
    return Path(top_level) / ANSWERS_FILE_NAME_FORMAT.format(number=number)


def check_every_finding_answered(number, answers_path):
    states = state_directory()
    request = saved_follow_up_request(states, number)
    answers = fix_round.read_answers(answers_path or default_answers_path(number), request.finding_count,
                                     findings_described=f"merge-lane-2 sent {request.finding_count} "
                                                        "findings")
    linked = sum(1 for answer in answers.values() if PULL_REQUEST_LINK_PATTERN.search(answer))
    write_text(state_file(states, EVERY_FINDING_ANSWERED_FILE_NAME_FORMAT, number), now() + "\n")
    message = [f"Follow-ups on pull request {number}, answering merge-lane-2's #follow_up_request "
               f"pull request {number}: {linked} of {request.finding_count} findings answered with a "
               "pull request link, the others with a reason.",
               *(f"{index}. {answer}" for index, answer in answers.items())]
    print("\n".join([f"PASS: each of the {request.finding_count} findings merge-lane-2 sent for pull "
                     f"request {number} has an answer.",
                     "", "Send merge-lane-2 this message with SendMessage:", "", *message]))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Print a pull request author's follow-up brief from the non-blocking findings "
                    "merge-lane-2 sent after merging, or with --check, check every finding is answered.")
    parser.add_argument("number", type=int, help="the merged pull request's number")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true",
                      help="check the answers file instead of printing the brief")
    mode.add_argument(RESTART_FLAG, action="store_true",
                      help="print the brief again although it was printed before and its --check "
                           "has not passed, because the subagent it dispatched died")
    parser.add_argument("--answers",
                        help="with --check: the answers file, one \"<n>. \" entry per finding "
                             "(default: " + ANSWERS_FILE_NAME_FORMAT.format(number="<number>")
                             + " at the root of this worktree)")
    arguments = parser.parse_args(argv)
    try:
        if arguments.check:
            check_every_finding_answered(arguments.number, arguments.answers)
        else:
            print_brief(arguments.number, arguments.print_brief_again_after_subagent_died)
    except Refused as refusal:
        print(f"REFUSED: {refusal}", file=sys.stderr)
        return 1
    except StepFailed as failure:
        print(f"FAILED: {failure}\n"
              "This program stopped there: it printed no brief and marked nothing answered.\n"
              "Run the same command again once.\n"
              "If it fails the same way, tell the user, in one sentence, which file or git command "
              f"failed and that the follow-up of pull request {arguments.number} is stopped until it "
              "works.\n"
              "If you are a subagent, pass that sentence to the agent that dispatched you instead.",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
