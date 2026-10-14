#!/usr/bin/env python3
"""Before a git push of a branch that changes a Markdown file, remind the agent
to run scripts/dangling-path-citation-check.py and
scripts/stale-code-citation-check.py.

A PreToolUse hook on Bash. It never blocks the push: it only adds context.
"Changes a Markdown file" means the merge-base diff against origin/main, as
`git diff origin/main...<pushed ref>`, adds, changes, renames or deletes a
`*.md` file: a deleted page matters too, since
scripts/dangling-path-citation-check.py reports the lines that still cite it. The pushed ref is each refspec's source side; a push with no
refspec, or with --all, --mirror or --tags and no refspec, is taken to push
HEAD. A push that deletes a remote branch is not reminded.

The push is found as scripts/force-push-with-open-pull-request-guard-hook.py
finds it, with that guard's parser: behind the wrappers the shared shell
module knows, with git -C, env --chdir and a literal cd earlier in the
command line followed. Commands run by ssh, bash -c, eval or a script file
are outside its reach. A checkout without both citation programs, such as
another repository, gets no reminder, since the commands would not run there.

Any failure, git erroring or the shell reader failing, gives one line saying
the reminder could not be checked, and the push goes on.
"""

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

_force_push_guard_spec = importlib.util.spec_from_file_location(
    "force_push_with_open_pull_request_guard_hook",
    Path(__file__).resolve().parents[2] / "scripts"
    / "force-push-with-open-pull-request-guard-hook.py")
force_push_guard = importlib.util.module_from_spec(_force_push_guard_spec)
_force_push_guard_spec.loader.exec_module(force_push_guard)
shell_reader = force_push_guard.shell_reader
is_program = shell_reader.is_program

HOOK_NAME = "claude-code-bash-git-push-of-markdown-change-citation-checks-reminder"
COMPARED_BRANCH = "origin/main"
CITATION_CHECK_PROGRAMS = ("scripts/dangling-path-citation-check.py",
                           "scripts/stale-code-citation-check.py")
GIT_TIMEOUT_SECONDS = 10
# The reminder names this many changed files and counts the rest.
NAMED_FILE_LIMIT = 5

ENVIRONMENT_ASSIGNMENT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
UNEXPANDED_PATTERN = force_push_guard.UNEXPANDED_PATTERN

REMINDER_TEMPLATE = (
    HOOK_NAME + ": this push sends {ref}, which changes {count} Markdown "
    "file(s) against " + COMPARED_BRANCH + ": {files}.\n"
    "Run both citation checks on the branch now, from its checkout:\n"
    "cd {top} && python3 " + CITATION_CHECK_PROGRAMS[0] + "\n"
    "cd {top} && python3 " + CITATION_CHECK_PROGRAMS[1] + "\n"
    "The first reports each repository path cited on a changed line that does "
    "not exist; the second reports each line-number citation in a design "
    "document whose cited code changed after the document's design-as-of "
    "date. Each exits 0 when it finds nothing and 1 when it reports a "
    "finding.\n"
    "{checkout_line}"
    "If either program reports a finding, fix the finding in a new commit on "
    "top of this push, and push that commit once."
)

NOT_CHECKED_OUT_LINE_TEMPLATE = (
    "{ref} is not what is checked out in {top}, so check {ref} out there "
    "first: both programs read the checkout, not the pushed ref.\n"
)

FAILURE_LINE_TEMPLATE = (
    HOOK_NAME + ": could not check whether this push changes a Markdown file "
    "({error}), so the push goes on without that check; if the push does change one, "
    "run python3 " + CITATION_CHECK_PROGRAMS[0] + " and python3 "
    + CITATION_CHECK_PROGRAMS[1] + " from the checkout's top directory."
)


class ReminderCheckFailure(Exception):
    pass


def git_output(arguments, directory, runner=None):
    """Return git's standard output, or raise ReminderCheckFailure saying why git failed.

    runner stands in for subprocess.run, so a replay of recorded commands can answer git itself.
    """
    try:
        completed = (runner or subprocess.run)(
            ["git", "-C", str(directory), *arguments], capture_output=True,
            text=True, errors="surrogateescape", timeout=GIT_TIMEOUT_SECONDS,
            check=False)
    except subprocess.TimeoutExpired as error:
        raise ReminderCheckFailure(
            f"git {arguments[0]} did not answer within {GIT_TIMEOUT_SECONDS} seconds") from error
    except (OSError, ValueError) as error:
        raise ReminderCheckFailure(f"git could not be run: {error}") from error
    if completed.returncode != 0:
        first_line = (completed.stderr.strip().splitlines() or [""])[0][:200]
        raise ReminderCheckFailure(
            f"git {arguments[0]} exited {completed.returncode}: {first_line}")
    return completed.stdout


