#!/usr/bin/env python3
"""Turn Remote Control back on in a ned-box agent-seat that a Claude login on ned-box turned off.

Usage, on ned-box:
  nc-systems/handoff/handoff-agent-seat-remote-control-lost-at-claude-login-reconnect-by-tmux-typing-watcher.py
      one run: check every running agent-seat and act. Cron runs this once a minute.
  nc-systems/handoff/handoff-agent-seat-remote-control-lost-at-claude-login-reconnect-by-tmux-typing-watcher.py --show-notice FILE
      what a notice window on the user's Mac runs: print FILE, then wait for
      Enter and close.

When the claude.ai account or organization signed in on ned-box changes, as a
`claude /login` does, Claude Code drops Remote Control in every running
session and logs, in the session's transcript, a system line starting with
DISCONNECT_TEXT. It does not turn Remote Control back on. Each run finds every
running agent-seat (a live `claude` process whose parent is
`handoff-supervisor.py --agent <seat>`), reads its session record
~/.claude/sessions/<pid>.json and its current transcript, and types
`/remote-control <seat>` and Enter into the claude's own tmux pane (server
`-L <seat>`, the pane id the session record's "tmux" field ends with) when all
of these hold:
- the transcript's latest Remote Control line is that disconnect line, with no
  later bridge_status line ("/remote-control is active"), which Claude Code
  logs whenever Remote Control comes back on, by the command or by itself;
- this program has not already typed for that disconnect line;
- the record's status is not "waiting", which Claude Code sets while a dialog
  waits for an answer;
- the pane is not in a tmux mode such as copy mode, where typed keys go to tmux
  and "/" starts a search;
- the pane shows the prompt line empty: the line between the input box's two
  rules is the prompt character alone.
Otherwise it types nothing and tries again on the next run. Typing only on the
disconnect line matters: while Remote Control is on, the same command opens
its menu instead, whose choices include "Disconnect this session".

Each run reads a transcript only from where the run before stopped: the place
reached, the bytes just before it and the disconnect line found by then are
saved per transcript in TRANSCRIPT_READ_POSITIONS_FILE_NAME in LOG_DIRECTORY. A transcript
whose bytes before that place no longer match is read whole, and so is every
transcript when the saved file is missing or unreadable.

It does not check afterwards that Remote Control came back. A failure it meets
in one agent-seat, such as a session record it cannot read or a tmux command
that fails or times out, is written to decisions.jsonl in LOG_DIRECTORY and
printed to stderr; the run goes on to the next agent-seat and, once every
agent-seat is checked, exits 1. The first time a failure is met, it is also
shown to the user in a terminal window on his Mac, opened with
scripts/open-mac-window-from-ned-box.py running --show-notice. "The first
time" counts once per agent-seat, claude process and kind of failure; once per
disconnect line for a failed typing; and once per error text for a failure that
stops the whole run. When the notice cannot be written or the window cannot be
opened, that is printed to stderr too, and a later run that meets the same
failure tries the notice again. Each typing is also written to decisions.jsonl, which is what
keeps a later run from typing again for the same disconnect line.

Off ned-box the program refuses: the agent-seats it reads are ned-box's.

SCHEDULED. The job is declared in
nc-systems/general-tools/scheduled-jobs-on-each-machine.json and installed
with nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py
--install --job handoff-agent-seat-remote-control-lost-at-claude-login-reconnect-by-tmux-typing-watcher,
on ned-box only, as the cron line
    * * * * * /usr/bin/python3 /home/nedlern/Projects/nedschorus/nc-systems/handoff/handoff-agent-seat-remote-control-lost-at-claude-login-reconnect-by-tmux-typing-watcher.py >> /home/nedlern/.claude/handoff-agent-seat-remote-control-lost-at-claude-login-reconnect-by-tmux-typing-watcher.log 2>&1

The environment variables named by the *_ENVIRONMENT_VARIABLE constants
override where the log, the session records, the transcripts and the process
table are read from: the seams the nc-test-suite uses.
"""

import argparse
import fcntl
import getpass
import importlib.util
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROGRAM = "handoff-agent-seat-remote-control-lost-at-claude-login-reconnect-by-tmux-typing-watcher"

REPOSITORY = Path(__file__).resolve().parent.parent.parent
MAC_WINDOW_OPENER_PROGRAM = REPOSITORY / "scripts" / "open-mac-window-from-ned-box.py"
_project_directory_specification = importlib.util.spec_from_file_location(
    "claude_code_session_transcript_project_directory_for_agent_seat_common",
    REPOSITORY / "scripts" / "claude-code-session-transcript-project-directory-for-agent-seat-common.py")
