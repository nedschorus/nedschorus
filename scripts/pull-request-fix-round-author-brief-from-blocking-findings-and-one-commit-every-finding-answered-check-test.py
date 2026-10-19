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


def answers_file(root, text):
    path = root / "answers.md"
    path.write_text(text)
    return str(path)


GOOD_ANSWERS = "1. Fixed: the error is raised,\n   and a case covers it.\n2. Added the timeout case.\n"


def case(name, body):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        repository, base, frozen_head = scratch_repository(root)
        body(root, repository, base, frozen_head)


def brief_cases(root, repository, base, frozen_head):
    code, out, err = run(root, repository, routes_for(frozen_head, [review(commit_id=frozen_head)]))
    check("brief: exit 0 for a changes-requested review of the current head", code == 0, err)
    check("brief: names the frozen-head", f"Frozen-head: {frozen_head}" in out, out)
    check("brief: carries both blocking findings word for word, in order, and not the note",
          out.index("hook.py swallows") < out.index("no case for the timeout")
          and "A non-blocking note" not in out and "1. hook.py:12" in out and "2. test.py (" in out, out)
    git_directory = git(repository, "rev-parse", "--absolute-git-dir")
    check("brief: names the answers file inside the checkout's git directory",
          f"{git_directory}/fix-round-answers-pull-request-{NUMBER}.md" in out, out)
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
    check("brief: the subagent checks out the frozen-head detached and pushes HEAD to the branch",
          f"git fetch origin && git checkout --detach {frozen_head}" in out
          and f"git push origin HEAD:{BRANCH}" in out, out)
    check("brief: says who removes the worktree, and to leave a harness-locked one",
          "git worktree remove" in out and "only the harness unlocks it" in out, out)
    check("brief: the author's worktree lines come before the subagent's rules of the round",
          out.index("For the author: dispatch") < out.index("For the author, when the subagent has finished")
          < out.index("For the subagent, the rules of the round") < out.index("0. Check out the frozen-head"), out)
    check("brief: says to leave a worktree the harness locked, and to read any other refusal",
          "lock reason it prints starts with \"claude agent\"" in out
          and "pass --force only once you have seen that none of them is work to keep" in out, out)
    answers_in_checkout = f"{git_directory}/fix-round-answers-pull-request-{NUMBER}.md"
    check("brief: the check command names the author's answers file, so it reads the same file in any worktree",
          f"{NUMBER} --check --answers {answers_in_checkout}" in out, out)

    worktree = root / "subagent-worktree"
    git(repository, "worktree", "add", "-q", "--detach", str(worktree), frozen_head)
    Path(answers_in_checkout).write_text(GOOD_ANSWERS)
    check_line = next((line for line in out.splitlines() if f"{NUMBER} --check --answers" in line), "")
    printed_answers = check_line.split("--answers ", 1)[-1].strip()
    code, check_out, err = run(root, worktree, routes_for(frozen_head, [review(commit_id=frozen_head)]),
                               "--check", "--answers", printed_answers)
    check("brief: the printed check command, run in the subagent's worktree, reads the author's answers file",
          code == 0 and "Nothing pushed" in check_out, check_out + err)
    Path(answers_in_checkout).unlink()
    git(repository, "worktree", "remove", "--force", str(worktree))

    spaced = root / "checkout with space"
    shutil.copytree(repository, spaced)
    code, spaced_out, err = run(root, spaced, routes_for(frozen_head, [review(commit_id=frozen_head)]))
    check("brief: an answers path with a space is shell-quoted in the check command",
          code == 0 and f"--answers '{spaced}/.git/fix-round-answers-pull-request-{NUMBER}.md'" in spaced_out,
          err + spaced_out)

    routes = routes_for(frozen_head, [review(commit_id=frozen_head)])
    routes[PR_VIEW] = {"stdout": json.dumps({"url": URL, "headRefOid": frozen_head, "headRefName": "topic$name"})}
    code, dollar_out, err = run(root, repository, routes)
    check("brief: a branch name the shell would expand is shell-quoted in the push command",
          code == 0 and "git push origin HEAD:'topic$name'" in dollar_out, err + dollar_out)

    outside = root / "not-a-checkout"
    outside.mkdir()
    code, out, err = run(root, outside, routes_for(frozen_head, [review(commit_id=frozen_head)]))
    check("brief: outside a git checkout refuses with exit 1, naming the checkout to use",
          code == 1 and "must run in your checkout of pull request 7's branch" in err, err)

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
          and "Otherwise, tell the user this message" in err, err)

    routes = routes_for(frozen_head, [review(commit_id=frozen_head)])
    routes[REVIEWS] = {"stdout": "not json\n"}
    code, out, err = run(root, repository, routes)
    check("brief: gh output that is not JSON fails with exit 2",
          code == 2 and "not JSON" in err, err)

    routes = routes_for(frozen_head, [review(commit_id=frozen_head)])
    routes[PR_VIEW] = {"stdout": json.dumps({"url": URL})}
    code, out, err = run(root, repository, routes)
    check("brief: gh pr view without headRefOid fails with exit 2",
          code == 2 and "gave no url, headRefOid and headRefName" in err, err)

    routes = routes_for(frozen_head, [review(commit_id=frozen_head)])
    routes[PR_VIEW] = {"stdout": json.dumps({"url": URL, "headRefOid": frozen_head})}
    code, out, err = run(root, repository, routes)
    check("brief: gh pr view without headRefName fails with exit 2",
          code == 2 and "gave no url, headRefOid and headRefName" in err, err)

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

    default_answers = Path(git(repository, "rev-parse", "--absolute-git-dir")) / \
        f"fix-round-answers-pull-request-{NUMBER}.md"
    default_answers.write_text(GOOD_ANSWERS)
    code, out, err = run(root, repository, routes_for(frozen_head, reviews), "--check")
    check("check: without --answers it reads the answers file in the checkout's git directory",
          code == 0 and "Nothing pushed" in out, out + err)
    check("check: the default answers file is not seen by git status",
          git(repository, "status", "--porcelain") == "", git(repository, "status", "--porcelain"))
    default_answers.unlink()
    code, out, err = run(root, repository, routes_for(frozen_head, reviews), "--check")
    check("check: a missing default answers file fails with exit 2, naming it",
          code == 2 and str(default_answers) in err, err)

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
