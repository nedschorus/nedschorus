#!/usr/bin/env python3
"""Tests for merge-lane-pull-request-claude-reviewer-headless-run-and-review-post.py.

Real git in a scratch directory: a repository whose head commit is checked
out, detached, as wt/pr7-head under a scratch worktrees and outputs directory,
as step 1 builds it, with the brief step 2 writes beside it. A stand-in claude
and a stand-in gh go first on PATH, and HOME holds a mac-claude token file, so
no case runs a model or reaches GitHub. The stand-in claude logs its
arguments, standard input, directory and environment, and answers as
FAKE_CLAUDE_MODE says: valid, null, invalid, could-not-review, nonzero,
not-json, hang (it writes its pid, starts a child that also sleeps, and
writes the child's pid), leave-child (it starts a sleeping child whose output
goes to /dev/null, writes the child's pid, and answers validly), or move-head
(it checks the head worktree out at another commit). Every
mode first makes a worktree named mac-claude-pr7-mutation, as a reviewer does.
The stand-in gh answers the author lookup with ned-review-merge, the pull
request's files with a diff of scripts/thing.py lines 1 to 3, the post with
review id 42, and the read-back as posted, unless FAKE_GH_FAILS names the post, or
FAKE_GH_HANGS names it, when it writes its pid to gh-post-started and sleeps.

Run: python3 scripts/merge-lane-pull-request-claude-reviewer-headless-run-and-review-post-test.py
"""

