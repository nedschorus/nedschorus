#!/usr/bin/env python3
"""Tests for .claude/guard-hooks/handoff-deferral-cold-read-full-run-launch-refusal-hook.py.

Each case drives main() with a hook payload, as the harness does, against a handoff directory
of this suite's own, so no case reads or writes the real ~/.claude/handoffs.

Run: python3 .claude/guard-hooks/handoff-deferral-cold-read-full-run-launch-refusal-hook-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HOOK_SCRIPT = Path(__file__).resolve().with_name("handoff-deferral-cold-read-full-run-launch-refusal-hook.py")
_spec = importlib.util.spec_from_file_location("handoff_deferral_cold_read_full_run_launch_refusal_hook", HOOK_SCRIPT)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)
markers = hook.handoff_deferred_marker_and_refused_commands_files_common

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


SESSION_ID = "grid-refusal-hook-test-session"
GRID_COMMAND = "python3 nc-systems/cold-read/cold-read-grid.py --target docs/x.md > /tmp/grid.log 2>&1"


def run_main(command, handoff_directory, session_id=SESSION_ID, cwd="/work/checkout"):
    """Return (exit code, hookSpecificOutput or None)."""
    payload = {"tool_name": "Bash", "session_id": session_id, "cwd": cwd,
               "tool_input": {"command": command}}
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code = hook.main(stdin=io.StringIO(json.dumps(payload)), handoff_directory=handoff_directory)
    text = stdout.getvalue().strip()
    return code, (json.loads(text)["hookSpecificOutput"] if text else None)


def defer(handoff_directory, session_id=SESSION_ID):
    markers.handoff_deferred_marker_write(handoff_directory, session_id, markers.HandoffDeferredMarker(
        used_percentage=40.0, deferral_began_at=datetime.now(timezone.utc),
        awaited_subagent_ids=["a1"], awaited_background_task_ids=[], awaited_work_is_unknown=False))


def refused(output):
    return output is not None and output.get("permissionDecision") == "deny"


def command_cases():
    runs = [
        GRID_COMMAND,
        "nc-systems/cold-read/cold-read-grid.py --target docs/x.md",
        "cd /work && python3 -u nc-systems/cold-read/cold-read-grid.py --target a.md",
        "timeout 3600 python3 /home/u/nc-systems/cold-read/cold-read-grid.py --target a.md",
        "env FOO=1 nohup python3.12 -X dev nc-systems/cold-read/cold-read-grid.py --target a.md &",
        "bash -c 'python3 nc-systems/cold-read/cold-read-grid.py --target a.md'",
        "ssh nedlern@ned-box 'cd ~/p && python3 nc-systems/cold-read/cold-read-grid.py --target a.md'",
        "python3 -W ignore -X dev -B nc-systems/cold-read/cold-read-grid.py --target a.md",
    ]
    for command in runs:
        check(f"a command that runs the grid is a run: {command}",
              hook.command_runs_cold_read_grid_script(command))
    not_runs = [
        "sed -n 1,50p nc-systems/cold-read/cold-read-grid.py",
        "git log -- nc-systems/cold-read/cold-read-grid.py",
        "grep -n 'python3 nc-systems/cold-read/cold-read-grid.py' docs/*.md",
        "python3 nc-systems/cold-read/cold-read-grid.py --help",
        "python3 -m py_compile nc-systems/cold-read/cold-read-grid.py",
        "python3 -c 'print(1)' nc-systems/cold-read/cold-read-grid.py",
        "python3 - nc-systems/cold-read/cold-read-grid.py <<'EOF'\nimport ast, sys\nprint(ast.get_docstring(ast.parse(open(sys.argv[1]).read())))\nEOF",
        "python3 -I - nc-systems/cold-read/cold-read-grid.py < read-docstring.py",
        "python3 nc-systems/cold-read/cold-read-grid.py --target a.md -h",
        "nc-systems/cold-read/cold-read-grid.py -h",
        "python3 -u",
        "python3 -W nc-systems/cold-read/cold-read-grid.py other.py",
        "FOO=1",
        # A wrapper with no program after it runs nothing.
        "env",
        "timeout 3600",
        "bash -c 'echo nc-systems/cold-read/cold-read-grid.py'",
        "python3 nc-systems/cold-read/cold-read-fast-read.py --target a.md",
        "cat <<'EOF'\npython3 nc-systems/cold-read/cold-read-grid.py --target a.md\nEOF",
    ]
    for command in not_runs:
        check(f"a command that does not run the grid is not a run: {command!r}",
              not hook.command_runs_cold_read_grid_script(command))


def hook_cases(workspace):
    handoffs = Path(workspace) / "handoffs"

    code, output = run_main(GRID_COMMAND, handoffs)
    check("with no handoff-deferral the grid runs", code == 0 and output is None, output)
    check("with no handoff-deferral nothing is saved",
          markers.cold_read_full_run_commands_refused_during_handoff_deferral_read(handoffs, SESSION_ID) == [])

    defer(handoffs)
    code, output = run_main(GRID_COMMAND, handoffs)
    check("during a handoff-deferral the grid is refused with the approved text",
          code == 0 and refused(output)
          and output["permissionDecisionReason"] == hook.COLD_READ_FULL_RUN_REFUSED_AND_SAVED_REASON,
          output)
    saved = markers.cold_read_full_run_commands_refused_during_handoff_deferral_read(handoffs, SESSION_ID)
    check("the refused command is saved with its working directory for the handoff writer script",
          len(saved) == 1 and saved[0]["command"] == GRID_COMMAND
          and saved[0]["working_directory"] == "/work/checkout" and saved[0].get("refused_at"),
          saved)

    code, output = run_main("sed -n 1,9p nc-systems/cold-read/cold-read-grid.py", handoffs)
    check("during a handoff-deferral a command that only reads the grid runs",
          code == 0 and output is None, output)
    code, output = run_main("git status", handoffs)
    check("during a handoff-deferral an unrelated command runs", code == 0 and output is None, output)

    code, output = run_main(GRID_COMMAND, handoffs, session_id="another-session")
    check("another agent-session's handoff-deferral does not refuse this one's grid",
          code == 0 and output is None, output)

    # A refused command that cannot be saved is still refused, and handed to the agent instead.
    blocked = Path(workspace) / "blocked-handoffs"
    defer(blocked)
    markers.cold_read_full_run_commands_refused_during_handoff_deferral_path(blocked, SESSION_ID).mkdir()
    code, output = run_main(GRID_COMMAND, blocked)
    check("a refused command that cannot be saved is refused, and the refusal gives the command",
          code == 0 and refused(output)
          and "could not save the command" in output["permissionDecisionReason"]
          and GRID_COMMAND in output["permissionDecisionReason"]
          and "/work/checkout" in output["permissionDecisionReason"],
          output)

    # A marker file that cannot be looked up lets the command run, and says it was not checked.
    unreachable = Path(workspace) / "unreachable-handoffs"
    defer(unreachable)
    os.chmod(unreachable, 0o000)
    try:
        code, output = run_main(GRID_COMMAND, unreachable)
    finally:
        os.chmod(unreachable, 0o700)
    check("a marker file that cannot be looked up lets the grid run and says so",
          code == 0 and output is not None and "permissionDecision" not in output
          and "start unchecked" in output.get("additionalContext", "")
          and "cold-read-grid.py --target docs/x.md" in output.get("additionalContext", ""),
          output)
    check("a marker file that cannot be looked up names the command's working directory",
          output is not None and "directory /work/checkout" in output.get("additionalContext", ""),
          output)
    os.chmod(unreachable, 0o000)
    try:
        code, output = run_main(GRID_COMMAND, unreachable, cwd="")
    finally:
        os.chmod(unreachable, 0o700)
    check("a marker file that cannot be looked up, with no working directory given, says it was not given",
          output is not None and "directory not given" in output.get("additionalContext", ""),
          output)

    # An unavailable shell reader lets the command through, saying so.
    real_reader = hook.command_runs_cold_read_grid_script

    def reader_that_is_unavailable(_command):
        raise hook.shell_reader.ShellParserUnavailable("tree-sitter-bash is missing in this test")

    hook.command_runs_cold_read_grid_script = reader_that_is_unavailable
    try:
        code, output_text = 0, io.StringIO()
        with contextlib.redirect_stdout(output_text):
            code = hook.main(stdin=io.StringIO(json.dumps({
                "tool_name": "Bash", "session_id": SESSION_ID, "cwd": "/w",
                "tool_input": {"command": GRID_COMMAND}})), handoff_directory=handoffs)
    finally:
        hook.command_runs_cold_read_grid_script = real_reader
    check("an unavailable shell reader during a deferral lets the command run, says it was not "
          "checked, and gives the command to carry by hand",
          code == 0 and "deny" not in output_text.getvalue()
          and "tree-sitter-bash is missing in this test" in output_text.getvalue()
          and "cold-read-grid.py --target docs/x.md" in output_text.getvalue(),
          output_text.getvalue()[:300])

    hook.command_runs_cold_read_grid_script = reader_that_is_unavailable
    try:
        output_text = io.StringIO()
        with contextlib.redirect_stdout(output_text):
            code = hook.main(stdin=io.StringIO(json.dumps({
                "tool_name": "Bash", "session_id": "session-with-no-deferral", "cwd": "/w",
                "tool_input": {"command": GRID_COMMAND}})), handoff_directory=handoffs)
    finally:
        hook.command_runs_cold_read_grid_script = real_reader
    check("an unavailable shell reader with no deferral says nothing, since there is nothing to guard",
          code == 0 and not output_text.getvalue().strip(), output_text.getvalue()[:300])


def payload_cases(workspace):
    handoffs = Path(workspace) / "payload-handoffs"
    defer(handoffs)
    # A marker named for an empty session id, so a payload with no session id would be refused.
    defer(handoffs, session_id="")

    def silent(stdin_text):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = hook.main(stdin=io.StringIO(stdin_text), handoff_directory=handoffs)
        return code == 0 and not stdout.getvalue().strip()

    for label, stdin_text in (
            ("input that is not JSON", "{not json"),
            ("a JSON value that is not an object", json.dumps(["Bash"])),
            ("another tool", json.dumps({"tool_name": "Read", "session_id": SESSION_ID,
                                         "tool_input": {"command": GRID_COMMAND}})),
            # A name that sorts before "Bash", so only an exact comparison lets it through.
            ("another tool named before Bash", json.dumps({"tool_name": "Agent", "session_id": SESSION_ID,
                                                           "tool_input": {"command": GRID_COMMAND}})),
            ("a command that is not text", json.dumps({"tool_name": "Bash", "session_id": SESSION_ID,
                                                       "tool_input": {"command": ["x"]}})),
            ("a command that is a list naming the grid",
             json.dumps({"tool_name": "Bash", "session_id": SESSION_ID,
                         "tool_input": {"command": ["cold-read-grid.py"]}})),
            ("no session id", json.dumps({"tool_name": "Bash", "tool_input": {"command": GRID_COMMAND}})),
            ("an empty session id", json.dumps({"tool_name": "Bash", "session_id": "",
                                                "tool_input": {"command": GRID_COMMAND}}))):
        check(f"the hook lets {label} through without a word", silent(stdin_text), label)

    # Without a working directory, the refusal that could not save says so rather than leaving a gap.
    blocked = Path(workspace) / "payload-blocked-handoffs"
    defer(blocked)
    markers.cold_read_full_run_commands_refused_during_handoff_deferral_path(blocked, SESSION_ID).mkdir()
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        hook.main(stdin=io.StringIO(json.dumps({"tool_name": "Bash", "session_id": SESSION_ID,
                                                 "tool_input": {"command": GRID_COMMAND}})),
                  handoff_directory=blocked)
    check("a refusal that could not save, with no working directory given, says it was not given",
          "directory not given" in stdout.getvalue(), stdout.getvalue()[:400])

    # With the shell reader unavailable and the marker file beyond reach, the hook assumes a deferral.
    unreachable = Path(workspace) / "payload-unreachable"
    defer(unreachable)
    real_reader = hook.command_runs_cold_read_grid_script

    def reader_that_is_unavailable(_command):
        raise hook.shell_reader.ShellParserUnavailable("tree-sitter-bash is missing in this test")

    hook.command_runs_cold_read_grid_script = reader_that_is_unavailable
    os.chmod(unreachable, 0o000)
    try:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = hook.main(stdin=io.StringIO(json.dumps({
                "tool_name": "Bash", "session_id": SESSION_ID, "cwd": "/w",
                "tool_input": {"command": GRID_COMMAND}})), handoff_directory=unreachable)
    finally:
        os.chmod(unreachable, 0o700)
        hook.command_runs_cold_read_grid_script = real_reader
    check("an unavailable shell reader and an unreachable marker file still say the command was not checked",
          code == 0 and "tree-sitter-bash is missing in this test" in stdout.getvalue(),
          stdout.getvalue()[:300])


def marker_file_cases(workspace):
    handoffs = Path(workspace) / "marker-file-cases"
    handoffs.mkdir()
    path = markers.handoff_deferred_marker_path(handoffs, SESSION_ID)
    check("no marker file reads as no deferral",
          markers.handoff_deferred_marker_read(handoffs, SESSION_ID) is None)
    path.write_text("41.2\n", encoding="utf-8")
    try:
        markers.handoff_deferred_marker_read(handoffs, SESSION_ID)
        check("a marker file holding only a share is reported unreadable", False, "no exception")
    except markers.HandoffDeferredMarkerUnreadable as problem:
        check("a marker file holding only a share is reported unreadable", "41.2" in str(problem),
              str(problem))
    refused_path = markers.cold_read_full_run_commands_refused_during_handoff_deferral_path(handoffs, SESSION_ID)
    refused_path.write_text('{"command": "x"}\nnot json\n', encoding="utf-8")
    try:
        markers.cold_read_full_run_commands_refused_during_handoff_deferral_read(handoffs, SESSION_ID)
        check("a file of refused commands with a bad line is reported unreadable", False, "no exception")
    except markers.ColdReadFullRunCommandsRefusedDuringHandoffDeferralUnreadable as problem:
        check("a file of refused commands with a bad line is reported unreadable",
              "line 2" in str(problem), str(problem))

    def marker_read_problem(text):
        path.write_text(text, encoding="utf-8")
        try:
            markers.handoff_deferred_marker_read(handoffs, SESSION_ID)
            return None
        except markers.HandoffDeferredMarkerUnreadable as problem:
            return str(problem)

    good = {"used_percentage": 40.04, "deferral_began_at": "2026-10-28T20:12:00.000Z",
            "awaited_subagent_ids": ["a1"], "awaited_background_task_ids": ["b1"],
            "awaited_work_is_unknown": False, "awaited_workflow_ids": ["w1"]}
    for label, record in (
            ("a JSON value that is not an object", ["a list"]),
            ("a start time with no time zone", {**good, "deferral_began_at": "2026-10-28T20:12:00"}),
            ("an awaited subagent list that is not a list", {**good, "awaited_subagent_ids": "a1"}),
            ("an awaited background task list that is not a list",
             {**good, "awaited_background_task_ids": "b1"}),
            ("an awaited workflow list that is not a list", {**good, "awaited_workflow_ids": "w1"}),
            ("a record missing a field", {key: value for key, value in good.items()
                                          if key != "awaited_work_is_unknown"})):
        check(f"a marker file holding {label} is reported unreadable",
              marker_read_problem(json.dumps(record)) is not None, label)
    check("an empty marker file is reported unreadable, naming its empty first line",
          "its first line is ''" in (marker_read_problem("") or ""), marker_read_problem(""))
    path.write_text("{}", encoding="utf-8")
    os.chmod(path, 0o000)
    try:
        markers.handoff_deferred_marker_read(handoffs, SESSION_ID)
        unopenable = None
    except markers.HandoffDeferredMarkerUnreadable as problem:
        unopenable = str(problem)
    finally:
        os.chmod(path, 0o600)
    check("a marker file that cannot be opened is reported unreadable",
          unopenable is not None and "Permission denied" in unopenable, unopenable)

    # A record written is read back the same, its share rounded and its time to the millisecond.
    began_at = datetime(2026, 10, 28, 20, 12, 0, 123456, tzinfo=timezone.utc)
    markers.handoff_deferred_marker_write(handoffs, SESSION_ID, markers.HandoffDeferredMarker(
        used_percentage=40.04, deferral_began_at=began_at, awaited_subagent_ids=["a1"],
        awaited_background_task_ids=["b1"], awaited_work_is_unknown=True,
        awaited_workflow_ids=["w1"]))
    saved = json.loads(path.read_text(encoding="utf-8"))
    read_back = markers.handoff_deferred_marker_read(handoffs, SESSION_ID)
    check("a written marker record is what the file holds",
          saved == {"used_percentage": 40.0, "deferral_began_at": "2026-10-28T20:12:00.123Z",
                    "awaited_subagent_ids": ["a1"], "awaited_background_task_ids": ["b1"],
                    "awaited_work_is_unknown": True, "awaited_workflow_ids": ["w1"]}, saved)
    check("a written marker record reads back",
          read_back.deferral_began_at == began_at.replace(microsecond=123000)
          and read_back.awaited_subagent_ids == ["a1"]
          and read_back.awaited_background_task_ids == ["b1"]
          and read_back.awaited_workflow_ids == ["w1"]
          and read_back.awaited_work_is_unknown is True and read_back.used_percentage == 40.0,
          vars(read_back))
    check("a written marker record leaves no partial file behind",
          sorted(entry.name for entry in handoffs.iterdir() if entry.name.endswith(".partial")) == [])

    # A marker that cannot be replaced leaves no partial file behind, and raises.
    blocked = Path(workspace) / "marker-write-blocked"
    markers.handoff_deferred_marker_path(blocked, SESSION_ID).mkdir(parents=True)
    try:
        markers.handoff_deferred_marker_write(blocked, SESSION_ID, read_back)
        raised = False
    except OSError:
        raised = True
    check("a marker that cannot be replaced raises and leaves no partial file",
          raised and not any(entry.name.endswith(".partial") for entry in blocked.iterdir()),
          sorted(entry.name for entry in blocked.iterdir()))
    # A partial file that cannot be written raises the write's own error, not one from cleaning up.
    read_only = Path(workspace) / "marker-write-read-only"
    read_only.mkdir()
    os.chmod(read_only, 0o500)
    try:
        markers.handoff_deferred_marker_write(read_only, SESSION_ID, read_back)
        write_error = None
    except OSError as problem:
        write_error = problem
    finally:
        os.chmod(read_only, 0o700)
    check("a marker whose partial file cannot be written raises the write's permission error",
          isinstance(write_error, PermissionError), repr(write_error))
    # The share is kept to one decimal place, not rounded to a whole number.
    markers.handoff_deferred_marker_write(handoffs, SESSION_ID, markers.HandoffDeferredMarker(
        used_percentage=40.36, deferral_began_at=began_at, awaited_subagent_ids=[],
        awaited_background_task_ids=[], awaited_work_is_unknown=False))
    check("a written marker keeps the share to one decimal place",
          json.loads(path.read_text(encoding="utf-8"))["used_percentage"] == 40.4,
          path.read_text(encoding="utf-8"))
    # The directories are made when missing.
    fresh = Path(workspace) / "fresh" / "handoffs"
    markers.handoff_deferred_marker_write(fresh, SESSION_ID, read_back)
    markers.cold_read_full_run_command_refused_during_handoff_deferral_append(
        Path(workspace) / "fresh-refused" / "handoffs", SESSION_ID, "c", "/w")
    check("writes make a missing handoff directory",
          markers.handoff_deferred_marker_path(fresh, SESSION_ID).is_file()
          and markers.cold_read_full_run_commands_refused_during_handoff_deferral_path(
              Path(workspace) / "fresh-refused" / "handoffs", SESSION_ID).is_file())

    # The file of refused commands: blank lines skipped, a line that is not a command rejected,
    # and one that cannot be opened reported.
    refused_path.write_text('{"command": "one"}\n\n{"command": "two", "working_directory": "/w"}\n',
                            encoding="utf-8")
    entries = markers.cold_read_full_run_commands_refused_during_handoff_deferral_read(handoffs, SESSION_ID)
    check("a blank line in the file of refused commands is skipped, and the rest are read in order",
          [entry["command"] for entry in entries] == ["one", "two"], entries)
    for label, line in (("an object with no command", '{"working_directory": "/w"}'),
                        ("a command that is not text", '{"command": 3}'),
                        ("a JSON value that is not an object", '["one"]')):
        refused_path.write_text(line + "\n", encoding="utf-8")
        try:
            markers.cold_read_full_run_commands_refused_during_handoff_deferral_read(handoffs, SESSION_ID)
            rejected = False
        except markers.ColdReadFullRunCommandsRefusedDuringHandoffDeferralUnreadable:
            rejected = True
        check(f"a refused-command line holding {label} is reported unreadable", rejected, line)
    os.chmod(refused_path, 0o000)
    try:
        markers.cold_read_full_run_commands_refused_during_handoff_deferral_read(handoffs, SESSION_ID)
        refused_unopenable = None
    except markers.ColdReadFullRunCommandsRefusedDuringHandoffDeferralUnreadable as problem:
        refused_unopenable = str(problem)
    finally:
        os.chmod(refused_path, 0o600)
    check("a file of refused commands that cannot be opened is reported unreadable",
          refused_unopenable is not None and "Permission denied" in refused_unopenable,
          refused_unopenable)
    stamp = datetime(2026, 10, 30, 9, 0, 0, tzinfo=timezone.utc)
    refused_path.unlink()
    markers.cold_read_full_run_command_refused_during_handoff_deferral_append(
        handoffs, SESSION_ID, "cmd", "/w", now=stamp)
    check("a refused command is saved with the time it was refused",
          markers.cold_read_full_run_commands_refused_during_handoff_deferral_read(handoffs, SESSION_ID)
          == [{"command": "cmd", "working_directory": "/w", "refused_at": "2026-10-30T09:00:00.000Z"}])
    original_home = os.environ.get("HOME")
    os.environ["HOME"] = str(Path(workspace) / "a-home")
    try:
        check("the default handoff directory is ~/.claude/handoffs, read when called",
              markers.default_handoff_directory() == Path(workspace) / "a-home" / ".claude" / "handoffs",
              markers.default_handoff_directory())
    finally:
        os.environ["HOME"] = original_home


def main():
    command_cases()
    workspace = tempfile.mkdtemp(prefix="grid-refusal-hook-test-")
    try:
        hook_cases(workspace)
        payload_cases(workspace)
        marker_file_cases(workspace)
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
    print()
    if failures:
        print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
