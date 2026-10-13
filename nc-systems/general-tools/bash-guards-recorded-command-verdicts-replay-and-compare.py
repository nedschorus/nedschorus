#!/usr/bin/env python3
"""Replay recorded real Bash commands through the five Bash guards at two git refs, and compare the verdicts.

Every pull request that changes a Bash guard or the shell command reader runs this at the base
and at the pull request's head. A verdict that differs blocks the merge.

Usage:
  python3 nc-systems/general-tools/bash-guards-recorded-command-verdicts-replay-and-compare.py \\
      --base-ref origin/main --head-ref <commit or branch>

Steps:
  1. Collect the distinct (command, working directory) pairs of every Bash tool call in the
     transcripts of both machines (--transcript-directory, repeatable), or read them from
     --pairs-file.
  2. Check out each ref as a detached worktree in the scratch directory.
  3. At each ref, run the five guards' analysis functions on every pair, with the guards' probes
     of git and gh stubbed so a verdict depends only on the command text and the working directory
     (in-process mode). Run the search-file guard's main() with each pair's own working
     directory. Then run the analysis again with the shell reader in new-process mode, on all
     pairs or on the subset --new-process-pairs names.
  4. Compare the two refs row by row and print each difference.

Exit status: 0 when no verdict differs; 1 when a verdict differs; 2 when the replay itself failed.
A message that differs while its verdict does not is printed, and does not change the exit status.
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
from multiprocessing import Pool
from pathlib import Path

DEFAULT_TRANSCRIPT_DIRECTORIES = [
    str(Path.home() / ".claude" / "projects"),
    "/home/nedlern/nedschorus-logs/transcripts/mac/projects",
    "/home/nedlern/nedschorus-logs/transcripts/ned-box",
]

# The guards, by the file each loads from in a checkout.
GUARD_FILES = {
    "synthetic-keystroke": "scripts/synthetic-keystroke-guard-hook.py",
    "force-push": "scripts/force-push-with-open-pull-request-guard-hook.py",
    "ghi-issue-write": ".claude/hooks/ghi-issue-write-redirect.py",
    "tmux-kill": "nc-systems/general-tools/claude-code-tmux-kill-server-and-kill-session-missing-server-selection-refusal-hook.py",
    "search-file": "scripts/search-file-argument-read-as-option-guard-hook.py",
}

# A new process per read is about 50 times slower than reading in-process, so by default
# new-process mode reads only the commands whose reading carries the most structure across
# the transport: a heredoc, a case terminator, or ~.
NEW_PROCESS_SUBSET_PATTERN = re.compile(r"<<|case|;&|~")

PER_PAIR_TIMEOUT_SECONDS = 20
MESSAGE_PREFIX_LENGTH = 60

# Copied from the parent, never inherited: a git variable would point the checkouts' git at
# another repository, and the attendance variables change the guards' messages.
ENVIRONMENT_VARIABLES_REMOVED = (
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR",
    "CLAUDE_CODE_SESSION_ATTENDED", "NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER",
)


class ReplayFailed(Exception):
    """The replay could not produce verdicts it can stand behind."""


# ---------------------------------------------------------------- step 1: the pairs

def recorded_command_pairs(transcript_directories):
    """Return the distinct [command, working directory] pairs of the Bash tool calls, in first-seen order."""
    seen = {}
    for directory in transcript_directories:
        if not os.path.isdir(directory):
            raise ReplayFailed(f"transcript directory {directory} does not exist")
        for parent, _, names in os.walk(directory):
            for name in sorted(names):
                if not name.endswith(".jsonl"):
                    continue
                try:
                    handle = open(os.path.join(parent, name), "rb")
                except OSError:
                    continue  # A transcript removed while the walk runs.
                with handle:
                    for line in handle:
                        if b'"Bash"' not in line:
                            continue
                        try:
                            record = json.loads(line)
                        except ValueError:
                            continue  # A line still being written.
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
    return [list(pair) for pair in seen]


# ---------------------------------------------------------------- step 3: one ref's verdicts

WORKER = {}


def load_module(checkout, relative_path, name):
    spec = importlib.util.spec_from_file_location(name, Path(checkout) / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def guards_loaded(checkout, new_process):
    """Return (guards, how many shell reader modules were switched to read in a new process)."""
    guards = {key: load_module(checkout, path, "replayed_" + key.replace("-", "_"))
              for key, path in GUARD_FILES.items()}
    switched = 0
    if new_process:
        for guard in guards.values():
            for value in vars(guard).values():
                if type(value).__name__ == "module" and hasattr(value, "_use_a_new_process"):
                    value._use_a_new_process()
                    switched += 1
        if switched == 0:
            raise ReplayFailed(f"no guard at {checkout} loads a shell reader that has _use_a_new_process()")
    return guards, switched


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


def message_prefix(text):
    return text[:MESSAGE_PREFIX_LENGTH] if text else None


def guard_readings(guards, command, working_directory, search_file_directory):
    """Return {guard: (verdict, message prefix)} for one pair; the verdict is what decides the merge."""
    readings = {}

    def keystroke():
        guard = guards["synthetic-keystroke"]
        runner = StubbedProbeRunner()
        reason = guard.analyze_command_text(command, None, False, guard.GuardRun(runner, fixed_clock))
        return ["refused" if reason else "passed", sorted(set(runner.calls))], message_prefix(reason)

    def force_push():
        guard = guards["force-push"]
        runner = StubbedProbeRunner()
        decision, reason = guard.analyze_command_text(command, working_directory, guard.GuardRun(runner, fixed_clock))
        return [decision, sorted(set(runner.calls))], message_prefix(reason)

    def issue_write():
        reason = guards["ghi-issue-write"].analyze_command_text(command, "/nonexistent-directory")
        return "refused" if reason else "passed", message_prefix(reason)

    def tmux_kill():
        reason = guards["tmux-kill"].refusal_for(command)
        return "refused" if reason else "passed", message_prefix(reason)

    def search_file():
        reason = guards["search-file"].analyze_command_text(command, search_file_directory, time.monotonic)
        return "refused" if reason else "passed", message_prefix(reason)

    for key, read in (("synthetic-keystroke", keystroke), ("force-push", force_push),
                      ("ghi-issue-write", issue_write), ("tmux-kill", tmux_kill),
                      ("search-file", search_file)):
        try:
            signal.alarm(PER_PAIR_TIMEOUT_SECONDS)
            readings[key] = read()
        except PairTimedOut:
            readings[key] = ("TIMEOUT", None)
        except BaseException as error:  # A guard that raises on a command is a verdict to compare.
            readings[key] = (f"EXCEPTION {type(error).__name__}", message_prefix(str(error)))
        finally:
            signal.alarm(0)
    return readings


class PairTimedOut(Exception):
    pass


def raise_pair_timed_out(*_):
    raise PairTimedOut()


def worker_start(checkout, new_process, search_file_directory):
    os.nice(15)
    signal.signal(signal.SIGALRM, raise_pair_timed_out)
    WORKER["guards"], _ = guards_loaded(checkout, new_process)
    WORKER["search_file_directory"] = search_file_directory


def worker_guard_row(pair):
    command, working_directory = pair
    return {key: list(value) for key, value in guard_readings(
        WORKER["guards"], command, working_directory, WORKER["search_file_directory"]).items()}


def search_file_main_outcome(guard, command, working_directory):
    """Return what the search-file guard's main() does with the hook payload of one recorded call."""
    payload = json.dumps({"tool_name": "Bash", "cwd": working_directory, "tool_input": {"command": command}})
    printed = io.StringIO()
    with contextlib.redirect_stdout(printed):
        exit_status = guard.main(stdin=io.StringIO(payload))
    text = printed.getvalue().strip()
    if not text:
        return ["silent", exit_status]
    try:
        output = json.loads(text)["hookSpecificOutput"]
    except (ValueError, KeyError, TypeError):
        return ["output that is not hook JSON", exit_status]
    if output.get("permissionDecision") == "deny":
        return ["refused", exit_status]
    return ["let through with a note", exit_status]


