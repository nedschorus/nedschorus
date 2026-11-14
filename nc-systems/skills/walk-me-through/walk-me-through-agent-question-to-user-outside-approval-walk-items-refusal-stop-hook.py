#!/usr/bin/env python3
"""Stop hook: while an approval-walk is open, block the agent's stop when its
reply asks the user something outside the walk's items, so that the question
becomes an interruption item and his letter always answers the one item
waiting; and block it when the agent's message ends with a walk item's
closing line but its checkout holds no open or paused walk, as NO WALK IN THE
CHECKOUT says.

Wired as a Stop hook in .claude/settings.json, beside the current-item Stop
hook, walk-me-through-agent-reply-to-user-not-ending-with-waiting-item-closing-line-refusal-stop-hook.py,
whose turn and transcript readers this hook loads, and the approval-walk
finder, walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py,
which finds the open walk, its waiting items and its walk-document's items. It
also loads the answer hook,
walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py,
for the closing line's answer letters, ANSWER_LETTERS_TEXT, and for its
closing_line, which builds the closing lines the refusal gives; and,
when it refuses, the walk check program,
walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py, for
the category and waits-on tags the refusal's step 1 names, which that
program's close step reads to choose when the new item is shown.

EVERY TURN is checked, whoever started it: the user, another agent-seat, a
background-task notice. THE REPLY is the text of every assistant message
since the turn's start, a prompt the user typed into the turn included, plus
the Stop payload's `last_assistant_message`, because Claude Code can start
the Stop hook before it has written the final message to the transcript.

THE TEXT CHECKED is the reply, line by line, without:
- every item of the walk-document the reply shows: an item is shown when a
  reply line matches the heading of its unit, the item's own opening, as the
  approval-walk finder reads openings, or `Item N of M: <the point>` or
  `Item N of M` alone naming that item, whatever M it gives; and then every
  reply line matching its unit's heading or a line of the item is left out,
  and, when a reply line matches the unit's heading, one matching a line
  between that heading and the unit's first item or first Withdrawn
  heading, a `#new` or `#new_if_d` line there included as shown below.
  The item's lines are those the approval-walk finder's line-range helper
  gives it, which leave out a Withdrawn version's lines, up to its answer
  line; an item without an opening under a heading shared by several items
  holds the whole unit, every answer line included, since its lines cannot
  be told from the other items'. So is a reply line matching
  the answer line's first sentence, the walk-me-through skill's
  answer line without what the item adds after it, such as ` D: <the
  alternative>`; and one showing a line of the item that opens with the
  mark `#new` or `#new_if_d` as the agent shows it, the mark replaced by
  `If you approve, the new text:` or `If you disapprove, the new text:` and
  a `The new text:` just after the mark dropped; lines match when they are
  equal once markdown emphasis, heading and list marks, a hashtag marker
  opening the line, such as `#new ` or `#new_if_d `, link targets, spacing
  and case are dropped;
- fenced and indented code and code spans;
- quoted text, `"..."`, `“...”` or a `>` line, that the walk-document holds;
- a waiting item's closing line, the line the walk-me-through skill ends
  every message with, `[Item 4 of 9, <the point>](<page link>) · ` and then
  the answer hook's ANSWER_LETTERS_TEXT, when every item it names is waiting,
  whatever M it gives, since M is display only, as the approval-walk finder's
  docstring says. The line is what the approval-walk
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
  a sentence, or that names another item, is checked;
- the line a sub-step that asks for no decision ends with, `[No decision
  here; type N or next to continue.](<page link>)` or the same line without
  its link, alone on its line, whatever item waits: it only tells the user
  how to move on, and whether it may end this message is the current-item
  Stop hook's check, which refuses it for an item without a dotted number
  such as `Item 4.1 of 9`;
- a sentence that only names waiting items, `Item 4 of 9 is waiting for your
  answer.`, the line the walk-me-through skill ended every message with before
  the closing line, when every item it names is waiting, whatever M it
  gives; one that names another item, as an agent does when it numbers its
  own questions as items, is checked.
`**` and `__` are dropped before the tests, so a bold question is read.

EACH LINE is question-like when it holds a `?` or a phrase in ASK_PHRASE,
such as `say yes`, `should I`, `needs your approval`, `I recommend`,
`whether to`, or an answer cue followed by a hyphen, as in `type A-D`,
`reply A-OP` or `say yes-or-no`, apart from the whole words `no-decision` and
`no-op`, which are words. Code
refuses no line by itself: a `?` or an ask phrase also ends or fills lines
that ask nothing, such as a question the agent answers itself, the
walk-me-through skill's answer line, or `nothing here needs your answer`.
Every other line passes, and a reply with no question-like line never waits
for the model.
When some lines are question-like, they go to
the model MODEL in one headless `claude -p` call, which is shown the text of
every waiting item, as its unit of the walk-document holds it, and answers
two yes-or-no questions for each question-like line: whether it concerns a waiting
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
blocks on the first question-like line, saying the model check failed: a missed
question scrolls away, a false block costs one turn ending with the closing line.

AN INTERRUPTION ITEM'S TEXT is not checked either: a line of the text
checked, a list joined to its lead-in included, is left out when the
walk-document, as it stands when the hook runs, holds each line of it, as
the agent wrote it, as a whole line of one interruption item: an unnumbered
item, as the approval-walk finder reads one, which the refusal's step 1 has
the agent add, or, in a walk opened before items were added unnumbered, one
numbered `W.n` after a waiting item W and not itself waiting, whatever its M.
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
item's opening, a Withdrawn heading or its unit's end, and are otherwise its whole unit; but an
item without an opening under a heading shared by several items holds no
lines. So a question the
agent has put into an interruption item passes, however that item got there
or was later retitled, and a question in any other item does not.

EACH BLOCK is logged as one JSON line, with its time, session, walk, the
sentence flagged, and what decided, `model`, `model-check-failed` or, for the
block NO WALK IN THE CHECKOUT describes, `no-walk-in-checkout`,
to LOG_FILE_NAME at the top of the log-store, as ned-box reaches it or as
the Mac's mount of ned-box's home reaches it; LOG_PATH_VARIABLE overrides the
path. When neither is reachable, or the write fails, the block's reason says
the block was not logged.

NO WALK IN THE CHECKOUT: when the cwd's checkout has no open or paused
approval-walk in its `docs/walk/`, a missing `docs/walk/` counting as empty,
since the folder is not in the repository and a new worktree lacks it, and the
agent's last message, the Stop payload's `last_assistant_message` or, when
that is empty, the turn's last assistant text, ends with a closing line, with
or without its link, as the approval-walk finder's
approval_walk_closing_line_read reads it, whatever items and total it names,
the hook blocks, names the checkout it searched, and tells the agent to keep
the walk's files in that checkout's `docs/walk/`: the walk-me-through hooks
find a walk only there, so the user's letter to that line would answer no
item.

SILENT while the agent answers a Stop hook (stop_hook_active set), as the
Stop-hook silence rule's module requires; in a headless `claude -p` child;
when the transcript or the cwd's checkout is missing; when no approval-walk is
open, unless NO WALK IN THE CHECKOUT applies; when more than one approval-walk
is open or paused, since no waiting item is known, which the answer program
refuses, naming each; while the open walk is paused,
or its minutes carry only the old marker; when the turn wrote no text; and
when the open walk's minutes line or walk-document cannot be read, which the
current-item Stop hook reports at the next turn the user starts.

OUTPUT: {"decision": "block", "reason": <message>}. ON A FAULT, such as input
that is not JSON or a file it cannot read, the hook prints one line naming it
on stderr and exits 1: Claude Code records a Stop hook's exit 1 as a
non-blocking error and still ends the turn.

Tool-messages-to-agent follow
docs/nedschorus-wiki/nedschorus-how-to-write-a-tool-message-to-agent-such-as-a-hook-refusal-or-script-error.md.

DURING AN EMERGENCY STOP, while the emergency-stop file is in force or cannot
be read, this hook is silent: an agent-seat shows no approval-walk item then,
and every reply goes through. The stop is read by
nc-systems/skills/emergency-stop/emergency-stop-file-in-force-read-common.py."""
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
CURRENT_ITEM_HOOK_FILE = HERE / "walk-me-through-agent-reply-to-user-not-ending-with-waiting-item-closing-line-refusal-stop-hook.py"
WALK_FINDER_FILE = HERE / "walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py"
WALK_CHECK_PROGRAM = HERE / "walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py"
ANSWER_HOOK_FILE = (HERE / "walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-"
                    "user-prompt-submit-hook.py")
