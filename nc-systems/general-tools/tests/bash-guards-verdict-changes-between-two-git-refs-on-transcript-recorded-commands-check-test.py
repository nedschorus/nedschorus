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
import re
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = Path(__file__).resolve().parents[1] / "bash-guards-verdict-changes-between-two-git-refs-on-transcript-recorded-commands-check.py"
TMUX_KILL_GUARD = "nc-systems/general-tools/claude-code-tmux-kill-server-and-kill-session-missing-server-selection-refusal-hook.py"
ISSUE_WRITE_GUARD = ".claude/hooks/ghi-issue-write-hand-typed-gh-command-refusal.py"
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


def readings_read_again_that_all_got_a_verdict(err, step):
    """Return how many readings step read again, when its read-again line says all got a verdict; else None.

    Under load a reading besides the one a case makes time out can time out too, so a case asks for at least one."""
    found = re.search(rf"^{re.escape(step)}: (\d+) readings? timed out", err, re.MULTILINE)
    count = int(found.group(1)) if found else None
    return count if count and replay.timed_out_readings_read_again_line(step, count, count) in err else None


def commit_with_one_command_per_process_reader_changed(code_on_ls, scratch):
    """Return a commit whose shell reader has no long-running child flag, so each guard reads one command per
    process, and whose one-command process runs code_on_ls before replying to `ls -la`. The code goes before the
    reader's __main__ lines, which start that process's reading; the flag is deleted after them, which name it."""
    def change(worktree):
        path = worktree / SHELL_READER
        text = path.read_text()
        at = text.index('if __name__ == "__main__"')
        path.write_text(text[:at] + (
            "_reply_as_written = _shell_command_read_request_to_reply\n"
            "def _shell_command_read_request_to_reply(request):\n"
            "    if request['command'] == 'ls -la' and sys.argv[1:] == [NEW_PROCESS_READ_FLAG]:\n"
            f"        {code_on_ls}\n"
            "    return _reply_as_written(request)\n\n\n") + text[at:]
            + "\ndel NEW_PROCESS_READ_ONE_REQUEST_PER_LINE_UNTIL_INPUT_CLOSES_FLAG\n")
    return commit_with_change(change, scratch)


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


def log_store_runs_directory(scratch):
    """The directory the suite passes as --log-store-runs-directory, so no replay writes into the log-store;
    made on first use."""
    directory = Path(scratch) / "log-store-runs"
    directory.mkdir(exist_ok=True)
    return directory


def default_scratch_replay(head_ref, scratch, *extra, base_ref="HEAD", pairs=FIXTURE_PAIRS):
    """run_replay() without --scratch-directory, its temporary directory in a new directory of the suite's scratch
    and its run log directory in another; return (status, out, err, what the temporary directory holds after the
    replay, the run log directories after the replay)."""
    temporary = Path(tempfile.mkdtemp(prefix="temporary-", dir=scratch))
    runs = Path(tempfile.mkdtemp(prefix="log-store-runs-", dir=scratch))
    previous_tempdir = tempfile.tempdir
    tempfile.tempdir = str(temporary)
    try:
        status, out, err = run_replay(head_ref, scratch, "--log-store-runs-directory", str(runs), *extra,
                                      base_ref=base_ref, scratch_directory=False, pairs=pairs)
    finally:
        tempfile.tempdir = previous_tempdir
    return status, out, err, sorted(os.listdir(temporary)), sorted(runs.iterdir())


def run_replay(head_ref, scratch, *extra, base_ref="HEAD", scratch_directory=True, pairs=FIXTURE_PAIRS):
    pairs_file = Path(scratch) / "fixture-pairs.json"
    pairs_file.write_text(json.dumps(pairs))
    arguments = ["--repository", str(TEST_REPOSITORY), "--base-ref", base_ref, "--head-ref", head_ref,
                 "--pairs-file", str(pairs_file), "--jobs", "2",
                 "--log-store-runs-directory", str(log_store_runs_directory(scratch))]
    if scratch_directory:
        arguments += ["--scratch-directory", str(Path(scratch) / f"run-{len(os.listdir(scratch))}")]
    printed, errors = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(printed), contextlib.redirect_stderr(errors):
        status = replay.main(arguments + list(extra))
    return status, printed.getvalue(), errors.getvalue()


