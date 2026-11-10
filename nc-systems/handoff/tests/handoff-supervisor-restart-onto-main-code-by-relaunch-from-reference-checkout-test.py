#!/usr/bin/env python3
"""Tests for handoff-supervisor-restart-onto-main-code-by-relaunch-from-reference-checkout.py.

Run: python3 nc-systems/handoff/tests/handoff-supervisor-restart-onto-main-code-by-relaunch-from-reference-checkout-test.py

No case touches a real agent-seat. HOME is a scratch directory, set before the program is
loaded, so the reference-checkout, the handoff directory, the agents root and the projects root
are all under it. The handoff-supervisor is a fake: a Python program named handoff-supervisor.py,
started under `sh -c` as a launcher starts the real one, which writes its process ID to the lock
file and starts a `claude` child, Python run under the name claude, working in the agent-home. Every
process a case signals is one the case started. The reference-checkout is a git repository with
a bare origin; its scripts/resupervise-seat.py and scripts/recover-crashed-seats.py are fakes
that record their arguments and exit as each case tells them, and the fake recovery writes the
successor's transcript when told to. Notices are captured, never opened.

Prints one line per case and exits non-zero if any case fails.
"""

import atexit
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
import time
from pathlib import Path

# Before anything runs git: a run started with GIT_DIR set, or another variable that redirects
# git, must keep this suite's git out of the repository the variable names.
_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().parents[3] / "scripts"
    / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

SCRATCH_HOME = Path(tempfile.mkdtemp(prefix="handoff-supervisor-restart-test-home-"))
atexit.register(shutil.rmtree, SCRATCH_HOME, True)
os.environ["HOME"] = str(SCRATCH_HOME)
os.environ["NEDSCHORUS_HANDOFF_SUPERVISOR_RESTART_LOG_DIRECTORY"] = str(SCRATCH_HOME / "restart-logs")

SYSTEM_DIRECTORY = Path(__file__).resolve().parent.parent
SCRIPT_PATH = SYSTEM_DIRECTORY / "handoff-supervisor-restart-onto-main-code-by-relaunch-from-reference-checkout.py"
_spec = importlib.util.spec_from_file_location("handoff_supervisor_restart", SCRIPT_PATH)
program = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(program)
# Every case runs as on ned-box, on either machine; the Mac's cases replace this with their own.
program.on_the_mac = lambda: False

SEAT = "restart-test-seat"
AGENT_HOME = program.AGENTS_ROOT / SEAT
PROJECT_DIRECTORY = program.recovery.harness_project_directory(AGENT_HOME, program.PROJECTS_ROOT)
FAKES = SCRATCH_HOME / "fakes"
CONTROL = SCRATCH_HOME / "fake-control"
FAKE_SUPERVISOR = FAKES / "handoff-supervisor.py"
FAKE_SUPERVISOR_TEXT = r'''
import os, subprocess, sys, time
from pathlib import Path
agent = sys.argv[sys.argv.index("--agent") + 1]
lock = Path(os.environ["HOME"]) / ".claude" / "handoffs" / f"{agent}-supervisor.lock"
lock.parent.mkdir(parents=True, exist_ok=True)
lock.write_text(f"{os.getpid()}\n")
# On the Mac, framework Python's bin/python3 is a launcher that runs this interpreter with argv[0]
# replaced by the interpreter's path; on Linux sys.executable is the interpreter itself.
interpreter = Path(sys.prefix, "Resources", "Python.app", "Contents", "MacOS", "Python")
interpreter = str(interpreter) if interpreter.is_file() else sys.executable
for _ in range(int(os.environ["FAKE_SUPERVISOR_CLAUDE_COUNT"])):
    # argv[0] is claude, as ps shows the real one: `claude --session-id ...`.
    subprocess.Popen(["claude", "-c", "import time; time.sleep(600)"], executable=interpreter,
                     cwd=os.environ["FAKE_AGENT_HOME"])
time.sleep(600)
'''
FAKE_RESUPERVISE_TEXT = r'''
import json, os, sys
from pathlib import Path
control = Path(os.environ["HOME"]) / "fake-control"
with (control / "resupervise-calls").open("a") as stream:
    stream.write(json.dumps(sys.argv[1:]) + "\n")
codes = (control / "resupervise-exit-codes").read_text().split()
(control / "resupervise-exit-codes").write_text(" ".join(codes[1:]) or codes[0])
print("fake resupervise-seat ran")
sys.exit(int(codes[0]))
'''
FAKE_RECOVER_TEXT = r'''
import json, os, sys
from pathlib import Path
control = Path(os.environ["HOME"]) / "fake-control"
with (control / "recover-calls").open("a") as stream:
    stream.write(json.dumps(sys.argv[1:]) + "\n")
codes = (control / "recover-exit-codes").read_text().split()
(control / "recover-exit-codes").write_text(" ".join(codes[1:]) or codes[0])
reply = (control / "successor-reply").read_text().strip() if (control / "successor-reply").is_file() else ""
if reply:
    project = Path(os.environ["FAKE_PROJECT_DIRECTORY"])
    project.mkdir(parents=True, exist_ok=True)
    records = [{"type": "user", "message": {"content": "start"}}]
    if reply == "replied":
        records.append({"type": "assistant", "message": {"model": "claude-opus-5-5",
                        "content": [{"type": "text", "text": "Reading the session-handoff."}]}})
    (project / "successor.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
print("fake recover-crashed-seats ran")
sys.exit(int(codes[0]))
'''

failures = []
started_process_ids = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def end_started_processes():
    for process_id in started_process_ids:
        with contextlib.suppress(OSError):
            os.kill(process_id, signal.SIGCONT)
            os.kill(process_id, signal.SIGKILL)


