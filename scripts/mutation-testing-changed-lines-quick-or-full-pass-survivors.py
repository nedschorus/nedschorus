#!/usr/bin/env python3
"""Run nc-mutation-testing with cosmic-ray on the lines a change made, in its quick or its full pass, and print the survivors.

Usage:
  scripts/mutation-testing-changed-lines-quick-or-full-pass-survivors.py
      (--quick-mutation-pass | --full-mutation-pass)
      (--pull-request N | --head COMMIT --base COMMIT)
      [--checkout DIR] [--cosmic-ray-venv DIR] [--python INTERPRETER]
      [--recorded-inputs-directory DIR] [--mutant-timeout-seconds S]
      [--lock-file PATH] [--survived-and-errored-mutants-json-file PATH]

The head is checked out in a detached scratch worktree, because cosmic-ray
edits each mutant into the file on disk; the worktree is removed afterwards,
whatever happens. Each changed Python file that is not itself a suite is
mutated on its changed lines only, against the merge base. A line that ends
in a `# pragma: no mutate` comment is never mutated: that comment records
why no test can kill the mutants of its line.

THE FULL MUTATION PASS mutates every changed line, and tests each mutant
with every suite whose recorded inputs read that file (the recordings
scripts/run-all-test-suites.py keeps), plus the file's sibling
`<name>-test.py` or `<name>-test.sh` when there is one.

THE QUICK MUTATION PASS, run before a push, mutates only the changed lines
that are failure-handling code: an `except` clause, and an `if` statement,
`while` loop or conditional expression whose test reads an exit code (a name
or attribute named `returncode`, or ending in `exit_code` or `exit_status`),
each from its first line to its last. A changed file with no changed line of
failure-handling code is not mutated, and is printed as NO FAILURE-HANDLING
CHANGE. Its mutants are tested with the full mutation pass's suites less the
repository-wide checks, which check one rule across a whole class of the
repository's files and are listed in REPOSITORY_WIDE_CHECKS, and less
every suite whose recorded inputs read every Python file git tracked at the
commit the recording was made at. Those suites still run on the unmutated
code before a push and every day on main, and against mutants in the full
mutation pass.

The test command cosmic-ray runs, for the baseline on the unmutated head and
for each mutant, is this script, given
--cosmic-ray-test-command-run-test-suite-runner-stopped-after-seconds, a flag
this script writes into cosmic-ray's config and no caller gives, which runs
scripts/run-all-test-suites.py, the one beside this file, once, with its standard error sent to its standard
output, the only stream cosmic-ray records, so the runner's refusals reach this
script. That run is on the scratch worktree, given --only-suites-named with the file's
suites, --leave-recorded-inputs-and-failure-history-unchanged, so a mutant
changes no suite's recording, and --stop-at-first-failing-suite, so a mutant
one suite kills does not wait for the rest. The runner runs the suites in
parallel, each starting when the runner's admission lets it (on Linux in
nc-test-sandboxes, when the machine's CPU and memory have room: ADMISSION in the
runner's docstring), each in its signal sandbox and, on Linux with
bwrap, its nc-test-sandbox, each under its own time limit (see PER-SUITE TIMEOUT
in the runner's docstring), and passes on --python, --recorded-inputs-directory
and, when given, --lock-file. Where suites run without nc-test-sandboxes (macOS,
or Linux without bwrap), each of the runner's runs takes the machine's lock,
and the runner exits 3 without running a suite while another test run holds it.
On a mutant, that refusal judges no suite, so the mutant is printed as ERRORED
with the runner's refusal and the script goes on to the next mutant; on the
unmutated head it stops the script with exit 2, as a failing suite there does.
When bwrap is on PATH but cannot start, the script exits 2 before making the
worktree.

The limit on one run of the suites, per changed file, is the longest of its
suites' time limits, computed as the runner computes them from the
recordings, times the number of rounds the runner needs for them (the number
of suites divided by the number it runs at once, its suites_run_at_once(), the
same call the runner makes, rounded up), plus
TEST_SUITE_RUNNER_START_UP_SECONDS: a backstop, which a run passes only when
admission keeps its suites waiting. --mutant-timeout-seconds, when given, sets
that limit for every file instead. At that limit the test command sends the
runner SIGTERM, on which the runner kills each running suite's process group;
cosmic-ray's own limit, which kills only the test command's process group, is
MUTANT_TIMEOUT_EXTRA_SECONDS_FOR_TEST_SUITE_RUNNER_TO_STOP_ITS_SUITES, 30 s,
later,
since a suite runs in a session of its own and, outside an nc-test-sandbox,
outlives a runner killed with SIGKILL.

A renamed file is mutated under its new name. A mutant cosmic-ray could not
judge, because its worker raised, its suites could not be launched, a suite
ran past its own time limit, which the runner's TIMEOUT line names, the
suites ran past the limit on one run of them, or the runner exited nonzero without a
suite failing by its own exit (it printed nothing, was not run to the end,
could not write its records, or a suite's nc-test-sandbox did not start), is
printed as ERRORED and counts against the run like a survivor. cosmic-ray
itself reports every nonzero exit of the runner as a kill; this script does
not. On the unmutated head either a suite's own time limit or the limit on
one run of the suites stops the script with exit 2 and a message saying the suites ran out of time, with the limit,
and, for a suite's own limit, the suite.

--survived-and-errored-mutants-json-file, when given, names a file this
script writes after its SUMMARY line, as one JSON object: "head",
"merge_base", "survived" and "errored", each a list of mutants with
"module_path", "line", "operator", "diff" and "reason", and
"files_with_no_suite". A file that cannot be written exits 2.

Exit codes: 0 every mutant was killed, 1 a mutant survived, errored or was
not run, or a changed file has no suite, 2 could not run (cosmic-ray missing,
a git step failed, the nc-head-commit is already in the base, the worktree could
not be made, a changed file the quick mutation pass reads is not valid Python,
the JSON file could not be written, or a suite fails, runs out of time or
cannot be launched on the
unmutated head), 143 or 129 stopped by SIGTERM or SIGHUP (128 plus the signal
number), after removing the scratch worktree, git's record of it included,
and the scratch directory.
"""

