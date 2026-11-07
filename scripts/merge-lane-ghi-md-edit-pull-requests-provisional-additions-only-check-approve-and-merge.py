#!/usr/bin/env python3
"""Approve and merge each open GHI-MD edit pull request that only adds provisional-additions, and tell merge-lane-2 about each other one.

Usage:
  scripts/merge-lane-ghi-md-edit-pull-requests-provisional-additions-only-check-approve-and-merge.py
      [--merge-lane-worktrees-and-outputs-directory DIR] [--merge-lane-review-worktrees-directory DIR]
      [--review-tools-worktree-at-main DIR]

Cron runs it every 5 minutes on ned-box, whether or not any agent-session is
running. It is installed on ned-box alone by
nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py, from the
table beside it, scheduled-jobs-on-each-machine.json:

    */5 * * * * /usr/bin/python3 /home/nedlern/Projects/nedschorus/scripts/merge-lane-ghi-md-edit-pull-requests-provisional-additions-only-check-approve-and-merge.py >> /home/nedlern/.claude/merge-lane-ghi-md-edit-pull-requests-provisional-additions-only-check-approve-and-merge.log 2>&1

Each invocation lists every open pull request
whose title starts "GHI-MD edit for issue" and, for each one that is not a
draft pull request, is not on the held list and has not already been
reported at its nc-head-commit, reads its diff and passes it when all of
these hold:
  - it changes exactly one file, and that file is under docs/issues/ and
    is neither new nor renamed;
  - the diff removes no line and adds at least one;
  - every added line that starts with "#" is exactly the heading
    "## Provisional additions (not yet vetted by the user)";
  - in the file at the nc-head-commit, which it reads too, that heading
    appears once, and every added line that is not blank lies under it,
    before the next line that starts with "#".
A passing pull request is approved as ned-review-merge, pinned to the
nc-head-commit that was read, and merged by running
merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py
from the checkout this program is in, with the approval's time as the
reviewed-since time. The merge's merge-gate.sh runs from this program's own
review tools worktree, by default
~/.cache/merge-lane-review-worktrees/merge-lane-ghi-md-edit-pull-requests-check-approve-and-merge-review-tools-worktree-at-main, which is
made when missing and moved to origin/main before each merge, so no review
merge-lane-2 is running uses it.

Every other pull request, and every one whose approval or merge fails, gets
one message for merge-lane-2: a file
needs-a-look/pr<number>-<first 12 characters of the nc-head-commit>.txt under
the state directory, <merge-lane-worktrees-and-outputs-directory>/merge-lane-ghi-md-edit-pull-requests-check-approve-and-merge-hold-list-reported-heads-and-needs-a-look-messages,
by default /home/nedlern/nedschorus-logs/seats/merge-lane-2/merge-helpers/merge-lane-ghi-md-edit-pull-requests-check-approve-and-merge-hold-list-reported-heads-and-needs-a-look-messages.
No program in the repository can hand a message to an agent-session
without a model, so the message is this file, which merge-lane-2's running
watcher, or its next agent-session, reads; merge-lane-2 deletes the file once
it has handled the pull request. reported-nc-head-commits.json in the state
directory records the nc-head-commit each message was written for: a
reported pull request is left alone, never approved, merged or reported
again, until its nc-head-commit changes. A pull request that is no longer
open is dropped from that record.

The held list is held-pull-requests.txt in the state directory, which
merge-lane-2 edits: one pull request number to a line, with blank lines and
lines starting "#" ignored. A held pull request is neither merged nor
reported. The program reads no project-wide merge pause, because the
repository has none; removing its cron line stops it altogether.

An invocation that stops, exit 2 below, also writes its reason to
needs-a-look/invocation-stopped.txt, which each later stop replaces.

Two invocations never overlap: each takes an exclusive flock on .lock in the
state directory without waiting, and an invocation that finds it held prints
so and exits 0, because a merge and its after-merge test run can outlast 5
minutes.

What it does not handle: a heading written with leading spaces or as an
underline is not recognised as a heading. It does not retry a failed approval or merge at the
same nc-head-commit; merge-lane-2 handles that pull request by hand. An
approval whose merge then fails stays on the pull request.

Output: one line for each pull request merged, held or reported, and each
failure; nothing when there is nothing to do. Cron appends the output to
~/.claude/merge-lane-ghi-md-edit-pull-requests-provisional-additions-only-check-approve-and-merge.log.

Exit codes: 0 every pull request was merged, skipped or reported; 1 one or
more approvals or merges failed, each reported to merge-lane-2; 2 the
invocation stopped before handling every pull request, because the lock,
the held list, the record, the merge account's token, a gh read, the review
tools worktree or a message file could not be read or written, or the held
list or the record is malformed.
"""

