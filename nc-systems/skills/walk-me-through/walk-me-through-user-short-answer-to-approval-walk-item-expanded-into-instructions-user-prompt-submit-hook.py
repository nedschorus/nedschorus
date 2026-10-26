#!/usr/bin/env python3
"""UserPromptSubmit hook: when the user's whole prompt is a short answer, such
as A, `approved`, `37.4 r` or `1 a 2 d`, add context that tells the agent
what the answer means and what to do.

Wired as a UserPromptSubmit hook in .claude/settings.json. The prompt is
stripped of surrounding whitespace, and of one trailing period for every form
but a rider, then read, ignoring case, as the first of these forms it matches,
in every form allowing a hyphen, with or without spaces around it, between the
letters of AO, O2 and O3 (`A-O`, `a - o`, `O-2`):

  SINGLE      one answer: A, AO, Aa, D, Z, R, E, O, O2 or O3, or a word approve,
              approved, approve as obvious, disapprove, disapproved, defer,
              later or repeat.
  ALL         `all a`, `a to all`, `all ao`, `ao to all`.
  NUMBERED    one or more pairs of a number and A, AO, D, Z or R:
              `8a`, `6 - a`, `1 a 2 d`, `5 d, 6 z`, `item 3 ao`, `37.4 r`; or a
              word, then numbers: `repeat 37.4` reads as `37.4 r`,
              `approve item 5` as `5 a`, `approve 5 and 6` as `5 a, 6 a`. The
              numbers are part numbers when PARTS OF THE WAITING ITEM, below,
              says so, and item numbers otherwise.
  CONDITION   an answer, then `if` or `after` and a condition: `a if ...`.
  RIDER       an answer, then more text: a letter needs a comma, semicolon,
              colon, dash or period before the text, or the words but, and,
              then, also or plus (`a but ...`, `d and r`, `a, ...`); a word
              needs only a space (`repeat with context`). Text that opens with
              an item number, `item` before it or not, is never a rider.
Every other prompt prints nothing and exits 0 without reading any file: Y, N
and C are not answers.

A, AO, Aa and D answer the item's recommendation: A, AO and Aa approve it,
Aa only after an advisor check, which the agent makes as AA_SKILL_TEXT, the
walk-me-through skill's text for Aa, says; D disapproves it, so the item's
alternative is done. An answer that makes a change sends the agent to
CHECK_PROGRAM's check step, with --obvious for AO and --after-advisor for Aa.
O asks the agent to show the item again with an "Option 2" and an "Option 3"
paragraph; O2 and O3 approve one of them, through the check step with
--option.

THE OPEN APPROVAL-WALK is found with WALK_FINDER_FILE, the module the
walk-me-through Stop hook uses too, loaded by path: the most recently modified
docs/walk/*-minutes.md, in the checkout the payload's cwd names, whose last
`#next_to_present` line is not `none` or `closed`. The waiting items are that
line's running count, such as `item 4.1 of 6`. An item's recommendation is the
rest of the line after the last `Recommendation:` in its part of the
walk-document, emphasis and one trailing period aside; an item with none
recommends nothing. Under a heading shared by several items, an item's part
starts at its opening, as WALK_FINDER_FILE's docstring says; when the heading
holds more than one recommendation and an item has no opening, the hook reads
no recommendation for any of its items and says why.

R ON AN OPEN APPROVAL-WALK, as the whole prompt (R or repeat), hands the
agent each waiting item's closing line to print, word for word: the item's
link, from the newest `#item_page item N of M <link>` line for that item
number in the minutes, outside code and HTML comments, with the item's running
count and point from its walk-document heading, any link in the point cut to
its text, then ANSWER_LETTERS_TEXT, as the walk-me-through skill writes it.
The link opens the item's page, which shows the item in full on every screen
the user reads. For an item with no `#item_page` line, the agent
is told to show the item in full, heading included, word for word as the
walk-document has it; the hook copies no item text. In a NUMBERED answer, each R
does the same for the item it names, and an answer whose every
letter is R, such as `37.4 r`, gets none of the lines for recording answers,
since R records nothing. When no approval-walk is
open, or its walk-document has no item with a number an R names, or with one
of the numbers after a word, as in `approve 5 and 6`, the hook prints
nothing, so the prompt reaches the agent as typed; when the walk-document or
the `#next_to_present` line cannot be read, the hook still gives the text, and
the agent looks for the item itself.

PARTS OF THE WAITING ITEM. The walk-me-through skill lets one item hold up to
five parts of a single fix, numbered 1 to 5, and answered part by part as in
`1 a 2 d`. The hook reads a part's number from a line in the item's part of
the walk-document, outside code, that starts at the line's first character,
after any heading marks and `**` or `__`, with `Part N`, or with N then `.` or
`)` and a space, emphasis or the line's end: `1. ...`, `**1.** ...`,
`**Part 2:** ...`, `### Part 3`. The item holds parts when those numbers run
1 to K, K from 2 to 5. When exactly one item is waiting, it holds parts, and
every number of a numbered answer is one of its part numbers, the answer
answers those parts, not items, unless the answer says `item`, as in `item 2 a`
or `approve item 2`, or its only number is the waiting item's own, as in `2 a`
or `approve 2` while item 2 waits: those answer the item. The text names each part's letter; R on a part
asks to see the item again. When a part gets more than one letter, the answer
is refused whole; when a part is left unanswered, the item stays open and the
agent records nothing yet. When every part gets the same letter, the text
gives that letter's lines for the whole item. When the letters differ and are
each A, AO or D, the text says what each does for its part and gives the
CHECK_PROGRAM check command with one `--part-answer N=ANSWER` flag per part. When
they differ and one is Z, it says check cannot record a part deferred while
others are answered, and tells the agent to record nothing and ask the user to
answer again. Every other
numbered answer, one to an item with no parts included, reads its numbers as
item numbers.

A NUMBERED ANSWER THAT GIVES A, AO, D OR Z TO AN ITEM NOT WAITING, one the
`#next_to_present` line does not name, or more than one of those letters to
one item, is refused whole: the text names those items and tells the agent to
record nothing and ask the user to answer the waiting item with one letter,
because each check run records one answer for the waiting item.

OUTPUT: {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
"additionalContext": <text>}}. The hook never blocks or rewrites the prompt:
a block's reason reaches neither the agent nor the user's window, only the
terminal the session runs in. The text opens with one line naming the answer
and the approval-walk item it answers, or saying no approval-walk is open;
then the answer's lines.

WHEN READING THE WALK STATE FAILS, such as a minutes file that is not UTF-8,
the first line says so and why, and the text gives the answer's lines both for
an open approval-walk and for none. When an A, AO, Aa or D answer reaches an item
whose recommendation cannot be read, RECOMMENDATION_UNKNOWN_LINE says why and
what to do. A payload that is not JSON is a fault: one line on stderr, exit 1,
which Claude Code records as a non-blocking error.

Agent-facing messages follow
docs/nedschorus-wiki/nedschorus-how-to-write-an-agent-facing-message-such-as-a-hook-refusal-or-script-error.md.
"""
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECKOUT = HERE.parents[2]
WALK_FINDER_FILE = HERE / "walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py"
CHECK_PROGRAM = HERE / "walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py"
EXPLAIN_SKILL = CHECKOUT / ".claude" / "skills" / "explain" / "SKILL.md"

