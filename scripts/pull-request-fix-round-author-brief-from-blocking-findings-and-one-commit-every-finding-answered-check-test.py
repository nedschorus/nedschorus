#!/usr/bin/env python3
"""Tests for pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py.

Each case runs the program in a scratch git repository with a fake `gh` first on PATH. The fake
answers from a routes file the case writes, keyed by its arguments joined with spaces, or by a
prefix of them when the key ends with "*"; it exits 1 on an unarranged call, and appends each
call's arguments to the calls file.

Run: python3 scripts/pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check-test.py
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

PROGRAM = Path(__file__).with_name(
    "pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py")
NUMBER = 7
REVIEWS = f"api --paginate repos/{{owner}}/{{repo}}/pulls/{NUMBER}/reviews --jq .[]"
ISSUE_COMMENTS = f"api --paginate repos/{{owner}}/{{repo}}/issues/{NUMBER}/comments --jq .[]"
ROUND_RECORD_POST = f"api repos/{{owner}}/{{repo}}/issues/{NUMBER}/comments -f body="
PR_VIEW = f"pr view {NUMBER} --json url,headRefOid,headRefName,body"
BRANCH = "topic-branch-of-the-pull-request"
URL = f"https://github.com/o/r/pull/{NUMBER}"
ADVISOR_SENTENCE = ("This is the pull request's third fix-round, its last before merge-lane-2 brings it to "
                    "the user: before you change anything, call the advisor with the blocking findings and "
                    "the fix you plan.")
CARRYING_OUT_USER_RULING_PARAGRAPH = (
    "When a finding asks you to change a file the instruction-file guard protects, and the fix only makes the "
    "file do what a ruling of the user's already says, the change is a user-approved-change: before each edit, "
    "write the ruling's words, quoted from the walk-minutes item or the agent-session where he gave it, with "
    "its time, into the `.walk-approved` marker file at the root of your worktree, and cite the ruling in the "
    "commit message. A change the guard's refusal lets through without a ruling, such as an obvious-error-fix, "
    "goes as that refusal says. Leave out any other change to such a file, go on with the other findings, and "
    "name that change in your report to the agent that dispatched you.")

FAKE_GH = r'''#!/usr/bin/env python3
import json, os, sys
key = " ".join(sys.argv[1:])
with open(os.environ["FAKE_GH_CALLS"], "a") as calls:
    calls.write(json.dumps(sys.argv[1:]) + "\n")
routes = json.load(open(os.environ["FAKE_GH_ROUTES"]))
key = next((pattern for pattern in routes if pattern.endswith("*") and key.startswith(pattern[:-1])), key)
if key not in routes:
    sys.stderr.write("fake gh: unarranged call %r\n" % key)
    sys.exit(1)
route = routes[key]
sys.stdout.write(route.get("stdout", ""))
sys.stderr.write(route.get("stderr", ""))
sys.exit(route.get("exit", 0))
'''

# Stands in for scripts/run-all-test-suites.py in every scratch repository's base commit. The suites that
# fail are those failing-suites.txt names in the checkout the fake sits in, so each commit decides its own;
# --only-suites-named narrows them. FAKE_RUNNER_EXIT makes it stop without a verdict. FAKE_RUNNER_NOT_RUN names
# a suite printed NOT RUN, and FAKE_RUNNER_STOPPED prints the runner's "not run to the end" line; the exit
# code stays the real runner's, 1 when a suite failed.
FAKE_SUITE_RUNNER = r'''import json, os, sys
from pathlib import Path
checkout = Path(__file__).resolve().parents[1]
arguments = sys.argv[1:]
if os.environ.get("FAKE_RUNNER_CALLS"):
    with open(os.environ["FAKE_RUNNER_CALLS"], "a") as calls:
        calls.write(json.dumps({"checkout": str(checkout), "arguments": arguments}) + "\n")
if os.environ.get("FAKE_RUNNER_EXIT"):
    print("run-all-test-suites: could not run")
    sys.exit(int(os.environ["FAKE_RUNNER_EXIT"]))
listed = checkout / "failing-suites.txt"
failing = listed.read_text().split() if listed.exists() else []
if "--only-suites-named" in arguments:
    failing = [suite for suite in failing if suite in arguments[arguments.index("--only-suites-named") + 1:]]
for suite in failing:
    print(f"FAIL {suite} exit 1 (0.1s)")
if os.environ.get("FAKE_RUNNER_STOPPED"):
    print("run-all-test-suites: not run to the end — stopped by SIGTERM.")
    sys.exit(1 if failing else 2)
print(f"{len(failing)} failed:")
for suite in failing:
    print(f"FAIL {suite} exit 1 \u2014 log /logs/{suite}.log")
not_run = os.environ.get("FAKE_RUNNER_NOT_RUN")
if not_run:
    print("1 not run, because bwrap could not build the nc-test-sandbox; each log says why and what to do:")
    print(f"NOT RUN {not_run} did not start: bwrap failed — log /logs/{not_run}.log")
print(f"SUMMARY: {len(failing)} failed")
sys.exit(1 if failing else 2 if not_run else 0)
'''

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


def commit_file(directory, name, text, message):
    (directory / name).write_text(text)
    git(directory, "add", name)
    git(directory, "commit", "-q", "-m", message)
    return git(directory, "rev-parse", "HEAD")


def scratch_repository(root):
    repository = root / "repository"
    repository.mkdir()
    git(repository, "init", "-q", "-b", "topic")
    git(repository, "config", "user.email", "test@example.invalid")
    git(repository, "config", "user.name", "test")
    (repository / ".gitignore").write_text(PROJECT_GITIGNORE.read_text())
    (repository / "scripts").mkdir()
    (repository / "scripts" / "run-all-test-suites.py").write_text(FAKE_SUITE_RUNNER)
    git(repository, "add", ".gitignore", "scripts/run-all-test-suites.py")
    base = commit_file(repository, "base.txt", "base\n", "base")
    git(repository, "branch", "main-line")
    frozen_head = commit_file(repository, "hook.py", "one\n", "topic work")
    git(repository, "checkout", "-q", "main-line")
    main_tip = commit_file(repository, "main.txt", "main\n", "main work")
    git(repository, "update-ref", "refs/remotes/origin/main", main_tip)
    git(repository, "checkout", "-q", "topic")
    return repository, base, frozen_head


def review(state="CHANGES_REQUESTED", commit_id=None, login="ned-review-merge", review_id=11,
           body="REQUEST_CHANGES\n\n**Blocking: 2**\n\nBoth inline."):
    return {"id": review_id, "user": {"login": login}, "state": state, "commit_id": commit_id,
            "html_url": f"{URL}#pullrequestreview-{review_id}", "body": body}


def comment(path, body, line=12, comment_id=1):
    return {"id": comment_id, "path": path, "line": line, "body": body,
            "html_url": f"{URL}#discussion_r{comment_id}"}


BLOCKING_COMMENTS = [
    comment("hook.py", "**Blocks.** hook.py swallows the error.", comment_id=1),
    comment("hook.py", "A non-blocking note.", comment_id=2),
    comment("test.py", "**Blocks.** no case for the timeout.", line=None, comment_id=3),
]


def gh_calls(root):
    return [json.loads(line) for line in (root / "calls.jsonl").read_text().splitlines()]


def round_record(frozen_head, review_ids, comment_id=900):
    """An issue comment as GitHub returns it, holding the record --check posts for a round with no commit."""
    return {"id": comment_id, "html_url": f"{URL}#issuecomment-{comment_id}",
            "body": f"Fix-round answered without a commit: frozen-head {frozen_head}, reviews "
                    f"{' '.join(map(str, review_ids))}.\nSomething else on the next line."}


def lines(objects):
    return "".join(json.dumps(item) + "\n" for item in objects)


def routes_for(head, reviews, comments=BLOCKING_COMMENTS, review_id=11):
    return {
        PR_VIEW: {"stdout": json.dumps({"url": URL, "headRefOid": head, "headRefName": BRANCH})},
        REVIEWS: {"stdout": lines(reviews)},
        ISSUE_COMMENTS: {"stdout": ""},
        ROUND_RECORD_POST + "*": {"stdout": "{}"},
        f"api --paginate repos/{{owner}}/{{repo}}/pulls/{NUMBER}/reviews/{review_id}/comments --jq .[]":
            {"stdout": lines(comments)},
    }


def run(root, repository, routes, *arguments, path_has_gh=True, environment_extra=None):
    bin_directory = root / "bin"
    bin_directory.mkdir(exist_ok=True)
    (bin_directory / "gh").write_text(FAKE_GH)
    (bin_directory / "gh").chmod(0o755)
    (root / "routes.json").write_text(json.dumps(routes))
    (root / "calls.jsonl").write_text("")
    environment = dict(os.environ, FAKE_GH_ROUTES=str(root / "routes.json"),
                       FAKE_GH_CALLS=str(root / "calls.jsonl"))
    git_only_directory = root / "git-only-bin"
    if not git_only_directory.exists():
        git_only_directory.mkdir()
        (git_only_directory / "git").symlink_to(shutil.which("git"))
    environment["PATH"] = (f"{bin_directory}{os.pathsep}{environment['PATH']}" if path_has_gh
                           else str(git_only_directory))
    environment.update(environment_extra or {})
    completed = subprocess.run([sys.executable, str(PROGRAM), str(NUMBER), *arguments],
                               cwd=repository, capture_output=True, text=True, env=environment,
                               timeout=120)
    return completed.returncode, completed.stdout, completed.stderr


WRITE_GUARD = Path(__file__).resolve().parents[1] / ".claude" / "guard-hooks" / "session-location-write-guard.py"
PROJECT_GITIGNORE = Path(__file__).resolve().parents[1] / ".gitignore"
ANSWERS_NAME = f"fix-round-answers-pull-request-{NUMBER}.md"


def run_write_guard(worktree, file_path, tool_name="Edit"):
    """Return the exit code of the project's write guard on an Edit or Write payload from a session in the worktree."""
    tool_input = ({"file_path": file_path, "old_string": "one", "new_string": "two"} if tool_name == "Edit"
                  else {"file_path": file_path, "content": "1. Fixed.\n"})
    payload = {"cwd": str(worktree), "tool_name": tool_name, "tool_input": tool_input}
    return subprocess.run([sys.executable, str(WRITE_GUARD)], input=json.dumps(payload),
                          capture_output=True, text=True, timeout=60).returncode


def answers_file(root, text):
    path = root / "answers.md"
    path.write_text(text)
    return str(path)


GOOD_ANSWERS = "1. Fixed: the error is raised,\n   and a case covers it.\n2. Added the timeout case.\n"


def case(name, body):
    with tempfile.TemporaryDirectory() as directory:
        # git prints resolved paths, and the Mac's temporary directory is behind the /var -> /private/var
        # symlink. Every case starts behind a symlink of its own, so ned-box meets the Mac's condition too.
        (Path(directory) / "real").mkdir()
        (Path(directory) / "behind-a-symlink").symlink_to(Path(directory) / "real")
        root = (Path(directory) / "behind-a-symlink").resolve()
        repository, base, frozen_head = scratch_repository(root)
        body(root, repository, base, frozen_head)


