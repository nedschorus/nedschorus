#!/usr/bin/env python3
"""Tests for handoff-supervisor.py: what the supervisor does when a session
ends.

A handoff that arrives as a session's exit; the stops with no terminal to ask
on or to seat a successor on; the exit record a stop writes; the worktree
cleanup between a retiring session's stop and its successor's launch; and
resuming a session that ended without a handoff, after a death or by hand.
The supervisor's other cases are in
handoff-supervisor-successor-prompt-test.py and
handoff-supervisor-session-launch-and-seat-lock-test.py, beside this file.

Run: python3 nc-systems/handoff/tests/handoff-supervisor-session-end-and-resume-test.py

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
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

# Before anything runs git: a run started with GIT_DIR set, or with another
# variable that redirects git, must keep this suite's git, and the git of every
# supervisor it starts, out of the repository the variable names. This suite
# sits at nc-systems/handoff/tests/, so the repository root is three
# directories up.
_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().parents[3] / "scripts"
    / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

_handoff_supervisor_test_fixture_spec = importlib.util.spec_from_file_location(
    "handoff_supervisor_test_fixture",
    Path(__file__).resolve().with_name("handoff-supervisor-test-fixture.py"))
fixture = importlib.util.module_from_spec(_handoff_supervisor_test_fixture_spec)
_handoff_supervisor_test_fixture_spec.loader.exec_module(fixture)

supervisor = fixture.supervisor
check = fixture.check
SCRIPT_PATH = fixture.SCRIPT_PATH
git_in = fixture.git_in
StubLaunchedSession = fixture.StubLaunchedSession
supervisor_names_replaced = fixture.supervisor_names_replaced


def stub_process(poll_result):
    """A stand-in for a session process: poll() reports the given exit state."""
    return SimpleNamespace(poll=lambda: poll_result)


def run_exit_handoff_cases(workspace: Path):
    """A headless session exits when its turn ends, so its handoff arrives AS
    a process exit. Exit with a new counter on disk must read as a handoff;
    exit without one is abandonment."""
    handoff_path = workspace / "exitcase-handoff.md"
    state_path = workspace / "exitcase-supervisor-state.json"

    handoff_path.write_text(
        "written-at: 2026-08-06T12:00:00Z\nnext-step: drain the tasks\nrestart-counter: 8\n",
        encoding="utf-8",
    )
    fields = supervisor.wait_for_handoff(stub_process(0), handoff_path, 7, state_path, {})
    check(
        "exit with a new counter reads as a handoff",
        fields is not None and supervisor.counter_from(fields) == 8,
        str(fields),
    )

    fields = supervisor.wait_for_handoff(stub_process(0), handoff_path, 8, state_path, {})
    check("exit with the already-consumed counter reads as abandonment", fields is None, str(fields))

    fields = supervisor.wait_for_handoff(
        stub_process(0), workspace / "never-written-handoff.md", 7, state_path, {}
    )
    check("exit with no handoff file reads as abandonment", fields is None, str(fields))

    fields = supervisor.wait_for_handoff(stub_process(None), handoff_path, 7, state_path, {})
    check(
        "a running session's new handoff is seen without an exit",
        fields is not None and supervisor.counter_from(fields) == 8,
        str(fields),
    )


def run_dont_restart_without_a_terminal_case(workspace: Path):
    """A supervisor whose stdin is redirected has no terminal. Asking `restart? y/n`
    there raises EOFError before the consumed counter is recorded, so the next
    supervisor re-fires on the stale handoff — launching a session and killing
    it immediately."""
    handoff_directory = workspace / "noterm"
    handoff_directory.mkdir(parents=True, exist_ok=True)
    (handoff_directory / "noterm-handoff.md").write_text(
        "written-at: 2026-08-06T12:00:00Z\n"
        "next-step: should not relaunch\n"
        "restart-counter: 1\n"
        "dont-restart: the user asked to be consulted\n",
        encoding="utf-8",
    )
    stub_agent = handoff_directory / "stub-agent"
    stub_agent.write_text("#!/bin/sh\nsleep 30\n", encoding="utf-8")
    stub_agent.chmod(0o755)

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--agent", "noterm", "--cd", str(workspace),
         "--handoff-dir", str(handoff_directory), "--agent-command", str(stub_agent), "--agent-update-timeout-seconds", "0"],
        capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL, timeout=60,
    )
    check("dont-restart without a terminal exits cleanly, not on EOFError",
          result.returncode == 0 and "EOFError" not in result.stderr, result.stderr[-300:])
    check("dont-restart without a terminal says why it stopped",
          "no terminal to ask on" in result.stdout, result.stdout[-300:])

    state = supervisor.read_supervisor_state(handoff_directory / "noterm-supervisor-state.json")
    check("the consumed counter is recorded before stopping",
          state.get("consumed_counter") == 1, str(state))
    # nedschorus#242 change 2: a seat stood down on dont-restart carries an exit
    # record, so recovery offers it rather than resuming a session that asked
    # not to be relaunched. This stop is boot-ignition's, before any launch, so
    # the code is unknown — and present all the same.
    check("dont-restart at boot records the agent's exit, its code unknown",
          supervisor.agent_exit_record_from_supervisor_state(state) is not None
          and state.get(supervisor.AGENT_EXIT_CODE_STATE_KEY, "absent") is None,
          str(state))


def run_no_seat_recycle_refusal_case(workspace: Path):
    """A handoff arriving at a supervisor with no terminal must not reincarnate:
    the successor would inherit this stdio and die at its first need for
    input (observed 2026-08-14 — an adopted console session was killed and
    its successor reported into a log file). The session stays up and the
    handoff stays unconsumed for a seated supervisor."""
    handoff_directory = workspace / "noseat"
    handoff_directory.mkdir(parents=True, exist_ok=True)
    stub_agent = handoff_directory / "stub-agent"
    session_process_id_path = handoff_directory / "stub-agent.pid"
    stub_agent.write_text(
        "#!/bin/sh\n"
        "exec >/dev/null 2>&1\n"  # release the supervisor's pipes, or the test waits out the sleep
        f"echo $$ > '{session_process_id_path}'\n"
        "printf 'written-at: 2026-08-14T00:00:00Z\\nnext-step: recycle me\\nrestart-counter: 9\\n' "
        f"> '{handoff_directory}/noseat-handoff.md'\n"
        "exec sleep 30\n",
        encoding="utf-8",
    )
    stub_agent.chmod(0o755)

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--agent", "noseat", "--cd", str(workspace),
         "--handoff-dir", str(handoff_directory), "--agent-command", str(stub_agent), "--agent-update-timeout-seconds", "0"],
        capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL, timeout=60,
    )
    check("a handoff without a seat stops the supervisor cleanly",
          result.returncode == 0, result.stderr[-300:])
    check("the refusal names the missing terminal, before any kill",
          "no terminal to seat a successor" in result.stdout, result.stdout[-400:])
    state = supervisor.read_supervisor_state(handoff_directory / "noseat-supervisor-state.json")
    check("the handoff stays unconsumed for a seated supervisor",
          state.get("consumed_counter") is None, str(state))
    # The session is left alive at this stop, so nothing exited: no record.
    check("a stop that leaves the session up records no agent exit",
          supervisor.agent_exit_record_from_supervisor_state(state) is None
          and supervisor.AGENT_EXIT_CODE_STATE_KEY not in state, str(state))

    # The supervisor leaves the session running at this stop, so the case
    # stops it: the stub execs its sleep, so the recorded id is the sleep's.
    if session_process_id_path.is_file():
        with contextlib.suppress(ProcessLookupError):
            os.kill(int(session_process_id_path.read_text(encoding="utf-8")), signal.SIGKILL)


def run_agent_exit_record_cases(workspace: Path):
    """nedschorus#242 change 2 (ruled 2026-09-02, the #120 overview § Ruled
    2026-09-02: record how the agent exited). Every stop after a session's end
    that launches no successor records the agent's exit code and the time in
    the state file; recover-crashed-seats.py offers such a seat instead of
    resuming it. The record is cleared before every launch or adoption, so a
    seat that once exited cleanly and later crashed does not read as clean."""
    # --- End to end: the real exit code of a real session -----------------
    name = "exitrecord"
    handoff_directory = workspace / name
    handoff_directory.mkdir(parents=True, exist_ok=True)
    state_path = handoff_directory / f"{name}-supervisor-state.json"
    stub_agent = handoff_directory / "stub-agent"
    for case_name, stub_body, expected_code in (
            ("a clean exit", "exit 0\n", 0),
            ("a nonzero exit", "exit 3\n", 3),
            # Negative, as Popen reports a signal: recorded as-is.
            ("an exit by SIGTERM", "kill -TERM $$\n", -15)):
        stub_agent.write_text("#!/bin/sh\n" + stub_body, encoding="utf-8")
        stub_agent.chmod(0o755)
        before = datetime.now(timezone.utc).replace(microsecond=0)
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--agent", name, "--cd", str(workspace),
             "--handoff-dir", str(handoff_directory), "--agent-command", str(stub_agent), "--agent-update-timeout-seconds", "0"],
            capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL, timeout=60,
        )
        state = supervisor.read_supervisor_state(state_path)
        record = supervisor.agent_exit_record_from_supervisor_state(state)
        try:
            recorded_at = datetime.fromisoformat(record[1]) if record else None
        except ValueError:
            recorded_at = None
        check(f"EXIT RECORD: {case_name} without a handoff records exit code {expected_code}",
              result.returncode == 0
              and "session ended without a handoff; supervisor stopping" in result.stdout
              and record is not None and record[0] == expected_code
              and state.get(supervisor.AGENT_EXIT_CODE_STATE_KEY) == expected_code,
              f"{state} {result.stdout[-300:]} {result.stderr[-300:]}")
        check(f"EXIT RECORD: {case_name} records when, in UTC, at the stop",
              recorded_at is not None and recorded_at.tzinfo is not None
              and before <= recorded_at <= datetime.now(timezone.utc),
              str(state))

    # The in-cycle dont-restart stop, with no terminal to ask on: the session
    # wrote its handoff and stayed up, so the supervisor terminated it before
    # standing the seat down — and records that termination's code as-is.
    name = "exitrecorddontrestart"
    handoff_directory = workspace / name
    handoff_directory.mkdir(parents=True, exist_ok=True)
    stub_agent = handoff_directory / "stub-agent"
    stub_agent.write_text(
        "#!/bin/sh\n"
        "exec >/dev/null 2>&1\n"
        "printf 'written-at: 2026-09-17T00:00:00Z\\nnext-step: stand down\\n"
        "restart-counter: 1\\ndont-restart: the user closes this seat\\n' "
        f"> '{handoff_directory}/{name}-handoff.md'\n"
        "exec sleep 30\n",
        encoding="utf-8",
    )
    stub_agent.chmod(0o755)
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--agent", name, "--cd", str(workspace),
         "--handoff-dir", str(handoff_directory), "--agent-command", str(stub_agent), "--agent-update-timeout-seconds", "0"],
        capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL, timeout=90,
    )
    state = supervisor.read_supervisor_state(handoff_directory / f"{name}-supervisor-state.json")
    check("EXIT RECORD: the in-cycle dont-restart stop records the terminated session's code",
          result.returncode == 0 and "no terminal to ask on; stopping" in result.stdout
          and state.get("consumed_counter") == 1
          and supervisor.agent_exit_record_from_supervisor_state(state) is not None
          and state.get(supervisor.AGENT_EXIT_CODE_STATE_KEY) == -15,
          f"{state} {result.stdout[-300:]} {result.stderr[-300:]}")

    # --- In process: the paths a subprocess cannot reach -------------------
    def settings_for(case: str, adopted_session=None):
        directory = workspace / f"exitrecord-in-process-{case}"
        directory.mkdir(parents=True, exist_ok=True)
        return supervisor.SupervisorSettings(
            agent=f"exitrecord{case}", working_directory=workspace,
            handoff_directory=directory, agent_command="unused-stub-agent",
            first_prompt="", adopted_session=adopted_session)

    def launch_recording(sessions, launched_state_snapshots, settings):
        def launch(agent_command, session_id, working_directory, prompt, **_):
            launched_state_snapshots.append(
                json.loads(settings.state_path.read_text(encoding="utf-8")))
            return sessions.pop(0)
        return launch

    no_branch_sync = lambda working_directory: "branch sync: not a git checkout, nothing to sync"

    # Cleared at launch: a record left by an earlier stop is gone from the state
    # file before the next session starts, and the stop after that session
    # writes a record of its own.
    settings = settings_for("cleared")
    supervisor.write_supervisor_state(settings.state_path, {
        "consumed_counter": None, "launched_session_id": "earlier-session", "generation": 2,
        supervisor.AGENT_EXIT_CODE_STATE_KEY: 0,
        supervisor.AGENT_EXIT_RECORDED_AT_STATE_KEY: "2026-01-01T00:00:00+00:00"})
    snapshots = []
    # No terminal, stated rather than inherited: exit code 9 is a death the
    # 2026-09-21 ruling resumes, and the no-terminal refusal is what
    # holds this case to the one launch it counts. Left to the real stdin it
    # would pass under a redirect and resume under a developer's terminal,
    # exhausting the one-session list below.
    with supervisor_names_replaced(
            launch_agent_session=launch_recording([StubLaunchedSession(9)], snapshots, settings),
            sync_working_branch_with_main=no_branch_sync, stdin_isatty=False), \
            contextlib.redirect_stdout(io.StringIO()):
        supervisor.supervise_sessions(settings)
    state = supervisor.read_supervisor_state(settings.state_path)
    check("EXIT RECORD: an earlier record is cleared from the state file before the launch",
          len(snapshots) == 1
          and supervisor.AGENT_EXIT_CODE_STATE_KEY not in snapshots[0]
          and supervisor.AGENT_EXIT_RECORDED_AT_STATE_KEY not in snapshots[0],
          str(snapshots))
    check("EXIT RECORD: and the launched session's own end is recorded afresh",
          supervisor.agent_exit_record_from_supervisor_state(state) is not None
          and state[supervisor.AGENT_EXIT_CODE_STATE_KEY] == 9
          and state[supervisor.AGENT_EXIT_RECORDED_AT_STATE_KEY] != "2026-01-01T00:00:00+00:00",
          str(state))

    # Cleared at adoption too, and an adopted session's code is unknown — its
    # poll() says 0 for any process that is merely gone — so it is recorded as
    # null rather than skipped.
    settings = settings_for("adopted", supervisor.AdoptedSession("adopted-session", 99999999))
    supervisor.write_supervisor_state(settings.state_path, {
        supervisor.AGENT_EXIT_CODE_STATE_KEY: 0,
        supervisor.AGENT_EXIT_RECORDED_AT_STATE_KEY: "2026-01-01T00:00:00+00:00"})
    written_states = []
    real_write_supervisor_state = supervisor.write_supervisor_state

    def write_recording(state_path, state):
        written_states.append(dict(state))
        real_write_supervisor_state(state_path, state)

    with supervisor_names_replaced(write_supervisor_state=write_recording), \
            contextlib.redirect_stdout(io.StringIO()):
        supervisor.supervise_sessions(settings)
    state = supervisor.read_supervisor_state(settings.state_path)
    check("EXIT RECORD: an earlier record is cleared before an adopted session is watched",
          written_states and supervisor.AGENT_EXIT_CODE_STATE_KEY not in written_states[0],
          str(written_states))
    check("EXIT RECORD: an adopted session's end is recorded with its code unknown",
          supervisor.agent_exit_record_from_supervisor_state(state) is not None
          and state.get(supervisor.AGENT_EXIT_CODE_STATE_KEY, "absent") is None,
          str(state))

    # A handoff arrives with a terminal to ask on. The session is still running
    # when it is written, so the supervisor stops it itself (SIGTERM, -15).
    def launch_writing_a_handoff(settings, session, handoff_text):
        def launch(agent_command, session_id, working_directory, prompt, **_):
            settings.handoff_path.write_text(handoff_text, encoding="utf-8")
            return session
        return launch

    # dont-restart answered n at the terminal.
    settings = settings_for("answeredn")
    supervisor.write_supervisor_state(settings.state_path, {"consumed_counter": 1})
    with supervisor_names_replaced(
            launch_agent_session=launch_writing_a_handoff(
                settings, StubLaunchedSession(-15, ended=False),
                "restart-counter: 2\nnext-step: stand down\ndont-restart: closing\n"),
            sync_working_branch_with_main=no_branch_sync,
            input=lambda prompt: "n", stdin_isatty=True), \
            contextlib.redirect_stdout(io.StringIO()):
        supervisor.supervise_sessions(settings)
    state = supervisor.read_supervisor_state(settings.state_path)
    check("EXIT RECORD: dont-restart answered n records the stopped session's code",
          state.get("consumed_counter") == 2
          and supervisor.agent_exit_record_from_supervisor_state(state) is not None
          and state.get(supervisor.AGENT_EXIT_CODE_STATE_KEY) == -15,
          str(state))

    # The dialog extraction fails, so no successor is launched: the stopped
    # session's end is recorded, and the handoff stays unconsumed.
    settings = settings_for("extractionfailed")
    supervisor.write_supervisor_state(settings.state_path, {"consumed_counter": 1})
    with supervisor_names_replaced(
            launch_agent_session=launch_writing_a_handoff(
                settings, StubLaunchedSession(-15, ended=False),
                "restart-counter: 2\nnext-step: carry on\n"),
            sync_working_branch_with_main=no_branch_sync,
            extract_dialog=lambda session_id, working_directory, output_path: False,
            stdin_isatty=True), \
            contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        supervisor.supervise_sessions(settings)
    state = supervisor.read_supervisor_state(settings.state_path)
    check("EXIT RECORD: a failed extraction records the stopped session, handoff unconsumed",
          state.get("consumed_counter") == 1
          and supervisor.agent_exit_record_from_supervisor_state(state) is not None
          and state.get(supervisor.AGENT_EXIT_CODE_STATE_KEY) == -15,
          str(state))


def process_is_gone_within_seconds(process_id: int, seconds: float) -> bool:
    """True once `ps` finds no process with this id, or finds it a zombie: a
    killed process whose parent has died waits as one until it is reaped."""
    deadline = time.monotonic() + seconds
    while True:
        state = subprocess.run(["ps", "-o", "stat=", "-p", str(process_id)],
                               capture_output=True, text=True, check=False).stdout.strip()
        if not state or state.startswith("Z"):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.1)


def run_handoff_worktree_cleanup_cases(workspace: Path):
    """Each handoff runs scripts/clean-worktrees.py --remove between the
    retiring session's stop and the successor's launch (superwalk item 6,
    2026-09-23), and nothing the cleaner does can stop the launch.

    GIT_DIR and GIT_WORK_TREE are removed for these cases and put back after:
    either one would send this fixture's git commands, and the cleaner's
    removals, into another repository (GHI 639's hazard)."""
    redirecting = {name: os.environ.pop(name) for name in ("GIT_DIR", "GIT_WORK_TREE")
                   if name in os.environ}
    try:
        run_handoff_worktree_cleanup_cases_without_git_redirection(workspace)
    finally:
        os.environ.update(redirecting)


def run_handoff_worktree_cleanup_cases_without_git_redirection(workspace: Path):
    root = workspace / "handoff-worktree-cleanup"
    root.mkdir()
    remote = root / "remote.git"
    git_in(["init", "--quiet", "--bare", "--initial-branch=main", str(remote)], root)
    home = root / "seat-home"
    git_in(["clone", "--quiet", str(remote), str(home)], root)
    git_in(["config", "user.name", "fixture"], home)
    git_in(["config", "user.email", "fixture@nedschorus.invalid"], home)
    (home / "README.md").write_text("seed\n", encoding="utf-8")
    git_in(["add", "-A"], home)
    git_in(["commit", "--quiet", "-m", "seed"], home)
    git_in(["push", "--quiet", "origin", "main"], home)
    git_in(["fetch", "--quiet", "origin"], home)
    # One finished worktree, one landed and vacant but holding an untracked
    # file, one with a commit beyond main, and one branch with no worktree
    # and nothing beyond main.
    finished = home / ".claude" / "worktrees" / "finished-worktree"
    git_in(["worktree", "add", "--quiet", "-b", "finished-branch", str(finished)], home)
    unfinished = home / ".claude" / "worktrees" / "unfinished-worktree"
    git_in(["worktree", "add", "--quiet", "-b", "unfinished-branch", str(unfinished)], home)
    (unfinished / "notes.txt").write_text("uncommitted\n", encoding="utf-8")
    unlanded = home / ".claude" / "worktrees" / "unlanded-worktree"
    git_in(["worktree", "add", "--quiet", "-b", "unlanded-branch", str(unlanded)], home)
    (unlanded / "work.txt").write_text("work\n", encoding="utf-8")
    git_in(["add", "-A"], unlanded)
    git_in(["commit", "--quiet", "-m", "unlanded work"], unlanded)
    git_in(["branch", "orphaned-branch"], home)
    # An Agent-tool subagent's worktree, clean and landed, made a moment ago:
    # its subagent runs inside its parent claude process, so no process has
    # its working directory here between the subagent's Bash calls.
    live_subagent = home / ".claude" / "worktrees" / "agent-0123456789abcdef0"
    git_in(["worktree", "add", "--quiet", "-b", "worktree-agent-0123456789abcdef0",
            str(live_subagent)], home)
    # Everything the cleaner is to remove is made an hour and a half old.
    long_ago = time.time() - 5400
    os.utime(finished / ".git", (long_ago, long_ago))

    report = supervisor.remove_finished_worktrees_at_handoff(home)
    branches = git_in(["branch", "--format=%(refname:short)"], home).stdout.split()
    check("WORKTREE CLEANUP: a finished worktree and its branch are removed",
          not finished.exists() and "finished-branch" not in branches,
          f"{report} {branches}")
    check("WORKTREE CLEANUP: a landed, vacant worktree holding an untracked file is removed",
          not unfinished.exists() and "unfinished-branch" not in branches,
          f"{report} {branches}")
    check("WORKTREE CLEANUP: a worktree with a commit beyond main is kept",
          unlanded.exists() and "unlanded-branch" in branches, f"{report} {branches}")
    check("WORKTREE CLEANUP: a branch with no worktree and nothing beyond main is deleted",
          "orphaned-branch" not in branches, f"{report} {branches}")
    check("WORKTREE CLEANUP: a live Agent-tool subagent's clean, landed worktree is kept",
          live_subagent.exists() and "worktree-agent-0123456789abcdef0" in branches,
          f"{report} {branches}")
    check("WORKTREE CLEANUP: the report counts what was removed and every branch deleted, "
          "and names the files a removal discarded",
          report == ("worktree cleanup: 2 finished worktree(s) removed, "
                     "3 branch ref(s) with nothing beyond main deleted; "
                     "1 removed with uncommitted, untracked or ignored files: "
                     "unfinished-worktree: discarding 1 uncommitted, untracked or ignored file(s): notes.txt"),
          report)

    # With GIT_DIR naming another repository, the cleanup still acts on the
    # seat's own, and leaves the other alone.
    other = root / "other-repository"
    git_in(["clone", "--quiet", str(remote), str(other)], root)
    git_in(["branch", "other-landed-branch"], other)
    second_finished = home / ".claude" / "worktrees" / "second-finished-worktree"
    git_in(["worktree", "add", "--quiet", "-b", "second-finished-branch",
            str(second_finished)], home)
    os.utime(second_finished / ".git", (long_ago, long_ago))
    os.environ["GIT_DIR"] = str(other / ".git")
    try:
        report = supervisor.remove_finished_worktrees_at_handoff(home)
    finally:
        del os.environ["GIT_DIR"]
    other_branches = git_in(["branch", "--format=%(refname:short)"], other).stdout.split()
    check("WORKTREE CLEANUP: GIT_DIR in the supervisor's environment does not "
          "redirect the cleanup to another repository",
          not second_finished.exists() and "other-landed-branch" in other_branches,
          f"{report} {other_branches}")

    not_a_checkout = root / "not-a-checkout"
    not_a_checkout.mkdir()
    report = supervisor.remove_finished_worktrees_at_handoff(not_a_checkout)
    check("WORKTREE CLEANUP: a directory that is not a checkout is reported, not raised",
          "exited 2" in report, report)

    hanging = root / "hanging-cleaner.py"
    hanging.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
    started = time.monotonic()
    with supervisor_names_replaced(CLEAN_WORKTREES_PATH=hanging):
        report = supervisor.remove_finished_worktrees_at_handoff(home, timeout_seconds=1)
    elapsed = time.monotonic() - started
    check("WORKTREE CLEANUP: a cleaner that hangs is stopped at the bound",
          elapsed < 15 and "did not finish in 1 s" in report, f"{elapsed:.1f}s {report}")

    # Like the real cleaner, this stand-in prints with a plain print() into a
    # pipe, never flushing, and has a child of its own running (the real one's
    # are lsof and git) when the bound stops it.
    grandchild_pid_file = root / "partway-cleaner-grandchild.pid"
    partway = root / "partway-cleaner.py"
    partway.write_text(
        "import subprocess, time\n"
        "print('agent-early: removed, branch worktree-agent-early deleted')\n"
        "print('branch landed-early: deleted (no worktree, nothing beyond origin/main)')\n"
        "grandchild = subprocess.Popen(['sleep', '30'], stdout=subprocess.DEVNULL,\n"
        "                              stderr=subprocess.DEVNULL)\n"
        f"open({str(grandchild_pid_file)!r}, 'w').write(str(grandchild.pid))\n"
        "time.sleep(30)\n", encoding="utf-8")
    started = time.monotonic()
    with supervisor_names_replaced(CLEAN_WORKTREES_PATH=partway):
        report = supervisor.remove_finished_worktrees_at_handoff(home, timeout_seconds=3)
    elapsed = time.monotonic() - started
    check("WORKTREE CLEANUP: a cleaner stopped at the bound partway through "
          "reports what it removed before the stop, though it never flushed its output",
          report.startswith("worktree cleanup: 1 finished worktree(s) removed, "
                            "2 branch ref(s)")
          and "did not finish in 3 s" in report and elapsed < 15,
          f"{elapsed:.1f}s {report}")
    grandchild_pid = (int(grandchild_pid_file.read_text(encoding="utf-8"))
                      if grandchild_pid_file.exists() else None)
    grandchild_gone = (grandchild_pid is not None
                       and process_is_gone_within_seconds(grandchild_pid, 5))
    check("WORKTREE CLEANUP: a cleaner stopped at the bound takes the processes "
          "it started down with it",
          grandchild_gone,
          f"the stand-in's child, pid {grandchild_pid}, is still running"
          if grandchild_pid is not None else "the stand-in never recorded its child")
    if grandchild_pid is not None and not grandchild_gone:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(grandchild_pid, signal.SIGKILL)

    crashing = root / "crashing-cleaner.py"
    crashing.write_text("raise RuntimeError('the cleaner broke')\n", encoding="utf-8")
    with supervisor_names_replaced(CLEAN_WORKTREES_PATH=crashing):
        report = supervisor.remove_finished_worktrees_at_handoff(home)
    check("WORKTREE CLEANUP: a cleaner that crashes is reported with its error, "
          "not as nothing removed",
          "exited 1" in report and "the cleaner broke" in report, report)

    unusable = root / "unusable-vacancy-cleaner.py"
    unusable.write_text(
        "print('agent-x: kept — the vacancy check (lsof) could not be run')\n"
        "print('done-y: removed, branch done-y-branch left in place "
        "(git branch -d refused)')\n", encoding="utf-8")
    with supervisor_names_replaced(CLEAN_WORKTREES_PATH=unusable):
        report = supervisor.remove_finished_worktrees_at_handoff(home)
    check("WORKTREE CLEANUP: a branch left in place and an unusable vacancy check "
          "are named in the report",
          "1 branch(es) left in place" in report
          and "kept because the vacancy check could not be run" in report, report)

    with supervisor_names_replaced(sys=SimpleNamespace(executable=str(root / "no-such-python"))):
        report = supervisor.remove_finished_worktrees_at_handoff(home)
    check("WORKTREE CLEANUP: a cleaner that cannot be run is reported, not raised",
          "could not be run" in report, report)

    # The wiring: after the handoff, the retiring session is stopped, then the
    # cleaner runs against the seat's directory, then the successor launches.
    handoff_directory = root / "handoffs"
    handoff_directory.mkdir()
    settings = supervisor.SupervisorSettings(
        agent="worktreecleanup", working_directory=home,
        handoff_directory=handoff_directory, agent_command="unused-stub-agent",
        first_prompt="")
    events = []

    def launch(agent_command, session_id, working_directory, prompt, **_):
        events.append("launch")
        if events.count("launch") == 1:
            settings.handoff_path.write_text(
                "restart-counter: 1\nnext-step: carry on\n", encoding="utf-8")
            return StubLaunchedSession(-15, ended=False)
        return StubLaunchedSession(0)

    def stop(process):
        events.append("stop")
        process.terminate()

    def cleanup(working_directory):
        events.append(("cleanup", working_directory))
        return "worktree cleanup: stubbed"

    console = io.StringIO()
    with supervisor_names_replaced(
            launch_agent_session=launch, stop_session=stop,
            remove_finished_worktrees_at_handoff=cleanup,
            sync_working_branch_with_main=lambda working_directory: "branch sync: stubbed",
            carry_over_to_successor=lambda settings, retiring, fields, generation: (
                f"successor-{generation}", None),
            stdin_isatty=True), \
            contextlib.redirect_stdout(console):
        supervisor.supervise_sessions(settings)
    check("WORKTREE CLEANUP: a handoff runs the cleaner on the seat's directory, "
          "between the stop and the successor's launch",
          events == ["launch", "stop", ("cleanup", home), "launch"],
          str(events))
    check("WORKTREE CLEANUP: the cleaner's report reaches the supervisor's console",
          "handoff-supervisor: worktree cleanup: stubbed" in console.getvalue(),
          console.getvalue()[-400:])

    # A first launch is not a handoff: the launchers' boot report covers it.
    events.clear()
    settings = supervisor.SupervisorSettings(
        agent="worktreecleanupfirst", working_directory=home,
        handoff_directory=handoff_directory, agent_command="unused-stub-agent",
        first_prompt="")
    with supervisor_names_replaced(
            launch_agent_session=lambda *arguments, **_: (
                events.append("launch") or StubLaunchedSession(0)),
            remove_finished_worktrees_at_handoff=cleanup,
            sync_working_branch_with_main=lambda working_directory: "branch sync: stubbed",
            stdin_isatty=False), \
            contextlib.redirect_stdout(io.StringIO()):
        supervisor.supervise_sessions(settings)
    check("WORKTREE CLEANUP: a launch with no handoff before it runs no cleaner",
          events == ["launch"], str(events))


def run_resume_after_a_death_without_a_handoff_cases(workspace: Path):
    """The ruling of 2026-09-21 (GHI [The handoff-supervisor resumes a session
    that died without a handoff, instead of stopping the seat](https://github.com/nedschorus/nedschorus/issues/613)):
    a session that dies without writing a handoff is resumed, chosen by how it
    died, under a budget of one resume that produces no new work.

    The behaviour it answers: on 2026-09-21 the MD-skills seat was terminated
    with exit code 143 beside an intact 6.4 MB transcript, its supervisor wrote
    the exit record and stopped as designed, and the seat stayed dark until the
    user happened to look.

    The budget is the case that matters, because a resume loop is unattended
    automation that spends money on every launch. The budget is one resume
    (user-ruled 2026-09-22): a seat whose transcript never grows gets its
    original launch and one resume — two launches — and the second resume is
    refused.
    The scripted launcher below raises rather than looping when the supervisor
    asks for a launch past the script, so a budget that stopped counting fails
    these cases instead of running forever.
    """
    # --- The ruling's table, against the pure function --------------------
    # Both spellings of each signal death: subprocess reports -15, a shell 143.
    # A rule that recognised one and not the other would stop the seat on the
    # other, which is why the ruling's table lists both.
    for exit_code, expect_resume, reason_fragment, row in (
            (0, False, "exited cleanly", "exit code 0 (a clean exit is a decision)"),
            (143, True, "SIGTERM", "exit code 143 (SIGTERM, as a shell reports it)"),
            (-15, True, "SIGTERM", "exit code -15 (SIGTERM, as subprocess reports it)"),
            (137, True, "SIGKILL", "exit code 137 (SIGKILL, as a shell reports it)"),
            (-9, True, "SIGKILL", "exit code -9 (SIGKILL, as subprocess reports it)"),
            (3, True, "error status", "exit code 3 (another non-zero status)"),
            (None, False, "adopted session", "exit code None (an adopted session)")):
        decision = supervisor.resume_or_stop_after_a_death_without_a_handoff(exit_code)
        check(f"RULING TABLE: {row} -> {'resume' if expect_resume else 'stop'}",
              decision.resume is expect_resume and reason_fragment in decision.reason,
              str(decision))

    # --- The growth measure the budget resets on --------------------------
    transcript_directory = workspace / "death-resume-turn-count"
    transcript_directory.mkdir(parents=True, exist_ok=True)
    with supervisor_names_replaced(
            project_directory_for_working_directory=lambda _: transcript_directory):
        check("BUDGET: a session with no transcript at all counts no work",
              supervisor.substantive_turn_count_of_session_transcript(
                  "no-such-session", workspace) == 0)
        # A launch's prompt reaches the transcript as a user record — the record
        # first_user_turn_text reads. Counting bytes or lines would read that
        # bookkeeping as new work and hand the budget back for it.
        prompt_only = transcript_directory / "prompt-only.jsonl"
        prompt_only.write_text(
            json.dumps({"type": "user",
                        "message": {
                            "content":
                                supervisor.RESUME_PROMPT_WHEN_A_SESSION_ENDED_WITHOUT_A_HANDOFF}})
            + "\n", encoding="utf-8")
        check("BUDGET: a transcript holding only the resume prompt counts no work",
              supervisor.substantive_turn_count_of_session_transcript(
                  "prompt-only", workspace) == 0)
        with prompt_only.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(
                {"type": "assistant", "message": {"model": "claude", "content": "work"}}) + "\n")
        check("BUDGET: an assistant turn on top of it counts as work",
              supervisor.substantive_turn_count_of_session_transcript(
                  "prompt-only", workspace) == 1)

    # --- The loop: what the supervisor actually does at a death -----------
    directory = workspace / "death-resume"
    directory.mkdir(parents=True, exist_ok=True)
    no_branch_sync = lambda working_directory: (
        "branch sync: not a git checkout, nothing to sync")
    first_prompt = "You are the seat. Do the work."

    def supervise_a_seat_whose_sessions_die(case: str, deaths, stdin_isatty=True,
                                            adopted_session=None, handoffs_after_launches=(),
                                            resume_session_id="", seat_first_prompt=None,
                                            transcripts_before_the_supervisor=None):
        """Supervise a seat whose every session ends without a handoff.

        `deaths` is one (exit_code, substantive_turns_written) per launch, in
        order: the code that launch dies with, and how much work it writes to
        its transcript first. Every launch also writes the prompt it was given
        as a user record — the shape a launch's prompt takes on disk — so a
        case that writes no work still grows the file, and a budget measured in
        bytes would pass these cases while stopping nothing.

        A launch past the end of the script raises: that is the runaway the
        budget exists to stop, and it must fail a case rather than spin.

        `handoffs_after_launches` names launches, counted from 1, whose session
        writes a handoff after its work instead of dying, so a case can put a
        reincarnation between two deaths; the successor gets the id
        `successor-<generation>`. `transcripts_before_the_supervisor` maps a
        session id to the substantive turns its transcript already holds when
        the supervisor starts, which is what a startup resume resumes.
        """
        case_projects = workspace / f"death-resume-projects-{case}"
        case_projects.mkdir(parents=True, exist_ok=True)
        case_directory = directory / case
        case_directory.mkdir(parents=True, exist_ok=True)
        settings = supervisor.SupervisorSettings(
            agent=f"death{case}", working_directory=workspace,
            handoff_directory=case_directory, agent_command="unused-stub-agent",
            first_prompt=first_prompt if seat_first_prompt is None else seat_first_prompt,
            adopted_session=adopted_session, resume_session_id=resume_session_id)
        launches, state_at_each_launch = [], []
        for earlier_session_id, earlier_turns in (transcripts_before_the_supervisor or {}).items():
            with (case_projects / f"{earlier_session_id}.jsonl").open("w", encoding="utf-8") as stream:
                stream.write(json.dumps(
                    {"type": "user", "message": {"content": "do the thing"}}) + "\n")
                for _ in range(earlier_turns):
                    stream.write(json.dumps(
                        {"type": "assistant",
                         "message": {"model": "claude", "content": "work"}}) + "\n")
        real_wait_for_handoff = supervisor.wait_for_handoff

        def wait_for_handoff(process, *arguments):
            if len(launches) in handoffs_after_launches:
                return {"restart-counter": str(len(launches))}
            return real_wait_for_handoff(process, *arguments)

        def launch(agent_command, session_id, working_directory, prompt, **kwargs):
            if len(launches) >= len(deaths):
                raise RuntimeError(
                    f"launch {len(launches) + 1} past the {len(deaths)} this case scripted")
            exit_code, substantive_turns_written = deaths[len(launches)]
            launches.append((session_id, prompt, kwargs.get("resume")))
            state_at_each_launch.append(
                json.loads(settings.state_path.read_text(encoding="utf-8")))
            with (case_projects / f"{session_id}.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(
                    {"type": "user", "message": {"content": prompt}}) + "\n")
                for _ in range(substantive_turns_written):
                    stream.write(json.dumps(
                        {"type": "assistant",
                         "message": {"model": "claude", "content": "work"}}) + "\n")
            return StubLaunchedSession(exit_code)

        console, overran = io.StringIO(), ""
        with supervisor_names_replaced(
                launch_agent_session=launch,
                project_directory_for_working_directory=lambda _: case_projects,
                sync_working_branch_with_main=no_branch_sync,
                wait_for_handoff=wait_for_handoff,
                stop_session=lambda process: None,
                carry_over_to_successor=lambda settings, retiring, fields, generation: (
                    f"successor-{generation}", None),
                stdin_isatty=stdin_isatty), \
                contextlib.redirect_stdout(console):
            try:
                supervisor.supervise_sessions(settings)
            except RuntimeError as overrun:
                overran = str(overrun)
        state = supervisor.read_supervisor_state(settings.state_path)
        return SimpleNamespace(
            launches=launches, state_at_each_launch=state_at_each_launch,
            printed=console.getvalue(), overran=overran, state=state,
            record=supervisor.agent_exit_record_from_supervisor_state(state))

    # 1. A clean exit stops. The ruling: /exit or a headless turn ending is a
    # decision, not a crash, so it gets the seat stood down as before.
    clean = supervise_a_seat_whose_sessions_die("clean", [(0, 1)])
    check("TABLE IN THE LOOP: a clean exit stops the supervisor after one launch",
          len(clean.launches) == 1 and not clean.overran
          and "session ended without a handoff; supervisor stopping" in clean.printed,
          f"{clean.launches} {clean.overran} {clean.printed[-300:]}")
    check("TABLE IN THE LOOP: the clean stop still writes the exit record recovery reads",
          clean.record is not None and clean.record[0] == 0,
          f"{clean.state}")

    # 2. Each resuming row of the table, both spellings of each signal. With a
    # transcript that never grows, every one of them spends the budget and
    # stops after the original launch and one resume.
    for case, exit_code, row in (
            ("sigtermnegative", -15, "SIGTERM as subprocess reports it (-15)"),
            ("sigtermshell", 143, "SIGTERM as a shell reports it (143)"),
            ("sigkillnegative", -9, "SIGKILL as subprocess reports it (-9)"),
            ("sigkillshell", 137, "SIGKILL as a shell reports it (137)"),
            ("othernonzero", 3, "another non-zero status (3)")):
        died = supervise_a_seat_whose_sessions_die(case, [(exit_code, 0)] * 3)
        check(f"TABLE IN THE LOOP: {row} is resumed",
              len(died.launches) >= 2 and died.launches[1][2] is True
              and not died.overran,
              f"{died.launches} {died.overran} {died.printed[-300:]}")
        check(f"TABLE IN THE LOOP: the resume after {row} continues the same session",
              len({launched[0] for launched in died.launches}) == 1,
              str(died.launches))
        check(f"TABLE IN THE LOOP: the resume after {row} carries the resume prompt",
              died.launches[1][1] == supervisor.RESUME_PROMPT_WHEN_A_SESSION_ENDED_WITHOUT_A_HANDOFF
              and died.launches[0][1] == first_prompt,
              str(died.launches))

    # 3. An adopted session's code is None — this supervisor never owned it —
    # so its death stops the seat, and nothing is launched over it.
    adopted = supervise_a_seat_whose_sessions_die(
        "adopted", [(0, 0)], adopted_session=supervisor.AdoptedSession("adopted-session", 99999999))
    check("TABLE IN THE LOOP: an adopted session's death stops without launching anything",
          adopted.launches == [] and not adopted.overran
          and "exit code is unknown" in adopted.printed,
          f"{adopted.launches} {adopted.printed[-300:]}")
    check("TABLE IN THE LOOP: the adopted stop still writes the exit record, code unknown",
          adopted.record is not None
          and adopted.state.get(supervisor.AGENT_EXIT_CODE_STATE_KEY, "absent") is None,
          str(adopted.state))

    # 4. THE BUDGET STOPS A LOOP. A session that dies again and again without
    # adding a single turn gets its launch and one resume, and no more. The
    # script holds four deaths, so a third launch would be taken rather than
    # raising: the count below is the assertion, not merely that it stopped.
    looping = supervise_a_seat_whose_sessions_die("budget", [(-15, 0)] * 4)
    check("BUDGET: a seat whose transcript never grows gets its launch and one resume, no more",
          len(looping.launches) == 2 and not looping.overran,
          f"{looping.launches} {looping.overran} {looping.printed[-400:]}")
    check("BUDGET: the launch after the first is a resume of the same session",
          [launched[2] for launched in looping.launches] == [False, True]
          and len({launched[0] for launched in looping.launches}) == 1,
          str(looping.launches))
    check("BUDGET: the refusal says the resumes added nothing and names the cost",
          "added nothing to this session's transcript" in looping.printed
          and "costs money" in looping.printed, looping.printed[-400:])
    check("BUDGET: the stop that spends the budget still writes the exit record",
          looping.record is not None and looping.record[0] == -15, str(looping.state))
    check("BUDGET: a resume advances no generation and keeps the launched session id",
          looping.state.get("generation") == 0
          and looping.state.get(supervisor.LAUNCHED_SESSION_ID_STATE_KEY)
          == looping.launches[0][0],
          str(looping.state))
    check("BUDGET: no resume leaves an exit record behind, which would read as a stop",
          all(supervisor.AGENT_EXIT_CODE_STATE_KEY not in launched_state
              for launched_state in looping.state_at_each_launch),
          str(looping.state_at_each_launch))

    # 5. THE BUDGET RESETS. The second session does real work before dying, so
    # the resume that produced it is not a workless one and the budget comes
    # back whole: this seat gets three launches where the looping seat got
    # two. Without the reset a long-lived seat would eventually refuse to
    # recover at all.
    recovered = supervise_a_seat_whose_sessions_die(
        "budgetreset", [(-15, 2), (-15, 3), (-15, 0), (-15, 0), (-15, 0)])
    check("BUDGET RESETS: a resumed session that works before dying gets the budget back",
          len(recovered.launches) == 3 and not recovered.overran,
          f"{recovered.launches} {recovered.overran} {recovered.printed[-400:]}")
    check("BUDGET RESETS: and it is the same session resumed each time",
          len({launched[0] for launched in recovered.launches}) == 1
          and [launched[2] for launched in recovered.launches] == [False, True, True],
          str(recovered.launches))
    check("BUDGET RESETS: the run still ends on the budget rather than running on",
          "added nothing to this session's transcript" in recovered.printed
          and recovered.record is not None and recovered.record[0] == -15,
          f"{recovered.state} {recovered.printed[-400:]}")

    # 5a. A SUCCESSOR STARTS WITH THE BUDGET WHOLE. The predecessor spends its
    # one resume, works, and writes a handoff; the successor works and dies.
    # Found at c7419d4 by merge-lane-2's review of PR [The handoff-supervisor
    # resumes a session that died without a handoff](https://github.com/nedschorus/nedschorus/pull/651):
    # the successor was measured against its predecessor's turn count and
    # spent budget, refused, and the seat went dark.
    reincarnated = supervise_a_seat_whose_sessions_die(
        "budgetacrosshandoff", [(-15, 5), (0, 3), (-15, 2), (-15, 0), (-15, 0)],
        handoffs_after_launches=(2,))
    check("BUDGET ACROSS A HANDOFF: a successor that worked and died is resumed",
          [(launched[0], launched[2]) for launched in reincarnated.launches][:4]
          == [(reincarnated.launches[0][0], False), (reincarnated.launches[0][0], True),
              ("successor-1", False), ("successor-1", True)]
          and not reincarnated.overran,
          f"{reincarnated.launches} {reincarnated.overran} {reincarnated.printed[-400:]}")
    check("BUDGET ACROSS A HANDOFF: and the successor's own workless resume still ends the run",
          len(reincarnated.launches) == 4
          and "added nothing to this session's transcript" in reincarnated.printed,
          f"{reincarnated.launches} {reincarnated.printed[-400:]}")

    # 5b. A STARTUP RESUME IS CHARGED. --resume-session-id (which
    # recover-crashed-seats.py and the login-time restart pass) makes the first
    # launch a resume, and that launch is the one resume the budget allows.
    # Found at c7419d4 by mac-claude's and merge-lane-2's reviews: a startup
    # resume that did nothing was resumed a second time.
    startup_workless = supervise_a_seat_whose_sessions_die(
        "startupresumeworkless", [(-15, 0), (-15, 0)],
        resume_session_id="crashed-session",
        transcripts_before_the_supervisor={"crashed-session": 7})
    check("STARTUP RESUME: a --resume-session-id launch that does nothing is not resumed again",
          [(launched[0], launched[2]) for launched in startup_workless.launches]
          == [("crashed-session", True)] and not startup_workless.overran
          and "added nothing to this session's transcript" in startup_workless.printed,
          f"{startup_workless.launches} {startup_workless.overran} "
          f"{startup_workless.printed[-400:]}")
    startup_working = supervise_a_seat_whose_sessions_die(
        "startupresumeworking", [(-15, 2), (-15, 0)],
        resume_session_id="crashed-session",
        transcripts_before_the_supervisor={"crashed-session": 7})
    check("STARTUP RESUME: a --resume-session-id launch that works before dying is resumed",
          [(launched[0], launched[2]) for launched in startup_working.launches]
          == [("crashed-session", True), ("crashed-session", True)]
          and not startup_working.overran,
          f"{startup_working.launches} {startup_working.overran} "
          f"{startup_working.printed[-400:]}")
    # The by-hand resume: no first prompt, no handoff, no recorded exit, and a
    # real transcript on disk, so the first launch resumes it.
    by_hand_workless = supervise_a_seat_whose_sessions_die(
        "byhandresumeworkless", [(-15, 0), (-15, 0)], seat_first_prompt="",
        transcripts_before_the_supervisor={"last-real-session": 7})
    check("STARTUP RESUME: a by-hand resume that does nothing is not resumed again",
          [(launched[0], launched[2]) for launched in by_hand_workless.launches]
          == [("last-real-session", True)] and not by_hand_workless.overran,
          f"{by_hand_workless.launches} {by_hand_workless.overran} "
          f"{by_hand_workless.printed[-400:]}")
    by_hand_working = supervise_a_seat_whose_sessions_die(
        "byhandresumeworking", [(-15, 2), (-15, 0)], seat_first_prompt="",
        transcripts_before_the_supervisor={"last-real-session": 7})
    check("STARTUP RESUME: a by-hand resume that works before dying is resumed",
          [(launched[0], launched[2]) for launched in by_hand_working.launches]
          == [("last-real-session", True), ("last-real-session", True)]
          and not by_hand_working.overran,
          f"{by_hand_working.launches} {by_hand_working.overran} "
          f"{by_hand_working.printed[-400:]}")

    # 5c. A transcript cut off inside a multibyte character still counts. The
    # death path reads it before the exit record is written, so a decode error
    # there would crash the supervisor with the seat unrecorded. Raised as a
    # question by merge-lane-2's review and the Codex cell; nobody has seen
    # Claude Code write such a file, and tolerating it costs one argument.
    cut_directory = workspace / "cut-mid-character"
    cut_directory.mkdir(parents=True, exist_ok=True)
    cut_transcript = cut_directory / "cut-session.jsonl"
    cut_transcript.write_bytes(
        (json.dumps({"type": "assistant", "message": {"model": "claude", "content": "work"}})
         + "\n").encode("utf-8")
        + '{"type": "assistant", "message": {"content": "café'.encode("utf-8")[:-1])
    try:
        cut_count = supervisor.worth_resuming.substantive_turn_count(cut_transcript)
    except UnicodeDecodeError as decode_error:
        cut_count = decode_error
    check("CUT TRANSCRIPT: a transcript cut mid-character counts its whole turns, not a crash",
          cut_count == 1, repr(cut_count))

    # 6. The no-terminal refusal holds for a resume exactly as for a successor:
    # a resumed session inherits this supervisor's stdio, and without a
    # terminal it reads EOF at its first need for input (observed 2026-08-14).
    seatless = supervise_a_seat_whose_sessions_die("noterminal", [(-15, 0), (-15, 0)],
                                                   stdin_isatty=False)
    check("NO TERMINAL: a death that would be resumed is refused without a seat",
          len(seatless.launches) == 1 and not seatless.overran
          and "no terminal to seat a resumed session on" in seatless.printed,
          f"{seatless.launches} {seatless.printed[-400:]}")
    check("NO TERMINAL: the refusal still writes the exit record recovery reads",
          seatless.record is not None and seatless.record[0] == -15, str(seatless.state))


