#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/bash-guards-verdict-changes-between-two-git-refs-on-transcript-recorded-commands-check.py.

Replays a small fixture of commands, never the real transcripts, at this checkout's HEAD and at
commits made for the test from HEAD with one guard changed: a changed verdict exits 1, a changed
message alone exits 0, and every way the replay can fail to get a verdict exits 2.

Run: python3 nc-systems/general-tools/tests/bash-guards-verdict-changes-between-two-git-refs-on-transcript-recorded-commands-check-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import importlib.util
import io
import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = Path(__file__).resolve().parents[1] / "bash-guards-verdict-changes-between-two-git-refs-on-transcript-recorded-commands-check.py"
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


def git(*arguments, cwd=REPOSITORY_ROOT, check=True):
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    completed = subprocess.run(["git", *arguments], cwd=cwd, capture_output=True, text=True, env=environment)
    if check and completed.returncode != 0:
        raise RuntimeError(f"git {arguments} exited {completed.returncode}: {completed.stderr}")
    return completed.stdout.strip()


def commit_with_change(change, scratch):
    """Return a commit made from HEAD with change(worktree) applied; HEAD itself is untouched."""
    worktree = Path(scratch) / f"changed-{len(os.listdir(scratch))}"
    git("worktree", "add", "--detach", str(worktree), "HEAD")
    try:
        change(worktree)
        git("-c", "core.hooksPath=/dev/null", "-c", "user.name=replay test", "-c", "user.email=replay@test.invalid",
            "commit", "-q", "-a", "-m", "replay test: one guard changed", cwd=worktree)
        return git("rev-parse", "HEAD", cwd=worktree)
    finally:
        git("worktree", "remove", "--force", str(worktree))


def commit_with_guard_changed(guard_path, appended_code, scratch):
    def append(worktree):
        with open(worktree / guard_path, "a") as handle:
            handle.write("\n" + appended_code + "\n")
    return commit_with_change(append, scratch)


def worktrees_registered_under(directory):
    return [line.split(" ", 1)[1] for line in git("worktree", "list", "--porcelain").splitlines()
            if line.startswith("worktree ") and line.split(" ", 1)[1].startswith(str(directory))]


FIXTURE_PAIRS = [
    ["ls -la", "/tmp"],
    ["tmux kill-server", "/tmp"],
    ["git status && echo done", "/tmp"],
    ["cat <<'EOF'\ncase x in x) :;; esac\nEOF", "/tmp"],
]


def run_replay(head_ref, scratch, *extra, base_ref="HEAD", scratch_directory=True):
    pairs_file = Path(scratch) / "fixture-pairs.json"
    pairs_file.write_text(json.dumps(FIXTURE_PAIRS))
    arguments = ["--repository", str(REPOSITORY_ROOT), "--base-ref", base_ref, "--head-ref", head_ref,
                 "--pairs-file", str(pairs_file), "--jobs", "2"]
    if scratch_directory:
        arguments += ["--scratch-directory", str(Path(scratch) / f"run-{len(os.listdir(scratch))}")]
    printed, errors = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(printed), contextlib.redirect_stderr(errors):
        status = replay.main(arguments + list(extra))
    return status, printed.getvalue(), errors.getvalue()


def stopped_by_sigterm(*_):
    raise SystemExit(1)  # So the temporary directory and its worktrees are removed below.


