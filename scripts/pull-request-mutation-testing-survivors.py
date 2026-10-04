#!/usr/bin/env python3
"""Run mutation testing with cosmic-ray on the lines a pull request changed, and print the survivors.

Usage:
  scripts/pull-request-mutation-testing-survivors.py --pull-request N
  scripts/pull-request-mutation-testing-survivors.py --head COMMIT --base COMMIT
      [--checkout DIR] [--cosmic-ray-venv DIR] [--python INTERPRETER]
      [--recorded-inputs-directory DIR] [--mutant-timeout-seconds S]

The head is checked out in a detached scratch worktree, because cosmic-ray
edits each mutant into the file on disk; the worktree is removed afterwards,
whatever happens. Each changed Python file that is not itself a suite is
mutated on its changed lines only, against the merge base, and each mutant
is tested with every suite whose recorded inputs read that file (the
recordings scripts/run-all-test-suites.py keeps), plus the file's sibling
`<name>-test.py` or `<name>-test.sh` when there is one.

Exit codes: 0 every mutant was killed, 1 a mutant survived or was not run,
or a changed file has no suite, 2 could not run (cosmic-ray missing, a git step failed, the
worktree could not be made, or a suite fails on the unmutated head).
"""

import argparse
import importlib.util
import json
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROGRAM = "pull-request-mutation-testing-survivors"

EXIT_EVERY_MUTANT_KILLED = 0
EXIT_SURVIVORS_OR_UNTESTED_FILES = 1
EXIT_COULD_NOT_RUN = 2

COSMIC_RAY_TOOLS = ("cosmic-ray", "cr-filter-git")
DEFAULT_MUTANT_TIMEOUT_SECONDS = 300.0

TEST_SUITE_RUNNER_PATH = Path(__file__).resolve().with_name("run-all-test-suites.py")


