#!/usr/bin/env python3
"""Tests for watch-agent-dialogs.py.

Run: python3 scripts/watch-agent-dialogs-test.py
Prints one line per case and exits non-zero if any case fails.

Every case builds fixture agents-root and projects-root trees in a
temporary directory and runs the watcher as a subprocess against them, so
the tests never read a real session and never touch ~/.claude. A reader
thread drains the watcher's stdout pipe as it flows, which is also what
proves the flushing: every "a line appears mid-run" wait would hang on a
buffered stdout.

Synchronization without sleeps: seats are scanned in name order, so a
sacrificial "zz-..." seat with no transcript scans last, and its "no
transcript found" line marks the startup scan complete for every seat
before it.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

WATCH_SCRIPT = Path(__file__).with_name("watch-agent-dialogs.py")

# The script's own project-directory mangle, so fixture directory names can
# never drift from what the watcher computes.
_spec = importlib.util.spec_from_file_location("watch_agent_dialogs", WATCH_SCRIPT)
watcher_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(watcher_module)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def assistant_text(text):
    return {"type": "assistant",
            "message": {"role": "assistant",
                        "content": [{"type": "text", "text": text}]}}


def assistant_tool_use(name, tool_input):
    return {"type": "assistant",
            "message": {"role": "assistant",
                        "content": [{"type": "tool_use", "id": "toolu_01",
                                     "name": name, "input": tool_input}]}}


def user_text(content):
    return {"type": "user", "message": {"role": "user", "content": content}}


def write_transcript(project_directory, name, records, mtime=None):
    project_directory.mkdir(parents=True, exist_ok=True)
    path = project_directory / name
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            if isinstance(record, str):
                handle.write(record + "\n")
            else:
                handle.write(json.dumps(record) + "\n")
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def append_record(path, record):
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


class WatcherProcess:
    """The watcher as a subprocess, its stdout drained by a thread."""

    def __init__(self, *flags, cwd=None):
        self.process = subprocess.Popen(
            [sys.executable, str(WATCH_SCRIPT),
             "--rescan-seconds", "0.3", "--poll-seconds", "0.05", *flags],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", cwd=cwd,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        self.lines = []
        self._thread = threading.Thread(target=self._drain, daemon=True)
        self._thread.start()

    def _drain(self):
        for line in self.process.stdout:
            self.lines.append(line.rstrip("\n"))

    def wait_for(self, fragment, timeout=10.0):
        """True once some line contains the fragment; False on timeout."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if any(fragment in line for line in self.lines):
                return True
            time.sleep(0.02)
        return False

    def stop(self):
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self._thread.join(timeout=2)
        return list(self.lines)


