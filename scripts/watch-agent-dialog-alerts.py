#!/usr/bin/env python3
"""Watch agent-dialog alerts and announce changes in stream coverage."""

import argparse
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

TARGET_MAC = "mac"
TARGET_NED_BOX = "ned-box"

DEFAULT_HOLD_SECONDS = 300.0
DEFAULT_RETRY_SECONDS = 60.0

# Preserve cwd: the child excludes the local seat by working directory, preventing self-watch feedback.
DIALOG_SCRIPT_NAME = "watch-agent-dialogs.py"
DEFAULT_REMOTE_SSH_DESTINATION = "nedlern@ned-box"
DEFAULT_REMOTE_DIALOG_SCRIPT_PATH = "~/Projects/nedschorus/scripts/watch-agent-dialogs.py"

# Bound stalled connections; BatchMode makes credential failures fail instead of waiting for input.
SSH_OPTIONS = (
    "-o", "ConnectTimeout=15",
    "-o", "ServerAliveInterval=15",
    "-o", "ServerAliveCountMax=4",
    "-o", "BatchMode=yes",
)

# A remote pty makes Python exit when ssh disconnects; the pty also produces CRLF newlines.
FORCE_REMOTE_PTY_OPTION = "-tt"

# OOM matches substrings, including room and zoom; changing to word boundaries changes filter behavior.
FLEET_ALERT_PATTERNS = (
    "supervisor exited",
    "unsupervised",
    "seat died",
    "died with",
    r"Traceback \(most recent",
    "OOM",
    "wedged",
    "deadlock",
    "resource not accessible",
    "token.*expired",
    "branch protection",
    r"reset --hard (origin/)?main",
    r"push.*--force.*main",
)

# Include ssh diagnostics remotely so connection failures retain their cause.
SSH_DIAGNOSTIC_PATTERNS = (
    "Permission denied",
    "Host key verification",
    "Connection refused",
    "Connection reset",
    "Operation timed out",
    "No route to host",
    "Could not resolve",
    "kex_exchange_identification",
)

# ssh uses 255 for its own failures, but a remote command can also exit 255.
SSH_OWN_FAILURE_EXIT_CODE = 255

# Ignore ssh teardown lines when quoting the last output so they do not displace the failure diagnosis.
SSH_SESSION_TEARDOWN_PATTERN = re.compile(
    r"^(?:Shared connection|Connection) to \S+ closed\.?$")

LAST_OUTPUT_LINE_SNIPPET_CHARS = 200

# The remote pty enables traceback colors; strip escapes before matching and truncating diagnostics.
TERMINAL_ESCAPE_SEQUENCE_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")

# 128 + SIGTERM is the shell convention for termination by that signal.
SIGTERM_EXIT_CODE = 128 + signal.SIGTERM

# Keep shutdown below Monitor's eight-second SIGKILL deadline.
CHILD_SHUTDOWN_SECONDS = 5.0

_emit_lock = threading.Lock()


def emit(line):
    """Emit one flushed event under the announcer lock."""
    # The hold timer emits from another thread; buffering would hide coverage loss.
    with _emit_lock:
        print(line, flush=True)


def warn(line):
    print(line, file=sys.stderr, flush=True)


class WatcherTerminated(BaseException):
    """A BaseException so generic Exception handlers cannot swallow termination."""


def raise_watcher_terminated(signal_number, frame):
    # Do not announce in the signal handler: the interrupted code may hold the announcer lock.
    raise WatcherTerminated()


def strip_terminal_escape_sequences(line):
    return TERMINAL_ESCAPE_SEQUENCE_PATTERN.sub("", line)


def one_line_snippet(text, limit):
    """Return a length-bounded snippet with newlines folded to paragraph markers."""
    return " ¶ ".join(str(text).strip().splitlines())[:limit]


def is_ssh_session_teardown_line(line):
    return bool(SSH_SESSION_TEARDOWN_PATTERN.match(line.strip()))


def alert_patterns_for_target(target):
    if target == TARGET_NED_BOX:
        return FLEET_ALERT_PATTERNS + SSH_DIAGNOSTIC_PATTERNS
    return FLEET_ALERT_PATTERNS


def compile_alert_filter(target):
    return re.compile("|".join(alert_patterns_for_target(target)), re.IGNORECASE)


def child_command(target, local_dialog_script_path, remote_ssh_destination,
                  remote_dialog_script_path):
    """Return the command for one stream attempt."""
    # Unbuffered Python reports events promptly; the remote shell must expand the ~-relative path.
    if target == TARGET_NED_BOX:
        return ["ssh", FORCE_REMOTE_PTY_OPTION, *SSH_OPTIONS,
                remote_ssh_destination,
                f"python3 -u {remote_dialog_script_path}"]
    return [sys.executable, "-u", str(local_dialog_script_path)]


