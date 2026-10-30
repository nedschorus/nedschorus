#!/usr/bin/env python3
"""Tests for emergency-stop-file-shown-and-push-and-merge-refusal-hook.py: what
it shows in each emergency-stop state, the once-per-agent-session notes, the
push-and-merge refusal and its exception for the coordinating agent-seat, and
the note it gives when it fails.

Every case drives output_for() or main() with a payload, the way Claude Code
does, against a temporary folder; one runs the file as a subprocess. None
touches the log-store. Run:
python3 nc-systems/skills/emergency-stop/emergency-stop-file-shown-and-push-and-merge-refusal-hook-test.py
Prints one line per case and exits non-zero if any case fails."""

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

HOOK = Path(__file__).with_name("emergency-stop-file-shown-and-push-and-merge-refusal-hook.py")
_spec = importlib.util.spec_from_file_location("emergency_stop_hook", HOOK)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def payload(event="UserPromptSubmit", command=None, session=None):
    value = {"hook_event_name": event, "session_id": session or uuid.uuid4().hex}
    if command is not None:
        value.update({"tool_name": "Bash", "tool_input": {"command": command}})
    return value


def decoded(output):
    return json.loads(output)["hookSpecificOutput"] if output else None


def main():
    pushes = ["git push", "git -C /x push origin b", "cd x && git push -u origin b", "gh pr merge 12 --squash",
              "FOO=1 git push", "/usr/bin/git push", "bash -c 'git push origin b'", "sudo git push"]
    not_pushes = ["git log --grep push", "git status", "echo git push-notes", "gh pr view 12", "git pushd"]
    check("push and merge commands are recognised", all(hook.bash_command_pushes_or_merges(c) for c in pushes),
          [c for c in pushes if not hook.bash_command_pushes_or_merges(c)])
    check("other commands are not", not any(hook.bash_command_pushes_or_merges(c) for c in not_pushes),
          [c for c in not_pushes if hook.bash_command_pushes_or_merges(c)])

    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        folder = root / "emergency-stop"
        environment = {"NEDSCHORUS_EMERGENCY_STOP_FOLDER": str(folder), "GIT_AUTHOR_NAME": "md-skills"}

        check("no stop: silent", hook.output_for(payload(), environment) is None)

        folder.mkdir()
        stop = folder / "2026-10-30T01-00-00Z.md"
        stop.write_text("# Emergency stop\ncoordinating agent-seat: reboot-test\n" + "x" * 9000 + "\n")
        shown = decoded(hook.output_for(payload(), environment))
        check("in force: rules and file shown on UserPromptSubmit",
              shown and "EMERGENCY STOP in force" in shown["additionalContext"]
              and "reboot-test" in shown["additionalContext"], shown)
        check("file cut to its limit", len(shown["additionalContext"]) < hook.MAX_FILE_CHARACTERS + 2000, None)

        shown = decoded(hook.output_for(payload("PreToolUse", "ls"), environment))
        check("in force: shown at PreToolUse", shown and shown["hookEventName"] == "PreToolUse"
              and "permissionDecision" not in shown, shown)

        refused = decoded(hook.output_for(payload("PreToolUse", "git push origin b"), environment))
        check("in force: push by another agent-seat refused",
              refused and refused["permissionDecision"] == "deny" and "md-skills" in refused["permissionDecisionReason"],
              refused)
        refused = decoded(hook.output_for(payload("PreToolUse", "git push"), {**environment, "GIT_AUTHOR_NAME": ""}))
        check("no agent-seat known: refused", refused and refused.get("permissionDecision") == "deny", refused)

        allowed = decoded(hook.output_for(payload("PreToolUse", "gh pr merge 5"),
                                          {**environment, "GIT_AUTHOR_NAME": "reboot-test"}))
        check("coordinating agent-seat may merge", allowed and "permissionDecision" not in allowed, allowed)

        original_reader = hook.shell_reader.simple_commands
        hook.shell_reader.simple_commands = lambda text, *rest: (_ for _ in ()).throw(
            hook.shell_reader.ShellCommandUnreadable("cannot parse"))
        try:
            refused = decoded(hook.output_for(payload("PreToolUse", "ls"), environment))
            allowed = decoded(hook.output_for(payload("PreToolUse", "ls"), {**environment, "GIT_AUTHOR_NAME": "reboot-test"}))
        finally:
            hook.shell_reader.simple_commands = original_reader
        check("unreadable command during a stop: refused, saying why",
              refused and refused.get("permissionDecision") == "deny"
              and "could not be read" in refused["permissionDecisionReason"], refused)
        check("unreadable command of the coordinating agent-seat: allowed",
              allowed and "permissionDecision" not in allowed, allowed)

        stop.write_bytes(b"\xff\xfe")
        refused = decoded(hook.output_for(payload("PreToolUse", "git push"),
                                          {**environment, "GIT_AUTHOR_NAME": "reboot-test"}))
        check("unreadable file: treated as in force, every push refused",
              refused and refused.get("permissionDecision") == "deny", refused)
        shown = decoded(hook.output_for(payload(), environment))
        check("unreadable file: says why", shown and "cannot be read" in shown["additionalContext"], shown)

        stop.write_text("started\n#emergency_stop_lifted all clear\n")
        session = uuid.uuid4().hex
        first = decoded(hook.output_for(payload(session=session), environment))
        second = hook.output_for(payload(session=session), environment)
        check("lifted: one note per agent-session", first and "was lifted" in first["additionalContext"]
              and second is None, (first, second))
        check("lifted: push allowed", hook.output_for(payload("PreToolUse", "git push", session), environment) is None)

        gone = {**environment, "NEDSCHORUS_EMERGENCY_STOP_FOLDER": str(root / "gone" / "emergency-stop")}
        session = uuid.uuid4().hex
        first = decoded(hook.output_for(payload(session=session), gone))
        second = hook.output_for(payload(session=session), gone)
        check("log-store unreachable: state unknown once, work continues",
              first and "emergency-stop state unknown" in first["additionalContext"] and second is None,
              (first, second))
        check("unsafe session id: note shown each time, nothing written",
              hook.note_record_path("../x") is None and hook.output_for(payload(session="../x"), gone) is not None)

        record = hook.note_record_path("unwritable-" + uuid.uuid4().hex)
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text("not json")
        check("unreadable note record: note shown again, not lost", hook.shown_before(record, "unknown") is False)
        record.unlink()

        broken = {**environment, "NEDSCHORUS_EMERGENCY_STOP_FOLDER": str(folder)}
        original = hook.common.read_state
        hook.common.read_state = lambda f: (_ for _ in ()).throw(RuntimeError("boom"))
        out = io.StringIO()
        try:
            sys_stdin = sys.stdin
            sys.stdin = io.StringIO(json.dumps(payload()))
            try:
                with contextlib.redirect_stdout(out):
                    status = hook.main()
            finally:
                sys.stdin = sys_stdin
        finally:
            hook.common.read_state = original
        shown = decoded(out.getvalue())
        check("hook failure: says so in context, exit 0",
              status == 0 and shown and "hook failed" in shown["additionalContext"], out.getvalue())

        stop.write_text("# Emergency stop\ncoordinating agent-seat: reboot-test\n")
        result = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload("PreToolUse", "git push")),
                                capture_output=True, text=True, env={**os.environ, **broken})
        check("runs as a program and refuses", result.returncode == 0
              and decoded(result.stdout)["permissionDecision"] == "deny", result)

    print(f"{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
