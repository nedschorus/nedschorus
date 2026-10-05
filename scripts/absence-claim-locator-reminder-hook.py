#!/usr/bin/env python3
"""Stop and SubagentStop hook: once per agent-session, remind an agent that
has just told someone a file or record is gone, missing or cannot be found to
run scripts/locate-file-copies-across-machines.py first.

Wired as a Stop and a SubagentStop hook in .claude/settings.json.

THE TRIGGER is the agent's last reply of the turn, read from the transcript:
the text blocks of the last assistant message that has text, since the last
message the user (or, for a subagent, its parent) sent. absence_claim_matches()
decides whether that reply claims a stored artifact is absent. It is four
phrase patterns, numbered 2, 4, 6 and 12 after the larger detector they were
chosen from, with the guards measured alongside them; on 278 hand-labelled
replies, about four fires in five were correct. Matches inside code, quoted
text and block quotes do not count.

THE HOOK STAYS SILENT when any of these holds:
  - stop_hook_active is set: the agent is already continuing because of a
    Stop hook, and blocking again could loop;
  - the agent ran the locator this turn (a Bash command naming
    locate-file-copies-across-machines.py) or invoked the skill
    locate-before-saying-a-file-is-missing;
  - this agent-session (for a subagent, this subagent) was already reminded:
    agents remember the reminder for a while, so it comes once;
  - the agent-session is a headless `claude -p` child, told apart as the
    due-task hook does: NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER set,
    or CLAUDE_CODE_SESSION_ATTENDED == "0". The reminder would otherwise
    become the child's last words, which its caller reads as the answer;
  - a SubagentStop payload names no agent_transcript_path: the main
    transcript holds the parent's reply, not the subagent's.

OUTPUT when it reminds: {"decision": "block", "reason": <reminder>}, which
keeps the agent going with the reminder as its next instruction.

THE LOG gets one JSON line per triggering reply, whatever the outcome
(reminded, locator_ran, already_reminded, headless), and one per internal
error, so precision can be rechecked from what the hook saw. On ned-box it is
the log-store file LOG_STORE_FILE_ON_NED_BOX; elsewhere it is under
~/.local/state/claude/, for shipping to the log-store later, because a hook
must not wait on ssh. NEDSCHORUS_ABSENCE_CLAIM_REMINDER_LOG overrides the
path, and NEDSCHORUS_ABSENCE_CLAIM_REMINDER_STATE_DIRECTORY overrides where
the once-per-session markers go.

The hook never exits nonzero and prints nothing on a fault: a fault here must
not stop a turn ending.

--measure-precision LABELS_CSV runs absence_claim_matches() over a labelled
reply file (columns reply_id, label, reply_text; label CORRECT, INCORRECT or
UNCLEAR) and prints the fire counts by label and the precision.
"""
import argparse
import csv
import json
import os
import re
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

SKILL_NAME = "locate-before-saying-a-file-is-missing"
LOCATOR_PROGRAM_NAME = "locate-file-copies-across-machines.py"
LOG_STORE_HOSTNAME = "ned-box"
LOG_STORE_FILE_ON_NED_BOX = Path(
    "/home/nedlern/nedschorus-logs/seats/ned-box-helper/"
    "absence-claim-locator-reminder-fires-ned-box.jsonl")
STATE_DIRECTORY_UNDER_HOME = (Path(".local") / "state" / "claude"
                              / "absence-claim-locator-reminder")
LOG_FILE_NAME_ELSEWHERE = "absence-claim-locator-reminder-fires-mac.jsonl"
LOG_ENVIRONMENT_VARIABLE = "NEDSCHORUS_ABSENCE_CLAIM_REMINDER_LOG"
STATE_ENVIRONMENT_VARIABLE = "NEDSCHORUS_ABSENCE_CLAIM_REMINDER_STATE_DIRECTORY"
REPLY_TEXT_LOGGED_CHARACTERS = 4000

