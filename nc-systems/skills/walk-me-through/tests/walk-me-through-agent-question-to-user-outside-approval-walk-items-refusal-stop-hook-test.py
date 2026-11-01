#!/usr/bin/env python3
"""Cases for the Stop hook that, during an open approval-walk, blocks the
agent's stop when its reply asks the user something outside the walk's items.

Most cases run the hook as a subprocess, its real stdin-to-stdout path, in a
scratch checkout this suite made, with a transcript this suite wrote. The model
call is never real: a fake `claude` first on PATH records each call and answers
as the case sets it. The refusal log goes to a file in the scratch directory.
"""

import importlib.util
import json
import os
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
               / "walk-me-through-agent-question-to-user-outside-approval-walk-items-refusal-stop-hook.py")
_hook_spec = importlib.util.spec_from_file_location("question_refusal_stop_hook", HOOK_SCRIPT)
hook = importlib.util.module_from_spec(_hook_spec)
_hook_spec.loader.exec_module(hook)
# The walk-me-through skill's closing line after its link; the answer hook's suite checks SKILL.md holds it.
CLOSING_LINE_ANSWER_LETTERS = ("A approve · AO approve as obvious · Aa approve after an advisor check · D disapprove · "
                               "Z defer · E explain · O other options")
SUITE_ROOT = Path(tempfile.mkdtemp(prefix="approval-walk-question-refusal-hook-test-")).resolve()
FAKE_BIN = SUITE_ROOT / "bin"
failures = []

ANSWER_LINE = ("Answer A to approve, AO to approve it as obvious, Aa to approve after an advisor check, D to "
               "disapprove, Z to defer, R to repeat the item, E to have it explained, or O to ask for other options.")
WALK_DOCUMENT = f"""# The poem page: approval-walk

This approval-walk settles where the poem page lives. It has 10 items.

## Item 1 of 10: the page's name

The page is named by the naming page. Recommendation: Use the name.

{ANSWER_LINE}

## Item 2 of 10: where the poem page lives

The page goes in the [wiki](file:///x/wiki), next to the glossary. Do you agree that agents look there first?

**The strongest case against:** one more page to read. Recommendation: Put it in the wiki.

{ANSWER_LINE}

## Item 3 of 10: the hook

A hook checks each written file. Recommendation: Build the hook.

{ANSWER_LINE}
"""
ITEM_2_SHOWN = """**Item 2 of 10: where the poem page lives**

The page goes in the wiki, next to the glossary. Do you agree that agents look there first?

**The strongest case against:** one more page to read. Recommendation: Put it in the wiki.

""" + ANSWER_LINE
INTERRUPTION_ITEM = f"""## Item 2.1 of 11: merge-lane-2's question about the GHI

merge-lane-2 asks: should I file one GHI listing the remaining seats' tests?

Recommendation: File it.

{ANSWER_LINE}
"""

FAKE_CLAUDE = """#!/usr/bin/env python3
import json, os, sys, time
with open(os.environ["FAKE_CLAUDE_CALLS"], "a") as calls:
    calls.write(json.dumps({"argv": sys.argv[1:], "stdin": sys.stdin.read()}) + "\\n")
mode = os.environ.get("FAKE_CLAUDE_MODE", "no")
if mode == "sleep":
    time.sleep(30)
if mode == "fail":
    print(json.dumps({"type": "result", "is_error": True, "result": "Not logged in"}))
    sys.exit(1)
if mode == "garbage":
    print("not json")
    sys.exit(0)
if mode == "stderr-only":
    print("Not logged in. Run claude login.", file=sys.stderr)
    sys.exit(1)
if mode == "error-exit-0":
    print(json.dumps({"type": "result", "is_error": True, "result": "API overloaded",
                      "structured_output": {"asks_user": False, "line_number": 0}}))
    sys.exit(0)
if mode in ("verdict-exit-1", "verdict-then-killed"):
    print(json.dumps({"type": "result", "is_error": False,
                      "structured_output": {"asks_user": False, "line_number": 0}}), flush=True)
    if mode == "verdict-exit-1":
        sys.exit(1)
    import signal
    os.kill(os.getpid(), signal.SIGKILL)
asks = mode.startswith("yes")
number = int(mode.split(":")[1]) if ":" in mode else (1 if asks else 0)
print(json.dumps({"type": "result", "is_error": False,
                  "structured_output": {"asks_user": asks, "line_number": number}}))
"""


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def opening_prompt(turn_origin, text, **fields):
    return {"type": "user", "turnOrigin": turn_origin, **fields,
            "message": {"role": "user", "content": [{"type": "text", "text": text}]}}


USER_PROMPT = opening_prompt("human", "A", origin={"kind": "human"}, promptSource="typed")
PEER_PROMPT = opening_prompt("peer", "Another Claude session sent a message: should I file one GHI?",
                             origin={"kind": "peer"}, isMeta=True, promptSource="system")


def text_record(text):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


def tool_record(name, tool_input):
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": name, "input": tool_input}]}}


class Case:
    """One case's own checkout, walk files, transcript, fake model and log."""

    counter = 0

    def __init__(self, minutes="#next_to_present item 2 of 10", document=WALK_DOCUMENT):
        Case.counter += 1
        self.root = SUITE_ROOT / f"case-{Case.counter}"
        self.checkout = self.root / "checkout"
        self.checkout.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.checkout)], check=True)
        self.walk = self.checkout / "docs" / "walk"
        self.walk.mkdir(parents=True)
        self.document = self.walk / "poem-page-2026-10-12.md"
        self.document.write_text(document)
        self.minutes = self.walk / "poem-page-2026-10-12-minutes.md"
        self.minutes.write_text(f"# Minutes\n\n{minutes}\n")
        self.transcript = self.root / "transcript.jsonl"
        self.calls = self.root / "model-calls.jsonl"
        self.log = self.root / "refusals.jsonl"

    def records(self, *records):
        self.transcript.write_text("".join(json.dumps(record) + "\n" for record in records))

    def reply(self, *texts, opening=USER_PROMPT):
        self.records(opening, *(text_record(text) for text in texts))

    def run(self, model="no", stop_hook_active=False, last_assistant_message=None, environment_extra=None,
            stdin_text=None):
        payload = {"hook_event_name": "Stop", "session_id": "test-session",
                   "transcript_path": str(self.transcript), "cwd": str(self.checkout),
                   "stop_hook_active": stop_hook_active}
        if last_assistant_message is not None:
            payload["last_assistant_message"] = last_assistant_message
        environment = {name: value for name, value in os.environ.items()
                       if name not in ("NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER",
                                       "CLAUDE_CODE_SESSION_ATTENDED")}
        environment.update({"PATH": f"{FAKE_BIN}{os.pathsep}{os.environ['PATH']}",
                            "FAKE_CLAUDE_CALLS": str(self.calls), "FAKE_CLAUDE_MODE": model,
                            hook.LOG_PATH_VARIABLE: str(self.log)})
        environment.update(environment_extra or {})
        return subprocess.run([sys.executable, str(HOOK_SCRIPT)],
                              input=json.dumps(payload) if stdin_text is None else stdin_text,
                              capture_output=True, text=True, env=environment, cwd=self.checkout)

    def model_calls(self):
        if not self.calls.exists():
            return []
        return [json.loads(line) for line in self.calls.read_text().splitlines()]

    def logged(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]