def brief_cases(root, repository, base, frozen_head):
    code, out, err = run(root, repository, routes_for(frozen_head, [review(commit_id=frozen_head)]))
    check("brief: exit 0 for a changes-requested review of the current head", code == 0, err)
    check("brief: names the frozen-head", f"Frozen-head: {frozen_head}" in out, out)
    check("brief: the first changes-requested review's brief does not ask for the advisor",
          ADVISOR_SENTENCE not in out and "advisor" not in out, out)
    check("brief: carries both blocking findings word for word, in order, and not the note",
          out.index("hook.py swallows") < out.index("no case for the timeout")
          and "A non-blocking note" not in out and "1. hook.py:12" in out and "2. test.py (" in out, out)
    check("brief: step 5 names the answers file at the root of the subagent's worktree",
          f"5. Write the answers file {ANSWERS_NAME} at the root of your worktree," in out, out)
    check("brief: names no absolute path, so nothing in it points into the author's checkout",
          str(root) not in out and str(repository) not in out and "/.git/" not in out, out)
    check("brief: the check command has no --answers, so it reads the file at its own worktree's root",
          f"6. Run the check: python3 scripts/{PROGRAM.name} {NUMBER} --check\n" in out
          and "--answers" not in out, out)
    check("brief: names the conflict check and then the check command, and no test run of its own, since "
          "the check runs the suites",
          out.index(f"branch-conflict-check.py --pull-request {NUMBER}") < out.index(f"{NUMBER} --check")
          and "run-all-test-suites" not in out and "Run the affected nc-test-suites" not in out
          and "Before the push, the check runs the nc-test-suites" in out, out)
    check("brief: says what to do when the check refuses and when a step fails after the push",
          "git commit --amend is allowed before the push" in out
          and "do not push again or rewrite the branch" in out, out)
    check("brief: step 3 lets a change that fails review move to its own pull request, answered by naming it",
          "should not land with the rest, you may move that change to a pull request of its own" in out
          and "entry that starts \"Moved to pull request \"" in out
          and out.index("3. Change nothing else") < out.index("Moved to pull request")
          < out.index("4. Put every change")
          and "or, for a change moved as step 3 says, the new pull request." in out
          and f"{NUMBER} --move-change-to-own-pull-request-cut-new-topic-branch <new topic branch> [<path> ...]" in out
          and f"{NUMBER} --move-change-to-own-pull-request-finish --title <title> --body-file <description file>" in out
          and f"puts you back on fix-round-pull-request-{NUMBER}-review-11." in out
          and "git switch" not in out.split("3. Change nothing else")[1].split("4. Put every change")[0], out)
    check("brief: rule 2 says a fix that carries out a user ruling in a guarded-file is a user-approved-change",
          "\n   " + CARRYING_OUT_USER_RULING_PARAGRAPH + "\n3. Change nothing else" in out
          and out.index("2. Check each finding") < out.index(CARRYING_OUT_USER_RULING_PARAGRAPH), out)
    check("brief: a conflict defers to the conflict check's report, and asks for no merge itself",
          "If it reports VERDICT: CONFLICT, do what its report says." in out
          and "merge origin/main as its report says" not in out and "merge nothing" not in out
          and "had you merge origin/main" not in out and "--after-conflict-merge" not in out, out)
    check("brief: says what to do when the push itself fails, and numbers the steps after the check on",
          "7. When it passes with a commit not yet pushed" in out and "8. If anything fails after the push" in out
          and "9. " not in out and "step 7" not in out
          and "If the push itself fails, do not retry it by force or rewrite the branch: tell "
          "merge-lane-2 with SendMessage what git printed." in out, out)

    check("brief: tells the author to dispatch the subagent in a worktree of its own",
          "subagent_type: \"fork\") with isolation: \"worktree\"" in out and "a git worktree of its own" in out, out)
    local_branch = f"fix-round-pull-request-{NUMBER}-review-11"
    check("brief: the subagent makes a local branch at the frozen-head, named for the review, and pushes HEAD to the branch",
          f"git fetch origin && git switch -C {local_branch} {frozen_head}" in out
          and f"git push origin HEAD:{BRANCH}" in out, out)
    check("brief: says who removes the worktree and its local branch, and to leave a harness-locked one",
          "   1. Run: git worktree remove <path>\n" in out
          and "the agent harness holds the lock: run step 1 again once git worktree list no longer shows" in out
          and "If git worktree list still shows it locked when you end your turn, tell the user the worktree's path and "
          "the lock reason, and go no further." in out, out)
    check("brief: the branch is deleted once, as the last step, after whichever removal command ran",
          out.count(f"git branch -D {local_branch}") == 1
          and out.index("git worktree remove --force <path>")
          < out.index(f"   2. Once the worktree is removed, run: git branch -D {local_branch}\n"), out)
    check("brief: the author's worktree lines come before the subagent's rules of the round",
          out.index("For the author: dispatch") < out.index("For the author, when the subagent has finished")
          < out.index("For the subagent, the rules of the round") < out.index("0. Make a local branch at the frozen-head"), out)
    check("brief: says to leave a worktree the harness locked, and writes out each forced removal whole",
          "the lock reason starts with \"claude agent\"" in out
          and "tell merge-lane-2 about it with SendMessage. Then run: git worktree remove --force --force <path>" in out
          and "tell merge-lane-2 about it with SendMessage. Then run: git worktree remove --force <path>\n" in out, out)
    check("brief: work to keep is copied out, and then the removal goes on, so no branch loops back to 1",
          "Copy out of the worktree any file that is work to keep, such as a fix the subagent did not push, "
          "and tell merge-lane-2 about it with SendMessage." in out
          and "read them, copy out any that is work to keep and tell merge-lane-2" in out
          and out.count("run step 1 again") == 1 and "start again at 1" not in out
          and out.count("and go no further.") == 2, out)

    worktree = root / "subagent-worktree"
    git(repository, "worktree", "add", "-q", "--detach", str(worktree), frozen_head)
    tracked = str(worktree / "hook.py")
    check("brief: before step 0, the write guard refuses the subagent's edit on a detached HEAD",
          run_write_guard(worktree, tracked) == 2)
    step_zero = next((line for line in out.splitlines() if line.startswith("0. ")), "")
    switch_command = step_zero.split(" && ", 1)[-1].split()
    subprocess.run(switch_command, cwd=worktree, check=True, capture_output=True, text=True)
    check("brief: after step 0's command, the write guard lets the subagent edit a tracked file",
          run_write_guard(worktree, tracked) == 0, " ".join(switch_command))
    answers_in_worktree = worktree / ANSWERS_NAME
    check("brief: the write guard lets the subagent Write the answers file at its worktree's root",
          run_write_guard(worktree, str(answers_in_worktree), tool_name="Write") == 0)
    answers_in_worktree.write_text(GOOD_ANSWERS)
    check_line = next((line for line in out.splitlines() if line.startswith("6. Run the check: ")), "")
    printed_arguments = check_line.split(f"{PROGRAM.name} ", 1)[-1].split()[1:]
    code, check_out, err = run(root, worktree, routes_for(frozen_head, [review(commit_id=frozen_head)]),
                               *printed_arguments)
    check("brief: the printed check command, run in the subagent's worktree, reads the answers file at its root",
          printed_arguments == ["--check"] and code == 0 and "Nothing pushed" in check_out,
          " ".join(printed_arguments) + check_out + err)
    check("brief: the author's checkout holds no answers file the subagent's check could have read",
          not (repository / ANSWERS_NAME).exists())
    git(worktree, "add", "-A")
    check("brief: git add -A in the subagent's worktree leaves the answers file out of the commit",
          git(worktree, "diff", "--cached", "--name-only") == "" and git(worktree, "status", "--porcelain") == "",
          git(worktree, "status", "--porcelain", "--ignored"))

    # A second changes-requested review of the same frozen-head, while the first brief's worktree
    # still has its branch checked out: the second brief's step 0 must work in a worktree of its own.
    code, second_out, err = run(root, repository, routes_for(
        frozen_head, [review(commit_id=frozen_head), review(commit_id=frozen_head, review_id=12)], review_id=12)
        | comments_route(11, BLOCKING_COMMENTS))
    second_step_zero = next((line for line in second_out.splitlines() if line.startswith("0. ")), "")
    second_switch = second_step_zero.split(" && ", 1)[-1].split()
    check("brief: a second changes-requested review of the same frozen-head names a different local branch",
          code == 0 and f"fix-round-pull-request-{NUMBER}-review-12" in second_step_zero, err + second_out)
    second_worktree = root / "second-subagent-worktree"
    git(repository, "worktree", "add", "-q", "--detach", str(second_worktree), frozen_head)
    first_name_again = subprocess.run(switch_command, cwd=second_worktree, capture_output=True, text=True)
    check("brief: the first round's branch name, still checked out in its worktree, cannot be reused",
          first_name_again.returncode != 0 and "already used by worktree" in first_name_again.stderr,
          first_name_again.stderr)
    second_switched = subprocess.run(second_switch, cwd=second_worktree, capture_output=True, text=True)
    check("brief: the second round's step 0 succeeds while the first round's worktree holds its branch",
          second_switched.returncode == 0, second_switched.stderr + " ".join(second_switch))
    git(repository, "worktree", "remove", "--force", str(second_worktree))
    git(repository, "branch", "-D", f"fix-round-pull-request-{NUMBER}-review-12")
    removed = subprocess.run(["git", "worktree", "remove", str(worktree)], cwd=repository,
                             capture_output=True, text=True)
    check("brief: git worktree remove, without --force, removes a worktree that holds only the answers file",
          removed.returncode == 0 and not worktree.exists(), removed.stderr)
    if worktree.exists():
        git(repository, "worktree", "remove", "--force", str(worktree))
    git(repository, "branch", "-D", local_branch)

    spaced = root / "checkout with space"
    shutil.copytree(repository, spaced)
    (spaced / ANSWERS_NAME).write_text(GOOD_ANSWERS)
    code, spaced_out, err = run(root, spaced, routes_for(frozen_head, [review(commit_id=frozen_head)]), "--check")
    check("check: reads the default answers file in a worktree whose path has a space",
          code == 0 and "Nothing pushed" in spaced_out, err + spaced_out)

    routes = routes_for(frozen_head, [review(commit_id=frozen_head)])
    routes[PR_VIEW] = {"stdout": json.dumps({"url": URL, "headRefOid": frozen_head, "headRefName": "topic$name"})}
    code, dollar_out, err = run(root, repository, routes)
    check("brief: a branch name the shell would expand is shell-quoted in the push command",
          code == 0 and "git push origin HEAD:'topic$name'" in dollar_out, err + dollar_out)

    outside = root / "not-a-checkout"
    outside.mkdir()
    code, out, err = run(root, outside, routes_for(frozen_head, [review(commit_id=frozen_head)]), "--check")
    check("check: outside a git worktree, with no --answers, refuses with exit 1, naming the worktree to use",
          code == 1 and "must run in the worktree or checkout of pull request 7's branch" in err
          and "Change to that worktree" in err and "--answers" not in err, err)

    code, out, err = run(root, repository, routes_for(
        frozen_head, [review(commit_id=frozen_head),
                      review(state="COMMENTED", login="someone-else", review_id=12)]))
    check("brief: a later review by another account does not hide merge-lane-2's", code == 0, err)

    code, out, err = run(root, repository, routes_for(
        frozen_head, [review(commit_id=frozen_head), review(state="PENDING", review_id=12)]))
    check("brief: an unsubmitted pending review by merge-lane-2's account is passed over", code == 0, err)

    code, out, err = run(root, repository, routes_for(frozen_head, [review(login="someone-else")]))
    check("brief: no review by merge-lane-2 refuses with exit 1",
          code == 1 and "no review by ned-review-merge" in err, err)

    code, out, err = run(root, repository, routes_for(
        frozen_head, [review(commit_id=frozen_head),
                      review(state="APPROVED", commit_id=frozen_head, review_id=12)]))
    check("brief: a later approval means no fix-round, exit 1",
          code == 1 and "is APPROVED, not CHANGES_REQUESTED" in err
          and "tell merge-lane-2 why not, with SendMessage" in err, err)

    reposted = dict(routes_for(frozen_head, [review(commit_id=frozen_head, body="Two blockers."),
                                             review(state="COMMENTED", commit_id=frozen_head, review_id=12,
                                                    body="REQUEST_CHANGES\n\n**Blocking: 2**\n\nNow inline.")],
                               comments=[BLOCKING_COMMENTS[1]]),
                    **comments_route(12, [BLOCKING_COMMENTS[0], BLOCKING_COMMENTS[2]]))
    code, out, err = run(root, repository, reposted)
    check("brief: blockers re-posted in a later comment-only review of the same commit are read",
          code == 0 and "Blocking findings (2)" in out and "hook.py swallows the error" in out
          and "no case for the timeout" in out and f"Frozen-head: {frozen_head}" in out, err + out)
    check("brief: names the changes-requested review and the later one",
          f"{URL}#pullrequestreview-11 and {URL}#pullrequestreview-12" in out, out)

    miscounted = dict(reposted, **{REVIEWS: {"stdout": lines([
        review(commit_id=frozen_head, body="Two blockers."),
        review(state="COMMENTED", commit_id=frozen_head, review_id=12, body="REQUEST_CHANGES\n\n**Blocking: 3**\n")])}})
    code, out, err = run(root, repository, miscounted)
    check("brief: a later review's stated count is checked against its own marked comments",
          code == 1 and "says **Blocking: 3**" in err and "2 of its own inline comments" in err
          and "change nothing and push nothing" in err
          and f"naming its changes-requested review, {URL}#pullrequestreview-11" in err, err)

    added = dict(routes_for(frozen_head, [review(commit_id=frozen_head),
                                          review(state="COMMENTED", commit_id=frozen_head, review_id=12,
                                                 body="REQUEST_CHANGES\n\n**Blocking: 1**\n\nOne more.")]),
                 **comments_route(12, [comment("run.py", "**Blocks.** run.py drops the exit code.",
                                               line=40, comment_id=4)]))
    code, out, err = run(root, repository, added)
    check("brief: a later review of the same commit that adds a blocker, with its own count, is read",
          code == 0 and "Blocking findings (3)" in out and "run.py drops the exit code" in out, err + out)

    duplicate = dict(routes_for(frozen_head, [review(commit_id=frozen_head),
                                              review(state="COMMENTED", commit_id=frozen_head, review_id=12,
                                                     body="Re-posting one.")]),
                     **comments_route(12, [dict(BLOCKING_COMMENTS[0], id=5,
                                                html_url=f"{URL}#discussion_r5")]))
    code, out, err = run(root, repository, duplicate)
    check("brief: a blocker re-posted with the same path, line and body counts once",
          code == 0 and "Blocking findings (2)" in out
          and out.count("hook.py swallows the error") == 1, err + out)

    moved = dict(routes_for(frozen_head, [review(commit_id=frozen_head),
                                          review(state="COMMENTED", commit_id=frozen_head, review_id=12,
                                                 body="Now inline.")],
                            comments=[BLOCKING_COMMENTS[1]]),
                 **comments_route(12, [BLOCKING_COMMENTS[0], BLOCKING_COMMENTS[2]]))
    code, out, err = run(root, repository, moved)
    check("brief: a changes-requested review's count with no marked comment is checked against the later ones",
          code == 0 and "Blocking findings (2)" in out, err + out)

    second_round = dict(routes_for(frozen_head, [review(commit_id=base, review_id=10),
                                                 review(commit_id=frozen_head, review_id=11)]),
                        **comments_route(10, [comment("old.py", "**Blocks.** an earlier round's finding.",
                                                      comment_id=9)]))
    code, out, err = run(root, repository, second_round)
    check("brief: with two changes-requested reviews of different commits, only the latest sets the round",
          code == 0 and f"Frozen-head: {frozen_head}" in out and "Blocking findings (2)" in out
          and "an earlier round's finding" not in out, err + out)
    check("brief: the second changes-requested review's brief does not ask for the advisor",
          code == 0 and "advisor" not in out, err + out)

    def earlier_rounds(count):
        return [review(commit_id=f"earlier-head-{review_id}", review_id=review_id)
                for review_id in range(11 - count, 11)]

    code, out, err = run(root, repository, routes_for(
        frozen_head, earlier_rounds(2) + [review(commit_id=frozen_head, review_id=11)]))
    check("brief: the third changes-requested review's brief asks for the advisor, word for word, before the findings",
          code == 0 and out.count(ADVISOR_SENTENCE) == 1
          and f"The round's reviews: {URL}#pullrequestreview-11\n\n{ADVISOR_SENTENCE}\n\n" in out
          and out.index(f"The round's reviews: {URL}#pullrequestreview-11\n\n{ADVISOR_SENTENCE}\n\n")
          < out.index("Blocking findings (2)") < out.index("For the subagent, the rules of the round"), err + out)
    code, out, err = run(root, repository, routes_for(
        frozen_head, earlier_rounds(2) + [review(commit_id=frozen_head, review_id=11),
                                          review(state="COMMENTED", commit_id=frozen_head, review_id=12,
                                                 body="Noted.")]) | comments_route(12, []))
    check("brief: a comment-only review after the third changes-requested review keeps the advisor sentence",
          code == 0 and out.count(ADVISOR_SENTENCE) == 1, err + out)
    for uncounted_state in ["COMMENTED", "DISMISSED"]:
        uncounted = review(state=uncounted_state, commit_id=base, review_id=8, body="Held for the user.")
        code, out, err = run(root, repository, routes_for(
            frozen_head, [review(commit_id=base, review_id=9), uncounted,
                          review(commit_id=frozen_head, review_id=11)]))
        check(f"brief: a {uncounted_state} review of an earlier commit does not make the second "
              "changes-requested review's brief ask for the advisor",
              code == 0 and "advisor" not in out, err + out)
        code, out, err = run(root, repository, routes_for(
            frozen_head, [review(commit_id=base, review_id=9), uncounted,
                          review(commit_id="earlier-head-10", review_id=10),
                          review(commit_id=frozen_head, review_id=11)]))
        check(f"brief: a {uncounted_state} review of an earlier commit leaves the advisor sentence "
              "on the third changes-requested review's brief",
              code == 0 and out.count(ADVISOR_SENTENCE) == 1, err + out)
    code, out, err = run(root, repository, routes_for(
        frozen_head, earlier_rounds(3) + [review(commit_id=frozen_head, review_id=11)]))
    check("brief: the fourth changes-requested review's brief does not ask for the advisor",
          code == 0 and "advisor" not in out, err + out)
    code, out, err = run(root, repository, routes_for(
        frozen_head, earlier_rounds(2) + [review(commit_id=frozen_head, review_id=11)]),
        "--check", "--answers", answers_file(root, GOOD_ANSWERS))
    check("check: the third round's check passes and prints no advisor sentence",
          code == 0 and "Nothing pushed" in out and "advisor" not in out, err + out)

    code, out, err = run(root, repository, routes_for(
        frozen_head, [review(commit_id=frozen_head),
                      review(state="COMMENTED", commit_id=base, review_id=12)]))
    check("brief: a later comment-only review of another commit means no fix-round, exit 1",
          code == 1 and f"is COMMENTED on commit {base}, not CHANGES_REQUESTED" in err, err)

    code, out, err = run(root, repository, routes_for(
        frozen_head, [review(commit_id=frozen_head),
                      review(state="COMMENTED", commit_id=frozen_head, review_id=12),
                      review(state="APPROVED", commit_id=frozen_head, review_id=13)]))
    check("brief: an approval after a comment-only review still means no fix-round, exit 1",
          code == 1 and "is APPROVED, not CHANGES_REQUESTED" in err, err)

    code, out, err = run(root, repository, routes_for(
        frozen_head, [review(state="COMMENTED", commit_id=frozen_head)]))
    check("brief: comment-only reviews with no changes-requested review mean no fix-round, exit 1",
          code == 1 and "is COMMENTED on commit" in err, err)

    code, out, err = run(root, repository, routes_for(base, [review(commit_id=frozen_head)]))
    check("brief: a head that moved past the reviewed commit refuses with exit 1",
          code == 1 and "already pushed" in err, err)

    code, out, err = run(root, repository, routes_for(
        frozen_head, [review(commit_id=frozen_head)], comments=[BLOCKING_COMMENTS[1]]))
    check("brief: a review with no **Blocks.** comment refuses with exit 1",
          code == 1 and "none of its 1 inline comments" in err, err)

    for spelling in ["**Blocks.**", "**Blocks:**", "**Blocks**", "**Blocks** (fast-read hold)",
                     "**Blocks the merge.**", "  **Blocks.**"]:
        code, out, err = run(root, repository, routes_for(
            frozen_head, [review(commit_id=frozen_head, body="REQUEST_CHANGES\n\n**Blocking: 1**\n")],
            comments=[comment("hook.py", f"{spelling} the spelling under test.")]))
        check(f"brief: a comment starting {spelling!r} is a blocking finding",
              code == 0 and "Blocking findings (1)" in out and "the spelling under test" in out, err + out)

    mixed = [comment("a.py", "**Blocks.** first.", comment_id=21),
             comment("b.py", "**Blocks.** second.", comment_id=22),
             comment("c.py", "**Blocks** (cold-read-fast-read hold on the docstring) third.", comment_id=23),
             comment("d.py", "**Blocks** (cold-read-fast-read hold on the progress line) fourth.", comment_id=24),
             comment("e.py", "Non-blocking. A note.", comment_id=25)]
    code, out, err = run(root, repository, routes_for(
        frozen_head, [review(commit_id=frozen_head, body="REQUEST_CHANGES\n\n**Blocking: 4**\n\nFour findings block.")],
        comments=mixed))
    check("brief: a review mixing **Blocks.** and **Blocks** (...) counts all four, as pull request 2145's did",
          code == 0 and "Blocking findings (4)" in out
          and all(word in out for word in ["first.", "second.", "third.", "fourth."])
          and "A note." not in out, err + out)

    for body in ["**Blocking** is not the mark.", "**Blockset** is not the mark.",
                 "**Blocks unclosed is not bold.", "Note: **Blocks.** in the middle is not the mark.",
                 "**Blocks\nacross a line** is not the mark."]:
        code, out, err = run(root, repository, routes_for(
            frozen_head, [review(commit_id=frozen_head, body="no count stated")],
            comments=[comment("hook.py", body)]))
        check(f"brief: a comment starting {body.splitlines()[0][:20]!r} is not a blocking finding",
              code == 1 and "none of its 1 inline comments starts with the bold word **Blocks**" in err, err)

    code, out, err = run(root, repository, routes_for(
        frozen_head, [review(commit_id=frozen_head, body="REQUEST_CHANGES\n\n**Blocking: 3**\n")]))
    check("brief: a stated blocking count that differs from the marked comments refuses",
          code == 1 and "says **Blocking: 3**" in err and "2 of its own inline comments" in err, err)

    code, out, err = run(root, repository, routes_for(
        frozen_head, [review(commit_id=frozen_head, body="no count stated")]))
    check("brief: a body without a stated count is accepted", code == 0, err)

    code, out, err = run(root, repository, routes_for(frozen_head, [review(commit_id=None)]))
    check("brief: a review without a commit_id fails with exit 2",
          code == 2 and "carries no commit_id" in err, err)

    routes = routes_for(frozen_head, [review(commit_id=frozen_head)])
    routes[REVIEWS] = {"exit": 1, "stderr": "HTTP 502"}
    code, out, err = run(root, repository, routes)
    check("brief: a gh failure fails with exit 2 and gh's message",
          code == 2 and "HTTP 502" in err and "only the user can log gh in" in err
          and "Otherwise, tell the user this whole message" in err, err)

    routes = routes_for(frozen_head, [review(commit_id=frozen_head)])
    routes[REVIEWS] = {"stdout": "not json\n"}
    code, out, err = run(root, repository, routes)
    check("brief: gh output that is not JSON fails with exit 2",
          code == 2 and "not JSON" in err, err)

    routes = routes_for(frozen_head, [review(commit_id=frozen_head)])
    routes[PR_VIEW] = {"stdout": json.dumps({"url": URL})}
    code, out, err = run(root, repository, routes)
    check("brief: gh pr view without headRefOid or headRefName names the whole command and both fields, exit 2",
          code == 2 and f"gh {PR_VIEW} printed JSON in which these fields are missing or empty: "
          "headRefOid, headRefName. Run " in err
          and f"Run gh {PR_VIEW} yourself: if it now prints an object with all three fields filled in, "
          f"run python3 {PROGRAM} {NUMBER} again.\n" in err
          and "This program stopped at the step named above." in err, err)

    routes = routes_for(frozen_head, [review(commit_id=frozen_head)])
    routes[PR_VIEW] = {"stdout": json.dumps({"url": URL, "headRefOid": frozen_head})}
    code, out, err = run(root, repository, routes)
    check("brief: gh pr view without headRefName names only that field, exit 2",
          code == 2 and "missing or empty: headRefName. Run " in err, err)

    for printed, expected in (("not json", f"gh {PR_VIEW} printed output that is not JSON; Python's JSON "
                                           "parser said: Expecting value"),
                              ("not json", "The output began: 'not json'"),
                              ("[1, 2]", "printed JSON that is not an object with named fields: [1, 2]")):
        routes = routes_for(frozen_head, [review(commit_id=frozen_head)])
        routes[PR_VIEW] = {"stdout": printed}
        code, out, err = run(root, repository, routes)
        check(f"brief: gh pr view printing {printed!r} fails with exit 2, saying so",
              code == 2 and expected in err, err)

    code, out, err = run(root, repository, routes_for(frozen_head, []), path_has_gh=False)
    check("brief: gh that cannot start fails with exit 2",
          code == 2 and "could not start gh" in err, err)


