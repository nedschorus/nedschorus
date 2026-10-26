#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/checkout-freshness-changed-skill-invoke-again-refusal-stop-hook.py.

Each case writes a transcript shaped like the records Claude Code writes, runs
the hook as a subprocess with a Stop payload naming it, and asserts the exit
code, stdout and stderr. The checkout-freshness note in each transcript is
built from scripts/checkout-freshness-catch-up.py's own SKILL_CHANGED_NOTE, so a
change to that note that the hook no longer matches fails here.

Run: python3 nc-systems/general-tools/tests/checkout-freshness-changed-skill-invoke-again-refusal-stop-hook-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
HOOK = REPOSITORY_ROOT / "nc-systems" / "general-tools" / "checkout-freshness-changed-skill-invoke-again-refusal-stop-hook.py"
FRESHNESS_HOOK = REPOSITORY_ROOT / "scripts" / "checkout-freshness-catch-up.py"

_specification = importlib.util.spec_from_file_location("checkout_freshness_catch_up", FRESHNESS_HOOK)
freshness = importlib.util.module_from_spec(_specification)
_specification.loader.exec_module(freshness)

SKILL = "walk-me-through"
PATH = f".claude/skills/{SKILL}/SKILL.md"
OTHER_SKILL = "cold-read"
OTHER_PATH = f".claude/skills/{OTHER_SKILL}/SKILL.md"

OPENING = ("changed-skill check (nc-systems/general-tools/checkout-freshness-changed-skill-invoke-again-"
           "refusal-stop-hook.py): this hook refused to end your turn on purpose, because a checkout-freshness note "
           f"told you that the main branch changed {PATH}, and this agent-session invoked the {SKILL} skill before "
           "that note and has not invoked it since.")
STILL_FOLLOWING_LINE = (f"If you are still following the {SKILL} skill, that is, you will act on another of its steps "
                        "in this agent-session, such as an approval-walk that is still open: invoke it again now with "
                        f"the Skill tool, with skill `{SKILL}`, then go on from where you were, following its new text.")
NO_LONGER_FOLLOWING_LINE = (f"If you are no longer following the {SKILL} skill: end your turn as you would have; this "
                            "hook refuses only once for each note that the main branch changed a skill.")
UNSURE_LINE = "If you cannot tell whether you are still following it, invoke it again: that costs one tool call."
REASON_LINE_START = "This checkout already holds the new text"
FROM_NOW_ON_LINE = ("From now on, when a note beginning `checkout-freshness: main changed` names a skill you are "
                    "following, invoke that skill again before its next step.")

FAILURES = []


def note(path=PATH, skill=SKILL):
    """The attachment record Claude Code writes when the freshness hook delivers its note."""
    text = (freshness.SKILL_CHANGED_NOTE.format(path=path, skill=skill)
            + "\n" + freshness.NOT_FOR_THE_USER_ADVICE)
    return {"type": "attachment", "isSidechain": False,
            "attachment": {"type": "hook_additional_context", "content": [text],
                           "hookName": "UserPromptSubmit", "hookEvent": "UserPromptSubmit"}}


def api_blob_holding_note():
    """A record of an API request that holds the note's text but is not its delivery."""
    return {"type": "api-request-blob", "message": {"role": "system", "content": [
        {"type": "text", "text": "UserPromptSubmit hook additional context: "
                                 + freshness.SKILL_CHANGED_NOTE.format(path=PATH, skill=SKILL)}]}}


def skill_call(skill=SKILL, sidechain=False):
    return {"type": "assistant", "isSidechain": sidechain, "message": {"role": "assistant", "content": [
        {"type": "tool_use", "name": "Skill", "id": "toolu_1", "input": {"skill": skill}}]}}


def typed_command(skill=SKILL):
    return {"type": "user", "isSidechain": False, "message": {"role": "user", "content": (
        f"<command-message>{skill}</command-message>\n<command-name>/{skill}</command-name>\n"
        f"<command-args></command-args>")}}


def prompt(text="go on"):
    return {"type": "user", "isSidechain": False, "message": {"role": "user", "content": text}}


def refusal_attachment(opening=OPENING):
    return {"type": "attachment", "isSidechain": False, "attachment": {
        "type": "hook_blocking_error", "hookName": "Stop", "hookEvent": "Stop",
        "blockingError": {"blockingError": opening + "\nmore lines", "command": "python3 hook.py"}}}


