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
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK_SCRIPT = Path(__file__).with_name("search-file-argument-read-as-option-guard-hook.py")
KEYSTROKE_GUARD_SCRIPT = Path(__file__).with_name("synthetic-keystroke-guard-hook.py")

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


def run_main(command, cwd, clock=None):
    """Drive main() as the harness does; return the refusal text or None."""
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
    assert output["permissionDecision"] == "deny", output
    return output["permissionDecisionReason"]


def run_in_shell(command, cwd):
    """Run a command the way the agent's shell would, glob expansion included."""
    return subprocess.run(["/bin/sh", "-c", command], cwd=str(cwd),
                          capture_output=True, text=True, check=False)


scratch = make_scratch_projects_folder()
try:
    # -----------------------------------------------------------------------
    # The shared shell reader is really imported, not copied.
    # -----------------------------------------------------------------------
    _keystroke_spec = importlib.util.spec_from_file_location(
        "keystroke_guard_for_test", KEYSTROKE_GUARD_SCRIPT)
    keystroke_guard = importlib.util.module_from_spec(_keystroke_spec)
    _keystroke_spec.loader.exec_module(keystroke_guard)
    check("the guard uses the keystroke guard's tokenizer and heredoc split",
          guard.tokenize_simple_commands.__code__.co_code
          == keystroke_guard.tokenize_simple_commands.__code__.co_code
          and guard.split_out_heredocs.__code__.co_code
          == keystroke_guard.split_out_heredocs.__code__.co_code
          and guard.tokenize_simple_commands.__module__
          == "synthetic_keystroke_guard_hook")

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
        "env LC_ALL=C grep -l needle */*.jsonl",
        "LC_ALL=C grep -l needle */*.jsonl",
        "echo $(grep -l needle */*.jsonl)",
        "for x in a; do grep -l needle */*.jsonl; done",
        "grep -l needle -[U]*/*.jsonl",
        "grep -l needle plain/*.jsonl */*.jsonl",
    ]:
        check(f"refused: {command}", run_main(command, scratch) is not None)

    elsewhere = scratch / "plain"
    check("refused after a literal cd into the folder from elsewhere",
          run_main(f"cd {scratch} && grep -l needle */*.jsonl", elsewhere) is not None)
    check("refused after cd with a relative path",
          run_main("cd .. && grep -l needle */*.jsonl", elsewhere) is not None)

    refusal = run_main("grep -l needle */*.jsonl -n", scratch)
    check("an option after the glob gets the instruction without a rebuilt command",
          refusal == (
              "Refused: */*.jsonl expands to names beginning with -, such as "
              f"{DASH_FILE}, which grep reads as options, not as files. Put -- "
              "after the last option and before the file names, then run the "
              "command again."),
          repr(refusal))

    refusal = run_main("grep -l needle 'my dir'/*.jsonl */*.jsonl", scratch)
    check("a quoted literal part is kept quoted in the accepted command",
          refusal is not None
          and refusal.endswith("grep -l needle 'my dir/'*.jsonl -- */*.jsonl"),
          repr(refusal))

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
    # Fails open, silently.
    # -----------------------------------------------------------------------
    check("passes when a cd target cannot be resolved",
          run_main('cd "$SOMEWHERE" && grep -l needle */*.jsonl', scratch) is None)
    check("passes when the payload's folder does not exist",
          run_main("grep -l needle */*.jsonl", scratch / "no-such-folder") is None)

    ticks = iter(range(0, 10_000, 100))
    check("passes when the expansion budget is spent",
          run_main("grep -l needle */*.jsonl", scratch,
                   clock=lambda: float(next(ticks))) is None)

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
    # The refusal is instruction only.
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
