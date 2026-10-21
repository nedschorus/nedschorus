#!/usr/bin/env python3
"""Tests for handoff-agent-seat-remote-control-lost-at-claude-login-reconnect-by-tmux-typing-watcher.py.

Run: python3 nc-systems/handoff/tests/handoff-agent-seat-remote-control-lost-at-claude-login-reconnect-by-tmux-typing-watcher-test.py

No case types into a real agent-seat or opens a window on the Mac. Each case
builds a fixture: a process table directory holding one stand-in supervisor
and its claude, a session record, a transcript, and a detached tmux session,
named for this run, on a tmux server in a private TMUX_TMPDIR, whose pane
paints a Claude Code input box and then echoes what is typed. The Mac window
opener runs for real, with NEDSCHORUS_SSH_PROGRAM pointing at a stand-in ssh
that records each request.

Prints one line per case and exits non-zero if any case fails.
"""

import fcntl
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import redirect_stderr
from pathlib import Path

SYSTEM_DIRECTORY = Path(__file__).resolve().parent.parent
SCRIPT_PATH = (SYSTEM_DIRECTORY
               / "handoff-agent-seat-remote-control-lost-at-claude-login-reconnect-by-tmux-typing-watcher.py")
_spec = importlib.util.spec_from_file_location(
    "handoff_agent_seat_remote_control_lost_at_claude_login_reconnect_by_tmux_typing_watcher", SCRIPT_PATH)
watcher = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(watcher)

failures = []

SUPERVISOR_PID = 4100
CLAUDE_PID = 4200
UPTIME_SECONDS = 100000.0
SESSION_ID = "0d0e0f10-1111-4222-8333-944455556666"
DISCONNECT_UUID = "d15c0aaa-0000-4000-8000-000000000001"
RULE = "─" * 60
EMPTY_BOX = [RULE + " seat ─", watcher.PROMPT_CHARACTER + "\xa0", RULE]


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def isolate_tmux() -> Path:
    """Every tmux call of this run, the program's included, goes to servers under a private TMUX_TMPDIR."""
    namespace = Path(tempfile.mkdtemp(prefix="rcw-tmux-", dir="/tmp" if os.path.isdir("/tmp") else None))
    os.environ["TMUX_TMPDIR"] = str(namespace)
    os.environ.pop("TMUX", None)
    os.environ.pop("TMUX_PANE", None)
    (namespace / "empty.conf").write_text("", encoding="utf-8")
    return namespace


def end_tmux(namespace: Path):
    socket_directory = namespace / f"tmux-{os.getuid()}"
    if socket_directory.is_dir():
        for socket in socket_directory.iterdir():
            subprocess.run(["tmux", "-S", str(socket), "kill-server"], capture_output=True, check=False)
    shutil.rmtree(namespace, ignore_errors=True)


def disconnect_line(uuid=DISCONNECT_UUID):
    return {"type": "system", "subtype": "informational", "level": "warning", "uuid": uuid,
            "timestamp": "2026-10-21T01:06:08.879Z",
            "content": watcher.DISCONNECT_TEXT + " — run /remote-control to start a session for the "
                       "current account, or /login to switch back, then /remote-control"}


def reconnect_line():
    return {"type": "system", "subtype": "bridge_status", "uuid": "b0000000-0000-4000-8000-000000000002",
            "content": "/remote-control is active · Continue here, on your phone, or at "
                       "https://claude.ai/code/session_01Example"}


def stat_text(pid, parent, age_seconds):
    started_ticks = int((UPTIME_SECONDS - age_seconds) * os.sysconf("SC_CLK_TCK"))
    return f"{pid} (name with spaces) S {parent} " + " ".join(["0"] * 17) + f" {started_ticks} 0 0\n"