def blocked_reason(result):
    if result.returncode != 0 or not result.stdout.strip():
        return None
    output = json.loads(result.stdout)
    return output["reason"] if output.get("decision") == "block" else None


def check_silent(case_name, result):
    check(case_name, result.returncode == 0 and result.stdout == "",
          f"exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")


def check_blocked(case_name, result, *phrases):
    reason = blocked_reason(result)
    check(case_name, reason is not None and all(phrase in reason for phrase in phrases),
          f"exit {result.returncode}, stdout {result.stdout!r}, stderr {result.stderr!r}")


def test_a_clear_question_blocks_without_the_model_and_is_logged():
    case = Case()
    case.reply("The tests passed.\n\nShould I merge the pull request now?\n\nItem 2 of 10 is waiting for your answer.")
    result = case.run(model="no")
    check_blocked("a sentence ending in a question mark blocks", result,
                  '"Should I merge the pull request now?"', "the hook's code read it as a clear question")
    check("a clear question is decided without the model", case.model_calls() == [], case.model_calls())
    entries = case.logged()
    check("the refusal is logged with its time, session, walk, sentence and what decided",
          len(entries) == 1 and entries[0]["session"] == "test-session"
          and entries[0]["walk"] == "poem-page-2026-10-12"
          and entries[0]["sentence"] == "Should I merge the pull request now?"
          and entries[0]["decided_by"] == "code" and entries[0]["time"].endswith("+00:00"), entries)
    for case_name, text in (
            ("`say yes` blocks", "The fix is ready. Say yes and I will push it."),
            ("`answer A` blocks", "The fix is ready. Answer A and I will push it."),
            ("`waiting for your answer` on a question that is not an item blocks",
             "The cleanup of the old directories is still waiting for your answer."),
            ("a bold question blocks", "**Do you agree with merging the two lines?** A: merge. D: keep both."),
            ("a cue split by bold marks blocks once the marks are dropped", "**Should** I go ahead with the merge."),
            ("a question relayed in quotes from another agent blocks",
             'merge-lane-2 asks: "Should the hook be fixed today?" I recommend yes.')):
        case.reply(text)
        check_blocked(case_name, case.run(model="no"), "approval-walk question check")


def test_the_block_message_says_what_to_do():
    case = Case()
    case.reply("Should I merge the pull request now?")
    reason = blocked_reason(case.run()) or ""
    for case_name, phrase in (
            ("the message says the hook refused on purpose", "this hook refused to end your turn on purpose"),
            ("the message names the walk and quotes the flagged text",
             "the open approval-walk poem-page-2026-10-12 (the hook's code read it as a clear question). "
             "The flagged text: \"Should I merge the pull request now?\""),
            ("the message names the waiting item", "goes to the waiting item, item 2,"),
            ("the message names the interruption item's number and the new total",
             "`## Item 2.1 of 11: <the point of the question>`, placed right after item 2."),
            ("the message says to quote the question whole with a recommendation",
             "Quote the question whole in the item, as its asker wrote it, whether you or another agent, giving each "
             "line of the flagged text a line of its own, word for word, and putting the rest of the question on "
             "other lines of the item. This hook passes the question only when the item in the walk-document holds every flagged line "
             "that way, and refuses again until it does; it ignores a `>` quote mark or a list mark such as `-` or "
             "`1.` at the start of a line, bold, italic and code marks, and letter case, so you may add or drop those. "
             "Give the item one recommendation and one alternative, and end it with the recommendation stated as "
             "an action, as in `Recommendation: <what you recommend doing>.` State the alternative before it, as in "
             "`The alternative: <what D does instead>.`"),
            ("the message says to change M everywhere",
             f"Change the walk's item count M from 10 to 11 in every item heading of {case.document} that carries `of 10`"),
            ("the message gives the minutes' new line",
             f"the last `#next_to_present` line of {case.minutes}, which then reads `#next_to_present item 2 of 11`"),
            ("the message says not to show the new item now",
             "Do not show the new item now: it is shown after item 2 is answered."),
            ("the message gives the closing line's form when the minutes record no page for the waiting item",
             "End the message you write next with the line `I added the question as Item 2.1 of 11.` and then the "
             "waiting item's closing line, as the walk-me-through skill writes it, as the last text of that message:\n"
             f"`[Item 2 of 11, where the poem page lives](<page link>) · {CLOSING_LINE_ANSWER_LETTERS}`\n"
             "The minutes record no `#item_page` line for item 2. For each such item, publish its page first if it "
             f"has none and add to {case.minutes} the line `#item_page item <N> of <M> <the page's link>`, which this "
             "hook reads back; then put the same link in place of `<page link>` in the item's closing line.\n"),
            ("the message says how to clear a false block",
             "If the flagged text does not ask the user anything, reword it in your reply so that it no longer reads")):
        check(case_name, phrase in reason, reason)
    taken = Case(document=WALK_DOCUMENT + "\n" + INTERRUPTION_ITEM.replace("of 11", "of 10"))
    taken.reply("Should I merge the pull request now?")
    check_blocked("an interruption number already in the walk-document is skipped",
                  taken.run(), "`## Item 2.2 of 11: <the point of the question>`")


def test_a_reply_with_nothing_question_like_passes():
    case = Case()
    for case_name, text in (
            ("a plain report passes", "The background job finished, and its report is in the log-store."),
            ("the waiting-item line the skill requires passes",
             "PR 1922 merged.\n\nItem 2 of 10 is waiting for your answer."),
            ("a question in a code span passes", "I ran `grep -c 'why?' notes.md` and found none."),
            ("a question in a code block passes", "The test prints:\n\n```\nShould I retry?\n```\n\nIt retried once."),
            ("`answer a` followed by a noun is the article, not the letter A, so it passes",
             "> When you answer a finding with a new rule, check the rule against the program's real output.")):
        case.reply(text)
        check_silent(case_name, case.run(model="yes"))
    check("a reply with nothing question-like never calls the model", case.model_calls() == [], case.model_calls())


