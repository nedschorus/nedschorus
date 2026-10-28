#!/usr/bin/env python3
"""Tests for handoff-supervisor-restart-onto-current-main-at-next-session-handoff-detached-from-its-agent-session.py.

The handoff-supervisor and the agent-session are real processes: a fake
handoff-supervisor.py, started with --agent <name>, whose child is a fake claude
started with --session-id <id>, whose own child is a helper process. Real
signals reach them, and real ps reads them. A git checkout with a bare origin
in a temporary directory stands for ~/Projects/nedschorus, and two stub
programs stand for resupervise-seat.py and recover-crashed-seats.py, recording
how they were run. The detached half runs in this process, except in the case
that tests the detaching itself in a child process. Every process a case starts
is ended when the case ends.

Run: python3 nc-systems/handoff/tests/handoff-supervisor-restart-onto-current-main-at-next-session-handoff-detached-from-its-agent-session-test.py

Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import importlib.util
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().parents[3] / "scripts"
    / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

PROGRAM_PATH = (Path(__file__).resolve().parents[1]
                / "handoff-supervisor-restart-onto-current-main-at-next-session-handoff-detached-from-its-agent-session.py")
_spec = importlib.util.spec_from_file_location("restart_program", PROGRAM_PATH)
restart = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(restart)

SESSION_ID = "11111111-2222-3333-4444-555555555555"
failures = []
CASES = []

FAKE_SUPERVISOR = textwrap.dedent("""\
    import os, subprocess, sys, time
    directory = os.environ["FAKE_DIRECTORY"]
    child = subprocess.Popen([sys.executable, os.path.join(directory, "claude"),
                              "--session-id", os.environ["FAKE_SESSION_ID"]])
    with open(os.path.join(directory, "claude.pid"), "w") as stream:
        stream.write(str(child.pid))
    while True:
        time.sleep(1)
""")

FAKE_CLAUDE = textwrap.dedent("""\
    import os, signal, subprocess, sys, time
    directory = os.environ["FAKE_DIRECTORY"]
    if os.environ.get("FAKE_CLAUDE_IGNORES_SIGTERM"):
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    helper = subprocess.Popen([sys.executable, "-c", "import time\\nwhile True: time.sleep(1)"])
    with open(os.path.join(directory, "helper.pid"), "w") as stream:
        stream.write(str(helper.pid))
    while True:
        time.sleep(1)
""")

STUB_RECOVERY_PROGRAM = textwrap.dedent("""\
    import json, os, sys
    from pathlib import Path
    name = Path(sys.argv[0]).name
    record = Path(os.environ["FAKE_DIRECTORY"]) / "recovery-calls.jsonl"
    with record.open("a") as stream:
        stream.write(json.dumps({"program": name, "argv": sys.argv[1:], "cwd": os.getcwd(),
                                 "tmux": os.environ.get("TMUX")}) + "\\n")
    print(f"{name} stub ran")
    sys.exit(int(os.environ.get("FAKE_EXIT_" + name.replace("-", "_").replace(".py", ""), "0")))