import argparse
import fcntl
import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_common_spec = importlib.util.spec_from_file_location(
    "merge_lane_pull_request_helpers_common", Path(__file__).resolve().with_name(
        "merge-lane-pull-request-helpers-common-options-paths-and-token.py"))
common = importlib.util.module_from_spec(_common_spec)
_common_spec.loader.exec_module(common)

PROGRAM = Path(__file__).stem
REPOSITORY = common.REPOSITORY
CHECKOUT = Path(__file__).resolve().parents[1]
MERGE_PROGRAM = Path(__file__).resolve().with_name(
    "merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py")
TITLE_PREFIX = "GHI-MD edit for issue"
PROVISIONAL_HEADING = "## Provisional additions (not yet vetted by the user)"
STATE_DIRECTORY_NAME = "merge-lane-ghi-md-edit-pull-requests-check-approve-and-merge-hold-list-reported-heads-and-needs-a-look-messages"
REVIEW_TOOLS_WORKTREE_NAME = "merge-lane-ghi-md-edit-pull-requests-check-approve-and-merge-review-tools-worktree-at-main"
HELD_LIST_NAME = "held-pull-requests.txt"
RECORD_NAME = "reported-nc-head-commits.json"
MESSAGES_DIRECTORY_NAME = "needs-a-look"
STOPPED_MESSAGE_NAME = "invocation-stopped.txt"
# gh pr list returns 30 pull requests unless told otherwise.
OPEN_PULL_REQUEST_LIST_LIMIT = 1000
GH_TIMEOUT_SECONDS = 120
GIT_TIMEOUT_SECONDS = 300
MERGE_OUTPUT_LINES_IN_MESSAGE = 15

EXIT_HANDLED = 0
EXIT_APPROVAL_OR_MERGE_FAILED = 1
EXIT_STOPPED = 2


class Stopped(Exception):
    """The invocation cannot go on; the text says why."""


