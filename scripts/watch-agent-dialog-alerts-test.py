#!/usr/bin/env python3
"""Tests for watch-agent-dialog-alerts.py.

Run: python3 scripts/watch-agent-dialog-alerts-test.py
Prints one line per case and exits non-zero if any case fails.

No case reaches ned-box, and no case runs the real watch-agent-dialogs.py.
The subprocess cases point --local-dialog-script-path at a fake dialog
stream driven by a plan file — one entry per attempt, each saying what to
print on stdout, what to print on stderr, how long to stay up and what to
exit with — and the remote cases put a fake `ssh` first on the wrapper's
PATH. That fake stream is what makes the interesting properties testable
at all: a stream that crashes with a specific status, one that holds, one
that will not hold, one that writes its failure only to stderr.

What these cases are defending, in the order the defects actually happened
(walk-ledgers/merge-lane-watchers.md records all three):

  - the watched program's stderr must reach the filter, because the filter's
    own `Traceback \\(most recent` pattern exists for the child's own crash
    and both shell watchers discarded stderr;
  - the exit status announced must be the CHILD's, not a pipeline's: the
    first rewrite printed `rc=$?` after a pipe and reported a stream that
    crashed with 3 as rc=0, and one that exited 9 as rc=1. Cases here run
    exactly those two statuses;
  - a stream that cannot hold the bar is announced once, not once per
    attempt, and the return to coverage is announced when it happens;
  - the child does not inherit this program's stdin (the #398 reviewer
    measured `ssh -tt` putting an inherited interactive terminal into raw
    mode), a SIGTERM is announced with exit 143 rather than silent (it was
    measured silent, exit -15), and terminal escape sequences are stripped
    before a line is filtered or quoted (the pty colourised a remote
    traceback, and the escapes reached the quoted snippet).

The three interrupt cases failed four times in the merge lane's sweeps and
passed alone every time, and the trigger was recorded as unidentified. The
MECHANISM is identified: signal_and_wait() below SIGKILLs a watcher that has
not exited within its grace window, so under load the helper itself
manufactures all three failures at once — rc=-9 where 130 is expected, no
"NOT WATCHING" line because the process never got to print it, and a surviving
dialog stream because the killed watcher never reaped its child. The grace was
15 s; it is SIGNALLED_EXIT_GRACE_SECONDS below, and the kill now says so in
the output rather than leaving rc=-9 to be read as a handler defect. What makes
a signalled watcher slow on a loaded machine is still unidentified, and a run
carrying that note is still a load symptom to re-run alone.

Synchronization without sleeps: the fake stream appends a timestamp per
attempt, so a case can wait for the Nth attempt rather than guessing a
duration — which is how "BROKEN is announced once over four attempts" is
checked (the attempts demonstrably happened) and how the immediate restart
after a held stream is measured.
"""

import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

WATCH_SCRIPT = Path(__file__).with_name("watch-agent-dialog-alerts.py")

_spec = importlib.util.spec_from_file_location("watch_agent_dialog_alerts",
                                               WATCH_SCRIPT)
watcher_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(watcher_module)

CONTROL_DIRECTORY_VARIABLE = "WATCH_AGENT_DIALOG_ALERTS_TEST_CONTROL_DIR"

# How long a signalled watcher is given to exit on its own before the helper
# SIGKILLs it. MEASURED: an unloaded watcher exits in well under a second, and
# the kill path is only ever reached on a machine too busy to let it. It was
# 15 s, and at 15 s the merge lane's sweeps hit it four times (2026-09-21,
# sequential sweeps and concurrent ones both), each time failing the same three
# interrupt cases and each time passing when that suite was re-run alone.
SIGNALLED_EXIT_GRACE_SECONDS = 60.0

# The fake dialog stream. One attempt reads its step from plan.json (the
# last step repeats once the plan runs out), records that it started, and
# behaves as the step says. Nothing here imports the real watcher.
FAKE_DIALOG_STREAM_SOURCE = f'''#!/usr/bin/env python3
import json, os, pathlib, sys, time

control = pathlib.Path(os.environ["{CONTROL_DIRECTORY_VARIABLE}"])
attempts = control / "attempts.log"
with attempts.open("a", encoding="utf-8") as handle:
    handle.write(repr(time.monotonic()) + "\\n")
attempt_number = len(attempts.read_text(encoding="utf-8").splitlines())
plan = json.loads((control / "plan.json").read_text(encoding="utf-8"))
step = plan[min(attempt_number - 1, len(plan) - 1)]
if step.get("probe_stdin"):
    # What stdin held, or EOF at once: the wrapper must have given /dev/null.
    (control / "stdin-probe.txt").write_text(
        "read:" + repr(sys.stdin.read()), encoding="utf-8")
for line in step.get("stdout", []):
    print(line, flush=True)
for line in step.get("stderr", []):
    sys.stderr.write(line + "\\n")
    sys.stderr.flush()
time.sleep(step.get("hold_seconds", 0))
sys.exit(step.get("exit_code", 0))
'''