def exit_status_phrase(target, returncode):
    """Format the exit status with the process that owns the status."""
    if target != TARGET_NED_BOX:
        return f"{DIALOG_SCRIPT_NAME} rc={returncode}"
    if returncode == SSH_OWN_FAILURE_EXIT_CODE:
        return (f"ssh rc={returncode}, which ssh uses for its own failures, "
                f"so this may be ssh or a remote program that exited 255")
    return f"ssh rc={returncode} (the remote program's own status)"


def attempt_end_detail(target, returncode, last_output_line):
    """Format the exit status and, on failure, the last output line."""
    # The final exception line may not match any alert pattern.
    detail = exit_status_phrase(target, returncode)
    if returncode != 0 and last_output_line:
        detail += ("; last output: "
                   + one_line_snippet(last_output_line,
                                      LAST_OUTPUT_LINE_SNIPPET_CHARS))
    return detail


def baseline_line(label, target, pattern_count, hold_seconds, retry_seconds,
                  what_is_run):
    where = ("this machine" if target != TARGET_NED_BOX
             else "ned-box over ssh")
    return (f"WATCH {label}: started — watching {where} with {what_is_run} "
            f"against {pattern_count} alert patterns (stderr merged in); "
            f"silence from here means the stream is up and nothing matched. "
            f"A stream that ends is announced; one that cannot hold "
            f"{hold_seconds:g}s is announced once, then retried every "
            f"{retry_seconds:g}s in silence until it holds.")


class StreamCoverageAnnouncer:
    """Announce coverage transitions while serializing timer and stream-end updates."""

    def __init__(self, label, target, hold_seconds, retry_seconds,
                 emit_line=emit):
        self.label = label
        self.target = target
        self.hold_seconds = hold_seconds
        self.retry_seconds = retry_seconds
        self.emit_line = emit_line
        self.lock = threading.Lock()
        self.state = "unknown"
        self.attempt_id = 0
        self.hold_announced_attempt = None
        self.ended_attempt = None

    def start_attempt(self):
        with self.lock:
            self.attempt_id += 1
            return self.attempt_id

    def _mark_held(self, attempt_id):
        """Announce restoration from the broken state; caller holds the lock."""
        # The baseline already promises the initial hold, so only restoration needs another announcement.
        if self.hold_announced_attempt == attempt_id:
            return
        self.hold_announced_attempt = attempt_id
        if self.state == "broken":
            self.emit_line(
                f"WATCH {self.label}: coverage RESTORED — the dialog stream "
                f"has now held {self.hold_seconds:g}s, so it is watching "
                f"again; silence means it holds")
        self.state = "holding"

    def hold_bar_reached(self, attempt_id):
        with self.lock:
            if attempt_id != self.attempt_id or attempt_id == self.ended_attempt:
                return  # A late timer must not announce restored coverage after the stream ends.
            self._mark_held(attempt_id)

    def attempt_ended(self, attempt_id, duration_seconds, returncode,
                      last_output_line):
        """Announce the attempt's end and return whether the next attempt should start immediately."""
        with self.lock:
            self.ended_attempt = attempt_id
            detail = attempt_end_detail(self.target, returncode,
                                        last_output_line)
            # Honor a timer-announced hold even if the end measurement falls just below the threshold.
            held = (duration_seconds >= self.hold_seconds
                    or self.hold_announced_attempt == attempt_id)
            if held:
                self._mark_held(attempt_id)
                self.emit_line(
                    f"WATCH {self.label}: NOT WATCHING — the dialog stream "
                    f"ended after {duration_seconds:.0f}s ({detail}); "
                    f"restarting it now, so the gap is that restart")
                return True
            if self.state != "broken":
                self.emit_line(
                    f"WATCH {self.label}: NOT WATCHING — the dialog stream "
                    f"keeps ending after only {duration_seconds:.0f}s, under "
                    f"the {self.hold_seconds:g}s hold bar, so events are "
                    f"being missed between attempts ({detail}); retrying "
                    f"every {self.retry_seconds:g}s and staying quiet until "
                    f"it holds")
            self.state = "broken"
            return False

    def interrupted(self):
        self._stopped("interrupted")

    def terminated(self):
        self._stopped("terminated (SIGTERM)")

    def _stopped(self, how):
        with self.lock:
            self.emit_line(
                f"WATCH {self.label}: NOT WATCHING — this watcher was "
                f"{how}; nothing is being seen here until it is restarted")


def stop_child(process):
    if process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=CHILD_SHUTDOWN_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    except OSError:
        pass