import contextlib
import importlib.util
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).resolve().with_name(
        "git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

PROGRAM = Path(__file__).with_name(
    "merge-lane-pull-request-claude-reviewer-headless-run-and-review-post.py")
SCHEMA = Path(__file__).with_name("merge-lane-pull-request-claude-reviewer-review-schema.json")
BRIEF = "Review pull request 7.\nThe brief's last line.\n"
GIT_ENVIRONMENT = {
    **{key: value for key, value in os.environ.items() if not key.startswith("GIT_")},
    "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid",
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
}

FAKE_CLAUDE = r'''#!/usr/bin/env python3
import json, os, subprocess, sys, time
from pathlib import Path
state = Path(os.environ["FAKE_CLAUDE_STATE"])
prompt = sys.stdin.read()
with open(state / "claude-calls.jsonl", "a") as log:
    log.write(json.dumps({"argv": sys.argv[1:], "stdin": prompt, "cwd": os.getcwd(),
                          "env": {key: os.environ.get(key) for key in
                                  ("GH_TOKEN", "GITHUB_TOKEN", "GH_CONFIG_DIR")}}) + "\n")
subprocess.run(["git", "worktree", "add", "-q", "--detach",
                str(state / "reviewer-scratch" / "wt" / "mac-claude-pr7-mutation"), "HEAD"],
               check=True, capture_output=True)
mode = os.environ["FAKE_CLAUDE_MODE"]
answer = {"verdict": "APPROVE", "body": "Looks right.",
          "comments": [{"path": "scripts/thing.py", "line": 2, "body": "A remark."}],
          "note": os.environ.get("FAKE_CLAUDE_NOTE", "")}
output = {"type": "result", "subtype": "success", "is_error": False, "session_id": "session-77",
          "result": "The reviewer's text answer.", "structured_output": answer,
          "permission_denials": [{"tool_name": "Bash",
                                  "tool_input": {"command": "rm -rf /tmp/x"}}]}
if mode == "null":
    output["structured_output"] = None
elif mode == "invalid":
    output["structured_output"] = {"verdict": "MAYBE", "body": "b", "comments": [], "note": ""}
elif mode == "no-note":
    del answer["note"]
elif mode == "note-not-text":
    answer["note"] = 5
elif mode == "could-not-review":
    output["structured_output"] = {"verdict": "COULD_NOT_REVIEW",
                                   "body": "Bash was refused, so nothing ran.", "comments": [],
                                   "note": os.environ.get("FAKE_CLAUDE_NOTE", "")}
elif mode == "nonzero":
    print("claude: API error 529", file=sys.stderr)
    sys.exit(3)
elif mode == "not-json":
    print("not json at all")
    sys.exit(0)
elif mode == "hang":
    (state / "claude.pid").write_text(str(os.getpid()))
    child = subprocess.Popen(["sleep", "60"])
    (state / "child.pid").write_text(str(child.pid))
    time.sleep(60)
elif mode == "leave-child":
    child = subprocess.Popen(["sleep", "60"], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
    (state / "child.pid").write_text(str(child.pid))
elif mode == "move-head":
    subprocess.run(["git", "checkout", "-q", "--detach", "HEAD~1"], check=True)
print(json.dumps(output))
'''

FAKE_GH = r'''#!/usr/bin/env python3
import json, os, sys, time
from pathlib import Path
state = Path(os.environ["FAKE_CLAUDE_STATE"])
arguments = sys.argv[1:]
stdin = sys.stdin.read() if "--input" in arguments else ""
with open(state / "gh-calls.jsonl", "a") as log:
    log.write(json.dumps({"arguments": arguments, "stdin": stdin}) + "\n")
path = next(argument for argument in arguments if argument.startswith("repos/"))
if "POST" in arguments:
    if os.environ.get("FAKE_GH_HANGS") == "post":
        (state / "gh-post-started").write_text(str(os.getpid()))
        time.sleep(60)
    if os.environ.get("FAKE_GH_FAILS") == "post":
        print("gh: HTTP 502: Bad Gateway", file=sys.stderr)
        sys.exit(1)
    (state / "posted.json").write_text(stdin)
    print(json.dumps({"id": 42}))
elif "/reviews/" in path:
    posted = json.loads((state / "posted.json").read_text())
    states = {"APPROVE": "APPROVED", "REQUEST_CHANGES": "CHANGES_REQUESTED", "COMMENT": "COMMENTED"}
    print(json.dumps({"id": 42, "state": states[posted["event"]], "commit_id": posted["commit_id"]}))
elif "/files" in path:
    print(json.dumps([[{"filename": "scripts/thing.py", "patch": "@@ -1,1 +1,3 @@\n a\n+b\n+c"}]]))
else:
    print(json.dumps({"user": {"login": "ned-review-merge"}}))
'''

failures = []


def check(name, condition, detail=""):
    """Report one case; condition is a callable, so an error in it fails only this case."""
    try:
        passed = condition()
    except Exception as error:
        passed = False
        detail = f"the check raised {type(error).__name__}: {error}\n{detail}"
    print(("PASS  " if passed else "FAIL  ") + name)
    if not passed:
        failures.append(name)
        if detail:
            print("      " + detail.replace("\n", "\n      "))


def git(directory, *arguments):
    return subprocess.run(["git", "-C", str(directory), *arguments], capture_output=True,
                          text=True, check=True, env=GIT_ENVIRONMENT).stdout.strip()


def running(pid):
    """Whether pid is a live process, not gone and not a zombie."""
    try:
        status = Path(f"/proc/{pid}/status").read_text()
    except OSError:
        return False
    return "\nState:\tZ" not in status


def read_lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


class Case:
    """One case's repository, head worktree, brief, stand-ins and run."""

    counter = 0

    def __init__(self, scratch):
        Case.counter += 1
        root = scratch / f"case-{Case.counter}"
        self.state, self.helpers, home, bin_directory = (
            root / "state", root / "helpers", root / "home", root / "bin")
        for directory in (self.state, home, bin_directory):
            directory.mkdir(parents=True)
        repository = root / "repository"
        subprocess.run(["git", "init", "-q", "-b", "main", str(repository)], check=True,
                       env=GIT_ENVIRONMENT)
        for name in ("base.txt", "head.txt"):
            (repository / name).write_text(name + "\n")
            git(repository, "add", ".")
            git(repository, "commit", "-q", "-m", name)
        self.head = git(repository, "rev-parse", "HEAD")
        self.head_worktree = self.helpers / "wt" / "pr7-head"
        git(repository, "worktree", "add", "-q", "--detach", str(self.head_worktree), self.head)
        (self.helpers / "briefs").mkdir()
        (self.helpers / "briefs" / "brief-7a-mac-claude.md").write_text(BRIEF)
        (home / ".config" / "nedschorus").mkdir(parents=True)
        (home / ".config" / "nedschorus" / "mac-claude.token").write_text("stand-in-token\n")
        for name, text in (("claude", FAKE_CLAUDE), ("gh", FAKE_GH)):
            (bin_directory / name).write_text(text)
            (bin_directory / name).chmod(0o755)
        self.environment = {**GIT_ENVIRONMENT, "HOME": str(home),
                            "FAKE_CLAUDE_STATE": str(self.state),
                            "GH_TOKEN": "a-token-the-reviewer-must-not-see",
                            "GITHUB_TOKEN": "another-token-the-reviewer-must-not-see",
                            "PATH": f"{bin_directory}{os.pathsep}{os.environ.get('PATH', '')}"}

    def command(self, tag, head, options):
        return [sys.executable, str(PROGRAM), "7", tag, head or self.head, *options,
                "--merge-lane-worktrees-and-outputs-directory", str(self.helpers),
                "--review-tools-worktree-at-main", str(self.helpers / "wt" / "main")]

    def run(self, mode="valid", *options, tag="7a", head=None, **environment):
        completed = subprocess.run(
            self.command(tag, head, options), capture_output=True, text=True,
            env={**self.environment, "FAKE_CLAUDE_MODE": mode, **environment})
        self.code, self.stdout = completed.returncode, completed.stdout + completed.stderr
        return self.read_calls()

    def interrupt(self, signal_number, mode="hang", started="child.pid", **environment):
        """Run in mode and send the program signal_number once the state file started exists."""
        process = subprocess.Popen(
            self.command("7a", None, ("--time-limit-seconds", "60")), stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True,
            env={**self.environment, "FAKE_CLAUDE_MODE": mode, **environment})
        deadline = time.monotonic() + 20
        started = self.state / started
        # gh-post-started holds the stand-in gh's pid, which a case reads after the signal.
        while (not (started.exists() and started.read_text())
               and time.monotonic() < deadline):
            time.sleep(0.05)
        process.send_signal(signal_number)
        try:
            self.stdout = process.communicate(timeout=30)[0]
            self.code = process.returncode
        except subprocess.TimeoutExpired:
            process.kill()
            self.stdout = process.communicate()[0] + "\n(the program was still running 30 s after the signal)"
            self.code = 0
        return self.read_calls()

    def read_calls(self):
        self.claude_calls = read_lines(self.state / "claude-calls.jsonl")
        self.gh_calls = read_lines(self.state / "gh-calls.jsonl")
        self.detail = f"exit {self.code}\n{self.stdout}\nclaude: {self.claude_calls}\ngh: {self.gh_calls}"
        return self

    def record(self, suffix=""):
        return self.helpers / "claude-reviews" / f"pr7-{self.head}{suffix}"

    def reviewer_worktree_left(self):
        return "mac-claude-pr7-mutation" in git(self.head_worktree, "worktree", "list")

    def reviewer_processes_alive(self):
        return [pid for pid in (self.state / "claude.pid", self.state / "child.pid")
                if not pid.exists() or running(int(pid.read_text()))]

    def posted(self):
        return any("POST" in call["arguments"] for call in self.gh_calls)


def main():
    scratch = Path(tempfile.mkdtemp(prefix="claude-reviewer-headless-run-test-")).resolve()
    try:
        reported = io.StringIO()
        with contextlib.redirect_stdout(reported):
            check("a check that raises", lambda: (scratch / "posted.json").read_text())
        raised_case_failed = failures[-1:] == ["a check that raises"]
        del failures[len(failures) - raised_case_failed:]
        check("a case whose check raises, as reading a posted.json no post wrote does, fails with "
              "the error, and the cases after it still run",
              lambda: raised_case_failed and "FAIL  a check that raises" in reported.getvalue()
              and "the check raised FileNotFoundError" in reported.getvalue(),
              reported.getvalue())

        case = Case(scratch).run("valid")
        call = case.claude_calls[0] if case.claude_calls else {}
        check("a valid answer is posted as mac-claude, and the step exits 0",
              lambda: case.code == 0 and case.posted()
              and "PR 7: Claude review posted, verdict APPROVE." in case.stdout, case.detail)
        check("claude runs headless with the schema, JSON output, dontAsk and the six tools, "
              "and no prompt argument after them",
              lambda: call.get("argv") == ["-p", "--json-schema", SCHEMA.read_text(),
                                           "--output-format", "json", "--permission-mode",
                                           "dontAsk", "--allowedTools", "Read", "Grep", "Glob",
                                           "Bash", "WebFetch", "WebSearch"],
              case.detail)
        check("the brief is the reviewer's standard input, and it runs in the head worktree",
              lambda: call.get("stdin") == BRIEF and call.get("cwd") == str(case.head_worktree),
              case.detail)
        gh_config = call.get("env", {}).get("GH_CONFIG_DIR")
        check("the reviewer gets no GitHub token and an empty gh config directory",
              lambda: call.get("env", {}).get("GH_TOKEN") is None
              and call.get("env", {}).get("GITHUB_TOKEN") is None
              and gh_config == str(case.record() / "gh-config-empty")
              and not any(Path(gh_config).iterdir()), case.detail)

        def posted_as_answered():
            posted = json.loads((case.state / "posted.json").read_text())
            return (posted["event"] == "APPROVE" and posted["commit_id"] == case.head
                    and posted["body"] == "APPROVE\n\nLooks right."
                    and posted["comments"] == [
                        {"path": "scripts/thing.py", "line": 2, "body": "A remark."}])
        check("the review posted is the reviewer's answer, as the review event on a pull "
              "request ned-review-merge opened", posted_as_answered, case.detail)
        check("the records hold the run's output, its stderr, the answer, what posting printed "
              "and the session to resume",
              lambda: json.loads((case.record() / "run.json").read_text())["session_id"]
              == "session-77"
              and (case.record() / "run-stderr.txt").exists()
              and json.loads((case.record() / "review.json").read_text())["verdict"] == "APPROVE"
              and "review 42 posted" in (case.record() / "posted.txt").read_text()
              and (case.record() / "resume.txt").read_text()
              == f"session-77\n{case.head_worktree}\n", case.detail)
        check("the follow-up command is printed whole, with where to run it",
              lambda: f"run from {case.head_worktree}" in case.stdout
              and "claude -p --resume session-77 --permission-mode dontAsk --allowedTools Read "
                  "Grep Glob Bash WebFetch WebSearch" in case.stdout, case.detail)
        check("each refused tool call is printed",
              lambda: "the reviewer was refused a Bash call it asked for: rm -rf /tmp/x"
              in case.stdout, case.detail)
        check("the reviewer's own worktree is removed after the run",
              lambda: not case.reviewer_worktree_left(), case.detail)

        case = Case(scratch)
        others = [case.helpers / "wt" / name for name in
                  ("mac-claude-pr70-mutation", "mac-claude-pr8-mutation")]
        for other in others:
            git(case.head_worktree, "worktree", "add", "-q", "--detach", str(other), "HEAD")
        case.run("valid")
        listed = git(case.head_worktree, "worktree", "list")
        check("another pull request's reviewer worktrees, pr70 and pr8, survive the cleanup",
              lambda: case.code == 0 and not case.reviewer_worktree_left()
              and all(str(other) in listed for other in others), case.detail + "\n" + listed)
        check("an answer with an empty note says there was none, and note.txt is empty",
              lambda: "PR 7: the reviewer left no note for merge-lane-2." in case.stdout
              and (case.record() / "note.txt").read_text() == "", case.detail)
        case.run("valid")
        check("a second run on the same head keeps the first run's records and writes -2",
              lambda: case.code == 0 and (case.record() / "review.json").exists()
              and (case.record("-2") / "review.json").exists(), case.detail)

        note = "The retry loop in thing.py hides a design question for the user."
        case = Case(scratch).run("valid", FAKE_CLAUDE_NOTE=note)
        check("the reviewer's note is printed for merge-lane-2 and saved, and reaches neither "
              "review.json nor any gh call",
              lambda: case.code == 0 and case.posted()
              and f"PR 7: the reviewer's note for merge-lane-2, which is private and never posted "
                  f"to the pull request; also saved in {case.record() / 'note.txt'}:\n{note}\n"
                  in case.stdout
              and (case.record() / "note.txt").read_text() == note + "\n"
              and note not in (case.record() / "review.json").read_text()
              and not any(note in call["stdin"] or note in " ".join(call["arguments"])
                          for call in case.gh_calls), case.detail)

        for mode, expected in (
                ("null", "the reviewer finished without an answer the review schema accepts"),
                ("invalid", "the reviewer's answer is not a valid review: its verdict 'MAYBE'"),
                ("no-note", "its keys are ['body', 'comments', 'verdict'], not verdict, body, "
                            "comments and note"),
                ("note-not-text", "the reviewer's answer is not a valid review: its note is not text"),
                ("could-not-review", "the reviewer could not finish the review"),
                ("nonzero", "claude exited 3: claude: API error 529"),
                ("not-json", "claude printed no JSON output"),
                ("move-head", f"moved to")):
            case = Case(scratch).run(mode)
            check(f"a {mode} run posts nothing, exits 1, says why, and removes the reviewer's "
                  f"worktree",
                  lambda: case.code == 1 and not case.posted() and expected in case.stdout
                  and "PR 7: Claude review not posted: " in case.stdout
                  and "Nothing was posted on GitHub." in case.stdout
                  and not case.reviewer_worktree_left(), case.detail)
        case = Case(scratch).run("could-not-review", FAKE_CLAUDE_NOTE="Bash needs allowing.")
        check("a COULD_NOT_REVIEW answer's note is still printed and saved, and nothing is posted",
              lambda: case.code == 1 and not case.posted()
              and "which is private and never posted to the pull request; also saved in"
              in case.stdout
              and (case.record() / "note.txt").read_text() == "Bash needs allowing.\n",
              case.detail)
        case = Case(scratch).run("could-not-review")
        check("a COULD_NOT_REVIEW answer's reason is printed",
              lambda: case.stdout.count("Bash was refused, so nothing ran.") == 1, case.detail)

        case = Case(scratch)
        started = time.monotonic()
        case.run("hang", "--time-limit-seconds", "2")
        took = time.monotonic() - started
        time.sleep(0.2)
        check("a reviewer past its time limit is killed with its children, posts nothing, "
              "and exits 1",
              lambda: case.code == 1 and not case.posted() and took < 30
              and not running(int((case.state / "child.pid").read_text()))
              and "ran past its 2-second limit and was killed" in case.stdout, case.detail)

        for signal_number in (signal.SIGTERM, signal.SIGINT):
            case = Case(scratch).interrupt(signal_number)
            time.sleep(0.2)
            check(f"{signal.Signals(signal_number).name} during the wait kills the reviewer and "
                  f"its children, removes its worktree, posts nothing, and exits nonzero",
                  lambda: case.code != 0 and not case.posted()
                  and not case.reviewer_processes_alive()
                  and not case.reviewer_worktree_left(), case.detail)

        case = Case(scratch).run("leave-child")
        time.sleep(0.2)
        check("a process the reviewer leaves running after it exits normally is killed",
              lambda: case.code == 0
              and not running(int((case.state / "child.pid").read_text())), case.detail)

        case = Case(scratch).interrupt(signal.SIGTERM, "valid", "gh-post-started",
                                       FAKE_GH_HANGS="post")
        time.sleep(0.2)
        check("SIGTERM during the posting step says the review may or may not have been posted, "
              "gives the command that shows it, removes the reviewer's worktree and exits nonzero",
              lambda: case.code != 0
              and "the posting step was interrupted, so the review in" in case.stdout
              and "may or may not have been posted" in case.stdout
              and "gh api --paginate 'repos/nedschorus/nedschorus/pulls/7/reviews' --jq "
                  "'.[] | select(.user.login == \"mac-claude\" and .commit_id == "
                  f"\"{case.head}\") | [.id, .state, .html_url] | @tsv'" in case.stdout
              and not case.reviewer_worktree_left(), case.detail)
        check("SIGTERM during the posting step kills the posting script's gh, so it cannot post "
              "after the message",
              lambda: not running(int((case.state / "gh-post-started").read_text())),
              case.detail)

        case = Case(scratch).run("valid", FAKE_GH_FAILS="post")
        check("a failed post exits 1 and passes the posting script's message through",
              lambda: case.code == 1 and "review may or may not be posted" in case.stdout
              and "the posting script exited 2" in case.stdout, case.detail)

        case = Case(scratch)
        (case.helpers / "briefs" / "brief-7a-mac-claude.md").unlink()
        case.run("valid")
        check("a missing brief refuses with exit 2 before the reviewer runs",
              lambda: case.code == 2 and not case.claude_calls
              and "PR 7: Claude review not run: could not read" in case.stdout, case.detail)
        case = Case(scratch).run("valid", tag="7b")
        check("a tag with no brief refuses with exit 2",
              lambda: case.code == 2 and not case.claude_calls, case.detail)
        case = Case(scratch)
        case.run("valid", head="0" * 40)
        check("a head worktree not at the head commit refuses with exit 2 before the reviewer runs",
              lambda: case.code == 2 and not case.claude_calls
              and "is not at the head commit" in case.stdout, case.detail)

        def schema_matches_the_step():
            schema = json.loads(SCHEMA.read_text())
            return (schema["properties"]["verdict"]["enum"] == ["APPROVE", "REQUEST_CHANGES",
                                                                "COULD_NOT_REVIEW"]
                    and schema["required"] == ["verdict", "body", "comments", "note"]
                    and schema["properties"]["note"] == {"type": "string"}
                    and schema["properties"]["comments"]["items"]["required"]
                    == ["path", "line", "body"])
        check("the schema file's verdicts and fields are the ones the step checks",
              schema_matches_the_step)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    if failures:
        print(f"\n{len(failures)} case(s) failed")
        return 1
    print("\nall cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
