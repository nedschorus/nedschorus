#!/usr/bin/env python3
"""Tests for merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget.py.

The program is loaded by path and its main() is called in this process, with
merge-gate.sh replaced by a fake gate and a fake `gh` first on PATH. The fake
gate answers each run from a numbered output file and exit code the case
writes. The fake `gh` logs every call with the GH_TOKEN it saw and answers
from a routes file the case writes; it does not filter `gh pr list` by base
branch, so the program's own filter is what each stacked case tests. The
waits between gate runs go to a list instead of sleeping.

Run: python3 scripts/merge-lane-pull-request-merge-through-merge-gate-with-stacked-pull-request-retarget-test.py
"""

import contextlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

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
count=$(wc -l < "$directory/gate-calls.log")
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
sys.stdout.write(route.get("stdout", ""))
sys.stderr.write(route.get("stderr", ""))
sys.exit(route.get("exit", 0))
'''

failures = []


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


def run_case(scratch, name, gate_answers, routes, token=TOKEN):
    """Run main() once; return (exit code, output, gh calls, gate calls, waits)."""
    directory = scratch / name
    directory.mkdir()
    bin_directory = directory / "bin"
    bin_directory.mkdir()
    (bin_directory / "gh").write_text(FAKE_GH)
    (bin_directory / "gh").chmod(0o755)
    gate = directory / "merge-gate.sh"
    gate.write_text(FAKE_GATE)
    for number, (output, exit_code) in enumerate(gate_answers, start=1):
        (directory / f"gate-{number}.out").write_text(output)
        (directory / f"gate-{number}.exit").write_text(str(exit_code))
    (directory / "gate-last.out").write_text(gate_answers[-1][0])
    (directory / "gate-last.exit").write_text(str(gate_answers[-1][1]))
    (directory / "gh-routes.json").write_text(json.dumps(routes))
    token_file = directory / "token"
    if token is not None:
        token_file.write_text(token + "\n")

    waits = []
    saved_path, saved_gate = os.environ["PATH"], program.MERGE_GATE_SCRIPT
    os.environ["PATH"] = f"{bin_directory}{os.pathsep}{saved_path}"
    os.environ["MERGE_LANE_MERGE_TEST_DIRECTORY"] = str(directory)
    program.MERGE_GATE_SCRIPT = gate
    output = io.StringIO()
    try:
        with contextlib.redirect_stdout(output):
            exit_code = program.main([PULL_REQUEST, HEAD, SINCE, "--token-file", str(token_file)],
                                     wait=waits.append)
    finally:
        os.environ["PATH"], program.MERGE_GATE_SCRIPT = saved_path, saved_gate
    gh_log = directory / "gh-calls.log"
    gh_calls = ([json.loads(line) for line in gh_log.read_text().splitlines()]
                if gh_log.exists() else [])
    gate_log = directory / "gate-calls.log"
    gate_calls = gate_log.read_text().splitlines() if gate_log.exists() else []
    return exit_code, output.getvalue(), gh_calls, gate_calls, waits


def argvs(gh_calls):
    return [call["argv"] for call in gh_calls]


def index_of(calls, prefix):
    for index, argv in enumerate(calls):
        if argv[:len(prefix)] == prefix:
            return index
    return None


def main():
    scratch = Path(tempfile.mkdtemp(prefix="merge-lane-merge-test-"))
    try:
        exit_code, output, gh_calls, gate_calls, waits = run_case(
            scratch, "stacked", [(GATE_PASSED, 0)], default_routes(STACKED_AND_NOT))
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
        check("the gate runs with the three arguments, once",
              gate_calls == [f"{PULL_REQUEST} {HEAD} {SINCE}"], repr(gate_calls))
        check("every gh call carries the token file's token",
              gh_calls and all(call["gh_token"] == TOKEN for call in gh_calls),
              json.dumps(gh_calls))
        check("the retarget is printed with how to undo it",
              f"retargeted pull request #20 from {BRANCH} to main" in output
              and f"--base {BRANCH}" in output, output)
        check("a merged pull request exits 0 and prints its state after the merge",
              exit_code == 0 and '{"state":"MERGED"}' in output, f"exit {exit_code}\n{output}")

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
              exit_code == 1 and gh_calls == [] and "STOP: not merged" in output,
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
            default_routes(STACKED_AND_NOT, merge_exit=1))
        check("a merge that fails exits 1", exit_code == 1 and "merge exit 1" in output,
              f"exit {exit_code}\n{output}")

        exit_code, output, gh_calls, gate_calls, _ = run_case(
            scratch, "no-token", [(GATE_PASSED, 0)], default_routes(STACKED_AND_NOT),
            token=None)
        check("an unreadable token file exits 2 before the gate or gh runs",
              exit_code == 2 and gate_calls == [] and gh_calls == [],
              f"exit {exit_code}\n{output}")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    if failures:
        print(f"\n{len(failures)} case(s) failed")
        return 1
    print("\nall cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
