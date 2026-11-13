#!/usr/bin/env python3
"""Restart an agent-seat's old handoff-supervisor onto main's code, from the reference-checkout.

Usage, on the machine the agent-seat runs on:
  python3 ~/Projects/nedschorus/nc-systems/handoff/handoff-supervisor-restart-onto-main-code-by-relaunch-from-reference-checkout.py <seat>

Run it for a handoff-supervisor that is running and will not restart itself, as
docs/nedschorus-wiki/nedschorus-handoff-supervisor-restart-onto-main-code-when-it-will-not-restart-itself.md
says. This program does steps 0, 2 and 4 to 7 of the restart, listed below. The agent-seat
being restarted does steps 1 and 3 itself: it gets ready (no subagent and no
test run of its own still running, its work committed, its walk-minutes written), runs this
program, and, when the program prints that the handoff-supervisor is frozen, writes its
session-handoff with the /handoff skill, without --ask-user-before-restart, naming in its next step the
result file this program prints, and stops working. On ned-box it runs this program through
`ssh nedlern@ned-box '<command>'`, because the Bash sandbox cannot signal the
handoff-supervisor.

In the foreground, the program:
- step 0: fast-forwards the reference-checkout ~/Projects/nedschorus to origin/main and checks
  that its HEAD is origin/main and that no tracked file is changed;
- step 2: reads the handoff-supervisor's process ID from <handoff dir>/<seat>-supervisor.lock,
  checks with ps that the process runs `handoff-supervisor.py --agent <seat>` followed by a
  space or the end of the line, notes its `claude` child, lists the processes working in the
  agent-home ~/agents/<seat>, and freezes the handoff-supervisor with SIGSTOP when its parent is
  a shell. Under a tmux server it cannot be frozen, because tmux continues it at once, so the
  program stops there and changes nothing;
- starts its own second half, detached in a session of its own and working in the home
  directory, so that ending the agent-seat's tmux session and agent-home processes does not end
  it, and prints what the agent-seat does next.

The detached second half, whose output goes to HANDOFF_SUPERVISOR_RESTART_DETACHED_SECOND_HALF_OUTPUT_FILE_NAME in the restart's log
directory:
- waits up to SESSION_HANDOFF_WAIT_LIMIT_SECONDS for <handoff dir>/<seat>-handoff.md to be
  modified after the freeze;
- step 4: ends the frozen handoff-supervisor with SIGKILL, then its `claude`, if still running,
  with SIGTERM and, 20 seconds later, SIGKILL;
- step 5: runs scripts/resupervise-seat.py <seat> --prepare-only from the reference-checkout,
  lists the processes working in the agent-home again, and ends each one also listed in step 2
  that is not a tmux server;
- step 6: runs scripts/recover-crashed-seats.py <seat> from the reference-checkout, with
  --open-iterm-window-per-seat on the Mac, which starts a new handoff-supervisor from the
  reference-checkout and the successor from the waiting session-handoff;
- step 7: waits up to 5 minutes from step 6's start for a new transcript in the agent-seat's
  project folder under ~/.claude/projects to hold a reply from the successor.
It sends no message to any agent. Every outcome is written to the result file, which the
successor reads when the session-handoff tells it to; the RESTARTED line is written before
step 7, because the successor's reading of the file is the reply step 7 waits for.

Failures, keyed on the agent-seat's state:
- before the freeze: the program prints why and exits 1; nothing was changed apart from the
  reference-checkout's fast-forward, which needs no undo;
- while the handoff-supervisor is frozen, it is unfrozen with SIGCONT, and the old
  handoff-supervisor carries on as before, consuming a session-handoff already written. The
  foreground sends the SIGCONT when the freeze did not hold or the second half could not start;
  the second half sends it when no new session-handoff came within the limit, when it was
  written with --ask-user-before-restart, which would make the new handoff-supervisor wait for an answer on
  a terminal nobody watches, or when step 4's ps check could not answer or its SIGKILL was
  refused;
- after step 4, while no new handoff-supervisor runs: the program removes the processes left
  from step 2's list and runs the failed command once more, checking with ps before each signal
  that the process ID still names the same command. A second failure, or a process in the
  agent-home that step 2 did not list, or a tmux server there, stops it;
- once a new handoff-supervisor runs, including when step 7 finds no reply: the program changes
  nothing, and records what ps shows for the agent-seat.
After the foreground has returned, every failure is also shown to the user as a notice: a text
file and an HTML page in the restart's log directory, the page opened in the Mac's browser
(through scripts/open-html-page-in-mac-browser-from-ned-box.py on ned-box, `open` on the Mac).
A notice that cannot be opened is still on disk, and the log says why it did not open. A state
file the second half cannot read, which the foreground writes just before starting it, is
reported only in HANDOFF_SUPERVISOR_RESTART_DETACHED_SECOND_HALF_OUTPUT_FILE_NAME, with the old handoff-supervisor left frozen.

What it does not handle: a handoff-supervisor that runs from a checkout other than the
reference-checkout keeps running there until step 4 ends it; the new one runs from the
reference-checkout. On ned-box the agent-crash-watcher may show the user a failed-restart-notice
while the agent-seat is down between steps 4 and 6; the result file says such a notice was
expected. It can harm work only as step 4 does by design: the agent-seat's agent-session and the
processes it started in its agent-home are ended, so anything the agent-seat did after writing
its session-handoff is lost.

Exit status, foreground: 0 frozen and the second half started, so the agent-seat writes its
session-handoff now; 1 not restarted, and the agent-seat carries on; 2 bad invocation.
Second half: 0 restarted and the successor replied; 1 a failure, shown to the user as a notice.

NEDSCHORUS_HANDOFF_SUPERVISOR_RESTART_LOG_DIRECTORY overrides where the log directories go: the
seam the nc-test-suite uses.
"""

