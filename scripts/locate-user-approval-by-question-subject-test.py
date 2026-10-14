#!/usr/bin/env python3
"""Tests for scripts/locate-user-approval-by-question-subject.py: how it pairs
an agent's question with the user's answer in a transcript, what it skips as
not the user's, how it filters walk-minutes, commits and pull requests by the
words and the date, the guidance it prints when too much or nothing matches,
and how it reports a place it could not search.

Every case runs the program against scratch directories named through
LOCATE_USER_APPROVAL_PLAN_JSON, with the variables that redirect git removed
first. `gh` and `ssh` are stand-ins on PATH that log
their arguments and answer as each case asks; nothing reaches GitHub or
ned-box. `grep` on PATH passes through to the real grep, and can add a path
that does not exist to its list. `git` is the real one, on a scratch repository.

LOCATE_USER_APPROVAL_PROGRAM_UNDER_TEST names a different copy of the program
to test.

Run: python3 scripts/locate-user-approval-by-question-subject-test.py   (exit 0 = all passed)
"""

import importlib.util
import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import tempfile

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent

# Before anything runs git: a run started with GIT_DIR set, or with another
# variable that redirects git, must still build this suite's scratch
# repository where the suite says, not in the repository the variable names.
_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    SCRIPTS_DIR / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

PROGRAM = pathlib.Path(
    os.environ.get("LOCATE_USER_APPROVAL_PROGRAM_UNDER_TEST")
    or SCRIPTS_DIR / "locate-user-approval-by-question-subject.py")

STAND_IN_GH = """#!/usr/bin/env python3
import json, os, sys
with open(os.environ["FAKE_GH_ARGV_LOG"], "a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\n")
mode = os.environ.get("FAKE_GH_MODE", "ok")
if mode == "fail":
    sys.stderr.write("To get started with GitHub CLI, please run:  gh auth login\\n")
    sys.exit(4)
sys.stdout.write(os.environ.get("FAKE_GH_JSON", "[]"))
"""

STAND_IN_SSH = """#!/usr/bin/env python3
import json, os, subprocess, sys
with open(os.environ["FAKE_SSH_ARGV_LOG"], "a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\n")
if os.environ.get("FAKE_SSH_MODE", "ok") == "unreachable":
    sys.stderr.write("ssh: connect to host ned-box port 22: No route to host\\n")
    sys.exit(255)
if os.environ.get("FAKE_SSH_MODE", "ok") == "hang":
    import time
    time.sleep(60)
sys.exit(subprocess.run(["sh", "-c", sys.argv[-1]]).returncode)
"""

STAND_IN_GREP = """#!/usr/bin/env python3
import os, subprocess, sys
result = subprocess.run([os.environ["FAKE_REAL_GREP"], *sys.argv[1:]])
extra = os.environ.get("FAKE_GREP_EXTRA_PATH")
if extra and "-rliF" in sys.argv[1:]:
    print(extra, flush=True)
    sys.exit(0)
sys.exit(result.returncode)
"""

REAL_GREP = shutil.which("grep")
RUNNING_AS_ROOT = hasattr(os, "geteuid") and os.geteuid() == 0

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS: {case_name}")
    else:
        print(f"FAIL: {case_name}" + (f"\n      {detail}" if detail else ""))
        failures.append(case_name)


def clean_environment():
    return dict(os.environ)


def git(cwd, *arguments):
    return subprocess.run(["git", "-C", str(cwd), *arguments], check=True, capture_output=True,
                          text=True, env=clean_environment()).stdout.strip()