""")


def git(cwd, *arguments):
    completed = subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid",
         "-c", "core.hooksPath=/dev/null", "-c", "init.defaultBranch=main", *arguments],
        cwd=str(cwd), capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise AssertionError(f"git {' '.join(arguments)} failed: {completed.stderr}")
    return completed.stdout.strip()


def process_state(process_id):
    completed = subprocess.run(["ps", "-o", "stat=", "-p", str(process_id)],
                               capture_output=True, text=True, check=False)
    return completed.stdout.strip()


def wait_for_file(path: Path):
    for _ in range(200):
        if path.is_file() and path.read_text().strip():
            return path.read_text().strip()
        time.sleep(0.05)
    raise AssertionError(f"{path} never appeared")


def short_sleep(seconds):
    time.sleep(min(seconds, 0.05))


class Fixture:
    """A fake agent-seat: checkout, handoff directory, handoff-supervisor, agent-session."""

    def __init__(self, root: Path, ignore_sigterm=False):
        self.root = root
        self.name = f"restart-test-{os.getpid()}"
        self.fake = root / "fake"
        self.fake.mkdir()
        (self.fake / "handoff-supervisor.py").write_text(FAKE_SUPERVISOR)
        (self.fake / "claude").write_text(FAKE_CLAUDE)
        self.home = root / "home"
        self.home.mkdir()
        self.handoff_directory = root / "handoffs"
        self.handoff_directory.mkdir()
        self.origin = root / "origin.git"
        self.checkout = root / "checkout"
        git(root, "init", "--bare", "-b", "main", str(self.origin))
        git(root, "clone", str(self.origin), str(self.checkout))
        (self.checkout / "tracked.txt").write_text("one\n")
        git(self.checkout, "add", "tracked.txt")
        git(self.checkout, "commit", "-m", "first")
        git(self.checkout, "push", "origin", "main")
        other = root / "other"
        git(root, "clone", str(self.origin), str(other))
        (other / "second.txt").write_text("two\n")
        git(other, "add", "second.txt")
        git(other, "commit", "-m", "second")
        git(other, "push", "origin", "main")
        self.origin_main = git(other, "rev-parse", "HEAD")
        (self.checkout / "scripts").mkdir()
        for program in ("resupervise-seat.py", "recover-crashed-seats.py"):
            (self.checkout / "scripts" / program).write_text(STUB_RECOVERY_PROGRAM)
        self.saved_environment = dict(os.environ)
        os.environ.update({"FAKE_DIRECTORY": str(self.fake), "FAKE_SESSION_ID": SESSION_ID,
                           "HOME": str(self.home), "TMUX": "/tmp/tmux-test/default,1,0"})
        if ignore_sigterm:
            os.environ["FAKE_CLAUDE_IGNORES_SIGTERM"] = "1"
        self.supervisor_process = subprocess.Popen(
            [sys.executable, str(self.fake / "handoff-supervisor.py"), "--agent", self.name])
        self.claude = int(wait_for_file(self.fake / "claude.pid"))
        self.helper = int(wait_for_file(self.fake / "helper.pid"))
        self.supervisor = self.supervisor_process.pid
        restart.supervisor.supervisor_lock_path(self.handoff_directory, self.name).write_text(
            str(self.supervisor))
        self.write_state({"consumed_counter": 3, "launched_session_id": SESSION_ID})

    def write_state(self, state):
        restart.supervisor.supervisor_state_path(self.handoff_directory, self.name).write_text(
            json.dumps(state))

    def write_handoff(self, counter, extra=""):
        restart.supervisor.handoff_file_path(self.handoff_directory, self.name).write_text(
            f"written-at: 2026-10-28T00:00:00Z\nnext-step: carry on\n"
            f"restart-counter: {counter}\n{extra}")

    @property
    def log_text(self):
        path = restart.handoff_supervisor_restart_log_path_for_agent_seat(self.handoff_directory, self.name)
        return path.read_text() if path.is_file() else ""

    def recovery_calls(self):
        path = self.fake / "recovery-calls.jsonl"
        if not path.is_file():
            return []
        return [json.loads(line) for line in path.read_text().splitlines()]

    def arguments(self, *extra):
        return [self.name, "--handoff-dir", str(self.handoff_directory),
                "--checkout", str(self.checkout), *extra]

    def close(self):
        for process_id in (self.supervisor, self.claude, self.helper):
            with contextlib.suppress(ProcessLookupError):
                os.kill(process_id, signal.SIGCONT)
                os.kill(process_id, signal.SIGKILL)
        self.supervisor_process.wait()
        os.environ.clear()
        os.environ.update(self.saved_environment)


def run_main(fixture, *extra, detach=lambda _: False, **keywords):
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = restart.main(fixture.arguments(*extra), detach=detach, sleep=keywords.pop("sleep", short_sleep),
                            **keywords)
    return code, stdout.getvalue(), stderr.getvalue()


def case(function):
    def run():
        root = Path(tempfile.mkdtemp(prefix="restart-test-"))
        fixture = None
        try:
            fixture = Fixture(root, **getattr(function, "fixture_options", {}))
            function(fixture)
            print(f"PASS {function.__name__}")
        except Exception as error:
            failures.append(function.__name__)
            print(f"FAIL {function.__name__}: {error!r}")
        finally:
            if fixture is not None:
                fixture.close()
            shutil.rmtree(root, ignore_errors=True)
    run.__name__ = function.__name__
    CASES.append(run)
    return run


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def check_refused_untouched(fixture, code, stderr, words):
    check(code == 1, f"exit {code}")
    check("REFUSED" in stderr and words in stderr, stderr)
    check("do not write a handoff for this restart" in stderr, stderr)
    check("tell merge-lane-2 with SendMessage" in stderr, stderr)
    check(not process_state(fixture.supervisor).startswith(("T", "t")),
          f"handoff-supervisor state {process_state(fixture.supervisor)}")
    check("NOT RESTARTED" in fixture.log_text, fixture.log_text)


# --- Refusals before any signal -------------------------------------------------------------

@case
def refuses_when_checkout_is_not_on_main(fixture):
    git(fixture.checkout, "switch", "-c", "elsewhere")
    code, _, stderr = run_main(fixture)
    check_refused_untouched(fixture, code, stderr, "is not on main (elsewhere)")
    check(f"git -C {fixture.checkout} switch main" in stderr, stderr)


@case
def refuses_when_checkout_has_detached_head(fixture):
    git(fixture.checkout, "switch", "--detach")
    code, _, stderr = run_main(fixture)
    check_refused_untouched(fixture, code, stderr, "is not on main")


@case
def refuses_when_a_tracked_file_is_changed(fixture):
    (fixture.checkout / "tracked.txt").write_text("changed\n")
    code, _, stderr = run_main(fixture)
    check_refused_untouched(fixture, code, stderr, "uncommitted changes to tracked files (tracked.txt)")


@case
def untracked_files_do_not_refuse_and_main_is_fast_forwarded(fixture):
    (fixture.checkout / "untracked.txt").write_text("loose\n")
    code, stdout, _ = run_main(fixture)
    check(code == 0, f"exit {code}")
    check(git(fixture.checkout, "rev-parse", "HEAD") == fixture.origin_main, "not fast-forwarded")
    check(f"is on main at {fixture.origin_main[:7]}" in fixture.log_text, fixture.log_text)


@case
def refuses_when_git_status_fails(fixture):
    (fixture.checkout / ".git" / "index").write_bytes(b"not an index")
    code, _, stderr = run_main(fixture)
    check(code == 1 and "`git status` failed in" in stderr, stderr)
    check(not process_state(fixture.supervisor).startswith(("T", "t")), "signalled")


@case
def refuses_when_fetch_fails(fixture):
    git(fixture.checkout, "remote", "set-url", "origin", str(fixture.root / "missing.git"))
    code, _, stderr = run_main(fixture)
    check_refused_untouched(fixture, code, stderr, "`git fetch origin main` failed")


@case
def refuses_when_main_cannot_fast_forward(fixture):
    (fixture.checkout / "local.txt").write_text("local\n")
    git(fixture.checkout, "add", "local.txt")
    git(fixture.checkout, "commit", "-m", "local")
    code, _, stderr = run_main(fixture)
    check_refused_untouched(fixture, code, stderr, "`git merge --ff-only origin/main` failed")


@case
def refuses_when_no_lock(fixture):
    restart.supervisor.supervisor_lock_path(fixture.handoff_directory, fixture.name).unlink()
    code, _, stderr = run_main(fixture)
    check_refused_untouched(fixture, code, stderr, "no readable handoff-supervisor lock")


@case
def refuses_when_lock_names_another_process(fixture):
    restart.supervisor.supervisor_lock_path(fixture.handoff_directory, fixture.name).write_text(
        str(fixture.helper))
    code, _, stderr = run_main(fixture)
    check_refused_untouched(fixture, code, stderr, f"names process {fixture.helper}, but")
    check(not process_state(fixture.helper).startswith(("T", "t")), "helper was signalled")


@case
def refuses_when_ps_cannot_identify_the_lock_holder(fixture):
    original = restart.supervisor.read_process_command_line
    restart.supervisor.read_process_command_line = lambda _: (None, False)
    try:
        code, _, stderr = run_main(fixture)
    finally:
        restart.supervisor.read_process_command_line = original
    check_refused_untouched(fixture, code, stderr, "ps could not say what process")


@case
def refuses_when_ps_process_list_fails(fixture):
    fake_bin = fixture.root / "fake-bin"
    fake_bin.mkdir()
    (fake_bin / "ps").write_text("#!/bin/sh\necho 'ps: broken' >&2\nexit 1\n")
    (fake_bin / "ps").chmod(0o755)
    saved_path = os.environ["PATH"]
    os.environ["PATH"] = f"{fake_bin}:{saved_path}"
    try:
        restart.read_process_table()
        raise AssertionError("read_process_table did not refuse")
    except restart.HandoffSupervisorRestartRefusal as refusal:
        check("ps exited 1: ps: broken" in str(refusal), str(refusal))
    finally:
        os.environ["PATH"] = saved_path


@case
def refuses_when_supervisor_is_missing_from_the_process_list(fixture):
    code, _, stderr = run_main(fixture, read_table=lambda: {})
    check_refused_untouched(fixture, code, stderr, "is not in ps's process list")


@case
def refuses_when_supervisor_is_its_tmux_panes_own_process(fixture):
    def table_with_tmux_parent():
        table = restart.read_process_table()
        parent = table[fixture.supervisor][0]
        table[parent] = (1, "Ss", "/usr/bin/tmux -L seat new-session -d -s seat")
        return table
    code, _, stderr = run_main(fixture, read_table=table_with_tmux_parent)
    check_refused_untouched(fixture, code, stderr, "is its tmux pane's own process")


@case
def refuses_when_state_records_no_session_id(fixture):
    fixture.write_state({"consumed_counter": 3})
    code, _, stderr = run_main(fixture)
    check_refused_untouched(fixture, code, stderr, "records no session id")


@case
def refuses_when_no_child_carries_the_session_id(fixture):
    fixture.write_state({"consumed_counter": 3, "launched_session_id": "another-id"})
    code, _, stderr = run_main(fixture)
    check_refused_untouched(fixture, code, stderr, "found 0 child processes")


@case
def finds_an_agent_session_started_with_resume(fixture):
    table = {10: (1, "S", "python3 handoff-supervisor.py --agent x"),
             11: (10, "S", f"claude --resume {SESSION_ID} prompt"),
             12: (10, "S", f"claude --session-id {SESSION_ID}x"),
             13: (99, "S", f"claude --session-id {SESSION_ID}"),
             14: (10, "S", "claude --session-id"),
             15: (5, "S", f"claude --session-id {SESSION_ID}")}
    check(restart.find_agent_session_process_id_among_handoff_supervisor_children(table, 10, SESSION_ID) == 11, "not found by --resume")


@case
def refuses_when_the_log_cannot_be_appended(fixture):
    restart.handoff_supervisor_restart_log_path_for_agent_seat(fixture.handoff_directory, fixture.name).mkdir()
    code, _, stderr = run_main(fixture)
    check(code == 1 and "cannot append to the log" in stderr, stderr)
    check(not process_state(fixture.supervisor).startswith(("T", "t")), "signalled")


@case
def refuses_when_the_sandbox_blocks_sigstop(fixture):
    original_kill = restart.os.kill

    def kill_refusing_sigstop(process_id, number):
        if number == signal.SIGSTOP:
            raise PermissionError(1, "Operation not permitted")
        original_kill(process_id, number)
    restart.os.kill = kill_refusing_sigstop
    try:
        code, _, stderr = run_main(fixture)
    finally:
        restart.os.kill = original_kill
    check_refused_untouched(fixture, code, stderr, "dangerouslyDisableSandbox set to true")


@case
def refuses_and_continues_when_the_freeze_does_not_hold(fixture):
    def sleep_while_tmux_continues_it(seconds):
        os.kill(fixture.supervisor, signal.SIGCONT)
        time.sleep(0.2)
    code, _, stderr = run_main(fixture, sleep=sleep_while_tmux_continues_it)
    check_refused_untouched(fixture, code, stderr, "did not stay stopped after SIGSTOP")


@case
def a_stopped_supervisor_that_the_freeze_check_sees_running_is_continued(fixture):
    seen = []

    def table_showing_it_running():
        table = restart.read_process_table()
        seen.append(table[fixture.supervisor][1])
        parent, _, command = table[fixture.supervisor]
        table[fixture.supervisor] = (parent, "S", command)
        return table
    code, _, stderr = run_main(fixture, read_table=table_showing_it_running)
    check(code == 1 and "did not stay stopped" in stderr, stderr)
    check(seen[-1].startswith(("T", "t")), f"the real process was not stopped: {seen}")
    check(not process_state(fixture.supervisor).startswith(("T", "t")), "SIGCONT was not sent")


@case
def refuses_and_continues_when_detaching_fails(fixture):
    def failing_detach(_):
        raise OSError(11, "Resource temporarily unavailable")
    code, _, stderr = run_main(fixture, detach=failing_detach)
    check_refused_untouched(fixture, code, stderr, "the detached process could not be started")


@case
def rejects_a_bad_agent_seat_name_and_wait(fixture):
    for arguments in (["bad name"], [fixture.name, "--handoff-wait-minutes", "0"],
                      [fixture.name, "--handoff-wait-minutes", "-1"]):
        with contextlib.redirect_stderr(io.StringIO()):
            try:
                restart.main(arguments, detach=lambda _: False)
                raise AssertionError(f"{arguments} accepted")
            except SystemExit as exit_:
                check(exit_.code == 2, f"exit {exit_.code}")
    check(not process_state(fixture.supervisor).startswith(("T", "t")), "signalled")


# --- The foreground's success ---------------------------------------------------------------

@case
def foreground_freezes_and_tells_the_agent_what_to_do(fixture):
    fixture.write_handoff(5)
    code, stdout, _ = run_main(fixture, "--handoff-wait-minutes", "7")
    check(code == 0, f"exit {code}")
    check(process_state(fixture.supervisor).startswith(("T", "t")), "handoff-supervisor not stopped")
    log_path = restart.handoff_supervisor_restart_log_path_for_agent_seat(fixture.handoff_directory, fixture.name)
    for line in ("Write your handoff now with the handoff skill, without --dont-restart.",
                 f"read the end of {log_path} and tell merge-lane-2 with SendMessage",
                 "If no handoff arrives within 7 minutes"):
        check(line in stdout, f"missing {line!r} in {stdout}")


# --- The detached half ----------------------------------------------------------------------

def detached_run(fixture, *extra, sleep=None, monotonic=time.monotonic, read_table=None):
    """Run main with the detached half in this process."""
    return run_main(fixture, *extra, detach=lambda _: True, sleep=sleep or short_sleep,
                    monotonic=monotonic, read_table=read_table or restart.read_process_table)


def sleep_that_writes_the_handoff(fixture, counter):
    calls = []

    def sleep(seconds):
        calls.append(seconds)
        if seconds == restart.HANDOFF_POLL_SECONDS:
            fixture.write_handoff(counter)
        short_sleep(seconds)
    return sleep


@case
def restarts_when_the_handoff_arrives(fixture):
    def table_with_this_process_under_the_agent_session():
        table = restart.read_process_table()
        table[os.getpid()] = (fixture.claude, "S", "python3 this-program")
        # This process is the fake handoff-supervisor's parent; cut that link so the table stays a tree.
        table[fixture.supervisor] = (1, *table[fixture.supervisor][1:])
        return table
    code, _, _ = detached_run(fixture, sleep=sleep_that_writes_the_handoff(fixture, 4),
                              read_table=table_with_this_process_under_the_agent_session)
    check(code == 0, f"exit {code}: {fixture.log_text}")
    for process_id in (fixture.supervisor, fixture.claude, fixture.helper):
        check(not restart.process_is_running(process_id), f"{process_id} still running")
    calls = fixture.recovery_calls()
    handoff_arguments = ["--handoff-dir", str(fixture.handoff_directory)]
    check([call["program"] for call in calls] == ["resupervise-seat.py", "recover-crashed-seats.py"],
          calls)
    check(calls[0]["argv"] == [fixture.name, "--prepare-only", *handoff_arguments], calls)
    check(calls[1]["argv"] == [fixture.name, *handoff_arguments], calls)
    check(all(call["tmux"] is None for call in calls), "TMUX reached a recovery program")
    check(all(call["cwd"] == str(fixture.home) for call in calls), calls)
    log = fixture.log_text
    for line in ("handoff with restart-counter 4 arrived",
                 f"sent SIGKILL to handoff-supervisor {fixture.supervisor}",
                 "resupervise-seat.py: resupervise-seat.py stub ran",
                 "resupervise-seat.py exited 0", "recover-crashed-seats.py exited 0"):
        check(line in log, f"missing {line!r} in {log}")
    check(log.strip().splitlines()[-1].endswith(
        f"RESTARTED: {fixture.name} runs under a new handoff-supervisor from {fixture.checkout}"), log)


@case
def a_handoff_no_newer_than_one_seen_before_does_not_count(fixture):
    fixture.write_handoff(5)
    ticks = iter(range(0, 10_000, 600))
    code, _, _ = detached_run(fixture, "--handoff-wait-minutes", "20",
                              sleep=sleep_that_writes_the_handoff(fixture, 2),
                              monotonic=lambda: next(ticks))
    check(code == 1, f"exit {code}")
    check("above 5 reached" in fixture.log_text, fixture.log_text)
    check(fixture.recovery_calls() == [], "recovery ran")


@case
def timeout_continues_the_supervisor(fixture):
    # The run ends exactly at the deadline: one tick more would raise StopIteration.
    ticks = iter([0, 0, 30])
    code, _, _ = detached_run(fixture, "--handoff-wait-minutes", "0.5", sleep=short_sleep,
                              monotonic=lambda: next(ticks))
    check(code == 1, f"exit {code}")
    check(not process_state(fixture.supervisor).startswith(("T", "t")), "not continued")
    check(restart.process_is_running(fixture.claude), "agent-session was ended")
    last = fixture.log_text.strip().splitlines()[-1]
    check("NOT RESTARTED: no handoff with a restart-counter above 3" in last
          and "within 0.5 minutes" in last and "sent SIGCONT" in last, last)
    check(fixture.recovery_calls() == [], "recovery ran")


@case
def a_failure_before_the_kill_continues_the_supervisor(fixture):
    calls = []

    def table_failing_in_the_wait():
        calls.append(1)
        if len(calls) > 2:
            raise RuntimeError("ps vanished")
        return restart.read_process_table()
    try:
        detached_run(fixture, sleep=sleep_that_writes_the_handoff(fixture, 4),
                     read_table=table_failing_in_the_wait)
        raise AssertionError("the failure was not raised")
    except RuntimeError:
        pass
    check(not process_state(fixture.supervisor).startswith(("T", "t")), "not continued")
    check("NOT RESTARTED: this program failed (RuntimeError('ps vanished'))" in fixture.log_text,
          fixture.log_text)


@case
def a_failure_after_the_kill_is_logged_as_failed(fixture):
    killed = []
    original_kill = restart.os.kill

    def kill_recording(process_id, number):
        if number == signal.SIGKILL and process_id == fixture.supervisor:
            killed.append(process_id)
        original_kill(process_id, number)

    def table_failing_after_the_kill():
        if killed:
            raise RuntimeError("ps vanished")
        return restart.read_process_table()
    restart.os.kill = kill_recording
    try:
        detached_run(fixture, sleep=sleep_that_writes_the_handoff(fixture, 4),
                     read_table=table_failing_after_the_kill)
        raise AssertionError("the failure was not raised")
    except RuntimeError:
        pass
    finally:
        restart.os.kill = original_kill
    log = fixture.log_text
    check("FAILED: this program failed (RuntimeError('ps vanished')) after ending" in log, log)
    check(f"recover-crashed-seats.py {fixture.name}" in log, log)


def ignores_sigterm(function):
    function.fixture_options = {"ignore_sigterm": True}
    return function


@case
@ignores_sigterm
def an_agent_session_that_ignores_sigterm_gets_sigkill(fixture):
    saved = restart.AGENT_SESSION_SIGTERM_TO_SIGKILL_WAIT_SECONDS
    restart.AGENT_SESSION_SIGTERM_TO_SIGKILL_WAIT_SECONDS = 1.0
    try:
        code, _, _ = detached_run(fixture, sleep=sleep_that_writes_the_handoff(fixture, 4))
    finally:
        restart.AGENT_SESSION_SIGTERM_TO_SIGKILL_WAIT_SECONDS = saved
    check(code == 0, f"exit {code}")
    check(not restart.process_is_running(fixture.claude), "agent-session still running")
    check(f"process {fixture.claude} was still running 1s after SIGTERM; sent SIGKILL"
          in fixture.log_text, fixture.log_text)


@case
def prepare_refusal_stops_before_recovery(fixture):
    os.environ["FAKE_EXIT_resupervise_seat"] = "1"
    code, _, _ = detached_run(fixture, sleep=sleep_that_writes_the_handoff(fixture, 4))
    check(code == 1, f"exit {code}")
    check([call["program"] for call in fixture.recovery_calls()] == ["resupervise-seat.py"],
          fixture.recovery_calls())
    last = fixture.log_text.strip().splitlines()[-1]
    check("FAILED: resupervise-seat.py --prepare-only refused." in last
          and f"is down on {restart.socket.gethostname()}" in last
          and f"resupervise-seat.py {fixture.name} --prepare-only && python3" in last, last)


@case
def recovery_failure_is_logged_as_failed(fixture):
    os.environ["FAKE_EXIT_recover_crashed_seats"] = "1"
    code, _, _ = detached_run(fixture, sleep=sleep_that_writes_the_handoff(fixture, 4))
    check(code == 1, f"exit {code}")
    last = fixture.log_text.strip().splitlines()[-1]
    check("FAILED: recover-crashed-seats.py did not report" in last
          and f"recover-crashed-seats.py {fixture.name}" in last, last)


@case
def recovery_without_a_mac_window_counts_as_restarted(fixture):
    os.environ["FAKE_EXIT_recover_crashed_seats"] = "3"
    code, _, _ = detached_run(fixture, sleep=sleep_that_writes_the_handoff(fixture, 4))
    check(code == 0, f"exit {code}")
    check("RESTARTED" in fixture.log_text.strip().splitlines()[-1], fixture.log_text)


@case
def a_process_already_gone_is_not_waited_for(fixture):
    os.kill(fixture.helper, signal.SIGKILL)
    for _ in range(100):
        if not restart.process_is_running(fixture.helper):
            break
        time.sleep(0.05)
    lines = []
    restart.end_process_by_sigterm_then_sigkill_after_wait(fixture.helper, 1.0, lines.append)
    restart.end_process_by_sigterm_then_sigkill_after_wait(2 ** 22 + 12345, 1.0, lines.append)
    check(lines == [], lines)


@case
def detaching_leaves_the_session_directory_and_terminal(fixture):
    log_path = fixture.root / "detach-log.txt"
    driver = textwrap.dedent(f"""\
        import importlib.util, os, sys, time
        spec = importlib.util.spec_from_file_location("restart_program", {str(PROGRAM_PATH)!r})
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        from pathlib import Path
        print(f"before {{os.getpid()}}", flush=True)
        if module.fork_child_detached_into_new_unix_session(Path({str(log_path)!r})):
            print(f"child sid={{os.getsid(0)}} pid={{os.getpid()}} cwd={{os.getcwd()}} "
                  f"stdin={{sys.stdin.read()!r}}", flush=True)
            print("child stderr", file=sys.stderr, flush=True)
            os._exit(0)
        print("parent", flush=True)
    """)
    completed = subprocess.run([sys.executable, "-c", driver], cwd=str(fixture.root),
                               input="typed", capture_output=True, text=True, timeout=30)
    driver_process_id = completed.stdout.split()[1]
    check(completed.stdout == f"before {driver_process_id}\nparent\n", completed.stdout)
    text = ""
    for _ in range(100):
        text = log_path.read_text() if log_path.is_file() else ""
        if "child stderr" in text:
            break
        time.sleep(0.05)
    child_line = next((line for line in text.splitlines() if line.startswith("child sid=")), "")
    words = dict(word.split("=", 1) for word in child_line.split()[1:4])
    check(words.get("sid") == words.get("pid"), f"not a new session: {text}")
    check(words.get("pid") != driver_process_id, f"the parent took the child's part: {text}")
    check(words.get("cwd") == str(fixture.home), f"did not leave its directory: {text}")
    check("stdin=''" in child_line, f"stdin not from /dev/null: {text}")
    check("child stderr" in text, text)


# --- Smaller parts, each on the input that tells its correct form from a near miss ----------

NO_SUCH_PROCESS_ID = 2 ** 22 + 12345


@case
def git_failure_text_falls_back_to_stdout_then_to_a_placeholder(fixture):
    completed = subprocess.CompletedProcess([], 1, stdout="out  put\n", stderr="")
    check(restart.failed_command_output_on_one_line(completed) == "out put", restart.failed_command_output_on_one_line(completed))
    completed = subprocess.CompletedProcess([], 1, stdout="", stderr="")
    check(restart.failed_command_output_on_one_line(completed) == "no output", restart.failed_command_output_on_one_line(completed))


@case
def process_table_skips_short_lines_and_keeps_spaces_in_commands(fixture):
    fake_bin = fixture.root / "fake-bin"
    fake_bin.mkdir()
    (fake_bin / "ps").write_text("#!/bin/sh\nprintf '  1   0 Ss\\nshort line\\n  5 1 S  python3 a  b\\n'\n")
    (fake_bin / "ps").chmod(0o755)
    saved_path = os.environ["PATH"]
    os.environ["PATH"] = f"{fake_bin}:{saved_path}"
    try:
        table = restart.read_process_table()
    finally:
        os.environ["PATH"] = saved_path
    check(table == {1: (0, "Ss", ""), 5: (1, "S", "python3 a  b")}, table)


@case
def a_parent_missing_from_the_table_is_not_taken_for_tmux(fixture):
    restart.refuse_handoff_supervisor_restart_when_its_parent_process_is_tmux({10: (9, "S", "python3 handoff-supervisor.py")}, 10)


@case
def two_children_carrying_the_session_id_refuse(fixture):
    table = {11: (10, "S", f"claude --session-id {SESSION_ID}"),
             12: (10, "S", f"claude --resume {SESSION_ID}")}
    try:
        restart.find_agent_session_process_id_among_handoff_supervisor_children(table, 10, SESSION_ID)
        raise AssertionError("two matches accepted")
    except restart.HandoffSupervisorRestartRefusal as refusal:
        check("found 2 child processes" in str(refusal), str(refusal))


@case
def descendants_are_children_and_their_children_only(fixture):
    table = {1: (7, "S", ""), 2: (1, "S", ""), 3: (2, "S", ""), 4: (2, "S", ""), 5: (9, "S", ""),
             6: (0, "S", "")}
    found = restart.descendant_process_ids(table, 1)
    check(sorted(found) == [2, 3, 4] and len(found) == 3, found)


@case
def counter_seen_is_minus_one_with_no_counter_and_zero_counts(fixture):
    check(restart.highest_restart_counter_field_value_in_session_handoff_and_handoff_supervisor_state_files(fixture.handoff_directory, fixture.name, {}) == -1,
          "no counter")
    check(restart.highest_restart_counter_field_value_in_session_handoff_and_handoff_supervisor_state_files(
        fixture.handoff_directory, fixture.name, {"consumed_counter": 0}) == 0, "zero")


@case
def a_supervisor_gone_from_the_table_after_sigstop_is_refused(fixture):
    calls = []

    def table_losing_the_supervisor():
        calls.append(1)
        table = restart.read_process_table()
        if len(calls) > 1:
            del table[fixture.supervisor]
        return table
    code, _, stderr = run_main(fixture, read_table=table_losing_the_supervisor)
    check(code == 1 and "(ps state gone)" in stderr, stderr)
    check(not process_state(fixture.supervisor).startswith(("T", "t")), "SIGCONT was not sent")


@case
def sigkill_is_sent_exactly_at_the_wait_and_a_process_gone_by_then_is_no_failure(fixture):
    sleeper = subprocess.Popen(["sleep", "60"])

    def table_reaping_it_but_showing_it_running():
        sleeper.wait()
        return {sleeper.pid: (1, "S", "sleep 60")}
    ticks = iter([0, 1.0])
    lines = []
    restart.end_process_by_sigterm_then_sigkill_after_wait(
        sleeper.pid, 1.0, lines.append, sleep=lambda _: None, monotonic=lambda: next(ticks),
        read_table=table_reaping_it_but_showing_it_running)
    check(lines == [f"process {sleeper.pid} was still running 1s after SIGTERM; sent SIGKILL"],
          lines)


@case
def a_failure_before_the_kill_with_the_supervisor_gone_is_still_logged(fixture):
    lines = []

    def failing_table():
        raise RuntimeError("ps vanished")
    fixture.write_handoff(4)
    try:
        restart.wait_for_new_session_handoff_then_kill_old_handoff_supervisor_and_agent_session_and_relaunch_agent_seat(fixture.name, fixture.handoff_directory, fixture.checkout,
                                      NO_SUCH_PROCESS_ID, fixture.claude, 3, 60, lines.append,
                                      sleep=short_sleep, read_table=failing_table)
        raise AssertionError("the failure was not raised")
    except RuntimeError:
        pass
    check(any(line.startswith("NOT RESTARTED: this program failed") for line in lines), lines)


def main() -> int:
    if shutil.which("ps") is None:
        print("FAIL ps is not on PATH, so these cases cannot read processes")
        return 1
    for run in CASES:
        run()
    print()
    if failures:
        print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
