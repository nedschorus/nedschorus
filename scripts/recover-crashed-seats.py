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
     directory: newest *.jsonl by mtime, skipping empty-successor sessions
     (a first user turn carrying "No handoff exists yet") — the shape the
     2026-08-21 relaunches minted, which must never shadow the real
     transcript they were born beside.
  4. Relaunch the seat through its launcher with the supervisor resuming
     that session id (handoff-supervisor.py --resume-session-id, riding the
     launcher's LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS hook): the
     successor wakes holding the crashed session's full context,
     supervised, on the seat's own per-seat tmux server.

Degraded mode (boss-directed 2026-08-21, recorded on #120): --ignite-fallback
skips the resume and launches fresh with a first prompt pointing at the
newest dialog extract in the handoff directory — the same read-and-continue
shape build_ignition_prompt composes at every recycle. Use it when a resume
fails or a transcript is too large to be worth replaying; the threshold
judgment stays with the operator in v1. It is also the automatic path when
no real transcript exists to resume.

Machine scope: this runs ON the machine whose seats it recovers — the
launcher it drives is the local one (launch-claude-mac on the Mac; on the
box the same recovery drives the supervisor's launcher conventions there).
Recovering box seats from the Mac is `ssh ned` plus this script there.

Usage:
  recover-crashed-seats.py <seat-name>... [--dry-run] [--ignite-fallback]
  recover-crashed-seats.py --all [--dry-run] [--ignite-fallback]

--all assesses every seat with a home under the agents root. --dry-run
reports every decision and launches nothing.
"""

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

_supervisor_spec = importlib.util.spec_from_file_location(
    "handoff_supervisor", Path(__file__).with_name("handoff-supervisor.py")
)
supervisor = importlib.util.module_from_spec(_supervisor_spec)
_supervisor_spec.loader.exec_module(supervisor)

EMPTY_SUCCESSOR_MARKER = "No handoff exists yet"
# A transcript whose first user turn carries the marker is skipped only when
# it is also SMALL: a seat's first-ever session legitimately starts with the
# no-handoff prompt and can then do real work (observed live 2026-08-22 —
# fixer1's 1.8MB genuine session began exactly so, and a marker-only filter
# wrongly wrote it off). The crash-day empty successors were a few KB.
EMPTY_SUCCESSOR_MAX_BYTES = 100_000


def default_agents_root() -> Path:
    return Path("~/agents").expanduser()


def default_handoff_directory() -> Path:
    return Path("~/.claude/handoffs").expanduser()


def harness_project_directory(seat_directory: Path, projects_root: Path) -> Path:
    """The harness's transcript directory for sessions run in this seat.

    The harness keys transcripts by the session's working directory with
    path separators and dots flattened to dashes, under ~/.claude/projects/.
    Derived, not configured — the same convention the 2026-08-21 hand
    recovery read by eye.
    """
    flattened = str(seat_directory.resolve()).replace("/", "-").replace(".", "-")
    return projects_root / flattened


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

    Per-seat servers (2026-08-21) put a seat's session on socket -L <name>;
    seats launched before that change live on the default socket. Both are
    checked, and either holding the name means the seat is NOT dead.
    """
    for socket_name in dict.fromkeys((name, "default")):
        completed = run_tmux("has-session", "-t", f"={name}", socket_name=socket_name)
        if completed is not None and completed.returncode == 0:
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
        if (transcript.stat().st_size <= EMPTY_SUCCESSOR_MAX_BYTES
                and EMPTY_SUCCESSOR_MARKER in first_user_turn_text(transcript)):
            continue  # a crash-day empty successor, not the seat's real work
        return transcript.stem, transcript
    return None, ("every transcript is an empty-successor session; nothing "
                  "worth resuming")


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
        return Path(__file__).with_name("launch-claude-mac")
    return None


def launch_seat(name: str, seat_directory: Path, extra_supervisor_arguments: str,
                first_prompt_file: Path = None):
    """Start the seat detached under its supervisor, on its own tmux server.

    On the Mac this rides launch-claude-mac (which owns the update step,
    checkout prep, and transition socket selection). On the box — where the
    only launcher is the Mac-side ssh wrapper — the supervisor is started
    directly in a per-seat tmux session, mirroring what launch-claude-ubuntu
    composes remotely; the update/prep steps are skipped, which recovery can
    afford (the seat ran this checkout minutes before the crash).
    """
    launcher = launcher_path()
    environment = dict(os.environ)
    if extra_supervisor_arguments:
        environment["LAUNCH_CLAUDE_SUPERVISOR_EXTRA_ARGUMENTS"] = extra_supervisor_arguments
    if launcher is not None:
        command = [str(launcher), name, "--no-attach"]
        if first_prompt_file is not None:
            command += ["--first-prompt-file", str(first_prompt_file)]
        return subprocess.run(command, env=environment, check=False).returncode

    supervisor_command = (
        'export PATH="$HOME/.local/bin:$PATH"; '
        f"python3 {Path(__file__).with_name('handoff-supervisor.py')} "
        f"--agent '{name}' --cd '{seat_directory}'"
    )
    if extra_supervisor_arguments:
        supervisor_command += f" {extra_supervisor_arguments}"
    if first_prompt_file is not None:
        supervisor_command += f" --first-prompt-file '{first_prompt_file}'"
    completed = run_tmux(
        "new-session", "-d", "-s", name, "-c", str(seat_directory),
        supervisor_command, socket_name=name,
    )
    return 1 if completed is None else completed.returncode


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
    if alive:
        return "refuse", f"{detail} — this tool recovers crashes, it never touches live seats"

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
        if counter is not None and (consumed is None or counter > consumed):
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


def recover_seat(name: str, agents_root: Path, handoff_directory: Path,
                 projects_root: Path, dry_run: bool, ignite_fallback: bool) -> str:
    """One seat's recovery. Returns a one-line report."""
    verdict, detail = assess_seat(name, agents_root, handoff_directory, projects_root)
    seat_directory = agents_root / name

    if verdict == "refuse":
        return f"{name}: REFUSED — {detail}"

    if verdict == "defer-to-boot-ignition":
        if dry_run:
            return f"{name}: would relaunch plain ({detail})"
        launch_seat(name, seat_directory, "")
        return f"{name}: relaunched plain — {detail}"

    if verdict == "resume" and not ignite_fallback:
        session_id, transcript = detail
        size_kb = transcript.stat().st_size // 1024
        if dry_run:
            return (f"{name}: would resume session {session_id} "
                    f"({size_kb}KB transcript) under a supervisor")
        launch_seat(name, seat_directory,
                    f"--resume-session-id '{session_id}'")
        return (f"{name}: relaunched resuming {session_id} "
                f"({size_kb}KB transcript)")

    # ignite: fresh session reading the newest dialog extract — the degraded
    # mode (boss-directed 2026-08-21), and the only path when nothing real
    # remains to resume.
    extract = newest_dialog_extract(handoff_directory, name)
    if extract is None:
        if dry_run:
            return f"{name}: would launch fresh — nothing to resume, no extract to read"
        launch_seat(name, seat_directory, "")
        return f"{name}: relaunched fresh (nothing to resume, no extract to read)"
    prompt = (
        f"Read {extract} — it is the dialog from this seat's last recorded "
        "session; the session that followed it died without a handoff (crash "
        "recovery, nedschorus#120). Continue from where that dialog ends, "
        "checking the repository's current state before trusting any of the "
        "dialog's in-flight assumptions."
    )
    if dry_run:
        return f"{name}: would launch fresh igniting from {extract.name}"
    prompt_path = handoff_directory / f"{name}-recovery-ignition-prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    launch_seat(name, seat_directory, "", first_prompt_file=prompt_path)
    return f"{name}: relaunched fresh igniting from {extract.name}"


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
    arguments = parser.parse_args(argv)

    agents_root = (Path(arguments.agents_root).expanduser() if arguments.agents_root
                   else default_agents_root())
    handoff_directory = (Path(arguments.handoff_dir).expanduser() if arguments.handoff_dir
                         else default_handoff_directory())
    projects_root = (Path(arguments.projects_root).expanduser() if arguments.projects_root
                     else Path("~/.claude/projects").expanduser())

    if arguments.all:
        names = sorted(
            entry.name for entry in agents_root.iterdir() if entry.is_dir()
        ) if agents_root.is_dir() else []
        if not names:
            print(f"recover-crashed-seats: no seat directories under {agents_root}")
            return 1
    elif arguments.names:
        names = arguments.names
    else:
        parser.error("name at least one seat, or pass --all")

    refused = 0
    for name in names:
        report = recover_seat(name, agents_root, handoff_directory, projects_root,
                              arguments.dry_run, arguments.ignite_fallback)
        print(f"recover-crashed-seats: {report}")
        if "REFUSED" in report:
            refused += 1
    return 1 if refused == len(names) else 0


if __name__ == "__main__":
    sys.exit(main())
