#!/usr/bin/env python3
"""Tests for handoff-extract-conversation-subagent-tracker-nbd.py, through the extractor that loads it.

Run: python3 scripts/handoff-extract-conversation-subagent-tracker-nbd-test.py
Prints one line per case and exits non-zero if any case fails.

Every case builds its own transcript in a temporary directory, so the tests
never read a real session and never touch ~/.claude.
"""

import contextlib
import importlib.util
import io
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

    # A subagent's own Agent call and its result, carried inline as sidechain records, are not this session's.
    sidechain_call = agent_call("toolu_side", "Nested look", "Look deeper.")
    sidechain_call["isSidechain"] = True
    sidechain_result = {"type": "user", "isSidechain": True,
                        "message": {"content": [{"type": "tool_result", "tool_use_id": "toolu_side",
                                                 "content": [{"type": "text", "text": "Nested answer."}]}]},
                        "toolUseResult": {"status": "completed", "agentId": "a3333333333333333",
                                          "content": [{"type": "text", "text": "Nested answer."}]}}
    path = write_transcript(workspace, "sub-sidechain.jsonl", foreground[:3] + [sidechain_call, sidechain_result]
                            + foreground[3:])
    turns, _ = extractor.read_dialog_turns(path, include_subagent_tasks_and_reports=True)
    check("a sidechain record's Agent call and result add no subagent turns",
          [description for _, description, _, _, _ in subagent_turns_of(turns)] == ["Check the docs", "Check the docs"],
          subagent_turns_of(turns))

    # The complete dialog's header counts the user's and the agent's words only.
    complete = extractor.render_complete_dialog_of_transcript_as_markdown(
        write_transcript(workspace, "sub-words.jsonl", foreground))
    dialog_words = sum(len(text.split()) for text in ("check the docs", "Yes."))
    check("the complete dialog's word count leaves out the subagent's task and report",
          f"({dialog_words} words; 2 subagent turns, not counted in the words)" in complete,
          complete.split("\n")[2])

    # With an explicit turn count, the turns counted are the user's and the agent's.
    recovery_output = Path(workspace) / "sub-recovery.md"
    recovery_code = extractor.main(["--transcript-path", str(path), "--last-turns", "2",
                                    "--output", str(recovery_output)])
    recovery = recovery_output.read_text(encoding="utf-8")
    check("recovery mode with subagent turns carries the last N dialog turns, no subagent turn among them",
          recovery_code == 0 and "## User\n\ncheck the docs" in recovery and "## Agent\n\nYes." in recovery
          and "Subagent" not in recovery.split("---")[1],
          recovery)

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
    rendered_task = "".join(extractor.render_turn(turns[1]))
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

    # The tail leaves every subagent text out; the complete dialog keeps each one whole.
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
    check("the tail carries no subagent task or report, and no note or pointer about them",
          "line 0 " not in tail_text and "Do the long job." not in tail_text
          and "## Subagent" not in tail_text and "subagent" not in tail_text.replace(
              "every subagent task and report", ""),
          tail_text)
    check("the complete dialog keeps the subagent's task and its long report whole",
          "Do the long job." in complete_text and "line 0 " in complete_text and "line 399" in complete_text)
    check("the complete dialog counts the subagent turns apart from the words, and points at the "
          "subagents' transcripts",
          "2 subagent turns, not counted in the words" in complete_text
          and "/subagents/agent-<agent id>.jsonl" in complete_text,
          complete_text[:500])

    # A session whose whole two-voice dialog fits the tail still gets its complete dialog for its subagent texts.
    short_session = [user_record("dispatch it"), agent_call("toolu_short", "Short job", "Do the short job."),
                     launched("toolu_short", "a9898989898989898"),
                     *every_copy_of(notification("a9898989898989898", "toolu_short", "Short job", "Done.")),
                     assistant_record(" ".join(["closing"] * 80))]
    path = write_transcript(workspace, "sub-short.jsonl", short_session)
    output_path = Path(workspace) / "seat-dialog-0008.md"
    exit_code = extractor.main(["--transcript-path", str(path), "--output", str(output_path)])
    tail_text = output_path.read_text(encoding="utf-8")
    complete_path = output_path.with_name("seat-dialog-0008-complete.md")
    check("a tail that holds the whole two-voice dialog still points at a complete dialog holding the "
          "subagent texts",
          exit_code == 0 and "Turns carried: 2 of 2" in tail_text and "Do the short job." not in tail_text
          and str(complete_path) in tail_text and complete_path.is_file()
          and "Do the short job." in complete_path.read_text(encoding="utf-8"),
          tail_text)

    # A session with subagent turns and no user or agent turn has no dialog to hand over.
    path = write_transcript(workspace, "sub-only.jsonl", [agent_call("toolu_only", "Only", "Only a task.")])
    check("a transcript whose only turns are subagent turns is refused like an empty one",
          extractor.main(["--transcript-path", str(path), "--output", str(Path(workspace) / "only.md")]) == 4)

    # The rolling session dialog renders even a transcript with no dialog in it.
    path = write_transcript(workspace, "no-dialog.jsonl", [{"type": "system", "content": "x"}])
    check("the complete dialog of a transcript with no dialog says it holds no turns",
          "All 0 dialog turns" in extractor.render_complete_dialog_of_transcript_as_markdown(path))

