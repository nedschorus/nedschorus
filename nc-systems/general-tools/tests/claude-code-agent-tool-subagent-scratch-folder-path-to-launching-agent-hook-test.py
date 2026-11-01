#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/claude-code-agent-tool-subagent-scratch-folder-path-to-launching-agent-hook.py.

Each case runs the PreToolUse hook that makes the folder where the case needs a record,
then drives this hook's main() with the PostToolUse payload of the same call.

Run: python3 nc-systems/general-tools/tests/claude-code-agent-tool-subagent-scratch-folder-path-to-launching-agent-hook-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

HOOK_SCRIPT = (Path(__file__).resolve().parents[1]
               / "claude-code-agent-tool-subagent-scratch-folder-path-to-launching-agent-hook.py")
_spec = importlib.util.spec_from_file_location(
    "claude_code_agent_tool_subagent_scratch_folder_path_to_launching_agent_hook", HOOK_SCRIPT)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)
folder_maker = hook.folder_maker

SESSION_ID = "11111111-2222-3333-4444-555555555555"
PROJECT_SLUG = "-home-someone-project"
TOOL_USE_ID = "toolu_01AbCdEf"
temp_roots = []
failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def make_temp_root(make_user_temp_directory=True) -> Path:
    temp_root = Path(tempfile.mkdtemp(prefix="agent-scratch-folder-path-hook-test-"))
    temp_roots.append(temp_root)
    if make_user_temp_directory:
        (temp_root / f"claude-{os.getuid()}").mkdir()
    return temp_root


def payload(event, **overrides):
    base = {
        "session_id": SESSION_ID,
        "transcript_path": f"/home/someone/.claude/projects/{PROJECT_SLUG}/{SESSION_ID}.jsonl",
        "hook_event_name": event,
        "tool_name": "Agent",
        "tool_input": {"description": "Draft the PR", "prompt": "Do the work."},
        "tool_use_id": TOOL_USE_ID,
    }
    base.update(overrides)
    return base


def run(main, hook_payload, environment):
    stdout, stderr = io.StringIO(), io.StringIO()
    exit_code = main(io.StringIO(json.dumps(hook_payload)), stdout, stderr, environment)
    return exit_code, stdout.getvalue(), stderr.getvalue()


def record_path(temp_root):
    return (temp_root / f"claude-{os.getuid()}" / PROJECT_SLUG / SESSION_ID / "scratchpad"
            / folder_maker.RECORDED_FOLDER_PATHS_DIRECTORY_NAME / TOOL_USE_ID)


def test_launching_agent_told_the_folder_path():
    temp_root = make_temp_root()
    environment = {"CLAUDE_CODE_TMPDIR": str(temp_root)}
    _, pre_out, _ = run(folder_maker.main, payload("PreToolUse"), environment)
    folder = record_path(temp_root).read_text()
    exit_code, out, err = run(hook.main, payload("PostToolUse"), environment)
    context = json.loads(out)["hookSpecificOutput"]["additionalContext"] if out else ""
    check("launching agent told the folder path and the description",
          exit_code == 0 and err == "" and folder in context and "Draft the PR" in context
          and folder in json.loads(pre_out)["hookSpecificOutput"]["updatedInput"]["prompt"],
          f"{exit_code} {out!r} {err!r}")
    check("record removed once read", not record_path(temp_root).exists())


def test_no_record_stays_silent():
    temp_root = make_temp_root()
    exit_code, out, err = run(hook.main, payload("PostToolUse"), {"CLAUDE_CODE_TMPDIR": str(temp_root)})
    check("no record: silent", exit_code == 0 and out == "" and err == "", f"{exit_code} {out!r} {err!r}")


def test_scratchpad_not_found_stays_silent():
    temp_root = make_temp_root(make_user_temp_directory=False)
    exit_code, out, err = run(hook.main, payload("PostToolUse"), {"CLAUDE_CODE_TMPDIR": str(temp_root)})
    check("scratchpad not found: silent, since the PreToolUse hook reported it",
          exit_code == 0 and out == "" and err == "", f"{exit_code} {out!r} {err!r}")


def test_unusable_tool_use_id_stays_silent():
    temp_root = make_temp_root()
    exit_code, out, err = run(hook.main, payload("PostToolUse", tool_use_id=None),
                              {"CLAUDE_CODE_TMPDIR": str(temp_root)})
    check("unusable tool_use_id: silent, since the PreToolUse hook reported it",
          exit_code == 0 and out == "" and err == "", f"{exit_code} {out!r} {err!r}")


def test_unreadable_record_reported():
    temp_root = make_temp_root()
    record_path(temp_root).mkdir(parents=True)
    exit_code, out, err = run(hook.main, payload("PostToolUse"), {"CLAUDE_CODE_TMPDIR": str(temp_root)})
    check("unreadable record: reported on stderr with exit 1",
          exit_code == 1 and out == "" and "not told" in err, f"{exit_code} {out!r} {err!r}")


if __name__ == "__main__":
    try:
        for name, function in list(globals().items()):
            if name.startswith("test_") and callable(function):
                function()
    finally:
        for temp_root in temp_roots:
            shutil.rmtree(temp_root, ignore_errors=True)
    sys.exit(1 if failures else 0)