def check_cases(root, repository, base, frozen_head):
    reviews = [review(commit_id=frozen_head)]
    answers = answers_file(root, GOOD_ANSWERS)

    code, out, err = run(root, repository, routes_for(frozen_head, reviews),
                         "--check", "--answers", answers)
    check("check: no commit and GitHub at the frozen-head is 'nothing pushed', exit 0",
          code == 0 and "Nothing pushed" in out and "1. hook.py:12: Fixed: the error is raised, and a case "
          "covers it." in out, out + err)

    fix = commit_file(repository, "hook.py", "two\n", "fix")
    (repository / "other.txt").write_text("x\n")
    code, out, err = run(root, repository, routes_for(frozen_head, reviews),
                         "--check", "--answers", answers)
    check("check: one commit not yet pushed passes and says to push", code == 0
          and "Not pushed yet" in out and "Send merge-lane-2" not in out, out + err)
    check("check: a file the findings name is not listed", "  hook.py" not in out, out)

    code, out, err = run(root, repository, routes_for(fix, reviews), "--check", "--answers", answers)
    check("check: one pushed commit prints the message for merge-lane-2",
          code == 0 and f"New head {fix}" in out and "2. test.py: Added the timeout case." in out, out + err)

    code, out, err = run(root, repository, routes_for(base, reviews), "--check", "--answers", answers)
    check("check: GitHub's head that is neither the commit nor the frozen-head refuses",
          code == 1 and "neither the checked commit" in err, err)

    git(repository, "add", "other.txt")
    git(repository, "commit", "-q", "--amend", "--no-edit")
    amended = git(repository, "rev-parse", "HEAD")
    code, out, err = run(root, repository, routes_for(amended, reviews), "--check", "--answers", answers)
    check("check: a changed file no finding names is listed for the reviewer",
          code == 0 and "  other.txt" in out and "Files the fix commit changes that no blocking finding "
          "or nit names: other.txt" in out, out + err)

    second = commit_file(repository, "hook.py", "three\n", "second")
    code, out, err = run(root, repository, routes_for(frozen_head, reviews),
                         "--check", "--answers", answers)
    check("check: two commits refuse with exit 1, each described with one parent",
          code == 1 and "has 2 commits" in err and "squash them" in err
          and "(1 parent)" in err and "1 parents" not in err, err)

    git(repository, "reset", "-q", "--hard", frozen_head)
    git(repository, "merge", "-q", "--no-edit", "origin/main")
    merge = git(repository, "rev-parse", "HEAD")
    code, out, err = run(root, repository, routes_for(frozen_head, reviews),
                         "--check", "--answers", answers)
    check("check: a merge without --after-conflict-merge refuses", code == 1
          and "one non-merge commit" in err, err)
    code, out, err = run(root, repository, routes_for(merge, reviews),
                         "--check", "--answers", answers, "--after-conflict-merge")
    check("check: a merge of origin/main alone passes with --after-conflict-merge",
          code == 0 and f"New head {merge}" in out, out + err)
    after_merge = commit_file(repository, "hook.py", "four\n", "fix after merge")
    code, out, err = run(root, repository, routes_for(after_merge, reviews),
                         "--check", "--answers", answers, "--after-conflict-merge")
    check("check: a merge of origin/main and one commit pass with --after-conflict-merge, "
          "and main's files are not listed", code == 0 and "main.txt" not in out, out + err)
    commit_file(repository, "hook.py", "five\n", "a third commit")
    code, out, err = run(root, repository, routes_for(frozen_head, reviews),
                         "--check", "--answers", answers, "--after-conflict-merge")
    check("check: a merge and two commits refuse", code == 1 and "has 3 commits" in err, err)

    git(repository, "reset", "-q", "--hard", frozen_head)
    git(repository, "checkout", "-q", "-b", "elsewhere", base)
    stray = commit_file(repository, "stray.txt", "s\n", "not on main")
    git(repository, "checkout", "-q", "topic")
    git(repository, "merge", "-q", "--no-edit", stray)
    code, out, err = run(root, repository, routes_for(frozen_head, reviews),
                         "--check", "--answers", answers, "--after-conflict-merge")
    check("check: a merge of a commit not on origin/main refuses", code == 1
          and "not on origin/main" in err, err)

    git(repository, "update-ref", "-d", "refs/remotes/origin/main")
    code, out, err = run(root, repository, routes_for(frozen_head, reviews),
                         "--check", "--answers", answers, "--after-conflict-merge")
    check("check: a missing origin/main fails with exit 2", code == 2
          and "merge-base --is-ancestor" in err, err)

    git(repository, "reset", "-q", "--hard", base)
    rewritten = commit_file(repository, "hook.py", "rewritten\n", "rewritten")
    code, out, err = run(root, repository, routes_for(frozen_head, reviews),
                         "--check", "--answers", answers)
    check("check: a commit that does not descend from the frozen-head refuses", code == 1
          and "does not have the frozen-head" in err, err)

    missing = "0" * 40
    code, out, err = run(root, repository, routes_for(missing, [review(commit_id=missing)]),
                         "--check", "--answers", answers)
    check("check: a frozen-head not in the checkout fails with exit 2", code == 2
          and "cat-file" in err, err)

    git(repository, "reset", "-q", "--hard", frozen_head)
    for text, expected in (
            ("1. Fixed.\n", "no entry for finding 2"),
            ("1. Fixed.\n2. Fixed.\n3. Extra.\n", "an entry for finding 3, which does not exist"),
            ("1. Fixed.\n1. Again.\n2. Fixed.\n", "two entries for finding 1")):
        code, out, err = run(root, repository, routes_for(frozen_head, reviews),
                             "--check", "--answers", answers_file(root, text))
        check(f"check: answers file refused: {expected}", code == 1 and expected in err, err)

    moved_answers = answers_file(root, "1. Fixed.\n2. Moved to pull request #41, which carries the timeout change.\n")
    moved_routes = routes_for(frozen_head, reviews)
    moved_routes["pr view 41 --json number"] = {"stdout": json.dumps({"number": 41})}
    moved_routes["pr diff 41"] = {"stdout": ""}
    code, out, err = run(root, repository, moved_routes, "--check", "--answers", moved_answers)
    check("check: an entry naming an existing new pull request counts as answered",
          code == 0 and "2. test.py: Moved to pull request #41" in out, out + err)
    moved_by_url = answers_file(root, "1. Fixed.\n2. Moved to pull request https://github.com/o/r/pull/41\n")
    moved_routes["pr view https://github.com/o/r/pull/41 --json number"] = {"stdout": json.dumps({"number": 41})}
    moved_routes["pr diff https://github.com/o/r/pull/41"] = {"stdout": ""}
    code, out, err = run(root, repository, moved_routes, "--check", "--answers", moved_by_url)
    check("check: an entry naming an existing new pull request by URL counts as answered",
          code == 0 and "Nothing pushed" in out, out + err)
    # Lower case, so that an entry whose writer did not copy the prefix exactly is still checked.
    moved_answers = answers_file(root, "1. Fixed.\n2. moved to pull request #41, which carries the timeout change.\n")
    missing_routes = routes_for(frozen_head, reviews)
    missing_routes["pr view 41 --json number"] = {
        "exit": 1, "stderr": "GraphQL: Could not resolve to a PullRequest with the number of 41. "
                             "(repository.pullRequest)\n"}
    code, out, err = run(root, repository, missing_routes, "--check", "--answers", moved_answers)
    check("check: an entry naming a pull request that does not exist refuses with exit 1, naming it",
          code == 1 and "entry 2" in err and "pull request 41" in err and "no such pull request" in err
          and "open it as CLAUDE.md says" in err and "correct it so that the entry starts" in err
          and "If the change did not move after all" in err and "carries it, or" in err
          and f"The check is: python3 {PROGRAM} {NUMBER} --check --answers {moved_answers}" in err, out + err)
    failing_routes = routes_for(frozen_head, reviews)
    failing_routes["pr view 41 --json number"] = {"exit": 1, "stderr": "error connecting to api.github.com\n"}
    code, out, err = run(root, repository, failing_routes, "--check", "--answers", moved_answers)
    check("check: gh failing for another cause while checking a moved entry fails with exit 2",
          code == 2 and "error connecting" in err and "no such pull request" not in err, out + err)
    for text in ("Moved to pull request soon, once it is opened", "Moved to pull request #",
                 "Moved to pull request: #41"):
        prefix_only = answers_file(root, f"1. Fixed.\n2. {text}\n")
        code, out, err = run(root, repository, routes_for(frozen_head, reviews),
                             "--check", "--answers", prefix_only)
        check(f"check: a moved entry with no pull request number or URL refuses with exit 1: {text!r}",
              code == 1 and "entry 2" in err and "no pull request number or URL follows" in err
              and "open it as CLAUDE.md says" in err and "If the change did not move after all" in err
              and f"The check is: python3 {PROGRAM} {NUMBER} --check --answers {prefix_only}" in err,
              out + err)

    code, out, err = run(root, repository, routes_for(frozen_head, reviews),
                         "--check", "--answers", str(root / "no-such-file"))
    check("check: an unreadable answers file fails with exit 2", code == 2
          and "could not read the answers file" in err, err)

    default_answers = repository / ANSWERS_NAME
    default_answers.write_text(GOOD_ANSWERS)
    code, out, err = run(root, repository, routes_for(frozen_head, reviews), "--check")
    check("check: without --answers it reads the answers file at the checkout's root",
          code == 0 and "Nothing pushed" in out, out + err)
    check("check: the default answers file is not seen by git status",
          git(repository, "status", "--porcelain") == "", git(repository, "status", "--porcelain"))
    default_answers.unlink()
    code, out, err = run(root, repository, routes_for(frozen_head, reviews), "--check")
    check("check: a missing default answers file fails with exit 2, naming it",
          code == 2 and str(default_answers) in err, err)

    # A branch cut before .gitignore named the answers file: the fix commit picks it up with git add -A.
    git(repository, "reset", "-q", "--hard", frozen_head)
    (repository / ".gitignore").write_text("")
    git(repository, "commit", "-q", "-am", "frozen-head without the ignore line")
    unignored_head = git(repository, "rev-parse", "HEAD")
    unignored_reviews = [review(commit_id=unignored_head)]
    default_answers.write_text(GOOD_ANSWERS)
    (repository / "hook.py").write_text("fixed\n")
    git(repository, "add", "-A")
    git(repository, "commit", "-q", "-m", "fix with the answers file")
    code, out, err = run(root, repository, routes_for(unignored_head, unignored_reviews), "--check")
    check("check: a fix commit holding the answers file refuses with exit 1, naming the file",
          code == 1 and ANSWERS_NAME in err and "git rm --cached" in err, out + err)
    git(repository, "rm", "-q", "--cached", ANSWERS_NAME)
    git(repository, "commit", "-q", "--amend", "--no-edit")
    code, out, err = run(root, repository, routes_for(unignored_head, unignored_reviews), "--check")
    check("check: the same fix without the answers file passes", code == 0 and "Not pushed yet" in out,
          out + err)
    git(repository, "reset", "-q", "--hard", unignored_head)
    git(repository, "update-ref", "refs/remotes/origin/main", "main-line")
    git(repository, "merge", "-q", "--no-edit", "origin/main")
    (repository / "other-answers").mkdir()
    commit_file(repository, "other-answers/fix-round-answers-pull-request-1901.md", "1. x\n", "fix")
    code, out, err = run(root, repository, routes_for(unignored_head, unignored_reviews),
                         "--check", "--after-conflict-merge")
    check("check: after a conflict merge, any pull request's answers file in a subdirectory refuses",
          code == 1 and "other-answers/fix-round-answers-pull-request-1901.md" in err, out + err)

    git(repository, "reset", "-q", "--hard", unignored_head)
    git(repository, "merge", "-q", "--no-ff", "--no-commit", "origin/main")
    (repository / "other-answers").mkdir(exist_ok=True)
    (repository / "other-answers/fix-round-answers-pull-request-1899.md").write_text("1. x\n")
    git(repository, "add", "other-answers/fix-round-answers-pull-request-1899.md")
    git(repository, "commit", "-q", "--no-edit")
    code, out, err = run(root, repository, routes_for(unignored_head, unignored_reviews),
                         "--check", "--after-conflict-merge")
    check("check: an answers file added in the conflict merge's own commit refuses",
          code == 1 and "other-answers/fix-round-answers-pull-request-1899.md" in err, out + err)
    commit_file(repository, "hook.py", "fixed after merge\n", "fix after the merge")
    code, out, err = run(root, repository, routes_for(unignored_head, unignored_reviews),
                         "--check", "--after-conflict-merge")
    check("check: an answers file the conflict merge adds refuses when a fix commit sits on top",
          code == 1 and "other-answers/fix-round-answers-pull-request-1899.md" in err, out + err)

    git(repository, "reset", "-q", "--hard", unignored_head)
    held = commit_file(repository, "fix-round-answers-pull-request-1900.md", "1. x\n",
                       "frozen-head holding an answers file")
    git(repository, "rm", "-q", "fix-round-answers-pull-request-1900.md")
    git(repository, "commit", "-q", "-m", "fix that deletes the answers file")
    code, out, err = run(root, repository, routes_for(held, [review(commit_id=held)]), "--check")
    check("check: a fix commit that deletes an answers file the frozen-head holds passes",
          code == 0 and "Not pushed yet" in out, out + err)

    git(repository, "reset", "-q", "--hard", unignored_head)
    notes = commit_file(repository, "notes.md", "1. Fixed: the error is raised.\n2. Added the case.\n",
                        "frozen-head holding a notes file")
    git(repository, "mv", "notes.md", "fix-round-answers-pull-request-1898.md")
    git(repository, "commit", "-q", "-m", "fix that renames the notes file to an answers file")
    code, out, err = run(root, repository, routes_for(notes, [review(commit_id=notes)]), "--check")
    check("check: a fix commit that renames a file to an answers file refuses",
          code == 1 and "fix-round-answers-pull-request-1898.md" in err, out + err)
    default_answers.unlink()

    code, out, err = run(root, repository, routes_for(frozen_head, reviews),
                         "--check", "--answers", answers_file(root, GOOD_ANSWERS), "--commit", "no-such-ref")
    check("check: an unknown --commit fails with exit 2", code == 2 and "rev-parse" in err, err)
    del rewritten, second


