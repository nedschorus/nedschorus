#!/usr/bin/env python3
"""Tests for pull-request-description-defect-line-hashtags-reader-common.py.

Each case reads descriptions with the reader loaded from a path, or runs it as a
command at that path, so the mutation section can rerun the cases against a
mutated copy in a scratch directory: one mutation per rule, each of which must
turn its cases red. The file under test is never modified. Each mutation asserts
that its replacement text was found, and an unmutated copy is run after all
mutations as the control.

Run: python3 scripts/pull-request-description-defect-line-hashtags-reader-common-test.py
"""

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

READER = Path(__file__).with_name("pull-request-description-defect-line-hashtags-reader-common.py")
ISSUE = "https://github.com/nedschorus/nedschorus/issues/1154"
PULL_REQUEST = "https://github.com/nedschorus/nedschorus/pull/1636"

failures = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"\n      {detail}"))
    if not ok:
        failures.append(name)


def load(path):
    spec = importlib.util.spec_from_file_location("reader_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def kinds(reader, description):
    return [line["kind"] for line in reader.pull_request_description_defect_lines(description)]


def kinds_are(description, expected):
    def case(reader, _path):
        found = kinds(reader, description)
        return found == expected, f"read {found!r} from {description!r}"
    return case


def link_is(line, expected):
    def case(reader, _path):
        found = reader.pull_request_description_defect_lines(line)
        link = found[0]["link"] if found else "no defect line"
        return link == expected, f"read link {link!r} from {line!r}"
    return case


def case_line_kept_whole_without_its_carriage_return(reader, _path):
    found = reader.pull_request_description_defect_lines(
        "Fixes a hang.\r\n\r\n  - **#root_cause_not_fixed** it stays.\r\n#no_defect_fixed\r\n")
    expected = [{"kind": "root_cause_not_fixed", "line": "  - **#root_cause_not_fixed** it stays.",
                 "link": None},
                {"kind": "no_defect_fixed", "line": "#no_defect_fixed", "link": None}]
    return found == expected, f"read {found!r}"


def case_follow_up_on_a_root_cause_line_not_read(reader, _path):
    found = reader.pull_request_description_defect_lines(f"#root_cause a file. #follow_up {ISSUE}")
    return found == [{"kind": "root_cause", "line": f"#root_cause a file. #follow_up {ISSUE}",
                      "link": None}], f"read {found!r}"


def run_command(path, stdin_bytes):
    return subprocess.run([sys.executable, str(path)], input=stdin_bytes, capture_output=True,
                          timeout=60)


def case_command_prints_the_lines_as_json(_reader, path):
    completed = run_command(
        path, f"Text.\n- Root cause not fixed: stays. #follow_up {ISSUE}#x\n".encode())
    expected = [{"kind": "root_cause_not_fixed",
                 "line": f"- Root cause not fixed: stays. #follow_up {ISSUE}#x", "link": ISSUE}]
    try:
        printed = json.loads(completed.stdout)
    except json.JSONDecodeError:
        printed = None
    return (completed.returncode == 0 and printed == expected,
            f"exit {completed.returncode}, stdout {completed.stdout!r}, stderr {completed.stderr!r}")


def case_command_prints_an_empty_list_for_no_lines(_reader, path):
    completed = run_command(path, b"")
    return (completed.returncode == 0 and completed.stdout == b"[]\n",
            f"exit {completed.returncode}, stdout {completed.stdout!r}")


def case_command_refuses_a_description_that_is_not_utf8(_reader, path):
    completed = run_command(path, b"#root_cause \xff\n")
    return (completed.returncode == 2 and completed.stdout == b""
            and b"the description on stdin is not UTF-8 text" in completed.stderr,
            f"exit {completed.returncode}, stdout {completed.stdout!r}, stderr {completed.stderr!r}")


RC, NF, ND = "root_cause", "root_cause_not_fixed", "no_defect_fixed"

case_root_cause_hashtag = kinds_are("#root_cause the hook read a file.", [RC])
case_not_fixed_hashtag = kinds_are("#root_cause_not_fixed it stays.", [NF])
case_no_defect_fixed_hashtag = kinds_are("#no_defect_fixed", [ND])
case_root_cause_label = kinds_are("Root cause: the hook read a file.", [RC])
case_not_fixed_label = kinds_are("Root cause not fixed: it stays.", [NF])
case_no_defect_fixed_label = kinds_are("No defect fixed.", [ND])
case_indented_bullets = kinds_are("  - #root_cause a.\n* Root cause not fixed: b.\n+ No defect fixed.", [RC, NF, ND])
case_bold_hashtag_after_a_bullet = kinds_are("- **#root_cause** a file.", [RC])
case_bold_label_closing_before_its_colon = kinds_are("**Root cause not fixed**: b.\n__No defect fixed__.", [NF, ND])
case_bold_label_closing_after_its_colon = kinds_are("**Root cause:** a file.", [RC])
case_hashtag_only_mid_line = kinds_are("This has no #root_cause line.", [])
case_label_only_mid_line = kinds_are("The Root cause: was a file.", [])
case_hashtag_run_on_into_a_longer_word = kinds_are("#root_causes a.\n#no_defect_fixedness", [])
case_label_without_its_colon = kinds_are("Root cause the hook read a file.", [])
case_label_without_its_period = kinds_are("No defect fixed", [])
case_lines_in_order = kinds_are("No defect fixed.\ntext\n#root_cause a.\n#root_cause_not_fixed b.", [ND, RC, NF])

case_follow_up_bare_link = link_is(f"#root_cause_not_fixed b. #follow_up {ISSUE}", ISSUE)
case_follow_up_link_ending_a_sentence = link_is(f"#root_cause_not_fixed b. #follow_up {ISSUE}.", ISSUE)
case_follow_up_link_with_a_fragment = link_is(f"#root_cause_not_fixed b. #follow_up {ISSUE}#issuecomment-1", ISSUE)
case_follow_up_link_with_a_sub_path = link_is(f"#root_cause_not_fixed b. #follow_up {PULL_REQUEST}/files", PULL_REQUEST)
case_follow_up_link_with_a_query = link_is(f"#root_cause_not_fixed b. #follow_up {ISSUE}?x=1", ISSUE)
case_follow_up_markdown_citation = link_is(f"#root_cause_not_fixed b. #follow_up GHI [Ask]({ISSUE}).", ISSUE)
case_follow_up_first_link_read = link_is(f"Root cause not fixed: b. #follow_up {ISSUE} or {PULL_REQUEST}", ISSUE)
case_follow_up_link_to_a_commit = link_is(
    "#root_cause_not_fixed b. #follow_up https://github.com/nedschorus/nedschorus/commit/40ad4f50c38e", None)
case_follow_up_http_link = link_is("#root_cause_not_fixed b. #follow_up http://github.com/o/r/issues/1", None)
case_line_with_no_link = link_is("#root_cause_not_fixed the outage had to end first.", None)
case_link_without_the_follow_up_hashtag = link_is(f"#root_cause_not_fixed b; see {ISSUE}", None)
case_link_before_the_follow_up_hashtag = link_is(f"#root_cause_not_fixed b; see {ISSUE} #follow_up soon", None)
case_follow_up_run_on_into_a_longer_word = link_is(f"#root_cause_not_fixed b. #follow_ups {ISSUE}", None)


CASES = [
    ("each line kept whole, bullet and bold included, without its carriage return",
     case_line_kept_whole_without_its_carriage_return),
    ("a #follow_up link on a #root_cause line is not read", case_follow_up_on_a_root_cause_line_not_read),
    ("the command prints the lines as JSON", case_command_prints_the_lines_as_json),
    ("the command prints [] for a description with no defect line", case_command_prints_an_empty_list_for_no_lines),
    ("the command exits 2 on a description that is not UTF-8", case_command_refuses_a_description_that_is_not_utf8),
    ("#root_cause", case_root_cause_hashtag),
    ("#root_cause_not_fixed", case_not_fixed_hashtag),
    ("#no_defect_fixed", case_no_defect_fixed_hashtag),
    ("Root cause:", case_root_cause_label),
    ("Root cause not fixed:", case_not_fixed_label),
    ("No defect fixed.", case_no_defect_fixed_label),
    ("indented bullets of each kind", case_indented_bullets),
    ("a bold hashtag after a bullet", case_bold_hashtag_after_a_bullet),
    ("a bold label closing before its colon or period", case_bold_label_closing_before_its_colon),
    ("a bold label closing after its colon", case_bold_label_closing_after_its_colon),
    ("a hashtag only mid-line is no defect line", case_hashtag_only_mid_line),
    ("a label only mid-line is no defect line", case_label_only_mid_line),
    ("a hashtag run on into a longer word is no defect line", case_hashtag_run_on_into_a_longer_word),
    ("\"Root cause\" without its colon is no defect line", case_label_without_its_colon),
    ("\"No defect fixed\" without its period is no defect line", case_label_without_its_period),
    ("lines are returned in order", case_lines_in_order),
    ("a bare #follow_up link", case_follow_up_bare_link),
    ("a #follow_up link ending a sentence loses the period", case_follow_up_link_ending_a_sentence),
    ("a #follow_up link with a #fragment is cut back", case_follow_up_link_with_a_fragment),
    ("a #follow_up link with a sub-path is cut back", case_follow_up_link_with_a_sub_path),
    ("a #follow_up link with a query is cut back", case_follow_up_link_with_a_query),
    ("a #follow_up link inside a Markdown citation", case_follow_up_markdown_citation),
    ("only the first link after #follow_up is read", case_follow_up_first_link_read),
    ("a #follow_up link to a commit is no link", case_follow_up_link_to_a_commit),
    ("an http:// #follow_up link is no link", case_follow_up_http_link),
    ("a not-fixed line with no link has none", case_line_with_no_link),
    ("a link without #follow_up is no link", case_link_without_the_follow_up_hashtag),
    ("a link before #follow_up is no link", case_link_before_the_follow_up_hashtag),
    ("#follow_up run on into a longer word is no hashtag", case_follow_up_run_on_into_a_longer_word),
]

MUTATIONS = [
    ("the line start allowed anywhere in a line", [("pattern.match(line)", "pattern.search(line)")],
     [case_hashtag_only_mid_line, case_label_only_mid_line]),
    ("no bullet allowed", [(r'_LINE_START = r"\s*(?:[-*+]\s+)?', r'_LINE_START = r"\s*')],
     [case_indented_bullets, case_bold_hashtag_after_a_bullet]),
    ("no indentation allowed", [(r'_LINE_START = r"\s*', r'_LINE_START = r"')], [case_indented_bullets]),
    ("no bold type allowed at the line start", [(r'(?:[-*+]\s+)?(?:\*\*|__)?"', r'(?:[-*+]\s+)?"')],
     [case_bold_hashtag_after_a_bullet, case_bold_label_closing_after_its_colon]),
    ("no bold type allowed before a label's colon or period",
     [("re.escape(label[:-1]) + _BOLD_END +", "re.escape(label[:-1]) +")],
     [case_bold_label_closing_before_its_colon]),
    ("a label's colon or period made optional",
     [("_BOLD_END + re.escape(label[-1])", "_BOLD_END + '(?:' + re.escape(label[-1]) + ')?'")],
     [case_label_without_its_colon, case_label_without_its_period]),
    ("a hashtag allowed to run on into a longer word", [(r'_HASHTAG) + r"(?!\w)|"', '_HASHTAG) + r"|"')],
     [case_hashtag_run_on_into_a_longer_word]),
    ("#root_cause not accepted", [('ROOT_CAUSE_HASHTAG = "#root_cause"', 'ROOT_CAUSE_HASHTAG = "#never"')],
     [case_root_cause_hashtag]),
    ("#root_cause_not_fixed not accepted",
     [('ROOT_CAUSE_NOT_FIXED_HASHTAG = "#root_cause_not_fixed"', 'ROOT_CAUSE_NOT_FIXED_HASHTAG = "#never"')],
     [case_not_fixed_hashtag]),
    ("#no_defect_fixed not accepted",
     [('NO_DEFECT_FIXED_HASHTAG = "#no_defect_fixed"', 'NO_DEFECT_FIXED_HASHTAG = "#never"')],
     [case_no_defect_fixed_hashtag]),
    ("\"Root cause:\" not accepted", [('ROOT_CAUSE_COLON_LABEL = "Root cause:"', 'ROOT_CAUSE_COLON_LABEL = "Never:"')],
     [case_root_cause_label]),
    ("\"Root cause not fixed:\" not accepted",
     [('ROOT_CAUSE_NOT_FIXED_COLON_LABEL = "Root cause not fixed:"', 'ROOT_CAUSE_NOT_FIXED_COLON_LABEL = "Never:"')],
     [case_not_fixed_label]),
    ("\"No defect fixed.\" not accepted",
     [('NO_DEFECT_FIXED_PERIOD_LABEL = "No defect fixed."', 'NO_DEFECT_FIXED_PERIOD_LABEL = "Never."')],
     [case_no_defect_fixed_label]),
    ("the carriage return kept on the line", [('line = line.removesuffix("\\r")', "line = line")],
     [case_line_kept_whole_without_its_carriage_return]),
    ("the #follow_up link read on every kind of line",
     [("if kind == ROOT_CAUSE_NOT_FIXED else None", "")], [case_follow_up_on_a_root_cause_line_not_read]),
    ("a link anywhere on the line read as the #follow_up link",
     [(r're.escape(PULL_REQUEST_DESCRIPTION_FOLLOW_UP_HASHTAG) + r"(?!\w).*?(?P<url>', r'r".*?(?P<url>')],
     [case_link_without_the_follow_up_hashtag, case_link_before_the_follow_up_hashtag]),
    ("#follow_up allowed to run on into a longer word", [(r'_HASHTAG) + r"(?!\w).*?', '_HASHTAG) + r".*?')],
     [case_follow_up_run_on_into_a_longer_word]),
    ("the last link after #follow_up read", [(r'(?!\w).*?(?P<url>', r'(?!\w).*(?P<url>')],
     [case_follow_up_first_link_read]),
    ("trailing punctuation kept on the link", [('.rstrip(".,;:")', "")],
     [case_follow_up_link_ending_a_sentence]),
    ("a closing parenthesis allowed in the link", [(r"[^\s)>\]`]+", r"[^\s>\]`]+")],
     [case_follow_up_markdown_citation]),
    ("a link other than an issue or pull request accepted", [("(?:issues|pull)/[0-9]+)", "[a-z]+/[0-9a-z]+)")],
     [case_follow_up_link_to_a_commit]),
    ("an http:// link accepted", [(r'r"(?P<item>https://github', r'r"(?P<item>https?://github')],
     [case_follow_up_http_link]),
    ("a #fragment, sub-path or query no longer cut from the link", [("(?:[/#?].*)?", "")],
     [case_follow_up_link_with_a_fragment, case_follow_up_link_with_a_sub_path, case_follow_up_link_with_a_query]),
    ("a description that is not UTF-8 read as success", [("        return 2", "        return 0")],
     [case_command_refuses_a_description_that_is_not_utf8]),
]


def run_cases(path, label):
    reader = load(path)
    passed = 0
    for name, function in CASES:
        ok, detail = function(reader, path)
        check(f"{label}{name}", ok, detail)
        passed += ok
    return passed


def case_name_of(function):
    for name, candidate in CASES:
        if candidate is function:
            return name
    raise SystemExit(f"reader test: mutation names an unlisted case {function!r}")


def reader_copy(scratch, text):
    copy = Path(tempfile.mkdtemp(dir=scratch)) / READER.name
    copy.write_text(text)
    return copy


def run_mutations(scratch):
    source = READER.read_text()
    for mutation_name, replacements, targets in MUTATIONS:
        mutated = source
        for old, new in replacements:
            if old not in mutated:
                check(f"mutation '{mutation_name}' applied", False, f"replacement text not found: {old!r}")
                break
            mutated = mutated.replace(old, new)
        else:
            if mutated == source:
                check(f"mutation '{mutation_name}' changes the reader", False, "the text is unchanged")
                continue
            path = reader_copy(scratch, mutated)
            try:
                reader = load(path)
            except Exception as error:
                check(f"mutation '{mutation_name}' loads", False, f"{error!r}")
                continue
            for target in targets:
                try:
                    ok, detail = target(reader, path)
                except Exception as error:
                    ok, detail = False, f"raised {error!r}"
                check(f"mutation '{mutation_name}' turns red: {case_name_of(target)}", not ok,
                      f"the case still passed against the mutated reader: {detail}")


def main():
    scratch = Path(tempfile.mkdtemp(prefix="description-defect-line-reader-test-"))
    try:
        first = run_cases(READER, "")
        run_mutations(scratch)
        control = run_cases(reader_copy(scratch, READER.read_text()), "control after mutations: ")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    print(f"\n{first} of {len(CASES)} cases passed; the unmutated control after the "
          f"mutations passed {control} of {len(CASES)}")
    if failures:
        print(f"\n{len(failures)} check(s) failed:")
        for name in failures:
            print(f"  {name}")
        sys.exit(1)
    print("\nall cases passed")


if __name__ == "__main__":
    main()
