#!/usr/bin/env python3
"""Cases for the Stop hook that raises an agent-seat's due tasks.

Every case runs the hook as a subprocess, its real stdin-to-stdout path,
under a HOME this suite made, so the task list it reads and the state file it
writes are this suite's and never the real ~/.claude/tasks or
~/.local/state/claude. `gh` is a stand-in placed first on PATH: it answers
from a file the case writes, and logs every call, with whether GH_TOKEN
reached it, so a case can count calls. No case touches the network.

The exit code is asserted on every case: a Stop hook that exits 2 blocks the
turn from ending, so "always 0" is a property, not a detail.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Before anything runs git: the next-action cases `git init` scratch checkouts,
# which a variable that redirects git would send into another repository.
_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().with_name(
        "git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

HOOK_SCRIPT = Path(__file__).with_name("agent-seat-due-task-raise-hook.py")

# Loaded in-process only for the cache boundary, which needs an exact clock;
# every other case runs the hook as a subprocess.
_hook_spec = importlib.util.spec_from_file_location("agent_seat_due_task_raise_hook",
                                                    HOOK_SCRIPT)
hook = importlib.util.module_from_spec(_hook_spec)
_hook_spec.loader.exec_module(hook)
TASK_LIST_ID = "nedschorus-test-seat-tasks"
MERGED_PR = 900
MET = {"prerequisites": [{"pr_merged": MERGED_PR}]}
STOP_PAYLOAD = json.dumps({
    "session_id": "test-session", "transcript_path": "/nonexistent.jsonl",
    "cwd": "/", "hook_event_name": "Stop", "stop_hook_active": False,
})
DEFER_LINE = ("If a task above cannot be acted on yet, record what it now waits on with "
              "TaskUpdate instead: a pull request, a GHI or an approval-walk item in a new "
              "metadata.prerequisites, or a task with addBlockedBy.")
CORRECT_PREREQUISITES_LINE = (
    'Correct the task with TaskUpdate, giving its metadata a "prerequisites" list whose entries '
    'are each one of {"pr_merged": <number>}, {"issue_closed": <number>} or '
    '{"approval_walk_item_decided": {"approval_walk_minutes_file_path": "<absolute path of the '
    'walk-minutes file>", "approval_walk_item_heading": "<the item\'s heading in the '
    'walk-document>"}}; if the task waits on no pull request, GHI or approval-walk item, set '
    '"prerequisites" to null, and record any task on your own task list it waits on with '
    "addBlockedBy.")


def problem_text(task_id, problem, subject=None):
    subject = subject if subject is not None else f"Subject of task {task_id}"
    return (f'Task {task_id} "{subject}" is never raised as its metadata.prerequisites stand, '
            f"because {problem}.\n{CORRECT_PREREQUISITES_LINE}")

GH_STAND_IN = """#!{python}
import json, os, sys, time
with open(os.environ["FAKE_GH_LOG"], "a") as log:
    log.write(json.dumps({{"argv": sys.argv[1:],
                          "gh_token_present": "GH_TOKEN" in os.environ}}) + "\\n")
try:
    with open(os.environ["FAKE_GH_RESPONSES"]) as handle:
        responses = json.load(handle)
except FileNotFoundError:
    responses = {{}}
key = sys.argv[1] + ":" + sys.argv[3]
answer = responses.get(key, "fail")
if answer == "fail":
    sys.stderr.write("gh stand-in: failing on purpose\\n")
    sys.exit(1)
if answer == "garbage":
    print("not json")
    sys.exit(0)
