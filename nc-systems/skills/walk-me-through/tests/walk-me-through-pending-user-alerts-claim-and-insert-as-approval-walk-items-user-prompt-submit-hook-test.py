#!/usr/bin/env python3
"""Cases for the UserPromptSubmit hook that claims the user's pending alerts and adds them to his approval-walk.

Each case runs the hook as a subprocess, its real stdin-to-stdout path, with HOME pointed at a scratch directory
holding the alerts, in a scratch checkout. The hook claims alerts only on Linux, so each case sets the hook's
sys.platform, and the suite passes on the Mac too. Prints one line per case and exits non-zero if any case fails.
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
_attendance_check_spec = importlib.util.spec_from_file_location(
    "agent_session_unattended_by_user_check_common",
    Path(__file__).resolve().parents[4] / "nc-systems" / "general-tools"
    / "agent-session-unattended-by-user-check-common.py")
attendance_check = importlib.util.module_from_spec(_attendance_check_spec)
_attendance_check_spec.loader.exec_module(attendance_check)

HERE = Path(__file__).resolve().parents[1]
HOOK = HERE / "walk-me-through-pending-user-alerts-claim-and-insert-as-approval-walk-items-user-prompt-submit-hook.py"
INSERT_PROGRAM = HERE / "walk-me-through-user-alert-insert-as-unnumbered-item-after-waiting-item-and-record-in-walk-minutes.py"
WALK = "alerts-hook-test-walk-2026-10-27"
failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


class Case:
    def __init__(self, root, name, walk_open=False, waiting="item 1 of 2"):
        self.home = root / name / "home"
        self.alerts = self.home / ".local/state/nedschorus/user-alerts"
        (self.alerts / "pending").mkdir(parents=True)
        self.checkout = root / name / "checkout"
        walk = self.checkout / "docs" / "walk"
        walk.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.checkout)], check=True)
        (walk / f"{WALK}.md").write_text("# A walk\n\n## Item 1 of 2: one\n\n## Item 2 of 2: summary\n",
                                         encoding="utf-8")
        marker = waiting if walk_open else "none, closed"
        self.document = walk / f"{WALK}.md"
        self.minutes = walk / f"{WALK}-minutes.md"
        (walk / f"{WALK}-minutes.md").write_text(f"#next_to_present {marker}\n", encoding="utf-8")
        self.transcript = root / name / "transcript.jsonl"

    def alert(self, alert_id, title="merge-lane-2 is down", directory="pending"):
        path = self.alerts / directory / f"{alert_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"id": alert_id, "written_at": "2026-10-27T12:00:00+00:00", "title": title,
                                    "alert_text": "text", "action": "act"}), encoding="utf-8")
        return path

    def turn_record(self, origin, text):
        with self.transcript.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"type": "user", "turnOrigin": origin,
                                     "message": {"role": "user", "content": text}}) + "\n")

    def run(self, prompt, stdin=None, platform="linux", insert_run="", environment_extra=None):
        """environment_extra is added to the hook's environment, which holds neither variable that marks an
        agent-session headless, so a case reads the same in a headless reviewer as in an attended agent-session.
        insert_run, when given, is a Python expression of the arguments a and k that takes the place of the
        hook's subprocess.run of the insert program, so a case can make that program time out, fail to start or
        die by a signal, which a real run cannot be made to; every other subprocess.run, such as git's, runs."""
        payload = {"hook_event_name": "UserPromptSubmit", "prompt": prompt, "cwd": str(self.checkout),
                   "transcript_path": str(self.transcript)}
        run_hook_as_platform = ("import runpy, subprocess, sys; sys.platform = sys.argv[1]; "
                                + ("subprocess.run = (lambda real: lambda *a, **k: "
                                   f"({insert_run}) if 'user-alert-insert' in str(a[0]) else real(*a, **k))"
                                   "(subprocess.run); " if insert_run else "")
                                + "runpy.run_path(sys.argv[2], run_name='__main__')")
        environment = attendance_check.environment_without_agent_session_attendance_variables(os.environ)
        environment.update({"HOME": str(self.home)}, **(environment_extra or {}))
        result = subprocess.run([sys.executable, "-c", run_hook_as_platform, platform, str(HOOK)],
                                input=stdin or json.dumps(payload),
                                capture_output=True, text=True, env=environment, check=False)
        self.output = json.loads(result.stdout) if result.stdout else {}
        context = self.output["hookSpecificOutput"]["additionalContext"] if result.stdout else ""
        return result, context

    def names(self, directory):
        return sorted(path.stem for path in (self.alerts / directory).glob("*.json"))


