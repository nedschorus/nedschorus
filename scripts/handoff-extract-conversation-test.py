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

    # A message typed mid-turn and then interrupted is persisted twice: the
    # queued_command attachment, and a plain user record when the harness
    # re-sends it after the interrupt (field specimen 2026-08-12: four records
    # and 5.7 seconds apart). The extract carries it once, and the short
    # answer that follows is the reply to it, not an acknowledgement of the
    # interrupt.
    resent_after_interrupt = [
        user_record("first prompt"),
        assistant_record("working on it"),
        queued("stop. I think another session is duplicating your work."),
        {"type": "user", "message": {"content": [{"type": "text", "text": "[Request interrupted by user]"}]}},
        {"type": "queue-operation", "operation": "dequeue"},
        user_record("stop. I think another session is duplicating your work."),
        assistant_record("Stopping."),
    ]
    path = write_transcript(workspace, "resent-after-interrupt.jsonl", resent_after_interrupt)
    turns, skips = extractor.read_dialog_turns(path)
    kept = [(turn["voice"], turn["text"]) for turn in turns]
    check(
        "a mid-turn message the harness re-sends after an interrupt is carried "
        "once, and the short answer after it survives",
        kept == [("user", "first prompt"), ("assistant", "working on it"),
                 ("user", "stop. I think another session is duplicating your work."),
                 ("assistant", "Stopping.")]
        and skips["resent_after_interrupt"] == 1,
        f"{kept} skips={skips}",
    )

    # Scope guard (passes with or without the de-duplication): the same short
    # answer twice with NO interrupt between is two replies — field shape
    # 2026-08-24, "y" approving item 1 of a walk, then "y" approving item 2,
    # 25 records and 121 seconds apart.
    two_approvals = [
        user_record("walk me through the items"),
        assistant_record("Item 1: rename the flag. Approve?"),
        queued("y"),
        assistant_record("Item 1 is in and pushed. Item 2: drop the alias. Approve?"),
        user_record("y"),
        assistant_record("Item 2 is in."),
    ]
    path = write_transcript(workspace, "two-approvals.jsonl", two_approvals)
    turns, _ = extractor.read_dialog_turns(path)
    kept = [turn["text"] for turn in turns]
    check(
        "the same short answer twice with no interrupt between is two replies, both carried",
        kept == ["walk me through the items", "Item 1: rename the flag. Approve?", "y",
                 "Item 1 is in and pushed. Item 2: drop the alias. Approve?", "y", "Item 2 is in."],
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

    # --- Slash commands typed with words ----------------------------------
    # The record shapes are copied from real transcripts: a skill command
    # (merge-lane, 2026-09-01T03:16:53Z — queued while the agent worked, then
    # delivered as a tagged user record followed by the skill's isMeta body),
    # a built-in command (opens with <command-name>, indented, answered by
    # local-command-stdout), and commands with no words. Before the fix every
    # one of them was dropped as injected, words included.
    typed_words = "what is standing with me. or any other qeustions"
    slash = [
        {"type": "queue-operation", "operation": "enqueue",
         "content": f"/walk-me-through {typed_words}"},
        user_record("<command-message>walk-me-through</command-message>\n"
                    "<command-name>/walk-me-through</command-name>\n"
                    f"<command-args>{typed_words}</command-args>",
                    origin={"kind": "human"}),
        user_record([{"type": "text", "text": "Base directory for this skill: "
                      "/x/.claude/skills/walk-me-through\n\n# Walk me through"}],
                    isMeta=True),
        assistant_record("Item 1 of 3: the first thing standing with you"),
        user_record("<command-name>/model</command-name>\n"
                    "            <command-message>model</command-message>\n"
                    "            <command-args>opus</command-args>"),
        user_record("<local-command-stdout>Set model to opus</local-command-stdout>"),
        user_record("<command-message>handoff</command-message>\n"
                    "<command-name>/handoff</command-name>",
                    origin={"kind": "human"}),
        user_record("<command-name>/compact</command-name>\n"
                    "            <command-message>compact</command-message>\n"
                    "            <command-args></command-args>"),
        user_record("<command-message>walk-me-through</command-message>\n"
                    "<command-name>/walk-me-through</command-name>\n"
                    "<command-args>these - 1 did you measure</command-args>"),
        user_record("<command-message>walk-me-through</command-message>\n"
                    "<command-name>/walk-me-through</command-name>\n"
                    "<command-args>sent by another seat</command-args>",
                    origin={"kind": "peer"}),
        {"type": "attachment", "attachment": {
            "type": "queued_command", "origin": {"kind": "human"},
            "prompt": "Still confused. /walk-me-through item 3"}},
        assistant_record("Item 3, retold as one story"),
    ]
    path = write_transcript(workspace, "slash.jsonl", slash)
    turns, skips = extractor.read_dialog_turns(path)
    kept = [turn["text"] for turn in turns]
    users = [turn["text"] for turn in turns if turn["voice"] == "user"]
    check("a skill command's words are carried as one user turn",
          users.count(f"/walk-me-through {typed_words}") == 1, str(users))
    check("a built-in command's words are carried",
          "/model opus" in users, str(users))
    check("a command recorded before origin existed is carried",
          "/walk-me-through these - 1 did you measure" in users, str(users))
    check("the skill's expanded body stays out",
          not any("Base directory for this skill" in text for text in kept), str(kept)[:200])
    check("a command with no words stays out",
          not any(text.startswith(("/handoff", "/compact", "<command-")) for text in kept),
          str(kept))
    check("a command of non-human origin stays out",
          not any("sent by another seat" in text for text in kept), str(kept))
    check("a slash command inside a queued message is carried once",
          users.count("Still confused. /walk-me-through item 3") == 1, str(users))
    check("the queued copy of a command is not carried a second time",
          sum(typed_words in text for text in kept) == 1, str(kept))
    check("the answer to a carried command survives",
          "Item 1 of 3: the first thing standing with you" in kept, str(kept))
    check("bare, non-human and stdout records are counted as injected",
          skips["injected"] == 4, str(skips))

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

# --- Subagent tasks and reports: the third voice -------------------------
# Each fixture is a small, anonymised copy of a shape found in the Mac's and
# ned-box's transcripts: every copy the harness writes of one report is kept,
# so the cases show each report carried once.


def agent_call(tool_use_id, description, prompt, **extra):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": tool_use_id, "name": "Agent",
         "input": {"description": description, "prompt": prompt, **extra}}]}}


