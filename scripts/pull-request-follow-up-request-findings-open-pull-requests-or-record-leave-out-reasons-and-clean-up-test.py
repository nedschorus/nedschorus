#!/usr/bin/env python3
"""Tests for pull-request-follow-up-request-findings-open-pull-requests-or-record-leave-out-reasons-and-clean-up.py.

Each case runs the program in a scratch clone of a scratch bare origin, with the follow-up request
saved by the program's own save_follow_up_request_and_clear_answers_when_its_findings_changed(), as the hook saves it.
start, open, record-finding-leave-out-reason and finish run in a second worktree of the clone, as the forked subagent
runs them; remove-recorded-topic-branches-and-worktrees runs in the clone, as the author runs it. A fake gh first on PATH stands in for
GitHub; a pre-push hook in the clone injects a refused push.

Run: python3 scripts/pull-request-follow-up-request-findings-open-pull-requests-or-record-leave-out-reasons-and-clean-up-test.py
"""

import importlib.util
import json
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
    "pull-request-follow-up-request-findings-open-pull-requests-or-record-leave-out-reasons-and-clean-up.py")
_program_spec = importlib.util.spec_from_file_location("follow_up_program", PROGRAM)
program = importlib.util.module_from_spec(_program_spec)
_program_spec.loader.exec_module(program)

NUMBER = 1964
BLOCK = (f"#follow_up_request pull request {NUMBER}\n"
         "1. Codex P2 (:519-520): keep the padding when rebuilding code spans.\n"
         "2. mac-claude (inline at :713): send every R through repeat_line.\n")
LINK = "https://github.com/nedschorus/nedschorus/pull/2001"
OPEN_LINK = "https://github.com/nedschorus/nedschorus/pull/2002"
ALREADY_OPEN = f'a pull request for branch "topic-one" into branch "main" already exists:\n{OPEN_LINK}'
NOT_PASSING_END = ("that the follow-up of pull request 1964 is stopped until it is fixed.\n"
                   "If you are a subagent, pass that sentence to the agent that dispatched you instead.\n")
DESCRIPTION = "Keep code span padding\n\nKeeps the padding.\n\n#no_defect_fixed\n"
FAKE_GH = """#!/bin/sh
printf '%s\\036' "$*" >> "$FAKE_GH_LOG"
[ -n "$FAKE_GH_KILLED" ] && kill -"$FAKE_GH_KILLED" $$
[ -n "$FAKE_GH_CREATE_FAILS_SILENTLY" ] && exit 1
if [ -n "$FAKE_GH_CREATE_ERROR" ]; then
    printf '%s\n' "$FAKE_GH_CREATE_ERROR" >&2
    exit 1
fi
if [ -n "$FAKE_GH_CREATE_FAILS" ]; then
    echo "GraphQL: something went wrong" >&2
    exit 1
fi
printf 'Creating pull request\\n%s\\n' "${FAKE_GH_CREATE_OUTPUT-https://github.com/nedschorus/nedschorus/pull/2001}"
"""

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


class Case:
    """A bare origin, the author's clone, a fake gh, and the subagent's worktree once made."""

    def __init__(self):
        self.root = Path(os.path.realpath(tempfile.mkdtemp(prefix="follow-up-program-test-")))
        self.origin = self.root / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.origin)], check=True)
        self.repository = self.root / "repository"
        subprocess.run(["git", "clone", "-q", str(self.origin), str(self.repository)], check=True,
                       capture_output=True)
        git(self.repository, "config", "user.email", "test@example.invalid")
        git(self.repository, "config", "user.name", "test")
        git(self.repository, "config", "core.hooksPath", str(self.repository / ".git" / "hooks"))
        (self.repository / "base.txt").write_text("base\n")
        # As the repository's own .gitignore does, so the file left after open-pull-request is no change.
        (self.repository / ".gitignore").write_text(
            "/" + program.FOLLOW_UP_PULL_REQUEST_TITLE_AND_DESCRIPTION_FILE_NAME + "\n")
        git(self.repository, "add", "base.txt", ".gitignore")
        git(self.repository, "commit", "-q", "-m", "base")
        git(self.repository, "push", "-q", "origin", "main")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        (self.bin / "gh").write_text(FAKE_GH)
        (self.bin / "gh").chmod(0o755)
        self.gh_log = self.root / "gh.log"
        self.environment = {**os.environ, "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
                            "FAKE_GH_LOG": str(self.gh_log)}
        self.worktree = None

    def save(self, text=BLOCK):
        [request] = program.parse_follow_up_request_blocks_from_message_text(text)
        return program.save_follow_up_request_and_clear_answers_when_its_findings_changed(request, str(self.repository))

    def subagent_worktree(self, name="subagent-worktree"):
        self.worktree = self.root / name
        git(self.repository, "worktree", "add", "-q", "--detach", str(self.worktree))
        return self.worktree

    def run(self, directory, *arguments, **environment):
        completed = subprocess.run([sys.executable, str(PROGRAM), str(NUMBER), *map(str, arguments)],
                                   cwd=directory, capture_output=True, text=True,
                                   stdin=subprocess.DEVNULL, env={**self.environment, **environment})
        return completed.returncode, completed.stdout, completed.stderr

    def states(self):
        return self.repository / ".git" / program.PULL_REQUEST_FOLLOW_UP_REQUESTS_DIRECTORY_NAME

    def topic_branches(self):
        path = self.states() / f"pull-request-{NUMBER}-follow-up-topic-branches-and-worktrees.json"
        return json.loads(path.read_text()) if path.exists() else None

    def answers(self):
        path = self.states() / f"pull-request-{NUMBER}-follow-up-finding-answers.json"
        return json.loads(path.read_text()) if path.exists() else None

    def gh_calls(self):
        return self.gh_log.read_text().split("\x1e")[:-1] if self.gh_log.exists() else []

    def commit_change(self, name="change.txt"):
        (self.worktree / name).write_text("change\n")
        git(self.worktree, "add", name)
        git(self.worktree, "commit", "-q", "-m", "change")

    def write_description(self, text=DESCRIPTION):
        path = self.worktree / program.FOLLOW_UP_PULL_REQUEST_TITLE_AND_DESCRIPTION_FILE_NAME
        path.write_text(text)
        return path

    def close(self):
        for path in self.root.rglob("*"):
            if path.is_dir() and not path.is_symlink():
                path.chmod(0o700)
        shutil.rmtree(self.root)