def assistant(text, timestamp, sidechain=False):
    return {"type": "assistant", "timestamp": timestamp, "isSidechain": sidechain,
            "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


def user(text, timestamp):
    return {"type": "user", "timestamp": timestamp, "message": {"role": "user", "content": text}}


def tool_result(timestamp):
    return {"type": "user", "timestamp": timestamp, "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "t1", "content": "y"}]}}


def notification(text, timestamp):
    return {"type": "user", "timestamp": timestamp, "message": {"role": "user", "content":
            f"<task-notification>\n<summary>{text}</summary>\n</task-notification>"}}


def queued_human(text, timestamp):
    return {"type": "attachment", "timestamp": timestamp, "attachment": {
        "type": "queued_command", "prompt": text, "origin": {"kind": "human"}}}


def write_transcript(directory, name, records):
    path = pathlib.Path(directory) / "-home-someone-project" / f"{name}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(record) + "\n" for record in records))
    return path


class Scratch:
    """A scratch plan: walk dir, two transcript dirs, a git repository, stand-in gh and ssh."""

    def __init__(self, base):
        self.base = pathlib.Path(base)
        self.walk = self.base / "walk"
        self.walk.mkdir()
        self.transcripts = self.base / "transcripts"
        self.transcripts.mkdir()
        self.second_transcripts = self.base / "mac-copy"
        self.second_transcripts.mkdir()
        self.repository = self.base / "repository"
        self.repository.mkdir()
        git(self.repository, "init", "-q", "-b", "main")
        git(self.repository, "config", "user.email", "test@example.invalid")
        git(self.repository, "config", "user.name", "test")
        git(self.repository, "commit", "-q", "--allow-empty", "-m", "Unrelated start")
        self.bin = self.base / "bin"
        self.bin.mkdir()
        for name, text in (("gh", STAND_IN_GH), ("ssh", STAND_IN_SSH), ("grep", STAND_IN_GREP)):
            path = self.bin / name
            path.write_text(text)
            path.chmod(0o755)
        self.gh_log = self.base / "gh-argv.log"
        self.ssh_log = self.base / "ssh-argv.log"
        self.ssh_target = None

    def plan(self):
        return {"walk_minutes": {"directory": str(self.walk), "ssh_target": self.ssh_target},
                "transcript_directories": [str(self.transcripts), str(self.second_transcripts)],
                "repository": str(self.repository),
                "github_repository": "owner/repository"}

    def run(self, *arguments, gh_mode="ok", gh_json="[]", ssh_mode="ok", plan=None,
            extra_environment=None):
        environment = clean_environment()
        environment.update({
            "FAKE_REAL_GREP": REAL_GREP,
            "LOCATE_USER_APPROVAL_PLAN_JSON": json.dumps(plan or self.plan()),
            "PATH": f"{self.bin}{os.pathsep}{environment.get('PATH', '')}",
            "FAKE_GH_ARGV_LOG": str(self.gh_log), "FAKE_GH_MODE": gh_mode, "FAKE_GH_JSON": gh_json,
            "FAKE_SSH_ARGV_LOG": str(self.ssh_log), "FAKE_SSH_MODE": ssh_mode,
        })
        environment.update(extra_environment or {})
        result = subprocess.run([sys.executable, str(PROGRAM), *arguments], capture_output=True,
                                text=True, env=environment, timeout=120)
        return result

    def logged(self, log):
        if not log.exists():
            return []
        return [json.loads(line) for line in log.read_text().splitlines()]


def section(stdout, heading_start):
    """Return the lines of the section whose heading starts with heading_start."""
    lines = stdout.splitlines()
    for index, line in enumerate(lines):
        if line.startswith(heading_start):
            body = []
            for following in lines[index + 1:]:
                if not following.strip():
                    break
                body.append(following)
            return line, body
    return None, []


def scratch():
    return tempfile.TemporaryDirectory(prefix="locate-user-approval-test-")


# Pairing: the user's next genuine message is the answer.
with scratch() as base:
    s = Scratch(base)
    write_transcript(s.transcripts, "pairing", [
        assistant("Shall I build the bwrap sandbox? Y builds it.", "2026-10-03T10:00:00Z"),
        user("<system-reminder>a reminder, not the user</system-reminder>", "2026-10-03T10:00:01Z"),
        tool_result("2026-10-03T10:00:02Z"),
        assistant("bwrap sidechain text", "2026-10-03T10:00:03Z", sidechain=True),
        user("y", "2026-10-03T10:00:04Z"),
    ])
    result = s.run("bwrap", "sandbox")
    heading, body = section(result.stdout, f"agent-session transcripts in {s.transcripts}")
    check("a matching agent message is paired with the user's next genuine message",
          heading is not None and any(line.strip() == "User:  y" for line in body), result.stdout)
    check("a system reminder and a tool result are not taken for the user's answer",
          "a reminder, not the user" not in result.stdout, result.stdout)
    check("the pair carries the answer's time and the transcript's path",
          any("2026-10-03 10:00 UTC" in line and "pairing.jsonl" in line for line in body), body)
    check("a fully searched run exits 0", result.returncode == 0, result.stderr)

with scratch() as base:
    s = Scratch(base)
    write_transcript(s.transcripts, "two-questions", [
        assistant("First: the bwrap plan, part one.", "2026-10-03T10:00:00Z"),
        assistant("Second: shall I build bwrap now?", "2026-10-03T10:00:01Z"),
        user("yes go", "2026-10-03T10:00:02Z"),
    ])
    result = s.run("bwrap")
    heading, body = section(result.stdout, f"agent-session transcripts in {s.transcripts}")
    stripped = [line.strip() for line in body]
    check("several matching agent messages before one answer make one pair, shown with the last "
          "and a count of the others",
          heading is not None and "1 found" in heading
          and any(line.startswith("Agent:") and "Second" in line for line in stripped)
          and not any("First" in line for line in stripped)
          and any("1 earlier matching agent message" in line for line in stripped)
          and "User:  yes go" in stripped
          and not any(line.startswith("User replied to:") for line in stripped), body)

with scratch() as base:
    s = Scratch(base)
    write_transcript(s.transcripts, "queued", [
        assistant("Approve the bwrap change?", "2026-10-03T10:00:00Z"),
        queued_human("approved, go ahead", "2026-10-03T10:00:05Z"),
    ])
    result = s.run("bwrap")
    check("a message the user typed while the agent worked counts as the answer",
          "User:  approved, go ahead" in result.stdout, result.stdout)

with scratch() as base:
    s = Scratch(base)
    write_transcript(s.transcripts, "unanswered", [
        assistant("Shall I build bwrap?", "2026-10-03T10:00:00Z"),
    ])
    result = s.run("bwrap")
    check("a matching question with no message after it is left out by default",
          "Shall I build bwrap?" not in result.stdout and "(no user message followed)" not in result.stdout,
          result.stdout)
    included = s.run("bwrap", "--include-unanswered")
    check("--include-unanswered lists a matching question with no message after it",
          "Shall I build bwrap?" in included.stdout and "(no user message followed)" in included.stdout,
          included.stdout)

# A notification and the agent's acknowledgement of it between the question and the answer.
with scratch() as base:
    s = Scratch(base)
    write_transcript(s.transcripts, "notification-between", [
        assistant("Shall I build the bwrap sandbox? Y builds it.", "2026-10-03T10:00:00Z"),
        notification("Agent \"fork\" finished", "2026-10-03T10:01:00Z"),
        assistant("Still waiting on your answer about the sandbox.", "2026-10-03T10:01:05Z"),
        user("y", "2026-10-03T10:02:00Z"),
    ])
    result = s.run("bwrap")
    _, body = section(result.stdout, f"agent-session transcripts in {s.transcripts}")
    stripped = [line.strip() for line in body]
    check("a notification does not separate a question from its answer, and the acknowledgement the "
          "user's message followed is shown as what the user replied to",
          any(line.startswith("Agent:") and "Shall I build the bwrap sandbox" in line for line in stripped)
          and "User replied to: Still waiting on your answer about the sandbox." in stripped
          and "User:  y" in stripped
          and not any("Agent \"fork\" finished" in line for line in stripped), body)

# The commonest approval-walk prompt, short and after a notification, is what the user replied to.
with scratch() as base:
    s = Scratch(base)
    write_transcript(s.transcripts, "walk-prompt-after-notification", [
        assistant("Item 3 of 9: build the bwrap sandbox for suites that send signals.", "2026-10-03T10:00:00Z"),
        notification("Agent \"fork\" finished", "2026-10-03T10:01:00Z"),
        assistant("Item 4 of 9: keep the old lock on the Mac. Y to approve, N to disapprove, D to defer.",
                  "2026-10-03T10:01:05Z"),
        user("y", "2026-10-03T10:02:00Z"),
    ])
    result = s.run("bwrap")
    check("a short Y/N/D walk prompt after a notification is shown as what the user replied to",
          "User replied to: Item 4 of 9: keep the old lock on the Mac. Y to approve, N to disapprove, "
          "D to defer." in result.stdout, result.stdout)

# A short summary after a notification is shown as what the user replied to, which is what happened.
with scratch() as base:
    s = Scratch(base)
    write_transcript(s.transcripts, "summary-after-notification", [
        assistant("Shall I build bwrap?", "2026-10-03T10:00:00Z"),
        notification("Agent \"fork\" finished", "2026-10-03T10:01:00Z"),
        assistant("Summary: the review finished; still waiting for your answer.", "2026-10-03T10:01:05Z"),
        user("y", "2026-10-03T10:02:00Z"),
    ])
    result = s.run("bwrap")
    check("a short summary after a notification is shown as what the user replied to",
          "User replied to: Summary: the review finished; still waiting for your answer." in result.stdout
          and "Shall I build bwrap?" in result.stdout, result.stdout)

# A short question after a notification is kept: it can be what the user answered.
with scratch() as base:
    s = Scratch(base)
    write_transcript(s.transcripts, "short-question-after-notification", [
        assistant("Shall I build bwrap?", "2026-10-03T10:00:00Z"),
        notification("Agent \"fork\" finished", "2026-10-03T10:01:00Z"),
        assistant("Shall I delete the stale branch instead?", "2026-10-03T10:01:05Z"),
        user("y", "2026-10-03T10:02:00Z"),
    ])
    result = s.run("bwrap")
    _, body = section(result.stdout, f"agent-session transcripts in {s.transcripts}")
    stripped = [line.strip() for line in body]
    check("a short question after a notification is kept and shown as what the user replied to, "
          "so the answer is not given to the earlier question alone",
          any(line.startswith("Agent:") and "Shall I build bwrap?" in line for line in stripped)
          and "User replied to: Shall I delete the stale branch instead?" in stripped
          and "User:  y" in stripped, body)

with scratch() as base:
    s = Scratch(base)
    write_transcript(s.transcripts, "only-question-after-notification", [
        assistant("A long report about other work, with no question in it.", "2026-10-03T10:00:00Z"),
        notification("Agent \"fork\" finished", "2026-10-03T10:01:00Z"),
        assistant("Shall I merge the bwrap change?", "2026-10-03T10:01:05Z"),
        user("y", "2026-10-03T10:02:00Z"),
    ])
    result = s.run("bwrap")
    _, body = section(result.stdout, f"agent-session transcripts in {s.transcripts}")
    stripped = [line.strip() for line in body]
    check("a matching short question after a notification is still found and paired",
          any(line.startswith("Agent:") and "Shall I merge the bwrap change?" in line for line in stripped)
          and "User:  y" in stripped, (result.stdout, body))

with scratch() as base:
    s = Scratch(base)
    write_transcript(s.transcripts, "recommendation-after-notification", [
        assistant("Shall I build bwrap?", "2026-10-03T10:00:00Z"),
        notification("Agent \"fork\" finished", "2026-10-03T10:01:00Z"),
        assistant("The fork finished. I recommend keeping the branch.", "2026-10-03T10:01:05Z"),
        user("y", "2026-10-03T10:02:00Z"),
    ])
    result = s.run("bwrap")
    check("a short message after a notification that makes a recommendation is kept as what the user "
          "replied to",
          "User replied to: The fork finished. I recommend keeping the branch." in result.stdout,
          result.stdout)

# A question already answered is not paired again with a later user message.
with scratch() as base:
    s = Scratch(base)
    write_transcript(s.transcripts, "answered-once", [
        assistant("Shall I build bwrap?", "2026-10-03T10:00:00Z"),
        user("first-answer", "2026-10-03T10:00:01Z"),
        assistant("Something unrelated.", "2026-10-03T10:00:02Z"),
        user("second-answer", "2026-10-03T10:00:03Z"),
    ])
    result = s.run("bwrap", "--include-unanswered")
    check("a question already answered is not paired again with a later user message",
          "first-answer" in result.stdout and "second-answer" not in result.stdout, result.stdout)

# Answered pairs are listed before unanswered ones.
with scratch() as base:
    s = Scratch(base)
    write_transcript(s.transcripts, "answered-old", [
        assistant("Shall I build bwrap? (old)", "2026-10-01T10:00:00Z"), user("old-yes", "2026-10-01T10:00:01Z")])
    write_transcript(s.transcripts, "unanswered-new", [
        assistant("Shall I keep bwrap? (new, never answered)", "2026-10-04T10:00:00Z")])
    result = s.run("bwrap", "--include-unanswered")
    output = result.stdout
    check("answered pairs are listed before unanswered ones, even when older",
          0 < output.find("old-yes") < output.find("never answered"), output)

# --all-words and --since.
with scratch() as base:
    s = Scratch(base)
    write_transcript(s.transcripts, "words", [
        assistant("Only one word here: bwrap.", "2026-10-03T10:00:00Z"),
        user("answer-one", "2026-10-03T10:00:01Z"),
        assistant("Both words: bwrap and sandbox.", "2026-10-03T10:00:02Z"),
        user("answer-two", "2026-10-03T10:00:03Z"),
    ])
    any_result = s.run("bwrap", "sandbox")
    all_result = s.run("bwrap", "sandbox", "--all-words")
    check("by default a message holding any of the words matches",
          "answer-one" in any_result.stdout and "answer-two" in any_result.stdout, any_result.stdout)
    check("--all-words requires every word in the same message",
          "answer-one" not in all_result.stdout and "answer-two" in all_result.stdout, all_result.stdout)

with scratch() as base:
    s = Scratch(base)
    write_transcript(s.transcripts, "dates", [
        assistant("Old bwrap question", "2026-09-01T10:00:00Z"),
        user("old-answer", "2026-09-01T10:00:01Z"),
        assistant("New bwrap question", "2026-10-03T10:00:00Z"),
        user("new-answer", "2026-10-03T10:00:01Z"),
    ])
    result = s.run("bwrap", "--since", "2026-10-01")
    check("--since leaves out a pair older than the date",
          "new-answer" in result.stdout and "old-answer" not in result.stdout, result.stdout)

# Ordering, the cap, and both transcript directories.
with scratch() as base:
    s = Scratch(base)
    write_transcript(s.transcripts, "older", [
        assistant("bwrap question A", "2026-10-01T10:00:00Z"), user("answer-A", "2026-10-01T10:00:01Z")])
    write_transcript(s.transcripts, "newer", [
        assistant("bwrap question B", "2026-10-02T10:00:00Z"), user("answer-B", "2026-10-02T10:00:01Z")])
    write_transcript(s.second_transcripts, "mac", [
        assistant("bwrap question C", "2026-10-03T10:00:00Z"), user("answer-C", "2026-10-03T10:00:01Z")])
    result = s.run("bwrap")
    output = result.stdout
    check("pairs are listed newest first",
          0 < output.find("answer-B") < output.find("answer-A"), output)
    check("the second transcript directory is searched too", "answer-C" in output, output)

with scratch() as base:
    s = Scratch(base)
    records = []
    for index in range(25):
        records.append(assistant(f"bwrap question {index:02d}", f"2026-10-03T10:{index:02d}:00Z"))
        records.append(user(f"answer-{index:02d}", f"2026-10-03T10:{index:02d}:30Z"))
    write_transcript(s.transcripts, "many", records)
    result = s.run("bwrap")
    heading, body = section(result.stdout, f"agent-session transcripts in {s.transcripts}")
    check("more than 20 pairs: 20 are shown and the rest are counted",
          heading is not None and "25 found" in heading and "showing 20" in heading
          and any("and 5 more not shown" in line for line in body)
          and "answer-24" in result.stdout and "answer-04" not in result.stdout, result.stdout)
    check("more matches than are shown prints the too-wide guidance",
          "Too wide" in result.stdout and "--all-words" in result.stdout
          and "--since" in result.stdout, result.stdout)

with scratch() as base:
    s = Scratch(base)
    write_transcript(s.transcripts, "few", [
        assistant("bwrap question", "2026-10-03T10:00:00Z"), user("answer", "2026-10-03T10:00:01Z")])
    result = s.run("bwrap")
    check("a few matches print no too-wide guidance", "Too wide" not in result.stdout, result.stdout)
    check("matches print how to read a pair with no \"User replied to\" line",
          "When a pair has no \"User replied to\" line: the user's message answers the Agent line."
          in result.stdout, result.stdout)
    check("matches print that a \"User replied to\" line, not the Agent line, is what the user answered",
          "When a pair has a \"User replied to\" line: the user's message answers that line, not "
          "the Agent line." in result.stdout, result.stdout)
    check("matches print what to report when the replied-to line is about the same subject, and when not",
          "If the replied-to line asks about the same subject as the Agent line: report the "
          "replied-to line and the user's message." in result.stdout
          and "If the replied-to line asks about something else: the Agent line's question was not "
          "answered in this pair; do not report this pair as its answer." in result.stdout,
          result.stdout)
    check("matches print that only a yes approves, and that a question, a no or a change is reported as that",
          "A user's message approves only if it says yes, such as \"y\" or \"yes\", to the message "
          "it answers." in result.stdout
          and "If the user's message is a question, a no, or a change: report it as that, not as an "
          "approval." in result.stdout, result.stdout)
    check("answered matches with nothing left out print no --include-unanswered instruction",
          "--include-unanswered" not in result.stdout, result.stdout)

# Only unanswered matches: they are counted and named, never reported as nothing found.
with scratch() as base:
    s = Scratch(base)
    write_transcript(s.transcripts, "zorblax", [assistant("Shall I build zorblax?", "2026-10-03T10:00:00Z")])
    result = s.run("zorblax")
    check("when the only matches are unanswered, the report says how many were left out and names "
          "--include-unanswered",
          "1 matching agent message(s) that no user message followed are not shown" in result.stdout
          and "--include-unanswered" in result.stdout, result.stdout)
    check("when matches were left out, the report never says nothing matched or not found",
          "Not found in these places." not in result.stdout and "Nothing matched" not in result.stdout,
          result.stdout)
    check("only unanswered matches tell the agent what to report when the question was asked but not answered",
          "If the question appears only among the unanswered messages: report that it was asked "
          "and that no answer was found in these places." in result.stdout, result.stdout)
    check("only unanswered matches, every place searched, exits 0", result.returncode == 0, result.stderr)

# Every matching message in a group the user never answered is counted as left out.
with scratch() as base:
    s = Scratch(base)
    write_transcript(s.transcripts, "two-unanswered", [
        assistant("Shall I build zorblax?", "2026-10-03T10:00:00Z"),
        assistant("Or shall I delete zorblax?", "2026-10-03T10:00:05Z"),
    ])
    result = s.run("zorblax")
    check("two matching messages no user message followed are both counted as left out",
          "2 matching agent message(s) that no user message followed are not shown" in result.stdout,
          result.stdout)

# A place with answered pairs also says how many unanswered matches it left out.
with scratch() as base:
    s = Scratch(base)
    write_transcript(s.transcripts, "answered", [
        assistant("Shall I build zorblax?", "2026-10-03T10:00:00Z"), user("yes-answer", "2026-10-03T10:00:01Z")])
    write_transcript(s.transcripts, "unanswered", [
        assistant("Shall I keep zorblax?", "2026-10-04T10:00:00Z")])
    result = s.run("zorblax")
    _, body = section(result.stdout, f"agent-session transcripts in {s.transcripts}")
    check("a place with answered pairs names the unanswered matches it left out",
          "yes-answer" in result.stdout
          and any("1 matching agent message(s) that no user message followed are not shown" in line
                  for line in body), (result.stdout, body))
    check("with answered pairs shown, --include-unanswered is suggested only if none of them is the question",
          "Only if no answered pair above is the question you are looking for: run again with "
          "--include-unanswered" in result.stdout, result.stdout)

# --since applies to each message of an unanswered group, not only the newest.
with scratch() as base:
    s = Scratch(base)
    write_transcript(s.transcripts, "group-across-cutoff", [
        assistant("Shall I build zorblax? (before the cutoff)", "2026-09-30T23:00:00Z"),
        assistant("Shall I keep zorblax? (on the cutoff day)", "2026-10-01T09:00:00Z")])
    result = s.run("zorblax", "--since", "2026-10-01")
    check("an unanswered group spanning --since counts only its messages on or after the date",
          "1 matching agent message(s) that no user message followed are not shown" in result.stdout
          and "2 matching agent message(s)" not in result.stdout, result.stdout)
    write_transcript(s.transcripts, "group-on-cutoff-day", [
        assistant("Shall I rename zorblax? (on the cutoff day, early)", "2026-10-01T08:00:00Z"),
        assistant("Shall I move zorblax? (on the cutoff day, later)", "2026-10-01T10:00:00Z")])
    result = s.run("zorblax", "--since", "2026-10-01")
    check("earlier messages of a group dated on the --since day itself are still counted",
          "3 matching agent message(s) that no user message followed are not shown" in result.stdout,
          result.stdout)

# --since keeps an answered pair by its answer's date and leaves its earlier matching messages counted.
with scratch() as base:
    s = Scratch(base)
    write_transcript(s.transcripts, "answered-across-cutoff", [
        assistant("Shall I build zorblax? (first)", "2026-09-29T10:00:00Z"),
        assistant("Shall I build zorblax? (asked again)", "2026-09-30T10:00:00Z"),
        user("answered-after-cutoff", "2026-10-01T10:00:00Z")])
    result = s.run("zorblax", "--since", "2026-10-01")
    check("--since keeps an answered pair whose answer is on or after the date",
          "answered-after-cutoff" in result.stdout, result.stdout)
    check("an answered pair kept by --since still counts its earlier matching messages from before the date",
          "(1 earlier matching agent message(s) before the same user message not shown)" in result.stdout,
          result.stdout)

# A matching message with no timestamp is kept and counted: nothing dates it.
with scratch() as base:
    s = Scratch(base)
    write_transcript(s.transcripts, "undated-earlier", [
        assistant("Shall I build zorblax? (no timestamp)", ""),
        assistant("Shall I keep zorblax? (dated)", "2026-10-02T10:00:00Z")])
    result = s.run("zorblax", "--since", "2026-10-01")
    check("an unanswered group's earlier message with no timestamp is counted under --since",
          "2 matching agent message(s) that no user message followed are not shown" in result.stdout,
          result.stdout)

# --since leaves an older unanswered match out before it is counted.
with scratch() as base:
    s = Scratch(base)
    write_transcript(s.transcripts, "old-unanswered", [
        assistant("Shall I build zorblax? (old)", "2026-09-01T10:00:00Z"),
        user("old-yes", "2026-09-01T10:00:01Z"),
        assistant("Shall I keep zorblax? (old, never answered)", "2026-09-01T10:00:02Z")])
    write_transcript(s.transcripts, "new-answered", [
        assistant("Shall I build zorblax? (new)", "2026-10-04T10:00:00Z"), user("new-yes", "2026-10-04T10:00:01Z")])
    result = s.run("zorblax", "--since", "2026-10-01")
    check("--since leaves out an older unanswered match before counting what was left out",
          "new-yes" in result.stdout and "not shown" not in result.stdout, result.stdout)

# Nothing found.
with scratch() as base:
    s = Scratch(base)
    write_transcript(s.transcripts, "other", [
        assistant("Something else entirely", "2026-10-03T10:00:00Z"), user("y", "2026-10-03T10:00:01Z")])
    result = s.run("bwrap", "sandbox")
    check("nothing found says \"Not found in these places\" and lists every place searched",
          "Not found in these places." in result.stdout
          and str(s.walk) in result.stdout and str(s.transcripts) in result.stdout
          and str(s.second_transcripts) in result.stdout and "commit messages" in result.stdout
          and "pull requests" in result.stdout, result.stdout)
    check("nothing found tells the agent to try at most two other names before reporting",
          "another name for the subject" in result.stdout
          and "Try at most two other names, that is, two more runs." in result.stdout, result.stdout)
    check("nothing found never reports that no approval was given",
          "never \"no approval\"" in result.stdout
          and "No approval" not in result.stdout, result.stdout)
    check("nothing found, every place searched, exits 0", result.returncode == 0, result.stderr)

# Walk-minutes.
with scratch() as base:
    s = Scratch(base)
    (s.walk / "sandbox-choice-2026-10-04-minutes.md").write_text(
        "| 1 | bwrap for suites that send signals | Y (\"y\") | accepted |\n"
        "| 2 | something unrelated | N | rejected |\n")
    (s.walk / "sandbox-choice-2026-10-04.md").write_text("bwrap in the walk-document, not minutes\n")
    (s.walk / "old-walk-2026-09-01-minutes.md").write_text("bwrap ruled long ago, 2026-09-01\n")
    result = s.run("bwrap")
    heading, body = section(result.stdout, f"walk-minutes in {s.walk}")
    check("a walk-minutes line holding the word is shown with its file, line and date",
          heading is not None
          and any("2026-10-04" in line and "sandbox-choice-2026-10-04-minutes.md:1:" in line
                  for line in body), result.stdout)
    check("only walk-minutes files are searched, not walk-documents",
          "not minutes" not in result.stdout, result.stdout)
    since_result = s.run("bwrap", "--since", "2026-10-01")
    check("--since leaves out walk-minutes dated before it",
          "ruled long ago" not in since_result.stdout
          and "suites that send signals" in since_result.stdout, since_result.stdout)
    all_result = s.run("bwrap", "unrelated", "--all-words")
    check("--all-words requires every word in the same walk-minutes line",
          "suites that send signals" not in all_result.stdout, all_result.stdout)

with scratch() as base:
    s = Scratch(base)
    s.ssh_target = "nedlern@fake-box"
    (s.walk / "remote-2026-10-04-minutes.md").write_text("bwrap approved remotely\n")
    result = s.run("bwrap")
    calls = s.logged(s.ssh_log)
    check("from the Mac the walk-minutes are searched over ssh",
          "bwrap approved remotely" in result.stdout and calls and calls[0][-2] == "nedlern@fake-box",
          (result.stdout, calls))
    unreachable = s.run("bwrap", ssh_mode="unreachable")
    check("an unreachable ned-box is listed as not searched, with the remedy, and exits 1",
          unreachable.returncode == 1 and "NOT searched" in unreachable.stdout
          and "ssh nedlern@ned-box true" in unreachable.stdout, unreachable.stdout)

# Commit messages.
with scratch() as base:
    s = Scratch(base)
    git(s.repository, "commit", "-q", "--allow-empty", "-m", "Run suites inside bwrap\n\nApproved by the user.")
    git(s.repository, "commit", "-q", "--allow-empty", "-m", "Sandbox notes only")
    result = s.run("bwrap")
    check("a commit whose message holds the word is listed with its subject",
          "Run suites inside bwrap" in result.stdout and "Unrelated start" not in result.stdout,
          result.stdout)
    all_result = s.run("bwrap", "sandbox", "--all-words")
    check("--all-words requires every word in one commit message",
          "Run suites inside bwrap" not in all_result.stdout
          and "Sandbox notes only" not in all_result.stdout, all_result.stdout)

# Pull requests.
with scratch() as base:
    s = Scratch(base)
    gh_json = json.dumps([
        {"title": "Older PR about bwrap", "url": "https://example.invalid/pull/1", "updatedAt": "2026-10-01T00:00:00Z"},
        {"title": "Newer PR about bwrap", "url": "https://example.invalid/pull/2", "updatedAt": "2026-10-03T00:00:00Z"}])
    result = s.run("bwrap", "sandbox", "--since", "2026-09-30", gh_json=gh_json)
    calls = s.logged(s.gh_log)
    check("pull requests are listed by title and link, newest first",
          0 < result.stdout.find("Newer PR about bwrap") < result.stdout.find("Older PR about bwrap")
          and "https://example.invalid/pull/2" in result.stdout, result.stdout)
    check("any-word search gives gh each word as its own argument, with OR between, since the date",
          calls and calls[-1][-4:] == ["--", "bwrap", "OR", "sandbox"] and ">=2026-09-30" in calls[-1],
          calls)
    s.run("bwrap", "sandbox", "--all-words")
    calls = s.logged(s.gh_log)
    check("--all-words gives gh each word as its own argument, so GitHub requires every word",
          calls[-1][-3:] == ["--", "bwrap", "sandbox"], calls)
    failed = s.run("bwrap", gh_mode="fail")
    check("a failed GitHub search is named with gh's message and exits 1",
          failed.returncode == 1 and "NOT searched" in failed.stdout
          and "gh auth login" in failed.stdout, failed.stdout)

# A matching agent message followed by another agent message before the user wrote.
with scratch() as base:
    s = Scratch(base)
    write_transcript(s.transcripts, "agent-wrote-again", [
        assistant("Status: the bwrap sandbox work is merged.", "2026-10-03T10:00:00Z"),
        assistant("Shall I delete the stale branch old-thing?", "2026-10-03T10:00:01Z"),
        user("y", "2026-10-03T10:00:02Z"),
    ])
    result = s.run("bwrap")
    _, body = section(result.stdout, f"agent-session transcripts in {s.transcripts}")
    stripped = [line.strip() for line in body]
    check("when the user's answer directly followed a different agent message, that message is shown "
          "as what the user replied to",
          any(line.startswith("Agent:") and "bwrap sandbox work is merged" in line for line in stripped)
          and any(line.startswith("User replied to:") and "delete the stale branch" in line
                  for line in stripped)
          and "User:  y" in stripped, body)

# grep cannot read part of a place.
if not RUNNING_AS_ROOT:
    with scratch() as base:
        s = Scratch(base)
        write_transcript(s.transcripts, "readable", [
            assistant("Shall I build bwrap?", "2026-10-03T10:00:00Z"), user("readable-answer", "2026-10-03T10:00:01Z")])
        locked = write_transcript(s.transcripts, "locked", [
            assistant("Approve the bwrap change?", "2026-10-03T11:00:00Z"), user("approved", "2026-10-03T11:00:01Z")])
        locked.chmod(0)
        try:
            result = s.run("bwrap")
        finally:
            locked.chmod(0o644)
        check("an unreadable transcript beside a matching one: the match is kept, the place is searched "
              "in part, the file is named, and the run exits 1",
              result.returncode == 1 and "readable-answer" in result.stdout
              and f"{s.transcripts} (in part)" in result.stdout and "locked.jsonl" in result.stdout,
              result.stdout)

    with scratch() as base:
        s = Scratch(base)
        (s.walk / "a-2026-10-01-minutes.md").write_text("bwrap approved y\n")
        locked_minutes = s.walk / "b-2026-10-02-minutes.md"
        locked_minutes.write_text("bwrap something\n")
        locked_minutes.chmod(0)
        try:
            result = s.run("bwrap")
        finally:
            locked_minutes.chmod(0o644)
        check("an unreadable walk-minutes file: the lines from readable files are kept, the place is "
              "searched in part, the file is named, and the run exits 1",
              result.returncode == 1 and "bwrap approved y" in result.stdout
              and f"walk-minutes in {s.walk} (in part)" in result.stdout
              and "b-2026-10-02-minutes.md" in result.stdout, result.stdout)
else:
    print("SKIP: unreadable-file cases: running as root, which reads a mode-000 file")

# A transcript grep listed that the program then cannot open.
with scratch() as base:
    s = Scratch(base)
    write_transcript(s.transcripts, "present", [
        assistant("Shall I build bwrap?", "2026-10-03T10:00:00Z"), user("present-answer", "2026-10-03T10:00:01Z")])
    vanished = s.transcripts / "-home-someone-project" / "vanished.jsonl"
    result = s.run("bwrap", extra_environment={"FAKE_GREP_EXTRA_PATH": str(vanished)})
    check("a transcript grep listed but the program cannot open is reported as not read, and exits 1",
          result.returncode == 1 and "present-answer" in result.stdout
          and "could not be read" in result.stdout and "vanished.jsonl" in result.stdout, result.stdout)

# --since is read in UTC.
with scratch() as base:
    s = Scratch(base)
    early = write_transcript(s.transcripts, "early-utc", [
        assistant("Shall I build bwrap?", "2026-10-01T02:00:00Z"), user("early-answer", "2026-10-01T02:00:01Z")])
    early_time = 1790820000  # 2026-10-01T02:00:00Z
    os.utime(early, (early_time, early_time))
    result = s.run("bwrap", "--since", "2026-10-01",
                   extra_environment={"TZ": "America/Los_Angeles"})
    check("--since keeps a transcript modified after midnight UTC on that date, whatever the local zone",
          "early-answer" in result.stdout, result.stdout)

with scratch() as base:
    s = Scratch(base)
    environment = clean_environment()
    environment.update({"GIT_COMMITTER_DATE": "2026-10-01T00:30:00+0000",
                        "GIT_AUTHOR_DATE": "2026-10-01T00:30:00+0000"})
    subprocess.run(["git", "-C", str(s.repository), "commit", "-q", "--allow-empty", "-m",
                    "Early bwrap commit"], check=True, env=environment)
    result = s.run("bwrap", "--since", "2026-10-01")
    check("--since keeps a commit made just after midnight UTC on that date",
          "Early bwrap commit" in result.stdout, result.stdout)

# Walk-minutes are dated by their lines, not by the file name.
with scratch() as base:
    s = Scratch(base)
    (s.walk / "long-walk-2026-10-05-minutes.md").write_text(
        "| 1 | bwrap item | Y (\"y\", 2026-10-07) | accepted |\n"
        "| 2 | bwrap item without a date | Y | accepted |\n"
        "| 3 | bwrap item from before | Y (\"y\", 2026-09-01) | accepted |\n")
    result = s.run("bwrap", "--since", "2026-10-07")
    check("--since keeps a walk-minutes ruling dated on or after it, in a file named for an earlier day",
          "bwrap item | Y" in result.stdout, result.stdout)
    check("--since keeps a walk-minutes line that carries no date",
          "bwrap item without a date" in result.stdout, result.stdout)
    check("a kept \"(no date)\" walk-minutes line comes with the reason and an instruction to date it",
          "nothing in the line dates it" in result.stdout
          and "Before you report a \"(no date)\" line: date it yourself from the walk-minutes file"
          in result.stdout, result.stdout)
    check("--since leaves out a walk-minutes line dated before it",
          "bwrap item from before" not in result.stdout, result.stdout)

# The "(no date)" guidance refers only to lines that are shown.
with scratch() as base:
    s = Scratch(base)
    dated = "".join(f"| {n} | bwrap dated item {n:02d} | Y (\"y\", 2026-10-{(n % 9) + 1:02d}) | accepted |\n"
                    for n in range(25))
    (s.walk / "many-2026-10-01-minutes.md").write_text(dated + "| 99 | bwrap undated item | Y | accepted |\n")
    result = s.run("bwrap")
    check("an undated walk-minutes line beyond the shown ones gets no \"(no date)\" guidance",
          "bwrap undated item" not in result.stdout and "(no date)" not in result.stdout,
          result.stdout)

# Where the real run searches, on each machine.
_program_spec = importlib.util.spec_from_file_location("locate_user_approval_under_test", PROGRAM)
_program = importlib.util.module_from_spec(_program_spec)
_program_spec.loader.exec_module(_program)
_real_gethostname = socket.gethostname
try:
    _program.socket.gethostname = lambda: "ned-box"
    ned_box_plan = _program.production_plan()
    _program.socket.gethostname = lambda: "Neds-MacBook-Pro.local"
    mac_plan = _program.production_plan()
finally:
    _program.socket.gethostname = _real_gethostname
check("on ned-box the walk-minutes are read locally and the Mac's transcript copy is searched",
      ned_box_plan["walk_minutes"]["ssh_target"] is None
      and _program.MAC_TRANSCRIPTS_COPY_ON_NED_BOX in ned_box_plan["transcript_directories"],
      ned_box_plan)
mac_transcript_directories = [entry["directory"] if isinstance(entry, dict) else entry
                              for entry in mac_plan["transcript_directories"]]
mac_remote_entries = [entry for entry in mac_plan["transcript_directories"] if isinstance(entry, dict)]
check("on the Mac the walk-minutes and ned-box's transcripts are read over ssh, never through the mount",
      mac_plan["walk_minutes"]["ssh_target"] == "nedlern@ned-box"
      and _program.MAC_TRANSCRIPTS_COPY_ON_NED_BOX not in mac_transcript_directories
      and not any("/Volumes/" in directory for directory in mac_transcript_directories)
      and len(mac_remote_entries) == 1
      and mac_remote_entries[0]["directory"] == "/home/nedlern/.claude/projects"
      and mac_remote_entries[0]["ssh_target"] == "nedlern@ned-box", mac_plan)

# ned-box's transcripts searched over ssh from the Mac; the ssh stand-in runs the command here.
with scratch() as base:
    s = Scratch(base)
    remote = s.base / "remote-transcripts"
    write_transcript(remote, "remote-session", [
        assistant("Shall I build bwrap on the box?", "2026-10-03T10:00:00Z"),
        notification("done", "2026-10-03T10:00:30Z"),
        assistant("Noted.", "2026-10-03T10:00:31Z"),
        user("remote-yes", "2026-10-03T10:01:00Z")])
    plan = s.plan()
    plan["transcript_directories"].append({"directory": str(remote), "ssh_target": "nedlern@fake-box",
                                           "label": "ned-box's agent-session transcripts, over ssh"})
    result = s.run("bwrap", plan=plan)
    calls = s.logged(s.ssh_log)
    check("on the Mac, ned-box's transcripts are searched over ssh and their pairs are shown",
          result.returncode == 0 and "remote-yes" in result.stdout
          and "ned-box's agent-session transcripts, over ssh" in result.stdout
          and any(call and "nedlern@fake-box" in call and "ConnectTimeout=10" in call for call in calls),
          (result.stdout, result.stderr, calls))
    unreachable = s.run("bwrap", plan=plan, ssh_mode="unreachable")
    check("an unreachable ned-box leaves its transcripts named as not searched, with the remedy, "
          "and exits 1",
          unreachable.returncode == 1
          and "ned-box's agent-session transcripts, over ssh: ssh nedlern@fake-box failed" in unreachable.stdout
          and "ssh nedlern@ned-box true" in unreachable.stdout, unreachable.stdout)

# An ssh search of ned-box's transcripts that does not finish in time.
with scratch() as base:
    s = Scratch(base)
    _saved_path, _saved_timeout = os.environ.get("PATH", ""), _program.COMMAND_TIMEOUT_SECONDS
    _saved_ssh_mode, _saved_ssh_log = os.environ.get("FAKE_SSH_MODE"), os.environ.get("FAKE_SSH_ARGV_LOG")
    try:
        os.environ["PATH"] = f"{s.bin}{os.pathsep}{_saved_path}"
        os.environ["FAKE_SSH_MODE"] = "hang"
        os.environ["FAKE_SSH_ARGV_LOG"] = str(s.ssh_log)
        _program.COMMAND_TIMEOUT_SECONDS = 1
        timed_out = _program.search_transcripts_over_ssh(
            "nedlern@fake-box", "/remote/projects", "ned-box's agent-session transcripts, over ssh",
            ["bwrap"], False, None, False)
    finally:
        os.environ["PATH"] = _saved_path
        _program.COMMAND_TIMEOUT_SECONDS = _saved_timeout
        for _name, _value in (("FAKE_SSH_MODE", _saved_ssh_mode), ("FAKE_SSH_ARGV_LOG", _saved_ssh_log)):
            if _value is None:
                os.environ.pop(_name, None)
            else:
                os.environ[_name] = _value
    check("an ssh search that does not finish in time is reported unreachable, with the time limit",
          timed_out.get("unreachable") is True and timed_out["items"] == []
          and "did not finish within 1 s" in timed_out.get("failure", ""), timed_out)
    report, code = _program.render_report([timed_out], ["bwrap"], False, None)
    check("a timed-out ssh search makes the run exit 1 and gives the remedy",
          code == 1 and "ssh nedlern@ned-box true" in report, report)

# Bad invocations and missing places.
with scratch() as base:
    s = Scratch(base)
    too_many = s.run("one", "two", "three", "four")
    check("more than three words is refused with exit 2", too_many.returncode == 2, too_many.stderr)
    bad_date = s.run("bwrap", "--since", "October")
    check("a --since that is not a date is refused with exit 2", bad_date.returncode == 2, bad_date.stderr)
    plan = s.plan()
    plan["transcript_directories"].append(str(s.base / "missing-directory"))
    missing = s.run("bwrap", plan=plan)
    check("a transcript directory that does not exist is reported and exits 1",
          missing.returncode == 1 and "missing-directory: the directory does not exist" in missing.stdout,
          missing.stdout)

print()
if failures:
    print(f"{len(failures)} case(s) FAILED:")
    for name in failures:
        print(f"  - {name}")
    sys.exit(1)
print("all cases passed")