def run_one_stream(command, alert_filter, label, emit_line=emit):
    """Run one stream, emit matching lines, and return the child's status and last output."""
    # Merge stderr so the alert filter also sees child tracebacks.
    process = subprocess.Popen(
        command,
        # ssh -tt with inherited terminal input disables local Ctrl-C handling; DEVNULL preserves the local terminal.
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        # Dialog snippets may contain undecodable bytes; one byte must not stop the watch.
        errors="replace",
        bufsize=1,
    )
    last_output_line = ""
    try:
        while True:
            raw_line = process.stdout.readline()
            if not raw_line:
                break
            line = strip_terminal_escape_sequences(raw_line.rstrip("\r\n"))
            if not line.strip():
                continue
            if not is_ssh_session_teardown_line(line):
                last_output_line = line
            if alert_filter.search(line):
                emit_line(f"ALERT {label}: {line}")
    except (KeyboardInterrupt, WatcherTerminated):
        stop_child(process)
        raise
    finally:
        try:
            process.stdout.close()
        except OSError:
            pass
    # Let the child finish after stdout closes so the reported status is the child's own.
    return process.wait(), last_output_line


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        description="Watch the fleet's agent dialogs for alerts, here or on "
                    "ned-box, announcing the baseline and every gap in "
                    "coverage.")
    parser.add_argument("--target", choices=[TARGET_MAC, TARGET_NED_BOX],
                        action="append", default=None,
                        help=f"where the dialog watcher runs: {TARGET_MAC} "
                             f"for this machine (the merge-lane seat's own, "
                             f"hence the name), {TARGET_NED_BOX} for ned-box "
                             f"over ssh; give it once per target to watch "
                             f"several from one process, each in its own "
                             f"child watcher labelled by its target "
                             f"(default: {TARGET_MAC})")
    parser.add_argument("--label", default=None,
                        help="name for this watcher in its own lines, with "
                             "one --target only (default: the target)")
    parser.add_argument("--hold-seconds", type=float,
                        default=DEFAULT_HOLD_SECONDS,
                        help=f"how long a stream must stay up to count as "
                             f"watching (default: {DEFAULT_HOLD_SECONDS:g})")
    parser.add_argument("--retry-seconds", type=float,
                        default=DEFAULT_RETRY_SECONDS,
                        help=f"wait between attempts that fell short of the "
                             f"hold bar; one that held restarts immediately "
                             f"(default: {DEFAULT_RETRY_SECONDS:g})")
    parser.add_argument("--local-dialog-script-path",
                        default=str(Path(__file__).resolve()
                                    .with_name(DIALOG_SCRIPT_NAME)),
                        help="the dialog watcher to run on this machine "
                             "(default: this script's sibling "
                             f"{DIALOG_SCRIPT_NAME}; the tests point this at "
                             "a fake stream)")
    parser.add_argument("--remote-ssh-destination",
                        default=DEFAULT_REMOTE_SSH_DESTINATION,
                        help=f"ssh destination for --target {TARGET_NED_BOX} "
                             f"(default: {DEFAULT_REMOTE_SSH_DESTINATION})")
    parser.add_argument("--remote-dialog-script-path",
                        default=DEFAULT_REMOTE_DIALOG_SCRIPT_PATH,
                        help=f"the dialog watcher's path on ned-box, expanded "
                             f"by the remote shell (default: "
                             f"{DEFAULT_REMOTE_DIALOG_SCRIPT_PATH})")
    return parser.parse_args(argv)


def invocation_error(arguments, targets):
    """Return why the invocation cannot watch, or None when it can."""
    if arguments.hold_seconds <= 0:
        return "--hold-seconds must be > 0"
    if arguments.retry_seconds < 0:
        return "--retry-seconds must be >= 0"
    if len(targets) > 1 and arguments.label is not None:
        return "--label names one watcher; give it with one --target only"
    if TARGET_NED_BOX in targets and not arguments.remote_ssh_destination.strip():
        return "--remote-ssh-destination is empty"
    local_script = Path(arguments.local_dialog_script_path).expanduser()
    if TARGET_MAC in targets and not local_script.is_file():
        return f"no dialog watcher at {local_script}"
    return None


def child_watcher_command(arguments, target):
    """Return the command that runs this script as the watcher for one target."""
    return [sys.executable, "-u", str(Path(__file__).resolve()),
            "--target", target,
            "--hold-seconds", repr(arguments.hold_seconds),
            "--retry-seconds", repr(arguments.retry_seconds),
            "--local-dialog-script-path", arguments.local_dialog_script_path,
            "--remote-ssh-destination", arguments.remote_ssh_destination,
            "--remote-dialog-script-path",
            arguments.remote_dialog_script_path]