def test_help():
    completed = subprocess.run([sys.executable, str(PROGRAM), "--help"], capture_output=True, text=True)
    check("--help exits 0 and names every subcommand",
          completed.returncode == 0 and all(name in completed.stdout for name in
                                            ("start-topic-branch", "open-pull-request", "record-finding-leave-out-reason", "finish-follow-up-request-and-print-merge-lane-2-message", "remove-recorded-topic-branches-and-worktrees")),
          completed.stdout)


def test_block_parsing():
    message = ("PR 1964 merged.\n" + BLOCK + "— merge-lane-2 on ned-box\n")
    [request] = program.parse_follow_up_request_blocks_from_message_text(message)
    check("a block ends at the first line that is not a numbered finding",
          request.number == NUMBER and request.text == BLOCK and request.finding_count == 2, request.text)
    check("text without the request line holds no block",
          program.parse_follow_up_request_blocks_from_message_text("1. a\n2. b\n") == [])
    [ended] = program.parse_follow_up_request_blocks_from_message_text(BLOCK + "thanks\n3. a numbered line after\n")
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


def test_brief_text():
    [request] = program.parse_follow_up_request_blocks_from_message_text(BLOCK)
    brief = program.build_follow_up_request_forked_subagent_brief(request)
    command = f"python3 {program.PROGRAM} {NUMBER}"
    check("the brief quotes the findings word for word", BLOCK in brief, brief)
    check("the brief names the program once", brief.count(program.PROGRAM) == 1, brief)
    for line in (f'Each "Program:" below means: run {command} followed by the words after it.',
                 'Dispatch one subagent with the Agent tool: subagent_type "fork", isolation "worktree", '
                 'run_in_background true. Give it this whole text unchanged; it skips the lines under "For you, the author".',
                 "When it has ended, Program: remove-recorded-topic-branches-and-worktrees\n"
                 "Then ask the user each question its report holds, and open a pull request for each finding he rules for.",
                 "   Leave out too any whose change would alter a design or decision of the user's, with the reason "
                 "\"needs the user's ruling: <question>\"; end your report with each question.",
                 "3. For each topic, Program: start-topic-branch <topic-branch>",
                 "   Program: open-pull-request --handled-finding-numbers <n>[,<n>...]",
                 "4. For each finding you leave out, Program: record-finding-leave-out-reason <n> --reason \"<why>\"",
                 "5. Program: finish-follow-up-request-and-print-merge-lane-2-message",
                 f"   Write {program.FOLLOW_UP_PULL_REQUEST_TITLE_AND_DESCRIPTION_FILE_NAME} at your worktree's root"):
        check(f"the brief holds: {line}", line in brief, brief)
    words = len(brief.replace(BLOCK.rstrip("\n"), "").split())
    check("the brief, findings aside, is at most 225 words", words <= 225, str(words))


def test_no_saved_block():
    case = Case()
    try:
        for arguments in (("start-topic-branch", "topic"), ("open-pull-request", "--handled-finding-numbers", "1"),
                          ("record-finding-leave-out-reason", "1", "--reason", "x"), ("finish-follow-up-request-and-print-merge-lane-2-message",)):
            code, out, err = case.run(case.repository, *arguments)
            check(f"{arguments[0]} with no saved block refuses with exit 1",
                  code == 1 and out == "" and err.startswith(
                      f"REFUSED: No follow-up request from merge-lane-2 is saved for pull request {NUMBER}"), err)
        check("start with no saved block records nothing", case.topic_branches() is None)
        code, out, err = case.run(case.repository, "remove-recorded-topic-branches-and-worktrees")
        check("remove-recorded-topic-branches-and-worktrees with nothing recorded removes nothing and exits 0",
              code == 0 and "No topic branch is recorded" in out, out + err)
    finally:
        case.close()


