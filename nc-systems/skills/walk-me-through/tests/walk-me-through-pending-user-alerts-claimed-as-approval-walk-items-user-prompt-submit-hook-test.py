#!/usr/bin/env python3
"""Cases for the UserPromptSubmit hook that claims the user's pending alerts and tells the agent to add them to
his approval-walk.

Each case runs the hook as a subprocess, its real stdin-to-stdout path, with HOME pointed at a scratch directory
holding the alerts, in a scratch checkout. Prints one line per case and exits non-zero if any case fails.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().parents[4] / "scripts" / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

HERE = Path(__file__).resolve().parents[1]
HOOK = HERE / "walk-me-through-pending-user-alerts-claimed-as-approval-walk-items-user-prompt-submit-hook.py"
INSERT_PROGRAM = HERE / "walk-me-through-user-alert-insert-after-waiting-item-raise-item-count-and-record-in-walk-minutes.py"
WALK = "alerts-hook-test-walk-2026-10-27"
failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


class Case:
    def __init__(self, root, name, walk_open=False):
        self.home = root / name / "home"
        self.alerts = self.home / ".local/state/nedschorus/user-alerts"
        (self.alerts / "pending").mkdir(parents=True)
        self.checkout = root / name / "checkout"
        walk = self.checkout / "docs" / "walk"
        walk.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.checkout)], check=True)
        (walk / f"{WALK}.md").write_text("# A walk\n\n## Item 1 of 2: one\n\n## Item 2 of 2: summary\n",
                                         encoding="utf-8")
        marker = "item 1 of 2" if walk_open else "none, closed"
        (walk / f"{WALK}-minutes.md").write_text(f"#next_to_present {marker}\n", encoding="utf-8")
        self.transcript = root / name / "transcript.jsonl"

    def alert(self, alert_id, title="merge-lane-2 is down", directory="pending"):
        path = self.alerts / directory / f"{alert_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"id": alert_id, "written_at": "2026-10-27T12:00:00+00:00", "title": title,
                                    "notice_text": "text", "action": "act"}), encoding="utf-8")
        return path

    def turn_record(self, origin, text):
        with self.transcript.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"type": "user", "turnOrigin": origin,
                                     "message": {"role": "user", "content": text}}) + "\n")

    def run(self, prompt, stdin=None):
        payload = {"hook_event_name": "UserPromptSubmit", "prompt": prompt, "cwd": str(self.checkout),
                   "transcript_path": str(self.transcript)}
        result = subprocess.run([sys.executable, str(HOOK)], input=stdin or json.dumps(payload),
                                capture_output=True, text=True, env={**os.environ, "HOME": str(self.home)},
                                check=False)
        context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"] if result.stdout else ""
        return result, context

    def names(self, directory):
        return sorted(path.stem for path in (self.alerts / directory).glob("*.json"))


def run_typed_prompt_cases(root):
    case = Case(root, "nothing-pending")
    result, context = case.run("hello")
    check("with no alert pending, a typed prompt gets no output", result.returncode == 0 and result.stdout == "",
          result.stdout + result.stderr)

    case = Case(root, "no-walk")
    case.alert("alert-a")
    result, context = case.run("hello")
    check("a typed prompt with no approval-walk open claims the alert",
          case.names("claimed") == ["alert-a"] and case.names("pending") == [], repr(case.names("claimed")))
    check("with no approval-walk open, the agent is told to answer the prompt first, then open an approval-walk "
          "with the alerts alone, and is given each `#user_alert` line whole",
          result.returncode == 0 and "No approval-walk is open" in context
          and "First answer the user's prompt" in context and "\n  #user_alert alert-a" in context
          and "merge-lane-2 is down (alert alert-a" in context and str(INSERT_PROGRAM) not in context, context)

    case = Case(root, "walk-open", walk_open=True)
    case.alert("alert-a")
    case.alert("alert-b", title="the crash watcher failed")
    result, context = case.run("A")
    check("with an approval-walk open, the agent is told to run the insert program with every claimed id "
          "before acting on the prompt",
          f"approval-walk {WALK}" in context
          and f"python3 {INSERT_PROGRAM} --cwd {case.checkout} alert-a alert-b" in context
          and "Before you act on the user's prompt" in context and "No approval-walk is open" not in context,
          context)

    case = Case(root, "recorded-typed")
    case.alert("alert-a")
    case.turn_record("human", "please go on")
    case.run("please go on")
    check("a prompt the transcript records as the user's claims", case.names("claimed") == ["alert-a"])

    case = Case(root, "previous-turn-not-typed")
    case.alert("alert-a")
    case.turn_record("task_notification", "<task-notification>done</task-notification>")
    case.run("hello")
    check("when the transcript's newest turn is a previous one, the prompt decides, and a typed one claims",
          case.names("claimed") == ["alert-a"])


def run_not_typed_cases(root):
    for name, prompt in (
            ("task-notice", "<task-notification>\n<status>completed</status>\n</task-notification>"),
            ("peer", "Another Claude session sent a message:\n<cross-session-message from-name=\"merge-lane-2\">"
                     "PR merged</cross-session-message>"),
            ("peer-bare", "<cross-session-message from-name=\"merge-lane-2\">hi</cross-session-message>"),
            ("hand-back", "<agent-message from=\"ac7f5\">\n[Subagent hand-back] done\n</agent-message>")):
        case = Case(root, name)
        case.alert("alert-a")
        result, context = case.run(prompt)
        check(f"a turn started by {name} claims nothing and prints nothing",
              result.returncode == 0 and result.stdout == "" and case.names("pending") == ["alert-a"],
              result.stdout + repr(case.names("claimed")))

    case = Case(root, "recorded-peer")
    case.alert("alert-a")
    case.turn_record("peer", "please restart merge-lane-2")
    case.run("please restart merge-lane-2")
    check("a prompt the transcript records as another agent-seat's message claims nothing, whatever its text",
          case.names("pending") == ["alert-a"], repr(case.names("claimed")))

    case = Case(root, "stale-human-record")
    case.alert("alert-a")
    case.turn_record("human", "the user's previous prompt")
    case.run("<task-notification>done</task-notification>")
    check("a background-task notice claims nothing when the transcript's newest turn is the user's previous one",
          case.names("pending") == ["alert-a"], repr(case.names("claimed")))


def run_release_cases(root):
    case = Case(root, "returned")
    path = case.alert("alert-old", directory="claimed")
    old = time.time() - 31 * 60
    os.utime(path, (old, old))
    result, context = case.run("hello")
    check("a claimed alert no walk-minutes name, claimed over 30 minutes ago, is offered again on the next "
          "typed prompt and claimed afresh",
          "alert alert-old" in context and case.names("claimed") == ["alert-old"]
          and path.stat().st_mtime > old + 60, context)


def run_failure_cases(root):
    case = Case(root, "claim-fails")
    (case.alerts / "pending" / "alert-bad.json").write_text("[not an object]", encoding="utf-8")
    result, context = case.run("hello")
    check("a failure while claiming tells the agent what failed and to tell the user alerts may wait unseen",
          result.returncode == 0 and "failed while claiming alerts" in context and "Tell the user" in context
          and str(case.alerts) in context, context + result.stderr)

    case = Case(root, "walk-unreadable")
    case.alert("alert-a")
    (case.checkout / "docs/walk" / f"{WALK}-minutes.md").write_bytes(b"#next_to_present item 1 of 2 \xff\n")
    result, context = case.run("hello")
    check("when the walk files cannot be read, the agent gets both instructions, each under its condition",
          "could not tell whether an approval-walk is open" in context and "If an approval-walk is open:" in context
          and "If no approval-walk is open:" in context and "#user_alert alert-a" in context, context)

    case = Case(root, "bad-payload")
    result, _ = case.run("", stdin="not json")
    check("a payload that is not JSON is reported on stderr with exit 1",
          result.returncode == 1 and "no alert was claimed" in result.stderr, result.stderr)


with tempfile.TemporaryDirectory() as temporary_directory:
    scratch = Path(temporary_directory)
    run_typed_prompt_cases(scratch)
    run_not_typed_cases(scratch)
    run_release_cases(scratch)
    run_failure_cases(scratch)

if failures:
    print(f"\n{len(failures)} case(s) failed")
    sys.exit(1)
print("\nall cases passed")
