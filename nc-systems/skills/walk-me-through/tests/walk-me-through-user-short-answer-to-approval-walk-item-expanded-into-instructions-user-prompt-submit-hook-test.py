#!/usr/bin/env python3
"""Cases for the UserPromptSubmit hook that expands a short answer, such as
A, `approved`, `37.4 r` or `1 a 2 d`, into context naming what the answer
means and the approval-walk item it answers.

Each case runs the hook as a subprocess, its real stdin-to-stdout path, in a
scratch checkout this suite made. The exit code is asserted on every case.
"""

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Before anything runs git: a GIT_DIR or similar variable inherited from the
# caller would otherwise send this suite's `git init` into another repository.
_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().parents[4] / "scripts"
    / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

HOOK_SCRIPT = (Path(__file__).resolve().parents[1]
               / "walk-me-through-user-short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook.py")
SUITE_ROOT = Path(tempfile.mkdtemp(prefix="short-answer-expansion-hook-test-")).resolve()
WALK_NAME = "reboot-test-older-open-items-2026-10-15"
CHECKOUT = HOOK_SCRIPT.parents[3]
CHECK = f"python3 {CHECKOUT}/nc-systems/skills/walk-me-through/walk-me-through-answer-added-texts-cold-read-fast-read-check-and-close.py check"
ONE_QUESTION_LINE = ("If your last message to the user left more than one question open, ask him which "
                     "one this answer is for, naming each, and act on none of them until he says.")
failures = []

WALK_DOCUMENT = """# A walk

## Item 3 of 9: the opening sentence

The opening sentence changes.

## Item 4 of 9: a filter

A filter would hide old rows. The strongest case against: old rows confuse readers.

**Recommendation: leave the filter out.**

## Items 5 and 6 of 9: two small corrections

Item 5 of 9 fixes a path. Recommendation: fix the path.

Item 6 of 9 drops a sentence; the sentence may still be needed. Recommendation: Y.
"""

# The line after the opening, outside an approval-walk, for each single answer.
NO_WALK_MEANINGS = {
    "A": "A means approve: the user agrees with your last recommendation or proposal. Do what it says.",
    "AO": "AO means approve as obvious: the user agrees with your last recommendation or proposal, and finds it obvious.",
    "Aa": "Aa means approve after an advisor check: the user agrees with your last recommendation or proposal, "
          "once the advisor has checked it.",
    "D": "D means disapprove: the user disagrees with your last recommendation or proposal. Do not act on it.",
    "Z": "Z means defer: postpone your last question or proposal and record it as a task.",
    "defer": "Z means defer: postpone your last question or proposal and record it as a task.",
    "later": "Z means defer: postpone your last question or proposal and record it as a task.",
    "R": "R asks to see your last question or proposal again: show it in full",
    "E": "E means explain: run the explain skill, ",
    "approved": "Approved means approve: the user agrees with your last recommendation or proposal.",
    "approve": "Approve means approve: the user agrees with your last recommendation or proposal.",
    "approve as obvious": "AO means approve as obvious: the user agrees with your last recommendation",
    "disapproved": "Disapproved means disapprove: the user disagrees with your last recommendation or proposal.",
    "disapprove": "Disapprove means disapprove: the user disagrees with your last recommendation or proposal.",
    "repeat": "Repeat asks to see your last question or proposal again: show it in full",
}


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


class Case:
    """One case's own checkout and walk files."""

    counter = 0

    def __init__(self, next_to_present=None, document=WALK_DOCUMENT):
        Case.counter += 1
        self.checkout = SUITE_ROOT / f"case-{Case.counter}" / "checkout"
        self.checkout.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.checkout)], check=True)
        self.walk = self.checkout / "docs" / "walk"
        if next_to_present is not None:
            self.walk.mkdir(parents=True)
            self.minutes(f"#next_to_present {next_to_present}")
            if document is not None:
                (self.walk / f"{WALK_NAME}.md").write_text(document)

    def minutes(self, text, name=WALK_NAME):
        path = self.walk / f"{name}-minutes.md"
        path.write_text(f"# Minutes\n\n{text}\n")
        return path

    def run(self, prompt=None, stdin_text=None):
        payload = {"hook_event_name": "UserPromptSubmit", "session_id": "test-session",
                   "cwd": str(self.checkout), "prompt": prompt}
        return subprocess.run(
            [sys.executable, str(HOOK_SCRIPT)],
            input=json.dumps(payload) if stdin_text is None else stdin_text,
            capture_output=True, text=True, cwd=self.checkout)

    def lines(self, prompt):
        """The additionalContext's lines, or None when the hook printed nothing or failed."""
        result = self.run(prompt)
        if result.returncode != 0 or not result.stdout.strip():
            return None
        output = json.loads(result.stdout)
        specific = output.get("hookSpecificOutput", {})
        if (set(output) != {"hookSpecificOutput"} or specific.get("hookEventName") != "UserPromptSubmit"
                or set(specific) != {"hookEventName", "additionalContext"}):
            return None
        return specific["additionalContext"].split("\n")


def unknown_line(item, problem, letter):
    return (f"The hook could not read the recommendation of {item}: {problem}. Read the recommendation in the "
            f"walk-document yourself. If you find it, act on {letter} as usual; if you cannot, ask the user "
            f"what he wants done before acting on {letter}.")


