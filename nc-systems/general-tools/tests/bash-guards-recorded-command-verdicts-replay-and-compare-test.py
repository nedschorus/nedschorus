#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/bash-guards-recorded-command-verdicts-replay-and-compare.py.

Replays a small fixture of commands, never the real transcripts, at this checkout's HEAD and at
commits made for the test from HEAD with one guard changed: a changed verdict exits 1, a changed
message alone exits 0, and a guard the replay can no longer call exits 2.

Run: python3 nc-systems/general-tools/tests/bash-guards-recorded-command-verdicts-replay-and-compare-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = Path(__file__).resolve().parents[1] / "bash-guards-recorded-command-verdicts-replay-and-compare.py"
TMUX_KILL_GUARD = "nc-systems/general-tools/claude-code-tmux-kill-server-and-kill-session-missing-server-selection-refusal-hook.py"
ISSUE_WRITE_GUARD = ".claude/hooks/ghi-issue-write-redirect.py"
SEARCH_FILE_GUARD = "scripts/search-file-argument-read-as-option-guard-hook.py"

spec = importlib.util.spec_from_file_location("bash_guards_replay", SCRIPT_PATH)
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def git(*arguments, cwd=REPOSITORY_ROOT):
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    return subprocess.run(["git", *arguments], cwd=cwd, capture_output=True, text=True, check=True,
                          env=environment).stdout.strip()


def commit_with_guard_changed(guard_path, appended_code, scratch):
    """Return a commit made from HEAD whose guard file ends with appended_code; HEAD itself is untouched."""
    worktree = Path(scratch) / f"changed-{len(os.listdir(scratch))}"
    git("worktree", "add", "--detach", str(worktree), "HEAD")
    try:
        with open(worktree / guard_path, "a") as handle:
            handle.write("\n" + appended_code + "\n")
        git("-c", "core.hooksPath=/dev/null", "-c", "user.name=replay test", "-c", "user.email=replay@test.invalid",
            "commit", "-q", "-a", "-m", "replay test: one guard changed", cwd=worktree)
        return git("rev-parse", "HEAD", cwd=worktree)
    finally:
        git("worktree", "remove", "--force", str(worktree))


FIXTURE_PAIRS = [
    ["ls -la", "/tmp"],
    ["tmux kill-server", "/tmp"],
    ["git status && echo done", "/tmp"],
    ["cat <<'EOF'\ncase x in x) :;; esac\nEOF", "/tmp"],
]


def run_replay(head_ref, scratch, *extra):
    pairs_file = Path(scratch) / "fixture-pairs.json"
    pairs_file.write_text(json.dumps(FIXTURE_PAIRS))
    printed, errors = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(printed), contextlib.redirect_stderr(errors):
        status = replay.main(["--repository", str(REPOSITORY_ROOT), "--base-ref", "HEAD", "--head-ref", head_ref,
                              "--pairs-file", str(pairs_file), "--jobs", "2",
                              "--scratch-directory", str(Path(scratch) / f"run-{len(os.listdir(scratch))}"),
                              *extra])
    return status, printed.getvalue(), errors.getvalue()