REMINDER_TEMPLATE = (
    "absence-claim reminder: your reply says a file or record is gone, missing "
    "or cannot be found ({matched}), and you have not run the locator this "
    "turn. Files agents call missing are often in another checkout, the "
    "log-store, a transcript or a backup.\n"
    "Before you tell anyone it does not exist, run: python3 "
    "scripts/locate-file-copies-across-machines.py <the file's name>\n"
    "If the locator finds it, tell whoever read your reply that it is not "
    "missing, and where it is.\n"
    "If the locator finds nothing, say where you looked, not that the file "
    "does not exist.\n"
    "If your reply was not about a stored file or record, carry on; this "
    "reminder comes once per session."
)

# The pattern numbers are kept from the detector these were measured in, so
# the guards below read the same as in the measurement.
PATTERNS = {
    2: r"\b(?:is|are|was|were|it's|they're)\s+(?:(?:now|all|still)\s+)?(?:gone|missing|lost|absent|unrecoverable)\b",
    4: r"\b(?:can not|cannot|can't|could not|couldn't|did not|didn't|do not|don't|unable to|failed to)\s+(?:\w+\s+){0,3}(?:find|locate|recover)\b",
    6: r"\b(?:not|isn't|aren't|wasn't|weren't)\s+(?:present\s+)?(?:on disk|in (?:the |this |any |our |my )?(?:mirror|log[- ]store|repo(?:sitory)?|checkout|git|branch|transcript|backup))\b|\bon no branch\b",
    12: r"\bno\s+(?:user turn|reply|response)(?:\s+from you)?\s+(?:in between|between)\b|\b(?:you never (?:gave|said yes)|ruling you never gave)\b",
}
COMPILED = {number: re.compile(pattern, re.I) for number, pattern in PATTERNS.items()}
# Pattern 2's words also describe processes, settings and findings, so it
# fires only when a stored artifact is named just before the match.
ARTIFACT = re.compile(r"\b(?:FILE|files?|documents?|drafts?|transcripts?|records?|copies|copy|backups?|paths?|directories|directory|folders?|artifacts?|overviews?|reports?|logs?|history|traces?|phrases?|mirrors?|checkouts?|repos?|issues?|comments?|edits?|citations?|rulings?|approvals?|prompts?|notes?|data|results?)\b", re.I)
SCORING_REPLY = re.compile(r"\b(?:match file|match to|report covers|answer-key entries)\b", re.I)


def strip_noise(text):
    """Remove what an agent quotes rather than asserts: fenced and indented
    code, block quotes, inline code, link targets, emphasis and double-quoted
    text. An inline code span that looks like a path becomes the word FILE."""
    text = text.replace("’", "'").replace("‘", "'").replace(" ", " ")
    lines = []
    fence = None
    for line in text.splitlines():
        fence_match = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if fence:
            if (fence_match and fence_match[1][0] == fence[0]
                    and len(fence_match[1]) >= len(fence)):
                fence = None
            continue
        if fence_match:
            fence = fence_match[1]
            continue
        if re.match(r"^\s*>", line):
            continue
        if re.match(r"^(?: {4}|\t)", line):
            continue
        lines.append(line)
    text = "\n".join(lines)

    def inline(code_match):
        body = code_match[2]
        if re.search(r"(?:[/~]|\.[a-zA-Z0-9]{1,8}\b)", body) and not re.search(r"\s", body):
            return " FILE "
        return " "
    text = re.sub(r"(`+)([^`\n]*?)\1", inline, text)
    text = re.sub(r"\[([^\]\n]+)\]\([^\n)]*\)", r"\1", text)
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r'"[^"\n]*"', " ", text)
    text = re.sub(r"“[^”\n]*”", " ", text)
    return text


