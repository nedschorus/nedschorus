#!/usr/bin/env python3
"""Tests for handoff-supervisor.py: a supervisor's hold on its seat, and the
session it launches.

The supervisor lock and the process-identity check behind it; adopting a
session already running; the appended system prompt and the seat environment
a launched session gets; and the agent-binary update before each launch,
under the machine-wide update lock. The supervisor's other cases are in
handoff-supervisor-successor-prompt-test.py and
handoff-supervisor-session-end-and-resume-test.py, beside this file.

Run: python3 nc-systems/handoff/tests/handoff-supervisor-session-launch-and-seat-lock-test.py

Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import fcntl
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

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
a_process_that_looks_like_a_supervisor = fixture.a_process_that_looks_like_a_supervisor
sandboxed_update_lock_path = fixture.sandboxed_update_lock_path


def run_adoption_cases(workspace: Path):
    """Adopting a running session is what lets a hand-started agent reincarnate:
    a supervisor normally owns only the process it launched itself."""
    # A process that has already exited: if the startup check stopped firing,
    # adopting it ends the supervisor at once instead of watching a live process.
    exited = subprocess.Popen(["true"])  # pylint: disable=consider-using-with
    exited.wait(timeout=10)
    for value in (None, "", "   "):
        environment = dict(os.environ)
        environment.pop("CLAUDE_CODE_TASK_LIST_ID", None)
        if value is not None:
            environment["CLAUDE_CODE_TASK_LIST_ID"] = value
        for arguments in ([], ["--resume-session-id", "retiring-session"],
                          ["--adopt-session-id", "live-session",
                           "--adopt-process-id", str(exited.pid)]):
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "--agent", "unpinned",
                 "--cd", str(workspace), "--handoff-dir", str(workspace / "unpinned"),
                 "--agent-command", "true", "--agent-update-timeout-seconds", "0",
                 *arguments],
                env=environment, capture_output=True, text=True, check=False,
                stdin=subprocess.DEVNULL, timeout=60,
            )
            check(f"unpinned startup is refused before watching: {value!r}, {arguments}",
                  result.returncode == 2
                  and "startup stopped" in result.stderr
                  and "not started by a launcher that pins its task list" in result.stderr
                  and "CLAUDE_CODE_TASK_LIST_ID is unset or empty" in result.stderr
                  and "scripts/launch-claude-mac" in result.stderr
                  and "scripts/launch-claude-ubuntu" in result.stderr
                  and "start it on the Mac" in result.stderr
                  and not (workspace / "unpinned").exists(), result.stderr)
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--check", "--agent", "unpinned",
             "--handoff-dir", str(workspace / "unpinned")],
            env=environment, capture_output=True, text=True, check=False,
            stdin=subprocess.DEVNULL, timeout=60,
        )
        check(f"read-only check needs no task-list pin: {value!r}",
              result.returncode == 1 and "startup stopped" not in result.stderr,
              result.stderr)

    # Not a context manager: the point is a process this test does NOT own a
    # handle to in the supervisor, which is what adoption exists for.
    sleeper = subprocess.Popen(  # pylint: disable=consider-using-with
        [sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        adopted = supervisor.AdoptedSession("some-session-id", sleeper.pid)
        check("an adopted live process reads as running", adopted.poll() is None)
        adopted.terminate()
        sleeper.wait(timeout=10)
        check("an adopted process can be terminated", adopted.poll() == 0)
        check("terminating an already-gone process is not an error",
              adopted.terminate() is None)
    finally:
        if sleeper.poll() is None:
            sleeper.kill()
            sleeper.wait()

    gone = supervisor.AdoptedSession("some-session-id", 99999999)
    check("a process id that does not exist reads as gone", gone.poll() == 0)

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--agent", "adopter",
         "--handoff-dir", str(workspace), "--adopt-session-id", "an-id"],
        capture_output=True, text=True, check=False,
    )
    check("adopting without a process id is refused", result.returncode == 2, result.stderr)

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--agent", "adopter", "--cd", str(workspace),
         "--handoff-dir", str(workspace), "--adopt-session-id", "an-id",
         "--adopt-process-id", "99999999"],
        capture_output=True, text=True, check=False,
    )
    check("adopting a process that is already gone is refused",
          result.returncode == 2 and "already gone" in result.stderr, result.stderr)


def run_process_identity_cases(workspace: Path):
    """A supervisor is judged by its process, not by how fresh its heartbeat is
    (nedschorus#242 change 1).

    The heartbeat cannot answer "is one running now". It is stamped every
    HEARTBEAT_INTERVAL_SECONDS, and the rule this replaced read it as fresh for
    sixty seconds afterwards, so for a full minute after a supervisor died the
    file still said it was alive — and that minute is exactly when the login
    restart runs.
    A bare process-id check cannot answer it either: ids are reused across the
    very reboot this serves, and the lock file holding one outlives the boot.
    """
    for impossible in (0, -1, -12345):
        alive, detail = supervisor.process_is_supervisor_for_agent(impossible, "x")
        check(f"process id {impossible} is not a supervisor", not alive, detail)

    alive, detail = supervisor.process_is_supervisor_for_agent(99999999, "x")
    check("a process id that is not running is not a supervisor", not alive, detail)

    # Process-id reuse, which is the whole reason a bare check will not do.
    unrelated = subprocess.Popen(  # pylint: disable=consider-using-with
        [sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        alive, detail = supervisor.process_is_supervisor_for_agent(unrelated.pid, "x")
        check("a live process that is not a supervisor is not one, however live it is",
              not alive and "not a supervisor" in detail, detail)
    finally:
        unrelated.kill()
        unrelated.wait()

    # ps is a program and a program can fail to run — a fork or exec failure
    # under load, which this machine reaches when several sweeps run at once.
    # That is a third answer, and filing it under "not running" makes a
    # confident false statement about a live process (found in review of
    # a82b49e). The reader keeps the three apart.
    ps_could_not_run = lambda process_id: (None, False)
    ps_says_no_such_process = lambda process_id: (None, True)

    # The real reader's own three answers, with nothing patched inside it: a
    # live process, a dead one, and ps not running at all. The last is driven
    # by making ps unfindable, which is a genuine OSError out of
    # subprocess.run — the same path a fork or exec failure under load takes.
    # Injected readers cannot cover this, so without it the defect found in
    # review of a82b49e could be reintroduced in the reader and no case would
    # notice.
    line, answered = supervisor.read_process_command_line(os.getpid())
    check("the real reader reads this process's own command line",
          answered and line is not None and "python" in line.lower(), (answered, line))
    line, answered = supervisor.read_process_command_line(99999999)
    check("the real reader says ps ANSWERED for a process that is not there",
          answered and line is None, (answered, line))
    real_search_path = os.environ.get("PATH", "")
    try:
        os.environ["PATH"] = ""
        line, answered = supervisor.read_process_command_line(os.getpid())
        check("the real reader says ps did NOT answer when ps cannot be run",
              not answered and line is None, (answered, line))
    finally:
        os.environ["PATH"] = real_search_path
    check("and the reader works again once ps is findable",
          supervisor.read_process_command_line(os.getpid())[1])

    # The OTHER way ps fails to answer: it runs and never finishes. Driven with
    # a real `ps` early on PATH that really hangs, a real subprocess.run
    # timeout, and a real TimeoutExpired — nothing patched inside the reader,
    # for the same reason as the block above.
    #
    # This case exists because mutation 18 of the #328 self-check SURVIVED:
    # dropping subprocess.SubprocessError from the reader's except tuple leaves
    # TimeoutExpired escaping the reader, which kills a supervisor at startup
    # instead of reporting "could not ask" and falling back to os.kill. Nothing
    # exercised the timeout, so nothing noticed. The 15 is now a module
    # constant precisely so this case can lower it; a default argument could not
    # be lowered from here, which is the trap the NOTE in
    # process_is_supervisor_for_agent describes.
    hanging_ps_directory = workspace / "hanging-ps"
    hanging_ps_directory.mkdir()
    hanging_ps = hanging_ps_directory / "ps"
    # exec, so the reader's kill at its timeout reaches the sleep itself rather
    # than leaving it running for half a minute after this case.
    hanging_ps.write_text("#!/bin/sh\nexec sleep 30\n", encoding="utf-8")
    hanging_ps.chmod(0o755)
    real_read_timeout = supervisor.PROCESS_COMMAND_LINE_READ_TIMEOUT_SECONDS
    try:
        os.environ["PATH"] = f"{hanging_ps_directory}:{real_search_path}"
        supervisor.PROCESS_COMMAND_LINE_READ_TIMEOUT_SECONDS = 0.25
        started_waiting = time.monotonic()
        line, answered = supervisor.read_process_command_line(os.getpid())
        waited = time.monotonic() - started_waiting
    finally:
        os.environ["PATH"] = real_search_path
        supervisor.PROCESS_COMMAND_LINE_READ_TIMEOUT_SECONDS = real_read_timeout
    check("a ps that hangs is reported as not having answered, not as 'no such process'",
          not answered and line is None, (answered, line))
    check("and the reader gives up at the timeout instead of waiting out ps",
          waited < 5, waited)
    check("and the timeout is a module constant the suite can lower, not a literal",
          supervisor.PROCESS_COMMAND_LINE_READ_TIMEOUT_SECONDS == 15,
          supervisor.PROCESS_COMMAND_LINE_READ_TIMEOUT_SECONDS)

    alive, detail = supervisor.process_is_supervisor_for_agent(
        99999999, "x", read_command_line=ps_says_no_such_process)
    check("ps answering 'no such process' means not a supervisor",
          not alive and "not running" in detail, detail)

    # os.kill answers EXISTENCE and cannot fail to: ProcessLookupError means
    # gone. So a lock left by a crashed supervisor, holding an id that no longer
    # exists, is still recognised as stale with no ps at all. Without this the
    # fail-closed rule wedged the ordinary post-crash state — the very state the
    # lock's reclaim exists to serve.
    check("os.kill says a process that is not there is not there",
          not supervisor.process_exists_by_signal(99999999))
    check("and says this process is",
          supervisor.process_exists_by_signal(os.getpid()))
    # A process that exists but cannot be signalled still exists. Process 1 is
    # root-owned on both machines, so os.kill raises PermissionError for it
    # while the process is plainly there; reading that as "gone" would be the
    # unsafe direction. Signal 0 sends nothing, so this probe is inert.
    #
    # LIMIT, stated rather than discovered: this case is VACUOUS under root.
    # As root os.kill(1, 0) simply succeeds, so the assertion passes through
    # the success branch and the PermissionError branch it was written for is
    # never reached. It is honest for this fleet, which runs as nedlern on
    # ned-box and el on the Mac, and it is not a check anyone should trust
    # after a change to who the seats run as. main-gatekeeper-test.py detects
    # the same condition and skips; here the case is kept unconditional because
    # passing vacuously is harmless and disappearing silently is not.
    check("a process that exists but cannot be signalled still counts as existing",
          supervisor.process_exists_by_signal(1))

    alive, detail = supervisor.process_is_supervisor_for_agent(
        99999999, "x", read_command_line=ps_could_not_run)
    check("with no ps, a dead id is still answered: not a supervisor",
          not alive and "os.kill" in detail, detail)

    # Only a process that really exists, and cannot be identified, is assumed
    # to be a supervisor.
    unidentifiable = subprocess.Popen(  # pylint: disable=consider-using-with
        [sys.executable, "-c", "import time; time.sleep(60)"])
    complaints = io.StringIO()
    try:
        with contextlib.redirect_stderr(complaints):
            alive, detail = supervisor.process_is_supervisor_for_agent(
                unidentifiable.pid, "x", read_command_line=ps_could_not_run)
        check("a live but unidentifiable process IS assumed to be the supervisor",
              alive, detail)
        check("and it says it cannot tell, rather than claiming the process is gone",
              "cannot tell" in detail and "not running" not in detail, detail)
        check("and the wedge is not mute: it says so on stderr, naming ps",
              "could not identify" in complaints.getvalue()
              and "ps could not be run" in complaints.getvalue(),
              complaints.getvalue())
        check("and names the way out, since whoever asked is now stuck on an assumption",
              "lock is removed" in complaints.getvalue(), complaints.getvalue())
        # The remedy is the same for every caller; the CONSEQUENCE is not. This
        # sentence once said "this seat will not start", which is true of
        # claim_supervisor_lock and of nothing else that asks — the other
        # callers refuse a repair, stop an agent, or set an exit code
        # (#328 follow-up round, nedschorus#242).
        check("and does not claim a consequence only one of the callers has",
              "this seat will not start" not in complaints.getvalue(),
              complaints.getvalue())
    finally:
        unidentifiable.kill()
        unidentifiable.wait()

    with a_process_that_looks_like_a_supervisor(workspace, "identity-seat") as running:
        alive, detail = supervisor.process_is_supervisor_for_agent(
            running.pid, "identity-seat")
        check("a running supervisor for this agent is recognised", alive, detail)
        # Seat names are letters, digits, hyphen and underscore, so the agent
        # argument is matched whole. A substring test would read this process
        # as the supervisor of a different seat whose name it merely begins.
        for other in ("identity-seat-2", "identity", "dentity-seat", "IDENTITY-SEAT"):
            alive, detail = supervisor.process_is_supervisor_for_agent(running.pid, other)
            check(f"it is not the supervisor of {other}", not alive, detail)

    check("and once it is gone it is no longer recognised",
          not supervisor.process_is_supervisor_for_agent(running.pid, "identity-seat")[0])

    # argparse accepts --agent=NAME as well as --agent NAME. No launcher writes
    # it that way today (checked across both launchers and both recovery
    # tools), but a supervisor started by hand that way must still be
    # recognised — otherwise its lock reads as stale and a second supervisor
    # starts on the same agent, which is what the lock exists to prevent.
    with a_process_that_looks_like_a_supervisor(
            workspace, "equals-seat", equals_form=True) as running:
        alive, detail = supervisor.process_is_supervisor_for_agent(
            running.pid, "equals-seat")
        check("a supervisor started with --agent=NAME is recognised too", alive, detail)

    # A python process running some other script for the same agent is not a
    # supervisor: the script name has to match as well as the agent.
    other_script = workspace / "not-the-supervisor.py"
    other_script.write_text("import time\ntime.sleep(120)\n", encoding="utf-8")
    impostor = subprocess.Popen(  # pylint: disable=consider-using-with
        [sys.executable, str(other_script), "--agent", "identity-seat"])
    try:
        alive, detail = supervisor.process_is_supervisor_for_agent(
            impostor.pid, "identity-seat")
        check("another script run with the same --agent is not the supervisor",
              not alive, detail)
    finally:
        impostor.kill()
        impostor.wait()


def run_lock_cases(workspace: Path):
    """Two supervisors on one agent would each kill the session and each launch
    a successor, so the second must refuse to start."""
    lock_path = workspace / "locktest-supervisor.lock"
    check("the lock is claimable when free", supervisor.claim_supervisor_lock(lock_path))
    check("the lock records the holder", lock_path.read_text().strip() == str(os.getpid()))
    check("the same process may re-enter its own lock", supervisor.claim_supervisor_lock(lock_path))

    lock_path.write_text("99999999\n", encoding="utf-8")
    check("a lock held by a dead process is reclaimed", supervisor.claim_supervisor_lock(lock_path))

    # Changed with nedschorus#242 change 1: a live process id is not enough.
    # The lock file survives a reboot, and process ids are reused across
    # exactly that reboot, so a stale lock whose id now belongs to something
    # else would refuse the very supervisor the login restart just asked for.
    # What blocks a second supervisor is a live supervisor FOR THIS AGENT.
    live_stranger = subprocess.Popen(  # pylint: disable=consider-using-with
        [sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        lock_path.write_text(f"{live_stranger.pid}\n", encoding="utf-8")
        check("a lock whose id now belongs to an unrelated live process is reclaimed",
              supervisor.claim_supervisor_lock(lock_path))
    finally:
        live_stranger.kill()
        live_stranger.wait()

    with a_process_that_looks_like_a_supervisor(workspace, "locktest") as running:
        lock_path.write_text(f"{running.pid}\n", encoding="utf-8")
        check("a lock held by a live supervisor for this agent blocks a second one",
              not supervisor.claim_supervisor_lock(lock_path))

    # The same lock, the same id, once that supervisor is gone.
    check("and is reclaimed once that supervisor has exited",
          supervisor.claim_supervisor_lock(lock_path))

    # Both callers of the identity check must fail CLOSED when ps cannot be
    # asked. For the lock that means refusing to claim: a seat that stays down
    # is visible and recoverable, while two supervisors on one agent each kill
    # the session and each launch a successor. This is the caller with nothing
    # behind it — assess_seat still has the tmux check ahead of it, this has
    # none (found in review of a82b49e).
    with a_process_that_looks_like_a_supervisor(workspace, "locktest") as running:
        lock_path.write_text(f"{running.pid}\n", encoding="utf-8")
        real_identity_check = supervisor.process_is_supervisor_for_agent
        try:
            supervisor.process_is_supervisor_for_agent = (
                lambda process_id, agent_name, **_: real_identity_check(
                    process_id, agent_name,
                    read_command_line=lambda _p: (None, False)))
            check("a lock is NOT reclaimed when ps could not say who holds it",
                  not supervisor.claim_supervisor_lock(lock_path))
            check("and the live supervisor still holds it",
                  lock_path.read_text().strip() == str(running.pid),
                  lock_path.read_text())
        finally:
            supervisor.process_is_supervisor_for_agent = real_identity_check

    # THE WEDGE, which fail-closed-everywhere would have shipped. A crashed seat
    # leaves a stale lock holding a dead id, and claim_supervisor_lock runs when
    # a supervisor STARTS. Refusing to reclaim that lock whenever ps is
    # unavailable means no supervisor can start for the seat at all — breaking
    # exactly the state the reclaim exists to serve. os.kill answers it.
    lock_path.write_text("99999999\n", encoding="utf-8")
    real_identity_check = supervisor.process_is_supervisor_for_agent
    try:
        supervisor.process_is_supervisor_for_agent = (
            lambda process_id, agent_name, **_: real_identity_check(
                process_id, agent_name, read_command_line=lambda _p: (None, False)))
        check("a crashed seat's stale lock is still reclaimed when ps cannot be run",
              supervisor.claim_supervisor_lock(lock_path))
    finally:
        supervisor.process_is_supervisor_for_agent = real_identity_check

    # The same unknown answer through supervisor_liveness: a supervisor that
    # cannot be ruled out is reported as watching, so nothing recovers over it.
    unknown_state_path = workspace / "unknown-supervisor-state.json"
    unknown_lock_path = workspace / "unknown-supervisor.lock"
    supervisor.stamp_heartbeat(unknown_state_path, {"launched_session_id": "s"})
    # A process that really exists, so existence is not what is unknown here —
    # only its identity is. A dead id would now be answered outright.
    unidentifiable = subprocess.Popen(  # pylint: disable=consider-using-with
        [sys.executable, "-c", "import time; time.sleep(60)"])
    unknown_lock_path.write_text(f"{unidentifiable.pid}\n", encoding="utf-8")
    real_identity_check = supervisor.process_is_supervisor_for_agent
    try:
        supervisor.process_is_supervisor_for_agent = (
            lambda process_id, agent_name, **_: real_identity_check(
                process_id, agent_name, read_command_line=lambda _p: (None, False)))
        with contextlib.redirect_stderr(io.StringIO()):
            alive, explanation = supervisor.supervisor_liveness(unknown_state_path)
        check("a supervisor that cannot be ruled out reads as watching",
              alive and "cannot tell" in explanation, explanation)

        # And the dead-id case through the same path: answered, not assumed.
        unknown_lock_path.write_text("99999999\n", encoding="utf-8")
        alive, explanation = supervisor.supervisor_liveness(unknown_state_path)
        check("a dead id reads as no supervisor even when ps cannot be run",
              not alive and "os.kill" in explanation, explanation)
    finally:
        supervisor.process_is_supervisor_for_agent = real_identity_check
        unidentifiable.kill()
        unidentifiable.wait()
    unknown_state_path.unlink(missing_ok=True)
    unknown_lock_path.unlink(missing_ok=True)

    # The agent name comes from the lock's own filename, so a lock that does
    # not follow the convention still reclaims rather than wedging a seat.
    odd_lock = workspace / "no-convention.lock"
    odd_lock.write_text("99999999\n", encoding="utf-8")
    check("a lock whose name carries no agent is still reclaimable",
          supervisor.claim_supervisor_lock(odd_lock))
    odd_lock.unlink(missing_ok=True)

    lock_path.write_text("not a number\n", encoding="utf-8")
    check("an unreadable lock is reclaimed", supervisor.claim_supervisor_lock(lock_path))
    lock_path.unlink(missing_ok=True)



def run_appended_system_prompt_cases(workspace: Path):
    """Every launched session gets --append-system-prompt-file, and a missing
    file degrades the session rather than losing the seat.

    The supervisor owns this flag rather than the launchers because a
    supervisor is started three ways -- launch-claude-mac, launch-claude-ubuntu
    and resupervise-seat.py -- and a flag living in the launchers would leave a
    recovered seat silently running without the appended text.
    """
    def boot_once(name: str, extra_arguments: list):
        """Boot-ignite once with an argument-recording stub; return its argv,
        one argument per line, and the supervisor's stderr."""
        handoff_directory = workspace / name
        handoff_directory.mkdir(parents=True, exist_ok=True)
        (handoff_directory / f"{name}-handoff.md").write_text(
            "written-at: 2026-08-31T00:00:00Z\nnext-step: carry on\nrestart-counter: 5\n",
            encoding="utf-8",
        )
        supervisor.write_supervisor_state(
            handoff_directory / f"{name}-supervisor-state.json",
            {"consumed_counter": 4, "launched_session_id": "no-such-session", "generation": 4},
        )
        record_path = handoff_directory / "argv.txt"
        stub_agent = handoff_directory / "stub-agent"
        # Records EVERY argument, one per line -- the boot-ignition case
        # records only the last one, which cannot see a flag.
        stub_agent.write_text(
            "#!/bin/sh\n"
            "exec >/dev/null 2>&1\n"
            f"printf '%s\\n' \"$@\" > '{record_path}'\n"
            "exit 0\n",
            encoding="utf-8",
        )
        stub_agent.chmod(0o755)
        finished = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--agent", name, "--cd", str(workspace),
             "--handoff-dir", str(handoff_directory),
             "--agent-command", str(stub_agent), "--agent-update-timeout-seconds", "0"] + extra_arguments,
            capture_output=True, text=True, check=False,
            stdin=subprocess.DEVNULL, timeout=60,
        )
        argv = record_path.read_text(encoding="utf-8") if record_path.is_file() else ""
        return argv, finished.stderr

    def warning_lines_about_no_separator(stderr: str) -> list:
        return [line for line in stderr.splitlines()
                if line.startswith("handoff-supervisor: no --- line")]

    # A file with no `---` line is all agent text: it goes to the CLI whole,
    # through its own path, as every file did before the split -- with a
    # warning, because the file may have lost the line that keeps editor notes
    # out of the seats.
    prompt_file = workspace / "appended-system-prompt.md"
    prompt_file.write_text("You may commission subagents on your own initiative.\n",
                           encoding="utf-8")

    argv, stderr = boot_once("appendon", ["--agent-append-system-prompt-file", str(prompt_file)])
    check("the launched session carries --append-system-prompt-file",
          "--append-system-prompt-file" in argv.splitlines(), argv)
    check("a file with no --- line is sent whole, through the path it was given",
          str(prompt_file) in argv.splitlines(), argv)
    check("and the supervisor prints exactly one warning line saying so",
          len(warning_lines_about_no_separator(stderr)) == 1
          and str(prompt_file) in warning_lines_about_no_separator(stderr)[0], stderr)
    check("and writes no agent-part file for it",
          not (workspace / "appendon" / "appendon-appended-system-prompt-agent-part.md").exists())
    # The prompt is read by position in the boot-ignition case and by every
    # reader of this command; a flag appended after it would BE the prompt.
    lines = [line for line in argv.splitlines() if line]
    check("the prompt is still the last argument, after the new flag",
          lines and lines[-1] not in ("--append-system-prompt-file", str(prompt_file)),
          repr(lines[-3:] if lines else lines))

    # A file with notes above its `---` line: only the part below reaches the
    # session. Before this, the whole file went, and every seat's system prompt
    # carried the notes to editors, "Keep it SHORT" included (observed
    # 2026-09-16 in the cold-read-research seat; user-ruled "fix 2").
    split_file = workspace / "appended-system-prompt-with-notes.md"
    split_file.write_text(
        "# Notes heading\n"
        "\n"
        "Keep it SHORT. EDITOR-NOTE-MARKER\n"
        "\n"
        "---\n"
        "\n"
        "\n"
        "AGENT-TEXT-MARKER: you may commission subagents.\n"
        "\n"
        "---\n"
        "SECOND-SECTION-MARKER after a later --- line, still agent text.\n",
        encoding="utf-8",
    )
    argv, stderr = boot_once("appendsplit", ["--agent-append-system-prompt-file", str(split_file)])
    agent_part_path = workspace / "appendsplit" / "appendsplit-appended-system-prompt-agent-part.md"
    argument_lines = argv.splitlines()
    flag_value = (argument_lines[argument_lines.index("--append-system-prompt-file") + 1]
                  if "--append-system-prompt-file" in argument_lines[:-1] else "")
    check("a file with a --- line is sent through the supervisor's agent-part file",
          flag_value == str(agent_part_path), argv)
    check("and not through its own path",
          str(split_file) not in argument_lines, argv)
    sent = agent_part_path.read_text(encoding="utf-8") if agent_part_path.is_file() else ""
    check("the text sent excludes everything above the --- line",
          sent.strip() != ""
          and "EDITOR-NOTE-MARKER" not in sent and "Notes heading" not in sent, sent)
    check("the text sent is what is below it, from its first non-blank line",
          sent.startswith("AGENT-TEXT-MARKER: you may commission subagents.\n"), repr(sent))
    check("the split is at the FIRST --- line: a later one stays in the text sent",
          "---\nSECOND-SECTION-MARKER" in sent, repr(sent))
    check("a file with a --- line launches with no warning",
          not warning_lines_about_no_separator(stderr), stderr)

    # The real committed file, through the default path, end to end.
    argv, stderr = boot_once("appendcommitted", [])
    agent_part_path = (workspace / "appendcommitted"
                       / "appendcommitted-appended-system-prompt-agent-part.md")
    sent = agent_part_path.read_text(encoding="utf-8") if agent_part_path.is_file() else ""
    check("by default the committed file is sent through the agent-part file",
          str(agent_part_path) in argv.splitlines(), argv)
    check("what the committed file sends carries none of its notes to editors",
          sent.strip() != "" and "Everything above this line is a note" not in sent,
          repr(sent[:300]))

    argv, stderr = boot_once("appendoff", ["--agent-append-system-prompt-file", ""])
    check("an empty value launches with no such flag",
          "--append-system-prompt-file" not in argv.splitlines(), argv)

    missing = workspace / "no-such-appended-prompt.md"
    argv, stderr = boot_once("appendmissing", ["--agent-append-system-prompt-file", str(missing)])
    check("a missing file does not lose the seat -- the session still launches",
          argv.strip() != "", "the stub agent recorded nothing, so no session launched")
    check("a missing file launches with no such flag",
          "--append-system-prompt-file" not in argv.splitlines(), argv)


