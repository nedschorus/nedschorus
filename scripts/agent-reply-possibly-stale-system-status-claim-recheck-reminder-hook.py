#!/usr/bin/env python3
"""Stop hook: remind an agent whose last reply states the current status of
something outside the conversation, such as an agent-seat offline, `claude`
logged out, a machine down or work still on hold, without a check in the same
turn, to check that status with a command before the user acts on it.

Wired as a Stop hook in .claude/settings.json; not at SubagentStop, since a
subagent's report goes to the agent that dispatched it, which checks before it
passes a status on.

THE TRIGGER is the agent's last reply of the turn, read as
scripts/absence-claim-locator-reminder-hook.py reads it: the text blocks of the
last assistant message that has text, since the last message the user, or
another agent-session, sent. The claims are the phrases
nn-systems/general-tools/agent-text-possibly-stale-system-status-claim-phrases-match-common.py
finds, the list the walk-me-through check program uses too.

A CHECK RAN when any tool call of the turn is a Bash command, a SendMessage or
a ListAgents call, CHECKING_TOOL_NAMES: those are how an agent looks at another
agent-seat, a machine, a login or a job. Reading a file is not a check: a
handoff or a log tells what was true when it was written. The hook cannot tell
whether the command looked at the status the reply states, so any such call
keeps it silent.

THE HOOK STAYS SILENT when this Stop ends the agent's answer to a Stop hook's
output (the shared rule of
nn-systems/general-tools/claude-code-stop-hooks-stay-silent-while-agent-answers-a-stop-hook-rule-common.py),
so it never reminds twice in a row; when a check ran; when no user attends
the agent-session, as
nn-systems/general-tools/agent-session-unattended-by-user-check-common.py
decides, since a headless child's last words are its caller's answer; when the
payload names no transcript; and when the transcript does not exist. It
reminds at every turn whose reply holds an unchecked claim, not once per
agent-session, because a stale status is most often repeated turn after turn.

OUTPUT when it reminds: {"hookSpecificOutput": {"hookEventName": "Stop",
"additionalContext": <reminder>}}, which Claude Code hands the agent as its
next input while the conversation continues. No `decision` field, so the hook
never blocks, and no `systemMessage`, since the text is for the agent.

A FAULT, such as a payload that is not a JSON object, a transcript that cannot
be read or any exception: one line on stderr naming the hook and the fault,
nothing on stdout, exit 1, which Claude Code records as a non-blocking error
while the turn ends as usual. Exit 2 would continue the conversation, and a
fault that recurs at every Stop would then never let the agent stop.

Tool-messages-to-agent follow
docs/nedsnodes-wiki/nedsnodes-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md.
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

REPOSITORY_TOP = Path(__file__).resolve().parents[1]


def _load(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


stop_hooks_stay_silent_rule = _load(
    "claude_code_stop_hooks_stay_silent_while_agent_answers_a_stop_hook_rule_common",
    REPOSITORY_TOP / "nn-systems" / "general-tools"
    / "claude-code-stop-hooks-stay-silent-while-agent-answers-a-stop-hook-rule-common.py")
agent_session_unattended_by_user_check_common = _load(
    "agent_session_unattended_by_user_check_common",
    REPOSITORY_TOP / "nn-systems" / "general-tools" / "agent-session-unattended-by-user-check-common.py")
transcript_records_read_backward = _load(
    "claude_code_session_transcript_records_read_backward_common",
    REPOSITORY_TOP / "scripts" / "claude-code-session-transcript-records-read-backward-common.py")
absence_claim_hook = _load(
    "absence_claim_locator_reminder_hook", REPOSITORY_TOP / "scripts" / "absence-claim-locator-reminder-hook.py")
system_status_claims = _load(
    "agent_text_possibly_stale_system_status_claim_phrases_match_common",
    REPOSITORY_TOP / "nn-systems" / "general-tools"
    / "agent-text-possibly-stale-system-status-claim-phrases-match-common.py")

HOOK_NAME = "agent-reply-possibly-stale-system-status-claim-recheck-reminder-hook"
CHECKING_TOOL_NAMES = ("Bash", "SendMessage", "ListAgents")
MATCHED_PHRASES_SHOWN = 3

SYSTEM_STATUS_CLAIM_RECHECK_REMINDER_MESSAGE = (
    "[rule agent-reply-system-status-claim-recheck-with-a-command-before-stating-it] system-status reminder: "
    "your last reply states the current status of something outside this conversation ({matched}), and no "
    "Bash command, SendMessage or ListAgents call in this turn checked it. A status changes without notice: an "
    "agent-seat comes back online, the user logs `claude` back in, a job is restarted. So a status taken from a "
    "session-handoff, a hook's message, a log or an earlier turn is often stale, and the user acts on it or has "
    "to correct you.\n"
    "If the reply states a status you did not check in this turn: check it now with a command, such as "
    "`claude auth status` for the login on this machine, `tmux -L <agent-seat> ls` on the agent-seat's machine, "
    "or the ListAgents tool for an agent-seat you would message. Then tell the user, in one line, what the "
    "command showed and the time you ran it, correcting your reply where it was wrong.\n"
    "If you hold work, such as a task, waiting on that status: start the work once the check shows the wait is "
    "over.\n"
    "If the matched words state no current status, as in a plan, a quotation or a description of what a "
    "program does: carry on, and do not mention this reminder.\n"
    "From now on, check a status with a command in the same turn before you state it to the user, and say when "
    "you checked it."
)


def read_turn(transcript_path):
    """Return (last reply text, whether a tool call in CHECKING_TOOL_NAMES ran this turn)."""
    records = transcript_records_read_backward.records_from_newest_boundary_to_end(
        transcript_path, absence_claim_hook.is_human_or_parent_message)
    start = 0
    for index in range(len(records) - 1, -1, -1):
        if absence_claim_hook.is_human_or_parent_message(records[index]):
            start = index + 1
            break
    checked = False
    last_text_message_id = None
    texts_by_message = {}
    for record in records[start:]:
        if record.get("type") != "assistant":
            continue
        message = record.get("message", {})
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and block.get("name") in CHECKING_TOOL_NAMES:
                checked = True
            elif block.get("type") == "text":
                message_id = message.get("id") or id(record)
                texts_by_message.setdefault(message_id, []).append(block.get("text", ""))
                last_text_message_id = message_id
    return "\n".join(texts_by_message.get(last_text_message_id, [])), checked


def run(stdin_text, environment):
    """Return the text to print, or None."""
    payload = json.loads(stdin_text)
    if not isinstance(payload, dict):
        raise ValueError("the input on the hook's stdin is JSON, but not an object")
    if stop_hooks_stay_silent_rule.stop_hook_stays_silent_while_agent_answers_a_stop_hook(payload):
        return None
    if agent_session_unattended_by_user_check_common.agent_session_unattended_by_user(environment):
        return None
    transcript_path = payload.get("transcript_path")
    if not transcript_path:
        return None
    try:
        reply, checked = read_turn(Path(transcript_path).expanduser())
    except FileNotFoundError:
        return None
    if checked:
        return None
    matches = system_status_claims.possibly_stale_system_status_claim_phrases_find(reply)
    if not matches:
        return None
    matched = ", ".join(f'"{phrase}"' for _, phrase in matches[:MATCHED_PHRASES_SHOWN])
    return json.dumps({"hookSpecificOutput": {
        "hookEventName": "Stop",
        "additionalContext": SYSTEM_STATUS_CLAIM_RECHECK_REMINDER_MESSAGE.format(matched=matched),
    }}, ensure_ascii=False)


def main():
    try:
        output = run(sys.stdin.read(), os.environ)
    except Exception as error:
        print(f"{HOOK_NAME}: the hook failed with {type(error).__name__}: {error}. So the last reply was not "
              f"checked for an unchecked claim about a system's status, and the turn ends as usual. If this "
              f"recurs, run python3 scripts/{HOOK_NAME}-test.py and tell the user what it reports.",
              file=sys.stderr)
        return 1
    if output is not None:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
