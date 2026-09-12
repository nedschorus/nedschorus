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
     live supervisor heartbeat, no process rooted in the seat directory.
     Refuse otherwise — this tool recovers crashes; it never kills live
     work, and unlike resupervise-seat.py it has no kill step at all.
  2. Defer when an unconsumed handoff IS waiting: relaunching plain is
     correct there — the supervisor's boot-ignition consumes it (that path
     landed with PR #106) — so this script hands over to the launcher
     rather than duplicating that logic.
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
EMPTY_SUCCESSOR_MARKERS = (
    "No handoff exists yet",            # handoff-supervisor's default first prompt
    "crash recovery, nedschorus#120",   # this script's ignition (initial agent instructions)
    "resumed by crash recovery",        # this script's resume prompt
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


def seat_directory_occupied(seat_directory: Path):
    """(occupied, detail): is any live process rooted in the seat directory?

    The same lsof contract as resupervise-seat.py and clean-worktrees.py:
    vacancy is proven, never assumed — an unusable answer counts as
    occupied, because recovering a seat something is still working in is
    the one harm this script must never do.
    """
    if shutil.which("lsof") is None:
        return True, "lsof is not installed, so the seat cannot be proven vacant"
    try:
        listing = subprocess.run(
            ["lsof", "-a", "-d", "cwd", "-F", "n"],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return True, "the occupancy check (lsof) could not be run"
    prefix = str(seat_directory.resolve())
    reported = 0
    for line in listing.stdout.splitlines():
        if line.startswith("n"):
            reported += 1
            cwd = line[1:]
            if cwd == prefix or cwd.startswith(prefix + "/"):
                return True, f"a live process is rooted in {prefix}"
    if listing.returncode != 0:
        return True, f"the occupancy check (lsof) exited {listing.returncode}; vacancy unproven"
    if reported == 0:
        return True, "the occupancy check (lsof) reported no working directories at all"
    return False, ""


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


def assess_seat(name: str, agents_root: Path, handoff_directory: Path,
                projects_root: Path):
    """Decide what recovery this seat needs.

    Returns (verdict, detail): refuse / defer-to-boot-ignition / resume
    (detail is (session_id, transcript_path)) / ignite (detail is the
    reason no resume is possible).
    """
    seat_directory = agents_root / name
    if not seat_directory.is_dir():
        return "refuse", f"no seat directory at {seat_directory}"

    alive, detail = tmux_session_alive_anywhere(name)
    if alive is None:
        return "refuse", detail
    if alive:
        return "refuse", f"{detail} — this tool recovers crashes, it never touches live seats"

    # A supervisor lock held by a live supervisor means one is starting or
    # racing this assessment (PR #131 review, question 3): the launch this
    # script would start exits at once against that lock, and finding-1's fix
    # would then report a failure — refusing earlier is clearer. This is the
    # check that catches a supervisor which has claimed its lock but not yet
    # written a state file, which supervisor_liveness cannot see.
    #
    # Held by a live SUPERVISOR OF THIS SEAT, not merely a live process
    # (nedschorus#242 change 1): this file outlives a reboot and process ids
    # are reused across it, so a bare check refuses the very seat the login
    # restart was asked to bring back.
    lock_path = handoff_directory / f"{name}-supervisor.lock"
    if lock_path.is_file():
        try:
            holder = int(lock_path.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            holder = None  # stale or unreadable lock: the launcher's own reclaim handles it
        if holder is not None:
            held, identity = supervisor.process_is_supervisor_for_agent(holder, name)
            if held:
                return "refuse", (f"the supervisor lock at {lock_path} is held by a live "
                                  f"supervisor — {identity}")

    state_path = handoff_directory / f"{name}-supervisor-state.json"
    supervisor_alive, liveness_detail = supervisor.supervisor_liveness(state_path)
    if supervisor_alive:
        return "refuse", f"a supervisor is watching this seat ({liveness_detail})"

    occupied, occupancy_detail = seat_directory_occupied(seat_directory)
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
            return "defer-to-boot-ignition", (
                f"an unconsumed handoff waits (counter {counter}, consumed "
                f"{consumed}) — plain relaunch is correct; the supervisor's "
                "boot-ignition consumes it"
            )

    session_id, found = newest_real_transcript(
        harness_project_directory(seat_directory, projects_root))
    if session_id is None:
        return "ignite", str(found)
    return "resume", (session_id, found)


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


def recover_seat(name: str, agents_root: Path, handoff_directory: Path,
                 projects_root: Path, dry_run: bool, ignite_fallback: bool,
                 open_iterm_window: bool = False) -> str:
    """One seat's recovery. Returns a one-line report. With open_iterm_window
    the seat is launched attached in its own iTerm window instead of
    detached (--open-iterm-window-per-seat); nothing else changes — not the
    deadness checks, the transcript choice, or the resume decision."""
    verdict, detail = assess_seat(name, agents_root, handoff_directory, projects_root)
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

    if verdict == "refuse":
        return f"{name}: REFUSED — {detail}"

    if verdict == "defer-to-boot-ignition":
        if dry_run:
            return f"{name}: would relaunch plain ({detail}){would_open('')}"
        exit_code = launch(name, seat_directory, handoff_directory, "")
        if exit_code != 0:
            return f"{name}: LAUNCH FAILED (exit {exit_code}) — the seat is still down"
        did_not_come_up = came_up_or_failure_report(name, handoff_directory, True)
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
        if "REFUSED" in report or "LAUNCH FAILED" in report:
            not_recovered += 1
    return 1 if not_recovered == len(names) else 0


if __name__ == "__main__":
    sys.exit(main())
