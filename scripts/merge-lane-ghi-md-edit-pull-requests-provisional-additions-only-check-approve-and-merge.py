#!/usr/bin/env python3
r"""Approve and merge each open GHI-MD edit pull request that only adds provisional-additions, and tell merge-lane-2 about each other one.

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
reported at its nc-head-commit, reads the file it changes at its merge base
and at its nc-head-commit, and passes it when all of these hold:
  - it changes exactly one file, and that file is under docs/issues/ and
    is neither new nor renamed;
  - neither text holds a character that Markdown or git reads as a line
    break other than "\n", such as a carriage return or a form feed;
  - the text at the nc-head-commit holds the line
    "## Provisional additions (not yet vetted by the user)" as a heading
    once, and the text at the merge base holds it at most once;
  - its other headings, as a CommonMark parser finds them, are the merge
    base's, one for one, so the pull request adds, removes and changes no
    other heading;
  - with the section under that heading taken out of both texts, they are
    the same, and the section at the nc-head-commit holds every line of the
    merge base's section, when there is one, in order. The section
    runs from the heading to the next heading, without the blank lines
    that end it and with the blank lines just before it;
  - the text at the nc-head-commit differs from the text at the merge base.
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
merge-lane-2's watcher, scripts/watch-open-pull-requests-nbd.py, prints one
event line for each file in needs-a-look/, taking the directory from
needs_a_look_directory() here, at every start until the file is moved;
merge-lane-2 moves the file into needs-a-look/handled/ as soon as it has
read it, and handles the pull request after. Whether a pull
request was reported is read from reported-nc-head-commits.json alone, never
from the files, so moving a file does not report its pull request again.
reported-nc-head-commits.json in the state
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

What it does not handle: it does not retry a failed approval or merge at the
same nc-head-commit; merge-lane-2 handles that pull request by hand. An
approval whose merge then fails stays on the pull request.

Output: one line for each pull request merged, held or reported, and each
failure; nothing when there is nothing to do. Cron appends the output to
~/.claude/merge-lane-ghi-md-edit-pull-requests-provisional-additions-only-check-approve-and-merge.log.

Exit codes: 0 every pull request was merged, skipped or reported; 1 one or
more approvals or merges failed, each reported to merge-lane-2; 2 the
invocation stopped before handling every pull request, because the lock,
the held list, the record, the merge account's token, a gh read, the
Markdown parser, the review tools worktree or a message file could not be
read, loaded or written, or the held list or the record is malformed.
"""

import argparse
import fcntl
import importlib.util
import json
import os
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
MARKDOWN_PARSER_MODULE = (CHECKOUT / "nc-systems" / "general-tools"
                          / "markdown-commonmark-parser-with-tables-common.py")
# Every character Python's str.splitlines() splits on except "\n": CommonMark reads a carriage
# return as a line break where git does not, and other Markdown tools split on the rest.
LINE_BREAKS_OTHER_THAN_NEWLINE = "\r\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029"
STATE_DIRECTORY_NAME = "merge-lane-ghi-md-edit-pull-requests-check-approve-and-merge-hold-list-reported-heads-and-needs-a-look-messages"
REVIEW_TOOLS_WORKTREE_NAME = "merge-lane-ghi-md-edit-pull-requests-check-approve-and-merge-review-tools-worktree-at-main"
HELD_LIST_NAME = "held-pull-requests.txt"
RECORD_NAME = "reported-nc-head-commits.json"
MESSAGES_DIRECTORY_NAME = "needs-a-look"
HANDLED_MESSAGES_DIRECTORY_NAME = "handled"
STOPPED_MESSAGE_NAME = "invocation-stopped.txt"
# gh pr list returns 30 pull requests unless told otherwise.
OPEN_PULL_REQUEST_LIST_LIMIT = 1000
GH_TIMEOUT_SECONDS = 120
GIT_TIMEOUT_SECONDS = 300
MERGE_OUTPUT_LINES_IN_MESSAGE = 15

EXIT_HANDLED = 0
EXIT_APPROVAL_OR_MERGE_FAILED = 1
EXIT_STOPPED = 2


