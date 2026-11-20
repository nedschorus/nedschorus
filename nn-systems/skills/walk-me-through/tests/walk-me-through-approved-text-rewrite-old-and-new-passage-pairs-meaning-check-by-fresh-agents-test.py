#!/usr/bin/env python3
"""Check the meaning check's sentence split, pairing, answer parsing, kept answers and failures.

The parsing and pairing cases call the program's functions. The end-to-end
cases run the program with a fake `claude` first on PATH, which logs each
prompt it is given and answers from a list of (text in the prompt, answer,
exit code) that the case writes; no case runs a model.

Run: python3 nn-systems/skills/walk-me-through/tests/walk-me-through-approved-text-rewrite-old-and-new-passage-pairs-meaning-check-by-fresh-agents-test.py
Prints one line per failing case and exits non-zero if any case fails.
"""

import contextlib
import hashlib
import io
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
PROGRAM = (Path(__file__).resolve().parents[1]
           / "walk-me-through-approved-text-rewrite-old-and-new-passage-pairs-meaning-check-by-fresh-agents.py")
_spec = importlib.util.spec_from_file_location("meaning_check", PROGRAM)
meaning_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(meaning_check)
CONTROL_VARIABLE = "MEANING_CHECK_TEST_CONTROL_DIRECTORY"
failures = []

FAKE_CLAUDE = f"""#!{sys.executable}
import json, os, pathlib, sys
control = pathlib.Path(os.environ[{CONTROL_VARIABLE!r}])
prompt = sys.stdin.read()
with (control / "calls.jsonl").open("a", encoding="utf-8") as log:
    log.write(json.dumps({{"argv": sys.argv[1:], "stdin": prompt}}) + "\\n")
for text, answer, code in json.loads((control / "answers.json").read_text(encoding="utf-8")):
    if text in prompt:
        sys.stdout.write(answer)
        sys.exit(code)
sys.stderr.write("fake claude: no answer for this prompt")
sys.exit(3)
"""


def check(name, condition, detail=""):
    if not condition:
        failures.append(name)
        print(f"FAIL {name}: {detail}")


def raises_value_error(function, *arguments):
    try:
        function(*arguments)
    except ValueError as error:
        return str(error)
    return None


class Case:
    def __init__(self, old, new, answers):
        self.directory = Path(tempfile.mkdtemp(prefix="meaning-check-test-"))
        (self.directory / "bin").mkdir()
        fake = self.directory / "bin" / "claude"
        fake.write_text(FAKE_CLAUDE)
        fake.chmod(0o755)
        (self.directory / "old.md").write_text(old)
        (self.directory / "new.md").write_text(new)
        self.set_answers(answers)

    def set_answers(self, answers):
        (self.directory / "answers.json").write_text(json.dumps(answers))

    def run(self, *extra, path=None):
        environment = {**os.environ, CONTROL_VARIABLE: str(self.directory),
                       "PATH": path if path is not None else f"{self.directory / 'bin'}:{os.environ['PATH']}"}
        return subprocess.run([sys.executable, str(PROGRAM), "--old", str(self.directory / "old.md"),
                               "--new", str(self.directory / "new.md"),
                               "--output-directory", str(self.directory / "out"), *extra],
                              capture_output=True, text=True, env=environment, timeout=120)

    def calls(self):
        log = self.directory / "calls.jsonl"
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    def output(self, name):
        path = self.directory / "out" / name
        return path.read_text() if path.exists() else None


def test_sentences():
    check("a line splits after a full stop followed by a capital",
          meaning_check.sentences_of_line("Run the tests. Then  push.") == ["Run the tests.", "Then push."],
          meaning_check.sentences_of_line("Run the tests. Then  push."))
    check("no split inside backticks or double quotes",
          meaning_check.sentences_of_line('Run `a. B` and say "x. Y" now. Done.')
          == ['Run `a. B` and say "x. Y" now.', "Done."])
    check("no split before a lower-case word", meaning_check.sentences_of_line("kinds: 1. text") == ["kinds: 1. text"])
    text = "# Title\n\nOne. Two.\n\n```\ncode. Here.\n```\n| a | b |\n|---|---|\n- Item.\n---\n"
    check("headings, fences, fence contents, table separators and rules are not sentences",
          meaning_check.sentences_of_markdown(text) == ["One.", "Two.", "| a | b |", "Item."],
          meaning_check.sentences_of_markdown(text))