NO_RECOMMENDATION = "no line starting \"Recommendation:\""


def test_each_single_answer_in_either_case_with_or_without_a_period():
    case = Case()
    for answer, meaning in NO_WALK_MEANINGS.items():
        for prompt in (answer, answer.lower(), answer.upper(), answer + ".", f"  {answer.lower()}. \n"):
            lines = case.lines(prompt)
            check(f"{prompt!r} is expanded",
                  lines is not None
                  and lines[0] == f"The user answered \"{prompt.strip().rstrip('.')}\"; no approval-walk is open."
                  and lines[1].startswith(meaning) and lines[-1] == ONE_QUESTION_LINE,
                  f"lines {lines!r}")


def test_retired_letters_o_and_other_prompts_print_nothing():
    case = Case(next_to_present="item 3 of 9")
    for prompt in ("y", "n", "c", "l", "L.", "1 l", "l, later", "Y.", "all o", "1 o2", "o4", "oo", "all y", "1 y 2 n", "5 n, 6 y", "y but quickly",
                   "yes", "a a", "aaa", "A..", "X", "", ".", "a lot of things to do", "I think a",
                   "4", "1a2d", "1 c", "1 ab", "explain", "repeater", "deferred", "aol"):
        result = case.run(prompt)
        check(f"{prompt!r} prints nothing",
              result.returncode == 0 and result.stdout == "" and result.stderr == "", (
                  f"exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}"))


CLOSE_END = "then the close command it prints, and do what close prints; write nothing in the minutes by hand."


def writes_minutes_by_hand(lines):
    return any("write the answer in the minutes" in line for line in lines)


def test_a_on_an_open_walk_names_the_item_its_recommendation_and_the_check_step():
    case = Case(next_to_present="item 4 of 9 (awaiting answer)")
    lines = case.lines("a")
    check("A names the waiting item and its recommendation as written, and sends every A to the check step and close",
          lines == [f"The user answered \"a\" to item 4 of 9 of approval-walk {WALK_NAME}.",
                    "A means approve: the user agrees with the recommendation of item 4 of 9 (leave the filter out). "
                    "Do what the recommendation says.",
                    f"Whether or not that makes a change, first run `{CHECK}`, {CLOSE_END}",
                    ONE_QUESTION_LINE], f"lines {lines!r}")
    lines = case.lines("Approved")
    check("approved is A", lines is not None and lines[1].startswith(
        "Approved means approve: the user agrees with the recommendation of item 4 of 9 (leave the filter out)."),
        f"lines {lines!r}")


def test_ao_runs_the_check_step_with_obvious():
    case = Case(next_to_present="item 4 of 9")
    for prompt in ("ao", "AO.", "approve as obvious", "Approve  as obvious"):
        lines = case.lines(prompt)
        check(f"{prompt!r} is AO and runs the check step with --obvious",
              lines is not None
              and lines[1].startswith("AO means approve as obvious: the user agrees with the recommendation of "
                                      "item 4 of 9 (leave the filter out), and finds the item obvious.")
              and f"Whether or not that makes a change, first run `{CHECK} --obvious`, which marks the answer, "
                  f"{CLOSE_END}" in lines
              and not writes_minutes_by_hand(lines), f"lines {lines!r}")
    lines = Case().lines("ao")
    check("AO with no approval-walk acts as for A",
          lines is not None and lines[1].endswith("so act exactly as for A."), f"lines {lines!r}")


SKILL_FILE = CHECKOUT / ".claude" / "skills" / "walk-me-through" / "SKILL.md"


def test_aa_in_any_mix_of_capitals_runs_the_check_step_with_after_advisor():
    case = Case(next_to_present="item 4 of 9")
    skill_lines = SKILL_FILE.read_text().split("\n")
    for prompt in ("aa", "AA", "aA", "Aa", "Aa."):
        lines = case.lines(prompt)
        check(f"{prompt!r} is Aa: it carries the skill's text for Aa and runs the check step with --after-advisor",
              lines is not None
              and lines[1].startswith("Aa means approve after an advisor check: the user agrees with the "
                                      "recommendation of item 4 of 9 (leave the filter out), once the advisor "
                                      "has checked it.")
              and lines[2].startswith("**Aa** approves after an advisor check.") and lines[2] in skill_lines
              and f"If the advisor's check leaves the approval standing, then whether or not it makes a change, "
                  f"first run `{CHECK} --after-advisor`, which marks the answer, {CLOSE_END}" in lines
              and not writes_minutes_by_hand(lines), f"lines {lines!r}")
    lines = Case().lines("aA")
    check("Aa with no approval-walk asks the advisor first, then acts as for A",
          lines is not None and lines[1].startswith("Aa means approve after an advisor check")
          and any("the six questions listed in the walk-me-through skill's section \"Advisor\"" in line
                  for line in lines)
          and lines[-2] == "Otherwise act exactly as for A.", f"lines {lines!r}")
    for prompt, meaning in (("a", "A means approve:"), ("AO", "AO means approve as obvious:")):
        lines = case.lines(prompt)
        check(f"{prompt!r} still means what it meant before Aa", lines is not None and lines[1].startswith(meaning),
              f"lines {lines!r}")