def run_replay_within(deadline_seconds, head_ref, scratch, *extra, base_ref="HEAD", pairs=FIXTURE_PAIRS):
    """run_replay() in a process of its own, stopped by this process after deadline_seconds.

    The deadline is kept from outside, so a replay that hangs, whatever hangs it, fails its case and does not
    stop the suite. On expiry
    the replay gets SIGTERM, which makes it stop its steps and remove its checkouts, then SIGKILL if it is
    still running; the status returned is then None.
    """
    pairs_file = Path(scratch) / "fixture-pairs.json"
    pairs_file.write_text(json.dumps(pairs))
    arguments = ["--repository", str(TEST_REPOSITORY), "--base-ref", base_ref, "--head-ref", head_ref,
                 "--pairs-file", str(pairs_file), "--jobs", "2",
                 "--log-store-runs-directory", str(log_store_runs_directory(scratch)), *extra]
    process = subprocess.Popen([sys.executable, str(SCRIPT_PATH), *arguments], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True)
    try:
        out, err = process.communicate(timeout=deadline_seconds)
        return process.returncode, out, err
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            out, err = process.communicate(timeout=REPLAY_STOP_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()
            out, err = process.communicate()
        return None, out, err + f"\nthe replay ran past this test's deadline of {deadline_seconds} s"


def signal_in_popen_wait_lock_gap_script(signal_name, handler_name):
    """Return the start of a script that loads the replay from its first argument, handles signal_name with the
    replay's handler_name, and defines profiler, which, once sys.setprofile() installs it, delivers that signal
    once, just after Popen._wait() acquires its lock and before its try, and records the delivery in fired."""
    return (
        "import importlib.util, os, signal, subprocess, sys\n"
        "spec = importlib.util.spec_from_file_location('replay', sys.argv[1])\n"
        "replay = importlib.util.module_from_spec(spec); spec.loader.exec_module(replay)\n"
        f"signal.signal(signal.{signal_name}, replay.{handler_name})\n"
        "fired = []\n"
        "def profiler(frame, event, arg):\n"
        "    if (event == 'c_return' and not fired and frame.f_code is subprocess.Popen._wait.__code__\n"
        "            and getattr(arg, '__name__', '') == 'acquire'):\n"
        "        fired.append(1)\n"
        f"        signal.raise_signal(signal.{signal_name})\n"
    )



# Defines run_then_record_return(), which makes a subprocess.run() call and then prints "subprocess.run returned".
# Its globals are subprocess's, so the per-pair timeout handler, which defers while a frame with those globals
# runs, cannot fire between the return and the print and drop the print from a correct run on a loaded machine.
SUBPROCESS_RUN_THEN_RECORD_RETURN = (
    "exec(" + repr(
        "def run_then_record_return(*arguments, **options):\n"
        "    run(*arguments, **options)\n"
        "    sys.stdout.write('subprocess.run returned\\n')\n"
        "    sys.stdout.flush()\n") + ", vars(subprocess))\n"
    "run_then_record_return = subprocess.run_then_record_return\n")

# A guard's code that times its reading out at once, as the replay's per-pair timer firing there would, but only
# while the replay has that timer set; unset, the reading goes on and the case fails. A wall-clock hang would
# need a per-pair timeout short enough that a loaded machine also times out the readings meant to pass.
PER_PAIR_TIMEOUT_DELIVERED_WHILE_ARMED = (
    "    import signal\n"
    "    if signal.getitimer(signal.ITIMER_REAL)[0] > 0:\n"
    "        signal.raise_signal(signal.SIGALRM)\n")
PER_PAIR_TIMEOUT_LOAD_CANNOT_REACH = "600"


def stopped_by_sigterm(*_):
    raise SystemExit(1)  # So the temporary directory and its worktrees are removed below.


# The hung-child case takes about 23 s on an idle machine: one 20 s timeout, then the reading again. A sender
# that kept the hung child would time out each later pair on that guard and each reading again, at least
# 9 more timeouts (180 s), so this deadline fails it by name with room for a loaded machine's slower readings.
HUNG_CHILD_CASE_DEADLINE_SECONDS = 150
# Long enough for a stopped replay to stop its steps and remove its checkouts.
REPLAY_STOP_SECONDS = 60
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

    codex_guard = "scripts/hand-typed-codex-exec-command-refusal-hook.py"
    calls_file = Path(scratch) / "codex-guard-calls-on-tmux-kill-server"

    def codex_guard_on_tmux_kill_server(code_on_tmux_kill_server):
        # Not the first fixture pair, so the retry pass must look past a row that did not time out.
        # Each call appends to calls_file first, so a test can count the readings across worker processes.
        return commit_with_guard_changed(codex_guard, (
            "_refusal_for_command_as_written = refusal_for_command\n"
            "def refusal_for_command(command):\n"
            "    import time\n"
            "    if command == 'tmux kill-server':\n"
            f"        with open({str(calls_file)!r}, 'a') as calls:\n"
            "            calls.write('call\\n')\n"
            + "".join(f"        {line}\n" for line in code_on_tmux_kill_server.splitlines())
            + "    return _refusal_for_command_as_written(command)"), scratch)

    def codex_guard_calls_on_tmux_kill_server():
        calls = len(calls_file.read_text().splitlines()) if calls_file.exists() else 0
        calls_file.unlink(missing_ok=True)
        return calls

    hanging_once_on_tmux_kill_server = codex_guard_on_tmux_kill_server(
        f"if len(open({str(calls_file)!r}).readlines()) == 1:\n" + PER_PAIR_TIMEOUT_DELIVERED_WHILE_ARMED)
    status, out, err = run_replay(hanging_once_on_tmux_kill_server, scratch, "--per-pair-timeout-seconds",
                                  PER_PAIR_TIMEOUT_LOAD_CANNOT_REACH, "--new-process-pairs", "none")
    calls = codex_guard_calls_on_tmux_kill_server()
    check("a guard that times out on its first reading of a pair and answers on the second: read again alone, exit 0",
          status == 0 and "NO VERDICT CHANGED" in out and calls == 2
          and readings_read_again_that_all_got_a_verdict(err, "in-process, head"),
          f"status {status}; calls {calls}\n{out}\n{err}")

    hanging_on_tmux_kill_server = codex_guard_on_tmux_kill_server("time.sleep(30)")
    status, out, err = run_replay(hanging_on_tmux_kill_server, scratch, "--per-pair-timeout-seconds", "2",
                                  "--new-process-pairs", "none")
    calls = codex_guard_calls_on_tmux_kill_server()
    check("a guard that times out on both readings of a pair: a failed reading, exit 2",
          status == 2 and "TIMEOUT" in out and calls == 2
          and re.search(r"^in-process, head: \d+ readings? timed out and w[a-z]+ read again", err, re.MULTILINE),
          f"status {status}; calls {calls}\n{out}\n{err}")

    raising_on_tmux_kill_server = codex_guard_on_tmux_kill_server(
        "raise RuntimeError('the guard broke on tmux kill-server')")
    status, out, err = run_replay(raising_on_tmux_kill_server, scratch, "--new-process-pairs", "none")
    calls = codex_guard_calls_on_tmux_kill_server()
    check("a guard that raises on a pair: not read again, exit 2",
          status == 2 and "EXCEPTION RuntimeError" in out and calls == 1,
          f"status {status}; calls {calls}\n{out}\n{err}")

    read_again_lines = {
        ("new-process, base", 5, 2):
            "new-process, base: 5 readings timed out and were read again after the step's other readings had "
            "finished (a reading is one Bash guard's verdict, to allow or to refuse, on one recorded command); 2 "
            "got a verdict the second time and 3 did not; those count as failed readings, and this replay will "
            "exit 2 when it finishes.",
        ("new-process, base", 3, 2):
            "new-process, base: 3 readings timed out and were read again after the step's other readings had "
            "finished (a reading is one Bash guard's verdict, to allow or to refuse, on one recorded command); 2 "
            "got a verdict the second time and 1 did not; that one counts as a failed reading, and this replay "
            "will exit 2 when it finishes.",
        ("in-process, head", 3, 0):
            "in-process, head: 3 readings timed out and were read again after the step's other readings had "
            "finished (a reading is one Bash guard's verdict, to allow or to refuse, on one recorded command); "
            "none got a verdict the second time, so they count as failed readings, and this replay will exit 2 "
            "when it finishes.",
        ("in-process, head", 2, 2):
            "in-process, head: 2 readings timed out and were read again after the step's other readings had "
            "finished (a reading is one Bash guard's verdict, to allow or to refuse, on one recorded command); "
            "all got a verdict the second time.",
        ("in-process, head", 1, 0):
            "in-process, head: 1 reading timed out and was read again after the step's other readings had "
            "finished (a reading is one Bash guard's verdict, to allow or to refuse, on one recorded command); "
            "it did not get a verdict the second time either, so it counts as a failed reading, and this replay "
            "will exit 2 when it finishes.",
        ("search-file main(), head", 1, 1):
            "search-file main(), head: 1 reading timed out and was read again after the step's other readings "
            "had finished (a reading is one Bash guard's verdict, to allow or to refuse, on one recorded "
            "command); it got a verdict the second time.",
    }
    for arguments, expected in read_again_lines.items():
        check(f"the read-again line for {arguments[1]} read again, {arguments[2]} with a verdict, says so in words",
              replay.timed_out_readings_read_again_line(*arguments) == expected,
              replay.timed_out_readings_read_again_line(*arguments))
    check("the step deadline covers every reading timing out in the parallel pass and again alone",
          replay.step_deadline_seconds(9, 3, 7)
          == (3 + 9) * (len(replay.GUARDS) + 1) * 7 + replay.STEP_DEADLINE_MARGIN_SECONDS,
          replay.step_deadline_seconds(9, 3, 7))

    class GhiMdGuardNaming:
        def __init__(self, replaced):
            self.replaced = replaced

        def ghi_md_replaced_by_command(self, command, working_directory):
            return self.replaced

    for replaced, expected in (("/c/docs/issues/46-a.md", ("refused", "replaces /c/docs/issues/46-a.md")),
                               (None, ("passed", None))):
        reading = replay.read_ghi_md_whole_file_replacement(GhiMdGuardNaming(replaced), "cp a b", "/c", None)
        check(f"the GHI-MD soft-block's reading when its guard names {replaced}", reading == expected, reading)

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

    # A search-file main() row is one reading, not a dict of them, so the retry pass stores it back by itself.
    main_hang_once_marker = Path(scratch) / "search-file-main-hung-on-ls"
    main_hanging_once_on_ls = commit_with_guard_changed(SEARCH_FILE_GUARD, (
        "_main_as_written = main\n"
        "def main(stdin=sys.stdin, clock=time.monotonic):\n"
        "    text = stdin.read()\n"
        f"    if '\"ls -la\"' in text and not os.path.exists({str(main_hang_once_marker)!r}):\n"
        f"        open({str(main_hang_once_marker)!r}, 'x').close()\n"
        + "".join(f"    {line}\n" for line in PER_PAIR_TIMEOUT_DELIVERED_WHILE_ARMED.splitlines()) +
        "    return _main_as_written(stdin=io.StringIO(text), clock=clock)\n"
        "import io, os"), scratch)
    main_hung_once_scratch = Path(scratch) / "run-search-file-main-hung-once"
    status, out, err = run_replay(main_hanging_once_on_ls, scratch, "--per-pair-timeout-seconds",
                                  PER_PAIR_TIMEOUT_LOAD_CANNOT_REACH, "--new-process-pairs", "none",
                                  "--scratch-directory", str(main_hung_once_scratch))
    main_rows = json.loads((main_hung_once_scratch / "verdicts-search-file-head.json").read_text())["rows"] \
        if (main_hung_once_scratch / "verdicts-search-file-head.json").exists() else None
    check("a search-file main() that times out on its first reading of `ls -la` and answers on the second: "
          "the row keeps the second reading, exit 0",
          status == 0 and "NO VERDICT CHANGED" in out and main_hang_once_marker.exists()
          and readings_read_again_that_all_got_a_verdict(err, "search-file main(), head")
          and main_rows is not None and main_rows[0][0] != "TIMEOUT",
          f"status {status}; rows {main_rows}\n{out}\n{err}")

    def drop_codex_hook(worktree):
        path = worktree / ".claude" / "settings.json"
        settings = json.loads(path.read_text())
        for entry in settings["hooks"]["PreToolUse"]:
            entry["hooks"] = [hook for hook in entry.get("hooks", [])
                              if "hand-typed-codex-exec-command-refusal-hook.py" not in hook.get("command", "")]
        path.write_text(json.dumps(settings, indent=2))
    fewer_hooks = commit_with_change(drop_codex_hook, scratch)
    status, out, err = run_replay(fewer_hooks, scratch)
    check("a head whose settings.json lacks a Bash hook the replay reads: exit 2, naming the hook",
          status == 2 and "replayed but not a Bash hook: ['scripts/hand-typed-codex-exec-command-refusal-hook.py']" in err,
          f"status {status}\n{out}\n{err}")

    # In the guard's own directory, so the files it loads beside itself are still found.
    former_tmux_kill_guard = str(Path(TMUX_KILL_GUARD).with_name("tmux-kill-guard-at-a-former-path-hook.py"))

    def move_tmux_kill_guard_to_its_former_path(worktree):
        git("mv", TMUX_KILL_GUARD, former_tmux_kill_guard, cwd=worktree)
        path = worktree / ".claude" / "settings.json"
        path.write_text(path.read_text().replace(TMUX_KILL_GUARD, former_tmux_kill_guard))
    before_rename = commit_with_change(move_tmux_kill_guard_to_its_former_path, scratch)
    status, out, err = run_replay("HEAD", scratch, base_ref=before_rename)
    check("a head that renames a guard whose former path the replay does not know: exit 2, naming the former path "
          "and the map that takes it",
          status == 2 and "at the base ref" in err and f"not replayed: ['{former_tmux_kill_guard}']" in err
          and "BASH_GUARD_CURRENT_PATHS_BY_FORMER_PATH" in err, f"status {status}\n{out}\n{err}")
    renames_as_written = getattr(replay, "BASH_GUARD_CURRENT_PATHS_BY_FORMER_PATH", {})
    replay.BASH_GUARD_CURRENT_PATHS_BY_FORMER_PATH = {former_tmux_kill_guard: TMUX_KILL_GUARD}
    try:
        status, out, err = run_replay("HEAD", scratch, base_ref=before_rename)
        check("a head that only renames a guard whose former path the replay knows: exit 0, and the renamed guard "
              "is not a guard the head adds",
              status == 0 and "NO VERDICT CHANGED" in out
              and "guards the head adds, read at the head only: none" in out, f"status {status}\n{out}\n{err}")
        status, out, err = run_replay(refusing_ls, scratch, base_ref=before_rename)
        check("a head that renames a guard and changes its verdict: exit 1, the difference named by the guard's "
              "current path",
              status == 1 and "in-process: rows whose verdict differs: 1" in out and f"  {TMUX_KILL_GUARD}: 1" in out
              and "base: ['passed', None]" in out and "NEW GUARD REFUSES RECORDED COMMANDS" not in out,
              f"status {status}\n{out}\n{err}")
    finally:
        replay.BASH_GUARD_CURRENT_PATHS_BY_FORMER_PATH = renames_as_written

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
    check("a head that adds a guard refusing a recorded command: the section names the guard, the count, the command "
          "and its working directory",
          f"in-process: new guard {TMUX_KILL_GUARD} would refuse 1 recorded command, listed with its "
          "working directory\n  1. command: 'tmux kill-server'\n     working directory: /tmp\n" in out
          and f"new-process: new guard {TMUX_KILL_GUARD} would refuse 1 recorded command" in out, out)
    check("a head that adds a guard refusing a recorded command, and changes no verdict: merge-lane-2 may merge "
          "once each refusal is accepted",
          replay.NEW_GUARD_REFUSES_ONLY_ENDING in out
          and replay.NEW_GUARD_REFUSES_AND_VERDICT_CHANGED_ENDING not in out, out)

    status, out, err = run_replay(main_refusing_all, scratch, "--new-process-pairs", "none",
                                  base_ref=before_tmux_kill_guard)
    check("a head that adds a refusing guard and changes another guard's verdicts: exit 1, both blocks printed",
          status == 1 and "NEW GUARD REFUSES RECORDED COMMANDS" in out
          and "\nVERDICT CHANGED: a recorded command gets a different verdict" in out,
          f"status {status}\n{out}\n{err}")
    check("a head that adds a refusing guard and changes another guard's verdicts: accepting the refusals does not "
          "clear the verdict change, and the merge waits for both kinds of answer",
          replay.NEW_GUARD_REFUSES_AND_VERDICT_CHANGED_ENDING in out
          and replay.NEW_GUARD_REFUSES_ONLY_ENDING not in out
          and "\"refusal right\" lines do not clear it" in out
          and "every difference has its \"verdict change intended\" line" in out, out)
    check("a head that changes a guard's verdicts: the reviewer is told the answer line to write for each difference",
          replay.VERDICT_CHANGED_MESSAGE in out
          and "  verdict change intended: <guard> | <working directory> | <command>\n" in out, out)
    check("a head that adds a guard: the guard is read at the head only, and the other guards are compared",
          f"guards the head adds, read at the head only: ['{TMUX_KILL_GUARD}']" in out
          and "in-process: rows whose verdict differs: 0" in out, out)

    # Longer than the 300 characters a printed reading is cut to, and different from its twin only at the end.
    long_refused = ["tmux kill-server; echo " + "x" * 320 + " first", "/tmp"]
    long_refused_twin = ["tmux kill-server; echo " + "x" * 320 + " second", "/tmp"]
    status, out, err = run_replay("HEAD", scratch, "--new-process-pairs", "none", base_ref=before_tmux_kill_guard,
                                  pairs=[long_refused, long_refused_twin])
    check("a head that adds a guard refusing two long commands that differ only at the end: each is listed in full",
          status == 1 and f"would refuse 2 recorded commands" in out
          and f"command: {long_refused[0]!r}\n" in out and f"command: {long_refused_twin[0]!r}\n" in out,
          f"status {status}\n{out}\n{err}")

    before_search_file_guard = commit_without_guard(SEARCH_FILE_GUARD)
    status, out, err = run_replay(main_refusing_all, scratch, "--new-process-pairs", "none",
                                  base_ref=before_search_file_guard)
    check("a head that adds the search-file guard, whose main() refuses every command: exit 1, and main()'s "
          "refusals are the added guard's, not verdict changes",
          status == 1 and f"guards the head adds, read at the head only: ['{SEARCH_FILE_GUARD}']" in out
          and f"search-file main(): new guard {SEARCH_FILE_GUARD} would refuse {len(FIXTURE_PAIRS)} recorded "
          "commands" in out
          and "NEW GUARD REFUSES RECORDED COMMANDS" in out and "VERDICT CHANGED" not in out
          and "search-file main(), base" not in out, f"status {status}\n{out}\n{err}")

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

    # The first child to read `ls -la` hangs for good, so only the per-pair timeout ends that reading,
    # and a sender that kept the hung child would hang the readings after it too, each then counted as
    # read again. Hanging once keeps the case to one timeout, which can then be the replay's default of
    # 20 s: a reading takes well under a second on an idle machine and several seconds on a loaded one,
    # at the workers' nice 15. The timed-out reading is read again, by a fresh child, and passes.
    hang_once_marker = Path(scratch) / "a-child-hung-on-ls"
    hanging_child_on_ls = commit_with_reader_changed_in_its_long_running_child(
        f"if not os.path.exists({str(hang_once_marker)!r}): open({str(hang_once_marker)!r}, 'x').close(); "
        "time.sleep(10 ** 6)", scratch)
    hung_child_scratch = Path(scratch) / "run-hung-child"
    status, out, err = run_replay_within(HUNG_CHILD_CASE_DEADLINE_SECONDS, hanging_child_on_ls, scratch, "--jobs", "1",
                                         "--scratch-directory", str(hung_child_scratch), base_ref=hanging_child_on_ls)
    failed, differing = failed_new_process_readings_and_rows_differing_from_in_process(hung_child_scratch)
    check("a shell reader child that hangs on `ls -la`: the per-pair timeout ends that one reading, which passes "
          "when read again, exit 0, and the hung child answers no later request",
          status == 0 and "NO VERDICT CHANGED" in out and failed == [] and not differing and hang_once_marker.exists()
          and readings_read_again_that_all_got_a_verdict(err, "new-process, base"),
          f"status {status}; failed {failed}; differing {differing}\n{out}\n{err}")

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

    # The first one-command process to read `ls -la` hangs, so the reader's own subprocess timeout ends it, and
    # the guard raises ShellCommandUnreadable from subprocess.TimeoutExpired: a timed-out reading, read again.
    reader_hang_once_marker = Path(scratch) / "a-one-command-reader-hung-on-ls"
    reader_hanging_once_on_ls = commit_with_one_command_per_process_reader_changed(
        f"if not os.path.exists({str(reader_hang_once_marker)!r}): open({str(reader_hang_once_marker)!r}, 'x').close(); "
        "time.sleep(10 ** 6)", scratch)
    reader_timed_out_scratch = Path(scratch) / "run-one-command-reader-timed-out"
    status, out, err = run_replay("HEAD", scratch, "--jobs", "1", "--scratch-directory", str(reader_timed_out_scratch),
                                  base_ref=reader_hanging_once_on_ls)
    failed, differing = failed_new_process_readings_and_rows_differing_from_in_process(reader_timed_out_scratch)
    check("a one-command-per-process shell reader that runs past its own timeout on `ls -la` once: a timed-out "
          "reading, which passes when read again, exit 0",
          status == 0 and "NO VERDICT CHANGED" in out and failed == [] and reader_hang_once_marker.exists()
          and readings_read_again_that_all_got_a_verdict(err, "new-process, base"),
          f"status {status}; failed {failed}\n{out}\n{err}")

    # Each one-command process that reads `ls -la` writes a line, so a reading read again writes a second.
    reader_failure_calls = Path(scratch) / "one-command-reader-failures-on-ls"
    reader_failing_on_ls = commit_with_one_command_per_process_reader_changed(
        f"open({str(reader_failure_calls)!r}, 'a').write('x\\n'); "
        "raise SystemExit('the one-command reader broke on ls -la')", scratch)
    reader_failed_scratch = Path(scratch) / "run-one-command-reader-failed"
    status, out, err = run_replay("HEAD", scratch, "--jobs", "1", "--scratch-directory", str(reader_failed_scratch),
                                  base_ref=reader_failing_on_ls)
    failed, _ = failed_new_process_readings_and_rows_differing_from_in_process(reader_failed_scratch)
    failed_on_ls = (failed or []).count("ls -la")
    calls = len(reader_failure_calls.read_text().splitlines()) if reader_failure_calls.exists() else 0
    check("a one-command-per-process shell reader that fails on `ls -la` other than by timing out: not read again, "
          "exit 2",
          status == 2 and "EXCEPTION ShellCommandUnreadable" in out and "the one-command reader broke on ls -la" in out
          and failed_on_ls > 0 and calls == failed_on_ls,
          f"status {status}; failed on ls -la {failed_on_ls}; reader calls {calls}\n{out}\n{err}")

    def raising(error, cause):
        def read(*_):
            raise error from cause
        return read

    timeout = subprocess.TimeoutExpired(["reader"], 8)
    injected = {"reader timed out": raising(ValueError("timed out after 8 seconds"), timeout),
                "reader failed": raising(ValueError("could not start"), OSError("no such file")),
                "uncaused": raising(ValueError("broke"), None)}
    guards_as_written = replay.GUARDS
    replay.GUARDS = injected
    try:
        readings = replay.guard_readings(dict.fromkeys(injected), "ls -la", "/tmp", "/tmp")
    finally:
        replay.GUARDS = guards_as_written
    check("a reading that raised from subprocess.TimeoutExpired is a timeout; one raised from another cause, or "
          "from none, is the exception",
          readings == {"reader timed out": ("TIMEOUT", "timed out after 8 seconds"),
                       "reader failed": ("EXCEPTION ValueError", "could not start"),
                       "uncaused": ("EXCEPTION ValueError", "broke")}, readings)

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
    codex_path = "scripts/hand-typed-codex-exec-command-refusal-hook.py"
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
    gap_script = signal_in_popen_wait_lock_gap_script("SIGHUP", "raise_terminated") + (
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

    # The same gap for the per-pair timeout: raised there, PairTimedOut left the lock held, and the wait() in
    # subprocess.run()'s exit blocked the reading forever. The real per-pair alarm is set past the case's
    # deadline, so a TIMEOUT can only come from the timeout delivered in the gap and tried again. The timeout
    # must wait until subprocess.run() returns: raised inside it, it too gives a TIMEOUT, with the lock held.
    pair_gap_script = signal_in_popen_wait_lock_gap_script("SIGALRM", "raise_pair_timed_out") + (
        SUBPROCESS_RUN_THEN_RECORD_RETURN +
        "import time\n"
        "def stand_in_reading(guard, command, working_directory, search_file_directory):\n"
        "    run_then_record_return([sys.executable, '-c', 'pass'], timeout=600)\n"
        "    time.sleep(1000)\n"
        "replay.GUARDS['stand-in guard'] = stand_in_reading\n"
        "replay.WORKER['timeout'] = 600\n"
        "sys.setprofile(profiler)\n"
        "readings = replay.guard_readings({'stand-in guard': None}, 'true', '/', '/')\n"
        "sys.setprofile(None)\n"
        "print(readings['stand-in guard'], 'signal delivered', bool(fired))\n"
    )
    try:
        pair_gap = subprocess.run([sys.executable, "-c", pair_gap_script, str(SCRIPT_PATH)],
                                  capture_output=True, text=True, timeout=30)
        pair_gap_detail = f"exit {pair_gap.returncode}\n{pair_gap.stdout}{pair_gap.stderr}"
        pair_gap_ok = (pair_gap.returncode == 0 and "subprocess.run returned" in pair_gap.stdout
                       and "('TIMEOUT', None) signal delivered True" in pair_gap.stdout)
    except subprocess.TimeoutExpired:
        pair_gap_ok = False
        pair_gap_detail = "the reading was still waiting 30 s after the per-pair timeout landed in Popen._wait()"
    check("a per-pair timeout landing inside subprocess's wait does not hang: the reading is a TIMEOUT",
          pair_gap_ok, pair_gap_detail)

    # A guard whose subprocess call outlasts the per-pair timeout and that answers as soon as the call returns
    # used to keep its verdict, unless the deferred timeout got in first: which one won was up to the load.
    # The child sleeps three times the 1 s timeout, so the timeout falls inside the call even on a loaded machine.
    late_answer_script = signal_in_popen_wait_lock_gap_script("SIGALRM", "raise_pair_timed_out") + (
        SUBPROCESS_RUN_THEN_RECORD_RETURN +
        "def stand_in_reading(guard, command, working_directory, search_file_directory):\n"
        "    run_then_record_return([sys.executable, '-c', 'import time; time.sleep(3)'], timeout=600)\n"
        "    return 'passed', None\n"
        "replay.GUARDS['stand-in guard'] = stand_in_reading\n"
        "replay.WORKER['timeout'] = 1\n"
        "print(replay.guard_readings({'stand-in guard': None}, 'true', '/', '/')['stand-in guard'])\n"
    )
    try:
        late_answer = subprocess.run([sys.executable, "-c", late_answer_script, str(SCRIPT_PATH)],
                                     capture_output=True, text=True, timeout=60)
        late_answer_detail = f"exit {late_answer.returncode}\n{late_answer.stdout}{late_answer.stderr}"
        late_answer_ok = (late_answer.returncode == 0 and "subprocess.run returned" in late_answer.stdout
                          and "('TIMEOUT', None)" in late_answer.stdout)
    except subprocess.TimeoutExpired:
        late_answer_ok, late_answer_detail = False, "the reading was still running 60 s after it started"
    check("a guard that answers as soon as a subprocess call outlasting the per-pair timeout returns: a TIMEOUT",
          late_answer_ok, late_answer_detail)

    # A worker reads many pairs in one process, so a timeout deferred in one reading must not time out the next.
    next_reading_script = signal_in_popen_wait_lock_gap_script("SIGALRM", "raise_pair_timed_out") + (
        "def late_reading(guard, command, working_directory, search_file_directory):\n"
        "    subprocess.run([sys.executable, '-c', 'import time; time.sleep(3)'], timeout=600)\n"
        "    return 'passed', None\n"
        "def prompt_reading(guard, command, working_directory, search_file_directory):\n"
        "    return 'passed', None\n"
        "replay.GUARDS['late guard'] = late_reading\n"
        "replay.GUARDS['prompt guard'] = prompt_reading\n"
        "replay.WORKER['timeout'] = 1\n"
        "print('first', replay.guard_readings({'late guard': None}, 'true', '/', '/')['late guard'])\n"
        "replay.WORKER['timeout'] = 600\n"
        "print('next', replay.guard_readings({'prompt guard': None}, 'true', '/', '/')['prompt guard'])\n"
    )
    try:
        next_reading = subprocess.run([sys.executable, "-c", next_reading_script, str(SCRIPT_PATH)],
                                      capture_output=True, text=True, timeout=60)
        next_reading_detail = f"exit {next_reading.returncode}\n{next_reading.stdout}{next_reading.stderr}"
        next_reading_lines = next_reading.stdout.splitlines()
    except subprocess.TimeoutExpired:
        next_reading_lines, next_reading_detail = [], "the readings were still running 60 s after they started"
    check("a reading after one whose timeout was deferred keeps its verdict",
          next_reading_lines == ["first ('TIMEOUT', None)", "next ('passed', None)"], next_reading_detail)

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
    check("a run log directory is removed after an exit 0",
          status == 0 and "run log directory removed" in out and not os.listdir(log_store_runs_directory(scratch)),
          f"status {status}\n{out}\n{os.listdir(log_store_runs_directory(scratch))}")

    status, out, err, left, runs = default_scratch_replay(refusing_ls, scratch)
    kept = sorted(path.name for path in runs[0].iterdir()) if len(runs) == 1 else None
    check("a default scratch directory is removed after an exit 1, and the run log directory is kept, holding the "
          "differences and the step logs but not the checkouts or the pairs",
          status == 1 and not left and "scratch directory removed" in out
          and f"run log directory kept: {runs[0] if runs else None}" in out
          and kept is not None and "differences-in-process.json" in kept and "verdicts-in-process-head.log" in kept
          and not any(name.startswith("checkout-") or name == "pairs.json" for name in kept),
          f"status {status}; left {left}; kept {kept}\n{out}\n{err}")
    check("the run log directory the replay prints first is the one the VERDICT CHANGED message sends the reviewer to",
          runs and out.splitlines()[0] == f"run log directory: {runs[0]}"
          and json.loads((runs[0] / "differences-in-process.json").read_text())["verdict"], out)

    status, out, err, left, runs = default_scratch_replay("no-such-ref-for-the-replay-test", scratch)
    check("a default scratch directory is removed when the replay fails partway, at a ref that does not exist",
          status == 2 and "REPLAY FAILED" in err and not left and len(runs) == 1,
          f"status {status}; left {left}; runs {runs}\n{out}\n{err}")

    not_json = Path(scratch) / "pairs-file-that-is-not-json.json"
    not_json.write_text("not JSON")
    status, out, err, left, runs = default_scratch_replay("HEAD", scratch, "--pairs-file", str(not_json))
    check("a default scratch directory is removed when the replay raises an unforeseen error before it reads a ref",
          status == 2 and "REPLAY FAILED: JSONDecodeError" in err and not left and len(runs) == 1,
          f"status {status}; left {left}; runs {runs}\n{out}\n{err}")

    status, out, err, left, runs = default_scratch_replay(
        "HEAD", scratch, "--log-store-runs-directory", str(Path(scratch) / "no-such-log-store" / "runs"))
    check("a run log directory that cannot be made: exit 2, the message says where to run the replay, and no "
          "scratch directory is made",
          status == 2 and "this Bash guards replay made no run log directory" in err
          and "run the replay again with --log-store-runs-directory <an existing directory>" in err and not left
          and not (Path(scratch) / "no-such-log-store").exists(), f"status {status}; left {left}\n{out}\n{err}")

    removal_failures_as_written = replay.remove_scratch_directory_and_after_exit_0_run_log_directory_returning_failures
    replay.remove_scratch_directory_and_after_exit_0_run_log_directory_returning_failures = lambda *arguments: (
        removal_failures_as_written(*arguments) + ["a path: could not be removed in the test"])
    try:
        status, out, err, left, runs = default_scratch_replay("HEAD", scratch)
    finally:
        replay.remove_scratch_directory_and_after_exit_0_run_log_directory_returning_failures = (
            removal_failures_as_written)
    check("a scratch directory that cannot be removed: exit 2, though no verdict changed, and the path is named "
          "with the command that removes it",
          status == 2 and "NO VERDICT CHANGED" in out and "could not be removed, so this Bash guards replay exits 2" in out
          and "Remove each listed path with rm -rf <path>" in out and "a path: could not be removed in the test" in out,
          f"status {status}\n{out}\n{err}")

    remove_checkouts_as_written = replay.remove_checkouts
    replay.remove_checkouts = lambda repository, checkouts: (
        remove_checkouts_as_written(repository, checkouts) + ["a checkout: git worktree remove exited 128: the test"])
    try:
        status, out, err, left, runs = default_scratch_replay("HEAD", scratch)
    finally:
        replay.remove_checkouts = remove_checkouts_as_written
    check("a default scratch directory is kept when a checkout in it could not be removed, so git's registration "
          "still has its files",
          status == 2 and len(left) == 1 and "scratch directory kept: " in out
          and "scratch directory removed" not in out,
          f"status {status}; left {left}\n{out}\n{err}")

    locked_scratch = Path(scratch) / "removal-failures-scratch"
    locked_run_logs = Path(scratch) / "removal-failures-run-logs"
    for directory in (locked_scratch, locked_run_logs):
        (directory / "locked").mkdir(parents=True)
        (directory / "locked" / "file").write_text("x")
        (directory / "locked").chmod(0o500)
    try:
        after_exit_1 = replay.remove_scratch_directory_and_after_exit_0_run_log_directory_returning_failures(
            locked_scratch, locked_run_logs, 1)
        after_exit_0 = replay.remove_scratch_directory_and_after_exit_0_run_log_directory_returning_failures(
            locked_scratch, locked_run_logs, 0)
    finally:
        for directory in (locked_scratch, locked_run_logs):
            (directory / "locked").chmod(0o700)
    check("a path that cannot be removed is returned with its reason: the scratch directory's after any exit, the "
          "run log directory's only after an exit 0",
          any(str(locked_scratch / "locked" / "file") in line for line in after_exit_1)
          and not any(str(locked_run_logs) in line for line in after_exit_1)
          and any(str(locked_scratch / "locked" / "file") in line for line in after_exit_0)
          and any(str(locked_run_logs / "locked" / "file") in line for line in after_exit_0),
          f"after exit 1 {after_exit_1}; after exit 0 {after_exit_0}")

    pairs_file = Path(scratch) / "fixture-pairs.json"
    pairs_file.write_text(json.dumps(FIXTURE_PAIRS))
    for stop_signal in (signal.SIGTERM, signal.SIGHUP):
        temporary = Path(tempfile.mkdtemp(prefix=f"temporary-{stop_signal.name}-", dir=scratch))
        runs = Path(tempfile.mkdtemp(prefix=f"log-store-runs-{stop_signal.name}-", dir=scratch))
        stopped = subprocess.Popen(
            [sys.executable, str(SCRIPT_PATH), "--repository", str(TEST_REPOSITORY), "--head-ref", "HEAD",
             "--base-ref", "HEAD", "--pairs-file", str(pairs_file), "--jobs", "2", "--log-store-runs-directory",
             str(runs)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=dict(os.environ, TMPDIR=str(temporary)))
        printed_before_the_stop = []
        for line in stopped.stdout:
            printed_before_the_stop.append(line)
            if line.startswith("pairs: "):
                break
        stopped.send_signal(stop_signal)
        try:
            out, err = stopped.communicate(timeout=REPLAY_STOP_SECONDS)
        except subprocess.TimeoutExpired:
            stopped.kill()
            out, err = stopped.communicate()
        check(f"a replay stopped by {stop_signal.name} after it made its scratch directory: exit 2, the scratch "
              f"directory is removed and the run log directory kept",
              stopped.returncode == 2 and not os.listdir(temporary) and len(os.listdir(runs)) == 1
              and "scratch directory removed" in out,
              f"exit {stopped.returncode}; left {os.listdir(temporary)}; runs {os.listdir(runs)}\n"
              f"{''.join(printed_before_the_stop)}{out}\n{err}")

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

check("the default transcript folders are this machine's and the three copies the mirror keeps on ned-box",
      replay.DEFAULT_TRANSCRIPT_DIRECTORIES == [
          str(Path.home() / ".claude" / "projects"),
          "/home/nedlern/nedschorus-logs/agent-session-files-by-machine/mac/projects",
          "/home/nedlern/nedschorus-logs/agent-session-files-by-machine/ned-box",
          "/home/nedlern/nedschorus-logs/agent-session-files-by-machine/recovered"],
      replay.DEFAULT_TRANSCRIPT_DIRECTORIES)

# A deleted entry passes this case; only a replay against a base that still runs the former path shows it.
renames_to_paths_not_in_guards = {former: current for former, current
                                  in replay.BASH_GUARD_CURRENT_PATHS_BY_FORMER_PATH.items() if current not in replay.GUARDS}
former_paths_still_in_guards = sorted(set(replay.BASH_GUARD_CURRENT_PATHS_BY_FORMER_PATH) & set(replay.GUARDS))
check("each renamed guard's former path maps to a path in GUARDS, and no former path is itself in GUARDS",
      not renames_to_paths_not_in_guards and not former_paths_still_in_guards,
      f"mapped to paths not in GUARDS: {renames_to_paths_not_in_guards}; former paths in GUARDS: "
      f"{former_paths_still_in_guards}")

if failures:
    print(f"{len(failures)} failed")
    sys.exit(1)
print("all passed")
