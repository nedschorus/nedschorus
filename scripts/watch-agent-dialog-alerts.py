#!/usr/bin/env python3
"""Watch the fleet's agent dialogs for alerts, and say when it stops watching.

This wraps scripts/watch-agent-dialogs.py — which is used UNCHANGED, as a
child process — and adds the three things a watcher needs that a raw dialog
stream does not have: a committed alert filter, an announced baseline, and
an announced end. It runs that program either on this machine (--target mac)
or on ned-box over ssh (--target ned-box), which are the merge-lane seat's
watchers 2 and 3.

Why it exists. Those two watchers were hand-typed shell blocks, retyped into
a Monitor call at the start of every merge-lane session out of a prose
ledger (walk-ledgers/merge-lane-watchers.md, machine-local and gitignored).
That is the same arrangement watch-open-pull-requests.py was written to end
for watcher 1, and its docstring states the argument: retyped shell is
"never reviewed, never tested", "each retyping was a fresh chance to get it
wrong, and the commonest way to get it wrong is silent". The ledger's own
text records the cost, measured 2026-09-13, when all three watchers were
found defective in one sitting:

  - both dialog watchers DISCARDED the watched program's stderr (`2>/dev/null`
    on the ssh, stderr unmerged on the Mac), so a Python traceback from
    watch-agent-dialogs.py could never match the filter's own `Traceback
    \\(most recent` pattern — the filter was blind to its own crash;
  - neither announced the end of its own stream, so a dead watcher looked
    exactly like a quiet fleet;
  - the ned-box one declared the MACHINE unreachable after one failed
    10-second probe, flapping UNREACHABLE/reachable while ned-box was up,
    idle and healthy.

And the first hand-typed REWRITE of that fix was itself defective, which is
the trap this file is shaped to make impossible. It printed `rc=$?` with the
echo placed AFTER a pipe, where `$?` is the PIPELINE's status — grep's,
never the watched program's. Measured: a stream crashing with exit 3
reported `rc=0`, and a stream exiting 9 reported `rc=1`. A crashed stream
announcing `rc=0` is a false clean, the exact lie the rewrite existed to
stop. walk-ledgers/merge-gate.sh carries that warning at the top of its own
file and it was reproduced anyway the same day. Here there is no pipeline at
all: the child is a subprocess whose status comes from wait(), so the status
printed is the child's by construction rather than by care.

The user's ruling over all of it: "a watcher that doesn't watch correctly is
worse than useless." Silence from this program means exactly one thing — the
stream is up and nothing matched.

Output contract — one stdout line per event, flushed immediately:

  ALERT mac: merge-lane CMD: git push --force main
                             a line from watch-agent-dialogs.py (stdout or
                             stderr) that matched the alert filter, prefixed
                             with the target so a stream carrying both
                             machines says which one spoke
  ALERT ned-box: ssh: connect to host ned-box port 22: Connection refused
                             on the remote target, ssh's own diagnostics are
                             in the filter too, so a failure says WHY
  WATCH mac: started ...     the baseline, one line, at startup
  WATCH mac: NOT WATCHING ...  the stream ended, with how long it held and
                             the child's exit status
  WATCH mac: coverage RESTORED ...  the stream has held the hold bar again

Everything else the dialog stream says is dropped. That includes
watch-agent-dialogs.py's own `WATCH:` lines (`no transcript found`,
`switched to <file>`): a rollover is routine and would be noise at this
altitude. Unchanged from the shell watchers, and a deliberate keep.

The filter, committed rather than retyped. FLEET_ALERT_PATTERNS is the
ledger's list verbatim, and SSH_DIAGNOSTIC_PATTERNS is added on the remote
target only, because those strings can only come from ssh: without them a
`Could not resolve` or a `Permission denied` is swallowed and the operator
gets only "the stream ended". One pattern of the shell version's is
deliberately GONE: `NOT WATCHING`. It was in the filter only so that the
watcher's own announcement could survive the pipe it was printed into.
There is no pipe here — this program's own lines never pass through the
filter — so keeping it would only mean a seat that quoted the words "not
watching" in a dialog raised an alert.

Known noise, measured and deliberately NOT fixed here. The `OOM` pattern is
matched case-insensitively as a substring, so it also matches room, zoom,
headroom, caskroom, boom and doomed. Measured 2026-09-15 over this Mac's
~/.claude/projects transcripts: zoom 1225, room 1204, headroom 226,
caskroom 215, boom 112, doomed 59 occurrences, against 975 of a bare `oom`.
A word-boundary form would fix it, and changing the filter's meaning is a
second topic with its own argument — this change is "the filter is committed
instead of retyped", and it keeps the retyped filter's behaviour exactly.
The test suite PINS the false positive rather than asserting it is right, so
the follow-up flips a case that names itself.

The hold bar, and what silence means on each side of it. A stream that
cannot stay up for --hold-seconds (default 300) is missing events between
its attempts however often it reconnects, so that condition is announced
ONCE and then the program stays quiet until the stream holds. Transitions
speak; steady states are silent. There is no separate reachability probe:
the stream attempt IS the probe, which is what stopped watcher 3 flapping.

One deliberate difference from the ledger's shell version, because silence
had to be made unambiguous in both directions. That version announced
"coverage RESTORED" only when a healthy stream next ENDED, so between a
BROKEN line and the next failure silence meant either "still broken,
retrying" or "holding fine" — two meanings, which is the defect this whole
family exists to remove. Here the restoration is announced the moment the
stream crosses the hold bar, by a timer, while it is still up.

A second, smaller difference: after a stream that HELD, the next attempt
starts immediately rather than after --retry-seconds, since a stream that
held cannot spin — at most one restart per hold bar. Only an attempt that
fell short of the bar waits. Each announcement says which of the two is
about to happen.

cwd is load-bearing, and this program never changes it. watch-agent-dialogs.py
excludes the seat whose directory contains the working directory, and that
exclusion is the only thing keeping the merge-lane seat out of its own watch
— a self-watch is an unbounded feedback loop, because the watcher's output
lands in its own session transcript and is re-emitted. So the Mac invocation
runs from the seat directory (`cd ~/agents/merge-lane && ...`); run from
elsewhere it watches itself, and it does so silently. The remote target is
not exposed to this: the ssh command runs in ned-box's home directory, which
contains no seat, and this session's transcript is not on that machine.

Exit status, since that is where the family's defects live. The number in a
NOT WATCHING line is proc.wait()'s — the child's own, not a pipeline's. On
--target ned-box it is ssh's, and the line labels it `ssh rc=` for that
reason: ssh passes the remote command's status through, except that it uses
255 for its own failures, so a 255 is ambiguous and the line says so. The
last output line the stream produced is quoted alongside a non-zero status,
because the filter is not a diagnostic channel: a traceback's header matches
`Traceback \\(most recent` but the exception line under it matches nothing,
so without the quote a crash reports only that it crashed.

Usage:
  scripts/watch-agent-dialog-alerts.py --target mac
  scripts/watch-agent-dialog-alerts.py --target ned-box
      [--hold-seconds N] [--retry-seconds N] [--label NAME]
      [--local-dialog-script-path PATH] [--remote-ssh-destination DEST]
      [--remote-dialog-script-path PATH]

Exit codes: 0 clean exit (the consumer closed the pipe), 2 bad invocation,
130 interrupted. It does not otherwise return: a stream that dies is an
event to announce, not a reason to stop watching.
"""