def test_d_does_the_alternative_after_the_check_step():
    case = Case(next_to_present="item 4 of 9")
    for prompt in ("d", "disapproved", "Disapprove"):
        lines = case.lines(prompt)
        word = prompt[:1].upper() + prompt[1:].lower()
        check(f"{prompt!r} disapproves and does the alternative after check --disapproved and close",
              lines is not None
              and lines[1] == (f"{word} means disapprove: the user disagrees with the recommendation of item 4 of 9 "
                               "(leave the filter out).")
              and lines[2] == ("If the item gives no single alternative, ask the user what he wants done instead, "
                               "and act on nothing yet.")
              and lines[3] == (f"Otherwise do the item's alternative; whether or not it makes a change, first run "
                               f"`{CHECK} --disapproved`, {CLOSE_END}"), f"lines {lines!r}")


def test_o_asks_for_option_2_and_option_3_paragraphs():
    case = Case(next_to_present="item 4 of 9")
    for prompt in ("o", "O."):
        lines = case.lines(prompt)
        check(f"{prompt!r} asks for two other options, written into the walk-document, without answering the item",
              lines is not None
              and lines[1] == ("O asks for other options: the user is not answering item 4 of 9 yet, and wants to "
                               "see it again with two other options beside your recommendation.")
              and any("\"Option 2:\", a simpler option, one that does the job with more code and less prompt "
                      "text and AI judgement" in line and "\"Option 3:\", a more creative option" in line
                      for line in lines)
              and any("how it differs from your recommendation, and its pluses and minuses" in line for line in lines)
              and ("Replace the item's answer line in the walk-document with this one: \"Answer O2 or O3 to take "
                   "that option; A still takes the recommendation, and the other answers work as before.\"") in lines
              and lines[-2] == "Then show the item again in full, word for word as the walk-document has it."
              and not any(line.startswith("The hook could not read") for line in lines), f"lines {lines!r}")
    lines = Case().lines("o")
    check("O with no approval-walk asks for the two options in the reply",
          lines is not None and lines[1].startswith("O asks for other options: the user is not answering your last")
          and lines[-2] == "End with this line: \"Answer O2 or O3 to take that option; A still takes the recommendation.\"",
          f"lines {lines!r}")


def test_o_with_a_condition_or_more_text():
    case = Case(next_to_present="item 4 of 9")
    for prompt, first in (("o if any are cheap", "The user set a condition on the answer: \"if any are cheap\"."),
                          ("O, only simple ones", "The user added to the answer: \"only simple ones\".")):
        lines = case.lines(prompt)
        check(f"{prompt!r} is O with its condition or added text",
              lines is not None and lines[1] == first
              and any(line.startswith("O asks for other options") for line in lines), f"lines {lines!r}")


def test_o2_and_o3_approve_an_option_through_the_check_step():
    case = Case(next_to_present="item 4 of 9")
    for prompt, option in (("o2", "2"), ("O3.", "3")):
        lines = case.lines(prompt)
        check(f"{prompt!r} approves option {option}, not the recommendation, through check --option {option}",
              lines is not None
              and lines[1] == (f"O{option} means the user approves option {option} of item 4 of 9: the paragraph "
                               f"\"Option {option}:\" in the walk-document, not your recommendation. Do what that "
                               "option says.")
              and f"If the item has no \"Option {option}:\" paragraph, ask the user what he means, and act on nothing yet." in lines
              and f"Whether or not the option makes a change, first run `{CHECK} --option {option}`, {CLOSE_END}" in lines
              and not writes_minutes_by_hand(lines),
              f"lines {lines!r}")
    lines = Case().lines("O2")
    check("O2 with no approval-walk approves option 2 of the last message, with a fast read first",
          lines is not None and lines[1].startswith("O2 means the user approves option 2 of your last message")
          and any("cold-read-fast-read.py --target <that file>" in line for line in lines), f"lines {lines!r}")
    lines = case.lines("o2 but keep it short")
    check("O2 with more text after it is a rider on O2",
          lines is not None and lines[1] == "The user added to the answer: \"but keep it short\"."
          and any(line.startswith("O2 means the user approves option 2") for line in lines), f"lines {lines!r}")


def test_a_shared_bold_count_with_no_line_per_item_gives_each_item_the_whole_unit():
    document = WALK_DOCUMENT + "\n**Items 8 and 9 of 9: two rows. Recommendation: keep both rows.**\n\nBoth rows stay.\n"
    lines = Case(next_to_present="item 8 of 9", document=document).lines("a")
    check("an item under a shared count with no line of its own reads the recommendation from the unit's first line",
          lines is not None and lines[1].startswith(
              "A means approve: the user agrees with the recommendation of item 8 of 9 (keep both rows)."),
          f"lines {lines!r}")


def test_z_defer_and_later_defer():
    for prompt in ("Z", "defer", "Later."):
        lines = Case(next_to_present="item 4 of 9").lines(prompt)
        check(f"{prompt!r} moves the item as the skill says, then runs check --deferred and close",
              lines is not None and lines[1] == "Z means defer: move item 4 of 9 as the walk-me-through skill's sentence on Z says."
              and lines[2] == "Then run the check step with --deferred, then close, and do what close prints.",
              f"lines {lines!r}")


