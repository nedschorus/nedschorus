#!/usr/bin/env python3
"""Tests for mutation-testing-changed-lines-quick-or-full-pass-survivors.py.

Run: python3 scripts/mutation-testing-changed-lines-quick-or-full-pass-survivors-test.py
Prints one line per case and exits non-zero if any case fails.

No case runs the real cosmic-ray. Each case builds a scratch repository with
a base commit and a nc-head-commit, and points --cosmic-ray-venv at a fake venv
whose cosmic-ray and cr-filter-git record every call and behave as the
case's plan file says; with run_test_command, the fake's baseline runs the
test command, the suite runner on fixture suites, as cosmic-ray runs it.
"""

import contextlib
import importlib.util
import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_git_environment_fixture_spec = importlib.util.spec_from_file_location(
    "git_redirecting_environment_removal_test_fixture",
    str(Path(__file__).resolve().with_name(
        "git-redirecting-environment-removal-test-fixture.py")))
_git_environment_fixture = importlib.util.module_from_spec(_git_environment_fixture_spec)
_git_environment_fixture_spec.loader.exec_module(_git_environment_fixture)
_git_environment_fixture.remove_git_redirecting_environment_variables_from_this_process()

SCRIPT = Path(__file__).with_name("mutation-testing-changed-lines-quick-or-full-pass-survivors.py")