print(json.dumps(answer))
"""

failures = []
SUITE_ROOT = Path(tempfile.mkdtemp(prefix="agent-seat-due-task-raise-test-"))


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def seat_session_environment():
    """This process's environment as an agent-seat's own attended session
    gives it to a Stop hook: attended, and no caller owning the session."""
    environment = dict(os.environ)
    environment["CLAUDE_CODE_SESSION_ATTENDED"] = "1"
    environment.pop("NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER", None)
    return environment


class Seat:
    """A HOME holding one task list, a gh stand-in, and its response file."""

    def __init__(self):
        self.home = Path(tempfile.mkdtemp(dir=str(SUITE_ROOT)))
        self.task_directory = self.home / ".claude" / "tasks" / TASK_LIST_ID
        self.task_directory.mkdir(parents=True)
        (self.task_directory / ".lock").write_text("")
        self.bin_directory = self.home / "fake-bin"
        self.bin_directory.mkdir()
        gh = self.bin_directory / "gh"
        gh.write_text(GH_STAND_IN.format(python=sys.executable))
        gh.chmod(0o755)
        self.gh_log = self.home / "gh-calls.log"
        self.gh_responses = self.home / "gh-responses.json"
        self.responses = {f"pr:{MERGED_PR}": {"state": "MERGED", "title": "Merged",
                                                "url": f"https://x/{MERGED_PR}"}}
        self.respond({})
        self.state_path = (self.home / ".local" / "state" / "claude"
                           / "agent-seat-due-task-raise-state" / f"{TASK_LIST_ID}.json")

    def task(self, task_id, status="pending", metadata=None, blocked_by=(),
             subject=None):
        task = {
            "id": task_id,
            "subject": subject if subject is not None else f"Subject of task {task_id}",
            "description": "a description",
            "activeForm": "Doing it",
            "status": status,
            "blocks": [],
            "blockedBy": list(blocked_by),
        }
        if metadata is not None:
            task["metadata"] = metadata
        (self.task_directory / f"{task_id}.json").write_text(json.dumps(task, indent=2))

    def respond(self, responses):
        """Add to, or replace, the answers the gh stand-in gives; pr:900 is merged."""
        self.responses.update(responses)
        self.gh_responses.write_text(json.dumps(self.responses))

    def gh_calls(self):
        if not self.gh_log.exists():
            return []
        return [json.loads(line) for line in self.gh_log.read_text().splitlines()]

    def run(self, stdin_text=STOP_PAYLOAD, list_id=TASK_LIST_ID, environment_changes=None):
        """Run the hook as an agent-seat's own attended session would, unless
        `environment_changes` says otherwise (a value of None removes the
        variable). The session signals are set rather than inherited, because
        this suite may itself run under a headless `claude -p`."""
        environment = {
            **seat_session_environment(),
            "HOME": str(self.home),
            "PATH": f"{self.bin_directory}{os.pathsep}{os.environ.get('PATH', '')}",
            "FAKE_GH_LOG": str(self.gh_log),
            "FAKE_GH_RESPONSES": str(self.gh_responses),
            "GH_TOKEN": "a-token-the-hook-must-remove",
        }
        if list_id is None:
            environment.pop("CLAUDE_CODE_TASK_LIST_ID", None)
        else:
            environment["CLAUDE_CODE_TASK_LIST_ID"] = list_id
        for name, value in (environment_changes or {}).items():
            if value is None:
                environment.pop(name, None)
            else:
                environment[name] = value
        return subprocess.run(
            [sys.executable, str(HOOK_SCRIPT)], input=stdin_text,
            capture_output=True, text=True, env=environment, check=False, timeout=60)


def context_of(result):
    """The additionalContext the hook emitted, or None when it printed nothing."""
    if not result.stdout.strip():
        return None
    payload = json.loads(result.stdout)
    return payload["hookSpecificOutput"]["additionalContext"]


def silent(result):
    return result.returncode == 0 and result.stdout == "" and result.stderr == ""


def reported(result, fault_words):
    """A fault: exit 1, no raise on stdout, one stderr line naming the hook and the fault."""
    lines = result.stderr.splitlines()
    return (result.returncode == 1 and result.stdout == "" and len(lines) == 1
            and lines[0].startswith("agent-seat-due-task-raise-hook: ")
            and fault_words in lines[0])




# --- prerequisites met raises, with the exact text ------------------------------
seat = Seat()
seat.task("7", metadata=MET, subject="Check the\nnightly run")
result = seat.run()
check("prerequisites met: exit 0", result.returncode == 0, result.returncode)
output = json.loads(result.stdout) if result.stdout.strip() else {}
check("prerequisites met: the Stop hook's JSON, no decision, no systemMessage",
      set(output) == {"hookSpecificOutput"}
      and output["hookSpecificOutput"].get("hookEventName") == "Stop",
      result.stdout)
expected_text = (f'Act on task 7 "Check the nightly run" now: its prerequisites are met: '
                 f'PR "Merged" (https://x/{MERGED_PR}) is merged.\n{DEFER_LINE}')
check("prerequisites met: the exact text handed to the agent",
      context_of(result) == expected_text, repr(context_of(result)))

# --- raised once, then silent ------------------------------------------------
second = seat.run()
check("raised once: the next stop is silent", silent(second), second)

# --- silent while the agent answers a Stop hook, raised at the next stop -----
answering_seat = Seat()
answering_seat.task("12", metadata=MET)
answering = answering_seat.run(json.dumps({**json.loads(STOP_PAYLOAD), "stop_hook_active": True}))
check("stop_hook_active: silent while the agent answers a Stop hook", silent(answering), answering)
check("stop_hook_active: no state written, so the raise is not lost",
      not answering_seat.state_path.exists())
later = answering_seat.run()
check("stop_hook_active: the next ordinary stop raises the task",
      context_of(later) is not None and "task 12" in context_of(later), later.stdout)

# --- not yet met --------------------------------------------------------------
seat = Seat()
seat.task("8", metadata={"prerequisites": [{"pr_merged": 901}]})
seat.respond({"pr:901": {"state": "OPEN", "title": "T", "url": "https://x/901"}})
check("prerequisites not met: silent", silent(seat.run()))
check("prerequisites not met: nothing recorded as raised",
      json.loads(seat.state_path.read_text())["raised"] == {})

# --- in_progress raises; completed never does --------------------------------
seat = Seat()
seat.task("20", status="in_progress", metadata=MET)
seat.task("21", status="completed", metadata=MET)
text = context_of(seat.run()) or ""
check("in_progress task met: raised", "Act on task 20 " in text, text)
check("completed task met: never raised", "task 21 " not in text, text)

seat = Seat()
seat.task("22", status="completed", metadata={"prerequisites": [{"pr_merged": 5}]})
seat.respond({"pr:5": {"state": "MERGED", "title": "T", "url": "https://x/5"}})
check("completed task with met prerequisites: silent", silent(seat.run()))
check("completed task: gh never asked", seat.gh_calls() == [], seat.gh_calls())

# --- blockedBy ----------------------------------------------------------------
seat = Seat()
seat.task("30", metadata=MET, blocked_by=["31"])
seat.task("31", status="in_progress")
check("blockedBy incomplete: held, silent", silent(seat.run()))
check("blockedBy incomplete: nothing recorded as raised",
      not seat.state_path.exists()
      or "30" not in json.loads(seat.state_path.read_text()).get("raised", {}))
seat.task("31", status="completed")
text = context_of(seat.run()) or ""
check("blockedBy completed: raised", "Act on task 30 " in text, text)

seat = Seat()
seat.task("32", metadata=MET, blocked_by=["999"])
text = context_of(seat.run()) or ""
check("blockedBy naming a task with no file: not held", "Act on task 32 " in text, text)

seat = Seat()
seat.task("33", metadata=MET, blocked_by=["34"])
(seat.task_directory / "34.json").write_text("{ not json")
check("blockedBy naming an unreadable task file: held", silent(seat.run()))

seat = Seat()
seat.task("35", metadata={"prerequisites": [{"pr_merged": 6}]}, blocked_by=["36"])
seat.task("36")
seat.respond({"pr:6": {"state": "MERGED", "title": "T", "url": "https://x/6"}})
check("blockedBy incomplete: gh not asked for the held task",
      silent(seat.run()) and seat.gh_calls() == [], seat.gh_calls())

# --- blockedBy alone: raised once its blockers all complete -------------------
seat = Seat()
seat.task("50", blocked_by=["52", "51"], subject="Ship after both")
seat.task("51", status="completed")
seat.task("52", status="in_progress")
check("blockedBy alone, one blocker still open: silent", silent(seat.run()))
seat.task("52", status="completed")
result = seat.run()
check("blockedBy alone, every blocker completed: the exact text handed to the agent",
      context_of(result) == ('Act on task 50 "Ship after both" now: the tasks it waited on '
                             f"are completed: task 51, task 52.\n{DEFER_LINE}"),
      repr(context_of(result)))
check("blockedBy alone: no gh call", seat.gh_calls() == [], seat.gh_calls())
check("blockedBy alone: the raise is recorded by its blocker list",
      json.loads(seat.state_path.read_text())["raised"]["50"] == {"blocked_by": ["51", "52"]},
      seat.state_path.read_text() if seat.state_path.exists() else "no state file")
check("blockedBy alone: raised once, then silent", silent(seat.run()))
seat.task("53", status="completed")
seat.task("50", blocked_by=["51", "52", "53"], subject="Ship after both")
text = context_of(seat.run()) or ""
check("blockedBy alone: a changed blocker list raises again", "Act on task 50 " in text, text)
check("blockedBy alone: then silent again", silent(seat.run()))

seat = Seat()
seat.task("54", metadata={}, blocked_by=["55"])
seat.task("55", status="completed")
text = context_of(seat.run()) or ""
check("blockedBy alone with an empty metadata object: raised", "Act on task 54 " in text, text)

seat = Seat()
seat.task("56", blocked_by=["998"])
check("blockedBy alone naming a deleted task: freed but not raised", silent(seat.run()))

seat = Seat()
seat.task("57", blocked_by=["58", "998"])
seat.task("58", status="completed")
check("blockedBy alone, one blocker completed and one deleted: not raised", silent(seat.run()))

seat = Seat()
seat.task("61", metadata={"prerequisites": [{"pr_merged": 7}]}, blocked_by=["62"])
seat.task("62", status="completed")
seat.respond({"pr:7": {"state": "OPEN", "title": "T", "url": "https://x/7"}})
check("blockers completed but prerequisites not met: silent", silent(seat.run()))

seat = Seat()
seat.task("63")
check("a task with no metadata and no blockedBy: silent", silent(seat.run()))
check("a task with no metadata and no blockedBy: no state written",
      not seat.state_path.exists())

# --- prerequisites ------------------------------------------------------------
seat = Seat()
seat.task("40", metadata={"prerequisites": [{"pr_merged": 101}, {"issue_closed": 202}]})
seat.respond({
    "pr:101": {"state": "MERGED", "title": "Add the\nthing", "url": "https://github.com/nedschorus/nedschorus/pull/101"},
    "issue:202": {"state": "CLOSED", "title": "The bug", "url": "https://github.com/nedschorus/nedschorus/issues/202"},
})
result = seat.run()
expected_text = (
    'Act on task 40 "Subject of task 40" now: its prerequisites are met: '
    'PR "Add the thing" (https://github.com/nedschorus/nedschorus/pull/101) is merged; '
    'GHI "The bug" (https://github.com/nedschorus/nedschorus/issues/202) is closed.'
    f"\n{DEFER_LINE}")
check("prerequisites met: raised with each prerequisite cited by title and link",
      context_of(result) == expected_text, repr(context_of(result)))
calls = seat.gh_calls()
check("prerequisites met: gh asked read-only view calls on the project repository",
      sorted(call["argv"] for call in calls) == [
          ["issue", "view", "202", "--repo", "nedschorus/nedschorus", "--json", "state,title,url"],
          ["pr", "view", "101", "--repo", "nedschorus/nedschorus", "--json", "state,title,url"]],
      calls)
check("prerequisites met: GH_TOKEN removed before gh runs",
      calls and not any(call["gh_token_present"] for call in calls), calls)
check("prerequisites met: raised once, then silent", silent(seat.run()))

seat = Seat()
seat.task("41", metadata={"prerequisites": [{"pr_merged": 101}, {"issue_closed": 202}]})
seat.respond({"pr:101": {"state": "MERGED", "title": "A", "url": "https://x/101"},
              "issue:202": {"state": "OPEN", "title": "B", "url": "https://x/202"}})
check("prerequisites partly met: silent", silent(seat.run()))

seat = Seat()
seat.task("42", metadata={"prerequisites": [{"pr_merged": 103}]})
seat.respond({"pr:103": "fail"})
result = seat.run()
GH_COMMAND_103 = "`gh pr view 103 --repo nedschorus/nedschorus --json state,title,url`"
GH_FAILURE_103 = ("This hook could not ask GitHub whether PR 103 is merged, so no task "
                  f"waiting on it was raised: {GH_COMMAND_103} exited 1: gh stand-in: "
                  "failing on purpose. It asks again at the first stop at least 5 minutes "
                  "after the failed call.")
check("gh failing: reported on stderr with gh's command and error, exit 1, nothing raised",
      reported(result, GH_FAILURE_103), result)
check("gh failing: it was asked", len(seat.gh_calls()) == 1, seat.gh_calls())
result = seat.run()
check("gh failing: the next stop within five minutes reports the same failure from the cache "
      "and does not ask gh again",
      reported(result, GH_FAILURE_103) and len(seat.gh_calls()) == 1, (result, seat.gh_calls()))

seat = Seat()
seat.task("43", metadata={"prerequisites": [{"pr_merged": 103}]})
seat.task("44", metadata={"prerequisites": [{"pr_merged": 103}]})
seat.respond({"pr:103": "fail"})
result = seat.run()
check("gh failing for a condition two tasks name: one gh call, the failure reported once",
      reported(result, GH_FAILURE_103) and result.stderr.count(GH_COMMAND_103) == 1
      and len(seat.gh_calls()) == 1, (result, seat.gh_calls()))

seat = Seat()
seat.task("40", metadata=MET, subject="Met anyway")
seat.task("42", metadata={"prerequisites": [{"pr_merged": 103}]})
seat.respond({"pr:103": "fail"})
result = seat.run()
text = context_of(result) or ""
check("gh failing at a stop that raises a task: exit 0, the raise, then the gh failure "
      "line for the agent",
      result.returncode == 0 and text.startswith('Act on task 40 "Met anyway" now')
      and text.splitlines()[-1].startswith(
          "This hook could not ask GitHub whether PR 103 is merged, so no task waiting on it "
          f"was raised: {GH_COMMAND_103} exited 1")
      and "Act on task 42" not in text, (result, text))

seat = Seat()
seat.task("43", metadata={"prerequisites": [{"pr_merged": 104}]})
seat.respond({"pr:104": "garbage"})
check("gh answering unparsable output: reported, exit 1",
      reported(seat.run(), "`gh pr view 104 --repo nedschorus/nedschorus --json "
                           "state,title,url` exited 0 without printing a JSON object"))

seat = Seat()
seat.task("44", metadata={"prerequisites": [{"pr_merged": 105}]})
seat.respond({"pr:105": {"state": "MERGED", "title": "T", "url": "https://x/105"}})
broken_path = seat.home / "fake-bin" / "gh"
broken_path.unlink()
empty_bin = seat.home / "empty-bin"
empty_bin.mkdir()
environment = {**seat_session_environment(), "HOME": str(seat.home), "PATH": str(empty_bin),
               "CLAUDE_CODE_TASK_LIST_ID": TASK_LIST_ID}
result = subprocess.run([sys.executable, str(HOOK_SCRIPT)], input=STOP_PAYLOAD,
                        capture_output=True, text=True, env=environment, check=False)
check("gh not installed: reported, exit 1",
      reported(result, "`gh pr view 105 --repo nedschorus/nedschorus --json state,title,url` "
                       "could not be run: "), result)

real_subprocess_run = hook.subprocess.run


def timing_out_run(command, timeout=None, **keywords):
    raise subprocess.TimeoutExpired(command, timeout)


hook.subprocess.run = timing_out_run
try:
    timed_out = hook.GitHubConditionChecker.ask_gh("issue_closed", 9, 8)
finally:
    hook.subprocess.run = real_subprocess_run
check("gh timing out is a gh failure naming the command and its time limit, not an answer",
      timed_out == {"gh_failure": "`gh issue view 9 --repo nedschorus/nedschorus --json "
                                  "state,title,url` did not answer within 8 seconds"},
      timed_out)

seat = Seat()
seat.task("45", metadata={"prerequisites": []})
seat.task("46", metadata={"prerequisites": [{"pr_merged": 107}, {"merged_by": "x"}]})
seat.task("47", metadata={"prerequisites": [{"pr_merged": "107"}]})
seat.respond({"pr:107": {"state": "MERGED", "title": "T", "url": "https://x/107"}})
result = seat.run()
check("empty prerequisites, an unknown condition, a non-number condition: each named to the "
      "agent, none raised, and gh never asked",
      context_of(result) == "\n".join((
          problem_text("45", "it is an empty list, which names nothing to wait on"),
          problem_text("46", 'its entry {"merged_by": "x"} names the kind "merged_by", which this '
                             "hook does not know"),
          problem_text("47", 'its entry {"pr_merged": "107"} does not give a positive whole '
                             "number")))
      and seat.gh_calls() == [], (context_of(result), seat.gh_calls()))
check("unreadable prerequisites: named once, then silent", silent(seat.run()))
seat.task("46", metadata={"prerequisites": [{"waits_on": 107}]})
check("unreadable prerequisites changed to another unreadable value: named again",
      context_of(seat.run()) == problem_text(
          "46", 'its entry {"waits_on": 107} names the kind "waits_on", which this hook does not '
                "know"))
seat.task("46", metadata={"prerequisites": [{"pr_merged": 107}]})
check("unreadable prerequisites corrected and met: raised",
      (context_of(seat.run()) or "").startswith("Act on task 46 "))

seat = Seat()
seat.task("48", metadata={"prerequisites": [{"pr_merged": 108}]})
seat.respond({"pr:108": {"state": "MERGED"}})
text = context_of(seat.run()) or ""
check("prerequisites met but gh gave no title: cited by number",
      'its prerequisites are met: PR 108 is merged.' in text, text)

seat = Seat()
seat.task("49", metadata={"prerequisites": [{"pr_merged": 109}]})
seat.state_path.parent.mkdir(parents=True)
seat.state_path.write_text(json.dumps({"raised": {}, "checks": {
    "pr_merged:109": {"met": 1, "checked_at_epoch": time.time()}}}))
check("a cached answer whose met is 1, not true: not met, so not raised",
      silent(seat.run()) and seat.gh_calls() == [], seat.gh_calls())

# --- the five-minute cache -----------------------------------------------------
seat = Seat()
seat.task("50", metadata={"prerequisites": [{"pr_merged": 110}]})
seat.respond({"pr:110": {"state": "OPEN", "title": "T", "url": "https://x/110"}})
check("cache: first stop, unmet, silent", silent(seat.run()))
check("cache: first stop asked gh once", len(seat.gh_calls()) == 1, seat.gh_calls())
seat.respond({"pr:110": {"state": "MERGED", "title": "T", "url": "https://x/110"}})
check("cache: a stop within five minutes is silent though the PR merged",
      silent(seat.run()))
check("cache: a stop within five minutes does not ask gh",
      len(seat.gh_calls()) == 1, seat.gh_calls())
state = json.loads(seat.state_path.read_text())
state["checks"]["pr_merged:110"]["checked_at_epoch"] -= 290
seat.state_path.write_text(json.dumps(state))
check("cache: 290 seconds old still holds", silent(seat.run()) and len(seat.gh_calls()) == 1,
      seat.gh_calls())
state = json.loads(seat.state_path.read_text())
state["checks"]["pr_merged:110"]["checked_at_epoch"] -= 15
seat.state_path.write_text(json.dumps(state))
text = context_of(seat.run()) or ""
check("cache: older than five minutes, gh is asked again and the task raised",
      "Act on task 50 " in text and len(seat.gh_calls()) == 2, (text, seat.gh_calls()))
seat.run()
check("cache: a raised task's prerequisites are never asked again",
      len(seat.gh_calls()) == 2, seat.gh_calls())


class CountingChecker(hook.GitHubConditionChecker):
    """The hook's checker with gh replaced by a counter, for exact clock values."""
    asked = []

    @staticmethod
    def ask_gh(kind, number, timeout_seconds):
        CountingChecker.asked.append((kind, number))
        return {"met": False}