def test_walk_marker_read_as_the_stop_hook_reads_it():
    case = Case(next_to_present="item 3 of 9")
    case.minutes("#next_to_present: `items 5 and 6 of 9`")
    lines = case.lines("z")
    check("a colon and a code-span value are read as the Stop hook reads them",
          lines is not None
          and lines[0] == f"The user answered \"z\" to items 5 and 6 of 9 of approval-walk {WALK_NAME}.",
          f"lines {lines!r}")


def test_no_open_walk():
    case = Case(next_to_present="item 3 of 9")
    case.minutes("#next_to_present item 3 of 9\n\n#next_to_present none, closed")
    case.minutes("No marker line here.", name="older-walk-2026-09-01")
    lines = case.lines("d")
    check("a closed approval-walk and minutes without a marker are not open",
          lines is not None and lines[0] == "The user answered \"d\"; no approval-walk is open.",
          f"lines {lines!r}")


def test_an_item_without_a_recommendation_line_is_reported_for_a_ao_and_d():
    case = Case(next_to_present="item 3 of 9")
    for letter in ("A", "AO", "Aa", "D"):
        lines = case.lines(letter.lower())
        check(f"{letter} on an item with no recommendation says so and how to go on",
              lines is not None and unknown_line("item 3 of 9", NO_RECOMMENDATION, letter) in lines
              and not any("item 3 of 9 (" in line for line in lines), f"lines {lines!r}")
    for prompt in ("z", "e", "r, then go on"):
        lines = case.lines(prompt)
        check(f"{prompt!r} on an item with no recommendation is not reported",
              lines is not None and not any(line.startswith("The hook could not read") for line in lines),
              f"lines {lines!r}")


def test_an_empty_recommendation_line_is_no_recommendation():
    document = WALK_DOCUMENT + "\n## Item 8 of 9: an unfinished item\n\nRecommendation:\n"
    lines = Case(next_to_present="item 8 of 9", document=document).lines("a")
    check("a `Recommendation:` line with nothing after it is reported as no recommendation",
          lines is not None and unknown_line("item 8 of 9", NO_RECOMMENDATION, "A") in lines
          and not any("item 8 of 9 (" in line for line in lines), f"lines {lines!r}")


def blocked_reason(result):
    """The block's reason when the hook blocked the prompt with exit 0, or None."""
    if result.returncode != 0 or not result.stdout.strip():
        return None
    output = json.loads(result.stdout)
    return output["reason"] if set(output) == {"decision", "reason"} and output["decision"] == "block" else None


ITEM_4_SECTION = """## Item 4 of 9: a filter

A filter would hide old rows. The strongest case against: old rows confuse readers.

**Recommendation: leave the filter out.**"""


def test_r_on_an_open_walk_is_blocked_and_shows_the_waiting_item_as_written():
    case = Case(next_to_present="item 4 of 9")
    before = (case.walk / f"{WALK_NAME}-minutes.md").read_text()
    for prompt in ("r", "R.", "repeat", "Repeat"):
        result = case.run(prompt)
        check(f"{prompt!r} blocks the prompt with the waiting item's section, word for word",
              blocked_reason(result) == ITEM_4_SECTION and result.stderr == "",
              f"exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")
    check("R records nothing in the minutes", (case.walk / f"{WALK_NAME}-minutes.md").read_text() == before)
    reason = blocked_reason(Case(next_to_present="items 5 and 6 of 9").run("r"))
    check("R on items shown together shows their shared heading's whole unit",
          reason is not None and reason.startswith("## Items 5 and 6 of 9: two small corrections")
          and reason.endswith("Recommendation: Y."), repr(reason))
    reason = blocked_reason(Case(next_to_present="items 3 and 4 of 9").run("r"))
    check("R on waiting items under two headings shows both sections, in the walk-document's order",
          reason is not None and reason.startswith("## Item 3 of 9: the opening sentence")
          and reason.endswith(ITEM_4_SECTION), repr(reason))
    case = Case(next_to_present="item 3 of 9")
    case.minutes("#next_to_present item 3 of 9\n\n#next_to_present none, closed")
    lines = case.lines("r")
    check("R with only a closed approval-walk is not blocked and carries no note",
          lines is not None and lines[0] == "The user answered \"r\"; no approval-walk is open."
          and not any(line.startswith("The hook could not show") for line in lines), f"lines {lines!r}")
    lines = Case(next_to_present="item 4 of 9").lines("r but shorter")
    check("R with more text after it is not blocked: it goes to the agent as a rider",
          lines is not None and lines[1] == "The user added to the answer: \"but shorter\".", f"lines {lines!r}")


