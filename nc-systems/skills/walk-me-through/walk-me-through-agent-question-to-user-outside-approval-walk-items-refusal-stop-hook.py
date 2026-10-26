#!/usr/bin/env python3
"""Stop hook: while an approval-walk is open, block the agent's stop when its
reply asks the user something outside the walk's items, so that the question
becomes an interruption item and his letter always answers the one item
waiting.

Wired as a Stop hook in .claude/settings.json, beside the current-item Stop
hook, walk-me-through-current-item-shown-to-user-after-each-agent-message-stop-hook.py,
whose turn and transcript readers this hook loads, and the approval-walk
finder, walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py,
which finds the open walk, its waiting items and its walk-document's items. It
also loads the answer hook,
walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py,
for the closing line's answer letters, ANSWER_LETTERS_TEXT.

EVERY TURN is checked, whoever started it: the user, another agent-seat, a
background-task notice. THE REPLY is the text of every assistant message
since the turn's start, a prompt the user typed into the turn included, plus
the Stop payload's `last_assistant_message`, because Claude Code can start
the Stop hook before it has written the final message to the transcript.

THE TEXT CHECKED is the reply, line by line, without:
- every item of the walk-document the reply shows: an item is shown when a
  reply line matches its heading, and then every reply line matching a line
  of the item, from its heading to its answer line, is left out, and so is
  one matching the answer line's first sentence, the walk-me-through skill's
  answer line without what the item adds after it, such as ` D: <the
  alternative>`; lines match when they are equal once markdown emphasis,
  heading and list marks, link targets, spacing and case are dropped;
- fenced and indented code and code spans;
- quoted text, `"..."`, `“...”` or a `>` line, that the walk-document holds;
- a waiting item's closing line, the line the walk-me-through skill ends
  every message with, `[Item 4 of 9, <the point>](<page link>) · ` and then
  the answer hook's ANSWER_LETTERS_TEXT, when the item it names is waiting and
  its total is the open walk's; its point and link are not compared, since the
  agent writes its own point and the user's letter after the line answers
  that item whatever the point says, and a link target is not text he reads;
  a line that names another item or total, or adds anything before or after
  the line, is checked;
- a sentence that only names waiting items, `Item 4 of 9 is waiting for your
  answer.`, the line the walk-me-through skill ended every message with before
  the closing line, when every item it names is waiting and its total is the
  open walk's or one an item heading of the walk-document carries; one that
  names another item or total, as an agent does when it numbers its own
  questions as items, is checked.
`**` and `__` are dropped before the tests, so a bold question is read.

EACH LINE is one of three:
- a clear ask: a sentence ending in `?`, or a phrase in CLEAR_ASK such as
  `say yes`, `should I` or `waiting for your answer`; it blocks, unless the
  line also names an item by number, which makes it unclear, because a
  reminder of a walk item's own question asks nothing new;
- unclear: a `?` inside the line, or a phrase in UNCLEAR_ASK such as `I
  recommend` or `whether to`;
- not question-like: everything else; it passes.
When no line is a clear ask and some are unclear, the unclear lines go to
the model MODEL in one headless `claude -p` call, which says whether one of
them asks the user to decide or answer something. The child runs with every
hook disabled, so this hook cannot run inside it, no session file, no tools,
and a cwd outside any checkout. When the call fails or runs past
MODEL_TIMEOUT_SECONDS, the hook blocks on the first unclear line, saying the
model check failed: a missed question scrolls away, a false block costs one
reworded line.

AN INTERRUPTION ITEM'S TEXT is not checked either: a line of the text
checked, a list joined to its lead-in included, is left out when the
walk-document, as it stands when the hook runs, holds each line of it, as
the agent wrote it, as a whole line of one interruption item, one numbered
`W.n` after a waiting item W and not itself waiting, whatever its total.
Lines are compared whole and equal once `normalized` has dropped their marks,
so a leading `>` or list mark, bold, italic and code-span marks, link targets,
spacing and case do not count, and a line left empty once they are dropped,
such as a list line holding only `*` in code marks, is not compared on either
side: a line that
is only part of an item's line, or that holds more than it, is not held. The
lines are compared as the agent wrote them, before the removals above,
because the item holds the question as its asker wrote it, code spans and
quotations included; the refusal names them as written, and its step 1 tells
the agent to copy each into the item as a line of its own, refusing until
the item holds them so. An item's lines run from its opening,
as the approval-walk finder reads openings, when it has one, to the next
item's opening or its unit's end, and are otherwise its whole unit; but an
item without an opening under a heading shared by several items holds no
lines. So a question the
agent has put into an interruption item passes, however that item got there
or was later retitled, and a question in any other item does not.

EACH BLOCK is logged as one JSON line, with its time, session, walk, the
sentence flagged, and what decided, `code`, `model` or `model-check-failed`,
to LOG_FILE_NAME at the top of the log-store, as ned-box reaches it or as
the Mac's mount of ned-box's home reaches it; LOG_PATH_VARIABLE overrides the
path. When neither is reachable, or the write fails, the block's reason says
the block was not logged.

SILENT while the agent answers a Stop hook (stop_hook_active set), as the
Stop-hook silence rule's module requires; in a headless `claude -p` child;
when the transcript or the cwd's checkout is missing; when no approval-walk is
open; when the turn wrote no text; and when the open walk's minutes line or
walk-document cannot be read, which the current-item Stop hook reports at the
next turn the user starts.

OUTPUT: {"decision": "block", "reason": <message>}. ON A FAULT, such as input
that is not JSON or a file it cannot read, the hook prints one line naming it
on stderr and exits 1: Claude Code records a Stop hook's exit 1 as a
non-blocking error and still ends the turn.

Agent-facing messages follow
docs/nedschorus-wiki/nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md.
"""
import datetime
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CURRENT_ITEM_HOOK_FILE = HERE / "walk-me-through-current-item-shown-to-user-after-each-agent-message-stop-hook.py"
WALK_FINDER_FILE = HERE / "walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py"
ANSWER_HOOK_FILE = (HERE / "walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-"
                    "user-prompt-submit-hook.py")