import argparse
import html
import importlib.util
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROGRAM = "handoff-supervisor-restart-onto-main-code-by-relaunch-from-reference-checkout"
HANDOFF_SUPERVISOR_RESTART_SIGSTOP_FROZEN_HANDOFF_SUPERVISOR_DETAILS_FOR_DETACHED_SECOND_HALF_FILE_NAME = "handoff-supervisor-restart-onto-main-code-by-relaunch-from-reference-checkout-frozen-handoff-supervisor-details-for-detached-second-half.json"
HANDOFF_SUPERVISOR_RESTART_RESULT_FILE_NAME = "handoff-supervisor-restart-onto-main-code-by-relaunch-from-reference-checkout-result.txt"
HANDOFF_SUPERVISOR_RESTART_SECOND_HALF_FAILURE_NOTICE_TO_USER_FILE_NAME = "handoff-supervisor-restart-onto-main-code-by-relaunch-from-reference-checkout-failure-notice-to-user.txt"
HANDOFF_SUPERVISOR_RESTART_SECOND_HALF_FAILURE_NOTICE_TO_USER_HTML_PAGE_FILE_NAME = "handoff-supervisor-restart-onto-main-code-by-relaunch-from-reference-checkout-failure-notice-to-user.html"
HANDOFF_SUPERVISOR_RESTART_DETACHED_SECOND_HALF_OUTPUT_FILE_NAME = "handoff-supervisor-restart-onto-main-code-by-relaunch-from-reference-checkout-detached-second-half-output.log"
SYSTEM_DIRECTORY = Path(__file__).resolve().parent
REPOSITORY = SYSTEM_DIRECTORY.parent.parent


def load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


supervisor = load_module("handoff_supervisor", SYSTEM_DIRECTORY / "handoff-supervisor.py")
recovery = load_module("recover_crashed_seats", REPOSITORY / "scripts" / "recover-crashed-seats.py")
ned_box_home_path_constants = load_module(
    "ned_box_home_directory_and_its_mac_mount_point_path_constants_common",
    REPOSITORY / "nc-systems" / "general-tools"
    / "ned-box-home-directory-and-its-mac-mount-point-path-constants-common.py")
reference_checkout_steps = load_module(
    "handoff_reference_checkout_fetch_and_fast_forward_to_origin_main_check_common",
    SYSTEM_DIRECTORY / "handoff-reference-checkout-fetch-and-fast-forward-to-origin-main-check-common.py")

REFERENCE_CHECKOUT = reference_checkout_steps.REFERENCE_CHECKOUT
HANDOFF_DIRECTORY = Path("~/.claude/handoffs").expanduser()
AGENTS_ROOT = Path("~/agents").expanduser()
PROJECTS_ROOT = Path("~/.claude/projects").expanduser()
LOG_DIRECTORY_ENVIRONMENT_VARIABLE = "NEDSCHORUS_HANDOFF_SUPERVISOR_RESTART_LOG_DIRECTORY"
MAC_PAGE_OPENER = REPOSITORY / "scripts" / "open-html-page-in-mac-browser-from-ned-box.py"
PROCESS_TABLE_DIRECTORY = Path("/proc")