cached_answer = {"met": False, "checked_at_epoch": 1000.0}
checker = CountingChecker({"pr_merged:1": cached_answer}, 1000.0 + 299.999)
check("cache boundary: 299.999 seconds old is answered from the cache",
      checker.answer("pr_merged", 1) is cached_answer and CountingChecker.asked == [],
      CountingChecker.asked)
checker = CountingChecker({"pr_merged:1": dict(cached_answer)}, 1000.0 + 300)
checker.answer("pr_merged", 1)
check("cache boundary: 300 seconds old asks gh",
      CountingChecker.asked == [("pr_merged", 1)], CountingChecker.asked)

seat = Seat()
seat.task("51", metadata={"prerequisites": [{"pr_merged": 111}]})
seat.respond({"pr:111": "fail"})
seat.run()
seat.run()
check("cache: a failed check also waits five minutes", len(seat.gh_calls()) == 1,
      seat.gh_calls())

seat = Seat()
seat.task("52", metadata={"prerequisites": [{"pr_merged": 112}]})
seat.task("53", metadata={"prerequisites": [{"pr_merged": 112}]})
seat.respond({"pr:112": {"state": "MERGED", "title": "T", "url": "https://x/112"}})
text = context_of(seat.run()) or ""
check("one condition named by two tasks: one gh call, both raised",
      len(seat.gh_calls()) == 1 and "task 52 " in text and "task 53 " in text,
      (text, seat.gh_calls()))