atexit.register(end_started_processes)


def git(*arguments, cwd):
    return subprocess.run(["git", *arguments], cwd=str(cwd), capture_output=True, text=True,
                          check=True).stdout.strip()


def build_fixture():
    FAKES.mkdir(parents=True, exist_ok=True)
    CONTROL.mkdir(parents=True, exist_ok=True)
    AGENT_HOME.mkdir(parents=True, exist_ok=True)
    program.HANDOFF_DIRECTORY.mkdir(parents=True, exist_ok=True)
    FAKE_SUPERVISOR.write_text(FAKE_SUPERVISOR_TEXT)
    os.environ["FAKE_AGENT_HOME"] = str(AGENT_HOME)
    os.environ["FAKE_PROJECT_DIRECTORY"] = str(PROJECT_DIRECTORY)
    origin = SCRATCH_HOME / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    checkout = program.REFERENCE_CHECKOUT
    subprocess.run(["git", "clone", "-q", str(origin), str(checkout)], check=True,
                   capture_output=True)
    for setting in (("user.name", "test"), ("user.email", "test@example.invalid")):
        git("config", *setting, cwd=checkout)
    (checkout / "tracked.txt").write_text("one\n")
    git("add", "tracked.txt", cwd=checkout)
    git("commit", "-q", "-m", "one", cwd=checkout)
    git("push", "-q", "origin", "HEAD:main", cwd=checkout)
    (checkout / "scripts").mkdir()
    (checkout / "scripts" / "resupervise-seat.py").write_text(FAKE_RESUPERVISE_TEXT)
    (checkout / "scripts" / "recover-crashed-seats.py").write_text(FAKE_RECOVER_TEXT)


def advance_origin():
    """Push a commit to origin from a second clone, so the reference-checkout is behind."""
    other = SCRATCH_HOME / "other-clone"
    if not other.is_dir():
        subprocess.run(["git", "clone", "-q", str(SCRATCH_HOME / "origin.git"), str(other)],
                       check=True, capture_output=True)
        for setting in (("user.name", "test"), ("user.email", "test@example.invalid")):
            git("config", *setting, cwd=other)
    git("pull", "-q", "--ff-only", cwd=other)
    (other / "tracked.txt").write_text((other / "tracked.txt").read_text() + "more\n")
    git("commit", "-q", "-am", "more", cwd=other)
    git("push", "-q", "origin", "HEAD:main", cwd=other)


def start_fake_supervisor(under_shell=True, starts_claude=True, agent=SEAT, claude_count=1):
    """Start the fake handoff-supervisor; return (its process ID, the claude's process ID or None)."""
    lock = program.supervisor.supervisor_lock_path(program.HANDOFF_DIRECTORY, agent)
    lock.unlink(missing_ok=True)
    environment = {**os.environ, "FAKE_SUPERVISOR_CLAUDE_COUNT": str(claude_count if starts_claude else 0)}
    command = [sys.executable, str(FAKE_SUPERVISOR), "--agent", agent, "--cd", str(AGENT_HOME)]
    if under_shell:
        quoted = " ".join(f"'{word}'" for word in command)
        # The shell's "Killed" report, when a case ends the fake, is noise in the suite's output.
        launched = subprocess.Popen(["sh", "-c", f"{quoted}; exit $?"], env=environment,
                                    cwd=str(AGENT_HOME), stderr=subprocess.DEVNULL)
    else:
        launched = subprocess.Popen(command, env=environment, cwd=str(AGENT_HOME))
    started_process_ids.append(launched.pid)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if lock.is_file() and lock.read_text().strip():
            break
        time.sleep(0.05)
    supervisor_id = int(lock.read_text())
    started_process_ids.append(supervisor_id)
    claude_id = None
    while starts_claude and time.monotonic() < deadline:
        table = program.process_table()
        # Between fork and exec a child still shows the fake handoff-supervisor's command line;
        # recorded then, step 4 takes the claude, once it has exec'd, for a reused process ID.
        children = [process_id for process_id, (parent, command) in table.items()
                    if parent == supervisor_id and command.split()
                    and Path(command.split()[0]).name == "claude"]
        if len(children) == claude_count:
            claude_id = children[0]
            started_process_ids.append(claude_id)
            break
        time.sleep(0.05)
    return supervisor_id, claude_id


def running(process_id):
    # A fake ended while its parent lives stays a zombie, which ps still lists by its command line.
    state = subprocess.run(["ps", "-o", "stat=", "-p", str(process_id)], capture_output=True,
                           text=True).stdout.strip()
    return bool(state) and not state.startswith("Z")


def stop_fake(process_id):
    with contextlib.suppress(OSError):
        os.kill(process_id, signal.SIGCONT)
        os.kill(process_id, signal.SIGKILL)


def quick_sleep(seconds):
    time.sleep(min(seconds, 0.2))


@contextlib.contextmanager
def replaced(owner, name, value):
    saved = getattr(owner, name)
    setattr(owner, name, value)
    try:
        yield
    finally:
        setattr(owner, name, saved)


def run_foreground(**keywords):
    output, errors = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
        status = program.foreground(SEAT, **keywords)
    return status, output.getvalue(), errors.getvalue()


# ---------------------------------------------------------------- step 0