def pull_request_2213_review(review_id, login, state, commit_id, body):
    return {"id": review_id, "user": {"login": login}, "state": state, "commit_id": commit_id,
            "html_url": f"{URL}#pullrequestreview-{review_id}", "body": body}


def pull_request_2213_comment(comment_id, path, body):
    # GitHub returns line and original_line as null for these comments, so the brief places them by path.
    return {"id": comment_id, "path": path, "line": None, "original_line": None, "body": body,
            "html_url": f"{URL}#discussion_r{comment_id}"}


def comments_route(review_id, comments):
    return {f"api --paginate repos/{{owner}}/{{repo}}/pulls/{NUMBER}/reviews/{review_id}/comments --jq .[]":
            {"stdout": lines(comments)}}


def commissioned_reviewer_cases(root, repository, base, frozen_head):
    """Pull request 2213's reviews, ids, logins, states and order as GitHub returned them, bodies shortened.

    Round 0: the commissioned reviewer (mac-claude) posts its review as a COMMENT on the frozen-head,
    then merge-lane-2 requests changes on the same commit. Round 1: after the fix commit is pushed,
    the commissioned reviewer posts on it before merge-lane-2's next review. The scratch repository's
    commits stand in for the pull request's."""
    bash_guards = ("nc-systems/general-tools/bash-guards-verdict-changes-between-two-git-refs-on-"
                   "transcript-recorded-commands-check.py")
    reviewer_round_0 = pull_request_2213_review(
        5718075290, "mac-claude", "COMMENTED", frozen_head,
        "REQUEST_CHANGES\n\n**Verdict: one blocking finding.** In the bash-guards replay check, "
        "`include_subagents=True` is the only thing that keeps subagent transcripts in step 1.")
    merge_lane_round_0 = pull_request_2213_review(
        5718084175, "ned-review-merge", "CHANGES_REQUESTED", frozen_head,
        "Changes requested by merge-lane-2.\n\nBlocking, each in its own inline comment:\n"
        f"1. The reviewer's finding at `{bash_guards}:285`.\n2. Codex: the ripgrep prefilter.\n"
        "3. Codex: the grep fallback.\n4. merge-lane-2's fast-read hold.")
    reviewer_comments = [pull_request_2213_comment(
        4428022230, bash_guards, "**Blocks.** No test covers `include_subagents=True` here.")]
    merge_lane_comments = [
        pull_request_2213_comment(4428029719, "scripts/search-user-messages-in-transcripts.py",
                                  "**Blocks.** (Codex [P2]) The prefilter intersects the selected transcripts."),
        pull_request_2213_comment(4428029724,
                                  "scripts/claude-code-session-transcript-lookup-and-text-search-common.py",
                                  "**Blocks.** (Codex [P2]) The grep fallback replaces `\\d` with `[0-9]`."),
        pull_request_2213_comment(4428029732, "scripts/search-user-messages-in-transcripts.py",
                                  "**Blocks.** (merge-lane-2's fast-read hold) Reword the summary clause."),
    ]
    round_0 = {PR_VIEW: {"stdout": json.dumps({"url": URL, "headRefOid": frozen_head, "headRefName": BRANCH})},
               REVIEWS: {"stdout": lines([reviewer_round_0, merge_lane_round_0])},
               ISSUE_COMMENTS: {"stdout": ""}, ROUND_RECORD_POST + "*": {"stdout": "{}"},
               **comments_route(5718075290, reviewer_comments),
               **comments_route(5718084175, merge_lane_comments)}
    code, out, err = run(root, repository, round_0)
    check("2213: the brief reads the commissioned reviewer's **Blocks.** comment as well as merge-lane-2's",
          code == 0 and "Blocking findings (4)" in out and "include_subagents=True" in out
          and all(text in out for text in ["selected transcripts", "grep fallback", "summary clause"]), err + out)
    check("2213: the round is set by merge-lane-2's changes-requested review, not the earlier comment",
          f"Frozen-head: {frozen_head}" in out
          and f"fix-round-pull-request-{NUMBER}-review-5718084175" in out, out)
    check("2213: the brief names merge-lane-2's review, then the commissioned reviewer's, each once",
          f"The round's reviews: {URL}#pullrequestreview-5718084175 and {URL}#pullrequestreview-5718075290\n"
          in out, out)

    four_answers = answers_file(root, GOOD_ANSWERS + "3. Fixed.\n4. Reworded.\n")
    code, out, err = run(root, repository, round_0, "--check", "--answers", four_answers)
    check("2213: the check takes an answer to the commissioned reviewer's finding",
          code == 0 and "4 findings answered" in out and f"{bash_guards}: " in out, err + out)
    code, out, err = run(root, repository, round_0, "--check", "--answers", answers_file(root, GOOD_ANSWERS
                                                                                         + "3. Fixed.\n"))
    check("2213: the check refuses three answers to four findings",
          code == 1 and "no entry for finding 4" in err, err)

    fix = commit_file(repository, "hook.py", "fixed\n", "fix-round 0")
    reviewer_round_1 = pull_request_2213_review(
        5718557027, "mac-claude", "COMMENTED", fix,
        "REQUEST_CHANGES\n\nFix-round review of 258b1a01..e1effdcb.")
    after_push = dict(round_0, **{
        PR_VIEW: {"stdout": json.dumps({"url": URL, "headRefOid": fix, "headRefName": BRANCH})},
        REVIEWS: {"stdout": lines([reviewer_round_0, merge_lane_round_0, reviewer_round_1])},
        **comments_route(5718557027, [pull_request_2213_comment(
            4428404941, "scripts/claude-code-session-transcript-lookup-and-text-search-common.py",
            "**Blocks.** `\\w` is passed to ripgrep unchanged.")])})
    four_answers = answers_file(root, GOOD_ANSWERS + "3. Fixed.\n4. Reworded.\n")
    code, out, err = run(root, repository, after_push, "--check", "--answers", four_answers)
    check("2213: after the push, the commissioned reviewer's review of the new head is not part of the round",
          code == 0 and "4 findings answered" in out and f"New head {fix}" in out
          and "passed to ripgrep" not in out, err + out)
    git(repository, "reset", "-q", "--hard", frozen_head)

    reviewer_dismissed = dict(reviewer_round_0, state="DISMISSED")
    dismissed = dict(round_0, **{REVIEWS: {"stdout": lines([reviewer_dismissed, merge_lane_round_0])}})
    code, out, err = run(root, repository, dismissed)
    check("brief: a dismissed review of the frozen-head gives no blocking finding",
          code == 0 and "Blocking findings (3)" in out and "include_subagents" not in out, err + out)

    del base


def split_review_cases(root, repository, base, frozen_head):
    """Pull request 2131's reviews, ids, logins, states and order as GitHub returned them, bodies shortened.

    merge-lane-2 requested changes on an earlier head, then on the frozen-head it posted its review
    in two changes-requested parts, 14 s apart, after the commissioned reviewer's comment-only
    review; each part holds one **Blocks.** comment. base stands in for the earlier head."""
    grid = "nc-systems/cold-read/cold-read-grid.py"
    reviews = [
        review(review_id=5721655691, commit_id=base, body="merge-lane-2: the head test run failed again."),
        review(state="COMMENTED", review_id=5722014373, commit_id=frozen_head, login="mac-claude",
               body="REQUEST_CHANGES\n\nOne blocking finding: a docstring in another program is false."),
        review(review_id=5722016079, commit_id=frozen_head,
               body="merge-lane-2's graded review of head 68002364d.\n\n**Blocking (2, each a comment of "
                    "this review, because the reviewer's own comment sits outside the diff):**"),
        review(review_id=5722016646, commit_id=frozen_head,
               body="merge-lane-2's second part of its graded review of 68002364d: blocking finding 2."),
    ]
    routes = {**routes_for(frozen_head, reviews, comments=[], review_id=5722014373),
              **comments_route(5722016079, [comment(grid, "**Blocks.** At :841-843, a cell that hangs past "
                                                          "the time limit.", line=1, comment_id=1)]),
              **comments_route(5722016646, [comment(grid, "**Blocks.** In `scripts/sanity-check-adversarial-"
                                                          "prompts.py`, the docstring.", line=1, comment_id=2)])}
    code, out, err = run(root, repository, routes)
    check("2131: the brief reads the Blocks of both changes-requested parts of merge-lane-2's review of one head",
          code == 0 and "Blocking findings (2)" in out and "hangs past the time limit" in out
          and "sanity-check-adversarial-prompts.py" in out, err + out)
    check("2131: the brief names every review of the frozen-head, the latest changes-requested part first",
          f"The round's reviews: {URL}#pullrequestreview-5722016646 and {URL}#pullrequestreview-5722014373 "
          f"and {URL}#pullrequestreview-5722016079\n" in out, out)
    check("2131: two changes-requested reviews of one head are one round, so the second head's brief "
          "does not ask for the advisor", code == 0 and "advisor" not in out, out)
    code, out, err = run(root, repository, routes, "--check", "--answers", answers_file(root, GOOD_ANSWERS))
    check("2131: the check takes answers to both parts' Blocks", code == 0 and "2 findings answered" in out,
          err + out)
    code, out, err = run(root, repository, routes, "--check", "--answers",
                         answers_file(root, "1. Fixed the time limit.\n"))
    check("2131: the check refuses an answers file with no entry for the first part's Block",
          code == 1 and "no entry for finding 2" in err, err)
    third_head = dict(routes, **{REVIEWS: {"stdout": lines(
        [review(review_id=5721600000, commit_id="earlier-head-5721600000"), *reviews])}})
    code, out, err = run(root, repository, third_head)
    check("2131: a review split in two on the third head reviewed asks for the advisor once",
          code == 0 and out.count(ADVISOR_SENTENCE) == 1, err + out)