class Fixture:
    def __init__(self, case, namespace: Path):
        self.root = Path(tempfile.mkdtemp(prefix="rcw-case-"))
        self.seat = f"rcw-{os.getpid()}-{case}"
        self.namespace = namespace
        self.processes = self.root / "proc"
        self.records = self.root / "sessions"
        self.projects = self.root / "projects"
        self.logs = self.root / "logs"
        self.seat_directory = self.root / "agents" / self.seat
        for directory in (self.processes, self.records, self.projects, self.seat_directory):
            directory.mkdir(parents=True)
        (self.processes / "uptime").write_text(f"{UPTIME_SECONDS} 0\n", encoding="utf-8")
        self.ssh_log = self.root / "ssh-requests.txt"
        self.ssh_exit = self.root / "ssh-exit-code.txt"
        stub = self.root / "ssh-stand-in"
        stub.write_text("#!/bin/sh\n"
                        f"printf '%s\\n' \"$*\" >> '{self.ssh_log}'\n"
                        f"if [ -f '{self.ssh_exit}' ]; then exit \"$(cat '{self.ssh_exit}')\"; fi\n"
                        "exit 0\n", encoding="utf-8")
        stub.chmod(0o755)
        os.environ["NEDSCHORUS_SSH_PROGRAM"] = str(stub)
        os.environ["NEDSCHORUS_MAC_SSH_DESTINATION"] = "mac-stand-in.invalid"
        self.environment = {
            watcher.LOG_DIRECTORY_ENVIRONMENT_VARIABLE: str(self.logs),
            watcher.SESSION_RECORDS_DIRECTORY_ENVIRONMENT_VARIABLE: str(self.records),
            watcher.PROJECTS_DIRECTORY_ENVIRONMENT_VARIABLE: str(self.projects),
            watcher.PROCESS_TABLE_DIRECTORY_ENVIRONMENT_VARIABLE: str(self.processes),
        }

    def add_process(self, pid, parent, words, age_seconds=1000.0):
        directory = self.processes / str(pid)
        directory.mkdir()
        (directory / "cmdline").write_bytes(b"\0".join(word.encode() for word in words) + b"\0")
        (directory / "stat").write_text(stat_text(pid, parent, age_seconds), encoding="utf-8")

    def add_seat_processes(self, claude_age_seconds=1000.0):
        self.add_process(SUPERVISOR_PID, 1, ["python3", "/x/nc-systems/handoff/handoff-supervisor.py",
                                             "--agent", self.seat, "--cd", str(self.seat_directory)])
        self.add_process(CLAUDE_PID, SUPERVISOR_PID, ["claude", "--session-id", SESSION_ID],
                         claude_age_seconds)

    def write_record(self, status="idle", text=None):
        record = {"pid": CLAUDE_PID, "sessionId": SESSION_ID, "cwd": str(self.seat_directory),
                  "status": status, "tmux": f"{self.seat}:@0.%0"}
        (self.records / f"{CLAUDE_PID}.json").write_text(
            json.dumps(record) if text is None else text, encoding="utf-8")

    @property
    def transcript(self) -> Path:
        return (watcher.project_directory_module.project_directory_for_seat(self.seat_directory, self.projects)
                / f"{SESSION_ID}.jsonl")

    def write_transcript(self, *entries, tail=""):
        self.transcript.parent.mkdir(parents=True, exist_ok=True)
        # Lines that only quote the disconnect text, after the real ones, must not count as one.
        unrelated = {"type": "assistant", "message": {"content": "work"}}
        quoted = [{"type": kind, "content": watcher.DISCONNECT_TEXT + ", quoted"}
                  for kind in ("user", "assistant")]
        lines = [json.dumps(unrelated)]
        lines += [json.dumps(entry, ensure_ascii=False) for entry in (*entries, *quoted)]
        self.transcript.write_text("\n".join(lines) + "\n" + tail, encoding="utf-8")

    def append_transcript(self, entry):
        with self.transcript.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def start_pane(self, box_lines=EMPTY_BOX):
        painter = self.root / "paint.txt"
        painter.write_text("conversation above\n" + "\n".join(box_lines) + "\n  status line\n",
                           encoding="utf-8")
        subprocess.run(["tmux", "-f", str(self.namespace / "empty.conf"), "-L", self.seat, "new-session",
                        "-d", "-s", self.seat, "-x", "100", "-y", "30",
                        f"cat '{painter}'; stty -echo; exec cat"], check=True, capture_output=True)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if "status line" in self.pane():
                return
            time.sleep(0.05)
        raise RuntimeError(f"the fixture pane of {self.seat} never painted")

    def pane(self) -> str:
        return subprocess.run(["tmux", "-L", self.seat, "capture-pane", "-p", "-t", f"={self.seat}:"],
                              capture_output=True, text=True, check=False).stdout

    def typed(self) -> str:
        """What the pane's cat echoed back: each line typed and submitted with Enter."""
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            text = self.pane()
            if "/remote-control" in text:
                return text
            time.sleep(0.05)
        return self.pane()

    def kill_server(self):
        subprocess.run(["tmux", "-L", self.seat, "kill-server"], capture_output=True, check=False)

    def run(self):
        errors = io.StringIO()
        with redirect_stderr(errors):
            exit_code = watcher.main([], self.environment)
        return exit_code, errors.getvalue()

    def entries(self):
        path = self.logs / "decisions.jsonl"
        if not path.is_file():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def decisions(self):
        return [entry["decision"] for entry in self.entries()]

    def ssh_requests(self):
        return self.ssh_log.read_text(encoding="utf-8").splitlines() if self.ssh_log.is_file() else []

    def notices(self):
        directory = self.logs / "notices"
        return sorted(directory.iterdir()) if directory.is_dir() else []

    def close(self):
        self.kill_server()
        shutil.rmtree(self.root, ignore_errors=True)