import argparse
import ast
import hashlib
import importlib.util
import json
import math
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROGRAM = "mutation-testing-changed-lines-quick-or-full-pass-survivors"

EXIT_EVERY_MUTANT_KILLED = 0
EXIT_SURVIVORS_OR_UNTESTED_FILES = 1
EXIT_COULD_NOT_RUN = 2

COSMIC_RAY_TOOLS = ("cosmic-ray", "cr-filter-git", "cr-filter-pragma", "cr-filter-lines")

QUICK_MUTATION_PASS_COMMAND_LINE_FLAG = "--quick-mutation-pass"
FULL_MUTATION_PASS_COMMAND_LINE_FLAG = "--full-mutation-pass"

# Each checks one rule across a whole class of the repository's files, so its recording reads
# nearly every module; the quick mutation pass leaves it out.
REPOSITORY_WIDE_CHECKS = (
    "nc-systems/general-tools/tests/common-module-wording-copied-into-other-test-files-guard-for-each-wording-module-test.py",
    "scripts/code-comments-carry-no-history-markers-test.py",
    "scripts/edited-file-path-within-checkout-root-and-git-check-ignore-defined-once-test.py",
    "scripts/every-repository-program-help-option-test.py",
    "scripts/git-redirecting-environment-variables-defined-once-test.py",
    "scripts/git-redirecting-environment-variables-removed-by-every-caller-test.py",
    "scripts/python-files-carry-no-try-except-pass-ruff-s110-test.py",
    "scripts/registered-hook-messages-carry-no-citations-test.py",
    "scripts/supervisor-file-names-defined-once-test.py",
    "scripts/test-suites-run-directly-ignore-git-redirecting-environment-test.py",
    "scripts/test-suites-source-scan-for-skipped-case-prints-run-all-test-suites-cannot-count-test.py",
)

# A name or attribute that holds a process's exit code, as this project's code names one.
EXIT_CODE_NAME = re.compile(r"(?:^|_)(?:returncode|exit_code|exit_status)$")
TEST_SUITE_RUNNER_START_UP_SECONDS = 5
# The runner acts on SIGTERM within RUN_STOP_SIGNAL_CHECK_SECONDS, then waits up to
# TEST_SUITE_OUTPUT_DRAIN_SECONDS for each killed suite's output.
MUTANT_TIMEOUT_EXTRA_SECONDS_FOR_TEST_SUITE_RUNNER_TO_STOP_ITS_SUITES = 30
COSMIC_RAY_TEST_COMMAND_RUN_TEST_SUITE_RUNNER_STOPPED_AFTER_SECONDS_FLAG = "--cosmic-ray-test-command-run-test-suite-runner-stopped-after-seconds"
TEST_SUITE_RUNNER_STOPPED_AT_MUTANT_TIMEOUT_LINE_PREFIX = f"{PROGRAM}: stopped the suite runner with SIGTERM"