def rounds_on_one_head_cases(root, repository, base, frozen_head):
    """Two rounds on one frozen-head, and a review that re-posts an earlier one's Blocks.

    The re-post shape is pull request 2236's: merge-lane-2's graded review with no marked comment,
    then a second changes-requested review of the same head that re-posts its Block inline; ids,
    order and logins as GitHub returned them, the stated count written as this program reads it."""
    graded = review(review_id=5721453347, commit_id=frozen_head,
                    body="REQUEST_CHANGES\n\n**Blocking: 2**\n\nmerge-lane-2's graded review; the reviewer's inline Blocks.")
    reposted = review(review_id=5721459882, commit_id=frozen_head,
                      body="merge-lane-2 reposts the 2 blocking finding(s) of its review 5721453347 as "
                           "comments of this review.")
    routes = {**routes_for(frozen_head, [graded, reposted], comments=[BLOCKING_COMMENTS[1]],
                           review_id=5721453347),
              **comments_route(5721459882, [BLOCKING_COMMENTS[0], BLOCKING_COMMENTS[2]])}
    code, out, err = run(root, repository, routes)
    check("2236: an earlier changes-requested review's stated count is checked against the later review "
          "that re-posts its Blocks", code == 0 and "Blocking findings (2)" in out, err + out)

    commissioned = review(state="COMMENTED", review_id=20, commit_id=frozen_head, login="mac-claude",
                          body="REQUEST_CHANGES")
    grading = review(review_id=21, commit_id=frozen_head,
                     body="REQUEST_CHANGES\n\n**Blocking: 1**\n\nmerge-lane-2's graded review; the reviewer's inline Block.")
    graded = {**routes_for(frozen_head, [commissioned, grading], comments=[BLOCKING_COMMENTS[0]],
                           review_id=20), **comments_route(21, [])}
    code, out, err = run(root, repository, graded)
    check("a stated count in merge-lane-2's review with no marked comment of its own is checked against "
          "the Blocks of the commissioned reviewer's review posted before it",
          code == 0 and "Blocking findings (1)" in out and "hook.py swallows the error" in out, err + out)
    overstated = dict(graded, **{REVIEWS: {"stdout": lines([commissioned, dict(
        grading, body="REQUEST_CHANGES\n\n**Blocking: 2**\n\nmerge-lane-2's graded review.")])}})
    code, out, err = run(root, repository, overstated)
    check("a stated count that the round's other reviews' Blocks do not match is refused",
          code == 1 and "says **Blocking: 2**" in err
          and "1 of the inline comments of the round's other reviews" in err, err)

    first = review(review_id=21, commit_id=frozen_head, body="Round one.")
    second = review(review_id=22, commit_id=frozen_head, body="Round two: the finding still holds.")
    reviewer = review(state="COMMENTED", review_id=20, commit_id=frozen_head, login="mac-claude",
                      body="REQUEST_CHANGES")
    second_block = [comment("run.py", "**Blocks.** run.py still drops the exit code.", line=40, comment_id=31)]
    answered = {**routes_for(frozen_head, [review(review_id=19, commit_id="earlier-head-19"),
                                           reviewer, first, second],
                             comments=second_block, review_id=22),
                **comments_route(20, []), **comments_route(21, BLOCKING_COMMENTS),
                ISSUE_COMMENTS: {"stdout": lines([round_record(frozen_head, [20, 21])])}}
    code, out, err = run(root, repository, answered)
    check("a changes-requested review after a round answered without a commit on the same head "
          "briefs only its own Blocks",
          code == 0 and "Blocking findings (1)" in out and "still drops the exit code" in out
          and "hook.py swallows" not in out
          and f"The round's reviews: {URL}#pullrequestreview-22\n" in out
          and f"fix-round-pull-request-{NUMBER}-review-22" in out, err + out)
    check("a round answered without a commit counts as a round, so the next one on the same head "
          "is the third and asks for the advisor", code == 0 and out.count(ADVISOR_SENTENCE) == 1, err + out)
    unanswered = dict(answered, **{ISSUE_COMMENTS: {"stdout": lines([round_record("f" * 40, [20, 21])])}})
    code, out, err = run(root, repository, unanswered)
    check("a record of a round on another head leaves both changes-requested reviews of this head in one round",
          code == 0 and "Blocking findings (3)" in out and "advisor" not in out, err + out)

    one_round = routes_for(frozen_head, [reviewer, first], review_id=21) | comments_route(20, [])
    code, out, err = run(root, repository, one_round, "--check", "--answers", answers_file(root, GOOD_ANSWERS))
    posts = [call for call in gh_calls(root) if "-f" in call]
    check("check: a round with no commit records on the pull request which reviews it answered",
          code == 0 and "Send merge-lane-2 this message" in out and len(posts) == 1
          and posts[0][:3] == ["api", f"repos/{{owner}}/{{repo}}/issues/{NUMBER}/comments", "-f"]
          and posts[0][3].startswith(f"body=Fix-round answered without a commit: frozen-head {frozen_head}, "
                                     "reviews 20 21.\n"), err + out + json.dumps(posts))
    recorded = dict(one_round, **{ISSUE_COMMENTS: {"stdout": lines([round_record(frozen_head, [20, 21])])}})
    del recorded[ROUND_RECORD_POST + "*"]
    code, out, err = run(root, repository, recorded, "--check", "--answers", answers_file(root, GOOD_ANSWERS))
    check("check: run again after the record is posted, it prints the message and posts no second record",
          code == 0 and "Send merge-lane-2 this message" in out, err + out)
    failing = dict(one_round, **{ROUND_RECORD_POST + "*": {"exit": 1, "stderr": "HTTP 403"}})
    code, out, err = run(root, repository, failing, "--check", "--answers", answers_file(root, GOOD_ANSWERS))
    check("check: when the record cannot be posted, it fails with exit 2 and prints no message for merge-lane-2",
          code == 2 and "HTTP 403" in err and "Send merge-lane-2" not in out, err + out)
    fix = commit_file(repository, "hook.py", "fixed\n", "fix")
    code, out, err = run(root, repository, routes_for(fix, [reviewer, first], review_id=21) | comments_route(20, []),
                         "--check", "--answers", answers_file(root, GOOD_ANSWERS))
    check("check: a round that pushed a commit posts no record",
          code == 0 and f"New head {fix}" in out
          and not any("-f" in call for call in gh_calls(root)), err + out)
    git(repository, "reset", "-q", "--hard", frozen_head)
    del base



PULL_REQUEST_2620_MAC_CLAUDE_REVIEW = {
    "id": 5779061216, "user": {"login": 'mac-claude'}, "state": 'COMMENTED',
    "commit_id": 'dc0950712c83b79f47fecd3a2d7cf750dcb99b79',
    "html_url": 'https://github.com/nedschorus/nedschorus/pull/2620#pullrequestreview-5779061216',
    "body": ('APPROVE\n'
            '\n'
            'Reviewed the whole PR at head dc0950712 (first round). Merge base e7ab8b286 is the same as `git merge-base origin/main HEAD`. Environment: Python 3.14.4 at /usr/bin/python3, on ned-box.\n'
            '\n'
            'I have two findings, both non-blocking in my judgment, posted inline: a mutant on the moved-comment read-back that survives (posting :267), and a moved comment whose text holds a `- `path:N`: ` line is read back as extra comments (posting :263). In both cases the subcommand either drops text or refuses with nothing on stdout. Neither touches the blocking count.\n'
            '\n'
            '**Verified against the repository**\n'
            '- **Blocking counting unchanged.**\n'
            "  - The fix-round's `marked()` uses `BLOCKING_MARKER_PATTERN.match` (`\\*\\*Blocks\\b[^*\\n]*\\*\\*`), so `**fix-next** `, `**fix-in-maintenance** ` and `**file-for-later** ` cannot match it.\n"
            '  - `with_finding_category_marks` still runs `fix_round.without_reposts` over the marked bodies, then counts with `fix_round.marked`. A duplicate gets the same mark, so it is still dropped.\n'
            "  - The test's REQUEST_CHANGES case still posts `**Blocking: 2**` with non-blocking comments now marked.\n"
            '  - The new case checks that no non-blocking mark matches `BLOCKING_MARKER_PATTERN`.\n'
            "- **Mark round trip.** I probed the head commit's functions directly:\n"
            '  - An inline comment and a moved comment whose path has spaces (`a b/c d.py`) and whose text has backticks, bold and a newline both read back with the right category and the full text.\n'
            '  - A path containing a colon reads back correctly.\n'
            '  - The one failure I found is the bullet-line case in finding 2.\n'
            '- **Subcommand.**\n'
            "  - It reads every page through `gh api --paginate --slurp` and flattens the pages. ned-box's gh is 2.102.0, which has `--slurp`.\n"
            '  - It leaves out replies (`in_reply_to_id`) and reads only `ned-review-merge` reviews.\n'
            '  - It prints a restated finding once; the key is (category, path, text).\n'
            '  - Refusals and failures go to stderr only (main :1061-1071), and the tests assert `out == ""`.\n'
            "- **Hook load.** The hook (`...user-prompt-submit-hook.py:52`) loads the follow-up program. That program's top level does not load the posting program: `load_script_beside_this_one(POSTING_PROGRAM_FILE_NAME)` runs only inside the subcommand function. Checked by reading.\n"
            "- **Read-back through the hook's parser.** It checks the block against the hook's request-line pattern, its finding-line pattern and 1..n numbering, so it is not a tautology. But argparse supplies an int and the text is flattened with `str.split()`, which splits on every character `splitlines` breaks on. So today only a path holding a line-break character could trip it. Its value is catching drift in the parser.\n"
            '- `#no_defect_fixed` is right: the change adds behaviour and fixes no defect on main.\n'
            '\n'
            '**Callers and readers** (each `git grep`ped at head):\n'
            "- `with_blocking_marks`: no callers remain. Its only caller, the posting program's main :408, now calls `with_finding_category_marks`.\n"
            "- Readers of merge-lane-2's inline comment bodies:\n"
            "  - The fix-round program's `blocking_findings` (:339-355) still works, by reading and by the round-trip test cases that call it.\n"
            '  - `scripts/merge-gate.sh:278` reads inline comments for timestamps and activity, not body marks. Still works, by reading.\n'
            '  - `scripts/pull-request-review-plan.py:835` counts inline comments per review. Still works, by reading.\n'
            '- The outside-the-diff body line format has the same text as before, and only the new reader parses it.\n'
            '- The new subcommand has no callers yet; per the description, the seat-brief sentence is held for the user.\n'
            '\n'
            '**Tests** (env -u GIT_*; PYTHONDONTWRITEBYTECODE=1 python3 -B). Both files fake gh, and every git push goes to a local origin under a mkdtemp; neither writes to nedschorus-logs or a remote.\n'
            '- Head, `scripts/merge-lane-pull-request-reviewer-review-post-and-read-back-test.py`: exit 0, 71 PASS, 0 failed, no SKIP lines.\n'
            '- Head, `scripts/pull-request-follow-up-request-after-merge-finding-answers-and-next-step-test.py`: exit 0, 175 PASS, "PASSED: 0 failed", no SKIP lines.\n'
            '- Merge base, posting test: exit 1, 24 PASS, 2 FAIL, then an AttributeError traceback (`review_comment_opening_mark_for_finding_category` is missing) stops the file.\n'
            '  - The two failures are "posted ... each other comment opened with its category in bold" (the claim that non-blocking comments get a mark) and "a finding opening with a hand-written category mark exits 2" (the refusal claim).\n'
            '  - The no-blocking-match case and the round-trip case never ran at the base.\n'
            '- Merge base, follow-up test: exit 2, 17 PASS, 1 FAIL ("--help exits 0 and names every subcommand"; the subcommand exists). The file then stops on argparse\'s SystemExit(2) inside `test_print_block`, so no print-block case ran at the base. The evidence for those cases is mutation testing.\n'
            '\n'
            '**Mutation testing.** Each mutant ran in a detached worktree at head, with `__pycache__` cleared; `git diff HEAD` showed the one intended line, and `git status --porcelain --untracked-files=no` was empty after the restore.\n'
            "- M1, posting :279, base line put back (non-blocking comments posted unmarked): killed by the posting test's post-shape case and round-trip case.\n"
            "- M2, posting :250, condition set to `False` (the reader ignores non-blocking marks): killed by the posting test's hand-written-mark case and round trip, and by 3 follow-up print-block cases.\n"
            '- M3, posting :218, `if marked:` set to `if False:`: killed by the hand-written-category-mark refusal case.\n'
            '- M4, posting :267, continuation branch disabled: **SURVIVED** in both files. It is not equivalent; see finding 1.\n'
            "- M5, follow-up :965, dedupe removed: killed by the posting test's round trip (restated finding).\n"
            '- M6, follow-up :943, approving-review refusal disabled: killed by the "refuses when merge-lane-2 has no approving review" case.\n'
            '- M7, follow-up :932, replies kept: killed by the "reads only merge-lane-2\'s reviews, leaves out replies" case.\n'
            '- M8, follow-up :952, `continue` instead of the refusal: killed by both unmarked-comment refusal cases.\n'
            '- M9, follow-up :929, account filter set to `True`: killed by 3 cases.\n'
            '- M10, follow-up :977, read-back check disabled: killed by both read-back cases.\n'
            '- M11, follow-up :965, must-fix-now kept: killed by the round trip and the "only must-fix-now prints nothing" case.\n'
            '- M12, follow-up :939, moved comments not read: killed by the round trip and the moved-unmarked refusal case.\n'
            '\n'
            '**Questions (not findings):**\n'
            '- The dedupe key leaves out the line, so two different findings with identical text on one file collapse into one.\n'
            '- Non-blocking findings from earlier changes-requested reviews are printed even if a fix-round already settled them. The docstring says this, so it is a design choice for merge-lane-2.\n'
            '\n'
            '**Not checked:**\n'
            '- Live gh against GitHub. Every run used a fake gh, so the real field shapes of `pulls/N/comments` (`pull_request_review_id`, `in_reply_to_id`, `line`/`original_line`) come from the API contract, not from observed data. A dry run of the subcommand on an already-merged PR would make this checkable.\n'
            '- Multi-page pagination is not exercised by any test, only read.\n'
            '- Hook timing was not measured; I checked the load order by reading.\n'
            '- The full test run was not run; merge-lane-2 runs it.')}
PULL_REQUEST_2620_MAC_CLAUDE_COMMENTS = [
    {"id": 4475925026, "path": 'scripts/merge-lane-pull-request-reviewer-review-post-and-read-back.py', "line": None, "original_line": None,
     "html_url": 'https://github.com/nedschorus/nedschorus/pull/2620#discussion_r4475925026',
     "body": ('Surviving mutant: the line that joins a moved comment\'s continuation lines (`elif comments: comments[-1]["body"] += "\\n" + line`) has no test.\n'
              '\n'
              '- **Mutation:** I replaced it with `elif False: pass`. Both test files still pass: posting test exit 0, follow-up test exit 0.\n'
              '- **Why it survives:** the round-trip test\'s only moved comment is the one-line `scripts/other.py:8` "Outside.". Its two-line finding is on line 2, which is inside the diff, so it is never moved into the body.\n'
              '- **The mutant is not equivalent.** My probe at head reads a two-line moved comment back with its second line. Under the mutation, a fix-next, fix-in-maintenance or file-for-later comment on a line outside the diff whose text spans more than one line would come back as its first line only. The `#follow_up_request` block would then carry a truncated finding.\n'
              '\n'
              'A round-trip case with a multi-line comment on a line outside the diff would kill this mutant.')},
    {"id": 4475925031, "path": 'scripts/merge-lane-pull-request-reviewer-review-post-and-read-back.py', "line": None, "original_line": None,
     "html_url": 'https://github.com/nedschorus/nedschorus/pull/2620#discussion_r4475925031',
     "body": ('A comment moved into the review body is read back as several comments when a continuation line of its text has the moved-comment form `- `<path>:<line>`: ...`. Reviewers often cite other places in exactly that form.\n'
              '\n'
              '**Reproduced at head:** I ran `with_finding_category_marks` then `with_outside_comments_in_body` (with no commentable lines) on one fix-in-maintenance comment on `x.py:5`, with this text:\n'
              '\n'
              '```\n'
              'Same issue in two places:\n'
              '- `y.py:12`: here too\n'
              '- `z.py:3`: and here\n'
              '```\n'
              '\n'
              '`outside_the_diff_comments_read_back_from_review_body` returns three comments:\n'
              '- `x.py:5`, fix-in-maintenance, truncated to "Same issue in two places:"\n'
              '- `y.py:12`, with no mark\n'
              '- `z.py:3`, with no mark\n'
              '\n'
              '**Effect on the subcommand:**\n'
              '- Usually it refuses, naming a comment on `y.py:12` that merge-lane-2 never wrote. stdout stays empty, so no bad block is saved.\n'
              '- If such a continuation line itself starts with a category mark after the `: `, the subcommand prints an extra finding that merge-lane-2 never made.\n'
              '\n'
              "The moved-comment line format needs a delimiter that a comment's own text cannot reproduce, on the write side (`OUTSIDE_THE_DIFF_LINE_FORMAT`, :111) or the read side.")}]
