#!/usr/bin/env python3
"""Replay recorded real Bash commands through the Bash guards at two git refs, and compare the verdicts.

Every pull request that changes a Bash guard or the shell command reader runs this at the base
and at the pull request's head. A verdict that differs blocks the merge. A guard the pull request
adds, a Bash hook in the head's .claude/settings.json but not the base's, is read at the head only,
and each recorded command it refuses blocks the merge until the reviewer accepts the refusal.

Usage:
  python3 nc-systems/general-tools/bash-guards-verdict-changes-between-two-git-refs-on-transcript-recorded-commands-check.py \\
      --base-ref origin/main --head-ref <commit or branch>

Steps:
  1. Collect the distinct (command, working directory) pairs of every Bash tool call in the
     transcripts of both machines (--transcript-directory, repeatable), or read them from
     --pairs-file.
  2. Check out each ref as a detached worktree in the scratch directory, and check that the
     guards this replay reads are exactly the Bash PreToolUse hooks in the head checkout's
     .claude/settings.json, and, less the guards the head adds, in the base checkout's.
  3. At each ref, run the guards' analysis functions on every pair, with the guards' probes
     of git and gh stubbed so a verdict depends only on the command text and the working directory
     (in-process mode). Run the search-file guard's main() with each pair's own working
     directory. Then run the analysis again on every pair with the shell reader in new-process
     mode, unless --new-process-pairs is none: each pool worker keeps one shell reader child
     process running and sends it one command at a time, through the same JSON conversion a
     hook's new process uses.
  4. Compare the two refs row by row and print each difference, then, for each guard the head
     adds, every recorded command it refuses.

Exit status: 0 when no verdict differs and no added guard refuses a recorded command; 1 when a
verdict differs or an added guard refuses a recorded command; 2 when the replay itself
failed, which includes a guard that raised or timed out on a recorded command at either ref,
because that row has no verdict to compare. A message that differs while its verdict does not is
printed, and does not change the exit status. The scratch directory is removed after an exit 0
unless --scratch-directory named it; after an exit 1 or 2 it is kept, and its path is printed.
"""

import argparse
import collections
import contextlib
import importlib.util
import io
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import traceback
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path

DEFAULT_TRANSCRIPT_DIRECTORIES = [
    str(Path.home() / ".claude" / "projects"),
    "/home/nedlern/nedschorus-logs/transcripts/mac/projects",
    "/home/nedlern/nedschorus-logs/transcripts/ned-box",
    "/home/nedlern/nedschorus-logs/transcripts/recovered",
]

DEFAULT_PER_PAIR_TIMEOUT_SECONDS = 20
# Pairs a worker reads per task; a worker that dies loses at most this many, and they are named.
PAIRS_PER_TASK = 200
# Margin for starting interpreters and loading the guards, on top of the worst case for the readings.
STEP_DEADLINE_MARGIN_SECONDS = 600
GIT_TIMEOUT_SECONDS = 600
PRINTED_TEXT_LENGTH = 300
NEW_GUARD_REFUSES_MESSAGE = (
    "NEW GUARD REFUSES RECORDED COMMANDS: a guard the head adds refuses each numbered command listed above "
    "under a \"new guard ... would refuse\" line, so this check exits 1. Agents ran each of those commands, "
    "and a guard that refuses a command agents need stops their work.\n"
    "The pull request's reviewer answers each listed command in the review, on a line of its own:\n"
    "  refusal right: <guard file> | <working directory> | <command>\n"
    "copying the guard file's path from its \"new guard\" line and the working directory and the command from "
    "the numbered entry, the command last, quotes included, so a | inside it is part of the command; for "
    "example, with a made-up guard path: refusal right: scripts/example-guard-hook.py | /tmp | 'tmux kill-server'. "
    "Answer a command whose refusal is wrong with a finding instead, and the author then narrows the guard so "
    "that it lets that command through. Each guard, working directory and command together need one line, "
    "once, even when more than one mode (in-process, search-file main(), new-process) lists them.\n")
NEW_GUARD_REFUSES_ONLY_ENDING = (
    "merge-lane-2 holds the merge until the review has a \"refusal right\" line for every listed command, "
    "and then merges despite the exit 1.")
NEW_GUARD_REFUSES_AND_VERDICT_CHANGED_ENDING = (
    "The VERDICT CHANGED line above blocks the merge on its own: \"refusal right\" lines do not clear it, "
    "so the merge also waits until each verdict difference is explained and intended.")

# Copied from the parent, never inherited: a git variable would point the checkouts' git at
# another repository, and the attendance variables change the guards' messages.
_git_redirecting_removal_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_variables_removal_common",
    Path(__file__).resolve().with_name("git-redirecting-environment-variables-removal-common.py"))
_git_redirecting_removal = importlib.util.module_from_spec(_git_redirecting_removal_spec)
_git_redirecting_removal_spec.loader.exec_module(_git_redirecting_removal)
ENVIRONMENT_VARIABLES_REMOVED = _git_redirecting_removal.GIT_REDIRECTING_ENVIRONMENT_VARIABLES + (
    "CLAUDE_CODE_SESSION_ATTENDED", "NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER",
)


class ReplayFailed(Exception):
    """The replay could not produce verdicts it can stand behind."""


class PairTimedOut(BaseException):
    """A guard ran past its time on one pair.

    A BaseException, so the shell reader's own `except Exception` cannot turn the timeout into
    a reading that looks like a verdict.
    """