REPOSITORY_TOP = HERE.parents[2]
STOP_HOOKS_STAY_SILENT_RULE_FILE = (
    REPOSITORY_TOP / "nc-systems" / "general-tools"
    / "claude-code-stop-hooks-stay-silent-while-agent-answers-a-stop-hook-rule-common.py")
PATH_CONSTANTS_FILE = (REPOSITORY_TOP / "nc-systems" / "general-tools"
                       / "ned-box-home-directory-and-its-mac-mount-point-path-constants-common.py")

MODEL = "claude-haiku-5-5"
MODEL_TIMEOUT_SECONDS = 25
LOG_STORE_DIRECTORY_NAME = "nedschorus-logs"
LOG_FILE_NAME = "walk-me-through-agent-question-to-user-outside-approval-walk-items-refusal-stop-hook-refusals.jsonl"
LOG_PATH_VARIABLE = "NEDSCHORUS_WALK_ME_THROUGH_AGENT_QUESTION_REFUSAL_LOG"

NUMBER_LIST = r"\d+(?:\.\d+)*(?:\s*(?:,|&|\band\b|\bto\b|-|–)\s*\d+(?:\.\d+)*)*"
ITEM_REFERENCE = re.compile(r"\bitems?\s+\d+(?:\.\d+)*", re.I)
WAITING_REMINDER = re.compile(
    rf"^(?:the\s+)?items?\s+(?P<numbers>{NUMBER_LIST})\s+of\s+(?P<total>\d+)\s+(?:is|are)\s+(?:still\s+)?waiting"
    r"\s+for\s+your\s+answer\W*$",
    re.I)
CLEAR_ASK = re.compile(
    # The letter A is matched in capitals only, because a lowercase `a` there is the article, as in `answer a finding`.
    r"\b(?:say|reply|answer|type)\s+(?:yes|no|y|n|ao|d|(?-i:A))\b|\bon\s+(?:a|your)\s+(?:yes|no)\b"
    r"|\byour\s+yes\s+or\s+no\b|\bdo\s+you\s+(?:want|agree)\b|\bshould\s+I\b|\bshall\s+I\b|\bwant\s+me\s+to\b"
    r"|\bwould\s+you\s+like\b|\bwaiting\s+(?:on|for)\s+your\s+(?:answer|word|decision|ruling|approval|go-ahead|yes)\b"
    r"|\bneeds?\s+your\s+(?:answer|decision|ruling|approval|word|go-ahead|yes)\b"
    r"|\b(?:tell\s+me|let\s+me\s+know)\s+(?:if|whether|which)\b|\bplease\s+(?:confirm|approve|decide|choose|pick|rule)\b",
    re.I)