def test_start():
    case = Case()
    try:
        case.save()
        worktree = case.subagent_worktree()
        git(case.repository, "commit", "-q", "--allow-empty", "-m", "newer main")
        git(case.repository, "push", "-q", "origin", "main")
        code, out, err = case.run(worktree, "start-topic-branch", "topic-one")
        check("start exits 0 and says the branch is made and recorded",
              code == 0 and "On topic branch topic-one, made from origin/main and recorded" in out, err)
        check("start switches the worktree to the new branch",
              git(worktree, "branch", "--show-current") == "topic-one")
        check("start fetches origin first, so the branch is made from the newest origin/main",
              git(worktree, "rev-parse", "HEAD") == git(case.origin, "rev-parse", "main"))
        check("start records the branch and the worktree's path",
              case.topic_branches() == [{"branch": "topic-one", "worktree": str(worktree)}],
              str(case.topic_branches()))
        code, out, err = case.run(worktree, "start-topic-branch", "topic-two")
        check("a second topic branch is recorded too",
              code == 0 and [record["branch"] for record in case.topic_branches()] == ["topic-one", "topic-two"],
              err + str(case.topic_branches()))
        origin_url = git(worktree, "remote", "get-url", "origin")
        git(worktree, "remote", "set-url", "origin", str(case.root / "missing.git"))
        code, out, err = case.run(worktree, "start-topic-branch", "topic-three")
        check("a fetch that fails is FAILED with exit 2, to be run again once, and records no branch",
              code == 2 and err.startswith("FAILED: git fetch origin") and "Run the same start-topic-branch command again once." in err
              and "that start-topic-branch fails with the error above" in err
              and "start-topic-branch stopped there; what it did before the failure stays done." in err
              and [record["branch"] for record in case.topic_branches()] == ["topic-one", "topic-two"], err)
        git(worktree, "remote", "set-url", "origin", origin_url)
        code, out, err = case.run(worktree, "start-topic-branch", "topic-one")
        check("a branch that already exists is FAILED with exit 2, telling the agent to choose another name, "
              "not to run it again",
              code == 2 and "a branch named 'topic-one' already exists" in err
              and "If git says the branch already exists or is not a valid branch name, run python3 "
                  f"{program.PROGRAM} {NUMBER} start-topic-branch <another topic-branch>\n" in err
              and "again once" not in err and err.endswith(NOT_PASSING_END)
              and git(worktree, "branch", "--show-current") == "topic-two"
              and [record["branch"] for record in case.topic_branches()] == ["topic-one", "topic-two"], err)
    finally:
        case.close()


def started(case, branch="topic-one"):
    case.save()
    worktree = case.subagent_worktree()
    code, _, err = case.run(worktree, "start-topic-branch", branch)
    assert code == 0, err
    return worktree


