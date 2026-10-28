#!/usr/bin/env python3
"""Save the follow-up request block of a merge-lane-2 message, and hand the agent the follow-up brief.

A UserPromptSubmit hook. It acts only on a prompt holding a cross-session message whose tag names
from-name="merge-lane-2" and whose body holds the line "#follow_up_request pull request <number>"
followed by numbered findings, one to a line. For each such block it saves the block word for word
with save_follow_up_request_and_clear_answers_when_its_findings_changed() of the program at FOLLOW_UP_PROGRAM_PATH, which owns the file's
place in the git common directory, and hands the agent, as additionalContext, the brief
build_follow_up_request_forked_subagent_brief() of that program writes. Any other prompt, including that line outside a merge-lane-2 message, gets no output
and exit 0.

The hook never blocks the prompt, so merge-lane-2's message always reaches the agent. When a block
cannot be read or saved, the additionalContext says so instead, and says what to do; the hook still
exits 0, because only additionalContext reaches the agent. A fault before a message is read, such
as a payload that is not JSON, goes to stderr with exit 1, which Claude Code shows the user.
"""

import importlib.util
import json
import re
import sys
from pathlib import Path

HOOK = Path(__file__).stem
REQUEST_LINE_START = "#follow_up_request"
MERGE_LANE_2_MESSAGE_PATTERN = re.compile(
    r"<cross-session-message\b(?P<attributes>[^>]*)>(?P<body>.*?)</cross-session-message>", re.DOTALL)
MERGE_LANE_2_SENDER_PATTERN = re.compile(r"\bfrom-name=\"merge-lane-2\"")
FOLLOW_UP_PROGRAM_PATH = (Path(__file__).resolve().parents[2] / "scripts"
                         / "pull-request-follow-up-request-findings-open-pull-requests-or-record-leave-out-reasons-and-clean-up.py")
# Each text this hook hands an agent follows
# docs/nedschorus-wiki/nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md.
UNREADABLE_BLOCK_LINES = (
    HOOK + ": merge-lane-2's message above holds a #follow_up_request block that the hook could not "
    "read, so nothing was saved, and no follow-up brief is given.\n"
    "Tell merge-lane-2 with SendMessage that its #follow_up_request block could not be read because "
    "{problem}, and ask it to send the block again.")
NOT_SAVED_LINES = (
    HOOK + ": merge-lane-2's message above holds a #follow_up_request block, but the hook could not "
    "save the block, so the follow-up program cannot track the "
    "findings: {error}\n"
    "Follow up the findings in merge-lane-2's message yourself now, as CLAUDE.md says: open a pull "
    "request for each you take on, and tell merge-lane-2 with SendMessage the reason for each you "
    "leave out.\n"
    "Tell the user, in one sentence: the follow-up request hook could not save merge-lane-2's "
    "findings, because of the error above, so you are following them up without the brief.\n"
    "If you are a subagent, pass that sentence to the agent that dispatched you instead.")


def load_follow_up_program():
    specification = importlib.util.spec_from_file_location(
        "pull_request_follow_up_request_findings_open_pull_requests_or_record_leave_out_reasons_and_clean_up",
        FOLLOW_UP_PROGRAM_PATH)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def merge_lane_2_message_bodies(prompt):
    return [match.group("body") for match in MERGE_LANE_2_MESSAGE_PATTERN.finditer(prompt)
            if MERGE_LANE_2_SENDER_PATTERN.search(match.group("attributes"))]


def context_for(payload):
    """The additionalContext text for the prompt, or None when the prompt asks for nothing."""
    prompt = payload.get("prompt") or ""
    if REQUEST_LINE_START not in prompt:
        return None
    bodies = [body for body in merge_lane_2_message_bodies(prompt) if REQUEST_LINE_START in body]
    if not bodies:
        return None
    try:
        follow_up_program = load_follow_up_program()
    except Exception as error:
        return NOT_SAVED_LINES.format(error=f"loading {FOLLOW_UP_PROGRAM_PATH} failed: {error!r}")
    requests = []
    for body in bodies:
        try:
            requests += follow_up_program.parse_follow_up_request_blocks_from_message_text(body)
        except ValueError as error:
            return UNREADABLE_BLOCK_LINES.format(problem=error)
    if not requests:
        return None
    directory = payload.get("cwd") or "."
    texts = []
    for request in requests:
        try:
            follow_up_program.save_follow_up_request_and_clear_answers_when_its_findings_changed(request, directory)
        except follow_up_program.StepFailed as error:
            return NOT_SAVED_LINES.format(error=error)
        texts.append(follow_up_program.build_follow_up_request_forked_subagent_brief(request))
    return "\n\n".join(texts)


def main():
    try:
        payload = json.loads(sys.stdin.read())
    except ValueError as error:
        print(f"{HOOK}: the hook could not read its input, so no #follow_up_request block was looked "
              f"for: {error!r}", file=sys.stderr)
        return 1
    context = context_for(payload)
    if context is not None:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                                 "additionalContext": context}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