UNCLEAR_ASK = re.compile(
    r"\brecommend|^\W*recommendation:|\bI\s+suggest\b|\blet\s+me\s+know\b|\btell\s+me\b|\basking\s+you\b"
    r"|\bwaiting\s+(?:on|for)\s+(?:you|your)\b|\bstill\s+open\b|\bneeds?\s+(?:you|your)\b|\bwhether\s+(?:I|to|we)\b"
    r"|\bA\s+or\s+D\b|\bY\s+or\s+N\b|\brule\s+once\b|\byou(?:'d|\s+would|\s+must|\s+need\s+to)?\s+rule\s+on\b"
    r"|\byour\s+(?:yes|word|call|go-ahead|approval|decision|choice|pick|ruling)\b"
    r"|\b(?:yes|no)\s+(?:adds|means|keeps|drops|leaves)\b|\bif\s+you\s+(?:agree|prefer|want|approve|'d\s+rather)\b"
    r"|\bunless\s+you\b|\b(?:would|could|can)\s+you\b|\bup\s+to\s+you\b",
    re.I)
# A sentence ends at its stop, or just after a closing quote, bracket or bold mark that follows the stop.
SENTENCE_END = re.compile(r"(?:(?<=[.?!])|(?<=[.?!][\"'\u201d\u2019)*_]))\s+")
TRAILING_MARKS = "*_ )\"'”’"
QUOTED = re.compile(r"\"[^\"\n]+\"|“[^”\n]+”")
LINK = re.compile(r"\[([^\]\n]*)\]\([^)\n]*\)")
LIST_ITEM = re.compile(r"^(?:[-+*]|\d+[.)])\s")
LINE_MARKS = re.compile(r"^\s*(?:(?:[-+*>]|\d+[.)])\s+)+")
EMPHASIS_AND_SPACING = re.compile(r"[\s*_#>`]+")
ANSWER_LINE_START = "answer a to approve"

MODEL_SCHEMA = {"type": "object",
                "properties": {"asks_user": {"type": "boolean"}, "line_number": {"type": "integer"}},
                "required": ["asks_user", "line_number"], "additionalProperties": False}
MODEL_SYSTEM_PROMPT = "You classify text. Answer only through the structured output."
MODEL_PROMPT_TEMPLATE = """An agent is taking the user through an approval-walk: numbered items, each of which he answers with a letter. While the walk is open, the agent must ask him nothing outside a walk item, because his next letter could then answer either question. This walk's items are named `Item N of {total}`, or `item N` for short, and item {waiting} waits for his answer; an item numbered some other way, such as a "side item" or an item with another total, is not one of the walk's items.

Below is one of the agent's messages, with any walk item it shows removed, and then the lines of it that the agent's code could not judge, numbered. Use the message as context, and judge only the numbered lines. Does any numbered line ask the user to decide, approve, choose or answer something?

Count as asking: a question to him; a recommendation he is expected to approve or reject, rather than advice that needs no answer; a question from another agent passed on to him; a reminder that a question that is not one of the walk's items still waits for him; a request for him to report something back, such as what a command printed.
Do not count: a line that only reminds him that one of the walk's items waits for his answer; a question the agent answers itself; a report of what someone asked someone else, not passed to him; a request only to run a command or open a file.

Set asks_user to true when a numbered line asks him something and to false otherwise, and set line_number to the number of the first such line, or to 0 when none does.

The message:
<message>
{message}
</message>

The numbered lines:
{lines}"""

REFUSAL_OPENING_TEMPLATE = (
    "approval-walk question check: this hook refused to end your turn on purpose, because your reply seems to "
    "ask the user something outside an item of the open approval-walk {walk} ({decided}). The flagged text: "
    "\"{sentence}\". While a walk is open the user's answer goes to the waiting item, item {waiting}, so a "
    "question asked in prose leaves him unable to tell which question his letter answers.")
DECIDED_BY_CODE_NOTICE = "the hook's code read it as a clear question"
DECIDED_BY_MODEL_NOTICE = "the model judged that it asks him something"
MODEL_CHECK_FAILED_NOTICE = ("the hook's `claude -p` call that has the model judge this unclear text failed, "
                             "{failure}, so the hook treats the text as a question")