TEST_SUITE_RUNNER_PATH = Path(__file__).resolve().with_name("run-all-test-suites.py")

_git_output_spec = importlib.util.spec_from_file_location(
    "git_machine_readable_output_runner_and_parser_common",
    Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
    / "git-machine-readable-output-runner-and-parser-common.py")
git_output = importlib.util.module_from_spec(_git_output_spec)
_git_output_spec.loader.exec_module(git_output)

_stop_signals_spec = importlib.util.spec_from_file_location(
    "stop_signal_sigterm_or_sighup_raises_system_exit_so_cleanup_runs_common",
    Path(__file__).resolve().parents[1] / "nc-systems" / "general-tools"
    / "stop-signal-sigterm-or-sighup-raises-system-exit-so-cleanup-runs-common.py")
stop_signals = importlib.util.module_from_spec(_stop_signals_spec)
_stop_signals_spec.loader.exec_module(stop_signals)


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
    """Return (nc-head-commit, base ref) of a pull request, fetching both."""
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
    """The nc-test-suites git tracks at head."""
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


def tracked_python_files_at(commit, checkout, environment, cache):
    """The Python files git tracks at the commit, or None when git cannot list them."""
    if commit not in cache:
        listed = run(["git", "ls-tree", "-r", "-z", "--name-only", commit], checkout, environment)
        cache[commit] = None if listed.returncode != 0 else {
            path for path in git_output.nul_separated_fields(listed.stdout) if path.endswith(".py")}
    return cache[commit]


def quick_mutation_pass_suites(suites, recordings_directory, runner, checkout, environment,
                               tracked_python_files_cache):
    """The suites less the repository-wide checks and every suite whose recording read every
    Python file git tracked at the commit it was recorded at."""
    chosen = []
    for suite in suites:
        if suite in REPOSITORY_WIDE_CHECKS:
            continue
        recording = runner.load_recording(recordings_directory, suite)
        commit = recording.get("commit") if isinstance(recording, dict) else None
        # A commit this clone lacks leaves the suite in: it only costs time.
        tracked = (tracked_python_files_at(commit, checkout, environment,
                                           tracked_python_files_cache)
                   if isinstance(commit, str) else None)
        if tracked and tracked <= set(recording.get("reads", {})):
            continue
        chosen.append(suite)
    return chosen


def reads_an_exit_code(expression):
    return any(EXIT_CODE_NAME.search(node.attr if isinstance(node, ast.Attribute) else node.id)
               for node in ast.walk(expression) if isinstance(node, (ast.Attribute, ast.Name)))


def failure_handling_line_ranges(source):
    """(first line, last line) of each except clause, and of each if, while or conditional
    expression whose test reads an exit code."""
    return sorted(
        (node.lineno, node.end_lineno) for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ExceptHandler)
        or (isinstance(node, (ast.If, ast.While, ast.IfExp)) and reads_an_exit_code(node.test)))


HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def line_numbers_at_head_of_lines_changed_since_merge_base(checkout, merge_base, head, path, environment):
    """The numbers, at head, of the lines the change added or changed in the file."""
    diff = run_or_raise(["git", "--literal-pathspecs", "diff", "--unified=0", "--no-color",
                         "--no-ext-diff", merge_base, head, "--", path],
                        checkout, environment, what=f"git diff of {path}")
    changed = set()
    for line in diff.splitlines():
        hunk = HUNK_HEADER.match(line)
        if hunk:
            start = int(hunk[1])
            changed.update(range(start, start + int(hunk[2] if hunk[2] is not None else 1)))
    return changed


def failure_handling_line_ranges_of_file(worktree, path):
    try:
        return failure_handling_line_ranges((worktree / path).read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError) as error:
        raise CouldNotRun(
            f"{PROGRAM}: not run — {path} at the head commit is not valid Python ({error}), so "
            f"the quick mutation pass cannot find its failure-handling code.\n"
            f"Fix the file until python3 -m py_compile {shlex.quote(path)} passes.\n"
            f"Commit the fix, then run scripts/{PROGRAM}.py again with the same options and the new head "
            f"commit.") from error


