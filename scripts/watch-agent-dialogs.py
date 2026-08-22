#!/usr/bin/env python3
"""Watch every fleet seat's live session transcript, one line per event.

A coordinator agent oversees the other seats — sibling Claude Code sessions,
one per directory under ~/agents — by reading their session transcripts, the
JSONL files the harness writes under ~/.claude/projects/. On 2026-08-16 the
coordinator improvised that watch with three hand-built `tail -F | jq`
pipelines, and four gaps were demonstrated:

  1. blind rollover — `tail -F` on a fixed path goes silently blind when a
     seat recycles into a new transcript file;
  2. blind arrival — a newly created seat gets no watcher until a human
     notices it;
  3. fragile filtering — the jq side mishandled the transcript schema
     (multi-block turns, truncated records);
  4. nothing durable — the filter lived in session scratch, unreviewed and
     lost with the session.

This script closes those gaps: one process discovers the seats (and, when no
--seats list pins them, keeps re-discovering, so a seat created mid-run gets
a watcher at the next rescan), follows each seat's newest transcript across
rollovers, and emits one compact line per event to stdout, for a monitor
process or a human terminal. Relates to issue 36 (mutual oversight).

Output contract — one stdout line per event, flushed immediately:

  <seat> AGENT: <text>       assistant display text, first 250 chars
  <seat> USER: <text>        a user-side text, first 250 chars; texts whose
                             stripped form starts with "<" (command wrappers,
                             system reminders) or "[SYSTEM" (task/monitor
                             notifications) are skipped, and tool results are
                             never emitted
  <seat> CMD: <command>      a Bash tool call matching the risky-command
                             pattern (pushes, merges, PR/issue writes,
                             destructive git, rm -rf), first 200 chars
  <seat> MSG→<to>: <text>    a SendMessage tool call, first 150 chars
  <seat> API-ERROR           an entry flagged isApiErrorMessage
  <seat> WATCH: ...          the watcher's own state: "no transcript found"
                             (once per disappearance, then it keeps polling),
                             "following <file>" on a seat's first acquisition
                             mid-run, or "switched to <file>" on rollover

Newlines inside a snippet become " ¶ ". Thinking blocks are never emitted;
unparseable records are skipped silently. --snippet-chars scales the
AGENT/USER length; CMD stays 200 and MSG stays 150.

Transcripts being followed at startup begin at end-of-file (--from-start
reads them whole); a transcript acquired after startup — a rollover, or a
seat's first transcript appearing — is read from byte 0, so the successor
session's boot is caught. But a transcript this run has followed before is
resumed at the offset it left off at, never byte 0 again: when two live
sessions share one project directory the newest-by-mtime rule alternates
between their files, and re-reading from byte 0 at every switch-back would
replay the seat's whole history as if it were happening now. Before
switching away from a file the watcher gives it one final read and flushes
any lines completed on disk; a final line still unterminated at that moment
is dropped — an accepted limitation, not a solved one. Only files named
like a session UUID (<8-4-4-4-12 hex>.jsonl) are candidates: anything else
in a project directory — subagent/sidecar transcripts live under
<project-dir>/<session-uuid>/subagents/ in the current layout, and the
directory may hold other non-session entries — must never be followed.

The seat whose directory contains this process's working directory is always
excluded (--include-self overrides): watching yourself is a feedback loop —
the watcher's own output lands in its session transcript as notification
entries and would be re-emitted, without bound. A second guard, the
"[SYSTEM" skip above, breaks the same loop at the text level.

See also: scripts/handoff-extract-conversation.py — the batch/deep
extraction tool that pulls the reviewed two-voice dialog out of one finished
transcript, where this script streams live events across many. They share no
code on purpose; each stays small enough to read whole.

Usage:
  scripts/watch-agent-dialogs.py [--agents-root DIR] [--seats a,b,c]
      [--include-self] [--from-start] [--rescan-seconds N] [--poll-seconds N]
      [--snippet-chars N] [--projects-root DIR]

Exit codes: 0 clean exit (the consumer closed the pipe), 2 bad invocation,
130 interrupted.
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

PROJECTS_ROOT = Path.home() / ".claude" / "projects"

# Session transcripts only. Subagent/sidecar transcripts live under
# <project-dir>/<session-uuid>/subagents/ in the current layout, but the
# name guard stays: it keeps the follower off directories and off any other
# non-session file a project directory may grow, so a stray sidecar can
# never speak in the seat's own voice.
SESSION_TRANSCRIPT_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.jsonl$")

# Bash commands worth surfacing: anything that pushes, merges, writes to
# PRs/issues, or destroys work. Everything else is noise at watch altitude.
#
# Option tokens may sit between `git` and its subcommand (`git -C <path>
# push`, `git --git-dir=... push`). A short option's separate argument must
# not itself start with a dash: `-C`'s path never does, and without that
# guard a run of dash tokens parses ambiguously and backtracks explosively.
_GIT_OPTION_TOKENS = r"""
    (?:
        \s+ -[a-zA-Z] \s+ (?!-)\S+     # short option with separate argument: -C <path>
      | \s+ --[^\s=]+ (?: = \S+ )?     # long option, with or without =value
      | \s+ -\S+                       # any other single-token flag cluster
    )*
