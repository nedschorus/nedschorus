#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/claude-code-agent-tool-subagent-scratch-folder-make-and-prompt-write-scratch-only-here-line-add-hook.py.

Each case drives the hook's main() with an Agent-tool payload against a scratch temp
root laid out as Claude Code lays out its session directories.

Run: python3 nc-systems/general-tools/tests/claude-code-agent-tool-subagent-scratch-folder-make-and-prompt-write-scratch-only-here-line-add-hook-test.py
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
               / "claude-code-agent-tool-subagent-scratch-folder-make-and-prompt-write-scratch-only-here-line-add-hook.py")
_spec = importlib.util.spec_from_file_location(
    "claude_code_agent_tool_subagent_scratch_folder_make_and_prompt_write_scratch_only_here_line_add_hook",
    HOOK_SCRIPT)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

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
    temp_root = Path(tempfile.mkdtemp(prefix="agent-scratch-folder-hook-test-"))
    temp_roots.append(temp_root)
    if make_user_temp_directory:
        (temp_root / f"claude-{os.getuid()}").mkdir()
    return temp_root


def scratchpad_of(temp_root: Path) -> Path:
    return temp_root / f"claude-{os.getuid()}" / PROJECT_SLUG / SESSION_ID / "scratchpad"


def payload(**overrides):
    base = {
        "session_id": SESSION_ID,
        "transcript_path": f"/home/someone/.claude/projects/{PROJECT_SLUG}/{SESSION_ID}.jsonl",
        "cwd": "/somewhere/else",
        "hook_event_name": "PreToolUse",
        "tool_name": "Agent",
        "tool_input": {"description": "Clean worktrees extension", "prompt": "Do the work.",
                       "subagent_type": "general-purpose", "run_in_background": True},
        "tool_use_id": TOOL_USE_ID,
    }
    base.update(overrides)
    return base


def run_hook(hook_payload, environment):
    stdout, stderr = io.StringIO(), io.StringIO()
    exit_code = hook.main(io.StringIO(json.dumps(hook_payload)), stdout, stderr, environment)
    return exit_code, stdout.getvalue(), stderr.getvalue()


def test_folder_made_and_line_appended_and_path_recorded():
    temp_root = make_temp_root()
    exit_code, out, err = run_hook(payload(), {"CLAUDE_CODE_TMPDIR": str(temp_root)})
    check("happy path exits 0 silently", exit_code == 0 and err == "", f"{exit_code} {err!r}")
    output = json.loads(out)
    specific = output["hookSpecificOutput"]
    check("no permissionDecision, so the permission flow is unchanged",
          "permissionDecision" not in specific and "systemMessage" not in output, out)
    updated = specific["updatedInput"]
    folders = [p for p in scratchpad_of(temp_root).iterdir() if not p.name.startswith(".")]
    check("one folder made in the scratchpad", len(folders) == 1 and folders[0].is_dir(), str(folders))
    folder = folders[0]
    check("folder named from the description plus a suffix",
          folder.name.startswith("clean-worktrees-extension-")
          and len(folder.name) > len("clean-worktrees-extension-"), folder.name)
    expected_prompt = ("Do the work.\n\nWrite your scratch files, such as a draft pull request "
                       f"description, only under {folder}, a folder of your own.")
    check("prompt has the line appended", updated["prompt"] == expected_prompt, updated["prompt"])
    check("other input fields echoed back unchanged",
          {k: v for k, v in updated.items() if k != "prompt"}
          == {"description": "Clean worktrees extension", "subagent_type": "general-purpose",
              "run_in_background": True}, str(updated))
    record = scratchpad_of(temp_root) / hook.RECORDED_FOLDER_PATHS_DIRECTORY_NAME / TOOL_USE_ID
    check("folder path recorded under the tool_use_id",
          record.is_file() and record.read_text() == str(folder), str(record))


def test_two_calls_with_one_description_get_two_folders():
    temp_root = make_temp_root()
    environment = {"CLAUDE_CODE_TMPDIR": str(temp_root)}
    run_hook(payload(tool_use_id="toolu_a"), environment)
    run_hook(payload(tool_use_id="toolu_b"), environment)
    folders = [p for p in scratchpad_of(temp_root).iterdir() if not p.name.startswith(".")]
    check("two calls with one description get two folders", len(folders) == 2, str(folders))


def test_empty_description_uses_fallback_name():
    temp_root = make_temp_root()
    hook_payload = payload(tool_input={"description": "", "prompt": "x"})
    exit_code, out, _ = run_hook(hook_payload, {"CLAUDE_CODE_TMPDIR": str(temp_root)})
    folders = [p for p in scratchpad_of(temp_root).iterdir() if not p.name.startswith(".")]
    check("empty description gives the fallback name",
          exit_code == 0 and len(folders) == 1 and folders[0].name.startswith("subagent-"), str(folders))


def test_slug_lowercases_hyphenates_and_truncates():
    check("slug of punctuation and capitals",
          hook.folder_name_slug("  Fix PR #12: the Swap!! ") == "fix-pr-12-the-swap",
          hook.folder_name_slug("  Fix PR #12: the Swap!! "))
    long_slug = hook.folder_name_slug("word " * 40)
    check("slug truncated without a trailing hyphen",
          len(long_slug) <= hook.FOLDER_NAME_SLUG_MAXIMUM_LENGTH and not long_slug.endswith("-"), long_slug)
    check("slug of a description with no letters is the fallback",
          hook.folder_name_slug("!!!") == "subagent" and hook.folder_name_slug(None) == "subagent")


