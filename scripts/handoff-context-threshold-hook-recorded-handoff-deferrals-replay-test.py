#!/usr/bin/env python3
"""Tests that the threshold hook counts a subagent whose last task-notification is interim only
while that subagent's own transcript shows work in flight.

Two kinds of case. Synthetic cases pin each edge of the rule: the 5-minute recent-write window,
the subagent's own background task and its wait, a missing own transcript, and an own transcript
that cannot be read. Recorded cases replay past session-handoff deferrals from trimmed copies of their real
transcripts, kept in
handoff-context-threshold-hook-recorded-handoff-deferrals-replay-test-fixtures/: each case is cut at each moment
cases.json names, as if the hook ran then, and the subagents and background tasks the hook counts
must match the lists cases.json records. Those lists were checked, subagent by subagent, against
what the subagent's full transcript shows it did after that moment.

Run: python3 scripts/handoff-context-threshold-hook-recorded-handoff-deferrals-replay-test.py
"""

import contextlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

# The hook computes its marker directory from HOME at import; keep this suite's markers its own.
SUITE_HOME = Path(tempfile.mkdtemp(prefix="handoff-threshold-hook-past-waits-test-home-"))
os.environ["HOME"] = str(SUITE_HOME)

HOOK_SCRIPT = Path(__file__).with_name("handoff-context-threshold-hook.py")
FIXTURES = Path(__file__).with_name("handoff-context-threshold-hook-recorded-handoff-deferrals-replay-test-fixtures")

_hook_spec = importlib.util.spec_from_file_location("handoff_threshold_hook", HOOK_SCRIPT)
hook = importlib.util.module_from_spec(_hook_spec)
_hook_spec.loader.exec_module(hook)

WAIT_SECONDS = hook.DEFAULT_BACKGROUND_TASK_WAIT_MINUTES * 60
failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        failures.append(case_name)
        print(f"FAIL  {case_name}  {detail}")


