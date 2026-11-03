#!/usr/bin/env python3
"""Tests for merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py.

The program is loaded by path and its main() is called in this process, with
a fake scripts/merge-gate.sh in a scratch --review-tools-worktree-at-main,
a clone of a scratch origin repository at its origin/main, a
fake `gh` first on PATH, and HOME pointing at a scratch home that holds the
merge account's token file. The fake
gate answers each run from a numbered output file and exit code the case
writes. The fake `gh` logs every call with the GH_TOKEN it saw and answers
from a routes file the case writes; it does not filter `gh pr list` by base
branch, so the program's own filter is what each stacked case tests. The
waits between gate runs go to a list instead of sleeping. A case may make the
pull request's review worktrees in a scratch review worktrees directory, as
worktrees of the review tools clone; a pr10-head that is a plain directory
instead makes git worktree remove fail. A route may kill the fake `gh` with
SIGKILL, and a case may put a `git` first on PATH that kills itself on
`git worktree remove` and runs the real git otherwise.

Run: python3 scripts/merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget-test.py
"""

import contextlib
import importlib.util
import io
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

PROGRAM = Path(__file__).with_name("merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py")
_spec = importlib.util.spec_from_file_location("merge_lane_pull_request_merge", PROGRAM)
program = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(program)

PULL_REQUEST = "10"
HEAD = "a" * 40
SINCE = "2026-10-09T21:00:00Z"
BRANCH = "topic-of-pull-request-10"
TOKEN = "merge-lane-merge-test-token-not-a-credential"
EXPECTED_MERGE = ["pr", "merge", PULL_REQUEST, "--repo", "nedschorus/nedschorus", "--merge",
                  "--delete-branch", "--match-head-commit", HEAD]
GATE_PASSED = ("gate passed (#10): approved commit " + HEAD + "\n"
               "MERGE WITH THIS EXACT COMMAND:\n"
               "  gh pr merge 10 --repo nedschorus/nedschorus --merge --delete-branch "
               "--match-head-commit " + HEAD + "\n"
               "Run that command with GH_TOKEN set to the merge account's token.\n")
GATE_UNKNOWN = "GATE REFUSED (#10): mergeStateStatus is UNKNOWN\nUNKNOWN: run the gate again.\n"
GATE_REFUSED = "GATE REFUSED (#10): no APPROVED review found\n"

FAKE_GATE = r'''#!/bin/bash
directory=$MERGE_LANE_MERGE_TEST_DIRECTORY
echo "$*" >> "$directory/gate-calls.log"
# macOS's wc pads the count with spaces; the arithmetic expansion drops them.
count=$(( $(wc -l < "$directory/gate-calls.log") ))
[ -f "$directory/gate-$count.out" ] || count=last
cat "$directory/gate-$count.out"
exit "$(cat "$directory/gate-$count.exit")"
'''

FAKE_GH = r'''#!/usr/bin/env python3
import json, os, sys
directory = os.environ["MERGE_LANE_MERGE_TEST_DIRECTORY"]
argv = sys.argv[1:]
with open(os.path.join(directory, "gh-calls.log"), "a") as log:
    log.write(json.dumps({"argv": argv, "gh_token": os.environ.get("GH_TOKEN")}) + "\n")
routes = json.load(open(os.path.join(directory, "gh-routes.json")))
if argv[:2] == ["pr", "view"] and "headRefName,baseRefName" in argv:
    key = "view-branches"
elif argv[:2] == ["pr", "view"]:
    key = "view-state"
else:
    key = " ".join(argv[:2])
route = routes.get(key)
if route is None:
    sys.stderr.write("fake gh: unarranged call %r\n" % (argv,))
    sys.exit(97)
if route.get("killed"):
    os.kill(os.getpid(), 9)
sys.stdout.write(route.get("stdout", ""))
sys.stderr.write(route.get("stderr", ""))
sys.exit(route.get("exit", 0))
'''

failures = []
GIT_ENVIRONMENT = dict(os.environ)
GIT_IDENTITY = ["-c", "user.name=merge-lane-test", "-c", "user.email=test@example.invalid"]


