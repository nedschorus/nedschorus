#!/usr/bin/env python3
"""Restart an agent-seat's handoff-supervisor on main's current code, started by that agent-seat itself.

A handoff-supervisor that does not restart itself at a session-handoff keeps the
code it started with, so after a change to handoff-supervisor.py merges, it has to
be ended and a new one started from the waiting session-handoff. An agent-seat cannot do that from its own agent-session
by hand, because one step ends that agent-session. This program does it in a
process detached from the agent-session, so it keeps running after the
agent-session is ended. It is written for the Mac, where no other agent-seat can
act as the operator, and it works the same way on ned-box.

The agent-seat's own agent-session starts it, outside the Bash tool's sandbox,
which on the Mac blocks signals to processes outside it:

  python3 ~/Projects/nedschorus/nc-systems/handoff/handoff-supervisor-restart-onto-current-main-at-next-session-handoff-detached-from-its-agent-session.py <agent-seat name>

In the foreground, before it signals anything, it:
  1. refuses unless ~/Projects/nedschorus (--checkout) is on main with no
     uncommitted change to a tracked file, then fast-forwards it to origin/main,
     so the new handoff-supervisor and the two recovery programs run main's code;
     untracked files are allowed, because `git merge --ff-only` itself refuses
     when one would be overwritten;
  2. reads the handoff-supervisor's process ID from its lock file and confirms
     with ps that the process is handoff-supervisor.py --agent <name>;
  3. refuses when the handoff-supervisor is the tmux pane's own process, because
     tmux sends SIGCONT to a stopped pane process at once, so kill -STOP cannot
     hold it;
  4. finds the agent-session as the handoff-supervisor's child process whose
     command carries the session id the handoff-supervisor recorded in its state
     file;
  5. checks that the log file can be appended to;
  6. sends SIGSTOP to the handoff-supervisor and confirms with ps a second later
     that it is still stopped; if it is not, it sends SIGCONT and refuses.
It then prints what the agent-session does next, and detaches.

The detached process, which leaves the agent-seat's directory so that
recover-crashed-seats.py does not find it there, then:
  7. waits for a session-handoff whose restart-counter is above every counter
     seen before the freeze. If none arrives within --handoff-wait-minutes, or the
     agent-session ends first, or this program fails before step 8, it sends
     SIGCONT, so the old handoff-supervisor carries on as before, and stops;
  8. sends SIGKILL to the handoff-supervisor and SIGTERM to the agent-session,
     then SIGKILL to the agent-session if it is still running 20 seconds later,
     and SIGTERM to each process the agent-session had started that is still
     running, by process ID, then SIGKILL to it if it is still running 5 seconds
     later, because recover-crashed-seats.py refuses while a process runs in the
     agent-seat's directory;
  9. runs resupervise-seat.py <name> --prepare-only, which refuses unless the
     handoff waits and no handoff-supervisor is alive, and removes the agent-seat's
     tmux session; and, if that succeeds,
 10. runs recover-crashed-seats.py <name>, which finds the handoff waiting and
     starts the agent-seat once, detached, with launch-claude-mac --no-attach on
     the Mac. resupervise-seat.py without --prepare-only is not used: it ends by
     running the launcher attached, which needs a terminal this process does not
     have.

Process IDs are read only from the lock file, the state file and ps, never by a
name pattern: every agent-seat runs as the same Unix user, so a pattern would
reach the other agent-seats too.

Every step is appended, with a UTC time, to
~/.claude/handoffs/<name>-handoff-supervisor-restart-log.txt, beside
recover-crashed-seats.py's own log; the detached process's stdout and stderr go
there too. The last line of each restart starts with RESTARTED, NOT RESTARTED or
FAILED. A FAILED line means the old handoff-supervisor was ended and no new one
was confirmed: the agent-seat stays down, with its handoff waiting on disk, until
someone reads the log and runs recover-crashed-seats.py again.

This program does not tell merge-lane-2. The agent-session's handoff carries
that instruction to its successor: the foreground output tells the agent to name
the log file in its handoff's next step.

What can go wrong: a handoff written with --dont-restart is still taken as the
signal, and recover-crashed-seats.py then does not relaunch the agent-seat, at
the handoff's own request, so the agent-seat stays down until it is launched by
hand. A process left in the agent-seat's directory that the agent-session did
not start, such as a shell the user opened there, makes recover-crashed-seats.py
refuse, and the result is a FAILED line. A process ID can be reused between the
moment it is read and the moment it is signalled; the gap is a few seconds.

Exit status of the foreground: 0 when the handoff-supervisor is frozen and the
detached process started; 1 when it refused, having signalled nothing, or having
sent SIGCONT after a freeze that did not hold; 2 for a bad invocation.
"""