def lost_seat(case, namespace, status="idle", box_lines=EMPTY_BOX, pane=True):
    fixture = Fixture(case, namespace)
    fixture.add_seat_processes()
    fixture.write_record(status=status)
    fixture.write_transcript(reconnect_line(), disconnect_line())
    if pane:
        fixture.start_pane(box_lines)
    return fixture


def case_prompt_line_reading():
    empty = "\n".join(["text", *EMPTY_BOX, "  status"])
    check("an input box holding only the prompt character and its no-break space reads as empty",
          watcher.prompt_line_is_empty(empty))
    draft = "\n".join(["text", EMPTY_BOX[0], "❯\xa0yes, merge it", RULE, "  status"])
    check("an input box holding a draft reads as not empty", not watcher.prompt_line_is_empty(draft))
    two_lines = "\n".join(["text", EMPTY_BOX[0], "❯\xa0", "  second line of a draft", RULE])
    check("a draft whose first line is empty but runs on to a second line reads as not empty",
          not watcher.prompt_line_is_empty(two_lines))
    dialog = "\n".join(["Remote Control", "   ❯ Continue", "   Enter to select · Esc to continue"])
    check("a menu's pointer outside an input box is no empty prompt line",
          not watcher.prompt_line_is_empty(dialog))
    history = "\n".join(["❯ an earlier prompt", "", *EMPTY_BOX[:1], "❯\xa0draft", RULE])
    check("the bottom input box decides, not an earlier prompt in the conversation",
          not watcher.prompt_line_is_empty(history))
    check("a pane with no input box reads as not empty", not watcher.prompt_line_is_empty("just output\n"))
    check("an input box at the very top of the pane is read",
          watcher.prompt_line_is_empty("\n".join([*EMPTY_BOX, "  status"])))
    check("a prompt line on the pane's last line, with no rule below it, is no input box",
          not watcher.prompt_line_is_empty("\n".join(["text", RULE, "❯\xa0"])))
    check("a prompt line with no rule above it is no input box",
          not watcher.prompt_line_is_empty("\n".join(["text", "❯\xa0", RULE])))
    check("a line of one rule character is no rule",
          not watcher.prompt_line_is_empty("\n".join(["─", "❯\xa0", "─"])))


def case_seat_finding(namespace):
    fixture = Fixture("finding", namespace)
    try:
        fixture.add_seat_processes(claude_age_seconds=42.0)
        fixture.add_process(4300, 1, ["claude", "--session-id", "not-a-seat"])
        fixture.add_process(4400, SUPERVISOR_PID, ["python3", "some-helper.py"])
        fixture.add_process(4500, 1, ["python3", "handoff-supervisor.py", "--agent"])
        fixture.add_process(4600, 1, ["python3", "/x/other-program.py", "--agent", "not-a-seat"])
        fixture.add_process(4601, 4600, ["claude"])
        fixture.add_process(4700, 1, ["python3", "-u", "/x/handoff-supervisor.py", "--agent", "too-deep"])
        fixture.add_process(4701, 4700, ["claude"])
        fixture.add_process(4800, SUPERVISOR_PID, ["/usr/bin/claudette"])
        # A process that ended while the table was read leaves a directory without its files.
        (fixture.processes / "4900").mkdir()
        (fixture.processes / "self").mkdir()
        (fixture.processes / "0self").mkdir()
        seats = watcher.running_agent_seats(watcher.process_table(fixture.processes))
        check("a claude whose parent is handoff-supervisor.py --agent <seat> is that seat's; "
              "a claude of no supervisor and a supervisor's other children are not",
              [(seat, pid) for seat, pid, _ in seats] == [(fixture.seat, CLAUDE_PID)], seats)
        check("a process's age is read from its start time and the uptime",
              abs(seats[0][2] - 42.0) < 1.0, seats)
    finally:
        fixture.close()


