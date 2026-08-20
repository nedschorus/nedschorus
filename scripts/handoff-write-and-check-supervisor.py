#!/usr/bin/env python3
"""Write the handoff file for a retiring session, and report who is watching.

The handoff system's writer (specification:
docs/cross-project/fast-handoff-design.md). The retiring agent writes one
thing — the prompt telling its successor what to do first — and this script
does everything else a machine can do: it stamps the timestamp, derives the
restart counter, formats and writes the file, then checks whether a
supervisor is actually watching and tells the agent what that means for it.

Usage:
  handoff-write-and-check-supervisor.py --agent <name> --next-step-file <path>
                                        [--dont-restart] [--claim]

`--claim` is for one situation, and it is worth knowing before you meet it:
this seat's FIRST handoff under a name that a handoff file already holds from
a DIFFERENT directory. The refusal exists because two seats sharing a name
means one handoff is about to be lost unread (observed 2026-08-16, counter 10
overwritten by counter 11 seconds later). But a seat legitimately inherits a
name when it moves directories or is re-founded elsewhere, and then the
refusal is the only thing standing between it and its own first handoff.
`--claim` takes the name, overwriting whatever handoff stands, with no
approval check: the refusal text is the guard and the typed flag in the
transcript is the audit trail (R9). Read the refusal before passing it — it
names the directory currently holding the name, which is what tells you
whether you are inheriting or colliding.

The next step arrives as a FILE rather than an argument so that backticks,
quotes, and newlines survive: a shell mangles all three inside an inline
argument.

A multi-line next step is written TWICE, and this is deliberate (R20; format
specified in docs/cross-project/fast-handoff-design.md). `next-step:` is
always the whitespace-collapsed single line, because that is what every
reader already handles — including a supervisor process that started before
this format existed and is still running. When the text spans lines, a
`next-step-verbatim:` block carrying it unaltered is appended LAST, after
every computed field, so a content line that happens to look like
`key: value` cannot shadow a real field: the real fields precede it and the
reader takes the first occurrence of a key.

Writing the marker on the `next-step:` line instead would be the obvious
design and is wrong: an older supervisor would boot its successor with the
marker string as its entire instruction, silently.

The liveness report is part of this script rather than a second command
because the two are one decision: a handoff nobody is watching must not stop
the agent working, and an agent that runs only the first half of a two-step
procedure would stop anyway.

Exit codes: 0 written and a supervisor is watching, 1 written but nothing is
watching, 2 bad invocation or an empty next step.
"""

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_supervisor_spec = importlib.util.spec_from_file_location(
    "handoff_supervisor", Path(__file__).with_name("handoff-supervisor.py")
)
supervisor = importlib.util.module_from_spec(_supervisor_spec)
_supervisor_spec.loader.exec_module(supervisor)


NEXT_STEP_VERBATIM_FIELD = "next-step-verbatim"
NEXT_STEP_BLOCK_OPENING_MARKER = "<<END-OF-NEXT-STEP"
NEXT_STEP_BLOCK_TERMINATOR = "END-OF-NEXT-STEP"


def collapse_to_one_line(text: str) -> str:
    """Collapse every run of whitespace into a single space."""
    return re.sub(r"\s+", " ", text).strip()


def verbatim_block_lines(text: str):
    """The lines of a multi-line next step, or [] when it does not need a block.

    Blank lines between the first and last non-blank lines are kept — they are
    part of what the agent wrote. Blank lines before the first and after the
    last are not written at all.
    """
    if "\n" not in text.strip("\n"):
        # One line of content, however much surrounding whitespace: the
        # collapsed `next-step:` field already carries it exactly.
        return []
    lines = text.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines if len(lines) > 1 else []


def consumed_counter_from_state(state_path: Path):
    """Return the counter the supervisor has already acted on, if any."""
    if not state_path.is_file():
        return None
    try:
        value = json.loads(state_path.read_text(encoding="utf-8")).get("consumed_counter")
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None
    return value if isinstance(value, int) else None


def next_restart_counter(handoff_path: Path, state_path: Path) -> int:
    """Return a counter the supervisor is guaranteed to read as new.

    The previous handoff file is the ordinary source, but it can be missing,
    malformed, or older than what the supervisor has already consumed. Taking
    the higher of the two is what keeps this from writing a counter the
    supervisor will ignore — a silent failure to recycle, with a handoff on
    disk and nothing acting on it.
    """
    from_file = supervisor.counter_from(supervisor.parse_handoff_file(handoff_path)) \
        if handoff_path.is_file() else None
    from_state = consumed_counter_from_state(state_path)
    highest_seen = max(value for value in (from_file, from_state, 0) if value is not None)
    return highest_seen + 1