def run_timeout_case():
    settings = json.loads((HERE.parents[2] / ".claude" / "settings.json").read_text(encoding="utf-8"))
    timeouts = [hook.get("timeout") for entry in settings["hooks"]["UserPromptSubmit"] for hook in entry["hooks"]
                if HOOK.name in hook.get("command", "")]
    specification = importlib.util.spec_from_file_location("user_alerts_hook", HOOK)
    hook_module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(hook_module)
    check("the insert program's limit is at most half the hook's timeout in .claude/settings.json, so a stalled "
          "insert is reported before Claude Code kills the hook",
          len(timeouts) == 1 and isinstance(timeouts[0], (int, float))
          and hook_module.INSERT_TIMEOUT_SECONDS * 2 <= timeouts[0],
          f"settings timeouts {timeouts}, INSERT_TIMEOUT_SECONDS {hook_module.INSERT_TIMEOUT_SECONDS}")


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
    document = case.document.read_text(encoding="utf-8")
    minutes = case.minutes.read_text(encoding="utf-8")
    headings = ("## Item 1 of 2: one", "## merge-lane-2 is down", "## the crash watcher failed",
                "## Item 2 of 2: summary")
    check("with an approval-walk open, the hook runs the insert program itself: both alerts become items right "
          "after the waiting item, and the walk-minutes name both",
          all(heading in document for heading in headings)
          and [document.index(heading) for heading in headings]
          == sorted(document.index(heading) for heading in headings)
          and "#user_alert alert-a" in minutes and "#user_alert alert-b" in minutes, document + minutes)
    check("with an approval-walk open, the agent is told what the hook added, with the insert program's output, "
          "and is not told to run the program",
          result.returncode == 0 and f"approval-walk {WALK}" in context
          and "The hook added these alerts" in context
          and "Added the unnumbered item `## merge-lane-2 is down`" in context
          and "Before you act on the user's prompt, add the alerts" not in context
          and "No approval-walk is open" not in context, context)

    case = Case(root, "insert-fails", walk_open=True, waiting="item 5 of 9")
    case.alert("alert-a")
    before = case.document.read_text(encoding="utf-8")
    result, context = case.run("A")
    # "run: " anchors the command's start: with sys.executable, such as /usr/bin/python3, put after "python3",
    # the text "python3 <program>" would still appear inside the command.
    check("when the insert program fails, the agent gets its exit code, its message and the command to run "
          "again, python3 then the program, and no item is added",
          result.returncode == 0 and "failed, so no item was added. The program exited 1" in context
          and "waiting item cannot be found" in context
          and f"then run: python3 {INSERT_PROGRAM} --cwd {case.checkout} alert-a\n" in context
          and case.document.read_text(encoding="utf-8") == before, context)

    for name, insert_run, code in (
            ("killed by a signal", "subprocess.CompletedProcess(a[0], -9, '', '')", "exited -9"),
            ("timed out", "(_ for _ in ()).throw(subprocess.TimeoutExpired(a[0], 60))", "exited no code"),
            ("could not start", "(_ for _ in ()).throw(OSError('no python3'))", "exited no code")):
        case = Case(root, f"insert-{name.replace(' ', '-')}", walk_open=True)
        case.alert("alert-a")
        result, context = case.run("A", insert_run=insert_run)
        check(f"when the insert program {name}, the agent is told it failed, with the command to run again, "
              "python3 then the program",
              result.returncode == 0 and f"failed, so no item was added. The program {code}" in context
              and f"then run: python3 {INSERT_PROGRAM} --cwd {case.checkout} alert-a\n" in context,
              context + result.stderr)

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