def parse_time(stamp):
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def utc_iso(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def write_jsonl(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    return path


NOW = datetime(2026, 10, 30, 21, 0, 0, tzinfo=timezone.utc)
SUBAGENT_ID = "aecc60a4911a7ff7e"
OWN_TASK_ID = "blrsaarzi"

# The fork's interim notification from case 20's fixture below, trimmed as the fixtures are.
INTERIM_NOTIFICATION = (
    "<task-notification>\n"
    f"<task-id>{SUBAGENT_ID}</task-id>\n"
    "<status>completed</status>\n"
    '<summary>Agent "Fix-round for PR 2213 review" is waiting on its own background work</summary>\n'
    "<note>This agent stopped with background work of its own still running. It may resume on "
    "its own when that work completes or reports, and the same task-id notifies again if it "
    "does; the result below may be interim.</note>\n"
    "<result>Waiting on the test run.</result>\n"
    "</task-notification>")


def spawn_record(agent_id, moment):
    return {"type": "user", "timestamp": utc_iso(moment), "toolUseResult": {
        "isAsync": True, "status": "async_launched", "agentId": agent_id,
        "description": "Fix-round for PR 2213 review"}}


def launch_record(task_id, moment):
    return {"type": "user", "timestamp": utc_iso(moment),
            "toolUseResult": {"backgroundTaskId": task_id}}


def completion_record(task_id, moment):
    return {"type": "user", "timestamp": utc_iso(moment), "content": (
        "<task-notification>\n"
        f"<task-id>{task_id}</task-id>\n"
        "<status>completed</status>\n"
        '<summary>Background command "Run changed test suites" completed (exit code 0)</summary>\n'
        "</task-notification>")}


def session_with_interim_subagent(directory, own_records=None):
    """A session whose one subagent's last notice is interim; own_records, when given, become its
    own transcript beside the session's."""
    session = write_jsonl(Path(directory) / "session.jsonl", [
        spawn_record(SUBAGENT_ID, NOW - timedelta(hours=1)),
        {"type": "user", "timestamp": utc_iso(NOW - timedelta(minutes=30)),
         "content": INTERIM_NOTIFICATION},
    ])
    if own_records is not None:
        write_jsonl(hook.subagent_transcript_path(session, SUBAGENT_ID), own_records)
    return session


def counted(session, now=NOW):
    """The subagent ids the hook counts, or, when the hook raises, the text "raised <exception>",
    which equals no list: the check then prints a FAIL line naming the exception and the suite goes on."""
    try:
        return hook.work_in_flight(str(session), WAIT_SECONDS, now=now).subagent_ids
    except Exception as problem:
        return f"raised {type(problem).__name__}: {problem}"


def check_raises_could_not_read(case_name, session):
    """Checks that the hook raises TranscriptCouldNotBeFullyRead; when it raises anything else, the
    FAIL line names that exception and the suite goes on, as counted() does."""
    try:
        hook.work_in_flight(str(session), WAIT_SECONDS, now=NOW)
    except hook.TranscriptCouldNotBeFullyRead:
        outcome = None
    except Exception as problem:
        outcome = f"raised {type(problem).__name__}: {problem}"
    else:
        outcome = "returned without raising"
    check(case_name, outcome is None, outcome)


def printed_by_check_raises_could_not_read(session):
    """What check_raises_could_not_read() prints for the session, leaving the suite's failures untouched."""
    failures_before = list(failures)
    printed = io.StringIO()
    try:
        with contextlib.redirect_stdout(printed):
            check_raises_could_not_read("the checked case", session)
    finally:
        failures[:] = failures_before
    return printed.getvalue()


def run_synthetic_cases(workspace):
    def case_directory(name):
        directory = Path(workspace) / name
        directory.mkdir()
        return directory

    session = session_with_interim_subagent(case_directory("path"), [])
    check("the own transcript is subagents/agent-<id>.jsonl in the directory named after the session",
          hook.subagent_transcript_path(session, SUBAGENT_ID)
          == Path(workspace) / "path" / "session" / "subagents" / f"agent-{SUBAGENT_ID}.jsonl",
          str(hook.subagent_transcript_path(session, SUBAGENT_ID)))

    # --- The 5-minute recent-write window ---------------------------------------------------
    session = session_with_interim_subagent(case_directory("written-4m59s-ago"), [
        {"type": "assistant", "timestamp": utc_iso(NOW - timedelta(minutes=4, seconds=59))}])
    check("an interim subagent whose own transcript was written 4m59s ago is counted",
          counted(session) == [SUBAGENT_ID], str(counted(session)))

    session = session_with_interim_subagent(case_directory("written-exactly-5m-ago"), [
        {"type": "assistant", "timestamp": utc_iso(NOW - timedelta(minutes=5))}])
    check("an interim subagent whose own transcript was written exactly 5 minutes ago is counted",
          counted(session) == [SUBAGENT_ID], str(counted(session)))

    # Timestamps are not always in line order; the newest line decides, not the latest time.
    session = session_with_interim_subagent(case_directory("newest-line-older-than-an-earlier-one"), [
        {"type": "attachment", "timestamp": utc_iso(NOW - timedelta(minutes=1))},
        {"type": "assistant", "timestamp": utc_iso(NOW - timedelta(minutes=20))}])
    check("the recent-write window reads only the newest timestamped line",
          counted(session) == [], str(counted(session)))

    session = session_with_interim_subagent(case_directory("written-5m01s-ago"), [
        {"type": "assistant", "timestamp": utc_iso(NOW - timedelta(minutes=5, seconds=1))}])
    check("an interim subagent whose own transcript was last written 5m01s ago is not counted",
          counted(session) == [], str(counted(session)))

    # A newest line with no timestamp, such as the line Claude Code is still writing, must not
    # hide the record before it.
    session = session_with_interim_subagent(case_directory("untimed-newest-line"), [
        {"type": "assistant", "timestamp": utc_iso(NOW - timedelta(minutes=1))},
        {"type": "fork-context-ref"}])
    check("the recent-write window reads the newest record that has a timestamp",
          counted(session) == [SUBAGENT_ID], str(counted(session)))

    # --- The subagent's own background task -------------------------------------------------
    stale_write = {"type": "assistant", "timestamp": utc_iso(NOW - timedelta(minutes=20))}
    session = session_with_interim_subagent(case_directory("own-task-74-minutes"), [
        launch_record(OWN_TASK_ID, NOW - timedelta(minutes=74)), stale_write])
    check("an interim subagent with its own unnotified background task 74 minutes old is counted",
          counted(session) == [SUBAGENT_ID], str(counted(session)))

    session = session_with_interim_subagent(case_directory("own-task-76-minutes"), [
        launch_record(OWN_TASK_ID, NOW - timedelta(minutes=76)), stale_write])
    check("an interim subagent whose own background task is 76 minutes old is not counted",
          counted(session) == [], str(counted(session)))

    session = session_with_interim_subagent(case_directory("own-task-74-minutes-short-wait"), [
        launch_record(OWN_TASK_ID, NOW - timedelta(minutes=74)), stale_write])
    short_wait = hook.work_in_flight(str(session), 60 * 60, now=NOW).subagent_ids
    check("the own background task is judged with the hook's --background-task-wait-minutes",
          short_wait == [], str(short_wait))

    session = session_with_interim_subagent(case_directory("own-task-notified"), [
        launch_record(OWN_TASK_ID, NOW - timedelta(minutes=30)),
        completion_record(OWN_TASK_ID, NOW - timedelta(minutes=20))])
    check("an interim subagent whose own background task has notified is not counted",
          counted(session) == [], str(counted(session)))

    # --- What the session transcript alone still decides ------------------------------------
    session = session_with_interim_subagent(case_directory("no-own-transcript"))
    check("an interim subagent with no own transcript is not counted",
          counted(session) == [], str(counted(session)))
    check("should_read_subagent_own_transcripts=False counts the interim subagent from its notices alone",
          hook.work_in_flight(str(session), WAIT_SECONDS, now=NOW,
                              should_read_subagent_own_transcripts=False).subagent_ids == [SUBAGENT_ID])

    no_notice = write_jsonl(case_directory("no-notice-yet") / "session.jsonl",
                            [spawn_record(SUBAGENT_ID, NOW - timedelta(hours=3))])
    check("a subagent with no notice yet is counted without its own transcript",
          counted(no_notice) == [SUBAGENT_ID], str(counted(no_notice)))

    # --- An own transcript that cannot be read ----------------------------------------------
    session = session_with_interim_subagent(case_directory("own-transcript-bad-bytes"), [])
    own_path = hook.subagent_transcript_path(session, SUBAGENT_ID)
    own_path.write_bytes(b'{"type":"assistant","timestamp":"2026-10-30T20:59:00.000Z"}\n'
                         b'{"type":"assistant","note":"\xff\xfe"}\n')
    check_raises_could_not_read("an own transcript holding bytes that are not UTF-8 raises "
                                "TranscriptCouldNotBeFullyRead", session)

    session = session_with_interim_subagent(
        case_directory("own-transcript-bad-bytes-before-stale-newest-record"), [])
    own_path = hook.subagent_transcript_path(session, SUBAGENT_ID)
    own_path.write_bytes(b'{"type":"assistant","note":"\xff\xfe"}\n'
                         b'{"type":"assistant","timestamp":"2026-10-30T20:00:00.000Z"}\n')
    check_raises_could_not_read("bytes that are not UTF-8 before a stale newest record raise "
                                "TranscriptCouldNotBeFullyRead", session)

    session_bad_bytes = case_directory("session-transcript-bad-bytes-outside-records") / "session.jsonl"
    session_bad_bytes.parent.mkdir(parents=True, exist_ok=True)
    session_bad_bytes.write_bytes(
        (json.dumps(spawn_record(SUBAGENT_ID, NOW - timedelta(hours=3))) + "\n").encode()
        + b'{"type":"assistant","note":"\xff\xfe"}\n')
    check("bytes that are not UTF-8 in a session transcript line the scan does not parse are "
          "read past", counted(session_bad_bytes) == [SUBAGENT_ID], str(counted(session_bad_bytes)))

    session = session_with_interim_subagent(case_directory("own-transcript-lookup-fails"), [
        {"type": "assistant", "timestamp": utc_iso(NOW - timedelta(minutes=1))}])
    subagents_directory = hook.subagent_transcript_path(session, SUBAGENT_ID).parent
    # No search permission makes stat() on the transcript fail with EACCES, not ENOENT.
    subagents_directory.chmod(0o600)
    try:
        check_raises_could_not_read("an own transcript whose lookup fails for a reason other than absence "
                                    "raises TranscriptCouldNotBeFullyRead", session)
    finally:
        subagents_directory.chmod(0o700)

    session = session_with_interim_subagent(case_directory("own-transcript-unreadable"), [])
    real_reader = hook.transcript_records.records_newest_first

    def reader_that_cannot_open(path):
        raise OSError(13, "Permission denied", str(path))

    hook.transcript_records.records_newest_first = reader_that_cannot_open
    try:
        check_raises_could_not_read("an own transcript that cannot be opened raises "
                                    "TranscriptCouldNotBeFullyRead", session)
    finally:
        hook.transcript_records.records_newest_first = real_reader

    session = session_with_interim_subagent(case_directory("own-transcript-reader-raises-value-error"), [])

    def reader_that_raises_value_error(path):
        raise ValueError("injected by this test")

    hook.transcript_records.records_newest_first = reader_that_raises_value_error
    try:
        printed = printed_by_check_raises_could_not_read(session)
    finally:
        hook.transcript_records.records_newest_first = real_reader
    check("a hook exception other than TranscriptCouldNotBeFullyRead prints a FAIL line naming the "
          "case and the exception",
          printed == "FAIL  the checked case  raised ValueError: injected by this test\n", repr(printed))

    session = session_with_interim_subagent(case_directory("own-transcript-readable"), [
        {"type": "assistant", "timestamp": utc_iso(NOW - timedelta(minutes=1))}])
    printed = printed_by_check_raises_could_not_read(session)
    check("a hook that raises nothing prints a FAIL line saying so",
          printed == "FAIL  the checked case  returned without raising\n", repr(printed))

def cut_copy(source_session, destination_directory, moment):
    """Copy a fixture session and its subagents' transcripts, each ending before its first record
    newer than the moment, as the files stood when the hook ran then."""
    def cut(source, destination):
        destination.parent.mkdir(parents=True, exist_ok=True)
        kept = []
        for line in source.read_text(encoding="utf-8").splitlines(keepends=True):
            stamp = json.loads(line).get("timestamp")
            if isinstance(stamp, str) and parse_time(stamp) > moment:
                break
            kept.append(line)
        destination.write_text("".join(kept), encoding="utf-8")

    destination_session = destination_directory / source_session.name
    cut(source_session, destination_session)
    for own in sorted(source_session.with_suffix("").glob("subagents/agent-*.jsonl")):
        cut(own, hook.subagent_transcript_path(destination_session, own.stem[len("agent-"):]))
    return destination_session


def run_past_wait_cases(workspace):
    cases = json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))
    verdicts = {}
    for case in cases:
        for number, expected in enumerate(case["moments"]):
            moment = parse_time(expected["moment"])
            session = cut_copy(FIXTURES / case["session_transcript"],
                               Path(workspace) / case["case"] / str(number), moment)
            by_own = hook.work_in_flight(str(session), WAIT_SECONDS, now=moment)
            by_notices = hook.work_in_flight(str(session), WAIT_SECONDS, now=moment,
                                             should_read_subagent_own_transcripts=False)
            verdicts[(case["case"][:2], expected["moment"])] = by_own.subagent_ids
            check(f"case {case['case']} at {expected['moment']} ({expected['why_this_moment']})",
                  by_own.subagent_ids == expected["subagents_counted_by_own_transcripts"]
                  and by_notices.subagent_ids == expected["subagents_counted_by_notices_alone"]
                  and by_own.background_task_ids == expected["background_tasks"],
                  f"own transcripts {by_own.subagent_ids}, notices alone {by_notices.subagent_ids}, "
                  f"background tasks {by_own.background_task_ids}")
    return verdicts