def match_is_excluded(number, sentence, before, after):
    """True when the sentence around a match shows it is not an absence claim."""
    if number == 2 and not ARTIFACT.search(before[-100:]):
        return True
    if number == 2 and re.match(r"\s+from (?:the |a )?(?:glossary|list|table|set|definition)\b", after, re.I):
        return True
    if number == 4 and re.search(r"\b(?:commands?|services?|hosts?|programs?|readers?)\b", sentence, re.I) and not ARTIFACT.search(sentence):
        return True
    if re.search(r"\b(?:not|rather than|without)\s+(?:\w+\s+){0,3}(?:claiming|concluded|concluding|saying|say)\b", before, re.I):
        return True
    if re.search(r"\b(?:before (?:saying|telling)|tells every agent|claimed|counts? how often|counts? how many)\b", before, re.I):
        return True
    if re.search(r"\b(?:if|unless|when|whenever|would|should|will)\b", before, re.I):
        return True
    if re.search(r"\bglossary\b", sentence, re.I):
        return True
    if number == 2 and re.search(r"\b(?:none|nothing|no (?:work|edits?|files?))\b", before, re.I):
        return True
    if number == 2 and re.search(r"\b(?:setting|option|field|flag|heading|section|sentence|clause|line|entry|entries|pid|process|supervisor|thread|cause|exception)\b[^,;:]{0,35}$", before, re.I):
        return True
    if number == 2 and re.search(r"\bprocesses\b[^,;:]{0,35}$", before, re.I):
        return True
    if number == 4 and re.match(r"\s+(?:out\s+)?(?:which run|who wrote|how|why)\b", after, re.I):
        return True
    if number == 4 and re.match(r"\s+this shape\b", after, re.I):
        return True
    if re.search(r"\beither\b", before, re.I) and re.search(r"\bor\b", after, re.I):
        return True
    if number == 2 and re.search(r"\bno\s+(?:report|file|record)\s*$", before, re.I):
        return True
    if re.search(r"\b(?:does not|doesn't|never)\s+say\b", before[-100:], re.I):
        return True
    if re.search(r"\buntil\b|(?<!at )\bonce\b", before, re.I):
        return True
    if re.search(r"\bcould\b", before, re.I):
        return True
    return False


def absence_claim_matches(text):
    """Return a list of (pattern number, matched phrase) for each absence claim."""
    stripped = strip_noise(text)
    if SCORING_REPLY.search(stripped):
        return []
    found = []
    for unit in re.finditer(r"[^\n]+", stripped):
        for sentence_match in re.finditer(r".+?(?:[.!?](?=\s|$)|$)", unit.group()):
            sentence = sentence_match.group()
            for number, pattern in COMPILED.items():
                for match in pattern.finditer(sentence):
                    before = sentence[:match.start()]
                    after = sentence[match.end():]
                    if not match_is_excluded(number, sentence, before, after):
                        found.append((number, match.group()))
    return found


def is_human_or_parent_message(record):
    if record.get("type") != "user":
        return False
    content = record.get("message", {}).get("content")
    if isinstance(content, str):
        return True
    if isinstance(content, list):
        return any(isinstance(block, dict) and block.get("type") == "text" for block in content)
    return False


def read_turn(transcript_path):
    """Return (last reply text, locator ran this turn) for the transcript's last turn."""
    records = []
    with open(transcript_path, encoding="utf-8") as transcript:
        for line in transcript:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if isinstance(record, dict):
                records.append(record)
    start = 0
    for index in range(len(records) - 1, -1, -1):
        if is_human_or_parent_message(records[index]):
            start = index + 1
            break
    turn = [record for record in records[start:] if record.get("type") == "assistant"]
    locator_ran = False
    last_text_message_id = None
    texts_by_message = {}
    for record in turn:
        message = record.get("message", {})
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                tool_input = block.get("input") or {}
                if (block.get("name") == "Bash"
                        and LOCATOR_PROGRAM_NAME in str(tool_input.get("command", ""))):
                    locator_ran = True
                if block.get("name") == "Skill" and tool_input.get("skill") == SKILL_NAME:
                    locator_ran = True
            elif block.get("type") == "text":
                message_id = message.get("id") or id(record)
                texts_by_message.setdefault(message_id, []).append(block.get("text", ""))
                last_text_message_id = message_id
    reply = "\n".join(texts_by_message.get(last_text_message_id, []))
    return reply, locator_ran


def log_path(environment, home):
    override = environment.get(LOG_ENVIRONMENT_VARIABLE)
    if override:
        return Path(override)
    if socket.gethostname().split(".")[0] == LOG_STORE_HOSTNAME:
        return LOG_STORE_FILE_ON_NED_BOX
    return home / STATE_DIRECTORY_UNDER_HOME / LOG_FILE_NAME_ELSEWHERE