import argparse
import importlib.util
import os
import re
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Messages here follow docs/nedschorus-wiki/nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md.
_supervisor_spec = importlib.util.spec_from_file_location(
    "handoff_supervisor", Path(__file__).resolve().with_name("handoff-supervisor.py"))
supervisor = importlib.util.module_from_spec(_supervisor_spec)
_supervisor_spec.loader.exec_module(supervisor)

PROGRAM = Path(__file__).stem
LOG_FILE_SUFFIX = "-handoff-supervisor-restart-log.txt"
DEFAULT_CHECKOUT = Path("~/Projects/nedschorus").expanduser()
DEFAULT_HANDOFF_DIRECTORY = Path("~/.claude/handoffs").expanduser()
DEFAULT_HANDOFF_WAIT_MINUTES = 20
HANDOFF_POLL_SECONDS = 2.0
# How long tmux takes to send SIGCONT to a stopped pane process is well under this.
FREEZE_CONFIRMATION_DELAY_SECONDS = 1.0
# The handoff-supervisor gives an agent-session the same time to end after SIGTERM.
AGENT_SESSION_SIGTERM_TO_SIGKILL_WAIT_SECONDS = 20.0
AGENT_SESSION_PROCESS_TREE_SIGTERM_TO_SIGKILL_WAIT_SECONDS = 5.0
AGENT_SEAT_NAME_PATTERN = re.compile(r"[A-Za-z0-9_-]+")
# recover-crashed-seats.py exits 3 when the agent-seat came up but no window opened on the Mac.
ALL_AGENT_SEATS_RECOVERED_BUT_MAC_WINDOW_NOT_OPENED_EXIT_STATUS = 3


class HandoffSupervisorRestartRefusal(Exception):
    """A reason to stop before the restart goes on."""


def handoff_supervisor_restart_log_path_for_agent_seat(handoff_directory: Path, name: str) -> Path:
    return handoff_directory / f"{name}{LOG_FILE_SUFFIX}"


def append_to_log(log_path: Path, name: str, line: str) -> None:
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with log_path.open("a", encoding="utf-8") as stream:
        stream.write(f"{stamp} {name}: {line}\n")


def run_git(checkout: Path, *arguments):
    return subprocess.run(["git", "-C", str(checkout), *arguments],
                          capture_output=True, text=True, check=False)


def failed_command_output_on_one_line(completed) -> str:
    return " ".join((completed.stderr or completed.stdout or "no output").split())


def fast_forward_checkout_to_origin_main(checkout: Path) -> str:
    """Refuse unless the checkout is on a clean main, then fast-forward it; return the new commit."""
    branch = run_git(checkout, "symbolic-ref", "--short", "HEAD")
    if branch.returncode != 0 or branch.stdout.strip() != "main":
        found = branch.stdout.strip() if branch.returncode == 0 else failed_command_output_on_one_line(branch)
        raise HandoffSupervisorRestartRefusal(f"{checkout} is not on main ({found}), so the new handoff-supervisor would "
                      f"not run main's code. If {checkout} holds no work of its own, run "
                      f"`git -C {checkout} switch main`.")
    status = run_git(checkout, "status", "--porcelain", "--untracked-files=no")
    if status.returncode != 0:
        raise HandoffSupervisorRestartRefusal(f"`git status` failed in {checkout}: {failed_command_output_on_one_line(status)}")
    if status.stdout.strip():
        changed = ", ".join(line[3:] for line in status.stdout.splitlines())
        raise HandoffSupervisorRestartRefusal(f"{checkout} has uncommitted changes to tracked files ({changed}). "
                      "They are not this program's to discard, and the fast-forward to "
                      "origin/main would mix them into the code the new handoff-supervisor runs.")
    fetch = run_git(checkout, "fetch", "origin", "main")
    if fetch.returncode != 0:
        raise HandoffSupervisorRestartRefusal(f"`git fetch origin main` failed in {checkout}: {failed_command_output_on_one_line(fetch)}")
    merge = run_git(checkout, "merge", "--ff-only", "origin/main")
    if merge.returncode != 0:
        raise HandoffSupervisorRestartRefusal(f"`git merge --ff-only origin/main` failed in {checkout}: "
                      f"{failed_command_output_on_one_line(merge)}")
    return run_git(checkout, "rev-parse", "--short", "HEAD").stdout.strip()


