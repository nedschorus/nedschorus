#!/usr/bin/env python3
"""Tests for pull-request-follow-up-author-brief-from-non-blocking-findings-and-every-finding-answered-check.py.

Each case runs the program in a scratch git repository, with the follow-up request saved by the
program's own save_follow_up_request_and_clear_its_markers(), as the hook saves it, and --check run in a second worktree
of that repository, as the forked subagent runs it.

Run: python3 scripts/pull-request-follow-up-author-brief-from-non-blocking-findings-and-every-finding-answered-check-test.py
"""

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().with_name("git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

PROGRAM = Path(__file__).resolve().with_name(
    "pull-request-follow-up-author-brief-from-non-blocking-findings-and-every-finding-answered-check.py")
_program_spec = importlib.util.spec_from_file_location("follow_up_brief_program", PROGRAM)
program = importlib.util.module_from_spec(_program_spec)
_program_spec.loader.exec_module(program)

NUMBER = 1964
BLOCK = (f"#follow_up_request pull request {NUMBER}\n"
         "1. Codex P2 (:519-520): keep the padding when rebuilding code spans.\n"
         "2. mac-claude (inline at :713): send every R through repeat_line.\n")
FLAG = "--print-brief-again-after-subagent-died"

failures = []


def check(name, condition, detail=""):
    print(("PASS " if condition else "FAIL ") + name)
    if not condition:
        failures.append(name)
        if detail:
            print("     " + detail.replace("\n", "\n     "))


def git(directory, *arguments):
    return subprocess.run(["git", "-C", str(directory), *arguments], check=True,
                          capture_output=True, text=True).stdout.strip()


def scratch_repository(root):
    repository = root / "repository"
    repository.mkdir()
    git(repository, "init", "-q", "-b", "main")
    git(repository, "config", "user.email", "test@example.invalid")
    git(repository, "config", "user.name", "test")
    (repository / "base.txt").write_text("base\n")
    git(repository, "add", "base.txt")
    git(repository, "commit", "-q", "-m", "base")
    return repository


def run(directory, *arguments):
    completed = subprocess.run([sys.executable, str(PROGRAM), *map(str, arguments)], cwd=directory,
                               capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return completed.returncode, completed.stdout, completed.stderr


def states(repository):
    return repository / ".git" / program.PULL_REQUEST_FOLLOW_UP_REQUESTS_DIRECTORY_NAME


def save(repository, text=BLOCK):
    [request] = program.parse_follow_up_request_blocks_from_message_text(text)
    return program.save_follow_up_request_and_clear_its_markers(request, str(repository))


def case(name):
    root = Path(tempfile.mkdtemp(prefix="follow-up-brief-test-"))
    return root, scratch_repository(root)


def test_help():
    code, out, _ = run(".", "--help")
    check("--help exits 0 and names both modes", code == 0 and "--check" in out and FLAG in out, out)


def test_block_parsing():
    message = ("PR 1964 merged.\n" + BLOCK + "— merge-lane-2 on ned-box\n")
    [request] = program.parse_follow_up_request_blocks_from_message_text(message)
    check("a block ends at the first line that is not a numbered finding",
          request.number == NUMBER and request.text == BLOCK and request.finding_count == 2, request.text)
    check("text without the request line holds no block", program.parse_follow_up_request_blocks_from_message_text("1. a\n2. b\n") == [])
    [three] = program.parse_follow_up_request_blocks_from_message_text(f"#follow_up_request pull request {NUMBER}\n1. a\n2. b\n3. c\n")
    check("a block of three findings counts three", three.finding_count == 3, str(three.finding_count))
    [ended] = program.parse_follow_up_request_blocks_from_message_text(BLOCK + "thanks\n3. a numbered line after the block\n")
    check("a numbered line after the block's end is not a finding", ended.text == BLOCK, ended.text)
    for label, text in (("no findings", f"#follow_up_request pull request {NUMBER}\nthanks\n"),
                        ("numbering that skips", f"#follow_up_request pull request {NUMBER}\n1. a\n3. b\n"),
                        ("numbering that starts at 2", f"#follow_up_request pull request {NUMBER}\n2. a\n"),
                        ("a repeated number", f"#follow_up_request pull request {NUMBER}\n1. a\n1. b\n")):
        try:
            program.parse_follow_up_request_blocks_from_message_text(text)
        except ValueError as error:
            check(f"a block with {label} is refused, naming the pull request", str(NUMBER) in str(error), str(error))
        else:
            check(f"a block with {label} is refused, naming the pull request", False)


def test_no_saved_block():
    root, repository = case("no saved block")
    try:
        code, out, err = run(repository, NUMBER)
        check("with no saved block the brief refuses with exit 1",
              code == 1 and out == "" and err.startswith("REFUSED: No follow-up request from merge-lane-2 "
                                                         f"is saved for pull request {NUMBER}"), err)
        code, out, err = run(repository, NUMBER, "--check")
        check("with no saved block --check refuses with exit 1", code == 1 and "No follow-up request" in err, err)
    finally:
        shutil.rmtree(root)


def test_brief_and_second_run():
    root, repository = case("brief")
    try:
        save(repository)
        code, out, err = run(repository, NUMBER)
        check("the brief exits 0", code == 0, err)
        check("the brief prints the saved block word for word", BLOCK in out, out)
        check("the brief says how to dispatch the forked subagent",
              'subagent_type: "fork"' in out and 'isolation: "worktree"' in out
              and "run_in_background: true" in out, out)
        check("the brief names the --check command to finish with",
              f"python3 {program.PROGRAM} {NUMBER} --check" in out, out)
        check("the brief names the answers file at the worktree root",
              f"follow-up-answers-pull-request-{NUMBER}.md at the root of your worktree" in out, out)
        check("the brief marks the brief printed",
              (states(repository) / f"pull-request-{NUMBER}-brief-printed-marker").exists())
        code, out, err = run(repository, NUMBER)
        check("a second brief refuses with exit 1 and prints no brief", code == 1 and out == "", err)
        check("the second brief's refusal names the flag that prints the brief again",
              f"python3 {program.PROGRAM} {NUMBER} {FLAG}" in err, err)
        code, out, err = run(repository, NUMBER, FLAG)
        check(f"{FLAG} prints the brief again", code == 0 and BLOCK in out, err)
        code, out, err = run(repository, NUMBER, "--check", FLAG)
        check(f"--check with {FLAG} is a usage error", code == 2 and "not allowed with" in err, err)
    finally:
        shutil.rmtree(root)


def subagent_worktree(repository):
    worktree = repository.parent / "subagent-worktree"
    git(repository, "worktree", "add", "-q", "-b", "follow-up-topic", str(worktree))
    return worktree


def test_check():
    root, repository = case("check")
    try:
        save(repository)
        run(repository, NUMBER)
        worktree = subagent_worktree(repository)
        answers = worktree / f"follow-up-answers-pull-request-{NUMBER}.md"
        code, out, err = run(worktree, NUMBER, "--check")
        check("--check with no answers file fails with exit 2 and marks nothing",
              code == 2 and out == "" and "could not read the answers file" in err
              and not (states(repository) / f"pull-request-{NUMBER}-every-finding-answered-check-passed-marker").exists(), err)
        answers.write_text("1. https://github.com/nedschorus/nedschorus/pull/2001\n")
        code, out, err = run(worktree, NUMBER, "--check")
        check("--check refuses, naming the unanswered finding, with exit 1",
              code == 1 and out == "" and "no entry for finding 2" in err
              and "merge-lane-2 sent 2 findings" in err, err)
        answers.write_text("1. https://github.com/nedschorus/nedschorus/pull/2001\n1. again\n2. x\n")
        code, out, err = run(worktree, NUMBER, "--check")
        check("--check refuses two entries for one finding", code == 1 and "two entries for finding 1" in err, err)
        answers.write_text("1. https://github.com/nedschorus/nedschorus/pull/2001\n2. x\n3. y\n")
        code, out, err = run(worktree, NUMBER, "--check")
        check("--check refuses an entry for a finding that does not exist",
              code == 1 and "an entry for finding 3, which does not exist" in err, err)
        answers.write_text("1. https://github.com/nedschorus/nedschorus/pull/2001\n"
                           "2. Left out: repeat_line already handles every R on origin/main.\n")
        code, out, err = run(worktree, NUMBER, "--check")
        check("--check passes in the subagent's worktree with every finding answered", code == 0, err)
        check("--check prints the message for merge-lane-2 with each answer",
              "Send merge-lane-2 this message with SendMessage:" in out
              and "1. https://github.com/nedschorus/nedschorus/pull/2001" in out
              and "2. Left out: repeat_line already handles every R on origin/main." in out
              and "1 of 2 findings answered with a pull request link" in out, out)
        check("--check marks the follow-up request answered in the shared git directory",
              (states(repository) / f"pull-request-{NUMBER}-every-finding-answered-check-passed-marker").exists())
        code, out, err = run(repository, NUMBER, FLAG)
        check("once --check has passed, the brief refuses even with the flag",
              code == 1 and out == "" and "is already answered" in err, err)
        other = root / "other-answers.md"
        other.write_text("1. a\n2. b\n")
        code, out, err = run(worktree, NUMBER, "--check", "--answers", other)
        check("--answers names another answers file", code == 0 and "1. a" in out, err)
    finally:
        shutil.rmtree(root)


def test_new_block_resets_marks():
    root, repository = case("reset")
    try:
        save(repository)
        run(repository, NUMBER)
        save(repository)
        code, _, _ = run(repository, NUMBER)
        check("the same block saved again keeps the brief-printed mark", code == 1)
        save(repository, BLOCK + "3. a third finding\n")
        code, out, err = run(repository, NUMBER)
        check("a changed block removes the marks, so the brief prints", code == 0 and "3. a third finding" in out, err)
        marker = states(repository) / f"pull-request-{NUMBER}-brief-printed-marker"
        marker.unlink()
        marker.mkdir()
        (marker / "inside").write_text("x")
        try:
            save(repository, BLOCK)
        except program.StepFailed as error:
            check("a mark that cannot be removed is reported", "could not remove" in str(error), str(error))
        else:
            check("a mark that cannot be removed is reported", False)
    finally:
        shutil.rmtree(root)


def test_failures():
    root, repository = case("failures")
    try:
        outside = root / "not-a-repository"
        outside.mkdir()
        code, out, err = run(outside, NUMBER)
        check("outside a git checkout the program fails with exit 2",
              code == 2 and out == "" and err.startswith("FAILED: git rev-parse") and "Run the same command again once." in err, err)
        saved = save(repository)
        saved.write_text("not a block\n")
        code, out, err = run(repository, NUMBER)
        check("a saved file that holds no block fails with exit 2",
              code == 2 and "cannot be read" in err and "exactly one block" in err, err)
        saved.write_text(BLOCK + "\n" + BLOCK)
        code, out, err = run(repository, NUMBER)
        check("a saved file that holds two blocks fails with exit 2", code == 2 and "exactly one block" in err, err)
        for other in (NUMBER - 1, NUMBER + 1):
            saved.write_text(BLOCK.replace(str(NUMBER), str(other)))
            code, out, err = run(repository, NUMBER)
            check(f"a saved file whose block names pull request {other} fails with exit 2",
                  code == 2 and "exactly one block, for this pull request" in err, err)
        saved.write_text(f"#follow_up_request pull request {NUMBER}\n2. x\n")
        code, out, err = run(repository, NUMBER)
        check("a saved block with bad numbering fails with exit 2", code == 2 and "numbered 1, 2, 3" in err, err)
        saved.unlink()
        saved.mkdir()
        code, out, err = run(repository, NUMBER)
        check("a saved file that cannot be read fails with exit 2", code == 2 and "could not read" in err, err)
        shutil.rmtree(saved)
        save(repository)
        os.chmod(states(repository), 0o500)
        try:
            code, out, err = run(repository, NUMBER)
            check("a brief whose mark cannot be written fails with exit 2 and prints no brief",
                  code == 2 and out == "" and "could not write" in err, err)
            worktree = subagent_worktree(repository)
            (worktree / f"follow-up-answers-pull-request-{NUMBER}.md").write_text("1. a\n2. b\n")
            code, out, err = run(worktree, NUMBER, "--check")
            check("a --check whose mark cannot be written fails with exit 2 and prints no message",
                  code == 2 and out == "" and "could not write" in err, err)
        finally:
            os.chmod(states(repository), 0o700)
    finally:
        shutil.rmtree(root)


for test in (test_help, test_block_parsing, test_no_saved_block, test_brief_and_second_run, test_check,
             test_new_block_resets_marks, test_failures):
    test()

print(f"FAILED: {len(failures)} failed" if failures else "PASSED: 0 failed")
sys.exit(1 if failures else 0)