def run_headless_cases(root):
    commission = "You are the independent reviewer for the nedschorus project. Review pull request 2891."
    for name, record_origin, environment_extra in (
            ("headless-first-prompt-no-record", None, {"CLAUDE_CODE_SESSION_ATTENDED": "0"}),
            ("headless-first-prompt-sdk-record", "sdk", {"CLAUDE_CODE_SESSION_ATTENDED": "0"}),
            ("caller-owned-child", None, {"NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER": "1"})):
        case = Case(root, name)
        case.alert("alert-a")
        if record_origin:
            case.turn_record(record_origin, commission)
        result, context = case.run(commission, environment_extra=environment_extra)
        check(f"a headless agent-session's first prompt ({name}) claims nothing and prints nothing",
              result.returncode == 0 and result.stdout == "" and case.names("pending") == ["alert-a"]
              and case.names("claimed") == [], result.stdout + result.stderr + repr(case.names("claimed")))

    case = Case(root, "headless-leaves-old-claim")
    path = case.alert("alert-old", directory="claimed")
    old = time.time() - 31 * 60
    os.utime(path, (old, old))
    case.run("hello", environment_extra={"CLAUDE_CODE_SESSION_ATTENDED": "0"})
    check("a headless agent-session's prompt neither releases nor claims again an alert claimed over 30 minutes ago",
          case.names("claimed") == ["alert-old"] and abs(path.stat().st_mtime - old) < 1, repr(case.names("claimed")))

    for name, attended in (("attended-first-prompt", "1"), ("attendance-unset-first-prompt", None)):
        case = Case(root, name)
        case.alert("alert-a")
        result, context = case.run("hello", environment_extra={} if attended is None
                                   else {"CLAUDE_CODE_SESSION_ATTENDED": attended})
        check(f"an attended agent-session's first typed prompt, with no record yet ({name}), claims the alert",
              case.names("claimed") == ["alert-a"] and "alert alert-a" in context, context + result.stderr)


def run_mac_cases(root):
    case = Case(root, "mac")
    case.alert("alert-a")
    result, context = case.run("hello", platform="darwin")
    check("on the Mac a typed prompt claims nothing and prints nothing",
          result.returncode == 0 and result.stdout == "" and case.names("pending") == ["alert-a"],
          result.stdout + result.stderr + repr(case.names("claimed")))


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
    system_message = case.output.get("systemMessage", "")
    check("a failure while claiming shows the user, as a systemMessage, that alerts may wait unseen",
          result.returncode == 0 and "may be waiting unseen" in system_message
          and str(case.alerts) in system_message, json.dumps(case.output) + result.stderr)
    check("a failure while claiming tells the agent what failed and that the user has been shown it",
          "failed while claiming alerts" in context and "has shown the user this sentence" in context
          and system_message in context, context)

    case = Case(root, "walk-unreadable")
    case.alert("alert-a")
    (case.checkout / "docs/walk" / f"{WALK}-minutes.md").write_bytes(b"#next_to_present item 1 of 2 \xff\n")
    result, context = case.run("hello")
    check("when the walk files cannot be read, the agent gets both instructions, each under its condition",
          "could not tell whether an approval-walk is open" in context and "If an approval-walk is open:" in context
          and "If no approval-walk is open:" in context and "#user_alert alert-a" in context, context)

    case = Case(root, "two-walks-unclosed", walk_open=True)
    case.alert("alert-a")
    second_minutes = case.checkout / "docs/walk" / "a-second-walk-minutes.md"
    second_minutes.write_text("#next_to_present item 4 of 9\n", encoding="utf-8")
    result, context = case.run("hello")
    check("with two approval-walks unclosed, the agent gets both instructions and the error naming each "
          "walk-minutes file",
          result.returncode == 0 and "MoreThanOneUnclosedApprovalWalk" in context
          and str(second_minutes.resolve()) in context and f"{WALK}-minutes.md" in context
          and "If an approval-walk is open:" in context and "If no approval-walk is open:" in context
          and "#user_alert alert-a" in context and case.names("claimed") == ["alert-a"], context + result.stderr)

    case = Case(root, "bad-payload")
    result, _ = case.run("", stdin="not json")
    check("a payload that is not JSON is reported on stderr with exit 1",
          result.returncode == 1 and "no alert was claimed" in result.stderr, result.stderr)


with tempfile.TemporaryDirectory() as temporary_directory:
    scratch = Path(temporary_directory)
    run_typed_prompt_cases(scratch)
    run_not_typed_cases(scratch)
    run_headless_cases(scratch)
    run_mac_cases(scratch)
    run_release_cases(scratch)
    run_failure_cases(scratch)
    run_timeout_case()

if failures:
    print(f"\n{len(failures)} case(s) failed")
    sys.exit(1)
print("\nall cases passed")
