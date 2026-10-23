#!/usr/bin/env python3
"""UserPromptSubmit hook: when the user's whole prompt is a short answer, such
as A, `approved`, `37.4 r` or `1 a 2 d`, add context that tells the agent
what the answer means and what to do.

Wired as a UserPromptSubmit hook in .claude/settings.json. The prompt is
stripped of surrounding whitespace, and of one trailing period for every form
but a rider, then read, ignoring case, as the first of these forms it matches:

  SINGLE      one answer: A, AO, Aa, D, Z, R, E, O, O2 or O3, or a word approve,
              approved, approve as obvious, disapprove, disapproved, defer,
              later or repeat.
  ALL         `all a`, `a to all`, `all ao`, `ao to all`.
  NUMBERED    one or more pairs of an item number and A, AO, D, Z or R:
              `8a`, `6 - a`, `1 a 2 d`, `5 d, 6 z`, `item 3 ao`, `37.4 r`; or a
              word, then item numbers: `repeat 37.4` reads as `37.4 r`,
              `approve item 5` as `5 a`, `approve 5 and 6` as `5 a, 6 a`.
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
recommends nothing.

R ON AN OPEN APPROVAL-WALK, as the whole prompt (R or repeat), is shown by
the hook itself: it blocks the prompt with {"decision": "block", "reason":
<the walk-document's units holding the waiting items, as written>}, which
Claude Code shows the user without running the model; the walk-minutes record
nothing. When the units cannot be read, the hook does not block: the
additionalContext below opens with REPEAT_NOT_SHOWN_LINES saying why, and the
agent shows the item. A NUMBERED answer whose every letter is R, such as
`37.4 r` or `37.4 r, 38 r`, is shown the same way, with the units holding the
items it names. In a NUMBERED answer that mixes R with other letters, each R
tells the agent to show that item. When no approval-walk is open, or its
walk-document has no item with a number an R names, or with one of the
numbers after a word, as in `approve 5 and 6`, the hook prints nothing, so
the prompt reaches the agent as typed; when the walk-document or the
`#next_to_present` line cannot be read, the text says why instead.

A NUMBERED ANSWER THAT GIVES A, AO, D OR Z TO AN ITEM NOT WAITING, one the
`#next_to_present` line does not name, is refused whole: the text names that
item and tells the agent to record nothing and ask the user to answer the
waiting item on its own, because the check step records an answer only for
the waiting item.

OUTPUT otherwise: {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
"additionalContext": <text>}}. No other answer blocks, and the hook never
rewrites the prompt. The text opens with one line naming the answer and the approval-walk
item it answers, or saying no approval-walk is open; then the answer's lines;
then ONE_QUESTION_LINE.

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
LETTERS = ("aa", "ao", "a", "d", "z", "r", "e", "o", "o2", "o3")
NUMBER = r"\d+(?:\.\d+)*"
LETTER = r"aa|ao|o[23]|[adzreo]"
WORD = "|".join(word.replace(" ", r"\s+") for word in WORDS)
ANSWER = rf"(?P<answer>{WORD}|{LETTER})"
ALL = re.compile(r"^(?:all\s+(?P<first>ao|a)|(?P<last>ao|a)\s+to\s+all)$", re.I)
PAIR = rf"(?:items?\s*)?({NUMBER})\s*(?:[-:=)]\s*)?(ao|[adzr])(?![a-z])"
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
NO_RECOMMENDATION_PROBLEM = "no line starting \"Recommendation:\""
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
ONE_QUESTION_LINE = (
    "If your last message to the user left more than one question open, ask him which one this "
    "answer is for, naming each, and act on none of them until he says.")

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
CHECK_COMMAND = "`python3 {checkout}/nc-systems/skills/walk-me-through/{program} check`"
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
           "Replace the item's answer line in the walk-document with this one: \"Answer O2 or O3 to take that "
           "option; A still takes the recommendation, and the other answers work as before.\"",
           "Then show the item again in full, word for word as the walk-document has it."),
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
    "R": (("{word} asks to see {item} again: show it in full, word for word as the walk-document "
           "has it, and wait for his answer.",),
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
NUMBERED_R_LINES = (
    "\"{answer}\" asks to see item {number}{of_total} again: show it in full, word for word as the "
    "walk-document has it.",
    "Then end your message naming the item waiting for his answer, {item}.",
)
ALL_LINES = {
    "A": (("\"{answer}\" means A to every item now waiting, {item}: the user agrees with each one's "
           "recommendation. Do what each recommends. For each item, whether or not it makes a change, run "
           "the check step, then close, and do what close prints; write nothing in the minutes by hand.",),
          ("\"{answer}\" means the user agrees with every recommendation or proposal your last message left "
           "open. Act on each as for a single approval, with the fast reads that text sets out.",)),
    "AO": (("\"{answer}\" means AO to every item now waiting, {item}: the user agrees with each one's "
            "recommendation and finds each obvious. Do what each recommends. For each item, whether or not "
            "it makes a change, run the check step (with --obvious for `all ao`), then close, and do what "
            "close prints; write nothing in the minutes by hand.",),
           ("\"{answer}\" means the user agrees with every recommendation or proposal your last message left "
            "open, and finds each obvious. Act on each as for a single approval, with the fast reads that "
            "text sets out.",)),
}
NUMBERED_LINES = (
    ("The answer gives each item it names its own letter: {pairs}.",
     "A agrees with the item's recommendation; AO does the same and marks the approval as obvious, with the "
     "flag --obvious; D disagrees with it, so D does the item's alternative, with the flag --disapproved; Z "
     "defers the item, with the flag --deferred; R shows the item again.",
     "Record the answers one item at a time, in the order given: for each, run the check step with that "
     "answer's flag, then close, and do what close prints, before the next. If check reports more than one "
     "item waiting, record nothing, and ask the user to answer those items one at a time."),
    ("The answer gives each numbered question or point of your last message its own letter: {pairs}.",
     "Every question or point the answer does not name stays open; say so in your reply."),
)
NUMBERED_NOT_WAITING_LINES = (
    "The answer gives a letter to {not_waiting}, which {verb} not waiting for an answer: the minutes' "
    "`#next_to_present` line names only {item}.",
    "Record nothing and act on none of the answer: the check step records an answer for the waiting item only, "
    "so running it for another item's letter would record that letter against an item the user did not answer.",
    "Ask the user to answer {item} first; the other items come to him one at a time after it.",
)
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
# R on an open approval-walk is shown by the hook itself; when it cannot be, the agent shows it.
REPEAT_NOT_SHOWN_LINES = (
    "The hook could not show {item} to the user itself: {problem}",
    "Show it to him as the lines for R below say; if you cannot find it either, tell him what the line "
    "above says, and ask him how to go on.",
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
    spacing."""
    lowered = " ".join(answer.lower().split())
    return WORDS.get(lowered, lowered.upper())


