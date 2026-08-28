#!/usr/bin/env python3
"""Run one agent session and recycle it when it writes a handoff.

The handoff system's supervisor (specification:
docs/cross-project/fast-handoff-design.md). One supervisor per agent, run in
that agent's console. It owns the whole recycle cycle because an agent
cannot exit itself: /clear and /exit are unavailable to it, and self-SIGTERM
trips the safety classifier.

The cycle, per recycle:
  1. Watch the handoff file for a restart-counter above the last consumed.
  2. Kill the running session.
  3. Extract its dialog to disk before anything else proceeds.
  4. Carry the tasks forward: nothing to do under a seat-pinned task list,
     where every generation shares one store; otherwise copy the retiring
     session's records into the successor's task directory.
  5. Print one queue-status line.
  6. Launch the successor with the ignition prompt.
  7. Keep the current and previous handoff and extract; delete older ones.

The handoff file the agent writes (simple `key: value` lines):
  written-at:           UTC timestamp, ISO 8601
  next-step:            the first action the successor takes
  restart-counter:      predecessor's counter plus one
  dont-restart:         optional; any value makes the supervisor ask before relaunching
  spawned-subagent-<n>: optional, one per subagent the retiring session
                        spawned; they die with it, so the successor is told
                        they existed and can restart the ones still owing work

How much dialog to carry is not among them: the extractor takes the tail that
clears its word floor, so the retiring agent exercises no judgment over what
its successor receives.

Never pass --allowedTools on the launch: it silently swallows the positional
prompt, so the successor would boot with no instructions at all.

Exit codes: 0 clean stop, 2 bad invocation, 3 the agent command is missing.
"""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

TASKS_ROOT = Path.home() / ".claude" / "tasks"
EXTRACTOR_PATH = Path(__file__).with_name("handoff-extract-conversation.py")
HANDOFF_POLL_SECONDS = 2.0
GENERATIONS_KEPT = 2

# The supervisor stamps its state file while polling so anyone can ask whether
# a supervisor is still watching. Without this an agent can write a handoff,
# stop working, and wait forever on a supervisor that died — a hang that looks
# like obedience. Stamped on an interval rather than every poll to keep the
# write rate low; treated as dead at several times that interval, so a slow
# machine does not read as a corpse.
HEARTBEAT_INTERVAL_SECONDS = 10.0
HEARTBEAT_STALE_SECONDS = 60.0


NEXT_STEP_VERBATIM_FIELD = "next-step-verbatim"
NEXT_STEP_BLOCK_OPENING_MARKER = "<<END-OF-NEXT-STEP"
NEXT_STEP_BLOCK_TERMINATOR = "END-OF-NEXT-STEP"
NEXT_STEP_BLOCK_UNTERMINATED_FIELD = "next-step-verbatim-unterminated"
SPAWNED_SUBAGENT_FIELD_PREFIX = "spawned-subagent-"


def parse_handoff_file(handoff_path: Path) -> dict:
    """Read the agent-written handoff into a dict of its `key: value` lines.

    One field may span lines: `next-step-verbatim`, whose value is the opening
    marker followed by the successor's instruction verbatim, ended by a line
    that is exactly the terminator (R20; format in
    docs/cross-project/fast-handoff-design.md). The writer appends that block
    last, after every computed field, so the lines inside it cannot shadow a
    real field — first occurrence still wins, and the real fields came first.

    An unterminated block is a damaged handoff. It is NOT returned as a value:
    the field is left absent so every caller's "prefer verbatim when present"
    is literally true, and a separate flag records that the block was seen
    unterminated, so the successor can be told rather than silently handed the
    collapsed form.
    """
    fields = {}
    lines = handoff_path.read_text(encoding="utf-8").splitlines()
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        index += 1
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        key = key.strip().lower()
        value = value.strip()

        if key == NEXT_STEP_VERBATIM_FIELD and value == NEXT_STEP_BLOCK_OPENING_MARKER:
            block, terminated = [], False
            while index < len(lines):
                candidate = lines[index]
                index += 1
                # EXACT line, not a stripped match. An indented lookalike —
                # a terminator inside a fenced code block, say — is content,
                # and the writer refuses on the same exact comparison, so the
                # two ends cannot disagree about where a block ends.
                if candidate == NEXT_STEP_BLOCK_TERMINATOR:
                    terminated = True
                    break
                block.append(candidate)
            if terminated:
                if key not in fields:
                    fields[key] = "\n".join(block)
            else:
                fields[NEXT_STEP_BLOCK_UNTERMINATED_FIELD] = "yes"
            continue

        if key not in fields:  # first occurrence wins; later prose cannot overwrite a field
            fields[key] = value
    return fields


def read_supervisor_state(state_path: Path) -> dict:
    if not state_path.is_file():
        return {"consumed_counter": None, "session_id": None, "generation": 0}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        print("handoff-supervisor: unreadable state file; starting fresh", file=sys.stderr)
        return {"consumed_counter": None, "session_id": None, "generation": 0}


