#!/usr/bin/env python3
"""Check that a rewrite of text the user approved keeps its meaning, pair by pair.

Given the old and the new version of a Markdown file, the program:

1. Splits each version into sentences: every non-blank line outside a code
   fence, split after `.`, `!` or `?` when a space and a capital letter, a
   quote, a backtick, a bracket or `*` follow, except inside backticks or
   double quotes. Headings, fence lines and table separator lines are not
   sentences. YAML front matter is read as lines too.
2. Sets aside every sentence whose text, with runs of white space made one
   space, is in both versions: it is unchanged, and no model reads it.
3. Pairs the rest. Each sentence is joined to the most similar sentence of
   the other version when their similarity reaches PAIR_SIMILARITY_THRESHOLD;
   similarity is the weight of the words the two share, divided by the weight
   of the shorter one's words, each word weighted by how rare it is in the
   two versions. The joined sentences form pairs by connected component, so
   three old repeats merged into one new sentence are one pair. An old
   sentence joined to nothing is a dropped pair, a new one an added pair.
4. For each pair, one fresh-agent lists the rules, conditions and limits of
   the old side, another those of the new side, each told only "the passage";
   a third is given both passages and both numbered lists and says, for each
   rule, which rule of the other list holds it, `held` when the other passage
   holds it without a line for it, or `none`. The program refuses an answer
   in which a rule is missing, answered twice or matched to a rule that does
   not exist. In a dropped or added pair, every rule of its one side is
   unmatched, without the third agent. A fourth fresh-agent is given the
   whole other version and the unmatched rules, and names for each the
   sentence of that version that holds it, or `none`; the program keeps a
   named sentence only when, white space aside, it is one whole sentence of
   the version as step 1 splits it, so a fragment that leaves out a condition
   does not count. A rule no
   sentence holds marks the pair; a pairing that put a rule's new wording in
   another pair thus marks nothing.
5. Writes `meaning-check-pairs-table.md`, every pair with its status and the
   rules only one side holds, and `marked-pairs-as-approval-walk-items.md`,
   one item per marked pair, with `<...>` slots for what needs judgment: the
   point, the case against, the alternative and the recommendation.

Every fresh-agent answer is kept in `fresh-agent-answers/` under the output
directory, named by a hash of what it was given, and used again on a later
invocation, so a rerun after a fix asks only about the passages that changed.

Does not handle: a sentence split inside an abbreviation such as "e.g. The";
a pair the similarity puts wrongly together or apart, which shows as a marked
pair whose rules the other version holds elsewhere: read every marked pair
before bringing it to the user; a change of meaning made by moving an
unchanged sentence to another section, which no pair shows; headings.
Failures: an unreadable input file is refused, exit 1. A fresh-agent that
exits nonzero, prints nothing or answers in a form the program cannot read
stops the program, exit 4, printing what it got; the answers already kept
are used again on the next invocation. No table is written unless every pair
has its answers. --pairs-only writes the table without running any model.

Usage:
  python3 nn-systems/skills/walk-me-through/walk-me-through-approved-text-rewrite-old-and-new-passage-pairs-meaning-check-by-fresh-agents.py \\
      --old OLD.md --new NEW.md --output-directory DIR [--pairs-only] [--jobs 8]

Exit 0: table written, no pair marked. 5: table and items written, some pair
marked. 1: refused. 4: a fresh-agent failed, nothing written but the kept
answers. 2: program defect.
"""

import argparse
import concurrent.futures
import hashlib
import json
import math
import re
import subprocess
import sys
import traceback
from pathlib import Path
import importlib.util

_command_line_prefix_spec = importlib.util.spec_from_file_location(
    "claude_code_headless_run_command_line_prefix_with_no_connectors_and_explicit_permission_mode_common",
    Path(__file__).resolve().parents[2] / "general-tools"
    / "claude-code-headless-run-command-line-prefix-with-no-connectors-and-explicit-permission-mode-common.py")
command_line_prefix = importlib.util.module_from_spec(_command_line_prefix_spec)
_command_line_prefix_spec.loader.exec_module(command_line_prefix)