def run_test_suite_runner_with_its_stderr_on_stdout_stopped_before_cosmic_ray_limit(
        seconds, command):
    """Run the suite runner's command, its standard error on standard output; past `seconds`,
    say so on standard output and send it SIGTERM. Return its exit code.

    A runner a signal killed returns the negative signal number, which leaves this process
    nonzero."""
    test_suite_runner = subprocess.Popen(command, stderr=subprocess.STDOUT)
    try:
        exit_code = test_suite_runner.wait(seconds)
    except subprocess.TimeoutExpired:
        print(f"{TEST_SUITE_RUNNER_STOPPED_AT_MUTANT_TIMEOUT_LINE_PREFIX}: it ran past the limit of "
              f"{seconds:g} s on one run of the suites", flush=True)
        test_suite_runner.terminate()
        exit_code = test_suite_runner.wait()
    return exit_code


def test_command_for(suites, worktree, arguments, recorded_inputs_directory,
                     mutant_timeout_seconds):
    """The command cosmic-ray runs: this script, running the suite runner once on the worktree."""
    command = [sys.executable, str(Path(__file__).resolve()), COSMIC_RAY_TEST_COMMAND_RUN_TEST_SUITE_RUNNER_STOPPED_AFTER_SECONDS_FLAG,
               repr(float(mutant_timeout_seconds)),
               sys.executable, str(TEST_SUITE_RUNNER_PATH), "--checkout", str(worktree),
               "--python", arguments.python,
               "--recorded-inputs-directory", str(recorded_inputs_directory),
               "--leave-recorded-inputs-and-failure-history-unchanged",
               "--stop-at-first-failing-suite"]
    # Left to the runner's default otherwise: every run that names one lock file shares the
    # admission kept beside it.
    if arguments.lock_file is not None:
        command += ["--lock-file", arguments.lock_file]
    # cosmic-ray splits the command with shlex.
    return shlex.join([*command, "--only-suites-named", *suites])


def default_mutant_timeout_seconds_from_test_suites_own_time_limits(
        suites, recordings_directory, runner, in_test_sandboxes):
    """The longest of the suites' own limits, times the runner's rounds of them, plus its start-up."""
    longest = max(runner.suite_timeout_and_the_recorded_seconds_it_came_from(
        runner.load_recording(recordings_directory, suite))[0] for suite in suites)
    at_once = runner.suites_run_at_once(None, len(suites), os.cpu_count(),
                                        admission_decides=in_test_sandboxes)
    return longest * math.ceil(len(suites) / at_once) + TEST_SUITE_RUNNER_START_UP_SECONDS


def cosmic_ray_config_text(module_path, test_command, merge_base,
                           mutant_timeout_seconds, failure_handling_ranges=None):
    """cosmic-ray's config; with failure_handling_ranges, cr-filter-lines keeps only those lines."""
    line_filter = "" if failure_handling_ranges is None else (
        "\n[cosmic-ray.filters.line-filter]\n"
        f"lines = {{ {json.dumps(module_path)} = "
        f"{json.dumps([f'{first}-{last}' for first, last in failure_handling_ranges])} }}\n")
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
        f"branch = {json.dumps(merge_base)}\n"
        + line_filter)


OUTCOME_KEYS = ("killed", "survived", "errored", "no mutation", "skipped",
                "not run")

# cosmic-ray reports a worker that raised as exception/incompetent, and a test
# command it could not launch as normal/incompetent: errors of the run, not
# properties of the mutant. A no-test worker found nothing to mutate.
WORKER_OUTCOMES_THAT_ERRORED = ("exception", "abnormal")

# cosmic-ray reports suites that ran past the timeout as killed, with exactly
# this output: a slow run, not a test that failed under the mutant.
TIMED_OUT_OUTPUT = "timeout"


def is_recorded_output_of_a_run_stopped_at_mutant_timeout(output):
    """True when the test command was stopped at the limit, by itself or by cosmic-ray."""
    return output == TIMED_OUT_OUTPUT or any(
        line.startswith(TEST_SUITE_RUNNER_STOPPED_AT_MUTANT_TIMEOUT_LINE_PREFIX) for line in output.splitlines())