def test_open_refusals():
    case = Case()
    try:
        worktree = started(case)
        case.commit_change()
        code, out, err = case.run(worktree, "open-pull-request", "--handled-finding-numbers", "0")
        check("open refuses finding 0", code == 1 and "so there is no finding 0, and" in err, err)
        code, out, err = case.run(worktree, "open-pull-request", "--handled-finding-numbers", "1,3")
        check("open refuses a finding that does not exist",
              code == 1 and "merge-lane-2 sent 2 findings for pull request 1964, numbered 1 to 2, so there "
                            "is no finding 3, and open-pull-request pushed nothing." in err, err)
        code, out, err = case.run(worktree, "open-pull-request", "--handled-finding-numbers", "1")
        check("open refuses when the title and description file is missing",
              code == 1 and f"{worktree / program.FOLLOW_UP_PULL_REQUEST_TITLE_AND_DESCRIPTION_FILE_NAME} does not exist, so "
                            "open-pull-request pushed nothing." in err, err)
        for label, text in (("no blank second line", "Title\nDescription\n#no_defect_fixed\n"),
                            ("no title", "\n\n#no_defect_fixed\n"),
                            ("no description", "Title\n\n")):
            case.write_description(text)
            code, out, err = case.run(worktree, "open-pull-request", "--handled-finding-numbers", "1")
            check(f"open refuses a title and description file with {label}",
                  code == 1 and "is not the pull request's title on the first line, a blank line, then the "
                                "description, so open-pull-request pushed nothing." in err, err)
        case.write_description("Title\n\nA description without a defect line.\n")
        code, out, err = case.run(worktree, "open-pull-request", "--handled-finding-numbers", "1")
        check("open refuses a description without a defect line",
              code == 1 and "has no line beginning \"#root_cause\", \"#root_cause_not_fixed\" or "
                            "\"#no_defect_fixed\", so open-pull-request pushed nothing" in err
              and "\nAdd a line for each defect the pull request fixes, or one line if it fixes none, starting "
                  "each line with its hashtag:\n" in err
              and "\nIf the root cause stays, or none was found: #root_cause_not_fixed, then the cause, or that "
                  "none was found, and the reason, then, on the same line, #follow_up and the full "
                  "https://github.com/ link of the open issue or pull request that will fix the cause or look "
                  "for it.\n" in err, err)
        # One path sorts before the recorded worktree's and one after, so only an exact match of paths refuses both.
        for name in ("another-worktree", "unrecorded-worktree"):
            unrecorded = case.subagent_worktree(name)
            case.write_description()
            code, out, err = case.run(unrecorded, "open-pull-request", "--handled-finding-numbers", "1")
            check(f"open refuses in a worktree start-topic-branch recorded no branch for ({name})",
                  code == 1 and f"REFUSED: start-topic-branch recorded no topic branch in {unrecorded} for pull "
                                "request 1964's follow-up, so open-pull-request has no branch to push, and pushed "
                                f"nothing.\nRun python3 {program.PROGRAM} {NUMBER} start-topic-branch <topic-branch> "
                                "in this worktree" in err, err)
        case.worktree = worktree
        check("no refusal pushed or called gh",
              case.gh_calls() == [] and "topic-one" not in git(case.origin, "branch"), str(case.gh_calls()))
        code, out, err = case.run(worktree, "record-finding-leave-out-reason", "2", "--reason", "already fixed")
        code, out, err = case.run(worktree, "open-pull-request", "--handled-finding-numbers", "1,2")
        check("open refuses a finding that already has an answer, quoting the answer",
              code == 1 and "Finding 2 of pull request 1964's follow-up request already has an answer, so "
                            "open-pull-request pushed nothing:\n2. Left out: already fixed\nEach finding takes one answer: run "
                            "the same command again without that finding.\n" in err
              and "If that leaves no finding" not in err, err)
        code, out, err = case.run(worktree, "open-pull-request", "--handled-finding-numbers", "3,4")
        check("open names several findings that do not exist in the plural",
              code == 1 and "so there are no findings 3 and 4, and" in err, err)
        case.run(worktree, "record-finding-leave-out-reason", "1", "--reason", "also fixed")
        code, out, err = case.run(worktree, "open-pull-request", "--handled-finding-numbers", "1,2")
        check("open names several answered findings in the plural",
              code == 1 and "Findings 1 and 2 of pull request 1964's follow-up request already have an answer" in err
              and "without those findings.\nIf that leaves no finding, do not open this branch's pull request: "
                  "other answers already cover what it handles. Go on with the next topic, and leave the branch: "
                  "remove-recorded-topic-branches-and-worktrees shows its commits to the author, who decides "
                  "whether to keep them.\n" in err, err)
        code, out, err = case.run(worktree, "open-pull-request", "--handled-finding-numbers", "1,x")
        check("open refuses finding numbers that are not numbers", code == 2 and "such as 1,3" in err, err)
    finally:
        case.close()


def test_open():
    case = Case()
    try:
        worktree = started(case)
        case.commit_change()
        description = case.write_description()
        code, out, err = case.run(worktree, "open-pull-request", "--handled-finding-numbers", "1")
        check("open exits 0 and says what it opened and what is left",
              code == 0 and f"Opened {LINK} for finding 1 of pull request 1964's follow-up request, and "
                            "recorded it.\nFinding 2 has no answer yet.\n" in out, out + err)
        check("open pushes the branch to origin", git(case.origin, "rev-parse", "topic-one")
              == git(worktree, "rev-parse", "HEAD"))
        check("open sets the branch's upstream", git(worktree, "rev-parse", "--abbrev-ref", "@{upstream}")
              == "origin/topic-one")
        calls = case.gh_calls()
        check("open creates the pull request from the file",
              len(calls) == 1 and calls[0] == "pr create --base main --head topic-one --title Keep code span padding "
                              "--body Keeps the padding.\n\n#no_defect_fixed\n", str(calls))
        check("open records the link against the finding",
              case.answers() == {"answers": {"1": {"link": LINK, "branch": "topic-one"}}}, str(case.answers()))
        code, out, err = case.run(worktree, "start-topic-branch", "topic-two")
        case.commit_change("second.txt")
        git(worktree, "switch", "-q", "-c", "unrecorded")
        case.commit_change("unrecorded.txt")
        git(worktree, "switch", "-q", "--detach", "main")
        case.write_description("Title\n\n- **Root cause:** the old label still counts.\n")
        code, out, err = case.run(worktree, "open-pull-request", "--handled-finding-numbers", "2")
        check("open of the last finding says every finding has an answer",
              code == 0 and f"Every finding has an answer: run python3 {program.PROGRAM} {NUMBER} finish-follow-up-request-and-print-merge-lane-2-message" in out, out + err)
        check("open accepts the merge gate's old defect label, and on a detached HEAD pushes the last "
              "recorded topic branch, not what is checked out",
              git(case.origin, "rev-parse", "topic-two") == git(worktree, "rev-parse", "topic-two")
              and "unrecorded" not in git(case.origin, "branch")
              and case.gh_calls()[-1].startswith("pr create --base main --head topic-two "), str(case.gh_calls()))
    finally:
        case.close()


