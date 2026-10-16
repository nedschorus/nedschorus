#!/usr/bin/env python3
"""Tests for log-store-past-discussions-regex-search-newest-first.py.

Run: python3 scripts/log-store-past-discussions-regex-search-newest-first-test.py
Prints one line per case and exits 1 if any case fails.

Each case builds a log-store in a temporary directory and runs the program on
it; no real record is read. Stub programs stand in for ripgrep and ssh where
a case needs one to fail.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROGRAM = Path(__file__).with_name("log-store-past-discussions-regex-search-newest-first.py")
PREFIX = "LOG_STORE_PAST_DISCUSSIONS_SEARCH_"

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def write(path, text, mtime=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def epoch(day):
    import datetime
    return datetime.datetime.fromisoformat(day + "T12:00:00+00:00").timestamp()


def transcript_records(*records):
    return "".join(json.dumps(record) + "\n" for record in records)


def typed(text, stamp):
    return {"type": "user", "timestamp": stamp, "message": {"role": "user", "content": text}}


def agent(text, stamp):
    return {"type": "assistant", "timestamp": stamp,
            "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


# The dialogs refresher gives a dialog its transcript's change time, which an import resets.
DIALOG_IMPORTED_AT = epoch("2026-12-01")


def build_store(root):
    """A log-store with one record of each kind that mentions the heron plan."""
    write(root / "walk" / "heron-walk-2026-10-01-minutes.md",
          "# Heron walk: minutes\n\nApproval-walk run by agent-instructions-editor on ned-box, 2026-10-01.\n\n"
          "User: \"y\" to the heron plan\n")
    write(root / "cold-read-records" / "heron-plan-2026-09-20" / "fast-read.md",
          "line one\nthe heron plan is unclear\nline three\n")
    write(root / "analysis" / "2026-08-15-heron-research.md", "Heron plan research.\n")
    key = "-home-nedlern-agents-prime-intellect"
    write(root / "session-dialogs" / "ned-box" / key / "s1-dialog-complete.md",
          "# Complete session dialog\n\n## Agent\n\nShall we start the heron plan?\n",
          mtime=DIALOG_IMPORTED_AT)
    write(root / "transcripts" / "ned-box" / "projects" / key / "s1.jsonl",
          transcript_records(agent("Shall we start the heron plan?", "2026-09-28T09:00:00Z"),
                             typed("go with the heron plan", "2026-09-28T09:01:00Z"),
                             agent("Done.", "2026-10-05T10:00:00Z")),
          mtime=epoch("2026-10-05"))
    mac_key = "-Users-el-agents-fleet-restart-at-login"
    write(root / "session-dialogs" / "mac" / mac_key / "s2-dialog-complete.md",
          "## User\n\nheron plan on the Mac\n", mtime=DIALOG_IMPORTED_AT)
    write(root / "transcripts" / "mac" / "projects" / mac_key / "s2.jsonl",
          transcript_records(typed("heron plan on the Mac", "2026-10-07T08:00:00Z")),
          mtime=epoch("2026-10-07"))
    write(root / "transcripts" / "mac" / "projects" / mac_key / "s2" / "subagents" / "agent-x.jsonl",
          transcript_records(typed("heron plan inside a subagent", "2026-10-07T08:00:00Z")))


def run(root, *arguments, environment=None):
    env = dict(os.environ)
    # The agent-session running these tests is not one of the store's sessions.
    env.pop("CLAUDE_CODE_SESSION_ID", None)
    # The program reads the running agent-session's live transcript under ~/.claude/projects.
    env["HOME"] = str(Path(root).parent / "home")
    env[PREFIX + "LOG_STORE_ROOT_OVERRIDE"] = str(root)
    env[PREFIX + "THIS_MACHINE_OVERRIDE"] = "ned-box"
    env.update(environment or {})
    return subprocess.run([sys.executable, str(PROGRAM), *arguments], capture_output=True, text=True,
                          env=env, stdin=subprocess.DEVNULL)


def stub(directory, name, body):
    path = Path(directory) / name
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(0o755)
    return str(path)


def hit_headers(output):
    return [line for line in output.splitlines() if line[:4].isdigit()]


if shutil.which("rg") is None:
    print("FAIL  ripgrep is installed: rg is not on PATH; install it: sudo apt install ripgrep")
    sys.exit(1)

with tempfile.TemporaryDirectory() as scratch:
    root = Path(scratch) / "store"
    build_store(root)

    result = run(root, "HERON PLAN")
    headers = hit_headers(result.stdout)
    kinds = [header.split("  ")[1] for header in headers]
    check("every kind is searched, case-insensitively, and found",
          result.returncode == 0 and sorted(set(kinds)) == sorted(
              ["walk", "cold-read-records", "analysis", "session-dialogs", "user-messages"]),
          result.stdout + result.stderr)
    dates = [header.split("  ")[0][:10] for header in headers]
    check("hits come newest first", dates == sorted(dates, reverse=True), dates)
    check("the transcripts' subagents directories are not searched",
          "inside a subagent" not in result.stdout, result.stdout)
    check("a walk file's agent-seat is read from its header",
          any(h.startswith("2026-10-01  walk  agent-instructions-editor") for h in headers), headers)
    check("a session's machine and agent-seat are read from its path",
          any("user-messages  ned-box  prime-intellect" in h for h in headers)
          and any("session-dialogs  mac  fleet-restart-at-login" in h for h in headers), headers)
    check("a hit shows its file and line, and its context",
          "fast-read.md:2" in result.stdout and "line one" in result.stdout
          and "line three" in result.stdout, result.stdout)
    check("a session dialog's hit is dated by its own turn, not the session's last activity "
          "or the dialog's modification time",
          "2026-09-28T09:00:00Z  session-dialogs  ned-box  prime-intellect" in result.stdout
          and "2026-10-05" not in result.stdout and "2026-12-01" not in result.stdout, result.stdout)
    check("a user's message carries the time he sent it",
          "2026-09-28T09:01:00Z  user-messages" in result.stdout, result.stdout)

    result = run(root, "heron plan", "--kind", "session-dialogs", "--since", "2026-11-01")
    check("--since leaves out a session dialog whose transcript ended before it, whatever the dialog's modification time",
          result.returncode == 1 and not hit_headers(result.stdout), result.stdout)

    long_tail = root / "transcripts" / "ned-box" / "projects" / "-home-nedlern-agents-z" / "s8.jsonl"
    write(long_tail, transcript_records(agent("heron plan tail", "2026-10-04T00:00:00Z"),
                                        {"type": "summary", "summary": "x" * 300000}))
    write(root / "session-dialogs" / "ned-box" / "-home-nedlern-agents-z" / "s8-dialog-complete.md",
          "## Agent\n\nheron plan tail, as the dialog words it\n", mtime=DIALOG_IMPORTED_AT)
    finding = run(root, "heron plan tail", "--kind", "session-dialogs")
    long_tail.unlink()
    (root / "session-dialogs" / "ned-box" / "-home-nedlern-agents-z" / "s8-dialog-complete.md").unlink()
    check("a hit whose turn is not in the transcript is dated by the session's last activity, found behind "
          "a long record with none, and says so",
          "2026-10-04T00:00:00Z (session's last activity: its turn was not found in the transcript)"
          in finding.stdout, finding.stdout)

    turns_key = "-home-nedlern-agents-turns"
    turns_transcript = root / "transcripts" / "ned-box" / "projects" / turns_key / "s20.jsonl"
    write(turns_transcript, transcript_records(
        agent("We keep one egret seat for the egret work.", "2026-09-10T08:00:00Z"),
        typed("yes, egret", "2026-09-10T08:01:00Z"),
        agent("As agreed: We keep one egret seat for the egret work.", "2026-09-20T08:00:00Z"),
        agent('The user said "keep the heron egret" today.', "2026-09-12T08:00:00Z"),
        agent("Done.", "2026-10-20T08:00:00Z")))
    turns_dialog = write(root / "session-dialogs" / "ned-box" / turns_key / "s20-dialog-complete.md",
                         "## Agent\n\nWe keep one egret seat for the egret work.\n\n## User\n\nyes, egret\n\n"
                         "## Agent\n\nThe user said \"keep the heron egret\" today.\n",
                         mtime=DIALOG_IMPORTED_AT)
    finding = run(root, "egret", "--kind", "session-dialogs")
    check("a dialog line is dated by its own turn, not a later turn that quotes it within a longer line",
          "2026-09-10T08:00:00Z  session-dialogs  ned-box  turns" in finding.stdout, finding.stdout)
    check("a short dialog line is dated by its own turn too",
          "2026-09-10T08:01:00Z  session-dialogs  ned-box  turns" in finding.stdout
          and "last activity" not in finding.stdout, finding.stdout)
    check("a dialog line holding a quote mark is found in the transcript, where JSON escapes it",
          "2026-09-12T08:00:00Z  session-dialogs  ned-box  turns" in finding.stdout, finding.stdout)
    finding = run(root, "one egret seat", "--kind", "session-dialogs", "--since", "2026-10-01")
    check("--since bounds a dialog hit by its turn's date, not the session's last activity",
          finding.returncode == 1 and not hit_headers(finding.stdout), finding.stdout)
    finding = run(root, "one egret seat", "--kind", "session-dialogs", "--until", "2026-09-15")
    check("--until keeps a dialog hit whose turn is inside the window",
          finding.returncode == 0 and "2026-09-10T08:00:00Z" in finding.stdout, finding.stdout)
    turns_dialog.unlink()
    turns_transcript.unlink()

    def tool_result(text, stamp):
        return {"type": "user", "timestamp": stamp, "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "read-1", "content": text}]}}

    def tool_use(text, stamp):
        return {"type": "assistant", "timestamp": stamp, "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": "write-1", "name": "Write", "input": {"content": text}}]}}

    ibis_key = "-home-nedlern-agents-ibis"
    ibis_transcript = root / "transcripts" / "ned-box" / "projects" / ibis_key / "s21.jsonl"
    write(ibis_transcript, transcript_records(
        tool_result("- [PR 7: the ibis plan](https://example.invalid/7)", "2026-09-01T08:00:00Z"),
        tool_use("The ibis draft says yes.", "2026-09-02T08:00:00Z"),
        agent("- [PR 7: the ibis plan](https://example.invalid/7)\nThe ibis draft says yes.", "2026-09-03T08:00:00Z"),
        agent("Again:\n- [PR 7: the ibis plan](https://example.invalid/7)", "2026-09-05T08:00:00Z"),
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "text", "text": "An ibis turn with no time."}]}},
        agent("Done.", "2026-09-30T08:00:00Z")))
    ibis_dialog = write(root / "session-dialogs" / "ned-box" / ibis_key / "s21-dialog-complete.md",
                        "# Complete session dialog\n\n## Agent\n\n- [PR 7: the ibis plan](https://example.invalid/7)\n"
                        "The ibis draft says yes.\n\n## Agent\n\nAgain:\n"
                        "- [PR 7: the ibis plan](https://example.invalid/7)\n\n## Agent\n\nAn ibis turn with no time.\n",
                        mtime=DIALOG_IMPORTED_AT)
    finding = run(root, "ibis", "--kind", "session-dialogs")
    check("a dialog line an earlier tool result also holds is dated by its own turn, not the tool result",
          "2026-09-03T08:00:00Z  session-dialogs  ned-box  ibis\n  " + str(ibis_dialog) + ":5" in finding.stdout
          and "2026-09-01" not in finding.stdout, finding.stdout)
    check("a dialog line an earlier tool call's input also holds is dated by its own turn, not the tool call",
          str(ibis_dialog) + ":6" in finding.stdout.split("2026-09-03T08:00:00Z")[-1]
          and "2026-09-02" not in finding.stdout, finding.stdout)
    check("a line said in two turns is dated, at each place, by the turn it appears in",
          "2026-09-05T08:00:00Z  session-dialogs  ned-box  ibis\n  " + str(ibis_dialog) + ":11" in finding.stdout,
          finding.stdout)
    check("a dialog line whose turn's record has no time is dated by the session's last activity, and says so",
          "2026-09-30T08:00:00Z (session's last activity: its turn was not found in the transcript)  "
          "session-dialogs  ned-box  ibis\n  " + str(ibis_dialog) + ":15" in finding.stdout, finding.stdout)
    ibis_dialog.unlink()
    ibis_transcript.unlink()

    probe = subprocess.run([sys.executable, "-c", f"""
