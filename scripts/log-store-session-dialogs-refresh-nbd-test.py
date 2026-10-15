#!/usr/bin/env python3
"""Tests for log-store-session-dialogs-refresh-nbd.py.

Run: python3 scripts/log-store-session-dialogs-refresh-nbd-test.py
Prints one line per case and exits non-zero if any case fails.

Every case builds a scratch log-store in a temporary directory and points the
program at it through LOG_STORE_SESSION_DIALOGS_REFRESH_LOG_STORE_ROOT_OVERRIDE, so the
tests never read or write the real log-store.
"""

import fcntl
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name("log-store-session-dialogs-refresh-nbd.py")
EXTRACTOR_PATH = Path(__file__).with_name("handoff-extract-conversation.py")
SUBAGENT_TRACKER_PATH = Path(__file__).with_name("handoff-extract-conversation-subagent-tracker-nbd.py")
# The transcripts' times are set after the extractor's, so a dialog's time is its transcript's.
LATER_THAN_THE_EXTRACTOR = int(max(time.time(), EXTRACTOR_PATH.stat().st_mtime)) + 1000
STORE_ROOT_VARIABLE = "LOG_STORE_SESSION_DIALOGS_REFRESH_LOG_STORE_ROOT_OVERRIDE"

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def run(store_root, *arguments, script_path=SCRIPT_PATH):
    environment = dict(os.environ, **{STORE_ROOT_VARIABLE: str(store_root)})
    return subprocess.run([sys.executable, str(script_path), *arguments], capture_output=True,
                          text=True, env=environment, check=False)


def write_transcript(store_root, machine, project_key, session_id, records):
    path = Path(store_root) / "transcripts" / machine / "projects" / project_key / f"{session_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    return path


def dialog_path(store_root, machine, project_key, session_id):
    return (Path(store_root) / "session-dialogs" / machine / project_key
            / f"{session_id}-dialog-complete.md")


def conversation(question):
    return [
        {"type": "user", "message": {"content": question}},
        {"type": "assistant", "message": {"content": [
            {"type": "text", "text": "Dispatching a reviewer."},
            {"type": "tool_use", "id": "toolu_review", "name": "Agent",
             "input": {"description": "Review the change", "prompt": "Review the diff.",
                       "subagent_type": "general-purpose"}}]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "toolu_review",
             "content": [{"type": "text", "text": "No findings."}]}]},
         "toolUseResult": {"status": "completed", "agentId": "a0000000000000001",
                           "content": [{"type": "text", "text": "No findings."}]}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "Merging."}]}},
    ]