def relay_child_watcher(target, process, stopping):
    """Relay one child watcher's lines; announce the child's own exit unless this process stopped it."""
    for raw_line in process.stdout:
        emit(raw_line.rstrip("\n"))
    returncode = process.wait()
    if not stopping.is_set():
        emit(f"WATCH {target}: NOT WATCHING — its watcher exited on its own "
             f"(rc={returncode}); nothing is being seen there until this "
             f"watcher is restarted")


def watch_targets_in_child_processes(arguments, targets):
    """Run one child watcher per target and relay their lines as one stream."""
    # Each child keeps the single-target behaviour and announces its own baseline,
    # gaps and termination; this process only relays and reports a child that exits.
    stopping = threading.Event()
    children = []
    relays = []
    signal.signal(signal.SIGTERM, raise_watcher_terminated)
    try:
        for target in targets:
            process = subprocess.Popen(
                child_watcher_command(arguments, target),
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace", bufsize=1)
            children.append(process)
            relay = threading.Thread(target=relay_child_watcher,
                                     args=(target, process, stopping),
                                     daemon=True)
            relay.start()
            relays.append(relay)
        while any(relay.is_alive() for relay in relays):
            for relay in relays:
                relay.join(timeout=1.0)
        return 1
    except (KeyboardInterrupt, WatcherTerminated) as stop:
        stopping.set()
        # Monitor signals the whole process group, but a signal sent to this
        # process alone must still reach the children so each announces its loss.
        child_signal = (signal.SIGINT if isinstance(stop, KeyboardInterrupt)
                        else signal.SIGTERM)
        for process in children:
            if process.poll() is None:
                try:
                    process.send_signal(child_signal)
                except OSError:
                    pass
        # Each child needs up to CHILD_SHUTDOWN_SECONDS to stop its stream; relay
        # its last lines within that, staying inside Monitor's SIGKILL deadline.
        deadline = time.monotonic() + CHILD_SHUTDOWN_SECONDS + 1.0
        for relay in relays:
            relay.join(timeout=max(0.0, deadline - time.monotonic()))
        for process in children:
            stop_child(process)
        return 130 if isinstance(stop, KeyboardInterrupt) else SIGTERM_EXIT_CODE


def main(argv=None):
    arguments = parse_arguments(argv)
    targets = list(dict.fromkeys(arguments.target or [TARGET_MAC]))
    error = invocation_error(arguments, targets)
    if error:
        warn(f"watch-agent-dialog-alerts: {error}")
        return 2

    # Dialog snippets may contain characters the output encoding cannot represent.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    if len(targets) > 1:
        return watch_targets_in_child_processes(arguments, targets)

    target = targets[0]
    local_script = Path(arguments.local_dialog_script_path).expanduser()
    label = arguments.label or target
    alert_filter = compile_alert_filter(target)
    command = child_command(target, local_script,
                            arguments.remote_ssh_destination,
                            arguments.remote_dialog_script_path)
    what_is_run = (str(local_script) if target == TARGET_MAC
                   else f"{arguments.remote_ssh_destination}:"
                        f"{arguments.remote_dialog_script_path}")

    emit(baseline_line(label, target,
                       len(alert_patterns_for_target(target)),
                       arguments.hold_seconds, arguments.retry_seconds,
                       what_is_run))

    announcer = StreamCoverageAnnouncer(label, target,
                                        arguments.hold_seconds,
                                        arguments.retry_seconds)
    # Monitor expires the process group with SIGTERM; coverage loss must be announced on that path too.
    signal.signal(signal.SIGTERM, raise_watcher_terminated)
    try:
        while True:
            attempt_id = announcer.start_attempt()
            hold_timer = threading.Timer(arguments.hold_seconds,
                                         announcer.hold_bar_reached,
                                         args=(attempt_id,))
            hold_timer.daemon = True
            hold_timer.start()
            started_at = time.monotonic()
            try:
                returncode, last_output_line = run_one_stream(
                    command, alert_filter, label)
            finally:
                hold_timer.cancel()
            duration_seconds = time.monotonic() - started_at
            held = announcer.attempt_ended(attempt_id, duration_seconds,
                                           returncode, last_output_line)
            if not held:
                time.sleep(arguments.retry_seconds)
    except KeyboardInterrupt:
        announcer.interrupted()
        return 130
    except WatcherTerminated:
        announcer.terminated()
        return SIGTERM_EXIT_CODE


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        # Before the watch starts, there is no coverage loss to announce.
        sys.exit(130)
    except WatcherTerminated:
        # The handler may fire before the watch's try block starts.
        sys.exit(SIGTERM_EXIT_CODE)
    except BrokenPipeError:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)