REPOSITORY_TOP = HERE.parents[2]
EMERGENCY_STOP_READER_FILE = (Path(__file__).resolve().parent.parent / "emergency-stop"
                              / "emergency-stop-file-in-force-read-common.py")
STOP_HOOKS_STAY_SILENT_RULE_FILE = (
    REPOSITORY_TOP / "nc-systems" / "general-tools"
    / "claude-code-stop-hooks-stay-silent-while-agent-answers-a-stop-hook-rule-common.py")
ATTENDANCE_CHECK_FILE = (REPOSITORY_TOP / "nc-systems" / "general-tools"
                         / "agent-session-unattended-by-user-check-common.py")
PATH_CONSTANTS_FILE = (REPOSITORY_TOP / "nc-systems" / "general-tools"
                       / "ned-box-home-directory-and-its-mac-mount-point-path-constants-common.py")
CLAUDE_CODE_COMMAND_LINE_PREFIX_FILE = (
    REPOSITORY_TOP / "nc-systems" / "general-tools"
    / "claude-code-headless-run-command-line-prefix-with-no-connectors-and-explicit-permission-mode-common.py")

MODEL = "claude-haiku-5-5"
MODEL_TIMEOUT_SECONDS = 25
LOG_STORE_DIRECTORY_NAME = "nedschorus-logs"
LOG_FILE_NAME = "walk-me-through-agent-question-to-user-outside-approval-walk-items-refusal-stop-hook-refusals.jsonl"
LOG_PATH_VARIABLE = "NEDSCHORUS_WALK_ME_THROUGH_AGENT_QUESTION_REFUSAL_LOG"

