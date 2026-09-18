#!/usr/bin/env python3
"""PreToolUse guard: deny a git force push that would rewrite the head of an
open pull request, and name that pull request and the remedy in the refusal.

The rule (CLAUDE.md, ruled 2026-09-08): a head is frozen the moment it is
pushed, because that is when its review is commissioned. A fix — for a
changes-requested finding or one the author found themselves — is a fresh
commit on top of the frozen head, never an amend and never a rewrite.

The incident this guard is built from (2026-09-17): the cold-read-research
seat's pull request "Fast read: say when the cold-read-full-run is still
required" had been approved by its reviewer at its pushed head. main then
moved under it — a terminology sweep rewrote the same docstring — and the seat
rebased the branch and force-pushed it, so the approved head was no longer in
the branch's history and the reviewer's round was spent for nothing. Nothing
about that was adversarial: a conflict with main reads as tidying rather than
as acting on a head under review, which is exactly the kind of mistake worth
making mechanical. Merge-lane's ruling on the aftermath — once a head has
been rewritten, stop rather than reverse, because undoing costs a second
rewrite and buys nothing — is the refusal's second line, because that is the
part an agent gets wrong under pressure.

Why it recurs without a guard: about 30 pull requests a day merge into main, a
pull request sits in the merge queue for hours, and sweeps are the collision
engine — the sweep that hit this one rewrote comments and docstrings across 19
scripts at once, so it would have conflicted with any open pull request
touching them.

Decisions, in order:
- DENY, never warn. The damage lands on a reviewer already running against the
  frozen head, so a warning arrives after the round is spent.
- Force forms matched: `--force`, `-f` including inside a short cluster
  (`-fu`), `--force-with-lease` with or without its `=<expect>` value, and a
  `+` prefix on a refspec, which forces with no flag at all.
- The branch is resolved from the DESTINATION side of a colon refspec, never
  the source: `git push --force origin my-local-name:the-pr-branch` rewrites
  `the-pr-branch`, and asking about `my-local-name` would find no pull request
  and allow the very push this guard exists to stop.
- A bare push resolves the branch from the checkout the command will actually
  run in — `git -C <dir>`, else a literal `cd <dir>` earlier in the same
  command, else the session's own cwd from the hook payload. The incident's
  shape is a push from a worktree, so the hook's own directory is not a safe
  stand-in. A directory named by an unexpanded word is refused as
  unresolvable, asking for a literal path.
- `gh` is bound by an explicit timeout, and a timeout is treated exactly like
  an unreachable or unauthenticated `gh`: allow, and say what went unchecked.
  A guard that blocks when GitHub is slow stops ordinary work for nothing, and
  a `gh` call hung in front of every push would be worse than the mistake it
  prevents.
- Every probe shares one wall-clock budget (PROBE_BUDGET_SECONDS), kept under
  the hook's registered timeout, and running out of it is reported as
  unchecked, like any other probe that could not answer. The budget exists
  even though this guard allows what it cannot check: a hook that overruns its
  timeout fails open SILENTLY, while a guard that stops in time can still say
  what went unchecked. The keystroke guard runs the same budget but denies on
  exhaustion; the difference is the fleet's ruling that this guard must not
  block ordinary work when GitHub is slow.
- `CLAUDE_MERGE_LANE_ASKED_FOR_THIS_REWRITE=1` as an environment-assignment
  prefix skips the check: the escape hatch for the one sanctioned case, where
  the seat that owns the merge has asked for the rewrite. The same text inside
  a quoted string is data and does not count.

What it deliberately does NOT do, so a later reader does not mistake a choice
for an oversight:
- It guards the push, not the rebase or the amend. The push is the harmful
  act; a rewritten local branch that is never pushed harms no reviewer.
- It does not recurse into `sh -c`, `eval`, or a shell-fed heredoc body. No
  agent here force-pushes through those, and this fleet's failures are
  accidents between cooperative agents, not evasion.
- A push behind `timeout`, `command`, `nohup`, or a shell keyword such as
  `then`, `do` or `{` is not recognised: across 628 push commands on this Mac
  in the 14 days to 2026-09-18, no agent pushed that way (the only hits were a
  reviewer's probes). `env` is recognised, because an agent did push behind it.
- A refspec written after a `2>&1`-style redirection
  (`git push --force origin 2>&1 the-pr-branch`) is lost: the shared tokenizer
  ends the command at the `&`, so the push is judged as bare. No agent writes
  a push that way.
- It ignores which remote the push names: `gh` answers for the GitHub
  repository it resolves from the checkout. Every push here goes to this
  project's one repository; no agent pushes to a fork.
- It does not look inside an `ssh` remote command, which is one quoted data
  word to this guard: no agent here pushes from another machine's checkout.
  The keystroke guard follows ssh because seats are driven across machines;
  pushes are not.
- It does not guard a branch DELETE (`git push --delete`, a `:branch`
  refspec), which is a different act from rewriting a head under review.
- `--force-if-includes` is not treated as a force: on its own it changes
  nothing, and it is only meaningful alongside `--force-with-lease`, which is
  matched.
- `--all` and `--mirror` push every branch, and the guard checks only the
  current one. No agent here pushes that way.
- A push naming no branch is taken to push the current branch. That is what
  git's default `push.default=simple` does, and it is unset on both the Mac
  and ned-box (checked 2026-09-18). Under `simple` git refuses such a push from
  a detached HEAD by itself, so the guard says nothing there.
- It fires only in sessions that load this project's settings, so a headless
  run started with `--setting-sources user` is unguarded. Those do not push.

Detection is literal, not adversarial, and quoted prose is data: this guard's
own commit message and pull request body say `git push --force`, and the
shared tokenizer is what keeps them from being read as invocations.

The tokenizer, the heredoc split and `is_program` are imported from
scripts/synthetic-keystroke-guard-hook.py, the project's other PreToolUse
Bash guard, rather than copied: one shell reader, reviewed once. The test
asserts the import so a signature change there fails the suite instead of
failing open at runtime.
"""