def test_system_temp_directory_used_when_variable_unset():
    temp_root = make_temp_root()
    saved = tempfile.tempdir
    tempfile.tempdir = str(temp_root)
    try:
        exit_code, out, err = run_hook(payload(), {})
    finally:
        tempfile.tempdir = saved
    check("without CLAUDE_CODE_TMPDIR the system temp directory is the root",
          exit_code == 0 and "updatedInput" in out, f"{exit_code} {err!r}")


def assert_passes_through_unchanged(case_name, exit_code, out, err, expected_in_err):
    check(case_name, exit_code == 1 and out == "" and expected_in_err in err, f"{exit_code} {out!r} {err!r}")


def test_missing_session_directory_lets_call_through():
    temp_root = make_temp_root(make_user_temp_directory=False)
    exit_code, out, err = run_hook(payload(), {"CLAUDE_CODE_TMPDIR": str(temp_root)})
    assert_passes_through_unchanged("missing claude-<uid> directory: call goes ahead unchanged",
                                    exit_code, out, err, "does not exist")
    check("missing claude-<uid> directory: nothing made",
          not (temp_root / f"claude-{os.getuid()}").exists())


def test_missing_transcript_path_lets_call_through():
    temp_root = make_temp_root()
    hook_payload = payload()
    del hook_payload["transcript_path"]
    exit_code, out, err = run_hook(hook_payload, {"CLAUDE_CODE_TMPDIR": str(temp_root)})
    assert_passes_through_unchanged("missing transcript_path: call goes ahead unchanged",
                                    exit_code, out, err, "transcript_path")


def test_missing_session_id_lets_call_through():
    temp_root = make_temp_root()
    exit_code, out, err = run_hook(payload(session_id=""), {"CLAUDE_CODE_TMPDIR": str(temp_root)})
    assert_passes_through_unchanged("missing session_id: call goes ahead unchanged",
                                    exit_code, out, err, "session_id")


def test_scratchpad_cannot_be_made_lets_call_through():
    temp_root = make_temp_root()
    scratchpad_of(temp_root).parent.mkdir(parents=True)
    scratchpad_of(temp_root).write_text("a file where the scratchpad should be")
    exit_code, out, err = run_hook(payload(), {"CLAUDE_CODE_TMPDIR": str(temp_root)})
    assert_passes_through_unchanged("scratchpad cannot be made: call goes ahead unchanged",
                                    exit_code, out, err, "could not make")


def test_folder_cannot_be_made_lets_call_through():
    temp_root = make_temp_root()
    saved = hook.tempfile.mkdtemp

    def failing_mkdtemp(*args, **kwargs):
        raise PermissionError(13, "Permission denied")
    hook.tempfile.mkdtemp = failing_mkdtemp
    try:
        exit_code, out, err = run_hook(payload(), {"CLAUDE_CODE_TMPDIR": str(temp_root)})
    finally:
        hook.tempfile.mkdtemp = saved
    assert_passes_through_unchanged("folder cannot be made: call goes ahead unchanged",
                                    exit_code, out, err, "Permission denied")


def test_tool_input_not_an_object_lets_call_through():
    temp_root = make_temp_root()
    exit_code, out, err = run_hook(payload(tool_input="text"), {"CLAUDE_CODE_TMPDIR": str(temp_root)})
    assert_passes_through_unchanged("tool_input not an object: call goes ahead unchanged",
                                    exit_code, out, err, "not an object")


def assert_folder_given_but_record_failure_reported(case_name, exit_code, out, err, expected_in_note):
    output = json.loads(out) if out else {}
    check(case_name,
          exit_code == 0 and "updatedInput" in output.get("hookSpecificOutput", {})
          and expected_in_note in output.get("systemMessage", "") and expected_in_note in err,
          f"{exit_code} {out!r} {err!r}")


def test_unusable_tool_use_id_still_gives_folder_and_reports():
    temp_root = make_temp_root()
    exit_code, out, err = run_hook(payload(tool_use_id="../escape"), {"CLAUDE_CODE_TMPDIR": str(temp_root)})
    assert_folder_given_but_record_failure_reported(
        "unusable tool_use_id: folder given, failure to record reported", exit_code, out, err, "tool_use_id")


def test_record_cannot_be_written_still_gives_folder_and_reports():
    temp_root = make_temp_root()
    scratchpad_of(temp_root).mkdir(parents=True)
    (scratchpad_of(temp_root) / hook.RECORDED_FOLDER_PATHS_DIRECTORY_NAME).write_text("a file, not a directory")
    exit_code, out, err = run_hook(payload(), {"CLAUDE_CODE_TMPDIR": str(temp_root)})
    assert_folder_given_but_record_failure_reported(
        "record cannot be written: folder given, failure reported", exit_code, out, err, "will not be told")


if __name__ == "__main__":
    try:
        for name, function in list(globals().items()):
            if name.startswith("test_") and callable(function):
                function()
    finally:
        for temp_root in temp_roots:
            shutil.rmtree(temp_root, ignore_errors=True)
    sys.exit(1 if failures else 0)