def mutant_description(item, result, reason=""):
    mutation = item["mutations"][0]
    return {
        "module_path": mutation["module_path"],
        "line": mutation["start_pos"][0],
        "operator": mutation["operator_name"],
        "diff": result.get("diff") or "",
        "reason": reason,
    }


def suite_timeouts_described(timed_out):
    return "; ".join(f"{suite} ran past its own limit of {limit} s"
                     for suite, limit in timed_out)


def runner_output_described(output, runner):
    """The runner's lines that say why it judged no suite, or that it printed nothing."""
    if not output.strip():
        return "was empty"
    lines = [line for line in output.splitlines()
             if line.startswith((f"{runner.PROGRAM}: not run", runner.FAILED_SUITE_LINE_PREFIX,
                                 runner.NOT_RUN_SUITE_LINE_PREFIX))]
    if not lines:
        return f"ended: {output.strip().splitlines()[-1]}"
    return f"says: {' | '.join(dict.fromkeys(lines))}"


def outcomes_from_dump(dump_text, mutant_timeout_seconds, runner):
    """Return (counts, survivors, errored) from `cosmic-ray dump` output.

    cosmic-ray counts a run past a suite's own limit, or the limit on one run of the suites,
    as a kill; each is an errored mutant here, whose reason says which limit it passed."""
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
              and is_recorded_output_of_a_run_stopped_at_mutant_timeout(result.get("output") or "")):
            counts["errored"] += 1
            errored.append(mutant_description(
                item, result,
                reason=f"timeout: the suites ran past the limit of "
                       f"{mutant_timeout_seconds:g} s on one run of them, so this mutant was "
                       f"not judged; rerun "
                       f"when the machine is quieter, or with a larger --mutant-timeout-seconds"))
        elif (worker_outcome not in WORKER_OUTCOMES_THAT_ERRORED
              and test_outcome == "killed"
              and runner.run_all_test_suites_output_timed_out_suites_and_limits_parse(
                  result.get("output") or "")):
            counts["errored"] += 1
            timed_out = runner.run_all_test_suites_output_timed_out_suites_and_limits_parse(
                result["output"])
            errored.append(mutant_description(
                item, result,
                reason=f"suite timeout: {suite_timeouts_described(timed_out)}, so this mutant "
                       f"was not judged: the mutant may make that suite hang, or the machine "
                       f"was busy; run this script again once, and if this mutant is ERRORED "
                       f"the same way again, it makes that suite hang: name it, with the "
                       f"suite, in the pull request's description"))
        elif (worker_outcome not in WORKER_OUTCOMES_THAT_ERRORED
              and test_outcome == "killed"
              and runner.run_all_test_suites_output_parse_whether_the_run_ended_with_a_suite_failed_by_its_exit_code_or_signal(
                  result.get("output") or "")):
            counts["killed"] += 1
        elif (worker_outcome not in WORKER_OUTCOMES_THAT_ERRORED
              and test_outcome == "killed"):
            counts["errored"] += 1
            errored.append(mutant_description(
                item, result,
                reason=f"no verdict: the suite runner exited nonzero but judged no suite "
                       f"failing, so this mutant was not judged; its output "
                       f"{runner_output_described(result.get('output') or '', runner)}"))
        else:
            counts["errored"] += 1
            errored.append(mutant_description(item, result))
    return counts, survivors, errored


def scratch_file_name_stem_under_255_bytes_unique_to_repository_paths(*paths):
    """A 64-byte file-name stem unique to these repository paths.

    Repository paths here run long, so a name built from whole paths passes the 255-byte limit."""
    return hashlib.sha256("\0".join(paths).encode()).hexdigest()