def tool_call(tool_use_id, name, tool_input):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": tool_use_id, "name": name, "input": tool_input}]}}


def launched(tool_use_id, agent_id):
    text = (f"Async agent launched successfully.\nagentId: {agent_id} (internal ID)\n"
            "The agent is working in the background.")
    return {"type": "user",
            "message": {"content": [{"type": "tool_result", "tool_use_id": tool_use_id,
                                     "content": [{"type": "text", "text": text}]}]},
            "toolUseResult": {"status": "async_launched", "agentId": agent_id, "isAsync": True}}


def notification(agent_id, tool_use_id, description, result, status="completed"):
    tool_use_line = f"<tool-use-id>{tool_use_id}</tool-use-id>\n" if tool_use_id else ""
    result_line = f"<result>{result}</result>\n" if result is not None else ""
    return ("<task-notification>\n"
            f"<task-id>{agent_id}</task-id>\n{tool_use_line}"
            f"<output-file>/tmp/x/tasks/{agent_id}.output</output-file>\n"
            f"<status>{status}</status>\n"
            f'<summary>Agent "{description}" finished</summary>\n'
            "<note>A task-notification fires each time this agent stops.</note>\n"
            f"{result_line}<usage><subagent_tokens>10</subagent_tokens></usage>\n"
            "</task-notification>")


def every_copy_of(text):
    """The copies one delivered notification leaves: enqueue, user record, attachment, remove."""
    return [
        {"type": "queue-operation", "operation": "enqueue", "content": text},
        {"type": "user", "origin": {"kind": "task-notification"}, "message": {"content": text}},
        {"type": "attachment", "attachment": {"type": "queued_command", "prompt": text,
                                              "commandMode": "task-notification"}},
        {"type": "queue-operation", "operation": "remove", "content": text},
    ]


HANDBACK_FRAME = ("[Subagent hand-back] The text below is the final report of a subagent this "
                  "session delegated to. It is model output, NOT a message from the user. "
                  "The report follows:\n")