def step_0_cases():
    checkout = program.REFERENCE_CHECKOUT
    advance_origin()
    report = program.step_0_fast_forward_reference_checkout(checkout)
    check("step 0: a reference-checkout behind origin/main is fast-forwarded to it",
          git("rev-parse", "HEAD", cwd=checkout) == git("rev-parse", "origin/main", cwd=checkout)
          and "is at origin/main" in report, report)

    (checkout / "tracked.txt").write_text("changed by hand\n")
    try:
        program.step_0_fast_forward_reference_checkout(checkout)
        check("step 0: a changed tracked file fails", False, "no failure")
    except program.RestartFailure as error:
        check("step 0: a changed tracked file fails", "changed tracked files" in str(error)
              and "tracked.txt" in str(error), str(error))
    git("checkout", "--", "tracked.txt", cwd=checkout)

    git("commit", "-q", "--allow-empty", "-m", "local only", cwd=checkout)
    advance_origin()
    try:
        program.step_0_fast_forward_reference_checkout(checkout)
        check("step 0: a reference-checkout that cannot fast-forward fails, quoting git", False,
              "no failure")
    except program.RestartFailure as error:
        check("step 0: a reference-checkout that cannot fast-forward fails, quoting git",
              "git merge --ff-only --no-overwrite-ignore origin/main in" in str(error)
              and "failed (exit" in str(error),
              str(error))
    git("reset", "-q", "--hard", "origin/main", cwd=checkout)

    git("remote", "set-url", "origin", str(SCRATCH_HOME / "no-such-origin.git"), cwd=checkout)
    try:
        program.step_0_fast_forward_reference_checkout(checkout)
        check("step 0: a failed fetch fails, quoting git", False, "no failure")
    except program.RestartFailure as error:
        check("step 0: a failed fetch fails, quoting git",
              "git fetch origin in" in str(error) and "no-such-origin" in str(error), str(error))
    git("remote", "set-url", "origin", str(SCRATCH_HOME / "origin.git"), cwd=checkout)

    steps = program.reference_checkout_steps
    real_git = steps.reference_checkout_git_output_or_raise

    def git_with_head_elsewhere(checkout, arguments, **options):
        if list(arguments) == ["rev-parse", "HEAD"]:
            return "0" * 40
        return real_git(checkout, arguments, **options)

    with replaced(steps, "reference_checkout_git_output_or_raise", git_with_head_elsewhere):
        try:
            program.step_0_fast_forward_reference_checkout(checkout)
            check("step 0: a HEAD other than origin/main fails", False, "no failure")
        except program.RestartFailure as error:
            check("step 0: a HEAD other than origin/main fails", "not at origin/main" in str(error),
                  str(error))


# ---------------------------------------------------------------- step 2 and the foreground


def step_2_cases():
    lock = program.supervisor.supervisor_lock_path(program.HANDOFF_DIRECTORY, SEAT)
    lock.write_text("not a number\n")
    try:
        program.step_2_identify_supervisor(SEAT, program.HANDOFF_DIRECTORY)
        check("step 2: an unreadable lock file fails", False, "no failure")
    except program.RestartFailure as error:
        check("step 2: an unreadable lock file fails", "could not be read from" in str(error), str(error))

    lock.write_text(f"{os.getpid()}\n")
    try:
        program.step_2_identify_supervisor(SEAT, program.HANDOFF_DIRECTORY)
        check("step 2: a lock naming a process that is not the handoff-supervisor fails", False, "")
    except program.RestartFailure as error:
        check("step 2: a lock naming a process that is not the handoff-supervisor fails",
              "is not the handoff-supervisor of" in str(error), str(error))

    helper_id, helper_claude = start_fake_supervisor(agent=f"{SEAT}-restart-helper")
    lock.write_text(f"{helper_id}\n")
    try:
        program.step_2_identify_supervisor(SEAT, program.HANDOFF_DIRECTORY)
        check("step 2: the handoff-supervisor of a longer agent-seat name does not pass", False, "")
    except program.RestartFailure as error:
        check("step 2: the handoff-supervisor of a longer agent-seat name does not pass",
              "is not the handoff-supervisor of" in str(error), str(error))
    stop_fake(helper_claude)
    stop_fake(helper_id)

    lonely_id, _ = start_fake_supervisor(starts_claude=False)
    try:
        program.step_2_identify_supervisor(SEAT, program.HANDOFF_DIRECTORY)
        check("step 2: a handoff-supervisor with no claude child fails", False, "")
    except program.RestartFailure as error:
        check("step 2: a handoff-supervisor with no claude child fails",
              "0 claude child processes" in str(error), str(error))
    stop_fake(lonely_id)

    crowded_id, _ = start_fake_supervisor(claude_count=2)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        crowded_children = [process_id for process_id, (parent, _) in program.process_table().items()
                            if parent == crowded_id]
        if len(crowded_children) == 2:
            break
        time.sleep(0.05)
    try:
        program.step_2_identify_supervisor(SEAT, program.HANDOFF_DIRECTORY)
        check("step 2: a handoff-supervisor with two claude children fails", False, "")
    except program.RestartFailure as error:
        check("step 2: a handoff-supervisor with two claude children fails",
              "2 claude child processes" in str(error), str(error))
    for process_id in crowded_children:
        stop_fake(process_id)
    stop_fake(crowded_id)

    supervisor_id, claude_id = start_fake_supervisor()
    found = program.step_2_identify_supervisor(SEAT, program.HANDOFF_DIRECTORY)
    check("step 2: the handoff-supervisor and its claude are found",
          found[0] == supervisor_id and found[2] == claude_id
          and Path(found[3].split()[0]).name == "claude", found[:4])
    check("step 2: a handoff-supervisor under sh is under a shell",
          program.parent_kind(supervisor_id, found[4]) == "shell")
    real_run = program.run
    for answer, expected in (("tmux: server", "tmux"), ("-zsh", "shell"), ("/bin/bash", "shell"),
                             ("launchd", "launchd")):
        def run_naming_the_parent(arguments, timeout=120, answer=answer):
            if arguments[:3] == ["ps", "-o", "comm="]:
                return 0, answer
            return real_run(arguments, timeout)
        with replaced(program, "run", run_naming_the_parent):
            kind = program.parent_kind(supervisor_id, found[4])
        check(f"step 2: a parent ps names {answer!r} is {expected!r}", kind == expected, kind)

    def run_failing_ps(arguments, timeout=120):
        return 1, ""
    with replaced(program, "run", run_failing_ps):
        kind = program.parent_kind(supervisor_id, found[4])
    check("step 2: a parent ps cannot name is reported by its process ID",
          "which ps could not name" in kind, kind)
    stop_fake(claude_id)
    stop_fake(supervisor_id)

    bare_id, bare_claude = start_fake_supervisor(under_shell=False)
    status, _, errors = run_foreground(start_second_half=lambda path: 0, sleep=quick_sleep)
    check("foreground: a handoff-supervisor under neither a shell nor tmux is left running",
          status == 1 and "not a shell, so it was not frozen" in errors
          and not program.process_is_stopped(bare_id), errors)
    stop_fake(bare_claude)
    stop_fake(bare_id)