def test_an_unclear_line_goes_to_the_model():
    case = Case()
    case.reply("The fix has a second part, and I recommend building it next.")
    result = case.run(model="yes:1")
    check_blocked("an unclear line the model says asks the user blocks", result,
                  '"The fix has a second part, and I recommend building it next."',
                  "the model judged that it asks him something")
    calls = case.model_calls()
    argv = calls[0]["argv"] if calls else []
    check("the model is called once, as Haiku, with every hook disabled and no session file",
          len(calls) == 1 and argv[argv.index("--model") + 1] == hook.MODEL == "claude-haiku-5-5"
          and json.loads(argv[argv.index("--settings") + 1]) == {"disableAllHooks": True}
          and "--no-session-persistence" in argv, calls)
    check("the model is given the unclear line, numbered, and the walk's total and waiting item",
          calls and "1. The fix has a second part, and I recommend building it next." in calls[0]["stdin"]
          and "`Item N of 10`, or `item N` for short, and item 2 waits for his answer" in calls[0]["stdin"], calls)
    check("a block the model decided is logged as the model's",
          [entry["decided_by"] for entry in case.logged()] == ["model"], case.logged())
    check_silent("an unclear line the model says asks nothing passes", case.run(model="no"))
    case.reply("Waiting on you: should line 34 change, as item 2 of 10 asks?")
    check_silent("a clear question on a line naming an item is unclear, so the model decides", case.run(model="no"))
    case.reply("I recommend building it next.\n\nThat also fixes the second part, if you agree with the plan.")
    check_blocked("the model's line number picks the sentence named", case.run(model="yes:2"),
                  '"That also fixes the second part, if you agree with the plan."')


def test_a_failed_model_check_blocks():
    case = Case()
    case.reply("The fix has a second part, and I recommend building it next.")
    for case_name, mode, phrase in (
            ("a model call that exits nonzero blocks", "fail", "claude exited 1"),
            ("a model call that prints no verdict blocks, quoting its output", "garbage", "without a verdict (JSONDecodeError"),
            ("the output of a call with no verdict is quoted", "garbage", "): not json"),
            ("a model call that writes only to stderr blocks, quoting stderr", "stderr-only",
             "Not logged in. Run claude login."),
            ("a model call that reports an error with exit 0 blocks", "error-exit-0",
             "claude exited 0 reporting an error: API overloaded"),
            ("a model call that prints a verdict but exits 1 blocks", "verdict-exit-1",
             "claude exited 1 reporting an error"),
            ("a model call killed by a signal after printing a verdict blocks", "verdict-then-killed",
             "claude exited -9 reporting an error")):
        check_blocked(case_name, case.run(model=mode), "the hook's `claude -p` call that has the model judge this unclear text failed", phrase,
                      '"The fix has a second part, and I recommend building it next."')
    check("a block after a failed model check is logged as such",
          [entry["decided_by"] for entry in case.logged()] == ["model-check-failed"] * 7, case.logged())
    saved_path = os.environ["PATH"]
    os.environ["FAKE_CLAUDE_CALLS"] = str(case.calls)
    try:
        os.environ["PATH"] = str(SUITE_ROOT / "no-such-directory")
        line, failure = hook.model_judgement(["x"], ["x"], "10", "2")
        check("a model that cannot be run is a failure", line is None and "could not be run" in (failure or ""),
              failure)
        os.environ["PATH"] = f"{FAKE_BIN}{os.pathsep}{saved_path}"
        os.environ["FAKE_CLAUDE_MODE"] = "sleep"
        line, failure = hook.model_judgement(["x"], ["x"], "10", "2", timeout_seconds=1)
        check("a model call past its time limit is a failure",
              line is None and "no answer within 1 seconds" in (failure or ""), failure)
        os.environ["FAKE_CLAUDE_MODE"] = "yes:7"
        line, failure = hook.model_judgement(["a", "b"], ["a", "b"], "10", "2")
        check("a line number out of range picks the first unclear line", (line, failure) == ("a", None),
              (line, failure))
        for mode, expected in (("yes:0", "a"), ("yes:3", "c"), ("yes:2", "b")):
            os.environ["FAKE_CLAUDE_MODE"] = mode
            line, failure = hook.model_judgement(["a", "b", "c"], ["a", "b", "c"], "10", "2")
            check(f"the model's answer {mode} picks unclear line {expected}", (line, failure) == (expected, None),
                  (line, failure))
    finally:
        os.environ["PATH"] = saved_path
        os.environ.pop("FAKE_CLAUDE_MODE", None)
        os.environ.pop("FAKE_CLAUDE_CALLS", None)