# Writing a session-handoff with the /handoff skill takes minutes; this limit bounds how long the
# old handoff-supervisor stays frozen when the agent-seat never writes one.
SESSION_HANDOFF_WAIT_LIMIT_SECONDS = 20 * 60
SESSION_HANDOFF_POLL_SECONDS = 5
PROCESS_END_GRACE_SECONDS = 20
SUCCESSOR_REPLY_WAIT_LIMIT_SECONDS = 5 * 60
SUCCESSOR_REPLY_POLL_SECONDS = 5
# tmux continues a process it parents at once after SIGSTOP; the state is read after this pause.
FREEZE_SETTLE_SECONDS = 1.0
SHELL_NAMES = ("sh", "bash", "zsh", "dash")
RECOVERY_WINDOW_NOT_OPENED_EXIT_STATUS = recovery.ALL_AGENT_SEATS_RECOVERED_BUT_MAC_WINDOW_OPEN_FAILED_EXIT_STATUS


class RestartFailure(Exception):
    """A step failed; the message says what failed and what the program printed or saw."""


def on_the_mac() -> bool:
    return sys.platform == "darwin"


def default_log_directory() -> Path:
    override = os.environ.get(LOG_DIRECTORY_ENVIRONMENT_VARIABLE)
    if override:
        return Path(override)
    home = (ned_box_home_path_constants.MAC_MOUNT_OF_NED_BOX_HOME if on_the_mac()
            else ned_box_home_path_constants.NED_BOX_HOME)
    return Path(home) / "nedschorus-logs" / PROGRAM


def clean_environment() -> dict:
    return supervisor.agent_seat_launch_environment_without_calling_agent_session_tmux_and_supervisor_variables(os.environ)


def run(arguments, timeout=120):
    """Return (exit status, standard output and error together); OSError and timeouts become exit 127 and 124."""
    try:
        completed = subprocess.run(arguments, capture_output=True, text=True, timeout=timeout,
                                   check=False, env=clean_environment(), cwd=str(Path.home()))
    except subprocess.TimeoutExpired:
        return 124, f"{' '.join(map(str, arguments))} did not finish within {timeout} seconds"
    except OSError as error:
        return 127, f"{' '.join(map(str, arguments))} could not be run: {error}"
    return completed.returncode, (completed.stdout + completed.stderr).strip()


def process_command_line(process_id: int):
    """Return the process's command line, or None when it is not running; raise when ps cannot answer."""
    command_line, answered = supervisor.read_process_command_line(process_id)
    if not answered:
        raise RestartFailure(f"ps could not tell whether process {process_id} is running")
    return command_line


def send_signal(process_id: int, signal_number) -> None:
    try:
        os.kill(process_id, signal_number)
    except ProcessLookupError:
        pass
    except OSError as error:
        raise RestartFailure(f"sending {signal.Signals(signal_number).name} to process "
                             f"{process_id} failed: {error}") from error


def process_is_stopped(process_id: int) -> bool:
    # ned-box has /proc, as the page's step 2 reads it; the Mac has only ps.
    if (PROCESS_TABLE_DIRECTORY / "self" / "status").is_file():
        try:
            text = (PROCESS_TABLE_DIRECTORY / str(process_id) / "status").read_text(encoding="utf-8")
        except OSError:
            return False
        # A process a tracer such as strace holds, as the test runner's input recording does,
        # shows SIGSTOP as "t (tracing stop)" rather than "T (stopped)".
        return any(line.startswith("State:") and ("T (stopped)" in line or "t (tracing stop)" in line)
                   for line in text.splitlines())
    status, output = run(["ps", "-o", "stat=", "-p", str(process_id)], timeout=15)
    return status == 0 and output[:1] in ("T", "t")


def supervisor_command_line_pattern(seat: str):
    return re.compile(rf"handoff-supervisor\.py --agent {re.escape(seat)}(\s|$)")


def process_table():
    """Return {process id: (parent process id, command line)} from ps."""
    status, output = run(["ps", "-ww", "-eo", "pid=,ppid=,args="], timeout=30)
    if status != 0:
        raise RestartFailure(f"ps -ww -eo pid,ppid,args exited {status}: {output}")
    table = {}
    for line in output.splitlines():
        parts = line.split(None, 2)
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            table[int(parts[0])] = (int(parts[1]), parts[2] if len(parts) == 3 else "")
    return table


