#!/usr/bin/env python3
"""Keep every session's complete filtered dialog current in the log-store, beside the transcripts.

Usage:
  scripts/log-store-session-dialogs-refresh-nbd.py                   # one pass, a summary line
  scripts/log-store-session-dialogs-refresh-nbd.py --failures-only   # one pass, only FAILED lines (cron)

WHAT IT READS AND WRITES. It runs on ned-box, where the log-store is. The
transcript mirror (scripts/transcript-mirror-to-log-store.py) copies each
machine's session transcripts into the store every minute, so both machines'
sessions are already on ned-box's disk:

  /home/nedlern/nedschorus-logs/agent-session-files-by-machine/<machine>/projects/<project-key>/<session-id>.jsonl

For each of those transcripts that changed since its dialog was written, this
program writes the session's complete filtered dialog, the form the handoff
extractor (scripts/handoff-extract-conversation.py) writes as
`<seat>-dialog-NNNN-complete.md`, subagent tasks and reports included, to

  /home/nedlern/nedschorus-logs/session-dialogs/<machine>/<project-key>/<session-id>-dialog-complete.md

overwriting the earlier one, so a running session's dialog is never more than
one pass behind its transcript, and an ended session's dialog is there whether
or not a handoff wrote one. The subagents' own transcripts under
`<session-id>/subagents/` are read only through the session's own records.
The past-discussion search
(scripts/log-store-past-discussions-regex-search-newest-first.py) also
writes, before it searches, each dialog whose transcript changed; both find
the transcripts and write a dialog with
scripts/log-store-session-dialogs-refresh-common.py, so the two
writers agree on what is current and never write into one temporary file.

WHEN A DIALOG IS WRITTEN. When there is none yet, when its modification
time differs from its transcript's change time (st_ctime), or when the
extractor has changed since the last pass that wrote every dialog it needed
to. Each dialog written is given, as its modification time, its transcript's
change time as read before the transcript was read, so a transcript that
grows while it is being read is written again on the next pass, and an
unchanged one is never read twice. The change time, not the modification
time, because the mirror keeps the Mac's modification times only to the
whole second, so a Mac transcript that grows again within the same second
keeps the same modification time; the change time is set by ned-box's own
file system whenever rsync puts a new copy in place. The extractor is known
by the sha256 of its bytes, its subagent tracker's
(scripts/handoff-extract-conversation-subagent-tracker-nbd.py) and those of
the module the tracker loads
(scripts/claude-code-subagent-task-notification-interim-recognizer-common.py),
kept in session-dialogs/ after each pass that had no failure; a pass that
finds any of the three files changed rewrites every dialog, so one change
rewrites every dialog once. A transcript with no dialog in it still gets a
dialog, one saying it holds no turns, so it is not read again until it
changes.

OUTPUT AND FAILURE. A transcript that cannot be read, a directory or file on
the way to the transcripts that cannot be listed or examined, or a dialog that cannot be written, prints
a line opening FAILED naming the path and the error, and the pass goes on to
the next; the exit is then 1. A session whose dialog could not be rewritten
also gets, as the first line of its dialog, a stale-dialog warning:

  This dialog could not be refreshed since <YYYY-MM-DD HH:MM> UTC: <error>; what follows may be out of date.

because the cron log the FAILED lines go to is read by no one, and the
reader of the dialog is the one the stale text would mislead. The warning
keeps the time the failure began across passes, is the whole dialog when
there was none before, and goes when a later pass rewrites the dialog. A
warned dialog is given modification time 0, which no transcript's change
time equals, so the next pass tries the transcript again. A store with no
agent-session-files-by-machine/ directory is FAILED too: on ned-box that means the store is not
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

  ned-box: */10 * * * * /usr/bin/python3 /home/nedlern/Projects/nedschorus/scripts/log-store-session-dialogs-refresh-nbd.py --failures-only >> /home/nedlern/.claude/log-store-session-dialogs-refresh.log 2>&1

LOG_STORE_SESSION_DIALOGS_REFRESH_LOG_STORE_ROOT_OVERRIDE in the environment overrides the
store's root for the tests, which point it at a scratch directory.
"""