def state_directory(environment, home):
    override = environment.get(STATE_ENVIRONMENT_VARIABLE)
    return Path(override) if override else home / STATE_DIRECTORY_UNDER_HOME


def append_log_line(path, entry):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as log:
            log.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def claim_once_per_session(directory, key):
    """True for the first caller with this key; the marker file is the claim."""
    safe_key = re.sub(r"[^A-Za-z0-9_.-]", "_", key)[:200] or "unknown-session"
    directory.mkdir(parents=True, exist_ok=True)
    try:
        with open(directory / f"{safe_key}.reminded", "x", encoding="utf-8") as marker:
            marker.write(datetime.now(timezone.utc).isoformat() + "\n")
    except FileExistsError:
        return False
    return True


def run(stdin_text, environment, home, now):
    """Return the text to print, or None; append what it decided to the log."""
    payload = json.loads(stdin_text)
    event = payload.get("hook_event_name") or "Stop"
    if payload.get("stop_hook_active"):
        return None
    if event == "SubagentStop":
        transcript_path = payload.get("agent_transcript_path")
        if not transcript_path:
            return None
    else:
        transcript_path = payload.get("transcript_path")
    if not transcript_path:
        return None
    reply, locator_ran = read_turn(Path(transcript_path).expanduser())
    matches = absence_claim_matches(reply)
    if not matches:
        return None
    session_key = str(payload.get("session_id") or "unknown-session")
    if event == "SubagentStop":
        session_key += "-" + str(payload.get("agent_id") or "unknown-agent")
    headless = bool(environment.get("NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER")
                    or environment.get("CLAUDE_CODE_SESSION_ATTENDED") == "0")
    if headless:
        outcome = "headless"
    elif locator_ran:
        outcome = "locator_ran"
    elif claim_once_per_session(state_directory(environment, home), session_key):
        outcome = "reminded"
    else:
        outcome = "already_reminded"
    append_log_line(log_path(environment, home), {
        "time": now.isoformat(),
        "event": event,
        "session_id": payload.get("session_id"),
        "agent_id": payload.get("agent_id"),
        "cwd": payload.get("cwd"),
        "outcome": outcome,
        "matches": [{"pattern": number, "phrase": phrase} for number, phrase in matches],
        "reply": reply[:REPLY_TEXT_LOGGED_CHARACTERS],
    })
    if outcome != "reminded":
        return None
    matched = ", ".join(f'"{phrase}"' for _, phrase in matches[:3])
    return json.dumps({"decision": "block",
                       "reason": REMINDER_TEMPLATE.format(matched=matched)},
                      ensure_ascii=False)


def measure_precision(labels_path):
    counts = {"CORRECT": 0, "INCORRECT": 0, "UNCLEAR": 0}
    with open(labels_path, encoding="utf-8", newline="") as labels:
        for row in csv.DictReader(labels):
            if absence_claim_matches(row["reply_text"]):
                counts[row["label"]] = counts.get(row["label"], 0) + 1
    fires = sum(counts.values())
    precision = counts["CORRECT"] / fires if fires else 0.0
    print(f"fires {fires}: correct {counts['CORRECT']}, incorrect "
          f"{counts['INCORRECT']}, unclear {counts['UNCLEAR']}; "
          f"precision {precision:.4f}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--measure-precision", metavar="LABELS_CSV")
    arguments = parser.parse_args(argv)
    if arguments.measure_precision:
        return measure_precision(arguments.measure_precision)
    stdin_text = sys.stdin.read()
    try:
        output = run(stdin_text, os.environ, Path.home(), datetime.now(timezone.utc))
    except Exception as error:
        try:
            append_log_line(log_path(os.environ, Path.home()), {
                "time": datetime.now(timezone.utc).isoformat(),
                "outcome": "error",
                "error": f"{type(error).__name__}: {error}",
            })
        except Exception:
            pass
        return 0
    if output is not None:
        try:
            print(output)
        except Exception:
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
