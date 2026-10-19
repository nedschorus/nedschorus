#!/usr/bin/env python3
"""Stop and SubagentStop hook: once per agent-session, remind an agent that
has just told someone a file or record is gone, missing or cannot be found to
run scripts/locate-file-copies-across-machines.py first.

Wired as a Stop and a SubagentStop hook in .claude/settings.json.

THE TRIGGER is the agent's last reply of the turn, read from the transcript:
the text blocks of the last assistant message that has text, since the last
message the user (or, for a subagent, its parent) sent. absence_claim_matches()
decides whether that reply claims a stored artifact is absent. It is five
phrase patterns, 2, 4, 6 and 12, numbered after the larger detector they were
chosen from, and 13, for "does not exist" and "no longer exists", with the
guards measured alongside them. Patterns 2 and 13 count only when a word
naming a stored artifact stands in the match's own clause. On 278
hand-labelled replies, about six fires in seven were correct. Matches inside
code, quoted text and block quotes do not count.

THE HOOK STAYS SILENT when any of these holds:
  - this Stop ends the agent's answer to a Stop hook's output (the shared
    rule of nc-systems/general-tools/claude-code-stop-hooks-stay-silent-while-agent-answers-a-stop-hook-rule-common.py);
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
    transcript holds the parent's reply, not the subagent's;
  - the transcript the payload names does not exist (reading it raises
    FileNotFoundError): Claude Code sends that for most subagent stops, and
    rarely for a Stop, so it is the ordinary case, not a fault, and nothing
    is logged for it. Any other error reading it, such as a permission
    error, is a fault.

OUTPUT when it reminds: {"decision": "block", "reason": <reminder>}, which
keeps the agent going with the reminder as its next instruction. At
SubagentStop the reminder also tells the subagent to end with its whole
report again, because Claude Code hands the dispatching agent only the
subagent's last message, and a reply to the reminder alone would replace the
report.

THE LOG gets one JSON line per triggering reply, whatever the outcome
(reminded, locator_ran, already_reminded, headless), and one per internal
error, so precision can be rechecked from what the hook saw. On ned-box it is
the log-store file LOG_STORE_FILE_ON_NED_BOX; elsewhere it is under
~/.local/state/claude/, for shipping to the log-store later, because a hook
must not wait on ssh. NEDSCHORUS_ABSENCE_CLAIM_REMINDER_LOG overrides the
path, and NEDSCHORUS_ABSENCE_CLAIM_REMINDER_STATE_DIRECTORY overrides where
the once-per-session markers go.

A fault, such as a payload that is not a JSON object, a transcript that
cannot be read or any exception: the error is logged as above, one line goes
to stderr naming the hook and the fault, nothing goes to stdout, and the hook
exits 1. No program reads the log's error lines, so stderr is where the fault
is seen. Claude Code records a Stop or SubagentStop hook's exit 1 as a
non-blocking error and still ends the turn. Exit 2 would continue the
conversation, and a fault that recurs at every stop would then never let the
agent stop. A log line that cannot be written is not a fault: the log is for
rechecking precision, and the reminder still goes out. The hook then exits 0
and puts the failure in its JSON output's systemMessage, which Claude Code
shows the user; stderr at exit 0 is shown to no one.

--measure-precision LABELS_CSV runs absence_claim_matches() over a labelled
reply file (columns reply_id, label, reply_text; label CORRECT, INCORRECT or
UNCLEAR) and prints the fire counts by label and the precision.
"""
import argparse
import csv
import importlib.util
import json
import os
import re
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

# Every Stop hook obeys this rule first: see the module's docstring.
_stop_hooks_stay_silent_rule_specification = importlib.util.spec_from_file_location(
    "claude_code_stop_hooks_stay_silent_while_agent_answers_a_stop_hook_rule_common",
    Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
    / "claude-code-stop-hooks-stay-silent-while-agent-answers-a-stop-hook-rule-common.py")
stop_hooks_stay_silent_rule = importlib.util.module_from_spec(_stop_hooks_stay_silent_rule_specification)
_stop_hooks_stay_silent_rule_specification.loader.exec_module(stop_hooks_stay_silent_rule)