def foreground_cases():
    supervisor_id, claude_id = start_fake_supervisor()
    real_run = program.run

    def run_with_tmux_parent(arguments, timeout=120):
        if arguments[:3] == ["ps", "-o", "comm="]:
            return 0, "tmux: server"
        return real_run(arguments, timeout)
    with replaced(program, "run", run_with_tmux_parent):
        status, _, errors = run_foreground(start_second_half=lambda path: 0, sleep=quick_sleep)
    check("foreground: a handoff-supervisor under its tmux server is not frozen and the user is told",
          status == 1 and "cannot be frozen" in errors and "Tell the user" in errors
          and not program.process_is_stopped(supervisor_id), errors)

    with replaced(program, "process_is_stopped", lambda process_id: False):
        status, _, errors = run_foreground(start_second_half=lambda path: 0, sleep=quick_sleep)
    time.sleep(0.2)
    check("foreground: a freeze that does not hold is undone with SIGCONT",
          status == 1 and "did not stay stopped" in errors and "unfrozen with SIGCONT" in errors
          and not program.process_is_stopped(supervisor_id), errors)

    def failing_start(path):
        raise OSError("no room to start")
    status, _, errors = run_foreground(start_second_half=failing_start, sleep=quick_sleep)
    time.sleep(0.2)
    check("foreground: a second half that cannot start leaves the handoff-supervisor unfrozen",
          status == 1 and "no room to start" in errors and "unfrozen with SIGCONT" in errors
          and not program.process_is_stopped(supervisor_id), errors)

    with replaced(program.recovery, "processes_rooted_in_seat_directory",
                  lambda directory, require_a_complete_listing=False: (None, "lsof broke")):
        status, _, errors = run_foreground(start_second_half=lambda path: 0, sleep=quick_sleep)
    check("foreground: agent-home processes that cannot be listed stop it before the freeze",
          status == 1 and "lsof broke" in errors and "Nothing of the agent-seat was changed" in errors
          and not program.process_is_stopped(supervisor_id), errors)

    started = []
    status, output, errors = run_foreground(start_second_half=lambda path: started.append(path) or 4242,
                                            sleep=quick_sleep)
    state = json.loads(started[0].read_text()) if started else {}
    check("foreground: the handoff-supervisor is frozen and the agent-seat told to write its session-handoff",
          status == 0 and program.process_is_stopped(supervisor_id)
          and "write your session-handoff now" in output and "result.txt" in output, output + errors)
    check("foreground: the state for the second half names both processes and the agent-home's processes",
          state.get("supervisor_id") == supervisor_id and state.get("claude_id") == claude_id
          and str(claude_id) in state.get("agent_home_processes", {}), state)
    return supervisor_id, claude_id, started[0] if started else None


# ---------------------------------------------------------------- second half


def control(name, text):
    (CONTROL / name).write_text(text)


def calls(name):
    path = CONTROL / name
    return [json.loads(line) for line in path.read_text().splitlines()] if path.is_file() else []


def reset_control():
    for path in CONTROL.iterdir():
        path.unlink()
    shutil.rmtree(PROJECT_DIRECTORY, ignore_errors=True)


def second_half(state_path, opened=None, now=time.time):
    opened = [] if opened is None else opened
    half = program.SecondHalf(state_path, sleep=quick_sleep, now=now,
                              open_notice_page=lambda page: opened.append(page) or (0, ""))
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        status = half.run_steps_and_report_any_unexpected_error()
    return status, half, output.getvalue()


def fresh_state(**changes):
    """Freeze a new fake handoff-supervisor and write a state file for it, as the foreground does."""
    supervisor_id, claude_id = start_fake_supervisor()
    os.kill(supervisor_id, signal.SIGSTOP)
    directory = program.restart_log_directory(SEAT, Path(os.environ[
        "NEDSCHORUS_HANDOFF_SUPERVISOR_RESTART_LOG_DIRECTORY"]))
    directory = Path(tempfile.mkdtemp(dir=directory))
    table = program.process_table()
    state = {"seat": SEAT, "supervisor_id": supervisor_id,
             "supervisor_command": table[supervisor_id][1], "claude_id": claude_id,
             "claude_command": table[claude_id][1], "frozen_at": time.time() - 1,
             "agent_home_processes": {str(claude_id): table[claude_id][1],
                                      str(supervisor_id): table[supervisor_id][1]}}
    state.update(changes)
    state_path = directory / "state.json"
    state_path.write_text(json.dumps(state))
    return supervisor_id, claude_id, state_path


def write_session_handoff(extra=""):
    handoff = program.supervisor.handoff_file_path(program.HANDOFF_DIRECTORY, SEAT)
    handoff.write_text("restart-counter: 5\nnext-step: carry on\n" + extra)


