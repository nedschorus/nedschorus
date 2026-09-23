#!/usr/bin/env python3
"""The work of the pre-push hook: refuse to push a branch that conflicts with main.

scripts/git-client-side-hooks/pre-push runs this file. Git hands the hook
the remote's name and URL as arguments, and one line per ref on stdin. This
file runs scripts/branch-conflict-check.py once for each branch being pushed,
and asks the hook to refuse the push only when the check reports a conflict
it can trust. Every other outcome lets the push through.

WHY IT EXISTS. User-ruled 2026-09-23 in the merge-lane walk
"merge-lane-mac-helper-open-items-and-questions-2026-09-23", item 2.1. The
first proposal was a CLAUDE.md sentence telling agents to run the conflict
check before pushing. The user's reply: "2.1 sounds reasonable, but this looks
like it should be a script, not a prompt". On the revised proposal, this hook,
at 22:52Z: "y but be careful. Messing up how git works or how we push is a big
problem".

WHAT IT DEFENDS AGAINST, measured 2026-09-23 with `git merge-tree
--write-tree`, comparing each pushed head with origin/main at the moment of
its push (push times from GitHub's branch activity API). PR 663, "Every
claude update on a machine waits for the one before it": its branch was
first pushed at 2026-09-23T01:12:09Z as commit 152c16f070ff. That commit
already conflicted with main as main stood then (c0ea5d74 and dbec7f50, both
merge-tree exit 1, in scripts/launch-claude-mac-test.py and
scripts/launch-claude-ubuntu-test.py). The conflict was found only after the
pull request was open, and it cost a hand merge and a second approval. This
hook refuses that push.
Two cases measured the same way are NOT caught here, and it does not claim
them:
  - PR 353, "Refresh the machine-paths map against both machines, then move
    it to the wiki". git merged it cleanly by following a rename, while
    GitHub reported CONFLICTING. This hook asks git alone.
  - PR 408, "cold-read scripts: sweep comments and docstrings to the
    glossary's project terms". Both of its pushes merged cleanly at push
    time. The conflict came from main moving afterwards, and no pre-push
    check can see that.

FAIL OPEN, BECAUSE OF THE SECOND QUOTE. A hook that blocks a push it should
not is worse than one that misses a conflict. A missed conflict is still
caught at review, as PR 663's was. A wrongly blocked push stops a seat's
work. So a push is refused only when both of these hold: the check
exits 1, AND its stdout has a line that begins `VERDICT: CONFLICT`. Exit 1
alone is not enough, because Python exits 1 on any uncaught exception, so a
crashing check would otherwise refuse every push. Everything else lets the
push go:
  - exit 0 (clean): silently;
  - exit 2 (the check's "no trustworthy answer"): with the check's own output;
  - a missing check, a check that cannot start, one that crashes, one that
    exits any other status or is killed, or one that runs past the time
    budget: with one line saying the check gave no verdict.
The shell hook in front of this file adds the rest. python3 missing from
PATH, this file missing, or this file failing in any way all let the push go.
This file asks for a refusal with its own status, EXIT_REFUSE_PUSH (10), and
never with 1, for the same reason.

WHAT IS CHECKED. Only refs git is pushing to a branch (refs/heads/...) on the
remote named `origin`, excluding refs/heads/main. Skipped:
  - deletes, whose local object id is all zeros. There is nothing to merge.
  - tags and every other ref that is not a branch. No pull request comes from
    them.
  - main. Main cannot conflict with itself, and whoever pushes main directly
    is not opening a pull request.
  - every remote not named `origin`. The check fetches origin and compares
    with origin/main. That comparison says whether the branch will merge into
    origin's main. It says nothing about a push to a backup remote, a test
    remote or a scratch mirror, so refusing those would block pushes the
    check knows nothing about. A push by URL rather than by name
    (`git push https://github.com/... branch`) reaches this file with the URL
    as the remote's name, so it is not checked either. That is a known gap,
    accepted because nothing in this project pushes by URL.

HOW THE CHECK RUNS. As `branch-conflict-check.py --head <the commit being
pushed>`, found beside this file, so each machine runs the copy in its
reference checkout, as prepare-commit-msg does. It runs WITHOUT
--pull-request. GitHub's mergeability answers only about a pull request's
pushed head, and before a push that head is still the old commit. The check
already discards a GitHub verdict about a different commit (its docstring,
"ONLY WHEN THE TWO ORACLES ARE ANSWERING ABOUT THE SAME COMMIT"), so asking
GitHub here would only add up to a minute of polling for an answer it throws
away. The check's own fetch is kept: it is part of the answer (its docstring,
"WHY IT FETCHES BEFORE IT ANSWERS"). So a merge that git calls clean and
GitHub calls conflicting, PR 353's rename, is not caught here. The reviewer
catches it after the push, as before.

WHICH REPOSITORY THE CHECK SEES. The check runs with the environment and
working directory git gave the hook, unchanged. Measured on this Mac, git
2.55.0, 2026-09-23, pushing from a linked worktree:
  - git runs the hook with its working directory at the worktree's top;
  - it exports GIT_DIR as that worktree's own git directory
    (<clone>/.git/worktrees/<name>), plus GIT_EXEC_PATH, GIT_PREFIX and any
    GIT_CONFIG_PARAMETERS from `git -c`.
Those variables name the repository being pushed, and so does everything the
check does. So keeping them is correct, and stripping them would be wrong: the
check would rediscover a repository from the working directory, and if the
pusher had set GIT_DIR itself, that could be a different repository from the
one git is pushing. The check writes nothing but remote-tracking refs and
FETCH_HEAD, through its fetch, and the merged tree's objects, through
`merge-tree --write-tree`, which nothing refers to and gc later removes. It
never touches a branch, the index or the work tree.

THE TIME BUDGET. DEFAULT_TIME_BUDGET_SECONDS (60) covers every check in one
push together. Measured 2026-09-23 on this Mac against the nedschorus
repository: a check whose fetch brought nothing took 0.54 seconds, wall
clock. The budget exists for a fetch that hangs on a dropped network, which
git itself never times out. Sixty seconds is long enough for a slow fetch, and
leaves the push itself most of the two minutes that Claude Code's Bash tool
allows a command by default.

When the budget runs out, the whole process group gets SIGTERM, and SIGKILL
only if something is still alive TERMINATE_GRACE_SECONDS later:
  - The process GROUP, because the fetch is the check's child. Killing the
    check alone would leave the fetch holding the output pipe open, and
    reading that pipe would then wait for the fetch.
  - SIGTERM first, because git removes its lock files on SIGTERM but cannot
    on SIGKILL. A fetch killed outright can leave a stale ref lock that makes
    the seat's next git command fail with "File exists".
The check's stdout and stderr are both captured, never inherited. So even a
process that outlives both signals holds no pipe that `git push`'s own caller
is waiting on.

The budget can be changed through NEDSCHORUS_PRE_PUSH_CONFLICT_CHECK_SECONDS,
which exists so the test can run a hanging check in a second. A value that
does not parse as a positive number is ignored.

THE MESSAGES. Text a program hands an agent at the moment it must act is
instruction and nothing else (CLAUDE.md, user-ruled 2026-09-18). A refusal
names the branch, passes on the check's own lines, and says to push again.
The check's lines already say how to merge, one instruction per line.
`--no-verify` is deliberately never printed. It is the escape for a person
who knows the hook is wrong, not a step to follow on a refusal.

Runs under the Python 3.9 that macOS ships as well as newer ones: the shell
hook runs whatever `python3` PATH finds first.
"""

