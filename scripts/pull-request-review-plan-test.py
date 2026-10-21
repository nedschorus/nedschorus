#!/usr/bin/env python3
"""Check review tiers, fix rounds, agent text, GitHub reads and brief skeletons.

Real git commits and merges live only in a TemporaryDirectory. A stand-in gh
answers each of the four read shapes from JSON control files and logs argv;
no case reaches GitHub or runs git against the checkout holding this suite.
Subprocess cases exercise the command line and JSON/text contracts. Imported
unit cases check fences, normalized syntax trees and diff hunk line ranges.

Run: python3 scripts/pull-request-review-plan-test.py
Prints one line per case and exits non-zero if any case fails.
"""

import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Importing these files must not create files in the real checkout either.
sys.dont_write_bytecode = True
_removal_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    Path(__file__).with_name("git-redirecting-environment-removal-test-fixture.py"))
_removal_module = importlib.util.module_from_spec(_removal_spec)
_removal_spec.loader.exec_module(_removal_module)
_removal_module.remove_git_redirecting_environment_variables_from_this_process()

REVIEW_PLAN_SCRIPT = Path(__file__).resolve().with_name("pull-request-review-plan.py")
CONTROL_DIRECTORY_VARIABLE = "PULL_REQUEST_REVIEW_PLAN_TEST_CONTROL_DIRECTORY"
FIXTURE_PULL_REQUEST_NUMBER = 852
FIXTURE_GITHUB_REPOSITORY = "fixture-owner/fixture-repository"
CHECK_FAILURE_NAMES = []

_review_plan_spec = importlib.util.spec_from_file_location("pull_request_review_plan", REVIEW_PLAN_SCRIPT)
review_plan_module = importlib.util.module_from_spec(_review_plan_spec)
_review_plan_spec.loader.exec_module(review_plan_module)

STAND_IN_GITHUB_SOURCE = f'''#!/usr/bin/env python3
import json
import os
import pathlib
import sys
control_directory = pathlib.Path(os.environ[{CONTROL_DIRECTORY_VARIABLE!r}])
arguments = sys.argv[1:]
with (control_directory / "calls.jsonl").open("a", encoding="utf-8") as call_log:
    call_log.write(json.dumps(arguments) + "\\n")
if arguments[:2] == ["pr", "view"]:
    control_name = "pull-request.json"
elif arguments[:3] == ["api", "--paginate", "--slurp"] and arguments[-1].endswith("/reviews"):
    control_name = "reviews.json"
elif arguments[:3] == ["api", "--paginate", "--slurp"] and arguments[-1].endswith("/comments"):
    control_name = "comments.json"
elif len(arguments) == 2 and arguments[0] == "api" and "/branches/" in arguments[1]:
    control_name = "branch.json"
else:
    sys.stderr.write("unexpected gh call shape\\n")
    sys.exit(91)
response = json.loads((control_directory / control_name).read_text(encoding="utf-8"))
sys.stdout.write(response["stdout"])
sys.stderr.write(response.get("stderr", ""))
sys.exit(response.get("exit_code", 0))
'''

FAILING_GIT_ARGUMENTS_VARIABLE = "PULL_REQUEST_REVIEW_PLAN_TEST_FAILING_GIT_ARGUMENTS"
REAL_GIT_VARIABLE = "PULL_REQUEST_REVIEW_PLAN_TEST_REAL_GIT"
# Fails as a broken repository does when the git arguments after -C begin with
# the listed ones, and runs the real git for every other call.
STAND_IN_FAILING_GIT_SOURCE = f'''#!/usr/bin/env python3
import json
import os
import sys
failing = json.loads(os.environ[{FAILING_GIT_ARGUMENTS_VARIABLE!r}])
if sys.argv[1] == "-C" and sys.argv[3:3 + len(failing)] == failing:
    sys.stderr.write("fatal: injected repository failure\\n")
    sys.exit(128)
os.execv(os.environ[{REAL_GIT_VARIABLE!r}], ["git", *sys.argv[1:]])
'''

BASELINE_FILE_CONTENTS = {
    "docs/review-note.md": "A prose heading\n\nOld prose.\n\n```python\nprint('old')\n```\n",
    "operative-note.md": "Old prose outside docs.\n",
    "scripts/example-program.py": '"""Old module documentation."""\n# Old comment\nVALUE = "old"\n\ndef show_value():\n    """Old function documentation."""\n    print(VALUE)\n    return 1\n',
    "scripts/example-program-test.py": 'EXPECTED = "old"\nassert EXPECTED\n',
    ".claude/hooks/example-hook.py": 'print("old")\n',
    ".claude/hooks/example-hook-test.py": 'print("old")\n',
    "scripts/synthetic-keystroke-guard-hook.py": 'print("old")\n',
    "scripts/registered-example-hook.py": 'print("old")\n',
    ".claude/settings.json": json.dumps({"hooks": {"PreToolUse": [{"hooks": [
        {"command": 'python3 "$CLAUDE_PROJECT_DIR"/scripts/registered-example-hook.py'}]}]}}) + "\n",
    "scripts/sibling-program.py": 'print("old")\n',
    "scripts/sibling-program-test.py": 'assert True\n',
    "scripts/nested-program.py": 'print("old")\n',
    "scripts/tests/nested-program-test.py": 'assert True\n',
    "nc-systems/example/parent-program.py": 'print("old")\n',
    "nc-systems/tests/parent-program-test.py": 'assert True\n',
    "scripts/agent-messages.py": '"""Old help.\nHelp details.\n"""\nimport sys\nHELP_TEXT = __doc__\nCHECK_ADVICE = "Old advice ``` marker"\n\ndef show_message(name):\n    print(f"Old message for {name}", "unchanged", file=sys.stderr)\n    raise ValueError("Old failure")\n',
    "scripts/agent-messages-test.py": 'print("Old test message")\n',
    "docs/plain-note.txt": "Old note.\n",
    "conflicting-example.txt": "base\n",
}


def check(name, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f": {detail}" if not condition else ""))
    if not condition:
        CHECK_FAILURE_NAMES.append(name)


