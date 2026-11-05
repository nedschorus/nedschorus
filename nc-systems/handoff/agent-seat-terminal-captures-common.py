"""Where each agent-seat's terminal output is captured, and the start of that terminal capture.

handoff-supervisor.py calls agent_seat_terminal_capture_start_in_this_tmux_pane at every start,
inside the agent-seat's tmux pane. It runs `tmux pipe-pane` on that pane, so everything the pane
shows from then on, terminal escape codes included, is appended to one new file:

    <captures directory>/<agent-seat>/<UTC start>-<agent-seat>-terminal-capture.log

with the start time written like 20261105T140322Z, so a listing sorts by time. A pane keeps its
pipe until the pane closes or another pipe-pane replaces it, so a terminal capture also holds what
the pane shows after the supervisor exits, such as the launcher's after-exit shell, and ends when
the next supervisor start in the same pane opens the next one.

The captures directory, agent_seat_terminal_captures_directory_on_this_machine_find:
- on ned-box, the log-store itself:
  /home/nedlern/nedschorus-logs/agent-session-files-by-machine/ned-box/agent-seat-terminal-captures
- elsewhere, which is the Mac, ~/.claude/agent-seat-terminal-captures, which
  scripts/transcript-mirror-to-log-store.py copies every minute to
  /home/nedlern/nedschorus-logs/agent-session-files-by-machine/mac/agent-seat-terminal-captures
- wherever AGENT_SEAT_TERMINAL_CAPTURES_DESTINATION names, when it is set, for tests.

agent-seat-terminal-captures-older-than-seven-days-delete.py, beside this file, deletes each
terminal capture whose last write is more than seven days old.

The start never stops an agent-seat: when the terminal capture cannot start, because the
supervisor is not in a tmux pane, the directory cannot be made, or tmux fails, the start returns a
line saying why, which the supervisor prints, and the agent-seat runs uncaptured.
"""

import os
import shlex
import socket
import subprocess
import time
from pathlib import Path

AGENT_SEAT_TERMINAL_CAPTURES_DIRECTORY_NAME = "agent-seat-terminal-captures"
AGENT_SEAT_TERMINAL_CAPTURES_DESTINATION_ENVIRONMENT_VARIABLE = "AGENT_SEAT_TERMINAL_CAPTURES_DESTINATION"
LOG_STORE_HOSTNAME = "ned-box"
LOG_STORE_AGENT_SESSION_FILES_BY_MACHINE_DIRECTORY = Path(
    "/home/nedlern/nedschorus-logs/agent-session-files-by-machine")
# The transcript mirror copies the Mac's ~/.claude/<name> to the store's mac/<name>.
CAPTURES_DIRECTORY_UNDER_HOME_OFF_THE_LOG_STORE_HOST = Path(".claude") / AGENT_SEAT_TERMINAL_CAPTURES_DIRECTORY_NAME
AGENT_SEAT_TERMINAL_CAPTURES_KEPT_DAYS = 7
TMUX_PIPE_PANE_TIMEOUT_SECONDS = 30
# Messages follow docs/nedschorus-wiki/nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md.
NOT_CAPTURED_OPENING_LINE = "this agent-seat's terminal output is not being captured to a file"
NOT_CAPTURED_AGENT_SEAT_RUNS_ON_LINE = (
    "The agent-seat runs as usual, uncaptured until its handoff-supervisor next starts, as it does "
    "at each session-handoff. Nothing needs doing for this agent-seat now.")
NOT_IN_A_TMUX_PANE_REMEDY_LINE = (
    "The agent-seat runs as usual, uncaptured. An agent-seat started by its launcher always runs "
    "in a tmux pane: start it with `launch-claude-ubuntu <agent-seat>` from the Mac for one on "
    "ned-box, or `launch-claude-mac <agent-seat>` on the Mac.")


def this_machine_is_the_log_store_host(hostname=None) -> bool:
    return (hostname or socket.gethostname()).split(".")[0] == LOG_STORE_HOSTNAME


def agent_seat_terminal_captures_directory_on_this_machine_find(hostname=None) -> Path:
    """Return the directory this machine's agent-seats capture their terminals into."""
    override = os.environ.get(AGENT_SEAT_TERMINAL_CAPTURES_DESTINATION_ENVIRONMENT_VARIABLE)
    if override:
        return Path(override)
    if this_machine_is_the_log_store_host(hostname):
        return (LOG_STORE_AGENT_SESSION_FILES_BY_MACHINE_DIRECTORY / LOG_STORE_HOSTNAME
                / AGENT_SEAT_TERMINAL_CAPTURES_DIRECTORY_NAME)
    return Path.home() / CAPTURES_DIRECTORY_UNDER_HOME_OFF_THE_LOG_STORE_HOST


def agent_seat_terminal_capture_path(agent_seat_name: str, started_at: time.struct_time,
                                     directory: Path) -> Path:
    started = time.strftime("%Y%m%dT%H%M%SZ", started_at)
    return directory / agent_seat_name / f"{started}-{agent_seat_name}-terminal-capture.log"


def agent_seat_terminal_capture_start_in_this_tmux_pane(agent_seat_name: str) -> str:
    """Pipe this tmux pane's output into a new terminal capture file; return the line saying where, or why not."""
    pane = os.environ.get("TMUX_PANE")
    if not os.environ.get("TMUX") or not pane:
        return (f"{NOT_CAPTURED_OPENING_LINE}: this handoff-supervisor is not in a tmux pane "
                f"(TMUX or TMUX_PANE is unset).\n{NOT_IN_A_TMUX_PANE_REMEDY_LINE}")
    path = agent_seat_terminal_capture_path(
        agent_seat_name, time.gmtime(), agent_seat_terminal_captures_directory_on_this_machine_find())
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        return (f"{NOT_CAPTURED_OPENING_LINE}: the directory {path.parent} could not be made "
                f"({error}).\n{NOT_CAPTURED_AGENT_SEAT_RUNS_ON_LINE}")
    # Without -o: a supervisor restarting itself at a session-handoff runs this again in the same
    # pane, and -o would close the pipe the earlier start opened instead of opening a new one.
    try:
        completed = subprocess.run(
            ["tmux", "pipe-pane", "-t", pane, f"exec cat >> {shlex.quote(str(path))}"],
            capture_output=True, text=True, check=False, timeout=TMUX_PIPE_PANE_TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as error:
        return (f"{NOT_CAPTURED_OPENING_LINE}: tmux pipe-pane could not run ({error}).\n"
                f"{NOT_CAPTURED_AGENT_SEAT_RUNS_ON_LINE}")
    if completed.returncode != 0:
        tmux_said = completed.stderr.strip()
        return (f"{NOT_CAPTURED_OPENING_LINE}: tmux pipe-pane exited {completed.returncode}"
                f"{': ' + tmux_said if tmux_said else ', saying nothing'}.\n"
                f"{NOT_CAPTURED_AGENT_SEAT_RUNS_ON_LINE}")
    return f"this agent-seat's terminal output is captured to {path}"