import argparse
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

TARGET_MAC = "mac"
TARGET_NED_BOX = "ned-box"

DEFAULT_HOLD_SECONDS = 300.0
DEFAULT_RETRY_SECONDS = 60.0

# The wrapped program, by absolute path off this file, so the wrapper works
# from any working directory — while the working directory still decides
# which seat the child excludes from its own watch (see the docstring).
DIALOG_SCRIPT_NAME = "watch-agent-dialogs.py"
DEFAULT_REMOTE_SSH_DESTINATION = "nedlern@ned-box"
DEFAULT_REMOTE_DIALOG_SCRIPT_PATH = "~/Projects/nedschorus/scripts/watch-agent-dialogs.py"

# Bounds a dead connection: ssh gives up connecting after 15s, and a TCP
# session that has gone away is noticed within 15 x 4 = 60s rather than
# hanging forever. Both numbers are the ledger's shell watcher's, kept.
# BatchMode means a credential problem fails and says so instead of
# blocking on a prompt no one will answer.
SSH_OPTIONS = (
    "-o", "ConnectTimeout=15",
    "-o", "ServerAliveInterval=15",
    "-o", "ServerAliveCountMax=4",
    "-o", "BatchMode=yes",
)

# Forces a pty for the remote command, which is what makes the remote
# python die when this ssh client does. MEASURED 2026-09-15, both ways, on
# ned-box: without it, interrupting this wrapper left
# `python3 -u ~/Projects/nedschorus/scripts/watch-agent-dialogs.py` running
# there (pid 488363, started at the second the run began, still running
# after the client exited, killed by hand); with it, the remote process was
# present while the stream ran (pid 489200) and gone three seconds after the
# interrupt. Every restart this program makes would otherwise leave another
# one behind, each following the same transcripts and writing to a pipe
# nobody reads. The pty also turns the remote newlines into CRLF, which is
# why the read loop strips both.
#
# Not a hypothetical leak, and not only this program's: at the moment of
# that measurement ned-box was already carrying an ORPHANED dialog watcher
# from the hand-typed shell watcher this wrapper replaces — pid 471948,
# parent pid 1, reparented to systemd when the ssh that started it went
# away an hour earlier, still following the transcripts and still writing
# into a pipe with nothing on the other end.
FORCE_REMOTE_PTY_OPTION = "-tt"