def test_pairs():
    old = ["Keep this.", "Run the check program before every push to main.",
           "Always run the check program before you push to main.", "Delete the cache file nightly."]
    new = ["Keep this.", "Run the check program before every push to main, always.", "Ship the walk files at the close."]
    pairs, unchanged = meaning_check.pair_changed_sentences_of_old_and_new_text_by_word_overlap(old, new)
    check("an unchanged sentence is set aside", unchanged == 1 and all("Keep this." not in p["old"] for p in pairs))
    merged = [p for p in pairs if len(p["old"]) == 2]
    check("two old repeats and their one replacement form one pair",
          len(merged) == 1 and merged[0]["new"] == ["Run the check program before every push to main, always."], pairs)
    check("an old sentence joined to nothing is a dropped pair",
          {"id": "P2", "old": ["Delete the cache file nightly."], "new": []} in pairs, pairs)
    check("a new sentence joined to nothing is an added pair, listed after the old ones",
          pairs[-1]["old"] == [] and pairs[-1]["new"] == ["Ship the walk files at the close."], pairs)
    check("a pair's status names it changed, dropped or added",
          [meaning_check.classify_old_and_new_sentence_pair_as_changed_dropped_or_added(p) for p in pairs] == ["changed", "dropped", "added"])
    check("no pairs and no shared words do not divide by zero",
          meaning_check.pair_changed_sentences_of_old_and_new_text_by_word_overlap([], []) == ([], 0)
          and meaning_check.similarity(set(), {"x"}, {"x": 1.0}) == 0.0)


def test_rule_list_parsing():
    check("numbered rules parse", meaning_check.parse_rule_list("R1: a\n\nR2: b\n") == ["a", "b"])
    check("NONE is an empty list", meaning_check.parse_rule_list("NONE\n") == [])
    check("a rule out of order is refused", "R2" in (raises_value_error(meaning_check.parse_rule_list, "R1: a\nR3: b") or ""))
    check("a line in another form is refused", raises_value_error(meaning_check.parse_rule_list, "Here are the rules:\nR1: a"))
    check("an empty answer is refused", raises_value_error(meaning_check.parse_rule_list, "  \n"))


def test_rule_match_parsing():
    parse = meaning_check.parse_fresh_agent_answer_matching_rules_of_old_and_new_rule_lists
    check("every answer form parses, preamble and backticks ignored",
          parse("Answers:\nA1 -> B2, B1\n`A2 -> none`\nB1 -> A1\nB2 -> held.\n", 2, 2)
          == {"A1": ["B2", "B1"], "A2": "none", "B1": ["A1"], "B2": "held"})
    check("a missing rule is refused", "B1" in (raises_value_error(parse, "A1 -> none", 1, 1) or ""))
    check("a rule answered twice is refused", "twice" in (raises_value_error(parse, "A1 -> B1\nA1 -> none\nB1 -> A1", 1, 1) or ""))
    check("a rule not in its list is refused", "A2 is not" in (raises_value_error(parse, "A2 -> none\nA1 -> B1\nB1 -> A1", 1, 1) or ""))
    check("a target not in the other list is refused", "B3" in (raises_value_error(parse, "A1 -> B3\nB1 -> A1", 1, 1) or ""))
    check("a target in the same list is refused", raises_value_error(parse, "A1 -> A1\nB1 -> A1", 1, 1))
    check("a malformed answer line is refused", raises_value_error(parse, "A1 -> maybe\nB1 -> A1", 1, 1))


def test_whole_document_parsing():
    parse = meaning_check.parse_fresh_agent_answer_naming_whole_document_sentence_that_holds_each_rule
    document = "First rule here.\nThe `second` rule  is this."
    check("a quote found word for word is kept, white space aside, and none is None",
          parse('X1 -> held: "The `second` rule is this."\nX2 -> none', 2, document)
          == {1: "The `second` rule is this.", 2: None})
    check("a quote the document lacks counts as not held",
          parse('X1 -> held: "A rule nobody wrote."', 1, document) == {1: None})
    conditioned = "Intro line.\nRun the check program before every push to main. Then rest."
    check("a fragment of a sentence that leaves out its condition counts as not held",
          parse('X1 -> held: "Run the check program"', 1, conditioned) == {1: None})
    check("the whole sentence, from a line of several, is kept",
          parse('X1 -> held: "Run the check program before every push to main."', 1, conditioned)
          == {1: "Run the check program before every push to main."})
    listed = "- Do the first thing. Then stop.\n  * Nested rule.\n12. Numbered rule.\n> - Quoted item."
    check("a quote of a list or block-quote item is kept with or without its marker",
          parse('X1 -> held: "Do the first thing."\nX2 -> held: "Nested rule."\nX3 -> held: "12. Numbered rule."\n'
                'X4 -> held: "Quoted item."', 4, listed)
          == {1: "Do the first thing.", 2: "Nested rule.", 3: "12. Numbered rule.", 4: "Quoted item."})
    check("a fragment of a list item still counts as not held",
          parse('X1 -> held: "Do the first"', 1, listed) == {1: None})
    check("a missing rule is refused", raises_value_error(parse, "X1 -> none", 2, document))
    check("a rule answered twice is refused", raises_value_error(parse, "X1 -> none\nX1 -> none", 1, document))
    check("a rule out of range is refused", raises_value_error(parse, "X2 -> none", 1, document))
    check("a malformed line is refused", raises_value_error(parse, "X1 -> probably", 1, document))


