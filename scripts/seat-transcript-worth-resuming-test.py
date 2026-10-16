#!/usr/bin/env python3
"""Tests for scripts/seat-transcript-worth-resuming.py, which picks the
transcript a restarted agent-seat resumes.

Recovery and the handoff-supervisor reach this module through their own
suites. These cases pin its three functions directly: which first user turn
counts, which assistant turns count as work, and which transcript is newest
and worth resuming.

Run: python3 scripts/seat-transcript-worth-resuming-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

MODULE_PATH = Path(os.environ.get(
    "SEAT_TRANSCRIPT_WORTH_RESUMING_MODULE_PATH",
    Path(__file__).resolve().parent / "seat-transcript-worth-resuming.py"))
_spec = importlib.util.spec_from_file_location("seat_transcript_worth_resuming", MODULE_PATH)
resuming = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(resuming)

failures = 0


def check(name, condition, detail=None):
    global failures
    if condition:
        print(f"PASS  {name}")
    else:
        failures += 1
        print(f"FAIL  {name}: {detail!r}")


def user(content, meta=False):
    record = {"type": "user", "message": {"role": "user", "content": content}}
    if meta:
        record["isMeta"] = True
    return record


def assistant(content, model="claude-opus-5-5"):
    return {"type": "assistant", "message": {"role": "assistant", "model": model,
                                             "content": content}}


def write_transcript(path, records, extra_lines=(), modified_at=None):
    lines = [json.dumps(record) for record in records] + list(extra_lines)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if modified_at is not None:
        os.utime(path, (modified_at, modified_at))
    return path


with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch)

    # first_user_turn_text
    path = write_transcript(scratch / "first.jsonl", [
        {"type": "summary"}, user("harness note", meta=True), user("real first prompt"),
        user("second prompt")], extra_lines=["not json"])
    check("first user turn: skips other records and meta turns",
          resuming.first_user_turn_text(path) == "real first prompt",
          resuming.first_user_turn_text(path))
    path = write_transcript(scratch / "broken-first.jsonl", [user("after a bad line")],
                            extra_lines=[])
    path.write_text("{not json\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
    check("first user turn: a line that is not JSON is skipped",
          resuming.first_user_turn_text(path) == "after a bad line")
    blocks = [{"type": "text", "text": "block prompt"}]
    path = write_transcript(scratch / "list.jsonl", [user(blocks)])
    check("first user turn: list content comes back as its JSON",
          resuming.first_user_turn_text(path) == json.dumps(blocks))
    path = write_transcript(scratch / "odd.jsonl", [user(None), user("later")])
    check("first user turn: content neither text nor list gives empty text",
          resuming.first_user_turn_text(path) == "")
    check("first user turn: an unreadable file gives empty text",
          resuming.first_user_turn_text(scratch / "missing.jsonl") == "")
    path = scratch / "bad-bytes.jsonl"
    path.write_bytes(json.dumps(user("café"), ensure_ascii=False).encode("utf-8").replace(
        "é".encode("utf-8"), b"\xff") + b"\n")
    check("first user turn: invalid UTF-8 is replaced, not fatal",
          resuming.first_user_turn_text(path).startswith("caf"),
          resuming.first_user_turn_text(path))

    # substantive_turn_count
    path = write_transcript(scratch / "turns.jsonl", [
        user("go"),
        assistant("plain text reply"),
        assistant("   "),
        assistant([{"type": "text", "text": "list text"}]),
        assistant([{"type": "text", "text": "  "}]),
        assistant([{"type": "tool_use", "name": "Bash", "input": {}}]),
        assistant([{"type": "thinking", "thinking": "only thinking"}]),
        assistant("harness error notice", model="<synthetic>"),
        assistant(["not a dict", {"type": "text", "text": "after a stray item"}]),
        assistant(None),
    ], extra_lines=["{broken"])
    count = resuming.substantive_turn_count(path)
    check("work turns: text, list text, tool use and a list with stray items count; "
          "blank text, thinking only, synthetic and empty turns do not",
          count == 4, count)
    check("work turns: an unreadable file counts zero",
          resuming.substantive_turn_count(scratch / "missing.jsonl") == 0)

    # newest_real_transcript
    check("newest: no project directory is reported, not raised",
          resuming.newest_real_transcript(scratch / "no-such-dir")[0] is None
          and "no harness project directory" in
          resuming.newest_real_transcript(scratch / "no-such-dir")[1])
    empty_directory = scratch / "empty-project"
    empty_directory.mkdir()
    result = resuming.newest_real_transcript(empty_directory)
    check("newest: a directory with no transcripts is reported",
          result[0] is None and "no transcripts under" in result[1], result)

    project = scratch / "project"
    project.mkdir()
    write_transcript(project / "older-real.jsonl", [user("real work"), assistant("done")],
                     modified_at=1_000)
    write_transcript(project / "newer-empty-successor.jsonl", [
        user("No handoff exists yet for this seat"), assistant("ok")], modified_at=2_000)
    write_transcript(project / "newest-blank-first-turn.jsonl", [user("   ")],
                     modified_at=3_000)
    result = resuming.newest_real_transcript(project)
    check("newest: skips a blank first turn and an empty successor, by modification time",
          result[0] == "older-real", result)
    write_transcript(project / "oldest-real.jsonl", [user("older work"), assistant("done")],
                     modified_at=500)
    result = resuming.newest_real_transcript(project)
    check("newest: of two real transcripts, the one modified last wins",
          result[0] == "older-real", result)

    for marker in resuming.EMPTY_SUCCESSOR_MARKERS:
        directory = scratch / f"marker-{abs(hash(marker))}"
        directory.mkdir()
        write_transcript(directory / "only.jsonl", [user(f"opener: {marker}")])
        result = resuming.newest_real_transcript(directory)
        check(f"newest: an opener holding {marker!r} with no work is an empty successor",
              result[0] is None and "empty-successor" in result[1], result)

    worked = scratch / "worked-successor"
    worked.mkdir()
    write_transcript(worked / "worked.jsonl", [
        user("resumed by crash recovery"), assistant("one"), assistant("two")])
    result = resuming.newest_real_transcript(worked)
    check("newest: a successor opener with two work turns is worth resuming",
          result[0] == "worked", result)
    one_turn = scratch / "one-turn-successor"
    one_turn.mkdir()
    write_transcript(one_turn / "one.jsonl", [
        user("resumed by crash recovery"), assistant("one")])
    check("newest: a successor opener with one work turn is not",
          resuming.newest_real_transcript(one_turn)[0] is None)

    large = scratch / "large"
    large.mkdir()
    write_transcript(large / "large.jsonl", [user("No handoff exists yet")],
                     extra_lines=["x" * (resuming.EMPTY_SUCCESSOR_MAX_BYTES + 1)])
    check("newest: a transcript over the size limit is resumed without reading its opener",
          resuming.newest_real_transcript(large)[0] == "large")
    at_limit = scratch / "at-limit"
    at_limit.mkdir()
    first = json.dumps(user("No handoff exists yet")) + "\n"
    filler = "x" * (resuming.EMPTY_SUCCESSOR_MAX_BYTES - len(first.encode()) - 1)
    (at_limit / "edge.jsonl").write_text(first + filler + "\n", encoding="utf-8")
    check("newest: a transcript exactly at the size limit is still judged by its opener",
          (at_limit / "edge.jsonl").stat().st_size == resuming.EMPTY_SUCCESSOR_MAX_BYTES
          and resuming.newest_real_transcript(at_limit)[0] is None)

    ignored = scratch / "other-files"
    ignored.mkdir()
    (ignored / "notes.txt").write_text("real work", encoding="utf-8")
    check("newest: only .jsonl files are transcripts",
          resuming.newest_real_transcript(ignored)[0] is None)

print(f"{failures} failure(s)" if failures else "all cases pass")
sys.exit(1 if failures else 0)