project_directory_module = importlib.util.module_from_spec(_project_directory_specification)
_project_directory_specification.loader.exec_module(project_directory_module)

LOG_DIRECTORY = Path.home() / "nedschorus-logs" / PROGRAM
SESSION_RECORDS_DIRECTORY = Path.home() / ".claude" / "sessions"
PROJECTS_DIRECTORY = Path.home() / ".claude" / "projects"
PROCESS_TABLE_DIRECTORY = Path("/proc")
LOG_DIRECTORY_ENVIRONMENT_VARIABLE = (
    "NEDSCHORUS_HANDOFF_AGENT_SEAT_REMOTE_CONTROL_LOST_AT_CLAUDE_LOGIN_RECONNECT_BY_TMUX_TYPING_WATCHER_LOG_DIRECTORY")
SESSION_RECORDS_DIRECTORY_ENVIRONMENT_VARIABLE = (
    "NEDSCHORUS_HANDOFF_AGENT_SEAT_REMOTE_CONTROL_LOST_AT_CLAUDE_LOGIN_RECONNECT_BY_TMUX_TYPING_WATCHER_SESSION_RECORDS_DIRECTORY")
PROJECTS_DIRECTORY_ENVIRONMENT_VARIABLE = (
    "NEDSCHORUS_HANDOFF_AGENT_SEAT_REMOTE_CONTROL_LOST_AT_CLAUDE_LOGIN_RECONNECT_BY_TMUX_TYPING_WATCHER_PROJECTS_DIRECTORY")
PROCESS_TABLE_DIRECTORY_ENVIRONMENT_VARIABLE = (
    "NEDSCHORUS_HANDOFF_AGENT_SEAT_REMOTE_CONTROL_LOST_AT_CLAUDE_LOGIN_RECONNECT_BY_TMUX_TYPING_WATCHER_PROCESS_TABLE_DIRECTORY")

DISCONNECT_TEXT = ("Remote Control disconnected — signed-in claude.ai account or organization "
                   "changed on this machine")
RECONNECT_SUBTYPE = "bridge_status"
DIALOG_OPEN_STATUS = "waiting"
PROMPT_CHARACTER = "❯"
RULE_CHARACTER = "─"
SUPERVISOR_PROGRAM_NAME = "handoff-supervisor.py"
CLAUDE_PROGRAM_NAME = "claude"
# Claude Code writes the session record only once its startup finishes, seconds after the process starts.
SESSION_RECORD_GRACE_SECONDS = 60
# Typed text and its Enter sent together can arrive as one paste, which the prompt does not submit.
SECONDS_BETWEEN_TEXT_AND_ENTER = 0.5
TMUX_TIMEOUT_SECONDS = 30
# Longer than the opener's own ssh time limit, so the opener reports its timeout itself.
MAC_WINDOW_OPENER_TIMEOUT_SECONDS = 90
PANE_IN_MODE = "1"
TRANSCRIPT_READ_POSITIONS_FILE_NAME = "transcript-read-positions.json"
WHOLE_READ_TYPES_NOTHING_TWICE = ("A whole read types nothing twice, "
                                  "because decisions.jsonl records each disconnect already typed for.")
# Enough to tell a transcript rewritten in place from the one an earlier run read.
BYTES_COMPARED_BEFORE_SAVED_OFFSET = 4096
CRON_LOG = Path.home() / ".claude" / f"{PROGRAM}.log"

SHOW_NOTICE_CLOSE_PROMPT = "Press Enter to close this window."

RUN_FAILED_NOTICE_TEMPLATE = (
    "The Remote Control watcher on ned-box failed and is checking no agent-seat: {problem}\n"
    "Until the watcher is fixed, Remote Control that a Claude login on ned-box turns off stays off. "
    "The watcher sends another notice only if its error changes.\n"
    "To have the watcher fixed, give this notice to an agent on ned-box and ask it to fix the watcher.\n"
    "Record: {record}, and the cron log {cron_log}\n"
)

RECORD_PROBLEM_NOTICE_TEMPLATE = (
    "The Remote Control watcher on ned-box cannot check {seat}: {problem}\n"
    "If a Claude login on ned-box turns Remote Control off in {seat}, the watcher cannot turn it "
    "back on until this problem is fixed. The watcher sends another notice only if the problem changes.\n"
    "If {seat}'s Remote Control is off, turn it on by typing in {seat}'s window:\n"
    "  /remote-control {seat}\n"
    "To have the problem fixed, give this notice to an agent on ned-box and ask it to fix the problem.\n"
    "Record: {record}\n"
)