REFUSAL_INSTRUCTIONS = (
    "If the flagged text asks the user to decide or answer something, do these four steps:",
    "1. Add it to the walk-document {document} as an interruption item headed `## Item {new_item} of "
    "{new_total}: <the point of the question>`, placed right after item {last_waiting}. Quote the question whole "
    "in the item, as its asker wrote it, whether you or another agent, giving each line of the flagged text a "
    "line of its own, word for word, and putting the rest of the question on other lines of the item. This hook passes the "
    "question only when the item in the walk-document holds every flagged line that way, and refuses again until "
    "it does; it ignores a `>` quote mark or a list mark such as `-` or `1.` at the start of a line, bold, italic "
    "and code marks, and letter case, so you may add or drop those. "
    "Give your recommendation as `Recommendation: <what you recommend doing>.`, and end the item with "
    "{answer_line}.",
    "2. Change the walk's item count M from {total} to {new_total} in every item heading of {document} that "
    "carries `of {total}`, and in "
    "the last `#next_to_present` line of {minutes}, which then reads `#next_to_present {waiting_value} of "
    "{new_total}`.",
    "3. Do not show the new item now: it is shown after item {waiting} is answered.",
    "4. The flagged text has already reached the user, so leave it; end the message you write next with these "
    "two lines: `I added the question as Item {new_item} of "
    "{new_total}.` and `{waiting_reminder}`",
    "If the flagged text does not ask the user anything, reword it in your reply so that it no longer reads "
    "as a question for him, and end the turn.",
    "From now on, while an approval-walk is open, put every question for the user, yours or another "
    "agent's, into the walk as an item instead of asking it in prose.",
)
ANSWER_LINE_IN_DOCUMENT_TEMPLATE = "this line, which the walk's other items end with: `{line}`"
ANSWER_LINE_NOT_FOUND_NOTICE = "the answer line the walk's other items end with"
NOT_LOGGED_NOTICE = ("This refusal was not logged, {problem}. If that is because ned-box cannot be reached, tell "
                     "the user that this hook could not log to the log-store on ned-box; otherwise you need not act on it.")


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


walk_finder = load_module("walk_me_through_approval_walk_minutes_and_walk_document_item_finder_common",
                          WALK_FINDER_FILE)
current_item_hook = load_module("walk_me_through_current_item_shown_to_user_after_each_agent_message_stop_hook",
                                CURRENT_ITEM_HOOK_FILE)
answer_hook = load_module(
    "walk_me_through_user_short_answer_to_approval_walk_item_expanded_into_instructions_user_prompt_submit_hook",
    ANSWER_HOOK_FILE)


def normalized(line):
    """The line with link targets, list, quotation and heading marks, emphasis, spacing and case dropped."""
    line = LINE_MARKS.sub("", LINK.sub(r"\1", line))
    return EMPHASIS_AND_SPACING.sub(" ", line).strip().lower()


# Matched against a normalized line, which has lost the link target and the case.
CLOSING_LINE = re.compile(rf"item (?P<number>{walk_finder.NUMBER}) of (?P<total>\d+)(?:, .*)? · "
                          + re.escape(normalized(answer_hook.ANSWER_LETTERS_TEXT)))


def normalized_lines(lines):
    """The set of the lines' normalized forms, without the empty one, which no line of an item can match."""
    return {normalized(line) for line in lines} - {""}


def answer_sentence(line):
    """The walk-me-through skill's answer line at the start of line, without a list or quotation mark before it, and
    without what an item adds after it on the same line, such as the ` D: <the alternative>` some walk-documents add."""
    return SENTENCE_END.split(LINE_MARKS.sub("", line.strip()), maxsplit=1)[0]


def turn_assistant_texts(records):
    """Every assistant text since the transcript's last turn start."""
    start = current_item_hook.turn_start(records)
    texts = []
    for record in records[0 if start is None else start + 1:]:
        content = record.get("message", {}).get("content") if record.get("type") == "assistant" else None
        texts.extend(block.get("text", "") for block in (content if isinstance(content, list) else ())
                     if isinstance(block, dict) and block.get("type") == "text")
    return texts