def test_a_question_held_in_an_interruption_item_is_not_checked():
    stray = "merge-lane-2 asks: should I file one GHI listing the remaining seats' tests?"
    closing = "I added it as Item 2.1 of 11.\n\nItem 2 of 11 is waiting for your answer."
    held = Case(document=WALK_DOCUMENT.replace("of 10", "of 11") + "\n" + INTERRUPTION_ITEM,
                minutes="#next_to_present item 2 of 11")
    held.records(PEER_PROMPT, text_record(stray), text_record(closing))
    check_silent("a question an interruption item after the waiting item holds passes, with no tool call this turn",
                 held.run(model="yes"))
    check("a question held in an interruption item never reaches the model", held.model_calls() == [],
          held.model_calls())
    held.reply("Should I merge the pull request now?\n\n" + closing)
    check_blocked("a question the interruption item does not hold still blocks", held.run(),
                  '"Should I merge the pull request now?"')
    part_word = Case(document=WALK_DOCUMENT.replace("of 10", "of 11") + "\n"
                     + INTERRUPTION_ITEM.replace("one GHI", "one GHIs"), minutes="#next_to_present item 2 of 11")
    part_word.reply("merge-lane-2 asks: should I file one GHI?")
    check_blocked("a line that matches the item only to part of a word still blocks", part_word.run(),
                  "approval-walk question check")
    for case_name, document, minutes in (
            ("the same question in an item that is not an interruption item blocks",
             WALK_DOCUMENT.replace("of 10", "of 11") + "\n" + INTERRUPTION_ITEM.replace("Item 2.1 of 11", "Item 11 of 11"),
             "#next_to_present item 2 of 11"),
            ("the same question in an interruption item after another item than the waiting one blocks",
             WALK_DOCUMENT.replace("of 10", "of 11") + "\n" + INTERRUPTION_ITEM.replace("Item 2.1", "Item 3.1"),
             "#next_to_present item 2 of 11"),
            ("the same question with no interruption item blocks", WALK_DOCUMENT, "#next_to_present item 2 of 10"),
            ("the same question in an interruption item that is itself waiting blocks",
             WALK_DOCUMENT.replace("of 10", "of 11") + "\n" + INTERRUPTION_ITEM,
             "#next_to_present items 2 and 2.1 of 11")):
        case = Case(document=document, minutes=minutes)
        case.records(PEER_PROMPT, text_record(stray), text_record(closing))
        check_blocked(case_name, case.run(), "approval-walk question check")
    for case_name, document, minutes in (
            ("an interruption item retitled after it was added still holds its question",
             WALK_DOCUMENT.replace("of 10", "of 11") + "\n"
             + INTERRUPTION_ITEM.replace("merge-lane-2's question about the GHI", "the remaining seats' GHI, revised"),
             "#next_to_present item 2 of 11"),
            ("an interruption item with a newer total than the minutes' still holds its question",
             WALK_DOCUMENT + "\n" + INTERRUPTION_ITEM, "#next_to_present item 2 of 10")):
        case = Case(document=document, minutes=minutes)
        case.records(PEER_PROMPT, text_record(stray), text_record(closing))
        check_silent(case_name, case.run(model="yes"))
    for case_name, reply_line, item_line, passes in (
            ("a bold question the item holds without bold passes",
             "**Should we rename the hook before it merges?**", "Should we rename the hook before it merges?", True),
            ("a question with a code span the item holds passes",
             "Should I rerun `run-all-test-suites.py` before the push?",
             "Should I rerun `run-all-test-suites.py` before the push?", True),
            ("a list joined to its lead-in that the item holds passes",
             "Should I do one of these:\n- merge the lines\n- keep both",
             "Should I do one of these:\n- merge the lines\n- keep both", True),
            ("a question holding a quotation the walk-document holds passes once the item holds it",
             'Should I label the pull request "needs-tests"?', 'Should I label the pull request "needs-tests"?', True),
            ("a numbered question passes when the item holds it without its number",
             "1. Should I keep both hooks?", "Should I keep both hooks?", True),
            ("a question the item holds with a link passes when the reply holds the link's text",
             "Should I merge PR 5 now?", "Should I merge [PR 5](https://github.com/nedschorus/nedschorus/pull/5) now?",
             True),
            ("a line that is the end of an item word for word passes", ANSWER_LINE, "Should I keep both hooks?", True),
            ("a question that is only part of a word of the item blocks",
             "File it?", "Should I refile it?", False),
            ("a word the item bolds in part does not match the whole word, so the question blocks",
             "Should we refile it?", "Should we re**file** it?", False),
            ("a short question whose words run inside the item's longer question blocks",
             "Should I merge?", "Should I merge PR 5 now?", False),
            ("an ask without a question mark whose words start the item's longer question blocks",
             "Should I merge.", "Should I merge PR 5 now?", False),
            ("a question the item holds only as a statement blocks", "Should I merge?", "Should I merge.", False),
            ("a question the item quotes after a colon in a longer line blocks",
             "Should I merge PR 5 now?", 'merge-lane-2 asks: "Should I merge PR 5 now?" before the release.', False),
            ("a question the item holds after a colon on the same line blocks",
             "Should I merge PR 5 now?", "merge-lane-2 asks: Should I merge PR 5 now?", False),
            ("an ask that is the text before an item line's colon blocks",
             "Which do you want.", "Which do you want: PR 5 or PR 6?", False),
            ("a line holding the question and more words blocks",
             "Should I merge PR 5 now? It has two open findings.", "Should I merge PR 5 now?", False),
            ("a line that is only the first sentence of the item's line blocks",
             "Should I merge PR 5 now?", "Should I merge PR 5 now? It has two open findings.", False),
            ("a two-sentence line the item holds whole passes",
             "Should I merge PR 5 now? It has two open findings.",
             "merge-lane-2 asks before the release\nShould I merge PR 5 now? It has two open findings.", True),
            ("a list copied whole, each line on its own, passes",
             "Which should I run:\n- `merge.py`\n- `keep.py`",
             "merge-lane-2 asks:\nWhich should I run:\n- `merge.py`\n- `keep.py`", True),
            ("a question the item holds on a line of its own passes",
             "Should I merge PR 5 now?", "merge-lane-2 asks before the release\nShould I merge PR 5 now?", True),
            ("a question the item holds as a `>` quote line passes",
             "Should I merge PR 5 now?", "merge-lane-2 asks before the release\n> Should I merge PR 5 now?", True),
            ("a question the item holds as a `-` list item passes",
             "Should I merge PR 5 now?", "merge-lane-2 asks before the release\n- Should I merge PR 5 now?", True),
            ("a question the item holds as a `1.` list item passes",
             "Should I merge PR 5 now?", "merge-lane-2 asks before the release\n1. Should I merge PR 5 now?", True),
            ("a question the item quotes inside a longer sentence blocks",
             "Should I merge PR 5 now?", 'merge-lane-2 asks "Should I merge PR 5 now?" before the release.', False),
            ("an ask without a question mark whose words start the item's longer question with a quotation blocks",
             "Should I merge.", 'Should I merge "PR 5" now?', False),
            ("a list whose lead-in the item holds, with other choices, blocks",
             "PR 1922 merged.\n\nShould I do one of these:\n- delete the hook\n- keep it",
             "Should I do one of these:\n- merge the lines\n- keep both", False),
            ("a list of code spans whose lead-in the item holds, with other choices, blocks",
             "Should I run one of these:\n- `delete-all.py`\n- `keep.py`",
             "Should I run one of these:\n- `merge.py`\n- `keep.py`", False),
            ("a list of code spans the item holds with its lead-in passes",
             "Should I run one of these:\n- `merge.py`\n- `keep.py`",
             "Should I run one of these:\n- `merge.py`\n- `keep.py`", True),
            ("a list the item holds whole passes when one of its lines has no text once marks are dropped",
             "Should I use one of these marks:\n- `*`\n- `-`",
             "Should I use one of these marks:\n- `*`\n- `-`", True)):
        item = f"## Item 2.1 of 11: a question\n\n{item_line}\n\nRecommendation: Merge.\n\n{ANSWER_LINE}\n"
        case = Case(document=WALK_DOCUMENT.replace("of 10", "of 11") + "\n" + item,
                    minutes="#next_to_present item 2 of 11")
        case.reply(reply_line + "\n\n" + closing)
        if passes:
            check_silent(case_name, case.run(model="yes"))
        else:
            check_blocked(case_name, case.run(), "approval-walk question check")
    with_openings = (f"## Items 2.1 and 3 of 11: two questions\n\n**Item 2.1:**\n\nShould I file the GHI?\n\n"
                     f"{ANSWER_LINE}\n\n**Item 3:**\n\nShould I merge PR 5 now?\n\n{ANSWER_LINE}\n")
    partly_opened = (f"## Items 3, 2.1 and 2.2 of 11: three questions\n\n**Item 3:**\n\nShould I merge PR 5 now?\n\n"
                     f"Should I file the GHI?\n\n**Item 2.2:**\n\nShould I rename the hook?\n\n{ANSWER_LINE}\n")
    without_openings = f"## Items 2.1 and 3 of 11: two questions\n\nShould I file the GHI?\n\nShould I merge PR 5 now?\n"
    for case_name, shared, reply_line, passes in (
            ("under a shared heading, the interruption item's own question passes",
             with_openings, "Should I file the GHI?", True),
            ("under a shared heading, the other item's question blocks", with_openings, "Should I merge PR 5 now?", False),
            ("under a shared heading, an interruption item's question passes after items without their own",
             partly_opened, "Should I rename the hook?", True),
            ("under a shared heading whose items have no openings, the interruption item's question blocks",
             without_openings, "Should I file the GHI?", False)):
        case = Case(document=WALK_DOCUMENT.replace("of 10", "of 11") + "\n" + shared,
                    minutes="#next_to_present item 2 of 11")
        case.reply(reply_line + "\n\n" + closing)
        if passes:
            check_silent(case_name, case.run(model="yes"))
        else:
            check_blocked(case_name, case.run(), "approval-walk question check")
    headed = Case(document=WALK_DOCUMENT.replace("of 10", "of 11")
                  + f"\n## Item 2.1 of 11: should I file the GHI?\n\nRecommendation: File it.\n\n{ANSWER_LINE}\n",
                  minutes="#next_to_present item 2 of 11")
    headed.reply("Item 2.1 of 11: should I file the GHI?\n\nRecommendation: File it.\n\n" + closing)
    check_silent("lines that are the start of an item word for word pass", headed.run(model="yes"))
    headed.reply("no proposed text marked\n\nItem 2.1 of 11's answer is recorded in the minutes, and its change may "
                 "now be made.\n\n" + closing)
    check_silent("the lines the walk-me-through skill and its check and close programs have the agent write pass",
                 headed.run(model="yes"))


