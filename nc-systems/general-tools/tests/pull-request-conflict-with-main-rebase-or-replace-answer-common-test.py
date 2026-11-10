#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/pull-request-conflict-with-main-rebase-or-replace-answer-common.py.

Each case calls the function with the gate constant set as the case needs and an
ever-marked-ready reader that records whether it was called.

Run: python3 nc-systems/general-tools/tests/pull-request-conflict-with-main-rebase-or-replace-answer-common-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "pull_request_conflict_with_main_rebase_or_replace_answer_common",
    Path(__file__).resolve().parents[1]
    / "pull-request-conflict-with-main-rebase-or-replace-answer-common.py")
module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(module)
answer = module.pull_request_conflict_with_main_rebase_or_replace_answer
GATE = "REBASE_ONTO_MAIN_FOR_PULL_REQUESTS_NEVER_MARKED_READY_FOR_REVIEW_TURNED_ON"

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


class Reader:
    def __init__(self, ever_ready):
        self.ever_ready = ever_ready
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if isinstance(self.ever_ready, Exception):
            raise self.ever_ready
        return self.ever_ready


def main():
    check("the rebase answer for a never-ready pull request is off as shipped",
          getattr(module, GATE) is False, repr(getattr(module, GATE)))
    check("the two answers differ", module.REBASE_ONTO_MAIN != module.REPLACE_WITH_NEW_PULL_REQUEST)

    for gate in (False, True):
        setattr(module, GATE, gate)
        reader = Reader(False)
        check(f"gate {gate}: a branch with no open pull request is rebased, without reading "
              "its ready history",
              answer(False, reader) == module.REBASE_ONTO_MAIN and reader.calls == 0)

    setattr(module, GATE, False)
    reader = Reader(False)
    check("gate off: an open pull request never marked ready is replaced, without reading its "
          "ready history",
          answer(True, reader) == module.REPLACE_WITH_NEW_PULL_REQUEST and reader.calls == 0)

    setattr(module, GATE, True)
    check("gate on: an open pull request whose caller reads no ready history is replaced",
          answer(True) == module.REPLACE_WITH_NEW_PULL_REQUEST)
    reader = Reader(True)
    check("gate on: an open pull request ever marked ready is replaced",
          answer(True, reader) == module.REPLACE_WITH_NEW_PULL_REQUEST and reader.calls == 1)
    reader = Reader(False)
    check("gate on: an open pull request never marked ready is rebased",
          answer(True, reader) == module.REBASE_ONTO_MAIN and reader.calls == 1)
    failure = RuntimeError("gh failed")
    try:
        answer(True, Reader(failure))
        raised = None
    except RuntimeError as error:
        raised = error
    check("gate on: a reader that fails raises to the caller, not an answer", raised is failure,
          repr(raised))
    setattr(module, GATE, False)

    print()
    if failures:
        print(f"{len(failures)} case(s) failed")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
