#!/usr/bin/env python3
"""Do the mechanical steps of following up the non-blocking findings merge-lane-2 sends after merging a pull request.

Usage:
  PROGRAM <number> next-step
  PROGRAM <number> start-topic-branch <topic-branch> --finding-numbers <n>[,<n>...]
  PROGRAM <number> open-pull-request [--handled-finding-numbers <n>[,<n>...]]
  PROGRAM <number> record-finding-leave-out-reason <n> --reason "<why>"
  PROGRAM <number> record-finding-as-waiting-for-user-ruling <n> --what-it-would-change "<what>"
  PROGRAM <number> reopen-waiting-finding-with-user-ruling <n> --user-ruling "<his words>"
  PROGRAM <number> finish-and-print-merge-lane-2-message
  PROGRAM <number> remove-topic-branches-and-worktrees

merge-lane-2 ends a merge message that asks for follow-ups with the line
"#follow_up_request pull request <number>", then each non-blocking finding on a
numbered line of its own, "1. ", "2. " and so on. The hook
nc-systems/general-tools/pull-request-follow-up-request-from-merge-lane-2-message-save-and-forked-subagent-brief-hand-over-user-prompt-submit-hook.py
saves that block word for word to SAVED_FINDINGS_FILE_NAME_FORMAT in
PULL_REQUEST_FOLLOW_UP_REQUESTS_DIRECTORY_NAME under the git common directory,
which every worktree of the checkout shares, and hands the author
build_follow_up_request_forked_subagent_brief(): dispatch one forked subagent in a worktree of its own,
which runs next-step and does what it prints until it prints "Done"; then run
remove-topic-branches-and-worktrees.

next-step, in the subagent's worktree: git fetch origin, then print the one step that comes next,
decided from the records alone, first match wins: "Done" once finish-and-print-merge-lane-2-message
has recorded the follow-up finished; the topic branch of the lowest finding start-topic-branch took on that has no
answer yet, to switch to it first when the worktree has another checked out, make the change, commit, write the title
and description, and run open-pull-request; the findings with
no answer, each with the user's decision when reopen-waiting-finding-with-user-ruling recorded one, to judge each against
origin/main and either run record-finding-leave-out-reason or record-finding-as-waiting-for-user-ruling, or group it
into a topic and run start-topic-branch; and, every finding answered, finish-and-print-merge-lane-2-message and
the message to merge-lane-2. Done lists each finding waiting for the user's decision, with the commands the author
runs once the user has answered. The judging and the change stay with the subagent.

start-topic-branch, in the subagent's worktree: refuse a finding that does not exist or already has an answer, and a
worktree with uncommitted changes to tracked files, which git switch could refuse to carry over; git
fetch origin and git switch -c <topic-branch> origin/main; then record the branch and the worktree's path in
TOPIC_BRANCHES_AND_WORKTREES_FILE_NAME_FORMAT, so remove-topic-branches-and-worktrees can remove them, and
record under "started" in FINDING_ANSWERS_FILE_NAME_FORMAT that the branch takes on the findings, so next-step and
open-pull-request know them; a finding named again moves to the new branch. A branch git could not make is not
recorded.

open-pull-request, in that worktree, with the change committed on its topic branch: without
--handled-finding-numbers, handle the findings start-topic-branch recorded for the branch that have no answer, and
refuse when there are none; refuse a
finding that does not exist or already has an answer, a worktree start-topic-branch recorded no
branch for, a worktree whose checked-out branch, or detached HEAD, is not one start-topic-branch recorded for it,
and a FOLLOW_UP_PULL_REQUEST_TITLE_AND_DESCRIPTION_FILE_NAME at the worktree's root that is
missing, is not a title, a blank line and a description, or whose description
has no defect line, the rule scripts/merge-gate.sh applies, read by the same
reader; then git push -u origin <branch>, where <branch> is the recorded topic branch the worktree has
checked out, and whose pre-push hook runs the test suites; gh pr create against main; record the pull request's link against each
finding in FINDING_ANSWERS_FILE_NAME_FORMAT; then remove FOLLOW_UP_PULL_REQUEST_TITLE_AND_DESCRIPTION_FILE_NAME, so the
next topic branch's pull request cannot take this one's title and description. A gh pr create that fails, other than
by gh not starting, is tried once more, and a second try that passes is printed as a notice; when a try refuses
because a pull request for the branch is already open, as after a first try that opened it but failed, that pull
request's link is recorded; when gh pr create exits 0 printing no link, the link gh pr list --head <branch> prints is
recorded. A push that fails is not tried again.

record-finding-leave-out-reason: record the reason against the finding; refuse a finding that does
not exist or already has an answer other than waiting for the user's decision, and an empty reason.

record-finding-as-waiting-for-user-ruling: record the finding as waiting for the user's decision, with what it would
change, an answer finish accepts; refuse a finding that does not exist or already has an answer, and empty text.

reopen-waiting-finding-with-user-ruling, in the author's checkout, once the user has decided for a waiting finding: remove
its answer and the topic branch start-topic-branch recorded for it, record the user's words for next-step's judging
step, remove the finished mark, and print the brief again, for a new subagent; refuse a finding that does not exist or
is not waiting, and empty words. A finding the user decided against is recorded with record-finding-leave-out-reason
instead.

finish-and-print-merge-lane-2-message: refuse, naming each finding without an answer, until every finding has
one; then record the follow-up finished, for next-step, and print the message
for merge-lane-2, which lists each waiting finding as still open, and which the subagent sends with SendMessage,
since a program cannot.

remove-topic-branches-and-worktrees, in the author's checkout once the subagent has ended: remove each
recorded worktree with git worktree remove, unless the agent harness still
locks it (a lock reason starting HARNESS_LOCK_REASON_START), something else
locks it, or it holds changed or untracked files; then delete each recorded
topic branch whose commits are all on a remote-tracking branch of origin.
Each worktree or branch left in place is printed with what the author should
do, and the exit code is 1.

A block that differs from the saved one is a new request: saving it removes
the answers file, with its started findings and its finished mark, but keeps the topic branch records,
which remove-topic-branches-and-worktrees still needs.

Not handled: whether a pull request handles its findings, which merge-lane-2
judges; two subagents following up one pull request at once, whose records
can overwrite each other; a finding that spans more than one line, which the
hook does not save; the branch the agent harness made the worktree on, which
start-topic-branch leaves; commits made on any branch but the checked-out one, which the push leaves out.

Each text that has the agent tell the user something hands it the finished sentence, which names the pull request
followed up by its link, built from REPOSITORY, and by its title when gh pr view gives it within
TITLE_TIMEOUT_SECONDS; otherwise by its link alone.

Exit codes: 0 done; 1 refused, or remove-topic-branches-and-worktrees left something in place, said with
what to do; 2 git, gh or a file failed, said on stderr, and what the subcommand
did before the failure stays done, or the arguments are not ones the program
takes, which argparse says on stderr, followed by what to do.
"""

