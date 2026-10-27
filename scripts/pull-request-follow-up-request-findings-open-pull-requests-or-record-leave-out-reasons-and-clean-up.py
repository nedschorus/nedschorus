#!/usr/bin/env python3
"""Do the mechanical steps of following up the non-blocking findings merge-lane-2 sends after merging a pull request.

Usage:
  PROGRAM <number> start-topic-branch <topic-branch>
  PROGRAM <number> open-pull-request --handled-finding-numbers <n>[,<n>...]
  PROGRAM <number> record-finding-leave-out-reason <n> --reason "<why>"
  PROGRAM <number> finish-follow-up-request-and-print-merge-lane-2-message
  PROGRAM <number> remove-recorded-topic-branches-and-worktrees

merge-lane-2 ends a merge message that asks for follow-ups with the line
"#follow_up_request pull request <number>", then each non-blocking finding on a
numbered line of its own, "1. ", "2. " and so on. The hook
nc-systems/general-tools/pull-request-follow-up-request-from-merge-lane-2-message-save-and-forked-subagent-brief-hand-over-user-prompt-submit-hook.py
saves that block word for word to SAVED_FINDINGS_FILE_NAME_FORMAT in
PULL_REQUEST_FOLLOW_UP_REQUESTS_DIRECTORY_NAME under the git common directory,
which every worktree of the checkout shares, and hands the author
build_follow_up_request_forked_subagent_brief(): dispatch one forked subagent in a worktree of its own,
which judges the findings and runs start-topic-branch, open-pull-request,
record-finding-leave-out-reason and finish-follow-up-request-and-print-merge-lane-2-message; then run
remove-recorded-topic-branches-and-worktrees.

start-topic-branch, in the subagent's worktree: record the branch and the worktree's path in TOPIC_BRANCHES_AND_WORKTREES_FILE_NAME_FORMAT,
first, so remove-recorded-topic-branches-and-worktrees knows them even when a later step fails; then git fetch
origin and git switch -c <topic-branch> origin/main.

open-pull-request, on a topic branch start-topic-branch recorded, with the change committed: refuse a
finding that does not exist or already has an answer, a branch start-topic-branch
did not record, and a FOLLOW_UP_PULL_REQUEST_TITLE_AND_DESCRIPTION_FILE_NAME at the worktree's root that is
missing, is not a title, a blank line and a description, or whose description
has no defect line, the rule scripts/merge-gate.sh applies, read by the same
reader; then git push -u origin <branch>, whose pre-push hook runs the test
suites, gh pr create against main, record the pull request's link against each
finding in FINDING_ANSWERS_FILE_NAME_FORMAT.

record-finding-leave-out-reason: record the reason against the finding; refuse a finding that does
not exist or already has an answer, and an empty reason.

finish-follow-up-request-and-print-merge-lane-2-message: refuse, naming each finding without an answer, until every finding has
one; then print the message
for merge-lane-2, which the subagent sends with SendMessage, since a program
cannot.

remove-recorded-topic-branches-and-worktrees, in the author's checkout once the subagent has ended: remove each
recorded worktree with git worktree remove, unless the agent harness still
locks it (a lock reason starting HARNESS_LOCK_REASON_START), something else
locks it, or it holds changed or untracked files; then delete each recorded
topic branch whose commits are all on a remote-tracking branch of origin.
Each worktree or branch left in place is printed with what the author should
do, and the exit code is 1.

A block that differs from the saved one is a new request: saving it removes
the answers file, but keeps the topic branch records,
which remove-recorded-topic-branches-and-worktrees still needs.

Not handled: whether a pull request handles its findings, which merge-lane-2
judges; two subagents following up one pull request at once, whose records
can overwrite each other; a finding that spans more than one line, which the
hook does not save; the branch the agent harness made the worktree on, which
start-topic-branch leaves.

Exit codes: 0 done; 1 refused, or remove-recorded-topic-branches-and-worktrees left something in place, said with
what to do; 2 git, gh or a file failed, said on stderr, and what the subcommand
did before the failure stays done, or the arguments are not ones the program
takes, which argparse says on stderr.
"""

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

