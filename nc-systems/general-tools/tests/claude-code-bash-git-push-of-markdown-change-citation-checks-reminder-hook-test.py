#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/claude-code-bash-git-push-of-markdown-change-citation-checks-reminder-hook.py.

Each case drives the hook's main() with a Bash payload against a scratch
repository whose origin/main is set with update-ref, so git really answers.

Run: python3 nc-systems/general-tools/tests/claude-code-bash-git-push-of-markdown-change-citation-checks-reminder-hook-test.py
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

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    REPOSITORY_ROOT / "scripts" / "git-redirecting-environment-removal-test-fixture.py")
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

HOOK_SCRIPT = (Path(__file__).resolve().parents[1]
               / "claude-code-bash-git-push-of-markdown-change-citation-checks-reminder-hook.py")
_spec = importlib.util.spec_from_file_location(
    "claude_code_bash_git_push_of_markdown_change_citation_checks_reminder_hook", HOOK_SCRIPT)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def git(directory, *arguments):
    return subprocess.run(
        ["git", "-C", str(directory), "-c", "user.name=Test", "-c", "user.email=test@example.com",
         "-c", "commit.gpgsign=false", *arguments],
        check=True, capture_output=True, text=True).stdout.strip()


def commit_file(directory, relative_path, text):
    path = directory / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    git(directory, "add", relative_path)
    git(directory, "commit", "-q", "-m", f"change {relative_path}")


def scratch_repository(root, with_citation_programs=True):
    """A repository on branch base, with origin/main at its first commit and two topic branches."""
    repository = root / "checkout"
    repository.mkdir()
    git(repository, "init", "-q", "-b", "base")
    if with_citation_programs:
        for program in hook.CITATION_CHECK_PROGRAMS:
            commit_file(repository, program, "")
    commit_file(repository, "README.md", "first\n")
    git(repository, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(repository, "switch", "-q", "-c", "markdown-branch")
    commit_file(repository, "docs/page.md", "a page\n")
    git(repository, "switch", "-q", "base")
    git(repository, "switch", "-q", "-c", "code-branch")
    commit_file(repository, "tool.py", "print()\n")
    git(repository, "switch", "-q", "base")
    git(repository, "switch", "-q", "-c", "markdown-deleting-branch")
    git(repository, "rm", "-q", "README.md")
    git(repository, "commit", "-q", "-m", "remove README.md")
    git(repository, "switch", "-q", "base")
    return repository


def run_main(command, cwd):
    """Drive main() as Claude Code does; return the added context, None when silent, or a crash note."""
    payload = {"tool_name": "Bash", "cwd": str(cwd), "tool_input": {"command": command}}
    stdout = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout):
            code = hook.main(stdin=io.StringIO(json.dumps(payload)))
    except Exception as error:  # A crash fails the case instead of ending the suite.
        return f"<crashed: {type(error).__name__}: {error}>"
    if code != 0:
        return f"<exit {code}>"
    text = stdout.getvalue().strip()
    if not text:
        return None
    output = json.loads(text)["hookSpecificOutput"]
    if "permissionDecision" in output:
        return f"<decided {output['permissionDecision']}>"
    return output["additionalContext"]


NOT_CHECKED_OUT_WORDS = "is not what is checked out in"
FAILURE_START = hook.HOOK_NAME + ": could not check whether this push changes a Markdown file"


def is_reminder(text, top, changed_file="docs/page.md"):
    return (isinstance(text, str) and text.startswith(hook.HOOK_NAME + ": this push goes ahead now. It sends")
            and changed_file in text
            and f"cd {top} && python3 scripts/dangling-path-citation-check.py" in text
            and f"cd {top} && python3 scripts/stale-code-citation-check.py" in text)


def is_failure_line(text, words):
    return isinstance(text, str) and "\n" not in text and text.startswith(FAILURE_START) and words in text


def run_hook_file(hook_file, command):
    """Run a copy of the hook as Claude Code does; return (exit code, added context or None, stderr)."""
    payload = {"tool_name": "Bash", "cwd": "/", "tool_input": {"command": command}}
    completed = subprocess.run([sys.executable, str(hook_file)], input=json.dumps(payload),
                               capture_output=True, text=True, timeout=60)
    text = completed.stdout.strip()
    context = json.loads(text)["hookSpecificOutput"]["additionalContext"] if text else None
    return completed.returncode, context, completed.stderr


