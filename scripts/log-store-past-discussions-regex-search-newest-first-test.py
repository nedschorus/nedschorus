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
          mtime=epoch("2026-10-05"))
    write(root / "transcripts" / "ned-box" / "projects" / key / "s1.jsonl",
          transcript_records(agent("Shall we?", "2026-09-28T09:00:00Z"),
                             typed("go with the heron plan", "2026-09-28T09:01:00Z")),
          mtime=epoch("2026-10-05"))
    mac_key = "-Users-el-agents-fleet-restart-at-login"
    write(root / "session-dialogs" / "mac" / mac_key / "s2-dialog-complete.md",
          "## User\n\nheron plan on the Mac\n", mtime=epoch("2026-10-07"))
    write(root / "transcripts" / "mac" / "projects" / mac_key / "s2.jsonl",
          transcript_records(typed("heron plan on the Mac", "2026-10-07T08:00:00Z")),
          mtime=epoch("2026-10-07"))
    write(root / "transcripts" / "mac" / "projects" / mac_key / "s2" / "subagents" / "agent-x.jsonl",
          transcript_records(typed("heron plan inside a subagent", "2026-10-07T08:00:00Z")))


def run(root, *arguments, environment=None):
    env = dict(os.environ)
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
    check("a session dialog's date is labelled as its last activity",
          "2026-10-05T12:00:00Z (last activity)  session-dialogs" in result.stdout, result.stdout)
    check("a user's message carries the time he sent it",
          "2026-09-28T09:01:00Z  user-messages" in result.stdout, result.stdout)

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
    check("a session dialog active within the window is kept though its last activity is after it",
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

    unreadable = Path(scratch) / "unreadable"
    build_store(unreadable)
    locked = unreadable / "walk" / "heron-walk-2026-10-01-minutes.md"
    locked.chmod(0)
    result = run(unreadable, "heron plan")
    locked.chmod(0o644)
    check("a file ripgrep cannot read is a failure",
          result.returncode == 2 and "FAILED: ripgrep could not search everything" in result.stderr
          and "Permission denied" in result.stderr, result.stderr)

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
               "'heron'\"'\"'s plan' --seat prime") in result.stdout.splitlines(), result.stdout)

print(f"{'FAILED' if failures else 'all cases passed'}: {len(failures)} failure(s)")
sys.exit(1 if failures else 0)
