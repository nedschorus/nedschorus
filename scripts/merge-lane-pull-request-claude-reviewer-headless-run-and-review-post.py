#!/usr/bin/env python3
"""Run the Claude reviewer on a pull request with no one at the prompt, then post its review as mac-claude.

Did the reviewer finish and was its review posted? Exits 0 if the reviewer
returned a valid review and it was posted and read back; 1 if the reviewer did
not finish, its answer was not a valid review, its checkout moved, or the
posting failed, with nothing posted except in the last case; 2 if it refused
before the reviewer ran.

Usage:
  scripts/merge-lane-pull-request-claude-reviewer-headless-run-and-review-post.py
      <pull request number> <tag> <nc-head-commit>
      [--merge-lane-worktrees-and-outputs-directory DIR] [--merge-lane-review-worktrees-directory DIR] [--review-tools-worktree-at-main DIR]
      [--time-limit-seconds N]

The review program runs this as its fifth step, at the same time as the Codex
review and the head test run. The
reviewer's prompt is the brief step 2 wrote, briefs/brief-<tag>-mac-claude.md
under the worktrees and outputs directory, given on stdin, because
--allowedTools takes several values and would swallow a prompt after it. The
reviewer runs as

  claude -p --strict-mcp-config --permission-mode dontAsk --json-schema <schema>
      --output-format json --allowedTools Read Grep Glob Bash WebFetch WebSearch

in pr<n>-head, which step 1 built detached at the nc-head-commit; a refused
tool call does not wait for anyone, and is listed in the output's
permission_denials, each of which is printed. The reviewer's environment has no
GH_TOKEN or GITHUB_TOKEN, and GH_CONFIG_DIR is an empty directory, so gh has no
login in it. The run gets --time-limit-seconds, 5400 by default. Whenever the
wait for it ends, at the time limit, on an interrupt or SIGTERM, or when claude
exits, the run's whole process group is killed and reaped, before the cleanup
below: the reviewer runs in its own session, so nothing else would stop it.

claude exits 0 with subtype "success" even when the reviewer never produced an
answer the schema accepts; only structured_output being null or absent, as
after a refusal, shows that. claude checks the answer against the schema too,
but this program does not rely on claude, whose checks it cannot see: the
answer is checked here against every rule of
merge-lane-pull-request-claude-reviewer-review-schema.json, the one place the
answer's fields are defined, minLength and minimum included. A
schema that uses a keyword or type this check does not know is refused before
the reviewer runs, so no rule of the schema goes unchecked. A COULD_NOT_REVIEW
verdict is a review that did not
finish. After the run, the head worktree must still be at the nc-head-commit:
the project's freshness hook fast-forwards a detached checkout with no commits
of its own, and a review of a moved checkout is not of this head.

Each run's records are kept in claude-reviews/pr<n>-<nc-head-commit>/ under the
worktrees and outputs directory, or -2, -3 and on for later runs on the same
head: run.json, claude's whole output; run-stderr.txt; resume.txt, the session
id and the directory the run started in; note.txt, the answer's note for
merge-lane-2; review.json, the answer posted, without its note; and posted.txt,
what the posting script printed. A follow-up question to the reviewer is asked
with the claude -p --resume command this prints.

The answer's "note" is what the reviewer wants merge-lane-2 to know outside the
review. It is printed and saved whenever the answer is valid, even when nothing
is posted, as for COULD_NOT_REVIEW, and never reaches the posting script.

The answer is posted by merge-lane-pull-request-reviewer-review-post-and-read-back.py,
which alone reads mac-claude's token, after the reviewer's process has ended.

Last, whatever happened, every worktree of the clone whose directory name
starts with mac-claude-pr<n>-, the names the reviewer's standing text gives
the worktrees it makes, is removed, so a run that crashed leaves none behind.
A removal that fails is printed, and does not change the exit code.

The posting script runs in this program's process group, so a terminal's
Ctrl-C reaches it and its gh directly, even when whoever ran this kills this
program first. An interrupt or SIGTERM sent to this program alone during the
posting step sends the posting script SIGTERM, not SIGINT, because a program
started as a background job of a non-interactive shell, and every program it
starts, ignores SIGINT. On SIGTERM the posting script kills its gh, perhaps
after its post, and exits. This waits for that, with no time limit, ignoring
any further interrupt or SIGTERM from then on, prints and keeps in posted.txt
what the posting script printed, then prints that the review may or may not
have been posted, and the gh api command that shows whether it was.
"""