def check_named_past_waits(verdicts):
    """The past waits the change was made for, each stated on its own."""
    named = [
        ("03", "2026-10-28T21:46:37.000Z", [],
         "merge-lane-2 72d04355 at its 65% ceiling: its one phantom, a043d8c1b4dfbec37, is not counted"),
        ("06", "2026-10-29T16:17:52.000Z", ["a9ab243b54a67773a", "a25748fab364a9faa"],
         "ned-box-helper 329c61e9 at its 65% ceiling: of 7 subagents, only the one spawned 3 s before "
         "and the one whose own transcript was written 76 s before are counted"),
        ("07", "2026-10-30T00:07:19.000Z", [],
         "fleet-restart-at-login 1306bfd9 at its 65% ceiling: its one phantom is not counted"),
        ("19", "2026-10-29T22:54:14.000Z", [],
         "reboot-test 222a1661: a145fa7adbc036372, last interim notice 17:10:29Z, is not counted"),
        ("20", "2026-10-30T20:43:30.000Z", ["aecc60a4911a7ff7e"],
         "reboot-test 28da2061: the PR 2213 fork is counted while its background task is under 75 minutes"),
        ("20", "2026-10-30T21:50:00.000Z", [],
         "reboot-test 28da2061: the PR 2213 fork is not counted once that task is past 75 minutes"),
        ("21", "2026-10-31T00:30:00.000Z", [],
         "cold-read-improvement 71798983: the finished subagent's leftover wait loop, past 75 minutes, "
         "holds nothing"),
        ("22", "2026-10-31T04:00:00.000Z", [],
         "ned-box-helper 7d38ec25: ac0cee90b8ff7486a, last written 2026-10-29T16:41Z, is not counted"),
    ]
    for case_number, moment, expected, statement in named:
        got = verdicts.get((case_number, moment))
        check(statement, got == expected, str(got))


def main():
    workspace = tempfile.mkdtemp(prefix="handoff-threshold-hook-past-waits-test-")
    try:
        run_synthetic_cases(workspace)
        check_named_past_waits(run_past_wait_cases(workspace))
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
        shutil.rmtree(SUITE_HOME, ignore_errors=True)
    if failures:
        print(f"\n{len(failures)} case(s) failed: {', '.join(failures)}")
        return 1
    print("\nall cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