import os
import signal
import subprocess
import sys
import time

EXIT_ALLOW_PUSH = 0
EXIT_REFUSE_PUSH = 10

CHECKED_REMOTE_NAME = "origin"
BRANCH_REF_PREFIX = "refs/heads/"
UNCHECKED_BRANCH_REF = "refs/heads/main"
BASE_NAME_FOR_MESSAGES = "origin/main"

CONFLICT_CHECK_FILE_NAME = "branch-conflict-check.py"
CHECK_EXIT_CLEAN = 0
CHECK_EXIT_CONFLICT = 1
CHECK_EXIT_NO_ANSWER = 2
CONFLICT_VERDICT_PREFIX = "VERDICT: CONFLICT"

DEFAULT_TIME_BUDGET_SECONDS = 60.0
TIME_BUDGET_ENVIRONMENT_VARIABLE = "NEDSCHORUS_PRE_PUSH_CONFLICT_CHECK_SECONDS"
TERMINATE_GRACE_SECONDS = 3.0

MESSAGE_PREFIX = "pre-push: "


def branches_to_check(pushed_refs_text):
    """(branch name, local object id) for each pushed ref this hook checks.

    Git writes one line per ref: <local ref> <local object id> <remote ref>
    <remote object id>. A line that does not have four fields is skipped
    rather than trusted.
    """
    branches = []
    for line in pushed_refs_text.splitlines():
        fields = line.split()
        if len(fields) != 4:
            continue
        _local_ref, local_object_id, remote_ref, _remote_object_id = fields
        if set(local_object_id) == {"0"}:
            continue
        if not remote_ref.startswith(BRANCH_REF_PREFIX):
            continue
        if remote_ref == UNCHECKED_BRANCH_REF:
            continue
        branches.append((remote_ref[len(BRANCH_REF_PREFIX):], local_object_id))
    return branches