def worker_search_file_main_row(pair):
    command, working_directory = pair
    try:
        signal.alarm(PER_PAIR_TIMEOUT_SECONDS)
        return search_file_main_outcome(WORKER["guards"]["search-file"], command, working_directory)
    except PairTimedOut:
        return ["TIMEOUT", None]
    except BaseException as error:
        return [f"EXCEPTION {type(error).__name__}", None]
    finally:
        signal.alarm(0)


def smoke_check(checkout, new_process, search_file_directory):
    """Fail the replay when a guard cannot read even `true`: the replay no longer fits the guards' code.

    Return how many shell reader modules read in a new process.
    """
    guards, switched = guards_loaded(checkout, new_process)
    signal.signal(signal.SIGALRM, raise_pair_timed_out)
    for key, (verdict, detail) in guard_readings(guards, "true", "/", search_file_directory).items():
        if not isinstance(verdict, list) and (verdict.startswith("EXCEPTION") or verdict == "TIMEOUT"):
            raise ReplayFailed(
                f"the {key} guard at {checkout} gave {verdict} ({detail}) on the command `true`; "
                f"its functions no longer match what this replay calls ({GUARD_FILES[key]})")
    return switched


def ref_verdicts(checkout, pairs, jobs, new_process, search_file_directory, search_file_main):
    switched = smoke_check(checkout, new_process, search_file_directory)
    with Pool(jobs, initializer=worker_start, initargs=(checkout, new_process, search_file_directory)) as pool:
        rows = pool.map(worker_search_file_main_row if search_file_main else worker_guard_row, pairs, chunksize=200)
    if len(rows) != len(pairs):
        raise ReplayFailed(f"{checkout} gave {len(rows)} rows for {len(pairs)} pairs")
    return rows, switched