def case_types_on_disconnect(namespace):
    fixture = lost_seat("types", namespace)
    try:
        exit_code, errors = fixture.run()
        pane = fixture.typed()
        check("a disconnect line with an empty prompt: types /remote-control <seat> and Enter, exits 0",
              exit_code == 0 and f"/remote-control {fixture.seat}\n" in pane + "\n"
              and fixture.decisions() == ["typed"], (exit_code, errors, pane, fixture.entries()))
        typed_entry = fixture.entries()[0]
        check("the typing is logged with the session and the disconnect line it answers",
              typed_entry["session_id"] == SESSION_ID and typed_entry["disconnect"] == DISCONNECT_UUID
              and typed_entry["seat"] == fixture.seat, typed_entry)
        exit_code, errors = fixture.run()
        time.sleep(1)
        check("a later run, the disconnect line still the latest, does not type again for it",
              exit_code == 0 and fixture.pane().count("/remote-control") == 1
              and fixture.decisions() == ["typed"], (exit_code, errors, fixture.pane(), fixture.entries()))
        fixture.append_transcript(disconnect_line("d15c0aaa-0000-4000-8000-000000000003"))
        exit_code, errors = fixture.run()
        check("a new disconnect line in the same session is typed for again",
              exit_code == 0 and fixture.decisions() == ["typed", "typed"], (exit_code, errors, fixture.entries()))
    finally:
        fixture.close()


def case_reconnected(namespace):
    fixture = Fixture("reconnected", namespace)
    try:
        fixture.add_seat_processes()
        fixture.write_record()
        fixture.write_transcript(disconnect_line(), reconnect_line())
        fixture.start_pane()
        exit_code, errors = fixture.run()
        time.sleep(1)
        check("a reconnection logged after the disconnect: nothing typed, nothing logged",
              exit_code == 0 and "/remote-control" not in fixture.pane() and fixture.decisions() == [],
              (exit_code, errors, fixture.pane(), fixture.entries()))
    finally:
        fixture.close()


def case_no_disconnect(namespace):
    fixture = Fixture("no-disconnect", namespace)
    try:
        fixture.add_seat_processes()
        fixture.write_record()
        fixture.write_transcript(reconnect_line())
        fixture.start_pane()
        exit_code, errors = fixture.run()
        time.sleep(1)
        check("no disconnect line: nothing typed, nothing logged",
              exit_code == 0 and "/remote-control" not in fixture.pane() and fixture.decisions() == [],
              (exit_code, errors, fixture.entries()))
    finally:
        fixture.close()


def case_no_transcript_yet(namespace):
    fixture = Fixture("no-transcript", namespace)
    try:
        fixture.add_seat_processes()
        fixture.write_record()
        fixture.start_pane()
        exit_code, errors = fixture.run()
        check("a session with no transcript yet: nothing typed, nothing logged",
              exit_code == 0 and fixture.decisions() == [], (exit_code, errors, fixture.entries()))
    finally:
        fixture.close()


def case_partial_last_line(namespace):
    fixture = Fixture("partial-line", namespace)
    try:
        fixture.add_seat_processes()
        fixture.write_record()
        fixture.write_transcript(disconnect_line(), tail='{"type":"system","subtype":"bridge_status","con')
        fixture.start_pane()
        exit_code, errors = fixture.run()
        check("a last line still being written is left for the next run; the whole lines before it decide",
              exit_code == 0 and fixture.decisions() == ["typed"], (exit_code, errors, fixture.entries()))
    finally:
        fixture.close()


def case_draft(namespace):
    box = [EMPTY_BOX[0], "❯\xa0yes, merge it", RULE]
    fixture = lost_seat("draft", namespace, box_lines=box)
    try:
        exit_code, errors = fixture.run()
        exit_code_again, _ = fixture.run()
        time.sleep(1)
        check("a draft at the prompt: nothing typed, the skip logged once over two runs, exit 0",
              exit_code == 0 and exit_code_again == 0 and "/remote-control" not in fixture.pane()
              and fixture.decisions() == ["skipped"], (exit_code, errors, fixture.entries()))
    finally:
        fixture.close()


def case_dialog_open(namespace):
    fixture = lost_seat("dialog", namespace, status=watcher.DIALOG_OPEN_STATUS)
    try:
        exit_code, errors = fixture.run()
        time.sleep(1)
        check("a dialog open (status waiting): nothing typed, the skip logged, exit 0",
              exit_code == 0 and "/remote-control" not in fixture.pane()
              and fixture.decisions() == ["skipped"]
              and "waiting" in fixture.entries()[0]["reason"], (exit_code, errors, fixture.entries()))
        fixture.write_record(status="idle")
        exit_code, errors = fixture.run()
        check("once the dialog closes, a later run types",
              exit_code == 0 and fixture.decisions() == ["skipped", "typed"], (exit_code, errors, fixture.entries()))
    finally:
        fixture.close()


