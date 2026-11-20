#!/usr/bin/env python3
"""Cases for proposed-improvements-or-changes-file-entry-state-try-and-second-agent-verdict-lines-write.py.

Each case runs the program's main() on a file in a temporary directory, with
the time fixed, and checks the file's whole text and the exit code. A stand-in
`claude`, first on PATH, plays the second agent: it logs its arguments and the
prompt it is given, then prints the reply, exit code and delay a case sets.

Run: scripts/proposed-improvements-or-changes-file-entry-state-try-and-second-agent-verdict-lines-write-test.py
Exit codes: 0 all passed, 1 any failed.
"""

import contextlib
import importlib.util
import io
import json
import os
import shlex
import sys
import tempfile
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "entry_lines_write",
    HERE / "proposed-improvements-or-changes-file-entry-state-try-and-second-agent-verdict-lines-write.py")
PROGRAM = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROGRAM)
PROGRAM.now = lambda: "2026-11-10T12:00Z"

failures = []
case_count = 0

STAND_IN_CLAUDE = f"""#!{sys.executable}
import json, os, sys, time
from pathlib import Path
control = Path(os.environ["STAND_IN_CLAUDE_CONTROL"])
with (control / "calls.jsonl").open("a", encoding="utf-8") as log:
    log.write(json.dumps({{"argv": sys.argv[1:], "stdin": sys.stdin.read()}}) + "\\n")
answer = json.loads((control / "answer.json").read_text(encoding="utf-8"))
time.sleep(answer["sleep_seconds"])
sys.stdout.write(answer["stdout"])
sys.stderr.write(answer["stderr"])
sys.exit(answer["exit_code"])
"""
STAND_IN_DIRECTORY = Path(tempfile.mkdtemp())
(STAND_IN_DIRECTORY / "claude").write_text(STAND_IN_CLAUDE, encoding="utf-8")
(STAND_IN_DIRECTORY / "claude").chmod(0o755)
os.environ["PATH"] = f"{STAND_IN_DIRECTORY}{os.pathsep}{os.environ['PATH']}"
os.environ["STAND_IN_CLAUDE_CONTROL"] = str(STAND_IN_DIRECTORY)


def second_agent_answers(stdout, exit_code=0, stderr="", sleep_seconds=0):
    (STAND_IN_DIRECTORY / "answer.json").write_text(json.dumps(
        {"stdout": stdout, "exit_code": exit_code, "stderr": stderr, "sleep_seconds": sleep_seconds}), encoding="utf-8")
    (STAND_IN_DIRECTORY / "calls.jsonl").unlink(missing_ok=True)


def second_agent_calls():
    log = STAND_IN_DIRECTORY / "calls.jsonl"
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []


AGREES = "The ruling covers decisions, and the edit fixes a link.\nVERDICT: agrees\n"
DISAGREES = "The sources do not show it.\nVERDICT: disagrees\n"
VERDICT = ["second-agent-verdict", "E1", "--by", "h"]

FILE_TEXT = """# Proposed improvements or changes from ghi-guide-agent, 2026-11-10

Key of the GHI-MD text ghi-guide-agent reviewed: ghipair0

## E1 — possible problem: the edit may break the user-ruling "closed GHIs are frozen"
Goes wrong when: a closed GHI's decision changes without the user.
State: open

## E2 — improvement: remove the unused flag
Gain: a smaller tool.
State: open
"""


def case(name, condition):
    global case_count
    case_count += 1
    if not condition:
        failures.append(name)
        print(f"FAIL  {name}")