import argparse
import functools
import importlib.util
import json
import math
import os
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


def load_script_beside_this_one(file_name):
    spec = importlib.util.spec_from_file_location(
        Path(file_name).stem.replace("-", "_"), Path(__file__).resolve().with_name(file_name))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


defect_line_reader = load_script_beside_this_one(
    "pull-request-description-defect-line-root-cause-status-and-follow-up-link-reader.py")
pre_push_conflict_check = load_script_beside_this_one("git-client-side-hooks-pre-push-conflict-check.py")
pre_push_selective_test_run = load_script_beside_this_one("git-client-side-hooks-pre-push-selective-test-run.py")

PROGRAM = "scripts/" + Path(__file__).name
REPOSITORY = "nedschorus/nedschorus"
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
# Short, as the title only adds to a sentence the user gets after a failure, which it must not hold up.
TITLE_TIMEOUT_SECONDS = 15
GH_PR_CREATE_TRIES = 2
PUSH_ITSELF_SECONDS = 120
FETCH_TIMEOUT_SECONDS = 300
# gh pr create's words, when a pull request for the head branch is already open, before its link.
PULL_REQUEST_ALREADY_OPEN_WORDS = "already exists"
START_ARGUMENTS = "start-topic-branch <topic-branch> --finding-numbers <n>[,<n>...]"
LEAVE_OUT_ARGUMENTS = 'record-finding-leave-out-reason <n> --reason "<why>"'
WAITING_ARGUMENTS = 'record-finding-as-waiting-for-user-ruling <n> --what-it-would-change "<what it would change>"'
REOPEN_ARGUMENTS = 'reopen-waiting-finding-with-user-ruling <n> --user-ruling "<his words>"'
WAITING_KEY = "waiting_for_user_ruling"
TITLE_AND_DESCRIPTION_FORM = "the pull request's title on the first line, a blank line, then the description"
DO_NOT_COMMIT_LINE = "Do not commit it: it is never part of the pull request."
SUBAGENT_LINE = "If you are a subagent, pass that sentence to the agent that dispatched you instead."
# Each text this program hands an agent follows
# docs/nedschorus-wiki/nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md.


def push_time_limit_seconds(environment):
    # Sized from the time budgets the two pre-push hooks bound themselves to, plus the push itself.
    return math.ceil(pre_push_conflict_check.time_budget_seconds(environment)
                     + pre_push_selective_test_run.time_budget_seconds(environment) + PUSH_ITSELF_SECONDS)


class Refused(Exception):
    """A rule stops the subcommand; the text says which and what to do."""


class StepFailed(Exception):
    """git, gh or a file failed. instructions, when given, replace the usual ones."""

    def __init__(self, text, instructions=None):
        super().__init__(text)
        self.instructions = instructions


class GhCouldNotStart(StepFailed):
    """gh could not be started, which a second try does not change."""


def command(number, subcommand):
    return f"python3 {PROGRAM} {number} {subcommand}"


@functools.lru_cache(maxsize=None)
def build_followed_up_pull_request_citation_with_title_and_link(number):
    """"pull request [<title>](<link>)" for the pull request followed up, or "pull request <link>" when gh pr view
    gives no title. Fetched only when a sentence for the user is built, so no other step waits on GitHub."""
    link = f"https://github.com/{REPOSITORY}/pull/{number}"
    try:
        title = gh(["pr", "view", str(number), "--repo", REPOSITORY, "--json", "title", "--jq", ".title"],
                   timeout_seconds=TITLE_TIMEOUT_SECONDS).strip()
    except StepFailed:
        title = ""
    return f"pull request [{title}]({link})" if title else f"pull request {link}"