def case_record_missing(namespace):
    fixture = Fixture("record-missing", namespace)
    try:
        fixture.add_seat_processes(claude_age_seconds=10.0)
        exit_code, errors = fixture.run()
        check("a claude seconds old with no session record yet: nothing reported, exit 0",
              exit_code == 0 and fixture.decisions() == [] and fixture.ssh_requests() == [],
              (exit_code, errors, fixture.entries()))
    finally:
        fixture.close()
    fixture = Fixture("record-missing-old", namespace)
    try:
        fixture.add_seat_processes()
        fixture.start_pane()
        exit_code, errors = fixture.run()
        notices = fixture.notices()
        check("a claude past its startup with no session record: reported on stderr, in a notice "
              "opened on the Mac, and by exit 1; nothing typed",
              exit_code == 1 and str(CLAUDE_PID) in errors and fixture.decisions() == ["failure", "user told"]
              and len(notices) == 1 and len(fixture.ssh_requests()) == 1
              and f"--show-notice {notices[0]}" in fixture.ssh_requests()[0]
              and "/remote-control" not in fixture.pane(), (exit_code, errors, fixture.entries(), fixture.ssh_requests()))
        check("the notice names the seat and the command that turns Remote Control on by hand",
              f"/remote-control {fixture.seat}" in notices[0].read_text(encoding="utf-8"))
        exit_code, errors = fixture.run()
        check("the same failure on a later run: on stderr and exit 1 again, but no second notice",
              exit_code == 1 and str(CLAUDE_PID) in errors and len(fixture.notices()) == 1
              and len(fixture.ssh_requests()) == 1, (exit_code, errors, fixture.ssh_requests()))
    finally:
        fixture.close()


def case_record_unreadable(namespace):
    for name, text in (("bad-json", "{not json"), ("no-status", json.dumps({"sessionId": SESSION_ID, "cwd": "/x"}))):
        fixture = Fixture(f"record-{name}", namespace)
        try:
            fixture.add_seat_processes()
            fixture.write_record(text=text)
            exit_code, errors = fixture.run()
            check(f"a session record that cannot be read ({name}): reported, exit 1, nothing typed",
                  exit_code == 1 and "could not be read" in errors
                  and fixture.decisions() == ["failure", "user told"] and len(fixture.notices()) == 1,
                  (exit_code, errors, fixture.entries()))
        finally:
            fixture.close()


def case_tmux_server_gone(namespace):
    fixture = lost_seat("server-gone", namespace, pane=False)
    try:
        exit_code, errors = fixture.run()
        check("the seat's tmux server gone: the failed pane read reported with tmux's words, a notice "
              "opened, exit 1",
              exit_code == 1 and "reading the mode of its tmux pane %0 failed" in errors
              and fixture.decisions() == ["failure", "user told"] and len(fixture.ssh_requests()) == 1,
              (exit_code, errors, fixture.entries()))
    finally:
        fixture.close()


def case_capture_pane_failing(namespace):
    fixture = lost_seat("capture-fails", namespace)
    real_tmux = watcher.tmux

    def tmux_whose_server_dies_before_the_pane_is_read(seat, *arguments):
        if arguments[0] == "capture-pane":
            fixture.kill_server()
        return real_tmux(seat, *arguments)

    watcher.tmux = tmux_whose_server_dies_before_the_pane_is_read
    try:
        exit_code, errors = fixture.run()
        check("capture-pane failing: reported with tmux's words, a notice opened, exit 1",
              exit_code == 1 and "reading its tmux pane %0 failed: tmux exited" in errors
              and fixture.decisions() == ["failure", "user told"], (exit_code, errors, fixture.entries()))
    finally:
        watcher.tmux = real_tmux
        fixture.close()