def read_process_table():
    """Return {process ID: (parent process ID, state, command line)} from ps."""
    completed = subprocess.run(["ps", "-A", "-ww", "-o", "pid=,ppid=,stat=,args="],
                               capture_output=True, text=True, check=False, timeout=30)
    if completed.returncode != 0:
        raise HandoffSupervisorRestartRefusal(f"ps exited {completed.returncode}: {failed_command_output_on_one_line(completed)}")
    table = {}
    for line in completed.stdout.splitlines():
        words = line.split(None, 3)
        if len(words) < 3:
            continue
        table[int(words[0])] = (int(words[1]), words[2], words[3] if len(words) == 4 else "")
    return table


def confirmed_supervisor_process_id(handoff_directory: Path, name: str) -> int:
    lock_path = supervisor.supervisor_lock_path(handoff_directory, name)
    try:
        process_id = int(lock_path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError) as error:
        raise HandoffSupervisorRestartRefusal(f"no readable handoff-supervisor lock at {lock_path} ({error}), so no "
                      f"handoff-supervisor of {name} is known to be running.")
    command_line, ps_answered = supervisor.read_process_command_line(process_id)
    if not ps_answered:
        raise HandoffSupervisorRestartRefusal(f"ps could not say what process {process_id}, named in {lock_path}, is.")
    held, identity = supervisor.process_is_supervisor_for_agent(
        process_id, name, read_command_line=lambda _: (command_line, True))
    if not held:
        raise HandoffSupervisorRestartRefusal(f"the lock {lock_path} names process {process_id}, but {identity}.")
    return process_id


def refuse_handoff_supervisor_restart_when_its_parent_process_is_tmux(process_table, supervisor_process_id: int) -> None:
    parent_process_id = process_table[supervisor_process_id][0]
    parent_command = process_table.get(parent_process_id, (0, "", ""))[2]
    first_word = (parent_command.split() or [""])[0].rpartition("/")[2]
    if first_word.startswith("tmux"):
        raise HandoffSupervisorRestartRefusal(
            f"handoff-supervisor {supervisor_process_id} is its tmux pane's own process (its "
            f"parent {parent_process_id} is `{parent_command}`), and tmux sends SIGCONT to a "
            "stopped pane process at once, so SIGSTOP cannot hold it and this program cannot "
            "restart this agent-seat.")


def find_agent_session_process_id_among_handoff_supervisor_children(process_table, supervisor_process_id: int, session_id) -> int:
    if not session_id:
        raise HandoffSupervisorRestartRefusal("the handoff-supervisor's state file records no session id, so its "
                      "agent-session cannot be told from its other child processes.")
    matches = []
    for process_id, (parent_process_id, _, command_line) in process_table.items():
        words = command_line.split()
        if parent_process_id == supervisor_process_id and any(
                word in ("--session-id", "--resume") and position + 1 < len(words)
                and words[position + 1] == session_id
                for position, word in enumerate(words)):
            matches.append(process_id)
    if len(matches) != 1:
        raise HandoffSupervisorRestartRefusal(f"found {len(matches)} child processes of handoff-supervisor "
                      f"{supervisor_process_id} carrying session id {session_id}, not one.")
    return matches[0]


def descendant_process_ids(process_table, ancestor_process_id: int):
    descendants, frontier = [], [ancestor_process_id]
    while frontier:
        parent = frontier.pop()
        # A process ID reused while ps reads the table can make the parent links loop.
        children = [process_id for process_id, (parent_process_id, _, _) in process_table.items()
                    if parent_process_id == parent and process_id != ancestor_process_id
                    and process_id not in descendants]
        descendants += children
        frontier += children
    return descendants


def highest_restart_counter_field_value_in_session_handoff_and_handoff_supervisor_state_files(handoff_directory: Path, name: str, state: dict) -> int:
    counters = [state.get("consumed_counter")]
    handoff_path = supervisor.handoff_file_path(handoff_directory, name)
    if handoff_path.is_file():
        counters.append(supervisor.counter_from(supervisor.parse_handoff_file(handoff_path)))
    return max((counter for counter in counters if counter is not None), default=-1)