def write_supervisor_state(state_path: Path, state: dict) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def stamp_heartbeat(state_path: Path, state: dict) -> None:
    """Record that a supervisor is alive and watching, right now."""
    state["last_poll_at"] = datetime.now(timezone.utc).isoformat()
    write_supervisor_state(state_path, state)


def supervisor_liveness(state_path: Path):
    """Return (is_alive, explanation) for the supervisor owning this state file."""
    if not state_path.is_file():
        return False, f"no supervisor state at {state_path} — none has ever run for this agent"

    state = read_supervisor_state(state_path)
    stamped = state.get("last_poll_at")
    if not stamped:
        return False, "supervisor state carries no heartbeat — it is from an older build or never polled"

    try:
        last_poll = datetime.fromisoformat(stamped)
    except ValueError:
        return False, f"unreadable heartbeat: {stamped!r}"

    age_seconds = (datetime.now(timezone.utc) - last_poll).total_seconds()
    if age_seconds > HEARTBEAT_STALE_SECONDS:
        return False, f"last heartbeat was {age_seconds:.0f}s ago — no supervisor is watching"
    return True, f"supervisor alive, last heartbeat {age_seconds:.0f}s ago"


def counter_from(fields: dict):
    raw = fields.get("restart-counter")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def elapsed_phrase(written_at: str) -> str:
    """Describe how stale a handoff is, for the ignition prompt."""
    try:
        written = datetime.fromisoformat(written_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return "written at an unrecorded time — treat every pointer in it as possibly stale"

    minutes = (datetime.now(timezone.utc) - written).total_seconds() / 60
    if minutes < 90:
        amount = f"{int(minutes)} minutes"
    elif minutes < 60 * 48:
        amount = f"{int(minutes / 60)} hours"
    else:
        amount = f"{int(minutes / 60 / 24)} days"
    return f"written {amount} ago — the longer the gap, the more will have changed since"


def pinned_task_list_id() -> str:
    """The seat-keyed task list id the launchers pin, or "" when unpinned.

    scripts/launch-claude-mac and scripts/launch-claude-ubuntu export
    CLAUDE_CODE_TASK_LIST_ID="<seat name>-tasks" into the seat's environment.
    This supervisor is started inside that environment and passes it on by
    inheritance to every session it launches, so when the variable is set,
    ALL of a seat's generations read and write one store,
    ~/.claude/tasks/<seat name>-tasks/, and the session id names no store at
    all. Read from the environment rather than recomposed from --agent: the
    launcher is the one place the id is composed, and a second composition
    here would be a second thing to keep in step.
    """
    return os.environ.get("CLAUDE_CODE_TASK_LIST_ID", "").strip()


def task_count_for(session_id: str) -> int:
    """How many task records the session with this id will actually see.

    Under a pinned list the session id names nothing and the count comes
    from the pinned store — which is the whole point of the ignition
    count-check: it must state what the successor will find, not what some
    directory named after its id holds.
    """
    directory = TASKS_ROOT / (pinned_task_list_id() or session_id)
    return len(list(directory.glob("*.json"))) if directory.is_dir() else 0


def preseed_tasks(retiring_session_id: str, successor_session_id: str) -> int:
    """Copy task records into the successor's directory before it boots.

    Rides undocumented harness state: tasks are <N>.json files under
    ~/.claude/tasks/<session-id>/, and a session started with an explicit id
    reads whatever is already there. An upgrade breaking this is detected at
    the successor's ignition count-check, with the queues as the backstop
    (per-upgrade canary re-runs were dropped as a remembered duty,
    user-ruled 2026-08-12); the canaries in handoff-supervisor-test.py
    (--canary) diagnose it when that fires.

    None of that applies under a pinned list, which is why this returns 0
    without copying there: the retiring and successor sessions already share
    one store, so there is no source and no destination to speak of, and the
    detection story above describes the un-pinned path only.
    """
    if pinned_task_list_id():
        return 0
    source = TASKS_ROOT / retiring_session_id
    if not source.is_dir():
        return 0
    destination = TASKS_ROOT / successor_session_id
    destination.mkdir(parents=True, exist_ok=True)
    copied = 0
    for task_file in sorted(source.glob("*.json")):
        shutil.copy2(task_file, destination / task_file.name)
        copied += 1
    return copied


def queue_status_line(working_directory: Path) -> str:
    """Report each queue's depth and oldest item, so rot stays visible."""
    reports = []
    for queue_directory in ("nc-queue", "docs/issues/queue", "docs/wiki/queue", "legacy-feature-queue"):
        directory = working_directory / queue_directory
        if not directory.is_dir():
            continue
        entries = sorted(
            item for item in directory.glob("*.md") if item.name.lower() != "readme.md"
        )
        if not entries:
            reports.append(f"{queue_directory}: empty")
            continue
        oldest = min(entries, key=lambda item: item.name)
        reports.append(f"{queue_directory}: {len(entries)}, oldest {oldest.name}")
    return "queues — " + ("; ".join(reports) if reports else "none found")


def extract_dialog(session_id: str, working_directory: Path, output_path: Path) -> bool:
    """Write the retiring session's dialog to disk. Returns True on success.

    No boundary is passed: the extractor carries the tail that clears its word
    floor, so nothing here depends on a judgment the retiring agent made.
    """
    result = subprocess.run(
        [
            sys.executable, str(EXTRACTOR_PATH),
            "--session-id", session_id,
            "--cd", str(working_directory),
            "--output", str(output_path),
        ],
        check=False,
    )
    return result.returncode == 0


def next_step_from(handoff_fields: dict) -> str:
    """The successor's instruction: the verbatim block when it is present and
    terminated, otherwise the collapsed single line.

    The collapsed line is always written, so the fallback is a correct
    instruction rather than a partial one.

    The block is returned EXACTLY as parsed. Stripping it here would be the
    quiet kind of wrong: a trailing double space is a markdown hard break, so
    a bare .rstrip() deletes formatting the agent chose, in the one function
    whose whole purpose is carrying the text unaltered. Emptiness is tested
    on a stripped copy; the value returned is never the stripped one.
    """
    verbatim = handoff_fields.get(NEXT_STEP_VERBATIM_FIELD, "")
    if verbatim.strip():
        return verbatim
    return handoff_fields.get("next-step", "").strip()


def spawned_subagent_roster_from(handoff_fields: dict) -> list:
    """The retiring session's subagent roster, in the order the writer wrote it.

    One numbered field per subagent (`spawned-subagent-1`, `-2`, ...), because
    a repeated key would lose every subagent but the first: the parser takes
    the first occurrence of a key. Fields the writer never wrote simply are
    not there — an older handoff yields an empty roster and the ignition
    prompt says nothing about subagents.
    """
    numbered = []
    for key, value in handoff_fields.items():
        if not key.startswith(SPAWNED_SUBAGENT_FIELD_PREFIX):
            continue
        ordinal = key[len(SPAWNED_SUBAGENT_FIELD_PREFIX):]
        if ordinal.isdigit() and value:
            numbered.append((int(ordinal), value))
    return [value for _, value in sorted(numbered)]


def build_ignition_prompt(extract_path: Path, handoff_fields: dict, task_count: int,
                          queue_status: str = "") -> str:
    next_step = next_step_from(handoff_fields)
    elapsed = elapsed_phrase(handoff_fields.get("written-at", ""))
    lines = [
        f"Read {extract_path} — it is the dialog from the session you are continuing, {elapsed}.",
        f"Confirm {task_count} task(s) are visible to you; if the count differs, say so before starting work.",
    ]
    if queue_status:
        # The rot-visibility duty (#32): the successor is the one reader every
        # supervisor mode has — a detached supervisor's console is a log file.
        lines.append(f"Queue status at this recycle: {queue_status} — surface anything rotting to the user.")
    roster = spawned_subagent_roster_from(handoff_fields)
    if roster:
        # The orphaned-subagent duty (ruled 2026-08-23): subagents die with the
        # session that spawned them, and the successor is the only reader who
        # can restart them. Their last recorded event is stated, not
        # interpreted — a subagent that stopped can still own unfinished work,
        # which is exactly how pull request #150's fixer was nearly lost.
        lines.append(
            f"The session you are replacing spawned {len(roster)} subagent(s), which died with it: "
            + "; ".join(roster)
            + ". A last event of `completed` means that subagent stopped, not that its work is "
            "finished — judge which of them still own unfinished work and restart those."
        )
    preamble = " ".join(lines)
    if handoff_fields.get(NEXT_STEP_BLOCK_UNTERMINATED_FIELD):
        preamble += (" NOTE: this handoff's verbatim next-step block was unterminated, so what "
                     "follows is the collapsed one-line form and may have lost structure.")
    if not next_step:
        return preamble + " Then continue from where that dialog ends."
    # The next step keeps its own line breaks: it is handed to the successor as
    # one argv element, so newlines survive delivery. Joining it into the
    # preamble would flatten exactly what the block form exists to preserve.
    return f"{preamble}\n\nThen take the next step:\n{next_step}"


def prune_old_generations(directory: Path, stem: str) -> None:
    """Keep the newest GENERATIONS_KEPT files of one family; delete older."""
    generations = sorted(directory.glob(f"{stem}-*.md"), key=lambda item: item.name)
    for stale in generations[:-GENERATIONS_KEPT]:
        stale.unlink()


def run_git_here(arguments: list, working_directory: Path, timeout: int = 60):
    """Run git in the agent's directory; never raise, whatever goes wrong."""
    try:
        return subprocess.run(
            ["git", *arguments], cwd=str(working_directory),
            capture_output=True, text=True, check=False, timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return subprocess.CompletedProcess(arguments, 1, "", f"{type(error).__name__}: {error}")


def sync_working_branch_with_main(working_directory: Path) -> str:
    """Bring the agent's branch to main before a session starts, and return
    one line of report describing what was or was not done.

    Ruled 2026-08-13. An agent's home sits on its own branch only because git
    refuses one branch in two worktrees — nobody chose a long-lived personal
    branch, and left alone it drifts from main until someone merges by hand.
    Syncing here, between sessions, is the one safe moment: the previous
    session has exited and the next has not started, so no agent is holding a
    mental model of the tree.

    Deliberately conservative — it only ever fast-forwards:

    * uncommitted work, a failed fetch, no origin/main, or a branch carrying
      commits main does not have: report and change nothing;
    * strictly behind main with a clean tree: fast-forward.

    Never a merge, because a conflicted merge left in the tree before the agent
    wakes is worse than being behind: the branch counts go in the report and
    the agent, which can judge, decides.

    Never call this while a session is running in that directory. Doing so
    would rewrite the files under a working agent, which believes it knows
    what its tree contains. There are exactly two ways supervise_sessions
    reaches a directory, and only the first is safe:

    * LAUNCH — the supervisor is about to start a session. Nothing is running
      there, so the sync happens here.
    * ADOPTION — a session is already running there, started by hand or by a
      previous supervisor. It is never synced; it stays as it is until it
      exits and the next launch syncs it.

    The cost of that rule is that a long-lived session drifts arbitrarily far
    from main with nothing announcing it, since sync is the only mechanism and
    it fires once, before the session begins. The design's answer is that
    sessions recycle often; a session that does not recycle should re-check
    main itself rather than trust what it read at start.
    """
    toplevel = run_git_here(["rev-parse", "--show-toplevel"], working_directory, timeout=15)
    if toplevel.returncode != 0:
        return "branch sync: not a git checkout, nothing to sync"

    fetched = run_git_here(["fetch", "--quiet", "origin"], working_directory)
    fetch_note = "" if fetched.returncode == 0 else " (fetch failed, comparing against what is on disk)"

    if run_git_here(["rev-parse", "--verify", "--quiet", "origin/main"],
                    working_directory, timeout=15).returncode != 0:
        return f"branch sync: no origin/main to sync with{fetch_note}"

    branch = run_git_here(["rev-parse", "--abbrev-ref", "HEAD"],
                          working_directory, timeout=15).stdout.strip() or "HEAD"

    dirty = run_git_here(["status", "--porcelain"], working_directory, timeout=30).stdout.strip()
    if dirty:
        return (f"branch sync: {branch} left as is — {len(dirty.splitlines())} uncommitted "
                f"path(s) in the tree{fetch_note}")

    if run_git_here(["merge-base", "--is-ancestor", "origin/main", "HEAD"],
                    working_directory, timeout=15).returncode == 0:
        ahead = run_git_here(["rev-list", "--count", "origin/main..HEAD"],
                             working_directory, timeout=30).stdout.strip() or "?"
        if ahead == "0":
            return f"branch sync: {branch} is current with main{fetch_note}"
        return (f"branch sync: {branch} is {ahead} commit(s) ahead of main and has all of "
                f"it — nothing to pull{fetch_note}")

    if run_git_here(["merge-base", "--is-ancestor", "HEAD", "origin/main"],
                    working_directory, timeout=15).returncode == 0:
        merged = run_git_here(["merge", "--ff-only", "origin/main"], working_directory)
        if merged.returncode != 0:
            return (f"branch sync: {branch} could not fast-forward: "
                    f"{merged.stderr.strip() or 'no detail'}{fetch_note}")
        tip = run_git_here(["rev-parse", "--short", "HEAD"],
                           working_directory, timeout=15).stdout.strip()
        return f"branch sync: {branch} fast-forwarded to main ({tip}){fetch_note}"

    ahead = run_git_here(["rev-list", "--count", "origin/main..HEAD"],
                         working_directory, timeout=30).stdout.strip() or "?"
    behind = run_git_here(["rev-list", "--count", "HEAD..origin/main"],
                          working_directory, timeout=30).stdout.strip() or "?"
    return (f"branch sync: {branch} is {ahead} ahead of main and {behind} behind — merge when "
            f"ready (git merge origin/main){fetch_note}")


def launch_agent_session(agent_command: str, session_id: str, working_directory: Path,
                         prompt: str, resume: bool = False,
                         remote_control_name: str = ""):
    """Start one interactive session, inheriting this console's terminal.

    resume=True launches `--resume <id>` instead of `--session-id <id>`: the
    crash-recovery path (nedschorus#120), where the session to run already
    has a transcript and must continue it. The CLI reuses the resumed id in
    place (--fork-session is the opt-out), so the state file's session_id
    stays correct for extraction at the next recycle — confirmed live
    2026-08-21, when the crash-recovered seats' transcripts grew under
    their original ids.

    remote_control_name launches with `--remote-control <name>`, which turns
    Remote Control on for the session and fixes the name it answers to. Both
    halves matter for cross-machine agent messaging: a session on another
    machine is reachable only while it is connected to Remote Control, and it
    is addressed by its Remote Control title, never by its local session name.
    Left to itself the CLI derives that title from the conversation and
    rewrites it as the conversation moves on, so a seat's address drifts under
    anyone trying to use it — observed 2026-08-27, when the Mac's mac-prof
    seat answered from three different titles inside twenty minutes. Passing
    the seat's own name pins it: this seat is `prof` on every machine, for the
    life of the session. An empty value launches without the flag, leaving the
    CLI's own defaults in charge.

    This widens what a seat's name means. It named local files; now it is also
    the address agents on other machines use, so two seats sharing a name are
    no longer merely confusing — they are ambiguous to a sender. The derived
    titles this replaces could not collide, because the CLI qualified them with
    the hostname. The fleet already keeps its names distinct by habit (the Mac
    runs `mac-prof` where this box runs `prof`); this makes the habit load-
    bearing, which is why --agent's own help text now says so."""
    flag = "--resume" if resume else "--session-id"
    command = [agent_command, flag, session_id]
    if remote_control_name:
        command += ["--remote-control", remote_control_name]
    command.append(prompt)
    return subprocess.Popen(command, cwd=str(working_directory))


class AdoptedSession:
    """A session this supervisor did not launch, identified by process id.

    A supervisor normally owns the process it started and can terminate it
    through that handle. A session started by hand — the founding boot, or any
    agent a person launched in a console — has no such owner, so it can never
    recycle. Adoption closes that: the agent's own handoff script starts a
    supervisor and tells it which process to watch, and everything after the
    kill is identical to the ordinary cycle.
    """

    def __init__(self, session_id: str, process_id: int):
        self.session_id = session_id
        self.process_id = process_id

    def poll(self):
        """Return None while the process is alive, 0 once it is gone."""
        try:
            os.kill(self.process_id, 0)
        except ProcessLookupError:
            return 0
        except PermissionError:
            return None  # alive, owned by someone else
        return None

    def terminate(self):
        try:
            os.kill(self.process_id, signal.SIGTERM)
        except ProcessLookupError:
            pass

    def kill(self):
        try:
            os.kill(self.process_id, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def wait(self, timeout=None):
        """Block until the process is gone, or raise once the timeout passes."""
        deadline = time.monotonic() + (timeout if timeout is not None else 0)
        while self.poll() is None:
            if timeout is not None and time.monotonic() > deadline:
                raise subprocess.TimeoutExpired(f"pid {self.process_id}", timeout)
            time.sleep(0.2)
        return 0


def claim_supervisor_lock(lock_path: Path) -> bool:
    """Take the one-supervisor-per-agent lock, or report it already held.

    Two supervisors on one agent would each kill the session and each launch a
    successor, so the second must not start. A lock left by a supervisor that
    died is reclaimed: the recorded process id is checked before the lock is
    believed.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            holder = int(lock_path.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            holder = None
        if holder is not None and holder != os.getpid():
            try:
                os.kill(holder, 0)
                return False  # a live supervisor already holds this agent
            except ProcessLookupError:
                pass
            except PermissionError:
                return False
        lock_path.unlink(missing_ok=True)  # the holder is gone; reclaim it
        return claim_supervisor_lock(lock_path)
    os.write(descriptor, f"{os.getpid()}\n".encode("utf-8"))
    os.close(descriptor)
    return True


def wait_for_handoff(process, handoff_path: Path, consumed_counter, state_path: Path, state: dict):
    """Block until the agent writes a new handoff, or the session exits.

    Returns the handoff fields when a counter above `consumed_counter`
    appears, or None if the session ended on its own without writing one.
    Stamps the heartbeat while it waits, so the watched agent can tell a
    live supervisor from a dead one.

    The exit check must not preempt the file check: a headless session exits
    when its turn ends, so its handoff arrives AS a process exit — the file
    was written during the turn, before the exit was observable. Exit with a
    new counter on disk is a handoff; exit without one is abandonment.
    """
    last_stamp = 0.0
    while True:
        exited = process.poll() is not None

        if time.monotonic() - last_stamp >= HEARTBEAT_INTERVAL_SECONDS:
            stamp_heartbeat(state_path, state)
            last_stamp = time.monotonic()

        if handoff_path.is_file():
            fields = parse_handoff_file(handoff_path)
            counter = counter_from(fields)
            if counter is not None and (consumed_counter is None or counter > consumed_counter):
                return fields

        if exited:
            return None

        time.sleep(HANDOFF_POLL_SECONDS)


def stop_session(process) -> None:
    process.terminate()
    try:
        process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        print("handoff-supervisor: session ignored terminate; killing", file=sys.stderr)
        process.kill()
        process.wait()


@dataclass
class SupervisorSettings:
    """Everything one supervisor needs, resolved from the command line."""

    agent: str
    working_directory: Path
    handoff_directory: Path
    agent_command: str
    first_prompt: str
    # Crash recovery (nedschorus#120): a session id whose transcript the FIRST
    # launch resumes (`claude --resume`) instead of starting fresh. Later
    # recycles mint fresh ids as always. The caller is responsible for having
    # checked that no unconsumed handoff waits — boot-ignition is skipped.
    resume_session_id: str = ""
    # A real annotation, not a string: this module is loaded by importlib in the
    # threshold hook and the tests, where a forward reference cannot resolve.
    adopted_session: Optional[AdoptedSession] = None

    @property
    def handoff_path(self) -> Path:
        return self.handoff_directory / f"{self.agent}-handoff.md"

    @property
    def state_path(self) -> Path:
        return self.handoff_directory / f"{self.agent}-supervisor-state.json"

    @property
    def lock_path(self) -> Path:
        return self.handoff_directory / f"{self.agent}-supervisor.lock"


def carry_over_to_successor(settings: SupervisorSettings, retiring_session_id: str,
                            handoff_fields: dict, generation: int):
    """Extract, archive, prune, and build the successor's launch.

    Returns (successor_session_id, ignition_prompt), or (None, None) when
    extraction failed and relaunching would lose the dialog.
    """
    extract_path = settings.handoff_directory / f"{settings.agent}-dialog-{generation:04d}.md"
    extracted = extract_dialog(retiring_session_id, settings.working_directory, extract_path)
    if not extracted:
        print(
            "handoff-supervisor: extraction failed; not relaunching "
            "(the transcript is intact — recover by hand)",
            file=sys.stderr,
        )
        return None, None

    shutil.copy2(
        settings.handoff_path,
        settings.handoff_directory / f"{settings.agent}-handoff-{generation:04d}.md",
    )
    prune_old_generations(settings.handoff_directory, f"{settings.agent}-dialog")
    prune_old_generations(settings.handoff_directory, f"{settings.agent}-handoff")

    queue_status = queue_status_line(settings.working_directory)
    print(f"handoff-supervisor: {queue_status}")

    successor_session_id = str(uuid.uuid4())
    # Two stories, and the console must not tell the wrong one: under a
    # pinned list nothing is carried because nothing needs to be, and
    # printing "carried 0 task record(s)" there reads as a failure to carry.
    pinned_list = pinned_task_list_id()
    if pinned_list:
        print(f"handoff-supervisor: tasks live in the seat-pinned list {pinned_list}; "
              f"the successor opens that same list, so nothing is carried")
    else:
        copied = preseed_tasks(retiring_session_id, successor_session_id)
        print(f"handoff-supervisor: carried {copied} task record(s) to the successor")

    prompt = build_ignition_prompt(
        extract_path, handoff_fields, task_count_for(successor_session_id), queue_status
    )
    return successor_session_id, prompt


def supervise_sessions(settings: SupervisorSettings) -> int:
    """Launch, watch, and recycle sessions until one ends without a handoff."""
    state = read_supervisor_state(settings.state_path)
    generation = state.get("generation", 0)
    if settings.first_prompt:
        prompt = settings.first_prompt
    elif settings.resume_session_id:
        # A resumed session holds its full pre-crash context; the no-handoff
        # default would tell it to ask for work it already has (PR #131
        # review round 3, P3-4 — the recovery script writes a richer prompt
        # file, and this default makes the by-hand flag equally truthful).
        prompt = (
            "This session was resumed by crash recovery (nedschorus#120): the "
            "previous incarnation died without a handoff. Re-verify in-flight "
            "state before trusting it, then continue the work underway."
        )
    else:
        prompt = f"You are {settings.agent}. No handoff exists yet; ask what to work on."

    adopted = settings.adopted_session
    # A fresh start always mints a new session id. Reusing the one in the state
    # file would launch `claude --session-id` against a transcript that already
    # exists — and if the supervisor died while its agent kept running, would put
    # two processes on one session id. Adoption is how a running session is
    # picked back up; resume (nedschorus#120) is how a CRASHED session's
    # transcript is continued, and applies to the first launch only.
    resume_first_launch = bool(settings.resume_session_id) and adopted is None
    if adopted:
        session_id = adopted.session_id
    elif resume_first_launch:
        session_id = settings.resume_session_id
    else:
        session_id = str(uuid.uuid4())

    print(f"handoff-supervisor: {settings.agent} in {settings.working_directory}")
    print(f"handoff-supervisor: watching {settings.handoff_path}")

    # The resume path (crash recovery, nedschorus#120) must not meet a stale
    # handoff either: the recovery script defers to boot-ignition when one
    # waits, but this flag can be run by hand, and the wait loop would then
    # kill the just-resumed session for a file predating it (PR #131 review,
    # finding 4). Mark any waiting handoff consumed BEFORE the resume launch —
    # the operator chose the transcript over the handoff by passing the flag.
    if resume_first_launch and settings.handoff_path.is_file():
        stale_fields = parse_handoff_file(settings.handoff_path)
        stale_counter = counter_from(stale_fields)
        if stale_counter is not None and stale_counter > (state.get("consumed_counter") or 0):
            print(
                f"handoff-supervisor: a handoff (counter {stale_counter}) predates this "
                "resume; marking it consumed so it cannot kill the resumed session. "
                "If that handoff was the fresher truth, stop and relaunch WITHOUT "
                "--resume-session-id — boot-ignition will consume it."
            )
            state["consumed_counter"] = stale_counter

    # A fresh boot may find an unconsumed handoff — a crash or reboot ended the
    # previous cycle after the write but before a supervisor acted on it. Ignite
    # from it directly. Launching first and letting the wait loop find the file
    # would kill the just-born session for a handoff that predates it.
    if adopted is None and not resume_first_launch and settings.handoff_path.is_file():
        boot_fields = parse_handoff_file(settings.handoff_path)
        boot_counter = counter_from(boot_fields)
        consumed = state.get("consumed_counter")
        if boot_counter is not None and (consumed is None or boot_counter > consumed):
            if boot_fields.get("dont-restart"):
                # The handoff asks for a consultation before any relaunch;
                # boot-ignition must not steamroll it. Same terminal rule as
                # the in-cycle dont-restart branch below.
                if not sys.stdin.isatty():
                    print("handoff-supervisor: dont-restart, and no terminal to ask on; stopping")
                    state["consumed_counter"] = boot_counter
                    write_supervisor_state(settings.state_path, state)
                    return 0
                if input("handoff-supervisor: restart? y/n ").strip().lower() != "y":
                    print("handoff-supervisor: stopping at the agent's request")
                    state["consumed_counter"] = boot_counter
                    write_supervisor_state(settings.state_path, state)
                    return 0
            generation += 1
            retiring_session_id = state.get("session_id")
            successor_session_id, ignition = (
                carry_over_to_successor(settings, retiring_session_id, boot_fields, generation)
                if retiring_session_id else (None, None)
            )
            if successor_session_id is None:
                # No retiring transcript to extract (new machine, or it is
                # gone). The next-step still carries the work: ignite with it
                # alone rather than discarding the handoff.
                successor_session_id = str(uuid.uuid4())
                ignition = (
                    f"{next_step_from(boot_fields)}\n\n(Recovered at supervisor boot: the "
                    "previous session's dialog extract is unavailable; this next-step and the "
                    "repository are your whole context.)"
                )
                print("handoff-supervisor: igniting from an unconsumed handoff without a dialog extract")
            else:
                print("handoff-supervisor: igniting from an unconsumed handoff left by a previous cycle")
            state["consumed_counter"] = boot_counter
            session_id, prompt = successor_session_id, ignition

    while True:
        state.update({"session_id": session_id, "generation": generation})
        write_supervisor_state(settings.state_path, state)

        if adopted is not None:
            print(
                f"handoff-supervisor: adopted running session {session_id} "
                f"(process {adopted.process_id}, generation {generation})"
            )
            process, adopted = adopted, None  # adoption applies to this pass only
        else:
            # Only on the launch path: an adopted session is alive in this
            # directory, and changing files under a working agent is the one
            # thing this must never do.
            print(f"handoff-supervisor: {sync_working_branch_with_main(settings.working_directory)}")
            verb = "resuming" if resume_first_launch else "launching"
            print(f"handoff-supervisor: {verb} session {session_id} (generation {generation})")
            process = launch_agent_session(
                settings.agent_command, session_id, settings.working_directory, prompt,
                resume=resume_first_launch, remote_control_name=settings.agent,
            )
            resume_first_launch = False  # recovery applies to the first launch only

        handoff_fields = wait_for_handoff(
            process, settings.handoff_path, state.get("consumed_counter"), settings.state_path, state
        )
        if handoff_fields is None:
            print("handoff-supervisor: session ended without a handoff; supervisor stopping")
            return 0

        # A successor inherits this process's stdio, so without a terminal
        # there is no seat to relaunch onto: the successor reads EOF at its
        # first need for input and dies after one turn — observed 2026-08-14,
        # when an adopted console session was killed and its successor
        # reported into a log file. Refusing BEFORE the kill and the consume
        # leaves the session alive and its handoff intact for a seated
        # supervisor (a launcher-owned tmux pane) or a by-hand relaunch.
        # dont-restart is exempt: that flow consumes and stops without ever
        # launching a successor, which needs no seat.
        if not sys.stdin.isatty() and not handoff_fields.get("dont-restart"):
            print(
                "handoff-supervisor: a handoff arrived, but this supervisor has no terminal to "
                "seat a successor on — not recycling. The session stays up and the handoff stays "
                "unconsumed; a seated supervisor (launch-claude-ubuntu / launch-claude-mac) or a "
                "by-hand relaunch picks it up. Stopping."
            )
            return 0

        stop_session(process)
        generation += 1

        if handoff_fields.get("dont-restart"):
            if not sys.stdin.isatty():
                # Nobody can answer: a supervisor the agent started has no
                # terminal, and asking would raise EOFError before the consumed
                # counter is recorded — leaving the next supervisor to re-fire on
                # a stale handoff. Not relaunching is the answer dont-restart asks
                # for, so take it.
                print("handoff-supervisor: dont-restart, and no terminal to ask on; stopping")
                answer = "n"
            else:
                answer = input("handoff-supervisor: restart? y/n ").strip().lower()
            if answer != "y":
                print("handoff-supervisor: stopping at the agent's request")
                state["consumed_counter"] = counter_from(handoff_fields)
                write_supervisor_state(settings.state_path, state)
                return 0

        successor_session_id, prompt = carry_over_to_successor(
            settings, session_id, handoff_fields, generation
        )
        if successor_session_id is None:
            return 0

        state["consumed_counter"] = counter_from(handoff_fields)
        session_id = successor_session_id


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Run and recycle one agent session.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--agent", required=True,
                        help="agent name; names the handoff and state files, and the Remote "
                             "Control name the session answers to. That name is how agents on "
                             "OTHER machines address this seat, so it has to be unique across "
                             "the whole fleet, not just this machine")
    parser.add_argument("--cd", default=".", help="the agent's worktree")
    parser.add_argument("--handoff-dir", default="~/.claude/handoffs", help="machine-local handoff directory")
    parser.add_argument("--agent-command", default="claude", help="the CLI to launch")
    parser.add_argument("--first-prompt", default="", help="prompt for the first session (no handoff yet)")
    parser.add_argument(
        "--first-prompt-file", default="",
        help="file holding the first session's prompt; read here so no caller "
             "has to smuggle file content through nested shell quoting",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="report whether a supervisor is watching this agent, then exit (0 alive, 1 not)",
    )
    parser.add_argument(
        "--resume-session-id", default="",
        help="crash recovery (nedschorus#120): the first launch resumes this "
             "session's transcript (claude --resume) instead of starting fresh; "
             "later recycles mint fresh ids as always. A handoff already on disk "
             "is marked consumed rather than igniting or recycling — passing this "
             "flag chooses the transcript over any waiting handoff",
    )
    parser.add_argument(
        "--adopt-session-id", default="",
        help="watch an already-running session with this id instead of launching one",
    )
    parser.add_argument(
        "--adopt-process-id", type=int, default=0,
        help="process id of the already-running session to adopt; required with --adopt-session-id",
    )
    arguments = parser.parse_args(argv)

    if arguments.check:
        state_path = (
            Path(arguments.handoff_dir).expanduser() / f"{arguments.agent}-supervisor-state.json"
        )
        alive, explanation = supervisor_liveness(state_path)
        print(explanation)
        return 0 if alive else 1

    if bool(arguments.adopt_session_id) != bool(arguments.adopt_process_id):
        parser.error("--adopt-session-id and --adopt-process-id must be given together")
    if arguments.resume_session_id and arguments.adopt_session_id:
        parser.error("--resume-session-id and --adopt-session-id are different recoveries: "
                     "resume continues a DEAD session's transcript, adopt watches a LIVE one")

    adopted = None
    if arguments.adopt_session_id:
        adopted = AdoptedSession(arguments.adopt_session_id, arguments.adopt_process_id)
        if adopted.poll() is not None:
            print(
                f"handoff-supervisor: process {arguments.adopt_process_id} is already gone; "
                "nothing to adopt",
                file=sys.stderr,
            )
            return 2

    if arguments.first_prompt_file:
        prompt_path = Path(arguments.first_prompt_file).expanduser()
        if not prompt_path.is_file():
            parser.error(f"--first-prompt-file does not exist: {prompt_path}")
        arguments.first_prompt = prompt_path.read_text(encoding="utf-8").strip()

    working_directory = Path(arguments.cd).expanduser().resolve()
    if not working_directory.is_dir():
        parser.error(f"--cd is not a directory: {working_directory}")
    if shutil.which(arguments.agent_command) is None:
        print(f"handoff-supervisor: no such command: {arguments.agent_command}", file=sys.stderr)
        return 3

    handoff_directory = Path(arguments.handoff_dir).expanduser()
    handoff_directory.mkdir(parents=True, exist_ok=True)

    settings = SupervisorSettings(
        agent=arguments.agent,
        working_directory=working_directory,
        handoff_directory=handoff_directory,
        agent_command=arguments.agent_command,
        first_prompt=arguments.first_prompt,
        resume_session_id=arguments.resume_session_id,
        adopted_session=adopted,
    )

    if not claim_supervisor_lock(settings.lock_path):
        print(
            f"handoff-supervisor: another supervisor already holds {settings.agent} "
            f"({settings.lock_path}); not starting a second one",
            file=sys.stderr,
        )
        return 4

    try:
        return supervise_sessions(settings)
    finally:
        settings.lock_path.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
