#!/usr/bin/env python3
"""Tests for empty-search-runs-locator-hook.py.

Run: python3 scripts/empty-search-runs-locator-hook-test.py
Prints one line per case and exits non-zero if any case fails.

Every case but the two that call summarize_answer runs the hook as a
program, the way Claude Code runs it: the payload on stdin, nothing expected
on stdout, exit 0. The payloads are the shapes a probe hook captured from
Claude Code 2.1.280 on 2026-09-24 (the module docstring names them), with
the paths changed, and five cases replay the captured payloads themselves.
The locator is a stand-in that counts its runs and prints a canned answer,
so the cases can say exactly what was recorded; the last case but one runs
the real locator over a throwaway directory, so the parser is held to the
locator's real output rather than to a copy of it.

THE FIRST CASES ARE THE POSITIVE ONES, deliberately: a hook never shown
able to fire says nothing when it stays silent.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().with_name(
    "empty-search-runs-locator-hook.py")
REAL_LOCATOR_PATH = Path(__file__).resolve().with_name(
    "locate-file-copies-across-machines.py")

HOOK_SPEC = importlib.util.spec_from_file_location(
    "empty_search_runs_locator_hook", SCRIPT_PATH)
HOOK = importlib.util.module_from_spec(HOOK_SPEC)
HOOK_SPEC.loader.exec_module(HOOK)

STUB_LOCATOR = r'''
import os, sys, time
with open(os.environ["STUB_RUNS_FILE"], "a") as handle:
    handle.write(repr(sys.argv[1:]) + "\n")
time.sleep(float(os.environ.get("STUB_SLEEP", "0")))
sys.stdout.write(os.environ.get("STUB_OUTPUT", ""))
sys.exit(int(os.environ.get("STUB_EXIT", "1")))
'''

FOUND_ANSWER = """locate-file-copies-across-machines: file names containing "plan", any case

Same name (plan.md), newest first:
  2026-09-24 18:11Z  mac checkouts /Users/el/agents/merge-lane/docs/plan.md (1.2 KB)
                     same content, 2026-09-20 10:00Z: mac git commit abc1234 ("x")

Candidates only, not counted as found: names containing "plan", any named plan.md first, then newest first:
  2026-09-23 12:00Z  ned-box log-store /home/nedlern/nedschorus-logs/seats/a/plan-draft.md (2 KB)
  2026-09-22 12:00Z  ned-box log-store /home/nedlern/nedschorus-logs/seats/b/planning.md (2 KB)
  ... and 7 more not shown

Searched:
  mac checkouts: /Users/el/agents

Took 2.1 s.
"""

INCOMPLETE_ANSWER = """locate-file-copies-across-machines: file names containing "plan", any case

Candidates only, not counted as found: names containing "plan", any named plan.md first, then newest first:
  2026-09-23 12:00Z  ned-box log-store /home/nedlern/nedschorus-logs/seats/a/plan-draft.md (2 KB)

Searched:
  ned-box checkouts: /home/nedlern/agents

NOT searched, or searched only in part:
  mac: no route from ned-box to the Mac is documented

Took 0.1 s.

