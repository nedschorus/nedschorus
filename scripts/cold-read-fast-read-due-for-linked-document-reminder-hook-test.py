#!/usr/bin/env python3
"""Cases for the Stop hook that tells an agent to fast-read the documents it
linked for the user that their checkout changed from main and have had no
cold-read-fast-read since their last change.

Each hook case runs the hook as a subprocess, its real stdin-to-stdout path,
in a scratch checkout this suite made, whose origin/main is an empty first
commit unless the case commits to it, with the log-store cold-read-records directory pointed by
NEDSCHORUS_LOG_STORE_COLD_READ_RECORDS_DIRECTORY into a scratch directory, so no
case reads the live log-store. The exit code is asserted on every case: the
hook exits 0 unless it hit a fault, which it names on stderr with exit 1.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Before anything runs git: a GIT_DIR or similar variable inherited from the
# caller would otherwise send this suite's `git init` into another repository.
_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().with_name(
        "git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

HOOK_SCRIPT = Path(__file__).with_name("cold-read-fast-read-due-for-linked-document-reminder-hook.py")
STORE_VARIABLE = "NEDSCHORUS_LOG_STORE_COLD_READ_RECORDS_DIRECTORY"
SUITE_ROOT = Path(tempfile.mkdtemp(prefix="cold-read-fast-read-due-for-linked-document-test-"))
failures = []


def git(checkout, *arguments):
    return subprocess.run(
        ["git", "-C", str(checkout), "-c", "user.name=suite", "-c", "user.email=suite@example.com",
         *arguments], check=True, capture_output=True, text=True).stdout


def make_checkout_with_main(checkout):
    """A checkout whose origin/main is an empty first commit, so every file in it is new."""
    subprocess.run(["git", "init", "-q", str(checkout)], check=True)
    git(checkout, "commit", "-q", "--allow-empty", "-m", "first")
    git(checkout, "update-ref", "refs/remotes/origin/main", "HEAD")


def commit_to_main(checkout, relative):
    """Commit the file and move origin/main onto that commit, as a merge to main would."""
    git(checkout, "add", "-f", relative)
    git(checkout, "commit", "-q", "-m", f"add {relative}")
    git(checkout, "update-ref", "refs/remotes/origin/main", "HEAD")


def object_file(checkout, revision):
    name = git(checkout, "rev-parse", revision).strip()
    return Path(checkout) / ".git" / "objects" / name[:2] / name[2:]


def expect_unchecked(case_name, completed, document, reason_part, due_paths=None,
                     already_read=False):
    """The document is listed as not checked, with git's reason, and the others are still judged.

    A document with a fast read on record since its last change, or one this agent-session
    fast-read, is marked as read, and no fast read is asked for it; any other is asked a fast read.
    """
    check(f"{case_name}: exit 0", completed.returncode == 0,
          f"exit {completed.returncode}, stderr {completed.stderr!r}")
    context = (json.loads(completed.stdout)["hookSpecificOutput"]["additionalContext"]
               if completed.returncode == 0 and completed.stdout.strip() else "")
    listed = [line for line in context.splitlines() if line.startswith("- ")]
    check(f"{case_name}: listed as not checked, with git's reason",
          "due check failed" in context and len(listed) == 1
          and listed[0].startswith(f"- {document.resolve()}: ") and reason_part in listed[0],
          f"context {context!r}")
    check(f"{case_name}: one stderr line naming the document and git's reason",
          len(completed.stderr.strip().splitlines()) == 1
          and "could not tell whether" in completed.stderr and str(document.resolve()) in completed.stderr
          and reason_part in completed.stderr,
          f"stderr {completed.stderr!r}")
    fast_read_asked = "Run on each document" in context and "not marked as read" in context
    if already_read:
        check(f"{case_name}: marked as read, and no fast read asked for it",
              listed and "(marked as read" in listed[0] and "not marked as read" not in context,
              f"context {context!r}")
        check(f"{case_name}: the fast read's command is given only when another document is due",
              ("Run on each document" in context) == bool(due_paths), f"context {context!r}")
    else:
        check(f"{case_name}: not marked as read, and a fast read asked for it",
              listed and "(marked as read" not in listed[0] and fast_read_asked,
              f"context {context!r}")
        instruction = [line for line in context.splitlines() if "not marked as read" in line]
        check(f"{case_name}: the list's own line tells the agent to run the fast read on a document it changed, with the command",
              len(instruction) == 1 and instruction[0].startswith("If you changed a document in this list that is not marked as read")
              and "--target <document path>" in instruction[0],
              f"context {context!r}")
    expected = [str(path.resolve()) for path in due_paths or []]
    check(f"{case_name}: the other documents are still judged",
          reported_paths(completed) == expected,
          f"reported {reported_paths(completed)!r}, expected {expected!r}")
    if due_paths:
        check(f"{case_name}: a fast read is asked for the other documents that are due",
              "Run on each document" in context, f"context {context!r}")


def git_that_on(subcommand, action):
    """A PATH entry whose git runs the shell action when given the subcommand, else runs git."""
    directory = SUITE_ROOT / f"git-{action.split()[0]}-on-{subcommand}"
    directory.mkdir(exist_ok=True)
    fake = directory / "git"
    fake.write_text(
        "#!/bin/sh\n"
        f'for argument in "$@"; do [ "$argument" = "{subcommand}" ] && {action}; done\n'
        f'exec "{shutil.which("git")}" "$@"\n')
    fake.chmod(0o755)
    return {"PATH": f"{directory}{os.pathsep}{os.environ['PATH']}"}


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


class Case:
    """One case's own checkout, cold-read-records directory and transcript."""

    counter = 0

    def __init__(self):
        Case.counter += 1
        self.root = SUITE_ROOT / f"case-{Case.counter}"
        self.checkout = self.root / "checkout"
        (self.checkout / "docs").mkdir(parents=True)
        make_checkout_with_main(self.checkout)
        # The log-store is the records directory's parent, as on ned-box.
        self.log_store = self.root / "log-store"
        self.store = self.log_store / "cold-read-records"
        self.store.mkdir(parents=True)
        self.transcript = self.root / "transcript.jsonl"

    def document(self, relative, text="# A document\n", modified=1_000_000):
        path = self.checkout / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        os.utime(path, (modified, modified))
        return path

    def record(self, name, modified, frozen_relative=None, frozen_text=None, local=False,
               report_name="fast-read.md"):
        directory = (self.checkout / "cold-read-records" if local else self.store) / name
        directory.mkdir(parents=True)
        if report_name is not None:
            report = directory / report_name
            report.write_text("<!-- provenance: cell=fast-clarify -->\nfindings\n")
            os.utime(report, (modified, modified))
        if frozen_relative is not None:
            frozen = directory / "target" / frozen_relative
            frozen.parent.mkdir(parents=True)
            frozen.write_text(frozen_text)
            os.utime(frozen, (modified, modified))
        return directory

    def run(self, reply, payload_extra=None, stdin_text=None, environment_extra=None):
        records = [
            {"type": "user", "message": {"role": "user", "content": "please write it"}},
            {"type": "assistant", "message": {"id": "msg_1", "role": "assistant",
                                              "content": [{"type": "text", "text": reply}]}},
        ]
        self.transcript.write_text("".join(json.dumps(record) + "\n" for record in records))
        return self.run_on_written_transcript(payload_extra, stdin_text, environment_extra)

    def run_on_written_transcript(self, payload_extra=None, stdin_text=None, environment_extra=None):
        payload = {"hook_event_name": "Stop", "session_id": "s1",
                   "transcript_path": str(self.transcript), "cwd": str(self.checkout)}
        payload.update(payload_extra or {})
        environment = {key: value for key, value in os.environ.items()
                       if key not in ("NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER",
                                      "CLAUDE_CODE_SESSION_ATTENDED")}
        environment[STORE_VARIABLE] = str(self.store)
        environment.update(environment_extra or {})
        completed = subprocess.run(
            [sys.executable, str(HOOK_SCRIPT)],
            input=json.dumps(payload) if stdin_text is None else stdin_text,
            capture_output=True, text=True, env=environment, timeout=60)
        return completed