def interruption_item_texts(document_text, units, waiting_numbers, parser):
    """The set of normalized lines of every item numbered W.n, for W a waiting item, not itself waiting: its lines as the
    approval-walk finder's line-range helper gives them, or nothing when they are the whole of a unit of several
    items, because that unit's items have no openings."""
    document_lines = document_text.split("\n")
    openings = walk_finder.item_opening_lines(document_text, parser)
    texts = []
    for numbers, total, _, first, end in units:
        for number in numbers:
            if number in waiting_numbers or not any(re.fullmatch(rf"{re.escape(waiting)}\.\d+", number)
                                                    for waiting in waiting_numbers):
                continue
            span = walk_finder.approval_walk_item_line_range_within_heading_shared_by_several_items(
                openings, first, end, number, numbers, total)
            if len(numbers) > 1 and span == (first, end):
                continue
            texts.append(normalized_lines(document_lines[span[0]:span[1]]))
    return texts


def shown_item_lines(reply_lines, document_lines, units):
    """The normalized lines, heading to answer line, of every unit whose heading a reply line matches, and the answer
    line's answer sentence alone."""
    reply_set = normalized_lines(reply_lines)
    shown = set()
    for _, _, _, first, end in units:
        if normalized(document_lines[first]) not in reply_set:
            continue
        for line in document_lines[first:end]:
            shown |= normalized_lines([line])
            if normalized(line).startswith(ANSWER_LINE_START):
                shown |= normalized_lines([answer_sentence(line)])
                break
    return shown


def is_closing_line(line, waiting_numbers, total):
    """Whether line is the closing line of a waiting item of the open walk, whose total is total."""
    closing = CLOSING_LINE.fullmatch(normalized(line))
    return bool(closing) and closing["number"] in waiting_numbers and closing["total"] == total


def is_waiting_reminder(sentence, waiting_numbers, totals):
    """Whether sentence only says that waiting items of the open walk, with one of its totals, wait for an answer."""
    reminder = WAITING_REMINDER.match(sentence.strip(TRAILING_MARKS))
    if not reminder or reminder["total"] not in totals:
        return False
    try:
        return set(walk_finder.expand_numbers(reminder["numbers"])) <= set(waiting_numbers)
    except walk_finder.UnusableRange:
        return False


def checked_lines(reply, document_text, units, parser, waiting_numbers, total):
    """The reply's lines as the module docstring's THE TEXT CHECKED says, emphasis dropped, empty ones left out,
    and each list joined to the line ending in `:` that introduces it, so the list is judged with its lead-in;
    then those an interruption item holds, compared as the reply wrote them, left out. Each comes as (the line
    checked, the lines as the reply wrote them)."""
    totals = {total} | {unit[1] for unit in units}
    document_lines = document_text.split("\n")
    normalized_document = normalized(" ".join(document_lines))
    lines = walk_finder.prose_lines(reply, parser)
    shown = shown_item_lines(lines, document_lines, units)
    kept, written, introduced_list = [], [], False
    for line in lines:
        if normalized(line) in shown or is_closing_line(line, waiting_numbers, total):
            continue
        if line.lstrip().startswith(">") and normalized(line) in normalized_document:
            continue
        as_written = line
        line = walk_finder.CODE_SPAN.sub(" ", line)
        line = QUOTED.sub(lambda quote: " " if normalized(quote[0][1:-1]) in normalized_document else quote[0], line)
        line = line.replace("**", "").replace("__", "")
        sentences = [sentence for sentence in SENTENCE_END.split(line.strip())
                     if not is_waiting_reminder(sentence, waiting_numbers, totals)]
        line = " ".join(sentences).strip()
        if not line:
            continue
        if introduced_list and LIST_ITEM.match(as_written.lstrip()):
            kept[-1] += " " + line
            written[-1].append(as_written)
        else:
            kept.append(line)
            written.append([as_written])
            introduced_list = line.endswith(":")
    item_texts = interruption_item_texts(document_text, units, waiting_numbers, parser)
    return [(line, as_written) for line, as_written in zip(kept, written)
            if not any(normalized_lines(as_written) <= text for text in item_texts)]


