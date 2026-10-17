#!/usr/bin/env python3
"""Tests for pull-request-mutation-testing-survivors.py.

Run: python3 scripts/pull-request-mutation-testing-survivors-test.py
Prints one line per case and exits non-zero if any case fails.

No case runs the real cosmic-ray. Each case builds a scratch repository with
a base commit and a head commit, and points --cosmic-ray-venv at a fake venv
whose cosmic-ray and cr-filter-git record every call and behave as the
case's plan file says.
"""

import contextlib
import fcntl
import importlib.util
import io
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
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
CONTROL_DIRECTORY_VARIABLE = "PULL_REQUEST_MUTATION_TESTING_SURVIVORS_TEST_CONTROL_DIR"

FAKE_COSMIC_RAY_SOURCE = f'''#!/usr/bin/env python3
import fcntl, json, os, pathlib, subprocess, sys

control = pathlib.Path(os.environ["{CONTROL_DIRECTORY_VARIABLE}"])
plan = json.loads((control / "plan.json").read_text())
tool = pathlib.Path(sys.argv[0]).name
arguments = sys.argv[1:]
head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                      text=True).stdout.strip()
# Whether the machine lock was free at this call: a non-blocking flock that succeeds.
lock_free = None
if (control / "machine.lock").exists():
    with open(control / "machine.lock", "a") as lock_probe:
        try:
            fcntl.flock(lock_probe.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            lock_free = True
        except OSError:
            lock_free = False
# Which of admission's locks another process holds at this call.
def held_by_another(path):
    with open(path, "a") as probe:
        try:
            fcntl.flock(probe.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return False
        except OSError:
            return True
admission = control / "machine.lock.test-suite-admission"
slots_held = (sum(held_by_another(path) for path in admission.glob("slot-*"))
              if admission.is_dir() else 0)
outside = admission / "suites-run-outside-the-signal-sandbox.lock"
outside_lock_held = outside.exists() and held_by_another(outside)
with (control / "calls.log").open("a") as log:
    log.write(json.dumps({{"tool": tool, "arguments": arguments,
                          "cwd": os.getcwd(), "head": head,
                          "lock_free": lock_free, "niceness": os.nice(0),
                          "slots_held": slots_held, "outside_lock_held": outside_lock_held,
                          "session_attended": os.environ.get("CLAUDE_CODE_SESSION_ATTENDED")}}) + "\\n")
if tool == "cr-filter-git":
    sys.exit(plan.get("filter_exit", 0))
command = arguments[0]
if command == "baseline":
    (control / "config.toml").write_text(pathlib.Path(arguments[-1]).read_text())
    if "--session-file" in arguments:
        session = arguments[arguments.index("--session-file") + 1]
        pathlib.Path(session).write_text("baseline")
    sys.exit(plan.get("baseline_exit", 0))
if command == "init":
    pathlib.Path(arguments[2]).write_text("session")
    sys.exit(0)
if command == "exec":
    sys.exit(plan.get("exec_exit", 0))
if command == "dump":
    if pathlib.Path(arguments[1]).read_text() == "baseline":
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


def calls(control):
    return [json.loads(line) for line in
            (control / "calls.log").read_text().splitlines() if line]


ADMISSION_OPENED_DRIVER = r'''
import importlib.util, sys
program_path, *arguments = sys.argv[1:]
spec = importlib.util.spec_from_file_location("pull_request_mutation_testing_survivors", program_path)
program = importlib.util.module_from_spec(spec)
sys.argv = [program_path, *arguments]
spec.loader.exec_module(program)
load_runner = program.load_test_suite_runner
def load_runner_with_admission_opened():
    runner = load_runner()
    runner.TEST_SUITE_ADMISSION_CPU_PERCENT_BELOW = 101
    runner.TEST_SUITE_ADMISSION_AVAILABLE_MEMORY_BYTES_ABOVE = -1
    return runner
