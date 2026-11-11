#!/usr/bin/env python3
"""Cases for proposed-improvements-or-changes-file-entry-state-try-and-second-agent-verdict-lines-write.py.

Each case runs the program's main() on a file in a temporary directory, with
the time fixed, and checks the file's whole text and the exit code.

Run: scripts/proposed-improvements-or-changes-file-entry-state-try-and-second-agent-verdict-lines-write-test.py
Exit codes: 0 all passed, 1 any failed.
"""

import contextlib
import importlib.util
import io
import os
import shlex
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
code, out, _ = run(path, "try", "E1", "--by", "h handler", "--found", "read the ruling")
case("a try exits 0", code == 0)
case("a try is the entry's last line",
     entry(path, "E1")[-1] == "Try 1 — h handler, 2026-11-10T12:00Z: read the ruling")
case("a try leaves the other entry alone",
     entry(path, "E2") == ["## E2 — improvement: remove the unused flag", "Gain: a smaller tool.", "State: open"])
case("a try keeps the blank line before the next entry",
     "read the ruling\n\n## E2" in path.read_text(encoding="utf-8"))
case("a try leaves the file's text before the entry alone",
     path.read_text(encoding="utf-8").startswith(FILE_TEXT.split("## E1")[0]))
case("show is printed after a change", "E1: State: open; tries since the user last decided: 1 of 3" in out)

# Related entries: one try line under each, each numbered for its own entry.
path = fresh()
run(path, "try", "E2", "--by", "h", "--found", "first")
code, _, _ = run(path, "try", "E1", "E2", "--by", "h", "--found", "one cause")
case("a try on two entries exits 0", code == 0)
case("the first related entry gets try 1", entry(path, "E1")[-1] == "Try 1 — h, 2026-11-10T12:00Z: one cause")
case("the second related entry gets try 2", entry(path, "E2")[-1] == "Try 2 — h, 2026-11-10T12:00Z: one cause")

# The fourth try is refused, under every entry named, and the file is unchanged.
path = fresh()
for number in range(3):
    _, third_out, _ = run(path, "try", "E1", "--by", "h", "--found", f"try {number}")
case("a second try says nothing of 3 tries", "now has" not in run(fresh(), "try", "E1", "--by", "h", "--found", "x")[1])
before = path.read_text(encoding="utf-8")
code, _, err = run(path, "try", "E2", "E1", "--by", "h", "--found", "fourth")
case("the third try says the entry has 3 tries", "Entry E1 now has 3 tries" in third_out)
case("a fourth try exits 1", code == 1)
case("a fourth try says to mark the entry for the user", "REFUSED:" in err and "--because three-tries" in err)
case("a refused try changes no entry", path.read_text(encoding="utf-8") == before)

# A user-ruling line starts the count again.
path = fresh(FILE_TEXT.replace("State: open\n\n## E2",
                               "State: open\nTry 1 — h, t: a\nTry 2: b\nTry 3 — h, t: c\n"
                               "User-ruling — the user, 2026-11-09: keep it\n\n## E2"))
code, _, _ = run(path, "try", "E1", "--by", "h", "--found", "after the ruling")
case("a try after a user-ruling line is allowed", code == 0)
case("a try after a user-ruling line is try 1",
     entry(path, "E1")[-1] == "Try 1 — h, 2026-11-10T12:00Z: after the ruling")