def load_test_suite_runner():
    spec = importlib.util.spec_from_file_location("run_all_test_suites",
                                                  TEST_SUITE_RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CouldNotRun(Exception):
    """A step failed; the message says which and what to do."""


def run(command, cwd, environment=None):
    return subprocess.run(command, cwd=str(cwd), env=environment, text=True,
                          capture_output=True, check=False)


def run_or_raise(command, cwd, environment=None, what=None):
    completed = run(command, cwd, environment)
    if completed.returncode != 0:
        raise CouldNotRun(
            f"{PROGRAM}: {what or ' '.join(command)} failed "
            f"(exit {completed.returncode}): "
            f"{(completed.stderr or completed.stdout).strip()}")
    return completed.stdout


def cosmic_ray_tool_paths(venv):
    """Return {tool: path} for the cosmic-ray commands, or raise naming how to install them."""
    found = {}
    for tool in COSMIC_RAY_TOOLS:
        if venv is not None:
            candidate = Path(venv).expanduser().resolve() / "bin" / tool
            path = str(candidate) if candidate.is_file() else None
        else:
            path = shutil.which(tool)
        if path is None:
            where = (f"in {Path(venv).expanduser() / 'bin'}" if venv is not None
                     else "on PATH")
            raise CouldNotRun(
                f"{PROGRAM}: not run — {tool} is not {where}.\n"
                f"Install cosmic-ray into a venv of its own, not globally:\n"
                f"  python3 -m venv /tmp/cosmic-ray-venv\n"
                f"  /tmp/cosmic-ray-venv/bin/pip install cosmic-ray\n"
                f"Then run this again with --cosmic-ray-venv /tmp/cosmic-ray-venv.")
        found[tool] = path
    return found


def head_and_base_of_pull_request(number, checkout):
    """Return (head commit, base ref) of a pull request, fetching both."""
    view = json.loads(run_or_raise(
        ["gh", "pr", "view", str(number), "--json", "headRefOid,baseRefName"],
        checkout, what=f"gh pr view {number}"))
    head, base_branch = view["headRefOid"], view["baseRefName"]
    run_or_raise(["git", "fetch", "--quiet", "origin", base_branch, head],
                 checkout, what=f"git fetch origin {base_branch} {head}")
    return head, f"origin/{base_branch}"


def changed_python_files_to_mutate(checkout, merge_base, head):
    """Changed or added Python files at head, suites excluded."""
    listed = run_or_raise(
        ["git", "diff", "--name-only", "--diff-filter=AM", merge_base, head,
         "--", "*.py"], checkout, what="git diff --name-only")
    return [path for path in listed.splitlines()
            if path and not path.endswith("-test.py")]


def suites_for_file(path, suites_at_head, recordings_directory, runner):
    """Suites whose recorded inputs read the file, plus its sibling suite."""
    chosen = []
    for suite in suites_at_head:
        recording = runner.load_recording(recordings_directory, suite)
        if (isinstance(recording, dict) and recording.get("exit") == 0
                and path in recording.get("reads", {})):
            chosen.append(suite)
    stem = path[:-len(".py")]
    for sibling in (f"{stem}-test.py", f"{stem}-test.sh"):
        if sibling in suites_at_head and sibling not in chosen:
            chosen.append(sibling)
    return chosen


def test_command_for(suites, interpreter):
    # The same launch the suite runner uses, so a suite judged by its exit code here is judged the same way there.
    chain = " && ".join(
        f"sh {shlex.quote(suite)}" if suite.endswith("-test.sh")
        else f"{shlex.quote(interpreter)} -u {shlex.quote(suite)}"
        for suite in suites)
    # cosmic-ray splits the command with shlex and runs it without a shell, so && needs sh -c.
    return f"sh -c {shlex.quote(chain)}"


def cosmic_ray_config_text(module_path, test_command, merge_base,
                           mutant_timeout_seconds):
    return (
        "[cosmic-ray]\n"
        f"module-path = {json.dumps(module_path)}\n"
        f"timeout = {float(mutant_timeout_seconds)!r}\n"
        "excluded-modules = []\n"
        f"test-command = {json.dumps(test_command)}\n"
        "\n"
        "[cosmic-ray.distributor]\n"
        "name = \"local\"\n"
        "\n"
        "[cosmic-ray.filters.git-filter]\n"
        f"branch = {json.dumps(merge_base)}\n")


def outcomes_from_dump(dump_text):
    """Return (counts, survivors) from `cosmic-ray dump` output."""
    counts = {"killed": 0, "survived": 0, "incompetent": 0, "skipped": 0,
              "not run": 0}
    survivors = []
    for line in dump_text.splitlines():
        if not line.strip():
            continue
        item, result = json.loads(line)
        if result is None:
            counts["not run"] += 1
            continue
        if result.get("worker_outcome") == "skipped":
            counts["skipped"] += 1
            continue
        outcome = result.get("test_outcome")
        if outcome == "survived":
            counts["survived"] += 1
            mutation = item["mutations"][0]
            survivors.append({
                "module_path": mutation["module_path"],
                "line": mutation["start_pos"][0],
                "operator": mutation["operator_name"],
                "diff": result.get("diff") or "",
            })
        elif outcome == "killed":
            counts["killed"] += 1
        else:
            counts["incompetent"] += 1
    return counts, survivors


def mutation_test_one_file(path, suites, worktree, scratch, tools, merge_base,
                           arguments, environment):
    """Run cosmic-ray on one file's changed lines; return (counts, survivors)."""
    name = path.replace("/", "__")
    config = scratch / f"{name}.toml"
    session = scratch / f"{name}.sqlite"
    config.write_text(cosmic_ray_config_text(
        path, test_command_for(suites, arguments.python), merge_base,
        arguments.mutant_timeout_seconds))
    cosmic_ray = tools["cosmic-ray"]
    baseline = run([cosmic_ray, "baseline", str(config)], worktree, environment)
    if baseline.returncode != 0:
        raise CouldNotRun(
            f"{PROGRAM}: not run — the suites for {path} fail on the unmutated "
            f"head, so no mutant can be judged: "
            f"{' '.join(suites)}\n{(baseline.stderr or baseline.stdout).strip()}")
    run_or_raise([cosmic_ray, "init", str(config), str(session)], worktree,
                 environment, what=f"cosmic-ray init for {path}")
    run_or_raise([tools["cr-filter-git"], "--config", str(config), str(session)],
                 worktree, environment, what=f"cr-filter-git for {path}")
    run_or_raise([cosmic_ray, "exec", str(config), str(session)], worktree,
                 environment, what=f"cosmic-ray exec for {path}")
    return outcomes_from_dump(run_or_raise(
        [cosmic_ray, "dump", str(session)], worktree, environment,
        what=f"cosmic-ray dump for {path}"))


def remove_worktree(checkout, worktree):
    removed = run(["git", "worktree", "remove", "--force", str(worktree)], checkout)
    if removed.returncode != 0 and worktree.exists():
        print(f"{PROGRAM}: could not remove the scratch worktree {worktree}: "
              f"{removed.stderr.strip()}\n"
              f"Remove it with: git worktree remove --force {worktree}",
              file=sys.stderr)


def parse_arguments(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--pull-request", type=int,
                       help="the pull request to test; its head and base are read with gh and fetched")
    which.add_argument("--head", help="the head commit to test (needs --base)")
    parser.add_argument("--base", help="the base the head is compared with (with --head)")
    parser.add_argument("--checkout", default=str(Path(__file__).resolve().parent.parent),
                        help="the checkout the worktree is made from; default, the one this file is in")
    parser.add_argument("--cosmic-ray-venv", default=None,
                        help="a venv holding cosmic-ray; default, cosmic-ray on PATH")
    parser.add_argument("--python", default=sys.executable,
                        help="the interpreter that runs each Python suite; default, this one")
    parser.add_argument("--recorded-inputs-directory", default=None,
                        help="where the suite runner keeps recorded inputs; default, the runner's")
    parser.add_argument("--mutant-timeout-seconds", type=float,
                        default=DEFAULT_MUTANT_TIMEOUT_SECONDS,
                        help=f"how long one mutant's suites may run (default {DEFAULT_MUTANT_TIMEOUT_SECONDS:g})")
    arguments = parser.parse_args(argv)
    if arguments.head is not None and arguments.base is None:
        parser.error("--head needs --base")
    if arguments.pull_request is not None and arguments.base is not None:
        parser.error("--base goes with --head; a pull request's base is read with gh")
    return arguments


def main(argv=None):
    arguments = parse_arguments(argv)
    checkout = Path(arguments.checkout).resolve()
    runner = load_test_suite_runner()
    try:
        tools = cosmic_ray_tool_paths(arguments.cosmic_ray_venv)
        if arguments.pull_request is not None:
            head, base = head_and_base_of_pull_request(arguments.pull_request, checkout)
        else:
            head, base = arguments.head, arguments.base
        head = run_or_raise(["git", "rev-parse", "--verify", f"{head}^{{commit}}"],
                            checkout, what=f"git rev-parse {head}").strip()
        merge_base = run_or_raise(["git", "merge-base", head, base], checkout,
                                  what=f"git merge-base {head} {base}").strip()
        files = changed_python_files_to_mutate(checkout, merge_base, head)
        recordings_directory = runner.recordings_directory_for(
            arguments.recorded_inputs_directory
            or runner.DEFAULT_RECORDED_INPUTS_DIRECTORY, checkout)
        suites_at_head = [path for path in run_or_raise(
            ["git", "ls-tree", "-r", "--name-only", head], checkout,
            what="git ls-tree").splitlines()
            if path.endswith(("-test.py", "-test.sh"))]
        environment = runner.environment_without_git_redirecting_variables()

        totals = {"killed": 0, "survived": 0, "incompetent": 0, "skipped": 0,
                  "not run": 0}
        untested = []
        with tempfile.TemporaryDirectory(prefix=f"{PROGRAM}-") as scratch_name:
            scratch = Path(scratch_name)
            worktree = scratch / "worktree"
            run_or_raise(["git", "worktree", "add", "--detach", str(worktree), head],
                         checkout, what=f"git worktree add at {head}")
            try:
                for path in files:
                    suites = suites_for_file(path, suites_at_head,
                                             recordings_directory, runner)
                    if not suites:
                        untested.append(path)
                        print(f"NO SUITE  {path}: no recorded suite reads it and it "
                              f"has no sibling suite, so its changed lines are untested")
                        continue
                    print(f"MUTATING  {path} with {', '.join(suites)}", flush=True)
                    counts, survivors = mutation_test_one_file(
                        path, suites, worktree, scratch, tools, merge_base,
                        arguments, environment)
                    for key in totals:
                        totals[key] += counts[key]
                    for survivor in survivors:
                        print(f"SURVIVED  {survivor['module_path']}:{survivor['line']} "
                              f"{survivor['operator']}")
                        for diff_line in survivor["diff"].splitlines():
                            print(f"    {diff_line}")
            finally:
                remove_worktree(checkout, worktree)
    except CouldNotRun as failure:
        print(str(failure), file=sys.stderr)
        return EXIT_COULD_NOT_RUN

    tested = totals["killed"] + totals["survived"] + totals["incompetent"]
    print(f"SUMMARY: {tested} mutants on changed lines of {len(files) - len(untested)} "
          f"file(s): {totals['killed']} killed, {totals['survived']} survived, "
          f"{totals['incompetent']} incompetent, {totals['not run']} not run; "
          f"{len(untested)} changed file(s) "
          f"with no suite; head {head[:12]}, merge base {merge_base[:12]}")
    if totals["survived"] or totals["not run"] or untested:
        return EXIT_SURVIVORS_OR_UNTESTED_FILES
    return EXIT_EVERY_MUTANT_KILLED


if __name__ == "__main__":
    sys.exit(main())