NUMBER_LIST = r"\d+(?:\.\d+)*(?:\s*(?:,|&|\band\b|\bto\b|-|–)\s*\d+(?:\.\d+)*)*"
WAITING_REMINDER = re.compile(
    rf"^(?:the\s+)?items?\s+(?P<numbers>{NUMBER_LIST})\s+of\s+(?P<total>\d+)\s+(?:is|are)\s+(?:still\s+)?waiting"
    r"\s+for\s+your\s+answer\W*$",
    re.I)
# `no-decision` and `no-op` are words, not answers; any other hyphen after an answer cue, as in `type A-D` or
# `reply A-OP`, may still be an answer.
NO_FOLLOWED_BY_HYPHEN_THAT_ASKS_NOTHING = r"no-(?:decision|op)\b"
ASK_PHRASE = re.compile(
    # The letter A is matched in capitals only, because a lowercase `a` there is the article, as in `answer a finding`.
    r"\b(?:say|reply|answer|type)\s+(?!" + NO_FOLLOWED_BY_HYPHEN_THAT_ASKS_NOTHING + r")(?:yes|no|y|n|ao|d|(?-i:A))\b"
    r"|\bon\s+(?:a|your)\s+(?!" + NO_FOLLOWED_BY_HYPHEN_THAT_ASKS_NOTHING + r")(?:yes|no)\b"
    r"|\byour\s+yes\s+or\s+no\b|\bdo\s+you\s+(?:want|agree)\b|\bshould\s+I\b|\bshall\s+I\b|\bwant\s+me\s+to\b"
    r"|\bwould\s+you\s+like\b|\bwaiting\s+(?:on|for)\s+your\s+(?:answer|word|decision|ruling|approval|go-ahead|yes)\b"
    r"|\bneeds?\s+your\s+(?:answer|decision|ruling|approval|word|go-ahead|yes)\b"
    r"|\b(?:tell\s+me|let\s+me\s+know)\s+(?:if|whether|which)\b|\bplease\s+(?:confirm|approve|decide|choose|pick|rule)\b"
    r"|\brecommend|^\W*recommendation:|\bI\s+suggest\b|\blet\s+me\s+know\b|\btell\s+me\b|\basking\s+you\b"
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
NEW_TEXT_LINE = re.compile(r"^(#new(?:_if_d)?)[:\s]+(?i:the\s+new\s+text:\s*)?(.*)$")
NEW_TEXT_SHOWN_AS = {"#new": "If you approve, the new text: ", "#new_if_d": "If you disapprove, the new text: "}

AGENT_REPLY_LINE_MODEL_LABEL_ONLY_ABOUT_WAITING_ITEM_DECISION = "concerns_only_a_waiting_item_decision"
AGENT_REPLY_LINE_MODEL_LABEL_ASKS_USER_SOMETHING_ELSE = "asks_something_else"
AGENT_REPLY_LINE_MODEL_LABEL_ASKS_USER_NO_QUESTION = "asks_nothing"
AGENT_REPLY_LINE_CONCERNS_WAITING_APPROVAL_WALK_ITEM_DECISION_MODEL_TRUE_OR_FALSE_ANSWER = "concerns_a_waiting_item_decision"
AGENT_REPLY_LINE_ASKS_USER_SOMETHING_ELSE_MODEL_TRUE_OR_FALSE_ANSWER = "asks_something_else"
MODEL_ANSWERS = (AGENT_REPLY_LINE_CONCERNS_WAITING_APPROVAL_WALK_ITEM_DECISION_MODEL_TRUE_OR_FALSE_ANSWER,
                 AGENT_REPLY_LINE_ASKS_USER_SOMETHING_ELSE_MODEL_TRUE_OR_FALSE_ANSWER)
MODEL_SCHEMA = {"type": "object",
                "properties": {"lines": {"type": "array", "description": "One entry per numbered line.", "items": {
                    "type": "object",
                    "properties": {
                        "line_number": {"type": "integer",
                                        "description": "The line's number in the list of numbered lines."},
                        AGENT_REPLY_LINE_CONCERNS_WAITING_APPROVAL_WALK_ITEM_DECISION_MODEL_TRUE_OR_FALSE_ANSWER: {
                            "type": "boolean",
                            "description": "Whether the line concerns the decision a waiting item puts to the user, in "
                                           "any words. True when the line restates, explains or argues for that "
                                           "item's recommendation, alternative or question, recommends an answer, "
                                           "reminds him that the item waits for his answer, or asks what he meant by "
                                           "his answer to the item, such as whether \"dark\" meant D. A line about a "
                                           "walk item that is not waiting, such as one still to come, concerns no "
                                           "waiting item. Judged apart from the other answer: a line can be true or "
                                           "false for both."},
                        AGENT_REPLY_LINE_ASKS_USER_SOMETHING_ELSE_MODEL_TRUE_OR_FALSE_ANSWER: {
                            "type": "boolean",
                            "description": "Whether the line asks the user to decide, approve, choose or answer "
                                           "anything other than a waiting item's decision. True for a question to him; "
                                           "a recommendation on another matter that he is expected to approve or "
                                           "reject; a question from another agent passed on to him; a reminder that a "
                                           "question that is not one of the walk's items still waits for him; a "
                                           "question about running the walk, such as whether to pause it or skip an "
                                           "item; a request for him to report something back, such as what a command "
                                           "printed. False when the line asks him nothing, such as a report, advice "
                                           "that needs no answer, a question the agent answers itself, a report of "
                                           "what someone asked someone else that is not passed to him, or a request "
                                           "to do something with nothing to report back, such as opening a file or a "
                                           "page. Judged apart from the other answer: a line can be true or false for "
                                           "both."}},
                    "required": ["line_number", *MODEL_ANSWERS], "additionalProperties": False}}},
                "required": ["lines"], "additionalProperties": False}
MODEL_SYSTEM_PROMPT = "You classify text. Answer only through the structured output."
MODEL_PROMPT_TEMPLATE = """An agent is taking the user through an approval-walk: numbered items, each of which he answers with a letter. While the walk is open, the agent must ask him nothing outside the items waiting for his answer, because his next letter could then answer either question. This walk's items are named `Item N of {total}`, or `item N` for short, and {waiting_phrase} for his answer; an item numbered some other way, such as a "side item", is not one of the walk's items.

The text of each waiting item, as the walk-document holds it:
<waiting_items>
{waiting_items}
</waiting_items>

Below is one of the agent's messages, with every walk item it shows word for word taken out, and then the lines of it that the agent's code could not judge, numbered from 1. Use the message and the waiting items' text as context, and judge each numbered line as the fields of the structured output describe.

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
DECIDED_BY_MODEL_NOTICE = "the model judged that it asks him something other than a waiting item's decision"
MODEL_CHECK_FAILED_NOTICE = ("the hook's `claude -p` call that has the model judge this question-like text failed, "
                             "{failure}, so the hook treats the text as a question")
REFUSAL_INSTRUCTIONS = (
    "If the flagged text asks the user to decide or answer something, do these three steps:",
    "1. Add it to the walk-document {document} as an interruption item headed `## <the point of the question>`, "
    "with no number, placed right after item {last_waiting}. Under the heading, give it a line of its own naming "
    "its category, the one for how soon its work must happen, one of {category_tags}, and a line "
    "`{waits_on_tag} <title>` for each item it must follow, as the walk-me-through skill's section "
    "\"Re-planning\" says. Do not number it yourself: the close step of "
    "nc-systems/skills/walk-me-through/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py "
    "chooses when, among the items not yet shown, the user sees it, by the items it waits on, its category and the "
    "day it first entered a walk, so it may come later than right after item {last_waiting}, and writes its number "
    "into this heading then. "
    "Quote the question whole "
    "in the item, as its asker wrote it, whether you or another agent, giving each line of the flagged text a "
    "line of its own, word for word, and putting the rest of the question on other lines of the item. This hook passes the "
    "question only when the item in the walk-document holds every flagged line that way, and refuses again until "
    "it does; it ignores a `>` quote mark or a list mark such as `-` or `1.` at the start of a line, bold, italic "
    "and code marks, and letter case, so you may add or drop those. "
    "Give the item one recommendation and one alternative, and end it with the recommendation stated as an "
    "action, as in `Recommendation: <what you recommend doing>.` State the alternative before it, as in "
    "`The alternative: <what D does instead>.`",
    "2. Do not show the new item now: the walk shows it when its turn comes.",
    "3. The flagged text has already reached the user, so leave it. End the message you write next with the line "
    "`I added the question to the walk as a new item.` and then {closing_lines_named}, as the "
    "walk-me-through skill writes it, as the last text of that message:\n{closing_lines}",
    "If the flagged text does not ask the user anything, end the turn with only the waiting item's closing line, "
    "printed below.\n{closing_lines_no_item_added}{no_page}",
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
NO_WALK_REFUSAL_OPENING_TEMPLATE = (
    "approval-walk closing-line check: this hook refused to end your turn on purpose, because your message ends "
    "with an approval-walk item's closing line, \"{line}\", but the checkout you work in, {top}, has no open or "
    "paused approval-walk in {walk_directory}{missing}. Your message has already reached the user. The "
    "walk-me-through hooks read an approval-walk's walk-minutes and walk-document only in {walk_directory}, so the "
    "letter he types to answer that line reaches no approval-walk item, and is read as an answer to anything else "
    "you asked him.")
NO_WALK_DIRECTORY_MISSING = ", which does not exist"
NO_WALK_REFUSAL_INSTRUCTIONS = (
    "If the walk-document and walk-minutes of your approval-walk are in another folder, such as another checkout's "
    "`docs/walk/`, move both files into {walk_directory}, creating {walk_directory} if it is missing, and then end "
    "your turn; {walk_directory} is not kept in the repository, so a new worktree starts without it. The hooks then "
    "find the approval-walk, and the user's next letter answers its waiting item.",
    "If you have no approval-walk with items still waiting for the user, tell him in your next message that the "
    "closing line your message ended with belongs to no open approval-walk, so a letter he types answers no item, "
    "and ask him nothing else in that message.",
    "From now on, keep the walk-document and walk-minutes of every approval-walk you run in the `docs/walk/` of the "
    "checkout you work in.",
)
NOT_LOGGED_NOTICE = ("This refusal was not logged, {problem}. If that is because ned-box cannot be reached, tell "
                     "the user that this hook could not log to the log-store on ned-box; otherwise you need not act on it.")


def load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


walk_finder = load_module("walk_me_through_approval_walk_minutes_and_walk_document_item_finder_common",
                          WALK_FINDER_FILE)
# An item's own heading as the agent shows it, normalized: `Item N of M: <the point>` with one item, whatever M gives.
ITEM_OWN_HEADING = re.compile(rf"item ({walk_finder.NUMBER}) of \d+(?::|$)")
current_item_hook = load_module("walk_me_through_agent_reply_to_user_not_ending_with_waiting_item_closing_line_refusal_stop_hook",
                                CURRENT_ITEM_HOOK_FILE)
answer_hook = load_module(
    "walk_me_through_user_short_answer_to_approval_walk_item_expanded_into_instructions_user_prompt_submit_hook",
    ANSWER_HOOK_FILE)
command_line_prefix = load_module("claude_code_headless_run_command_line_prefix_with_no_connectors_and_explicit_permission_mode_common",
                            CLAUDE_CODE_COMMAND_LINE_PREFIX_FILE)


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
    """The set of normalized lines of every unnumbered item, its whole unit, and of every item numbered W.n, for W a
    waiting item, not itself waiting: its lines as the approval-walk finder's line-range helper gives them, or
    nothing when they start at the heading of a unit of several items, because that unit's items have no
    openings."""
    document_lines = document_text.split("\n")
    openings = walk_finder.item_opening_lines(document_text, parser)
    texts = [normalized_lines(document_lines[unit[3]:unit[4]])
             for unit in units if walk_finder.approval_walk_unit_is_unnumbered_item(unit)]
    for numbers, total, _, first, end in units:
        for number in numbers:
            if number in waiting_numbers or not any(re.fullmatch(rf"{re.escape(waiting)}\.\d+", number)
                                                    for waiting in waiting_numbers):
                continue
            span = walk_finder.approval_walk_item_line_range_within_heading_shared_by_several_items(
                openings, first, end, number, numbers, total)
            if len(numbers) > 1 and span[0] == first:
                continue
            texts.append(normalized_lines(document_lines[span[0]:span[1]]))
    return texts


def new_text_as_shown(line):
    """The `#new` or `#new_if_d` line as the agent shows it to the user, or None for any other line."""
    new_text = NEW_TEXT_LINE.match(LINE_MARKS.sub("", line.strip()))
    return NEW_TEXT_SHOWN_AS[new_text[1]] + new_text[2] if new_text else None


def shown_item_lines(reply_lines, document_lines, units, openings):
    """The normalized lines of every item the reply shows, as the module docstring's THE TEXT CHECKED says: the
    heading of its unit, the unit's lines before its first item's or its first Withdrawn heading when the reply
    holds that heading, and its lines as the approval-walk finder's line-range helper gives them, up to its answer
    line, or, for an item without an opening under a heading shared by several items, the whole unit; with each
    answer line's answer sentence alone and each `#new` or `#new_if_d` line as the agent shows it."""
    reply_set = normalized_lines(reply_lines)
    own_headings = {heading[1] for heading in map(ITEM_OWN_HEADING.match, reply_set) if heading}
    shown = set()
    for numbers, total, _, first, end in units:
        unit_shown = normalized(document_lines[first]) in reply_set
        spans = [(number, *(walk_finder.approval_walk_item_line_range_within_heading_shared_by_several_items(
            openings, first, end, number, numbers, total) if len(numbers) > 1 else (first, end)))
                 for number in numbers or [None]]
        if unit_shown:
            # A Withdrawn heading, an opening that names no item, ends the lead-in as it ends an item's lines.
            withdrawn = [line for line in openings if first < line < end and not openings[line][0]]
            for line in document_lines[first:min([start for _, start, _ in spans] + withdrawn)]:
                shown |= normalized_lines([line, new_text_as_shown(line) or ""])
        for number, start, stop in spans:
            if not (unit_shown or number in own_headings or normalized(document_lines[start]) in reply_set):
                continue
            # The whole unit stands for each of its items, so no item's answer line ends it.
            whole_shared_unit = len(numbers) > 1 and start == first
            for line in document_lines[start:stop]:
                shown |= normalized_lines([line, new_text_as_shown(line) or ""])
                if normalized(line).startswith(ANSWER_LINE_START):
                    shown |= normalized_lines([answer_sentence(line)])
                    if not whole_shared_unit:
                        break
    return shown


def is_closing_line(line, waiting_numbers, pages):
    """Whether line is the closing line of waiting items of the open walk, whatever M it gives, as the module
    docstring's THE TEXT CHECKED says; pages are the walk-minutes' newest `#item_page` link per item."""
    closing = walk_finder.approval_walk_closing_line_read(line, closing_line_parser(), answer_hook.ANSWER_LETTERS_TEXT)
    if closing is None:
        return False
    numbers, _, link = closing
    return (set(numbers) <= set(waiting_numbers)
            and (link is not None or all(pages.get(number) == walk_finder.ITEM_PAGE_PUBLISH_FAILED
                                         for number in numbers)))


def is_waiting_reminder(sentence, waiting_numbers):
    """Whether sentence only says that waiting items of the open walk, whatever M it gives, wait for an answer."""
    reminder = WAITING_REMINDER.match(sentence.strip(TRAILING_MARKS))
    if not reminder:
        return False
    try:
        return set(walk_finder.expand_numbers(reminder["numbers"])) <= set(waiting_numbers)
    except walk_finder.UnusableRange:
        return False


def checked_lines(reply, document_text, units, parser, waiting_numbers, pages):
    """The reply's lines as the module docstring's THE TEXT CHECKED says, emphasis dropped, empty ones left out,
    and each list joined to the line ending in `:` that introduces it, so the list is judged with its lead-in;
    then those an interruption item holds, compared as the reply wrote them, left out. Each comes as (the line
    checked, the lines as the reply wrote them)."""
    document_lines = document_text.split("\n")
    normalized_document = normalized(" ".join(document_lines))
    lines = walk_finder.prose_lines(reply, parser)
    shown = shown_item_lines(lines, document_lines, units, walk_finder.item_opening_lines(document_text, parser))
    kept, written, introduced_list = [], [], False
    for line in lines:
        if (normalized(line) in shown or is_closing_line(line, waiting_numbers, pages)
                or walk_finder.approval_walk_sub_step_no_decision_closing_line_page_link_or_none(line) is not None):
            continue
        if line.lstrip().startswith(">") and normalized(line) in normalized_document:
            continue
        as_written = line
        line = walk_finder.CODE_SPAN.sub(" ", line)
        line = QUOTED.sub(lambda quote: " " if normalized(quote[0][1:-1]) in normalized_document else quote[0], line)
        line = line.replace("**", "").replace("__", "")
        sentences = [sentence for sentence in SENTENCE_END.split(line.strip())
                     if not is_waiting_reminder(sentence, waiting_numbers)]
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


def is_question_like(line):
    """Whether line is question-like, as the module docstring's EACH LINE says."""
    return "?" in line or ASK_PHRASE.search(line) is not None


def model_judgement(message_lines, question_like_lines, total, waiting, waiting_items_text,
                    timeout_seconds=MODEL_TIMEOUT_SECONDS):
    """Return (the first question-like line the model labels AGENT_REPLY_LINE_MODEL_LABEL_ASKS_USER_SOMETHING_ELSE, or None; None, or why the call
    failed), for the walk whose items have total M, whose item waiting is numbered waiting, and whose waiting items
    read waiting_items_text."""
    prompt = MODEL_PROMPT_TEMPLATE.format(
        total=total, waiting_items=waiting_items_text,
        waiting_phrase=f"items {waiting} wait" if " and " in waiting else f"item {waiting} waits",
        message="\n".join(message_lines),
        lines="\n".join(f"{number}. {line}" for number, line in enumerate(question_like_lines, 1)))
    command = [*command_line_prefix.claude_code_headless_run_command_line_prefix_build(
                   "dontAsk", caller_claude_code_session_settings={"disableAllHooks": True}),
               "--model", MODEL, "--output-format", "json",
               "--json-schema", json.dumps(MODEL_SCHEMA), "--system-prompt", MODEL_SYSTEM_PROMPT,
               "--tools", "",
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
    labels = agent_reply_line_model_labels_from_true_or_false_model_answers(entries, len(question_like_lines))
    if labels is None:
        return None, (f"claude's verdict does not give each of the {len(question_like_lines)} numbered lines exactly one "
                      f"entry with a true or false {' and '.join(MODEL_ANSWERS)}: {json.dumps(verdict)[:300]}")
    return next((line for line, label in zip(question_like_lines, labels) if label == AGENT_REPLY_LINE_MODEL_LABEL_ASKS_USER_SOMETHING_ELSE), None), None


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


def closing_lines(pages, name, document_text, units, parser, numbers, new_total):
    """(each waiting item's closing line, in code marks, once the walk's count M is new_total, built by the answer
    hook's closing_line with the link of the item's newest `#item_page` line in pages, or NO_PAGE_LINK when the minutes
    record no page for it; the numbers of the items the minutes record no page for)."""
    pages = dict(pages)
    without_page = [number for number in numbers if number not in pages]
    pages.update(dict.fromkeys(without_page, NO_PAGE_LINK))
    points = answer_hook.heading_points(document_text.split("\n"), units, parser)
    walk = answer_hook.WalkState(name, None, numbers, new_total, {}, None, pages=pages, points=points)
    return [f"`{answer_hook.closing_line(number, walk)}`" for number in numbers], without_page


def no_walk_in_checkout_refusal(payload, environment, top, walk_directory):
    """The block the module docstring's NO WALK IN THE CHECKOUT describes, or None when the agent's last message does
    not end with a closing line."""
    message = payload.get("last_assistant_message") or ""
    if not message.strip():
        texts = turn_assistant_texts(current_item_hook.transcript_records(Path(payload["transcript_path"]).expanduser()))
        message = texts[-1] if texts else ""
    # Every closing line holds the answer letters, so a message without them needs no parser, and most lack them.
    if answer_hook.ANSWER_LETTERS_TEXT not in message:
        return None
    lines = [line for line in walk_finder.prose_lines(message, closing_line_parser()) if line.strip()]
    if not lines or walk_finder.approval_walk_closing_line_read(
            lines[-1], closing_line_parser(), answer_hook.ANSWER_LETTERS_TEXT) is None:
        return None
    values = {"line": lines[-1].strip(), "top": top, "walk_directory": walk_directory,
              "missing": "" if walk_directory.is_dir() else NO_WALK_DIRECTORY_MISSING}
    lines_out = [NO_WALK_REFUSAL_OPENING_TEMPLATE.format(**values)] + [
        line.format(**values) for line in NO_WALK_REFUSAL_INSTRUCTIONS]
    problem = log_refusal(environment, {
        "time": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "session": payload.get("session_id"), "walk": None, "sentence": values["line"],
        "decided_by": "no-walk-in-checkout"})
    if problem is not None:
        lines_out.append(NOT_LOGGED_NOTICE.format(problem=problem))
    return json.dumps({"decision": "block", "reason": "\n".join(lines_out)}, ensure_ascii=False)


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
    if load_module("agent_session_unattended_by_user_check_common",
                   ATTENDANCE_CHECK_FILE).agent_session_unattended_by_user(environment):
        return None
    emergency_stop = load_module("emergency_stop_file_in_force_read_common", EMERGENCY_STOP_READER_FILE)
    stop_state = emergency_stop.read_state(emergency_stop.emergency_stop_folder(environment))
    if isinstance(stop_state, (emergency_stop.InForce, emergency_stop.Unreadable)):
        return None
    transcript_path = payload.get("transcript_path")
    if not transcript_path or not Path(transcript_path).expanduser().is_file() or not payload.get("cwd"):
        return None
    top = walk_finder.checkout_top(Path(payload["cwd"]))
    if top is None:
        return None
    walk_directory = top / walk_finder.WALK_DIRECTORY
    if not walk_directory.is_dir():
        return no_walk_in_checkout_refusal(payload, environment, top, walk_directory)
    parser = walk_finder.markdown_parser()
    try:
        walk = walk_finder.the_one_unclosed_approval_walk_including_paused(walk_directory, parser)
    except walk_finder.MoreThanOneUnclosedApprovalWalk:
        return None  # no waiting item is known; the answer program refuses and names both approval-walks
    if walk is None:
        return no_walk_in_checkout_refusal(payload, environment, top, walk_directory)
    minutes, value, old_marker, paused = walk
    if old_marker or paused:
        return None
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
    checked = checked_lines(reply, document_text, units, parser, numbers, pages)
    lines = [line for line, _ in checked]
    question_like = [line for line in lines if is_question_like(line)]
    if not question_like:
        return None
    document_lines = document_text.split("\n")
    waiting_items_text = "\n\n".join("\n".join(document_lines[first:end]).strip()
                                     for _, _, _, first, end in waiting_units)
    sentence, failure = model(lines, question_like, total, " and ".join(numbers), waiting_items_text)
    if failure is not None:
        sentence, decided, decided_by = question_like[0], MODEL_CHECK_FAILED_NOTICE.format(failure=failure), \
            "model-check-failed"
    elif sentence is None:
        return None
    else:
        decided, decided_by = DECIDED_BY_MODEL_NOTICE, "model"
    # The agent copies the flagged text into the item, so it is named as written, not as checked.
    sentence = "\n".join(next(written for line, written in checked if line == sentence))
    waiting = numbers[-1]
    waiting_label = " and ".join(numbers)
    new_total = str(int(total) + 1)
    # Loaded only here, on the way to a refusal, so a reply that passes does not pay for it.
    check_and_close = load_module("walk_me_through_answer_added_texts_cold_read_fast_read_check_and_close",
                                  WALK_CHECK_PROGRAM)
    closing, without_page = closing_lines(pages, name, document_text, units, parser, numbers, new_total)
    # No item is added when the flagged text asks nothing, so that branch's closing line keeps the walk's count.
    closing_no_item_added, _ = closing_lines(pages, name, document_text, units, parser, numbers, total)
    values = {"walk": name, "last_waiting": waiting, "sentence": sentence, "decided": decided, "waiting": waiting_label,
              "document": document, "waits_on_tag": check_and_close.WALK_WAITS_ON_TAG,
              "category_tags": ", ".join(f"`{check_and_close.WALK_CATEGORY_TAG}{category}`"
                                         for category in check_and_close.WALK_CATEGORIES),
              "closing_lines_named": SEVERAL_CLOSING_LINES_NAMED if numbers[1:] else ONE_CLOSING_LINE_NAMED,
              "closing_lines": "\n".join(closing),
              "closing_lines_no_item_added": "\n".join(closing_no_item_added), "no_page": NO_PAGE_TEMPLATE.format(
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