def second_half_cases():
    reset_control()
    supervisor_id, claude_id, state_path = fresh_state(frozen_at=time.time() + 3600)
    clock = iter(range(0, 10**9, 600))
    opened = []
    status, half, output = second_half(state_path, opened, now=lambda: next(clock))
    time.sleep(0.2)
    check("second half: no session-handoff within the limit unfreezes the old handoff-supervisor",
          status == 1 and not program.process_is_stopped(supervisor_id) and running(supervisor_id)
          and "unfrozen with SIGCONT" in output
          and "step 4" not in (state_path.parent / "result.txt").read_text(), output)
    check("second half: that failure is a notice for the user and a line in the result file",
          opened and (state_path.parent / "notice.txt").is_file()
          and "FAILED" in (state_path.parent / "result.txt").read_text(), opened)
    stop_fake(claude_id)
    stop_fake(supervisor_id)

    reset_control()
    control("resupervise-exit-codes", "0")
    control("recover-exit-codes", "0")
    control("successor-reply", "replied")
    supervisor_id, claude_id, state_path = fresh_state()
    write_session_handoff()
    opened = []
    status, half, output = second_half(state_path, opened)
    time.sleep(0.3)
    result = (state_path.parent / "result.txt").read_text()
    check("second half: the old handoff-supervisor and its claude are ended",
          not running(supervisor_id) and not running(claude_id), output)
    check("second half: resupervise-seat.py --prepare-only and recover-crashed-seats.py run from the reference-checkout",
          calls("resupervise-calls") == [[SEAT, "--prepare-only"]]
          and calls("recover-calls") == [[SEAT]], (calls("resupervise-calls"), calls("recover-calls")))
    check("second half: a successor's reply in a new transcript is a restart, with no notice",
          status == 0 and "RESTARTED" in result and not opened, result)
    check("second half: the RESTARTED line is written before step 7, which the successor's reading of it answers",
          "RESTARTED" in result and "step 7: the successor replied" in result
          and result.index("RESTARTED") < result.index("step 7: the successor replied"), result)

    reset_control()
    control("resupervise-exit-codes", "0")
    control("recover-exit-codes", "0")
    supervisor_id, claude_id, state_path = fresh_state()
    write_session_handoff("ask-user-before-restart: the user asked to be consulted before a relaunch\n")
    opened = []
    status, half, output = second_half(state_path, opened)
    time.sleep(0.2)
    check("second half: a session-handoff written with --ask-user-before-restart unfreezes the old handoff-supervisor and ends nothing",
          status == 1 and opened and "--ask-user-before-restart" in output and running(supervisor_id)
          and not program.process_is_stopped(supervisor_id) and running(claude_id)
          and not calls("resupervise-calls"), output)
    stop_fake(claude_id)
    stop_fake(supervisor_id)
    check("second half: on ned-box the result says a failed-restart-notice was expected",
          "failed-restart-notice" in result, result)

    reset_control()
    control("resupervise-exit-codes", "0")
    control("recover-exit-codes", "3")
    control("successor-reply", "replied")
    supervisor_id, claude_id, state_path = fresh_state()
    write_session_handoff()
    status, half, output = second_half(state_path)
    check("second half: recovery's exit 3, no window on the Mac, is no failure",
          status == 0 and "no window opened on the Mac" in output, output)

    reset_control()
    control("resupervise-exit-codes", "0")
    control("recover-exit-codes", "1 0")
    control("successor-reply", "replied")
    supervisor_id, claude_id, state_path = fresh_state()
    write_session_handoff()
    status, half, output = second_half(state_path)
    check("second half: a failed recovery is run once more",
          status == 0 and len(calls("recover-calls")) == 2 and "run once more: exited 0" in output,
          output)

    reset_control()
    control("resupervise-exit-codes", "0")
    control("recover-exit-codes", "1 1")
    supervisor_id, claude_id, state_path = fresh_state()
    write_session_handoff()
    opened = []
    status, half, output = second_half(state_path, opened)
    check("second half: a recovery that fails twice, with no handoff-supervisor running, says the session-handoff waits",
          status == 1 and opened and len(calls("recover-calls")) == 2
          and "session-handoff still waits on disk" in output, output)

    reset_control()
    control("resupervise-exit-codes", "0")
    control("recover-exit-codes", "1 1")
    supervisor_id, claude_id, state_path = fresh_state()
    write_session_handoff()
    with replaced(program.supervisor, "supervisor_liveness", lambda path: (True, "fake liveness")):
        status, half, output = second_half(state_path)
    check("second half: a recovery that fails twice while a new handoff-supervisor runs changes nothing more",
          status == 1 and "A new handoff-supervisor runs (fake liveness)" in output, output)

    reset_control()
    control("resupervise-exit-codes", "1 1")
    control("recover-exit-codes", "0")
    supervisor_id, claude_id, state_path = fresh_state()
    write_session_handoff()
    status, half, output = second_half(state_path)
    check("second half: resupervise-seat.py --prepare-only failing twice stops before recovery",
          status == 1 and len(calls("resupervise-calls")) == 2 and not calls("recover-calls")
          and "step 5 failed twice" in output, output)

    reset_control()
    control("resupervise-exit-codes", "0")
    control("recover-exit-codes", "0")
    control("successor-reply", "silent")
    supervisor_id, claude_id, state_path = fresh_state()
    write_session_handoff()
    clock = iter(range(0, 10**9, 120))
    opened = []
    status, half, output = second_half(state_path, opened, now=lambda: next(clock))
    check("second half: no reply from the successor within 5 minutes is a notice with what ps shows",
          status == 1 and opened and "no new transcript" in output and "as ps lists them" in output
          and "tmux -L restart-test-seat attach" in (state_path.parent / "notice.txt").read_text(),
          output)
    notice_text = (state_path.parent / "notice.txt").read_text()
    check("second half: off the Mac, the notice's attach command is wrapped in ssh to ned-box, "
          "and it names the result file for an agent-seat to read",
          "`ssh -t nedlern@ned-box 'tmux -L restart-test-seat attach -t restart-test-seat'`" in notice_text
          and f"to read {state_path.parent / 'result.txt'}" in notice_text, notice_text)

    reset_control()
    control("resupervise-exit-codes", "0")
    control("recover-exit-codes", "0")
    PROJECT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    (PROJECT_DIRECTORY / "old.jsonl").write_text(json.dumps(
        {"type": "assistant", "message": {"model": "claude-opus-5-5",
                                          "content": [{"type": "text", "text": "old work"}]}}) + "\n")
    supervisor_id, claude_id, state_path = fresh_state()
    write_session_handoff()
    clock = iter(range(0, 10**9, 120))
    status, half, output = second_half(state_path, now=lambda: next(clock))
    check("second half: a reply in a transcript that existed before step 6 is not the successor's",
          status == 1 and "no new transcript" in output, output)

    reset_control()
    supervisor_id, claude_id, state_path = fresh_state()
    state_path.write_text(state_path.read_text())
    write_session_handoff()
    with replaced(program, "end_process", lambda *arguments, **keywords: 1 / 0):
        opened = []
        status, half, output = second_half(state_path, opened)
    check("second half: an unexpected error after step 4 began is a notice, and nothing is unfrozen",
          status == 1 and opened and "ZeroDivisionError" in output and "unfrozen" not in output, output)
    stop_fake(claude_id)

    reset_control()
    supervisor_id, claude_id, state_path = fresh_state()
    with replaced(program.SecondHalf, "wait_for_session_handoff", lambda self: 1 / 0):
        status, half, output = second_half(state_path)
    time.sleep(0.2)
    check("second half: an unexpected error before step 4 unfreezes the old handoff-supervisor",
          status == 1 and "ZeroDivisionError" in output and "unfrozen with SIGCONT" in output
          and not program.process_is_stopped(supervisor_id), output)
    stop_fake(claude_id)
    stop_fake(supervisor_id)