class ReviewPlanTemporaryRepositoryFixture:
    """One disposable repository, reset to its baseline between independent cases."""

    def __init__(self, temporary_directory):
        self.repository = temporary_directory / "repository"
        self.repository.mkdir()
        self.control_directory = temporary_directory / "github-control"
        self.control_directory.mkdir()
        self.binary_directory = temporary_directory / "bin"
        self.binary_directory.mkdir()
        # A space, an apostrophe, a dollar sign, a backtick and a double quote in the name: each printed
        # command must shell-quote its target, and double quotes would leave $, ` and " live.
        self.message_target_temporary_directory = temporary_directory / "message target temporary directory's $HOME `id` \"q\""
        self.message_target_temporary_directory.mkdir()
        stand_in_path = self.binary_directory / "gh"
        stand_in_path.write_text(STAND_IN_GITHUB_SOURCE, encoding="utf-8")
        stand_in_path.chmod(0o755)
        self.environment = {**os.environ,
                            "PATH": str(self.binary_directory) + os.pathsep + os.environ["PATH"],
                            CONTROL_DIRECTORY_VARIABLE: str(self.control_directory),
                            "TMPDIR": str(self.message_target_temporary_directory),
                            "PYTHONDONTWRITEBYTECODE": "1"}
        self.git_command("init", "-q", "-b", "main")
        for path, content in BASELINE_FILE_CONTENTS.items():
            self.write_fixture_file(path, content)
        self.base_head = self.commit_fixture_changes("baseline")
        self.git_command("update-ref", "refs/remotes/origin/main", self.base_head)
        self.configure_github_answers(self.base_head)

    def git_command(self, *arguments, expected_exit=0):
        result = subprocess.run(
            ["git", "-C", str(self.repository), "-c", "user.name=Review plan fixture",
             "-c", "user.email=review-plan@nedschorus.invalid", "-c", "core.hooksPath=/dev/null", *arguments],
            env=self.environment, capture_output=True, text=True, timeout=10)
        if result.returncode != expected_exit:
            raise AssertionError(f"fixture git {arguments} exited {result.returncode}: {result.stderr}\n{result.stdout}")
        return result.stdout.strip()

    def write_fixture_file(self, path, content):
        destination = self.repository / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")

    def commit_fixture_changes(self, message):
        self.git_command("add", "-A")
        self.git_command("commit", "-q", "-m", message)
        return self.git_command("rev-parse", "HEAD")

    def reset_fixture_to_base(self):
        self.git_command("checkout", "-q", "--detach", self.base_head)
        self.git_command("reset", "--hard", self.base_head)
        self.git_command("clean", "-fdq")
        self.git_command("update-ref", "refs/remotes/origin/main", self.base_head)
        self.configure_github_answers(self.base_head)

    def set_github_response(self, control_name, payload=None, *, stdout=None, exit_code=0, stderr=""):
        response = {"stdout": json.dumps(payload) if stdout is None else stdout,
                    "exit_code": exit_code, "stderr": stderr}
        (self.control_directory / control_name).write_text(json.dumps(response), encoding="utf-8")

    def configure_github_answers(self, head, *, author="someone-else", reviews=None, comments=None,
                                 live_base=None, state="OPEN", merge_commit=None, base_branch="main"):
        self.set_github_response("pull-request.json", {
            "number": FIXTURE_PULL_REQUEST_NUMBER, "title": "Compute a review plan",
            "url": "https://github.com/fixture-owner/fixture-repository/pull/852",
            "state": state, "author": {"login": author}, "headRefOid": head,
            "baseRefName": base_branch, "mergeCommit": {"oid": merge_commit} if merge_commit else None})
        self.set_github_response("reviews.json", reviews if reviews is not None else [[]])
        self.set_github_response("comments.json", comments if comments is not None else [[]])
        self.set_github_response("branch.json", {"commit": {"sha": live_base or self.base_head}})

    def run_review_plan(self, *extra_arguments, json_output=True, environment=None):
        return subprocess.run(
            [sys.executable, str(REVIEW_PLAN_SCRIPT), "--pull-request", str(FIXTURE_PULL_REQUEST_NUMBER),
             "--repository", str(self.repository), "--github-repository", FIXTURE_GITHUB_REPOSITORY,
             *(["--json"] if json_output else []), *extra_arguments],
            env=environment or self.environment, capture_output=True, text=True, timeout=10)

    def run_review_plan_with_git_failing_on(self, *failing_arguments):
        stand_in_directory = self.repository.parent / "failing-git-bin"
        stand_in_directory.mkdir(exist_ok=True)
        stand_in_path = stand_in_directory / "git"
        stand_in_path.write_text(STAND_IN_FAILING_GIT_SOURCE, encoding="utf-8")
        stand_in_path.chmod(0o755)
        return self.run_review_plan(environment={
            **self.environment, "PATH": str(stand_in_directory) + os.pathsep + self.environment["PATH"],
            FAILING_GIT_ARGUMENTS_VARIABLE: json.dumps(list(failing_arguments)),
            REAL_GIT_VARIABLE: shutil.which("git", path=self.environment["PATH"])})

    def read_review_plan(self):
        result = self.run_review_plan()
        if result.returncode:
            raise AssertionError(f"review plan exited {result.returncode}: {result.stderr}")
        return json.loads(result.stdout)

    def plan_for_changed_file(self, path, content):
        self.reset_fixture_to_base()
        self.write_fixture_file(path, content)
        head = self.commit_fixture_changes("change " + path)
        self.configure_github_answers(head)
        return self.read_review_plan()


def fixture_review(review_id, head, *, state="COMMENTED", submitted_at="2026-01-01T00:00:00Z"):
    return {"id": review_id, "node_id": f"REVIEW_node_{review_id}", "user": {"login": "fixture-reviewer"},
            "state": state, "commit_id": head, "submitted_at": submitted_at}


def refusal_has_expected_prefix(result):
    return result.returncode == 1 and result.stderr.startswith("pull-request-review-plan: ")


def run_unit_cases():
    fence_source = "prose\n  ````python\nvalue\n```\n~~~~\n ```` \nend\n~~~sh\nlast\n"
    check("fence detection includes openers, closers and unclosed blocks",
          review_plan_module.fenced_code_block_line_numbers_in_markdown(fence_source) == {2, 3, 4, 5, 6, 8, 9})
    check("fence detection distinguishes tildes from backticks",
          review_plan_module.fenced_code_block_line_numbers_in_markdown("~~~\n```\n~~~~\nprose\n") == {1, 2, 3})
    old_source = '"""module old"""\nclass Example:\n    """class old"""\n    async def show(self, x):\n        """function old"""\n        return f"old {x}"\n'
    new_source = old_source.replace("old", "new") + "# a comment\n"
    check("normalized AST ignores docstrings, comments and f-string constant parts",
          review_plan_module.normalized_syntax_tree_dump_without_strings(old_source)
          == review_plan_module.normalized_syntax_tree_dump_without_strings(new_source))
    check("normalized AST preserves behaviour and f-string expressions",
          review_plan_module.normalized_syntax_tree_dump_without_strings(old_source)
          != review_plan_module.normalized_syntax_tree_dump_without_strings(old_source.replace("{x}", "{x + 1}")))
    check("hunk parser handles omitted counts and zero-line sides",
          review_plan_module.parse_diff_hunk_line_ranges("@@ -1 +2 @@\n-x\n+y\n@@ -3,0 +4,2 @@ context\n@@ -9,3 +8,0 @@\n")
          == [(1, 1, 2, 1), (3, 0, 4, 2), (9, 3, 8, 0)])


def run_classification_cases(fixture):
    plan = fixture.plan_for_changed_file("docs/review-note.md", BASELINE_FILE_CONTENTS["docs/review-note.md"].replace("Old prose", "New prose"))
    check("Markdown prose only gets no-reviewer-tier", plan["tier"] == "no-reviewer-tier" and plan["changed_files"][0]["class"] == "prose", plan)
    check("no reviews gives round one", plan["round"] == 1 and not plan["fix_round"] and plan["delta_only_review_applies"] is None, plan)
    check("clean merged tree is a 40-hex tree", bool(re.fullmatch(r"[0-9a-f]{40}", plan["merged_tree"]["tree"])) and not plan["merged_tree"]["conflicting_paths"], plan)
    plan = fixture.plan_for_changed_file("operative-note.md", "New prose outside docs.\n")
    check("Markdown prose outside docs also gets no-reviewer-tier", plan["tier"] == "no-reviewer-tier", plan)
    plan = fixture.plan_for_changed_file("scripts/example-program-test.py", 'EXPECTED = "new"\nassert EXPECTED\n')
    check("a changed test gets codex-review-and-head-tests-tier", plan["tier"] == "codex-review-and-head-tests-tier" and plan["changed_files"][0]["class"] == "test", plan)
    plan = fixture.plan_for_changed_file("scripts/example-program.py", BASELINE_FILE_CONTENTS["scripts/example-program.py"].replace("Old", "New").replace('"old"', '"new"'))
    check("Python string, docstring and comment changes get codex-review-and-head-tests-tier", plan["tier"] == "codex-review-and-head-tests-tier" and "string constants" in plan["tier_decided_by"], plan)
    plan = fixture.plan_for_changed_file("docs/review-note.md", BASELINE_FILE_CONTENTS["docs/review-note.md"].replace("print('old')", "print('new')"))
    check("fenced Markdown code changes get codex-review-and-head-tests-tier", plan["tier"] == "codex-review-and-head-tests-tier" and "fenced code blocks" in plan["tier_decided_by"], plan)
    full_reviewer_cases = [
        ("Python logic changes get claude-and-codex-review-and-head-tests-tier", "scripts/example-program.py", BASELINE_FILE_CONTENTS["scripts/example-program.py"].replace("return 1", "return 2")),
        ("every hook directory file gets claude-and-codex-review-and-head-tests-tier", ".claude/hooks/example-hook.py", 'print("new")\n'),
        ("settings gets claude-and-codex-review-and-head-tests-tier", ".claude/settings.json", '{"hooks": {}}\n'),
        ("a Bash guard string-only change gets claude-and-codex-review-and-head-tests-tier", "scripts/synthetic-keystroke-guard-hook.py", 'print("new")\n'),
        ("a registered hook string-only change gets claude-and-codex-review-and-head-tests-tier", "scripts/registered-example-hook.py", 'print("new")\n'),
        ("a new Python program gets claude-and-codex-review-and-head-tests-tier", "scripts/new-example-program.py", 'print("new")\n'),
        ("a test under the hook directory gets claude-and-codex-review-and-head-tests-tier", ".claude/hooks/example-hook-test.py", 'print("new")\n'),
    ]
    for case_name, path, content in full_reviewer_cases:
        plan = fixture.plan_for_changed_file(path, content)
        check(case_name, plan["tier"] == "claude-and-codex-review-and-head-tests-tier" and path in plan["tier_decided_by"], plan)
    fixture.reset_fixture_to_base()
    fixture.write_fixture_file("scripts/a-new-program.py", "VALUE = 1\n")
    fixture.write_fixture_file("scripts/registered-example-hook.py", 'print("new")\n')
    head = fixture.commit_fixture_changes("hook priority over path order")
    fixture.configure_github_answers(head)
    plan = fixture.read_review_plan()
    check("always-full hook wins the deciding line before path order", "scripts/registered-example-hook.py" in plan["tier_decided_by"], plan)
    fixture.reset_fixture_to_base()
    fixture.write_fixture_file(".claude/hooks/example-hook.py", 'print("new")\n')
    fixture.write_fixture_file(".claude/hooks/example-hook-test.py", 'print("new")\n')
    head = fixture.commit_fixture_changes("hook program priority over hook test")
    fixture.configure_github_answers(head)
    plan = fixture.read_review_plan()
    check("the deciding line prefers the hook program over its earlier-sorting test",
          plan["tier"] == "claude-and-codex-review-and-head-tests-tier"
          and ".claude/hooks/example-hook.py" in plan["tier_decided_by"]
          and "example-hook-test.py" not in plan["tier_decided_by"], plan)
    plan = fixture.plan_for_changed_file("scripts/example-program.py", "def broken(:\n")
    check("unparseable Python gets claude-and-codex-review-and-head-tests-tier with side named", plan["tier"] == "claude-and-codex-review-and-head-tests-tier" and "does not parse at new side" in plan["tier_decided_by"], plan)
    fixture.reset_fixture_to_base()
    (fixture.repository / "scripts/example-program.py").unlink()
    head = fixture.commit_fixture_changes("delete program")
    fixture.configure_github_answers(head)
    plan = fixture.read_review_plan()
    check("deleted Python gets claude-and-codex-review-and-head-tests-tier", plan["tier"] == "claude-and-codex-review-and-head-tests-tier" and "is deleted" in plan["tier_decided_by"], plan)
    fixture.reset_fixture_to_base()
    fixture.configure_github_answers(fixture.base_head)
    plan = fixture.read_review_plan()
    check("an empty change set gets no-reviewer-tier with explicit reason", plan["tier"] == "no-reviewer-tier" and plan["tier_decided_by"] == "the pull request changes no file", plan)