def test_open_failures():
    case = Case()
    try:
        worktree = started(case)
        case.commit_change()
        description = case.write_description()
        hook = case.repository / ".git" / "hooks" / "pre-push"
        hook.write_text("#!/bin/sh\necho 'pre-push: suite x fails' >&2\nexit 1\n")
        hook.chmod(0o755)
        code, out, err = case.run(worktree, "open-pull-request", "--handled-finding-numbers", "1")
        check("a refused push is FAILED with exit 2, git's output and what to do after the hook refuses",
              code == 2 and err.startswith("FAILED: git push -u origin topic-one exited 1, so no pull request was opened. git's "
                                         "output:\npre-push: suite x fails")
              and "If git's output shows the pre-push hook refusing the push, do what it says, commit "
                  "the fix, and run the same open-pull-request command again." in err
              and "Run the same open-pull-request command again once." not in err, err)
        check("a refused push calls no gh, records nothing and keeps the file",
              case.gh_calls() == [] and case.answers() is None and description.exists())
        hook.write_text("#!/bin/sh\nsleep 5\n")
        original_timeout, original_directory = program.PUSH_TIMEOUT_SECONDS, os.getcwd()
        program.PUSH_TIMEOUT_SECONDS = 0.5
        os.chdir(worktree)
        try:
            program.open_pull_request(NUMBER, [1])
        except program.StepFailed as error:
            check("a push that does not finish in time is a StepFailed a run again may pass, with the usual instructions",
                  str(error) == "git push -u origin topic-one failed (did not finish within 0.5 s), so no pull request was opened."
                  and error.instructions is None and error.passing, repr(error.instructions))
        else:
            check("a push that does not finish in time is a StepFailed a run again may pass, with the usual instructions", False)
        finally:
            program.PUSH_TIMEOUT_SECONDS = original_timeout
        original_run_git = program.git_output.run_git

        def push_cannot_start(directory, arguments, **options):
            if arguments[0] == "push":
                raise program.git_output.GitCommandFailed(arguments, directory, None, "could not start git: injected")
            return original_run_git(directory, arguments, **options)
        program.git_output.run_git = push_cannot_start
        try:
            program.open_pull_request(NUMBER, [1])
        except program.StepFailed as error:
            check("a push that cannot start is a StepFailed a run again does not pass",
                  "could not start git: injected" in str(error) and error.instructions is None and not error.passing,
                  str(error))
        else:
            check("a push that cannot start is a StepFailed a run again does not pass", False)
        finally:
            program.git_output.run_git = original_run_git
            os.chdir(original_directory)
        hook.unlink()
        code, out, err = case.run(worktree, "open-pull-request", "--handled-finding-numbers", "1", FAKE_GH_CREATE_FAILS="1")
        check("gh pr create that fails is FAILED with exit 2, naming the call without its description, recording nothing",
              code == 2 and "FAILED: gh pr create exited 1: GraphQL: something went wrong\n" in err
              and "Run the same open-pull-request command again once." in err and case.answers() is None
              and description.exists(), err)
        code, out, err = case.run(worktree, "open-pull-request", "--handled-finding-numbers", "1", FAKE_GH_CREATE_OUTPUT="no link here")
        check("gh pr create that prints no link is FAILED with exit 2, saying how to check for the pull request",
              code == 2 and "FAILED: gh pr create exited 0 but printed no pull request link, so the pull request "
                            "may be open: 'Creating pull request\\nno link here'\n" in err
              and "Check whether it is open with: gh pr list --head topic-one --json url --jq '.[].url'\n" in err
              and "the follow-up of pull request 1964 is stopped until it is recorded." in err
              and case.answers() is None, err)
        code, out, err = case.run(worktree, "open-pull-request", "--handled-finding-numbers", "1",
                                  FAKE_GH_CREATE_ERROR="a pull request for branch \"topic-one\" into branch \"main\" already exists:")
        check("gh pr create that says a pull request already exists but names none is FAILED, to be run again once",
              code == 2 and "FAILED: gh pr create exited 1: a pull request for branch" in err
              and "Run the same open-pull-request command again once." in err and case.answers() is None, err)
        code, out, err = case.run(worktree, "open-pull-request", "--handled-finding-numbers", "1",
                                  FAKE_GH_CREATE_ERROR=f"HTTP 502: bad gateway {OPEN_LINK}")
        check("gh pr create that fails naming a link, without saying a pull request is open, is FAILED",
              code == 2 and "FAILED: gh pr create exited 1: HTTP 502" in err and case.answers() is None, err)
        for signal_number in ("9", "1"):
            code, out, err = case.run(worktree, "open-pull-request", "--handled-finding-numbers", "1", FAKE_GH_KILLED=signal_number)
            check(f"a gh killed by signal {signal_number} is FAILED with exit 2, to be run again once, recording nothing",
                  code == 2 and f"FAILED: gh pr create was killed by signal {signal_number}: it printed no error text\n" in err
                  and "Run the same open-pull-request command again once." in err
                  and case.answers() is None, err)
        code, out, err = case.run(worktree, "open-pull-request", "--handled-finding-numbers", "1", FAKE_GH_CREATE_FAILS_SILENTLY="1")
        check("a gh that exits nonzero without error text is FAILED, saying it printed none",
              code == 2 and "FAILED: gh pr create exited 1: it printed no error text\n" in err, err)
        git_only = case.root / "git-only"
        git_only.mkdir()
        (git_only / "git").symlink_to(shutil.which("git"))
        code, out, err = case.run(worktree, "open-pull-request", "--handled-finding-numbers", "1", PATH=str(git_only))
        check("a gh that cannot start is FAILED with exit 2, not to be run again",
              code == 2 and "could not start gh" in err and "again once" not in err
              and err.endswith(NOT_PASSING_END), err)
        (case.bin / "gh").write_text("#!/bin/sh\nsleep 5\n")
        original_timeout = program.GH_TIMEOUT_SECONDS
        program.GH_TIMEOUT_SECONDS = 0.5
        saved_path = os.environ["PATH"]
        os.environ["PATH"] = case.environment["PATH"]
        try:
            program.gh(["pr", "list"])
        except program.StepFailed as error:
            check("a gh that does not finish in time is a StepFailed a run again may pass",
                  "did not finish within 0.5 s" in str(error) and error.passing, str(error))
        else:
            check("a gh that does not finish in time is a StepFailed a run again may pass", False)
        finally:
            os.environ["PATH"] = saved_path
            program.GH_TIMEOUT_SECONDS = original_timeout
        (case.bin / "gh").write_text(FAKE_GH)
        code, out, err = case.run(worktree, "open-pull-request", "--handled-finding-numbers", "1",
                                  FAKE_GH_CREATE_ERROR=ALREADY_OPEN)
        check("gh pr create that refuses a second pull request records the one already open, as a run again "
              "after a lost link does",
              code == 0 and f"Found already open {OPEN_LINK} for finding 1 of pull request 1964's follow-up request, and recorded it.\n" in out
              and case.answers() == {"answers": {"1": {"link": OPEN_LINK, "branch": "topic-one"}}}, out + err)
    finally:
        case.close()