def start_leftover_in_agent_home():
    """Start a process working in the agent-home that step 4 does not end; return (its ID, its command)."""
    leftover = subprocess.Popen(["sleep", "600"], cwd=str(AGENT_HOME))
    started_process_ids.append(leftover.pid)
    return leftover.pid, program.process_command_line(leftover.pid)


def state_with_leftover():
    """A frozen fake handoff-supervisor whose step-2 list also holds a leftover that outlives step 4."""
    leftover_id, leftover_command = start_leftover_in_agent_home()
    supervisor_id, claude_id, state_path = fresh_state()
    state = json.loads(state_path.read_text())
    state["agent_home_processes"][str(leftover_id)] = leftover_command
    state_path.write_text(json.dumps(state))
    return supervisor_id, claude_id, leftover_id, state_path


def step_4_and_leftover_cases():
    reset_control()
    control("resupervise-exit-codes", "0")
    control("recover-exit-codes", "0")
    supervisor_id, claude_id, state_path = fresh_state(supervisor_command="python3 a command no process runs")
    write_session_handoff()
    status, half, output = second_half(state_path)
    result = (state_path.parent / "result.txt").read_text()
    check("step 4: an old handoff-supervisor whose process ID now names another command gets no SIGKILL",
          f"the old handoff-supervisor {supervisor_id} had already ended" in result
          and "was ended with SIGKILL" not in result, result)
    stop_fake(claude_id)
    stop_fake(supervisor_id)

    for case, failing in (("step 4's ps check that cannot answer", "ps"),
                          ("step 4's SIGKILL that the system refuses", "kill")):
        reset_control()
        supervisor_id, claude_id, state_path = fresh_state()
        write_session_handoff()
        real_command_line, real_send_signal = program.process_command_line, program.send_signal
        asked = []

        def command_line_failing_once(process_id):
            if failing == "ps" and process_id == supervisor_id and not asked:
                asked.append(process_id)
                raise program.RestartFailure(f"ps could not tell whether process {process_id} is running")
            return real_command_line(process_id)

        def signal_refusing_kill(process_id, number):
            if failing == "kill" and number == signal.SIGKILL:
                raise program.RestartFailure(f"sending SIGKILL to process {process_id} failed: not permitted")
            return real_send_signal(process_id, number)

        with replaced(program, "process_command_line", command_line_failing_once), \
                replaced(program, "send_signal", signal_refusing_kill):
            opened = []
            status, half, output = second_half(state_path, opened)
        time.sleep(0.2)
        check(f"step 4: {case} unfreezes the old handoff-supervisor and says so",
              status == 1 and opened and "unfrozen with SIGCONT" in output and not half.step_4_started
              and running(supervisor_id) and not program.process_is_stopped(supervisor_id)
              and running(claude_id) and not calls("resupervise-calls"), output)
        stop_fake(claude_id)
        stop_fake(supervisor_id)

    reset_control()
    control("resupervise-exit-codes", "1 0")
    control("recover-exit-codes", "0")
    control("successor-reply", "replied")
    supervisor_id, claude_id, leftover_id, state_path = state_with_leftover()
    write_session_handoff()
    status, half, output = second_half(state_path)
    time.sleep(0.2)
    result = (state_path.parent / "result.txt").read_text()
    ended_line = f"step 5: process {leftover_id} (sleep 600) ended"
    check("step 5: a failed resupervise-seat.py ends step 2's leftovers before it is run once more",
          status == 0 and not running(leftover_id) and ended_line in result
          and result.index(ended_line) < result.index("step 5, run once more"), result)

    reset_control()
    control("resupervise-exit-codes", "0")
    control("recover-exit-codes", "0")
    control("successor-reply", "replied")
    supervisor_id, claude_id, leftover_id, state_path = state_with_leftover()
    write_session_handoff()
    status, half, output = second_half(state_path)
    time.sleep(0.2)
    result = (state_path.parent / "result.txt").read_text()
    ended_line = f"step 5: process {leftover_id} (sleep 600) ended"
    check("step 5: a leftover of step 2 that outlives step 4 is ended before recover-crashed-seats.py runs",
          status == 0 and not running(leftover_id) and ended_line in result
          and result.index(ended_line) < result.index("step 6:"), result)


