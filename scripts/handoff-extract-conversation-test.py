#!/usr/bin/env python3
"""Tests for handoff-extract-conversation.py.

Run: python3 scripts/handoff-extract-conversation-test.py
Prints one line per case and exits non-zero if any case fails.

Every case builds its own transcript in a temporary directory, so the tests
never read a real session and never touch ~/.claude.
"""

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name("handoff-extract-conversation.py")

_spec = importlib.util.spec_from_file_location("handoff_extract_conversation", SCRIPT_PATH)
extractor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(extractor)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def user_record(text, **overrides):
    record = {"type": "user", "message": {"content": text}}
    record.update(overrides)
    return record


def assistant_record(text, **overrides):
    record = {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": text}]},
    }
    record.update(overrides)
    return record


def write_transcript(directory, name, records, trailing_raw_lines=()):
    transcript_path = Path(directory) / name
    with transcript_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")
        for raw in trailing_raw_lines:
            handle.write(raw)
    return transcript_path


def ordinary_records():
    return [
        user_record("first prompt"),
        assistant_record("first answer"),
        user_record("the boundary prompt\nwith a second line"),
        assistant_record("answer after the boundary"),
        user_record("last prompt"),
        assistant_record("last answer"),
    ]


with tempfile.TemporaryDirectory() as workspace:
    # --- Dialog selection -------------------------------------------------
    path = write_transcript(workspace, "plain.jsonl", ordinary_records())
    turns, skips = extractor.read_dialog_turns(path)
    check("reads every dialog turn", len(turns) == 6, f"got {len(turns)}")
    check("no skips on a clean transcript", not any(skips.values()), str(skips))

    # minimum_words=0 isolates boundary selection from the word floor.
    selected, start, quoted = extractor.select_turns_from_boundary(turns, "the boundary prompt", 0)
    check("boundary starts at the quoted prompt", selected[0]["text"].startswith("the boundary prompt"))
    check("boundary carries to the end", len(selected) == 4, f"got {len(selected)}")
    check("boundary reports its index", start == 2 and quoted == 2, f"got {start},{quoted}")

    try:
        extractor.select_turns_from_boundary(turns, "a prompt nobody typed")
        check("missing boundary refuses", False, "no exception raised")
    except extractor.TranscriptProblem:
        check("missing boundary refuses", True)

    # --- The word floor widens a too-tight boundary ------------------------
    # Ten topics of ~600 words each: comfortably above a 2500-word floor in
    # total, comfortably below it for any single topic.
    wordy = []
    for topic in range(10):
        wordy.append(user_record(f"topic {topic} opens"))
        wordy.append(assistant_record(" ".join(["word"] * 600)))
    path = write_transcript(workspace, "wordy.jsonl", wordy)
    turns, _ = extractor.read_dialog_turns(path)

    selected, start, quoted = extractor.select_turns_from_boundary(turns, "topic 9 opens", 2500)
    check("floor widens a too-tight boundary", start < quoted, f"start {start}, quoted {quoted}")
    check("widened selection clears the floor", extractor.word_count(selected) >= 2500,
          extractor.word_count(selected))
    check("widened boundary lands on a user prompt", selected[0]["voice"] == "user", selected[0]["voice"])

    selected, start, quoted = extractor.select_turns_from_boundary(turns, "topic 1 opens", 2500)
    check("a boundary already clearing the floor is untouched", start == quoted, f"{start} vs {quoted}")

    # Quoting the LAST topic forces the widening walk to traverse the whole
    # session (a boundary already at index 0 would pass this trivially).
    selected, start, _ = extractor.select_turns_from_boundary(turns, "topic 9 opens", 999999)
    check("an unreachable floor carries the whole session", start == 0, f"got {start}")

    # --- The default: a floor-sized tail, no boundary named ---------------
    selected, start = extractor.select_tail_clearing_floor(turns, 2500)
    check("default tail clears the floor", extractor.word_count(selected) >= 2500,
          extractor.word_count(selected))
    check("default tail opens on a user prompt", selected[0]["voice"] == "user", selected[0]["voice"])
    check("default tail leaves earlier turns behind", start > 0, f"got {start}")
    check(
        "default tail carries no more than it needs",
        extractor.word_count(selected) < 2500 + 1300,
        extractor.word_count(selected),
    )

    selected, start = extractor.select_tail_clearing_floor(turns, 999999)
    check("an unreachable floor carries everything", start == 0 and len(selected) == len(turns))

    exit_code = extractor.main(["--transcript-path", str(path), "--output", str(Path(workspace) / "default.md")])
    check("extraction runs with no boundary argument at all", exit_code == 0, f"got {exit_code}")
    default_text = (Path(workspace) / "default.md").read_text(encoding="utf-8")
    check("default extraction names the floor in its header",
          f"clearing {extractor.MINIMUM_DIALOG_WORDS} words" in default_text,
          default_text[:200])

    # --- Noise classes are dropped ---------------------------------------
    noisy = [
        user_record("kept prompt"),
        {"type": "user", "isMeta": True,
         "message": {"content": "<local-command-caveat>injected</local-command-caveat>"}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "content": "huge tool dump"}]}},
        {
            "type": "assistant",
            "message": {"content": [{"type": "thinking", "thinking": "private reasoning"},
                                     {"type": "tool_use", "name": "Bash", "input": {}},
                                     {"type": "text", "text": "kept answer"}]},
        },
        user_record("subagent prompt", isSidechain=True),
        assistant_record("subagent answer", isSidechain=True),
        {"type": "system", "content": "system notice"},
        {"type": "queue-operation", "operation": "enqueue", "content": "<task-notification/>"},
        {"type": "file-history-snapshot", "snapshot": {}},
    ]
    path = write_transcript(workspace, "noisy.jsonl", noisy)
    turns, _ = extractor.read_dialog_turns(path)
    kept = [turn["text"] for turn in turns]
    check("keeps both voices, drops all noise", kept == ["kept prompt", "kept answer"], str(kept))

    # --- Messages typed while the agent was mid-turn -----------------------
    # These are NOT user records. The harness queues them and persists an
    # attachment of type queued_command, which the type filter dropped — so
    # every message the user typed during a running turn was invisible to the
    # handoff. Shapes below are copied from the field (2026-08-23 census of 530
    # transcripts: 294 human-origin records, 283 appearing nowhere else in
    # their own transcript), not from the design.
    def queued(prompt, kind="human"):
        origin = {"kind": kind} if kind is not None else None
        return {"type": "attachment",
                "attachment": {"type": "queued_command", "prompt": prompt, "origin": origin}}

    mid_turn = [
        user_record("first prompt"),
        assistant_record("working on it"),
        queued("the post tool hook is the magic"),
        assistant_record("answer after the interruption"),
    ]
    path = write_transcript(workspace, "mid-turn.jsonl", mid_turn)
    turns, _ = extractor.read_dialog_turns(path)
    kept = [(turn["voice"], turn["text"]) for turn in turns]
    check(
        "a message typed mid-turn is carried, in the position it was delivered",
        kept == [("user", "first prompt"), ("assistant", "working on it"),
                 ("user", "the post tool hook is the magic"),
                 ("assistant", "answer after the interruption")],
        str(kept),
    )

    other_origins = [
        user_record("real prompt"),
        queued("<cross-session-message from-name=\"merge-lane\">merge #143</cross-session-message>", kind="peer"),
        queued("<task-notification><task-id>b1</task-id></task-notification>", kind=None),
        queued("", kind="human"),
        {"type": "attachment", "attachment": {"type": "total_tokens_reminder", "text": "<total_tokens>1</total_tokens>"}},
        assistant_record("real answer"),
    ]
    path = write_transcript(workspace, "other-origins.jsonl", other_origins)
    turns, _ = extractor.read_dialog_turns(path)
    kept = [turn["text"] for turn in turns]
    check(
        "another agent's message, a task notification, an empty one and a "
        "non-command attachment all stay out",
        kept == ["real prompt", "real answer"],
        str(kept),
    )

    # --- Harness-injected pseudo-prompts and their acknowledgements --------
    # Fixture shapes are copied from the field, not the design: a delivered
    # monitor notification persists as a PLAIN user record — no isMeta, string
    # content — indistinguishable by type from a typed prompt. The original
    # fixture modeled it as a queue-operation record, which the filter always
    # dropped, so the tests stayed green while real extracts ran 79% noise
    # (2026-08-17 census of 341 transcripts: handoff-census-user-record-shapes.py).
    notification_text = (
        "<task-notification>\n<task-id>b123</task-id>\n"
        '<summary>Monitor event: "fleet watcher"</summary>\n'
        "<event>some seat said something</event>\n"
        "If this event is something the user would act on now, send a "
        "PushNotification. Routine or benign output doesn't need one.\n"
        "</task-notification>"
    )
    injected = [
        user_record("real question"),
        assistant_record("real answer to the question"),
        user_record(notification_text),
        assistant_record("Routine — noted. On watch."),
        user_record(notification_text),
        assistant_record(" ".join(["urgent"] * 80)),
        user_record("<command-message>walk-me-through</command-message> "
                    "<command-name>/walk-me-through</command-name>"),
        user_record("<local-command-stdout>Set model to Opus</local-command-stdout>"),
        user_record("[Request interrupted by user]"),
        user_record("<bash-input>git status</bash-input>"),
        assistant_record("short reply after a real prompt"),
    ]
    path = write_transcript(workspace, "injected.jsonl", injected)
    turns, skips = extractor.read_dialog_turns(path)
    kept = [turn["text"] for turn in turns]
    check("notification pseudo-prompts are dropped",
          not any("<task-notification>" in text for text in kept), str(kept)[:200])
    check("command and interrupt records are dropped",
          not any(text.startswith(("<command-", "<local-command", "[Request interrupted"))
                  for text in kept), str(kept)[:200])
    check("the short acknowledgement falls with its notification",
          "Routine — noted. On watch." not in kept, str(kept)[:200])
    check("a long reaction to a notification survives as dialog",
          any(text.startswith("urgent") for text in kept), str(kept)[:200])
    check("bash-input is kept — the user typed it",
          "<bash-input>git status</bash-input>" in kept, str(kept)[:200])
    check("a short answer after a real prompt is kept",
          "short reply after a real prompt" in kept, str(kept)[:200])
    check("injected records are counted", skips["injected"] == 5, str(skips))
    check("acknowledgements are counted", skips["acknowledgement"] == 1, str(skips))

    # A tool-bearing record between a notification and the next assistant text
    # means the agent did real work — its short conclusion is a report the
    # successor needs, not the notification's ack (review finding: it was
    # being dropped unrecoverably). Pure harness records leave the pair intact.
    tool_use_record = {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {"command": "true"}}]}}
    tool_result_record = {"type": "user", "message": {"content": [
        {"type": "tool_result", "content": "ran"}]}}
    interleaved = [
        user_record("fix the bug please"),
        user_record(notification_text),
        tool_use_record,
        tool_result_record,
        assistant_record("Fixed — the null check in parse() was inverted. Tests pass."),
        user_record(notification_text),
        {"type": "queue-operation", "operation": "enqueue"},
        {"type": "system", "content": "notice"},
        assistant_record("Routine — noted. On watch."),
    ]
    path = write_transcript(workspace, "interleaved.jsonl", interleaved)
    turns, skips = extractor.read_dialog_turns(path)
    kept = [turn["text"] for turn in turns]
    check("a short real conclusion after tool work survives",
          any(text.startswith("Fixed —") for text in kept), str(kept)[:200])
    check("harness records between the pair do not save the ack",
          "Routine — noted. On watch." not in kept, str(kept)[:200])

    # "message": null appears on some harness record types; both content
    # readers must survive it (review finding: this crashed extraction).
    null_message = [
        user_record("real prompt"),
        user_record(notification_text),
        {"type": "progress", "message": None},
        {"type": "user", "message": None},
        assistant_record("Routine ack after a null-message record."),
    ]
    path = write_transcript(workspace, "null-message.jsonl", null_message)
    turns, skips = extractor.read_dialog_turns(path)
    check("a null message field does not crash extraction",
          [t["text"] for t in turns] == ["real prompt"], str(turns)[:200])

    # --- Short trailing handoff fragments are trimmed ----------------------
    tail_fragment = [
        user_record("penultimate prompt"),
        assistant_record(" ".join(["substantive"] * 100)),
        user_record("handoff please"),
        assistant_record("Writing the successor's first-action prompt:"),
    ]
    path = write_transcript(workspace, "tail-fragment.jsonl", tail_fragment)
    turns, _ = extractor.read_dialog_turns(path)
    selected, start = extractor.select_tail_clearing_floor(turns, 10)
    check("short dangling handoff fragment is trimmed",
          selected[-1]["text"] == "handoff please",
          selected[-1]["text"][:60])

    fragment_output = Path(workspace) / "fragment-out.md"
    exit_code = extractor.main(["--transcript-path", str(path),
                                "--minimum-words", "10",
                                "--output", str(fragment_output)])
    fragment_text = fragment_output.read_text(encoding="utf-8")
    check("header reports the trimmed fragment count",
          "Trimmed from the end: 1 short agent turn(s)" in fragment_text,
          fragment_text[:400])

    # argparse refuses via SystemExit(2); catch it so the suite survives.
    try:
        exit_code = extractor.main(["--transcript-path", str(path), "--minimum-words", "0"])
    except SystemExit as refusal:
        exit_code = refusal.code
    check("a zero word floor refuses with exit 2 instead of crashing",
          exit_code == 2, f"got {exit_code}")

    solid_tail = [
        user_record("a prompt"),
        assistant_record(" ".join(["substantive"] * 100)),
    ]
    path = write_transcript(workspace, "solid-tail.jsonl", solid_tail)
    turns, _ = extractor.read_dialog_turns(path)
    selected, _ = extractor.select_tail_clearing_floor(turns, 10)
    check("a substantive final answer survives the trim",
          selected[-1]["text"].startswith("substantive"), selected[-1]["text"][:40])

    # --- Companion file: the complete filtered dialog ----------------------
    long_session = []
    for chapter in range(10):
        long_session.append(user_record(f"chapter {chapter} question"))
        long_session.append(assistant_record(" ".join([f"chapter{chapter}"] * 300)))
    path = write_transcript(workspace, "companion-source.jsonl", long_session)
    tail_output = Path(workspace) / "seat-dialog-0003.md"
    exit_code = extractor.main(["--transcript-path", str(path), "--output", str(tail_output)])
    companion_output = Path(workspace) / "seat-dialog-0003-complete.md"
    check("companion extraction exits 0", exit_code == 0, f"got {exit_code}")
    check("companion file is written when turns are left behind",
          companion_output.is_file())
    check("companion carries every dialog turn",
          companion_output.read_text(encoding="utf-8").count("\n## ") == 20,
          companion_output.read_text(encoding="utf-8").count("\n## "))
    tail_text = tail_output.read_text(encoding="utf-8")
    check("extract points at the companion", str(companion_output) in tail_text)
    check("extract names thinking in the transcript pointer", "thinking" in tail_text)
    check("extract header counts only real turns", " of 20 (" in tail_text, tail_text[:300])

    whole_session = ordinary_records()[:-1] + [assistant_record(" ".join(["closing"] * 80))]
    path = write_transcript(workspace, "whole-session.jsonl", whole_session)
    whole_output = Path(workspace) / "whole-out.md"
    extractor.main(["--transcript-path", str(path), "--output", str(whole_output)])
    check("no companion when the whole dialog is carried",
          not (Path(workspace) / "whole-out-complete.md").exists())

    # --- Tolerance: malformed line skipped and counted --------------------
    path = write_transcript(
        workspace, "malformed.jsonl", ordinary_records(),
        trailing_raw_lines=['{"type": "user", "message": BROKEN}\n', json.dumps(user_record("after the break")) + "\n"],
    )
    turns, skips = extractor.read_dialog_turns(path)
    check("malformed line is skipped", skips["malformed"] == 1, str(skips))
    check("reading continues past a malformed line", turns[-1]["text"] == "after the break", turns[-1]["text"])

    # --- Tolerance: partial final record ----------------------------------
    path = write_transcript(
        workspace, "partial.jsonl", ordinary_records(),
        trailing_raw_lines=['{"type": "user", "message": {"content": "cut off mid-writ'],
    )
    turns, skips = extractor.read_dialog_turns(path)
    check("partial final record is counted separately", skips["partial_final_record"] == 1, str(skips))
    check("partial final record is not fatal", len(turns) == 6, f"got {len(turns)}")

    # --- Tolerance: oversized record bounded ------------------------------
    giant = user_record("x" * (extractor.MAXIMUM_RECORD_BYTES + 100))
    path = write_transcript(workspace, "oversized.jsonl", [giant, *ordinary_records()])
    turns, skips = extractor.read_dialog_turns(path)
    check("oversized record is skipped by size", skips["oversized"] == 1, str(skips))
    check("oversized record does not defeat extraction", len(turns) == 6, f"got {len(turns)}")

    # --- Refusals ---------------------------------------------------------
    path = write_transcript(workspace, "empty.jsonl", [])
    exit_code = extractor.main(["--transcript-path", str(path), "--last-turns", "3"])
    check("empty transcript refuses with exit 4", exit_code == 4, f"got {exit_code}")

    path = write_transcript(workspace, "garbage.jsonl", [], trailing_raw_lines=["not json at all\n", "still not\n"])
    exit_code = extractor.main(["--transcript-path", str(path), "--last-turns", "3"])
    check("unparseable transcript refuses with exit 4", exit_code == 4, f"got {exit_code}")

    exit_code = extractor.main(["--transcript-path", str(Path(workspace) / "absent.jsonl"), "--last-turns", "3"])
    check("absent transcript reports exit 3", exit_code == 3, f"got {exit_code}")

    # --- Recovery mode and rendering --------------------------------------
    path = write_transcript(workspace, "recovery.jsonl", ordinary_records())
    output_path = Path(workspace) / "extraction.md"
    exit_code = extractor.main(
        ["--transcript-path", str(path), "--last-turns", "3", "--output", str(output_path)]
    )
    rendered = output_path.read_text(encoding="utf-8")
    check("recovery mode exits 0", exit_code == 0, f"got {exit_code}")
    check("recovery mode carries exactly N turns", rendered.count("\n## ") == 3, rendered.count("\n## "))
    check("extraction points at the full transcript", str(path) in rendered)
    check("extraction labels both voices", "## User" in rendered and "## Agent" in rendered)

    # --- Cross-directory id lookup ----------------------------------------
    elsewhere_session_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    projects_root = Path(workspace) / "projects"
    (projects_root / "-Some-Other-Worktree").mkdir(parents=True)
    write_transcript(
        projects_root / "-Some-Other-Worktree", f"{elsewhere_session_id}.jsonl", ordinary_records()
    )
    original_root = extractor.PROJECTS_ROOT
    try:
        extractor.PROJECTS_ROOT = projects_root
        found = extractor.find_transcript_path(
            elsewhere_session_id, Path("/Users/someone/Projects/elsewhere")
        )
        check(
            "finds a transcript in another project directory",
            found.name == f"{elsewhere_session_id}.jsonl",
            str(found),
        )

        try:
            extractor.find_transcript_path("ffffffff-0000-0000-0000-000000000000", Path("/nowhere"))
            check("missing session reports a problem", False, "no exception raised")
        except extractor.TranscriptProblem:
            check("missing session reports a problem", True)
    finally:
        extractor.PROJECTS_ROOT = original_root

    check(
        "keyed lookup mangles the worktree path",
        extractor.project_directory_for_working_directory(Path("/Users/el/Projects/nedschorus")).name
        == "-Users-el-Projects-nedschorus",
        extractor.project_directory_for_working_directory(Path("/Users/el/Projects/nedschorus")).name,
    )

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