def run_fix_round_cases(fixture):
    fixture.reset_fixture_to_base()
    fixture.write_fixture_file("scripts/example-program.py", BASELINE_FILE_CONTENTS["scripts/example-program.py"].replace("return 1", "return 2"))
    earlier = fixture.commit_fixture_changes("first reviewed head")
    fixture.write_fixture_file("scripts/example-program.py", (fixture.repository / "scripts/example-program.py").read_text().replace('"old"', '"new"'))
    head = fixture.commit_fixture_changes("message fix")
    reviews = [[fixture_review(101, earlier), fixture_review(102, earlier, state="APPROVED")],
               [fixture_review(103, head, submitted_at="2026-01-02T00:00:00Z"),
                fixture_review(104, "9" * 40, state="PENDING", submitted_at=None)]]
    fixture.configure_github_answers(head, reviews=reviews,
                                     comments=[[{"pull_request_review_id": 101}, {"pull_request_review_id": 101}],
                                               [{"pull_request_review_id": 102}, {"pull_request_review_id": 104}]])
    plan = fixture.read_review_plan()
    check("a string fix gives round two and delta-only codex-review-and-head-tests-tier", plan["round"] == 2 and plan["fix_round"] and plan["delta_tier"] == "codex-review-and-head-tests-tier" and plan["delta_only_review_applies"] and plan["delta_range"] == f"{earlier}..{head}", plan)
    check("inline comments are counted per review across pages", [review["inline_comments"] for review in plan["reviews"]] == [2, 1, 0], plan["reviews"])
    check("pending reviews are ignored and current-head reviews do not raise the round", len(plan["reviews"]) == 3 and plan["round"] == 2 and plan["reviews"][-1]["head_relation"] == "current head", plan)
    fixture.write_fixture_file("scripts/example-program.py", (fixture.repository / "scripts/example-program.py").read_text().replace("return 2", "return 3"))
    logic_head = fixture.commit_fixture_changes("logic fix")
    fixture.configure_github_answers(logic_head, reviews=[[fixture_review(101, earlier)]])
    plan = fixture.read_review_plan()
    check("a program logic delta keeps delta-only review at the claude-and-codex-review-and-head-tests-tier delta tier",
          plan["delta_only_review_applies"] is True and plan["delta_only_review_reasons"] == []
          and [entry["path"] for entry in plan["delta_files"]] == ["scripts/example-program.py"]
          and plan["delta_tier"] == "claude-and-codex-review-and-head-tests-tier"
          and "scripts/example-program.py" in plan["delta_tier_decided_by"], plan)
    fixture.configure_github_answers(logic_head, reviews=[[fixture_review(101, "a" * 40)]])
    plan = fixture.read_review_plan()
    check("an unavailable earlier head voids delta-only review without a delta tier", plan["delta_tier"] is None and not plan["delta_only_review_applies"] and "not in this repository" in plan["delta_only_review_reasons"][0], plan)
    fixture.configure_github_answers(logic_head, reviews=[[fixture_review(102, earlier, submitted_at="2026-01-03T00:00:00Z"),
                                                           fixture_review(101, head), fixture_review(103, logic_head)]])
    plan = fixture.read_review_plan()
    check("rounds count distinct earlier heads and select the latest submitted review", plan["round"] == 3 and plan["earlier_reviewed_head"] == earlier, plan)

    fixture.reset_fixture_to_base()
    fixture.write_fixture_file("scripts/example-program.py", BASELINE_FILE_CONTENTS["scripts/example-program.py"].replace('"old"', '"reviewed"'))
    earlier = fixture.commit_fixture_changes("review before main merge")
    fixture.git_command("checkout", "-q", "--detach", fixture.base_head)
    fixture.write_fixture_file("scripts/unrelated-main-program.py", 'MAIN_VALUE = 1\nprint("main-only message")\n')
    main_head = fixture.commit_fixture_changes("unrelated main change")
    fixture.git_command("update-ref", "refs/remotes/origin/main", main_head)
    fixture.git_command("checkout", "-q", "--detach", earlier)
    fixture.git_command("merge", "-q", "--no-ff", "-m", "merge main", main_head)
    merge_head = fixture.git_command("rev-parse", "HEAD")
    fixture.write_fixture_file("scripts/example-program.py", (fixture.repository / "scripts/example-program.py").read_text().replace('"reviewed"', '"fixed"'))
    head = fixture.commit_fixture_changes("fix after main merge")
    fixture.configure_github_answers(head, reviews=[[fixture_review(101, earlier)]], live_base=main_head)
    plan = fixture.read_review_plan()
    check("a main merge voids delta-only review and names its short hash", not plan["delta_only_review_applies"] and any(merge_head[:12] in reason for reason in plan["delta_only_review_reasons"]), plan)
    check("a main merge restricts delta files to the pull request's own files", plan["delta_files_restricted_to_pull_request_files"] and [entry["path"] for entry in plan["delta_files"]] == ["scripts/example-program.py"] and plan["delta_tier"] == "codex-review-and-head-tests-tier", plan)
    check("a main merge excludes main-only files and messages from delta agent-facing text",
          not any(entry["path"] == "scripts/unrelated-main-program.py"
                  or "main-only message" in (entry["old_text"] or "")
                  or "main-only message" in (entry["new_text"] or "")
                  for entry in plan["agent_facing_text_delta"]), plan["agent_facing_text_delta"])
    skeleton_result = fixture.run_review_plan("--brief-skeleton", str(fixture.control_directory / "fix-round-brief.md"))
    skeleton_text = (fixture.control_directory / "fix-round-brief.md").read_text()
    check("a fix round brief includes delta tier, restrictions and every verdict reason", skeleton_result.returncode == 0 and "delta tier: codex-review-and-head-tests-tier" in skeleton_text and "files restricted" in skeleton_text and merge_head[:12] in skeleton_text, skeleton_text)

    fixture.reset_fixture_to_base()
    fixture.write_fixture_file("docs/main-side-note.txt", "Main side history.\n")
    main_side_line_head = fixture.commit_fixture_changes("main side line before main merge")
    fixture.git_command("checkout", "-q", "--detach", fixture.base_head)
    fixture.write_fixture_file("docs/plain-note.txt", "Main first-parent history.\n")
    fixture.commit_fixture_changes("main first parent before main merge")
    fixture.git_command("merge", "-q", "--no-ff", "-m", "main merges side line", main_side_line_head)
    main_merge_commit_head = fixture.git_command("rev-parse", "HEAD")
    fixture.git_command("update-ref", "refs/remotes/origin/main", main_merge_commit_head)
    fixture.git_command("checkout", "-q", "--detach", fixture.base_head)
    fixture.write_fixture_file("scripts/example-program.py", BASELINE_FILE_CONTENTS["scripts/example-program.py"].replace('"old"', '"reviewed"'))
    branch_reviewed_commit_head = fixture.commit_fixture_changes("reviewed branch before main with merge history")
    fixture.git_command("merge", "-q", "--no-ff", "-m", "branch merges main with merge history", main_merge_commit_head)
    branch_merge_commit_head = fixture.git_command("rev-parse", "HEAD")
    fixture.write_fixture_file("scripts/example-program.py", (fixture.repository / "scripts/example-program.py").read_text().replace('"reviewed"', '"fixed"'))
    branch_fixed_commit_head = fixture.commit_fixture_changes("string fix after branch merges main")
    fixture.configure_github_answers(branch_fixed_commit_head,
                                     reviews=[[fixture_review(101, branch_reviewed_commit_head)]],
                                     live_base=main_merge_commit_head)
    plan = fixture.read_review_plan()
    expected_merge_commit_reason = "the delta holds merge commit(s): " + branch_merge_commit_head[:12]
    check("delta merge reasons name only the branch merge and exclude main's own merge",
          plan["delta_only_review_reasons"] == [expected_merge_commit_reason]
          and main_merge_commit_head[:12] not in plan["delta_only_review_reasons"][0], plan)

    fixture.reset_fixture_to_base()
    fixture.write_fixture_file("scripts/example-program.py", BASELINE_FILE_CONTENTS["scripts/example-program.py"].replace('"old"', '"earlier"'))
    earlier = fixture.commit_fixture_changes("old branch history")
    fixture.git_command("checkout", "-q", "--detach", fixture.base_head)
    fixture.write_fixture_file("scripts/example-program.py", BASELINE_FILE_CONTENTS["scripts/example-program.py"].replace('"old"', '"rewritten"'))
    head = fixture.commit_fixture_changes("rewritten branch history")
    fixture.configure_github_answers(head, reviews=[[fixture_review(101, earlier)]])
    plan = fixture.read_review_plan()
    check("rewritten history voids delta-only review", not plan["delta_only_review_applies"] and "the branch's history was rewritten" in plan["delta_only_review_reasons"], plan)
    check("rewritten history also restricts the delta's files", plan["delta_files_restricted_to_pull_request_files"], plan)


