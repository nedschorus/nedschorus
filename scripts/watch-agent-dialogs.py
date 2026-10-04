#!/usr/bin/env python3
"""Stream compact events from fleet seats' live transcripts across session rollovers."""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

PROJECTS_ROOT = Path.home() / ".claude" / "projects"

# Only session UUID filenames may speak for a seat; project directories can contain unrelated entries.
SESSION_TRANSCRIPT_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.jsonl$")

# A short option's separate argument must not start with a dash; ambiguous runs of dash tokens cause explosive backtracking.
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
    """Print and flush one event line."""
    print(line, flush=True)


def project_directory_for_seat(seat_path, projects_root):
    """Return the harness project directory for the seat."""
    # The harness replaces every non-ASCII-alphanumeric character, including underscores, with a dash.
    mangled = re.sub(r"[^a-zA-Z0-9]", "-", str(seat_path.resolve()))
    return projects_root / mangled


def one_line_snippet(text, limit):
    """Fold newlines to paragraph markers and return at most limit characters."""
    return " ¶ ".join(text.strip().splitlines())[:limit]


def event_lines(seat_name, raw_record, snippet_chars, resend_state=None):
    """Yield event lines from a raw transcript record, skipping unrecognized records.

    resend_state is a dict the caller keeps for one transcript, so that a queued
    message the harness re-sends after an interrupt is shown once."""
    if resend_state is None:
        resend_state = {}
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
                    resend_state.pop("queued_text", None)
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
                        text = ""
                    yield (f"{seat_name} MSG→{to}: "
                           f"{one_line_snippet(text, MSG_SNIPPET_CHARS)}")

    # A message the user types mid-turn has no user record, only this attachment;
    # the same shape carries peer and task messages, which origin.kind tells apart.
    elif entry.get("type") == "attachment":
        attachment = entry.get("attachment")
        if not isinstance(attachment, dict) or attachment.get("type") != "queued_command":
            return
        origin = attachment.get("origin")
        if not isinstance(origin, dict) or origin.get("kind") != "human":
            return
        prompt = attachment.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            return
        resend_state["queued_text"] = prompt.strip()
        resend_state["interrupted"] = False
        yield f"{seat_name} USER: {one_line_snippet(prompt, snippet_chars)}"

    elif entry.get("type") == "user":
        if isinstance(content, str):
            texts = [content]
        elif isinstance(content, list):
            texts = [block.get("text") for block in content
                     if isinstance(block, dict) and block.get("type") == "text"]
        else:
            texts = []
        for text in texts:
            if not isinstance(text, str):
                continue
            stripped = text.strip()
            if stripped.startswith("[Request interrupted"):
                resend_state["interrupted"] = True
            elif (resend_state.get("interrupted")
                    and stripped == resend_state.get("queued_text")):
                resend_state.pop("queued_text", None)
                continue
            else:
                resend_state.pop("queued_text", None)
            # Injected monitor notifications must be skipped to prevent self-watch feedback.
            if not stripped or stripped.startswith("<") or stripped.startswith("[SYSTEM"):
                continue
            yield f"{seat_name} USER: {one_line_snippet(text, snippet_chars)}"


class SeatFollower:
    """Follow a seat's newest transcript while preserving per-file offsets."""
    # Newest-by-mtime can alternate between two live sessions; retain each offset to avoid replay.
    # An unterminated line left at a switch is dropped.

    def __init__(self, seat_path, projects_root, snippet_chars):
        self.seat_name = seat_path.name
        self.project_directory = project_directory_for_seat(seat_path, projects_root)
        self.snippet_chars = snippet_chars
        self.transcript_path = None
        self.handle = None
        self.offset = 0
        self.pending = b""
        self.missing_announced = False
        self.followed_offsets = {}  # Offsets survive _close so switching back to a live transcript does not replay its history.
        self.last_followed_path = None
        self.resend_state = {}
        self.followed_resend_states = {}

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
                continue
            if newest_mtime is None or mtime > newest_mtime:
                newest, newest_mtime = path, mtime
        return newest

    def rescan(self, at_startup=False, from_start=False):
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
        # Read once before switching so completed lines in the old transcript are not lost.
        if self.handle is not None:
            self.poll()
        if not at_startup:
            if self.last_followed_path is None:
                emit(f"{self.seat_name} WATCH: following {newest.name}")
            elif newest != self.last_followed_path:
                emit(f"{self.seat_name} WATCH: switched to {newest.name}")
            # Reacquiring the same file after a transient failure is not a new session announcement.
        try:
            self._open(newest, start_at_end=at_startup and not from_start,
                       resume_offset=self.followed_offsets.get(newest))
        except OSError:
            self._close()

    def poll(self):
        """Emit newly appended events, recovering from truncation or replacement."""
        if self.handle is None:
            return
        try:
            on_disk = os.stat(self.transcript_path)
        except OSError:
            return
        if (on_disk.st_ino != os.fstat(self.handle.fileno()).st_ino
                or on_disk.st_size < self.offset):
            # Replacement or truncation invalidates the saved offset; reread the new content.
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
        # Hold an unterminated fragment until the writer completes it.
        *complete_records, self.pending = self.pending.split(b"\n")
        for raw_record in complete_records:
            for line in event_lines(self.seat_name, raw_record, self.snippet_chars,
                                    self.resend_state):
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
        # Resuming at a saved offset must also resume the re-send state, or a re-send after the switch prints twice.
        self.resend_state = (self.followed_resend_states.get(path, {})
                             if resume_offset is not None and not start_at_end else {})

    def _close(self):
        if self.transcript_path is not None:
            self.followed_offsets[self.transcript_path] = self.offset
            self.followed_resend_states[self.transcript_path] = self.resend_state
        if self.handle is not None:
            self.handle.close()
        self.handle = None
        self.transcript_path = None
        self.offset = 0
        self.pending = b""


def default_agents_root() -> Path:
    """Return the agents root, honoring NEDSCHORUS_AGENTS_ROOT as the Mac launcher does."""
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

    # Transcript text may contain characters stdout cannot encode; one snippet must not end the watch.
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
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)