def run_appended_system_prompt_agent_part_cases(workspace: Path):
    """Where agent_part_of_appended_system_prompt splits a file, on the committed
    file and on made-up ones, and the launch-site fallbacks that keep a launch
    from ever failing over the appended text."""
    split = supervisor.agent_part_of_appended_system_prompt

    committed_text = supervisor.DEFAULT_APPENDED_SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    agent_text, separator_found = split(committed_text)
    check("the committed appended-system-prompt file has a --- line", separator_found)
    check("its agent part does not contain the notes' closing sentence",
          "Everything above this line is a note" not in agent_text, agent_text)
    last_committed_line = [line for line in committed_text.splitlines() if line.strip()][-1]
    check("its agent part runs to the end of the file",
          agent_text.rstrip("\n").endswith(last_committed_line), repr(agent_text[-200:]))

    agent_text, separator_found = split("notes\n  ---\t\n\n   \nagent\n\nmore agent\n")
    check("a --- line with surrounding whitespace is the separator",
          separator_found and agent_text == "agent\n\nmore agent\n", repr(agent_text))

    for lookalike in ("----", "--- notes", "- - -", "`---`"):
        text = f"notes\n{lookalike}\nagent\n"
        agent_text, separator_found = split(text)
        check(f"{lookalike!r} is not the separator, so the text comes back whole",
              not separator_found and agent_text == text, repr(agent_text))

    agent_text, separator_found = split("no separator here\n")
    check("text with no --- line comes back whole, and says so",
          not separator_found and agent_text == "no separator here\n", repr(agent_text))

    # The launch-site fallbacks, called directly.
    for_launch = supervisor.appended_system_prompt_file_for_launch
    check("an empty source path launches without the flag",
          for_launch("", workspace / "unused-agent-part.md") == "")

    unreadable_stderr = io.StringIO()
    with contextlib.redirect_stderr(unreadable_stderr):
        chosen = for_launch(str(workspace / "vanished-appended-prompt.md"),
                            workspace / "vanished-agent-part.md")
    check("a source gone by launch time launches without the flag, with one warning line",
          chosen == "" and len(unreadable_stderr.getvalue().splitlines()) == 1
          and unreadable_stderr.getvalue().startswith("handoff-supervisor: "),
          repr((chosen, unreadable_stderr.getvalue())))

    source = workspace / "appended-prompt-unwritable-destination.md"
    source.write_text("notes\n---\nagent\n", encoding="utf-8")
    unwritable_stderr = io.StringIO()
    with contextlib.redirect_stderr(unwritable_stderr):
        chosen = for_launch(str(source), workspace / "no-such-directory" / "agent-part.md")
    check("an agent part that cannot be written sends the whole file, with one warning line",
          chosen == str(source) and len(unwritable_stderr.getvalue().splitlines()) == 1
          and unwritable_stderr.getvalue().startswith("handoff-supervisor: "),
          repr((chosen, unwritable_stderr.getvalue())))

    # Read at every launch: an edit between two launches reaches the second.
    agent_part_path = workspace / "reread-agent-part.md"
    source.write_text("notes\n---\nfirst agent text\n", encoding="utf-8")
    for_launch(str(source), agent_part_path)
    source.write_text("notes\n---\nsecond agent text\n", encoding="utf-8")
    for_launch(str(source), agent_part_path)
    check("the source is re-read at each launch, so an edit reaches the next one",
          agent_part_path.read_text(encoding="utf-8") == "second agent text\n",
          agent_part_path.read_text(encoding="utf-8"))


