#!/usr/bin/env python3
"""Claude Code Stop hook: at each turn end, put the ending agent-seat's committed work on GitHub.

For each worktree of this clone whose owner file, scripts/worktree-owner-file-read-and-write.py's,
names the agent-seat GIT_AUTHOR_NAME names, and whose checked-out branch is not main and has a
commit no origin branch holds (`git rev-list <branch> --not --remotes=origin` prints something):

  - asks GitHub for the branch's open pull request, before any push;
  - skips the branch when that pull request is ready for review, since its head is a frozen-head
    that only a fix-round pushes;
  - otherwise runs `git push origin <branch>` from the worktree, so the pre-push hook checks it
    as it checks any push; it never forces, so a draft rewritten since its last push is refused
    and reported;
  - when the branch has no open pull request, opens a draft one whose description is a
    placeholder with no defect line, so the mark-ready command and scripts/merge-gate.sh refuse
    it until its owner writes the real description.

A subagent's worktree whose owner file names an agent-session of this agent-seat counts too.

Silent, doing nothing, at a Stop that ends the agent's answer to a Stop hook, as
nc-systems/general-tools/claude-code-stop-hooks-stay-silent-while-agent-answers-a-stop-hook-rule-common.py
says every Stop hook is; the next turn end pushes instead. Silent too when GIT_AUTHOR_NAME is unset, since no agent-seat is ending, and when no
user attends the agent-session, as
nc-systems/general-tools/agent-session-unattended-by-user-check-common.py says: a headless child
inherits the agent-seat's name, and its own turn end would push the same branches the agent-seat's
turn end pushes, and would make the report its caller's answer.

OUTPUT. Nothing pushed or nothing failed: nothing printed, exit 0. Something failed, such as a
question to GitHub, a push the pre-push hook refused or a draft that could not be opened: one line
per failure, naming the branch and quoting the command's own error, sent to the agent as
{"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": ...}}, exit 0. A failure the
agent leaves unfixed is reported again at its next turn end. A failure that stops the hook as a whole, such as a payload that is not a JSON object or
`git worktree list` failing, is one line on stderr, exit 1.

A draft that fails to open after its push succeeded is not tried again at the next turn end,
because the branch then has no commit origin lacks; its failure line gives the command to run.
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_NAME = "agent-seat-owned-nc-topic-branches-push-and-draft-pull-request-open-stop-hook"
MAIN_BRANCH = "main"
DRAFT_PULL_REQUEST_DESCRIPTION = (
    "Draft opened by the turn-end hook, "
    "nc-systems/general-tools/agent-seat-owned-nc-topic-branches-push-and-draft-pull-request-open-stop-hook.py, "
    "so that this branch's committed work is on GitHub and not only in a local worktree.\n\n"
    "This description is a placeholder. Before marking the pull request ready for review, its "
    "owner replaces it with what the pull request changes, ending with the defect line CLAUDE.md "
    "asks for.\n")


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


worktree_owner_file = load_module(
    "worktree_owner_file_read_and_write", REPO_ROOT / "scripts" / "worktree-owner-file-read-and-write.py")
stop_hooks_stay_silent_rule = load_module(
    "claude_code_stop_hooks_stay_silent_while_agent_answers_a_stop_hook_rule_common",
    REPO_ROOT / "nc-systems" / "general-tools"
    / "claude-code-stop-hooks-stay-silent-while-agent-answers-a-stop-hook-rule-common.py")
attendance = load_module(
    "agent_session_unattended_by_user_check_common",
    REPO_ROOT / "nc-systems" / "general-tools" / "agent-session-unattended-by-user-check-common.py")


class HookFailure(Exception):
    pass


def run_command(arguments, directory):
    return subprocess.run(arguments, cwd=directory, capture_output=True, text=True)


def single_line(text):
    return " ".join(text.split())


def command_error(result):
    return single_line(result.stderr or result.stdout) or f"exit status {result.returncode}, no output"


def worktrees_with_branches(clone_directory):
    """(worktree path, branch) for each linked worktree of the clone with a branch checked out."""
    result = run_command(["git", "worktree", "list", "--porcelain"], clone_directory)
    if result.returncode != 0:
        raise HookFailure(f"`git worktree list` failed in {clone_directory}, so no branch was pushed: "
                          f"{command_error(result)}")
    found = []
    # The first entry is the reference-checkout, which has no owner file.
    for entry in result.stdout.strip().split("\n\n")[1:]:
        fields = dict(line.partition(" ")[::2] for line in entry.splitlines())
        branch_reference = fields.get("branch", "")
        if "prunable" in fields or not branch_reference.startswith("refs/heads/"):
            continue
        found.append((Path(fields["worktree"]), branch_reference[len("refs/heads/"):]))
    return found


def agent_seat_owned_nc_topic_branches_with_commits_origin_lacks(clone_directory, agent_seat, failures):
    """(worktree, branch) pairs to push; an owner file that cannot be read adds a line to failures."""
    owned = []
    for worktree, branch in worktrees_with_branches(clone_directory):
        if branch == MAIN_BRANCH:
            continue
        try:
            owner = worktree_owner_file.worktree_owner_file_read(worktree)
        except worktree_owner_file.WorktreeOwnerFileError as error:
            failures.append(f"branch {branch}: the owner file of worktree {worktree} could not be read, "
                            f"so the branch was not pushed even if it is yours: {single_line(str(error))}")
            continue
        if owner is None or owner["agent_seat"] != agent_seat:
            continue
        unpushed = run_command(["git", "rev-list", "--max-count=1", f"refs/heads/{branch}",
                                "--not", "--remotes=origin"], worktree)
        if unpushed.returncode != 0:
            failures.append(f"branch {branch}: `git rev-list` failed in {worktree}, so the branch was "
                            f"not pushed: {command_error(unpushed)}")
        elif unpushed.stdout.strip():
            owned.append((worktree, branch))
    return owned


def branch_push_and_draft_open(worktree, branch, failures):
    asked = run_command(["gh", "pr", "list", "--head", branch, "--state", "open",
                         "--json", "number,isDraft"], worktree)
    try:
        open_pull_requests = json.loads(asked.stdout) if asked.returncode == 0 else None
    except json.JSONDecodeError:
        open_pull_requests = None
    if not isinstance(open_pull_requests, list):
        failures.append(f"branch {branch}: GitHub could not be asked whether its open pull request is "
                        f"ready for review, so it was not pushed: {command_error(asked)}")
        return
    if any(not pull_request.get("isDraft") for pull_request in open_pull_requests):
        return
    pushed = run_command(["git", "push", "origin", f"refs/heads/{branch}:refs/heads/{branch}"], worktree)
    if pushed.returncode != 0:
        failures.append(f"branch {branch}: `git push origin {branch}` from {worktree} failed, so its "
                        f"new commits are not on GitHub: {command_error(pushed)}")
        return
    if open_pull_requests:
        return
    title = run_command(["git", "log", "-1", "--format=%s", f"refs/heads/{branch}"], worktree).stdout.strip()
    title = title or branch
    create = ["gh", "pr", "create", "--draft", "--base", MAIN_BRANCH, "--head", branch,
              "--title", title, "--body", DRAFT_PULL_REQUEST_DESCRIPTION]
    created = run_command(create, worktree)
    if created.returncode != 0:
        failures.append(
            f"branch {branch}: pushed, but its draft pull request could not be opened, and the next "
            f"turn end will not try again because the branch is then pushed: {command_error(created)}. "
            f"Open it yourself from {worktree} with: "
            f"gh pr create --draft --base {MAIN_BRANCH} --head {branch} --title <title> --body <description>")


def run(stdin_text, environment, default_directory):
    """(stdout text, stderr text, exit status)."""
    try:
        payload = json.loads(stdin_text)
    except json.JSONDecodeError as error:
        raise HookFailure(f"the Stop payload is not JSON, so no branch was pushed: {error}") from None
    if stop_hooks_stay_silent_rule.stop_hook_stays_silent_while_agent_answers_a_stop_hook(payload):
        return "", "", 0
    if not isinstance(payload, dict):
        raise HookFailure("the Stop payload is not a JSON object, so no branch was pushed")
    agent_seat = environment.get("GIT_AUTHOR_NAME", "")
    if not agent_seat or attendance.agent_session_unattended_by_user(environment):
        return "", "", 0
    clone_directory = payload.get("cwd") or default_directory
    failures = []
    for worktree, branch in agent_seat_owned_nc_topic_branches_with_commits_origin_lacks(
            clone_directory, agent_seat, failures):
        branch_push_and_draft_open(worktree, branch, failures)
    if not failures:
        return "", "", 0
    lines = [f"{HOOK_NAME}: at this turn end, pushing your agent-seat's branches to GitHub failed "
             f"for these branches:"] + [f"- {failure}" for failure in failures]
    lines.append("For each branch, fix what its line names, then push it yourself; when a line quotes "
                 "the pre-push hook's refusal, follow that refusal's own steps.")
    output = {"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": "\n".join(lines)}}
    return json.dumps(output) + "\n", "", 0


def main():
    try:
        stdout_text, stderr_text, status = run(
            sys.stdin.read(), os.environ, os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    except HookFailure as error:
        print(f"{HOOK_NAME}: {error}", file=sys.stderr)
        return 1
    sys.stdout.write(stdout_text)
    sys.stderr.write(stderr_text)
    return status


if __name__ == "__main__":
    sys.exit(main())