import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

_keystroke_guard_path = Path(__file__).with_name("synthetic-keystroke-guard-hook.py")
_keystroke_guard_spec = importlib.util.spec_from_file_location(
    "synthetic_keystroke_guard_hook", _keystroke_guard_path)
keystroke_guard = importlib.util.module_from_spec(_keystroke_guard_spec)
_keystroke_guard_spec.loader.exec_module(keystroke_guard)

split_out_heredocs = keystroke_guard.split_out_heredocs
tokenize_simple_commands = keystroke_guard.tokenize_simple_commands
is_program = keystroke_guard.is_program

# All probes share PROBE_BUDGET_SECONDS, kept under the hook's registered
# timeout: a PreToolUse hook that overruns its timeout fails open silently,
# which is the one outcome this guard must not reach by accident. Each probe is
# also capped on its own, so one slow answer cannot spend the whole budget.
PROBE_BUDGET_SECONDS = 20.0
GH_TIMEOUT_SECONDS = 10.0
GIT_TIMEOUT_SECONDS = 5.0

ESCAPE_HATCH_VARIABLE = "CLAUDE_MERGE_LANE_ASKED_FOR_THIS_REWRITE"
ESCAPE_HATCH_ASSIGNMENT = ESCAPE_HATCH_VARIABLE + "=1"

# `--force-with-lease` matches with or without an `=<expect>` value; see the
# docstring for why `--force-if-includes` is absent.
FORCE_LONG_FLAGS = {"--force", "--force-with-lease"}

# git's own options, before the subcommand, that take a separate value.
GIT_GLOBAL_VALUE_FLAGS = {"-C", "-c", "--git-dir", "--work-tree",
                          "--namespace", "--config-env", "--exec-path"}

# `git push` options that take a separate value, so the word after them is
# data and never a refspec.
PUSH_VALUE_OPTIONS = {"--repo", "--receive-pack", "--exec", "--push-option",
                      "-o"}

# Short `git push` options taking a value: letters after one in a cluster are
# its value, so an `f` there is not the force flag.
SHORT_VALUE_LETTERS = "o"

ENVIRONMENT_ASSIGNMENT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

# `env` options that take a separate value, so the word after them is that
# value and not the program `env` runs.
ENV_COMMAND_VALUE_OPTIONS = {"-u", "--unset"}

# A redirection as the shared tokenizer leaves it: an optional file-descriptor
# number and the operator, with its target either in the same word
# (`>/tmp/x`, `2>/dev/null`) or as the next word (`> /tmp/x`, `2> err.log`).
# `2>&1` arrives as `2>` ending its command, because the `&` cuts it there;
# `>|` and `&>` are cut the same way before they reach this guard.
REDIRECTION_WORD_PATTERN = re.compile(r"^[0-9]*(?:>>|>|<<<|<>|<)")

# A word the shell would expand or glob, which this guard cannot resolve.
UNEXPANDED_PATTERN = re.compile(r"[$`*?]|\{\}")

