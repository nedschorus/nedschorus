#!/usr/bin/env python3
"""Stop hook: refuse the agent's stop once when main changed a skill the agent
invoked, the agent was told so, and it has not invoked the skill again since.

scripts/checkout-freshness-catch-up.py tells the agent, with its next prompt,
that main changed `.claude/skills/<name>/SKILL.md`, in a note built from its
SKILL_CHANGED_NOTE. Claude Code reloads a skill's text only when the skill is
invoked again, so an agent that read the skill earlier keeps following the old
text until it does. This hook makes that note hard to miss.

THE RECORD of which skills were reported is the transcript itself: Claude Code
writes each note it delivers as an `attachment` record of type
`hook_additional_context`. Only those records count as the note; the same text
also sits in records Claude Code keeps of its API requests, which would place
the note later than it reached the agent. The note's text is matched with a
pattern built from SKILL_CHANGED_NOTE, loaded from the freshness hook, so the
two hooks cannot drift apart.

FOR EACH SKILL named in a note, the newest note governs. The hook refuses when
the skill was invoked before that note and has not been invoked after it, and
this hook has not already refused for it after that note. An invocation is the
main agent's Skill tool call naming the skill, or a user prompt carrying
`<command-name>/<name></command-name>` as its text or in a text block, which is
how Claude Code records the user typing the skill's command; a tool result,
which Claude Code also writes as a `user` record, does not count; a subagent's call (`isSidechain` true) does
not reload the skill in the main agent's context, so it does not count. A
refusal already made is found as the Stop-hook block Claude Code records, an
`attachment` of type `hook_blocking_error` or the `Stop hook feedback:` user
record, holding the refusal's first sentence for that skill. So each note
brings at most one refusal per skill, and a later note about the same skill
brings one more.

The whole transcript is read, because the note may have come several turns
ago when another Stop hook's block kept this one silent; only lines holding one
of the texts the checks look for are parsed as JSON, which keeps the read of
a 58 MB transcript fast.

SILENT while the agent answers a Stop hook (`stop_hook_active` set), as the
Stop-hook silence rule's module requires, and when the payload names no
transcript or the transcript does not exist.

OUTPUT: {"decision": "block", "reason": <message>}, exit 0. ON A FAULT, such
as input that is not JSON or a transcript that cannot be read, one line on
stderr naming it and saying what to do instead, and exit 1: Claude Code records a Stop hook's exit 1 as a
non-blocking error and still ends the turn.

Agent-facing messages follow
docs/nedschorus-wiki/nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md.
"""
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FRESHNESS_HOOK_FILE = HERE.parents[1] / "scripts" / "checkout-freshness-catch-up.py"
STOP_HOOKS_STAY_SILENT_RULE_FILE = HERE / "claude-code-stop-hooks-stay-silent-while-agent-answers-a-stop-hook-rule-common.py"

REFUSAL_OPENING_TEMPLATE = (
    "changed-skill check (nc-systems/general-tools/checkout-freshness-changed-skill-invoke-again-"
    "refusal-stop-hook.py): this hook refused to end your turn on purpose, because a checkout-freshness note "
    "told you that the main branch changed {path}, and this agent-session invoked the {skill} skill before that "
    "note and has not invoked it since.")
REFUSAL_REASON_TEMPLATE = (
    "This checkout already holds the new text, but the {skill} skill's text in your context is the old one, so "
    "the skill's next step may follow instructions that have since changed.")
REFUSAL_INSTRUCTIONS_TEMPLATE = (
    "If you are still following the {skill} skill, that is, you will act on another of its steps in this "
    "agent-session, such as an approval-walk that is still open: invoke it again now with the Skill tool, with "
    "skill `{skill}`, then go on from where you were, following its new text.\n"
    "If you are no longer following the {skill} skill: end your turn as you would have; this hook refuses only "
    "once for each note that the main branch changed a skill.\n"
    "If you cannot tell whether you are still following it, invoke it again: that costs one tool call.")
FROM_NOW_ON_LINE = (
    "From now on, when a note beginning `checkout-freshness: main changed` names a skill you are following, "
    "invoke that skill again before its next step.")

# Only lines holding one of these are parsed: every record the checks read holds one.
CANDIDATE_LINE_MARKERS = (b'"Skill"', b"<command-name>/", b"checkout-freshness", b"changed-skill check")
STOP_HOOK_FEEDBACK_PREFIX = "Stop hook feedback:"


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


freshness_hook = load_module("checkout_freshness_catch_up", FRESHNESS_HOOK_FILE)

SKILL_CHANGED_NOTE_PATTERN = re.compile(
    re.escape(freshness_hook.SKILL_CHANGED_NOTE)
    .replace(re.escape("{path}"), r"(?P<path>\S+)")
    .replace(re.escape("{skill}"), r"(?P<skill>\S+)"))


