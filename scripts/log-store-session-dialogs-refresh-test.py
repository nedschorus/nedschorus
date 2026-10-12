#!/usr/bin/env python3
"""Tests for log-store-session-dialogs-refresh.py.

Run: python3 scripts/log-store-session-dialogs-refresh-test.py
Prints one line per case and exits non-zero if any case fails.

Every case builds a scratch log-store in a temporary directory and points the
program at it through LOG_STORE_SESSION_DIALOGS_REFRESH_LOG_STORE_ROOT_OVERRIDE, so the
tests never read or write the real log-store.
"""

import fcntl
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name("log-store-session-dialogs-refresh.py")
STORE_ROOT_VARIABLE = "LOG_STORE_SESSION_DIALOGS_REFRESH_LOG_STORE_ROOT_OVERRIDE"

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def run(store_root, *arguments):
    environment = dict(os.environ, **{STORE_ROOT_VARIABLE: str(store_root)})
    return subprocess.run([sys.executable, str(SCRIPT_PATH), *arguments], capture_output=True,
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
        os.utime(path, (1_700_000_000, 1_700_000_000))

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
    check("a dialog carries its transcript's modification time",
          mac_dialog.stat().st_mtime_ns == mac_transcript.stat().st_mtime_ns,
          (mac_dialog.stat().st_mtime_ns, mac_transcript.stat().st_mtime_ns))

    second = run(store)
    check("a second pass over unchanged transcripts writes nothing",
          second.returncode == 0 and "wrote 0 session dialogs, 3 already current" in second.stdout,
          second.stdout + second.stderr)

    with mac_transcript.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"type": "user", "message": {"content": "a later question"}}) + "\n")
    os.utime(mac_transcript, (1_700_000_600, 1_700_000_600))
    third = run(store, "--failures-only")
    check("a transcript that grew is written again, quietly under --failures-only",
          third.returncode == 0 and third.stdout == ""
          and "a later question" in mac_dialog.read_text(encoding="utf-8"),
          third.stdout + third.stderr)

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

    # A dialog that cannot be written is a failure too.
    blocked = write_transcript(store, "mac", "-Users-blocked-project", "s-blocked", conversation("blocked"))
    blocked_directory = store / "session-dialogs" / "mac" / "-Users-blocked-project"
    blocked_directory.parent.mkdir(parents=True, exist_ok=True)
    blocked_directory.write_text("a file where the directory should be", encoding="utf-8")
    fifth = run(store, "--failures-only")
    check("a dialog that cannot be written prints a FAILED line, and the pass exits 1",
          fifth.returncode == 1 and f"FAILED: {blocked}" in fifth.stdout,
          (fifth.returncode, fifth.stdout, fifth.stderr))
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
