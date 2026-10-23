#!/usr/bin/env python3
"""Tests for claude-code-session-transcript-records-read-backward-common.py and the hooks that read
a transcript's last turn with it.

Run: python3 scripts/claude-code-session-transcript-records-read-backward-common-test.py
Prints one line per case and exits non-zero if any case fails.

The reader cases check the line splitting at block edges, with a block size of a few bytes so
that every line and one multi-byte character cross an edge, and the skipping a whole-file read
does: a partial last line, one ending partway through a multi-byte character, a blank line, JSON
that is not an object, a CRLF line end.

The equivalence cases run each hook's turn reader twice on the same transcript: once as it is,
reading from the end, and once with the reader swapped for a whole-file read, which is what each
hook did before. Both must give the same answer on every fixture transcript: several turns,
mid-turn prompts, peer and task-notification messages, a compaction, subagent hand-backs, tool
results, a partial last line and a turn with no prompt before it. When the machine holds real
transcripts under ~/.claude/projects/, copies of the five largest are compared too.

The early-stop case writes a transcript of about 20 MB whose first line holds bytes that are not
UTF-8: a whole-file read raises on it, so a hook that reads only the last turn shows it stopped
before the first line by not raising.
"""

import importlib.util
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
REPOSITORY_TOP = SCRIPTS.parent