TYPING_FAILED_NOTICE_TEMPLATE = (
    "Remote Control in {seat} is off, and the Remote Control watcher on ned-box could not turn it "
    "back on: {problem}\n"
    "A Claude login on ned-box turned it off at {disconnected_at}.\n"
    "To turn it on, type in {seat}'s window:\n"
    "  /remote-control {seat}\n"
    "If the watcher keeps failing, give this notice to an agent on ned-box and ask it to find out why.\n"
    "Record: {record}\n"
)


class Run:
    """One run: its log directory, the log entries already written, and whether it met a failure."""

    def __init__(self, log_directory: Path):
        self.log_directory = log_directory
        self.decisions_path = log_directory / "decisions.jsonl"
        try:
            text = self.decisions_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            text = ""
        self.entries = [json.loads(line) for line in text.splitlines() if line.strip()]
        self.failed = False
        self.saved_read_positions = transcript_read_positions_load(log_directory)
        self.transcript_read_positions = {}

    def log(self, seat, decision, **details):
        entry = {"at": datetime.now(timezone.utc).isoformat(), "seat": seat, "decision": decision,
                 **details}
        with self.decisions_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
        self.entries.append(entry)

    def logged(self, **fields) -> bool:
        return any(all(entry.get(key) == value for key, value in fields.items())
                   for entry in self.entries)

    def report(self, seat, kind, template, problem, key, **fields):
        """Log a failure and print it; show the user a notice the first time its key is met."""
        self.failed = True
        print(f"{PROGRAM}: {seat}: {problem}", file=sys.stderr)
        self.log(seat, "failure", kind=kind, problem=problem, key=key)
        if self.logged(decision="user told", key=key):
            return
        if notice_show(self.log_directory, seat, kind, template, problem=problem, **fields):
            self.log(seat, "user told", key=key)


def notice_show(log_directory: Path, seat, kind, template, **fields) -> bool:
    """Write a notice and open it in a window on the user's Mac; print to stderr what failed."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = log_directory / "notices" / f"{stamp}-{seat}-{kind}.txt"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(template.format(seat=seat, record=log_directory / "decisions.jsonl",
                                        **fields), encoding="utf-8")
    except OSError as error:
        print(f"{PROGRAM}: the notice to the user about {seat} was not written ({error}). If the failure "
              "this notice reports happens again, a later run tries the notice again; until then the user "
              "does not know of that failure.", file=sys.stderr)
        return False
    exit_code, output = run_command(
        [sys.executable, str(MAC_WINDOW_OPENER_PROGRAM), *show_notice_words(path)],
        MAC_WINDOW_OPENER_TIMEOUT_SECONDS)
    if exit_code != 0:
        print(f"{PROGRAM}: the notice {path} did not open on the user's Mac (the opener "
              f"{outcome(exit_code)} and said: {output}). If the failure this notice reports happens "
              "again, a later run tries the notice again; until then the user does not know of that "
              "failure.", file=sys.stderr)
        return False
    return True


def run_command(command, timeout_seconds):
    """Return (exit code, output); the exit code is None when the command timed out and was killed."""
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False,
                                   timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        return None, f"it did not finish within {timeout_seconds} seconds"
    return completed.returncode, (completed.stdout + completed.stderr).strip()


def outcome(exit_code):
    return "timed out" if exit_code is None else f"exited {exit_code}"


def show_notice_words(path):
    return [sys.executable, str(Path(__file__).resolve()), "--show-notice", str(path)]


def show_notice(path: str) -> int:
    """What a notice window on the Mac runs: the notice, then Enter closes it."""
    sys.stdout.write(Path(path).read_text(encoding="utf-8"))
    try:
        input(f"\n{SHOW_NOTICE_CLOSE_PROMPT}")
    except EOFError:
        pass
    return 0


def tmux(seat, *arguments):
    """Run one tmux command on the seat's own server; return (exit code, output)."""
    return run_command(["tmux", "-L", seat, *arguments], TMUX_TIMEOUT_SECONDS)