def test_the_final_message_from_the_payload_is_checked():
    case = Case()
    case.records(USER_PROMPT, tool_record("Bash", {"command": "ls"}))
    check_blocked("a question only in the payload's last_assistant_message blocks",
                  case.run(last_assistant_message="Do you want me to merge it?"), '"Do you want me to merge it?"')
    check_silent("a turn with no text in the transcript or the payload passes", case.run())


def test_the_shown_item_and_quotes_from_it_are_not_checked():
    case = Case()
    case.reply("Recorded your answer to item 1.\n\n" + ITEM_2_SHOWN)
    check_silent("a question inside the item the reply shows does not block", case.run(model="yes"))
    case.reply(ITEM_2_SHOWN + "\n\nShould I also add a link to it?")
    check_blocked("a question after the shown item still blocks", case.run(), '"Should I also add a link to it?"')
    case.reply('You asked about "Do you agree that agents look there first?" It means the wiki comes first.')
    check_silent("a quote of the walk-document's text is not checked", case.run(model="no"))
    case.reply("> Do you agree that agents look there first?\n\nThat line is the item's question.")
    check_silent("a quotation line holding the walk-document's text is not checked", case.run(model="no"))
    check("quoted text from the walk-document never reaches the model", case.model_calls() == [], case.model_calls())
    alternative = " D: the page stays out of the wiki."
    with_alternative = Case(document=WALK_DOCUMENT.replace(ANSWER_LINE, ANSWER_LINE + alternative))
    with_alternative.reply(ITEM_2_SHOWN)
    check_silent("the shown item's answer line passes without the alternative the walk-document adds after it",
                 with_alternative.run(model="yes"))
    with_alternative.reply(ITEM_2_SHOWN + alternative)
    check_silent("the shown item's answer line passes with the alternative", with_alternative.run(model="yes"))
    numbered = Case(document=WALK_DOCUMENT.replace(f"\n{ANSWER_LINE}\n", f"\n6. {ANSWER_LINE}{alternative}\n"))
    numbered.reply(ITEM_2_SHOWN)
    check_silent("the shown item's answer line passes without the number and the alternative the walk-document adds",
                 numbered.run(model="yes"))


def test_every_turn_is_checked_whoever_started_it():
    case = Case()
    case.reply("merge-lane-2 reports PR 1922 merged. Should I start the next fix?", opening=PEER_PROMPT)
    check_blocked("a turn started by another agent-seat's message is checked", case.run(),
                  '"merge-lane-2 reports PR 1922 merged. Should I start the next fix?"')
    notice = opening_prompt("task_notification", "<task-notification>done</task-notification>",
                            origin={"kind": "task-notification"}, promptSource="system")
    case.reply("The subagent finished. Should I open the pull request?", opening=notice)
    check_blocked("a turn started by a background-task notice is checked", case.run(), "approval-walk question check")
    case.records(USER_PROMPT, text_record("Should I open the pull request?"), USER_PROMPT,
                 text_record("Recorded."))
    check_silent("a question from an earlier turn is not checked again", case.run())
    unmarked_peer_prompt = {key: value for key, value in PEER_PROMPT.items() if key != "turnOrigin"}
    case.records(USER_PROMPT, text_record("Should I open the pull request?"), unmarked_peer_prompt,
                 text_record("Noted.\n\nItem 2 of 10 is waiting for your answer."))
    check_silent("a question from an earlier turn is not checked again when the newer turn's start has no "
                 "turnOrigin", case.run())


def test_when_the_hook_stays_silent():
    case = Case()
    case.reply("Should I merge the pull request now?")
    check_silent("silent while the agent answers a Stop hook", case.run(stop_hook_active=True))
    check_silent("silent in a headless claude -p child",
                 case.run(environment_extra={"CLAUDE_CODE_SESSION_ATTENDED": "0"}))
    check_silent("silent in a child whose caller owns its session",
                 case.run(environment_extra={"NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER": "x"}))
    closed = Case(minutes="#next_to_present none, closed")
    closed.reply("Should I merge the pull request now?")
    check_silent("silent when no approval-walk is open", closed.run())
    unreadable = Case(minutes="#next_to_present item 7 of 10")
    unreadable.reply("Should I merge the pull request now?")
    check_silent("silent when the walk-document has no heading for the waiting item", unreadable.run())
    old_marker = Case(minutes="Next to present: item 2 of 10")
    old_marker.reply("Should I merge the pull request now?")
    check_silent("silent when the minutes carry only the old marker", old_marker.run())
    check("no silent case is logged", case.logged() == [] and closed.logged() == [], case.logged())


