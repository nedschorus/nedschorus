#!/usr/bin/env python3
"""Tests for pull-request-fix-round-author-brief-from-blocking-findings-and-one-commit-every-finding-answered-check.py.

Each case runs the program in a scratch git repository with a fake `gh` first on PATH. The fake
answers from a routes file the case writes, keyed by its arguments joined with spaces, and
exits 1 on an unarranged call.

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
PR_VIEW = f"pr view {NUMBER} --json url,headRefOid,headRefName"
BRANCH = "topic-branch-of-the-pull-request"
URL = f"https://github.com/o/r/pull/{NUMBER}"

FAKE_GH = r'''#!/usr/bin/env python3
import json, os, sys
key = " ".join(sys.argv[1:])
routes = json.load(open(os.environ["FAKE_GH_ROUTES"]))
if key not in routes:
    sys.stderr.write("fake gh: unarranged call %r\n" % key)
    sys.exit(1)
route = routes[key]
sys.stdout.write(route.get("stdout", ""))
sys.stderr.write(route.get("stderr", ""))
sys.exit(route.get("exit", 0))
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
    git(repository, "add", ".gitignore")
    base = commit_file(repository, "base.txt", "base\n", "base")
    git(repository, "branch", "main-line")
    frozen_head = commit_file(repository, "hook.py", "one\n", "topic work")
    git(repository, "checkout", "-q", "main-line")
    main_tip = commit_file(repository, "main.txt", "main\n", "main work")
    git(repository, "update-ref", "refs/remotes/origin/main", main_tip)
    git(repository, "checkout", "-q", "topic")
    return repository, base, frozen_head


def review(state="CHANGES_REQUESTED", commit_id=None, login="ned-review-merge", review_id=11,
           body="merge-lane-2: changes requested.\n\n**Blocking: 2**, both inline."):
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


def lines(objects):
    return "".join(json.dumps(item) + "\n" for item in objects)


def routes_for(head, reviews, comments=BLOCKING_COMMENTS, review_id=11):
    return {
        PR_VIEW: {"stdout": json.dumps({"url": URL, "headRefOid": head, "headRefName": BRANCH})},
        REVIEWS: {"stdout": lines(reviews)},
        f"api --paginate repos/{{owner}}/{{repo}}/pulls/{NUMBER}/reviews/{review_id}/comments --jq .[]":
            {"stdout": lines(comments)},
    }


def run(root, repository, routes, *arguments, path_has_gh=True):
    bin_directory = root / "bin"
    bin_directory.mkdir(exist_ok=True)
    (bin_directory / "gh").write_text(FAKE_GH)
    (bin_directory / "gh").chmod(0o755)
    (root / "routes.json").write_text(json.dumps(routes))
    environment = dict(os.environ, FAKE_GH_ROUTES=str(root / "routes.json"))
    git_only_directory = root / "git-only-bin"
    if not git_only_directory.exists():
        git_only_directory.mkdir()
        (git_only_directory / "git").symlink_to(shutil.which("git"))
    environment["PATH"] = (f"{bin_directory}{os.pathsep}{environment['PATH']}" if path_has_gh
                           else str(git_only_directory))
    completed = subprocess.run([sys.executable, str(PROGRAM), str(NUMBER), *arguments],
                               cwd=repository, capture_output=True, text=True, env=environment,
                               timeout=120)
    return completed.returncode, completed.stdout, completed.stderr


WRITE_GUARD = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "session-location-write-guard.py"
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
    check("brief: carries both blocking findings word for word, in order, and not the note",
          out.index("hook.py swallows") < out.index("no case for the timeout")
          and "A non-blocking note" not in out and "1. hook.py:12" in out and "2. test.py (" in out, out)
    check("brief: step 5 names the answers file at the root of the subagent's worktree",
          f"5. Write the answers file {ANSWERS_NAME} at the root of your worktree," in out, out)
    check("brief: names no absolute path, so nothing in it points into the author's checkout",
          str(root) not in out and str(repository) not in out and "/.git/" not in out, out)
    check("brief: the check command has no --answers, so it reads the file at its own worktree's root",
          f"7. Run the check: python3 scripts/{PROGRAM.name} {NUMBER} --check\n" in out
          and "--answers" not in out, out)
    check("brief: names the conflict check, the pre-push test run and the check command, in order",
          out.index(f"branch-conflict-check.py --pull-request {NUMBER}")
          < out.index("run-all-test-suites.py --only-suites-whose-recorded-inputs-changed-since origin/main")
          < out.index(f"{NUMBER} --check"), out)
    check("brief: says what to do when the check refuses and when a step fails after the push",
          "git commit --amend is allowed before the push" in out
          and "do not push again or rewrite the branch" in out, out)
    check("brief: a conflict defers to the conflict check's report, and asks for no merge itself",
          "If it reports VERDICT: CONFLICT, do what its report says." in out
          and "merge origin/main as its report says" not in out and "merge nothing" not in out, out)
    check("brief: says what to do when a suite fails and when the push itself fails",
          "fix it in the same commit; if it fails for another cause, tell merge-lane-2 with "
          "SendMessage before pushing" in out
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
    check_line = next((line for line in out.splitlines() if line.startswith("7. Run the check: ")), "")
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

    # A second changes-requested review of the same frozen-head, while the first round's worktree
    # still has its branch checked out: the second round's step 0 must work in a worktree of its own.
    code, second_out, err = run(root, repository, routes_for(
        frozen_head, [review(commit_id=frozen_head), review(commit_id=frozen_head, review_id=12)], review_id=12))
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

    def comments_route(review_id, comments):
        return {f"api --paginate repos/{{owner}}/{{repo}}/pulls/{NUMBER}/reviews/{review_id}/comments --jq .[]":
                {"stdout": lines(comments)}}

    reposted = dict(routes_for(frozen_head, [review(commit_id=frozen_head, body="Two blockers."),
                                             review(state="COMMENTED", commit_id=frozen_head, review_id=12,
                                                    body="**Blocking: 2**, now inline.")],
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
        review(state="COMMENTED", commit_id=frozen_head, review_id=12, body="**Blocking: 3**")])}})
    code, out, err = run(root, repository, miscounted)
    check("brief: a later review's stated count is checked against its own marked comments",
          code == 1 and "says **Blocking: 3**" in err and "2 of its own inline comments" in err
          and "change nothing and push nothing" in err
          and f"naming its changes-requested review, {URL}#pullrequestreview-11" in err, err)

    added = dict(routes_for(frozen_head, [review(commit_id=frozen_head),
                                          review(state="COMMENTED", commit_id=frozen_head, review_id=12,
                                                 body="**Blocking: 1**, one more.")]),
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
            frozen_head, [review(commit_id=frozen_head, body="**Blocking: 1**")],
            comments=[comment("hook.py", f"{spelling} the spelling under test.")]))
        check(f"brief: a comment starting {spelling.strip()!r} is a blocking finding",
              code == 0 and "Blocking findings (1)" in out and "the spelling under test" in out, err + out)

    mixed = [comment("a.py", "**Blocks.** first.", comment_id=21),
             comment("b.py", "**Blocks.** second.", comment_id=22),
             comment("c.py", "**Blocks** (cold-read-fast-read hold on the docstring) third.", comment_id=23),
             comment("d.py", "**Blocks** (cold-read-fast-read hold on the progress line) fourth.", comment_id=24),
             comment("e.py", "Non-blocking. A note.", comment_id=25)]
    code, out, err = run(root, repository, routes_for(
        frozen_head, [review(commit_id=frozen_head, body="Four findings block.\n\n**Blocking: 4**")],
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
        frozen_head, [review(commit_id=frozen_head, body="**Blocking: 3**")]))
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
          and "This program stopped there: it printed no brief and checked no round." in err, err)

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
          "names: other.txt" in out, out + err)

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


gh_timeout_case()
case("brief", brief_cases)
case("check", check_cases)
print(f"{'FAILED' if failures else 'PASSED'}: {len(failures)} failed")
sys.exit(1 if failures else 0)
