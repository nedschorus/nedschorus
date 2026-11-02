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
for the closing line's answer letters, ANSWER_LETTERS_TEXT, and for its
closing_line, which builds the closing line the refusal's step 4 gives.

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
  heading and list marks, a hashtag marker opening the line, such as `#new `
  or `#new_if_d `, link targets, spacing and case are dropped;
- fenced and indented code and code spans;
- quoted text, `"..."`, `“...”` or a `>` line, that the walk-document holds;
- a waiting item's closing line, the line the walk-me-through skill ends
  every message with, `[Item 4 of 9, <the point>](<page link>) · ` and then
  the answer hook's ANSWER_LETTERS_TEXT, when every item it names is waiting
  and its total is the open walk's. The line is what the approval-walk
  finder's approval_walk_closing_line_read reads, as the finder's docstring
  says, the reader the current-item Stop hook uses too, so a point holding
  brackets, escaped or not, still makes one link. The point and the link
  target are not compared, since the agent writes its own point and the
  user's letter after the line answers that item whatever the point says, and
  a link target is not text he reads. The line without its link, `Item 4 of 9,
  <the point> · ` and ANSWER_LETTERS_TEXT, is left out only when the newest
  `#item_page` line of every item it names records a failed publish, because
  the current-item Stop hook then requires that form. A line with anything
  outside the link but the answer letters, such as a list mark, bold marks or
  a sentence, or that names another item or total, is checked;
- the line a sub-step that asks for no decision ends with, `[No decision
  here; type N or next to continue.](<page link>)` or the same line without
  its link, alone on its line, whatever item waits: it only tells the user
  how to move on, and whether it may end this message is the current-item
  Stop hook's check, which refuses it for an item without a dotted number
  such as `Item 4.1 of 9`;
- a sentence that only names waiting items, `Item 4 of 9 is waiting for your
  answer.`, the line the walk-me-through skill ended every message with before
  the closing line, when every item it names is waiting and its total is the
  open walk's or one an item heading of the walk-document carries; one that
  names another item or total, as an agent does when it numbers its own
  questions as items, is checked.
`**` and `__` are dropped before the tests, so a bold question is read.

EACH LINE is one of three:
- a clear ask: a sentence ending in `?`, or a phrase in CLEAR_ASK such as
  `say yes`, `should I` or `waiting for your answer` outside quoted text; it
  blocks, unless the line also names an item by number, which makes it
  unclear, because a reminder of a walk item's own question asks nothing new;
- unclear: a `?` inside the line, a phrase in CLEAR_ASK inside quoted text,
  such as a quoted title or a quoted line of the walk-me-through skill, which
  may only be named and not asked, or a phrase in UNCLEAR_ASK such as `I
  recommend` or `whether to`;
- not question-like: everything else; it passes.
When no line is a clear ask and some are unclear, the unclear lines go to
the model MODEL in one headless `claude -p` call, which is shown the text of
every waiting item, as its unit of the walk-document holds it, and answers
two yes-or-no questions for each unclear line: whether it concerns a waiting
item's decision, as a reworded recommendation of that item does, and whether
it asks the user something else. Code turns the two answers into one of three
labels, and asking something else wins:
AGENT_REPLY_LINE_MODEL_LABEL_ASKS_USER_SOMETHING_ELSE when the second answer is
yes, else AGENT_REPLY_LINE_MODEL_LABEL_ONLY_ABOUT_WAITING_ITEM_DECISION when
the first is, else AGENT_REPLY_LINE_MODEL_LABEL_ASKS_USER_NO_QUESTION. The hook
blocks on the first line labelled
AGENT_REPLY_LINE_MODEL_LABEL_ASKS_USER_SOMETHING_ELSE. The child runs with every hook disabled, so this
hook cannot run inside it, no session file, no tools, and a cwd outside any
checkout. When the call fails, runs past MODEL_TIMEOUT_SECONDS, or answers
without giving each numbered line exactly one entry holding both answers, the hook
blocks on the first unclear line, saying the model check failed: a missed
question scrolls away, a false block costs one reworded line.

AN INTERRUPTION ITEM'S TEXT is not checked either: a line of the text
checked, a list joined to its lead-in included, is left out when the
walk-document, as it stands when the hook runs, holds each line of it, as
the agent wrote it, as a whole line of one interruption item, one numbered
`W.n` after a waiting item W and not itself waiting, whatever its total.
Lines are compared whole and equal once `normalized` has dropped their marks,
so a leading `>` or list mark, a hashtag marker opening the line, bold,
italic and code-span marks, link targets,
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
import functools
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
    r"\b(?:say|reply|answer|type)\s+(?:yes|no|y|n|ao|d|(?-i:A))\b(?!-)|\bon\s+(?:a|your)\s+(?:yes|no)\b(?!-)"
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
HASHTAG_MARKER = re.compile(r"^#\w+\s+")
EMPHASIS_AND_SPACING = re.compile(r"[\s*_#>`]+")
ANSWER_LINE_START = "answer a to approve"