def run_launched_session_seat_environment_cases(workspace: Path):
    """Every launched session is told the seat's name and directory, and its own
    session id.

    The handoff writer the agent runs names its handoff after the name this
    supervisor watches only if the session carries it: taken from the shell's
    working directory instead, a `cd scripts` or a worktree names the handoff
    after that directory, and nothing polls the file (user-ruled 2026-09-16).
    The agent command here is a real child process that records what its
    environment holds, so what is proven is what a launched session sees.
    The supervisor itself is started with decoy values of all three variables,
    as it would be when run from inside another seat's session, so an
    inherited value cannot pass for a value the supervisor set.

    The session id is what confines the name and directory to this session:
    the writer honours them only where CLAUDE_CODE_SESSION_ID equals it, and a
    child `claude` the session starts inherits all three under its own id
    (PR #414 review, 2026-09-16). So it must be the id launched, the one on
    the command line and in the state file.
    """
    name = "launchenvseat"
    handoff_directory = workspace / name
    handoff_directory.mkdir(parents=True, exist_ok=True)
    seat_directory = workspace / "launchenvseat-directory"
    seat_directory.mkdir(parents=True, exist_ok=True)
    record_path = handoff_directory / "environment.json"
    stub_agent = handoff_directory / "stub-agent"
    stub_agent.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        f"with open({str(record_path)!r}, 'w', encoding='utf-8') as handle:\n"
        "    recorded = {variable: os.environ.get(variable) for variable in (\n"
        "        'NEDSCHORUS_HANDOFF_SUPERVISOR_AGENT_NAME',\n"
        "        'NEDSCHORUS_HANDOFF_SUPERVISOR_WORKING_DIRECTORY',\n"
        "        'NEDSCHORUS_HANDOFF_SUPERVISOR_SESSION_ID')}\n"
        "    recorded['argv'] = sys.argv[1:]\n"
        "    json.dump(recorded, handle)\n",
        encoding="utf-8",
    )
    stub_agent.chmod(0o755)
    environment = dict(os.environ)
    environment["NEDSCHORUS_HANDOFF_SUPERVISOR_AGENT_NAME"] = "decoy-outer-seat"
    environment["NEDSCHORUS_HANDOFF_SUPERVISOR_WORKING_DIRECTORY"] = str(workspace / "decoy-outer-seat")
    environment["NEDSCHORUS_HANDOFF_SUPERVISOR_SESSION_ID"] = "decoy-outer-session"
    subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--agent", name, "--cd", str(seat_directory),
         "--handoff-dir", str(handoff_directory), "--agent-command", str(stub_agent), "--agent-update-timeout-seconds", "0"],
        capture_output=True, text=True, check=False,
        stdin=subprocess.DEVNULL, timeout=60, env=environment,
    )
    recorded = (json.loads(record_path.read_text(encoding="utf-8"))
                if record_path.is_file() else {})
    check("the launched session ran and recorded its environment",
          record_path.is_file(), "the stub agent wrote no record, so no session launched")
    check("the launched session is told the agent name its supervisor watches",
          recorded.get("NEDSCHORUS_HANDOFF_SUPERVISOR_AGENT_NAME") == name, str(recorded))
    # main() resolves --cd, so on macOS a /var tempdir arrives as /private/var.
    check("the launched session is told the directory its supervisor launched it in",
          recorded.get("NEDSCHORUS_HANDOFF_SUPERVISOR_WORKING_DIRECTORY")
          == str(seat_directory.resolve()), str(recorded))
    launched_argv = recorded.get("argv") or []
    launched_session_id = (launched_argv[launched_argv.index("--session-id") + 1]
                           if "--session-id" in launched_argv[:-1] else None)
    state = supervisor.read_supervisor_state(handoff_directory / f"{name}-supervisor-state.json")
    check("the launched session is told the session id it was launched with",
          launched_session_id is not None
          and recorded.get("NEDSCHORUS_HANDOFF_SUPERVISOR_SESSION_ID") == launched_session_id
          and state.get("launched_session_id") == launched_session_id,
          f"{recorded} state session_id={state.get('session_id')}")