SKILL_NAME = "locate-before-saying-a-file-is-missing"
LOCATOR_PROGRAM_NAME = "locate-file-copies-across-machines.py"
# A person ("human"), another session or a subagent handing back ("peer"), and
# a parent session writing to its subagent ("coordinator"): the agent answers each.
TURN_STARTING_ORIGIN_KINDS = ("human", "peer", "coordinator")
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

REMINDER_HEAD = (
    "absence-claim reminder: your reply says a file or record is gone, missing "
    "or cannot be found ({matched}), and you have not run the locator this "
    "turn. Files agents call missing are often in another checkout, the "
    "log-store, a transcript or a backup.\n"
    "Before you tell anyone it does not exist, run: python3 "
    "scripts/locate-file-copies-across-machines.py <the file's name>\n"
)
REMINDER_TEMPLATE = REMINDER_HEAD + (
    "If the locator finds it, tell whoever read your reply that it is not "
    "missing, and where it is.\n"
    "If the locator finds nothing, say where you looked, not that the file "
    "does not exist.\n"
    "If your reply was not about a stored file or record, carry on; this "
    "reminder comes once per session."
)
SUBAGENT_REMINDER_TEMPLATE = REMINDER_HEAD + (
    "The agent that dispatched you receives only your last message, so what "
    "you write now replaces your report unless it contains the report.\n"
    "If the locator finds it, end with your whole report again, with that "
    "claim corrected to say where the file is.\n"
    "If the locator finds nothing, end with your whole report again, with "
    "that claim saying where you looked, not that the file does not exist.\n"
    "If your reply was not about a stored file or record, say so in one line, "
    "then end with your whole report again, unchanged; this reminder comes "
    "once per subagent."
)

# The pattern numbers are kept from the detector these were measured in, so
# the guards below read the same as in the measurement.
PATTERNS = {
    2: r"\b(?:is|are|was|were|it's|they're)\s+(?:(?:now|all|still)\s+)?(?:gone|missing|lost|absent|unrecoverable)\b",
    # Only adverbs may stand between the negation and the verb: "can't reliably find", not "didn't say where to find".
    4: r"\b(?:can not|cannot|can't|could not|couldn't|did not|didn't|do not|don't|unable to|failed to)\s+(?:(?:yet|still|ever|even|actually|really|reliably|directly|quickly|immediately|always)\s+){0,3}(?:find|locate|recover)\b",
    6: r"\b(?:not|isn't|aren't|wasn't|weren't)\s+(?:present\s+)?(?:on disk|in (?:the |this |any |our |my )?(?:mirror|log[- ]store|repo(?:sitory)?|checkout|git history|branch|transcript|backup))\b|\bon no branch\b",
    13: r"\b(?:does not|doesn't|did not|didn't|no longer)\s+exists?\b|\bnever existed\b",
    12: r"\bno\s+(?:user turn|reply|response)(?:\s+from you)?\s+(?:in between|between)\b|\b(?:you never (?:gave|said yes)|ruling you never gave)\b",
}
COMPILED = {number: re.compile(pattern, re.I) for number, pattern in PATTERNS.items()}

# Pattern 2 fires only when a stored artifact is named in its own clause, just before the match. A hyphen
# next to the word ("per-path", "file-by-file") makes it a modifier, not the artifact.
ARTIFACT = re.compile(r"(?<![\w-])(?:FILE|files?|documents?|drafts?|transcripts?|records?|copies|copy|backups?|paths?|directories|directory|folders?|artifacts?|overviews?|reports?|logs?|history|traces?|mirrors?|checkouts?|repos?|issues?|citations?|rulings?|approvals?|prompts?|minutes|data|results?)(?![\w-])", re.I)
CLAUSE_BREAK = re.compile(r"[;:(—–]|\s-\s")
# Code and text elements an edit removes; "the fallback is gone" reports a change, not a missing artifact.
EDITED_ELEMENT = re.compile(r"\b(?:parsing|parser|lookup|comparison|rules?|guards?|comments?|fallback|scan|tail|property|words?|phrases?|names?|command|gap|rows?|arithmetic|waker|advice|alignment|minimum|mod|change|premise|reason|case|binary|style|options?|flags?|code|helper|function|stand-ins)\s*$", re.I)
EDITED_HEAD = re.compile(r"\b(?:rules?|comparison|owner|guards?|scan|lock|lookup|minimum|change|parsing|arithmetic|waker|code|comments?|refusal|cases?|checks?|format|steps?|fork|clog|command|words|mark|link|alignment|distinction|mod)\b", re.I)
FIRST_PERSON = re.compile(r"\b(?:I|[Ww]e|[Mm]y|[Oo]ur|me|us)\b")
SCORING_REPLY = re.compile(r"\b(?:match file|match to|report covers|answer-key entries)\b", re.I)