def freeze_supervisor(supervisor_process_id: int, sleep=time.sleep, read_table=read_process_table):
    try:
        os.kill(supervisor_process_id, signal.SIGSTOP)
    except PermissionError as error:
        raise HandoffSupervisorRestartRefusal(f"SIGSTOP to handoff-supervisor {supervisor_process_id} was refused "
                      f"({error}). The Bash tool's sandbox blocks signals to processes outside "
                      "it: run this program again with the Bash tool's dangerouslyDisableSandbox "
                      "set to true.")
    sleep(FREEZE_CONFIRMATION_DELAY_SECONDS)
    state = read_table().get(supervisor_process_id, (0, "gone", ""))[1]
    # Linux shows a stopped process as t instead of T inside some PID namespaces, such as bwrap's.
    if not state.startswith(("T", "t")):
        os.kill(supervisor_process_id, signal.SIGCONT)
        raise HandoffSupervisorRestartRefusal(f"handoff-supervisor {supervisor_process_id} did not stay stopped after "
                      f"SIGSTOP (ps state {state}), so SIGCONT was sent to it, and this program "
                      "cannot restart this agent-seat.")


def process_is_running(process_id: int, read_table=read_process_table) -> bool:
    entry = read_table().get(process_id)
    return entry is not None and not entry[1].startswith("Z")


def wait_for_new_handoff(handoff_directory: Path, name: str, counter_seen: int,
                         agent_session_process: int, deadline_seconds: float,
                         sleep=time.sleep, monotonic=time.monotonic,
                         read_table=read_process_table):
    """Return (True, counter) when a new handoff arrives, else (False, reason)."""
    handoff_path = supervisor.handoff_file_path(handoff_directory, name)
    started = monotonic()
    while True:
        if handoff_path.is_file():
            counter = supervisor.counter_from(supervisor.parse_handoff_file(handoff_path))
            if counter is not None and counter > counter_seen:
                return True, counter
        if not process_is_running(agent_session_process, read_table):
            return False, (f"agent-session process {agent_session_process} ended without "
                           f"writing a handoff to {handoff_path}")
        if monotonic() - started >= deadline_seconds:
            return False, (f"no handoff with a restart-counter above {counter_seen} reached "
                           f"{handoff_path} within {deadline_seconds / 60:g} minutes")
        sleep(HANDOFF_POLL_SECONDS)


def end_process_by_sigterm_then_sigkill_after_wait(process_id: int, wait_seconds: float, log, sleep=time.sleep,
                monotonic=time.monotonic, read_table=read_process_table) -> None:
    try:
        os.kill(process_id, signal.SIGTERM)
    except ProcessLookupError:
        return
    started = monotonic()
    while process_is_running(process_id, read_table):
        if monotonic() - started >= wait_seconds:
            log(f"process {process_id} was still running {wait_seconds:.0f}s after SIGTERM; "
                "sent SIGKILL")
            try:
                os.kill(process_id, signal.SIGKILL)
            except ProcessLookupError:
                pass
            return
        sleep(0.5)


def run_recovery_program(checkout: Path, program_name: str, arguments, log) -> int:
    command = [sys.executable, str(checkout / "scripts" / program_name), *arguments]
    environment = supervisor.agent_seat_launch_environment_without_calling_agent_session_tmux_and_supervisor_variables(os.environ)
    completed = subprocess.run(command, capture_output=True, text=True, check=False,
                               env=environment, cwd=str(Path.home()))
    for line in (completed.stdout + completed.stderr).splitlines():
        log(f"  {program_name}: {line}")
    log(f"{program_name} exited {completed.returncode}")
    return completed.returncode