def git(*arguments, cwd=None):
    subprocess.run(["git", *GIT_IDENTITY, *arguments], cwd=cwd, env=GIT_ENVIRONMENT,
                   check=True, capture_output=True, stdin=subprocess.DEVNULL)


def origin_with_one_commit(scratch):
    """Return a bare origin repository whose main has one commit."""
    origin = scratch / "origin.git"
    seed = scratch / "origin-seed"
    git("init", "-q", "-b", "main", str(seed))
    (seed / "README").write_text("seed\n")
    git("add", "README", cwd=seed)
    git("commit", "-q", "-m", "seed", cwd=seed)
    git("clone", "-q", "--bare", str(seed), str(origin))
    return origin


def check(name, condition, detail=""):
    print(("PASS  " if condition else "FAIL  ") + name)
    if not condition:
        failures.append(name)
        if detail:
            print("      " + detail.replace("\n", "\n      "))


def default_routes(open_pull_requests, edit_exit=0, merge_exit=0):
    return {
        "view-branches": {"stdout": json.dumps({"headRefName": BRANCH, "baseRefName": "main"})},
        "pr list": {"stdout": json.dumps(open_pull_requests)},
        "pr edit": {"exit": edit_exit, "stderr": "" if edit_exit == 0 else "edit refused\n"},
        "pr merge": {"exit": merge_exit},
        "view-state": {"stdout": '{"state":"MERGED"}\n'},
    }


STACKED_AND_NOT = [{"number": 20, "baseRefName": BRANCH},
                   {"number": 21, "baseRefName": "main"},
                   {"number": 22, "baseRefName": "some-other-topic"}]


def run_case(scratch, name, gate_answers, routes, token=TOKEN, review_tools_state="at-main",
             review_worktrees_state="none", git_killed_on_worktree_remove=False):
    """Run main() once; return (exit code, output, gh calls, gate calls, waits).

    review_tools_state: "at-main", "behind-main" (origin/main moved on after the
    clone), "no-origin" (the clone's origin is gone) or "no-gate".
    review_worktrees_state: "none", "both" (pr10-head and pr10-merged are
    worktrees, pr10-merged with an untracked file), "merged-only" (pr10-merged
    is a worktree, pr10-head is not there) or "head-not-a-worktree" (pr10-head
    is a plain directory, pr10-merged a worktree).
    """
    directory = scratch / name
    directory.mkdir()
    bin_directory = directory / "bin"
    bin_directory.mkdir()
    (bin_directory / "gh").write_text(FAKE_GH)
    (bin_directory / "gh").chmod(0o755)
    if git_killed_on_worktree_remove:
        (bin_directory / "git").write_text(
            '#!/bin/bash\ncase " $* " in *" worktree remove "*) kill -9 $$;; esac\n'
            f'exec {shutil.which("git")} "$@"\n')
        (bin_directory / "git").chmod(0o755)
    origin = origin_with_one_commit(directory)
    review_tools = directory / "review-tools"
    git("clone", "-q", str(origin), str(review_tools))
    git("checkout", "-q", "--detach", "origin/main", cwd=review_tools)
    if review_tools_state != "no-gate":
        (review_tools / "scripts").mkdir(parents=True)
        (review_tools / "scripts" / "merge-gate.sh").write_text(FAKE_GATE)
    if review_tools_state == "behind-main":
        seed = directory / "origin-seed"
        (seed / "README").write_text("moved on\n")
        git("commit", "-q", "-am", "main moves on", cwd=seed)
        git("push", "-q", str(origin), "main", cwd=seed)
    review_worktrees = directory / "review-worktrees"
    if review_worktrees_state == "both":
        git("worktree", "add", "-q", "--detach", str(review_worktrees / "pr10-head"),
            cwd=review_tools)
    if review_worktrees_state == "head-not-a-worktree":
        (review_worktrees / "pr10-head").mkdir(parents=True)
        (review_worktrees / "pr10-head" / "README").write_text("not a worktree\n")
    if review_worktrees_state != "none":
        git("worktree", "add", "-q", "--detach", str(review_worktrees / "pr10-merged"),
            cwd=review_tools)
        (review_worktrees / "pr10-merged" / "left-by-a-test-run.txt").write_text("untracked\n")
    if review_tools_state == "no-origin":
        shutil.rmtree(origin)
    for number, (output, exit_code) in enumerate(gate_answers, start=1):
        (directory / f"gate-{number}.out").write_text(output)
        (directory / f"gate-{number}.exit").write_text(str(exit_code))
    (directory / "gate-last.out").write_text(gate_answers[-1][0])
    (directory / "gate-last.exit").write_text(str(gate_answers[-1][1]))
    (directory / "gh-routes.json").write_text(json.dumps(routes))
    home = directory / "home"
    (home / ".config" / "nedschorus").mkdir(parents=True)
    if token is not None:
        (home / ".config" / "nedschorus" / "ned-review-merge.token").write_text(token + "\n")

    waits = []
    saved_path, saved_home = os.environ["PATH"], os.environ.get("HOME")
    os.environ["PATH"] = f"{bin_directory}{os.pathsep}{saved_path}"
    os.environ["HOME"] = str(home)
    os.environ["MERGE_LANE_MERGE_TEST_DIRECTORY"] = str(directory)
    output = io.StringIO()
    try:
        with contextlib.redirect_stdout(output):
            exit_code = program.main([PULL_REQUEST, HEAD, SINCE, "--review-tools-worktree-at-main",
                                      str(review_tools), "--merge-lane-review-worktrees-directory",
                                      str(review_worktrees)], wait=waits.append)
    finally:
        os.environ["PATH"] = saved_path
        if saved_home is None:
            del os.environ["HOME"]
        else:
            os.environ["HOME"] = saved_home
    gh_log = directory / "gh-calls.log"
    gh_calls = ([json.loads(line) for line in gh_log.read_text().splitlines()]
                if gh_log.exists() else [])
    gate_log = directory / "gate-calls.log"
    gate_calls = gate_log.read_text().splitlines() if gate_log.exists() else []
    return exit_code, output.getvalue(), gh_calls, gate_calls, waits