import argparse
import importlib.util
import json
import os
import shlex
import signal
import subprocess
import sys
from pathlib import Path

SCHEMA_FILE_NAME = "merge-lane-pull-request-claude-reviewer-review-schema.json"
POST_SCRIPT_NAME = "merge-lane-pull-request-reviewer-review-post-and-read-back.py"
DEFAULT_TIME_LIMIT_SECONDS = 5400
ALLOWED_TOOLS = ("Read", "Grep", "Glob", "Bash", "WebFetch", "WebSearch")
REMOVED_ENVIRONMENT_VARIABLES = ("GH_TOKEN", "GITHUB_TOKEN")

EXIT_POSTED = 0
EXIT_NOT_DONE = 1
EXIT_REFUSED = 2

_common_spec = importlib.util.spec_from_file_location(
    "merge_lane_pull_request_helpers_common", Path(__file__).resolve().with_name(
        "merge-lane-pull-request-helpers-common-options-paths-and-token.py"))
common = importlib.util.module_from_spec(_common_spec)
_common_spec.loader.exec_module(common)
_command_line_prefix_spec = importlib.util.spec_from_file_location(
    "claude_code_headless_print_mode_command_line_prefix_with_no_connectors_and_explicit_permission_mode_common",
    Path(__file__).resolve().parent.parent / "nc-systems" / "general-tools"
    / "claude-code-headless-print-mode-command-line-prefix-with-no-connectors-and-explicit-permission-mode-common.py")
command_line_prefix = importlib.util.module_from_spec(_command_line_prefix_spec)
_command_line_prefix_spec.loader.exec_module(command_line_prefix)
JSON_SCHEMA_CHECK_MODULE = (Path(__file__).resolve().parent.parent / "nc-systems" / "general-tools"
                            / "json-schema-keyword-subset-answer-check-common.py")
_json_schema_check_spec = importlib.util.spec_from_file_location(
    "json_schema_keyword_subset_answer_check_common", JSON_SCHEMA_CHECK_MODULE)
json_schema_check = importlib.util.module_from_spec(_json_schema_check_spec)
_json_schema_check_spec.loader.exec_module(json_schema_check)
answer_problems = json_schema_check.answer_problems
review_schema_keywords_and_types_the_answer_check_does_not_enforce = (
    json_schema_check.schema_keywords_and_types_the_answer_check_does_not_enforce)
run_all_test_suites = common.run_all_test_suites

REFUSED = ("PR {number}: Claude review not run: {reason}.\n"
           "If the cause above is one you can fix, fix it and run the review program again; "
           "otherwise, tell the user this message.")
NOT_FINISHED = ("PR {number}: Claude review not posted: {reason}.\n"
                "Nothing was posted on GitHub. The run's records are in {record}.\n"
                "Read the reviewer's last answer below, then run this step again with the "
                "same arguments, or tell the user if it fails the same way again.")

# The posting script may have posted before it was killed; only it reads mac-claude's
# token, so the check is left to whoever ran this, with their own gh login.
POSTING_INTERRUPTED = (
    "PR {number}: the posting step was interrupted, so the review in {review_file} may or may "
    "not have been posted.\n"
    "Check before running this step again, because a second run posts a second review:\n"
    "  gh api --paginate 'repos/{repository}/pulls/{number}/reviews' --jq "
    "'.[] | select(.user.login == \"mac-claude\" and .commit_id == \"{head}\") "
    "| [.id, .state, .html_url] | @tsv'")