# What an agent reads. Each line is one instruction and the condition it
# applies under — no citations, dates or rationale, which live in this
# module's docstring (user-ruled 2026-09-18: agents need clear, direct,
# specific instructions). Line 1 names the pull request, so the agent can tell
# the one sanctioned rewrite from the mistake. Line 2 is the case agents get
# wrong under pressure: undoing a rewrite with a second rewrite.
DENY_REASON_TEMPLATE = (
    "Refused: branch {branch} has an open pull request, \"{title}\" ({url}). "
    "A force push would replace the commits under review.\n"
    "If you are force-pushing to restore what an earlier force push replaced, "
    "stop: leave the branch as it is and message merge-lane (find its current "
    "name with ListAgents).\n"
    "Otherwise, put your change, including any fix for a conflict with main, "
    "in a new commit on top of the pushed branch, and push without --force.\n"
    "If you already rebased or amended it locally, keep that work on another "
    "branch (git branch {branch}-rewritten), go back to the pushed head (git "
    "switch -C {branch} origin/{branch}), and redo your change as a new "
    "commit.\n"
    "If merge-lane asked you for this force push, run it again with {escape} "
    "directly in front of the git push command."
)

UNRESOLVED_REASON_TEMPLATE = (
    "Refused: this guard cannot read {word}, so it cannot check whether the "
    "branch has an open pull request.\n"
    "Run the push again with the checkout path and the branch name written "
    "out, so this guard can check it: git -C <checkout path> push --force "
    "origin <branch>\n"
    "If merge-lane asked you for this force push, run it again with {escape} "
    "directly in front of the git push command."
)

UNCHECKED_NOTE_FIRST_LINE = (
    "Not checked: {detail}. This guard could not tell whether {subject} has an "
    "open pull request, so it did not stop this force push.\n")

# After a timeout or an unreadable answer, asking again can work.
UNCHECKED_NOTE_RETRY_TEMPLATE = UNCHECKED_NOTE_FIRST_LINE + (
    "Run: gh pr list --state open --head {head_argument}\n"
    "If that lists a pull request, or fails, message merge-lane (find its "
    "current name with ListAgents) which branch you force-pushed, and do not "
    "force push again to undo it.\n"
    "If it lists nothing, no pull request was affected."
)

# After a tool that could not run or failed outright, asking again fails the
# same way, so the note goes straight to the agent that can check.
UNCHECKED_NOTE_NO_RETRY_TEMPLATE = UNCHECKED_NOTE_FIRST_LINE + (
    "Message merge-lane (find its current name with ListAgents) which branch "
    "you force-pushed, so it can check for an open pull request, and do not "
    "force push again to undo it."
)


class UncheckedDetail:
    """Why a probe could not answer, and whether asking again could help."""

    def __init__(self, text, retryable):
        self.text = text
        self.retryable = retryable

# How the unchecked note names a branch it could not resolve, in prose and as
# a runnable `gh` argument.
CURRENT_BRANCH_SUBJECT = "the current branch"
CURRENT_BRANCH_HEAD_ARGUMENT = '"$(git branch --show-current)"'


class GuardRun:
    """One hook invocation: the injected subprocess runner, the shared probe
    budget's clock, and caches, so a command naming the same branch twice asks
    `gh` once."""

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
    """Given one simple command's words, return a dict describing a `git push`
    invocation — `sanctioned`, `push_words`, `directory_override` — or None
    when this command is not one.

    Only an actually-invoked `git push` matches. Quoted prose naming it is a
    single data word by the time it arrives here, which is what the shared
    tokenizer buys.

    An `env` in front, with its options and assignments, is read through: an
    assignment after it counts exactly like a leading one, the escape hatch
    included. Other prefixes are not; see the module docstring's limits."""
    index = 0
    sanctioned = False
    while index < len(words) and ENVIRONMENT_ASSIGNMENT_PATTERN.match(words[index]):
        if words[index] == ESCAPE_HATCH_ASSIGNMENT:
            sanctioned = True
        index += 1
    if index < len(words) and is_program(words[index], "env"):
        index += 1
        while index < len(words):
            word = words[index]
            if ENVIRONMENT_ASSIGNMENT_PATTERN.match(word):
                if word == ESCAPE_HATCH_ASSIGNMENT:
                    sanctioned = True
                index += 1
                continue
            if word in ENV_COMMAND_VALUE_OPTIONS:
                index += 2
                continue
            # `-i`, `-`, `--ignore-environment`, `--unset=NAME`: one word each.
            if word.startswith("-"):
                index += 1
                continue
            break
    if index >= len(words) or not is_program(words[index], "git"):
        return None
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
    return {"sanctioned": sanctioned,
            "push_words": words[index + 1:],
            "directory_override": directory_override}