# The ledger's filter, verbatim. Matched case-insensitively, as `grep -iE`
# matched it. See "Known noise" in the docstring for what that costs on OOM.
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

# Added on the remote target only: these can only be ssh speaking, and
# without them a real failure reaches the operator as nothing but the end of
# the stream.
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

# ssh's own code for "I failed", as opposed to a status passed through from
# the remote command. A remote program exiting 255 is indistinguishable, and
# the announcement says so rather than guessing.
SSH_OWN_FAILURE_EXIT_CODE = 255

# ssh's own session-teardown message, which the pty makes it print on every
# remote stream's last breath. MEASURED 2026-09-15: a remote stream that
# died of `ValueError: the remote seats list was empty` announced `last
# output: Connection to 10.0.1.106 closed.` — ssh's closing line had
# displaced the only line saying what went wrong, which is the whole point
# of quoting the last one. Anchored at the start of the line so a seat
# saying the words in a dialog is not mistaken for ssh saying them.
SSH_SESSION_TEARDOWN_PATTERN = re.compile(
    r"^(?:Shared connection|Connection) to \S+ closed\.?$")

LAST_OUTPUT_LINE_SNIPPET_CHARS = 200

# How long a terminated child is given to die before it is killed. It only
# runs on the interrupt path, where the operator is waiting.
CHILD_SHUTDOWN_SECONDS = 5.0

_emit_lock = threading.Lock()


def emit(line):
    """One event, one line, flushed now — a monitor reads this as it
    arrives, and a buffered line is a silent death. Locked because the hold
    timer announces from its own thread."""
    with _emit_lock:
        print(line, flush=True)


def warn(line):
    print(line, file=sys.stderr, flush=True)


def one_line_snippet(text, limit):
    """Newlines folded to " ¶ " first, then the first `limit` characters —
    the same shape as watch-agent-dialogs.py's, so the emitted length is
    bounded by `limit`."""
    return " ¶ ".join(str(text).strip().splitlines())[:limit]


def is_ssh_session_teardown_line(line):
    """True for ssh's own "Connection to <host> closed." — kept out of the
    last-output quote so it cannot displace the line that said why."""
    return bool(SSH_SESSION_TEARDOWN_PATTERN.match(line.strip()))