def test_the_refusal_log():
    case = Case()
    case.reply("Should I merge the pull request now?")
    case.log.mkdir()
    check_blocked("a refusal that cannot be logged still blocks and says it was not logged", case.run(),
                  "This refusal was not logged, because", str(case.log))
    homes = SUITE_ROOT / "log-store-homes"
    (homes / "mac-mount" / hook.LOG_STORE_DIRECTORY_NAME).mkdir(parents=True)
    path, problem = hook.log_path({}, [str(homes / "ned-box-home"), str(homes / "mac-mount")])
    check("the log-store is reached through the Mac's mount when ned-box's path is missing",
          (path, problem) == (homes / "mac-mount" / hook.LOG_STORE_DIRECTORY_NAME / hook.LOG_FILE_NAME, None),
          (path, problem))
    path, problem = hook.log_path({}, [str(homes / "ned-box-home"), str(homes / "nowhere")])
    check("an unreachable log-store is reported", path is None and "reachable at neither" in problem, problem)
    path, _ = hook.log_path({})
    check("by default the log-store is the one under ned-box's home or the Mac's mount",
          path is None or path.name == hook.LOG_FILE_NAME and path.parent.name == "nedschorus-logs", path)


def test_which_line_is_flagged_and_how_lines_are_joined():
    case = Case()
    case.reply("Should I merge it now?\n\nShould I also tag it?")
    check_blocked("of two clear questions, the first is flagged", case.run(), '"Should I merge it now?"')
    case.reply("I recommend merging it.\n\nI recommend tagging it too.")
    check_blocked("after a failed model check, the first unclear line is flagged", case.run(model="fail"),
                  '"I recommend merging it."')
    case.reply("Still waiting for you:\n- the cleanup of the old directories;\n- the naming change.\n\nDone.")
    case.run(model="no")
    calls = case.model_calls()
    check("a list is judged with the line ending in `:` that introduces it",
          calls and "1. Still waiting for you: - the cleanup of the old directories; - the naming change.\n"
          in calls[-1]["stdin"] + "\n" and "2." not in calls[-1]["stdin"].split("The numbered lines:")[1], calls)
    case.reply("Should I run one of these:\n- `delete-all.py`\n- **keep.py**")
    check_blocked("a flagged list is named as written, line by line, marks included", case.run(),
                  '"Should I run one of these:\n- `delete-all.py`\n- **keep.py**"')
    case.reply("Should I merge the café page now?")
    case.run()
    check("the log keeps a sentence's letters as written", "café" in case.log.read_text(encoding="utf-8"),
          case.log.read_text(encoding="utf-8"))


def test_two_waiting_items():
    case = Case(minutes="#next_to_present items 2 and 3 of 10")
    case.reply("Should I merge the pull request now?")
    check_blocked("with two items waiting, the interruption item follows the later one and both are named",
                  case.run(), "`## Item 3.1 of 11: <the point of the question>`, placed right after item 3.",
                  "which then reads `#next_to_present items 2 and 3 of 11`",
                  "and then each waiting item's closing line, on a line of its own, as the walk-me-through skill "
                  f"writes it, as the last text of that message:\n`[Item 2 of 11, where the poem page lives](<page link>) · "
                  f"{CLOSING_LINE_ANSWER_LETTERS}`\n`[Item 3 of 11, the hook](<page link>) · "
                  f"{CLOSING_LINE_ANSWER_LETTERS}`\nThe minutes record no `#item_page` line for items 2 and 3. For each such item")
    mixed = Case(minutes="#item_page item 3 of 10 https://claude.ai/artifact/p3\n#next_to_present items 2 and 3 of 10")
    mixed.reply("Should I merge the pull request now?")
    check_blocked("with two items waiting and a page for one, each gets its own form of the closing line",
                  mixed.run(), f"`[Item 2 of 11, where the poem page lives](<page link>) · {CLOSING_LINE_ANSWER_LETTERS}`\n"
                  f"`[Item 3 of 11, the hook](https://claude.ai/artifact/p3) · {CLOSING_LINE_ANSWER_LETTERS}`\n"
                  "The minutes record no `#item_page` line for item 2. For each such item")


def test_only_a_reminder_of_the_open_walks_waiting_items_is_skipped():
    case = Case()
    for case_name, reminder in (
            ("a reminder with another total is checked", "Item 2 of 200 is waiting for your answer."),
            ("a reminder of an item that is not waiting is checked", "Item 99 of 10 is waiting for your answer."),
            ("a reminder whose range runs backwards is checked", "Items 3 to 2 of 10 are waiting for your answer.")):
        case.reply("PR 1922 merged.\n\n" + reminder)
        check_blocked(case_name, case.run(model="yes"), f'"{reminder}"')
    two_waiting = Case(minutes="#next_to_present items 2 and 3 of 10")
    two_waiting.reply("PR 1922 merged.\n\nItem 2 of 10 is waiting for your answer.")
    check_silent("a reminder of one of two waiting items is skipped", two_waiting.run(model="yes"))


def closing_line(count, point="the poem page is recommended for the wiki"):
    label = f"Item {count}, {point}" if point else f"Item {count}"
    return f"[{label}](https://claude.ai/artifact/x) · {CLOSING_LINE_ANSWER_LETTERS}"


def test_only_the_waiting_items_closing_line_is_skipped():
    case = Case()
    for case_name, text in (
            ("the waiting item's closing line after an event note passes, though its point differs from the "
             "heading's and holds `recommended`", "PR 1922 merged.\n\n" + closing_line("2 of 10")),
            ("the waiting item's closing line after the item shown in full passes",
             ITEM_2_SHOWN + "\n\n" + closing_line("2 of 10")),
            ("a closing line without a point passes", closing_line("2 of 10", point=None))):
        case.reply(text)
        check_silent(case_name, case.run(model="yes"))
    check("a waiting item's closing line never reaches the model", case.model_calls() == [], case.model_calls())
    for case_name, line in (
            ("a closing line naming an item that is not waiting is checked", closing_line("3 of 10")),
            ("a closing line with a larger total is checked", closing_line("2 of 11")),
            ("a closing line with a smaller total is checked", closing_line("2 of 1")),
            ("a closing line with text after its answer letters is checked", closing_line("2 of 10") + " Agree?"),
            ("a closing line with text before it on its line is checked", "Recommended: " + closing_line("2 of 10")),
            ("a closing line missing an answer letter is checked",
             closing_line("2 of 10").replace(" · O other options", ""))):
        case.reply("PR 1922 merged.\n\n" + line)
        check_blocked(case_name, case.run(model="yes"), "approval-walk question check")
    two_waiting = Case(minutes="#next_to_present items 2 and 3 of 10")
    two_waiting.reply(closing_line("2 of 10") + "\n\n" + closing_line("3 of 10"))
    check_silent("the closing line of each of two waiting items passes", two_waiting.run(model="yes"))


