#!/usr/bin/env python3
"""Deny force pushes that would replace a pull request head under review.

Reviewers work against the pushed head; rewriting it invalidates their work.
Detection is literal: a push behind the wrappers the shared shell module
knows, such as env, sudo and timeout, is read; ssh commands, heredoc bodies,
and pushes of multiple branches are outside this guard's scope.
The checkout determines the GitHub repository, regardless of the named remote;
a push with no refspec is assumed to use push.default=simple.

Commands are read with the shared shell module on tree-sitter-bash, which
leaves redirections out of a command's words. Quoted prose is data, not an
invocation.
"""

import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

_shell_reader_spec = importlib.util.spec_from_file_location(
    "shell_command_tree_sitter_bash_reader_common",
    Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
    / "shell-command-tree-sitter-bash-reader-common.py")
shell_reader = importlib.util.module_from_spec(_shell_reader_spec)
_shell_reader_spec.loader.exec_module(shell_reader)
is_program = shell_reader.is_program

# Stay below the hook timeout: overrunning it fails open silently.
# Cap individual probes so one slow answer cannot consume the whole budget.
PROBE_BUDGET_SECONDS = 20.0
GH_TIMEOUT_SECONDS = 10.0
GIT_TIMEOUT_SECONDS = 5.0

ESCAPE_HATCH_VARIABLE = "CLAUDE_MERGE_LANE_ASKED_FOR_THIS_REWRITE"
ESCAPE_HATCH_ASSIGNMENT = ESCAPE_HATCH_VARIABLE + "=1"

# --force-if-includes alone does not force a push.
FORCE_LONG_FLAGS = {"--force", "--force-with-lease"}

GIT_GLOBAL_VALUE_FLAGS = {"-C", "-c", "--git-dir", "--work-tree",
                          "--namespace", "--config-env", "--exec-path"}

# Option values must not be mistaken for refspecs.
PUSH_VALUE_OPTIONS = {"--repo", "--receive-pack", "--exec", "--push-option",
                      "-o"}

# Letters after a value-taking short option are its value, even f.
SHORT_VALUE_LETTERS = "o"

ENVIRONMENT_ASSIGNMENT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

# A wrapper option that runs the program in another directory.
WRAPPER_DIRECTORY_OPTIONS = {("env", "-C"), ("env", "--chdir"), ("sudo", "-D"), ("sudo", "--chdir")}

UNEXPANDED_PATTERN = re.compile(r"[$`*?]|\{\}")

DENY_REASON_TEMPLATE = (
    "Refused: branch {branch} has an open pull request, \"{title}\" ({url}). "
    "A force push would replace the commits under review.\n"
    "If you are force-pushing to restore what an earlier force push replaced, "
    "stop: leave the branch as it is and message merge-lane-2 with SendMessage "
    "(ListAgents lists its address).\n"
    "Otherwise, put your change in a new commit on top of the pushed branch, "
    "and push without --force.\n"
    "If the branch conflicts with main, clear the conflict with the hand-merge "
    "that scripts/branch-conflict-check.py describes, and push without --force.\n"
    "If you already rebased or amended it locally, keep that work on another "
    "branch (git branch {branch}-rewritten), go back to the pushed head (git "
    "switch -C {branch} origin/{branch}), and redo your change as a new "
    "commit.\n"
    "If merge-lane-2 asked you for this force push, run it again with {escape} "
    "directly in front of the git push command."
)

UNRESOLVED_REASON_TEMPLATE = (
    "Refused: this guard cannot read {word}, so it cannot check whether the "
    "branch has an open pull request.\n"
    "Run the push again with the checkout path and the branch name written "
    "out, so this guard can check it: git -C <checkout path> push --force "
    "origin <branch>\n"
    "If merge-lane-2 asked you for this force push, run it again with {escape} "
    "directly in front of the git push command."
)

UNCHECKED_NOTE_FIRST_LINE = (
    "Not checked: {detail}. This guard could not tell whether {subject} has an "
    "open pull request, so it did not stop this force push.\n")

# A timeout or unreadable answer may succeed on retry.
UNCHECKED_NOTE_RETRY_TEMPLATE = UNCHECKED_NOTE_FIRST_LINE + (
    "Run: gh pr list --state open --head {head_argument}\n"
    "If that lists a pull request, or fails, message merge-lane-2 with SendMessage "
    "(ListAgents lists its address) which branch you force-pushed, and do not "
    "force push again to undo it.\n"
    "If it lists nothing, no pull request was affected."
)