# Longer forms first, so `ao` is not read as `a` and `approve as obvious` not as `approve`.
WORDS = {"approve as obvious": "AO", "approved": "A", "approve": "A", "disapproved": "D",
         "disapprove": "D", "defer": "Z", "later": "Z", "repeat": "R"}
NUMBER = r"\d+(?:\.\d+)*"
JOINER = r"(?:\s*-\s*)?"
AO = rf"a{JOINER}o"
LETTER = rf"aa|{AO}|o{JOINER}[23]|[adzreo]"
SINGLE_LETTER = re.compile(rf"^(?:{LETTER})$", re.I)
WORD = "|".join(word.replace(" ", r"\s+") for word in WORDS)
ANSWER = rf"(?P<answer>{WORD}|{LETTER})"
ALL = re.compile(rf"^(?:all\s+(?P<first>{AO}|a)|(?P<last>{AO}|a)\s+to\s+all)$", re.I)
PAIR = rf"(?:items?\s*)?({NUMBER})\s*(?:[-:=)]\s*)?({AO}|[adzr])(?![a-z])"
NUMBERED = re.compile(rf"^(?:{PAIR}(?:[\s,;]+|$))+$", re.I)
PAIRS = re.compile(PAIR, re.I)
WORD_NUMBERS = re.compile(
    rf"^(?P<word>{WORD})\s+(?:items?\s+)?(?P<numbers>{NUMBER}(?:(?:\s*,\s*|\s+and\s+|\s+){NUMBER})*)$", re.I)
NOT_AN_ITEM_NUMBER = r"(?!(?:items?\s*)?\d)"
CONDITION = re.compile(rf"^{ANSWER}\s*[,;:\-]?\s+(?P<condition>(?:if|after)\b.+)$", re.I | re.S)
LETTER_RIDER = re.compile(
    rf"^(?P<answer>{LETTER})(?:\s*(?:[,;:]|\.(?=\s)|\s-)\s*|\s+(?=(?:but|and|then|also|plus)\b))"
    rf"{NOT_AN_ITEM_NUMBER}(?P<rest>\S.*)$", re.I | re.S)
WORD_RIDER = re.compile(rf"^(?P<answer>{WORD})\b[\s,;:.\-]+{NOT_AN_ITEM_NUMBER}(?P<rest>\S.*)$", re.I | re.S)
RECOMMENDATION = re.compile(r"Recommendation:(.*)$", re.I | re.M)
PART_START = re.compile(
    r"^(?:#{1,6}\s+)?(?:\*\*|__)?(?:part\s+(?P<labelled>\d+)\b|(?P<listed>\d+)(?:\*\*|__)?[.)](?=[\s*_]|$))",
    re.I)
MOST_PARTS = 5
ITEM_PAGE = re.compile(rf"^#item_page\s+item\s+({NUMBER})\s+of\s+\d+\s+(\S+)\s*$", re.I | re.M)
HEADING_POINT = re.compile(r"^[#\s*]*items?\s[^:]*:\s*(.*?)[\s*]*$", re.I)
# The walk-me-through skill's closing line after its link, word for word; the hook's test checks SKILL.md holds it.
ANSWER_LETTERS_TEXT = ("A approve · AO approve as obvious · Aa approve after an advisor check · D disapprove · "
                       "Z defer · E explain · O other options")
NO_RECOMMENDATION_PROBLEM = "no line starting \"Recommendation:\""
PARTS_NOT_TOLD_APART_PROBLEM = (
    "it is one of the items under the walk-document's heading `{heading}`, which holds more than one line "
    "starting \"Recommendation:\", and the hook could not tell which part of the text under that heading "
    "belongs to which item, because {missing} has no opening it reads. It reads an opening only on the first line of a top-level paragraph or "
    "top-level list item that starts with the item's label in bold, the number followed by `:`, `.` or `,` "
    "inside or right after the bold, as in `**Item 5: the label.**` or `- **Item 5, step 1.**`, or on the "
    "first line of a top-level paragraph that starts `Item 5:`, `Item 5.` or the full count `Item 5 of 9`")