PULL_REQUEST_2620_MERGE_LANE_2_REVIEW = {
    "id": 5779070233, "user": {"login": 'ned-review-merge'}, "state": 'CHANGES_REQUESTED',
    "commit_id": 'dc0950712c83b79f47fecd3a2d7cf750dcb99b79',
    "html_url": 'https://github.com/nedschorus/nedschorus/pull/2620#pullrequestreview-5779070233',
    "body": ('REQUEST_CHANGES\n'
            '\n'
            '**Blocking: 1**\n'
            '\n'
            'merge-lane-2 review of head dc0950712c83b79f47fecd3a2d7cf750dcb99b79 (round 1), full tier. An independent fresh Claude reviewer (mac-claude, review above) and the Codex review cell (gpt-6.1-sol, built-in review from merge base e7ab8b28) both reviewed it; merge-lane-2 graded their findings and added none of its own.\n'
            '\n'
            '**Checked**\n'
            '- Head test run on the merged tree 2ce6ced682f8: 59 passed, 0 failed.\n'
            '- mac-claude verified, against the repository, that blocking counting is unchanged (no category mark matches BLOCKING_MARKER_PATTERN; without_reposts and marked still applied), that the hook does not load the posting program, and that refusals go to stderr only; it ran 12 mutants, 11 killed.\n'
            '- Fast reads of the 7 changed messages (records under nedlern@ned-box:/home/nedlern/nedschorus-logs/cold-read-records/, the 2026-11-04 and 2026-11-04-2 records of the ids in the review plan): no misreading, so no hold. Set aside as coming from reading a message apart from its output: every struggle with an unexpanded {placeholder}, and the whole read of the block-printing line (it is the block itself).\n'
            '\n'
            "**Blocking (1)**, inline at posting :263, raised by both Codex (P2) and mac-claude, reproduced by mac-claude at head: a comment moved into the review body whose text has a continuation line of the form `- `<path>:<line>`: ...` is read back as several comments. When those lines carry a category mark, the subcommand prints a block with a truncated finding and a finding merge-lane-2 never made, and reports success. Graded must-fix-now under question 2 of merge-lane-2's grading (a result someone relies on can be wrong while the code reports success; a constructed case is enough).\n"
            '\n'
            '**Non-blocking, sent as follow-ups after the merge**\n'
            "1. fix-next, posting :267: the continuation-join line's mutant survives (inline).\n"
            '2. Fast-read struggles: posting :220 "so leave it out of the body" ("it" can be read as the finding_category key); follow-up :920 "printed no list of pages" is opaque about what was expected; follow-up :944 "not final" does not say whether the review is still running or requested changes; follow-up :954 "the merge message" is not defined and "If they hold none" has two possible antecedents; follow-up :978 gives no next step when the read-back check fails.\n'
            '\n'
            '**Questions from mac-claude, for the author to answer**\n'
            '- The dedupe key leaves out the line, so two different findings with identical text on one file collapse into one. Intended?\n'
            '- Non-blocking findings of an earlier changes-requested review are printed even when a fix-round settled them (the docstring says so).\n'
            '\n'
            "For each finding you fix, say in the fix commit's message whether the finding is one case of a wider pattern; if it is, name the pattern. Fix the other cases in this pull request when they run the same test suites or a reviewer would check them the same way; list in the commit message any you leave for a follow-up pull request. After the merge, merge-lane-2 sends you that list, as it does non-blocking findings, and you open a follow-up pull request for them or tell merge-lane-2 why not.")}
PULL_REQUEST_2620_MERGE_LANE_2_COMMENTS = [
    {"id": 4475930572, "path": 'scripts/merge-lane-pull-request-reviewer-review-post-and-read-back.py', "line": None, "original_line": None,
     "html_url": 'https://github.com/nedschorus/nedschorus/pull/2620#discussion_r4475930572',
     "body": ('**Blocks** A comment moved into the review body is read back as several comments when a continuation line of its text has the moved-comment form `- `<path>:<line>`: ...` (reproduced by mac-claude at head, also Codex P2). When such a line carries a category mark after the `: `, `print-follow-up-request-block-from-merge-lane-2-reviews` prints a truncated finding plus one merge-lane-2 never made, and exits 0. Fix: make the read-back detect this, for example by having the posting program check that the moved comments read back exactly as posted and refuse otherwise, or by a line format the text cannot reproduce; add a round-trip case with such a continuation line.')},
    {"id": 4475930574, "path": 'scripts/merge-lane-pull-request-reviewer-review-post-and-read-back.py', "line": None, "original_line": None,
     "html_url": 'https://github.com/nedschorus/nedschorus/pull/2620#discussion_r4475930574',
     "body": ('The continuation-join line `elif comments: comments[-1]["body"] += "\\n" + line` has no test: replacing it with `elif False: pass` leaves both test files passing (mac-claude, mutant M4). A round-trip case with a multi-line comment on a line outside the diff would kill it.')}]


def stated_count_position_cases(root, repository, base, frozen_head):
    """Pull request 2620's round 1, its reviews and their comments as GitHub returned them, in order.

    mac-claude's COMMENTED review quotes "**Blocking: 2**" in a code span on its body's eleventh line;
    merge-lane-2's review, posted by merge-lane-pull-request-reviewer-review-post-and-read-back.py,
    states **Blocking: 1** on its third line and marks 1 inline comment. The scratch repository's
    frozen-head stands in for the pull request's commit."""
    reviewer = dict(PULL_REQUEST_2620_MAC_CLAUDE_REVIEW, commit_id=frozen_head)
    grading = dict(PULL_REQUEST_2620_MERGE_LANE_2_REVIEW, commit_id=frozen_head)
    routes = {PR_VIEW: {"stdout": json.dumps({"url": URL, "headRefOid": frozen_head, "headRefName": BRANCH})},
              REVIEWS: {"stdout": lines([reviewer, grading])},
              ISSUE_COMMENTS: {"stdout": ""}, ROUND_RECORD_POST + "*": {"stdout": "{}"},
              **comments_route(reviewer["id"], PULL_REQUEST_2620_MAC_CLAUDE_COMMENTS),
              **comments_route(grading["id"], PULL_REQUEST_2620_MERGE_LANE_2_COMMENTS)}
    code, out, err = run(root, repository, routes)
    check("2620: a Blocking count a reviewer quotes in a code span of its review's prose is not read, so "
          "merge-lane-2's stated count, which matches its own Blocks, briefs the round",
          code == 0 and "Blocking findings (1)" in out
          and "is read back as several comments when a continuation" in out
          and "Surviving mutant" not in out, err + out)

    counted_reviewer = dict(reviewer, body="REQUEST_CHANGES\n\n**Blocking: 3**\n\nThree blockers.")
    reviewer_blocks = [comment("hook.py", "**Blocks** A finding merge-lane-2 graded fix-next.", comment_id=41)]
    lane_only = dict(routes, **{REVIEWS: {"stdout": lines([counted_reviewer, grading])},
                                **comments_route(reviewer["id"], reviewer_blocks)})
    code, out, err = run(root, repository, lane_only)
    check("a count where the review poster writes it, in a commissioned reviewer's review, is not checked, "
          "since only merge-lane-2's review grades the round",
          code == 0 and "Blocking findings (1)" in out and "graded fix-next" not in out, err + out)

    for body in ["REQUEST_CHANGES\n\nThe reviewer's test posts `**Blocking: 2**`; one finding blocks.",
                 "REQUEST_CHANGES\n\n**Blocking: 2**, both inline.",
                 "**Blocking: 2**\n\nREQUEST_CHANGES",
                 "Changes requested.\n\n**Blocking: 2**\n\nBoth inline."]:
        prose = dict(routes, **{REVIEWS: {"stdout": lines([dict(grading, body=body)])}})
        code, out, err = run(root, repository, prose)
        check(f"a Blocking count away from the line the review poster writes is not read: {body[:40]!r}",
              code == 0 and "Blocking findings (1)" in out, err + out)
    del base


def gh_timeout_case():
    specification = importlib.util.spec_from_file_location("fix_round_program", PROGRAM)
    program = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(program)

    def time_out(*arguments, **options):
        raise subprocess.TimeoutExpired(arguments[0], options.get("timeout"))

    original_run = subprocess.run
    program.subprocess.run = time_out
    try:
        program.gh(["pr", "view", "7"])
        check("gh: a call that times out raises StepFailed", False, "no exception")
    except program.StepFailed as failure:
        check("gh: a call that times out raises StepFailed naming the limit",
              "did not finish within 60 s" in str(failure), str(failure))
    finally:
        program.subprocess.run = original_run


LOCAL_BRANCH = f"fix-round-pull-request-{NUMBER}-review-11"
NEW_BRANCH = "moved-change-topic-branch"
PARTLY_MAIN = "".join(f"line {n}\n" for n in range(1, 21))
PARTLY_FROZEN = PARTLY_MAIN.replace("line 2\n", "line 2 kept\n").replace("line 18\n", "line 18 moved\n")
PARTLY_KEPT_ONLY = PARTLY_MAIN.replace("line 2\n", "line 2 kept\n")
PARTLY_MOVED_ONLY = PARTLY_MAIN.replace("line 18\n", "line 18 moved\n")
ANSWERS_TEXT = "1. Fixed.\n2. Moved.\n"
# Stands in for scripts/run-all-test-suites.py in the scratch repository.
FAKE_TESTS = 'import os, sys\nsys.exit(int(os.environ.get("FAKE_TESTS_EXIT", "0")))\n'
# A git that leaves a branch in place on git branch -D, so the program's check that the branch is gone can fail.
GIT_KEEPING_DELETED_BRANCH = r'''#!/usr/bin/env python3
import os, sys
if "branch" in sys.argv and "-D" in sys.argv:
    sys.exit(0)
os.execv(os.environ["REAL_GIT"], ["git", *sys.argv[1:]])
'''


def move_repository(root):
    """A repository with a bare origin; topic adds moved.py and changes two lines of partly.txt, and the round's
    local branch undoes moved.py and the moved line, keeping the other."""
    origin = root / "origin.git"
    git(root, "init", "-q", "--bare", "-b", "main", str(origin))
    repository = root / "move-repository"
    repository.mkdir()
    git(repository, "init", "-q", "-b", "main")
    git(repository, "config", "user.email", "test@example.invalid")
    git(repository, "config", "user.name", "test")
    git(repository, "remote", "add", "origin", str(origin))
    # No .gitignore: a branch cut before .gitignore named the answers file shows it as untracked.
    (repository / "scripts").mkdir()
    (repository / "scripts" / "run-all-test-suites.py").write_text(FAKE_TESTS)
    (repository / "partly.txt").write_text(PARTLY_MAIN)
    git(repository, "add", "-A")
    git(repository, "commit", "-q", "-m", "main")
    git(repository, "push", "-q", "origin", "main")
    git(repository, "fetch", "-q", "origin")
    git(repository, "switch", "-q", "-c", "topic")
    (repository / "moved.py").write_text("moved\n")
    (repository / "partly.txt").write_text(PARTLY_FROZEN)
    git(repository, "add", "-A")
    git(repository, "commit", "-q", "-m", "topic work")
    frozen_head = git(repository, "rev-parse", "HEAD")
    git(repository, "switch", "-q", "-c", LOCAL_BRANCH)
    git(repository, "rm", "-q", "moved.py")
    (repository / "partly.txt").write_text(PARTLY_KEPT_ONLY)
    git(repository, "add", "-A")
    git(repository, "commit", "-q", "-m", "fix-round: move the change out")
    (repository / ANSWERS_NAME).write_text(ANSWERS_TEXT)
    return repository, frozen_head


def move_routes(frozen_head, body, pull_request_create=None):
    routes = routes_for(frozen_head, [review(commit_id=frozen_head)])
    routes[f"pr create --base main --head {NEW_BRANCH} --title Move it --body-file {body}"] = (
        pull_request_create or {"stdout": "https://github.com/o/r/pull/41\n"})
    return routes


