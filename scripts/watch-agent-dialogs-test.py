#!/usr/bin/env python3
"""Tests for watch-agent-dialogs.py.

Run: python3 scripts/watch-agent-dialogs-test.py
Prints one line per case and exits non-zero if any case fails.

Most cases build fixture agents-root and projects-root trees in a temporary
directory and run the watcher as a subprocess against them, so the tests
never read a real session and never touch ~/.claude. A reader thread drains
the watcher's stdout pipe as it flows, which is also what proves the
flushing: every "a line appears mid-run" wait would hang on a buffered
stdout. A few cases are direct unit checks on the imported module — the
path-mangle expectations are HARD-CODED literals on purpose, so the suite
cannot mirror a future mangle bug by deriving fixtures from the function
under test.

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

# The script's own project-directory mangle, used for fixture directory
# names; the hard-coded mangle cases below keep this from drifting
# unnoticed alongside a harness change.
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


def append_record(path, record, mtime=None):
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")
    if mtime is not None:
        os.utime(path, (mtime, mtime))


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


def run_unit_cases():
    # ------------------------------------------------------------------
    # Project-directory mangle: HARD-CODED expectations against a path
    # rooted at a directory that exists on no machine, so resolve() passes
    # it through verbatim. Deliberately not derived from the function
    # under test — that is the whole point (harness v2.1.233 probed with
    # a real session: [^a-zA-Z0-9] becomes "-", underscores included).
    # ------------------------------------------------------------------
    def mangled_name(seat):
        return watcher_module.project_directory_for_seat(
            Path(seat), Path("/proj")).name

    check("mangle: underscore becomes dash (hard-coded, harness v2.1.233)",
          mangled_name("/mangle-probe-root/agents/mangle_probe")
          == "-mangle-probe-root-agents-mangle-probe",
          mangled_name("/mangle-probe-root/agents/mangle_probe"))
    check("mangle: plain dashed path (hard-coded)",
          mangled_name("/mangle-probe-root/agents/plain-seat")
          == "-mangle-probe-root-agents-plain-seat",
          mangled_name("/mangle-probe-root/agents/plain-seat"))
    check("mangle: dot becomes dash (hard-coded)",
          mangled_name("/mangle-probe-root/.claude/b")
          == "-mangle-probe-root--claude-b",
          mangled_name("/mangle-probe-root/.claude/b"))

    # ------------------------------------------------------------------
    # Agents-root default: ${NEDSCHORUS_AGENTS_ROOT:-~/agents}, as the
    # launchers resolve it. Resolving differently on a machine where the
    # variable is set means iterating a root no seat lives in — the watcher
    # then watches nothing, silently (user-ruled 2026-08-22: allowed
    # overrides must work). Both the function and the parser wiring are
    # pinned; the wiring case proves the env read happens per invocation.
    # ------------------------------------------------------------------
    saved_root = os.environ.get("NEDSCHORUS_AGENTS_ROOT")
    try:
        os.environ["NEDSCHORUS_AGENTS_ROOT"] = "/relocated/fleet-root"
        check("default_agents_root honors NEDSCHORUS_AGENTS_ROOT",
              watcher_module.default_agents_root() == Path("/relocated/fleet-root"),
              watcher_module.default_agents_root())
        check("parse_arguments defaults --agents-root from the variable",
              watcher_module.parse_arguments([]).agents_root == "/relocated/fleet-root",
              watcher_module.parse_arguments([]).agents_root)
        os.environ["NEDSCHORUS_AGENTS_ROOT"] = ""
        check("an empty NEDSCHORUS_AGENTS_ROOT falls back to ~/agents (the :- rule)",
              watcher_module.default_agents_root() == Path("~/agents").expanduser(),
              watcher_module.default_agents_root())
    finally:
        if saved_root is None:
            os.environ.pop("NEDSCHORUS_AGENTS_ROOT", None)
        else:
            os.environ["NEDSCHORUS_AGENTS_ROOT"] = saved_root

    # ------------------------------------------------------------------
    # Risky-command pattern: every claimed class, both directions.
    # ------------------------------------------------------------------
    pattern = watcher_module.RISKY_COMMAND_PATTERN

    def misses(commands):
        return [command for command in commands if not pattern.search(command)]

    def false_alarms(commands):
        return [command for command in commands if pattern.search(command)]

    check("risky pattern still catches the original forms",
          not misses(["git push", "git push -u origin some-branch",
                      "git merge feature", "git reset --hard HEAD~1",
                      "git worktree remove w", "git branch -d b",
                      "git branch -D b", "gh pr merge 1", "gh pr close 1",
                      "gh pr create --title t", "gh issue create",
                      "gh issue edit 3", "gh issue comment 3", "rm -rf x"]),
          str(misses(["git push", "gh pr merge 1", "rm -rf x"])))
    check("risky pattern catches gh pr comment/edit/review",
          not misses(["gh pr comment 74 --body ok", "gh pr edit 74",
                      "gh pr review 74 --approve"]),
          str(misses(["gh pr comment 74 --body ok", "gh pr edit 74",
                      "gh pr review 74 --approve"])))
    check("risky pattern catches gh issue close",
          not misses(["gh issue close 3"]), "gh issue close 3 missed")
    check("risky pattern catches rm flag-order variants",
          not misses(["rm -rf x", "rm -fr x", "rm -r -f x", "rm -f -r x",
                      "rm -vrf x"]),
          str(misses(["rm -rf x", "rm -fr x", "rm -r -f x", "rm -f -r x",
                      "rm -vrf x"])))
    check("risky pattern catches git with intervening options",
          not misses(["git -C /some/where push",
                      "git --git-dir=/r/.git push",
                      "git -C /w --git-dir=/r/.git push -u origin b",
                      "git -C /w merge feature"]),
          str(misses(["git -C /some/where push",
                      "git --git-dir=/r/.git push"])))
    check("risky pattern does not overmatch",
          not false_alarms(["rm -f x", "rm -r x", "rm file.txt", "rm -v x",
                            "gh pr view 12", "gh pr list", "gh issue view 3",
                            "gh issue list", "git log --oneline",
                            "git -C /x status", "git status",
                            "ls -la /never/emitted"]),
          str(false_alarms(["rm -f x", "gh pr view 12", "git -C /x status"])))


def run_bad_invocation_cases(agents_root, projects_root):
    """--poll-seconds/--rescan-seconds must be > 0, --snippet-chars >= 1:
    one stderr line, exit 2. Fixture roots are passed so a future reorder
    of main can never make these touch the real ~/agents."""
    for flags, label in [
            (["--poll-seconds", "0"], "--poll-seconds 0"),
            (["--poll-seconds", "-0.5"], "--poll-seconds -0.5"),
            (["--rescan-seconds", "0"], "--rescan-seconds 0"),
            (["--snippet-chars", "0"], "--snippet-chars 0")]:
        try:
            result = subprocess.run(
                [sys.executable, str(WATCH_SCRIPT),
                 "--agents-root", str(agents_root),
                 "--projects-root", str(projects_root), *flags],
                capture_output=True, text=True, timeout=15)
            ok = (result.returncode == 2
                  and len(result.stderr.strip().splitlines()) == 1)
            detail = f"rc={result.returncode} stderr={result.stderr!r}"
        except subprocess.TimeoutExpired:
            ok, detail = False, "still running after 15s — validation never fired"
        check(f"bad invocation {label} exits 2 with one stderr line", ok, detail)


def run_all_cases():
    run_unit_cases()

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

        run_bad_invocation_cases(agents_root, projects_root)

        long_text = "A" * 300
        many_newlines = "B\n" * 200  # folded, this exceeds every snippet limit
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
            assistant_tool_use("SendMessage", {"to": "merge-seat",
                                               "message": {"not": "a string"}}),
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
            assistant_text(many_newlines),
            assistant_text("TAXONOMY-DONE-MARKER"),
        ]
        write_transcript(alpha_project, "11111111-1111-1111-1111-111111111111.jsonl",
                         records, mtime=time.time() - 50)
        # A sidecar-style file, deliberately the newest thing in the
        # directory: it must never be followed.
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
        check("SendMessage with a non-string message emits 'to' and no repr",
              "alpha MSG→merge-seat: " in lines
              and "{'not'" not in everything, everything)
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
        folded_lines = [line for line in lines
                        if line.startswith("alpha AGENT: B ¶ B")]
        check("newlines fold before truncation, so 250 bounds the snippet",
              folded_lines
              and all(len(line) <= len("alpha AGENT: ") + 250
                      for line in folded_lines),
              str([len(line) for line in folded_lines]))
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

        # Rollover: a newer session transcript appears; the watcher must
        # switch and read it from byte 0.
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
        # Two live transcripts alternating as newest-by-mtime: switching
        # back must resume at the remembered offset, never replay from
        # byte 0. Explicit monotonic mtimes force each handover.
        # ------------------------------------------------------------------
        agents_root, projects_root, seats = build_fixture(
            "alternating", ["gamma", "zz-sync"])
        _, gamma_project = seats["gamma"]
        mtime_step = time.time()
        file_x = write_transcript(
            gamma_project, "ffffffff-ffff-ffff-ffff-ffffffffffff.jsonl",
            [assistant_text("ALT-X-LINE-1")], mtime=mtime_step)
        file_y = write_transcript(
            gamma_project, "99999999-9999-9999-9999-999999999999.jsonl",
            [assistant_text("ALT-Y-LINE-1")], mtime=mtime_step - 100)

        watcher = WatcherProcess("--agents-root", str(agents_root),
                                 "--projects-root", str(projects_root),
                                 "--from-start", cwd=str(scratch))
        watcher.wait_for("gamma AGENT: ALT-X-LINE-1")

        mtime_step += 10
        append_record(file_y, assistant_text("ALT-Y-LINE-2"), mtime=mtime_step)
        watcher.wait_for("gamma AGENT: ALT-Y-LINE-2")

        mtime_step += 10
        append_record(file_x, assistant_text("ALT-X-LINE-2"), mtime=mtime_step)
        watcher.wait_for("gamma AGENT: ALT-X-LINE-2")

        mtime_step += 10
        append_record(file_y, assistant_text("ALT-Y-LINE-3"), mtime=mtime_step)
        watcher.wait_for("gamma AGENT: ALT-Y-LINE-3")
        lines = watcher.stop()
        everything = "\n".join(lines)

        markers = ["ALT-X-LINE-1", "ALT-Y-LINE-1", "ALT-Y-LINE-2",
                   "ALT-X-LINE-2", "ALT-Y-LINE-3"]
        check("alternating transcripts: every new line in both files arrives",
              all(everything.count(marker) >= 1 for marker in markers),
              everything)
        agent_lines = [line for line in lines if line.startswith("gamma AGENT: ")]
        check("alternating transcripts: no line is ever emitted twice",
              len(agent_lines) == len(set(agent_lines))
              and all(everything.count(marker) == 1 for marker in markers),
              everything)
        check("alternating transcripts: the WATCH switch line fires both ways",
              "gamma WATCH: switched to 99999999-9999-9999-9999-999999999999.jsonl"
              in lines
              and "gamma WATCH: switched to ffffffff-ffff-ffff-ffff-ffffffffffff.jsonl"
              in lines, everything)

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

        # A seat created while the watcher runs is adopted at the next
        # rescan, its transcript read from byte 0.
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
        check("a seat's first acquisition mid-run announces 'following'",
              "zz-late WATCH: following eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee.jsonl"
              in lines
              and "zz-late WATCH: switched" not in "\n".join(lines),
              "\n".join(lines))

        watcher = WatcherProcess("--agents-root", str(agents_root),
                                 "--projects-root", str(projects_root),
                                 "--from-start", "--include-self",
                                 cwd=str(self_path))
        self_arrived = watcher.wait_for("selfseat AGENT: SELF-VOICE-LINE")
        lines = watcher.stop()
        check("--include-self watches the self seat after all",
              self_arrived, "\n".join(lines))


if __name__ == "__main__":
    run_all_cases()
    print()
    if failures:
        print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
        sys.exit(1)
    print("all cases passed")