def run_hook_registration_and_delta_boundary_cases(fixture):
    fixture.reset_fixture_to_base()
    fixture.write_fixture_file(".claude/settings.json", '{"hooks": {}}\n')
    fixture.write_fixture_file("scripts/registered-example-hook.py", 'print("branch message")\n')
    branch_removed_hook_head = fixture.commit_fixture_changes("branch removes registration and changes hook string")
    fixture.git_command("checkout", "-q", "--detach", fixture.base_head)
    fixture.write_fixture_file(".claude/settings.json", '{"hooks": {}}\n')
    main_removed_hook_head = fixture.commit_fixture_changes("main removes hook registration")
    fixture.git_command("update-ref", "refs/remotes/origin/main", main_removed_hook_head)
    fixture.configure_github_answers(branch_removed_hook_head, live_base=main_removed_hook_head)
    plan = fixture.read_review_plan()
    merge_base_hook_entry = next(entry for entry in plan["changed_files"]
                                if entry["path"] == "scripts/registered-example-hook.py")
    check("a registration present only at the merge base keeps the program a claude-and-codex-review-and-head-tests-tier hook",
          merge_base_hook_entry["class"] == "hook" and merge_base_hook_entry["tier"] == "claude-and-codex-review-and-head-tests-tier", plan)

    fixture.reset_fixture_to_base()
    fixture.write_fixture_file("scripts/sibling-program.py", 'print("branch message")\n')
    head = fixture.commit_fixture_changes("branch before main hook registration")
    fixture.git_command("checkout", "-q", "--detach", fixture.base_head)
    sibling_hook_settings = json.dumps({"hooks": {"PreToolUse": [{"hooks": [
        {"command": "python3 $CLAUDE_PROJECT_DIR/scripts/sibling-program.py"}]}]}}) + "\n"
    fixture.write_fixture_file(".claude/settings.json", sibling_hook_settings)
    main_head = fixture.commit_fixture_changes("main registers branch program as hook")
    fixture.git_command("update-ref", "refs/remotes/origin/main", main_head)
    fixture.configure_github_answers(head, live_base=main_head)
    plan = fixture.read_review_plan()
    check("whole PR hook registrations come from the diff base rather than the merge base",
          plan["tier"] == "claude-and-codex-review-and-head-tests-tier" and plan["changed_files"][0]["class"] == "hook"
          and plan["merge_base"] != main_head, plan)

    fixture.reset_fixture_to_base()
    fixture.write_fixture_file("scripts/sibling-program.py", 'print("reviewed message")\n')
    delta_hook_earlier_head = fixture.commit_fixture_changes("reviewed head before main hook registration")
    fixture.write_fixture_file("scripts/sibling-program.py", 'print("fixed message")\n')
    delta_hook_changed_head = fixture.commit_fixture_changes("string fix before main hook registration")
    fixture.git_command("checkout", "-q", "--detach", fixture.base_head)
    fixture.write_fixture_file(".claude/settings.json", sibling_hook_settings)
    delta_hook_main_head = fixture.commit_fixture_changes("main registers program after branch was cut")
    fixture.git_command("update-ref", "refs/remotes/origin/main", delta_hook_main_head)
    fixture.configure_github_answers(delta_hook_changed_head,
                                     reviews=[[fixture_review(101, delta_hook_earlier_head)]],
                                     live_base=delta_hook_main_head)
    plan = fixture.read_review_plan()
    delta_hook_program_entry = next(entry for entry in plan["delta_files"]
                                   if entry["path"] == "scripts/sibling-program.py")
    check("delta hook registrations include the diff base when main registers the program after the branch was cut",
          delta_hook_program_entry["class"] == "hook" and delta_hook_program_entry["tier"] == "claude-and-codex-review-and-head-tests-tier"
          and plan["delta_tier"] == "claude-and-codex-review-and-head-tests-tier" and plan["delta_only_review_applies"] is True, plan)

    fixture.reset_fixture_to_base()
    fixture.write_fixture_file(".claude/settings.json", sibling_hook_settings)
    earlier = fixture.commit_fixture_changes("earlier round registers hook")
    fixture.write_fixture_file(".claude/settings.json", BASELINE_FILE_CONTENTS[".claude/settings.json"])
    fixture.write_fixture_file("scripts/sibling-program.py", 'print("changed after registration")\n')
    head = fixture.commit_fixture_changes("remove registration and change old hook")
    fixture.configure_github_answers(head, reviews=[[fixture_review(101, earlier)]])
    plan = fixture.read_review_plan()
    delta_entry = next(entry for entry in plan["delta_files"] if entry["path"] == "scripts/sibling-program.py")
    check("delta hook registrations include the earlier reviewed head even after removal",
          delta_entry["class"] == "hook" and delta_entry["tier"] == "claude-and-codex-review-and-head-tests-tier"
          and plan["changed_files"][0]["class"] == "code", plan)

    fixture.reset_fixture_to_base()
    fixture.write_fixture_file("scripts/example-program.py", BASELINE_FILE_CONTENTS["scripts/example-program.py"].replace('"old"', '"earlier"'))
    earlier = fixture.commit_fixture_changes("earlier head before rewrite and merge")
    fixture.git_command("checkout", "-q", "--detach", fixture.base_head)
    fixture.write_fixture_file("docs/plain-note.txt", "Main's unrelated prose.\n")
    main_head = fixture.commit_fixture_changes("main before rewritten branch merge")
    fixture.git_command("update-ref", "refs/remotes/origin/main", main_head)
    fixture.git_command("checkout", "-q", "--detach", fixture.base_head)
    fixture.write_fixture_file("scripts/example-program.py", BASELINE_FILE_CONTENTS["scripts/example-program.py"].replace("return 1", "return 4"))
    fixture.commit_fixture_changes("rewritten logic")
    fixture.git_command("merge", "-q", "--no-ff", "-m", "merge after rewrite", main_head)
    head = fixture.git_command("rev-parse", "HEAD")
    fixture.configure_github_answers(head, reviews=[[fixture_review(101, earlier)]], live_base=main_head)
    plan = fixture.read_review_plan()
    check("a claude-and-codex-review-and-head-tests-tier program delta after a merge and rewritten history lists only those two reasons",
          plan["delta_only_review_applies"] is False and plan["delta_tier"] == "claude-and-codex-review-and-head-tests-tier"
          and len(plan["delta_only_review_reasons"]) == 2
          and head[:12] in plan["delta_only_review_reasons"][0]
          and "history was rewritten" in plan["delta_only_review_reasons"][1], plan)

    fixture.reset_fixture_to_base()
    fixture.write_fixture_file("scripts/example-program.py", BASELINE_FILE_CONTENTS["scripts/example-program.py"].replace('"old"', '"earlier"'))
    fixture.write_fixture_file("docs/plain-note.txt", "Earlier round's own prose.\n")
    earlier = fixture.commit_fixture_changes("earlier changes later reverted")
    fixture.git_command("checkout", "-q", "--detach", fixture.base_head)
    fixture.write_fixture_file("scripts/unrelated-main-program.py", "VALUE = 1\n")
    main_head = fixture.commit_fixture_changes("unrelated main before revert")
    fixture.git_command("update-ref", "refs/remotes/origin/main", main_head)
    fixture.git_command("checkout", "-q", "--detach", earlier)
    fixture.git_command("merge", "-q", "--no-ff", "-m", "merge before reverting own file", main_head)
    fixture.write_fixture_file("docs/plain-note.txt", BASELINE_FILE_CONTENTS["docs/plain-note.txt"])
    head = fixture.commit_fixture_changes("revert earlier prose")
    fixture.configure_github_answers(head, reviews=[[fixture_review(101, earlier)]], live_base=main_head)
    plan = fixture.read_review_plan()
    check("restricted delta retains files belonging only to the earlier PR diff",
          [entry["path"] for entry in plan["delta_files"]] == ["docs/plain-note.txt"]
          and plan["delta_tier"] == "no-reviewer-tier", plan)

    fixture.reset_fixture_to_base()
    fixture.git_command("mv", "scripts/sibling-program.py", "scripts/renamed-sibling-program.py")
    head = fixture.commit_fixture_changes("program rename")
    fixture.configure_github_answers(head)
    plan = fixture.read_review_plan()
    check("program renames are deletion plus addition and get claude-and-codex-review-and-head-tests-tier",
          sorted(entry["status"] for entry in plan["changed_files"]) == ["A", "D"]
          and plan["tier"] == "claude-and-codex-review-and-head-tests-tier", plan)