def test_leave_out_and_finish():
    case = Case()
    try:
        worktree = started(case)
        code, out, err = case.run(worktree, "finish-follow-up-request-and-print-merge-lane-2-message")
        check("finish refuses, naming each finding without an answer",
              code == 1 and "Findings 1 and 2 of pull request 1964's follow-up request have no answer yet" in err
              and f"python3 {program.PROGRAM} {NUMBER} record-finding-leave-out-reason <n> --reason \"<why>\"" in err, err)
        code, out, err = case.run(worktree, "record-finding-leave-out-reason", "3", "--reason", "x")
        check("record-finding-leave-out-reason refuses a finding that does not exist",
              code == 1 and "so there is no finding 3, and nothing was recorded." in err, err)
        code, out, err = case.run(worktree, "record-finding-leave-out-reason", "1", "--reason", "  ")
        check("record-finding-leave-out-reason refuses an empty reason",
              code == 1 and "--reason is empty, so nothing was recorded for finding 1." in err
              and f"python3 {program.PROGRAM} {NUMBER} record-finding-leave-out-reason 1 --reason \"<why>\"" in err
              and case.answers() is None, err)
        code, out, err = case.run(worktree, "record-finding-leave-out-reason", "1", "--reason", "already\nfixed on main")
        check("record-finding-leave-out-reason records the reason on one line",
              code == 0 and out == "Recorded finding 1 of pull request 1964's follow-up request as left out.\n"
                                   "Finding 2 has no answer yet.\n"
              and case.answers()["answers"]["1"] == {"reason": "already fixed on main"}, out + err)
        code, out, err = case.run(worktree, "record-finding-leave-out-reason", "1", "--reason", "again")
        check("record-finding-leave-out-reason refuses a finding that already has an answer",
              code == 1 and "already has an answer, so nothing was recorded" in err
              and err.endswith("\nEach finding takes one answer, so leave this one as it is and go on with the next.\n")
              and "without that finding" not in err, err)
        code, out, err = case.run(worktree, "finish-follow-up-request-and-print-merge-lane-2-message")
        check("finish names only the finding still without an answer",
              code == 1 and "Finding 2 of pull request 1964's follow-up request has no answer yet" in err
              and err.endswith(f"\nThen run: python3 {program.PROGRAM} {NUMBER} finish-follow-up-request-and-print-merge-lane-2-message\n"), err)
        case.run(worktree, "record-finding-leave-out-reason", "2", "--reason", "a guard nothing calls for")
        code, out, err = case.run(worktree, "finish-follow-up-request-and-print-merge-lane-2-message")
        check("finish passes and prints the message for merge-lane-2",
              code == 0 and out == "Every finding of pull request 1964's follow-up request has an answer.\n"
                                   "Send merge-lane-2 this message with SendMessage:\n\n"
                                   "Follow-ups on pull request 1964, answering merge-lane-2's #follow_up_request "
                                   "pull request 1964:\n"
                                   "1. Left out: already fixed on main\n"
                                   "2. Left out: a guard nothing calls for\n", out + err)
        case.save()
        check("the same block saved again keeps the answers", case.answers() is not None)
        case.save(BLOCK + "3. a third finding\n")
        check("a changed block removes the answers but keeps the topic branches",
              case.answers() is None and case.topic_branches() is not None)
    finally:
        case.close()