def test_r_whose_item_cannot_be_read_goes_to_the_agent_with_the_reason():
    shown_by_agent = "R asks to see "
    for case, item, problem in (
            (Case(next_to_present="item 7 of 9"), "item 7 of 9",
             "its walk-document has no heading `Item 7 of 9`, which the minutes name."),
            (Case(next_to_present="item 4 of 9", document=None), "item 4 of 9", "its walk-document "),
            (Case(next_to_present="paused until rewritten"), "the waiting item",
             "its minutes' last `#next_to_present` line, `paused until rewritten`, does not open with an item")):
        result = case.run("r")
        lines = case.lines("r")
        check(f"R whose waiting item cannot be read ({problem[:40]}...) is not blocked, and says why",
              blocked_reason(result) is None and lines is not None
              and lines[1].startswith(f"The hook could not show {item} to the user itself: {problem}")
              and lines[2] == "Show it to him as the lines for R below say; if you cannot find it either, tell him what the line above says, and ask him how to go on."
              and any(line.startswith(shown_by_agent) for line in lines), f"lines {lines!r}")
    case = Case(next_to_present="item 4 of 9")
    (case.walk / f"{WALK_NAME}-minutes.md").write_bytes(b"#next_to_present item 4 of 9 \xff\xfe\n")
    lines = case.lines("r")
    check("R with minutes that cannot be read is not blocked, and names the failure",
          lines is not None
          and "The hook could not show the waiting item to the user itself: reading the walk files failed: "
              "UnicodeDecodeError" in "\n".join(lines)
          and "Show it to him as the lines for R below say; if you cannot find it either, tell him what the line above says, and ask him how to go on." in lines, f"lines {lines!r}")


def test_numbered_answers():
    case = Case(next_to_present="items 5 and 6 of 9")
    lines = case.lines("5 a")
    check("a numbered answer that leaves an item open says so",
          lines is not None
          and lines[1] == "The answer gives each item it names its own letter: item 5 of 9: A."
          and lines[2].startswith("A agrees with the item's recommendation; AO does the same")
          and "The answer does not name item 6 of 9, so it stays open; say so in your reply." in lines,
          f"lines {lines!r}")
    text = " ".join(lines or [])
    check("a numbered answer names each letter's check flag, records one item at a time through close, and "
          "falls back to asking one item at a time",
          all(flag in text for flag in ("AO does the same and marks the approval as obvious, with the flag --obvious",
                                        "alternative, with the flag --disapproved",
                                        "Z defers the item, with the flag --deferred"))
          and ("Record the answers one item at a time, in the order given: for each, run the check step with that "
               "answer's flag, then close, and do what close prints, before the next.") in text
          and ("If check reports more than one item waiting, record nothing, and ask the user to answer those "
               "items one at a time.") in text
          and "makes a change waits for the check step" not in text, f"lines {lines!r}")
    for prompt, letters in (("5 d, 6 ao", ("D", "AO")), ("5d 6ao", ("D", "AO")), ("5 - a 6 - z", ("A", "Z")),
                            ("Item 5 AO; item 6 D", ("AO", "D"))):
        lines = case.lines(prompt)
        check(f"{prompt!r} names both items, each with its letter",
              lines is not None
              and lines[1] == ("The answer gives each item it names its own letter: "
                               f"item 5 of 9: {letters[0]}, item 6 of 9: {letters[1]}.")
              and "The answer names every item now waiting." in lines
              and not any(line.startswith("The hook could not read") for line in lines), f"lines {lines!r}")
    lines = Case(next_to_present="items 3 and 4 of 9").lines("3 a 4 d")
    check("a numbered A on an item with no recommendation is reported for that item only",
          lines is not None and unknown_line("item 3 of 9", NO_RECOMMENDATION, "A") in lines
          and not any("of item 4 of 9" in line for line in lines), f"lines {lines!r}")


ITEM_37_4_SECTION = """## Item 37.4 of 9: R with a number

R with a number shows that item. Recommendation: let the hook expand it."""
ITEM_38_SECTION = """## Item 38 of 9: a second numbered item

Recommendation: show it too."""
NUMBERED_R_DOCUMENT = WALK_DOCUMENT + "\n" + ITEM_37_4_SECTION + "\n\n" + ITEM_38_SECTION + "\n"


def test_numbered_r_alone_is_blocked_and_shows_the_items_it_names_as_written():
    case = Case(next_to_present="item 4 of 9", document=NUMBERED_R_DOCUMENT)
    before = (case.walk / f"{WALK_NAME}-minutes.md").read_text()
    for prompt in ("37.4 r", "37.4 R.", "item 37.4 - r", "37.4r"):
        result = case.run(prompt)
        check(f"{prompt!r} blocks the prompt with item 37.4's section, word for word",
              blocked_reason(result) == ITEM_37_4_SECTION and result.stderr == "",
              f"exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")
    result = case.run("38 r, 37.4 r")
    check("'38 r, 37.4 r' blocks with both sections, in the walk-document's order",
          blocked_reason(result) == ITEM_37_4_SECTION + "\n\n" + ITEM_38_SECTION,
          f"exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")
    check("numbered R records nothing in the minutes", (case.walk / f"{WALK_NAME}-minutes.md").read_text() == before)


ITEM_37_53_SECTION = """## Item 37.53 of 9: an item numbered 37.53

Recommendation: show it."""


def test_repeat_and_an_item_number_is_read_as_that_number_and_r():
    case = Case(next_to_present="item 4 of 9",
                document=NUMBERED_R_DOCUMENT + "\n" + ITEM_37_53_SECTION + "\n")
    for prompt, section in (("repeat 37.4", ITEM_37_4_SECTION), ("Repeat 37.53.", ITEM_37_53_SECTION),
                            ("REPEAT item 37.4", ITEM_37_4_SECTION)):
        result = case.run(prompt)
        check(f"{prompt!r} blocks the prompt with that item's section, not the waiting item's",
              blocked_reason(result) == section and result.stderr == "",
              f"exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")
    result = case.run("repeat 99")
    check("'repeat 99' with no item 99 prints nothing",
          result.returncode == 0 and result.stdout == "" and result.stderr == "",
          f"exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")