def baseline_refusal(path, suites, baseline, baseline_results, mutant_timeout_seconds,
                     runner):
    """The message for a baseline cosmic-ray exited nonzero on: a timeout, or failing suites."""
    outputs = [result.get("output") or "" for _, result in baseline_results
               if result and result.get("test_outcome") == "killed"]
    if any(is_recorded_output_of_a_run_stopped_at_mutant_timeout(output) for output in outputs):
        return (f"{PROGRAM}: not run — the suites for {path} ran out of time on the unmutated "
                f"head: they had not ended when the limit of "
                f"{mutant_timeout_seconds:g} s on one run of them passed, so no mutant "
                f"can be judged. Suites: {' '.join(suites)}\n"
                f"Run this again with --mutant-timeout-seconds larger than "
                f"{mutant_timeout_seconds:g}.")
    timed_out = runner.run_all_test_suites_output_timed_out_suites_and_limits_parse(
        "\n".join(outputs))
    if timed_out:
        suites_timed_out = " ".join(shlex.quote(suite) for suite, _ in timed_out)
        return (f"{PROGRAM}: not run — on the unmutated head, {suite_timeouts_described(timed_out)}"
                f" in scripts/run-all-test-suites.py, so no mutant of {path} can be judged. A "
                f"suite's own limit comes from its last passing run (PER-SUITE TIMEOUT in that "
                f"file's docstring); a larger --mutant-timeout-seconds does not raise it.\n"
                f"Run the suite alone, in a checkout at the head: python3 "
                f"scripts/run-all-test-suites.py --only-suites-named {suites_timed_out}\n"
                f"If it passes there, it only ran slowly on a busy machine: run this again.\n"
                f"If it times out there too, the head makes it hang: fix that before mutation "
                f"testing.")
    return (f"{PROGRAM}: not run — the suites for {path} fail on the unmutated "
            f"head, so no mutant can be judged: "
            f"{' '.join(suites)}\n{(baseline.stderr or baseline.stdout).strip()}")


def mutation_test_one_file(path, suites, worktree, scratch, tools, merge_base,
                           arguments, environment, runner, recorded_inputs_directory,
                           recordings_directory, in_test_sandboxes,
                           failure_handling_ranges=None):
    """Run cosmic-ray on one file's changed lines; return (counts, survivors, errored).

    With failure_handling_ranges, only the changed lines inside them are mutated."""
    name = scratch_file_name_stem_under_255_bytes_unique_to_repository_paths(path)
    config = scratch / f"{name}.toml"
    session = scratch / f"{name}.sqlite"
    baseline_session = scratch / f"{name}.baseline.sqlite"
    mutant_timeout_seconds = (
        arguments.mutant_timeout_seconds if arguments.mutant_timeout_seconds is not None
        else default_mutant_timeout_seconds_from_test_suites_own_time_limits(
            suites, recordings_directory, runner, in_test_sandboxes))
    config.write_text(cosmic_ray_config_text(
        path, test_command_for(suites, worktree, arguments, recorded_inputs_directory,
                               mutant_timeout_seconds),
        merge_base,
        mutant_timeout_seconds
        + MUTANT_TIMEOUT_EXTRA_SECONDS_FOR_TEST_SUITE_RUNNER_TO_STOP_ITS_SUITES,
        failure_handling_ranges))
    cosmic_ray = [tools["cosmic-ray"]]
    baseline = run([*cosmic_ray, "baseline", "--session-file",
                    str(baseline_session), str(config)], worktree, environment)
    if baseline.returncode != 0:
        # cosmic-ray writes the baseline's result before it exits 1; a baseline that crashed
        # before writing it leaves nothing to dump, and is reported as failing suites.
        dumped = run([*cosmic_ray, "dump", str(baseline_session)], worktree, environment)
        baseline_results = ([json.loads(line) for line in dumped.stdout.splitlines()
                             if line.strip()] if dumped.returncode == 0 else [])
        raise CouldNotRun(baseline_refusal(path, suites, baseline, baseline_results,
                                           mutant_timeout_seconds, runner))
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
    run_or_raise([tools["cr-filter-pragma"], str(session)],
                 worktree, environment, what=f"cr-filter-pragma for {path}")
    if failure_handling_ranges is not None:
        run_or_raise([tools["cr-filter-lines"], "--config", str(config), str(session)],
                     worktree, environment, what=f"cr-filter-lines for {path}")
    run_or_raise([*cosmic_ray, "exec", str(config), str(session)], worktree,
                 environment, what=f"cosmic-ray exec for {path}")
    return outcomes_from_dump(run_or_raise(
        [*cosmic_ray, "dump", str(session)], worktree, environment,
        what=f"cosmic-ray dump for {path}"), mutant_timeout_seconds, runner)


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
    which_pass = parser.add_mutually_exclusive_group(required=True)
    which_pass.add_argument(QUICK_MUTATION_PASS_COMMAND_LINE_FLAG, action="store_true",
                            help="mutate only the changed failure-handling code, without the "
                                 "repository-wide checks; the pass to run before a push")
    which_pass.add_argument(FULL_MUTATION_PASS_COMMAND_LINE_FLAG, action="store_true",
                            help="mutate every changed line, with every suite that reads the "
                                 "file; the pass the daily maintenance-job runs")
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--pull-request", type=int,
                       help="the pull request to test; its head and base are read with gh and fetched")
    which.add_argument("--head", help="the nc-head-commit to test (needs --base)")
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
                        help="the --lock-file given to the suite runner; default, the runner's")
    parser.add_argument("--mutant-timeout-seconds", type=float, default=None,
                        help="the limit on one run of a file's suites; default, the "
                             "longest suite's own limit times the runner's rounds, plus its "
                             "start-up")
    parser.add_argument("--survived-and-errored-mutants-json-file", default=None,
                        help="a file to write the survived and errored mutants to, as JSON")
    arguments = parser.parse_args(argv)
    if arguments.head is not None and arguments.base is None:
        parser.error("--head needs --base")
    if arguments.pull_request is not None and arguments.base is not None:
        parser.error("--base goes with --head; a pull request's base is read with gh")
    return arguments


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == [COSMIC_RAY_TEST_COMMAND_RUN_TEST_SUITE_RUNNER_STOPPED_AFTER_SECONDS_FLAG]:
        return run_test_suite_runner_with_its_stderr_on_stdout_stopped_before_cosmic_ray_limit(
            float(argv[1]), argv[2:])
    # A Bash tool timeout or TaskStop sends SIGTERM; raised as SystemExit, the stop still runs the
    # finally that removes the scratch worktree, and the TemporaryDirectory's exit.
    with stop_signals.stop_signals_raise_system_exit_so_cleanup_runs():
        return main_with_stop_signals_raising_system_exit(argv)