# A settled entry takes no try, verdict or new state.
settled_text = FILE_TEXT.replace("Gain: a smaller tool.\nState: open", "Gain: a smaller tool.\nState: settled, done — h, t: removed")
for command in (["try", "E2", "--by", "h", "--found", "x"],
                ["second-agent-verdict", "E2", "--agrees", "--who", "w"],
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
code, _, err = run(path, "try", "E1", "--by", "h", "--found", "one\nState: settled")
case("a value with a line break is refused", code == 1 and "line break" in err
     and path.read_text(encoding="utf-8") == FILE_TEXT)
code, _, _ = run(path, "settle", "E1", "--kind", "done", "--by", "h", "--how", "a\rb")
case("a carriage return is refused too", code == 1 and path.read_text(encoding="utf-8") == FILE_TEXT)

# A missing entry is refused, naming the entries there are.
path = fresh()
code, _, err = run(path, "try", "E9", "--by", "h", "--found", "x")
case("a missing entry is refused", code == 1 and "no entry E9" in err and "E1, E2" in err)

# A verdict needs a try after the last verdict.
path = fresh()
code, _, err = run(path, "second-agent-verdict", "E1", "--agrees", "--who", "w")
case("a verdict with no try is refused", code == 1 and "no Try line after its last verdict" in err)
run(path, "try", "E1", "--by", "h", "--found", "not real")
code, _, _ = run(path, "second-agent-verdict", "E1", "--disagrees", "--who", "fresh subagent")
case("a verdict after a try exits 0", code == 0)
case("a disagreement is recorded in the ruled wording",
     entry(path, "E1")[-1] == "Second agent: disagrees that it is not worth doing, fresh subagent, 2026-11-10T12:00Z")
code, _, err = run(path, "second-agent-verdict", "E1", "--agrees", "--who", "w")
case("a second verdict on one try is refused", code == 1 and "no Try line after its last verdict" in err)

# Not worth doing needs an agreement that answers the last try.
path = fresh()
run(path, "try", "E1", "--by", "h", "--found", "not real")
code, _, err = run(path, "settle", "E1", "--kind", "not-worth-doing", "--by", "h", "--how", "x")
case("not worth doing with no verdict is refused", code == 1 and "stays open" in err)
run(path, "second-agent-verdict", "E1", "--disagrees", "--who", "w")
code, _, _ = run(path, "settle", "E1", "--kind", "not-worth-doing", "--by", "h", "--how", "x")
case("not worth doing after a disagreement is refused", code == 1)
run(path, "try", "E1", "--by", "h", "--found", "again")
run(path, "second-agent-verdict", "E1", "--agrees", "--who", "w")
code, _, _ = run(path, "settle", "E1", "--kind", "not-worth-doing", "--by", "h", "--how", "the ruling covers decisions")
case("not worth doing after an agreement exits 0", code == 0)
case("the State line is rewritten in place",
     entry(path, "E1")[2] == "State: settled, not worth doing — h, 2026-11-10T12:00Z: the ruling covers decisions")
case("only one State line remains", sum(line.startswith("State:") for line in entry(path, "E1")) == 1)

path = fresh()
run(path, "try", "E1", "--by", "h", "--found", "a")
run(path, "second-agent-verdict", "E1", "--agrees", "--who", "w")
run(path, "try", "E1", "--by", "h", "--found", "b")
code, _, _ = run(path, "settle", "E1", "--kind", "not-worth-doing", "--by", "h", "--how", "x")
case("an agreement followed by a newer try does not settle", code == 1)

# Done and new GHI need no verdict; an entry with no State line gets one.
path = fresh(FILE_TEXT.replace("Gain: a smaller tool.\nState: open\n", "Gain: a smaller tool.\n"))
code, _, _ = run(path, "settle", "E2", "--kind", "new-ghi", "--by", "h", "--how", "GHI 9")
case("new GHI settles with no verdict", code == 0)
case("an entry with no State line gets one at its end",
     entry(path, "E2")[-1] == "State: settled, new GHI filed — h, 2026-11-10T12:00Z: GHI 9")

# Needs the user: three-tries needs three tries; the other reasons need none.
path = fresh()
code, _, err = run(path, "needs-the-user", "E1", "--because", "three-tries", "--by", "h", "--why", "x")
case("three-tries with no tries is refused", code == 1 and "fewer than 3" in err)
for number in range(3):
    run(path, "try", "E1", "--by", "h", "--found", "t")
code, _, _ = run(path, "needs-the-user", "E1", "--because", "three-tries", "--by", "h", "--why", "decide x")
case("three-tries after three tries exits 0", code == 0)
case("three-tries writes the reason",
     entry(path, "E1")[2] == "State: needs the user — h, 2026-11-10T12:00Z: still open after 3 tries; decide x")
path = fresh()
code, _, _ = run(path, "needs-the-user", "E2", "--because", "cold-read-document", "--by", "h", "--why", "y")
case("a design change goes to the user without a try", code == 0 and entry(path, "E2")[-1].startswith("State: needs the user"))

# The second agent's input leaves out the handler's conclusion.
path = fresh(FILE_TEXT.replace("State: open\n\n## E2",
                               "State: settled, not worth doing — h, t: CONCLUSION-A\nTry 1 — h, t: CONCLUSION-B\n"
                               "Try 2: CONCLUSION-C\nSecond agent: disagrees, CONCLUSION-D\n"
                               "User-ruling — the user: RULING-KEPT\n\n## E2"))
code, out, _ = run(path, "second-agent-input", "E1", "--source", "docs/issues/1-x.md", "--source", "PR 5")
case("second-agent-input exits 0", code == 0)
case("second-agent-input holds no conclusion", "CONCLUSION" not in out)
case("second-agent-input holds the entry's text",
     "## E1 — possible problem" in out and "Goes wrong when: a closed GHI" in out and "RULING-KEPT" in out)
case("second-agent-input holds no other entry", "remove the unused flag" not in out)
case("second-agent-input lists each source", "- docs/issues/1-x.md\n- PR 5\n" in out)
case("second-agent-input starts with the prompt", out.startswith("# Is this entry not worth doing?"))

# Show.
path = fresh()
code, out, _ = run(path, "show")
case("show lists each entry", code == 0 and out.startswith("E1: State: open; tries since the user last decided: 0 of 3; last verdict: none"))

# The log-store form of a path.
with mock.patch.object(PROGRAM.socket, "gethostname", return_value="ned-mac.local"):
    code, _, err = run("nedlern@ned-box:/home/nedlern/x.md", "try", "E1", "--by", "h", "--found", "the ruling's words")
case("the log-store form is refused off ned-box, with the ssh command",
     code == 1 and "ssh nedlern@ned-box " in err)
command_line = err.strip().splitlines()[-1]
case("the ssh command carries the arguments, quoted",
     shlex.split(shlex.split(command_line)[2])[-7:]
     == ["try", "nedlern@ned-box:/home/nedlern/x.md", "E1", "--by", "h", "--found", "the ruling's words"])
path = fresh()
with mock.patch.object(PROGRAM.socket, "gethostname", return_value="ned-box"):
    code, out, _ = run(f"nedlern@ned-box:{path}", "show")
case("the log-store form is a local path on ned-box", code == 0 and out.startswith("E1:"))

# A change keeps the file's mode.
path = fresh()
os.chmod(path, 0o644)
run(path, "try", "E1", "--by", "h", "--found", "x")
case("a change keeps the file's mode", (path.stat().st_mode & 0o777) == 0o644)

# A file that cannot be read, and a write that fails, leave the file as it was.
code, _, err = run(Path(tempfile.mkdtemp()) / "missing.md", "show")
case("a missing file exits 1", code == 1 and "FAILED:" in err)
path = fresh()
with mock.patch.object(PROGRAM.os, "replace", side_effect=OSError("disk full")):
    code, _, err = run(path, "try", "E1", "--by", "h", "--found", "x")
case("a failed write exits 1", code == 1 and "disk full" in err)
case("a failed write leaves the file as it was", path.read_text(encoding="utf-8") == FILE_TEXT)
case("a failed write leaves no temporary file", sorted(os.listdir(path.parent)) == [path.name])

# The prompt the program prints exists.
root = HERE.parent
case("the second agent's prompt exists", (root / PROGRAM.SECOND_AGENT_PROMPT).is_file())

print(f"{case_count - len(failures)} of {case_count} cases passed")
raise SystemExit(1 if failures else 0)