def registered_worktrees(review_tools):
    listing = subprocess.run(["git", "-C", str(review_tools), "worktree", "list", "--porcelain"],
                             capture_output=True, text=True, env=GIT_ENVIRONMENT, check=True)
    return [line.split(" ", 1)[1] for line in listing.stdout.splitlines()
            if line.startswith("worktree ")]


def argvs(gh_calls):
    return [call["argv"] for call in gh_calls]


def index_of(calls, prefix):
    for index, argv in enumerate(calls):
        if argv[:len(prefix)] == prefix:
            return index
    return None


def main():
    # Resolved, because macOS's mkdtemp path is a symlink and the program resolves its paths.
    scratch = Path(tempfile.mkdtemp(prefix="merge-lane-merge-test-")).resolve()
    try:
        exit_code, output, gh_calls, gate_calls, waits = run_case(
            scratch, "stacked", [(GATE_PASSED, 0)], default_routes(STACKED_AND_NOT),
            review_worktrees_state="both")
        calls = argvs(gh_calls)
        edit_20 = index_of(calls, ["pr", "edit", "20"])
        merge = index_of(calls, ["pr", "merge"])
        check("a pull request based on the merged branch is retargeted to main before the merge",
              edit_20 is not None and merge is not None and edit_20 < merge
              and calls[edit_20] == ["pr", "edit", "20", "--repo", "nedschorus/nedschorus",
                                     "--base", "main"], json.dumps(calls))
        check("a pull request based on main is left alone",
              index_of(calls, ["pr", "edit", "21"]) is None, json.dumps(calls))
        check("a pull request based on another branch is left alone",
              index_of(calls, ["pr", "edit", "22"]) is None, json.dumps(calls))
        check("the merge runs exactly the command the gate printed",
              merge is not None and calls[merge] == EXPECTED_MERGE, json.dumps(calls))
        check("the gate that runs is --review-tools-worktree-at-main's, not the one beside the program",
              gate_calls == [f"{PULL_REQUEST} {HEAD} {SINCE}"], repr(gate_calls))
        check("every gh call carries the merge account's token, read from the gate's own file",
              gh_calls and all(call["gh_token"] == TOKEN for call in gh_calls),
              json.dumps(gh_calls))
        check("the retarget is printed with how to undo it",
              f"retargeted pull request #20 from {BRANCH} to main" in output
              and f"--base {BRANCH}" in output, output)
        check("a merged pull request exits 0 and prints its state after the merge",
              exit_code == 0 and '{"state":"MERGED"}' in output, f"exit {exit_code}\n{output}")
        review_worktrees = scratch / "stacked" / "review-worktrees"
        left = registered_worktrees(scratch / "stacked" / "review-tools")
        check("a merged pull request's two review worktrees are removed, an untracked file "
              "in one included, and each removal is printed",
              not (review_worktrees / "pr10-head").exists()
              and not (review_worktrees / "pr10-merged").exists()
              and not any("review-worktrees" in path for path in left)
              and f"removed the review worktree {review_worktrees / 'pr10-head'}" in output
              and f"removed the review worktree {review_worktrees / 'pr10-merged'}" in output,
              f"{left}\n{output}")

        exit_code, output, _, _, _ = run_case(
            scratch, "merged-only", [(GATE_PASSED, 0)], default_routes(STACKED_AND_NOT),
            review_worktrees_state="merged-only")
        review_worktrees = scratch / "merged-only" / "review-worktrees"
        check("a review worktree that is not there is skipped, and the other is still removed",
              exit_code == 0 and not (review_worktrees / "pr10-merged").exists(),
              f"exit {exit_code}\n{output}")

        exit_code, output, gh_calls, _, _ = run_case(
            scratch, "review-worktree-not-removable", [(GATE_PASSED, 0)],
            default_routes(STACKED_AND_NOT), review_worktrees_state="head-not-a-worktree")
        review_tools = scratch / "review-worktree-not-removable" / "review-tools"
        not_removable = scratch / "review-worktree-not-removable" / "review-worktrees" / "pr10-head"
        check("a review worktree that git cannot remove exits 3 after the merge is reported, "
              "naming the worktree, git's error as text and the command to remove it",
              exit_code == 3 and index_of(argvs(gh_calls), ["pr", "merge"]) is not None
              and '{"state":"MERGED"}' in output
              and f"STOP: merged, but the review worktree {not_removable} was not removed"
              in output and "exited 128: fatal: " in output and "is not a working tree" in output
              and f"git -C {review_tools} worktree remove --force {not_removable}" in output,
              f"exit {exit_code}\n{output}")
        check("the other review worktree is still removed when one cannot be",
              not (not_removable.parent / "pr10-merged").exists(), output)

        exit_code, output, _, _, _ = run_case(
            scratch, "git-killed", [(GATE_PASSED, 0)], default_routes(STACKED_AND_NOT),
            review_worktrees_state="both", git_killed_on_worktree_remove=True)
        check("a git worktree remove killed by a signal exits 3 after the merge",
              exit_code == 3 and "STOP: merged, but the review worktree" in output
              and "exited -9" in output, f"exit {exit_code}\n{output}")

        exit_code, output, gh_calls, _, _ = run_case(
            scratch, "none-stacked", [(GATE_PASSED, 0)],
            default_routes([{"number": 21, "baseRefName": "main"}]))
        calls = argvs(gh_calls)
        check("with no stacked pull request nothing is retargeted and the merge runs",
              index_of(calls, ["pr", "edit"]) is None
              and index_of(calls, ["pr", "merge"]) is not None and exit_code == 0,
              f"exit {exit_code}\n{json.dumps(calls)}")
        check("with no stacked pull request the output says so",
              f"no open pull request is based on {BRANCH}" in output, output)

        exit_code, output, gh_calls, gate_calls, waits = run_case(
            scratch, "unknown-then-passes",
            [(GATE_UNKNOWN, 1), (GATE_UNKNOWN, 1), (GATE_PASSED, 0)],
            default_routes(STACKED_AND_NOT))
        check("the gate runs again, 5 seconds apart, while it reports UNKNOWN",
              len(gate_calls) == 3 and waits == [5, 5], f"{gate_calls} {waits}")
        check("a gate that passes after UNKNOWN goes on to merge",
              exit_code == 0 and index_of(argvs(gh_calls), ["pr", "merge"]) is not None,
              f"exit {exit_code}\n{output}")

        exit_code, output, gh_calls, gate_calls, waits = run_case(
            scratch, "unknown-always", [(GATE_UNKNOWN, 1)], default_routes(STACKED_AND_NOT))
        check("the gate runs at most 8 times while it reports UNKNOWN",
              len(gate_calls) == 8 and len(waits) == 7, f"{len(gate_calls)} {waits}")
        check("a gate still UNKNOWN after 8 runs stops with its exit code, touching nothing",
              exit_code == 1 and gh_calls == [], f"exit {exit_code}\n{json.dumps(gh_calls)}")

        exit_code, output, gh_calls, gate_calls, waits = run_case(
            scratch, "refused", [(GATE_REFUSED, 1)], default_routes(STACKED_AND_NOT))
        check("a refusal other than UNKNOWN is not retried",
              len(gate_calls) == 1 and waits == [], f"{gate_calls} {waits}")
        check("a refused gate retargets nothing and merges nothing",
              exit_code == 1 and gh_calls == [] and GATE_REFUSED.strip() in output,
              f"exit {exit_code}\n{output}\n{json.dumps(gh_calls)}")

        exit_code, output, gh_calls, _, _ = run_case(
            scratch, "could-not-run", [("GATE COULD NOT RUN: jq is not on PATH.\n", 2)],
            default_routes(STACKED_AND_NOT))
        check("a gate that could not run exits 2, touching nothing",
              exit_code == 2 and gh_calls == [], f"exit {exit_code}\n{output}")

        unexpected = GATE_PASSED.replace(" --match-head-commit " + HEAD, "")
        exit_code, output, gh_calls, _, _ = run_case(
            scratch, "unexpected-command", [(unexpected, 0)], default_routes(STACKED_AND_NOT))
        check("a merge command other than the expected one is refused, touching nothing",
              exit_code == 1 and gh_calls == [] and "STOP: not merged" in output
              and "Do not merge, by either command." in output,
              f"exit {exit_code}\n{output}\n{json.dumps(gh_calls)}")

        exit_code, output, gh_calls, _, _ = run_case(
            scratch, "retarget-fails", [(GATE_PASSED, 0)],
            default_routes(STACKED_AND_NOT, edit_exit=1))
        calls = argvs(gh_calls)
        check("a retarget that fails stops before the merge, exit 2",
              exit_code == 2 and index_of(calls, ["pr", "merge"]) is None,
              f"exit {exit_code}\n{json.dumps(calls)}")
        check("a failed retarget names the pull request and gh's error",
              "could not retarget pull request #20" in output and "edit refused" in output,
              output)

        routes = default_routes(STACKED_AND_NOT)
        routes["pr list"] = {"exit": 1, "stderr": "HTTP 502\n"}
        exit_code, output, gh_calls, _, _ = run_case(
            scratch, "list-fails", [(GATE_PASSED, 0)], routes)
        calls = argvs(gh_calls)
        check("an open pull request list that fails stops before the merge, exit 2",
              exit_code == 2 and index_of(calls, ["pr", "merge"]) is None
              and "HTTP 502" in output, f"exit {exit_code}\n{output}")

        exit_code, output, gh_calls, _, _ = run_case(
            scratch, "merge-fails", [(GATE_PASSED, 0)],
            default_routes(STACKED_AND_NOT, merge_exit=1), review_worktrees_state="both")
        check("a merge that fails exits 1", exit_code == 1 and "merge exit 1" in output,
              f"exit {exit_code}\n{output}")
        review_worktrees = scratch / "merge-fails" / "review-worktrees"
        check("a merge that fails leaves the review worktrees in place",
              (review_worktrees / "pr10-head").is_dir()
              and (review_worktrees / "pr10-merged").is_dir(), output)

        routes = default_routes(STACKED_AND_NOT)
        routes["pr merge"] = {"killed": True}
        exit_code, output, _, _, _ = run_case(
            scratch, "merge-killed", [(GATE_PASSED, 0)], routes, review_worktrees_state="both")
        review_worktrees = scratch / "merge-killed" / "review-worktrees"
        check("a merge killed by a signal exits 1 and leaves the review worktrees in place",
              exit_code == 1 and (review_worktrees / "pr10-head").is_dir()
              and (review_worktrees / "pr10-merged").is_dir(), f"exit {exit_code}\n{output}")

        exit_code, output, gh_calls, gate_calls, _ = run_case(
            scratch, "no-token", [(GATE_PASSED, 0)], default_routes(STACKED_AND_NOT),
            token=None)
        check("an unreadable token file exits 2 before the gate or gh runs",
              exit_code == 2 and gate_calls == [] and gh_calls == [],
              f"exit {exit_code}\n{output}")

        exit_code, output, gh_calls, gate_calls, _ = run_case(
            scratch, "blank-token", [(GATE_PASSED, 0)], default_routes(STACKED_AND_NOT),
            token=" \t ")
        check("a token file holding only whitespace exits 2 before the gate or gh runs",
              exit_code == 2 and gate_calls == [] and gh_calls == []
              and "STOP: not merged" in output and "is empty" in output,
              f"exit {exit_code}\n{output}")

        exit_code, output, gh_calls, gate_calls, _ = run_case(
            scratch, "review-tools-behind-main", [(GATE_PASSED, 0)],
            default_routes(STACKED_AND_NOT), review_tools_state="behind-main")
        check("a review tools worktree behind origin/main stops before the gate, exit 2",
              exit_code == 2 and gate_calls == [] and gh_calls == []
              and "not at origin/main" in output and "checkout --detach origin/main" in output,
              f"exit {exit_code}\n{output}")
        review_tools = scratch / "review-tools-behind-main" / "review-tools"
        printed = [line.split("Move it to main:", 1)[1].strip() for line in output.splitlines()
                   if "Move it to main:" in line]
        moved = (subprocess.run(["bash", "-c", printed[0]], capture_output=True, text=True,
                                env=GIT_ENVIRONMENT) if len(printed) == 1 else None)
        head_and_main = subprocess.run(
            ["git", "-C", str(review_tools), "rev-parse", "HEAD", "origin/main"],
            capture_output=True, text=True, env=GIT_ENVIRONMENT).stdout.split()
        at_main = (moved is not None and moved.returncode == 0 and len(head_and_main) == 2
                   and head_and_main[0] == head_and_main[1])
        check("the printed command to move the worktree, run as printed, puts it at origin/main",
              at_main, "no single printed command" if moved is None
              else f"exit {moved.returncode}\n{moved.stderr}")

        exit_code, output, gh_calls, gate_calls, _ = run_case(
            scratch, "review-tools-fetch-fails", [(GATE_PASSED, 0)],
            default_routes(STACKED_AND_NOT), review_tools_state="no-origin")
        check("a review tools worktree that cannot fetch origin stops before the gate, exit 2",
              exit_code == 2 and gate_calls == [] and gh_calls == []
              and "could not fetch origin" in output, f"exit {exit_code}\n{output}")

        exit_code, output, gh_calls, gate_calls, _ = run_case(
            scratch, "no-gate", [(GATE_PASSED, 0)],
            default_routes(STACKED_AND_NOT), review_tools_state="no-gate")
        check("a review tools worktree without merge-gate.sh stops before any run, exit 2",
              exit_code == 2 and gh_calls == [] and "merge-gate.sh is missing" in output,
              f"exit {exit_code}\n{output}")

        exit_code, output, gh_calls, _, _ = run_case(
            scratch, "gate-undocumented-exit", [("bash: something broke\n", 127)],
            default_routes(STACKED_AND_NOT))
        check("a gate exit outside 0, 1 and 2 is reported as could-not-run, exit 2",
              exit_code == 2 and gh_calls == [] and "exited 127" in output,
              f"exit {exit_code}\n{output}")

        routes = default_routes(STACKED_AND_NOT)
        routes["view-branches"] = {"exit": 1, "stderr": "HTTP 503\n"}
        exit_code, output, gh_calls, _, _ = run_case(
            scratch, "view-branches-fails", [(GATE_PASSED, 0)], routes)
        calls = argvs(gh_calls)
        check("a pull request whose branches cannot be read stops before the merge, exit 2",
              exit_code == 2 and index_of(calls, ["pr", "merge"]) is None
              and index_of(calls, ["pr", "edit"]) is None
              and "STOP: not merged: could not read pull request 10's branch" in output
              and "HTTP 503" in output, f"exit {exit_code}\n{output}")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    if failures:
        print(f"\n{len(failures)} case(s) failed")
        return 1
    print("\nall cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
