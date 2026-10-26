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
ONE_ITEM_AT_A_TIME_LINE = (
    "Before each check run, if the minutes' last `#next_to_present` line does not name that item alone, add the "
    "line `#next_to_present item <number> of 9` for it, with its number, as the minutes' last line, because the "
    "walk-me-through skill has that line name one item, or one part such as `item 4.1 of 9`. Present the item "
    "that `close` names only after the last answer is recorded.")
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
                  and lines[1].startswith(meaning) and not any("which one" in line for line in lines),
                  f"lines {lines!r}")


def test_a_hyphen_between_the_letters_of_ao_o2_and_o3_is_read_as_that_letter():
    case = Case(next_to_present="item 4 of 9")
    for prompt, code, meaning in (
            ("A-O.", "AO", "AO means approve as obvious"), ("a-o", "AO", "AO means approve as obvious"),
            ("A - O", "AO", "AO means approve as obvious"), ("O-2", "O2", "O2 means the user approves option 2"),
            ("o - 3.", "O3", "O3 means the user approves option 3")):
        lines = case.lines(prompt)
        check(f"{prompt!r} is {code}",
              lines is not None
              and lines[0] == f"The user answered \"{prompt.rstrip('.')}\" to item 4 of 9 of approval-walk {WALK_NAME}."
              and lines[1].startswith(meaning), f"lines {lines!r}")
    lines = case.lines("A-O, keep the old name")
    check("'A-O, keep the old name' is a rider on AO",
          lines is not None and lines[1] == "The user added to the answer: \"keep the old name\"."
          and any(line.startswith("AO means approve as obvious") for line in lines), f"lines {lines!r}")
    lines = Case(next_to_present="items 5 and 6 of 9").lines("5 a-o, 6 d")
    check("'5 a-o, 6 d' gives item 5 AO",
          lines is not None
          and lines[1] == "The answer gives each item it names its own letter: item 5 of 9: AO, item 6 of 9: D.",
          f"lines {lines!r}")
    for prompt in ("all a-o", "a-o to all"):
        lines = Case(next_to_present="items 5 and 6 of 9").lines(prompt)
        check(f"{prompt!r} is AO to all", lines is not None
              and lines[1].startswith(f"\"{prompt}\" means AO to every item now waiting"), f"lines {lines!r}")
    for prompt in ("a-ok", "A-OK.", "O-ring", "a-one", "a-o-k", "a o", "o-4", "5 a-ok"):
        result = case.run(prompt)
        check(f"the hyphenated word {prompt!r} is not read as an answer",
              result.returncode == 0 and result.stdout == "" and result.stderr == "",
              f"exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")
    lines = case.lines("a - other text")
    check("'a - other text' stays a rider on A", lines is not None
          and lines[1] == "The user added to the answer: \"other text\"."
          and any(line.startswith("A means approve") for line in lines), f"lines {lines!r}")


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
                    f"Whether or not that makes a change, first run `{CHECK}`, {CLOSE_END}"], f"lines {lines!r}")
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
          and lines[-1] == "Otherwise act exactly as for A.", f"lines {lines!r}")
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
              and ("Below the two paragraphs, add this line: \"Answer O2 or O3 to take that option; A still takes "
                   "the recommendation, and the other answers work as before.\"") in lines
              and lines[-1] == ("Then republish the item's page as its new version, and show the item again in full, "
                                "word for word as the walk-document has it.")
              and not any(line.startswith("The hook could not read") for line in lines), f"lines {lines!r}")
    lines = Case().lines("o")
    check("O with no approval-walk asks for the two options in the reply",
          lines is not None and lines[1].startswith("O asks for other options: the user is not answering your last")
          and lines[-1] == "End with this line: \"Answer O2 or O3 to take that option; A still takes the recommendation.\"",
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


def test_lines_inside_code_are_neither_an_items_start_nor_its_recommendation():
    for shape, hidden in (("a ``` fence", "```\nItem 6 of 9: an example\nRecommendation: hidden.\n```"),
                          ("a ~~~ fence", "~~~\nItem 6 of 9: an example\nRecommendation: hidden.\n~~~"),
                          ("an indented code block", "    Item 6 of 9: an example\n    Recommendation: hidden."),
                          ("an HTML comment", "<!-- A drafter's note.\nItem 6 of 9: an example\nRecommendation: hidden.\n-->")):
        # The hidden recommendation comes last, since the last recommendation of an item is the one read.
        document = WALK_DOCUMENT.replace(
            "Item 5 of 9 fixes a path. Recommendation: fix the path.\n",
            f"Item 5 of 9 fixes a path.\n\nRecommendation: fix the path.\n\n{hidden}\n")
        lines = Case(next_to_present="item 5 of 9", document=document).lines("a")
        check(f"inside {shape}, a line opening with another item's count does not end the waiting item, and "
              "a recommendation line is not read",
              lines is not None and lines[1].startswith(
                  "A means approve: the user agrees with the recommendation of item 5 of 9 (fix the path)."),
              f"lines {lines!r}")


def test_a_quoted_count_is_not_an_items_start_for_the_recommendation():
    document = WALK_DOCUMENT.replace(
        "Item 5 of 9 fixes a path. Recommendation: fix the path.\n",
        "Item 5 of 9 fixes a path.\n\n> Item 6 of 9: the user's earlier wording\n\nRecommendation: fix the path.\n")
    lines = Case(next_to_present="item 5 of 9", document=document).lines("a")
    check("a quoted line opening with another item's count does not end the waiting item",
          lines is not None and lines[1].startswith(
              "A means approve: the user agrees with the recommendation of item 5 of 9 (fix the path)."),
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


def not_blocked(result):
    """Whether the hook exited 0 with output that holds no "decision" key, so it did not block the prompt."""
    return (result.returncode == 0 and bool(result.stdout.strip())
            and "decision" not in json.loads(result.stdout) and result.stderr == "")


def r_line(word, item):
    return (f"{word} asks to see {item} again: show it in full, heading included, word for word as the "
            "walk-document has it, and wait for his answer.")


def numbered_r_line(number, item):
    return (f"\"{number} R\" asks to see {item} again: show it in full, heading included, word for word as the "
            "walk-document has it.")


def test_r_on_an_open_walk_goes_to_the_agent_and_does_not_block():
    case = Case(next_to_present="item 4 of 9")
    before = (case.walk / f"{WALK_NAME}-minutes.md").read_text()
    for prompt, word in (("r", "R"), ("R.", "R"), ("repeat", "Repeat"), ("Repeat", "Repeat")):
        result = case.run(prompt)
        lines = case.lines(prompt)
        check(f"{prompt!r} gives the agent additionalContext telling it to show the waiting item, and no decision",
              not_blocked(result) and lines is not None
              and lines[0] == f"The user answered \"{prompt.rstrip('.')}\" to item 4 of 9 of approval-walk {WALK_NAME}."
              and lines[1:] == [r_line(word, "item 4 of 9")]
              and not any("leave the filter out" in line or "old rows" in line for line in lines),
              f"exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")
    check("R records nothing in the minutes", (case.walk / f"{WALK_NAME}-minutes.md").read_text() == before)
    lines = Case(next_to_present="items 5 and 6 of 9").lines("r")
    check("R on items shown together tells the agent to show them all",
          lines is not None and lines[1] == r_line("R", "items 5 and 6 of 9"), f"lines {lines!r}")
    case = Case(next_to_present="item 3 of 9")
    case.minutes("#next_to_present item 3 of 9\n\n#next_to_present none, closed")
    lines = case.lines("r")
    check("R with only a closed approval-walk asks for the last question again",
          lines is not None and lines[0] == "The user answered \"r\"; no approval-walk is open."
          and lines[1].startswith(NO_WALK_MEANINGS["R"]), f"lines {lines!r}")
    lines = Case(next_to_present="item 4 of 9").lines("r but shorter")
    check("R with more text after it goes to the agent as a rider",
          lines is not None and lines[1] == "The user added to the answer: \"but shorter\".", f"lines {lines!r}")


PAGE_1 = "https://claude.ai/artifact/PageOfItem4Old"
PAGE_2 = "https://claude.ai/artifact/PageOfItem4New"
LETTERS_AFTER_LINK = ("A approve · AO approve as obvious · Aa approve after an advisor check · D disapprove · "
                      "Z defer · E explain · O other options")


def page_line(answer, item, closing_line):
    return (f"\"{answer}\" asks to see {item} again. Its page shows it in full, so reply with only this closing "
            f"line, word for word, and wait for his answer: {closing_line}")


def test_r_hands_the_agent_the_closing_line_of_the_items_newest_page():
    case = Case(next_to_present="item 4 of 9")
    minutes = case.minutes(f"#item_page item 4 of 9 {PAGE_1}\n\n#item_page item 3 of 9 https://claude.ai/artifact/Three"
                           f"\n\n#item_page item 4 of 9 {PAGE_2}\n\n#next_to_present item 4 of 9")
    before = minutes.read_text()
    closing = f"[Item 4 of 9, a filter]({PAGE_2}) · {LETTERS_AFTER_LINK}"
    for prompt in ("r", "repeat"):
        result = case.run(prompt)
        lines = case.lines(prompt)
        check(f"{prompt!r} with a recorded page hands the agent the newest page's closing line, and no decision",
              not_blocked(result) and lines is not None
              and lines[1] == page_line(prompt[:1].upper() + prompt[1:], "item 4 of 9", closing)
              and not any(PAGE_1 in line for line in lines), f"lines {lines!r}")
    check("R with a page records nothing in the minutes", minutes.read_text() == before)
    lines = case.lines("3 r")
    check("a numbered R hands the agent the closing line of the item it names",
          lines is not None and page_line("3 R", "item 3 of 9",
                                          f"[Item 3 of 9, the opening sentence](https://claude.ai/artifact/Three) · "
                                          f"{LETTERS_AFTER_LINK}") in lines, f"lines {lines!r}")


def test_r_on_an_item_with_no_page_tells_the_agent_to_show_it_in_full():
    case = Case(next_to_present="item 4 of 9")
    case.minutes(f"#item_page item 3 of 9 {PAGE_1}\n\n#next_to_present item 4 of 9")
    lines = case.lines("r")
    check("R on an item the minutes record no page for tells the agent to show the item in full",
          lines is not None and lines[1] == r_line("R", "item 4 of 9"), f"lines {lines!r}")
    lines = case.lines("4 r")
    check("a numbered R on an item with no page tells the agent to show it in full",
          lines is not None and numbered_r_line(4, "item 4 of 9") in lines, f"lines {lines!r}")


def test_the_closing_line_letters_are_the_walk_skills():
    check("SKILL.md writes the closing line with the letters the hook hands the agent",
          f"](<page link>) · {LETTERS_AFTER_LINK}" in SKILL_FILE.read_text())


def test_r_whose_item_cannot_be_read_still_goes_to_the_agent():
    for case, item in ((Case(next_to_present="item 7 of 9"), "item 7 of 9"),
                       (Case(next_to_present="item 4 of 9", document=None), "item 4 of 9")):
        result = case.run("r")
        lines = case.lines("r")
        check(f"R on {item}, whose walk-document holds no such item or does not exist, tells the agent to show it",
              not_blocked(result) and lines is not None and lines[1] == r_line("R", item), f"lines {lines!r}")


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
    check("a numbered answer names each letter's check flag, records one item at a time through close, sets "
          "the `#next_to_present` line to each item before its check, and stops at a refusal",
          all(flag in text for flag in ("AO does the same and marks the approval as obvious, with the flag --obvious",
                                        "alternative, with the flag --disapproved",
                                        "Z defers the item, with the flag --deferred"))
          and ("Record the answers one item at a time, in the order given: for each, run the check step with that "
               "answer's flag, then close, and do what close prints, before the next.") in text
          and ONE_ITEM_AT_A_TIME_LINE in text
          and ("If check or close refuses or fails, stop there and record none of the remaining answers: tell the "
               "user which answers were recorded and what was printed, and ask him how to go on.") in text
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


def test_numbered_r_alone_tells_the_agent_to_show_the_items_it_names_and_records_nothing():
    case = Case(next_to_present="item 4 of 9", document=NUMBERED_R_DOCUMENT)
    before = (case.walk / f"{WALK_NAME}-minutes.md").read_text()
    for prompt in ("37.4 r", "37.4 R.", "item 37.4 - r", "37.4r"):
        result = case.run(prompt)
        lines = case.lines(prompt)
        check(f"{prompt!r} tells the agent to show item 37.4, then name the waiting item, and nothing else",
              not_blocked(result) and lines is not None
              and lines[1:] == [numbered_r_line("37.4", "item 37.4 of 9"),
                                "Then end your message naming the item waiting for his answer, item 4 of 9."],
              f"lines {lines!r}")
    lines = case.lines("38 r, 37.4 r")
    check("'38 r, 37.4 r' tells the agent to show both items, and gives no line for recording an answer",
          lines is not None
          and lines[1:3] == [numbered_r_line("38", "item 38 of 9"), numbered_r_line("37.4", "item 37.4 of 9")]
          and not any("check step" in line or "`#next_to_present`" in line for line in lines), f"lines {lines!r}")
    check("numbered R records nothing in the minutes", (case.walk / f"{WALK_NAME}-minutes.md").read_text() == before)


ITEM_37_53_SECTION = """## Item 37.53 of 9: an item numbered 37.53

Recommendation: show it."""


def test_repeat_and_an_item_number_is_read_as_that_number_and_r():
    case = Case(next_to_present="item 4 of 9",
                document=NUMBERED_R_DOCUMENT + "\n" + ITEM_37_53_SECTION + "\n")
    for prompt, number in (("repeat 37.4", "37.4"), ("Repeat 37.53.", "37.53"), ("REPEAT item 37.4", "37.4")):
        lines = case.lines(prompt)
        check(f"{prompt!r} tells the agent to show that item, not the waiting item",
              lines is not None and lines[1] == numbered_r_line(number, f"item {number} of 9"), f"lines {lines!r}")
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
    lines = case.lines("repeat 5 6")
    check("'repeat 5 6' tells the agent to show items 5 and 6",
          lines is not None and lines[1:3] == [numbered_r_line("5", "item 5 of 9"), numbered_r_line("6", "item 6 of 9")],
          f"lines {lines!r}")
    for prompt in ("approve 5 and 99", "repeat 5 99", "approve 5 and 6 then more", "a, 5", "approve item 5 too",
                   "defer, 5 and 6"):
        result = case.run(prompt)
        check(f"{prompt!r} prints nothing, so the prompt reaches the agent as typed",
              result.returncode == 0 and result.stdout == "" and result.stderr == "",
              f"exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")
    lines = case.lines("approve 7")
    check("'approve 7', one number that names an item not waiting, is refused",
          lines is not None and lines[1].startswith("The answer gives a letter to item 7 of 9, which is not waiting"),
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
          and numbered_r_line("6", "item 6 of 9") in lines
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


NOT_WAITING_LINES = [
    "Record nothing and act on none of the answer: each check run records one answer against the item the "
    "`#next_to_present` line names, and close then moves that line on to the next item, so a letter for "
    "another item, or a second letter for the same item, would be recorded against an item the user did not "
    "answer.",
    "Ask the user to answer item 5 of 9 with one letter; the other items come to him one at a time after it."]


def test_a_numbered_letter_other_than_r_for_an_item_not_waiting_is_refused():
    case = Case(next_to_present="item 5 of 9")
    for prompt, named in (("5 a, 7 d", "item 7 of 9, which is"), ("7 a", "item 7 of 9, which is"),
                          ("5 a 6 z 7 ao", "item 6 of 9, item 7 of 9, which are"), ("approve 5 and 6", "item 6 of 9, which is")):
        lines = case.lines(prompt)
        check(f"{prompt!r} with only item 5 waiting is refused whole, naming {named.split(', which')[0]}",
              lines is not None
              and lines[1] == (f"The answer gives a letter to {named} not waiting for an answer, and the minutes' "
                               "`#next_to_present` line names only item 5 of 9.")
              and lines[2:4] == NOT_WAITING_LINES and not any("`python3" in line for line in lines),
              f"lines {lines!r}")
    for prompt, problems in (
            ("5 a, 5 a", "gives item 5 of 9 more than one letter"),
            ("5 a 5 d", "gives item 5 of 9 more than one letter"),
            ("5 a, 7 d, 5 z", "gives a letter to item 7 of 9, which is not waiting for an answer and gives item 5 "
                              "of 9 more than one letter")):
        lines = case.lines(prompt)
        check(f"{prompt!r} with only item 5 waiting is refused whole, saying {problems!r}",
              lines is not None
              and lines[1] == (f"The answer {problems}, and the minutes' `#next_to_present` line names only "
                               "item 5 of 9.")
              and lines[2:4] == NOT_WAITING_LINES and not any("`python3" in line for line in lines),
              f"lines {lines!r}")
    lines = case.lines("5 a, 5 r")
    check("an R beside a letter for the same waiting item is not a second letter",
          lines is not None and lines[1] == "The answer gives each item it names its own letter: item 5 of 9: A, "
          "item 5 of 9: R.", f"lines {lines!r}")
    lines = case.lines("5 a, 6 r")
    check("an R for an item not waiting does not refuse the answer for the waiting item",
          lines is not None and lines[1] == "The answer gives each item it names its own letter: item 5 of 9: A, "
          "item 6 of 9: R.", f"lines {lines!r}")
    lines = Case(next_to_present="items 5 and 6 of 9").lines("5 a, 6 d")
    check("letters for every waiting item are not refused",
          lines is not None and lines[1].startswith("The answer gives each item it names its own letter:"),
          f"lines {lines!r}")


PARTS_DOCUMENT = """# A walk with parts

## Item 4 of 9: three wording fixes in one file

The fix changes three phrases in `docs/example.md`.

1. "item close names" becomes "item that `close` names".
2. "a walk" becomes "an approval-walk".
3. "fast read" becomes "cold-read-fast-read".

Recommendation: make all three changes.

## Item 7 of 9: labelled parts

**Part 1:** drop a word.

### Part 2

Drop another.

Recommendation: drop both.

## Item 8 of 9: no parts

A plain item. Recommendation: keep it.
"""
def parts_different_letters_lines(flags):
    return [
        "Each part's letter does for that part what it does for a whole item: A approves the part's recommendation, "
        "so do what it says; AO does the same and marks the approval as obvious; D disapproves it, so do the "
        "part's alternative.",
        "If a part answered D gives no single alternative, ask the user what he wants done instead, and act on "
        "nothing yet.",
        f"Otherwise, whether or not the parts make a change, first run `{CHECK} {flags}`, which records each part's "
        "answer, then the close command it prints, and do what close prints; write nothing in the minutes by hand."]


def parts_deferred_beside_answered_lines(item="item 4 of 9"):
    return [
        "The check step cannot record this answer: `walk-me-through-answer-added-texts-cold-read-fast-read-check-and-"
        "close.py check --part-answer` takes A, AO or D for a part, because the walk-me-through skill does not say where an "
        "item goes in the walk when one of its parts is deferred and the others are answered.",
        "Record nothing and act on none of the parts.",
        "Tell the user that the walk-me-through check program cannot record a deferred part beside answered ones, "
        f"and ask him to answer every part of {item} with A, AO or D, to answer Z to the whole item, or to say how "
        "else to go on."]


def parts_unanswered_lines(missing, item="item 4 of 9"):
    return [
        f"The answer does not name {missing}, and the walk-me-through skill keeps an item open while a part is "
        f"unanswered, so record nothing in the minutes and act on none of the parts of {item}.",
        f"Ask the user to answer every part of {item} in one reply, the parts he has answered included, "
        "giving each part's number with its letter, as in `1 a 2 d`, because this hook reads each reply on its "
        "own, so a reply that names only the parts still missing would leave the others unanswered."]


def parts_read_line(pairs, item="item 4 of 9", last="3"):
    return (f"The numbers are the part numbers of {item}, which holds parts 1 to {last} of one fix, as the "
            f"walk-me-through skill lets an item do; the answer gives each part it names its own letter: {pairs}.")


def test_a_numbered_answer_within_the_waiting_items_parts_answers_the_parts():
    case = Case(next_to_present="item 4 of 9", document=PARTS_DOCUMENT)
    for prompt, pairs, flags in (
            ("1 a 2 d 3 a", "part 1: A, part 2: D, part 3: A", "--part-answer 1=A --part-answer 2=D --part-answer 3=A"),
            ("3 a, 1 ao, 2 a", "part 3: A, part 1: AO, part 2: A", "--part-answer 1=AO --part-answer 2=A --part-answer 3=A")):
        lines = case.lines(prompt)
        check(f"{prompt!r} on an item with parts 1 to 3 names each part's letter and gives the check command "
              "with one --part-answer flag per part, in part number order",
              lines is not None
              and lines[0] == f"The user answered \"{prompt}\" to item 4 of 9 of approval-walk {WALK_NAME}."
              and lines[1:] == [parts_read_line(pairs)] + parts_different_letters_lines(flags), f"lines {lines!r}")
    lines = case.lines("1 a 2 d")
    check("'1 a 2 d' on an item with parts 1 to 3 leaves part 3 unanswered, so nothing is recorded, though the "
          "letters differ",
          lines is not None and lines[1:] == [parts_read_line("part 1: A, part 2: D")]
          + parts_unanswered_lines("part 3"), f"lines {lines!r}")
    for prompt, pairs in (("1 a 2 z 3 a", "part 1: A, part 2: Z, part 3: A"),
                          ("1 z 2 z 3 d", "part 1: Z, part 2: Z, part 3: D")):
        lines = case.lines(prompt)
        check(f"{prompt!r} defers a part beside answered ones, which check cannot record, so nothing is recorded",
              lines is not None and lines[1:] == [parts_read_line(pairs)] + parts_deferred_beside_answered_lines(),
              f"lines {lines!r}")
    lines = case.lines("1 a 2 d 3 a 2 r")
    check("R on a part beside different letters for every part shows the item again and still gives the command",
          lines is not None and lines[1:] == [
              parts_read_line("part 1: A, part 2: D, part 3: A, part 2: R"),
              "R on a part asks to see item 4 of 9 again: show it in full, heading included, word for word as the "
              "walk-document has it."] + parts_different_letters_lines("--part-answer 1=A --part-answer 2=D --part-answer 3=A"),
          f"lines {lines!r}")
    lines = case.lines("1 a 2 a")
    check("'1 a 2 a' leaves part 3 unanswered, so the item stays open and nothing is recorded",
          lines is not None and lines[1:] == [
              parts_read_line("part 1: A, part 2: A"),
              "The answer does not name part 3, and the walk-me-through skill keeps an item open while a part is "
              "unanswered, so record nothing in the minutes and act on none of the parts of item 4 of 9.",
              "Ask the user to answer every part of item 4 of 9 in one reply, the parts he has answered included, "
              "giving each part's number with its letter, as in `1 a 2 d`, because this hook reads each reply on its "
              "own, so a reply that names only the parts still missing would leave the others unanswered."],
          f"lines {lines!r}")
    for prompt, letter, flag in (("1 a 2 a 3 a", "A", " check`"), ("approve 1, 2 and 3", "A", " check`"),
                                 ("1 d 2 d 3 d", "D", " check --disapproved`")):
        lines = case.lines(prompt)
        check(f"{prompt!r} gives every part {letter}, so it is {letter} to the whole item, with that letter's "
              "check command",
              lines is not None and lines[1] == parts_read_line(", ".join(f"part {n}: {letter}" for n in "123"))
              and lines[2] == (f"Every part has the answer {letter}, so the answer is {letter} to the whole of item 4 "
                               "of 9, and means what the lines below say.")
              and lines[3].startswith(f"{letter} means ") and "(make all three changes)" in lines[3]
              and any(flag in line for line in lines[4:]), f"lines {lines!r}")
    lines = case.lines("1 z 2 z 3 z")
    check("'1 z 2 z 3 z' gives every part Z, so it is Z to the whole item, not a part deferred beside answered ones",
          lines is not None and lines[1:] == [
              parts_read_line("part 1: Z, part 2: Z, part 3: Z"),
              "Every part has the answer Z, so the answer is Z to the whole of item 4 of 9, and means what the lines "
              "below say.",
              "Z means defer: move item 4 of 9 as the walk-me-through skill's sentence on Z says.",
              "Then run the check step with --deferred, then close, and do what close prints."], f"lines {lines!r}")
    lines = case.lines("1 a 1 d 2 a 3 a")
    check("a part given two letters is refused whole",
          lines is not None and lines[1:] == [
              "The answer gives part 1 of item 4 of 9 more than one letter.",
              "Record nothing and act on none of the answer, because the letters for that part contradict each other.",
              "Ask the user to answer every part of item 4 of 9 again, giving each part's number once with its "
              "letter, as in `1 a 2 d`."],
          f"lines {lines!r}")
    lines = case.lines("2 r")
    check("R on a part shows the waiting item again and records nothing",
          lines is not None and lines[1:] == [
              parts_read_line("part 2: R"),
              "R on a part asks to see item 4 of 9 again: show it in full, heading included, word for word as the "
              "walk-document has it."], f"lines {lines!r}")
    lines = Case(next_to_present="item 7 of 9", document=PARTS_DOCUMENT).lines("1 a 2 d")
    check("parts labelled `**Part 1:**` and `### Part 2` are read as parts",
          lines is not None and lines[1:] == [parts_read_line("part 1: A, part 2: D", "item 7 of 9", "2")]
          + parts_different_letters_lines("--part-answer 1=A --part-answer 2=D"), f"lines {lines!r}")


def test_numbers_are_item_numbers_when_the_waiting_item_has_no_parts_or_a_number_falls_outside_them():
    for next_to_present, prompt, named in (
            ("item 8 of 9", "1 a 2 d", "item 1 of 9, item 2 of 9, which are"),
            ("item 4 of 9", "1 a 6 d", "item 1 of 9, item 6 of 9, which are"),
            ("item 4 of 9", "1 a 2.1 d", "item 1 of 9, item 2.1 of 9, which are"),
            ("item 4 of 9", "1 a 2 z", None)):
        lines = Case(next_to_present=next_to_present, document=PARTS_DOCUMENT).lines(prompt)
        if named is None:
            check(f"{prompt!r} on an item with parts reads Z on a part as a part's letter",
                  lines is not None and lines[1:] == [parts_read_line("part 1: A, part 2: Z")]
                  + parts_unanswered_lines("part 3"),
                  f"lines {lines!r}")
            continue
        check(f"{prompt!r} while {next_to_present} waits is read as item numbers and refused as today",
              lines is not None
              and lines[1] == (f"The answer gives a letter to {named} not waiting for an answer, and the minutes' "
                               f"`#next_to_present` line names only {next_to_present}."), f"lines {lines!r}")
    own_number_document = PARTS_DOCUMENT.replace("## Item 4 of 9:", "## Item 2 of 9:")
    case = Case(next_to_present="item 2 of 9", document=own_number_document)
    for prompt in ("2 a", "item 2 a", "approve item 2", "approve 2"):
        lines = case.lines(prompt)
        check(f"{prompt!r} while item 2, with parts 1 to 3, waits is A to item 2, not to its part 2",
              lines is not None
              and lines[1] == "The answer gives each item it names its own letter: item 2 of 9: A.", f"lines {lines!r}")
    lines = case.lines("1 a 2 d")
    check("'1 a 2 d' while item 2, with parts 1 to 3, waits still answers its parts",
          lines is not None and lines[1:] == [parts_read_line("part 1: A, part 2: D", "item 2 of 9")]
          + parts_unanswered_lines("part 3", "item 2 of 9"), f"lines {lines!r}")
    lines = Case(next_to_present="item 4 of 9", document=PARTS_DOCUMENT).lines("item 1 a item 2 d")
    check("an answer that says `item` names items, not parts",
          lines is not None and lines[1].startswith("The answer gives a letter to item 1 of 9, item 2 of 9"),
          f"lines {lines!r}")
    lines = Case(next_to_present="items 4 and 7 of 9", document=PARTS_DOCUMENT).lines("1 a 2 d")
    check("with two items with parts waiting, numbers stay item numbers",
          lines is not None and lines[1].startswith("The answer gives a letter to item 1 of 9, item 2 of 9"),
          f"lines {lines!r}")


def test_part_numbers_are_read_only_from_top_level_lines_outside_code_and_only_as_a_run_from_1():
    for name, body, prompt in (
            ("numbers inside a fenced code block", "```\n1. one\n2. two\n```", "1 a 2 d"),
            ("a nested list", "- a list\n  1. one\n  2. two", "1 a 2 d"),
            ("a single numbered line", "1. only one", "1 a"),
            ("numbers that do not start at 1", "2. two\n3. three", "2 a 3 d"),
            ("more than five numbers", "1. a\n2. b\n3. c\n4. d\n5. e\n6. f", "1 a 2 d"),
            ("a decimal at a line's start", "1.5 litres\n2.5 litres", "1 a 2 d")):
        document = f"## Item 4 of 9: no real parts\n\n{body}\n\nRecommendation: keep it.\n"
        lines = Case(next_to_present="item 4 of 9", document=document).lines(prompt)
        first = prompt.split()[0]
        check(f"{name} are not parts, so {prompt!r} is read as item numbers",
              lines is not None and lines[1].startswith(f"The answer gives a letter to item {first} of 9"),
              f"lines {lines!r}")


def test_numbered_r_whose_walk_document_or_marker_cannot_be_read_still_goes_to_the_agent():
    for case, problem in ((Case(next_to_present="item 4 of 9", document=None), "no walk-document"),
                          (Case(next_to_present="paused until rewritten"), "a marker naming no item")):
        lines = case.lines("4 r")
        check(f"'4 r' with {problem} tells the agent to show item 4, instead of printing nothing",
              lines is not None and any(line.startswith("\"4 R\" asks to see item 4") for line in lines),
              f"lines {lines!r}")


def test_numbered_r_reads_the_walk_in_the_payloads_cwd_not_the_hooks_own():
    case = Case(next_to_present="item 4 of 9", document=NUMBERED_R_DOCUMENT)
    payload = {"hook_event_name": "UserPromptSubmit", "session_id": "test-session",
               "cwd": str(case.checkout), "prompt": "37.4 r"}
    result = subprocess.run([sys.executable, str(HOOK_SCRIPT)], input=json.dumps(payload),
                            capture_output=True, text=True, cwd=SUITE_ROOT)
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"] if not_blocked(result) else ""
    check("'37.4 r' run from outside the checkout still finds item 37.4 in the payload's cwd",
          context.startswith(f"The user answered \"37.4 r\" to item 4 of 9 of approval-walk {WALK_NAME}.\n"
                             + numbered_r_line("37.4", "item 37.4 of 9")),
          f"exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")


def test_numbered_r_on_unreadable_minutes_expands_and_says_so():
    case = Case(next_to_present="item 3 of 9")
    (case.walk / f"{WALK_NAME}-minutes.md").write_bytes(b"#next_to_present item 3 of 9 \xff\xfe\n")
    lines = case.lines("6 r")
    check("'6 r' on minutes that cannot be read names the failure and still says to show item 6",
          lines is not None
          and "reading the approval-walk state failed: UnicodeDecodeError" in lines[0]
          and numbered_r_line("6", "item 6") in lines
          and not any("check step" in line for line in lines), f"lines {lines!r}")


def test_all_a_and_all_ao():
    case = Case(next_to_present="items 5 and 6 of 9")
    for prompt in ("all a", "A to all."):
        lines = case.lines(prompt)
        check(f"{prompt!r} approves every waiting item",
              lines is not None
              and lines[1] == (f"\"{prompt.rstrip('.')}\" means A to every item now waiting, items 5 and 6 of 9: the "
                               "user agrees with each one's recommendation. Do what each recommends. For each item, "
                               "whether or not it makes a change, run the check step, then close, and do what close "
                               "prints; write nothing in the minutes by hand but the `#next_to_present` lines below.")
              and lines[2] == ONE_ITEM_AT_A_TIME_LINE, f"lines {lines!r}")
    for prompt in ("all ao", "ao to all"):
        lines = case.lines(prompt)
        check(f"{prompt!r} approves every waiting item as obvious",
              lines is not None and lines[1].startswith(f"\"{prompt}\" means AO to every item now waiting")
              and lines[1].endswith("For each item, whether or not it makes a change, run the check step (with "
                                    "--obvious for `all ao`), then close, and do what close prints; write nothing in "
                                    "the minutes by hand but the `#next_to_present` lines below.")
              and lines[2] == ONE_ITEM_AT_A_TIME_LINE, f"lines {lines!r}")
    for prompt in ("all a", "all ao"):
        lines = Case().lines(prompt)
        check(f"{prompt} with no approval-walk acts on each open recommendation, with the single approval's fast "
              "reads printed beside it",
              lines is not None and lines[1].startswith(f"\"{prompt}\" means the user agrees with every recommendation")
              and lines[1].endswith("as the lines below say for a single approval.")
              and "that text" not in lines[1]
              and any(line.startswith("If that makes a change, first save each text the change adds that has not had "
                                      "a fast read to a scratch file, run `python3 ") for line in lines[2:])
              and any(line.startswith("If a fast read prints a line opening FAILED") for line in lines[2:]),
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
    case = Case(next_to_present="item 3 of 9")
    lines = case.lines("d") or []
    commands = [line.split("`")[1] for line in lines if "`python3 " in line and " check" in line]
    result = subprocess.run((commands or ["false"])[0].split() + ["--counts-log", str(case.checkout.parent / "c.tsv")],
                            capture_output=True, text=True, cwd=case.checkout)
    check("the check command the hook names for 'd' runs and records the answer as disapproved",
          result.returncode == 0 and "item 3 of 9: the user answered disapproved ("
          in (case.walk / f"{WALK_NAME}-minutes.md").read_text(), f"lines {lines!r}, stdout {result.stdout!r}")
    # Z's text names the check step and its flag, not the whole command.
    case = Case(next_to_present="item 3 of 9")
    lines = case.lines("z") or []
    result = subprocess.run(CHECK.strip("`").split() + ["--deferred"], capture_output=True, text=True, cwd=case.checkout)
    check("Z's text names --deferred, and the check step run with it records the answer as deferred",
          any("--deferred" in line for line in lines) and result.returncode == 0
          and "item 3 of 9: the user answered deferred (" in (case.walk / f"{WALK_NAME}-minutes.md").read_text(),
          f"lines {lines!r}, stdout {result.stdout!r}, stderr {result.stderr!r}")


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


def test_a_mention_of_an_item_inside_another_does_not_take_its_recommendation():
    document = ("# A walk\n\n## Item 4 of 9: four\n\nRecommendation: do four.\n\n## Items 5 and 6 of 9: grouped\n\n"
                "**Item 5 of 9**: the label wording.\n\nRecommendation: adopt label text five.\n\n"
                "**Item 6 of 9**: the button wording.\n\nRecommendation: use the same style as Item 5 of 9.\n\n"
                "## Item 7 of 9: seven\n\nRecommendation: do seven.\n")
    lines = Case(next_to_present="item 5 of 9", document=document).lines("a")
    check("item 5's recommendation is its own, though item 6 mentions `Item 5 of 9`",
          lines is not None and lines[1].startswith(
              "A means approve: the user agrees with the recommendation of item 5 of 9 (adopt label text five)."),
          f"lines {lines!r}")


def shared_heading_document(parts):
    return ("# A walk\n\n## Item 4 of 9: four\n\nRecommendation: do four.\n\n## Items 5 and 6 of 9: grouped\n\n"
            + parts + "\n## Item 7 of 9: seven\n\nRecommendation: do seven.\n")


SHARED_HEADING_OPENINGS_READ = {
    "a bold count with no `of M`": ("**Item 5: the path.** Recommendation: fix the path.\n\n"
                                     "**Item 6: the sentence.** Recommendation: drop it.\n"),
    "a list item opening with a bold count with no `of M`": ("- **Item 5, the path.** Recommendation: fix the path.\n"
                                                              "- **Item 6, the sentence.** Recommendation: drop it.\n"),
    "a list item opening with a bold count with `of M`": ("- **Item 5 of 9**: the path.\n  Recommendation: fix the path.\n"
                                                           "- **Item 6 of 9**: the sentence.\n  Recommendation: drop it.\n"),
    "a bold label ending in a period": ("**Item 5.** The path. Recommendation: fix the path.\n\n"
                                        "**Item 6.** The sentence. Recommendation: drop it.\n"),
    "a plain label": ("Item 5: the path. Recommendation: fix the path.\n\n"
                      "Item 6. The sentence. Recommendation: drop it.\n"),
}

# Each is a top-level line inside item 5's part, ahead of its recommendation, that only mentions item 6.
MENTIONS_OF_ANOTHER_ITEM = {
    "a plain sentence about item 6": "Item 6 depends on item 5, so answer 5 first.",
    "a bold sentence about item 6": "**Item 6** depends on item 5, so answer 5 first.",
    "a possessive": "Item 6's sentence stays.",
    "a bold possessive": "**Item 6's** sentence stays.",
    "a bold label that ends before `of` another total": "**Item 6** of 8 said the same.",
    "a longer number of another walk": "Item 60 of the previous approval-walk said the same.",
    "a bold longer number of another walk": "**Item 60** of the previous approval-walk said the same.",
    "a bold longer number with its `of` inside the bold": "**Item 60 of the previous approval-walk** said the same.",
    "an item's part number": "Item 6.2 shows the rewrite.",
    "a bold item's part number": "**Item 6.2** shows the rewrite.",
    "a bold item's part number followed by its words": "**Item 6.2 shows** the rewrite.",
    "a plain number followed by more words": "Item 6 of the plan said the same.",
    "a bold number followed by more words": "**Item 6 of the plan** said the same.",
    "a bold label in a list in a quotation": "> - **Item 6: a quotation.** Recommendation: quoted.",
    "a bold label in a nested list": "- Context.\n  - **Item 6: nested.** Recommendation: nested.",
}
FINDER_MODULE_FILE = (HOOK_SCRIPT.parent
                      / "walk-me-through-approval-walk-minutes-and-walk-document-item-finder-common.py")


def test_no_mention_of_another_item_is_read_as_an_opening_in_any_place_an_opening_is_read():
    specification = importlib.util.spec_from_file_location("item_finder", FINDER_MODULE_FILE)
    finder = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(finder)
    parser = finder.markdown_parser()
    for shape, mention in MENTIONS_OF_ANOTHER_ITEM.items():
        # A one-line mention is tried as each place an opening is read: a top-level paragraph, under each emphasis,
        # and the first line of a top-level list item; a mention that has its own structure is tried as written.
        if "\n" in mention or mention.startswith((">", "-")):
            places = {"as written": mention}
        else:
            places = {"a top-level paragraph": mention, "a top-level list item": f"- {mention}",
                      "a paragraph in `__`": mention.replace("**", "__")}
        for place, text in places.items():
            openings = finder.item_opening_lines(f"Before.\n\n{text}\n\nAfter.\n", parser)
            check(f"{shape}, as {place}, is not read as an opening of item 6",
                  not any("6" in numbers for numbers, _ in openings.values()), f"openings {openings!r}")


def test_a_line_that_only_mentions_another_item_does_not_open_it_under_a_shared_heading():
    for shape, mention in MENTIONS_OF_ANOTHER_ITEM.items():
        parts = (f"**Item 5: the path.**\n\n{mention}\n\nRecommendation: fix the path.\n\n"
                 "**Item 6: the sentence.**\n\nRecommendation: drop it.\n")
        for number, recommendation in (("5", "fix the path"), ("6", "drop it")):
            lines = Case(next_to_present=f"item {number} of 9", document=shared_heading_document(parts)).lines("a")
            check(f"under a shared heading, {shape} inside item 5's part does not open item 6, so item {number} reads "
                  "its own recommendation",
                  lines is not None and lines[1].startswith(
                      f"A means approve: the user agrees with the recommendation of item {number} of 9 ({recommendation}).")
                  and not any(line.startswith("The hook could not read") for line in lines), f"lines {lines!r}")


def test_each_item_under_a_shared_heading_reads_its_own_recommendation_from_each_opening_shape():
    for shape, parts in SHARED_HEADING_OPENINGS_READ.items():
        for number, recommendation in (("5", "fix the path"), ("6", "drop it")):
            lines = Case(next_to_present=f"item {number} of 9", document=shared_heading_document(parts)).lines("a")
            check(f"under a shared heading, item {number} opening with {shape} reads its own recommendation",
                  lines is not None and lines[1].startswith(
                      f"A means approve: the user agrees with the recommendation of item {number} of 9 ({recommendation}).")
                  and not any(line.startswith("The hook could not read") for line in lines), f"lines {lines!r}")


SHARED_HEADING_OPENINGS_NOT_READ = {
    "a continuation line": ("**Item 5 of 9**: the path.\nRecommendation: fix the path.\n"
                            "**Item 6 of 9**: the sentence.\nRecommendation: drop it.\n", "item 6"),
    "a line inside <details>": ("**Item 5 of 9**: the path.\nRecommendation: fix the path.\n\n<details>\n"
                                "**Item 6 of 9**: the sentence.\nRecommendation: drop it.\n</details>\n", "item 6"),
    "a plain list item": ("- Item 5: the path. Recommendation: fix the path.\n"
                          "- Item 6: the sentence. Recommendation: drop it.\n", "item 5, item 6"),
    "a plain list item with the full count": ("- Item 5 of 9: the path. Recommendation: fix the path.\n"
                                              "- Item 6 of 9: the sentence. Recommendation: drop it.\n",
                                              "item 5, item 6"),
    "a bold number with no `Item`": ("**5. The path.** Recommendation: fix the path.\n\n"
                                     "**6. The sentence.** Recommendation: drop it.\n", "item 5, item 6"),
    "a count of another document's items": ("Item 5 of the plan: the path. Recommendation: fix the path.\n\n"
                                            "Item 6 of the plan: the sentence. Recommendation: drop it.\n",
                                            "item 5, item 6"),
}


def test_items_under_a_shared_heading_whose_openings_are_not_read_get_no_recommendation_and_the_reason():
    for shape, (parts, missing) in SHARED_HEADING_OPENINGS_NOT_READ.items():
        for number in ("5", "6"):
            lines = Case(next_to_present=f"item {number} of 9", document=shared_heading_document(parts)).lines("a")
            check(f"under a shared heading with more than one recommendation, item {number}, where an item opens with "
                  f"{shape}, gets no recommendation and the line saying why",
                  lines is not None
                  and lines[1] == f"A means approve: the user agrees with the recommendation of item {number} of 9. "
                                  "Do what the recommendation says."
                  and any(line.startswith(f"The hook could not read the recommendation of item {number} of 9: it is "
                                          "one of the items under the walk-document's heading `## Items 5 and 6 of 9: "
                                          "grouped`")
                          and f"because {missing} has no opening it reads" in line for line in lines),
                  f"lines {lines!r}")


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
