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
    ("a chain with a parenthesised chain on the right", 'X_MESSAGE = "a" + ("b" + x)\n', [(1, 1, "ab{x}")]),
    ("a chain nested in a call argument", 'print(str("a " + x + " b"))\n', [(1, 1, "a {x} b")]),
)
for case_name, source, expected in CHAINS:
    found = [(entry["line"], entry["end_line"], entry["text"]) for entry in entries(source)]
    check(f"concatenation: {case_name} is one message", found == expected, found)

def chain_text(source):
    return entries(source)[0]["text"]


spec_one = chain_text('X_MESSAGE = "Elapsed: " + f"{seconds:.1f}"\n')
spec_three = chain_text('X_MESSAGE = "Elapsed: " + f"{seconds:.3f}"\n')
check("an f-string field in a chain keeps its format spec, so .1f and .3f differ",
      spec_one == "Elapsed: {seconds:.1f}" and spec_three == "Elapsed: {seconds:.3f}", (spec_one, spec_three))
check("an f-string field in a chain keeps its conversion", chain_text('X_MESSAGE = "v " + f"{x!r}"\n') == "v {x!r}")
check("a chain's field text matches the field in the same standalone f-string",
      "{seconds:.1f}" in chain_text('X_MESSAGE = f"{seconds:.1f}"\n'))
found = entries('print(report.render() + "\\n")\nprint("Failed: " + name + f" {n!r}")\n')
check("literal_text leaves out every {...} placeholder",
      [entry["literal_text"] for entry in found] == ["\n", "Failed:  "], found)