AGENT_REPLY_LINE_MODEL_LABEL_ONLY_ABOUT_WAITING_ITEM_DECISION = "concerns_only_a_waiting_item_decision"
AGENT_REPLY_LINE_MODEL_LABEL_ASKS_USER_SOMETHING_ELSE = "asks_something_else"
AGENT_REPLY_LINE_MODEL_LABEL_ASKS_USER_NO_QUESTION = "asks_nothing"
AGENT_REPLY_LINE_CONCERNS_WAITING_APPROVAL_WALK_ITEM_DECISION_MODEL_TRUE_OR_FALSE_ANSWER = "concerns_a_waiting_item_decision"
AGENT_REPLY_LINE_ASKS_USER_SOMETHING_ELSE_MODEL_TRUE_OR_FALSE_ANSWER = "asks_something_else"
MODEL_ANSWERS = (AGENT_REPLY_LINE_CONCERNS_WAITING_APPROVAL_WALK_ITEM_DECISION_MODEL_TRUE_OR_FALSE_ANSWER,
                 AGENT_REPLY_LINE_ASKS_USER_SOMETHING_ELSE_MODEL_TRUE_OR_FALSE_ANSWER)
MODEL_SCHEMA = {"type": "object",
                "properties": {"lines": {"type": "array", "items": {
                    "type": "object",
                    "properties": {"line_number": {"type": "integer"},
                                   **{answer: {"type": "boolean"} for answer in MODEL_ANSWERS}},
                    "required": ["line_number", *MODEL_ANSWERS], "additionalProperties": False}}},
                "required": ["lines"], "additionalProperties": False}
MODEL_SYSTEM_PROMPT = "You classify text. Answer only through the structured output."
MODEL_PROMPT_TEMPLATE = """An agent is taking the user through an approval-walk: numbered items, each of which he answers with a letter. While the walk is open, the agent must ask him nothing outside the items waiting for his answer, because his next letter could then answer either question. This walk's items are named `Item N of {total}`, or `item N` for short, and {waiting_phrase} for his answer; an item numbered some other way, such as a "side item" or an item with another total, is not one of the walk's items.

The text of each waiting item, as the walk-document holds it:
<waiting_items>
{waiting_items}
</waiting_items>

Below is one of the agent's messages, with every walk item it shows word for word taken out, and then the lines of it that the agent's code could not judge, numbered from 1. Use the message and the waiting items' text as context, and answer two questions about each numbered line, true or false:

- {concerns_answer}: does the line concern the decision a waiting item puts to him, in any words? True when the line restates, explains or argues for that item's recommendation, alternative or question, recommends an answer, reminds him that the item waits for his answer, or asks what he meant by his answer to the item, such as whether "dark" meant D. A line about a walk item that is not waiting, such as one still to come, concerns no waiting item.
- {asks_else_answer}: does the line ask him to decide, approve, choose or answer anything other than a waiting item's decision? True for a question to him; a recommendation on another matter that he is expected to approve or reject; a question from another agent passed on to him; a reminder that a question that is not one of the walk's items still waits for him; a question about running the walk, such as whether to pause it or skip an item; a request for him to report something back, such as what a command printed. False when the line asks him nothing, such as a report, advice that needs no answer, a question the agent answers itself, a report of what someone asked someone else that is not passed to him, or a request to do something with nothing to report back, such as opening a file or a page.

A line can be true for both, or false for both.

Give one entry per numbered line, with its number in the list of numbered lines as line_number, and both answers.

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
DECIDED_BY_MODEL_NOTICE = "the model judged that it asks him something other than a waiting item's decision"
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
    "Give the item one recommendation and one alternative, and end it with the recommendation stated as an "
    "action, as in `Recommendation: <what you recommend doing>.` State the alternative before it, as in "
    "`The alternative: <what D does instead>.`",
    "2. Change the walk's item count M from {total} to {new_total} in every item heading of {document} that "
    "carries `of {total}`, and in "
    "the last `#next_to_present` line of {minutes}, which then reads `#next_to_present {waiting_value} of "
    "{new_total}`.",
    "3. Do not show the new item now: it is shown after item {waiting} is answered.",
    "4. The flagged text has already reached the user, so leave it. End the message you write next with the line "
    "`I added the question as Item {new_item} of {new_total}.` and then {closing_lines_named}, as the "
    "walk-me-through skill writes it, as the last text of that message:\n{closing_lines}{no_page}",
    "If the flagged text does not ask the user anything, reword it in your reply so that it no longer reads "
    "as a question for him, and end the turn.",
    "From now on, while an approval-walk is open, put every question for the user, yours or another "
    "agent's, into the walk as an item instead of asking it in prose.",
)
ONE_CLOSING_LINE_NAMED = "the waiting item's closing line"
SEVERAL_CLOSING_LINES_NAMED = "each waiting item's closing line, on a line of its own"
NO_PAGE_LINK = "<page link>"
NO_PAGE_TEMPLATE = (
    "\nThe minutes record no `#item_page` line for {items}. For each such item, publish its page first if it has "
    "none and add to {minutes} the line `#item_page item <N> of <M> <the page's link>`, which this hook reads back; "
    "then put the same link in place of `<page link>` in the item's closing line.")
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
    """The line with link targets, list, quotation and heading marks, a hashtag marker opening it, emphasis,
    spacing and case dropped."""
    line = HASHTAG_MARKER.sub("", LINE_MARKS.sub("", LINK.sub(r"\1", line)))
    return EMPHASIS_AND_SPACING.sub(" ", line).strip().lower()


# Built on first use, not at import: building it can install markdown-it-py under HOME, which must not happen
# before run's stays-silent check.
@functools.cache
def closing_line_parser():
    parser = walk_finder.markdown_parser()
    # The link target is not compared, but the parser refuses a link whose scheme it distrusts, such as `file:`, and
    # walks have linked items to `file://` pages.
    parser.validateLink = lambda url: True
    return parser


def normalized_lines(lines):
    """The set of the lines' normalized forms, without the empty one, which no line of an item can match."""
    return {normalized(line) for line in lines} - {""}


