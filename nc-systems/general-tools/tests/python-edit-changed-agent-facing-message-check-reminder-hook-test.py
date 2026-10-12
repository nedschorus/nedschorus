#!/usr/bin/env python3
"""Tests for python-edit-changed-agent-facing-message-check-reminder-hook.py.

Run: python3 nc-systems/general-tools/tests/python-edit-changed-agent-facing-message-check-reminder-hook-test.py
Prints one line per case and exits non-zero if any case fails.

Each case runs the hook as Claude Code does, as a subprocess reading a
PostToolUse payload on stdin, against a throwaway repository under a temporary
directory. The variables that redirect git (GIT_DIR and its kin) are removed
from this process before any git runs.
"""

import difflib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

GENERAL_TOOLS = Path(__file__).resolve().parent.parent
REPOSITORY = GENERAL_TOOLS.parent.parent

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    REPOSITORY / "scripts" / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

HOOK_PATH = GENERAL_TOOLS / "python-edit-changed-agent-facing-message-check-reminder-hook.py"
PAGE_PATH = ("docs/nedschorus-wiki/"
             "nedschorus-how-to-write-the-refusal-warning-or-reminder-a-program-hands-an-agent.md")

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def git(repository, *arguments):
    subprocess.run(["git", *arguments], cwd=str(repository), check=True, capture_output=True, text=True)


def run_hook(payload):
    return subprocess.run([sys.executable, str(HOOK_PATH)], input=json.dumps(payload),
                          capture_output=True, text=True, timeout=60)


def structured_patch(before, after):
    """A structuredPatch in the format Claude Code puts in an Edit's tool_response:
    one hunk per changed region with three lines of context, newStart counted
    from 1, and each line prefixed " ", "-" or "+"."""
    old_lines, new_lines = before.splitlines(), after.splitlines()
    hunks = []
    for group in difflib.SequenceMatcher(None, old_lines, new_lines).get_grouped_opcodes(3):
        lines = []
        for tag, old_start, old_end, new_start, new_end in group:
            if tag == "equal":
                lines += [" " + line for line in old_lines[old_start:old_end]]
                continue
            lines += ["-" + line for line in old_lines[old_start:old_end]]
            lines += ["+" + line for line in new_lines[new_start:new_end]]
        hunks.append({"oldStart": group[0][1] + 1, "oldLines": group[-1][2] - group[0][1],
                      "newStart": group[0][3] + 1, "newLines": group[-1][4] - group[0][3],
                      "lines": lines})
    return hunks


def edit_then_run(cwd, file_path, before, old_string, new_string, tool_name="Edit"):
    after = before.replace(old_string, new_string, 1)
    file_path.write_text(after, encoding="utf-8")
    return run_hook({"session_id": "test", "cwd": str(cwd), "hook_event_name": "PostToolUse",
                     "tool_name": tool_name,
                     "tool_input": {"file_path": str(file_path), "old_string": old_string,
                                    "new_string": new_string},
                     "tool_response": {"filePath": str(file_path), "originalFile": before,
                                       "structuredPatch": structured_patch(before, after)}})


def write_then_run(cwd, file_path, content):
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    return run_hook({"session_id": "test", "cwd": str(cwd), "hook_event_name": "PostToolUse",
                     "tool_name": "Write",
                     "tool_input": {"file_path": str(file_path), "content": content},
                     "tool_response": {}})


def silent(result):
    return result.returncode == 0 and result.stdout.strip() == "" and result.stderr.strip() == ""


def agent_text(result):
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        return ""
    return parsed.get("hookSpecificOutput", {}).get("additionalContext", "")


COMMITTED_SOURCE = '''import sys

LIMIT = 3
REFUSAL_MESSAGE = "refused: the old reason."


def main():
    print("first message to the agent")
    sys.stderr.write("second message to the agent\\n")
    print("a message held "
          "on three lines "
          "of source")
    return LIMIT


print("last line message")
'''

