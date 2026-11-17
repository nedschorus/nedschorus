#!/usr/bin/env python3
"""Tests for merge-lane-pull-request-reviewer-brief-compose-with-facts.py.

Runs the program against real git in a scratch repository that serves as
--review-tools-worktree-at-main: main, a first nc-head-commit and a fix-round nc-head-commit, with a
copy of this directory's compose-pull-request-reviewer-brief.py and an
instructions file committed on main. wt/pr7-merged is a worktree of that
repository. The reviewer's scratch directories are made in their own directory
of the scratch, in place of the default parent outside the log-store. The program runs with GIT_DIR pointing at a directory that does
not exist, so a case passes only if the program drops it. A stand-in for gh
on PATH serves the pull request's closing issues and description and the merged
pull requests from routes each case arranges, and logs each call with the GH_TOKEN it saw;
HOME is a scratch directory holding the merge account's token file.

Run: python3 scripts/merge-lane-pull-request-reviewer-brief-compose-with-facts-test.py
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
    Path(__file__).resolve().with_name(
        "git-redirecting-environment-removal-test-fixture.py"))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

PROGRAM = Path(__file__).with_name("merge-lane-pull-request-reviewer-brief-compose-with-facts.py")
COMPOSER = Path(__file__).with_name("compose-pull-request-reviewer-brief.py")
GIT_ENVIRONMENT = {
    **{key: value for key, value in os.environ.items() if not key.startswith("GIT_")},
    "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid",
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
}
STANDING_TEXT = "Review pull request <N>.\n<<PR-REVIEWER-INSTRUCTIONS>>\nEnd of standing text.\n"
INSTRUCTIONS = "The reviewing instructions.\n"
ADDENDUM = "The ned-box addendum.\n"
DESCRIPTION = "The author's description.\n\n#no_defect_fixed\n"

TEST_TOKEN = "brief-compose-test-token-not-a-credential"
GH_STAND_IN = r'''#!/usr/bin/env python3
import json, os, sys
argv = sys.argv[1:]
with open(os.environ["BRIEF_COMPOSE_TEST_GH_CALL_LOG"], "a") as log:
    log.write(json.dumps({"argv": argv, "gh_token": os.environ.get("GH_TOKEN")}) + "\n")
routes = json.load(open(os.environ["BRIEF_COMPOSE_TEST_GH_ROUTES"]))
key = {"view": "closing", "list": "merged"}.get(argv[1] if argv[:1] == ["pr"] else "")
route = routes.get(key)
if route is None:
    sys.stderr.write("brief-compose-test stand-in: unarranged gh call %r\n" % (argv,))
    sys.exit(97)
sys.stdout.write(route.get("stdout", ""))
sys.stderr.write(route.get("stderr", ""))
sys.exit(route.get("exit", 0))
'''


GIT_FAILING_ON_LINE_LOG = r'''#!/usr/bin/env python3
import os, sys
if "log" in sys.argv and any(argument.startswith("-L") for argument in sys.argv):
    sys.stderr.write("fatal: file scripts/fixed.py has only 5 lines\n")
    sys.exit(128)
os.execv("REAL_GIT", ["REAL_GIT", *sys.argv[1:]])
'''


def closing_route(closing_issues=(), body=DESCRIPTION):
    return {"stdout": json.dumps({"closingIssuesReferences": list(closing_issues), "body": body})}


QUIET_GH_ROUTES = {"closing": closing_route(), "merged": {"stdout": "[]"}}

failures = []


def review_worktrees_directory(helpers):
    return helpers.parent / f"{helpers.name}-review-worktrees"


def check(name, condition, detail=""):
    print(("PASS  " if condition else "FAIL  ") + name)
    if not condition:
        failures.append(name)
        if detail:
            print("      " + detail.replace("\n", "\n      "))


def git(directory, *arguments):
    return subprocess.run(["git", "-C", str(directory), *arguments], capture_output=True,
                          text=True, check=True, env=GIT_ENVIRONMENT).stdout.strip()


def commit_file(repository, path, text, message):
    (repository / path).parent.mkdir(parents=True, exist_ok=True)
    (repository / path).write_text(text)
    git(repository, "add", path)
    git(repository, "commit", "-q", "-m", message)
    return git(repository, "rev-parse", "HEAD")


def git_failing_on_line_log_directory(scratch):
    """A directory holding a git that fails `git log -L` as git does on a bad range,
    and runs the real git for every other command."""
    directory = scratch / "git-failing-on-line-log"
    directory.mkdir(exist_ok=True)
    (directory / "git").write_text(GIT_FAILING_ON_LINE_LOG.replace("REAL_GIT", shutil.which("git")))
    (directory / "git").chmod(0o755)
    return directory


def run_program(scratch, helpers, specs, *extra, gh_routes=None, token=TEST_TOKEN,
                first_path_directory=None):
    specs_file = scratch / "brief-specs.json"
    specs_file.write_text(json.dumps(specs))
    stand_in_directory = scratch / "gh-stand-in"
    stand_in_directory.mkdir(exist_ok=True)
    (stand_in_directory / "gh").write_text(GH_STAND_IN)
    (stand_in_directory / "gh").chmod(0o755)
    (scratch / "gh-routes.json").write_text(json.dumps(QUIET_GH_ROUTES if gh_routes is None else gh_routes))
    (scratch / "gh-calls.jsonl").write_text("")
    home = scratch / "home"
    shutil.rmtree(home, ignore_errors=True)
    (home / ".config" / "nedschorus").mkdir(parents=True)
    if token is not None:
        (home / ".config" / "nedschorus" / "ned-review-merge.token").write_text(token + "\n")
    return subprocess.run(
        [sys.executable, str(PROGRAM), str(specs_file),
         "--merge-lane-worktrees-and-outputs-directory", str(helpers),
         "--merge-lane-review-worktrees-directory", str(review_worktrees_directory(helpers)),
         "--review-tools-worktree-at-main", str(scratch / "main-checkout"),
         "--brief-file", str(scratch / "standing.md"),
         "--ned-box-reviewer-brief-environment-addendum-file", str(scratch / "addendum.md"),
         "--merge-lane-pull-request-reviewer-scratch-directories-parent-directory", str(scratch / "reviewer-scratch"), *extra],
        capture_output=True, text=True,
        env={**GIT_ENVIRONMENT, "GIT_DIR": str(scratch / "no-such-git-directory"), "HOME": str(home),
             "PATH": os.pathsep.join(
                 [str(directory) for directory in (first_path_directory, stand_in_directory)
                  if directory is not None] + [os.environ["PATH"]]),
             "BRIEF_COMPOSE_TEST_GH_ROUTES": str(scratch / "gh-routes.json"),
             "BRIEF_COMPOSE_TEST_GH_CALL_LOG": str(scratch / "gh-calls.jsonl")})


def gh_calls(scratch):
    return [json.loads(line) for line in (scratch / "gh-calls.jsonl").read_text().splitlines()]


ISSUE_THIS_PULL_REQUEST_CLOSES = "https://github.com/nedschorus/nedschorus/issues/50"
MERGED_PULL_REQUESTS = [
    {"number": 101, "title": "Kept a workaround", "url": "https://github.com/nedschorus/nedschorus/pull/101",
     "body": f"Fixes a hang.\r\n\r\n- #root_cause_not_fixed the harness drops it. #follow_up {ISSUE_THIS_PULL_REQUEST_CLOSES}\r\n"},
    {"number": 102, "title": "Kept another", "url": "https://github.com/nedschorus/nedschorus/pull/102",
     "body": "**Root cause not fixed:** the cause stays until https://github.com/NedSchorus/nedschorus/pull/7 merges."},
    {"number": 103, "title": "Links elsewhere", "url": "https://github.com/nedschorus/nedschorus/pull/103",
     "body": "#root_cause_not_fixed it stays. #follow_up https://github.com/nedschorus/nedschorus/issues/51"},
    {"number": 104, "title": "A root-cause line", "url": "https://github.com/nedschorus/nedschorus/pull/104",
     "body": f"#root_cause the hook read a file. See {ISSUE_THIS_PULL_REQUEST_CLOSES}"},
    {"number": 105, "title": "Another repository's issue 50", "url": "https://github.com/nedschorus/nedschorus/pull/105",
     "body": "#root_cause_not_fixed it stays. #follow_up https://github.com/cli/cli/issues/50"},
    {"number": 106, "title": "No description", "url": "https://github.com/nedschorus/nedschorus/pull/106",
     "body": None},
]
FOLLOW_UP_GH_ROUTES = {
    "closing": closing_route([
        {"number": 50, "url": ISSUE_THIS_PULL_REQUEST_CLOSES,
         "repository": {"name": "nedschorus", "owner": {"login": "nedschorus"}}}]),
    "merged": {"stdout": json.dumps(MERGED_PULL_REQUESTS)}}


def main():
    # Resolved, because macOS's mkdtemp path is a symlink and the program resolves its paths.
    scratch = Path(tempfile.mkdtemp(prefix="merge-lane-brief-compose-test-")).resolve()
    try:
        repository = scratch / "main-checkout"
        subprocess.run(["git", "init", "-q", "-b", "main", str(repository)], check=True,
                       env=GIT_ENVIRONMENT)
        commit_file(repository, "scripts/compose-pull-request-reviewer-brief.py",
                    COMPOSER.read_text(), "composer")
        main_commit = commit_file(repository, "docs/agents/pr-reviewer-instructions.md",
                                  INSTRUCTIONS, "instructions")
        git(repository, "checkout", "-q", "-b", "topic")
        first_head = commit_file(repository, "scripts/thing.py", "one\ntwo\n", "first head")
        fix_head = commit_file(repository, "scripts/thing.py", "one\nthree\n", "fix-round")
        git(repository, "checkout", "-q", "main")
        helpers = scratch / "merge-helpers"
        git(repository, "worktree", "add", "-q", "--detach",
            str(review_worktrees_directory(helpers) / "pr7-merged"), fix_head)
        merged_tree = git(review_worktrees_directory(helpers) / "pr7-merged", "rev-parse", "HEAD^{tree}")
        (scratch / "standing.md").write_text(STANDING_TEXT)
        (scratch / "addendum.md").write_text(ADDENDUM)

        first_round = {"tag": "7", "number": 7, "title": "A title", "author": "an author",
                       "head": first_head, "main": main_commit,
                       "tests": ["scripts/thing-test.py"], "hazards": "Check the thing."}
        completed = run_program(scratch, helpers, [first_round])
        brief_file = helpers / "briefs" / "brief-7-mac-claude.md"
        expected = (
            "Review pull request 7.\nThe reviewing instructions.\nEnd of standing text.\n\n"
            "The ned-box addendum.\n\n"
            "## This pull request (facts from merge-lane-2)\n\n"
            f"- Pull request: #7, \"A title\", author `an author`.\n"
            f"- nc-head-commit: `{first_head}`.\n"
            f"- Merge base: `{main_commit}`.\n"
            f"- Main's tip when commissioned: `{main_commit}`.\n"
            f"- Merged tree (head merged onto main by merge-lane-2): `{merged_tree}`.\n"
            f"- Your scratch directory: `{scratch / 'reviewer-scratch' / 'rv7'}`. "
            "Use it as `<your scratchpad>`.\n"
            "- Files the change touches: `scripts/thing.py` (+2/-0).\n"
            "- Test files the change touches: `scripts/thing-test.py`.\n"
            "- First round: no nc-head-commit was reviewed before.\n"
            "- Other open pull requests changing the same files: none.\n"
            "- Merged pull requests whose not-fixed line links to an issue this pull request "
            "closes, or to this pull request: none.\n"
            "- Hazards: Check the thing.\n"
            "- The author's description of the pull request, quoted below. It is what the "
            "author claims; check each claim against the repository yourself, including its "
            "`#root_cause`, `#root_cause_not_fixed` or `#no_defect_fixed` line.\n\n"
            "> The author's description.\n>\n> #no_defect_fixed\n")
        detail = f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}"
        brief = brief_file.read_text() if brief_file.exists() else ""
        check("a first-round brief is the standing text, the addendum and the facts",
              completed.returncode == 0 and brief == expected,
              detail + "\n--- brief ---\n" + brief)
        check("the reviewer's scratch directory is made in the reviewer scratch parent, "
              "not in the worktrees and outputs directory",
              (scratch / "reviewer-scratch" / "rv7").is_dir()
              and not (helpers / "rv7").exists(), detail)
        check("the output names the brief and its word count",
              completed.stdout == f"composed {brief_file} {len(expected.split())} words\n",
              detail)

        calls = gh_calls(scratch)
        check("gh is asked for this pull request's closing issues and description in one call, "
              "and for the merged pull requests, as the merge account",
              [call["argv"][:3] for call in calls] == [["pr", "view", "7"], ["pr", "list", "--repo"]]
              and calls[0]["argv"][-2:] == ["--json", "closingIssuesReferences,body"]
              and "merged" in calls[1]["argv"] and "body" in calls[1]["argv"][-1]
              and all(call["gh_token"] == TEST_TOKEN for call in calls), json.dumps(calls))

        completed = run_program(scratch, helpers, [first_round, {**first_round, "tag": "7b"}],
                                gh_routes=FOLLOW_UP_GH_ROUTES)
        brief_file = helpers / "briefs" / "brief-7-mac-claude.md"
        brief = brief_file.read_text() if brief_file.exists() else ""
        check("the brief lists the merged pull requests whose not-fixed line links to an issue "
              "this pull request closes or to this pull request, in either form",
              completed.returncode == 0
              and ("- Merged pull requests whose not-fixed line links to an issue this pull "
                   "request closes, or to this pull request: #101 \"Kept a workaround\" "
                   "(https://github.com/nedschorus/nedschorus/pull/101), whose line is "
                   f"`- #root_cause_not_fixed the harness drops it. #follow_up {ISSUE_THIS_PULL_REQUEST_CLOSES}`; "
                   "#102 \"Kept another\" (https://github.com/nedschorus/nedschorus/pull/102), whose "
                   "line is `**Root cause not fixed:** the cause stays until "
                   "https://github.com/NedSchorus/nedschorus/pull/7 merges.`.\n") in brief,
              f"exit {completed.returncode}\n{completed.stderr}\n--- brief ---\n{brief}")
        check("the merged pull requests are read once for two briefs",
              [call["argv"][1] for call in gh_calls(scratch)]
              == ["view", "list", "view"],
              json.dumps(gh_calls(scratch)))

        for route, what in (("closing", "closing issues"), ("merged", "merged pull requests")):
            failing = {**QUIET_GH_ROUTES, route: {"exit": 1, "stderr": "HTTP 502: Bad Gateway\n"}}
            (helpers / "briefs" / "brief-10-mac-claude.md").unlink(missing_ok=True)
            completed = run_program(scratch, helpers, [{**first_round, "tag": "10"}], gh_routes=failing)
            check(f"gh failing on the {what} exits 1, naming gh's error, and writes no brief",
                  completed.returncode == 1 and "brief not composed: StepFailed" in completed.stderr
                  and "HTTP 502: Bad Gateway" in completed.stderr
                  and not (helpers / "briefs" / "brief-10-mac-claude.md").exists(),
                  f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")

        completed = run_program(scratch, helpers, [{**first_round, "tag": "11"}], token=None)
        check("a missing merge account token exits 1, naming the token file, and asks gh nothing",
              completed.returncode == 1
              and "brief not composed: MergeAccountTokenUnusable" in completed.stderr
              and "ned-review-merge.token" in completed.stderr and not gh_calls(scratch)
              and not (helpers / "briefs" / "brief-11-mac-claude.md").exists(),
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")

        program_spec = importlib.util.spec_from_file_location("brief_compose", PROGRAM)
        program = importlib.util.module_from_spec(program_spec)
        program_spec.loader.exec_module(program)
        log_store = Path("/home/nedlern/nedschorus-logs")
        default_parent = program.DEFAULT_MERGE_LANE_PULL_REQUEST_REVIEWER_SCRATCH_DIRECTORIES_PARENT_DIRECTORY
        check("the default reviewer scratch parent is outside the log-store, which the "
              "standing text forbids the reviewer to write to",
              default_parent != log_store and log_store not in default_parent.parents,
              str(default_parent))

        fix_round = {**first_round, "tag": "7r2", "head": fix_head,
                     "reviewed_before": first_head, "previous_reviews": "review 1",
                     "new_commits": "One new commit.", "answer": "fixed it",
                     "overlaps": "PR 9"}
        completed = run_program(scratch, helpers, [fix_round])
        brief_file = helpers / "briefs" / "brief-7r2-mac-claude.md"
        brief = brief_file.read_text() if brief_file.exists() else ""
        detail = (f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}"
                  f"\n--- brief ---\n{brief}")
        check("a fix-round brief names the nc-head-commit reviewed before and the answer",
              completed.returncode == 0
              and (f"- This nc-head-commit is a fix-round. nc-head-commit reviewed before: "
                   f"`{first_head}` (review 1). One new commit.\n") in brief
              and "- The author's answer to each finding: fixed it\n" in brief, detail)
        check("a fix-round brief counts only the new commit's changes",
              "- Files the new commit touches: `scripts/thing.py` (+1/-1).\n" in brief, detail)
        check("a fix-round brief names the whole pull request's test files and the overlaps",
              "- Test files the whole pull request touches: `scripts/thing-test.py`.\n" in brief
              and "- Other open pull requests changing the same files: PR 9.\n" in brief,
              detail)

        other_instructions = scratch / "other-instructions.md"
        other_instructions.write_text("Other instructions.\n")
        completed = run_program(scratch, helpers, [first_round],
                                "--instructions-file", str(other_instructions))
        brief = (helpers / "briefs" / "brief-7-mac-claude.md").read_text()
        check("--instructions-file replaces the review tools worktree's instructions",
              completed.returncode == 0 and "Other instructions.\n" in brief
              and INSTRUCTIONS not in brief, brief)

        git(repository, "checkout", "-q", "topic")
        git(repository, "mv", "scripts/thing.py", "scripts/thing renamed.py")
        commit_file(repository, "docs/côté notes.md", "notes\n", "rename and a non-ASCII file")
        rename_head = git(repository, "rev-parse", "HEAD")
        git(repository, "checkout", "-q", "main")
        completed = run_program(scratch, helpers, [{**fix_round, "tag": "7r3", "head": rename_head,
                                                    "reviewed_before": fix_head}])
        brief_file = helpers / "briefs" / "brief-7r3-mac-claude.md"
        brief = brief_file.read_text() if brief_file.exists() else ""
        check("a brief names a renamed file by both paths and a non-ASCII path as stored",
              completed.returncode == 0
              and ("- Files the new commit touches: `docs/côté notes.md` (+1/-0), "
                   "`scripts/thing renamed.py` (renamed from `scripts/thing.py`, +0/-0).\n")
              in brief,
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}"
              f"\n--- brief ---\n{brief}")

        completed = run_program(scratch, helpers, [{**first_round, "tag": "8", "number": 8}])
        check("a pull request with no merged worktree exits 1, writing no brief",
              completed.returncode == 1 and "brief not composed" in completed.stderr
              and not (helpers / "briefs" / "brief-8-mac-claude.md").exists(),
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")

        for body, what in (("\n", "a blank description"), (None, "no description")):
            (helpers / "briefs" / "brief-10-mac-claude.md").unlink(missing_ok=True)
            completed = run_program(scratch, helpers, [{**first_round, "tag": "10"}],
                                    gh_routes={**QUIET_GH_ROUTES, "closing": closing_route(body=body)})
            brief_file = helpers / "briefs" / "brief-10-mac-claude.md"
            brief = brief_file.read_text() if brief_file.exists() else ""
            check(f"{what} is said to be empty",
                  completed.returncode == 0
                  and brief.endswith("`#no_defect_fixed` line.\n\n(the description is empty)\n"),
                  f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}"
                  f"\n--- brief ---\n{brief}")

        completed = run_program(scratch, helpers, [{**first_round, "tag": "11"}],
                                gh_routes={**QUIET_GH_ROUTES, "closing": {
                                    "exit": 1, "stderr": "HTTP 502: bad gateway\n"}})
        check("gh failing to read the pull request exits 1, names gh's reason and says to "
              "run again once, writing no brief",
              completed.returncode == 1
              and "HTTP 502: bad gateway" in completed.stderr
              and "run this again once" in completed.stderr
              and not (helpers / "briefs" / "brief-11-mac-claude.md").exists(),
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")

        # Line 4 begins "-- ", so its deletion reads "--- four" in the patch, like a header.
        fixed_path = "scripts/fixed côté.py"
        fixed_lines = ["one", "two", "three", "-- four", "five", "six", "seven", "eight"]

        def merge_pull_request(number, *lines_and_texts):
            git(repository, "checkout", "-q", "-b", f"pr{number}", "main")
            for line, text in lines_and_texts:
                fixed_lines[line - 1] = text
            commit_file(repository, fixed_path, "\n".join(fixed_lines) + "\n", f"pull request {number}")
            git(repository, "checkout", "-q", "main")
            git(repository, "merge", "-q", "--no-ff", "-m",
                f"Merge pull request #{number} from nedschorus/pr{number}", f"pr{number}")

        commit_file(repository, fixed_path, "\n".join(fixed_lines) + "\n", "a file changed directly on main")
        merge_pull_request(201, (2, "two, fixed"), (5, "five, fixed"))
        merge_pull_request(202, (2, "two, fixed again"))
        merge_pull_request(203, (2, "two, fixed a third way"))
        merge_pull_request(204, (2, "two, by a pull request gh does not list"))
        merge_pull_request(205, (5, "five, fixed again"), (7, "seven, fixed"))
        fixed_lines[1] = "two, changed on main directly"
        history_main = commit_file(repository, fixed_path, "\n".join(fixed_lines) + "\n",
                                   "a direct change to line two")
        git(repository, "checkout", "-q", "-b", "history-topic")
        changed = fixed_lines[:1] + ["two, changed by this pull request"] + fixed_lines[2:3] \
            + ["five, changed by this pull request"] + fixed_lines[5:6] \
            + ["seven, changed by this pull request", "eight", "nine, added"]
        commit_file(repository, fixed_path, "\n".join(changed) + "\n",
                    "change lines 2, 5 and 7, delete line 4, add line 9")
        history_head = commit_file(repository, "scripts/new.py", "new\n", "a new file")
        git(repository, "checkout", "-q", "main")
        history_round = {**first_round, "tag": "7h", "head": history_head, "main": history_main}

        def merged_route(fixing_no_defect=()):
            listed = [
                {"number": 201, "title": "Fixed two and five", "url": "https://github.com/nedschorus/nedschorus/pull/201",
                 "body": "- #root_cause the reader split on spaces."},
                {"number": 202, "title": "Fixed two again", "url": "https://github.com/nedschorus/nedschorus/pull/202",
                 "body": "**Root cause:** the reader split on tabs."},
                {"number": 203, "title": "Kept a workaround", "url": "https://github.com/nedschorus/nedschorus/pull/203",
                 "body": "#root_cause_not_fixed it stays. #follow_up https://github.com/nedschorus/nedschorus/issues/51"},
                {"number": 205, "title": "Fixed five and seven", "url": "https://github.com/nedschorus/nedschorus/pull/205",
                 "body": "#root_cause seven was wrong."}]
            return {"stdout": json.dumps([
                {**merged, "body": "#no_defect_fixed"} if merged["number"] in fixing_no_defect else merged
                for merged in listed])}

        completed = run_program(scratch, helpers, [history_round],
                                gh_routes={**QUIET_GH_ROUTES, "merged": merged_route()})
        brief_file = helpers / "briefs" / "brief-7h-mac-claude.md"
        brief = brief_file.read_text() if brief_file.exists() else ""
        check("the brief names each line range that two earlier pull requests with a #root_cause "
              "line, in either form, changed, and no range that only one changed, then each of "
              "those pull requests once, after the not-fixed line's fact; it counts no direct "
              "commit, no not-fixed-only pull request and no merge gh does not list, and reads a "
              "deleted line beginning \"-- \" as a line, not a header",
              completed.returncode == 0
              and ("closes, or to this pull request: none.\n"
                   "- Line ranges at the merge base that this pull request changes and that two or "
                   "more earlier merged pull requests with a `#root_cause` line also changed, which "
                   "suggests each of those fixed a symptom, not its cause: "
                   "`scripts/fixed côté.py` lines 2-2 (#201, #202); "
                   "`scripts/fixed côté.py` lines 4-5 (#201, #205). Those pull requests: "
                   "#201 \"Fixed two and five\" (https://github.com/nedschorus/nedschorus/pull/201); "
                   "#202 \"Fixed two again\" (https://github.com/nedschorus/nedschorus/pull/202); "
                   "#205 \"Fixed five and seven\" (https://github.com/nedschorus/nedschorus/pull/205).\n"
                   "- Hazards: ") in brief,
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}\n--- brief ---\n{brief}")
        check("the line ranges are read with no more gh calls than before",
              [call["argv"][1] for call in gh_calls(scratch)] == ["view", "list"],
              json.dumps(gh_calls(scratch)))

        completed = run_program(scratch, helpers, [history_round], gh_routes={
            **QUIET_GH_ROUTES, "merged": merged_route(fixing_no_defect={202, 205})})
        brief = brief_file.read_text() if brief_file.exists() else ""
        check("line ranges each changed by only one earlier pull request with a #root_cause "
              "line give no line-range fact",
              completed.returncode == 0 and "- Hazards: " in brief and "- Line ranges" not in brief,
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}\n--- brief ---\n{brief}")

        brief_file.unlink(missing_ok=True)
        completed = run_program(scratch, helpers, [history_round],
                                first_path_directory=git_failing_on_line_log_directory(scratch))
        check("git log -L failing exits 1, naming git's error, and writes no brief",
              completed.returncode == 1 and "brief not composed: StepFailed" in completed.stderr
              and "has only 5 lines" in completed.stderr and not brief_file.exists(),
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")

        (scratch / "standing.md").write_text("A standing text with no instructions line.\n")
        completed = run_program(scratch, helpers, [{**first_round, "tag": "9"}])
        check("a composer refusal exits 1 and names the composer's reason",
              completed.returncode == 1 and "marker lines" in completed.stderr
              and not (helpers / "briefs" / "brief-9-mac-claude.md").exists(),
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    if failures:
        print(f"\n{len(failures)} case(s) failed")
        return 1
    print("\nall cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
