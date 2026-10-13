#!/usr/bin/env python3
"""Tests for the search guard (search-file-argument-read-as-option-guard-hook.py).

Every case runs in a scratch folder shaped like ~/.claude/projects: a folder
named after a path, `-Users-el-agents-x`, and an ordinary one, `plain`, each
holding one .jsonl file that contains the searched word.

The first cases run the REAL programs on that folder, before any case tests
the guard, so the refusal is shown to answer a real misreading: the search
`-l needle */*.jsonl` must fail to list both files, and the same search with
`--` before the file names must list both. If a later grep stopped reading
`-Users-el-agents-x/a.jsonl` as options, these cases would fail and say the
guard's premise had gone.

Run: python3 scripts/search-file-argument-read-as-option-guard-hook-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import importlib.util
import io
import json
import re
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK_SCRIPT = Path(__file__).with_name("search-file-argument-read-as-option-guard-hook.py")

_spec = importlib.util.spec_from_file_location("search_guard", HOOK_SCRIPT)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)

DASH_FOLDER = "-Users-el-agents-x"
DASH_FILE = DASH_FOLDER + "/a.jsonl"
PLAIN_FILE = "plain/b.jsonl"

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def make_scratch_projects_folder():
    scratch = Path(tempfile.mkdtemp(prefix="search-guard-test-"))
    (scratch / DASH_FOLDER).mkdir()
    (scratch / "plain").mkdir()
    (scratch / DASH_FILE).write_text('{"text": "needle here"}\n')
    (scratch / PLAIN_FILE).write_text('{"text": "needle too"}\n')
    return scratch


LET_THROUGH_MESSAGES = []


def run_main(command, cwd, clock=None):
    """Drive main() as the harness does; return the refusal text or None.

    A message that lets the command through is kept in LET_THROUGH_MESSAGES.
    """
    payload = {"tool_name": "Bash", "cwd": str(cwd),
               "tool_input": {"command": command}}
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        if clock is None:
            code = guard.main(stdin=io.StringIO(json.dumps(payload)))
        else:
            code = guard.main(stdin=io.StringIO(json.dumps(payload)), clock=clock)
    text = stdout.getvalue().strip()
    if code != 0:
        return f"<exit {code}>"
    if not text:
        return None
    output = json.loads(text)["hookSpecificOutput"]
    if "permissionDecision" not in output:
        LET_THROUGH_MESSAGES.append(output["additionalContext"])
        return None
    assert output["permissionDecision"] == "deny", output
    return output["permissionDecisionReason"]


def run_in_shell(command, cwd):
    """Run a command the way the agent's shell would, glob expansion included."""
    return subprocess.run(["/bin/sh", "-c", command], cwd=str(cwd),
                          capture_output=True, text=True, check=False)