def run_agent_text_cases(fixture):
    fixture.reset_fixture_to_base()
    long_help_program_source = '"""' + "\n".join(f"Help line {line_number}." for line_number in range(1, 13)) + '\n"""\nHELP_TEXT = __doc__\n'
    fixture.write_fixture_file("scripts/long-help-program.py", long_help_program_source)
    long_help_merge_base_head = fixture.commit_fixture_changes("long help program at merge base")
    fixture.git_command("update-ref", "refs/remotes/origin/main", long_help_merge_base_head)
    fixture.write_fixture_file("scripts/long-help-program.py", long_help_program_source.replace("Help line 6.", "Help line six."))
    long_help_changed_head = fixture.commit_fixture_changes("change one long help docstring line")
    fixture.configure_github_answers(long_help_changed_head, live_base=long_help_merge_base_head)
    long_help_text_result = fixture.run_review_plan(json_output=False)
    unchanged_help_docstring_lines = [f"Help line {line_number}." for line_number in range(1, 13) if line_number != 6]
    check("long agent-facing text shows changed lines without repeating unchanged docstring lines",
          long_help_text_result.returncode == 0 and "changed lines:" in long_help_text_result.stdout
          and any(line.endswith("-Help line 6.") for line in long_help_text_result.stdout.splitlines())
          and any(line.endswith("+Help line six.") for line in long_help_text_result.stdout.splitlines())
          and all(long_help_text_result.stdout.count(line) <= 1 for line in unchanged_help_docstring_lines),
          long_help_text_result)
    long_help_skeleton_path = fixture.control_directory / "long-help-review-brief.md"
    long_help_skeleton_result = fixture.run_review_plan("--brief-skeleton", str(long_help_skeleton_path))
    long_help_skeleton_text = long_help_skeleton_path.read_text()
    check("long agent-facing text skeleton uses a diff fence for changed lines",
          long_help_skeleton_result.returncode == 0
          and bool(re.search(r"^`{3,}diff$", long_help_skeleton_text, re.MULTILINE)), long_help_skeleton_text)
    long_help_json_plan = fixture.read_review_plan()
    long_help_docstring_entry = next(entry for entry in long_help_json_plan["agent_facing_text_whole_pull_request"]
                                    if entry["path"] == "scripts/long-help-program.py")
    check("long agent-facing text JSON retains full old and new docstrings",
          "Help line 6." in long_help_docstring_entry["old_text"]
          and "Help line 12." in long_help_docstring_entry["old_text"]
          and "Help line six." in long_help_docstring_entry["new_text"]
          and "Help line 12." in long_help_docstring_entry["new_text"], long_help_docstring_entry)

    fixture.reset_fixture_to_base()
    fixture.write_fixture_file("scripts/agent-messages.py", BASELINE_FILE_CONTENTS["scripts/agent-messages.py"].replace("Old", "New"))
    fixture.write_fixture_file("scripts/agent-messages-test.py", 'print("New test message")\n')
    head = fixture.commit_fixture_changes("agent-facing message changes")
    fixture.configure_github_answers(head, reviews=[[fixture_review(101, fixture.base_head)]])
    plan = fixture.read_review_plan()
    entries = plan["agent_facing_text_whole_pull_request"]
    f_string_entry = next((entry for entry in entries if entry["label"] == "print in show_message()"), {})
    check("changed print f-strings retain placeholders and old/new text", "{name}" in f_string_entry.get("old_text", "") and "{name}" in f_string_entry.get("new_text", "") and "Old message" in f_string_entry["old_text"] and "New message" in f_string_entry["new_text"], entries)
    check("changed raise text is listed with context", any(entry["label"] == "raise in show_message()" and entry["old_text"] == "Old failure" and entry["new_text"] == "New failure" for entry in entries), entries)
    check("changed advice constants are listed", any(entry["label"] == "CHECK_ADVICE =" and entry["old_text"] == "Old advice ``` marker" and entry["new_text"] == "New advice ``` marker" for entry in entries), entries)
    check("module docstrings printed through __doc__ are listed", any(entry["label"] == "module docstring (printed by --help)" and "Old help" in entry["old_text"] and "New help" in entry["new_text"] for entry in entries), entries)
    check("unchanged strings inside a changed hunk are omitted", not any(entry["new_text"] == "unchanged" for entry in entries), entries)
    check("test strings are not agent-facing text", not any(entry["path"].endswith("-test.py") for entry in entries), entries)
    check("fix round delta also lists agent-facing strings", plan["agent_facing_text_delta"] == entries, plan)
    skeleton_path = fixture.control_directory / "agent-text-brief.md"
    result = fixture.run_review_plan("--brief-skeleton", str(skeleton_path))
    skeleton = skeleton_path.read_text()
    check("agent text skeleton uses fences longer than embedded backticks", result.returncode == 0 and "````\nNew advice ``` marker\n````" in skeleton, skeleton)
    source_before = 'def outer():\n    class Inner:\n        def show(self):\n            sys.stderr.write("old stderr")\n            sys.stdout.write("old stdout")\n            EXTRA_MESSAGE: str = "old annotated"\n            EXTRA_MESSAGE += "old augmented"\n'
    fixture.reset_fixture_to_base()
    fixture.write_fixture_file("scripts/scoped-messages.py", source_before)
    earlier = fixture.commit_fixture_changes("scoped messages")
    fixture.write_fixture_file("scripts/scoped-messages.py", source_before.replace("old", "new"))
    head = fixture.commit_fixture_changes("scoped message changes")
    fixture.configure_github_answers(head, reviews=[[fixture_review(101, earlier)]])
    delta = fixture.read_review_plan()["agent_facing_text_delta"]
    check("stream writes and annotated/augmented assignments retain qualified contexts", {entry["label"] for entry in delta} == {"sys.stderr.write in outer.Inner.show()", "sys.stdout.write in outer.Inner.show()", "EXTRA_MESSAGE = in outer.Inner.show()"} and len(delta) == 4, delta)
    old_source = 'print(\n    "same moved message")\n'
    new_source = 'print("same moved message")\n'
    fixture.reset_fixture_to_base()
    fixture.write_fixture_file("scripts/scoped-messages.py", old_source)
    earlier = fixture.commit_fixture_changes("multiline message")
    fixture.write_fixture_file("scripts/scoped-messages.py", new_source)
    head = fixture.commit_fixture_changes("reflow message")
    fixture.configure_github_answers(head, reviews=[[fixture_review(101, earlier)]])
    plan = fixture.read_review_plan()
    check("reflowed identical messages are omitted", plan["agent_facing_text_delta"] == [], plan)