CHANGE_MAKING_ANSWERS = ("A", "AO", "AA", "D")
# How an answer code is written to the agent: Aa's second letter is lower case.
CODE_NAMES = {"AA": "Aa"}

OPEN_WALK_OPENING = "The user answered \"{answer}\" to {item} of approval-walk {walk}."
NO_WALK_OPENING = "The user answered \"{answer}\"; no approval-walk is open."
WALK_UNKNOWN_OPENING = (
    "The user answered \"{answer}\"; the hook could not tell whether an approval-walk is open, because "
    "reading the approval-walk state failed: {error}")
WALK_UNKNOWN_FIND = (
    "Find out yourself: the last `#next_to_present` line in each of the checkout's docs/walk/*-minutes.md names its "
    "waiting item, and a value other than `none` or `closed` marks the approval-walk open.")
IF_WALK_OPEN = "If an approval-walk is open:"
IF_NO_WALK = "If no approval-walk is open:"

# The walk-me-through skill's text for Aa, word for word; the hook's test checks SKILL.md still holds it.
AA_SKILL_TEXT = (
    "**Aa** approves after an advisor check. Write in the conversation, for the advisor, the question "
    "whether anything it sees would change what the item decides, then the six questions listed in the "
    "section \"Advisor\", then call the advisor. If the advisor finds something that would change what the "
    "item decides, revise the item, mark what changed [advisor], and show the revised item again for the "
    "user to answer. Otherwise record the approval and go to the next item; what the advisor raised "
    "outside the item becomes a new item in the walk or a loose end. If the call fails, say so and show "
    "the item again, unapproved; the user may then answer A to approve it without the check."
)
# Each answer's lines: (lines while an approval-walk is open, lines while none is).
MEANINGS = {
    "A": (("{word} means approve: the user agrees with the recommendation of {item}{recommended}. "
           "Do what the recommendation says.",
           "Whether or not that makes a change, first run "
           "`python3 {checkout}/nc-systems/skills/walk-me-through/{program} check`, "
           "then the close command it prints, and do what close prints; write nothing in the minutes by hand."),
          ("{word} means approve: the user agrees with your last recommendation or proposal. Do what it says.",
           "If that makes a change, first save each text the change adds that has not had a fast read to a "
           "scratch file, run `python3 {checkout}/nc-systems/cold-read/cold-read-fast-read.py --target "
           "<that file>`, and apply the findings that hold.",
           "If a fast read prints a line opening FAILED, tell the user that line and make no change.",
           "If a finding would change what your recommendation decides, put the changed recommendation to "
           "the user instead of acting on it.",
           "Otherwise act on it, and say in your next message which fast reads were already done and which "
           "had to be run.")),
    "AO": (("AO means approve as obvious: the user agrees with the recommendation of {item}{recommended}, "
            "and finds the item obvious. Act as for A, with one difference: the minutes must mark the "
            "answer as obvious.",
            "Whether or not that makes a change, first run "
            "`python3 {checkout}/nc-systems/skills/walk-me-through/{program} check --obvious`, which marks the "
            "answer, then the close command it prints, and do what close prints; write nothing in the minutes by hand."),
           ("AO means approve as obvious: the user agrees with your last recommendation or proposal, and "
            "finds it obvious. With no approval-walk open there are no minutes to mark, so act exactly as "
            "for A.",)),
    "AA": (("Aa means approve after an advisor check: the user agrees with the recommendation of {item}{recommended}, "
            "once the advisor has checked it. The walk-me-through skill's text for Aa says what to do:",
            "{aa_skill_text}",
            "If the advisor's check leaves the approval standing, then whether or not it makes a change, first run "
            "`python3 {checkout}/nc-systems/skills/walk-me-through/{program} check --after-advisor`, which marks "
            "the answer, then the close command it prints, and do what close prints; write nothing in the minutes by hand."),
           ("Aa means approve after an advisor check: the user agrees with your last recommendation or proposal, "
            "once the advisor has checked it.",
            "Write in the conversation, for the advisor, the question whether anything it sees would change what "
            "you recommended, then the six questions listed in the walk-me-through skill's section \"Advisor\", "
            "then call the advisor.",
            "If the advisor finds something that would change your recommendation, put the changed recommendation "
            "to the user instead of acting on it; if the call fails, say so, and act only when he answers again.",
            "Otherwise act exactly as for A.")),
    "D": (("{word} means disapprove: the user disagrees with the recommendation of {item}{recommended}.",
           "If the item gives no single alternative, ask the user what he wants done instead, and act on "
           "nothing yet.",
           "Otherwise do the item's alternative; whether or not it makes a change, first run "
           "`python3 {checkout}/nc-systems/skills/walk-me-through/{program} check --disapproved`, "
           "then the close command it prints, and do what close prints; write nothing in the minutes by hand."),
          ("{word} means disapprove: the user disagrees with your last recommendation or proposal. Do not "
           "act on it.",
           "If he has said what he wants instead, do that, with a fast read first of any text it adds, as "
           "for an approval; otherwise ask him.")),
    "O": (("O asks for other options: the user is not answering {item} yet, and wants to see it again with two "
           "other options beside your recommendation.",
           "Write two paragraphs into the item in the walk-document, below its recommendation: one opening "
           "\"Option 2:\", a simpler option, one that does the job with more code and less prompt text and AI "
           "judgement; and one opening \"Option 3:\", a more creative option.",
           "In each paragraph say what the option is, how it differs from your recommendation, and its pluses "
           "and minuses. Leave the recommendation as it is.",
           "Below the two paragraphs, add this line: \"Answer O2 or O3 to take that option; A still takes the "
           "recommendation, and the other answers work as before.\"",
           "Then republish the item's page as its new version, and show the item again in full, word for word as "
           "the walk-document has it."),
          ("O asks for other options: the user is not answering your last recommendation or proposal yet, and "
           "wants two other options beside it.",
           "Show him two paragraphs: one opening \"Option 2:\", a simpler option, one that does the job with more "
           "code and less prompt text and AI judgement; and one opening \"Option 3:\", a more creative option.",
           "In each paragraph say what the option is, how it differs from your recommendation, and its pluses "
           "and minuses.",
           "End with this line: \"Answer O2 or O3 to take that option; A still takes the recommendation.\"")),
    "Z": (("Z means defer: move {item} as the walk-me-through skill's sentence on Z says.",
           "Then run the check step with --deferred, then close, and do what close prints."),
          ("Z means defer: postpone your last question or proposal and record it as a task.",)),
    "R": (("\"{word}\" asks to see {item} again: show it in full, heading included, word for word as the "
           "walk-document has it, and wait for his answer.",),
          ("{word} asks to see your last question or proposal again: show it in full, word for word, "
           "and wait for his answer.",)),
    "E": (("E means explain: run the explain skill, {explain_skill}, on {item}.",),
          ("E means explain: run the explain skill, {explain_skill}, on your last message.",)),
}
# O2 and O3 approve an option the agent showed after an O, instead of the recommendation.
OPTION_TAKEN_LINES = (
    ("O{option} means the user approves option {option} of {item}: the paragraph \"Option {option}:\" in the "
     "walk-document, not your recommendation. Do what that option says.",
     "If the item has no \"Option {option}:\" paragraph, ask the user what he means, and act on nothing yet.",
     "Whether or not the option makes a change, first run "
     "`python3 {checkout}/nc-systems/skills/walk-me-through/{program} check --option {option}`, "
     "then the close command it prints, and do what close prints; write nothing in the minutes by hand."),
    ("O{option} means the user approves option {option} of your last message, not your recommendation. Do what "
     "that option says.",
     "If your last message had no option {option}, ask the user what he means, and act on nothing yet.",
     "If the option makes a change, first save each text it adds that has not had a fast read to a scratch "
     "file, run `python3 {checkout}/nc-systems/cold-read/cold-read-fast-read.py --target <that file>`, and "
     "apply the findings that hold.",
     "If a fast read prints a line opening FAILED, tell the user that line and make no change."),
)
MEANINGS.update({f"O{option}": tuple(tuple(line.replace("{option}", option) for line in lines)
                                     for lines in OPTION_TAKEN_LINES) for option in ("2", "3")})
