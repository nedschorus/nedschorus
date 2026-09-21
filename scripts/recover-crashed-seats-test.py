#!/usr/bin/env python3
"""Tests for recover-crashed-seats.py (nedschorus#120).

Every case runs against a sandboxed workspace — throwaway agents root,
handoff directory, and projects root — with tmux and lsof answered by
monkeypatched functions, so no test touches a real seat, server, or
process listing. The launch step is captured, never executed.

The refusal and already-running cases are the script's whole safety story:
it must never act on a live seat, a watched seat, an occupied directory, or
an unprovable answer. The recovery cases prove the 2026-08-21 hand procedure is what
actually runs: newest real transcript wins, empty successors are skipped,
and the resume rides --resume-session-id to the supervisor.

Run: python3 scripts/recover-crashed-seats-test.py
"""

import atexit
import importlib.util
import io
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name("recover-crashed-seats.py")
# The supervisor moved into nc-systems/handoff/ on 2026-09-20 and is no
# longer a sibling of the recovery tool this suite tests.
SUPERVISOR_SCRIPT = (SCRIPT_PATH.resolve().parent.parent
                     / "nc-systems" / "handoff" / "handoff-supervisor.py")

_spec = importlib.util.spec_from_file_location("recover_crashed_seats", SCRIPT_PATH)
recovery = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(recovery)

failures = []
skips = []
passes = []
verdict_reached = False


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
        passes.append(case_name)
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def skip(case_name, reason):
    """A case this machine cannot run, said out loud (nedschorus#172). A
    silent platform guard leaves no FAIL line and no trace that anything was
    left out, which read as a clean run once already: on ned-box the suite
    died at the attached-launcher probe with 55 PASS lines and no verdict,
    and a pull request reported that as "55 pass, 0 fail"."""
    print(f"SKIP  {case_name}: {reason}")
    skips.append(case_name)


def print_verdict():
    """The summary, on EVERY exit path. Registered with atexit so an
    exception that escapes the cases still ends with a verdict line naming
    the run as unfinished, instead of a traceback that leaves the PASS lines
    above it reading as a complete run (nedschorus#172)."""
    counts = (f"{len(passes)} passed, {len(failures)} failed, {len(skips)} skipped"
              f"{' (' + '; '.join(skips) + ')' if skips else ''}")
    print()
    if not verdict_reached:
        print(f"ABORTED before the last case: {counts} so far; this run did not finish")
    elif failures:
        print(f"{len(failures)} case(s) failed: {counts}")
    else:
        print(f"all cases passed: {counts}")


atexit.register(print_verdict)


# The two harness-authored assistant shapes the 2026-09-10 reboot left in its
# successors (measured 2026-09-11): the session-limit notice that was each
# successor's only reply, and the filler a resume of an interrupted session
# appends. Both carry model "<synthetic>".
SESSION_LIMIT_NOTICE_TEXT = "You've hit your session limit · resets 8:50pm (America/Los_Angeles)"
RESUME_FILLER_TEXT = "No response requested."