class Refused(Exception):
    pass


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        description="Run the Claude reviewer headless on a pull request's head worktree, check "
                    "its answer against the review schema, and post it as mac-claude.")
    parser.add_argument("pull_request", type=int, help="the pull request's number")
    parser.add_argument("tag", help="the brief's tag, as in briefs/brief-<tag>-mac-claude.md")
    parser.add_argument("head_commit", help="the full hash of the nc-head-commit under review")
    parser.add_argument("--time-limit-seconds", type=float, default=DEFAULT_TIME_LIMIT_SECONDS,
                        help=f"how long the reviewer may run (default: "
                             f"{DEFAULT_TIME_LIMIT_SECONDS})")
    common.add_directory_options(parser, "briefs/ and claude-reviews/")
    return common.resolve_path_options(parser.parse_args(argv))


def git(directory, *arguments):
    return subprocess.run(
        ["git", "-C", str(directory), *arguments], capture_output=True, text=True,
        stdin=subprocess.DEVNULL,
        env=run_all_test_suites.environment_without_git_redirecting_variables())


def read_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise Refused(f"could not read {path}: {error}")


def hand_over_note(note, record, number):
    note_file = record / "note.txt"
    note_file.write_text(note + "\n" if note.strip() else "")
    if note.strip():
        print(f"PR {number}: the reviewer's note for merge-lane-2, which is private and never "
              f"posted to the pull request; also saved in {note_file}:\n{note}", flush=True)
    else:
        print(f"PR {number}: the reviewer left no note for merge-lane-2.", flush=True)


def record_directory(helpers, number, head):
    """Make and return the first free claude-reviews/pr<n>-<head>[-k] directory."""
    parent = helpers / "claude-reviews"
    parent.mkdir(parents=True, exist_ok=True)
    name, suffix = f"pr{number}-{head}", 1
    while True:
        candidate = parent / (name if suffix == 1 else f"{name}-{suffix}")
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            suffix += 1


def reviewer_environment(record):
    environment = {key: value for key, value in
                   run_all_test_suites.environment_without_git_redirecting_variables().items()
                   if key not in REMOVED_ENVIRONMENT_VARIABLES}
    empty_gh_config = record / "gh-config-empty"
    empty_gh_config.mkdir()
    environment["GH_CONFIG_DIR"] = str(empty_gh_config)
    return environment


def run_reviewer(schema_text, brief, head_worktree, environment, time_limit):
    """Return (exit code or None when killed at the time limit, stdout, stderr)."""
    process = subprocess.Popen(
        [*command_line_prefix.claude_code_headless_print_mode_command_line_prefix_build("dontAsk"),
         "--json-schema", schema_text, "--output-format", "json", "--allowedTools", *ALLOWED_TOOLS],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        cwd=head_worktree, env=environment, start_new_session=True)
    timed_out = False
    try:
        stdout, stderr = process.communicate(brief, timeout=time_limit)
    except subprocess.TimeoutExpired:
        timed_out = True
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
    if timed_out:
        stdout, stderr = process.communicate()
        return None, stdout, stderr
    return process.returncode, stdout, stderr


def remove_reviewer_worktrees(head_worktree, number):
    """Remove the clone's mac-claude-pr<n>- worktrees; print any that could not be removed."""
    listed = git(head_worktree, "worktree", "list", "--porcelain")
    if listed.returncode != 0:
        print(f"PR {number}: could not list worktrees to remove the reviewer's worktrees: "
              f"{listed.stderr.strip()}.\n"
              f"Once git works in {head_worktree} again, list the worktrees of the repository "
              f"it belongs to with `git -C {head_worktree} worktree list`, and remove each one "
              f"whose directory name starts with mac-claude-pr{number}- with "
              f"`git -C {head_worktree} worktree remove --force <the path the list shows>`.\n"
              f"If git cannot be made to work there, tell the user this whole message.",
              flush=True)
        return
    for line in listed.stdout.splitlines():
        if not line.startswith("worktree "):
            continue
        path = line[len("worktree "):]
        if Path(path).name.startswith(f"mac-claude-pr{number}-"):
            removed = git(head_worktree, "worktree", "remove", "--force", path)
            if removed.returncode != 0:
                print(f"PR {number}: could not remove the reviewer's worktree {path}: "
                      f"{removed.stderr.strip()}; remove it yourself.", flush=True)