def refusal_feedback(opening=OPENING):
    return {"type": "user", "isSidechain": False, "message": {"role": "user", "content": (
        "Stop hook feedback:\n" + opening + "\nmore lines")}}


def run_hook(stdin_text):
    completed = subprocess.run([sys.executable, str(HOOK)], input=stdin_text, capture_output=True, text=True,
                               timeout=60, check=False)
    return completed.returncode, completed.stdout, completed.stderr


def run_on(records, directory, extra_lines=(), **payload_fields):
    transcript = Path(directory) / "transcript.jsonl"
    lines = list(extra_lines) + [json.dumps(record) for record in records]
    transcript.write_text("\n".join(lines) + "\n", encoding="utf-8")
    payload = {"session_id": "s", "transcript_path": str(transcript), "cwd": str(directory),
               "hook_event_name": "Stop", "stop_hook_active": False, **payload_fields}
    return run_hook(json.dumps(payload))


def check(name, condition, detail=""):
    print(("PASS " if condition else "FAIL ") + name + ("" if condition else f": {detail}"))
    if not condition:
        FAILURES.append(name)


def check_silent(name, result):
    code, stdout, stderr = result
    check(name, code == 0 and stdout == "" and stderr == "", f"exit {code}, stdout {stdout!r}, stderr {stderr!r}")


def check_blocks(name, result, *expected_lines):
    code, stdout, stderr = result
    try:
        output = json.loads(stdout)
    except ValueError:
        check(name, False, f"exit {code}, stdout not JSON: {stdout!r}, stderr {stderr!r}")
        return None
    reason = output.get("reason", "")
    reason_lines = reason.split("\n")
    missing = [line for line in expected_lines if not any(line in reason_line for reason_line in reason_lines)]
    check(name, code == 0 and output.get("decision") == "block" and not missing and stderr == "",
          f"exit {code}, output {output!r}, missing {missing!r}, stderr {stderr!r}")
    return reason


