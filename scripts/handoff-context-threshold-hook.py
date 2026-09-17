#!/usr/bin/env python3
"""Tell a session to write its handoff once context runs low.

The handoff system's auto-trigger (specification:
docs/cross-project/fast-handoff-design.md). Wire it as a Stop hook in
settings.json; it runs at every turn boundary.

Stop-hook stdin does not carry the context window, so the used share is
computed from the session's own transcript: every assistant record carries
the model and the token usage of the request that produced it. A reply built
from several passes of this model -- an advisor call is one -- carries them
in usage["iterations"], and the share is the largest pass rather than the
top-level sum, which is not a context size (see used_tokens_of). That works
in every session type, headless included — a statusline-relay fallback was
cut 2026-08-12 because its only remaining trigger was a session whose first
turn had not completed, a moment the threshold cannot be crossed. A
supervisor-liveness gate (silent unless --agent's supervisor was alive) was
cut the same day, and the reason still holds: a firing with no supervisor
watching is what surfaces the dead one. The writer script reports that nothing
is watching and tells the agent to have the user run resupervise-seat.py (from
self-registration on 2026-08-06 until its removal on 2026-08-14, it started an
adopting supervisor instead), so silence only ever turned a dead supervisor
into a permanent stall.

When the used share reaches the threshold, the hook emits a system message
telling the agent to run the handoff skill; the supervisor takes over from
there. Below the threshold it stays silent.

It fires ONCE per session: after firing it records the fact in the handoff
directory, so the reminder does not repeat at every subsequent turn while
the agent is composing the handoff.

A SESSION ITS CALLER REINCARNATES IS LEFT ALONE. scripts/ghi-info-ask.py runs
ghi-info as `claude -p` turns, reincarnates that session on triggers of its
own, and returns a turn's last message as its answer. On 2026-09-16 ghi-info
crossed the threshold at 52% while answering: it ran the handoff skill, and the
caller received the handoff notice in place of the reading list it had just
written. The caller now sets NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER
in its claude's environment, which a `claude -p` Stop hook inherits (measured
2026-09-16), and the hook stays silent while it is set. This is not the
supervisor-liveness gate cut above: an unsupervised seat still hears the hook.

WHILE A SUBAGENT IS RUNNING THE HANDOFF WAITS (user-ruled 2026-08-27). A
reincarnation kills the session, and the session's in-process subagents die with
it: on 2026-08-27 a seat dispatched a builder subagent at 20:38, the hook
fired at 50% at 20:43, and the subagent died four minutes into its job. So
at the threshold the hook first asks whether any Agent-tool subagent is
still in flight. The first time one is, it says so — spawn no new subagents,
the handoff fires when they finish — and records that it has said it, in a
deferral marker beside the fired one. At every later boundary while the wait
continues it exits silently. Saying it again would refuse the stop again, and
a hook that refuses the stop at every boundary drives an otherwise idle
session into a loop of short turns, one model call each, for as long as the
subagent runs. Going quiet costs nothing: the completion notification wakes
the session by itself, and the boundary that ends that turn is where the scan
finds nothing in flight and the handoff fires. The standing ruling that a reincarnation records its subagents rather
than waiting for them (2026-08-23, [nedschorus#153]) still governs
everything else; this deferral is its one bounded exception, and
--ceiling-used-percentage is the bound. Above the ceiling the handoff fires
whatever is running, because a session deferring to a subagent that never
finishes would run out of context instead of reincarnating — which is a worse
loss than the one this defers.

TWO MARKERS, both in the handoff directory and both named for the session.
`<session>-handoff-asked` is the older one and keeps its meaning exactly: it
is written when the handoff fires, and it is what stops the reminder
repeating while the agent composes the handoff. `<session>-handoff-deferred`
is written the first time the hook defers, and its whole job is to keep the
deferral quiet once it has been said. It is left in place when the handoff
finally fires — the fired marker is what governs repeats, and clearing the
deferral marker there would tell nobody anything.

IN FLIGHT means spawned and not yet finished, both read from the transcript.
A spawn is a tool result carrying `status: async_launched` and an `agentId`;
a Monitor's tool result carries neither, so monitors are excluded by their
shape rather than by a guess about their ids. A finish is that agent's id
inside the `<task-id>` tag of a task-notification. The notification arrives
in more than one record shape — as a `user` record when the session is idle
enough to be interrupted, as an `attachment` plus `queue-operation` pair
when it is busy — and in the 2026-08-27 transcript six of the fourteen
finished subagents produced no `user` record at all, so the scan matches the
tag wherever in a record it appears rather than keying on one shape.

WHAT THE SCAN COSTS: the whole transcript, read once. The used share comes
from the tail, but a spawn can be hours back, so this read cannot be a tail
read. Measured at roughly 2 ms per megabyte: 7 ms on the 3.5 MB transcript of
the session this change came from, and 8.7 ms on the largest transcript
measured, 3.9 MB. Those are 2.0 and 2.23 ms per megabyte; the rate is
given to one figure because it is a sizing aid, not a model, and an
idle machine is what it assumes — the same scan under eight concurrent
review subprocesses measured 24 to 48 ms. Adding the background-task launch
key (2026-09-14) cost one more substring test per line: 12.3 ms against
10.7 ms without it on that day's 3.8 MB transcript, best of five, with the
seat working. It is paid only between the threshold and the fire:
never below the threshold, and never once the fired marker is written. A
silent deferred boundary still pays it, because whether the wait is over is
exactly what it is asking.

WHAT THE SCAN DOES WHEN IT CANNOT TELL: it says so, and the handoff waits.
A line that carries the spawn marker and does not parse, or a read error,
raises TranscriptCouldNotBeFullyRead, and below the ceiling that defers
exactly as a running subagent does, with a notice that says the count is
unknown. Before that the two answers were one: an empty list meant both
"nothing is running" and "I could not look", and main() fired on either.

WHAT AN EMPTY LIST MEANS, EXACTLY: no parseable spawn record is without a
completion. That is narrower than "nothing is running", and the difference is
not academic. Only a line carrying the spawn marker is parsed at all, and
across 550 real spawn records the marker sits a median 31.5% of the way into
its line, so a record cut off before its marker is not a candidate — it is
passed over in silence and still yields an empty list. Failing closed narrows
this gap; it does not close it.

HOW LIKELY A TRUNCATED RECORD IS, MEASURED (merge-lane review of PR #180,
2026-08-28). An earlier version of this paragraph called a half-written final
line "the ordinary state" of a transcript being appended to. That was asserted,
not measured, and the measurements do not support it: of 841 transcripts on
this machine, none ends mid-line; appending a median-sized spawn record
(5.1 KB) 3,000 times while polling concurrently exposed no partial record, and
800 appends of the largest observed record (86 KB) exposed none either. A
realistically sized append reads atomically on this filesystem. What is NOT
established is whether the harness writes each record in one write() call,
which is why the case is guarded rather than dismissed: failing closed costs
at most a deferral to the ceiling, and firing wrongly costs a subagent.

THE READ-ERROR HALF IS NOT REACHABLE THROUGH main(). The used-share read runs
first on the same file and exits the hook when it returns None, so a
transcript this process cannot open never reaches the scan. The raise is kept
for any other caller, and for a file that stops being readable between the two
reads.

TWO WAYS THE SCAN CAN STILL BE WRONG, both of them in the fire-too-early
direction and neither bounded by the ceiling, because both look like a clean
answer rather than a failure. An agent resumed by SendMessage runs again with
no new spawn record, so its earlier completion still stands and the handoff
fires while it works — the behaviour this project had before this change. A
subagent stopped by TaskStop takes the same path as any other finish and is
untested, because no specimen exists. A completion the scan misses errs the
other way and defers the handoff no further than the ceiling.

A RUNNING BACKGROUND BASH TASK COUNTS TOO, FOR A BOUNDED WHILE (user-ruled
2026-09-14). The deferral above saw only Agent-tool subagents, and on
2026-09-14 session 831c08ee handed off at 50% with the cold-read grid
(scripts/cold-read-grid.py) running as a background Bash task: the scan found
nothing in flight, the reincarnation killed the grid and its six reviewer
cells 12.7 minutes in, and five of the six reports were lost, because a cell
writes its report as its last act. The user's ruling, verbatim: "do 72 - if
you know how to see if the background tasks is not stuck or not open ended,
or we have some reasonable threshold like 15 minutes." Nothing in the
transcript can tell a running task from a stuck one: the harness records no
pid, the Bash tool's `timeout` input is not enforced on a background task
(a 600000 ms timeout on the 27-minute grid run of 2026-09-14), and the
task's output file is silent whenever the command redirects its own stdout,
as the grid's did. So the threshold is the instrument: a background task
holds the handoff only while it is younger than
--background-task-wait-minutes, and past that it is presumed stuck or
open-ended and holds nothing. The default is 30, not the 15 the ruling
offered as an example, because 15 would have killed the very run this is
for: the 2026-09-11 grid died at 12.7 minutes needing about 20, and across
365 finished background tasks on the Mac (measured 2026-09-14) the 90th
percentile is 20 minutes and the 95th is 31, with cold-read grid runs at
8 to 27 minutes. The ceiling still bounds everything.

A launch is a tool result carrying `backgroundTaskId`, which a Monitor's
result and a subagent's spawn do not; its age is read from the launch
record's own timestamp, and a launch with no readable timestamp counts as
in flight, failing closed like the rest of the scan. Its finish is the same
`<task-id>` notification a subagent's is. Both are read in the one pass the
subagent scan already makes, so the cost is one more substring test per
line; a line carrying the launch key that does not parse raises
TranscriptCouldNotBeFullyRead exactly as a half-written spawn does.

Threshold: --threshold-used-percentage, default 50.
Ceiling: --ceiling-used-percentage, default 65.
Background task wait: --background-task-wait-minutes, default 30.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HANDOFF_DIRECTORY = Path.home() / ".claude" / "handoffs"

# Set, to the calling script's name, by a caller that reincarnates the session
# itself; the hook stays silent while it is set. Module docstring.
REINCARNATION_OWNED_BY_CALLER_VARIABLE = "NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER"

# Context window per model, so a percentage can be computed from the transcript
# alone — the status line is an interactive-only surface, and headless sessions
# never run it. Prefix-matched against the model id each assistant record
# carries. A model absent from this table falls back to the default; the table
# is worth re-checking when a new model ships, since a wrong window silently
# scales the threshold rather than failing.
CONTEXT_WINDOW_TOKENS_BY_MODEL_PREFIX = {
    "claude-fable-5": 1_000_000,
    "claude-mythos-5": 1_000_000,
    "claude-opus-5": 1_000_000,
    "claude-opus-4": 1_000_000,
    "claude-sonnet-5": 1_000_000,
    "claude-sonnet-4-6": 1_000_000,
    "claude-haiku-4-5": 200_000,
}
DEFAULT_CONTEXT_WINDOW_TOKENS = 200_000

# How much of the transcript's tail to read when looking for the newest
# assistant record. Sized to clear a few large tool-result records; the read
# doubles from here when that is not enough.
FIRST_TAIL_READ_BYTES = 256 * 1024

# The skill carries the whole procedure. A hook message that restated any of it
# would be a second copy going stale on its own schedule, which this one did
# twice in a day: once when boundary judgment was removed, once when the writer
# took over the fields.
HANDOFF_INSTRUCTION = "Run the handoff skill now."

# The deferral says the opposite of the instruction above, so it must not read
# like it: the agent is being told to keep working, and told the two things
# that would extend the wait indefinitely. {running} is the phrase
# running_phrase() builds: "1 subagent(s)", "1 background task(s)", or both.
HANDOFF_DEFERRED_NOTICE = (
    "Context at {used_percentage:.0f}% — handoff deferred while {running} run. "
    "Spawn no new subagents and start no new background tasks; the handoff "
    "fires when they finish, when a background task outlives its "
    "{wait_minutes:g} minute wait, or when context reaches the ceiling."
)

# Said instead of the notice above when the scan could not finish. It reports
# the wait without a count, because the count is exactly what is not known.
HANDOFF_DEFERRED_UNKNOWN_COUNT_NOTICE = (
    "Context at {used_percentage:.0f}% — handoff deferred: the transcript "
    "could not be fully read, so what is running is unknown. Spawn no new "
    "subagents and start no new background tasks; the handoff fires when "
    "they finish, or when context reaches the ceiling."
)

# A background Bash task older than this no longer holds the handoff. Why 30
# and not the 15 the ruling offered: the module docstring, with the
# measurements.
DEFAULT_BACKGROUND_TASK_WAIT_MINUTES = 30.0

class TranscriptCouldNotBeFullyRead(Exception):
    """The in-flight scan could not read the whole transcript, so what it
    found is not an answer about what is running.

    Raised rather than returned so no caller can mistake it for "nothing in
    flight". That mistake is the defect this class exists to prevent: an empty
    list is falsy, `if subagents_in_flight:` reads it as an all-clear, and the
    handoff fires and kills the subagent the deferral is for.
    """


# What a spawned subagent's tool result carries and a Monitor's does not.
SPAWNED_SUBAGENT_STATUS = "async_launched"

# What a background Bash task's tool result carries and neither a Monitor's
# (`taskId`, `persistent`) nor a subagent's spawn (`agentId`) does. Tested as
# a key of toolUseResult, never as a bare word: a grep over a transcript
# prints the word into an ordinary foreground Bash result.
BACKGROUND_TASK_LAUNCH_KEY = "backgroundTaskId"

# A completion notification names the agent that finished in this tag, in every
# record shape that carries the notification.
TASK_NOTIFICATION_TASK_ID_PATTERN = re.compile(r"<task-id>([^<]+)</task-id>")


def hook_payload_from_stdin() -> dict:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def context_window_for(model: str) -> int:
    """Return the model's context window in tokens."""
    for prefix, window in CONTEXT_WINDOW_TOKENS_BY_MODEL_PREFIX.items():
        if model.startswith(prefix):
            return window
    return DEFAULT_CONTEXT_WINDOW_TOKENS