def test_a_closing_line_passes_only_as_one_link_followed_by_the_answer_letters():
    case = Case()
    point = "the *poem* page in `docs/` is recommended"
    case.reply(f"[Item 2 of 10, {point}](https://claude.ai/artifact/x) · {CLOSING_LINE_ANSWER_LETTERS}")
    check_silent("a closing line whose point holds emphasis and a code span passes", case.run(model="yes"))
    case.reply(closing_line("2 of 10").replace("https://claude.ai/artifact/x", "file:///Volumes/nedhome/x/walk.md"))
    check_silent("a closing line whose link is a file:// link passes", case.run(model="yes"))
    case.reply(closing_line("2 of 10", point="the page recommended for `docs/`"))
    check_silent("a closing line whose point ends in a code span passes", case.run(model="yes"))
    letters = f" · {CLOSING_LINE_ANSWER_LETTERS}"
    for case_name, line in (
            ("a question between the link and the answer letters is checked",
             f"[Item 2 of 10, x](https://claude.ai/artifact/x) Should I also merge PR 9?{letters}"),
            ("a closing line without its link is checked",
             f"Item 2 of 10, the poem page is recommended for the wiki{letters}"),
            ("a closing line with its label in brackets but no link target is checked",
             f"[Item 2 of 10, the poem page is recommended for the wiki]{letters}"),
            ("a closing line written as a list item is checked", "- " + closing_line("2 of 10")),
            ("a closing line in bold marks is checked", f"**{closing_line('2 of 10')}**"),
            ("a closing line whose label opens with bold marks is checked",
             closing_line("2 of 10").replace("[Item 2 of 10,", "[**Item 2 of 10**,")),
            ("a closing line whose label opens with a code span is checked",
             closing_line("2 of 10").replace("[Item 2 of 10,", "[`Item 2 of 10`,")),
            ("an italic count and point followed by an empty link is checked",
             f"*Item 2 of 10, the poem page is recommended*[](https://claude.ai/artifact/x){letters}"),
            ("a bold count and point followed by an empty link is checked",
             f"**Item 2 of 10, the poem page is recommended**[](https://claude.ai/artifact/x){letters}"),
            ("a closing line whose label does not open with `Item` in capitals is checked",
             closing_line("2 of 10").replace("[Item", "[item")),
            ("a closing line whose label puts no comma after the count is checked",
             closing_line("2 of 10").replace("2 of 10,", "2 of 10:")),
            ("the closing line's link alone is checked",
             "[Item 2 of 10, the poem page is recommended for the wiki](https://claude.ai/artifact/x)"),
            ("a closing line whose answer letters are a code span is checked",
             f"[Item 2 of 10, the poem page is recommended for the wiki](https://claude.ai/artifact/x)`{letters}`"),
            ("a closing line with emphasis right after its answer letters is checked",
             closing_line("2 of 10") + "*really*"),
            ("a closing line with a second link after the answer letters is checked",
             closing_line("2 of 10") + " [why](https://claude.ai/artifact/y)")):
        case.reply("PR 1922 merged.\n\n" + line)
        check_blocked(case_name, case.run(model="yes"), "approval-walk question check")


def test_the_answer_hooks_closing_line_for_a_point_with_brackets_passes():
    document = WALK_DOCUMENT.replace("## Item 2 of 10: where the poem page lives",
                                     "## Item 2 of 10: the [advisor] check is recommended for the poem page")
    case = Case(document=document,
                minutes="#item_page item 2 of 10 https://claude.ai/artifact/p2\n#next_to_present item 2 of 10")
    line = hook.answer_hook.closing_line("2", hook.answer_hook.read_walk(case.checkout))
    check("the answer hook escapes the point's brackets in its closing line",
          line is not None and line.startswith("[Item 2 of 10, the \\[advisor\\] check"), line)
    case.reply("PR 1922 merged.\n\n" + str(line))
    check_silent("the answer hook's closing line for a point holding brackets passes", case.run(model="yes"))
    case.reply("PR 1922 merged.\n\n" + str(line).replace("\\[", "[").replace("\\]", "]"))
    check_silent("the closing line for a point holding unescaped brackets passes", case.run(model="yes"))
    check("a closing line whose point holds brackets never reaches the model", case.model_calls() == [],
          case.model_calls())


def test_the_refusal_gives_the_waiting_items_closing_line_and_it_passes_once_the_steps_are_done():
    case = Case(minutes="#item_page item 2 of 10 https://claude.ai/artifact/p2\n#next_to_present item 2 of 10")
    case.reply("Should I merge the pull request now?")
    reason = blocked_reason(case.run()) or ""
    expected = (f"`[Item 2 of 11, where the poem page lives](https://claude.ai/artifact/p2) · "
                f"{CLOSING_LINE_ANSWER_LETTERS}`")
    check("the refusal gives the waiting item's closing line with its page link and the new total",
          reason.endswith(f"as the last text of that message:\n{expected}\n" + hook.REFUSAL_INSTRUCTIONS[-2]
                          + "\n" + hook.REFUSAL_INSTRUCTIONS[-1]), reason)
    done = Case(document=WALK_DOCUMENT.replace("of 10", "of 11") + "\n"
                + INTERRUPTION_ITEM.replace("merge-lane-2 asks: should I file one GHI listing the remaining seats' "
                                            "tests?", "Should I merge the pull request now?"),
                minutes="#item_page item 2 of 10 https://claude.ai/artifact/p2\n#next_to_present item 2 of 11")
    done.reply("Should I merge the pull request now?\n\nI added the question as Item 2.1 of 11.\n\n" + expected[1:-1])
    check_silent("the reply the refusal's step 4 asks for passes once steps 1 and 2 are done", done.run(model="yes"))