def line_kind(line):
    """`clear`, `unclear` or None, as the module docstring's EACH LINE says."""
    ends_in_question = any(sentence.rstrip(TRAILING_MARKS).endswith("?") for sentence in SENTENCE_END.split(line))
    if ends_in_question or CLEAR_ASK.search(line):
        return "unclear" if ITEM_REFERENCE.search(line) else "clear"
    if "?" in line or UNCLEAR_ASK.search(line):
        return "unclear"
    return None


def model_judgement(message_lines, unclear_lines, total, waiting, timeout_seconds=MODEL_TIMEOUT_SECONDS):
    """Return (the unclear line the model says asks the user something, or None; None, or why the call failed),
    for the walk whose items have total M and whose item waiting is numbered waiting."""
    prompt = MODEL_PROMPT_TEMPLATE.format(
        total=total, waiting=waiting,
        message="\n".join(message_lines),
        lines="\n".join(f"{number}. {line}" for number, line in enumerate(unclear_lines, 1)))
    command = ["claude", "-p", "--model", MODEL, "--output-format", "json",
               "--json-schema", json.dumps(MODEL_SCHEMA), "--system-prompt", MODEL_SYSTEM_PROMPT,
               "--tools", "", "--settings", json.dumps({"disableAllHooks": True}),
               # Without this every check would leave a session file behind.
               "--no-session-persistence"]
    try:
        completed = subprocess.run(command, input=prompt, capture_output=True, text=True,
                                   timeout=timeout_seconds, cwd=tempfile.gettempdir(), check=False)
    except subprocess.TimeoutExpired:
        return None, f"claude gave no answer within {timeout_seconds} seconds"
    except OSError as error:
        return None, f"claude could not be run: {error}"
    try:
        result = json.loads(completed.stdout)
        verdict = result["structured_output"]
        asks, number = verdict["asks_user"], verdict["line_number"]
    except (ValueError, TypeError, KeyError) as error:
        detail = (completed.stderr or completed.stdout or "no output").strip()[:300]
        return None, f"claude exited {completed.returncode} without a verdict ({error!r}): {detail}"
    if completed.returncode != 0 or result.get("is_error"):
        return None, f"claude exited {completed.returncode} reporting an error: {str(result.get('result'))[:300]}"
    if not asks:
        return None, None
    return unclear_lines[number - 1] if 1 <= number <= len(unclear_lines) else unclear_lines[0], None


def log_path(environment, log_store_homes=None):
    """Return (the refusal log's path, None), or (None, why the log-store cannot be reached); log_store_homes are
    the directories that may hold the log-store, by default ned-box's home and the Mac's mount of it."""
    override = environment.get(LOG_PATH_VARIABLE)
    if override:
        return Path(override), None
    if log_store_homes is None:
        constants = load_module("ned_box_home_directory_and_its_mac_mount_point_path_constants_common",
                                PATH_CONSTANTS_FILE)
        log_store_homes = (constants.NED_BOX_HOME, constants.MAC_MOUNT_OF_NED_BOX_HOME)
    candidates = [Path(home) / LOG_STORE_DIRECTORY_NAME for home in log_store_homes]
    for directory in candidates:
        if directory.is_dir():
            return directory / LOG_FILE_NAME, None
    return None, "because the log-store is reachable at neither " + " nor ".join(map(str, candidates))


def log_refusal(environment, entry):
    """Append entry to the refusal log; return None, or why it was not logged."""
    path, problem = log_path(environment)
    if path is None:
        return problem
    try:
        with open(path, "a", encoding="utf-8") as log:
            log.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as error:
        return f"because {path} could not be written: {error}"
    return None


def next_free_item(waiting, held):
    suffix = 1
    while f"{waiting}.{suffix}" in held:
        suffix += 1
    return f"{waiting}.{suffix}"


def run(stdin_text, environment):
    """Return the text to print, or None."""
    payload = json.loads(stdin_text)
    rule = load_module("claude_code_stop_hooks_stay_silent_while_agent_answers_a_stop_hook_rule_common",
                       STOP_HOOKS_STAY_SILENT_RULE_FILE)
    if rule.stop_hook_stays_silent_while_agent_answers_a_stop_hook(payload):
        return None
    return output_for(payload, environment)