def main_with_stop_signals_raising_system_exit(argv):
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
            # The runner's first line says what failed; the lines after it name the runner's
            # own command, so this program's next steps replace them.
            what_failed = str(refusal).splitlines()[0].replace(f"{runner.PROGRAM}:",
                                                               f"{PROGRAM}:", 1)
            raise CouldNotRun(what_failed + "\n"
                              + runner.git_failure_next_step_lines(Path(__file__).name)) \
                from refusal
        suites_listed_at_head = suites_at_head(checkout, head, environment)

        try:
            sandbox_prefix, unconfined_because = runner.signal_sandbox()
        except runner.SignalSandboxCouldNotStart as error:
            raise CouldNotRun(runner.signal_sandbox_refusal(error, PROGRAM)) from error
        print(runner.signal_sandbox_line(sandbox_prefix, unconfined_because), flush=True)

        totals = dict.fromkeys(OUTCOME_KEYS, 0)
        untested = []
        no_failure_handling_change = []
        all_survivors = []
        all_errored = []
        tracked_python_files_cache = {}
        # As the runner decides it, since the runner's rounds of suites set the limit.
        in_test_sandboxes = sys.platform.startswith("linux") and \
            runner.does_signal_sandbox_report_killed_suite_as_exit_code_128_plus_signal(
                sandbox_prefix)
        if in_test_sandboxes:
            # The runner needs psutil there; refused here once, not once per mutant.
            psutil, refusal = runner.psutil_imported_or_why_not()
            if psutil is None:
                raise CouldNotRun(refusal.replace(f"{runner.PROGRAM}:", f"{PROGRAM}:", 1))
        recorded_inputs_directory = (arguments.recorded_inputs_directory
                                     or runner.DEFAULT_RECORDED_INPUTS_DIRECTORY)
        with tempfile.TemporaryDirectory(prefix=f"{PROGRAM}-") as scratch_name:
            # Resolved, as the cwd of every process run there reports it: on macOS the temporary
            # directory is under /var, a symbolic link to /private/var.
            scratch = Path(scratch_name).resolve()
            worktree = scratch / "worktree"
            try:
                run_or_raise(["git", "worktree", "add", "--detach", str(worktree),
                              head], checkout, environment,
                             what=f"git worktree add at {head}")
                for path in files:
                    suites = suites_for_file(path, suites_listed_at_head,
                                             recordings_directory, runner)
                    failure_handling_ranges = None
                    if arguments.quick_mutation_pass:
                        failure_handling_ranges = failure_handling_line_ranges_of_file(
                            worktree, path)
                        changed = line_numbers_at_head_of_lines_changed_since_merge_base(checkout, merge_base, head,
                                                               path, environment)
                        if not any(first <= number <= last for number in changed
                                   for first, last in failure_handling_ranges):
                            no_failure_handling_change.append(path)
                            print(f"NO FAILURE-HANDLING CHANGE  {path}: none of its changed "
                                  f"lines is in an except clause, or in an if, while or "
                                  f"conditional expression that tests an exit code, so the "
                                  f"quick mutation pass does not mutate it; nothing to do "
                                  f"for it")
                            continue
                        suites = quick_mutation_pass_suites(
                            suites, recordings_directory, runner, checkout, environment,
                            tracked_python_files_cache)
                    if not suites:
                        untested.append(path)
                        if arguments.quick_mutation_pass:
                            print(f"NO SUITE  {path}: once the repository-wide checks and "
                                  f"the suites that read every tracked Python file are left "
                                  f"out, no recorded suite reads it and it has no sibling "
                                  f"suite, so its changed failure-handling code is untested.\n"
                                  f"Write a suite that makes that code handle its failure, "
                                  f"and commit it.\n"
                                  f"Run it once with python3 scripts/run-all-test-suites.py "
                                  f"--only-suites-named <the suite's path>, which records "
                                  f"what it reads, so this program finds it.\n"
                                  f"Run scripts/{PROGRAM}.py again with the same options and the new head "
                                  f"commit.")
                        else:
                            print(f"NO SUITE  {path}: no recorded suite reads it and it "
                                  f"has no sibling suite, so its changed lines are untested")
                        continue
                    print(f"MUTATING  {path} with {', '.join(suites)}", flush=True)
                    outside = runner.SUITES_RUN_WITHOUT_ANY_SANDBOX
                    for suite in suites:
                        if sandbox_prefix and suite in outside:
                            print(f"NO SANDBOX  {suite} runs WITHOUT the signal "
                                  f"sandbox: {outside[suite]}", flush=True)
                    counts, survivors, errored = mutation_test_one_file(
                        path, suites, worktree, scratch, tools, merge_base, arguments,
                        environment, runner, recorded_inputs_directory, recordings_directory,
                        in_test_sandboxes, failure_handling_ranges)
                    all_survivors += survivors
                    all_errored += errored
                    for key in totals:
                        totals[key] += counts[key]
                    for label, mutants in (("SURVIVED", survivors),
                                           ("ERRORED ", errored)):
                        for mutant in mutants:
                            reason = f" ({mutant['reason']})" if mutant["reason"] else ""
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
    lines_mutated = ("changed failure-handling lines" if arguments.quick_mutation_pass
                     else "changed lines")
    no_failure_handling_change_count = (
        f"{len(no_failure_handling_change)} changed file(s) with no failure-handling change; "
        if arguments.quick_mutation_pass else "")
    print(f"SUMMARY: {tested} mutants on {lines_mutated} of "
          f"{len(files) - len(untested) - len(no_failure_handling_change)} "
          f"file(s): {totals['killed']} killed, {totals['survived']} survived, "
          f"{totals['errored']} errored, {totals['not run']} not run; "
          f"{no_failure_handling_change_count}{len(untested)} changed file(s) "
          f"with no suite; head {head[:12]}, merge base {merge_base[:12]}")
    if arguments.survived_and_errored_mutants_json_file is not None:
        try:
            Path(arguments.survived_and_errored_mutants_json_file).write_text(json.dumps({
                "head": head, "merge_base": merge_base, "survived": all_survivors,
                "errored": all_errored, "files_with_no_suite": untested}, indent=1) + "\n",
                encoding="utf-8")
        except OSError as error:
            print(f"{PROGRAM}: the survived and errored mutants were not written to "
                  f"{arguments.survived_and_errored_mutants_json_file}: {error}. The lines "
                  f"above are this run's whole result.\n"
                  f"Run scripts/{PROGRAM}.py again with "
                  f"--survived-and-errored-mutants-json-file naming a path in a directory "
                  f"you can write to, or without that option if you need no JSON file.",
                  file=sys.stderr)
            return EXIT_COULD_NOT_RUN
    if totals["survived"] or totals["errored"] or totals["not run"] or untested:
        return EXIT_SURVIVORS_OR_UNTESTED_FILES
    return EXIT_EVERY_MUTANT_KILLED


if __name__ == "__main__":
    sys.exit(main())