def load_test_suite_runner():
    spec = importlib.util.spec_from_file_location(
        "run_all_test_suites", Path(__file__).with_name("run-all-test-suites.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_script_module():
    spec = importlib.util.spec_from_file_location("mutation_testing_changed_lines_quick_or_full_pass_survivors",
                                                  str(SCRIPT))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# The limit on one run of the suites, by default, for one suite with no recording: one round
# of the runner.
DEFAULT_LIMIT_FOR_A_SUITE_WITHOUT_RECORDING = (
    load_test_suite_runner().TEST_SUITE_TIMEOUT_WITHOUT_PASSING_RECORDING_SECONDS
    + load_script_module().TEST_SUITE_RUNNER_START_UP_SECONDS)
EXTRA_SECONDS = load_script_module(
).MUTANT_TIMEOUT_EXTRA_SECONDS_FOR_TEST_SUITE_RUNNER_TO_STOP_ITS_SUITES


def cosmic_ray_timeout_line_and_test_command_words_for_limit(limit):
    """The config's timeout line and the test command's first words, for this limit."""
    return (f"timeout = {float(limit + EXTRA_SECONDS)!r}\n",
            [sys.executable, str(SCRIPT.resolve()),
             load_script_module().COSMIC_RAY_TEST_COMMAND_RUN_TEST_SUITE_RUNNER_STOPPED_AFTER_SECONDS_FLAG, repr(float(limit))])

CONTROL_DIRECTORY_VARIABLE = "MUTATION_TESTING_CHANGED_LINES_QUICK_OR_FULL_PASS_SURVIVORS_TEST_CONTROL_DIR"

FAKE_COSMIC_RAY_SOURCE = f'''#!/usr/bin/env python3
import json, os, pathlib, re, shlex, subprocess, sys

control = pathlib.Path(os.environ["{CONTROL_DIRECTORY_VARIABLE}"])
plan = json.loads((control / "plan.json").read_text())
tool = pathlib.Path(sys.argv[0]).name
arguments = sys.argv[1:]
head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                      text=True).stdout.strip()
with (control / "calls.log").open("a") as log:
    log.write(json.dumps({{"tool": tool, "arguments": arguments,
                          "cwd": os.getcwd(), "head": head,
                          "session_attended": os.environ.get("CLAUDE_CODE_SESSION_ATTENDED")}}) + "\\n")
if tool == "cr-filter-git":
    sys.exit(plan.get("filter_exit", 0))
if tool in ("cr-filter-pragma", "cr-filter-lines"):
    sys.exit(plan.get(tool + "_exit", 0))
command = arguments[0]
if command == "baseline":
    config_text = pathlib.Path(arguments[-1]).read_text()
    (control / "config.toml").write_text(config_text)
    # Not tomllib, which Apple's Python 3.9 lacks; the script writes this line's value as JSON.
    test_command = re.search(r"^test-command = (.*)$", config_text, re.MULTILINE).group(1)
    words = shlex.split(json.loads(test_command))
    (control / "test-command.json").write_text(json.dumps(words))
    if "--session-file" in arguments:
        session = arguments[arguments.index("--session-file") + 1]
        pathlib.Path(session).write_text("baseline")
    if plan.get("run_test_command"):
        # As cosmic-ray does: the command's standard output is the result's output, and a
        # nonzero exit is a kill.
        completed = subprocess.run(words, capture_output=True, text=True)
        (control / "test-command-run.json").write_text(json.dumps(
            {{"exit": completed.returncode, "stdout": completed.stdout,
              "stderr": completed.stderr}}))
        plan["baseline_dump"] = [[{{"job_id": "baseline", "mutations": []}},
                                  {{"worker_outcome": "normal", "output": completed.stdout,
                                   "test_outcome": "survived" if completed.returncode == 0
                                   else "killed", "diff": None}}]]
        (control / "plan.json").write_text(json.dumps(plan))
        sys.exit(0 if completed.returncode == 0 else 1)
    sys.exit(plan.get("baseline_exit", 0))
if command == "init":
    pathlib.Path(arguments[2]).write_text("session")
    sys.exit(0)
if command == "exec":
    import time
    time.sleep(plan.get("exec_sleep_seconds", 0))
    sys.exit(plan.get("exec_exit", 0))
if command == "dump":
    if pathlib.Path(arguments[1]).read_text() == "baseline":
        if plan.get("baseline_dump_exit"):
            print("Traceback (most recent call last): the session cannot be read")
            sys.exit(plan["baseline_dump_exit"])
        lines = plan.get("baseline_dump", [[{{"job_id": "baseline", "mutations": []}},
                                             {{"worker_outcome": "normal", "output": "",
                                              "test_outcome": "survived", "diff": None}}]])
    else:
        lines = plan.get("dump", [])
    for line in lines:
        print(json.dumps(line))
    sys.exit(0)
sys.exit(9)
'''

failures = []


def check(case_name, condition, detail=""):
    if condition:
        print(f"PASS  {case_name}")
    else:
        print(f"FAIL  {case_name}: {detail}")
        failures.append(case_name)


def git(repository, *arguments):
    completed = subprocess.run(["git", "-C", str(repository), *arguments],
                               capture_output=True, text=True, check=True)
    return completed.stdout.strip()


def scratch_repository(directory, head_files):
    """A repository with a base commit and a nc-head-commit adding head_files."""
    repository = Path(directory) / "repository"
    repository.mkdir()
    git(repository, "init", "-q", "-b", "main")
    git(repository, "config", "user.email", "test@example.invalid")
    git(repository, "config", "user.name", "mutation survivors test")
    (repository / "README").write_text("base\n")
    git(repository, "add", "-A")
    git(repository, "commit", "-q", "-m", "base")
    base = git(repository, "rev-parse", "HEAD")
    for path, text in head_files.items():
        (repository / path).parent.mkdir(parents=True, exist_ok=True)
        (repository / path).write_text(text)
    git(repository, "add", "-A")
    git(repository, "commit", "-q", "-m", "head")
    head = git(repository, "rev-parse", "HEAD")
    return repository, base, head


def advance_base_past_merge_base(repository, merge_base):
    """Commit on a branch cut from the merge base, so the base tip is not the merge base."""
    git(repository, "branch", "advanced-base", merge_base)
    git(repository, "worktree", "add", "-q", str(repository.parent / "base-checkout"),
        "advanced-base")
    (repository.parent / "base-checkout" / "LATER").write_text("later on the base\n")
    git(repository.parent / "base-checkout", "add", "-A")
    git(repository.parent / "base-checkout", "commit", "-q", "-m", "later on the base")
    git(repository, "worktree", "remove", str(repository.parent / "base-checkout"))
    return git(repository, "rev-parse", "advanced-base")


def fake_venv(directory, plan):
    venv = Path(directory) / "venv"
    (venv / "bin").mkdir(parents=True)
    for tool in ("cosmic-ray", "cr-filter-git", "cr-filter-pragma", "cr-filter-lines"):
        path = venv / "bin" / tool
        path.write_text(FAKE_COSMIC_RAY_SOURCE)
        path.chmod(0o755)
    control = Path(directory) / "control"
    control.mkdir()
    (control / "plan.json").write_text(json.dumps(plan))
    (control / "calls.log").write_text("")
    return venv, control


def config_and_test_command_words(control):
    """The config the fake cosmic-ray's baseline saw, and its test command split into words."""
    config = (control / "config.toml").read_text() if (control / "config.toml").exists() else ""
    words_file = control / "test-command.json"
    return config, json.loads(words_file.read_text()) if words_file.exists() else []


def calls(control):
    return [json.loads(line) for line in
            (control / "calls.log").read_text().splitlines() if line]


def run_script(repository, control, *flags, path_override=None,
               extra_environment=None, dropped_variables=()):
    command, environment = script_command_and_environment(
        repository, control, *flags, path_override=path_override,
        extra_environment=extra_environment, dropped_variables=dropped_variables)
    return subprocess.run(command, capture_output=True, text=True, check=False, env=environment,
                          timeout=120)


def script_command_and_environment(repository, control, *flags, path_override=None,
                                   extra_environment=None, dropped_variables=()):
    environment = {name: value for name, value in os.environ.items()
                   if name not in dropped_variables}
    environment[CONTROL_DIRECTORY_VARIABLE] = str(control)
    # As inside the suite runner's sandbox, so a case takes the same path whether this file
    # runs there or directly: the machine lock and no sandbox. The sandbox cases drop it.
    inside_variable = load_test_suite_runner().SIGNAL_SANDBOX_INSIDE_VARIABLE
    if inside_variable not in dropped_variables:
        environment[inside_variable] = "1"
    if path_override is not None:
        environment["PATH"] = path_override
    environment.update(extra_environment or {})
    # The full mutation pass, unless the case names a pass: it mutates every changed line.
    passes = (load_script_module().QUICK_MUTATION_PASS_FLAG,
              load_script_module().FULL_MUTATION_PASS_FLAG)
    if not any(flag in passes for flag in flags):
        flags = (passes[1], *flags)
    # Never the real machine lock or admission, which the suite runner the test command runs
    # would share with every run on the machine.
    return ([sys.executable, str(SCRIPT), "--checkout", str(repository),
             "--recorded-inputs-directory", str(control / "recordings"),
             "--lock-file", str(control / "machine.lock"), *flags], environment)


def worktrees_of(repository):
    return [line for line in git(repository, "worktree", "list", "--porcelain").splitlines()
            if line.startswith("worktree ")]


def work_item(path, line, operator, job_id):
    return {"job_id": job_id, "mutations": [{
        "module_path": path, "operator_name": operator, "occurrence": 0,
        "start_pos": [line, 4], "end_pos": [line, 9], "operator_args": {}}]}


# What the suite runner prints when a suite fails under the mutant: what cosmic-ray records as a
# kill this script counts.
SUITE_FAILED_RUNNER_OUTPUT = (
    "FAIL scripts/thing-test.py exit 1 (0.4s)\n\n1 failed:\n"
    "FAIL scripts/thing-test.py exit 1 — log /tmp/a.log\n"
    "SUMMARY: 0 passed, 1 failed, 1 total\n")


def result(test_outcome, worker_outcome="normal", diff=None):
    return {"worker_outcome": worker_outcome,
            "output": SUITE_FAILED_RUNNER_OUTPUT if test_outcome == "killed" else "",
            "test_outcome": test_outcome, "diff": diff}


HEAD_FILES = {
    "scripts/thing.py": "def double(x):\n    return x + x\n",
    "scripts/thing-test.py": "import sys\nsys.exit(0)\n",
}

SURVIVOR_DIFF = ("--- mutation diff ---\n--- a/scripts/thing.py\n+++ b/scripts/thing.py\n"
                 "@@ -1,2 +1,2 @@\n-    return x + x\n+    return x * x\n")


def runner_output_with_suites_timed_out(timed_out, others=()):
    """What the suite runner prints when each (suite, limit) of timed_out ran past its limit.

    Its lines come from the runner's own code, so a case follows the runner's format."""
    runner = load_test_suite_runner()
    results = [{"suite": suite, "exit": -9, "seconds": limit + 1.0, "skips": [],
                "timeout": {"limit": limit, "recorded": None}} for suite, limit in timed_out]
    lines = ["run-all-test-suites: /tmp/worktree at abc (tracked files match that commit)"]
    lines += [runner.suite_line(result) for result in results] + list(others)
    lines += ["", f"{len(results)} failed:"]
    lines += [f"FAIL {result['suite']} {runner.why_suite_failed(result)} — log /tmp/a.log"
              for result in results]
    return "\n".join(lines) + "\nSUMMARY: 0 passed\n"


def runner_output_with_test_sandbox_not_started(suite):
    """The suite runner's NOT RUN lines for a suite whose nc-test-sandbox did not start, from its code."""
    runner = load_test_suite_runner()
    not_run = {"suite": suite, "exit": 1, "seconds": 0.1, "skips": [],
               "test sandbox did not start": True}
    return (f"{runner.suite_line(not_run)}\n\n1 not run, because bwrap could not build the "
            f"nc-test-sandbox; each log says why and what to do:\n"
            f"NOT RUN {suite} {runner.why_suite_failed(not_run)} — log /tmp/a.log\n")


def runner_output_with_a_suite_failed_with_exit_code(suite, exit_code):
    """The suite runner's FAIL lines for a suite that ended with this exit code, from its code."""
    runner = load_test_suite_runner()
    failed = {"suite": suite, "exit": exit_code, "seconds": 1.0, "skips": []}
    return (f"{runner.suite_line(failed)}\n\n1 failed:\n"
            f"FAIL {suite} {runner.why_suite_failed(failed)} — log /tmp/a.log\n")


def test_command_output_when_the_machine_lock_is_held(scratch):
    """The test command's run, as cosmic-ray runs it, while another run holds the machine lock.

    The test command and the suite runner are the real ones, so the case sees the streams
    cosmic-ray sees."""
    import fcntl
    repository, _, _ = scratch_repository(scratch, HEAD_FILES)
    lock_file = Path(scratch) / "machine.lock"
    environment = dict(os.environ)
    # Suites without an nc-test-sandbox: the path that takes the machine lock.
    environment[load_test_suite_runner().SIGNAL_SANDBOX_INSIDE_VARIABLE] = "1"
    with open(lock_file, "a+") as holder:
        fcntl.flock(holder, fcntl.LOCK_EX)
        holder.write("pid 7, the holder in this test\n")
        holder.flush()
        return subprocess.run(
            [sys.executable, str(SCRIPT), load_script_module().COSMIC_RAY_TEST_COMMAND_RUN_TEST_SUITE_RUNNER_STOPPED_AFTER_SECONDS_FLAG,
             "60.0", sys.executable, str(SCRIPT.with_name("run-all-test-suites.py")),
             "--checkout", str(repository), "--lock-file", str(lock_file),
             "--recorded-inputs-directory", str(Path(scratch) / "recordings"),
             "--only-suites-named", "scripts/thing-test.py"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=environment,
            timeout=60)


def killed_with_output(output):
    return {"worker_outcome": "normal", "output": output, "test_outcome": "killed",
            "diff": SURVIVOR_DIFF}


HANDLER_SOURCE = """import subprocess


def double(x):
    return x + x


def status(command):
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        return "failed"
    try:
        return int("7")
    except ValueError:
        return -1
"""

QUICK_HEAD_FILES = {
    "scripts/handler.py": HANDLER_SOURCE,
    "scripts/handler-test.py": "import sys\nsys.exit(0)\n",
}


def commit_on_top(repository, path, text):
    """Commit one more change on the repository's head; return (the old head, the new head)."""
    old_head = git(repository, "rev-parse", "HEAD")
    (repository / path).write_text(text)
    git(repository, "add", "-A")
    git(repository, "commit", "-q", "-m", "on top")
    return old_head, git(repository, "rev-parse", "HEAD")


def write_recording(control, repository, suite, recording):
    root = git(repository, "rev-list", "--max-parents=0", "HEAD")
    recordings = control / "recordings" / root[:16]
    recordings.mkdir(parents=True, exist_ok=True)
    (recordings / (suite.replace("/", "__") + ".json")).write_text(json.dumps(recording))


def suites_named(control):
    _, words = config_and_test_command_words(control)
    return words[words.index("--only-suites-named") + 1:] if words else []


def run_quick_mutation_pass_cases():
    survivors = load_script_module()

    # ------------------------------------------------------------------
    # What counts as failure-handling code, and which lines a change made.
    # ------------------------------------------------------------------
    source = ("def f(completed, runner_exit_code, code, process):\n"
              "    try:\n"
              "        g()\n"
              "    except OSError:\n"
              "        h()\n"
              "    while runner_exit_code != 0:\n"
              "        g()\n"
              "    word = 'failed' if completed.returncode else 'passed'\n"
              "    if code:\n"
              "        g()\n"
              "    if process.exit_status == 3:\n"
              "        g()\n"
              "    else:\n"
              "        h()\n")
    check("failure-handling code: each except clause, and each while, conditional expression "
          "and if statement whose test reads an exit code, from its first line to its last; "
          "not an if on another name",
          survivors.failure_handling_line_ranges(source) == [(4, 5), (6, 7), (8, 8), (11, 14)],
          survivors.failure_handling_line_ranges(source))
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, _, _ = scratch_repository(scratch_name, QUICK_HEAD_FILES)
        old_head, new_head = commit_on_top(
            repository, "scripts/handler.py",
            HANDLER_SOURCE.replace("    return x + x\n", "    return 2 * x\n").replace(
                "        return -1\n", "        return -2\n        # and more\n"))
        changed = survivors.changed_line_numbers_at_head(repository, old_head, new_head,
                                                        "scripts/handler.py", None)
        check("the changed lines are the head's numbers of every line changed or added",
              changed == {5, 15, 16}, changed)

    # ------------------------------------------------------------------
    # The quick mutation pass on a new file: only its failure-handling lines are mutated.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, QUICK_HEAD_FILES)
        venv, control = fake_venv(scratch_name, {"dump": [
            [work_item("scripts/handler.py", 10, "core/ReplaceComparisonOperator_NotEq_Eq", "a"),
             result("survived", diff=SURVIVOR_DIFF)]]})
        json_file = Path(scratch_name) / "mutants.json"
        completed = run_script(repository, control, "--quick-mutation-pass", "--head", head,
                               "--base", base, "--cosmic-ray-venv", str(venv),
                               "--survived-and-errored-mutants-json-file", str(json_file))
        config, _ = config_and_test_command_words(control)
        recorded = calls(control)
        check("quick mutation pass: a survivor makes the exit 1",
              completed.returncode == 1,
              f"rc={completed.returncode} out={completed.stdout} err={completed.stderr}")
        check("quick mutation pass: the config's line filter keeps the file's failure-handling "
              "lines",
              '[cosmic-ray.filters.line-filter]\nlines = { "scripts/handler.py" = '
              '["10-11", "14-15"] }\n' in config, config)
        check("quick mutation pass: cr-filter-lines runs with the config after cr-filter-git "
              "and cr-filter-pragma, before exec",
              [c["tool"] if c["tool"].startswith("cr-filter") else c["arguments"][0]
               for c in recorded]
              == ["baseline", "dump", "init", "cr-filter-git", "cr-filter-pragma",
                  "cr-filter-lines", "exec", "dump"]
              and recorded[5]["arguments"][:2] == ["--config", recorded[5]["arguments"][1]]
              and recorded[5]["arguments"][1].endswith(".toml"), json.dumps(recorded))
        check("quick mutation pass: the summary counts failure-handling lines and files with "
              "no failure-handling change",
              "SUMMARY: 1 mutants on changed failure-handling lines of 1 file(s): 0 killed, "
              "1 survived, 0 errored, 0 not run; 0 changed file(s) with no failure-handling "
              "change; 0 changed file(s) with no suite" in completed.stdout, completed.stdout)
        written = json.loads(json_file.read_text()) if json_file.exists() else {}
        check("the JSON file holds the head, the merge base and each survivor",
              written.get("head") == head and written.get("merge_base") == base
              and written.get("survived") == [{
                  "module_path": "scripts/handler.py", "line": 10,
                  "operator": "core/ReplaceComparisonOperator_NotEq_Eq",
                  "diff": SURVIVOR_DIFF, "reason": ""}]
              and written.get("errored") == [] and written.get("files_with_no_suite") == [],
              written)

    # A JSON file that cannot be written: exit 2, after the summary.
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, QUICK_HEAD_FILES)
        venv, control = fake_venv(scratch_name, {"dump": []})
        completed = run_script(repository, control, "--quick-mutation-pass", "--head", head,
                               "--base", base, "--cosmic-ray-venv", str(venv),
                               "--survived-and-errored-mutants-json-file",
                               str(Path(scratch_name) / "missing-directory" / "mutants.json"))
        check("a JSON file that cannot be written: exit 2, and the message says what to do",
              completed.returncode == 2 and "SUMMARY:" in completed.stdout
              and "were not written to" in completed.stderr
              and "Give --survived-and-errored-mutants-json-file a path" in completed.stderr,
              f"rc={completed.returncode} err={completed.stderr}")

    # A change with no failure-handling line is not mutated in the quick pass.
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, _, _ = scratch_repository(scratch_name, QUICK_HEAD_FILES)
        base, head = commit_on_top(repository, "scripts/handler.py",
                                   HANDLER_SOURCE.replace("x + x", "2 * x"))
        venv, control = fake_venv(scratch_name, {"dump": []})
        completed = run_script(repository, control, "--quick-mutation-pass", "--head", head,
                               "--base", base, "--cosmic-ray-venv", str(venv))
        check("quick mutation pass: a file whose changed lines hold no failure-handling code is "
              "not mutated, is named so, and leaves the exit 0",
              completed.returncode == 0 and calls(control) == []
              and "NO FAILURE-HANDLING CHANGE  scripts/handler.py" in completed.stdout
              and "1 changed file(s) with no failure-handling change" in completed.stdout,
              f"rc={completed.returncode} out={completed.stdout} calls={calls(control)}")

    # Suites: the quick pass leaves out the repository-wide checks and every suite whose
    # recording read every Python file tracked at its commit; the full pass keeps them.
    with tempfile.TemporaryDirectory() as scratch_name:
        files = dict(QUICK_HEAD_FILES)
        repository_wide_check = survivors.REPOSITORY_WIDE_CHECKS[0]
        for suite in ("scripts/reader-test.py", "scripts/all-reader-test.py",
                      "scripts/unknown-commit-reader-test.py", repository_wide_check):
            files[suite] = "import sys\nsys.exit(0)\n"
        repository, base, head = scratch_repository(scratch_name, files)
        every_python_file = {path: "blob" for path in files if path.endswith(".py")}
        venv, control = fake_venv(scratch_name, {"dump": []})
        write_recording(control, repository, "scripts/reader-test.py",
                        {"exit": 0, "commit": head, "reads": {"scripts/handler.py": "blob"}})
        write_recording(control, repository, "scripts/all-reader-test.py",
                        {"exit": 0, "commit": head, "reads": every_python_file})
        write_recording(control, repository, "scripts/unknown-commit-reader-test.py",
                        {"exit": 0, "commit": "f" * 40, "reads": every_python_file})
        write_recording(control, repository, repository_wide_check,
                        {"exit": 0, "commit": head, "reads": {"scripts/handler.py": "blob"}})
        completed = run_script(repository, control, "--quick-mutation-pass", "--head", head,
                               "--base", base, "--cosmic-ray-venv", str(venv))
        check("quick mutation pass: a repository-wide check, and a suite that read every Python "
              "file tracked at its recording's commit, are left out; a suite whose recording's "
              "commit git cannot list is kept",
              sorted(suites_named(control)) == ["scripts/handler-test.py",
                                                "scripts/reader-test.py",
                                                "scripts/unknown-commit-reader-test.py"],
              (suites_named(control), completed.stdout, completed.stderr))
        full_directory = Path(scratch_name) / "full"
        full_directory.mkdir()
        venv_full, control_full = fake_venv(full_directory, {"dump": []})
        (control_full / "recordings").symlink_to(control / "recordings")
        run_script(repository, control_full, "--full-mutation-pass", "--head", head,
                   "--base", base, "--cosmic-ray-venv", str(venv_full))
        check("full mutation pass: the repository-wide check and the suite that read every "
              "Python file are kept",
              sorted(suites_named(control_full)) == sorted([
                  "scripts/handler-test.py", "scripts/reader-test.py",
                  "scripts/all-reader-test.py", "scripts/unknown-commit-reader-test.py",
                  repository_wide_check]), suites_named(control_full))

    # A file whose only suites are left out has no suite in the quick pass.
    with tempfile.TemporaryDirectory() as scratch_name:
        repository_wide_check = survivors.REPOSITORY_WIDE_CHECKS[0]
        files = {"scripts/lonely.py": HANDLER_SOURCE,
                 repository_wide_check: "import sys\nsys.exit(0)\n"}
        repository, base, head = scratch_repository(scratch_name, files)
        venv, control = fake_venv(scratch_name, {"dump": []})
        write_recording(control, repository, repository_wide_check,
                        {"exit": 0, "commit": head, "reads": {"scripts/lonely.py": "blob"}})
        completed = run_script(repository, control, "--quick-mutation-pass", "--head", head,
                               "--base", base, "--cosmic-ray-venv", str(venv))
        check("quick mutation pass: a file read only by left-out suites has NO SUITE, exit 1, "
              "and the message says how to give it one",
              completed.returncode == 1 and calls(control) == []
              and "NO SUITE  scripts/lonely.py: once the repository-wide checks" in completed.stdout
              and "python3 scripts/run-all-test-suites.py --only-suites-named <the suite's path>"
              in completed.stdout,
              f"rc={completed.returncode} out={completed.stdout}")

    # A changed file that is not valid Python cannot be searched for failure-handling code.
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, {
            "scripts/broken.py": "def broken(:\n"})
        venv, control = fake_venv(scratch_name, {"dump": []})
        completed = run_script(repository, control, "--quick-mutation-pass", "--head", head,
                               "--base", base, "--cosmic-ray-venv", str(venv))
        check("quick mutation pass: a changed file that is not valid Python exits 2, naming it "
              "and the check to pass, and removes the worktree",
              completed.returncode == 2
              and "scripts/broken.py at the head is not valid Python" in completed.stderr
              and "python3 -m py_compile scripts/broken.py" in completed.stderr
              and len(worktrees_of(repository)) == 1,
              f"rc={completed.returncode} err={completed.stderr}")

    with tempfile.TemporaryDirectory() as scratch_name:
        worktree = Path(scratch_name)
        (worktree / "latin.py").write_bytes(b"NAME = '\xe9'\n")
        try:
            survivors.failure_handling_line_ranges_of_file(worktree, "latin.py")
            refused = ""
        except survivors.CouldNotRun as refusal:
            refused = str(refusal)
        check("quick mutation pass: a changed file that is not UTF-8 is refused as not valid "
              "Python", "latin.py at the head is not valid Python" in refused, refused)

    # Every listed repository-wide check is a suite in this repository.
    repository_root = SCRIPT.resolve().parent.parent
    missing = [suite for suite in survivors.REPOSITORY_WIDE_CHECKS
               if not (repository_root / suite).is_file()]
    check("every suite REPOSITORY_WIDE_CHECKS names exists, so a renamed check is not "
          "silently kept in the quick mutation pass", missing == [], missing)


def run_cases():
    # ------------------------------------------------------------------
    # The config written, the worktree used, and survivors parsed.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
        venv, control = fake_venv(scratch_name, {"dump": [
            [work_item("scripts/thing.py", 2, "core/ReplaceBinaryOperator_Add_Mul", "a"),
             result("survived", diff=SURVIVOR_DIFF)],
            [work_item("scripts/thing.py", 2, "core/ReplaceBinaryOperator_Add_Sub", "b"),
             result("killed")],
            [work_item("scripts/thing.py", 2, "core/NumberReplacer", "c"),
             result("incompetent")],
            [work_item("scripts/thing.py", 1, "core/AddNot", "d"),
             result(None, worker_outcome="skipped")],
            [work_item("scripts/thing.py", 1, "core/AddNot", "e"), None],
        ]})
        advanced_base = advance_base_past_merge_base(repository, base)
        # A temporary directory reached through a symbolic link, as macOS's /var is, so a
        # scratch worktree path the script did not resolve differs from the cwd recorded.
        temporary_directory = Path(scratch_name) / "temporary-directory"
        temporary_directory.mkdir()
        temporary_directory_link = Path(scratch_name) / "temporary-directory-link"
        temporary_directory_link.symlink_to(temporary_directory)
        completed = run_script(repository, control, "--head", head, "--base", advanced_base,
                               "--cosmic-ray-venv", str(venv),
                               "--python", "/usr/bin/python3",
                               "--mutant-timeout-seconds", "45",
                               extra_environment={"TMPDIR": str(temporary_directory_link)})
        out = completed.stdout
        config, test_command_words = config_and_test_command_words(control)
        recorded = calls(control)
        check("survivors found: exit 1", completed.returncode == 1,
              f"rc={completed.returncode} out={out} err={completed.stderr}")
        check("the config names the changed file as the module path",
              'module-path = "scripts/thing.py"' in config, config)
        worktree_seen = recorded[0]["cwd"] if recorded else None
        check("the scratch worktree is made in the temporary directory reached through the link",
              worktree_seen is not None
              and Path(worktree_seen).is_relative_to(temporary_directory.resolve()),
              worktree_seen)
        check("the test command is this script, stopping at the given --mutant-timeout-seconds "
              "one run of the suite runner beside the script, on the "
              "scratch worktree, of the sibling suite only, recording nothing and stopping at "
              "the first failing suite, with the given interpreter, recordings and lock",
              test_command_words == [
                  *cosmic_ray_timeout_line_and_test_command_words_for_limit(45)[1],
                  sys.executable, str(SCRIPT.resolve().with_name("run-all-test-suites.py")),
                  "--checkout", worktree_seen, "--python", "/usr/bin/python3",
                  "--recorded-inputs-directory", str(control / "recordings"),
                  "--leave-recorded-inputs-and-failure-history-unchanged",
                  "--stop-at-first-failing-suite",
                  "--lock-file", str(control / "machine.lock"),
                  "--only-suites-named", "scripts/thing-test.py"],
              (test_command_words, worktree_seen))
        check("the config sets the git filter's branch to the merge base, not the base's tip",
              f'branch = "{base}"' in config
              and "[cosmic-ray.filters.git-filter]" in config, config)
        check("the config uses the local distributor, and the given --mutant-timeout-seconds "
              "plus the runner's time to stop its suites as cosmic-ray's limit",
              'name = "local"' in config
              and cosmic_ray_timeout_line_and_test_command_words_for_limit(45)[0] in config,
              config)
        check("cosmic-ray runs baseline, its dump, init, cr-filter-git, cr-filter-pragma, exec "
              "and dump, in order, and the full mutation pass runs no cr-filter-lines",
              [c["tool"] if c["tool"].startswith("cr-filter") else c["arguments"][0]
               for c in recorded]
              == ["baseline", "dump", "init", "cr-filter-git", "cr-filter-pragma", "exec",
                  "dump"],
              json.dumps(recorded))
        check("the full mutation pass's config has no line filter",
              "line-filter" not in config, config)
        check("cosmic-ray runs in a worktree at the head, not in the checkout",
              recorded and all(c["head"] == head and Path(c["cwd"]).resolve()
                               != repository.resolve() for c in recorded),
              json.dumps(recorded))
        check("the suite itself is not mutated",
              "MUTATING  scripts/thing.py" in out and "MUTATING  scripts/thing-test.py" not in out,
              out)
        check("a survivor is printed with its file, line and operator",
              "SURVIVED  scripts/thing.py:2 core/ReplaceBinaryOperator_Add_Mul" in out, out)
        check("a survivor's diff is printed under it, indented",
              "    +    return x * x" in out, out)
        check("killed and errored mutants are not printed as survivors",
              out.count("SURVIVED") == 1, out)
        check("an incompetent mutant is printed as ERRORED with its file, line and operator",
              "ERRORED   scripts/thing.py:2 core/NumberReplacer" in out, out)
        check("the summary counts killed, survived and errored, leaving out "
              "skipped and unrun mutants",
              "SUMMARY: 3 mutants on changed lines of 1 file(s): 1 killed, 1 survived, "
              "1 errored, 1 not run; 0 changed file(s) with no suite" in out, out)
        check("the worktree is removed after a run",
              len(worktrees_of(repository)) == 1
              and not Path(recorded[0]["cwd"]).exists(), worktrees_of(repository))

    # ------------------------------------------------------------------
    # Every mutant killed: exit 0.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
        venv, control = fake_venv(scratch_name, {"dump": [
            [work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"), result("killed")]]})
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(venv),
                               extra_environment={"CLAUDE_CODE_SESSION_ATTENDED": "0"})
        check("every mutant killed: exit 0", completed.returncode == 0,
              f"rc={completed.returncode} out={completed.stdout} err={completed.stderr}")
        recorded = calls(control)
        check("cosmic-ray, which launches the suites, runs without the variable that says whether "
              "a user attends the agent-session",
              recorded and all(call["session_attended"] is None for call in recorded), recorded)

    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
        venv, control = fake_venv(scratch_name, {"dump": [
            [work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"), result("killed")],
            [work_item("scripts/thing.py", 2, "core/AddNot", "b"), None]]})
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(venv))
        check("a mutant that was never run makes the exit 1, though none survived",
              completed.returncode == 1 and "1 not run" in completed.stdout,
              f"rc={completed.returncode} out={completed.stdout}")

    # ------------------------------------------------------------------
    # A survivor alone makes the exit 1; errored mutants make it 1; a
    # no-test result, where cosmic-ray found nothing to mutate, does not.
    # ------------------------------------------------------------------
    for case_name, dump, wanted_exit, wanted_text in [
        ("a survivor alone makes the exit 1",
         [[work_item("scripts/thing.py", 2, "core/ReplaceBinaryOperator_Add_Mul", "a"),
           result("survived", diff=SURVIVOR_DIFF)]],
         1, "1 survived"),
        ("a mutant whose worker raised is ERRORED and makes the exit 1",
         [[work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
           result("incompetent", worker_outcome="exception")],
          [work_item("scripts/thing.py", 2, "core/NumberReplacer", "b"),
           result("killed")]],
         1, "1 errored"),
        ("a mutant whose suites could not be launched is ERRORED and makes the exit 1",
         [[work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
           result("incompetent")]],
         1, "1 errored"),
        ("a worker that raised is ERRORED even with a killed test outcome",
         [[work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
           result("killed", worker_outcome="exception")]],
         1, "1 errored"),
        ("a worker that ended abnormally is ERRORED, not SURVIVED, with a survived test outcome",
         [[work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
           result("survived", worker_outcome="abnormal")]],
         1, "0 survived, 1 errored"),
        ("a worker that ended abnormally is ERRORED even with a killed test outcome",
         [[work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
           result("killed", worker_outcome="abnormal")]],
         1, "1 errored"),
        # The record cosmic-ray 8.7.0 wrote for a suite that slept past the
        # timeout, copied from a real sweep.
        ("a mutant whose suites timed out is ERRORED with the reason, not killed",
         [[work_item("scripts/thing.py", 2, "core/ReplaceBinaryOperator_Add_Sub", "a"),
           {"worker_outcome": "normal", "output": "timeout", "test_outcome": "killed",
            "diff": SURVIVOR_DIFF}]],
         1, "0 killed, 0 survived, 1 errored"),
        ("the ERRORED line for a timed-out mutant names the timeout",
         [[work_item("scripts/thing.py", 2, "core/ReplaceBinaryOperator_Add_Sub", "a"),
           {"worker_outcome": "normal", "output": "timeout", "test_outcome": "killed",
            "diff": SURVIVOR_DIFF}]],
         1, "ERRORED   scripts/thing.py:2 core/ReplaceBinaryOperator_Add_Sub (timeout: the "
            f"suites ran past the limit of {DEFAULT_LIMIT_FOR_A_SUITE_WITHOUT_RECORDING:g} s "
            "on one run of them"),
        ("a mutant one of whose suites ran past its own limit in the suite runner is ERRORED, "
         "not killed",
         [[work_item("scripts/thing.py", 2, "core/ReplaceBinaryOperator_Add_Sub", "a"),
           killed_with_output(runner_output_with_suites_timed_out(
               [("scripts/thing-test.py", 1800)]))]],
         1, "0 killed, 0 survived, 1 errored"),
        ("the ERRORED line for a mutant whose suite ran past its own limit names the suite "
         "and the limit, once",
         [[work_item("scripts/thing.py", 2, "core/ReplaceBinaryOperator_Add_Sub", "a"),
           killed_with_output(runner_output_with_suites_timed_out(
               [("scripts/thing-test.py", 1800)]))]],
         1, "ERRORED   scripts/thing.py:2 core/ReplaceBinaryOperator_Add_Sub (suite timeout: "
            "scripts/thing-test.py ran past its own limit of 1800 s, so this mutant"),
        ("the ERRORED line for a mutant two of whose suites ran past their own limits names each",
         [[work_item("scripts/thing.py", 2, "core/ReplaceBinaryOperator_Add_Sub", "a"),
           killed_with_output(runner_output_with_suites_timed_out(
               [("scripts/thing-test.py", 1800), ("scripts/other-test.py", 600)]))]],
         1, "(suite timeout: scripts/thing-test.py ran past its own limit of 1800 s; "
            "scripts/other-test.py ran past its own limit of 600 s, so"),
        ("a mutant whose first failing suite stopped the suites beside it is killed",
         [[work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
           killed_with_output(
               "FAIL scripts/thing-test.py exit 1 (0.4s)\n"
               "FAIL scripts/other-test.py killed when the run was stopped by the first "
               "failing suite, scripts/thing-test.py (0.5s)\n")]],
         0, "1 killed, 0 survived, 0 errored"),
        ("a killed mutant whose output only mentions a timeout is still killed",
         [[work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
           {"worker_outcome": "normal",
            "output": "FAIL: case timeout handling\n" + SUITE_FAILED_RUNNER_OUTPUT,
            "test_outcome": "killed", "diff": None}]],
         0, "1 killed, 0 survived, 0 errored"),
        # Sorts after "timeout", so only an exact comparison keeps it killed.
        ("a killed mutant whose output is longer than the timeout record is still killed",
         [[work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
           {"worker_outcome": "normal", "output": "timeout\n" + SUITE_FAILED_RUNNER_OUTPUT,
            "test_outcome": "killed", "diff": None}]],
         0, "1 killed, 0 survived, 0 errored"),
        # Each a nonzero exit of the runner that cosmic-ray records as a kill, though no suite
        # failed under the mutant.
        ("a killed mutant whose runner printed nothing is ERRORED, not killed",
         [[work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
           killed_with_output("")]],
         1, "ERRORED   scripts/thing.py:2 core/NumberReplacer (no verdict: the suite runner "
            "exited nonzero but judged no suite failing, so this mutant was not judged; its "
            "output was empty)"),
        ("a killed mutant whose run was not run to the end is ERRORED, not killed, even "
         "after a suite failed",
         [[work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
           killed_with_output(
               "FAIL scripts/thing-test.py exit 1 (0.4s)\n"
               "run-all-test-suites: not run to the end — admission failed: gone\n")]],
         1, "0 killed, 0 survived, 1 errored"),
        ("the ERRORED line for a run not run to the end quotes the runner's line",
         [[work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
           killed_with_output(
               "PASS scripts/thing-test.py (0.4s)\n"
               "run-all-test-suites: not run to the end — admission failed: gone\n")]],
         1, "its output says: run-all-test-suites: not run to the end — admission failed: "
            "gone)"),
        ("a killed mutant the test command stopped at the limit on one run of the suites is "
         "ERRORED with the timeout, not killed",
         [[work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
           killed_with_output(
               f"{load_script_module().TEST_SUITE_RUNNER_STOPPED_AT_MUTANT_TIMEOUT_LINE_PREFIX}: it ran past "
               f"the limit of 45 s on one run of the suites\n"
               "FAIL scripts/thing-test.py exit 1 (0.4s)\n"
               "run-all-test-suites: not run to the end — stopped by SIGTERM.\n")]],
         1, "ERRORED   scripts/thing.py:2 core/NumberReplacer (timeout: the suites ran past "
            "the limit of"),
        ("a killed mutant whose failing suite was killed by a signal Python has no name for is "
         "killed",
         [[work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
           killed_with_output(runner_output_with_a_suite_failed_with_exit_code(
               "scripts/thing-test.py", -40))]],
         0, "1 killed, 0 survived, 0 errored"),
        ("a killed mutant whose every suite passed but whose records could not be written "
         "is ERRORED, not killed",
         [[work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
           killed_with_output(
               "PASS scripts/thing-test.py (0.4s)\n"
               "run-all-test-suites: the run's case times, suite resources, JUnit XML or "
               "failure history could not be written: full\n"
               "SUMMARY: 1 passed, 0 failed, 1 total\n")]],
         1, "0 killed, 0 survived, 1 errored"),
        ("a killed mutant whose only failing suite's nc-test-sandbox did not start is ERRORED, "
         "not killed",
         [[work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
           killed_with_output(runner_output_with_test_sandbox_not_started(
               "scripts/thing-test.py"))]],
         1, "0 killed, 0 survived, 1 errored"),
        ("the ERRORED line for a mutant whose only nonzero suite's nc-test-sandbox did not start "
         "quotes the runner's NOT RUN line, which names the suite",
         [[work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
           killed_with_output(runner_output_with_test_sandbox_not_started(
               "scripts/thing-test.py"))]],
         1, "its output says: NOT RUN scripts/thing-test.py did not start: bwrap could not "
            "build its nc-test-sandbox"),
        ("a killed mutant with one suite failing beside an nc-test-sandbox that did not start is "
         "killed",
         [[work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
           killed_with_output(runner_output_with_test_sandbox_not_started(
               "scripts/other-test.py") + SUITE_FAILED_RUNNER_OUTPUT)]],
         0, "1 killed, 0 survived, 0 errored"),
        ("a no-test result beside a killed mutant leaves the exit 0",
         [[work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"), result("killed")],
          [work_item("scripts/thing.py", 1, "core/AddNot", "b"),
           result(None, worker_outcome="no-test")]],
         0, "1 killed, 0 survived, 0 errored, 0 not run"),
    ]:
        with tempfile.TemporaryDirectory() as scratch_name:
            repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
            venv, control = fake_venv(scratch_name, {"dump": dump})
            completed = run_script(repository, control, "--head", head, "--base", base,
                                   "--cosmic-ray-venv", str(venv))
            check(case_name,
                  completed.returncode == wanted_exit and wanted_text in completed.stdout,
                  f"rc={completed.returncode} out={completed.stdout} err={completed.stderr}")

    # The machine lock's refusal, as the real test command and suite runner print it, reaches
    # the output cosmic-ray records, and the mutant is ERRORED with it.
    with tempfile.TemporaryDirectory() as scratch_name:
        refused = test_command_output_when_the_machine_lock_is_held(scratch_name)
    check("while another run holds the machine lock, the test command exits nonzero with the "
          "suite runner's refusal on its standard output and nothing on its standard error",
          refused.returncode == 3 and refused.stderr == ""
          and "run-all-test-suites: not run — another run holds" in refused.stdout
          and "pid 7, the holder in this test" in refused.stdout,
          f"rc={refused.returncode} out={refused.stdout} err={refused.stderr}")
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
        venv, control = fake_venv(scratch_name, {"dump": [
            [work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
             killed_with_output(refused.stdout)]]})
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(venv))
        check("a killed mutant whose run the machine's lock refused is ERRORED with the refusal",
              completed.returncode == 1
              and "(no verdict: the suite runner exited nonzero but judged no suite failing, "
                  "so this mutant was not judged; its output says: run-all-test-suites: not "
                  "run — another run holds" in completed.stdout,
              f"rc={completed.returncode} out={completed.stdout} err={completed.stderr}")

    # Every form describe_exit() gives a suite's own exit or signal is read as a failing suite.
    runner_module = load_test_suite_runner()
    parse = runner_module.run_all_test_suites_output_parse_whether_the_run_ended_with_a_suite_failed_by_its_exit_code_or_signal
    unread = [code for code in range(-64, 256) if code != 0 and not all(
        parse(line) for line in runner_output_with_a_suite_failed_with_exit_code(
            "scripts/thing-test.py", code).splitlines() if line.startswith("FAIL "))]
    check("each FAIL line form, for every exit code and signal describe_exit() names, is read "
          "as a failing suite",
          unread == [], unread)

    # ------------------------------------------------------------------
    # The test command stops a suite runner that runs past the limit on
    # one run of the suites, and the runner ends its suite's process group.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch_name:
        pid_file = Path(scratch_name) / "suite.pid"
        repository, base, head = scratch_repository(scratch_name, {
            **HEAD_FILES, "scripts/thing-test.py":
                f"import os, time\nopen({str(pid_file)!r}, 'w').write(str(os.getpid()))\n"
                f"time.sleep(120)\n"})
        venv, control = fake_venv(scratch_name, {"run_test_command": True, "dump": []})
        started = time.monotonic()
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(venv), "--mutant-timeout-seconds", "15")
        seconds = time.monotonic() - started
        ran = (json.loads((control / "test-command-run.json").read_text())
               if (control / "test-command-run.json").exists() else {})
        suite_pid = int(pid_file.read_text()) if pid_file.exists() else None
        suite_still_running = False
        if suite_pid is not None:
            try:
                os.kill(suite_pid, 0)
                suite_still_running = True
                os.kill(suite_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        check("a baseline the test command stopped at the limit exits 2, saying the suites ran "
              "out of time with that limit",
              completed.returncode == 2
              and "ran out of time on the unmutated head" in completed.stderr
              and "the limit of 15 s on one run of them" in completed.stderr,
              f"rc={completed.returncode} err={completed.stderr} ran={ran}")
        check("the test command says it stopped the suite runner, and the runner says it was "
              "stopped by SIGTERM",
              ran.get("exit") == 2
              and load_script_module().TEST_SUITE_RUNNER_STOPPED_AT_MUTANT_TIMEOUT_LINE_PREFIX
              in ran.get("stdout", "")
              and "not run to the end — stopped by SIGTERM" in ran.get("stdout", ""), ran)
        check("a suite running when the test command stops the suite runner has ended, before "
              "cosmic-ray's own limit",
              suite_pid is not None and not suite_still_running
              and seconds < 15 + EXTRA_SECONDS,
              (suite_pid, suite_still_running, seconds))

    # ------------------------------------------------------------------
    # A baseline cosmic-ray passes although its suites never launched:
    # exit 2, nothing mutated.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
        venv, control = fake_venv(scratch_name, {"baseline_dump": [
            [{"job_id": "baseline", "mutations": []},
             {"worker_outcome": "normal", "output": "FileNotFoundError: sh",
              "test_outcome": "incompetent", "diff": None}]]})
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(venv))
        recorded = calls(control)
        check("a baseline whose suites could not be launched exits 2 and quotes why",
              completed.returncode == 2
              and "could not be run on the unmutated head" in completed.stderr
              and "FileNotFoundError: sh" in completed.stderr,
              f"rc={completed.returncode} err={completed.stderr}")
        check("after a baseline whose suites could not be launched no mutant is run",
              [c["arguments"][0] for c in recorded] == ["baseline", "dump"],
              json.dumps(recorded))

    # ------------------------------------------------------------------
    # A renamed-and-changed file is mutated under its new name.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch_name:
        repository = Path(scratch_name) / "repository"
        repository.mkdir()
        git(repository, "init", "-q", "-b", "main")
        git(repository, "config", "user.email", "test@example.invalid")
        git(repository, "config", "user.name", "mutation survivors test")
        old_text = "".join(f"VALUE_{n} = {n}\n" for n in range(20))
        (repository / "scripts").mkdir()
        (repository / "scripts" / "old_name.py").write_text(old_text)
        git(repository, "add", "-A")
        git(repository, "commit", "-q", "-m", "base")
        base = git(repository, "rev-parse", "HEAD")
        git(repository, "mv", "scripts/old_name.py", "scripts/thing.py")
        (repository / "scripts" / "thing.py").write_text(
            old_text.replace("VALUE_3 = 3", "VALUE_3 = 33"))
        (repository / "scripts" / "thing-test.py").write_text("import sys\nsys.exit(0)\n")
        git(repository, "add", "-A")
        git(repository, "commit", "-q", "-m", "head")
        head = git(repository, "rev-parse", "HEAD")
        status = git(repository, "diff", "--name-status", base, head)
        venv, control = fake_venv(scratch_name, {"dump": [
            [work_item("scripts/thing.py", 4, "core/NumberReplacer", "a"), result("killed")]]})
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(venv))
        config = (control / "config.toml").read_text() if (control / "config.toml").exists() else ""
        check("a renamed-and-changed file is mutated under its new name",
              any(line.startswith("R") and line.endswith("\tscripts/thing.py")
                  for line in status.splitlines())
              and "MUTATING  scripts/thing.py" in completed.stdout
              and 'module-path = "scripts/thing.py"' in config
              and completed.returncode == 0,
              f"status={status!r} rc={completed.returncode} out={completed.stdout}")

    # ------------------------------------------------------------------
    # An inherited GIT_DIR does not point the git commands at another
    # repository.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
        other = Path(scratch_name) / "other"
        other.mkdir()
        git(other, "init", "-q", "-b", "main")
        venv, control = fake_venv(scratch_name, {"dump": [
            [work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"), result("killed")]]})
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(venv),
                               extra_environment={"GIT_DIR": str(other / ".git")})
        check("an inherited GIT_DIR naming another repository does not redirect the run",
              completed.returncode == 0 and "MUTATING  scripts/thing.py" in completed.stdout,
              f"rc={completed.returncode} out={completed.stdout} err={completed.stderr}")

    # ------------------------------------------------------------------
    # Suites chosen from the suite runner's recordings.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch_name:
        files = dict(HEAD_FILES)
        files["scripts/reader-test.py"] = "import sys\nsys.exit(0)\n"
        files["scripts/failed-reader-test.py"] = "import sys\nsys.exit(0)\n"
        files["scripts/other-file-reader-test.py"] = "import sys\nsys.exit(0)\n"
        repository, base, head = scratch_repository(scratch_name, files)
        venv, control = fake_venv(scratch_name, {"dump": []})
        root = git(repository, "rev-list", "--max-parents=0", "HEAD")
        recordings = control / "recordings" / root[:16]
        recordings.mkdir(parents=True)
        (recordings / "scripts__reader-test.py.json").write_text(json.dumps(
            {"exit": 0, "reads": {"scripts/thing.py": "blob"}}))
        (recordings / "scripts__other-file-reader-test.py.json").write_text(json.dumps(
            {"exit": 0, "reads": {"scripts/elsewhere.py": "blob"}}))
        (recordings / "scripts__failed-reader-test.py.json").write_text(json.dumps(
            {"exit": 1, "reads": {"scripts/thing.py": "blob"}}))
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(venv))
        config, words = config_and_test_command_words(control)
        named = words[words.index("--only-suites-named") + 1:] if words else []
        check("a suite whose passing recording reads the file is run on its mutants",
              "scripts/reader-test.py" in named and "scripts/thing-test.py" in named, words)
        check("a suite whose recording does not read the file is not run on its mutants",
              "scripts/other-file-reader-test.py" not in named, words)
        check("a suite whose recorded run did not pass is not chosen from that recording",
              "scripts/failed-reader-test.py" not in named, words)
        # reader-test.py's recording keeps no seconds, so both suites get the limit for no
        # passing recording, in as many rounds as the runner needs for two suites.
        runner_module = load_test_suite_runner()
        rounds = -(-2 // runner_module.suites_run_at_once(None, 2, os.cpu_count()))
        limit = (rounds * runner_module.TEST_SUITE_TIMEOUT_WITHOUT_PASSING_RECORDING_SECONDS
                 + load_script_module().TEST_SUITE_RUNNER_START_UP_SECONDS)
        timeout_line, first_words = cosmic_ray_timeout_line_and_test_command_words_for_limit(limit)
        check("by default the limit on one run of the suites is the longest suite limit times "
              "the runner's rounds, plus its start-up",
              timeout_line in config and words[:4] == first_words, (config, words))

    with tempfile.TemporaryDirectory() as scratch_name:
        files = dict(HEAD_FILES)
        files["scripts/slow-reader-test.py"] = "import sys\nsys.exit(0)\n"
        repository, base, head = scratch_repository(scratch_name, files)
        venv, control = fake_venv(scratch_name, {"dump": []})
        root = git(repository, "rev-list", "--max-parents=0", "HEAD")
        recordings = control / "recordings" / root[:16]
        recordings.mkdir(parents=True)
        (recordings / "scripts__slow-reader-test.py.json").write_text(json.dumps(
            {"exit": 0, "seconds": 900.0, "reads": {"scripts/thing.py": "blob"}}))
        (recordings / "scripts__thing-test.py.json").write_text(json.dumps(
            {"exit": 0, "seconds": 1.0, "reads": {"scripts/thing.py": "blob"}}))
        run_script(repository, control, "--head", head, "--base", base,
                   "--cosmic-ray-venv", str(venv))
        config, words = config_and_test_command_words(control)
        runner_module = load_test_suite_runner()
        rounds = -(-2 // runner_module.suites_run_at_once(None, 2, os.cpu_count()))
        limit = (rounds * runner_module.TEST_SUITE_TIMEOUT_MULTIPLE_OF_RECORDED_SECONDS * 900.0
                 + load_script_module().TEST_SUITE_RUNNER_START_UP_SECONDS)
        timeout_line, first_words = cosmic_ray_timeout_line_and_test_command_words_for_limit(limit)
        check("a suite's recorded passing seconds set its limit, and the longest limit sets "
              "the limit on one run of the suites",
              timeout_line in config and words[:4] == first_words, (config, words))

    # ------------------------------------------------------------------
    # A changed file with no suite is reported, not silently skipped.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(
            scratch_name, {"scripts/lonely.py": "VALUE = 1\n"})
        venv, control = fake_venv(scratch_name, {"dump": []})
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(venv))
        check("a changed file with no suite is named and makes the exit 1",
              completed.returncode == 1 and "NO SUITE  scripts/lonely.py" in completed.stdout
              and "1 changed file(s) with no suite" in completed.stdout,
              f"rc={completed.returncode} out={completed.stdout}")
        check("cosmic-ray is not run for a file with no suite", calls(control) == [],
              json.dumps(calls(control)))

    # ------------------------------------------------------------------
    # A nc-head-commit already in the base, as a merged pull request's is:
    # exit 2 before a worktree, not a 0-mutant success.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
        venv, control = fake_venv(scratch_name, {"dump": []})
        git(repository, "commit", "-q", "--allow-empty", "-m", "merged later")
        base_containing_head = git(repository, "rev-parse", "HEAD")
        for case_name, given_base in [
                ("a base that contains the nc-head-commit", base_containing_head),
                ("a base equal to the nc-head-commit", head)]:
            completed = run_script(repository, control, "--head", head,
                                   "--base", given_base, "--cosmic-ray-venv", str(venv))
            check(f"{case_name}: exit 2, saying the nc-head-commit is already in the base",
                  completed.returncode == 2
                  and f"head {head[:12]} is already in {given_base}" in completed.stderr
                  and "SUMMARY" not in completed.stdout,
                  f"rc={completed.returncode} out={completed.stdout} err={completed.stderr}")
            check(f"{case_name}: given --head, the command it suggests keeps <number> "
                  f"for the reader to fill in",
                  "gh pr view <number> --json headRefOid,baseRefOid" in completed.stderr,
                  f"rc={completed.returncode} out={completed.stdout} err={completed.stderr}")
            check(f"{case_name}: no worktree made, no cosmic-ray run",
                  len(worktrees_of(repository)) == 1 and calls(control) == [],
                  f"{worktrees_of(repository)} {json.dumps(calls(control))}")

    # ------------------------------------------------------------------
    # A change with no Python file to mutate is still a pass: the run
    # covered everything it tests.
    # ------------------------------------------------------------------
    for case_name, head_files, delete_path in [
            ("a change to a non-Python file only", {"docs/notes.md": "notes\n"}, None),
            ("a change that only deletes a Python file", {}, "scripts/gone.py")]:
        with tempfile.TemporaryDirectory() as scratch_name:
            if delete_path is None:
                repository, base, head = scratch_repository(scratch_name, head_files)
            else:
                repository, base, _ = scratch_repository(scratch_name,
                                                         {delete_path: "VALUE = 1\n"})
                base = git(repository, "rev-parse", "HEAD")
                git(repository, "rm", "-q", delete_path)
                git(repository, "commit", "-q", "-m", "delete")
                head = git(repository, "rev-parse", "HEAD")
            venv, control = fake_venv(scratch_name, {"dump": []})
            completed = run_script(repository, control, "--head", head, "--base", base,
                                   "--cosmic-ray-venv", str(venv))
            check(f"{case_name}: exit 0 with 0 mutants on 0 files",
                  completed.returncode == 0
                  and "SUMMARY: 0 mutants on changed lines of 0 file(s)" in completed.stdout,
                  f"rc={completed.returncode} out={completed.stdout} err={completed.stderr}")

    # ------------------------------------------------------------------
    # cosmic-ray missing.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
        _, control = fake_venv(scratch_name, {})
        empty_venv = Path(scratch_name) / "empty-venv"
        (empty_venv / "bin").mkdir(parents=True)
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(empty_venv))
        check("cosmic-ray missing from the given venv: exit 2, saying how to install it",
              completed.returncode == 2
              and "pip install cosmic-ray" in completed.stderr
              and "--cosmic-ray-venv" in completed.stderr
              and str(empty_venv / "bin") in completed.stderr,
              f"rc={completed.returncode} err={completed.stderr}")
        git_directory = str(Path(subprocess.run(["which", "git"], capture_output=True,
                                                text=True).stdout.strip()).parent)
        completed = run_script(repository, control, "--head", head, "--base", base,
                               path_override=git_directory)
        check("cosmic-ray missing from PATH with no venv given: exit 2, naming PATH",
              completed.returncode == 2 and "is not on PATH" in completed.stderr,
              f"rc={completed.returncode} err={completed.stderr}")
        check("no worktree is made when cosmic-ray is missing",
              len(worktrees_of(repository)) == 1, worktrees_of(repository))

    # ------------------------------------------------------------------
    # The baseline fails: exit 2, nothing mutated, worktree removed.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
        venv, control = fake_venv(scratch_name, {"baseline_exit": 1})
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(venv))
        recorded = calls(control)
        check("a failing baseline exits 2 and says the suites fail on the unmutated head",
              completed.returncode == 2 and "fail on the unmutated head" in completed.stderr,
              f"rc={completed.returncode} err={completed.stderr}")
        check("after a failing baseline its result is dumped, and no mutant is run",
              [c["arguments"][0] for c in recorded] == ["baseline", "dump"],
              json.dumps(recorded))
        check("the worktree is removed after a failing baseline",
              len(worktrees_of(repository)) == 1, worktrees_of(repository))

    # ------------------------------------------------------------------
    # A baseline that ran out of time is reported as a timeout, not as
    # failing suites; any other killed baseline still fails.
    # ------------------------------------------------------------------
    baseline_item = {"job_id": "baseline", "mutations": []}
    for case_name, plan, flags, wanted, unwanted in [
        ("a baseline killed with cosmic-ray's timeout output exits 2, says the suites ran out "
         "of time, gives the limit and says to raise --mutant-timeout-seconds",
         {"baseline_exit": 1, "baseline_dump": [[baseline_item, killed_with_output("timeout")]]},
         ("--mutant-timeout-seconds", "45"),
         ["ran out of time on the unmutated head", "the limit of 45 s on one run of them",
          "Run this again with --mutant-timeout-seconds larger than 45."], ["fail"]),
        ("a baseline killed with the suite runner's TIMEOUT line exits 2 naming the suite and "
         "its own limit",
         {"baseline_exit": 1, "baseline_dump": [[baseline_item, killed_with_output(
             runner_output_with_suites_timed_out([("scripts/thing-test.py", 1800)]))]]},
         (), ["on the unmutated head, scripts/thing-test.py ran past its own limit of 1800 s",
              "a larger --mutant-timeout-seconds does not raise it",
              "--only-suites-named scripts/thing-test.py\n"], ["fail"]),
        ("a baseline killed with any other output still says the suites fail",
         {"baseline_exit": 1, "baseline_dump": [[baseline_item, killed_with_output(
             "FAIL scripts/thing-test.py exit 1 (0.2s)\n")]]},
         (), ["fail on the unmutated head"], ["ran out of time", "ran past its own limit"]),
        ("a failing baseline whose result cannot be dumped still says the suites fail",
         {"baseline_exit": 1, "baseline_dump_exit": 4},
         (), ["fail on the unmutated head"], ["ran out of time", "ran past its own limit"]),
    ]:
        with tempfile.TemporaryDirectory() as scratch_name:
            repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
            venv, control = fake_venv(scratch_name, plan)
            completed = run_script(repository, control, "--head", head, "--base", base,
                                   "--cosmic-ray-venv", str(venv), *flags)
            check(case_name,
                  completed.returncode == 2
                  and all(text in completed.stderr for text in wanted)
                  and not any(text in completed.stderr.lower() for text in unwanted)
                  and [c["arguments"][0] for c in calls(control)] == ["baseline", "dump"],
                  f"rc={completed.returncode} err={completed.stderr}")

    # ------------------------------------------------------------------
    # The test command, run as cosmic-ray runs it: the suite runner runs
    # the suite in the scratch worktree and records nothing.
    # ------------------------------------------------------------------
    for case_name, suite_text, wanted_exit, wanted_run_exit, wanted_text in [
        ("the test command runs the sibling suite through the suite runner, which passes it",
         "import sys\nsys.exit(0)\n", 0, 0, "PASS scripts/thing-test.py"),
        ("a suite that fails on the unmutated head, run through the suite runner, makes the "
         "baseline fail",
         "import sys\nsys.exit(1)\n", 2, 1, "FAIL scripts/thing-test.py exit 1"),
    ]:
        with tempfile.TemporaryDirectory() as scratch_name:
            repository, base, head = scratch_repository(scratch_name, {
                **HEAD_FILES, "scripts/thing-test.py": suite_text})
            venv, control = fake_venv(scratch_name, {"run_test_command": True, "dump": [
                [work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
                 result("killed")]]})
            completed = run_script(repository, control, "--head", head, "--base", base,
                                   "--cosmic-ray-venv", str(venv))
            ran = (json.loads((control / "test-command-run.json").read_text())
                   if (control / "test-command-run.json").exists() else {})
            check(case_name,
                  completed.returncode == wanted_exit and ran.get("exit") == wanted_run_exit
                  and wanted_text in ran.get("stdout", "")
                  and "1 suites listed by git; 1 named by --only-suites-named"
                      in ran.get("stdout", ""),
                  f"rc={completed.returncode} ran={ran} err={completed.stderr}")
            check(f"{case_name}: the suite runner saves no recording of the suite",
                  not list((control / "recordings").rglob("*thing-test.py.json")),
                  sorted(str(path) for path in (control / "recordings").rglob("*")))

    # ------------------------------------------------------------------
    # A cosmic-ray step fails mid-run: exit 2 and the worktree is removed.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
        venv, control = fake_venv(scratch_name, {"exec_exit": 3})
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(venv))
        recorded = calls(control)
        check("a failing cosmic-ray exec exits 2 and names the step",
              completed.returncode == 2 and "cosmic-ray exec" in completed.stderr
              and "exit 3" in completed.stderr,
              f"rc={completed.returncode} err={completed.stderr}")
        check("the worktree is removed after a failed step",
              len(worktrees_of(repository)) == 1
              and recorded and not Path(recorded[0]["cwd"]).exists(),
              worktrees_of(repository))

    # ------------------------------------------------------------------
    # The head cannot be checked out: exit 2.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
        venv, control = fake_venv(scratch_name, {})
        completed = run_script(repository, control, "--head", "0" * 40, "--base", base,
                               "--cosmic-ray-venv", str(venv))
        check("a head that is not a commit exits 2 and says which step failed",
              completed.returncode == 2 and "git rev-parse" in completed.stderr,
              f"rc={completed.returncode} err={completed.stderr}")
        # A file where git keeps its worktree records makes `git worktree add` fail.
        worktrees_record = repository / ".git" / "worktrees"
        worktrees_record.write_text("")
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(venv))
        worktrees_record.unlink()
        check("a worktree that cannot be made exits 2 and names the step",
              completed.returncode == 2 and "git worktree add" in completed.stderr
              and "SUMMARY" not in completed.stdout,
              f"rc={completed.returncode} out={completed.stdout} err={completed.stderr}")

    # The runner's refusal to name the recordings directory is this program's refusal, exit 2.
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
        venv, control = fake_venv(scratch_name, {"dump": []})
        spec = importlib.util.spec_from_file_location(
            "mutation_testing_changed_lines_quick_or_full_pass_survivors", str(SCRIPT))
        survivors_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(survivors_module)
        load_runner_for_refusal = survivors_module.load_test_suite_runner

        def runner_that_cannot_name_the_recordings_directory():
            loaded_runner = load_runner_for_refusal()

            def refuse(given, top):
                raise loaded_runner.CouldNotRun(
                    f"{loaded_runner.PROGRAM}: not run — injected root-commit failure")
            loaded_runner.recordings_directory_for = refuse
            return loaded_runner

        survivors_module.load_test_suite_runner = runner_that_cannot_name_the_recordings_directory
        os.environ[CONTROL_DIRECTORY_VARIABLE] = str(control)
        printed = io.StringIO()
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(printed):
                status = survivors_module.main([
                    survivors_module.FULL_MUTATION_PASS_FLAG,
                    "--checkout", str(repository),
                    "--recorded-inputs-directory", str(control / "recordings"),
                    "--lock-file", str(control / "machine.lock"),
                    "--head", head, "--base", base, "--cosmic-ray-venv", str(venv)])
        except Exception as error:  # A crash is this case's failure, not the suite's.
            status = repr(error)
        finally:
            del os.environ[CONTROL_DIRECTORY_VARIABLE]
        check("when the runner cannot name the recordings directory, the run exits 2 with "
              "the runner's reason under this program's name",
              status == survivors_module.EXIT_COULD_NOT_RUN
              and printed.getvalue() == (
                  "mutation-testing-changed-lines-quick-or-full-pass-survivors: not run — injected root-commit "
                  "failure\n" + survivors_module.load_test_suite_runner()
                  .git_failure_next_step_lines("mutation-testing-changed-lines-quick-or-full-pass-survivors.py")
                  + "\n"), (status, printed.getvalue()))

    # ------------------------------------------------------------------
    # The signal sandbox, driven through a fake bwrap on PATH. The variable
    # that marks a run already inside the sandbox is dropped, since this
    # file itself runs inside the suite runner's sandbox.
    # ------------------------------------------------------------------
    if sys.platform.startswith("linux"):
        inside_variable = load_test_suite_runner().SIGNAL_SANDBOX_INSIDE_VARIABLE
        with tempfile.TemporaryDirectory() as scratch_name:
            repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
            venv, control = fake_venv(scratch_name, {"dump": []})
            fake_bin = Path(scratch_name) / "bin"
            fake_bin.mkdir()
            (fake_bin / "bwrap").write_text(
                "#!/bin/sh\necho 'bwrap: No permissions to create a new namespace' >&2\nexit 1\n")
            (fake_bin / "bwrap").chmod(0o755)
            completed = run_script(repository, control, "--head", head, "--base", base,
                                   "--cosmic-ray-venv", str(venv),
                                   path_override=f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
                                   dropped_variables=(inside_variable,))
            check("a bwrap that fails to start: exit 2, naming the sandbox and what bwrap printed",
                  completed.returncode == 2
                  and "the signal sandbox could not start" in completed.stderr
                  and "No permissions" in completed.stderr,
                  f"rc={completed.returncode} out={completed.stdout} err={completed.stderr}")
            check("a bwrap that fails to start: no worktree made, no cosmic-ray run",
                  len(worktrees_of(repository)) == 1 and calls(control) == [],
                  f"{worktrees_of(repository)} {json.dumps(calls(control))}")

        # A suite the runner lists as unable to work inside the sandbox runs
        # without the prefix in each mutant's test command, and the run says so.
        outside_suite = "scripts/mac-request-from-ned-box-forced-command-test.py"
        with tempfile.TemporaryDirectory() as scratch_name:
            repository, base, head = scratch_repository(scratch_name, {
                "scripts/mac-request-from-ned-box-forced-command.py":
                    "def double(x):\n    return x + x\n",
                outside_suite: "import sys\nsys.exit(0)\n"})
            venv, control = fake_venv(scratch_name, {"dump": []})
            fake_bin = Path(scratch_name) / "bin"
            fake_bin.mkdir()
            (fake_bin / "bwrap").write_text("#!/bin/sh\nexit 0\n")
            (fake_bin / "bwrap").chmod(0o755)
            completed = run_script(repository, control, "--head", head, "--base", base,
                                   "--cosmic-ray-venv", str(venv),
                                   path_override=f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
                                   dropped_variables=(inside_variable,))
            _, words = config_and_test_command_words(control)
            check("with the sandbox on, the run says each suite runs in its own nc-test-sandbox, named by the bwrap program",
                  f"each suite runs in its own nc-test-sandbox: {fake_bin / 'bwrap'}"
                  in completed.stdout, f"rc={completed.returncode} out={completed.stdout}")
            check("a suite listed to run outside the sandbox is named in a NO SANDBOX line",
                  f"NO SANDBOX  {outside_suite} runs WITHOUT the signal sandbox"
                  in completed.stdout, f"rc={completed.returncode} out={completed.stdout}")
            check("with the sandbox on, the test command leaves each suite's sandbox to the "
                  "suite runner",
                  words[-2:] == ["--only-suites-named", outside_suite]
                  and str(fake_bin / "bwrap") not in words, words)

        # Repository paths longer than a file name may be: each file named in the scratch
        # directory stays within the 255-byte limit.
        long_directory = "/".join(["d" * 80] * 3)
        long_source = f"{long_directory}/{'s' * 100}.py"
        long_suite = f"{long_directory}/{'s' * 100}-test.py"
        with tempfile.TemporaryDirectory() as scratch_name:
            repository, base, head = scratch_repository(scratch_name, {
                long_source: "def double(x):\n    return x + x\n",
                long_suite: "import sys\nsys.exit(0)\n"})
            venv, control = fake_venv(scratch_name, {"dump": []})
            fake_bin = Path(scratch_name) / "bin"
            fake_bin.mkdir()
            (fake_bin / "bwrap").write_text("#!/bin/sh\nexit 0\n")
            (fake_bin / "bwrap").chmod(0o755)
            completed = run_script(repository, control, "--head", head, "--base", base,
                                   "--cosmic-ray-venv", str(venv),
                                   path_override=f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
                                   dropped_variables=(inside_variable,))
            check("with paths longer than a file name may be, the run goes to its summary",
                  completed.returncode == 0 and "SUMMARY:" in completed.stdout
                  and "File name too long" not in completed.stderr,
                  f"rc={completed.returncode} out={completed.stdout[-600:]} "
                  f"err={completed.stderr[-600:]}")
    else:
        print("SKIP  the signal sandbox cases: bwrap is used only on Linux")

    run_quick_mutation_pass_cases()

    # ------------------------------------------------------------------
    # Path listings: names git would C-quote without -z come back as stored.
    # ------------------------------------------------------------------
    spec = importlib.util.spec_from_file_location("mutation_testing_changed_lines_quick_or_full_pass_survivors",
                                                  SCRIPT)
    survivors = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(survivors)

    runner_module = load_test_suite_runner()
    with tempfile.TemporaryDirectory() as recordings_name:
        many = [f"scripts/s{number}-test.py" for number in range(
            runner_module.TEST_SUITE_ADMISSION_SUITES_RUNNING_AT_ONCE_CEILING + 1)]
        limit = survivors.default_mutant_timeout_seconds_from_test_suites_own_time_limits(
            many, Path(recordings_name), runner_module, True)
    check("with more suites than the runner runs at once, cosmic-ray's limit covers each "
          "round of them",
          limit == 2 * runner_module.TEST_SUITE_TIMEOUT_WITHOUT_PASSING_RECORDING_SECONDS
          + survivors.TEST_SUITE_RUNNER_START_UP_SECONDS, limit)
    stem_for = survivors.scratch_file_name_stem_under_255_bytes_unique_to_repository_paths
    long_path = "/".join(["é" * 120] * 3) + ".py"
    stems = [stem_for(long_path, long_path), stem_for(long_path, long_path),
             stem_for("a/x.py", "a/x-test.py"), stem_for("b/x.py", "a/x-test.py")]
    check("a scratch file name stem stays within 255 bytes with its longest suffix, "
          "whatever the paths' length",
          len((stems[0] + ".baseline.sqlite").encode()) <= 255, stems[0])
    check("a scratch file name stem is the same for the same paths and differs for paths "
          "that differ only before the last name",
          stems[0] == stems[1] and stems[2] != stems[3], stems)
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, {
            "scripts/tést.py": "VALUE = 1\n",
            'scripts/say "hi".py': "VALUE = 2\n",
            "scripts/tést-test.py": "import sys\nsys.exit(0)\n",
        })
        files = survivors.changed_python_files_to_mutate(repository, base, head, None)
        check("the files to mutate are named as stored, a non-ASCII name and a quote included",
              sorted(files) == ['scripts/say "hi".py', "scripts/tést.py"], files)
        suites = survivors.suites_at_head(repository, head, None)
        check("the suites at head are named as stored",
              suites == ["scripts/tést-test.py"], suites)

    # ------------------------------------------------------------------
    # A stop signal while cosmic-ray runs still removes the worktree, git's
    # record of it, and the scratch directory.
    # ------------------------------------------------------------------
    for stop_signal in (signal.SIGTERM, signal.SIGHUP):
        name = signal.Signals(stop_signal).name
        with tempfile.TemporaryDirectory() as scratch_name:
            repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
            venv, control = fake_venv(scratch_name, {"exec_sleep_seconds": 60})
            temporary_directory = Path(scratch_name) / "tmp"
            temporary_directory.mkdir()
            worktrees_before = worktrees_of(repository)
            command, environment = script_command_and_environment(
                repository, control, "--head", head, "--base", base,
                "--cosmic-ray-venv", str(venv), "--python", "/usr/bin/python3",
                extra_environment={"TMPDIR": str(temporary_directory)})
            script = subprocess.Popen(command, env=environment, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, text=True)
            try:
                deadline = time.monotonic() + 60
                execs = []
                while not execs and time.monotonic() < deadline and script.poll() is None:
                    execs = [c for c in calls(control) if c["arguments"][:1] == ["exec"]]
                    time.sleep(0.1)
                script.send_signal(stop_signal)
                out, err = script.communicate(timeout=60)
            finally:
                if script.poll() is None:
                    script.kill()
                    script.communicate()
            worktree = Path(execs[0]["cwd"]) if execs else None
            check(f"{name} while cosmic-ray exec runs: the script exits 128 plus the signal "
                  f"number, having removed the worktree, git's record of it and the "
                  f"scratch directory",
                  worktree is not None and script.returncode == 128 + stop_signal
                  and not worktree.exists() and worktrees_of(repository) == worktrees_before
                  and list(temporary_directory.iterdir()) == [],
                  f"exec seen {worktree} rc={script.returncode} "
                  f"worktrees={worktrees_of(repository)} "
                  f"left={list(temporary_directory.iterdir())} out={out} err={err}")

    # ------------------------------------------------------------------
    # Bad invocations.
    # ------------------------------------------------------------------
    completed = subprocess.run([sys.executable, str(SCRIPT), "--quick-mutation-pass",
                                "--head", "abc"],
                               capture_output=True, text=True, check=False)
    check("--head without --base exits 2 and says why",
          completed.returncode == 2 and "--head needs --base" in completed.stderr,
          completed.stderr)
    completed = subprocess.run([sys.executable, str(SCRIPT), "--full-mutation-pass",
                                "--pull-request", "1", "--base", "main"],
                               capture_output=True, text=True, check=False)
    check("--base with --pull-request exits 2 and says why",
          completed.returncode == 2 and "--base goes with --head" in completed.stderr,
          completed.stderr)


if __name__ == "__main__":
    run_cases()
    print()
    if failures:
        print(f"{len(failures)} case(s) failed: {', '.join(failures)}")
        sys.exit(1)
    print("all cases passed")