# --- prerequisite set changed raises again --------------------------------------
seat.task("52", metadata={"prerequisites": [{"pr_merged": 112}, {"issue_closed": 113}]})
seat.respond({"issue:113": {"state": "CLOSED", "title": "U", "url": "https://x/113"}})
text = context_of(seat.run()) or ""
check("prerequisites changed and met: raised again", "Act on task 52 " in text
      and "task 53 " not in text, text)

# --- a task raised for its prerequisites, then given a blocker ------------------
seat = Seat()
seat.task("110", metadata=MET, subject="Wait again")
check("raised for prerequisites", "Act on task 110 " in (context_of(seat.run()) or ""))
seat.task("110", metadata=MET, blocked_by=["111"], subject="Wait again")
seat.task("111", status="in_progress")
check("given a blocker after the raise: held, silent", silent(seat.run()))
seat.task("111", status="completed")
result = seat.run()
check("the blocker completed: raised for it, with the exact text",
      context_of(result) == ('Act on task 110 "Wait again" now: the tasks it waited on are '
                             f"completed: task 111.\n{DEFER_LINE}"), repr(context_of(result)))
check("the blocker completed: raised once, then silent", silent(seat.run()))

seat = Seat()
seat.task("112", metadata=MET, blocked_by=["113"])
seat.task("113", status="completed")
text = context_of(seat.run()) or ""
check("prerequisites met and blockers already completed: raised once, for the prerequisites",
      "Act on task 112 " in text and "its prerequisites are met" in text
      and "the tasks it waited on" not in text, text)
check("prerequisites met and blockers already completed: then silent", silent(seat.run()))

