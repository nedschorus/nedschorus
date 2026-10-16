#!/usr/bin/env python3
"""Tests for python-source-agent-facing-string-collector-common.py.

Run: python3 nc-systems/general-tools/tests/python-source-agent-facing-string-collector-common-test.py
Prints one line per case and exits non-zero if any case fails.

Each case hands the collector a small Python source and checks which strings
it reports, one case for each form the collector recognizes and for forms it
does not.
"""

import importlib.util
import sys
from pathlib import Path

_collector_spec = importlib.util.spec_from_file_location(
    "python_source_agent_facing_string_collector_common",
    Path(__file__).resolve().parent.parent / "python-source-agent-facing-string-collector-common.py")
collector = importlib.util.module_from_spec(_collector_spec)
_collector_spec.loader.exec_module(collector)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def texts(source):
    return [entry["text"] for entry in collector.agent_facing_string_nodes_in_source(source)]


def entries(source):
    return collector.agent_facing_string_nodes_in_source(source)


RECOGNIZED_FORMS = (
    ("a printed string", 'print("printed text")\n', "printed text"),
    ("a string written to sys.stderr", 'import sys\nsys.stderr.write("stderr text")\n', "stderr text"),
    ("a string written to sys.stdout", 'import sys\nsys.stdout.write("stdout text")\n', "stdout text"),
    ("a string in a raise", 'raise SystemExit("raised text")\n', "raised text"),
    ("a string assigned to a name with a message suffix", 'REFUSAL_MESSAGE = "assigned text"\n', "assigned text"),
    ("a suffix followed by S", 'HINT_LINES = ("plural text",)\n', "plural text"),
    ("a suffix the citation suite also reads", 'DENY_REASON = "reason text"\n', "reason text"),
    ("an annotated assignment", 'STOP_NOTICE: str = "annotated text"\n', "annotated text"),
    ("an augmented assignment", 'X_ADVICE = "a"\nX_ADVICE += "augmented text"\n', "augmented text"),
    ("a module docstring printed through __doc__",
     '"""help text"""\nimport argparse\nargparse.ArgumentParser(description=__doc__)\n', "help text"),
    ("a string literal as additionalContext in a dict literal",
     'import json\nprint(json.dumps({"hookSpecificOutput": {"additionalContext": "context text"}}))\n',
     "context text"),
    ("a string literal as permissionDecisionReason",
     'output = {"permissionDecision": "deny", "permissionDecisionReason": "deny text"}\n', "deny text"),
    ("a string literal as reason", 'output = {"decision": "block", "reason": "block text"}\n', "block text"),
    ("a string literal as stopReason", 'output = {"continue": False, "stopReason": "stop text"}\n', "stop text"),
    ("a concatenation of strings as additionalContext",
     'output = {"additionalContext": "joined " + "text"}\n', "joined text"),
    ("a name assigned a string once at module level, as additionalContext",
     'REMINDER = "bound text"\noutput = {"additionalContext": REMINDER}\n', "bound text"),
)
for case_name, source, expected in RECOGNIZED_FORMS:
    found = texts(source)
    check(f"recognized: {case_name}", expected in found, found)

found = entries('def main(name):\n    output = {"additionalContext": f"hello {name}"}\n')
check("an f-string as additionalContext is reported with its placeholders and its function",
      [(entry["text"], entry["label"]) for entry in found]
      == [("f'hello {name}'", '"additionalContext" value in main()')], found)

found = entries('X_MESSAGE = "suffix text"\noutput = {"additionalContext": X_MESSAGE}\n')
check("a name with a message suffix used as additionalContext is reported once, at its assignment",
      [entry["label"] for entry in found] == ["X_MESSAGE ="], found)

found = entries('print("one "\n      "two")\n')
check("an entry carries its first and last line", [(entry["line"], entry["end_line"]) for entry in found]
      == [(1, 2)], found)

CHAINS = (
    ("a chain of two literals", 'X_MESSAGE = "first " + "second"\n', [(1, 1, "first second")]),
    ("a chain with a variable in the middle", 'X_MESSAGE = "first " + name + " second"\n',
     [(1, 1, "first {name} second")]),
    ("a parenthesised multi-line chain", 'X_MESSAGE = (\n    "a"\n    + "b"\n)\n', [(2, 3, "ab")]),
    ("a chain nested in a call argument", 'print(str("a " + x + " b"))\n', [(1, 1, "a {x} b")]),
)
for case_name, source, expected in CHAINS:
    found = [(entry["line"], entry["end_line"], entry["text"]) for entry in entries(source)]
    check(f"concatenation: {case_name} is one message", found == expected, found)

NOT_RECOGNIZED_FORMS = (
    ("a systemMessage, which the user sees and the agent does not",
     'output = {"systemMessage": "user text"}\n'),
    ("a string held in a local variable", 'def main():\n    text = "local text"\n    return {"additionalContext": text}\n'),
    ("a name assigned twice at module level",
     'TEXT = "first"\nTEXT = "second"\noutput = {"additionalContext": TEXT}\n'),
    ("a string assigned to a name with no message suffix", 'GREETING = "plain text"\n'),
    ("a string as the value of another dict key", 'output = {"note": "data text"}\n'),
    ("a module docstring the program does not print", '"""docstring text"""\nimport sys\n'),
    ("a string in a lower-case name that merely contains a suffix", 'error_message_count = "count text"\n'),
)
for case_name, source in NOT_RECOGNIZED_FORMS:
    found = texts(source)
    check(f"not recognized: {case_name}", found == [], found)

check("source that does not parse yields no entries", texts('print("unclosed\n') == [])
check("no source yields no entries", texts(None) == [])

for path, expected in (("scripts/tool-test.py", True), ("nc-systems/x/tests/helper.py", True),
                       ("scripts/tool.py", False), ("scripts/tests.py", False)):
    check(f"path_is_test_file({path!r}) is {expected}", collector.path_is_test_file(path) is expected)

print()
print(f"{len(failures)} failed")
sys.exit(1 if failures else 0)