NOT_RECOGNIZED_FORMS = (
    ("a systemMessage, which the user sees and the agent does not",
     'output = {"systemMessage": "user text"}\n'),
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

SAY = 'def say(stream, text):\n    stream.write(text + "\\n")\n'

# Modelled on IgnitionPlanWithoutConversationTail.compose() in nc-systems/handoff/handoff-supervisor.py,
# whose recovery note reaches the agent only through a second local name and a return.
COMPOSE_SOURCE = """ITEMS_INSTRUCTION = "Show the user every waiting item in one approval-walk."


class IgnitionPlan:
    def compose(self, report, lines=()):
        if self.transcript_path is not None:
            recovery_note = (
                "the conversation-tail is unavailable; "
                f"that session's transcript is {self.transcript_path}.")
        elif self.transcript_paths:
            paths = [str(path) for path in self.transcript_paths]
            recovery_note = (
                "the conversation-tail is unavailable; that session's transcript is in "
                f"more than one folder, at {', '.join(paths[:-1])} and {paths[-1]}.")
        else:
            recovery_note = "the conversation-tail is unavailable; this next-step is your whole context."
        prompt = (
            f"{self.next_step}\\n\\n(Recovered at {self.occasion}: {recovery_note}) "
            + ITEMS_INSTRUCTION
        )
        if report:
            prompt += " " + report
        for line in lines:
            prompt += " " + line
        return prompt
"""
found = [(entry["line"], entry["end_line"], entry["label"], entry["text"]) for entry in entries(COMPOSE_SOURCE)]
check("a recovery note built in a local name and returned through another is found, each branch at its own lines",
      [entry for entry in found if entry[2] == "recovery_note = in IgnitionPlan.compose()"] == [
          (8, 9, "recovery_note = in IgnitionPlan.compose()",
           "f\"the conversation-tail is unavailable; that session's transcript is {self.transcript_path}.\""),
          (13, 14, "recovery_note = in IgnitionPlan.compose()",
           "f\"the conversation-tail is unavailable; that session's transcript is in more than one folder, "
           "at {', '.join(paths[:-1])} and {paths[-1]}.\""),
          (16, 16, "recovery_note = in IgnitionPlan.compose()",
           "the conversation-tail is unavailable; this next-step is your whole context.")], found)
check("the returned local that holds the recovery note is found too, with each += at its own line",
      [entry[0] for entry in found if entry[2] == "prompt = in IgnitionPlan.compose()"] == [18, 22, 24], found)
check("a list the recovery note's f-string reads through a join call is not text", not any(
    entry[2].startswith("paths =") for entry in found), found)
compose_kinds = {(entry["label"].split(" ")[0], entry["kind"]) for entry in entries(COMPOSE_SOURCE)}
check("the recovery note and the prompt it is returned in are prompts, and the module instruction is a message",
      compose_kinds == {("recovery_note", "prompt"), ("prompt", "prompt"), ("ITEMS_INSTRUCTION", "message")},
      compose_kinds)

KINDS = (
    ("a printed local", 'def main(n):\n    text = f"{n} failed"\n    print(text)\n', ["message"]),
    ("a local returned by a function with no prompt in its name",
     'def line(n):\n    text = f"{n} failed"\n    return text\n', ["message"]),
    ("a local returned by a function whose name holds prompt",
     'def build_ignition_prompt(n):\n    text = f"Start at step {n}."\n    return text\n', ["prompt"]),
    ("a local returned by a method whose name holds Prompt",
     'class Plan:\n    def handoffPrompt(self):\n        text = "Start here."\n        return text\n', ["prompt"]),
    ("a local named in capitals with PROMPT, printed",
     'def main():\n    SYSTEM_PROMPT_TEXT = "Answer in one line."\n    print(SYSTEM_PROMPT_TEXT)\n', ["prompt"]),
    ("a local printed first and then folded into a returned prompt",
     'def compose():\n    note = "Read the transcript."\n    print(note)\n    prompt = "Resume. " + note\n    return prompt\n',
     ["prompt", "prompt"]),
    ("a local printed twice, which stays a message",
     'def main():\n    text = "Twice."\n    print(text)\n    print(text)\n', ["message"]),
    ("a local returned through a string literal's join from a function whose name holds prompt",
     'def build_prompt():\n    note = "Read the transcript."\n    return "\\n".join([note])\n', ["prompt"]),
    ("a string printed directly in a function whose name holds prompt",
     'def prompt_failure():\n    print("the prompt could not be built")\n', ["message"]),
)
for case_name, source, expected in KINDS:
    found = [entry["kind"] for entry in entries(source)]
    check(f"kind: {case_name}", found == expected, entries(source))

LOCAL_NAME_FORMS = (
    ("a local f-string that is printed", 'def main(n):\n    text = f"{n} failed"\n    print(text)\n',
     [("f'{n} failed'", "text = in main()")]),
    ("a local string a raise hands to the exception it builds",
     'def main():\n    detail = "no branch"\n    raise SystemExit(detail)\n', [("no branch", "detail = in main()")]),
    ("a local string as a hook output value",
     'def main():\n    text = "local text"\n    return {"additionalContext": text}\n',
     [("local text", "text = in main()")]),
    ("a local string inside a hook output f-string",
     'def main():\n    text = "local text"\n    return {"additionalContext": f"see {text}"}\n',
     [("f'see {text}'", '"additionalContext" value in main()'), ("local text", "text = in main()")]),
    ("a local string a helper printer is handed",
     SAY + 'def main():\n    text = "said later"\n    say(sys.stderr, text)\n',
     [("said later", "text = in main()")]),
    ("a local string assigned to a name with a message suffix",
     'def main(n):\n    count = f"{n} files"\n    STOP_MESSAGE = "stopped after " + count\n',
     [("f'{n} files'", "count = in main()"), ("stopped after {count}", "STOP_MESSAGE = in main()")]),
    ("a local string % something that is printed", 'def main(n):\n    text = "%d failed" % n\n    print(text)\n',
     [("%d failed", "text = in main()")]),
    ("a local join whose pieces are listed",
     'def main(items):\n    text = "\\n".join(["Fix these:", *items])\n    print(text)\n',
     [("\n", "text = in main()"), ("Fix these:", "text = in main()")]),
    ("a local joined from another local",
     'def main():\n    head = "Fix these"\n    text = " ".join([head])\n    print(text)\n',
     [("Fix these", "head = in main()"), (" ", "text = in main()")]),
    ("a local chosen by a condition, its condition left out",
     'def main(row):\n    verb = "resuming" if row["kind"] == "known" else "launching"\n    print(f"{verb} now")\n',
     [("resuming", "verb = in main()"), ("launching", "verb = in main()"), ("f'{verb} now'", "print in main()")]),
    ("a local returned as part of a built string",
     'def line(n):\n    count = f"{n} files"\n    return "checked " + count\n', [("f'{n} files'", "count = in line()")]),
    ("a local annotated with its type", 'def line():\n    text: str = "annotated text"\n    return text\n',
     [("annotated text", "text = in line()")]),
    ("a local of a nested function as a hook output value, its enclosing function binding nothing",
     'def outer():\n    def inner():\n        text = "inner text"\n        return {"additionalContext": text}\n'
     '    return inner()\n', [("inner text", "text = in outer.inner()")]),
    ("a local printed after a nested function's definition",
     'def outer():\n    text = "outer text"\n    def inner():\n        pass\n    print(text)\n',
     [("outer text", "text = in outer()")]),
    ("a local returned through a string literal's join",
     'def build_prompt():\n    note = "Read the transcript."\n    return "\\n".join([note])\n',
     [("Read the transcript.", "note = in build_prompt()")]),
    ("a local printed through a string literal's join",
     'def main():\n    note = "Read the transcript."\n    print(" ".join([note]))\n',
     [(" ", "print in main()"), ("Read the transcript.", "note = in main()")]),
    ("a local in a + chain as a hook output value",
     'def main():\n    note = "Read the transcript."\n    return {"additionalContext": "Instructions: " + note}\n',
     [("Instructions: {note}", '"additionalContext" value in main()'), ("Read the transcript.", "note = in main()")]),
    ("a printed conditional's branches, its condition left out",
     'def main(mode):\n    state = "internal data"\n    print("Resume" if state == "known" else "Stop")\n',
     [("Resume", "print in main()"), ("Stop", "print in main()")]),
    ("a local of an enclosing function printed by a lambda nested in it",
     'def main():\n    text = "outer text"\n    callback = lambda: print(text)\n',
     [("outer text", "text = in main()")]),
    ("a local of an enclosing function printed in the body of a class nested in it",
     'def main():\n    text = "outer text"\n    class Holder:\n        print(text)\n',
     [("outer text", "text = in main.Holder()")]),
    ("a local printed in a lambda's default, which the enclosing function evaluates",
     'def main():\n    text = "Visible message"\n    callback = lambda value=print(text): None\n',
     [("Visible message", "text = in main()")]),
    ("a local printed in a class decorator, which the enclosing function evaluates",
     'def main():\n    text = "Decorated message"\n    @register(print(text))\n    class Holder:\n        pass\n',
     [("Decorated message", "text = in main()")]),
    ("a local printed in a class base, which the enclosing function evaluates",
     'def main():\n    text = "Base message"\n    class Holder(make_base(print(text))):\n        pass\n',
     [("Base message", "text = in main()")]),
)
for case_name, source, expected in LOCAL_NAME_FORMS:
    found = [(entry["text"], entry["label"]) for entry in entries(source)]
    check(f"recognized: {case_name}", sorted(found) == sorted(expected), found)

LOCAL_NAME_FORMS_NOT_RECOGNIZED = (
    ("a local path handed to open and Path",
     'from pathlib import Path\ndef save(root):\n    path = f"{root}/notes.json"\n'
     '    with open(path, "w") as handle:\n        handle.write("{}")\n    Path(path).touch()\n'),
    ("a local path returned through a call",
     'from pathlib import Path\ndef where(root):\n    path = f"{root}/notes.json"\n    return Path(path)\n'),
    ("a local subprocess argument, run and returned in a list",
     'import subprocess\ndef fetch(branch):\n    ref = f"origin/{branch}"\n'
     '    subprocess.run(["git", "fetch", ref])\n    return ["git", "log", ref]\n'),
    ("a local log key", 'def record(log, agent):\n    key = f"{agent}-last-run"\n    log[key] = 1\n    print(len(log))\n'),
    ("a local printed only through a call",
     'import json\ndef main(n):\n    text = f"{n}"\n    print(json.dumps(text))\n'),
    ("a local of an enclosing function printed by a function nested in it",
     'def outer():\n    text = "outer text"\n    def inner():\n        print(text)\n    inner()\n'),
    ("a local of a nested function, when the enclosing function prints its own name of that spelling",
     'def outer(text):\n    def inner():\n        text = "inner text"\n        store(text)\n    print(text)\n'),
    ("a local of an enclosing function, when a lambda prints its own parameter of that spelling",
     'def main():\n    prompt = "unused"\n    callback = lambda prompt: print(prompt)\n'),
    ("a local of an enclosing function, when a class body nested in it binds that name itself",
     'def main():\n    text = "outer text"\n    class Holder:\n        text = 3\n        print(text)\n'),
    ("a string bound in a class body and printed there, as at module level",
     'def main():\n    class Holder:\n        text = "class text"\n        print(text)\n'),
    ("a local in a returned conditional's condition",
     'def build_prompt():\n    state = "internal data"\n    return "Resume" if state else "Stop"\n'),
    ("an empty local string that is printed", 'def main():\n    text = ""\n    print(text)\n'),
    ("a local string returned in a tuple", 'def main():\n    text = "tuple text"\n    return text, 1\n'),
    ("a local string returned only when a condition holds, as a name",
     'def main(flag):\n    text = "chosen text"\n    return text if flag else None\n'),
    ("a string printed by name outside any function", 'text = "module text"\nprint(text)\n'),
    ("a local built with a string method other than join, such as format",
     'def main(n):\n    text = "{} failed".format(n)\n    print(text)\n'),
    ("a local built with a string method other than join, such as strip",
     'def main():\n    text = " padded ".strip()\n    print(text)\n'),
    ("an attribute assigned a string, which is not a local name",
     'def main(self):\n    self.note = "attribute text"\n    print(self.note)\n'),
)
for case_name, source in LOCAL_NAME_FORMS_NOT_RECOGNIZED:
    found = texts(source)
    check(f"not recognized: {case_name}", found == [], found)

HELPER_PRINTER_FORMS = (
    ("a string passed to a helper that writes its parameter to a stream parameter",
     SAY + 'say(sys.stderr, "said text")\n', [("said text", "say()")]),
    ("a string passed by keyword to a helper printer",
     SAY + 'say(sys.stderr, text="keyword text")\n', [("keyword text", "say()")]),
    ("a string passed to a helper's keyword-only parameter that it prints",
     'def warn(*, message):\n    print(message)\nwarn(message="keyword-only text")\n',
     [("keyword-only text", "warn()")]),
    ("a string passed to a helper that prints its parameter",
     'def warn(message):\n    print("warning: " + message)\nwarn("warned text")\n',
     [("warning: {message}", "print in warn()"), ("warned text", "warn()")]),
    ("a string passed to a helper that writes its parameter to sys.stderr in an f-string",
     'import sys\ndef fail(reason):\n    sys.stderr.write(f"failed: {reason}")\nfail("reason text")\n',
     [("f'failed: {reason}'", "sys.stderr.write in fail()"), ("reason text", "fail()")]),
    ("a string passed to a helper that hands its parameter to another helper printer",
     SAY + 'def refuse(stream, cause):\n    say(stream, cause + ", so refused")\n'
     'refuse(sys.stderr, "cause text")\n',
     [("{cause}, so refused", "say() in refuse()"), ("cause text", "refuse()")]),
    ("a string passed to a helper whose lambda prints the helper's parameter",
     'def sink(text):\n    run(lambda: print(text))\nsink("closure text")\n',
     [("closure text", "sink()")]),
    ("a string passed to a helper that hands its parameter to a helper printer defined after it",
     'def refuse(stream, cause):\n    say(stream, cause + ", so refused")\n' + SAY
     + 'refuse(sys.stderr, "cause text")\n',
     [("{cause}, so refused", "say() in refuse()"), ("cause text", "refuse()")]),
    ("a string built with % for a helper printer, inside a function",
     SAY + 'def main():\n    say(sys.stderr, "branch %s failed" % name)\n',
     [("branch %s failed", "say() in main()")]),
)
for case_name, source, expected in HELPER_PRINTER_FORMS:
    found = [(entry["text"], entry["label"]) for entry in entries(source)]
    check(f"recognized: {case_name}", found == expected, found)

HELPER_PRINTER_FORMS_NOT_RECOGNIZED = (
    ("the stream argument of a helper printer, which is not printed", SAY + 'say("stream text", x)\n'),
    ("a string a helper prints only through a call",
     'import json\ndef emit(payload):\n    print(json.dumps(payload))\nemit({"key": "dumped text"})\n'),
    ("a string a helper writes to a file it opens itself",
     'def save(text):\n    with open("f") as handle:\n        handle.write(text)\nsave("saved text")\n'),
    ("a string passed to a helper defined twice",
     SAY + SAY + 'say(sys.stderr, "twice text")\n'),
    ("a string passed to a method named like a helper printer",
     'class C:\n    def say(self, text):\n        print(text)\nC().say("method text")\n'),
    ("a string after a starred argument", SAY + 'say(*streams, "starred text")\n'),
    ("a string passed to a parameter that hides a helper printer's name",
     SAY + 'def run(say=None):\n    say(sys.stderr, "hidden text")\n'),
    ("a string passed to a function whose parameter hides a helper printer's name",
     'def say(text):\n    print(text)\ndef route(say, payload):\n    say(payload)\n'
     'route(lambda p: None, {"key": "value"})\n'),
    ("a string passed to a lambda's parameter that hides a helper printer's name",
     SAY + 'route = lambda say: say(sys.stderr, "hidden text")\n'),
    ("a string a helper prints only in a conditional's condition, handed through a join",
     'def status(mode):\n    print("Resume" if mode else "Stop")\n'
     'def main():\n    prompt = "condition text"\n    status("".join([prompt]))\n'),
    ("a string a helper's lambda prints only through the lambda's own parameter of that spelling",
     'def sink(text):\n    callback = lambda text: print(text)\n'
     'def main():\n    prompt = "shadowed text"\n    sink("".join([prompt]))\n'),
    ("a print keyword that names where to print, not what",
     'def show(text, out):\n    print(text, file=out)\nshow(None, out="file text")\n'),
)
for case_name, source in HELPER_PRINTER_FORMS_NOT_RECOGNIZED:
    found = [entry["text"] for entry in entries(source)
             if entry["label"].split(" in ")[0] not in ("print", "sys.stderr.write")]
    check(f"not recognized: {case_name}", found == [], found)

CONFLICT_CHECK = (Path(__file__).resolve().parents[3]
                  / "scripts" / "git-client-side-hooks-pre-push-conflict-check.py")
found = [entry["text"] for entry in entries(CONFLICT_CHECK.read_text(encoding="utf-8"))]
for line in ("Once the merge is committed, push again.",
             "the pre-push conflict check did not run, because %s is missing",
             "Follow the report, then check %s again by hand from your worktree: %s"):
    check(f"the pre-push conflict check's helper-printed line {line!r} is found", line in found,
          found)

check("source that does not parse yields no entries", texts('print("unclosed\n') == [])
check("no source yields no entries", texts(None) == [])

for path, expected in (("scripts/tool-test.py", True), ("nc-systems/x/tests/helper.py", True),
                       ("scripts/tool.py", False), ("scripts/tests.py", False)):
    check(f"path_is_test_file({path!r}) is {expected}", collector.path_is_test_file(path) is expected)

print()
print(f"{len(failures)} failed")
sys.exit(1 if failures else 0)