def answer_sentence(line):
    """The walk-me-through skill's answer line at the start of line, without a list or quotation mark before it, and
    without what an item adds after it on the same line, such as the ` D: <the alternative>` some walk-documents add."""
    return SENTENCE_END.split(LINE_MARKS.sub("", line.strip()))[0]


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


def is_closing_line(line, waiting_numbers, total, pages):
    """Whether line is the closing line of waiting items of the open walk, whose total is total, as the module
    docstring's THE TEXT CHECKED says; pages are the walk-minutes' newest `#item_page` link per item."""
    closing = walk_finder.approval_walk_closing_line_read(line, closing_line_parser(), answer_hook.ANSWER_LETTERS_TEXT)
    if closing is None:
        return False
    numbers, line_total, link = closing
    return (line_total == total and set(numbers) <= set(waiting_numbers)
            and (link is not None or all(pages.get(number) == walk_finder.ITEM_PAGE_PUBLISH_FAILED
                                         for number in numbers)))


def is_waiting_reminder(sentence, waiting_numbers, totals):
    """Whether sentence only says that waiting items of the open walk, with one of its totals, wait for an answer."""
    reminder = WAITING_REMINDER.match(sentence.strip(TRAILING_MARKS))
    if not reminder or reminder["total"] not in totals:
        return False
    try:
        return set(walk_finder.expand_numbers(reminder["numbers"])) <= set(waiting_numbers)
    except walk_finder.UnusableRange:
        return False


def checked_lines(reply, document_text, units, parser, waiting_numbers, total, pages):
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
        if (normalized(line) in shown or is_closing_line(line, waiting_numbers, total, pages)
                or walk_finder.approval_walk_sub_step_no_decision_closing_line_page_link_or_none(line) is not None):
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
    if ends_in_question or CLEAR_ASK.search(QUOTED.sub(" ", line)):
        return "unclear" if ITEM_REFERENCE.search(line) else "clear"
    if "?" in line or CLEAR_ASK.search(line) or UNCLEAR_ASK.search(line):
        return "unclear"
    return None


