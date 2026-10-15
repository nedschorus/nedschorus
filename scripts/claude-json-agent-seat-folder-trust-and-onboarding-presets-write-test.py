#!/usr/bin/env python3
"""Tests for scripts/claude-json-agent-seat-folder-trust-and-onboarding-presets-write.py.

Every case writes inside a temporary directory, and each run of the script as a
program gets that directory as HOME, so no case reads or writes the real
~/.claude.json. How each launcher runs the script, and a write that fails
partway, are covered in scripts/launch-claude-pre-trust-step-test.py.

Run: python3 scripts/claude-json-agent-seat-folder-trust-and-onboarding-presets-write-test.py
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).with_name(
    "claude-json-agent-seat-folder-trust-and-onboarding-presets-write.py")
_spec = importlib.util.spec_from_file_location(
    "claude_json_agent_seat_folder_trust_and_onboarding_presets_write", SCRIPT)
presets = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(presets)
write = presets.claude_json_agent_seat_folder_trust_and_onboarding_presets_write

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def run_script(home: Path, *arguments):
    environment = {key: value for key, value in os.environ.items()
                   if key != "HOME"}
    environment["HOME"] = str(home)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run([sys.executable, str(SCRIPT), *arguments],
                          capture_output=True, text=True, check=False,
                          env=environment)


def temporary_leftovers(home: Path) -> list:
    return sorted(path.name for path in home.glob(".claude.json.*"))


def fully_preset(folder: str, theme: str = "light") -> dict:
    return {"projects": {folder: {"hasTrustDialogAccepted": True}},
            "hasCompletedOnboarding": True, "theme": theme}


def main() -> int:
    with tempfile.TemporaryDirectory(
            prefix="claude-json-presets-write-test-") as scratch:
        root = Path(scratch)

        # A machine with no ~/.claude.json yet.
        home = root / "fresh"
        home.mkdir()
        state = home / ".claude.json"
        wrote = write(state, "/seats/one")
        parsed = json.loads(state.read_text(encoding="utf-8"))
        check("no file: the file is written with the trust, onboarding and theme presets",
              wrote is True and parsed == fully_preset("/seats/one"), (wrote, parsed))
        check("no file: the new file is 0600, since it will hold credentials",
              state.stat().st_mode & 0o777 == 0o600, oct(state.stat().st_mode))

        # A second launch finds everything in place and writes nothing, so the
        # agent-sessions writing the same file are not raced for no reason.
        before = state.stat()
        wrote = write(state, "/seats/one")
        after = state.stat()
        check("everything already set: nothing is written (inode and mtime unchanged)",
              wrote is False and (after.st_ino, after.st_mtime_ns)
              == (before.st_ino, before.st_mtime_ns),
              (wrote, before.st_ino, after.st_ino))

        # Each preset alone being missing is enough to write.
        for case_name, settings in (
                ("the folder is not trusted",
                 {**fully_preset("/seats/one"),
                  "projects": {"/seats/one": {"hasTrustDialogAccepted": False}}}),
                ("hasCompletedOnboarding is false",
                 {**fully_preset("/seats/one"), "hasCompletedOnboarding": False}),
                ("hasCompletedOnboarding is absent",
                 {key: value for key, value in fully_preset("/seats/one").items()
                  if key != "hasCompletedOnboarding"}),
                ("no theme is set",
                 {key: value for key, value in fully_preset("/seats/one").items()
                  if key != "theme"})):
            state.write_text(json.dumps(settings), encoding="utf-8")
            wrote = write(state, "/seats/one")
            parsed = json.loads(state.read_text(encoding="utf-8"))
            check(f"only {case_name}: the file is written and then holds every preset",
                  wrote is True and parsed == fully_preset("/seats/one"), (wrote, parsed))

        # The harness's other keys, other projects and the user's own theme survive.
        home = root / "existing"
        home.mkdir()
        state = home / ".claude.json"
        state.write_text(json.dumps({
            "numStartups": 41,
            "oauthAccount": {"accountUuid": "not-a-real-uuid"},
            "theme": "dark",
            "hasCompletedOnboarding": False,
            "projects": {"/seats/old": {"hasTrustDialogAccepted": True,
                                        "history": ["an earlier session"]},
                         "/seats/one": {"history": ["kept"]}},
        }), encoding="utf-8")
        state.chmod(0o640)
        wrote = write(state, "/seats/one")
        parsed = json.loads(state.read_text(encoding="utf-8"))
        check("existing file: other keys and projects are kept, the set theme is kept",
              wrote is True and parsed == {
                  "numStartups": 41,
                  "oauthAccount": {"accountUuid": "not-a-real-uuid"},
                  "theme": "dark",
                  "hasCompletedOnboarding": True,
                  "projects": {"/seats/old": {"hasTrustDialogAccepted": True,
                                              "history": ["an earlier session"]},
                               "/seats/one": {"history": ["kept"],
                                              "hasTrustDialogAccepted": True}},
              }, parsed)
        check("existing file: its mode is kept (0640)",
              state.stat().st_mode & 0o777 == 0o640, oct(state.stat().st_mode))
        check("existing file: no temporary file is left", temporary_leftovers(home) == [],
              temporary_leftovers(home))

        # Run as a program: HOME picks the file, and ~ in the folder is HOME's.
        home = root / "program"
        home.mkdir()
        completed = run_script(home, "~/agents/seat-two")
        parsed = (json.loads((home / ".claude.json").read_text(encoding="utf-8"))
                  if (home / ".claude.json").exists() else None)
        check("as a program: exit 0, and HOME's ~/.claude.json trusts HOME's ~/agents/<seat>",
              completed.returncode == 0
              and parsed == fully_preset(f"{home}/agents/seat-two"),
              (completed.returncode, completed.stderr, parsed))
        completed = run_script(home)
        check("as a program, without the folder: exit 2 with the usage line",
              completed.returncode == 2 and "usage:" in completed.stderr,
              (completed.returncode, completed.stderr))
        for option in ("--help", "-h"):
            empty_home = root / f"help{option}"
            empty_home.mkdir()
            completed = run_script(empty_home, option)
            check(f"as a program, {option}: exit 0, usage on stdout, and nothing written",
                  completed.returncode == 0 and completed.stdout.startswith("usage:")
                  and list(empty_home.iterdir()) == [],
                  (completed.returncode, completed.stdout, list(empty_home.iterdir())))
        empty_home = root / "unknown-option"
        empty_home.mkdir()
        completed = run_script(empty_home, "--verbose")
        check("as a program, an unknown option: exit 2 with the usage line, and nothing written",
              completed.returncode == 2 and "usage:" in completed.stderr
              and list(empty_home.iterdir()) == [],
              (completed.returncode, completed.stderr, list(empty_home.iterdir())))

        # A file that is not a JSON object is never overwritten: it holds credentials.
        # Each case prints only the remedy that fits it, naming the backups by absolute path.
        for case_name, content, remedy, other_remedy in (
                ("not valid JSON", '{"oauthAccount": {"accountU',
                 "that is valid JSON, then launch again", "holds a JSON object"),
                ("a JSON array, not an object", "[]",
                 "that holds a JSON object, then launch again", "that is valid JSON")):
            home = root / f"unreadable-{len(content)}"
            home.mkdir()
            state = home / ".claude.json"
            state.write_text(content, encoding="utf-8")
            before = state.stat()
            try:
                write(state, "/seats/one")
                raised = None
            except presets.ClaudeJsonNotAJsonObjectError as error:
                raised = error
            check(f"{case_name}: the write raises, naming the file",
                  raised is not None and str(state) in str(raised), raised)
            completed = run_script(home, "/seats/one")
            after = state.stat()
            check(f"{case_name}: as a program, exit 1 with the cause and what to do on stderr",
                  completed.returncode == 1 and str(state) in completed.stderr
                  and "left unchanged" in completed.stderr,
                  (completed.returncode, completed.stderr))
            check(f"{case_name}: the one remedy that fits, naming {home}/.claude/backups/",
                  f"{home}/.claude/backups/ {remedy}" in completed.stderr
                  and other_remedy not in completed.stderr
                  and "~/.claude/backups/" not in completed.stderr
                  and "Otherwise" not in completed.stderr
                  and "Fix the cause" not in completed.stderr,
                  completed.stderr)
            check(f"{case_name}: the file is byte-identical and its inode unchanged, "
                  "with no temporary left",
                  state.read_text(encoding="utf-8") == content
                  and after.st_ino == before.st_ino
                  and temporary_leftovers(home) == [],
                  (state.read_text(encoding="utf-8"), temporary_leftovers(home)))

        # The onboarding-only write, which the handoff-supervisor makes before every
        # agent-session it launches: onboarding and theme, never a trust preset.
        onboarding_write = presets.claude_json_onboarding_presets_write
        home = root / "onboarding-only"
        home.mkdir()
        state = home / ".claude.json"
        logged_out = {"numStartups": 7, "theme": "dark",
                      "projects": {"/seats/one": {"history": ["kept"]}}}
        state.write_text(json.dumps(logged_out), encoding="utf-8")
        wrote = onboarding_write(state)
        parsed = json.loads(state.read_text(encoding="utf-8"))
        check("onboarding only: hasCompletedOnboarding is written, the set theme and "
              "every project are kept, and no folder is trusted",
              wrote is True and parsed == dict(logged_out, hasCompletedOnboarding=True),
              (wrote, parsed))
        before = state.stat()
        wrote = onboarding_write(state)
        after = state.stat()
        check("onboarding only, already set: nothing is written (inode and mtime unchanged)",
              wrote is False and (after.st_ino, after.st_mtime_ns)
              == (before.st_ino, before.st_mtime_ns), wrote)
        state.unlink()
        wrote = onboarding_write(state)
        parsed = json.loads(state.read_text(encoding="utf-8"))
        check("onboarding only, no file: the file holds onboarding and the theme, "
              "and no projects",
              wrote is True and parsed == {"hasCompletedOnboarding": True, "theme": "light"},
              (wrote, parsed))
        unparseable = '{"oauthAccount": {"accountU'
        state.write_text(unparseable, encoding="utf-8")
        try:
            onboarding_write(state)
            raised = None
        except presets.ClaudeJsonNotAJsonObjectError as error:
            raised = error
        check("onboarding only, not valid JSON: the write raises, naming the file, "
              "and the file is left as it was",
              raised is not None and str(state) in str(raised)
              and state.read_text(encoding="utf-8") == unparseable,
              (raised, state.read_text(encoding="utf-8")))

        # A write that cannot happen is reported, and the program exits 1.
        if os.geteuid() == 0:
            print("SKIP  unwritable HOME: running as root, which can write anywhere")
        else:
            home = root / "unwritable"
            home.mkdir()
            home.chmod(0o500)
            try:
                completed = run_script(home, "/seats/one")
            finally:
                home.chmod(0o700)
            check("unwritable HOME: as a program, exit 1 with the cause on stderr",
                  completed.returncode == 1 and "Permission denied" in completed.stderr
                  and "Traceback" not in completed.stderr,
                  (completed.returncode, completed.stderr))
            check("unwritable HOME: the remedy is to fix the cause, not to restore a backup",
                  "Fix the cause named above, then launch again." in completed.stderr
                  and "Restore" not in completed.stderr,
                  completed.stderr)

    print()
    if failures:
        print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