def parse_arguments(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    common.add_directory_options(parser, f"the state directory {STATE_DIRECTORY_NAME} and the "
                                         "after-merge test runs' logs")
    arguments = parser.parse_args(argv)
    review_tools_given = arguments.review_tools_worktree_at_main is not None
    arguments = common.resolve_path_options(arguments)
    if not review_tools_given:
        arguments.review_tools_worktree_at_main = (
            arguments.merge_lane_review_worktrees_directory / REVIEW_TOOLS_WORKTREE_NAME)
    return arguments


def say(line):
    print(f"{PROGRAM}: {line}", flush=True)


def read_held_list(path):
    """Return the set of held pull request numbers; a missing file holds none."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return set()
    except OSError as error:
        raise Stopped(f"could not read the held list {path}: {error}") from error
    held = set()
    for number, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if not line.isdigit():
            raise Stopped(f"line {number} of the held list {path} is not a pull request number: "
                          f"{line!r}. Fix the line; nothing is merged until it is fixed")
        held.add(int(line))
    return held


def read_record(path):
    """Return {pull request number: nc-head-commit reported}; a missing file records none."""
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as error:
        raise Stopped(f"could not read the record {path}: {error}") from error
    if not isinstance(record, dict) or not all(
            key.isdigit() and isinstance(value, str) for key, value in record.items()):
        raise Stopped(f"the record {path} is not a JSON object of pull request numbers to "
                      f"nc-head-commits")
    return {int(key): value for key, value in record.items()}


def write_record(path, record):
    """Replace the record by rename, so a reader never sees half a file."""
    written = path.with_name(path.name + ".being-written")
    try:
        written.write_text(json.dumps({str(key): record[key] for key in sorted(record)},
                                      indent=1) + "\n", encoding="utf-8")
        os.rename(written, path)
    except OSError as error:
        raise Stopped(f"could not write the record {path}: {error}") from error


def gh(environment, *arguments):
    """Run gh; return its stdout, or raise Stopped naming the call and its error."""
    try:
        completed = subprocess.run(["gh", *arguments], capture_output=True, text=True,
                                   env=environment, stdin=subprocess.DEVNULL,
                                   timeout=GH_TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise Stopped(f"gh {' '.join(arguments[:3])} could not run: {error}") from error
    if completed.returncode != 0:
        raise Stopped(f"gh {' '.join(arguments[:3])} exited {completed.returncode}: "
                      f"{completed.stderr.strip() or 'no error printed'}")
    return completed.stdout


def gh_json(environment, *arguments):
    output = gh(environment, *arguments)
    try:
        return json.loads(output)
    except ValueError as error:
        raise Stopped(f"gh {' '.join(arguments[:3])} printed no JSON: {output[:200]!r}") from error


def provisional_additions_only_problem(files, diff):
    """Return None when the diff passes the checks that need no file, else what makes the pull request need a look."""
    if len(files) != 1 or not files[0].startswith("docs/issues/"):
        return f"it changes {len(files)} files ({', '.join(files)}), not exactly one under docs/issues/"
    lines = diff.splitlines()
    if f"--- a/{files[0]}" not in lines or f"+++ b/{files[0]}" not in lines:
        return f"its diff does not change {files[0]} in place: the file is new, renamed or binary"
    removed = [line for line in lines if line.startswith("-") and line != f"--- a/{files[0]}"]
    if removed:
        return f"its diff removes {len(removed)} lines, first {removed[0][:120]!r}"
    other_headings = [line for line in lines
                      if line.startswith("+#") and line != "+" + PROVISIONAL_HEADING]
    if other_headings:
        return (f"it adds {len(other_headings)} lines starting \"#\" other than the heading "
                f"\"{PROVISIONAL_HEADING}\", first {other_headings[0][:120]!r}")
    return None


def added_lines_outside_section_problem(diff, file_text):
    """Return None when every added line that is not blank lies in the provisional-additions section of file_text, the file at the nc-head-commit, else why not."""
    file_lines = file_text.splitlines()
    heading_lines = [number for number, line in enumerate(file_lines, start=1)
                     if line == PROVISIONAL_HEADING]
    if len(heading_lines) != 1:
        return (f"the file at the nc-head-commit has the heading \"{PROVISIONAL_HEADING}\" "
                f"{len(heading_lines)} times, not once")
    section_start = heading_lines[0]
    section_end = next((number for number, line in enumerate(file_lines, start=1)
                        if number > section_start and line.startswith("#")),
                       len(file_lines) + 1)
    added = []
    new_line = None
    for line in diff.splitlines():
        hunk = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
        if hunk:
            new_line = int(hunk.group(1))
        elif new_line is not None and line.startswith("+"):
            added.append((new_line, line[1:]))
            new_line += 1
        elif new_line is not None and line.startswith(" "):
            new_line += 1
    if not added:
        return "its diff adds no line"
    outside = [(number, text) for number, text in added
               if text.strip() and not section_start <= number < section_end]
    if outside:
        number, text = outside[0]
        return (f"it adds {len(outside)} lines outside the section \"{PROVISIONAL_HEADING}\" "
                f"(lines {section_start} to {section_end - 1} of the file), first line "
                f"{number}: {text[:120]!r}")
    return None


def approval_body(path, diff):
    if ("+" + PROVISIONAL_HEADING) in diff.splitlines():
        section = f"adding a \"{PROVISIONAL_HEADING[3:]}\" section"
    else:
        section = f"adding lines to its existing \"{PROVISIONAL_HEADING[3:]}\" section"
    return (f"Approved by merge-lane-2's scheduled job {PROGRAM}. Prose tier: the pull request "
            f"changes only {path} (checked against the diff: one file, no lines removed), "
            f"{section}, the form the user's task-to-GHI sweep asks for. No independent "
            f"reviewer: prose under docs/ is silent to reviewers under CLAUDE.md's review-scope "
            f"rule.")


def git(*arguments):
    try:
        completed = subprocess.run(["git", *arguments], capture_output=True, text=True,
                                   stdin=subprocess.DEVNULL, timeout=GIT_TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise Stopped(f"git {' '.join(arguments)} could not run: {error}") from error
    if completed.returncode != 0:
        raise Stopped(f"git {' '.join(arguments)} exited {completed.returncode}: "
                      f"{completed.stderr.strip()}")


def review_tools_worktree_move_to_main(worktree):
    """Make the worktree at origin/main when missing; else fetch and check out origin/main."""
    if not worktree.exists():
        git("-C", str(CHECKOUT), "fetch", "-q", "origin")
        git("-C", str(CHECKOUT), "worktree", "add", "-q", "--detach", str(worktree), "origin/main")
        return
    git("-C", str(worktree), "fetch", "-q", "origin")
    git("-C", str(worktree), "checkout", "-q", "--force", "--detach", "origin/main")


class Invocation:
    def __init__(self, arguments, environment):
        self.arguments = arguments
        self.environment = environment
        self.state_directory = (arguments.merge_lane_worktrees_and_outputs_directory
                                / STATE_DIRECTORY_NAME)
        self.record_path = self.state_directory / RECORD_NAME
        self.record = read_record(self.record_path)
        self.held = read_held_list(self.state_directory / HELD_LIST_NAME)
        self.failed = False

    def report(self, pull_request, why, details=""):
        """Write merge-lane-2's message for this nc-head-commit, then record it."""
        number, head = pull_request["number"], pull_request["headRefOid"]
        messages = self.state_directory / MESSAGES_DIRECTORY_NAME
        message = messages / f"pr{number}-{head[:12]}.txt"
        text = (f"GHI-MD edit pull request {number} needs a look: "
                f"https://github.com/{REPOSITORY}/pull/{number}\n"
                f"Title: {pull_request['title']}\n"
                f"nc-head-commit: {head}\n"
                f"Why: {why}\n"
                + (f"\n{details.rstrip()}\n" if details else "")
                + f"\n{PROGRAM} leaves this pull request alone until its nc-head-commit changes.\n"
                  f"Review and merge it, or close it, as any other pull request.\n"
                  f"Delete this file once you have handled it.\n")
        try:
            messages.mkdir(parents=True, exist_ok=True)
            message.write_text(text, encoding="utf-8")
        except OSError as error:
            raise Stopped(f"could not write merge-lane-2's message {message} about pull request "
                          f"{number}: {error}") from error
        self.record[number] = head
        write_record(self.record_path, self.record)
        say(f"pull request {number} needs a look ({why}); merge-lane-2's message is {message}")

    def handle(self, pull_request):
        number, head = pull_request["number"], pull_request["headRefOid"]
        if number in self.held:
            say(f"pull request {number} is on the held list; left alone")
            return
        if self.record.get(number) == head:
            return
        view = gh_json(self.environment, "pr", "view", str(number), "--repo", REPOSITORY,
                       "--json", "files,headRefOid")
        diff = gh(self.environment, "pr", "diff", str(number), "--repo", REPOSITORY)
        head_after_diff = gh_json(self.environment, "pr", "view", str(number), "--repo",
                                  REPOSITORY, "--json", "headRefOid")["headRefOid"]
        if not (view["headRefOid"] == head == head_after_diff):
            say(f"pull request {number}'s nc-head-commit moved while it was read; left for the "
                f"next invocation")
            return
        files = [entry["path"] for entry in view["files"]]
        problem = provisional_additions_only_problem(files, diff)
        if not problem:
            file_text = gh(self.environment, "api", "-H", "Accept: application/vnd.github.raw+json",
                           f"repos/{REPOSITORY}/contents/{files[0]}?ref={head}")
            problem = added_lines_outside_section_problem(diff, file_text)
        if problem:
            self.report(pull_request, problem)
            return
        review_tools_worktree_move_to_main(self.arguments.review_tools_worktree_at_main)
        try:
            review = gh_json(self.environment, "api", "--method", "POST",
                             f"repos/{REPOSITORY}/pulls/{number}/reviews",
                             "-f", f"commit_id={head}", "-f", "event=APPROVE",
                             "-f", f"body={approval_body(files[0], diff)}")
            reviewed_since = review["submitted_at"]
        except (Stopped, KeyError, TypeError) as error:
            self.failed = True
            self.report(pull_request, f"its approval failed: {error}")
            return
        merge = subprocess.run(
            [sys.executable, str(MERGE_PROGRAM), str(number), head, reviewed_since,
             *common.directory_options_argv(self.arguments)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            stdin=subprocess.DEVNULL, cwd=CHECKOUT)
        last_lines = "\n".join(merge.stdout.splitlines()[-MERGE_OUTPUT_LINES_IN_MESSAGE:])
        if merge.returncode == 0:
            say(f"pull request {number} ({files[0]}) merged: "
                f"{(merge.stdout.splitlines() or [''])[-1]}")
            return
        self.failed = True
        outcome = ("merged, but a step after the merge was not done" if merge.returncode == 3
                   else "not merged")
        self.report(pull_request, f"{MERGE_PROGRAM.name} exited {merge.returncode}: {outcome}",
                    f"The last lines it printed:\n{last_lines}")

    def run(self):
        listed = gh_json(self.environment, "pr", "list", "--repo", REPOSITORY, "--state", "open",
                         "--limit", str(OPEN_PULL_REQUEST_LIST_LIMIT),
                         "--json", "number,title,headRefOid,isDraft")
        candidates = [pull_request for pull_request in listed
                      if pull_request["title"].startswith(TITLE_PREFIX)
                      and not pull_request["isDraft"]]
        for pull_request in sorted(candidates, key=lambda entry: entry["number"]):
            self.handle(pull_request)
        open_numbers = {pull_request["number"] for pull_request in listed}
        if set(self.record) - open_numbers:
            self.record = {number: head for number, head in self.record.items()
                           if number in open_numbers}
            write_record(self.record_path, self.record)
        return EXIT_APPROVAL_OR_MERGE_FAILED if self.failed else EXIT_HANDLED


def stopped_message_write(state_directory, error):
    """Tell merge-lane-2 why the latest invocation stopped, in one file each stop replaces."""
    message = state_directory / MESSAGES_DIRECTORY_NAME / STOPPED_MESSAGE_NAME
    try:
        message.parent.mkdir(parents=True, exist_ok=True)
        message.write_text(
            f"{PROGRAM} stopped at {datetime.now(timezone.utc).isoformat(timespec='seconds')} "
            f"before handling every open GHI-MD edit pull request:\n{error}\n\n"
            f"Each later invocation that stops replaces this file. Fix the cause, then delete "
            f"this file.\n", encoding="utf-8")
    except OSError as write_error:
        say(f"could not write merge-lane-2's message {message}: {write_error}")


def main(argv=None):
    arguments = parse_arguments(sys.argv[1:] if argv is None else argv)
    state_directory = arguments.merge_lane_worktrees_and_outputs_directory / STATE_DIRECTORY_NAME
    lock_path = state_directory / ".lock"
    try:
        state_directory.mkdir(parents=True, exist_ok=True)
        lock = open(lock_path, "a")
    except OSError as error:
        say(f"STOPPED: could not open the lock {lock_path}: {error}")
        return EXIT_STOPPED
    with lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            say(f"another invocation holds {lock_path}; nothing to do")
            return EXIT_HANDLED
        try:
            environment = {**os.environ, "GH_TOKEN": common.read_merge_account_token()}
            return Invocation(arguments, environment).run()
        except (Stopped, common.MergeAccountTokenUnusable) as error:
            say(f"STOPPED: {error}")
            stopped_message_write(state_directory, error)
            return EXIT_STOPPED


if __name__ == "__main__":
    sys.exit(main())