def model_judgement(message_lines, unclear_lines, total, waiting, waiting_items_text,
                    timeout_seconds=MODEL_TIMEOUT_SECONDS):
    """Return (the first unclear line the model labels AGENT_REPLY_LINE_MODEL_LABEL_ASKS_USER_SOMETHING_ELSE, or None; None, or why the call
    failed), for the walk whose items have total M, whose item waiting is numbered waiting, and whose waiting items
    read waiting_items_text."""
    prompt = MODEL_PROMPT_TEMPLATE.format(
        total=total, waiting_items=waiting_items_text,
        waiting_phrase=f"items {waiting} wait" if " and " in waiting else f"item {waiting} waits",
        concerns_answer=AGENT_REPLY_LINE_CONCERNS_WAITING_APPROVAL_WALK_ITEM_DECISION_MODEL_TRUE_OR_FALSE_ANSWER,
        asks_else_answer=AGENT_REPLY_LINE_ASKS_USER_SOMETHING_ELSE_MODEL_TRUE_OR_FALSE_ANSWER,
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
        entries = verdict["lines"]
    except (ValueError, TypeError, KeyError) as error:
        detail = (completed.stderr or completed.stdout or "no output").strip()[:300]
        return None, f"claude exited {completed.returncode} without a verdict ({error!r}): {detail}"
    if completed.returncode != 0 or result.get("is_error"):
        return None, f"claude exited {completed.returncode} reporting an error: {str(result.get('result'))[:300]}"
    labels = agent_reply_line_model_labels_from_true_or_false_model_answers(entries, len(unclear_lines))
    if labels is None:
        return None, (f"claude's verdict does not give each of the {len(unclear_lines)} numbered lines exactly one "
                      f"entry with a true or false {' and '.join(MODEL_ANSWERS)}: {json.dumps(verdict)[:300]}")
    return next((line for line, label in zip(unclear_lines, labels) if label == AGENT_REPLY_LINE_MODEL_LABEL_ASKS_USER_SOMETHING_ELSE), None), None


def agent_reply_line_model_labels_from_true_or_false_model_answers(entries, count):
    """The labels of lines 1 to count, in order, or None unless entries give each of those lines exactly one entry
    with a boolean for each of MODEL_ANSWERS and name no other line. Asking something else wins over concerning a
    waiting item's decision."""
    if not isinstance(entries, list) or not all(isinstance(entry, dict) for entry in entries):
        return None
    labels = {}
    for entry in entries:
        number = entry.get("line_number")
        concerns, asks_else = (entry.get(answer) for answer in MODEL_ANSWERS)
        if type(number) is not int or type(concerns) is not bool or type(asks_else) is not bool or number in labels:
            return None
        labels[number] = (AGENT_REPLY_LINE_MODEL_LABEL_ASKS_USER_SOMETHING_ELSE if asks_else else
                          AGENT_REPLY_LINE_MODEL_LABEL_ONLY_ABOUT_WAITING_ITEM_DECISION if concerns else
                          AGENT_REPLY_LINE_MODEL_LABEL_ASKS_USER_NO_QUESTION)
    if sorted(labels) != list(range(1, count + 1)):
        return None
    return [labels[number] for number in range(1, count + 1)]


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


def closing_lines(pages, name, document_text, units, parser, numbers, total, new_total):
    """(each waiting item's closing line, in code marks, once the walk's count M is new_total, built by the answer
    hook's closing_line with the link of the item's newest `#item_page` line in pages, or NO_PAGE_LINK when the minutes
    record no page for it; the numbers of the items the minutes record no page for)."""
    pages = dict(pages)
    without_page = [number for number in numbers if number not in pages]
    pages.update(dict.fromkeys(without_page, NO_PAGE_LINK))
    points = answer_hook.heading_points(document_text.split("\n"), units, total, parser)
    walk = answer_hook.WalkState(name, None, numbers, new_total, {}, None, pages=pages, points=points)
    return [f"`{answer_hook.closing_line(number, walk)}`" for number in numbers], without_page


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
        total, waiting_units = walk_finder.waiting_item_units(document, value, numbers, total, parser,
                                                              all_units=units)
    except walk_finder.UnusableRange:
        return None
    pages = walk_finder.newest_item_page_link_per_item_from_walk_minutes(minutes.read_text(encoding="utf-8"), parser)
    checked = checked_lines(reply, document_text, units, parser, numbers, total, pages)
    lines = [line for line, _ in checked]
    kinds = [(line, line_kind(line)) for line in lines]
    clear = [line for line, kind in kinds if kind == "clear"]
    unclear = [line for line, kind in kinds if kind == "unclear"]
    if clear:
        sentence, decided, decided_by = clear[0], DECIDED_BY_CODE_NOTICE, "code"
    elif unclear:
        document_lines = document_text.split("\n")
        waiting_items_text = "\n\n".join("\n".join(document_lines[first:end]).strip()
                                         for _, _, _, first, end in waiting_units)
        sentence, failure = model(lines, unclear, total, " and ".join(numbers), waiting_items_text)
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
    closing, without_page = closing_lines(pages, name, document_text, units, parser, numbers, total, new_total)
    values = {"walk": name, "last_waiting": waiting, "sentence": sentence, "decided": decided, "waiting": waiting_label,
              "document": document, "minutes": minutes, "total": total, "new_total": new_total,
              "new_item": next_free_item(waiting, held),
              "waiting_value": ("item " if len(numbers) == 1 else "items ") + waiting_label,
              "closing_lines_named": SEVERAL_CLOSING_LINES_NAMED if numbers[1:] else ONE_CLOSING_LINE_NAMED,
              "closing_lines": "\n".join(closing), "no_page": NO_PAGE_TEMPLATE.format(
                  items=("items " if without_page[1:] else "item ") + " and ".join(without_page),
                  minutes=minutes) if without_page else ""}
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
