#!/usr/bin/env python3
"""Keep every session's complete filtered dialog current in the log-store, beside the transcripts.

Usage:
  scripts/log-store-session-dialogs-refresh.py                   # one pass, a summary line
  scripts/log-store-session-dialogs-refresh.py --failures-only   # one pass, only FAILED lines (cron)

WHAT IT READS AND WRITES. It runs on ned-box, where the log-store is. The
transcript mirror (scripts/transcript-mirror-to-log-store.py) copies each
machine's session transcripts into the store every minute, so both machines'
sessions are already on ned-box's disk:

  /home/nedlern/nedschorus-logs/transcripts/<machine>/projects/<project-key>/<session-id>.jsonl

For each of those transcripts that changed since its dialog was written, this
program writes the session's complete filtered dialog, the form the handoff
extractor (scripts/handoff-extract-conversation.py) writes as
`<seat>-dialog-NNNN-complete.md`, subagent tasks and reports included, to

  /home/nedlern/nedschorus-logs/session-dialogs/<machine>/<project-key>/<session-id>-dialog-complete.md

overwriting the earlier one, so a running session's dialog is never more than
one pass behind its transcript, and an ended session's dialog is there whether
or not a handoff wrote one. The subagents' own transcripts under
`<session-id>/subagents/` are read only through the session's own records.

WHEN A DIALOG IS WRITTEN. When there is none yet, when its modification
time differs from its transcript's, or when the extractor has changed since
the last pass that wrote every dialog it needed to. Each dialog written is
given its transcript's modification time as read before the transcript was
read, so a transcript that grows while it is being read, or whose growth
reaches the mirror late, is written again on the next pass, and an unchanged
one is never read twice. rsync -a keeps each transcript's own time, which is
what makes the comparison hold across the mirror. The extractor is known by
the sha256 of its bytes, kept in session-dialogs/ after each pass that had no
failure; a pass that finds another extractor rewrites every dialog, so one
change to the extractor rewrites every dialog once. A transcript with no
dialog in it still gets a dialog, one saying it holds no turns, so it is not
read again until it changes.

OUTPUT AND FAILURE. A transcript that cannot be read, a directory or file on
the way to the transcripts that cannot be listed or examined, or a dialog that cannot be written, prints
a line opening FAILED naming the path and the error, and the pass goes on to
the next; the exit is then 1. A store with no
transcripts/ directory is FAILED too: on ned-box that means the store is not
where this program looks. Without --failures-only a pass ends with one line
counting the dialogs written, the ones already current, and the failures.
Exit 0 when nothing failed, 1 when anything did, 3 when another run holds the
lock, which happens only when a pass outlasts the schedule; that run then
exits quietly under --failures-only. Measured on ned-box over the store's
2,854 transcripts, the first pass, which reads them all, took 18 seconds and
60 MB of memory and wrote 88 MB of dialogs; the pass after it, which read
only the 13 transcripts written in between, took 0.2 seconds.

SCHEDULE. Every 10 minutes, by cron on ned-box only, installed by
nc-systems/general-tools/install-scheduled-jobs-on-this-machine.py from the
table beside that program:

  ned-box: */10 * * * * /usr/bin/python3 /home/nedlern/Projects/nedschorus/scripts/log-store-session-dialogs-refresh.py --failures-only >> /home/nedlern/.claude/log-store-session-dialogs-refresh.log 2>&1

LOG_STORE_SESSION_DIALOGS_REFRESH_LOG_STORE_ROOT_OVERRIDE in the environment overrides the
store's root for the tests, which point it at a scratch directory.
"""

import argparse
import fcntl
import hashlib
import os
import pathlib
import stat
import sys
import types

PROGRAM = "log-store-session-dialogs-refresh"
LOG_STORE_ROOT = "/home/nedlern/nedschorus-logs"
STORE_ROOT_ENVIRONMENT_VARIABLE = "LOG_STORE_SESSION_DIALOGS_REFRESH_LOG_STORE_ROOT_OVERRIDE"
TRANSCRIPTS_DIRECTORY_NAME = "transcripts"
SESSION_DIALOGS_DIRECTORY_NAME = "session-dialogs"
SESSION_DIALOG_SUFFIX = "-dialog-complete.md"
LOCK_FILE_NAME = ".log-store-session-dialogs-refresh.lock"
EXTRACTOR_SHA256_FILE_NAME = ".dialogs-written-by-extractor-sha256"
EXTRACTOR_PATH = pathlib.Path(__file__).resolve().with_name("handoff-extract-conversation.py")

EXIT_REFRESHED = 0
EXIT_FAILED = 1
EXIT_LOCKED = 3