def strip_noise(text):
    """Remove what an agent quotes rather than asserts: fenced and indented
    code, block quotes, inline code, link targets, emphasis and double-quoted
    text. An inline code span that looks like a path, one with no space that
    holds a slash or a file extension, becomes the word FILE."""
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
        # A slash or a file extension marks a path; a tilde alone does not,
        # since agents backquote a lone ~ as a character, and ~/x has a slash.
        if re.search(r"(?:/|\.[a-zA-Z0-9]{1,8}\b)", body) and not re.search(r"\s", body):
            return " FILE "
        return " "
    text = re.sub(r"(`+)([^`\n]*?)\1", inline, text)
    text = re.sub(r"\[([^\]\n]+)\]\([^\n)]*\)", r"\1", text)
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r'"[^"\n]*"', " ", text)
    text = re.sub(r"“[^”\n]*”", " ", text)
    return text


def clause_before(before):
    """The text after the last clause break before the match: the match's own subject, roughly."""
    return CLAUSE_BREAK.split(before)[-1][-80:]


def match_is_excluded(number, sentence, before, after):
    """True when the sentence around a match shows it is not an absence claim."""
    clause = clause_before(before)
    is_pattern_13 = number == 13
    if is_pattern_13:
        # Pattern 13 needs a stored artifact in its clause or a place after it ("does not exist on main"),
        # and is read like pattern 2 by every other guard.
        if not re.search(ARTIFACT.pattern + r"|\bbranch(?:es)?\b", clause, re.I) and not re.match(r"\s+(?:yet\s+)?(?:on|in|anywhere)\b", after, re.I):
            return True
        # "a file that doesn't exist", "something that doesn't exist": an indefinite noun with a relative clause names a kind.
        if re.search(r"\b(?:an?|any|every|something)\s+(?:[\w'-]+\s+){0,4}(?:that|which)\s+$", before, re.I):
            return True
        # "on a machine where the directory doesn't exist yet": a general case.
        if re.search(r"\bwhere\b", before, re.I):
            return True
        number = 2
    if number == 2 and not is_pattern_13:
        # A pronoun subject ("it is gone", "they're lost") points back past the clause break.
        pronoun = re.search(r"\b(?:it|they|this|these|those)\s+$", before, re.I) or re.match(r"(?:it's|they're)\b", sentence[len(before):], re.I)
        if not ARTIFACT.search(before[-100:] if pronoun else clause):
            return True
    if number == 4 and re.search(r"\b(?:commands?|services?|hosts?|programs?|readers?)\b", sentence, re.I) and not ARTIFACT.search(sentence):
        return True
    if re.search(r"\b(?:if|unless|when|whenever|would|should|will)\b", before, re.I):
        return True
    if number == 2 and re.search(r"\b(?:none|nothing|no (?:work|edits?|files?))\b", before, re.I):
        return True
    if number == 2 and re.search(r"\b(?:setting|option|field|flag|heading|section|sentence|clause|line|entry|entries|pid|process|supervisor|thread|cause|exception)\b[^,;:]{0,35}$", before, re.I):
        return True
    # A fact, not an artifact: "I did not find out which run wrote it", "What I can't recover: who set the template".
    if number == 4 and re.match(r"\s*[:\u2014-]?\s*(?:out\s+)?(?:which run|who|how|why)\b", after, re.I):
        return True
    if number == 4 and re.match(r"\s+this shape\b", after, re.I):
        return True
    if re.search(r"\beither\b", before, re.I) and re.search(r"\bor\b", after, re.I):
        return True
    if re.search(r"\b(?:does not|doesn't|never)\s+say\b", before[-100:], re.I):
        return True
    if re.search(r"\buntil\b|(?<!at )\bonce\b", before, re.I):
        return True
    if re.search(r"\bcould\b", before, re.I):
        return True
    # A relative clause with "whose" names a kind of thing: "a worktree whose git directory is missing".
    if number == 2 and re.search(r"\bwhose\b[^,;:.]{0,40}$", before, re.I):
        return True
    # Talk about claims in the match's own clause, or what someone says just before the match, is not a claim.
    if re.search(r"\bclaim(?:s|ing|ed)?\b|\b(?:not|isn't) true\b", clause, re.I):
        return True
    if re.search(r"\b(?:say|says|said|saying)\s+(?:[\w'-]+\s+){0,5}$", before, re.I):
        return True
    # "no test case on main is lost", "nobody's lines are lost".
    if number == 2 and re.search(r"\b(?:no|nobody's|neither)\s+(?:[\w'-]+\s+){0,4}$", before, re.I):
        return True
    # What a test or check verifies: "the tests check that the temporary folder is gone".
    if re.search(r"\b(?:tests?|checks?)\s+(?:\w+\s+){0,2}(?:that|whether)\b", before, re.I):
        return True
    # Pattern 2 on an edited code or text element: "the untested guards are gone".
    if number == 2 and EDITED_ELEMENT.search(before.rstrip()):
        return True
    # Alternatives in a case analysis: "its file is gone", "is missing or stale".
    if number == 2 and (re.match(r"\s+or\b", after, re.I) or re.search(r"\bor\s+(?:[\w'-]+\s+){0,3}$", before, re.I)):
        return True
    # Pattern 4 whose subject is a program, a search or agents in general: "the locator ... so it can't find an approval",
    # "Keyword search cannot find reviewers", "agents can't find your answer" describe what something can do.
    if number == 4 and not FIRST_PERSON.search(clause) and re.search(r"\b(?:it|they|agents?|search|test|hook|locator|guard|program|script|reader|checker)\s+$", before, re.I):
        return True
    # "couldn't find a stronger case for N", "a term for": an argument or a word, not an artifact.
    if number == 4 and re.match(r"\s+(?:a|any)\s+(?:[\w-]+\s+){0,2}(?:case|argument|reason|term|word|replacement)s?\b", after, re.I):
        return True
    # Pattern 6 on a file said to live elsewhere: it exists, and the sentence says where.
    if number == 6 and re.search(r"\b(?:lives?|sits?)\s+in\b|\bexists? only\b|\b(?:machine|seat)-local\b|\bgit-?ignored\b", sentence, re.I):
        return True
    # A relative clause describes a kind: "rulings an agent asked for that you never gave".
    if number == 12 and re.search(r"\b(?:that|which)\s+(?:(?:is|are|was|were)\s+)?$", before, re.I):
        return True
    # A definition: "step 4 uses the word for another file: the old version kept beside a revised text that is not in the repository".
    if number == 6 and re.search(r"\b(?:uses?|means|refers? to|stands? for)\b", before, re.I):
        return True
    # "missing" as a verb: "the record is missing a field".
    if number == 2 and re.match(r"\s+(?:a|an|something)\b", after, re.I) and "missing" in sentence[len(before):].lower():
        return True
    # A future moment, a test case or every run: "the moment the move lands, that path is gone".
    if number == 2 and re.search(r"\b(?:checks? on|case where|the moment|on any run)\b", before, re.I):
        return True
    # A kind named by a relative clause: "a folder that is missing", "any reports whose file is gone".
    if number == 2 and re.search(r"\b(?:a|an|any)\s+(?:\w+\s+){0,3}(?:worktree|checkout|folder|file|report)\s+(?:that|whose)\b", before, re.I):
        return True
    if number == 2 and re.search(r"\b(?:those|any)\b.*\b(?:whose|that)\b", before, re.I):
        return True
    if number == 2 and re.search(r"\b(?:advice|conditional)\b", before, re.I):
        return True
    # A removed code element is the head of the match's clause, after any artifact word: "TR1's checks on FILE are gone".
    if number == 2:
        clause_after_comma = re.split(r"[,;:]", before)[-1]
        heads = list(EDITED_HEAD.finditer(clause_after_comma))
        artifacts = list(ARTIFACT.finditer(clause_after_comma))
        if heads and (not artifacts or heads[-1].start() >= artifacts[-1].start()):
            return True
    # What a search tool can do: "grep and glob don't find branch names".
    if number == 4 and re.search(r"\b(?:the locator|keyword search|grep and glob|the pre-push hook|the search)\b", sentence, re.I) and re.search(r"\b(?:cannot|can't|don't)\b", sentence, re.I):
        return True
    # "Records like these belong in the log-store, not in the repository": where things should go.
    if number == 6 and re.search(r"\bbelongs?\b", re.split(r"[;:]", before)[-1], re.I):
        return True
    # "a commit on no branch": a kind of commit.
    if number == 6 and re.search(r"\b(?:a|an|any)\s+commit\s*$", before, re.I):
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
    # Claude Code marks peer messages, subagent hand-backs and a parent's
    # messages isMeta too, so the origin kind decides before isMeta does.
    origin_kind = (record.get("origin") or {}).get("kind")
    if origin_kind == "task-notification":
        return False
    if origin_kind not in TURN_STARTING_ORIGIN_KINDS and record.get("isMeta"):
        # A loaded skill's text, a system reminder or hook feedback, written
        # inside the turn that caused it.
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
    """Append entry to the log at path; return None, or why it could not be written."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as log:
            log.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as error:
        return f"{type(error).__name__}: {error}"
    return None


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
    if not isinstance(payload, dict):
        raise ValueError("the input on the hook's stdin is JSON, but not an object")
    event = payload.get("hook_event_name") or "Stop"
    if stop_hooks_stay_silent_rule.stop_hook_stays_silent_while_agent_answers_a_stop_hook(payload):
        return None
    if event == "SubagentStop":
        transcript_path = payload.get("agent_transcript_path")
    else:
        transcript_path = payload.get("transcript_path")
    if not transcript_path:
        return None
    try:
        reply, locator_ran = read_turn(Path(transcript_path).expanduser())
    except FileNotFoundError:
        return None
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
    path = log_path(environment, home)
    log_failure = append_log_line(path, {
        "time": now.isoformat(),
        "event": event,
        "session_id": payload.get("session_id"),
        "agent_id": payload.get("agent_id"),
        "cwd": payload.get("cwd"),
        "outcome": outcome,
        "matches": [{"pattern": number, "phrase": phrase} for number, phrase in matches],
        "reply": reply[:REPLY_TEXT_LOGGED_CHARACTERS],
    })
    output = {}
    if outcome == "reminded":
        matched = ", ".join(f'"{phrase}"' for _, phrase in matches[:3])
        template = SUBAGENT_REMINDER_TEMPLATE if event == "SubagentStop" else REMINDER_TEMPLATE
        output.update({"decision": "block", "reason": template.format(matched=matched)})
    if log_failure:
        reached = ("The reminder to run the locator was still sent to the agent."
                   if outcome == "reminded" else "No reminder was due, so none was sent to the agent.")
        output["systemMessage"] = (
            f"absence-claim-locator-reminder-hook: the outcome {outcome!r} of checking the last "
            f"reply was not logged to {path}: {log_failure}. {reached} A recheck of the hook's "
            f"precision will miss this reply; make {path} a file that can be written, or set "
            f"{LOG_ENVIRONMENT_VARIABLE} to one.")
    return json.dumps(output, ensure_ascii=False) if output else None


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
    try:
        output = run(sys.stdin.read(), os.environ, Path.home(), datetime.now(timezone.utc))
        if output is not None:
            print(output)
    except Exception as error:
        try:
            log_failure = append_log_line(log_path(os.environ, Path.home()), {
                "time": datetime.now(timezone.utc).isoformat(),
                "outcome": "error",
                "error": f"{type(error).__name__}: {error}",
            })
        except Exception as log_error:
            log_failure = f"{type(log_error).__name__}: {log_error}"
        not_logged = f"; the failure was not logged either: {log_failure}" if log_failure else ""
        print(f"absence-claim-locator-reminder-hook: the hook failed with "
              f"{type(error).__name__}: {error}{not_logged}. So the last reply was not checked "
              f"for a claim that a file is missing, no reminder reached the agent, and the turn "
              f"ends as usual. If this recurs, run python3 "
              f"scripts/absence-claim-locator-reminder-hook-test.py and tell the user what it "
              f"reports.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