"""
RISKY_COMMAND_PATTERN = re.compile(rf"""
    git {_GIT_OPTION_TOKENS} \s+
        (?: push | merge | reset\s+--hard | worktree\s+remove | branch\s+-[dD] )
  | gh \s+ pr \s+ (?: merge | close | create | comment | edit | review )
  | gh \s+ issue \s+ (?: create | edit | comment | close )
  | rm \s+ (?= (?:-[a-zA-Z]+\s+)* -[a-zA-Z]*r )  # some leading flag cluster has r
           (?= (?:-[a-zA-Z]+\s+)* -[a-zA-Z]*f )  # ... and some has f: -rf, -fr,
                                                 # -r -f, -f -r; never -f alone
""", re.VERBOSE)

CMD_SNIPPET_CHARS = 200
MSG_SNIPPET_CHARS = 150


def emit(line):
    """One event, one line, flushed now — a monitor pipes this, and a
    buffered line is a silent death."""
    print(line, flush=True)


def project_directory_for_seat(seat_path, projects_root):
    """The ~/.claude/projects directory holding a seat's session transcripts.

    The harness mangles the seat's absolute path by replacing every character
    outside ASCII [a-zA-Z0-9] with a dash — underscores included (probed
    against harness v2.1.233 with a real session: a directory named
    mangle_probe got the project directory suffix -mangle-probe, and
    /a/.claude/b becomes -a--claude-b).
    """
    mangled = re.sub(r"[^a-zA-Z0-9]", "-", str(seat_path.resolve()))
    return projects_root / mangled


def one_line_snippet(text, limit):
    """Newlines folded to " ¶ " first, then the first `limit` characters —
    fold-then-truncate, so the emitted length is bounded by `limit`."""
    return " ¶ ".join(text.strip().splitlines())[:limit]


def event_lines(seat_name, raw_record, snippet_chars):
    """Yield the output lines for one raw transcript record (bytes).

    Unparseable or unrecognized records yield nothing: the transcript is
    written by a live process and its schema drifts, so the watcher's
    stance is "emit what matches, skip the rest silently".
    """
    try:
        entry = json.loads(raw_record.decode("utf-8", errors="replace"))
    except (json.JSONDecodeError, ValueError):
        return
    if not isinstance(entry, dict):
        return

    if entry.get("isApiErrorMessage") is True:
        yield f"{seat_name} API-ERROR"
        return

    message = entry.get("message")
    content = message.get("content") if isinstance(message, dict) else None

    if entry.get("type") == "assistant" and isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text":
                text = block.get("text")
                if isinstance(text, str) and text.strip():
                    yield f"{seat_name} AGENT: {one_line_snippet(text, snippet_chars)}"
            elif block_type == "tool_use":
                tool_input = block.get("input")
                if not isinstance(tool_input, dict):
                    continue
                if block.get("name") == "Bash":
                    command = tool_input.get("command")
                    if isinstance(command, str) and RISKY_COMMAND_PATTERN.search(command):
                        yield (f"{seat_name} CMD: "
                               f"{one_line_snippet(command, CMD_SNIPPET_CHARS)}")
                elif block.get("name") == "SendMessage":
                    to = tool_input.get("to", "?")
                    text = tool_input.get("message")
                    if not isinstance(text, str):
                        text = ""  # a missing or non-string message is never
                        # shown as a repr; the "to" alone still surfaces
                    yield (f"{seat_name} MSG→{to}: "
                           f"{one_line_snippet(text, MSG_SNIPPET_CHARS)}")
            # "thinking" and every other block type: never emitted.

    elif entry.get("type") == "user":
        if isinstance(content, str):
            texts = [content]
        elif isinstance(content, list):
            # tool_result blocks are skipped entirely — only text blocks speak.
            texts = [block.get("text") for block in content
                     if isinstance(block, dict) and block.get("type") == "text"]
        else:
            texts = []
        for text in texts:
            if not isinstance(text, str):
                continue
            stripped = text.strip()
            # "<" catches command wrappers and system reminders; "[SYSTEM"
            # catches task/monitor notifications — the second layer of the
            # self-watch loop guard.
            if not stripped or stripped.startswith("<") or stripped.startswith("[SYSTEM"):
                continue
            yield f"{seat_name} USER: {one_line_snippet(text, snippet_chars)}"


class SeatFollower:
    """Follow one seat's newest session transcript across rollovers.

    Every file followed this run keeps its offset in followed_offsets, so
    when the newest-by-mtime rule alternates between two live transcripts,
    switching back resumes where that file left off instead of replaying it
    from byte 0. A partial line pending at switch-away time is dropped (see
    the module docstring); the final read just before switching keeps that
    loss to genuinely unterminated lines.
    """

    def __init__(self, seat_path, projects_root, snippet_chars):
        self.seat_name = seat_path.name
        self.project_directory = project_directory_for_seat(seat_path, projects_root)
        self.snippet_chars = snippet_chars
        self.transcript_path = None
        self.handle = None
        self.offset = 0
        self.pending = b""
        self.missing_announced = False
        self.followed_offsets = {}  # path -> offset reached while following it
        self.last_followed_path = None  # survives _close, unlike transcript_path

    def newest_candidate(self):
        try:
            entries = list(self.project_directory.iterdir())
        except OSError:
            return None
        newest, newest_mtime = None, None
        for path in entries:
            if not SESSION_TRANSCRIPT_PATTERN.match(path.name):
                continue
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue  # deleted between listing and stat
            if newest_mtime is None or mtime > newest_mtime:
                newest, newest_mtime = path, mtime
        return newest

    def rescan(self, at_startup=False, from_start=False):
        """Point the follower at the seat's newest transcript, if it moved."""
        newest = self.newest_candidate()
        if newest is None:
            if not self.missing_announced:
                emit(f"{self.seat_name} WATCH: no transcript found")
                self.missing_announced = True
            self._close()
            return
        self.missing_announced = False
        if self.transcript_path is not None and newest == self.transcript_path:
            return
        # Rollover: one final read of the file being left, so lines already
        # complete on disk are flushed before the switch.
        if self.handle is not None:
            self.poll()
        if not at_startup:
            if self.last_followed_path is None:
                emit(f"{self.seat_name} WATCH: following {newest.name}")
            elif newest != self.last_followed_path:
                emit(f"{self.seat_name} WATCH: switched to {newest.name}")
            # else: the same file reacquired after a transient reopen
            # failure — nothing changed worth announcing.
        try:
            # A file followed earlier this run resumes at its remembered
            # offset; a genuinely new one starts at byte 0 (or, at startup
            # without --from-start, at end-of-file).
            self._open(newest, start_at_end=at_startup and not from_start,
                       resume_offset=self.followed_offsets.get(newest))
        except OSError:
            self._close()  # vanished under us; the next rescan retries

    def poll(self):
        """Emit whatever grew since the last poll; heal truncation/replacement."""
        if self.handle is None:
            return
        try:
            on_disk = os.stat(self.transcript_path)
        except OSError:
            return  # gone right now; the next rescan decides the successor
        if (on_disk.st_ino != os.fstat(self.handle.fileno()).st_ino
                or on_disk.st_size < self.offset):
            # Replaced or truncated: reopen by path and read it whole. The
            # remembered offset is stale for this new content, so no resume.
            reopen_path = self.transcript_path
            self._close()
            try:
                self._open(reopen_path, start_at_end=False)
            except OSError:
                return
        self.handle.seek(self.offset)
        grown = self.handle.read()
        if not grown:
            return
        self.offset += len(grown)
        self.pending += grown
        # The final fragment may be a partial write; hold it for next poll.
        *complete_records, self.pending = self.pending.split(b"\n")
        for raw_record in complete_records:
            for line in event_lines(self.seat_name, raw_record, self.snippet_chars):
                emit(line)

    def _open(self, path, start_at_end, resume_offset=None):
        self._close()
        self.handle = open(path, "rb")
        self.transcript_path = path
        self.last_followed_path = path
        if start_at_end:
            self.offset = self.handle.seek(0, os.SEEK_END)
        elif resume_offset is not None:
            self.offset = resume_offset
        else:
            self.offset = 0
        self.followed_offsets[path] = self.offset
        self.pending = b""

    def _close(self):
        if self.transcript_path is not None:
            # Remember how far this file was read, so reacquiring it later
            # this run resumes here instead of replaying from byte 0.
            self.followed_offsets[self.transcript_path] = self.offset
        if self.handle is not None:
            self.handle.close()
        self.handle = None
        self.transcript_path = None
        self.offset = 0
        self.pending = b""