program.load_test_suite_runner = load_runner_with_admission_opened
sys.exit(program.main(arguments))
'''


def run_script(repository, control, *flags, path_override=None,
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
    # Never the real machine lock: the suite runner holds that one while this file runs.
    # Admission's thresholds are opened wide, so a case does not wait on a busy machine.
    return subprocess.run(
        [sys.executable, "-c", ADMISSION_OPENED_DRIVER, str(SCRIPT), "--checkout", str(repository),
         "--recorded-inputs-directory", str(control / "recordings"),
         "--lock-file", str(control / "machine.lock"), *flags],
        capture_output=True, text=True, check=False, env=environment, timeout=120)


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
        config = (control / "config.toml").read_text() if (control / "config.toml").exists() else ""
        recorded = calls(control)
        check("survivors found: exit 1", completed.returncode == 1,
              f"rc={completed.returncode} out={out} err={completed.stderr}")
        check("the config names the changed file as the module path",
              'module-path = "scripts/thing.py"' in config, config)
        test_suite_runner = load_test_suite_runner()
        # The script runs as inside the runner's sandbox (run_script), so it builds the
        # prefix the runner builds there; the sandbox cases below cover the bwrap prefix.
        sandbox_prefix, _ = test_suite_runner.signal_sandbox(environment={
            **os.environ, test_suite_runner.SIGNAL_SANDBOX_INSIDE_VARIABLE: "1"})
        launch = shlex.join([*sandbox_prefix, "/usr/bin/python3", "-u", "scripts/thing-test.py"])
        # On macOS the prefix names the process that built it, which differs between
        # this file and the script it runs.
        outside_process = re.compile(
            re.escape(test_suite_runner.SIGNAL_SANDBOX_TRIAL_SIGNAL_TARGET_PROCESS_VARIABLE) + r"=\d+")
        check("the config's test command runs the sibling suite through sh -c, "
              "because cosmic-ray runs it without a shell, inside the signal sandbox "
              "when this machine has one",
              outside_process.sub("OUTSIDE", f"test-command = {json.dumps('sh -c ' + shlex.quote(launch))}")
              in outside_process.sub("OUTSIDE", config),
              (launch, config))
        check("the config sets the git filter's branch to the merge base, not the base's tip",
              f'branch = "{base}"' in config
              and "[cosmic-ray.filters.git-filter]" in config, config)
        check("the config uses the local distributor and the given timeout",
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
         1, "ERRORED   scripts/thing.py:2 core/ReplaceBinaryOperator_Add_Sub (timeout:"),
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
        config = (control / "config.toml").read_text() if (control / "config.toml").exists() else ""
        check("a suite whose passing recording reads the file is run on its mutants",
              "scripts/reader-test.py" in config and "scripts/thing-test.py" in config,
              config)
        check("a suite whose recording does not read the file is not run on its mutants",
              "other-file-reader-test.py" not in config, config)
        check("a suite whose recorded run did not pass is not chosen from that recording",
              "failed-reader-test.py" not in config, config)

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
    # exit 2 before the lock or a worktree, not a 0-mutant success.
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
            check(f"{case_name}: no lock taken, no worktree made, no cosmic-ray run",
                  not (control / "machine.lock").exists()
                  and len(worktrees_of(repository)) == 1 and calls(control) == [],
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
        check("after a failing baseline no mutant is run",
              [c["arguments"][0] for c in recorded] == ["baseline"], json.dumps(recorded))
        check("the worktree is removed after a failing baseline",
              len(worktrees_of(repository)) == 1, worktrees_of(repository))

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

    # ------------------------------------------------------------------
    # The machine lock: held through every cosmic-ray call, refused at
    # once when another process holds it, released when the run ends.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
        venv, control = fake_venv(scratch_name, {"dump": [
            [work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"), result("killed")]]})
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(venv))
        recorded = calls(control)
        check("the machine lock is held through every cosmic-ray call, baseline to exec",
              completed.returncode == 0 and len(recorded) >= 6
              and all(call["lock_free"] is False for call in recorded),
              f"rc={completed.returncode} calls={recorded} err={completed.stderr}")
        check("the lock file names the run that held it",
              f"checkout {repository.resolve()}" in (control / "machine.lock").read_text(),
              (control / "machine.lock").read_text())

    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
        venv, control = fake_venv(scratch_name, {"dump": [
            [work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"), result("killed")]]})
        with open(control / "machine.lock", "a+") as held:
            held.write("pid 1, checkout a flock the caller started\n")
            held.flush()
            fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            completed = run_script(repository, control, "--head", head, "--base", base,
                                   "--cosmic-ray-venv", str(venv))
        check("a held lock exits 3 at once, naming the lock and its recorded holder",
              completed.returncode == 3
              and str(control / "machine.lock") in completed.stderr
              and "a flock the caller started" in completed.stderr,
              f"rc={completed.returncode} err={completed.stderr}")
        check("a held lock tells a caller under flock to run the script without flock",
              "If you started this script under flock on that lock" in completed.stderr
              and "run this script without flock" in completed.stderr,
              completed.stderr)
        check("a held lock runs no cosmic-ray and makes no worktree",
              calls(control) == [] and len(worktrees_of(repository)) == 1,
              f"calls={calls(control)} worktrees={worktrees_of(repository)}")

    # A suite run killed while holding the lock leaves its traces for the next
    # holder to remove; when that holder is this script, it must remove them.
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
        venv, control = fake_venv(scratch_name, {"dump": [
            [work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"), result("killed")]]})
        killed_run_logs = Path(scratch_name) / "killed-suite-run-logs"
        left_trace = killed_run_logs / "recorded-inputs" / "some-suite-test.py.strace"
        left_trace.mkdir(parents=True)
        (left_trace / "trace.123").write_text("openat(...)\n")
        kept_log = killed_run_logs / "some-suite-test.py.log"
        kept_log.write_text("PASS\n")
        (control / "machine.lock").write_text(
            f"pid 99999, checkout /elsewhere, started 2026-10-04T00:00:00Z, "
            f"logs in {killed_run_logs}\n")
        test_suite_runner = load_test_suite_runner()
        if sys.platform.startswith("linux"):
            # On Linux the runner keeps a record of each run; this one has ended.
            # Started to sleep, so its start ticks are read while it still runs.
            ended = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
            ended_ticks = test_suite_runner.process_start_ticks(ended.pid)
            ended.terminate()
            ended.wait()
            runs = test_suite_runner.run_records_directory_for_lock_file(control / "machine.lock")
            runs.mkdir(parents=True, exist_ok=True)
            (runs / f"{ended.pid}-{ended_ticks}.json").write_text(json.dumps({
                "runner": {"pid": ended.pid, "start_ticks": ended_ticks},
                "log_dir": str(killed_run_logs), "log_dir_is_temporary": False,
                "started": "then", "finished": None, "suite_processes": []}))
        completed = run_script(repository, control, "--head", head, "--base", base,
                               "--cosmic-ray-venv", str(venv))
        check("taking the lock removes the traces a killed suite run left, as the runner would",
              completed.returncode == 0 and not left_trace.exists(),
              f"rc={completed.returncode} trace_left={left_trace.exists()} err={completed.stderr}")
        check("and removes only the traces, not the killed run's logs",
              kept_log.exists(), f"log_kept={kept_log.exists()}")

    # In this process, so the lock's release is seen before the process exits.
    with tempfile.TemporaryDirectory() as scratch_name:
        repository, base, head = scratch_repository(scratch_name, HEAD_FILES)
        venv, control = fake_venv(scratch_name, {"dump": [
            [work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"), result("killed")]]})
        spec = importlib.util.spec_from_file_location(
            "pull_request_mutation_testing_survivors", str(SCRIPT))
        survivors_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(survivors_module)
        released = {}
        free_at_worktree_removal = {}
        remove_worktree = survivors_module.remove_worktree

        def remove_worktree_noting_the_lock(checkout, worktree, environment):
            with open(control / "machine.lock", "a") as probe:
                try:
                    fcntl.flock(probe.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    free_at_worktree_removal[label] = True
                except OSError:
                    free_at_worktree_removal[label] = False
            remove_worktree(checkout, worktree, environment)

        survivors_module.remove_worktree = remove_worktree_noting_the_lock
        for label, plan_exit in (("after a run", 0), ("after a failed step", 7)):
            (control / "plan.json").write_text(json.dumps({
                "exec_exit": plan_exit,
                "dump": [[work_item("scripts/thing.py", 2, "core/NumberReplacer", "a"),
                          result("killed")]]}))
            os.environ[CONTROL_DIRECTORY_VARIABLE] = str(control)
            try:
                with contextlib.redirect_stdout(io.StringIO()), \
                        contextlib.redirect_stderr(io.StringIO()):
                    survivors_module.main([
                        "--checkout", str(repository),
                        "--recorded-inputs-directory", str(control / "recordings"),
                        "--lock-file", str(control / "machine.lock"),
                        "--head", head, "--base", base, "--cosmic-ray-venv", str(venv)])
            finally:
                del os.environ[CONTROL_DIRECTORY_VARIABLE]
            with open(control / "machine.lock", "a") as probe:
                try:
                    fcntl.flock(probe.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    released[label] = True
                except OSError:
                    released[label] = False
        check("the machine lock is released when the run ends, and after a failed step",
              released == {"after a run": True, "after a failed step": True}, released)
        check("the machine lock is released before the worktree is removed",
              free_at_worktree_removal == {"after a run": True, "after a failed step": True},
              free_at_worktree_removal)

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
            check("a bwrap that fails to start: no lock taken, no worktree made, no cosmic-ray run",
                  not (control / "machine.lock").exists()
                  and len(worktrees_of(repository)) == 1 and calls(control) == [],
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
            config = ((control / "config.toml").read_text()
                      if (control / "config.toml").exists() else "")
            check("with the sandbox on, the run says each suite runs in its own test sandbox, named by the bwrap program",
                  f"each suite runs in its own test sandbox: {fake_bin / 'bwrap'}"
                  in completed.stdout, f"rc={completed.returncode} out={completed.stdout}")
            check("a suite listed to run outside the sandbox is named in a NO SANDBOX line",
                  f"NO SANDBOX  {outside_suite} runs WITHOUT the signal sandbox"
                  in completed.stdout, f"rc={completed.returncode} out={completed.stdout}")
            check("a suite listed to run outside the sandbox runs without the prefix in "
                  "the mutant's test command",
                  outside_suite in config and str(fake_bin / "bwrap") not in config,
                  config)
            cosmic_ray_calls = [call for call in calls(control) if call["tool"] == "cosmic-ray"]
            check("in test sandboxes, cosmic-ray, and so every suite it runs, holds an admission "
                  "slot and runs at low priority",
                  cosmic_ray_calls
                  and all(call["slots_held"] >= 1 for call in cosmic_ray_calls)
                  and all(call["niceness"] >= 10 for call in cosmic_ray_calls),
                  json.dumps(cosmic_ray_calls)[:800])
            check("with a suite that runs outside the sandbox, cosmic-ray holds the lock those "
                  "suites share with every other run",
                  cosmic_ray_calls
                  and all(call["outside_lock_held"] for call in cosmic_ray_calls),
                  json.dumps(cosmic_ray_calls)[:800])
            check("in test sandboxes, no machine lock is taken",
                  not (control / "machine.lock").exists()
                  and all(call["lock_free"] is None for call in cosmic_ray_calls),
                  json.dumps(cosmic_ray_calls)[:800])

        # An interpreter the test sandbox would hide, as `--python ~/venv/bin/python` names
        # one: its installation is shown read-only in each mutant's sandbox.
        with tempfile.TemporaryDirectory() as scratch_name, tempfile.TemporaryDirectory(
                dir=Path.home()) as home_name:
            repository, base, head = scratch_repository(scratch_name, {
                "scripts/doubler.py": "def double(x):\n    return x + x\n",
                "scripts/doubler-test.py": "import sys\nsys.exit(0)\n"})
            venv, control = fake_venv(scratch_name, {"dump": []})
            fake_bin = Path(scratch_name) / "bin"
            fake_bin.mkdir()
            (fake_bin / "bwrap").write_text("#!/bin/sh\nexit 0\n")
            (fake_bin / "bwrap").chmod(0o755)
            installation = Path(home_name).resolve() / "python-installation"
            (installation / "bin").mkdir(parents=True)
            standard_library = installation / "lib" / "python3.99"
            standard_library.mkdir(parents=True)
            home_python = installation / "bin" / "python3"
            # Answers the question of what it loads as a real interpreter installed there would.
            home_python.write_text("#!/bin/sh\nprintf " + shlex.quote("\\0".join(
                [str(home_python)] * 2 + [str(standard_library)] * 4)) + "\n")
            home_python.chmod(0o755)
            completed = run_script(repository, control, "--head", head, "--base", base,
                                   "--cosmic-ray-venv", str(venv), "--python", str(home_python),
                                   path_override=f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
                                   dropped_variables=(inside_variable,))
            config = ((control / "config.toml").read_text()
                      if (control / "config.toml").exists() else "")
            check("an interpreter in the hidden home directory has what it loads shown "
                  "read-only in each mutant's test sandbox",
                  f"--ro-bind {standard_library} {standard_library}" in config
                  and f"--ro-bind {home_python} {home_python}" in config,
                  f"rc={completed.returncode} out={completed.stdout[-600:]} config={config[:1500]}")
    else:
        print("SKIP  the signal sandbox cases: bwrap is used only on Linux")

    # ------------------------------------------------------------------
    # Path listings: names git would C-quote without -z come back as stored.
    # ------------------------------------------------------------------
    spec = importlib.util.spec_from_file_location("pull_request_mutation_testing_survivors",
                                                  SCRIPT)
    survivors = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(survivors)

    # A test sandbox that does not start: cosmic-ray would count the failing exit as a
    # killed mutant, so the suite's proof stays empty and the run stops instead.
    with tempfile.TemporaryDirectory() as scratch_name:
        scratch = Path(scratch_name)
        (scratch / "a-test.py").write_text("print('ran')\n")
        proof, did_not_start = scratch / "a.started", scratch / "did-not-start"
        for label, prefix, expected_exit, named in (
                ("a sandbox that starts", ("env",), 0, False),
                ("a sandbox that fails before the suite", ("sh", "-c", "exit 1", "stand-in"), 1,
                 True)):
            did_not_start.unlink(missing_ok=True)
            command = survivors.test_command_for(["a-test.py"], sys.executable, prefix, (),
                                                 {"a-test.py": proof}, did_not_start)
            completed = subprocess.run(shlex.split(command), cwd=scratch, capture_output=True,
                                       text=True, timeout=60)
            check(f"{label}: the test command exits {expected_exit}, and names the suite as "
                  f"not started {'' if named else 'not '}at all",
                  completed.returncode == expected_exit
                  and did_not_start.exists() == named
                  and (not named or did_not_start.read_text().split() == ["a-test.py"]),
                  (completed.returncode, did_not_start.exists(), completed.stderr))
            try:
                survivors.raise_when_a_test_sandbox_did_not_start(did_not_start, "a.py", "baseline")
                raised = None
            except survivors.CouldNotRun as error:
                raised = str(error)
            check(f"{label}: the run {'stops, naming the suite' if named else 'goes on'}",
                  (raised is not None and "a-test.py" in raised and "did not start" in raised)
                  if named else raised is None, raised)
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