def step_5_cases():
    supervisor_id, claude_id, state_path = fresh_state()
    half = program.SecondHalf(state_path, sleep=quick_sleep, open_notice_page=lambda page: (0, ""))
    claude_command = half.state["claude_command"]
    with contextlib.redirect_stdout(io.StringIO()):
        half.end_leftovers_from_step_2({claude_id: claude_command})
    time.sleep(0.2)
    check("step 5: a process left from step 2's list is ended", not running(claude_id))

    for listed_now, case in (({os.getpid(): "python3 a process step 2 did not list"},
                              "a process step 2 did not list"),
                             ({supervisor_id: "tmux new-session -s other"},
                              "a tmux server, even at a listed process ID"),
                             ({supervisor_id: "sleep 1 a different command"},
                              "a listed process ID now running another command")):
        try:
            half.end_leftovers_from_step_2(listed_now)
            check(f"step 5: {case} stops the program", False, "no failure")
        except program.RestartFailure as error:
            check(f"step 5: {case} stops the program",
                  "processes other than those left from the old agent-session" in str(error), str(error))

    tmux_command = "tmux new-session -d -s restart-test-seat"
    half.state["agent_home_processes"][str(os.getpid())] = tmux_command
    try:
        half.end_leftovers_from_step_2({os.getpid(): tmux_command})
        check("step 5: a tmux server listed with the same command in step 2 stops the program", False,
              "no failure")
    except program.RestartFailure as error:
        check("step 5: a tmux server listed with the same command in step 2 stops the program",
              "processes other than those left from the old agent-session" in str(error), str(error))
    stop_fake(supervisor_id)