def process_table(process_table_directory: Path):
    """Return {pid: (parent pid, argument words, seconds since start)} for every process still there."""
    clock_ticks_per_second = os.sysconf("SC_CLK_TCK")
    uptime_seconds = float((process_table_directory / "uptime").read_text().split()[0])
    table = {}
    for entry in process_table_directory.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            words = (entry / "cmdline").read_bytes().decode("utf-8", "replace").split("\0")
            # The command name in parentheses may hold spaces; the fields after it do not.
            fields_after_name = (entry / "stat").read_text().rsplit(")", 1)[1].split()
        except (FileNotFoundError, ProcessLookupError):
            # The process ended while the table was read: before its file was opened, or after.
            continue
        started = int(fields_after_name[19]) / clock_ticks_per_second
        table[int(entry.name)] = (int(fields_after_name[1]), [word for word in words if word],
                                  uptime_seconds - started)
    return table


def running_agent_seats(table):
    """Return [(seat, claude pid, seconds since the claude process started)], sorted by seat."""
    supervisors = {}
    for pid, (_, words, _) in table.items():
        if (any(Path(word).name == SUPERVISOR_PROGRAM_NAME for word in words[:2])
                and "--agent" in words[:-1]):
            supervisors[pid] = words[words.index("--agent") + 1]
    seats = []
    for pid, (parent, words, age) in table.items():
        if parent in supervisors and words and Path(words[0]).name == CLAUDE_PROGRAM_NAME:
            seats.append((supervisors[parent], pid, age))
    return sorted(seats)


def latest_unanswered_disconnect(transcript: Path, transcript_read_positions=None):
    """Return the disconnect line after which Remote Control was not turned back on, or None.

    transcript_read_positions maps a transcript's path to where an earlier run stopped reading it and
    what it had found by then; reading resumes there, and the entry is updated. A transcript
    whose bytes just before that place differ from the ones saved, as when it was replaced,
    shrank or was rewritten, is read whole.
    """
    transcript_read_positions = {} if transcript_read_positions is None else transcript_read_positions
    key = str(transcript)
    try:
        stream = transcript.open("rb")
    except FileNotFoundError:
        # Claude Code writes the transcript only from the session's first message on.
        transcript_read_positions.pop(key, None)
        return None
    with stream:
        saved = transcript_read_positions.get(key)
        offset, latest = 0, None
        if isinstance(saved, dict) and isinstance(saved.get("offset"), int) and saved["offset"] > 0:
            stream.seek(saved["offset"] - len(bytes.fromhex(saved.get("bytes_before", ""))))
            if stream.read(saved["offset"] - stream.tell()).hex() == saved.get("bytes_before"):
                offset, latest = saved["offset"], saved.get("latest")
        stream.seek(offset)
        for raw in stream:
            if not raw.endswith(b"\n"):
                # The line Claude Code is still writing; the next run reads it whole.
                break
            offset += len(raw)
            # Most lines are large and unrelated; parse only the ones that can matter.
            if b'"bridge_status"' not in raw and b"Remote Control disconnected" not in raw:
                continue
            entry = json.loads(raw)
            if entry.get("type") != "system":
                continue
            if entry.get("subtype") == RECONNECT_SUBTYPE:
                latest = None
            elif str(entry.get("content", "")).startswith(DISCONNECT_TEXT):
                latest = entry
        stream.seek(max(0, offset - BYTES_COMPARED_BEFORE_SAVED_OFFSET))
        wanted = offset - stream.tell()
        bytes_before = stream.read(wanted)
    if len(bytes_before) == wanted:
        transcript_read_positions[key] = {"offset": offset, "bytes_before": bytes_before.hex(), "latest": latest}
    else:
        # The file shrank after the scan; a short window could never match, so the next run reads whole.
        transcript_read_positions.pop(key, None)
    return latest


def transcript_read_positions_load(log_directory: Path):
    """Return the saved read positions; a missing or unreadable file means reading every transcript whole."""
    path = log_directory / TRANSCRIPT_READ_POSITIONS_FILE_NAME
    try:
        positions = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as error:
        print(f"{PROGRAM}: the saved read positions {path} could not be read ({type(error).__name__}: "
              f"{error}), so this run reads every transcript whole and saves new positions in their place.\n"
              f"Nothing needs doing for this run: {WHOLE_READ_TYPES_NOTHING_TWICE}\n"
              f"When {CRON_LOG} shows this message from two runs in a row: fix the cause the error names, such as "
              "the file's permissions, because until then every run reads every transcript whole.", file=sys.stderr)
        return {}
    if not isinstance(positions, dict):
        print(f"{PROGRAM}: the saved read positions {path} hold valid JSON whose top level is not an "
              "object, so this run reads every transcript whole and saves new positions in their place.\n"
              f"Nothing needs doing for this run: {WHOLE_READ_TYPES_NOTHING_TWICE}", file=sys.stderr)
        return {}
    return positions


