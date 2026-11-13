#!/usr/bin/env python3
"""Tests for nc-systems/general-tools/agent-seat-owned-nc-topic-branches-push-and-draft-pull-request-open-stop-hook.py.

Each test runs the hook as Claude Code does, as a program reading the Stop payload on stdin, in a
real clone of a bare origin made in a temporary directory, with a fake `gh` first on PATH that
records its calls and answers as the test sets.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK = REPO_ROOT / "nc-systems" / "general-tools" / "agent-seat-owned-nc-topic-branches-push-and-draft-pull-request-open-stop-hook.py"
SEAT = "test-seat"

_specification = importlib.util.spec_from_file_location(
    "worktree_owner_file_read_and_write", REPO_ROOT / "scripts" / "worktree-owner-file-read-and-write.py")
worktree_owner_file = importlib.util.module_from_spec(_specification)
_specification.loader.exec_module(worktree_owner_file)

FAKE_GH = """#!/usr/bin/env python3
import json, os, sys
with open(os.environ["FAKE_GH_CALLS"], "a") as calls:
    calls.write(json.dumps(sys.argv[1:]) + "\\n")
kind = sys.argv[2] if len(sys.argv) > 2 else ""
sys.stdout.write(os.environ.get("FAKE_GH_" + kind.upper() + "_STDOUT", ""))
sys.stderr.write(os.environ.get("FAKE_GH_" + kind.upper() + "_STDERR", ""))
sys.exit(int(os.environ.get("FAKE_GH_" + kind.upper() + "_STATUS", "0")))
"""


# The tests' git runs with this identity and no global or system configuration, whatever the
# machine running them has.
GIT_ENVIRONMENT = {
    "GIT_AUTHOR_NAME": SEAT, "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": SEAT, "GIT_COMMITTER_EMAIL": "t@example.invalid",
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def git(directory, *arguments):
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    return subprocess.run(["git", *arguments], cwd=directory, check=True, capture_output=True,
                          text=True, env={**environment, **GIT_ENVIRONMENT}).stdout.strip()


class StopHookTest(unittest.TestCase):

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="turn-end-push-test-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.origin = self.root / "origin.git"
        git(self.root, "init", "--quiet", "--bare", "--initial-branch=main", str(self.origin))
        self.clone = self.root / "clone"
        git(self.root, "clone", "--quiet", str(self.origin), str(self.clone))
        git(self.clone, "commit", "--quiet", "--allow-empty", "-m", "first")
        git(self.clone, "push", "--quiet", "origin", "main")
        fake_bin = self.root / "bin"
        fake_bin.mkdir()
        (fake_bin / "gh").write_text(FAKE_GH)
        (fake_bin / "gh").chmod(0o755)
        self.calls = self.root / "gh-calls"
        self.calls.write_text("")
        self.environment = environment = {
            key: value for key, value in os.environ.items()
            if not key.startswith(("GIT_", "FAKE_GH_", "NEDSCHORUS_", "CLAUDE_CODE_SESSION_ATTENDED",
                                   "CLAUDE_PROJECT_DIR"))}
        environment.update({
            "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
            "FAKE_GH_CALLS": str(self.calls),
            "FAKE_GH_LIST_STDOUT": "[]", "CLAUDE_PROJECT_DIR": str(self.clone), **GIT_ENVIRONMENT})

    def worktree(self, branch, owner_seat=SEAT, commit=True):
        path = self.root / branch
        git(self.clone, "worktree", "add", "--quiet", "-b", branch, str(path), "origin/main")
        if commit:
            git(path, "commit", "--quiet", "--allow-empty", "-m", f"work on {branch}")
        if owner_seat:
            worktree_owner_file.worktree_owner_file_write(path, "agent-seat", owner_seat)
        return path

    def run_hook(self, payload=None, stdin_text=None, **environment_changes):
        environment = dict(self.environment)
        for key, value in environment_changes.items():
            if value is None:
                environment.pop(key, None)
            else:
                environment[key] = value
        if stdin_text is None:
            stdin_text = json.dumps({"cwd": str(self.root), "stop_hook_active": False, **(payload or {})})
        return subprocess.run([sys.executable, str(HOOK)], input=stdin_text, capture_output=True,
                              text=True, env=environment, cwd=self.clone)

    def on_origin(self, branch):
        return subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
                              cwd=self.origin, capture_output=True, env=self.environment).returncode == 0

    def gh_calls(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()]

    def created(self):
        return [call for call in self.gh_calls() if call[:2] == ["pr", "create"]]

    def context(self, result):
        return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]

    def test_branch_with_no_pull_request_is_pushed_and_gets_a_draft_with_no_defect_line(self):
        self.worktree("topic-a")
        result = self.run_hook()
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))
        self.assertTrue(self.on_origin("topic-a"))
        [create] = self.created()
        self.assertIn("--draft", create)
        self.assertEqual(create[create.index("--head") + 1], "topic-a")
        self.assertEqual(create[create.index("--title") + 1], "work on topic-a")
        body = create[create.index("--body") + 1]
        self.assertFalse([line for line in body.splitlines() if line.lstrip("-* ").startswith("#")])

    def test_branch_with_an_open_draft_is_pushed_and_gets_no_second_pull_request(self):
        self.worktree("topic-a")
        result = self.run_hook(FAKE_GH_LIST_STDOUT='[{"number": 5, "isDraft": true}]')
        self.assertEqual(result.returncode, 0)
        self.assertTrue(self.on_origin("topic-a"))
        self.assertEqual(self.created(), [])

    def test_branch_whose_pull_request_is_ready_is_not_pushed(self):
        self.worktree("topic-a")
        self.run_hook(FAKE_GH_LIST_STDOUT='[{"number": 5, "isDraft": false}]')
        self.assertFalse(self.on_origin("topic-a"))
        self.assertEqual(self.created(), [])

    def test_ready_query_asks_for_the_branch_open_pull_requests_only(self):
        self.worktree("topic-a")
        self.run_hook()
        [listing] = [call for call in self.gh_calls() if call[:2] == ["pr", "list"]]
        self.assertEqual(listing[listing.index("--head") + 1], "topic-a")
        self.assertEqual(listing[listing.index("--state") + 1], "open")

    def test_other_seats_unowned_main_detached_and_unchanged_worktrees_are_left_alone(self):
        self.worktree("other-seats", owner_seat="another-seat")
        self.worktree("no-owner-file", owner_seat=None)
        self.worktree("nothing-new", commit=False)
        git(self.clone, "worktree", "add", "--quiet", "--detach", str(self.root / "detached"), "origin/main")
        git(self.clone, "switch", "--quiet", "--detach")
        main_worktree = self.root / "main-worktree"
        git(self.clone, "worktree", "add", "--quiet", str(main_worktree), "main")
        git(main_worktree, "commit", "--quiet", "--allow-empty", "-m", "on main")
        worktree_owner_file.worktree_owner_file_write(main_worktree, "agent-seat", SEAT)
        gone = self.worktree("prunable")
        shutil.rmtree(gone)
        result = self.run_hook()
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))
        self.assertEqual(self.gh_calls(), [])
        self.assertEqual(git(self.origin, "for-each-ref", "--format=%(refname)"), "refs/heads/main")
        self.assertNotEqual(git(self.origin, "rev-parse", "main"), git(main_worktree, "rev-parse", "HEAD"))

    def test_subagent_worktree_owned_by_an_agent_session_of_this_seat_is_pushed(self):
        path = self.root / "subagent"
        git(self.clone, "worktree", "add", "--quiet", "-b", "subagent", str(path), "origin/main")
        git(path, "commit", "--quiet", "--allow-empty", "-m", "subagent work")
        worktree_owner_file.worktree_owner_file_write(path, "agent-session", SEAT, "boot:1:2")
        self.run_hook()
        self.assertTrue(self.on_origin("subagent"))

    def test_nothing_runs_without_an_agent_seat_or_in_a_session_no_user_attends(self):
        self.worktree("topic-a")
        for changes in ({"GIT_AUTHOR_NAME": None}, {"CLAUDE_CODE_SESSION_ATTENDED": "0"},
                        {"NEDSCHORUS_SESSION_REINCARNATION_OWNED_BY_CALLER": "1"}):
            with self.subTest(changes=changes):
                result = self.run_hook(**changes)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))
        self.assertFalse(self.on_origin("topic-a"))
        self.assertEqual(self.gh_calls(), [])

    def test_failed_question_to_github_pushes_nothing_and_is_reported(self):
        self.worktree("topic-a")
        for changes, quoted in (({"FAKE_GH_LIST_STATUS": "1", "FAKE_GH_LIST_STDERR": "HTTP 502"}, "HTTP 502"),
                                ({"FAKE_GH_LIST_STDOUT": "not json"}, "not json")):
            with self.subTest(changes=changes):
                result = self.run_hook(**changes)
                self.assertEqual(result.returncode, 0)
                context = self.context(result)
                self.assertIn("branch topic-a: GitHub could not be asked", context)
                self.assertIn(quoted, context)
        self.assertFalse(self.on_origin("topic-a"))
        self.assertEqual(self.created(), [])

    def test_push_the_pre_push_hook_refuses_is_reported_with_its_message_and_opens_no_draft(self):
        self.worktree("topic-a")
        hooks = self.root / "hooks"
        hooks.mkdir()
        (hooks / "pre-push").write_text("#!/bin/sh\necho 'pre-push: REFUSED: conflicts with main' >&2\nexit 1\n")
        (hooks / "pre-push").chmod(0o755)
        git(self.clone, "config", "core.hooksPath", str(hooks))
        context = self.context(self.run_hook())
        self.assertIn("branch topic-a: `git push origin topic-a`", context)
        self.assertIn("pre-push: REFUSED: conflicts with main", context)
        self.assertFalse(self.on_origin("topic-a"))
        self.assertEqual(self.created(), [])

    def test_draft_that_fails_to_open_after_the_push_is_reported_with_the_command_to_run(self):
        self.worktree("topic-a")
        context = self.context(self.run_hook(FAKE_GH_CREATE_STATUS="1", FAKE_GH_CREATE_STDERR="rate limited"))
        self.assertTrue(self.on_origin("topic-a"))
        self.assertIn("branch topic-a: pushed, but its draft pull request could not be opened", context)
        self.assertIn("rate limited", context)
        self.assertIn("gh pr create --draft --base main --head topic-a", context)

    def test_unreadable_owner_file_is_reported_and_its_branch_not_pushed(self):
        path = self.worktree("topic-a", owner_seat=None)
        worktree_owner_file.worktree_owner_file_path_find(path).write_text("not json")
        context = self.context(self.run_hook())
        self.assertIn("branch topic-a: the owner file of worktree", context)
        self.assertFalse(self.on_origin("topic-a"))

    def test_failed_rev_list_is_reported(self):
        path = self.worktree("topic-a")
        git(path, "update-ref", "-d", "refs/heads/topic-a")
        context = self.context(self.run_hook())
        self.assertIn("branch topic-a: `git rev-list` failed", context)

    def test_stop_ending_the_answer_to_a_stop_hook_pushes_nothing_and_says_nothing(self):
        self.worktree("topic-a")
        result = self.run_hook({"stop_hook_active": True}, FAKE_GH_LIST_STATUS="1")
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))
        self.assertFalse(self.on_origin("topic-a"))
        self.assertEqual(self.gh_calls(), [])

    def test_payload_that_is_not_a_json_object_is_one_stderr_line_with_exit_1(self):
        for stdin_text in ("not json", "[]"):
            with self.subTest(stdin_text=stdin_text):
                result = self.run_hook(stdin_text=stdin_text)
                self.assertEqual((result.returncode, result.stdout), (1, ""))
                self.assertIn("no branch was pushed", result.stderr)

    def test_failed_worktree_listing_is_one_stderr_line_with_exit_1(self):
        not_a_clone = self.root / "not-a-clone"
        not_a_clone.mkdir()
        result = self.run_hook(CLAUDE_PROJECT_DIR=str(not_a_clone))
        self.assertEqual((result.returncode, result.stdout), (1, ""))
        self.assertIn("`git worktree list` failed", result.stderr)


if __name__ == "__main__":
    unittest.main()