def alert_patterns_for_target(target):
    """The committed pattern list for one target. The ssh diagnostics are
    on the remote target only: locally nothing can emit them except a seat
    quoting them, which is not an alert."""
    if target == TARGET_NED_BOX:
        return FLEET_ALERT_PATTERNS + SSH_DIAGNOSTIC_PATTERNS
    return FLEET_ALERT_PATTERNS


def compile_alert_filter(target):
    return re.compile("|".join(alert_patterns_for_target(target)), re.IGNORECASE)


def child_command(target, local_dialog_script_path, remote_ssh_destination,
                  remote_dialog_script_path):
    """The argv of one stream attempt.

    `python3 -u` on both sides: a buffered child is a watcher that reports
    an event four kilobytes late, which is its own kind of silence. The
    remote side is a single shell word for ssh to run, so the remote path
    stays ~-relative and is expanded by the remote shell, not this one.
    """
    if target == TARGET_NED_BOX:
        return ["ssh", FORCE_REMOTE_PTY_OPTION, *SSH_OPTIONS,
                remote_ssh_destination,
                f"python3 -u {remote_dialog_script_path}"]
    return [sys.executable, "-u", str(local_dialog_script_path)]


def exit_status_phrase(target, returncode):
    """How a finished attempt's status is said — labelled by whose status it
    actually is, which on the remote target is ssh's."""
    if target != TARGET_NED_BOX:
        return f"{DIALOG_SCRIPT_NAME} rc={returncode}"
    if returncode == SSH_OWN_FAILURE_EXIT_CODE:
        return (f"ssh rc={returncode}, which ssh uses for its own failures, "
                f"so this may be ssh or a remote program that exited 255")
    return f"ssh rc={returncode} (the remote program's own status)"


def attempt_end_detail(target, returncode, last_output_line):
    """The parenthesised detail on a NOT WATCHING line: the status always,
    and the last thing the stream said when that status was not clean —
    because an exception line matches no alert pattern and would otherwise
    be lost with the process that printed it."""
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
    """The watcher's own state, and the only thing that prints about it.

    Three states — unknown, holding, broken — and the rule that only
    transitions speak. `broken` means the stream keeps ending short of the
    hold bar, so events are being missed between attempts; it is announced
    once and then silent.

    The hold bar is crossed while the stream is still up, announced by a
    timer, so that silence after a BROKEN line cannot mean two things. Two
    races between that timer and the attempt's end are closed here, both
    under one lock: an attempt that has already ended never draws a hold
    announcement, and an attempt the timer already declared held is treated
    as held by the end path even if its measured duration lands a hair
    under the bar.
    """

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
        """Caller holds the lock. Announces a restoration only out of the
        broken state — the first hold of a run is what the baseline already
        promised, and saying it again would teach the reader that these
        lines are routine."""
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
        """The timer's callback: this attempt has been up for the hold bar."""
        with self.lock:
            if attempt_id != self.attempt_id or attempt_id == self.ended_attempt:
                return  # a stale or already-finished attempt never speaks
            self._mark_held(attempt_id)

    def attempt_ended(self, attempt_id, duration_seconds, returncode,
                      last_output_line):
        """Announce the end of one attempt. Returns True when the next
        attempt should start immediately (the stream held), False when it
        should wait --retry-seconds (it did not)."""
        with self.lock:
            self.ended_attempt = attempt_id
            detail = attempt_end_detail(self.target, returncode,
                                        last_output_line)
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
        with self.lock:
            self.emit_line(
                f"WATCH {self.label}: NOT WATCHING — this watcher was "
                f"interrupted; nothing is being seen here until it is "
                f"restarted")


