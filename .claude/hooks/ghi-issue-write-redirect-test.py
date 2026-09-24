#!/usr/bin/env python3
"""Tests for ghi-issue-write-redirect.py, the guard that refuses hand-typed
`gh issue` writes on this project's repository.

No case runs `gh`: the guard never calls it, and every case drives the guard
in-process through `main` with a payload, the way the harness does. One case
runs the file end to end as a subprocess, so the shared shell reader's import
is exercised as the harness loads it.

Run: python3 .claude/hooks/ghi-issue-write-redirect-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

HOOK_SCRIPT = Path(__file__).with_name("ghi-issue-write-redirect.py")

_spec = importlib.util.spec_from_file_location("ghi_issue_write_redirect", HOOK_SCRIPT)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def decision_for(command, tool_name="Bash"):
    """Run the guard on one command; return the refusal text, or None."""
    payload = {"tool_name": tool_name, "cwd": "/a/session/checkout",
               "tool_input": {"command": command}}
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code = guard.main(stdin=io.StringIO(json.dumps(payload)))
    if code != 0:
        return f"<exit {code}>"
    text = stdout.getvalue().strip()
    if not text:
        return None
    output = json.loads(text)["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny", output
    return output["permissionDecisionReason"]


# Each refused form, and the refusal it must get.
REFUSED = [
    ("comment with --body", 'gh issue comment 46 --body "done"',
     guard.COMMENT_REFUSAL),
    ("comment with -b", "gh issue comment 46 -b done", guard.COMMENT_REFUSAL),
    ("comment with an attached -b value", "gh issue comment 46 -bdone",
     guard.COMMENT_REFUSAL),
    ("comment with --body-file", "gh issue comment 46 --body-file notes.md",
     guard.COMMENT_REFUSAL),
    ("comment with -F from a heredoc", "gh issue comment 46 -F - <<'EOF'\nan outcome\nEOF",
     guard.COMMENT_REFUSAL),
    ("comment opening the editor", "gh issue comment 46 --editor",
     guard.COMMENT_REFUSAL),
    ("comment through the web", "gh issue comment 46 -w", guard.COMMENT_REFUSAL),
    ("comment editing the last comment", 'gh issue comment 46 --edit-last -b "x"',
     guard.COMMENT_REFUSAL),
    ("comment naming this repository", "gh issue comment 46 -R nedschorus/nedschorus -b x",
     guard.COMMENT_REFUSAL),
    ("comment naming this repository with a host",
     "gh issue comment 46 --repo github.com/NedSchorus/NedSchorus -b x",
     guard.COMMENT_REFUSAL),
    ("comment by this repository's issue URL",
     "gh issue comment https://github.com/nedschorus/nedschorus/issues/46 -b x",
     guard.COMMENT_REFUSAL),
    ("comment behind env and an assignment", "env GH_PAGER= gh issue comment 46 -b x",
     guard.COMMENT_REFUSAL),
    ("comment by gh's full path", "/opt/homebrew/bin/gh issue comment 46 -b x",
     guard.COMMENT_REFUSAL),
    ("comment after a cd in the same command", "cd /tmp && gh issue comment 46 -b x",
     guard.COMMENT_REFUSAL),
    ("close with --comment", 'gh issue close 46 --comment "done" --reason completed',
     guard.STATE_CHANGE_COMMENT_REFUSAL.format(subcommand="close")),
    ("close with -c", "gh issue close 46 -c done",
     guard.STATE_CHANGE_COMMENT_REFUSAL.format(subcommand="close")),
    ("close with --comment=", "gh issue close 46 --comment=done",
     guard.STATE_CHANGE_COMMENT_REFUSAL.format(subcommand="close")),
    ("reopen with -c", "gh issue reopen 46 -c again",
     guard.STATE_CHANGE_COMMENT_REFUSAL.format(subcommand="reopen")),
    ("create", 'gh issue create --title "A" --body "B"', guard.CREATE_REFUSAL),
    ("create through the web", "gh issue create --web", guard.CREATE_REFUSAL),
    ("create by its alias new", 'gh issue new -t A -b B', guard.CREATE_REFUSAL),
    ("edit with --body", 'gh issue edit 46 --body "links"', guard.EDIT_BODY_REFUSAL),
    ("edit with -F", "gh issue edit 46 -F body.md", guard.EDIT_BODY_REFUSAL),
    ("edit with --body-file=", "gh issue edit 46 --body-file=body.md",
     guard.EDIT_BODY_REFUSAL),
    ("edit with a title and a body", 'gh issue edit 46 -t "T" -b "B"',
     guard.EDIT_BODY_REFUSAL),
    ("edit attaching a file to the body", "gh issue edit 46 --attach shot.png",
     guard.EDIT_BODY_REFUSAL),
    ("delete", "gh issue delete 46 --yes", guard.DELETE_REFUSAL),
    ("the second command of a pipeline", "true | gh issue comment 46 -b x",
     guard.COMMENT_REFUSAL),
]

# Each form that must pass untouched.
ALLOWED = [
    ("view", "gh issue view 46"),
    ("list", "gh issue list --state open --limit 200"),
    ("status", "gh issue status"),
    ("close without a comment", "gh issue close 46 --reason completed"),
    ("close as a duplicate", "gh issue close 46 --reason duplicate --duplicate-of 12"),
    ("reopen without a comment", "gh issue reopen 46"),
    ("edit adding a label", "gh issue edit 46 --add-label draft"),
    ("edit removing a label and adding an assignee",
     "gh issue edit 46 --remove-label draft --add-assignee @me"),
    ("edit setting the milestone", "gh issue edit 46 -m v1"),
    ("edit changing only the title", 'gh issue edit 46 --title "New title"'),
    ("a title whose value looks like -b", 'gh issue edit 46 --title "-b is a flag"'),
    ("a label whose value looks like --body", 'gh issue edit 46 --add-label "--body"'),
    ("comment deleting the last comment", "gh issue comment 46 --delete-last --yes"),
    ("comment on another repository", "gh issue comment 5 -R cli/cli -b report",
     ),
    ("comment on another repository with --repo=",
     "gh issue comment 5 --repo=github.com/cli/cli -b report"),
    ("comment on another repository by GH_REPO", "GH_REPO=cli/cli gh issue comment 5 -b x"),
    ("comment on another repository's issue URL",
     "gh issue comment https://github.com/cli/cli/issues/5 -b report"),
    ("create on another repository", "gh issue create -R cli/cli -t A -b B"),
    ("the write tool itself", "python3 scripts/ghi-issue-write.py create docs/issues/queue/x.md"),
    ("the write tool's edit", "python3 scripts/ghi-issue-write.py edit docs/issues/46-x.md"),
    ("gh issue comment quoted as prose", 'echo "run gh issue comment 46 -b x"'),
    ("gh issue comment in a commit message",
     "git commit -m 'Refuse gh issue comment and gh issue create by hand'"),
    ("gh issue comment in a heredoc body", "cat > note.md <<'EOF'\ngh issue comment 46 -b x\nEOF"),
    ("a pull request comment", "gh pr comment 700 -b looks-good"),
    ("gh api", "gh api repos/nedschorus/nedschorus/issues/46/comments -f body=x"),
    ("gh issue with no subcommand", "gh issue"),
    ("a bare gh", "gh"),
]

for name, command, expected in REFUSED:
    refusal = decision_for(command)
    check(f"refuses: {name}", refusal == expected, repr(refusal))

for name, command in ALLOWED:
    refusal = decision_for(command)
    check(f"allows: {name}", refusal is None, repr(refusal))

# Every refusal is instructions only: no line gives a date, a ruling or a
# reason (user-ruled 2026-09-18). A line starts with an imperative or with
# the condition it applies under.
REFUSAL_TEXTS = [guard.COMMENT_REFUSAL, guard.CREATE_REFUSAL,
                 guard.EDIT_BODY_REFUSAL, guard.DELETE_REFUSAL,
                 guard.STATE_CHANGE_COMMENT_REFUSAL.format(subcommand="close")]
OPENING_WORDS = ("Do not", "Put", "If", "Write", "Edit", "To change", "Close",
                 "Run", "Record")
for text in REFUSAL_TEXTS:
    for line in text.splitlines():
        check(f"refusal line is an instruction: {line[:48]}",
              line.startswith(OPENING_WORDS)
              and "because" not in line and "ruled" not in line
              and "2026" not in line, line)

# Non-Bash tools and empty or unreadable payloads pass without a word.
for tool_name in ("Edit", "Write"):
    check(f"a {tool_name} call passes", decision_for("gh issue comment 1 -b x",
                                                   tool_name=tool_name) is None)
check("an empty command passes", decision_for("") is None)
stdout = io.StringIO()
with contextlib.redirect_stdout(stdout):
    code = guard.main(stdin=io.StringIO("not json"))
check("an unreadable payload exits 0 and says nothing",
      code == 0 and not stdout.getvalue().strip(), f"{code} {stdout.getvalue()}")

# The shared shell reader is imported, not copied: a change there reaches
# this guard, and a broken import fails here instead of failing open at runtime.
check("the tokenizer is the keystroke guard's",
      guard.tokenize_simple_commands.__module__ == "synthetic_keystroke_guard_hook",
      guard.tokenize_simple_commands.__module__)

# End to end, as the harness runs it.
for command, should_refuse in (("gh issue comment 46 -b x", True),
                               ("gh issue view 46", False)):
    result = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        input=json.dumps({"tool_name": "Bash", "cwd": "/a/session/checkout",
                          "tool_input": {"command": command}}),
        capture_output=True, text=True, check=False)
    refused = '"permissionDecision": "deny"' in result.stdout
    check(f"end to end, {command!r} {'is refused' if should_refuse else 'passes'}",
          result.returncode == 0 and refused == should_refuse,
          f"{result.returncode} {result.stdout} {result.stderr}")

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
