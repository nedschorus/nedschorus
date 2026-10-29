#!/usr/bin/env python3
"""Tests for ghi-md-whole-file-replacement-soft-block.py, the soft-block on
replacing the whole of an existing GHI-MD.

Each case builds a scratch checkout, a directory with a `.git/HEAD` file as
git leaves one, and drives the hook in-process through `main` with a payload,
the way Claude Code does. One case runs the file end to end as a subprocess,
so its imports by path are exercised as Claude Code loads them. No case runs
git or any command the hook reads.

Run: python3 .claude/hooks/ghi-md-whole-file-replacement-soft-block-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK_SCRIPT = Path(__file__).with_name("ghi-md-whole-file-replacement-soft-block.py")

_spec = importlib.util.spec_from_file_location("ghi_md_whole_file_replacement_soft_block",
                                               HOOK_SCRIPT)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def make_checkout(parent):
    checkout = Path(parent) / "checkout"
    (checkout / ".git").mkdir(parents=True)
    (checkout / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    issues = checkout / "docs" / "issues"
    (issues / "queue").mkdir(parents=True)
    (issues / "46-ghi-info-agent-design.md").write_text("# ghi-info\n")
    (issues / "queue" / "47-queued.md").write_text("# queued\n")
    (checkout / "docs" / "notes.md").write_text("# notes\n")
    (checkout / "cold-read-records" / "record" / "target" / "docs" / "issues").mkdir(parents=True)
    (checkout / "cold-read-records" / "record" / "target" / "docs" / "issues"
     / "46-ghi-info-agent-design.md").write_text("# frozen copy\n")
    (checkout / "draft").mkdir()
    (checkout / "draft" / "46-ghi-info-agent-design.md").write_text("# my copy\n")
    return checkout


def run_hook(payload_object):
    """Run the hook on one payload; return (exit code, parsed stdout or None)."""
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code = hook.main(stdin=io.StringIO(payload_object if isinstance(payload_object, str)
                                           else json.dumps(payload_object)))
    text = stdout.getvalue().strip()
    return code, (json.loads(text) if text else None)


def refusal_for(checkout, tool_name, tool_input, cwd=None):
    """The refusal text for one tool call, or None when the call passes."""
    code, output = run_hook({"tool_name": tool_name, "cwd": str(cwd or checkout),
                             "tool_input": tool_input})
    if code != 0:
        return f"<exit {code}>"
    if output is None:
        return None
    decision = output["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny", decision
    return decision["permissionDecisionReason"]


def bash_refusal(checkout, command, cwd=None):
    return refusal_for(checkout, "Bash", {"command": command}, cwd)


def expected_refusal(checkout):
    ghi_md = checkout / "docs" / "issues" / "46-ghi-info-agent-design.md"
    marker = checkout / ".ghi-md-whole-file-replacement-reason"
    return (
        f"Refused: this command replaces the whole GHI-MD {ghi_md}, which can undo changes "
        "merged into it on main after your copy was written.\n"
        "Change the GHI-MD with the Edit tool instead, one passage at a time, so main's other "
        "changes stay.\n"
        f"If you mean to replace the whole file, write your reason into {marker} and run the "
        "command again.")


with tempfile.TemporaryDirectory() as scratch:
    checkout = make_checkout(scratch)
    ghi_md = checkout / "docs" / "issues" / "46-ghi-info-agent-design.md"
    refusal = expected_refusal(checkout)
    marker = checkout / ".ghi-md-whole-file-replacement-reason"

    refused_commands = {
        "cp onto the GHI-MD": "cp draft/46-ghi-info-agent-design.md "
                              "docs/issues/46-ghi-info-agent-design.md",
        "cp with options onto the GHI-MD by absolute path": f"cp -fv draft/x.md {ghi_md}",
        "cp into docs/issues/ by directory, a source of the same name":
            "cp draft/46-ghi-info-agent-design.md docs/issues/",
        "cp -t docs/issues": "cp -t docs/issues draft/46-ghi-info-agent-design.md",
        "cp --target-directory=docs/issues":
            "cp --target-directory=docs/issues draft/46-ghi-info-agent-design.md",
        "cp with the target directory attached, -tDIR":
            "cp -tdocs/issues draft/46-ghi-info-agent-design.md",
        "cp -T onto the GHI-MD": "cp -T draft/46-ghi-info-agent-design.md "
                                 "docs/issues/46-ghi-info-agent-design.md",
        "cp with --suffix taking the next word":
            "cp --suffix .old draft/x.md docs/issues/46-ghi-info-agent-design.md",
        "cp after --": "cp -- draft/x.md docs/issues/46-ghi-info-agent-design.md",
        "mv onto the GHI-MD": "mv draft/46-ghi-info-agent-design.md "
                              "docs/issues/46-ghi-info-agent-design.md",
        "mv -S taking the next word":
            "mv -S .bak draft/x.md docs/issues/46-ghi-info-agent-design.md",
        "tee onto the GHI-MD": "cat draft/x.md | tee docs/issues/46-ghi-info-agent-design.md",
        "tee with another option": "cat x | tee -i docs/issues/46-ghi-info-agent-design.md",
        "> redirection onto the GHI-MD": "cat draft/x.md > docs/issues/46-ghi-info-agent-design.md",
        ">| redirection": "cat x >| docs/issues/46-ghi-info-agent-design.md",
        "&> redirection": "cat x &> docs/issues/46-ghi-info-agent-design.md",
        "1> redirection": "cat x 1> docs/issues/46-ghi-info-agent-design.md",
        ">& redirection to a file": "cat x >& docs/issues/46-ghi-info-agent-design.md",
        "cp behind a wrapper": "timeout 5 cp x.md docs/issues/46-ghi-info-agent-design.md",
        "cp after a cd into the checkout":
            f"cd {checkout} && cp x.md docs/issues/46-ghi-info-agent-design.md",
        "cp after a cd into docs": "cd docs && cp ../x.md issues/46-ghi-info-agent-design.md",
        "cp in a later command of several": "true; cp x.md docs/issues/46-ghi-info-agent-design.md",
    }
    for case_name, command in refused_commands.items():
        got = bash_refusal(checkout, command)
        check(f"refused: {case_name}", got == refusal, got)
    got = bash_refusal(checkout, f"cd {checkout} && cp x.md docs/issues/46-ghi-info-agent-design.md",
                       cwd=scratch)
    check("refused: a cd that moves a session started elsewhere into the checkout",
          got == refusal, got)
    got = bash_refusal(checkout, "cp x.md checkout/docs/issues/46-ghi-info-agent-design.md",
                       cwd=scratch)
    check("refused: the marker file is at the checkout root even when the session sits outside "
          "a checkout", got == refusal, got)
    got = refusal_for(checkout, "Write", {"file_path": str(ghi_md), "content": "x"})
    check("refused: the Write tool on the GHI-MD", got == refusal, got)

    passed_commands = {
        "tee -a appends": "cat x | tee -a docs/issues/46-ghi-info-agent-design.md",
        "tee --append appends": "cat x | tee --append docs/issues/46-ghi-info-agent-design.md",
        "tee with -a in a cluster": "cat x | tee -ia docs/issues/46-ghi-info-agent-design.md",
        ">> appends": "cat x >> docs/issues/46-ghi-info-agent-design.md",
        "&>> appends": "cat x &>> docs/issues/46-ghi-info-agent-design.md",
        "2>&1 duplicates a descriptor": "cat docs/issues/46-ghi-info-agent-design.md 2>&1",
        ">&- closes a descriptor": "cat x >&-",
        "cp of the GHI-MD to another place":
            "cp docs/issues/46-ghi-info-agent-design.md draft/copy.md",
        "mv of the GHI-MD to another place":
            "mv docs/issues/46-ghi-info-agent-design.md draft/moved.md",
        "cp with one operand": "cp docs/issues/46-ghi-info-agent-design.md",
        "cp onto a new GHI-MD": "cp draft/x.md docs/issues/48-new-issue.md",
        "> onto a new GHI-MD": "echo x > docs/issues/48-new-issue.md",
        "cp into docs/issues/ of a source with a new name": "cp draft/48-new.md docs/issues/",
        "cp onto a queued file": "cp x.md docs/issues/queue/47-queued.md",
        "cp onto another markdown file": "cp x.md docs/notes.md",
        "cp onto a cold-read-record's frozen copy":
            "cp x.md cold-read-records/record/target/docs/issues/46-ghi-info-agent-design.md",
        "a GHI-MD path only as data": "echo 'cp x docs/issues/46-ghi-info-agent-design.md'",
        "cp -T onto docs/issues/ itself": "cp -T draft/x docs/issues",
        "cp after a cd whose directory is a variable":
            "cd $SOMEWHERE && cp x.md docs/issues/46-ghi-info-agent-design.md",
        "cp after cd -": "cd - && cp x.md docs/issues/46-ghi-info-agent-design.md",
        "cp -t whose directory follows an unknown cd":
            "cd $X && cp -t docs/issues draft/46-ghi-info-agent-design.md",
        "> after a cd whose directory is a variable":
            "cd $X && echo x > docs/issues/46-ghi-info-agent-design.md",
        "tee after a cd whose directory is a variable":
            "cd $X && echo x | tee docs/issues/46-ghi-info-agent-design.md",
        "an empty command": "",
    }
    for case_name, command in passed_commands.items():
        got = bash_refusal(checkout, command)
        check(f"passes: {case_name}", got is None, got)
    got = bash_refusal(checkout, "cp x.md docs/issues/46-ghi-info-agent-design.md", cwd=scratch)
    check("passes: a relative path that names no GHI-MD from the session's directory",
          got is None, got)
    got = bash_refusal(checkout, "(cd docs; true); cp x.md issues/46-ghi-info-agent-design.md")
    check("passes: a cd inside ( ... ) does not move the commands after it", got is None, got)
    got = bash_refusal(checkout, "cd; cp x.md docs/issues/46-ghi-info-agent-design.md")
    check("passes: a bare cd goes to the home directory, outside the checkout",
          got is None, got)

    more_refused_commands = {
        "tee after --": "cat x | tee -- docs/issues/46-ghi-info-agent-design.md",
        "cp with -S's value attached, holding a t":
            "cp -S.txt x.md docs/issues/46-ghi-info-agent-design.md",
        "cp inside ( ... ) after a cd there":
            "(cd docs && cp x.md issues/46-ghi-info-agent-design.md)",
        "cp in a child shell inside one that ran the cd":
            "(cd docs; (cp x.md issues/46-ghi-info-agent-design.md))",
        "cp after a command that is only an assignment":
            "X=1; cp x.md docs/issues/46-ghi-info-agent-design.md",
        "cp after cd -P, an option before the directory":
            "cd -P docs && cp x.md issues/46-ghi-info-agent-design.md",
    }
    for case_name, command in more_refused_commands.items():
        got = bash_refusal(checkout, command)
        check(f"refused: {case_name}", got == refusal, got)
    got = bash_refusal(checkout, "env cp docs/issues/46-ghi-info-agent-design.md")
    check("passes: cp behind a wrapper with one operand", got is None, got)
    for other_tool in ("Agent", "mcp__files__write"):
        got = refusal_for(checkout, other_tool, {
            "file_path": str(ghi_md), "command": "cp x.md docs/issues/46-ghi-info-agent-design.md"})
        check(f"passes: {other_tool}, a tool that is neither Bash nor Write, even with their "
              "fields", got is None, got)
    saved_directory = Path.cwd()
    try:
        import os
        os.chdir(checkout)
        code, output = run_hook({"tool_name": "Bash", "tool_input": {
            "command": "cp x.md docs/issues/46-ghi-info-agent-design.md"}})
    finally:
        os.chdir(saved_directory)
    got = output and output["hookSpecificOutput"].get("permissionDecisionReason")
    check("refused: a payload without cwd is read from the hook's own directory",
          code == 0 and got == refusal, (code, output))

    replay_check = Path(__file__).resolve().parents[2] / "nc-systems" / "general-tools" / (
        "bash-guards-verdict-changes-between-two-git-refs-on-transcript-recorded-commands-"
        "check.py")
    _replay_spec = importlib.util.spec_from_file_location("bash_guards_replay_check", replay_check)
    replay = importlib.util.module_from_spec(_replay_spec)
    _replay_spec.loader.exec_module(replay)
    marker.write_text("A reason the replay must not consume.\n")
    reading = replay.read_ghi_md_whole_file_replacement(
        hook, "cp x.md docs/issues/46-ghi-info-agent-design.md", str(checkout), None)
    check("the Bash-guard replay reads a refused command as refused, naming the GHI-MD",
          reading == ("refused", f"replaces {ghi_md}"), reading)
    check("the Bash-guard replay leaves the marker file in place", marker.exists())
    reading = replay.read_ghi_md_whole_file_replacement(
        hook, "cp x.md docs/notes.md", str(checkout), None)
    check("the Bash-guard replay reads a passed command as passed", reading == ("passed", None),
          reading)
    marker.unlink()

    got = refusal_for(checkout, "Edit", {"file_path": str(ghi_md), "old_string": "a",
                                         "new_string": "b"})
    check("passes: the Edit tool on the GHI-MD", got is None, got)
    got = refusal_for(checkout, "Write", {"file_path": str(checkout / "docs" / "issues"
                                                          / "48-new-issue.md")})
    check("passes: the Write tool on a new GHI-MD", got is None, got)
    got = refusal_for(checkout, "Write", {"file_path": str(checkout / "docs" / "notes.md")})
    check("passes: the Write tool on another markdown file", got is None, got)
    got = refusal_for(checkout, "Write", {})
    check("passes: a Write with no file path", got is None, got)
    got = refusal_for(checkout, "Read", {"file_path": str(ghi_md)})
    check("passes: a tool that is neither Bash nor Write", got is None, got)

    marker.write_text("Rewriting the whole file from scratch on purpose.\n")
    got = bash_refusal(checkout, "cp x.md docs/issues/46-ghi-info-agent-design.md")
    check("a reason in the marker file clears the rerun", got is None, got)
    check("the marker file is consumed by the call it clears", not marker.exists())
    got = bash_refusal(checkout, "cp x.md docs/issues/46-ghi-info-agent-design.md")
    check("the next rerun is refused again", got == refusal, got)
    marker.write_text("Writing the GHI-MD anew.\n")
    got = refusal_for(checkout, "Write", {"file_path": str(ghi_md)})
    check("a reason in the marker file clears a Write", got is None and not marker.exists(), got)
    marker.write_text("  \n")
    got = bash_refusal(checkout, "cp x.md docs/issues/46-ghi-info-agent-design.md")
    check("an empty marker file clears nothing", got == refusal, got)
    marker.unlink()

    code, output = run_hook("not json")
    check("a payload that is not JSON passes silently", code == 0 and output is None,
          (code, output))
    code, output = run_hook("[]")
    check("a payload that is not an object passes silently", code == 0 and output is None,
          (code, output))

    saved_simple_commands = hook.shell_reader.simple_commands

    def parser_missing(*arguments, **keywords):
        raise hook.shell_reader.ShellParserUnavailable("pip: no network")

    hook.shell_reader.simple_commands = parser_missing
    try:
        code, output = run_hook({"tool_name": "Bash", "cwd": str(checkout), "tool_input": {
            "command": "cp x.md docs/issues/46-ghi-info-agent-design.md"}})
    finally:
        hook.shell_reader.simple_commands = saved_simple_commands
    specific = (output or {}).get("hookSpecificOutput", {})
    check("without the shell parser the hook exits 0, lets the command through and says so",
          code == 0 and "permissionDecision" not in specific
          and "The GHI-MD whole-file replacement soft-block let this command through"
          in specific.get("additionalContext", "")
          and hook.PARSER_UNAVAILABLE_NEXT_STEP_LINES in specific.get("additionalContext", ""),
          (code, output))

    completed = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)], capture_output=True, text=True, timeout=120,
        input=json.dumps({"tool_name": "Bash", "cwd": str(checkout), "tool_input": {
            "command": "cp x.md docs/issues/46-ghi-info-agent-design.md"}}))
    end_to_end_reason = None
    if completed.returncode == 0 and completed.stdout.strip():
        end_to_end_reason = json.loads(completed.stdout)["hookSpecificOutput"].get(
            "permissionDecisionReason")
    check("end to end as a subprocess: the hook loads and refuses",
          end_to_end_reason == refusal, (completed.returncode, completed.stdout,
                                         completed.stderr))

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