_git_output_spec = importlib.util.spec_from_file_location(
    "git_machine_readable_output_runner_and_parser_common",
    Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
    / "git-machine-readable-output-runner-and-parser-common.py")
git_output = importlib.util.module_from_spec(_git_output_spec)
_git_output_spec.loader.exec_module(git_output)
_defect_line_reader_spec = importlib.util.spec_from_file_location(
    "pull_request_description_defect_line_root_cause_status_and_follow_up_link_reader",
    Path(__file__).resolve().with_name(
        "pull-request-description-defect-line-root-cause-status-and-follow-up-link-reader.py"))
defect_line_reader = importlib.util.module_from_spec(_defect_line_reader_spec)
_defect_line_reader_spec.loader.exec_module(defect_line_reader)

PROGRAM = "scripts/" + Path(__file__).name
FOLLOW_UP_REQUEST_LINE_PATTERN = re.compile(r"^#follow_up_request pull request (\d+)[ \t]*$")
FINDING_LINE_PATTERN = re.compile(r"^(\d+)\.\s+(\S.*)$")
PULL_REQUEST_LINK_PATTERN = re.compile(r"https://github\.com/[^/\s]+/[^/\s]+/pull/\d+")
PULL_REQUEST_FOLLOW_UP_REQUESTS_DIRECTORY_NAME = "pull-request-follow-up-requests"
SAVED_FINDINGS_FILE_NAME_FORMAT = "pull-request-{number}-non-blocking-findings.md"
TOPIC_BRANCHES_AND_WORKTREES_FILE_NAME_FORMAT = "pull-request-{number}-follow-up-topic-branches-and-worktrees.json"
FINDING_ANSWERS_FILE_NAME_FORMAT = "pull-request-{number}-follow-up-finding-answers.json"
FOLLOW_UP_PULL_REQUEST_TITLE_AND_DESCRIPTION_FILE_NAME = "follow-up-pull-request-title-and-description.md"
HARNESS_LOCK_REASON_START = "claude agent"
GH_TIMEOUT_SECONDS = 60
# The pre-push hook runs the test suites, and may first wait up to 600 s for their lock.
PUSH_TIMEOUT_SECONDS = 3600
FETCH_TIMEOUT_SECONDS = 300
OPEN_ARGUMENTS = "open-pull-request --handled-finding-numbers <n>[,<n>...]"
LEAVE_OUT_ARGUMENTS = 'record-finding-leave-out-reason <n> --reason "<why>"'
# Each text this program hands an agent follows
# docs/nedschorus-wiki/nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md.


class Refused(Exception):
    """A rule stops the subcommand; the text says which and what to do."""


class StepFailed(Exception):
    """git, gh or a file failed. instructions, when given, replace the usual ones."""

    def __init__(self, text, instructions=None):
        super().__init__(text)
        self.instructions = instructions


def command(number, subcommand):
    return f"python3 {PROGRAM} {number} {subcommand}"


def build_follow_up_request_forked_subagent_brief(request):
    """The brief the hook hands the author for request."""
    number = request.number
    return "\n".join([
        f"merge-lane-2 merged pull request {number} and sent {request.finding_count} non-blocking "
        "findings to follow up now:",
        "",
        *request.lines,
        "",
        f"Each \"Program:\" below means: run {command(number, '')}followed by the words after it.",
        "",
        "For you, the author:",
        "Dispatch one subagent: subagent_type \"fork\", isolation \"worktree\", "
        "run_in_background true. Give it this whole text; the lines under \"For you, the author\" are "
        "not its.",
        "When it has ended, Program: remove-recorded-topic-branches-and-worktrees",
        "",
        "For the subagent, in your own worktree:",
        "1. Run git fetch origin, then check each finding against origin/main; leave out any that "
        "no longer holds.",
        "2. Group the findings you take on by topic: one pull request per topic.",
        "3. For each topic, Program: start-topic-branch <topic-branch>",
        "   Make the change with its tests, and commit.",
        f"   Write {FOLLOW_UP_PULL_REQUEST_TITLE_AND_DESCRIPTION_FILE_NAME} at your worktree's root: the title, a blank line, "
        "then the description. Do not commit it.",
        f"   Program: {OPEN_ARGUMENTS}",
        f"4. For each finding you leave out, Program: {LEAVE_OUT_ARGUMENTS}",
        "5. Program: finish-follow-up-request-and-print-merge-lane-2-message",
        "   Send the message it prints to merge-lane-2 with SendMessage.",
        "If a command refuses or fails, do what it prints.",
    ])


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