import argparse
import datetime
import fcntl
import hashlib
import importlib.util
import os
import pathlib
import sys
import types

PROGRAM = "log-store-session-dialogs-refresh"
LOG_STORE_ROOT = "/home/nedlern/nedschorus-logs"
STORE_ROOT_ENVIRONMENT_VARIABLE = "LOG_STORE_SESSION_DIALOGS_REFRESH_LOG_STORE_ROOT_OVERRIDE"
LOCK_FILE_NAME = ".log-store-session-dialogs-refresh.lock"
EXTRACTOR_SHA256_FILE_NAME = ".dialogs-written-by-extractor-sha256"
STALE_DIALOG_WARNING_OPENING = "This dialog could not be refreshed since "
STALE_DIALOG_WARNING_TIME_FORMAT = "%Y-%m-%d %H:%M UTC"
EXTRACTOR_PATH = pathlib.Path(__file__).resolve().with_name("handoff-extract-conversation.py")
SUBAGENT_TRACKER_PATH = pathlib.Path(__file__).resolve().with_name(
    "handoff-extract-conversation-subagent-tracker-nbd.py")
SUBAGENT_TRACKER_PATHS = (
    SUBAGENT_TRACKER_PATH,
    pathlib.Path(__file__).resolve().with_name("claude-code-subagent-task-notification-interim-recognizer-common.py"))

_refresh_common_specification = importlib.util.spec_from_file_location(
    "log_store_session_dialogs_refresh_common",
    pathlib.Path(__file__).resolve().with_name("log-store-session-dialogs-refresh-common.py"))
refresh_common = importlib.util.module_from_spec(_refresh_common_specification)
_refresh_common_specification.loader.exec_module(refresh_common)

EXIT_REFRESHED = 0
EXIT_FAILED = 1
EXIT_LOCKED = 3