# The lines every reminder must carry, each an instruction the agent acts on.
REMINDER_INSTRUCTION_LINES = (
    "Read that page now, unless you have already read the page in this agent-session, and "
    "check each message listed above against the page.",
    "If a message fails the page, rewrite that message in this turn, and update any test "
    "that asserts the message's text.",
    "If every listed message passes, carry on; nothing needs saying to the user.",
    "If your edit changed a message built another way, such as text put straight into a "
    "hook's JSON output, check that message against the page too.",
    "Before you write or change an agent-facing-message from now on, read the page first.",
)

with tempfile.TemporaryDirectory() as temporary:
    repository = Path(temporary) / "repository"
    repository.mkdir()
    git(repository, "init", "-q")
    check("the scratch repository is a repository at its own path",
          subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=repository, capture_output=True,
                         text=True).stdout.strip() == str(repository.resolve()))
    git(repository, "config", "user.email", "test@example.invalid")
    git(repository, "config", "user.name", "test")
    program = repository / "scripts" / "tool.py"
    program.parent.mkdir()
    program.write_text(COMMITTED_SOURCE, encoding="utf-8")
    git(repository, "add", "-A")
    git(repository, "commit", "-q", "-m", "fixture")

    def reset():
        program.write_text(COMMITTED_SOURCE, encoding="utf-8")

    reset()
    result = edit_then_run(repository, program, COMMITTED_SOURCE,
                           '"first message to the agent"', '"first message, reworded"')
    text = agent_text(result)
    check("an Edit that changes one message lists that message with path and line",
          result.returncode == 0 and "scripts/tool.py:8  first message, reworded" in text, result)
    check("the reminder lists only the changed message",
          "second message" not in text and "(s), text" in text and "changed 1 " in text, text)
    check("the reminder names the page by path", PAGE_PATH in text, text)
    for line in REMINDER_INSTRUCTION_LINES:
        check(f"the reminder carries the instruction line: {line[:60]}", line in text.split("\n"), text)
    check("the reminder names every name suffix the collector recognizes",
          "_ADVICE, _MESSAGE, _TEMPLATE, _LINE, _LINES or _REFUSAL" in text, text)

    reset()
    result = edit_then_run(repository, program, COMMITTED_SOURCE, '"first message to the agent"',
                           '"first message, reworded"', tool_name="MultiEdit")
    check("a MultiEdit is judged as an Edit is",
          "scripts/tool.py:8  first message, reworded" in agent_text(result), result)

    reset()
    result = edit_then_run(repository, program, COMMITTED_SOURCE, "LIMIT = 3", "LIMIT = 4")
    check("an Edit that touches code but no message is silent", silent(result), result)

    reset()
    result = edit_then_run(repository, program, COMMITTED_SOURCE,
                           '    print("first message to the agent")\n', "")
    check("an Edit that only removes a message is silent", silent(result), result)

    reset()
    result = edit_then_run(repository, program, COMMITTED_SOURCE, '"on three lines "\n', "")
    check("an Edit that deletes one line of a message held on several lines lists the message",
          "scripts/tool.py:10  a message held of source" in agent_text(result), result)

    reset()
    result = edit_then_run(repository, program, COMMITTED_SOURCE,
                           '"last line message"', '"last line message, reworded"')
    check("an Edit of a message on the file's last line lists the message",
          "scripts/tool.py:16  last line message, reworded" in agent_text(result), result)

    first_line_source = 'print("a message on line one")\nLIMIT = 3\n'
    first_line_program = repository / "scripts" / "first.py"
    first_line_program.write_text(first_line_source, encoding="utf-8")
    git(repository, "add", "scripts/first.py")
    git(repository, "commit", "-q", "-m", "line one fixture")
    result = edit_then_run(repository, first_line_program, first_line_source,
                           "a message on line one", "a reworded message on line one")
    check("an Edit of a message on the file's first line lists the message",
          "scripts/first.py:1  a reworded message on line one" in agent_text(result), result)

    reset()
    reindented = COMMITTED_SOURCE.replace('    print("first message to the agent")\n',
                                          '    if LIMIT:\n        print("first message to the agent")\n')
    result = edit_then_run(repository, program, COMMITTED_SOURCE, COMMITTED_SOURCE, reindented)
    check("an Edit that re-indents an unchanged message is silent", silent(result), result)

    reset()
    result = run_hook({"cwd": str(repository), "tool_name": "Edit",
                       "tool_input": {"file_path": str(program)}, "tool_response": {}})
    text = agent_text(result)
    check("an Edit whose payload has no structuredPatch is reported as not inspected, exit 0",
          result.returncode == 0 and "could not inspect your Edit of scripts/tool.py" in text
          and "no tool_response.structuredPatch" in text
          and "check that message against the page yourself" in text, result)

    new_program = repository / "scripts" / "brand-new-tool.py"
    result = write_then_run(repository, new_program,
                            'print("hello agent")\nraise SystemExit("stopped: the reason")\n')
    text = agent_text(result)
    check("a Write of a file new to git lists every message in the file",
          "scripts/brand-new-tool.py:1  hello agent" in text
          and "scripts/brand-new-tool.py:2  stopped: the reason" in text, result)

    result = write_then_run(repository, program,
                            COMMITTED_SOURCE.replace("second message to the agent", "second, reworded"))
    text = agent_text(result)
    check("a Write of a tracked file lists only the message whose text changed",
          "scripts/tool.py:9  second, reworded" in text and "first message" not in text
          and "changed 1 " in text, result)

    result = write_then_run(repository, program, COMMITTED_SOURCE)
    check("a Write that changes no message is silent", silent(result), result)

    for test_path in (repository / "scripts" / "tool-test.py", repository / "scripts" / "tests" / "helper.py"):
        result = write_then_run(repository, test_path, 'print("expected message")\n')
        check(f"a test file is silent: {test_path.relative_to(repository)}", silent(result), result)

    result = write_then_run(repository, repository / "scripts" / "notes.md", 'print("not python")\n')
    check("a file that is not .py is silent", silent(result), result)

    outside = Path(temporary) / "outside" / "loose.py"
    result = write_then_run(repository, outside, 'print("outside the repository")\n')
    check("a .py file outside the repository is silent", silent(result), result)

    result = write_then_run(repository, program, COMMITTED_SOURCE + 'print("unclosed\n')
    text = agent_text(result)
    check("a file that does not parse is reported as not parsed, exit 0",
          result.returncode == 0 and "scripts/tool.py does not parse as Python after your Write" in text
          and "the hook looks again after your next edit of scripts/tool.py" in text
          and "check that message against " + PAGE_PATH + " yourself once the file parses" in text,
          result)

    many_messages = "".join(f'print("message number {index}")\n' for index in range(30))
    result = write_then_run(repository, repository / "scripts" / "many.py", many_messages)
    text = agent_text(result)
    check("a long list is capped and says how many more there are",
          "scripts/many.py:20  message number 19" in text and "message number 20" not in text
          and "and 10 more in scripts/many.py, not listed here" in text
          and "changed 30 " in text, text)
    long_messages = "".join(f'print("{"x" * 5000} {index}")\n' for index in range(30))
    result = write_then_run(repository, repository / "scripts" / "long.py", long_messages)
    text = agent_text(result)
    check("the reminder stays under Claude Code's 10,000-character cut, first lines truncated",
          0 < len(text) < 10000 and ("x" * 100 + "...") in text, len(text))

    (repository / ".git" / "HEAD").write_text("not a reference\n", encoding="utf-8")
    result = write_then_run(repository, program,
                            COMMITTED_SOURCE.replace("second message to the agent", "second, reworded"))
    text = agent_text(result)
    check("a git failure is reported as not inspected, with git's reason, exit 0",
          result.returncode == 0 and "could not inspect your Write of scripts/tool.py, because git" in text
          and "check that message against the page yourself" in text, result)

print()
print(f"{len(failures)} failed")
sys.exit(1 if failures else 0)
