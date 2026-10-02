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
     agent's exit (2a) is then restarted on that yes. The proof is taken again
     after the yes, immediately before the retire, and a session still holding
     the name that is no longer only an idle shell is left alone and the seat
     reported NOT RESTARTED (ruled 2026-09-18), since the operator's answer can
     come any time later. A session gone by then holds no work, and the
     recovery goes on as before; when tmux cannot say which, the seat is
     refused for that. Run unattended — at boot, under
     restart-live-seats-at-login — nothing is asked and the refusal stands
     exactly as it did. A session that cannot be proven idle is refused with
     no question, attended or not. A dry run asks nobody; for a seat it would
     ask about, its line quotes the REFUSED line a no or nobody to ask gives,
     so a practice run counts that seat as not recovered (ruled 2026-09-18).
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

Agents root: on the Mac a seat's directory is <root>/<name>, the root being
--agents-root, else $NEDSCHORUS_AGENTS_ROOT, else ~/agents, as
launch-claude-mac resolves it. Off macOS — where launcher_path() is None — it
is always ~/agents/<name>: --agents-root is refused (exit 2, nothing read or
launched) and the variable is ignored. A box seat is always ~/agents/<name>
because launch-claude-ubuntu reads no agents-root variable (user-ruled
2026-09-22, in merge-lane-2's walk
merge-lane-2-questions-concerns-and-suggestions-2026-09-22). A root chosen
here anyway split the recovery: the automatic launch seated <root>/<name>,
while the by-hand command printed when that launch fails runs
launch-claude-ubuntu, which seats ~/agents/<name>, not the seat that was
assessed. Raised by ned-review-merge's inline question 4088153045 on PR
[The ubuntu launcher reads no agents-root variable: a box seat is always ~/agents/<name>](https://github.com/nedschorus/nedschorus/pull/684);
the user answered "Y" at 2026-09-28T16:37:05Z, closing question 1 of
merge-lane-2's walk merge-lane-2-meta-walk-open-items-2026-09-23, to refuse
the flag off macOS as resupervise-seat.py refuses it with --machine ubuntu.
The variable is ignored there too, so the box listing in
restart-live-seats-at-login.py, which reads ~/agents, and this tool agree on
where a box seat lives by rule rather than because nothing sets it.

Checkout: a seat this tool launches runs its supervisor from the durable
checkout — --checkout, default ~/Projects/nedschorus, the name and default the
login restart's install scripts give it — whichever checkout this tool itself
runs from. On the Mac it runs that checkout's launch-claude-mac, which takes
the supervisor from its own checkout; off macOS the tmux command names that
checkout's supervisor, as launch-claude-ubuntu does. Until 2026-09-29 both
came from this tool's own checkout, so a recovery run by hand from a worktree
left the seat's supervisor running that worktree's code for the rest of its
life, and the seat stopped at its next handoff once the worktree was removed,
because at every handoff the supervisor runs the conversation extractor from
its own checkout (GHI [recover-crashed-seats: a recovered seat's supervisor runs from whichever checkout the recovery was run from, and stops at its next handoff once that checkout is removed](https://github.com/nedschorus/nedschorus/issues/659)).
The user answered "y" on 2026-09-29, walk
open-items-this-seat-holds-2026-09-24, item 12, to: "The choices: always run
the supervisor from the machine's reference clone, `~/Projects/nedschorus`, as
the login restart already does; or warn or refuse when recovery runs from any
other checkout. I recommend the reference clone. It is the one checkout that
is never removed, and the login restart already relies on it." So when the
file a launch needs is missing from the durable checkout — launch-claude-mac
on the Mac, the supervisor elsewhere — the seat is refused and nothing is
launched, never launched from this tool's own checkout instead.

Usage:
  recover-crashed-seats.py <seat-name>... [--dry-run] [--ignite-fallback]
                           [--open-iterm-window-per-seat] [--checkout DIR]
  recover-crashed-seats.py --all [--dry-run] [--ignite-fallback]
                           [--open-iterm-window-per-seat] [--checkout DIR]

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

# Share the relative path so imports and box launches cannot diverge.
SUPERVISOR_SCRIPT_WITHIN_A_CHECKOUT = Path("nc-systems") / "handoff" / "handoff-supervisor.py"
SUPERVISOR_SCRIPT = Path(__file__).resolve().parent.parent / SUPERVISOR_SCRIPT_WITHIN_A_CHECKOUT
LAUNCH_CLAUDE_MAC_WITHIN_A_CHECKOUT = Path("scripts") / "launch-claude-mac"
# Use a durable checkout: removing a worktree must not break a recovered supervisor.
durable_checkout = Path("~/Projects/nedschorus").expanduser()

_supervisor_spec = importlib.util.spec_from_file_location(
    "handoff_supervisor", SUPERVISOR_SCRIPT
)
supervisor = importlib.util.module_from_spec(_supervisor_spec)
_supervisor_spec.loader.exec_module(supervisor)

_watcher_spec = importlib.util.spec_from_file_location(
    "watch_agent_dialogs", Path(__file__).with_name("watch-agent-dialogs.py")
)
watcher = importlib.util.module_from_spec(_watcher_spec)
_watcher_spec.loader.exec_module(watcher)

# Reuse retirement rules so every socket holding the seat’s name is cleared consistently.
_resupervise_spec = importlib.util.spec_from_file_location(
    "resupervise_seat", Path(__file__).with_name("resupervise-seat.py")
)
resupervise = importlib.util.module_from_spec(_resupervise_spec)
_resupervise_spec.loader.exec_module(resupervise)

# A shared module avoids circular loading between recovery and the supervisor.
# Re-export the names for callers that reach them through this module.
_worth_resuming_spec = importlib.util.spec_from_file_location(
    "seat_transcript_worth_resuming",
    Path(__file__).with_name("seat-transcript-worth-resuming.py"))
worth_resuming = importlib.util.module_from_spec(_worth_resuming_spec)
_worth_resuming_spec.loader.exec_module(worth_resuming)
FIRST_PROMPT_AFTER_RECORDED_EXIT_MARKER = worth_resuming.FIRST_PROMPT_AFTER_RECORDED_EXIT_MARKER
EMPTY_SUCCESSOR_MARKERS = worth_resuming.EMPTY_SUCCESSOR_MARKERS
SUBSTANTIVE_ASSISTANT_TURNS_MINIMUM = worth_resuming.SUBSTANTIVE_ASSISTANT_TURNS_MINIMUM
EMPTY_SUCCESSOR_MAX_BYTES = worth_resuming.EMPTY_SUCCESSOR_MAX_BYTES
SYNTHETIC_ASSISTANT_MODEL = worth_resuming.SYNTHETIC_ASSISTANT_MODEL
first_user_turn_text = worth_resuming.first_user_turn_text
substantive_turn_count = worth_resuming.substantive_turn_count
newest_real_transcript = worth_resuming.newest_real_transcript
# Do not skip a handoff successor: its parent is already retired.
# Keep the marker short enough to match both timestamp forms stored in transcripts.
REINCARNATION_OPENER_MARKER = "the dialog from the session you are continuing"
# Anchor the opener to avoid matching its text quoted in a hand-written brief.
REINCARNATION_OPENER_PATTERN = re.compile(
    r"Read .+? — (?:it is )?" + re.escape(REINCARNATION_OPENER_MARKER))
# Boot ignition without a dialog also consumes the handoff and retires the parent.
BOOT_RECOVERY_IGNITION_MARKER = "(Recovered at supervisor boot:"


def default_agents_root() -> Path:
    # Match the launcher: only the Mac launcher reads NEDSCHORUS_AGENTS_ROOT.
    if not agents_root_is_movable_on_this_machine():
        return Path("~/agents").expanduser()
    return Path(os.environ.get("NEDSCHORUS_AGENTS_ROOT") or "~/agents").expanduser()


def default_handoff_directory() -> Path:
    return Path("~/.claude/handoffs").expanduser()


def harness_project_directory(seat_directory: Path, projects_root: Path) -> Path:
    # The harness replaces every non-ASCII-alphanumeric character, including underscores.
    return watcher.project_directory_for_seat(seat_directory, projects_root)


def run_tmux(*arguments_after_tmux, socket_name=None):
    """Return the tmux result, or None when tmux cannot answer."""
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
    """Return (alive, detail), with alive None when tmux cannot answer."""
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
    """Return (process_ids, detail), with process_ids None when vacancy is unproven."""
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
    # A partial listing proves presence, but cannot prove that only the excused panes remain.
    if rooted and not require_a_complete_listing:
        return rooted, ""
    if listing.returncode != 0:
        return None, f"the occupancy check (lsof) exited {listing.returncode}; vacancy unproven"
    if reported == 0:
        return None, "the occupancy check (lsof) reported no working directories at all"
    return rooted, ""


def seat_directory_occupied(seat_directory: Path, apart_from_process_ids=()):
    """Return (occupied, detail), treating an unusable listing as occupied."""
    # Retired panes may still be exiting; excluding them requires a complete listing.
    rooted, unusable_detail = processes_rooted_in_seat_directory(
        seat_directory, require_a_complete_listing=bool(apart_from_process_ids))
    if rooted is None:
        return True, unusable_detail
    retired = set(apart_from_process_ids)
    if any(process_id not in retired for process_id in rooted):
        return True, f"a live process is rooted in {seat_directory.resolve()}"
    return False, ""


# A live attached seat can also report a shell as its foreground command.
# The process-occupancy check is required to prove the shell is idle.
LEFTOVER_IDLE_SHELL_PANE_COMMANDS = (
    "bash", "zsh", "sh", "dash", "ksh", "fish", "tcsh", "csh",
)


def tmux_session_is_a_leftover_idle_shell(name: str, seat_directory: Path):
    """Return (proven_idle, pane_process_ids, detail) for every session holding the name."""
    # The launcher execs the leftover shell, preserving the pane PID for the lsof check.
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


LEFTOVER_IDLE_SHELL_REASSESSMENT_VERDICTS_THAT_LAUNCH = (
    "defer-to-boot-ignition", "resume", "ignite",
)
LEFTOVER_IDLE_SHELL_REASSESSMENT_VERDICTS_RESTARTED_ONLY_ON_THE_OPERATORS_WORD = (
    "offer-after-recorded-exit", "seat-asked-to-be-consulted",
)


def restart_question_for_a_seat_with_a_recorded_exit(name: str, exit_code) -> str:
    # A recorded nonzero exit may be an agent failure, not an intentional stop.
    if exit_code is None or exit_code == 0:
        return f"{name} stopped on purpose. Restart it anyway? y/n"
    return f"{name} stopped with exit code {exit_code}. Restart it? y/n"


def restart_after_recorded_exit_described(session_id) -> str:
    if session_id is None:
        return "restart the seat as a fresh session"
    return f"restart the seat resuming session {session_id}"


def leftover_idle_shell_question_for_seat(name: str, predicted_verdict: str,
                                          predicted_detail=None) -> str:
    # Restart can launch fresh; resume specifically continues the previous conversation.
    if predicted_verdict in LEFTOVER_IDLE_SHELL_REASSESSMENT_VERDICTS_THAT_LAUNCH:
        return f"Restart {name}? y/n"
    if (predicted_verdict
            not in LEFTOVER_IDLE_SHELL_REASSESSMENT_VERDICTS_RESTARTED_ONLY_ON_THE_OPERATORS_WORD):
        raise ValueError(f"no leftover-shell question is worded for the verdict "
                         f"{predicted_verdict!r}")
    if predicted_verdict == "offer-after-recorded-exit":
        predicted_exit_code, _, _ = predicted_detail
        return restart_question_for_a_seat_with_a_recorded_exit(name, predicted_exit_code)
    _, reason = predicted_detail
    reason = reason.strip()
    if not reason.endswith((".", "!", "?")):
        reason += "."
    return f"{name}'s handoff says: {reason} Restart it? y/n"


def recovery_has_an_operator_terminal() -> bool:
    # A caller may inherit terminal stdin while capturing stdout, hiding a blocking question.
    try:
        return bool(sys.stdin.isatty() and sys.stdout.isatty())
    except (AttributeError, ValueError):
        return False


def ask_operator_yes_or_no(question: str) -> bool:
    """Return True only for an explicit yes."""
    try:
        answer = input(f"{question} ")
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer.strip().lower() in ("y", "yes")


def is_unreplied_reincarnation_successor(transcript_path: Path) -> bool:
    """Return whether a handoff successor has no substantive turns."""
    first_turn = first_user_turn_text(transcript_path)
    return ((REINCARNATION_OPENER_PATTERN.match(first_turn) is not None
             or BOOT_RECOVERY_IGNITION_MARKER in first_turn)
            and substantive_turn_count(transcript_path) == 0)


def resume_prompt_path(handoff_directory: Path, name: str) -> Path:
    return handoff_directory / f"{name}-resume-recovery-prompt.md"


def write_resume_prompt(handoff_directory: Path, name: str,
                        unreplied_successor: bool = False) -> Path:
    # The supervisor’s default prompt would ask for work despite the restored context.
    # An unreplied successor must act on its ignition prompt instead of continuing nonexistent work.
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
            "previous session ended without writing a handoff, and your transcript "
            "was resumed under a fresh supervisor. "
            "Re-verify any in-flight state before trusting it (files you were "
            "mid-edit in, processes you were watching, messages you were owed), "
            "then continue the work you were doing."
        )
    prompt_path.write_text(prompt, encoding="utf-8")
    return prompt_path


def first_prompt_after_recorded_exit_path(handoff_directory: Path, name: str,
                                          by_hand: bool) -> Path:
    # Separate files keep an operator restart from overwriting the printed by-hand prompt.
    kind = "by-hand-resume" if by_hand else "operator-restart"
    return handoff_directory / f"{name}-{kind}-after-recorded-exit-prompt.md"


def write_first_prompt_after_recorded_exit(handoff_directory: Path, name: str,
                                           by_hand: bool, resuming: bool) -> Path:
    # The supervisor’s default resume prompt describes a crash; a recorded exit proves no such thing.
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
    """Return the newest <name>-dialog-NNNN.md for the ignite fallback."""
    extracts = sorted(handoff_directory.glob(f"{name}-dialog-*.md"))
    return extracts[-1] if extracts else None


def launcher_path():
    """Return the durable checkout’s Mac launcher, or None off macOS."""
    # launch-claude-ubuntu is a Mac-side ssh wrapper, not a box-local launcher.
    if sys.platform == "darwin":
        # iTerm window commands start in / with a bare PATH; the launcher path must be absolute.
        return durable_checkout / LAUNCH_CLAUDE_MAC_WITHIN_A_CHECKOUT
    return None


def durable_checkout_file_a_launch_here_runs() -> Path:
    if launcher_path() is None:
        return durable_checkout / SUPERVISOR_SCRIPT_WITHIN_A_CHECKOUT
    return durable_checkout / LAUNCH_CLAUDE_MAC_WITHIN_A_CHECKOUT


def agents_root_is_movable_on_this_machine() -> bool:
    return launcher_path() is not None


def compose_supervisor_arguments_for_seat_launch(handoff_directory: Path,
                                                 extra_supervisor_arguments: str) -> str:
    # The supervisor must consume the same handoff directory recovery assessed.
    supervisor_arguments = f"--handoff-dir {shlex.quote(str(handoff_directory))}"
    if extra_supervisor_arguments:
        supervisor_arguments += f" {extra_supervisor_arguments}"
    return supervisor_arguments


def by_hand_launch_command_for_seat(name: str, seat_directory: Path, handoff_directory: Path,
                                    extra_supervisor_arguments: str,
                                    first_prompt_file: Path = None) -> str:
    launcher = launcher_path()
    words = [] if launcher is None else [
        f"NEDSCHORUS_AGENTS_ROOT={shlex.quote(str(seat_directory.parent))}"]
    words += [
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
    """Start the seat detached under its supervisor on its own tmux server."""
    # Pin the assessed agents root and handoff directory so launch defaults cannot select another seat.
    launcher = launcher_path()
    environment = dict(os.environ)
    # Each value passes through one shell; shlex.quote preserves apostrophes in paths.
    supervisor_arguments = compose_supervisor_arguments_for_seat_launch(
        handoff_directory, extra_supervisor_arguments)
    if launcher is not None:
        environment["LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS"] = supervisor_arguments
        environment["NEDSCHORUS_AGENTS_ROOT"] = str(seat_directory.parent)
        command = [str(launcher), name, "--no-attach"]
        if first_prompt_file is not None:
            command += ["--first-prompt-file", str(first_prompt_file)]
        return subprocess.run(command, env=environment, check=False).returncode

    # This branch bypasses the launcher: preserve its task-store migration and binding.
    # Export the seat’s own git identity, since tmux otherwise inherits the recovering seat’s identity.
    supervisor_command = (
        'export PATH="$HOME/.local/bin:$PATH"; '
        f'if [ -d "$HOME/.claude/tasks/{name}-tasks" ] && '
        f'[ ! -e "$HOME/.claude/tasks/nedschorus-{name}-tasks" ]; then '
        f'mv "$HOME/.claude/tasks/{name}-tasks" '
        f'"$HOME/.claude/tasks/nedschorus-{name}-tasks"; fi; '
        f"export CLAUDE_CODE_TASK_LIST_ID={shlex.quote(f'nedschorus-{name}-tasks')}; "
        "export CLAUDE_CODE_ENABLE_TODO_TOOLS=1; "
        f"export GIT_AUTHOR_NAME={shlex.quote(name)} "
        f"GIT_AUTHOR_EMAIL={shlex.quote(f'{name}@nedschorus.invalid')} "
        f"GIT_COMMITTER_NAME={shlex.quote(name)} "
        f"GIT_COMMITTER_EMAIL={shlex.quote(f'{name}@nedschorus.invalid')}; "
        f"python3 {shlex.quote(str(durable_checkout / SUPERVISOR_SCRIPT_WITHIN_A_CHECKOUT))} "
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
    """Return the command for an attached recovery in an iTerm window."""
    # iTerm inherits its own environment, so recovery settings travel in the command.
    # iTerm’s command parser cannot carry POSIX single-quote escapes.
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
    """Return the opener’s exit code; success confirms a window request, not a running seat."""
    opener = Path(__file__).resolve().with_name("open-iterm-window-running-command")
    command_text = iterm_window_command_text(name, seat_directory, handoff_directory,
                                             extra_supervisor_arguments, first_prompt_file)
    return subprocess.run([str(opener), command_text], check=False).returncode


SUPERVISOR_CONFIRMED_BY_PS = "confirmed-by-ps"
SUPERVISOR_ASSUMED_WITHOUT_PS = "assumed-without-ps"
SUPERVISOR_NOT_CONFIRMED = "supervisor-not-confirmed"


def seat_supervisor_confirmed_by_ps(name: str, lock_path: Path):
    """Return (confirmation_status, identity), distinguishing unavailable ps from proof."""
    # The shared predicate can assume liveness without ps; recovery must distinguish that from proof.
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
    """Return (verdict, detail) for the seat’s recovery."""
    seat_directory = agents_root / name
    if not seat_directory.is_dir():
        return "refuse", f"no seat directory at {seat_directory}"

    alive, detail = tmux_session_alive_anywhere(name)
    if alive is None:
        return "refuse", detail

    # Locks survive reboots and PIDs are reused; confirm the holder is this seat’s supervisor.
    # Check before tmux: a supervisor may hold its lock before writing state.
    lock_path = supervisor.supervisor_lock_path(handoff_directory, name)
    supervisor_answer, identity = seat_supervisor_confirmed_by_ps(name, lock_path)

    # Attached sessions outlive supervisors as shells; tmux liveness alone cannot prove a seat is running.
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
        return ASK_TO_CLOSE_THE_LEFTOVER_IDLE_SHELL_VERDICT, (
            refusal, pane_process_ids, shell_detail)

    if supervisor_answer == SUPERVISOR_CONFIRMED_BY_PS:
        return "seat-already-running", (
            f"the supervisor lock at {lock_path} is held by a live supervisor — {identity}")
    # Unavailable ps is an assumption of liveness, not proof the seat recovered.
    if supervisor_answer == SUPERVISOR_ASSUMED_WITHOUT_PS:
        return "refuse", (
            f"the supervisor lock at {lock_path} names a live process, but ps could not "
            f"confirm it is a supervisor of this seat — {identity}")

    state_path = supervisor.supervisor_state_path(handoff_directory, name)
    supervisor_alive, liveness_detail = supervisor.supervisor_liveness(state_path)
    if supervisor_alive:
        # A supervisor may claim its lock after the first check; recheck because liveness can also assume ps failed.
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

    handoff_path = supervisor.handoff_file_path(handoff_directory, name)
    if handoff_path.is_file():
        fields = supervisor.parse_handoff_file(handoff_path)
        counter = supervisor.counter_from(fields)
        state = supervisor.read_supervisor_state(state_path)
        consumed = state.get("consumed_counter")
        if counter is None:
            # The supervisor cannot consume a handoff without a valid counter; resuming would discard its request.
            return "refuse", (
                f"a handoff exists at {handoff_path} but its restart-counter is "
                "missing or unreadable, so no supervisor would ever consume it. "
                "Read it: if it is real, fix its restart-counter and relaunch "
                "plain; if it is scrap, delete it and rerun this recovery"
            )
        if consumed is None or counter > consumed:
            dont_restart = fields.get("dont-restart")
            if dont_restart:
                # Leave the handoff unconsumed so a by-hand launch still asks the supervisor’s restart question.
                return "seat-asked-to-be-consulted", (counter, dont_restart)
            return "defer-to-boot-ignition", (
                f"an unconsumed handoff waits (counter {counter}, consumed "
                f"{consumed}) — plain relaunch is correct; the supervisor's "
                "boot-ignition consumes it"
            )

    session_id, found = newest_real_transcript(
        harness_project_directory(seat_directory, projects_root))

    # A waiting handoff takes precedence; otherwise a recorded exit requires an operator restart.
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
    """Return (verdict, detail) as though the idle shell were closed, without changing state."""
    # Only the question uses this prediction; state can change before the post-retirement assessment.
    return assess_seat(
        name, agents_root, handoff_directory, projects_root,
        retired_pane_process_ids=pane_process_ids,
        predicting_as_though_the_leftover_idle_shell_were_closed=True)


# Allow the supervisor to notice a dead session and remove its lock before checking survival.
SEAT_SETTLE_SECONDS = 3 * supervisor.HANDOFF_POLL_SECONDS
# The deadline must cover the launcher’s update step; opening a window does not wait for launch.
SEAT_COMES_UP_DEADLINE_SECONDS = 120.0
SEAT_COMES_UP_POLL_SECONDS = 0.5


def wait_for_the_seat_to_come_up(name: str, handoff_directory: Path,
                                 settle_seconds=SEAT_SETTLE_SECONDS,
                                 deadline_seconds=SEAT_COMES_UP_DEADLINE_SECONDS,
                                 identity_check=None, sleep=time.sleep,
                                 monotonic=time.monotonic):
    """Return (came_up, reason) after a supervisor appears and survives the settle interval."""
    # Settle from first sighting, not launch: the launcher may still be updating.
    # The supervisor claims its lock before starting the session, so survival is only a bounded check.
    if identity_check is None:
        identity_check = supervisor.process_is_supervisor_for_agent
    lock_path = supervisor.supervisor_lock_path(handoff_directory, name)

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
    """Return None if the seat came up, otherwise a failure report."""
    # Automatic fallback could spend a session on the wrong recovery; offer it instead.
    came_up, why = wait_for_the_seat_to_come_up(name, handoff_directory)
    if came_up:
        return None
    offer = ("; the degraded restart is --ignite-fallback, which starts a fresh session "
             "from the newest dialog extract" if offer_ignite_fallback else "")
    return f"{name}: LAUNCHED BUT DID NOT COME UP — {why}{offer}"


# Count every report that leaves a seat down; ALREADY RUNNING needs no recovery.
SEAT_ASKED_TO_BE_CONSULTED_REPORT_MARKER = "NOT RELAUNCHED, AT ITS OWN REQUEST"
SEAT_NOT_RELAUNCHED_AFTER_RECORDED_EXIT_REPORT_MARKER = "NOT RELAUNCHED AFTER A RECORDED EXIT"
SEAT_NOT_RESTARTED_AFTER_THE_OPERATORS_YES_REPORT_MARKER = "NOT RESTARTED"
SEAT_NOT_RECOVERED_REPORT_MARKERS = (
    "REFUSED",
    "LAUNCH FAILED",
    "LAUNCHED BUT DID NOT COME UP",
    SEAT_ASKED_TO_BE_CONSULTED_REPORT_MARKER,
    SEAT_NOT_RELAUNCHED_AFTER_RECORDED_EXIT_REPORT_MARKER,
    SEAT_NOT_RESTARTED_AFTER_THE_OPERATORS_YES_REPORT_MARKER,
)
SEAT_ALREADY_RUNNING_REPORT_MARKER = "ALREADY RUNNING"
# A predicted refusal needs operator action anyway; a running seat must keep its window.
LEFTOVER_IDLE_SHELL_PREDICTIONS_REPORTED_WITHOUT_ASKING = {
    "refuse": "REFUSED",
    "seat-already-running": SEAT_ALREADY_RUNNING_REPORT_MARKER,
}
LEFTOVER_IDLE_SHELL_NOT_PROVEN_AGAIN_REPORT = (
    f"{SEAT_NOT_RESTARTED_AFTER_THE_OPERATORS_YES_REPORT_MARKER} — something may have "
    "started in it while you were answering, so it was left alone")


def recover_seat(name: str, agents_root: Path, handoff_directory: Path,
                 projects_root: Path, dry_run: bool, ignite_fallback: bool,
                 open_iterm_window: bool = False,
                 retired_pane_process_ids=None,
                 restart_at_the_operators_word: bool = False) -> str:
    """Recover one seat and return a one-line report."""
    verdict, detail = assess_seat(name, agents_root, handoff_directory, projects_root,
                                  retired_pane_process_ids=retired_pane_process_ids or ())
    # Check launch prerequisites before closing any shell, so a missing durable checkout leaves the window intact.
    if verdict not in ("seat-already-running", "refuse"):
        needed = durable_checkout_file_a_launch_here_runs()
        if not needed.is_file():
            return f"{name}: REFUSED — {needed} does not exist, so nothing was launched"
    seat_directory = agents_root / name
    launch = open_seat_in_iterm_window if open_iterm_window else launch_seat
    in_window = " in a new iTerm window" if open_iterm_window else ""

    def would_open(extra_supervisor_arguments: str, first_prompt_file: Path = None) -> str:
        """Return the command a dry run would open in a window."""
        if not open_iterm_window:
            return ""
        return "; would open an iTerm window running: " + iterm_window_command_text(
            name, seat_directory, handoff_directory, extra_supervisor_arguments,
            first_prompt_file)

    # Resolve the leftover shell first, because the resulting assessment controls every launch branch.
    if verdict == ASK_TO_CLOSE_THE_LEFTOVER_IDLE_SHELL_VERDICT:
        refusal, pane_process_ids, shell_detail = detail

        def the_prediction():
            """Predict the result only when a question or dry-run report needs it."""
            return predicted_assessment_once_the_leftover_idle_shell_is_closed(
                name, agents_root, handoff_directory, projects_root, pane_process_ids)

        def reported_without_asking(predicted_verdict, predicted_detail) -> str:
            """Report a predicted refusal or running seat without closing the window."""
            return (f"{LEFTOVER_IDLE_SHELL_PREDICTIONS_REPORTED_WITHOUT_ASKING[predicted_verdict]}"
                    f" — {predicted_detail}. This was found assessing the seat as though "
                    "its leftover shell were already closed")

        def what_a_yes_does(predicted_verdict, predicted_detail) -> str:
            """Describe the predicted recovery after closing the shell."""
            if predicted_verdict == "offer-after-recorded-exit":
                return restart_after_recorded_exit_described(predicted_detail[2])
            if predicted_verdict == "seat-asked-to-be-consulted":
                return ("relaunch the seat plain, whose supervisor then asks its own restart "
                        "question before it starts a session")
            return "assess the seat without it"

        if dry_run:
            # A dry run must describe the question a later attended run would ask.
            predicted_verdict, predicted_detail = the_prediction()
            if predicted_verdict in LEFTOVER_IDLE_SHELL_PREDICTIONS_REPORTED_WITHOUT_ASKING:
                return (f"{name}: with an operator at a terminal would ask nothing, leave the "
                        f"window open ({shell_detail}) and report straight away: "
                        f"{reported_without_asking(predicted_verdict, predicted_detail)}. "
                        "With no terminal it refuses")
            question = leftover_idle_shell_question_for_seat(name, predicted_verdict,
                                                             predicted_detail)
            # Include the refusal class so a dry run counts unattended seats that would stay down.
            return (f"{name}: would ask an operator at a terminal — \"{question}\" — and on a "
                    f"yes close that session and "
                    f"{what_a_yes_does(predicted_verdict, predicted_detail)} ({shell_detail}); "
                    f"on a no, or with no terminal, it reports: REFUSED — {refusal}")
        if retired_pane_process_ids is not None:
            # Asking again would loop if retirement left a session holding the name.
            return (f"{name}: REFUSED — the leftover shell was closed, but a tmux session "
                    f"named '{name}' still holds the name: clear it by hand, then rerun "
                    "this recovery")
        if not recovery_has_an_operator_terminal():
            return f"{name}: REFUSED — {refusal}"
        predicted_verdict, predicted_detail = the_prediction()
        if predicted_verdict in LEFTOVER_IDLE_SHELL_PREDICTIONS_REPORTED_WITHOUT_ASKING:
            return (f"{name}: {reported_without_asking(predicted_verdict, predicted_detail)}, "
                    "so nothing was asked and its window was left open")
        question = leftover_idle_shell_question_for_seat(name, predicted_verdict,
                                                         predicted_detail)
        print(f"recover-crashed-seats: {shell_detail}")
        if not ask_operator_yes_or_no(question):
            return f"{name}: REFUSED — {refusal}"
        # Recheck immediately before retirement: work may have started while the operator considered the question.
        # Only the panes proved idle now may be excused from the next occupancy check.
        still_a_leftover_shell, rechecked_pane_process_ids, _ = (
            tmux_session_is_a_leftover_idle_shell(name, seat_directory))
        if still_a_leftover_shell:
            pane_process_ids = rechecked_pane_process_ids
        else:
            # A failed idle proof does not prove the session exists; a vanished session holds no work.
            # Ask tmux explicitly, since retirement treats an unanswered socket as empty.
            session_still_there, liveness_detail = tmux_session_alive_anywhere(name)
            if session_still_there is None:
                return f"{name}: REFUSED — {liveness_detail}"
            if session_still_there:
                return f"{name}: {LEFTOVER_IDLE_SHELL_NOT_PROVEN_AGAIN_REPORT}"
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
        # Reassess after retirement: state may have changed while the operator answered.
        rest = recover_seat(name, agents_root, handoff_directory, projects_root,
                            dry_run, ignite_fallback, open_iterm_window,
                            retired_pane_process_ids=pane_process_ids,
                            restart_at_the_operators_word=True)
        return (f"{rest} (the operator said to restart it, so the leftover shell was closed "
                f"first: {closed})")

    if verdict == "seat-already-running":
        return f"{name}: {SEAT_ALREADY_RUNNING_REPORT_MARKER} — {detail}"

    if verdict == "refuse":
        return f"{name}: REFUSED — {detail}"

    if verdict == "seat-asked-to-be-consulted":
        counter, reason = detail
        if restart_at_the_operators_word:
            # A plain launch preserves dont-restart for the supervisor’s own question, even when detached.
            # Do not offer ignite fallback: it would bypass that request.
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

    if verdict == "offer-after-recorded-exit":
        exit_code, recorded_at, session_id = detail
        code_text = "an unknown exit code" if exit_code is None else f"exit code {exit_code}"
        recorded = (f"its supervisor recorded at {recorded_at} that its agent exited with "
                    f"{code_text}")
        question = restart_question_for_a_seat_with_a_recorded_exit(name, exit_code)
        the_operator_said_yes_here = (not restart_at_the_operators_word and not dry_run
                                      and recovery_has_an_operator_terminal()
                                      and ask_operator_yes_or_no(question))
        on_whose_word = " (the operator said to restart it)" if the_operator_said_yes_here else ""
        if restart_at_the_operators_word or the_operator_said_yes_here:
            # Ignite fallback would describe a crash despite the recorded exit; restart by resume or fresh launch only.
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
            # The printed resume command needs its own prompt to avoid falsely describing the exit as a crash.
            # Dry runs name the prompt without writing it.
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
            # Keep the unattended report class in the dry-run line so outcome counting still works.
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
        # Do not offer ignite fallback after that same fallback has failed.
        did_not_come_up = came_up_or_failure_report(name, handoff_directory,
                                                    not ignite_fallback)
        if did_not_come_up is not None:
            return did_not_come_up
        return f"{name}: relaunched plain{in_window} — {detail}"

    if verdict == "resume" and not ignite_fallback:
        session_id, transcript = detail
        size_kb = transcript.stat().st_size // 1024
        unreplied_successor = is_unreplied_reincarnation_successor(transcript)
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
        "session; the session that followed it ended without writing a handoff "
        "(crash recovery, nedschorus#120). Continue from where that dialog ends, "
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
    # Recovery changes state, so the original verdict may not be reconstructible later.
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
                        help="seat home root, macOS only (default "
                             "$NEDSCHORUS_AGENTS_ROOT, else ~/agents); off macOS a "
                             "seat is always ~/agents/<name>")
    parser.add_argument("--handoff-dir", default="",
                        help="handoff directory (default ~/.claude/handoffs)")
    parser.add_argument("--projects-root", default="",
                        help="harness transcript root (default ~/.claude/projects)")
    parser.add_argument("--open-iterm-window-per-seat", action="store_true",
                        help="launch each recovered seat attached, in its own iTerm "
                             "window (macOS only; nedschorus#242 change 6)")
    parser.add_argument("--checkout", default="",
                        help="the durable checkout whose launcher and supervisor a "
                             "launched seat runs (default ~/Projects/nedschorus)")
    arguments = parser.parse_args(argv)

    if arguments.checkout:
        global durable_checkout
        durable_checkout = Path(os.path.abspath(Path(arguments.checkout).expanduser()))

    if arguments.agents_root and not agents_root_is_movable_on_this_machine():
        print("recover-crashed-seats: off macOS, re-run without --agents-root.",
              file=sys.stderr)
        return 2

    agents_root = (Path(arguments.agents_root).expanduser() if arguments.agents_root
                   else default_agents_root())
    handoff_directory = (Path(arguments.handoff_dir).expanduser() if arguments.handoff_dir
                         else default_handoff_directory())
    projects_root = (Path(arguments.projects_root).expanduser() if arguments.projects_root
                     else Path("~/.claude/projects").expanduser())

    if arguments.open_iterm_window_per_seat:
        # The Ubuntu box is headless and has neither iTerm2 nor launch-claude-mac.
        if launcher_path() is None:
            parser.error("--open-iterm-window-per-seat needs macOS: it opens iTerm2 "
                         "windows running launch-claude-mac, and neither exists here")
        # The handoff path is nested in shell-quoted supervisor arguments, which iTerm cannot carry.
        # Reject unsupported quoting before any seat launches; other paths may contain spaces.
        if shlex.quote(str(handoff_directory)) != str(handoff_directory):
            parser.error("--open-iterm-window-per-seat cannot carry a handoff directory "
                         "that needs shell quoting — a space or an apostrophe in it — "
                         f"into an iTerm window: {handoff_directory}")
        for path in (agents_root, launcher_path()):
            if "'" in str(path):
                parser.error("--open-iterm-window-per-seat cannot carry a path holding "
                             f"an apostrophe into an iTerm window: {path}")

    if arguments.all:
        # A never-run directory is not a crashed seat; explicit names may still recover one.
        def ever_ran(name: str) -> bool:
            return (supervisor.supervisor_state_path(handoff_directory, name).is_file()
                    or supervisor.handoff_file_path(handoff_directory, name).is_file()
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
    return 1 if not_recovered else 0


if __name__ == "__main__":
    sys.exit(main())