def test_an_answer_word_and_an_item_number_is_read_as_that_numbered_answer():
    case = Case(next_to_present="items 5 and 6 of 9")
    for prompt, letter in (("approve 5", "A"), ("Approved item 5.", "A"), ("approve as obvious 5", "AO"),
                           ("disapprove 5", "D"), ("defer 5", "Z"), ("later 5", "Z")):
        lines = case.lines(prompt)
        check(f"{prompt!r} answers item 5 with {letter}, not the waiting items with a rider",
              lines is not None
              and lines[1] == f"The answer gives each item it names its own letter: item 5 of 9: {letter}."
              and "The answer does not name item 6 of 9, so it stays open; say so in your reply." in lines
              and not any(line.startswith("The user added to the answer") for line in lines), f"lines {lines!r}")


def test_an_answer_word_and_a_list_of_item_numbers_answers_each_when_each_names_an_item():
    case = Case(next_to_present="items 5 and 6 of 9")
    for prompt in ("approve 5 and 6", "approve 5, 6", "Approve items 5 and 6."):
        lines = case.lines(prompt)
        check(f"{prompt!r} gives items 5 and 6 each an A",
              lines is not None
              and lines[1] == "The answer gives each item it names its own letter: item 5 of 9: A, item 6 of 9: A."
              and not any(line.startswith("The user added to the answer") for line in lines), f"lines {lines!r}")
    result = case.run("repeat 5 6")
    check("'repeat 5 6' blocks with the unit holding items 5 and 6",
          (blocked_reason(result) or "").startswith("## Items 5 and 6 of 9: two small corrections"),
          f"exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")
    for prompt in ("approve 5 and 99", "repeat 5 99", "approve 5 and 6 then more", "a, 5", "approve item 5 too",
                   "defer, 5 and 6"):
        result = case.run(prompt)
        check(f"{prompt!r} prints nothing, so the prompt reaches the agent as typed",
              result.returncode == 0 and result.stdout == "" and result.stderr == "",
              f"exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")
    lines = case.lines("approve 7")
    check("'approve 7', one number that names no item, still expands as that numbered answer",
          lines is not None and lines[1] == "The answer gives each item it names its own letter: item 7 of 9: A.",
          f"lines {lines!r}")
    for prompt, rest in (("Approve, first line\nsecond line", "first line\nsecond line"),
                         ("a, first line\nsecond line", "first line\nsecond line"),
                         ("REPEAT with context", "with context")):
        lines = case.lines(prompt)
        check(f"{prompt!r} is a rider whose added text is {rest!r}",
              lines is not None and f"The user added to the answer: \"{rest}\"." in "\n".join(lines),
              f"lines {lines!r}")
    lines = case.lines("approve, items are fine")
    check("added text that opens with a word starting with 'item' but no number is still a rider",
          lines is not None and lines[1] == "The user added to the answer: \"items are fine\".", f"lines {lines!r}")


def test_numbered_r_alone_whose_section_cannot_be_read_goes_to_the_agent_with_the_reason():
    case = Case(next_to_present="item 4 of 9", document=NUMBERED_R_DOCUMENT + "\n" + ITEM_37_4_SECTION + "\n")
    lines = case.lines("37.4 r")
    check("'37.4 r' on an item with two headings is not blocked, and says why",
          lines is not None
          and lines[1] == ("The hook could not show item 37.4 to the user itself: its walk-document has more than "
                           "one heading for `Item 37.4 of 9`, so the hook cannot tell which one the minutes name.")
          and "\"37.4 R\" asks to see item 37.4 of 9 again: show it in full, word for word as the "
              "walk-document has it." in lines
          and "Then end your message naming the item waiting for his answer, item 4 of 9." in lines,
          f"lines {lines!r}")


def test_numbered_r_on_a_number_no_item_has_passes_the_prompt_through():
    for case, prompt in ((Case(next_to_present="item 4 of 9"), "37.4 r"),
                         (Case(next_to_present="items 5 and 6 of 9"), "5 a, 7 r"),
                         (Case(), "6 r")):
        result = case.run(prompt)
        check(f"{prompt!r} with no such item prints nothing",
              result.returncode == 0 and result.stdout == "" and result.stderr == "",
              f"exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")


def test_numbered_r_beside_other_numbered_answers():
    lines = Case(next_to_present="items 5 and 6 of 9").lines("5 a, 6 r")
    check("'5 a, 6 r' gives item 5 its A and tells the agent to show item 6",
          lines is not None
          and lines[1] == "The answer gives each item it names its own letter: item 5 of 9: A, item 6 of 9: R."
          and "R shows the item again" in lines[2]
          and "\"6 R\" asks to see item 6 of 9 again: show it in full, word for word as the walk-document has it."
              in lines
          and not any("item 5 of 9 again" in line for line in lines)
          and "Then end your message naming the item waiting for his answer, item 6 of 9." in lines,
          f"lines {lines!r}")
    lines = Case(next_to_present="items 5 and 6 of 9").lines("5 a, 6 d, 3 r")
    check("'5 a, 6 d, 3 r' shows item 3 and names no waiting item, because it answers both",
          lines is not None
          and any(line.startswith("\"3 R\" asks to see item 3 of 9 again") for line in lines)
          and not any(line.startswith("Then end your message naming") for line in lines), f"lines {lines!r}")
    lines = Case(next_to_present="items 5 and 6 of 9").lines("5 z, 6 r")
    check("'5 z, 6 r' tells the agent to show item 6 only",
          lines is not None and not any("\"5 R\"" in line for line in lines)
          and any(line.startswith("\"6 R\" asks to see item 6 of 9 again") for line in lines)
          and "Then end your message naming the item waiting for his answer, item 6 of 9." in lines,
          f"lines {lines!r}")