seat = Seat()
seat.task("114", metadata={"prerequisites": [{"pr_merged": 902}]}, blocked_by=["115"])
seat.task("115", status="completed")
seat.respond({"pr:902": {"state": "OPEN", "title": "T", "url": "https://x/902"}})
check("prerequisites not yet met, blockers completed: silent", silent(seat.run()))

seat = Seat()
seat.task("116", metadata={"prerequisites": []}, blocked_by=["117"])
seat.task("117", status="completed")
check("unreadable prerequisites, blockers completed: named, never raised",
      context_of(seat.run()) == problem_text(
          "116", "it is an empty list, which names nothing to wait on"))

# --- malformed input ----------------------------------------------------------------
seat = Seat()
(seat.task_directory / "60.json").write_text("{ this is not json")
(seat.task_directory / "61.json").write_text(json.dumps(["a", "list"]))
(seat.task_directory / "62.json").write_text(json.dumps({"subject": "no id",
                                                          "status": "pending",
                                                          "metadata": MET}))
seat.task("63", metadata="not a dict")
check("malformed task files alone: silent", silent(seat.run()))
seat.task("64", metadata=MET)
text = context_of(seat.run()) or ""
check("malformed task files beside a due task: the due task still raised",
      text.startswith("Act on task 64 ") and text.count("Act on task") == 1, text)

seat = Seat()
seat.task("65", metadata=MET)
for name, stdin_text, fault_words in (
        ("not JSON", "not json at all", "no task was checked at this stop"),
        ("a JSON list", "[1, 2]", "JSON, but not an object, so no task was checked"),
        ("empty", "", "JSONDecodeError")):
    result = seat.run(stdin_text=stdin_text)
    check(f"malformed payload ({name}): reported on stderr, exit 1, no raise",
          reported(result, fault_words), result)
check("malformed payload: nothing recorded", not seat.state_path.exists())

seat = Seat()
seat.task("66", metadata=MET)
check("no task list id in the environment: silent", silent(seat.run(list_id=None)))
check("a task list id that is a path, even to a real list: silent",
      silent(seat.run(list_id=f"../tasks/{TASK_LIST_ID}")))
check("a task list with no directory: silent",
      silent(seat.run(list_id="nedschorus-no-such-seat-tasks")))

# --- a headless child of an agent-seat is never raised ------------------------------
seat = Seat()
seat.task("68", metadata=MET)
result = seat.run(environment_changes={"CLAUDE_CODE_SESSION_ATTENDED": "0"})
check("unattended session (a claude -p child): silent", silent(result), result)
result = seat.run(environment_changes={
    "NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER": "scripts/ghi-guide-agent-ask.py"})
check("session whose caller owns its reincarnation: silent", silent(result), result)
check("silenced sessions record nothing, so the seat's own session still raises the task",
      not seat.state_path.exists(), seat.state_path)
text = context_of(seat.run(environment_changes={"CLAUDE_CODE_SESSION_ATTENDED": None})) or ""
check("attended variable missing: the task is raised", "Act on task 68 " in text, text)
check("the attended session after them: silent, the task already raised", silent(seat.run()))

seat = Seat()
seat.task("67", metadata=MET)
seat.state_path.parent.mkdir(parents=True)
seat.state_path.write_text("{ torn")
text = context_of(seat.run()) or ""
check("unparsable state file: read as empty, task raised", "Act on task 67 " in text, text)
check("unparsable state file: replaced, so the next stop is silent", silent(seat.run()))

# --- the record is written before anything is printed ------------------------------
seat = Seat()
seat.task("70", metadata=MET)
seat.state_path.parent.parent.mkdir(parents=True)
seat.state_path.parent.write_text("a file where the state directory should be")
result = seat.run()
check("state cannot be written: reported on stderr, exit 1, and no raise goes unrecorded",
      reported(result, "could not be written, and so 1 due task(s) were not raised at this "
                       "stop; the first stop after the state file can be written raises them")
      and "no task was checked" not in result.stderr
      and "old key" not in result.stderr, result)
seat.state_path.parent.unlink()
text = context_of(seat.run()) or ""
check("state writable again: the task the failed write left unraised is raised",
      text.startswith("Act on task 70 "), text)

seat = Seat()
seat.task("71", metadata={"prerequisites": [{"pr_merged": 140}]})
seat.respond({"pr:140": "fail"})
seat.state_path.parent.parent.mkdir(parents=True)
seat.state_path.parent.write_text("a file where the state directory should be")
result = seat.run()
check("state cannot be written with nothing due: reported, saying no task went unraised",
      reported(result, "could not be written, and no task was due at this stop, so none "
                       "went unraised. Make ")
      and "were not raised" not in result.stderr
      and "no task was checked" not in result.stderr, result)

# --- task files are never written ------------------------------------------------
seat = Seat()
seat.task("80", metadata={"prerequisites": [{"pr_merged": 120}]}, blocked_by=["81"])
seat.task("81", status="completed")
seat.respond({"pr:120": {"state": "MERGED", "title": "T", "url": "https://x/120"}})
before = {path.name: path.read_bytes() for path in seat.task_directory.iterdir()}
seat.run()
seat.run()
after = {path.name: path.read_bytes() for path in seat.task_directory.iterdir()}
check("task files byte-identical and none added after runs", before == after,
      sorted(set(before) ^ set(after)))
check("the state file is outside the task directory",
      seat.state_path.exists() and seat.task_directory not in seat.state_path.parents)

# --- state is pruned ------------------------------------------------------------------
seat = Seat()
seat.task("90", metadata={"prerequisites": [{"pr_merged": 130}]})
seat.task("89", metadata=MET)
seat.respond({"pr:130": "fail"})
seat.run()
(seat.task_directory / "90.json").unlink()
(seat.task_directory / "89.json").unlink()
seat.task("91")
seat.run()
state = json.loads(seat.state_path.read_text())
check("state pruned of deleted tasks and conditions no open task names",
      state["raised"] == {} and state["checks"] == {}, state)

# --- the next-action prompt, when no walk is open and nothing runs ----------------
NEXT_ACTION_FIRST_LINE = ("No approval-walk is open and none of your work is running, so do not "
                          "stop here.")


def tool_use_record(tool_use_id):
    return {"type": "assistant", "timestamp": "2026-11-02T00:00:00Z",
            "message": {"content": [{"type": "text", "text": "x"},
                                    {"type": "tool_use", "id": tool_use_id, "name": "Bash",
                                     "input": {}}]}}