def run_by_hand_resume_cases(workspace: Path):
    """nedschorus#242 change 5 (ruled 2026-09-02, the #120 overview § Ruled:
    what happens when a restart fails): a by-hand `launch-claude-mac <seat>` of
    a seat with no waiting handoff and no recorded exit resumes its last
    transcript instead of minting an empty session.

    Measured 2026-09-02 on both machines, and the shape of the 2026-08-21 tmux
    death: three supervisors fell through to their first-prompt path and minted
    near-empty successors while three intact 1-2MB transcripts sat on disk. The
    first case below is that defect written down; it fails against the code as
    it stood before this change.

    The seat's project directory is stubbed rather than derived, so these cases
    never read or write the real ~/.claude/projects.
    """
    directory = workspace / "by-hand-resume"
    directory.mkdir(parents=True, exist_ok=True)
    projects = workspace / "by-hand-resume-projects"
    projects.mkdir(parents=True, exist_ok=True)

    def write_transcript(session_id: str, first_turn: str, assistant_turns: int):
        lines = [json.dumps({"type": "user", "message": {"content": first_turn}})]
        for _ in range(assistant_turns):
            lines.append(json.dumps(
                {"type": "assistant", "message": {"model": "claude", "content": "work"}}))
        path = projects / f"{session_id}.jsonl"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def settings_for(case: str):
        case_directory = directory / case
        case_directory.mkdir(parents=True, exist_ok=True)
        return supervisor.SupervisorSettings(
            agent=f"byhand{case}", working_directory=workspace,
            handoff_directory=case_directory, agent_command="unused-stub-agent",
            first_prompt="")

    no_branch_sync = lambda working_directory: (
        "branch sync: not a git checkout, nothing to sync")

    def launch_once(settings):
        """(session_id, prompt, resume) of the one launch, which then ends."""
        launched = []

        def launch(agent_command, session_id, working_directory, prompt, **kwargs):
            launched.append((session_id, prompt, kwargs.get("resume")))
            return StubLaunchedSession(0)

        with supervisor_names_replaced(
                launch_agent_session=launch,
                project_directory_for_working_directory=lambda _: projects,
                sync_working_branch_with_main=no_branch_sync), \
                contextlib.redirect_stdout(io.StringIO()):
            supervisor.supervise_sessions(settings)
        return launched[0] if launched else (None, None, None)

    # 1. The defect: real work on disk, nothing to say the seat stopped on
    # purpose. Before this change the supervisor minted a new id and told the
    # agent no handoff exists.
    crashed = write_transcript("crashed-with-real-work", "do the thing", assistant_turns=4)
    settings = settings_for("crash")
    supervisor.write_supervisor_state(settings.state_path, {"generation": 1})
    session_id, prompt, resume = launch_once(settings)
    check("BY HAND: a seat with no handoff and no recorded exit resumes its last transcript",
          session_id == crashed.stem and resume is True,
          (session_id, resume, crashed.stem))
    check("BY HAND: and the resumed session is told the previous one ended without a handoff",
          prompt == supervisor.RESUME_PROMPT_WHEN_A_SESSION_ENDED_WITHOUT_A_HANDOFF
          and "No handoff exists yet" not in (prompt or ""),
          prompt)

    # 2. A recorded exit means the seat was stopped under supervision, not
    # crashed. recover-crashed-seats.py reads the same record the same way:
    # any record counts, whatever its code.
    settings = settings_for("recorded-exit")
    supervisor.write_supervisor_state(settings.state_path, {
        "generation": 1,
        supervisor.AGENT_EXIT_CODE_STATE_KEY: 0,
        supervisor.AGENT_EXIT_RECORDED_AT_STATE_KEY: "2026-01-01T00:00:00+00:00"})
    session_id, prompt, resume = launch_once(settings)
    check("BY HAND: a seat carrying a recorded exit still gets a fresh session",
          resume is not True and session_id != crashed.stem,
          (session_id, resume))
    check("BY HAND: and that fresh session gets the no-handoff prompt",
          "No handoff exists yet" in (prompt or ""), prompt)

    # 3. Nothing worth resuming: every transcript is a session this machinery
    # minted that then did nothing. Starting fresh is right, and the run must
    # not resume one of them.
    empty_projects = workspace / "by-hand-resume-projects-empty"
    empty_projects.mkdir(parents=True, exist_ok=True)
    (empty_projects / "failed-successor.jsonl").write_text(
        json.dumps({"type": "user",
                    "message": {"content": "You are x. No handoff exists yet; ask what "
                                           "to work on."}}) + "\n",
        encoding="utf-8")
    settings = settings_for("nothing-worth-resuming")
    supervisor.write_supervisor_state(settings.state_path, {"generation": 1})
    launched = []

    def launch_empty(agent_command, session_id, working_directory, prompt, **kwargs):
        launched.append((session_id, prompt, kwargs.get("resume")))
        return StubLaunchedSession(0)

    with supervisor_names_replaced(
            launch_agent_session=launch_empty,
            project_directory_for_working_directory=lambda _: empty_projects,
            sync_working_branch_with_main=no_branch_sync), \
            contextlib.redirect_stdout(io.StringIO()):
        supervisor.supervise_sessions(settings)
    check("BY HAND: a seat whose every transcript is an empty successor starts fresh",
          launched and launched[0][2] is not True
          and launched[0][0] != "failed-successor",
          str(launched))

    # 4. An unconsumed handoff is the fresher truth and boot-ignition takes it,
    # exactly as before: the by-hand resume must not steal a waiting handoff.
    settings = settings_for("waiting-handoff")
    supervisor.write_supervisor_state(settings.state_path, {"generation": 1})
    settings.handoff_path.write_text(
        "# Handoff\nrestart-counter: 4\nnext-step: carry on\n", encoding="utf-8")
    session_id, prompt, resume = launch_once(settings)
    check("BY HAND: a waiting handoff still wins, and is not resumed over",
          resume is not True and session_id != crashed.stem,
          (session_id, resume))

    # 5. --resume-session-id, the flag scripts/recover-crashed-seats.py and the
    # login-time restart pass. No case ran it through the loop until the
    # 2026-09-21 ruling renamed the flag it sets, so this one holds the path
    # that rename touched: the named session is resumed, not a fresh id, and a
    # handoff waiting on disk is marked consumed rather than igniting over it.
    settings = settings_for("resume-session-id")
    settings.resume_session_id = "session-named-by-recovery"
    supervisor.write_supervisor_state(settings.state_path, {"generation": 1})
    settings.handoff_path.write_text(
        "# Handoff\nrestart-counter: 4\nnext-step: carry on\n", encoding="utf-8")
    session_id, prompt, resume = launch_once(settings)
    check("RESUME-SESSION-ID: the first launch resumes the session the flag names",
          session_id == "session-named-by-recovery" and resume is True,
          (session_id, resume))
    check("RESUME-SESSION-ID: and tells it the previous session ended without a handoff",
          prompt == supervisor.RESUME_PROMPT_WHEN_A_SESSION_ENDED_WITHOUT_A_HANDOFF, prompt)
    check("RESUME-SESSION-ID: a waiting handoff is marked consumed, not ignited over the resume",
          supervisor.read_supervisor_state(settings.state_path).get("consumed_counter") == 4,
          str(supervisor.read_supervisor_state(settings.state_path)))


with fixture.handoff_supervisor_suite_workspace() as workspace:
    run_exit_handoff_cases(workspace)
    run_dont_restart_without_a_terminal_case(workspace)
    run_no_seat_recycle_refusal_case(workspace)
    run_agent_exit_record_cases(workspace)
    run_handoff_worktree_cleanup_cases(workspace)
    run_resume_after_a_death_without_a_handoff_cases(workspace)
    run_by_hand_resume_cases(workspace)

fixture.print_summary_and_exit_nonzero_if_any_case_failed()