def move_cases(root, _repository, _base, _frozen_head):
    repository, frozen_head = move_repository(root)
    answers = repository / ANSWERS_NAME
    body = root / "description.md"
    body.write_text("Moves the timeout change.\n")
    routes = move_routes(frozen_head, body)
    finish = ("--move-change-to-own-pull-request-finish", "--title", "Move it", "--body-file", str(body))

    code, out, err = run(root, repository, routes, *finish)
    check("move-finish: refuses when no move is under way, exit 1", code == 1 and "No move is under way" in err, err)
    (repository / "stray.txt").write_text("stray\n")
    code, out, err = run(root, repository, routes, "--move-change-to-own-pull-request-cut-new-topic-branch", NEW_BRANCH, "moved.py")
    check("move-start: refuses a worktree with changes outside the round's commit, naming them",
          code == 1 and "stray.txt" in err and git(repository, "branch", "--show-current") == LOCAL_BRANCH, err)
    (repository / "stray.txt").unlink()
    code, out, err = run(root, repository, routes, "--move-change-to-own-pull-request-cut-new-topic-branch", NEW_BRANCH, "missing.py")
    check("move-start: refuses a path the frozen-head does not hold",
          code == 1 and f"frozen-head {frozen_head[:12]} has no file missing.py" in err, err)
    git(repository, "switch", "-q", "topic")
    code, out, err = run(root, repository, routes, "--move-change-to-own-pull-request-cut-new-topic-branch", NEW_BRANCH, "moved.py")
    check("move-start: refuses on any branch but the round's local branch",
          code == 1 and f"runs on the round's local branch {LOCAL_BRANCH}, but this worktree is on topic" in err, err)
    git(repository, "switch", "-q", LOCAL_BRANCH)
    round_commit = git(repository, "rev-parse", "HEAD")
    git(repository, "reset", "-q", "--keep", frozen_head)
    code, out, err = run(root, repository, routes, "--move-change-to-own-pull-request-cut-new-topic-branch", NEW_BRANCH, "moved.py")
    check("move-start: refuses before the round's commit exists", code == 1 and "no commit on top of the frozen-head" in err, err)
    git(repository, "reset", "-q", "--keep", round_commit)
    state_file = repository / ".git" / "fix-round-move-to-own-pull-request.json"
    code, out, err = run(root, repository, routes, "--move-change-to-own-pull-request-cut-new-topic-branch",
                         "bad..name", "moved.py")
    check("move-start: a switch git refuses fails with exit 2, leaving nothing recorded and the answers file in place",
          code == 2 and "bad..name" in err and answers.read_text() == ANSWERS_TEXT and not state_file.exists()
          and git(repository, "branch", "--show-current") == LOCAL_BRANCH, out + err)
    git(repository, "branch", NEW_BRANCH, "origin/main")
    code, out, err = run(root, repository, routes, "--move-change-to-own-pull-request-cut-new-topic-branch",
                         NEW_BRANCH, "moved.py")
    check("move-start: refuses a new topic branch that already exists, leaving the answers file in place",
          code == 1 and f"A local branch {NEW_BRANCH} already exists" in err
          and answers.read_text() == ANSWERS_TEXT and not state_file.exists()
          and git(repository, "branch", "--show-current") == LOCAL_BRANCH, out + err)
    git(repository, "branch", "-q", "-D", NEW_BRANCH)

    code, out, err = run(root, repository, routes, "--move-change-to-own-pull-request-cut-new-topic-branch", NEW_BRANCH, "moved.py")
    check("move-start: switches to the new topic branch cut from origin/main, with the named file copied whole",
          code == 0 and git(repository, "branch", "--show-current") == NEW_BRANCH
          and f"copied from the frozen-head {frozen_head[:12]}." in out
          and git(repository, "merge-base", "HEAD", "origin/main") == git(repository, "rev-parse", "origin/main")
          and (repository / "moved.py").read_text() == "moved\n"
          and (repository / "partly.txt").read_text() == PARTLY_MAIN, out + err)
    check("move-start: sets the answers file aside, out of the new topic branch's worktree", not answers.exists(), err)
    code, out, err = run(root, repository, routes, "--move-change-to-own-pull-request-cut-new-topic-branch", "another-branch")
    check("move-start: refuses a second move while one is under way", code == 1 and "already under way" in err, err)
    git(repository, "switch", "-q", "main")
    code, out, err = run(root, repository, routes, *finish)
    check("move-finish: refuses on any branch but the one --move-change-to-own-pull-request-cut-new-topic-branch made",
          code == 1 and f"runs on {NEW_BRANCH}, which --move-change-to-own-pull-request-cut-new-topic-branch made, but this worktree is on main" in err, err)
    git(repository, "switch", "-q", NEW_BRANCH)
    (repository / "partly.txt").write_text(PARTLY_MOVED_ONLY)

    answers.write_text("a new answers file\n")
    code, out, err = run(root, repository, routes, *finish)
    check("move-finish: refuses while an answers file is in the worktree, and commits nothing",
          code == 1 and "would carry it" in err
          and git(repository, "rev-parse", "HEAD") == git(repository, "rev-parse", "origin/main"), err)
    answers.unlink()
    inside = repository / "description-inside.md"
    inside.write_text("inside\n")
    code, out, err = run(root, repository, routes, "--move-change-to-own-pull-request-finish", "--title", "Move it", "--body-file", str(inside))
    check("move-finish: refuses a description file inside the worktree", code == 1 and "inside this worktree" in err, err)
    inside.unlink()
    code, out, err = run(root, repository, routes, *finish, environment_extra={"FAKE_TESTS_EXIT": "3"})
    check("move-finish: a failing test command stops it before the commit",
          code == 1 and "exited 3" in err
          and git(repository, "rev-parse", "HEAD") == git(repository, "rev-parse", "origin/main"), err)

    code, out, err = run(root, repository, routes, *finish)
    pushed = git(repository, "ls-tree", "-r", "--name-only", f"origin/{NEW_BRANCH}").split("\n")
    check("move-finish: pushes the moved change alone, without the answers file",
          code == 0 and sorted(pushed) == sorted(["moved.py", "partly.txt", "scripts/run-all-test-suites.py"])
          and git(repository, "show", f"origin/{NEW_BRANCH}:partly.txt") + "\n" == PARTLY_MOVED_ONLY, out + err)
    check("move-finish: opens the pull request with the given title and description",
          ["pr", "create", "--base", "main", "--head", NEW_BRANCH, "--title", "Move it", "--body-file", str(body)]
          in gh_calls(root), str(gh_calls(root)))
    check("move-finish: switches back to the round's branch and restores the answers file",
          git(repository, "branch", "--show-current") == LOCAL_BRANCH and answers.read_text() == ANSWERS_TEXT, out + err)
    check("move-finish: deletes the new topic branch's local branch",
          git(repository, "branch", "--list", NEW_BRANCH) == "", git(repository, "branch"))
    check("move-finish: prints the entry that answers the finding",
          "Moved to pull request https://github.com/o/r/pull/41" in out, out)

    patch = git(repository, "diff", "origin/main", f"origin/{NEW_BRANCH}") + "\n"
    check_routes = routes_for(frozen_head, [review(commit_id=frozen_head)])
    check_routes["pr view 41 --json number"] = {"stdout": json.dumps({"number": 41})}
    check_routes["pr diff 41"] = {"stdout": patch}
    moved_entry = answers_file(root, "1. Fixed.\n2. Moved to pull request #41\n")
    code, out, err = run(root, repository, check_routes, "--check", "--answers", moved_entry)
    check("check: a moved change undone here passes, with a partly moved file's kept part still here",
          code == 0 and "PASS" in out, out + err)
    corrupt_routes = dict(check_routes)
    corrupt_routes["pr view 42 --json number"] = {"stdout": json.dumps({"number": 42})}
    corrupt_routes["pr diff 42"] = {"stdout": "diff --git a/moved.py b/moved.py\n--- a/moved.py\n+++ b/moved.py\n"
                                              "@@ -1,2 +1,2 @@\nnot a patch line\n"}
    corrupt_entry = answers_file(root, "1. Fixed.\n2. Moved to pull request #42\n")
    code, out, err = run(root, repository, corrupt_routes, "--check", "--answers", corrupt_entry)
    check("check: a moved pull request's patch git cannot parse fails with exit 2, not a pass",
          code == 2 and "on pull request 42's patch" in err and "PASS" not in out, out + err)
    moved_entry = answers_file(root, "1. Fixed.\n2. Moved to pull request #41\n")
    for name, moved_kept_here, partly_text, expected in (
            ("a whole moved file", True, PARTLY_KEPT_ONLY, "moved.py"),
            ("a partly moved file's moved part", False, PARTLY_FROZEN, "partly.txt")):
        git(repository, "switch", "-q", "-c", f"not-undone-{expected}", frozen_head)
        if not moved_kept_here:
            git(repository, "rm", "-q", "moved.py")
        (repository / "partly.txt").write_text(partly_text)
        git(repository, "add", "-A")
        git(repository, "commit", "-q", "-m", "round that forgot to undo")
        code, out, err = run(root, repository, check_routes, "--check", "--answers", moved_entry)
        check(f"check: refuses, exit 1, when {name} is still here, naming the commit and the file",
              code == 1 and "would land twice" in err and expected in err
              and f"but {git(repository, 'rev-parse', 'HEAD')[:12]} still holds" in err
              and ("partly.txt" not in err if expected == "moved.py" else "moved.py" not in err), out + err)
        git(repository, "switch", "-q", LOCAL_BRANCH)

    code, out, err = run(root, repository, routes, "--move-change-to-own-pull-request-cut-new-topic-branch", "second-moved-change-topic-branch")
    check("move-start: a second move in the same worktree sets the answers file aside again",
          code == 0 and not answers.exists()
          and git(repository, "branch", "--show-current") == "second-moved-change-topic-branch", out + err)
    code, out, err = run(root, repository, routes, *finish)
    check("move-finish: refuses a new topic branch that holds no change", code == 1 and "nothing to move" in err, err)


def move_failure_after_push_cases(root, _repository, _base, _frozen_head):
    for name, extra, create, expected in (
            ("the local branch survives git branch -D", True, None, "left the branch in place"),
            ("gh pr create fails", False, {"exit": 1, "stderr": "pull request create failed\n"}, "exited 1")):
        case_root = root / name.replace(" ", "-")
        case_root.mkdir()
        repository, frozen_head = move_repository(case_root)
        body = case_root / "description.md"
        body.write_text("Moves the timeout change.\n")
        routes = move_routes(frozen_head, body, create)
        run(case_root, repository, routes, "--move-change-to-own-pull-request-cut-new-topic-branch", NEW_BRANCH, "moved.py")
        (repository / "partly.txt").write_text(PARTLY_MOVED_ONLY)
        environment_extra = None
        if extra:
            wrapper_directory = case_root / "git-keeping-deleted-branch"
            wrapper_directory.mkdir()
            (wrapper_directory / "git").write_text(GIT_KEEPING_DELETED_BRANCH)
            (wrapper_directory / "git").chmod(0o755)
            environment_extra = {"REAL_GIT": shutil.which("git"),
                                 "PATH": f"{wrapper_directory}{os.pathsep}{case_root / 'bin'}{os.pathsep}{os.environ['PATH']}"}
        code, out, err = run(case_root, repository, routes, "--move-change-to-own-pull-request-finish", "--title", "Move it",
                             "--body-file", str(body), environment_extra=environment_extra)
        check(f"move-finish: when {name} after the push, exit 2 naming what failed and every step still to do",
              code == 2 and expected in err and f"committed on {NEW_BRANCH} as" in err
              and f"git switch {LOCAL_BRANCH}" in err and f"git branch -D {NEW_BRANCH}" in err
              and "Do these by hand" in err and "resumes at the push" not in err, out + err)


def move_push_failure_cases(root, _repository, _base, _frozen_head):
    repository, frozen_head = move_repository(root)
    answers = repository / ANSWERS_NAME
    body = root / "description.md"
    body.write_text("Moves the timeout change.\n")
    routes = move_routes(frozen_head, body)
    finish = ("--move-change-to-own-pull-request-finish", "--title", "Move it", "--body-file", str(body))
    run(root, repository, routes, "--move-change-to-own-pull-request-cut-new-topic-branch", NEW_BRANCH, "moved.py")
    (repository / "partly.txt").write_text(PARTLY_MOVED_ONLY)
    origin, hidden = root / "origin.git", root / "origin-hidden.git"
    origin.rename(hidden)
    code, out, err = run(root, repository, routes, *finish)
    commit = git(repository, "rev-parse", "HEAD")
    check("move-finish: a failed push exits 2, naming the commit made and the push still to do, never 'pushed'",
          code == 2 and f"committed on {NEW_BRANCH} as {commit[:12]}" in err
          and f"push {NEW_BRANCH} with git push origin {NEW_BRANCH}" in err and "Do these by hand" in err
          and "resumes at the push" not in err
          and "is pushed" not in err and git(repository, "branch", "--show-current") == NEW_BRANCH, out + err)
    hidden.rename(origin)
    base = git(repository, "rev-parse", "origin/main")
    code, out, err = run(root, repository, routes, *finish)
    check("move-finish: a second run refuses the commit an earlier run made, naming the reset that undoes it",
          code == 1 and f"already holds commit {commit[:12]}" in err and f"git reset --soft {base}" in err
          and not git(repository, "ls-remote", "origin", NEW_BRANCH), out + err)
    git(repository, "commit", "-q", "--amend", "--no-edit", "--allow-empty")
    git(repository, "reset", "-q", "--soft", base)
    code, out, err = run(root, repository, routes, *finish)
    check("move-finish: after the reset the refusal names, even of an amended commit, a run tests, commits once and pushes",
          code == 0 and git(repository, "rev-list", "--count", f"origin/main..origin/{NEW_BRANCH}") == "1"
          and git(repository, "branch", "--show-current") == LOCAL_BRANCH and answers.read_text() == ANSWERS_TEXT
          and "Moved to pull request https://github.com/o/r/pull/41" in out, out + err)


def move_hand_commit_cases(root, _repository, _base, _frozen_head):
    repository, frozen_head = move_repository(root)
    body = root / "description.md"
    body.write_text("Moves the timeout change.\n")
    routes = move_routes(frozen_head, body)
    finish = ("--move-change-to-own-pull-request-finish", "--title", "Move it", "--body-file", str(body))
    code, out, err = run(root, repository, routes, "--move-change-to-own-pull-request-cut-new-topic-branch", NEW_BRANCH, "moved.py")
    check("move-start: says to leave the hand-made part uncommitted for the finish step",
          code == 0 and "leave it uncommitted" in out, out + err)
    base = git(repository, "rev-parse", "origin/main")
    (repository / "partly.txt").write_text(PARTLY_MOVED_ONLY)
    git(repository, "add", "-A")
    git(repository, "commit", "-q", "-m", "committed by hand")
    code, out, err = run(root, repository, routes, *finish)
    pushed = git(repository, "ls-remote", "origin", NEW_BRANCH)
    check("move-finish: refuses a commit it did not make and test, pushing nothing",
          code == 1 and "already holds commit" in err and f"git reset --soft {base}" in err and not pushed, out + err)


PRE_PUSH_CHECKED_LINES = ("pre-push: starting the selective test run on /x, which can take up to 480 seconds.",
                          "pre-push: the selective test run passed. SUMMARY: 3 passed, 0 failed, 3 total")
PRE_PUSH_SKIP_LINE = ("pre-push: the selective test run ran past its time limit, so this push goes ahead without "
                      "the selective test run: topic.")
# Worded as scripts/git-client-side-hooks-pre-push-conflict-check.py words them; neither holds a phrase the
# selective test run's skip lines share.
PRE_PUSH_CONFLICT_CHECK_SKIP_LINE = ("pre-push: branch topic was not checked for conflicts with origin/main, because "
                                     "it had not finished when the 60-second time budget ran out, and was stopped.")
PRE_PUSH_REVERT_CHECK_SKIP_LINE = ("pre-push: branch topic was not checked for files set back to a version that "
                                   "origin/main has replaced, because it could not decide: no merge base.")


def move_with_pre_push_hook(case_root, hook_lines, pull_request_create=None):
    """Runs a whole move whose pre-push hook prints hook_lines on stderr and exits 0."""
    repository, frozen_head = move_repository(case_root)
    body = case_root / "description.md"
    body.write_text("Moves the timeout change.\n")
    routes = move_routes(frozen_head, body, pull_request_create)
    hooks = case_root / "hooks"
    hooks.mkdir()
    (hooks / "pre-push").write_text("#!/bin/sh\n" + "".join(f"echo '{line}' >&2\n" for line in hook_lines) + "exit 0\n")
    (hooks / "pre-push").chmod(0o755)
    git(repository, "config", "core.hooksPath", str(hooks))
    run(case_root, repository, routes, "--move-change-to-own-pull-request-cut-new-topic-branch", NEW_BRANCH, "moved.py")
    (repository / "partly.txt").write_text(PARTLY_MOVED_ONLY)
    return run(case_root, repository, routes, "--move-change-to-own-pull-request-finish", "--title", "Move it",
               "--body-file", str(body))


def move_pre_push_hook_output_cases(root, _repository, _base, _frozen_head):
    checked_root = root / "checked"
    checked_root.mkdir()
    code, out, err = move_with_pre_push_hook(checked_root, PRE_PUSH_CHECKED_LINES)
    check("move-finish: when the pre-push hook checks the push and prints its start and pass lines, exit 0 with "
          "the success line, naming the answers file the entry goes in, and the hook's lines labelled after it",
          code == 0 and "Moved to https://github.com/o/r/pull/41" in out
          and f"in the answers file, {(checked_root / 'move-repository').resolve() / ANSWERS_NAME}, with an entry" in out
          and "<n>. Moved to pull request https://github.com/o/r/pull/41" in out
          and "printed the lines below on stderr during the push" in out
          and all(line in out for line in PRE_PUSH_CHECKED_LINES), out + err)
    for name, lines in (("selective-run-skip", (PRE_PUSH_SKIP_LINE,)),
                        ("conflict-check-skip", (PRE_PUSH_CONFLICT_CHECK_SKIP_LINE, PRE_PUSH_CHECKED_LINES[1])),
                        ("revert-check-skip", (PRE_PUSH_REVERT_CHECK_SKIP_LINE,))):
        case_root = root / name
        case_root.mkdir()
        code, out, err = move_with_pre_push_hook(case_root, lines)
        check(f"move-finish ({name}): when the pre-push hook lets the push through after skipping a check, exit 0 "
              "with the success line and every line the hook printed, labelled, after it",
              code == 0 and "Moved to https://github.com/o/r/pull/41" in out
              and "printed the lines below on stderr during the push" in out
              and all(line in out for line in lines), out + err)
    silent_root = root / "silent"
    silent_root.mkdir()
    code, out, err = move_with_pre_push_hook(silent_root, ())
    check("move-finish: when the pre-push hook prints nothing, exit 0 with the success line and no hook label",
          code == 0 and "Moved to https://github.com/o/r/pull/41" in out and "printed the lines below" not in out,
          out + err)
    failed_root = root / "skip-then-gh-fails"
    failed_root.mkdir()
    code, out, err = move_with_pre_push_hook(failed_root, (PRE_PUSH_CONFLICT_CHECK_SKIP_LINE,),
                                             {"exit": 1, "stderr": "pull request create failed\n"})
    check("move-finish: when the pre-push hook skips a check and gh pr create then fails, exit 2 with the hook's "
          "lines labelled in the failure report",
          code == 2 and "Do these by hand" in err and PRE_PUSH_CONFLICT_CHECK_SKIP_LINE in err
          and "printed the lines below on stderr during the push" in err, out + err)


def runner_calls(root):
    path = root / "runner-calls.jsonl"
    calls = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    path.write_text("")
    return calls