REPEAT_PAGE_LINE = (
    "\"{answer}\" asks to see {item} again. Its page shows it in full, so reply with only this closing line, "
    "word for word, and wait for his answer: {closing_line}")
NUMBERED_R_WAITING_ITEM_LINE = "Then end your message naming the item waiting for his answer, {item}."
# Check records one answer for every item the `#next_to_present` line names, and close moves that line on.
ONE_ITEM_AT_A_TIME_LINE = (
    "Before each check run, if the minutes' last `#next_to_present` line does not name that item alone, add "
    "the line `{one_item_line}` for it, with its number, as the minutes' last line, because the walk-me-through "
    "skill has that line name one item, or one part such as `item 4.1 of 9`. Present the item that `close` names "
    "only after the last answer is recorded.")
ALL_LINES = {
    "A": (("\"{answer}\" means A to every item now waiting, {item}: the user agrees with each one's "
           "recommendation. Do what each recommends. For each item, whether or not it makes a change, run "
           "the check step, then close, and do what close prints; write nothing in the minutes by hand but the "
           "`#next_to_present` lines below.", ONE_ITEM_AT_A_TIME_LINE),
          ("\"{answer}\" means the user agrees with every recommendation or proposal your last message left "
           "open. Act on each as the lines below say for a single approval.",) + MEANINGS["A"][1][1:]),
    "AO": (("\"{answer}\" means AO to every item now waiting, {item}: the user agrees with each one's "
            "recommendation and finds each obvious. Do what each recommends. For each item, whether or not "
            "it makes a change, run the check step (with --obvious for `all ao`), then close, and do what close "
            "prints; write nothing in the minutes by hand but the `#next_to_present` lines below.", ONE_ITEM_AT_A_TIME_LINE),
           ("\"{answer}\" means the user agrees with every recommendation or proposal your last message left "
            "open, and finds each obvious. With no approval-walk open there are no minutes to mark, so act on "
            "each as the lines below say for a single approval.",) + MEANINGS["A"][1][1:]),
}
NUMBERED_LINES = (
    ("The answer gives each item it names its own letter: {pairs}.",
     "A agrees with the item's recommendation; AO does the same and marks the approval as obvious, with the "
     "flag --obvious; D disagrees with it, so D does the item's alternative, with the flag --disapproved; Z "
     "defers the item, with the flag --deferred; R shows the item again.",
     "Record the answers one item at a time, in the order given: for each, run the check step with that "
     "answer's flag, then close, and do what close prints, before the next.",
     ONE_ITEM_AT_A_TIME_LINE,
     "If check or close refuses or fails, stop there and record none of the remaining answers: tell the user "
     "which answers were recorded and what was printed, and ask him how to go on."),
    ("The answer gives each numbered question or point of your last message its own letter: {pairs}.",
     "Every question or point the answer does not name stays open; say so in your reply."),
)
NUMBERED_REFUSED_LINES = (
    "The answer {problems}, and the minutes' `#next_to_present` line names only {item}.",
    "Record nothing and act on none of the answer: each check run records one answer against the item the "
    "`#next_to_present` line names, and close then moves that line on to the next item, so a letter for "
    "another item, or a second letter for the same item, would be recorded against an item the user did not "
    "answer.",
    "Ask the user to answer {item} with one letter; the other items come to him one at a time after it.",
)
NUMBERED_NOT_WAITING_PROBLEM = "gives a letter to {items}, which {verb} not waiting for an answer"
NUMBERED_REPEATED_PROBLEM = "gives {items} more than one letter"
PARTS_READ_LINE = (
    "The numbers are the part numbers of {item}, which holds parts {parts} of one fix, as the walk-me-through "
    "skill lets an item do; the answer gives each part it names its own letter: {pairs}.")