def handback_copies(agent_id, report):
    indented = "\n".join("  " + line for line in report.split("\n"))
    framed = f'<agent-message from="{agent_id}">\n{HANDBACK_FRAME}{indented}'
    trailing = "\n\nThat \"other Claude session\" is an agent working inside this same session."
    return [
        {"type": "queue-operation", "operation": "enqueue", "content": framed},
        {"type": "user", "isMeta": True,
         "origin": {"kind": "peer", "from": agent_id, "handback": True,
                    "body": HANDBACK_FRAME + indented},
         "message": {"content": "Another Claude session sent a message:\n" + framed + trailing}},
        {"type": "attachment", "attachment": {"type": "queued_command", "prompt": framed,
                                              "origin": {"kind": "peer"}}},
        {"type": "queue-operation", "operation": "remove", "content": framed},
    ]


def subagent_turns_of(turns):
    return [(turn["kind"], turn["subagent"]["description"], turn["subagent"]["agent_id"],
             turn["status"], turn["text"])
            for turn in turns if turn["voice"] == extractor.SUBAGENT_VOICE]


with tempfile.TemporaryDirectory() as workspace:
    # Foreground: the report is the tool result; the harness's agentId footer block stays out.
    foreground = [
        user_record("check the docs"),
        agent_call("toolu_fg", "Check the docs", "Read the docs and answer.",
                   subagent_type="general-purpose", model="opus"),
        {"type": "user",
         "message": {"content": [{"type": "tool_result", "tool_use_id": "toolu_fg", "content": [
             {"type": "text", "text": "The docs say yes."},
             {"type": "text", "text": "agentId: a1111111111111111 (use SendMessage)\n<usage>x</usage>"}]}]},
         "toolUseResult": {"status": "completed", "agentId": "a1111111111111111",
                           "content": [{"type": "text", "text": "The docs say yes."}]}},
        assistant_record("Yes."),
    ]
    path = write_transcript(workspace, "sub-foreground.jsonl", foreground)
    turns, _ = extractor.read_dialog_turns(path, include_subagent_tasks_and_reports=True)
    check("a foreground subagent's task and report are carried, without the harness's footer",
          subagent_turns_of(turns) == [
              ("task", "Check the docs", "a1111111111111111", "", "Read the docs and answer."),
              ("report", "Check the docs", "a1111111111111111", "completed", "The docs say yes.")],
          subagent_turns_of(turns))
    check("the subagent turns sit between the dialog turns they came between",
          [turn["voice"] for turn in turns] == ["user", "subagent", "subagent", "assistant"],
          [turn["voice"] for turn in turns])
    plain_turns, _ = extractor.read_dialog_turns(path)
    check("read_dialog_turns without the flag keeps the two voices its other callers expect",
          [turn["voice"] for turn in plain_turns] == ["user", "assistant"],
          [turn["voice"] for turn in plain_turns])

    # Foreground hand-back: the report reaches the transcript before the tool result that names the agent.
    handback_report = "Verdict: approve.\n\n- one finding, minor"
    foreground_handback = [
        user_record("review it"),
        agent_call("toolu_fh", "Review the pull request", "Review it.", subagent_type="claude",
                   run_in_background=False),
        *handback_copies("a2222222222222222", handback_report)[:1],
        {"type": "user",
         "message": {"content": [{"type": "tool_result", "tool_use_id": "toolu_fh", "content": [
             {"type": "text", "text": "  This agent's report was delivered to you as a message from "
                                      "\"a2222222222222222\" (its SubagentHandback call)."}]}]},
         "toolUseResult": {"status": "completed", "agentId": "a2222222222222222", "handback": "send",
                           "handbackReport": {"text": handback_report},
                           "content": [{"type": "text", "text": "This agent's report was delivered "
                                                                "to you as a message."}]}},
        *handback_copies("a2222222222222222", handback_report)[2:],
        assistant_record("Approved."),
    ]
    path = write_transcript(workspace, "sub-foreground-handback.jsonl", foreground_handback)
    turns, _ = extractor.read_dialog_turns(path, include_subagent_tasks_and_reports=True)
    check("a foreground hand-back is carried once, unframed and unindented, under its task's description",
          subagent_turns_of(turns) == [
              ("task", "Review the pull request", "a2222222222222222", "", "Review it."),
              ("report", "Review the pull request", "a2222222222222222", "completed", handback_report)],
          subagent_turns_of(turns))

    # Background: a launch notice, then one notification written four times; the short reply after it is dialog.
    background = [
        user_record("run the review in the background"),
        agent_call("toolu_bg", "Background review", "Review in the background.",
                   subagent_type="fork", run_in_background=True, isolation="worktree"),
        launched("toolu_bg", "a3333333333333333"),
        assistant_record("Started."),
        *every_copy_of(notification("a3333333333333333", "toolu_bg", "Background review",
                                    "Two findings, both fixed.")),
        assistant_record("Both fixed; merging."),
    ]
    path = write_transcript(workspace, "sub-background.jsonl", background)
    turns, skips = extractor.read_dialog_turns(path, include_subagent_tasks_and_reports=True)
    check("a background subagent's launch notice is dropped and its report carried once",
          subagent_turns_of(turns) == [
              ("task", "Background review", "a3333333333333333", "", "Review in the background."),
              ("report", "Background review", "a3333333333333333", "completed",
               "Two findings, both fixed.")],
          subagent_turns_of(turns))
    check("the agent's short reply to a carried report is kept, not dropped as an acknowledgement",
          turns[-1]["text"] == "Both fixed; merging." and skips["acknowledgement"] == 0,
          (turns[-1]["text"], skips))
    acknowledged_turns, _ = extractor.read_dialog_turns(path)
    check("without the flag the reply after a notification is still an acknowledgement",
          "Both fixed; merging." not in [turn["text"] for turn in acknowledged_turns],
          [turn["text"] for turn in acknowledged_turns])
    rendered_task = "".join(extractor.render_turn(turns[1], extractor.ExtractionReport(
        "s", path, "", 0, len(turns), {})))
    check("a task's heading names the description, and its facts line the agent and how it ran",
          "## Subagent task — Background review" in rendered_task
          and "(agent a3333333333333333, fork, background, isolation worktree)" in rendered_task,
          rendered_task)

    # Background hand-back, then a SendMessage that continues the same agent and its second report.
    background_handback = [
        user_record("ask the guide"),
        agent_call("toolu_bh", "Ask the guide", "What does the hook do?",
                   subagent_type="claude-code-guide"),
        launched("toolu_bh", "a4444444444444444"),
        *handback_copies("a4444444444444444", "It fires after compaction."),
        *every_copy_of(notification("a4444444444444444", "toolu_bh", "Ask the guide",
                                    "This agent's report was delivered to you as a message from "
                                    "\"a4444444444444444\" (its SubagentHandback call).")),
        tool_call("toolu_send", "SendMessage", {"to": "a4444444444444444", "summary": "settle it",
                                                "message": "Your answer contradicts itself.",
                                                "type": "message", "recipient": "a4444444444444444",
                                                "content": "Your answer contradicts…"}),
        *handback_copies("a4444444444444444", "It fires; the turn does not continue."),
        *every_copy_of(notification("a4444444444444444", "toolu_send", "Ask the guide",
                                    "This agent's report was delivered to you as a message.")),
        tool_call("toolu_peer", "SendMessage", {"to": "merge-lane", "message": "not a subagent"}),
        {"type": "user", "isMeta": True, "origin": {"kind": "peer", "from": "bridge:session_x"},
         "message": {"content": '<agent-message from="bridge:session_x">\nhello from a peer\n'
                                '</agent-message>'}},
    ]
    path = write_transcript(workspace, "sub-background-handback.jsonl", background_handback)
    turns, _ = extractor.read_dialog_turns(path, include_subagent_tasks_and_reports=True)
    check("a background hand-back and its continuation carry the task, both reports and the "
          "follow-up, and the pointer-only notifications stay out",
          subagent_turns_of(turns) == [
              ("task", "Ask the guide", "a4444444444444444", "", "What does the hook do?"),
              ("report", "Ask the guide", "a4444444444444444", "completed", "It fires after compaction."),
              ("follow-up", "Ask the guide", "a4444444444444444", "", "Your answer contradicts itself."),
              ("report", "Ask the guide", "a4444444444444444", "completed",
               "It fires; the turn does not continue.")],
          subagent_turns_of(turns))
    check("a SendMessage to a peer and an agent-message from one are not subagent turns",
          not any("peer" in text or "not a subagent" in text
                  for *_, text in subagent_turns_of(turns)),
          subagent_turns_of(turns))

    # A running subagent's message to its session, a failure, an agent from a previous session,
    # and an Agent call the harness refused.
    progress = [
        user_record("start the fix"),
        agent_call("toolu_fix", "Fix round", "Fix the findings.", subagent_type="fork"),
        launched("toolu_fix", "a5555555555555555"),
        {"type": "queue-operation", "operation": "enqueue",
         "content": '<agent-message from="a5555555555555555">\nQueued for the test lock.\n</agent-message>'},
        {"type": "user", "isMeta": True,
         "origin": {"kind": "peer", "from": "a5555555555555555", "body": "Queued for the test lock."},
         "message": {"content": 'Another Claude session sent a message:\n<agent-message '
                                'from="a5555555555555555">\nQueued for the test lock.\n</agent-message>'}},
        *every_copy_of(notification("a5555555555555555", "toolu_fix", "Fix round", None, status="failed")),
        {"type": "queue-operation", "operation": "enqueue",
         "content": "<task-notification>\n<task-id>a6666666666666666</task-id>\n<status>killed</status>\n"
                    '<summary>Background agent "Earlier review" didn\'t finish before the previous '
                    "session ended</summary>\n</task-notification>"},
        agent_call("toolu_denied", "Denied canary", "Read a file."),
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "toolu_denied", "is_error": True,
             "content": "Permission for this action was denied."}]}},
    ]
    path = write_transcript(workspace, "sub-progress.jsonl", progress)
    turns, _ = extractor.read_dialog_turns(path, include_subagent_tasks_and_reports=True)
    kept = subagent_turns_of(turns)
    check("a running subagent's message to its session is carried once",
          [entry for entry in kept if entry[0] == "message"]
          == [("message", "Fix round", "a5555555555555555", "", "Queued for the test lock.")], kept)
    check("a failed report with no result carries its status and the notification's summary",
          ("report", "Fix round", "a5555555555555555", "failed", 'Agent "Fix round" finished') in kept, kept)
    check("a subagent from a previous session is reported under the description its notification names",
          ("report", "Earlier review", "a6666666666666666", "killed",
           'Background agent "Earlier review" didn\'t finish before the previous session ended') in kept,
          kept)
    check("an Agent call the harness refused is reported as an error with the refusal",
          ("report", "Denied canary", "", "error", "Permission for this action was denied.") in kept, kept)

    # A skill run as a fork, and a workflow, whose result is its script's return value in JSON.
    fork_and_workflow = [
        user_record("review and probe"),
        tool_call("toolu_skill", "Skill", {"skill": "code-review", "args": "--effort high"}),
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "toolu_skill",
             "content": "Skill \"code-review\" launched (forked execution, running in the background)."}]},
         "toolUseResult": {"success": True, "commandName": "code-review", "status": "forked",
                           "background": True, "agentId": "a7777777777777777"}},
        *every_copy_of(notification("a7777777777777777", "", "code-review", "No bugs found.")),
        tool_call("toolu_wf", "Workflow", {"script": "export const meta = { name: 'probe', "
                                                     "description: 'Probe the shell' }\nreturn 1"}),
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "toolu_wf",
             "content": "Workflow launched in background. Task ID: w8888"}]},
         "toolUseResult": {"status": "async_launched", "taskId": "w8888", "runId": "wf_1",
                           "summary": "Probe the shell", "workflowName": "probe"}},
        {"type": "queue-operation", "operation": "enqueue",
         "content": "<task-notification>\n<task-id>w8888</task-id>\n<tool-use-id>toolu_wf</tool-use-id>\n"
                    "<status>completed</status>\n<summary>Dynamic workflow \"Probe the shell\" "
                    "completed</summary>\n<result>\"NO_SHELL_TOOL\\nEdit\"</result>\n"
                    "</task-notification>"},
        tool_call("toolu_wf2", "Workflow", {"script": "export const meta = { description: 'Second' }"}),
        {"type": "queue-operation", "operation": "enqueue",
         "content": "<task-notification>\n<task-id>w9999</task-id>\n<tool-use-id>toolu_wf2</tool-use-id>\n"
                    "<status>completed</status>\n<summary>Dynamic workflow \"Second\" completed</summary>\n"
                    "<result>\"not JSON after all</result>\n</task-notification>"},
    ]
    path = write_transcript(workspace, "sub-fork-workflow.jsonl", fork_and_workflow)
    turns, _ = extractor.read_dialog_turns(path, include_subagent_tasks_and_reports=True)
    kept = subagent_turns_of(turns)
    check("a skill run as a fork is a task named for the skill, and its report is carried",
          kept[:2] == [("task", "/code-review", "a7777777777777777", "", "--effort high"),
                       ("report", "/code-review", "a7777777777777777", "completed", "No bugs found.")],
          kept)
    check("a workflow's task is its script and its report is its decoded return value",
          kept[2:4] == [("task", "Probe the shell", "w8888", "",
                         "export const meta = { name: 'probe', description: 'Probe the shell' }\nreturn 1"),
                        ("report", "Probe the shell", "w8888", "completed", "NO_SHELL_TOOL\nEdit")],
          kept)
    check("a workflow result that only looks like JSON is carried as it is",
          kept[4:] == [("task", "Second", "", "", "export const meta = { description: 'Second' }"),
                       ("report", "Second", "", "completed", '"not JSON after all')],
          kept)
    workflow_report = turns[[turn["text"] for turn in turns].index("NO_SHELL_TOOL\nEdit")]
    check("a workflow's own transcripts are found under subagents/workflows/<run id>/",
          extractor.subagent_transcript_path(workflow_report["subagent"], extractor.ExtractionReport(
              "s", path, "", 0, 0, {})) == path.with_suffix("") / "subagents" / "workflows" / "wf_1"
          / "journal.jsonl")

    # The tail cuts a long subagent text and says where the whole is; the complete dialog keeps it whole.
    long_report = "\n".join(f"line {number} " + "word " * 9 for number in range(400))
    long_session = [user_record("opening question"), assistant_record(" ".join(["ancient"] * 1200)),
                    user_record("first question"), assistant_record(" ".join(["early"] * 1200)),
                    user_record("dispatch it"),
                    agent_call("toolu_long", "Long job", "Do the long job."),
                    launched("toolu_long", "a9999999999999999"),
                    *every_copy_of(notification("a9999999999999999", "toolu_long", "Long job", long_report)),
                    assistant_record(" ".join(["closing"] * 80))]
    path = write_transcript(workspace, "sub-long.jsonl", long_session)
    output_path = Path(workspace) / "seat-dialog-0007.md"
    exit_code = extractor.main(["--transcript-path", str(path), "--output", str(output_path)])
    tail_text = output_path.read_text(encoding="utf-8")
    complete_text = output_path.with_name("seat-dialog-0007-complete.md").read_text(encoding="utf-8")
    check("subagent words do not count toward the word floor, so the tail still reaches back "
          "for the dialog it needs",
          exit_code == 0 and "early early" in tail_text and "ancient" not in tail_text,
          tail_text[:600])
    check("the tail cuts a subagent text over the limit and names the session's and the "
          "subagent's transcripts",
          "line 399" not in tail_text and "[Cut here: " in tail_text and str(path) in tail_text
          and str(path.with_suffix("") / "subagents" / "agent-a9999999999999999.jsonl") in tail_text,
          tail_text[-900:])
    check("the complete dialog keeps the long subagent text whole",
          "line 399" in complete_text and "[Cut here" not in complete_text)
    check("both files count the subagent turns apart from the words, and point at the "
          "subagents' transcripts",
          "2 subagent turns, not counted in the words" in tail_text
          and "2 subagent turns, not counted in the words" in complete_text
          and "/subagents/agent-<agent id>.jsonl" in tail_text
          and "/subagents/agent-<agent id>.jsonl" in complete_text,
          tail_text[:500])

    # The rolling session dialog renders even a transcript with no dialog in it.
    path = write_transcript(workspace, "no-dialog.jsonl", [{"type": "system", "content": "x"}])
    check("the complete dialog of a transcript with no dialog says it holds no turns",
          "All 0 dialog turns" in extractor.render_complete_dialog_of_transcript_as_markdown(path))