def processes_working_in_agent_home(agent_home: Path, apart_from=()):
    """Return {process id: command line} for the processes whose working directory is in the agent-home."""
    process_ids, detail = recovery.processes_rooted_in_seat_directory(
        agent_home, require_a_complete_listing=True)
    if process_ids is None:
        raise RestartFailure(f"the processes whose working directory is in {agent_home} could not "
                             f"be listed: {detail}")
    listed = {}
    for process_id in process_ids:
        if process_id in apart_from:
            continue
        command_line = process_command_line(process_id)
        if command_line is not None:
            listed[process_id] = command_line
    return listed


def is_tmux_server(command_line: str) -> bool:
    words = command_line.split()
    return bool(words) and Path(words[0]).name.startswith("tmux")


def end_process(process_id: int, command_line: str, sleep=time.sleep) -> str:
    """End the process with SIGTERM, then SIGKILL after the grace; return what was done."""
    if process_command_line(process_id) != command_line:
        return f"process {process_id} ({command_line}) had already ended"
    send_signal(process_id, signal.SIGTERM)
    waited = 0.0
    while waited < PROCESS_END_GRACE_SECONDS:
        sleep(0.5)
        waited += 0.5
        if process_command_line(process_id) != command_line:
            return f"process {process_id} ({command_line}) ended on SIGTERM"
    send_signal(process_id, signal.SIGKILL)
    for _ in range(10):
        sleep(0.5)
        if process_command_line(process_id) != command_line:
            return f"process {process_id} ({command_line}) ended on SIGKILL"
    raise RestartFailure(f"process {process_id} ({command_line}) still runs after SIGKILL")


# ---------------------------------------------------------------- foreground: steps 0 and 2


def step_0_fast_forward_reference_checkout(checkout: Path) -> str:
    try:
        reference_checkout_steps.git_fetch_origin_or_raise(checkout)
        main = reference_checkout_steps.fast_forward_to_origin_main_and_check_or_raise(checkout)
    except reference_checkout_steps.ReferenceCheckoutGitStepFailed as error:
        raise RestartFailure(f"step 0: {error}") from None
    return f"step 0: the reference-checkout {checkout} is at origin/main {main}"


def step_2_identify_supervisor(seat: str, handoff_directory: Path):
    """Return the supervisor's process ID and command line, its claude's, and the process table."""
    lock_path = supervisor.supervisor_lock_path(handoff_directory, seat)
    try:
        supervisor_id = int(lock_path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError) as error:
        raise RestartFailure(f"step 2: the handoff-supervisor's process ID could not be read from "
                             f"{lock_path}: {error}") from error
    supervisor_command = process_command_line(supervisor_id)
    if supervisor_command is None or not supervisor_command_line_pattern(seat).search(supervisor_command):
        raise RestartFailure(f"step 2: process {supervisor_id}, named in {lock_path}, is not the "
                             f"handoff-supervisor of {seat}: `ps -ww -o args= -p {supervisor_id}` "
                             f"shows {supervisor_command or 'no process'}")
    table = process_table()
    children = [(process_id, command) for process_id, (parent, command) in table.items()
                if parent == supervisor_id and command.split()
                and Path(command.split()[0]).name == "claude"]
    if len(children) != 1:
        raise RestartFailure(f"step 2: the handoff-supervisor {supervisor_id} of {seat} has "
                             f"{len(children)} claude child processes, not one: {children}")
    claude_id, claude_command = children[0]
    return supervisor_id, supervisor_command, claude_id, claude_command, table


def parent_kind(supervisor_id: int, table) -> str:
    """Return 'shell', 'tmux' or the parent's command, for the freeze decision."""
    parent_id = table.get(supervisor_id, (0, ""))[0]
    status, name = run(["ps", "-o", "comm=", "-p", str(parent_id)], timeout=15)
    name = Path(name.strip()).name.lstrip("-") if status == 0 else ""
    if name in SHELL_NAMES:
        return "shell"
    if name.startswith("tmux"):
        return "tmux"
    return name or f"process {parent_id}, which ps could not name"


def freeze(supervisor_id: int, sleep=time.sleep) -> None:
    send_signal(supervisor_id, signal.SIGSTOP)
    sleep(FREEZE_SETTLE_SECONDS)
    if not process_is_stopped(supervisor_id):
        raise RestartFailure(f"step 2: the handoff-supervisor {supervisor_id} did not stay "
                             "stopped after SIGSTOP")