def write_transcript(directory: Path, session_id: str, first_user_text: str,
                     age_seconds: float = 0.0, records: int = 3,
                     tool_turns: int = 0, synthetic_texts=()):
    """One harness transcript whose first user turn says first_user_text.
    Then one harness-authored assistant turn per synthetic_texts entry,
    records-1 text-bearing assistant turns, then tool_turns assistant turns
    carrying only tool_use blocks (the terse tool-heavy shape, round 3
    finding 2)."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{session_id}.jsonl"
    lines = [json.dumps({"type": "user", "isMeta": False,
                         "message": {"content": first_user_text}})]
    for text in synthetic_texts:
        lines.append(json.dumps({
            "type": "assistant", "isApiErrorMessage": text != RESUME_FILLER_TEXT,
            "message": {"model": "<synthetic>",
                        "content": [{"type": "text", "text": text}]}}))
    for index in range(records - 1):
        lines.append(json.dumps({"type": "assistant",
                                 "message": {"content": f"turn {index}"}}))
    for index in range(tool_turns):
        lines.append(json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": f"tool-{index}", "name": "Bash",
             "input": {"command": "true"}}]}}))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if age_seconds:
        stamp = time.time() - age_seconds
        import os
        os.utime(path, (stamp, stamp))
    return path


class Workspace:
    """A sandboxed seat world, plus captured launches."""

    def __init__(self, root: Path, name="seat-a"):
        self.name = name
        self.agents_root = root / "agents"
        self.handoffs = root / "handoffs"
        self.projects = root / "projects"
        self.seat_directory = self.agents_root / name
        self.seat_directory.mkdir(parents=True)
        self.handoffs.mkdir(parents=True)
        self.projects.mkdir(parents=True)
        self.launches = []

    def project_directory(self) -> Path:
        return recovery.harness_project_directory(self.seat_directory, self.projects)

    def assess(self):
        return recovery.assess_seat(self.name, self.agents_root, self.handoffs,
                                    self.projects)

    def recover(self, dry_run=False, ignite_fallback=False):
        return recovery.recover_seat(self.name, self.agents_root, self.handoffs,
                                     self.projects, dry_run, ignite_fallback)




def real_subprocess_run_help():
    import subprocess
    return subprocess.run(
        [sys.executable, str(SUPERVISOR_SCRIPT), "--help"],
        capture_output=True, text=True).stdout

def patch(monkey_target, value):
    setattr(recovery, monkey_target, value)


def all_dead():
    """Monkeypatch the world to 'seat is fully dead, directory vacant'."""
    patch("tmux_session_alive_anywhere", lambda name: (False, ""))
    patch("seat_directory_occupied",
          lambda directory, apart_from_process_ids=(): (False, ""))
    no_leftover_idle_shell()
    no_operator_terminal()


# The leftover-idle-shell question (user-ruled 2026-09-17). The probes it rests
# on are patched for EVERY case by default, at the bottom of this block, so no
# case reaches a real tmux server or a real terminal through the new path; the
# cases that measure the proof and the question itself put the real ones back.
real_run_tmux = recovery.run_tmux
real_seat_directory_occupied = recovery.seat_directory_occupied
real_processes_rooted_in_seat_directory = recovery.processes_rooted_in_seat_directory
real_tmux_session_is_a_leftover_idle_shell = recovery.tmux_session_is_a_leftover_idle_shell
real_recovery_has_an_operator_terminal = recovery.recovery_has_an_operator_terminal
real_retire_seat_tmux_session = recovery.resupervise.retire_seat_tmux_session
real_resupervise_run_tmux = recovery.resupervise.run_tmux
real_tmux_session_alive_anywhere = recovery.tmux_session_alive_anywhere


def no_leftover_idle_shell(detail="no tmux server holds a session named 'x'"):
    """The proof says 'not shown to be an idle shell' — the answer that leaves
    a live tmux session the refusal it has always been."""
    patch("tmux_session_is_a_leftover_idle_shell",
          lambda name, seat_directory: (False, [], detail))


def a_leftover_idle_shell(pane_process_ids=(4242,), detail="it is one pane at a shell"):
    patch("tmux_session_is_a_leftover_idle_shell",
          lambda name, seat_directory: (True, list(pane_process_ids), detail))


def a_live_tmux_session():
    patch("tmux_session_alive_anywhere",
          lambda name: (True, f"tmux session '{name}' is alive on socket '{name}'"))


def no_operator_terminal():
    patch("recovery_has_an_operator_terminal", lambda: False)


def an_operator_terminal():
    patch("recovery_has_an_operator_terminal", lambda: True)


def capture_retires(retired, killed_sockets=("seat-a",), failure=None,
                    the_session_then_dies=True):
    """Stand in for resupervise-seat.py's retire step, recording each call.
    With the_session_then_dies the tmux probe flips to dead afterwards, as a
    real kill leaves it."""
    def fake_retire(name):
        retired.append(name)
        if failure is None and the_session_then_dies:
            patch("tmux_session_alive_anywhere", lambda name: (False, ""))
        return list(killed_sockets), failure
    recovery.resupervise.retire_seat_tmux_session = fake_retire


def rooted_processes_are(process_ids, unusable_detail=""):
    """The lsof reader answers with exactly these processes rooted in the seat,
    or with None and why it could not be trusted."""
    patch("processes_rooted_in_seat_directory",
          lambda seat_directory, require_a_complete_listing=False:
          (process_ids, unusable_detail))


def lsof_reports_rooted(process_ids):
    """The REAL occupancy check, over an lsof listing naming these processes as
    rooted in the seat — so the pane exemption is measured, not assumed."""
    patch("seat_directory_occupied", real_seat_directory_occupied)
    rooted_processes_are(list(process_ids))


def tmux_server_answers(panes_by_socket, tmux_cannot_be_run=False,
                        list_panes_exit_code=0):
    """run_tmux for the real proof: which sockets hold the seat's session, and
    what `list-panes` prints for each (one "<pane pid>\\t<command>" per line)."""
    class Answer:
        def __init__(self, returncode, stdout=""):
            self.returncode, self.stdout, self.stderr = returncode, stdout, ""

    def fake_run_tmux(*arguments_after_tmux, socket_name=None):
        if tmux_cannot_be_run:
            return None
        if arguments_after_tmux[0] == "has-session":
            return Answer(0 if socket_name in panes_by_socket else 1)
        if arguments_after_tmux[0] == "list-panes":
            if list_panes_exit_code:
                return Answer(list_panes_exit_code)
            return Answer(0, panes_by_socket[socket_name])
        return Answer(1)
    patch("run_tmux", fake_run_tmux)


def recover_with_an_operator_typing(workspace, typed, dry_run=False, ignite_fallback=False):
    """One recovery with an operator at a terminal typing `typed` (None is end
    of input). Returns (report, everything the operator saw)."""
    an_operator_terminal()
    seen = io.StringIO()
    stdin_before = sys.stdin
    sys.stdin = io.StringIO("" if typed is None else f"{typed}\n")
    try:
        with redirect_stdout(seen):
            report = workspace.recover(dry_run=dry_run, ignite_fallback=ignite_fallback)
    finally:
        sys.stdin = stdin_before
    return report, seen.getvalue()


def recover_recording_every_prompt(workspace, dry_run=False, at_a_terminal=True):
    """One recovery with an operator at a terminal who answers yes to anything
    put to him — or, with at_a_terminal False, with nobody at one, and input()
    still answering yes if anything reached it. input() itself is replaced, so
    a question asked by any route is recorded. Returns (report, every prompt
    input() was called with, everything else the operator saw)."""
    if at_a_terminal:
        an_operator_terminal()
    else:
        no_operator_terminal()
    prompts = []

    def input_answering_yes(prompt=""):
        prompts.append(prompt)
        return "y"

    recovery.input = input_answering_yes
    seen = io.StringIO()
    try:
        with redirect_stdout(seen):
            report = workspace.recover(dry_run=dry_run)
    finally:
        del recovery.input
    return report, prompts, seen.getvalue()


no_leftover_idle_shell()
no_operator_terminal()


# The first prompts of a seat brought back after its supervisor recorded its
# agent's exit, spelled out byte for byte rather than derived from the
# function that writes them. Each clause is true wherever it is used: the
# record is described as what it is, the session named is the seat's last,
# only the restart an operator said yes to names the operator, and none says
# crash (review 5240813304 found the by-hand resume starting on the crash
# default).
FIRST_PROMPT_RECORDED_EXIT_SENTENCE = (
    "This seat's supervisor recorded the exit of its last session, as it does when a "
    "session is stopped on purpose, so recovery did not bring the seat back on its own.")
FIRST_PROMPT_FOR_AN_OPERATORS_RESTART_RESUMING = (
    FIRST_PROMPT_RECORDED_EXIT_SENTENCE + " The operator has now restarted the seat, "
    "resuming this conversation. Re-verify any in-flight state before trusting it, then "
    "continue.")
FIRST_PROMPT_FOR_AN_OPERATORS_RESTART_AS_A_FRESH_SESSION = (
    "You are seat-a. " + FIRST_PROMPT_RECORDED_EXIT_SENTENCE + " The operator has now "
    "restarted the seat as a fresh session, so none of that conversation is here. Ask what "
    "to work on.")
FIRST_PROMPT_FOR_A_BY_HAND_RESUME_AFTER_A_RECORDED_EXIT = (
    FIRST_PROMPT_RECORDED_EXIT_SENTENCE + " It has now been restarted by hand, resuming "
    "this conversation. Re-verify any in-flight state before trusting it, then continue.")

# The first prompt of a seat resumed because its supervisor vanished with no
# exit record, spelled out byte for byte. That happens after a crash, but also
# after a reboot, a power cut or a killed tmux server, so it does not say
# "crash" about the session (ruled 2026-09-18, after that day's Mac reboot
# told every seat its session ended in "a crash"). Its opening stays, because
# "resumed by crash recovery" is how EMPTY_SUCCESSOR_MARKERS recognises this
# tool's own earlier resumes.
RESUME_PROMPT_AFTER_A_SESSION_ENDED_WITHOUT_A_HANDOFF = (
    "This session was resumed by crash recovery (nedschorus#120): your previous session "
    "ended without writing a handoff, and your transcript was resumed under a fresh "
    "supervisor. Re-verify any in-flight state before trusting it (files you were "
    "mid-edit in, processes you were watching, messages you were owed), then continue "
    "the work you were doing.")
# The handoff-supervisor's default when it resumes a session and no first
# prompt was given (handoff-supervisor.py, the resume_session_id branch).
# A different sentence from the one above: the supervisor says "the previous
# session", this tool says "your previous session". Compared for EQUALITY at
# P3-4 against the prompt the supervisor actually hands its launch, because
# nothing asserted it until 2026-09-20 and its opening is what
# EMPTY_SUCCESSOR_MARKERS recognises.
SUPERVISOR_DEFAULT_RESUME_PROMPT = (
    "This session was resumed by crash recovery (nedschorus#120): the previous session "
    "ended without writing a handoff. Re-verify in-flight state before trusting it, "
    "then continue the work underway.")


def supervisor_first_turn_for_a_by_hand_command(command, workspace):
    """(prompt, resume) the REAL supervisor's first launch would carry for a
    by-hand command this tool printed. The command's
    LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS and anything after the seat name
    (the launcher's --first-prompt-file) go on the supervisor's argv the way
    both launchers put them there (their suites measure that carriage); the
    supervisor's main then parses them, reads the file, and supervise_sessions
    chooses the prompt. Only the session launch itself is stopped — after the
    supervisor has written the workspace's state file, which clears its exit
    record, so a case must not read that record after calling this."""
    words = shlex.split(command.replace(" (on the Mac)", ""))
    extra_arguments = words[1].split("=", 1)[1]
    supervisor_argv = (["--agent", workspace.name, "--cd", str(workspace.seat_directory),
                        "--agent-command", sys.executable, *words[4:]]
                       + shlex.split(extra_arguments))
    launched = []

    def launch_probe(agent_command, session_id, working_directory, prompt, resume=False,
                     **_):
        launched.append((prompt, resume))
        raise StopIteration()

    sup = recovery.supervisor
    original_launch = sup.launch_agent_session
    original_sync = sup.sync_working_branch_with_main
    try:
        sup.launch_agent_session = launch_probe
        sup.sync_working_branch_with_main = lambda directory: "sync skipped (probe)"
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            try:
                sup.main(supervisor_argv)
            except StopIteration:
                pass
    finally:
        sup.launch_agent_session = original_launch
        sup.sync_working_branch_with_main = original_sync
    return launched[0] if launched else ("", None)


# A seat is already running only when ps confirms a live supervisor of it
# (user-ruled 2026-09-16). These answer the ps probe that
# seat_supervisor_confirmed_by_ps asks, which looks it up when it asks, so
# replacing the module attribute reaches it; the supervisor predicate's own
# default reader is untouched (its docstring's NOTE). Every case that uses one
# puts the real probe back with ps_answers_for_real in a finally.
real_read_process_command_line = recovery.supervisor.read_process_command_line


def ps_confirms_supervisors(seat_supervised_by_process_id):
    """ps answers that each process id given runs the supervisor of the seat
    it maps to, and that no other process id exists."""
    recovery.supervisor.read_process_command_line = lambda process_id: (
        (f"python3 /agents/nc-systems/handoff/handoff-supervisor.py --agent "
         f"{seat_supervised_by_process_id[process_id]} --cd /agents/x", True)
        if process_id in seat_supervised_by_process_id else (None, True))


def ps_cannot_be_run():
    """ps could not be asked at all, as under a fork failure."""
    recovery.supervisor.read_process_command_line = lambda process_id: (None, False)


def ps_answers_for_real():
    recovery.supervisor.read_process_command_line = real_read_process_command_line


real_launch_seat = recovery.launch_seat  # for cases that probe the real one
# capture_launches stubs the come-up check for every launch case, so the cases
# that test the check itself have to put the real one back first.
real_wait_for_the_seat_to_come_up = recovery.wait_for_the_seat_to_come_up


def capture_launches(workspace: Workspace):
    def fake_launch(name, seat_directory, handoff_directory, extra_arguments,
                    first_prompt_file=None):
        workspace.launches.append((name, extra_arguments, first_prompt_file))
        return 0
    patch("launch_seat", fake_launch)
    # Nothing real starts behind a fake launch, so the come-up check (#242
    # change 4) would find no supervisor and every one of these cases would
    # report a seat that did not come up. These cases are about what the report
    # SAYS for a launch that worked, so the seat is stubbed as having come up;
    # the come-up behaviour itself has its own cases below.
    seat_comes_up()


def seat_comes_up(came_up=True, why="a supervisor was still running"):
    patch("wait_for_the_seat_to_come_up",
          lambda name, handoff_directory, **_: (came_up, why))


def a_fake_clock():
    """(monotonic, sleep, elapsed) — a clock that only moves when slept on, so
    the waiter's timing can be driven without the suite waiting for anything."""
    now = [0.0]
    return (lambda: now[0]), (lambda seconds: now.__setitem__(0, now[0] + seconds)), now


def identity_answers(*answers):
    """An identity check that returns each answer in turn, then repeats the last
    — so a case can say 'alive, then dead' and mean it."""
    remaining = list(answers)
    def check(process_id, agent_name):
        alive = remaining.pop(0) if len(remaining) > 1 else remaining[0]
        return alive, ("it is the supervisor" if alive else "it is not a supervisor")
    return check


def identity_answers_recording_when_asked(monotonic, *answers):
    """(check, asked_at) — identity_answers, plus the fake clock's reading at
    every call. The ORDER of the waiter's two waits is only visible from inside
    it: reading the clock after it returns sees one total, which cannot tell a
    settle placed before the first-sighting loop from one placed after it."""
    answering = identity_answers(*answers)
    asked_at = []

    def check_recording_when_asked(process_id, agent_name):
        asked_at.append(monotonic())
        return answering(process_id, agent_name)

    return check_recording_when_asked, asked_at


def run_came_up_cases(root: Path):
    """nedschorus#242 change 4: a launch exiting zero says the launcher ran, not
    that the seat came back. A resume whose session dies inside Claude leaves the
    launcher exiting zero while the supervisor starts, sees the session end with
    no handoff, and stops — reported as success, that tells an absent operator
    the fleet is back when it is not."""
    patch("wait_for_the_seat_to_come_up", real_wait_for_the_seat_to_come_up)
    handoffs = root / "came-up" / "handoffs"
    handoffs.mkdir(parents=True)
    lock_path = handoffs / "seat-a-supervisor.lock"
    lock_path.write_text("4321\n", encoding="utf-8")

    check("the settle is derived from the supervisor's own poll interval",
          recovery.SEAT_SETTLE_SECONDS == 3 * recovery.supervisor.HANDOFF_POLL_SECONDS
          and recovery.SEAT_SETTLE_SECONDS > recovery.supervisor.HANDOFF_POLL_SECONDS,
          recovery.SEAT_SETTLE_SECONDS)

    monotonic, sleep, elapsed = a_fake_clock()
    came_up, why = recovery.wait_for_the_seat_to_come_up(
        "seat-a", handoffs, identity_check=identity_answers(True),
        sleep=sleep, monotonic=monotonic)
    check("a supervisor that starts and survives the settle came up", came_up, why)
    check("and the settle was actually waited out",
          elapsed[0] >= recovery.SEAT_SETTLE_SECONDS, elapsed[0])

    # That case reads the clock only after the call, so it sees a total and
    # nothing about ORDER. Measured: moving the settle before the first-sighting
    # loop, keeping the recheck, left every case in this suite passing. The
    # order is the design point — the settle is measured from FIRST SIGHTING,
    # never from the launch — so it is pinned from inside, by an identity check
    # that records the clock at every call (PR #329 review, finding 3).
    monotonic, sleep, _ = a_fake_clock()
    identity_check, asked_at = identity_answers_recording_when_asked(monotonic, True)
    came_up, why = recovery.wait_for_the_seat_to_come_up(
        "seat-a", handoffs, identity_check=identity_check,
        sleep=sleep, monotonic=monotonic)
    check("the first sighting is taken before any settle is waited out",
          came_up and asked_at[0] == 0.0, (asked_at, why))
    check("and the recheck comes a whole settle after that first sighting",
          len(asked_at) == 2
          and asked_at[1] >= asked_at[0] + recovery.SEAT_SETTLE_SECONDS,
          asked_at)

    # The same ordering where it discriminates: a supervisor sixty polls late.
    # A settle measured from the LAUNCH is long spent by then, so it would
    # recheck at once; measured from first sighting it cannot.
    monotonic, sleep, _ = a_fake_clock()
    identity_check, asked_at = identity_answers_recording_when_asked(
        monotonic, *([False] * 60 + [True]))
    came_up, why = recovery.wait_for_the_seat_to_come_up(
        "seat-a", handoffs, identity_check=identity_check,
        sleep=sleep, monotonic=monotonic)
    first_sighting = 60 * recovery.SEAT_COMES_UP_POLL_SECONDS
    check("a supervisor sixty polls late settles from when IT appeared, not from the launch",
          came_up and len(asked_at) == 62 and asked_at[60] == first_sighting
          and asked_at[61] >= first_sighting + recovery.SEAT_SETTLE_SECONDS,
          (asked_at[59:], why))

    # THE CASE THAT DISCRIMINATES a settle from a single check. A supervisor
    # whose session has already died still holds its lock for up to
    # HANDOFF_POLL_SECONDS, so checking once when it first appears calls that
    # coming up. It is the exact failure #242 change 4 names.
    monotonic, sleep, _ = a_fake_clock()
    came_up, why = recovery.wait_for_the_seat_to_come_up(
        "seat-a", handoffs, identity_check=identity_answers(True, False),
        sleep=sleep, monotonic=monotonic)
    check("a supervisor that starts and stops again did NOT come up", not came_up, why)
    check("and it says the session did not survive, not that nothing started",
          "did not survive" in why, why)

    monotonic, sleep, elapsed = a_fake_clock()
    came_up, why = recovery.wait_for_the_seat_to_come_up(
        "seat-a", handoffs, identity_check=identity_answers(False),
        sleep=sleep, monotonic=monotonic)
    check("a supervisor that never appears did not come up", not came_up, why)
    check("and it says how long it waited", "no supervisor appeared within" in why, why)
    check("and it waited the whole deadline before saying so",
          elapsed[0] >= recovery.SEAT_COMES_UP_DEADLINE_SECONDS, elapsed[0])

    # The window path's shape: this script waits only for the opener, so the
    # launcher — and its Claude update step — runs after the launch returns. A
    # supervisor appearing long after the launch is normal there, not a failure.
    monotonic, sleep, _ = a_fake_clock()
    late = [False] * 60 + [True]
    came_up, why = recovery.wait_for_the_seat_to_come_up(
        "seat-a", handoffs, identity_check=identity_answers(*late),
        sleep=sleep, monotonic=monotonic)
    check("a supervisor that appears long after the launch still came up", came_up, why)

    missing_lock = root / "came-up" / "no-lock"
    missing_lock.mkdir(parents=True)
    monotonic, sleep, _ = a_fake_clock()
    came_up, why = recovery.wait_for_the_seat_to_come_up(
        "seat-a", missing_lock, identity_check=identity_answers(True),
        sleep=sleep, monotonic=monotonic)
    check("with no lock to read, nothing came up and the lock is named",
          not came_up and "supervisor lock" in why, why)

    # The reports. The waiter has its own cases above, driven by a fake clock;
    # these are about what the report SAYS, so the waiter is stubbed here. The
    # real one would find no lock and spend SEAT_COMES_UP_DEADLINE_SECONDS twice
    # — 240 real seconds to check two strings, which is what it cost before this
    # was noticed. A resume or a plain relaunch that did not come up names the
    # degraded restart; the ignite paths do not, because that is what just ran.
    did_not_survive = "a supervisor started and stopped again within 6s"
    seat_comes_up(False, did_not_survive)
    for offer, expected in ((True, True), (False, False)):
        report = recovery.came_up_or_failure_report("seat-a", missing_lock, offer)
        check(f"a seat that did not come up reports it (offer={offer})",
              report is not None and "LAUNCHED BUT DID NOT COME UP" in report
              and "relaunched" not in report, report)
        check(f"and names --ignite-fallback only when there is one to offer (offer={offer})",
              ("--ignite-fallback" in report) == expected, report)
        # The seam the slow version implied but never asserted: the report says
        # what the waiter found, rather than composing a reason of its own.
        check(f"and it carries the waiter's reason verbatim (offer={offer})",
              did_not_survive in report, report)

    seat_comes_up()
    check("a seat that came up reports nothing, leaving the success report alone",
          recovery.came_up_or_failure_report("seat-a", missing_lock, True) is None)


with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)

    # --- refusals, and seats already running ---------------------------------
    # A seat found running is not refused (user-ruled 2026-09-16, on the
    # question PR #426's reviewer asked): it is its own verdict, and is still
    # never touched. Found running means a live supervisor of it confirmed by
    # ps (user-ruled 2026-09-16, PR #426 review): an attached launch leaves its
    # tmux session alive at a shell after the supervisor exits, so a live
    # session alone refuses.
    workspace = Workspace(root / "w1")
    patch("tmux_session_alive_anywhere",
          lambda name: (True, f"tmux session '{name}' is alive on socket '{name}'"))
    verdict, detail = workspace.assess()
    check("a live tmux session with no supervisor of the seat refuses (per-seat socket)",
          verdict == "refuse" and "never touches a live tmux session" in detail
          and "no live supervisor of this seat is confirmed" in detail, (verdict, detail))
    w1_lock_path = workspace.handoffs / f"{workspace.name}-supervisor.lock"
    w1_lock_path.write_text("4321\n", encoding="utf-8")
    try:
        ps_confirms_supervisors({4321: workspace.name})
        verdict, detail = workspace.assess()
        check("a live tmux session with a confirmed supervisor of the seat is already running",
              verdict == "seat-already-running" and "never touches live seats" in detail
              and f"process 4321 is the supervisor of {workspace.name}" in detail,
              (verdict, detail))
        ps_confirms_supervisors({4321: "some-other-seat"})
        verdict, detail = workspace.assess()
        check("a live tmux session whose lock holder supervises another seat refuses",
              verdict == "refuse" and "never touches a live tmux session" in detail,
              (verdict, detail))
    finally:
        ps_answers_for_real()
        w1_lock_path.unlink()

    patch("tmux_session_alive_anywhere", lambda name: (False, ""))
    state_path = workspace.handoffs / f"{workspace.name}-supervisor-state.json"
    state_path.write_text(json.dumps({
        "session_id": "x", "generation": 1,
        "last_poll_at": datetime.now(timezone.utc).isoformat(),
    }), encoding="utf-8")
    verdict, detail = workspace.assess()
    # Changed with nedschorus#242 change 1. A heartbeat stamped a moment ago
    # with no supervisor process behind it is the 60-second hole this tool used
    # to fall into: measured on ned-box, it refused a crashed seat until 60
    # seconds after the kill, and the login restart of #116 was predicted to
    # land inside that window on a fast enough boot. The heartbeat no
    # longer decides; the supervisor's process does, and there is none here.
    check("a fresh heartbeat alone no longer refuses, with no supervisor process behind it",
          verdict != "refuse", (verdict, detail))
    state_path.unlink()

    patch("seat_directory_occupied",
          lambda directory, apart_from_process_ids=(): (True, f"a live process is rooted in {directory}"))
    verdict, detail = workspace.assess()
    check("an occupied seat directory refuses",
          verdict == "refuse" and "live process" in detail, (verdict, detail))

    patch("seat_directory_occupied",
          lambda directory, apart_from_process_ids=(): (True, "lsof is not installed, so the seat cannot be proven vacant"))
    verdict, detail = workspace.assess()
    check("an unprovable vacancy answer refuses (fail closed)",
          verdict == "refuse" and "cannot be proven" in detail, (verdict, detail))

    workspace_missing = Workspace(root / "w2", name="seat-b")
    all_dead()
    verdict, detail = recovery.assess_seat("no-such-seat", workspace_missing.agents_root,
                                           workspace_missing.handoffs,
                                           workspace_missing.projects)
    check("a seat with no home directory refuses",
          verdict == "refuse" and "no seat directory" in detail, (verdict, detail))

    # --- defer to boot-ignition when a handoff genuinely waits --------------
    workspace = Workspace(root / "w3")
    all_dead()
    (workspace.handoffs / f"{workspace.name}-handoff.md").write_text(
        "# Handoff\nrestart-counter: 5\nnext-step: continue\n", encoding="utf-8")
    verdict, detail = workspace.assess()
    check("an unconsumed handoff defers to the supervisor's boot-ignition",
          verdict == "defer-to-boot-ignition" and "counter 5" in detail,
          (verdict, detail))

    state_path = workspace.handoffs / f"{workspace.name}-supervisor-state.json"
    state_path.write_text(json.dumps({"consumed_counter": 5}), encoding="utf-8")
    write_transcript(workspace.project_directory(), "real-session", "do the work", records=4)
    verdict, detail = workspace.assess()
    check("a consumed handoff does not defer; the transcript resume proceeds",
          verdict == "resume" and detail[0] == "real-session", (verdict, detail))

    # --- a waiting handoff that asks to be consulted (nedschorus#350) --------
    # User-ruled 2026-09-17: launch nothing. A launch let the supervisor stop at
    # once, and this tool then waited out its deadline and offered the forced
    # restart the seat had declined.
    consulted_handoff_text = (
        "# Handoff\nrestart-counter: 11\nnext-step: wait for the user\n"
        "dont-restart: the user asked to be consulted before a relaunch\n")
    workspace = Workspace(root / "w3-consulted", name="seat-consulted")
    all_dead()
    (workspace.handoffs / f"{workspace.name}-handoff.md").write_text(
        consulted_handoff_text, encoding="utf-8")
    verdict, detail = workspace.assess()
    check("an unconsumed handoff that asks to be consulted is not deferred to a launch",
          verdict == "seat-asked-to-be-consulted"
          and detail == (11, "the user asked to be consulted before a relaunch"),
          (verdict, detail))

    # --- transcript selection ----------------------------------------------
    workspace = Workspace(root / "w4")
    all_dead()
    write_transcript(workspace.project_directory(), "old-real",
                     "start the build", age_seconds=3600)
    write_transcript(workspace.project_directory(), "empty-successor",
                     "You are seat-a. No handoff exists yet; ask what to work on.",
                     records=2)  # died at its first reply: under the turn minimum
    verdict, detail = workspace.assess()
    check("an empty-successor transcript never shadows the real one",
          verdict == "resume" and detail[0] == "old-real", (verdict, detail))

    workspace = Workspace(root / "w5")
    all_dead()
    write_transcript(workspace.project_directory(), "older-real", "first stint",
                     age_seconds=7200)
    write_transcript(workspace.project_directory(), "newer-real", "second stint",
                     age_seconds=60)
    verdict, detail = workspace.assess()
    check("the newest real transcript wins",
          verdict == "resume" and detail[0] == "newer-real", (verdict, detail))

    workspace = Workspace(root / "w6")
    all_dead()
    write_transcript(workspace.project_directory(), "empty-only",
                     "You are seat-a. No handoff exists yet; ask what to work on.",
                     records=1)  # never replied at all
    verdict, detail = workspace.assess()
    check("only empty successors on disk routes to ignite, not resume",
          verdict == "ignite" and "nothing worth resuming" in detail, (verdict, detail))

    workspace = Workspace(root / "w7")
    all_dead()
    verdict, detail = workspace.assess()
    check("no transcripts at all routes to ignite",
          verdict == "ignite" and "no harness project directory" in detail,
          (verdict, detail))

    # Caught live 2026-08-22: a seat's FIRST session legitimately starts with
    # the no-handoff prompt and then does real work — the marker alone must
    # not write it off. Size decides: big-with-marker resumes.
    workspace = Workspace(root / "w7b")
    all_dead()
    big = write_transcript(workspace.project_directory(), "first-ever-session",
                           "You are seat-a. No handoff exists yet; ask what to work on.")
    big.write_text(big.read_text() +
                   ("\n" + json.dumps({"type": "assistant",
                                        "message": {"content": "x" * 400}})) * 300,
                   encoding="utf-8")
    verdict, detail = workspace.assess()
    check("a LARGE transcript that began with the no-handoff prompt still resumes",
          verdict == "resume" and detail[0] == "first-ever-session",
          (verdict, detail))

    # --- recovery actions ---------------------------------------------------
    workspace = Workspace(root / "w8")
    all_dead()
    write_transcript(workspace.project_directory(), "crashed-session", "real work",
                     records=6)
    capture_launches(workspace)
    report = workspace.recover(dry_run=True)
    check("dry-run resumes nothing and names the session",
          "would resume session crashed-session" in report and not workspace.launches,
          (report, workspace.launches))
    report = workspace.recover()
    check("the resume launch rides --resume-session-id to the supervisor",
          workspace.launches
          and shlex.split(workspace.launches[0][1])
              == ["--resume-session-id", "crashed-session"],
          workspace.launches)
    check("the resume report names the session and its size",
          "resuming crashed-session" in report and "KB transcript" in report, report)

    workspace = Workspace(root / "w9")
    all_dead()
    write_transcript(workspace.project_directory(), "crashed-session", "real work")
    (workspace.handoffs / f"{workspace.name}-dialog-0007.md").write_text(
        "the dialog extract", encoding="utf-8")
    capture_launches(workspace)
    report = workspace.recover(ignite_fallback=True)
    check("--ignite-fallback launches fresh reading the newest extract",
          workspace.launches and workspace.launches[0][1] == ""
          and workspace.launches[0][2] is not None
          and "igniting from seat-a-dialog-0007.md" in report,
          (report, workspace.launches))
    prompt_text = workspace.launches[0][2].read_text(encoding="utf-8")
    check("the recovery's initial agent instructions name the extract, the missing handoff, and #120",
          "seat-a-dialog-0007.md" in prompt_text and "ended without writing a handoff" in prompt_text
          and "nedschorus#120" in prompt_text, prompt_text)

    workspace = Workspace(root / "w10")
    all_dead()
    (workspace.handoffs / f"{workspace.name}-handoff.md").write_text(
        "# Handoff\nrestart-counter: 9\nnext-step: go\n", encoding="utf-8")
    capture_launches(workspace)
    report = workspace.recover()
    check("the defer path relaunches plain (no extra supervisor arguments)",
          workspace.launches and workspace.launches[0][1] == ""
          and workspace.launches[0][2] is None and "relaunched plain" in report,
          (report, workspace.launches))

    workspace = Workspace(root / "w10-consulted", name="seat-consulted")
    all_dead()
    consulted_handoff_path = workspace.handoffs / f"{workspace.name}-handoff.md"
    consulted_handoff_path.write_text(consulted_handoff_text, encoding="utf-8")
    capture_launches(workspace)
    waited = []
    patch("wait_for_the_seat_to_come_up",
          lambda *a, **k: (waited.append(1), (True, "x"))[1])
    for dry_run in (False, True):
        report = workspace.recover(dry_run=dry_run)
        check(f"a seat that asked to be consulted is reported, and nothing is launched, "
              f"waited for, or offered (dry run: {dry_run})",
              report.startswith(f"{workspace.name}: "
                                f"{recovery.SEAT_ASKED_TO_BE_CONSULTED_REPORT_MARKER} — ")
              and not workspace.launches and not waited
              and "--ignite-fallback" not in report,
              (report, workspace.launches, waited))
        # Composed in recover_seat since the verdict's detail became (counter,
        # reason); the line is the one assess_seat used to compose, byte for byte.
        check(f"and its line is unchanged, byte for byte (dry run: {dry_run})",
              report == (
                  "seat-consulted: NOT RELAUNCHED, AT ITS OWN REQUEST — an unconsumed "
                  "handoff (counter 11) asks to be consulted before a relaunch: the user "
                  "asked to be consulted before a relaunch. Nothing was launched. To bring "
                  "it back, launch it by hand (launch-claude-mac seat-consulted or "
                  "launch-claude-ubuntu seat-consulted) and answer its supervisor's restart "
                  "question"),
              report)
    check("and its handoff is left unconsumed, for its supervisor's own restart question",
          consulted_handoff_path.read_text(encoding="utf-8") == consulted_handoff_text
          and not (workspace.handoffs / f"{workspace.name}-supervisor-state.json").exists(),
          sorted(path.name for path in workspace.handoffs.iterdir()))
    seat_comes_up()

    # --- the supervisor's --resume-session-id flag --------------------------
    supervisor_spec = importlib.util.spec_from_file_location(
        "handoff_supervisor_under_test", SUPERVISOR_SCRIPT)
    supervisor_module = importlib.util.module_from_spec(supervisor_spec)
    supervisor_spec.loader.exec_module(supervisor_module)

    launched = []
    class FakeProcess:
        pass
    def fake_popen(argv, cwd=None, env=None):
        launched.append((argv, cwd, (env or {}).get("NEDSCHORUS_HANDOFF_SUPERVISOR_SESSION_ID")))
        return FakeProcess()
    # supervisor_module.subprocess IS the shared subprocess module: patch the
    # attribute and restore it, or every later real_subprocess.run breaks.
    real_popen = supervisor_module.subprocess.Popen
    try:
        supervisor_module.subprocess.Popen = fake_popen
        supervisor_module.launch_agent_session("claude", "abc-123", Path("/tmp"),
                                               "the prompt", resume=True)
        check("supervisor resume launch uses --resume, not --session-id",
              launched and launched[0][0] == ["claude", "--resume", "abc-123", "the prompt"],
              launched)
        # The handoff writer honours the seat's name and directory only in the
        # session whose CLAUDE_CODE_SESSION_ID is this id; a resumed session
        # keeps the id it resumes (PR #414 review, 2026-09-16).
        check("supervisor resume launch tells the session the id it resumes",
              launched and launched[0][2] == "abc-123", launched)
        launched.clear()
        supervisor_module.launch_agent_session("claude", "abc-123", Path("/tmp"),
                                               "the prompt")
        check("supervisor plain launch still uses --session-id",
              launched and launched[0][0] == ["claude", "--session-id", "abc-123", "the prompt"],
              launched)
        check("supervisor plain launch tells the session the id it launches",
              launched and launched[0][2] == "abc-123", launched)
        launched.clear()
        # nedschorus#142 lane: a seat launched with its own name pins the title
        # it answers to across machines, and turns Remote Control on so it is
        # reachable at all. The name sits before the prompt positional.
        supervisor_module.launch_agent_session("claude", "abc-123", Path("/tmp"),
                                               "the prompt", remote_control_name="prof")
        check("supervisor launch names the seat for cross-machine messaging",
              launched and launched[0][0] == ["claude", "--session-id", "abc-123",
                                              "--remote-control", "prof", "the prompt"],
              launched)
    finally:
        supervisor_module.subprocess.Popen = real_popen

    # --- PR #131 review round: the fix-round regressions --------------------

    # F1: an unanswerable tmux axis refuses (fail closed, like lsof).
    workspace = Workspace(root / "r1")
    patch("tmux_session_alive_anywhere",
          lambda name: (None, "tmux cannot be run here, so seat liveness cannot be "
                              "checked — refusing rather than guessing"))
    patch("seat_directory_occupied",
          lambda directory, apart_from_process_ids=(): (False, ""))
    verdict, detail = workspace.assess()
    check("F1: tmux unanswerable refuses instead of reading as dead",
          verdict == "refuse" and "cannot be checked" in detail, (verdict, detail))

    # F1: a failing launch is reported and counted, not claimed as success.
    workspace = Workspace(root / "r2")
    all_dead()
    write_transcript(workspace.project_directory(), "real-work", "do things", records=5)
    def failing_launch(name, seat_directory, handoff_directory, extra,
                       first_prompt_file=None):
        workspace.launches.append((name, extra, first_prompt_file))
        return 2
    patch("launch_seat", failing_launch)
    report = workspace.recover()
    check("F1: a failed launch reports LAUNCH FAILED, never 'relaunched'",
          "LAUNCH FAILED (exit 2)" in report and "relaunched" not in report, report)

    # F2: the resume launch carries the crash-recovery prompt file.
    workspace = Workspace(root / "r3")
    all_dead()
    write_transcript(workspace.project_directory(), "real-work", "do things", records=5)
    capture_launches(workspace)
    workspace.recover()
    check("F2: the resume launch passes a first-prompt file",
          workspace.launches and workspace.launches[0][2] is not None,
          workspace.launches)
    resume_prompt = workspace.launches[0][2].read_text(encoding="utf-8")
    check("F2: the resume prompt says the session ended without a handoff and to re-verify, "
          "not ask-for-work",
          "ended without writing a handoff" in resume_prompt
          and "Re-verify" in resume_prompt
          and "No handoff exists yet" not in resume_prompt, resume_prompt)
    check("F2: the resume prompt is exactly the ruled text, and says nothing of a crash "
          "(ruled 2026-09-18)",
          resume_prompt == RESUME_PROMPT_AFTER_A_SESSION_ENDED_WITHOUT_A_HANDOFF
          and "a crash" not in resume_prompt, resume_prompt)
    check("F2: an EMPTY_SUCCESSOR_MARKERS entry still recognises the resume prompt",
          any(marker in resume_prompt for marker in recovery.EMPTY_SUCCESSOR_MARKERS),
          (resume_prompt, recovery.EMPTY_SUCCESSOR_MARKERS))

    # F3: recovery's own fresh-session shapes are skipped when small and workless...
    workspace = Workspace(root / "r4")
    all_dead()
    write_transcript(workspace.project_directory(), "pre-crash-real", "real work",
                     age_seconds=3600, records=6)
    write_transcript(workspace.project_directory(), "failed-ignition",
                     "Read x-dialog-0004.md (crash recovery, nedschorus#120). Continue.",
                     records=1)  # died before working
    verdict, detail = workspace.assess()
    check("F3/R4: a failed-ignition successor that died before working is skipped",
          verdict == "resume" and detail[0] == "pre-crash-real", (verdict, detail))

    workspace = Workspace(root / "r5")
    all_dead()
    write_transcript(workspace.project_directory(), "pre-crash-real", "real work",
                     age_seconds=3600, records=6)
    empty = workspace.project_directory() / "zero-byte.jsonl"
    empty.write_text("", encoding="utf-8")
    verdict, detail = workspace.assess()
    check("F3: a 0-byte transcript never shadows the pre-crash transcript",
          verdict == "resume" and detail[0] == "pre-crash-real", (verdict, detail))

    workspace = Workspace(root / "r6")
    all_dead()
    write_transcript(workspace.project_directory(), "pre-crash-real", "real work",
                     age_seconds=3600, records=6)
    # The PRE-2026-08-30 opener shape, kept deliberately: transcripts written
    # before the wariness template sit on disk and must still match the
    # shortened marker. The post-change shape is covered at P2 below.
    # Reversed 2026-09-11 (the 2026-09-10 reboot, nedschorus#116): the
    # supervisor composes this opener only after marking its handoff
    # consumed, so the transcript beside it is a retired parent, and the
    # successor is resumed even when it never worked.
    ignition_shape = write_transcript(
        workspace.project_directory(), "supervisor-ignition",
        "Read /x/y-dialog-0002.md — it is the dialog from the session you are "
        "continuing, written 0 minutes ago.", records=1)  # died before working
    verdict, detail = workspace.assess()
    check("F3/P2: a pre-2026-08-30 reincarnation successor that never worked is resumed",
          verdict == "resume" and detail[0] == "supervisor-ignition", (verdict, detail))

    # F8: every cross-file literal the filter relies on is asserted against
    # the supervisor's actual source, so a wording change there fails HERE
    # (round-3 P3-3: the round-2 assertion covered only the first marker).
    source = SUPERVISOR_SCRIPT.read_text(encoding="utf-8")
    check("F8: the no-handoff marker is verbatim in handoff-supervisor.py",
          "No handoff exists yet" in source
          and "No handoff exists yet" in recovery.EMPTY_SUCCESSOR_MARKERS,
          recovery.EMPTY_SUCCESSOR_MARKERS)
    check("F8: the ignition-opener literal is verbatim in handoff-supervisor.py",
          recovery.REINCARNATION_OPENER_MARKER in source
          and recovery.REINCARNATION_OPENER_MARKER
              == "the dialog from the session you are continuing",
          "opener literal missing from supervisor source, or the marker changed")
    check("F8: the reincarnation opener is not a skip marker (2026-09-10 reboot)",
          recovery.REINCARNATION_OPENER_MARKER not in recovery.EMPTY_SUCCESSOR_MARKERS,
          recovery.EMPTY_SUCCESSOR_MARKERS)

    # Q2: an unparseable handoff counter refuses with both paths named.
    workspace = Workspace(root / "r7")
    all_dead()
    (workspace.handoffs / f"{workspace.name}-handoff.md").write_text(
        "# Handoff\nrestart-counter: not-a-number\nnext-step: x\n", encoding="utf-8")
    verdict, detail = workspace.assess()
    check("Q2: an unreadable restart-counter refuses, naming fix and delete paths",
          verdict == "refuse" and "restart-counter" in detail
          and "delete it" in detail, (verdict, detail))

    # Q3: a supervisor lock held by a live supervisor stops the recovery: the
    # seat is already running (user-ruled 2026-09-16; it was a refusal before).
    workspace = Workspace(root / "r8")
    all_dead()
    lock_path = workspace.handoffs / f"{workspace.name}-supervisor.lock"
    stub_directory = root / "r8-looks-like-a-supervisor"
    stub_directory.mkdir(parents=True, exist_ok=True)
    stub = stub_directory / "handoff-supervisor.py"
    stub.write_text("import time\ntime.sleep(120)\n", encoding="utf-8")
    holder = subprocess.Popen(  # pylint: disable=consider-using-with
        [sys.executable, str(stub), "--agent", workspace.name, "--cd", str(stub_directory)])
    try:
        lock_path.write_text(f"{holder.pid}\n", encoding="utf-8")
        verdict, detail = workspace.assess()
        check("Q3: a supervisor lock held by a live supervisor is already running",
              verdict == "seat-already-running" and "supervisor lock" in detail,
              (verdict, detail))
        report = workspace.recover()
        check("Q3: and it is reported ALREADY RUNNING, not REFUSED",
              report.startswith(f"{workspace.name}: ALREADY RUNNING — the supervisor lock")
              and "REFUSED" not in report, report)
    finally:
        holder.kill()
        holder.wait()

    # Changed with nedschorus#242 change 1: the lock file outlives a reboot and
    # process ids are reused across it, so a live id that is NOT this seat's
    # supervisor must not block the recovery the login restart just asked for.
    unrelated = subprocess.Popen(  # pylint: disable=consider-using-with
        [sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        lock_path.write_text(f"{unrelated.pid}\n", encoding="utf-8")
        write_transcript(workspace.project_directory(), "real", "work", records=4)
        verdict, detail = workspace.assess()
        check("Q3: a lock whose id is live but not this seat's supervisor does not block",
              verdict == "resume", (verdict, detail))
    finally:
        unrelated.kill()
        unrelated.wait()

    lock_path.write_text("999999999\n", encoding="utf-8")
    verdict, detail = workspace.assess()
    check("Q3: a stale lock (dead pid) does not block recovery",
          verdict == "resume", (verdict, detail))

    # nedschorus#346 item 1: the two answers process_is_supervisor_for_agent
    # gives when ps cannot be asked (PR #328), each pinned through assess_seat.
    # The predicate's ps reader is a default argument bound at definition, so
    # patching the module attribute would not reach it (its docstring says so);
    # instead ps is made unaskable the way it really fails — no such program on
    # PATH — so the real read_process_command_line returns (None, False). Both
    # cases and their precondition run inside the same hijack.
    empty_path_directory = root / "r8-no-ps-on-path"
    empty_path_directory.mkdir(parents=True, exist_ok=True)
    real_path = os.environ["PATH"]
    os.environ["PATH"] = str(empty_path_directory)
    try:
        # Without this line the dead-pid case below passes whether or not ps was
        # asked — resume either way — so it would test nothing the moment the
        # reader learned an absolute path to ps.
        check("#346: with no ps on PATH the reader answers 'could not be asked'",
              recovery.supervisor.read_process_command_line(os.getpid()) == (None, False),
              recovery.supervisor.read_process_command_line(os.getpid()))

        # Answer 1: ps could not be asked and os.kill says no such process —
        # the lock is stale, and recovery proceeds exactly as with a working ps.
        lock_path.write_text("999999999\n", encoding="utf-8")
        verdict, detail = workspace.assess()
        check("#346: unknown ps, pid does not exist: the stale lock does not block",
              verdict == "resume", (verdict, detail))

        # Answer 2: ps could not be asked and a process with that id exists —
        # this very interpreter, which is certainly not a supervisor. With ps
        # working, Q3 above proves such a lock does not block; without it the
        # predicate assumes a supervisor rather than risk a second one, and
        # assess_seat launches nothing. It refuses: an assumed supervisor is
        # not a seat found running, so it is not the seat-already-running
        # verdict Q3's confirmed supervisor gets (user-ruled 2026-09-16, PR #426
        # review 5228492424). The detail keeps the predicate's assumption
        # wording, because its promise is that the detail SAYS it is an
        # assumption rather than pretending to certainty.
        lock_path.write_text(f"{os.getpid()}\n", encoding="utf-8")
        operator_line = io.StringIO()
        with redirect_stderr(operator_line):
            verdict, detail = workspace.assess()
        check("#346: unknown ps, pid exists: refuses, not already running, and the detail "
              "says ps could not confirm the assumed supervisor",
              verdict == "refuse" and "supervisor lock" in detail
              and "ps could not confirm it is a supervisor of this seat" in detail
              and "ps could not be run" in detail and "assumed present" in detail,
              (verdict, detail))
        check("#346: unknown ps, pid exists: the operator line on stderr names the seat",
              f"supervisor of {workspace.name}" in operator_line.getvalue()
              and "ps could not be run" in operator_line.getvalue(),
              operator_line.getvalue())
    finally:
        os.environ["PATH"] = real_path

    # F4: the supervisor's resume path consumes a stale handoff instead of
    # letting the wait loop kill the resumed session. Proven through the
    # boot-sequence branch in supervise_sessions via source inspection plus
    # the flag's help text; the live-loop probe belongs to the reviewer's
    # harness and stays there.
    help_text = " ".join(real_subprocess_run_help().split())
    check("F4: --resume-session-id help states the handoff-consumption rule",
          "marked consumed" in help_text
          and "chooses the transcript over any waiting handoff" in help_text,
          help_text[:300])

    # F4 behavioral: drive supervise_sessions far enough to prove a stale
    # handoff is consume-marked BEFORE the resume launch, so the wait loop
    # cannot kill the resumed session for it. The fake launch records the
    # state file's counter at launch time, then raises to stop the loop.
    workspace = Workspace(root / "r9")
    state_seen_at_launch = {}
    class StopLoop(Exception):
        pass
    # Mirrors launch_agent_session's signature exactly, on purpose: a stub with
    # **kwargs would swallow a signature change instead of failing here, and
    # this probe exists to assert what the supervisor passes at launch.
    def probe_launch(agent_command, session_id, working_directory, prompt, resume=False,
                     remote_control_name="", appended_system_prompt_file="",
                     handoff_supervisor_agent_name=""):
        state_seen_at_launch.update(json.loads(
            (workspace.handoffs / "seat-a-supervisor-state.json").read_text()))
        state_seen_at_launch["resume_flag"] = resume
        raise StopLoop()
    (workspace.handoffs / "seat-a-handoff.md").write_text(
        "# Handoff\nrestart-counter: 7\nnext-step: stale\n", encoding="utf-8")
    sup = supervisor_module
    original_launch = sup.launch_agent_session
    original_sync = sup.sync_working_branch_with_main
    try:
        sup.launch_agent_session = probe_launch
        sup.sync_working_branch_with_main = lambda d: "sync skipped (probe)"
        settings = sup.SupervisorSettings(
            agent="seat-a", working_directory=workspace.seat_directory,
            handoff_directory=workspace.handoffs, agent_command="claude",
            first_prompt="", resume_session_id="resume-me")
        try:
            sup.supervise_sessions(settings)
        except StopLoop:
            pass
    finally:
        sup.launch_agent_session = original_launch
        sup.sync_working_branch_with_main = original_sync
    check("F4: a stale handoff is consume-marked before the resume launch",
          state_seen_at_launch.get("consumed_counter") == 7
          and state_seen_at_launch.get("resume_flag") is True,
          state_seen_at_launch)

    # Round 3 P1: an underscore-named seat's transcripts are FOUND — the
    # mangling is the harness's (every non-alphanumeric becomes a dash),
    # delegated to watch-agent-dialogs' probe-verified rule.
    workspace = Workspace(root / "r10", name="under_score_seat")
    all_dead()
    mangled = recovery.harness_project_directory(workspace.seat_directory,
                                                 workspace.projects)
    check("P1: underscore in the seat path mangles to a dash (harness rule)",
          "under-score-seat" in mangled.name and "_" not in mangled.name,
          mangled.name)
    write_transcript(mangled, "underscore-real", "real work here", records=6)
    verdict, detail = workspace.assess()
    check("P1: an underscore-named seat's intact transcript is found and resumed",
          verdict == "resume" and detail[0] == "underscore-real", (verdict, detail))

    # Round 3 P2: a reincarnated successor that crashed AFTER doing real work is
    # resumed, not skipped for its handed-off parent. Its second half — one
    # that died before doing anything was skipped for the parent — was
    # reversed 2026-09-11 after the 2026-09-10 Mac reboot (nedschorus#116,
    # comment of 2026-09-11): the parent had handed off, so it is retired, and
    # resuming it would have told it that it "died without writing a handoff".
    # Both under 100KB.
    # The opener is the post-2026-08-30 shape the supervisor now composes —
    # written-at stamp, gap computed by the reader from `date`, the wariness
    # tail cut and the open-walks duty added in the user's second round the
    # same day — so the marker match against the CURRENT template is what
    # these cases prove (the pre-change shape is covered at F3/P2 above).
    ignition_opener = (
        "Read /x/seat-a-dialog-0003.md — the dialog from the session you are "
        "continuing, written at 2026-08-28T12:00:00Z. Calculate from `date` "
        "how long ago that was, and be wary of obsolescence and drift in "
        "everything in this handoff in proportion to that gap. This handoff "
        "should list what items or walks are open. Display them to the user, "
        "and continue them when you get a chance.")
    workspace = Workspace(root / "r11")
    all_dead()
    write_transcript(workspace.project_directory(), "generation-3-handed-off",
                     "older real work", age_seconds=7200, records=8)
    write_transcript(workspace.project_directory(), "generation-4-crashed",
                     ignition_opener, records=9)  # 8 assistant turns: real work
    verdict, detail = workspace.assess()
    check("P2: a crashed reincarnated successor WITH real work is resumed, not its parent",
          verdict == "resume" and detail[0] == "generation-4-crashed",
          (verdict, detail))

    workspace = Workspace(root / "r12")
    all_dead()
    write_transcript(workspace.project_directory(), "generation-3-handed-off",
                     "older real work", age_seconds=7200, records=8)
    write_transcript(workspace.project_directory(), "generation-4-stillborn",
                     ignition_opener, records=1)  # no assistant turns at all
    verdict, detail = workspace.assess()
    check("P2: a reincarnated successor that died before working is resumed, not its retired parent",
          verdict == "resume" and detail[0] == "generation-4-stillborn",
          (verdict, detail))

    # P3-4: the supervisor's own default prompt on a resume launch is the
    # truthful crash-recovery text, not ask-for-work.
    launched_prompts = []
    # Mirrors launch_agent_session's signature exactly; see probe_launch above.
    def prompt_probe(agent_command, session_id, working_directory, prompt, resume=False,
                     remote_control_name="", appended_system_prompt_file="",
                     handoff_supervisor_agent_name=""):
        launched_prompts.append((prompt, resume))
        raise StopIteration()
    sup = supervisor_module
    original_launch2 = sup.launch_agent_session
    original_sync2 = sup.sync_working_branch_with_main
    try:
        sup.launch_agent_session = prompt_probe
        sup.sync_working_branch_with_main = lambda d: "sync skipped (probe)"
        ws = Workspace(root / "r13")
        settings = sup.SupervisorSettings(
            agent="seat-a", working_directory=ws.seat_directory,
            handoff_directory=ws.handoffs, agent_command="claude",
            first_prompt="", resume_session_id="resume-me")
        try:
            sup.supervise_sessions(settings)
        except StopIteration:
            pass
    finally:
        sup.launch_agent_session = original_launch2
        sup.sync_working_branch_with_main = original_sync2
    check("P3-4: a by-hand resume launch defaults to the crash-recovery prompt",
          launched_prompts and launched_prompts[0][1] is True
          and "resumed by crash recovery" in launched_prompts[0][0]
          and "No handoff exists yet" not in launched_prompts[0][0],
          launched_prompts)
    # P3-4: and that default is pinned word for word, which no suite did until
    # 2026-09-20 (found by merge-lane-e2). It matters because its opening is an
    # EMPTY_SUCCESSOR_MARKERS entry: reword it and a supervisor-resumed
    # successor that never worked stops being recognised as workless, so
    # recovery passes it over for its retired parent — the failure of the
    # 2026-09-10 Mac reboot (nedschorus#116, comment of 2026-09-11). Pinned
    # against the prompt the probe caught the supervisor handing its launch —
    # not against handoff-supervisor.py's source, and never against the
    # constant these compare to, which would assert the test against itself.
    # Equality with what the program produced is the form of this assertion
    # that a reword and an addition to the prompt both fail.
    launched_prompt = launched_prompts[0][0] if launched_prompts else None
    check("P3-4: the supervisor's default resume prompt is verbatim what it launches",
          launched_prompt == SUPERVISOR_DEFAULT_RESUME_PROMPT,
          launched_prompt)
    check("P3-4: the supervisor's default resume prompt carries a skip marker",
          launched_prompt is not None
          and any(marker in launched_prompt
                  for marker in recovery.EMPTY_SUCCESSOR_MARKERS),
          (launched_prompt, recovery.EMPTY_SUCCESSOR_MARKERS))
    check("P3-4: the supervisor's default resume prompt says the session ended, "
          "never that it died (ruled 2026-09-19)",
          launched_prompt is not None
          and "ended without writing a handoff" in launched_prompt
          and "died" not in launched_prompt,
          launched_prompt)

    # --- PR #131 review round 4 --------------------------------------------

    # Round 4 finding 1: the turn gate covers EVERY marker, not only the
    # reincarnation opener — the reviewer measured markers 1 and 2 skipping real
    # work on size alone. Same shape as the accepted round-3 P2 cases: small
    # transcript, 8 text-bearing assistant turns, beside an older parent.
    workspace = Workspace(root / "r14")
    all_dead()
    write_transcript(workspace.project_directory(), "handed-off-parent",
                     "older real work", age_seconds=7200, records=8)
    write_transcript(workspace.project_directory(), "first-ever-crashed",
                     "You are seat-a. No handoff exists yet; ask what to work on.",
                     records=9)  # 8 assistant turns: real work
    verdict, detail = workspace.assess()
    check("R4-1: a small first-ever session WITH real work is resumed, not its parent",
          verdict == "resume" and detail[0] == "first-ever-crashed",
          (verdict, detail))

    workspace = Workspace(root / "r15")
    all_dead()
    write_transcript(workspace.project_directory(), "handed-off-parent",
                     "older real work", age_seconds=7200, records=8)
    write_transcript(workspace.project_directory(), "ignition-then-crashed",
                     "Read x-dialog-0004.md (crash recovery, nedschorus#120). Continue.",
                     records=9)  # the --ignite-fallback loop the reviewer named
    verdict, detail = workspace.assess()
    check("R4-1: an ignite-fallback successor WITH real work is resumed, not its parent",
          verdict == "resume" and detail[0] == "ignition-then-crashed",
          (verdict, detail))

    # Round 4 finding 2: tool_use-only assistant turns are work. The
    # reviewer's shapes: 12 tool-only turns and no text reply, and the same
    # with one text reply — both were skipped for the parent before.
    workspace = Workspace(root / "r16")
    all_dead()
    write_transcript(workspace.project_directory(), "handed-off-parent",
                     "older real work", age_seconds=7200, records=8)
    tool_heavy = write_transcript(
        workspace.project_directory(), "tool-heavy-crashed", ignition_opener,
        records=1, tool_turns=12)  # no text replies at all, 12 tool calls
    check("R4-2: substantive_turn_count counts tool_use-only turns",
          recovery.substantive_turn_count(tool_heavy) == 12,
          recovery.substantive_turn_count(tool_heavy))
    verdict, detail = workspace.assess()
    check("R4-2: a terse tool-heavy successor is resumed, not its parent",
          verdict == "resume" and detail[0] == "tool-heavy-crashed",
          (verdict, detail))

    # --- the 2026-09-10 Mac reboot (nedschorus#116, comment of 2026-09-11) ---
    # Two seats handed off at 20:09 PDT; each successor's only reply was the
    # harness's session-limit notice, and the Mac rebooted at 22:07. The dry
    # run the next morning chose each seat's retired parent, and would have
    # told it that it "died without writing a handoff". The shape exactly: a
    # consumed handoff, a successor holding the reincarnation opener and one
    # synthetic notice, and the older parent beside it.
    workspace = Workspace(root / "r23")
    all_dead()
    (workspace.handoffs / f"{workspace.name}-handoff.md").write_text(
        "# Handoff\nrestart-counter: 16\nnext-step: continue\n", encoding="utf-8")
    (workspace.handoffs / f"{workspace.name}-supervisor-state.json").write_text(
        json.dumps({"consumed_counter": 16,
                    "session_id": "successor-hit-session-limit",
                    "generation": 16}), encoding="utf-8")
    write_transcript(workspace.project_directory(), "handed-off-parent",
                     "older real work", age_seconds=7200, records=8)
    write_transcript(workspace.project_directory(), "successor-hit-session-limit",
                     ignition_opener, records=1,
                     synthetic_texts=(SESSION_LIMIT_NOTICE_TEXT,))
    verdict, detail = workspace.assess()
    check("REBOOT-0910: the successor that never replied is resumed, not its retired parent",
          verdict == "resume" and detail[0] == "successor-hit-session-limit",
          (verdict, detail))
    dry_report = workspace.recover(dry_run=True)
    check("REBOOT-0910: the dry run names the successor and says it never replied",
          "would resume session successor-hit-session-limit" in dry_report
          and "never replied" in dry_report, dry_report)
    capture_launches(workspace)
    report = workspace.recover()
    check("REBOOT-0910: the launch resumes the successor, and the report says it never replied",
          workspace.launches
          and "--resume-session-id successor-hit-session-limit" in workspace.launches[0][1]
          and "never replied" in report, (workspace.launches, report))
    unreplied_prompt = (workspace.launches[0][2].read_text(encoding="utf-8")
                        if workspace.launches and workspace.launches[0][2] else "")
    check("REBOOT-0910: the resume prompt says the first reply never happened, not a crash",
          "first reply never happened" in unreplied_prompt
          and "first prompt above" in unreplied_prompt
          and "ended without writing a handoff" not in unreplied_prompt,
          unreplied_prompt)

    # Harness-authored turns are not work. Counted, the notice made the
    # successor above look half-working, and the filler a resume appends
    # makes any resumed successor look as if it replied.
    synthetic_only = write_transcript(
        root / "r24-transcripts", "synthetic-turns-only", ignition_opener,
        records=1, synthetic_texts=(SESSION_LIMIT_NOTICE_TEXT, RESUME_FILLER_TEXT))
    check("REBOOT-0910: substantive_turn_count ignores the harness's <synthetic> turns",
          recovery.substantive_turn_count(synthetic_only) == 0,
          recovery.substantive_turn_count(synthetic_only))

    # The 2026-08-21 shape keeps its skip: a plain relaunch's no-handoff
    # session beside a crashed parent that did real work. Two notices must not
    # read as two turns of work (merge-lane and reboot-test each carried
    # several notices on 2026-09-10).
    workspace = Workspace(root / "r25")
    all_dead()
    write_transcript(workspace.project_directory(), "pre-crash-real", "real work",
                     age_seconds=3600, records=6)
    write_transcript(workspace.project_directory(), "no-handoff-stillborn",
                     "You are seat-a. No handoff exists yet; ask what to work on.",
                     records=1, synthetic_texts=(SESSION_LIMIT_NOTICE_TEXT,
                                                 SESSION_LIMIT_NOTICE_TEXT))
    verdict, detail = workspace.assess()
    check("REBOOT-0910: a no-handoff session with two notices is still skipped for the pre-crash one",
          verdict == "resume" and detail[0] == "pre-crash-real", (verdict, detail))

    # A successor that was resumed after the notice, worked, and then crashed
    # is an ordinary crash: it gets the crash prompt, not the never-replied one.
    workspace = Workspace(root / "r26")
    all_dead()
    write_transcript(workspace.project_directory(), "handed-off-parent",
                     "older real work", age_seconds=7200, records=8)
    write_transcript(workspace.project_directory(), "resumed-successor-then-crashed",
                     ignition_opener, records=6,
                     synthetic_texts=(SESSION_LIMIT_NOTICE_TEXT, RESUME_FILLER_TEXT))
    capture_launches(workspace)
    report = workspace.recover()
    crash_prompt = (workspace.launches[0][2].read_text(encoding="utf-8")
                    if workspace.launches and workspace.launches[0][2] else "")
    check("REBOOT-0910: a successor that worked after its resume gets the crash prompt",
          "relaunched resuming resumed-successor-then-crashed" in report
          and "never replied" not in report
          and crash_prompt == RESUME_PROMPT_AFTER_A_SESSION_ENDED_WITHOUT_A_HANDOFF
          and "first reply never happened" not in crash_prompt,
          (report, crash_prompt))

    # PR review of 7e33908, finding 1: the supervisor's other ignition shape,
    # a boot that found an unconsumed handoff but no dialog to extract
    # (fired four times on this Mac, 2026-08-16/17). Composed through the
    # supervisor's own plan, so a wording change there fails here.
    boot_recovery_prompt = supervisor_module.BootRecoveryIgnitionPlan(
        "Finish the walk.").compose("")
    workspace = Workspace(root / "r27")
    all_dead()
    write_transcript(workspace.project_directory(), "boot-recovery-successor",
                     boot_recovery_prompt, records=1,
                     synthetic_texts=(SESSION_LIMIT_NOTICE_TEXT,))
    capture_launches(workspace)
    report = workspace.recover()
    boot_prompt_sent = (workspace.launches[0][2].read_text(encoding="utf-8")
                        if workspace.launches and workspace.launches[0][2] else "")
    check("REVIEW-1: a boot-recovery successor that never replied gets the never-replied prompt",
          "relaunched resuming boot-recovery-successor" in report
          and "never replied" in report
          and "first reply never happened" in boot_prompt_sent,
          (report, boot_prompt_sent))

    # Finding 2: the opener counts only where the supervisor puts it, at the
    # start of the first turn. A hand-written brief that quotes it (this
    # seat's own first brief, 2026-09-11) is not a handoff successor.
    dialog_prompt = supervisor_module.build_ignition_prompt(
        Path("/x/seat-a-dialog-0016.md"), {"written-at": "2026-09-11T03:09:55Z"})
    composed = write_transcript(root / "r28-transcripts", "composed-opener",
                                dialog_prompt, records=1)
    quoted = write_transcript(
        root / "r28-transcripts", "brief-quoting-opener",
        "# a first brief\n\nThe successor's opener carries \"the dialog from "
        "the session you are continuing\".", records=1)
    check("REVIEW-2: the supervisor's composed dialog opener is recognized",
          recovery.is_unreplied_reincarnation_successor(composed),
          dialog_prompt[:120])
    check("REVIEW-2: a brief that only quotes the opener is not a handoff successor",
          not recovery.is_unreplied_reincarnation_successor(quoted))

    # --- recover into a window (nedschorus#242 change 6, #116 build step 3) --
    # --open-iterm-window-per-seat launches the seat ATTACHED in its own iTerm
    # window, through open-iterm-window-running-command. The trap the design
    # names: the window's process is a child of iTerm, not of this script, so
    # the supervisor arguments cannot ride the environment — they are encoded
    # into the command text, `/usr/bin/env 'NAME=value' <launcher> <seat>`.
    window_launches, detached_launches = [], []
    def capture_window_launch(name, seat_directory, handoff_directory,
                              extra_arguments, first_prompt_file=None):
        window_launches.append((name, extra_arguments, first_prompt_file))
        return 0
    def capture_detached_launch(name, seat_directory, handoff_directory,
                                extra_arguments, first_prompt_file=None):
        detached_launches.append((name, extra_arguments, first_prompt_file))
        return 0
    real_open_seat_in_iterm_window = recovery.open_seat_in_iterm_window
    real_launcher_path = recovery.launcher_path

    workspace = Workspace(root / "window-command-text")
    prompt_file = workspace.handoffs / f"{workspace.name}-resume-recovery-prompt.md"
    try:
        recovery.launcher_path = lambda: Path("/fake/scripts/launch-claude-mac")
        command_text = recovery.iterm_window_command_text(
            workspace.name, workspace.seat_directory, workspace.handoffs,
            "--resume-session-id abc-123", first_prompt_file=prompt_file)
    finally:
        recovery.launcher_path = real_launcher_path
    # iTerm2 splits its command shell-style, one level of quoting; shlex.split
    # reads it the same way for text with no backslash or double quote.
    check("WINDOW: the command text carries the supervisor arguments and agents root",
          shlex.split(command_text) == [
              "/usr/bin/env",
              f"LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS=--handoff-dir "
              f"{workspace.handoffs} --resume-session-id abc-123",
              f"NEDSCHORUS_AGENTS_ROOT={workspace.agents_root}",
              "/fake/scripts/launch-claude-mac", workspace.name,
              "--first-prompt-file", str(prompt_file)],
          command_text)
    check("WINDOW: the seat is launched attached, not --no-attach",
          "--no-attach" not in command_text, command_text)

    # The real opener accepts the text: its dry-run seam prints the AppleScript
    # it would run, and refuses a command it could not deliver intact.
    import subprocess as real_subprocess_for_window
    opener = SCRIPT_PATH.with_name("open-iterm-window-running-command")
    opened = real_subprocess_for_window.run(
        [str(opener), command_text], capture_output=True, text=True,
        env={**os.environ, "OPEN_ITERM_WINDOW_DRY_RUN": "1"})
    check("WINDOW: open-iterm-window-running-command accepts the command text",
          opened.returncode == 0
          and "create window with default profile command" in opened.stdout
          and "--resume-session-id abc-123" in opened.stdout,
          (opened.returncode, opened.stdout, opened.stderr))

    # open_seat_in_iterm_window hands that text, as one argument, to the opener.
    captured_window_run = []
    def capture_window_subprocess_run(command, check=False):
        captured_window_run.append(command)
        class Done:
            returncode = 0
        return Done()
    real_run = recovery.subprocess.run
    try:
        recovery.subprocess.run = capture_window_subprocess_run
        recovery.launcher_path = lambda: Path("/fake/scripts/launch-claude-mac")
        exit_code = recovery.open_seat_in_iterm_window(
            workspace.name, workspace.seat_directory, workspace.handoffs,
            "--resume-session-id abc-123", first_prompt_file=prompt_file)
    finally:
        recovery.subprocess.run = real_run
        recovery.launcher_path = real_launcher_path
    check("WINDOW: the opener gets the whole command as one argument",
          exit_code == 0 and len(captured_window_run) == 1
          and Path(captured_window_run[0][0]).name == "open-iterm-window-running-command"
          and Path(captured_window_run[0][0]).is_absolute()
          and captured_window_run[0][1:] == [command_text],
          captured_window_run)

    # Through recover_seat: every launching path opens a window instead of
    # the detached launch.
    try:
        patch("open_seat_in_iterm_window", capture_window_launch)
        patch("launch_seat", capture_detached_launch)

        workspace = Workspace(root / "window-resume")
        all_dead()
        write_transcript(workspace.project_directory(), "resume-in-window",
                         "real work", records=5)
        report = recovery.recover_seat(workspace.name, workspace.agents_root,
                                       workspace.handoffs, workspace.projects,
                                       False, False, open_iterm_window=True)
        check("WINDOW: a resume opens a window carrying --resume-session-id",
              window_launches
              and window_launches[-1][1] == "--resume-session-id resume-in-window"
              and window_launches[-1][2] is not None
              and "relaunched resuming resume-in-window" in report
              and "iTerm window" in report and not detached_launches,
              (window_launches, detached_launches, report))

        dry_report = recovery.recover_seat(workspace.name, workspace.agents_root,
                                           workspace.handoffs, workspace.projects,
                                           True, False, open_iterm_window=True)
        check("WINDOW: --dry-run prints the window command and opens nothing",
              len(window_launches) == 1
              and "would open an iTerm window running:" in dry_report
              and "--resume-session-id resume-in-window" in dry_report
              and "resume-recovery-prompt.md" in dry_report,
              dry_report)

        workspace = Workspace(root / "window-ignite")
        all_dead()
        write_transcript(workspace.project_directory(), "resume-in-window",
                         "real work", records=5)
        (workspace.handoffs / f"{workspace.name}-dialog-0004.md").write_text(
            "dialog", encoding="utf-8")
        report = recovery.recover_seat(workspace.name, workspace.agents_root,
                                       workspace.handoffs, workspace.projects,
                                       False, True, open_iterm_window=True)
        check("WINDOW: --ignite-fallback opens the window fresh, reading the extract",
              window_launches[-1][1] == ""
              and window_launches[-1][2] is not None
              and window_launches[-1][2].name == f"{workspace.name}-recovery-ignition-prompt.md"
              and "iTerm window" in report and not detached_launches,
              (window_launches[-1], report))

        workspace = Workspace(root / "window-defer")
        all_dead()
        (workspace.handoffs / f"{workspace.name}-handoff.md").write_text(
            "# Handoff\nrestart-counter: 5\nnext-step: continue\n", encoding="utf-8")
        report = recovery.recover_seat(workspace.name, workspace.agents_root,
                                       workspace.handoffs, workspace.projects,
                                       False, False, open_iterm_window=True)
        check("WINDOW: a waiting handoff opens a plain window for boot-ignition",
              window_launches[-1][1] == "" and window_launches[-1][2] is None
              and "relaunched plain" in report and "iTerm window" in report
              and not detached_launches,
              (window_launches[-1], report))

        # main(): the flag reaches recover_seat, and is refused where it
        # cannot work.
        workspace = Workspace(root / "window-main")
        all_dead()
        write_transcript(workspace.project_directory(), "main-window",
                         "real work", records=5)
        recovery.launcher_path = lambda: Path("/fake/scripts/launch-claude-mac")
        exit_code = recovery.main([workspace.name, "--open-iterm-window-per-seat",
                                   "--agents-root", str(workspace.agents_root),
                                   "--handoff-dir", str(workspace.handoffs),
                                   "--projects-root", str(workspace.projects)])
        check("WINDOW: main passes --open-iterm-window-per-seat through",
              exit_code == 0
              and window_launches[-1][1] == "--resume-session-id main-window",
              window_launches[-1])

        # The Ubuntu box is headless and has no iTerm2 or launch-claude-mac:
        # refused with the reason, never silently downgraded to detached.
        recovery.launcher_path = lambda: None
        errors = io.StringIO()
        with redirect_stderr(errors):
            try:
                exit_code = recovery.main([workspace.name, "--open-iterm-window-per-seat",
                                           "--agents-root", str(workspace.agents_root),
                                           "--handoff-dir", str(workspace.handoffs),
                                           "--projects-root", str(workspace.projects)])
            except SystemExit as stop_request:
                exit_code = stop_request.code
        check("WINDOW: refused off macOS, with the reason",
              exit_code == 2 and "macOS" in errors.getvalue(),
              (exit_code, errors.getvalue()))

        # iTerm2's parser takes one level of quoting and has no POSIX '\''
        # escape (measured 2026-09-02, open-iterm-window-running-command), so
        # a path holding an apostrophe cannot be carried into the window. The
        # suite's own apostrophe workspace (r21, PR #134 round 2) is that path.
        recovery.launcher_path = lambda: Path("/fake/scripts/launch-claude-mac")
        apostrophe_handoffs = root / "agent's window handoffs"
        errors = io.StringIO()
        launches_before = len(window_launches)
        with redirect_stderr(errors):
            try:
                exit_code = recovery.main([workspace.name, "--open-iterm-window-per-seat",
                                           "--agents-root", str(workspace.agents_root),
                                           "--handoff-dir", str(apostrophe_handoffs),
                                           "--projects-root", str(workspace.projects)])
            except SystemExit as stop_request:
                exit_code = stop_request.code
        check("WINDOW: a path with an apostrophe is refused before anything launches",
              exit_code == 2 and "agent's window handoffs" in errors.getvalue()
              and len(window_launches) == launches_before,
              (exit_code, errors.getvalue()))
    finally:
        recovery.launcher_path = real_launcher_path
        patch("open_seat_in_iterm_window", real_open_seat_in_iterm_window)

    # Review of e55904d, finding 1: a handoff directory holding a SPACE is
    # shell-quoted into the supervisor arguments (shlex.quote), and the single
    # quotes it adds are exactly what iTerm2 cannot carry. The refusal must
    # catch it up front: composing anyway raised from inside the composer,
    # which under --all aborts every seat after it, logs nothing, and leaves
    # the written resume prompt behind with no window. Paths of this class are
    # already in this suite (r21's "agent's r21", PR #134's apostrophe
    # handoff directory).
    workspace = Workspace(root / "window-space-handoff-dir")
    all_dead()
    write_transcript(workspace.project_directory(), "space-dir-resume",
                     "real work", records=5)
    spaced_handoffs = root / "window handoffs with spaces"
    spaced_handoffs.mkdir(parents=True, exist_ok=True)
    window_launches.clear()
    errors = io.StringIO()
    try:
        recovery.launcher_path = lambda: Path("/fake/scripts/launch-claude-mac")
        patch("open_seat_in_iterm_window", capture_window_launch)
        with redirect_stderr(errors):
            try:
                exit_code = recovery.main([workspace.name, "--open-iterm-window-per-seat",
                                           "--agents-root", str(workspace.agents_root),
                                           "--handoff-dir", str(spaced_handoffs),
                                           "--projects-root", str(workspace.projects)])
            except SystemExit as stop_request:
                exit_code = stop_request.code
            except ValueError as raised:
                exit_code = f"ValueError: {raised}"
    finally:
        recovery.launcher_path = real_launcher_path
        patch("open_seat_in_iterm_window", real_open_seat_in_iterm_window)
    check("WINDOW: a handoff directory needing shell quoting is refused up front",
          exit_code == 2 and "window handoffs with spaces" in errors.getvalue()
          and not window_launches
          and not list(spaced_handoffs.glob("*-resume-recovery-prompt.md")),
          (exit_code, errors.getvalue(), window_launches))

    # The agents root and the launcher path keep the apostrophe rule, and are
    # refused through main() the same way. Covered here because the handoff
    # directory moved to its own check above, and nothing else exercised this
    # loop (review of dd4df6a, the coverage gap it left).
    workspace = Workspace(root / "window-apostrophe-paths")
    all_dead()
    write_transcript(workspace.project_directory(), "apostrophe-path-resume",
                     "real work", records=5)
    for label, agents_root_argument, launcher in (
            ("the agents root", str(root / "agent's agents"),
             Path("/fake/scripts/launch-claude-mac")),
            ("the launcher path", str(workspace.agents_root),
             Path("/fake/agent's scripts/launch-claude-mac"))):
        window_launches.clear()
        errors = io.StringIO()
        try:
            recovery.launcher_path = lambda pinned=launcher: pinned
            patch("open_seat_in_iterm_window", capture_window_launch)
            with redirect_stderr(errors):
                try:
                    exit_code = recovery.main([workspace.name, "--open-iterm-window-per-seat",
                                               "--agents-root", agents_root_argument,
                                               "--handoff-dir", str(workspace.handoffs),
                                               "--projects-root", str(workspace.projects)])
                except SystemExit as stop_request:
                    exit_code = stop_request.code
                except ValueError as raised:
                    exit_code = f"ValueError: {raised}"
        finally:
            recovery.launcher_path = real_launcher_path
            patch("open_seat_in_iterm_window", real_open_seat_in_iterm_window)
        check(f"WINDOW: an apostrophe in {label} is refused up front",
              exit_code == 2 and "apostrophe" in errors.getvalue()
              and not window_launches,
              (exit_code, errors.getvalue(), window_launches))

    # A space elsewhere is carried, not refused: the reviewer measured the
    # agents root, launcher path and prompt file arriving intact through the
    # opener's AppleScript, the login shell and into the launcher, because
    # those are whole words this composer quotes itself.
    workspace = Workspace(root / "window space agents root")
    all_dead()
    write_transcript(workspace.project_directory(), "space-root-resume",
                     "real work", records=5)
    plain_handoffs = root / "window-plain-handoffs"
    plain_handoffs.mkdir(parents=True, exist_ok=True)
    try:
        recovery.launcher_path = lambda: Path("/fake/scripts/launch-claude-mac")
        report = recovery.recover_seat(workspace.name, workspace.agents_root,
                                       plain_handoffs, workspace.projects,
                                       True, False, open_iterm_window=True)
    finally:
        recovery.launcher_path = real_launcher_path
    check("WINDOW: a space in the agents root is carried into the command, not refused",
          f"'NEDSCHORUS_AGENTS_ROOT={workspace.agents_root}'" in report, report)

    # --dry-run promises to change nothing: no prompt file, no window.
    workspace = Workspace(root / "window-dry-run-changes-nothing")
    all_dead()
    write_transcript(workspace.project_directory(), "dry-run-resume",
                     "real work", records=5)
    (workspace.handoffs / f"{workspace.name}-dialog-0002.md").write_text(
        "dialog", encoding="utf-8")
    before = sorted(path.name for path in workspace.handoffs.iterdir())
    window_launches.clear()
    detached_launches.clear()
    try:
        recovery.launcher_path = lambda: Path("/fake/scripts/launch-claude-mac")
        patch("open_seat_in_iterm_window", capture_window_launch)
        patch("launch_seat", capture_detached_launch)
        for fallback in (False, True):
            recovery.recover_seat(workspace.name, workspace.agents_root,
                                  workspace.handoffs, workspace.projects,
                                  True, fallback, open_iterm_window=True)
    finally:
        recovery.launcher_path = real_launcher_path
        patch("open_seat_in_iterm_window", real_open_seat_in_iterm_window)
    check("WINDOW: --dry-run writes no prompt file and opens no window",
          sorted(path.name for path in workspace.handoffs.iterdir()) == before
          and not window_launches and not detached_launches,
          (before, sorted(path.name for path in workspace.handoffs.iterdir()),
           window_launches, detached_launches))

    # The opener's exit code is the seat's: a window that could not be opened
    # is reported, never claimed as a recovery.
    def failing_window_subprocess_run(command, check=False):
        class Done:
            returncode = 3
        return Done()
    workspace = Workspace(root / "window-opener-fails")
    all_dead()
    write_transcript(workspace.project_directory(), "opener-fails-resume",
                     "real work", records=5)
    try:
        recovery.subprocess.run = failing_window_subprocess_run
        recovery.launcher_path = lambda: Path("/fake/scripts/launch-claude-mac")
        report = recovery.recover_seat(workspace.name, workspace.agents_root,
                                       workspace.handoffs, workspace.projects,
                                       False, False, open_iterm_window=True)
    finally:
        recovery.subprocess.run = real_run
        recovery.launcher_path = real_launcher_path
    check("WINDOW: a failing opener reports LAUNCH FAILED, never 'relaunched'",
          "LAUNCH FAILED (exit 3)" in report and "relaunched" not in report, report)

    # An iTerm window's command starts in / with a bare PATH, and this script
    # is normally run by a relative path (`python3 scripts/...`), so both the
    # launcher and the opener must be absolutized rather than inherited from
    # __file__ as given.
    if sys.platform == "darwin":
        real_module_file = recovery.__file__
        captured_window_run.clear()
        try:
            recovery.__file__ = "scripts/recover-crashed-seats.py"
            recovery.subprocess.run = capture_window_subprocess_run
            launcher_from_relative = recovery.launcher_path()
            recovery.open_seat_in_iterm_window(workspace.name, workspace.seat_directory,
                                               workspace.handoffs, "")
        finally:
            recovery.__file__ = real_module_file
            recovery.subprocess.run = real_run
        check("WINDOW: launcher and opener stay absolute when the script is run by a relative path",
              launcher_from_relative.is_absolute()
              and captured_window_run
              and Path(captured_window_run[-1][0]).is_absolute()
              and str(launcher_from_relative) in captured_window_run[-1][1],
              (launcher_from_relative,
               captured_window_run[-1] if captured_window_run else None))
    else:
        skip("WINDOW: launcher and opener stay absolute when the script is run by a relative path",
             "macOS only: launcher_path() is None off macOS and the iTerm opener is Mac-side")

    # Round 4 codex finding A (handoff dir) and finding B (agents root):
    # probed through the REAL launch_seat on the launcher branch, in codex's
    # own scenario — the defer path with an override handoff directory.
    workspace = Workspace(root / "r17")
    all_dead()
    (workspace.handoffs / f"{workspace.name}-handoff.md").write_text(
        "# Handoff\nrestart-counter: 3\nnext-step: go\n", encoding="utf-8")
    captured_run = {}
    def capture_subprocess_run(command, env=None, check=False):
        captured_run["command"] = command
        captured_run["env"] = env
        class Done:
            returncode = 0
        return Done()
    real_run = recovery.subprocess.run
    real_launcher_path = recovery.launcher_path
    try:
        patch("launch_seat", real_launch_seat)
        recovery.subprocess.run = capture_subprocess_run
        recovery.launcher_path = lambda: Path("/fake/launch-claude-mac")
        report = workspace.recover()
    finally:
        recovery.subprocess.run = real_run
        recovery.launcher_path = real_launcher_path
    supervisor_arguments = captured_run["env"].get(
        "LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS", "")
    # Assertions parse the composed string the way the launch shell will
    # (shlex.split), instead of matching hand-written quotes — the quoting
    # itself is under test since PR #134's review finding 1.
    check("A: the defer launch hands the supervisor the assessed handoff directory",
          shlex.split(supervisor_arguments) == ["--handoff-dir", str(workspace.handoffs)]
          and "relaunched plain" in report,
          (supervisor_arguments, report))
    check("B: the launcher branch pins NEDSCHORUS_AGENTS_ROOT to the assessed root",
          captured_run["env"].get("NEDSCHORUS_AGENTS_ROOT")
          == str(workspace.agents_root),
          captured_run["env"].get("NEDSCHORUS_AGENTS_ROOT"))

    # Finding A on the resume path: --handoff-dir and --resume-session-id
    # travel together, and the box branch composes the same into its
    # supervisor command.
    workspace = Workspace(root / "r18")
    tmux_commands = []
    def capture_tmux(*arguments_after_tmux, socket_name=None):
        tmux_commands.append((arguments_after_tmux, socket_name))
        class Done:
            returncode = 0
        return Done()
    try:
        recovery.subprocess.run = capture_subprocess_run
        recovery.launcher_path = lambda: Path("/fake/launch-claude-mac")
        real_launch_seat(workspace.name, workspace.seat_directory,
                         workspace.handoffs,
                         f"--resume-session-id {shlex.quote('abc-123')}")
    finally:
        recovery.subprocess.run = real_run
        recovery.launcher_path = real_launcher_path
    resume_arguments = captured_run["env"].get(
        "LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS", "")
    check("A: the resume launch carries --handoff-dir alongside --resume-session-id",
          shlex.split(resume_arguments) == ["--handoff-dir", str(workspace.handoffs),
                                            "--resume-session-id", "abc-123"],
          resume_arguments)
    real_run_tmux = recovery.run_tmux
    try:
        recovery.launcher_path = lambda: None
        recovery.run_tmux = capture_tmux
        real_launch_seat(workspace.name, workspace.seat_directory,
                         workspace.handoffs,
                         f"--resume-session-id {shlex.quote('abc-123')}")
    finally:
        recovery.launcher_path = real_launcher_path
        recovery.run_tmux = real_run_tmux
    box_command = tmux_commands[0][0][-1] if tmux_commands else ""
    box_tokens = shlex.split(box_command)
    check("A: the box branch composes --handoff-dir into the supervisor command",
          str(workspace.handoffs) in box_tokens
          and str(workspace.seat_directory) in box_tokens
          and "abc-123" in box_tokens
          and "--handoff-dir" in box_tokens,
          box_command)
    # nedschorus#141 review F2: this branch composes the supervisor command
    # itself instead of running the launcher, so it must carry the seat
    # environment the launcher would have set. Without it a recovered box
    # generation has no task tools and no pin, and its list is invisible with
    # no error. Asserted on the composed string parsed as the launch shell
    # parses it, and on the id being derived from the SEAT NAME.
    # `export NAME=value;` splits into two tokens, the second keeping the
    # statement's trailing semicolon, so compare with it stripped.
    box_assignments = [token.rstrip(";") for token in box_tokens]
    check("task list: the box branch pins the list to the seat name",
          f"CLAUDE_CODE_TASK_LIST_ID=nedschorus-{workspace.name}-tasks" in box_assignments,
          box_command)
    check("task list: the box branch carries the store migration before the pin",
          f'if [ -d "$HOME/.claude/tasks/{workspace.name}-tasks" ]' in box_command
          and box_command.index("mv ")
          < box_command.index("CLAUDE_CODE_TASK_LIST_ID"),
          box_command)
    check("task list: the box branch enables the task tools",
          "CLAUDE_CODE_ENABLE_TODO_TOOLS=1" in box_assignments,
          box_command)
    # `marker in box_command` first, so a missing export FAILS this case
    # rather than raising out of the suite: str.index on an absent marker
    # tracebacks, which reads as a broken harness instead of a caught defect.
    check("task list: both exports precede the supervisor on the box command line",
          all(marker in box_command
              and box_command.index(marker) < box_command.index("handoff-supervisor.py")
              for marker in ("CLAUDE_CODE_TASK_LIST_ID",
                             "CLAUDE_CODE_ENABLE_TODO_TOOLS")),
          box_command)

    # PR #134 review finding 1: an apostrophe in an operator's directory path
    # must survive the one shell parse each composed value gets — the
    # reviewer measured the hand-quoted version killing the seat and then
    # failing the launch. Both branches, parsed as the launch shell would.
    apostrophe_handoffs = root / "r19" / "agent's handoffs"
    apostrophe_handoffs.mkdir(parents=True)
    try:
        recovery.subprocess.run = capture_subprocess_run
        recovery.launcher_path = lambda: Path("/fake/launch-claude-mac")
        real_launch_seat(workspace.name, workspace.seat_directory,
                         apostrophe_handoffs, "")
    finally:
        recovery.subprocess.run = real_run
        recovery.launcher_path = real_launcher_path
    check("F1: an apostrophe handoff dir survives the mac hook's shell parse",
          shlex.split(captured_run["env"]["LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS"])
          == ["--handoff-dir", str(apostrophe_handoffs)],
          captured_run["env"]["LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS"])
    tmux_commands.clear()
    try:
        recovery.launcher_path = lambda: None
        recovery.run_tmux = capture_tmux
        real_launch_seat(workspace.name, workspace.seat_directory,
                         apostrophe_handoffs, "")
    finally:
        recovery.launcher_path = real_launcher_path
        recovery.run_tmux = real_run_tmux
    check("F1: an apostrophe handoff dir survives the box command's shell parse",
          str(apostrophe_handoffs) in shlex.split(tmux_commands[0][0][-1]),
          tmux_commands[0][0][-1])

    # PR #134 review finding 2: a --handoff-dir that does not exist yet must
    # not traceback after assessment already chose to resume — the resume
    # prompt's directory is created, as the supervisor creates its own.
    workspace = Workspace(root / "r20")
    all_dead()
    write_transcript(workspace.project_directory(), "resume-me", "real work",
                     records=5)
    capture_launches(workspace)
    missing_handoffs = workspace.handoffs / "not-created-yet"
    report = recovery.recover_seat(workspace.name, workspace.agents_root,
                                   missing_handoffs, workspace.projects,
                                   False, False)
    check("F2: a nonexistent --handoff-dir does not traceback; the resume proceeds",
          "relaunched resuming resume-me" in report, report)
    check("F2: the resume prompt lands in the created directory",
          (missing_handoffs / f"{workspace.name}-resume-recovery-prompt.md").is_file(),
          missing_handoffs)

    # PR #134 round-2 finding 1: the REAL mac launcher's own composition must
    # survive apostrophes in the override-fed values — the reviewer measured
    # recovery reporting "relaunched resuming" while the command tmux was
    # handed did not parse (hand-quoted --first-prompt-file, whose path is
    # built inside --handoff-dir; the agents root reaches AGENT_DIRECTORY the
    # same way). Sandbox: stub tmux capturing argv, no-op claude/python3/git
    # on PATH, throwaway HOME; the workspace root carries the apostrophe so
    # both quoted launcher sites are exercised in one run through the real
    # launch-claude-mac.
    workspace = Workspace(root / "agent's r21")
    all_dead()
    write_transcript(workspace.project_directory(), "apostrophe-resume",
                     "real work", records=5)
    patch("launch_seat", real_launch_seat)
    stub_directory = root / "r21-stubs"
    stub_directory.mkdir()
    capture_path = root / "r21-tmux-capture.txt"
    (stub_directory / "tmux").write_text(
        '#!/bin/sh\n'
        'for argument in "$@"; do\n'
        '  case "$argument" in (has-session) exit 1;; esac\n'
        'done\n'
        f'printf \'%s\\n\' "$@" >> "{capture_path}"\n'
        'exit 0\n', encoding="utf-8")
    for stub_name in ("claude", "python3", "git"):
        (stub_directory / stub_name).write_text("#!/bin/sh\nexit 0\n",
                                                encoding="utf-8")
    for stub in stub_directory.iterdir():
        stub.chmod(0o755)
    sandbox_home = root / "r21-home"
    sandbox_home.mkdir()
    saved_path_env = os.environ["PATH"]
    saved_home_env = os.environ.get("HOME")
    saved_agents_root_env = os.environ.get("NEDSCHORUS_AGENTS_ROOT")
    try:
        os.environ["PATH"] = f"{stub_directory}:/usr/bin:/bin:/usr/sbin:/sbin"
        os.environ["HOME"] = str(sandbox_home)
        report = recovery.recover_seat(workspace.name, workspace.agents_root,
                                       workspace.handoffs, workspace.projects,
                                       False, False)
        # The attached path composes AFTER_EXIT_COMMAND too (its cd rides the
        # same quoted directory); resupervise launches attached, so it is
        # probed directly.
        os.environ["NEDSCHORUS_AGENTS_ROOT"] = str(workspace.agents_root)
        detached_capture = (capture_path.read_text(encoding="utf-8")
                            if capture_path.is_file() else "")
        capture_path.write_text("", encoding="utf-8")
        # launcher_path() is None off macOS -- the box composes its launch
        # directly -- and handing subprocess the string "None" aborted the
        # whole run there (nedschorus#172), so the probe is skipped out loud.
        if recovery.launcher_path() is None:
            attached_capture = None
        else:
            recovery.subprocess.run([str(recovery.launcher_path()), workspace.name],
                                    capture_output=True, text=True, check=False)
            attached_capture = (capture_path.read_text(encoding="utf-8")
                                if capture_path.is_file() else "")
    finally:
        os.environ["PATH"] = saved_path_env
        if saved_home_env is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = saved_home_env
        if saved_agents_root_env is None:
            os.environ.pop("NEDSCHORUS_AGENTS_ROOT", None)
        else:
            os.environ["NEDSCHORUS_AGENTS_ROOT"] = saved_agents_root_env
    command_line = next((line for line in detached_capture.splitlines()
                         if "handoff-supervisor.py" in line), "")
    try:
        command_tokens = shlex.split(command_line)
        parse_problem = ""
    except ValueError as error:
        command_tokens, parse_problem = [], str(error)
    check("F1: the REAL launcher's composed command parses with apostrophe overrides",
          "relaunched resuming apostrophe-resume" in report
          and not parse_problem and command_tokens,
          (report, parse_problem, command_line))
    check("F1: prompt-file and seat-directory paths reach the supervisor byte-intact",
          str(workspace.handoffs / f"{workspace.name}-resume-recovery-prompt.md")
          in command_tokens
          and str(workspace.seat_directory) in command_tokens,
          command_tokens)
    if attached_capture is None:
        skip("F1: the attached launch's after-exit shell command parses too",
             "macOS only: the attached launch runs launch-claude-mac, and "
             "launcher_path() is None on this platform")
    else:
        attached_line = next((line for line in attached_capture.splitlines()
                              if "handoff-supervisor.py" in line), "")
        try:
            attached_tokens = shlex.split(attached_line)
            attached_problem = ""
        except ValueError as error:
            attached_tokens, attached_problem = [], str(error)
        check("F1: the attached launch's after-exit shell command parses too",
              not attached_problem and attached_tokens
              # containment, not equality: the composed string juxtaposes ';'
              # against the closing quote, so the directory's token carries it
              and any(str(workspace.seat_directory) in token
                      for token in attached_tokens),
              (attached_problem, attached_line))

    # Round-4 review note (user-ruled 2026-08-22: allowed overrides must
    # work): default_agents_root resolves the same way the launchers do —
    # ${NEDSCHORUS_AGENTS_ROOT:-~/agents}. Resolving differently assesses a
    # root no seat lives in, and recovery refuses on "no seat directory".
    saved_root = os.environ.get("NEDSCHORUS_AGENTS_ROOT")
    try:
        os.environ["NEDSCHORUS_AGENTS_ROOT"] = str(root / "custom-agents")
        check("default_agents_root honors NEDSCHORUS_AGENTS_ROOT",
              recovery.default_agents_root() == root / "custom-agents",
              recovery.default_agents_root())
        os.environ["NEDSCHORUS_AGENTS_ROOT"] = ""
        check("an empty NEDSCHORUS_AGENTS_ROOT falls back to ~/agents (the :- rule)",
              recovery.default_agents_root() == Path("~/agents").expanduser(),
              recovery.default_agents_root())
    finally:
        if saved_root is None:
            os.environ.pop("NEDSCHORUS_AGENTS_ROOT", None)
        else:
            os.environ["NEDSCHORUS_AGENTS_ROOT"] = saved_root

    # User-ruled 2026-08-22: recovery's verdicts are durably logged. The
    # printed reports otherwise live only in the operator's scrollback, and
    # a post-crash investigator needs the decision AS MADE AT THE TIME —
    # state moves after a recovery, so the verdict may not be re-derivable.
    # Driven through main(), where the logging hook lives.
    workspace = Workspace(root / "r22")
    all_dead()
    write_transcript(workspace.project_directory(), "logged-resume", "real work",
                     records=5)
    capture_launches(workspace)
    exit_code = recovery.main(["seat-a",
                               "--agents-root", str(workspace.agents_root),
                               "--handoff-dir", str(workspace.handoffs),
                               "--projects-root", str(workspace.projects)])
    log_path = workspace.handoffs / "recover-crashed-seats-log.txt"
    log_text = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
    check("LOG: a recovery run appends its verdict, timestamped",
          exit_code == 0 and "relaunched resuming logged-resume" in log_text
          and log_text[:4].isdigit()
          and "+00:00 " in log_text.splitlines()[0],
          (exit_code, log_text))
    exit_code = recovery.main(["seat-a", "--dry-run",
                               "--agents-root", str(workspace.agents_root),
                               "--handoff-dir", str(workspace.handoffs),
                               "--projects-root", str(workspace.projects)])
    after_dry_run = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
    check("LOG: --dry-run logs nothing — it changes nothing, and it is the probe",
          exit_code == 0 and after_dry_run == log_text,
          after_dry_run)
    # A refusal is a decision too. Before 2026-09-16 this case refused a live
    # tmux session; a live seat, its supervisor confirmed by ps, is now ALREADY
    # RUNNING (below), so the refusal here is one that means something is wrong
    # whatever the lock says: tmux could not be asked.
    patch("tmux_session_alive_anywhere",
          lambda name: (None, "tmux cannot be run here, so seat liveness cannot be "
                              "checked — refusing rather than guessing"))
    exit_code = recovery.main(["seat-a",
                               "--agents-root", str(workspace.agents_root),
                               "--handoff-dir", str(workspace.handoffs),
                               "--projects-root", str(workspace.projects)])
    after_refusal = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
    check("LOG: a refusal is a decision too — logged, run exits 1",
          exit_code == 1 and after_refusal.startswith(log_text)
          and "seat-a: REFUSED — tmux cannot be run here" in after_refusal[len(log_text):],
          (exit_code, after_refusal))
    patch("tmux_session_alive_anywhere",
          lambda name: (True, f"tmux session '{name}' is alive on socket '{name}'"))
    logged_lock_path = workspace.handoffs / "seat-a-supervisor.lock"
    logged_lock_path.write_text("4321\n", encoding="utf-8")
    try:
        ps_confirms_supervisors({4321: "seat-a"})
        exit_code = recovery.main(["seat-a",
                                   "--agents-root", str(workspace.agents_root),
                                   "--handoff-dir", str(workspace.handoffs),
                                   "--projects-root", str(workspace.projects)])
    finally:
        ps_answers_for_real()
        logged_lock_path.unlink()
    after_already_running = (log_path.read_text(encoding="utf-8")
                             if log_path.is_file() else "")
    check("LOG: a seat already running is logged as ALREADY RUNNING, and the run exits 0",
          exit_code == 0 and after_already_running.startswith(after_refusal)
          and "seat-a: ALREADY RUNNING — tmux session 'seat-a' is alive"
              in after_already_running[len(after_refusal):],
          (exit_code, after_already_running))

    import subprocess as real_subprocess
    completed = real_subprocess.run(
        [sys.executable, str(SUPERVISOR_SCRIPT),
         "--agent", "x", "--resume-session-id", "a", "--adopt-session-id", "b",
         "--adopt-process-id", "1"],
        capture_output=True, text=True)
    check("supervisor refuses --resume-session-id together with adoption",
          completed.returncode != 0 and "different recoveries" in completed.stderr,
          completed.stderr)

    run_came_up_cases(root)

    # The same thing through recover_seat, on each path that can offer the
    # degraded restart and on one that cannot.
    workspace = Workspace(root / "came-up-resume", name="did-not-come-up")
    all_dead()
    capture_launches(workspace)
    seat_comes_up(False, "a supervisor started and stopped again within 6s, "
                         "so the session did not survive")
    write_transcript(workspace.project_directory(), "resume-me", "real work", records=4)
    report = workspace.recover()
    check("a resume that did not come up is never reported as relaunched",
          "LAUNCHED BUT DID NOT COME UP" in report and "relaunched" not in report, report)
    check("and it offers the degraded restart",
          "--ignite-fallback" in report, report)

    # The plain relaunch the deferred-handoff verdict chooses. That verdict is
    # reached on the verdict alone — assess_seat never sees --ignite-fallback —
    # so a run that PASSED the flag lands here too, and was offered the flag it
    # had just used (PR #329 review, finding 2).
    for used_the_flag, offered in ((True, False), (False, True)):
        workspace = Workspace(root / f"came-up-defer-{used_the_flag}",
                              name="defer-did-not-come-up")
        all_dead()
        capture_launches(workspace)
        seat_comes_up(False, "no supervisor appeared within 120s")
        (workspace.handoffs / f"{workspace.name}-handoff.md").write_text(
            "# Handoff\nrestart-counter: 5\nnext-step: continue\n", encoding="utf-8")
        report = workspace.recover(ignite_fallback=used_the_flag)
        check("a plain relaunch that did not come up offers the degraded restart "
              f"only to an operator who has not just used it (--ignite-fallback: {used_the_flag})",
              "LAUNCHED BUT DID NOT COME UP" in report
              and ("--ignite-fallback" in report) == offered, report)

    workspace = Workspace(root / "came-up-ignite", name="ignite-did-not-come-up")
    all_dead()
    capture_launches(workspace)
    seat_comes_up(False, "no supervisor appeared within 120s")
    (workspace.handoffs / f"{workspace.name}-dialog-0001.md").write_text(
        "# Dialog\n", encoding="utf-8")
    report = workspace.recover(ignite_fallback=True)
    check("an ignite that did not come up is reported, without offering itself again",
          "LAUNCHED BUT DID NOT COME UP" in report
          and "--ignite-fallback" not in report, report)

    # A dry run launches nothing, so it must not wait for anything either.
    workspace = Workspace(root / "came-up-dry", name="dry-no-wait")
    all_dead()
    capture_launches(workspace)
    waited = []
    patch("wait_for_the_seat_to_come_up",
          lambda *a, **k: (waited.append(1), (True, "x"))[1])
    write_transcript(workspace.project_directory(), "resume-me", "real work", records=4)
    report = workspace.recover(dry_run=True)
    check("a dry run never waits for a seat to come up",
          waited == [] and "would resume" in report, (waited, report))
    seat_comes_up()

    # --- the exit code -------------------------------------------------------
    # A report class the counting does not recognise makes this tool exit ZERO
    # for a seat it has just said did not come back — which is what LAUNCHED BUT
    # DID NOT COME UP did, containing neither "REFUSED" nor "LAUNCH FAILED"
    # (PR #329 review, finding 1). Two cases, catching different things.
    #
    # This one pins main against the DECLARED set: every class named in
    # SEAT_NOT_RECOVERED_REPORT_MARKERS is counted, so a class added there is
    # covered without anyone writing a case for it.
    def main_on(workspace):
        return recovery.main([workspace.name,
                              "--agents-root", str(workspace.agents_root),
                              "--handoff-dir", str(workspace.handoffs),
                              "--projects-root", str(workspace.projects)])

    workspace = Workspace(root / "exit-declared", name="exit-declared-seat")
    real_recover_seat = recovery.recover_seat
    try:
        for marker in recovery.SEAT_NOT_RECOVERED_REPORT_MARKERS:
            stubbed = f"{workspace.name}: {marker} — whatever the reason was"
            patch("recover_seat", lambda *a, report=stubbed, **k: report)
            check(f"EXIT: a seat reported {marker} does not exit zero",
                  main_on(workspace) != 0, marker)
        patch("recover_seat",
              lambda *a, **k: f"{workspace.name}: relaunched plain — it came back")
        check("EXIT: and a seat that did come back exits zero", main_on(workspace) == 0)
        # A seat already running is not a seat not recovered (user-ruled
        # 2026-09-16, on the question PR #426's reviewer asked), so its class
        # must not contain any declared marker, or main would count it.
        check("EXIT: the ALREADY RUNNING class contains no not-recovered marker",
              not any(marker in recovery.SEAT_ALREADY_RUNNING_REPORT_MARKER
                      or recovery.SEAT_ALREADY_RUNNING_REPORT_MARKER in marker
                      for marker in recovery.SEAT_NOT_RECOVERED_REPORT_MARKERS),
              (recovery.SEAT_ALREADY_RUNNING_REPORT_MARKER,
               recovery.SEAT_NOT_RECOVERED_REPORT_MARKERS))
        patch("recover_seat", lambda *a, **k: (
            f"{workspace.name}: {recovery.SEAT_ALREADY_RUNNING_REPORT_MARKER} — "
            "tmux session is alive"))
        check("EXIT: and a seat reported ALREADY RUNNING exits zero",
              main_on(workspace) == 0)
    finally:
        patch("recover_seat", real_recover_seat)

    # And this one runs the REAL recover_seat down every failure path it has,
    # which is the half that would have caught the miss: the tuple above is only
    # as good as someone remembering to add to it, and nobody did.
    def a_real_failure_path_does_not_exit_zero(case_name, workspace):
        exit_code = main_on(workspace)
        log_path = workspace.handoffs / "recover-crashed-seats-log.txt"
        logged = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
        check(f"EXIT: {case_name} does not exit zero, and says so in a declared class",
              exit_code != 0
              and any(marker in logged
                      for marker in recovery.SEAT_NOT_RECOVERED_REPORT_MARKERS),
              (exit_code, logged))

    # Refused for a reason that still means something is wrong. This case used
    # to refuse a live tmux session, which is ALREADY RUNNING since 2026-09-16
    # when a supervisor of the seat is confirmed and REFUSED when none is (cases
    # below); a handoff whose restart-counter nobody can read is refused still.
    workspace = Workspace(root / "exit-refused", name="exit-refused-seat")
    all_dead()
    capture_launches(workspace)
    (workspace.handoffs / f"{workspace.name}-handoff.md").write_text(
        "# Handoff\nrestart-counter: not-a-number\nnext-step: x\n", encoding="utf-8")
    a_real_failure_path_does_not_exit_zero("a seat that was refused", workspace)

    # Left down on purpose, but down: counted, or the login restart would list
    # it with the seats that came up.
    workspace = Workspace(root / "exit-consulted", name="exit-consulted-seat")
    all_dead()
    capture_launches(workspace)
    (workspace.handoffs / f"{workspace.name}-handoff.md").write_text(
        consulted_handoff_text, encoding="utf-8")
    a_real_failure_path_does_not_exit_zero("a seat that asked to be consulted", workspace)

    # Every refusal the 2026-09-16 ruling kept as a failure, through the real
    # assess_seat and recover_seat: each is reported REFUSED, never ALREADY
    # RUNNING, and makes the run exit 1.
    def refused_for_no_seat_directory(workspace):
        (workspace.agents_root / workspace.name).rmdir()

    def refused_for_tmux_that_cannot_be_asked(workspace):
        patch("tmux_session_alive_anywhere",
              lambda name: (None, "tmux cannot be run here, so seat liveness cannot be "
                                  "checked — refusing rather than guessing"))

    def refused_for_an_occupied_seat_directory(workspace):
        patch("seat_directory_occupied",
              lambda directory, apart_from_process_ids=(): (True, f"a live process is rooted in {directory}"))

    def refused_for_an_unprovable_vacancy(workspace):
        patch("seat_directory_occupied",
              lambda directory, apart_from_process_ids=(): (True, "lsof is not installed, so the seat cannot be "
                                       "proven vacant"))

    def refused_for_an_unreadable_restart_counter(workspace):
        (workspace.handoffs / f"{workspace.name}-handoff.md").write_text(
            "# Handoff\nrestart-counter: not-a-number\nnext-step: x\n", encoding="utf-8")

    for refusal in (refused_for_no_seat_directory, refused_for_tmux_that_cannot_be_asked,
                    refused_for_an_occupied_seat_directory, refused_for_an_unprovable_vacancy,
                    refused_for_an_unreadable_restart_counter):
        workspace = Workspace(root / f"exit-{refusal.__name__}", name="still-refused-seat")
        all_dead()
        capture_launches(workspace)
        write_transcript(workspace.project_directory(), "resume-me", "real work", records=4)
        refusal(workspace)
        report = workspace.recover()
        exit_code = main_on(workspace)
        check(f"EXIT: {refusal.__name__.replace('_', ' ')} is REFUSED, counted, and exits 1",
              report.startswith(f"{workspace.name}: REFUSED — ")
              and recovery.SEAT_ALREADY_RUNNING_REPORT_MARKER not in report
              and exit_code == 1 and workspace.launches == [],
              (report, exit_code, workspace.launches))

    # The three ways a seat is found already running (user-ruled 2026-09-16),
    # each with a live supervisor of it CONFIRMED by ps (user-ruled 2026-09-16,
    # PR #426 review): its tmux session is alive with that supervisor, its
    # supervisor lock is held by that supervisor, or that supervisor is
    # watching it. Each is reported ALREADY RUNNING, keeps its own detail,
    # launches nothing, is reported the same by a dry run, and leaves the exit
    # code zero.
    real_supervisor_liveness = recovery.supervisor.supervisor_liveness

    def already_running_in_tmux_with_a_confirmed_supervisor(workspace):
        (workspace.handoffs / f"{workspace.name}-supervisor.lock").write_text(
            "4321\n", encoding="utf-8")
        ps_confirms_supervisors({4321: workspace.name})
        patch("tmux_session_alive_anywhere",
              lambda name: (True, f"tmux session '{name}' is alive on socket '{name}'"))
        return (f"tmux session '{workspace.name}' is alive on socket '{workspace.name}', "
                f"and process 4321 is the supervisor of {workspace.name} — "
                "this tool recovers crashes, it never touches live seats")

    def already_running_under_a_supervisor_lock_confirmed_by_ps(workspace):
        (workspace.handoffs / f"{workspace.name}-supervisor.lock").write_text(
            "4321\n", encoding="utf-8")
        ps_confirms_supervisors({4321: workspace.name})
        return (f"the supervisor lock at {workspace.handoffs}/{workspace.name}-supervisor.lock "
                f"is held by a live supervisor — process 4321 is the supervisor of "
                f"{workspace.name}")

    def a_supervisor_claims_the_lock_between_the_lock_check_and_the_liveness_check(
            workspace, holder, liveness_detail):
        """The only way to reach the watching-supervisor check on its own: in
        real operation it reads the same lock as the lock check before it, so it
        says yes by itself only when a supervisor claims that lock in between.
        Each assessment starts before the claim (the tmux check, asked first,
        removes the lock) and the liveness check is where it lands."""
        lock_path = workspace.handoffs / f"{workspace.name}-supervisor.lock"

        def no_tmux_session_and_no_lock_yet(name):
            lock_path.unlink(missing_ok=True)
            return False, ""

        def the_supervisor_claims_its_lock(state_path):
            lock_path.write_text(f"{holder}\n", encoding="utf-8")
            return True, liveness_detail
        patch("tmux_session_alive_anywhere", no_tmux_session_and_no_lock_yet)
        recovery.supervisor.supervisor_liveness = the_supervisor_claims_its_lock

    def already_running_under_a_watching_supervisor_confirmed_by_ps(workspace):
        a_supervisor_claims_the_lock_between_the_lock_check_and_the_liveness_check(
            workspace, 4321, "supervisor alive — last heartbeat 3s ago")
        ps_confirms_supervisors({4321: workspace.name})
        return "a supervisor is watching this seat (supervisor alive — last heartbeat 3s ago)"

    for running in (already_running_in_tmux_with_a_confirmed_supervisor,
                    already_running_under_a_supervisor_lock_confirmed_by_ps,
                    already_running_under_a_watching_supervisor_confirmed_by_ps):
        workspace = Workspace(root / f"exit-{running.__name__}", name="running-seat")
        all_dead()
        capture_launches(workspace)
        write_transcript(workspace.project_directory(), "resume-me", "real work", records=4)
        try:
            detail = running(workspace)
            verdict, _ = workspace.assess()
            report = workspace.recover()
            dry_run_report = workspace.recover(dry_run=True)
            exit_code = main_on(workspace)
        finally:
            ps_answers_for_real()
            recovery.supervisor.supervisor_liveness = real_supervisor_liveness
        log_path = workspace.handoffs / "recover-crashed-seats-log.txt"
        logged = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
        case_name = running.__name__.replace("_", " ")
        check(f"RUNNING: {case_name} is the seat-already-running verdict",
              verdict == "seat-already-running", verdict)
        check(f"RUNNING: {case_name} is reported ALREADY RUNNING with its own detail",
              report == f"{workspace.name}: ALREADY RUNNING — {detail}", (report, detail))
        check(f"RUNNING: {case_name} carries no not-recovered marker",
              not any(marker in report
                      for marker in recovery.SEAT_NOT_RECOVERED_REPORT_MARKERS), report)
        check(f"RUNNING: {case_name} reads the same under a dry run",
              dry_run_report == report, (dry_run_report, report))
        check(f"RUNNING: {case_name} launches nothing, is logged, and exits 0",
              workspace.launches == [] and exit_code == 0
              and f"{workspace.name}: ALREADY RUNNING — " in logged,
              (workspace.launches, exit_code, logged))

    # What dc949ef first called already running and the user ruled back to a
    # refusal (2026-09-16, PR #426 reviews 5228492424 and 5228560398): a
    # supervisor only ASSUMED because ps could not be run — on the lock check
    # and on the watching-supervisor check — and a live tmux session with no
    # confirmed supervisor, which an attached launch leaves open at a shell
    # after its supervisor exits (scripts/launch-claude-mac, AFTER_EXIT_COMMAND).
    # Each is REFUSED under its own detail, never ALREADY RUNNING, is refused
    # the same by a dry run, launches nothing — into a live tmux session least
    # of all — and makes the run exit 1. The assumption needs a process that
    # exists, so its lock names this very interpreter.
    def refused_for_a_supervisor_lock_ps_could_not_confirm(workspace):
        (workspace.handoffs / f"{workspace.name}-supervisor.lock").write_text(
            f"{os.getpid()}\n", encoding="utf-8")
        ps_cannot_be_run()
        return (f"the supervisor lock at {workspace.handoffs}/{workspace.name}-supervisor.lock "
                "names a live process, but ps could not confirm it is a supervisor of this "
                f"seat — cannot tell whether process {os.getpid()} is the supervisor of "
                f"{workspace.name}")

    def refused_for_a_watching_supervisor_ps_could_not_confirm(workspace):
        a_supervisor_claims_the_lock_between_the_lock_check_and_the_liveness_check(
            workspace, os.getpid(),
            f"supervisor alive — cannot tell whether process {os.getpid()} is the "
            f"supervisor of {workspace.name}")
        ps_cannot_be_run()
        return (f"a supervisor may be watching this seat (supervisor alive — cannot tell "
                f"whether process {os.getpid()} is the supervisor of {workspace.name}), but "
                "ps could not confirm it")

    def refused_for_a_live_tmux_session_with_no_supervisor(workspace):
        patch("tmux_session_alive_anywhere",
              lambda name: (True, f"tmux session '{name}' is alive on socket '{name}'"))
        return (f"tmux session '{workspace.name}' is alive on socket '{workspace.name}', "
                "but no live supervisor of this seat is confirmed (no supervisor lock at "
                f"{workspace.handoffs}/{workspace.name}-supervisor.lock) — this tool never "
                "touches a live tmux session")

    def refused_for_a_live_tmux_session_whose_supervisor_ps_could_not_confirm(workspace):
        (workspace.handoffs / f"{workspace.name}-supervisor.lock").write_text(
            f"{os.getpid()}\n", encoding="utf-8")
        ps_cannot_be_run()
        patch("tmux_session_alive_anywhere",
              lambda name: (True, f"tmux session '{name}' is alive on socket '{name}'"))
        return (f"tmux session '{workspace.name}' is alive on socket '{workspace.name}', "
                "but no live supervisor of this seat is confirmed (cannot tell whether "
                f"process {os.getpid()} is the supervisor of {workspace.name}")

    for unconfirmed in (refused_for_a_supervisor_lock_ps_could_not_confirm,
                        refused_for_a_watching_supervisor_ps_could_not_confirm,
                        refused_for_a_live_tmux_session_with_no_supervisor,
                        refused_for_a_live_tmux_session_whose_supervisor_ps_could_not_confirm):
        workspace = Workspace(root / f"exit-{unconfirmed.__name__}", name="unconfirmed-seat")
        all_dead()
        capture_launches(workspace)
        write_transcript(workspace.project_directory(), "resume-me", "real work", records=4)
        try:
            with redirect_stderr(io.StringIO()):  # the predicate's operator line
                detail_opening = unconfirmed(workspace)
                verdict, _ = workspace.assess()
                report = workspace.recover()
                dry_run_report = workspace.recover(dry_run=True)
                exit_code = main_on(workspace)
        finally:
            ps_answers_for_real()
            recovery.supervisor.supervisor_liveness = real_supervisor_liveness
        log_path = workspace.handoffs / "recover-crashed-seats-log.txt"
        logged = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
        case_name = unconfirmed.__name__.replace("_", " ")
        check(f"UNCONFIRMED: {case_name} is the refuse verdict, not seat-already-running",
              verdict == "refuse", verdict)
        check(f"UNCONFIRMED: {case_name} is reported REFUSED with its own detail",
              report.startswith(f"{workspace.name}: REFUSED — {detail_opening}")
              and recovery.SEAT_ALREADY_RUNNING_REPORT_MARKER not in report,
              (report, detail_opening))
        check(f"UNCONFIRMED: {case_name} is refused the same under a dry run",
              dry_run_report == report, (dry_run_report, report))
        check(f"UNCONFIRMED: {case_name} launches nothing, is counted, and exits 1",
              workspace.launches == [] and exit_code == 1
              and f"{workspace.name}: REFUSED — " in logged,
              (workspace.launches, exit_code, logged))

    workspace = Workspace(root / "exit-launch-failed", name="exit-launch-failed-seat")
    all_dead()
    capture_launches(workspace)
    patch("launch_seat", lambda *arguments, **keywords: 7)
    write_transcript(workspace.project_directory(), "resume-me", "real work", records=4)
    a_real_failure_path_does_not_exit_zero("a launch that failed", workspace)

    workspace = Workspace(root / "exit-did-not-come-up", name="exit-did-not-come-up-seat")
    all_dead()
    capture_launches(workspace)
    seat_comes_up(False, "a supervisor started and stopped again within 6s, "
                         "so the session did not survive")
    write_transcript(workspace.project_directory(), "resume-me", "real work", records=4)
    a_real_failure_path_does_not_exit_zero("a launch that did not come up", workspace)

    # Several seats in one run: nonzero when ANY seat was not recovered, not only
    # when every one was (user-ruled 2026-09-16, merge-lane walk item 6). Three
    # seats up and one down used to exit zero, telling an unattended caller the
    # fleet came back. Driven through the real recover_seat with a launch stub
    # that fails for the seats named, so a failure in the middle of the run is
    # also shown not to stop the seats after it from being tried and reported.
    # A seat named in running is found with its tmux session alive and a live
    # supervisor of it confirmed by ps — its lock names process 5000 plus the
    # seat's position — so it is ALREADY RUNNING (user-ruled 2026-09-16);
    # selection is what main is given in place of the names, so --all and
    # --dry-run can be driven too.
    def main_on_seats(case_directory, names, failing, running=frozenset(), selection=None):
        workspace = Workspace(case_directory, name=names[0])
        for name in names:
            (workspace.agents_root / name).mkdir(parents=True, exist_ok=True)
            write_transcript(recovery.harness_project_directory(
                workspace.agents_root / name, workspace.projects),
                f"resume-{name}", "real work", records=4)
        all_dead()
        patch("tmux_session_alive_anywhere",
              lambda name: ((True, f"tmux session '{name}' is alive on socket '{name}'")
                            if name in running else (False, "")))
        seat_supervised_by_process_id = {}
        for position, name in enumerate(names):
            if name in running:
                (workspace.handoffs / f"{name}-supervisor.lock").write_text(
                    f"{5000 + position}\n", encoding="utf-8")
                seat_supervised_by_process_id[5000 + position] = name
        capture_launches(workspace)

        def launch_failing_for_the_seats_named(name, seat_directory, handoff_directory,
                                               extra_arguments, first_prompt_file=None):
            workspace.launches.append((name, extra_arguments, first_prompt_file))
            return 7 if name in failing else 0
        patch("launch_seat", launch_failing_for_the_seats_named)
        printed = io.StringIO()
        try:
            ps_confirms_supervisors(seat_supervised_by_process_id)
            with redirect_stdout(printed):
                exit_code = recovery.main([*(names if selection is None else selection),
                                           "--agents-root", str(workspace.agents_root),
                                           "--handoff-dir", str(workspace.handoffs),
                                           "--projects-root", str(workspace.projects)])
        finally:
            ps_answers_for_real()
        log_path = workspace.handoffs / "recover-crashed-seats-log.txt"
        logged = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
        return exit_code, printed.getvalue(), logged, workspace.launches

    def every_seat_reported(names, failing, printed, logged, launches, running=frozenset()):
        """One printed line and one log line per seat, in the order given, each
        saying what became of that seat, and every seat's launch attempted —
        except a seat already running, which is launched nothing and reported
        ALREADY RUNNING, in a line carrying no not-recovered marker."""
        printed_lines = printed.splitlines()
        logged_lines = logged.splitlines()
        return (len(printed_lines) == len(names) and len(logged_lines) == len(names)
                and [launch[0] for launch in launches]
                    == [name for name in names if name not in running]
                and all(line.startswith(f"recover-crashed-seats: {name}: ")
                        and ("ALREADY RUNNING" in line) == (name in running)
                        and ("LAUNCH FAILED" in line) == (name in failing)
                        and ("relaunched resuming" in line)
                            == (name not in failing and name not in running)
                        and (name not in running
                             or not any(marker in line for marker
                                        in recovery.SEAT_NOT_RECOVERED_REPORT_MARKERS))
                        and f" {name}: " in logged_line
                        for name, line, logged_line
                        in zip(names, printed_lines, logged_lines)))

    names = ("several-first-seat-up", "several-middle-seat-down", "several-last-seat-up")
    failing = {"several-middle-seat-down"}
    exit_code, printed, logged, launches = main_on_seats(
        root / "exit-several-one-down", names, failing)
    check("EXIT: several seats with one not recovered exits 1, not zero",
          exit_code == 1, (exit_code, printed))
    check("EXIT: and every seat still gets its report line and its log line",
          every_seat_reported(names, failing, printed, logged, launches),
          (printed, logged, launches))

    exit_code, printed, logged, launches = main_on_seats(
        root / "exit-several-all-up", names, set())
    check("EXIT: several seats all recovered exits zero",
          exit_code == 0 and every_seat_reported(names, set(), printed, logged, launches),
          (exit_code, printed, logged, launches))

    exit_code, printed, logged, launches = main_on_seats(
        root / "exit-several-all-down", names, set(names))
    check("EXIT: several seats none recovered still exits 1",
          exit_code == 1 and every_seat_reported(names, set(names), printed, logged, launches),
          (exit_code, printed, logged, launches))

    # A seat already running is not a seat that failed (user-ruled 2026-09-16,
    # on the question PR #426's reviewer asked): one running beside seats that
    # came back exits zero, and one running beside a seat that genuinely failed
    # still exits 1.
    names = ("several-first-seat-up", "several-middle-seat-already-running",
             "several-last-seat-up")
    running = {"several-middle-seat-already-running"}
    exit_code, printed, logged, launches = main_on_seats(
        root / "exit-several-one-already-running", names, set(), running)
    check("EXIT: several seats, one already running and the rest recovered, exits zero",
          exit_code == 0, (exit_code, printed))
    check("EXIT: and the running seat is reported ALREADY RUNNING, launched nothing",
          every_seat_reported(names, set(), printed, logged, launches, running),
          (printed, logged, launches))

    names = ("several-first-seat-already-running", "several-middle-seat-down",
             "several-last-seat-up")
    running, failing = {"several-first-seat-already-running"}, {"several-middle-seat-down"}
    exit_code, printed, logged, launches = main_on_seats(
        root / "exit-several-already-running-and-down", names, failing, running)
    check("EXIT: several seats, one already running and one genuinely failed, exits 1",
          exit_code == 1
          and every_seat_reported(names, failing, printed, logged, launches, running),
          (exit_code, printed, logged, launches))

    # The reviewer's own probe: --all lists every seat that ever ran, live ones
    # included, so one live seat used to fail the whole run, dry run and all.
    names = ("all-seat-already-running", "all-seat-crashed")
    running = {"all-seat-already-running"}
    exit_code, printed, logged, launches = main_on_seats(
        root / "exit-all-one-already-running", names, set(), running, selection=["--all"])
    check("EXIT: --all with one seat already running and the crashed seat recovered exits zero",
          exit_code == 0
          and every_seat_reported(names, set(), printed, logged, launches, running),
          (exit_code, printed, logged, launches))
    exit_code, printed, logged, launches = main_on_seats(
        root / "exit-all-dry-run-one-already-running", names, set(), running,
        selection=["--all", "--dry-run"])
    check("EXIT: and so does --all --dry-run, reporting the running seat ALREADY RUNNING",
          exit_code == 0 and launches == [] and logged == ""
          and printed.splitlines() == [
              "recover-crashed-seats: all-seat-already-running: ALREADY RUNNING — tmux "
              "session 'all-seat-already-running' is alive on socket "
              "'all-seat-already-running', and process 5000 is the supervisor of "
              "all-seat-already-running — this tool recovers crashes, it never touches "
              "live seats",
              "recover-crashed-seats: all-seat-crashed: would resume session "
              "resume-all-seat-crashed (0KB transcript) under a supervisor"],
          (exit_code, printed, logged, launches))

    # --- a recorded agent exit (nedschorus#242 change 2) ----------------------
    # Ruled 2026-09-02 (the #120 overview, § Ruled 2026-09-02: record how the
    # agent exited): a seat whose supervisor recorded its agent's exit did not
    # crash, so it is offered to be brought back by hand, never resumed or
    # ignited. Presence decides, not the code: zero, nonzero, a signal's
    # negative code and an unknown code all offer; only no record resumes. The
    # record is written here by the supervisor's own writer, so the key names
    # the two programs share are the ones under test.
    def record_an_agent_exit(workspace, exit_code):
        state_path = workspace.handoffs / f"{workspace.name}-supervisor-state.json"
        recovery.supervisor.record_agent_exit_in_supervisor_state(
            state_path, {"consumed_counter": None, "session_id": "resume-me",
                         "generation": 3}, exit_code)
        return recovery.supervisor.read_supervisor_state(state_path)[
            recovery.supervisor.AGENT_EXIT_RECORDED_AT_STATE_KEY]

    for exit_code in (0, 3, -15, None):
        workspace = Workspace(root / f"exit-record-{exit_code}", name="exited-seat")
        all_dead()
        capture_launches(workspace)
        write_transcript(workspace.project_directory(), "resume-me", "real work", records=4)
        recorded_at = record_an_agent_exit(workspace, exit_code)
        verdict, detail = workspace.assess()
        check(f"EXIT RECORD: a recorded exit with code {exit_code} is offered, not resumed",
              verdict == "offer-after-recorded-exit"
              and detail == (exit_code, recorded_at, "resume-me"),
              (verdict, detail))
        report = workspace.recover()
        check(f"EXIT RECORD: code {exit_code} is reported as not relaunched, and nothing launches",
              report.startswith(
                  f"exited-seat: {recovery.SEAT_NOT_RELAUNCHED_AFTER_RECORDED_EXIT_REPORT_MARKER} — "
                  f"its supervisor recorded at {recorded_at} that its agent exited with "
                  + ("an unknown exit code" if exit_code is None else f"exit code {exit_code}")
                  + " and stopped without launching a successor, so this is not treated "
                    "as a crash and nothing is launched; ")
              and workspace.launches == [],
              (report, workspace.launches))

    workspace = Workspace(root / "exit-record-absent", name="exited-seat")
    all_dead()
    capture_launches(workspace)
    write_transcript(workspace.project_directory(), "resume-me", "real work", records=4)
    (workspace.handoffs / f"{workspace.name}-supervisor-state.json").write_text(
        json.dumps({"consumed_counter": None, "session_id": "resume-me", "generation": 3}),
        encoding="utf-8")
    verdict, detail = workspace.assess()
    check("EXIT RECORD: a seat with no exit record is still resumed",
          verdict == "resume" and detail[0] == "resume-me", (verdict, detail))

    # The report names both ways back by hand, each carrying what launch_seat
    # would pass, and --ignite-fallback says the same and launches nothing. A
    # dry run quotes that report whole, after the question an operator at a
    # terminal would be asked (ruled 2026-09-18).
    workspace = Workspace(root / "exit-record-report", name="exited-seat")
    all_dead()
    capture_launches(workspace)
    write_transcript(workspace.project_directory(), "resume-me", "real work", records=4)
    recorded_at = record_an_agent_exit(workspace, 0)
    # The by-hand resume carries its own first prompt (review 5240813304): without
    # one, the supervisor's default for a resume tells the agent the previous
    # session ended without writing a handoff — untrue of a seat that is here
    # because its exit was recorded. (Until 2026-09-18 that default also called
    # it a crash and said "died"; both are gone, and the default is still the
    # wrong sentence for a recorded exit.)
    # A dry run names the file and writes nothing; the real run writes it, so
    # the printed command works when it is typed.
    by_hand_prompt_path = (workspace.handoffs
                           / "exited-seat-by-hand-resume-after-recorded-exit-prompt.md")
    report_dry = workspace.recover(dry_run=True)
    check("EXIT RECORD: a dry run names the by-hand resume's prompt file and writes nothing",
          f"--first-prompt-file {by_hand_prompt_path}" in report_dry
          and not by_hand_prompt_path.exists(),
          (report_dry, sorted(path.name for path in workspace.handoffs.iterdir())))
    report = workspace.recover()
    resume_command = recovery.by_hand_launch_command_for_seat(
        workspace.name, workspace.seat_directory, workspace.handoffs,
        "--resume-session-id resume-me", first_prompt_file=by_hand_prompt_path)
    fresh_command = recovery.by_hand_launch_command_for_seat(
        workspace.name, workspace.seat_directory, workspace.handoffs, "")
    check("EXIT RECORD: the report names the by-hand resume and the by-hand fresh launch",
          report.endswith(f"; to bring it back by hand resuming session resume-me: "
                          f"{resume_command}; or as a fresh session: {fresh_command}"),
          report)
    check("EXIT RECORD: --ignite-fallback offers the same, and neither launches anything",
          workspace.recover(ignite_fallback=True) == report
          and workspace.launches == [],
          (report, workspace.launches))
    check("EXIT RECORD: a dry run quotes the question, what a yes does, and that report whole",
          report_dry == ("exited-seat: would ask an operator at a terminal — \"exited-seat "
                         "stopped on purpose. Restart it anyway? y/n\" — and on a yes restart "
                         "the seat resuming session resume-me; on a no, or with no terminal, "
                         "it reports: " + report[len("exited-seat: "):])
          and report.startswith("exited-seat: ")
          and workspace.launches == [],
          (report_dry, report))
    expected_launcher_word = (str(recovery.launcher_path()) if recovery.launcher_path()
                              else "launch-claude-ubuntu")
    resume_command_words = shlex.split(resume_command.replace(" (on the Mac)", ""))
    check("EXIT RECORD: the by-hand resume command parses into the launch_seat environment",
          resume_command_words[:4] == [
              f"NEDSCHORUS_AGENTS_ROOT={workspace.agents_root}",
              "LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS="
              f"--handoff-dir {shlex.quote(str(workspace.handoffs))} --resume-session-id resume-me",
              expected_launcher_word, workspace.name],
          resume_command_words)
    check("EXIT RECORD: and passes the launcher its first-prompt file, as launch_seat does",
          resume_command_words[4:] == ["--first-prompt-file", str(by_hand_prompt_path)],
          resume_command_words)
    by_hand_prompt = (by_hand_prompt_path.read_text(encoding="utf-8")
                      if by_hand_prompt_path.is_file() else "")
    check("EXIT RECORD: the by-hand resume's first prompt is the deliberate-stop one, byte "
          "for byte",
          by_hand_prompt == FIRST_PROMPT_FOR_A_BY_HAND_RESUME_AFTER_A_RECORDED_EXIT,
          by_hand_prompt)
    check("EXIT RECORD: and it says neither crash nor died, nor names an operator it never met",
          by_hand_prompt
          and not any(word in by_hand_prompt.lower() for word in ("crash", "died", "operator")),
          by_hand_prompt)
    # What the supervisor itself would do with the printed command: its first
    # launch resumes that session with the file's words, not with its crash
    # default. The command without the file is what this tool printed before.
    first_turn, resumed = supervisor_first_turn_for_a_by_hand_command(
        resume_command, workspace)
    check("EXIT RECORD: the printed resume starts the supervisor on the deliberate-stop prompt",
          resumed is True
          and first_turn == FIRST_PROMPT_FOR_A_BY_HAND_RESUME_AFTER_A_RECORDED_EXIT,
          (first_turn, resumed))
    first_turn_without_the_file, _ = supervisor_first_turn_for_a_by_hand_command(
        resume_command.replace(f" --first-prompt-file {shlex.quote(str(by_hand_prompt_path))}",
                               ""), workspace)
    check("EXIT RECORD: (without the file, the same command starts it on the crash default)",
          "crash" in first_turn_without_the_file, first_turn_without_the_file)
    real_launcher_path = recovery.launcher_path
    try:
        patch("launcher_path", lambda: None)
        box_command = recovery.by_hand_launch_command_for_seat(
            workspace.name, workspace.seat_directory, workspace.handoffs, "")
    finally:
        patch("launcher_path", real_launcher_path)
    check("EXIT RECORD: off the Mac the by-hand command names launch-claude-ubuntu, on the Mac",
          box_command.endswith(f" launch-claude-ubuntu {workspace.name} (on the Mac)"),
          box_command)

    # With nothing to resume, the offer stands in for the ignite and names only
    # the fresh launch.
    workspace = Workspace(root / "exit-record-no-transcript", name="exited-seat")
    all_dead()
    capture_launches(workspace)
    record_an_agent_exit(workspace, 0)
    verdict, detail = workspace.assess()
    report = workspace.recover()
    check("EXIT RECORD: a recorded exit with nothing to resume is offered, not ignited",
          verdict == "offer-after-recorded-exit" and detail[2] is None
          and report.endswith("; to bring it back by hand as a fresh session: "
                              + recovery.by_hand_launch_command_for_seat(
                                  workspace.name, workspace.seat_directory,
                                  workspace.handoffs, ""))
          and workspace.launches == [],
          (verdict, detail, report, workspace.launches))
    report_dry = workspace.recover(dry_run=True)
    check("EXIT RECORD: and its dry run says a yes would restart it as a fresh session",
          report_dry == ("exited-seat: would ask an operator at a terminal — \"exited-seat "
                         "stopped on purpose. Restart it anyway? y/n\" — and on a yes restart "
                         "the seat as a fresh session; on a no, or with no terminal, it "
                         "reports: " + report[len("exited-seat: "):])
          and workspace.launches == [],
          (report_dry, report))

    # What the record does not reach: a waiting handoff still defers to
    # boot-ignition, and a live tmux session with no confirmed supervisor is
    # still refused (user-ruled 2026-09-16).
    workspace = Workspace(root / "exit-record-waiting-handoff", name="exited-seat")
    all_dead()
    record_an_agent_exit(workspace, 0)
    (workspace.handoffs / f"{workspace.name}-handoff.md").write_text(
        "# Handoff\nrestart-counter: 5\nnext-step: continue\n", encoding="utf-8")
    verdict, detail = workspace.assess()
    check("EXIT RECORD: a waiting handoff still defers to boot-ignition over the record",
          verdict == "defer-to-boot-ignition", (verdict, detail))
    workspace = Workspace(root / "exit-record-live-tmux", name="exited-seat")
    all_dead()
    record_an_agent_exit(workspace, 0)
    patch("tmux_session_alive_anywhere",
          lambda name: (True, f"tmux session '{name}' is alive on socket '{name}'"))
    verdict, detail = workspace.assess()
    check("EXIT RECORD: a live tmux session is still refused whatever the record says",
          verdict == "refuse" and "never touches a live tmux session" in detail,
          (verdict, detail))

    # Through main: logged in its report class, counted as not recovered, and
    # under --all a recorded seat launches nothing while a crashed seat beside
    # it is still resumed.
    workspace = Workspace(root / "exit-record-main", name="all-seat-exited")
    (workspace.agents_root / "all-seat-crashed").mkdir()
    for name in ("all-seat-exited", "all-seat-crashed"):
        write_transcript(recovery.harness_project_directory(
            workspace.agents_root / name, workspace.projects),
            f"resume-{name}", "real work", records=4)
    all_dead()
    capture_launches(workspace)
    record_an_agent_exit(workspace, 0)
    printed = io.StringIO()
    with redirect_stdout(printed):
        exit_code = recovery.main(["--all", "--agents-root", str(workspace.agents_root),
                                   "--handoff-dir", str(workspace.handoffs),
                                   "--projects-root", str(workspace.projects)])
    log_path = workspace.handoffs / "recover-crashed-seats-log.txt"
    logged = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
    logged_lines = logged.splitlines()
    check("EXIT RECORD: --all resumes the crashed seat and launches nothing for the exited one",
          [launch[0] for launch in workspace.launches] == ["all-seat-crashed"],
          workspace.launches)
    check("EXIT RECORD: the offer is logged in its report class, timestamped, and the run exits 1",
          exit_code == 1 and len(logged_lines) == 2  # --all goes in name order
          and "+00:00 all-seat-crashed: relaunched resuming resume-all-seat-crashed"
              in logged_lines[0]
          and logged_lines[1][:4].isdigit()
          and "+00:00 all-seat-exited: NOT RELAUNCHED AFTER A RECORDED EXIT — its supervisor "
              "recorded at " in logged_lines[1],
          (exit_code, logged, printed.getvalue()))

    # The first prompts after a recorded exit are this machinery's own openers,
    # so a fresh restart that died on its first turn before working is passed
    # over like any other failed successor, never resumed in place of real work.
    workspace = Workspace(root / "exit-record-stillborn-restart")
    all_dead()
    write_transcript(workspace.project_directory(), "older-real", "real work",
                     age_seconds=3600, records=6)
    write_transcript(workspace.project_directory(), "stillborn-restart",
                     FIRST_PROMPT_FOR_AN_OPERATORS_RESTART_AS_A_FRESH_SESSION, records=1)
    verdict, detail = workspace.assess()
    check("EXIT RECORD: a fresh restart that died before working is skipped for real work",
          verdict == "resume" and detail[0] == "older-real"
          and recovery.FIRST_PROMPT_AFTER_RECORDED_EXIT_MARKER
              in FIRST_PROMPT_FOR_A_BY_HAND_RESUME_AFTER_A_RECORDED_EXIT
          and recovery.FIRST_PROMPT_AFTER_RECORDED_EXIT_MARKER
              in FIRST_PROMPT_FOR_AN_OPERATORS_RESTART_RESUMING,
          (verdict, detail))

    # --- a recorded exit with no leftover session is asked about too -------
    # Ruled 2026-09-18 in a walk: a seat carrying a recorded exit whose tmux
    # session is gone — after a reboot, say — is asked the question a seat
    # behind a leftover shell is asked, when an operator is at a terminal and
    # this is not a dry run. A yes restarts it exactly as the leftover-shell
    # yes does; a no, or nobody to ask, leaves the NOT RELAUNCHED line it has
    # always had. The question is worded by the recorded exit code (ruled the
    # same day): a supervisor also records the exit of an agent that died
    # with an error while it watched, and for that seat "stopped on purpose"
    # can be false. The user's words, spelled out byte for byte and never
    # derived from the function that composes them.
    question_for_a_seat_stopped_on_purpose = (
        "seat-a stopped on purpose. Restart it anyway? y/n")
    question_for_a_seat_that_stopped_with_exit_code_1 = (
        "seat-a stopped with exit code 1. Restart it? y/n")
    question_for_a_seat_that_stopped_with_exit_code_137 = (
        "seat-a stopped with exit code 137. Restart it? y/n")
    question_for_a_recorded_exit_code = (
        (0, question_for_a_seat_stopped_on_purpose),
        (None, question_for_a_seat_stopped_on_purpose),
        (1, question_for_a_seat_that_stopped_with_exit_code_1),
        (137, question_for_a_seat_that_stopped_with_exit_code_137))
    every_recorded_exit_question = (
        question_for_a_seat_stopped_on_purpose, question_for_a_seat_that_stopped_with_exit_code_1,
        question_for_a_seat_that_stopped_with_exit_code_137)
    # With no leftover shell nothing was closed, so the line says only whose
    # word the restart was on — never the leftover shell's suffix.
    the_operator_said_to_restart_it_and_nothing_was_closed = (
        " (the operator said to restart it)")

    def operator_restart_prompt_path_for(workspace):
        return workspace.handoffs / "seat-a-operator-restart-after-recorded-exit-prompt.md"

    def by_hand_prompt_path_for(workspace):
        return workspace.handoffs / "seat-a-by-hand-resume-after-recorded-exit-prompt.md"

    def a_seat_with_a_recorded_exit_and_no_session(directory_name, exit_code, resumable=True):
        """(workspace, recorded_at): seat-a, fully dead with no tmux session
        at all, its supervisor's record of its agent's exit on disk, and a
        transcript to resume unless resumable is False."""
        workspace = Workspace(root / directory_name, name="seat-a")
        all_dead()
        capture_launches(workspace)
        if resumable:
            write_transcript(workspace.project_directory(), "resume-me", "real work",
                             records=4)
        return workspace, record_an_agent_exit(workspace, exit_code)

    def the_not_relaunched_line(workspace, recorded_at, code_text):
        """The line such a seat has always got, composed here byte for byte."""
        resume_command = recovery.by_hand_launch_command_for_seat(
            "seat-a", workspace.seat_directory, workspace.handoffs,
            "--resume-session-id resume-me",
            first_prompt_file=by_hand_prompt_path_for(workspace))
        fresh_command = recovery.by_hand_launch_command_for_seat(
            "seat-a", workspace.seat_directory, workspace.handoffs, "")
        return ("seat-a: NOT RELAUNCHED AFTER A RECORDED EXIT — its supervisor recorded at "
                f"{recorded_at} that its agent exited with {code_text} and stopped without "
                "launching a successor, so this is not treated as a crash and nothing is "
                "launched; to bring it back by hand resuming session resume-me: "
                f"{resume_command}; or as a fresh session: {fresh_command}")

    # The question for each recorded code, and a no to it, which launches
    # nothing and leaves the line the seat gets with nobody to ask.
    for exit_code, expected_question in question_for_a_recorded_exit_code:
        workspace, recorded_at = a_seat_with_a_recorded_exit_and_no_session(
            f"no-leftover-exit-code-{exit_code}", exit_code)
        report_after_no, seen = recover_with_an_operator_typing(workspace, "n")
        check(f"NO LEFTOVER SESSION: a recorded exit code {exit_code!r} is asked "
              f"{expected_question!r}, byte for byte, and nothing else is shown",
              seen == f"{expected_question} ", seen)
        no_operator_terminal()
        check(f"NO LEFTOVER SESSION: a no to it (code {exit_code!r}) launches nothing and "
              "reports what nobody-to-ask reports",
              workspace.launches == [] and report_after_no == workspace.recover()
              and recovery.SEAT_NOT_RELAUNCHED_AFTER_RECORDED_EXIT_REPORT_MARKER
                  in report_after_no,
              (workspace.launches, report_after_no))

    # A yes with a session to resume: the recorded session is resumed, on the
    # operator-restart first prompt, after the come-up check, and the line
    # says whose word it was without claiming a shell was closed.
    workspace, recorded_at = a_seat_with_a_recorded_exit_and_no_session(
        "no-leftover-yes-resume", 0)
    report_yes, prompts, seen = recover_recording_every_prompt(workspace)
    launched_prompt = (workspace.launches[0][2].read_text(encoding="utf-8")
                       if workspace.launches and workspace.launches[0][2] else "")
    check("NO LEFTOVER SESSION: at a terminal the question is asked once, through input()",
          prompts == [f"{question_for_a_seat_stopped_on_purpose} "] and seen == "",
          (prompts, seen))
    check("NO LEFTOVER SESSION: a yes resumes the recorded session on the operator-restart "
          "first prompt, byte for byte",
          workspace.launches == [("seat-a", "--resume-session-id resume-me",
                                  operator_restart_prompt_path_for(workspace))]
          and launched_prompt == FIRST_PROMPT_FOR_AN_OPERATORS_RESTART_RESUMING
          and not by_hand_prompt_path_for(workspace).exists(),
          (workspace.launches, launched_prompt))
    check("NO LEFTOVER SESSION: and its line says the operator said to restart it, and "
          "nothing about a leftover shell",
          report_yes == (
              f"seat-a: relaunched resuming resume-me after its supervisor recorded at "
              f"{recorded_at} that its agent exited with exit code 0"
              + the_operator_said_to_restart_it_and_nothing_was_closed)
          and "leftover" not in report_yes and "closed" not in report_yes
          and not any(marker in report_yes
                      for marker in recovery.SEAT_NOT_RECOVERED_REPORT_MARKERS),
          report_yes)

    # A yes with nothing to resume starts it fresh, on the fresh first prompt;
    # the nonzero code's question restarts it just the same.
    workspace, recorded_at = a_seat_with_a_recorded_exit_and_no_session(
        "no-leftover-yes-fresh", 1, resumable=False)
    report_yes_fresh, seen = recover_with_an_operator_typing(workspace, "y")
    launched_prompt = (workspace.launches[0][2].read_text(encoding="utf-8")
                       if workspace.launches and workspace.launches[0][2] else "")
    check("NO LEFTOVER SESSION: a yes with no session to resume starts the seat fresh, on "
          "the fresh first prompt, byte for byte",
          seen == f"{question_for_a_seat_that_stopped_with_exit_code_1} "
          and workspace.launches == [("seat-a", "", operator_restart_prompt_path_for(workspace))]
          and launched_prompt == FIRST_PROMPT_FOR_AN_OPERATORS_RESTART_AS_A_FRESH_SESSION,
          (seen, workspace.launches, launched_prompt))
    check("NO LEFTOVER SESSION: and its line says so, on the operator's word",
          report_yes_fresh == (
              f"seat-a: relaunched fresh after its supervisor recorded at {recorded_at} that "
              "its agent exited with exit code 1, with no session to resume"
              + the_operator_said_to_restart_it_and_nothing_was_closed),
          report_yes_fresh)

    # --ignite-fallback does not turn that restart into an ignite, as it does
    # not behind a leftover shell.
    workspace, recorded_at = a_seat_with_a_recorded_exit_and_no_session(
        "no-leftover-yes-ignite-fallback", 0)
    (workspace.handoffs / "seat-a-dialog-0007.md").write_text("the dialog", encoding="utf-8")
    report_fallback, seen = recover_with_an_operator_typing(workspace, "y",
                                                            ignite_fallback=True)
    check("NO LEFTOVER SESSION: with --ignite-fallback a yes still resumes",
          [launch[:2] for launch in workspace.launches] == [
              ("seat-a", "--resume-session-id resume-me")]
          and report_fallback.startswith("seat-a: relaunched resuming resume-me after ")
          and "--ignite-fallback" not in report_fallback,
          (workspace.launches, report_fallback))

    # A restart that fails is still reported as one the operator asked for.
    workspace, recorded_at = a_seat_with_a_recorded_exit_and_no_session(
        "no-leftover-yes-launch-fails", 0)
    patch("launch_seat", lambda name, seat_directory, handoff_directory, extra_arguments,
          first_prompt_file=None: 7)
    report_launch_failed, seen = recover_with_an_operator_typing(workspace, "y")
    workspace, recorded_at = a_seat_with_a_recorded_exit_and_no_session(
        "no-leftover-yes-did-not-come-up", 0)
    seat_comes_up(False, "a supervisor started and stopped again within 6s, so the session "
                         "did not survive")
    report_not_up, seen = recover_with_an_operator_typing(workspace, "y")
    check("NO LEFTOVER SESSION: a failed restart on a yes is a failure that says whose word "
          "it was",
          report_launch_failed == ("seat-a: LAUNCH FAILED (exit 7) — the seat is still down"
                                   + the_operator_said_to_restart_it_and_nothing_was_closed)
          and report_not_up == ("seat-a: LAUNCHED BUT DID NOT COME UP — a supervisor started "
                                "and stopped again within 6s, so the session did not survive"
                                + the_operator_said_to_restart_it_and_nothing_was_closed),
          (report_launch_failed, report_not_up))

    # A no: the NOT RELAUNCHED line exactly as it has always been, its by-hand
    # prompt written as it always is, and nothing launched. End of input is a no.
    for typed in ("n", None):
        workspace, recorded_at = a_seat_with_a_recorded_exit_and_no_session(
            f"no-leftover-no-{typed}", 0)
        report_no, seen = recover_with_an_operator_typing(workspace, typed)
        by_hand_prompt = (by_hand_prompt_path_for(workspace).read_text(encoding="utf-8")
                          if by_hand_prompt_path_for(workspace).is_file() else "")
        check(f"NO LEFTOVER SESSION: {'a no' if typed else 'end of input'} gives the NOT "
              "RELAUNCHED line, byte for byte, and launches nothing",
              report_no == the_not_relaunched_line(workspace, recorded_at, "exit code 0")
              and workspace.launches == []
              and by_hand_prompt == FIRST_PROMPT_FOR_A_BY_HAND_RESUME_AFTER_A_RECORDED_EXIT
              and not operator_restart_prompt_path_for(workspace).exists(),
              (report_no, workspace.launches, by_hand_prompt))

    # With nobody at a terminal — at boot, under restart-live-seats-at-login —
    # nothing is asked (input() is never called), nothing is launched, and
    # the line is the one it has always been.
    workspace, recorded_at = a_seat_with_a_recorded_exit_and_no_session(
        "no-leftover-unattended", 137)
    report_unattended, prompts, seen = recover_recording_every_prompt(workspace,
                                                                      at_a_terminal=False)
    check("NO LEFTOVER SESSION: with nobody at a terminal nothing is asked and the line is "
          "unchanged, byte for byte",
          prompts == [] and seen == "" and workspace.launches == []
          and report_unattended == the_not_relaunched_line(workspace, recorded_at,
                                                           "exit code 137")
          and not operator_restart_prompt_path_for(workspace).exists(),
          (prompts, seen, workspace.launches, report_unattended))

    # A dry run asks nobody, even at a terminal, and writes nothing; it
    # quotes the question, what a yes does, and the line a no or nobody to
    # ask gives.
    workspace, recorded_at = a_seat_with_a_recorded_exit_and_no_session(
        "no-leftover-dry-run", 137)
    report_dry, seen = recover_with_an_operator_typing(workspace, "y", dry_run=True)
    written_by_the_dry_run = sorted(path.name for path in workspace.handoffs.glob("*-prompt.md"))
    no_operator_terminal()
    check("NO LEFTOVER SESSION: --dry-run quotes the question and what a yes and a no do, "
          "asking nothing and writing nothing",
          seen == "" and workspace.launches == [] and written_by_the_dry_run == []
          and report_dry == (
              "seat-a: would ask an operator at a terminal — "
              f"\"{question_for_a_seat_that_stopped_with_exit_code_137}\" — and on a yes "
              "restart the seat resuming session resume-me; on a no, or with no terminal, it "
              "reports: "
              + the_not_relaunched_line(workspace, recorded_at, "exit code 137")[
                  len("seat-a: "):]),
          (seen, workspace.launches, written_by_the_dry_run, report_dry))

    # Two seats carrying recorded exits in one --all run at a terminal: each is
    # asked its own question, in name order, and a no to the first does not
    # stop the run reaching the second, which a yes restarts (the user
    # accepted one question per such seat).
    workspace = Workspace(root / "no-leftover-two-seats", name="two-seats-first")
    (workspace.agents_root / "two-seats-second").mkdir()
    for name, exit_code in (("two-seats-first", 0), ("two-seats-second", 1)):
        write_transcript(recovery.harness_project_directory(
            workspace.agents_root / name, workspace.projects),
            f"resume-{name}", "real work", records=4)
        recovery.supervisor.record_agent_exit_in_supervisor_state(
            workspace.handoffs / f"{name}-supervisor-state.json",
            {"consumed_counter": None, "session_id": f"resume-{name}", "generation": 3},
            exit_code)
    all_dead()
    capture_launches(workspace)
    an_operator_terminal()
    printed = io.StringIO()
    stdin_before = sys.stdin
    sys.stdin = io.StringIO("n\ny\n")
    try:
        with redirect_stdout(printed):
            exit_code = recovery.main(["--all", "--agents-root", str(workspace.agents_root),
                                       "--handoff-dir", str(workspace.handoffs),
                                       "--projects-root", str(workspace.projects)])
    finally:
        sys.stdin = stdin_before
        no_operator_terminal()
    printed = printed.getvalue()
    first_question = "two-seats-first stopped on purpose. Restart it anyway? y/n "
    second_question = "two-seats-second stopped with exit code 1. Restart it? y/n "
    first_line = "recover-crashed-seats: two-seats-first: NOT RELAUNCHED AFTER A RECORDED EXIT — "
    second_line = ("recover-crashed-seats: two-seats-second: relaunched resuming "
                   "resume-two-seats-second")
    log_path = workspace.handoffs / "recover-crashed-seats-log.txt"
    logged_lines = (log_path.read_text(encoding="utf-8").splitlines()
                    if log_path.is_file() else [])
    check("NO LEFTOVER SESSION: two recorded-exit seats in one run are each asked, and a no "
          "to the first still reaches the second",
          all(printed.count(text) == 1
              for text in (first_question, first_line, second_question, second_line))
          and (printed.index(first_question) < printed.index(first_line)
               < printed.index(second_question) < printed.index(second_line)),
          printed)
    check("NO LEFTOVER SESSION: the first is left down and the second restarted on the "
          "operator's word, and the run exits 1 for the first",
          [launch[:2] for launch in workspace.launches] == [
              ("two-seats-second", "--resume-session-id resume-two-seats-second")]
          and exit_code == 1 and len(logged_lines) == 2
          and "two-seats-first: NOT RELAUNCHED AFTER A RECORDED EXIT" in logged_lines[0]
          and logged_lines[1].endswith(
              "two-seats-second: relaunched resuming resume-two-seats-second after its "
              "supervisor recorded at "
              + recovery.supervisor.read_supervisor_state(
                  workspace.handoffs / "two-seats-second-supervisor-state.json")[
                  recovery.supervisor.AGENT_EXIT_RECORDED_AT_STATE_KEY]
              + " that its agent exited with exit code 1"
              + the_operator_said_to_restart_it_and_nothing_was_closed),
          (workspace.launches, exit_code, logged_lines))

    # --- the leftover idle shell is a question, not a refusal ---------------
    # Ruled 2026-09-17 (the #120 overview, § Ruled 2026-09-02): with an
    # operator at a terminal, a seat whose tmux session is alive with no
    # confirmed supervisor and nothing but an idle shell in it is ASKED about;
    # run unattended it is refused exactly as it was under the 2026-09-16
    # ruling. Nothing is closed that cannot be PROVEN idle, whoever is asking.
    #
    # The question asks whether to restart the seat, worded by what the
    # seat's reassessment will do once the shell is closed. Ruled 2026-09-18 in
    # a walk, of the words before these: "that is a confusing y/n question.
    # kind of a double negative. I don't care about 'thes session'. I care
    # about the reboot-test. perhaps resume reboot-test? Y/N." — "restart",
    # not "resume", which here means picking up the last conversation. The two
    # ruled questions are the user's approved words, so they are spelled out
    # here byte for byte and never derived from the function that composes
    # them. A yes restarts the seat on both, a recorded exit included. The
    # recorded exit's questions, worded by its code, are spelled out above.
    question_that_restarts_the_seat = "Restart seat-a? y/n"
    # Ruled 2026-09-18: the question for a seat whose waiting handoff asks to
    # be consulted, showing its reason first.
    question_for_a_seat_that_asked_to_be_consulted = (
        "seat-a's handoff says: the user asked to be consulted before a relaunch. "
        "Restart it? y/n")
    every_leftover_shell_question = (
        question_that_restarts_the_seat, *every_recorded_exit_question,
        question_for_a_seat_that_asked_to_be_consulted)
    the_operator_said_to_restart_it = (
        "(the operator said to restart it, so the leftover shell was closed first: closed "
        "the leftover shell — retired the tmux session on socket seat-a)")

    def asked_only(question, seen):
        """The operator saw exactly this one of the questions, followed by the
        space input() puts after it, and none of the others."""
        return (f"{question} " in seen
                and all(other not in seen
                        for other in every_leftover_shell_question if other != question))

    def capture_launches_with_what_was_retired_by_then(workspace, retired):
        """capture_launches, each launch also recording which sessions had
        been retired when it ran: a restart must close the leftover shell
        BEFORE it launches into the seat's name."""
        def fake_launch(name, seat_directory, handoff_directory, extra_arguments,
                        first_prompt_file=None):
            workspace.launches.append((name, extra_arguments, first_prompt_file,
                                       list(retired)))
            return 0
        patch("launch_seat", fake_launch)
        seat_comes_up()

    def a_seat_behind_a_leftover_shell(directory_name, pane_process_ids=(4242,)):
        """A crashed seat with a resumable transcript, its tmux session alive
        with no supervisor, and that session proven to be an idle shell."""
        workspace = Workspace(root / directory_name)
        all_dead()
        capture_launches(workspace)
        write_transcript(workspace.project_directory(), "resume-me", "real work", records=4)
        a_live_tmux_session()
        a_leftover_idle_shell(pane_process_ids=pane_process_ids)
        # lsof still names the pane that was just closed: it dies on tmux's
        # signal, not on this script's clock. The exemption is what keeps that
        # from refusing the seat the operator just cleared.
        lsof_reports_rooted(list(pane_process_ids))
        return workspace

    workspace = a_seat_behind_a_leftover_shell("leftover-shell-yes")
    retired = []
    capture_retires(retired)
    report, seen = recover_with_an_operator_typing(workspace, "y")
    check("LEFTOVER SHELL: a seat that would resume is asked \"Restart seat-a? y/n\", "
          "byte for byte",
          asked_only(question_that_restarts_the_seat, seen), seen)
    check("LEFTOVER SHELL: a yes retires the session and the assessment goes on without it",
          retired == ["seat-a"]
          and [launch[:2] for launch in workspace.launches] == [
              ("seat-a", "--resume-session-id resume-me")]
          and report.startswith("seat-a: relaunched resuming resume-me")
          and report.endswith(" " + the_operator_said_to_restart_it),
          (retired, workspace.launches, report, seen))

    # A no changes nothing at all, and says what it said before the question
    # existed. Measured against the report the SAME seat gets with nobody to
    # ask, which is the 2026-09-16 refusal itself.
    def the_refusal_with_nobody_to_ask(workspace):
        no_operator_terminal()
        unattended_seen = io.StringIO()
        with redirect_stdout(unattended_seen):
            return workspace.recover(), unattended_seen.getvalue()

    def dry_run_ending_quoting_the_refusal(workspace):
        """How a dry-run line that asks now ends (ruled 2026-09-18): the
        2026-09-16 refusal a no or nobody to ask gives, spelled out byte for
        byte, carrying the REFUSED that main counts."""
        lock_path = workspace.handoffs / "seat-a-supervisor.lock"
        return ("; on a no, or with no terminal, it reports: REFUSED — tmux session 'seat-a' "
                "is alive on socket 'seat-a', but no live supervisor of this seat is confirmed "
                f"(no supervisor lock at {lock_path}) — this tool never touches a live tmux "
                "session. If the seat's supervisor has exited, that session is the shell an "
                "attached launch leaves open: exit it, then rerun this recovery")

    workspace = a_seat_behind_a_leftover_shell("leftover-shell-no")
    retired = []
    capture_retires(retired)
    report_after_no, seen = recover_with_an_operator_typing(workspace, "n")
    report_unattended, unattended_seen = the_refusal_with_nobody_to_ask(workspace)
    check("LEFTOVER SHELL: a no retires nothing, launches nothing, and reports as today",
          retired == [] and workspace.launches == []
          and report_after_no == report_unattended
          and "REFUSED" in report_after_no
          and "this tool never touches a live tmux session" in report_after_no
          and "exit it, then rerun this recovery" in report_after_no,
          (retired, workspace.launches, report_after_no, report_unattended))
    check("LEFTOVER SHELL: with no terminal nothing is asked and the refusal is unchanged",
          retired == [] and workspace.launches == [] and unattended_seen == "",
          (retired, workspace.launches, unattended_seen))

    # A session that cannot be shown to be idle is refused with no question at
    # all — at a terminal exactly as without one.
    workspace = a_seat_behind_a_leftover_shell("leftover-shell-busy-pane")
    no_leftover_idle_shell("a pane of session 'seat-a' on socket 'seat-a' is running vim, "
                           "not an idle shell")
    retired = []
    capture_retires(retired)
    report_busy, busy_seen = recover_with_an_operator_typing(workspace, "y")
    report_busy_unattended, _ = the_refusal_with_nobody_to_ask(workspace)
    check("LEFTOVER SHELL: a pane running real work is refused with no question, terminal or not",
          retired == [] and workspace.launches == [] and busy_seen == ""
          and report_busy == report_busy_unattended
          and "this tool never touches a live tmux session" in report_busy,
          (retired, workspace.launches, report_busy, busy_seen))

    # End of input — a pipe, a closed terminal, an interrupt — is a no.
    workspace = a_seat_behind_a_leftover_shell("leftover-shell-eof")
    retired = []
    capture_retires(retired)
    report_after_eof, seen = recover_with_an_operator_typing(workspace, None)
    check("LEFTOVER SHELL: end of input answers no",
          retired == [] and workspace.launches == []
          and report_after_eof == the_refusal_with_nobody_to_ask(workspace)[0],
          (retired, report_after_eof, seen))
    for typed in ("", "yes please", "Y", "yes"):
        answered_yes = []
        stdin_before = sys.stdin
        sys.stdin = io.StringIO(f"{typed}\n")
        try:
            with redirect_stdout(io.StringIO()):
                answered_yes.append(
                    recovery.ask_operator_yes_or_no(question_that_restarts_the_seat))
        finally:
            sys.stdin = stdin_before
        check(f"QUESTION: the answer {typed!r} is "
              f"{'yes' if typed in ('Y', 'yes') else 'no'}",
              answered_yes == [typed in ("Y", "yes")], (typed, answered_yes))

    # A dry run reports the question and asks nobody, whoever is at the
    # terminal, because --dry-run promises to change nothing. It ends with the
    # line a no or nobody to ask gives, quoted whole (ruled 2026-09-18), so
    # main counts the seat by that line's REFUSED.
    workspace = a_seat_behind_a_leftover_shell("leftover-shell-dry-run")
    retired = []
    capture_retires(retired)
    report_dry, seen = recover_with_an_operator_typing(workspace, "y", dry_run=True)
    check("LEFTOVER SHELL: --dry-run reports the question, asks nothing, closes nothing",
          retired == [] and workspace.launches == [] and seen == ""
          and report_dry == ("seat-a: would ask an operator at a terminal — "
                             f'"{question_that_restarts_the_seat}" — and on a yes close that '
                             "session and assess the seat without it (it is one pane at a "
                             "shell)" + dry_run_ending_quoting_the_refusal(workspace)),
          (retired, workspace.launches, report_dry, seen))
    report_unattended, _ = the_refusal_with_nobody_to_ask(workspace)
    check("LEFTOVER SHELL (ruled 2026-09-18): --dry-run quotes the unattended refusal whole",
          report_dry.endswith("; on a no, or with no terminal, it reports: "
                              + report_unattended[len("seat-a: "):])
          and retired == [],
          (report_dry, report_unattended, retired))
    # And the question it reports is the predicted one, with what a yes does:
    # a seat stopped on purpose is restarted, resuming its session if it has one.
    workspace = a_seat_behind_a_leftover_shell("leftover-shell-dry-run-exit-record")
    record_an_agent_exit(workspace, 0)
    retired = []
    capture_retires(retired)
    report_dry, seen = recover_with_an_operator_typing(workspace, "y", dry_run=True)
    check("LEFTOVER SHELL: --dry-run carries the stopped-on-purpose question and the resume",
          retired == [] and workspace.launches == [] and seen == ""
          and report_dry == ("seat-a: would ask an operator at a terminal — "
                             f'"{question_for_a_seat_stopped_on_purpose}" — and on a yes close '
                             "that session and restart the seat resuming session resume-me "
                             "(it is one pane at a shell)"
                             + dry_run_ending_quoting_the_refusal(workspace))
          and not any(workspace.handoffs.glob("*-prompt.md")),
          (retired, workspace.launches, report_dry, seen))
    workspace = a_seat_behind_a_leftover_shell("leftover-shell-dry-run-exit-record-fresh")
    (workspace.project_directory() / "resume-me.jsonl").unlink()
    record_an_agent_exit(workspace, 0)
    retired = []
    capture_retires(retired)
    report_dry, seen = recover_with_an_operator_typing(workspace, "y", dry_run=True)
    check("LEFTOVER SHELL: --dry-run says a seat stopped on purpose with nothing to resume "
          "restarts fresh",
          retired == [] and workspace.launches == [] and seen == ""
          and report_dry == ("seat-a: would ask an operator at a terminal — "
                             f'"{question_for_a_seat_stopped_on_purpose}" — and on a yes close '
                             "that session and restart the seat as a fresh session (it is one "
                             "pane at a shell)" + dry_run_ending_quoting_the_refusal(workspace)),
          (retired, workspace.launches, report_dry, seen))

    # Ruled 2026-09-18: a seat carrying a recorded exit is asked "stopped on
    # purpose. Restart it anyway?", and a yes RESTARTS it — the rule that such
    # a seat is not brought back is about this tool doing it on its own. The
    # leftover shell is retired first, then the seat is launched resuming its
    # session, on a first prompt that says what was recorded and never "crash".
    workspace = a_seat_behind_a_leftover_shell("leftover-shell-exit-record")
    recorded_at = record_an_agent_exit(workspace, 0)
    retired = []
    capture_retires(retired)
    capture_launches_with_what_was_retired_by_then(workspace, retired)
    report_recorded, seen = recover_with_an_operator_typing(workspace, "y")
    check("LEFTOVER SHELL: a seat with a recorded exit is asked \"seat-a stopped on purpose. "
          "Restart it anyway? y/n\", byte for byte",
          asked_only(question_for_a_seat_stopped_on_purpose, seen), seen)
    check("LEFTOVER SHELL: and a yes retires its session, THEN launches it resuming its session",
          retired == ["seat-a"]
          and [launch[:2] + launch[3:] for launch in workspace.launches] == [
              ("seat-a", "--resume-session-id resume-me", ["seat-a"])],
          (retired, workspace.launches))
    operator_restart_prompt_path = (workspace.handoffs
                                    / "seat-a-operator-restart-after-recorded-exit-prompt.md")
    launched_prompt = (workspace.launches[0][2].read_text(encoding="utf-8")
                       if workspace.launches and workspace.launches[0][2] else "")
    check("LEFTOVER SHELL: on the deliberate-stop first prompt, byte for byte, never the crash one",
          workspace.launches and workspace.launches[0][2] == operator_restart_prompt_path
          and launched_prompt == FIRST_PROMPT_FOR_AN_OPERATORS_RESTART_RESUMING
          and "crash" not in launched_prompt.lower() and "died" not in launched_prompt.lower(),
          (workspace.launches, launched_prompt))
    check("LEFTOVER SHELL: and its line says it was relaunched, on the operator's word",
          report_recorded == (
              f"seat-a: relaunched resuming resume-me after its supervisor recorded at "
              f"{recorded_at} that its agent exited with exit code 0 "
              + the_operator_said_to_restart_it)
          and not any(marker in report_recorded
                      for marker in recovery.SEAT_NOT_RECOVERED_REPORT_MARKERS),
          report_recorded)

    # With nothing to resume, the same yes starts it fresh, on a first prompt
    # that says so.
    workspace = a_seat_behind_a_leftover_shell("leftover-shell-exit-record-fresh")
    (workspace.project_directory() / "resume-me.jsonl").unlink()
    recorded_at = record_an_agent_exit(workspace, None)
    retired = []
    capture_retires(retired)
    capture_launches_with_what_was_retired_by_then(workspace, retired)
    report_fresh, seen = recover_with_an_operator_typing(workspace, "y")
    launched_prompt = (workspace.launches[0][2].read_text(encoding="utf-8")
                       if workspace.launches and workspace.launches[0][2] else "")
    check("LEFTOVER SHELL: a yes on a recorded exit with nothing to resume retires, then starts "
          "it fresh",
          asked_only(question_for_a_seat_stopped_on_purpose, seen)
          and retired == ["seat-a"]
          and [launch[:2] + launch[3:] for launch in workspace.launches] == [
              ("seat-a", "", ["seat-a"])]
          and launched_prompt == FIRST_PROMPT_FOR_AN_OPERATORS_RESTART_AS_A_FRESH_SESSION
          and "crash" not in launched_prompt.lower() and "died" not in launched_prompt.lower()
          and report_fresh == (
              f"seat-a: relaunched fresh after its supervisor recorded at {recorded_at} that "
              "its agent exited with an unknown exit code, with no session to resume "
              + the_operator_said_to_restart_it),
          (retired, workspace.launches, launched_prompt, report_fresh))

    # --ignite-fallback does not turn that restart into an ignite: the degraded
    # restart's prompt says the session ended without writing a handoff, which the
    # record says it did not, and the ruling names resume-or-fresh only.
    workspace = a_seat_behind_a_leftover_shell("leftover-shell-exit-record-ignite-fallback")
    record_an_agent_exit(workspace, 0)
    (workspace.handoffs / "seat-a-dialog-0007.md").write_text("the dialog", encoding="utf-8")
    retired = []
    capture_retires(retired)
    report_fallback, seen = recover_with_an_operator_typing(workspace, "y", ignite_fallback=True)
    check("LEFTOVER SHELL: with --ignite-fallback a yes on a recorded exit still resumes",
          [launch[:2] for launch in workspace.launches] == [
              ("seat-a", "--resume-session-id resume-me")]
          and report_fallback.startswith("seat-a: relaunched resuming resume-me after ")
          and "--ignite-fallback" not in report_fallback,
          (workspace.launches, report_fallback))

    # A no on the same question changes nothing: nothing retired, nothing
    # launched, no prompt written, and the refusal the seat gets unattended.
    workspace = a_seat_behind_a_leftover_shell("leftover-shell-exit-record-no")
    record_an_agent_exit(workspace, 0)
    retired = []
    capture_retires(retired)
    report_recorded_no, seen = recover_with_an_operator_typing(workspace, "n")
    check("LEFTOVER SHELL: a no to a seat stopped on purpose leaves everything as it is",
          asked_only(question_for_a_seat_stopped_on_purpose, seen)
          and retired == [] and workspace.launches == []
          and not any(workspace.handoffs.glob("*-prompt.md"))
          and report_recorded_no == the_refusal_with_nobody_to_ask(workspace)[0],
          (retired, workspace.launches, report_recorded_no))

    # Behind a leftover shell too, the question is worded by the recorded
    # exit code (ruled 2026-09-18), and a no to any of them changes nothing.
    for exit_code, expected_question in question_for_a_recorded_exit_code:
        workspace = a_seat_behind_a_leftover_shell(
            f"leftover-shell-exit-record-code-{exit_code}")
        record_an_agent_exit(workspace, exit_code)
        retired = []
        capture_retires(retired)
        report_code_no, seen = recover_with_an_operator_typing(workspace, "n")
        check(f"LEFTOVER SHELL: a recorded exit code {exit_code!r} is asked "
              f"{expected_question!r}, byte for byte",
              asked_only(expected_question, seen)
              and retired == [] and workspace.launches == []
              and report_code_no == the_refusal_with_nobody_to_ask(workspace)[0],
              (seen, retired, workspace.launches, report_code_no))

    # And a yes to the nonzero code's question restarts the seat just as a yes
    # to the stopped-on-purpose one does.
    workspace = a_seat_behind_a_leftover_shell("leftover-shell-exit-record-code-1-yes")
    recorded_at = record_an_agent_exit(workspace, 1)
    retired = []
    capture_retires(retired)
    capture_launches_with_what_was_retired_by_then(workspace, retired)
    report_code_1_yes, seen = recover_with_an_operator_typing(workspace, "y")
    check("LEFTOVER SHELL: a yes to \"seat-a stopped with exit code 1. Restart it? y/n\" "
          "retires the session, then resumes the seat on the operator-restart prompt",
          asked_only(question_for_a_seat_that_stopped_with_exit_code_1, seen)
          and retired == ["seat-a"]
          and workspace.launches == [
              ("seat-a", "--resume-session-id resume-me",
               workspace.handoffs / "seat-a-operator-restart-after-recorded-exit-prompt.md",
               ["seat-a"])]
          and report_code_1_yes == (
              f"seat-a: relaunched resuming resume-me after its supervisor recorded at "
              f"{recorded_at} that its agent exited with exit code 1 "
              + the_operator_said_to_restart_it),
          (seen, retired, workspace.launches, report_code_1_yes))

    # With nobody to ask, the same seat is refused exactly as before the
    # question's words depended on anything: one assessment, nothing printed,
    # nothing closed, and the 2026-09-16 refusal byte for byte.
    workspace = a_seat_behind_a_leftover_shell("leftover-shell-exit-record-unattended")
    record_an_agent_exit(workspace, 0)
    retired = []
    capture_retires(retired)
    real_assess_seat = recovery.assess_seat
    assessments = []

    def assess_seat_counting_each_call(*arguments, **keywords):
        assessments.append(keywords)
        return real_assess_seat(*arguments, **keywords)

    patch("assess_seat", assess_seat_counting_each_call)
    try:
        report_unattended, unattended_seen = the_refusal_with_nobody_to_ask(workspace)
    finally:
        patch("assess_seat", real_assess_seat)
    lock_path = workspace.handoffs / "seat-a-supervisor.lock"
    check("LEFTOVER SHELL: with no terminal a seat left down is refused as today, byte for byte",
          report_unattended == (
              "seat-a: REFUSED — tmux session 'seat-a' is alive on socket 'seat-a', but no "
              f"live supervisor of this seat is confirmed (no supervisor lock at {lock_path}) "
              "— this tool never touches a live tmux session. If the seat's supervisor has "
              "exited, that session is the shell an attached launch leaves open: exit it, "
              "then rerun this recovery")
          and unattended_seen == "" and retired == [] and workspace.launches == []
          and len(assessments) == 1
          and not any(workspace.handoffs.glob("*-prompt.md")),
          (report_unattended, unattended_seen, retired, workspace.launches, assessments))

    # Ruled 2026-09-18: a seat whose waiting handoff asks to be consulted
    # (nedschorus#350). It is asked a question that shows its reason first,
    # and a yes relaunches it plain — the launch its own report tells an
    # operator to make by hand — leaving the handoff unconsumed, so its
    # supervisor's boot-ignition asks its own "restart? y/n" in the seat's
    # tmux session before it starts anything. The user ruled both the words
    # and what a yes does as built.
    workspace = a_seat_behind_a_leftover_shell("leftover-shell-consulted")
    consulted_handoff_path = workspace.handoffs / "seat-a-handoff.md"
    consulted_handoff_path.write_text(consulted_handoff_text, encoding="utf-8")
    retired = []
    capture_retires(retired)
    capture_launches_with_what_was_retired_by_then(workspace, retired)
    report_consulted, seen = recover_with_an_operator_typing(workspace, "y")
    check("LEFTOVER SHELL (ruled 2026-09-18): a seat that asked to be consulted is shown its "
          "reason and asked whether to restart it",
          asked_only(question_for_a_seat_that_asked_to_be_consulted, seen), seen)
    check("LEFTOVER SHELL (ruled 2026-09-18): and a yes retires its session, then relaunches it "
          "plain, its handoff unconsumed for its supervisor's own question",
          retired == ["seat-a"]
          and workspace.launches == [("seat-a", "", None, ["seat-a"])]
          and report_consulted == (
              "seat-a: relaunched plain, although an unconsumed handoff (counter 11) asks to "
              "be consulted before a relaunch: the user asked to be consulted before a "
              "relaunch. Its supervisor asks its own restart question before it starts a "
              "session: answer it in the seat's tmux session "
              + the_operator_said_to_restart_it)
          and consulted_handoff_path.read_text(encoding="utf-8") == consulted_handoff_text,
          (retired, workspace.launches, report_consulted))
    workspace = a_seat_behind_a_leftover_shell("leftover-shell-consulted-dry-run")
    (workspace.handoffs / "seat-a-handoff.md").write_text(consulted_handoff_text,
                                                          encoding="utf-8")
    retired = []
    capture_retires(retired)
    report_dry, seen = recover_with_an_operator_typing(workspace, "y", dry_run=True)
    check("LEFTOVER SHELL (ruled 2026-09-18): --dry-run carries the consulted question and the "
          "plain relaunch",
          retired == [] and workspace.launches == [] and seen == ""
          and report_dry == (
              "seat-a: would ask an operator at a terminal — "
              f'"{question_for_a_seat_that_asked_to_be_consulted}" — and on a yes '
              "close that session and relaunch the seat plain, whose supervisor then asks its "
              "own restart question before it starts a session (it is one pane at a shell)"
              + dry_run_ending_quoting_the_refusal(workspace)),
          (retired, workspace.launches, report_dry))
    workspace = a_seat_behind_a_leftover_shell("leftover-shell-consulted-no")
    consulted_handoff_path = workspace.handoffs / "seat-a-handoff.md"
    consulted_handoff_path.write_text(consulted_handoff_text, encoding="utf-8")
    retired = []
    capture_retires(retired)
    report_consulted_no, seen = recover_with_an_operator_typing(workspace, "n")
    check("LEFTOVER SHELL (ruled 2026-09-18): a no to a seat that asked to be consulted leaves "
          "everything as it is",
          retired == [] and workspace.launches == []
          and report_consulted_no == the_refusal_with_nobody_to_ask(workspace)[0]
          and consulted_handoff_path.read_text(encoding="utf-8") == consulted_handoff_text,
          (retired, workspace.launches, report_consulted_no))

    # A seat with nothing to resume is ignited fresh after a yes: a launch, so
    # it is asked whether to restart it.
    workspace = a_seat_behind_a_leftover_shell("leftover-shell-ignite")
    (workspace.project_directory() / "resume-me.jsonl").unlink()
    retired = []
    capture_retires(retired)
    report_ignited, seen = recover_with_an_operator_typing(workspace, "y")
    check("LEFTOVER SHELL: a seat that would be ignited is asked \"Restart seat-a? y/n\", "
          "byte for byte",
          asked_only(question_that_restarts_the_seat, seen), seen)
    check("LEFTOVER SHELL: and after the yes it is launched fresh",
          retired == ["seat-a"] and [launch[:2] for launch in workspace.launches] == [
              ("seat-a", "")]
          and report_ignited.startswith("seat-a: relaunched fresh"),
          (retired, workspace.launches, report_ignited))

    # --- a yes that could only end in a refusal or a running seat -----------
    # Ruled 2026-09-18 in a walk: "Don't ask. When the tool can already see a
    # yes would end in a refusal or a running seat, it refuses straight away
    # with the reason and leaves the window open". Nothing is put to the
    # operator (input() is never called), nothing is retired, and the line
    # carries the prediction's reason in that verdict's usual report class.
    reported_straight_away = ("This was found assessing the seat as though its leftover "
                              "shell were already closed, so nothing was asked and its "
                              "window was left open")

    def a_seat_behind_a_leftover_shell_with_an_unreadable_handoff(directory_name):
        """Its reassessment refuses whatever happens to the window: a handoff
        whose restart-counter no supervisor could ever read."""
        workspace = a_seat_behind_a_leftover_shell(directory_name)
        handoff_path = workspace.handoffs / "seat-a-handoff.md"
        handoff_path.write_text("# Handoff\nnext-step: go\n", encoding="utf-8")
        return workspace, handoff_path

    def a_supervisor_starts_right_after_the_idle_shell_proof(workspace):
        """The seat's supervisor claims its lock between the assessment that
        proved the shell idle and the prediction, and ps confirms it from then
        on. Returns the lock's path; ps_answers_for_real puts ps back."""
        lock_path = workspace.handoffs / "seat-a-supervisor.lock"

        def the_proof_and_then_a_supervisor_starts(name, seat_directory):
            lock_path.write_text("4321\n", encoding="utf-8")
            ps_confirms_supervisors({4321: "seat-a"})
            return True, [4242], "it is one pane at a shell"

        patch("tmux_session_is_a_leftover_idle_shell", the_proof_and_then_a_supervisor_starts)
        return lock_path

    workspace, handoff_path = a_seat_behind_a_leftover_shell_with_an_unreadable_handoff(
        "leftover-shell-predicted-refusal")
    retired = []
    capture_retires(retired)
    report_refused, prompts, seen = recover_recording_every_prompt(workspace)
    check("LEFTOVER SHELL: a predicted refusal asks nothing, retires nothing, launches nothing",
          prompts == [] and retired == [] and workspace.launches == [],
          (prompts, retired, workspace.launches, report_refused, seen))
    check("LEFTOVER SHELL: and is REFUSED with the predicted reason, the window left open",
          report_refused.startswith(f"seat-a: REFUSED — a handoff exists at {handoff_path} "
                                    "but its restart-counter is missing or unreadable")
          and report_refused.endswith(reported_straight_away)
          and "never touches a live tmux session" not in report_refused
          and any(marker in report_refused
                  for marker in recovery.SEAT_NOT_RECOVERED_REPORT_MARKERS),
          report_refused)

    workspace, handoff_path = a_seat_behind_a_leftover_shell_with_an_unreadable_handoff(
        "leftover-shell-predicted-refusal-dry-run")
    retired = []
    capture_retires(retired)
    report_refused_dry, prompts, seen = recover_recording_every_prompt(workspace, dry_run=True)
    check("LEFTOVER SHELL: --dry-run says a predicted refusal is reported without asking",
          prompts == [] and retired == [] and workspace.launches == [] and seen == ""
          and report_refused_dry.startswith(
              "seat-a: with an operator at a terminal would ask nothing, leave the window "
              "open (it is one pane at a shell) and report straight away: REFUSED — a "
              f"handoff exists at {handoff_path} but its restart-counter is missing")
          and report_refused_dry.endswith("With no terminal it refuses")
          and "would ask an operator at a terminal —" not in report_refused_dry,
          (prompts, retired, report_refused_dry))

    workspace = a_seat_behind_a_leftover_shell("leftover-shell-predicted-running")
    retired = []
    capture_retires(retired)
    try:
        lock_path = a_supervisor_starts_right_after_the_idle_shell_proof(workspace)
        report_running, prompts, seen = recover_recording_every_prompt(workspace)
    finally:
        ps_answers_for_real()
    check("LEFTOVER SHELL: a seat predicted running asks nothing, retires nothing, launches "
          "nothing",
          prompts == [] and retired == [] and workspace.launches == [],
          (prompts, retired, workspace.launches, report_running, seen))
    check("LEFTOVER SHELL: and is ALREADY RUNNING with the predicted reason, the window left open",
          report_running.startswith(
              f"seat-a: {recovery.SEAT_ALREADY_RUNNING_REPORT_MARKER} — the supervisor lock at "
              f"{lock_path} is held by a live supervisor — ")
          and "process 4321 is the supervisor of seat-a" in report_running
          and report_running.endswith(reported_straight_away)
          and not any(marker in report_running
                      for marker in recovery.SEAT_NOT_RECOVERED_REPORT_MARKERS),
          report_running)

    workspace = a_seat_behind_a_leftover_shell("leftover-shell-predicted-running-dry-run")
    retired = []
    capture_retires(retired)
    try:
        lock_path = a_supervisor_starts_right_after_the_idle_shell_proof(workspace)
        report_running_dry, prompts, seen = recover_recording_every_prompt(workspace,
                                                                           dry_run=True)
    finally:
        ps_answers_for_real()
    check("LEFTOVER SHELL: --dry-run says a seat predicted running is reported without asking",
          prompts == [] and retired == [] and workspace.launches == [] and seen == ""
          and report_running_dry.startswith(
              "seat-a: with an operator at a terminal would ask nothing, leave the window "
              "open (it is one pane at a shell) and report straight away: "
              f"{recovery.SEAT_ALREADY_RUNNING_REPORT_MARKER} — the supervisor lock at "
              f"{lock_path} is held by a live supervisor — ")
          and report_running_dry.endswith("With no terminal it refuses")
          and "would ask an operator at a terminal —" not in report_running_dry,
          (prompts, retired, report_running_dry))

    # A retire that fails, and a session that survives one: refused, never
    # asked twice.
    workspace = a_seat_behind_a_leftover_shell("leftover-shell-retire-fails")
    retired = []
    capture_retires(retired, killed_sockets=(),
                    failure="could not kill the stale tmux session seat-a "
                            "(server socket seat-a): server exited")
    report_failed, seen = recover_with_an_operator_typing(workspace, "y")
    check("LEFTOVER SHELL: a retire that fails refuses and launches nothing",
          retired == ["seat-a"] and workspace.launches == []
          and report_failed == ("seat-a: REFUSED — could not kill the stale tmux session "
                                "seat-a (server socket seat-a): server exited"),
          (retired, workspace.launches, report_failed))
    workspace = a_seat_behind_a_leftover_shell("leftover-shell-survives-the-retire")
    retired = []
    capture_retires(retired, the_session_then_dies=False)
    report_survived, seen = recover_with_an_operator_typing(workspace, "y")
    check("LEFTOVER SHELL: a session still holding the name is refused, not asked about again",
          retired == ["seat-a"] and workspace.launches == []
          and seen.count(question_that_restarts_the_seat) == 1
          and "still holds the name" in report_survived,
          (retired, workspace.launches, report_survived, seen))

    # --- the proof again, immediately before the retire --------------------
    # Ruled 2026-09-18 in a walk, answering the independent review of the pull
    # request that added the question: between the proof in assess_seat and
    # the retire, the operator's think time is unbounded, and the retire kills
    # whatever holds the seat's name when it runs. The shape it names: while
    # the question waits, the operator goes to the seat's own window and starts
    # something in that shell, and a yes then kills it. So after the yes the
    # shell is proven idle once more, and nothing is closed if it is not.
    the_shell_proven_idle = (True, [4242], "it is one pane at a shell")
    work_started_in_the_shell_while_the_question_waited = (
        False, [], "a pane of session 'seat-a' on socket 'seat-a' is running vim, not an "
                   "idle shell")

    def main_at_a_terminal_answering_yes(workspace, events, proof_before_the_question,
                                         proof_after_the_question,
                                         rooted_before_and_after_the_question=None):
        """recovery.main on seat-a with an operator at a terminal who answers
        yes. The idle-shell proof gives one answer until the question has been
        put and the other after it, and every proof, question and retire is
        appended to events in the order it happens. With
        rooted_before_and_after_the_question, lsof names the first list as
        rooted in the seat until the question is put, and the second after.
        Returns (exit code, every printed line, every logged line)."""
        def the_proof(name, seat_directory):
            events.append("proof")
            return (proof_after_the_question if "question" in events
                    else proof_before_the_question)

        def input_answering_yes(prompt=""):
            events.append("question")
            return "y"

        def fake_retire(name):
            events.append("retire")
            patch("tmux_session_alive_anywhere", lambda name: (False, ""))
            return ["seat-a"], None

        patch("tmux_session_is_a_leftover_idle_shell", the_proof)
        if rooted_before_and_after_the_question is not None:
            rooted_before, rooted_after = rooted_before_and_after_the_question
            patch("processes_rooted_in_seat_directory",
                  lambda seat_directory, require_a_complete_listing=False: (
                      list(rooted_after if "question" in events else rooted_before), ""))
        recovery.resupervise.retire_seat_tmux_session = fake_retire
        recovery.input = input_answering_yes
        an_operator_terminal()
        printed = io.StringIO()
        try:
            with redirect_stdout(printed):
                exit_code = recovery.main(["seat-a",
                                           "--agents-root", str(workspace.agents_root),
                                           "--handoff-dir", str(workspace.handoffs),
                                           "--projects-root", str(workspace.projects)])
        finally:
            del recovery.input
            no_operator_terminal()
        log_path = workspace.handoffs / "recover-crashed-seats-log.txt"
        logged = log_path.read_text(encoding="utf-8").splitlines() if log_path.is_file() else []
        return exit_code, printed.getvalue().splitlines(), logged

    workspace = a_seat_behind_a_leftover_shell("leftover-shell-work-started-while-asked")
    events = []
    exit_code, printed, logged = main_at_a_terminal_answering_yes(
        workspace, events, the_shell_proven_idle,
        work_started_in_the_shell_while_the_question_waited)
    # The user's words, approved 2026-09-18 after he asked of the line before
    # them "What are we refusing. I don't care about tmux sessions." Spelled
    # out byte for byte, never derived from the constant that holds them.
    left_alone_as_something_may_have_started = (
        "seat-a: NOT RESTARTED — something may have started in it while you were answering, "
        "so it was left alone")
    check("LEFTOVER SHELL (ruled 2026-09-18): after a yes the shell is proven again, and work "
          "started in it while the question waited is not closed",
          events == ["proof", "question", "proof"] and workspace.launches == [],
          (events, workspace.launches, printed))
    check("LEFTOVER SHELL (ruled 2026-09-18): its line is exactly \"seat-a: NOT RESTARTED — "
          "something may have started in it while you were answering, so it was left alone\", "
          "logged, and main exits 1",
          printed[-1:] == ["recover-crashed-seats: " + left_alone_as_something_may_have_started]
          and len(logged) == 1
          and logged[0].endswith(" " + left_alone_as_something_may_have_started)
          and exit_code == 1,
          (exit_code, printed, logged))
    check("LEFTOVER SHELL (ruled 2026-09-18): that line counts as not recovered by its own "
          "marker, NOT RESTARTED, and by no other",
          [marker for marker in recovery.SEAT_NOT_RECOVERED_REPORT_MARKERS
           if marker in left_alone_as_something_may_have_started] == ["NOT RESTARTED"],
          recovery.SEAT_NOT_RECOVERED_REPORT_MARKERS)

    workspace = a_seat_behind_a_leftover_shell("leftover-shell-still-idle-when-proven-again")
    events = []
    exit_code, printed, logged = main_at_a_terminal_answering_yes(
        workspace, events, the_shell_proven_idle, the_shell_proven_idle)
    check("LEFTOVER SHELL (ruled 2026-09-18): a shell still idle after the yes is proven again, "
          "THEN retired, and the seat is restarted as before",
          events == ["proof", "question", "proof", "retire"]
          and [launch[:2] for launch in workspace.launches] == [
              ("seat-a", "--resume-session-id resume-me")]
          and printed[-1:] == [
              "recover-crashed-seats: seat-a: relaunched resuming resume-me (0KB transcript) "
              + the_operator_said_to_restart_it]
          and exit_code == 0,
          (events, workspace.launches, printed, exit_code))

    # The panes excused from the occupancy check after the retire are the ones
    # the second proof found, since those are what the retire closed: a second
    # idle shell opened in the session while the question waited is closed with
    # the first, and lsof still naming it must not refuse the seat.
    workspace = a_seat_behind_a_leftover_shell("leftover-shell-second-pane-while-asked")
    events = []
    exit_code, printed, logged = main_at_a_terminal_answering_yes(
        workspace, events, the_shell_proven_idle,
        (True, [4242, 5151], "it is two panes at a shell"),
        rooted_before_and_after_the_question=([4242], [4242, 5151]))
    check("LEFTOVER SHELL: the panes excused after the retire are those the second proof found",
          events == ["proof", "question", "proof", "retire"]
          and [launch[:2] for launch in workspace.launches] == [
              ("seat-a", "--resume-session-id resume-me")]
          and printed[-1:] == [
              "recover-crashed-seats: seat-a: relaunched resuming resume-me (0KB transcript) "
              + the_operator_said_to_restart_it]
          and exit_code == 0,
          (events, workspace.launches, printed, exit_code))

    # What the second proof failing means depends on whether the session is
    # still there, which tmux is asked; the proof's words are never read. Only
    # a session still there can hold work, so only it is left alone and the
    # seat reported NOT RESTARTED. One that is gone — the operator exited the
    # shell himself while the question waited — is recovered exactly as before
    # the recheck.
    # With no answer from tmux, the seat is refused in the liveness check's
    # own words, and nothing is closed. These run the real proof, the real
    # liveness check and resupervise-seat.py's real retire over a faked tmux.
    def main_at_a_terminal_answering_yes_over_a_tmux_server(workspace, events,
                                                            after_the_question):
        """recovery.main on seat-a with an operator at a terminal who answers
        yes, with only tmux's answers faked. Until the question is put, the
        seat's socket holds one pane at zsh, process 4242. After it, that pane
        runs vim ("work started"), no server holds the name ("gone"), or tmux
        answers nothing at all ("unanswerable"). Every proof, question and
        retire is appended to events. Returns (exit code, every printed line,
        every logged line)."""
        class Answer:
            def __init__(self, returncode, stdout=""):
                self.returncode, self.stdout, self.stderr = returncode, stdout, ""

        def fake_run_tmux(*arguments_after_tmux, socket_name=None):
            asked = "question" in events
            if asked and after_the_question == "unanswerable":
                return None
            held = socket_name == "seat-a" and not (asked and after_the_question == "gone")
            if arguments_after_tmux[0] == "has-session":
                return Answer(0 if held else 1)
            if arguments_after_tmux[0] == "list-panes" and held:
                return Answer(0, "4242\tvim\n" if asked else "4242\tzsh\n")
            return Answer(1)

        def the_real_proof_recorded(name, seat_directory):
            events.append("proof")
            return real_tmux_session_is_a_leftover_idle_shell(name, seat_directory)

        def input_answering_yes(prompt=""):
            events.append("question")
            return "y"

        def the_real_retire_recorded(name):
            events.append("retire")
            return real_retire_seat_tmux_session(name)

        patch("run_tmux", fake_run_tmux)
        recovery.resupervise.run_tmux = fake_run_tmux
        patch("tmux_session_alive_anywhere", real_tmux_session_alive_anywhere)
        patch("tmux_session_is_a_leftover_idle_shell", the_real_proof_recorded)
        recovery.resupervise.retire_seat_tmux_session = the_real_retire_recorded
        recovery.input = input_answering_yes
        an_operator_terminal()
        printed = io.StringIO()
        try:
            with redirect_stdout(printed):
                exit_code = recovery.main(["seat-a",
                                           "--agents-root", str(workspace.agents_root),
                                           "--handoff-dir", str(workspace.handoffs),
                                           "--projects-root", str(workspace.projects)])
        finally:
            del recovery.input
            no_operator_terminal()
            patch("run_tmux", real_run_tmux)
            recovery.resupervise.run_tmux = real_resupervise_run_tmux
            recovery.resupervise.retire_seat_tmux_session = real_retire_seat_tmux_session
        log_path = workspace.handoffs / "recover-crashed-seats-log.txt"
        logged = log_path.read_text(encoding="utf-8").splitlines() if log_path.is_file() else []
        return exit_code, printed.getvalue().splitlines(), logged

    workspace = a_seat_behind_a_leftover_shell("leftover-shell-gone-while-asked")
    events = []
    exit_code, printed, logged = main_at_a_terminal_answering_yes_over_a_tmux_server(
        workspace, events, "gone")
    relaunched_after_the_session_was_gone = (
        "seat-a: relaunched resuming resume-me (0KB transcript) (the operator said to restart "
        "it, so the leftover shell was closed first: the leftover shell was already gone when "
        "it was retired)")
    check("LEFTOVER SHELL: a session gone while the question waited is not refused: the retire "
          "finds nothing, and the seat is relaunched, its line byte for byte",
          events == ["proof", "question", "proof", "retire"]
          and [launch[:2] for launch in workspace.launches] == [
              ("seat-a", "--resume-session-id resume-me")]
          and printed[-2:] == [
              "recover-crashed-seats: seat-a: the leftover shell was already gone when it was "
              "retired",
              "recover-crashed-seats: " + relaunched_after_the_session_was_gone]
          and len(logged) == 1
          and logged[0].endswith(" " + relaunched_after_the_session_was_gone)
          and exit_code == 0,
          (events, workspace.launches, printed, logged, exit_code))

    workspace = a_seat_behind_a_leftover_shell("leftover-shell-tmux-unanswerable-when-asked-again")
    events = []
    exit_code, printed, logged = main_at_a_terminal_answering_yes_over_a_tmux_server(
        workspace, events, "unanswerable")
    refused_as_tmux_cannot_be_run = (
        "seat-a: REFUSED — tmux cannot be run here, so seat liveness cannot be checked — "
        "refusing rather than guessing")
    check("LEFTOVER SHELL: when tmux cannot answer at the recheck, nothing is closed and the "
          "seat is REFUSED in the liveness check's words, byte for byte",
          events == ["proof", "question", "proof"] and workspace.launches == []
          and printed[-1:] == ["recover-crashed-seats: " + refused_as_tmux_cannot_be_run]
          and len(logged) == 1 and logged[0].endswith(" " + refused_as_tmux_cannot_be_run)
          and exit_code == 1,
          (events, workspace.launches, printed, logged, exit_code))

    workspace = a_seat_behind_a_leftover_shell("leftover-shell-vim-started-while-asked")
    events = []
    exit_code, printed, logged = main_at_a_terminal_answering_yes_over_a_tmux_server(
        workspace, events, "work started")
    check("LEFTOVER SHELL (ruled 2026-09-18): over the real proof, vim started in the shell "
          "while the question waited is not closed, and the seat is reported NOT RESTARTED",
          events == ["proof", "question", "proof"] and workspace.launches == []
          and printed[-1:] == ["recover-crashed-seats: "
                               + left_alone_as_something_may_have_started]
          and exit_code == 1,
          (events, workspace.launches, printed, exit_code))

    # --- a practice run counts a seat it would ask about --------------------
    # Ruled 2026-09-18 in a walk: a practice run exits 1 if any seat would stay
    # down with nobody at the keyboard. A dry-run line that asks now ends with
    # the refusal a no, or nobody to ask, gives, quoted whole as the recorded
    # exit's own dry run quotes its line, so main counts it by that REFUSED.
    # Every verdict the question is asked for, through main, byte for byte.
    def write_a_waiting_handoff(workspace):
        (workspace.handoffs / "seat-a-handoff.md").write_text(
            "# Handoff\nrestart-counter: 5\nnext-step: continue\n", encoding="utf-8")

    def write_a_handoff_asking_to_be_consulted(workspace):
        (workspace.handoffs / "seat-a-handoff.md").write_text(consulted_handoff_text,
                                                              encoding="utf-8")

    def remove_the_transcript(workspace):
        (workspace.project_directory() / "resume-me.jsonl").unlink()

    def remove_the_transcript_and_record_an_unknown_exit(workspace):
        remove_the_transcript(workspace)
        record_an_agent_exit(workspace, None)

    for case_slug, prepare, question, what_a_yes_does in (
            ("defer-to-boot-ignition", write_a_waiting_handoff,
             question_that_restarts_the_seat, "assess the seat without it"),
            ("resume", lambda workspace: None,
             question_that_restarts_the_seat, "assess the seat without it"),
            ("ignite", remove_the_transcript,
             question_that_restarts_the_seat, "assess the seat without it"),
            ("offer-after-recorded-exit-code-0-resuming",
             lambda workspace: record_an_agent_exit(workspace, 0),
             question_for_a_seat_stopped_on_purpose,
             "restart the seat resuming session resume-me"),
            ("offer-after-recorded-exit-unknown-code-fresh",
             remove_the_transcript_and_record_an_unknown_exit,
             question_for_a_seat_stopped_on_purpose, "restart the seat as a fresh session"),
            ("offer-after-recorded-exit-code-1-resuming",
             lambda workspace: record_an_agent_exit(workspace, 1),
             question_for_a_seat_that_stopped_with_exit_code_1,
             "restart the seat resuming session resume-me"),
            ("seat-asked-to-be-consulted", write_a_handoff_asking_to_be_consulted,
             question_for_a_seat_that_asked_to_be_consulted,
             "relaunch the seat plain, whose supervisor then asks its own restart question "
             "before it starts a session")):
        workspace = a_seat_behind_a_leftover_shell(f"leftover-shell-practice-run-{case_slug}")
        prepare(workspace)
        retired = []
        capture_retires(retired)
        prompts = []

        def input_recording_the_prompt(prompt=""):
            prompts.append(prompt)
            return "y"

        recovery.input = input_recording_the_prompt
        printed = io.StringIO()
        try:
            with redirect_stdout(printed):
                exit_code = recovery.main(["seat-a", "--dry-run",
                                           "--agents-root", str(workspace.agents_root),
                                           "--handoff-dir", str(workspace.handoffs),
                                           "--projects-root", str(workspace.projects)])
        finally:
            del recovery.input
        check(f"PRACTICE RUN (ruled 2026-09-18): {case_slug} behind a leftover shell ends "
              "\"; on a no, or with no terminal, it reports: REFUSED — <the unattended "
              "refusal>\", byte for byte",
              printed.getvalue().splitlines() == [
                  "recover-crashed-seats: seat-a: would ask an operator at a terminal — "
                  f'"{question}" — and on a yes close that session and {what_a_yes_does} '
                  "(it is one pane at a shell)" + dry_run_ending_quoting_the_refusal(workspace)],
              printed.getvalue())
        check(f"PRACTICE RUN (ruled 2026-09-18): a --dry-run whose only seat is {case_slug} "
              "behind a leftover shell exits 1, asking, closing and launching nothing",
              exit_code == 1 and prompts == [] and retired == [] and workspace.launches == []
              and not (workspace.handoffs / "recover-crashed-seats-log.txt").exists(),
              (exit_code, prompts, retired, workspace.launches))

    # --- what proves "nothing but an idle shell" ----------------------------
    # Both halves, because neither is enough on its own. Measured on the Mac,
    # 2026-09-17: a LIVE attached seat's pane reports a shell too — the
    # launcher's pane command is `zsh -c "...; <supervisor>; <after-exit>"`, so
    # the supervisor runs as the pane process's child inside its process group
    # (seat fleet-restart-at-login: pane process 27178 `zsh`, supervisor 27179
    # `Python`). What separates it from a real leftover shell is that something
    # OTHER than the pane is rooted in the seat directory.
    workspace = Workspace(root / "idle-shell-proof")
    patch("tmux_session_is_a_leftover_idle_shell", real_tmux_session_is_a_leftover_idle_shell)

    tmux_server_answers({"seat-a": "27178\tzsh\n"})
    rooted_processes_are([27178])
    proven, panes, detail = recovery.tmux_session_is_a_leftover_idle_shell(
        "seat-a", workspace.seat_directory)
    check("IDLE SHELL PROOF: a pane at a shell with only its own process rooted in the seat",
          proven is True and panes == [27178] and "nothing in the foreground" in detail,
          (proven, panes, detail))

    rooted_processes_are([27178, 27179])
    proven, panes, detail = recovery.tmux_session_is_a_leftover_idle_shell(
        "seat-a", workspace.seat_directory)
    check("IDLE SHELL PROOF: a live attached seat's pane reports a shell too, and is not idle",
          proven is False and panes == [] and "27179" in detail
          and "cannot be shown to be an idle shell" in detail, (proven, panes, detail))

    rooted_processes_are([])
    proven, panes, detail = recovery.tmux_session_is_a_leftover_idle_shell(
        "seat-a", workspace.seat_directory)
    check("IDLE SHELL PROOF: a shell that left the seat directory is still idle",
          proven is True and panes == [27178], (proven, panes, detail))

    tmux_server_answers({"seat-a": "27178\tPython\n"})
    proven, panes, detail = recovery.tmux_session_is_a_leftover_idle_shell(
        "seat-a", workspace.seat_directory)
    check("IDLE SHELL PROOF: a pane running real work is not an idle shell",
          proven is False and "running Python" in detail, (proven, panes, detail))

    tmux_server_answers({"seat-a": "27178\tzsh\n99\tvim\n"})
    rooted_processes_are([27178])
    proven, panes, detail = recovery.tmux_session_is_a_leftover_idle_shell(
        "seat-a", workspace.seat_directory)
    check("IDLE SHELL PROOF: one working pane in the session is enough to refuse",
          proven is False and "running vim" in detail, (proven, panes, detail))

    tmux_server_answers({"seat-a": "27178\tzsh\n", "default": "5\tbash\n"})
    rooted_processes_are([27178, 5])
    proven, panes, detail = recovery.tmux_session_is_a_leftover_idle_shell(
        "seat-a", workspace.seat_directory)
    check("IDLE SHELL PROOF: both servers holding the name are measured, and their panes named",
          proven is True and panes == [27178, 5] and "sockets 'seat-a', 'default'" in detail,
          (proven, panes, detail))

    tmux_server_answers({"seat-a": "27178\tzsh\n"}, tmux_cannot_be_run=True)
    proven, panes, detail = recovery.tmux_session_is_a_leftover_idle_shell(
        "seat-a", workspace.seat_directory)
    check("IDLE SHELL PROOF: tmux that cannot answer proves nothing",
          proven is False and "tmux cannot be run here" in detail, (proven, panes, detail))

    tmux_server_answers({"seat-a": "27178\tzsh\n"}, list_panes_exit_code=1)
    proven, panes, detail = recovery.tmux_session_is_a_leftover_idle_shell(
        "seat-a", workspace.seat_directory)
    check("IDLE SHELL PROOF: panes that cannot be listed prove nothing",
          proven is False and "could not list the panes" in detail, (proven, panes, detail))

    tmux_server_answers({"seat-a": "27178\tzsh\n"})
    rooted_processes_are(None, "lsof is not installed, so the seat cannot be proven vacant")
    proven, panes, detail = recovery.tmux_session_is_a_leftover_idle_shell(
        "seat-a", workspace.seat_directory)
    check("IDLE SHELL PROOF: an unusable lsof answer proves nothing",
          proven is False and "lsof is not installed" in detail, (proven, panes, detail))

    tmux_server_answers({})
    proven, panes, detail = recovery.tmux_session_is_a_leftover_idle_shell(
        "seat-a", workspace.seat_directory)
    check("IDLE SHELL PROOF: no server holding the name proves nothing",
          proven is False and "no tmux server holds" in detail, (proven, panes, detail))

    # The occupancy check reads process ids now, and excuses only the panes it
    # was handed.
    patch("run_tmux", real_run_tmux)
    patch("seat_directory_occupied", real_seat_directory_occupied)
    rooted_processes_are([4242])
    check("IDLE SHELL PROOF: the retired pane is excused from the occupancy check",
          recovery.seat_directory_occupied(workspace.seat_directory) == (
              True, f"a live process is rooted in {workspace.seat_directory.resolve()}")
          and recovery.seat_directory_occupied(
              workspace.seat_directory, apart_from_process_ids=[4242]) == (False, ""),
          (recovery.seat_directory_occupied(workspace.seat_directory),
           recovery.seat_directory_occupied(workspace.seat_directory,
                                            apart_from_process_ids=[4242])))
    rooted_processes_are([4242, 77])
    check("IDLE SHELL PROOF: a process that was not a retired pane still occupies the seat",
          recovery.seat_directory_occupied(
              workspace.seat_directory, apart_from_process_ids=[4242])[0] is True,
          recovery.seat_directory_occupied(workspace.seat_directory,
                                           apart_from_process_ids=[4242]))

    # The lsof reader itself, over the -F pn shape both machines print
    # (checked on the box, 2026-09-17: same p/n fields, with unreadable
    # processes named as paths that match no seat).
    patch("processes_rooted_in_seat_directory", real_processes_rooted_in_seat_directory)
    seat = str(workspace.seat_directory.resolve())
    real_subprocess_run = recovery.subprocess.run
    real_shutil_which = recovery.shutil.which

    def lsof_prints(text, returncode=0):
        class Listing:
            def __init__(self):
                self.stdout, self.returncode = text, returncode
        recovery.shutil.which = lambda binary: f"/usr/bin/{binary}"
        recovery.subprocess.run = lambda *arguments, **keywords: Listing()

    try:
        lsof_prints(f"p11\nn/elsewhere\np12\nn{seat}\np13\nn{seat}/worktree\n")
        check("IDLE SHELL PROOF: the lsof reader names every process rooted in the seat",
              recovery.processes_rooted_in_seat_directory(workspace.seat_directory)
              == ([12, 13], ""),
              recovery.processes_rooted_in_seat_directory(workspace.seat_directory))
        lsof_prints("p11\nn/elsewhere\n")
        check("IDLE SHELL PROOF: a listing naming no process in the seat is a vacant seat",
              recovery.processes_rooted_in_seat_directory(workspace.seat_directory) == ([], ""),
              recovery.processes_rooted_in_seat_directory(workspace.seat_directory))
        lsof_prints("")
        answer, why = recovery.processes_rooted_in_seat_directory(workspace.seat_directory)
        check("IDLE SHELL PROOF: an lsof that named nothing at all proves nothing",
              answer is None and "no working directories at all" in why, (answer, why))
        lsof_prints("p11\nn/elsewhere\n", returncode=1)
        answer, why = recovery.processes_rooted_in_seat_directory(workspace.seat_directory)
        check("IDLE SHELL PROOF: an lsof that exited nonzero proves nothing",
              answer is None and "exited 1" in why, (answer, why))
        lsof_prints(f"p11\nn/elsewhere\np12\nn{seat}\n", returncode=1)
        check("IDLE SHELL PROOF: a partial listing naming the seat is still positive evidence",
              recovery.processes_rooted_in_seat_directory(workspace.seat_directory)
              == ([12], ""),
              recovery.processes_rooted_in_seat_directory(workspace.seat_directory))
        # The proof reads that same listing the other way round — is nothing
        # but these panes in there — which a partial listing cannot answer,
        # however innocent the part of it that arrived.
        tmux_server_answers({"seat-a": "27178\tzsh\n"})
        lsof_prints(f"p11\nn/elsewhere\np27178\nn{seat}\n", returncode=1)
        proven, panes, detail = recovery.tmux_session_is_a_leftover_idle_shell(
            "seat-a", workspace.seat_directory)
        check("IDLE SHELL PROOF: a partial lsof listing cannot show a session to be idle",
              proven is False and "exited 1" in detail, (proven, panes, detail))
        check("IDLE SHELL PROOF: nor can it excuse a retired pane from the occupancy check",
              recovery.seat_directory_occupied(
                  workspace.seat_directory, apart_from_process_ids=[27178])
              == (True, "the occupancy check (lsof) exited 1; vacancy unproven"),
              recovery.seat_directory_occupied(workspace.seat_directory,
                                               apart_from_process_ids=[27178]))
    finally:
        patch("run_tmux", real_run_tmux)
        recovery.subprocess.run = real_subprocess_run
        recovery.shutil.which = real_shutil_which
        recovery.resupervise.retire_seat_tmux_session = real_retire_seat_tmux_session
        patch("processes_rooted_in_seat_directory", real_processes_rooted_in_seat_directory)
        patch("seat_directory_occupied", real_seat_directory_occupied)
        patch("tmux_session_is_a_leftover_idle_shell",
              real_tmux_session_is_a_leftover_idle_shell)
        patch("recovery_has_an_operator_terminal", real_recovery_has_an_operator_terminal)

    # The leftover-shell question's map, over the five verdicts it is worded
    # for, each with the detail assess_seat gives it. Last, because it calls
    # the composer directly. refuse and seat-already-running are reported
    # without asking (ruled 2026-09-18), so no words are chosen for them.
    for predicted_verdict, predicted_detail, expected_question in (
            ("defer-to-boot-ignition", "an unconsumed handoff waits (counter 5, consumed None)",
             question_that_restarts_the_seat),
            ("resume", ("resume-me", Path("/transcripts/resume-me.jsonl")),
             question_that_restarts_the_seat),
            ("ignite", "no transcripts under /transcripts", question_that_restarts_the_seat),
            ("offer-after-recorded-exit", (0, "2026-09-18T00:00:00+00:00", "resume-me"),
             question_for_a_seat_stopped_on_purpose),
            ("offer-after-recorded-exit", (None, "2026-09-18T00:00:00+00:00", None),
             question_for_a_seat_stopped_on_purpose),
            ("offer-after-recorded-exit", (1, "2026-09-18T00:00:00+00:00", "resume-me"),
             question_for_a_seat_that_stopped_with_exit_code_1),
            ("offer-after-recorded-exit", (137, "2026-09-18T00:00:00+00:00", None),
             question_for_a_seat_that_stopped_with_exit_code_137),
            ("offer-after-recorded-exit", (-15, "2026-09-18T00:00:00+00:00", "resume-me"),
             "seat-a stopped with exit code -15. Restart it? y/n"),
            ("seat-asked-to-be-consulted",
             (11, "the user asked to be consulted before a relaunch"),
             question_for_a_seat_that_asked_to_be_consulted),
            ("seat-asked-to-be-consulted", (3, "  ask me first.  "),
             "seat-a's handoff says: ask me first. Restart it? y/n")):
        composed_question = recovery.leftover_idle_shell_question_for_seat(
            "seat-a", predicted_verdict, predicted_detail)
        check(f"LEFTOVER SHELL: a reassessment predicted to give {predicted_verdict} "
              f"({predicted_detail!r}) is asked {expected_question!r}, byte for byte",
              composed_question == expected_question, composed_question)

    # A verdict with no words chosen for it is never put silently: the composer
    # refuses to word it.
    for unworded_verdict in ("refuse", "seat-already-running",
                             recovery.ASK_TO_CLOSE_THE_LEFTOVER_IDLE_SHELL_VERDICT,
                             "a-verdict-no-one-has-worded"):
        try:
            composed_question = recovery.leftover_idle_shell_question_for_seat(
                "seat-a", unworded_verdict)
        except ValueError as error:
            composed_question = error
        check(f"LEFTOVER SHELL: no question is worded for {unworded_verdict}",
              isinstance(composed_question, ValueError), composed_question)

    # And every verdict assess_seat can return is accounted for: worded by the
    # composer, reported without asking, or the ask verdict itself, which the
    # prediction cannot give because it reads the session as closed. Read from
    # assess_seat's own returns, so a verdict added there without a place here
    # fails this case rather than reaching the composer's refusal at a terminal.
    import inspect
    import re
    assess_seat_source = inspect.getsource(recovery.assess_seat)
    verdicts_assess_seat_returns = set(
        re.findall(r'return\s*\(?\s*"([a-z-]+)"', assess_seat_source))
    if "return ASK_TO_CLOSE_THE_LEFTOVER_IDLE_SHELL_VERDICT" in assess_seat_source:
        verdicts_assess_seat_returns.add(recovery.ASK_TO_CLOSE_THE_LEFTOVER_IDLE_SHELL_VERDICT)
    verdicts_accounted_for = (
        set(recovery.LEFTOVER_IDLE_SHELL_REASSESSMENT_VERDICTS_THAT_LAUNCH)
        | set(recovery.LEFTOVER_IDLE_SHELL_REASSESSMENT_VERDICTS_RESTARTED_ONLY_ON_THE_OPERATORS_WORD)
        | set(recovery.LEFTOVER_IDLE_SHELL_PREDICTIONS_REPORTED_WITHOUT_ASKING)
        | {recovery.ASK_TO_CLOSE_THE_LEFTOVER_IDLE_SHELL_VERDICT})
    check("LEFTOVER SHELL: every verdict assess_seat returns is worded or reported without asking",
          len(verdicts_assess_seat_returns) == 8
          and verdicts_assess_seat_returns == verdicts_accounted_for,
          (sorted(verdicts_assess_seat_returns), sorted(verdicts_accounted_for)))


verdict_reached = True
sys.exit(1 if failures else 0)