class IdleSeat(Seat):
    """A Seat whose session has a transcript and a checkout holding docs/walk."""

    def __init__(self):
        super().__init__()
        self.checkout = self.home / "seat-checkout"
        self.walk_directory = self.checkout / "docs" / "walk"
        self.walk_directory.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.checkout)], check=True)
        self.transcript = self.home / "session.jsonl"
        self.transcript.write_text("")
        self.append(tool_use_record("toolu_first"))

    def append(self, record):
        with self.transcript.open("a") as handle:
            handle.write(json.dumps(record) + "\n")

    def minutes(self, name, text):
        (self.walk_directory / f"{name}-minutes.md").write_text(text)

    def stop(self, session_id="idle-session", background_tasks=()):
        """background_tasks=None sends no list, as a claude that predates the list would."""
        payload = {
            "session_id": session_id, "transcript_path": str(self.transcript),
            "cwd": str(self.checkout), "hook_event_name": "Stop", "stop_hook_active": False}
        if background_tasks is not None:
            payload["background_tasks"] = list(background_tasks)
        return self.run(stdin_text=json.dumps(payload))


seat = IdleSeat()
seat.task("5", subject="Free task")
seat.task("6", metadata={"prerequisites": [{"pr_merged": 150}]}, subject="Waits on a PR")
seat.respond({"pr:150": {"state": "OPEN", "title": "Open", "url": "https://x/150"}})
seat.minutes("old-walk", "#next_to_present none, closed\n- Item 2: deferred twice <open>\n")
result = seat.stop()
text = context_of(result) or ""
check("next-action: idle seat gets the prompt, exit 0",
      result.returncode == 0 and text.startswith(NEXT_ACTION_FIRST_LINE), result)
check("next-action: the prompt restores the many-parts exception and names ghi-guide-agent",
      "more than 16 only for one large thing with many parts" in text
      and "scripts/ghi-guide-agent-ask.py" in text, text)
check("next-action: an unheld task is listed, a held one is counted, not listed",
      '- task 5 "Free task"' in text and "Waits on a PR" not in text
      and "1 more open task(s) are not listed: each waits on" in text, text)
check("next-action: a walk-minutes line marked <open> is listed with its file and line",
      "- old-walk-minutes.md:2: - Item 2: deferred twice <open>" in text, text)
check("next-action: the last line says a second stop without a tool ends the turn",
      text.endswith("If you end your turn again without running a tool, this hook lets the "
                    "turn end."), text)
check("next-action: the prompt is recorded before it is printed",
      json.loads(seat.state_path.read_text()).get("next_action_prompt")
      == {"session_id": "idle-session", "newest_tool_use_id": "toolu_first"})
check("next-action: no tool run since the prompt, so the next stop is silent",
      silent(seat.stop()))
seat.append(tool_use_record("toolu_second"))
check("next-action: a tool run since the prompt lets the prompt come again",
      (context_of(seat.stop()) or "").startswith(NEXT_ACTION_FIRST_LINE))
check("next-action: another session in the same list gets its own prompt",
      (context_of(seat.stop(session_id="other-session")) or "").startswith(
          NEXT_ACTION_FIRST_LINE))

seat = IdleSeat()
seat.task("5", subject="Free task")
check("next-action: with no prerequisite to check, the prompt is still handed",
      (context_of(seat.stop()) or "").startswith(NEXT_ACTION_FIRST_LINE))
check("next-action: with no prerequisite to check, the prompt is still recorded",
      seat.state_path.exists() and json.loads(seat.state_path.read_text()).get(
          "next_action_prompt") == {"session_id": "idle-session",
                                    "newest_tool_use_id": "toolu_first"})
check("next-action: with no prerequisite to check, the next stop with no tool run is silent",
      silent(seat.stop()))

seat = IdleSeat()
seat.task("9", metadata=MET, subject="Raised already")
first_text = context_of(seat.stop()) or ""
state = json.loads(seat.state_path.read_text())
for entry in state["checks"].values():
    entry["checked_at_epoch"] = 0
seat.state_path.write_text(json.dumps(state))
seat.respond({f"pr:{MERGED_PR}": "fail"})
seat.append(tool_use_record("toolu_after_raise"))
result = seat.stop()
text = context_of(result) or ""
check("next-action: a raised task's expired prerequisite that GitHub cannot answer is "
      "reported in the prompt",
      first_text.startswith("Act on task 9 ") and result.returncode == 0
      and text.startswith(NEXT_ACTION_FIRST_LINE)
      and f"This hook could not ask GitHub whether PR {MERGED_PR} is merged" in text
      and "1 more open task(s) are not listed" in text, (first_text, result))

seat = IdleSeat()
seat.minutes("live-walk", "#next_to_present item 1 of 3\n")
check("next-action: silent while an approval-walk is open", silent(seat.stop()))
seat.minutes("live-walk", "#next_to_present item 1 of 3\n#approval_walk_paused lunch\n")
check("next-action: silent while the newest walk is paused", silent(seat.stop()))
seat.minutes("second-walk", "#next_to_present item 2 of 4\n")
check("next-action: silent while two approval-walks are unclosed", silent(seat.stop()))

seat = IdleSeat()
handoffs = seat.home / ".claude" / "handoffs"
handoffs.mkdir(parents=True)
(handoffs / "idle-session-handoff-asked").write_text("40.0\n")
check("next-action: silent once a handoff is asked for", silent(seat.stop()))
(handoffs / "idle-session-handoff-asked").unlink()
(handoffs / "idle-session-handoff-deferred").write_text("40.0\n")
check("next-action: silent while a handoff is deferred", silent(seat.stop()))


def usage_record(input_tokens):
    """An assistant record whose usage gives a model-less 200,000-token window this many tokens."""
    return {"type": "assistant", "timestamp": "2026-11-02T00:00:02Z",
            "message": {"usage": {"input_tokens": input_tokens},
                        "content": [{"type": "text", "text": "x"}]}}


seat = IdleSeat()
seat.append(usage_record(70_000))
result = seat.stop()
check("next-action: silent, with no marker yet, once the context used reaches the reincarnation "
      "threshold, because the handoff hook writes its marker in parallel at the same stop",
      silent(result) and not seat.state_path.exists(), result)

seat = IdleSeat()
seat.append(usage_record(60_000))
check("next-action: context used below the reincarnation threshold still gets the prompt",
      (context_of(seat.stop()) or "").startswith(NEXT_ACTION_FIRST_LINE))

seat = IdleSeat()
seat.append({"type": "system", "subtype": "compact_boundary",
             "compactMetadata": {"cumulativeDroppedTokens": 10_000}})
seat.append(usage_record(60_000))
result = seat.stop()
check("next-action: silent once the context used plus the tokens compactions dropped reaches the "
      "reincarnation threshold, as the handoff hook counts it",
      silent(result) and not seat.state_path.exists(), result)

seat = IdleSeat()
shutil.rmtree(seat.task_directory)
result = seat.stop()
check("next-action: a task list whose directory does not exist yet still gets the prompt, "
      "with no task listed",
      result.returncode == 0
      and (context_of(result) or "").startswith(NEXT_ACTION_FIRST_LINE)
      and "- task " not in (context_of(result) or "")
      and json.loads(seat.state_path.read_text()).get("next_action_prompt")
      == {"session_id": "idle-session", "newest_tool_use_id": "toolu_first"}, result)