def case_send_keys_failing(namespace):
    fixture = lost_seat("send-keys", namespace)
    real_tmux = watcher.tmux

    def tmux_whose_server_dies_before_typing(seat, *arguments):
        if arguments[0] == "send-keys":
            fixture.kill_server()
        return real_tmux(seat, *arguments)

    watcher.tmux = tmux_whose_server_dies_before_typing
    try:
        exit_code, errors = fixture.run()
        notices = fixture.notices()
        check("send-keys failing: reported on stderr, in a notice opened on the Mac, and by exit 1; "
              "the typing is not logged as done",
              exit_code == 1 and "typing into its tmux pane %0 failed" in errors
              and fixture.decisions() == ["failure", "user told"] and len(notices) == 1
              and "2026-10-21T01:06:08.879Z" in notices[0].read_text(encoding="utf-8"),
              (exit_code, errors, fixture.entries()))
    finally:
        watcher.tmux = real_tmux
        fixture.close()


def case_reconnected_while_reading_the_pane(namespace):
    fixture = lost_seat("reconnected-meanwhile", namespace)
    real_tmux = watcher.tmux

    def tmux_during_which_remote_control_comes_back(seat, *arguments):
        if arguments[0] == "capture-pane":
            fixture.append_transcript(reconnect_line())
        return real_tmux(seat, *arguments)

    watcher.tmux = tmux_during_which_remote_control_comes_back
    try:
        exit_code, errors = fixture.run()
        time.sleep(1)
        check("Remote Control back on by itself while the pane was read: nothing typed",
              exit_code == 0 and "/remote-control" not in fixture.pane() and fixture.decisions() == [],
              (exit_code, errors, fixture.entries()))
    finally:
        watcher.tmux = real_tmux
        fixture.close()


def case_copy_mode(namespace):
    fixture = lost_seat("copy-mode", namespace)
    try:
        subprocess.run(["tmux", "-L", fixture.seat, "copy-mode", "-t", "%0"], check=True, capture_output=True)
        exit_code, errors = fixture.run()
        time.sleep(1)
        subprocess.run(["tmux", "-L", fixture.seat, "send-keys", "-t", "%0", "-X", "cancel"],
                       check=True, capture_output=True)
        check("a pane in tmux copy mode: nothing typed, the skip logged, exit 0",
              exit_code == 0 and "/remote-control" not in fixture.pane() and fixture.decisions() == ["skipped"]
              and "copy mode" in fixture.entries()[0]["reason"], (exit_code, errors, fixture.entries()))
        exit_code, errors = fixture.run()
        check("once copy mode ends, a later run types",
              exit_code == 0 and fixture.decisions() == ["skipped", "typed"]
              and f"/remote-control {fixture.seat}" in fixture.typed(), (exit_code, errors, fixture.entries()))
    finally:
        fixture.close()


def case_types_into_the_recorded_pane(namespace):
    fixture = lost_seat("recorded-pane", namespace)
    try:
        painter = fixture.root / "paint.txt"
        # A second window, made active, whose pane also shows an empty input box.
        subprocess.run(["tmux", "-L", fixture.seat, "new-window", "-t", f"={fixture.seat}:",
                        f"cat '{painter}'; stty -echo; exec cat"], check=True, capture_output=True)
        exit_code, errors = fixture.run()
        time.sleep(1)
        recorded, active = (subprocess.run(["tmux", "-L", fixture.seat, "capture-pane", "-p", "-t", target],
                                           capture_output=True, text=True, check=False).stdout
                            for target in ("%0", f"={fixture.seat}:"))
        check("the command is typed into the pane the session record names, not the active pane",
              exit_code == 0 and f"/remote-control {fixture.seat}" in recorded
              and "/remote-control" not in active, (exit_code, errors, recorded, active))
    finally:
        fixture.close()


def open_active_window_with_empty_box(fixture):
    """A second window, made active, whose pane shows an empty input box and is in no mode."""
    painter = fixture.root / "active-paint.txt"
    painter.write_text("other window\n" + "\n".join(EMPTY_BOX) + "\n  status line\n", encoding="utf-8")
    subprocess.run(["tmux", "-L", fixture.seat, "new-window", "-t", f"={fixture.seat}:",
                    f"cat '{painter}'; stty -echo; exec cat"], check=True, capture_output=True)
    time.sleep(0.5)