PARTS_REPEATED_LINES = (
    "The answer gives {parts} of {item} more than one letter.",
    "Record nothing and act on none of the answer, because the letters for that part contradict each other.",
    "Ask the user to answer every part of {item} again, giving each part's number once with its letter, as in "
    "`1 a 2 d`.",
)
PART_R_LINE = (
    "R on a part asks to see {item} again: show it in full, heading included, word for word as the walk-document "
    "has it.")
PARTS_SAME_LETTER_LINE = (
    "Every part has the answer {letter}, so the answer is {letter} to the whole of {item}, and means what the "
    "lines below say.")
PARTS_DIFFERENT_LETTERS_LINES = (
    "Each part's letter does for that part what it does for a whole item: A approves the part's recommendation, "
    "so do what it says; AO does the same and marks the approval as obvious; D disapproves it, so do the "
    "part's alternative.",
    "If a part answered D gives no single alternative, ask the user what he wants done instead, and act on "
    "nothing yet.",
    "Otherwise, whether or not the parts make a change, first run "
    "`python3 {checkout}/nc-systems/skills/walk-me-through/{program} check {flags}`, which records each part's "
    "answer, then the close command it prints, and do what close prints; write nothing in the minutes by hand.",
)
PARTS_NOT_RECORDABLE_LINES = (
    "The check step cannot record this answer: `{program} check --part-answer` takes A, AO or D for a part, because "
    "the walk-me-through skill does not say where an item goes in the walk when one of its parts is deferred "
    "and the others are answered.",
    "Record nothing and act on none of the parts.",
    "Tell the user that the walk-me-through check program cannot record a deferred part beside answered ones, "
    "and ask him to answer every part of {item} with A, AO or D, to answer Z to the whole item, or to say how "
    "else to go on.",
)
PARTS_UNANSWERED_LINES = (
    "The answer does not name {unanswered}, and the walk-me-through skill keeps an item open while a part is "
    "unanswered, so record nothing in the minutes and act on none of the parts of {item}.",
    "Ask the user to answer every part of {item} in one reply, the parts he has answered included, giving each "
    "part's number with its letter, as in `1 a 2 d`, because this hook reads each reply on its own, so a reply "
    "that names only the parts still missing would leave the others unanswered.")
NUMBERED_UNNAMED_LINE = "The answer does not name {unnamed}, so it stays open; say so in your reply."
NUMBERED_ALL_NAMED_LINE = "The answer names every item now waiting."
CONDITION_LINES = (
    "The user set a condition on the answer: \"{condition}\".",
    "Meet the condition before you record or act on the answer.",
    "If meeting the condition changes what the user was answering, show it to him again instead.",
    "The answer itself means:",
)
RIDER_LINES = (
    "The user added to the answer: \"{rest}\".",
    "Act on the answer as the lines below say, then act on what he added.",
    "If what he added contradicts or limits the answer, ask him which he means before acting on either.",
    "If what he added cannot be done this turn, record it as a task.",
    "The answer itself means:",
)
RECOMMENDATION_UNKNOWN_LINE = (
    "The hook could not read the recommendation of {item}: {problem}. Read the recommendation in the "
    "walk-document yourself. If you find it, act on {answer_letter} as usual; if you cannot, ask the user "
    "what he wants done before acting on {answer_letter}.")