def needs_a_look_directory(
        merge_lane_worktrees_and_outputs_directory=common.DEFAULT_MERGE_LANE_WORKTREES_AND_OUTPUTS_DIRECTORY):
    """Return the directory of merge-lane-2's messages, which watch-open-pull-requests-nbd.py lists too."""
    return (Path(merge_lane_worktrees_and_outputs_directory) / STATE_DIRECTORY_NAME
            / MESSAGES_DIRECTORY_NAME)


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


def gh_bytes(environment, *arguments):
    """Run gh; return its stdout as bytes, or raise Stopped naming the call and its error."""
    try:
        completed = subprocess.run(["gh", *arguments], capture_output=True,
                                   env=environment, stdin=subprocess.DEVNULL,
                                   timeout=GH_TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise Stopped(f"gh {' '.join(arguments[:3])} could not run: {error}") from error
    if completed.returncode != 0:
        error_text = completed.stderr.decode("utf-8", errors="replace").strip()
        raise Stopped(f"gh {' '.join(arguments[:3])} exited {completed.returncode}: "
                      f"{error_text or 'no error printed'}")
    return completed.stdout


def gh_json(environment, *arguments):
    output = gh_bytes(environment, *arguments).decode("utf-8", errors="replace")
    try:
        return json.loads(output)
    except ValueError as error:
        raise Stopped(f"gh {' '.join(arguments[:3])} printed no JSON: {output[:200]!r}") from error


def markdown_parser():
    """Return the project's CommonMark parser; raise Stopped when markdown-it-py cannot be loaded."""
    try:
        specification = importlib.util.spec_from_file_location(
            "markdown_commonmark_parser_with_tables_common", MARKDOWN_PARSER_MODULE)
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
        return module.markdown_parser()
    except Exception as error:
        raise Stopped(f"the Markdown parser {MARKDOWN_PARSER_MODULE} could not be loaded: "
                      f"{error}") from error


def changed_file_problem(files):
    """Return None when the compare's files are one docs/issues/ file changed in place, else why not."""
    paths = [entry["filename"] for entry in files]
    if len(paths) != 1 or not paths[0].startswith("docs/issues/"):
        return f"it changes {len(paths)} files ({', '.join(paths)}), not exactly one under docs/issues/"
    if files[0]["status"] != "modified":
        return (f"it does not change {paths[0]} in place: GitHub calls the change "
                f"\"{files[0]['status']}\"")
    return None


def provisional_section(parser, text, where):
    """Return (lines, headings other than the provisional one, section's first line, line after its end), or a problem string.

    The section's first line is None when the text has no provisional heading; each heading is
    its tag, its nesting level and its source lines."""
    lines = text.split("\n")
    headings = [(token.tag, token.level, "\n".join(lines[token.map[0]:token.map[1]]), token.map[0])
                for token in parser.parse(text) if token.type == "heading_open"]
    provisional = [heading for heading in headings if heading[2] == PROVISIONAL_HEADING]
    if len(provisional) > 1 or (where == "nc-head-commit" and not provisional):
        return (f"the file at the {where} has the heading \"{PROVISIONAL_HEADING}\" "
                f"{len(provisional)} times, not once")
    others = [heading[:3] for heading in headings if heading[2] != PROVISIONAL_HEADING]
    if not provisional:
        return lines, others, None, None
    start = provisional[0][3]
    end = next((heading[3] for heading in headings if heading[3] > start), len(lines))
    while end > start + 1 and not lines[end - 1].strip(" \t"):
        end -= 1
    while start > 0 and not lines[start - 1].strip(" \t"):
        start -= 1
    return lines, others, start, end


def provisional_additions_only_problem(parser, base_text, head_text):
    """Return None when head_text is base_text with lines added only to its provisional-additions section, or with that section added, else why not."""
    for where, text in (("merge base", base_text), ("nc-head-commit", head_text)):
        line_break = next((character for character in text
                           if character in LINE_BREAKS_OTHER_THAN_NEWLINE), None)
        if line_break is not None:
            line = text[:text.index(line_break)].count("\n") + 1
            return (f"the file at the {where} holds U+{ord(line_break):04X} on line {line}, which "
                    f"Markdown or git reads as a line break where the other does not")
    if head_text == base_text:
        return "it does not change the file's text"
    base = provisional_section(parser, base_text, "merge base")
    if isinstance(base, str):
        return base
    head = provisional_section(parser, head_text, "nc-head-commit")
    if isinstance(head, str):
        return head
    (base_lines, base_headings, base_start, base_end), (head_lines, head_headings, start, end) = base, head
    if base_headings != head_headings:
        first = next(index for index in range(max(len(base_headings), len(head_headings)))
                     if base_headings[index:index + 1] != head_headings[index:index + 1])
        return (f"it adds, removes or changes a heading other than \"{PROVISIONAL_HEADING}\": "
                f"heading {first + 1} is {(base_headings[first:first + 1] or ['none'])[0]!r} at the "
                f"merge base and {(head_headings[first:first + 1] or ['none'])[0]!r} at the "
                f"nc-head-commit")
    base_section = base_lines[base_start:base_end] if base_start is not None else []
    base_outside = (base_lines[:base_start] + base_lines[base_end:] if base_start is not None
                    else base_lines)
    head_outside = head_lines[:start] + head_lines[end:]
    if base_outside != head_outside:
        first = next(index for index in range(max(len(base_outside), len(head_outside)))
                     if base_outside[index:index + 1] != head_outside[index:index + 1])
        return (f"it changes text outside the section \"{PROVISIONAL_HEADING}\" (lines "
                f"{start + 1} to {end} of the file at the nc-head-commit): the first line that "
                f"differs is {(base_outside[first:first + 1] or ['none'])[0][:120]!r} at the merge "
                f"base and {(head_outside[first:first + 1] or ['none'])[0][:120]!r} at the "
                f"nc-head-commit")
    head_section = iter(head_lines[start:end])
    if not all(line in head_section for line in base_section):
        return (f"it removes or changes a line of the section \"{PROVISIONAL_HEADING}\" instead "
                f"of only adding lines to it")
    return None


def approval_body(path, section_is_new):
    if section_is_new:
        section = f"adding a \"{PROVISIONAL_HEADING[3:]}\" section"
    else:
        section = f"adding lines to its existing \"{PROVISIONAL_HEADING[3:]}\" section"
    return (f"Approved by merge-lane-2's scheduled job {PROGRAM}. Prose tier: the pull request "
            f"changes only {path} (checked against the file at the merge base and at the "
            f"nc-head-commit with a CommonMark parser: one file, no other text or heading "
            f"changed), {section}, the form the user's task-to-GHI sweep asks for. No independent "
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
        self._parser = None

    def parser(self):
        if self._parser is None:
            self._parser = markdown_parser()
        return self._parser

    def report(self, pull_request, why, details=""):
        """Write the needs-a-look notice for merge-lane-2 for this nc-head-commit, then record it."""
        number, head = pull_request["number"], pull_request["headRefOid"]
        messages = needs_a_look_directory(self.arguments.merge_lane_worktrees_and_outputs_directory)
        message = messages / f"pr{number}-{head[:12]}.txt"
        text = (f"GHI-MD edit pull request {number} needs a look: "
                f"https://github.com/{REPOSITORY}/pull/{number}\n"
                f"Title: {pull_request['title']}\n"
                f"nc-head-commit: {head}\n"
                f"Why: {why}\n"
                + (f"\n{details.rstrip()}\n" if details else "")
                + f"\n{PROGRAM} leaves this pull request alone until its nc-head-commit changes.\n"
                  f"Review and merge it, or close it, as any other pull request.\n"
                  f"Move this file into {messages / HANDLED_MESSAGES_DIRECTORY_NAME} as soon as you "
                  f"have read it: until then the watcher reports it again at each start, before "
                  f"any pull request event.\n")
        try:
            messages.mkdir(parents=True, exist_ok=True)
            message.write_text(text, encoding="utf-8")
        except OSError as error:
            raise Stopped(f"could not write the needs-a-look notice for merge-lane-2 about pull "
                          f"request {number} at {message}: {error}") from error
        self.record[number] = head
        write_record(self.record_path, self.record)
        say(f"pull request {number} needs a look ({why}); the needs-a-look notice for "
            f"merge-lane-2 is at {message}")

    def handle(self, pull_request):
        number, head = pull_request["number"], pull_request["headRefOid"]
        if number in self.held:
            say(f"pull request {number} is on the held list; left alone")
            return
        if self.record.get(number) == head:
            return
        compare = gh_json(self.environment, "api",
                          f"repos/{REPOSITORY}/compare/{pull_request['baseRefName']}...{head}")
        problem = changed_file_problem(compare["files"])
        if not problem:
            path = compare["files"][0]["filename"]
            texts = [gh_bytes(self.environment, "api", "-H", "Accept: application/vnd.github.raw+json",
                              f"repos/{REPOSITORY}/contents/{path}?ref={commit}")
                     for commit in (compare["merge_base_commit"]["sha"], head)]
            try:
                base_text, head_text = (text.decode("utf-8") for text in texts)
            except UnicodeDecodeError as error:
                problem = f"{path} is not UTF-8 at its merge base or its nc-head-commit: {error}"
            else:
                problem = provisional_additions_only_problem(self.parser(), base_text, head_text)
        head_after_read = gh_json(self.environment, "pr", "view", str(number), "--repo",
                                  REPOSITORY, "--json", "headRefOid")["headRefOid"]
        if head_after_read != head:
            say(f"pull request {number}'s nc-head-commit moved while it was read; left for the "
                f"next invocation")
            return
        if problem:
            self.report(pull_request, problem)
            return
        section_is_new = PROVISIONAL_HEADING not in base_text.split("\n")
        review_tools_worktree_move_to_main(self.arguments.review_tools_worktree_at_main)
        try:
            review = gh_json(self.environment, "api", "--method", "POST",
                             f"repos/{REPOSITORY}/pulls/{number}/reviews",
                             "-f", f"commit_id={head}", "-f", "event=APPROVE",
                             "-f", f"body={approval_body(path, section_is_new)}")
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
            say(f"pull request {number} ({path}) merged: "
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
                         "--json", "number,title,headRefOid,isDraft,baseRefName")
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


def stopped_message_write(merge_lane_worktrees_and_outputs_directory, error):
    """Tell merge-lane-2 why the latest invocation stopped, in one file each stop replaces."""
    message = (needs_a_look_directory(merge_lane_worktrees_and_outputs_directory)
               / STOPPED_MESSAGE_NAME)
    try:
        message.parent.mkdir(parents=True, exist_ok=True)
        message.write_text(
            f"{PROGRAM} stopped at {datetime.now(timezone.utc).isoformat(timespec='seconds')} "
            f"before handling every open GHI-MD edit pull request: {error}\n\n"
            f"Each later invocation that stops replaces this file. Move this file into "
            f"{message.parent / HANDLED_MESSAGES_DIRECTORY_NAME} as soon as you have read it, "
            f"then fix the cause.\n", encoding="utf-8")
    except OSError as write_error:
        say(f"could not write the needs-a-look notice for merge-lane-2 at {message}: {write_error}")


def main(argv=None):
    arguments = parse_arguments(sys.argv[1:] if argv is None else argv)
    state_directory = arguments.merge_lane_worktrees_and_outputs_directory / STATE_DIRECTORY_NAME
    lock_path = state_directory / ".lock"
    try:
        state_directory.mkdir(parents=True, exist_ok=True)
        lock = open(lock_path, "a")
    except OSError as error:
        stop = f"could not open the lock {lock_path}: {error}"
        say(f"STOPPED: {stop}")
        stopped_message_write(arguments.merge_lane_worktrees_and_outputs_directory, stop)
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
            stopped_message_write(arguments.merge_lane_worktrees_and_outputs_directory, error)
            return EXIT_STOPPED


if __name__ == "__main__":
    sys.exit(main())