def default_agent_name() -> str:
    """The working directory's name, which is already unique per seat.

    An agent name selects the handoff file, the supervisor state and the lock,
    so two sessions sharing a name share all three. Nothing enforced
    uniqueness and the name was a free-text argument, so every hand-started
    session on this Mac was called `new-vp` and they overwrote each other's
    handoffs: on 2026-08-16 one session wrote counter 10 and another wrote
    counter 11 seconds later, and the first was gone — never archived, because
    retention keeps the last two GENERATIONS of one file, not one file per
    session.

    A worktree directory name is unique by construction — Claude Code appends
    a random suffix for exactly that reason — so defaulting to it removes the
    collision without anyone having to invent a name. An explicit --agent
    still wins, which is how the launchers name their seats.
    """
    return Path.cwd().name


def claiming_directory(handoff_path: Path) -> str:
    """Which directory last wrote this handoff, or '' if it does not say."""
    if not handoff_path.is_file():
        return ""
    return supervisor.parse_handoff_file(handoff_path).get("written-in", "")


def write_handoff_file(handoff_path: Path, next_step: str, counter: int, dont_restart: bool,
                       verbatim_lines=()) -> None:
    """Write the handoff file in one step, so no reader sees it half-written."""
    lines = [
        f"written-at: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"next-step: {next_step}",
        f"restart-counter: {counter}",
        # Who wrote this, so a collision is detectable rather than silent.
        # written-in is the discriminator, not the session id: successive
        # generations of one seat are different sessions in the SAME
        # directory, while two seats sharing a name are different directories.
        f"written-in: {Path.cwd()}",
        f"written-by-session: {os.environ.get('CLAUDE_CODE_SESSION_ID', 'unknown')}",
    ]
    if dont_restart:
        lines.append("dont-restart: the user asked to be consulted before a relaunch")

    # LAST, always: a block's content lines can look like fields, and only the
    # position guarantees they cannot shadow one.
    if verbatim_lines:
        lines.append(f"{NEXT_STEP_VERBATIM_FIELD}: {NEXT_STEP_BLOCK_OPENING_MARKER}")
        lines.extend(verbatim_lines)
        lines.append(NEXT_STEP_BLOCK_TERMINATOR)

    handoff_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = handoff_path.with_suffix(handoff_path.suffix + ".partial")
    temporary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(temporary_path, handoff_path)


# The adopt-and-recycle path once lived here: with no supervisor watching, this
# script started a detached one that adopted the running session, killed it, and
# relaunched. Removed 2026-08-14 after its second observed failure: a successor
# inherits the supervisor's stdio, and a detached supervisor's console is a log
# file, so every successor it launched died at its first need for input — the
# desktop-app case observed 2026-08-11, the terminal-console case 2026-08-14.
# Only a seat-owning supervisor (a tmux pane via the launchers) can recycle;
# every other seat hands off by the user relaunching and pointing the fresh
# session at the handoff file.