def suite_cases(root, repository, _base, _frozen_head):
    """At the frozen-head a-test.py fails and b-test.py passes; c-test.py does not exist there."""
    for name in ("a-test.py", "b-test.py"):
        (repository / name).write_text("suite\n")
        git(repository, "add", name)
    frozen_head = commit_file(repository, "failing-suites.txt", "a-test.py\n", "frozen-head")
    reviews = [review(commit_id=frozen_head)]
    answers = answers_file(root, GOOD_ANSWERS)
    environment = {"FAKE_RUNNER_CALLS": str(root / "runner-calls.jsonl")}

    def check_with_head(head, extra=None):
        return run(root, repository, routes_for(head, reviews), "--check", "--answers", answers,
                   environment_extra=dict(environment, **(extra or {})))

    code, out, err = check_with_head(frozen_head)
    check("suites: a round with no commit runs no suite", code == 0 and runner_calls(root) == [], out + err)

    (repository / "c-test.py").write_text("suite\n")
    git(repository, "add", "c-test.py")
    broken = commit_file(repository, "failing-suites.txt", "a-test.py b-test.py c-test.py\n", "round breaks two")
    code, out, err = check_with_head(frozen_head)
    calls = runner_calls(root)
    check("suites: a suite failing at the round's commit and passing at the frozen-head refuses, naming it, "
          "and a suite the frozen-head lacks counts as the round's",
          code == 1 and "so the round's change broke them: b-test.py, c-test.py." in err
          and "These fail at the frozen-head too, so they are not the round's doing: a-test.py." in err
          and "Not pushed yet" not in out, out + err)
    check("suites: the round's commit runs the suites the ready command runs, and the frozen-head only its "
          "failing suites the frozen-head has, recording nothing, each in a scratch worktree",
          [call["arguments"] for call in calls] == [
              ["--only-suites-whose-recorded-inputs-changed-since", "origin/main"],
              ["--leave-recorded-inputs-and-failure-history-unchanged", "--only-suites-named", "a-test.py",
               "b-test.py"]]
          and all(call["checkout"] != str(repository) for call in calls)
          and "FAIL b-test.py exit 1" in out, json.dumps(calls) + out)
    check("suites: the scratch worktrees are removed", len(git(repository, "worktree", "list").splitlines()) == 1,
          git(repository, "worktree", "list"))

    (repository / "failing-suites.txt").write_text("a-test.py\n")
    git(repository, "add", "failing-suites.txt")
    git(repository, "commit", "-q", "--amend", "--no-edit")
    fixed = git(repository, "rev-parse", "HEAD")
    code, out, err = check_with_head(frozen_head)
    check("suites: a suite failing at the frozen-head too passes the check, which names it before the push",
          code == 0 and "Not pushed yet" in out and "at the frozen-head too, so not because of this round; the "
          "message for merge-lane-2 will name them: a-test.py" in out and len(runner_calls(root)) == 2, out + err)
    code, out, err = check_with_head(frozen_head, {"FAKE_RUNNER_NOT_RUN": "b-test.py"})
    check("suites: a suite NOT RUN beside a failure the frozen-head shares fails the check with exit 2, "
          "before any push",
          code == 2 and "did not judge every suite: it printed 'NOT RUN b-test.py" in err
          and "Not pushed yet" not in out and len(git(repository, "worktree", "list").splitlines()) == 1,
          out + err)
    runner_calls(root)
    code, out, err = check_with_head(frozen_head, {"FAKE_RUNNER_STOPPED": "1"})
    check("suites: a run stopped before its end beside a failure the frozen-head shares fails the check "
          "with exit 2, before any push",
          code == 2 and "did not judge every suite: it printed 'run-all-test-suites: not run to the end" in err
          and "Not pushed yet" not in out, out + err)
    runner_calls(root)
    code, out, err = check_with_head(fixed)
    check("suites: after the push the message for merge-lane-2 names that suite, and no suite runs",
          code == 0 and "nc-test-suites that fail at the frozen-head too, so not because of this round: "
          "a-test.py." in out and runner_calls(root) == [], out + err)

    (repository / "other.txt").write_text("other\n")
    git(repository, "add", "other.txt")
    git(repository, "commit", "-q", "--amend", "--no-edit")
    unchecked = git(repository, "rev-parse", "HEAD")
    code, out, err = check_with_head(unchecked)
    check("suites: the suites recorded for one commit are not named for another",
          code == 0 and "fail at the frozen-head too" not in out, out + err)

    (repository / "failing-suites.txt").write_text("")
    git(repository, "add", "failing-suites.txt")
    git(repository, "commit", "-q", "--amend", "--no-edit")
    passing = git(repository, "rev-parse", "HEAD")
    code, out, err = check_with_head(frozen_head)
    calls = runner_calls(root)
    check("suites: when every suite passes at the round's commit, the frozen-head runs none",
          code == 0 and "Not pushed yet" in out and len(calls) == 1 and "fail at the frozen-head too" not in out,
          json.dumps(calls) + out + err)
    code, out, err = check_with_head(passing)
    check("suites: after the push, a round whose suites all passed names no suite",
          code == 0 and "fail at the frozen-head too" not in out, out + err)

    code, out, err = check_with_head(frozen_head, {"FAKE_RUNNER_EXIT": "2"})
    check("suites: a runner that stops without a verdict fails the check with exit 2, before any push",
          code == 2 and "ended with exit 2 and named no failing suite" in err and "Not pushed yet" not in out
          and len(git(repository, "worktree", "list").splitlines()) == 1, out + err)
    runner_calls(root)


def nit_cases(root, repository, base, frozen_head):
    """merge-lane-2's nits, posted opening with the nit mark beside its blocking findings, ride in the fix-round."""
    nit = comment("nit.txt", " **fix-in-maintenance, nit** nit.txt misspells the name.", line=20, comment_id=6)
    lane_comments = [*BLOCKING_COMMENTS, nit, dict(nit, id=7, html_url=f"{URL}#discussion_r7")]
    reviews = [review(commit_id=frozen_head),
               review(state="COMMENTED", commit_id=frozen_head, login="mac-claude", review_id=12, body="COMMENT")]
    routes = dict(routes_for(frozen_head, reviews, comments=lane_comments),
                  **comments_route(12, [comment("other.txt", "**fix-in-maintenance, nit** Not merge-lane-2's.",
                                                comment_id=8)]))
    code, out, err = run(root, repository, routes)
    check("nits: the brief lists merge-lane-2's nit once, numbered on from the blocking findings, and the "
          "stated count of 2 still passes beside it",
          code == 0 and "Blocking findings (2)" in out and "Nits to fix in this round too (1)" in out
          and f"3. nit.txt:20 ({URL}#discussion_r6)\n**fix-in-maintenance, nit** nit.txt misspells the name." in out
          and out.count("misspells the name") == 1
          and out.index("2. test.py (") < out.index("Nits to fix in this round too"), err + out)
    check("nits: the brief leaves out a nit-marked comment of another account's review",
          "Not merge-lane-2's" not in out, out)
    check("nits: step 3 makes the listed nits part of the round",
          "are not part of this round, apart from the nits listed above" in out, out)
    check("nits: step 2 says a nit needs no test",
          "with a test that fails without the fix; a nit needs no test." in out, out)

    code, out, err = run(root, repository, routes_for(frozen_head, [review(commit_id=frozen_head)]))
    check("nits: a round with no nit prints no nit heading", code == 0 and "Nits to fix" not in out, err + out)

    code, out, err = run(root, repository, routes_for(
        frozen_head, [review(commit_id=frozen_head, body="One nit.")], comments=[nit]))
    check("nits: a changes-requested review whose only marked comment is a nit gives no brief, as with no "
          "blocking finding",
          code == 1 and "none of its 1 inline comments starts with the bold word **Blocks**" in err
          and "Nits to fix" not in out, err + out)

    code, out, err = run(root, repository, routes, "--check", "--answers", answers_file(root, GOOD_ANSWERS))
    check("nits: --check refuses answers with no entry for the nit",
          code == 1 and "no entry for finding 3" in err and "the review has 2 blocking findings and 1 nit." in err,
          err + out)

    fix = commit_file(repository, "nit.txt", "the name\n", "fix the nit")
    code, out, err = run(root, repository, dict(routes, **{PR_VIEW: {"stdout": json.dumps(
        {"url": URL, "headRefOid": fix, "headRefName": BRANCH})}}),
        "--check", "--answers", answers_file(root, GOOD_ANSWERS + "3. Spelt the name right.\n"))
    check("nits: --check passes with an answer to the nit, lists no file the nit names, and marks the nit's "
          "line in the message for merge-lane-2",
          code == 0 and "3 findings answered" in out and "no blocking finding or nit names" not in out
          and "2. test.py: Added the timeout case.\n" in out
          and "3. nit.txt:20 (nit): Spelt the name right." in out, err + out)


REPLACED_NUMBER = 5
REPLACED_URL = f"https://github.com/o/r/pull/{REPLACED_NUMBER}"
REPLACED_FIRST_HEAD = "1" * 40
REPLACED_SECOND_HEAD = "2" * 40


def replaced_routes(head, replaced_head, replaced_reviews, replaced_comments=(), replaced_records=(),
                    description=f"Text.\n#replaces {REPLACED_URL}\n"):
    """Routes for pull request NUMBER, whose description replaces pull request REPLACED_NUMBER."""
    routes = routes_for(head, [review(commit_id=head)])
    routes[PR_VIEW] = {"stdout": json.dumps({"url": URL, "headRefOid": head, "headRefName": BRANCH,
                                             "body": description})}
    routes[f"pr view {REPLACED_NUMBER} --json url,headRefOid,headRefName,body"] = {"stdout": json.dumps(
        {"url": REPLACED_URL, "headRefOid": replaced_head, "headRefName": "old-branch", "body": "Old."})}
    routes[f"api --paginate repos/{{owner}}/{{repo}}/pulls/{REPLACED_NUMBER}/reviews --jq .[]"] = {
        "stdout": lines(replaced_reviews)}
    routes[f"api --paginate repos/{{owner}}/{{repo}}/issues/{REPLACED_NUMBER}/comments --jq .[]"] = {
        "stdout": lines(replaced_records)}
    for replaced_review in replaced_reviews:
        routes[f"api --paginate repos/{{owner}}/{{repo}}/pulls/{REPLACED_NUMBER}/reviews/{replaced_review['id']}"
               f"/comments --jq .[]"] = {"stdout": lines(replaced_comments if replaced_review["id"] == 52 else [])}
    return routes


def replaced_review(review_id, commit_id, state="CHANGES_REQUESTED"):
    return dict(review(state=state, commit_id=commit_id, review_id=review_id,
                       body="REQUEST_CHANGES\n\n**Blocking: 1**\n\nInline."),
                html_url=f"{REPLACED_URL}#pullrequestreview-{review_id}")


REPLACED_TWO_ROUNDS = [replaced_review(51, REPLACED_FIRST_HEAD), replaced_review(52, REPLACED_SECOND_HEAD)]
REPLACED_COMMENTS = [
    dict(comment("old.py", "**Blocks.** old.py loses the record.", line=30, comment_id=60),
         html_url=f"{REPLACED_URL}#discussion_r60"),
    dict(comment("old.txt", "**fix-in-maintenance, nit** old.txt misspells it.", line=4, comment_id=61),
         html_url=f"{REPLACED_URL}#discussion_r61"),
]


def replaces_cases(root, repository, base, frozen_head):
    """A #replaces line carries the replaced pull request's round count, and its never-answered round's findings."""
    code, out, err = run(root, repository, replaced_routes(
        frozen_head, REPLACED_SECOND_HEAD, REPLACED_TWO_ROUNDS, REPLACED_COMMENTS))
    carried = f", carried over from the replaced pull request's review {REPLACED_URL}#pullrequestreview-52"
    check("replaces: the replaced pull request's two rounds make this first round the third, which asks "
          "for the advisor", code == 0 and out.count(ADVISOR_SENTENCE) == 1, err + out)
    check("replaces: the never-answered round's blocking finding follows this pull request's own, marked "
          "with the replaced pull request's review, and its nit follows as finding 4",
          "Blocking findings (3)" in out
          and f"3. old.py:30{carried} ({REPLACED_URL}#discussion_r60)\n**Blocks.** old.py loses the record." in out
          and "Nits to fix in this round too (1)" in out
          and f"4. old.txt:4{carried} ({REPLACED_URL}#discussion_r61)" in out
          and out.index("2. test.py (") < out.index("3. old.py:30"), err + out)

    code, out, err = run(root, repository, replaced_routes(
        frozen_head, REPLACED_SECOND_HEAD, REPLACED_TWO_ROUNDS, REPLACED_COMMENTS),
        "--check", "--answers", answers_file(root, GOOD_ANSWERS))
    check("replaces: --check wants an answer to each carried finding too",
          code == 1 and "no entry for finding 3, 4" in err
          and "the review has 3 blocking findings and 1 nit." in err, err + out)

    code, out, err = run(root, repository, replaced_routes(
        frozen_head, "3" * 40, REPLACED_TWO_ROUNDS, REPLACED_COMMENTS))
    check("replaces: a replaced pull request whose head moved past its last round carries its rounds but "
          "no finding", code == 0 and out.count(ADVISOR_SENTENCE) == 1 and "Blocking findings (2)" in out
          and "old.py" not in out, err + out)

    code, out, err = run(root, repository, replaced_routes(
        frozen_head, REPLACED_SECOND_HEAD, REPLACED_TWO_ROUNDS, REPLACED_COMMENTS,
        replaced_records=[round_record(REPLACED_SECOND_HEAD, [52])]))
    check("replaces: a replaced round answered without a commit, as its round record says, carries no "
          "finding", code == 0 and "Blocking findings (2)" in out and "old.py" not in out, err + out)

    code, out, err = run(root, repository, replaced_routes(frozen_head, REPLACED_SECOND_HEAD, []))
    check("replaces: a replaced pull request merge-lane-2 never reviewed adds no round and no finding",
          code == 0 and ADVISOR_SENTENCE not in out and "Blocking findings (2)" in out, err + out)

    routes = replaced_routes(frozen_head, REPLACED_SECOND_HEAD, [],
                             description=f"#replaces {REPLACED_URL}\n#replaces https://github.com/o/r/pull/4\n")
    other = {key.replace(f"/{REPLACED_NUMBER}/", "/4/").replace(f"pr view {REPLACED_NUMBER} ", "pr view 4 "): value
             for key, value in replaced_routes(frozen_head, REPLACED_SECOND_HEAD, REPLACED_TWO_ROUNDS,
                                               REPLACED_COMMENTS).items()
             if f"/{REPLACED_NUMBER}/" in key or key.startswith(f"pr view {REPLACED_NUMBER} ")}
    code, out, err = run(root, repository, {**routes, **other})
    check("replaces: a replaced pull request with no open round does not stop the next one's findings from "
          "being carried", code == 0 and "Blocking findings (3)" in out and "3. old.py:30" in out, err + out)

    code, out, err = run(root, repository, replaced_routes(
        frozen_head, REPLACED_SECOND_HEAD, REPLACED_TWO_ROUNDS, REPLACED_COMMENTS,
        description="#replaces pull request 5\n"))
    check("replaces: a #replaces line with no full link is refused, naming the line",
          code == 1 and err.startswith("REFUSED: pull request 7's description has the line `#replaces pull request 5`")
          and f"#replaces https://github.com/o/r/pull/<the old pull request's number>" in err, err + out)


gh_timeout_case()
case("suites", suite_cases)
case("nits", nit_cases)
case("move", move_cases)
case("move hand commit", move_hand_commit_cases)
case("move failure after push", move_failure_after_push_cases)
case("move push failure", move_push_failure_cases)
case("move pre-push hook output", move_pre_push_hook_output_cases)
case("brief", brief_cases)
case("check", check_cases)
case("commissioned reviewer", commissioned_reviewer_cases)
case("split review", split_review_cases)
case("rounds on one head", rounds_on_one_head_cases)
case("stated count position", stated_count_position_cases)
case("replaces", replaces_cases)
print(f"{'FAILED' if failures else 'PASSED'}: {len(failures)} failed")
sys.exit(1 if failures else 0)