def run_fast_read_command_cases(fixture):
    fixture.reset_fixture_to_base()
    fixture.write_fixture_file("scripts/agent-messages.py", BASELINE_FILE_CONTENTS["scripts/agent-messages.py"].replace("Old failure", "Middle failure"))
    earlier = fixture.commit_fixture_changes("earlier message")
    fixture.write_fixture_file("scripts/agent-messages.py", BASELINE_FILE_CONTENTS["scripts/agent-messages.py"].replace("Old failure", "New failure"))
    head = fixture.commit_fixture_changes("reworded message")
    fixture.configure_github_answers(head, reviews=[[fixture_review(101, earlier)]])
    plan = fixture.read_review_plan()
    whole_entry = next(entry for entry in plan["agent_facing_text_whole_pull_request"] if entry["label"] == "raise in show_message()")
    delta_entry = next(entry for entry in plan["agent_facing_text_delta"] if entry["label"] == "raise in show_message()")
    command_prefix = "python3 nc-systems/cold-read/cold-read-fast-read.py --target "
    try:
        command_words = shlex.split(whole_entry["fast_read_command"])
    except ValueError:
        command_words = []  # An unquoted target can leave a quote unclosed; the case below then fails by name.
    target = Path(command_words[-1]) if len(command_words) == 4 else Path()
    check("each listed message gets a fast-read command whose target holds its new text",
          whole_entry["fast_read_command"].startswith(command_prefix) and whole_entry["fast_read_target_error"] is None
          and target.is_relative_to(fixture.message_target_temporary_directory)
          and target.read_text(encoding="utf-8") == "New failure\n", whole_entry)
    check("the delta's entry for the same new text gets the same command",
          delta_entry["fast_read_command"] == whole_entry["fast_read_command"], delta_entry)
    text_result = fixture.run_review_plan(json_output=False)
    check("the text plan prints each command beside its message",
          text_result.returncode == 0
          and text_result.stdout.count("    cold-read-fast-read: " + whole_entry["fast_read_command"]) == 2, text_result)
    skeleton_path = fixture.control_directory / "fast-read-brief.md"
    skeleton_result = fixture.run_review_plan("--brief-skeleton", str(skeleton_path))
    check("the brief skeleton carries each command",
          skeleton_result.returncode == 0
          and skeleton_path.read_text().count("cold-read-fast-read: " + whole_entry["fast_read_command"]) == 2,
          skeleton_result)

    blocked_temporary_directory = fixture.control_directory / "temporary-directory-with-target-directory-blocked"
    blocked_temporary_directory.mkdir()
    (blocked_temporary_directory / review_plan_module._message_reminder_hook.FAST_READ_TARGET_DIRECTORY_NAME).write_text(
        "a file where the target directory belongs\n", encoding="utf-8")
    saved_environment = fixture.environment
    fixture.environment = {**saved_environment, "TMPDIR": str(blocked_temporary_directory)}
    try:
        json_result = fixture.run_review_plan()
        text_result = fixture.run_review_plan(json_output=False)
    finally:
        fixture.environment = saved_environment
    blocked_plan = json.loads(json_result.stdout) if json_result.stdout else {}
    blocked_entries = blocked_plan.get("agent_facing_text_whole_pull_request", [])
    check("a target that cannot be written leaves the plan printed, the entry marked and exit 3, not a refusal's 1",
          json_result.returncode == 3 and bool(blocked_entries)
          and all(entry["fast_read_command"] is None and entry["fast_read_target_error"] for entry in blocked_entries)
          and "1 listed agent-facing message has no cold-read-fast-read command, because its text" in json_result.stderr
          and "--target <that file's full path>" in json_result.stderr, json_result)
    blocked_entry = blocked_entries[0] if blocked_entries else {"path": "", "line": 0, "new_text": ""}
    file_name = review_plan_module._message_reminder_hook.fast_read_target_path(blocked_entry["path"], blocked_entry["new_text"]).name
    listing_lines = [line for line in json_result.stderr.splitlines() if line.startswith("  ")]
    check("the message lists each message without a command once, by path, line and label, with the file name to write",
          listing_lines == [f"  {blocked_entry['path']}:{blocked_entry['line']}  label: {blocked_entry.get('label')}  file name: {file_name}"]
          and "a directory outside your checkout, such as one made with mktemp -d" in json_result.stderr, json_result.stderr)
    two_entries = [{"path": "a.py", "line": 3, "label": "raise in f()", "new_text": "one", "fast_read_target_file_name": "one.md"},
                   {"path": "a.py", "line": 3, "label": "print in f()", "new_text": "two", "fast_read_target_file_name": "two.md"}]
    check("the count reads right for more than one message",
          "2 listed agent-facing messages have no cold-read-fast-read command, because their text"
          in review_plan_module.missing_fast_read_commands_message(two_entries))
    check("each entry carries the file name the message lists, so the message's file name finds its entry",
          all(entry["fast_read_target_file_name"] == review_plan_module._message_reminder_hook.fast_read_target_path(entry["path"], entry["new_text"]).name
              for entry in blocked_entries)
          and "whose fast_read_target_file_name is that file name" in json_result.stderr, json_result)
    check("the text plan says why a message has no command",
          text_result.returncode == 3
          and "cold-read-fast-read: none, because this message's text could not be written to a file: " in text_result.stdout,
          text_result)
    check("after a JSON run, the message says to use the JSON this run printed",
          "1. Use the plan this run printed as JSON on stdout." in json_result.stderr, json_result.stderr)
    text_stderr_lines = text_result.stderr.splitlines()
    rerun_index = next((index for index, line in enumerate(text_stderr_lines) if line.startswith("1. Get the plan as JSON")), None)
    try:
        rerun_words = shlex.split(text_stderr_lines[rerun_index + 1]) if rerun_index is not None else []
    except (ValueError, IndexError):
        rerun_words = []
    check("after a text run, the message gives this run's own command with --json and without --brief-skeleton",
          rerun_words == ["python3", "scripts/pull-request-review-plan.py",
                          "--pull-request", str(FIXTURE_PULL_REQUEST_NUMBER), "--repository", str(fixture.repository.resolve()),
                          "--github-repository", FIXTURE_GITHUB_REPOSITORY, "--json"], text_result.stderr)
    fixture.environment = {**saved_environment, "TMPDIR": str(blocked_temporary_directory)}
    try:
        relative_result = subprocess.run(
            [sys.executable, str(REVIEW_PLAN_SCRIPT), "--pull-request", str(FIXTURE_PULL_REQUEST_NUMBER),
             "--repository", "..", "--github-repository", FIXTURE_GITHUB_REPOSITORY],
            cwd=fixture.repository / "scripts", env=fixture.environment, capture_output=True, text=True, timeout=10)
    finally:
        fixture.environment = saved_environment
    relative_lines = relative_result.stderr.splitlines()
    relative_index = next((index for index, line in enumerate(relative_lines) if line.startswith("1. Get the plan as JSON")), None)
    try:
        relative_words = shlex.split(relative_lines[relative_index + 1]) if relative_index is not None else []
    except (ValueError, IndexError):
        relative_words = []
    check("run from a subdirectory with a relative --repository, the rerun command names the repository by its absolute path",
          relative_result.returncode == 3 and "--repository" in relative_words
          and relative_words[relative_words.index("--repository") + 1] == str(fixture.repository.resolve()),
          relative_result.stderr)

    hook_tempfile = review_plan_module._message_reminder_hook.tempfile
    saved_gettempdir = hook_tempfile.gettempdir

    def gettempdir_finding_no_usable_directory():
        raise FileNotFoundError(2, "No usable temporary directory found")
    hook_tempfile.gettempdir = gettempdir_finding_no_usable_directory
    try:
        try:
            unplaced = review_plan_module.entries_with_fast_read_commands(
                [{"path": "scripts/a.py", "line": 1, "label": "raise in f()", "new_text": "text"}])
        except OSError as escaped:
            unplaced = [{"escaped": f"{type(escaped).__name__}: {escaped}"}]
    finally:
        hook_tempfile.gettempdir = saved_gettempdir
    check("no usable temporary directory marks the entry, with its file name, instead of ending the run",
          len(unplaced) == 1 and unplaced[0].get("fast_read_command", "absent") is None
          and "FileNotFoundError" in (unplaced[0].get("fast_read_target_error") or "")
          and unplaced[0].get("fast_read_target_file_name")
          == review_plan_module._message_reminder_hook.fast_read_target_file_name("scripts/a.py", "text"), unplaced)