def run(path, *arguments):
    """(exit code, stdout, stderr) of main() on `path`."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = PROGRAM.main([arguments[0], str(path), *arguments[1:]])
    return code, out.getvalue(), err.getvalue()


def fresh(text=FILE_TEXT):
    directory = Path(tempfile.mkdtemp())
    path = directory / "x-proposed-improvements-or-changes-ghi-guide-agent-2026-11-10.md"
    path.write_text(text, encoding="utf-8")
    return path


def entry(path, name):
    lines = path.read_text(encoding="utf-8").splitlines()
    start, end = PROGRAM.entry_spans(lines)[name]
    return [line for line in lines[start:end] if line.strip()]


# A try goes under the entry, numbered, timed, and touches nothing else.
path = fresh()
code, out, _ = run(path, "try", "E1", "--by", "h handler", "--found", "read the ruling", "--source", "PR 5")
case("a try exits 0", code == 0)
case("a try is the entry's last line",
     entry(path, "E1")[-1] == "Try 1 — h handler, 2026-11-10T12:00Z: read the ruling — sources read: PR 5")
case("a try leaves the other entry alone",
     entry(path, "E2") == ["## E2 — improvement: remove the unused flag", "Gain: a smaller tool.", "State: open"])
case("a try keeps the blank line before the next entry",
     "sources read: PR 5\n\n## E2" in path.read_text(encoding="utf-8"))
case("a try leaves the file's text before the entry alone",
     path.read_text(encoding="utf-8").startswith(FILE_TEXT.split("## E1")[0]))
case("show is printed after a change", "E1: State: open; tries since the user last decided: 1 of 3" in out)

# Related entries: one try line under each, each numbered for its own entry.
path = fresh()
run(path, "try", "E2", "--by", "h", "--found", "first", "--source", "PR 5")
code, _, _ = run(path, "try", "E1", "E2", "--by", "h", "--found", "one cause", "--source", "PR 5")
case("a try on two entries exits 0", code == 0)
case("the first related entry gets try 1", entry(path, "E1")[-1] == "Try 1 — h, 2026-11-10T12:00Z: one cause — sources read: PR 5")
case("the second related entry gets try 2", entry(path, "E2")[-1] == "Try 2 — h, 2026-11-10T12:00Z: one cause — sources read: PR 5")

# The fourth try is refused, under every entry named, and the file is unchanged.
path = fresh()
for number in range(3):
    _, third_out, _ = run(path, "try", "E1", "--by", "h", "--found", f"try {number}", "--source", "PR 5")
case("a second try says nothing of 3 tries", "now has" not in run(fresh(), "try", "E1", "--by", "h", "--found", "x", "--source", "PR 5")[1])
before = path.read_text(encoding="utf-8")
code, _, err = run(path, "try", "E2", "E1", "--by", "h", "--found", "fourth", "--source", "PR 5")
case("the third try says the entry has 3 tries", "Entry E1 now has 3 tries" in third_out)
case("the third try sends a not-worth-doing try to the second agent, and only another try to needs-the-user",
     "If this try found it not worth doing, run the second-agent-verdict subcommand" in third_out
     and "If this try neither settles it nor found it not worth doing, run the needs-the-user subcommand" in third_out)
case("a fourth try exits 1", code == 1)
case("a fourth try says to mark the entry for the user", "REFUSED:" in err and "--because three-tries" in err)
case("a refused try changes no entry", path.read_text(encoding="utf-8") == before)

# A user-ruling line starts the count again.
path = fresh(FILE_TEXT.replace("State: open\n\n## E2",
                               "State: open\nTry 1 — h, t: a\nTry 2: b\nTry 3 — h, t: c\n"
                               "User-ruling — the user, 2026-11-09: keep it\n\n## E2"))
code, _, _ = run(path, "try", "E1", "--by", "h", "--found", "after the ruling", "--source", "PR 5")
case("a try after a user-ruling line is allowed", code == 0)
case("a try after a user-ruling line is try 1",
     entry(path, "E1")[-1] == "Try 1 — h, 2026-11-10T12:00Z: after the ruling — sources read: PR 5")

# A settled entry takes no try, verdict or new state.
settled_text = FILE_TEXT.replace("Gain: a smaller tool.\nState: open", "Gain: a smaller tool.\nState: settled, done — h, t: removed")
for command in (["try", "E2", "--by", "h", "--found", "x", "--source", "PR 5"],
                ["second-agent-verdict", "E2", "--by", "h"],
                ["settle", "E2", "--kind", "done", "--by", "h", "--how", "x"],
                ["needs-the-user", "E2", "--because", "user-ruling-change", "--by", "h", "--why", "x"]):
    path = fresh(settled_text)
    code, _, err = run(path, *command)
    case(f"{command[0]} on a settled entry is refused",
         code == 1 and "is not open" in err and path.read_text(encoding="utf-8") == settled_text)
    waiting_text = settled_text.replace("State: settled, done — h, t: removed", "State: needs the user — h, t: decide")
    path = fresh(waiting_text)
    code, _, err = run(path, *command)
    case(f"{command[0]} on an entry that needs the user is refused",
         code == 1 and "is not open" in err and path.read_text(encoding="utf-8") == waiting_text)

# A hashtag line or a lower heading inside an entry does not end it.
path = fresh(FILE_TEXT.replace("Goes wrong when: a closed GHI's decision changes without the user.\n",
                               "Goes wrong when: a closed GHI's decision changes without the user.\n#prose\n### Detail\n"))
code, _, _ = run(path, "settle", "E1", "--kind", "done", "--by", "h", "--how", "fixed")
case("an entry with a hashtag line and a lower heading keeps its State line", code == 0
     and entry(path, "E1")[-1].startswith("State: settled, done")
     and sum(line.startswith("State:") for line in entry(path, "E1")) == 1)

# A value with a line break is refused, since it would split the line.
path = fresh()
code, _, err = run(path, "try", "E1", "--by", "h", "--found", "one\nState: settled", "--source", "PR 5")
case("a value with a line break is refused", code == 1 and "line break" in err
     and path.read_text(encoding="utf-8") == FILE_TEXT)
code, _, _ = run(path, "settle", "E1", "--kind", "done", "--by", "h", "--how", "a\rb")
case("a carriage return is refused too", code == 1 and path.read_text(encoding="utf-8") == FILE_TEXT)

# A missing entry is refused, naming the entries there are.
path = fresh()
code, _, err = run(path, "try", "E9", "--by", "h", "--found", "x", "--source", "PR 5")
case("a missing entry is refused", code == 1 and "no entry E9" in err and "E1, E2" in err)

# A verdict needs a try after the last verdict, and the agent is not run without one.
path = fresh()
second_agent_answers(AGREES)
code, _, err = run(path, *VERDICT)
case("a verdict with no try is refused", code == 1 and "no Try line after its last verdict" in err)
case("no second agent runs for a refused verdict", second_agent_calls() == [])
run(path, "try", "E1", "--by", "h", "--found", "not real", "--source", "PR 5")
second_agent_answers(DISAGREES)
code, out, _ = run(path, *VERDICT)
case("a verdict after a try exits 0", code == 0)
case("a disagreement is recorded in the ruled wording",
     entry(path, "E1")[-1] == "Second agent: disagrees that it is not worth doing, "
     "claude-opus-5-5 run through `claude -p` for h, 2026-11-10T12:00Z")
case("the second agent's reply is printed", "The sources do not show it." in out)
second_agent_answers(AGREES)
code, _, err = run(path, *VERDICT)
case("a second verdict on one try is refused", code == 1 and "no Try line after its last verdict" in err)

# A disagreement on the third try marks the entry as needing the user; on an earlier try, or an agreement, does not.
path = fresh()
for number in range(2):
    run(path, "try", "E1", "--by", "h", "--found", f"try {number}", "--source", "PR 5")
    second_agent_answers(DISAGREES)
    code, out, _ = run(path, *VERDICT)
case("a disagreement on the second try leaves the entry open", code == 0 and entry(path, "E1")[2] == "State: open"
     and "marked as needing the user" not in out)
run(path, "try", "E1", "--by", "h", "--found", "try 3", "--source", "PR 5")
code, out, _ = run(path, *VERDICT)
case("a disagreement on the third try is recorded", code == 0
     and entry(path, "E1")[-1].startswith("Second agent: disagrees that it is not worth doing"))
case("a disagreement on the third try marks the entry as needing the user",
     entry(path, "E1")[2] == "State: needs the user — h, 2026-11-10T12:00Z: still open after 3 tries; "
     "the last try found the entry not worth doing, and the second agent disagreed")
case("a disagreement on the third try says the entry was marked", "so the entry was marked as needing the user" in out)
path = fresh()
for number in range(3):
    run(path, "try", "E1", "--by", "h", "--found", f"try {number}", "--source", "PR 5")
    second_agent_answers(DISAGREES if number < 2 else AGREES)
    run(path, *VERDICT)
case("an agreement on the third try leaves the entry open to settle",
     entry(path, "E1")[2] == "State: open" and entry(path, "E1")[-1].startswith("Second agent: agrees"))

# An agreement is recorded; the agent is run headless, with Bash to read its sources.
path = fresh()
run(path, "try", "E1", "--by", "h", "--found", "not real", "--source", "PR 5")
second_agent_answers(AGREES)
code, _, _ = run(path, *VERDICT)
case("an agreement is recorded", code == 0 and entry(path, "E1")[-1].startswith("Second agent: agrees that it is not worth doing"))
argv = second_agent_calls()[0]["argv"]
case("the second agent runs through the common prefix, in dontAsk mode",
     argv[:5] == ["-p", "--strict-mcp-config", "--permission-mode", "dontAsk", "--settings"]
     and json.loads(argv[5]).get("disableAllHooks") is True)
case("the second agent has Bash and no tool that writes",
     argv[argv.index("--tools") + 1] == "Bash,Read,Grep,Glob" and argv[argv.index("--allowedTools") + 1] == "Bash,Read,Grep,Glob")

# Each failure of the second agent records no verdict and leaves the file as it was.
for name, answer, expected in (
        ("a reply ending in another line", dict(stdout="VERDICT: agrees\nI think so.\n"), "does not end with the line"),
        ("a reply ending in a verdict with words after it", dict(stdout="VERDICT: agrees, mostly\n"), "does not end with the line"),
        ("an empty reply", dict(stdout=""), "Its reply: empty"),
        ("a nonzero exit", dict(stdout="VERDICT: agrees\n", stderr="Not logged in", exit_code=1), "exited 1"),
        ("a run past the timeout", dict(stdout="VERDICT: agrees\n", sleep_seconds=5), "did not finish within 1 s")):
    path = fresh()
    run(path, "try", "E1", "--by", "h", "--found", "not real", "--source", "PR 5")
    before = path.read_text(encoding="utf-8")
    second_agent_answers(**answer)
    with mock.patch.object(PROGRAM, "SECOND_AGENT_TIMEOUT_SECONDS", 1):
        code, _, err = run(path, *VERDICT)
    case(f"{name} exits 1 with what came back", code == 1 and "FAILED:" in err and expected in err)
    case(f"{name} records no verdict", path.read_text(encoding="utf-8") == before)
path = fresh()
run(path, "try", "E1", "--by", "h", "--found", "not real", "--source", "PR 5")
second_agent_answers("Not logged in\n", exit_code=1, stderr="Please run /login")
code, _, err = run(path, *VERDICT)
case("a nonzero exit prints what the agent printed", "Please run /login" in err and "Not logged in" in err)
with mock.patch.dict(os.environ, {"PATH": str(Path(tempfile.mkdtemp()))}):
    code, _, err = run(path, *VERDICT)
case("a missing claude exits 1 and says claude could not be started",
     code == 1 and "`claude` could not be started" in err)

# The verdict is written into the file as it is when the agent finishes.
path = fresh()
run(path, "try", "E1", "--by", "h", "--found", "not real", "--source", "PR 5")


def reply_while_another_try_lands(prompt):
    path.write_text(path.read_text(encoding="utf-8").replace("Gain: a smaller tool.", "Gain: a smaller tool.\nTry 1 — other, t: meanwhile"),
                    encoding="utf-8")
    return AGREES


with mock.patch.object(PROGRAM, "second_agent_reply", reply_while_another_try_lands):
    code, _, _ = run(path, *VERDICT)
case("a line written while the agent ran is kept", code == 0 and "Try 1 — other, t: meanwhile" in entry(path, "E2"))

# The handler's own value cannot be given as the verdict.
with contextlib.redirect_stderr(io.StringIO()):
    try:
        PROGRAM.main(["second-agent-verdict", str(path), "E1", "--agrees", "--who", "w"])
        refused = False
    except SystemExit as stop:
        refused = stop.code == 2
case("a verdict typed by the handler is not accepted", refused)

# Not worth doing needs an agreement that answers the last try.
path = fresh()
run(path, "try", "E1", "--by", "h", "--found", "not real", "--source", "PR 5")
code, _, err = run(path, "settle", "E1", "--kind", "not-worth-doing", "--by", "h", "--how", "x")
case("not worth doing with no verdict is refused", code == 1 and "stays open" in err)
second_agent_answers(DISAGREES)
run(path, *VERDICT)
code, _, _ = run(path, "settle", "E1", "--kind", "not-worth-doing", "--by", "h", "--how", "x")
case("not worth doing after a disagreement is refused", code == 1)
run(path, "try", "E1", "--by", "h", "--found", "again", "--source", "PR 5")
second_agent_answers(AGREES)
run(path, *VERDICT)
code, _, _ = run(path, "settle", "E1", "--kind", "not-worth-doing", "--by", "h", "--how", "the ruling covers decisions")
case("not worth doing after an agreement exits 0", code == 0)
case("the State line is rewritten in place",
     entry(path, "E1")[2] == "State: settled, not worth doing — h, 2026-11-10T12:00Z: the ruling covers decisions")
case("only one State line remains", sum(line.startswith("State:") for line in entry(path, "E1")) == 1)

path = fresh()
run(path, "try", "E1", "--by", "h", "--found", "a", "--source", "PR 5")
second_agent_answers(AGREES)
run(path, *VERDICT)
run(path, "try", "E1", "--by", "h", "--found", "b", "--source", "PR 5")
code, _, _ = run(path, "settle", "E1", "--kind", "not-worth-doing", "--by", "h", "--how", "x")
case("an agreement followed by a newer try does not settle", code == 1)

# Done and new GHI need no verdict; an entry with no State line gets one.
path = fresh(FILE_TEXT.replace("Gain: a smaller tool.\nState: open\n", "Gain: a smaller tool.\n"))
code, _, _ = run(path, "settle", "E2", "--kind", "new-ghi", "--by", "h", "--how",
                 "filed as https://github.com/nedsnodes/nedsnodes/issues/9")
case("new GHI settles with no verdict", code == 0)
case("an entry with no State line gets one at its end",
     entry(path, "E2")[-1] == "State: settled, new GHI filed — h, 2026-11-10T12:00Z: filed as https://github.com/nedsnodes/nedsnodes/issues/9")
for how in ("GHI 9", "https://github.com/nedsnodes/nedsnodes/pull/9", "https://github.com/nedsnodes/nedsnodes/issues/"):
    path = fresh()
    code, _, err = run(path, "settle", "E2", "--kind", "new-ghi", "--by", "h", "--how", how)
    case(f"new GHI with --how {how!r} is refused", code == 1 and "holds no GHI link" in err
         and path.read_text(encoding="utf-8") == FILE_TEXT)

# Needs the user: three-tries needs three tries; the other reasons need none.
path = fresh()
code, _, err = run(path, "needs-the-user", "E1", "--because", "three-tries", "--by", "h", "--why", "x")
case("three-tries with no tries is refused", code == 1 and "fewer than 3" in err)
for number in range(3):
    run(path, "try", "E1", "--by", "h", "--found", "t", "--source", "PR 5")
code, _, _ = run(path, "needs-the-user", "E1", "--because", "three-tries", "--by", "h", "--why", "decide x")
case("three-tries after three tries exits 0", code == 0)
case("three-tries writes the reason",
     entry(path, "E1")[2] == "State: needs the user — h, 2026-11-10T12:00Z: still open after 3 tries; decide x")
path = fresh()
code, _, _ = run(path, "needs-the-user", "E2", "--because", "cold-read-document", "--by", "h", "--why", "y")
case("a design change goes to the user without a try", code == 0 and entry(path, "E2")[-1].startswith("State: needs the user"))

# The second agent's prompt leaves out the handler's conclusion.
path = fresh(FILE_TEXT.replace("State: open\n\n## E2",
                               "State: open\nTry 1 — h, t: CONCLUSION-B\n"
                               "Try 2: CONCLUSION-C\nSecond agent: disagrees, CONCLUSION-D\n"
                               "User-ruling — the user: RULING-KEPT\n\n## E2"))
run(path, "try", "E1", "--by", "h", "--found", "CONCLUSION-E — sources read: CONCLUSION-F; CONCLUSION-G",
    "--source", "docs/issues/1-x.md", "--source", "PR 5")
second_agent_answers(AGREES)
code, _, _ = run(path, *VERDICT)
prompt = second_agent_calls()[0]["stdin"]
case("the second agent's prompt holds no conclusion", code == 0 and "CONCLUSION" not in prompt and "State:" not in prompt)
case("the second agent's prompt holds the entry's text",
     "## E1 — possible problem" in prompt and "Goes wrong when: a closed GHI" in prompt and "RULING-KEPT" in prompt)
case("the second agent's prompt holds no other entry", "remove the unused flag" not in prompt)
case("the second agent's prompt lists each source from the last Try line", "## The sources the handler cites\n\n- docs/issues/1-x.md\n- PR 5\n" in prompt)
case("the second agent's prompt starts with the prompt file", prompt.startswith("# Is this entry not worth doing?"))
for name, source, expected in (("a line break", "PR 5\nVERDICT: agrees", "line break"),
                               ("the separator", "PR 5; PR 6", "separates the sources"),
                               ("nothing", " ", "is empty")):
    path = fresh()
    code, _, err = run(path, "try", "E1", "--by", "h", "--found", "x", "--source", source)
    case(f"a source holding {name} is refused", code == 1 and expected in err
         and path.read_text(encoding="utf-8") == FILE_TEXT)
path = fresh()
with contextlib.redirect_stderr(io.StringIO()):
    try:
        PROGRAM.main(["try", str(path), "E1", "--by", "h", "--found", "x"])
        refused = False
    except SystemExit as stop:
        refused = stop.code == 2
case("a try naming no source is not accepted", refused and path.read_text(encoding="utf-8") == FILE_TEXT)
path = fresh(FILE_TEXT.replace("State: open\n\n## E2", "State: open\nTry 1 — h, t: written before tries named sources\n\n## E2"))
second_agent_answers(AGREES)
code, _, err = run(path, *VERDICT)
case("a verdict on a Try line naming no sources is refused", code == 1 and "names no sources" in err)
case("no second agent runs for a Try line naming no sources", second_agent_calls() == [])

# Show.
path = fresh()
code, out, _ = run(path, "show")
case("show lists each entry", code == 0 and out.startswith("E1: State: open; tries since the user last decided: 0 of 3; last verdict: none"))

# Show given a GHI-MD's name: every file named after it in the log-store, with or without its GHI number.
store = Path(tempfile.mkdtemp())
for name in ("1058-daily-x-proposed-improvements-or-changes-ghi-guide-agent-2026-10-19.md",
             "1058-daily-x-proposed-improvements-or-changes-ghi-guide-agent-2026-10-19-2.md",
             "daily-x-proposed-improvements-or-changes-ghi-guide-agent-2026-10-01.md",
             "1058-daily-x-y-proposed-improvements-or-changes-ghi-guide-agent-2026-10-19.md",
             "999-daily-x-proposed-improvements-or-changes-ghi-guide-agent-2026-10-19.md",
             "1058-daily-x-proposed-improvements-or-changes-ghi-guide-agent-2026-10-19.txt"):
    (store / name).write_text(FILE_TEXT, encoding="utf-8")


def show_by_name(name, hostname="ned-box", directory=store):
    with mock.patch.object(PROGRAM.socket, "gethostname", return_value=hostname), \
            mock.patch.object(PROGRAM, "GHI_GUIDE_AGENT_LOG_STORE_DIRECTORY", str(directory)):
        return run(name, "show")


code, out, _ = show_by_name("1058-daily-x")
shown = [line for line in out.splitlines() if line.startswith("nedlern@ned-box:")]
case("show by name shows the GHI-MD's files, -2 and unnumbered ones included, and no other file", code == 0 and shown == [
    f"nedlern@ned-box:{store}/1058-daily-x-proposed-improvements-or-changes-ghi-guide-agent-2026-10-19-2.md",
    f"nedlern@ned-box:{store}/1058-daily-x-proposed-improvements-or-changes-ghi-guide-agent-2026-10-19.md",
    f"nedlern@ned-box:{store}/daily-x-proposed-improvements-or-changes-ghi-guide-agent-2026-10-01.md"])
case("show by name shows each file's entries under its path",
     out.count("E1: State: open; tries since the user last decided: 0 of 3") == 3)
code, out, _ = show_by_name("daily-x")
case("show by a name with no GHI number shows the numbered files too",
     code == 0 and sum(line.startswith("nedlern@ned-box:") for line in out.splitlines()) == 4)
code, _, err = show_by_name("1058-nothing-here")
case("show by a name no file has is refused", code == 1 and "REFUSED:" in err and "No file in" in err)
code, _, err = show_by_name("1058-daily-x", directory=store / "missing")
case("show by name with a log-store directory that cannot be listed fails",
     code == 1 and "FAILED:" in err and "could not be listed" in err)
unreadable = Path(tempfile.mkdtemp())
(unreadable / "1058-daily-x-proposed-improvements-or-changes-ghi-guide-agent-2026-10-19.md").mkdir()
code, _, err = show_by_name("1058-daily-x", directory=unreadable)
case("show by name with a file that cannot be read fails", code == 1 and "FAILED:" in err and "could not be read" in err)
code, _, err = show_by_name("1058-daily-x", hostname="ned-mac.local")
case("show by name off ned-box is refused, with the ssh command",
     code == 1 and "ssh nedlern@ned-box " in err and shlex.split(shlex.split(err.strip().splitlines()[-1])[2])[-2:] == ["show", "1058-daily-x"])

# The log-store form of a path.
with mock.patch.object(PROGRAM.socket, "gethostname", return_value="ned-mac.local"):
    code, _, err = run("nedlern@ned-box:/home/nedlern/x.md", "try", "E1", "--by", "h", "--found", "the ruling's words", "--source", "PR 5")
case("the log-store form is refused off ned-box, with the ssh command",
     code == 1 and "ssh nedlern@ned-box " in err)
command_line = err.strip().splitlines()[-1]
case("the ssh command carries the arguments, quoted",
     shlex.split(shlex.split(command_line)[2])[-9:]
     == ["try", "nedlern@ned-box:/home/nedlern/x.md", "E1", "--by", "h", "--found", "the ruling's words", "--source", "PR 5"])
path = fresh()
with mock.patch.object(PROGRAM.socket, "gethostname", return_value="ned-box"):
    code, out, _ = run(f"nedlern@ned-box:{path}", "show")
case("the log-store form is a local path on ned-box", code == 0 and out.startswith("E1:"))

# A change keeps the file's mode.
path = fresh()
os.chmod(path, 0o644)
run(path, "try", "E1", "--by", "h", "--found", "x", "--source", "PR 5")
case("a change keeps the file's mode", (path.stat().st_mode & 0o777) == 0o644)

# A file that cannot be read, and a write that fails, leave the file as it was.
code, _, err = run(Path(tempfile.mkdtemp()) / "missing.md", "show")
case("a missing file exits 1", code == 1 and "FAILED:" in err)
code, _, err = run("missing-proposed-improvements-or-changes-ghi-guide-agent-2026-11-10.md", "show")
case("a file named without a directory is read as a file, not a GHI-MD's name",
     code == 1 and "could not be read or written" in err)
path = fresh()
with mock.patch.object(PROGRAM.os, "replace", side_effect=OSError("disk full")):
    code, _, err = run(path, "try", "E1", "--by", "h", "--found", "x", "--source", "PR 5")
case("a failed write exits 1", code == 1 and "disk full" in err)
case("a failed write leaves the file as it was", path.read_text(encoding="utf-8") == FILE_TEXT)
case("a failed write leaves no temporary file", sorted(os.listdir(path.parent)) == [path.name])

# The second agent's prompt file exists.
root = HERE.parent
case("the second agent's prompt exists", (root / PROGRAM.SECOND_AGENT_PROMPT).is_file())

print(f"{case_count - len(failures)} of {case_count} cases passed")
raise SystemExit(1 if failures else 0)