def raise_pair_timed_out(*_):
    raise PairTimedOut()


class ShellReaderLongRunningChildProcessDiedMidRequest(BaseException):
    """The shell reader's long-running child process exited, or could not be written to, before it replied.

    A BaseException, as PairTimedOut is, so the shell reader's and the guards' own `except Exception`
    cannot turn the lost reading into a verdict.
    """


# A stop signal must not raise SystemExit inside subprocess's own code: raised between Popen._wait()'s
# lock acquire and its try, it leaves the lock held, and the wait() that subprocess.run() or
# run_step_in_child() then makes blocks forever with the child unreaped. Every subprocess call in the
# replay parent runs inside stop_deferred(), in which the handler only records the stop and the block's
# exit raises SystemExit(2) from the replay's own code, except remove_checkouts(), which runs after the
# stop signals are set to SIG_IGN.
STOP_STATE = {"deferred": 0, "stop_requested": False}


def raise_terminated(*_):
    if STOP_STATE["deferred"]:
        STOP_STATE["stop_requested"] = True
        return
    raise SystemExit(2)  # So the finally blocks remove the checkouts when the run is stopped.


@contextlib.contextmanager
def stop_deferred():
    STOP_STATE["deferred"] += 1
    try:
        yield
    finally:
        STOP_STATE["deferred"] -= 1
        if STOP_STATE["stop_requested"] and not STOP_STATE["deferred"]:
            STOP_STATE["stop_requested"] = False
            raise SystemExit(2)


# ---------------------------------------------------------------- step 1: the pairs

def raise_walk_failed(error):
    raise ReplayFailed(f"reading the transcripts failed: {error}")


def recorded_command_pairs(transcript_directories):
    """Return (the distinct [command, working directory] pairs of the Bash tool calls in first-seen order,
    the number of transcript lines that are not JSON)."""
    seen = {}
    lines_not_json = 0
    for directory in transcript_directories:
        if not os.path.isdir(directory):
            raise ReplayFailed(f"transcript directory {directory} does not exist")
        for parent, _, names in os.walk(directory, onerror=raise_walk_failed):
            for name in sorted(names):
                if not name.endswith(".jsonl"):
                    continue
                path = os.path.join(parent, name)
                try:
                    handle = open(path, "rb")
                except FileNotFoundError:
                    continue  # Removed after the walk listed it.
                except OSError as error:
                    raise ReplayFailed(f"transcript {path} cannot be read: {error}") from error
                with handle:
                    for line in handle:
                        if b'"Bash"' not in line:
                            continue
                        try:
                            record = json.loads(line)
                        except ValueError:
                            lines_not_json += 1  # Most often the last line of a transcript still being written.
                            continue
                        message = record.get("message")
                        content = message.get("content") if isinstance(message, dict) else None
                        if not isinstance(content, list):
                            continue
                        for item in content:
                            if (isinstance(item, dict) and item.get("type") == "tool_use"
                                    and item.get("name") == "Bash"):
                                command = (item.get("input") or {}).get("command")
                                if isinstance(command, str):
                                    seen.setdefault((command, record.get("cwd") or "/"), None)
    return [list(pair) for pair in seen], lines_not_json


# ---------------------------------------------------------------- step 2: the guards a checkout has

def bash_hook_files(checkout):
    """Return the repository paths of the PreToolUse hooks that .claude/settings.json runs on a Bash call."""
    settings = json.loads((Path(checkout) / ".claude" / "settings.json").read_text())
    files = set()
    for entry in settings.get("hooks", {}).get("PreToolUse", []):
        matcher = entry.get("matcher") or "*"
        if matcher != "*" and not re.fullmatch(matcher, "Bash"):
            continue
        for hook in entry.get("hooks", []):
            found = re.search(r'"\$CLAUDE_PROJECT_DIR"/(\S+)', hook.get("command", ""))
            if not found:
                raise ReplayFailed(f"a Bash hook in {checkout}/.claude/settings.json runs "
                                   f"{hook.get('command')!r}, which names no file in the repository")
            files.add(found.group(1))
    return files


def check_guards_match_settings(hooks, replayed, label):
    if hooks != replayed:
        raise ReplayFailed(
            f"the Bash hooks in .claude/settings.json at the {label} ref are not the guards this replay reads; "
            f"not replayed: {sorted(hooks - replayed) or 'none'}; replayed but not a Bash hook: "
            f"{sorted(replayed - hooks) or 'none'}. Add each new hook to GUARDS in this script, with a function "
            f"that reads one command through it, in the pull request that adds the hook")


def guards_added_at_head(checkouts):
    """Return the guards in the head's settings.json but not the base's, after checking both against GUARDS."""
    head_hooks, base_hooks = bash_hook_files(checkouts["head"]), bash_hook_files(checkouts["base"])
    check_guards_match_settings(head_hooks, set(GUARDS), "head")
    added = head_hooks - base_hooks
    check_guards_match_settings(base_hooks, set(GUARDS) - added, "base")
    return sorted(added)


# ---------------------------------------------------------------- step 3: one ref's verdicts

WORKER = {}


