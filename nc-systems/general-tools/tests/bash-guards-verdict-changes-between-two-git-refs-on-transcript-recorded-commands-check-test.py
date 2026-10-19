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
import time
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = Path(__file__).resolve().parents[1] / "bash-guards-verdict-changes-between-two-git-refs-on-transcript-recorded-commands-check.py"
TMUX_KILL_GUARD = "nc-systems/general-tools/claude-code-tmux-kill-server-and-kill-session-missing-server-selection-refusal-hook.py"
ISSUE_WRITE_GUARD = ".claude/hooks/ghi-issue-write-redirect.py"
SEARCH_FILE_GUARD = "scripts/search-file-argument-read-as-option-guard-hook.py"
SHELL_READER = "nc-systems/general-tools/shell-command-tree-sitter-bash-reader-common.py"

spec = importlib.util.spec_from_file_location("bash_guards_replay", SCRIPT_PATH)
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)

# Every Bash hook loads the shell reader, so new-process mode switches one reader per hook.
BASH_HOOK_COUNT = len(replay.bash_hook_files(REPOSITORY_ROOT))

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def git(*arguments, cwd=None, check=True):
    cwd = TEST_REPOSITORY if cwd is None else cwd
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


def commit_with_reader_changed_in_its_long_running_child(code_on_ls, scratch):
    """Return a commit whose shell reader runs code_on_ls before replying to `ls -la`, only in a child that
    reads one request per line; the code goes before the reader's __main__ lines, which start that child's loop."""
    def insert(worktree):
        path = worktree / SHELL_READER
        text = path.read_text()
        at = text.index('if __name__ == "__main__"')
        path.write_text(text[:at] + (
            "_reply_as_written = _shell_command_read_request_to_reply\n"
            "def _shell_command_read_request_to_reply(request):\n"
            "    if (request['command'] == 'ls -la'\n"
            "            and sys.argv[1:] == [NEW_PROCESS_READ_ONE_REQUEST_PER_LINE_UNTIL_INPUT_CLOSES_FLAG]):\n"
            f"        {code_on_ls}\n"
            "    return _reply_as_written(request)\n\n\n") + text[at:])
    return commit_with_change(insert, scratch)


def failed_new_process_readings_and_rows_differing_from_in_process(run_scratch):
    """Return (the commands of the failed new-process readings, the commands other than `ls -la` whose
    new-process verdicts at the head differ from their in-process verdicts); (None, None) when the run wrote none."""
    if not (run_scratch / "differences-new-process.json").exists():
        return None, None
    failed = [entry[0][0] for entry in json.loads((run_scratch / "differences-new-process.json").read_text())["failed"]]
    in_process = json.loads((run_scratch / "verdicts-in-process-head.json").read_text())["rows"]
    new_process = json.loads((run_scratch / "verdicts-new-process-head.json").read_text())["rows"]
    differing = [pair[0] for pair, here, there in zip(FIXTURE_PAIRS, in_process, new_process)
                 if pair[0] != "ls -la" and {key: value[0] for key, value in here.items()}
                 != {key: value[0] for key, value in there.items()}]
    return failed, differing


def commit_with_guard_changed(guard_path, appended_code, scratch):
    def append(worktree):
        with open(worktree / guard_path, "a") as handle:
            handle.write("\n" + appended_code + "\n")
    return commit_with_change(append, scratch)


def scratch_directory_removal_failures(directory):
    """Remove directory and return one line per path that could not be removed."""
    import shutil
    could_not_remove = []
    shutil.rmtree(directory, onexc=lambda _, path, error: could_not_remove.append(f"{path}: {error}"))
    return could_not_remove


def check_scratch_directory_removed(directory, record=None):
    """Remove directory; a path that could not be removed fails the suite through record, check by default."""
    record = check if record is None else record
    could_not_remove = scratch_directory_removal_failures(directory)
    record("the scratch directory is removed after the run", not could_not_remove, "\n".join(could_not_remove))


def worktrees_registered_under(directory):
    # git lists resolved paths; on macOS the scratch directory is named through the /var symlink.
    resolved = os.path.realpath(directory)
    return [line.split(" ", 1)[1] for line in git("worktree", "list", "--porcelain").splitlines()
            if line.startswith("worktree ") and line.split(" ", 1)[1].startswith(resolved)]


FIXTURE_PAIRS = [
    ["ls -la", "/tmp"],
    ["tmux kill-server", "/tmp"],
    ["git status && echo done", "/tmp"],
    ["cat <<'EOF'\ncase x in x) :;; esac\nEOF", "/tmp"],
    ['codex exec -C /tmp/x "do the task"', "/tmp"],
]