PROGRAM = "walk-me-through-approved-text-rewrite-old-and-new-passage-pairs-meaning-check-by-fresh-agents"
# On a rewrite of the walk-me-through skill, 0.5 left 65 old sentences unpaired and 0.2 chained 14 into one pair.
PAIR_SIMILARITY_THRESHOLD = 0.3
# Pairs bigger than this are usually two passages chained by one shared word: read them before trusting the marks.
LARGE_PAIR_SENTENCE_COUNT = 10
# Listing and matching rules in a few sentences needs no tools or repository; a weaker model drops qualifiers.
FRESH_AGENT_MODEL = "claude-opus-5-5"
FRESH_AGENT_EFFORT = "medium"
FRESH_AGENT_SETTINGS = {"disableAllHooks": True}
FRESH_AGENT_TIMEOUT_SECONDS = 900
TABLE_FILE_NAME = "meaning-check-pairs-table.md"
MARKED_PAIRS_AS_APPROVAL_WALK_ITEMS_FILE_NAME = "marked-pairs-as-approval-walk-items.md"
FRESH_AGENT_ANSWERS_DIRECTORY_NAME = "fresh-agent-answers"

STOPWORDS = frozenset(
    "a an the and or but of to in on at by for with as is are be been was were it its this that these those "
    "then than so if when which who what each every any no not do does did you your he his him they their "
    "one there here from into only also all can may must".split())

RULE_LISTING_PROMPT = """You are listing what one passage of an agent's instruction file requires.

List every rule, condition, limit, exception, order of steps, and every file, command, marker or example the passage names, one per line, as `R<number>: <the rule>`, numbered from R1. Write each rule so that it can be read alone. Split a sentence that states two rules into two lines. Keep every word that narrows a rule, such as "only", "before", "every", "at most" or a number. List only what the passage says.

Write nothing but those lines. If the passage states no rule, write the one line `NONE`.

The passage:
<<<
{passage}
>>>
"""

RULE_MATCHING_PROMPT = """Two passages of an agent's instruction file are meant to say the same thing in different words. A separate reader listed the rules of each passage.

For each listed rule, decide whether the other passage holds it: states it, or states something that requires exactly the same, with every condition, limit and number. A rule the other passage states more weakly, more broadly, or without one of its conditions is not held.

Passage A:
<<<
{passage_a}
>>>

List A:
{list_a}

Passage B:
<<<
{passage_b}
>>>

List B:
{list_b}

Answer with one line for each rule of both lists, and nothing else. For each rule of list A: `A<n> -> B<m>`, naming the rule of list B that holds it, several as `A<n> -> B2, B5`; or `A<n> -> held` when passage B holds it but list B has no line for it; or `A<n> -> none` when passage B does not hold it. Then the same for each rule of list B: `B<n> -> A<m>`, `B<n> -> held` or `B<n> -> none`.
"""

RULE_WHOLE_DOCUMENT_PROMPT = """Below are an agent's instruction file and a numbered list of rules.

For each rule, decide whether the file holds it: states it, or states something that requires exactly the same, with every condition, limit and number. A rule the file states more weakly, more broadly, or without one of its conditions is not held.

The file:
<<<
{document}
>>>

The rules:
{rules}

Answer with one line for each rule, and nothing else: `X<n> -> held: "<the shortest whole sentence of the file that holds it, copied exactly>"`, or `X<n> -> none`.
"""


class Refusal(Exception):
    def __init__(self, message, exit_code=1):
        super().__init__(message)
        self.exit_code = exit_code


def normalized(text):
    return " ".join(text.split())


def sentences_of_line(line):
    """Split one line into sentences, never inside backticks or double quotes."""
    line = normalized(line)
    pieces, start, in_code, in_quote = [], 0, False, False
    for index, character in enumerate(line):
        if character == "`":
            in_code = not in_code
        elif character == '"' and not in_code:
            in_quote = not in_quote
        elif (character in ".!?" and not in_code and not in_quote and index + 2 < len(line)
              and line[index + 1] == " " and re.match(r"[A-Z\"`\[*(]", line[index + 2])):
            pieces.append(line[start:index + 1])
            start = index + 2
    pieces.append(line[start:])
    return [normalized(piece) for piece in pieces if piece.strip()]


LIST_OR_QUOTE_MARKERS = re.compile(r"^(?:(?:[-*+]|\d+[.)]|>)\s+)+")