def output_for(payload, environment, model=model_judgement):
    """A block naming the sentence that asks the user something outside the walk's items, or None."""
    if (environment.get("NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER")
            or environment.get("CLAUDE_CODE_SESSION_ATTENDED") == "0"):
        return None
    transcript_path = payload.get("transcript_path")
    if not transcript_path or not Path(transcript_path).expanduser().is_file() or not payload.get("cwd"):
        return None
    top = walk_finder.checkout_top(Path(payload["cwd"]))
    if top is None or not (top / walk_finder.WALK_DIRECTORY).is_dir():
        return None
    parser = walk_finder.markdown_parser()
    walk = walk_finder.open_walk(top / walk_finder.WALK_DIRECTORY, parser)
    if walk is None or walk[2]:
        return None
    minutes, value, _ = walk
    records = current_item_hook.transcript_records(Path(transcript_path).expanduser())
    texts = turn_assistant_texts(records)
    reply = "\n".join(texts + [payload.get("last_assistant_message") or ""])
    if not reply.strip():
        return None
    name = minutes.name[:-len(walk_finder.MINUTES_SUFFIX)]
    document = minutes.with_name(name + ".md")
    try:
        numbers, total = walk_finder.parse_items(value)
        document_text = document.read_text(encoding="utf-8") if document.is_file() else ""
        units = walk_finder.item_unit_spans(document_text, parser)
        total, _ = walk_finder.waiting_item_units(document, value, numbers, total, parser, all_units=units)
    except walk_finder.UnusableRange:
        return None
    checked = checked_lines(reply, document_text, units, parser, numbers, total)
    lines = [line for line, _ in checked]
    kinds = [(line, line_kind(line)) for line in lines]
    clear = [line for line, kind in kinds if kind == "clear"]
    unclear = [line for line, kind in kinds if kind == "unclear"]
    if clear:
        sentence, decided, decided_by = clear[0], DECIDED_BY_CODE_NOTICE, "code"
    elif unclear:
        sentence, failure = model(lines, unclear, total, " and ".join(numbers))
        if failure is not None:
            sentence, decided, decided_by = unclear[0], MODEL_CHECK_FAILED_NOTICE.format(failure=failure), \
                "model-check-failed"
        elif sentence is None:
            return None
        else:
            decided, decided_by = DECIDED_BY_MODEL_NOTICE, "model"
    else:
        return None
    # The agent copies the flagged text into the item, so it is named as written, not as checked.
    sentence = "\n".join(next(written for line, written in checked if line == sentence))
    held = {number for unit in units for number in unit[0]}
    waiting = numbers[-1]
    waiting_label = " and ".join(numbers)
    new_total = str(int(total) + 1)
    answer_lines = [answer_sentence(line) for line in document_text.split("\n")
                    if normalized(line).startswith(ANSWER_LINE_START)]
    values = {"answer_line": (ANSWER_LINE_IN_DOCUMENT_TEMPLATE.format(line=answer_lines[-1]) if answer_lines
                              else ANSWER_LINE_NOT_FOUND_NOTICE),
              "walk": name, "last_waiting": waiting, "sentence": sentence, "decided": decided, "waiting": waiting_label,
              "document": document, "minutes": minutes, "total": total, "new_total": new_total,
              "new_item": next_free_item(waiting, held),
              "waiting_value": ("item " if len(numbers) == 1 else "items ") + waiting_label,
              "waiting_reminder": (f"Item {waiting_label} of {new_total} is waiting for your answer."
                                   if len(numbers) == 1 else
                                   f"Items {waiting_label} of {new_total} are waiting for your answer.")}
    lines_out = [REFUSAL_OPENING_TEMPLATE.format(**values)] + [line.format(**values) for line in REFUSAL_INSTRUCTIONS]
    problem = log_refusal(environment, {
        "time": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "session": payload.get("session_id"), "walk": name, "sentence": sentence, "decided_by": decided_by})
    if problem is not None:
        lines_out.append(NOT_LOGGED_NOTICE.format(problem=problem))
    return json.dumps({"decision": "block", "reason": "\n".join(lines_out)}, ensure_ascii=False)


def main():
    try:
        output = run(sys.stdin.read(), os.environ)
    except Exception as error:
        print(f"walk-me-through-agent-question-to-user-outside-approval-walk-items-refusal-stop-hook: the hook "
              f"failed, so it did not check the reply for a question to the user outside the approval-walk's "
              f"items; the agent need not act: {error!r}", file=sys.stderr)
        return 1
    if output is not None:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