def pass_on_to_the_user(sentence, start="Pass"):
    return f'{start} this sentence to the user word for word: "{sentence}"'


def fails_sentence(subcommand, number, error):
    # On one line, as git's error text can span several.
    return (f"{subcommand} fails with this error, so the follow-up of {build_followed_up_pull_request_citation_with_title_and_link(number)} is "
            f"stopped until it is fixed: {' '.join(str(error).split())}")


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
        "Dispatch one subagent with the Agent tool: subagent_type \"fork\", isolation \"worktree\", "
        "run_in_background true. Give it this whole text unchanged; it skips the lines under "
        "\"For you, the author\".",
        "When it has ended, ask the user its report's questions, then Program: remove-topic-branches-and-worktrees",
        "",
        "For the subagent, in your own worktree: Program: next-step. Do what it prints, then run Program: next-step "
        "again, until it prints \"Done\".",
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
    """git's stdout."""
    # Absolute, so a failure names the directory: "." says nothing to the agent reading it.
    try:
        return git_output.run_git(Path(directory).absolute(), arguments, **options).decode()
    except git_output.GitCommandFailed as failure:
        raise StepFailed(str(failure)) from None


def gh(arguments, timeout_seconds=None):
    # The subcommand alone names the call: pr create's arguments hold the whole description.
    name = "gh " + " ".join(arguments[:2])
    timeout_seconds = timeout_seconds or GH_TIMEOUT_SECONDS
    try:
        completed = subprocess.run(["gh", *arguments], capture_output=True, text=True,
                                   stdin=subprocess.DEVNULL, timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        raise StepFailed(f"{name} did not finish within {timeout_seconds} s") from None
    except OSError as error:
        raise GhCouldNotStart(f"could not start gh: {error}") from None
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
    saved is a new request, so the answers file, its started findings and finished mark included, is removed."""
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
                      f"\"#follow_up_request pull request {number}\", this program does not handle it: "
                      "follow up the message's findings by hand, as CLAUDE.md says.\n"
                      "If the message has that line, the hook did not save the block: follow up the "
                      "message's findings by hand, as CLAUDE.md says, and "
                      + pass_on_to_the_user("The follow-up request hook did not save merge-lane-2's findings for "
                                            f"{build_followed_up_pull_request_citation_with_title_and_link(number)}.", "pass")
                      + f"\n{SUBAGENT_LINE}")
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
    if "link" in answer:
        return answer["link"]
    if WAITING_KEY in answer:
        return "Still open, waiting for the user's decision: it would change " + answer[WAITING_KEY]
    return "Left out: " + answer["reason"]


def waiting_findings(request, answers):
    return [index for index in range(1, request.finding_count + 1) if WAITING_KEY in answers.get(str(index), {})]


def finding_text(request, finding):
    return FINDING_LINE_PATTERN.match(request.lines[finding]).group(2)


def still_unanswered_text(number, request, answers):
    unanswered = [index for index in range(1, request.finding_count + 1) if str(index) not in answers]
    if not unanswered:
        return f"Every finding has an answer: run {command(number, 'finish-and-print-merge-lane-2-message')}"
    return (f"{findings_text(unanswered).capitalize()} "
            f"{'has' if len(unanswered) == 1 else 'have'} no answer yet.")


def refuse_unknown_or_answered(number, request, answers, findings, not_done, answered_instruction):
    unknown = [finding for finding in findings if not 1 <= finding <= request.finding_count]
    if unknown:
        raise Refused(f"merge-lane-2 sent {request.finding_count} findings for pull request {number}, "
                      f"numbered 1 to {request.finding_count}, so there "
                      f"{'is no' if len(unknown) == 1 else 'are no'} {findings_text(unknown)}, and {not_done}.\n"
                      f"Run the same command again with finding numbers from 1 to {request.finding_count}.")
    answered = [finding for finding in findings if str(finding) in answers]
    if answered:
        raise Refused(f"{findings_text(answered).capitalize()} of pull request {number}'s follow-up "
                      f"request already {'has' if len(answered) == 1 else 'have'} an answer, so {not_done}:\n"
                      + "\n".join(f"{finding}. {answer_text(answers[str(finding)])}" for finding in answered)
                      + "\n" + answered_instruction(answered))


def start_topic_branch(number, branch, findings):
    states = state_directory()
    request = saved_follow_up_request(states, number)
    answers_file = state_file(states, FINDING_ANSWERS_FILE_NAME_FORMAT, number)
    answers_record = read_json(answers_file, {})
    refuse_unknown_or_answered(
        number, request, answers_record.get("answers", {}), findings, "no topic branch was made",
        lambda answered: "Each finding takes one answer: run the same command again without "
                         + ("that finding." if len(answered) == 1 else "those findings."))
    worktree = git(".", ["rev-parse", "--show-toplevel"]).strip()
    # rstrip, not strip: a line git status prints for an unstaged change starts with a space.
    changed = git(".", ["status", "--porcelain", "--untracked-files=no"]).rstrip("\n")
    if changed:
        raise Refused(f"{worktree} has uncommitted changes to tracked files, so no topic branch was made:\n"
                      f"{changed}\n"
                      "Commit or remove them, then run the same start-topic-branch command again.")
    branches_file = state_file(states, TOPIC_BRANCHES_AND_WORKTREES_FILE_NAME_FORMAT, number)
    records = read_json(branches_file, [])
    git(".", ["fetch", "origin"], timeout_seconds=FETCH_TIMEOUT_SECONDS)
    try:
        git(".", ["switch", "-c", branch, "origin/main"])
    except StepFailed as failure:
        raise StepFailed(str(failure),
                         "If git says the branch already exists or is not a valid branch name, run "
                         f"{command(number, START_ARGUMENTS.replace('<topic-branch>', '<another topic-branch>'))}\n"
                         + pass_on_to_the_user(fails_sentence("start-topic-branch", number, failure), "Otherwise pass")
                         + f"\n{SUBAGENT_LINE}") from None
    record = {"branch": branch, "worktree": worktree}
    if record not in records:
        write_json(branches_file, [*records, record])
    answers_record["started"] = {**answers_record.get("started", {}),
                                 **{str(finding): branch for finding in findings}}
    write_json(answers_file, answers_record)
    print(f"On topic branch {branch}, made from origin/main and recorded for pull request {number}'s "
          "follow-up.")


def read_title_and_description(path):
    text = read_text_if_present(path)
    if text is None:
        raise Refused(f"{path} does not exist, so open-pull-request pushed nothing.\n"
                      f"Write it at the root of your worktree: {TITLE_AND_DESCRIPTION_FORM}.\n"
                      f"{DO_NOT_COMMIT_LINE}\n"
                      "Then run the same open-pull-request command again.")
    title, _, rest = text.partition("\n")
    blank, _, description = rest.partition("\n")
    if not title.strip() or blank.strip() or not description.strip():
        raise Refused(f"{path} is not {TITLE_AND_DESCRIPTION_FORM}, so open-pull-request pushed nothing.\n"
                      "Write it in that form.\n"
                      f"{DO_NOT_COMMIT_LINE}\n"
                      "Then run the same open-pull-request command again.")
    if not defect_line_reader.pull_request_description_defect_lines(description):
        raise Refused(f"The description in {path} has no line beginning \"#root_cause\", "
                      "\"#root_cause_not_fixed\" or \"#no_defect_fixed\", so open-pull-request pushed nothing: "
                      "scripts/merge-gate.sh does not merge a pull request without one.\n"
                      "Add a line for each defect the pull request fixes, or one line if it fixes none, "
                      "starting each line with its hashtag:\n"
                      "If the change removes the defect's root cause: #root_cause, then that cause.\n"
                      "If the root cause stays, or none was found: #root_cause_not_fixed, then the cause, or "
                      "that none was found, and the reason, then, on the same line, #follow_up and the full "
                      "https://github.com/ link of the open issue or pull request that will fix the cause or "
                      "look for it.\n"
                      "If the pull request fixes no defect: #no_defect_fixed.\n"
                      "Then run the same open-pull-request command again.")
    return title.strip(), description


def unanswered_started_findings(record, branch=None):
    """The findings start-topic-branch recorded, for branch or for any, that have no answer, lowest first."""
    answers = record.get("answers", {})
    return sorted(int(finding) for finding, started in record.get("started", {}).items()
                  if finding not in answers and branch in (None, started))


def open_pull_request(number, findings):
    states = state_directory()
    request = saved_follow_up_request(states, number)
    answers_file = state_file(states, FINDING_ANSWERS_FILE_NAME_FORMAT, number)
    record = read_json(answers_file, {})
    answers = record.get("answers", {})
    worktree = git(".", ["rev-parse", "--show-toplevel"]).strip()
    recorded = [entry["branch"] for entry in read_json(
        state_file(states, TOPIC_BRANCHES_AND_WORKTREES_FILE_NAME_FORMAT, number), [])
        if entry["worktree"] == worktree]
    if not recorded:
        raise Refused(f"start-topic-branch recorded no topic branch in {worktree} for pull request {number}'s "
                      "follow-up, so open-pull-request has no branch to push, and pushed nothing.\n"
                      f"Run {command(number, START_ARGUMENTS)} in this worktree, make "
                      "and commit the change on that branch, and run the same open-pull-request command again.")
    branch = git(".", ["branch", "--show-current"]).strip()
    if branch not in recorded:
        commits = git(".", ["log", "--oneline", "origin/main..HEAD"]).rstrip("\n")
        raise Refused(f"this worktree has {branch or 'no branch'} checked out, which start-topic-branch did not "
                      f"record for pull request {number}'s follow-up, so open-pull-request pushed nothing.\n"
                      "HEAD holds these commits that are not on origin/main:\n"
                      f"{commits}\n"
                      "Switch to the topic branch whose pull request you are opening, one of "
                      f"{numbers_text(recorded)}, with git switch <topic-branch>, and run the same open-pull-request "
                      "command again.")
    if findings is None:
        findings = unanswered_started_findings(record, branch)
        if not findings:
            raise Refused(f"start-topic-branch recorded no finding without an answer for topic branch {branch} of "
                          f"pull request {number}'s follow-up, so open-pull-request pushed nothing.\n"
                          "If the pull request handles findings, run the same command again with "
                          "--handled-finding-numbers <n>[,<n>...] naming them.\n"
                          f"Otherwise run {command(number, 'next-step')} and do what it prints.")
    refuse_unknown_or_answered(
        number, request, answers, findings, "open-pull-request pushed nothing",
        lambda answered: ("Each finding takes one answer: run the same command again without "
                          + ("that finding." if len(answered) == 1 else "those findings.")
                          + ("" if len(answered) < len(findings) else
                             "\nIf that leaves no finding, do not open this branch's pull request: other "
                             "answers already cover what it handles. Go on with the next topic, and leave the "
                             "branch: remove-topic-branches-and-worktrees shows its commits to the "
                             "author, who decides whether to keep them.")))
    description_file = Path(worktree) / FOLLOW_UP_PULL_REQUEST_TITLE_AND_DESCRIPTION_FILE_NAME
    title, description = read_title_and_description(description_file)
    try:
        git_output.run_git(".", ["push", "-u", "origin", branch], timeout_seconds=push_time_limit_seconds(os.environ))
    except git_output.GitCommandFailed as failure:
        if failure.returncode is None:
            raise StepFailed(f"git push -u origin {branch} failed ({failure.stderr}), so no pull request "
                             "was opened.") from None
        raise StepFailed(
            f"git push -u origin {branch} exited {failure.returncode}, so no pull request was "
            f"opened. git's output:\n{failure.stderr.strip()}",
            "If git's output shows the pre-push hook refusing the push, do what it "
            "says, commit the fix, and run the same open-pull-request command again.\n"
            + pass_on_to_the_user(f"git push of {branch} fails, so the follow-up of "
                                  f"{build_followed_up_pull_request_citation_with_title_and_link(number)} is stopped until it works.",
                                  "Otherwise pass")
            + f"\n{SUBAGENT_LINE}") from None
    output, opened = gh_pr_create_tried_twice(
        ["pr", "create", "--base", "main", "--head", branch, "--title", title, "--body", description])
    links = PULL_REQUEST_LINK_PATTERN.findall(output)
    if not links:
        links = [link_gh_pr_list_finds(number, branch, output)]
    link = links[-1]
    for finding in findings:
        answers[str(finding)] = {"link": link, "branch": branch}
    record["answers"] = answers
    write_json(answers_file, record)
    print(f"{opened} {link} for {findings_text(findings)} of pull request {number}'s follow-up "
          "request, and recorded it.")
    remove_file(description_file)
    print(still_unanswered_text(number, request, answers))


def gh_pr_create_tried_twice(arguments):
    """gh pr create's output, and "Opened", or "Found already open" when a try refuses because the branch's pull
    request is already open and names it. A failure other than gh not starting gets a second try, and a second try
    that passes is printed as a notice."""
    first_failure = None
    for attempt in range(1, GH_PR_CREATE_TRIES + 1):
        try:
            output, opened = gh(arguments), "Opened"
        except GhCouldNotStart:
            raise
        except StepFailed as failure:
            if PULL_REQUEST_ALREADY_OPEN_WORDS in str(failure) and PULL_REQUEST_LINK_PATTERN.search(str(failure)):
                output, opened = str(failure), "Found already open"
            elif attempt < GH_PR_CREATE_TRIES:
                first_failure = failure
                continue
            else:
                raise StepFailed(f"both tries of gh pr create failed: {first_failure}; then {failure}") from None
        if first_failure is not None:
            print(f"Notice: gh pr create failed once ({' '.join(str(first_failure).split())}) and passed on the "
                  "second try.")
        return output, opened


def link_gh_pr_list_finds(number, branch, create_output):
    """The link of the one open pull request gh pr list finds for branch, after gh pr create printed none."""
    lost = f"gh pr create exited 0 but printed no pull request link: {create_output.strip()!r}"
    instructions = (pass_on_to_the_user(f"open-pull-request could not record the pull request of branch {branch}, "
                                        f"so the follow-up of {build_followed_up_pull_request_citation_with_title_and_link(number)} is stopped "
                                        "until it is recorded.")
                    + f"\n{SUBAGENT_LINE}")
    try:
        listed = gh(["pr", "list", "--head", branch, "--json", "url", "--jq", ".[].url"])
    except StepFailed as failure:
        raise StepFailed(f"{lost}, and {failure}", instructions) from None
    links = PULL_REQUEST_LINK_PATTERN.findall(listed)
    if len(links) != 1:
        raise StepFailed(f"{lost}, and gh pr list --head {branch} printed {len(links)} pull request links, not one: "
                         f"{listed.strip()!r}", instructions)
    print(f"Notice: gh pr create exited 0 but printed no pull request link; gh pr list --head {branch} found "
          f"{links[0]}.")
    return links[0]


def record_finding_leave_out_reason(number, finding, reason):
    states = state_directory()
    request = saved_follow_up_request(states, number)
    answers_file = state_file(states, FINDING_ANSWERS_FILE_NAME_FORMAT, number)
    record = read_json(answers_file, {})
    answers = record.get("answers", {})
    refuse_unknown_or_answered(
        number, request, {key: answer for key, answer in answers.items() if WAITING_KEY not in answer},
        [finding], "nothing was recorded",
        lambda answered: "Each finding takes one answer, so leave this one as it is and go on with the next.")
    if not reason.strip():
        raise Refused(f"--reason is empty, so nothing was recorded for finding {finding}.\n"
                      f"Run it again with the reason the finding is left out: "
                      f"{command(number, LEAVE_OUT_ARGUMENTS.replace('<n>', str(finding)))}")
    answers[str(finding)] = {"reason": " ".join(reason.split())}
    record["answers"] = answers
    write_json(answers_file, record)
    print(f"Recorded finding {finding} of pull request {number}'s follow-up request as left out.")
    print(still_unanswered_text(number, request, answers))


def record_finding_as_waiting_for_user_ruling(number, finding, what_it_would_change):
    states = state_directory()
    request = saved_follow_up_request(states, number)
    answers_file = state_file(states, FINDING_ANSWERS_FILE_NAME_FORMAT, number)
    record = read_json(answers_file, {})
    answers = record.get("answers", {})
    refuse_unknown_or_answered(
        number, request, answers, [finding], "nothing was recorded",
        lambda answered: "Each finding takes one answer, so leave this one as it is and go on with the next.")
    if not what_it_would_change.strip():
        raise Refused(f"--what-it-would-change is empty, so nothing was recorded for finding {finding}.\n"
                      "Run it again, saying which of the user's designs or decisions the finding would change: "
                      f"{command(number, WAITING_ARGUMENTS.replace('<n>', str(finding)))}")
    answers[str(finding)] = {WAITING_KEY: " ".join(what_it_would_change.split())}
    record["answers"] = answers
    write_json(answers_file, record)
    print(f"Recorded finding {finding} of pull request {number}'s follow-up request as waiting for the user's decision.")
    print(still_unanswered_text(number, request, answers))


def reopen_waiting_finding_with_user_ruling(number, finding, user_ruling):
    states = state_directory()
    request = saved_follow_up_request(states, number)
    answers_file = state_file(states, FINDING_ANSWERS_FILE_NAME_FORMAT, number)
    record = read_json(answers_file, {})
    answers = record.get("answers", {})
    refuse_unknown_or_answered(number, request, {}, [finding], "nothing was reopened", None)
    answer = answers.get(str(finding))
    if answer is None or WAITING_KEY not in answer:
        raise Refused(f"Finding {finding} of pull request {number}'s follow-up request is not waiting for the user's "
                      f"decision, so nothing was reopened. Its answer: {answer_text(answer) if answer else 'none yet'}\n"
                      "Leave the finding as it is: only a finding recorded with "
                      "record-finding-as-waiting-for-user-ruling is reopened.")
    if not user_ruling.strip():
        raise Refused(f"--user-ruling is empty, so nothing was reopened for finding {finding}.\n"
                      "Run it again with the user's decision in his words: "
                      f"{command(number, REOPEN_ARGUMENTS.replace('<n>', str(finding)))}")
    del answers[str(finding)]
    record.get("started", {}).pop(str(finding), None)
    record["user_rulings"] = {**record.get("user_rulings", {}), str(finding): {
        "would_change": answer[WAITING_KEY], "decision": " ".join(user_ruling.split())}}
    record.pop("finished", None)
    write_json(answers_file, record)
    print("\n".join([
        f"Reopened finding {finding} of pull request {number}'s follow-up request with the user's decision, and "
        "marked the follow-up as not finished.",
        "Do what the text below says for you, the author: the subagent it starts follows up the reopened finding.",
        "",
        build_follow_up_request_forked_subagent_brief(request),
    ]))


def finish_and_print_merge_lane_2_message(number):
    states = state_directory()
    request = saved_follow_up_request(states, number)
    answers_file = state_file(states, FINDING_ANSWERS_FILE_NAME_FORMAT, number)
    record = read_json(answers_file, {})
    answers = record.get("answers", {})
    unanswered = [index for index in range(1, request.finding_count + 1) if str(index) not in answers]
    if unanswered:
        raise Refused(f"{findings_text(unanswered).capitalize()} of pull request {number}'s follow-up "
                      f"request {'has' if len(unanswered) == 1 else 'have'} no answer yet, so the follow-up is not finished.\n"
                      f"Run {command(number, 'next-step')} and do what it prints.")
    record["finished"] = True
    write_json(answers_file, record)
    print("\n".join([
        f"Every finding of pull request {number}'s follow-up request has an answer.",
        "Send merge-lane-2 this message with SendMessage:",
        "",
        f"Follow-ups on pull request {number}, answering merge-lane-2's #follow_up_request pull request "
        f"{number}:",
        *(f"{index}. {answer_text(answers[str(index)])}" for index in range(1, request.finding_count + 1)),
        *(["You will get a new message on each still-open finding once the user has decided."]
          if waiting_findings(request, answers) else []),
    ]))


def next_step(number):
    states = state_directory()
    git(".", ["fetch", "origin"], timeout_seconds=FETCH_TIMEOUT_SECONDS)
    request = saved_follow_up_request(states, number)
    record = read_json(state_file(states, FINDING_ANSWERS_FILE_NAME_FORMAT, number), {})
    answers = record.get("answers", {})
    if record.get("finished"):
        waiting = waiting_findings(request, answers)
        if not waiting:
            print(f"Done: pull request {number}'s follow-up request is finished.\n"
                  "End your turn with your report.")
            return
        print("\n".join([
            f"Done: pull request {number}'s follow-up request is finished, with {findings_text(waiting)} waiting for "
            "the user's decision.",
            "End your turn with your report, ending it with these lines word for word, for the agent that dispatched you:",
            *(line for finding in waiting for line in (
                f"Finding {finding} of the follow-up of {build_followed_up_pull_request_citation_with_title_and_link(number)} "
                "waits for the user's decision: "
                f"{finding_text(request, finding)}",
                f"It would change {answers[str(finding)][WAITING_KEY]}.",
                "Put it to the user as an item of an approval-walk: whether he wants that change.",
                "If he does, run: " + command(number, REOPEN_ARGUMENTS.replace("<n>", str(finding))),
                "If he does not, run: " + command(number, LEAVE_OUT_ARGUMENTS.replace("<n>", str(finding)).replace(
                    '"<why>"', '"The user decided against it: <his words>"')),
            )),
        ]))
        return
    started = unanswered_started_findings(record)
    if started:
        branch = record["started"][str(started[0])]
        findings = unanswered_started_findings(record, branch)
        switch = ("" if git(".", ["branch", "--show-current"]).strip() == branch
                  else f"First run: git switch {branch}\n")
        print(f"Next: topic branch {branch} takes on {findings_text(findings)}, which "
              f"{'has' if len(findings) == 1 else 'have'} no pull request yet.\n"
              + switch +
              "On that branch, make the change with its tests, and commit, unless you have.\n"
              f"Write {FOLLOW_UP_PULL_REQUEST_TITLE_AND_DESCRIPTION_FILE_NAME} at your worktree's root: "
              f"{TITLE_AND_DESCRIPTION_FORM}.\n"
              f"{DO_NOT_COMMIT_LINE}\n"
              f"Then run: {command(number, 'open-pull-request')}")
        return
    unanswered = [index for index in range(1, request.finding_count + 1) if str(index) not in answers]
    decisions = record.get("user_rulings", {})
    if unanswered:
        print("\n".join([
            f"Next: judge {findings_text(unanswered)}, which {'has' if len(unanswered) == 1 else 'have'} no answer yet:",
            *(line for index in unanswered for line in (
                request.lines[index],
                *([f"The user's decision on finding {index}, which would change "
                   f"{decisions[str(index)]['would_change']}: \"{decisions[str(index)]['decision']}\""]
                  if str(index) in decisions else []))),
            "Check each against origin/main.",
            *(["Do as the user decided on each finding that shows his decision; do not ask him again."]
              if any(str(index) in decisions for index in unanswered) else []),
            f"If a finding no longer holds, run: {command(number, LEAVE_OUT_ARGUMENTS)}",
            f"If a finding would change a design or decision of the user's, run: {command(number, WAITING_ARGUMENTS)}",
            "Otherwise group it with the findings of its topic, one pull request per topic, and for one topic run: "
            f"{command(number, START_ARGUMENTS)}",
        ]))
        return
    print("Next: every finding has an answer.\n"
          f"Run: {command(number, 'finish-and-print-merge-lane-2-message')}\n"
          "Send the message it prints to merge-lane-2 with SendMessage.")


def remove_topic_branches_and_worktrees(number):
    states = state_directory()
    records = read_json(state_file(states, TOPIC_BRANCHES_AND_WORKTREES_FILE_NAME_FORMAT, number), [])
    if not records:
        print(f"No topic branch is recorded for pull request {number}'s follow-up, so remove-topic-branches-and-worktrees removed "
              "nothing.")
        return 0
    again = command(number, "remove-topic-branches-and-worktrees")
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
                        "remove-topic-branches-and-worktrees left it and the topic branches recorded with it: the subagent may still be running.\n"
                        "Wait until the subagent has ended.\n"
                        + pass_on_to_the_user(
                            f"The agent harness still locks worktree {path} of the follow-up of "
                            f"{build_followed_up_pull_request_citation_with_title_and_link(number)}, so remove-topic-branches-and-worktrees "
                            "could not remove it.", "If the worktree is still locked when you end your turn, pass")
                        + f"\n{SUBAGENT_LINE}")
        elif reason is not None:
            locked = f"locked (lock reason: {reason or 'none given'})"
            left.append(f"Worktree {path} is {locked}, so remove-topic-branches-and-worktrees "
                        "left it and the topic branches recorded with it.\n"
                        + pass_on_to_the_user(
                            f"Worktree {path} of the follow-up of {build_followed_up_pull_request_citation_with_title_and_link(number)} is {locked}, "
                            "so remove-topic-branches-and-worktrees left it.",
                            "If anyone may still be using the worktree, leave it, and pass") + "\n"
                        f"Otherwise list its changed or untracked files with git -C {path} status "
                        "--short, read them, copy out any that is work to keep, and tell merge-lane-2 "
                        "about it with SendMessage.\n"
                        f"Then run: git worktree remove --force --force {path}\n"
                        "If you are a subagent, pass any sentence for the user to the agent that "
                        "dispatched you instead.")
        else:
            changed = git(path, ["status", "--short"]).rstrip("\n")
            if changed:
                left.append(f"Worktree {path} holds changed or untracked files, so remove-topic-branches-and-worktrees left it and "
                            f"the topic branches recorded with it:\n{changed}\n"
                            "Read them, copy out of the worktree any file that is work to keep, such as a "
                            "change the subagent did not push, and tell merge-lane-2 about it with "
                            "SendMessage.\n"
                            f"Then run: git worktree remove --force {path}")
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
            commits = git(".", ["log", "--oneline", "refs/heads/" + branch, "--not", "--remotes=origin"]).rstrip("\n")
            left.append(f"Branch {branch} holds commits on no branch of origin, so remove-topic-branches-and-worktrees left it:\n"
                        f"{commits}\n"
                        f"Read them with git log -p {branch} --not --remotes=origin, copy out any that is work to keep, "
                        "and tell merge-lane-2 about it with SendMessage.\n"
                        f"Then run: git branch -D {branch}")
            continue
        git(".", ["branch", "-D", branch])
        print(f"Deleted branch {branch}.")
    if left:
        print("\n".join(left))
        print(f"Clean-up of pull request {number}'s follow-up left {len(left)} "
              + ("worktree or branch" if len(left) == 1 else "worktrees or branches")
              + " in place; each is above, with what to do.\n"
              + f"When you have done what each says, run: {again}")
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


class ArgumentParserThatSaysWhatToDo(argparse.ArgumentParser):
    """argparse's parser, whose error text ends with what the agent should do."""

    def error(self, message):
        super().error(f"{message}, so nothing was done.\n"
                      "Run the same command again with arguments in the form the usage above shows.")


def main(argv=None):
    parser = ArgumentParserThatSaysWhatToDo(
        description="Do the mechanical steps of following up the non-blocking findings merge-lane-2 "
                    "sent after merging a pull request.")
    parser.add_argument("number", metavar="<number>", type=int, help="the merged pull request's number")
    # Without prog, argparse builds it by wrapping the usage line, which can break it onto two lines.
    subcommands = parser.add_subparsers(dest="subcommand", required=True, prog=f"{parser.prog} <number>")
    subcommands.add_parser("next-step", help="in the subagent's worktree: fetch origin and print the step that "
                                             "comes next")
    start_parser = subcommands.add_parser(
        "start-topic-branch", help="in the subagent's worktree: make a topic branch from origin/main and record it")
    start_parser.add_argument("branch", metavar="topic-branch")
    start_parser.add_argument("--finding-numbers", type=finding_numbers, required=True,
                              help="the findings the topic branch takes on, such as 1,3")
    open_parser = subcommands.add_parser(
        "open-pull-request", help="push the recorded topic branch, open its pull request and record its link")
    open_parser.add_argument("--handled-finding-numbers", type=finding_numbers,
                             help="the findings the pull request handles, such as 1,3; by default those "
                                  "start-topic-branch recorded for the branch that have no answer")
    leave_out_parser = subcommands.add_parser("record-finding-leave-out-reason", help="record why a finding is left out")
    leave_out_parser.add_argument("finding", type=int)
    leave_out_parser.add_argument("--reason", required=True)
    waiting_parser = subcommands.add_parser(
        "record-finding-as-waiting-for-user-ruling",
        help="record that a finding waits for the user's decision, because it would change a design or decision of his")
    waiting_parser.add_argument("finding", type=int)
    waiting_parser.add_argument("--what-it-would-change", required=True,
                                help="which of the user's designs or decisions the finding would change")
    reopen_parser = subcommands.add_parser(
        "reopen-waiting-finding-with-user-ruling",
        help="in the author's checkout, once the user wants a waiting finding's change: record his decision and "
             "reopen the finding for a new subagent")
    reopen_parser.add_argument("finding", type=int)
    reopen_parser.add_argument("--user-ruling", required=True, help="the user's decision, in his words")
    subcommands.add_parser("finish-and-print-merge-lane-2-message", help="check every finding has an answer and print the message "
                                          "for merge-lane-2")
    subcommands.add_parser("remove-topic-branches-and-worktrees", help="in the author's checkout, once the subagent has ended: "
                                            "remove each recorded worktree and topic branch")
    arguments = parser.parse_args(argv)
    try:
        if arguments.subcommand == "next-step":
            next_step(arguments.number)
        elif arguments.subcommand == "start-topic-branch":
            start_topic_branch(arguments.number, arguments.branch, arguments.finding_numbers)
        elif arguments.subcommand == "open-pull-request":
            open_pull_request(arguments.number, arguments.handled_finding_numbers)
        elif arguments.subcommand == "record-finding-leave-out-reason":
            record_finding_leave_out_reason(arguments.number, arguments.finding, arguments.reason)
        elif arguments.subcommand == "record-finding-as-waiting-for-user-ruling":
            record_finding_as_waiting_for_user_ruling(arguments.number, arguments.finding, arguments.what_it_would_change)
        elif arguments.subcommand == "reopen-waiting-finding-with-user-ruling":
            reopen_waiting_finding_with_user_ruling(arguments.number, arguments.finding, arguments.user_ruling)
        elif arguments.subcommand == "finish-and-print-merge-lane-2-message":
            finish_and_print_merge_lane_2_message(arguments.number)
        else:
            return remove_topic_branches_and_worktrees(arguments.number)
    except Refused as refusal:
        print(f"REFUSED: {refusal}", file=sys.stderr)
        return 1
    except StepFailed as failure:
        instructions = failure.instructions or (
            pass_on_to_the_user(fails_sentence(arguments.subcommand, arguments.number, failure))
            + f"\n{SUBAGENT_LINE}")
        print(f"FAILED: {failure}\n"
              f"{arguments.subcommand} stopped there; what it did before the failure stays done.\n"
              + instructions, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