def run_repository_and_output_cases(fixture):
    fixture.reset_fixture_to_base()
    fixture.write_fixture_file("scripts/example-program.py", BASELINE_FILE_CONTENTS["scripts/example-program.py"].replace('"old"', '"open branch"'))
    head = fixture.commit_fixture_changes("open pull request with no merge commit")
    fixture.configure_github_answers(head)
    plan = fixture.read_review_plan()
    check("an open pull request diff base is the full origin/main commit hash",
          plan["diff_base"] == fixture.base_head and bool(re.fullmatch(r"[0-9a-fA-F]{40}", plan["diff_base"]))
          and "origin/main" in plan["diff_base_reason"] and "not merged" in plan["diff_base_reason"], plan)

    fixture.reset_fixture_to_base()
    for author, expected_text in [("mac-claude", "posts a COMMENT"), ("ned-review-merge", "approval is the one the merge needs"), ("another-login", "a normal review")]:
        fixture.configure_github_answers(fixture.base_head, author=author)
        plan = fixture.read_review_plan()
        check("posting rule for " + author, expected_text in plan["posting_rule"] and plan["author"] == author, plan)

    fixture.write_fixture_file("conflicting-example.txt", "pull request\n")
    fixture.write_fixture_file("côté notes.md", "pull request\n")
    head = fixture.commit_fixture_changes("pull request conflict")
    fixture.git_command("checkout", "-q", "--detach", fixture.base_head)
    fixture.write_fixture_file("conflicting-example.txt", "main\n")
    fixture.write_fixture_file("côté notes.md", "main\n")
    main_head = fixture.commit_fixture_changes("main conflict")
    fixture.git_command("update-ref", "refs/remotes/origin/main", main_head)
    fixture.configure_github_answers(head, live_base=main_head)
    plan = fixture.read_review_plan()
    check("conflicting merged tree lists each path as stored, a non-ASCII name with a space included",
          plan["merged_tree"]["conflicting_paths"] == ["conflicting-example.txt", "côté notes.md"] and plan["merged_tree"]["error"] is None, plan)

    fixture.reset_fixture_to_base()
    fixture.write_fixture_file("scripts/example-program.py", BASELINE_FILE_CONTENTS["scripts/example-program.py"].replace('"old"', '"merged"'))
    head = fixture.commit_fixture_changes("pull request for merged diff")
    fixture.git_command("checkout", "-q", "--detach", fixture.base_head)
    fixture.write_fixture_file("scripts/only-on-main.py", "VALUE = 1\n")
    first_parent = fixture.commit_fixture_changes("main before merge")
    fixture.git_command("merge", "-q", "--no-ff", "-m", "merge pull request", head)
    merge_commit = fixture.git_command("rev-parse", "HEAD")
    fixture.git_command("update-ref", "refs/remotes/origin/main", merge_commit)
    fixture.configure_github_answers(head, state="MERGED", merge_commit=merge_commit, live_base=merge_commit)
    plan = fixture.read_review_plan()
    check("a merged pull request uses the first parent and retains its own changes", plan["diff_base"] == first_parent and "first parent" in plan["diff_base_reason"] and [entry["path"] for entry in plan["changed_files"]] == ["scripts/example-program.py"], plan)

    fixture.configure_github_answers(head, live_base="b" * 40)
    plan = fixture.read_review_plan()
    check("a nonlocal GitHub base tip produces a stale-main warning", "behind GitHub's" in (plan["base_branch_behind_github_warning"] or "") and "fetch origin" in plan["base_branch_behind_github_warning"], plan)
    fixture.git_command("update-ref", "refs/remotes/origin/main", fixture.base_head)
    fixture.configure_github_answers(head, live_base=first_parent)
    plan = fixture.read_review_plan()
    check("a local GitHub base tip ahead of origin also warns", plan["base_branch_behind_github_warning"] is not None, plan)
    fixture.git_command("update-ref", "refs/remotes/origin/main", merge_commit)
    fixture.configure_github_answers(head, live_base=fixture.base_head)
    plan = fixture.read_review_plan()
    check("origin ahead of GitHub produces no stale warning", plan["base_branch_behind_github_warning"] is None, plan)

    fixture.reset_fixture_to_base()
    for path in ("scripts/sibling-program.py", "scripts/nested-program.py", "nc-systems/example/parent-program.py"):
        fixture.write_fixture_file(path, 'print("new")\n')
    fixture.write_fixture_file("scripts/example-program-test.py", 'EXPECTED = "new"\n')
    (fixture.repository / "scripts/sibling-program-test.py").unlink()
    # A deletion must not offer a nonexistent test; recreate it in a later case.
    head = fixture.commit_fixture_changes("associated tests with deleted sibling")
    fixture.configure_github_answers(head)
    plan = fixture.read_review_plan()
    check("test discovery includes changed tests and nested/parent test directories, excluding deleted tests", plan["test_files_to_run"] == ["nc-systems/tests/parent-program-test.py", "scripts/example-program-test.py", "scripts/tests/nested-program-test.py"], plan)
    fixture.write_fixture_file("scripts/sibling-program-test.py", "assert True\n")
    head = fixture.commit_fixture_changes("restore sibling test")
    fixture.configure_github_answers(head)
    plan = fixture.read_review_plan()
    check("changed programs discover sibling tests and results are sorted and deduplicated", plan["test_files_to_run"] == ["nc-systems/tests/parent-program-test.py", "scripts/example-program-test.py", "scripts/sibling-program-test.py", "scripts/tests/nested-program-test.py"], plan)
    text_result = fixture.run_review_plan(json_output=False)
    check("text output includes tier and posting rule", text_result.returncode == 0 and "tier: " in text_result.stdout and "posting rule: " in text_result.stdout, text_result)
    skeleton_path = fixture.control_directory / "review-brief.md"
    result = fixture.run_review_plan("--brief-skeleton", str(skeleton_path))
    skeleton = skeleton_path.read_text()
    check("brief skeleton ends with the empty What to check heading", result.returncode == 0 and re.findall(r"^### .*$", skeleton, re.MULTILINE)[-1] == "### What to check" and skeleton.endswith("### What to check\n\n"), skeleton)
    check("brief creation still prints the usual JSON", json.loads(result.stdout) == plan, result.stdout)
    before_text = skeleton_path.read_bytes()
    result = fixture.run_review_plan("--brief-skeleton", str(skeleton_path))
    check("an existing brief is refused and unchanged", refusal_has_expected_prefix(result) and skeleton_path.read_bytes() == before_text, result.stderr)
    result = fixture.run_review_plan("--brief-skeleton", str(fixture.control_directory / "missing-directory" / "brief.md"))
    check("a missing brief directory is refused", refusal_has_expected_prefix(result), result.stderr)

    # The split suite lands on main first, so the pull request changes only the
    # program and the parts are found by name, not as changed tests.
    fixture.reset_fixture_to_base()
    for path in ("scripts/sibling-program-launch-test.py", "scripts/tests/sibling-program-resume-test.py",
                 "tests/sibling-program-parent-directory-test.py", "scripts/sibling-programmer-test.py",
                 "scripts/sibling-program-test-fixture.py", "scripts/elsewhere/sibling-program-elsewhere-test.py"):
        fixture.write_fixture_file(path, "assert True\n")
    main_with_a_split_suite = fixture.commit_fixture_changes("a sibling suite split by topic lands on main")
    fixture.git_command("update-ref", "refs/remotes/origin/main", main_with_a_split_suite)
    fixture.write_fixture_file("scripts/sibling-program.py", 'print("new")\n')
    head = fixture.commit_fixture_changes("change the program whose suite was split")
    fixture.configure_github_answers(head, live_base=main_with_a_split_suite)
    plan = fixture.read_review_plan()
    check("a changed program discovers each part of its split suite in every test directory, and no file that only shares the name's start",
          plan["test_files_to_run"] == ["scripts/sibling-program-launch-test.py", "scripts/sibling-program-test.py",
                                        "scripts/tests/sibling-program-resume-test.py",
                                        "tests/sibling-program-parent-directory-test.py"], plan)

    # Git reads a pathspec relative to the -C directory, so each path-limited
    # git call needs a change here: a fenced Markdown block, agent-facing text
    # and a split suite.
    fixture.write_fixture_file("scripts/agent-messages.py", BASELINE_FILE_CONTENTS["scripts/agent-messages.py"].replace("Old", "New"))
    fixture.write_fixture_file("docs/review-note.md", BASELINE_FILE_CONTENTS["docs/review-note.md"].replace("print('old')", "print('new')"))
    head = fixture.commit_fixture_changes("changes that path-limited git calls must see")
    fixture.configure_github_answers(head, live_base=main_with_a_split_suite)
    top_level_plan = fixture.read_review_plan()
    subdirectory_result = fixture.run_review_plan("--repository", str(fixture.repository / "scripts"))
    check("a run from a subdirectory of the checkout gives the top-level run's plan, agent-facing text, tiers and split suites included",
          subdirectory_result.returncode == 0 and json.loads(subdirectory_result.stdout) == top_level_plan
          and "scripts/sibling-program-launch-test.py" in top_level_plan["test_files_to_run"]
          and top_level_plan["agent_facing_text_whole_pull_request"]
          and any(entry["path"] == "docs/review-note.md" and entry["tier"] == "codex-review-and-head-tests-tier" for entry in top_level_plan["changed_files"]),
          subdirectory_result.stdout or subdirectory_result.stderr)