def words_without_redirections(words):
    """The words git itself receives: every redirection dropped, with its
    target when that is the next word. The shell removes redirections wherever
    they stand, after a `--` included, so none of them is ever a refspec."""
    kept = []
    index = 0
    while index < len(words):
        match = REDIRECTION_WORD_PATTERN.match(words[index])
        if match is None:
            kept.append(words[index])
            index += 1
            continue
        target_is_next_word = match.end() == len(words[index])
        index += 2 if target_is_next_word else 1
    return kept


def parse_push_arguments(push_words):
    """Return (forced, refspecs) for the words after `git push`.

    A `+` prefix on a refspec forces with no flag at all, so refspecs are read
    for it too. A delete (`--delete`, `-d`) is reported as not forced even
    with `--force` beside it: it is a different act from rewriting a head, and
    this guard's refusal, which teaches a commit on top, would be wrong for it.

    Redirections are dropped first. Read as a refspec, the `2>` a trailing
    `2>&1` leaves would skip the current-branch lookup and ask `gh` about a
    branch named `2>`, so a bare force push would pass unchecked."""
    push_words = words_without_redirections(push_words)
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
                    # The rest of the cluster is this option's value; if the
                    # cluster ends here, the value is the next word.
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
    # The first positional is the remote; every later one is a refspec.
    refspecs = positionals[1:]
    if deletes:
        return False, []
    if any(spec.startswith("+") for spec in refspecs):
        forced = True
    return forced, refspecs


def destination_branch(refspec):
    """The branch a refspec writes ON THE REMOTE — the destination side of a
    colon, never the source. None when the refspec rewrites no branch head: a
    delete, a tag, or another ref namespace."""
    spec = refspec[1:] if refspec.startswith("+") else refspec
    if ":" in spec:
        source, destination = spec.split(":", 1)
        if not source:
            return None  # `:branch` deletes it; see the docstring's limits
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
    """The directory a `cd` or `git -C` lands in, relative to the directory in
    force before it."""
    expanded = os.path.expanduser(target)
    if os.path.isabs(expanded):
        return os.path.normpath(expanded)
    return os.path.normpath(os.path.join(base, expanded))


def current_branch(directory, guard):
    """Return (branch, unchecked_detail) for the checkout at `directory`.
    (None, None) is a detached HEAD: no branch, and nothing to report."""
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
            # A detached HEAD has no current branch, and git refuses a push
            # that would need one: see the docstring's note on push.default.
            answer = (None, None)
        else:
            answer = (name, None)
    guard.branch_cache[directory] = answer
    return answer


def open_pull_request_for_branch(branch, directory, guard):
    """Return (pull_request, unchecked_detail). The pull request is a dict
    carrying title and url, or None when the branch has no open one.

    An unreachable, unauthenticated, slow or unparseable `gh` all return an
    unchecked detail rather than a decision: this guard allows what it cannot
    check, and says so."""
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
    """Decide one `git push` invocation. Returns (decision, reason) where the
    decision is "deny", "unchecked" or None."""
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
    """Walk the command's simple commands in order, carrying the directory a
    literal `cd` puts them in, and decide the first force push found.

    Heredoc bodies are dropped rather than analyzed: a body is data here, and
    this guard does not chase a push through a shell it feeds (see the module
    docstring's stated limits)."""
    shell_view, _heredoc_bodies = split_out_heredocs(command)
    effective_directory = payload_cwd
    directory_is_unresolved = None
    for words in tokenize_simple_commands(shell_view):
        if not words:
            continue
        # A `cd` may carry environment assignments in front, like any command.
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
    """Say what went unchecked WITHOUT deciding the call.

    Deliberately not `permissionDecision: "allow"`: an allow from a hook
    auto-approves the call past the permission rules the user configured, so
    a guard that merely failed to reach `gh` would end up widening
    permissions on a force push. With no decision the call continues through
    the normal permission flow, unchanged.

    The channel is `additionalContext`, not stderr. On exit 0 the harness
    sends a hook's stderr only to its debug log, so a note there reaches no
    one. That an `additionalContext` with no decision beside it still reaches
    the agent is NOT stated in the hooks documentation, so it was measured
    (2026-09-18): a headless run whose only PreToolUse hook returned this
    shape quoted back a random canary token its prompt never contained, and
    a control run returning the same context with an allow did the same."""
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
    decision, reason = analyze_command_text(command, payload_cwd, guard)
    if decision == "deny":
        deny(reason)
    elif decision == "unchecked":
        note_unchecked(reason)
    return 0


if __name__ == "__main__":
    sys.exit(main())