# Fix-round cases: a repeated report after a SendMessage, late copies, and the interim notice.
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

    # One delivery whose later copies the harness writes after a SendMessage to the same agent.
    approved = notification("a1414141414141414", "toolu_late", "Review", "APPROVED.")
    late_copies = [
        user_record("review it"),
        agent_call("toolu_late", "Review", "Review the change."),
        launched("toolu_late", "a1414141414141414"),
        {"type": "queue-operation", "operation": "enqueue", "timestamp": "2026-09-11T23:30:36.982Z",
         "content": approved},
        tool_call("toolu_moved", "SendMessage", {"to": "a1414141414141414", "message": "The head moved."}),
        {"type": "queue-operation", "operation": "remove", "timestamp": "2026-09-11T23:31:01.310Z",
         "reason": "absorbed_mid_turn", "content": approved},
        {"type": "attachment", "timestamp": "2026-09-11T23:30:36.982Z",
         "attachment": {"type": "queued_command", "prompt": approved, "commandMode": "task-notification",
                        "timestamp": "2026-09-11T23:30:36.982Z"}},
        assistant_record("Waiting for the re-review."),
    ]
    path = write_transcript(workspace, "sub-late-copies.jsonl", late_copies)
    turns, _ = extractor.read_dialog_turns(path, include_subagent_tasks_and_reports=True)
    check("copies of one delivery written after a SendMessage to the same agent are not a second report",
          [kind for kind, *_ in subagent_turns_of(turns)] == ["task", "report", "follow-up"],
          subagent_turns_of(turns))

    # The harness stamps an attachment copy up to a few milliseconds off its enqueue's time.
    skewed = [dict(record) for record in late_copies]
    skewed[6] = {"type": "attachment", "timestamp": "2026-09-11T23:30:36.981Z",
                 "attachment": {"type": "queued_command", "prompt": approved,
                                "commandMode": "task-notification", "timestamp": "2026-09-11T23:30:36.981Z"}}
    path = write_transcript(workspace, "sub-late-copies-skewed.jsonl", skewed)
    turns, _ = extractor.read_dialog_turns(path, include_subagent_tasks_and_reports=True)
    check("a late attachment copy whose time is 1 ms off its enqueue's is not a second report",
          [kind for kind, *_ in subagent_turns_of(turns)] == ["task", "report", "follow-up"],
          subagent_turns_of(turns))

    # A second copy of one kind with no enqueue left to match is a delivery of its own.
    again = notification("a1515151515151515", "toolu_twice", "Review", "Still clean.")
    twice = [
        user_record("review it"),
        agent_call("toolu_twice", "Review", "Review the change."),
        launched("toolu_twice", "a1515151515151515"),
        {"type": "queue-operation", "operation": "enqueue", "content": again},
        {"type": "user", "origin": {"kind": "task-notification"}, "message": {"content": again}},
        tool_call("toolu_recheck", "SendMessage", {"to": "a1515151515151515", "message": "Check again."}),
        {"type": "user", "origin": {"kind": "task-notification"}, "message": {"content": again}},
        assistant_record("Clean twice."),
    ]
    path = write_transcript(workspace, "sub-second-copy-of-one-kind.jsonl", twice)
    turns, _ = extractor.read_dialog_turns(path, include_subagent_tasks_and_reports=True)
    check("a second user-record copy after a SendMessage, with no enqueue of its own, is a new report",
          [kind for kind, *_ in subagent_turns_of(turns)] == ["task", "report", "follow-up", "report"],
          subagent_turns_of(turns))

    # A hand-back whose user-record copy lands after a SendMessage to its sender is one report.
    handback = handback_copies("a1616161616161616", "No findings in the fix.")
    late_handback = [
        user_record("review the fix"),
        agent_call("toolu_hb", "Review the fix", "Review it."),
        launched("toolu_hb", "a1616161616161616"),
        handback[0],
        tool_call("toolu_hb_more", "SendMessage", {"to": "a1616161616161616", "message": "One more file."}),
        handback[1], handback[2], handback[3],
        assistant_record("Waiting for the last file."),
    ]
    path = write_transcript(workspace, "sub-late-handback-copy.jsonl", late_handback)
    turns, _ = extractor.read_dialog_turns(path, include_subagent_tasks_and_reports=True)
    check("a hand-back's copies written after a SendMessage to its sender are not a second report",
          [kind for kind, *_ in subagent_turns_of(turns)] == ["task", "report", "follow-up"],
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


# The tracker is nice-but-dirty: when it cannot load or raises, the dialog is written without subagent turns.
with tempfile.TemporaryDirectory() as workspace:
    path = write_transcript(workspace, "tracker-fails.jsonl", foreground)
    output_path = Path(workspace) / "seat-dialog-0001.md"
    original_tracker_path = extractor.subagent_tracker_module_path
    file_stderr, stdout_stderr, stdout_text = io.StringIO(), io.StringIO(), io.StringIO()
    try:
        extractor._subagent_tracker_module = None
        extractor.subagent_tracker_module_path = lambda: Path(workspace) / "no-such-tracker-nbd.py"
        with contextlib.redirect_stderr(file_stderr):
            exit_code = extractor.main(["--transcript-path", str(path), "--output", str(output_path)])
        with contextlib.redirect_stderr(stdout_stderr), contextlib.redirect_stdout(stdout_text):
            stdout_exit_code = extractor.main(["--transcript-path", str(path)])
        complete = extractor.render_complete_dialog_of_transcript_as_markdown(path)
    finally:
        extractor.subagent_tracker_module_path = original_tracker_path
        extractor._subagent_tracker_module = None
    check("a tracker that cannot be loaded leaves the handoff's exit 0 and its tail written",
          exit_code == 0 and output_path.is_file(), exit_code)
    check("a tracker that cannot be loaded is told on stderr, writing to a file or to stdout",
          "subagent tracker" in file_stderr.getvalue() and "FileNotFoundError" in file_stderr.getvalue()
          and stdout_exit_code == 0 and "FileNotFoundError" in stdout_stderr.getvalue()
          and "check the docs" in stdout_text.getvalue(),
          (file_stderr.getvalue(), stdout_stderr.getvalue()))
    check("a tracker that cannot be loaded leaves a note naming the failure in the complete dialog, "
          "and no subagent turn",
          "## Subagent tasks and reports left out" in complete and "FileNotFoundError" in complete
          and "## Subagent task " not in complete and "check the docs" in complete,
          complete)
    whole_path = write_transcript(workspace, "tracker-fails-whole.jsonl",
                                  ordinary_records()[:-1] + [assistant_record(" ".join(["closing"] * 80))])
    whole_output = Path(workspace) / "whole-out.md"
    try:
        extractor._subagent_tracker_module = None
        extractor.subagent_tracker_module_path = lambda: Path(workspace) / "no-such-tracker-nbd.py"
        with contextlib.redirect_stderr(io.StringIO()):
            extractor.main(["--transcript-path", str(whole_path), "--output", str(whole_output)])
    finally:
        extractor.subagent_tracker_module_path = original_tracker_path
        extractor._subagent_tracker_module = None
    check("a tracker that cannot be loaded adds no complete dialog to a handoff whose tail carries every turn",
          whole_output.is_file() and not (Path(workspace) / "whole-out-complete.md").exists())
    complete_header = complete.split("\n---\n", 1)[0]
    check("the note is counted neither as a dialog turn nor as a subagent turn, and brings no subagent "
          "transcript pointer",
          "All 2 dialog turns" in complete_header and "subagent turns" not in complete_header
          and "agent-<agent id>.jsonl" not in complete_header,
          complete_header)

    # The reply to a notification is kept once the tracker fails: no record can then show it carried a report.
    notified = [
        user_record("run the long job"),
        user_record("<task-notification><task-id>b1</task-id><status>completed</status>"
                    "<result>All green.</result></task-notification>"),
        assistant_record("Both fixed; merging."),
    ]
    notified_path = write_transcript(workspace, "tracker-fails-on-notification.jsonl", notified)

    class TrackerThatRaisesOnNotification:
        def turns_from_record(self, record):
            if "<task-notification>" in json.dumps(record):
                raise KeyError("a notification shape the tracker does not know")
            return [], False

    original_new_tracker = extractor.new_subagent_tracker
    try:
        extractor.new_subagent_tracker = TrackerThatRaisesOnNotification
        notified_turns, notified_skips = extractor.read_dialog_turns(
            notified_path, include_subagent_tasks_and_reports=True)
    finally:
        extractor.new_subagent_tracker = original_new_tracker
    check("a tracker that raises on a notification leaves the agent's short reply to it in the dialog",
          "Both fixed; merging." in [turn["text"] for turn in notified_turns]
          and notified_skips["acknowledgement"] == 0,
          ([turn["text"] for turn in notified_turns], notified_skips))
    plain_turns, plain_skips = extractor.read_dialog_turns(notified_path)
    check("without subagent turns asked for, a short reply to a notification is still an acknowledgement",
          "Both fixed; merging." not in [turn["text"] for turn in plain_turns]
          and plain_skips["acknowledgement"] == 1,
          ([turn["text"] for turn in plain_turns], plain_skips))

    class TrackerThatRaises:
        def __init__(self):
            self.records = 0

        def turns_from_record(self, record):
            self.records += 1
            if self.records == 3:
                raise KeyError("a record shape the tracker does not know")
            return ([{"voice": extractor.SUBAGENT_VOICE, "kind": "task", "text": "kept so far",
                      "subagent": {"agent_id": "", "description": "", "details": []}, "status": ""}],
                    False)

    original_new_tracker = extractor.new_subagent_tracker
    try:
        extractor.new_subagent_tracker = TrackerThatRaises
        turns, _ = extractor.read_dialog_turns(path, include_subagent_tasks_and_reports=True)
    finally:
        extractor.new_subagent_tracker = original_new_tracker
    subagent_kinds = [turn["kind"] for turn in turns if turn["voice"] == extractor.SUBAGENT_VOICE]
    check("a tracker that raises part-way drops the subagent turns it gave, keeps every dialog turn, "
          "and ends with one note naming the error",
          subagent_kinds == [extractor.SUBAGENT_TURNS_LEFT_OUT_KIND]
          and "KeyError" in turns[-1]["text"]
          and [turn["text"] for turn in turns if turn["voice"] != extractor.SUBAGENT_VOICE]
          == ["check the docs", "Yes."],
          [(turn["voice"], turn.get("kind"), turn["text"][:60]) for turn in turns])

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