# The fake ssh. It records the argv it was handed, writes the ssh-shaped
# lines the case wants on stderr, and exits with the status the case wants.
def fake_ssh_source(stderr_lines, exit_code):
    return f'''#!/usr/bin/env python3
import json, os, pathlib, sys, time

control = pathlib.Path(os.environ["{CONTROL_DIRECTORY_VARIABLE}"])
(control / "ssh-argv.json").write_text(json.dumps(sys.argv[1:]),
                                       encoding="utf-8")
with (control / "attempts.log").open("a", encoding="utf-8") as handle:
    handle.write(repr(time.monotonic()) + "\\n")
for line in {stderr_lines!r}:
    sys.stderr.write(line + "\\n")
sys.stderr.flush()
sys.exit({exit_code})
'''

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


# ----------------------------------------------------------------------
# Unit cases: the filter, the command, the status wording, the state
# machine. No subprocess.
# ----------------------------------------------------------------------

def run_unit_cases():
    mac_filter = watcher_module.compile_alert_filter(watcher_module.TARGET_MAC)
    box_filter = watcher_module.compile_alert_filter(
        watcher_module.TARGET_NED_BOX)

    # Every pattern the ledger carried, with a line it must catch. A
    # pattern that stops matching its own reason for existing is the
    # silent failure this file is against.
    alert_lines = [
        ("supervisor exited", "assess WATCH: the supervisor exited early"),
        ("unsupervised", "bridge AGENT: seat is running unsupervised"),
        ("seat died", "merge-lane AGENT: the seat died overnight"),
        ("died with", "assess AGENT: the cell died with signal 9"),
        ("Traceback", "ned-review AGENT: Traceback (most recent call last):"),
        ("OOM", "assess AGENT: the kernel OOM killer took it"),
        ("wedged", "bridge AGENT: the seat is wedged on a prompt"),
        ("deadlock", "assess AGENT: deadlock between the two writers"),
        ("resource not accessible",
         "merge-lane AGENT: Resource not accessible by personal access token"),
        ("token expired", "merge-lane AGENT: the token has expired"),
        ("branch protection", "merge-lane CMD: gh api branch protection"),
        ("reset --hard main", "bridge CMD: git reset --hard main"),
        ("reset --hard origin/main", "bridge CMD: git reset --hard origin/main"),
        ("push --force main", "bridge CMD: git push --force main"),
    ]
    missed = [name for name, line in alert_lines if not mac_filter.search(line)]
    check("every committed alert pattern catches the line it exists for",
          not missed, f"missed: {missed}")

    check("the filter is case-insensitive, as grep -iE was",
          mac_filter.search("seat-a AGENT: traceback (most recent call last):"),
          "a lower-cased traceback header did not match")

    check("an ordinary dialog line is not an alert",
          not mac_filter.search(
              "merge-lane AGENT: reviewing pull request #391 now"),
          "an ordinary line matched the alert filter")

    # PINNED, not endorsed. `OOM` is matched case-insensitively as a
    # substring, so it also matches room/zoom/boom. Measured 2026-09-15
    # over this Mac's ~/.claude/projects transcripts: zoom 1225, room 1204,
    # headroom 226, caskroom 215, boom 112. The committed filter keeps the
    # retyped filter's behaviour exactly; tightening it to a word boundary
    # is a separate topic, and it will flip this case, which is the point
    # of pinning it here.
    check("PINNED NOISE: the OOM pattern also matches ordinary words "
          "(a word-boundary fix is a separate topic and flips this case)",
          mac_filter.search("assess AGENT: there is room for improvement"),
          "the pinned false positive no longer reproduces")

    check("ssh diagnostics are in the ned-box filter, so a failure says WHY",
          all(box_filter.search(line) for line in [
              "ssh: connect to host ned-box port 22: Connection refused",
              "ssh: Could not resolve hostname ned-box",
              "nedlern@ned-box: Permission denied (publickey).",
              "Host key verification failed.",
              "Connection reset by 10.0.1.106 port 22",
              "ssh: connect to host ned-box port 22: Operation timed out",
              "ssh: connect to host ned-box port 22: No route to host",
              "kex_exchange_identification: read: Connection reset by peer",
          ]), "an ssh diagnostic was swallowed by the ned-box filter")

    check("ssh diagnostics are NOT in the mac filter — nothing local emits "
          "them but a seat quoting them",
          not mac_filter.search(
              "ssh: connect to host ned-box port 22: Connection refused"),
          "the mac filter carried the remote-only patterns")

    # `NOT WATCHING` was a filter pattern in the shell watcher only so the
    # watcher's own announcement could survive the pipe it was printed
    # into. There is no pipe here, so it is gone; keeping it would mean a
    # seat quoting the words raised an alert.
    check("NOT WATCHING is no longer a filter pattern (it existed only to "
          "survive the pipe)",
          not mac_filter.search("assess AGENT: the log said NOT WATCHING"),
          "the pipe-era pattern is still in the filter")

    local_command = watcher_module.child_command(
        watcher_module.TARGET_MAC, "/x/scripts/watch-agent-dialogs.py",
        "nedlern@ned-box", "~/Projects/nedschorus/scripts/watch-agent-dialogs.py")
    check("the mac target runs the dialog watcher unbuffered, in process",
          local_command == [sys.executable, "-u",
                            "/x/scripts/watch-agent-dialogs.py"],
          f"{local_command}")

    remote_command = watcher_module.child_command(
        watcher_module.TARGET_NED_BOX, "/x/scripts/watch-agent-dialogs.py",
        "nedlern@ned-box", "~/Projects/nedschorus/scripts/watch-agent-dialogs.py")
    check("the ned-box target runs it over ssh, unbuffered, at the remote path",
          remote_command[0] == "ssh"
          and remote_command[-2] == "nedlern@ned-box"
          and remote_command[-1] ==
          "python3 -u ~/Projects/nedschorus/scripts/watch-agent-dialogs.py",
          f"{remote_command}")

    # BatchMode is what makes a credential failure SAY so: without it ssh
    # can sit on a password prompt no one will ever answer, which is
    # silence wearing a running process.
    check("the ssh options bound a dead connection and refuse to prompt",
          all(option in remote_command for option in
              ["ConnectTimeout=15", "ServerAliveInterval=15",
               "ServerAliveCountMax=4", "BatchMode=yes"]),
          f"{remote_command}")

    # Without the forced pty the remote python outlives the ssh client:
    # measured 2026-09-15 on ned-box, pid 488363 left running after this
    # wrapper was interrupted, one more per restart.
    check("the remote command gets a pty, so the remote watcher dies with "
          "its ssh client instead of being orphaned",
          remote_command[1] == "-tt", f"{remote_command}")

    check("the default remote destination and path are ned-box's",
          watcher_module.DEFAULT_REMOTE_SSH_DESTINATION == "nedlern@ned-box"
          and watcher_module.DEFAULT_REMOTE_DIALOG_SCRIPT_PATH ==
          "~/Projects/nedschorus/scripts/watch-agent-dialogs.py",
          "the committed defaults moved")

    check("the hold bar is 300s and the retry 60s, as ruled",
          watcher_module.DEFAULT_HOLD_SECONDS == 300.0
          and watcher_module.DEFAULT_RETRY_SECONDS == 60.0,
          "the committed defaults moved")

    # The status wording names WHOSE status it is. On the remote target it
    # is ssh's, and 255 is ambiguous — which the line has to say rather
    # than quietly presenting it as the remote program's.
    check("a mac status is named as the dialog watcher's own",
          watcher_module.exit_status_phrase(watcher_module.TARGET_MAC, 3)
          == "watch-agent-dialogs.py rc=3")
    check("a ned-box status is named as ssh's",
          "ssh rc=3" in watcher_module.exit_status_phrase(
              watcher_module.TARGET_NED_BOX, 3))
    check("ssh's own 255 is reported as ambiguous rather than as the "
          "remote program's status",
          "255" in watcher_module.exit_status_phrase(
              watcher_module.TARGET_NED_BOX, 255)
          and "own failures" in watcher_module.exit_status_phrase(
              watcher_module.TARGET_NED_BOX, 255))

    # A crash's exception line matches no alert pattern, so without this
    # the operator learns only that it crashed.
    detail = watcher_module.attempt_end_detail(
        watcher_module.TARGET_MAC, 1, "ValueError: the seats list was empty")
    check("a non-zero exit quotes the last thing the stream said",
          "ValueError: the seats list was empty" in detail, detail)
    clean_detail = watcher_module.attempt_end_detail(
        watcher_module.TARGET_MAC, 0, "assess AGENT: goodbye")
    check("a clean exit does not quote it",
          "goodbye" not in clean_detail, clean_detail)

    check("ssh's own closing line is recognised as teardown noise",
          all(watcher_module.is_ssh_session_teardown_line(line) for line in [
              "Connection to 10.0.1.106 closed.",
              "Connection to ned-box closed",
              "Shared connection to ned-box closed.",
          ]), "an ssh teardown line was not recognised")
    check("a seat that merely says the words is not teardown noise",
          not watcher_module.is_ssh_session_teardown_line(
              "assess AGENT: Connection to the database closed."),
          "the teardown pattern is not anchored")

    run_announcer_cases()