with tempfile.TemporaryDirectory(prefix="bash-guards-replay-test-") as scratch:
    status, out, err = run_replay("HEAD", scratch)
    check("the same commit at base and head: exit 0 and no verdict changed",
          status == 0 and "NO VERDICT CHANGED" in out, f"status {status}\n{out}\n{err}")
    check("the same commit: in-process, search-file main() and new-process modes each ran",
          all(f"{mode}: rows whose verdict differs: 0" in out
              for mode in ("in-process", "search-file main()", "new-process")), out)
    check("the same commit: the new-process subset holds only the heredoc command",
          "new-process pairs: 1" in out, out)
    check("the same commit: new-process mode reads through a new process at both refs, in-process mode does not",
          all(f"new-process, {label}: 1 rows" in out and f"new-process, {label}: 1 rows" in out
              for label in ("base", "head"))
          and out.count("shell readers in a new process: 5") == 2
          and out.count("shell readers in a new process: 0") == 4, out)

    refusing_ls = commit_with_guard_changed(TMUX_KILL_GUARD, (
        "_refusal_for_as_written = refusal_for\n"
        "def refusal_for(command):\n"
        "    return 'refused by the test' if command == 'ls -la' else _refusal_for_as_written(command)"), scratch)
    status, out, err = run_replay(refusing_ls, scratch)
    check("a head whose tmux kill guard refuses `ls -la`: exit 1, the merge is blocked",
          status == 1 and "VERDICT CHANGED" in out, f"status {status}\n{out}\n{err}")
    check("a head whose tmux kill guard refuses `ls -la`: the difference names the guard and the command",
          "in-process: rows whose verdict differs: 1" in out and "tmux-kill: 1" in out and "'ls -la'" in out
          and "base: ['passed', None]" in out, out)
    check("a head whose tmux kill guard refuses `ls -la`: the differences file holds the row",
          any(json.loads(path.read_text())["verdict"]
              for path in Path(scratch).glob("run-*/differences-in-process.json")), "no differences file holds it")

    reworded = commit_with_guard_changed(TMUX_KILL_GUARD, (
        "_refusal_for_as_written = refusal_for\n"
        "def refusal_for(command):\n"
        "    reason = _refusal_for_as_written(command)\n"
        "    return 'Reworded: ' + reason if reason else reason"), scratch)
    status, out, err = run_replay(reworded, scratch)
    check("a head that rewords a refusal only: exit 0, and the message difference is printed",
          status == 0 and "in-process: rows whose message differs and verdict does not: 1" in out
          and "Reworded: " in out, f"status {status}\n{out}\n{err}")

    main_refusing_all = commit_with_guard_changed(SEARCH_FILE_GUARD, (
        "def main(stdin=sys.stdin, clock=time.monotonic):\n"
        "    deny('refused by the test')\n"
        "    return 0"), scratch)
    status, out, err = run_replay(main_refusing_all, scratch)
    check("a head whose search-file main() refuses every command: exit 1, and only main()'s rows differ",
          status == 1 and "search-file main(): rows whose verdict differs: 4" in out
          and "in-process: rows whose verdict differs: 0" in out, f"status {status}\n{out}\n{err}")

    uncallable = commit_with_guard_changed(ISSUE_WRITE_GUARD, "del analyze_command_text", scratch)
    status, out, err = run_replay(uncallable, scratch)
    check("a head whose guard lacks the function the replay calls: exit 2, the replay failed",
          status == 2 and "REPLAY FAILED" in err and "ghi-issue-write" in err, f"status {status}\n{out}\n{err}")

    status, out, err = run_replay("no-such-ref-for-the-replay-test", scratch)
    check("a ref that does not exist: exit 2, the replay failed",
          status == 2 and "REPLAY FAILED" in err, f"status {status}\n{err}")

    guards, switched = replay.guards_loaded(REPOSITORY_ROOT, True)
    check("new-process mode switches the shell reader each guard loads",
          switched == 5 and all(guard.shell_reader._read_in_a_new_process for guard in guards.values()),
          {key: guard.shell_reader._read_in_a_new_process for key, guard in guards.items()})

    left_over = [line for line in git("worktree", "list").splitlines() if scratch in line]
    check("every checkout the replay made is removed", not left_over, left_over)

    transcripts = Path(scratch) / "transcripts" / "project"
    transcripts.mkdir(parents=True)
    bash_call = lambda command, cwd: json.dumps({"cwd": cwd, "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {"command": command}}]}})
    (transcripts / "a.jsonl").write_text("\n".join([
        bash_call("ls", "/a"),
        bash_call("ls", "/a"),
        bash_call("ls", "/b"),
        json.dumps({"cwd": "/a", "message": {"content": [
            {"type": "tool_use", "name": "Read", "input": {"command": "not a Bash call"}},
            {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}]}}),
        '{"Bash" this line is cut off',
    ]) + "\n")
    (transcripts / "notes.txt").write_text(bash_call("never read", "/c"))
    pairs = replay.recorded_command_pairs([str(Path(scratch) / "transcripts")])
    check("transcripts: distinct (command, working directory) pairs of Bash calls only, in order",
          pairs == [["ls", "/a"], ["ls", "/b"]], pairs)

    errors = io.StringIO()
    with contextlib.redirect_stderr(errors), contextlib.redirect_stdout(io.StringIO()):
        status = replay.main(["--head-ref", "HEAD", "--repository", str(REPOSITORY_ROOT),
                              "--transcript-directory", str(Path(scratch) / "missing"),
                              "--scratch-directory", str(Path(scratch) / "run-missing")])
    check("a transcript directory that does not exist: exit 2, the replay failed",
          status == 2 and "does not exist" in errors.getvalue(), f"status {status}\n{errors.getvalue()}")

if failures:
    print(f"{len(failures)} failed")
    sys.exit(1)
print("all passed")