def load_walk_finder():
    spec = importlib.util.spec_from_file_location(
        "walk_me_through_approval_walk_minutes_and_walk_document_item_finder_common", WALK_FINDER_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def answer_code(answer):
    """The answer's code, A, AO, AA for Aa, D, Z, R, E, O, O2 or O3, from a letter or a word in any case and
    spacing, with any hyphen between the letters dropped."""
    lowered = " ".join(answer.lower().split())
    return WORDS.get(lowered) or re.sub(r"[\s-]", "", lowered).upper()


def parsed_answer(prompt):
    """Return a dict describing the answer form the whole prompt is, or None."""
    raw = prompt.strip()
    text = raw[:-1].rstrip() if raw.endswith(".") else raw
    lowered = " ".join(text.lower().split())
    if SINGLE_LETTER.match(text) or lowered in WORDS:
        return {"form": "single", "answer": text, "code": answer_code(text)}
    match = ALL.match(text)
    if match:
        return {"form": "all", "answer": text, "code": answer_code(match["first"] or match["last"])}
    if NUMBERED.match(text):
        return {"form": "numbered", "answer": text, "says item": "item" in lowered,
                "pairs": [(number, answer_code(letter)) for number, letter in PAIRS.findall(text)]}
    match = WORD_NUMBERS.match(text)
    if match:
        numbers = re.findall(NUMBER, match["numbers"])
        return {"form": "numbered", "answer": text, "says item": "item" in lowered,
                "pairs": [(n, answer_code(match["word"])) for n in numbers],
                "every number names an item": len(numbers) > 1}
    match = CONDITION.match(text)
    if match:
        return {"form": "condition", "answer": text, "code": answer_code(match["answer"]),
                "word": match["answer"], "condition": match["condition"]}
    match = LETTER_RIDER.match(raw) or WORD_RIDER.match(raw)
    if match:
        return {"form": "rider", "answer": raw, "code": answer_code(match["answer"]),
                "word": match["answer"], "rest": match["rest"].strip()}
    return None


class WalkState:
    """The open approval-walk as the hook read it."""

    def __init__(self, name, item, numbers, total, recommendations, problem, recommendation_problems=None,
                 parts=None, pages=None, points=None):
        self.name, self.item, self.numbers, self.total = name, item, numbers, total
        self.pages = pages or {}  # item number -> link of its newest `#item_page` line
        self.points = points or {}  # item number -> the point its walk-document heading states
        self.recommendations = recommendations  # item number -> recommendation text or None
        self.problem = problem  # why recommendations could not be read, or None
        # item number -> why its recommendation is None, when the reason is not NO_RECOMMENDATION_PROBLEM
        self.recommendation_problems = recommendation_problems or {}
        self.parts = parts or {}  # item number -> its part numbers, for the items that hold parts


def read_walk(cwd):
    """Return the WalkState of the open approval-walk, or None when none is open."""
    walk_finder = load_walk_finder()
    top = walk_finder.checkout_top(Path(cwd))
    if top is None or not (top / walk_finder.WALK_DIRECTORY).is_dir():
        return None
    parser = walk_finder.markdown_parser()
    walk = walk_finder.open_walk(top / walk_finder.WALK_DIRECTORY, parser)
    if walk is None:
        return None
    minutes, value, _ = walk
    name = minutes.name[:-len(walk_finder.MINUTES_SUFFIX)]
    # The newest line for an item wins, since a re-planned walk records its pages again.
    pages = {number: link for number, link in ITEM_PAGE.findall(
        "\n".join(walk_finder.prose_lines(minutes.read_text(encoding="utf-8"), parser)))}
    count = walk_finder.VALUE_COUNT.match(value)
    if not count:
        return WalkState(name, f"the item its minutes' `#next_to_present` line names, `{value}`,",
                         [], None, {}, f"the `#next_to_present` line, `{value}`, names no item")
    try:
        numbers, total = walk_finder.parse_items(value)
    except walk_finder.UnusableRange as problem:
        return WalkState(name, count[0], [], None, {}, f"the `#next_to_present` line, `{value}`, {problem}")
    document = minutes.with_name(name + ".md")
    if not document.is_file():
        return WalkState(name, count[0], numbers, total, {}, f"the walk-document {document} does not exist")
    text = document.read_text(encoding="utf-8")
    tokens = parser.parse(text)
    spans = walk_finder.item_unit_spans(text, parser)
    if total is None:
        totals = {span[1] for span in spans}
        total = totals.pop() if len(totals) == 1 else None
    recommendations, problems, parts = recommendations_in(
        walk_finder.prose_lines(text, parser, tokens), walk_finder.item_opening_lines(text, parser, tokens),
        spans, total, walk_finder)
    return WalkState(name, count[0], numbers, total, recommendations, None, problems, parts, pages,
                     heading_points(text.split("\n"), spans, total, parser))


def heading_points(lines, spans, total, parser):
    """{item number: the point its heading states after the running count's colon, without its links} for the
    walk's items."""
    points = {}
    for numbers, unit_total, _, first, _ in spans:
        match = HEADING_POINT.match(lines[first])
        if match and match[1] and (total is None or unit_total == total):
            points.update({number: without_links(match[1], parser) for number in numbers})
    return points


def without_links(markdown, parser):
    """The inline Markdown with each link's text kept and its link syntax gone, since the closing line puts the
    point inside a link label, where a link of its own would leave the closing line unclickable."""
    pieces = []
    for token in parser.parseInline(markdown)[0].children:
        if token.type in ("link_open", "link_close"):
            continue
        if token.type in ("text", "image"):
            # The parser has decoded the text's escapes and entities, so each character that would start
            # markup or an entity is escaped again, or the closing line would show something the heading does not.
            pieces.append(re.sub(r"([\\`*_\[\]<>!&])", r"\\\1", token.content))
        elif token.type == "code_inline":
            # The parser drops the padding space that lets a code span's content start or end with a backtick
            # or a space; without it the rebuilt fence takes in an edge backtick, or the parser strips an edge space.
            content = token.content
            if content.strip(" ") and {content[0], content[-1]} & {"`", " "}:
                content = f" {content} "
            pieces.append(token.markup + content + token.markup)
        else:
            pieces.append(token.markup or token.content)
    return "".join(pieces)


def closing_line(number, walk):
    """The walk-me-through skill's closing line for the item, or None when the minutes record no page for it."""
    link = walk.pages.get(number)
    if link is None:
        return None
    point = walk.points.get(number)
    label = "Item " + item_name(number, walk)[len("item "):] + (f", {point}" if point else "")
    return f"[{label}]({link}) · {ANSWER_LETTERS_TEXT}"


def recommendation_text(part):
    """The last recommendation in the lines, as written, without emphasis or one trailing period; or None."""
    found = [match[1].strip(" *_") for match in RECOMMENDATION.finditer("\n".join(part))]
    found = [text[:-1].rstrip(" *_") if text.endswith(".") else text for text in found]
    return found[-1] if found and found[-1] else None


def part_numbers(part):
    """The part numbers 1 to K that the lines number, as the docstring's PARTS OF THE WAITING ITEM says, or
    an empty list when they number no parts."""
    found = {int(match["labelled"] or match["listed"]) for match in map(PART_START.match, part) if match}
    return sorted(found) if 1 < len(found) <= MOST_PARTS and found == set(range(1, len(found) + 1)) else []


def recommendations_in(lines, openings, spans, total, walk_finder):
    """Return ({item number: recommendation text or None} for every item of the walk-document, {item number:
    why its recommendation is None} for the items whose reason is not NO_RECOMMENDATION_PROBLEM, {item number:
    its part numbers} for the items that hold parts), from its prose_lines and item_opening_lines.

    Under a heading that names several items and holds more than one recommendation, every item's
    recommendation is None when any of them has no opening, since an opening missed leaves the part
    before it running on into the next item's recommendation."""
    found, problems, parts = {}, {}, {}
    for numbers, unit_total, _, first, end in spans:
        if total is not None and unit_total != total:
            continue
        ranges = {number: (first, end) for number in numbers}
        if len(numbers) > 1:
            ranges = {number: walk_finder.approval_walk_item_line_range_within_heading_shared_by_several_items(
                openings, first, end, number, numbers, unit_total) for number in numbers}
            # An item with no opening of its own is given the whole unit, which starts at the heading.
            missing = [number for number in numbers if ranges[number][0] == first]
            if missing and len(RECOMMENDATION.findall("\n".join(lines[first:end]))) > 1:
                problem = PARTS_NOT_TOLD_APART_PROBLEM.format(
                    heading=lines[first].strip(), missing=", ".join(f"item {number}" for number in missing))
                for number in numbers:
                    found[number], problems[number] = None, problem
                continue
        for number in numbers:
            part = lines[ranges[number][0]:ranges[number][1]]
            found[number] = recommendation_text(part)
            numbered = part_numbers(part)
            if numbered:
                parts[number] = numbered
    return found, problems, parts


def item_name(number, walk):
    return f"item {number} of {walk.total}" if walk and walk.total else f"item {number}"


def recommendation_unknown_lines(answer_letter, numbers, walk):
    """A line for each item an A, AO, Aa or D answer reaches whose recommendation the hook could not read."""
    if answer_letter not in CHANGE_MAKING_ANSWERS or walk is None:
        return []
    name = CODE_NAMES.get(answer_letter, answer_letter)
    if walk.problem:
        return [RECOMMENDATION_UNKNOWN_LINE.format(item=walk.item, problem=walk.problem, answer_letter=name)]
    return [RECOMMENDATION_UNKNOWN_LINE.format(
                item=item_name(number, walk), answer_letter=name,
                problem=walk.recommendation_problems.get(number, NO_RECOMMENDATION_PROBLEM))
            for number in numbers if walk.recommendations.get(number) is None]


def answered_parts(answer, walk):
    """The waiting item's part numbers when the numbered answer answers its parts, or None."""
    if answer["form"] != "numbered" or walk is None or len(walk.numbers) != 1 or answer["says item"]:
        return None
    # Many items number their own number among their parts; `2 a` while item 2 waits answers the item.
    if {number for number, _ in answer["pairs"]} == set(walk.numbers):
        return None
    parts = walk.parts.get(walk.numbers[0])
    if parts and all(number.isdigit() and int(number) in parts for number, _ in answer["pairs"]):
        return parts
    return None


def parts_lines(answer, parts, walk):
    """The lines for a numbered answer that answers the parts of the one waiting item."""
    def named(numbers):
        return ", ".join(f"part {number}" for number in numbers)
    item = walk.item
    deciding = [(int(number), letter) for number, letter in answer["pairs"] if letter != "R"]
    numbers = [number for number, _ in deciding]
    repeated = [number for number in dict.fromkeys(numbers) if numbers.count(number) > 1]
    if repeated:
        return [line.format(parts=named(repeated), item=item) for line in PARTS_REPEATED_LINES]
    pairs = ", ".join(f"part {int(number)}: {letter}" for number, letter in answer["pairs"])
    lines = [PARTS_READ_LINE.format(item=item, parts=f"1 to {parts[-1]}", pairs=pairs)]
    if len(deciding) < len(answer["pairs"]):
        lines.append(PART_R_LINE.format(item=item))
    letters = {letter for _, letter in deciding}
    unanswered = [number for number in parts if number not in numbers]
    if not deciding:
        return lines
    if unanswered:
        return lines + [line.format(unanswered=named(unanswered), item=item) for line in PARTS_UNANSWERED_LINES]
    if len(letters) > 1 and "Z" in letters:
        return lines + [line.format(program=CHECK_PROGRAM.name, item=item) for line in PARTS_NOT_RECORDABLE_LINES]
    if len(letters) > 1:
        flags = " ".join(f"--part-answer {number}={letter}" for number, letter in sorted(deciding))
        return lines + [line.format(checkout=CHECKOUT, program=CHECK_PROGRAM.name, flags=flags)
                        for line in PARTS_DIFFERENT_LETTERS_LINES]
    letter = letters.pop()
    return [*lines, PARTS_SAME_LETTER_LINE.format(letter=letter, item=item),
            *meaning_lines({"form": "single", "answer": letter, "code": letter}, walk, True)]


def meaning_lines(answer, walk, in_walk):
    """The answer's lines for an open approval-walk (in_walk) or for none."""
    branch = 0 if in_walk else 1
    walk = walk if in_walk else None
    item = walk.item if walk else "the waiting item"
    numbers = walk.numbers if walk else []
    values = {"item": item, "answer": answer["answer"], "checkout": CHECKOUT, "program": CHECK_PROGRAM.name,
              "explain_skill": EXPLAIN_SKILL, "aa_skill_text": AA_SKILL_TEXT,
              "one_item_line": "#next_to_present item <number>" + (f" of {walk.total}" if walk and walk.total else "")}
    form = answer["form"]
    parts = answered_parts(answer, walk)
    if parts:
        return parts_lines(answer, parts, walk)
    if form == "numbered":
        deciding = [number for number, letter in answer["pairs"] if in_walk and numbers and letter != "R"]
        not_waiting = [number for number in dict.fromkeys(deciding) if number not in numbers]
        named_twice = [number for number in dict.fromkeys(deciding) if deciding.count(number) > 1]
        problems = []
        if not_waiting:
            problems.append(NUMBERED_NOT_WAITING_PROBLEM.format(
                items=", ".join(item_name(number, walk) for number in not_waiting),
                verb="are" if not_waiting[1:] else "is"))
        if named_twice:
            problems.append(NUMBERED_REPEATED_PROBLEM.format(
                items=", ".join(item_name(number, walk) for number in named_twice)))
        if problems:
            return [line.format(problems=" and ".join(problems), item=item) for line in NUMBERED_REFUSED_LINES]
        pairs = ", ".join(f"{item_name(number, walk) if in_walk else number}: {letter}"
                          for number, letter in answer["pairs"])
        # R records nothing, and a check run with no flag would record an A, so R alone gets no recording lines.
        only_repeats = in_walk and all(letter == "R" for _, letter in answer["pairs"])
        lines = [] if only_repeats else [line.format(pairs=pairs, one_item_line=values["one_item_line"])
                                         for line in NUMBERED_LINES[branch]]
        if in_walk:
            named = {number for number, _ in answer["pairs"]}
            unnamed = [number for number in numbers if number not in named]
            if not only_repeats:
                lines.append(NUMBERED_UNNAMED_LINE.format(unnamed=", ".join(item_name(n, walk) for n in unnamed))
                             if unnamed else NUMBERED_ALL_NAMED_LINE)
            for number, letter in answer["pairs"]:
                lines += recommendation_unknown_lines(letter, [number], walk)
            repeated = [number for number, letter in answer["pairs"] if letter == "R"]
            lines += [repeat_line(f"{number} R", number, walk) for number in repeated]
            answered = {number for number, letter in answer["pairs"] if letter != "R"}
            still_waiting = [number for number in numbers if number not in answered]
            if repeated and still_waiting:
                lines.append(NUMBERED_R_WAITING_ITEM_LINE.format(
                    item=", ".join(item_name(n, walk) for n in still_waiting)))
        return lines
    code = answer["code"]
    if form == "all":
        return ([line.format(**values) for line in ALL_LINES[code][branch]]
                + recommendation_unknown_lines(code, numbers, walk))
    word = " ".join(answer.get("word", answer["answer"]).split())
    recommendation = None
    if walk and len(numbers) == 1 and not walk.problem:
        recommendation = walk.recommendations.get(numbers[0])
    values.update(word=word[:1].upper() + word[1:].lower(),
                  recommended=f" ({recommendation})" if recommendation else "")
    if code == "R" and walk and numbers:
        return [repeat_line(values["word"], number, walk) for number in numbers]
    lines = [line.format(**values) for line in MEANINGS[code][branch]]
    return lines + recommendation_unknown_lines(code, numbers, walk)


def repeat_line(answer, number, walk):
    """The line telling the agent how to answer an R for the item: its closing line, or the item in full."""
    line = closing_line(number, walk)
    if line is None:
        return MEANINGS["R"][0][0].format(word=answer, item=item_name(number, walk))
    return REPEAT_PAGE_LINE.format(answer=answer, item=item_name(number, walk), closing_line=line)


def output_for(payload):
    """Return the hook's output for the payload as a dict, or None."""
    answer = parsed_answer(payload.get("prompt") or "")
    if answer is None:
        return None
    try:
        walk, walk_error = read_walk(payload.get("cwd") or os.getcwd()), None
    except Exception as error:
        walk, walk_error = None, error
    if named_item_missing(answer, walk, walk_error):
        return None
    context = context_for(answer, walk, walk_error)
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": context}}


def named_item_missing(answer, walk, walk_error):
    """Whether a numbered answer gives R, or a word with a list of numbers, to a number no item of the
    open approval-walk has, or no approval-walk is open; False when the walk, its `#next_to_present` line
    or its walk-document cannot be read, so that the context says why."""
    numbers = [number for number, letter in answer.get("pairs", [])
               if letter == "R" or answer.get("every number names an item")]
    if not numbers or walk_error is not None or (walk is not None and walk.problem) or answered_parts(answer, walk):
        return False
    return walk is None or any(number not in walk.recommendations for number in numbers)


def context_for(answer, walk, walk_error):
    """Return the additionalContext text for the answer, given the open approval-walk as read_walk read it, or
    the error reading it raised."""
    prefix = []
    if answer["form"] == "condition":
        prefix = [line.format(condition=answer["condition"]) for line in CONDITION_LINES]
    elif answer["form"] == "rider":
        prefix = [line.format(rest=answer["rest"]) for line in RIDER_LINES]
    if walk_error is not None:
        lines = [WALK_UNKNOWN_OPENING.format(answer=answer["answer"], error=repr(walk_error)), WALK_UNKNOWN_FIND]
        lines += prefix + [IF_WALK_OPEN]
        lines += meaning_lines(answer, WalkState("", "the waiting item", [], None, {}, None), True)
        lines += [IF_NO_WALK] + meaning_lines(answer, None, False)
    else:
        if walk is None:
            lines = [NO_WALK_OPENING.format(answer=answer["answer"])] + prefix + meaning_lines(answer, None, False)
        else:
            lines = ([OPEN_WALK_OPENING.format(answer=answer["answer"], item=walk.item, walk=walk.name)]
                     + prefix + meaning_lines(answer, walk, True))
    return "\n".join(lines)


def main():
    try:
        output = output_for(json.loads(sys.stdin.read()))
    except Exception as error:
        print(f"walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook: the hook "
              f"failed, so a short answer was not expanded: {error!r}", file=sys.stderr)
        return 1
    if output is not None:
        print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