OLD = "# T\n\nRun the check program before every push to main.\n\nDelete the cache file nightly.\n"
NEW = "# T\n\nRun the check program before each push.\n"
LISTING = "You are listing what one passage"
MATCHING = "Two passages of an agent's instruction file"
WHOLE = "Below are an agent's instruction file"


def listing_answers():
    return [
        ["Run the check program before every push to main.\n>>>",
         "R1: Run the check program before a push.\nR2: Only a push to main needs it.\n", 0],
        ["Run the check program before each push.\n>>>", "R1: Run the check program before every push.\n", 0],
        ["Delete the cache file nightly.\n>>>", "R1: Delete the cache file every night.\n", 0],
    ]


def test_end_to_end():
    whole_none = [[WHOLE, "X1 -> none\n", 0]]
    matching = [[MATCHING, "A1 -> B1\nA2 -> none\nB1 -> A1\n", 0]]
    case = Case(OLD, NEW, matching + whole_none + listing_answers())
    result = case.run()
    table = case.output(meaning_check.TABLE_FILE_NAME) or ""
    items = case.output(meaning_check.MARKED_PAIRS_AS_APPROVAL_WALK_ITEMS_FILE_NAME) or ""
    check("a rule only one side holds marks its pair, exit 5", result.returncode == 5, result.stderr + result.stdout)
    check("the table lists the changed pair and the dropped pair with the rules lost",
          "Only a push to main needs it." in table and "| dropped" not in table and "Delete the cache file every night." in table,
          table)
    check("the items file holds one item per marked pair, with the slots for judgment",
          items.count("## <the point>") == 2 and "#case_against <rating>:" in items and "Recommendation: <...>" in items,
          items)
    calls = case.calls()
    check("every fresh-agent runs with no tools and hooks off", calls and all(
        c["argv"][c["argv"].index("--tools") + 1] == "" and "disableAllHooks" in c["argv"][c["argv"].index("--settings") + 1]
        for c in calls), calls)
    check("the fourth agent is given the whole other version", any(
        WHOLE in c["stdin"] and "Run the check program before each push." in c["stdin"] for c in calls))
    before = len(calls)
    again = case.run()
    check("a second invocation uses the kept answers and runs no model",
          again.returncode == 5 and len(case.calls()) == before, (again.returncode, len(case.calls()), before))

    held = Case(OLD, NEW, matching + [[WHOLE, 'X1 -> held: "Run the check program before each push."\n', 0]]
                + listing_answers())
    result = held.run()
    check("a rule the whole other version holds marks nothing, exit 0",
          result.returncode == 0 and "held by" in (held.output(meaning_check.TABLE_FILE_NAME) or ""),
          result.stderr + result.stdout + str(held.output(meaning_check.TABLE_FILE_NAME)))
    check("no marked pair leaves the items file empty", held.output(meaning_check.MARKED_PAIRS_AS_APPROVAL_WALK_ITEMS_FILE_NAME) == "")


def test_failures():
    for name, answer, code, said in (
            ("a fresh-agent that exits nonzero", "R1: x\n", 1,
             "a fresh-agent exited 1 with some answer.\nIts stderr: empty\nIts stdout: R1: x\n"),
            ("a fresh-agent that prints nothing", "", 0, "a fresh-agent exited 0 with no answer.\n"),
            ("a fresh-agent whose answer cannot be read", "Here you go: x", 0,
             "a fresh-agent's answer cannot be read: line 'Here you go: x' is not `R1: <the rule>`.\n"
             "Its answer:\nHere you go: x\nRun this again")):
        case = Case(OLD, NEW, [[LISTING, answer, code]])
        result = case.run()
        check(f"{name} stops the program, exit 4, with no table, saying what it got", result.returncode == 4
              and case.output(meaning_check.TABLE_FILE_NAME) is None and said in result.stderr, result.stderr)
        kept = list((case.directory / "out" / meaning_check.FRESH_AGENT_ANSWERS_DIRECTORY_NAME).glob("*.txt"))
        check(f"{name}: no answer is kept", kept == [], kept)
    case = Case(OLD, NEW, [])
    result = case.run(path="/nonexistent")
    check("a missing claude stops the program, exit 4", result.returncode == 4 and "could not run" in result.stderr,
          result.stderr)
    case = Case(OLD, NEW, [])
    (case.directory / "new.md").unlink()
    result = case.run()
    check("an unreadable input file is refused, exit 1", result.returncode == 1 and "cannot read" in result.stderr,
          result.stderr)
    case = Case(OLD, NEW, [])
    result = case.run("--pairs-only")
    check("--pairs-only writes the table and runs no model",
          result.returncode == 0 and case.calls() == [] and "| P1 |" in (case.output(meaning_check.TABLE_FILE_NAME) or ""),
          result.stderr)
    case = Case(OLD, NEW, listing_answers())
    answers = case.directory / "out" / meaning_check.FRESH_AGENT_ANSWERS_DIRECTORY_NAME
    answers.mkdir(parents=True)
    prompt = meaning_check.RULE_LISTING_PROMPT.format(passage="Delete the cache file nightly.")
    (answers / (hashlib.sha256(prompt.encode()).hexdigest()[:32] + ".txt")).write_text("garbled")
    case.set_answers([[MATCHING, "A1 -> B1\nA2 -> held\nB1 -> A1\n", 0], [WHOLE, "X1 -> none\n", 0]] + listing_answers())
    result = case.run()
    check("a kept answer that no longer parses is asked again", result.returncode == 5 and any(
        "Delete the cache file nightly.\n>>>" in c["stdin"] for c in case.calls()), result.stderr)