scratch = make_scratch_projects_folder()
try:
    # -----------------------------------------------------------------------
    # The shared shell module is really imported, not copied.
    # -----------------------------------------------------------------------
    check("the guard reads commands with the shared shell module",
          guard.shell_reader.__name__ == "shell_command_tree_sitter_bash_reader_common"
          and guard.read_simple_commands("grep x *")[0][:2] == ["grep", "x"])

    # -----------------------------------------------------------------------
    # The misreading, on the real programs, before the guard is tested.
    # -----------------------------------------------------------------------
    search_programs = [("grep", shutil.which("grep")), ("rg", shutil.which("rg"))]
    for name, path in search_programs:
        if path is None:
            print(f"SKIP  {name} reproduction: {name} is not on PATH here")
            continue
        broken = run_in_shell(f"{path} -l needle */*.jsonl", scratch)
        fixed = run_in_shell(f"{path} -l needle -- */*.jsonl", scratch)
        listed_by_broken = set(broken.stdout.split())
        listed_by_fixed = set(fixed.stdout.split())
        check(f"REPRODUCTION: real {name} reads the expanded {DASH_FILE} as "
              "options and does not list both files",
              {DASH_FILE, PLAIN_FILE} - listed_by_broken,
              f"exit {broken.returncode}, stdout {broken.stdout!r}, "
              f"stderr {broken.stderr!r}")
        check(f"REPRODUCTION: real {name} with -- before the files lists both",
              {DASH_FILE, PLAIN_FILE} <= listed_by_fixed,
              f"exit {fixed.returncode}, stdout {fixed.stdout!r}, "
              f"stderr {fixed.stderr!r}")

    # -----------------------------------------------------------------------
    # Refused: the glob forms that expand to a name beginning with -.
    # -----------------------------------------------------------------------
    refusal = run_main("grep -l needle */*.jsonl", scratch)
    check("the 22 September shape is refused with the exact accepted command",
          refusal == (
              "Refused: */*.jsonl expands to names beginning with -, such as "
              f"{DASH_FILE}, which grep reads as options, not as files. Put -- "
              "before the file names and run: grep -l needle -- */*.jsonl"),
          repr(refusal))

    accepted_command = refusal.rsplit("run: ", 1)[1] if refusal else ""
    accepted_run = run_in_shell(accepted_command, scratch) if accepted_command else None
    check("the command the refusal gives finds what was meant",
          accepted_run is not None
          and {DASH_FILE, PLAIN_FILE} <= set(accepted_run.stdout.split()),
          repr(accepted_run))
    check("the command the refusal gives passes the guard",
          accepted_command and run_main(accepted_command, scratch) is None,
          accepted_command)

    for command in [
        "grep -l needle *",
        "grep -rl needle */*.jsonl 2>/dev/null | head -5",
        "rg -l needle */*.jsonl",
        "ugrep -l needle */*.jsonl",
        "egrep -l needle */*.jsonl",
        "/usr/bin/grep -l needle */*.jsonl",
        "timeout 10 grep -l needle */*.jsonl",
        "time grep -l needle */*.jsonl",
        "env LC_ALL=C grep -l needle */*.jsonl",
        "timeout --signal=KILL 10 grep -l needle */*.jsonl",
        "timeout --kill-after 5 10 grep -l needle */*.jsonl",
        "sudo -u nedlern grep -l needle */*.jsonl",
        "flock /tmp/search.lock grep -l needle */*.jsonl",
        "caffeinate -i grep -l needle */*.jsonl",
        "echo x | xargs -n 1 grep -l needle */*.jsonl",
        "LC_ALL=C grep -l needle */*.jsonl",
        "echo $(grep -l needle */*.jsonl)",
        "for x in a; do grep -l needle */*.jsonl; done",
        "grep -l needle -[U]*/*.jsonl",
        "grep -l needle plain/*.jsonl */*.jsonl",
        "if grep -q needle */*.jsonl; then echo found; fi",
        "while grep -q needle */*.jsonl; do break; done",
        "until grep -q needle */*.jsonl; do break; done",
        f"grep -l needle {DASH_FOLDER}/*.jsonl",
    ]:
        check(f"refused: {command}", run_main(command, scratch) is not None)

    # When the -- cannot be put into the whole command, the suggestion is the search alone,
    # with its redirections, so that running it does what the agent meant.
    real_whole_command = guard.command_with_double_dash_before_word
    guard.command_with_double_dash_before_word = lambda *arguments: None
    try:
        refusal = run_main("grep -l needle */*.jsonl 2>/dev/null", scratch)
    finally:
        guard.command_with_double_dash_before_word = real_whole_command
    check("the search-alone suggestion keeps the search's redirections",
          (refusal or "").endswith("run: grep -l needle -- */*.jsonl 2>/dev/null"), refusal)

    elsewhere = scratch / "plain"
    check("refused after a literal cd into the folder from elsewhere",
          run_main(f"cd {scratch} && grep -l needle */*.jsonl", elsewhere) is not None)
    check("refused after cd with a relative path",
          run_main("cd .. && grep -l needle */*.jsonl", elsewhere) is not None)

    # tree-sitter-bash folds a command bash runs in the parent shell into a pipeline
    # stage in two shapes; the cd before or on the line after the pipeline still counts.
    check("refused after a cd before a pipeline in which two stages have a redirection",
          run_main(f"cd {scratch} && ls 2>/dev/null | head 2>/dev/null | cat; "
                   f"grep -l needle */*.jsonl", elsewhere) is not None)
    check("refused after a redirected cd on the line after a pipeline of three stages",
          run_main(f"ls 2>&1 | tail -1 | sed s/a/b/\ncd {scratch} >/dev/null\n"
                   f"grep -l needle */*.jsonl", elsewhere) is not None)
    check("passes: a cd that is itself a pipeline stage runs in a child shell",
          run_main(f"cd {scratch} | cat; grep -l needle */*.jsonl", elsewhere) is None)

    # A command substitution runs in a shell of its own: a `cd` inside a
    # double-quoted one, or inside one in a heredoc body, moves that shell
    # and no other. The search after it still runs in the folder it ran in.
    for command in [
        'X="$(cd /tmp && pwd)"; grep -l needle */*.jsonl',
        'ROOT="$(cd "$(dirname "$0")" && pwd)"; grep -l needle */*.jsonl',
        "cat > /dev/null <<EOF\npath: $(cd /tmp && pwd)\nEOF\ngrep -l needle */*.jsonl",
        'git commit -m "$(cd /tmp; echo m)"; grep -l needle */*.jsonl',
    ]:
        check(f"refused: a cd inside a substitution does not move the search after it: "
              f"{command!r}", run_main(command, scratch) is not None)
    check("refused: a cd inside a quoted substitution moves the search in the same one",
          run_main(f'echo "$(cd {scratch} && grep -l needle */*.jsonl)"', elsewhere)
          is not None)
    check("passes: a cd inside a quoted substitution does not move the search after it",
          run_main(f'echo "$(cd {scratch})"; grep -l needle */*.jsonl', elsewhere) is None)

    # The globs this guard expands are the ones the shared reader reads as
    # unquoted, inside a double-quoted substitution too.
    check("refused: a search inside a double-quoted substitution",
          run_main('n="$(grep -l needle */*.jsonl)"', scratch) is not None)
    check("passes: a quoted glob inside a double-quoted substitution",
          run_main('n="$(grep -c "*/*.jsonl" notes.txt)"', scratch) is None)

    refusal = run_main("grep -l needle */*.jsonl -n", scratch)
    check("an option after the glob gets the instruction without a rebuilt command",
          refusal == (
              "Refused: */*.jsonl expands to names beginning with -, such as "
              f"{DASH_FILE}, which grep reads as options, not as files. Put -- "
              "after the last option and before the file names, then run the "
              "command again."),
          repr(refusal))

    refusal = run_main("grep -l needle 'my dir'/*.jsonl */*.jsonl", scratch)
    check("a quoted literal part is kept as the agent quoted it",
          refusal is not None
          and refusal.endswith("run: grep -l needle 'my dir'/*.jsonl -- */*.jsonl"),
          repr(refusal))

    # -----------------------------------------------------------------------
    # The command the refusal gives is the agent's own command, whole, with
    # `--` put in: run as written from the payload's folder, it finds what
    # the refused command meant.
    # -----------------------------------------------------------------------
    def command_given(command, cwd, clock=None):
        refusal = run_main(command, cwd, clock)
        return refusal.rsplit("run: ", 1)[1] if refusal and "run: " in refusal else None

    def files_listed(command, cwd):
        return set(run_in_shell(command, cwd).stdout.split())

    given = command_given(
        f"cd {scratch} && grep -l needle */*.jsonl 2>/dev/null | head -5", elsewhere)
    check("the command given keeps the cd and the pipe of the refused command",
          given == f"cd {scratch} && grep -l needle -- */*.jsonl 2>/dev/null | head -5",
          repr(given))
    check("run from the payload's own folder, that command lists both files",
          given is not None
          and {DASH_FILE, PLAIN_FILE} <= files_listed(given, elsewhere),
          repr(given))
    check("the guard passes that command from the payload's own folder",
          given is not None and run_main(given, elsewhere) is None, repr(given))

    for command, expected in [
        ("for x in a; do grep -l needle */*.jsonl; done",
         "for x in a; do grep -l needle -- */*.jsonl; done"),
        ("if true; then grep -l needle */*.jsonl; fi",
         "if true; then grep -l needle -- */*.jsonl; fi"),
        ("! grep -l needle */*.jsonl", "! grep -l needle -- */*.jsonl"),
        ("{ grep -l needle */*.jsonl; }", "{ grep -l needle -- */*.jsonl; }"),
        ('k=needle; grep -l "$k" */*.jsonl', 'k=needle; grep -l "$k" -- */*.jsonl'),
        ('FOO="$HOME" grep -l needle */*.jsonl',
         'FOO="$HOME" grep -l needle -- */*.jsonl'),
        ("grep -l needle */*.jsonl; grep -c needle */*.jsonl >/dev/null",
         "grep -l needle -- */*.jsonl; grep -c needle -- */*.jsonl >/dev/null"),
        ("cat <<'EOF'\ngrep -l needle */*.jsonl\nEOF\ngrep -l needle */*.jsonl",
         "cat <<'EOF'\ngrep -l needle */*.jsonl\nEOF\ngrep -l needle -- */*.jsonl"),
    ]:
        given = command_given(command, scratch)
        check(f"the command given for {command!r} is that command with -- put in",
              given == expected, repr(given))
        check(f"the command given for {command!r} lists both files and passes the guard",
              given is not None
              and {DASH_FILE, PLAIN_FILE} <= files_listed(given, scratch)
              and run_main(given, scratch) is None,
              repr(given))

    for command, expected in [
        ('grep -l needle "$PWD"/plain/b.jsonl */*.jsonl',
         'grep -l needle "$PWD"/plain/b.jsonl -- */*.jsonl'),
        ("grep -l needle {plain,nosuch}/*.jsonl */*.jsonl",
         "grep -l needle {plain,nosuch}/*.jsonl -- */*.jsonl"),
        (f"grep -l needle {DASH_FOLDER}/*.jsonl",
         f"grep -l needle -- {DASH_FOLDER}/*.jsonl"),
        (f'grep -l needle "{DASH_FOLDER}"/*.jsonl',
         f'grep -l needle -- "{DASH_FOLDER}"/*.jsonl'),
    ]:
        given = command_given(command, scratch)
        check(f"the command given for {command!r} is that command with -- put in",
              given == expected, repr(given))
        check(f"the command given for {command!r} lists the file under the "
              "folder named with a -",
              given is not None and DASH_FILE in files_listed(given, scratch),
              repr(given))

    # Out of budget before the place for -- is found, the refusal falls back
    # to the search's own words: the first two readings of the clock are the
    # start and the check before the glob is expanded.
    readings = iter([0.0, 0.0])
    given = command_given("for x in a; do grep -l needle */*.jsonl; done", scratch,
                          clock=lambda: next(readings, 1000.0))
    check("out of budget for the place, the search alone is given, without the keyword",
          given == "grep -l needle -- */*.jsonl", repr(given))

    # -----------------------------------------------------------------------
    # Passed.
    # -----------------------------------------------------------------------
    for command in [
        "grep -l needle -- */*.jsonl",
        "rg -l needle -- */*.jsonl",
        "grep -l needle '*/*.jsonl'",
        'grep -l needle "*/*.jsonl"',
        "grep -l needle \\*/\\*.jsonl",
        "grep -l needle ./*/*.jsonl",
        f"grep -l needle {scratch}/*/*.jsonl",
        "grep -l needle ~/*.nothing-here",
        "grep -rl needle --include=*.jsonl .",
        "grep -rl needle --include=sub/*.jsonl .",
        "grep -l needle plain/*.jsonl",
        "cd plain && grep -l needle *.jsonl",
        "ls */*.jsonl",
        "git grep -l needle",
        'git commit -m "grep -l needle */*.jsonl"',
        "echo hi # grep -l needle */*.jsonl",
        "cat <<'EOF'\ngrep -l needle */*.jsonl\nEOF",
        "git commit -F - <<EOF\nSearch with grep -l needle */*.jsonl fails.\nEOF",
        "grep needle",
    ]:
        check(f"passes: {command!r}", run_main(command, scratch) is None)

    # -----------------------------------------------------------------------
    # Lets the command through, and says why it was not checked.
    # -----------------------------------------------------------------------
    check("passes when a cd target cannot be resolved",
          run_main('cd "$SOMEWHERE" && grep -l needle */*.jsonl', scratch) is None)
    check("passes when the payload's folder does not exist",
          run_main("grep -l needle */*.jsonl", scratch / "no-such-folder") is None)

    ticks = iter(range(0, 10_000, 100))
    LET_THROUGH_MESSAGES.clear()
    check("passes when the expansion budget is spent, and says the limit stopped the check",
          run_main("grep -l needle */*.jsonl", scratch,
                   clock=lambda: float(next(ticks))) is None
          and len(LET_THROUGH_MESSAGES) == 1
          and "limit is deliberate; nothing failed" in LET_THROUGH_MESSAGES[0]
          and "Tell the user" not in LET_THROUGH_MESSAGES[0], LET_THROUGH_MESSAGES)
    real_analyze = guard.analyze_command_text
    for failure in (OSError("disk unreadable"), ValueError("bad value"), re.error("bad pattern")):
        def failing(*arguments, failure=failure, **keywords):
            raise failure
        guard.analyze_command_text = failing
        LET_THROUGH_MESSAGES.clear()
        try:
            refusal = run_main("grep -l needle */*.jsonl", scratch)
        finally:
            guard.analyze_command_text = real_analyze
        check(f"when the guard fails with {type(failure).__name__}, it lets the command through, "
              f"says it was not checked, quotes the error and says whom to tell",
              refusal is None and len(LET_THROUGH_MESSAGES) == 1
              and f"{type(failure).__name__}: {failure}" in LET_THROUGH_MESSAGES[0]
              and "without checking it" in LET_THROUGH_MESSAGES[0]
              and "Tell the user" in LET_THROUGH_MESSAGES[0], LET_THROUGH_MESSAGES)

    many = scratch / "many"
    many.mkdir()
    for number in range(300):
        (many / f"file-{number:03}.txt").write_text("needle\n")
    readings_taken = []

    def clock_past_the_budget_on_its_third_reading():
        readings_taken.append(None)
        return 0.0 if len(readings_taken) < 3 else 1000.0

    LET_THROUGH_MESSAGES.clear()
    check("passes when the budget is spent during a walk over 300 names",
          run_main("grep -l needle *", many,
                   clock=clock_past_the_budget_on_its_third_reading) is None)
    check("the budget is read during that walk, after the 256th name",
          len(readings_taken) == 3, str(len(readings_taken)))

    for raw in ["not json", json.dumps({"tool_name": "Edit"}),
                json.dumps({"tool_name": "Bash", "tool_input": {}}),
                json.dumps({"tool_name": "Bash", "tool_input": {"command": ""}}),
                json.dumps(["Bash"])]:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = guard.main(stdin=io.StringIO(raw))
        check(f"says nothing and exits 0 for {raw[:40]!r}",
              code == 0 and not stdout.getvalue().strip(),
              f"{code} {stdout.getvalue()!r}")

    # -----------------------------------------------------------------------
    # A refusal template cites no date, link, pull request or GHI.
    # -----------------------------------------------------------------------
    for template in (guard.REFUSAL_WITH_COMMAND_TEMPLATE,
                     guard.REFUSAL_WITHOUT_COMMAND_TEMPLATE):
        check("a refusal template carries no date, link or citation",
              "http" not in template and "20" not in template
              and "PR" not in template and "GHI" not in template,
              template)

    # -----------------------------------------------------------------------
    # End to end, as the harness runs it.
    # -----------------------------------------------------------------------
    result = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        input=json.dumps({"tool_name": "Bash", "cwd": str(scratch),
                          "tool_input": {"command": "grep -l needle */*.jsonl"}}),
        capture_output=True, text=True, check=False)
    decision = json.loads(result.stdout or "{}").get("hookSpecificOutput", {})
    check("run end-to-end, the 22 September shape is denied",
          result.returncode == 0 and decision.get("permissionDecision") == "deny",
          f"{result.returncode} {result.stdout!r} {result.stderr!r}")
    result = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        input=json.dumps({"tool_name": "Bash", "cwd": str(scratch),
                          "tool_input": {"command": "echo hello"}}),
        capture_output=True, text=True, check=False)
    check("run end-to-end, an ordinary command passes",
          result.returncode == 0 and not result.stdout.strip(),
          f"{result.returncode} {result.stdout!r} {result.stderr!r}")
finally:
    shutil.rmtree(scratch, ignore_errors=True)

# ---------------------------------------------------------------------------
# The wiring. A hook that overruns its registered timeout fails open silently,
# so the timeout in .claude/settings.json must stay above the guard's own
# expansion budget: the guard then always answers first.
# ---------------------------------------------------------------------------
SETTINGS_PATH = HOOK_SCRIPT.resolve().parent.parent / ".claude" / "settings.json"
settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
guard_entries = [
    hook
    for matcher_block in settings.get("hooks", {}).get("PreToolUse", [])
    if matcher_block.get("matcher") == "Bash"
    for hook in matcher_block.get("hooks", [])
    if HOOK_SCRIPT.name in hook.get("command", "")
]
check("the guard is wired exactly once as a PreToolUse Bash hook",
      len(guard_entries) == 1, str(guard_entries))
registered_timeout = guard_entries[0].get("timeout") if guard_entries else None
check("the registered timeout exceeds the guard's expansion budget",
      isinstance(registered_timeout, (int, float))
      and registered_timeout > guard.EXPANSION_BUDGET_SECONDS,
      f"timeout {registered_timeout} vs budget {guard.EXPANSION_BUDGET_SECONDS}")

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