def run_escape_and_termination_unit_cases():
    strip = watcher_module.strip_terminal_escape_sequences
    coloured = ("\x1b[0;31mValueError\x1b[0m: \x1b[1mthe seats list "
                "was empty\x1b[0m")
    check("terminal colour escapes are stripped from a line",
          strip(coloured) == "ValueError: the seats list was empty",
          repr(strip(coloured)))
    check("a line without escapes is returned unchanged",
          strip("bridge CMD: git push --force main")
          == "bridge CMD: git push --force main")
    check("a cursor-movement escape (non-colour CSI) is stripped too",
          strip("\x1b[2K\x1b[1Gseat died") == "seat died",
          repr(strip("\x1b[2K\x1b[1Gseat died")))
    check("the SIGTERM exit status is 143, the shell's 128 + 15",
          watcher_module.SIGTERM_EXIT_CODE == 143,
          str(watcher_module.SIGTERM_EXIT_CODE))
    check("the SIGTERM handler raises rather than announcing (announcing "
          "would take a lock the interrupted code may hold)",
          _raises_watcher_terminated(),
          "handler did not raise WatcherTerminated")
    emitted = []
    announcer = watcher_module.StreamCoverageAnnouncer(
        "mac", watcher_module.TARGET_MAC, 300.0, 60.0,
        emit_line=emitted.append)
    announcer.terminated()
    check("a termination is announced as NOT WATCHING, naming SIGTERM",
          len(emitted) == 1 and emitted[0].startswith("WATCH mac: NOT WATCHING")
          and "terminated (SIGTERM)" in emitted[0], "\n".join(emitted))