def wait_for_new_session_handoff_then_kill_old_handoff_supervisor_and_agent_session_and_relaunch_agent_seat(name: str, handoff_directory: Path, checkout: Path,
                          supervisor_process_id: int, agent_session_process: int,
                          counter_seen: int, deadline_seconds: float, log,
                          sleep=time.sleep, monotonic=time.monotonic,
                          read_table=read_process_table) -> int:
    """The detached half: wait for the handoff, end the old processes, start the agent-seat again."""
    supervisor_ended = False
    try:
        log(f"handoff-supervisor {supervisor_process_id} is stopped; waiting for agent-session "
            f"process {agent_session_process} to write a handoff with a restart-counter above "
            f"{counter_seen}")
        arrived, detail = wait_for_new_handoff(handoff_directory, name, counter_seen,
                                               agent_session_process, deadline_seconds,
                                               sleep, monotonic, read_table)
        if not arrived:
            os.kill(supervisor_process_id, signal.SIGCONT)
            log(f"NOT RESTARTED: {detail}; sent SIGCONT to handoff-supervisor "
                f"{supervisor_process_id}, which carries on with the code it started with.")
            return 1
        log(f"handoff with restart-counter {detail} arrived")

        agent_session_tree = [process_id for process_id in
                              descendant_process_ids(read_table(), agent_session_process)
                              if process_id != os.getpid()]
        supervisor_ended = True
        os.kill(supervisor_process_id, signal.SIGKILL)
        log(f"sent SIGKILL to handoff-supervisor {supervisor_process_id}")
        end_process_by_sigterm_then_sigkill_after_wait(agent_session_process, AGENT_SESSION_SIGTERM_TO_SIGKILL_WAIT_SECONDS, log,
                    sleep, monotonic, read_table)
        log(f"agent-session process {agent_session_process} has ended")
        for process_id in agent_session_tree:
            end_process_by_sigterm_then_sigkill_after_wait(process_id, AGENT_SESSION_PROCESS_TREE_SIGTERM_TO_SIGKILL_WAIT_SECONDS, log,
                        sleep, monotonic, read_table)

        handoff_arguments = ["--handoff-dir", str(handoff_directory)]
        down = (f"The agent-seat {name} is down on {socket.gethostname()}, and its handoff "
                f"waits in {handoff_directory}. Once the cause in the lines above this one in "
                f"this log is removed, run in a Terminal on {socket.gethostname()}:")
        prepare_command = (f"python3 {checkout / 'scripts' / 'resupervise-seat.py'} {name} "
                           "--prepare-only")
        recover_command = f"python3 {checkout / 'scripts' / 'recover-crashed-seats.py'} {name}"
        prepared = run_recovery_program(checkout, "resupervise-seat.py",
                                        [name, "--prepare-only", *handoff_arguments], log)
        if prepared != 0:
            log(f"FAILED: resupervise-seat.py --prepare-only refused. {down} "
                f"{prepare_command} && {recover_command}")
            return 1
        recovered = run_recovery_program(checkout, "recover-crashed-seats.py",
                                         [name, *handoff_arguments], log)
        if recovered in (0, ALL_AGENT_SEATS_RECOVERED_BUT_MAC_WINDOW_NOT_OPENED_EXIT_STATUS):
            log(f"RESTARTED: {name} runs under a new handoff-supervisor from {checkout}")
            return 0
        log(f"FAILED: recover-crashed-seats.py did not report {name} running. {down} "
            f"{recover_command}")
        return 1
    except Exception as error:
        if not supervisor_ended:
            try:
                os.kill(supervisor_process_id, signal.SIGCONT)
            except ProcessLookupError:
                pass
            log(f"NOT RESTARTED: this program failed ({error!r}); sent SIGCONT to "
                f"handoff-supervisor {supervisor_process_id}, which carries on with the code it "
                "started with.")
        else:
            log(f"FAILED: this program failed ({error!r}) after ending handoff-supervisor "
                f"{supervisor_process_id}. The agent-seat {name} may be down on "
                f"{socket.gethostname()}, with its handoff waiting in {handoff_directory}: run "
                f"in a Terminal on {socket.gethostname()}: "
                f"python3 {checkout / 'scripts' / 'recover-crashed-seats.py'} {name}")
        raise


def fork_child_detached_into_new_unix_session(log_path: Path) -> bool:
    """Fork; return False in the foreground and True in the detached child."""
    sys.stdout.flush()
    sys.stderr.flush()
    if os.fork() != 0:
        return False
    os.setsid()
    os.chdir(Path.home())
    with open(os.devnull, "rb") as null:
        os.dup2(null.fileno(), 0)
    with log_path.open("a", encoding="utf-8") as log_stream:
        os.dup2(log_stream.fileno(), 1)
        os.dup2(log_stream.fileno(), 2)
    return True


def report_refusal(refusal: HandoffSupervisorRestartRefusal, log) -> None:
    print(f"{PROGRAM}: REFUSED: {refusal}\n"
          "The handoff-supervisor and your agent-session run as before, so do not write a "
          "handoff for this restart.\n"
          "If the reason above names a fix you can make, make it and run this program once "
          "more.\n"
          "Otherwise, or if it refuses again, tell merge-lane-2 with SendMessage, quoting "
          "these lines; a subagent tells the agent that dispatched it instead.",
          file=sys.stderr)
    try:
        log(f"NOT RESTARTED: {refusal}")
    except OSError:
        pass