# A tool that cannot run needs intervention rather than another identical probe.
UNCHECKED_NOTE_NO_RETRY_TEMPLATE = UNCHECKED_NOTE_FIRST_LINE + (
    "Message merge-lane-2 with SendMessage (ListAgents lists its address) "
    "which branch "
    "you force-pushed, so it can check for an open pull request, and do not "
    "force push again to undo it."
)


class UncheckedDetail:
    """Why a probe could not answer, and whether asking again could help."""

    def __init__(self, text, retryable):
        self.text = text
        self.retryable = retryable

CURRENT_BRANCH_SUBJECT = "the current branch"
CURRENT_BRANCH_HEAD_ARGUMENT = '"$(git branch --show-current)"'


class GuardRun:
    """Probe budget and caches shared by one hook invocation."""

    def __init__(self, runner, clock):
        self.runner = runner
        self.clock = clock
        self.deadline = clock() + PROBE_BUDGET_SECONDS
        self.pull_request_cache = {}
        self.branch_cache = {}

    def probe_timeout(self, per_probe_seconds):
        """The timeout for the next probe, or None when the budget is spent."""
        remaining = self.deadline - self.clock()
        if remaining <= 0:
            return None
        return min(per_probe_seconds, remaining)


BUDGET_SPENT_DETAIL = (
    "the guard's {budget:.0f}-second limit ran out before it could check "
    "{what}")


def find_git_push_invocation(words):
    """Return sanctioned status, push words and directory override, or None for a non-push."""
    index, _ = shell_reader.simple_command_program_index_skipping_wrappers(words)
    if index is None or not is_program(words[index], "git"):
        return None
    sanctioned = ESCAPE_HATCH_ASSIGNMENT in words[:index]
    wrapper_directory = directory_a_wrapper_sets(words)
    index += 1
    directory_override = None
    while index < len(words):
        word = words[index]
        if word == "-C" and index + 1 < len(words):
            directory_override = words[index + 1]
            index += 2
            continue
        if word.startswith("-C") and len(word) > 2:
            directory_override = word[2:]
            index += 1
            continue
        if word in GIT_GLOBAL_VALUE_FLAGS:
            index += 2
            continue
        if word.startswith("-"):
            index += 1
            continue
        break
    if index >= len(words) or words[index] != "push":
        return None
    if wrapper_directory is not None:
        directory_override = (wrapper_directory if directory_override is None
                              else directory_joined(wrapper_directory, directory_override))
    return {"sanctioned": sanctioned,
            "push_words": words[index + 1:],
            "directory_override": directory_override}


def directory_a_wrapper_sets(words):
    """Return the directory the wrappers in front of the program run it in, or None.

    A wrapper given more than one directory option uses its last, as env does; a
    wrapper inside another runs in a directory taken relative to the outer one's.
    """
    directory = None
    wrappers = shell_reader.simple_command_wrapper_options_and_values_parsed_from_words(words)
    for wrapper, options in wrappers:
        own = [value for option, value in options if (wrapper, option) in WRAPPER_DIRECTORY_OPTIONS]
        if own:
            directory = directory_joined(directory, own[-1])
    return directory


def directory_joined(base, target):
    """Return target with a ~ bash expands expanded, taken relative to base when base is given."""
    target = shell_reader.shell_word_tilde_prefix_expand_as_bash_would(target)
    return target if base is None else os.path.join(base, target)


def parse_push_arguments(push_words):
    """Return (forced, refspecs) for the words after git push."""
    # Deletion is not a head rewrite; the guard's commit-on-top remedy would be wrong.
    forced = False
    deletes = False
    positionals = []
    index = 0
    while index < len(push_words):
        word = push_words[index]
        if word == "--":
            positionals.extend(push_words[index + 1:])
            break
        if word.startswith("--"):
            name = word.split("=", 1)[0]
            if name in FORCE_LONG_FLAGS:
                forced = True
            if name == "--delete":
                deletes = True
            if name in PUSH_VALUE_OPTIONS and "=" not in word:
                index += 2
                continue
            index += 1
            continue
        if word.startswith("-") and len(word) > 1:
            consumes_next_word = False
            for position, letter in enumerate(word[1:], start=1):
                if letter in SHORT_VALUE_LETTERS:
                    consumes_next_word = position == len(word) - 1
                    break
                if letter == "f":
                    forced = True
                if letter == "d":
                    deletes = True
            index += 2 if consumes_next_word else 1
            continue
        positionals.append(word)
        index += 1
    refspecs = positionals[1:]
    if deletes:
        return False, []
    if any(spec.startswith("+") for spec in refspecs):
        forced = True
    return forced, refspecs