def _raises_watcher_terminated():
    try:
        watcher_module.raise_watcher_terminated(signal.SIGTERM, None)
    except watcher_module.WatcherTerminated:
        return True
    except BaseException:
        return False
    return False


def new_announcer(hold_seconds=300.0):
    """An announcer printing into a list instead of stdout."""
    lines = []
    announcer = watcher_module.StreamCoverageAnnouncer(
        "mac", watcher_module.TARGET_MAC, hold_seconds, 60.0,
        emit_line=lines.append)
    return announcer, lines


def run_announcer_cases():
    # Four straight attempts that fall short: the condition is announced
    # once. A line per attempt would bury the events either side of it.
    announcer, lines = new_announcer()
    for _ in range(4):
        attempt = announcer.start_attempt()
        restart_now = announcer.attempt_ended(attempt, 4.0, 1, "")
    check("four straight short attempts announce BROKEN exactly once",
          sum(1 for line in lines if "keeps ending after only" in line) == 1,
          f"{lines}")
    check("an attempt that fell short waits rather than restarting at once",
          restart_now is False)

    # A stream that holds and then ends: each gap is a real gap, so each
    # one speaks.
    announcer, lines = new_announcer(hold_seconds=1.0)
    for _ in range(2):
        attempt = announcer.start_attempt()
        restart_now = announcer.attempt_ended(attempt, 900.0, 0, "")
    check("a stream that held and ended announces the gap every time",
          sum(1 for line in lines if "ended after 900s" in line) == 2,
          f"{lines}")
    check("a stream that held restarts immediately",
          restart_now is True)
    check("no RESTORED line when nothing was broken",
          not any("RESTORED" in line for line in lines), f"{lines}")

    # Broken, then holding: the restoration is announced once, and by the
    # timer — while the stream is still up, not at its next death.
    announcer, lines = new_announcer(hold_seconds=1.0)
    first = announcer.start_attempt()
    announcer.attempt_ended(first, 0.2, 1, "")
    second = announcer.start_attempt()
    announcer.hold_bar_reached(second)
    check("crossing the hold bar announces RESTORED while the stream is up",
          any("RESTORED" in line for line in lines), f"{lines}")
    restored_index = [index for index, line in enumerate(lines)
                      if "RESTORED" in line][0]
    announcer.attempt_ended(second, 5.0, 0, "")
    check("the gap line for that stream comes after the RESTORED line",
          any("ended after 5s" in line for line in lines[restored_index + 1:]),
          f"{lines}")
    third = announcer.start_attempt()
    announcer.hold_bar_reached(third)
    check("a second hold does not re-announce RESTORED (nothing was broken)",
          sum(1 for line in lines if "RESTORED" in line) == 1, f"{lines}")
    announcer.attempt_ended(third, 6.0, 0, "")
    # A fourth attempt that falls short — its hold timer never fires, which
    # is the only way an attempt can be short. Coverage was holding, so the
    # loss of it is a transition and speaks again.
    fourth = announcer.start_attempt()
    announcer.attempt_ended(fourth, 0.1, 1, "")
    check("falling short after a restoration announces BROKEN again — it is "
          "a transition",
          sum(1 for line in lines if "keeps ending after only" in line) == 2
          and lines[-1].endswith("until it holds"), f"{lines}")

    # Race one: the timer fires after the attempt it belongs to has ended.
    # Without the guard this prints a restoration for a stream that is
    # already gone.
    announcer, lines = new_announcer(hold_seconds=1.0)
    first = announcer.start_attempt()
    announcer.attempt_ended(first, 0.2, 1, "")
    before = len(lines)
    announcer.hold_bar_reached(first)
    check("a hold timer that fires after its attempt ended says nothing",
          len(lines) == before, f"{lines[before:]}")

    # Race two: the timer declared the hold at 300.0s and the measured
    # duration lands a hair under. The attempt must not then be reported as
    # if it never held, contradicting the line already printed.
    announcer, lines = new_announcer(hold_seconds=1.0)
    first = announcer.start_attempt()
    announcer.attempt_ended(first, 0.2, 1, "")
    second = announcer.start_attempt()
    announcer.hold_bar_reached(second)
    restart_now = announcer.attempt_ended(second, 0.999, 0, "")
    check("an attempt the timer already called held is not then called short",
          restart_now is True
          and not any("keeps ending after only 1s" in line for line in lines),
          f"{lines}")

    # A stale attempt's timer (the next attempt is already running) is
    # ignored: it would otherwise declare coverage that belongs to a stream
    # that is gone.
    announcer, lines = new_announcer(hold_seconds=1.0)
    first = announcer.start_attempt()
    announcer.attempt_ended(first, 0.1, 1, "")
    second = announcer.start_attempt()
    before = len(lines)
    announcer.hold_bar_reached(first)
    check("a stale attempt's hold timer says nothing",
          len(lines) == before, f"{lines[before:]}")