def refusal_of(function, *arguments):
    try:
        function(*arguments)
    except meaning_check.Refusal as refusal:
        return str(refusal), refusal.exit_code
    return "", None


def test_fresh_agent_failure_text_and_time_limit():
    case = Case(OLD, NEW, [])
    fake = case.directory / "bin" / "claude"
    fake.write_text(f"#!{sys.executable}\nimport sys, time\nsys.stdin.read()\n"
                    "if any('sleep' in a for a in sys.argv): time.sleep(5)\n"
                    "sys.stderr.write('x' * 100 + 'y' * 2000); sys.stdout.write('p' * 100 + 'q' * 2000); sys.exit(2)\n")
    saved_path, saved_settings, saved_timeout = (os.environ["PATH"], meaning_check.FRESH_AGENT_SETTINGS,
                                                 meaning_check.FRESH_AGENT_TIMEOUT_SECONDS)
    os.environ["PATH"] = f"{case.directory / 'bin'}:{saved_path}"
    try:
        message, code = refusal_of(meaning_check.run_fresh_agent, "prompt")
        check("a failed fresh-agent's message carries the last 2000 characters of its stderr and stdout, exit 4",
              code == 4 and f"Its stderr: {'y' * 2000}\n" in message and f"Its stdout: {'q' * 2000}\n" in message,
              (code, message[:200]))
        meaning_check.FRESH_AGENT_SETTINGS, meaning_check.FRESH_AGENT_TIMEOUT_SECONDS = {"sleep": 1}, 1
        message, code = refusal_of(meaning_check.run_fresh_agent, "prompt")
        check("a fresh-agent past its time limit stops the program, exit 4", code == 4 and "could not run" in message,
              (code, message))
        meaning_check.FRESH_AGENT_SETTINGS = saved_settings
        fake.write_text(f"#!{sys.executable}\nimport sys\nsys.stdin.read(); sys.stdout.write('z' * 100 + 'w' * 3000)\n")
        answers = case.directory / "answers-kept"
        answers.mkdir()
        message, code = refusal_of(meaning_check.parse_fresh_agent_answer_for_prompt_reusing_one_kept_on_disk_or_running_agent, answers, "prompt", meaning_check.parse_rule_list)
        check("an unreadable answer's message carries its last 3000 characters, exit 4",
              code == 4 and f"Its answer:\n{'w' * 3000}\n" in message, (code, message[-200:]))
    finally:
        os.environ["PATH"] = saved_path
        meaning_check.FRESH_AGENT_SETTINGS, meaning_check.FRESH_AGENT_TIMEOUT_SECONDS = saved_settings, saved_timeout


def test_program_defect_exits_2():
    original = meaning_check.run
    meaning_check.run = lambda arguments: 1 / 0
    try:
        with contextlib.redirect_stderr(io.StringIO()) as printed:
            code = meaning_check.main(["--old", "a", "--new", "b", "--output-directory", "c"])
    finally:
        meaning_check.run = original
    check("an unexpected exception is a program defect, exit 2", code == 2 and "program defect" in printed.getvalue(), code)


for test in (test_sentences, test_pairs, test_rule_list_parsing, test_rule_match_parsing, test_whole_document_parsing,
             test_end_to_end, test_failures, test_fresh_agent_failure_text_and_time_limit,
             test_program_defect_exits_2):
    test()
print(f"{'FAILED' if failures else 'passed'}: {len(failures)} failing case(s)")
sys.exit(1 if failures else 0)
