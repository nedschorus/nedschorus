"""Find the log-store's mirrored session transcripts and write the session dialog of each one that changed.

Not a program to run: scripts/log-store-session-dialogs-refresh-nbd.py, the
cron job, and scripts/log-store-past-discussions-regex-search-newest-first.py,
the past-discussion search, load it, so both write a session dialog the same
way and leave it current by the same rule.

A transcript is at

  <store>/agent-session-files-by-machine/<machine>/projects/<project-key>/<session-id>.jsonl

and its session dialog at

  <store>/session-dialogs/<machine>/<project-key>/<session-id>-dialog-complete.md

A dialog is current when it exists and its modification time equals its
transcript's change time (st_ctime): each dialog written is given, as its
modification time, its transcript's change time as read before the
transcript was read, so a transcript that grows while it is read is written
again next time.

Both programs may write the same dialog at once. Each writes through a
temporary file named with its process id and renames it over the dialog, so
a reader never sees half a dialog and the two never write into one temporary
file. When the two race, the rename that lands last wins; if that is the
older text, it carries the older change time, so the next writer finds it
not current and writes it again.

A dialog that is current by its change time was written by the extractor and
subagent tracker whose digest, load_extractor's, the refresher last recorded
in <store>/session-dialogs/EXTRACTOR_SHA256_FILE_NAME, unless a writer with
another extractor stamped it. So the search writes a dialog only when its own
digest equals the recorded one, and never one that leaves out the subagent
turns: either would stand as current until the next extractor change.

The recorded digest is kept only after a pass that wrote every dialog, so
while a pass with a changed extractor runs, or after one that failed partway,
the dialogs are of two digests under one record. So each dialog's last line
names the digest that wrote it, as session_dialog_extractor_sha256_last_line_build says, and the
search dates a dialog's hits by their turns only when that digest is its own.
"""

import hashlib
import os
import pathlib
import stat
import sys
import types

AGENT_SESSION_FILES_FOLDER_IN_LOG_STORE = "agent-session-files-by-machine"
SESSION_DIALOGS_DIRECTORY_NAME = "session-dialogs"
SESSION_DIALOG_FILE_NAME_SUFFIX = "-dialog-complete.md"
EXTRACTOR_SHA256_FILE_NAME = ".dialogs-written-by-extractor-sha256"
SESSION_DIALOG_EXTRACTOR_SHA256_LAST_LINE_OPENING = "<!-- written by the session dialog extractor whose sha256 is "
SESSION_DIALOG_EXTRACTOR_SHA256_LAST_LINE_CLOSING = " -->"
EXTRACTOR_PATH = pathlib.Path(__file__).resolve().with_name("handoff-extract-conversation.py")
SUBAGENT_TRACKER_PATHS = (
    pathlib.Path(__file__).resolve().with_name("handoff-extract-conversation-subagent-tracker-nbd.py"),
    pathlib.Path(__file__).resolve().with_name("claude-code-subagent-task-notification-interim-recognizer-common.py"))


class SubagentTurnsLeftOut(Exception):
    """The subagent tracker failed while a dialog was rendered, so the dialog was not written."""


def load_extractor():
    """Return (the extractor module, the sha256 of its bytes, its subagent tracker's files' and this file's,
    (path, error) or None).

    This file is in the digest because it writes the digest line into each dialog. The tracker's files are
    SUBAGENT_TRACKER_PATHS; (path, error) names the first that cannot be read. When one cannot be read, all count
    as empty in the digest: the extractor then writes each dialog without subagent turns and says so in it, which
    beats leaving every dialog stale.
    """
    # One read for both, so a change to the file during a pass cannot pair old code with the new digest.
    source = EXTRACTOR_PATH.read_bytes()
    module = types.ModuleType("handoff_extract_conversation")
    module.__file__ = str(EXTRACTOR_PATH)
    sys.modules[module.__name__] = module
    exec(compile(source, str(EXTRACTOR_PATH), "exec"), module.__dict__)
    tracker_source, tracker_failure = b"", None
    for path in SUBAGENT_TRACKER_PATHS:
        try:
            tracker_source += path.read_bytes()
        except OSError as error:
            tracker_source, tracker_failure = b"", (path, error)
            break
    this_file_source = pathlib.Path(__file__).resolve().read_bytes()
    return module, hashlib.sha256(source + tracker_source + this_file_source).hexdigest(), tracker_failure


