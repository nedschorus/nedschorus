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
import tempfile
from pathlib import Path

# Before anything runs git: a run started with GIT_DIR set, or with another
# variable that redirects git, must still build this suite's scratch
# repositories where the suite says, not in the repository the variable names.
_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().parents[2] / "scripts"
    / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

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


# The refusals as they read when the issue's files cannot be looked up, as in
# these cases, whose checkout does not exist.
CLOSE_WITH_COMMENT_FALLBACK = guard.CLOSE_WITH_COMMENT_REFUSAL.format(
    record_line=guard.record_line(guard.CLOSE_OUTCOME, None))
REOPEN_WITH_COMMENT_FALLBACK = guard.REOPEN_WITH_COMMENT_REFUSAL.format(
    record_line=guard.record_line(guard.REOPEN_OUTCOME, None))
DELETE_FALLBACK = guard.DELETE_REFUSAL.format(
    record_line=guard.record_line(guard.CLOSE_OUTCOME, None))
COMMENT_FALLBACK = guard.comment_refusal(None)
EDIT_BODY_FALLBACK = guard.edit_body_refusal(None)
EDIT_TITLE_FALLBACK = guard.edit_title_refusal(None)

# Each refused form, and the refusal it must get.
REFUSED = [
    ("comment with --body", 'gh issue comment 46 --body "done"',
     COMMENT_FALLBACK),
    ("comment with -b", "gh issue comment 46 -b done", COMMENT_FALLBACK),
    ("comment with an attached -b value", "gh issue comment 46 -bdone",
     COMMENT_FALLBACK),
    ("comment with --body-file", "gh issue comment 46 --body-file notes.md",
     COMMENT_FALLBACK),
    ("comment with -F from a heredoc", "gh issue comment 46 -F - <<'EOF'\nan outcome\nEOF",
     COMMENT_FALLBACK),
    ("comment opening the editor", "gh issue comment 46 --editor",
     COMMENT_FALLBACK),
    ("comment through the web", "gh issue comment 46 -w", COMMENT_FALLBACK),
    ("comment editing the last comment", 'gh issue comment 46 --edit-last -b "x"',
     COMMENT_FALLBACK),
    ("comment naming this repository", "gh issue comment 46 -R nedschorus/nedschorus -b x",
     COMMENT_FALLBACK),
    ("comment naming this repository with a host",
     "gh issue comment 46 --repo github.com/NedSchorus/NedSchorus -b x",
     COMMENT_FALLBACK),
    ("comment by this repository's issue URL",
     "gh issue comment https://github.com/nedschorus/nedschorus/issues/46 -b x",
     COMMENT_FALLBACK),
    ("comment behind env and an assignment", "env GH_PAGER= gh issue comment 46 -b x",
     COMMENT_FALLBACK),
    ("comment by gh's full path", "/opt/homebrew/bin/gh issue comment 46 -b x",
     COMMENT_FALLBACK),
    ("comment after a cd in the same command", "cd /tmp && gh issue comment 46 -b x",
     COMMENT_FALLBACK),
    ("close with --comment", 'gh issue close 46 --comment "done" --reason completed',
     CLOSE_WITH_COMMENT_FALLBACK),
    ("close with -c", "gh issue close 46 -c done",
     CLOSE_WITH_COMMENT_FALLBACK),
    ("close with --comment=", "gh issue close 46 --comment=done",
     CLOSE_WITH_COMMENT_FALLBACK),
    ("reopen with -c", "gh issue reopen 46 -c again",
     REOPEN_WITH_COMMENT_FALLBACK),
    ("create", 'gh issue create --title "A" --body "B"', guard.CREATE_REFUSAL),
    ("create through the web", "gh issue create --web", guard.CREATE_REFUSAL),
    ("create by its alias new", 'gh issue new -t A -b B', guard.CREATE_REFUSAL),
    ("edit with --body", 'gh issue edit 46 --body "links"', EDIT_BODY_FALLBACK),
    ("edit with -F", "gh issue edit 46 -F body.md", EDIT_BODY_FALLBACK),
    ("edit with --body-file=", "gh issue edit 46 --body-file=body.md",
     EDIT_BODY_FALLBACK),
    ("edit with a title and a body", 'gh issue edit 46 -t "T" -b "B"',
     EDIT_BODY_FALLBACK),
    ("edit attaching a file to the body", "gh issue edit 46 --attach shot.png",
     EDIT_BODY_FALLBACK),
    ("edit changing only the title", 'gh issue edit 46 --title "New title"',
     EDIT_TITLE_FALLBACK),
    ("edit with -t", 'gh issue edit 46 -t "New title"', EDIT_TITLE_FALLBACK),
    ("edit with --title=", "gh issue edit 46 --title=New", EDIT_TITLE_FALLBACK),
    ("edit with an attached -t value", "gh issue edit 46 -tNew",
     EDIT_TITLE_FALLBACK),
    ("edit with a title and a label",
     'gh issue edit 46 --title "T" --add-label draft', EDIT_TITLE_FALLBACK),
    ("a title whose value looks like -b",
     'gh issue edit 46 --title "-b is a flag"', EDIT_TITLE_FALLBACK),
    ("edit with a title naming this repository",
     'gh issue edit 46 -R nedschorus/nedschorus --title "T"',
     EDIT_TITLE_FALLBACK),
    ("delete", "gh issue delete 46 --yes", DELETE_FALLBACK),
    ("the second command of a pipeline", "true | gh issue comment 46 -b x",
     COMMENT_FALLBACK),
    # This repository named by a repository flag before the subcommand, in
    # each place and spelling gh accepts.
    ("create with -R between gh and issue",
     "gh -R nedschorus/nedschorus issue create -t A -b B", guard.CREATE_REFUSAL),
    ("comment with --repo between gh and issue",
     "gh --repo nedschorus/nedschorus issue comment 46 -b x",
     COMMENT_FALLBACK),
    ("comment with --repo= between gh and issue",
     "gh --repo=nedschorus/nedschorus issue comment 46 -b x",
     COMMENT_FALLBACK),
    ("delete with an attached -R value between gh and issue",
     "gh -Rnedschorus/nedschorus issue delete 46 --yes", DELETE_FALLBACK),
    ("create with -R and a host between gh and issue",
     "gh -R github.com/nedschorus/nedschorus issue create -t A -b B",
     guard.CREATE_REFUSAL),
    ("comment with -R between issue and the subcommand",
     "gh issue -R nedschorus/nedschorus comment 46 -b x",
     COMMENT_FALLBACK),
    ("edit with --repo between issue and the subcommand",
     "gh issue --repo nedschorus/nedschorus edit 46 --body x",
     EDIT_BODY_FALLBACK),
    ("close with -R= between issue and the subcommand",
     "gh issue -R=nedschorus/nedschorus close 46 -c done",
     CLOSE_WITH_COMMENT_FALLBACK),
    ("comment with -R= after the subcommand",
     "gh issue comment 46 -R=nedschorus/nedschorus -b x",
     COMMENT_FALLBACK),
    ("comment with repository flags in two places, this one last",
     "gh -R cli/cli issue -R nedschorus/nedschorus comment 46 -b x",
     COMMENT_FALLBACK),
    ("comment with two -R flags after the subcommand, this one last",
     "gh issue comment 46 -R cli/cli -R nedschorus/nedschorus -b x",
     COMMENT_FALLBACK),
    # The shell runs a command substitution inside double quotes exactly as
    # it runs a bare one, so the write inside either is refused.
    ("create in a double-quoted command substitution",
     'URL="$(gh issue create -t A -b B)"', guard.CREATE_REFUSAL),
    ("create in a bare command substitution",
     "URL=$(gh issue create -t A -b B)", guard.CREATE_REFUSAL),
    ("comment in a double-quoted command substitution",
     'echo "$(gh issue comment 46 -b x)"', COMMENT_FALLBACK),
    ("comment in a bare command substitution",
     "echo $(gh issue comment 46 -b x)", COMMENT_FALLBACK),
]

