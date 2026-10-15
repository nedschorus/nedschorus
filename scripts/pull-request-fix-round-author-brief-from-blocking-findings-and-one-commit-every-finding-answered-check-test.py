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
PR_VIEW = f"pr view {NUMBER} --json url,headRefOid"
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
        PR_VIEW: {"stdout": json.dumps({"url": URL, "headRefOid": head})},
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
    check("brief: ends with the --check command", f"{NUMBER} --check --answers" in out, out)

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
          code == 1 and "is APPROVED, not CHANGES_REQUESTED" in err, err)

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
          code == 1 and "says **Blocking: 3**" in err and "2 of its inline comments" in err, err)

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
          code == 2 and "HTTP 502" in err and "tell the user" in err, err)

    routes = routes_for(frozen_head, [review(commit_id=frozen_head)])
    routes[REVIEWS] = {"stdout": "not json\n"}
    code, out, err = run(root, repository, routes)
    check("brief: gh output that is not JSON fails with exit 2",
          code == 2 and "not JSON" in err, err)

    routes = routes_for(frozen_head, [review(commit_id=frozen_head)])
    routes[PR_VIEW] = {"stdout": json.dumps({"url": URL})}
    code, out, err = run(root, repository, routes)
    check("brief: gh pr view without headRefOid fails with exit 2",
          code == 2 and "gave no url and headRefOid" in err, err)

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
    check("check: two commits refuse with exit 1", code == 1 and "has 2 commits" in err
          and "squash them" in err, err)

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

    code, out, err = run(root, repository, routes_for(frozen_head, reviews), "--check")
    check("check: --check without --answers is a usage error", code == 2
          and "--check needs --answers" in err, err)

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