def destination_branch(refspec):
    """Return the remote destination branch, or None for deletion and non-head refs."""
    spec = refspec[1:] if refspec.startswith("+") else refspec
    if ":" in spec:
        source, destination = spec.split(":", 1)
        if not source:
            return None  # An empty source deletes the remote branch.
    else:
        destination = spec
    if not destination:
        return None
    if destination.startswith("refs/heads/"):
        return destination[len("refs/heads/"):]
    if destination.startswith("refs/"):
        return None
    return destination


def resolve_directory(base, target):
    expanded = shell_reader.shell_word_tilde_prefix_expand_as_bash_would(target)
    if os.path.isabs(expanded):
        return os.path.normpath(expanded)
    return os.path.normpath(os.path.join(base, expanded))


def current_branch(directory, guard):
    """Return (branch, unchecked detail); (None, None) means detached HEAD."""
    if directory in guard.branch_cache:
        return guard.branch_cache[directory]
    timeout = guard.probe_timeout(GIT_TIMEOUT_SECONDS)
    if timeout is None:
        return None, UncheckedDetail(BUDGET_SPENT_DETAIL.format(
            budget=PROBE_BUDGET_SECONDS, what=CURRENT_BRANCH_SUBJECT), True)
    argv = ["git", "-C", str(directory), "rev-parse", "--abbrev-ref", "HEAD"]
    try:
        completed = guard.runner(
            argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        answer = (None, UncheckedDetail(
            "`git rev-parse` did not answer within "
            f"{GIT_TIMEOUT_SECONDS:.0f} seconds", True))
    except (OSError, ValueError) as error:
        answer = (None, UncheckedDetail(f"`git` could not be run ({error})", False))
    else:
        name = (completed.stdout or "").strip()
        if completed.returncode != 0:
            answer = (None, UncheckedDetail(
                f"`git rev-parse` failed in {directory}", False))
        elif not name or name == "HEAD":
            # With push.default=simple, git itself refuses bare pushes from detached HEAD.
            answer = (None, None)
        else:
            answer = (name, None)
    guard.branch_cache[directory] = answer
    return answer


def open_pull_request_for_branch(branch, directory, guard):
    """Return (pull request or None, unchecked detail or None)."""
    key = (branch, str(directory))
    if key in guard.pull_request_cache:
        return guard.pull_request_cache[key]
    timeout = guard.probe_timeout(GH_TIMEOUT_SECONDS)
    if timeout is None:
        return None, UncheckedDetail(BUDGET_SPENT_DETAIL.format(
            budget=PROBE_BUDGET_SECONDS, what=branch), True)
    argv = ["gh", "pr", "list", "--state", "open", "--head", branch,
            "--json", "title,url"]
    try:
        completed = guard.runner(
            argv, cwd=str(directory), stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, timeout=timeout,
            check=False)
    except subprocess.TimeoutExpired:
        answer = (None, UncheckedDetail(
            f"`gh` did not answer within {GH_TIMEOUT_SECONDS:.0f} seconds", True))
    except (OSError, ValueError) as error:
        answer = (None, UncheckedDetail(f"`gh` could not be run ({error})", False))
    else:
        if completed.returncode != 0:
            first_line = ((completed.stderr or "").strip().splitlines() or [""])[0]
            text = f"`gh` failed: {first_line}" if first_line else "`gh` failed"
            answer = (None, UncheckedDetail(text, False))
        else:
            try:
                entries = json.loads(completed.stdout or "[]")
            except (json.JSONDecodeError, ValueError):
                answer = (None, UncheckedDetail(
                    "`gh` returned output this guard could not parse", True))
            else:
                found = next((entry for entry in entries if entry.get("url")), None)
                answer = (found, None)
    guard.pull_request_cache[key] = answer
    return answer


def analyze_push(invocation, effective_directory, directory_is_unresolved, guard):
    """Return (decision, reason), with decision deny, unchecked or None."""
    forced, refspecs = parse_push_arguments(invocation["push_words"])
    if not forced:
        return None, None

    directory = effective_directory
    override = invocation["directory_override"]
    if override is not None:
        if UNEXPANDED_PATTERN.search(override):
            return "deny", UNRESOLVED_REASON_TEMPLATE.format(
                word=override, escape=ESCAPE_HATCH_ASSIGNMENT)
        directory = resolve_directory(effective_directory, override)
    elif directory_is_unresolved:
        return "deny", UNRESOLVED_REASON_TEMPLATE.format(
            word=directory_is_unresolved, escape=ESCAPE_HATCH_ASSIGNMENT)

    branches, unchecked = [], []
    if not refspecs:
        branch, detail = current_branch(directory, guard)
        if detail:
            unchecked.append((CURRENT_BRANCH_SUBJECT, detail))
        elif branch:
            branches.append(branch)
    for spec in refspecs:
        destination = destination_branch(spec)
        if destination is None:
            continue
        if UNEXPANDED_PATTERN.search(destination):
            return "deny", UNRESOLVED_REASON_TEMPLATE.format(
                word=destination, escape=ESCAPE_HATCH_ASSIGNMENT)
        if destination == "HEAD":
            branch, detail = current_branch(directory, guard)
            if detail:
                unchecked.append((CURRENT_BRANCH_SUBJECT, detail))
            if not branch:
                continue
            destination = branch
        branches.append(destination)

    for branch in branches:
        pull_request, detail = open_pull_request_for_branch(branch, directory, guard)
        if pull_request:
            return "deny", DENY_REASON_TEMPLATE.format(
                branch=branch, title=pull_request.get("title") or branch,
                url=pull_request.get("url"), escape=ESCAPE_HATCH_ASSIGNMENT)
        if detail:
            unchecked.append((branch, detail))

    if unchecked:
        branch, detail = unchecked[0]
        if branch == CURRENT_BRANCH_SUBJECT:
            subject, head_argument = branch, CURRENT_BRANCH_HEAD_ARGUMENT
        else:
            subject, head_argument = f"branch {branch}", branch
        template = (UNCHECKED_NOTE_RETRY_TEMPLATE if detail.retryable
                    else UNCHECKED_NOTE_NO_RETRY_TEMPLATE)
        return "unchecked", template.format(
            detail=detail.text, subject=subject, head_argument=head_argument)
    return None, None


def analyze_command_text(command, payload_cwd, guard):
    """Return the first force-push decision while tracking literal directory changes."""
    # A child shell, such as a command substitution or ( ... ), inherits its parent's
    # directory; its cd must not affect the parent.
    directories = {(): (payload_cwd, None)}  # Per child shell: (directory, unresolved cd target).
    for words in shell_reader.simple_commands(command):
        substitution = words.child_shell
        enclosing = substitution
        while enclosing not in directories:
            enclosing = enclosing[:-1]
        effective_directory, directory_is_unresolved = directories[enclosing]
        # Leading environment assignments may precede cd.
        program_index = 0
        while (program_index < len(words)
               and ENVIRONMENT_ASSIGNMENT_PATTERN.match(words[program_index])):
            program_index += 1
        if (program_index + 1 < len(words)
                and is_program(words[program_index], "cd")):
            target = words[program_index + 1]
            if UNEXPANDED_PATTERN.search(target):
                directory_is_unresolved = target
            else:
                effective_directory = resolve_directory(effective_directory, target)
                directory_is_unresolved = None
            directories[substitution] = (effective_directory, directory_is_unresolved)
            continue
        invocation = find_git_push_invocation(words)
        if invocation is None or invocation["sanctioned"]:
            continue
        decision, reason = analyze_push(
            invocation, effective_directory, directory_is_unresolved, guard)
        if decision:
            return decision, reason
    return None, None


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))


def note_unchecked(reason):
    """Report an unchecked push without granting permission."""
    # An allow decision bypasses permission rules; omit the decision.
    # Exit-0 stderr goes only to debug logs, so use additionalContext.
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "additionalContext": reason,
    }}))


def main(stdin=sys.stdin, runner=subprocess.run, clock=time.monotonic):
    try:
        payload = json.load(stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not command:
        return 0
    payload_cwd = payload.get("cwd") or os.getcwd()
    guard = GuardRun(runner, clock)
    try:
        decision, reason = analyze_command_text(command, payload_cwd, guard)
    except shell_reader.ShellParserUnavailable as error:
        print(shell_reader.parser_unavailable_hook_output(
            "The force-push guard", error))
        return 0
    if decision == "deny":
        deny(reason)
    elif decision == "unchecked":
        note_unchecked(reason)
    return 0


if __name__ == "__main__":
    sys.exit(main())