def default_agents_root() -> Path:
    """${NEDSCHORUS_AGENTS_ROOT:-~/agents}, as both launchers resolve it —
    the same read as recover-crashed-seats.py's and resupervise-seat.py's
    same-named twins. A watcher resolving the root differently on a machine
    where that variable is set iterates a directory no seat lives in and
    watches nothing, silently and forever (user-ruled 2026-08-22: allowed
    overrides must work)."""
    return Path(os.environ.get("NEDSCHORUS_AGENTS_ROOT") or "~/agents").expanduser()


def parse_arguments(argv):
    parser = argparse.ArgumentParser(
        description="Follow every fleet seat's live session transcript, "
                    "one compact stdout line per event.")
    parser.add_argument("--agents-root", default=str(default_agents_root()),
                        help="directory whose subdirectories are the seats "
                             "(default $NEDSCHORUS_AGENTS_ROOT, else ~/agents)")
    parser.add_argument("--seats", default=None,
                        help="comma-separated seat names to watch; default: "
                             "every subdirectory of the agents root, "
                             "re-discovered at each rescan")
    parser.add_argument("--include-self", action="store_true",
                        help="also watch the seat containing this process's "
                             "working directory (normally excluded — "
                             "self-watch is a feedback loop)")
    parser.add_argument("--from-start", action="store_true",
                        help="read transcripts found at startup from the "
                             "beginning instead of from end-of-file")
    parser.add_argument("--rescan-seconds", type=float, default=15.0,
                        help="how often to look for newer transcripts and "
                             "new seats (default: 15)")
    parser.add_argument("--poll-seconds", type=float, default=0.5,
                        help="how often to poll followed files for growth "
                             "(default: 0.5)")
    parser.add_argument("--snippet-chars", type=int, default=250,
                        help="AGENT/USER snippet length (default: 250; "
                             "CMD stays 200 and MSG stays 150)")
    parser.add_argument("--projects-root", default=str(PROJECTS_ROOT),
                        help="where session transcripts live (default: "
                             "~/.claude/projects; the tests point this at "
                             "a fixture directory)")
    return parser.parse_args(argv)