def refusal_opening(path, skill):
    return REFUSAL_OPENING_TEMPLATE.format(path=path, skill=skill)


def candidate_records(transcript_path):
    """The transcript's records, oldest first, that hold one of CANDIDATE_LINE_MARKERS; raises OSError."""
    records = []
    with open(transcript_path, "rb") as transcript:
        for line in transcript:
            if not any(marker in line for marker in CANDIDATE_LINE_MARKERS):
                continue
            try:
                record = json.loads(line.decode("utf-8", "replace"))
            except ValueError:
                continue
            if isinstance(record, dict):
                records.append(record)
    return records


def message_content(record):
    message = record.get("message")
    return message.get("content") if isinstance(message, dict) else None


def changed_skill_notes(record):
    """[(path, skill), ...] that a delivered checkout-freshness note in this record names."""
    attachment = record.get("attachment")
    if not isinstance(attachment, dict) or attachment.get("type") != "hook_additional_context":
        return []
    return [(match["path"], match["skill"]) for text in attachment.get("content") or ()
            if isinstance(text, str) for match in SKILL_CHANGED_NOTE_PATTERN.finditer(text)]


def invoked_skills(record):
    """The skills this record shows the main agent, or the user's typed command, invoking."""
    if record.get("isSidechain"):
        return set()
    content = message_content(record)
    if record.get("type") == "assistant":
        return {block["input"].get("skill") for block in content or ()
                if isinstance(block, dict) and block.get("name") == "Skill" and isinstance(block.get("input"), dict)}
    if record.get("type") == "user":
        # Tool results are `user` records too, holding their output under "content", never "text": a tool output
        # quoting the tag is not the user typing the command.
        texts = [content] if isinstance(content, str) else [
            block.get("text") for block in content or () if isinstance(block, dict)]
        return {skill for text in texts if isinstance(text, str)
                for skill in re.findall(r"<command-name>/([^<\s]+)</command-name>", text)}
    return set()


def stop_block_text(record):
    """The text of a Stop-hook block Claude Code recorded, or ""."""
    attachment = record.get("attachment")
    if isinstance(attachment, dict) and attachment.get("type") == "hook_blocking_error":
        return json.dumps(attachment.get("blockingError"))
    content = message_content(record)
    if isinstance(content, str) and content.startswith(STOP_HOOK_FEEDBACK_PREFIX):
        return content
    return ""


def skills_due(records):
    """[(path, skill), ...] for each skill the agent must invoke again."""
    # Per skill: the newest note's index and path, and whether the skill was invoked before it.
    newest_note = {}
    invoked = set()
    for index, record in enumerate(records):
        for path, skill in changed_skill_notes(record):
            newest_note[skill] = (index, path, skill in invoked)
        for skill in invoked_skills(record):
            invoked.add(skill)
            newest_note.pop(skill, None)
    return [(path, skill) for skill, (index, path, invoked_before) in newest_note.items()
            if invoked_before
            and not any(refusal_opening(path, skill) in stop_block_text(record) for record in records[index:])]


def refusal_reason(due):
    parts = []
    for path, skill in due:
        parts.append(refusal_opening(path, skill) + " " + REFUSAL_REASON_TEMPLATE.format(skill=skill)
                     + "\n" + REFUSAL_INSTRUCTIONS_TEMPLATE.format(skill=skill))
    parts.append(FROM_NOW_ON_LINE)
    return "\n".join(parts)


def run(stdin_text):
    """Return the text to print, or None."""
    payload = json.loads(stdin_text)
    if not isinstance(payload, dict):
        raise ValueError(f"the hook's input is JSON but not an object: it is a {type(payload).__name__}")
    rule = load_module("claude_code_stop_hooks_stay_silent_while_agent_answers_a_stop_hook_rule_common",
                       STOP_HOOKS_STAY_SILENT_RULE_FILE)
    if rule.stop_hook_stays_silent_while_agent_answers_a_stop_hook(payload):
        return None
    transcript_path = payload.get("transcript_path")
    if not transcript_path or not Path(transcript_path).expanduser().exists():
        return None
    due = skills_due(candidate_records(Path(transcript_path).expanduser()))
    if not due:
        return None
    return json.dumps({"decision": "block", "reason": refusal_reason(due)})


def main():
    try:
        output = run(sys.stdin.read())
    except Exception as error:
        print(f"checkout-freshness-changed-skill-invoke-again-refusal-stop-hook: the hook failed, so it did not "
              f"check whether the main branch changed a skill this agent-session invoked: {error!r}. Your turn can "
              f"still end. If a note beginning `checkout-freshness: main changed` named a "
              f"skill whose steps you will still act on in this agent-session: invoke that skill again with the "
              f"Skill tool before you act on the skill's next step.",
              file=sys.stderr)
        return 1
    if output is not None:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
