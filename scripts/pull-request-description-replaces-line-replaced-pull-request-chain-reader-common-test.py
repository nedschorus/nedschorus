#!/usr/bin/env python3
"""Tests for pull-request-description-replaces-line-replaced-pull-request-chain-reader-common.py.

Run: python3 scripts/pull-request-description-replaces-line-replaced-pull-request-chain-reader-common-test.py
"""

import importlib.util
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "pull_request_description_replaces_line_replaced_pull_request_chain_reader_common",
    Path(__file__).with_name("pull-request-description-replaces-line-replaced-pull-request-chain-reader-common.py"))
reader = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reader)

REPOSITORY = "nedschorus/nedschorus"
LINK = "https://github.com/nedschorus/nedschorus/pull/"
failures = []


def check(name, condition, detail=""):
    print(("PASS " if condition else "FAIL ") + name)
    if not condition:
        failures.append(name)
        if detail:
            print("     " + str(detail).replace("\n", "\n     "))


def refusal(call):
    try:
        call()
    except reader.ReplacedPullRequestChainUnreadable as error:
        return str(error)
    return None


def numbers(description, number=9):
    return reader.replaced_pull_request_numbers_on_replaces_lines(description, REPOSITORY, number)


check("a #replaces line names the old pull request",
      numbers(f"Text.\n#replaces {LINK}2544\nMore.") == [2544])
check("a bulleted, bold line with a trailing fragment and a carriage return is read",
      numbers(f"- **#replaces {LINK}12#issuecomment-3**\r\n#replaces {LINK}13.") == [12, 13])
check("a line naming the same pull request twice gives it once",
      numbers(f"#replaces {LINK}12\n#replaces {LINK}12") == [12])
check("prose that mentions #replaces mid-line, a longer hashtag, and no description give nothing",
      numbers(f"This one replaces {LINK}12 by its #replaces line.\n#replaces_not {LINK}3") == []
      and numbers(None) == [])
check("a link to another repository is refused",
      "does not name, after #replaces, a full https://github.com/nedschorus/nedschorus/pull/<number>"
      in (refusal(lambda: numbers("#replaces https://github.com/other/repo/pull/12")) or ""))
check("a line with no link, or an issue link, is refused naming the line",
      "has the line `#replaces #12`" in (refusal(lambda: numbers("#replaces #12")) or "")
      and refusal(lambda: numbers("#replaces https://github.com/nedschorus/nedschorus/issues/12")) is not None)
check("a line naming the pull request itself is refused",
      "names pull request 9 itself" in (refusal(lambda: numbers(f"#replaces {LINK}9")) or ""))

descriptions = {30: f"#replaces {LINK}20\n#replaces {LINK}25", 25: f"#replaces {LINK}10", 20: "", 10: "None."}
check("a chain is followed through replacements of replacements, oldest first",
      reader.replaced_pull_request_chain_numbers_oldest_first(30, REPOSITORY, descriptions.__getitem__) == [20, 10, 25])
check("a pull request with no #replaces line replaces none",
      reader.replaced_pull_request_chain_numbers_oldest_first(20, REPOSITORY, descriptions.__getitem__) == [])
looping = {3: f"#replaces {LINK}2", 2: f"#replaces {LINK}1", 1: f"#replaces {LINK}3"}
looping_reads = []


class ReadPastTheLoop(Exception):
    """A reader without its loop check would read the loop's descriptions forever."""


def read_looping_description(number):
    looping_reads.append(number)
    if len(looping_reads) > 10:
        raise ReadPastTheLoop(looping_reads)
    return looping[number]


def loop_refusal():
    try:
        return refusal(lambda: reader.replaced_pull_request_chain_numbers_oldest_first(
            3, REPOSITORY, read_looping_description))
    except ReadPastTheLoop as reads:
        return f"read on past the loop: {reads}"


loop_text = loop_refusal()
check("a loop is refused, naming each pull request in it",
      "pull request 3 replaces pull request 2 replaces pull request 1 replaces pull request 3" in (loop_text or ""),
      loop_text)
shared = {4: f"#replaces {LINK}2\n#replaces {LINK}3", 3: f"#replaces {LINK}2", 2: ""}
check("an old pull request two lines reach is listed once",
      reader.replaced_pull_request_chain_numbers_oldest_first(4, REPOSITORY, shared.__getitem__) == [2, 3])

print(f"{'FAILED' if failures else 'PASSED'}: {len(failures)} failed")
sys.exit(1 if failures else 0)