def main(argv=None):
    arguments = parse_arguments(argv)
    if arguments.poll_seconds <= 0:
        print("watch-agent-dialogs: --poll-seconds must be > 0", file=sys.stderr)
        return 2
    if arguments.rescan_seconds <= 0:
        print("watch-agent-dialogs: --rescan-seconds must be > 0", file=sys.stderr)
        return 2
    if arguments.snippet_chars < 1:
        print("watch-agent-dialogs: --snippet-chars must be >= 1", file=sys.stderr)
        return 2
    agents_root = Path(arguments.agents_root).expanduser()
    projects_root = Path(arguments.projects_root).expanduser()
    named_seats = None
    if arguments.seats is not None:
        named_seats = [name.strip() for name in arguments.seats.split(",")
                       if name.strip()]
        if not named_seats:
            print("watch-agent-dialogs: --seats named nobody", file=sys.stderr)
            return 2

    working_directory = Path.cwd().resolve()

    def seat_paths_now():
        if named_seats is not None:
            return [agents_root / name for name in named_seats]
        try:
            return sorted((path for path in agents_root.iterdir() if path.is_dir()),
                          key=lambda path: path.name)
        except OSError:
            return []

    def is_self_seat(seat_path):
        resolved = seat_path.resolve()
        return resolved == working_directory or resolved in working_directory.parents

    # Snippets can carry any text; never let one unencodable character kill
    # the watcher.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    followers = {}

    def adopt_new_seats(at_startup):
        for seat_path in seat_paths_now():
            if not arguments.include_self and is_self_seat(seat_path):
                continue
            key = str(seat_path.resolve())
            if key not in followers:
                followers[key] = SeatFollower(seat_path, projects_root,
                                              arguments.snippet_chars)
                followers[key].rescan(at_startup=at_startup,
                                      from_start=arguments.from_start)

    adopt_new_seats(at_startup=True)
    if named_seats is not None and not followers:
        print("watch-agent-dialogs: every named seat was excluded "
              "(self-watch? see --include-self)", file=sys.stderr)
        return 2
    if not followers:
        print(f"watch-agent-dialogs: no seats under {agents_root} yet; "
              "watching for arrivals", file=sys.stderr)

    def followers_in_order():
        return sorted(followers.values(), key=lambda follower: follower.seat_name)

    next_rescan = time.monotonic() + arguments.rescan_seconds
    while True:
        if time.monotonic() >= next_rescan:
            adopt_new_seats(at_startup=False)
            for follower in followers_in_order():
                follower.rescan()
            next_rescan = time.monotonic() + arguments.rescan_seconds
        for follower in followers_in_order():
            follower.poll()
        time.sleep(arguments.poll_seconds)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except BrokenPipeError:
        # The consumer closed the pipe; die quietly, not with a traceback.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)