# One GitHub budget bounds the whole run: tasks 1 and 2 spend it in the due-task pass, so the
# next-action prompt's check of task 3's expired prerequisite must not get a budget of its own.
seat = IdleSeat()
seat.task("1", metadata={"prerequisites": [{"pr_merged": 301}]})
seat.task("2", metadata={"prerequisites": [{"pr_merged": 302}]})
seat.task("3", metadata={"prerequisites": [{"pr_merged": 303}]})
seat.state_path.parent.mkdir(parents=True)
seat.state_path.write_text(json.dumps({"raised": {"3": {"prerequisites": hook.canonical_prerequisites(
    [{"pr_merged": 303}])}}, "checks": {}}))
gh_calls_made = []


# The budget is read off a fake clock that only the fake gh moves, 0.2 seconds a call, so the
# cases do not depend on how fast the machine runs the rest of the hook. The fake gh also
# sleeps for real longer than the whole budget, as a loaded machine would.
fake_clock_seconds = [0.0]


def slow_timing_out_gh(command, *arguments, **keywords):
    if command[0] != "gh":
        return real_subprocess_run(command, *arguments, **keywords)
    gh_calls_made.append(command[3])
    time.sleep(0.35)
    fake_clock_seconds[0] += 0.2
    raise subprocess.TimeoutExpired(command, keywords.get("timeout"))


real_budget = hook.GH_CALLS_TOTAL_BUDGET_SECONDS
real_clock = hook.GitHubConditionChecker.clock
real_home = os.environ.get("HOME")
hook.subprocess.run = slow_timing_out_gh
hook.GitHubConditionChecker.clock = staticmethod(lambda: fake_clock_seconds[0])
hook.GH_CALLS_TOTAL_BUDGET_SECONDS = 0.3
os.environ["HOME"] = str(seat.home)  # the handoff module finds its markers under Path.home()
try:
    output = hook.run(json.dumps({
        "session_id": "idle-session", "transcript_path": str(seat.transcript),
        "cwd": str(seat.checkout), "hook_event_name": "Stop", "stop_hook_active": False}),
        {**seat_session_environment(), "CLAUDE_CODE_TASK_LIST_ID": TASK_LIST_ID},
        seat.home, hook.datetime.now(hook.timezone.utc))
finally:
    hook.subprocess.run = real_subprocess_run
    hook.GitHubConditionChecker.clock = real_clock
    hook.GH_CALLS_TOTAL_BUDGET_SECONDS = real_budget
    if real_home is None:
        os.environ.pop("HOME", None)
    else:
        os.environ["HOME"] = real_home
text = json.loads(output)["hookSpecificOutput"]["additionalContext"] if output else ""
check("one GitHub budget for the whole run: once the due-task pass spends it, the next-action "
      "prompt asks gh nothing more",
      gh_calls_made == ["301", "302"], gh_calls_made)
# A second budget would ask gh about task 3's prerequisite too, and report that failure as well.
check("one GitHub budget for the whole run: each condition gh could not answer is reported "
      "once, and the condition past the spent budget is not reported",
      text.startswith(NEXT_ACTION_FIRST_LINE)
      and text.count("could not ask GitHub whether PR 301 is merged") == 1
      and text.count("could not ask GitHub whether PR 302 is merged") == 1
      and "could not ask GitHub whether PR 303 is merged" not in text
      and "3 more open task(s) are not listed" in text, text)


seat = IdleSeat()
check("next-action: silent while the background_tasks list holds a running subagent",
      silent(seat.stop(background_tasks=[{"id": "a1", "type": "subagent",
                                          "status": "running"}])))

# The transcript shows a subagent launched and never finished; only the list counts.
seat = IdleSeat()
seat.append({"type": "user", "timestamp": "2026-11-02T00:00:01Z",
             "toolUseResult": {"status": "async_launched", "agentId": "a1"}})
text = context_of(seat.stop()) or ""
check("next-action: an empty background_tasks list gets the prompt, whatever the transcript "
      "shows", text.startswith(NEXT_ACTION_FIRST_LINE), text)
seat = IdleSeat()
seat.append({"type": "user", "timestamp": "2026-11-02T00:00:01Z",
             "toolUseResult": {"status": "async_launched", "agentId": "a1"}})
text = context_of(seat.stop(background_tasks=None)) or ""
check("next-action: a payload without the background_tasks list counts no work running and "
      "gets the prompt", text.startswith(NEXT_ACTION_FIRST_LINE), text)

seat = IdleSeat()
with seat.transcript.open("a") as handle:
    handle.write('{"toolUseResult": {"backgroundTaskId": "b1", broken\n')
result = seat.stop(background_tasks=[{"id": "b1", "type": "shell", "status": "running"}])
check("next-action: silent, with no fault, when the work in flight cannot be counted",
      silent(result) and not seat.state_path.exists(), result)

seat = IdleSeat()
seat.task("8", metadata=MET, subject="Due now")
text = context_of(seat.stop()) or ""
check("next-action: a due task is raised alone, with no next-action prompt",
      text.startswith("Act on task 8 ") and NEXT_ACTION_FIRST_LINE not in text, text)

seat = IdleSeat()
(seat.walk_directory / "broken-minutes.md").mkdir()
result = seat.stop()
check("next-action: a walk-minutes file that cannot be read is reported, saying tasks were "
      "checked",
      reported(result, "every task was checked and none was due, but the check whether to "
                       "hand the next-action prompt failed, so none was handed at this stop: ")
      and "start your ready work and build your next approval-walk yourself whenever no "
          "approval-walk is open" in result.stderr
      and "Tell the user this whole message" in result.stderr
      and not seat.state_path.exists(), result)

# --- approval-walk items ------------------------------------------------------------
WALK_DOCUMENT = """# Walk

## Item 1 of 3: The memory-file refusal shows each agent only its lines

Recommendation: approve.

## Item 2 of 3: The `restore` task finds its commit

## Item 2.1 of 3: Why a rebase closes it early

## Item 2.2 of 3: The design's new sentences

## Item 3 of 3: What this walk decided
"""
ITEM_1 = "The memory-file refusal shows each agent only its lines"


class WalkSeat(Seat):
    """A Seat with an approval-walk's walk-document and walk-minutes beside its task list."""

    def __init__(self, document=WALK_DOCUMENT):
        super().__init__()
        walk_directory = self.home / "checkout" / "docs" / "walk"
        walk_directory.mkdir(parents=True)
        self.document = walk_directory / "w-2026-11-12.md"
        self.document.write_text(document)
        self.minutes = walk_directory / "w-2026-11-12-minutes.md"

    def minutes_say(self, *lines):
        self.minutes.write_text("# Minutes: w-2026-11-12\n\n" + "".join(f"{line}\n" for line in lines))

    def waiting_task(self, task_id, heading, subject=None):
        self.task(task_id, subject=subject, metadata={"prerequisites": [{"approval_walk_item_decided": {
            "approval_walk_minutes_file_path": str(self.minutes),
            "approval_walk_item_heading": heading}}]})