def test_state_failures():
    case = Case()
    try:
        outside = case.root / "not-a-repository"
        outside.mkdir()
        code, out, err = case.run(outside, "finish-follow-up-request-and-print-merge-lane-2-message")
        check("outside a git checkout the program is FAILED with exit 2",
              code == 2 and out == "" and err.startswith("FAILED: git rev-parse")
              and f" in {outside} failed" in err
              and "\nTell the user, in one sentence, that finish-follow-up-request-and-print-merge-lane-2-message "
                  "fails with the error above and " in err
              and "again once" not in err and err.endswith(NOT_PASSING_END), err)
        saved = case.save()
        saved.write_text("not a block\n")
        code, out, err = case.run(case.repository, "finish-follow-up-request-and-print-merge-lane-2-message")
        check("a saved file that holds no block is FAILED", code == 2 and "exactly one block" in err, err)
        for label, text in (("a later pull request", BLOCK.replace(str(NUMBER), str(NUMBER + 1))),
                            ("an earlier pull request", BLOCK.replace(str(NUMBER), str(NUMBER - 1))),
                            ("two blocks", BLOCK + "\n" + BLOCK.replace(str(NUMBER), str(NUMBER - 1)))):
            saved.write_text(text)
            code, out, err = case.run(case.repository, "finish-follow-up-request-and-print-merge-lane-2-message")
            check(f"a saved file whose block is for {label} is FAILED",
                  code == 2 and "exactly one block, for this pull request" in err, err)
        saved.write_text(f"#follow_up_request pull request {NUMBER}\n2. x\n")
        code, out, err = case.run(case.repository, "finish-follow-up-request-and-print-merge-lane-2-message")
        check("a saved block with bad numbering is FAILED", code == 2 and "numbered 1, 2, 3" in err, err)
        saved.unlink()
        saved.mkdir()
        code, out, err = case.run(case.repository, "finish-follow-up-request-and-print-merge-lane-2-message")
        check("a saved file that cannot be read is FAILED", code == 2 and "could not read" in err, err)
        saved.rmdir()
        case.save()
        answers = case.states() / f"pull-request-{NUMBER}-follow-up-finding-answers.json"
        answers.write_text("{not json")
        code, out, err = case.run(case.repository, "finish-follow-up-request-and-print-merge-lane-2-message")
        check("an answers file that is not JSON is FAILED, not to be run again",
              code == 2 and "is not the JSON this program writes" in err and "again once" not in err
              and err.endswith(NOT_PASSING_END), err)
        answers.unlink()
        answers.mkdir()
        (answers / "inside").write_text("x")
        try:
            case.save(BLOCK + "3. c\n")
        except program.StepFailed as error:
            check("an answers file that cannot be removed is reported", "could not remove" in str(error), str(error))
        else:
            check("an answers file that cannot be removed is reported", False)
        shutil.rmtree(answers)
        case.save()
        case.states().chmod(0o500)
        code, out, err = case.run(case.repository, "record-finding-leave-out-reason", "1", "--reason", "x")
        check("an answers file that cannot be written is FAILED, with nothing printed on stdout",
              code == 2 and out == "" and "could not write" in err, err)
    finally:
        case.close()


def test_clean_up():
    case = Case()
    try:
        worktree = started(case)
        case.commit_change()
        case.write_description()
        case.run(worktree, "open-pull-request", "--handled-finding-numbers", "1")
        case.run(worktree, "start-topic-branch", "topic-unpushed")
        case.commit_change("unpushed.txt")
        git(worktree, "switch", "-q", "topic-one")
        git(case.repository, "worktree", "lock", "--reason", "claude agent agent-a1b2 (pid 4242)", str(worktree))
        code, out, err = case.run(case.repository, "remove-recorded-topic-branches-and-worktrees")
        check("remove-recorded-topic-branches-and-worktrees leaves a worktree the agent harness locks, and its branches, with exit 1",
              code == 1 and f"Worktree {worktree} is locked by the agent harness (lock reason: claude agent "
                            "agent-a1b2 (pid 4242)), so remove-recorded-topic-branches-and-worktrees left it" in out
              and "Wait until the subagent has ended.\n" in out
              and out.endswith(f"\nWhen you have done what each says, run: python3 {program.PROGRAM} {NUMBER} remove-recorded-topic-branches-and-worktrees\n")
              and worktree.exists() and "topic-one" in git(case.repository, "branch"), out + err)
        git(case.repository, "worktree", "unlock", str(worktree))
        git(case.repository, "worktree", "lock", "--reason", "kept by the user", str(worktree))
        code, out, err = case.run(case.repository, "remove-recorded-topic-branches-and-worktrees")
        check("remove-recorded-topic-branches-and-worktrees leaves a worktree locked for another reason, saying what to do",
              code == 1 and "is locked (lock reason: kept by the user), so remove-recorded-topic-branches-and-worktrees left it" in out
              and f"Then run: git worktree remove --force --force {worktree}" in out and worktree.exists(), out + err)
        git(case.repository, "worktree", "unlock", str(worktree))
        (worktree / "stray.txt").write_text("stray\n")
        code, out, err = case.run(case.repository, "remove-recorded-topic-branches-and-worktrees")
        check("remove-recorded-topic-branches-and-worktrees leaves a worktree with untracked files, listing them",
              code == 1 and f"Worktree {worktree} holds changed or untracked files" in out
              and "?? stray.txt" in out and f"Then run: git worktree remove --force {worktree}" in out
              and worktree.exists(), out + err)
        (worktree / "stray.txt").unlink()
        code, out, err = case.run(case.repository, "remove-recorded-topic-branches-and-worktrees")
        check("remove-recorded-topic-branches-and-worktrees removes the worktree and the pushed branch, and leaves the unpushed branch with exit 1",
              code == 1 and f"Removed worktree {worktree}." in out and "Deleted branch topic-one." in out
              and "Branch topic-unpushed holds commits on no branch of origin, so remove-recorded-topic-branches-and-worktrees left it:" in out
              and "Then run: git branch -D topic-unpushed" in out and not worktree.exists()
              and "topic-one" not in git(case.repository, "branch")
              and "topic-unpushed" in git(case.repository, "branch"), out + err)
        git(case.repository, "branch", "-D", "topic-unpushed")
        code, out, err = case.run(case.repository, "remove-recorded-topic-branches-and-worktrees")
        check("remove-recorded-topic-branches-and-worktrees run again, with everything gone, is done with exit 0",
              code == 0 and "is done: every recorded worktree and topic branch is removed." in out, out + err)
    finally:
        case.close()