def session_dialog_extractor_sha256_last_line_build(extractor_sha256: str) -> str:
    """The line ending each session dialog written here, naming the digest of the extractor that wrote it."""
    return SESSION_DIALOG_EXTRACTOR_SHA256_LAST_LINE_OPENING + extractor_sha256 + SESSION_DIALOG_EXTRACTOR_SHA256_LAST_LINE_CLOSING


def session_dialog_extractor_sha256_read_from_last_line(dialog_lines) -> str:
    """The digest the dialog's last line names, or "" when that line is not a digest line."""
    opening, closing = SESSION_DIALOG_EXTRACTOR_SHA256_LAST_LINE_OPENING, SESSION_DIALOG_EXTRACTOR_SHA256_LAST_LINE_CLOSING
    last = next((line for line in reversed(dialog_lines) if line.strip()), "")
    if last.startswith(opening) and last.endswith(closing):
        return last[len(opening):-len(closing)]
    return ""


def sorted_entries(directory: pathlib.Path, unreadable: list):
    """Return the directory's entries, sorted, or none, adding (directory, error) to unreadable when it cannot be listed."""
    # Path.glob skips a directory it cannot list without saying so, which would leave its sessions undialogued unseen.
    try:
        return sorted(directory.iterdir())
    except OSError as error:
        unreadable.append((directory, error))
        return []


def is_of_kind(path: pathlib.Path, kind_test, unreadable: list) -> bool:
    """Return whether path exists and passes kind_test, adding (path, error) to unreadable when it cannot be examined."""
    # Path.is_dir and Path.is_file answer False on a permission error, which would skip a directory in silence.
    try:
        return kind_test(path.stat().st_mode)
    except FileNotFoundError:
        return False
    except OSError as error:
        unreadable.append((path, error))
        return False


def find_session_transcripts_mirrored_in_log_store(transcripts_directory: pathlib.Path, unreadable: list):
    """Yield (machine, project key, transcript path) for every mirrored session transcript.

    Each directory or file on the way that cannot be listed or examined is added to unreadable as (path, error).
    The subagents' own transcripts, a level deeper, are not yielded.
    """
    for machine_directory in sorted_entries(transcripts_directory, unreadable):
        projects_directory = machine_directory / "projects"
        if not is_of_kind(projects_directory, stat.S_ISDIR, unreadable):
            continue
        for project_directory in sorted_entries(projects_directory, unreadable):
            if not is_of_kind(project_directory, stat.S_ISDIR, unreadable):
                continue
            for transcript in sorted_entries(project_directory, unreadable):
                if transcript.suffix == ".jsonl" and is_of_kind(transcript, stat.S_ISREG, unreadable):
                    yield machine_directory.name, project_directory.name, transcript


def session_dialog_path_for_transcript(dialogs_directory: pathlib.Path, machine: str, project_key: str,
                        transcript: pathlib.Path) -> pathlib.Path:
    return dialogs_directory / machine / project_key / f"{transcript.stem}{SESSION_DIALOG_FILE_NAME_SUFFIX}"


def write_text_through_temporary_file(path: pathlib.Path, text: str, modification_time_ns: int) -> None:
    """Write text to path whole, with the given modification time; any failure raises."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.partial")
    temporary.write_text(text, encoding="utf-8")
    os.utime(temporary, ns=(modification_time_ns, modification_time_ns))
    os.replace(temporary, path)


def refresh_session_dialog_file_unless_current_with_transcript(extractor, extractor_sha256: str,
                                                               extractor_unchanged: bool,
                                                               transcript: pathlib.Path, dialog: pathlib.Path,
                                                               refuse_without_subagent_turns=False) -> bool:
    """Write the transcript's session dialog unless it is current and extractor_unchanged; return whether written.

    extractor is scripts/handoff-extract-conversation.py, loaded, and extractor_sha256 load_extractor's digest of
    it, which the dialog's last line names. With refuse_without_subagent_turns, a dialog the
    subagent tracker failed on is not written and SubagentTurnsLeftOut raises. Any other failure raises too.
    """
    transcript_changed = transcript.stat().st_ctime_ns
    if extractor_unchanged and dialog.exists() and dialog.stat().st_mtime_ns == transcript_changed:
        return False
    turns, report = extractor.complete_dialog_turns_and_report(transcript)
    left_out = extractor.turns_left_out_notes(turns)
    if refuse_without_subagent_turns and left_out:
        raise SubagentTurnsLeftOut(left_out[0]["text"])
    text = (extractor.render_companion(turns, report) + "\n\n"
            + session_dialog_extractor_sha256_last_line_build(extractor_sha256) + "\n")
    write_text_through_temporary_file(dialog, text, transcript_changed)
    return True