def push_deletes(push_words):
    """Whether the words after git push ask for a remote branch to be deleted."""
    for word in push_words:
        if word == "--":
            return False
        if word == "--delete":
            return True
        if word.startswith("-") and not word.startswith("--") and "d" in word[1:]:
            return True
    return False


def pushed_refs(push_words):
    """Return the refs a push sends: each refspec's source, or HEAD when none is written."""
    if push_deletes(push_words):
        return []
    _, refspecs = force_push_guard.parse_push_arguments(push_words)
    if not refspecs:
        return ["HEAD"]
    refs = []
    for spec in refspecs:
        source = (spec[1:] if spec.startswith("+") else spec).split(":", 1)[0]
        if source:  # An empty source deletes the destination.
            refs.append(source)
    return refs


def push_message(invocation, directory, unresolved_directory, runner=None):
    """Return the reminder or failure line for one git push, or None when nothing is to be said."""
    override = invocation["directory_override"]
    if override is not None:
        if UNEXPANDED_PATTERN.search(override):
            raise ReminderCheckFailure(f"the push runs in a directory this hook cannot read, {override}")
        directory = force_push_guard.resolve_directory(directory, override)
    elif unresolved_directory is not None:
        raise ReminderCheckFailure(
            f"the push runs in a directory this hook cannot read, {unresolved_directory}")
    refs = pushed_refs(invocation["push_words"])
    if not refs:
        return None
    top = git_output(["rev-parse", "--show-toplevel"], directory, runner).strip()
    if not all((Path(top) / program).is_file() for program in CITATION_CHECK_PROGRAMS):
        return None
    for ref in refs:
        if UNEXPANDED_PATTERN.search(ref):
            raise ReminderCheckFailure(f"the push names a ref this hook cannot read, {ref}")
        changed = git_output(
            ["diff", "--name-only", "-z", f"{COMPARED_BRANCH}...{ref}", "--", "*.md"], top, runner)
        files = [name for name in changed.split("\0") if name]
        if files:
            named = ", ".join(files[:NAMED_FILE_LIMIT])
            if len(files) > NAMED_FILE_LIMIT:
                named += f" and {len(files) - NAMED_FILE_LIMIT} more"
            checked_out = (git_output(["rev-parse", "--verify", "-q", f"{ref}^{{commit}}"], top, runner)
                           == git_output(["rev-parse", "--verify", "-q", "HEAD^{commit}"], top, runner))
            if ref == "HEAD":
                ref = git_output(["branch", "--show-current"], top, runner).strip() or "HEAD"
            checkout_line = "" if checked_out else NOT_CHECKED_OUT_LINE_TEMPLATE.format(ref=ref, top=top)
            return REMINDER_TEMPLATE.format(ref=ref, count=len(files), files=named, top=top,
                                            checkout_line=checkout_line)
    return None


def messages_for_command(command, payload_cwd, runner=None):
    """Return the reminder and failure lines for every git push in the command line."""
    # A child shell inherits its parent's directory; its cd must not affect the parent.
    directories = {(): (payload_cwd, None)}  # Per child shell: (directory, unresolved cd target).
    messages = []
    for words in shell_reader.simple_commands(command):
        enclosing = words.child_shell
        while enclosing not in directories:
            enclosing = enclosing[:-1]
        directory, unresolved_directory = directories[enclosing]
        program_index = 0
        while (program_index < len(words)
               and ENVIRONMENT_ASSIGNMENT_PATTERN.match(words[program_index])):
            program_index += 1
        if program_index + 1 < len(words) and is_program(words[program_index], "cd"):
            target = words[program_index + 1]
            if UNEXPANDED_PATTERN.search(target):
                unresolved_directory = target
            else:
                directory = force_push_guard.resolve_directory(directory, target)
                unresolved_directory = None
            directories[words.child_shell] = (directory, unresolved_directory)
            continue
        invocation = force_push_guard.find_git_push_invocation(words)
        if invocation is None:
            continue
        try:
            message = push_message(invocation, directory, unresolved_directory, runner)
        except ReminderCheckFailure as failure:
            message = failure_line(failure)
        if message and message not in messages:
            messages.append(message)
    return messages


def failure_line(error):
    return FAILURE_LINE_TEMPLATE.format(error=" ".join(str(error).split()))


def add_context(text):
    # No permissionDecision: an allow would bypass the permission rules.
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "additionalContext": text,
    }}))


def main(stdin=sys.stdin):
    try:
        payload = json.load(stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command")
    if not isinstance(command, str) or "push" not in command:
        return 0
    payload_cwd = payload.get("cwd") or os.getcwd()
    try:
        messages = messages_for_command(command, payload_cwd)
    except shell_reader.ShellParserUnavailable as error:
        messages = [failure_line(f"the shell command reader failed: {error}")]
    if messages:
        add_context("\n\n".join(messages))
    return 0


if __name__ == "__main__":
    sys.exit(main())