# Claude Code's default commit form passes the message as a heredoc inside
# "$(cat <<'EOF' ... )". The message is a heredoc body, so it is data wherever
# its own quotes and backticks fall.
HEREDOC_MESSAGE_QUOTING_A_COMMENT = (
    "$(cat <<'EOF'\n"
    "Drop the interim path\n"
    "\n"
    "The skill said: \"plain `gh issue comment` is the interim path.\" Gone now.\n"
    "EOF\n"
    ")"
)

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
    ("edit changing the title on another repository",
     'gh issue edit 5 --repo cli/cli --title "New title"'),
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
    ("comment on another repository with -R between gh and issue",
     "gh -R cli/cli issue comment 5 -b report"),
    ("create on another repository with --repo between issue and the "
     "subcommand", "gh issue --repo cli/cli create -t A -b B"),
    ("create on another repository with an attached -R value",
     "gh -Rcli/cli issue create -t A -b B"),
    ("comment on another repository with --repo= between gh and issue",
     "gh --repo=cli/cli issue comment 5 -b x"),
    ("comment on another repository with -R= between issue and the "
     "subcommand", "gh issue -R=cli/cli comment 5 -b x"),
    ("the -R flag outranks GH_REPO",
     "GH_REPO=nedschorus/nedschorus gh -R cli/cli issue comment 5 -b x"),
    ("view with -R between gh and issue",
     "gh -R nedschorus/nedschorus issue view 46"),
    ("-R between gh and issue with no subcommand",
     "gh -R nedschorus/nedschorus issue"),
    ("a -R flag with no value", "gh -R"),
    ("comment with repository flags in two places, another one last",
     "gh -R nedschorus/nedschorus issue -R cli/cli comment 5 -b x"),
    ("the write tool itself", "python3 scripts/ghi-issue-write.py create docs/issues/queue/x.md"),
    ("the write tool's edit", "python3 scripts/ghi-issue-write.py edit docs/issues/46-x.md"),
    ("gh issue comment quoted as prose", 'echo "run gh issue comment 46 -b x"'),
    ("gh issue comment in a commit message",
     "git commit -m 'Refuse gh issue comment and gh issue create by hand'"),
    ("gh issue comment in a heredoc body", "cat > note.md <<'EOF'\ngh issue comment 46 -b x\nEOF"),
    ("a heredoc commit message quoting a backticked gh issue comment",
     f'git commit -m "{HEREDOC_MESSAGE_QUOTING_A_COMMENT}"'),
    ("a heredoc pull request body quoting a backticked gh issue comment",
     f'gh pr create --title "Drop the interim path" '
     f'--body "{HEREDOC_MESSAGE_QUOTING_A_COMMENT}"'),
    ("an escaped \\$( in double quotes, which the shell does not run",
     'echo "\\$(gh issue comment 46 -b x)"'),
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

