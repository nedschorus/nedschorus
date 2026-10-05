#!/usr/bin/env python3
"""Run mutation testing with cosmic-ray on the lines a pull request changed, and print the survivors.

Usage:
  scripts/pull-request-mutation-testing-survivors.py --pull-request N
  scripts/pull-request-mutation-testing-survivors.py --head COMMIT --base COMMIT
      [--checkout DIR] [--cosmic-ray-venv DIR] [--python INTERPRETER]
      [--recorded-inputs-directory DIR] [--mutant-timeout-seconds S]
      [--lock-file PATH]

The head is checked out in a detached scratch worktree, because cosmic-ray
edits each mutant into the file on disk; the worktree is removed afterwards,
whatever happens. Each changed Python file that is not itself a suite is
mutated on its changed lines only, against the merge base, and each mutant
is tested with every suite whose recorded inputs read that file (the
recordings scripts/run-all-test-suites.py keeps), plus the file's sibling
`<name>-test.py` or `<name>-test.sh` when there is one.

While cosmic-ray runs, the script holds the lock scripts/run-all-test-suites.py
takes (--lock-file, default ~/.claude/.run-all-test-suites.lock), because each
mutant is a test run and two test runs on one machine disturb each other. It
takes the lock without waiting: when another process holds it, the script
exits 3 at once, before making the worktree. Do not run the script under
`flock` on that lock; the script takes the lock itself, so the flock would be
the holder it refuses on.

Each mutant's suites run in the signal sandbox scripts/run-all-test-suites.py
uses, so a mutant that aims a signal at the wrong process can reach only the
suite's own processes; when bwrap is on PATH but cannot start, the script
exits 2.

A renamed file is mutated under its new name. A mutant cosmic-ray could not
judge, because its worker raised, its suites could not be launched, or its
suites ran past --mutant-timeout-seconds, is printed as ERRORED and counts
against the run like a survivor. cosmic-ray itself reports a timeout as a
kill; this script does not.

Exit codes: 0 every mutant was killed, 1 a mutant survived, errored or was
not run, or a changed file has no suite, 2 could not run (cosmic-ray missing,
a git step failed, the head commit is already in the base, the worktree could
not be made, or a suite fails or cannot be launched on the unmutated head),
3 not run because another process holds the lock.
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
EXIT_LOCKED = 3

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


def head_and_base_of_pull_request(number, checkout, environment):
    """Return (head commit, base ref) of a pull request, fetching both."""
    view = json.loads(run_or_raise(
        ["gh", "pr", "view", str(number), "--json", "headRefOid,baseRefName"],
        checkout, environment, what=f"gh pr view {number}"))
    head, base_branch = view["headRefOid"], view["baseRefName"]
    run_or_raise(["git", "fetch", "--quiet", "origin", base_branch, head],
                 checkout, environment,
                 what=f"git fetch origin {base_branch} {head}")
    return head, f"origin/{base_branch}"


def changed_python_files_to_mutate(checkout, merge_base, head, environment):
    """Changed, added or renamed Python files at head, by their head names, suites excluded."""
    # R keeps a renamed-and-changed file, which --name-only lists by its new
    # name, the name cr-filter-git's own rename-detecting diff uses.
    listed = run_or_raise(
        ["git", "diff", "--name-only", "--diff-filter=AMR", merge_base, head,
         "--", "*.py"], checkout, environment, what="git diff --name-only")
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


def test_command_for(suites, interpreter, sandbox_prefix=(), suites_outside_sandbox=()):
    # The same launch the suite runner uses, so a suite judged by its exit code here is judged the same way there.
    # A mutant can aim a signal anywhere, so each suite runs inside the runner's signal sandbox.
    chain = " && ".join(
        shlex.join([*(() if suite in suites_outside_sandbox else sandbox_prefix),
                    *(["sh", suite] if suite.endswith("-test.sh")
                      else [interpreter, "-u", suite])])
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


OUTCOME_KEYS = ("killed", "survived", "errored", "no mutation", "skipped",
                "not run")

# cosmic-ray reports a worker that raised as exception/incompetent, and a test
# command it could not launch as normal/incompetent: errors of the run, not
# properties of the mutant. A no-test worker found nothing to mutate.
WORKER_OUTCOMES_THAT_ERRORED = ("exception", "abnormal")

# cosmic-ray reports suites that ran past the timeout as killed, with exactly
# this output: a slow run, not a test that failed under the mutant.
TIMED_OUT_OUTPUT = "timeout"


def mutant_description(item, result, reason=""):
    mutation = item["mutations"][0]
    return {
        "module_path": mutation["module_path"],
        "line": mutation["start_pos"][0],
        "operator": mutation["operator_name"],
        "diff": result.get("diff") or "",
        "reason": reason,
    }


def outcomes_from_dump(dump_text):
    """Return (counts, survivors, errored) from `cosmic-ray dump` output."""
    counts = dict.fromkeys(OUTCOME_KEYS, 0)
    survivors = []
    errored = []
    for line in dump_text.splitlines():
        if not line.strip():
            continue
        item, result = json.loads(line)
        if result is None:
            counts["not run"] += 1
            continue
        worker_outcome = result.get("worker_outcome")
        test_outcome = result.get("test_outcome")
        if worker_outcome == "skipped":
            counts["skipped"] += 1
        elif worker_outcome == "no-test":
            counts["no mutation"] += 1
        elif (worker_outcome not in WORKER_OUTCOMES_THAT_ERRORED
              and test_outcome == "survived"):
            counts["survived"] += 1
            survivors.append(mutant_description(item, result))
        elif (worker_outcome not in WORKER_OUTCOMES_THAT_ERRORED
              and test_outcome == "killed"
              and result.get("output") == TIMED_OUT_OUTPUT):
            counts["errored"] += 1
            errored.append(mutant_description(item, result, reason="timeout"))
        elif (worker_outcome not in WORKER_OUTCOMES_THAT_ERRORED
              and test_outcome == "killed"):
            counts["killed"] += 1
        else:
            counts["errored"] += 1
            errored.append(mutant_description(item, result))
    return counts, survivors, errored


def mutation_test_one_file(path, suites, worktree, scratch, tools, merge_base,
                           arguments, environment, sandbox_prefix=(),
                           suites_outside_sandbox=()):
    """Run cosmic-ray on one file's changed lines; return (counts, survivors, errored)."""
    name = path.replace("/", "__")
    config = scratch / f"{name}.toml"
    session = scratch / f"{name}.sqlite"
    baseline_session = scratch / f"{name}.baseline.sqlite"
    config.write_text(cosmic_ray_config_text(
        path, test_command_for(suites, arguments.python, sandbox_prefix,
                               suites_outside_sandbox), merge_base,
        arguments.mutant_timeout_seconds))
    cosmic_ray = tools["cosmic-ray"]
    baseline = run([cosmic_ray, "baseline", "--session-file",
                    str(baseline_session), str(config)], worktree, environment)
    if baseline.returncode != 0:
        raise CouldNotRun(
            f"{PROGRAM}: not run — the suites for {path} fail on the unmutated "
            f"head, so no mutant can be judged: "
            f"{' '.join(suites)}\n{(baseline.stderr or baseline.stdout).strip()}")
    # cosmic-ray's baseline exits 0 unless the suites failed, so a suite it
    # could not launch at all passes it; only a survived baseline means they ran.
    baseline_results = [json.loads(line) for line in run_or_raise(
        [cosmic_ray, "dump", str(baseline_session)], worktree, environment,
        what=f"cosmic-ray dump of the baseline for {path}").splitlines()
        if line.strip()]
    if not any(result and result.get("test_outcome") == "survived"
               for _, result in baseline_results):
        raise CouldNotRun(
            f"{PROGRAM}: not run — the suites for {path} could not be run on "
            f"the unmutated head, so no mutant can be judged: "
            f"{' '.join(suites)}\n"
            + "\n".join((result or {}).get("output") or ""
                        for _, result in baseline_results).strip())
    run_or_raise([cosmic_ray, "init", str(config), str(session)], worktree,
                 environment, what=f"cosmic-ray init for {path}")
    run_or_raise([tools["cr-filter-git"], "--config", str(config), str(session)],
                 worktree, environment, what=f"cr-filter-git for {path}")
    run_or_raise([cosmic_ray, "exec", str(config), str(session)], worktree,
                 environment, what=f"cosmic-ray exec for {path}")
    return outcomes_from_dump(run_or_raise(
        [cosmic_ray, "dump", str(session)], worktree, environment,
        what=f"cosmic-ray dump for {path}"))