def test_a_numbered_letter_other_than_r_on_a_number_no_item_has_still_expands():
    case = Case(next_to_present="items 5 and 6 of 9")
    for prompt in ("7 a", "7 z"):
        lines = case.lines(prompt)
        check(f"{prompt!r} still expands", lines is not None
              and lines[1].startswith("The answer gives each item it names its own letter: item 7 of 9:"),
              f"lines {lines!r}")


def test_numbered_r_reads_the_walk_in_the_payloads_cwd_not_the_hooks_own():
    case = Case(next_to_present="item 4 of 9", document=NUMBERED_R_DOCUMENT)
    payload = {"hook_event_name": "UserPromptSubmit", "session_id": "test-session",
               "cwd": str(case.checkout), "prompt": "37.4 r"}
    result = subprocess.run([sys.executable, str(HOOK_SCRIPT)], input=json.dumps(payload),
                            capture_output=True, text=True, cwd=SUITE_ROOT)
    check("'37.4 r' run from outside the checkout still finds item 37.4 in the payload's cwd",
          result.returncode == 0 and blocked_reason(result) == ITEM_37_4_SECTION,
          f"exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")


def test_numbered_r_on_unreadable_minutes_expands_and_says_so():
    case = Case(next_to_present="item 3 of 9")
    (case.walk / f"{WALK_NAME}-minutes.md").write_bytes(b"#next_to_present item 3 of 9 \xff\xfe\n")
    lines = case.lines("6 r")
    check("'6 r' on minutes that cannot be read names the failure and still says to show item 6",
          lines is not None
          and "reading the approval-walk state failed: UnicodeDecodeError" in lines[0]
          and "\"6 R\" asks to see item 6 again: show it in full, word for word as the walk-document has it."
              in lines, f"lines {lines!r}")


def test_all_a_and_all_ao():
    case = Case(next_to_present="items 5 and 6 of 9")
    for prompt in ("all a", "A to all."):
        lines = case.lines(prompt)
        check(f"{prompt!r} approves every waiting item",
              lines is not None
              and lines[1] == (f"\"{prompt.rstrip('.')}\" means A to every item now waiting, items 5 and 6 of 9: the "
                               "user agrees with each one's recommendation. Do what each recommends. For each item, "
                               "whether or not it makes a change, run the check step, then close, and do what close "
                               "prints; write nothing in the minutes by hand."), f"lines {lines!r}")
    for prompt in ("all ao", "ao to all"):
        lines = case.lines(prompt)
        check(f"{prompt!r} approves every waiting item as obvious",
              lines is not None and lines[1].startswith(f"\"{prompt}\" means AO to every item now waiting")
              and lines[1].endswith("For each item, whether or not it makes a change, run the check step (with "
                                    "--obvious for `all ao`), then close, and do what close prints; write nothing in "
                                    "the minutes by hand."), f"lines {lines!r}")
    lines = Case().lines("all a")
    check("all a with no approval-walk acts on each open recommendation",
          lines is not None and lines[1].startswith("\"all a\" means the user agrees with every recommendation"),
          f"lines {lines!r}")
    lines = Case(next_to_present="items 3 and 4 of 9").lines("all a")
    check("all a over an item with no recommendation reports that item",
          lines is not None and unknown_line("item 3 of 9", NO_RECOMMENDATION, "A") in lines, f"lines {lines!r}")


def test_condition_and_rider():
    case = Case(next_to_present="item 4 of 9")
    lines = case.lines("A if the prose has been cold read fast")
    check("a letter with `if` puts the condition first",
          lines is not None
          and lines[1] == "The user set a condition on the answer: \"if the prose has been cold read fast\"."
          and lines[2] == "Meet the condition before you record or act on the answer."
          and any(line.startswith("A means approve: the user agrees with the recommendation of item 4 of 9")
                  for line in lines), f"lines {lines!r}")
    lines = case.lines("ao after a fast read")
    check("AO with `after` is a condition too",
          lines is not None and lines[1] == "The user set a condition on the answer: \"after a fast read\"."
          and any(line.startswith("AO means approve as obvious") for line in lines), f"lines {lines!r}")
    for prompt, rest, meaning in (
            ("A but will need careful instructional wording.", "but will need careful instructional wording.",
             "A means approve"),
            ("d and r", "and r", "D means disapprove"), ("ao, keep the old name", "keep the old name", "AO means"),
            ("aa, keep the old name", "keep the old name", "Aa means approve after an advisor check"),
            ("z - later", "later", "Z means defer"), ("approved next", "next", "Approved means approve"),
            ("approve as obvious, thanks", "thanks", "AO means")):
        lines = case.lines(prompt)
        check(f"{prompt!r} applies the answer, then the rest",
              lines is not None and lines[1] == f"The user added to the answer: \"{rest}\"."
              and lines[2] == "Act on the answer as the lines below say, then act on what he added."
              and any(line.startswith(meaning) for line in lines), f"lines {lines!r}")