# ---------------------------------------------------------------- step 4: compare

def verdict_differences(pairs, base_rows, head_rows):
    """Return (differences, message-only differences); each item is (pair, guard, base, head)."""
    if not (len(pairs) == len(base_rows) == len(head_rows)):
        raise ReplayFailed(f"row counts differ: {len(pairs)} pairs, {len(base_rows)} base, {len(head_rows)} head")
    differences, message_differences = [], []
    for pair, base, head in zip(pairs, base_rows, head_rows):
        if isinstance(base, dict):
            for key in GUARD_FILES:
                if base[key][0] != head[key][0]:
                    differences.append((pair, key, base[key], head[key]))
                elif base[key][1] != head[key][1]:
                    message_differences.append((pair, key, base[key], head[key]))
        elif base != head:
            differences.append((pair, "search-file main()", base, head))
    return differences, message_differences


def failed_rows(rows):
    counts = collections.Counter()
    for row in rows:
        verdicts = [value[0] for value in row.values()] if isinstance(row, dict) else [row[0]]
        for verdict in verdicts:
            if isinstance(verdict, str) and (verdict.startswith("EXCEPTION") or verdict == "TIMEOUT"):
                counts[verdict] += 1
    return counts


# ---------------------------------------------------------------- the whole flow

def child_environment():
    environment = {key: value for key, value in os.environ.items() if key not in ENVIRONMENT_VARIABLES_REMOVED}
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def run_git(repository, *arguments):
    completed = subprocess.run(["git", "-C", repository, *arguments], capture_output=True, text=True,
                               env=child_environment())
    if completed.returncode != 0:
        raise ReplayFailed(f"git {' '.join(arguments)} exited {completed.returncode}: {completed.stderr.strip()}")
    return completed.stdout.strip()


def run_step_in_child(arguments, log_path):
    """Run one ref's step in a fresh interpreter, so each ref's modules load from that ref alone."""
    with open(log_path, "w") as log:
        completed = subprocess.run([sys.executable, "-B", __file__, *arguments], stdout=log,
                                   stderr=subprocess.STDOUT, env=child_environment())
    if completed.returncode != 0:
        tail = Path(log_path).read_text(errors="replace").strip().splitlines()[-5:]
        raise ReplayFailed(f"the step {arguments[1]} exited {completed.returncode}; log {log_path}: " + " | ".join(tail))


def print_differences(title, differences, limit):
    print(f"{title}: {len(differences)}")
    by_guard = collections.Counter(item[1] for item in differences)
    for key, count in sorted(by_guard.items()):
        print(f"  {key}: {count}")
    for (command, working_directory), key, base, head in differences[:limit]:
        print(f"  {key}  in {working_directory}\n    command: {command[:300]!r}\n    base: {base}\n    head: {head}")