signal.signal(signal.SIGTERM, stopped_by_sigterm)
scratch = tempfile.mkdtemp(prefix="bash-guards-replay-test-")
try:
    status, out, err = run_replay("HEAD", scratch)
    check("the same commit at base and head: exit 0 and no verdict changed",
          status == 0 and "NO VERDICT CHANGED" in out, f"status {status}\n{out}\n{err}")
    check("the same commit: in-process, search-file main() and new-process modes each ran",
          all(f"{mode}: rows whose verdict differs: 0" in out
              for mode in ("in-process", "search-file main()", "new-process")), out)
    check("the same commit: the new-process subset holds only the heredoc command",
          "new-process pairs: 1" in out, out)
    check("the same commit: new-process mode reads through a new process at both refs, in-process mode does not",
          all(f"new-process, {label}: 1 rows" in out for label in ("base", "head"))
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
        "    return reason + ' Reworded at the end.' if reason else reason"), scratch)
    status, out, err = run_replay(reworded, scratch)
    check("a head that rewords the end of a refusal only: exit 0, and the message difference is printed",
          status == 0 and "in-process: rows whose message differs and verdict does not: 1" in out
          and "Reworded at the end." in out, f"status {status}\n{out}\n{err}")

    main_refusing_all = commit_with_guard_changed(SEARCH_FILE_GUARD, (
        "def main(stdin=sys.stdin, clock=time.monotonic):\n"
        "    if 'true' not in stdin.read():\n"
        "        deny('refused by the test')\n"
        "    return 0"), scratch)
    status, out, err = run_replay(main_refusing_all, scratch)
    check("a head whose search-file main() refuses every command: exit 1, and only main()'s rows differ",
          status == 1 and "search-file main(): rows whose verdict differs: 4" in out
          and "in-process: rows whose verdict differs: 0" in out, f"status {status}\n{out}\n{err}")
    check("a head whose search-file main() refuses every command: its rows read as refused, not let through",
          "head: ['refused', 0]" in out and "base: ['silent', 0]" in out, out)

    def raise_on_ls(worktree):
        with open(worktree / TMUX_KILL_GUARD, "a") as handle:
            handle.write("\n_refusal_for_as_written = refusal_for\n"
                         "def refusal_for(command):\n"
                         "    if command == 'ls -la':\n"
                         "        raise RuntimeError('the test makes this guard fail')\n"
                         "    return _refusal_for_as_written(command)\n")
        with open(worktree / SEARCH_FILE_GUARD, "a") as handle:
            handle.write("\n_main_as_written = main\n"
                         "def main(stdin=sys.stdin, clock=time.monotonic):\n"
                         "    text = stdin.read()\n"
                         "    if 'ls -la' in text:\n"
                         "        raise RuntimeError('the test makes main() fail')\n"
                         "    return _main_as_written(stdin=io.StringIO(text), clock=clock)\n"
                         "import io\n")
    raising_on_ls = commit_with_change(raise_on_ls, scratch)
    status, out, err = run_replay(raising_on_ls, scratch, base_ref=raising_on_ls)
    check("a guard that raises on a command at both refs: exit 2, the reading has no verdict",
          status == 2 and "REPLAY FAILED: readings that raised or timed out" in out
          and "in-process, tmux-kill: 2" in out and "EXCEPTION RuntimeError" in out
          and "NO VERDICT CHANGED" not in out, f"status {status}\n{out}\n{err}")
    check("a search-file main() that raises on a command at both refs: its rows are failed readings too",
          "search-file main(), search-file main(): 2" in out, out)

    swallowing_timeout = commit_with_guard_changed(SEARCH_FILE_GUARD, (
        "_first_refused_search_as_written = first_refused_search\n"
        "def first_refused_search(command, *rest):\n"
        "    if command == 'ls -la':\n"
        "        try:\n"
        "            time.sleep(10)\n"
        "        except Exception:\n"
        "            return None\n"
        "    return _first_refused_search_as_written(command, *rest)"), scratch)
    status, out, err = run_replay(swallowing_timeout, scratch, "--per-pair-timeout-seconds", "1",
                                  "--new-process-pairs", "none",
                                  base_ref=swallowing_timeout)
    check("a guard whose own `except Exception` surrounds a timed-out read: exit 2, the timeout is not swallowed",
          status == 2 and "TIMEOUT" in out and "NO VERDICT CHANGED" not in out, f"status {status}\n{out}\n{err}")

    def add_bash_hook(worktree):
        path = worktree / ".claude" / "settings.json"
        settings = json.loads(path.read_text())
        settings["hooks"]["PreToolUse"].append({"matcher": "Bash", "hooks": [
            {"type": "command", "command": 'python3 "$CLAUDE_PROJECT_DIR"/scripts/a-sixth-bash-guard-hook.py'}]})
        path.write_text(json.dumps(settings, indent=2))
    sixth_hook = commit_with_change(add_bash_hook, scratch)
    status, out, err = run_replay(sixth_hook, scratch)
    check("a head with a Bash hook this replay does not read: exit 2, naming the hook",
          status == 2 and "scripts/a-sixth-bash-guard-hook.py" in err and "not replayed" in err,
          f"status {status}\n{out}\n{err}")

    uncallable = commit_with_guard_changed(ISSUE_WRITE_GUARD, "del analyze_command_text", scratch)
    status, out, err = run_replay(uncallable, scratch)
    check("a head whose guard lacks the function the replay calls: exit 2, the replay failed",
          status == 2 and "REPLAY FAILED" in err and "ghi-issue-write" in err, f"status {status}\n{out}\n{err}")

    status, out, err = run_replay("no-such-ref-for-the-replay-test", scratch)
    check("a ref that does not exist: exit 2, the replay failed",
          status == 2 and "REPLAY FAILED" in err, f"status {status}\n{err}")

    errors = io.StringIO()
    with contextlib.redirect_stderr(errors), contextlib.redirect_stdout(io.StringIO()):
        status = replay.main(["--head-ref", "HEAD", "--repository", str(REPOSITORY_ROOT),
                              "--pairs-file", str(Path(scratch) / "no-such-pairs-file.json"),
                              "--scratch-directory", str(Path(scratch) / "run-no-pairs-file")])
    check("a pairs file that does not exist: exit 2, not the verdict status 1",
          status == 2 and "REPLAY FAILED: FileNotFoundError" in errors.getvalue(), f"status {status}\n{errors.getvalue()}")

    remove_checkouts_as_written = replay.remove_checkouts
    replay.remove_checkouts = lambda repository, checkouts: (
        remove_checkouts_as_written(repository, checkouts) + ["a checkout: git worktree remove exited 128: the test"])
    try:
        status, out, err = run_replay("HEAD", scratch)
    finally:
        replay.remove_checkouts = remove_checkouts_as_written
    check("a run whose checkouts cannot all be removed: exit 2, and the checkout is named",
          status == 2 and "could not be removed" in out and "a checkout: git worktree remove exited 128" in out,
          f"status {status}\n{out}\n{err}")

    guards, switched = replay.guards_loaded(REPOSITORY_ROOT, True)
    check("new-process mode switches the shell reader each guard loads",
          switched == 5 and all(guard.shell_reader._read_in_a_new_process for guard in guards.values()),
          {key: guard.shell_reader._read_in_a_new_process for key, guard in guards.items()})

    left_over = worktrees_registered_under(Path(scratch) / "run-")
    check("every checkout the replay made is removed", not left_over, left_over)

    previous_tempdir = tempfile.tempdir
    tempfile.tempdir = str(Path(scratch) / "temporary")
    Path(tempfile.tempdir).mkdir()
    try:
        status, out, err = run_replay("HEAD", scratch, scratch_directory=False)
    finally:
        tempfile.tempdir = previous_tempdir
    check("a default scratch directory is removed after an exit 0",
          status == 0 and "scratch directory removed" in out and not os.listdir(Path(scratch) / "temporary"),
          f"status {status}\n{out}\n{os.listdir(Path(scratch) / 'temporary')}")

    previous_directory = os.getcwd()
    os.chdir(scratch)
    try:
        status, out, err = run_replay("HEAD", scratch, "--scratch-directory", "relative-run", scratch_directory=False)
    finally:
        os.chdir(previous_directory)
    check("a relative --scratch-directory is resolved once, against the directory the replay runs in",
          status == 0 and (Path(scratch) / "relative-run" / "pairs.json").exists()
          and f"scratch directory: {Path(scratch).resolve() / 'relative-run'}" in out, f"status {status}\n{out}\n{err}")

    locked = Path(scratch) / "locked-checkout"
    git("worktree", "add", "--detach", str(locked), "HEAD")
    git("worktree", "lock", str(locked))
    not_removed = replay.remove_checkouts(str(REPOSITORY_ROOT), [locked])
    git("worktree", "unlock", str(locked))
    check("a checkout git cannot remove is reported, with git's reason",
          len(not_removed) == 1 and str(locked) in not_removed[0] and "exited" in not_removed[0], not_removed)

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
    pairs, lines_not_json = replay.recorded_command_pairs([str(Path(scratch) / "transcripts")])
    check("transcripts: distinct (command, working directory) pairs of Bash calls only, in order",
          pairs == [["ls", "/a"], ["ls", "/b"]], pairs)
    check("transcripts: a line that is not JSON is counted, not dropped silently", lines_not_json == 1, lines_not_json)

    unreadable = transcripts / "unreadable.jsonl"
    unreadable.write_text(bash_call("ls", "/d"))
    unreadable.chmod(0)
    try:
        replay.recorded_command_pairs([str(Path(scratch) / "transcripts")])
        check("an unreadable transcript fails the replay", False, "no ReplayFailed")
    except replay.ReplayFailed as error:
        check("an unreadable transcript fails the replay", "unreadable.jsonl" in str(error), error)
    finally:
        unreadable.chmod(0o600)
        unreadable.unlink()

    unlistable = transcripts / "unlistable"
    unlistable.mkdir()
    unlistable.chmod(0)
    try:
        replay.recorded_command_pairs([str(Path(scratch) / "transcripts")])
        check("a transcript directory that cannot be listed fails the replay", False, "no ReplayFailed")
    except replay.ReplayFailed as error:
        check("a transcript directory that cannot be listed fails the replay", "unlistable" in str(error), error)
    finally:
        unlistable.chmod(0o700)

    errors = io.StringIO()
    with contextlib.redirect_stderr(errors), contextlib.redirect_stdout(io.StringIO()):
        status = replay.main(["--head-ref", "HEAD", "--repository", str(REPOSITORY_ROOT),
                              "--transcript-directory", str(Path(scratch) / "missing"),
                              "--scratch-directory", str(Path(scratch) / "run-missing")])
    check("a transcript directory that does not exist: exit 2, the replay failed",
          status == 2 and "does not exist" in errors.getvalue(), f"status {status}\n{errors.getvalue()}")
finally:
    # Removes the worktrees a run left registered when it was stopped, or when a mutant of its cleanup ran.
    for worktree in worktrees_registered_under(scratch):
        git("worktree", "remove", "--force", "--force", worktree, check=False)
    import shutil
    shutil.rmtree(scratch, ignore_errors=True)
    git("worktree", "prune", check=False)

if failures:
    print(f"{len(failures)} failed")
    sys.exit(1)
print("all passed")