def load_extractor():
    """Return (the extractor module, the sha256 of the bytes it was built from)."""
    # One read for both, so a change to the file during a pass cannot pair old code with the new digest.
    source = EXTRACTOR_PATH.read_bytes()
    module = types.ModuleType("handoff_extract_conversation")
    module.__file__ = str(EXTRACTOR_PATH)
    sys.modules[module.__name__] = module
    exec(compile(source, str(EXTRACTOR_PATH), "exec"), module.__dict__)
    return module, hashlib.sha256(source).hexdigest()


def store_root() -> pathlib.Path:
    return pathlib.Path(os.environ.get(STORE_ROOT_ENVIRONMENT_VARIABLE) or LOG_STORE_ROOT)


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


def session_transcripts(transcripts_directory: pathlib.Path, unreadable: list):
    """Yield (machine, project key, transcript path) for every mirrored session transcript.

    Each directory or file on the way that cannot be listed or examined is added to unreadable as (path, error).
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


def refresh_one(extractor, extractor_unchanged: bool, transcript: pathlib.Path, dialog: pathlib.Path) -> bool:
    """Write the transcript's dialog unless it exists, carries the transcript's time, and the extractor is unchanged.

    Return whether it was written.
    """
    transcript_modified = transcript.stat().st_mtime_ns
    if extractor_unchanged and dialog.exists() and dialog.stat().st_mtime_ns == transcript_modified:
        return False
    text = extractor.render_complete_dialog_of_transcript_as_markdown(transcript)
    dialog.parent.mkdir(parents=True, exist_ok=True)
    partial = dialog.with_name(dialog.name + ".partial")
    partial.write_text(text, encoding="utf-8")
    os.utime(partial, ns=(transcript_modified, transcript_modified))
    os.replace(partial, dialog)
    return True


def refresh_all(root: pathlib.Path, failures_only: bool) -> int:
    transcripts_directory = root / TRANSCRIPTS_DIRECTORY_NAME
    if not transcripts_directory.is_dir():
        print(f"FAILED: no {transcripts_directory} directory to read transcripts from; "
              "scripts/transcript-mirror-to-log-store.py creates it on its first pass")
        return EXIT_FAILED
    extractor, extractor_sha256 = load_extractor()
    dialogs_directory = root / SESSION_DIALOGS_DIRECTORY_NAME
    extractor_sha256_file = dialogs_directory / EXTRACTOR_SHA256_FILE_NAME
    try:
        extractor_unchanged = extractor_sha256_file.read_text(encoding="utf-8").strip() == extractor_sha256
    except OSError:
        # Unknown counts as changed: every dialog is rewritten, and the write below reports a file it cannot keep.
        extractor_unchanged = False
    written = current = failed = 0
    unreadable = []
    for machine, project_key, transcript in session_transcripts(transcripts_directory, unreadable):
        dialog = dialogs_directory / machine / project_key / f"{transcript.stem}{SESSION_DIALOG_SUFFIX}"
        try:
            if refresh_one(extractor, extractor_unchanged, transcript, dialog):
                written += 1
            else:
                current += 1
        except Exception as error:
            # One unreadable transcript must not keep every other session's dialog stale.
            failed += 1
            print(f"FAILED: {transcript} — {type(error).__name__}: {error}")
    for path, error in unreadable:
        failed += 1
        print(f"FAILED: cannot read {path}, so the sessions under it get no dialog — "
              f"{type(error).__name__}: {error}; make it readable and searchable by this user")
    if not failed and not extractor_unchanged:
        # Kept only after a pass with no failure, so a dialog the new extractor could not write is retried.
        try:
            extractor_sha256_file.write_text(extractor_sha256 + "\n", encoding="utf-8")
        except OSError as error:
            failed += 1
            print(f"FAILED: could not record the extractor's sha256 in {extractor_sha256_file}, so the next "
                  f"pass rewrites every dialog again — {type(error).__name__}: {error}")
    if not failures_only:
        print(f"{PROGRAM}: wrote {written} session dialogs, {current} already current, "
              f"{failed} failed, under {dialogs_directory}")
    return EXIT_FAILED if failed else EXIT_REFRESHED


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Keep every session's complete filtered dialog current in the log-store.")
    parser.add_argument("--failures-only", action="store_true",
                        help="print FAILED lines only, for cron")
    failures_only = parser.parse_args(argv).failures_only
    root = store_root()
    dialogs_directory = root / SESSION_DIALOGS_DIRECTORY_NAME
    try:
        dialogs_directory.mkdir(parents=True, exist_ok=True)
        lock = (dialogs_directory / LOCK_FILE_NAME).open("w")
    except OSError as error:
        print(f"FAILED: could not prepare {dialogs_directory} ({error})")
        return EXIT_FAILED
    with lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            if not failures_only:
                print(f"{PROGRAM}: another run holds {dialogs_directory / LOCK_FILE_NAME}; "
                      "leaving it to finish")
            return EXIT_LOCKED
        return refresh_all(root, failures_only)


if __name__ == "__main__":
    sys.exit(main())
