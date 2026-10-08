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
    _, body = section(result.stdout, f"agent-session transcripts in {s.transcripts}")
    stripped = [line.strip() for line in body]
    second = next((index for index, line in enumerate(stripped)
                   if line.startswith("Agent:") and "Second" in line), None)
    first = next((index for index, line in enumerate(stripped)
                  if line.startswith("Agent:") and "First" in line), None)
    check("of several matching agent messages before one answer, the answer is paired with the last",
          second is not None and stripped[second + 1] == "User:  yes go"
          and first is not None and "agent wrote again" in stripped[first + 1], body)

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
    check("a matching question with no message after it is shown as unanswered",
          "(no user message followed)" in result.stdout, result.stdout)

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
    check("matches print how to read the pairs", "Read each pair" in result.stdout, result.stdout)

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
    check("nothing found tells the agent to try another name before reporting",
          "another name for the subject" in result.stdout, result.stdout)
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
    check("a user's answer to a later agent message is not paired with an earlier matching one",
          not any(line.strip() == "User:  y" for line in body)
          and any("the agent wrote again before the user answered" in line for line in body), body)

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
    check("--since leaves out a walk-minutes line dated before it",
          "bwrap item from before" not in result.stdout, result.stdout)

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
check("on the Mac the walk-minutes are read over ssh, and ned-box's transcripts through the mount",
      mac_plan["walk_minutes"]["ssh_target"] == "nedlern@ned-box"
      and _program.MAC_TRANSCRIPTS_COPY_ON_NED_BOX not in mac_transcript_directories
      and "/Volumes/nedhome/.claude/projects" in mac_transcript_directories, mac_plan)

with scratch() as base:
    s = Scratch(base)
    plan = s.plan()
    plan["transcript_directories"].append({"directory": str(s.base / "not-mounted"),
                                           "label": "ned-box's agent-session transcripts, through the mount",
                                           "remedy": "mount ned-box's home on the Mac"})
    result = s.run("bwrap", plan=plan)
    check("on the Mac, ned-box's transcripts when the mount is missing are named as not searched, "
          "with the remedy, and the run exits 1",
          result.returncode == 1 and "ned-box's agent-session transcripts, through the mount" in result.stdout
          and "mount ned-box's home on the Mac" in result.stdout, result.stdout)

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
