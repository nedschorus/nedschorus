#!/usr/bin/env python3
"""Tests for merge-lane-code-review-codex-cell-run-on-pull-request-head.py.

A fake `gh` first on PATH logs its arguments and the GH_TOKEN it saw and
prints a description, or fails when the case says so. A scratch --review-tools-worktree-at-main
holds a fake scripts/code-review-codex-cell.py that logs its arguments and
whether GIT_DIR or GH_TOKEN reached it, writes a report, and exits with the
case's code. The program runs with GIT_DIR set.

Run: python3 scripts/merge-lane-code-review-codex-cell-run-on-pull-request-head-test.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROGRAM = Path(__file__).with_name(
    "merge-lane-code-review-codex-cell-run-on-pull-request-head.py")
TOKEN = "merge-lane-codex-test-token-not-a-credential"
BASE = "0123456789abcdef0123456789abcdef01234567"
DESCRIPTION = "The pull request's description.\n"

FAKE_GH = r'''#!/usr/bin/env python3
import json, os, sys
with open(os.environ["MERGE_LANE_CODEX_TEST_GH_LOG"], "a") as log:
    log.write(json.dumps({"argv": sys.argv[1:], "gh_token": os.environ.get("GH_TOKEN")}) + "\n")
if os.environ.get("MERGE_LANE_CODEX_TEST_GH_FAILS"):
    sys.stderr.write("HTTP 404: Not Found\n")
    sys.exit(1)
sys.stdout.write(os.environ["MERGE_LANE_CODEX_TEST_DESCRIPTION"])
'''

FAKE_CODEX_CELL = r'''#!/usr/bin/env python3
import json, os, sys
argv = sys.argv[1:]
with open(os.environ["MERGE_LANE_CODEX_TEST_CELL_LOG"], "a") as log:
    log.write(json.dumps({"argv": argv, "git_dir": os.environ.get("GIT_DIR"),
                          "gh_token": os.environ.get("GH_TOKEN")}) + "\n")
open(argv[argv.index("--output") + 1], "w").write("the report\n")
print("cell stdout")
print("cell stderr", file=sys.stderr)
sys.exit(int(os.environ.get("MERGE_LANE_CODEX_TEST_CELL_EXIT", "0")))
'''

failures = []


def check(name, condition, detail=""):
    print(("PASS  " if condition else "FAIL  ") + name)
    if not condition:
        failures.append(name)
        if detail:
            print("      " + detail.replace("\n", "\n      "))


def read_log(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def run_program(scratch, helpers, extra_environment=None, home=None):
    for log in ("gh.log", "cell.log"):
        (scratch / log).unlink(missing_ok=True)
    completed = subprocess.run(
        [sys.executable, str(PROGRAM), "7", BASE, "--merge-lane-worktrees-and-outputs-directory", str(helpers),
         "--review-tools-worktree-at-main", str(scratch / "main-checkout")],
        capture_output=True, text=True,
        env={**os.environ,
             "HOME": str(home or scratch / "home"),
             "PATH": f"{scratch / 'bin'}{os.pathsep}{os.environ['PATH']}",
             "GIT_DIR": str(scratch / "no-such-git-directory"),
             "MERGE_LANE_CODEX_TEST_GH_LOG": str(scratch / "gh.log"),
             "MERGE_LANE_CODEX_TEST_CELL_LOG": str(scratch / "cell.log"),
             "MERGE_LANE_CODEX_TEST_DESCRIPTION": DESCRIPTION,
             **(extra_environment or {})})
    return completed, read_log(scratch / "gh.log"), read_log(scratch / "cell.log")


def main():
    # Resolved, because macOS's mkdtemp path is a symlink and the program resolves its paths.
    scratch = Path(tempfile.mkdtemp(prefix="merge-lane-codex-test-")).resolve()
    try:
        (scratch / "bin").mkdir()
        (scratch / "bin" / "gh").write_text(FAKE_GH)
        (scratch / "bin" / "gh").chmod(0o755)
        (scratch / "main-checkout" / "scripts").mkdir(parents=True)
        (scratch / "main-checkout" / "scripts" / "code-review-codex-cell.py").write_text(
            FAKE_CODEX_CELL)
        token_directory = scratch / "home" / ".config" / "nedschorus"
        token_directory.mkdir(parents=True)
        (token_directory / "ned-review-merge.token").write_text(TOKEN + "\n")
        helpers = scratch / "merge-helpers"
        outputs = helpers / "cx" / "pr7-01234567"

        completed, gh_calls, cell_calls = run_program(scratch, helpers)
        detail = f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}"
        check("the description is read from GitHub with the merge account's token",
              gh_calls == [{"argv": ["pr", "view", "7", "--repo", "nedschorus/nedschorus",
                                     "--json", "body", "--jq", ".body"], "gh_token": TOKEN}],
              json.dumps(gh_calls))
        check("the description is saved under cx/pr<n>-<base>",
              (outputs / "description.md").read_text() == DESCRIPTION, detail)
        check("main's review runs on wt/pr<n>-head from the base commit",
              cell_calls and cell_calls[0]["argv"] == [
                  "--base", BASE, "--repo", str(helpers / "wt" / "pr7-head"),
                  "--pull-request-description-file", str(outputs / "description.md"),
                  "--output", str(outputs / "report.md")], json.dumps(cell_calls))
        check("neither GIT_DIR nor the token reaches the review",
              cell_calls and cell_calls[0]["git_dir"] is None
              and cell_calls[0]["gh_token"] is None, json.dumps(cell_calls))
        check("the review's stdout, stderr and report are kept under cx/pr<n>-<base>",
              (outputs / "stdout").read_text() == "cell stdout\n"
              and (outputs / "stderr").read_text() == "cell stderr\n"
              and (outputs / "report.md").read_text() == "the report\n", detail)
        check("one line names the exit code and the report, and the program exits 0",
              completed.returncode == 0 and completed.stdout ==
              f"PR 7 codex cell (base 01234567) exit 0; report {outputs / 'report.md'}\n",
              detail)

        completed, _, _ = run_program(scratch, helpers, {"MERGE_LANE_CODEX_TEST_CELL_EXIT": "3"})
        check("the review's exit code is the program's",
              completed.returncode == 3 and "exit 3;" in completed.stdout,
              f"exit {completed.returncode}\n{completed.stdout}")

        completed, _, cell_calls = run_program(scratch, helpers,
                                               {"MERGE_LANE_CODEX_TEST_GH_FAILS": "1"})
        check("a description gh cannot read exits 2 before the review runs",
              completed.returncode == 2 and cell_calls == []
              and "HTTP 404" in completed.stdout,
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")

        completed, gh_calls, cell_calls = run_program(scratch, helpers,
                                                      home=scratch / "home-with-no-token")
        check("an unreadable token file exits 2 before gh or the review runs",
              completed.returncode == 2 and gh_calls == [] and cell_calls == [],
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")

        blank_home = scratch / "home-with-blank-token"
        (blank_home / ".config" / "nedschorus").mkdir(parents=True)
        (blank_home / ".config" / "nedschorus" / "ned-review-merge.token").write_text(" \n\t\n")
        completed, gh_calls, cell_calls = run_program(scratch, helpers, home=blank_home)
        check("a token file holding only whitespace exits 2 before gh or the review runs",
              completed.returncode == 2 and gh_calls == [] and cell_calls == []
              and "is empty" in completed.stdout,
              f"exit {completed.returncode}\n{completed.stdout}{completed.stderr}")

        cell = scratch / "main-checkout" / "scripts" / "code-review-codex-cell.py"
        cell.rename(cell.with_suffix(".away"))
        completed, gh_calls, cell_calls = run_program(scratch, helpers)
        cell.with_suffix(".away").rename(cell)
        check("a review tools worktree without code-review-codex-cell.py exits 2 before gh runs",
              completed.returncode == 2 and gh_calls == [] and cell_calls == []
              and "code-review-codex-cell.py is missing" in completed.stdout,
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