To search the Mac as well, run this program on the Mac.
"""

# The five payloads the probe hook captured, byte for byte but for the
# probe's scratch directory, which is renamed /Users/el/probe-work. They pin
# which event each search arrives as: a missing-file Read and a Bash call
# that exits non-zero are PostToolUseFailure, a Bash call that exits 0 and an
# empty Glob are PostToolUse.
CAPTURED_PAYLOADS = [
    ('{"session_id":"eb25228e-36d0-410f-b3b9-eb2b4b8d38a2","transcript_path":'
     '"/Users/el/.claude/projects/-Users-el-probe-work/eb25228e-36d0-410f-b3b9-'
     'eb2b4b8d38a2.jsonl","cwd":"/Users/el/probe-work","prompt_id":"61025fa2-'
     '569c-418a-9978-bb939c91c19a","permission_mode":"default",'
     '"hook_event_name":"PostToolUseFailure","tool_name":"Read","tool_input":'
     '{"file_path":"/Users/el/probe-work/no-such-probe-file.md"},"tool_use_id":'
     '"toolu_01KvzfhobBgCMqNtbT9RngRv","error":"File does not exist. Note: '
     'your current working directory is /Users/el/probe-work.","is_interrupt":'
     'false,"duration_ms":2}',
     [("read-missing-file", "/Users/el/probe-work/no-such-probe-file.md")]),
    ('{"session_id":"eb25228e-36d0-410f-b3b9-eb2b4b8d38a2","transcript_path":'
     '"/Users/el/.claude/projects/-Users-el-probe-work/eb25228e-36d0-410f-b3b9-'
     'eb2b4b8d38a2.jsonl","cwd":"/Users/el/probe-work","prompt_id":"61025fa2-'
     '569c-418a-9978-bb939c91c19a","permission_mode":"default",'
     '"hook_event_name":"PostToolUseFailure","tool_name":"Bash","tool_input":'
     '{"command":"ls /Users/el/probe-work/no-such-dir/x.md"},"tool_use_id":'
     '"toolu_01TozocpxiDY67tXfvdUQzF4","error":"Exit code 1\\nls: '
     '/Users/el/probe-work/no-such-dir/x.md: No such file or directory",'
     '"is_interrupt":false,"duration_ms":146}',
     [("no-such-file", "/Users/el/probe-work/no-such-dir/x.md")]),
    ('{"session_id":"eb25228e-36d0-410f-b3b9-eb2b4b8d38a2","transcript_path":'
     '"/Users/el/.claude/projects/-Users-el-probe-work/eb25228e-36d0-410f-b3b9-'
     'eb2b4b8d38a2.jsonl","cwd":"/Users/el/probe-work","prompt_id":"61025fa2-'
     '569c-418a-9978-bb939c91c19a","permission_mode":"default",'
     '"hook_event_name":"PostToolUse","tool_name":"Bash","tool_input":'
     '{"command":"echo \'== header\'; ls /Users/el/probe-work/missing-two.md; '
     'echo end"},"tool_response":{"stdout":"== header\\nls: '
     '/Users/el/probe-work/missing-two.md: No such file or directory\\nend",'
     '"stderr":"","interrupted":false,"isImage":false,"noOutputExpected":false}'
     ',"tool_use_id":"toolu_01X8MDn58Unz4EPkkhk6p72f","duration_ms":17}',
     [("no-such-file", "/Users/el/probe-work/missing-two.md")]),
    ('{"session_id":"eb25228e-36d0-410f-b3b9-eb2b4b8d38a2","transcript_path":'
     '"/Users/el/.claude/projects/-Users-el-probe-work/eb25228e-36d0-410f-b3b9-'
     'eb2b4b8d38a2.jsonl","cwd":"/Users/el/probe-work","prompt_id":"61025fa2-'
     '569c-418a-9978-bb939c91c19a","permission_mode":"default",'
     '"hook_event_name":"PostToolUse","tool_name":"Bash","tool_input":'
     '{"command":"find /Users/el/probe-work -name \'never-there.md\'"},'
     '"tool_response":{"stdout":"","stderr":"","interrupted":false,"isImage":'
     'false,"noOutputExpected":false},"tool_use_id":'
     '"toolu_01PfZRomQA6rg8nqPi9wT7n6","duration_ms":12}',
     [("empty-find", "never-there.md")]),
    ('{"session_id":"eb25228e-36d0-410f-b3b9-eb2b4b8d38a2","transcript_path":'
     '"/Users/el/.claude/projects/-Users-el-probe-work/eb25228e-36d0-410f-b3b9-'
     'eb2b4b8d38a2.jsonl","cwd":"/Users/el/probe-work","prompt_id":"61025fa2-'
     '569c-418a-9978-bb939c91c19a","permission_mode":"default",'
     '"hook_event_name":"PostToolUse","tool_name":"Glob","tool_input":'
     '{"pattern":"**/never-there-glob.md","path":"/Users/el/probe-work"},'
     '"tool_response":{"filenames":[],"durationMs":6,"numFiles":0,"truncated":'
     'false,"totalMatches":0,"countIsComplete":true},"tool_use_id":'
     '"toolu_01WKf1xyGHWjjCuYt6cDiAdM","duration_ms":6}',
     []),
]

failures = []
case_count = 0
sandbox_directories = []


def check(name, condition, detail=""):
    global case_count
    case_count += 1
    if condition:
        print(f"ok    {name}")
    else:
        print(f"FAIL  {name}{': ' + detail if detail else ''}")
        failures.append(name)


class Sandbox:
    """A record file, a stand-in locator and a run counter, per case."""

    def __init__(self, stub_output=FOUND_ANSWER, stub_exit=0, stub_sleep=0,
                 locator=None, record_file=None):
        self.directory = Path(tempfile.mkdtemp(prefix="esrl-hook-test-"))
        sandbox_directories.append(self.directory)
        self.record_file = record_file or self.directory / "records.jsonl"
        self.runs_file = self.directory / "runs.txt"
        stub = self.directory / "stub-locator.py"
        stub.write_text(STUB_LOCATOR)
        self.environment = dict(os.environ)
        for variable in ("GIT_DIR", "GIT_WORK_TREE"):
            self.environment.pop(variable, None)
        self.environment.update({
            HOOK.RECORD_FILE_ENVIRONMENT_VARIABLE: str(self.record_file),
            HOOK.LOCATOR_ENVIRONMENT_VARIABLE: str(locator or stub),
            "STUB_RUNS_FILE": str(self.runs_file),
            "STUB_OUTPUT": stub_output,
            "STUB_EXIT": str(stub_exit),
            "STUB_SLEEP": str(stub_sleep),
            "CLAUDE_PROJECT_DIR": "/Users/el/agents/test-seat",
        })

    def run(self, payload, raw=None):
        started = time.monotonic()
        process = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            input=raw if raw is not None else json.dumps(payload),
            capture_output=True, text=True, env=self.environment, timeout=60)
        return process, time.monotonic() - started

    def records(self, kind=None):
        if not Path(self.record_file).exists():
            return []
        rows = [json.loads(line) for line in
                Path(self.record_file).read_text().splitlines() if line]
        return [row for row in rows if kind is None or row.get("kind") == kind]

    def wait_for_results(self, count, seconds=20):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if len(self.records("result")) >= count:
                return self.records("result")
            time.sleep(0.1)
        return self.records("result")

    def locator_runs(self):
        if not self.runs_file.exists():
            return []
        return self.runs_file.read_text().splitlines()


def bash_success(command, stdout, stderr="", cwd="/Users/el/agents/test-seat"):
    return {"session_id": "session-a", "cwd": cwd,
            "hook_event_name": "PostToolUse", "tool_name": "Bash",
            "tool_input": {"command": command},
            "tool_response": {"stdout": stdout, "stderr": stderr,
                              "interrupted": False, "isImage": False},
            "tool_use_id": "toolu_test"}


def bash_failure(command, output, exit_code=1,
                 cwd="/Users/el/agents/test-seat"):
    return {"session_id": "session-a", "cwd": cwd,
            "hook_event_name": "PostToolUseFailure", "tool_name": "Bash",
            "tool_input": {"command": command},
            "error": f"Exit code {exit_code}\n{output}",
            "is_interrupt": False, "tool_use_id": "toolu_test"}


def read_failure(path, error="File does not exist. Note: your current "
                 "working directory is /Users/el/agents/test-seat."):
    return {"session_id": "session-a", "cwd": "/Users/el/agents/test-seat",
            "hook_event_name": "PostToolUseFailure", "tool_name": "Read",
            "tool_input": {"file_path": path}, "error": error,
            "is_interrupt": False, "tool_use_id": "toolu_test"}


def fires(sandbox):
    return [(row["trigger"], row["query"]) for row in sandbox.records("fire")]


def expect_fire(name, payload, expected, **sandbox_options):
    sandbox = Sandbox(**sandbox_options)
    process, _ = sandbox.run(payload)
    got = fires(sandbox)
    check(name, got == expected and process.returncode == 0
          and process.stdout == "",
          f"fires {got!r}, expected {expected!r}; exit "
          f"{process.returncode}; stdout {process.stdout!r}")
    return sandbox


def expect_silence(name, payload):
    sandbox = Sandbox()
    process, _ = sandbox.run(payload)
    time.sleep(0.3)
    check(name, fires(sandbox) == [] and not sandbox.locator_runs()
          and process.returncode == 0 and process.stdout == "",
          f"fires {fires(sandbox)!r}; locator runs "
          f"{sandbox.locator_runs()!r}; exit {process.returncode}")


# --- the three triggers fire --------------------------------------------

sandbox = expect_fire(
    "a Read of a missing file fires, with the path as the query",
    read_failure("/Users/el/agents/test-seat/docs/drafts/lost-plan.md"),
    [("read-missing-file",
      "/Users/el/agents/test-seat/docs/drafts/lost-plan.md")])
results = sandbox.wait_for_results(1)
# Read with a default, so a hook that records nothing fails the cases below
# rather than stopping the suite before it counts them.
fire = (sandbox.records("fire") or [{}])[0]
check("the fire's locator answer is recorded against the same fire_id",
      len(results) == 1
      and results[0]["fire_id"] == fire.get("fire_id")
      and results[0]["outcome"] == "found"
      and results[0]["exit_code"] == 0
      and sandbox.locator_runs() == [repr(
          ["--", "/Users/el/agents/test-seat/docs/drafts/lost-plan.md"])],
      f"results {results!r}; runs {sandbox.locator_runs()!r}")
check("a fire records machine, seat, session, tool and event",
      fire.get("machine") in ("mac", "ned-box")
      and fire.get("seat") == "test-seat"
      and fire.get("session_id") == "session-a" and fire.get("tool") == "Read"
      and fire.get("event") == "PostToolUseFailure"
      and fire.get("tool_use_id") == "toolu_test", repr(fire))

expect_fire(
    "a failed ls in the BSD form fires (a non-zero exit arrives as a failure)",
    bash_failure("ls /Users/el/x/missing-design.md",
                 "ls: /Users/el/x/missing-design.md: No such file or directory"),
    [("no-such-file", "/Users/el/x/missing-design.md")])

expect_fire(
    "an ls chained with echo headers fires though the command exits 0",
    bash_success("echo '== header'; ls /Users/el/x/missing-two.md; echo end",
                 "== header\nls: /Users/el/x/missing-two.md: No such file or "
                 "directory\nend"),
    [("no-such-file", "/Users/el/x/missing-two.md")])

expect_fire(
    "the GNU ls form, as ned-box prints it, fires",
    bash_failure("ls /home/nedlern/agents/prof/notes.md",
                 "ls: cannot access '/home/nedlern/agents/prof/notes.md': "
                 "No such file or directory", exit_code=2),
    [("no-such-file", "/home/nedlern/agents/prof/notes.md")])

expect_fire(
    "the GNU head form fires",
    bash_failure("head -5 /home/nedlern/x/report.md",
                 "head: cannot open '/home/nedlern/x/report.md' for reading: "
                 "No such file or directory"),
    [("no-such-file", "/home/nedlern/x/report.md")])

expect_fire(
    "the zsh form fires, and a relative path is made absolute from cwd",
    bash_failure("./scripts/run-thing.sh",
                 "zsh: no such file or directory: ./scripts/run-thing.sh",
                 exit_code=127),
    [("no-such-file", "/Users/el/agents/test-seat/scripts/run-thing.sh")])

expect_fire(
    "Python's FileNotFoundError form fires",
    bash_failure("python3 -c 'open(\"/Users/el/x/data.json\")'",
                 "Traceback (most recent call last):\n  File \"<string>\", "
                 "line 1, in <module>\nFileNotFoundError: [Errno 2] No such "
                 "file or directory: '/Users/el/x/data.json'"),
    [("no-such-file", "/Users/el/x/data.json")])

expect_fire(
    "an empty find -name fires on the name",
    bash_success("find /Users/el/agents -name 'pr-main-process-design.md'", ""),
    [("empty-find", "pr-main-process-design.md")])

expect_fire(
    "an empty find with 2>/dev/null that exits 1 fires (a failure with no "
    "output)",
    bash_failure("find /Users/el -name explain-skill-draft.md 2>/dev/null", ""),
    [("empty-find", "explain-skill-draft.md")])

expect_fire(
    "echo headers around an empty find and an empty git log: both fire",
    bash_success(
        "echo '== find'\nfind . -name 'lost-notes.md'\necho \"== git\"\n"
        "git log --all --oneline -- '*pr-main-process-design*'",
        "== find\n== git\n"),
    [("empty-find", "lost-notes.md"),
     ("empty-git-log", "pr-main-process-design")])

expect_fire(
    "an empty git -C <dir> log -- <path> fires on the path under that dir",
    bash_success("git -C /Users/el/Projects/nedschorus log --all -- "
                 "docs/drafts/gone.md", ""),
    [("empty-git-log", "/Users/el/Projects/nedschorus/docs/drafts/gone.md")])

expect_fire(
    "find's own permission-denied lines do not stop an empty find firing",
    bash_success("find /Users/el -name 'secret-plan.md'",
                 "find: /Users/el/Library/Mail: Operation not permitted\n"
                 "find: /Users/el/.Trash: Permission denied"),
    [("empty-find", "secret-plan.md")])

expect_fire(
    "a missing find root fires on the find's -name, not on the root",
    bash_failure("find /home/nedlern/nowhere -name 'wanted.md'",
                 "find: '/home/nedlern/nowhere': No such file or directory"),
    [("no-such-file", "wanted.md")])

expect_fire(
    "at most three queries are taken from one tool call",
    bash_failure("ls a1.md b2.md c3.md d4.md",
                 "\n".join(f"ls: {name}: No such file or directory"
                           for name in ("aaa1.md", "bbb2.md", "ccc3.md",
                                        "ddd4.md"))),
    [("no-such-file", f"/Users/el/agents/test-seat/{name}")
     for name in ("aaa1.md", "bbb2.md", "ccc3.md")])

for raw, expected in CAPTURED_PAYLOADS:
    payload = json.loads(raw)
    sandbox = Sandbox()
    process, _ = sandbox.run(None, raw=raw)
    check(f"the captured {payload['hook_event_name']} {payload['tool_name']} "
          f"payload {'fires ' + expected[0][0] if expected else 'is silent'}",
          fires(sandbox) == expected and process.returncode == 0
          and process.stdout == "",
          f"fires {fires(sandbox)!r}, expected {expected!r}; exit "
          f"{process.returncode}; stdout {process.stdout!r}")

# --- a repeat does not run the locator again ----------------------------

sandbox = Sandbox()
payload = read_failure("/Users/el/x/again.md")
sandbox.run(payload)
sandbox.wait_for_results(1)
sandbox.run(payload)
time.sleep(0.5)
fire_records = sandbox.records("fire")
check("the same query from the same session is recorded as a repeat and the "
      "locator runs once",
      len(fire_records) == 2 and "repeat_of" not in fire_records[0]
      and fire_records[1].get("repeat_of") == fire_records[0]["fire_id"]
      and len(sandbox.locator_runs()) == 1,
      f"fires {fire_records!r}; runs {sandbox.locator_runs()!r}")
other_session = dict(payload, session_id="session-b")
sandbox.run(other_session)
sandbox.wait_for_results(2)
check("the same query from another session is not a repeat",
      len(sandbox.locator_runs()) == 2
      and "repeat_of" not in (sandbox.records("fire") or [{}])[-1],
      repr(sandbox.records("fire")))

# --- what must not fire ---------------------------------------------------

expect_silence("a find that found something does not fire",
               bash_success("find . -name 'plan.md'", "./docs/plan.md\n"))
expect_silence("an empty Glob does not fire", {
    "session_id": "session-a", "cwd": "/Users/el/agents/test-seat",
    "hook_event_name": "PostToolUse", "tool_name": "Glob",
    "tool_input": {"pattern": "**/never-there.md"},
    "tool_response": {"filenames": [], "numFiles": 0}})
expect_silence("an empty Grep does not fire", {
    "session_id": "session-a", "cwd": "/Users/el/agents/test-seat",
    "hook_event_name": "PostToolUse", "tool_name": "Grep",
    "tool_input": {"pattern": "never-there"},
    "tool_response": {"filenames": [], "numFiles": 0}})
expect_silence("a Read that failed for another reason does not fire",
               read_failure("/Users/el/x/big.log",
                            error="File content (30000 tokens) exceeds "
                                  "maximum allowed tokens (25000)."))
expect_silence("the locator's own run does not fire",
               bash_failure("python3 scripts/locate-file-copies-across-"
                            "machines.py gone.md",
                            "ls: /x/gone.md: No such file or directory"))
expect_silence("a search for the words 'No such file' does not fire",
               bash_success("grep -h 'No such file' /tmp/logs/*.log",
                            "cat: /x/old.md: No such file or directory\n"))
expect_silence("a cd into a missing directory does not fire",
               bash_failure("cd /Users/el/missing-directory",
                            "cd: no such file or directory: "
                            "/Users/el/missing-directory"))
expect_silence("an empty find for a generic pattern does not fire",
               bash_success("find . -name '*.md'", ""))
expect_silence("an empty git log without -- does not fire",
               bash_success("git log --oneline origin/main..HEAD", ""))
expect_silence("an interrupted call does not fire",
               dict(bash_failure("ls /x/gone.md",
                                 "ls: /x/gone.md: No such file or directory"),
                    is_interrupt=True))
expect_silence("the phrase inside a JSON line does not fire",
               bash_success("cat record.json",
                            '{"error": "No such file or directory", '
                            '"path": "/x/y.md"}\n'))
expect_silence("an ls of a file that exists does not fire",
               bash_success("ls /Users/el/x/present.md",
                            "/Users/el/x/present.md\n"))

# --- the hook never blocks and never speaks -------------------------------

sandbox = Sandbox()
process, _ = sandbox.run(None, raw="this is not json {")
check("a payload that is not JSON exits 0 and prints nothing",
      process.returncode == 0 and process.stdout == ""
      and process.stderr == "" and sandbox.records() == [],
      f"exit {process.returncode}; stdout {process.stdout!r}; stderr "
      f"{process.stderr!r}")

sandbox = Sandbox(locator="/nonexistent/locate-file-copies-across-machines.py")
process, _ = sandbox.run(read_failure("/Users/el/x/when-locator-missing.md"))
results = sandbox.wait_for_results(1)
check("a missing locator: the hook exits 0, prints nothing, and records the "
      "error",
      process.returncode == 0 and process.stdout == ""
      and len(results) == 1 and results[0]["outcome"] == "error",
      f"exit {process.returncode}; results {results!r}")

sandbox = Sandbox(record_file=Path("/nonexistent-directory-esrl/records.jsonl"))
process, _ = sandbox.run(read_failure("/Users/el/x/unwritable.md"))
time.sleep(0.5)
check("a record file that cannot be written: exit 0, nothing printed, and "
      "the locator is not started",
      process.returncode == 0 and process.stdout == ""
      and process.stderr == "" and sandbox.locator_runs() == [],
      f"exit {process.returncode}; stderr {process.stderr!r}; runs "
      f"{sandbox.locator_runs()!r}")

sandbox = Sandbox(stub_sleep=5)
process, elapsed = sandbox.run(read_failure("/Users/el/x/slow.md"))
check("the hook returns before a slow locator finishes: the locator runs "
      "detached",
      process.returncode == 0 and elapsed < 2.5
      and sandbox.records("result") == [],
      f"hook took {elapsed:.2f} s; results {sandbox.records('result')!r}")
results = sandbox.wait_for_results(1, seconds=30)
check("the detached run still records its answer when it finishes",
      len(results) == 1 and results[0]["duration_s"] >= 4.5, repr(results))

# --- what an answer is recorded as ----------------------------------------

sandbox = Sandbox(stub_output=INCOMPLETE_ANSWER, stub_exit=3)
sandbox.run(read_failure("/home/nedlern/x/plan.md"))
results = sandbox.wait_for_results(1)
check("ned-box's exit 3, the Mac not reachable, is recorded as incomplete, "
      "not as a miss",
      len(results) == 1 and results[0]["outcome"] == "incomplete"
      and results[0]["not_searched"] ==
      ["mac: no route from ned-box to the Mac is documented"]
      and results[0]["candidates_count"] == 1,
      repr(results))

summary = HOOK.summarize_answer(FOUND_ANSWER, 0)
check("an answer's found and candidate entries are counted, and the ones "
      "not shown are added",
      summary["found_count"] == 1 and summary["candidates_count"] == 9
      and summary["found"][0].startswith("2026-09-24 18:11Z  mac checkouts")
      and len(summary["candidates"]) == 2, repr(summary))

with tempfile.TemporaryDirectory(prefix="esrl-real-locator-") as root:
    wanted = Path(root) / "projects" / "real-locator-wanted-notes.md"
    wanted.parent.mkdir(parents=True)
    wanted.write_text("x")
    (Path(root) / "real-locator-wanted-notes-old.md").write_text("y")
    plan = {"this": {"machine": "mac",
                     "surfaces": [{"name": "checkouts", "roots": [root]}],
                     "this_repository": {"clones": [], "checkout_parents": [],
                                         "scratch_trees": []},
                     "spellings": []}}
    environment = dict(os.environ,
                       LOCATE_FILE_COPIES_ACROSS_MACHINES_PLAN=json.dumps(plan))
    for variable in ("GIT_DIR", "GIT_WORK_TREE"):
        environment.pop(variable, None)
    process = subprocess.run(
        [sys.executable, str(REAL_LOCATOR_PATH), "--",
         "real-locator-wanted-notes.md"],
        capture_output=True, text=True, env=environment, timeout=120, cwd="/")
    summary = HOOK.summarize_answer(process.stdout, process.returncode)
    check("the parser reads the real locator's answer: one found, one "
          "candidate",
          process.returncode == 0 and summary["outcome"] == "found"
          and summary["found_count"] == 1
          and str(wanted) in summary["found"][0]
          and summary["candidates_count"] == 1,
          f"exit {process.returncode}; summary {summary!r}; output "
          f"{process.stdout!r}")

sandbox = Sandbox()
sandbox.run(read_failure("/Users/el/x/one.md"))
sandbox.run(read_failure("/Users/el/x/one.md"))
sandbox.run(bash_success("find . -name 'two-files.md'", ""))
sandbox.wait_for_results(2)
report = subprocess.run(
    [sys.executable, str(SCRIPT_PATH), "--summarize", str(sandbox.record_file)],
    capture_output=True, text=True, timeout=30).stdout
check("--summarize counts fires, repeats, triggers and outcomes",
      report.startswith("3 fires, 1 of them repeats; 2 locator runs, "
                        "2 answered")
      and "read-missing-file 1" in report and "empty-find 1" in report
      and "found 2" in report, report)

# A locator still running detached finds its directory gone and records
# nothing; it can no longer reach a case.
for directory in sandbox_directories:
    shutil.rmtree(directory, ignore_errors=True)

print()
if failures:
    print(f"FAILED: {len(failures)} of {case_count} cases")
    sys.exit(1)
print(f"all {case_count} cases passed")