def time_budget_seconds(environment):
    """The seconds all checks of one push may take together."""
    configured = environment.get(TIME_BUDGET_ENVIRONMENT_VARIABLE, "")
    try:
        seconds = float(configured)
    except ValueError:
        return DEFAULT_TIME_BUDGET_SECONDS
    if seconds > 0:
        return seconds
    return DEFAULT_TIME_BUDGET_SECONDS


def signal_process_group(process, signal_number):
    """Send a signal to the check and everything it started."""
    try:
        os.killpg(process.pid, signal_number)
    except (ProcessLookupError, PermissionError):
        pass


def stop_process_group(process):
    """SIGTERM the check's process group, then SIGKILL it if it lingers.

    Returns whatever output could still be read, as (stdout, stderr).
    """
    for signal_number in (signal.SIGTERM, signal.SIGKILL):
        signal_process_group(process, signal_number)
        try:
            return process.communicate(timeout=TERMINATE_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            continue
    for pipe in (process.stdout, process.stderr):
        try:
            pipe.close()
        except OSError:
            pass
    return "", ""


class CheckResult:
    """What one run of the conflict check came to.

    kind is "conflict", "clean", "no answer" or "no verdict". lines are the
    check's stdout lines; reason says why a "no verdict" is one.
    """

    def __init__(self, kind, lines=(), reason=""):
        self.kind = kind
        self.lines = list(lines)
        self.reason = reason


def run_conflict_check(check_path, local_object_id, seconds_left, budget):
    """Run the check on one commit, stopping it after seconds_left.

    budget is the whole push's time budget, named in the reason when the
    check is stopped.
    """
    try:
        process = subprocess.Popen(
            [sys.executable, check_path, "--head", local_object_id],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8",
            errors="replace", start_new_session=True)
    except (OSError, ValueError) as error:
        return CheckResult("no verdict", reason="it could not be started: %s" % error)
    try:
        stdout, stderr = process.communicate(timeout=seconds_left)
    except subprocess.TimeoutExpired:
        stop_process_group(process)
        return CheckResult(
            "no verdict",
            reason="it had not finished when the %g-second budget ran out, and "
                   "was stopped" % budget)
    lines = stdout.splitlines()
    status = process.returncode
    has_conflict_verdict = any(line.startswith(CONFLICT_VERDICT_PREFIX) for line in lines)
    if status == CHECK_EXIT_CONFLICT and has_conflict_verdict:
        return CheckResult("conflict", lines)
    if status == CHECK_EXIT_CLEAN:
        return CheckResult("clean", lines)
    if status == CHECK_EXIT_NO_ANSWER:
        return CheckResult("no answer", lines)
    if status is not None and status < 0:
        reason = "it was killed by signal %d" % -status
    elif status == CHECK_EXIT_CONFLICT:
        reason = "it exited 1 without a %s line" % CONFLICT_VERDICT_PREFIX
    else:
        reason = "it exited %s" % status
    last_error_line = next(
        (line.strip() for line in reversed(stderr.splitlines()) if line.strip()), "")
    if last_error_line:
        reason = "%s: %s" % (reason, last_error_line)
    return CheckResult("no verdict", reason=reason)


def say(stream, text):
    stream.write(text + "\n")


def main(argv, pushed_refs_text, stderr, environment):
    """Decide one push. Returns EXIT_ALLOW_PUSH or EXIT_REFUSE_PUSH."""
    remote_name = argv[0] if argv else ""
    if remote_name != CHECKED_REMOTE_NAME:
        return EXIT_ALLOW_PUSH
    branches = branches_to_check(pushed_refs_text)
    if not branches:
        return EXIT_ALLOW_PUSH

    check_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), CONFLICT_CHECK_FILE_NAME)
    if not os.path.isfile(check_path):
        say(stderr, MESSAGE_PREFIX + "the conflict check did not run (%s is missing); "
            "the push goes ahead unchecked." % check_path)
        return EXIT_ALLOW_PUSH

    budget = time_budget_seconds(environment)
    deadline = time.monotonic() + budget
    conflicts = []
    for branch, local_object_id in branches:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            say(stderr, MESSAGE_PREFIX + "the conflict check did not run for branch %s "
                "(the %g-second budget was spent); the push goes ahead unchecked."
                % (branch, budget))
            continue
        result = run_conflict_check(check_path, local_object_id, remaining, budget)
        if result.kind == "conflict":
            conflicts.append((branch, result))
        elif result.kind == "no answer":
            say(stderr, MESSAGE_PREFIX + "the conflict check gave no answer for branch "
                "%s; the push goes ahead unchecked." % branch)
            for line in result.lines:
                say(stderr, line)
            say(stderr, "To get an answer, run scripts/%s --head %s from this checkout."
                % (CONFLICT_CHECK_FILE_NAME, local_object_id))
        elif result.kind == "no verdict":
            say(stderr, MESSAGE_PREFIX + "the conflict check gave no verdict for branch "
                "%s (%s); the push goes ahead unchecked." % (branch, result.reason))

    if not conflicts:
        return EXIT_ALLOW_PUSH
    for branch, result in conflicts:
        say(stderr, MESSAGE_PREFIX + "branch %s conflicts with %s; this push is refused."
            % (branch, BASE_NAME_FOR_MESSAGES))
        for line in result.lines:
            say(stderr, line)
    say(stderr, "Once the merge is committed, push again.")
    return EXIT_REFUSE_PUSH


if __name__ == "__main__":
    # Fail open: see the module docstring. Every exception, not only the
    # expected ones, lets the push go with one line saying why.
    try:
        pushed = sys.stdin.buffer.read().decode("utf-8", "replace")
        exit_status = main(sys.argv[1:], pushed, sys.stderr, os.environ)
    except Exception as error:
        say(sys.stderr, MESSAGE_PREFIX + "the conflict check failed (%s: %s); the push "
            "goes ahead unchecked." % (type(error).__name__, error))
        exit_status = EXIT_ALLOW_PUSH
    sys.exit(exit_status)