def resume_command(session_id):
    return shlex.join([*command_line_prefix.claude_code_headless_print_mode_command_line_prefix_build("dontAsk"),
                       "--resume", session_id, "--allowedTools", *ALLOWED_TOOLS])


def exit_on_sigterm(signal_number, frame):
    raise SystemExit(128 + signal_number)


def main(argv=None):
    # SIGTERM must raise, so the finally blocks that stop the reviewer and remove its
    # worktrees run, as they do for an interrupt.
    signal.signal(signal.SIGTERM, exit_on_sigterm)
    arguments = parse_arguments(argv)
    number, tag, head = arguments.pull_request, arguments.tag, arguments.head_commit
    helpers = arguments.merge_lane_worktrees_and_outputs_directory
    head_worktree = common.pull_request_head_worktree(arguments, number)
    here = Path(__file__).resolve().parent
    try:
        brief_file = helpers / "briefs" / f"brief-{tag}-mac-claude.md"
        brief = read_text(brief_file)
        schema_file = here / SCHEMA_FILE_NAME
        schema_text = read_text(schema_file)
        try:
            schema = json.loads(schema_text)
        except ValueError as error:
            raise Refused(f"the review schema {schema_file} is not JSON ({error}), so the "
                          f"reviewer's answer could not be checked against it")
        if not isinstance(schema, dict):
            raise Refused(f"the review schema {schema_file} is not a JSON object, so the "
                          f"reviewer's answer could not be checked against it")
        not_enforced = review_schema_keywords_and_types_the_answer_check_does_not_enforce(schema)
        if not_enforced:
            raise Refused(
                f"the review schema {schema_file} uses JSON-schema keywords or types that this "
                f"program's answer check does not enforce, so an answer could break those rules "
                f"unnoticed: {'; '.join(not_enforced)}. Remove each from the schema, unless "
                f"the reviewer's answer must keep to it; to keep one, add a keyword to "
                f"CHECKED_SCHEMA_KEYWORDS, or a type to JSON_TYPES, and enforce it in "
                f"answer_problems, both in {JSON_SCHEMA_CHECK_MODULE}")
        if not (here / POST_SCRIPT_NAME).is_file():
            raise Refused(f"the posting script {here / POST_SCRIPT_NAME} is missing")
        at = git(head_worktree, "rev-parse", "HEAD")
        if at.returncode != 0 or at.stdout.strip() != head:
            raise Refused(f"the head worktree {head_worktree} is not at the nc-head-commit {head}"
                          f" ({at.stdout.strip() or at.stderr.strip()})")
    except Refused as refusal:
        print(REFUSED.format(number=number, reason=refusal), flush=True)
        return EXIT_REFUSED

    record = record_directory(helpers, number, head)
    try:
        return review_and_post(arguments, number, head, brief, schema_text, schema,
                               head_worktree, record, here)
    finally:
        remove_reviewer_worktrees(head_worktree, number)


