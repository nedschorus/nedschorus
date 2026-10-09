#!/usr/bin/env python3
"""Cases for the Stop hook that tells an agent to fast-read the documents it
linked for the user that have had no cold-read-fast-read since their last change.

Each hook case runs the hook as a subprocess, its real stdin-to-stdout path,
in a scratch checkout this suite made, with the log-store cold-read-records directory pointed by
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
        subprocess.run(["git", "init", "-q", str(self.checkout)], check=True)
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
    subprocess.run(["git", "init", "-q", str(session_checkout)], check=True)
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
    check("an unreadable record directory is a fault: exit 1, one stderr line, no output",
          completed.returncode == 1 and completed.stdout == ""
          and "made no check" in completed.stderr
          and len(completed.stderr.strip().splitlines()) == 1,
          f"exit {completed.returncode}, stdout {completed.stdout!r}, stderr {completed.stderr!r}")

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

    shutil.rmtree(SUITE_ROOT, ignore_errors=True)
    if failures:
        print(f"{len(failures)} case(s) failed")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