def main(argv=None, detach=fork_child_detached_into_new_unix_session, sleep=time.sleep,
         monotonic=time.monotonic, read_table=read_process_table) -> int:
    parser = argparse.ArgumentParser(
        description="Restart this agent-seat's handoff-supervisor on main's current code, "
                    "from a process that outlives the agent-session.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    parser.add_argument("name", help="the agent-seat's name")
    parser.add_argument("--handoff-wait-minutes", type=float, default=DEFAULT_HANDOFF_WAIT_MINUTES,
                        help="how long to wait for the handoff before sending SIGCONT "
                             f"(default {DEFAULT_HANDOFF_WAIT_MINUTES})")
    parser.add_argument("--handoff-dir", type=Path, default=DEFAULT_HANDOFF_DIRECTORY,
                        help="the handoff directory (default ~/.claude/handoffs)")
    parser.add_argument("--checkout", type=Path, default=DEFAULT_CHECKOUT,
                        help="the reference checkout to fast-forward and run the recovery "
                             "programs from (default ~/Projects/nedschorus)")
    arguments = parser.parse_args(argv)
    name = arguments.name
    if not AGENT_SEAT_NAME_PATTERN.fullmatch(name):
        parser.error("an agent-seat's name is letters, digits, - and _")
    if arguments.handoff_wait_minutes <= 0:
        parser.error("--handoff-wait-minutes must be above 0")
    handoff_directory = arguments.handoff_dir.expanduser()
    checkout = arguments.checkout.expanduser()
    log_path = handoff_supervisor_restart_log_path_for_agent_seat(handoff_directory, name)

    def log(line: str) -> None:
        append_to_log(log_path, name, line)

    try:
        try:
            log("restart requested")
        except OSError as error:
            raise HandoffSupervisorRestartRefusal(f"cannot append to the log {log_path}: {error}")
        commit = fast_forward_checkout_to_origin_main(checkout)
        log(f"{checkout} is on main at {commit}")
        supervisor_process_id = confirmed_supervisor_process_id(handoff_directory, name)
        process_table = read_table()
        if supervisor_process_id not in process_table:
            raise HandoffSupervisorRestartRefusal(f"handoff-supervisor {supervisor_process_id} is not in ps's process list.")
        refuse_handoff_supervisor_restart_when_its_parent_process_is_tmux(process_table, supervisor_process_id)
        state = supervisor.read_supervisor_state(
            supervisor.supervisor_state_path(handoff_directory, name))
        agent_session = find_agent_session_process_id_among_handoff_supervisor_children(
            process_table, supervisor_process_id,
            state.get(supervisor.LAUNCHED_SESSION_ID_STATE_KEY))
        counter_seen = highest_restart_counter_field_value_in_session_handoff_and_handoff_supervisor_state_files(handoff_directory, name, state)
        freeze_supervisor(supervisor_process_id, sleep, read_table)
    except HandoffSupervisorRestartRefusal as refusal:
        report_refusal(refusal, log)
        return 1
    try:
        detached = detach(log_path)
    except OSError as error:
        os.kill(supervisor_process_id, signal.SIGCONT)
        report_refusal(HandoffSupervisorRestartRefusal(f"the detached process could not be started ({error!r}), so "
                               f"SIGCONT was sent to handoff-supervisor {supervisor_process_id}."),
                       log)
        return 1
    if detached:
        return wait_for_new_session_handoff_then_kill_old_handoff_supervisor_and_agent_session_and_relaunch_agent_seat(name, handoff_directory, checkout, supervisor_process_id,
                                     agent_session, counter_seen,
                                     arguments.handoff_wait_minutes * 60, log,
                                     sleep, monotonic, read_table)
    print(f"{PROGRAM}: handoff-supervisor {supervisor_process_id} of {name} is stopped, and a "
          "detached process now waits for your handoff.\n"
          "Write your handoff now with the handoff skill, without --dont-restart.\n"
          f"Put this in its next step, so that your successor reports the restart: \"FIRST "
          f"ACTION: read the end of {log_path} and tell merge-lane-2 with SendMessage what its "
          "last line says about the handoff-supervisor restart.\"\n"
          f"If no handoff arrives within {arguments.handoff_wait_minutes:g} minutes, the "
          "detached process sends SIGCONT and the handoff-supervisor carries on unchanged; "
          f"its result is then in {log_path}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