def case_recorded_pane_decides_mode_and_prompt(namespace):
    fixture = lost_seat("recorded-pane-mode", namespace)
    try:
        subprocess.run(["tmux", "-L", fixture.seat, "copy-mode", "-t", "%0"], check=True, capture_output=True)
        open_active_window_with_empty_box(fixture)
        exit_code, errors = fixture.run()
        check("the recorded pane in copy mode while the active pane is not: nothing typed, the skip logged",
              exit_code == 0 and fixture.decisions() == ["skipped"]
              and "copy mode" in fixture.entries()[0]["reason"], (exit_code, errors, fixture.entries()))
    finally:
        fixture.close()
    fixture = lost_seat("recorded-pane-draft", namespace, box_lines=[EMPTY_BOX[0], "❯\xa0yes, merge it", RULE])
    try:
        open_active_window_with_empty_box(fixture)
        exit_code, errors = fixture.run()
        check("a draft in the recorded pane while the active pane's prompt is empty: nothing typed, "
              "the skip logged",
              exit_code == 0 and fixture.decisions() == ["skipped"]
              and "not empty" in fixture.entries()[0]["reason"], (exit_code, errors, fixture.entries()))
    finally:
        fixture.close()


def case_record_names_no_pane(namespace):
    fixture = lost_seat("no-pane", namespace)
    try:
        record = json.loads((fixture.records / f"{CLAUDE_PID}.json").read_text(encoding="utf-8"))
        del record["tmux"]
        fixture.write_record(text=json.dumps(record))
        exit_code, errors = fixture.run()
        time.sleep(1)
        check("a session record that names no tmux pane: reported as a typing failure, exit 1, nothing typed",
              exit_code == 1 and "names no tmux pane" in errors and "/remote-control" not in fixture.pane()
              and fixture.decisions() == ["failure", "user told"], (exit_code, errors, fixture.entries()))
    finally:
        fixture.close()


def case_tmux_timing_out(namespace):
    fixture = lost_seat("tmux-timeout", namespace)
    real_tmux = watcher.tmux

    def tmux_that_hangs(seat, *arguments):
        return watcher.run_command(["sleep", "5"], 0.2)

    watcher.tmux = tmux_that_hangs
    try:
        exit_code, errors = fixture.run()
        check("a tmux command that times out: reported as that seat's typing failure, the run not "
              "stopped, exit 1",
              exit_code == 1 and "timed out" in errors and "within 0.2 seconds" in errors
              and fixture.decisions() == ["failure", "user told"], (exit_code, errors, fixture.entries()))
    finally:
        watcher.tmux = real_tmux
        fixture.close()


def case_process_ending_mid_read(namespace):
    fixture = Fixture("ended-mid-read", namespace)
    real_read_bytes = Path.read_bytes
    ended = fixture.processes / "4900" / "cmdline"

    def read_bytes_of_a_process_that_ends(path):
        if path == ended:
            raise ProcessLookupError(3, "No such process")
        return real_read_bytes(path)

    try:
        fixture.add_seat_processes()
        fixture.add_process(4900, 1, ["sleep", "1"])
        Path.read_bytes = read_bytes_of_a_process_that_ends
        seats = watcher.running_agent_seats(watcher.process_table(fixture.processes))
        check("a process that ends after its file is opened is skipped, and the scan goes on",
              [(seat, pid) for seat, pid, _ in seats] == [(fixture.seat, CLAUDE_PID)], seats)
    finally:
        Path.read_bytes = real_read_bytes
        fixture.close()


def case_notice_failing(namespace):
    fixture = lost_seat("notice-unwritable", namespace, pane=False)
    try:
        fixture.logs.mkdir()
        (fixture.logs / "notices").write_text("a file where the notices directory goes", encoding="utf-8")
        exit_code, errors = fixture.run()
        check("a notice that cannot be written: said on stderr, exit 1, not logged as told",
              exit_code == 1 and "was not written (" in errors and "so the user has not been told" in errors
              and "need not tell the user" in errors
              and fixture.decisions() == ["failure"] and fixture.ssh_requests() == [],
              (exit_code, errors, fixture.entries()))
    finally:
        fixture.close()
    fixture = lost_seat("notice-unopened", namespace, pane=False)
    try:
        fixture.ssh_exit.write_text("255", encoding="utf-8")
        exit_code, errors = fixture.run()
        check("a notice the Mac window opener cannot open: said on stderr with the opener's exit code, "
              "exit 1, not logged as told",
              exit_code == 1 and "did not open on the user's Mac (the opener exited 1" in errors
              and "need not tell the user" in errors
              and fixture.decisions() == ["failure"], (exit_code, errors, fixture.entries()))
        fixture.ssh_exit.unlink()
        exit_code, errors = fixture.run()
        check("a notice not shown is tried again on the next run",
              exit_code == 1 and fixture.decisions() == ["failure", "failure", "user told"]
              and len(fixture.ssh_requests()) == 2, (exit_code, errors, fixture.entries()))
    finally:
        fixture.close()


