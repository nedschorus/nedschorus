#!/usr/bin/env python3
"""Recover named seats whose sessions died WITHOUT writing a handoff.

The gap this fills (nedschorus#120, from the 2026-08-21 incident): the Mac's
single tmux server died and took every Mac seat down mid-flight. No handoff
existed, so `resupervise-seat.py` refused (its precondition is a genuinely
waiting handoff), and a plain relaunch fell through to the supervisor's
first-prompt path — three near-empty successor sessions born while the full
pre-crash transcripts sat intact on disk. The operator recovered by hand:
dig the session id out of ~/.claude/projects/<seat-dir>/ by mtime, then
`claude --resume <id>` in the seat directory. This script is that recovery,
with the refusals that make it safe to run at any time.

What it does, per seat:
  1. Prove the seat is actually DEAD: no tmux session holding its name (the
     seat's own per-seat socket and the default socket both checked), no
     live supervisor of it, no process rooted in the seat directory. A seat
     with a live supervisor of it CONFIRMED by ps is reported ALREADY RUNNING
     and left alone, which is not a failure (user-ruled 2026-09-16). Every
     other doubt is REFUSED — a tmux session alive with no confirmed
     supervisor, and a supervisor only assumed because ps could not be run,
     included — and a refusal counts as a seat not recovered. Either way this
     tool recovers crashes; it never kills live work and never launches into a
     live tmux session.
  1a. With one question, and only with an operator at a terminal to answer it
     (user-ruled 2026-09-17). A tmux session alive with no confirmed
     supervisor is often nothing but the shell an attached launch leaves open
     in the seat's directory, which no operator can pass without killing it by
     hand. When this tool can PROVE that is all it is —
     tmux_session_is_a_leftover_idle_shell below — it asks whether to restart
     the seat (user-ruled 2026-09-18), and on an explicit yes retires that
     session (the step resupervise-seat.py already performs) and assesses the
     seat as though it were not there; a seat whose supervisor recorded its
     agent's exit (2a) is then restarted on that yes. Run unattended — at boot,
     under restart-live-seats-at-login — nothing is asked and the refusal
     stands exactly as it did. A session that cannot be proven idle is refused
     with no question, attended or not.
  2. Defer when an unconsumed handoff IS waiting: relaunching plain is
     correct there — the supervisor's boot-ignition consumes it (that path
     landed with PR #106) — so this script hands over to the launcher
     rather than duplicating that logic. Unless that handoff asks to be
     consulted before a relaunch (dont-restart): then nothing is launched,
     and the seat is reported NOT RELAUNCHED, AT ITS OWN REQUEST, which
     counts as not recovered — unless an operator says yes to the
     leftover-shell question in 1a, which relaunches it plain (ruled
     2026-09-18; see recover_seat).
  2a. Launch nothing on this tool's own account when the seat's supervisor
     recorded its agent's exit (nedschorus#242 change 2, ruled 2026-09-02): a
     supervisor that outlived its agent saw the ending, so the seat did not
     crash. Any recorded exit counts, whatever its code. Only a seat with no
     record goes on to the resume below. An operator at a terminal is asked
     (ruled 2026-09-18) — "<seat> stopped on purpose. Restart it anyway? y/n",
     or "<seat> stopped with exit code <code>. Restart it? y/n" when the
     recorded code is neither zero nor unknown — whether a leftover shell
     holds the seat's name (the question in 1a) or no session does at all, as
     after a reboot; a yes restarts the seat, resuming its session if there is
     one. With no leftover session, nobody to ask or a no leaves the seat down:
     the report says it was not relaunched and gives the commands to bring it
     back by hand, and it counts as a seat not recovered. With a leftover
     shell, nobody to ask or a no is the refusal in 1.
  3. Find the seat's most recent real transcript under the harness project
     directory: newest *.jsonl by mtime, skipping failed successors — small
     sessions whose first turn this machinery itself composed and which
     never produced work — the shape the 2026-08-21 relaunches minted,
     which must never shadow the real transcript they were born beside. A
     successor the supervisor started from a handoff is never skipped,
     even one that never replied: its parent handed off and is retired
     (the 2026-09-10 reboot).
  4. Relaunch the seat through its launcher with the supervisor resuming
     that session id (handoff-supervisor.py --resume-session-id, riding the
     launcher's LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS hook): the
     successor wakes holding the crashed session's full context,
     supervised, on the seat's own per-seat tmux server.

Degraded mode (user-directed 2026-08-21, recorded on #120): --ignite-fallback
skips the resume and launches fresh with a first prompt pointing at the
newest dialog extract in the handoff directory — the same read-and-continue
shape build_ignition_prompt composes at every reincarnation. Use it when a resume
fails or a transcript is too large to be worth replaying; the threshold
judgment stays with the operator in v1. It is also the automatic path when
no real transcript exists to resume.

Machine scope: this runs ON the machine whose seats it recovers — the
launcher it drives is the local one (launch-claude-mac on the Mac; on the
box the same recovery drives the supervisor's launcher conventions there).
Recovering box seats from the Mac is `ssh ned` plus this script there.

Usage:
  recover-crashed-seats.py <seat-name>... [--dry-run] [--ignite-fallback]
                           [--open-iterm-window-per-seat]
  recover-crashed-seats.py --all [--dry-run] [--ignite-fallback]
                           [--open-iterm-window-per-seat]

--all assesses every seat with a home under the agents root. --dry-run
reports every decision and launches nothing. --open-iterm-window-per-seat
(macOS only) launches each recovered seat attached, in its own iTerm window,
instead of detached; with --dry-run it prints the command each window would
run.
"""

import argparse
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_supervisor_spec = importlib.util.spec_from_file_location(
    "handoff_supervisor", Path(__file__).with_name("handoff-supervisor.py")
)
supervisor = importlib.util.module_from_spec(_supervisor_spec)
_supervisor_spec.loader.exec_module(supervisor)

_watcher_spec = importlib.util.spec_from_file_location(
    "watch_agent_dialogs", Path(__file__).with_name("watch-agent-dialogs.py")
)
watcher = importlib.util.module_from_spec(_watcher_spec)
_watcher_spec.loader.exec_module(watcher)

# For its retire step alone (retire_seat_tmux_session), run when an operator
# says to close a seat's leftover idle shell: the kill rules — every socket
# holding the name, no survivor left behind as a decoy — are that script's,
# and a second copy of them here would drift from it.
_resupervise_spec = importlib.util.spec_from_file_location(
    "resupervise_seat", Path(__file__).with_name("resupervise-seat.py")
)
resupervise = importlib.util.module_from_spec(_resupervise_spec)
_resupervise_spec.loader.exec_module(resupervise)

# First-turn shapes of sessions this machinery itself composes — the
# supervisor's no-handoff prompt and this script's own ignition and resume
# prompts. A marker alone writes nothing off: a first-ever session
# legitimately opens with the no-handoff prompt and then works (observed
# live 2026-08-22), and an ignited successor can crash mid-work — both must
# be resumed, not skipped for an older parent. What marks a failed successor
# is a marker AND no work: substantive_turn_count() below measures work, and
# the gate applies to every marker uniformly (round 4 finding 1 — markers
# were measured skipping real work on size alone). The supervisor-owned
# literals are asserted against the supervisor's actual source in the test
# suite, so a wording change there fails loudly.
# The phrase every first prompt after a recorded exit carries
# (write_first_prompt_after_recorded_exit), and so its marker.
FIRST_PROMPT_AFTER_RECORDED_EXIT_MARKER = "as it does when a session is stopped on purpose"
EMPTY_SUCCESSOR_MARKERS = (
    "No handoff exists yet",            # handoff-supervisor's default first prompt
    "crash recovery, nedschorus#120",   # this script's ignition (initial agent instructions)
    "resumed by crash recovery",        # this script's resume prompt
    FIRST_PROMPT_AFTER_RECORDED_EXIT_MARKER,  # this script's prompts after a recorded exit
)
# The supervisor's reincarnation opener is deliberately NOT a skip marker.
# The supervisor composes it only after marking the handoff consumed — on
# both its boot-ignition and in-cycle paths — so the transcript before a
# successor carrying it is a parent that handed off and is retired. A
# successor that never worked is still the seat's current incarnation, and
# is resumed (the 2026-09-10 Mac reboot, nedschorus#116, comment of
# 2026-09-11: two successors whose only reply was a session-limit notice
# were passed over for their retired parents). Shortened to the span both
# eras share: openers before 2026-08-30 read "it is the dialog from the
# session you are continuing, written N minutes ago" and sit in transcripts
# on disk; openers since read "— the dialog from the session you are
# continuing, written at <UTC>Z". Do not lengthen it back to either full
# sentence.
REINCARNATION_OPENER_MARKER = "the dialog from the session you are continuing"
# Anchored where the supervisor puts it — the start of the first turn,
# "Read <extract path> — ", in both eras — because the marker text alone
# also turns up quoted inside a hand-written first brief (this seat's own,
# 2026-09-11; PR review of 7e33908, finding 2). Measured 2026-09-11: all 80
# supervisor openers on this Mac match, and the hand brief does not.
REINCARNATION_OPENER_PATTERN = re.compile(
    r"Read .+? — (?:it is )?" + re.escape(REINCARNATION_OPENER_MARKER))
# The supervisor's other ignition shape: a boot that finds an unconsumed
# handoff but no dialog to extract (BootRecoveryIgnitionPlan) puts the next
# step first and then this note. It is composed in the same consumed-handoff
# block as the opener, and fired four times on this Mac, 2026-08-16/17
# (review finding 1).
BOOT_RECOVERY_IGNITION_MARKER = "(Recovered at supervisor boot:"
SUBSTANTIVE_ASSISTANT_TURNS_MINIMUM = 2
# The size guard: a seat's first-ever session legitimately starts with the
# no-handoff prompt and can then do real work (observed live 2026-08-22 —
# fixer1's 1880KB genuine session began exactly so, and a marker-only filter
# wrongly wrote it off). The crash-day empty successors were a few KB. A
# transcript too small to hold real work is also skipped when its first
# user turn is missing or unreadable — a 0-byte or no-user-turn file is
# not the seat's real work either (finding 3's second shape).
EMPTY_SUCCESSOR_MAX_BYTES = 100_000
# The model name the harness writes on assistant turns it authors itself —
# API error notices (a session limit, "Not logged in", 529 Overloaded,
# "Prompt is too long") and the "No response requested." filler that a
# resume of an interrupted session appends. None of them is work. Measured
# 2026-09-11 across forty days of this Mac's transcripts: every such record
# is text-only.
SYNTHETIC_ASSISTANT_MODEL = "<synthetic>"


def default_agents_root() -> Path:
    """${NEDSCHORUS_AGENTS_ROOT:-~/agents}, as both launchers resolve it.
    Resolving differently means, on a machine where that variable is set,
    assessing ~/agents while every seat lives elsewhere — recovery then
    refuses on "no seat directory" (PR #131 round-4 review note; user-ruled
    2026-08-22: allowed overrides must work)."""
    return Path(os.environ.get("NEDSCHORUS_AGENTS_ROOT") or "~/agents").expanduser()


def default_handoff_directory() -> Path:
    return Path("~/.claude/handoffs").expanduser()