def run_refusal_and_call_shape_cases(fixture):
    fixture.reset_fixture_to_base()
    git_refusal_message_text = ""
    try:
        review_plan_module.required_git_output(fixture.repository, "rev-parse", "--verify", "no-such-revision-for-review-plan")
    except review_plan_module.ReviewPlanRefusal as failure:
        git_refusal_message_text = str(failure)
    git_revision_fetch_instruction = next((line for line in git_refusal_message_text.splitlines()
                                           if line.startswith("If git says it cannot find a revision: run ")), "")
    check("a required git refusal names the revision fetch and separate fallback instruction",
          bool(re.search(r"`[^`]*fetch origin[^`]*`", git_revision_fetch_instruction))
          and "Otherwise: tell the user what git said." in git_refusal_message_text.splitlines(), git_refusal_message_text)

    fixture.reset_fixture_to_base()
    fixture.set_github_response("pull-request.json", stdout="", exit_code=1, stderr="not logged in\nmore detail\n")
    result = fixture.run_review_plan()
    check("a gh exit one is a refusal with conditional instructions", refusal_has_expected_prefix(result) and "not logged in" in result.stderr and "If gh says" in result.stderr, result.stderr)
    fixture.configure_github_answers("c" * 40)
    result = fixture.run_review_plan()
    check("a nonlocal head is refused with a fetch that creates no branch", refusal_has_expected_prefix(result) and f"fetch origin pull/{FIXTURE_PULL_REQUEST_NUMBER}/head`" in result.stderr, result.stderr)
    result = fixture.run_review_plan("--unknown-argument")
    check("malformed arguments are a refusal", refusal_has_expected_prefix(result), result.stderr)
    result = fixture.run_review_plan("--pull-request", "0")
    check("a nonpositive pull request is refused", refusal_has_expected_prefix(result), result.stderr)
    result = fixture.run_review_plan("--repository", str(fixture.control_directory))
    check("a directory outside git is refused", refusal_has_expected_prefix(result) and "not inside a git repository" in result.stderr, result.stderr)
    result = fixture.run_review_plan("--repository", str(fixture.repository / ".git"))
    check("a .git directory is refused as outside a checkout", refusal_has_expected_prefix(result) and "not inside a git repository" in result.stderr, result.stderr)
    bare_repository = fixture.repository.parent / "bare-repository"
    fixture.git_command("init", "-q", "--bare", str(bare_repository))
    result = fixture.run_review_plan("--repository", str(bare_repository))
    check("a bare repository is refused as outside a checkout", refusal_has_expected_prefix(result) and "not inside a git repository" in result.stderr, result.stderr)
    for control_name, stdout in [("pull-request.json", "not json"), ("reviews.json", "[{}]"),
                                 ("comments.json", '[[{"pull_request_review_id":"invalid"}]]'),
                                 ("branch.json", '{"commit":{}}')]:
        fixture.configure_github_answers(fixture.base_head)
        fixture.set_github_response(control_name, stdout=stdout)
        result = fixture.run_review_plan()
        check("unexpected gh data is refused for " + control_name, refusal_has_expected_prefix(result) and "unexpected JSON" in result.stderr, result.stderr)
    fixture.configure_github_answers(fixture.base_head, state="MERGED", merge_commit="d" * 40)
    result = fixture.run_review_plan()
    check("a nonlocal merged commit is refused with fetch origin", refusal_has_expected_prefix(result) and "merge commit" in result.stderr and "fetch origin`" in result.stderr, result.stderr)
    fixture.configure_github_answers(fixture.base_head, base_branch="topic-base")
    result = fixture.run_review_plan()
    check("a missing origin base branch is refused", refusal_has_expected_prefix(result) and "origin/topic-base" in result.stderr and "fetch origin`" in result.stderr, result.stderr)
    fixture.git_command("update-ref", "refs/remotes/origin/topic-base", fixture.base_head)
    fixture.git_command("update-ref", "-d", "refs/remotes/origin/main")
    result = fixture.run_review_plan()
    check("a missing origin/main is refused even for another base branch", refusal_has_expected_prefix(result) and "origin/main" in result.stderr, result.stderr)
    fixture.reset_fixture_to_base()
    fixture.configure_github_answers(fixture.base_head, base_branch="topic/base")
    fixture.git_command("update-ref", "refs/remotes/origin/topic/base", fixture.base_head)
    plan = fixture.read_review_plan()
    check("a base branch with a slash works through the branch API", plan["base_branch"] == "topic/base", plan)
    calls = [json.loads(line) for line in (fixture.control_directory / "calls.jsonl").read_text().splitlines()]
    prefix = f"repos/{FIXTURE_GITHUB_REPOSITORY}"
    accepted_calls = [
        ["pr", "view", str(FIXTURE_PULL_REQUEST_NUMBER), "--repo", FIXTURE_GITHUB_REPOSITORY,
         "--json", "number,title,url,state,author,headRefOid,baseRefName,mergeCommit"],
        ["api", "--paginate", "--slurp", f"{prefix}/pulls/{FIXTURE_PULL_REQUEST_NUMBER}/reviews"],
        ["api", "--paginate", "--slurp", f"{prefix}/pulls/{FIXTURE_PULL_REQUEST_NUMBER}/comments"],
        *[["api", f"{prefix}/branches/{base}"] for base in ("main", "topic-base", "topic%2Fbase")],
    ]
    check("every gh call is one of the four read-only shapes with the requested repository", bool(calls) and all(call in accepted_calls for call in calls) and all(shape in calls for shape in accepted_calls[:4]), calls)


def run_git_failure_cases(fixture):
    """A git failure stops the plan with git's words instead of reading as an absent commit or file."""
    def refused_with_git_failure(result):
        return refusal_has_expected_prefix(result) and "fatal: injected repository failure" in result.stderr

    fixture.reset_fixture_to_base()
    fixture.write_fixture_file("docs/review-note.md", "Changed prose.\n\n```python\nprint('new')\n```\n")
    fixture.write_fixture_file("scripts/example-program.py", BASELINE_FILE_CONTENTS["scripts/example-program.py"] + "VALUE = 2\n")
    fixture.write_fixture_file("scripts/example-program-test.py", "print('test')\n")
    head = fixture.commit_fixture_changes("change prose, a program and its test")
    fixture.configure_github_answers(head)
    plan = fixture.read_review_plan()
    check("the git failure cases' control plan runs the changed program's test",
          plan["test_files_to_run"] == ["scripts/example-program-test.py"], plan)

    result = fixture.run_review_plan_with_git_failing_on("rev-parse", "--verify", "--quiet", f"{head}^{{commit}}")
    check("git failing while looking up the head is refused with git's error, not as a head missing from the repository",
          refused_with_git_failure(result) and "is not in the repository" not in result.stderr, result.stderr)
    result = fixture.run_review_plan_with_git_failing_on("ls-tree", "-z", "--name-only", head, "--", "docs/review-note.md")
    check("git failing while looking for a changed file is refused, not read as the file being absent",
          refused_with_git_failure(result) and not result.stdout, result.stderr + result.stdout)
    result = fixture.run_review_plan_with_git_failing_on("show", f"{head}:docs/review-note.md")
    check("git failing while reading a changed file that is there is refused",
          refused_with_git_failure(result) and not result.stdout, result.stderr + result.stdout)
    result = fixture.run_review_plan_with_git_failing_on("ls-tree", "-z", "--name-only", head, "--", "scripts/example-program-test.py")
    check("git failing while looking for test files is refused, not a plan that leaves the test out",
          refused_with_git_failure(result) and not result.stdout, result.stderr + result.stdout)


def main():
    start_time = time.monotonic()
    run_unit_cases()
    with tempfile.TemporaryDirectory(prefix="pull-request-review-plan-test-") as temporary_directory:
        fixture = ReviewPlanTemporaryRepositoryFixture(Path(temporary_directory))
        run_classification_cases(fixture)
        run_fix_round_cases(fixture)
        run_hook_registration_and_delta_boundary_cases(fixture)
        run_agent_text_cases(fixture)
        run_fast_read_command_cases(fixture)
        run_repository_and_output_cases(fixture)
        run_refusal_and_call_shape_cases(fixture)
        run_git_failure_cases(fixture)
    print(f"{len(CHECK_FAILURE_NAMES)} failed; elapsed {time.monotonic() - start_time:.2f}s")
    return 1 if CHECK_FAILURE_NAMES else 0


if __name__ == "__main__":
    sys.exit(main())