def unfreeze(supervisor_id: int, supervisor_command: str) -> str:
    try:
        if process_command_line(supervisor_id) != supervisor_command:
            return (f"The old handoff-supervisor {supervisor_id} is no longer running, so it was "
                    "not unfrozen")
        send_signal(supervisor_id, signal.SIGCONT)
    except RestartFailure as error:
        return (f"Unfreezing the old handoff-supervisor {supervisor_id} failed: {error}. It stays "
                f"frozen, and the agent-seat cannot hand off, until someone runs "
                f"`kill -CONT {supervisor_id}` on {socket.gethostname()}, after checking that "
                f"`ps -ww -o args= -p {supervisor_id}` still shows {supervisor_command}")
    return (f"The old handoff-supervisor {supervisor_id} was unfrozen with SIGCONT; it carries on "
            "on its old code, and consumes a session-handoff already written")


def start_second_half(state_path: Path) -> int:
    """Start the detached second half; return its process ID."""
    output = (state_path.parent / HANDOFF_SUPERVISOR_RESTART_DETACHED_SECOND_HALF_OUTPUT_FILE_NAME).open("a", encoding="utf-8")
    try:
        process = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--second-half", str(state_path)],
            stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
            cwd=str(Path.home()), env=clean_environment(), start_new_session=True)
    finally:
        output.close()
    return process.pid