def harness_project_directory(seat_directory: Path, projects_root: Path) -> Path:
    """The harness's transcript directory for sessions run in this seat.

    Delegates to watch-agent-dialogs.py's project_directory_for_seat — the
    one probe-verified statement of the harness's mangling rule (every
    character outside ASCII [a-zA-Z0-9] becomes a dash, underscores
    included). The first build re-derived the rule locally as
    replace("/","-").replace(".","-"), which preserves underscores — and an
    underscore-named seat's intact transcript became invisible, routing
    recovery to ignite beside the prize (PR #131 review round 2, P1;
    CLAUDE.md's use-the-existing-name rule applies to functions too).
    """
    return watcher.project_directory_for_seat(seat_directory, projects_root)


def run_tmux(*arguments_after_tmux, socket_name=None):
    """One tmux call; None when tmux cannot answer (missing binary, timeout).

    Mirrors resupervise-seat.py's guard for the same reason: a machine
    without tmux must get a refusal, not a traceback.
    """
    if shutil.which("tmux") is None:
        return None
    socket_arguments = [] if socket_name is None else ["-L", socket_name]
    try:
        return subprocess.run(
            ["tmux", *socket_arguments, *arguments_after_tmux],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def tmux_session_alive_anywhere(name: str):
    """(alive, detail): whether any tmux server still holds this seat's name.
    alive is None when tmux cannot answer at all — the caller refuses, the
    same fail-closed rule as the lsof check (PR #131 review, finding 1: an
    unanswerable liveness axis must never read as "dead").

    Per-seat servers (2026-08-21) put a seat's session on socket -L <name>;
    seats launched before that change live on the default socket. Both are
    checked, and either holding the name means the seat is NOT dead.
    """
    for socket_name in dict.fromkeys((name, "default")):
        completed = run_tmux("has-session", "-t", f"={name}", socket_name=socket_name)
        if completed is None:
            return None, ("tmux cannot be run here, so seat liveness cannot be "
                          "checked — refusing rather than guessing")
        if completed.returncode == 0:
            return True, f"tmux session '{name}' is alive on socket '{socket_name}'"
    return False, ""


def processes_rooted_in_seat_directory(seat_directory: Path,
                                       require_a_complete_listing=False):
    """(process_ids, unusable_detail): the id of every live process whose
    working directory is the seat directory or under it — or (None, why) when
    lsof's answer cannot be trusted.

    The same lsof contract as resupervise-seat.py and clean-worktrees.py:
    vacancy is proven, never assumed, so every unusable answer is None here
    and occupied to the caller below.

    It reads process ids (`-F pn`) as well as paths because a path alone
    cannot tell a seat's own leftover shell from anything else rooted in the
    seat — and telling those apart is the whole of the idle-shell proof below
    (ruled 2026-09-17).

    require_a_complete_listing is for the callers that read this list the
    other way round. By default a listing that names the seat is positive
    evidence however lsof exited, because for "is anything in there?" a
    partial answer that says yes is still a yes. The idle-shell proof asks the
    opposite — "is nothing in there but these panes?" — and a partial listing
    cannot answer that at all, so those callers demand a listing lsof did not
    flag. Measured 2026-09-17: this lsof exits zero on both machines in the
    ordinary case, the box's unreadable-process lines included, so the demand
    costs nothing that works today.
    """
    if shutil.which("lsof") is None:
        return None, "lsof is not installed, so the seat cannot be proven vacant"
    try:
        listing = subprocess.run(
            ["lsof", "-a", "-d", "cwd", "-F", "pn"],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, "the occupancy check (lsof) could not be run"
    prefix = str(seat_directory.resolve())
    rooted = []
    reported = 0
    process_id = None
    for line in listing.stdout.splitlines():
        if line.startswith("p"):
            try:
                process_id = int(line[1:])
            except ValueError:
                process_id = None
        elif line.startswith("n"):
            reported += 1
            cwd = line[1:]
            if cwd == prefix or cwd.startswith(prefix + "/"):
                if process_id is None:
                    return None, (f"the occupancy check (lsof) named {prefix} without a "
                                  "usable process id; vacancy unproven")
                rooted.append(process_id)
    # A listing that names the seat is positive evidence however the run
    # exited, so a match is answered before the exit code is judged — the rule
    # this check has kept since PR #131's review, and the one
    # require_a_complete_listing suspends for the callers reading the list the
    # other way round.
    if rooted and not require_a_complete_listing:
        return rooted, ""
    if listing.returncode != 0:
        return None, f"the occupancy check (lsof) exited {listing.returncode}; vacancy unproven"
    if reported == 0:
        return None, "the occupancy check (lsof) reported no working directories at all"
    return rooted, ""


def seat_directory_occupied(seat_directory: Path, apart_from_process_ids=()):
    """(occupied, detail): is any live process rooted in the seat directory?

    An unusable answer counts as occupied, because recovering a seat something
    is still working in is the one harm this script must never do.

    apart_from_process_ids are the panes of a leftover idle shell this
    recovery has just retired at the operator's word (ruled 2026-09-17). Those
    processes WERE the session that was closed, and they die on tmux's signal
    rather than on this script's clock: counting them would refuse the very
    seat the operator just cleared, whenever lsof ran before the shell had
    finished exiting. Excusing a process turns this into a question about what
    is NOT in the listing, which a partial listing cannot answer, so a run
    with panes to excuse demands a complete one.
    """
    rooted, unusable_detail = processes_rooted_in_seat_directory(
        seat_directory, require_a_complete_listing=bool(apart_from_process_ids))
    if rooted is None:
        return True, unusable_detail
    retired = set(apart_from_process_ids)
    if any(process_id not in retired for process_id in rooted):
        return True, f"a live process is rooted in {seat_directory.resolve()}"
    return False, ""


# What a pane may be running for its session to be nothing but the after-exit
# shell. tmux names the command of the pane terminal's foreground process
# group, so a shell here means the shell has nothing in the foreground — and
# ONLY that. Measured on this Mac, 2026-09-17: a LIVE attached seat reports
# `zsh` too, because the launcher's pane command is
# `zsh -c "trap ...; <supervisor>; <after-exit>"` and the supervisor runs as
# its child inside the same process group (seat fleet-restart-at-login, pane
# process 27178 `zsh`, supervisor 27179 `Python`). The occupancy half of the
# proof below is what separates the two, and neither half alone is enough.
LEFTOVER_IDLE_SHELL_PANE_COMMANDS = (
    "bash", "zsh", "sh", "dash", "ksh", "fish", "tcsh", "csh",
)


def tmux_session_is_a_leftover_idle_shell(name: str, seat_directory: Path):
    """(proven, pane_process_ids, detail): is every tmux session holding this
    seat's name nothing but the shell an attached launch leaves open?

    The launcher's AFTER_EXIT_COMMAND ends `exec ${SHELL:-/bin/sh}` in the
    seat's directory (scripts/launch-claude-mac, scripts/launch-claude-ubuntu),
    so that shell REPLACES the pane's process and keeps its process id — which
    is why a pane's own id is the id to expect from lsof below.

    proven is True only when both measurements say so, and False whenever
    either cannot be taken — the same fail-closed rule the checks above keep:

      1. Every pane of every session named for this seat, on the seat's own
         socket and the default one, runs one of
         LEFTOVER_IDLE_SHELL_PANE_COMMANDS. This catches work in the pane's
         foreground wherever its working directory is, and it is also what
         stops a recovery run from inside the seat's own window from closing
         the terminal doing the closing: that pane would report the recovery
         tool, not a shell (the hazard resupervise-seat.py guards with $TMUX).
      2. Every process rooted in the seat directory is one of those panes'
         own process ids. This is the half that separates an idle shell from a
         live attached seat, whose pane reports a shell as well.

    pane_process_ids are those panes' process ids, which the caller hands back
    to the occupancy check after retiring the session.
    """
    pane_process_ids = []
    sockets_holding = []
    for socket_name in dict.fromkeys((name, "default")):
        held = run_tmux("has-session", "-t", f"={name}", socket_name=socket_name)
        if held is None:
            return False, [], ("tmux cannot be run here, so the session cannot be shown "
                               "to be an idle shell")
        if held.returncode != 0:
            continue
        panes = run_tmux("list-panes", "-s", "-t", f"={name}",
                         "-F", "#{pane_pid}\t#{pane_current_command}",
                         socket_name=socket_name)
        if panes is None or panes.returncode != 0:
            return False, [], (f"tmux could not list the panes of session '{name}' on socket "
                               f"'{socket_name}', so it cannot be shown to be an idle shell")
        lines = [line for line in panes.stdout.splitlines() if line.strip()]
        if not lines:
            return False, [], (f"tmux listed no panes for session '{name}' on socket "
                               f"'{socket_name}', so it cannot be shown to be an idle shell")
        for line in lines:
            reported_id, _, command = line.partition("\t")
            command = command.strip()
            try:
                pane_process_ids.append(int(reported_id.strip()))
            except ValueError:
                return False, [], (f"tmux reported a pane of session '{name}' on socket "
                                   f"'{socket_name}' without a usable process id ({line!r}), "
                                   "so it cannot be shown to be an idle shell")
            if command not in LEFTOVER_IDLE_SHELL_PANE_COMMANDS:
                return False, [], (f"a pane of session '{name}' on socket '{socket_name}' is "
                                   f"running {command or 'a command tmux did not name'}, not "
                                   "an idle shell")
        sockets_holding.append(socket_name)
    if not sockets_holding:
        return False, [], f"no tmux server holds a session named '{name}'"

    rooted, unusable_detail = processes_rooted_in_seat_directory(
        seat_directory, require_a_complete_listing=True)
    if rooted is None:
        return False, [], (f"{unusable_detail}, so the session cannot be shown to be an "
                           "idle shell")
    strangers = sorted(set(rooted) - set(pane_process_ids))
    if strangers:
        return False, [], (
            f"process {', '.join(str(process_id) for process_id in strangers)} is rooted in "
            f"{seat_directory.resolve()} and is not one of the session's own panes, so the "
            "session cannot be shown to be an idle shell")
    return True, pane_process_ids, (
        f"the {name} tmux session (socket{'s' if len(sockets_holding) > 1 else ''} "
        f"{', '.join(repr(socket_name) for socket_name in sockets_holding)}) is "
        f"{len(pane_process_ids)} pane{'s' if len(pane_process_ids) != 1 else ''} at a shell "
        f"with nothing in the foreground, and nothing but those panes is rooted in "
        f"{seat_directory.resolve()}")


# The verdicts whose recovery launches the seat: recover_seat's
# defer-to-boot-ignition, resume and ignite branches (--ignite-fallback turns a
# resume into an ignite, still a launch).
LEFTOVER_IDLE_SHELL_REASSESSMENT_VERDICTS_THAT_LAUNCH = (
    "defer-to-boot-ignition", "resume", "ignite",
)
# The verdicts whose recovery launches nothing on this tool's own account, and
# launches the seat only on an operator's yes (ruled 2026-09-18): to the
# leftover-shell question, and for a recorded exit also to the same question
# asked when no leftover session holds the seat's name. recover_seat's
# offer-after-recorded-exit and seat-asked-to-be-consulted branches.
LEFTOVER_IDLE_SHELL_REASSESSMENT_VERDICTS_RESTARTED_ONLY_ON_THE_OPERATORS_WORD = (
    "offer-after-recorded-exit", "seat-asked-to-be-consulted",
)


def restart_question_for_a_seat_with_a_recorded_exit(name: str, exit_code) -> str:
    """The question an operator at a terminal is asked about a seat whose
    supervisor recorded its agent's exit, with a leftover shell holding the
    seat's name or with no session at all (both ruled 2026-09-18).

    Worded by the recorded exit code (ruled 2026-09-18), because a supervisor
    also records the exit of an agent that died with an error while it
    watched — the design record: "a seat whose agent crashed while its
    supervisor kept watching produces a record too" — and for that seat
    "stopped on purpose" can be false. Code zero, or a code the record does not
    know, keeps the words ruled first; any other code is named instead.
    """
    if exit_code is None or exit_code == 0:
        return f"{name} stopped on purpose. Restart it anyway? y/n"
    return f"{name} stopped with exit code {exit_code}. Restart it? y/n"


def restart_after_recorded_exit_described(session_id) -> str:
    """What a yes to restart_question_for_a_seat_with_a_recorded_exit does, in
    the words a dry run reports it with: resume the recorded session, or start
    fresh when there is none."""
    if session_id is None:
        return "restart the seat as a fresh session"
    return f"restart the seat resuming session {session_id}"


def leftover_idle_shell_question_for_seat(name: str, predicted_verdict: str,
                                          predicted_detail=None) -> str:
    """The question an operator is asked, in the user's own words. One line,
    because it is read in the middle of a fleet-wide run.

    Ruled 2026-09-18 in a walk, of the words before these: "that is a confusing
    y/n question. kind of a double negative. I don't care about 'thes
    session'. I care about the reboot-test. perhaps resume reboot-test? Y/N."
    So the question names the seat and asks whether to restart it — "restart",
    not "resume", which in this project means picking up the seat's last
    conversation, and only the resume verdict does that. A yes restarts the
    seat on every verdict worded here:

      - a verdict that launches: "Restart <seat>? y/n".
      - offer-after-recorded-exit: restart_question_for_a_seat_with_a_recorded_exit,
        worded by the exit code in predicted_detail, (exit_code, recorded_at,
        session_id): "<seat> stopped on purpose. Restart it anyway? y/n" for
        code zero or an unknown code, "<seat> stopped with exit code <code>.
        Restart it? y/n" for any other. The rule that a seat stopped on
        purpose is not brought back is about this tool doing it on its own;
        here the operator decides.
      - seat-asked-to-be-consulted, ruled 2026-09-18: "<seat>'s handoff says:
        <its dont-restart reason>. Restart it? y/n", the reason read from
        predicted_detail, (counter, reason).

    Those five verdicts are the only ones this is ever called with. A predicted
    refuse or seat-already-running is not asked about at all (ruled 2026-09-18):
    recover_seat reports it straight away and leaves the window open, before
    reaching here. Anything else raises rather than put a question whose words
    were never chosen for it, and the suite walks every verdict assess_seat can
    return to keep each one either worded here or reported without asking.
    """
    if predicted_verdict in LEFTOVER_IDLE_SHELL_REASSESSMENT_VERDICTS_THAT_LAUNCH:
        return f"Restart {name}? y/n"
    if (predicted_verdict
            not in LEFTOVER_IDLE_SHELL_REASSESSMENT_VERDICTS_RESTARTED_ONLY_ON_THE_OPERATORS_WORD):
        raise ValueError(f"no leftover-shell question is worded for the verdict "
                         f"{predicted_verdict!r}")
    if predicted_verdict == "offer-after-recorded-exit":
        predicted_exit_code, _, _ = predicted_detail
        return restart_question_for_a_seat_with_a_recorded_exit(name, predicted_exit_code)
    _, reason = predicted_detail  # seat-asked-to-be-consulted: (counter, reason)
    reason = reason.strip()
    if not reason.endswith((".", "!", "?")):
        reason += "."
    return f"{name}'s handoff says: {reason} Restart it? y/n"


def recovery_has_an_operator_terminal() -> bool:
    """Is there an operator at a terminal to be asked a question?

    Both ends of the terminal, not stdin alone. restart-live-seats-at-login.py
    runs this tool as `run(command, stdout=subprocess.PIPE, text=True)` (its
    launch_seats_decided_restart), which inherits stdin: run by hand from a
    terminal, that child would have a tty on stdin and a pipe on stdout — a
    question nobody can see, in front of an input() that never returns.
    Asking only when the answer can be both shown and read keeps the
    2026-09-16 refusal, and a recorded exit's NOT RELAUNCHED line, in place on
    every path an operator is not watching.
    """
    try:
        return bool(sys.stdin.isatty() and sys.stdout.isatty())
    except (AttributeError, ValueError):
        # A stream closed or replaced by something that cannot answer: no
        # terminal, so no question.
        return False


def ask_operator_yes_or_no(question: str) -> bool:
    """True only on an explicit yes. Everything else is a no (ruled
    2026-09-17) — a bare return, a word this does not know, end of input, an
    interrupt — because a no falls back to what this tool does with nobody to
    ask (the leftover shell's refusal, a recorded exit's NOT RELAUNCHED line),
    which is the safe one.
    """
    try:
        answer = input(f"{question} ")
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer.strip().lower() in ("y", "yes")


def first_user_turn_text(transcript_path: Path) -> str:
    """The first non-meta user turn's text, or "" when none is readable."""
    try:
        with transcript_path.open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("type") != "user" or record.get("isMeta"):
                    continue
                content = (record.get("message") or {}).get("content")
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    return json.dumps(content)
                return ""
    except OSError:
        pass
    return ""


def substantive_turn_count(transcript_path: Path) -> int:
    """Assistant turns carrying text or tool use — the working measure of
    "this session did something". A failed successor dies at or before its
    first reply; a crashed-but-working one replied or called tools after the
    opener. Tool calls count because a terse tool-heavy stint is an ordinary
    seat shape (PR #131 review round 3, finding 2: text-only counting wrote
    off a successor whose work was 12 tool calls and one reply). The
    harness's own turns are not counted (SYNTHETIC_ASSISTANT_MODEL): on
    2026-09-10 a session-limit notice was a successor's only "reply"."""
    count = 0
    try:
        with transcript_path.open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("type") != "assistant":
                    continue
                message = record.get("message") or {}
                if message.get("model") == SYNTHETIC_ASSISTANT_MODEL:
                    continue
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    count += 1
                elif isinstance(content, list) and any(
                        x.get("type") == "tool_use"
                        or (x.get("type") == "text" and x.get("text", "").strip())
                        for x in content if isinstance(x, dict)):
                    count += 1
    except OSError:
        pass
    return count


def is_unreplied_reincarnation_successor(transcript_path: Path) -> bool:
    """A successor the supervisor started from a handoff that never replied:
    no substantive turn at all once the harness's own turns are set aside.
    The 2026-09-10 shape — ignited at 20:09 PDT, its only turn the
    session-limit notice, then the Mac rebooted. Both of the supervisor's
    ignition shapes count, the dialog opener and the boot-recovery note.
    Either way it is the seat's current incarnation (see
    REINCARNATION_OPENER_MARKER), so it is resumed, and its resume prompt
    says its first reply never happened rather than that it crashed."""
    first_turn = first_user_turn_text(transcript_path)
    return ((REINCARNATION_OPENER_PATTERN.match(first_turn) is not None
             or BOOT_RECOVERY_IGNITION_MARKER in first_turn)
            and substantive_turn_count(transcript_path) == 0)


def newest_real_transcript(project_directory: Path):
    """(session_id, transcript_path) of the newest transcript that is not an
    empty-successor session, or (None, reason).
    """
    if not project_directory.is_dir():
        return None, f"no harness project directory at {project_directory}"
    candidates = sorted(
        project_directory.glob("*.jsonl"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return None, f"no transcripts under {project_directory}"
    for transcript in candidates:
        if transcript.stat().st_size <= EMPTY_SUCCESSOR_MAX_BYTES:
            first_turn = first_user_turn_text(transcript)
            if not first_turn.strip():
                continue  # small with no readable user turn: not real work
            if (any(marker in first_turn for marker in EMPTY_SUCCESSOR_MARKERS)
                    and substantive_turn_count(transcript)
                        < SUBSTANTIVE_ASSISTANT_TURNS_MINIMUM):
                continue  # machinery-composed opener and no work: failed successor
        return transcript.stem, transcript
    return None, ("every transcript is an empty-successor session; nothing "
                  "worth resuming")


def resume_prompt_path(handoff_directory: Path, name: str) -> Path:
    return handoff_directory / f"{name}-resume-recovery-prompt.md"


def write_resume_prompt(handoff_directory: Path, name: str,
                        unreplied_successor: bool = False) -> Path:
    """The resumed session's first turn (PR #131 review, finding 2): without
    this, the supervisor's default first prompt tells a mid-task agent that
    no handoff exists and to ask for work — pointing it away from the
    context the resume just restored. The hand recovery sent no prompt; a
    supervised launch must send one, so it says what actually happened.
    An unreplied reincarnation successor did not die mid-work — it never
    started — so "died without writing a handoff" would be false for it
    (the 2026-09-10 reboot); it is told to act on its ignition prompt."""
    # A --handoff-dir that does not exist yet must not crash the recovery
    # after assessment already chose to resume (PR #134 review, finding 2);
    # created the same way the supervisor creates its own on startup.
    handoff_directory.mkdir(parents=True, exist_ok=True)
    prompt_path = resume_prompt_path(handoff_directory, name)
    if unreplied_successor:
        prompt = (
            "This session was resumed by crash recovery (nedschorus#120). You "
            "are the successor your predecessor's handoff started, and your "
            "first reply never happened: the session ended before you did any "
            "work (if the harness recorded why, its notice is above). The "
            "handoff was consumed when you were started, so nothing else will "
            "act on it. Act on your first prompt above now, re-verifying the "
            "repository's current state before trusting anything it says, "
            "since time has passed since the handoff was written."
        )
    else:
        prompt = (
            "This session was resumed by crash recovery (nedschorus#120): your "
            "previous incarnation died without writing a handoff — a crash, not a "
            "reincarnation — and your transcript was resumed under a fresh supervisor. "
            "Re-verify any in-flight state before trusting it (files you were "
            "mid-edit in, processes you were watching, messages you were owed), "
            "then continue the work you were doing."
        )
    prompt_path.write_text(prompt, encoding="utf-8")
    return prompt_path


def first_prompt_after_recorded_exit_path(handoff_directory: Path, name: str,
                                          by_hand: bool) -> Path:
    """Where write_first_prompt_after_recorded_exit puts its prompt: one file
    for the restart an operator says yes to, another for the by-hand resume
    command a report prints, so neither overwrites the other's words."""
    kind = "by-hand-resume" if by_hand else "operator-restart"
    return handoff_directory / f"{name}-{kind}-after-recorded-exit-prompt.md"


def write_first_prompt_after_recorded_exit(handoff_directory: Path, name: str,
                                           by_hand: bool, resuming: bool) -> Path:
    """The first turn of a seat brought back after its supervisor recorded its
    agent's exit — at an operator's yes (by_hand False), or by the by-hand
    resume command the NOT RELAUNCHED line prints (by_hand True, always
    resuming).

    Without it the supervisor's own first prompt is the wrong one: a resume
    with no prompt file tells the agent it "died without a handoff", a crash,
    for a seat that got here precisely because its exit was recorded (review
    5240813304 on the pull request that added the record).

    Every clause is true wherever it is used. The record is described as what
    it is — a supervisor records it when a session is stopped on purpose, and
    the design record admits it also follows an agent that failed with its
    supervisor watching — so the prompt never says which this was. The
    session it names is the seat's last one, which a resume need not be: a
    stillborn successor is passed over for its parent. "The operator" is only
    in the prompt for a yes at this tool's terminal; whoever runs a printed
    command may be someone else. None says "crash".
    """
    handoff_directory.mkdir(parents=True, exist_ok=True)
    prompt_path = first_prompt_after_recorded_exit_path(handoff_directory, name, by_hand)
    recorded = (f"This seat's supervisor recorded the exit of its last session, "
                f"{FIRST_PROMPT_AFTER_RECORDED_EXIT_MARKER}, so recovery did not bring the "
                "seat back on its own.")
    re_verify = "Re-verify any in-flight state before trusting it, then continue."
    if by_hand:
        prompt = (f"{recorded} It has now been restarted by hand, resuming this "
                  f"conversation. {re_verify}")
    elif resuming:
        prompt = (f"{recorded} The operator has now restarted the seat, resuming this "
                  f"conversation. {re_verify}")
    else:
        prompt = (f"You are {name}. {recorded} The operator has now restarted the seat as "
                  "a fresh session, so none of that conversation is here. Ask what to "
                  "work on.")
    prompt_path.write_text(prompt, encoding="utf-8")
    return prompt_path


def newest_dialog_extract(handoff_directory: Path, name: str):
    """The newest <name>-dialog-NNNN.md, for the ignite fallback."""
    extracts = sorted(handoff_directory.glob(f"{name}-dialog-*.md"))
    return extracts[-1] if extracts else None


def launcher_path():
    """The local machine's seat launcher. Box recovery runs this script ON
    the box, where the Mac launcher is absent — launch-claude-ubuntu is a
    Mac-side wrapper that drives the box over ssh, so it is not the box-local
    answer; there, the launch is composed directly (see launch_seat)."""
    if sys.platform == "darwin":
        # Absolute, because an iTerm window's command starts in / with a bare
        # PATH (--open-iterm-window-per-seat), and this script is usually run
        # by a relative path.
        return Path(__file__).resolve().with_name("launch-claude-mac")
    return None


def compose_supervisor_arguments_for_seat_launch(handoff_directory: Path,
                                                 extra_supervisor_arguments: str) -> str:
    """The supervisor's arguments for a recovery launch: always the handoff
    directory this recovery assessed with (see launch_seat), then the rest."""
    supervisor_arguments = f"--handoff-dir {shlex.quote(str(handoff_directory))}"
    if extra_supervisor_arguments:
        supervisor_arguments += f" {extra_supervisor_arguments}"
    return supervisor_arguments


def by_hand_launch_command_for_seat(name: str, seat_directory: Path, handoff_directory: Path,
                                    extra_supervisor_arguments: str,
                                    first_prompt_file: Path = None) -> str:
    """The command an operator types to launch this seat under a supervisor,
    carrying what launch_seat would pass: the agents root, the supervisor
    arguments, and a first-prompt file through the launcher's own
    --first-prompt-file, as launch_seat passes it. On the Mac it runs
    launch-claude-mac; elsewhere it names launch-claude-ubuntu, which is run on
    the Mac and drives the box, and whose --first-prompt-file takes a box-side
    path — which a file this tool wrote on the box is."""
    launcher = launcher_path()
    words = [
        f"NEDSCHORUS_AGENTS_ROOT={shlex.quote(str(seat_directory.parent))}",
        "LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS=" + shlex.quote(
            compose_supervisor_arguments_for_seat_launch(handoff_directory,
                                                         extra_supervisor_arguments)),
        "launch-claude-ubuntu" if launcher is None else shlex.quote(str(launcher)),
        shlex.quote(name),
    ]
    if first_prompt_file is not None:
        words += ["--first-prompt-file", shlex.quote(str(first_prompt_file))]
    command = " ".join(words)
    return command if launcher is not None else f"{command} (on the Mac)"


def launch_seat(name: str, seat_directory: Path, handoff_directory: Path,
                extra_supervisor_arguments: str, first_prompt_file: Path = None):
    """Start the seat detached under its supervisor, on its own tmux server.

    On the Mac this rides launch-claude-mac (which owns the update step,
    checkout prep, and transition socket selection). On the box — where the
    only launcher is the Mac-side ssh wrapper — the supervisor is started
    directly in a per-seat tmux session, mirroring what launch-claude-ubuntu
    composes remotely; the update/prep steps are skipped, which recovery can
    afford (the seat ran this checkout minutes before the crash).

    The supervisor is always told the handoff directory this recovery
    assessed with (PR #131 review round 3, codex finding A: without it the
    supervisor fell back to its own default, so under --handoff-dir the
    boot-ignition watched an empty directory and supervisor state split
    across two directories). The launcher branch likewise pins the agents
    root the assessment used (codex finding B: the launcher's own
    NEDSCHORUS_AGENTS_ROOT default made it create and attach a fresh seat
    beside the assessed one — under --agents-root, and on the DEFAULT
    no-flag path on any machine where that variable is set).
    """
    launcher = launcher_path()
    environment = dict(os.environ)
    # shlex.quote, not hand-written single quotes: each value here is parsed
    # by exactly one shell (the launcher appends it verbatim and tmux runs
    # the composed command through sh), and an apostrophe in an operator's
    # path breaks a hand-quoted string — the kill has already happened by
    # then, so the seat stays down while the output says otherwise (PR #134
    # review, finding 1).
    supervisor_arguments = compose_supervisor_arguments_for_seat_launch(
        handoff_directory, extra_supervisor_arguments)
    if launcher is not None:
        environment["LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS"] = supervisor_arguments
        environment["NEDSCHORUS_AGENTS_ROOT"] = str(seat_directory.parent)
        command = [str(launcher), name, "--no-attach"]
        if first_prompt_file is not None:
            command += ["--first-prompt-file", str(first_prompt_file)]
        return subprocess.run(command, env=environment, check=False).returncode

    # This branch hand-composes what the launcher would have composed, so it
    # must carry the launcher's seat environment too — the task-list binding
    # included (nedschorus#141, scripts/launch-claude-mac, where the
    # mechanism is written out). Without it, the recovered generation runs
    # with no task tools and no pin: its list is invisible, TaskList returns
    # empty and TaskUpdate answers "Task not found", both with no error —
    # the launcher comment's Warning 2, arriving at the one moment
    # continuity is being promised. The launcher branch above needs nothing
    # here; it runs the launcher, which does this itself.
    # The one-time store migration rides here too (user-ruled 2026-08-29):
    # this branch bypasses the launcher, so without the rename a recovered
    # seat would pin to an empty prefixed store while its list sat under the
    # old unprefixed name. The name is embedded unquoted inside the
    # double-quoted paths so $HOME expands box-side, safe for the same
    # reason as the launchers: seat names are charset-validated at launch.
    supervisor_command = (
        'export PATH="$HOME/.local/bin:$PATH"; '
        f'if [ -d "$HOME/.claude/tasks/{name}-tasks" ] && '
        f'[ ! -e "$HOME/.claude/tasks/nedschorus-{name}-tasks" ]; then '
        f'mv "$HOME/.claude/tasks/{name}-tasks" '
        f'"$HOME/.claude/tasks/nedschorus-{name}-tasks"; fi; '
        f"export CLAUDE_CODE_TASK_LIST_ID={shlex.quote(f'nedschorus-{name}-tasks')}; "
        "export CLAUDE_CODE_ENABLE_TODO_TOOLS=1; "
        f"python3 {Path(__file__).with_name('handoff-supervisor.py')} "
        f"--agent {shlex.quote(name)} --cd {shlex.quote(str(seat_directory))} "
        f"{supervisor_arguments}"
    )
    if first_prompt_file is not None:
        supervisor_command += f" --first-prompt-file {shlex.quote(str(first_prompt_file))}"
    completed = run_tmux(
        "new-session", "-d", "-s", name, "-c", str(seat_directory),
        supervisor_command, socket_name=name,
    )
    return 1 if completed is None else completed.returncode


def iterm_window_command_text(name: str, seat_directory: Path, handoff_directory: Path,
                             extra_supervisor_arguments: str,
                             first_prompt_file: Path = None) -> str:
    """The command an iTerm window runs to launch this seat ATTACHED
    (nedschorus#242 change 6; the #120 overview, § recover into a window).

    The window's process is a child of iTerm, not of this script, so it
    inherits iTerm's environment. What launch_seat passes through the
    environment — the supervisor arguments and the agents root — is written
    into the command instead, `/usr/bin/env 'NAME=value' <launcher> <seat>`;
    written naively, each window would start a fresh seat while looking like
    a recovery. iTerm2 splits the text shell-style with one level of quoting,
    so every word is single-quoted. It has no POSIX '\\'' escape (measured
    2026-09-02, recorded in open-iterm-window-running-command), so no word
    here may contain a single quote — an apostrophe in a path, or the shell
    quoting shlex.quote adds around a handoff directory holding a space.
    main() refuses both before anything launches; this raises rather than
    open a window whose command iTerm would split wrong.
    """
    words = ["/usr/bin/env",
             "LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS="
             + compose_supervisor_arguments_for_seat_launch(
                 handoff_directory, extra_supervisor_arguments),
             f"NEDSCHORUS_AGENTS_ROOT={seat_directory.parent}",
             str(launcher_path()), name]
    if first_prompt_file is not None:
        words += ["--first-prompt-file", str(first_prompt_file)]
    for word in words:
        if "'" in word:
            raise ValueError("an iTerm window command cannot carry a word holding a "
                             f"single quote: {word!r}")
    return " ".join(f"'{word}'" for word in words)


def open_seat_in_iterm_window(name: str, seat_directory: Path, handoff_directory: Path,
                              extra_supervisor_arguments: str,
                              first_prompt_file: Path = None):
    """launch_seat's twin for --open-iterm-window-per-seat: the seat is born
    attached in its own iTerm window, through open-iterm-window-running-command
    (the only sanctioned way to open a window that runs a command,
    nedschorus#27). Born attached, its pane drops to a shell in the seat's
    directory when the supervisor exits, instead of closing. Returns the
    opener's exit code, which says the window was asked for — not that the
    seat came up inside it (#242 change 4 is that check)."""
    opener = Path(__file__).resolve().with_name("open-iterm-window-running-command")
    command_text = iterm_window_command_text(name, seat_directory, handoff_directory,
                                             extra_supervisor_arguments, first_prompt_file)
    return subprocess.run([str(opener), command_text], check=False).returncode


# The three answers seat_supervisor_confirmed_by_ps gives. Only the first lets
# assess_seat call a seat already running (user-ruled 2026-09-16).
SUPERVISOR_CONFIRMED_BY_PS = "confirmed-by-ps"
SUPERVISOR_ASSUMED_WITHOUT_PS = "assumed-without-ps"
SUPERVISOR_NOT_CONFIRMED = "supervisor-not-confirmed"


def seat_supervisor_confirmed_by_ps(name: str, lock_path: Path):
    """(answer, identity): is the holder of this seat's supervisor lock a live
    supervisor of this seat, CONFIRMED by ps?

    SUPERVISOR_CONFIRMED_BY_PS: ps ran, and the holder runs the supervisor for
    this seat. SUPERVISOR_ASSUMED_WITHOUT_PS: process_is_supervisor_for_agent
    said yes only because ps could not be run and a process with the lock's
    id exists. SUPERVISOR_NOT_CONFIRMED: anything else — no lock, an
    unreadable one (the launcher's own reclaim handles a stale lock), or a
    holder that is not this seat's supervisor. identity is the predicate's
    sentence, or why there was no process to ask about.

    The predicate is used unchanged, because its other callers act on its
    assumption deliberately (see its docstring) and a second copy of its
    identity rules would drift. What this adds is knowing whether ps answered
    without reading the predicate's English: the reader handed to it records
    that. supervisor.read_process_command_line is looked up when the reader
    runs, not bound as a default argument, so a test that replaces the module
    attribute reaches this function — unlike the predicate's own default
    reader, which its docstring's NOTE warns about.
    """
    try:
        holder = int(lock_path.read_text(encoding="utf-8").strip())
    except FileNotFoundError:
        return SUPERVISOR_NOT_CONFIRMED, f"no supervisor lock at {lock_path}"
    except (ValueError, OSError) as error:
        return SUPERVISOR_NOT_CONFIRMED, (
            f"the supervisor lock at {lock_path} is unreadable: {error}")

    ps_answered_each_time = []

    def read_command_line_recording_whether_ps_answered(process_id):
        command_line, ps_answered = supervisor.read_process_command_line(process_id)
        ps_answered_each_time.append(ps_answered)
        return command_line, ps_answered

    held, identity = supervisor.process_is_supervisor_for_agent(
        holder, name, read_command_line=read_command_line_recording_whether_ps_answered)
    if not held:
        return SUPERVISOR_NOT_CONFIRMED, identity
    if ps_answered_each_time and all(ps_answered_each_time):
        return SUPERVISOR_CONFIRMED_BY_PS, identity
    return SUPERVISOR_ASSUMED_WITHOUT_PS, identity


ASK_TO_CLOSE_THE_LEFTOVER_IDLE_SHELL_VERDICT = "ask-to-close-the-leftover-idle-shell"


def assess_seat(name: str, agents_root: Path, handoff_directory: Path,
                projects_root: Path, retired_pane_process_ids=(),
                predicting_as_though_the_leftover_idle_shell_were_closed=False):
    """Decide what recovery this seat needs.

    Returns (verdict, detail): seat-already-running / refuse /
    ask-to-close-the-leftover-idle-shell (detail is (refusal,
    pane_process_ids, shell_detail)) / defer-to-boot-ignition /
    seat-asked-to-be-consulted (detail is (counter, the handoff's dont-restart
    reason)) / offer-after-recorded-exit (detail is
    (exit_code, recorded_at, session_id), session_id None when nothing could
    be resumed) / resume (detail is (session_id, transcript_path)) / ignite
    (detail is the reason no resume is possible).

    ask-to-close-the-leftover-idle-shell decides nothing by itself: the seat's
    tmux session is alive with no confirmed supervisor, AND this function
    could prove it is nothing but a leftover idle shell, so the caller may put
    the question to an operator (user-ruled 2026-09-17). It is the caller that
    knows whether there is anyone to ask, and the caller that carries the
    refusal to give when there is not — which is why the refusal travels in
    the detail rather than being composed twice.

    retired_pane_process_ids are the panes of a leftover idle shell the caller
    has just closed. They are excused from the occupancy check, so the
    assessment runs as though that session had never been there — which is
    what the operator asked for by answering yes.

    predicting_as_though_the_leftover_idle_shell_were_closed is for
    predicted_assessment_once_the_leftover_idle_shell_is_closed alone: it reads a
    live tmux session as already closed, so the assessment can be taken before
    the retire. Without it a live session always decides at the `if alive:`
    branch, retired_pane_process_ids or not, because they are consulted only
    at the occupancy check after it.

    offer-after-recorded-exit launches nothing on this tool's own account
    (nedschorus#242 change 2): the seat's supervisor recorded that its agent
    exited, so it is not a crash, and the seat is offered to be brought back by
    hand — or restarted, when an operator at a terminal says yes to the
    restart question recover_seat asks, leftover shell or none (ruled
    2026-09-18). Any recorded exit counts, code zero or not, known or not; only
    a seat with no record is resumed automatically.

    seat-already-running is not a refusal (user-ruled 2026-09-16, on the
    question PR #426's reviewer asked): a seat a live supervisor of which is
    confirmed was not recovered because it did not need to be, and --all
    lists every seat that ever ran, live ones included. The supervisor must
    be CONFIRMED by ps (user-ruled 2026-09-16, on PR #426's review of this
    verdict): a tmux session alive with no confirmed supervisor, and a
    supervisor only assumed because ps could not be run, are refuse — each
    is a liveness question this tool could not answer, not a seat found
    running. Everything else this function cannot prove safe stays refuse.
    """
    seat_directory = agents_root / name
    if not seat_directory.is_dir():
        return "refuse", f"no seat directory at {seat_directory}"

    alive, detail = tmux_session_alive_anywhere(name)
    if alive is None:
        return "refuse", detail

    # A supervisor lock held by a live supervisor means one is starting or
    # racing this assessment (PR #131 review, question 3): the launch this
    # script would start exits at once against that lock, and finding-1's fix
    # would then report a failure — reporting the seat as running here is
    # clearer. This is the check that catches a supervisor which has claimed
    # its lock but not yet written a state file, which supervisor_liveness
    # cannot see.
    #
    # Held by a live SUPERVISOR OF THIS SEAT, not merely a live process
    # (nedschorus#242 change 1): this file outlives a reboot and process ids
    # are reused across it, so a bare check would call the very seat the login
    # restart was asked to bring back already running, and leave it down.
    #
    # Asked here, before the tmux answer is acted on, because a live tmux
    # session needs the same confirmation.
    lock_path = handoff_directory / f"{name}-supervisor.lock"
    supervisor_answer, identity = seat_supervisor_confirmed_by_ps(name, lock_path)

    # A live tmux session is not proof that the seat is running: an attached
    # launch leaves its pane open at a shell in the seat's directory after the
    # supervisor exits (scripts/launch-claude-mac, AFTER_EXIT_COMMAND), so the
    # session outlives the supervisor. Refused unless a live supervisor of this
    # seat is confirmed (user-ruled 2026-09-16, PR #426 review 5228560398) —
    # and either way nothing is launched into a live session.
    #
    # Unless that session can be PROVEN to be that leftover shell and nothing
    # else, in which case it becomes a question for an operator rather than a
    # refusal (user-ruled 2026-09-17). The refusal below is what an unattended
    # caller still gets, unchanged, so it is composed here either way.
    if alive and not predicting_as_though_the_leftover_idle_shell_were_closed:
        if supervisor_answer == SUPERVISOR_CONFIRMED_BY_PS:
            return "seat-already-running", (
                f"{detail}, and {identity} — this tool recovers crashes, it never "
                "touches live seats")
        refusal = (
            f"{detail}, but no live supervisor of this seat is confirmed ({identity}) — "
            "this tool never touches a live tmux session. If the seat's supervisor has "
            "exited, that session is the shell an attached launch leaves open: exit it, "
            "then rerun this recovery")
        leftover_shell, pane_process_ids, shell_detail = (
            tmux_session_is_a_leftover_idle_shell(name, seat_directory))
        if not leftover_shell:
            return "refuse", refusal
        # No question is composed here: its words depend on a prediction that
        # recover_seat takes only where the question is shown, so an
        # unattended run does exactly what it did before the prediction.
        return ASK_TO_CLOSE_THE_LEFTOVER_IDLE_SHELL_VERDICT, (
            refusal, pane_process_ids, shell_detail)

    if supervisor_answer == SUPERVISOR_CONFIRMED_BY_PS:
        return "seat-already-running", (
            f"the supervisor lock at {lock_path} is held by a live supervisor — {identity}")
    # ps could not be run and a process with the lock's id exists: the
    # predicate assumes a supervisor rather than risk a second one
    # (nedschorus#346), and this tool launches nothing on that assumption. But
    # it is an assumption, not a seat found running, so it is refused and
    # counts as not recovered (user-ruled 2026-09-16, PR #426 review
    # 5228492424): an unattended caller must not be told the seat is up.
    if supervisor_answer == SUPERVISOR_ASSUMED_WITHOUT_PS:
        return "refuse", (
            f"the supervisor lock at {lock_path} names a live process, but ps could not "
            f"confirm it is a supervisor of this seat — {identity}")

    state_path = handoff_directory / f"{name}-supervisor-state.json"
    supervisor_alive, liveness_detail = supervisor.supervisor_liveness(state_path)
    if supervisor_alive:
        # supervisor_liveness reads the same lock through the same predicate,
        # so it says yes on its own only when a supervisor claimed the lock
        # after the check above — and it says yes by the same assumption when
        # ps cannot be run, which it does not report apart. So the lock is
        # asked again, and only a confirmed supervisor is already running.
        watching_answer, watching_identity = seat_supervisor_confirmed_by_ps(name, lock_path)
        if watching_answer == SUPERVISOR_CONFIRMED_BY_PS:
            return ("seat-already-running",
                    f"a supervisor is watching this seat ({liveness_detail})")
        why_unconfirmed = ("ps could not confirm it"
                           if watching_answer == SUPERVISOR_ASSUMED_WITHOUT_PS
                           else "it could not be confirmed when asked again")
        return "refuse", (
            f"a supervisor may be watching this seat ({liveness_detail}), but "
            f"{why_unconfirmed} — {watching_identity}")

    occupied, occupancy_detail = seat_directory_occupied(
        seat_directory, apart_from_process_ids=retired_pane_process_ids)
    if occupied:
        return "refuse", occupancy_detail

    handoff_path = handoff_directory / f"{name}-handoff.md"
    if handoff_path.is_file():
        fields = supervisor.parse_handoff_file(handoff_path)
        counter = supervisor.counter_from(fields)
        state = supervisor.read_supervisor_state(state_path)
        consumed = state.get("consumed_counter")
        if counter is None:
            # A handoff whose counter is missing or unparseable would be
            # consumed by nobody — the supervisor's wait loop ignores it too.
            # Resuming past it silently discards whatever it says (PR #131
            # review, question 2); the operator decides, with both paths named.
            return "refuse", (
                f"a handoff exists at {handoff_path} but its restart-counter is "
                "missing or unreadable, so no supervisor would ever consume it. "
                "Read it: if it is real, fix its restart-counter and relaunch "
                "plain; if it is scrap, delete it and rerun this recovery"
            )
        if consumed is None or counter > consumed:
            dont_restart = fields.get("dont-restart")
            if dont_restart:
                # The seat asked to be consulted before a relaunch and died before
                # a supervisor could ask. Launching it only let the supervisor stop
                # at once, after which this tool waited out
                # SEAT_COMES_UP_DEADLINE_SECONDS and offered the forced restart the
                # seat had declined (nedschorus#350; user-ruled 2026-09-17: launch
                # nothing). The handoff stays unconsumed, so a by-hand launch still
                # reaches the supervisor's restart question. The reason travels
                # apart from the report, which recover_seat composes, because the
                # leftover-shell question shows it too.
                return "seat-asked-to-be-consulted", (counter, dont_restart)
            return "defer-to-boot-ignition", (
                f"an unconsumed handoff waits (counter {counter}, consumed "
                f"{consumed}) — plain relaunch is correct; the supervisor's "
                "boot-ignition consumes it"
            )

    session_id, found = newest_real_transcript(
        harness_project_directory(seat_directory, projects_root))

    # After the handoff checks, which a waiting handoff still settles, and in
    # place of both automatic launches below (nedschorus#242 change 2, ruled
    # 2026-09-02): a supervisor that outlived its agent recorded the exit, so
    # the seat did not crash, whatever the code says.
    exit_record = supervisor.agent_exit_record_from_supervisor_state(
        supervisor.read_supervisor_state(state_path))
    if exit_record is not None:
        exit_code, recorded_at = exit_record
        return "offer-after-recorded-exit", (exit_code, recorded_at, session_id)

    if session_id is None:
        return "ignite", str(found)
    return "resume", (session_id, found)


def predicted_assessment_once_the_leftover_idle_shell_is_closed(
        name: str, agents_root: Path, handoff_directory: Path, projects_root: Path,
        pane_process_ids):
    """(verdict, detail): the assessment the reassessment after a yes is
    expected to give, taken while the leftover idle shell's tmux session is
    still alive.

    It decides only what the operator is shown: whether the question is put at
    all (ruled 2026-09-18 — a predicted refuse or seat-already-running is
    reported straight away with this detail as its reason, and the window is
    left open), and in which words (ruled 2026-09-17, reworded 2026-09-18). What
    a yes actually does is decided, exactly as before, by the assessment
    recover_seat runs AFTER the retire, read with the operator's word to
    restart. The two can disagree when the seat's state moves while the
    operator thinks — a supervisor starting, a handoff landing — and then the
    real outcome wins and the line it prints says what actually happened. No
    attempt is made to close that gap.

    It is assess_seat itself, reading the live session as closed and excusing
    its panes from the occupancy check as the reassessment will. Past the tmux
    check assess_seat only reads (the supervisor lock and state, ps, lsof, the
    handoff, the transcripts), so asking early changes nothing on disk.
    """
    return assess_seat(
        name, agents_root, handoff_directory, projects_root,
        retired_pane_process_ids=pane_process_ids,
        predicting_as_though_the_leftover_idle_shell_were_closed=True)


# A supervisor notices its session has died within HANDOFF_POLL_SECONDS and then
# stops and removes its lock, so anything checked sooner than that can see a
# supervisor that is already finished. Three times the interval leaves room for
# the cleanup that follows.
SEAT_SETTLE_SECONDS = 3 * supervisor.HANDOFF_POLL_SECONDS
# How long a supervisor may take to appear at all. The launcher runs its Claude
# update step BEFORE starting the supervisor, and on the window path this script
# does not wait for the launcher — it waits only for the opener, which returns as
# soon as the window exists. So this has to cover an update, not a process start.
# A version change was observed taking tens of seconds on 2026-09-11; this is a
# generous multiple of that, and only a seat that never comes up pays it in full.
# Tunable: it is a fact about the user's machines, not about this program.
SEAT_COMES_UP_DEADLINE_SECONDS = 120.0
SEAT_COMES_UP_POLL_SECONDS = 0.5


def wait_for_the_seat_to_come_up(name: str, handoff_directory: Path,
                                 settle_seconds=SEAT_SETTLE_SECONDS,
                                 deadline_seconds=SEAT_COMES_UP_DEADLINE_SECONDS,
                                 identity_check=None, sleep=time.sleep,
                                 monotonic=time.monotonic):
    """(came_up, why): did a supervisor actually start for this seat and survive?

    nedschorus#242 change 4. A launch that exits zero says the launcher ran, not
    that the seat came back: a resume whose session dies inside Claude — a
    session id that no longer resolves, say — leaves the launcher exiting zero
    while the supervisor starts, watches the session end without a handoff, and
    stops. Reported as success, that is the login restart telling an absent
    operator the fleet is back when it is not.

    Two waits, and they are different. First, poll until a supervisor is seen at
    all, which can take as long as the launcher's update step. Then wait out
    SEAT_SETTLE_SECONDS and look again, because a supervisor whose session has
    already died still holds its lock for up to HANDOFF_POLL_SECONDS — so a
    single check right after it appears would call that coming up. The settle is
    measured from when the supervisor was FIRST SEEN, never from the launch:
    on the window path the launch returns before the launcher has even started.

    So what this answers is that a supervisor appeared and survived the settle,
    which is not quite that the seat is back: handoff-supervisor.py claims its
    lock at :1383, BEFORE supervise_sessions starts the session, so the first
    sighting can precede the session existing at all, and a session that dies
    more than SEAT_SETTLE_SECONDS after the lock appeared still reads here as
    come up (PR #329 review, raised as a question and left as a bound).
    """
    if identity_check is None:
        identity_check = supervisor.process_is_supervisor_for_agent
    lock_path = handoff_directory / f"{name}-supervisor.lock"

    def a_supervisor_is_running():
        try:
            holder = int(lock_path.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            return False, f"no readable supervisor lock at {lock_path}"
        return identity_check(holder, name)

    started_waiting = monotonic()
    while True:
        running, identity = a_supervisor_is_running()
        if running:
            break
        if monotonic() - started_waiting >= deadline_seconds:
            return False, (f"no supervisor appeared within {deadline_seconds:.0f}s — "
                           f"{identity}")
        sleep(SEAT_COMES_UP_POLL_SECONDS)

    sleep(settle_seconds)
    running, identity = a_supervisor_is_running()
    if running:
        return True, f"a supervisor was still running {settle_seconds:.0f}s after it started"
    return False, (f"a supervisor started and stopped again within {settle_seconds:.0f}s, "
                   f"so the session did not survive — {identity}")


def came_up_or_failure_report(name: str, handoff_directory: Path,
                              offer_ignite_fallback: bool):
    """None when the seat came up, else the report that says it did not.

    The offer is a sentence, not an action (nedschorus#242 change 4 says offer):
    falling back automatically would spend a session on a recovery that may be
    the wrong one. On the ignite paths there is nothing further to offer, because
    the degraded restart is what just failed.
    """
    came_up, why = wait_for_the_seat_to_come_up(name, handoff_directory)
    if came_up:
        return None
    offer = ("; the degraded restart is --ignite-fallback, which starts a fresh session "
             "from the newest dialog extract" if offer_ignite_fallback else "")
    return f"{name}: LAUNCHED BUT DID NOT COME UP — {why}{offer}"


# Every report class that means the seat is NOT running once this tool is done.
# ALREADY RUNNING is deliberately not one: that seat is running, and --all lists
# every seat that ever ran, so counting it made one live seat fail a whole run
# (user-ruled 2026-09-16, on the question PR #426's reviewer asked).
# main counts these for its exit code, and the suite enumerates this same tuple,
# so a failure report is covered the moment it is named here. It is one named
# tuple rather than substrings spelled into main because that is exactly how
# LAUNCHED BUT DID NOT COME UP slipped through: it contains neither "REFUSED"
# nor "LAUNCH FAILED", so the failure #242 change 4 was added to catch was
# printed, logged, and then exited zero — a login restart still reporting the
# fleet is back to an absent operator, by way of the status code this time
# (PR #329 review, finding 1).
# A seat that asked to be consulted is left down on purpose, but it is down: were
# it not counted, the login restart would list it with the seats that came up.
SEAT_ASKED_TO_BE_CONSULTED_REPORT_MARKER = "NOT RELAUNCHED, AT ITS OWN REQUEST"
# So is a seat whose supervisor recorded its agent's exit (nedschorus#242
# change 2): nothing is launched for it, and it is down.
SEAT_NOT_RELAUNCHED_AFTER_RECORDED_EXIT_REPORT_MARKER = "NOT RELAUNCHED AFTER A RECORDED EXIT"
SEAT_NOT_RECOVERED_REPORT_MARKERS = (
    "REFUSED",
    "LAUNCH FAILED",
    "LAUNCHED BUT DID NOT COME UP",
    SEAT_ASKED_TO_BE_CONSULTED_REPORT_MARKER,
    SEAT_NOT_RELAUNCHED_AFTER_RECORDED_EXIT_REPORT_MARKER,
)
# The report class for assess_seat's seat-already-running verdict. Named so the
# suites can pin that it contains none of the markers above.
SEAT_ALREADY_RUNNING_REPORT_MARKER = "ALREADY RUNNING"
# The predicted verdicts for which the leftover-shell question is not put (ruled
# 2026-09-18), each with the report class its line carries — the class the
# same verdict carries everywhere else, so what counts outcomes counts these
# the same way. A yes would close a window and then report a problem the
# operator must fix anyway, and a running seat is no time to offer closing a
# window at all.
LEFTOVER_IDLE_SHELL_PREDICTIONS_REPORTED_WITHOUT_ASKING = {
    "refuse": "REFUSED",
    "seat-already-running": SEAT_ALREADY_RUNNING_REPORT_MARKER,
}


def recover_seat(name: str, agents_root: Path, handoff_directory: Path,
                 projects_root: Path, dry_run: bool, ignite_fallback: bool,
                 open_iterm_window: bool = False,
                 retired_pane_process_ids=None,
                 restart_at_the_operators_word: bool = False) -> str:
    """One seat's recovery. Returns a one-line report. With open_iterm_window
    the seat is launched attached in its own iTerm window instead of
    detached (--open-iterm-window-per-seat); nothing else changes — not the
    deadness checks, the transcript choice, or the resume decision.

    retired_pane_process_ids and restart_at_the_operators_word are set only
    by this function's one re-entry, after an operator has answered yes to
    restarting a seat behind a leftover idle shell, and that shell was
    closed. retired_pane_process_ids carries the panes that were closed past
    the occupancy check; being not-None, it is also what stops the question
    being asked a second time in the same recovery.
    restart_at_the_operators_word is that yes: the operator's word to
    restart, which a seat carrying a recorded exit or a handoff asking to be
    consulted needs before it is launched (ruled 2026-09-18).

    A seat carrying a recorded exit (2a in this module's docstring) is also
    asked about with no leftover session at all — after a reboot, say — when
    an operator is at a terminal and this is not a dry run (ruled
    2026-09-18): "<seat> stopped on purpose. Restart it anyway? y/n", or
    "<seat> stopped with exit code <code>. Restart it? y/n" when the recorded
    code is neither zero nor unknown. A yes restarts it exactly as the
    leftover-shell yes does, and its line says the operator said to restart
    it; a no, or nobody to ask, leaves the NOT RELAUNCHED line it has always
    had. Under --all that is one question per such seat, each answered on its
    own (the user accepted that cost)."""
    verdict, detail = assess_seat(name, agents_root, handoff_directory, projects_root,
                                  retired_pane_process_ids=retired_pane_process_ids or ())
    seat_directory = agents_root / name
    launch = open_seat_in_iterm_window if open_iterm_window else launch_seat
    in_window = " in a new iTerm window" if open_iterm_window else ""

    def would_open(extra_supervisor_arguments: str, first_prompt_file: Path = None) -> str:
        """The dry run's view of the window: the command it would run."""
        if not open_iterm_window:
            return ""
        return "; would open an iTerm window running: " + iterm_window_command_text(
            name, seat_directory, handoff_directory, extra_supervisor_arguments,
            first_prompt_file)

    # Before every branch below, because it decides which assessment the rest
    # of this function acts on (user-ruled 2026-09-17). The seat's tmux
    # session is alive with no confirmed supervisor, and assess_seat proved it
    # is nothing but the shell an attached launch leaves open. With an
    # operator at a terminal that is a question, unless a yes can already be
    # seen to end in a refusal or a running seat, which is reported at once
    # (user-ruled 2026-09-18); with no one to ask — at boot, under
    # restart-live-seats-at-login — it is the refusal it has always been.
    if verdict == ASK_TO_CLOSE_THE_LEFTOVER_IDLE_SHELL_VERDICT:
        refusal, pane_process_ids, shell_detail = detail

        def the_prediction():
            """Taken only where the operator is shown something — a dry run's
            line and an operator's terminal — so an unattended run never takes
            it. It decides whether the question is put and in which words; the
            reassessment after the retire below still decides what a yes does."""
            return predicted_assessment_once_the_leftover_idle_shell_is_closed(
                name, agents_root, handoff_directory, projects_root, pane_process_ids)

        def reported_without_asking(predicted_verdict, predicted_detail) -> str:
            """The report for a predicted refuse or seat-already-running (ruled
            2026-09-18): the prediction's own reason, in the class that verdict
            carries everywhere else. Its reason was found with the shell read as
            closed, which the line says, so it is never read as the window's
            fault."""
            return (f"{LEFTOVER_IDLE_SHELL_PREDICTIONS_REPORTED_WITHOUT_ASKING[predicted_verdict]}"
                    f" — {predicted_detail}. This was found assessing the seat as though "
                    "its leftover shell were already closed")

        def what_a_yes_does(predicted_verdict, predicted_detail) -> str:
            """The dry run's account of a yes, after the session is closed: what
            the reassessment below is predicted to do with the operator's word."""
            if predicted_verdict == "offer-after-recorded-exit":
                return restart_after_recorded_exit_described(predicted_detail[2])
            if predicted_verdict == "seat-asked-to-be-consulted":
                return ("relaunch the seat plain, whose supervisor then asks its own restart "
                        "question before it starts a session")
            return "assess the seat without it"

        if dry_run:
            # Reported whether or not anyone is at a terminal: a dry run's
            # job is to say what a real run would do, and a run this one
            # cannot see — an operator's, later — is the one that would ask.
            predicted_verdict, predicted_detail = the_prediction()
            if predicted_verdict in LEFTOVER_IDLE_SHELL_PREDICTIONS_REPORTED_WITHOUT_ASKING:
                return (f"{name}: with an operator at a terminal would ask nothing, leave the "
                        f"window open ({shell_detail}) and report straight away: "
                        f"{reported_without_asking(predicted_verdict, predicted_detail)}. "
                        "With no terminal it refuses")
            question = leftover_idle_shell_question_for_seat(name, predicted_verdict,
                                                             predicted_detail)
            return (f"{name}: would ask an operator at a terminal — \"{question}\" — and on a "
                    f"yes close that session and "
                    f"{what_a_yes_does(predicted_verdict, predicted_detail)} ({shell_detail}); "
                    "with no terminal it refuses")
        if retired_pane_process_ids is not None:
            # A session still holding the name after the retire below. Asking
            # again would loop; this tool cannot clear that state.
            return (f"{name}: REFUSED — the leftover shell was closed, but a tmux session "
                    f"named '{name}' still holds the name: clear it by hand, then rerun "
                    "this recovery")
        if not recovery_has_an_operator_terminal():
            return f"{name}: REFUSED — {refusal}"
        predicted_verdict, predicted_detail = the_prediction()
        # A yes here would only close a window and then report what the
        # prediction already shows, so nothing is asked and nothing is retired
        # (ruled 2026-09-18) — what this tool did for every live window before
        # the question existed.
        if predicted_verdict in LEFTOVER_IDLE_SHELL_PREDICTIONS_REPORTED_WITHOUT_ASKING:
            return (f"{name}: {reported_without_asking(predicted_verdict, predicted_detail)}, "
                    "so nothing was asked and its window was left open")
        question = leftover_idle_shell_question_for_seat(name, predicted_verdict,
                                                         predicted_detail)
        print(f"recover-crashed-seats: {shell_detail}")
        if not ask_operator_yes_or_no(question):
            return f"{name}: REFUSED — {refusal}"
        killed_sockets, retire_failure = resupervise.retire_seat_tmux_session(name)
        if retire_failure is not None:
            return f"{name}: REFUSED — {retire_failure}"
        if killed_sockets:
            closed = ("closed the leftover shell — retired the tmux session on socket"
                      f"{'s' if len(killed_sockets) > 1 else ''} "
                      f"{', '.join(killed_sockets)}")
        else:
            closed = "the leftover shell was already gone when it was retired"
        print(f"recover-crashed-seats: {name}: {closed}")
        # The assessment again, with those panes excused from the occupancy
        # check: the seat is now read as though the session had never been
        # there, and with the operator's word to restart it — which a seat
        # carrying a recorded exit, or a handoff asking to be consulted, needs
        # before it is launched (ruled 2026-09-18). This assessment, not the
        # prediction the question was worded by, decides what happens: if the
        # seat's state moved while the operator thought, the two disagree, and
        # the line this one prints says what actually happened.
        rest = recover_seat(name, agents_root, handoff_directory, projects_root,
                            dry_run, ignite_fallback, open_iterm_window,
                            retired_pane_process_ids=pane_process_ids,
                            restart_at_the_operators_word=True)
        # In the report, so the recovery log records that a session was closed
        # and on whose word.
        return (f"{rest} (the operator said to restart it, so the leftover shell was closed "
                f"first: {closed})")

    # Before any dry-run or launch branch: a dry run reports the same class,
    # and nothing is launched for a seat that is already running.
    if verdict == "seat-already-running":
        return f"{name}: {SEAT_ALREADY_RUNNING_REPORT_MARKER} — {detail}"

    if verdict == "refuse":
        return f"{name}: REFUSED — {detail}"

    # Also before the dry-run branch: nothing is launched without the
    # operator's word, which a dry run never has, since it asks nobody.
    if verdict == "seat-asked-to-be-consulted":
        counter, reason = detail
        if restart_at_the_operators_word:
            # Ruled 2026-09-18: what "restart" means for a seat that asked to
            # be consulted. It means the one launch this seat's own report
            # tells an operator to make by hand: plain, leaving its handoff
            # unconsumed, so that the supervisor's boot-ignition finds the
            # dont-restart and asks its own "restart? y/n" on the seat's
            # terminal before it starts a session. That is a
            # second question after the operator's yes here, and in a detached
            # launch it waits in a tmux session nobody is looking at; its
            # supervisor holds its lock while it waits, so the come-up check
            # below reads the seat as up. No --ignite-fallback is offered: it
            # is the forced restart the seat declined (nedschorus#350).
            launch_exit_code = launch(name, seat_directory, handoff_directory, "")
            if launch_exit_code != 0:
                return (f"{name}: LAUNCH FAILED (exit {launch_exit_code}) — the seat is "
                        "still down")
            did_not_come_up = came_up_or_failure_report(name, handoff_directory, False)
            if did_not_come_up is not None:
                return did_not_come_up
            return (f"{name}: relaunched plain{in_window}, although an unconsumed handoff "
                    f"(counter {counter}) asks to be consulted before a relaunch: {reason}. Its "
                    "supervisor asks its own restart question before it starts a session: "
                    "answer it in the seat's tmux session")
        return (f"{name}: {SEAT_ASKED_TO_BE_CONSULTED_REPORT_MARKER} — an unconsumed handoff "
                f"(counter {counter}) asks to be consulted before a relaunch: {reason}. Nothing "
                f"was launched. To bring it back, launch it by hand (launch-claude-mac {name} "
                f"or launch-claude-ubuntu {name}) and answer its supervisor's restart question")

    # Also before the dry-run branches: nothing is launched without the
    # operator's word, which a dry run never has.
    if verdict == "offer-after-recorded-exit":
        exit_code, recorded_at, session_id = detail
        code_text = "an unknown exit code" if exit_code is None else f"exit code {exit_code}"
        recorded = (f"its supervisor recorded at {recorded_at} that its agent exited with "
                    f"{code_text}")
        question = restart_question_for_a_seat_with_a_recorded_exit(name, exit_code)
        # With no leftover session — after a reboot, say — the operator is
        # asked here (ruled 2026-09-18). A seat that came through the
        # leftover-shell question was asked there, and its line gains that
        # question's suffix, saying the shell was closed; here nothing was
        # closed, so the line says only whose word it was. Nothing is asked in
        # a dry run, which changes nothing, nor with nobody at a terminal to
        # answer — at boot, under restart-live-seats-at-login — and then the
        # line below is unchanged.
        the_operator_said_yes_here = (not restart_at_the_operators_word and not dry_run
                                      and recovery_has_an_operator_terminal()
                                      and ask_operator_yes_or_no(question))
        on_whose_word = " (the operator said to restart it)" if the_operator_said_yes_here else ""
        if restart_at_the_operators_word or the_operator_said_yes_here:
            # Ruled 2026-09-18: the operator said yes to "<seat> stopped on
            # purpose. Restart it anyway?" or "<seat> stopped with exit code
            # <code>. Restart it?", so the seat is restarted — resuming
            # its session if there is one, fresh if there is none. The rule that
            # a seat stopped on purpose is not brought back is about this tool
            # doing it on its own. --ignite-fallback does not change this: its
            # degraded restart tells the agent that its session died without a
            # handoff, which a recorded exit says it did not, and the ruling
            # names these two outcomes only. So no fallback is offered either.
            if session_id is None:
                launch_exit_code = launch(
                    name, seat_directory, handoff_directory, "",
                    first_prompt_file=write_first_prompt_after_recorded_exit(
                        handoff_directory, name, by_hand=False, resuming=False))
                relaunched = f"relaunched fresh{in_window}"
                no_session = ", with no session to resume"
            else:
                launch_exit_code = launch(
                    name, seat_directory, handoff_directory,
                    f"--resume-session-id {shlex.quote(session_id)}",
                    first_prompt_file=write_first_prompt_after_recorded_exit(
                        handoff_directory, name, by_hand=False, resuming=True))
                relaunched = f"relaunched resuming {session_id}{in_window}"
                no_session = ""
            if launch_exit_code != 0:
                return (f"{name}: LAUNCH FAILED (exit {launch_exit_code}) — the seat is "
                        f"still down{on_whose_word}")
            did_not_come_up = came_up_or_failure_report(name, handoff_directory, False)
            if did_not_come_up is not None:
                return f"{did_not_come_up}{on_whose_word}"
            return f"{name}: {relaunched} after {recorded}{no_session}{on_whose_word}"
        fresh = by_hand_launch_command_for_seat(name, seat_directory, handoff_directory, "")
        if session_id is None:
            by_hand = f"to bring it back by hand as a fresh session: {fresh}"
        else:
            # The resume carries its own first prompt, or the supervisor's
            # default for a resume tells the agent it died without a handoff
            # (review 5240813304). Written here, where the command naming it is
            # printed, so the command works when it is typed. A dry run changes
            # nothing, so it names the file without writing it.
            prompt_file = first_prompt_after_recorded_exit_path(handoff_directory, name,
                                                                by_hand=True)
            if not dry_run:
                write_first_prompt_after_recorded_exit(handoff_directory, name,
                                                       by_hand=True, resuming=True)
            resume = by_hand_launch_command_for_seat(
                name, seat_directory, handoff_directory,
                f"--resume-session-id {shlex.quote(session_id)}",
                first_prompt_file=prompt_file)
            by_hand = (f"to bring it back by hand resuming session {session_id}: {resume}; "
                       f"or as a fresh session: {fresh}")
        not_relaunched = (f"{SEAT_NOT_RELAUNCHED_AFTER_RECORDED_EXIT_REPORT_MARKER} — "
                          f"{recorded} and stopped without launching a successor, so this is "
                          f"not treated as a crash and nothing is launched; {by_hand}")
        if dry_run:
            # Reported whether or not anyone is at a terminal, as the
            # leftover-shell question's dry run is: a run this one cannot
            # see, an operator's, is the one that would ask. The unattended
            # line is quoted whole, so its class still counts in main.
            return (f"{name}: would ask an operator at a terminal — \"{question}\" — and on a "
                    f"yes {restart_after_recorded_exit_described(session_id)}; on a no, or "
                    f"with no terminal, it reports: {not_relaunched}")
        return f"{name}: {not_relaunched}"

    if verdict == "defer-to-boot-ignition":
        if dry_run:
            return f"{name}: would relaunch plain ({detail}){would_open('')}"
        exit_code = launch(name, seat_directory, handoff_directory, "")
        if exit_code != 0:
            return f"{name}: LAUNCH FAILED (exit {exit_code}) — the seat is still down"
        # Not offered to an operator who just used it. This path is chosen by
        # the verdict alone — assess_seat never sees the flag — so a run that
        # passed --ignite-fallback lands here too, and was told to try the flag
        # it had already tried (PR #329 review, finding 2).
        did_not_come_up = came_up_or_failure_report(name, handoff_directory,
                                                    not ignite_fallback)
        if did_not_come_up is not None:
            return did_not_come_up
        return f"{name}: relaunched plain{in_window} — {detail}"

    if verdict == "resume" and not ignite_fallback:
        session_id, transcript = detail
        size_kb = transcript.stat().st_size // 1024
        unreplied_successor = is_unreplied_reincarnation_successor(transcript)
        # In the report, so the recovery log records which prompt was sent.
        unreplied_note = ("; it is the successor its handoff started, which "
                          "never replied" if unreplied_successor else "")
        resume_arguments = f"--resume-session-id {shlex.quote(session_id)}"
        if dry_run:
            return (f"{name}: would resume session {session_id} "
                    f"({size_kb}KB transcript) under a supervisor{unreplied_note}"
                    f"{would_open(resume_arguments, resume_prompt_path(handoff_directory, name))}")
        exit_code = launch(name, seat_directory, handoff_directory, resume_arguments,
                           first_prompt_file=write_resume_prompt(
                               handoff_directory, name, unreplied_successor))
        if exit_code != 0:
            return f"{name}: LAUNCH FAILED (exit {exit_code}) — the seat is still down"
        did_not_come_up = came_up_or_failure_report(name, handoff_directory, True)
        if did_not_come_up is not None:
            return did_not_come_up
        return (f"{name}: relaunched resuming {session_id} "
                f"({size_kb}KB transcript){in_window}{unreplied_note}")

    # ignite: fresh session reading the newest dialog extract — the degraded
    # mode (user-directed 2026-08-21), and the only path when nothing real
    # remains to resume.
    extract = newest_dialog_extract(handoff_directory, name)
    if extract is None:
        if dry_run:
            return (f"{name}: would launch fresh — nothing to resume, no extract to "
                    f"read{would_open('')}")
        exit_code = launch(name, seat_directory, handoff_directory, "")
        if exit_code != 0:
            return f"{name}: LAUNCH FAILED (exit {exit_code}) — the seat is still down"
        did_not_come_up = came_up_or_failure_report(name, handoff_directory, False)
        if did_not_come_up is not None:
            return did_not_come_up
        return f"{name}: relaunched fresh{in_window} (nothing to resume, no extract to read)"
    prompt = (
        f"Read {extract} — it is the dialog from this seat's last recorded "
        "session; the session that followed it died without a handoff (crash "
        "recovery, nedschorus#120). Continue from where that dialog ends, "
        "checking the repository's current state before trusting any of the "
        "dialog's in-flight assumptions."
    )
    prompt_path = handoff_directory / f"{name}-recovery-ignition-prompt.md"
    if dry_run:
        return f"{name}: would launch fresh igniting from {extract.name}{would_open('', prompt_path)}"
    prompt_path.write_text(prompt, encoding="utf-8")
    exit_code = launch(name, seat_directory, handoff_directory, "",
                       first_prompt_file=prompt_path)
    if exit_code != 0:
        return f"{name}: LAUNCH FAILED (exit {exit_code}) — the seat is still down"
    did_not_come_up = came_up_or_failure_report(name, handoff_directory, False)
    if did_not_come_up is not None:
        return did_not_come_up
    return f"{name}: relaunched fresh{in_window} igniting from {extract.name}"


def append_to_recovery_log(handoff_directory: Path, report: str):
    """One timestamped line per seat verdict, appended durably.

    The printed reports otherwise live only in the operator's scrollback,
    and a post-crash investigator needs the decision AS MADE AT THE TIME —
    state moves after a recovery (handoffs consumed, seats relaunched), so
    the verdict may not be re-derivable later (user-ruled 2026-08-22: a
    simple durable log). Dry runs do not log: --dry-run promises to change
    nothing, and it is itself the investigator's probe. A log failure never
    blocks a recovery — the seat matters more than the record.
    """
    log_path = handoff_directory / "recover-crashed-seats-log.txt"
    try:
        handoff_directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(f"{stamp} {report}\n")
    except OSError as error:
        print(f"recover-crashed-seats: could not append to {log_path}: {error}",
              file=sys.stderr)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Recover seats whose sessions died without writing a handoff.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("names", nargs="*", help="seat names to recover")
    parser.add_argument("--all", action="store_true",
                        help="every seat with a home under the agents root")
    parser.add_argument("--dry-run", action="store_true",
                        help="report decisions; launch nothing")
    parser.add_argument("--ignite-fallback", action="store_true",
                        help="skip the transcript resume; launch fresh reading the "
                             "newest dialog extract (degraded mode, #120)")
    parser.add_argument("--agents-root", default="",
                        help="seat home root (default ~/agents)")
    parser.add_argument("--handoff-dir", default="",
                        help="handoff directory (default ~/.claude/handoffs)")
    parser.add_argument("--projects-root", default="",
                        help="harness transcript root (default ~/.claude/projects)")
    parser.add_argument("--open-iterm-window-per-seat", action="store_true",
                        help="launch each recovered seat attached, in its own iTerm "
                             "window (macOS only; nedschorus#242 change 6)")
    arguments = parser.parse_args(argv)

    agents_root = (Path(arguments.agents_root).expanduser() if arguments.agents_root
                   else default_agents_root())
    handoff_directory = (Path(arguments.handoff_dir).expanduser() if arguments.handoff_dir
                         else default_handoff_directory())
    projects_root = (Path(arguments.projects_root).expanduser() if arguments.projects_root
                     else Path("~/.claude/projects").expanduser())

    if arguments.open_iterm_window_per_seat:
        # Refused with the reason, never silently downgraded to a detached
        # launch: the Ubuntu box is headless, with no iTerm2 and no
        # launch-claude-mac.
        if launcher_path() is None:
            parser.error("--open-iterm-window-per-seat needs macOS: it opens iTerm2 "
                         "windows running launch-claude-mac, and neither exists here")
        # Every path the window's command carries; see iterm_window_command_text
        # for why a single quote cannot be carried. The handoff directory is
        # the strict one: it travels INSIDE the supervisor arguments, where
        # shlex.quote wraps a space in the very quotes iTerm2 cannot carry, so
        # a handoff directory needing any shell quoting is refused (review of
        # e55904d, finding 1: composing anyway raised from inside the composer,
        # which under --all abandons the seats after it and leaves a written
        # resume prompt with no window). The rest are whole words this composer
        # quotes itself, so a space in them is carried intact.
        if shlex.quote(str(handoff_directory)) != str(handoff_directory):
            parser.error("--open-iterm-window-per-seat cannot carry a handoff directory "
                         "that needs shell quoting — a space or an apostrophe in it — "
                         f"into an iTerm window: {handoff_directory}")
        for path in (agents_root, launcher_path()):
            if "'" in str(path):
                parser.error("--open-iterm-window-per-seat cannot carry a path holding "
                             f"an apostrophe into an iTerm window: {path}")

    if arguments.all:
        # A directory under the agents root is a SEAT only if something ever
        # ran there: a supervisor state file, a handoff, or a transcript
        # directory (PR #131 review, finding 6 — an empty leftover from a
        # mistyped launch is not a seat, and "not running" is not "crashed").
        # A never-run directory can still be recovered by NAME, deliberately.
        def ever_ran(name: str) -> bool:
            return ((handoff_directory / f"{name}-supervisor-state.json").is_file()
                    or (handoff_directory / f"{name}-handoff.md").is_file()
                    or harness_project_directory(agents_root / name,
                                                 projects_root).is_dir())
        names = sorted(
            entry.name for entry in agents_root.iterdir()
            if entry.is_dir() and ever_ran(entry.name)
        ) if agents_root.is_dir() else []
        if not names:
            print(f"recover-crashed-seats: no seat directories under {agents_root}")
            return 1
    elif arguments.names:
        names = arguments.names
    else:
        parser.error("name at least one seat, or pass --all")

    not_recovered = 0
    for name in names:
        report = recover_seat(name, agents_root, handoff_directory, projects_root,
                              arguments.dry_run, arguments.ignite_fallback,
                              open_iterm_window=arguments.open_iterm_window_per_seat)
        print(f"recover-crashed-seats: {report}")
        if not arguments.dry_run:
            append_to_recovery_log(handoff_directory, report)
        if any(marker in report for marker in SEAT_NOT_RECOVERED_REPORT_MARKERS):
            not_recovered += 1
    # Nonzero when ANY seat was not recovered, not only when every one was:
    # three seats up and one down used to exit zero, telling an unattended
    # caller the fleet came back (user-ruled 2026-09-16, merge-lane walk item
    # 6 — the multi-seat half of the shape PR #329 fixed for one seat).
    return 1 if not_recovered else 0


if __name__ == "__main__":
    sys.exit(main())