def newest_assistant_message(path: Path):
    """Return the newest assistant record's message, reading from the end.

    Only the last request's usage matters, so the file is read backwards in
    chunks rather than parsed front to back — a transcript grows all session,
    and this hook runs at every turn boundary. The window doubles until the
    record is found or the whole file has been read, so a run of oversized
    tool-result records cannot hide it.
    """
    file_size = path.stat().st_size
    window = FIRST_TAIL_READ_BYTES

    while True:
        with path.open("rb") as handle:
            start = max(0, file_size - window)
            handle.seek(start)
            chunk = handle.read()

        lines = chunk.split(b"\n")
        if start > 0:
            lines = lines[1:]  # the first line is a fragment of an earlier record

        for raw_line in reversed(lines):
            if not raw_line.strip():
                continue
            try:
                record = json.loads(raw_line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if record.get("type") != "assistant":
                continue
            message = record.get("message", {})
            if message.get("usage"):
                return message

        if start == 0:
            return None  # whole file read, no assistant record with usage
        window *= 2


def context_used_percentage_from_transcript(transcript_path: str):
    """Return the session's used-context share, read from its transcript.

    Every assistant record carries both the model and the
    usage of the request that produced it; the newest record's input plus
    cached tokens is what the model last had in front of it, and the model id
    gives the window to divide by.
    """
    if not transcript_path:
        return None
    path = Path(transcript_path).expanduser()
    if not path.is_file():
        return None

    try:
        message = newest_assistant_message(path)
    except OSError:
        return None
    if message is None:
        return None

    return 100.0 * used_tokens_of(message["usage"]) / context_window_for(
        message.get("model", ""))


# The fields that say how much the model had in front of it.
USED_TOKEN_FIELDS = ("input_tokens", "cache_read_input_tokens",
                     "cache_creation_input_tokens")
# A reply built from several passes of this model carries one entry per pass
# in usage["iterations"], each with its own counts and a "type": the advisor
# tool's reply has this model's passes typed "message" around the advisor
# model's own, typed "advisor_message".
USAGE_ITERATIONS_FIELD = "iterations"
OWN_PASS_ITERATION_TYPE = "message"


def used_tokens_of(usage: dict) -> int:
    """The tokens the model last had in front of it.

    THE TOP-LEVEL FIELDS ADD THE PASSES UP, WHICH IS NOT A CONTEXT SIZE
    (measured 2026-09-17, session 8b3cd015). An advisor call makes one reply
    from three passes -- this model asks, the advisor model answers, this
    model carries on -- and the record's top-level cache_read_input_tokens
    was 1,111,912: the sum of a 555,460-token pass and a 556,452-token one,
    against a real context of about 557,000, 56% of the window. Read as a
    context size that is 111%, and this hook would have fired a handoff at
    half the real share -- above the ceiling, so even with a cold-read grid
    running, which is exactly how five of six reviewer reports were lost on
    2026-09-14.

    So when the record says how it was built, the size is the largest of this
    model's own passes, not their sum. The advisor model's pass is left out:
    its context is its own, not this session's. A record with no iterations
    list -- every ordinary reply -- is read from the top-level fields as
    before, which is the same number for a single-pass reply.
    """
    iterations = usage.get(USAGE_ITERATIONS_FIELD)
    if isinstance(iterations, list):
        own_passes = [
            sum(entry.get(field, 0) or 0 for field in USED_TOKEN_FIELDS)
            for entry in iterations
            if isinstance(entry, dict)
            and entry.get("type", OWN_PASS_ITERATION_TYPE) == OWN_PASS_ITERATION_TYPE
        ]
        if own_passes:
            return max(own_passes)
    return sum(usage.get(field, 0) or 0 for field in USED_TOKEN_FIELDS)


class WorkInFlight:
    """What the scan found still running: Agent-tool subagents and background
    Bash tasks, each in launch order.

    A class rather than a tuple so that `if flight:` means "something is
    running": a two-field tuple is truthy even when both fields are empty,
    and that reading would defer a handoff behind nothing.
    """

    def __init__(self, subagent_ids, background_task_ids):
        self.subagent_ids = list(subagent_ids)
        self.background_task_ids = list(background_task_ids)

    def __bool__(self):
        return bool(self.subagent_ids or self.background_task_ids)


def running_phrase(flight: WorkInFlight) -> str:
    """The counts for the deferral notice, naming only the kinds present."""
    parts = []
    if flight.subagent_ids:
        parts.append(f"{len(flight.subagent_ids)} subagent(s)")
    if flight.background_task_ids:
        parts.append(f"{len(flight.background_task_ids)} background task(s)")
    return " and ".join(parts)


def record_age_seconds(record, now):
    """Seconds from the record's own timestamp to `now`, or None when the
    record has no timestamp or it does not parse. Transcript timestamps are
    ISO 8601 with a trailing Z, which fromisoformat accepts only from Python
    3.11, hence the replace."""
    stamp = record.get("timestamp") if isinstance(record, dict) else None
    if not isinstance(stamp, str):
        return None
    try:
        launched_at = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if launched_at.tzinfo is None:
        launched_at = launched_at.replace(tzinfo=timezone.utc)
    return (now - launched_at).total_seconds()


def spawned_subagent_ids_in_flight(transcript_path: str) -> list:
    """Return the ids of the session's Agent-tool subagents still running.

    The subagent half of work_in_flight(), kept as the name the subagent
    deferral was built under; the one-pass scan and its rules are documented
    there. Background tasks are not reported here whatever their age.
    """
    return work_in_flight(transcript_path, background_task_wait_seconds=0).subagent_ids


def work_in_flight(transcript_path: str, background_task_wait_seconds: float,
                   now=None) -> WorkInFlight:
    """Return the session's Agent-tool subagents and background Bash tasks
    still running, from one pass over the whole transcript.

    A subagent is in flight when the transcript holds its spawn and no
    completion notification naming it. Both halves are read from the whole
    file, not the tail: a spawn can be hours behind the newest record, and a
    session that missed one would kill a subagent it did not know about,
    which is the failure this exists to prevent (2026-08-27).

    A background task is in flight when the transcript holds its launch, no
    completion notification names it, AND the launch is no older than
    `background_task_wait_seconds` as measured against `now` (the clock,
    unless a test supplies one). Past the wait it is presumed stuck or
    open-ended and holds nothing (user-ruled 2026-09-14; the module docstring
    has the measurements behind the default). A launch whose timestamp is
    missing or unreadable has no age and counts as in flight, bounded by the
    ceiling like every other thing the scan cannot tell.

    The cheap substring tests on each line are what keep the whole-file read
    affordable — a transcript is mostly large tool results, and only the few
    lines that could matter are parsed. Cost and limits are in the module
    docstring.

    A spawn is identified structurally, by `status: async_launched` plus an
    `agentId` in the tool result; a background task by a `backgroundTaskId`
    key in the tool result. Monitors produce task notifications too, but
    their tool results carry neither, so they never enter either set and
    their notifications match nothing.

    Order is launch order, so a caller reporting the ids reports them in the
    order the agent created them.

    THE SCAN FAILS CLOSED (merge-lane review of PR #180, 2026-08-28). It
    raises TranscriptCouldNotBeFullyRead rather than returning what it had,
    in two cases: a line that looks like a spawn record but does not parse,
    and a read error. Both mean the same thing — the scan could not tell —
    and the previous version returned [] for both, which main() read as
    "nothing is running" and fired on, killing the subagent this exists to
    protect.

    Not because a truncated record is common — it is not observed in
    practice, and the module docstring gives the measurements — but because
    the two answers cost differently. The usage reader may skip an unparsed
    line safely: skipping it costs one turn's worth of freshness. Skipping it
    here would convert "I could not tell" into "nothing is running", and only
    one of those two answers kills work. Failing closed costs at most a
    deferral to the ceiling.

    Only a line carrying the spawn marker or the launch key is parsed at all,
    so an ordinary unparsed line is not a candidate and raises nothing. That
    also bounds what this guard can catch: a record truncated before its
    marker is invisible to it. Completion tags are matched as text, so a
    truncated notification loses a completion instead of gaining one, which
    fails closed the same way: the work stays in flight and the handoff
    waits.

    A transcript that is absent altogether still reports nothing running,
    not unknown. It is not a failure to read: a session with no transcript
    launched nothing, and main() cannot reach this scan on a transcript it
    could not read, because the used-share read runs first on the same file
    and exits the hook when it returns None.
    """
    path = Path(transcript_path).expanduser() if transcript_path else None
    if path is None or not path.is_file():
        return WorkInFlight([], [])
    if now is None:
        now = datetime.now(timezone.utc)

    spawned_ids = []
    launched_task_ids = []
    launched_task_age = {}  # id -> seconds since launch, or None when unreadable
    finished_ids = set()
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                is_spawn_candidate = SPAWNED_SUBAGENT_STATUS in line
                is_launch_candidate = BACKGROUND_TASK_LAUNCH_KEY in line
                if is_spawn_candidate or is_launch_candidate:
                    try:
                        record = json.loads(line)
                    except (json.JSONDecodeError, UnicodeDecodeError) as problem:
                        # A candidate record that will not parse: this line
                        # may be the spawn or launch of work running right
                        # now, half-written as the session appends it.
                        raise TranscriptCouldNotBeFullyRead(
                            f"{path}: a spawn or launch record did not parse"
                        ) from problem
                    tool_result = record.get("toolUseResult") if isinstance(record, dict) else None
                    if not isinstance(tool_result, dict):
                        tool_result = {}
                    if is_spawn_candidate and \
                            tool_result.get("status") == SPAWNED_SUBAGENT_STATUS:
                        agent_id = tool_result.get("agentId")
                        if agent_id and agent_id not in spawned_ids:
                            spawned_ids.append(agent_id)
                    if is_launch_candidate:
                        task_id = tool_result.get(BACKGROUND_TASK_LAUNCH_KEY)
                        if task_id and task_id not in launched_task_age:
                            launched_task_ids.append(task_id)
                            launched_task_age[task_id] = record_age_seconds(record, now)
                if "<task-id>" in line:
                    finished_ids.update(TASK_NOTIFICATION_TASK_ID_PATTERN.findall(line))
    except OSError as problem:
        raise TranscriptCouldNotBeFullyRead(f"{path}: {problem}") from problem

    def still_within_wait(task_id):
        age = launched_task_age[task_id]
        return age is None or age <= background_task_wait_seconds

    return WorkInFlight(
        [agent_id for agent_id in spawned_ids if agent_id not in finished_ids],
        [task_id for task_id in launched_task_ids
         if task_id not in finished_ids and still_within_wait(task_id)],
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Fire the handoff skill when context runs low.")
    parser.add_argument("--threshold-used-percentage", type=float, default=50.0)
    parser.add_argument(
        "--ceiling-used-percentage", type=float, default=65.0,
        help="above this used share the handoff fires even with work in flight",
    )
    parser.add_argument(
        "--background-task-wait-minutes", type=float,
        default=DEFAULT_BACKGROUND_TASK_WAIT_MINUTES,
        help="a background Bash task older than this no longer holds the handoff: "
             "it is presumed stuck or open-ended",
    )
    arguments = parser.parse_args(argv)

    if os.environ.get(REINCARNATION_OWNED_BY_CALLER_VARIABLE):
        return 0  # the caller reincarnates this session; a handoff would replace its answer

    payload = hook_payload_from_stdin()
    session_id = payload.get("session_id", "")
    if not session_id:
        return 0  # no session to reason about; stay silent

    transcript_path = payload.get("transcript_path", "")
    # Every session has a transcript, headless included; before the first
    # assistant turn completes there is nothing to measure and nothing near
    # the threshold either, so None simply stays silent.
    used = context_used_percentage_from_transcript(transcript_path)
    if used is None or used < arguments.threshold_used_percentage:
        return 0  # nothing measurable yet, or still plenty of room

    fired_marker = HANDOFF_DIRECTORY / f"{session_id}-handoff-asked"
    if fired_marker.exists():
        return 0  # already asked this session; do not nag every turn

    # Below the ceiling, a running subagent (user-ruled 2026-08-27) or a
    # background Bash task younger than the wait (user-ruled 2026-09-14)
    # postpones the handoff rather than dying with the session; module
    # docstring.
    if used < arguments.ceiling_used_percentage:
        # A scan that could not finish is treated as work in flight, not as an
        # all-clear: "could not tell" and "nothing running" are different
        # answers and only one of them is safe to fire on (merge-lane review
        # of PR #180, 2026-08-28). Above the ceiling this block is skipped
        # entirely, so an unknown postpones the handoff no further than a
        # known subagent does.
        try:
            flight = work_in_flight(
                transcript_path, arguments.background_task_wait_minutes * 60)
            count_is_known = True
        except TranscriptCouldNotBeFullyRead:
            flight = None
            count_is_known = False

        if not count_is_known or flight:
            deferred_marker = HANDOFF_DIRECTORY / f"{session_id}-handoff-deferred"
            if deferred_marker.exists():
                return 0  # said once already; let the session go idle and wait

            try:
                HANDOFF_DIRECTORY.mkdir(parents=True, exist_ok=True)
                deferred_marker.write_text(f"{used:.1f}\n", encoding="utf-8")
            except OSError:
                pass  # as with the fired marker: speak now, repeat next turn

            notice = (
                HANDOFF_DEFERRED_NOTICE.format(
                    used_percentage=used, running=running_phrase(flight),
                    wait_minutes=arguments.background_task_wait_minutes,
                )
                if count_is_known
                else HANDOFF_DEFERRED_UNKNOWN_COUNT_NOTICE.format(used_percentage=used)
            )
            print(notice, file=sys.stderr)
            return 2  # exit 2 surfaces stderr to the agent as a system message

    try:
        # Nothing guarantees the directory exists this early in a session, and a
        # marker that fails to write silently means the hook nags every turn.
        HANDOFF_DIRECTORY.mkdir(parents=True, exist_ok=True)
        fired_marker.write_text(f"{used:.1f}\n", encoding="utf-8")
    except OSError:
        pass

    print(
        HANDOFF_INSTRUCTION,
        file=sys.stderr,
    )
    return 2  # exit 2 surfaces stderr to the agent as a system message


if __name__ == "__main__":
    sys.exit(main())