def test_the_closing_line_and_the_item_ending_are_the_walk_skills():
    skill = (Path(__file__).resolve().parents[4] / ".claude" / "skills" / "walk-me-through" / "SKILL.md").read_text()
    example = next((line for line in skill.split("\n") if line.startswith("[Item 4 of 9, <the point>](<page link>)")),
                   None)
    check("SKILL.md holds the closing line's form, `[Item 4 of 9, <the point>](<page link>) · ...`, on a line of its "
          "own", example is not None, "no such line")
    case = Case()
    case.reply("PR 1922 merged.\n\n" + str(example).replace("4 of 9", "2 of 10").replace(
        "<the point>", "the poem page is recommended for the wiki").replace("<page link>", "https://claude.ai/artifact/x"))
    check_silent("SKILL.md's closing line, filled in for the waiting item, passes", case.run(model="yes"))
    ending = "end it with the recommendation stated as an action"
    check("refusal step 1 ends the new item as SKILL.md's section \"Each item\" says",
          ending in skill and ending in hook.REFUSAL_INSTRUCTIONS[1], hook.REFUSAL_INSTRUCTIONS[1])
    check("refusal step 1 and SKILL.md's section \"Each item\" both open the alternative with \"The alternative:\"",
          "as in `The alternative: " in hook.REFUSAL_INSTRUCTIONS[1]
          and "State the alternative just before the recommendation, as in \"The alternative: " in skill,
          hook.REFUSAL_INSTRUCTIONS[1])
    check("SKILL.md's Style paragraph puts the strongest case against just before the alternative, where \"Each item\" "
          "puts the alternative", "Just before the alternative, state the strongest case against the recommendation"
          in skill)


SUB_STEP_2_1_NO_DECISION_CLOSING_LINE = "[No decision here; type N or next to continue.](https://claude.ai/artifact/p21)"


def test_a_no_decision_sub_steps_line_is_skipped_only_while_a_sub_step_waits():
    sub_step = Case(document=WALK_DOCUMENT.replace("of 10", "of 11") + "\n" + INTERRUPTION_ITEM,
                    minutes="#next_to_present item 2.1 of 11")
    sub_step.reply("PR 1922 merged.\n\n" + SUB_STEP_2_1_NO_DECISION_CLOSING_LINE)
    check_silent("the no-decision line passes while a sub-step waits", sub_step.run(model="yes"))
    check("the no-decision line never reaches the model", sub_step.model_calls() == [], sub_step.model_calls())
    sub_step.reply("PR 1922 merged.\n\n" + SUB_STEP_2_1_NO_DECISION_CLOSING_LINE + " Agree?")
    check_blocked("the no-decision line with text after it is checked", sub_step.run(model="yes"),
                  "approval-walk question check")
    whole_item = Case()
    whole_item.reply("PR 1922 merged.\n\n" + SUB_STEP_2_1_NO_DECISION_CLOSING_LINE)
    check_blocked("the no-decision line is checked while a whole item waits", whole_item.run(model="yes"),
                  "approval-walk question check")


PUBLISH_FAILED_LINE = "#item_page item {number} of {total} publish failed: the Artifact tool timed out"
RECOMMENDED_ITEM_2_DOCUMENT = WALK_DOCUMENT.replace("## Item 2 of 10: where the poem page lives",
                                                    "## Item 2 of 10: the poem page is recommended for the wiki")


def test_the_closing_line_without_its_link_is_skipped_only_for_an_item_whose_publish_failed():
    failed = Case(document=RECOMMENDED_ITEM_2_DOCUMENT,
                  minutes=PUBLISH_FAILED_LINE.format(number=2, total=10) + "\n#next_to_present item 2 of 10")
    line = hook.answer_hook.closing_line("2", hook.answer_hook.read_walk(failed.checkout))
    check("the answer hook's closing line for an item whose publish failed has no link",
          line == f"Item 2 of 10, the poem page is recommended for the wiki · {CLOSING_LINE_ANSWER_LETTERS}", line)
    failed.reply("Recorded.\n\n" + str(line))
    check_silent("the closing line without its link passes for an item whose newest publish failed",
                 failed.run(model="yes"))
    check("the closing line without its link of an item whose publish failed never reaches the model",
          failed.model_calls() == [], failed.model_calls())
    republished = Case(document=RECOMMENDED_ITEM_2_DOCUMENT,
                       minutes=PUBLISH_FAILED_LINE.format(number=2, total=10)
                       + "\n#item_page item 2 of 10 https://claude.ai/artifact/p2\n#next_to_present item 2 of 10")
    republished.reply("Recorded.\n\n" + str(line))
    check_blocked("the closing line without its link is checked once a later `#item_page` line gives the item a page",
                  republished.run(model="yes"), "approval-walk question check")
    two_waiting = Case(document=RECOMMENDED_ITEM_2_DOCUMENT,
                       minutes=PUBLISH_FAILED_LINE.format(number=2, total=10) + "\n#next_to_present items 2 and 3 of 10")
    two_waiting.reply("Recorded.\n\n" + str(line) + "\n\n"
                      + f"Item 3 of 10, the hook is recommended · {CLOSING_LINE_ANSWER_LETTERS}")
    check_blocked("the closing line without its link is checked for a waiting item whose publish did not fail",
                  two_waiting.run(model="yes"), "approval-walk question check", "Item 3 of 10, the hook")


def test_the_no_decision_line_without_its_link_is_skipped_only_for_a_sub_step_whose_publish_failed():
    bare = "No decision here; type N or next to continue."
    document = WALK_DOCUMENT.replace("of 10", "of 11") + "\n" + INTERRUPTION_ITEM
    failed = Case(document=document,
                  minutes=PUBLISH_FAILED_LINE.format(number="2.1", total=11) + "\n#next_to_present item 2.1 of 11")
    failed.reply("PR 1922 merged.\n\n" + bare)
    check_silent("the no-decision line without its link passes for a sub-step whose newest publish failed",
                 failed.run(model="yes"))
    published = Case(document=document,
                     minutes="#item_page item 2.1 of 11 https://claude.ai/artifact/p21\n#next_to_present item 2.1 of 11")
    published.reply("PR 1922 merged.\n\n" + bare)
    check_blocked("the no-decision line without its link is checked for a sub-step that has a page",
                  published.run(model="yes"), "approval-walk question check")
    whole_item = Case(minutes=PUBLISH_FAILED_LINE.format(number=2, total=10) + "\n#next_to_present item 2 of 10")
    whole_item.reply("PR 1922 merged.\n\n" + bare)
    check_blocked("the no-decision line without its link is checked while a whole item whose publish failed waits",
                  whole_item.run(model="yes"), "approval-walk question check")


def test_a_fault_exits_1_and_names_it():
    case = Case()
    result = case.run(stdin_text="not json")
    check("input that is not JSON exits 1 and names the fault on stderr",
          result.returncode == 1 and result.stdout == "" and result.stderr.startswith(
              "walk-me-through-agent-question-to-user-outside-approval-walk-items-refusal-stop-hook: the hook failed")
          and "JSONDecodeError" in result.stderr and "Traceback" not in result.stderr,
          f"exit {result.returncode}, stderr {result.stderr!r}")


def main():
    FAKE_BIN.mkdir(parents=True)
    fake = FAKE_BIN / "claude"
    fake.write_text(FAKE_CLAUDE.replace("#!/usr/bin/env python3", f"#!{sys.executable}", 1))
    fake.chmod(0o755)
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