import importlib.util
spec = importlib.util.spec_from_file_location("search", {str(PROGRAM)!r})
search = importlib.util.module_from_spec(spec)
spec.loader.exec_module(search)
print(search.dialog_line_turn_times({str(root / "transcripts" / "ned-box" / "projects" / "-home-nedlern-agents-prime-intellect" / "s1.jsonl")!r},
                                    {str(Path(scratch) / "no-such-dialog.md")!r}, [3]))
"""], capture_output=True, text=True)
    broken_tracker = subprocess.run([sys.executable, "-c", f"""
import importlib.util, os, sys
os.environ[{PREFIX + "LOG_STORE_ROOT_OVERRIDE"!r}] = {str(root)!r}
os.environ[{PREFIX + "THIS_MACHINE_OVERRIDE"!r}] = "ned-box"
os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
spec = importlib.util.spec_from_file_location("search", {str(PROGRAM)!r})
search = importlib.util.module_from_spec(spec)
spec.loader.exec_module(search)
extractor = search.load_handoff_extractor()
def broken():
    raise RuntimeError("the tracker is broken")
extractor.new_subagent_tracker = broken
search._extractor_in_this_process = extractor
sys.exit(search.main(["start the heron plan", "--kind", "session-dialogs", "--jobs", "1"]))
"""], capture_output=True, text=True)
    check("when the subagent tracker fails, the dialog's hits keep the noted date, a FAILED line says why, "
          "and the search exits nonzero",
          broken_tracker.returncode == 2 and "lacks its subagent turns" in broken_tracker.stderr
          and "RuntimeError: the tracker is broken" in broken_tracker.stderr
          and "(session's last activity" in broken_tracker.stdout
          and "2026-09-28T09:00:00Z  session-dialogs" not in broken_tracker.stdout,
          broken_tracker.stdout + broken_tracker.stderr)
    egret_key = "-home-nedlern-agents-written-while-broken"
    egret_transcript = write(root / "transcripts" / "ned-box" / "projects" / egret_key / "s22.jsonl", transcript_records(
        agent("the stork plan", "2026-09-01T08:00:00Z"),
        agent("the stork plan", "2026-09-02T08:00:00Z")))
    left_out_section = ("## Subagent tasks and reports left out\n\nThe subagent tracker, "
                        "handoff-extract-conversation-subagent-tracker-nbd.py, failed, so this dialog leaves out "
                        "every subagent task and report: RuntimeError: gone\n")
    egret_dialog = write(root / "session-dialogs" / "ned-box" / egret_key / "s22-dialog-complete.md",
                         "## Agent\n\nthe stork plan\n\n" + left_out_section, mtime=DIALOG_IMPORTED_AT)
    finding = run(root, "stork plan", "--kind", "session-dialogs")
    check("a dialog written while the subagent tracker failed is not dated by turn, since the dialog built "
          "again holds turns it lacks; a FAILED line says so and the search exits nonzero",
          finding.returncode == 2 and "was written while the subagent tracker failed" in finding.stderr
          and "(session's last activity" in finding.stdout and "2026-09-01T08:00:00Z" not in finding.stdout,
          finding.stdout + finding.stderr)
    egret_dialog.write_text("## Agent\n\nthe stork plan\n\n## User\n\n" + left_out_section.split("\n", 2)[2]
                            + "\n## Subagent tasks and reports left out\n\nas a heading the user typed\n")
    finding = run(root, "stork plan", "--kind", "session-dialogs")
    check("a dialog that only quotes the tracker's note, or its heading with no note under it, is dated by turn",
          finding.returncode == 0 and "2026-09-01T08:00:00Z  session-dialogs" in finding.stdout,
          finding.stdout + finding.stderr)
    egret_dialog.unlink()
    egret_transcript.unlink()

    check("a session dialog that cannot be read again to date its hits is a failure",
          "could not read the session dialog " in probe.stdout and "no-such-dialog.md" in probe.stdout,
          probe.stdout + probe.stderr)

    own = run(root, "heron plan", environment={"CLAUDE_CODE_SESSION_ID": "s1"})
    check("the agent-session running the search is left out, its dialog and its messages both, and the "
          "closing line says so",
          own.returncode == 0 and "prime-intellect" not in own.stdout
          and "Left out this agent-session's own records, session s1, since it has not been compacted"
          in own.stdout, own.stdout)
    own = run(root, "heron plan", "--include-own-session", environment={"CLAUDE_CODE_SESSION_ID": "s1"})
    check("--include-own-session searches the running agent-session too",
          "session-dialogs  ned-box  prime-intellect" in own.stdout
          and "user-messages  ned-box  prime-intellect" in own.stdout
          and "Left out" not in own.stdout and "could not be identified" not in own.stdout, own.stdout)
    own = run(root, "heron plan")
    check("when the running agent-session cannot be identified, everything is searched and the closing "
          "line says so",
          "prime-intellect" in own.stdout and "could not be identified" in own.stdout, own.stdout)

    s1 = root / "transcripts" / "ned-box" / "projects" / "-home-nedlern-agents-prime-intellect" / "s1.jsonl"
    s1_text = s1.read_text()
    compaction = {"type": "system", "subtype": "compact_boundary", "content": "Conversation compacted",
                  "timestamp": "2026-09-28T09:00:30Z"}
    s1.write_text(s1_text + transcript_records(compaction))
    own = run(root, "heron plan", environment={"CLAUDE_CODE_SESSION_ID": "s1"})
    check("after a compaction, the running agent-session's records from before it are searched and those "
          "since are left out, and the closing line says so",
          own.returncode == 0 and "2026-09-28T09:00:00Z  session-dialogs  ned-box  prime-intellect" in own.stdout
          and "user-messages  ned-box  prime-intellect" not in own.stdout
          and "since its last compaction at 2026-09-28T09:00:30Z" in own.stdout, own.stdout)
    live = Path(scratch) / "home" / ".claude" / "projects" / "-home-nedlern-agents-prime-intellect" / "s1.jsonl"
    write(live, s1_text + transcript_records(dict(compaction, timestamp="2026-09-28T08:58:00Z"),
                                             dict(compaction, timestamp="2026-09-28T08:59:00Z"),
                                             dict(compaction, timestamp="2026-09-28T09:05:00Z", isSidechain=True)))
    own = run(root, "heron plan", environment={"CLAUDE_CODE_SESSION_ID": "s1"})
    check("the last compaction is read from the live transcript when there is one, and a subagent's is not "
          "the session's",
          "prime-intellect" not in own.stdout.split("Hits")[0]
          and "since its last compaction at 2026-09-28T08:59:00Z" in own.stdout, own.stdout)
    live.unlink()
    own = run(root, "heron plan", "--own-session", "s1", "--own-session-compacted-at", "2026-09-28T09:02:00Z")
    check("ned-box's copy takes the compaction time the Mac's copy passes, since it cannot read the Mac's live "
          "transcript",
          "2026-09-28T09:01:00Z  user-messages  ned-box  prime-intellect" in own.stdout
          and "since its last compaction at 2026-09-28T09:02:00Z" in own.stdout, own.stdout)
    live.mkdir()
    own = run(root, "heron plan", environment={"CLAUDE_CODE_SESSION_ID": "s1"})
    live.rmdir()
    check("a transcript that cannot be read for its last compaction leaves the agent-session out whole, "
          "and a FAILED line says so",
          own.returncode == 2 and "to find its last compaction, so all of its records were left out" in own.stderr
          and "prime-intellect" not in own.stdout.split("Hits")[0], own.stdout + own.stderr)
    write(root / "session-dialogs" / "ned-box" / "-home-nedlern-agents-prime-intellect" / "s1-dialog-complete.md",
          "# Complete session dialog\n\n## Agent\n\nShall we start the heron plan?\n\n## Agent\n\n"
          "heron plan said nowhere in the transcript\n", mtime=DIALOG_IMPORTED_AT)
    own = run(root, "heron plan", "--kind", "session-dialogs", environment={"CLAUDE_CODE_SESSION_ID": "s1"})
    check("after a compaction, a dialog hit of the running agent-session not dated by its turn is left out, "
          "since it cannot be placed before the compaction",
          "said nowhere" not in own.stdout and "2026-09-28T09:00:00Z" in own.stdout, own.stdout)
    write(root / "session-dialogs" / "ned-box" / "-home-nedlern-agents-prime-intellect" / "s1-dialog-complete.md",
          "# Complete session dialog\n\n## Agent\n\nShall we start the heron plan?\n", mtime=DIALOG_IMPORTED_AT)
    s1.write_text(s1_text)
    os.utime(s1, (epoch("2026-10-05"), epoch("2026-10-05")))

    write(root / "walk" / "a-tie-2026-09-01.md", "kingfisher\n")
    write(root / "walk" / "b-tie-2026-09-01.md", "kingfisher\n")
    # ripgrep's own order would hide a missing tie-break, so it is made to list files in reverse.
    reversed_rg = stub(scratch, "rg-reverse-order", 'exec rg --sortr path "$@"\n')
    first = run(root, "kingfisher", "--limit", "1", environment={PREFIX + "RIPGREP_PROGRAM_OVERRIDE": reversed_rg})
    second = run(root, "kingfisher", "--limit", "1", "--skip", "1",
                 environment={PREFIX + "RIPGREP_PROGRAM_OVERRIDE": reversed_rg})
    (root / "walk" / "a-tie-2026-09-01.md").unlink()
    (root / "walk" / "b-tie-2026-09-01.md").unlink()
    check("hits with the same date keep one order, by file, so --skip pages through them",
          "a-tie-2026-09-01.md" in first.stdout and "b-tie-2026-09-01.md" in second.stdout,
          first.stdout + second.stdout)

    write(root / "session-dialogs" / ".dialogs-written-by-extractor-sha256", "heron plan\n")
    result = run(root, "heron plan", "--kind", "session-dialogs")
    (root / "session-dialogs" / ".dialogs-written-by-extractor-sha256").unlink()
    check("a file in session-dialogs/ that is not a session dialog is passed over",
          result.returncode == 0 and "sha256" not in result.stdout and "Traceback" not in result.stderr,
          result.stdout + result.stderr)

    answered = root / "transcripts" / "ned-box" / "projects" / "-home-nedlern-agents-y" / "s7.jsonl"
    write(answered, transcript_records(agent("Ship it?", "2026-10-03T00:00:00Z"),
                                       typed("yes", "2026-10-03T00:01:00Z")))
    result = run(root, "^yes$", "--kind", "user-messages")
    answered.unlink()
    check("a pattern anchored to a whole message finds that message in the transcripts",
          result.returncode == 0 and "USER: yes" in result.stdout, result.stdout + result.stderr)

    spoken = root / "transcripts" / "ned-box" / "projects" / "-home-nedlern-agents-y" / "s10.jsonl"
    write(spoken, transcript_records(agent("heron words of the agent", "2026-10-03T00:00:00Z"),
                                     typed("heron words of the user", "2026-10-03T00:01:00Z")))
    finding = run(root, "heron words", "--kind", "user-messages")
    spoken.unlink()
    check("user-messages finds the user's words in a transcript and not the agent's",
          finding.returncode == 0 and "USER: heron words of the user" in finding.stdout
          and "of the agent" not in finding.stdout, finding.stdout + finding.stderr)

    escaped = root / "transcripts" / "ned-box" / "projects" / "-home-nedlern-agents-y" / "s11.jsonl"
    write(escaped, transcript_records(typed("merge it\nplease now", "2026-10-03T00:02:00Z"),
                                      typed('say "hi" to the\tgatekeeper', "2026-10-03T00:03:00Z"),
                                      typed("path C:\\logs here", "2026-10-03T00:04:00Z")))
    for pattern, expected in ((r"merge it\s+please", "merge it please now"),
                              ('say "hi', 'say "hi" to the gatekeeper'),
                              (r"the.gatekeeper", 'say "hi" to the gatekeeper'),
                              (r"C:\\logs", "path C:\\logs here")):
        finding = run(root, pattern, "--kind", "user-messages")
        check(f"a pattern that matches what JSON escapes finds the message, {pattern}",
              finding.returncode == 0 and f"USER: {expected}" in finding.stdout, finding.stdout + finding.stderr)
    escaped.unlink()

    for locked_directory in (root / "transcripts" / "mac" / "projects",
                             root / "transcripts" / "ned-box" / "projects" / "-home-nedlern-agents-prime-intellect"):
        locked_directory.chmod(0)
        finding = run(root, r"heron\s+plan", "--kind", "user-messages")
        locked_directory.chmod(0o755)
        check(f"a transcript directory that cannot be listed is a failure, {locked_directory.name}",
              finding.returncode == 2 and f"could not list the transcripts in {locked_directory}" in finding.stderr,
              finding.stderr)

    late = root / "transcripts" / "ned-box" / "projects" / "-home-nedlern-agents-y" / "s12.jsonl"
    write(late, transcript_records(typed("heron from the future", "2026-10-09T00:00:00Z")), mtime=epoch("2026-10-02"))
    finding = run(root, "heron from the future", "--kind", "user-messages", "--since", "2026-10-01")
    late.unlink()
    check("a message dated after its transcript's modification time is reported when --since relies on it",
          finding.returncode == 2 and "after its modification time" in finding.stderr, finding.stderr)

    hidden = root / "session-dialogs" / "ned-box" / "-home-nedlern-agents-prime-intellect" / "s1-dialog-complete.md"
    hidden_transcript = root / "transcripts" / "ned-box" / "projects" / "-home-nedlern-agents-prime-intellect" / "s1.jsonl"
    hidden_transcript.chmod(0)
    finding = run(root, "start the heron plan", "--kind", "session-dialogs")
    hidden_transcript.chmod(0o644)
    check("a session dialog whose transcript cannot be read is a failure, not an undated hit",
          finding.returncode == 2 and "to date the session dialog " in finding.stderr
          and "to date the session dialog's hits by their turns" in finding.stderr
          and str(hidden) in finding.stderr, finding.stderr)

    walk_file = root / "walk" / "heron-walk-2026-10-01-minutes.md"
    header_match = json.dumps({"type": "match", "data": {
        "path": {"text": str(walk_file)}, "lines": {"text": "heron\n"}, "line_number": 5,
        "submatches": [{"start": 0}]}})
    header_reporter = stub(scratch, "rg-reports-locked-walk", f"printf '%s\\n' '{header_match}'\n")
    walk_file.chmod(0)
    finding = run(root, "heron", "--kind", "walk", environment={PREFIX + "RIPGREP_PROGRAM_OVERRIDE": header_reporter})
    walk_file.chmod(0o644)
    check("a walk file whose header cannot be read for its agent-seat is a failure",
          finding.returncode == 2 and "for its agent-seat" in finding.stderr, finding.stderr)

    probe = subprocess.run([sys.executable, "-c", f"""
