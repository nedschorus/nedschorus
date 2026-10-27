#!/usr/bin/env python3
"""Tests for pull-request-mutation-testing-survivors.py.

Run: python3 scripts/pull-request-mutation-testing-survivors-test.py
Prints one line per case and exits non-zero if any case fails.

No case runs the real cosmic-ray. Each case builds a scratch repository with
a base commit and a head commit, and points --cosmic-ray-venv at a fake venv
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

SCRIPT = Path(__file__).with_name("pull-request-mutation-testing-survivors.py")


def load_test_suite_runner():
    spec = importlib.util.spec_from_file_location(
        "run_all_test_suites", Path(__file__).with_name("run-all-test-suites.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_script_module():
    spec = importlib.util.spec_from_file_location("pull_request_mutation_testing_survivors",
                                                  str(SCRIPT))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# cosmic-ray's limit, by default, for one suite with no recording: one round of the runner.
DEFAULT_LIMIT_FOR_A_SUITE_WITHOUT_RECORDING = (
    load_test_suite_runner().TEST_SUITE_TIMEOUT_WITHOUT_PASSING_RECORDING_SECONDS
    + load_script_module().TEST_SUITE_RUNNER_START_UP_SECONDS)

CONTROL_DIRECTORY_VARIABLE = "PULL_REQUEST_MUTATION_TESTING_SURVIVORS_TEST_CONTROL_DIR"

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
    """A repository with a base commit and a head commit adding head_files."""
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
    for tool in ("cosmic-ray", "cr-filter-git"):
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


def result(test_outcome, worker_outcome="normal", diff=None):
    return {"worker_outcome": worker_outcome, "output": "", "test_outcome": test_outcome,
            "diff": diff}


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


def killed_with_output(output):
    return {"worker_outcome": "normal", "output": output, "test_outcome": "killed",
            "diff": SURVIVOR_DIFF}


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
        completed = run_script(repository, control, "--head", head, "--base", advanced_base,
                               "--cosmic-ray-venv", str(venv),
                               "--python", "/usr/bin/python3",
                               "--mutant-timeout-seconds", "45")
        out = completed.stdout
        config, test_command_words = config_and_test_command_words(control)
        recorded = calls(control)
        check("survivors found: exit 1", completed.returncode == 1,
              f"rc={completed.returncode} out={out} err={completed.stderr}")
        check("the config names the changed file as the module path",
              'module-path = "scripts/thing.py"' in config, config)
        worktree_seen = recorded[0]["cwd"] if recorded else None
        check("the test command is one run of the suite runner beside the script, on the "
              "scratch worktree, of the sibling suite only, recording nothing and stopping at "
              "the first failing suite, with the given interpreter, recordings and lock",
              test_command_words == [
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
        check("the config uses the local distributor and the given --mutant-timeout-seconds "
              "as cosmic-ray's limit",
              'name = "local"' in config and "timeout = 45.0" in config, config)
        check("cosmic-ray runs baseline, its dump, init, cr-filter-git, exec and dump, in order",
              [c["tool"] if c["tool"] == "cr-filter-git" else c["arguments"][0]
               for c in recorded]
              == ["baseline", "dump", "init", "cr-filter-git", "exec", "dump"],
              json.dumps(recorded))
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
            f"suites ran past cosmic-ray's limit of {DEFAULT_LIMIT_FOR_A_SUITE_WITHOUT_RECORDING:g} s"),
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
           {"worker_outcome": "normal", "output": "FAIL: case timeout handling\n",
            "test_outcome": "killed", "diff": None}]],
         0, "1 killed, 0 survived, 0 errored"),
        # Sorts after "timeout", so only an exact comparison keeps it killed.
        ("a killed mutant whose output is longer than the timeout record is still killed",
         [[work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
           {"worker_outcome": "normal", "output": "timeout\n",
            "test_outcome": "killed", "diff": None}]],
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
        check("by default cosmic-ray's limit is the longest suite limit times the runner's "
              "rounds, plus its start-up",
              f"timeout = {float(rounds * runner_module.TEST_SUITE_TIMEOUT_WITHOUT_PASSING_RECORDING_SECONDS + load_script_module().TEST_SUITE_RUNNER_START_UP_SECONDS)!r}"
              in config, config)

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
        config, _ = config_and_test_command_words(control)
        runner_module = load_test_suite_runner()
        rounds = -(-2 // runner_module.suites_run_at_once(None, 2, os.cpu_count()))
        check("a suite's recorded passing seconds set its limit, and the longest limit sets "
              "cosmic-ray's",
              f"timeout = {float(rounds * runner_module.TEST_SUITE_TIMEOUT_MULTIPLE_OF_RECORDED_SECONDS * 900.0 + load_script_module().TEST_SUITE_RUNNER_START_UP_SECONDS)!r}"
              in config, config)

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
    # A head commit already in the base, as a merged pull request's is:
    # exit 2 before a worktree, not a 0-mutant success.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
        venv, control = fake_venv(scratch_name, {"dump": []})
        git(repository, "commit", "-q", "--allow-empty", "-m", "merged later")
        base_containing_head = git(repository, "rev-parse", "HEAD")
        for case_name, given_base in [
                ("a base that contains the head commit", base_containing_head),
                ("a base equal to the head commit", head)]:
            completed = run_script(repository, control, "--head", head,
                                   "--base", given_base, "--cosmic-ray-venv", str(venv))
            check(f"{case_name}: exit 2, saying the head commit is already in the base",
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
         "of time, gives cosmic-ray's limit and says to raise --mutant-timeout-seconds",
         {"baseline_exit": 1, "baseline_dump": [[baseline_item, killed_with_output("timeout")]]},
         ("--mutant-timeout-seconds", "45"),
         ["ran out of time on the unmutated head", "cosmic-ray's limit of 45 s",
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
            "pull_request_mutation_testing_survivors", str(SCRIPT))
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
                  "pull-request-mutation-testing-survivors: not run — injected root-commit "
                  "failure\n" + survivors_module.load_test_suite_runner()
                  .git_failure_next_step_lines("pull-request-mutation-testing-survivors.py")
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
            check("with the sandbox on, the run says each suite runs in its own test sandbox, named by the bwrap program",
                  f"each suite runs in its own test sandbox: {fake_bin / 'bwrap'}"
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

    # ------------------------------------------------------------------
    # Path listings: names git would C-quote without -z come back as stored.
    # ------------------------------------------------------------------
    spec = importlib.util.spec_from_file_location("pull_request_mutation_testing_survivors",
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
    completed = subprocess.run([sys.executable, str(SCRIPT), "--head", "abc"],
                               capture_output=True, text=True, check=False)
    check("--head without --base exits 2 and says why",
          completed.returncode == 2 and "--head needs --base" in completed.stderr,
          completed.stderr)
    completed = subprocess.run([sys.executable, str(SCRIPT), "--pull-request", "1",
                                "--base", "main"],
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
