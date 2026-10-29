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
"""

import os
import pathlib
import stat

AGENT_SESSION_FILES_FOLDER_IN_LOG_STORE = "agent-session-files-by-machine"
SESSION_DIALOGS_DIRECTORY_NAME = "session-dialogs"
SESSION_DIALOG_FILE_NAME_SUFFIX = "-dialog-complete.md"


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


def refresh_session_dialog_unless_current(extractor, extractor_unchanged: bool, transcript: pathlib.Path,
                                        dialog: pathlib.Path) -> bool:
    """Write the transcript's session dialog unless it is current and extractor_unchanged; return whether written.

    extractor is scripts/handoff-extract-conversation.py, loaded. Any failure raises.
    """
    transcript_changed = transcript.stat().st_ctime_ns
    if extractor_unchanged and dialog.exists() and dialog.stat().st_mtime_ns == transcript_changed:
        return False
    text = extractor.render_complete_dialog_of_transcript_as_markdown(transcript)
    write_text_through_temporary_file(dialog, text, transcript_changed)
    return True