def reported_paths(completed):
    if not completed.stdout.strip():
        return None
    context = json.loads(completed.stdout)["hookSpecificOutput"]["additionalContext"]
    return [line.strip() for line in context.splitlines() if line.startswith("  ")]


def expect(case_name, completed, expected_paths):
    check(f"{case_name}: exit 0", completed.returncode == 0,
          f"exit {completed.returncode}, stderr {completed.stderr!r}")
    paths = reported_paths(completed)
    expected = None if expected_paths is None else [str(path.resolve()) for path in expected_paths]
    check(case_name, paths == expected, f"reported {paths!r}, expected {expected!r}")


def main():
    case = Case()
    document = case.document("docs/plan-of-record.md")
    expect("a linked document with no record is reported",
           case.run("I wrote docs/plan-of-record.md for you."), [document])

    case = Case()
    document = case.document("docs/plan-of-record.md", modified=1_000_000)
    case.record("plan-of-record-2026-10-08", 2_000_000, "docs/plan-of-record.md", "older text\n")
    expect("a document with a newer record is silent",
           case.run("See [the plan](docs/plan-of-record.md)."), None)

    case = Case()
    document = case.document("docs/plan-of-record.md", modified=3_000_000)
    case.record("plan-of-record-2026-10-08", 2_000_000, "docs/plan-of-record.md", "older text\n")
    case.record("plan-of-record-2026-10-07", 1_000_000, "docs/plan-of-record.md", "oldest\n")
    expect("a document modified after its newest record is reported",
           case.run("Updated docs/plan-of-record.md."), [document])

    case = Case()
    document = case.document("docs/plan-of-record.md", text="same\n", modified=3_000_000)
    case.record("plan-of-record-2026-10-08", 2_000_000, "docs/plan-of-record.md", "same\n")
    expect("a record whose frozen copy matches the document is silent despite file times",
           case.run("Updated docs/plan-of-record.md."), None)

    case = Case()
    document = case.document("docs/plan-of-record.md", text="same\n", modified=3_000_000)
    absolute_form = Path(*document.resolve().parts[1:])
    case.record("plan-of-record-2026-10-08", 2_000_000, absolute_form, "same\n")
    expect("a frozen copy at the absolute path, as a read from another checkout writes, counts",
           case.run("Updated docs/plan-of-record.md."), None)

    case = Case()
    document = case.document("docs/plan-of-record.md", modified=1_000_000)
    case.record("2026-09-14-plan-of-record-2", 2_000_000)
    expect("an older-form record without target/ is matched by name",
           case.run("Updated docs/plan-of-record.md."), None)

    case = Case()
    document = case.document("docs/plan-of-record.md", modified=1_000_000)
    case.record("plan-of-record-2026-10-08", 2_000_000, "docs/other/plan-of-record.md", "x\n")
    expect("a record of another document with the same stem does not count",
           case.run("Updated docs/plan-of-record.md."), [document])

    case = Case()
    document = case.document("docs/plan-of-record.md", modified=1_000_000)
    case.record("plan-of-record-extra-2026-10-08", 2_000_000)
    expect("a record of a document whose stem only starts the same does not count",
           case.run("Updated docs/plan-of-record.md."), [document])

    case = Case()
    document = case.document(".claude/skills/handoff/SKILL.md", modified=1_000_000)
    case.record("SKILL-handoff-2026-10-08", 2_000_000, ".claude/skills/handoff/SKILL.md", "y\n",
                local=True)
    expect("a skill's record in the checkout's cold-read-records is found",
           case.run("Read .claude/skills/handoff/SKILL.md."), None)

    case = Case()
    draft = case.document("docs/walk/naming-rules-draft.md", modified=2_000_000)
    expect("a walk-document without a suggestions file is reported",
           case.run("The walk-document is docs/walk/naming-rules-draft.md."), [draft])
    case.document("docs/walk/naming-rules-suggestions.md", modified=3_000_000)
    expect("a walk-document with a newer suggestions file is silent, and the suggestions file is skipped",
           case.run("See docs/walk/naming-rules-draft.md and docs/walk/naming-rules-suggestions.md."),
           None)

    case = Case()
    document = case.document("docs/plan-of-record.md")
    expect("an absolute file:// link is found",
           case.run(f"Open [plan](file://{document})."), [document])
    expect("a link to a file that does not exist is skipped",
           case.run("See docs/never-written.md."), None)
    expect("no links is silent", case.run("All done; nothing to link."), None)
    expect("stop_hook_active is silent",
           case.run("I wrote docs/plan-of-record.md.", {"stop_hook_active": True}), None)
    expect("a headless child is silent",
           case.run("I wrote docs/plan-of-record.md.",
                    environment_extra={"CLAUDE_CODE_SESSION_ATTENDED": "0"}), None)
    expect("a missing log-store cold-read-records directory is silent",
           case.run("I wrote docs/plan-of-record.md.",
                    environment_extra={STORE_VARIABLE: str(case.root / "absent")}), None)
    completed = case.run("", stdin_text="not json {")
    check("input that is not JSON is a fault: exit 1, one stderr line, no output",
          completed.returncode == 1 and completed.stdout == ""
          and "made no check" in completed.stderr
          and len(completed.stderr.strip().splitlines()) == 1,
          f"exit {completed.returncode}, stdout {completed.stdout!r}, stderr {completed.stderr!r}")
    expect("a transcript that does not exist is silent",
           case.run("", {"transcript_path": str(case.root / "absent.jsonl")}), None)

    case = Case()
    draft = case.document("docs/walk/naming-rules-draft.md", text="walk\n", modified=3_000_000)
    case.record("naming-rules-draft-2026-10-08", 2_000_000,
                Path(*draft.resolve().parts[1:]), "walk\n")
    expect("a walk-document read from another checkout, into a cold-read-record, is silent",
           case.run("The walk-document is docs/walk/naming-rules-draft.md."), None)

    case = Case()
    document = case.document("docs/plan-of-record.md", text="same\n", modified=3_000_000)
    case.record("plan-of-record-2026-10-08", 2_000_000, "docs/plan-of-record.md", "same\n")
    other = SUITE_ROOT / "other-checkout"
    subprocess.run(["git", "init", "-q", str(other)], check=True)
    expect("a leaked GIT_DIR and GIT_WORK_TREE do not hide the document's own checkout",
           case.run("Updated docs/plan-of-record.md.",
                    environment_extra={"GIT_DIR": str(other / ".git"),
                                       "GIT_WORK_TREE": str(other)}), None)

    case = Case()
    document = case.document("docs/plan-of-record.md", text="same\n", modified=3_000_000)
    case.record("plan-of-record-2026-10-08", 2_000_000, "docs/plan-of-record.md", "same\n",
                report_name=None)
    expect("a read that failed after freezing its target, with no report, does not count",
           case.run("Updated docs/plan-of-record.md."), [document])

    case = Case()
    document = case.document("docs/composed-prompt.md", modified=1_000_000)
    case.record("2026-08-24-composed-prompt-restate", 2_000_000)
    expect("an older-form record of a longer name does not count for a shorter one",
           case.run("See docs/composed-prompt.md."), [document])

    case = Case()
    document = case.document("docs/plan-of-record.md", modified=1_000_000)
    case.record("2026-08-25-plan-of-record", 2_000_000,
                report_name="2026-08-25-plan-of-record--claude-hunt-good.md")
    expect("an older full run's prefixed report counts as a finished report",
           case.run("See docs/plan-of-record.md."), None)

    case = Case()
    log_store_file = case.log_store / "analysis" / "survey.md"
    log_store_file.parent.mkdir(parents=True)
    log_store_file.write_text("x\n")
    expect("a file in the log-store is skipped",
           case.run(f"The survey is at file://{log_store_file}."), None)

    case = Case()
    case.document("cold-read-records/plan-2026-10-08/fast-read.md")
    expect("a file in a cold-read-records directory is skipped",
           case.run("The report is at file://"
                    f"{case.checkout / 'cold-read-records/plan-2026-10-08/fast-read.md'}."),
           None)

    case = Case()
    document = case.document("docs/plan-of-record.md")
    expect("a document linked twice is reported once",
           case.run(f"See docs/plan-of-record.md, or [the plan](file://{document})."),
           [document])

    case = Case()
    draft = case.document("docs/walk/claude-notes-draft.md", text="walk\n", modified=3_000_000)
    record = case.record("claude-notes-draft-2026-10-08", 2_000_000,
                         Path(*draft.resolve().parts[1:]), "walk\n",
                         report_name="claude-notes-draft-with-sentence-ids.md")
    expect("a failed cross-checkout walk read that left only its marked input copy does not count",
           case.run("The walk-document is docs/walk/claude-notes-draft.md."), [draft])

    case = Case()
    document = case.document("docs/plan-of-record.md", modified=1_000_000)
    case.record("plan-of-record-2026-09-20", 2_000_000, report_name="plan-of-record-fast-read.md")
    expect("an older record holding only <name>-fast-read.md counts as a finished report",
           case.run("See docs/plan-of-record.md."), None)

    case = Case()
    document = case.document("docs/plan-of-record.md", modified=1_000_000)
    case.record("plan-of-record-2026-09-29", 2_000_000, report_name="codex-hunt-deep.md")
    expect("a record holding only codex- reports counts as a finished report",
           case.run("See docs/plan-of-record.md."), None)

    case = Case()
    document = case.document("docs/plan-of-record.md", modified=1_000_000)
    session_checkout = case.root / "session-checkout"
    make_checkout_with_main(session_checkout)
    session_record = session_checkout / "cold-read-records" / "plan-of-record-2026-10-08"
    session_record.mkdir(parents=True)
    (session_record / "fast-read.md").write_text("findings\n")
    os.utime(session_record / "fast-read.md", (2_000_000, 2_000_000))
    expect("a record in the session checkout's cold-read-records counts for a document elsewhere",
           case.run(f"Updated file://{document}.", {"cwd": str(session_checkout)}), None)

    case = Case()
    document = case.document("docs/plan-of-record.md", modified=1_000_000)
    unreadable = case.record("plan-of-record-2026-10-08", 2_000_000)
    unreadable.chmod(0)
    try:
        completed = case.run("See docs/plan-of-record.md.")
    finally:
        unreadable.chmod(0o755)
    check("an unreadable record directory is a fault naming it: exit 1, one stderr line, no output",
          completed.returncode == 1 and completed.stdout == ""
          and "made no check" in completed.stderr
          and "PermissionError" in completed.stderr and str(unreadable) in completed.stderr
          and len(completed.stderr.strip().splitlines()) == 1,
          f"exit {completed.returncode}, stdout {completed.stdout!r}, stderr {completed.stderr!r}")

    def name_agent_session(report, session_id, target):
        """What cold-read-fast-read.py writes beside a finished report."""
        written = report.parent / (report.name + ".agent-session.json")
        written.write_text(
            json.dumps({"agent_session_id": session_id, "target": str(target.resolve())}))
        os.utime(written, (4_000_000, 4_000_000))

    case = Case()
    document = case.document("docs/plan-of-record.md", modified=5_000_000)
    record = case.record("plan-of-record-2026-10-14", 4_000_000, "docs/plan-of-record.md",
                         "before the fix\n")
    expect("a record with no agent-session file, then a change, is raised",
           case.run("Applied the findings to docs/plan-of-record.md."), [document])
    name_agent_session(record / "fast-read.md", "s1", document)
    expect("a document this agent-session fast-read, then changed, is not raised again",
           case.run("Applied the findings to docs/plan-of-record.md."), None)
    expect("another agent-session's fast read, then this agent-session's change, is raised",
           case.run("Applied the findings to docs/plan-of-record.md.", {"session_id": "s2"}),
           [document])
    expect("a payload with no session_id judges by file times",
           case.run("Applied the findings to docs/plan-of-record.md.", {"session_id": None}),
           [document])
    name_agent_session(record / "fast-read.md", "s1", case.checkout / "docs" / "other.md")
    expect("this agent-session's fast read of another document with the same stem does not count",
           case.run("Applied the findings to docs/plan-of-record.md."), [document])
    (record / "fast-read.md.agent-session.json").write_text("not json\n")
    completed = case.run("Applied the findings to docs/plan-of-record.md.")
    check("an agent-session file that is not JSON is a fault naming the file: exit 1, one stderr line, no output",
          completed.returncode == 1 and completed.stdout == ""
          and "made no check" in completed.stderr
          and str(record / "fast-read.md.agent-session.json") in completed.stderr
          and len(completed.stderr.strip().splitlines()) == 1,
          f"exit {completed.returncode}, stdout {completed.stdout!r}, stderr {completed.stderr!r}")
    for label, content in (("empty", b""), ("not UTF-8", b"\xff\xfe{")):
        (record / "fast-read.md.agent-session.json").write_bytes(content)
        completed = case.run("Applied the findings to docs/plan-of-record.md.")
        check(f"an agent-session file that is {label} is a fault naming the file: exit 1",
              completed.returncode == 1
              and str(record / "fast-read.md.agent-session.json") in completed.stderr,
              f"exit {completed.returncode}, stderr {completed.stderr!r}")
    (record / "fast-read.md.agent-session.json").write_text('{"agent_session_id": "s1"}\n')
    completed = case.run("Applied the findings to docs/plan-of-record.md.")
    check("an agent-session file without a target is a fault: exit 1",
          completed.returncode == 1 and "not an agent-session record" in completed.stderr,
          f"exit {completed.returncode}, stderr {completed.stderr!r}")

    case = Case()
    draft = case.document("docs/walk/naming-rules-draft.md", modified=5_000_000)
    suggestions = case.document("docs/walk/naming-rules-suggestions.md", modified=4_000_000)
    expect("a walk-document changed after another agent-session's read is raised",
           case.run("The walk-document is docs/walk/naming-rules-draft.md."), [draft])
    name_agent_session(suggestions, "s1", draft)
    expect("a walk-document this agent-session fast-read, then changed, is not raised again",
           case.run("The walk-document is docs/walk/naming-rules-draft.md."), None)

    case = Case()
    draft = case.document("docs/walk/naming-rules-draft.md", modified=4_000_000)
    suggestions = case.document("docs/walk/naming-rules-suggestions.md", modified=5_000_000)
    malformed = suggestions.parent / (suggestions.name + ".agent-session.json")
    malformed.write_text("not json\n")
    completed = case.run("The walk-document is docs/walk/naming-rules-draft.md.")
    check("a malformed agent-session file beside suggestions newer than the walk-document is a fault naming the file",
          completed.returncode == 1 and completed.stdout == ""
          and str(malformed) in completed.stderr,
          f"exit {completed.returncode}, stdout {completed.stdout!r}, stderr {completed.stderr!r}")

    case = Case()
    case.document("docs/plan-of-record.md", modified=5_000_000)
    case.run("Updated docs/plan-of-record.md.")
    case.transcript.chmod(0)
    try:
        completed = case.run_on_written_transcript()
    finally:
        case.transcript.chmod(0o644)
    context = (json.loads(completed.stdout)["hookSpecificOutput"]["additionalContext"]
               if completed.returncode == 0 and completed.stdout.strip() else "")
    check("a transcript that cannot be read is reported to the agent and on stderr, exit 0",
          completed.returncode == 0
          and "could not read this agent-session's transcript" in context
          and "could not read this agent-session's transcript" in completed.stderr,
          f"exit {completed.returncode}, stdout {completed.stdout!r}, stderr {completed.stderr!r}")

    case = Case()
    document = case.document("docs/plan-of-record.md", text="on main\n")
    commit_to_main(case.checkout, "docs/plan-of-record.md")
    expect("a linked document the same as on origin/main, with no record, is silent",
           case.run("See docs/plan-of-record.md."), None)
    case.document("docs/plan-of-record.md", text="on main, edited\n")
    expect("a document on main with an uncommitted edit is reported",
           case.run("See docs/plan-of-record.md."), [document])
    git(case.checkout, "commit", "-q", "-am", "edit on the topic branch")
    expect("a document changed by a commit on the topic branch is reported",
           case.run("See docs/plan-of-record.md."), [document])
    case.document("docs/plan-of-record.md", text="on main\n", modified=9_000_000)
    expect("a document whose topic-branch commit is undone in the working tree is silent",
           case.run("See docs/plan-of-record.md."), None)

    case = Case()
    case.document("docs/on-main.md", text="on main\n")
    commit_to_main(case.checkout, "docs/on-main.md")
    document = case.document("docs/plan-of-record.md")
    expect("a document the same as on main does not stop the check of the next one linked",
           case.run("See docs/on-main.md and docs/plan-of-record.md."), [document])

    case = Case()
    (case.checkout / ".gitignore").write_text("docs/walk/\n")
    commit_to_main(case.checkout, ".gitignore")
    draft = case.document("docs/walk/naming-rules-draft.md")
    check("the walk-document is ignored by git",
          git(case.checkout, "status", "--porcelain", "--ignored", "docs/walk/").startswith("!! "),
          git(case.checkout, "status", "--porcelain", "--ignored"))
    expect("a git-ignored walk-document, not on main, is reported",
           case.run("The walk-document is docs/walk/naming-rules-draft.md."), [draft])

    case = Case()
    other = case.root / "other-agent-checkout"
    make_checkout_with_main(other)
    elsewhere = other / "docs" / "design.md"
    elsewhere.parent.mkdir(parents=True)
    elsewhere.write_text("on main\n")
    commit_to_main(other, "docs/design.md")
    expect("a document in another checkout, the same as that checkout's main, is silent",
           case.run(f"See file://{elsewhere}."), None)
    elsewhere.write_text("edited there\n")
    expect("a document in another checkout that differs from that checkout's main is reported",
           case.run(f"See file://{elsewhere}."), [elsewhere])

    case = Case()
    git(case.checkout, "update-ref", "-d", "refs/remotes/origin/main")
    no_main = case.document("docs/plan-of-record.md")
    expect_unchecked("a checkout without origin/main lists its document as not checked",
                     case.run("See docs/plan-of-record.md."), no_main, "git merge-base")
    other = case.root / "other-checkout-with-main"
    make_checkout_with_main(other)
    changed_elsewhere = other / "docs" / "design.md"
    changed_elsewhere.parent.mkdir(parents=True)
    changed_elsewhere.write_text("new there\n")
    expect_unchecked("a document that cannot be checked does not stop the check of another",
                     case.run(f"See file://{no_main} and file://{changed_elsewhere}."),
                     no_main, "git merge-base", [changed_elsewhere])

    case = Case()
    git(case.checkout, "update-ref", "-d", "refs/remotes/origin/main")
    read = case.document("docs/plan-of-record.md", modified=1_000_000)
    case.record("plan-of-record-2026-10-08", 2_000_000, "docs/plan-of-record.md", "older text\n")
    expect_unchecked("a document that cannot be checked, fast-read since its last change, "
                     "still shows git's failure",
                     case.run("See docs/plan-of-record.md."), read, "git merge-base",
                     already_read=True)
    other = case.root / "other-checkout-with-main"
    make_checkout_with_main(other)
    changed_elsewhere = other / "docs" / "design.md"
    changed_elsewhere.parent.mkdir(parents=True)
    changed_elsewhere.write_text("new there\n")
    expect_unchecked("a document that cannot be checked and is not due leaves the other "
                     "documents' fast read asked for",
                     case.run(f"See file://{read} and file://{changed_elsewhere}."),
                     read, "git merge-base", [changed_elsewhere], already_read=True)

    case = Case()
    document = case.document("docs/plan-of-record.md", text="when the branch was cut\n")
    commit_to_main(case.checkout, "docs/plan-of-record.md")
    git(case.checkout, "checkout", "-q", "-b", "main-moves-on")
    case.document("docs/plan-of-record.md", text="changed on main since\n")
    commit_to_main(case.checkout, "docs/plan-of-record.md")
    git(case.checkout, "checkout", "-q", "-")
    expect("a document only main changed since the checkout's branch was cut is silent",
           case.run("See docs/plan-of-record.md."), None)
    case.document("docs/plan-of-record.md", text="changed on the topic branch too\n")
    git(case.checkout, "commit", "-q", "-am", "edit on the topic branch")
    expect("a document a branch behind main also changed is reported",
           case.run("See docs/plan-of-record.md."), [document])

    case = Case()
    case.document("docs/plan-of-record.md", text="on main\n")
    commit_to_main(case.checkout, "docs/plan-of-record.md")
    object_file(case.checkout, "refs/remotes/origin/main^{tree}").unlink()
    expect_unchecked("a main whose tree git cannot read lists the document as not checked",
                     case.run("See docs/plan-of-record.md."),
                     case.checkout / "docs/plan-of-record.md", "git ls-tree")

    case = Case()
    case.document("docs/plan-of-record.md", text="on main\n")
    commit_to_main(case.checkout, "docs/plan-of-record.md")
    object_file(case.checkout, "refs/remotes/origin/main:docs/plan-of-record.md").unlink()
    expect_unchecked("a main whose copy of the document git cannot read lists it as not checked",
                     case.run("See docs/plan-of-record.md."),
                     case.checkout / "docs/plan-of-record.md", "git cat-file")

    # A git killed by a signal exits with a negative code, which is a failure too.
    for subcommand in ("merge-base", "ls-tree", "cat-file"):
        case = Case()
        on_main = case.document("docs/plan-of-record.md", text="on main\n")
        commit_to_main(case.checkout, "docs/plan-of-record.md")
        expect_unchecked(f"a git {subcommand} killed by a signal lists the document as not checked",
                         case.run("See docs/plan-of-record.md.",
                                  environment_extra=git_that_on(subcommand, "kill -9 $$")),
                         on_main, f"git {subcommand}")

    case = Case()
    on_main = case.document("docs/plan-of-record.md", text="on main\n")
    commit_to_main(case.checkout, "docs/plan-of-record.md")
    expect_unchecked("a git merge-base that outlasts its time limit lists the document as not checked",
                     case.run("See docs/plan-of-record.md.",
                              environment_extra=git_that_on("merge-base", "exec sleep 30")),
                     on_main, "TimeoutExpired")

    case = Case()
    first = case.document("docs/first.md")
    second = case.document("docs/second.md")
    calls = case.root / "merge-base-calls"
    completed = case.run("See docs/first.md and docs/second.md.",
                         environment_extra=git_that_on(
                             "merge-base", f"{{ echo called >> {calls}; exec sleep 30; }}"))
    check("a git merge-base that outlasts its time limit runs once per checkout: exit 0",
          completed.returncode == 0, f"exit {completed.returncode}, stderr {completed.stderr!r}")
    check("a git merge-base that outlasts its time limit runs once per checkout",
          calls.is_file() and calls.read_text().count("called") == 1,
          f"calls {calls.read_text() if calls.is_file() else None!r}")
    context = (json.loads(completed.stdout)["hookSpecificOutput"]["additionalContext"]
               if completed.returncode == 0 and completed.stdout.strip() else "")
    listed = [line for line in context.splitlines() if line.startswith("- ")]
    check("a timed-out merge-base lists each document of its checkout as not checked",
          [line.split(": ")[0] for line in listed]
          == [f"- {first.resolve()}", f"- {second.resolve()}"]
          and all("TimeoutExpired" in line for line in listed),
          f"context {context!r}")

    loose = SUITE_ROOT / "in-no-checkout" / "notes.md"
    loose.parent.mkdir(parents=True)
    loose.write_text("x\n")
    case = Case()
    expect("a document in no git checkout is judged by its records alone",
           case.run(f"See file://{loose}."), [loose])

    # The Mac mount maps to ned-box's /home/nedlern; point that prefix at a scratch directory.
    specification = importlib.util.spec_from_file_location("hook_under_test", HOOK_SCRIPT)
    hook = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(hook)
    fake_home = SUITE_ROOT / "fake-ned-box-home"
    mapped = fake_home / "Projects" / "nedschorus" / "docs" / "two words.md"
    mapped.parent.mkdir(parents=True)
    mapped.write_text("x\n")
    hook.NED_BOX_HOME = str(fake_home) + "/"
    found = hook.find_markdown_file_paths_linked_or_named_in_agent_reply(
        "[doc](file:///Volumes/nedhome/Projects/nedschorus/docs/two%20words.md).", None)
    check("a file:///Volumes/nedhome link maps to the file under ned-box's home",
          found == [mapped.resolve()], f"found {found!r}")

    # Only the mount itself maps: /Volumes/nedhome-other is another directory.
    lookalike = fake_home / "-other" / "a.md"
    lookalike.parent.mkdir(parents=True)
    lookalike.write_text("x\n")
    found = hook.find_markdown_file_paths_linked_or_named_in_agent_reply(
        "[doc](file:///Volumes/nedhome-other/a.md).", None)
    check("a file:///Volumes/nedhome-other link is not mapped under ned-box's home",
          found == [], f"found {found!r}")

    # On the Mac, a walk-document in a ned-box worktree is fast-read on ned-box
    # over ssh, which records the document's ned-box path.
    fake_mount = SUITE_ROOT / "fake-mac-mount"
    hook.MAC_MOUNT_OF_NED_BOX_HOME = str(fake_mount) + "/"
    mac_draft = fake_mount / "agents" / "seat" / "docs" / "walk" / "naming-rules-draft.md"
    mac_suggestions = mac_draft.with_name("naming-rules-suggestions.md")
    mac_draft.parent.mkdir(parents=True)
    mac_draft.write_text("x\n")
    mac_suggestions.write_text("report\n")
    os.utime(mac_suggestions, (4_000_000, 4_000_000))
    os.utime(mac_draft, (5_000_000, 5_000_000))
    (mac_suggestions.parent / (mac_suggestions.name + ".agent-session.json")).write_text(
        json.dumps({"agent_session_id": "s1",
                    "target": str(fake_home / "agents" / "seat" / "docs" / "walk"
                                  / "naming-rules-draft.md")}))
    record_names = hook.load_cold_read_record_names()
    check("on the Mac, a walk-document this agent-session fast-read on ned-box over ssh, "
          "then changed, is not due again",
          hook.document_is_due(mac_draft, [], None, record_names, "s1") is False)
    check("on the Mac, another agent-session's read on ned-box over ssh does not count as this one's",
          hook.document_is_due(mac_draft, [], None, record_names, "s2") is True)

    # A shared module that will not load is a fault like any other, not a traceback.
    scratch_root = SUITE_ROOT / "hook-without-its-home-module"
    (scratch_root / "scripts").mkdir(parents=True)
    (scratch_root / "nc-systems" / "general-tools").mkdir(parents=True)
    shutil.copy(HOOK_SCRIPT, scratch_root / "scripts" / HOOK_SCRIPT.name)
    rule_module = "claude-code-stop-hooks-stay-silent-while-agent-answers-a-stop-hook-rule-common.py"
    shutil.copy(HOOK_SCRIPT.resolve().parents[1] / "nc-systems" / "general-tools" / rule_module,
                scratch_root / "nc-systems" / "general-tools" / rule_module)
    completed = subprocess.run(
        [sys.executable, str(scratch_root / "scripts" / HOOK_SCRIPT.name)],
        input="{}", capture_output=True, text=True, timeout=60)
    home_module_path = (scratch_root / "nc-systems" / "general-tools"
                        / "ned-box-home-directory-and-its-mac-mount-point-path-constants-common.py")
    check("a shared module that is missing is a fault naming its path: exit 1, one stderr line, no output",
          completed.returncode == 1 and completed.stdout == ""
          and "made no check" in completed.stderr
          and f"could not load {home_module_path}: FileNotFoundError" in completed.stderr
          and len(completed.stderr.strip().splitlines()) == 1,
          f"exit {completed.returncode}, stdout {completed.stdout!r}, stderr {completed.stderr!r}")

    # An error raised inside the module carries no path of its own; the loader must add it.
    home_module_path.write_text('raise RuntimeError("injected\\nload failure")\n')
    completed = subprocess.run(
        [sys.executable, str(scratch_root / "scripts" / HOOK_SCRIPT.name)],
        input="{}", capture_output=True, text=True, timeout=60)
    check("a shared module that raises while loading is a fault naming its path: exit 1, one stderr line",
          completed.returncode == 1 and completed.stdout == ""
          and f"could not load {home_module_path}: RuntimeError: injected load failure"
          in completed.stderr
          and len(completed.stderr.strip().splitlines()) == 1,
          f"exit {completed.returncode}, stdout {completed.stdout!r}, stderr {completed.stderr!r}")

    # A module loaded by run(), after the import-time ones, is reported the same way.
    shutil.copy(HOOK_SCRIPT.resolve().parents[1] / "nc-systems" / "general-tools"
                / home_module_path.name, home_module_path)
    git_runner_module = "git-machine-readable-output-runner-and-parser-common.py"
    shutil.copy(HOOK_SCRIPT.resolve().parents[1] / "nc-systems" / "general-tools" / git_runner_module,
                scratch_root / "nc-systems" / "general-tools" / git_runner_module)
    record_names_path = scratch_root / "nc-systems" / "cold-read" / "cold-read-record-names.py"
    case = Case()
    case.transcript.write_text("")
    completed = subprocess.run(
        [sys.executable, str(scratch_root / "scripts" / HOOK_SCRIPT.name)],
        input=json.dumps({"hook_event_name": "Stop", "transcript_path": str(case.transcript)}),
        capture_output=True, text=True, timeout=60)
    check("a module run() loads that is missing is a fault naming its path: exit 1, one stderr line",
          completed.returncode == 1 and completed.stdout == ""
          and f"could not load {record_names_path}: FileNotFoundError" in completed.stderr
          and len(completed.stderr.strip().splitlines()) == 1,
          f"exit {completed.returncode}, stdout {completed.stdout!r}, stderr {completed.stderr!r}")

    # git failing to find a checkout is reported, not taken as "in no checkout".
    empty_path_directory = SUITE_ROOT / "path-without-git"
    empty_path_directory.mkdir()
    for label, environment_extra, reason_part in (
            ("outlasts its time limit", git_that_on("--show-toplevel", "exec sleep 30"),
             "did not finish within"),
            ("cannot run", {"PATH": str(empty_path_directory)}, "could not start git"),
            ("fails for another reason than being in no repository",
             git_that_on("--show-toplevel", "{ echo 'fatal: injected failure' >&2; exit 128; }"),
             "exit 128: fatal: injected failure")):
        case = Case()
        document = case.document("docs/plan-of-record.md")
        completed = case.run("See docs/plan-of-record.md.", environment_extra=environment_extra)
        context = (json.loads(completed.stdout)["hookSpecificOutput"]["additionalContext"]
                   if completed.returncode == 0 and completed.stdout.strip() else "")
        failure_part = f"git rev-parse --show-toplevel in {case.checkout} failed ({reason_part}"
        check(f"git that {label} finding the session's checkout: exit 0, said first in the output",
              completed.returncode == 0 and context.startswith("cold-read-fast-read due check incomplete")
              and failure_part in context.splitlines()[0],
              f"exit {completed.returncode}, context {context!r}, stderr {completed.stderr!r}")
        listed = [line for line in context.splitlines() if line.startswith("- ")]
        check(f"git that {label} finding the document's checkout: the document is listed as not checked",
              len(listed) == 1 and listed[0].startswith(f"- {document.resolve()}: ")
              and f"git rev-parse --show-toplevel in {document.resolve().parent} failed ({reason_part}"
              in listed[0] and "Run on each document" in context,
              f"context {context!r}")
        stderr_lines = completed.stderr.strip().splitlines()
        check(f"git that {label}: one stderr line for the session's checkout, one for the document",
              len(stderr_lines) == 2 and "could not find the top" in stderr_lines[0]
              and failure_part in stderr_lines[0]
              and str(document.resolve()) in stderr_lines[1] and reason_part in stderr_lines[1],
              f"stderr {completed.stderr!r}")
    case = Case()
    completed = case.run("No document named here.", environment_extra=git_that_on(
        "--show-toplevel", "exec sleep 30"))
    context = (json.loads(completed.stdout)["hookSpecificOutput"]["additionalContext"]
               if completed.returncode == 0 and completed.stdout.strip() else "")
    check("git that outlasts its time limit finding the session's checkout is said even when no document is found",
          context.startswith("cold-read-fast-read due check incomplete") and "did not finish within" in context,
          f"exit {completed.returncode}, context {context!r}, stderr {completed.stderr!r}")

    shutil.rmtree(SUITE_ROOT, ignore_errors=True)
    if failures:
        print(f"{len(failures)} case(s) failed")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
