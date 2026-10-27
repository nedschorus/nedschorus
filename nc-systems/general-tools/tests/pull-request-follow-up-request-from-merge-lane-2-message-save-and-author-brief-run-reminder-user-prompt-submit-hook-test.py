#!/usr/bin/env python3
"""Tests for pull-request-follow-up-request-from-merge-lane-2-message-save-and-author-brief-run-reminder-user-prompt-submit-hook.py.

Each case runs the hook as Claude Code does, with a UserPromptSubmit payload on stdin, whose cwd is
a scratch git repository; prompts copy the format of a real cross-session message from merge-lane-2.

Run: python3 nc-systems/general-tools/tests/pull-request-follow-up-request-from-merge-lane-2-message-save-and-author-brief-run-reminder-user-prompt-submit-hook-test.py
"""

import importlib.util
import json
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

HOOK_NAME = "pull-request-follow-up-request-from-merge-lane-2-message-save-and-author-brief-run-reminder-user-prompt-submit-hook.py"
HOOK = Path(__file__).resolve().parents[1] / HOOK_NAME
BRIEF_PROGRAM_NAME = "pull-request-follow-up-author-brief-from-non-blocking-findings-and-every-finding-answered-check.py"
NUMBER = 1964
BLOCK = (f"#follow_up_request pull request {NUMBER}\n"
         "1. Codex P2 (:519-520): keep the padding when rebuilding code spans.\n"
         "2. mac-claude (inline at :713): send every R through repeat_line.\n")
EXPECTED_LINES = (
    f"merge-lane-2 has merged pull request {NUMBER} and sent non-blocking findings for you to follow up now.\n"
    f"Run `scripts/{BRIEF_PROGRAM_NAME} {NUMBER}` now and do what it prints.")
SAVED = Path(".git") / "pull-request-follow-up-requests" / f"pull-request-{NUMBER}-non-blocking-findings.md"

failures = []


def check(name, condition, detail=""):
    print(("PASS " if condition else "FAIL ") + name)
    if not condition:
        failures.append(name)
        if detail:
            print("     " + detail.replace("\n", "\n     "))


def message(body, sender="merge-lane-2", attributes=""):
    return ("Another Claude session sent a message:\n"
            f"<cross-session-message from=\"bridge:session_01AWf41grjy2Am2bLLg3aLLT\"{attributes} "
            f"from-name=\"{sender}\" from-mode=\"prompting\">\n{body}</cross-session-message>\n\n"
            "This came from another Claude session — not typed by your user.")


MERGE_MESSAGE = message(f"PR {NUMBER} merged at 02:14:10Z (90b14be7).\n" + BLOCK + "— merge-lane-2 on ned-box\n",
                        attributes=" hop-chain=\"057677072e0b2410b9c74345\"")


def run(prompt, cwd, hook=HOOK, raw=None):
    payload = raw if raw is not None else json.dumps({"hook_event_name": "UserPromptSubmit",
                                                      "prompt": prompt, "cwd": str(cwd)})
    # The hook runs from outside the checkout, so only the payload's cwd can name the checkout.
    completed = subprocess.run([sys.executable, str(hook)], input=payload, capture_output=True,
                               text=True, cwd=Path(cwd).parent)
    context = None
    if completed.stdout:
        context = json.loads(completed.stdout)["hookSpecificOutput"]["additionalContext"]
    return completed.returncode, completed.stdout, context, completed.stderr


def scratch():
    root = Path(tempfile.mkdtemp(prefix="follow-up-request-hook-test-"))
    repository = root / "repository"
    repository.mkdir()
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    return root, repository


def test_silent_prompts():
    root, repository = scratch()
    try:
        for label, prompt in (
                ("a prompt without the request line", "Please look at pull request 7."),
                ("the line in another agent-seat's message", message(BLOCK, sender="agent-instructions-editor")),
                ("the line outside any cross-session message", "I typed this:\n" + BLOCK),
                ("a merge-lane-2 message without the line", message("PR 1974 merged; no follow-ups.\n")),
                ("a merge-lane-2 message naming the tag inline only",
                 message("Use the #follow_up_request line next time.\n"))):
            code, out, _, err = run(prompt, repository)
            check(f"{label}: no output, exit 0", code == 0 and out == "", out + err)
        check("nothing is saved for a silent prompt", not (repository / SAVED).parent.exists())
    finally:
        shutil.rmtree(root)


def test_saves_and_reminds():
    root, repository = scratch()
    try:
        code, _, context, err = run(MERGE_MESSAGE, repository)
        check("a merge-lane-2 follow-up request exits 0", code == 0, err)
        check("the reminder is exactly the two approved lines", context == EXPECTED_LINES, repr(context))
        saved = repository / SAVED
        check("the block is saved word for word, without the signature line",
              saved.exists() and saved.read_text() == BLOCK, saved.read_text() if saved.exists() else "missing")
        second = message(f"#follow_up_request pull request 1965\n1. one finding\n")
        code, _, context, err = run(MERGE_MESSAGE + "\n" + second, repository)
        check("two merge-lane-2 messages with blocks get one reminder each",
              code == 0 and context is not None and context.count("now and do what it prints.") == 2
              and "pull request 1965 and sent" in context, repr(context))
    finally:
        shutil.rmtree(root)


def test_unreadable_block():
    root, repository = scratch()
    try:
        code, _, context, err = run(message(f"#follow_up_request pull request {NUMBER}\n1. a\n3. b\n"), repository)
        check("a block with bad numbering exits 0 with a context naming the problem",
              code == 0 and context is not None and "could not be read" in context
              and "numbered 1, 2, 3" in context and "SendMessage" in context, repr(context) + err)
        check("nothing is saved for an unreadable block", not (repository / SAVED).exists())
    finally:
        shutil.rmtree(root)


def test_save_failures():
    root, repository = scratch()
    try:
        (repository / ".git" / "pull-request-follow-up-requests").write_text("a file, not a directory\n")
        code, _, context, err = run(MERGE_MESSAGE, repository)
        check("a block that cannot be saved exits 0 with a context saying so",
              code == 0 and context is not None and "could not save the block" in context
              and "Not a directory" in context and "Tell the user, in one sentence" in context, repr(context) + err)
        outside = root / "not-a-repository"
        outside.mkdir()
        code, _, context, err = run(MERGE_MESSAGE, outside)
        check("outside a git checkout the hook exits 0 with a context naming git's failure",
              code == 0 and context is not None and "could not save the block" in context
              and "git rev-parse" in context, repr(context) + err)
        broken = root / "broken-checkout"
        (broken / "nc-systems" / "general-tools").mkdir(parents=True)
        (broken / "scripts").mkdir()
        shutil.copy(HOOK, broken / "nc-systems" / "general-tools" / HOOK_NAME)
        (broken / "scripts" / BRIEF_PROGRAM_NAME).write_text("raise RuntimeError('broken program')\n")
        code, _, context, err = run(MERGE_MESSAGE, repository, hook=broken / "nc-systems" / "general-tools" / HOOK_NAME)
        check("a brief program that cannot be loaded is reported in the context",
              code == 0 and context is not None and "loading" in context and "broken program" in context,
              repr(context) + err)
        code, out, _, err = run(None, repository, raw="not json")
        check("a payload that is not JSON exits 1 with the fault on stderr",
              code == 1 and out == "" and "could not read its input" in err, err)
    finally:
        shutil.rmtree(root)


for test in (test_silent_prompts, test_saves_and_reminds, test_unreadable_block, test_save_failures):
    test()

print(f"FAILED: {len(failures)} failed" if failures else "PASSED: 0 failed")
sys.exit(1 if failures else 0)