def load(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


reader = load("claude_code_session_transcript_records_read_backward_common",
              SCRIPTS / "claude-code-session-transcript-records-read-backward-common.py")
absence = load("absence_claim_locator_reminder_hook", SCRIPTS / "absence-claim-locator-reminder-hook.py")
bare_number = load("bare_number_citation_in_markdown_and_agent_reply_warning_hook",
                   SCRIPTS / "bare-number-citation-in-markdown-and-agent-reply-warning-hook.py")
walk = load("walk_me_through_current_item_stop_hook",
            REPOSITORY_TOP / "nc-systems" / "skills" / "walk-me-through"
            / "walk-me-through-current-item-shown-to-user-after-each-agent-message-stop-hook.py")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def whole_file_records(path):
    """What each hook read before: every line of the file parsed, in text mode."""
    records = []
    with open(path, encoding="utf-8") as transcript:
        for line in transcript:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if isinstance(record, dict):
                records.append(record)
    return records


def whole_file_compaction_count(path):
    return sum(1 for record in whole_file_records(path)
               if record.get("type") == "system" and record.get("subtype") == "compact_boundary")


# --- fixtures ----------------------------------------------------------------

def user(text, **more):
    return {"type": "user", "message": {"role": "user", "content": text}, **more}


def assistant(message_id, *blocks):
    return {"type": "assistant", "message": {"id": message_id, "content": list(blocks)}}


def text(words):
    return {"type": "text", "text": words}


def tool_use(name, **tool_input):
    return {"type": "tool_use", "name": name, "input": tool_input}


def tool_result():
    return {"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}}


def turn_ends(origin):
    return {"type": "system", "subtype": "turn_duration", "turnOrigin": origin}


FIXTURES = {
    "one turn": [
        user("first prompt"),
        assistant("m1", text("The file is missing.")),
        turn_ends("human"),
    ],
    "several turns, the last cites PR #12": [
        user("first"), assistant("m1", text("one")), turn_ends("human"),
        user("second"), assistant("m2", text("two")), turn_ends("human"),
        user("third"), assistant("m3", tool_use("Bash", command="ls")), tool_result(),
        assistant("m3", text("See PR #12 and Item 4 of 9.")),
    ],
    "a reply split over records sharing one message id": [
        user("go"), assistant("m1", text("part one")), assistant("m1", text("part two, issue #7")),
    ],
    "a prompt typed while the agent worked": [
        user("go"), assistant("m1", text("working")),
        {"type": "attachment", "attachment": {"type": "queued_command", "origin": {"kind": "human"}}},
        assistant("m2", text("Item 2 of 5 now")), turn_ends("human"),
    ],
    "a peer message and a task notification": [
        user("go"), assistant("m1", text("done")), turn_ends("human"),
        user("from a peer", isMeta=True, origin={"kind": "peer"}),
        assistant("m2", text("answered the peer, PR #3")),
        user("<task-notification>", isMeta=True, origin={"kind": "task-notification"}),
        assistant("m3", text("noted the task")), turn_ends("task_notification"),
    ],
    # The running turn starts at a task notification and has written no turnOrigin yet, so the
    # newest turnOrigin, "human", is in the turn before it; a read that stops at the turn's
    # start alone misses it.
    "a running turn opened by a task notification, after a turn the user opened": [
        user("go"), assistant("m1", text("done")), turn_ends("human"),
        user("<task-notification>", isMeta=True, origin={"kind": "task-notification"}),
        assistant("m2", text("noting the task, Item 3 of 9")),
    ],
    "a compaction inside the transcript": [
        user("before"), assistant("m1", text("old reply")), turn_ends("human"),
        {"type": "system", "subtype": "compact_boundary"},
        user("summary of the session", isCompactSummary=True),
        user("after"), assistant("m2", text("ran locate-file-copies-across-machines.py")),
        assistant("m2", tool_use("Bash", command="python3 scripts/locate-file-copies-across-machines.py x")),
        tool_result(), assistant("m3", text("It is not there, PR #9.")),
        {"type": "system", "subtype": "compact_boundary"},
        # Lines that name the subtype but are no compaction, so the count must check the
        # record's type and subtype, not only find the word.
        {"type": "system", "subtype": "compact", "note": "compact_boundary"},
        {"type": "system", "subtype": "compact_boundary_note"},
        {"type": "user", "subtype": "compact_boundary"},
        {"type": "assistant", "subtype": "compact_boundary"},
    ],
    "a skill and a system reminder inside the turn": [
        user("go"),
        assistant("m1", tool_use("Skill", skill="locate-before-saying-a-file-is-missing")),
        user("skill text", isMeta=True), assistant("m2", text("Cannot find it.")),
    ],
    "a subagent's hand-back from its parent": [
        user("brief", isMeta=True, origin={"kind": "coordinator"}),
        assistant("m1", text("subagent report, issue #4")),
    ],
    "no prompt at all": [
        assistant("m1", text("no prompt before me")),
        {"type": "system", "subtype": "compact_boundary"},
    ],
    "an empty transcript": [],
}


def write_transcript(directory, name, records, tail=""):
    path = Path(directory) / (name.replace(" ", "-").replace(",", "").replace("#", "") + ".jsonl")
    path.write_text("".join(json.dumps(record) + "\n" for record in records) + tail, encoding="utf-8")
    return path


# --- answers, from the end and from the whole file ---------------------------

class WholeFileReader:
    """Stands in for the reader module: hands every record over, as a whole-file read did."""

    @staticmethod
    def records_from_newest_boundary_to_end(path, *is_boundary):
        return whole_file_records(path)


def answers(path):
    walk_records = walk.transcript_records(path)
    previous = bare_number.previous_reply(bare_number.previous_turn_records(path),
                                          absence.is_human_or_parent_message)
    return {
        "absence read_turn": absence.read_turn(path),
        "bare-number previous reply": previous,
        "bare-number compaction count": bare_number.compaction_count(path),
        "walk turn_reply_text": walk.turn_reply_text(walk_records),
        "walk turn_answers_user": walk.turn_answers_user(walk_records),
    }


def whole_file_answers(path):
    real_absence_reader = absence.claude_code_session_transcript_records_read_backward_common
    real_bare_number_loader = bare_number._load_claude_code_session_transcript_records_read_backward_common
    real_walk_records = walk.transcript_records
    absence.claude_code_session_transcript_records_read_backward_common = WholeFileReader
    bare_number._load_claude_code_session_transcript_records_read_backward_common = lambda: WholeFileReader
    walk.transcript_records = whole_file_records
    try:
        found = answers(path)
    finally:
        absence.claude_code_session_transcript_records_read_backward_common = real_absence_reader
        bare_number._load_claude_code_session_transcript_records_read_backward_common = real_bare_number_loader
        walk.transcript_records = real_walk_records
    found["bare-number compaction count"] = whole_file_compaction_count(path)
    return found


def compare(case_name, path):
    from_end, whole = answers(path), whole_file_answers(path)
    for key in whole:
        check(f"{case_name}: {key} is the same read from the end as read whole",
              from_end[key] == whole[key], f"from the end {from_end[key]!r}, whole {whole[key]!r}")


# --- cases --------------------------------------------------------------------

def run_reader_cases(directory):
    records = [{"n": 1, "word": "café über — \U0001f600"}, {"n": 2}, {"n": 3}]
    path = Path(directory) / "reader.jsonl"
    path.write_bytes(b"".join(json.dumps(record, ensure_ascii=False).encode() + b"\n"
                              for record in records)
                     + b"\n[1, 2]\n\"a string\"\r\n" + json.dumps({"n": 4}).encode() + b"\r\n"
                     + b'{"n": 5, "partial')
    expected = records + [{"n": 4}]
    for block_size in (3, 7, 64, 1 << 16):
        reader.BLOCK_SIZE = block_size
        found = list(reader.records_newest_first(path))
        check(f"block size {block_size}: every whole line is read newest first, the partial last "
              f"line, the blank line and the JSON that is not an object are skipped",
              found == list(reversed(expected)), repr(found))
    reader.BLOCK_SIZE = 1 << 16

    no_newline = Path(directory) / "no-newline.jsonl"
    no_newline.write_text('{"n": 1}\n{"n": 2}', encoding="utf-8")
    check("a last line with no newline after it is read",
          list(reader.records_newest_first(no_newline)) == [{"n": 2}, {"n": 1}])

    empty = Path(directory) / "empty.jsonl"
    empty.write_bytes(b"")
    check("an empty file yields no record", list(reader.records_newest_first(empty)) == [])

    numbered = Path(directory) / "numbered.jsonl"
    numbered.write_text("".join(json.dumps({"n": n, "even": n % 2 == 0}) + "\n" for n in range(1, 10)),
                        encoding="utf-8")
    found = reader.records_from_newest_boundary_to_end(numbered, lambda record: record["n"] == 6)
    check("records_from_newest_boundary_to_end stops at the newest record the predicate matches, and returns it first",
          [record["n"] for record in found] == [6, 7, 8, 9], repr(found))
    found = reader.records_from_newest_boundary_to_end(numbered, lambda record: record["n"] == 8,
                                   lambda record: record["n"] == 4)
    check("with two predicates, it reads back until each has matched a record",
          [record["n"] for record in found] == [4, 5, 6, 7, 8, 9], repr(found))
    found = reader.records_from_newest_boundary_to_end(numbered, lambda record: record["even"])
    check("of several matching records, the newest is where it stops",
          [record["n"] for record in found] == [8, 9], repr(found))
    found = reader.records_from_newest_boundary_to_end(numbered, lambda record: record["n"] == 99)
    check("a predicate no record matches returns every record, oldest first",
          [record["n"] for record in found] == list(range(1, 10)), repr(found))

    split_character = Path(directory) / "split-character.jsonl"
    split_character.write_bytes(b'{"n": 1}\n{"n": "caf\xc3')
    try:
        found = list(reader.records_newest_first(split_character))
    except UnicodeDecodeError as error:
        found = error
    check("a partial last line that ends partway through a multi-byte character is skipped",
          found == [{"n": 1}], repr(found))

    bad_last = Path(directory) / "bad-last.jsonl"
    bad_last.write_bytes(b'{"n": 1}\n{"n": "\xff"}\n')
    try:
        list(reader.records_newest_first(bad_last))
        raised = False
    except UnicodeDecodeError:
        raised = True
    check("a line it reads that is not UTF-8 raises UnicodeDecodeError, as a whole-file read does",
          raised)


def run_equivalence_cases(directory):
    for name, records in FIXTURES.items():
        compare(name, write_transcript(directory, name, records))
        compare(f"{name}, with a partial last line",
                write_transcript(directory, name + " partial", records, tail='{"type": "assist'))
    compare("a partial last line that names the compaction subtype",
            write_transcript(directory, "partial compaction", FIXTURES["a compaction inside the transcript"],
                             tail='{"type": "system", "subtype": "compact_boundary", "par'))
    real = sorted(Path.home().glob(".claude/projects/*/*.jsonl"),
                  key=lambda path: path.stat().st_size, reverse=True)[:5]
    if not real:
        print("SKIP  no real transcripts under ~/.claude/projects/ to compare")
    for path in real:
        # A live transcript grows between the two reads compare makes, so compare a copy.
        copy = Path(directory) / f"real-{path.name}"
        shutil.copyfile(path, copy)
        compare(f"real transcript {path.name} ({copy.stat().st_size // 1_000_000} MB)", copy)
        copy.unlink()


def run_early_stop_case(directory):
    path = Path(directory) / "large.jsonl"
    filler = json.dumps(assistant("old", text("x" * 2000))) + "\n"
    last_turn = FIXTURES["several turns, the last cites PR #12"]
    with open(path, "wb") as transcript:
        transcript.write(b'{"bad": "\xff"}\n')
        transcript.write(filler.encode() * 10_000)
        transcript.write("".join(json.dumps(record) + "\n" for record in last_turn).encode())
    size = path.stat().st_size // 1_000_000
    try:
        whole_file_records(path)
        whole_raised = False
    except UnicodeDecodeError:
        whole_raised = True
    started = time.perf_counter()
    try:
        reply, _ = absence.read_turn(path)
        walk_records = walk.transcript_records(path)
        previous, _ = bare_number.previous_reply(bare_number.previous_turn_records(path),
                                                 absence.is_human_or_parent_message)
        raised = None
    except UnicodeDecodeError as error:
        raised = error
    elapsed = time.perf_counter() - started
    check(f"a {size} MB transcript whose first line is not UTF-8: a whole-file read raises on it",
          whole_raised)
    check(f"each hook reads its last turn without reaching the first line, in {elapsed * 1000:.0f} ms",
          raised is None and reply == "See PR #12 and Item 4 of 9." and previous == reply
          and walk.turn_reply_text(walk_records).endswith(reply), repr(raised))


with tempfile.TemporaryDirectory() as scratch:
    run_reader_cases(scratch)
    run_equivalence_cases(scratch)
    run_early_stop_case(scratch)

if failures:
    print(f"\n{len(failures)} case(s) failed")
    sys.exit(1)
print("\nall cases passed")