def parsed_answer(prompt):
    """Return a dict describing the answer form the whole prompt is, or None."""
    raw = prompt.strip()
    text = raw[:-1].rstrip() if raw.endswith(".") else raw
    lowered = " ".join(text.lower().split())
    if lowered in LETTERS or lowered in WORDS:
        return {"form": "single", "answer": text, "code": answer_code(text)}
    match = ALL.match(text)
    if match:
        return {"form": "all", "answer": text, "code": (match["first"] or match["last"]).upper()}
    if NUMBERED.match(text):
        return {"form": "numbered", "answer": text,
                "pairs": [(number, letter.upper()) for number, letter in PAIRS.findall(text)]}
    match = WORD_NUMBERS.match(text)
    if match:
        numbers = re.findall(NUMBER, match["numbers"])
        return {"form": "numbered", "answer": text, "pairs": [(n, answer_code(match["word"])) for n in numbers],
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

    def __init__(self, name, item, numbers, total, recommendations, problem):
        self.name, self.item, self.numbers, self.total = name, item, numbers, total
        self.recommendations = recommendations  # item number -> recommendation text or None
        self.problem = problem  # why recommendations could not be read, or None


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
    spans = walk_finder.item_unit_spans(text, parser)
    if total is None:
        totals = {span[1] for span in spans}
        total = totals.pop() if len(totals) == 1 else None
    return WalkState(name, count[0], numbers, total, recommendations_in(text.split("\n"), spans, total, walk_finder), None)


class WaitingItemNotShown(Exception):
    """The waiting item's section could not be read; its arguments are the item and why."""


def item_section(cwd, shown=None):
    """Return the walk-document's units that hold the item numbers shown, or the open approval-walk's
    waiting items when shown is None, as written, or None when no approval-walk is open; raise
    WaitingItemNotShown when they cannot be read."""
    walk_finder = load_walk_finder()
    top = walk_finder.checkout_top(Path(cwd))
    if top is None or not (top / walk_finder.WALK_DIRECTORY).is_dir():
        return None
    parser = walk_finder.markdown_parser()
    walk = walk_finder.open_walk(top / walk_finder.WALK_DIRECTORY, parser)
    if walk is None:
        return None
    minutes, value, _ = walk
    count = walk_finder.VALUE_COUNT.match(value)
    item = count[0] if count else "the waiting item"
    try:
        numbers, total = walk_finder.parse_items(value)
    except walk_finder.UnusableRange as problem:
        raise WaitingItemNotShown(item, f"its minutes' last `#next_to_present` line, `{value}`, {problem}.")
    if shown is not None:
        numbers, item = shown, "item " + ", ".join(shown)
    document = minutes.with_name(minutes.name[:-len(walk_finder.MINUTES_SUFFIX)] + ".md")
    try:
        _, units = walk_finder.waiting_item_units(document, value, numbers, total, parser)
    except walk_finder.UnusableRange as problem:
        raise WaitingItemNotShown(item, str(problem))
    lines = document.read_text(encoding="utf-8").split("\n")
    return "\n\n".join("\n".join(lines[first:end]).strip("\n")
                        for _, _, _, first, end in sorted(units, key=lambda unit: unit[3]))


def recommendation_text(part):
    """The last recommendation in the lines, as written, without emphasis or one trailing period; or None."""
    found = [match[1].strip(" *_") for match in RECOMMENDATION.finditer("\n".join(part))]
    found = [text[:-1].rstrip(" *_") if text.endswith(".") else text for text in found]
    return found[-1] if found and found[-1] else None


def recommendations_in(lines, spans, total, walk_finder):
    """Return {item number: recommendation text or None} for every item of the walk-document."""
    found = {}
    for numbers, unit_total, _, first, end in spans:
        if total is not None and unit_total != total:
            continue
        for number in numbers:
            part = lines[first:end]
            if len(numbers) > 1:
                own_first, own_end = walk_finder.approval_walk_item_line_range_within_heading_shared_by_several_items(
                    part, number, numbers, unit_total)
                part = part[own_first:own_end]
            found[number] = recommendation_text(part)
    return found


def item_name(number, walk):
    return f"item {number} of {walk.total}" if walk and walk.total else f"item {number}"


def recommendation_unknown_lines(answer_letter, numbers, walk):
    """A line for each item an A, AO, Aa or D answer reaches whose recommendation the hook could not read."""
    if answer_letter not in CHANGE_MAKING_ANSWERS or walk is None:
        return []
    name = CODE_NAMES.get(answer_letter, answer_letter)
    if walk.problem:
        return [RECOMMENDATION_UNKNOWN_LINE.format(item=walk.item, problem=walk.problem, answer_letter=name)]
    return [RECOMMENDATION_UNKNOWN_LINE.format(item=item_name(number, walk), problem=NO_RECOMMENDATION_PROBLEM,
                                               answer_letter=name)
            for number in numbers if walk.recommendations.get(number) is None]


def meaning_lines(answer, walk, in_walk):
    """The answer's lines for an open approval-walk (in_walk) or for none."""
    branch = 0 if in_walk else 1
    walk = walk if in_walk else None
    item = walk.item if walk else "the waiting item"
    numbers = walk.numbers if walk else []
    values = {"item": item, "answer": answer["answer"], "checkout": CHECKOUT, "program": CHECK_PROGRAM.name,
              "explain_skill": EXPLAIN_SKILL, "aa_skill_text": AA_SKILL_TEXT}
    form = answer["form"]
    if form == "numbered":
        not_waiting = [number for number, letter in answer["pairs"]
                       if in_walk and numbers and letter != "R" and number not in numbers]
        if not_waiting:
            return [line.format(not_waiting=", ".join(item_name(number, walk) for number in not_waiting),
                                verb="are" if not_waiting[1:] else "is", item=item)
                    for line in NUMBERED_NOT_WAITING_LINES]
        pairs = ", ".join(f"{item_name(number, walk) if in_walk else number}: {letter}"
                          for number, letter in answer["pairs"])
        lines = [line.format(pairs=pairs) for line in NUMBERED_LINES[branch]]
        if in_walk:
            named = {number for number, _ in answer["pairs"]}
            unnamed = [number for number in numbers if number not in named]
            lines.append(NUMBERED_UNNAMED_LINE.format(unnamed=", ".join(item_name(n, walk) for n in unnamed))
                         if unnamed else NUMBERED_ALL_NAMED_LINE)
            for number, letter in answer["pairs"]:
                lines += recommendation_unknown_lines(letter, [number], walk)
            repeated = [number for number, letter in answer["pairs"] if letter == "R"]
            of_total = f" of {walk.total}" if walk.total else ""
            lines += [NUMBERED_R_LINES[0].format(answer=f"{number} R", number=number, of_total=of_total)
                      for number in repeated]
            answered = {number for number, letter in answer["pairs"] if letter != "R"}
            still_waiting = [number for number in numbers if number not in answered]
            if repeated and still_waiting:
                lines.append(NUMBERED_R_LINES[1].format(item=", ".join(item_name(n, walk) for n in still_waiting)))
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
    lines = [line.format(**values) for line in MEANINGS[code][branch]]
    return lines + recommendation_unknown_lines(code, numbers, walk)


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
    note = []
    shown = None
    if answer["form"] == "numbered" and all(letter == "R" for _, letter in answer["pairs"]):
        shown = [number for number, _ in answer["pairs"]]
    if shown is not None or (answer["form"] == "single" and answer["code"] == "R"):
        try:
            section = item_section(payload.get("cwd") or os.getcwd(), shown)
        except WaitingItemNotShown as not_shown:
            note = [line.format(item=not_shown.args[0], problem=not_shown.args[1]) for line in REPEAT_NOT_SHOWN_LINES]
        except Exception as error:
            note = [line.format(item="the waiting item", problem=f"reading the walk files failed: {error!r}.")
                    for line in REPEAT_NOT_SHOWN_LINES]
        else:
            if section is not None:
                return {"decision": "block", "reason": section}
    context = context_for(answer, walk, walk_error, note)
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": context}}


def named_item_missing(answer, walk, walk_error):
    """Whether a numbered answer gives R, or a word with a list of numbers, to a number no item of the
    open approval-walk has, or no approval-walk is open; False when the walk, its `#next_to_present` line
    or its walk-document cannot be read, so that the context says why."""
    numbers = [number for number, letter in answer.get("pairs", [])
               if letter == "R" or answer.get("every number names an item")]
    if not numbers or walk_error is not None or (walk is not None and walk.problem):
        return False
    return walk is None or any(number not in walk.recommendations for number in numbers)


def context_for(answer, walk, walk_error, note=()):
    """Return the additionalContext text for the answer, given the open approval-walk as read_walk read it, or
    the error reading it raised, with the note's lines after its opening line."""
    prefix = list(note)
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
    return "\n".join(lines + [ONE_QUESTION_LINE])


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