def process_cases():
    stubborn = subprocess.Popen([sys.executable, "-c",
                                 "import signal, time\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                                 "print('ready', flush=True)\ntime.sleep(600)"],
                                stdout=subprocess.PIPE, text=True)
    started_process_ids.append(stubborn.pid)
    stubborn.stdout.readline()
    command = program.process_command_line(stubborn.pid)
    with replaced(program, "PROCESS_END_GRACE_SECONDS", 1):
        done = program.end_process(stubborn.pid, command, sleep=lambda s: (stubborn.poll(), time.sleep(s)))
    check("a process that ignores SIGTERM is ended with SIGKILL", "ended on SIGKILL" in done, done)

    polite = subprocess.Popen(["sleep", "600"])
    started_process_ids.append(polite.pid)
    command = program.process_command_line(polite.pid)
    done = program.end_process(polite.pid, command, sleep=lambda s: (polite.poll(), time.sleep(0.05)))
    check("a process that takes SIGTERM is ended with it", "ended on SIGTERM" in done, done)
    done = program.end_process(polite.pid, command)
    check("a process already gone is not signalled", "had already ended" in done, done)

    with replaced(program, "process_command_line", lambda process_id: "unkillable"), \
            replaced(program, "send_signal", lambda process_id, number: None), \
            replaced(program, "PROCESS_END_GRACE_SECONDS", 1):
        try:
            program.end_process(12345, "unkillable", sleep=lambda s: None)
            check("a process that outlives SIGKILL fails", False, "no failure")
        except program.RestartFailure as error:
            check("a process that outlives SIGKILL fails", "still runs after SIGKILL" in str(error),
                  str(error))

    with replaced(program.os, "kill", lambda process_id, number: (_ for _ in ()).throw(
            PermissionError("not permitted"))):
        try:
            program.send_signal(12345, signal.SIGSTOP)
            check("a signal the system refuses fails", False, "no failure")
        except program.RestartFailure as error:
            check("a signal the system refuses fails", "SIGSTOP to process 12345 failed" in str(error),
                  str(error))
    with replaced(program.os, "kill", lambda process_id, number: (_ for _ in ()).throw(
            ProcessLookupError())):
        program.send_signal(12345, signal.SIGKILL)
        check("a signal to a process already gone is no failure", True)

    with replaced(program.supervisor, "read_process_command_line", lambda process_id: (None, False)):
        try:
            program.process_command_line(1)
            check("ps that cannot answer fails", False, "no failure")
        except program.RestartFailure as error:
            check("ps that cannot answer fails", "ps could not tell" in str(error), str(error))

    def ps_cannot_answer(process_id):
        raise program.RestartFailure("ps could not tell")
    with replaced(program, "process_command_line", ps_cannot_answer):
        said = program.unfreeze(12345, "python3 handoff-supervisor.py --agent x")
    check("an unfreeze that fails says the process stays frozen and how to unfreeze it",
          "stays frozen" in said and "kill -CONT 12345" in said, said)
    said = program.unfreeze(12345, "a command no process runs")
    check("an old handoff-supervisor already gone is not unfrozen", "not unfrozen" in said, said)

    with replaced(program, "run", lambda arguments, timeout=120: (1, "ps broke")):
        try:
            program.process_table()
            check("a process table ps cannot give fails", False, "no failure")
        except program.RestartFailure as error:
            check("a process table ps cannot give fails", "ps broke" in str(error), str(error))
    check("is_tmux_server: a tmux command is a tmux server, a claude is not",
          program.is_tmux_server("tmux -L seat new-session") and program.is_tmux_server("/usr/bin/tmux")
          and not program.is_tmux_server("claude --resume x") and not program.is_tmux_server(""))
    check("run: a command that cannot be started is exit 127",
          program.run([str(SCRATCH_HOME / "no-such-program")])[0] == 127)
    check("run: a command that runs too long is exit 124",
          program.run(["sleep", "5"], timeout=0.2)[0] == 124)

    stoppable = subprocess.Popen(["sleep", "600"])
    started_process_ids.append(stoppable.pid)
    os.kill(stoppable.pid, signal.SIGSTOP)
    time.sleep(0.2)
    stopped = program.process_is_stopped(stoppable.pid)
    os.kill(stoppable.pid, signal.SIGCONT)
    time.sleep(0.2)
    check("process_is_stopped: true for a stopped process, false for a running one",
          stopped and not program.process_is_stopped(stoppable.pid))
    stoppable.kill()


def notice_cases():
    supervisor_id, claude_id, state_path = fresh_state()
    half = program.SecondHalf(state_path, open_notice_page=lambda page: (1, "the Mac is asleep"))
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        half.notice("something failed <badly>")
    page = (state_path.parent / "notice.html").read_text()
    check("a notice page that does not open is reported, and the notice stays on disk",
          "was not opened on the Mac (exit 1): the Mac is asleep" in output.getvalue()
          and (state_path.parent / "notice.txt").read_text().startswith("something failed")
          and "&lt;badly&gt;" in page, output.getvalue())
    stop_fake(claude_id)
    stop_fake(supervisor_id)


def mac_cases():
    reset_control()
    control("resupervise-exit-codes", "0")
    control("recover-exit-codes", "3 0")
    control("successor-reply", "replied")
    supervisor_id, claude_id, state_path = fresh_state()
    write_session_handoff()
    with replaced(program, "on_the_mac", lambda: True):
        status, half, output = second_half(state_path)
    check("on the Mac: recovery gets --open-iterm-window-per-seat, and its exit 3 is a failure run once more",
          status == 0 and calls("recover-calls") == [[SEAT, "--open-iterm-window-per-seat"]] * 2
          and "failed-restart-notice" not in output, output)

    asked = []
    with replaced(program, "run", lambda arguments, timeout=120: asked.append(arguments) or (0, "")):
        program.open_notice_page_for_the_user(Path("/x/notice.html"))
        with replaced(program, "on_the_mac", lambda: True):
            program.open_notice_page_for_the_user(Path("/x/notice.html"))
    check("a notice page opens through the page opener on ned-box and with open on the Mac",
          asked[0][1:] == [str(program.MAC_PAGE_OPENER), "/x/notice.html"]
          and asked[1] == ["open", "/x/notice.html"], asked)

    stoppable = subprocess.Popen(["sleep", "600"])
    started_process_ids.append(stoppable.pid)
    os.kill(stoppable.pid, signal.SIGSTOP)
    time.sleep(0.2)
    with replaced(program, "PROCESS_TABLE_DIRECTORY", SCRATCH_HOME / "no-proc-here"):
        stopped = program.process_is_stopped(stoppable.pid)
        os.kill(stoppable.pid, signal.SIGCONT)
        time.sleep(0.2)
        check("process_is_stopped without /proc reads ps, as on the Mac",
              stopped and not program.process_is_stopped(stoppable.pid))
    stoppable.kill()

    saved = os.environ.pop("NEDSCHORUS_HANDOFF_SUPERVISOR_RESTART_LOG_DIRECTORY")
    try:
        on_ned_box = program.default_log_directory()
        with replaced(program, "on_the_mac", lambda: True):
            on_mac = program.default_log_directory()
    finally:
        os.environ["NEDSCHORUS_HANDOFF_SUPERVISOR_RESTART_LOG_DIRECTORY"] = saved
    check("the log directory is in the log-store, on ned-box and through the Mac's mount",
          str(on_ned_box) == f"/home/nedlern/nedschorus-logs/{program.PROGRAM}"
          and str(on_mac) == f"/Volumes/nedhome/nedschorus-logs/{program.PROGRAM}", (on_ned_box, on_mac))


def detached_start_cases():
    directory = Path(tempfile.mkdtemp(dir=SCRATCH_HOME))
    state_path = directory / "state.json"
    state_path.write_text("{}")
    process_id = program.start_second_half(state_path)
    started_process_ids.append(process_id)
    session = os.getsid(process_id)
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline and running(process_id):
        time.sleep(0.1)
    log = (directory / "detached-output.log").read_text()
    check("the second half starts in a session of its own, with its output in detached-output.log",
          session != os.getsid(0) and "KeyError" in log, log)


def main_cases():
    errors = io.StringIO()
    with contextlib.redirect_stderr(errors):
        try:
            program.main([])
            status = 0
        except SystemExit as exit_:
            status = exit_.code
    check("main: no agent-seat named is a usage error", status == 2, errors.getvalue())


build_fixture()
step_0_cases()
step_2_cases()
foreground_supervisor_id, foreground_claude_id, _ = foreground_cases()
stop_fake(foreground_claude_id)
stop_fake(foreground_supervisor_id)
second_half_cases()
step_4_and_leftover_cases()
step_5_cases()
process_cases()
notice_cases()
mac_cases()
detached_start_cases()
main_cases()
end_started_processes()

if failures:
    print(f"\n{len(failures)} case(s) failed")
    sys.exit(1)
print("\nall cases passed")