# Fix-round cases: a repeated report after a SendMessage, the interim notice, and the tail's shared budget.
with tempfile.TemporaryDirectory() as workspace:
    # Two reviews by one agent, the second after a SendMessage, that both report the same words.
    repeated = [
        user_record("review it twice"),
        agent_call("toolu_rv", "Review", "Review the change."),
        launched("toolu_rv", "a1212121212121212"),
        *every_copy_of(notification("a1212121212121212", "toolu_rv", "Review", "No findings.")),
        tool_call("toolu_again", "SendMessage", {"to": "a1212121212121212", "message": "Review the fix."}),
        *every_copy_of(notification("a1212121212121212", "toolu_again", "Review", "No findings.")),
        assistant_record("Clean twice."),
    ]
    path = write_transcript(workspace, "sub-repeated.jsonl", repeated)
    turns, _ = extractor.read_dialog_turns(path, include_subagent_tasks_and_reports=True)
    check("an identical report after a SendMessage to the same agent is a new report, carried again, "
          "while each report's four copies are carried once",
          [kind for kind, *_ in subagent_turns_of(turns)] == ["task", "report", "follow-up", "report"],
          subagent_turns_of(turns))

    # A subagent waiting on its own background work: the interim notice is not its report.
    interim = ("This agent has not reported yet: it is waiting on its own background work and will "
               "deliver its report through SubagentHandback when that finishes.")
    waiting = [
        user_record("start the long job"),
        agent_call("toolu_wait", "Long job", "Run it."),
        launched("toolu_wait", "a1313131313131313"),
        *every_copy_of(notification("a1313131313131313", "toolu_wait", "Long job", interim)),
        assistant_record("Waiting."),
        *handback_copies("a1313131313131313", "Done: all green."),
    ]
    path = write_transcript(workspace, "sub-interim.jsonl", waiting)
    turns, skips = extractor.read_dialog_turns(path, include_subagent_tasks_and_reports=True)
    check("the interim notice of a subagent still waiting is not carried as its report; the real report is",
          [(kind, text) for kind, _, _, _, text in subagent_turns_of(turns)]
          == [("task", "Run it."), ("report", "Done: all green.")],
          subagent_turns_of(turns))
    check("the agent's reply to an interim notice is kept, not dropped as an acknowledgement",
          "Waiting." in [turn["text"] for turn in turns] and skips["acknowledgement"] == 0,
          ([turn["text"] for turn in turns], skips))

    # The tail's subagent texts share one budget, newest first; each keeps at least the minimum.
    def words(label, count):
        return " ".join([label] * count)
    budget_session = [user_record("dispatch three"),
                      agent_call("toolu_b1", "First", words("first", 900)),
                      agent_call("toolu_b2", "Second", words("second", 900)),
                      agent_call("toolu_b3", "Third", words("third", 300)),
                      assistant_record(words("closing", 80))]
    path = write_transcript(workspace, "sub-budget.jsonl", budget_session)
    turns, skips = extractor.read_dialog_turns(path, include_subagent_tasks_and_reports=True)
    tail_text = extractor.render_extraction(turns, extractor.ExtractionReport(
        "s", path, "", 0, len(turns), skips))
    check("the newest subagent text in the tail is whole, the next takes what the budget leaves, "
          "and the oldest keeps the minimum, each cut one saying where the whole text is",
          tail_text.count("third") == 300
          and tail_text.count("second") == extractor.SUBAGENT_TAIL_WORDS_IN_ALL - 300
          and tail_text.count("first") == extractor.MINIMUM_SUBAGENT_TAIL_WORDS
          and tail_text.count("[Cut here: ") == 2,
          (tail_text.count("third"), tail_text.count("second"), tail_text.count("first")))
    complete_text = extractor.render_companion(turns, extractor.ExtractionReport(
        "s", path, "", 0, len(turns), skips))
    check("the complete dialog keeps every subagent text whole",
          complete_text.count("first") == 900 and complete_text.count("second") == 900
          and "[Cut here" not in complete_text)

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