def main():
    with tempfile.TemporaryDirectory() as directory:
        check_blocks("invoked before the note and not since: blocks, naming the skill and both instructions",
                     run_on([prompt(), skill_call(), prompt(), note(), prompt()], directory),
                     OPENING, REASON_LINE_START, STILL_FOLLOWING_LINE, NO_LONGER_FOLLOWING_LINE, UNSURE_LINE,
                     FROM_NOW_ON_LINE)
        check_blocks("the user's typed command before the note counts as an invocation",
                     run_on([typed_command(), prompt(), note()], directory), OPENING)
        check_silent("invoked again after the note: silent",
                     run_on([skill_call(), note(), skill_call()], directory))
        check_silent("the user's typed command after the note counts: silent",
                     run_on([skill_call(), note(), typed_command()], directory))
        check_silent("never invoked: silent", run_on([prompt(), note(), prompt()], directory))
        check_silent("invoked only after the note: silent", run_on([note(), skill_call()], directory))
        check_silent("another skill invoked before the note: silent",
                     run_on([skill_call(OTHER_SKILL), note()], directory))
        check_silent("a subagent's invocation before the note does not count: silent",
                     run_on([skill_call(sidechain=True), note()], directory))
        check_blocks("a subagent's invocation after the note does not count: blocks",
                     run_on([skill_call(), note(), skill_call(sidechain=True)], directory), OPENING)
        check_silent("the note's text only in an API request record is no note: silent",
                     run_on([skill_call(), api_blob_holding_note()], directory))
        check_silent("already refused after the note, recorded as a blocking-error attachment: silent",
                     run_on([skill_call(), note(), refusal_attachment(), prompt()], directory))
        check_silent("already refused after the note, recorded as Stop hook feedback: silent",
                     run_on([skill_call(), note(), refusal_feedback(), prompt()], directory))
        check_blocks("a refusal before a newer note does not stop the newer note's refusal",
                     run_on([skill_call(), note(), refusal_attachment(), note()], directory), OPENING)
        check_blocks("a refusal for another skill does not count as this skill's",
                     run_on([skill_call(), note(), refusal_attachment(OPENING.replace(SKILL, OTHER_SKILL))],
                            directory), OPENING)
        check_blocks("an invocation between two notes is before the newer note: blocks",
                     run_on([skill_call(), note(), skill_call(), note()], directory), OPENING)
        reason = check_blocks(
            "two skills due in one note: both named",
            run_on([skill_call(), skill_call(OTHER_SKILL), {
                "type": "attachment", "attachment": {"type": "hook_additional_context", "content": [
                    freshness.SKILL_CHANGED_NOTE.format(path=PATH, skill=SKILL) + "\n"
                    + freshness.SKILL_CHANGED_NOTE.format(path=OTHER_PATH, skill=OTHER_SKILL)]}}], directory),
            OPENING, OPENING.replace(SKILL, OTHER_SKILL))
        check("two skills due: the from-now-on line comes once",
              reason is not None and reason.count(FROM_NOW_ON_LINE) == 1, repr(reason))
        check_blocks("lines that are not JSON objects, before the records, are skipped",
                     run_on([skill_call(), note()], directory,
                            extra_lines=['{"type": "Skill" broken', '["Skill", "checkout-freshness"]']), OPENING)
        check_silent("a typed command in a prompt made of text blocks counts after the note: silent",
                     run_on([skill_call(), note(), {"type": "user", "message": {"role": "user", "content": [
                         {"type": "text", "text": f"<command-name>/{SKILL}</command-name>"}]}}], directory))
        note_text = freshness.SKILL_CHANGED_NOTE.format(path=PATH, skill=SKILL)
        for kind in ("async_hook_response", "hook_success"):
            check_silent(f"the note's text in an attachment of type {kind} is no note: silent",
                         run_on([skill_call(), {"type": "attachment", "attachment": {"type": kind, "content": [note_text]}}],
                                directory))
            check_blocks(f"the refusal's text in an attachment of type {kind} is no refusal: blocks",
                         run_on([skill_call(), note(), {"type": "attachment", "attachment": {
                             "type": kind, "blockingError": {"blockingError": OPENING}}}], directory), OPENING)
        for kind in ("api-request-blob", "attachment"):
            check_blocks(f"a Skill call inside a {kind} record is no invocation: blocks",
                         run_on([skill_call(), note(), {**skill_call(), "type": kind}], directory), OPENING)
        for kind in ("progress", "worktree-state"):
            check_blocks(f"a typed command inside a {kind} record is no invocation: blocks",
                         run_on([skill_call(), note(), {**typed_command(), "type": kind}], directory), OPENING)
        for tool in ("Bash", "Task"):
            check_blocks(f"a {tool} call whose input names the skill is no invocation: blocks",
                         run_on([skill_call(), note(), {"type": "assistant", "message": {"content": [
                             {"type": "text", "text": "Skill"}, {"type": "tool_use", "name": tool, "input": {"skill": SKILL}}]}}], directory), OPENING)
        check_blocks("an assistant message with text after the note is no invocation: blocks",
                     run_on([skill_call(), note(), {"type": "assistant", "message": {"content": [
                         {"type": "text", "text": "Skill"}]}}], directory), OPENING)
        check_silent("stop_hook_active: silent although a refusal is due",
                     run_on([skill_call(), note()], directory, stop_hook_active=True))
        check_silent("no transcript path: silent", run_hook(json.dumps({"stop_hook_active": False})))
        check_silent("a transcript that does not exist: silent",
                     run_hook(json.dumps({"transcript_path": str(Path(directory) / "absent.jsonl")})))

        unreadable = Path(directory) / "a-directory.jsonl"
        unreadable.mkdir()
        code, stdout, stderr = run_hook(json.dumps({"transcript_path": str(unreadable)}))
        check("a transcript that cannot be read: exit 1, one stderr line saying the check did not run",
              code == 1 and stdout == "" and "the hook failed, so it did not check" in stderr
              and len(stderr.strip().split("\n")) == 1, f"exit {code}, stdout {stdout!r}, stderr {stderr!r}")
        code, stdout, stderr = run_hook("not json")
        check("input that is not JSON: exit 1 with a stderr line", code == 1 and stdout == ""
              and "the hook failed" in stderr, f"exit {code}, stdout {stdout!r}, stderr {stderr!r}")
        code, stdout, stderr = run_hook("[1]")
        check("input that is JSON but not an object: exit 1 with a stderr line", code == 1 and stdout == ""
              and "not an object" in stderr, f"exit {code}, stdout {stdout!r}, stderr {stderr!r}")
    print(f"{len(FAILURES)} case(s) failed" if FAILURES else "every case passed")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