# Every refusal line starts with an imperative or with the condition it
# applies under. A line may give a reason, but it may not cite a ruling
# or a date: a reason helps the agent act well, and a ruling or a date
# only says who decided and when. For example:
#   passes: "Do not delete issues; a deleted issue cannot be restored."
#   fails:  "Do not delete issues (user-ruled 2026-09-18)."
RECORD_LINE_CASES = (None, [], ["docs/issues/46-a.md"],
                     ["docs/issues/46-a.md", "docs/issues/46-b.md"])
REFUSAL_TEXTS = [guard.CREATE_REFUSAL,
                 guard.DELETE_REFUSAL_NO_FILE, guard.CLOSE_WITH_COMMENT_REFUSAL_NO_FILE]
for files in RECORD_LINE_CASES:
    REFUSAL_TEXTS += [
        guard.comment_refusal(files), guard.edit_body_refusal(files),
        guard.edit_title_refusal(files),
        guard.CLOSE_WITH_COMMENT_REFUSAL.format(
            record_line=guard.record_line(guard.CLOSE_OUTCOME, files)),
        guard.REOPEN_WITH_COMMENT_REFUSAL.format(
            record_line=guard.record_line(guard.REOPEN_OUTCOME, files)),
        guard.DELETE_REFUSAL.format(
            record_line=guard.record_line(guard.CLOSE_OUTCOME, files))]
OPENING_WORDS = ("Do not", "Put", "If", "Write", "Edit", "To change", "Close",
                 "Run", "Record", "Change", "This", "The", "Otherwise")
for text in REFUSAL_TEXTS:
    for line in text.splitlines():
        check(f"refusal line is an instruction: {line[:48]}",
              line.startswith(OPENING_WORDS)
              and "ruled" not in line
              and "2026" not in line, line)

# edit-GHI retitles only an issue with one filed GHI-MD, and only when the
# edit changes its heading, so the title refusal sends the agent to the user
# in the other cases, and says so before it says what to change.
check("the title refusal, files unknown: the stop line comes before the change line",
      EDIT_TITLE_FALLBACK.splitlines()[2] ==
      "If the issue has no file or two or more files, counting files named "
      "docs/issues/<number>-*.md and designs in a system's docs/ directory, or the "
      "first heading of the issue's GHI-MD already reads the title you want, stop "
      "and tell the user."
      and EDIT_TITLE_FALLBACK.splitlines()[3].startswith("Otherwise change the first heading"),
      EDIT_TITLE_FALLBACK)
for name, text in (("comment", COMMENT_FALLBACK), ("body", EDIT_BODY_FALLBACK),
                   ("title", EDIT_TITLE_FALLBACK)):
    check(f"the {name} refusal, files unknown, ends with the rerun line",
          text.splitlines()[-1] == guard.RERUN_LINE, text)

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