with fixture.handoff_supervisor_suite_workspace() as workspace:
    run_adoption_cases(workspace)
    run_appended_system_prompt_cases(workspace)
    run_appended_system_prompt_agent_part_cases(workspace)
    run_launched_session_seat_environment_cases(workspace)
    run_process_identity_cases(workspace)
    run_lock_cases(workspace)

# -- the agent binary is updated immediately before each launch ---------------
# User-ruled 2026-09-22. A handoff restart passed no update moment, so a
# long-lived seat drifted behind the published Claude Code while background
# auto-update stayed off by the 2026-08-22 ruling (R16). update_agent_binary
# carries the whole reasoning; these cases pin its behaviour and its wiring.


def an_agent_recording_its_invocations(directory, body="exit 0"):
    """A stub agent that appends the arguments of every invocation to a file."""
    log = Path(directory) / "invocations"
    path = Path(directory) / "recording-agent"
    path.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$*" >> "' + str(log) + '"\n' + body + "\n",
        encoding="utf-8")
    path.chmod(0o755)
    return path


def invocations_of(directory):
    log = Path(directory) / "invocations"
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


class AnotherUpdateHoldsTheLock:
    """Hold the update lock from this test, as another update would, releasing
    it after release_after_seconds (None: held until the block ends). The
    release marker is written BEFORE the lock is released, so an update that
    ran only after taking the lock always sees it."""

    def __init__(self, lock_path, release_marker, release_after_seconds=None):
        self.lock_path = Path(lock_path)
        self.release_marker = Path(release_marker)
        self.release_after_seconds = release_after_seconds
        self.timer = None

    def release(self):
        self.release_marker.write_text("released", encoding="utf-8")
        fcntl.flock(self.lock_file, fcntl.LOCK_UN)

    def __enter__(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_file = open(self.lock_path, "a")
        fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if self.release_after_seconds is not None:
            self.timer = threading.Timer(self.release_after_seconds, self.release)
            self.timer.start()
        return self

    def __exit__(self, *exception):
        if self.timer is not None:
            self.timer.join()
        self.lock_file.close()


with tempfile.TemporaryDirectory() as update_workspace:
    agent = an_agent_recording_its_invocations(update_workspace)

    supervisor.update_agent_binary(str(agent), 0)
    check("a zero update timeout runs no update at all",
          invocations_of(update_workspace) == [],
          str(invocations_of(update_workspace)))

    supervisor.update_agent_binary(str(agent), 30)
    check("the update invokes the agent command with the update subcommand",
          invocations_of(update_workspace) == ["update"],
          str(invocations_of(update_workspace)))

with tempfile.TemporaryDirectory() as update_workspace:
    # A hung update is killed at the timeout and the launch proceeds. The
    # launchers allow 120s for a real download; 1s here bounds the case. exec,
    # so the kill at the timeout reaches the sleep and nothing outlives the case.
    agent = an_agent_recording_its_invocations(update_workspace, body="exec sleep 30")
    started = time.monotonic()
    captured = io.StringIO()
    with contextlib.redirect_stderr(captured):
        supervisor.update_agent_binary(str(agent), 1)
    elapsed = time.monotonic() - started
    check("a hung update is killed at the timeout rather than blocking the launch",
          elapsed < 15, f"{elapsed:.1f}s")
    check("a killed update says so, because the supervisor is what killed it",
          "was stopped" in captured.getvalue(), captured.getvalue())

with tempfile.TemporaryDirectory() as update_workspace:
    # A non-zero status is deliberately silent: the agent prints its own
    # diagnosis, so a paraphrase here would add nothing and could mislead.
    agent = an_agent_recording_its_invocations(update_workspace, body="exit 3")
    captured = io.StringIO()
    with contextlib.redirect_stderr(captured):
        supervisor.update_agent_binary(str(agent), 30)
    check("a failing update is silent and does not raise",
          captured.getvalue() == "", captured.getvalue())

with tempfile.TemporaryDirectory() as update_workspace:
    # An agent command that cannot be run at all must not stop the seat coming
    # back, which is what catching OSError is for.
    captured = io.StringIO()
    with contextlib.redirect_stderr(captured):
        supervisor.update_agent_binary(
            str(Path(update_workspace) / "no-such-command"), 30)
    check("an agent command that cannot be run is reported, not raised",
          "could not be run" in captured.getvalue(), captured.getvalue())

with tempfile.TemporaryDirectory() as update_workspace:
    # The wiring. launch_agent_session is the ONE site every restart path
    # reaches a session through: the supervisor's relaunch after a handoff,
    # recover-crashed-seats.py, and the login restart, which goes through
    # recovery. An adopted session never passes through here, which is what
    # keeps the update off the adopted path structurally rather than by
    # where the call happens to sit.
    agent = an_agent_recording_its_invocations(update_workspace)
    supervisor.launch_agent_session(
        str(agent), "session-without-update", Path(update_workspace), "prompt",
        update_timeout_seconds=0).wait()
    check("launching with the update switched off invokes no update",
          "update" not in invocations_of(update_workspace),
          str(invocations_of(update_workspace)))

with tempfile.TemporaryDirectory() as update_workspace:
    agent = an_agent_recording_its_invocations(update_workspace)
    supervisor.launch_agent_session(
        str(agent), "session-with-update", Path(update_workspace), "prompt",
        update_timeout_seconds=30).wait()
    check("a launch updates the binary before it starts the session",
          invocations_of(update_workspace)[:1] == ["update"],
          str(invocations_of(update_workspace)))

# -- every update on a machine runs under one lock ------------------------------
# User-approved 2026-09-22 (superwalk item 2). A login restart starts one
# supervisor about 6 s after the last, and each first launch runs `claude
# update`, so two could overlap. scripts/agent-binary-update-under-lock.py
# carries the reasoning; these cases pin the supervisor's side of it.

with tempfile.TemporaryDirectory() as update_workspace:
    release_marker = Path(update_workspace) / "released"
    agent = an_agent_recording_its_invocations(
        update_workspace,
        body=f'if [ -e "{release_marker}" ]; then echo after-release; '
             f'else echo before-release; fi >> "{update_workspace}/order"')
    captured = io.StringIO()
    with AnotherUpdateHoldsTheLock(sandboxed_update_lock_path, release_marker,
                                   release_after_seconds=1.5):
        with contextlib.redirect_stderr(captured):
            supervisor.update_agent_binary(str(agent), 30)
    order_log = Path(update_workspace) / "order"
    order = order_log.read_text(encoding="utf-8").splitlines() if order_log.exists() else []
    check("an update started while another holds the lock waits, then runs",
          invocations_of(update_workspace) == ["update"] and order == ["after-release"],
          str((invocations_of(update_workspace), order)))
    check("an update waiting for the lock says so",
          "handoff-supervisor: waiting for another update on this machine to finish"
          in captured.getvalue(), captured.getvalue())

with tempfile.TemporaryDirectory() as update_workspace:
    agent = an_agent_recording_its_invocations(update_workspace)
    captured = io.StringIO()
    with AnotherUpdateHoldsTheLock(sandboxed_update_lock_path,
                                   Path(update_workspace) / "released"):
        started = time.monotonic()
        with contextlib.redirect_stderr(captured):
            supervisor.update_agent_binary(str(agent), 1)
        elapsed = time.monotonic() - started
    check("a lock held past the limit skips the update rather than blocking the launch",
          invocations_of(update_workspace) == [] and elapsed < 15,
          f"{invocations_of(update_workspace)} after {elapsed:.1f}s")
    check("the skipped update is reported in one line naming the limit",
          "handoff-supervisor: another update on this machine was still running "
          "after 1s; skipping this update and launching on the installed version\n"
          in captured.getvalue(), captured.getvalue())

with tempfile.TemporaryDirectory() as update_workspace:
    # Timeout 0 is --agent-update-timeout-seconds 0, which every supervisor
    # case in the handoff-supervisor suites passes: it must skip the update
    # entirely, lock included. Held lock: returning at once proves it neither
    # waited nor reported. Fresh path: the lock file never even being created
    # proves it was never opened.
    agent = an_agent_recording_its_invocations(update_workspace)
    captured = io.StringIO()
    with AnotherUpdateHoldsTheLock(sandboxed_update_lock_path,
                                   Path(update_workspace) / "released"):
        started = time.monotonic()
        with contextlib.redirect_stderr(captured):
            supervisor.update_agent_binary(str(agent), 0)
        elapsed = time.monotonic() - started
    check("a zero timeout does not wait on a held lock, and says nothing",
          elapsed < 0.5 and captured.getvalue() == ""
          and invocations_of(update_workspace) == [],
          f"{elapsed:.2f}s {captured.getvalue()!r} {invocations_of(update_workspace)}")
    unused_lock_path = Path(update_workspace) / "unused-lock" / "agent-binary-update.lock"
    supervisor.agent_binary_update_under_lock.AGENT_BINARY_UPDATE_LOCK_PATH = str(
        unused_lock_path)
    try:
        supervisor.update_agent_binary(str(agent), 0)
        supervisor.launch_agent_session(
            str(agent), "session-zero-timeout", Path(update_workspace), "prompt",
            update_timeout_seconds=0).wait()
    finally:
        supervisor.agent_binary_update_under_lock.AGENT_BINARY_UPDATE_LOCK_PATH = str(
            sandboxed_update_lock_path)
    check("a zero timeout takes no lock: the lock file is never created",
          not unused_lock_path.exists() and not unused_lock_path.parent.exists(),
          str(unused_lock_path))
    check("a zero timeout runs no update, directly or through a launch",
          "update" not in invocations_of(update_workspace),
          str(invocations_of(update_workspace)))

with tempfile.TemporaryDirectory() as update_workspace:
    # The supervisor's OWN zero-timeout guard, apart from the helper's. The
    # cases above cannot tell the two apart: with the supervisor's guard
    # removed, the helper's guard still skips the update and the lock, so
    # every one of them passes. Standing in for the helper with a recorder
    # takes its guard out of play; the supervisor must then neither reach the
    # helper nor announce an update check it is not making.
    agent = an_agent_recording_its_invocations(update_workspace)
    helper_calls = []
    real_helper = supervisor.agent_binary_update_under_lock.run_agent_binary_update_under_lock
    supervisor.agent_binary_update_under_lock.run_agent_binary_update_under_lock = (
        lambda *arguments, **keywords: helper_calls.append(arguments) or 0)
    captured_output = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured_output), \
                contextlib.redirect_stderr(captured_output):
            supervisor.update_agent_binary(str(agent), 0)
            supervisor.launch_agent_session(
                str(agent), "session-zero-timeout-own-guard", Path(update_workspace),
                "prompt", update_timeout_seconds=0).wait()
    finally:
        supervisor.agent_binary_update_under_lock.run_agent_binary_update_under_lock = (
            real_helper)
    check("a zero timeout stops in the supervisor: the update helper is never called",
          helper_calls == [], str(helper_calls))
    check("a zero timeout prints no update check, directly or through a launch",
          "checking for" not in captured_output.getvalue(),
          captured_output.getvalue())

check("the update timeout defaults to the launchers' own 120 seconds",
      supervisor.AGENT_BINARY_UPDATE_TIMEOUT_SECONDS == 120,
      str(supervisor.AGENT_BINARY_UPDATE_TIMEOUT_SECONDS))

fixture.print_summary_and_exit_nonzero_if_any_case_failed()
