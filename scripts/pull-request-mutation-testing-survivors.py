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

On Linux with bwrap each mutant's suites run in test sandboxes of their own, as
scripts/run-all-test-suites.py runs them, so the script takes no lock and
overlaps other test runs; the admission scripts/run-all-test-suites.py uses
decides when each file's mutants start, they hold one of its slots while they
run, at low priority, and a suite that runs without any sandbox first
takes the lock those suites share with every other run. Elsewhere, while cosmic-ray runs, the script holds the
lock scripts/run-all-test-suites.py takes (--lock-file, default
~/.claude/.run-all-test-suites.lock), because each mutant is a test run and two
test runs sharing the machine disturb each other. It takes the lock without
waiting: when another process holds it, the script
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
import contextlib
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

_git_output_spec = importlib.util.spec_from_file_location(
    "git_machine_readable_output_runner_and_parser_common",
    Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
    / "git-machine-readable-output-runner-and-parser-common.py")
git_output = importlib.util.module_from_spec(_git_output_spec)
_git_output_spec.loader.exec_module(git_output)


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
        ["git", "diff", "-z", "--name-only", "--diff-filter=AMR", merge_base, head,
         "--", "*.py"], checkout, environment, what="git diff --name-only")
    return [path for path in git_output.nul_separated_fields(listed)
            if not path.endswith("-test.py")]


def suites_at_head(checkout, head, environment):
    """The test suites git tracks at head."""
    listed = run_or_raise(["git", "ls-tree", "-r", "-z", "--name-only", head], checkout,
                          environment, what="git ls-tree")
    return [path for path in git_output.nul_separated_fields(listed)
            if path.endswith(("-test.py", "-test.sh"))]


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


def test_command_for(suites, interpreter, sandbox_prefix=(), suites_outside_sandbox=(),
                     started_proofs=None, sandbox_did_not_start_file=None):
    # The same launch the suite runner uses, so a suite judged by its exit code here is judged the same way there.
    # A mutant can aim a signal anywhere, so each suite runs inside the runner's signal sandbox.
    # sandbox_prefix is one prefix for every suite, or a mapping of each suite to its own.
    # cosmic-ray counts any failing exit as a killed mutant, so a sandbox that does not
    # start would kill every mutant: with started_proofs, a mapping of each sandboxed suite
    # to a file bound writable in its sandbox, the suite writes its proof inside before it
    # runs, and a suite whose proof stays empty is named in sandbox_did_not_start_file.
    def prefix_of(suite):
        if suite in suites_outside_sandbox:
            return ()
        return sandbox_prefix[suite] if isinstance(sandbox_prefix, dict) else sandbox_prefix

    def launch(suite):
        command = ["sh", suite] if suite.endswith("-test.sh") else [interpreter, "-u", suite]
        prefix = prefix_of(suite)
        proof = (started_proofs or {}).get(suite)
        if not prefix or proof is None:
            return shlex.join([*prefix, *command])
        inside = shlex.join([*prefix, "sh", "-c", 'echo started > "$0" && exec "$@"',
                             str(proof), *command])
        return (f"{{ : > {shlex.quote(str(proof))}; {inside}; status=$?; "
                f"[ -s {shlex.quote(str(proof))} ] || "
                f"echo {shlex.quote(suite)} >> {shlex.quote(str(sandbox_did_not_start_file))}; "
                f"[ $status -eq 0 ]; }}")

    chain = " && ".join(launch(suite) for suite in suites)
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


def raise_when_a_test_sandbox_did_not_start(sandbox_did_not_start_file, path, step):
    """Stop the run when a suite's test sandbox did not start, which cosmic-ray counts as a kill."""
    try:
        named = sandbox_did_not_start_file.read_text().split()
    except FileNotFoundError:
        return
    raise CouldNotRun(
        f"{PROGRAM}: not run to the end — during the {step} for {path}, the test sandbox of "
        f"{', '.join(sorted(set(named)))} did not start, so cosmic-ray would have counted a "
        f"mutant as killed that no suite judged.\n"
        f"Run scripts/run-suite-in-signal-sandbox.py on that suite to see bwrap's message, fix "
        f"what it names, then run this again.")