def replay(arguments):
    scratch = Path(arguments.scratch_directory or tempfile.mkdtemp(prefix="bash-guards-replay-"))
    scratch.mkdir(parents=True, exist_ok=True)
    print(f"scratch directory: {scratch}")
    if arguments.pairs_file:
        pairs = json.loads(Path(arguments.pairs_file).read_text())
    else:
        pairs = recorded_command_pairs(arguments.transcript_directory or DEFAULT_TRANSCRIPT_DIRECTORIES)
        (scratch / "pairs.json").write_text(json.dumps(pairs))
    if not pairs:
        raise ReplayFailed("no recorded Bash commands were found")
    if arguments.new_process_pairs == "all":
        new_process_pairs = pairs
    elif arguments.new_process_pairs == "subset":
        new_process_pairs = [pair for pair in pairs if NEW_PROCESS_SUBSET_PATTERN.search(pair[0])]
    else:
        new_process_pairs = []
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
    try:
        for label, ref in (("base", arguments.base_ref), ("head", arguments.head_ref)):
            commit = run_git(repository, "rev-parse", "--verify", ref + "^{commit}")
            checkout = scratch / f"checkout-{label}"
            run_git(repository, "worktree", "add", "--detach", str(checkout), commit)
            checkouts[label] = checkout
            print(f"{label}: {ref} at {commit}")

        modes = [("in-process", "pairs.json", False, False),
                 ("search-file main()", "pairs.json", False, True)]
        if new_process_pairs:
            modes.append(("new-process", "new-process-pairs.json", True, False))
        verdict_changed = False
        for mode, pairs_name, new_process, search_file_main in modes:
            rows = {}
            for label, checkout in checkouts.items():
                out = scratch / f"verdicts-{mode.split()[0]}-{label}.json"
                started = time.monotonic()
                run_step_in_child(["--step", "verdicts", str(checkout), str(scratch / pairs_name), str(out),
                                   str(arguments.jobs), "1" if new_process else "0",
                                   "1" if search_file_main else "0", str(search_file_directory)],
                                  scratch / f"verdicts-{mode.split()[0]}-{label}.log")
                written = json.loads(out.read_text())
                rows[label] = written["rows"]
                print(f"{mode}, {label}: {len(rows[label])} rows in {time.monotonic() - started:.0f}s; "
                      f"shell readers in a new process: {written['shell_readers_in_a_new_process']}; "
                      f"failed readings {dict(failed_rows(rows[label])) or 0}")
            mode_pairs = json.loads((scratch / pairs_name).read_text())
            differences, message_differences = verdict_differences(mode_pairs, rows["base"], rows["head"])
            print_differences(f"{mode}: rows whose verdict differs", differences, arguments.show)
            print_differences(f"{mode}: rows whose message differs and verdict does not",
                              message_differences, arguments.show)
            (scratch / f"differences-{mode.split()[0]}.json").write_text(
                json.dumps({"verdict": differences, "message": message_differences}))
            verdict_changed = verdict_changed or bool(differences)
    finally:
        for checkout in checkouts.values():
            subprocess.run(["git", "-C", repository, "worktree", "remove", "--force", str(checkout)],
                           capture_output=True, env=child_environment())
    if verdict_changed:
        print("VERDICT CHANGED: a recorded command gets a different verdict at the head; the merge is blocked "
              "until each difference above is explained and intended.")
        return 1
    print("NO VERDICT CHANGED")
    return 0


def verdicts_step(checkout, pairs_path, out_path, jobs, new_process, search_file_main, search_file_directory):
    pairs = json.loads(Path(pairs_path).read_text())
    rows, switched = ref_verdicts(checkout, pairs, int(jobs), new_process == "1", search_file_directory,
                                  search_file_main == "1")
    Path(out_path).write_text(json.dumps({"rows": rows, "shell_readers_in_a_new_process": switched}))
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
        parser.add_argument("--new-process-pairs", choices=("subset", "all", "none"), default="subset")
        parser.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
        parser.add_argument("--scratch-directory")
        parser.add_argument("--show", type=int, default=20, help="how many differences to print per mode")
        return replay(parser.parse_args(argv))
    except ReplayFailed as error:
        print(f"REPLAY FAILED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)  # Progress shows while a long replay runs.
    sys.exit(main())