def load_extractor():
    """Return (the extractor module, the sha256 of its bytes and its subagent tracker's files', (path, error) or None).

    The tracker's files are SUBAGENT_TRACKER_PATHS; (path, error) names the first that cannot be read. When one
    cannot be read, all count as empty in the digest: the extractor then writes each dialog without subagent turns
    and says so in it, which beats leaving every dialog stale.
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
    return module, hashlib.sha256(source + tracker_source).hexdigest(), tracker_failure


def store_root() -> pathlib.Path:
    return pathlib.Path(os.environ.get(STORE_ROOT_ENVIRONMENT_VARIABLE) or LOG_STORE_ROOT)


def mark_dialog_stale(dialog: pathlib.Path, error: BaseException) -> None:
    """Put the stale-dialog warning first in the dialog, keeping the time an earlier warning gives; any failure raises."""
    try:
        text = dialog.read_text(encoding="utf-8")
    except FileNotFoundError:
        text = ""
    since = datetime.datetime.now(datetime.timezone.utc).strftime(STALE_DIALOG_WARNING_TIME_FORMAT)
    if text.startswith(STALE_DIALOG_WARNING_OPENING):
        first_line, _, text = text.partition("\n")
        since = first_line[len(STALE_DIALOG_WARNING_OPENING):].split(" UTC: ", 1)[0] + " UTC"
        text = text.removeprefix("\n")
    reason = " ".join(f"{type(error).__name__}: {error}".split())
    warning = f"{STALE_DIALOG_WARNING_OPENING}{since}: {reason}; what follows may be out of date.\n"
    # No change time is 0, so the next pass never takes a stale dialog for current, even within one timestamp tick.
    refresh_common.write_text_through_temporary_file(dialog, warning + ("\n" + text if text else ""), 0)


def refresh_all(root: pathlib.Path, failures_only: bool) -> int:
    transcripts_directory = root / refresh_common.AGENT_SESSION_FILES_FOLDER_IN_LOG_STORE
    if not transcripts_directory.is_dir():
        print(f"FAILED: no {transcripts_directory} directory to read transcripts from; "
              "scripts/transcript-mirror-to-log-store.py creates it on its first pass")
        return EXIT_FAILED
    extractor, extractor_sha256, tracker_failure = load_extractor()
    dialogs_directory = root / refresh_common.SESSION_DIALOGS_DIRECTORY_NAME
    extractor_sha256_file = dialogs_directory / EXTRACTOR_SHA256_FILE_NAME
    written = current = failed = 0
    if tracker_failure is not None:
        unreadable_tracker_path, tracker_error = tracker_failure
        # Counted as a failure, so the digest is not kept and every dialog is written again once the tracker is back.
        failed += 1
        print(f"FAILED: cannot read {unreadable_tracker_path}, so every dialog this pass writes leaves out its "
              f"subagent tasks and reports and says so — {type(tracker_error).__name__}: {tracker_error}")
        # The kept digest names the working tracker; without it the dialogs written now would pass for current later.
        try:
            extractor_sha256_file.unlink(missing_ok=True)
        except OSError as error:
            print(f"FAILED: could not remove {extractor_sha256_file}, so the dialogs this pass writes without "
                  f"subagent turns may not be written again when the tracker is back — {type(error).__name__}: {error}")
    try:
        extractor_unchanged = extractor_sha256_file.read_text(encoding="utf-8").strip() == extractor_sha256
    except FileNotFoundError:
        extractor_unchanged = False
    except OSError as error:
        # Unknown counts as changed, so every dialog is rewritten; failed also withholds the write below.
        extractor_unchanged = False
        failed += 1
        print(f"FAILED: cannot read {extractor_sha256_file}, so every dialog is rewritten on every pass — "
              f"{type(error).__name__}: {error}; make it a file readable and writable by this user, or remove it")
    unreadable = []
    for machine, project_key, transcript in refresh_common.find_session_transcripts_mirrored_in_log_store(
            transcripts_directory, unreadable):
        dialog = refresh_common.session_dialog_path_for_transcript(dialogs_directory, machine, project_key, transcript)
        try:
            if refresh_common.refresh_session_dialog_unless_current(extractor, extractor_unchanged, transcript, dialog):
                written += 1
            else:
                current += 1
        except Exception as error:
            # One unreadable transcript must not keep every other session's dialog stale.
            failed += 1
            print(f"FAILED: {transcript} — {type(error).__name__}: {error}")
            try:
                mark_dialog_stale(dialog, error)
            except Exception as marking_error:
                print(f"FAILED: could not warn in {dialog} that it is stale — "
                      f"{type(marking_error).__name__}: {marking_error}")
    for path, error in unreadable:
        failed += 1
        print(f"FAILED: cannot read {path}, so the sessions under it get no dialog — "
              f"{type(error).__name__}: {error}; make it readable by this user, and each directory on its path searchable")
    if not failed and not extractor_unchanged:
        # Kept only after a pass with no failure, so a dialog the new extractor could not write is retried.
        try:
            extractor_sha256_file.write_text(extractor_sha256 + "\n", encoding="utf-8")
        except OSError as error:
            failed += 1
            print(f"FAILED: could not record the extractor's sha256 in {extractor_sha256_file}, so the next "
                  f"pass rewrites every dialog again — {type(error).__name__}: {error}; "
                  f"make {dialogs_directory} writable by this user, and remove anything at that path that is "
                  "not a file")
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
    dialogs_directory = root / refresh_common.SESSION_DIALOGS_DIRECTORY_NAME
    try:
        dialogs_directory.mkdir(parents=True, exist_ok=True)
        lock = (dialogs_directory / LOCK_FILE_NAME).open("w")
    except OSError as error:
        print(f"FAILED: could not prepare {dialogs_directory} ({error})")
        return EXIT_FAILED
    with lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            if not failures_only:
                print(f"{PROGRAM}: another run holds {dialogs_directory / LOCK_FILE_NAME}; "
                      "leaving it to finish")
            return EXIT_LOCKED
        except OSError as error:
            print(f"FAILED: could not lock {dialogs_directory / LOCK_FILE_NAME}, so no dialog was refreshed — "
                  f"{type(error).__name__}: {error}")
            return EXIT_FAILED
        return refresh_all(root, failures_only)


if __name__ == "__main__":
    sys.exit(main())