# The record line names the issue's files on main, looked up in the session's
# checkout as the GHI write tool lists them.
with tempfile.TemporaryDirectory() as temporary_directory:
    root = Path(temporary_directory)
    origin = root / "origin"
    origin.mkdir()

    def git(arguments, cwd):
        return subprocess.run(["git", *arguments], cwd=cwd, capture_output=True,
                              text=True, check=True)

    git(["init", "-q", "-b", "main"], origin)
    git(["config", "user.email", "test@example.com"], origin)
    git(["config", "user.name", "test"], origin)
    for relative in ("docs/issues/46-the-only-file.md", "docs/issues/47-the-ghi-md.md",
                     "docs/issues/47-supporting-notes.md", "docs/issues/9-unrelated.md"):
        (origin / relative).parent.mkdir(parents=True, exist_ok=True)
        (origin / relative).write_text("# A file\n", encoding="utf-8")
    git(["add", "-A"], origin)
    git(["commit", "-q", "-m", "issue files"], origin)
    session_checkout = root / "session-checkout"
    git(["clone", "-q", str(origin), str(session_checkout)], root)

    def refusal_in_checkout(command):
        payload = {"tool_name": "Bash", "cwd": str(session_checkout),
                   "tool_input": {"command": command}}
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            guard.main(stdin=io.StringIO(json.dumps(payload)))
        text = stdout.getvalue().strip()
        return json.loads(text)["hookSpecificOutput"]["permissionDecisionReason"] if text else None

    refusal = refusal_in_checkout("gh issue close 46 -c done")
    check("close: an issue with one file on main is told to record the outcome in it",
          refusal is not None and refusal.split("\n")[1] ==
          "Record the outcome in docs/issues/46-the-only-file.md, then open the edit's pull "
          "request with: python3 scripts/ghi-issue-write.py edit docs/issues/46-the-only-file.md",
          refusal)
    check("close: the refusal says to close only after that edit has merged and its rerun",
          refusal is not None and refusal.split("\n")[2].startswith(
              "Close the issue after that edit's pull request has merged and its rerun has "
              "finished, without --comment"), refusal)

    refusal = refusal_in_checkout("gh issue close 47 --comment done")
    check("close: an issue with several files on main is given all of them to choose among",
          refusal is not None and refusal.split("\n")[1] ==
          "The issue's files on main are: docs/issues/47-supporting-notes.md, "
          "docs/issues/47-the-ghi-md.md. Record the outcome in the issue's GHI-MD among "
          "them, then open the edit's pull request with: python3 "
          "scripts/ghi-issue-write.py edit <that path>", refusal)

    refusal = refusal_in_checkout("gh issue close 48 -c done")
    check("close: an issue with no file on main is told to stop, and the message ends there",
          refusal == guard.NO_COMMENTS_LINE + "\n" +
          "This issue has no file on main under docs/issues/<number>-* or a system's "
          "directory: stop and tell the user.", refusal)

    refusal = refusal_in_checkout("gh issue reopen 46 -c again")
    check("reopen: the record line asks for why the issue is reopening",
          refusal is not None and refusal.split("\n")[2].startswith(
              "Record why the issue is reopening in docs/issues/46-the-only-file.md"), refusal)

    refusal = refusal_in_checkout(
        "gh issue delete https://github.com/nedschorus/nedschorus/issues/46 --yes")
    check("delete by URL: the issue number is read from the URL and its file named",
          refusal is not None and refusal.split("\n")[1].startswith(
              "Record the outcome in docs/issues/46-the-only-file.md"), refusal)
    check("delete: the duplicate line comes first among the close lines",
          refusal is not None and refusal.split("\n")[3].startswith(
              "If this issue covers the same work as another issue: "), refusal)

    refusal = refusal_in_checkout("gh issue delete 48 --yes")
    check("delete: an issue with no file on main may be closed as not planned if filed by mistake",
          refusal == guard.DELETE_REFUSAL_NO_FILE, refusal)

    ONE_FILE = "docs/issues/46-the-only-file.md"
    SEVERAL_FILES = "docs/issues/47-supporting-notes.md, docs/issues/47-the-ghi-md.md"
    NO_FILE_LINE = ("This issue has no file on main under docs/issues/<number>-* or a "
                    "system's directory: stop and tell the user.")
    RERUN = ("If you opened that pull request: after it merges, pull main and run the "
             "same python3 scripts/ghi-issue-write.py edit command again; the rerun "
             "updates the issue.")

    refusal = refusal_in_checkout("gh issue comment 46 --body done")
    check("comment: an issue with one file on main is told to record the comment in it, "
          "then rerun",
          refusal is not None and refusal.split("\n") == [
              guard.NO_COMMENTS_LINE,
              f"Record what the comment would say in {ONE_FILE}, then open the edit's pull "
              f"request with: python3 scripts/ghi-issue-write.py edit {ONE_FILE}",
              RERUN], refusal)
    refusal = refusal_in_checkout("gh issue comment 47 -b done")
    check("comment: an issue with several files on main is given all of them, then rerun",
          refusal is not None and refusal.split("\n") == [
              guard.NO_COMMENTS_LINE,
              f"The issue's files on main are: {SEVERAL_FILES}. Record what the comment "
              "would say in the issue's GHI-MD among them, then open the edit's pull "
              "request with: python3 scripts/ghi-issue-write.py edit <that path>",
              RERUN], refusal)
    refusal = refusal_in_checkout("gh issue comment 48 -b done")
    check("comment: an issue with no file on main is told to stop, with no rerun line",
          refusal == guard.NO_COMMENTS_LINE + "\n" + NO_FILE_LINE, refusal)

    BODY_FIRST_LINES = [
        "Do not set this project's issue bodies with gh issue edit: an issue's body is "
        "the links to its files on main, and scripts/ghi-issue-write.py writes it from "
        "those files.",
        "To change only labels, assignees or the milestone, run gh issue edit without "
        "--title, --body, --body-file and --attach; that needs no file.",
        "If the command also set the title, run gh issue edit <number> --title alone "
        "afterwards for the title's instructions."]
    refusal = refusal_in_checkout('gh issue edit 46 --body "links"')
    check("body: an issue with one file on main is told to record the change in it, "
          "then rerun",
          refusal is not None and refusal.split("\n") == BODY_FIRST_LINES + [
              f"Record the change in {ONE_FILE}, then open the edit's pull request with: "
              f"python3 scripts/ghi-issue-write.py edit {ONE_FILE}", RERUN], refusal)
    refusal = refusal_in_checkout("gh issue edit 47 -F body.md")
    check("body: an issue with several files on main is given all of them, then rerun",
          refusal is not None and refusal.split("\n") == BODY_FIRST_LINES + [
              f"The issue's files on main are: {SEVERAL_FILES}. Record the change in the "
              "issue's GHI-MD among them, then open the edit's pull request with: python3 "
              "scripts/ghi-issue-write.py edit <that path>", RERUN], refusal)
    refusal = refusal_in_checkout('gh issue edit 48 --body "links"')
    check("body: an issue with no file on main is told to stop, with no rerun line",
          refusal is not None and refusal.split("\n") == BODY_FIRST_LINES + [NO_FILE_LINE],
          refusal)
    refusal = refusal_in_checkout('gh issue edit 46 --title "New" --body "links"')
    check("body and title in one command: the body refusal, which sends the title on alone",
          refusal is not None and refusal.split("\n")[:3] == BODY_FIRST_LINES, refusal)

    TITLE_FIRST_LINES = [
        "Do not set this project's issue titles with gh issue edit: "
        "scripts/ghi-issue-write.py sets an issue's title from the first heading of the "
        "issue's GHI-MD, when the issue has one file on main and an edit changes that "
        "heading.",
        "To change only labels, assignees or the milestone, run gh issue edit without "
        "--title, --body, --body-file and --attach; that needs no file."]
    refusal = refusal_in_checkout('gh issue edit 46 --title "New title"')
    check("title: an issue with one file on main: stop if the heading already reads it, "
          "otherwise change it, then rerun",
          refusal is not None and refusal.split("\n") == TITLE_FIRST_LINES + [
              f"If the first heading of {ONE_FILE} already reads the title you want, stop "
              "and tell the user.",
              "Otherwise change that heading to the title you want, then open the edit's "
              f"pull request with: python3 scripts/ghi-issue-write.py edit {ONE_FILE}",
              RERUN], refusal)
    refusal = refusal_in_checkout('gh issue edit 47 -t "New title"')
    check("title: an issue with several files on main is told to stop, with no rerun line",
          refusal is not None and refusal.split("\n") == TITLE_FIRST_LINES + [
              f"The issue's files on main are: {SEVERAL_FILES}. scripts/ghi-issue-write.py "
              "changes the title only of an issue with one file, so stop and tell the "
              "user."], refusal)
    refusal = refusal_in_checkout("gh issue edit 48 --title=New")
    check("title: an issue with no file on main is told to stop, with no rerun line",
          refusal is not None and refusal.split("\n") == TITLE_FIRST_LINES + [NO_FILE_LINE],
          refusal)
    refusal = refusal_in_checkout("gh issue edit 46 --add-label draft")
    check("an edit changing only a label still passes in a checkout", refusal is None,
          refusal)

print()
if failures:
    print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
    sys.exit(1)
print("all cases passed")