with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch)

    def build_fixture(fixture_name, seat_names):
        """One agents-root + projects-root pair; returns (root, projects, seats)."""
        agents_root = scratch / fixture_name / "agents"
        projects_root = scratch / fixture_name / "projects"
        seats = {}
        for seat_name in seat_names:
            seat_path = agents_root / seat_name
            seat_path.mkdir(parents=True)
            seats[seat_name] = (
                seat_path,
                watcher_module.project_directory_for_seat(seat_path, projects_root))
        return agents_root, projects_root, seats

    # ------------------------------------------------------------------
    # Taxonomy: one transcript exercising every event shape, read whole
    # with --from-start.
    # ------------------------------------------------------------------
    agents_root, projects_root, seats = build_fixture(
        "taxonomy", ["alpha", "zz-sync"])
    alpha_path, alpha_project = seats["alpha"]
    _, zz_project = seats["zz-sync"]
    zz_project.mkdir(parents=True)  # exists but holds no session transcript

    long_text = "A" * 300
    records = [
        assistant_text("The merge is clean and I am proceeding."),
        {"type": "assistant",
         "message": {"role": "assistant",
                     "content": [{"type": "thinking",
                                  "thinking": "SECRET-THOUGHT-NEVER-SHOWN"},
                                 {"type": "text",
                                  "text": "line one\nline two"}]}},
        assistant_tool_use("Bash", {"command": "git push -u origin some-branch"}),
        assistant_tool_use("Bash", {"command": "ls -la /never/emitted"}),
        assistant_tool_use("SendMessage", {"to": "merge-seat",
                                           "message": "PR 74 is ready"}),
        user_text("please check the tests"),
        user_text([{"type": "tool_result", "tool_use_id": "toolu_01",
                    "content": "SECRET-TOOL-RESULT"},
                   {"type": "text", "text": "after the tool result"}]),
        user_text("<local-command-stdout>wrapped, skipped</local-command-stdout>"),
        user_text("  <system-reminder>indented wrapper, skipped</system-reminder>"),
        user_text("[SYSTEM task notification] a monitor line, skipped"),
        {"type": "assistant", "isApiErrorMessage": True,
         "message": {"role": "assistant",
                     "content": [{"type": "text",
                                  "text": "API Error: overloaded"}]}},
        "this line is not json {{{",
        assistant_text(long_text),
        assistant_text("TAXONOMY-DONE-MARKER"),
    ]
    write_transcript(alpha_project, "11111111-1111-1111-1111-111111111111.jsonl",
                     records, mtime=time.time() - 50)
    # A sidecar file, deliberately the newest thing in the directory: it must
    # never be followed.
    write_transcript(alpha_project, "agent-abc123.jsonl",
                     [assistant_text("FROM-SIDECAR-NEVER-EMITTED")],
                     mtime=time.time() + 100)

    watcher = WatcherProcess("--agents-root", str(agents_root),
                             "--projects-root", str(projects_root),
                             "--from-start", cwd=str(scratch))
    saw_marker = watcher.wait_for("TAXONOMY-DONE-MARKER")
    saw_sync = watcher.wait_for("zz-sync WATCH: no transcript found")
    lines = watcher.stop()
    everything = "\n".join(lines)

    check("assistant text becomes an AGENT line",
          "alpha AGENT: The merge is clean and I am proceeding." in lines,
          everything)
    check("newlines inside a snippet become ' ¶ '",
          "alpha AGENT: line one ¶ line two" in lines, everything)
    check("thinking blocks are never emitted",
          "SECRET-THOUGHT" not in everything, everything)
    check("a risky Bash command becomes a CMD line",
          "alpha CMD: git push -u origin some-branch" in lines, everything)
    check("a non-risky Bash command is not emitted",
          "/never/emitted" not in everything, everything)
    check("SendMessage becomes a MSG line",
          "alpha MSG→merge-seat: PR 74 is ready" in lines, everything)
    check("string user content becomes a USER line",
          "alpha USER: please check the tests" in lines, everything)
    check("tool_result blocks are skipped entirely",
          "SECRET-TOOL-RESULT" not in everything, everything)
    check("the text block beside a tool_result still speaks",
          "alpha USER: after the tool result" in lines, everything)
    check("user text starting with '<' is skipped",
          "wrapped, skipped" not in everything
          and "indented wrapper" not in everything, everything)
    check("user text starting with '[SYSTEM' is skipped",
          "a monitor line, skipped" not in everything, everything)
    check("isApiErrorMessage becomes API-ERROR and nothing else",
          "alpha API-ERROR" in lines and "API Error: overloaded" not in everything,
          everything)
    check("AGENT text is truncated to 250 chars",
          ("alpha AGENT: " + "A" * 250) in lines
          and "A" * 251 not in everything, everything)
    check("an unparseable line is skipped silently",
          saw_marker, everything)
    check("a non-UUID jsonl is never followed even when newest",
          "FROM-SIDECAR-NEVER-EMITTED" not in everything, everything)
    check("a seat with no session transcript reports it and stays watched",
          saw_sync, everything)

    # --snippet-chars scales AGENT/USER, CMD stays 200 and MSG stays 150.
    watcher = WatcherProcess("--agents-root", str(agents_root),
                             "--projects-root", str(projects_root),
                             "--from-start", "--snippet-chars", "10",
                             cwd=str(scratch))
    watcher.wait_for("TAXONOMY-DONE-MARKER"[:10])
    lines = watcher.stop()
    everything = "\n".join(lines)
    check("--snippet-chars shortens AGENT and USER snippets",
          "alpha AGENT: The merge " in lines
          and "alpha USER: please che" in lines, everything)
    check("--snippet-chars leaves CMD and MSG lengths alone",
          "alpha CMD: git push -u origin some-branch" in lines
          and "alpha MSG→merge-seat: PR 74 is ready" in lines, everything)

    # ------------------------------------------------------------------
    # Following live: startup at EOF, growth arrives promptly through the
    # pipe, rollover to a newer transcript is picked up from byte 0.
    # ------------------------------------------------------------------
    agents_root, projects_root, seats = build_fixture(
        "rollover", ["beta", "zz-sync"])
    beta_path, beta_project = seats["beta"]
    first_transcript = write_transcript(
        beta_project, "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.jsonl",
        [assistant_text("PREEXISTING-NEVER-WITHOUT-FROM-START")],
        mtime=time.time() - 50)

    watcher = WatcherProcess("--agents-root", str(agents_root),
                             "--projects-root", str(projects_root),
                             cwd=str(scratch))
    startup_done = watcher.wait_for("zz-sync WATCH: no transcript found")
    check("startup scan completes (sync seat reports in)", startup_done,
          "\n".join(watcher.lines))

    append_record(first_transcript, assistant_text("APPENDED-AFTER-START"))
    appended_arrived = watcher.wait_for("beta AGENT: APPENDED-AFTER-START",
                                        timeout=8.0)
    check("a line appended mid-run arrives promptly through the pipe",
          appended_arrived, "\n".join(watcher.lines))
    check("startup begins at EOF: pre-existing lines are not emitted",
          "PREEXISTING-NEVER-WITHOUT-FROM-START"
          not in "\n".join(watcher.lines), "\n".join(watcher.lines))

    # Rollover: a newer session transcript appears; the watcher must switch
    # and read it from byte 0. first_transcript is never touched again.
    write_transcript(beta_project, "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb.jsonl",
                     [assistant_text("NEWFILE-FIRST-LINE")],
                     mtime=time.time() + 5)
    switched = watcher.wait_for(
        "beta WATCH: switched to bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb.jsonl")
    new_content = watcher.wait_for("beta AGENT: NEWFILE-FIRST-LINE")
    lines = watcher.stop()
    check("a newer transcript mid-run yields the WATCH switch line",
          switched, "\n".join(lines))
    check("the new transcript is read from byte 0",
          new_content, "\n".join(lines))

    # --from-start emits the pre-existing lines it skipped above.
    watcher = WatcherProcess("--agents-root", str(agents_root),
                             "--projects-root", str(projects_root),
                             "--from-start", cwd=str(scratch))
    from_start_arrived = watcher.wait_for("NEWFILE-FIRST-LINE")
    lines = watcher.stop()
    check("--from-start emits a transcript's pre-existing lines",
          from_start_arrived, "\n".join(lines))

    # ------------------------------------------------------------------
    # Self-seat exclusion, --include-self, and mid-run seat discovery.
    # ------------------------------------------------------------------
    agents_root, projects_root, seats = build_fixture(
        "selfwatch", ["other", "selfseat"])
    self_path, self_project = seats["selfseat"]
    other_path, other_project = seats["other"]
    write_transcript(self_project, "cccccccc-cccc-cccc-cccc-cccccccccccc.jsonl",
                     [assistant_text("SELF-VOICE-LINE")])
    write_transcript(other_project, "dddddddd-dddd-dddd-dddd-dddddddddddd.jsonl",
                     [assistant_text("OTHER-VOICE-LINE")])

    watcher = WatcherProcess("--agents-root", str(agents_root),
                             "--projects-root", str(projects_root),
                             "--from-start", cwd=str(self_path))
    other_arrived = watcher.wait_for("other AGENT: OTHER-VOICE-LINE")

    # A seat created while the watcher runs is adopted at the next rescan,
    # its transcript read from byte 0.
    late_path = agents_root / "zz-late"
    late_path.mkdir()
    late_project = watcher_module.project_directory_for_seat(
        late_path, projects_root)
    write_transcript(late_project, "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee.jsonl",
                     [assistant_text("LATE-SEAT-LINE")])
    late_arrived = watcher.wait_for("zz-late AGENT: LATE-SEAT-LINE")
    lines = watcher.stop()
    check("the seat containing the working directory is excluded",
          other_arrived and "SELF-VOICE-LINE" not in "\n".join(lines),
          "\n".join(lines))
    check("a seat created mid-run is discovered and read from byte 0",
          late_arrived, "\n".join(lines))

    watcher = WatcherProcess("--agents-root", str(agents_root),
                             "--projects-root", str(projects_root),
                             "--from-start", "--include-self",
                             cwd=str(self_path))
    self_arrived = watcher.wait_for("selfseat AGENT: SELF-VOICE-LINE")
    lines = watcher.stop()
    check("--include-self watches the self seat after all",
          self_arrived, "\n".join(lines))

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