def mutation_test_one_file(path, suites, worktree, scratch, tools, merge_base,
                           arguments, environment, sandbox_prefix=(),
                           suites_outside_sandbox=(), nice_prefix=(), started_proofs=None):
    """Run cosmic-ray on one file's changed lines; return (counts, survivors, errored).

    nice_prefix goes before each cosmic-ray command, so the suites it runs inherit it.
    started_proofs maps each suite in a test sandbox to its proof file, as test_command_for
    takes it; a sandbox that did not start stops the run."""
    name = path.replace("/", "__")
    config = scratch / f"{name}.toml"
    session = scratch / f"{name}.sqlite"
    baseline_session = scratch / f"{name}.baseline.sqlite"
    did_not_start = scratch / f"{name}.test-sandbox-did-not-start"
    config.write_text(cosmic_ray_config_text(
        path, test_command_for(suites, arguments.python, sandbox_prefix,
                               suites_outside_sandbox, started_proofs, did_not_start),
        merge_base, arguments.mutant_timeout_seconds))
    cosmic_ray = [*nice_prefix, tools["cosmic-ray"]]
    baseline = run([*cosmic_ray, "baseline", "--session-file",
                    str(baseline_session), str(config)], worktree, environment)
    raise_when_a_test_sandbox_did_not_start(did_not_start, path, "baseline")
    if baseline.returncode != 0:
        raise CouldNotRun(
            f"{PROGRAM}: not run — the suites for {path} fail on the unmutated "
            f"head, so no mutant can be judged: "
            f"{' '.join(suites)}\n{(baseline.stderr or baseline.stdout).strip()}")
    # cosmic-ray's baseline exits 0 unless the suites failed, so a suite it
    # could not launch at all passes it; only a survived baseline means they ran.
    baseline_results = [json.loads(line) for line in run_or_raise(
        [*cosmic_ray, "dump", str(baseline_session)], worktree, environment,
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
    run_or_raise([*cosmic_ray, "init", str(config), str(session)], worktree,
                 environment, what=f"cosmic-ray init for {path}")
    run_or_raise([tools["cr-filter-git"], "--config", str(config), str(session)],
                 worktree, environment, what=f"cr-filter-git for {path}")
    run_or_raise([*cosmic_ray, "exec", str(config), str(session)], worktree,
                 environment, what=f"cosmic-ray exec for {path}")
    raise_when_a_test_sandbox_did_not_start(did_not_start, path, "mutants' runs")
    return outcomes_from_dump(run_or_raise(
        [*cosmic_ray, "dump", str(session)], worktree, environment,
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
    # An inherited GIT_DIR or GIT_WORK_TREE would point every git command at another repository,
    # and cosmic-ray launches the suites with this environment, as the runner launches them.
    environment = runner.launch_environment_for_a_test_suite_with_git_redirecting_agent_session_attendance_and_credential_variables_removed()
    try:
        tools = cosmic_ray_tool_paths(arguments.cosmic_ray_venv)
        if arguments.pull_request is not None:
            # gh needs the credential that the suites' environment leaves out.
            head, base = head_and_base_of_pull_request(
                arguments.pull_request, checkout,
                runner.environment_without_git_redirecting_variables())
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
        try:
            recordings_directory = runner.recordings_directory_for(
                arguments.recorded_inputs_directory
                or runner.DEFAULT_RECORDED_INPUTS_DIRECTORY, checkout)
        except runner.CouldNotRun as refusal:
            raise CouldNotRun(str(refusal).replace(f"{runner.PROGRAM}:", f"{PROGRAM}:", 1)) \
                from refusal
        suites_listed_at_head = suites_at_head(checkout, head, environment)

        try:
            sandbox_prefix, unconfined_because = runner.signal_sandbox()
        except runner.SignalSandboxCouldNotStart as error:
            raise CouldNotRun(runner.signal_sandbox_refusal(error, PROGRAM)) from error
        print(runner.signal_sandbox_line(sandbox_prefix, unconfined_because), flush=True)

        totals = dict.fromkeys(OUTCOME_KEYS, 0)
        untested = []
        lock_file = Path(arguments.lock_file or runner.DEFAULT_LOCK_FILE).expanduser()
        # Each suite runs in its own test sandbox under bwrap, sharing no machine state with
        # other runs, so no machine lock is taken there.
        in_test_sandboxes = \
            runner.does_signal_sandbox_report_killed_suite_as_exit_code_128_plus_signal(
                sandbox_prefix)
        if in_test_sandboxes:
            lock_handle, holder, previous_holder = contextlib.nullcontext(), None, ""
        else:
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
        # Clean up after earlier runs here, as scripts/run-all-test-suites.py does.
        if in_test_sandboxes:
            with runner.lock_held_while_cleaning_up_after_earlier_runs(lock_file):
                runner.clean_up_after_earlier_runs(lock_file, previous_holder)
        else:
            runner.clean_up_after_earlier_runs(lock_file, previous_holder)
        # Each file's mutants are a test run of their own: admission decides when they start,
        # they hold a slot while they run, at low priority, and a suite run outside the
        # test sandbox first takes the lock those suites share with every other run.
        admission = readings = None
        nice_prefix = ()
        if in_test_sandboxes:
            psutil, refusal = runner.psutil_imported_or_why_not()
            if psutil is None:
                raise CouldNotRun(refusal.replace(f"{runner.PROGRAM}:", f"{PROGRAM}:", 1))
            try:
                readings = runner.TestSuiteAdmissionMachineCpuAndMemoryReadingsSampler(psutil)
                readings.start()
                admission = runner.MachineWideTestSuiteAdmission(
                    runner.test_suite_admission_directory_for_lock_file(lock_file), readings,
                    lambda line: print(f"{PROGRAM}: {line}", flush=True))
            except runner.MachineWideTestSuiteAdmissionCouldNotDecide as error:
                if readings is not None:
                    readings.stop()
                raise CouldNotRun(f"{PROGRAM}: not run — admission could not start: {error}\n"
                                  f"Fix what it names, then run this again.") from error
            nice_prefix = ("nice", "-n", str(runner.TEST_SUITE_NICE_INCREMENT))
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
                        suites = suites_for_file(path, suites_listed_at_head,
                                                 recordings_directory, runner)
                        if not suites:
                            untested.append(path)
                            print(f"NO SUITE  {path}: no recorded suite reads it and it "
                                  f"has no sibling suite, so its changed lines are untested")
                            continue
                        print(f"MUTATING  {path} with {', '.join(suites)}", flush=True)
                        outside = runner.SUITES_RUN_WITHOUT_ANY_SANDBOX
                        for suite in suites:
                            if sandbox_prefix and suite in outside:
                                print(f"NO SANDBOX  {suite} runs WITHOUT the signal "
                                      f"sandbox: {outside[suite]}", flush=True)
                        admitted = (contextlib.nullcontext() if admission is None else
                                    admission.admitted(
                                        f"mutation testing of {path}",
                                        without_any_sandbox=any(
                                            suite in outside for suite in suites)))
                        started_proofs = {}
                        if in_test_sandboxes:
                            for suite in suites:
                                proof = scratch / f"{path.replace('/', '__')}.{suite.replace('/', '__')}.started"
                                proof.touch()
                                started_proofs[suite] = proof
                        with admitted:
                            counts, survivors, errored = mutation_test_one_file(
                                path, suites, worktree, scratch, tools, merge_base,
                                arguments, environment,
                                {suite: runner.command_prefix_starting_one_suite_in_its_test_sandbox(
                                    sandbox_prefix, worktree,
                                    [started_proofs[suite]] if suite in started_proofs else (),
                                    suite=suite,
                                    read_only_paths=runner.paths_one_suite_launch_needs_shown_read_only_in_test_sandbox(
                                        [arguments.python]) if in_test_sandboxes else ())
                                 for suite in suites},
                                outside, nice_prefix, started_proofs)
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
                if readings is not None:
                    readings.stop()
    except runner.MachineWideTestSuiteAdmissionCouldNotDecide as error:
        print(f"{PROGRAM}: not run to the end — admission failed: {error}\n"
              f"Fix what it names, then run this again.", file=sys.stderr)
        return EXIT_COULD_NOT_RUN
    except runner.SignalSandboxCouldNotStart as error:
        print(runner.signal_sandbox_refusal(error, PROGRAM), file=sys.stderr)
        return EXIT_COULD_NOT_RUN
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
