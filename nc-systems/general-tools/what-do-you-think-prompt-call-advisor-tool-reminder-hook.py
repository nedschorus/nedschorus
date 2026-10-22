#!/usr/bin/env python3
"""When the user's prompt contains "what do you think", in any letter case,
tell the agent to call the advisor before it answers.

A UserPromptSubmit hook: it adds ADVISOR_REQUEST as
hookSpecificOutput.additionalContext and lets the prompt through. A hook runs
on every prompt, so it cannot miss the phrase the way a skill can, which loads
only when the agent judges its description matches the prompt.

Any other prompt: nothing printed, exit 0. Input that is not a JSON object
with a string "prompt": FAULT_LINES on stderr, nothing on stdout, exit 1,
which Claude Code records as a non-blocking error.
"""

import json
import sys

PROGRAM = "what-do-you-think-prompt-call-advisor-tool-reminder-hook"
PHRASE = "what do you think"
ADVISOR_REQUEST = (
    "The user asked what you think. He wants the advisor's view as well as yours.\n"
    "Before you answer, call the advisor tool, so a stronger reviewer checks your answer; "
    "then answer, and mark what the advisor changed with [advisor].\n"
    "If the advisor tool call fails, say so in your answer and answer without it."
)
FAULT_LINES = (
    PROGRAM + ": the user's prompt went through unchecked for the words \"what do you think\", "
    "because the hook's input could not be read: {reason}",
    "If the user asked what you think, call the advisor tool before you answer.",
    "If this failure is reported again on later prompts, tell the user, quoting the first line.",
)


def run(stdin_text):
    """Return the hook's stdout text, empty when the prompt lacks the phrase; raises ValueError on bad input."""
    payload = json.loads(stdin_text)
    if not isinstance(payload, dict) or not isinstance(payload.get("prompt"), str):
        raise ValueError("the hook's stdin is not a JSON object whose \"prompt\" key holds a string")
    if PHRASE not in " ".join(payload["prompt"].lower().split()):
        return ""
    return json.dumps({"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit", "additionalContext": ADVISOR_REQUEST}}, ensure_ascii=False)


def main():
    try:
        output = run(sys.stdin.read())
    except ValueError as error:
        print("\n".join(FAULT_LINES).format(reason=error), file=sys.stderr)
        return 1
    if output:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