def run_branch_protection_audit() -> str:
    """Slice 5's ruled anchor (2026-08-12): the branch-protection audit rides
    each session recycle. One line, never blocking — an unreadable wall is a
    named finding, and a broken audit must never break a handoff."""
    if os.environ.get("HANDOFF_SKIP_PROTECTION_AUDIT"):
        return "branch-protection audit: skipped (HANDOFF_SKIP_PROTECTION_AUDIT set)"
    gatekeeper_path = Path(__file__).with_name("git-gatekeeper.py")
    if not gatekeeper_path.is_file():
        return "branch-protection audit: audit-failed — no gatekeeper beside this script"
    try:
        completed = subprocess.run(
            [sys.executable, str(gatekeeper_path), "audit"],
            capture_output=True, text=True, check=False, timeout=45,
        )
        payload = json.loads(completed.stdout)
        return f"branch-protection audit: {payload.get('summary', completed.stdout.strip())}"
    except Exception as error:  # noqa: BLE001 - the audit never blocks a handoff
        return f"branch-protection audit: audit-failed — {type(error).__name__}: {error}"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Write the handoff file that retires this session.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--agent", default=None,
        help="agent name; names the handoff file. Defaults to the working "
             "directory's name, which is unique per worktree — pass this only "
             "to name a seat deliberately, as the launchers do.",
    )
    parser.add_argument(
        "--claim", action="store_true",
        help="write even though another directory holds this agent name, taking the name from it",
    )
    parser.add_argument(
        "--next-step-file", required=True,
        help="file holding the prompt for the successor; written collapsed to one line, and "
             "also verbatim when it spans several lines",
    )
    parser.add_argument(
        "--dont-restart", action="store_true",
        help="ask the supervisor to confirm before relaunching, instead of relaunching automatically",
    )
    parser.add_argument("--handoff-dir", default="~/.claude/handoffs", help="machine-local handoff directory")
    arguments = parser.parse_args(argv)

    next_step_path = Path(arguments.next_step_file).expanduser()
    if not next_step_path.is_file():
        print(f"handoff-write-and-check-supervisor: no such file: {next_step_path}", file=sys.stderr)
        return 2

    next_step_text = next_step_path.read_text(encoding="utf-8")
    next_step = collapse_to_one_line(next_step_text)
    if not next_step:
        print(
            "handoff-write-and-check-supervisor: the next-step file is empty — the successor would boot "
            "with no instruction, so nothing was written",
            file=sys.stderr,
        )
        return 2

    # The empty refusal above is applied to the COLLAPSED value, before any
    # block is considered, so a next step that is only whitespace is refused
    # rather than written as an empty block.
    verbatim_lines = verbatim_block_lines(next_step_text)
    offending = [line for line in verbatim_lines if line.strip() == NEXT_STEP_BLOCK_TERMINATOR]
    if offending:
        print(
            "handoff-write-and-check-supervisor: the next step contains a line equal to the block "
            f"terminator ({NEXT_STEP_BLOCK_TERMINATOR}), which would end the block early and change "
            "what the successor reads. Reword that line and rerun. Nothing was written.",
            file=sys.stderr,
        )
        return 2

    agent = arguments.agent or default_agent_name()
    handoff_directory = Path(arguments.handoff_dir).expanduser()
    handoff_path = handoff_directory / f"{agent}-handoff.md"
    state_path = handoff_directory / f"{agent}-supervisor-state.json"

    # Refuse a foreign claim rather than overwrite it. Successive generations
    # of one seat run in the same directory, so a DIFFERENT directory holding
    # this name means two seats share it and one handoff is about to be lost
    # unread -- observed 2026-08-16, counter 10 overwritten by counter 11
    # seconds later, with no archived copy because retention keeps the last
    # two generations of the file rather than one file per session.
    # Compare RESOLVED paths: on macOS /var is a symlink to /private/var, so
    # the same seat can describe itself two ways and would otherwise look
    # foreign to itself and refuse its own handoff.
    held_by = claiming_directory(handoff_path)
    held_by_resolved = str(Path(held_by).resolve()) if held_by else ""
    if held_by and held_by_resolved != str(Path.cwd().resolve()) and not arguments.claim:
        print(
            f"handoff-write-and-check-supervisor: {handoff_path} belongs to a seat in "
            f"{held_by}, and this session is in {Path.cwd()}. Nothing was written, because "
            f"writing would destroy a handoff that seat may not have acted on yet. Either "
            f"run with --agent <a name of your own> (the default is this directory's name, "
            f"{default_agent_name()}), or pass --claim to take the name from it.",
            file=sys.stderr,
        )
        return 2

    counter = next_restart_counter(handoff_path, state_path)
    write_handoff_file(handoff_path, next_step, counter, arguments.dont_restart,
                       verbatim_lines=verbatim_lines)
    print(f"handoff-write-and-check-supervisor: wrote {handoff_path} (restart-counter {counter})")
    print(f"handoff-write-and-check-supervisor: {run_branch_protection_audit()}")

    alive, explanation = supervisor.supervisor_liveness(state_path)
    if alive:
        print(
            f"handoff-write-and-check-supervisor: {explanation}. Stop working now and wait — "
            "it takes over within seconds."
        )
        return 0

    print(
        f"handoff-write-and-check-supervisor: {explanation} — and this seat has no supervisor to "
        "recycle it. The handoff is written; nothing will act on it by itself. Tell the user: to "
        f"continue in a fresh session, relaunch claude here and point it at {handoff_path} "
        "(“read the handoff file and continue”). Until then, keep working."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