def case_run_failure(namespace):
    fixture = Fixture("run-failure", namespace)
    try:
        fixture.add_seat_processes()
        fixture.logs.mkdir()
        (fixture.logs / "decisions.jsonl").write_text("{broken\n", encoding="utf-8")
        raised = []
        for _ in range(2):
            try:
                fixture.run()
            except ValueError as error:
                raised.append(error)
        notices = fixture.notices()
        check("a run that fails: the error raised, so cron's log keeps it and the exit is nonzero, and "
              "one notice for the same error over two runs",
              len(raised) == 2 and len(notices) == 1 and len(fixture.ssh_requests()) == 1
              and "JSONDecodeError" in notices[0].read_text(encoding="utf-8"),
              (raised, notices, fixture.ssh_requests()))
    finally:
        fixture.close()


def case_run_failure_notice_not_shown(namespace):
    fixture = Fixture("run-failure-unshown", namespace)
    try:
        fixture.add_seat_processes()
        fixture.logs.mkdir()
        (fixture.logs / "decisions.jsonl").write_text("{broken\n", encoding="utf-8")
        fixture.ssh_exit.write_text("255", encoding="utf-8")
        errors = io.StringIO()
        with redirect_stderr(errors):
            try:
                watcher.main([], fixture.environment)
            except ValueError:
                pass
        check("a run failure whose notice the Mac does not open: said on stderr, and not marked as told",
              "did not open on the user's Mac" in errors.getvalue()
              and not (fixture.logs / "reported-run-failures.txt").exists(), errors.getvalue())
    finally:
        fixture.close()


def case_overlapping_run(namespace):
    fixture = lost_seat("overlap", namespace)
    try:
        fixture.logs.mkdir()
        with (fixture.logs / "run.lock").open("w") as holder:
            fcntl.flock(holder, fcntl.LOCK_EX)
            exit_code, errors = fixture.run()
        time.sleep(1)
        check("a run that starts while another holds the lock does nothing and exits 0",
              exit_code == 0 and fixture.decisions() == [] and "/remote-control" not in fixture.pane(),
              (exit_code, errors, fixture.entries()))
    finally:
        fixture.close()


def case_off_ned_box_and_show_notice():
    real_platform = watcher.sys.platform
    watcher.sys.platform = "darwin"
    errors = io.StringIO()
    try:
        with redirect_stderr(errors):
            exit_code = watcher.main([], {})
    finally:
        watcher.sys.platform = real_platform
    check("off ned-box the program refuses with exit 2", exit_code == 2 and "refused" in errors.getvalue(),
          errors.getvalue())
    directory = Path(tempfile.mkdtemp(prefix="rcw-show-"))
    try:
        notice = directory / "notice.txt"
        notice.write_text("the notice text\n", encoding="utf-8")
        shown = subprocess.run([sys.executable, str(SCRIPT_PATH), "--show-notice", str(notice)],
                               capture_output=True, text=True, stdin=subprocess.DEVNULL, check=False)
        check("--show-notice prints the notice, then the line that says how to close the window",
              shown.returncode == 0 and shown.stdout.startswith("the notice text\n")
              and watcher.SHOW_NOTICE_CLOSE_PROMPT in shown.stdout, (shown.returncode, shown.stdout, shown.stderr))
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def main():
    if shutil.which("tmux") is None:
        print("FAIL  tmux is not installed, and every typing case needs it")
        return 1
    namespace = isolate_tmux()
    try:
        case_prompt_line_reading()
        case_seat_finding(namespace)
        case_types_on_disconnect(namespace)
        case_reconnected(namespace)
        case_no_disconnect(namespace)
        case_no_transcript_yet(namespace)
        case_partial_last_line(namespace)
        case_draft(namespace)
        case_dialog_open(namespace)
        case_record_missing(namespace)
        case_record_unreadable(namespace)
        case_tmux_server_gone(namespace)
        case_capture_pane_failing(namespace)
        case_send_keys_failing(namespace)
        case_reconnected_while_reading_the_pane(namespace)
        case_copy_mode(namespace)
        case_types_into_the_recorded_pane(namespace)
        case_recorded_pane_decides_mode_and_prompt(namespace)
        case_record_names_no_pane(namespace)
        case_tmux_timing_out(namespace)
        case_process_ending_mid_read(namespace)
        case_notice_failing(namespace)
        case_run_failure(namespace)
        case_run_failure_notice_not_shown(namespace)
        case_overlapping_run(namespace)
        case_off_ned_box_and_show_notice()
    finally:
        end_tmux(namespace)
    if failures:
        print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