def transcript_read_positions_save(log_directory: Path, positions) -> bool:
    """Save the read positions and return True; when that fails, say so and return False."""
    path = log_directory / TRANSCRIPT_READ_POSITIONS_FILE_NAME
    temporary = path.with_name(path.name + ".new")
    try:
        temporary.write_text(json.dumps(positions, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        os.replace(temporary, path)
    except OSError as error:
        print(f"{PROGRAM}: the read positions were not saved to {path} ({error}), so the next run reads "
              "every transcript whole again. Every run still checks every agent-seat, then exits 1 until a save "
              f"succeeds. The one exception is a run that starts while an earlier run still holds {log_directory}/run.lock: "
              "that new run exits 0 without saving.\n"
              f"{WHOLE_READ_TYPES_NOTHING_TWICE}\n"
              f"When the error says No space left on device: free space on the disk that holds {log_directory}.\n"
              f"When the error says Permission denied: give {getpass.getuser()}, the user this watcher runs as, "
              f"write and search (x) permission on {log_directory}, and write permission on {temporary} "
              "where it exists.\n"
              f"When the error says Is a directory: remove the directory at {path} or at {temporary}; "
              "the next run writes the file in its place.\n"
              "Otherwise: fix the cause the error names.", file=sys.stderr)
        return False
    return True


def prompt_line_is_empty(pane_text: str) -> bool:
    """True when the input box shows the prompt character alone between its two rules."""
    lines = pane_text.split("\n")

    def is_rule(index):
        stripped = lines[index].strip() if 0 <= index < len(lines) else ""
        return stripped.startswith(RULE_CHARACTER * 2) and stripped.endswith(RULE_CHARACTER)

    for index in range(len(lines) - 1, -1, -1):
        if lines[index].startswith(PROMPT_CHARACTER) and is_rule(index - 1) and is_rule(index + 1):
            # str.strip removes the no-break space Claude Code puts after the prompt character.
            return lines[index][len(PROMPT_CHARACTER):].strip() == ""
    return False


def check_seat(run: Run, seat, pid, age, session_records_directory: Path, projects_directory: Path):
    record_path = session_records_directory / f"{pid}.json"
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
        session_id, working_directory, status = record["sessionId"], record["cwd"], record["status"]
        tmux_place = record.get("tmux")
    except FileNotFoundError:
        if age < SESSION_RECORD_GRACE_SECONDS:
            return
        run.report(seat, "record-missing", RECORD_PROBLEM_NOTICE_TEMPLATE,
                   f"its claude process {pid} has no session record at {record_path}",
                   key=f"{seat}:{pid}:record-missing")
        return
    except (ValueError, KeyError) as error:
        run.report(seat, "record-unreadable", RECORD_PROBLEM_NOTICE_TEMPLATE,
                   f"its session record {record_path} could not be read as a record with "
                   f"sessionId, cwd and status: {type(error).__name__}: {error}",
                   key=f"{seat}:{pid}:record-unreadable:{type(error).__name__}")
        return
    transcript = (project_directory_module.project_directory_for_seat(
        Path(working_directory), projects_directory) / f"{session_id}.jsonl")
    if str(transcript) in run.saved_read_positions:
        run.transcript_read_positions.setdefault(str(transcript), run.saved_read_positions[str(transcript)])
    disconnect = latest_unanswered_disconnect(transcript, run.transcript_read_positions)
    if disconnect is None:
        return
    event = {"session_id": session_id, "disconnect": disconnect.get("uuid")}
    if run.logged(seat=seat, decision="typed", **event):
        return
    if status == DIALOG_OPEN_STATUS:
        skip(run, seat, event, "a dialog is open: its session record's status is waiting")
        return
    # The record's "tmux" field reads <session>:@<window>.%<pane>; the pane id names this claude's pane.
    pane = str(tmux_place).rpartition(".")[2]
    if not pane.startswith("%"):
        report_typing_failure(run, seat, event, disconnect,
                              f"its session record names no tmux pane: its tmux field is {tmux_place!r}")
        return
    exit_code, mode = tmux(seat, "display-message", "-p", "-t", pane, "#{pane_in_mode}")
    if exit_code != 0:
        report_typing_failure(run, seat, event, disconnect,
                              f"reading the mode of its tmux pane {pane} failed: tmux {outcome(exit_code)}: {mode}")
        return
    if mode == PANE_IN_MODE:
        skip(run, seat, event, f"its tmux pane {pane} is in a mode such as copy mode")
        return
    exit_code, pane_text = tmux(seat, "capture-pane", "-p", "-t", pane)
    if exit_code != 0:
        report_typing_failure(run, seat, event, disconnect,
                              f"reading its tmux pane {pane} failed: tmux {outcome(exit_code)}: {pane_text}")
        return
    if not prompt_line_is_empty(pane_text):
        skip(run, seat, event, "its prompt line is not empty, or no prompt line is shown")
        return
    # Remote Control may have come back on by itself while this run read the pane.
    if latest_unanswered_disconnect(transcript, run.transcript_read_positions) is None:
        return
    for number, arguments in enumerate((("-l", f"/remote-control {seat}"), ("Enter",))):
        if number:
            time.sleep(SECONDS_BETWEEN_TEXT_AND_ENTER)
        exit_code, output = tmux(seat, "send-keys", "-t", pane, *arguments)
        if exit_code != 0:
            report_typing_failure(run, seat, event, disconnect,
                                  f"typing into its tmux pane {pane} failed: tmux {outcome(exit_code)}: {output}")
            return
    run.log(seat, "typed", typed=f"/remote-control {seat}", **event)


def skip(run: Run, seat, event, reason):
    """Log a skip once per disconnect and reason; a later run tries again."""
    if not run.logged(seat=seat, decision="skipped", reason=reason, **event):
        run.log(seat, "skipped", reason=reason, **event)


def report_typing_failure(run: Run, seat, event, disconnect, problem):
    run.report(seat, "typing-failed", TYPING_FAILED_NOTICE_TEMPLATE, problem,
               key=f"{seat}:{event['session_id']}:{event['disconnect']}:typing-failed",
               disconnected_at=disconnect.get("timestamp", "an unknown time"))


def report_run_failure(log_directory: Path, error_text):
    """Show the user a notice the first time this error is met; cron's log keeps every one."""
    reported_path = log_directory / "reported-run-failures.txt"
    try:
        reported = reported_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        reported = []
    if error_text in reported:
        return
    if notice_show(log_directory, "watcher", "run-failed", RUN_FAILED_NOTICE_TEMPLATE,
                   problem=error_text, cron_log=CRON_LOG):
        with reported_path.open("a", encoding="utf-8") as stream:
            stream.write(error_text + "\n")


def run_once(environment) -> int:
    log_directory = Path(environment.get(LOG_DIRECTORY_ENVIRONMENT_VARIABLE) or LOG_DIRECTORY)
    session_records_directory = Path(environment.get(SESSION_RECORDS_DIRECTORY_ENVIRONMENT_VARIABLE)
                                     or SESSION_RECORDS_DIRECTORY)
    projects_directory = Path(environment.get(PROJECTS_DIRECTORY_ENVIRONMENT_VARIABLE)
                              or PROJECTS_DIRECTORY)
    process_table_directory = Path(environment.get(PROCESS_TABLE_DIRECTORY_ENVIRONMENT_VARIABLE)
                                   or PROCESS_TABLE_DIRECTORY)
    log_directory.mkdir(parents=True, exist_ok=True)
    with (log_directory / "run.lock").open("w") as lock_stream:
        try:
            fcntl.flock(lock_stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            # A run still typing owns this minute; two runs could type twice.
            return 0
        try:
            run = Run(log_directory)
            for seat, pid, age in running_agent_seats(process_table(process_table_directory)):
                check_seat(run, seat, pid, age, session_records_directory, projects_directory)
            if not transcript_read_positions_save(log_directory, run.transcript_read_positions):
                run.failed = True
        except Exception as error:  # noqa: BLE001 - a failed run must reach the user, not only cron's log
            report_run_failure(log_directory, f"{type(error).__name__}: {error}")
            raise
        return 1 if run.failed else 0


def main(argv=None, environment=None) -> int:
    parser = argparse.ArgumentParser(prog=PROGRAM, description=__doc__.splitlines()[0])
    parser.add_argument("--show-notice", metavar="FILE")
    arguments = parser.parse_args(argv)
    if arguments.show_notice:
        return show_notice(arguments.show_notice)
    if sys.platform != "linux":
        print(f"{PROGRAM}: refused: this machine is not ned-box (it is not Linux), and this program "
              "watches only ned-box's agent-seats.", file=sys.stderr)
        return 2
    return run_once(dict(os.environ) if environment is None else environment)


if __name__ == "__main__":
    sys.exit(main())
