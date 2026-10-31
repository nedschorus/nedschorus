#!/usr/bin/env python3
"""Tests for log-store-session-dialogs-refresh-common.py.

Run: python3 scripts/log-store-session-dialogs-refresh-common-test.py
Prints one line per case and exits 1 if any case fails.

Every case builds a scratch log-store in a temporary directory; no real record is read or written.
"""

import importlib.util
import os
import stat
import sys
import tempfile
import types
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("log-store-session-dialogs-refresh-common.py")
_specification = importlib.util.spec_from_file_location("log_store_session_dialogs_refresh_common", MODULE_PATH)
refresh_common = importlib.util.module_from_spec(_specification)
_specification.loader.exec_module(refresh_common)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def counting_extractor(left_out=()):
    """A stand-in for the extractor; left_out are the tracker-failure notes its turns hold."""
    rendered = []

    def turns_and_report(transcript):
        rendered.append(transcript)
        return [], transcript.name
    return types.SimpleNamespace(
        complete_dialog_turns_and_report=turns_and_report,
        turns_left_out_notes=lambda turns: [{"text": note} for note in left_out],
        render_companion=lambda turns, name: f"dialog of {name}\n"), rendered


with tempfile.TemporaryDirectory() as workspace:
    store = Path(workspace)
    transcripts = store / refresh_common.AGENT_SESSION_FILES_FOLDER_IN_LOG_STORE
    project = transcripts / "mac" / "projects" / "-Users-someone-project"
    project.mkdir(parents=True)
    transcript = project / "s1.jsonl"
    transcript.write_text("{}\n")
    (project / "settings.json").write_text("{}")
    (project / "s1" / "subagents").mkdir(parents=True)
    (project / "s1" / "subagents" / "agent-a.jsonl").write_text("{}\n")
    (transcripts / "recovered").mkdir()

    unreadable = []
    found = list(refresh_common.find_session_transcripts_mirrored_in_log_store(transcripts, unreadable))
    check("every session transcript is found with its machine and project key, and nothing else",
          found == [("mac", "-Users-someone-project", transcript)] and not unreadable, (found, unreadable))

    dialog = refresh_common.session_dialog_path_for_transcript(
        store / refresh_common.SESSION_DIALOGS_DIRECTORY_NAME, "mac", "-Users-someone-project", transcript)
    check("a transcript's session dialog is under session-dialogs/<machine>/<project-key>/",
          dialog == store / "session-dialogs" / "mac" / "-Users-someone-project" / "s1-dialog-complete.md", dialog)

    extractor, rendered = counting_extractor()
    written = refresh_common.refresh_session_dialog_file_unless_current_with_transcript(
        extractor, True, transcript, dialog)
    check("a transcript with no dialog gets one, carrying the transcript's change time",
          written and dialog.read_text() == "dialog of s1.jsonl\n"
          and dialog.stat().st_mtime_ns == transcript.stat().st_ctime_ns, (written, dialog.stat()))
    written = refresh_common.refresh_session_dialog_file_unless_current_with_transcript(
        extractor, True, transcript, dialog)
    check("a current dialog is not written again, and its transcript is not read",
          not written and len(rendered) == 1, (written, rendered))
    written = refresh_common.refresh_session_dialog_file_unless_current_with_transcript(
        extractor, False, transcript, dialog)
    check("a current dialog is written again when the extractor changed", written and len(rendered) == 2, rendered)
    os.utime(transcript)
    written = refresh_common.refresh_session_dialog_file_unless_current_with_transcript(
        extractor, True, transcript, dialog)
    check("a dialog whose transcript changed since it was written is written again",
          written and dialog.stat().st_mtime_ns == transcript.stat().st_ctime_ns, written)

    failing_extractor, rendered = counting_extractor(left_out=["The subagent tracker failed."])
    os.utime(transcript)
    try:
        refresh_common.refresh_session_dialog_file_unless_current_with_transcript(
            failing_extractor, True, transcript, dialog, refuse_without_subagent_turns=True)
        check("a dialog the subagent tracker failed on is refused, not written, when the caller asks", False,
              "nothing raised")
    except refresh_common.SubagentTurnsLeftOut as error:
        check("a dialog the subagent tracker failed on is refused, not written, when the caller asks",
              str(error) == "The subagent tracker failed." and dialog.stat().st_mtime_ns != transcript.stat().st_ctime_ns,
              error)
    written = refresh_common.refresh_session_dialog_file_unless_current_with_transcript(
        failing_extractor, True, transcript, dialog)
    check("a dialog the subagent tracker failed on is written when the caller does not refuse it",
          written and dialog.stat().st_mtime_ns == transcript.stat().st_ctime_ns, written)

    replaced_from = []
    real_replace = os.replace

    def recording_replace(source, destination):
        replaced_from.append(Path(source).name)
        real_replace(source, destination)
    os.replace = recording_replace
    try:
        refresh_common.write_text_through_temporary_file(dialog, "whole\n", 12345)
    finally:
        os.replace = real_replace
    check("the temporary file a dialog is written through is named with this process's id, so two writers never "
          "share one",
          replaced_from == [f"{dialog.name}.{os.getpid()}.partial"], replaced_from)

    other_writer = dialog.with_name(dialog.name + ".1.partial")
    other_writer.write_text("another process's half-written dialog")
    refresh_common.write_text_through_temporary_file(dialog, "whole\n", 12345)
    check("a dialog is written whole through a temporary file of this process's own, leaving another "
          "writer's temporary file alone and none of its own",
          dialog.read_text() == "whole\n" and dialog.stat().st_mtime_ns == 12345
          and other_writer.is_file() and other_writer.read_text() == "another process's half-written dialog"
          and sorted(path.name for path in dialog.parent.iterdir()) == sorted([dialog.name, other_writer.name]),
          sorted(path.name for path in dialog.parent.iterdir()))

    blocked = store / "session-dialogs" / "ned-box"
    blocked.write_text("a file where a directory belongs")
    try:
        refresh_common.write_text_through_temporary_file(blocked / "key" / "s2-dialog-complete.md", "x", 0)
        check("a dialog that cannot be written raises", False, "nothing raised")
    except OSError as error:
        check("a dialog that cannot be written raises", True, error)

    if os.geteuid() == 0:
        print("SKIP  a directory that cannot be listed or examined: root reads every directory")
    else:
        project.chmod(0)
        unreadable = []
        try:
            found = list(refresh_common.find_session_transcripts_mirrored_in_log_store(transcripts, unreadable))
        finally:
            project.chmod(0o755)
        check("a project directory that cannot be listed is reported as unreadable, not passed over",
              found == [] and [path for path, _ in unreadable] == [project], unreadable)
        mac = transcripts / "mac"
        mac.chmod(stat.S_IRUSR)
        unreadable = []
        try:
            found = list(refresh_common.find_session_transcripts_mirrored_in_log_store(transcripts, unreadable))
        finally:
            mac.chmod(0o755)
        check("a directory that can be listed but not searched is reported as unreadable, not passed over",
              found == [] and [path for path, _ in unreadable] == [mac / "projects"], unreadable)

print(f"{'FAILED' if failures else 'all cases passed'}: {len(failures)} failure(s)")
sys.exit(1 if failures else 0)