def git(directory, arguments, **options):
    # Absolute, so a failure names the directory: "." says nothing to the agent reading it.
    try:
        return git_output.run_git(Path(directory).absolute(), arguments, **options).decode()
    except git_output.GitCommandFailed as failure:
        raise StepFailed(str(failure)) from None


def gh(arguments):
    # The subcommand alone names the call: pr create's arguments hold the whole description.
    name = "gh " + " ".join(arguments[:2])
    try:
        completed = subprocess.run(["gh", *arguments], capture_output=True, text=True,
                                   stdin=subprocess.DEVNULL, timeout=GH_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        raise StepFailed(f"{name} did not finish within {GH_TIMEOUT_SECONDS} s") from None
    except OSError as error:
        raise StepFailed(f"could not start gh: {error}") from None
    if completed.returncode < 0:
        raise StepFailed(f"{name} was killed by signal {-completed.returncode}: "
                         f"{completed.stderr.strip() or 'it printed no error text'}")
    if completed.returncode != 0:
        raise StepFailed(f"{name} exited {completed.returncode}: "
                         f"{completed.stderr.strip() or 'it printed no error text'}")
    return completed.stdout


def state_directory(directory="."):
    """PULL_REQUEST_FOLLOW_UP_REQUESTS_DIRECTORY_NAME in the git common directory, which the checkout and its worktrees share."""
    common = git(directory, ["rev-parse", "--path-format=absolute", "--git-common-dir"]).strip()
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


def remove_file(path):
    try:
        path.unlink(missing_ok=True)
    except OSError as error:
        raise StepFailed(f"could not remove {path}: {error}") from None


def read_json(path, empty):
    text = read_text_if_present(path)
    if text is None:
        return empty
    try:
        return json.loads(text)
    except ValueError as error:
        raise StepFailed(f"could not read {path}: it is not the JSON this program writes: {error}") from None


def write_json(path, value):
    write_text(path, json.dumps(value, indent=2) + "\n")


def save_follow_up_request_and_clear_answers_when_its_findings_changed(request, directory="."):
    """Save request's block for its pull request, as the hook does. A block that differs from the one
    saved is a new request, so the answers file, finish time included, is removed."""
    states = state_directory(directory)
    saved = state_file(states, SAVED_FINDINGS_FILE_NAME_FORMAT, request.number)
    if read_text_if_present(saved) == request.text:
        return saved
    write_text(saved, request.text)
    remove_file(state_file(states, FINDING_ANSWERS_FILE_NAME_FORMAT, request.number))
    return saved


def saved_follow_up_request(states, number):
    saved = state_file(states, SAVED_FINDINGS_FILE_NAME_FORMAT, number)
    text = read_text_if_present(saved)
    if text is None:
        raise Refused(f"No follow-up request from merge-lane-2 is saved for pull request {number}: "
                      f"{saved} does not exist.\n"
                      "If merge-lane-2's message for that pull request has no line "
                      f"\"#follow_up_request pull request {number}\", there is nothing for this "
                      "program to follow up: follow up the message's findings as CLAUDE.md says.\n"
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


def numbers_text(numbers):
    numbers = [str(number) for number in numbers]
    return numbers[0] if len(numbers) == 1 else ", ".join(numbers[:-1]) + " and " + numbers[-1]


def findings_text(numbers):
    return ("finding " if len(numbers) == 1 else "findings ") + numbers_text(numbers)


def answer_text(answer):
    return answer["link"] if "link" in answer else "Left out: " + answer["reason"]


def refuse_unknown_or_answered(number, request, answers, findings, not_done, answered_instruction):
    unknown = [finding for finding in findings if not 1 <= finding <= request.finding_count]
    if unknown:
        raise Refused(f"merge-lane-2 sent {request.finding_count} findings for pull request {number}, "
                      f"numbered 1 to {request.finding_count}, so there "
                      f"{'is no' if len(unknown) == 1 else 'are no'} {findings_text(unknown)}, and {not_done}.\n"
                      "Run the command again with finding numbers from the follow-up request.")
    answered = [finding for finding in findings if str(finding) in answers]
    if answered:
        raise Refused(f"{findings_text(answered).capitalize()} of pull request {number}'s follow-up "
                      f"request already {'has' if len(answered) == 1 else 'have'} an answer, so {not_done}:\n"
                      + "\n".join(f"{finding}. {answer_text(answers[str(finding)])}" for finding in answered)
                      + "\n" + answered_instruction(answered))


def start_topic_branch(number, branch):
    states = state_directory()
    saved_follow_up_request(states, number)
    worktree = git(".", ["rev-parse", "--show-toplevel"]).strip()
    branches_file = state_file(states, TOPIC_BRANCHES_AND_WORKTREES_FILE_NAME_FORMAT, number)
    records = read_json(branches_file, [])
    record = {"branch": branch, "worktree": worktree}
    if record not in records:
        write_json(branches_file, [*records, record])
    git(".", ["fetch", "origin"], timeout_seconds=FETCH_TIMEOUT_SECONDS)
    git(".", ["switch", "-c", branch, "origin/main"])
    print(f"On topic branch {branch}, made from origin/main and recorded for pull request {number}'s "
          "follow-up.")


def read_title_and_description(path):
    text = read_text_if_present(path)
    if text is None:
        raise Refused(f"{path} does not exist, so open-pull-request pushed nothing.\n"
                      "Write it at the root of your worktree: the pull request's title on the first "
                      "line, a blank line, then the description. Do not commit it.\n"
                      "Then run open-pull-request again.")
    title, _, rest = text.partition("\n")
    blank, _, description = rest.partition("\n")
    if not title.strip() or blank.strip() or not description.strip():
        raise Refused(f"{path} is not the pull request's title on the first line, a blank line, then "
                      "the description, so open-pull-request pushed nothing.\n"
                      "Write it in that form, and run open-pull-request again.")
    if not defect_line_reader.pull_request_description_defect_lines(description):
        raise Refused(f"The description in {path} has no line beginning \"#root_cause\", "
                      "\"#root_cause_not_fixed\" or \"#no_defect_fixed\", so open-pull-request pushed nothing: "
                      "scripts/merge-gate.sh does not merge a pull request without one.\n"
                      "Add one of these lines, starting the line with the hashtag: \"#root_cause\" and "
                      "the root cause the change removes; \"#root_cause_not_fixed\" and the root cause "
                      "that stays, or that none was found, with the reason, then #follow_up and the link "
                      "of the issue or pull request that will fix it or look for it; or "
                      "\"#no_defect_fixed\" when the pull request fixes no defect.\n"
                      "Then run open-pull-request again.")
    return title.strip(), description


def open_pull_request(number, findings):
    states = state_directory()
    request = saved_follow_up_request(states, number)
    answers_file = state_file(states, FINDING_ANSWERS_FILE_NAME_FORMAT, number)
    record = read_json(answers_file, {})
    answers = record.get("answers", {})
    refuse_unknown_or_answered(
        number, request, answers, findings, "open-pull-request pushed nothing",
        lambda answered: ("Run the command again without "
                          + ("that finding" if len(answered) == 1 else "those findings")
                          + ": each finding takes one answer."))
    branch = git(".", ["branch", "--show-current"]).strip()
    recorded = [entry["branch"] for entry in read_json(
        state_file(states, TOPIC_BRANCHES_AND_WORKTREES_FILE_NAME_FORMAT, number), [])]
    if branch not in recorded:
        on = f"branch {branch}" if branch else "a detached HEAD"
        raise Refused(f"This worktree is on {on}, which start-topic-branch did not record for pull request "
                      f"{number}'s follow-up, so open-pull-request pushed nothing.\n"
                      f"If you have not run start-topic-branch for this topic, run: {command(number, 'start-topic-branch <topic-branch>')}\n"
                      "Then make and commit the change on it.\n"
                      "If you have, switch to its branch with git switch <topic-branch>, and run open-pull-request again.")
    description_file = Path(git(".", ["rev-parse", "--show-toplevel"]).strip()) / FOLLOW_UP_PULL_REQUEST_TITLE_AND_DESCRIPTION_FILE_NAME
    title, description = read_title_and_description(description_file)
    try:
        git_output.run_git(".", ["push", "-u", "origin", branch], timeout_seconds=PUSH_TIMEOUT_SECONDS)
    except git_output.GitCommandFailed as failure:
        if failure.returncode is None:
            text = f"git push -u origin {branch} failed ({failure.stderr}), so no pull request was opened."
            hook_instruction = ""
        else:
            text = (f"git push -u origin {branch} exited {failure.returncode}, so no pull request was "
                    f"opened. git's output:\n{failure.stderr.strip()}")
            hook_instruction = ("If git's output shows the pre-push hook refusing the push, do what it "
                                "says, commit the fix, and run open-pull-request again.\n"
                                "Otherwise run open-pull-request again once.\n")
        raise StepFailed(
            text,
            (hook_instruction or "Run open-pull-request again once.\n") +
            f"If the push fails the same way, tell the user, in one sentence, that git push of {branch} "
            f"fails and that the follow-up of pull request {number} is stopped until it works.\n"
            "If you are a subagent, pass that sentence to the agent that dispatched you instead.") from None
    output = gh(["pr", "create", "--base", "main", "--head", branch, "--title", title, "--body", description])
    links = PULL_REQUEST_LINK_PATTERN.findall(output)
    if not links:
        raise StepFailed(f"gh pr create printed no pull request link: {output.strip()!r}")
    link = links[-1]
    for finding in findings:
        answers[str(finding)] = {"link": link, "branch": branch}
    record["answers"] = answers
    write_json(answers_file, record)
    unanswered = [index for index in range(1, request.finding_count + 1) if str(index) not in answers]
    print(f"Opened {link} for {findings_text(findings)} of pull request {number}'s follow-up "
          "request, and recorded it.")
    print(f"Findings without an answer yet: {numbers_text(unanswered)}." if unanswered
          else f"Every finding has an answer: run {command(number, 'finish-follow-up-request-and-print-merge-lane-2-message')}")


def record_finding_leave_out_reason(number, finding, reason):
    states = state_directory()
    request = saved_follow_up_request(states, number)
    answers_file = state_file(states, FINDING_ANSWERS_FILE_NAME_FORMAT, number)
    record = read_json(answers_file, {})
    answers = record.get("answers", {})
    refuse_unknown_or_answered(
        number, request, answers, [finding], "nothing was recorded",
        lambda answered: "Each finding takes one answer, so leave this one as it is and go on with the next.")
    if not reason.strip():
        raise Refused(f"--reason is empty, so nothing was recorded for finding {finding}.\n"
                      f"Run it again with the reason the finding is left out: "
                      f"{command(number, LEAVE_OUT_ARGUMENTS.replace('<n>', str(finding)))}")
    answers[str(finding)] = {"reason": " ".join(reason.split())}
    record["answers"] = answers
    write_json(answers_file, record)
    print(f"Recorded finding {finding} of pull request {number}'s follow-up request as left out.")


def finish_follow_up_request_and_print_merge_lane_2_message(number):
    states = state_directory()
    request = saved_follow_up_request(states, number)
    answers_file = state_file(states, FINDING_ANSWERS_FILE_NAME_FORMAT, number)
    record = read_json(answers_file, {})
    answers = record.get("answers", {})
    unanswered = [index for index in range(1, request.finding_count + 1) if str(index) not in answers]
    if unanswered:
        raise Refused(f"{findings_text(unanswered).capitalize()} of pull request {number}'s follow-up "
                      f"request {'has' if len(unanswered) == 1 else 'have'} no answer yet, so the follow-up is not finished.\n"
                      "For each finding a pull request handles, run on that pull request's topic "
                      f"branch: {command(number, OPEN_ARGUMENTS)}\n"
                      "For each finding you leave out, run: "
                      f"{command(number, LEAVE_OUT_ARGUMENTS)}\n"
                      "Then run finish-follow-up-request-and-print-merge-lane-2-message again.")
    print("\n".join([
        f"Every finding of pull request {number}'s follow-up request has an answer.",
        "Send merge-lane-2 this message with SendMessage:",
        "",
        f"Follow-ups on pull request {number}, answering merge-lane-2's #follow_up_request pull request "
        f"{number}:",
        *(f"{index}. {answer_text(answers[str(index)])}" for index in range(1, request.finding_count + 1)),
    ]))


def remove_recorded_topic_branches_and_worktrees(number):
    states = state_directory()
    records = read_json(state_file(states, TOPIC_BRANCHES_AND_WORKTREES_FILE_NAME_FORMAT, number), [])
    if not records:
        print(f"No topic branch is recorded for pull request {number}'s follow-up, so remove-recorded-topic-branches-and-worktrees removed "
              "nothing.")
        return 0
    again = command(number, "remove-recorded-topic-branches-and-worktrees")
    worktrees = {worktree.path.rstrip("/"): worktree for worktree in git_output.worktree_records(
        git(".", ["worktree", "list", "--porcelain", "-z"]))}
    left_paths, left = set(), []
    for path in dict.fromkeys(record["worktree"] for record in records):
        worktree = worktrees.get(path.rstrip("/"))
        if worktree is None:
            continue
        reason = worktree.locked_reason
        if reason is not None and reason.startswith(HARNESS_LOCK_REASON_START):
            left.append(f"Worktree {path} is locked by the agent harness (lock reason: {reason}), so "
                        "remove-recorded-topic-branches-and-worktrees left it and the topic branches recorded with it: the subagent may still be running.\n"
                        f"Wait until the subagent has ended, then run: {again}\n"
                        "If the worktree is still locked when you end your turn, tell the user, in one "
                        f"sentence, that the agent harness still locks worktree {path} of pull request "
                        f"{number}'s follow-up, so remove-recorded-topic-branches-and-worktrees could not remove it.\n"
                        "If you are a subagent, pass that sentence to the agent that dispatched you instead.")
        elif reason is not None:
            left.append(f"Worktree {path} is locked (lock reason: {reason or 'none given'}), so remove-recorded-topic-branches-and-worktrees "
                        "left it and the topic branches recorded with it.\n"
                        "If whoever the lock reason names may still be using the worktree, leave it, "
                        f"and tell the user, in one sentence, that worktree {path} of pull request "
                        f"{number}'s follow-up is locked ({reason or 'no reason given'}), so remove-recorded-topic-branches-and-worktrees left "
                        "it.\n"
                        f"Otherwise list its changed or untracked files with git -C {path} status "
                        "--short, read them, copy out any that is work to keep, and tell merge-lane-2 "
                        "about it with SendMessage.\n"
                        f"Then run: git worktree remove --force --force {path}\n"
                        f"Then run: {again}\n"
                        "If you are a subagent, pass any sentence for the user to the agent that "
                        "dispatched you instead.")
        else:
            changed = git(path, ["status", "--short"]).rstrip("\n")
            if changed:
                left.append(f"Worktree {path} holds changed or untracked files, so remove-recorded-topic-branches-and-worktrees left it and "
                            f"the topic branches recorded with it:\n{changed}\n"
                            "Read them, copy out of the worktree any file that is work to keep, such as a "
                            "change the subagent did not push, and tell merge-lane-2 about it with "
                            "SendMessage.\n"
                            f"Then run: git worktree remove --force {path}\n"
                            f"Then run: {again}")
            else:
                git(".", ["worktree", "remove", path])
                print(f"Removed worktree {path}.")
                continue
        left_paths.add(path)
    for record in records:
        branch = record["branch"]
        if record["worktree"] in left_paths:
            continue
        if not git(".", ["rev-parse", "--verify", "--quiet", "refs/heads/" + branch],
                   accepted_exit_codes=(0, 1)).strip():
            continue
        if not git(".", ["for-each-ref", "--contains", "refs/heads/" + branch, "refs/remotes/origin/"]).strip():
            commits = git(".", ["log", "--oneline", "refs/remotes/origin/main..refs/heads/" + branch]).rstrip("\n")
            left.append(f"Branch {branch} holds commits on no branch of origin, so remove-recorded-topic-branches-and-worktrees left it:\n"
                        f"{commits}\n"
                        f"Read them with git log -p origin/main..{branch}, copy out any that is work to keep, "
                        "and tell merge-lane-2 about it with SendMessage.\n"
                        f"Then run: git branch -D {branch}")
            continue
        git(".", ["branch", "-D", branch])
        print(f"Deleted branch {branch}.")
    if left:
        print("\n".join(left))
        print(f"Clean-up of pull request {number}'s follow-up left {len(left)} "
              + ("worktree or branch" if len(left) == 1 else "worktrees or branches")
              + " in place; each is above, with what to do.")
        return 1
    print(f"Clean-up of pull request {number}'s follow-up is done: every recorded worktree and topic "
          "branch is removed.")
    return 0


def finding_numbers(text):
    try:
        numbers = [int(part) for part in text.split(",")]
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not finding numbers separated by commas, "
                                         "such as 1,3") from None
    return list(dict.fromkeys(numbers))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Do the mechanical steps of following up the non-blocking findings merge-lane-2 "
                    "sent after merging a pull request.")
    parser.add_argument("number", type=int, help="the merged pull request's number")
    subcommands = parser.add_subparsers(dest="subcommand", required=True)
    start_parser = subcommands.add_parser(
        "start-topic-branch", help="in the subagent's worktree: make a topic branch from origin/main and record it")
    start_parser.add_argument("branch", metavar="topic-branch")
    open_parser = subcommands.add_parser(
        "open-pull-request", help="push the recorded topic branch, open its pull request and record its link")
    open_parser.add_argument("--handled-finding-numbers", type=finding_numbers, required=True,
                             help="the findings the pull request handles, such as 1,3")
    leave_out_parser = subcommands.add_parser("record-finding-leave-out-reason", help="record why a finding is left out")
    leave_out_parser.add_argument("finding", type=int)
    leave_out_parser.add_argument("--reason", required=True)
    subcommands.add_parser("finish-follow-up-request-and-print-merge-lane-2-message", help="check every finding has an answer and print the message "
                                          "for merge-lane-2")
    subcommands.add_parser("remove-recorded-topic-branches-and-worktrees", help="in the author's checkout, once the subagent has ended: "
                                            "remove each recorded worktree and topic branch")
    arguments = parser.parse_args(argv)
    try:
        if arguments.subcommand == "start-topic-branch":
            start_topic_branch(arguments.number, arguments.branch)
        elif arguments.subcommand == "open-pull-request":
            open_pull_request(arguments.number, arguments.handled_finding_numbers)
        elif arguments.subcommand == "record-finding-leave-out-reason":
            record_finding_leave_out_reason(arguments.number, arguments.finding, arguments.reason)
        elif arguments.subcommand == "finish-follow-up-request-and-print-merge-lane-2-message":
            finish_follow_up_request_and_print_merge_lane_2_message(arguments.number)
        else:
            return remove_recorded_topic_branches_and_worktrees(arguments.number)
    except Refused as refusal:
        print(f"REFUSED: {refusal}", file=sys.stderr)
        return 1
    except StepFailed as failure:
        instructions = failure.instructions or (
            "Run the same command again once.\n"
            "If it fails the same way, tell the user, in one sentence, which file, git or gh command "
            f"failed and that the follow-up of pull request {arguments.number} is stopped until it works.\n"
            "If you are a subagent, pass that sentence to the agent that dispatched you instead.")
        print(f"FAILED: {failure}\n"
              f"{arguments.subcommand} stopped there; what it did before the failure stays done.\n"
              + instructions, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