def run_replay(head_ref, scratch, *extra, base_ref="HEAD", scratch_directory=True):
    pairs_file = Path(scratch) / "fixture-pairs.json"
    pairs_file.write_text(json.dumps(FIXTURE_PAIRS))
    arguments = ["--repository", str(TEST_REPOSITORY), "--base-ref", base_ref, "--head-ref", head_ref,
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
# The test's checkouts are registered in a clone of its own inside the scratch directory, never in the
# clone this checkout belongs to, whose worktree list other agent-seats and concurrent runs share; a run
# that is killed leaves its registrations in the scratch directory alone.
TEST_REPOSITORY = Path(scratch) / "repository"
try:
    git("clone", "--quiet", "--shared", "--no-checkout", str(REPOSITORY_ROOT), str(TEST_REPOSITORY), cwd=scratch)
    git("update-ref", "--no-deref", "HEAD", git("rev-parse", "HEAD", cwd=REPOSITORY_ROOT))
    status, out, err = run_replay("HEAD", scratch)
    check("the same commit at base and head: exit 0 and no verdict changed",
          status == 0 and "NO VERDICT CHANGED" in out, f"status {status}\n{out}\n{err}")
    check("the same commit: in-process, search-file main() and new-process modes each ran",
          all(f"{mode}: rows whose verdict differs: 0" in out
              for mode in ("in-process", "search-file main()", "new-process")), out)
    check("the same commit: no message differs, though the codex exec refusal names a file in each checkout",
          "in-process: rows whose message differs and verdict does not: 0" in out, out)
    check("a replay that returns puts back the SIGTERM handler its caller had",
          signal.getsignal(signal.SIGTERM) is stopped_by_sigterm, signal.getsignal(signal.SIGTERM))
    check("the same commit: new-process mode reads every pair by default",
          f"new-process pairs: {len(FIXTURE_PAIRS)}" in out, out)
    check("the same commit: new-process mode reads through a new process at both refs, in-process mode does not",
          all(f"new-process, {label}: {len(FIXTURE_PAIRS)} rows" in out for label in ("base", "head"))
          and out.count(f"shell readers in a new process: {BASH_HOOK_COUNT}") == 2
          and out.count("shell readers in a new process: 0") == 4, out)

    refusing_ls = commit_with_guard_changed(TMUX_KILL_GUARD, (
        "_refusal_for_as_written = refusal_for\n"
        "def refusal_for(command):\n"
        "    return 'refused by the test' if command == 'ls -la' else _refusal_for_as_written(command)"), scratch)
    status, out, err = run_replay(refusing_ls, scratch)
    check("a head whose tmux kill guard refuses `ls -la`: exit 1, the merge is blocked",
          status == 1 and "VERDICT CHANGED" in out, f"status {status}\n{out}\n{err}")
    check("a head whose tmux kill guard refuses `ls -la`: the difference names the guard and the command",
          "in-process: rows whose verdict differs: 1" in out and f"{TMUX_KILL_GUARD}: 1" in out and "'ls -la'" in out
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
          status == 1 and f"search-file main(): rows whose verdict differs: {len(FIXTURE_PAIRS)}" in out
          and "in-process: rows whose verdict differs: 0" in out, f"status {status}\n{out}\n{err}")
    check("a head whose search-file main() refuses every command: its rows read as refused, not let through",
          "head: [['refused', 0], 'refused by the test']" in out and "base: [['silent', 0], None]" in out, out)

    main_reworded = commit_with_guard_changed(SEARCH_FILE_GUARD, (
        "def main(stdin=sys.stdin, clock=time.monotonic):\n"
        "    if 'true' not in stdin.read():\n"
        "        deny('refused by the test, in other words')\n"
        "    return 0"), scratch)
    status, out, err = run_replay(main_reworded, scratch, base_ref=main_refusing_all)
    check("a head that rewords only search-file main()'s refusal: exit 0, and main()'s message difference is printed",
          status == 0 and f"search-file main(): rows whose message differs and verdict does not: {len(FIXTURE_PAIRS)}"
          in out and "in other words" in out, f"status {status}\n{out}\n{err}")

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
          and f"in-process, {TMUX_KILL_GUARD}: 2" in out and "EXCEPTION RuntimeError" in out
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
    check("the replay reads exactly the Bash hooks in this checkout's settings.json",
          set(replay.GUARDS) == replay.bash_hook_files(REPOSITORY_ROOT),
          set(replay.GUARDS) ^ replay.bash_hook_files(REPOSITORY_ROOT))
    check("a head with a Bash hook this replay does not read: exit 2, naming the hook",
          status == 2 and "scripts/a-sixth-bash-guard-hook.py" in err and "not replayed" in err,
          f"status {status}\n{out}\n{err}")

    main_hanging_on_true = commit_with_guard_changed(SEARCH_FILE_GUARD, (
        "_main_as_written = main\n"
        "def main(stdin=sys.stdin, clock=time.monotonic):\n"
        "    text = stdin.read()\n"
        "    if '\"true\"' in text:\n"
        "        time.sleep(30)\n"
        "    return _main_as_written(stdin=io.StringIO(text), clock=clock)\n"
        "import io"), scratch)
    status, out, err = run_replay(main_hanging_on_true, scratch, "--per-pair-timeout-seconds", "2",
                                  "--new-process-pairs", "none")
    check("a search-file main() that hangs on the check's own `true`: exit 2 within the per-pair timeout",
          status == 2 and "search-file main() guard" in err and "TIMEOUT" in err, f"status {status}\n{out}\n{err}")

    def drop_codex_hook(worktree):
        path = worktree / ".claude" / "settings.json"
        settings = json.loads(path.read_text())
        for entry in settings["hooks"]["PreToolUse"]:
            entry["hooks"] = [hook for hook in entry.get("hooks", [])
                              if "hand-typed-codex-exec-redirect-hook.py" not in hook.get("command", "")]
        path.write_text(json.dumps(settings, indent=2))
    fewer_hooks = commit_with_change(drop_codex_hook, scratch)
    status, out, err = run_replay(fewer_hooks, scratch)
    check("a head whose settings.json lacks a Bash hook the replay reads: exit 2, naming the hook",
          status == 2 and "replayed but not a Bash hook: ['scripts/hand-typed-codex-exec-redirect-hook.py']" in err,
          f"status {status}\n{out}\n{err}")

    def commit_without_guard(guard_path):
        """Return a commit made from HEAD that has neither the guard's file nor its hook, as a base before the guard."""
        def remove(worktree):
            path = worktree / ".claude" / "settings.json"
            settings = json.loads(path.read_text())
            for entry in settings["hooks"]["PreToolUse"]:
                entry["hooks"] = [hook for hook in entry.get("hooks", []) if guard_path not in hook.get("command", "")]
            path.write_text(json.dumps(settings, indent=2))
            (worktree / guard_path).unlink()
        return commit_with_change(remove, scratch)

    before_tmux_kill_guard = commit_without_guard(TMUX_KILL_GUARD)
    status, out, err = run_replay("HEAD", scratch, base_ref=before_tmux_kill_guard)
    check("a head that adds a guard refusing a recorded command: exit 1, the merge is blocked",
          status == 1 and "NEW GUARD REFUSES RECORDED COMMANDS" in out and "VERDICT CHANGED" not in out,
          f"status {status}\n{out}\n{err}")
    check("a head that adds a guard refusing a recorded command: the section names the guard, the count and the command",
          f"in-process: new guard {TMUX_KILL_GUARD} would refuse 1 recorded command\n  in /tmp\n"
          "    command: 'tmux kill-server'" in out
          and f"new-process: new guard {TMUX_KILL_GUARD} would refuse 1 recorded command" in out, out)
    check("a head that adds a guard: the guard is read at the head only, and the other guards are compared",
          f"guards the head adds, read at the head only: ['{TMUX_KILL_GUARD}']" in out
          and "in-process: rows whose verdict differs: 0" in out, out)

    before_issue_write_guard = commit_without_guard(ISSUE_WRITE_GUARD)
    status, out, err = run_replay("HEAD", scratch, base_ref=before_issue_write_guard)
    check("a head that adds a guard refusing no recorded command: exit 0, and no new-guard section",
          status == 0 and "NO VERDICT CHANGED" in out and "would refuse" not in out
          and f"guards the head adds, read at the head only: ['{ISSUE_WRITE_GUARD}']" in out,
          f"status {status}\n{out}\n{err}")

    uncallable = commit_with_guard_changed(ISSUE_WRITE_GUARD, "del analyze_command_text", scratch)
    status, out, err = run_replay(uncallable, scratch)
    check("a head whose guard lacks the function the replay calls: exit 2, the replay failed",
          status == 2 and "REPLAY FAILED" in err and ISSUE_WRITE_GUARD in err, f"status {status}\n{out}\n{err}")

    status, out, err = run_replay("no-such-ref-for-the-replay-test", scratch)
    check("a ref that does not exist: exit 2, the replay failed",
          status == 2 and "REPLAY FAILED" in err, f"status {status}\n{err}")

    errors = io.StringIO()
    with contextlib.redirect_stderr(errors), contextlib.redirect_stdout(io.StringIO()):
        status = replay.main(["--head-ref", "HEAD", "--repository", str(TEST_REPOSITORY),
                              "--pairs-file", str(Path(scratch) / "no-such-pairs-file.json"),
                              "--scratch-directory", str(Path(scratch) / "run-no-pairs-file")])
    check("a pairs file that does not exist: exit 2, not the verdict status 1",
          status == 2 and "REPLAY FAILED: FileNotFoundError" in errors.getvalue(), f"status {status}\n{errors.getvalue()}")
    check("a replay failure from an unforeseen error names the line that raised it",
          "raised at " in errors.getvalue() and "read_text()" in errors.getvalue(), errors.getvalue())
    check("the line that raised is named by its path from the repository root, so a reader can open it",
          f"raised at {SCRIPT_PATH.relative_to(REPOSITORY_ROOT)}:" in errors.getvalue(), errors.getvalue())

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

    guards, switched, _, _ = replay.guards_loaded(REPOSITORY_ROOT, True)
    check("new-process mode switches the shell reader each guard loads",
          switched == BASH_HOOK_COUNT and all(guard.shell_reader._read_in_a_new_process for guard in guards.values()),
          {key: guard.shell_reader._read_in_a_new_process for key, guard in guards.items()})

    killing_child_on_ls = commit_with_reader_changed_in_its_long_running_child(
        "import signal; os.kill(os.getpid(), signal.SIGKILL)", scratch)
    killed_child_scratch = Path(scratch) / "run-killed-child"
    status, out, err = run_replay(killing_child_on_ls, scratch, "--jobs", "1", "--scratch-directory",
                                  str(killed_child_scratch), base_ref=killing_child_on_ls)
    failed, differing = failed_new_process_readings_and_rows_differing_from_in_process(killed_child_scratch)
    check("a shell reader child killed while reading `ls -la`: exit 2, only that pair's readings fail, and a fresh "
          "child reads the pairs after it as the in-process mode does",
          status == 2 and "EXCEPTION ShellReaderLongRunningChildProcessDiedMidRequest" in out
          and failed and set(failed) == {"ls -la"} and not differing and "in-process, " not in out.split("REPLAY FAILED")[-1],
          f"status {status}; failed {failed}; differing {differing}\n{out}\n{err}")

    hanging_child_on_ls = commit_with_reader_changed_in_its_long_running_child("import time; time.sleep(60)", scratch)
    hung_child_scratch = Path(scratch) / "run-hung-child"
    started = time.monotonic()
    status, out, err = run_replay(hanging_child_on_ls, scratch, "--jobs", "1", "--per-pair-timeout-seconds", "2",
                                  "--scratch-directory", str(hung_child_scratch), base_ref=hanging_child_on_ls)
    failed, differing = failed_new_process_readings_and_rows_differing_from_in_process(hung_child_scratch)
    check("a shell reader child that hangs on `ls -la`: exit 2 by the per-pair timeout, only that pair's readings "
          "fail, and its late reply answers no later request",
          status == 2 and "TIMEOUT" in out and failed and set(failed) == {"ls -la"} and not differing
          and time.monotonic() - started < 120,
          f"status {status} after {time.monotonic() - started:.0f}s; failed {failed}; differing {differing}\n{out}\n{err}")

    def reader_without_the_long_running_child_flag(worktree):
        with open(worktree / SHELL_READER, "a") as handle:
            handle.write("\ndel NEW_PROCESS_READ_ONE_REQUEST_PER_LINE_UNTIL_INPUT_CLOSES_FLAG\n")
    older_reader = commit_with_change(reader_without_the_long_running_child_flag, scratch)
    status, out, err = run_replay("HEAD", scratch, base_ref=older_reader)
    check("a base ref whose shell reader predates the long-running child reads one command per process, "
          "with the same verdicts as the head's long-running child",
          status == 0 and "NO VERDICT CHANGED" in out
          and f"new-process, base: {len(FIXTURE_PAIRS)} rows" in out
          and f"of which one command per process: {BASH_HOOK_COUNT}" in out.split("new-process, head")[0]
          and "of which one command per process" not in out.split("new-process, head")[1],
          f"status {status}\n{out}\n{err}")

    # Each reply the reader sends crosses the long-running child's pipe and is decoded as a one-command
    # process's output is: a missing parser and a command the reader fails on reach the guard as each does today.
    failing_reader = Path(scratch) / "shell-reader-failing-on-two-commands.py"
    failing_reader.write_text(
        "import importlib.util, sys\n"
        f"spec = importlib.util.spec_from_file_location('r', {str(REPOSITORY_ROOT / SHELL_READER)!r})\n"
        "r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)\n"
        "read_as_written = r._simple_commands_read\n"
        "def read(command, markers):\n"
        "    if command == 'needs the parser':\n"
        "        raise r.ShellParserUnavailable('pip exited 1: no network')\n"
        "    if command == 'fails the reader':\n"
        "        raise ValueError('injected')\n"
        "    return read_as_written(command, markers)\n"
        "r._simple_commands_read = read\n"
        "if sys.argv[1:] == [r.NEW_PROCESS_READ_ONE_REQUEST_PER_LINE_UNTIL_INPUT_CLOSES_FLAG]:\n"
        "    r._read_one_request_per_line_until_input_closes()\n")
    reader_module_spec = importlib.util.spec_from_file_location("shell_reader_for_the_replay_test",
                                                                REPOSITORY_ROOT / SHELL_READER)
    reader_module = importlib.util.module_from_spec(reader_module_spec)
    reader_module_spec.loader.exec_module(reader_module)
    sender = replay.ShellReaderLongRunningChildProcessRequestSender(
        failing_reader, reader_module.NEW_PROCESS_READ_ONE_REQUEST_PER_LINE_UNTIL_INPUT_CLOSES_FLAG)
    reader_module._use_a_new_process(sender)
    replies = []
    try:
        for command in ("needs the parser", "fails the reader", "ls -la | head"):
            try:
                replies.append([list(found) for found in reader_module.simple_commands(command)])
            except reader_module.ShellParserUnavailable as error:
                replies.append((type(error).__name__, error.install_output))
        child_pid = sender.child.pid if sender.child else None
    finally:
        sender.close()
    check("a missing parser and a reader failure each cross the long-running child as one-command processes send "
          "them, and the same child then reads the next command",
          replies == [("ShellParserUnavailable", "pip exited 1: no network"),
                      ("ShellCommandUnreadable", "ValueError: injected"), [["ls", "-la"], ["head"]]]
          and child_pid is not None, replies)

    # A child that has exited between two requests cannot be written to; that request is a failed reading too.
    exiting_after_one_reply = Path(scratch) / "child-exiting-after-one-reply.py"
    exiting_after_one_reply.write_text("import sys\nsys.stdin.readline()\nprint('{}', flush=True)\n")
    sender = replay.ShellReaderLongRunningChildProcessRequestSender(exiting_after_one_reply, "--unused")
    outcomes = [sender(["unused"], input=b"{}").stdout]
    sender.child.wait()
    try:
        sender(["unused"], input=b"{}")
        outcomes.append("no exception")
    except replay.ShellReaderLongRunningChildProcessDiedMidRequest as error:
        outcomes.append(str(error))
    except Exception as error:
        outcomes.append(f"not a failed reading: {type(error).__name__}: {error}")
    finally:
        sender.close()
    check("a request to a child that has already exited: the reading fails, naming the child's reader file",
          outcomes[0] == b"{}\n" and "failed (" in outcomes[1] and str(exiting_after_one_reply) in outcomes[1],
          outcomes)

    # A child that exits partway through its reply leaves a line with no newline; decoded, the part would
    # reach the guard as the reader's own failure on the command, not as a lost reading.
    exiting_mid_reply = Path(scratch) / "child-exiting-mid-reply.py"
    exiting_mid_reply.write_text("import sys\nsys.stdin.readline()\nsys.stdout.write('{\"commands\"')\n")
    mid_reply_guards, _, mid_reply_senders, _ = replay.guards_loaded(REPOSITORY_ROOT, True)
    for sender in mid_reply_senders:
        sender.reader_path = str(exiting_mid_reply)
    alarm_handler = signal.signal(signal.SIGALRM, replay.raise_pair_timed_out)
    try:
        mid_reply_readings = replay.guard_readings(mid_reply_guards, "ls -la", "/", "/")
    finally:
        signal.signal(signal.SIGALRM, alarm_handler)
        for sender in mid_reply_senders:
            sender.close()
    lost = [reading for reading in mid_reply_readings.values()
            if reading[0] == "EXCEPTION ShellReaderLongRunningChildProcessDiedMidRequest"
            and "before it replied" in reading[1] and str(exiting_mid_reply) in reading[1]]
    check("a child that exits partway through its reply: the pair is a failed reading, the child lost mid-request",
          mid_reply_senders and lost and all(replay.is_failed_reading(reading[0]) for reading in lost)
          and not any(reading[0].startswith("EXCEPTION") and reading not in lost
                      for reading in mid_reply_readings.values()),
          mid_reply_readings)

    def exit_on_ls(worktree):
        with open(worktree / TMUX_KILL_GUARD, "a") as handle:
            handle.write("\n_refusal_for_as_written = refusal_for\n"
                         "def refusal_for(command):\n"
                         "    if command == 'ls -la':\n"
                         "        sys.exit('the test makes this guard exit')\n"
                         "    return _refusal_for_as_written(command)\n")
        with open(worktree / SEARCH_FILE_GUARD, "a") as handle:
            handle.write("\n_main_as_written = main\n"
                         "def main(stdin=sys.stdin, clock=time.monotonic):\n"
                         "    text = stdin.read()\n"
                         "    if 'ls -la' in text:\n"
                         "        sys.exit(3)\n"
                         "    return _main_as_written(stdin=io.StringIO(text), clock=clock)\n"
                         "import io\n")
    exiting_on_ls = commit_with_change(exit_on_ls, scratch)
    (Path(scratch) / "fixture-pairs.json").write_text(json.dumps(FIXTURE_PAIRS))
    try:
        exiting = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--repository", str(TEST_REPOSITORY), "--base-ref", exiting_on_ls,
             "--head-ref", exiting_on_ls, "--pairs-file", str(Path(scratch) / "fixture-pairs.json"), "--jobs", "2",
             "--new-process-pairs", "none", "--scratch-directory", str(Path(scratch) / "run-exiting")],
            capture_output=True, text=True, timeout=180)
        check("a guard and a main() that call sys.exit on a command: exit 2 with failed readings, not a hung pool",
              exiting.returncode == 2 and "EXCEPTION SystemExit" in exiting.stdout
              and f"in-process, {TMUX_KILL_GUARD}: 2" in exiting.stdout
              and "search-file main(), search-file main(): 2" in exiting.stdout,
              f"exit {exiting.returncode}\n{exiting.stdout}\n{exiting.stderr}")
    except subprocess.TimeoutExpired:
        check("a guard and a main() that call sys.exit on a command: exit 2 with failed readings, not a hung pool",
              False, "the replay was still running after 180 s")
        subprocess.run(["pkill", "-f", str(Path(scratch) / "run-exiting")])

    codex_guard, _, _, _ = replay.guards_loaded(REPOSITORY_ROOT, False)
    codex_path = "scripts/hand-typed-codex-exec-redirect-hook.py"
    check("the codex exec guard's reading refuses a hand-typed codex exec and passes ls",
          replay.GUARDS[codex_path](codex_guard[codex_path], 'codex exec -C /tmp/x "do the task"', "/", "/")[0] == "refused"
          and replay.GUARDS[codex_path](codex_guard[codex_path], "ls -la", "/", "/")[0] == "passed",
          replay.GUARDS[codex_path](codex_guard[codex_path], 'codex exec -C /tmp/x "do the task"', "/", "/"))

    markdown_path = ("nc-systems/general-tools/"
                     "claude-code-bash-git-push-of-markdown-change-citation-checks-reminder-hook.py")
    # The reading's stubbed git names this checkout, which holds both citation programs.
    replay.WORKER["checkout"] = str(REPOSITORY_ROOT)
    markdown_push = replay.GUARDS[markdown_path](codex_guard[markdown_path], "git push origin topic", "/", "/")
    markdown_ls = replay.GUARDS[markdown_path](codex_guard[markdown_path], "ls -la", "/", "/")
    check("the Markdown push reminder's reading adds context for a push and passes ls",
          markdown_push[0][0] == "added context" and "docs/changed-page.md" in markdown_push[1]
          and markdown_ls == [["passed", []], None],
          f"{markdown_push!r} {markdown_ls!r}")

    killed_on_ls = commit_with_guard_changed(TMUX_KILL_GUARD, (
        "_refusal_for_as_written = refusal_for\n"
        "def refusal_for(command):\n"
        "    if command == 'ls -la':\n"
        "        os.kill(os.getpid(), signal.SIGKILL)\n"
        "    return _refusal_for_as_written(command)\n"
        "import os, signal"), scratch)
    killed_scratch = Path(scratch) / "run-killed-worker"
    started = time.monotonic()
    try:
        killed = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--repository", str(TEST_REPOSITORY), "--base-ref", killed_on_ls,
             "--head-ref", killed_on_ls, "--pairs-file", str(Path(scratch) / "fixture-pairs.json"), "--jobs", "2",
             "--new-process-pairs", "none", "--scratch-directory", str(killed_scratch)],
            capture_output=True, text=True, timeout=180)
        still_running = subprocess.run(["pgrep", "-f", str(killed_scratch)], capture_output=True,
                                        text=True).stdout.split()
        check("a worker killed by SIGKILL: exit 2 within 180 s, naming the pairs not read, no process left",
              killed.returncode == 2 and "a worker reading at" in killed.stderr and "'ls -la'" in killed.stderr
              and not still_running and not worktrees_registered_under(killed_scratch),
              f"exit {killed.returncode} after {time.monotonic() - started:.0f}s; running {still_running}\n"
              f"{killed.stdout}\n{killed.stderr}")
    except subprocess.TimeoutExpired:
        check("a worker killed by SIGKILL: exit 2 within 180 s, naming the pairs not read, no process left",
              False, "the replay was still running after 180 s")
        subprocess.run(["pkill", "-f", str(killed_scratch)])

    slow_on_ls = commit_with_guard_changed(TMUX_KILL_GUARD, (
        "_refusal_for_as_written = refusal_for\n"
        "def refusal_for(command):\n"
        "    if command == 'ls -la':\n"
        "        open(os.environ.get('REPLAY_TEST_READY_FILE', os.devnull), 'w').close()\n"
        "        time.sleep(120)\n"
        "    return _refusal_for_as_written(command)\n"
        "import os, time"), scratch)
    for stop_signal in (signal.SIGTERM, signal.SIGHUP):
        stopped_scratch = Path(scratch) / f"run-stopped-by-{stop_signal.name}"
        (Path(scratch) / "fixture-pairs.json").write_text(json.dumps(FIXTURE_PAIRS))
        ready_file = Path(scratch) / f"ready-{stop_signal.name}"
        stopped = subprocess.Popen(
            [sys.executable, str(SCRIPT_PATH), "--repository", str(TEST_REPOSITORY), "--base-ref", slow_on_ls,
             "--head-ref", slow_on_ls, "--pairs-file", str(Path(scratch) / "fixture-pairs.json"), "--jobs", "2",
             "--per-pair-timeout-seconds", "300", "--scratch-directory", str(stopped_scratch)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True,
            env={**os.environ, "REPLAY_TEST_READY_FILE": str(ready_file)})
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline and not ready_file.exists():  # A pool worker is inside the slow reading.
            time.sleep(0.5)
        stopped.send_signal(stop_signal)
        try:
            stopped_output = stopped.communicate(timeout=60)[0]
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(stopped.pid, signal.SIGKILL)
            stopped_output = stopped.communicate()[0]
            check(f"a replay stopped by {stop_signal.name} in the middle of a step exits within 60 s", False,
                  f"still running 60 s after the signal (ready file present: {ready_file.exists()}); "
                  f"its process group was killed\n{stopped_output}")
            continue
        still_running = subprocess.run(["pgrep", "-f", str(stopped_scratch)], capture_output=True, text=True).stdout.split()
        check(f"a replay stopped by {stop_signal.name} in the middle of a step: exit 2, its checkouts removed, "
              f"no process left",
              stopped.returncode == 2 and not worktrees_registered_under(stopped_scratch) and not still_running,
              f"exit {stopped.returncode}; registered {worktrees_registered_under(stopped_scratch)}; "
              f"running {still_running}\n{stopped_output}")

    # SystemExit raised by the stop handler between Popen._wait()'s lock acquire and its try used to leave
    # the lock held, so the next wait() on that process blocked forever. The signal is delivered at exactly
    # that point, in a child process so a hang is a timeout and not a stuck test.
    gap_script = (
        "import importlib.util, os, signal, subprocess, sys\n"
        "spec = importlib.util.spec_from_file_location('replay', sys.argv[1])\n"
        "replay = importlib.util.module_from_spec(spec); spec.loader.exec_module(replay)\n"
        "signal.signal(signal.SIGHUP, replay.raise_terminated)\n"
        "fired = []\n"
        "def profiler(frame, event, arg):\n"
        "    if (event == 'c_return' and not fired and frame.f_code is subprocess.Popen._wait.__code__\n"
        "            and getattr(arg, '__name__', '') == 'acquire'):\n"
        "        fired.append(1)\n"
        "        signal.raise_signal(signal.SIGHUP)\n"
        "replay.__file__ = sys.argv[2]\n"
        "sys.setprofile(profiler)\n"
        "try:\n"
        "    if sys.argv[3] == 'step':\n"
        "        replay.run_step_in_child(['--step', 'stand-in'], os.devnull, 600)\n"
        "    else:\n"
        "        replay.run_git(sys.argv[4], 'rev-parse', 'HEAD')\n"
        "except SystemExit as stop:\n"
        "    sys.setprofile(None)\n"
        "    print('exit', stop.code, 'signal delivered', bool(fired))\n"
    )
    gap_directory = Path(scratch) / "gap"
    gap_directory.mkdir()
    (gap_directory / "stand-in-step.py").write_text("import time\ntime.sleep(1000)\n")
    for gap_call, gap_extra in (("step", []), ("git", [str(REPOSITORY_ROOT)])):
        try:
            gap = subprocess.run([sys.executable, "-c", gap_script, str(SCRIPT_PATH),
                                  str(gap_directory / "stand-in-step.py"), gap_call.split()[0], *gap_extra],
                                 capture_output=True, text=True, timeout=30)
            gap_detail = f"exit {gap.returncode}\n{gap.stdout}{gap.stderr}"
            gap_ok = gap.returncode == 0 and "exit 2 signal delivered True" in gap.stdout
        except subprocess.TimeoutExpired:
            gap_ok, gap_detail = False, f"the {gap_call} call was still waiting 30 s after a stop signal landed in Popen._wait()"
            subprocess.run(["pkill", "-f", str(gap_directory / "stand-in-step.py")])
        check(f"a stop signal landing inside subprocess's wait during the {gap_call} call does not hang: exit 2",
              gap_ok, gap_detail)

    step_deadline_as_written = replay.step_deadline_seconds
    replay.step_deadline_seconds = lambda pair_count, jobs, timeout: 10
    started = time.monotonic()
    try:
        status, out, err = run_replay(slow_on_ls, scratch, "--per-pair-timeout-seconds", "300",
                                      "--new-process-pairs", "none", base_ref=slow_on_ls)
    finally:
        replay.step_deadline_seconds = step_deadline_as_written
    still_running = subprocess.run(["pgrep", "-f", str(Path(scratch) / f"run-")], capture_output=True,
                                    text=True).stdout.split()
    check("a step that runs past its deadline: exit 2 within about the deadline, no process left",
          status == 2 and "ran past its deadline of 10 s" in err and time.monotonic() - started < 60
          and not still_running, f"status {status} after {time.monotonic() - started:.0f}s; running {still_running}\n{err}")

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
    shared_registrations = [line for line in git("worktree", "list", "--porcelain", cwd=REPOSITORY_ROOT).splitlines()
                            if line.startswith("worktree ") and os.path.realpath(scratch) in line]
    check("a checkout the test made is registered in the test's own clone, not in the clone this checkout belongs to",
          worktrees_registered_under(locked) and not shared_registrations,
          f"own clone {worktrees_registered_under(locked)}; shared clone {shared_registrations}")
    not_removed = replay.remove_checkouts(str(TEST_REPOSITORY), [locked])
    git("worktree", "unlock", str(locked))
    check("a checkout git cannot remove is reported, with git's reason",
          len(not_removed) == 1 and str(locked) in not_removed[0] and "exited" in not_removed[0], not_removed)

    # macOS names its temporary directories through the /var -> /private/var symlink, and git lists checkouts by
    # their resolved paths; a symlink to the scratch directory reproduces that on Linux.
    through_symlink = Path(scratch) / "scratch-through-a-symlink"
    through_symlink.symlink_to(scratch)
    locked_through_symlink = through_symlink / "locked-checkout-named-through-a-symlink"
    git("worktree", "add", "--detach", str(locked_through_symlink), "HEAD")
    git("worktree", "lock", str(locked_through_symlink))
    not_removed = replay.remove_checkouts(str(TEST_REPOSITORY), [locked_through_symlink])
    git("worktree", "unlock", str(locked_through_symlink))
    check("a checkout named through a symlink that git cannot remove is reported, with git's reason",
          len(not_removed) == 1 and str(locked_through_symlink) in not_removed[0] and "exited" in not_removed[0],
          not_removed)
    removed_through_symlink = through_symlink / "checkout-named-through-a-symlink"
    git("worktree", "add", "--detach", str(removed_through_symlink), "HEAD")
    not_removed = replay.remove_checkouts(str(TEST_REPOSITORY), [removed_through_symlink])
    check("a checkout named through a symlink is removed and left registered with git nowhere",
          not_removed == [] and not worktrees_registered_under(removed_through_symlink),
          f"{not_removed}; registered {worktrees_registered_under(scratch)}")

    hanging_git = Path(scratch) / "hanging-git"
    hanging_git.mkdir()
    (hanging_git / "git").write_text("#!/bin/sh\nsleep 60\n")
    (hanging_git / "git").chmod(0o755)
    path_as_set, timeout_as_set = os.environ["PATH"], replay.GIT_TIMEOUT_SECONDS
    os.environ["PATH"], replay.GIT_TIMEOUT_SECONDS = f"{hanging_git}:{path_as_set}", 2
    started = time.monotonic()
    try:
        status, out, err = run_replay("HEAD", scratch)
    finally:
        os.environ["PATH"], replay.GIT_TIMEOUT_SECONDS = path_as_set, timeout_as_set
    check("a git call that hangs: exit 2 after the git timeout",
          status == 2 and "did not finish in 2 s" in err and time.monotonic() - started < 30,
          f"status {status} after {time.monotonic() - started:.0f}s\n{err}")

    never_added = Path(scratch) / "never-added-checkout"
    check("a checkout whose add never started is no removal failure",
          replay.remove_checkouts(str(TEST_REPOSITORY), [never_added]) == [], never_added)

    run_git_as_written = replay.run_git
    def run_git_stopped_after_the_add(repository, *arguments):
        result = run_git_as_written(repository, *arguments)
        if arguments[:2] == ("worktree", "add"):
            raise SystemExit(2)  # As raise_terminated() does when SIGTERM lands while git is adding.
        return result
    replay.run_git = run_git_stopped_after_the_add
    try:
        status, out, err = run_replay("HEAD", scratch)
    except SystemExit as stop:
        status = stop.code
    finally:
        replay.run_git = run_git_as_written
    check("a replay stopped during `git worktree add` removes the checkout that add made",
          status == 2 and not worktrees_registered_under(Path(scratch) / "run-"),
          worktrees_registered_under(Path(scratch) / "run-"))

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
        status = replay.main(["--head-ref", "HEAD", "--repository", str(TEST_REPOSITORY),
                              "--transcript-directory", str(Path(scratch) / "missing"),
                              "--scratch-directory", str(Path(scratch) / "run-missing")])
    check("a transcript directory that does not exist: exit 2, the replay failed",
          status == 2 and "does not exist" in errors.getvalue(), f"status {status}\n{errors.getvalue()}")

    killpg_as_written = os.killpg
    def killpg_as_on_macos(process_group, signal_number):
        # A step's workers outlive it as orphans; Linux reaps them at once, so the group is empty by the time
        # the replay signals it, but macOS may still hold them unreaped and then answers EPERM. Linux is made
        # to answer as macOS does whenever no process in the group is still running.
        members = []
        for stat in Path("/proc").glob("[0-9]*/stat"):
            with contextlib.suppress(OSError):
                fields = stat.read_text().rsplit(")", 1)[1].split()
                if int(fields[2]) == process_group:
                    members.append(fields[0])
        if all(state == "Z" for state in members):
            raise PermissionError(1, "Operation not permitted")
        return killpg_as_written(process_group, signal_number)
    replay.os.killpg = killpg_as_on_macos
    try:
        status, out, err = run_replay("HEAD", scratch, "--new-process-pairs", "none")
    finally:
        replay.os.killpg = killpg_as_written
    check("a step whose process group macOS will not signal once it has exited: exit 0, not a replay failure",
          status == 0 and "NO VERDICT CHANGED" in out, f"status {status}\n{out}\n{err}")

    unremovable = Path(scratch) / "unremovable"
    (unremovable / "locked").mkdir(parents=True)
    (unremovable / "locked" / "file").write_text("x")
    (unremovable / "locked").chmod(0o500)
    try:
        could_not_remove = scratch_directory_removal_failures(unremovable)
    finally:
        (unremovable / "locked").chmod(0o700)
    check("a scratch directory that cannot be removed is reported, naming the path",
          could_not_remove and str(unremovable / "locked" / "file") in could_not_remove[0], could_not_remove)

    left_behind = Path(scratch) / "left-behind"
    (left_behind / "locked").mkdir(parents=True)
    (left_behind / "locked" / "file").write_text("x")
    (left_behind / "locked").chmod(0o500)
    recorded = []
    try:
        check_scratch_directory_removed(left_behind, lambda *outcome: recorded.append(outcome))
    finally:
        (left_behind / "locked").chmod(0o700)
    check("the end-of-run cleanup fails the suite when the scratch directory cannot be removed, naming the path",
          len(recorded) == 1 and recorded[0][1] is False and str(left_behind / "locked" / "file") in recorded[0][2],
          recorded)
finally:
    # The test's checkouts are registered only in its own clone, which goes with the scratch directory.
    check_scratch_directory_removed(scratch)

if failures:
    print(f"{len(failures)} failed")
    sys.exit(1)
print("all passed")