import importlib.util, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("search", {str(PROGRAM)!r})
search = importlib.util.module_from_spec(spec)
spec.loader.exec_module(search)
def unreadable(transcript):
    raise PermissionError(13, "Permission denied")
search.session_start = unreadable
search.session_last_activity = lambda transcript: "2026-10-05T10:00:00Z"
dialog = {str(root / "session-dialogs" / "ned-box" / "-home-nedlern-agents-prime-intellect" / "s1-dialog-complete.md")!r}
hit = {{"kind": "session-dialogs", "path": dialog, "machine": "ned-box",
        "project_key": "-home-nedlern-agents-prime-intellect", "line": 1}}
failures = []
search.dated_file_hits([hit], Path({str(root)!r}), "", "", None, "2026-09-30", failures)
print(failures)
"""], capture_output=True, text=True)
    check("a session dialog's transcript that cannot be read for the session's start is a failure",
          "for the start of the session dialog" in probe.stdout, probe.stdout + probe.stderr)

    wide = write(root / "walk" / "wide-2026-10-02.md", "é" * 400 + " heron tail\n")
    result = run(root, "heron tail", "--kind", "walk")
    wide.unlink()
    check("a match after multibyte text is shown in its excerpt",
          result.returncode == 0 and "heron tail" in result.stdout.split("wide-2026-10-02.md")[1],
          result.stdout)
    result = run(root, "heron plan", "--limit", "2")
    check("--limit caps the hits and the closing line says how to see the rest",
          len(hit_headers(result.stdout)) == 2 and "rerun with --skip 2" in result.stdout,
          result.stdout)
    second = run(root, "heron plan", "--limit", "2", "--skip", "2")
    check("--skip shows the next hits",
          hit_headers(second.stdout) and hit_headers(second.stdout)[0] not in hit_headers(result.stdout)
          and "Hits 3-4 of" in second.stdout, second.stdout)

    result = run(root, "heron plan", "--seat", "prime-intellect")
    kinds = {header.split("  ")[1] for header in hit_headers(result.stdout)}
    check("--seat keeps only that agent-seat's session dialogs and user's messages",
          kinds == {"session-dialogs", "user-messages"}
          and "fleet-restart-at-login" not in result.stdout, result.stdout)
    result = run(root, "heron plan", "--machine", "mac")
    check("--machine keeps only that machine's sessions",
          hit_headers(result.stdout) and all("  mac  " in h for h in hit_headers(result.stdout)),
          result.stdout)

    result = run(root, "heron plan", "--since", "2026-09-01", "--until", "2026-09-30")
    headers = hit_headers(result.stdout)
    check("--since and --until bound the hits' dates",
          not any(h.startswith("2026-08") or h.startswith("2026-10-07") or h.startswith("2026-10-01")
                  for h in headers)
          and any(h.startswith("2026-09-28") for h in headers)
          and any(h.startswith("2026-09-20") for h in headers), headers)
    check("a session dialog hit whose turn is within the window is kept though its session's last "
          "activity is after it",
          any("session-dialogs  ned-box  prime-intellect" in h for h in headers), headers)
    result = run(root, "heron plan", "--until", "2026-09-27", "--kind", "session-dialogs")
    check("a session dialog whose session began after --until is left out",
          result.returncode == 1 and not hit_headers(result.stdout), result.stdout)

    orphan = root / "session-dialogs" / "ned-box" / "-home-nedlern-agents-orphan" / "s5-dialog-complete.md"
    write(orphan, "## User\n\nheron orphan\n", mtime=epoch("2026-10-09"))
    result = run(root, "heron orphan", "--until", "2026-09-01")
    orphan.unlink()
    check("a session dialog whose transcript is missing is kept, since nothing dates its start",
          result.returncode == 0 and "orphan" in result.stdout, result.stdout + result.stderr)

    result = run(root, "no such words anywhere")
    check("nothing found exits 1 with no failure, and says what was searched",
          result.returncode == 1 and "Searched:" in result.stdout and not result.stderr,
          f"{result.returncode} {result.stdout} {result.stderr}")

    result = run(root, "--", "-heron")
    check("a pattern opening with a dash is read as the pattern after --",
          result.returncode == 1 and not result.stderr, result.stderr)

    result = run(root, "heron", "--since", "2026-13-40")
    check("a malformed date is refused", result.returncode == 2 and "YYYY-MM-DD" in result.stderr,
          result.stderr)

    # Parallel reading and the early stop: many transcripts, one with old messages but a recent
    # modification time, and messages in the same second as their transcript's modification time.
    many = Path(scratch) / "many"
    build_store(many)
    for number in range(40):
        day = f"2026-07-{1 + number % 28:02d}"
        stamp = f"{day}T10:{number:02d}:00.500Z"
        touched = epoch(day) - 2 * 3600 + number * 60 if number != 7 else epoch("2026-07-30")
        write(many / "transcripts" / "ned-box" / "projects" / f"-home-nedlern-agents-seat{number % 3}"
              / f"t{number}.jsonl",
              transcript_records(typed(f"heron plan number {number}", stamp),
                                 typed(f"heron plan again {number}", stamp.replace(".500Z", ".900Z"))),
              mtime=touched)
    write(many / "transcripts" / "ned-box" / "projects" / "-home-nedlern-agents-seat0" / "t7.jsonl",
          transcript_records(typed("heron plan from long ago", "2026-06-01T00:00:00Z"),
                             typed("heron plan newest of all", "2026-07-29T23:00:00Z")),
          mtime=epoch("2026-07-30"))
    everything = run(many, "heron plan", "--limit", "0", "--jobs", "1")
    every_hit = everything.stdout.split("\n\nHits ")[0].split("\n\n")
    for arguments in (["--limit", "5"], ["--limit", "7", "--skip", "3"], ["--limit", "0"],
                      ["--kind", "user-messages", "--limit", "4"], ["--seat", "seat1", "--limit", "3"]):
        sequential = run(many, "heron plan", "--jobs", "1", *arguments)
        parallel = run(many, "heron plan", "--jobs", "4", *arguments)
        check(f"parallel and sequential reading print the same output, {' '.join(arguments)}",
              (parallel.returncode, parallel.stdout, parallel.stderr)
              == (sequential.returncode, sequential.stdout, sequential.stderr),
              f"\n--- sequential\n{sequential.stdout}{sequential.stderr}\n--- parallel\n{parallel.stdout}{parallel.stderr}")
    paged = run(many, "heron plan", "--limit", "7", "--skip", "3")
    check("reading stops early once older transcripts cannot change the page",
          "older transcripts were not read" in paged.stdout, paged.stdout)
    check("the page read with an early stop is the same page a full read gives",
          paged.stdout.split("\n\nHits ")[0].split("\n\n") == every_hit[3:10],
          f"\n{paged.stdout}\n--- full read's hits 4-10\n" + "\n\n".join(every_hit[3:10]))
    check("a transcript with a recent modification time is read before older ones",
          "heron plan newest of all" in paged.stdout or "heron plan newest of all" in "".join(every_hit[:3]),
          paged.stdout)

    late_in_early_stop = (many / "transcripts" / "ned-box" / "projects" / "-home-nedlern-agents-seat0"
                          / "late.jsonl")
    write(late_in_early_stop, transcript_records(typed("heron plan dated after its file", "2026-08-15T00:00:00Z")),
          mtime=epoch("2026-07-31"))
    stopped = run(many, "heron plan", "--kind", "user-messages", "--limit", "3")
    late_in_early_stop.unlink()
    check("a message dated after its transcript's modification time is reported when the early stop relies on it",
          "older transcripts were not read" in stopped.stdout and stopped.returncode == 2
          and "after its modification time" in stopped.stderr, stopped.stdout + stopped.stderr)

    tabbed = write(root / "transcripts" / "ned-box" / "projects" / "-home-nedlern-agents-x" / "tabbed.jsonl",
                   transcript_records(typed("heron\tplan with a tab", "2026-10-03T00:00:00Z")))
    result = run(root, "heron\tplan", "--kind", "user-messages")
    tabbed.unlink()
    check("a pattern holding a literal control character finds the message JSON stores escaped",
          result.returncode == 0 and "plan with a tab" in result.stdout, result.stdout + result.stderr)

    session_dates = subprocess.run([sys.executable, "-c", f"""
import importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location("search", {str(PROGRAM)!r})
search = importlib.util.module_from_spec(spec)
spec.loader.exec_module(search)
missing = Path({str(Path(scratch) / "no-such-transcript.jsonl")!r})
locked = Path({str(Path(scratch) / "locked-transcript.jsonl")!r})
locked.write_text('{{"timestamp": "2026-10-01T00:00:00Z"}}\\n')
locked.chmod(0)
for function in (search.session_start, search.session_last_activity):
    print(function.__name__, "missing", repr(function(missing)))
    try:
        function(locked)
        print(function.__name__, "locked", "returned")
    except PermissionError:
        print(function.__name__, "locked", "raised")
locked.chmod(0o644)
"""], capture_output=True, text=True)
    check("session_start and session_last_activity give no date for a missing transcript, "
          "and raise for one that cannot be read",
          session_dates.stdout.split("\n")[:4] == ["session_start missing ''", "session_start locked raised",
                                                   "session_last_activity missing ''",
                                                   "session_last_activity locked raised"],
          session_dates.stdout + session_dates.stderr)

    # Failures.
    result = run(Path(scratch) / "absent", "heron")
    check("a missing log-store on ned-box is a failure, not an empty result",
          result.returncode == 2 and "FAILED: there is no log-store" in result.stderr, result.stderr)

    partial = Path(scratch) / "partial"
    build_store(partial)
    shutil.rmtree(partial / "analysis")
    result = run(partial, "heron plan")
    check("a missing kind directory is a failure, and the other kinds' hits are still shown",
          result.returncode == 2 and "has no" in result.stderr and "analysis" in result.stderr
          and "walk" in result.stdout, result.stderr)
    result = run(partial, "no-record-holds-this-pattern-zq")
    closing = result.stderr.rstrip().splitlines()[-1] if result.stderr.strip() else ""
    check("with failures and no hit printed, the closing line says a match may be in the failed records",
          result.returncode == 2 and closing.startswith("No hit was printed")
          and "do not say nothing matched" in closing and "Each hit printed above" not in result.stderr,
          result.stderr)

    unreadable = Path(scratch) / "unreadable"
    build_store(unreadable)
    locked = unreadable / "walk" / "heron-walk-2026-10-01-minutes.md"
    locked.chmod(0)
    result = run(unreadable, "heron plan")
    locked.chmod(0o644)
    check("a file ripgrep cannot read is a failure",
          result.returncode == 2 and "FAILED: ripgrep could not search everything" in result.stderr
          and "Permission denied" in result.stderr, result.stderr)
    check("after the FAILED lines, one closing line says whether the hits shown hold and what to tell the user",
          result.stderr.rstrip().splitlines()[-1].startswith("Each hit printed above is a real match")
          and "do not change the path's permissions" in result.stderr and "walk" in result.stdout, result.stderr)
    check("the closing line says what to tell the user, a directory's whole tree included, and which remedies to run",
          "which leaves out everything under it" in result.stderr.splitlines()[-1]
          and "a record not dated" in result.stderr.splitlines()[-1]
          and "run it if it reruns this search" in result.stderr.splitlines()[-1], result.stderr)
    check("with hits printed, the closing line does not say no hit was printed",
          "No hit was printed" not in result.stderr, result.stderr)
    clean = run(unreadable, "heron plan")
    check("a search with no failures prints no closing line about failures",
          clean.returncode == 0 and "Each hit printed above" not in clean.stderr, clean.stderr)

    result = run(root, "heron", environment={PREFIX + "RIPGREP_PROGRAM_OVERRIDE": str(Path(scratch) / "no-rg")})
    check("ripgrep missing is a failure that says how to install it",
          result.returncode == 2 and "ripgrep" in result.stderr and "apt install ripgrep" in result.stderr,
          result.stderr)

    silent = stub(scratch, "rg-silent-failure", "exit 3\n")
    result = run(root, "heron", environment={PREFIX + "RIPGREP_PROGRAM_OVERRIDE": silent})
    check("ripgrep failing without a word is a failure",
          result.returncode == 2 and "ripgrep exited 3 and said nothing" in result.stderr, result.stderr)

    locked_transcript = root / "transcripts" / "ned-box" / "projects" / "-home-nedlern-agents-x" / "s9.jsonl"
    write(locked_transcript, transcript_records(typed("heron", "2026-10-02T00:00:00Z")))
    locked_transcript.chmod(0)
    lister = stub(scratch, "rg-lists-locked-transcript", f"echo '{locked_transcript}'\n")
    result = run(root, "heron", "--kind", "user-messages",
                 environment={PREFIX + "RIPGREP_PROGRAM_OVERRIDE": lister})
    locked_transcript.chmod(0o644)
    locked_transcript.unlink()
    check("a transcript the reader cannot read is a failure",
          result.returncode == 2 and "could not read the transcript" in result.stderr, result.stderr)

    gone = [root / "transcripts" / "ned-box" / "projects" / "-home-nedlern-agents-x" / f"gone-{letter}.jsonl"
            for letter in "ab"]
    gone_lister = stub(scratch, "rg-lists-gone-transcripts", "".join(f"echo '{path}'\n" for path in reversed(gone)))
    result = run(root, "heron", "--kind", "user-messages",
                 environment={PREFIX + "RIPGREP_PROGRAM_OVERRIDE": gone_lister})
    reported = [line for line in result.stderr.splitlines() if "could not read the transcript" in line]
    check("transcripts that vanish before they are read are failures, reported in path order",
          result.returncode == 2 and len(reported) == 2 and "gone-a" in reported[0] and "gone-b" in reported[1],
          result.stderr)

    vanished = root / "walk" / "vanished-walk-minutes.md"
    match = json.dumps({"type": "match", "data": {
        "path": {"text": str(vanished)}, "lines": {"text": "heron\n"}, "line_number": 1,
        "submatches": [{"start": 0}]}})
    reporter = stub(scratch, "rg-reports-vanished-file", f"printf '%s\\n' '{match}'\n")
    result = run(root, "heron", "--kind", "walk", environment={PREFIX + "RIPGREP_PROGRAM_OVERRIDE": reporter})
    check("a hit whose file's date cannot be read is a failure",
          result.returncode == 2 and "could not read the date of" in result.stderr, result.stderr)

    result = run(root, r"heron\p{L}")
    check("a pattern Python cannot read is a failure for the user's messages",
          result.returncode == 2 and "the user's messages were not searched" in result.stderr, result.stderr)

    no_ned_box = stub(scratch, "ssh-unreachable", "echo 'ssh: connect to host ned-box: No route to host' >&2\nexit 255\n")
    result = run(Path(scratch) / "absent", "heron",
                 environment={PREFIX + "THIS_MACHINE_OVERRIDE": "mac", PREFIX + "SSH_PROGRAM_OVERRIDE": no_ned_box})
    check("from the Mac, ned-box unreachable is a failure that names the remedy",
          result.returncode == 2 and "No route to host" in result.stderr
          and "ssh nedlern@ned-box true" in result.stderr, result.stderr)

    result = run(Path(scratch) / "absent", "heron",
                 environment={PREFIX + "THIS_MACHINE_OVERRIDE": "mac",
                              PREFIX + "SSH_PROGRAM_OVERRIDE": str(Path(scratch) / "no-ssh")})
    check("from the Mac, ssh missing is a failure",
          result.returncode == 2 and "ssh is not installed" in result.stderr, result.stderr)

    echoing = stub(scratch, "ssh-echoes", 'for a in "$@"; do echo "ARG:$a"; done\nexit 1\n')
    result = run(Path(scratch) / "absent", "heron's plan", "--seat", "prime",
                 environment={PREFIX + "THIS_MACHINE_OVERRIDE": "mac", PREFIX + "SSH_PROGRAM_OVERRIDE": echoing})
    check("from the Mac, the program runs on ned-box with the same arguments, and passes its exit through",
          result.returncode == 1 and "ARG:nedlern@ned-box" in result.stdout
          and ("ARG:python3 /home/nedlern/Projects/nedschorus/scripts/"
               "log-store-past-discussions-regex-search-newest-first.py "
               "--own-session '' 'heron'\"'\"'s plan' --seat prime") in result.stdout.splitlines(), result.stdout)
    result = run(Path(scratch) / "absent", "heron",
                 environment={PREFIX + "THIS_MACHINE_OVERRIDE": "mac", PREFIX + "SSH_PROGRAM_OVERRIDE": echoing,
                              "CLAUDE_CODE_SESSION_ID": "mac-session-1"})
    check("from the Mac, the running agent-session is passed to ned-box's copy, which cannot see it",
          any(line.endswith("newest-first.py --own-session mac-session-1 heron")
              for line in result.stdout.splitlines()), result.stdout)
    mac_live = write(Path(scratch) / "home" / ".claude" / "projects" / "-Users-el-agents-x" / "mac-session-1.jsonl",
                     transcript_records({"type": "system", "subtype": "compact_boundary",
                                         "timestamp": "2026-10-09T10:00:00Z"}))
    result = run(Path(scratch) / "absent", "heron",
                 environment={PREFIX + "THIS_MACHINE_OVERRIDE": "mac", PREFIX + "SSH_PROGRAM_OVERRIDE": echoing,
                              "CLAUDE_CODE_SESSION_ID": "mac-session-1"})
    mac_live.unlink()
    check("from the Mac, the running agent-session's last compaction, read from the Mac's live transcript, "
          "is passed to ned-box's copy",
          any(line.endswith("newest-first.py --own-session mac-session-1 --own-session-compacted-at "
                            "2026-10-09T10:00:00Z heron") for line in result.stdout.splitlines()), result.stdout)
    result = run(Path(scratch) / "absent", "--", "-heron",
                 environment={PREFIX + "THIS_MACHINE_OVERRIDE": "mac", PREFIX + "SSH_PROGRAM_OVERRIDE": echoing,
                              "CLAUDE_CODE_SESSION_ID": "mac-session-1"})
    check("from the Mac, a pattern after -- is still the pattern on ned-box, since the session goes before it",
          any(line.endswith("newest-first.py --own-session mac-session-1 -- -heron")
              for line in result.stdout.splitlines()), result.stdout)

print(f"{'FAILED' if failures else 'all cases passed'}: {len(failures)} failure(s)")
sys.exit(1 if failures else 0)