def without_list_or_quote_markers(line):
    """Drop the leading `- `, `* `, `+ `, `1. `, `1) ` and `> ` markers, so a sentence quoted without its list marker still matches."""
    return LIST_OR_QUOTE_MARKERS.sub("", line.strip())


def sentences_of_markdown(text):
    sentences, in_fence = [], False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not stripped or stripped.startswith("#") or stripped == "---" or re.fullmatch(r"[|:\- ]+", stripped):
            continue
        sentences.extend(sentences_of_line(without_list_or_quote_markers(stripped)))
    return sentences


def words(sentence):
    return {word for word in re.findall(r"[a-z0-9#_][a-z0-9#_\-]*", sentence.lower()) if word not in STOPWORDS}


def similarity(first_words, second_words, weight):
    smaller = min(sum(weight[word] for word in first_words), sum(weight[word] for word in second_words))
    if not smaller:
        return 0.0
    return sum(weight[word] for word in first_words & second_words) / smaller


def pair_changed_sentences_of_old_and_new_text_by_word_overlap(old_sentences, new_sentences):
    """Return (pairs, unchanged count); each pair is {"id", "old": [...], "new": [...]} in old-text order."""
    old_set, new_set = set(old_sentences), set(new_sentences)
    old_changed = list(dict.fromkeys(s for s in old_sentences if s not in new_set))
    new_changed = list(dict.fromkeys(s for s in new_sentences if s not in old_set))
    unchanged = len(set(old_sentences) & new_set)
    nodes = [("old", s) for s in old_changed] + [("new", s) for s in new_changed]
    node_words = [words(sentence) for _, sentence in nodes]
    document_count = len(nodes) or 1
    frequency = {}
    for word_set in node_words:
        for word in word_set:
            frequency[word] = frequency.get(word, 0) + 1
    weight = {word: math.log(1 + document_count / count) for word, count in frequency.items()}
    parent = list(range(len(nodes)))

    def root(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    old_indexes = range(len(old_changed))
    new_indexes = range(len(old_changed), len(nodes))
    for own, other in ((old_indexes, new_indexes), (new_indexes, old_indexes)):
        for index in own:
            scored = [(similarity(node_words[index], node_words[candidate], weight), candidate) for candidate in other]
            if scored:
                best_score, best = max(scored)
                if best_score >= PAIR_SIMILARITY_THRESHOLD:
                    parent[root(index)] = root(best)
    groups = {}
    for index in range(len(nodes)):
        groups.setdefault(root(index), []).append(index)
    ordered = sorted(groups.values(), key=lambda members: (min(m for m in members) if any(
        m < len(old_changed) for m in members) else len(nodes) + min(members)))
    pairs = []
    for number, members in enumerate(ordered, 1):
        pairs.append({"id": f"P{number}",
                      "old": [nodes[m][1] for m in sorted(members) if nodes[m][0] == "old"],
                      "new": [nodes[m][1] for m in sorted(members) if nodes[m][0] == "new"]})
    return pairs, unchanged


def classify_old_and_new_sentence_pair_as_changed_dropped_or_added(pair):
    if pair["old"] and pair["new"]:
        return "changed"
    return "dropped" if pair["old"] else "added"


def parse_rule_list(answer):
    lines = [line.strip() for line in answer.strip().splitlines() if line.strip()]
    if lines == ["NONE"]:
        return []
    rules = []
    for line in lines:
        match = re.fullmatch(r"R(\d+):\s*(.+)", line)
        if not match or int(match.group(1)) != len(rules) + 1:
            raise ValueError(f"line {line!r} is not `R{len(rules) + 1}: <the rule>`")
        rules.append(match.group(2))
    if not rules:
        raise ValueError("no rule lines and no NONE")
    return rules


def parse_fresh_agent_answer_matching_rules_of_old_and_new_rule_lists(answer, count_a, count_b):
    """Return {"A1": "none" | "held" | ["B2", ...], ...}; every rule of both lists exactly once."""
    counts = {"A": count_a, "B": count_b}
    matches = {}
    for line in answer.strip().splitlines():
        line = line.strip().strip("`")
        if not re.match(r"[AB]\d+\s*->", line):
            continue
        match = re.fullmatch(r"([AB])(\d+)\s*->\s*(none|held|[AB]\d+(?:\s*,\s*[AB]\d+)*)\.?", line)
        if not match:
            raise ValueError(f"line {line!r} is not `<rule> -> <rule>`, `-> held` or `-> none`")
        side, number, target = match.group(1), int(match.group(2)), match.group(3)
        rule = f"{side}{number}"
        if not 1 <= number <= counts[side]:
            raise ValueError(f"{rule} is not a rule of list {side}")
        if rule in matches:
            raise ValueError(f"{rule} is answered twice")
        if target in ("none", "held"):
            matches[rule] = target
            continue
        other = "B" if side == "A" else "A"
        targets = [item.strip() for item in target.split(",")]
        for item in targets:
            if item[0] != other or not 1 <= int(item[1:]) <= counts[other]:
                raise ValueError(f"{rule} -> {item}: {item} is not a rule of list {other}")
        matches[rule] = targets
    missing = [f"{side}{n}" for side in "AB" for n in range(1, counts[side] + 1) if f"{side}{n}" not in matches]
    if missing:
        raise ValueError(f"no answer for {', '.join(missing)}")
    return matches


def parse_fresh_agent_answer_naming_whole_document_sentence_that_holds_each_rule(answer, count, document):
    """Return {n: quote or None}; a quote that is not one whole sentence of the document counts as None, so the rule stays marked."""
    holds = {}
    document_sentences = set(sentences_of_markdown(document))
    for line in answer.strip().splitlines():
        line = line.strip().strip("`")
        if not re.match(r"X\d+\s*->", line):
            continue
        match = re.fullmatch(r"X(\d+)\s*->\s*(?:held:\s*\"(.+)\"|none)\.?", line)
        if not match:
            raise ValueError(f"line {line!r} is not `X<n> -> held: \"<sentence>\"` or `X<n> -> none`")
        number = int(match.group(1))
        if not 1 <= number <= count:
            raise ValueError(f"X{number} is not a rule of the list")
        if number in holds:
            raise ValueError(f"X{number} is answered twice")
        quote = match.group(2)
        holds[number] = quote if quote and normalized(without_list_or_quote_markers(quote)) in document_sentences else None
    missing = [f"X{n}" for n in range(1, count + 1) if n not in holds]
    if missing:
        raise ValueError(f"no answer for {', '.join(missing)}")
    return holds


def rules_the_whole_document_holds(answers_directory, rules, document):
    """Return {rule: the sentence of document that holds it} for each of rules the whole document holds."""
    if not rules:
        return {}
    prompt = RULE_WHOLE_DOCUMENT_PROMPT.format(
        document=document, rules="\n".join(f"X{n}: {rule}" for n, rule in enumerate(rules, 1)))
    holds = parse_fresh_agent_answer_for_prompt_reusing_one_kept_on_disk_or_running_agent(answers_directory, prompt,
                               lambda answer: parse_fresh_agent_answer_naming_whole_document_sentence_that_holds_each_rule(answer, len(rules), document))
    return {rules[n - 1]: quote for n, quote in holds.items() if quote}


def run_fresh_agent(prompt):
    command = [*command_line_prefix.claude_code_headless_run_command_line_prefix_build(
                   "dontAsk", caller_claude_code_session_settings=FRESH_AGENT_SETTINGS),
               "--model", FRESH_AGENT_MODEL, "--effort", FRESH_AGENT_EFFORT, "--output-format", "text", "--tools", ""]
    try:
        # The prompt goes on stdin, so a passage starting with "-" is never read as a flag.
        result = subprocess.run(command, input=prompt, capture_output=True, text=True,
                                timeout=FRESH_AGENT_TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as failure:
        raise Refusal(f"a fresh-agent could not run: {failure}\n"
                      "If `claude` is missing or logged out on this machine: fix that, then run this again.", 4)
    if result.returncode or not result.stdout.strip():
        raise Refusal(f"a fresh-agent exited {result.returncode} with {'some' if result.stdout.strip() else 'no'} answer.\n"
                      f"Its stderr: {result.stderr.strip()[-2000:] or 'empty'}\n"
                      f"Its stdout: {result.stdout.strip()[-2000:] or 'empty'}\n"
                      "If it says `claude` is logged out or a usage limit is reached: tell the user what it said, then "
                      "run this again once it is fixed; the answers already kept are used again.\n"
                      "If you are a subagent: tell the agent that dispatched you what it said, instead of the user.", 4)
    return result.stdout


def parse_fresh_agent_answer_for_prompt_reusing_one_kept_on_disk_or_running_agent(answers_directory, prompt, parse):
    """Return parse(answer), reusing the answer kept for this exact prompt; keep a new one only once it parses."""
    path = answers_directory / (hashlib.sha256(prompt.encode()).hexdigest()[:32] + ".txt")
    if path.exists():
        try:
            return parse(path.read_text(encoding="utf-8"))
        except ValueError:
            path.unlink()
    answer = run_fresh_agent(prompt)
    try:
        parsed = parse(answer)
    except ValueError as defect:
        raise Refusal(f"a fresh-agent's answer cannot be read: {defect}.\nIts answer:\n{answer.strip()[-3000:]}\n"
                      "Run this again: only this prompt and the ones not yet answered run.", 4)
    path.write_text(answer, encoding="utf-8")
    return parsed


def numbered(rules, side):
    return "\n".join(f"{side}{n}: {rule}" for n, rule in enumerate(rules, 1)) or "(no rules)"


def check_pair(pair, answers_directory, old_document, new_document):
    old_text, new_text = " ".join(pair["old"]), " ".join(pair["new"])
    old_rules = parse_fresh_agent_answer_for_prompt_reusing_one_kept_on_disk_or_running_agent(answers_directory, RULE_LISTING_PROMPT.format(passage=old_text),
                                   parse_rule_list) if old_text else []
    new_rules = parse_fresh_agent_answer_for_prompt_reusing_one_kept_on_disk_or_running_agent(answers_directory, RULE_LISTING_PROMPT.format(passage=new_text),
                                   parse_rule_list) if new_text else []
    if old_text and new_text and old_rules and new_rules:
        prompt = RULE_MATCHING_PROMPT.format(passage_a=old_text, list_a=numbered(old_rules, "A"),
                                             passage_b=new_text, list_b=numbered(new_rules, "B"))
        matches = parse_fresh_agent_answer_for_prompt_reusing_one_kept_on_disk_or_running_agent(answers_directory, prompt,
                                     lambda answer: parse_fresh_agent_answer_matching_rules_of_old_and_new_rule_lists(answer, len(old_rules), len(new_rules)))
    else:
        matches = {**{f"A{n}": "none" for n in range(1, len(old_rules) + 1)},
                   **{f"B{n}": "none" for n in range(1, len(new_rules) + 1)}}
    unmatched_old = [rule for n, rule in enumerate(old_rules, 1) if matches[f"A{n}"] == "none"]
    unmatched_new = [rule for n, rule in enumerate(new_rules, 1) if matches[f"B{n}"] == "none"]
    held_elsewhere = {**rules_the_whole_document_holds(answers_directory, unmatched_old, new_document),
                      **rules_the_whole_document_holds(answers_directory, unmatched_new, old_document)}
    only_old = [rule for rule in unmatched_old if rule not in held_elsewhere]
    only_new = [rule for rule in unmatched_new if rule not in held_elsewhere]
    return {**pair, "old_rules": old_rules, "new_rules": new_rules, "only_old": only_old, "only_new": only_new,
            "held_elsewhere": held_elsewhere, "status": "marked" if only_old or only_new else "kept"}


def cell(text):
    return text.replace("|", "\\|") or " "


def table_text(old_path, new_path, results, unchanged):
    counts = {}
    for result in results:
        counts[result["status"]] = counts.get(result["status"], 0) + 1
    lines = [f"# Meaning check: {old_path} against {new_path}", "",
             f"{unchanged} sentences unchanged and not checked; {len(results)} pairs: "
             + ", ".join(f"{count} {status}" for status, count in sorted(counts.items())) + ".", "",
             "| Pair | Old text | New text | Status | Rules only the old text holds | Rules only the new text holds "
             "| Rules the other version holds elsewhere |",
             "|---|---|---|---|---|---|---|"]
    for result in results:
        size = len(result["old"]) + len(result["new"])
        status = result["status"] + (f" ({size} sentences: check the pairing)" if size > LARGE_PAIR_SENTENCE_COUNT else "")
        lines.append("| " + " | ".join([result["id"], cell(" ".join(result["old"])), cell(" ".join(result["new"])),
                                        status, cell("; ".join(result.get("only_old", []))),
                                        cell("; ".join(result.get("only_new", []))),
                                        cell("; ".join(f'{rule} (held by "{quote}")' for rule, quote
                                                       in result.get("held_elsewhere", {}).items()))]) + " |")
    return "\n".join(lines) + "\n"


def items_text(results):
    blocks = []
    for result in results:
        if result["status"] != "marked":
            continue
        lost = result["only_old"] + result["only_new"]
        blocks.append("\n".join([
            f"## <the point> ({result['id']}: {lost[0]})", "",
            "Old text: \"" + " ".join(result["old"]) + "\"" if result["old"] else "Old text: none.", "",
            "New text: \"" + " ".join(result["new"]) + "\"" if result["new"] else "New text: none.", "",
            "Only the old text holds: " + ("; ".join(result["only_old"]) or "nothing") + ".", "",
            "Only the new text holds: " + ("; ".join(result["only_new"]) or "nothing") + ".", "",
            "#case_against <rating>: <the strongest case against the recommendation>", "",
            "The alternative: <...>", "",
            "Recommendation: <...>"]))
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def run(arguments):
    try:
        old_text = Path(arguments.old).read_text(encoding="utf-8")
        new_text = Path(arguments.new).read_text(encoding="utf-8")
    except OSError as failure:
        raise Refusal(f"cannot read an input file: {failure}")
    output = Path(arguments.output_directory)
    answers_directory = output / FRESH_AGENT_ANSWERS_DIRECTORY_NAME
    answers_directory.mkdir(parents=True, exist_ok=True)
    pairs, unchanged = pair_changed_sentences_of_old_and_new_text_by_word_overlap(sentences_of_markdown(old_text), sentences_of_markdown(new_text))
    if arguments.pairs_only:
        results = [{**pair, "status": classify_old_and_new_sentence_pair_as_changed_dropped_or_added(pair)} for pair in pairs]
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=arguments.jobs) as pool:
            futures = [pool.submit(check_pair, pair, answers_directory, old_text, new_text) for pair in pairs]
            failures = []
            for future in futures:
                try:
                    future.result()
                except Refusal as failure:
                    failures.append(failure)
            if failures:
                raise Refusal("\n\n".join(str(failure) for failure in failures),
                              max(failure.exit_code for failure in failures))
            results = [future.result() for future in futures]
    (output / TABLE_FILE_NAME).write_text(table_text(arguments.old, arguments.new, results, unchanged), encoding="utf-8")
    marked = [result for result in results if result["status"] == "marked"]
    (output / MARKED_PAIRS_AS_APPROVAL_WALK_ITEMS_FILE_NAME).write_text(items_text(results), encoding="utf-8")
    print(f"{len(results)} pairs, {len(marked)} marked, {unchanged} sentences unchanged. "
          f"Table: {output / TABLE_FILE_NAME}. Items: {output / MARKED_PAIRS_AS_APPROVAL_WALK_ITEMS_FILE_NAME}.")
    if marked:
        print("Next: read each marked pair; restore the meaning where the new text lost it, run this again, and bring "
              "each pair still marked to the user as an approval-walk item, its `<...>` slots filled.")
        return 5
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog=PROGRAM, description=__doc__.split("\n")[0])
    parser.add_argument("--old", required=True)
    parser.add_argument("--new", required=True)
    parser.add_argument("--output-directory", required=True)
    parser.add_argument("--pairs-only", action="store_true", help="write the table of pairs without running a model")
    parser.add_argument("--jobs", type=int, default=8)
    arguments = parser.parse_args(argv)
    try:
        return run(arguments)
    except Refusal as refusal:
        print(f"{PROGRAM}: {refusal}", file=sys.stderr)
        return refusal.exit_code
    except Exception:
        traceback.print_exc()
        print(f"{PROGRAM}: program defect; the traceback above says where.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