def load_module(checkout, relative_path, name):
    spec = importlib.util.spec_from_file_location(name, Path(checkout) / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ShellReaderLongRunningChildProcessRequestSender:
    """Answers one shell reader file's new-process reads from one child process that reads one request per line.

    The reader calls it as it calls subprocess.run, with the request as input, and decodes the reply
    exactly as it decodes a one-command process's output. The child is started at the first request
    and again at the first request after a failure.
    """

    def __init__(self, reader_path, flag):
        self.reader_path, self.flag, self.child = str(reader_path), flag, None

    def __call__(self, argv, input, **_):
        # The per-pair alarm, not the reader's own timeout, bounds the wait for a reply.
        try:
            if self.child is None:
                self.child = subprocess.Popen([sys.executable, self.reader_path, self.flag],
                                              stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            self.child.stdin.write(input + b"\n")
            self.child.stdin.flush()
            reply = self.child.stdout.readline()
        except OSError as error:
            status = self.close()
            raise ShellReaderLongRunningChildProcessDiedMidRequest(
                f"the shell reader child process for {self.reader_path} failed ({error}; exit {status}); "
                f"its error output is in this step's log") from error
        except BaseException:
            self.close()  # A PairTimedOut: a reply the child sends late must not answer the next request.
            raise
        if not reply.endswith(b"\n"):
            status = self.close()
            raise ShellReaderLongRunningChildProcessDiedMidRequest(
                f"the shell reader child process for {self.reader_path} exited {status} before it replied; "
                f"its error output is in this step's log")
        return subprocess.CompletedProcess(argv, 0, reply, b"")

    def close(self):
        """Stop the child, if one runs, and return its exit status."""
        child, self.child = self.child, None
        if child is None:
            return None
        child.kill()
        for pipe in (child.stdin, child.stdout):
            with contextlib.suppress(OSError):
                pipe.close()
        return child.wait()


def guards_loaded(checkout, new_process, guards_left_out=()):
    """Return (guards, how many shell reader modules were switched to read in a new process,
    the senders of the long-running child processes, how many of those modules read one command per
    process because their reader has no flag for a long-running child).

    guards_left_out are the guards the head adds, which the base checkout does not have.
    """
    guards = {path: load_module(checkout, path, "replayed_" + re.sub(r"\W", "_", path))
              for path in GUARDS if path not in guards_left_out}
    switched, one_command_per_process, senders = 0, 0, {}
    if new_process:
        for guard in guards.values():
            for value in vars(guard).values():
                if type(value).__name__ == "module" and hasattr(value, "_use_a_new_process"):
                    flag = getattr(value, "NEW_PROCESS_READ_ONE_REQUEST_PER_LINE_UNTIL_INPUT_CLOSES_FLAG", None)
                    if flag is None:
                        # A ref older than the flag, such as the base ref of the pull request that added it.
                        value._use_a_new_process()
                        one_command_per_process += 1
                    else:
                        reader_path = Path(value.__file__).resolve()
                        value._use_a_new_process(senders.setdefault(
                            reader_path, ShellReaderLongRunningChildProcessRequestSender(reader_path, flag)))
                    switched += 1
        if switched == 0:
            raise ReplayFailed(f"no guard at {checkout} loads a shell reader that has _use_a_new_process()")
    return guards, switched, list(senders.values()), one_command_per_process


class StubbedProbeRunner:
    """Answers the guards' git and gh probes the same way at both refs, and records them."""

    def __init__(self):
        self.calls = []

    def __call__(self, argv, **keywords):
        argv = list(argv)
        self.calls.append(" ".join(argv[:3]) if argv[:1] == ["git"] else f"{argv[0]} in {keywords.get('cwd')}")
        if argv[:1] == ["git"]:
            return subprocess.CompletedProcess(argv, 0, "the-pull-request-branch\n", "")
        if argv[:1] == ["gh"]:
            return subprocess.CompletedProcess(argv, 0, json.dumps([{"title": "t", "url": "u"}]), "")
        return subprocess.CompletedProcess(argv, 0, "1\n", "")


def fixed_clock():
    return 1000.0


def is_failed_reading(verdict):
    return isinstance(verdict, str) and (verdict.startswith("EXCEPTION") or verdict == "TIMEOUT")


def read_synthetic_keystroke(guard, command, working_directory, search_file_directory):
    runner = StubbedProbeRunner()
    reason = guard.analyze_command_text(command, None, False, guard.GuardRun(runner, fixed_clock))
    return ["refused" if reason else "passed", sorted(set(runner.calls))], reason


def read_force_push(guard, command, working_directory, search_file_directory):
    runner = StubbedProbeRunner()
    decision, reason = guard.analyze_command_text(command, working_directory, guard.GuardRun(runner, fixed_clock))
    return [decision, sorted(set(runner.calls))], reason


def read_issue_write(guard, command, working_directory, search_file_directory):
    reason = guard.analyze_command_text(command, "/nonexistent-directory")
    return "refused" if reason else "passed", reason


def read_tmux_kill(guard, command, working_directory, search_file_directory):
    reason = guard.refusal_for(command)
    return "refused" if reason else "passed", reason


def read_search_file(guard, command, working_directory, search_file_directory):
    reason = guard.analyze_command_text(command, search_file_directory, time.monotonic)
    return "refused" if reason else "passed", reason


def read_codex_exec(guard, command, working_directory, search_file_directory):
    reason = guard.refusal_for_command(command)
    return "refused" if reason else "passed", reason


class MarkdownChangingCheckoutProbeRunner(StubbedProbeRunner):
    """Answers the Markdown push reminder's git as a checkout whose every ref changes one Markdown file.

    The checkout is the ref's own, which holds both citation programs the reminder looks for, and
    every ref is the commit checked out, so the reminder's outcome depends only on the command.
    """

    def __call__(self, argv, **keywords):
        argv = list(argv)
        # The checkout's path differs between the base and head checkouts, so it is named, not written.
        self.calls.append(" ".join(argv[:5]).replace(WORKER["checkout"], "<checkout>"))
        arguments = argv[3:]  # After git -C <directory>.
        if arguments[:2] == ["rev-parse", "--show-toplevel"]:
            return subprocess.CompletedProcess(argv, 0, WORKER["checkout"] + "\n", "")
        if arguments[:1] == ["diff"]:
            return subprocess.CompletedProcess(argv, 0, "docs/changed-page.md\0", "")
        if arguments[:1] == ["branch"]:
            return subprocess.CompletedProcess(argv, 0, "the-pull-request-branch\n", "")
        return subprocess.CompletedProcess(argv, 0, "0" * 40 + "\n", "")


def read_markdown_push_reminder(guard, command, working_directory, search_file_directory):
    runner = MarkdownChangingCheckoutProbeRunner()
    messages = guard.messages_for_command(command, working_directory, runner)
    # The hook never refuses; what it adds to the agent's context is its verdict.
    return [["added context" if messages else "passed", sorted(set(runner.calls))],
            "\n\n".join(messages) or None]


# Every Bash PreToolUse hook in .claude/settings.json, by the file it runs, with the function
# that reads one command through it. check_guards_match_settings() names each hook missing here,
# so a new guard is one line: its file and a reading function like the ones above.
GUARDS = {
    "scripts/synthetic-keystroke-guard-hook.py": read_synthetic_keystroke,
    "scripts/force-push-with-open-pull-request-guard-hook.py": read_force_push,
    ".claude/hooks/ghi-issue-write-redirect.py": read_issue_write,
    "nc-systems/general-tools/claude-code-tmux-kill-server-and-kill-session-missing-server-selection-refusal-hook.py": read_tmux_kill,
    "scripts/search-file-argument-read-as-option-guard-hook.py": read_search_file,
    "scripts/hand-typed-codex-exec-redirect-hook.py": read_codex_exec,
    "nc-systems/general-tools/claude-code-bash-git-push-of-markdown-change-citation-checks-reminder-hook.py":
        read_markdown_push_reminder,
}
SEARCH_FILE_GUARD = "scripts/search-file-argument-read-as-option-guard-hook.py"


def guard_readings(guards, command, working_directory, search_file_directory):
    """Return {guard file: (verdict, message)} for one pair; the verdict is what decides the merge."""
    readings = {}
    for path in guards:
        try:
            signal.alarm(WORKER.get("timeout", DEFAULT_PER_PAIR_TIMEOUT_SECONDS))
            verdict, message = GUARDS[path](guards[path], command, working_directory, search_file_directory)
            if isinstance(message, str) and WORKER.get("checkout"):
                # A message naming a file in the checkout would differ between the base and head checkouts.
                message = message.replace(WORKER["checkout"], "<checkout>")
            readings[path] = (verdict, message)
        except PairTimedOut:
            readings[path] = ("TIMEOUT", None)
        except (Exception, SystemExit, ShellReaderLongRunningChildProcessDiedMidRequest) as error:
            # A failed reading; is_failed_reading() makes the run exit 2.
            # SystemExit too: one escaping a worker would end that worker.
            readings[path] = (f"EXCEPTION {type(error).__name__}", str(error))
        finally:
            signal.alarm(0)
    return readings


def worker_start(checkout, new_process, search_file_directory, timeout, guards_left_out):
    os.nice(15)
    WORKER["timeout"] = timeout
    WORKER["checkout"] = str(checkout)
    signal.signal(signal.SIGALRM, raise_pair_timed_out)
    WORKER["guards"], WORKER["switched"], _, _ = guards_loaded(checkout, new_process, guards_left_out)
    WORKER["search_file_directory"] = search_file_directory


def worker_guard_rows(pairs):
    rows = []
    for command, working_directory in pairs:
        rows.append({key: list(value) for key, value in guard_readings(
            WORKER["guards"], command, working_directory, WORKER["search_file_directory"]).items()})
    return rows, WORKER["switched"]


def search_file_main_outcome(guard, command, working_directory):
    """Return ([what the search-file guard's main() does, its exit status], the message it prints)
    for the hook payload of one recorded call."""
    payload = json.dumps({"tool_name": "Bash", "cwd": working_directory, "tool_input": {"command": command}})
    printed = io.StringIO()
    with contextlib.redirect_stdout(printed):
        exit_status = guard.main(stdin=io.StringIO(payload))
    text = printed.getvalue().strip()
    if not text:
        return ["silent", exit_status], None
    try:
        output = json.loads(text)["hookSpecificOutput"]
    except (ValueError, KeyError, TypeError):
        return ["output that is not hook JSON", exit_status], text
    if output.get("permissionDecision") == "deny":
        return ["refused", exit_status], output.get("permissionDecisionReason")
    return ["let through with a note", exit_status], output.get("additionalContext")


def worker_search_file_main_rows(pairs):
    rows = []
    for command, working_directory in pairs:
        try:
            signal.alarm(WORKER["timeout"])
            verdict, message = search_file_main_outcome(WORKER["guards"][SEARCH_FILE_GUARD], command,
                                                         working_directory)
            if isinstance(message, str):
                message = message.replace(WORKER["checkout"], "<checkout>")
            row = [verdict, message]
        except PairTimedOut:
            row = ["TIMEOUT", None]
        except (Exception, SystemExit, ShellReaderLongRunningChildProcessDiedMidRequest) as error:
            # A failed reading; is_failed_reading() makes the run exit 2.
            row = [f"EXCEPTION {type(error).__name__}", str(error)]
        finally:
            signal.alarm(0)
        rows.append(row)
    return rows, WORKER["switched"]


def smoke_check(checkout, new_process, search_file_directory, timeout, guards_left_out):
    """Fail the replay when a guard cannot read even `true`: the replay no longer fits the guards' code.

    Return (how many shell reader modules read in a new process, how many of them one command per process).
    """
    guards, switched, senders, one_command_per_process = guards_loaded(checkout, new_process, guards_left_out)
    signal.signal(signal.SIGALRM, raise_pair_timed_out)
    WORKER["timeout"] = timeout
    readings = guard_readings(guards, "true", "/", search_file_directory)
    try:
        signal.alarm(timeout)
        readings["search-file main()"] = search_file_main_outcome(guards[SEARCH_FILE_GUARD], "true", "/")
    except PairTimedOut:
        readings["search-file main()"] = ("TIMEOUT", None)
    except (Exception, SystemExit, ShellReaderLongRunningChildProcessDiedMidRequest) as error:
        readings["search-file main()"] = (f"EXCEPTION {type(error).__name__}", str(error))
    finally:
        signal.alarm(0)
        for sender in senders:
            sender.close()  # Before the pool starts, so no worker inherits the child's pipes.
    for key, (verdict, detail) in readings.items():
        if is_failed_reading(verdict):
            raise ReplayFailed(
                f"the {key} guard at {checkout} gave {verdict} ({detail}) on the command `true`; "
                f"its functions no longer match what this replay calls")
    return switched, one_command_per_process


def ref_verdicts(checkout, pairs, jobs, new_process, search_file_directory, search_file_main, timeout,
                 guards_left_out=()):
    """Return (rows, shell readers switched to a new process, how many of them read one command per process)."""
    switched, one_command_per_process = smoke_check(checkout, new_process, search_file_directory, timeout,
                                                    guards_left_out)
    tasks = [pairs[start:start + PAIRS_PER_TASK] for start in range(0, len(pairs), PAIRS_PER_TASK)]
    read = worker_search_file_main_rows if search_file_main else worker_guard_rows
    # Not multiprocessing.Pool: when a Pool worker dies, its task is never finished and map() waits
    # forever. A ProcessPoolExecutor marks every unfinished task broken instead.
    executor = ProcessPoolExecutor(jobs, initializer=worker_start,
                                   initargs=(checkout, new_process, search_file_directory, timeout, guards_left_out))
    rows, not_read, workers_switched = [], [], set()
    try:
        futures = [executor.submit(read, task) for task in tasks]
        for task, future in zip(tasks, futures):
            try:
                task_rows, worker_switched = future.result()
            except BrokenProcessPool:
                not_read.extend(task)
                continue
            rows.extend(task_rows)
            workers_switched.add(worker_switched)
    finally:
        # Without waiting: the step then exits, and run_step_in_child() stops its process group.
        executor.shutdown(wait=False, cancel_futures=True)
    if not_read:
        raise ReplayFailed(f"a worker reading at {checkout} died, so {len(not_read)} pairs were not read; the first: "
                           + "; ".join(repr(command[:100]) for command, _ in not_read[:5]))
    if len(rows) != len(pairs):
        raise ReplayFailed(f"{checkout} gave {len(rows)} rows for {len(pairs)} pairs")
    if workers_switched - {switched}:
        raise ReplayFailed(f"the workers at {checkout} switched {sorted(workers_switched)} shell readers to a new "
                           f"process, where the check before them switched {switched}")
    return rows, switched, one_command_per_process


# ---------------------------------------------------------------- step 4: compare

def verdict_differences(pairs, base_rows, head_rows):
    """Return (differences, message-only differences); each item is (pair, guard, base, head)."""
    if not (len(pairs) == len(base_rows) == len(head_rows)):
        raise ReplayFailed(f"row counts differ: {len(pairs)} pairs, {len(base_rows)} base, {len(head_rows)} head")
    differences, message_differences = [], []
    for pair, base, head in zip(pairs, base_rows, head_rows):
        if isinstance(base, dict):
            for key in base:  # A guard the head adds is in the head's rows only.
                if base[key][0] != head[key][0]:
                    differences.append((pair, key, base[key], head[key]))
                elif base[key][1] != head[key][1]:
                    message_differences.append((pair, key, base[key], head[key]))
        elif base[0] != head[0]:
            differences.append((pair, "search-file main()", base, head))
        elif base[1] != head[1]:
            message_differences.append((pair, "search-file main()", base, head))
    return differences, message_differences


def refuses(verdict):
    decision = verdict[0] if isinstance(verdict, list) else verdict
    return decision in ("refused", "deny")


def added_guard_refusals(pairs, head_rows, added_guards):
    """Return each (pair, guard, head reading) where a guard the head adds refuses the pair."""
    return [(pair, guard, row[guard]) for pair, row in zip(pairs, head_rows) if isinstance(row, dict)
            for guard in added_guards if refuses(row[guard][0])]


def failed_readings(pairs, rows, label):
    """Return each (pair, guard, label, reading) whose reading raised or timed out."""
    failed = []
    for pair, row in zip(pairs, rows):
        readings = row.items() if isinstance(row, dict) else [("search-file main()", row)]
        for key, reading in readings:
            if is_failed_reading(reading[0]):
                failed.append((pair, key, label, reading))
    return failed


# ---------------------------------------------------------------- the whole flow

def child_environment():
    environment = {key: value for key, value in os.environ.items() if key not in ENVIRONMENT_VARIABLES_REMOVED}
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def run_git(repository, *arguments):
    try:
        with stop_deferred():
            completed = subprocess.run(["git", "-C", repository, *arguments], capture_output=True, text=True,
                                       env=child_environment(), timeout=GIT_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as error:
        raise ReplayFailed(f"git {' '.join(arguments)} did not finish in {GIT_TIMEOUT_SECONDS} s") from error
    if completed.returncode != 0:
        raise ReplayFailed(f"git {' '.join(arguments)} exited {completed.returncode}: {completed.stderr.strip()}")
    return completed.stdout.strip()


STOP_CHECK_INTERVAL_SECONDS = 0.2  # How soon a stop signal received during a step's wait takes effect.


def step_deadline_seconds(pair_count, jobs, timeout):
    """The longest one step can take if every reading of every pair runs to its timeout."""
    readings_per_pair = len(GUARDS) + 1  # The guards, or search-file main(); plus the smoke check's share.
    return -(-pair_count // jobs) * readings_per_pair * timeout + STEP_DEADLINE_MARGIN_SECONDS


def run_step_in_child(arguments, log_path, deadline_seconds):
    """Run one ref's step in a fresh interpreter, so each ref's modules load from that ref alone."""
    # In its own process group, so a step that ends, fails or is stopped takes its workers with it;
    # they would otherwise go on reading checkouts the replay is removing.
    with stop_deferred(), open(log_path, "w") as log:
        step = subprocess.Popen([sys.executable, "-B", __file__, *arguments], stdout=log,
                                stderr=subprocess.STDOUT, env=child_environment(), start_new_session=True)
        try:
            returncode = None
            deadline = time.monotonic() + deadline_seconds
            while returncode is None and time.monotonic() < deadline and not STOP_STATE["stop_requested"]:
                with contextlib.suppress(subprocess.TimeoutExpired):
                    returncode = step.wait(timeout=min(STOP_CHECK_INTERVAL_SECONDS, max(deadline - time.monotonic(), 0)))
        finally:
            # macOS answers EPERM, not ESRCH, when every process left in the group has exited but is not yet
            # reaped, as the step is after a normal exit; the processes are this replay's own, so EPERM can
            # mean nothing else.
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(step.pid, signal.SIGKILL)
            step.wait()
    if returncode is None:
        raise ReplayFailed(f"the step {arguments[1]} ran past its deadline of {deadline_seconds} s and was stopped; "
                           f"log {log_path}")
    if returncode != 0:
        tail = Path(log_path).read_text(errors="replace").strip().splitlines()[-5:]
        raise ReplayFailed(f"the step {arguments[1]} exited {returncode}; log {log_path}: " + " | ".join(tail))


def shortened(value):
    text = str(value)
    return text if len(text) <= PRINTED_TEXT_LENGTH else text[:PRINTED_TEXT_LENGTH] + "…"


def print_rows(title, items, limit):
    print(f"{title}: {len(items)}")
    for key, count in sorted(collections.Counter(item[1] for item in items).items()):
        print(f"  {key}: {count}")
    for (command, working_directory), key, *readings in items[:limit]:
        print(f"  {key}  in {working_directory}\n    command: {shortened(repr(command))}")
        if len(readings) == 2 and readings[0][0] == readings[1][0]:
            # Same verdict, different message: show where the messages part.
            base, head = (str(reading[1]) for reading in readings)
            start = next((index for index, (x, y) in enumerate(zip(base, head)) if x != y), min(len(base), len(head)))
            print(f"    verdict: {readings[0][0]}; the messages differ from character {start}:")
            print(f"    base: {shortened(repr(base[max(0, start - 40):]))}\n    head: {shortened(repr(head[max(0, start - 40):]))}")
            continue
        for name, reading in zip(("base", "head") if len(readings) == 2 else ("at",), readings):
            print(f"    {name}: {shortened(reading)}")


def remove_checkouts(repository, checkouts):
    """Remove each checkout that git has registered or that exists; return the ones that could not be
    removed, with the reason."""
    failed = []
    try:
        listed = subprocess.run(["git", "-C", repository, "worktree", "list", "--porcelain"], capture_output=True,
                                text=True, env=child_environment(), timeout=GIT_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return [f"{checkout}: git worktree list did not finish in {GIT_TIMEOUT_SECONDS} s" for checkout in checkouts]
    if listed.returncode != 0:
        return [f"{checkout}: git worktree list exited {listed.returncode}: {listed.stderr.strip()}"
                for checkout in checkouts]
    # git lists each checkout by its resolved path, so a checkout named through a symlink, such as macOS's
    # /var for /private/var, is matched by its resolved path; otherwise it would be deleted as unregistered.
    registered = {os.path.realpath(line[len("worktree "):])
                  for line in listed.stdout.splitlines() if line.startswith("worktree ")}
    for checkout in checkouts:
        if os.path.realpath(checkout) not in registered:
            if os.path.exists(checkout):
                shutil.rmtree(checkout, ignore_errors=True)  # An add stopped before git registered it.
            if os.path.exists(checkout):
                failed.append(f"{checkout}: not registered with git, and it could not be deleted")
            continue
        try:
            completed = subprocess.run(["git", "-C", repository, "worktree", "remove", "--force", str(checkout)],
                                       capture_output=True, text=True, env=child_environment(),
                                       timeout=GIT_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            failed.append(f"{checkout}: git worktree remove did not finish in {GIT_TIMEOUT_SECONDS} s")
            continue
        if completed.returncode != 0:
            failed.append(f"{checkout}: git worktree remove exited {completed.returncode}: {completed.stderr.strip()}")
    return failed


# The steps run in their own sessions, so a SIGHUP from a closing terminal reaches only the replay,
# which must then remove its checkouts and stop the steps as it does for SIGTERM.
STOP_SIGNALS = (signal.SIGTERM, signal.SIGHUP)


def replay(arguments):
    previous_handlers = {number: signal.signal(number, raise_terminated) for number in STOP_SIGNALS}
    try:
        return replay_with_sigterm_handled(arguments)
    finally:
        for number, handler in previous_handlers.items():
            signal.signal(number, handler)


def replay_with_sigterm_handled(arguments):
    scratch_named = arguments.scratch_directory is not None
    scratch = Path(arguments.scratch_directory).resolve() if scratch_named else \
        Path(tempfile.mkdtemp(prefix="bash-guards-replay-"))
    scratch.mkdir(parents=True, exist_ok=True)
    print(f"scratch directory: {scratch}")
    if arguments.pairs_file:
        pairs = json.loads(Path(arguments.pairs_file).read_text())
    else:
        pairs, lines_not_json = recorded_command_pairs(arguments.transcript_directory or DEFAULT_TRANSCRIPT_DIRECTORIES)
        print(f"transcript lines naming Bash that are not JSON, skipped: {lines_not_json}")
    if not pairs:
        raise ReplayFailed("no recorded Bash commands were found")
    new_process_pairs = pairs if arguments.new_process_pairs == "all" else []
    (scratch / "pairs.json").write_text(json.dumps(pairs))
    (scratch / "new-process-pairs.json").write_text(json.dumps(new_process_pairs))
    print(f"pairs: {len(pairs)}; new-process pairs: {len(new_process_pairs)}")

    # A file whose name starts with - is what the search-file guard looks for.
    search_file_directory = scratch / "search-file-directory"
    search_file_directory.mkdir(exist_ok=True)
    (search_file_directory / "-v.txt").touch()
    (search_file_directory / "a.txt").touch()

    repository = run_git(arguments.repository, "rev-parse", "--show-toplevel")
    checkouts = {}
    status = 2
    try:
        for label, ref in (("base", arguments.base_ref), ("head", arguments.head_ref)):
            commit = run_git(repository, "rev-parse", "--verify", ref + "^{commit}")
            checkout = scratch / f"checkout-{label}"
            checkouts[label] = checkout  # Before the add, so a stop in the middle of the add is cleaned up too.
            run_git(repository, "worktree", "add", "--detach", str(checkout), commit)
            print(f"{label}: {ref} at {commit}")
        added_guards = guards_added_at_head(checkouts)
        print(f"guards the head adds, read at the head only: {added_guards or 'none'}")

        modes = [("in-process", "pairs.json", False, False),
                 ("search-file main()", "pairs.json", False, True)]
        if new_process_pairs:
            modes.append(("new-process", "new-process-pairs.json", True, False))
        verdict_changed = False
        added_guard_refused = False
        all_failed = []
        for mode, pairs_name, new_process, search_file_main in modes:
            rows, mode_failed = {}, []
            mode_pairs = json.loads((scratch / pairs_name).read_text())
            for label, checkout in checkouts.items():
                out = scratch / f"verdicts-{mode.split()[0]}-{label}.json"
                started = time.monotonic()
                run_step_in_child(["--step", "verdicts", str(checkout), str(scratch / pairs_name), str(out),
                                   str(arguments.jobs), "1" if new_process else "0",
                                   "1" if search_file_main else "0", str(search_file_directory),
                                   str(arguments.per_pair_timeout_seconds),
                                   json.dumps(added_guards if label == "base" else [])],
                                  scratch / f"verdicts-{mode.split()[0]}-{label}.log",
                                  step_deadline_seconds(len(mode_pairs), arguments.jobs,
                                                        arguments.per_pair_timeout_seconds))
                written = json.loads(out.read_text())
                rows[label] = written["rows"]
                failed = failed_readings(mode_pairs, rows[label], label)
                mode_failed.extend(failed)
                all_failed.extend((pair, f"{mode}, {key}", at, reading) for pair, key, at, reading in failed)
                one_command_per_process = written["shell_readers_reading_one_command_per_process"]
                print(f"{mode}, {label}: {len(rows[label])} rows in {time.monotonic() - started:.0f}s; "
                      f"shell readers in a new process: {written['shell_readers_in_a_new_process']}"
                      + (f", of which one command per process: {one_command_per_process}"
                         if one_command_per_process else "")
                      + f"; failed readings: {len(failed)}")
            differences, message_differences = verdict_differences(mode_pairs, rows["base"], rows["head"])
            print_rows(f"{mode}: rows whose verdict differs", differences, arguments.show)
            print_rows(f"{mode}: rows whose message differs and verdict does not", message_differences, arguments.show)
            refusals = added_guard_refusals(mode_pairs, rows["head"], added_guards)
            for guard in added_guards:
                guard_refusals = [item for item in refusals if item[1] == guard]
                if guard_refusals:
                    # Every one, not the first --show: the reviewer accepts each refusal in the review.
                    # The command in full: the reviewer's "refusal right" line names it, and two long
                    # commands may differ only at the end.
                    print(f"{mode}: new guard {guard} would refuse {len(guard_refusals)} recorded "
                          + ("command, listed with its working directory" if len(guard_refusals) == 1
                             else "commands, each listed with its working directory"))
                    for number, ((command, working_directory), _, reading) in enumerate(guard_refusals, 1):
                        print(f"  {number}. command: {command!r}\n     working directory: {working_directory}\n"
                              f"     head: {shortened(reading)}")
            (scratch / f"differences-{mode.split()[0]}.json").write_text(
                json.dumps({"verdict": differences, "message": message_differences, "failed": mode_failed,
                            "added_guard_refusals": refusals}))
            verdict_changed = verdict_changed or bool(differences)
            added_guard_refused = added_guard_refused or bool(refusals)
        if all_failed:
            print_rows("REPLAY FAILED: readings that raised or timed out, which have no verdict to compare",
                       [(pair, key, f"{at}: {reading}") for pair, key, at, reading in all_failed], arguments.show)
            status = 2
        elif verdict_changed or added_guard_refused:
            if verdict_changed:
                print("VERDICT CHANGED: a recorded command gets a different verdict at the head; the merge is blocked "
                      "until each difference above is explained and intended.")
            if added_guard_refused:
                print(NEW_GUARD_REFUSES_MESSAGE + (NEW_GUARD_REFUSES_AND_VERDICT_CHANGED_ENDING if verdict_changed
                                                   else NEW_GUARD_REFUSES_ONLY_ENDING))
            status = 1
        else:
            print("NO VERDICT CHANGED")
            status = 0
    finally:
        for number in STOP_SIGNALS:
            signal.signal(number, signal.SIG_IGN)  # A second stop must not interrupt the removal.
        not_removed = remove_checkouts(repository, checkouts.values())
        if not_removed:
            print("REPLAY FAILED: these checkouts could not be removed; remove them with git worktree remove --force:\n  "
                  + "\n  ".join(not_removed))
            status = 2
    if status == 0 and not scratch_named:
        shutil.rmtree(scratch)
        print(f"scratch directory removed: {scratch}")
    else:
        print(f"scratch directory kept: {scratch}")
    return status


def verdicts_step(checkout, pairs_path, out_path, jobs, new_process, search_file_main, search_file_directory,
                  timeout, guards_left_out):
    pairs = json.loads(Path(pairs_path).read_text())
    rows, switched, one_command_per_process = ref_verdicts(
        checkout, pairs, int(jobs), new_process == "1", search_file_directory, search_file_main == "1", int(timeout),
        json.loads(guards_left_out))
    Path(out_path).write_text(json.dumps({"rows": rows, "shell_readers_in_a_new_process": switched,
                                          "shell_readers_reading_one_command_per_process": one_command_per_process}))
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        if argv[:1] == ["--step"]:
            return verdicts_step(*argv[2:])
        parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
        parser.add_argument("--base-ref", default="origin/main")
        parser.add_argument("--head-ref", required=True)
        parser.add_argument("--repository", default=".", help="the git repository the refs are in")
        parser.add_argument("--transcript-directory", action="append",
                            help="a directory of Claude Code transcripts (repeatable); "
                                 "by default both machines' transcripts on ned-box")
        parser.add_argument("--pairs-file", help="a JSON list of [command, working directory] pairs to replay "
                                                 "instead of reading the transcripts")
        parser.add_argument("--new-process-pairs", choices=("all", "none"), default="all")
        # Half the processors, so the replay leaves the machine room for other agents' work.
        parser.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) // 2))
        parser.add_argument("--scratch-directory", help="kept after the run; by default a temporary directory, "
                                                        "removed when no verdict changed")
        parser.add_argument("--per-pair-timeout-seconds", type=int, default=DEFAULT_PER_PAIR_TIMEOUT_SECONDS,
                            help="how long one guard may take on one command before the reading counts as failed")
        parser.add_argument("--show", type=int, default=20, help="how many rows to print per list")
        return replay(parser.parse_args(argv))
    except ReplayFailed as error:
        print(f"REPLAY FAILED: {error}", file=sys.stderr)
        return 2
    except Exception as error:  # A pairs file, the scratch directory or the disk; never the verdict status 1.
        # Where in this file it was raised, since an error such as PermissionError does not say which step it
        # stopped; the innermost frame is often inside the standard library.
        where = [frame for frame in traceback.extract_tb(error.__traceback__)
                 if os.path.realpath(frame.filename) == os.path.realpath(__file__)][-1]
        this_file = Path(os.path.realpath(__file__))
        print(f"REPLAY FAILED: {type(error).__name__}: {error}\n  raised at "
              f"{this_file.relative_to(this_file.parents[2])}:{where.lineno}: {where.line}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)  # Progress shows while a long replay runs.
    sys.exit(main())