def review_and_post(arguments, number, head, brief, schema_text, schema, head_worktree, record,
                    here):
    print(f"PR {number}: Claude reviewer running in {head_worktree}, records in {record}",
          flush=True)
    exit_code, stdout, stderr = run_reviewer(schema_text, brief, head_worktree,
                                             reviewer_environment(record),
                                             arguments.time_limit_seconds)
    (record / "run.json").write_text(stdout)
    (record / "run-stderr.txt").write_text(stderr)
    try:
        output = json.loads(stdout)
    except ValueError:
        output = None
    output = output if isinstance(output, dict) else {}
    session_id = output.get("session_id")
    if session_id:
        (record / "resume.txt").write_text(f"{session_id}\n{head_worktree}\n")
        print(f"PR {number}: to ask the reviewer a follow-up question, run from "
              f"{head_worktree}, with the question on stdin:\n  {resume_command(session_id)}",
              flush=True)
    for denial in output.get("permission_denials") or []:
        if not isinstance(denial, dict):
            denial = {"tool_input": denial}
        tool_input = denial.get("tool_input")
        what = (tool_input["command"] if isinstance(tool_input, dict) and tool_input.get("command")
                else json.dumps(tool_input))
        print(f"PR {number}: the reviewer was refused a {denial.get('tool_name', 'tool')} call "
              f"it asked for: {what}", flush=True)

    answer = output.get("structured_output")
    problems = answer_problems(answer, schema) if answer is not None else []
    if exit_code is None:
        reason = f"the reviewer ran past its {arguments.time_limit_seconds:g}-second limit and was killed"
    elif exit_code != 0:
        reason = f"claude exited {exit_code}: {stderr.strip()[-2000:]}"
    elif not output:
        reason = "claude printed no JSON output"
    elif answer is None:
        reason = "the reviewer finished without an answer the review schema accepts"
    elif problems:
        reason = "the reviewer's answer is not a valid review: " + "; ".join(problems)
    elif answer["verdict"] == "COULD_NOT_REVIEW":
        reason = "the reviewer could not finish the review, and says why below"
    else:
        reason = None
    at = git(head_worktree, "rev-parse", "HEAD")
    if reason is None and (at.returncode != 0 or at.stdout.strip() != head):
        reason = (f"the head worktree {head_worktree} moved to "
                  f"{at.stdout.strip() or at.stderr.strip()} during the review, so the review "
                  f"is not of the nc-head-commit {head}")
    if answer is not None and not problems:
        hand_over_note(answer["note"], record, number)
    if reason is not None:
        last = (answer.get("body") if isinstance(answer, dict) else None) or output.get("result")
        print(NOT_FINISHED.format(number=number, reason=reason, record=record), flush=True)
        print(f"The reviewer's last answer:\n{last or '(none)'}", flush=True)
        return EXIT_NOT_DONE

    review_file = record / "review.json"
    review = {key: answer[key] for key in ("verdict", "body", "comments")}
    review_file.write_text(json.dumps(review, indent=2) + "\n")
    posting = None
    try:
        posting = subprocess.Popen(
            [sys.executable, str(here / POST_SCRIPT_NAME), "--pull-request", str(number),
             "--head-commit", head, str(review_file)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, stdin=subprocess.DEVNULL)
        stdout, stderr = posting.communicate()
    except BaseException:
        # Ignored before terminate(), because a second signal that cut the wait short would
        # skip the report below while the posting script's gh may still be running.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        if posting is not None:
            # Not SIGKILL, which would leave its gh to post after the message below: the
            # posting script's SIGTERM handler makes its subprocess.run kill gh.
            posting.terminate()
            stdout, stderr = posting.communicate()
            (record / "posted.txt").write_text(stdout + stderr)
            sys.stdout.write(stdout + stderr)
        print(POSTING_INTERRUPTED.format(number=number, head=head, review_file=review_file,
                                         repository=common.REPOSITORY), flush=True)
        raise
    (record / "posted.txt").write_text(stdout + stderr)
    sys.stdout.write(stdout + stderr)
    if posting.returncode != 0:
        print(f"PR {number}: the posting script exited {posting.returncode}; act on its message "
              f"above. The review it was given is {review_file}.", flush=True)
        return EXIT_NOT_DONE
    print(f"PR {number}: Claude review posted, verdict {answer['verdict']}.", flush=True)
    return EXIT_POSTED


if __name__ == "__main__":
    sys.exit(main())