# ----------------------------------------------------------------------
# Subprocess cases: the real program, a fake dialog stream, a fake ssh.
# ----------------------------------------------------------------------

class FakeDialogStream:
    """A fake watch-agent-dialogs.py, driven by a plan file."""

    def __init__(self, directory, plan):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.marker = f"dialog-alerts-fake-{uuid.uuid4().hex[:8]}"
        self.path = self.directory / f"{self.marker}.py"
        self.path.write_text(FAKE_DIALOG_STREAM_SOURCE, encoding="utf-8")
        self.path.chmod(0o755)
        (self.directory / "plan.json").write_text(json.dumps(plan),
                                                  encoding="utf-8")
        (self.directory / "attempts.log").write_text("", encoding="utf-8")

    def environment(self, extra_path=None):
        environment = dict(os.environ)
        environment[CONTROL_DIRECTORY_VARIABLE] = str(self.directory)
        if extra_path:
            environment["PATH"] = f"{extra_path}{os.pathsep}" + environment["PATH"]
        return environment

    def attempt_times(self):
        try:
            text = (self.directory / "attempts.log").read_text(encoding="utf-8")
        except OSError:
            return []
        return [float(line) for line in text.splitlines() if line.strip()]

    def attempt_count(self):
        return len(self.attempt_times())

    def wait_for_attempts(self, wanted, timeout=20.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.attempt_count() >= wanted:
                return True
            time.sleep(0.02)
        return False


def write_fake_ssh(directory, control_directory, stderr_lines, exit_code):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "ssh"
    path.write_text(fake_ssh_source(stderr_lines, exit_code), encoding="utf-8")
    path.chmod(0o755)
    control = Path(control_directory)
    control.mkdir(parents=True, exist_ok=True)
    (control / "attempts.log").write_text("", encoding="utf-8")
    return path


def remote_environment(control_directory, fake_bin_directory):
    environment = dict(os.environ)
    environment[CONTROL_DIRECTORY_VARIABLE] = str(control_directory)
    environment["PATH"] = (f"{fake_bin_directory}{os.pathsep}"
                           + environment["PATH"])
    return environment


class WatcherProcess:
    """The wrapper as a subprocess, both its streams drained by threads."""

    def __init__(self, *flags, environment=None, stdin_text=None):
        self.lines = []
        self.error_lines = []
        # stdin_text gives the wrapper a real, readable stdin with content
        # in it; the stdin case needs that, because a wrapper inheriting a
        # runner's /dev/null would pass the case with or without the fix.
        self.process = subprocess.Popen(
            [sys.executable, "-u", str(WATCH_SCRIPT), *flags],
            stdin=(subprocess.PIPE if stdin_text is not None else None),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", env=environment)
        if stdin_text is not None:
            self.process.stdin.write(stdin_text)
            self.process.stdin.close()
        self._threads = [
            threading.Thread(target=self._drain, args=(self.process.stdout,
                                                       self.lines), daemon=True),
            threading.Thread(target=self._drain, args=(self.process.stderr,
                                                       self.error_lines),
                             daemon=True)]
        for thread in self._threads:
            thread.start()

    @staticmethod
    def _drain(stream, sink):
        for line in stream:
            sink.append(line.rstrip("\n"))

    def wait_for(self, fragment, timeout=20.0):
        """True once some stdout line contains the fragment; False on timeout."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if any(fragment in line for line in self.lines):
                return True
            time.sleep(0.02)
        return False

    def count(self, fragment):
        return sum(1 for line in self.lines if fragment in line)

    def interrupt_and_wait(self, timeout=SIGNALLED_EXIT_GRACE_SECONDS):
        return self.signal_and_wait(signal.SIGINT, timeout)

    def terminate_and_wait(self, timeout=SIGNALLED_EXIT_GRACE_SECONDS):
        return self.signal_and_wait(signal.SIGTERM, timeout)

    def signal_and_wait(self, signal_number, timeout=SIGNALLED_EXIT_GRACE_SECONDS):
        self.process.send_signal(signal_number)
        try:
            returncode = self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.process.kill()
            returncode = self.process.wait()
            # Said out loud, because this kill is what fails the cases that
            # follow: rc=-9 read as a handler defect is what sent four sweeps
            # looking for one.
            print(f"NOTE  the watcher did not exit within {timeout:g}s of "
                  f"signal {signal_number}, so this helper SIGKILLed it. The "
                  f"cases below fail for that reason, not the watcher's "
                  f"handler. Re-run this suite alone.")
        for thread in self._threads:
            thread.join(timeout=2)
        return returncode

    def stop(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        for thread in self._threads:
            thread.join(timeout=2)
        return list(self.lines)


def watcher_against(stream, *flags, environment=None, stdin_text=None):
    return WatcherProcess("--target", "mac",
                          "--local-dialog-script-path", str(stream.path),
                          *flags,
                          environment=environment or stream.environment(),
                          stdin_text=stdin_text)


def wait_until_gone(marker, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not process_is_running(marker):
            return True
        time.sleep(0.1)
    return False


def process_is_running(marker):
    result = subprocess.run(["pgrep", "-f", marker], capture_output=True,
                            text=True, check=False)
    return result.returncode == 0 and result.stdout.strip() != ""


def run_subprocess_cases():
    with tempfile.TemporaryDirectory() as scratch_name:
        scratch = Path(scratch_name)

        # --------------------------------------------------------------
        # The baseline, the filter on the real path, and the child's own
        # stderr — the defect both shell watchers had.
        # --------------------------------------------------------------
        stream = FakeDialogStream(scratch / "crash", [{
            "stdout": ["assess AGENT: nothing unusual here",
                       "bridge CMD: git push --force main"],
            "stderr": ["Traceback (most recent call last):",
                       "ValueError: the seats list was empty"],
            "exit_code": 3,
        }])
        watcher = watcher_against(stream, "--hold-seconds", "60",
                                  "--retry-seconds", "30")
        started = watcher.wait_for("WATCH mac: started")
        alert = watcher.wait_for("ALERT mac: bridge CMD: git push --force main")
        traceback_seen = watcher.wait_for(
            "ALERT mac: Traceback (most recent call last):")
        ended = watcher.wait_for("NOT WATCHING")
        lines = watcher.stop()
        check("the baseline is announced at startup, before anything happens",
              started and lines[0].startswith("WATCH mac: started"),
              "\n".join(lines))
        check("the baseline says silence means the stream is up",
              "silence from here means the stream is up" in lines[0],
              "\n".join(lines))
        check("a matching dialog line is passed through, labelled",
              alert, "\n".join(lines))
        check("a non-matching dialog line is dropped",
              watcher.count("nothing unusual here") == 0, "\n".join(lines))
        check("the child's stderr reaches the filter (stderr merged, not "
              "discarded — the 2026-09-13 defect)",
              traceback_seen, "\n".join(lines))
        check("a crash with exit 3 is announced as rc=3, not a pipeline's "
              "status (the 2026-09-13 rewrite's defect)",
              ended and any("watch-agent-dialogs.py rc=3" in line
                            for line in lines), "\n".join(lines))
        check("the exception line under the traceback is quoted with the "
              "status (no alert pattern matches it)",
              any("ValueError: the seats list was empty" in line
                  for line in lines if "NOT WATCHING" in line),
              "\n".join(lines))

        # --------------------------------------------------------------
        # A silent stream exiting 9 — the second measured lie (rc=1, grep's
        # status) — and a clean exit reported as 0.
        # --------------------------------------------------------------
        stream = FakeDialogStream(scratch / "exit9", [{"exit_code": 9}])
        watcher = watcher_against(stream, "--hold-seconds", "60",
                                  "--retry-seconds", "30")
        seen = watcher.wait_for("watch-agent-dialogs.py rc=9")
        lines = watcher.stop()
        check("a silent stream that exits 9 is announced as rc=9", seen,
              "\n".join(lines))

        stream = FakeDialogStream(scratch / "exit0", [{"exit_code": 0}])
        watcher = watcher_against(stream, "--hold-seconds", "60",
                                  "--retry-seconds", "30")
        seen = watcher.wait_for("watch-agent-dialogs.py rc=0")
        lines = watcher.stop()
        check("a clean exit is announced as rc=0", seen, "\n".join(lines))

        # --------------------------------------------------------------
        # Transition reporting on the real path: four attempts, one line.
        # --------------------------------------------------------------
        stream = FakeDialogStream(scratch / "broken", [{"exit_code": 1}])
        watcher = watcher_against(stream, "--hold-seconds", "30",
                                  "--retry-seconds", "0.05")
        broken = watcher.wait_for("keeps ending after only")
        attempted = stream.wait_for_attempts(4)
        lines = watcher.stop()
        check("a stream that will not hold announces BROKEN once over four "
              "attempts",
              broken and attempted and watcher.count("keeps ending after only") == 1,
              f"attempts={stream.attempt_count()} " + "\n".join(lines))
        check("and says it is staying quiet until it holds",
              any("staying quiet until it holds" in line for line in lines),
              "\n".join(lines))

        # --------------------------------------------------------------
        # Restoration announced while the stream is still up, by the timer
        # — not at its next death, which would leave post-BROKEN silence
        # meaning two things.
        # --------------------------------------------------------------
        stream = FakeDialogStream(scratch / "restored", [
            {"exit_code": 1},
            {"hold_seconds": 8, "exit_code": 0},
        ])
        watcher = watcher_against(stream, "--hold-seconds", "0.5",
                                  "--retry-seconds", "0.05")
        broken = watcher.wait_for("keeps ending after only")
        restored = watcher.wait_for("coverage RESTORED", timeout=6.0)
        still_up = watcher.count("the dialog stream ended after") == 0
        lines = watcher.stop()
        check("coverage RESTORED is announced when the bar is crossed, while "
              "the stream is still up",
              broken and restored and still_up, "\n".join(lines))

        # --------------------------------------------------------------
        # A stream that held restarts at once rather than waiting out the
        # retry interval — the gap is the restart, and the line says so.
        # --------------------------------------------------------------
        stream = FakeDialogStream(scratch / "immediate", [
            {"hold_seconds": 1.2, "exit_code": 0},
            {"hold_seconds": 30, "exit_code": 0},
        ])
        watcher = watcher_against(stream, "--hold-seconds", "1",
                                  "--retry-seconds", "30")
        two_attempts = stream.wait_for_attempts(2, timeout=15.0)
        times = stream.attempt_times()
        lines = watcher.stop()
        gap = (times[1] - times[0] - 1.2) if len(times) >= 2 else None
        check("a stream that held is restarted at once, not after the retry "
              "interval",
              two_attempts and gap is not None and gap < 5.0,
              f"gap={gap} attempts={times}\n" + "\n".join(lines))
        check("and the gap line says the restart is immediate",
              any("restarting it now" in line for line in lines),
              "\n".join(lines))

        # --------------------------------------------------------------
        # The remote path, with a fake ssh: the argv, and an ssh failure
        # that says WHY instead of only that the stream ended.
        # --------------------------------------------------------------
        control = scratch / "remote"
        write_fake_ssh(scratch / "fake-bin", control,
                       ["ssh: connect to host ned-box port 22: "
                        "Connection refused"], 255)
        watcher = WatcherProcess("--target", "ned-box",
                                 "--hold-seconds", "30",
                                 "--retry-seconds", "30",
                                 environment=remote_environment(
                                     control, scratch / "fake-bin"))
        refused = watcher.wait_for("Connection refused")
        status = watcher.wait_for("ssh rc=255")
        lines = watcher.stop()
        argv = json.loads((control / "ssh-argv.json").read_text(encoding="utf-8"))
        check("the ned-box target invokes ssh with the committed options, "
              "destination and remote path",
              argv[:9] == ["-tt",
                           "-o", "ConnectTimeout=15",
                           "-o", "ServerAliveInterval=15",
                           "-o", "ServerAliveCountMax=4",
                           "-o", "BatchMode=yes"]
              and argv[-2] == "nedlern@ned-box"
              and argv[-1].startswith("python3 -u "), f"{argv}")
        check("an ssh failure's reason reaches the operator, not just the "
              "end of the stream",
              refused, "\n".join(lines))
        check("ssh's 255 is announced as ambiguous rather than as the remote "
              "program's status",
              status and any("own failures" in line for line in lines),
              "\n".join(lines))

        # --------------------------------------------------------------
        # ssh's own teardown line must not displace the line that said why.
        # Measured live on ned-box 2026-09-15: a remote stream that died of
        # a ValueError announced `last output: Connection to 10.0.1.106
        # closed.` — the pty makes ssh print that on every stream's last
        # breath, and it arrived after the exception it was hiding.
        # --------------------------------------------------------------
        control = scratch / "remote-teardown"
        write_fake_ssh(scratch / "fake-bin-teardown", control,
                       ["ValueError: the remote seats list was empty",
                        "Connection to ned-box closed."], 3)
        watcher = WatcherProcess("--target", "ned-box",
                                 "--hold-seconds", "30",
                                 "--retry-seconds", "30",
                                 environment=remote_environment(
                                     control, scratch / "fake-bin-teardown"))
        ended = watcher.wait_for("NOT WATCHING")
        lines = watcher.stop()
        check("ssh's closing line does not displace the line that said why",
              ended and any("ValueError: the remote seats list was empty"
                            in line for line in lines
                            if "NOT WATCHING" in line),
              "\n".join(lines))
        check("and the closing line is not quoted in its place",
              not any("Connection to ned-box closed" in line
                      for line in lines if "NOT WATCHING" in line),
              "\n".join(lines))

        # --------------------------------------------------------------
        # Bad invocation refuses at startup rather than watching wrongly.
        # --------------------------------------------------------------
        present_script = ["--local-dialog-script-path", str(WATCH_SCRIPT)]
        for flags, reason in [
            (["--target", "mac", "--hold-seconds", "0", *present_script],
             "--hold-seconds"),
            (["--target", "mac", "--retry-seconds", "-1", *present_script],
             "--retry-seconds"),
            (["--target", "mac", "--local-dialog-script-path",
              str(scratch / "no-such-file.py")], "no dialog watcher at"),
            (["--target", "ned-box", "--remote-ssh-destination", "  "],
             "--remote-ssh-destination"),
        ]:
            result = subprocess.run(
                [sys.executable, str(WATCH_SCRIPT), *flags],
                capture_output=True, text=True, check=False, timeout=30)
            check(f"a bad invocation ({reason}) exits 2 and says why",
                  result.returncode == 2 and reason in result.stderr,
                  f"rc={result.returncode} stderr={result.stderr!r}")

        # --------------------------------------------------------------
        # An interrupt announces the loss of coverage and takes the child
        # with it — a watcher that dies quietly is the whole failure.
        # --------------------------------------------------------------
        stream = FakeDialogStream(scratch / "interrupt", [
            {"stdout": ["assess AGENT: holding steady"], "hold_seconds": 120,
             "exit_code": 0}])
        watcher = watcher_against(stream, "--hold-seconds", "60",
                                  "--retry-seconds", "30")
        started = watcher.wait_for("WATCH mac: started")
        stream.wait_for_attempts(1)
        returncode = watcher.interrupt_and_wait()
        child_gone = True
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if not process_is_running(stream.marker):
                break
            time.sleep(0.1)
        else:
            child_gone = False
        check("an interrupt announces that nothing is being watched now",
              started and any("NOT WATCHING" in line and "interrupted" in line
                              for line in watcher.lines),
              "\n".join(watcher.lines))
        check("an interrupt exits 130", returncode == 130, f"rc={returncode}")
        check("an interrupt takes the dialog stream with it",
              child_gone, f"{stream.marker} still running")

        # --------------------------------------------------------------
        # A SIGTERM — what Monitor's expiry sends, every thirty minutes —
        # is announced and exits 143. Measured before the handler: silent,
        # exit -15.
        # --------------------------------------------------------------
        stream = FakeDialogStream(scratch / "terminate", [
            {"stdout": ["assess AGENT: holding steady"], "hold_seconds": 120,
             "exit_code": 0}])
        watcher = watcher_against(stream, "--hold-seconds", "60",
                                  "--retry-seconds", "30")
        started = watcher.wait_for("WATCH mac: started")
        stream.wait_for_attempts(1)
        returncode = watcher.terminate_and_wait()
        child_gone = wait_until_gone(stream.marker)
        check("a SIGTERM announces that nothing is being watched now, "
              "naming the signal",
              started and any("NOT WATCHING" in line
                              and "terminated (SIGTERM)" in line
                              for line in watcher.lines),
              "\n".join(watcher.lines))
        check("a SIGTERM exits 143, not -15", returncode == 143,
              f"rc={returncode}")
        check("a SIGTERM takes the dialog stream with it",
              child_gone, f"{stream.marker} still running")

        # A SIGTERM during the retry sleep, when there is no child at all,
        # is announced the same way.
        stream = FakeDialogStream(scratch / "terminate-in-retry",
                                  [{"exit_code": 1}])
        watcher = watcher_against(stream, "--hold-seconds", "30",
                                  "--retry-seconds", "120")
        broken = watcher.wait_for("keeps ending after only")
        returncode = watcher.terminate_and_wait()
        check("a SIGTERM during the retry sleep is announced and exits 143",
              broken and returncode == 143
              and any("terminated (SIGTERM)" in line for line in watcher.lines),
              f"rc={returncode}\n" + "\n".join(watcher.lines))

        # --------------------------------------------------------------
        # The child does not inherit stdin. The wrapper is given a real
        # stdin with content; the fake stream reads its own stdin and
        # records what it got, which must be EOF at once.
        # --------------------------------------------------------------
        stream = FakeDialogStream(scratch / "stdin", [
            {"probe_stdin": True, "exit_code": 0}])
        watcher = watcher_against(stream, "--hold-seconds", "60",
                                  "--retry-seconds", "30",
                                  stdin_text="MUST-NOT-REACH-THE-CHILD\n")
        watcher.wait_for("watch-agent-dialogs.py rc=0")
        watcher.stop()
        probe_path = stream.directory / "stdin-probe.txt"
        probe = (probe_path.read_text(encoding="utf-8")
                 if probe_path.is_file() else "<no probe written>")
        check("the dialog stream does not inherit the wrapper's stdin "
              "(it reads EOF at once, not what the wrapper was given)",
              probe == "read:''", probe)

        # --------------------------------------------------------------
        # Terminal escapes are stripped before the filter and the snippet.
        # A coloured exception line is quoted clean, and a phrase the
        # filter matches on still matches with an escape splitting it.
        # --------------------------------------------------------------
        stream = FakeDialogStream(scratch / "escapes", [{
            "stdout": ["bridge AGENT: the seat \u001b[31mdied\u001b[0m "
                       "in its sleep"],
            "stderr": ["Traceback (most recent call last):",
                       "\u001b[0;31mValueError\u001b[0m: \u001b[1mthe "
                       "coloured seats list was empty\u001b[0m"],
            "exit_code": 3,
        }])
        watcher = watcher_against(stream, "--hold-seconds", "60",
                                  "--retry-seconds", "30")
        split_alert = watcher.wait_for(
            "ALERT mac: bridge AGENT: the seat died in its sleep")
        ended = watcher.wait_for("NOT WATCHING")
        lines = watcher.stop()
        check("an alert phrase split by a colour escape still matches, and "
              "is passed through clean",
              split_alert, "\n".join(lines))
        check("a coloured exception line is quoted without its escapes",
              ended and any("last output: ValueError: the coloured seats "
                            "list was empty" in line
                            for line in lines if "NOT WATCHING" in line),
              "\n".join(lines))
        check("no escape byte reaches any output line",
              not any("\x1b" in line for line in lines), "\n".join(lines))


if __name__ == "__main__":
    run_unit_cases()
    run_escape_and_termination_unit_cases()
    run_subprocess_cases()
    print()
    if failures:
        print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
        sys.exit(1)
    print("all cases passed")