def test_e_points_at_the_explain_skill():
    lines = Case(next_to_present="item 3 of 9").lines("e")
    explain = CHECKOUT / ".claude" / "skills" / "explain" / "SKILL.md"
    check("E runs the explain skill on the waiting item",
          lines is not None and lines[1] == f"E means explain: run the explain skill, {explain}, on item 3 of 9."
          and explain.is_file(), f"lines {lines!r}")


def test_named_programs_exist():
    for path in (CHECK.split()[1], f"{CHECKOUT}/nc-systems/cold-read/cold-read-fast-read.py"):
        check(f"the program the hook names, {path}, exists", Path(path).is_file())
    lines = Case().lines("a")
    check("A with no approval-walk names the fast-read program by its path",
          lines is not None and f"run `python3 {CHECKOUT}/nc-systems/cold-read/cold-read-fast-read.py --target "
                                "<that file>`, and apply the findings that hold." in lines[2], f"lines {lines!r}")


def test_each_check_command_the_hook_names_runs_on_the_real_program():
    """The command is run as the hook prints it, plus --counts-log, so no test line reaches the log-store.
    Item 3 has no `#new` line, so no fast read, and no model, is called."""
    for prompt, word in (("a", "approved ("), ("ao", "approved #approved_obvious ("),
                         ("aa", "approved #approved_after_advisor ("),
                         ("o2", "approved option 2 ("), ("o3", "approved option 3 (")):
        case = Case(next_to_present="item 3 of 9")
        lines = case.lines(prompt) or []
        commands = [line.split("`")[1] for line in lines if "`python3 " in line and " check" in line]
        if not commands:
            check(f"the hook names a check command for {prompt!r}", False, f"lines {lines!r}")
            continue
        result = subprocess.run(commands[0].split() + ["--counts-log", str(case.checkout.parent / "counts.tsv")],
                                capture_output=True, text=True, cwd=case.checkout)
        minutes = (case.walk / f"{WALK_NAME}-minutes.md").read_text()
        check(f"the check command the hook names for {prompt!r} runs and records the answer",
              result.returncode == 0 and result.stdout.startswith("no proposed text marked")
              and f"item 3 of 9: the user answered {word}" in minutes,
              f"command {commands[0]!r}, exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")


def test_unreadable_minutes_still_expand_and_say_so():
    case = Case(next_to_present="item 3 of 9")
    (case.walk / f"{WALK_NAME}-minutes.md").write_bytes(b"#next_to_present item 3 of 9 \xff\xfe\n")
    lines = case.lines("d")
    check("minutes that cannot be read still give both branches and name the failure",
          lines is not None
          and lines[0].startswith("The user answered \"d\"; the hook could not tell whether an approval-walk "
                                  "is open, because reading the approval-walk state failed: UnicodeDecodeError")
          and lines[1].startswith("Find out yourself: the last `#next_to_present` line in each of the checkout's")
          and "If an approval-walk is open:" in lines and "If no approval-walk is open:" in lines
          and any(line.startswith("D means disapprove: the user disagrees with your last") for line in lines),
          f"lines {lines!r}")


def test_missing_walk_document_is_reported_for_a():
    case = Case(next_to_present="item 4 of 9", document=None)
    lines = case.lines("a")
    check("a walk-document that is missing is reported before acting on A",
          lines is not None and any(line.startswith("The hook could not read the recommendation of item 4 of 9: "
                                                    "the walk-document ") for line in lines),
          f"lines {lines!r}")


def test_a_marker_value_naming_no_item_is_reported_for_a_and_d():
    lines = Case(next_to_present="paused until rewritten").lines("a")
    check("a `#next_to_present` value with no running count is quoted and reported before acting on A",
          lines is not None
          and lines[0] == (f"The user answered \"a\" to the item its minutes' `#next_to_present` line names, "
                           f"`paused until rewritten`, of approval-walk {WALK_NAME}.")
          and any(line.startswith("The hook could not read the recommendation of ") for line in lines),
          f"lines {lines!r}")
    lines = Case(next_to_present="items 6 to 4 of 9").lines("d")
    check("a backwards range is reported before acting on D",
          lines is not None and any("runs backwards" in line and line.startswith("The hook could not read")
                                    for line in lines), f"lines {lines!r}")


def test_payload_that_is_not_json_is_a_fault():
    result = Case().run(stdin_text="not json")
    check("a payload that is not JSON is reported on stderr with exit 1",
          result.returncode == 1 and result.stdout == ""
          and "short-answer-to-approval-walk-item-expanded-into-instructions-user-prompt-submit-hook: the hook failed" in result.stderr,
          f"exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")


def main():
    try:
        for name, function in sorted(globals().items()):
            if name.startswith("test_") and callable(function):
                function()
    finally:
        shutil.rmtree(SUITE_ROOT, ignore_errors=True)
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
