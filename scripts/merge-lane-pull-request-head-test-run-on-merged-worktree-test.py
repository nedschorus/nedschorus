#!/usr/bin/env python3
"""Tests for merge-lane-pull-request-head-test-run-on-merged-worktree.py.

A scratch --review-tools-worktree-at-main holds a fake scripts/pull-request-head-test-run.py
that logs its arguments, working directory, the first PATH entry and whether
GIT_DIR reached it, prints a SUMMARY line and a line on stderr, and exits
with the code the case gives for its --checkout. The program runs with
GIT_DIR set, so a case that finds GIT_DIR absent shows the program dropped
it.

Run: python3 scripts/merge-lane-pull-request-head-test-run-on-merged-worktree-test.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROGRAM = Path(__file__).with_name("merge-lane-pull-request-head-test-run-on-merged-worktree.py")

FAKE_HEAD_TEST_RUN = r'''#!/usr/bin/env python3
import json, os, sys
argv = sys.argv[1:]
checkout = argv[argv.index("--checkout") + 1]
with open(os.environ["MERGE_LANE_HEAD_TEST_RUN_TEST_LOG"], "a") as log:
    log.write(json.dumps({"argv": argv, "cwd": os.getcwd(),
                          "first_path_entry": os.environ["PATH"].split(os.pathsep)[0],
                          "git_dir": os.environ.get("GIT_DIR")}) + "\n")
exit_code = json.loads(os.environ["MERGE_LANE_HEAD_TEST_RUN_TEST_EXITS"]).get(
    os.path.basename(checkout), 0)
print("pull-request-head-test-run: starting")
print(f"SUMMARY: fake summary for {os.path.basename(checkout)}")
print("a line on stderr", file=sys.stderr)
sys.exit(exit_code)
'''

failures = []


def check(name, condition, detail=""):
    print(("PASS  " if condition else "FAIL  ") + name)
    if not condition:
        failures.append(name)
        if detail:
            print("      " + detail.replace("\n", "\n      "))


def run_program(scratch, helpers, exits, *pull_requests):
    log = scratch / "head-test-run-calls.log"
    log.unlink(missing_ok=True)
    completed = subprocess.run(
        [sys.executable, str(PROGRAM), *pull_requests,
         "--merge-lane-worktrees-and-outputs-directory", str(helpers),
         "--review-tools-worktree-at-main", str(scratch / "main-checkout")],
        capture_output=True, text=True,
        env={**os.environ, "GIT_DIR": str(scratch / "no-such-git-directory"),
             "MERGE_LANE_HEAD_TEST_RUN_TEST_LOG": str(log),
             "MERGE_LANE_HEAD_TEST_RUN_TEST_EXITS": json.dumps(exits)})
    calls = ([json.loads(line) for line in log.read_text().splitlines()]
             if log.exists() else [])
    return completed, calls


def main():
    scratch = Path(tempfile.mkdtemp(prefix="merge-lane-head-test-run-test-"))
    try:
        (scratch / "main-checkout" / "scripts").mkdir(parents=True)
        (scratch / "main-checkout" / "scripts" / "pull-request-head-test-run.py").write_text(
            FAKE_HEAD_TEST_RUN)
        helpers = scratch / "merge-helpers"
        (helpers / "tripwire-bin").mkdir(parents=True)

        completed, calls = run_program(scratch, helpers, {}, "7", "8")
        detail = f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}"
        check("each pull request is run in turn", [
            call["argv"][call["argv"].index("--checkout") + 1] for call in calls] == [
            str(helpers / "wt" / "pr7-merged"), str(helpers / "wt" / "pr8-merged")], detail)
        check("the run gets the paths under the worktrees and outputs directory",
              calls and calls[0]["argv"] == [
                  "--checkout", str(helpers / "wt" / "pr7-merged"),
                  "--log-store-root", str(helpers / "hr" / "pr7" / "log-store"),
                  "--temporary-directory", str(helpers / "hr" / "pr7" / "tmp"),
                  "--recorded-inputs-directory", str(helpers / "hr" / "store")],
              json.dumps(calls))
        check("the log-store root and temporary directory are made",
              (helpers / "hr" / "pr7" / "log-store").is_dir()
              and (helpers / "hr" / "pr7" / "tmp").is_dir(), detail)
        check("tripwire-bin is first on PATH",
              calls and all(call["first_path_entry"] == str(helpers / "tripwire-bin")
                            for call in calls), json.dumps(calls))
        check("GIT_DIR does not reach the run",
              calls and all(call["git_dir"] is None for call in calls), json.dumps(calls))
        check("the run starts in the worktrees and outputs directory",
              calls and all(call["cwd"] == str(helpers) for call in calls), json.dumps(calls))
        check("the run's stdout and stderr are kept under hr/pr<n>",
              "SUMMARY: fake summary for pr7-merged"
              in (helpers / "hr" / "pr7" / "stdout").read_text()
              and (helpers / "hr" / "pr7" / "stderr").read_text() == "a line on stderr\n",
              detail)
        check("one line per pull request with its exit code and SUMMARY line",
              completed.stdout.splitlines() == [
                  "PR 7 head test run: exit 0; SUMMARY: fake summary for pr7-merged",
                  "PR 8 head test run: exit 0; SUMMARY: fake summary for pr8-merged"], detail)
        check("every run passing exits 0", completed.returncode == 0, detail)

        completed, calls = run_program(scratch, helpers, {"pr7-merged": 1, "pr8-merged": 4},
                                       "7", "8")
        detail = f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}"
        check("a failed run does not stop the next one", len(calls) == 2, detail)
        check("the first nonzero exit code is the program's",
              completed.returncode == 1
              and "PR 8 head test run: exit 4;" in completed.stdout, detail)

        shutil.rmtree(helpers / "tripwire-bin")
        completed, calls = run_program(scratch, helpers, {}, "7")
        check("a missing tripwire-bin exits 2 before any run",
              completed.returncode == 2 and calls == []
              and "tripwire-bin is missing" in completed.stdout,
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