def restart_log_directory(seat: str, log_root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    directory = log_root / f"{stamp}-{seat}"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def foreground(seat: str, start_second_half=start_second_half, sleep=time.sleep) -> int:
    os.chdir(Path.home())
    try:
        print(step_0_fast_forward_reference_checkout(REFERENCE_CHECKOUT))
        supervisor_id, supervisor_command, claude_id, claude_command, table = (
            step_2_identify_supervisor(seat, HANDOFF_DIRECTORY))
        kind = parent_kind(supervisor_id, table)
        if kind == "tmux":
            raise RestartFailure(
                f"step 2: the handoff-supervisor {supervisor_id} of {seat} runs directly under its "
                "tmux server, which would continue it at once after SIGSTOP, so it cannot be frozen. "
                "It was left running untouched")
        if kind != "shell":
            raise RestartFailure(f"step 2: the handoff-supervisor {supervisor_id} of {seat} runs "
                                 f"under {kind}, not a shell, so it was not frozen")
        agent_home = AGENTS_ROOT / seat
        agent_home_processes = processes_working_in_agent_home(agent_home, apart_from={os.getpid()})
        log_directory = restart_log_directory(seat, default_log_directory())
    except (RestartFailure, OSError) as error:
        print(not_restarted_message(seat, str(error), "Nothing of the agent-seat was changed."),
              file=sys.stderr)
        return 1

    try:
        freeze(supervisor_id, sleep=sleep)
        frozen_at = time.time()
        state_path = log_directory / HANDOFF_SUPERVISOR_RESTART_SIGSTOP_FROZEN_HANDOFF_SUPERVISOR_DETAILS_FOR_DETACHED_SECOND_HALF_FILE_NAME
        state_path.write_text(json.dumps({
            "seat": seat, "supervisor_id": supervisor_id, "supervisor_command": supervisor_command,
            "claude_id": claude_id, "claude_command": claude_command, "frozen_at": frozen_at,
            "agent_home_processes": {str(key): value for key, value in agent_home_processes.items()},
        }, indent=2) + "\n", encoding="utf-8")
        second_half_id = start_second_half(state_path)
    except (RestartFailure, OSError) as error:
        print(not_restarted_message(seat, str(error),
                                    unfreeze(supervisor_id, supervisor_command) + "."),
              file=sys.stderr)
        return 1
    result_path = log_directory / HANDOFF_SUPERVISOR_RESTART_RESULT_FILE_NAME
    print(f"step 2: the handoff-supervisor {supervisor_id} of {seat} is frozen, so it cannot start a "
          f"successor on its old code; its claude is process {claude_id}. The program's second half, "
          f"process {second_half_id}, waits up to {SESSION_HANDOFF_WAIT_LIMIT_SECONDS // 60} minutes "
          f"for a new session-handoff, then ends this agent-session and starts a new "
          f"handoff-supervisor from {REFERENCE_CHECKOUT}; the second half writes what it prints to "
          f"{log_directory / HANDOFF_SUPERVISOR_RESTART_DETACHED_SECOND_HALF_OUTPUT_FILE_NAME}.\n"
          f"If you are the agent-seat {seat}: write your session-handoff now with the /handoff skill, "
          f"without --ask-user-before-restart, because that flag makes the new handoff-supervisor wait for an "
          f"answer on the terminal. Add this sentence to the session-handoff's next step, keeping "
          f"what the next step already says: \"Read {result_path} and tell the user the restart's "
          f"result it reports.\" Then end your turn and start no new work: the second half ends "
          f"this agent-session.\n"
          f"If you cannot write the session-handoff: write no session-handoff. The second half then "
          f"unfreezes the old handoff-supervisor after {SESSION_HANDOFF_WAIT_LIMIT_SECONDS // 60} "
          f"minutes and shows the user a notice.")
    return 0


def not_restarted_message(seat: str, reason: str, what_was_changed: str) -> str:
    return (f"{PROGRAM}: the handoff-supervisor of {seat} was not restarted onto main's code, "
            f"because of this failure: {reason}.\n{what_was_changed}\n"
            f"Carry on working as before; do not run the restart steps by hand.\n"
            f"Tell the user: \"The handoff-supervisor of {seat} on {socket.gethostname()} was not "
            f"restarted onto main's code, so {seat} keeps running on its old code. The program "
            f"said: {reason}.\"\n"
            f"A subagent gives the text in quotation marks, both of its sentences, to the agent that dispatched it, not to the user.")


# ---------------------------------------------------------------- second half: steps 4 to 7


class SecondHalf:
    """Steps 4 to 7, writing each outcome to HANDOFF_SUPERVISOR_RESTART_RESULT_FILE_NAME and each failure to a notice."""

    def __init__(self, state_path: Path, sleep=time.sleep, now=time.time,
                 open_notice_page=None):
        self.state_path = state_path
        self.log_directory = state_path.parent
        self.state = json.loads(state_path.read_text(encoding="utf-8"))
        self.seat = self.state["seat"]
        self.sleep = sleep
        self.now = now
        self.open_notice_page = open_notice_page or open_notice_page_for_the_user
        self.result_path = self.log_directory / HANDOFF_SUPERVISOR_RESTART_RESULT_FILE_NAME
        self.step_4_started = False

    def record(self, line: str) -> None:
        print(line, flush=True)
        with self.result_path.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")

    def notice(self, text: str) -> None:
        notice_path = self.log_directory / HANDOFF_SUPERVISOR_RESTART_SECOND_HALF_FAILURE_NOTICE_TO_USER_FILE_NAME
        notice_path.write_text(text + "\n", encoding="utf-8")
        page_path = self.log_directory / HANDOFF_SUPERVISOR_RESTART_SECOND_HALF_FAILURE_NOTICE_TO_USER_HTML_PAGE_FILE_NAME
        title = f"{self.seat}: its handoff-supervisor restart needs you"
        page_path.write_text(
            f"<!doctype html><html><head><meta charset=\"utf-8\"><title>{html.escape(title)}</title>"
            f"</head><body><h1>{html.escape(title)}</h1><pre style=\"white-space:pre-wrap\">"
            f"{html.escape(text)}</pre></body></html>\n", encoding="utf-8")
        status, output = self.open_notice_page(page_path)
        if status != 0:
            print(f"the notice page {page_path} was not opened on the Mac (exit {status}): {output}; "
                  f"the notice is on disk at {notice_path}", flush=True)

    def fail(self, text: str) -> int:
        self.record(f"FAILED: {text}")
        record = str(self.result_path)
        if record.startswith(ned_box_home_path_constants.NED_BOX_HOME + "/"):
            record = (ned_box_home_path_constants.MAC_MOUNT_OF_NED_BOX_HOME
                      + record[len(ned_box_home_path_constants.NED_BOX_HOME):]
                      + f" on the Mac (on ned-box: {self.result_path})")
        attach = f"tmux -L {self.seat} attach -t {self.seat}"
        if not on_the_mac():
            attach = f"ssh -t nedlern@ned-box '{attach}'"
        self.notice(f"The restart of {self.seat}'s handoff-supervisor onto main's code, on "
                    f"{socket.gethostname()}, failed.\n{text}\n"
                    f"The restart program's record of every step: {record}\n"
                    f"To see the agent-seat, run in a Terminal on your Mac: `{attach}`\n"
                    f"To have it checked, ask an agent-seat on {socket.gethostname()} to read "
                    f"{self.result_path} and find why the restart failed.")
        return 1

    def wait_for_session_handoff(self) -> bool:
        handoff_path = supervisor.handoff_file_path(HANDOFF_DIRECTORY, self.seat)
        deadline = self.now() + SESSION_HANDOFF_WAIT_LIMIT_SECONDS
        while True:
            try:
                if handoff_path.stat().st_mtime > self.state["frozen_at"]:
                    return True
            except FileNotFoundError:
                pass
            if self.now() >= deadline:
                return False
            self.sleep(SESSION_HANDOFF_POLL_SECONDS)

    def end_leftovers_from_step_2(self, listed_now) -> None:
        """End each process in both lists that is not a tmux server; raise for any other."""
        listed_at_step_2 = {int(key): value for key, value
                            in self.state["agent_home_processes"].items()}
        others = {process_id: command for process_id, command in listed_now.items()
                  if listed_at_step_2.get(process_id) != command or is_tmux_server(command)}
        if others:
            raise RestartFailure(
                f"processes other than those left from the old agent-session have their working "
                f"directory in {AGENTS_ROOT / self.seat}, so the program stopped: " + "; ".join(
                    f"{process_id}: {command}" for process_id, command in others.items()))
        for process_id, command in listed_now.items():
            self.record(f"step 5: {end_process(process_id, command, sleep=self.sleep)}")

    def clear_agent_home(self) -> None:
        listed_now = processes_working_in_agent_home(AGENTS_ROOT / self.seat, apart_from={os.getpid()})
        self.end_leftovers_from_step_2(listed_now)

    def run_with_one_retry(self, step: str, arguments, accepted_statuses=(0,)):
        """Run a step's command; after a failure, clear the leftovers and run it once more."""
        status, output = run(arguments, timeout=600)
        self.record(f"{step}: `{' '.join(map(str, arguments))}` exited {status}:\n{output}")
        if status in accepted_statuses:
            return status
        self.clear_agent_home()
        status, output = run(arguments, timeout=600)
        self.record(f"{step}, run once more: exited {status}:\n{output}")
        if status in accepted_statuses:
            return status
        raise RestartFailure(f"{step} failed twice; the last exit was {status}, printing:\n{output}")

    def processes_of_the_seat(self) -> str:
        try:
            table = process_table()
        except RestartFailure as error:
            return str(error)
        pattern = supervisor_command_line_pattern(self.seat)
        supervisors = {process_id for process_id, (_, command) in table.items()
                       if pattern.search(command)}
        lines = [f"{process_id} {parent} {command}" for process_id, (parent, command) in table.items()
                 if process_id in supervisors or parent in supervisors]
        return "\n".join(lines) or f"ps shows no handoff-supervisor of {self.seat}"

    def successor_replied(self, transcripts_before, started_at) -> bool:
        project = recovery.harness_project_directory(AGENTS_ROOT / self.seat, PROJECTS_ROOT)
        deadline = started_at + SUCCESSOR_REPLY_WAIT_LIMIT_SECONDS
        while True:
            for transcript in sorted(project.glob("*.jsonl")) if project.is_dir() else []:
                if (transcript.name not in transcripts_before
                        and recovery.worth_resuming.substantive_turn_count(transcript) > 0):
                    self.record(f"step 7: the successor replied in {transcript}")
                    return True
            if self.now() >= deadline:
                return False
            self.sleep(SUCCESSOR_REPLY_POLL_SECONDS)

    def run_steps_and_report_any_unexpected_error(self) -> int:
        # Nobody reads the detached output: an error must reach the user, and must not leave the
        # old handoff-supervisor frozen.
        try:
            return self.run_steps()
        except Exception as error:  # noqa: BLE001
            unfrozen = ("" if self.step_4_started else " " + unfreeze(
                self.state["supervisor_id"], self.state["supervisor_command"]) + ".")
            return self.fail(f"the program stopped on an unexpected error: "
                             f"{type(error).__name__}: {error}.{unfrozen}")

    def run_steps(self) -> int:
        supervisor_id = self.state["supervisor_id"]
        supervisor_command = self.state["supervisor_command"]
        if not self.wait_for_session_handoff():
            return self.fail(
                f"no session-handoff of {self.seat} was written within "
                f"{SESSION_HANDOFF_WAIT_LIMIT_SECONDS // 60} minutes of the freeze. "
                f"{unfreeze(supervisor_id, supervisor_command)}.")
        self.record(f"step 4: the session-handoff of {self.seat} was written after the freeze")
        handoff_path = supervisor.handoff_file_path(HANDOFF_DIRECTORY, self.seat)
        if supervisor.read_ask_user_before_restart_reason_from_session_handoff_fields(
                supervisor.parse_handoff_file(handoff_path)):
            # A new handoff-supervisor would wait for an answer on a terminal nobody watches.
            return self.fail(
                f"the session-handoff {handoff_path} was written with --ask-user-before-restart, so a new "
                f"handoff-supervisor would wait for an answer on the agent-seat's terminal. "
                f"{unfreeze(supervisor_id, supervisor_command)}.")
        try:
            if process_command_line(supervisor_id) == supervisor_command:
                send_signal(supervisor_id, signal.SIGKILL)
                ended = f"step 4: the old handoff-supervisor {supervisor_id} was ended with SIGKILL"
            else:
                ended = f"step 4: the old handoff-supervisor {supervisor_id} had already ended"
        except RestartFailure as error:
            # The old handoff-supervisor may still be frozen, so it is unfrozen as before step 4.
            return self.fail(f"step 4: {error}. {unfreeze(supervisor_id, supervisor_command)}.")
        self.step_4_started = True
        self.record(ended)
        try:
            self.record(f"step 4: {end_process(self.state['claude_id'], self.state['claude_command'], sleep=self.sleep)}")
            prepare = [sys.executable, str(REFERENCE_CHECKOUT / "scripts" / "resupervise-seat.py"),
                       self.seat, "--prepare-only"]
            self.run_with_one_retry("step 5", prepare)
            self.clear_agent_home()
            project = recovery.harness_project_directory(AGENTS_ROOT / self.seat, PROJECTS_ROOT)
            transcripts_before = ({path.name for path in project.glob("*.jsonl")}
                                  if project.is_dir() else set())
            step_6_started_at = self.now()
            recover = [sys.executable, str(REFERENCE_CHECKOUT / "scripts" / "recover-crashed-seats.py"),
                       self.seat] + (["--open-iterm-window-per-seat"] if on_the_mac() else [])
            accepted = (0,) if on_the_mac() else (0, RECOVERY_WINDOW_NOT_OPENED_EXIT_STATUS)
            status = self.run_with_one_retry("step 6", recover, accepted_statuses=accepted)
        except RestartFailure as error:
            alive, liveness = supervisor.supervisor_liveness(
                supervisor.supervisor_state_path(HANDOFF_DIRECTORY, self.seat))
            if alive:
                return self.fail(f"{error}\nA new handoff-supervisor runs ({liveness}), so nothing "
                                 f"more was changed. ps shows:\n{self.processes_of_the_seat()}")
            return self.fail(f"{error}\nNo handoff-supervisor of {self.seat} runs, and its "
                             "session-handoff still waits on disk.")
        if status == RECOVERY_WINDOW_NOT_OPENED_EXIT_STATUS:
            self.record("step 6: the agent-seat started but no window opened on the Mac; that is "
                        "no failure")
        if not on_the_mac():
            self.record("Between steps 4 and 6 the agent-crash-watcher may have shown the user a "
                        "failed-restart-notice about this agent-seat; that notice was expected.")
        # Written before step 7 because the successor's first turn, reading this file, is the
        # reply step 7 waits for.
        self.record(f"RESTARTED: {self.seat}'s handoff-supervisor now runs main's code from "
                    f"{REFERENCE_CHECKOUT}. Step 7 waits for the successor's reply; a successor "
                    f"reading this line has replied.")
        if not self.successor_replied(transcripts_before, step_6_started_at):
            return self.fail(
                f"step 7: no new transcript of {self.seat} held a reply from the successor within "
                f"{SUCCESSOR_REPLY_WAIT_LIMIT_SECONDS // 60} minutes of step 6, which started a new "
                f"handoff-supervisor. That handoff-supervisor may already have consumed the "
                f"session-handoff, so the program changed nothing more. The agent-seat's "
                f"handoff-supervisors and their children, as ps lists them (process ID, parent "
                f"process ID, command):\n{self.processes_of_the_seat()}")
        return 0


def open_notice_page_for_the_user(page_path: Path):
    if on_the_mac():
        return run(["open", str(page_path)], timeout=30)
    return run([sys.executable, str(MAC_PAGE_OPENER), str(page_path)], timeout=60)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Restart an agent-seat's handoff-supervisor onto main's code.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    parser.add_argument("seat", nargs="?", help="the name of the agent-seat being restarted")
    parser.add_argument("--second-half", metavar="STATE_FILE",
                        help="what the foreground starts, detached: steps 4 to 7; no caller gives it")
    arguments = parser.parse_args(argv)
    if arguments.second_half:
        return SecondHalf(Path(arguments.second_half)).run_steps_and_report_any_unexpected_error()
    if not arguments.seat:
        parser.error("name the agent-seat being restarted")
    return foreground(arguments.seat)


if __name__ == "__main__":
    sys.exit(main())