with tempfile.TemporaryDirectory() as workspace:
    store = Path(workspace) / "store"
    mac_transcript = write_transcript(store, "mac", "-Users-someone-project", "s-mac", conversation("mac question"))
    box_transcript = write_transcript(store, "ned-box", "-home-someone-project", "s-box", conversation("box question"))
    empty_transcript = write_transcript(store, "ned-box", "-home-someone-project", "s-empty",
                                        [{"type": "system", "content": "no dialog here"}])
    # A subagent's own transcript sits below the session directory and is not a session.
    write_transcript(store, "mac", "-Users-someone-project/s-mac/subagents", "agent-a0000000000000001",
                     conversation("subagent's own turn"))
    for path in (mac_transcript, box_transcript, empty_transcript):
        os.utime(path, (LATER_THAN_THE_EXTRACTOR, LATER_THAN_THE_EXTRACTOR))

    first = run(store)
    mac_dialog = dialog_path(store, "mac", "-Users-someone-project", "s-mac")
    box_dialog = dialog_path(store, "ned-box", "-home-someone-project", "s-box")
    empty_dialog = dialog_path(store, "ned-box", "-home-someone-project", "s-empty")
    check("a first pass exits 0 and counts three dialogs written",
          first.returncode == 0 and "wrote 3 session dialogs, 0 already current, 0 failed" in first.stdout,
          first.stdout + first.stderr)
    check("each machine's session gets its dialog under session-dialogs/<machine>/<project-key>/",
          mac_dialog.is_file() and box_dialog.is_file(), sorted(str(p) for p in store.rglob("*.md")))
    mac_text = mac_dialog.read_text(encoding="utf-8") if mac_dialog.is_file() else ""
    check("the dialog is the complete dialog, the subagent's task and report included",
          "mac question" in mac_text and "## Subagent task — Review the change" in mac_text
          and "## Subagent report — Review the change" in mac_text and "Merging." in mac_text,
          mac_text)
    check("a subagent's own transcript gets no dialog of its own",
          not list((store / "session-dialogs").rglob("agent-*")),
          sorted(str(p) for p in (store / "session-dialogs").rglob("*")))
    check("a transcript with no dialog still gets a dialog that says it has no turns",
          empty_dialog.is_file() and "All 0 dialog turns" in empty_dialog.read_text(encoding="utf-8"))
    check("a dialog carries its transcript's change time",
          mac_dialog.stat().st_mtime_ns == mac_transcript.stat().st_ctime_ns,
          (mac_dialog.stat().st_mtime_ns, mac_transcript.stat().st_ctime_ns))

    second = run(store)
    check("a second pass over unchanged transcripts writes nothing",
          second.returncode == 0 and "wrote 0 session dialogs, 3 already current" in second.stdout,
          second.stdout + second.stderr)

    with mac_transcript.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"type": "user", "message": {"content": "a later question"}}) + "\n")
    os.utime(mac_transcript, (LATER_THAN_THE_EXTRACTOR + 600, LATER_THAN_THE_EXTRACTOR + 600))
    third = run(store, "--failures-only")
    check("a transcript that grew is written again, quietly under --failures-only",
          third.returncode == 0 and third.stdout == ""
          and "a later question" in mac_dialog.read_text(encoding="utf-8"),
          third.stdout + third.stderr)

    # Growth that reaches the mirror late keeps the Mac's time, which can be older than the extractor's.
    old_times = write_transcript(store, "mac", "-Users-someone-project", "s-old-times", conversation("first"))
    os.utime(old_times, (1_000_000_000, 1_000_000_000))
    run(store, "--failures-only")
    with old_times.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"type": "user", "message": {"content": "mirrored late"}}) + "\n")
    os.utime(old_times, (1_000_001_000, 1_000_001_000))
    late = run(store, "--failures-only")
    check("a transcript whose growth carries a time older than the extractor's is written again",
          late.returncode == 0 and "mirrored late" in dialog_path(
              store, "mac", "-Users-someone-project", "s-old-times").read_text(encoding="utf-8"),
          (late.returncode, late.stdout))

    # The mirror keeps a Mac transcript's time to the whole second, so growth within that second keeps the time.
    with old_times.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"type": "user", "message": {"content": "same second"}}) + "\n")
    os.utime(old_times, (1_000_001_000, 1_000_001_000))
    same_second = run(store, "--failures-only")
    check("a transcript that grew without its modification time changing is written again",
          same_second.returncode == 0 and "same second" in dialog_path(
              store, "mac", "-Users-someone-project", "s-old-times").read_text(encoding="utf-8"),
          (same_second.returncode, same_second.stdout))

    # A mirrored transcript replaced by an older-dated copy has a time that goes backwards.
    with old_times.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"type": "user", "message": {"content": "an older copy"}}) + "\n")
    os.utime(old_times, (1_000_000_500, 1_000_000_500))
    backwards = run(store, "--failures-only")
    check("a transcript whose time goes backwards is written again",
          backwards.returncode == 0 and "an older copy" in dialog_path(
              store, "mac", "-Users-someone-project", "s-old-times").read_text(encoding="utf-8"),
          (backwards.returncode, backwards.stdout))

    # A machine directory without projects/, and a file other than a transcript, are passed over quietly.
    (store / "transcripts" / "recovered").mkdir()
    (mac_transcript.parent / "settings.json").write_text("{}", encoding="utf-8")
    quiet = run(store)
    check("a machine directory with no projects/ and a non-.jsonl file in a project are passed over, exit 0",
          quiet.returncode == 0 and "FAILED" not in quiet.stdout
          and not (store / "session-dialogs" / "recovered").exists()
          and not dialog_path(store, "mac", "-Users-someone-project", "settings").exists(),
          (quiet.returncode, quiet.stdout))

    # A transcript that cannot be read fails alone: the others are still written.
    unreadable = write_transcript(store, "mac", "-Users-someone-project", "s-unreadable", conversation("hidden"))
    unreadable.chmod(0)
    later = write_transcript(store, "ned-box", "-home-someone-project", "s-later", conversation("later"))
    try:
        fourth = run(store, "--failures-only")
    finally:
        unreadable.chmod(0o644)
    check("an unreadable transcript prints a FAILED line naming it, and the pass exits 1",
          fourth.returncode == 1 and f"FAILED: {unreadable}" in fourth.stdout,
          (fourth.returncode, fourth.stdout, fourth.stderr))
    check("the pass goes on past an unreadable transcript",
          dialog_path(store, "ned-box", "-home-someone-project", "s-later").is_file())

    # The stale-dialog warning: the cron log is read by no one, so the reader of the dialog is told.
    warning_opening = "This dialog could not be refreshed since "
    unreadable_dialog = dialog_path(store, "mac", "-Users-someone-project", "s-unreadable")
    unreadable_text = unreadable_dialog.read_text(encoding="utf-8") if unreadable_dialog.is_file() else ""
    check("a transcript with no dialog yet that cannot be read gets a dialog holding only the stale-dialog warning",
          unreadable_text.startswith(warning_opening) and unreadable_text.count("\n") == 1
          and unreadable_text.rstrip().endswith("; what follows may be out of date.")
          and "PermissionError" in unreadable_text, unreadable_text)
    check("a dialog given the stale-dialog warning carries time 0, which no transcript's change time can equal",
          unreadable_dialog.is_file() and unreadable_dialog.stat().st_mtime_ns == 0
          and mac_dialog.stat().st_mtime_ns != 0,
          unreadable_dialog.stat().st_mtime_ns if unreadable_dialog.is_file() else "no dialog")
    unreadable_dialog.write_text(warning_opening + "2020-01-01 00:00 UTC: PermissionError: earlier; "
                                 "what follows may be out of date.\n", encoding="utf-8")
    # As the program leaves a warned dialog, so the next pass reads the transcript whatever tick the chmod lands in.
    os.utime(unreadable_dialog, ns=(0, 0))
    mac_transcript.chmod(0)
    unreadable.chmod(0)
    try:
        still_failing = run(store, "--failures-only")
    finally:
        mac_transcript.chmod(0o644)
        unreadable.chmod(0o644)
    still_text = unreadable_dialog.read_text(encoding="utf-8")
    check("a failure that lasts keeps the time it began in the stale-dialog warning, and still prints FAILED",
          still_text.startswith(warning_opening + "2020-01-01 00:00 UTC: PermissionError")
          and still_text.count(warning_opening) == 1 and f"FAILED: {unreadable}" in still_failing.stdout
          and still_failing.returncode == 1, (still_text, still_failing.stdout))
    stale_mac_text = mac_dialog.read_text(encoding="utf-8")
    check("a dialog that could not be rewritten keeps its last text under the stale-dialog warning",
          stale_mac_text.startswith(warning_opening) and "mac question" in stale_mac_text
          and "a later question" in stale_mac_text, stale_mac_text[:400])
    mac_transcript.chmod(0)
    try:
        run(store, "--failures-only")
    finally:
        mac_transcript.chmod(0o644)
    twice_stale_mac_text = mac_dialog.read_text(encoding="utf-8")
    check("a second failed pass keeps one stale-dialog warning over the same last text",
          twice_stale_mac_text.count(warning_opening) == 1 and "mac question" in twice_stale_mac_text,
          twice_stale_mac_text[:400])
    recovered_pass = run(store, "--failures-only")
    check("the pass after the transcripts can be read again rewrites both dialogs without the warning",
          recovered_pass.returncode == 0
          and not mac_dialog.read_text(encoding="utf-8").startswith(warning_opening)
          and "mac question" in mac_dialog.read_text(encoding="utf-8")
          and not unreadable_dialog.read_text(encoding="utf-8").startswith(warning_opening)
          and "hidden" in unreadable_dialog.read_text(encoding="utf-8"),
          (recovered_pass.returncode, recovered_pass.stdout))

    # A dialog that cannot be written is a failure too.
    blocked = write_transcript(store, "mac", "-Users-blocked-project", "s-blocked", conversation("blocked"))
    blocked_directory = store / "session-dialogs" / "mac" / "-Users-blocked-project"
    blocked_directory.parent.mkdir(parents=True, exist_ok=True)
    blocked_directory.write_text("a file where the directory should be", encoding="utf-8")
    fifth = run(store, "--failures-only")
    check("a dialog that cannot be written prints a FAILED line, and the pass exits 1",
          fifth.returncode == 1 and f"FAILED: {blocked}" in fifth.stdout,
          (fifth.returncode, fifth.stdout, fifth.stderr))
    check("a dialog whose stale-dialog warning cannot be written either prints that FAILED line too",
          "FAILED: could not warn in " in fifth.stdout, fifth.stdout)
    blocked_directory.unlink()

    lock_path = store / "session-dialogs" / ".log-store-session-dialogs-refresh.lock"
    with lock_path.open("w") as holder:
        fcntl.flock(holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
        held_quiet = run(store, "--failures-only")
        held_loud = run(store)
    check("a run that finds the lock held exits 3, silently under --failures-only",
          held_quiet.returncode == 3 and held_quiet.stdout == "",
          (held_quiet.returncode, held_quiet.stdout))
    check("without --failures-only the held lock is named",
          held_loud.returncode == 3 and "another run holds" in held_loud.stdout, held_loud.stdout)

    # A lock that fails for any reason but another run holding it is a failure, not an overlap to leave alone.
    lock_failing_script = Path(workspace) / "refresh-with-a-failing-lock.py"
    lock_failing_script.write_text(
        "import errno, fcntl, runpy, sys\n"
        "def failing_flock(*arguments):\n"
        "    raise OSError(errno.ENOLCK, 'No locks available')\n"
        "fcntl.flock = failing_flock\n"
        f"sys.argv[0] = {str(SCRIPT_PATH)!r}\n"
        f"runpy.run_path({str(SCRIPT_PATH)!r}, run_name='__main__')\n", encoding="utf-8")
    lock_failed = run(store, "--failures-only", script_path=lock_failing_script)
    check("a lock that fails other than by being held prints a FAILED line, and the pass exits 1",
          lock_failed.returncode == 1 and "FAILED: could not lock" in lock_failed.stdout,
          (lock_failed.returncode, lock_failed.stdout, lock_failed.stderr))

    # A project directory that cannot be listed is a failure, not a pass with nothing in it.
    hidden_project = store / "transcripts" / "mac" / "projects" / "-Users-hidden-project"
    write_transcript(store, "mac", "-Users-hidden-project", "s-hidden", conversation("hidden project"))
    hidden_project.chmod(0)
    try:
        unlistable = run(store, "--failures-only")
    finally:
        hidden_project.chmod(0o755)
    if os.geteuid() == 0:
        print("SKIP  an unlistable directory: root lists every directory, so no failure can be caused")
    else:
        check("a directory of transcripts that cannot be listed prints a FAILED line naming it, "
              "and the pass exits 1",
              unlistable.returncode == 1 and f"FAILED: cannot read {hidden_project}" in unlistable.stdout,
              (unlistable.returncode, unlistable.stdout, unlistable.stderr))

    # A directory that can be listed but not searched, at each level, and a machine directory with no access.
    mac_directory = store / "transcripts" / "mac"
    for blocked_path, mode, named in (
            (mac_directory, 0o000, mac_directory / "projects"),
            (mac_directory, 0o644, mac_directory / "projects"),
            (mac_directory / "projects", 0o644, mac_directory / "projects" / "-Users-hidden-project"),
            (hidden_project, 0o644, hidden_project / "s-hidden.jsonl")):
        blocked_path.chmod(mode)
        try:
            unsearchable = run(store, "--failures-only")
        finally:
            blocked_path.chmod(0o755)
        if os.geteuid() == 0:
            print(f"SKIP  {blocked_path.name} at {mode:o}: root searches every directory")
            continue
        check(f"{blocked_path.relative_to(store)} at mode {mode:o} prints a FAILED line naming {named.name}, "
              "and the pass exits 1",
              unsearchable.returncode == 1 and f"FAILED: cannot read {named}" in unsearchable.stdout,
              (unsearchable.returncode, unsearchable.stdout, unsearchable.stderr))

    # A change to the extractor rewrites every dialog once, even of a transcript that never changes again.
    programs = Path(workspace) / "programs"
    programs.mkdir()
    script_copy = programs / SCRIPT_PATH.name
    shutil.copy2(SCRIPT_PATH, script_copy)
    shutil.copy2(EXTRACTOR_PATH, programs / EXTRACTOR_PATH.name)
    shutil.copy2(SUBAGENT_TRACKER_PATH, programs / SUBAGENT_TRACKER_PATH.name)
    settled = run(store, "--failures-only", script_path=script_copy)
    touched = run(store, script_path=script_copy)
    with (programs / EXTRACTOR_PATH.name).open("a", encoding="utf-8") as handle:
        handle.write("# changed\n")
    rewritten = run(store, script_path=script_copy)
    after = run(store, script_path=script_copy)
    check("after the extractor's bytes change, one pass rewrites the dialogs of unchanged transcripts, "
          "and the next writes none",
          settled.returncode == 0 and "wrote 0 session dialogs" in touched.stdout
          and rewritten.returncode == 0 and "wrote 0 session dialogs" not in rewritten.stdout
          and "wrote 0 session dialogs" in after.stdout
          and box_dialog.stat().st_mtime_ns == box_transcript.stat().st_ctime_ns,
          (settled.stdout, touched.stdout, rewritten.stdout, after.stdout))

    # A dialog the changed extractor could not rewrite is rewritten by a later pass.
    box_dialogs = box_dialog.parent
    with (programs / EXTRACTOR_PATH.name).open("a", encoding="utf-8") as handle:
        handle.write("# changed again\n")
    box_dialogs.chmod(0o555)
    try:
        stuck = run(store, script_path=script_copy)
    finally:
        box_dialogs.chmod(0o755)
    retried = run(store, script_path=script_copy)
    if os.geteuid() == 0:
        print("SKIP  a dialog the changed extractor could not rewrite: root writes every directory")
    else:
        check("a dialog the changed extractor could not rewrite is rewritten by the next pass",
              stuck.returncode == 1 and "wrote 0 session dialogs" not in retried.stdout,
              (stuck.stdout, retried.stdout))

    # A change to the subagent tracker alone also rewrites every dialog once.
    with (programs / SUBAGENT_TRACKER_PATH.name).open("a", encoding="utf-8") as handle:
        handle.write("# changed\n")
    tracker_rewritten = run(store, script_path=script_copy)
    tracker_after = run(store, script_path=script_copy)
    check("after the subagent tracker's bytes change, one pass rewrites the dialogs, and the next writes none",
          tracker_rewritten.returncode == 0 and "wrote 0 session dialogs" not in tracker_rewritten.stdout
          and "wrote 0 session dialogs" in tracker_after.stdout,
          (tracker_rewritten.stdout, tracker_after.stdout))

    # A tracker that cannot be read still lets every dialog be written, without subagent turns and saying so.
    tracker_copy = programs / SUBAGENT_TRACKER_PATH.name
    tracker_aside = programs / "tracker-set-aside.py"
    tracker_copy.rename(tracker_aside)
    try:
        without_tracker = run(store, "--failures-only", script_path=script_copy)
        box_without_tracker = box_dialog.read_text(encoding="utf-8")
    finally:
        tracker_aside.rename(tracker_copy)
    check("a subagent tracker that cannot be read prints a FAILED line naming it, and the pass exits 1",
          without_tracker.returncode == 1 and f"FAILED: cannot read {tracker_copy.resolve()}" in without_tracker.stdout,
          (without_tracker.returncode, without_tracker.stdout, without_tracker.stderr))
    check("a subagent tracker that cannot be read leaves each dialog written, with the note that subagent turns "
          "are left out and no subagent turn",
          "## Subagent tasks and reports left out" in box_without_tracker
          and "## Subagent task " not in box_without_tracker and "box question" in box_without_tracker,
          box_without_tracker[:600])
    undeletable_store = Path(workspace) / "undeletable-digest-store"
    write_transcript(undeletable_store, "mac", "-Users-someone-project", "s-undeletable", conversation("undeletable"))
    (undeletable_store / "session-dialogs" / ".dialogs-written-by-extractor-sha256" / "inside").mkdir(parents=True)
    tracker_copy.rename(tracker_aside)
    try:
        undeletable = run(undeletable_store, "--failures-only", script_path=script_copy)
    finally:
        tracker_aside.rename(tracker_copy)
    check("a digest that cannot be removed while the tracker cannot be read prints a FAILED line, and the pass exits 1",
          undeletable.returncode == 1 and "FAILED: could not remove " in undeletable.stdout,
          (undeletable.returncode, undeletable.stdout, undeletable.stderr))
    tracker_back = run(store, script_path=script_copy)
    check("the pass after the tracker is back writes every dialog again, with its subagent turns",
          tracker_back.returncode == 0 and "wrote 0 session dialogs" not in tracker_back.stdout
          and "## Subagent task " in box_dialog.read_text(encoding="utf-8"),
          (tracker_back.stdout, box_dialog.read_text(encoding="utf-8")[:400]))

    # A digest that cannot be read or kept is a failure: otherwise every pass would rewrite every dialog unseen.
    digest_store = Path(workspace) / "digest-store"
    write_transcript(digest_store, "mac", "-Users-someone-project", "s-digest", conversation("digest"))
    digest_file = digest_store / "session-dialogs" / ".dialogs-written-by-extractor-sha256"
    digest_file.mkdir(parents=True)
    undigested = run(digest_store, "--failures-only")
    check("a directory where the extractor digest belongs prints a FAILED line naming it, and the pass exits 1",
          undigested.returncode == 1 and f"FAILED: cannot read {digest_file}" in undigested.stdout,
          (undigested.returncode, undigested.stdout, undigested.stderr))
    digest_file.rmdir()
    recorded = run(digest_store, "--failures-only")
    digest_file.chmod(0o200)
    try:
        unreadable_digest = run(digest_store, "--failures-only")
        unreadable_again = run(digest_store, "--failures-only")
    finally:
        digest_file.chmod(0o644)
    if os.geteuid() == 0:
        print("SKIP  an extractor digest that cannot be read: root reads every file")
    else:
        check("an extractor digest that cannot be read prints a FAILED line under --failures-only on every pass, "
              "exit 1",
              recorded.returncode == 0 and unreadable_digest.returncode == 1
              and f"FAILED: cannot read {digest_file}" in unreadable_digest.stdout
              and unreadable_again.returncode == 1
              and f"FAILED: cannot read {digest_file}" in unreadable_again.stdout,
              (recorded.stdout, unreadable_digest.stdout, unreadable_again.stdout))
    digest_file.unlink()
    digest_file.parent.chmod(0o555)
    try:
        unwritable_digest = run(digest_store, "--failures-only")
    finally:
        digest_file.parent.chmod(0o755)
    if os.geteuid() == 0:
        print("SKIP  an extractor digest that cannot be written: root writes every directory")
    else:
        check("an extractor digest that cannot be written prints a FAILED line, and the pass exits 1",
              unwritable_digest.returncode == 1
              and "FAILED: could not record the extractor's sha256" in unwritable_digest.stdout,
              (unwritable_digest.returncode, unwritable_digest.stdout, unwritable_digest.stderr))

    no_transcripts = Path(workspace) / "empty-store"
    no_transcripts.mkdir()
    sixth = run(no_transcripts, "--failures-only")
    check("a store with no transcripts directory is FAILED, exit 1",
          sixth.returncode == 1 and "FAILED: no " in sixth.stdout, (sixth.returncode, sixth.stdout))

    unpreparable = Path(workspace) / "store-with-a-file-for-session-dialogs"
    (unpreparable / "transcripts").mkdir(parents=True)
    (unpreparable / "session-dialogs").write_text("not a directory", encoding="utf-8")
    seventh = run(unpreparable, "--failures-only")
    check("a session-dialogs directory that cannot be prepared is FAILED, exit 1",
          seventh.returncode == 1 and "FAILED: could not prepare" in seventh.stdout,
          (seventh.returncode, seventh.stdout, seventh.stderr))

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