seat = WalkSeat()
seat.waiting_task("70", ITEM_1, subject="Build item 1")
check("approval-walk item, walk-minutes not written yet: not raised, nothing named",
      silent(seat.run()))
seat.minutes_say("#next_to_present item 1 of 3",
                 'item 1 of 3: the user answered approved (2026-11-12 10:00) in his words "A", which '
                 "makes its change. Fast reads:")
check("approval-walk item answered by check but not yet closed: not raised", silent(seat.run()))
seat.minutes_say("#next_to_present item 2 of 3",
                 'item 1 of 3: the user answered approved (2026-11-12 10:00) in his words "A", which '
                 "makes its change. Fast reads:",
                 "item 1 of 3: approved; every text the change adds has had a fast read. <accepted>")
result = seat.run()
check("approval-walk item closed <accepted>: raised, with the exact text",
      context_of(result) == (f'Act on task 70 "Build item 1" now: its prerequisites are met: the '
                             f'approval-walk item "{ITEM_1}" is decided in {seat.minutes}.'
                             f"\n{DEFER_LINE}"), repr(context_of(result)))
check("approval-walk item: raised once, then silent", silent(seat.run()))
check("approval-walk item: gh never asked", seat.gh_calls() == [], seat.gh_calls())

seat = WalkSeat()
seat.waiting_task("71", f"Item 1 of 3: {ITEM_1}")
seat.minutes_say("item 1 of 3: disapproved; every text the change adds has had a fast read. <rejected>")
check("approval-walk item closed <rejected>, named with its running count: raised",
      (context_of(seat.run()) or "").startswith("Act on task 71 "))

seat = WalkSeat()
seat.waiting_task("72", ITEM_1)
seat.minutes_say("item 1 of 3: deferred; it moves to just before the summary item. <open>")
check("approval-walk item deferred, <open>: not raised", silent(seat.run()))
seat.minutes_say("item 1 of 3: deferred; it moves to just before the summary item. <open>",
                 "item 1 of 3: deferred a second time, so it leaves the walk and stays open. <open>")
check("approval-walk item deferred a second time, <open>: not raised", silent(seat.run()))

seat = WalkSeat()
seat.waiting_task("73", "Item 2 of 3: The `restore` task finds its commit")
seat.minutes_say("item 2.1 of 3: moved on; the item asked for no decision. <moved on, no decision>")
check("approval-walk item with sub-steps, one sub-step decided: not raised", silent(seat.run()))
seat.minutes_say("item 2.1 of 3: moved on; the item asked for no decision. <moved on, no decision>",
                 "item 2.2 of 3: approved; every text the change adds has had a fast read. <accepted>")
check("approval-walk item whose sub-steps are all decided: raised",
      (context_of(seat.run()) or "").startswith("Act on task 73 "))

# Items added before it while the walk runs: the walk-document's count and the item's number change.
seat = WalkSeat(document="# Walk\n\n## Item 1 of 2: First\n\n## The fix\n")
seat.waiting_task("74", "The fix")
seat.minutes_say("item 1 of 2: approved; every text the change adds has had a fast read. <accepted>")
check("approval-walk item not yet numbered: not raised, nothing named", silent(seat.run()))
seat.document.write_text("# Walk\n\n## Item 1 of 19: First\n\n## Item 2 of 19: Added\n\n"
                         "## Item 3 of 19 (deferred: moved to just before the summary item): Also added\n\n"
                         "## Item 4 of 19: The fix\n")
seat.minutes_say("item 1 of 2: approved; every text the change adds has had a fast read. <accepted>",
                 "item 2 of 19: approved; every text the change adds has had a fast read. <accepted>")
check("approval-walk item renumbered, another item decided: not raised", silent(seat.run()))
seat.minutes_say("item 1 of 2: approved; every text the change adds has had a fast read. <accepted>",
                 "item 2 of 19: approved; every text the change adds has had a fast read. <accepted>",
                 "item 4 of 19: already decided by the user-ruling of 2026-11-01; the walk does not "
                 "come back to it. <accepted>")
check("approval-walk item renumbered and decided: raised",
      (context_of(seat.run()) or "").startswith("Act on task 74 "))

seat = WalkSeat()
seat.waiting_task("75", "A heading the walk-document lacks")
seat.minutes_say("item 1 of 3: approved; every text the change adds has had a fast read. <accepted>")
result = seat.run()
check("approval-walk item whose heading is not in the walk-document: named, not raised",
      context_of(result) == problem_text(
          "75", f"the walk-document {seat.document} holds no item heading that reads \"A heading "
                "the walk-document lacks\" once its running count is left out"),
      repr(context_of(result)))
check("approval-walk item whose heading is not found: named once, then silent", silent(seat.run()))

seat = WalkSeat()
seat.waiting_task("76", ITEM_1)
seat.minutes_say("item 1 of 3: approved; every text the change adds has had a fast read. <accepted>")
seat.document.unlink()
check("approval-walk item whose walk-document does not exist: named, since the path is wrong",
      context_of(seat.run()) == problem_text(
          "76", f"the walk-document {seat.document}, which the walk-minutes path {seat.minutes} "
                "names, does not exist"))

seat = WalkSeat()
mistyped = seat.minutes.with_name("w-2026-11-21-minutes.md")
seat.task("80", metadata={"prerequisites": [{"approval_walk_item_decided": {
    "approval_walk_minutes_file_path": str(mistyped), "approval_walk_item_heading": ITEM_1}}]})
check("approval-walk item named by a mistyped walk-minutes path, neither file there: named",
      context_of(seat.run()) == problem_text(
          "80", f"the walk-document {mistyped.with_name('w-2026-11-21.md')}, which the walk-minutes "
                f"path {mistyped} names, does not exist"))

seat = Seat()
seat.task("77", metadata={"prerequisites": [{"approval_walk_item_decided": {
    "approval_walk_minutes_file_path": "docs/walk/w-minutes.md", "approval_walk_item_heading": "x"}}]})
check("approval-walk item with a relative walk-minutes path: named as unreadable",
      "is never raised as its metadata.prerequisites stand, because its entry" in (
          context_of(seat.run()) or ""))

seat = WalkSeat()
seat.waiting_task("78", ITEM_1)
seat.minutes_say("item 1 of 3: deferred; it moves to just before the summary item. <open>")
seat.task("79")
unheld, held = hook.unheld_and_held_tasks(hook.read_tasks(seat.task_directory),
                                          seat.task_directory, hook.GitHubConditionChecker({}, 0))
check("approval-walk item not decided: the next-action list counts the task held",
      unheld == ["79"] and held == 1, (unheld, held))

shutil.rmtree(SUITE_ROOT, ignore_errors=True)
print()
if failures:
    print(f"{len(failures)} FAILED: {failures}")
    sys.exit(1)
print("all cases passed")