def remove_worktree(checkout, worktree, environment):
    removed = run(["git", "worktree", "remove", "--force", str(worktree)], checkout,
                  environment)
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
    parser.add_argument("--lock-file", default=None,
                        help="the lock that keeps test runs on one machine apart; "
                             "default, the suite runner's")
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
    # An inherited GIT_DIR or GIT_WORK_TREE would point every git command at another repository.
    environment = runner.environment_without_git_redirecting_variables()
    try:
        tools = cosmic_ray_tool_paths(arguments.cosmic_ray_venv)
        if arguments.pull_request is not None:
            head, base = head_and_base_of_pull_request(arguments.pull_request,
                                                       checkout, environment)
        else:
            head, base = arguments.head, arguments.base
        head = run_or_raise(["git", "rev-parse", "--verify", f"{head}^{{commit}}"],
                            checkout, environment,
                            what=f"git rev-parse {head}").strip()
        merge_base = run_or_raise(["git", "merge-base", head, base], checkout,
                                  environment,
                                  what=f"git merge-base {head} {base}").strip()
        if merge_base == head:
            number = (arguments.pull_request if arguments.pull_request is not None
                      else "<number>")
            raise CouldNotRun(
                f"{PROGRAM}: not run — head {head[:12]} is already in {base}, so "
                f"there are no changed lines to test. Either the pull request is "
                f"merged, or it adds no commits of its own.\n"
                f"If it is merged and you want to test what it changed:\n"
                f"  gh pr view {number} --json headRefOid,baseRefOid\n"
                f"  git fetch origin <baseRefOid>\n"
                f"  then run this again with --head <headRefOid> --base <baseRefOid>.\n"
                f"If it adds no commits of its own, there is nothing to test.")
        files = changed_python_files_to_mutate(checkout, merge_base, head,
                                               environment)
        recordings_directory = runner.recordings_directory_for(
            arguments.recorded_inputs_directory
            or runner.DEFAULT_RECORDED_INPUTS_DIRECTORY, checkout)
        suites_at_head = [path for path in run_or_raise(
            ["git", "ls-tree", "-r", "--name-only", head], checkout,
            environment, what="git ls-tree").splitlines()
            if path.endswith(("-test.py", "-test.sh"))]

        try:
            sandbox_prefix, unconfined_because = runner.signal_sandbox()
        except runner.SignalSandboxCouldNotStart as error:
            raise CouldNotRun(runner.signal_sandbox_refusal(error, PROGRAM)) from error
        print(runner.signal_sandbox_line(sandbox_prefix, unconfined_because), flush=True)

        totals = dict.fromkeys(OUTCOME_KEYS, 0)
        untested = []
        lock_file = Path(arguments.lock_file or runner.DEFAULT_LOCK_FILE).expanduser()
        lock_handle, holder, previous_holder = runner.take_machine_lock(lock_file, checkout)
        if lock_handle is None:
            print(f"{PROGRAM}: not run — another process holds {lock_file}, the lock "
                  f"that keeps test runs on one machine apart. Its last recorded "
                  f"holder: {holder}.\n"
                  f"If you started this script under flock on that lock, that flock "
                  f"is the holder: run this script without flock, since it takes "
                  f"the lock itself.\n"
                  f"Otherwise, run this again after the run holding the lock has "
                  f"finished.", file=sys.stderr)
            return EXIT_LOCKED
        # Taking the lock overwrites the holder's log directory, so a killed suite
        # run's traces are removed here or never.
        runner.remove_traces_the_last_lock_holder_left(previous_holder)
        with tempfile.TemporaryDirectory(prefix=f"{PROGRAM}-") as scratch_name:
            scratch = Path(scratch_name)
            worktree = scratch / "worktree"
            try:
                # Released before the worktree is removed: removing it is not a test run.
                with lock_handle:
                    run_or_raise(["git", "worktree", "add", "--detach", str(worktree),
                                  head], checkout, environment,
                                 what=f"git worktree add at {head}")
                    for path in files:
                        suites = suites_for_file(path, suites_at_head,
                                                 recordings_directory, runner)
                        if not suites:
                            untested.append(path)
                            print(f"NO SUITE  {path}: no recorded suite reads it and it "
                                  f"has no sibling suite, so its changed lines are untested")
                            continue
                        print(f"MUTATING  {path} with {', '.join(suites)}", flush=True)
                        outside = runner.SUITES_RUN_OUTSIDE_THE_SIGNAL_SANDBOX
                        for suite in suites:
                            if sandbox_prefix and suite in outside:
                                print(f"NO SANDBOX  {suite} runs WITHOUT the signal "
                                      f"sandbox: {outside[suite]}", flush=True)
                        counts, survivors, errored = mutation_test_one_file(
                            path, suites, worktree, scratch, tools, merge_base,
                            arguments, environment, sandbox_prefix, outside)
                        for key in totals:
                            totals[key] += counts[key]
                        for label, mutants in (("SURVIVED", survivors),
                                               ("ERRORED ", errored)):
                            for mutant in mutants:
                                reason = (f" ({mutant['reason']}: the suites ran past "
                                          "--mutant-timeout-seconds, so this mutant was "
                                          "not judged; rerun when the machine is quieter)"
                                          if mutant["reason"] else "")
                                print(f"{label}  {mutant['module_path']}:{mutant['line']} "
                                      f"{mutant['operator']}{reason}")
                                for diff_line in mutant["diff"].splitlines():
                                    print(f"    {diff_line}")
            finally:
                remove_worktree(checkout, worktree, environment)
    except CouldNotRun as failure:
        print(str(failure), file=sys.stderr)
        return EXIT_COULD_NOT_RUN

    tested = totals["killed"] + totals["survived"] + totals["errored"]
    print(f"SUMMARY: {tested} mutants on changed lines of {len(files) - len(untested)} "
          f"file(s): {totals['killed']} killed, {totals['survived']} survived, "
          f"{totals['errored']} errored, {totals['not run']} not run; "
          f"{len(untested)} changed file(s) "
          f"with no suite; head {head[:12]}, merge base {merge_base[:12]}")
    if totals["survived"] or totals["errored"] or totals["not run"] or untested:
        return EXIT_SURVIVORS_OR_UNTESTED_FILES
    return EXIT_EVERY_MUTANT_KILLED


if __name__ == "__main__":
    sys.exit(main())