def main():
    root = Path(tempfile.mkdtemp(prefix="markdown-push-reminder-test-"))
    try:
        repository = scratch_repository(root)
        top = git(repository, "rev-parse", "--show-toplevel")

        text = run_main("git push origin markdown-branch", repository)
        check("a push of a branch that changes a .md file is reminded", is_reminder(text, top), repr(text))
        check("a reminder for a branch that is not checked out says to check it out first",
              isinstance(text, str) and f"markdown-branch {NOT_CHECKED_OUT_WORDS} {top}" in text, repr(text))
        check("the check-out line comes before the two commands it must precede",
              isinstance(text, str) and NOT_CHECKED_OUT_WORDS in text
              and text.index(NOT_CHECKED_OUT_WORDS) < text.index(f"cd {top} && python3"), repr(text))

        text = run_main("git push origin +markdown-branch", repository)
        check("a forced +ref push of a branch that changes a .md file is reminded about that branch",
              is_reminder(text, top) and "It sends markdown-branch," in text, repr(text))

        text = run_main("git push origin markdown-branch markdown-deleting-branch", repository)
        check("a push of two branches that both change a .md file gives a reminder for each",
              isinstance(text, str) and text.count(": this push goes ahead now.") == 2
              and "It sends markdown-branch," in text and "It sends markdown-deleting-branch," in text,
              repr(text))

        text = run_main("git push origin code-branch markdown-branch", repository)
        check("a push of a branch without a .md change and one with gives the reminder for the second",
              is_reminder(text, top) and "It sends markdown-branch," in text
              and "code-branch" not in text, repr(text))

        for command in ("git status && git push origin markdown-branch",
                        "git branch -v && git push origin markdown-branch",
                        "git branch --merged && git push origin markdown-branch",
                        "git fetch -q origin && git push origin markdown-branch",
                        "git fetch https://host/x.git && git push origin markdown-branch",
                        "git fetch git@host:x.git main && git push origin markdown-branch",
                        "git fetch --multiple origin https://host/x.git && git push origin markdown-branch",
                        "git fetch --depth 1 origin && git push origin markdown-branch",
                        "git branch --sort -committerdate && git push origin markdown-branch",
                        "git branch --contains -m && git push origin markdown-branch",
                        "git branch -uorigin/main && git push origin markdown-branch"):
            text = run_main(command, repository)
            check(f"a git command that moves no ref, earlier in the call, leaves the push reminded: {command}",
                  is_reminder(text, top), repr(text))
        for command, subcommand in (
                ("git commit -q -m x && git push origin markdown-branch", "commit"),
                ("(git switch -q markdown-branch) && git push", "switch"),
                (f"git -C {repository} commit -q -m x && git push origin markdown-branch", "commit"),
                ("git -c user.name=x commit -q -m x; git push origin markdown-branch", "commit"),
                ("git branch -f code-branch markdown-branch && git push origin code-branch", "branch"),
                ("git branch --force code-branch markdown-branch && git push origin code-branch", "branch"),
                ("git branch -M code-branch && git push origin code-branch", "branch"),
                ("git fetch -q . markdown-branch:code-branch && git push origin code-branch", "fetch"),
                ("git fetch https://host/x.git main:code-branch && git push origin code-branch", "fetch"),
                ("git branch --sort -committerdate -f code-branch markdown-branch && git push origin code-branch", "branch"),
                ("git branch -vf code-branch markdown-branch && git push origin code-branch", "branch")):
            text = run_main(command, repository)
            check(f"a push after a git {subcommand} in the same call gives the failure line naming it: {command}",
                  is_failure_line(text, f"an earlier command in this call, git {subcommand}, can change what"),
                  repr(text))

        text = run_main("git push origin markdown-deleting-branch", repository)
        check("a push of a branch that deletes a .md file is reminded",
              is_reminder(text, top, changed_file="README.md"), repr(text))

        git(repository, "switch", "-q", "markdown-branch")
        text = run_main(f"cd {repository} && git push", root)
        check("a bare push after cd, of a checked-out branch that changes a .md file, is reminded",
              is_reminder(text, top), repr(text))
        check("a reminder for a bare push names the checked-out branch and gives no check-out line",
              isinstance(text, str) and "It sends markdown-branch," in text
              and NOT_CHECKED_OUT_WORDS not in text, repr(text))
        text = run_main(f"timeout 60 git -C {repository} push -u origin HEAD:markdown-branch", root)
        check("a push behind a wrapper, with -C and a HEAD refspec, is reminded",
              is_reminder(text, top), repr(text))
        git(repository, "switch", "-q", "base")

        text = run_main("git push origin code-branch", repository)
        check("a push of a branch that changes no .md file is silent", text is None, repr(text))

        # With markdown-branch checked out, a deletion read as a push of HEAD would be reminded.
        git(repository, "switch", "-q", "markdown-branch")
        for command in ("git push origin --delete markdown-branch", "git push -d origin markdown-branch",
                        "git push origin :markdown-branch"):
            text = run_main(command, repository)
            check(f"a push that deletes a remote branch is silent: {command}", text is None, repr(text))
        git(repository, "switch", "-q", "base")

        for command, words in (
                ("git -C $CHECKOUT push origin markdown-branch",
                 "the push runs in a directory this hook cannot read, $CHECKOUT"),
                ("cd $HOME/x && git push", "the push runs in a directory this hook cannot read, $HOME/x"),
                ('git push origin "$BRANCH"', "the push names a ref this hook cannot read, $BRANCH")):
            text = run_main(command, repository)
            check(f"a push this hook cannot read gives the failure line: {command}",
                  is_failure_line(text, words), repr(text))

        for command in ("git status", "git log --oneline -1 markdown-branch",
                        'echo "git push origin markdown-branch"'):
            text = run_main(command, repository)
            check(f"a command that is not a push is silent: {command}", text is None, repr(text))

        git(repository, "update-ref", "-d", "refs/remotes/origin/main")
        text = run_main("git push origin markdown-branch", repository)
        check("a git failure gives one line saying the reminder could not be checked",
              isinstance(text, str) and "\n" not in text
              and text.startswith(hook.HOOK_NAME + ": could not check whether this push changes a Markdown file")
              and "git diff exited" in text, repr(text))

        reader = hook.shell_reader
        real_simple_commands = reader.simple_commands

        def reader_failing(command_text, glob_markers=None):
            raise reader.ShellParserUnavailable("pip could not reach the index\nsecond line")

        reader.simple_commands = reader_failing
        try:
            text = run_main("git push origin markdown-branch", repository)
        finally:
            reader.simple_commands = real_simple_commands
        check("a shell reader failure gives one line saying the reminder could not be checked",
              isinstance(text, str) and "\n" not in text
              and text.startswith(hook.HOOK_NAME + ": could not check whether this push changes a Markdown file")
              and "the shell command reader failed: pip could not reach the index second line" in text,
              repr(text))

        real_run = hook.subprocess.run
        for raised, words in ((OSError("no git here"), "git could not be run: no git here"),
                              (subprocess.TimeoutExpired(["git"], 10),
                               f"did not answer within {hook.GIT_TIMEOUT_SECONDS} seconds")):
            def run_raising(*arguments, **options):
                raise raised
            hook.subprocess.run = run_raising
            try:
                text = run_main("git push origin markdown-branch", repository)
            finally:
                hook.subprocess.run = real_run
            check(f"git that {type(raised).__name__} stops gives the one failure line",
                  isinstance(text, str) and "\n" not in text
                  and text.startswith(hook.HOOK_NAME + ": could not check") and words in text,
                  repr(text))

        git(repository, "update-ref", "refs/remotes/origin/main", "base")
        clock_now = [0.0]
        timeouts = []

        def runner_advancing_clock(argv, **options):
            timeouts.append(options["timeout"])
            clock_now[0] += 15
            return real_run(argv, **options)

        messages = hook.messages_for_command("git push origin markdown-branch", str(repository),
                                             runner_advancing_clock, clock=lambda: clock_now[0])
        check("each git call gets at most the time left of the shared budget",
              timeouts == [hook.GIT_TIMEOUT_SECONDS, hook.GIT_BUDGET_SECONDS - 15], repr(timeouts))
        check("a spent git budget gives the one failure line and makes no more git calls",
              len(messages) == 1 and is_failure_line(
                  messages[0], f"the hook's {hook.GIT_BUDGET_SECONDS:.0f}-second limit for git ran out before git")
              and len(timeouts) == 2, repr(messages))

        settings = json.loads((REPOSITORY_ROOT / ".claude" / "settings.json").read_text())
        registered = [entry.get("timeout") for block in settings["hooks"]["PreToolUse"]
                      if block.get("matcher") == "Bash" for entry in block["hooks"]
                      if HOOK_SCRIPT.name in entry["command"]]
        check("the registered hook timeout exceeds the git budget, so the hook ends before it is killed",
              len(registered) == 1 and isinstance(registered[0], (int, float))
              and registered[0] > hook.GIT_BUDGET_SECONDS, repr(registered))

        # A copy without scripts/ beside it cannot load the force-push guard's file.
        copy = root / "copy" / "nc-systems" / "general-tools" / HOOK_SCRIPT.name
        copy.parent.mkdir(parents=True)
        shutil.copy(HOOK_SCRIPT, copy)
        code, text, stderr = run_hook_file(copy, "ls -la")
        check("when the force-push guard's file cannot load, a command without the word push is silent",
              code == 0 and text is None and not stderr, f"exit {code}, {text!r}, {stderr!r}")
        code, text, stderr = run_hook_file(copy, "git push origin markdown-branch")
        check("when the force-push guard's file cannot load, a push gives the one failure line",
              code == 0 and is_failure_line(text, "could not be loaded: FileNotFoundError"),
              f"exit {code}, {text!r}, {stderr!r}")

        other = root / "other"
        other.mkdir()
        repository_without_programs = scratch_repository(other, with_citation_programs=False)
        text = run_main("git push origin markdown-branch", repository_without_programs)
        check("a checkout without the citation programs is silent", text is None, repr(text))
    finally:
        shutil.rmtree(root, ignore_errors=True)

    if failures:
        print(f"{len(failures)} case(s) failed")
        return 1
    print("all cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