def stop_child(process):
    """Used on the interrupt path only: ask, then insist. A child left
    running would hold the transcript files open and, on the remote target,
    leave a python running on ned-box."""
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
    """One attempt: run the dialog stream to its end, printing the lines
    that match. Returns (returncode, last output line).

    The status returned is the child's own, from wait(). This is the
    property the whole file exists for: there is no pipeline here whose
    status could be mistaken for the child's, which is what `rc=$?` after a
    pipe got wrong twice. stderr is merged into stdout — not discarded, as
    both shell watchers discarded it — so the child's own traceback reaches
    the filter that has a pattern for exactly that.
    """
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        # Dialog snippets carry whatever a seat typed; one undecodable byte
        # must not kill the watch.
        errors="replace",
        bufsize=1,
    )
    last_output_line = ""
    try:
        while True:
            raw_line = process.stdout.readline()
            if not raw_line:
                break
            line = raw_line.rstrip("\r\n")
            if not line.strip():
                continue
            if not is_ssh_session_teardown_line(line):
                last_output_line = line
            if alert_filter.search(line):
                emit_line(f"ALERT {label}: {line}")
    except KeyboardInterrupt:
        stop_child(process)
        raise
    finally:
        try:
            process.stdout.close()
        except OSError:
            pass
    # End of stream: the child has closed stdout, so this wait is its exit,
    # not a hang. Nothing is terminated on this path — a child that is on
    # its way out is allowed to finish and report.
    return process.wait(), last_output_line


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        description="Watch the fleet's agent dialogs for alerts, here or on "
                    "ned-box, announcing the baseline and every gap in "
                    "coverage.")
    parser.add_argument("--target", choices=[TARGET_MAC, TARGET_NED_BOX],
                        default=TARGET_MAC,
                        help=f"where the dialog watcher runs: {TARGET_MAC} "
                             f"for this machine (the merge-lane seat's own, "
                             f"hence the name), {TARGET_NED_BOX} for ned-box "
                             f"over ssh (default: {TARGET_MAC})")
    parser.add_argument("--label", default=None,
                        help="name for this watcher in its own lines "
                             "(default: the target)")
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


def main(argv=None):
    arguments = parse_arguments(argv)
    if arguments.hold_seconds <= 0:
        warn("watch-agent-dialog-alerts: --hold-seconds must be > 0")
        return 2
    if arguments.retry_seconds < 0:
        warn("watch-agent-dialog-alerts: --retry-seconds must be >= 0")
        return 2
    if arguments.target == TARGET_NED_BOX and not arguments.remote_ssh_destination.strip():
        warn("watch-agent-dialog-alerts: --remote-ssh-destination is empty")
        return 2
    local_script = Path(arguments.local_dialog_script_path).expanduser()
    if arguments.target == TARGET_MAC and not local_script.is_file():
        warn(f"watch-agent-dialog-alerts: no dialog watcher at {local_script}")
        return 2

    label = arguments.label or arguments.target
    alert_filter = compile_alert_filter(arguments.target)
    command = child_command(arguments.target, local_script,
                            arguments.remote_ssh_destination,
                            arguments.remote_dialog_script_path)
    what_is_run = (str(local_script) if arguments.target == TARGET_MAC
                   else f"{arguments.remote_ssh_destination}:"
                        f"{arguments.remote_dialog_script_path}")

    # Dialog snippets carry whatever a seat typed; never let one
    # unencodable character kill the watch.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    emit(baseline_line(label, arguments.target,
                       len(alert_patterns_for_target(arguments.target)),
                       arguments.hold_seconds, arguments.retry_seconds,
                       what_is_run))

    announcer = StreamCoverageAnnouncer(label, arguments.target,
                                        arguments.hold_seconds,
                                        arguments.retry_seconds)
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
                # Blind for exactly this long, which the announcement above
                # has already said out loud.
                time.sleep(arguments.retry_seconds)
    except KeyboardInterrupt:
        # Say it stopped. A watcher that dies quietly is the failure this
        # program is about, and an interrupt is no exception to it. This
        # covers the retry sleep as well as the stream itself.
        announcer.interrupted()
        return 130


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        # Interrupted before the watch began (argument parsing, the
        # baseline): there is no coverage to announce the loss of.
        sys.exit(130)
    except BrokenPipeError:
        # The consumer closed the pipe; die quietly, not with a traceback.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)