def test_clean_up_goes_on_past_each_worktree_and_branch():
    case = Case()
    try:
        case.save()
        command = "remove-recorded-topic-branches-and-worktrees"
        worktrees = {}
        for name in ("gone", "locked", "clean-one", "clean-two"):
            worktrees[name] = case.subagent_worktree(f"worktree-{name}")
            code, _, err = case.run(worktrees[name], "start-topic-branch", f"branch-{name}")
            assert code == 0, err
        git(case.repository, "worktree", "remove", str(worktrees["gone"]))
        git(case.repository, "branch", "-D", "branch-gone")
        git(case.repository, "worktree", "lock", "--reason", "kept by the user", str(worktrees["locked"]))
        case.worktree = worktrees["clean-one"]
        case.commit_change()
        git(worktrees["clean-two"], "push", "-q", "origin", "branch-clean-two")
        code, out, err = case.run(case.repository, command)
        branches = git(case.repository, "branch")
        check("clean-up goes on past a worktree already gone, a locked worktree and a missing or unpushed branch",
              code == 1 and not worktrees["clean-one"].exists() and not worktrees["clean-two"].exists()
              and "Deleted branch branch-clean-two." in out and "branch-clean-two" not in branches
              and "Branch branch-clean-one holds commits on no branch of origin" in out
              and "branch-locked" in branches and worktrees["locked"].exists()
              and "left 2 worktrees or branches in place" in out, out + err)
        git(case.repository, "worktree", "unlock", str(worktrees["locked"]))
        git(case.repository, "worktree", "lock", str(worktrees["locked"]))
        code, out, err = case.run(case.repository, command)
        check("a lock without a reason is named as such",
              code == 1 and "is locked (lock reason: none given)" in out
              and "of pull request 1964's follow-up is locked (lock reason: none given), so" in out, out + err)
    finally:
        case.close()


def test_git_failure_passing():
    directory = tempfile.mkdtemp(prefix="follow-up-program-git-test-")
    try:
        cases = (("a git call that does not finish in time", ["-c", "alias.wait=!sleep 5", "wait"],
                  {"timeout_seconds": 0.5}, True),
                 ("a git call that exits nonzero", ["rev-parse", "--show-toplevel"], {}, False),
                 ("a git call marked passing that exits nonzero", ["rev-parse", "--show-toplevel"],
                  {"passing": True}, True))
        for label, arguments, options, passing in cases:
            try:
                program.git(directory, arguments, **options)
            except program.StepFailed as error:
                check(f"{label} is a StepFailed with passing {passing}", error.passing is passing, str(error))
            else:
                check(f"{label} is a StepFailed with passing {passing}", False)
    finally:
        shutil.rmtree(directory)


def test_clean_up_failure():
    case = Case()
    try:
        worktree = started(case)
        (case.repository / ".git" / "worktrees" / worktree.name / "index").write_text("not an index")
        code, out, err = case.run(case.repository, "remove-recorded-topic-branches-and-worktrees")
        check("a git command remove-recorded-topic-branches-and-worktrees cannot run is FAILED with exit 2",
              code == 2 and err.startswith("FAILED: git status --short") and "again once" not in err
              and err.endswith(NOT_PASSING_END),
              out + err)
    finally:
        case.close()


for test in (test_help, test_block_parsing, test_brief_text, test_no_saved_block, test_start,
             test_open_refusals, test_open, test_open_failures, test_leave_out_and_finish,
             test_state_failures, test_clean_up, test_clean_up_goes_on_past_each_worktree_and_branch,
             test_git_failure_passing, test_clean_up_failure):
    test()

print(f"FAILED: {len(failures)} failed" if failures else "PASSED: 0 failed")
sys.exit(1 if failures else 0)
